"""Dependabot triage classifier.

Pure decision logic: consumes a JSON snapshot produced by
``dep_triage_collect.py`` and emits a classification plus a stated reason for
every open pull request. Performs no network access and has no side effects, so
the whole rule set is unit-testable against recorded fixtures.

Nothing in this module merges or approves a pull request. See
``docs/superpowers/specs/2026-09-19-dependabot-triage-design.md``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEPENDABOT_AUTHOR = "dependabot[bot]"

# Classification codes. Consumers match on these exact strings.
CODE_NON_DEPENDABOT = "excluded:non-dependabot"
CODE_NO_CHECKS = "excluded:no-checks"
CODE_POLICY_REVIEW = "held:policy-review"
CODE_PINNED_BY_POLICY = "held:pinned-by-policy"
CODE_RISK_TIER = "held:risk-tier"
CODE_COUPLED = "coupled"
CODE_FAILING = "attention:failing"
CODE_SUSPECTED_FLAKE = "attention:suspected-flake"
CODE_MISSING_REQUIRED = "attention:missing-required"
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
    """One check run on a pull request head."""

    name: str
    status: str
    conclusion: str | None
    failing_log_excerpt: str = ""


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
    security_advisory: bool = False


@dataclass(frozen=True)
class Decision:
    """Classification outcome for one pull request."""

    number: int
    code: str
    reason: str
    family: str | None = None


def load_snapshot(path: Path) -> list[PRSnapshot]:
    """Read a snapshot JSON file into immutable PRSnapshot records."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    snapshots: list[PRSnapshot] = []
    for item in raw["pull_requests"]:
        checks = tuple(
            CheckRun(
                name=c["name"],
                status=c["status"],
                conclusion=c.get("conclusion"),
                failing_log_excerpt=c.get("failing_log_excerpt", ""),
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
                security_advisory=bool(item.get("security_advisory", False)),
            )
        )
    return snapshots


def rule_non_dependabot(pr: PRSnapshot) -> Decision | None:
    """R1: only Dependabot PRs are in scope.

    Keyed on author identity rather than title text, so Release Please and
    other bot PRs are excluded regardless of how they are titled.
    """
    if pr.author != DEPENDABOT_AUTHOR:
        return Decision(
            number=pr.number,
            code=CODE_NON_DEPENDABOT,
            reason=f"author is {pr.author!r}, not {DEPENDABOT_AUTHOR!r}",
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
    "pyproject.toml": ("carries the 70% coverage threshold, which must not be lowered"),
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


# Substrings in a failing step's log that indicate infrastructure trouble
# rather than a defect in the change under test. Each entry must be specific
# enough that a genuinely broken change cannot produce it.
FLAKE_SIGNATURES: tuple[str, ...] = (
    "exit code 35",
    "Could not resolve host",
    "connection reset",
    "TLS handshake timeout",
    "rate limit",
    "429 Too Many Requests",
    "ECONNRESET",
)

FAILED_CONCLUSIONS: frozenset[str] = frozenset({"failure", "timed_out"})


def _is_flake(check: CheckRun) -> bool:
    """True when a failed check's log carries an infrastructure signature."""
    excerpt = check.failing_log_excerpt.lower()
    return any(signature.lower() in excerpt for signature in FLAKE_SIGNATURES)


def rule_failing(pr: PRSnapshot) -> Decision | None:
    """R6: classify failing checks, separating infrastructure flakes.

    A flake is worth a rerun; a real failure is worth a human. Conflating them
    means genuine failures get retried and flakes rot untouched.

    Each failed check is judged on its own log. A PR is only called a flake
    when every failed check is one: if a genuine failure and a flake land
    together, the genuine failure decides, because a "rerun once" label on a
    real defect hides it until someone reruns and watches it fail again.
    """
    failed = [c for c in pr.checks if (c.conclusion or "") in FAILED_CONCLUSIONS]
    if not failed:
        return None

    flaky: list[CheckRun] = []
    genuine: list[CheckRun] = []
    for check in failed:
        (flaky if _is_flake(check) else genuine).append(check)

    if genuine:
        reason = f"{', '.join(c.name for c in genuine)} failed"
        if flaky:
            reason += (
                f" (also failing with an infrastructure signature: "
                f"{', '.join(c.name for c in flaky)})"
            )
        return Decision(number=pr.number, code=CODE_FAILING, reason=reason)

    return Decision(
        number=pr.number,
        code=CODE_SUSPECTED_FLAKE,
        reason=(
            f"{', '.join(c.name for c in flaky)} failed with an "
            "infrastructure signature, not a defect in the change; rerun once "
            "before escalating"
        ),
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

    Security advisories bypass this hold entirely: a CVE fix must not be
    delayed for a major-version review.
    """
    if pr.security_advisory:
        return None
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

    Security advisories bypass this hold entirely: the cooldown defends against
    compromised releases, and applying it to a CVE fix would delay the patch it
    exists to protect.
    """
    if pr.security_advisory:
        return None
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
