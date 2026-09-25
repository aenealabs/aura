"""Dependabot triage classifier.

Pure decision logic: consumes a JSON snapshot produced by
``dep_triage_collect.py`` and emits a classification plus a stated reason for
every open pull request. Performs no network access and has no side effects, so
the whole rule set is unit-testable against recorded fixtures.

Nothing in this module merges or approves a pull request. See
``docs/superpowers/specs/2026-09-19-dependabot-triage-design.md``.

Three observations used to be holds. Two are annotations now and one still
holds, and the reasoning below is the whole chain rather than the end state,
because the middle step is where the argument actually lives.

The starting point: this report is advisory. It merges nothing, and the
repository's ``main-protection`` ruleset still requires one human approval plus
four status checks before anything lands. A hold does not block a merge -- it
only tells the operator to look -- so it earns its cost only when it states
something the operator could not cheaply derive from the PR in front of them.
Anything else inflates the Held pile, and a Held pile that is mostly restatement
trains the operator to skim it, which is how a hold carrying genuinely
non-obvious information gets missed.

Demoted to ``Decision.notes``, and staying demoted:

* ``held:major-review`` -- a major semver bump. The entire content of the
  observation is the leading integer going up, which is written in the PR
  title the reviewer is already reading.
* The ``POLICY_PATHS`` half of ``held:policy-review`` -- a diff touching a
  ``Dockerfile*`` or a ``pyproject.toml``. Both are self-evident one-file
  diffs. What is *not* self-evident is why each matters, so the per-entry
  rationale survives as note text.

Retained as a hold, on a narrower argument:

* The ``POLICY_DIRS`` half of ``held:policy-review`` -- a diff under
  ``.github/workflows/``. This was demoted along with the rest and then
  restored, because it fails the "cheaply derive" test where the other two pass
  it. What a reviewer sees in a workflow diff is ``uses: owner/action@<40 hex>``
  replaced by ``@<40 other hex>``. That proves the pin moved and reveals
  nothing about what the new pin points at, which is the only load-bearing
  fact. SHA pinning helps only if a human confirms the new SHA is the one
  intended, and nothing in this module confirms that. It is also the most
  credential-adjacent surface in the repository -- the batch that motivated
  this work contained an ``aws-actions/configure-aws-credentials`` bump, i.e.
  the action that performs AWS credential assumption -- so the hold is what
  puts the confirmation in front of someone. A security review raised exactly
  this case against the demotion and was right on the facts.

Net effect, which is the point: the Held pile stays small by design. In the
captured batch it is two PRs of twenty-two -- one At-Risk register entry and one
workflow bump -- with the coupled set in its own section. Both remaining hold
categories say something the PR does not. If a future change grows this pile
with restatement again, the skimming problem comes back and the useful holds go
with it.

Reversing either direction is a small edit, so state the intent if you make one.
To re-demote the workflow hold: delete ``rule_workflow_path`` from
``classify``'s chain and fold ``POLICY_DIRS`` into ``note_policy_file``. To
re-promote a note to a hold: give it a ``CODE_*`` constant, a ``_SECTIONS``
entry, and a position in the chain after ``rule_coupled``.

An earlier revision carried a "security advisory" fast path that let a PR skip
both the major-version hold and the cooldown when its body text mentioned a CVE
or GHSA id; it was removed because body text is the wrong primitive for a
control that strips two guards -- a real Dependabot security body cites the
advisory inside a collapsible block rather than the preamble, so the heuristic
fired on ordinary bumps and stayed silent on the updates it existed for. The
correct signal, if the capability is wanted later, is
``gh api repos/{owner}/{repo}/dependabot/alerts`` correlated to the PR by
package name and ``fixed_in`` version, which is authoritative rather than
inferred.

A "suspected flake" detector was removed for the same reason. It matched
infrastructure signatures ("rate limit", "Could not resolve host") against
``CheckRun.failing_log_excerpt``, which the collector filled from
``gh pr checks --json description``. That description is empty for every
GitHub Actions check run, so no signature could ever match and the code path
was unreachable in production while advertising coverage the tool did not
have. Every failure now reads as genuine, which is conservative and honest
about it.

A sound reimplementation would read the failing check run's own failure
annotation -- ``gh api repos/{owner}/{repo}/check-runs/{id}/annotations`` --
which the runner writes about the step, not the step's own stdout. The easy
version is the dangerous one: matching patterns like "rate limit" or
"429 Too Many Requests" against arbitrary program output lets a compromised
package print that string from its own test process and have the classifier
relabel its genuine test failure as "rerun once before escalating". That is
evidence tampering through a signal the adversary controls, and it is the
reason the detector must not be rebuilt on program output.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

# `gh` normalizes bot logins to `app/<slug>`; the GitHub API and webhooks use
# `<slug>[bot]`. Both are accepted because the collector reads whichever form its
# source returns, and a mismatch here silently excludes every Dependabot PR --
# which is exactly the defect this set replaces.
DEPENDABOT_AUTHORS: frozenset[str] = frozenset({"app/dependabot", "dependabot[bot]"})

# Classification codes. Consumers match on these exact strings.
CODE_NON_DEPENDABOT = "excluded:non-dependabot"
CODE_NO_CHECKS = "excluded:no-checks"
CODE_POLICY_REVIEW = "held:policy-review"
CODE_PINNED_BY_POLICY = "held:pinned-by-policy"
CODE_RISK_TIER = "held:risk-tier"
CODE_COUPLED = "coupled"
CODE_FAILING = "attention:failing"
CODE_MISSING_REQUIRED = "attention:missing-required"
CODE_REQUIRED_NOT_PASSING = "attention:required-not-passing"
CODE_CONFLICT = "attention:conflict"
# "this release is too new" and "I could not determine the age" are different
# facts about a PR and lead to different operator actions. Conflating them
# under one code is what made every github-actions PR read as a transient
# lookup glitch.
CODE_COOLDOWN = "held:cooldown"
CODE_NO_RELEASE_METADATA = "held:no-release-metadata"
CODE_GROUPED_UNPARSED = "held:grouped-unparsed"
CODE_CANDIDATE = "candidate"
CODE_MERGE_SAFE = "merge-safe"

# The effective granularity either constant delivers is the triage
# schedule's own interval (monthly, `.github/workflows/dependabot-triage.yml`
# cron `0 16 1 * *`), not the number written here. A release is either
# already older than the constant at the first triage that sees it, or it is
# held to the next scheduled run regardless -- so both constants read, in
# practice, as "held until the next run," and a smaller number here does not
# buy a package an earlier merge. The monthly cadence widens that gap rather
# than narrowing it: schedule-only worst case is now the interval, not a
# week. Do not read either constant as a promise that a release unlocks
# after exactly that many days.
#
# The 7-day commitment in docs/security/SI2_DEPENDENCY_COOLDOWN_RISK_
# ACCEPTANCE.md is therefore procedural, not automatic: it rests on the
# weekly dependency-risk audit surfacing an urgent finding and an operator
# re-dispatching triage, not on this schedule coming around.
PACKAGE_COOLDOWN_DAYS = 3

# Defence-in-depth, not a live control: every GitHub Actions PR reaches
# `rule_coupled` or `rule_workflow_path` before `rule_cooldown` ever runs
# (`classify`'s rule order below), and `rule_workflow_path` holds every one of
# them as `held:policy-review` because `.github/workflows/` is in
# `POLICY_DIRS` -- so this constant does not currently gate anything for the
# github-actions ecosystem. It briefly *was* the only live control on that
# path, during the revision that demoted the workflow hold to a note; the
# module docstring records why that was narrowed back. It would become live
# again only if that hold stopped matching workflow files: `POLICY_DIRS`'s
# `.github/workflows` entry narrowed, removed, or a github-actions bump
# started landing outside that directory. If that happens, the same
# effective-granularity caveat as `PACKAGE_COOLDOWN_DAYS` above applies to
# this constant too.
ACTION_COOLDOWN_DAYS = 7

_LEADING_INT = re.compile(r"\D*(\d+)")

# A grouped Dependabot PR: ".github/dependabot.yml" configures a
# `minor-and-patch` group for pip and for npm, so these are routine here.
# "bump the <group> group" is the grouped form; "bump ruff ... in the
# <group> group" is a single-package update that happens to belong to a
# group and parses as an ordinary bump, which is why the pattern anchors on
# "bump the" rather than on the word "group" alone.
_GROUP_TITLE = re.compile(r"\bbump the\s+(?P<group>.+?)\s+group\b", re.IGNORECASE)
_GROUP_COUNT = re.compile(r"\bwith\s+(?P<count>\d+)\s+updates?\b", re.IGNORECASE)


def group_name(title: str) -> str | None:
    """Return the update-group name a title belongs to, or None.

    A grouped PR bumps several packages at once and names none of them in its
    title, so ``parse_bump_title`` yields empty strings for it and every
    per-package rule sees no package to test.
    """
    match = _GROUP_TITLE.search(title or "")
    return match.group("group") if match else None


def group_update_count(title: str) -> int | None:
    """Return how many updates a grouped title claims to carry, or None.

    This is the authority on whether a parsed member list is complete. No
    single region of a Dependabot group body is: GitHub's body size cap
    truncates the per-member lines while leaving the summary table, and the
    table omits transitively-pulled members the per-member lines carry.
    """
    match = _GROUP_COUNT.search(title or "")
    return int(match.group("count")) if match else None


@dataclass(frozen=True)
class CheckRun:
    """One check run on a pull request head.

    Carries no log excerpt. The field that held one existed solely for the
    removed flake detector and was empty in every real capture; see the module
    docstring for why it is not coming back in that form.
    """

    name: str
    status: str
    conclusion: str | None


@dataclass(frozen=True)
class GroupMember:
    """One package inside a grouped Dependabot update.

    A grouped PR names no package in its title, so without these the
    per-package rules have nothing to test and every At-Risk or deliberately
    held package inside a group passes unexamined.
    """

    package: str
    from_version: str = ""
    to_version: str = ""
    risk_tier: str = "unknown"
    release_age_days: float | None = None


@dataclass(frozen=True)
class PRSnapshot:
    """Recorded state of one open pull request."""

    number: int
    title: str
    author: str
    files: tuple[str, ...]
    checks: tuple[CheckRun, ...]
    required_checks: tuple[str, ...]
    ecosystem: str
    directory: str
    package: str
    from_version: str
    to_version: str
    release_age_days: float | None
    risk_tier: str
    # Trailing because it carries a default and every field above it does not.
    # Recorded for the report's reason text; the author *login* remains the
    # decision, because a non-Dependabot bot is also `is_bot: true`.
    author_is_bot: bool = False
    # The commit the classification was computed against. Dependabot force-
    # pushes its branches on rebase, so a verdict is only true of one head:
    # the batch proof can prove commit X, the report can say merge-safe, and
    # the operator can merge commit Y. Rendered in the report and re-checked
    # by the workflow before any PR is merged into the candidate branch.
    head_sha: str = ""
    # The packages a grouped update carries, parsed from the PR body by the
    # collector. Empty for an ordinary single-package bump.
    members: tuple[GroupMember, ...] = ()


@dataclass(frozen=True)
class Decision:
    """Classification outcome for one pull request.

    ``notes`` carries advisory observations that do *not* change the
    classification: facts worth stating beside a verdict that are not
    themselves grounds for holding the PR. See the module docstring for which
    rules were demoted into notes and what that costs. Trailing because it
    carries a default and the fields above it do not.
    """

    number: int
    code: str
    reason: str
    family: str | None = None
    notes: tuple[str, ...] = ()


def load_snapshot(path: Path) -> list[PRSnapshot]:
    """Read a snapshot JSON file into immutable PRSnapshot records."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    snapshots: list[PRSnapshot] = []
    for item in raw["pull_requests"]:
        checks = tuple(
            CheckRun(
                name=c["name"],
                status=c["status"],
                conclusion=c.get("conclusion"),
            )
            for c in item["checks"]
        )
        snapshots.append(
            PRSnapshot(
                number=item["number"],
                title=item["title"],
                author=item["author"],
                files=tuple(item["files"]),
                checks=checks,
                required_checks=tuple(item["required_checks"]),
                ecosystem=item["ecosystem"],
                directory=item["directory"],
                package=item["package"],
                from_version=item["from_version"],
                to_version=item["to_version"],
                release_age_days=item.get("release_age_days"),
                risk_tier=item.get("risk_tier", "unknown"),
                author_is_bot=bool(item.get("author_is_bot", False)),
                head_sha=item.get("head_sha", ""),
                members=tuple(
                    GroupMember(
                        package=m["package"],
                        from_version=m.get("from_version", ""),
                        to_version=m.get("to_version", ""),
                        risk_tier=m.get("risk_tier", "unknown"),
                        release_age_days=m.get("release_age_days"),
                    )
                    for m in item.get("members", [])
                ),
            )
        )
    return snapshots


