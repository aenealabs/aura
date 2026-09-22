"""Tests for the Dependabot triage classifier."""

import json
from dataclasses import fields
from pathlib import Path

import pytest

from scripts.security import dep_triage as dt
from scripts.security import dep_triage_collect as dc

# Derived from tests/fixtures/dep_triage/raw_2026_09_19.json, a verbatim capture
# of `gh pr list` and `gh pr checks` against aenealabs/aura. Never hand-edit it:
# test_snapshot_fixture_is_derived_from_the_raw_capture regenerates it through
# build_snapshot and fails if the two drift. A transcribed fixture is what let an
# author-login mismatch and an unreachable zero-checks path pass a green suite.
FIXTURE = Path("tests/fixtures/dep_triage/batch_2026_09_19.json")

# The captured batch. Numbers are pinned so a silently shrunken fixture -- the
# failure mode where a regression "passes" because the PR that proved it is gone
# -- fails loudly rather than quietly.
CAPTURED_NUMBERS = {
    386,
    455,
    456,
    457,
    458,
    459,
    460,
    461,
    462,
    463,
    464,
    465,
    466,
    467,
    468,
    469,
    470,
    471,
    472,
    473,
    474,
    475,
}
CODEQL_FAMILY = (457, 459, 465, 474)
VITEST_FAMILY = (463, 464)


def test_load_snapshot_reads_all_prs():
    prs = dt.load_snapshot(FIXTURE)
    assert len(prs) == len(CAPTURED_NUMBERS)
    assert {p.number for p in prs} == CAPTURED_NUMBERS


def test_load_snapshot_parses_checks_and_metadata():
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    pr = prs[463]
    assert pr.author == "app/dependabot"
    assert pr.author_is_bot is True
    assert pr.ecosystem == "npm"
    assert pr.directory == "/frontend"
    assert pr.package == "@vitest/coverage-v8"
    assert pr.from_version == "4.1.11"
    assert pr.to_version == "5.0.1"
    assert all(c.conclusion in ("success", "skipped") for c in pr.checks)


def test_captured_authors_are_the_login_forms_gh_actually_emits():
    """The whole classifier hinged on this string and it was wrong.

    `gh` normalizes bot logins to `app/<slug>`; nothing in real output is ever
    spelled `dependabot[bot]`. Pinning the captured set means a fixture edited
    back to the API spelling fails here instead of silently excluding the queue.
    """
    authors = {p.author for p in dt.load_snapshot(FIXTURE)}
    assert "app/dependabot" in authors
    assert "dependabot[bot]" not in authors


def test_snapshot_is_immutable():
    pr = dt.load_snapshot(FIXTURE)[0]
    with pytest.raises(Exception):
        pr.number = 1  # frozen dataclass


def _pr(**kw):
    """Build a PRSnapshot with harmless defaults, overridden by kwargs."""
    base = dict(
        number=1,
        title="t",
        author="app/dependabot",
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
        author_is_bot=True,
    )
    base.update(kw)
    return dt.PRSnapshot(**base)


def test_release_please_pr_excluded_by_author():
    pr = _pr(number=386, author="app/github-actions")
    d = dt.rule_non_dependabot(pr)
    assert d is not None
    assert d.code == dt.CODE_NON_DEPENDABOT
    assert "dependabot" in d.reason.lower()


@pytest.mark.parametrize("login", sorted(dt.DEPENDABOT_AUTHORS))
def test_every_accepted_dependabot_login_form_passes_the_author_rule(login):
    """`gh` reports `app/dependabot`; the REST API and webhooks report
    `dependabot[bot]`. The collector reads whichever form its source returns, so
    an equality test against one form excludes the entire queue whenever the
    other is in play -- which is precisely what happened."""
    assert dt.rule_non_dependabot(_pr(author=login)) is None


def test_a_different_bot_is_still_excluded_despite_author_is_bot():
    """`is_bot` is recorded for the reason text, never used as the decision.

    A human cannot be Dependabot, but another bot can be `is_bot: true`, so
    trusting the flag would admit every app-authored PR in the repository."""
    decision = dt.rule_non_dependabot(_pr(author="app/github-actions"))
    assert decision is not None
    assert decision.code == dt.CODE_NON_DEPENDABOT
    assert "a bot" in decision.reason


