"""Rollback mechanism contracts (ADR-088 Phase 3.3).

After every approved model-config update the platform records a
``ConfigRevision`` so a one-click rollback can restore the previous
configuration without going back through the full evaluation
pipeline. Each revision is immutable; rollback creates a NEW
revision that points at the prior state.

Edge cases the contract handles per ADR-088 acceptance criteria:

  * Rollback when the previous model is no longer available in
    Bedrock — the revision-history check surfaces the missing model
    so the operator decides whether to roll back to n-2 instead.
  * Double rollback (n -> n-1 -> n-2) — each rollback is itself a
    revision, so the chain is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping


class RollbackVerdict(Enum):
    """Outcome of a rollback request."""

    APPLIED = "applied"
    NO_PRIOR_REVISION = "no_prior_revision"
    TARGET_MODEL_UNAVAILABLE = "target_model_unavailable"
    REVISION_NOT_FOUND = "revision_not_found"


@dataclass(frozen=True)
class ConfigRevision:
    """One revision of the active model configuration.

    Each upgrade emits exactly one revision; each rollback ALSO
    emits a revision (its ``rolled_back_from`` field is non-empty).
    The chain is the linked-list audit trail.
    """

    revision_id: str
    model_id: str
    model_parameters: tuple[tuple[str, str], ...] = ()  # tuple-of-tuples → hashable
    prompt_template_version: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    created_by: str = "system"
    notes: str = ""
    # When this revision is itself the result of a rollback, this
    # field carries the revision_id we rolled back FROM. The
    # ``model_id`` already reflects the rolled-back-TO target.
    rolled_back_from: str | None = None

    @property
    def parameters_dict(self) -> dict[str, str]:
        return dict(self.model_parameters)


@dataclass(frozen=True)
class RollbackOutcome:
    """Result of one rollback attempt."""

    verdict: RollbackVerdict
    new_revision: ConfigRevision | None = None
    target_revision_id: str | None = None
    detail: str = ""

    @property
    def applied(self) -> bool:
        return self.verdict is RollbackVerdict.APPLIED


@dataclass(frozen=True)
class ModelAvailabilityCheck:
    """Probe result for whether a target model is currently deployable."""

    model_id: str
    is_available: bool
    reason: str = ""
