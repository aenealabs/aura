"""Tests for the Dependabot triage snapshot collector."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.security import dep_triage as dt
from scripts.security import dep_triage_collect as dc

RAW_FIXTURE = Path("tests/fixtures/dep_triage/raw_2026_09_19.json")
SNAPSHOT_FIXTURE = Path("tests/fixtures/dep_triage/batch_2026_09_19.json")

# The login form `gh` actually emits. Every author literal in this file uses it,
# because a test that invents `dependabot[bot]` is testing a string the tool
# under test never sees.
GH_DEPENDABOT = {"login": "app/dependabot", "is_bot": True}


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "chore(deps): bump github/codeql-action/init from 4.37.9 to 4.38.0",
            ("github/codeql-action/init", "4.37.9", "4.38.0"),
        ),
        (
            "chore(deps-dev): bump vitest from 4.1.11 to 5.0.0 in /frontend",
            ("vitest", "4.1.11", "5.0.0"),
        ),
        (
            "chore(deps): update pydantic requirement from >=2.12.5 to >=2.13.5",
            ("pydantic", ">=2.12.5", ">=2.13.5"),
        ),
        ("chore: release 1.8.0", ("", "", "")),
        # Dependabot's own default title forms (no conventional-commit
        # prefix). This repo only sees the lowercase "chore(deps): bump ..."
        # form because Dependabot infers that prefix from repo history --
        # .github/dependabot.yml sets no commit-message.prefix to guarantee
        # it -- so these must parse too, not just the inferred form.
        (
            "Bump vitest from 4.0.16 to 5.0.0",
            ("vitest", "4.0.16", "5.0.0"),
        ),
        (
            "Update vitest requirement from ^4.0.16 to ^5.0.0",
            ("vitest", "^4.0.16", "^5.0.0"),
        ),
    ],
)
def test_parse_bump_title(title, expected):
    assert dc.parse_bump_title(title) == expected


def test_build_snapshot_emits_schema_load_snapshot_accepts(tmp_path):
    snapshot = dc.build_snapshot(
        prs=[
            {
                "number": 450,
                "title": "chore(deps): bump github/codeql-action/upload-sarif "
                "from 4.37.9 to 4.38.0",
                "author": GH_DEPENDABOT,
                "files": [".github/workflows/code-quality.yml"],
            }
        ],
        checks_by_pr={
            450: [
                {
                    "name": "Analyze (python)",
                    "status": "completed",
                    "conclusion": "success",
                    "failing_log_excerpt": "",
                },
            ]
        },
        required_checks=["Analyze (python)"],
        release_ages={("github-actions", "github/codeql-action/upload-sarif"): 9.0},
        risk_tiers={},
    )
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    prs = dt.load_snapshot(path)
    assert len(prs) == 1
    assert prs[0].ecosystem == "github-actions"
    assert prs[0].package == "github/codeql-action/upload-sarif"


def test_build_snapshot_keys_release_age_by_ecosystem_and_package():
    """A same-named pip and npm package in one batch must not clobber each
    other's cached release age -- the cache key includes the ecosystem."""
    snapshot = dc.build_snapshot(
        prs=[
            {
                "number": 1,
                "title": "chore(deps): bump six from 1.0.0 to 1.1.0",
                "author": GH_DEPENDABOT,
                "files": ["requirements.txt"],
            },
            {
                "number": 2,
                "title": "chore(deps-dev): bump six from 1.0.0 to 1.1.0 in /frontend",
                "author": GH_DEPENDABOT,
                "files": ["frontend/package.json"],
            },
        ],
        checks_by_pr={},
        required_checks=[],
        release_ages={("pip", "six"): 30.0, ("npm", "six"): 2.0},
        risk_tiers={},
    )
    by_number = {p["number"]: p for p in snapshot["pull_requests"]}
    assert by_number[1]["ecosystem"] == "pip"
    assert by_number[1]["release_age_days"] == 30.0
    assert by_number[2]["ecosystem"] == "npm"
    assert by_number[2]["release_age_days"] == 2.0