def test_author_exclusion_reason_names_the_accepted_logins():
    """The reason is the operator's only clue when this rule misfires again."""
    decision = dt.rule_non_dependabot(_pr(author="lavrut", author_is_bot=False))
    assert decision is not None
    assert "app/dependabot" in decision.reason
    assert "not a bot" in decision.reason


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


def test_deliberate_hold_takes_precedence_over_risk_tier():
    """tree-sitter is a deliberate hold; pin the more specific reason as the
    winner over a same-package At-Risk register entry, matching current
    first-match-wins behaviour in rule_held_package."""
    pr = _pr(package="tree-sitter", risk_tier="at-risk")
    d = dt.rule_held_package(pr)
    assert d is not None
    assert d.code == dt.CODE_PINNED_BY_POLICY
    assert "timeout_micros" in d.reason or "DoS" in d.reason


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
        number=474,
        ecosystem="github-actions",
        package="github/codeql-action/upload-sarif",
    )
    b = _pr(
        number=465, ecosystem="github-actions", package="github/codeql-action/analyze"
    )
    assert dt.family_key(a) == dt.family_key(b) == "github/codeql-action"


def test_family_key_groups_vitest_peer_cluster_per_directory():
    a = _pr(number=464, ecosystem="npm", directory="/frontend", package="vitest")
    b = _pr(
        number=463,
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
        _pr(number=466, ecosystem="pip", package="hypothesis"),
        _pr(
            number=474,
            ecosystem="github-actions",
            package="github/codeql-action/upload-sarif",
        ),
        _pr(
            number=465,
            ecosystem="github-actions",
            package="github/codeql-action/analyze",
        ),
    ]
    families = dt.detect_families(prs)
    assert 466 not in families
    assert families[474] == families[465] == "github/codeql-action"


def test_green_pr_in_coupled_family_is_still_coupled():
    """#474 is fully green in the capture and still unsafe to merge alone."""
    prs = dt.load_snapshot(FIXTURE)
    families = dt.detect_families(prs)
    pr474 = next(p for p in prs if p.number == 474)
    assert all(
        c.conclusion in ("success", "skipped") for c in pr474.checks
    ), "the point of this test is a green sibling; the capture no longer has one"
    d = dt.rule_coupled(pr474, families)
    assert d is not None
    assert d.code == dt.CODE_COUPLED
    assert d.family == "github/codeql-action"


def test_all_four_codeql_refs_form_one_family():
    """The capture holds a real 4-member coupled family.

    codeql-action's sub-actions must move in lockstep or CodeQL refuses to run,
    and #465's own failing checks say so. A grouping rule that caught only two
    of the four would leave two individually mergeable."""
    families = dt.detect_families(dt.load_snapshot(FIXTURE))
    keys = {families.get(n) for n in CODEQL_FAMILY}
    assert keys == {"github/codeql-action"}


def test_vitest_pair_is_a_peer_family_in_the_capture():
    families = dt.detect_families(dt.load_snapshot(FIXTURE))
    keys = {families.get(n) for n in VITEST_FAMILY}
    assert keys == {"npm:/frontend:vitest"}


def test_uncoupled_pr_returns_none():
    prs = dt.load_snapshot(FIXTURE)
    families = dt.detect_families(prs)
    pr466 = next(p for p in prs if p.number == 466)
    assert dt.rule_coupled(pr466, families) is None


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
        _pr(number=464, ecosystem="npm", directory="/frontend", package="vitest"),
        _pr(
            number=463,
            ecosystem="npm",
            directory="/frontend",
            package="@vitest/coverage-v8",
        ),
    ]
    families = dt.detect_families(prs)
    assert families[464] == families[463] == "npm:/frontend:vitest"


def test_single_segment_action_is_not_grouped():
    """actions/checkout has no sub-action segment, so it has no family."""
    assert (
        dt.family_key(_pr(ecosystem="github-actions", package="actions/checkout"))
        is None
    )


def test_codeql_version_mismatch_is_a_real_failure_in_the_capture():
    """#465 bumps one codeql-action ref, so the other refs' Analyze jobs fail.

    Every failure is a real failure: there is no flake exemption to fall
    through to, which is the conservative direction."""
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    d = dt.rule_failing(prs[465])
    assert d is not None
    assert d.code == dt.CODE_FAILING
    assert "Analyze" in d.reason


