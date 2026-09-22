"""Tests for coupled-set consolidation verification.

The union check compares tree metadata from `git diff --raw -z`, not diff
text. Tests that existed only to pin the behaviour of the old unified-diff
parser (`+++`-prefixed content, dashes-prefixed removals arming a header
skip, hunk-state resets) were removed with that parser: they asserted
properties of a state machine that no longer exists, and there is no state
machine left for crafted content to steer. What replaces them is the block
of attack regressions below, which covers what the text check structurally
could not see -- deletions, modes, renames, and file identity.
"""

import json

import pytest

from scripts.security import dep_triage_consolidate as dcon

BLOB_PAYLOADQ_OLD = "a" * 40
BLOB_PAYLOADQ_NEW = "b" * 40
BLOB_QUALITY_OLD = "c" * 40
BLOB_QUALITY_NEW = "d" * 40
BLOB_PAYLOAD = "e" * 40
BLOB_PAYLOADQ_NEWLANK = "f" * 40
ZEROS = "0" * 40

CODEQL = ".github/workflows/codeql.yml"
QUALITY = ".github/workflows/code-quality.yml"


def raw(*records):
    """Build `git diff --raw -z` output from (meta..., *paths) tuples.

    Each record is ``(oldmode, newmode, oldsha, newsha, status, *paths)``.
    The real command emits a trailing NUL after the final field, so this does
    too -- a parser that only worked on input without it would be parsing
    something git never produces.
    """
    fields = []
    for record in records:
        fields.append(":%s %s %s %s %s" % tuple(record[:5]))
        fields.extend(record[5:])
    return "".join(f + "\0" for f in fields)


# PR #450 bumps codeql-action/init, in codeql.yml. Its PR diff has two hunks
# (the `uses:` line and the pinned-version comment), but `--raw` reports one
# entry per *path*: what is compared is the file's resulting blob, so hunk
# count is not part of the comparison and cannot be gamed by splitting a
# change across more of them.
MEMBER_450 = raw(
    ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEW, "M", CODEQL)
)
# PR #452 bumps codeql-action/upload-sarif, which lives in a different file.
MEMBER_452 = raw(("100644", "100644", BLOB_QUALITY_OLD, BLOB_QUALITY_NEW, "M", QUALITY))
COMBINED = raw(
    ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEW, "M", CODEQL),
    ("100644", "100644", BLOB_QUALITY_OLD, BLOB_QUALITY_NEW, "M", QUALITY),
)


# --------------------------------------------------------------------------
# The legitimate path
# --------------------------------------------------------------------------


def test_verify_union_accepts_an_exact_union():
    ok, missing, extra = dcon.verify_union([MEMBER_450, MEMBER_452], COMBINED)
    assert ok and not missing and not extra


def test_verify_union_accepts_a_two_hunk_single_file_consolidation():
    """A member whose PR edits one file in two places still verifies.

    Two hunks collapse into one `--raw` entry, because the entry describes
    the file's resulting content. The union check is comparing end states,
    not counting edits.
    """
    member = raw(
        ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEW, "M", CODEQL)
    )
    ok, missing, extra = dcon.verify_union([member], member)
    assert ok and not missing and not extra


def test_verify_union_accepts_a_member_that_legitimately_adds_a_file():
    member = raw(("000000", "100644", ZEROS, BLOB_PAYLOADQ_NEW, "A", "new.yml"))
    ok, _, _ = dcon.verify_union([member], member)
    assert ok


def test_verify_union_reports_a_member_change_the_branch_does_not_carry():
    ok, missing, extra = dcon.verify_union([MEMBER_450, MEMBER_452], MEMBER_450)
    assert not ok
    assert dcon.TreeEntry(QUALITY, "M", "100644", BLOB_QUALITY_NEW) in missing
    assert not extra


# --------------------------------------------------------------------------
# Attack regressions
#
# Each of these six passed the previous added-line text check. The first
# three are invisible to any `+`-line comparison; the fourth defeated it by
# discarding the file a line landed in; the last two by discarding lines
# that were empty after stripping.
# --------------------------------------------------------------------------


