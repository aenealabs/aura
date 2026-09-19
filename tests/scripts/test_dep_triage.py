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


def test_policy_path_does_not_match_substring_lookalikes():
    """A component named after Dockerfile is not a Dockerfile."""
    pr = _pr(files=("frontend/src/components/DockerfileViewer.jsx",))
    assert dt.rule_policy_path(pr) is None


def test_policy_path_matches_dockerfile_variants():
    assert (
        dt.rule_policy_path(_pr(files=("deploy/docker/api/Dockerfile.prod",)))
        is not None
    )


def test_policy_path_matches_nested_pyproject():
    assert dt.rule_policy_path(_pr(files=("tools/pyproject.toml",))) is not None


def test_family_key_groups_codeql_action_subactions():
    a = _pr(
        number=450,
        ecosystem="github-actions",
        package="github/codeql-action/upload-sarif",
    )
    b = _pr(
        number=452, ecosystem="github-actions", package="github/codeql-action/analyze"
    )
    assert dt.family_key(a) == dt.family_key(b) == "github/codeql-action"


def test_family_key_groups_vitest_peer_cluster_per_directory():
    a = _pr(number=442, ecosystem="npm", directory="/frontend", package="vitest")
    b = _pr(
        number=443,
        ecosystem="npm",
        directory="/frontend",
        package="@vitest/coverage-v8",
    )
    assert dt.family_key(a) == dt.family_key(b) == "npm:/frontend:vitest"


def test_family_key_separates_same_package_in_different_directories():
    a = _pr(ecosystem="npm", directory="/frontend", package="vitest")
    b = _pr(ecosystem="npm", directory="/sdk/typescript", package="vitest")
    assert dt.family_key(a) != dt.family_key(b)


def test_detect_families_ignores_singletons():
    prs = [
        _pr(number=439, ecosystem="pip", package="pydantic"),
        _pr(
            number=450,
            ecosystem="github-actions",
            package="github/codeql-action/upload-sarif",
        ),
        _pr(
            number=452,
            ecosystem="github-actions",
            package="github/codeql-action/analyze",
        ),
    ]
    families = dt.detect_families(prs)
    assert 439 not in families
    assert families[450] == families[452] == "github/codeql-action"


def test_green_pr_in_coupled_family_is_still_coupled():
    """#450 was fully green and still unsafe to merge alone."""
    prs = dt.load_snapshot(FIXTURE)
    families = dt.detect_families(prs)
    pr450 = next(p for p in prs if p.number == 450)
    assert all(c.conclusion == "success" for c in pr450.checks)
    d = dt.rule_coupled(pr450, families)
    assert d is not None
    assert d.code == dt.CODE_COUPLED
    assert d.family == "github/codeql-action"


def test_uncoupled_pr_returns_none():
    prs = dt.load_snapshot(FIXTURE)
    families = dt.detect_families(prs)
    pr439 = next(p for p in prs if p.number == 439)
    assert dt.rule_coupled(pr439, families) is None


def test_shared_npm_scope_alone_is_not_a_family():
    """@types/react and @types/node release independently."""
    prs = [
        _pr(number=1, ecosystem="npm", directory="/frontend", package="@types/react"),
        _pr(number=2, ecosystem="npm", directory="/frontend", package="@types/node"),
    ]
    assert dt.detect_families(prs) == {}


def test_shared_babel_scope_alone_is_not_a_family():
    prs = [
        _pr(number=1, ecosystem="npm", directory="/frontend", package="@babel/core"),
        _pr(
            number=2,
            ecosystem="npm",
            directory="/frontend",
            package="@babel/preset-env",
        ),
    ]
    assert dt.detect_families(prs) == {}


def test_scoped_package_couples_with_its_unscoped_namesake():
    prs = [
        _pr(number=442, ecosystem="npm", directory="/frontend", package="vitest"),
        _pr(
            number=443,
            ecosystem="npm",
            directory="/frontend",
            package="@vitest/coverage-v8",
        ),
    ]
    families = dt.detect_families(prs)
    assert families[442] == families[443] == "npm:/frontend:vitest"


def test_single_segment_action_is_not_grouped():
    """actions/checkout has no sub-action segment, so it has no family."""
    assert (
        dt.family_key(_pr(ecosystem="github-actions", package="actions/checkout"))
        is None
    )
