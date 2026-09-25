"""Tests for the Dependabot triage classifier.

Scoped to what the tool still does: exclude non-Dependabot authors, detect
coupled update families, and render a report. The suite that covered check
evaluation, the cooldown, register holds, grouped-member holds and the
``merge-safe`` promotion went with those controls; ``dep_triage``'s module
docstring records why.
"""

import json
from pathlib import Path

import pytest
import yaml

from scripts.security import dep_triage as dt

# Derived from tests/fixtures/dep_triage/raw_2026_09_19.json, a verbatim capture
# of `gh pr list` against aenealabs/aura. Never hand-edit it:
# test_snapshot_fixture_is_derived_from_the_raw_capture (in the collector's
# suite) regenerates it through build_snapshot and fails if the two drift. A
# transcribed fixture is what let an author-login mismatch pass a green suite.
FIXTURE = Path("tests/fixtures/dep_triage/batch_2026_09_19.json")

# Numbers are pinned so a silently shrunken fixture -- the failure mode where a
# regression "passes" because the PR that proved it is gone -- fails loudly.
CAPTURED_NUMBERS = set(range(455, 476)) | {386}
CODEQL_FAMILY = (457, 459, 465, 474)
VITEST_FAMILY = (463, 464)


def _pr(**kw):
    """Build a PRSnapshot with harmless defaults, overridden by kwargs."""
    base = dict(
        number=1,
        title="t",
        author="app/dependabot",
        files=(),
        ecosystem="pip",
        directory="/",
        package="x",
        from_version="1.0.0",
        to_version="1.0.1",
        author_is_bot=True,
    )
    base.update(kw)
    return dt.PRSnapshot(**base)


# --------------------------------------------------------------------------
# Snapshot loading
# --------------------------------------------------------------------------


def test_load_snapshot_parses_the_fields_coupling_is_keyed_on():
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    pr = prs[463]
    assert pr.author == "app/dependabot"
    assert pr.author_is_bot is True
    assert pr.ecosystem == "npm"
    assert pr.directory == "/frontend"
    assert pr.package == "@vitest/coverage-v8"
    assert pr.from_version == "4.1.11"
    assert pr.to_version == "5.0.1"
    assert len(pr.head_sha) == 40


def test_captured_authors_are_the_login_forms_gh_actually_emits():
    """The whole classifier hinged on this string and it was wrong.

    `gh` normalizes bot logins to `app/<slug>`; nothing in real output is ever
    spelled `dependabot[bot]`. Pinning the captured set means a fixture edited
    back to the API spelling fails here instead of silently excluding the queue.
    """
    authors = {p.author for p in dt.load_snapshot(FIXTURE)}
    assert "app/dependabot" in authors
    assert "dependabot[bot]" not in authors


# --------------------------------------------------------------------------
# R1: author exclusion
# --------------------------------------------------------------------------


@pytest.mark.parametrize("login", sorted(dt.DEPENDABOT_AUTHORS))
def test_every_accepted_dependabot_login_form_passes_the_author_rule(login):
    """`gh` returns `app/dependabot`, the REST API `dependabot[bot]`.

    An equality test against one form made the entire system a silent no-op.
    """
    assert dt.rule_non_dependabot(_pr(author=login)) is None


def test_a_different_bot_is_still_excluded_despite_author_is_bot():
    decision = dt.rule_non_dependabot(
        _pr(author="app/renovate", author_is_bot=True),
    )
    assert decision.code == dt.CODE_NON_DEPENDABOT
    assert "a bot" in decision.reason
    for login in dt.DEPENDABOT_AUTHORS:
        assert login in decision.reason


# --------------------------------------------------------------------------
# R5: coupled families
# --------------------------------------------------------------------------


def test_family_key_groups_codeql_action_subactions():
    init = _pr(
        number=1, ecosystem="github-actions", package="github/codeql-action/init"
    )
    analyze = _pr(
        number=2, ecosystem="github-actions", package="github/codeql-action/analyze"
    )
    assert dt.family_key(init) == dt.family_key(analyze) == "github/codeql-action"


def test_single_segment_action_is_not_grouped():
    pr = _pr(ecosystem="github-actions", package="actions/checkout")
    assert dt.family_key(pr) is None


def test_family_key_separates_the_same_package_in_different_directories():
    frontend = _pr(number=1, ecosystem="npm", package="vitest", directory="/frontend")
    sdk = _pr(number=2, ecosystem="npm", package="vitest", directory="/sdk/typescript")
    assert dt.family_key(frontend) != dt.family_key(sdk)


