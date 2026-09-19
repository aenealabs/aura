"""Tests for the Dependabot triage snapshot collector."""

import json
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
        release_ages={"github/codeql-action/upload-sarif": 9.0},
        risk_tiers={},
    )
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    prs = dt.load_snapshot(path)
    assert len(prs) == 1
    assert prs[0].ecosystem == "github-actions"
    assert prs[0].package == "github/codeql-action/upload-sarif"


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
        release_ages={"urllib3": 0.2},
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
