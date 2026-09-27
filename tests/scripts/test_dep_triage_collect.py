"""Tests for the Dependabot triage snapshot collector.

The last two tests are the capture discipline and the reason four inert controls
were ever found: the committed snapshot fixture must be exactly what
``build_snapshot`` makes of the committed raw ``gh`` capture, so neither file can
be edited alone. See the collector's module docstring.
"""

import json
import subprocess
from pathlib import Path

import pytest

from scripts.security import dep_triage_collect as dc

RAW_FIXTURE = Path("tests/fixtures/dep_triage/raw_2026_09_19.json")
SNAPSHOT_FIXTURE = Path("tests/fixtures/dep_triage/batch_2026_09_19.json")

# The login form `gh` actually emits. Every author literal in this file uses it,
# because a test that invents `dependabot[bot]` tests a string the tool never
# sees.
GH_DEPENDABOT = {"login": "app/dependabot", "is_bot": True}


@pytest.mark.parametrize(
    "title,expected",
    [
        (
            "chore(deps): bump github/codeql-action/init from 4.37.9 to 4.38.0",
            ("github/codeql-action/init", "4.37.9", "4.38.0"),
        ),
        (
            "chore(deps): update pydantic requirement from >=2.12.5 to >=2.13.5",
            ("pydantic", ">=2.12.5", ">=2.13.5"),
        ),
        # Dependabot's own default title form, with no conventional-commit
        # prefix. This repo only sees the lowercase inferred form, so a
        # case-sensitive pattern would silently parse no title at all.
        ("Bump vitest from 4.0.16 to 5.0.0", ("vitest", "4.0.16", "5.0.0")),
        # A grouped update and a release PR both name no package, which is how
        # they fall through to `candidate` harmlessly.
        ("chore(deps): bump the minor-and-patch group with 4 updates", ("", "", "")),
    ],
)
def test_parse_bump_title(title, expected):
    assert dc.parse_bump_title(title) == expected


def test_infer_ecosystem_from_files():
    assert dc.infer_ecosystem([".github/workflows/ci.yml"]) == "github-actions"
    assert dc.infer_ecosystem(["frontend/package.json"]) == "npm"
    assert dc.infer_ecosystem(["requirements.txt"]) == "pip"
    assert dc.infer_ecosystem(["pyproject.toml"]) == "pip"
    assert dc.infer_ecosystem(["Dockerfile"]) == "docker"
    assert dc.infer_ecosystem(["README.md"]) == "unknown"


def test_infer_directory_scopes_npm_families():
    assert dc.infer_directory(["frontend/package.json"]) == "/frontend"
    assert dc.infer_directory(["package.json"]) == "/"
    assert dc.infer_directory(["requirements.txt"]) == "/"


def test_build_snapshot_emits_the_schema_load_snapshot_accepts(tmp_path):
    from scripts.security import dep_triage as dt

    snapshot = dc.build_snapshot(
        [
            {
                "number": 1,
                "title": "chore(deps-dev): bump vitest from 4.1.11 to 5.0.1",
                "author": GH_DEPENDABOT,
                "files": ["frontend/package.json"],
                "head_sha": "a" * 40,
            }
        ]
    )
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    pr = dt.load_snapshot(path)[0]
    assert pr.author == "app/dependabot"
    assert pr.author_is_bot is True
    assert pr.ecosystem == "npm"
    assert pr.directory == "/frontend"
    assert pr.package == "vitest"
    assert pr.head_sha == "a" * 40


def test_build_snapshot_tolerates_a_missing_author_block():
    snapshot = dc.build_snapshot([{"number": 1, "title": "x", "files": []}])
    assert snapshot["pull_requests"][0]["author"] == ""
    assert snapshot["pull_requests"][0]["author_is_bot"] is False


def _fake_gh(monkeypatch, listing):
    """Stub `gh pr list` with `listing`, recording the argv it was called with."""
    calls: list[list[str]] = []

    def fake(args):
        calls.append(args)
        return listing

    monkeypatch.setattr(dc, "_gh_json", fake)
    return calls


