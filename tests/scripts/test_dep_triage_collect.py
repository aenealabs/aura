"""Tests for the Dependabot triage snapshot collector."""

import json

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
