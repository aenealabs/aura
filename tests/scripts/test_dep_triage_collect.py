"""Tests for the Dependabot triage snapshot collector."""

import json
import subprocess
from datetime import datetime, timezone

import pytest

from scripts.security import dep_triage as dt
from scripts.security import dep_triage_collect as dc


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
                "author": {"login": "dependabot[bot]"},
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
                "author": {"login": "dependabot[bot]"},
                "files": ["requirements.txt"],
            },
            {
                "number": 2,
                "title": "chore(deps-dev): bump six from 1.0.0 to 1.1.0 in /frontend",
                "author": {"login": "dependabot[bot]"},
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


@pytest.mark.parametrize(
    "body,expected",
    [
        ("Bumps cryptography from 49.0.0 to 50.0.1.", False),
        ("", False),
        (None, False),
        ("Bumps urllib3. Fixes [GHSA-1234-abcd-5678](https://x).", True),
        ("Patches CVE-2026-12345 in the transitive dependency.", True),
        ("mentions ghsa-lower-case-id", True),
    ],
)
def test_is_security_advisory(body, expected):
    assert dc.is_security_advisory(body) is expected


def test_advisory_ignores_cve_mentions_inside_release_notes():
    """Upstream changelogs cite old CVEs; that is not this PR being a fix."""
    body = (
        "Bumps [foo](https://github.com/foo/foo) from 1.0.0 to 2.0.0.\n"
        "<details>\n<summary>Release notes</summary>\n"
        "<p>2.0.0 also carried the fix for CVE-2024-11111 and GHSA-aaaa-bbbb-cccc.</p>\n"
        "</details>\n"
    )
    assert dc.is_security_advisory(body) is False


def test_advisory_detected_when_cited_in_the_preamble():
    body = (
        "Bumps [urllib3](https://github.com/urllib3/urllib3) from 2.0.0 to 2.0.7.\n"
        "This update fixes GHSA-aaaa-bbbb-cccc.\n"
        "<details>\n<summary>Release notes</summary>\n<p>unrelated</p>\n</details>\n"
    )
    assert dc.is_security_advisory(body) is True


def test_advisory_ignores_tail_after_an_unclosed_details_block():
    body = "Bumps foo from 1 to 2.\n<details>\n<summary>x</summary>\nCVE-2024-22222\n"
    assert dc.is_security_advisory(body) is False


def test_advisory_handles_multiple_details_blocks():
    body = (
        "Bumps foo from 1 to 2.\n"
        "<details><summary>Release notes</summary>CVE-2024-33333</details>\n"
        "<details><summary>Commits</summary>GHSA-dddd-eeee-ffff</details>\n"
    )
    assert dc.is_security_advisory(body) is False


def test_advisory_ignores_cve_in_a_nested_details_tail():
    """A non-greedy paired strip would leak the outer tail back into scope."""
    body = (
        "Bumps foo from 1.0.0 to 2.0.0.\n"
        "<details><summary>Notes</summary>Intro\n"
        "<details><summary>inner</summary>Inner text</details>\n"
        "CVE-2024-99999 in outer tail</details>\n"
    )
    assert dc.is_security_advisory(body) is False


def test_advisory_ignores_details_with_attributes():
    body = (
        "Bumps foo from 1.0.0 to 2.0.0.\n"
        "<details open><summary>Notes</summary>CVE-2024-88888</details>\n"
    )
    assert dc.is_security_advisory(body) is False


def test_advisory_ignores_uppercase_and_spaced_details_tags():
    body = "Bumps foo from 1 to 2.\n< DETAILS >GHSA-aaaa-bbbb-cccc</DETAILS>\n"
    assert dc.is_security_advisory(body) is False


def test_build_snapshot_carries_the_security_flag(tmp_path):
    snapshot = dc.build_snapshot(
        prs=[
            {
                "number": 1,
                "title": "chore(deps): bump urllib3 from 2.0.0 to 2.0.1",
                "author": {"login": "dependabot[bot]"},
                "files": ["requirements.txt"],
                "security_advisory": True,
            }
        ],
        checks_by_pr={
            1: [
                {
                    "name": "Analyze (python)",
                    "status": "completed",
                    "conclusion": "success",
                    "failing_log_excerpt": "",
                },
            ]
        },
        required_checks=["Analyze (python)"],
        release_ages={("pip", "urllib3"): 0.2},
        risk_tiers={},
    )
    assert snapshot["pull_requests"][0]["security_advisory"] is True
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    assert dt.load_snapshot(path)[0].security_advisory is True


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


def test_main_maps_pending_and_in_progress_check_states(tmp_path, monkeypatch):
    """main() must not hardcode every check's status to 'completed' -- a
    pending or in-progress gh state maps to 'in_progress'."""

    def fake_gh_json(args):
        if args[:2] == ["pr", "list"]:
            return [
                {
                    "number": 1,
                    "title": "chore: release 1.0.0",
                    "author": {"login": "dependabot[bot]"},
                    "files": [],
                    "body": "",
                }
            ]
        if args[:2] == ["pr", "checks"]:
            return [
                {"name": "Build", "state": "PENDING", "description": ""},
                {"name": "Lint", "state": "IN_PROGRESS", "description": ""},
                {"name": "Tests", "state": "SUCCESS", "description": ""},
            ]
        raise AssertionError(f"unexpected gh call: {args}")

    monkeypatch.setattr(dc, "_gh_json", fake_gh_json)
    out = tmp_path / "snap.json"
    rc = dc.main(["--output", str(out), "--repo", "org/repo"])
    assert rc == 0
    snapshot = json.loads(out.read_text(encoding="utf-8"))
    by_name = {c["name"]: c for c in snapshot["pull_requests"][0]["checks"]}
    assert by_name["Build"]["status"] == "in_progress"
    assert by_name["Lint"]["status"] == "in_progress"
    assert by_name["Tests"]["status"] == "completed"
