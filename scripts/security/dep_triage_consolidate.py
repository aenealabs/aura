"""Verification helpers for coupled-set consolidation.

When several Dependabot PRs must land together, the consolidation branch has to
contain exactly the union of their changes -- no more, no less. An extra added
line in a consolidation branch is an unreviewed change riding along with an
approved one, so the union check is a security control, not a convenience.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_SLUG = re.compile(r"[^a-z0-9.]+")


_NULL_MODE = "000000"
_NULL_SHA = "0" * 40


class RawParseError(ValueError):
    """`git diff --raw -z` output did not have the documented shape.

    Raised rather than skipped. A record this parser cannot account for is a
    record whose change it cannot verify, and silently ignoring it is the
    failure mode this whole module exists to avoid.
    """


@dataclass(frozen=True, repr=False)
class TreeEntry:
    """One path's post-change tree metadata, as git itself computed it.

    ``status`` is the single-letter code with any similarity score dropped
    (``R100`` -> ``R``). The score is a heuristic that varies with what else
    is in the diff, so comparing it would produce mismatches that reflect
    git's rename-detection budget rather than any real difference.

    ``newmode`` and ``newsha`` describe the file *after* the change, which is
    what a consolidation branch must justify. Mode carries the executable bit
    and the symlink type (``120000``), so a ``chmod +x`` or a file swapped for
    a symlink is a different entry by construction -- neither is visible in a
    diff's ``+`` lines at all.
    """

    path: str
    status: str
    newmode: str
    newsha: str

    def __repr__(self) -> str:
        """Render for an operator-facing error message, not for eval().

        These land in the `union mismatch` message a human reads when a
        consolidation is refused, so the path comes first and the blob is
        abbreviated -- the full 40 characters are compared but add nothing
        to a human's reading of *which file* is unaccounted for.
        """
        return (
            f"<{self.status} {self.path} mode={self.newmode} blob={self.newsha[:12]}>"
        )


@dataclass(frozen=True, repr=False)
class ContestedPath:
    """A path changed by more than one member PR.

    The consolidation branch's content for such a path is git's three-way
    merge of several members' versions, so its blob matches no single
    member's blob. That is not evidence of tampering and it is not evidence
    of safety either -- it is simply outside what tree metadata can decide.

    It is reported instead of being reconciled. Reconciling it would mean
    re-deriving the merged content textually, which is the approach this
    module abandoned; asserting it is fine without checking would be a hole
    in exactly the file the members all care about.
    """

    path: str
    members: int

    def __repr__(self) -> str:
        return (
            f"<CONTESTED {self.path}: changed by {self.members} member PRs; "
            "the merged content is no single member's, so tree metadata "
            "cannot verify it -- review this file by hand>"
        )


def parse_raw(raw: str) -> list[TreeEntry]:
    """Parse `git diff --raw -z` output into per-path tree entries.

    The record shape is
    ``:<oldmode> <newmode> <oldsha> <newsha> <status>NUL<path>NUL``, with a
    **second** path field for the ``R`` and ``C`` statuses. Walking fields
    positionally (rather than splitting on newlines) is what makes the ``-z``
    form safe: a path containing a newline, a tab or a quote cannot desync
    the parse, because only NUL separates fields and NUL cannot occur in a
    path.

    A rename expands into two entries -- a deletion of the source path and a
    creation of the destination -- so that the ``R`` form and the
    ``--no-renames`` ``D``+``A`` form produce the same result. Without the
    synthesised source deletion, a file renamed *out* of a protected
    directory would leave no entry at its original path. A copy leaves its
    source untouched, so it expands to the destination entry only.
    """
    fields = raw.split("\0")
    if fields and fields[-1] == "":
        fields.pop()

    entries: list[TreeEntry] = []
    index = 0
    while index < len(fields):
        meta = fields[index]
        if meta.startswith("::"):
            # A combined (multi-parent) raw diff. `A...B` never produces one,
            # so its presence means the command was not the one this module
            # asked for -- refuse rather than guess at the wider record shape.
            raise RawParseError("combined multi-parent raw diffs are not supported")
        if not meta.startswith(":"):
            raise RawParseError(f"expected a ':' metadata field, got {meta!r}")
        parts = meta[1:].split(" ")
        if len(parts) != 5:
            raise RawParseError(f"malformed raw record: {meta!r}")
        _oldmode, newmode, _oldsha, newsha, status = parts
        if not status:
            raise RawParseError(f"raw record has an empty status: {meta!r}")
        code = status[0]

        index += 1
        if index >= len(fields):
            raise RawParseError(f"raw record has no path field: {meta!r}")
        path = fields[index]
        index += 1

        if code in ("R", "C"):
            if index >= len(fields):
                raise RawParseError(
                    f"{code} record for {path!r} has no destination path"
                )
            destination = fields[index]
            index += 1
            if code == "R":
                entries.append(TreeEntry(path, "D", _NULL_MODE, _NULL_SHA))
            entries.append(TreeEntry(destination, code, newmode, newsha))
        else:
            entries.append(TreeEntry(path, code, newmode, newsha))
    return entries


def entries_by_path(raw: str) -> dict[str, TreeEntry]:
    """Index parsed raw entries by path, refusing duplicates.

    `git diff --raw` emits at most one record per path. A repeated path means
    the input is not what it claims to be, and letting one entry silently
    overwrite another would discard a change -- the unsafe direction.
    """
    out: dict[str, TreeEntry] = {}
    for entry in parse_raw(raw):
        if entry.path in out:
            raise RawParseError(f"path appears twice in one raw diff: {entry.path!r}")
        out[entry.path] = entry
    return out


def added_lines(diff: str) -> set[str]:
    """Return the set of content lines added by a unified diff.

    Two details are load-bearing, because this set is what decides whether a
    consolidation branch carries anything its member pull requests did not.

    Indentation is preserved; only trailing whitespace is stripped. In YAML --
    which is what these consolidations mostly touch -- indentation is semantics,
    so the same text at a different depth is a different change. Comparing
    without it would accept a line relocated into another scope as identical to
    the reviewed one.

    The `+++ b/path` file header is recognised by diff structure, not by text. A
    header pair only ever appears before a file section's first `@@` hunk, so
    once inside a hunk every `+` line is content. Only a `diff --git` separator
    returns to header territory; nothing inside a hunk may clear that state.
    Anchoring on line text instead lets a *removed* line whose content starts
    with dashes arm the skip, and the following `+`-prefixed line vanishes --
    silently dropping an unreviewed addition rather than reporting it as extra,
    which is the unsafe direction. Three earlier attempts failed exactly there.

    A multi-file diff that omits `diff --git` separators may classify a later
    file's `+++` header as content. That over-reports rather than under-reports,
    and these diffs come from `git diff`, which always emits the separators.

    The antecedent check requires the space in `--- `, because a real header is
    always `--- a/path`, `--- b/path` or `--- /dev/null`. Without it, a diff
    containing no `@@` at all would let a dashes-prefixed line arm the skip and
    swallow the following addition.
    """
    out: set[str] = set()
    in_hunk = False
    previous = ""
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
        elif line.startswith("@@"):
            in_hunk = True
        elif not in_hunk and line.startswith("+++") and previous.startswith("--- "):
            previous = line
            continue
        if line.startswith("+"):
            content = line[1:].rstrip()
            if content:
                out.add(content)
        previous = line
    return out


def verify_union(
    member_diffs: list[str], combined_diff: str
) -> tuple[bool, set[str], set[str]]:
    """Check a consolidation diff equals the union of its members' additions.

    Returns (ok, missing, extra). ``missing`` are member additions absent from
    the consolidation; ``extra`` are additions present in the consolidation that
    no member PR introduced.

    Comparison is by set, so byte-identical duplicate additions collapse. That
    weakens only the ``missing`` side -- re-adding already-approved text
    introduces no new unreviewed content -- so the security-relevant ``extra``
    side is unaffected.
    """
    expected: set[str] = set()
    for diff in member_diffs:
        expected |= added_lines(diff)
    actual = added_lines(combined_diff)
    missing = expected - actual
    extra = actual - expected
    return (not missing and not extra, missing, extra)


def branch_name(family: str, version: str) -> str:
    """Build the consolidation branch name for a family and target version.

    Both ``family`` and ``version`` are slugified. ``version`` legitimately
    carries npm requirement-range markers such as ``^`` or ``~`` (Dependabot
    titles like "Update vitest requirement from ^4.0.16 to ^5.0.0"), and those
    characters are not valid in a git ref, so leaving it unslugified breaks
    branch creation for exactly the coupled-npm case this module exists to
    consolidate.
    """
    family_slug = _SLUG.sub("-", family.lower()).strip("-")
    version_slug = _SLUG.sub("-", version.lower()).strip("-")
    return f"dep-consolidate/{family_slug}-{version_slug}"


def families_from_decisions(decisions: list[dict]) -> dict[str, list[int]]:
    """Group coupled decisions by family, in ascending PR order.

    Decisions are read as plain dicts -- the same shape `dep_triage` writes to
    `decisions.json` -- rather than as `Decision` instances, so this module has
    no import dependency on `dep_triage` at all.
    """
    families: dict[str, list[int]] = {}
    for decision in decisions:
        if decision.get("code") != "coupled":
            continue
        family = decision.get("family")
        if not family:
            continue
        families.setdefault(family, []).append(int(decision["number"]))
    return {key: sorted(value) for key, value in families.items()}


def consolidation_body(family: str, version: str, members: list[int]) -> str:
    """Build the consolidated PR body explaining why members cannot merge alone."""
    listed = ", ".join(f"#{number}" for number in sorted(members))
    return (
        f"Consolidates the `{family}` update to {version}.\n\n"
        f"Members: {listed}.\n\n"
        "These cannot be merged individually. The refs must move together, so "
        "merging any one alone leaves the repository inconsistent -- and a "
        "member can pass every check while still being unsafe by itself.\n\n"
        "The set of added lines in this branch was verified equal to the union "
        "of the member pull requests' added lines before this PR was opened.\n\n"
        "Member PRs are left open deliberately: Dependabot retires them once "
        "the version lands, and keeping them open means rejecting this "
        "consolidation does not discard the originals.\n\n"
        "Operator review and merge required. Nothing here was merged or "
        "approved automatically."
    )


class CommandFailed(RuntimeError):
    """A subprocess command exited non-zero."""


def _run(args: list[str], capture: bool = False) -> str:
    """Execute a command, raising CommandFailed on a non-zero exit."""
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise CommandFailed(
            f"{' '.join(args)} exited {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout if capture else ""


def consolidate_family(
    family: str,
    version: str,
    members: list[int],
    run: Callable[..., str] = _run,
) -> tuple[bool, str]:
    """Build a consolidation branch for one family and open its pull request.

    Returns (ok, message). Never merges and never approves anything: the
    consolidated PR goes through the same operator review as any other change.

    The union check is a security control. If the branch contains an added line
    that no member PR introduced, an unreviewed change would be riding along
    inside an approved one, so the function refuses to open the PR.

    `git`/`gh` calls go through the injected `run` callable rather than calling
    `subprocess` directly, so this orchestration is unit-testable with a fake
    that never touches the network or a real git checkout.

    Every command failure is converted into a returned `(False, message)` rather
    than raised. This component holds write access, so a raised exception is the
    expensive outcome: the branch may already be pushed, and an escape past the
    caller's loop would leave the repository on a consolidation branch and
    silently skip every remaining family. The `finally` returns to `main` on all
    paths for the same reason.
    """
    branch = branch_name(family, version)
    try:
        run(["git", "switch", "-c", branch, "origin/main"])

        member_diffs: list[str] = []
        for pr in members:
            run(["git", "fetch", "origin", f"pull/{pr}/head:pr-{pr}"])
            member_diffs.append(
                run(["git", "diff", f"origin/main...pr-{pr}"], capture=True)
            )
            try:
                run(["git", "merge", "--no-edit", f"pr-{pr}"])
            except CommandFailed:
                # A merge conflict must not leave the repo on a half-merged
                # branch: abort the in-progress merge before reporting. The
                # return to main is handled by the outer `finally`.
                run(["git", "merge", "--abort"])
                return (False, f"family {family}: PR #{pr} conflicts; skipped")

        if not any(added_lines(d) for d in member_diffs):
            return (
                False,
                f"family {family}: no member contributed an added line; "
                "refusing to open an empty consolidation",
            )

        combined = run(["git", "diff", "origin/main...HEAD"], capture=True)
        ok, missing, extra = verify_union(member_diffs, combined)
        if not ok:
            return (
                False,
                f"family {family}: union mismatch; "
                f"missing={sorted(missing)} extra={sorted(extra)}",
            )

        run(["git", "push", "-u", "origin", branch, "--force-with-lease"])
        run(
            [
                "gh",
                "pr",
                "create",
                "--base",
                "main",
                "--head",
                branch,
                "--title",
                f"chore(deps): bump {family} to {version} across all refs",
                "--body",
                consolidation_body(family, version, members),
                "--label",
                "dependencies",
                "--label",
                "automated",
            ]
        )
        for pr in members:
            run(
                [
                    "gh",
                    "pr",
                    "comment",
                    str(pr),
                    "--body",
                    f"Superseded by the consolidated PR on `{branch}`; this PR "
                    "cannot be merged on its own.",
                ]
            )
        return (True, f"family {family}: opened {branch}")
    except CommandFailed as exc:
        return (False, f"family {family}: aborted after a command failure: {exc}")
    finally:
        # Return to main on every path, including the failure paths above. A
        # failure that left the repository on a consolidation branch would
        # make the next family in the loop branch from the wrong base.
        try:
            run(["git", "switch", "main"])
        except CommandFailed:
            pass


def main(argv: list[str] | None = None) -> int:
    """Open one consolidated PR per coupled family.

    Without `--execute`, the plan is printed and nothing is changed -- that
    dry-run default is a safety property: the workflow can be exercised (or a
    developer can sanity-check its output locally) without ever touching git
    remotes or opening a pull request.
    """
    parser = argparse.ArgumentParser(
        description="Open consolidated PRs for coupled Dependabot families."
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        required=True,
        help="decisions.json written by dep_triage.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        help="snapshot.json, used for target versions.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually create branches and PRs. Without it, "
        "the plan is printed and nothing is changed.",
    )
    args = parser.parse_args(argv)

    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))["decisions"]
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    versions = {
        pr["number"]: pr.get("to_version", "") for pr in snapshot["pull_requests"]
    }

    families = families_from_decisions(decisions)
    any_failed = False
    for family, members in sorted(families.items()):
        if len(members) < 2:
            continue
        target = next((versions[m] for m in members if versions.get(m)), "")
        if not args.execute:
            print(f"would consolidate {family} -> {target}: {members}")
            continue
        ok, message = consolidate_family(family, target, members)
        print(message)
        if not ok:
            # The union check is a security control: an unreviewed line
            # riding along inside an approved consolidation. A ::warning::
            # is easy to miss on a manually dispatched run, so a failed
            # family is reported as an error and fails the job.
            print(f"::error::{message}")
            any_failed = True
    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