def test_attack_deleting_a_security_workflow_is_reported():
    """A deletion is not an added line, so the text check never saw it."""
    combined = COMBINED + raw(
        (
            "100644",
            "000000",
            BLOB_PAYLOAD,
            ZEROS,
            "D",
            ".github/workflows/security-scan.yml",
        )
    )
    ok, _, extra = dcon.verify_union([MEMBER_450, MEMBER_452], combined)
    assert not ok
    assert (
        dcon.TreeEntry(".github/workflows/security-scan.yml", "D", "000000", ZEROS)
        in extra
    )


def test_attack_making_a_script_executable_is_reported():
    """A mode change alters no line at all; only the mode bits move."""
    combined = COMBINED + raw(
        ("100644", "100755", BLOB_PAYLOAD, BLOB_PAYLOAD, "M", "scripts/deploy.sh")
    )
    ok, _, extra = dcon.verify_union([MEMBER_450, MEMBER_452], combined)
    assert not ok
    assert dcon.TreeEntry("scripts/deploy.sh", "M", "100755", BLOB_PAYLOAD) in extra


def test_attack_chmod_on_a_members_own_file_is_reported():
    """Sharper than the above: the path *is* one a member changed.

    It cannot be caught by noticing an unfamiliar path, and the blob is the
    member's own. Only the mode differs, so this fails unless mode is part
    of the compared entry.
    """
    combined = raw(
        ("100644", "100755", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEW, "M", CODEQL),
        ("100644", "100644", BLOB_QUALITY_OLD, BLOB_QUALITY_NEW, "M", QUALITY),
    )
    ok, missing, extra = dcon.verify_union([MEMBER_450, MEMBER_452], combined)
    assert not ok
    assert dcon.TreeEntry(CODEQL, "M", "100755", BLOB_PAYLOADQ_NEW) in extra
    assert dcon.TreeEntry(CODEQL, "M", "100644", BLOB_PAYLOADQ_NEW) in missing


def test_attack_renaming_a_workflow_out_of_the_workflows_directory_is_reported():
    """Under `--no-renames` a move is a deletion plus a creation.

    Both halves are unexplained: the workflow stops being a workflow, and a
    file appears where no member put one.
    """
    combined = raw(
        ("100644", "000000", BLOB_PAYLOADQ_OLD, ZEROS, "D", CODEQL),
        ("000000", "100644", ZEROS, BLOB_PAYLOADQ_OLD, "A", "docs/codeql.yml"),
        ("100644", "100644", BLOB_QUALITY_OLD, BLOB_QUALITY_NEW, "M", QUALITY),
    )
    ok, missing, extra = dcon.verify_union([MEMBER_450, MEMBER_452], combined)
    assert not ok
    assert dcon.TreeEntry("docs/codeql.yml", "A", "100644", BLOB_PAYLOADQ_OLD) in extra
    assert dcon.TreeEntry(CODEQL, "D", "000000", ZEROS) in extra


def test_attack_rename_reported_even_when_git_detects_it_as_a_rename():
    """The same move, reported by git in its `R` form rather than as D+A.

    `consolidate_family` passes `--no-renames`, but `verify_union` is given
    whatever the injected runner returns, so the `R` form must be caught
    too -- including the disappearance of the source path.
    """
    combined = raw(
        (
            "100644",
            "100644",
            BLOB_PAYLOADQ_OLD,
            BLOB_PAYLOADQ_OLD,
            "R100",
            CODEQL,
            "docs/codeql.yml",
        ),
        ("100644", "100644", BLOB_QUALITY_OLD, BLOB_QUALITY_NEW, "M", QUALITY),
    )
    ok, missing, extra = dcon.verify_union([MEMBER_450, MEMBER_452], combined)
    assert not ok
    assert dcon.TreeEntry(CODEQL, "D", "000000", ZEROS) in extra
    assert dcon.TreeEntry("docs/codeql.yml", "R", "100644", BLOB_PAYLOADQ_OLD) in extra