def test_infer_ecosystem_from_files():
    assert dc.infer_ecosystem([".github/workflows/x.yml"]) == "github-actions"
    assert dc.infer_ecosystem(["frontend/package.json"]) == "npm"
    assert dc.infer_ecosystem(["requirements.txt"]) == "pip"
    assert dc.infer_ecosystem(["deploy/docker/api/Dockerfile"]) == "docker"
    assert dc.infer_ecosystem(["CHANGELOG.md"]) == "unknown"


def test_infer_directory_from_files():
    assert dc.infer_directory(["frontend/package.json"]) == "/frontend"
    assert dc.infer_directory(["sdk/typescript/package.json"]) == "/sdk/typescript"
    assert dc.infer_directory(["requirements.txt"]) == "/"


def test_the_security_advisory_fast_path_is_gone():
    """Removed deliberately; see the dep_triage module docstring.

    It searched only the text before the first collapsible block, but a real
    Dependabot security body puts the CVE/GHSA id *inside* that block and leaves
    only prose in the preamble -- so it returned False on the updates it existed
    for. It returned True for bodies with no collapsible block at all, which is
    the docker and github-actions shape, where release_age_days is
    unconditionally None and rule_cooldown would otherwise hold the PR. Its only
    observable effect was converting a permanent hold into a candidate while
    stripping the major-version guard too.

    The correct signal, if the capability is wanted later, is
    `gh api repos/{owner}/{repo}/dependabot/alerts` correlated by package and
    `fixed_in` version."""
    assert not hasattr(dc, "is_security_advisory")
    assert not hasattr(dc, "_ADVISORY")
    assert not hasattr(dc, "_DETAILS_OPEN")


def test_build_snapshot_records_whether_the_author_is_a_bot(tmp_path):
    """Carried for the report's reason text; the login stays the decision."""
    snapshot = dc.build_snapshot(
        prs=[
            {
                "number": 1,
                "title": "chore(deps): bump urllib3 from 2.0.0 to 2.0.1",
                "author": GH_DEPENDABOT,
                "files": ["requirements.txt"],
            },
            {
                "number": 2,
                "title": "docs: fix a typo",
                "author": {"login": "lavrut", "is_bot": False},
                "files": ["README.md"],
            },
        ],
        checks_by_pr={},
        required_checks=[],
        release_ages={},
        risk_tiers={},
    )
    by_number = {p["number"]: p for p in snapshot["pull_requests"]}
    assert by_number[1]["author_is_bot"] is True
    assert by_number[2]["author_is_bot"] is False
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    loaded = {p.number: p for p in dt.load_snapshot(path)}
    assert loaded[1].author_is_bot is True
    assert loaded[2].author_is_bot is False


def test_build_snapshot_tolerates_a_missing_author_block():
    """`gh` has omitted `author` on PRs from deleted accounts."""
    snapshot = dc.build_snapshot(
        prs=[{"number": 1, "title": "x", "author": None, "files": []}],
        checks_by_pr={},
        required_checks=[],
        release_ages={},
        risk_tiers={},
    )
    assert snapshot["pull_requests"][0]["author"] == ""
    assert snapshot["pull_requests"][0]["author_is_bot"] is False


def test_release_age_days_computes_from_pip_upload_time():
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)

    def fake_fetch(url):
        assert url == "https://pypi.org/pypi/pydantic/2.13.5/json"
        return {"urls": [{"upload_time_iso_8601": "2026-09-09T00:00:00Z"}]}

    age = dc.release_age_days("pip", "pydantic", "2.13.5", now, fake_fetch)
    assert age == pytest.approx(10.0, abs=0.1)


