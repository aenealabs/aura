"""Pipeline orchestrator contracts (ADR-088 Phase 2.3).

The pipeline is the Step Functions state machine that takes a
ModelCandidateDetected event from the Scout Agent and runs it
through provenance → sandbox → oracle → CGE scoring → report →
HITL. Each stage produces a structured outcome that the next stage
inspects to decide whether to continue.

The orchestrator's verdict is consumed by the HITL approval queue
(Phase 2.5 Shadow Deployment Report); the pipeline never auto-
deploys a model swap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, Sequence

from src.services.model_assurance import ModelAssuranceVerdict
from src.services.model_assurance.adapter_registry import (
    DisqualificationReason,
    ModelRequirements,
)
from src.services.model_assurance.frozen_oracle import OracleEvaluation
from src.services.model_assurance.scout import ModelCandidateDetected
from src.services.supply_chain.model_provenance import (
    ModelArtifact,
    ModelProvenanceRecord,
    ProvenanceVerdict,
)


class PipelineStage(Enum):
    """Stages in the model-assurance state machine.

    Order is the deterministic execution order; the CloudFormation
    state machine builder uses these names verbatim as ASL state
    identifiers.
    """

    ADAPTER_DISQUALIFICATION = "adapter_disqualification"
    PROVENANCE = "provenance"
    SANDBOX = "sandbox"
    ORACLE = "oracle"
    CGE_SCORING = "cge_scoring"
    REPORT = "report"
    HITL_QUEUED = "hitl_queued"


class PipelineDecision(Enum):
    """Why the pipeline stopped (or completed).

    DISQUALIFIED  — Adapter Registry capability gate rejected.
    QUARANTINED   — Model Provenance Service quarantined the artifact.
    REJECTED      — Floor violation in CGE / Oracle. Hard fail; no
                    HITL queue (the floors already speak for the
                    operator).
    HITL_QUEUED   — Pipeline ran cleanly to completion; result is in
                    the HITL approval queue. This is the *only*
                    success exit — even a strong candidate awaits
                    human approval before deployment.
    INFRASTRUCTURE_ERROR
                  — A stage raised an unexpected exception. The
                    candidate is *not* sticky-rejected; the operator
                    can re-run.
    """

    DISQUALIFIED = "disqualified"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"
    HITL_QUEUED = "hitl_queued"
    INFRASTRUCTURE_ERROR = "infrastructure_error"


@dataclass(frozen=True)
class PipelineInput:
    """One pipeline invocation's input.

    Consolidates the artifacts the orchestrator needs across all
    stages so the Step Functions input is a single JSON object the
    state machine can pass between states without per-stage lookups.
    """

    candidate_event: ModelCandidateDetected
    artifact: ModelArtifact
    requirements: ModelRequirements
    candidate_outputs: Mapping[str, Sequence[object]]
    seed: int = 42  # holdout sampling seed
    incumbent_axis_scores: tuple[tuple[str, float], ...] = ()
    incumbent_id: str | None = None


@dataclass(frozen=True)
class StageOutcome:
    """Per-stage outcome record for the audit trail."""

    stage: PipelineStage
    succeeded: bool
    started_at: datetime
    completed_at: datetime
    detail: str = ""
    error_type: str | None = None

    @property
    def duration_ms(self) -> float:
        return (
            self.completed_at - self.started_at
        ).total_seconds() * 1000.0

    def to_audit_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "succeeded": self.succeeded,
            "duration_ms": round(self.duration_ms, 3),
            "detail": self.detail,
            "error_type": self.error_type,
        }


@dataclass(frozen=True)
class PipelineResult:
    """Aggregate result of one pipeline run."""

    candidate_id: str
    decision: PipelineDecision
    stages: tuple[StageOutcome, ...]
    disqualification_reasons: tuple[DisqualificationReason, ...] = ()
    provenance_record: ModelProvenanceRecord | None = None
    oracle_evaluation: OracleEvaluation | None = None
    assurance_verdict: ModelAssuranceVerdict | None = None
    rejection_reason: str | None = None
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def total_duration_ms(self) -> float:
        return (
            self.completed_at - self.started_at
        ).total_seconds() * 1000.0

    def stage_outcome(self, stage: PipelineStage) -> StageOutcome | None:
        for s in self.stages:
            if s.stage is stage:
                return s
        return None

    def to_audit_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "decision": self.decision.value,
            "rejection_reason": self.rejection_reason,
            "total_duration_ms": round(self.total_duration_ms, 3),
            "stages": [s.to_audit_dict() for s in self.stages],
            "disqualification_reasons": [
                r.value for r in self.disqualification_reasons
            ],
            "provenance": (
                self.provenance_record.to_audit_dict()
                if self.provenance_record
                else None
            ),
            "oracle": (
                self.oracle_evaluation.to_audit_dict()
                if self.oracle_evaluation
                else None
            ),
            "assurance_verdict": (
                self.assurance_verdict.value
                if self.assurance_verdict
                else None
            ),
        }