def test_attack_approved_content_landing_in_a_different_file_is_reported():
    """The blob is byte-identical to an approved one -- in the wrong file.

    This is the case that most directly killed the text check: comparing
    added lines as bare strings threw away the path, so an approved line
    satisfied the check no matter which file it was written into.
    """
    combined = COMBINED + raw(
        (
            "000000",
            "100644",
            ZEROS,
            BLOB_PAYLOADQ_NEW,
            "A",
            ".github/workflows/evil.yml",
        )
    )
    ok, _, extra = dcon.verify_union([MEMBER_450, MEMBER_452], combined)
    assert not ok
    assert (
        dcon.TreeEntry(".github/workflows/evil.yml", "A", "100644", BLOB_PAYLOADQ_NEW)
        in extra
    )


def test_attack_a_new_file_whose_only_added_line_is_blank_is_reported():
    """The old check dropped lines that were empty after stripping.

    A file is a tree entry whether or not its contents amount to anything,
    and an empty file in `.github/workflows/` is still a file an attacker
    can grow in a later commit.
    """
    combined = COMBINED + raw(
        (
            "000000",
            "100644",
            ZEROS,
            BLOB_PAYLOADQ_NEWLANK,
            "A",
            ".github/workflows/placeholder.yml",
        )
    )
    ok, _, extra = dcon.verify_union([MEMBER_450, MEMBER_452], combined)
    assert not ok
    assert (
        dcon.TreeEntry(
            ".github/workflows/placeholder.yml", "A", "100644", BLOB_PAYLOADQ_NEWLANK
        )
        in extra
    )


def test_attack_a_whitespace_only_addition_to_a_members_file_is_reported():
    """Whitespace-only additions were stripped to nothing and discarded.

    Applied to a file a member legitimately changed, so novelty of the path
    cannot catch it: the entry differs only in the blob, which is exactly
    what a content hash is for.
    """
    blob_with_trailing_whitespace = "9" * 40
    combined = raw(
        (
            "100644",
            "100644",
            BLOB_PAYLOADQ_OLD,
            blob_with_trailing_whitespace,
            "M",
            CODEQL,
        ),
        ("100644", "100644", BLOB_QUALITY_OLD, BLOB_QUALITY_NEW, "M", QUALITY),
    )
    ok, missing, extra = dcon.verify_union([MEMBER_450, MEMBER_452], combined)
    assert not ok
    assert dcon.TreeEntry(CODEQL, "M", "100644", blob_with_trailing_whitespace) in extra
    assert dcon.TreeEntry(CODEQL, "M", "100644", BLOB_PAYLOADQ_NEW) in missing


def test_attack_a_file_swapped_for_a_symlink_is_reported():
    """A type change (`T`) shows up as a mode of 120000."""
    combined = COMBINED + raw(
        (
            "100644",
            "120000",
            BLOB_PAYLOAD,
            BLOB_PAYLOADQ_NEWLANK,
            "T",
            "config/settings.yml",
        )
    )
    ok, _, extra = dcon.verify_union([MEMBER_450, MEMBER_452], combined)
    assert not ok
    assert (
        dcon.TreeEntry("config/settings.yml", "T", "120000", BLOB_PAYLOADQ_NEWLANK)
        in extra
    )


def test_verify_union_reports_content_added_when_no_member_contributed():
    ok, _, extra = dcon.verify_union([], COMBINED)
    assert not ok
    assert len(extra) == 2


# --------------------------------------------------------------------------
# Contested paths
# --------------------------------------------------------------------------