def test_all_green_pr_has_no_failure_decision():
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    assert dt.rule_failing(prs[466]) is None


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


def test_missing_required_with_no_required_checks_returns_none():
    """An empty required-checks list has nothing to be missing."""
    assert dt.rule_missing_required(_pr(required_checks=())) is None


def test_every_failed_check_is_named_in_the_reason():
    """Both failures are reported; neither is filtered out as infrastructure."""
    pr = _pr(
        checks=(
            dt.CheckRun("Python Quality & Tests", "completed", "failure"),
            dt.CheckRun("Security Scanning", "completed", "failure"),
        )
    )
    decision = dt.rule_failing(pr)
    assert decision.code == dt.CODE_FAILING
    assert "Python Quality & Tests" in decision.reason
    assert "Security Scanning" in decision.reason


def test_no_failure_is_exempted_as_an_infrastructure_flake():
    """The flake exemption is gone, and must not come back on program output.

    The removed detector matched strings like "rate limit" against a log
    excerpt. A compromised package can print that string from its own test
    process, which would have let it relabel a genuine failure as "rerun once
    before escalating" -- evidence tampering through a signal the adversary
    controls. This pins the absence of every name that path went by.
    """
    assert not hasattr(dt, "FLAKE_SIGNATURES")
    assert not hasattr(dt, "_is_flake")
    assert not hasattr(dt, "CODE_SUSPECTED_FLAKE")
    codes = {code for _, codes in dt._SECTIONS for code in codes}
    assert not any("flake" in code for code in codes)
    assert "failing_log_excerpt" not in {f.name for f in fields(dt.CheckRun)}


# gh's complete bucket vocabulary. `state` is open-ended and GitHub keeps
# extending it; `bucket` is gh's own normalization over it, which is why the
# collector maps from the latter.
GH_BUCKETS = frozenset({"pass", "fail", "pending", "skipping", "cancel"})

# Deliberately has no default. A bucket added to GH_BUCKETS without a ruling
# here raises KeyError and fails the suite, which is the point: the defect this
# replaces was six non-passing states quietly reading as green because the
# mapping had a fall-through.
EXPECTED_FOR_REQUIRED_BUCKET = {
    "pass": dt.CODE_CANDIDATE,
    "skipping": dt.CODE_CANDIDATE,
    "fail": dt.CODE_FAILING,
    "pending": dt.CODE_REQUIRED_NOT_PASSING,
    "cancel": dt.CODE_REQUIRED_NOT_PASSING,
}


@pytest.mark.parametrize("bucket", sorted(GH_BUCKETS))
def test_every_gh_bucket_reaches_a_deliberate_classification(bucket):
    """Every state a required check can be in must be ruled on explicitly.

    Before this, only SUCCESS/FAILURE/SKIPPED were mapped and everything else
    fell to a null conclusion, so a required check that was CANCELLED,
    TIMED_OUT, ACTION_REQUIRED, STARTUP_FAILURE, NEUTRAL, STALE, ERROR or still
    running classified the PR identically to genuinely green. At 16:00 Monday,
    right after Dependabot opens its PRs, still-running is the ordinary state.
    """
    required = "Python Quality & Tests"
    status, conclusion = dc.check_state(bucket, "")
    pr = _pr(
        checks=(dt.CheckRun(required, status, conclusion),),
        required_checks=(required,),
    )
    code = dt.classify([pr])[0].code
    assert code == EXPECTED_FOR_REQUIRED_BUCKET[bucket]


def test_an_unrecognized_bucket_is_never_read_as_green():
    """GitHub extends the state vocabulary; gh may grow a bucket to match.

    An unknown bucket maps to no conclusion, and a required check with no
    conclusion is unproven -- so a future state surfaces for a human rather
    than joining the merge-safe queue."""
    required = "Python Quality & Tests"
    status, conclusion = dc.check_state("a-bucket-gh-does-not-have-yet", "")
    assert conclusion is None
    pr = _pr(
        checks=(dt.CheckRun(required, status, conclusion),),
        required_checks=(required,),
    )
    assert dt.classify([pr])[0].code == dt.CODE_REQUIRED_NOT_PASSING


