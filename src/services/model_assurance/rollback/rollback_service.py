"""One-click rollback orchestrator (ADR-088 Phase 3.3).

Three operations:

    record_upgrade(revision)     called after every approved
                                 evaluation pipeline run that
                                 changed the active model config.
                                 Appends to history.
    rollback_one_step()          one-click reversion to the
                                 previous revision. Verifies the
                                 target model is currently
                                 available; if not, surfaces
                                 TARGET_MODEL_UNAVAILABLE so the
                                 operator can decide whether to
                                 roll back further.
    rollback_to(revision_id)     explicit-target rollback (used by
                                 double-rollback flows where the
                                 operator already knows n-2 is the
                                 right target).

The rollback itself is a NEW revision in the history — never a
truncation. The audit trail is linear and append-only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from src.services.model_assurance.rollback.contracts import (
    ConfigRevision,
    ModelAvailabilityCheck,
    RollbackOutcome,
    RollbackVerdict,
)
from src.services.model_assurance.rollback.revision_history import (
    RevisionHistory,
)

logger = logging.getLogger(__name__)


# A pluggable hook for "is this model currently available in Bedrock /
# the deployment registry". Production wires this to a Bedrock
# ListFoundationModels call; tests inject a fake.
AvailabilityProbe = Callable[[str], ModelAvailabilityCheck]


def _always_available(model_id: str) -> ModelAvailabilityCheck:
    return ModelAvailabilityCheck(model_id=model_id, is_available=True)


class RollbackService:
    """Stateless rollback orchestrator over a RevisionHistory."""

    def __init__(
        self,
        *,
        history: RevisionHistory | None = None,
        availability_probe: AvailabilityProbe | None = None,
    ) -> None:
        self._history = history or RevisionHistory()
        self._availability = availability_probe or _always_available
        self._counter = 0

    @property
    def history(self) -> RevisionHistory:
        return self._history

    def record_upgrade(self, revision: ConfigRevision) -> None:
        """Append a new upgrade revision to the history."""
        self._history.append(revision)

    def rollback_one_step(
        self,
        *,
        operator_id: str = "system",
        notes: str = "",
    ) -> RollbackOutcome:
        """Roll back to the immediately-previous revision."""
        return self._rollback_n_back(
            n=1, operator_id=operator_id, notes=notes,
        )

    def rollback_two_steps(
        self,
        *,
        operator_id: str = "system",
        notes: str = "",
    ) -> RollbackOutcome:
        """Restore the n-2 configuration (double-rollback shorthand)."""
        return self._rollback_n_back(
            n=2, operator_id=operator_id, notes=notes,
        )

    def rollback_to(
        self,
        revision_id: str,
        *,
        operator_id: str = "system",
        notes: str = "",
    ) -> RollbackOutcome:
        """Explicit-target rollback to a named revision_id."""
        target = self._history.find(revision_id)
        if target is None:
            return RollbackOutcome(
                verdict=RollbackVerdict.REVISION_NOT_FOUND,
                target_revision_id=revision_id,
                detail=f"revision_id {revision_id!r} not found in history",
            )
        # Defensive: don't roll back to the latest (no-op).
        latest = self._history.latest()
        if latest is not None and latest.revision_id == target.revision_id:
            return RollbackOutcome(
                verdict=RollbackVerdict.NO_PRIOR_REVISION,
                target_revision_id=target.revision_id,
                detail="target is already the active revision",
            )
        return self._apply_rollback(
            target=target,
            from_id=latest.revision_id if latest else "",
            operator_id=operator_id,
            notes=notes,
        )

    # ---------------------------------------------------- internals

    def _rollback_n_back(
        self,
        *,
        n: int,
        operator_id: str,
        notes: str,
    ) -> RollbackOutcome:
        target = self._history.nth_back(n)
        if target is None:
            return RollbackOutcome(
                verdict=RollbackVerdict.NO_PRIOR_REVISION,
                detail=(
                    f"history has fewer than {n + 1} entries; "
                    f"cannot roll back {n} step(s)"
                ),
            )
        latest = self._history.latest()
        from_id = latest.revision_id if latest else ""
        return self._apply_rollback(
            target=target,
            from_id=from_id,
            operator_id=operator_id,
            notes=notes,
        )

    def _apply_rollback(
        self,
        *,
        target: ConfigRevision,
        from_id: str,
        operator_id: str,
        notes: str,
    ) -> RollbackOutcome:
        # Edge case the issue specifically calls out: target model is
        # no longer available. Surface a distinct verdict so the
        # operator can decide whether to go further back instead of
        # silently failing or applying half a rollback.
        check = self._availability(target.model_id)
        if not check.is_available:
            return RollbackOutcome(
                verdict=RollbackVerdict.TARGET_MODEL_UNAVAILABLE,
                target_revision_id=target.revision_id,
                detail=(
                    f"target model {target.model_id!r} not available: "
                    f"{check.reason or 'no longer in registry'}"
                ),
            )

        new_revision = ConfigRevision(
            revision_id=self._next_revision_id(),
            model_id=target.model_id,
            model_parameters=target.model_parameters,
            prompt_template_version=target.prompt_template_version,
            created_at=datetime.now(timezone.utc),
            created_by=operator_id,
            notes=notes or (
                f"rollback to {target.revision_id} from {from_id}"
            ),
            rolled_back_from=from_id or None,
        )
        self._history.append(new_revision)
        return RollbackOutcome(
            verdict=RollbackVerdict.APPLIED,
            new_revision=new_revision,
            target_revision_id=target.revision_id,
        )

    def _next_revision_id(self) -> str:
        self._counter += 1
        return f"rev-rollback-{self._counter:06d}"