def test_release_age_days_pip_uses_the_earliest_upload_across_files():
    """A version's files (sdist, wheels) upload at slightly different times;
    the version became available at the earliest of them."""
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)

    def fake_fetch(url):
        return {
            "urls": [
                {"upload_time_iso_8601": "2026-09-09T12:00:00Z"},
                {"upload_time_iso_8601": "2026-09-09T00:00:00Z"},
                {"upload_time_iso_8601": "2026-09-09T18:00:00Z"},
            ]
        }

    age = dc.release_age_days("pip", "pydantic", "2.13.5", now, fake_fetch)
    assert age == pytest.approx(10.0, abs=0.1)


def test_release_age_days_computes_from_npm_time_map():
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)

    def fake_fetch(url):
        assert url == "https://registry.npmjs.org/vitest"
        return {"time": {"5.0.0": "2026-09-14T00:00:00Z"}}

    age = dc.release_age_days("npm", "vitest", "5.0.0", now, fake_fetch)
    assert age == pytest.approx(5.0, abs=0.1)


def test_release_age_days_returns_none_on_fetch_failure():
    def boom(url):
        raise OSError("network down")

    assert (
        dc.release_age_days("pip", "x", "1.0.0", datetime.now(timezone.utc), boom)
        is None
    )


def test_release_age_days_returns_none_when_pip_urls_are_empty():
    assert (
        dc.release_age_days(
            "pip", "x", "1.0.0", datetime.now(timezone.utc), lambda u: {"urls": []}
        )
        is None
    )


def test_release_age_days_returns_none_when_npm_version_is_missing():
    assert (
        dc.release_age_days(
            "npm",
            "x",
            "9.9.9",
            datetime.now(timezone.utc),
            lambda u: {"time": {}},
        )
        is None
    )


def test_release_age_days_returns_none_on_malformed_timestamp():
    assert (
        dc.release_age_days(
            "pip",
            "x",
            "1.0.0",
            datetime.now(timezone.utc),
            lambda u: {"urls": [{"upload_time_iso_8601": "not-a-timestamp"}]},
        )
        is None
    )


@pytest.mark.parametrize("ecosystem", ["docker", "github-actions", "unknown"])
def test_release_age_days_unresolvable_ecosystems_return_none(ecosystem):
    assert (
        dc.release_age_days(
            ecosystem, "x", "1", datetime.now(timezone.utc), lambda u: {}
        )
        is None
    )


def test_release_age_days_returns_none_for_empty_package_or_version():
    now = datetime.now(timezone.utc)
    assert dc.release_age_days("pip", "", "1.0.0", now, lambda u: {}) is None
    assert dc.release_age_days("pip", "x", "", now, lambda u: {}) is None


def test_release_age_days_strips_requirement_specifier_operators():
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)

    def fake_fetch(url):
        assert url == "https://pypi.org/pypi/pydantic/2.13.5/json"
        return {"urls": [{"upload_time_iso_8601": "2026-09-09T00:00:00Z"}]}

    age = dc.release_age_days("pip", "pydantic", ">=2.13.5", now, fake_fetch)
    assert age == pytest.approx(10.0, abs=0.1)


def test_release_age_days_returns_none_on_naive_timestamp():
    """A parseable timestamp with no offset must not escape as a TypeError."""
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)

    def naive(url):
        return {"urls": [{"upload_time_iso_8601": "2026-09-09T00:00:00"}]}

    assert dc.release_age_days("pip", "x", "1.0.0", now, naive) is None


def test_release_age_days_strips_a_leading_v_prefix():
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)
    seen = []

    def fetch(url):
        seen.append(url)
        return {"urls": [{"upload_time_iso_8601": "2026-09-16T00:00:00Z"}]}

    age = dc.release_age_days("pip", "foo", "v7.0.1", now, fetch)
    assert age == pytest.approx(3.0, abs=0.1)
    assert "/foo/7.0.1/" in seen[0]