def test_verify_union_reports_a_path_two_members_touched():
    """Two members editing one file cannot be reconciled from hashes.

    The branch's blob for that path is git's merge of both members' blobs
    and equals neither. Reporting it is the only honest outcome; silently
    accepting whatever the merge produced would be a hole in exactly the
    file every member of the family cares about.
    """
    member_a = raw(
        ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEW, "M", CODEQL)
    )
    member_b = raw(("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOAD, "M", CODEQL))
    merged = raw(
        ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEWLANK, "M", CODEQL)
    )
    ok, missing, extra = dcon.verify_union([member_a, member_b], merged)
    assert not ok
    assert dcon.ContestedPath(CODEQL, 2) in extra


def test_contested_path_is_reported_once_not_as_a_pile_of_mismatches():
    """One clear signal, so it does not read as an attack."""
    member_a = raw(
        ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEW, "M", CODEQL)
    )
    member_b = raw(("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOAD, "M", CODEQL))
    merged = raw(
        ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEWLANK, "M", CODEQL)
    )
    _, missing, extra = dcon.verify_union([member_a, member_b], merged)
    assert extra == {dcon.ContestedPath(CODEQL, 2)}
    assert not missing


def test_contested_path_repr_tells_the_operator_to_review_by_hand():
    text = repr(dcon.ContestedPath(CODEQL, 3))
    assert CODEQL in text
    assert "3 member" in text
    assert "by hand" in text


def test_contested_path_does_not_mask_an_unrelated_extra_entry():
    """A contested path must not become a blanket amnesty for the branch."""
    member_a = raw(
        ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEW, "M", CODEQL)
    )
    member_b = raw(("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOAD, "M", CODEQL))
    merged = raw(
        ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEWLANK, "M", CODEQL),
        ("000000", "100644", ZEROS, BLOB_PAYLOAD, "A", "evil.sh"),
    )
    ok, _, extra = dcon.verify_union([member_a, member_b], merged)
    assert not ok
    assert dcon.TreeEntry("evil.sh", "A", "100644", BLOB_PAYLOAD) in extra
    assert dcon.ContestedPath(CODEQL, 2) in extra


# --------------------------------------------------------------------------
# Naming, grouping, PR body
# --------------------------------------------------------------------------


def test_branch_name_is_slugified():
    assert dcon.branch_name("github/codeql-action", "4.38.0") == (
        "dep-consolidate/github-codeql-action-4.38.0"
    )


def test_branch_name_slugifies_an_npm_requirement_range_version():
    """`to_version` legitimately carries `^`/`~` for npm requirement bumps
    (e.g. "Update vitest requirement from ^4.0.16 to ^5.0.0"). Those
    characters are invalid in a git ref, so the version must be slugified
    too, not just the family -- otherwise consolidation is dead for exactly
    the coupled-npm case it exists to handle."""
    branch = dcon.branch_name("npm:/frontend:vitest", "^5.0.0")
    # Asserted structurally rather than by shelling out to
    # `git check-ref-format`: none of git's forbidden ref characters may
    # appear, and the slug may not start or end with a dash.
    forbidden = set("^~:?*[\\")
    assert not (forbidden & set(branch))
    slug = branch.split("/", 1)[1]
    assert not slug.startswith("-")
    assert not slug.endswith("-")


def test_families_from_decisions_groups_coupled_members():
    decisions = [
        {"number": 452, "code": "coupled", "family": "github/codeql-action"},
        {"number": 450, "code": "coupled", "family": "github/codeql-action"},
        {"number": 442, "code": "coupled", "family": "npm:/frontend:vitest"},
        {"number": 439, "code": "candidate", "family": None},
    ]
    families = dcon.families_from_decisions(decisions)
    assert families["github/codeql-action"] == [450, 452]
    assert families["npm:/frontend:vitest"] == [442]
    assert 439 not in [n for v in families.values() for n in v]


def test_families_from_decisions_ignores_non_coupled():
    assert (
        dcon.families_from_decisions(
            [{"number": 1, "code": "merge-safe", "family": None}]
        )
        == {}
    )


def test_consolidation_body_names_every_member_and_the_coupling():
    body = dcon.consolidation_body(
        "github/codeql-action", "4.38.0", [450, 452, 453, 454]
    )
    for number in (450, 452, 453, 454):
        assert f"#{number}" in body
    assert "together" in body.lower()
    assert "4.38.0" in body


def test_consolidation_body_does_not_claim_members_were_closed():
    body = dcon.consolidation_body("github/codeql-action", "4.38.0", [450, 452])
    assert "closed" not in body.lower()
    assert "left open" in body.lower()


def test_consolidation_body_describes_what_was_actually_verified():
    """The body must not claim more than the check establishes.

    It previously told reviewers the branch's *added lines* had been
    verified equal to the members' added lines, which overstated a check
    that could not see deletions, modes or paths at all.
    """
    body = dcon.consolidation_body("github/codeql-action", "4.38.0", [450, 452])
    assert "added lines" not in body.lower()
    assert "mode" in body.lower()


# --------------------------------------------------------------------------
# consolidate_family orchestration
# --------------------------------------------------------------------------


class FakeRun:
    """Records commands; returns canned stdout per matched prefix."""

    def __init__(self, responses=None, fail_on=None):
        self.calls = []
        self.responses = responses or {}
        self.fail_on = fail_on or ()

    def __call__(self, args, capture=False):
        self.calls.append(list(args))
        joined = " ".join(args)
        for needle in self.fail_on:
            if needle in joined:
                raise dcon.CommandFailed(joined)
        for needle, out in self.responses.items():
            if needle in joined:
                return out
        return ""

    def ran(self, needle):
        return any(needle in " ".join(c) for c in self.calls)


def _happy_run(**overrides):
    responses = {
        "origin/main...pr-450": MEMBER_450,
        "origin/main...pr-452": MEMBER_452,
        "origin/main...HEAD": COMBINED,
    }
    responses.update(overrides.pop("responses", {}))
    return FakeRun(responses=responses, **overrides)


def test_consolidate_family_opens_pr_when_union_matches():
    run = _happy_run()
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert ok, message
    assert run.ran("switch -c dep-consolidate/github-codeql-action-4.38.0")
    assert run.ran("pr create")
    # A plain --force on a stable branch name would let this call clobber
    # commits an operator added to an already-open consolidation PR.
    assert run.ran(
        "push -u origin dep-consolidate/github-codeql-action-4.38.0 "
        "--force-with-lease"
    )


def test_consolidate_family_asks_git_for_tree_metadata_not_diff_text():
    """The flags are the control. `--raw -z` is what makes the comparison
    structural; `--no-abbrev` prevents git shortening hashes by a length
    that varies with repository size; `--no-renames` makes a move a
    deterministic D+A on both sides instead of a similarity heuristic whose
    result depends on the size of the surrounding diff."""
    run = _happy_run()
    dcon.consolidate_family("github/codeql-action", "4.38.0", [450, 452], run)
    diffs = [c for c in run.calls if c[:2] == ["git", "diff"]]
    assert diffs, "no git diff was run"
    for call in diffs:
        assert "--raw" in call
        assert "-z" in call
        assert "--no-abbrev" in call
        assert "--no-renames" in call


def test_consolidate_family_refuses_when_the_branch_carries_an_extra_entry():
    """A change no member introduced is an unreviewed change."""
    sneaky = COMBINED + raw(("000000", "100644", ZEROS, BLOB_PAYLOAD, "A", "evil.sh"))
    run = _happy_run(responses={"origin/main...HEAD": sneaky})
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "union" in message.lower()
    assert "evil.sh" in message
    assert not run.ran("pr create")
    # Defense in depth: a regression that moved the push above the union
    # check would still be caught here even if `pr create` were guarded.
    assert not run.ran("push")


def test_consolidate_family_refuses_when_the_branch_deletes_a_workflow():
    """The deletion case, driven through the orchestration rather than
    through `verify_union` alone -- the gate must be wired to the push."""
    sneaky = COMBINED + raw(
        (
            "100644",
            "000000",
            BLOB_PAYLOAD,
            ZEROS,
            "D",
            ".github/workflows/security-scan.yml",
        )
    )
    run = _happy_run(responses={"origin/main...HEAD": sneaky})
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "security-scan.yml" in message
    assert not run.ran("pr create")
    assert not run.ran("push")


def test_consolidate_family_refuses_when_two_members_touch_one_path():
    """Reported for human attention, not reconciled and not pushed."""
    run = _happy_run(
        responses={
            "origin/main...pr-452": raw(
                ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOAD, "M", CODEQL)
            ),
            "origin/main...HEAD": raw(
                (
                    "100644",
                    "100644",
                    BLOB_PAYLOADQ_OLD,
                    BLOB_PAYLOADQ_NEWLANK,
                    "M",
                    CODEQL,
                )
            ),
        }
    )
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "CONTESTED" in message
    assert CODEQL in message
    assert not run.ran("pr create")
    assert not run.ran("push")