def test_a_full_pr_listing_is_treated_as_truncated(tmp_path, monkeypatch):
    """`gh pr list --limit N` truncates silently; under-reporting is worse."""
    listing = [
        {"number": n, "title": "t", "author": GH_DEPENDABOT, "files": []}
        for n in range(dc.PR_LIST_LIMIT)
    ]
    _fake_gh(monkeypatch, listing)
    with pytest.raises(RuntimeError, match="truncated"):
        dc.main(["--repo", "org/repo", "--output", str(tmp_path / "s.json")])


def test_the_listing_requests_and_records_the_head_commit(tmp_path, monkeypatch):
    listing = [
        {
            "number": 1,
            "title": "chore(deps): bump ruff from 1.0.0 to 1.0.1",
            "author": GH_DEPENDABOT,
            "files": [{"path": "requirements.txt"}],
            "headRefOid": "b" * 40,
        }
    ]
    calls = _fake_gh(monkeypatch, listing)
    out = tmp_path / "s.json"
    assert dc.main(["--repo", "org/repo", "--output", str(out)]) == 0
    assert "headRefOid" in calls[0][-1]
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["pull_requests"][0]["head_sha"] == "b" * 40


def test_record_writes_the_raw_gh_payload_verbatim(tmp_path, monkeypatch):
    """The fixture must come off the wire, never from a transcription."""
    listing = [
        {
            "number": 1,
            "title": "t",
            "author": GH_DEPENDABOT,
            "files": [],
            "headRefOid": "c" * 40,
        }
    ]
    _fake_gh(monkeypatch, listing)
    record = tmp_path / "raw.json"
    dc.main(
        [
            "--repo",
            "org/repo",
            "--output",
            str(tmp_path / "s.json"),
            "--record",
            str(record),
        ]
    )
    raw = json.loads(record.read_text(encoding="utf-8"))
    assert raw["repo"] == "org/repo"
    assert raw["pr_list"] == listing


def test_gh_json_wraps_called_process_error_with_command_and_stderr(monkeypatch):
    def boom(*a, **kw):
        raise subprocess.CalledProcessError(1, "gh", stderr="gh: rate limited")

    monkeypatch.setattr(dc.subprocess, "run", boom)
    with pytest.raises(RuntimeError) as exc:
        dc._gh_json(["pr", "list"])
    assert "gh pr list" in str(exc.value)
    assert "rate limited" in str(exc.value)


def _snapshot_from_raw(raw):
    """Rebuild the snapshot document from the raw capture.

    The capture predates the reduction and still carries ``pr_checks`` and PR
    ``body`` payloads. Nothing reads them any more; the file is left verbatim
    because trimming a capture turns it back into a transcription.
    """
    return dc.build_snapshot(
        [
            {
                "number": item["number"],
                "title": item["title"],
                "author": item["author"],
                "files": [f["path"] for f in item.get("files", [])],
                "head_sha": item.get("headRefOid", ""),
            }
            for item in raw["pr_list"]
        ]
    )


def test_snapshot_fixture_is_derived_from_the_raw_capture():
    """The committed snapshot must be what build_snapshot makes of the capture.

    An earlier fixture was hand-authored and encoded three things the real tool
    never produces: the author login `dependabot[bot]`, a zero-checks PR the
    collector could not reach, and a version that had since moved on. This test
    is why those cannot recur -- edit either file alone and it fails.
    """
    raw = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))
    committed = json.loads(SNAPSHOT_FIXTURE.read_text(encoding="utf-8"))
    rebuilt = _snapshot_from_raw(raw)
    # generated_at is a wall clock reading, not derived from anything.
    assert rebuilt["pull_requests"] == committed["pull_requests"]


def test_raw_capture_holds_the_regression_cases_the_fixture_exists_for():
    """A capture that lost these PRs would make several tests vacuously pass."""
    raw = json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))
    authors = {item["author"]["login"] for item in raw["pr_list"]}
    assert "app/dependabot" in authors
    # A non-Dependabot bot, so the author rule is not vacuous.
    assert "app/github-actions" in authors
    titles = " ".join(item["title"] for item in raw["pr_list"])
    # The two near-misses the surviving control exists for.
    assert titles.count("github/codeql-action/") == 4
    assert "@vitest/coverage-v8" in titles
    assert all(len(item["headRefOid"]) == 40 for item in raw["pr_list"])