def test_required_not_passing_ignores_non_required_checks():
    """An optional check that never concluded is not a reason to hold."""
    pr = _pr(
        checks=(
            dt.CheckRun("Python Quality & Tests", "completed", "success"),
            dt.CheckRun("Optional Benchmark", "in_progress", None),
        ),
        required_checks=("Python Quality & Tests",),
    )
    assert dt.rule_required_not_passing(pr) is None


def test_required_not_passing_accepts_skipped_and_neutral():
    """GitHub's own "declined to object" conclusions satisfy branch protection.

    Treating them as unproven would hold every PR whose conditional jobs were
    correctly skipped, which is the opposite failure and just as useless."""
    pr = _pr(
        checks=(
            dt.CheckRun("Python Quality & Tests", "completed", "skipped"),
            dt.CheckRun("Analyze (python)", "completed", "neutral"),
        ),
        required_checks=("Python Quality & Tests", "Analyze (python)"),
    )
    assert dt.rule_required_not_passing(pr) is None


def test_required_check_absent_is_reported_separately_from_unproven():
    """R7 and R7b are adjacent but distinct: absent is not the same as unfinished.

    Collapsing them into one code would tell an operator to look for a check
    that is in fact running."""
    absent = _pr(
        checks=(dt.CheckRun("Analyze (python)", "completed", "success"),),
        required_checks=("Analyze (python)", "Python Quality & Tests"),
    )
    assert dt.classify([absent])[0].code == dt.CODE_MISSING_REQUIRED
    unfinished = _pr(
        checks=(
            dt.CheckRun("Analyze (python)", "completed", "success"),
            dt.CheckRun("Python Quality & Tests", "in_progress", None),
        ),
        required_checks=("Analyze (python)", "Python Quality & Tests"),
    )
    assert dt.classify([unfinished])[0].code == dt.CODE_REQUIRED_NOT_PASSING


def test_required_not_passing_names_the_check_and_its_state():
    pr = _pr(
        checks=(dt.CheckRun("Python Quality & Tests", "in_progress", None),),
        required_checks=("Python Quality & Tests",),
    )
    decision = dt.rule_required_not_passing(pr)
    assert decision is not None
    assert "Python Quality & Tests" in decision.reason
    assert "in_progress" in decision.reason


def test_a_single_failed_check_is_a_real_failure():
    pr = _pr(checks=(dt.CheckRun("Python Quality & Tests", "completed", "failure"),))
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


def test_cooldown_boundary_exactly_at_limit_is_not_held():
    """The comparison is a strict less-than, so a release aged exactly the
    cooldown limit has cleared it -- this pins the boundary deliberately
    rather than leaving it to accident."""
    pr = _pr(ecosystem="pip", release_age_days=float(dt.PACKAGE_COOLDOWN_DAYS))
    assert dt.rule_cooldown(pr) is None


def test_unknown_release_age_is_held():
    d = dt.rule_cooldown(_pr(release_age_days=None))
    assert d is not None
    assert d.code == dt.CODE_COOLDOWN


def test_no_rule_can_bypass_the_cooldown_or_the_major_hold():
    """The removed security fast path stripped both guards on body text alone.

    `release_age_days` is None for every ecosystem with no stdlib-reachable
    release timestamp -- docker and github-actions always, pip and npm on any
    lookup failure -- and that is only safe because rule_cooldown holds on
    unknown. A bypass evaluated before that check turned a permanent hold into
    a candidate, which is the one outcome the design forbids."""
    assert not hasattr(dt.PRSnapshot, "security_advisory")
    assert dt.rule_cooldown(_pr(release_age_days=None)) is not None
    assert dt.rule_cooldown(_pr(ecosystem="pip", release_age_days=0.5)) is not None
    assert dt.rule_major(_pr(from_version="4.1.11", to_version="5.0.0")) is not None