def test_consolidate_family_returns_to_main_after_a_union_mismatch():
    sneaky = COMBINED + raw(("000000", "100644", ZEROS, BLOB_PAYLOAD, "A", "evil.sh"))
    run = _happy_run(responses={"origin/main...HEAD": sneaky})
    ok, _ = dcon.consolidate_family("github/codeql-action", "4.38.0", [450, 452], run)
    assert not ok
    assert run.ran("switch main")


def test_consolidate_family_refuses_when_the_raw_diff_is_unreadable():
    """A check that cannot run is not a check that passed."""
    run = _happy_run(responses={"origin/main...HEAD": "not a raw diff at all"})
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "unreadable" in message.lower()
    assert not run.ran("pr create")
    assert not run.ran("push")
    assert run.ran("switch main")


def test_consolidate_family_returns_cleanly_when_pr_create_fails():
    """Re-running a family whose PR already exists must not raise."""
    run = _happy_run(fail_on=("pr create",))
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "command failure" in message.lower()
    assert run.ran("switch main"), "must return to main even after a failure"


def test_consolidate_family_returns_cleanly_when_push_fails():
    run = _happy_run(fail_on=("push",))
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert not run.ran("pr create")
    assert run.ran("switch main")


def test_consolidate_family_refuses_when_no_member_contributed_a_change():
    """verify_union([], "") passes vacuously (True, set(), set()). If every
    member diff came back empty, that vacuous pass must not let an empty
    branch and an empty PR get created."""
    run = FakeRun(
        responses={
            "origin/main...pr-450": "",
            "origin/main...pr-452": "",
            "origin/main...HEAD": "",
        }
    )
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "no member contributed" in message.lower()
    assert not run.ran("pr create")
    assert not run.ran("push")