def rule_non_dependabot(pr: PRSnapshot) -> Decision | None:
    """R1: only Dependabot PRs are in scope.

    Keyed on author identity rather than title text, so Release Please and
    other bot PRs are excluded regardless of how they are titled. Membership is
    tested against every login form Dependabot is known to appear under, because
    an equality test against a single form excludes the whole queue whenever the
    collector's source reports the other one.
    """
    if pr.author not in DEPENDABOT_AUTHORS:
        accepted = ", ".join(repr(name) for name in sorted(DEPENDABOT_AUTHORS))
        bot_note = "a bot" if pr.author_is_bot else "not a bot"
        return Decision(
            number=pr.number,
            code=CODE_NON_DEPENDABOT,
            reason=(
                f"author is {pr.author!r} ({bot_note}), which is not one of the "
                f"accepted Dependabot logins: {accepted}"
            ),
        )
    return None


def rule_no_checks(pr: PRSnapshot) -> Decision | None:
    """R2: a PR with no check runs has not been validated.

    Without this, "no failing checks" is vacuously true for any PR whose
    workflows never ran, which would read as safe.
    """
    if not pr.checks:
        return Decision(
            number=pr.number,
            code=CODE_NO_CHECKS,
            reason="no check runs present; absence of failures proves nothing",
        )
    return None