def test_detect_families_ignores_singletons():
    prs = [
        _pr(number=1, ecosystem="github-actions", package="github/codeql-action/init"),
        _pr(number=2, ecosystem="pip", package="ruff"),
    ]
    assert dt.detect_families(prs) == {}


def test_shared_npm_scope_alone_is_not_a_family():
    """@types/react and @types/node release on independent cadences.

    Keying on the bare scope grouped them, which is the defect
    ``_has_unscoped_root`` exists for.
    """
    prs = [
        _pr(number=1, ecosystem="npm", package="@types/react", directory="/frontend"),
        _pr(number=2, ecosystem="npm", package="@types/node", directory="/frontend"),
    ]
    assert dt.detect_families(prs) == {}


def test_scoped_package_couples_with_its_unscoped_namesake():
    prs = [
        _pr(
            number=1,
            ecosystem="npm",
            package="@vitest/coverage-v8",
            directory="/frontend",
        ),
        _pr(number=2, ecosystem="npm", package="vitest", directory="/frontend"),
    ]
    assert dt.detect_families(prs) == {
        1: "npm:/frontend:vitest",
        2: "npm:/frontend:vitest",
    }


def test_all_four_codeql_refs_form_one_family_in_the_capture():
    """PR #450's near-miss: four green refs, none individually mergeable."""
    families = dt.detect_families(dt.load_snapshot(FIXTURE))
    assert {n: families.get(n) for n in CODEQL_FAMILY} == {
        n: "github/codeql-action" for n in CODEQL_FAMILY
    }


def test_vitest_pair_is_a_peer_family_in_the_capture():
    """PR #443's near-miss: @vitest/coverage-v8 at 5.x, vitest at 4.x."""
    families = dt.detect_families(dt.load_snapshot(FIXTURE))
    assert {n: families.get(n) for n in VITEST_FAMILY} == {
        n: "npm:/frontend:vitest" for n in VITEST_FAMILY
    }


def test_coupling_carries_the_family_key_and_ignores_everything_else():
    """The dangerous case is a green sibling, so no other signal can clear it."""
    decision = dt.rule_coupled(_pr(number=7), {7: "github/codeql-action"})
    assert decision.code == dt.CODE_COUPLED
    assert decision.family == "github/codeql-action"
    assert dt.rule_coupled(_pr(number=7), {}) is None


# --------------------------------------------------------------------------
# classify
# --------------------------------------------------------------------------


def test_classify_emits_exactly_the_captured_codes():
    decisions = dt.classify(dt.load_snapshot(FIXTURE))
    by_number = {d.number: d for d in decisions}
    assert len(decisions) == len(CAPTURED_NUMBERS)
    assert set(by_number) == CAPTURED_NUMBERS
    # Three codes only. A fourth appearing here means a control crept back in.
    assert {d.code for d in decisions} == {
        dt.CODE_CANDIDATE,
        dt.CODE_COUPLED,
        dt.CODE_NON_DEPENDABOT,
    }
    for number in CODEQL_FAMILY:
        assert by_number[number].code == dt.CODE_COUPLED
        assert by_number[number].family == "github/codeql-action"
    for number in VITEST_FAMILY:
        assert by_number[number].code == dt.CODE_COUPLED
        assert by_number[number].family == "npm:/frontend:vitest"
    # 386 is Release Please; 455 and 456 are a human's PRs.
    assert {n for n, d in by_number.items() if d.code == dt.CODE_NON_DEPENDABOT} == {
        386,
        455,
        456,
    }


def test_no_dependabot_pr_is_excluded_as_non_dependabot():
    """The no-op regression, asserted against the capture rather than a mock."""
    prs = dt.load_snapshot(FIXTURE)
    excluded = {d.number for d in dt.classify(prs) if d.code == dt.CODE_NON_DEPENDABOT}
    dependabot = {p.number for p in prs if p.author in dt.DEPENDABOT_AUTHORS}
    assert dependabot
    assert not (dependabot & excluded)


def test_author_exclusion_precedes_coupling():
    """A non-Dependabot PR must never reach family logic."""
    prs = [
        _pr(
            number=1,
            author="attacker",
            ecosystem="github-actions",
            package="github/codeql-action/init",
        ),
        _pr(
            number=2,
            ecosystem="github-actions",
            package="github/codeql-action/analyze",
        ),
    ]
    by_number = {d.number: d for d in dt.classify(prs)}
    assert by_number[1].code == dt.CODE_NON_DEPENDABOT
    assert by_number[1].family is None


