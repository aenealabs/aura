"""Data contracts for the model-upgrade watcher (issue #212)."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class BedrockModelVersion:
    """Versioned identifier for one tier's Bedrock model.

    ``tier`` is the Aura capability tier (STANDARD / ADVANCED).
    ``model_id`` is the Bedrock model id (e.g.
    'anthropic.claude-sonnet-4-7-20260120'). ``version`` is the
    version string AWS exposes alongside the id; the watcher
    treats a change in either as a bump.
    """

    tier: str
    model_id: str
    version: str = ""

    @property
    def identity(self) -> str:
        """Combined identity used for change detection."""
        return f"{self.model_id}@{self.version}" if self.version else self.model_id


class RevalidationStatus(enum.Enum):
    """Lifecycle status of a single re-validation pass."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ModelUpgradeEvent:
    """One detected bump (or absence of one) per watcher tick."""

    detected_at: datetime
    tier: str
    previous: BedrockModelVersion
    current: BedrockModelVersion

    @property
    def is_bump(self) -> bool:
        return self.previous.identity != self.current.identity


@dataclass(frozen=True)
class RevalidationOutcome:
    """Result of running the Frozen Reference Oracle against the new model."""

    status: RevalidationStatus
    tier: str
    model_identity: str
    cases_total: int = 0
    cases_passed: int = 0
    rationale: str = ""
    incident_ticket_id: str = ""
    flag_cleared: bool = False
    flag_set: bool = False
    metric_emitted: bool = False
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def passed(self) -> bool:
        return self.status == RevalidationStatus.PASSED

    def to_audit_dict(self) -> dict:
        return {
            "status": self.status.value,
            "tier": self.tier,
            "model_identity": self.model_identity,
            "cases_total": self.cases_total,
            "cases_passed": self.cases_passed,
            "rationale": self.rationale,
            "incident_ticket_id": self.incident_ticket_id,
            "flag_cleared": self.flag_cleared,
            "flag_set": self.flag_set,
            "metric_emitted": self.metric_emitted,
            "completed_at": self.completed_at.isoformat(),
        }
