"""Dependabot triage classifier.

Pure decision logic: consumes a JSON snapshot produced by
``dep_triage_collect.py`` and emits a classification plus a stated reason for
every open pull request. Performs no network access and has no side effects, so
the whole rule set is unit-testable against recorded fixtures.

Nothing in this module merges or approves a pull request. See
``docs/superpowers/specs/2026-09-19-dependabot-triage-design.md``.

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
from dataclasses import dataclass
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
CODE_MAJOR = "held:major-review"
CODE_COOLDOWN = "held:cooldown"
CODE_CANDIDATE = "candidate"
CODE_MERGE_SAFE = "merge-safe"

PACKAGE_COOLDOWN_DAYS = 3
ACTION_COOLDOWN_DAYS = 7

_LEADING_INT = re.compile(r"\D*(\d+)")


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


@dataclass(frozen=True)
class Decision:
    """Classification outcome for one pull request."""

    number: int
    code: str
    reason: str
    family: str | None = None


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


# Path globs whose changes require human policy review rather than a version
# judgement. Keep each entry commented with the rule it protects.
POLICY_PATHS: dict[str, str] = {
    "Dockerfile": (
        "container base images must come from private ECR "
        "(aura-base-images); a bump can silently reintroduce a public image"
    ),
    "pyproject.toml": "carries the 70% coverage threshold, which must not be lowered",
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


def rule_policy_path(pr: PRSnapshot) -> Decision | None:
    """R3: changes to policy-sensitive paths need human review."""
    for path in pr.files:
        name = PurePosixPath(path).name
        for marker, why in POLICY_PATHS.items():
            if name == marker or name.startswith(f"{marker}."):
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


def rule_major(pr: PRSnapshot) -> Decision | None:
    """R8: major bumps carry breaking changes CI may not exercise.

    No bypass exists. An earlier revision let a body-text advisory match skip
    this hold; see the module docstring for why that was removed.
    """
    before, after = major_of(pr.from_version), major_of(pr.to_version)
    if before is None or after is None or after <= before:
        return None
    return Decision(
        number=pr.number,
        code=CODE_MAJOR,
        reason=(
            f"major bump {pr.from_version} -> {pr.to_version} "
            f"({before} -> {after}); breaking changes may not be covered by CI"
        ),
    )


def rule_cooldown(pr: PRSnapshot) -> Decision | None:
    """R9: hold releases younger than the cooldown window.

    A freshly published version is the window in which a compromised release is
    still undetected. Actions wait longer because they are SHA-pinned
    supply-chain surface executed with repository credentials.

    No bypass exists, which is what makes an unknown release age safe to report:
    this rule holds on unknown, so every ecosystem with no stdlib-reachable
    release timestamp queues for a human rather than passing unexamined.
    """
    limit = (
        ACTION_COOLDOWN_DAYS
        if pr.ecosystem == "github-actions"
        else PACKAGE_COOLDOWN_DAYS
    )
    if pr.release_age_days is None:
        return Decision(
            number=pr.number,
            code=CODE_COOLDOWN,
            reason="release age unknown; cannot confirm the cooldown elapsed",
        )
    if pr.release_age_days < limit:
        return Decision(
            number=pr.number,
            code=CODE_COOLDOWN,
            reason=(
                f"{pr.to_version} is {pr.release_age_days:.0f}d old, "
                f"under the {limit}d cooldown for {pr.ecosystem}"
            ),
        )
    return None


def classify(prs: list[PRSnapshot]) -> list[Decision]:
    """Classify every PR with the first matching rule.

    Rule order is load-bearing. Author and check-presence exclusions run first
    so non-Dependabot and unvalidated PRs never reach version logic. Coupling
    runs before check evaluation because the failure mode it guards against is a
    *green* sibling. Everything surviving is a candidate, which only becomes
    merge-safe by passing the batch proof.
    """
    families = detect_families(prs)
    decisions: list[Decision] = []
    for pr in prs:
        decision = (
            rule_non_dependabot(pr)
            or rule_no_checks(pr)
            or rule_policy_path(pr)
            or rule_held_package(pr)
            or rule_coupled(pr, families)
            or rule_failing(pr)
            or rule_missing_required(pr)
            or rule_required_not_passing(pr)
            or rule_major(pr)
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
        decisions.append(decision)
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
            CODE_MAJOR,
            CODE_COOLDOWN,
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
    unparsed = [p for p in attempted if not p.package]
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


def render_report(
    decisions: list[Decision],
    prs: list[PRSnapshot],
    proof_url: str | None = None,
    controls: dict | None = None,
) -> str:
    """Build the markdown triage report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    titles = {p.number: p.title for p in prs}
    lines: list[str] = [f"# Dependabot Triage -- {now}", ""]
    lines.append(
        "Automated classification. Every merge is performed by an operator; "
        "nothing here merges or approves a pull request."
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
                    f"#{d.number}" for d in sorted(members, key=lambda m: m.number)
                )
                lines.append(f"### `{family}`")
                lines.append("")
                lines.append(
                    f"Members ({len(members)}): {numbers}. These must land "
                    "together; no member is individually mergeable."
                )
                lines.append("")
            continue
        lines.append("| PR | Code | Title | Reason |")
        lines.append("|----|------|-------|--------|")
        for d in sorted(selected, key=lambda x: x.number):
            title = titles.get(d.number, "").replace("|", "\\|")
            reason = d.reason.replace("|", "\\|")
            lines.append(f"| #{d.number} | `{d.code}` | {title} | {reason} |")
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