# File markers whose changes are worth *stating* beside a verdict. These feed
# `note_policy_file`, not a hold: a Dockerfile or a pyproject.toml change is a
# self-evident one-file diff the reviewer reads directly, so the observation is
# free and the hold was not. Keep each entry commented with the rule it
# protects -- the rationale is the part a reviewer cannot read off the diff, and
# it is the whole reason these entries survive at all.
POLICY_PATHS: dict[str, str] = {
    "Dockerfile": (
        "container base images must come from private ECR "
        "(aura-base-images); a bump can silently reintroduce a public image"
    ),
    "pyproject.toml": "carries the 70% coverage threshold, which must not be lowered",
}

# Directory prefixes whose files require human policy review. Unlike
# POLICY_PATHS above, these are a *hold* (`rule_workflow_path`), because a
# reviewer looking at a workflow diff sees one opaque 40-hex SHA replace
# another: the diff proves the pin moved and reveals nothing about what the new
# pin points at, which is the only fact that matters. See the module docstring.
#
# Matched by whole path segment, never by substring -- the same discipline
# POLICY_PATHS uses, and for the same reason: a substring match once held
# frontend/src/components/DockerfileViewer.jsx as a Dockerfile change. Keyed by
# the segment tuple; the value is (accepted suffixes, the rule it protects).
POLICY_DIRS: dict[tuple[str, ...], tuple[tuple[str, ...], str]] = {
    (".github", "workflows"): (
        (".yml", ".yaml"),
        "a workflow's `uses:` pin decides which third-party code runs with "
        "repository credentials, so moving it is a supply-chain decision "
        "rather than a dependency bump; SHA pinning only helps if a human "
        "confirms the new SHA is the one intended",
    ),
}

# Packages deliberately capped for a documented reason.
DELIBERATE_HOLDS: dict[str, str] = {
    "tree-sitter": (
        "capped below 0.26: that release removed parser.timeout_micros, the "
        "parse-time DoS guard used in "
        "src/services/vulnerability_scanner/parsing/ast.py. See "
        "docs/DEFERRED_WORK_REGISTRY.md"
    ),
}

# Risk-register tiers whose entries say "pin precisely".
HELD_TIERS: frozenset[str] = frozenset({"at-risk", "replace-now"})


def note_policy_file(pr: PRSnapshot) -> str | None:
    """Observe that a PR touches a policy-sensitive *file*, or return None.

    ``Dockerfile*`` and ``pyproject.toml`` only. Both were part of a
    ``held:policy-review`` hold and are annotations now: each is a self-evident
    one-file diff that the human whose approval the branch ruleset requires is
    reading anyway, so the hold bought nothing the reviewer did not already
    have. What the reviewer does *not* have is the rationale -- that a base
    image must resolve to private ECR, that pyproject.toml carries the 70%
    coverage floor -- so the rationale is what survives, as text beside the
    verdict.

    The workflow-directory case is deliberately not here. It kept its hold in
    ``rule_workflow_path`` for a reason that does not apply to these two; see
    the module docstring.
    """
    for path in pr.files:
        pure = PurePosixPath(path)
        for marker, why in POLICY_PATHS.items():
            if pure.name == marker or pure.name.startswith(f"{marker}."):
                return f"touches {path}: {why}"
    return None


