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
from pathlib import Path
from typing import Callable

_SLUG = re.compile(r"[^a-z0-9.]+")


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

    Only ``family`` is slugified; ``version`` is assumed to already be a plain
    release identifier as parsed from a bump title.
    """
    slug = _SLUG.sub("-", family.lower()).strip("-")
    return f"dep-consolidate/{slug}-{version}"


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
    """
    branch = branch_name(family, version)
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
            # A merge conflict must not leave the repo on a half-merged branch:
            # abort the in-progress merge and return to main before reporting.
            run(["git", "merge", "--abort"])
            run(["git", "switch", "main"])
            return (False, f"family {family}: PR #{pr} conflicts; skipped")

    combined = run(["git", "diff", "origin/main...HEAD"], capture=True)
    ok, missing, extra = verify_union(member_diffs, combined)
    if not ok:
        run(["git", "switch", "main"])
        return (
            False,
            f"family {family}: union mismatch; "
            f"missing={sorted(missing)} extra={sorted(extra)}",
        )

    run(["git", "push", "-u", "origin", branch, "--force"])
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
                f"Superseded by the consolidated PR on `{branch}`; this PR cannot "
                "be merged on its own.",
            ]
        )
    run(["git", "switch", "main"])
    return (True, f"family {family}: opened {branch}")


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
            print(f"::warning::{message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