def test_release_age_days_escapes_package_name_in_url():
    """A package name containing '/', '?' or '#' must not reach an
    unintended same-host path -- the host is fixed, so this guards the
    path only, not SSRF."""
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)
    seen = []

    def fetch(url):
        seen.append(url)
        return {"urls": [{"upload_time_iso_8601": "2026-09-16T00:00:00Z"}]}

    dc.release_age_days("pip", "../etc/passwd?x=1", "1.0.0", now, fetch)
    assert seen[0] == "https://pypi.org/pypi/..%2Fetc%2Fpasswd%3Fx%3D1/1.0.0/json"


def test_release_age_days_escapes_package_name_for_npm_url():
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)
    seen = []

    def fetch(url):
        seen.append(url)
        return {"time": {"1.0.0": "2026-09-16T00:00:00Z"}}

    dc.release_age_days("npm", "@scope/name#frag", "1.0.0", now, fetch)
    assert seen[0] == "https://registry.npmjs.org/%40scope%2Fname%23frag"


def test_release_age_days_non_str_version_does_not_raise():
    """A future caller passing a non-str, non-None version must not escape
    the guard that this function never raises -- the cleaning step runs
    inside the same try/except as everything else."""
    now = datetime.now(timezone.utc)
    assert dc.release_age_days("pip", "x", 123, now, lambda u: {}) is None  # type: ignore[arg-type]


def test_release_age_days_strips_range_operators():
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)
    seen = []

    def fetch(url):
        seen.append(url)
        return {"urls": [{"upload_time_iso_8601": "2026-09-16T00:00:00Z"}]}

    dc.release_age_days("pip", "foo", ">=2.13.5", now, fetch)
    dc.release_age_days("pip", "foo", "^4.1.11", now, fetch)
    assert "/foo/2.13.5/" in seen[0]
    assert "/foo/4.1.11/" in seen[1]


def test_risk_tiers_extracts_the_first_backticked_token_from_an_annotated_cell(
    tmp_path,
):
    """A register row whose name cell carries an annotation, e.g.
    "`image-size` (via `pptxgenjs`)", must resolve to the package the
    backticks name first -- not the whole cell text with backticks stripped,
    which produces a key like 'image-size` (via `pptxgenjs' that never
    matches a real package."""
    register = tmp_path / "register.md"
    register.write_text(
        "| Package | Scope | Tier | Notes |\n"
        "|---|---|---|---|\n"
        "| `image-size` (via `pptxgenjs`) | Frontend | **At-Risk** | narrow |\n"
        "| `gremlinpython` | Python | **At-Risk** | tied to Neptune |\n"
        "| `pptxgenjs` | Frontend | **Watch** | niche |\n",
        encoding="utf-8",
    )
    tiers = dc._risk_tiers(register)
    assert tiers["image-size"] == "at-risk"
    assert tiers["gremlinpython"] == "at-risk"
    assert tiers["pptxgenjs"] == "watch"


def test_gh_json_wraps_called_process_error_with_command_and_stderr(monkeypatch):
    """A raw CalledProcessError traceback on auth failure or rate limiting is
    not actionable; the wrapped RuntimeError must name the command and carry
    stderr. The failure itself must still propagate, not be swallowed."""

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=4, cmd=cmd, output="", stderr="gh: authentication required"
        )

    monkeypatch.setattr(dc.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError) as exc_info:
        dc._gh_json(["pr", "list", "--repo", "org/repo"])
    message = str(exc_info.value)
    assert "gh pr list --repo org/repo" in message
    assert "authentication required" in message


def test_gh_json_returns_parsed_output_on_success(monkeypatch):
    class FakeResult:
        stdout = '{"ok": true}'

    monkeypatch.setattr(dc.subprocess, "run", lambda cmd, **kwargs: FakeResult())
    assert dc._gh_json(["pr", "list"]) == {"ok": True}