def test_author_is_bot_defaults_to_false_for_older_snapshots(tmp_path):
    """A snapshot written before the field existed must still load."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for item in payload["pull_requests"]:
        item.pop("author_is_bot", None)
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert all(p.author_is_bot is False for p in dt.load_snapshot(path))


def test_classify_covers_every_pr_exactly_once():
    prs = dt.load_snapshot(FIXTURE)
    decisions = dt.classify(prs)
    assert len(decisions) == len(prs)
    assert {d.number for d in decisions} == {p.number for p in prs}


def test_classify_assigns_expected_codes_for_the_captured_batch():
    """Regression lock on the captured batch.

    Before the author fix every one of these was excluded:non-dependabot on the
    first rule, so no other rule ever ran and the queue reported empty."""
    by_number = {d.number: d for d in dt.classify(dt.load_snapshot(FIXTURE))}
    assert by_number[386].code == dt.CODE_NON_DEPENDABOT  # release PR, no checks
    assert by_number[455].code == dt.CODE_NON_DEPENDABOT  # human
    assert by_number[456].code == dt.CODE_NON_DEPENDABOT  # human
    assert by_number[474].code == dt.CODE_COUPLED  # green but coupled
    assert by_number[465].code == dt.CODE_COUPLED  # coupling precedes failure
    assert by_number[457].code == dt.CODE_COUPLED
    assert by_number[459].code == dt.CODE_COUPLED
    assert by_number[464].code == dt.CODE_COUPLED  # peer-coupled
    assert by_number[463].code == dt.CODE_COUPLED  # peer-coupled
    assert by_number[461].code == dt.CODE_MAJOR  # mermaid 11 -> 12
    assert by_number[472].code == dt.CODE_MAJOR  # openai 2 -> 3
    assert by_number[462].code == dt.CODE_POLICY_REVIEW  # touches pyproject.toml
    assert by_number[468].code == dt.CODE_RISK_TIER  # gremlinpython is At-Risk
    assert by_number[458].code == dt.CODE_COOLDOWN  # action, age unresolvable
    assert by_number[466].code == dt.CODE_CANDIDATE
    assert by_number[467].code == dt.CODE_CANDIDATE


def test_no_dependabot_pr_is_excluded_as_non_dependabot():
    """The defect in one assertion: the queue classified as empty.

    Every `app/dependabot` PR must reach a rule that actually examines it."""
    prs = dt.load_snapshot(FIXTURE)
    dependabot = {p.number for p in prs if p.author in dt.DEPENDABOT_AUTHORS}
    assert dependabot, "the capture holds no Dependabot PRs to prove anything with"
    excluded = {
        d.number
        for d in dt.classify(prs)
        if d.code == dt.CODE_NON_DEPENDABOT and d.number in dependabot
    }
    assert excluded == set()


def test_coupling_is_evaluated_before_check_results():
    """#465's required checks fail and it is still reported as coupled.

    The order is load-bearing in the other direction too: a *green* sibling is
    the dangerous case, because it looks individually mergeable."""
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    assert dt.rule_failing(prs[465]) is not None
    by_number = {d.number: d for d in dt.classify(list(prs.values()))}
    assert by_number[465].code == dt.CODE_COUPLED


def test_release_pr_with_zero_checks_is_excluded_on_both_counts():
    """#386 is a release PR gh reports no checks for at all.

    The author rule wins in classify(), but the check-presence rule must also
    fire on its own -- that path only became reachable once the collector
    stopped aborting on the non-zero exit gh returns for a PR with no checks."""
    pr386 = next(p for p in dt.load_snapshot(FIXTURE) if p.number == 386)
    assert pr386.checks == ()
    assert dt.rule_non_dependabot(pr386) is not None
    no_checks = dt.rule_no_checks(pr386)
    assert no_checks is not None
    assert no_checks.code == dt.CODE_NO_CHECKS


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
    promoted = {d.number: d for d in dt.promote(decisions, proved=[466, 467])}
    assert promoted[466].code == dt.CODE_MERGE_SAFE
    assert promoted[467].code == dt.CODE_MERGE_SAFE
    assert "batch proof" in promoted[466].reason.lower()


def test_promote_marks_conflicted_candidates_attention():
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    promoted = {
        d.number: d for d in dt.promote(decisions, proved=[467], conflicted=[466])
    }
    assert promoted[466].code == dt.CODE_CONFLICT
    assert promoted[467].code == dt.CODE_MERGE_SAFE


def test_promote_never_upgrades_a_non_candidate():
    """A coupled or excluded PR must not become merge-safe by promotion."""
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    promoted = {d.number: d for d in dt.promote(decisions, proved=[386, 474, 468])}
    assert promoted[386].code == dt.CODE_NON_DEPENDABOT
    assert promoted[474].code == dt.CODE_COUPLED
    assert promoted[468].code == dt.CODE_RISK_TIER


def test_promote_leaves_unproved_candidates_as_candidates():
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    promoted = {d.number: d for d in dt.promote(decisions, proved=[])}
    assert promoted[466].code == dt.CODE_CANDIDATE


def test_conflict_wins_when_a_pr_is_both_proved_and_conflicted():
    """The worst possible wrong answer is reporting a conflict as merge-safe."""
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    promoted = {
        d.number: d for d in dt.promote(decisions, proved=[466], conflicted=[466])
    }
    assert promoted[466].code == dt.CODE_CONFLICT


def test_promote_does_not_mutate_its_input():
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    before = [(d.number, d.code) for d in decisions]
    dt.promote(decisions, proved=[466, 467], conflicted=[])
    after = [(d.number, d.code) for d in decisions]
    assert before == after


def test_render_report_groups_by_classification():
    prs = dt.load_snapshot(FIXTURE)
    md = dt.render_report(dt.classify(prs), prs)
    assert md.startswith("# Dependabot Triage --")
    for heading in (
        "## Merge-safe",
        "## Coupled sets",
        "## Held",
        "## Needs attention",
        "## Excluded",
    ):
        assert heading in md


def test_every_verdict_is_rendered_beside_the_commit_it_was_computed_against():
    """A verdict with no head SHA cannot be checked against what gets merged.

    Dependabot force-pushes its branches on rebase, so the batch proof can
    prove commit X, the report can say merge-safe, and the operator can merge
    commit Y. Naming the head in the report is what closes that window on the
    human side; the workflow's SHA re-check closes it on the machine side."""
    prs = dt.load_snapshot(FIXTURE)
    md = dt.render_report(dt.classify(prs), prs)
    assert "| PR | Head | Code | Title | Reason |" in md
    for pr in prs:
        assert pr.head_sha, f"#{pr.number} carries no head SHA"
        assert f"`{pr.head_sha[:10]}`" in md


