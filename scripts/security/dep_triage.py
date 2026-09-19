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
from pathlib import Path

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