@pytest.mark.parametrize(
    "bucket,expected",
    [
        ("pass", ("completed", "success")),
        ("fail", ("completed", "failure")),
        ("skipping", ("completed", "skipped")),
        ("cancel", ("completed", "cancelled")),
        ("pending", ("in_progress", None)),
    ],
)
def test_check_state_maps_every_gh_bucket(bucket, expected):
    """gh maintains exactly these five buckets over an open `state` vocabulary."""
    assert dc.check_state(bucket, "IRRELEVANT") == expected


@pytest.mark.parametrize(
    "state",
    [
        "CANCELLED",
        "TIMED_OUT",
        "ACTION_REQUIRED",
        "STARTUP_FAILURE",
        "NEUTRAL",
        "STALE",
        "ERROR",
        "PENDING",
        "IN_PROGRESS",
        "A_STATE_GITHUB_HAS_NOT_INVENTED_YET",
    ],
)
def test_check_state_never_reads_an_unmapped_bucket_as_success(state):
    """The mapping keys on bucket precisely so `state` cannot decide anything.

    Previously only SUCCESS/FAILURE/SKIPPED were handled and every other state
    fell through to a null conclusion, which the classifier could not
    distinguish from green."""
    status, conclusion = dc.check_state("", state)
    assert (status, conclusion) == ("completed", None)
    assert conclusion != "success"


def _fake_gh(prs, checks):
    """Build a _gh_json stand-in over a canned listing and check map."""

    def fake_gh_json(args):
        if args[:2] == ["pr", "list"]:
            return prs
        if args[:2] == ["pr", "checks"]:
            result = checks[int(args[2])]
            if isinstance(result, Exception):
                raise result
            return result
        raise AssertionError(f"unexpected gh call: {args}")

    return fake_gh_json


def test_main_maps_check_buckets_rather_than_states(tmp_path, monkeypatch):
    """main() must not hardcode every check's status to 'completed'."""
    monkeypatch.setattr(
        dc,
        "_gh_json",
        _fake_gh(
            [
                {
                    "number": 1,
                    "title": "chore: release 1.0.0",
                    "author": GH_DEPENDABOT,
                    "files": [],
                }
            ],
            {
                1: [
                    {"name": "Build", "bucket": "pending", "state": "PENDING"},
                    {"name": "Lint", "bucket": "pending", "state": "IN_PROGRESS"},
                    {"name": "Tests", "bucket": "pass", "state": "SUCCESS"},
                    {"name": "Old", "bucket": "cancel", "state": "CANCELLED"},
                    {"name": "Cond", "bucket": "skipping", "state": "NEUTRAL"},
                ]
            },
        ),
    )
    out = tmp_path / "snap.json"
    assert dc.main(["--output", str(out), "--repo", "org/repo"]) == 0
    snapshot = json.loads(out.read_text(encoding="utf-8"))
    by_name = {c["name"]: c for c in snapshot["pull_requests"][0]["checks"]}
    assert by_name["Build"]["status"] == "in_progress"
    assert by_name["Lint"]["status"] == "in_progress"
    assert by_name["Tests"] == {
        "name": "Tests",
        "status": "completed",
        "conclusion": "success",
        "failing_log_excerpt": "",
    }
    assert by_name["Old"]["conclusion"] == "cancelled"
    assert by_name["Cond"]["conclusion"] == "skipped"


