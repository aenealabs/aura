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
        security_advisory=False,
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


def test_trivy_download_failure_is_suspected_flake():
    """#442 failed because the trivy installer died, not because of a defect."""
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    d = dt.rule_failing(prs[442])
    assert d is not None
    assert d.code == dt.CODE_SUSPECTED_FLAKE
    assert "Security Scanning" in d.reason


def test_codeql_version_mismatch_is_real_failure():
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    d = dt.rule_failing(prs[452])
    assert d is not None
    assert d.code == dt.CODE_FAILING


def test_all_green_pr_has_no_failure_decision():
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    assert dt.rule_failing(prs[439]) is None


def test_timed_out_counts_as_failure():
    pr = _pr(checks=(dt.CheckRun("Python Quality & Tests", "completed", "timed_out"),))
    d = dt.rule_failing(pr)
    assert d is not None
    assert d.code == dt.CODE_FAILING


def test_missing_required_check_is_not_treated_as_pass():
    """An unrun required check is missing, not passing."""
    pr = _pr(
        checks=(dt.CheckRun("Analyze (python)", "completed", "success"),),
        required_checks=("Analyze (python)", "Python Quality & Tests"),
    )
    d = dt.rule_missing_required(pr)
    assert d is not None
    assert d.code == dt.CODE_MISSING_REQUIRED
    assert "Python Quality & Tests" in d.reason


def test_all_required_checks_present_returns_none():
    assert dt.rule_missing_required(_pr()) is None


def test_mixed_genuine_and_flake_failures_report_the_genuine_one():
    """A real failure must not be hidden behind a flake in the same PR."""
    pr = _pr(
        checks=(
            dt.CheckRun(
                "Python Quality & Tests",
                "completed",
                "failure",
                "AssertionError: expected 3, got 4",
            ),
            dt.CheckRun(
                "Security Scanning",
                "completed",
                "failure",
                "##[error]Process completed with exit code 35.",
            ),
        )
    )
    decision = dt.rule_failing(pr)
    assert decision.code == dt.CODE_FAILING
    assert "Python Quality & Tests" in decision.reason


def test_all_failures_flaky_is_still_a_flake():
    pr = _pr(
        checks=(
            dt.CheckRun(
                "Security Scanning",
                "completed",
                "failure",
                "##[error]Process completed with exit code 35.",
            ),
            dt.CheckRun(
                "Container Build",
                "completed",
                "failure",
                "Could not resolve host: registry.example",
            ),
        )
    )
    assert dt.rule_failing(pr).code == dt.CODE_SUSPECTED_FLAKE


def test_missing_path_alone_is_not_treated_as_a_flake():
    """A broken path introduced by the change is a real failure."""
    pr = _pr(
        checks=(
            dt.CheckRun(
                "Python Quality & Tests",
                "completed",
                "failure",
                "Path does not exist: src/module.py",
            ),
        )
    )
    assert dt.rule_failing(pr).code == dt.CODE_FAILING


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("5.0.0", 5),
        ("^4.1.11", 4),
        (">=2.13.5", 2),
        ("v7.0.1", 7),
        ("4.38.0", 4),
        ("", None),
        ("latest", None),
    ],
)
def test_major_of_parses_leading_integer(raw, expected):
    assert dt.major_of(raw) == expected


def test_major_bump_is_held():
    d = dt.rule_major(_pr(package="vitest", from_version="4.1.11", to_version="5.0.0"))
    assert d is not None
    assert d.code == dt.CODE_MAJOR


def test_minor_bump_is_not_major():
    assert dt.rule_major(_pr(from_version="2.12.5", to_version="2.13.5")) is None


def test_unparseable_version_is_not_major():
    assert dt.rule_major(_pr(from_version="", to_version="")) is None


def test_fresh_package_release_held_for_cooldown():
    d = dt.rule_cooldown(_pr(ecosystem="pip", release_age_days=1.0))
    assert d is not None
    assert d.code == dt.CODE_COOLDOWN


def test_aged_package_release_passes_cooldown():
    assert dt.rule_cooldown(_pr(ecosystem="pip", release_age_days=5.0)) is None


def test_action_uses_longer_cooldown():
    """Actions are SHA-pinned supply-chain surface, so they wait longer."""
    pr = _pr(ecosystem="github-actions", package="a/b/c", release_age_days=5.0)
    d = dt.rule_cooldown(pr)
    assert d is not None
    assert d.code == dt.CODE_COOLDOWN
    assert (
        dt.rule_cooldown(
            _pr(ecosystem="github-actions", package="a/b/c", release_age_days=9.0)
        )
        is None
    )