def rule_workflow_path(pr: PRSnapshot) -> Decision | None:
    """R3: a change under .github/workflows/ needs human policy review.

    The one member of the old ``held:policy-review`` hold that survived the
    demotion, and it survived on a narrower argument than the one that held the
    file markers. The test for keeping a hold is whether it states something the
    operator could not cheaply derive from the PR. For a Dockerfile that test
    fails: the diff is legible. For a workflow ``uses:`` pin it passes. What the
    diff shows is ``uses: owner/action@<40 hex>`` becoming ``@<40 other hex>``;
    it proves the pin moved and says nothing about what the new pin points at,
    which is the only load-bearing fact. SHA pinning only helps if a human
    confirms the new SHA is the one intended, and nothing in this module
    confirms that -- so the hold is what puts the confirmation in front of
    someone.

    Runs *after* ``rule_coupled``, which is load-bearing: every github-actions
    family touches a workflow file by construction, so running this first would
    flip all four codeql PRs out of ``coupled`` and delete the family key
    ``dep_triage_consolidate`` reads. A coupled member is held for a human
    either way, so the coupled verdict loses nothing by winning.

    Matched by whole path segment; see POLICY_DIRS on why never by substring.
    """
    for path in pr.files:
        pure = PurePosixPath(path)
        for segments, (suffixes, why) in POLICY_DIRS.items():
            if pure.parts[: len(segments)] == segments and pure.suffix in suffixes:
                return Decision(
                    number=pr.number,
                    code=CODE_POLICY_REVIEW,
                    reason=f"touches {path}: {why}",
                )
    return None


def rule_held_package(pr: PRSnapshot) -> Decision | None:
    """R4: deliberate holds and At-Risk register entries are not bumped."""
    if pr.package in DELIBERATE_HOLDS:
        return Decision(
            number=pr.number,
            code=CODE_PINNED_BY_POLICY,
            reason=DELIBERATE_HOLDS[pr.package],
        )
    if pr.risk_tier.lower() in HELD_TIERS:
        return Decision(
            number=pr.number,
            code=CODE_RISK_TIER,
            reason=(
                f"{pr.package} is tier {pr.risk_tier!r} in the dependency risk "
                "register, which specifies pinning precisely"
            ),
        )
    return None


def rule_grouped(pr: PRSnapshot) -> Decision | None:
    """R4b: apply the per-package holds to every member of a grouped update.

    Runs before ``rule_held_package`` because a grouped PR carries no package
    of its own: ``parse_bump_title`` returns empty strings for it, so the
    deliberate holds and the At-Risk tier check have nothing to match and
    cannot fire for anything inside the group. Since .github/dependabot.yml
    groups both pip and npm minor/patch updates, that is the most common PR
    shape in this repository, not a corner case.

    A PR is held if *any* member is held, and the reason names the member --
    a group is merged as one commit, so one held package holds all of it.

    A group whose members cannot be recovered from its body is held
    explicitly rather than left to fall through. Falling through would land
    it in the cooldown's "release age unknown" branch, whose reason reads as a
    transient lookup glitch when the real fact is that the per-package holds
    were never evaluated.
    """
    name = group_name(pr.title)
    if name is None:
        return None

    expected = group_update_count(pr.title)
    if not pr.members or (expected is not None and len(pr.members) < expected):
        found = len(pr.members)
        promised = "an unstated number" if expected is None else str(expected)
        return Decision(
            number=pr.number,
            code=CODE_GROUPED_UNPARSED,
            reason=(
                f"grouped update {name!r} states {promised} member package(s) "
                f"but only {found} could be parsed from the PR body, so the "
                "deliberate holds and risk-register tiers could not be "
                "evaluated for the members that are missing"
            ),
        )

    # Two passes rather than one, so a deliberate hold is reported in
    # preference to a tier hold -- the same precedence rule_held_package uses
    # for a single-package PR.
    for member in pr.members:
        if member.package in DELIBERATE_HOLDS:
            return Decision(
                number=pr.number,
                code=CODE_PINNED_BY_POLICY,
                reason=(
                    f"grouped update {name!r} carries {member.package}: "
                    f"{DELIBERATE_HOLDS[member.package]}"
                ),
            )
    for member in pr.members:
        if member.risk_tier.lower() in HELD_TIERS:
            return Decision(
                number=pr.number,
                code=CODE_RISK_TIER,
                reason=(
                    f"grouped update {name!r} carries {member.package}, tier "
                    f"{member.risk_tier!r} in the dependency risk register, "
                    "which specifies pinning precisely"
                ),
            )
    return None


def family_key(pr: PRSnapshot) -> str | None:
    """Return a candidate update-family key for a PR, or None if not groupable.

    Two signals produce a candidate:

    * A GitHub Action whose package path has a sub-action segment
      (``github/codeql-action/init``) groups under its owner/repo. Those
      sub-actions must move in lockstep or CodeQL refuses to run.
    * An npm package groups with its scoped peers in the same directory. A
      shared scope alone is not coupling; validation in ``detect_families``
      ensures the group contains the unscoped root the scope is named for.
    """
    if pr.ecosystem == "github-actions" and pr.package.count("/") >= 2:
        owner, repo, *_ = pr.package.split("/")
        return f"{owner}/{repo}"
    if pr.ecosystem == "npm" and pr.package:
        root = pr.package.lstrip("@").split("/")[0]
        return f"npm:{pr.directory}:{root}"
    return None