def test_main_treats_a_pr_with_no_checks_as_having_no_checks(tmp_path, monkeypatch):
    """`gh pr checks` exits non-zero when a PR has no checks at all.

    With --json, gh's exporter writes and returns *before* its pending/failure
    exit-code logic, so a PR with FAILURE or pending checks exits 0. Only the
    zero-checks case exits non-zero, because that error is raised before the
    exporter runs. main() had no guard, so the first scheduled run died at
    Collect snapshot -- deterministically, since an open release PR with no
    checks is the ordinary state of this repository. rule_no_checks exists to
    classify exactly this, and could never be reached in production."""
    monkeypatch.setattr(
        dc,
        "_gh_json",
        _fake_gh(
            [
                {
                    "number": 386,
                    "title": "chore: release 1.8.0",
                    "author": {"login": "app/github-actions", "is_bot": True},
                    "files": [{"path": "CHANGELOG.md"}],
                },
                {
                    "number": 1,
                    "title": "chore(deps): bump six from 1.0.0 to 1.1.0",
                    "author": GH_DEPENDABOT,
                    "files": [{"path": "requirements.txt"}],
                },
            ],
            {
                386: RuntimeError(
                    "command failed: 'gh pr checks 386' (exit 1): no checks "
                    "reported on the 'release-please--branches--main' branch"
                ),
                1: [{"name": "Tests", "bucket": "pass", "state": "SUCCESS"}],
            },
        ),
    )
    out = tmp_path / "snap.json"
    assert dc.main(["--output", str(out), "--repo", "org/repo"]) == 0
    by_number = {
        p["number"]: p
        for p in json.loads(out.read_text(encoding="utf-8"))["pull_requests"]
    }
    assert by_number[386]["checks"] == []
    # The run must continue past the zero-check PR, not stop at it.
    assert len(by_number[1]["checks"]) == 1


def test_main_still_aborts_on_any_other_gh_failure(tmp_path, monkeypatch):
    """A real gh outage must fail loudly, per this module's error policy.

    A partial snapshot is a silently incomplete security report: the PRs gh
    failed on would simply be absent from the triage, with nothing saying so."""
    monkeypatch.setattr(
        dc,
        "_gh_json",
        _fake_gh(
            [
                {
                    "number": 1,
                    "title": "chore(deps): bump six from 1.0.0 to 1.1.0",
                    "author": GH_DEPENDABOT,
                    "files": [{"path": "requirements.txt"}],
                }
            ],
            {
                1: RuntimeError(
                    "command failed: 'gh pr checks 1' (exit 4): API rate "
                    "limit exceeded"
                )
            },
        ),
    )
    with pytest.raises(RuntimeError, match="rate limit"):
        dc.main(["--output", str(tmp_path / "snap.json"), "--repo", "org/repo"])


def test_main_no_longer_requests_the_pr_body(tmp_path, monkeypatch):
    """`body` was fetched solely for the removed advisory detector.

    Dependabot bodies embed entire upstream changelogs, so this is a real cost
    on a 20-PR listing, and the field is now unread."""
    seen = []

    def fake_gh_json(args):
        seen.append(args)
        return [] if args[:2] == ["pr", "list"] else []

    monkeypatch.setattr(dc, "_gh_json", fake_gh_json)
    assert dc.main(["--output", str(tmp_path / "s.json"), "--repo", "org/repo"]) == 0
    listing_args = next(a for a in seen if a[:2] == ["pr", "list"])
    assert "body" not in listing_args[listing_args.index("--json") + 1]


def test_record_writes_the_raw_gh_payloads_verbatim(tmp_path, monkeypatch):
    """--record is the capture primitive the fixture is built from.

    It must not transform anything: the value of a capture over a transcription
    is precisely that it can contain shapes nobody thought to write down."""
    listing = [
        {
            "number": 1,
            "title": "chore(deps): bump six from 1.0.0 to 1.1.0",
            "author": GH_DEPENDABOT,
            "files": [{"path": "requirements.txt"}],
        },
        {
            "number": 2,
            "title": "chore: release 1.0.0",
            "author": {"login": "app/github-actions", "is_bot": True},
            "files": [{"path": "CHANGELOG.md"}],
        },
    ]
    runs = [{"name": "Tests", "bucket": "pass", "state": "SUCCESS", "description": ""}]
    monkeypatch.setattr(
        dc,
        "_gh_json",
        _fake_gh(
            listing,
            {1: runs, 2: RuntimeError("exit 1: no checks reported on the branch")},
        ),
    )
    record = tmp_path / "raw.json"
    rc = dc.main(
        [
            "--output",
            str(tmp_path / "snap.json"),
            "--repo",
            "org/repo",
            "--record",
            str(record),
        ]
    )
    assert rc == 0
    raw = json.loads(record.read_text(encoding="utf-8"))
    assert raw["repo"] == "org/repo"
    assert raw["pr_list"] == listing
    assert raw["pr_checks"]["1"] == runs
    # The zero-checks case is recorded as an error marker, not as an empty list:
    # "gh refused" and "gh returned nothing" are different facts.
    assert "no checks reported" in raw["pr_checks"]["2"]["error"]