def test_a_snapshot_without_head_shas_renders_unknown_rather_than_blank():
    """An older snapshot must read as unverifiable, not as verified."""
    pr = _pr(number=99, head_sha="")
    md = dt.render_report(dt.classify([pr]), [pr])
    assert "(unknown)" in md


def test_report_header_echoes_the_control_inputs_it_classified_against():
    """A wrong control input otherwise produces a confident, wrong report.

    Both inputs fail quietly: a moved register parses to no tiers and a
    changed title format parses to no package, and in either case no hold
    fires and every verdict still reads as authoritative."""
    prs = dt.load_snapshot(FIXTURE)
    controls = dt.load_controls(FIXTURE)
    md = dt.render_report(dt.classify(prs), prs, controls=controls)
    header = md.split("## Control inputs", 1)[1].split("## ", 1)[0]
    assert "DEPENDENCY_RISK_REGISTER.md" in header
    assert f"{len(controls['risk_register_tiers'])} package tier(s) parsed" in header
    # The held tiers are named, not just counted: a count cannot tell an
    # operator whether the package they care about is among them.
    assert "`gremlinpython` (at-risk)" in header
    attempted = sum(1 for p in prs if p.author in dt.DEPENDABOT_AUTHORS)
    assert f"of {attempted} Dependabot title(s) parsed" in header


def test_report_header_says_so_when_no_register_tiers_were_recorded():
    """A snapshot with no controls block must not read as a clean register."""
    pr = _pr(number=99)
    md = dt.render_report(dt.classify([pr]), [pr], controls=None)
    header = md.split("## Control inputs", 1)[1].split("## ", 1)[0]
    assert "no tiers recorded" in header
    assert "unverified against the register" in header


def test_report_header_names_every_unparsed_dependabot_title():
    """An unparsed title carries no package, so its holds cannot fire.

    Counting them is not enough -- the operator needs the PR numbers to judge
    whether the tool has stopped understanding a whole title shape."""
    parsed = _pr(number=1, package="six")
    unparsed = _pr(number=2, package="", title="chore(deps): bump something odd")
    prs = [parsed, unparsed]
    md = dt.render_report(dt.classify(prs), prs)
    header = md.split("## Control inputs", 1)[1].split("## ", 1)[0]
    assert "1 of 2 Dependabot title(s) parsed" in header
    assert "#2" in header
    assert "#1" not in header