def _has_unscoped_root(key: str, members: list[PRSnapshot]) -> bool:
    """True when one member is the unscoped package the scope is named for.

    A shared npm scope is not evidence of coupling: @types/react and
    @types/node release on independent cadences. The coupling that matters is a
    scoped package pinned to its unscoped namesake, as @vitest/coverage-v8 is
    to vitest, so a family requires that namesake to be under update as well.

    Known limitation, accepted deliberately: a scoped cluster with no unscoped
    root in the batch (@vitest/coverage-v8 alongside @vitest/ui, with no vitest
    PR) is not detected. It loses nothing, because either member alone is a
    singleton that no grouping rule would have caught either.
    """
    root = key.rsplit(":", 1)[-1]
    return any(member.package == root for member in members)


def detect_families(prs: list[PRSnapshot]) -> dict[int, str]:
    """Map PR number to family key, for families with more than one member.

    An npm candidate family is kept only when it contains the unscoped package
    its scope is named for. A shared scope alone is not coupling.
    """
    grouped: dict[str, list[PRSnapshot]] = {}
    for pr in prs:
        key = family_key(pr)
        if key is not None:
            grouped.setdefault(key, []).append(pr)

    families: dict[int, str] = {}
    for key, members in grouped.items():
        if len(members) < 2:
            continue
        if key.startswith("npm:") and not _has_unscoped_root(key, members):
            continue
        for pr in members:
            families[pr.number] = key
    return families


FAILED_CONCLUSIONS: frozenset[str] = frozenset({"failure", "timed_out"})


def rule_failing(pr: PRSnapshot) -> Decision | None:
    """R6: a failed check is a real failure.

    There is no flake exemption. The detector that provided one is gone --
    see the module docstring -- so every failure routes to a human. That is
    the conservative direction: a "rerun once" label on a genuine defect hides
    it until someone reruns and watches it fail again, whereas a human looking
    at a real flake costs one glance.
    """
    failed = [c for c in pr.checks if (c.conclusion or "") in FAILED_CONCLUSIONS]
    if not failed:
        return None
    return Decision(
        number=pr.number,
        code=CODE_FAILING,
        reason=f"{', '.join(c.name for c in failed)} failed",
    )


def rule_missing_required(pr: PRSnapshot) -> Decision | None:
    """R7: a required check that never ran is missing, never passing.

    A required check absent from the run set looks identical to "nothing
    failed" when only conclusions are inspected. Treating absence as success is
    how a PR that never triggered its own test workflow gets reported as safe.
    """
    present = {c.name for c in pr.checks}
    missing = [name for name in pr.required_checks if name not in present]
    if not missing:
        return None
    return Decision(
        number=pr.number,
        code=CODE_MISSING_REQUIRED,
        reason=(
            "required check(s) absent from the run set: "
            f"{', '.join(missing)}; an unrun check is not a passing check"
        ),
    )


# A required check has passed only on positive evidence. `success` is the
# ordinary pass; `skipped` and `neutral` are GitHub's own "this check declined to
# object" conclusions, which a branch-protection rule also accepts. Every other
# conclusion -- including `None`, which is what an unfinished or unmapped run
# reports -- is an absence of evidence, not evidence of success.
PASSING_CONCLUSIONS: frozenset[str] = frozenset({"success", "skipped", "neutral"})


def rule_required_not_passing(pr: PRSnapshot) -> Decision | None:
    """R7b: a required check that is present but not conclusively passing.

    R7 catches a required check that is absent. This catches one that is present
    and has not passed -- still running, cancelled, timed out, errored. Without
    it the classifier treats "no objection found" as evidence of success, and a
    check that never concluded reads exactly like one that passed.
    """
    by_name: dict[str, CheckRun] = {c.name: c for c in pr.checks}
    unproven = [
        check
        for name in pr.required_checks
        if (check := by_name.get(name)) is not None
        and (check.conclusion or "") not in PASSING_CONCLUSIONS
    ]
    if not unproven:
        return None
    detail = ", ".join(
        f"{c.name} ({c.status}/{c.conclusion or 'no conclusion'})" for c in unproven
    )
    return Decision(
        number=pr.number,
        code=CODE_REQUIRED_NOT_PASSING,
        reason=(
            f"required check(s) present but not conclusively passing: {detail}; "
            "absence of a failure is not evidence of a pass"
        ),
    )


def rule_coupled(pr: PRSnapshot, families: dict[int, str]) -> Decision | None:
    """R5: no member of a multi-PR family is individually mergeable.

    Evaluated before check results, because the dangerous case is a *green*
    sibling: a PR can pass every check and still leave the repository
    inconsistent once merged alone.
    """
    key = families.get(pr.number)
    if key is None:
        return None
    return Decision(
        number=pr.number,
        code=CODE_COUPLED,
        reason=(
            f"member of update family {key!r}; members must land together, so "
            "this PR is not individually mergeable regardless of its checks"
        ),
        family=key,
    )


def major_of(version: str) -> int | None:
    """Return the leading integer of a version string, ignoring range markers.

    Handles the forms Dependabot produces: ``5.0.0``, ``^4.1.11``, ``>=2.13.5``
    and ``v7.0.1``. Returns None when no leading integer is present.
    """
    match = _LEADING_INT.match(version or "")
    return int(match.group(1)) if match else None


def note_major(pr: PRSnapshot) -> str | None:
    """Observe that a PR is a major version bump, or return None.

    This was a hold (``held:major-review``) and is now an annotation, because
    the whole content of the observation -- "the leading version integer went
    up" -- is stated in the PR title the reviewer is already looking at. See
    the module docstring for the full reasoning, including why the workflow
    hold did not go the same way.

    There is still no bypass to speak of, in the sense that nothing suppresses
    this note: an earlier revision let a body-text advisory match skip the hold
    this used to be, and that path is gone for good. What changed is the
    consequence of the observation, not the reliability of making it.
    """
    before, after = major_of(pr.from_version), major_of(pr.to_version)
    if before is None or after is None or after <= before:
        return None
    return (
        f"major bump {pr.from_version} -> {pr.to_version} "
        f"({before} -> {after}); breaking changes may not be covered by CI"
    )