def _snapshot_from_raw(raw, committed):
    """Rebuild the snapshot document from the raw capture.

    ``release_ages`` and ``risk_tiers`` are read back out of the committed
    snapshot rather than recomputed: they come from PyPI, the npm registry and
    the risk register, none of which are gh output and none of which are
    reachable from a captured file. Every field that *is* derivable from the
    capture -- author, author_is_bot, checks, ecosystem, directory, package,
    versions -- is rebuilt, and those are exactly the fields the defects lived
    in.
    """
    by_number = {p["number"]: p for p in committed["pull_requests"]}
    prs = []
    checks_by_pr = {}
    release_ages = {}
    risk_tiers = {}
    for item in raw["pr_list"]:
        number = item["number"]
        prs.append(
            {
                "number": number,
                "title": item["title"],
                "author": item["author"],
                "files": [f["path"] for f in item.get("files", [])],
            }
        )
        recorded = raw["pr_checks"][str(number)]
        runs = [] if isinstance(recorded, dict) else recorded
        mapped = []
        for run in runs:
            status, conclusion = dc.check_state(
                run.get("bucket", ""), run.get("state", "")
            )
            mapped.append(
                {
                    "name": run["name"],
                    "status": status,
                    "conclusion": conclusion,
                    "failing_log_excerpt": run.get("description", ""),
                }
            )
        checks_by_pr[number] = mapped
        row = by_number[number]
        release_ages[(row["ecosystem"], row["package"])] = row["release_age_days"]
        if row["risk_tier"] != "unknown":
            risk_tiers[row["package"]] = row["risk_tier"]
    required = by_number[raw["pr_list"][0]["number"]]["required_checks"]
    return dc.build_snapshot(
        prs=prs,
        checks_by_pr=checks_by_pr,
        required_checks=required,
        release_ages=release_ages,
        risk_tiers=risk_tiers,
    )


def test_snapshot_fixture_is_derived_from_the_raw_capture():
    """The committed snapshot must be what build_snapshot makes of the capture.

    The previous fixture was hand-authored, and encoded three things the real
    tool never produces: the author login `dependabot[bot]`, a zero-checks PR
    the collector could not reach, and a version that had since moved on. This
    test is the reason those cannot recur -- edit either file alone and it
    fails."""
    raw = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))
    committed = json.loads(SNAPSHOT_FIXTURE.read_text(encoding="utf-8"))
    rebuilt = _snapshot_from_raw(raw, committed)
    # generated_at is a wall clock reading, not derived from anything.
    assert rebuilt["pull_requests"] == committed["pull_requests"]


def test_raw_capture_holds_the_regression_cases_the_fixture_exists_for():
    """A capture that lost these PRs would make several tests vacuously pass."""
    raw = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))
    authors = {item["author"]["login"] for item in raw["pr_list"]}
    assert "app/dependabot" in authors
    assert "app/github-actions" in authors
    # A PR gh refuses to report checks for, recorded as an error marker.
    assert any(
        isinstance(v, dict) and "no checks reported" in v.get("error", "")
        for v in raw["pr_checks"].values()
    )
    titles = " ".join(item["title"] for item in raw["pr_list"])
    assert titles.count("github/codeql-action/") == 4
    assert "vitest" in titles
