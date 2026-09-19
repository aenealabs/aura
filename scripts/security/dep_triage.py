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