def _group_cooldown(pr: PRSnapshot, limit: int) -> Decision | None:
    """Evaluate the cooldown member by member for a grouped update.

    A group has no single release age, so inventing one would be a lie in
    either direction: a group is as young as its youngest member, and the
    member that matters is whichever one is still inside the window.

    Members too new are reported before members with no resolvable age. Both
    hold, but "vite is 1d old" is a fact the operator can act on, where "no
    timestamp for vite" only says the tool could not look.
    """
    too_new = [
        m
        for m in pr.members
        if m.release_age_days is not None and m.release_age_days < limit
    ]
    if too_new:
        detail = ", ".join(
            f"{m.package} {m.to_version} ({m.release_age_days:.0f}d)"
            for m in sorted(too_new, key=lambda m: m.release_age_days or 0.0)
        )
        return Decision(
            number=pr.number,
            code=CODE_COOLDOWN,
            reason=(
                f"grouped update carries {len(too_new)} member(s) under the "
                f"{limit}d cooldown for {pr.ecosystem}: {detail}; will be "
                "re-evaluated on the next scheduled triage run rather than "
                "unlocking on a fixed day count"
            ),
        )
    unknown = [m for m in pr.members if m.release_age_days is None]
    if unknown:
        names = ", ".join(sorted(m.package for m in unknown))
        return Decision(
            number=pr.number,
            code=CODE_NO_RELEASE_METADATA,
            reason=(
                f"no release timestamp could be resolved for {names}, so the "
                f"{limit}d cooldown could not be evaluated for the whole group"
            ),
        )
    return None


def rule_cooldown(pr: PRSnapshot) -> Decision | None:
    """R9: hold releases younger than the cooldown window.

    A freshly published version is the window in which a compromised release is
    still undetected. Actions wait longer because they are SHA-pinned
    supply-chain surface executed with repository credentials.

    A grouped update is judged member by member. It never takes the single-age
    branch below: a group has no single release age, and reporting one as
    unknown states the wrong fact about it.

    No bypass exists, which is what makes an unresolvable release age safe to
    report: this rule holds on unknown. It holds under a *different* code,
    though. ``held:cooldown`` means "this release is too new"; ``held:no-
    release-metadata`` means "the age could not be determined". Conflating
    them left an operator unable to tell a real hold from an abstention, which
    mattered because every github-actions PR sat in the second case while
    reading as the first.
    """
    limit = (
        ACTION_COOLDOWN_DAYS
        if pr.ecosystem == "github-actions"
        else PACKAGE_COOLDOWN_DAYS
    )
    if group_name(pr.title) is not None:
        return _group_cooldown(pr, limit)
    if pr.release_age_days is None:
        return Decision(
            number=pr.number,
            code=CODE_NO_RELEASE_METADATA,
            reason=(
                f"no release timestamp could be resolved for {pr.package} "
                f"{pr.to_version}, so the {limit}d cooldown for "
                f"{pr.ecosystem} could not be evaluated"
            ),
        )
    if pr.release_age_days < limit:
        return Decision(
            number=pr.number,
            code=CODE_COOLDOWN,
            reason=(
                f"{pr.to_version} is {pr.release_age_days:.0f}d old, under "
                f"the {limit}d cooldown for {pr.ecosystem}; will be "
                "re-evaluated on the next scheduled triage run rather than "
                "unlocking on a fixed day count"
            ),
        )
    return None


def classify(prs: list[PRSnapshot]) -> list[Decision]:
    """Classify every PR with the first matching rule.

    Rule order is load-bearing:

    * Author and check-presence exclusions run first, so non-Dependabot and
      unvalidated PRs never reach version logic.
    * The per-package holds -- ``rule_grouped`` for a group's members, then
      ``rule_held_package`` for a single bump -- run next. They say a package
      must not move at all, which is stronger than any statement about the
      pull request carrying it.
    * ``rule_coupled`` follows, ahead of both check evaluation and
      ``rule_workflow_path``. Ahead of checks because the failure mode it
      guards against is a *green* sibling. Ahead of the workflow rule because
      a coupled verdict is the stronger statement -- no member is individually
      mergeable at all -- and because it is the only classification carrying
      the family key ``dep_triage_consolidate`` reads. Every github-actions
      family touches a workflow file by construction, so the reverse order
      would shadow every family in the repository and consolidation would find
      nothing to group.
    * Everything surviving is a candidate, which only becomes merge-safe by
      passing the batch proof.

    Two ordering trades, both deliberate. A held package in a PR that also
    touches a workflow file reports the package hold, which is the more
    specific statement. A coupled family member touching a workflow file
    reports the coupling -- both outcomes hold the PR for a human, and the
    coupled one additionally tells consolidation what to group.

    Notes are gathered for every PR and attached to whatever verdict the rules
    produce -- candidate, held, coupled or excluded alike. A coupled PR that is
    also a major bump is worth saying so, and a held PR's notes are the only
    place the demoted observations survive at all.
    """
    families = detect_families(prs)
    decisions: list[Decision] = []
    for pr in prs:
        decision = (
            rule_non_dependabot(pr)
            or rule_no_checks(pr)
            or rule_grouped(pr)
            or rule_held_package(pr)
            or rule_coupled(pr, families)
            or rule_workflow_path(pr)
            or rule_failing(pr)
            or rule_missing_required(pr)
            or rule_required_not_passing(pr)
            or rule_cooldown(pr)
            # R10: nothing objected.
            or Decision(
                number=pr.number,
                code=CODE_CANDIDATE,
                reason=(
                    "no rule objected; pending batch proof before it is "
                    "reported merge-safe"
                ),
            )
        )
        # Note order follows the order the two observations were made in when
        # both were holds, so a row reads the way it used to.
        notes = tuple(
            note for note in (note_policy_file(pr), note_major(pr)) if note is not None
        )
        decisions.append(replace(decision, notes=notes) if notes else decision)
    return decisions