def test_every_decision_carries_a_nonempty_reason():
    for decision in dt.classify(dt.load_snapshot(FIXTURE)):
        assert decision.reason.strip()


def test_no_section_names_a_code_no_rule_can_emit():
    rendered = {code for _, codes in dt._SECTIONS for code in codes}
    assert rendered == {dt.CODE_CANDIDATE, dt.CODE_COUPLED, dt.CODE_NON_DEPENDABOT}


def test_nothing_in_the_pipeline_merges_approves_or_marks_ready():
    """The single property the whole reduction is meant to guarantee."""
    workflow = Path(".github/workflows/dependabot-triage.yml")
    targets = [
        Path("scripts/security/dep_triage.py"),
        Path("scripts/security/dep_triage_collect.py"),
        workflow,
    ]
    for path in targets:
        # Comments are stripped so a line explaining why something is *not*
        # done cannot fail the scan. A `gh pr merge` hidden in a comment is
        # still not a call, and the trigger check below reads parsed YAML.
        text = "\n".join(
            line.split("#", 1)[0]
            for line in path.read_text(encoding="utf-8").split("\n")
        )
        for needle in ("gh pr merge", "gh pr review", "gh pr ready", "--admin"):
            assert needle not in text, f"{path} contains {needle!r}"

    # YAML 1.1 resolves a bare `on:` key to the boolean True, so read both.
    parsed = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    triggers = parsed.get("on", parsed.get(True))
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    assert set(parsed["jobs"]) == {"triage"}


# --------------------------------------------------------------------------
# Report rendering
# --------------------------------------------------------------------------


def test_render_report_groups_families_and_sections():
    prs = dt.load_snapshot(FIXTURE)
    report = dt.render_report(dt.classify(prs), prs)
    assert "## Candidates" in report
    assert "### `github/codeql-action`" in report
    assert "### `npm:/frontend:vitest`" in report
    assert "## Excluded" in report
    for number in CODEQL_FAMILY:
        assert f"#{number}" in report
    # Every row names the head commit it was computed against.
    assert f"`{prs[0].head_sha[:10]}`" in report


def test_render_report_names_every_dependabot_title_without_a_package():
    """A whole batch here means the title format moved and coupling is inert."""
    prs = [_pr(number=9, package="", title="chore(deps): bump the npm group")]
    assert "#9" in dt.title_parse_line(prs)
    assert "0 of 1" in dt.title_parse_line(prs)


def test_render_report_neutralizes_a_hostile_non_dependabot_title():
    """A public repo means any stranger chooses an Excluded row's title."""
    hostile = "<img src=x onerror=alert(1)> [click](http://evil) `x` | injected"
    prs = [_pr(number=99, author="attacker", title=hostile)]
    report = dt.render_report(dt.classify(prs), prs)
    row = next(line for line in report.splitlines() if line.startswith("| #99"))
    # The whole title is inside a code span, and its pipe cannot break the cell.
    assert (
        "``<img src=x onerror=alert(1)> [click](http://evil) `x` \\| injected``" in row
    )
    # Five cells, so six column delimiters. The title's own pipe is escaped and
    # therefore not one of them.
    assert row.replace("\\|", "").count("|") == 6


def test_inert_span_fences_longer_than_the_longest_backtick_run():
    assert dt._inert_span("a``b") == "```a``b```"
    assert dt._inert_span("`x`") == "`` `x` ``"


def test_main_writes_the_report_and_the_decisions(tmp_path):
    report = tmp_path / "out" / "triage.md"
    decisions = tmp_path / "out" / "decisions.json"
    assert (
        dt.main(
            [
                "--snapshot",
                str(FIXTURE),
                "--output",
                str(report),
                "--decisions",
                str(decisions),
            ]
        )
        == 0
    )
    assert report.read_text(encoding="utf-8").startswith("# Dependabot Triage")
    payload = json.loads(decisions.read_text(encoding="utf-8"))
    assert len(payload["decisions"]) == len(CAPTURED_NUMBERS)
    assert {d["code"] for d in payload["decisions"]} == {
        dt.CODE_CANDIDATE,
        dt.CODE_COUPLED,
        dt.CODE_NON_DEPENDABOT,
    }