def test_unknown_release_age_is_held():
    d = dt.rule_cooldown(_pr(release_age_days=None))
    assert d is not None
    assert d.code == dt.CODE_COOLDOWN


def test_security_advisory_bypasses_cooldown():
    pr = _pr(ecosystem="pip", release_age_days=0.5, security_advisory=True)
    assert dt.rule_cooldown(pr) is None


def test_security_advisory_bypasses_unknown_release_age():
    pr = _pr(release_age_days=None, security_advisory=True)
    assert dt.rule_cooldown(pr) is None


def test_security_advisory_bypasses_major_hold():
    pr = _pr(from_version="4.1.11", to_version="5.0.0", security_advisory=True)
    assert dt.rule_major(pr) is None


def test_non_security_major_is_still_held():
    pr = _pr(from_version="4.1.11", to_version="5.0.0", security_advisory=False)
    assert dt.rule_major(pr) is not None


def test_security_advisory_does_not_bypass_policy_holds():
    """A CVE fix is still not permission to rewrite a base image unreviewed."""
    pr = _pr(files=("deploy/docker/api/Dockerfile",), security_advisory=True)
    assert dt.rule_policy_path(pr) is not None
    held = _pr(package="tree-sitter", security_advisory=True)
    assert dt.rule_held_package(held) is not None


def test_security_advisory_defaults_to_false(tmp_path):
    """Snapshots written before this field existed still load."""
    prs = dt.load_snapshot(FIXTURE)
    assert all(p.security_advisory is False for p in prs)


def test_classify_covers_every_pr_exactly_once():
    prs = dt.load_snapshot(FIXTURE)
    decisions = dt.classify(prs)
    assert len(decisions) == len(prs)
    assert {d.number for d in decisions} == {p.number for p in prs}


def test_classify_assigns_expected_codes_for_the_observed_batch():
    """Regression lock on the real 2026-09-19 batch."""
    by_number = {d.number: d for d in dt.classify(dt.load_snapshot(FIXTURE))}
    assert by_number[386].code == dt.CODE_NON_DEPENDABOT
    assert by_number[450].code == dt.CODE_COUPLED  # green but coupled
    assert by_number[452].code == dt.CODE_COUPLED  # coupling precedes failure
    assert by_number[442].code == dt.CODE_COUPLED  # coupling precedes flake
    assert by_number[443].code == dt.CODE_COUPLED  # green but peer-coupled
    assert by_number[439].code == dt.CODE_CANDIDATE
    assert by_number[446].code == dt.CODE_CANDIDATE


def test_author_exclusion_precedes_all_other_rules():
    pr = _pr(
        number=386, author="app/github-actions", checks=(), files=("pyproject.toml",)
    )
    assert dt.classify([pr])[0].code == dt.CODE_NON_DEPENDABOT


def test_every_decision_carries_a_nonempty_reason():
    for d in dt.classify(dt.load_snapshot(FIXTURE)):
        assert d.reason.strip(), f"PR #{d.number} has no reason"


def test_promote_marks_proved_candidates_merge_safe():
    prs = dt.load_snapshot(FIXTURE)
    decisions = dt.classify(prs)
    promoted = {d.number: d for d in dt.promote(decisions, proved=[439, 446])}
    assert promoted[439].code == dt.CODE_MERGE_SAFE
    assert promoted[446].code == dt.CODE_MERGE_SAFE
    assert "batch proof" in promoted[439].reason.lower()


def test_promote_marks_conflicted_candidates_attention():
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    promoted = {
        d.number: d for d in dt.promote(decisions, proved=[446], conflicted=[439])
    }
    assert promoted[439].code == dt.CODE_CONFLICT
    assert promoted[446].code == dt.CODE_MERGE_SAFE


def test_promote_never_upgrades_a_non_candidate():
    """A coupled or excluded PR must not become merge-safe by promotion."""
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    promoted = {d.number: d for d in dt.promote(decisions, proved=[386, 450, 452])}
    assert promoted[386].code == dt.CODE_NON_DEPENDABOT
    assert promoted[450].code == dt.CODE_COUPLED
    assert promoted[452].code == dt.CODE_COUPLED


def test_promote_leaves_unproved_candidates_as_candidates():
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    promoted = {d.number: d for d in dt.promote(decisions, proved=[])}
    assert promoted[439].code == dt.CODE_CANDIDATE