def promote(
    decisions: list[Decision],
    proved: list[int],
    conflicted: list[int] | None = None,
) -> list[Decision]:
    """Apply batch-proof results to a classification.

    Only a ``candidate`` may be promoted. Anything the rules already excluded,
    held or marked coupled keeps its original classification, so a passing batch
    proof can never override a policy decision.
    """
    proved_set = set(proved)
    conflicted_set = set(conflicted or ())
    out: list[Decision] = []
    for d in decisions:
        if d.code != CODE_CANDIDATE:
            out.append(d)
        elif d.number in conflicted_set:
            out.append(
                Decision(
                    number=d.number,
                    code=CODE_CONFLICT,
                    reason="conflicts with the candidate integration branch",
                    family=d.family,
                    # A promotion changes the verdict, never the observations
                    # the classifier made about the PR.
                    notes=d.notes,
                )
            )
        elif d.number in proved_set:
            out.append(
                Decision(
                    number=d.number,
                    code=CODE_MERGE_SAFE,
                    reason=(
                        "passed the batch proof as a unit: dependency "
                        "resolution and the test suite succeeded with every "
                        "other candidate merged alongside it"
                    ),
                    family=d.family,
                    notes=d.notes,
                )
            )
        else:
            out.append(d)
    return out


_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Merge-safe", (CODE_MERGE_SAFE,)),
    ("Candidates (pending batch proof)", (CODE_CANDIDATE,)),
    ("Coupled sets", (CODE_COUPLED,)),
    (
        "Held",
        (
            CODE_POLICY_REVIEW,
            CODE_PINNED_BY_POLICY,
            CODE_RISK_TIER,
            CODE_COOLDOWN,
            CODE_NO_RELEASE_METADATA,
            CODE_GROUPED_UNPARSED,
        ),
    ),
    (
        "Needs attention",
        (
            CODE_FAILING,
            CODE_MISSING_REQUIRED,
            CODE_REQUIRED_NOT_PASSING,
            CODE_CONFLICT,
        ),
    ),
    ("Excluded", (CODE_NON_DEPENDABOT, CODE_NO_CHECKS)),
)