def test_consolidate_family_aborts_on_merge_conflict():
    run = FakeRun(
        responses={"origin/main...pr-450": MEMBER_450},
        fail_on=("merge --no-edit pr-452",),
    )
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "conflict" in message.lower()
    assert run.ran("merge --abort")
    assert not run.ran("pr create")
    assert run.ran("switch main")


def test_consolidate_family_never_merges_or_approves():
    run = _happy_run()
    dcon.consolidate_family("github/codeql-action", "4.38.0", [450, 452], run)
    for forbidden in ("pr merge", "pr review", "pr ready"):
        assert not run.ran(forbidden), f"must never run: {forbidden}"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _write_fixtures(tmp_path):
    decisions = {
        "decisions": [
            {"number": 452, "code": "coupled", "family": "github/codeql-action"},
            {"number": 450, "code": "coupled", "family": "github/codeql-action"},
            {"number": 439, "code": "candidate", "family": None},
        ]
    }
    snapshot = {
        "pull_requests": [
            {"number": 452, "to_version": "4.38.0"},
            {"number": 450, "to_version": "4.38.0"},
            {"number": 439, "to_version": "1.2.3"},
        ]
    }
    dec_path = tmp_path / "decisions.json"
    snap_path = tmp_path / "snapshot.json"
    dec_path.write_text(json.dumps(decisions), encoding="utf-8")
    snap_path.write_text(json.dumps(snapshot), encoding="utf-8")
    return dec_path, snap_path