def test_load_controls_of_a_snapshot_without_the_block_is_empty(tmp_path):
    """A snapshot predating the controls block must still load, as {}.

    Returning {} routes to the "no tiers recorded" warning above rather than
    raising, so an old artifact can still be re-reported."""
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw.pop("controls")
    path = tmp_path / "old.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert dt.load_controls(path) == {}
    assert dt.load_controls(FIXTURE)["risk_register_tiers"]


def test_render_report_lists_family_members_together():
    prs = dt.load_snapshot(FIXTURE)
    md = dt.render_report(dt.classify(prs), prs)
    assert "github/codeql-action" in md
    for number in CODEQL_FAMILY:
        assert f"#{number}" in md


def test_render_report_lists_required_not_passing_under_needs_attention():
    """A new code that no section names would vanish from the report entirely."""
    required = "Python Quality & Tests"
    pr = _pr(
        number=99,
        checks=(dt.CheckRun(required, "in_progress", None),),
        required_checks=(required,),
    )
    md = dt.render_report(dt.classify([pr]), [pr])
    attention = md.split("## Needs attention", 1)[1].split("## ", 1)[0]
    assert dt.CODE_REQUIRED_NOT_PASSING in attention
    assert "#99" in attention


def test_render_report_states_a_reason_for_every_pr():
    prs = dt.load_snapshot(FIXTURE)
    md = dt.render_report(dt.classify(prs), prs)
    for pr in prs:
        assert f"#{pr.number}" in md


def test_main_writes_report_and_returns_zero(tmp_path):
    out = tmp_path / "report.md"
    rc = dt.main(["--snapshot", str(FIXTURE), "--output", str(out)])
    assert rc == 0
    assert out.read_text(encoding="utf-8").startswith("# Dependabot Triage --")


def test_main_writes_decisions_json_when_requested(tmp_path):
    out = tmp_path / "report.md"
    dec = tmp_path / "decisions.json"
    rc = dt.main(
        ["--snapshot", str(FIXTURE), "--output", str(out), "--decisions", str(dec)]
    )
    assert rc == 0
    payload = json.loads(dec.read_text(encoding="utf-8"))
    assert {d["number"] for d in payload["decisions"]} >= {386, 466, 474}
    # families_from_decisions (dep_triage_consolidate.py) depends on the
    # "family" key surviving serialisation here -- a field rename on either
    # side would silently kill consolidation with no test catching it.
    coupled = next(d for d in payload["decisions"] if d["number"] == 474)
    assert coupled["code"] == "coupled"
    assert coupled["family"] == "github/codeql-action"


def test_main_returns_nonzero_on_malformed_proved_json(tmp_path, capsys):
    out = tmp_path / "report.md"
    rc = dt.main(
        ["--snapshot", str(FIXTURE), "--output", str(out), "--proved", "{not json"]
    )
    assert rc != 0
    assert "--proved" in capsys.readouterr().err


def test_main_returns_nonzero_on_malformed_conflicted_json(tmp_path, capsys):
    out = tmp_path / "report.md"
    rc = dt.main(
        [
            "--snapshot",
            str(FIXTURE),
            "--output",
            str(out),
            "--conflicted",
            "{not json",
        ]
    )
    assert rc != 0
    assert "--conflicted" in capsys.readouterr().err


def test_render_report_escapes_pipes_in_titles_and_reasons():
    """An unescaped pipe would break the Markdown table row it sits in."""
    pr = _pr(number=99, title="bump foo from 1.0 | 2.0 to 3.0")
    decision = dt.Decision(
        number=99,
        code=dt.CODE_CANDIDATE,
        reason="held because a | appeared in the reason",
    )
    md = dt.render_report([decision], [pr])
    row = next(line for line in md.splitlines() if line.startswith("| #99 "))
    assert "1.0 \\| 2.0" in row
    assert "a \\| appeared" in row
    # The row must have exactly the 5 declared columns plus the leading and
    # trailing delimiters; an unescaped pipe would add cells.
    assert row.count("|") - row.count("\\|") == 6