def load_controls(path: Path) -> dict:
    """Read the snapshot's recorded control inputs, or {} if it has none.

    Kept separate from ``load_snapshot`` so the return type of that function --
    which other tools consume -- does not change shape.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    controls = raw.get("controls")
    return controls if isinstance(controls, dict) else {}


def _control_input_lines(prs: list[PRSnapshot], controls: dict | None) -> list[str]:
    """Render the parsed control inputs the classification depended on.

    A classification is only as good as its inputs, and both inputs fail
    quietly: a risk register that moved parses to no tiers, and a title format
    Dependabot changes parses to no package. Either produces a confident report
    in which no hold fires. Stating them puts the check in front of the only
    reader who can judge whether they look right.
    """
    lines = ["## Control inputs", ""]

    tiers = (controls or {}).get("risk_register_tiers")
    if isinstance(tiers, dict) and tiers:
        register = (controls or {}).get("risk_register_path", "the risk register")
        held = sorted(
            f"`{name}` ({tier})"
            for name, tier in tiers.items()
            if str(tier).lower() in HELD_TIERS
        )
        held_text = ", ".join(held) if held else "none"
        lines.append(
            f"- Risk register (`{register}`): {len(tiers)} package tier(s) "
            f"parsed. Held tiers: {held_text}."
        )
    else:
        lines.append(
            "- Risk register: **no tiers recorded in this snapshot**, so no "
            "At-Risk hold could have fired. Treat every verdict below as "
            "unverified against the register."
        )

    attempted = [p for p in prs if p.author in DEPENDABOT_AUTHORS]
    unparsed = [p for p in attempted if not p.package and group_name(p.title) is None]
    parsed = len(attempted) - len(unparsed)
    line = f"- Bump titles: {parsed} of {len(attempted)} Dependabot title(s) parsed."
    if unparsed:
        numbers = ", ".join(
            f"#{p.number}" for p in sorted(unparsed, key=lambda x: x.number)
        )
        line += (
            f" Unparsed: {numbers} -- these carry no package name, so the "
            "per-package holds cannot fire for them."
        )
    lines.append(line)
    lines.append("")
    return lines


def _inert_span(text: str) -> str:
    """Wrap ``text`` in a Markdown code span it cannot escape out of.

    A PR title is attacker-controlled: this repository is public, and any
    non-Dependabot PR's title -- reported verbatim in the "Excluded" section
    -- is chosen by whoever opened that PR. Without this, backticks, a
    ``[link](...)`` or an inline ``<img>``/``<details>`` tag in a title pass
    straight through into an issue body an operator reads and acts on.

    Follows CommonMark's own rule for code spans: use a backtick fence one
    character longer than the longest run of backticks already inside the
    content (so the content's own backticks can never close the span early),
    and pad with a single space on each side when the content starts or ends
    with a backtick (otherwise that backtick would visually fuse with the
    fence). There is no newline in a PR title, so a forged table *row* is not
    possible here -- only a forged inline element within one cell -- and a
    code span is sufficient defense against that.
    """
    longest_run = 0
    current = 0
    for char in text:
        if char == "`":
            current += 1
            longest_run = max(longest_run, current)
        else:
            current = 0
    fence = "`" * (longest_run + 1)
    body = f" {text} " if text[:1] == "`" or text[-1:] == "`" else text
    return f"{fence}{body}{fence}"


def render_report(
    decisions: list[Decision],
    prs: list[PRSnapshot],
    proof_url: str | None = None,
    controls: dict | None = None,
) -> str:
    """Build the markdown triage report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    titles = {p.number: p.title for p in prs}
    heads = {p.number: p.head_sha for p in prs}
    lines: list[str] = [f"# Dependabot Triage -- {now}", ""]
    lines.append(
        "Automated classification. Every merge is performed by an operator; "
        "nothing here merges or approves a pull request."
    )
    lines.append("")
    lines.append(
        "Every verdict below is a statement about the **Head** commit named "
        "beside it, and nothing else. Dependabot force-pushes its branches on "
        "rebase, so confirm the PR's head still matches before merging."
    )
    lines.append("")
    if proof_url:
        lines.append(f"Batch proof run: {proof_url}")
        lines.append("")
    lines.extend(_control_input_lines(prs, controls))

    for heading, codes in _SECTIONS:
        selected = [d for d in decisions if d.code in codes]
        lines.append(f"## {heading}")
        lines.append("")
        if not selected:
            lines.append("(none)")
            lines.append("")
            continue
        if heading == "Coupled sets":
            by_family: dict[str, list[Decision]] = {}
            for d in selected:
                by_family.setdefault(d.family or "unknown", []).append(d)
            for family, members in sorted(by_family.items()):
                numbers = ", ".join(
                    # The head SHA belongs here too: a family is merged as a
                    # unit, so every member's verdict is a statement about one
                    # specific commit exactly as it is in the tables below.
                    (
                        f"#{d.number} (`{heads.get(d.number, '')[:10]}`)"
                        if heads.get(d.number)
                        else f"#{d.number} (unknown)"
                    )
                    for d in sorted(members, key=lambda m: m.number)
                )
                lines.append(f"### `{family}`")
                lines.append("")
                lines.append(
                    f"Members ({len(members)}): {numbers}. These must land "
                    "together; no member is individually mergeable."
                )
                lines.append("")
                # The coupled section is prose, not a table, so notes cannot
                # ride along in a reason cell here. They are still printed:
                # a coupled member that is also a major bump or a workflow
                # `uses:` change is exactly the case where an operator wants
                # both facts, and dropping the note for this one section
                # would silently exempt every action family from the
                # observation the demoted policy rule used to make.
                annotated = [
                    d for d in sorted(members, key=lambda m: m.number) if d.notes
                ]
                for d in annotated:
                    lines.append(f"- #{d.number} -- {'; '.join(d.notes)}")
                if annotated:
                    lines.append("")
            continue
        lines.append("| PR | Head | Code | Title | Reason |")
        lines.append("|----|------|------|-------|--------|")
        for d in sorted(selected, key=lambda x: x.number):
            # The title is untrusted for any PR a Dependabot-only classifier
            # still has to display -- the "Excluded" section carries every
            # non-Dependabot PR's title verbatim, and anyone can open one
            # against this public repository. `_inert_span` neutralizes
            # backticks, links, and raw HTML by rendering the whole title as
            # a code span; the `|` escape still runs first because a code
            # span protects inline markup, not a table cell's own column
            # boundary. `d.reason` gets only the `|` escape and no code
            # span: reasons are strings this codebase generates from its own
            # rule set, never copied from a PR, so there is no markup in
            # them to neutralize -- only the pipe, which any reason mentioning
            # a package version range (e.g. "^4.1.11") could still contain.
            title = _inert_span(titles.get(d.number, "").replace("|", "\\|"))
            reason = d.reason.replace("|", "\\|")
            # Notes are appended to the reason cell rather than given a sixth
            # column. A note is only worth demoting a hold for if the operator
            # actually reads it, and the reason cell is the one cell they
            # already read to decide what to do about the row -- a sixth column
            # pushes the table past a readable width and puts the note where a
            # horizontal scroll can hide it. `<br>` keeps it visually distinct
            # from the verdict it sits beside. Notes get the same `|` escape
            # and no code span, for the same reason `d.reason` does: they are
            # generated from this module's own rule set, never copied from a PR.
            if d.notes:
                joined = "; ".join(n.replace("|", "\\|") for n in d.notes)
                reason = f"{reason}<br>**Note:** {joined}"
            sha = heads.get(d.number, "")
            head = f"`{sha[:10]}`" if sha else "(unknown)"
            lines.append(f"| #{d.number} | {head} | `{d.code}` | {title} | {reason} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    """Classify a snapshot and write the markdown report."""
    parser = argparse.ArgumentParser(
        description="Classify open Dependabot PRs for Project Aura."
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        help="Path to the snapshot JSON from dep_triage_collect.",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Path to write the markdown report."
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        default=None,
        help="Optional path to write decisions as JSON.",
    )
    parser.add_argument(
        "--proof-url",
        default=None,
        help="URL of the batch-proof run, embedded in the report.",
    )
    parser.add_argument(
        "--proved",
        default=None,
        help="JSON list of PR numbers that passed the batch "
        "proof; promotes them to merge-safe.",
    )
    parser.add_argument(
        "--conflicted",
        default=None,
        help="JSON list of PR numbers that conflicted with the "
        "candidate integration branch.",
    )
    args = parser.parse_args(argv)

    prs = load_snapshot(args.snapshot)
    controls = load_controls(args.snapshot)
    decisions = classify(prs)
    if args.proved or args.conflicted:
        try:
            proved = json.loads(args.proved) if args.proved else []
        except json.JSONDecodeError as exc:
            print(f"error: --proved is not valid JSON: {exc}", file=sys.stderr)
            return 1
        try:
            conflicted = json.loads(args.conflicted) if args.conflicted else []
        except json.JSONDecodeError as exc:
            print(f"error: --conflicted is not valid JSON: {exc}", file=sys.stderr)
            return 1
        decisions = promote(decisions, proved=proved, conflicted=conflicted)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        render_report(decisions, prs, args.proof_url, controls), encoding="utf-8"
    )
    if args.decisions:
        args.decisions.parent.mkdir(parents=True, exist_ok=True)
        args.decisions.write_text(
            json.dumps({"decisions": [d.__dict__ for d in decisions]}, indent=2),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