def test_main_dry_run_prints_plan_without_execute(tmp_path, capsys):
    """Without --execute, main must be pure: no consolidate_family call at all."""
    dec_path, snap_path = _write_fixtures(tmp_path)
    rc = dcon.main(["--decisions", str(dec_path), "--snapshot", str(snap_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "would consolidate" in out
    assert "github/codeql-action" in out
    assert "450" in out and "452" in out


def test_main_skips_families_with_a_single_member(tmp_path, capsys):
    """A lone `coupled` PR (e.g. a family whose sibling already merged) is not
    consolidated -- there is nothing to union against."""
    decisions = {
        "decisions": [
            {"number": 442, "code": "coupled", "family": "npm:/frontend:vitest"},
        ]
    }
    snapshot = {"pull_requests": [{"number": 442, "to_version": "2.0.0"}]}
    dec_path = tmp_path / "decisions.json"
    snap_path = tmp_path / "snapshot.json"
    dec_path.write_text(json.dumps(decisions), encoding="utf-8")
    snap_path.write_text(json.dumps(snapshot), encoding="utf-8")

    rc = dcon.main(["--decisions", str(dec_path), "--snapshot", str(snap_path)])
    assert rc == 0
    assert "would consolidate" not in capsys.readouterr().out


def test_main_execute_invokes_consolidate_family_per_family(
    tmp_path, monkeypatch, capsys
):
    """`--execute` drives `consolidate_family`; the network/git seam is still
    the injected `run`, so this patches the function itself rather than
    touching a real git checkout."""
    dec_path, snap_path = _write_fixtures(tmp_path)
    calls = []

    def fake_consolidate_family(family, version, members, run=dcon._run):
        calls.append((family, version, members))
        return (True, f"family {family}: opened dep-consolidate/fake")

    monkeypatch.setattr(dcon, "consolidate_family", fake_consolidate_family)
    rc = dcon.main(
        ["--decisions", str(dec_path), "--snapshot", str(snap_path), "--execute"]
    )
    assert rc == 0
    assert calls == [("github/codeql-action", "4.38.0", [450, 452])]
    assert "opened dep-consolidate/fake" in capsys.readouterr().out


def test_main_execute_reports_error_and_nonzero_on_family_failure(
    tmp_path, monkeypatch, capsys
):
    """The union check is a security control. A ::warning:: with exit 0 is
    easy to miss on a manually dispatched run, so a failed family must be
    reported as an ::error:: and fail the job."""
    dec_path, snap_path = _write_fixtures(tmp_path)

    def fake_consolidate_family(family, version, members, run=dcon._run):
        return (False, f"family {family}: union mismatch")

    monkeypatch.setattr(dcon, "consolidate_family", fake_consolidate_family)
    rc = dcon.main(
        ["--decisions", str(dec_path), "--snapshot", str(snap_path), "--execute"]
    )
    assert rc != 0
    out = capsys.readouterr().out
    assert "::error::" in out
    assert "::warning::" not in out


# --------------------------------------------------------------------------
# Structural raw-diff parsing
# --------------------------------------------------------------------------


def test_parse_raw_reads_a_simple_modification():
    out = dcon.parse_raw(
        raw(
            (
                "100644",
                "100644",
                BLOB_PAYLOADQ_OLD,
                BLOB_PAYLOADQ_NEW,
                "M",
                ".github/workflows/codeql.yml",
            )
        )
    )
    assert out == [
        dcon.TreeEntry(".github/workflows/codeql.yml", "M", "100644", BLOB_PAYLOADQ_NEW)
    ]


def test_parse_raw_reads_several_records_from_one_nul_stream():
    out = dcon.parse_raw(
        raw(
            ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEW, "M", "a.yml"),
            ("000000", "100644", ZEROS, BLOB_PAYLOAD, "A", "b.yml"),
        )
    )
    assert [e.path for e in out] == ["a.yml", "b.yml"]
    assert [e.status for e in out] == ["M", "A"]


def test_parse_raw_handles_an_empty_diff():
    assert dcon.parse_raw("") == []


def test_parse_raw_expands_a_rename_into_a_source_deletion_and_a_destination():
    """A rename must leave an entry at the path it vacated.

    Keyed only on the destination, a file renamed *out* of a protected
    directory would produce no entry at its original path at all -- the
    disappearance would be invisible, which is the direction that hides an
    attack rather than reporting it.
    """
    out = dcon.parse_raw(
        raw(
            (
                "100644",
                "100644",
                BLOB_PAYLOADQ_OLD,
                BLOB_PAYLOADQ_OLD,
                "R100",
                ".github/workflows/codeql.yml",
                "docs/codeql.yml",
            )
        )
    )
    assert dcon.TreeEntry(".github/workflows/codeql.yml", "D", "000000", ZEROS) in out
    assert dcon.TreeEntry("docs/codeql.yml", "R", "100644", BLOB_PAYLOADQ_OLD) in out


def test_parse_raw_does_not_desync_on_the_second_path_of_a_rename():
    """The record after a two-path R must still parse as a record.

    A parser that assumed one path per record would read the destination
    path as the next record's metadata field and lose every entry after it.
    """
    out = dcon.parse_raw(
        raw(
            (
                "100644",
                "100644",
                BLOB_PAYLOADQ_OLD,
                BLOB_PAYLOADQ_OLD,
                "R100",
                "old.yml",
                "new.yml",
            ),
            ("100644", "100644", BLOB_PAYLOADQ_NEW, BLOB_PAYLOAD, "M", "after.yml"),
        )
    )
    assert dcon.TreeEntry("after.yml", "M", "100644", BLOB_PAYLOAD) in out


def test_parse_raw_expands_a_copy_without_deleting_the_source():
    out = dcon.parse_raw(
        raw(
            (
                "100644",
                "100644",
                BLOB_PAYLOADQ_OLD,
                BLOB_PAYLOADQ_OLD,
                "C75",
                "src.yml",
                "copy.yml",
            )
        )
    )
    assert [e.path for e in out] == ["copy.yml"]


def test_parse_raw_drops_the_similarity_score_from_the_status():
    """The score reflects git's rename-detection budget, not the change."""
    out = dcon.parse_raw(
        raw(
            (
                "100644",
                "100644",
                BLOB_PAYLOADQ_OLD,
                BLOB_PAYLOADQ_OLD,
                "R087",
                "old.yml",
                "new.yml",
            )
        )
    )
    assert out[-1].status == "R"


def test_parse_raw_keeps_a_path_containing_a_newline_intact():
    """NUL separation is the reason the `-z` form is used.

    A path with a newline in it would split a line-oriented parser's record
    in half; here it is simply part of one field.
    """
    out = dcon.parse_raw(
        raw(("000000", "100644", ZEROS, BLOB_PAYLOADQ_OLD, "A", "we\nird.yml"))
    )
    assert out == [dcon.TreeEntry("we\nird.yml", "A", "100644", BLOB_PAYLOADQ_OLD)]


def test_parse_raw_rejects_a_record_without_a_leading_colon():
    with pytest.raises(dcon.RawParseError):
        dcon.parse_raw("100644 100644 x y M\0a.yml\0")


def test_parse_raw_rejects_a_combined_multi_parent_diff():
    """`A...B` never emits one, so its appearance means a different command."""
    with pytest.raises(dcon.RawParseError):
        dcon.parse_raw("::100644 100644 100644 aaa bbb ccc MM\0a.yml\0")


def test_parse_raw_rejects_a_metadata_field_with_the_wrong_arity():
    with pytest.raises(dcon.RawParseError):
        dcon.parse_raw(":100644 100644 M\0a.yml\0")


def test_parse_raw_rejects_a_record_with_no_path_field():
    with pytest.raises(dcon.RawParseError):
        dcon.parse_raw(
            ":100644 100644 %s %s M\0" % (BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEW)
        )


def test_parse_raw_rejects_a_rename_with_no_destination_path():
    with pytest.raises(dcon.RawParseError):
        dcon.parse_raw(
            ":100644 100644 %s %s R100\0old.yml\0"
            % (BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_OLD)
        )


def test_parse_raw_rejects_an_empty_status():
    with pytest.raises(dcon.RawParseError):
        dcon.parse_raw(
            ":100644 100644 %s %s \0a.yml\0" % (BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEW)
        )


def test_entries_by_path_rejects_a_duplicated_path():
    """Letting one entry overwrite another would discard a change."""
    with pytest.raises(dcon.RawParseError):
        dcon.entries_by_path(
            raw(
                (
                    "100644",
                    "100644",
                    BLOB_PAYLOADQ_OLD,
                    BLOB_PAYLOADQ_NEW,
                    "M",
                    "a.yml",
                ),
                ("100644", "100644", BLOB_PAYLOADQ_NEW, BLOB_PAYLOAD, "M", "a.yml"),
            )
        )


def test_tree_entry_repr_names_the_path_for_an_operator():
    entry = dcon.TreeEntry(".github/workflows/codeql.yml", "D", "000000", ZEROS)
    text = repr(entry)
    assert ".github/workflows/codeql.yml" in text
    assert text.startswith("<D ")
