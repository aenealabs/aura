"""ModelCandidateDetected event schema for the Scout Agent (ADR-088 Phase 1.4).

The Scout Agent emits one event per *new* candidate per run. Events
are versioned (``schema_version``) so downstream consumers can detect
schema migrations cleanly. The event is the only contract between the
Scout Agent and Phase 2's evaluation pipeline — they communicate via
EventBridge, never via direct call.

Eligibility flags ride on the event so consumers don't need to
re-execute the Adapter Registry check:

  QUALIFIED               — passes all ModelRequirements; queue for evaluation
  REJECTED_NO_CAPABILITY  — the registry's qualifier check disqualified it;
                            no further action; event is recorded purely for
                            audit (knowing the platform considered the model
                            and explicitly skipped it).
  PENDING_AVAILABILITY    — model exists in another AWS partition (commercial)
                            but is not yet available in the deployment partition
                            (GovCloud lag, 3-6 months). Re-evaluate on next
                            partition catalog update.
  ALREADY_KNOWN           — model already in active evaluation, previously
                            rejected, or already incumbent. Skip silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from src.services.model_assurance.adapter_registry import (
    DisqualificationReason,
    ModelProvider,
)


SCHEMA_VERSION = "1.0"
EVENT_SOURCE = "aura.model_assurance.scout"
EVENT_DETAIL_TYPE = "ModelCandidateDetected"


class EligibilityFlag(Enum):
    QUALIFIED = "qualified"
    REJECTED_NO_CAPABILITY = "rejected_no_capability"
    PENDING_AVAILABILITY = "pending_availability"
    ALREADY_KNOWN = "already_known"


@dataclass(frozen=True)
class ModelCandidateDetected:
    """One candidate-detected record.

    Frozen so the same instance can fan out to multiple sinks (EventBridge,
    local audit log, in-memory test buffer) without defensive copies.
    The ``schema_version`` field is the single point of compatibility
    contract — a change here is a contract change.
    """

    schema_version: str
    candidate_id: str            # vendor model ID, e.g. anthropic.claude-...
    display_name: str
    provider: ModelProvider
    partition: str               # "aws" or "aws-us-gov"
    detected_at: datetime
    eligibility: EligibilityFlag
    disqualification_reasons: tuple[DisqualificationReason, ...] = ()
    notes: str = ""

    def to_eventbridge_detail(self) -> dict:
        """Render for ``put_events`` ``Detail`` field (string-serialisable)."""
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "display_name": self.display_name,
            "provider": self.provider.value,
            "partition": self.partition,
            "detected_at": self.detected_at.isoformat(),
            "eligibility": self.eligibility.value,
            "disqualification_reasons": [
                r.value for r in self.disqualification_reasons
            ],
            "notes": self.notes,
        }


def make_event(
    *,
    candidate_id: str,
    display_name: str,
    provider: ModelProvider,
    partition: str,
    eligibility: EligibilityFlag,
    disqualification_reasons: tuple[DisqualificationReason, ...] = (),
    notes: str = "",
    detected_at: datetime | None = None,
) -> ModelCandidateDetected:
    return ModelCandidateDetected(
        schema_version=SCHEMA_VERSION,
        candidate_id=candidate_id,
        display_name=display_name,
        provider=provider,
        partition=partition,
        detected_at=detected_at or datetime.now(timezone.utc),
        eligibility=eligibility,
        disqualification_reasons=disqualification_reasons,
        notes=notes,
    )
