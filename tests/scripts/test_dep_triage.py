"""Tests for the Dependabot triage classifier."""

import json
from pathlib import Path

import pytest

from scripts.security import dep_triage as dt

FIXTURE = Path("tests/fixtures/dep_triage/batch_2026_09_19.json")


def test_load_snapshot_reads_all_prs():
    prs = dt.load_snapshot(FIXTURE)
    assert len(prs) == 7
    assert {p.number for p in prs} == {386, 439, 442, 443, 446, 450, 452}


def test_load_snapshot_parses_checks_and_metadata():
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    pr = prs[443]
    assert pr.author == "dependabot[bot]"
    assert pr.ecosystem == "npm"
    assert pr.directory == "/frontend"
    assert pr.package == "@vitest/coverage-v8"
    assert pr.from_version == "4.1.11"
    assert pr.to_version == "5.0.0"
    assert all(c.conclusion == "success" for c in pr.checks)


def test_snapshot_is_immutable():
    pr = dt.load_snapshot(FIXTURE)[0]
    with pytest.raises(Exception):
        pr.number = 1  # frozen dataclass


def _pr(**kw):
    """Build a PRSnapshot with harmless defaults, overridden by kwargs."""
    base = dict(
        number=1,
        title="t",
        author=dt.DEPENDABOT_AUTHOR,
        files=(),
        checks=(dt.CheckRun("Python Quality & Tests", "completed", "success"),),
        required_checks=("Python Quality & Tests",),
        ecosystem="pip",
        directory="/",
        package="x",
        from_version="1.0.0",
        to_version="1.0.1",
        release_age_days=30.0,
        risk_tier="healthy",
    )
    base.update(kw)
    return dt.PRSnapshot(**base)


def test_release_please_pr_excluded_by_author():
    pr = _pr(number=386, author="app/github-actions")
    d = dt.rule_non_dependabot(pr)
    assert d is not None
    assert d.code == dt.CODE_NON_DEPENDABOT
    assert "dependabot" in d.reason.lower()


def test_dependabot_pr_not_excluded_by_author():
    assert dt.rule_non_dependabot(_pr()) is None


def test_zero_checks_excluded():
    pr = _pr(number=386, checks=())
    d = dt.rule_no_checks(pr)
    assert d is not None
    assert d.code == dt.CODE_NO_CHECKS


def test_pr_with_checks_not_excluded_by_no_checks():
    assert dt.rule_no_checks(_pr()) is None


def test_dockerfile_change_held_for_policy_review():
    pr = _pr(files=("deploy/docker/api/Dockerfile",), ecosystem="docker")
    d = dt.rule_policy_path(pr)
    assert d is not None
    assert d.code == dt.CODE_POLICY_REVIEW
    assert "ECR" in d.reason or "base image" in d.reason


def test_coverage_threshold_file_held_for_policy_review():
    d = dt.rule_policy_path(_pr(files=("pyproject.toml",)))
    assert d is not None
    assert d.code == dt.CODE_POLICY_REVIEW


def test_requirements_change_not_policy_held():
    assert dt.rule_policy_path(_pr(files=("requirements.txt",))) is None


def test_tree_sitter_is_pinned_by_policy():
    pr = _pr(package="tree-sitter", from_version="0.25.2", to_version="0.26.0")
    d = dt.rule_held_package(pr)
    assert d is not None
    assert d.code == dt.CODE_PINNED_BY_POLICY
    assert "timeout_micros" in d.reason or "DoS" in d.reason


def test_at_risk_tier_is_held():
    d = dt.rule_held_package(_pr(package="gremlinpython", risk_tier="at-risk"))
    assert d is not None
    assert d.code == dt.CODE_RISK_TIER


def test_healthy_tier_not_held():
    assert dt.rule_held_package(_pr(package="pydantic")) is None
