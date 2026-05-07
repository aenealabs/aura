"""
Project Aura - Campaign Manager Data Contracts.

Typed data structures referenced by every other module. The shapes
here are intentionally aligned with the schemas in ADR-089
(CampaignDefinition, CampaignState, PhaseCheckpoint,
ArtifactManifest); the in-memory stores and the future DynamoDB-backed
stores both serialize against these contracts.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Optional


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class CampaignType(enum.Enum):
    """The catalogue of campaign types defined in ADR-089.

    The campaign manager's behaviour (required quorum, default cost cap
    floor, mandatory milestones) is driven off this enum, so adding a
    new type is a deliberate review-time decision.
    """

    COMPLIANCE_HARDENING = "compliance_hardening"
    VULNERABILITY_REMEDIATION = "vulnerability_remediation"
    CROSS_REPO_CHAIN_ANALYSIS = "cross_repo_chain_analysis"
    CONTINUOUS_THREAT_HUNTING = "continuous_threat_hunting"
    MYTHOS_EXPLOIT_REFINEMENT = "mythos_exploit_refinement"
    SELF_PLAY_SECURITY_TRAINING = "self_play_security_training"


# Campaign types that mutate code at scale and therefore require
# two-person rule (D8). Approver quorum is enforced server-side; the
# creator cannot approve their own campaign's milestones.
HIGH_IMPACT_CAMPAIGN_TYPES: frozenset[CampaignType] = frozenset(
    {
        CampaignType.COMPLIANCE_HARDENING,
        CampaignType.MYTHOS_EXPLOIT_REFINEMENT,
    }
)


class CampaignStatus(enum.Enum):
    """Lifecycle status of a campaign instance."""

    CREATED = "created"
    RUNNING = "running"
    AWAITING_HITL = "awaiting_hitl"
    HALTED_AT_CAP = "halted_at_cap"
    HALTED_AT_ANOMALY = "halted_at_anomaly"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in {
            CampaignStatus.COMPLETED,
            CampaignStatus.CANCELLED,
            CampaignStatus.FAILED,
        }

    @property
    def is_active(self) -> bool:
        """A campaign that is consuming budget right now."""
        return self == CampaignStatus.RUNNING

    @property
    def can_resume(self) -> bool:
        return self in {
            CampaignStatus.PAUSED,
            CampaignStatus.HALTED_AT_CAP,
            CampaignStatus.HALTED_AT_ANOMALY,
            CampaignStatus.AWAITING_HITL,
        }


class CampaignOutcome(enum.Enum):
    """Terminal outcomes recorded against completed campaigns."""

    SUCCESS = "success"
    HALTED_AT_CAP = "halted_at_cap"
    HALTED_AT_ANOMALY = "halted_at_anomaly"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PhaseOutcome(enum.Enum):
    """Outcome of a single phase execution."""

    COMPLETED = "completed"
    HITL_PENDING = "hitl_pending"
    DRIFT_DETECTED = "drift_detected"
    COST_CAP_REACHED = "cost_cap_reached"
    ANOMALY = "anomaly"
    FAILED = "failed"


# -----------------------------------------------------------------------------
# Phase identity
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class CampaignPhase:
    """A named phase in a campaign type's static state graph.

    Phases are defined once per campaign type at code level. The
    ``order`` field lets the orchestrator render phase-progress
    heatmaps.
    """

    phase_id: str  # stable identifier within the campaign type
    label: str  # human-readable
    order: int  # 0-indexed position in the phase graph
    is_milestone: bool = False  # True => HITL approval required after this phase
    is_high_consequence: bool = False  # True => constitutional-AI critique runs
    estimated_cost_usd: float = 0.0  # for burn-rate alarming


# -----------------------------------------------------------------------------
# Artifact contract (from ADR-089 "Audit-Grade Artifact Contract")
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolInvocation:
    """A single tool call recorded in the artifact manifest."""

    tool_name: str
    arguments_hash: str  # SHA-256 of canonicalised arguments
    duration_ms: int
    outcome: str  # "success" | "failure" | "skipped"


@dataclass(frozen=True)
class ArtifactManifest:
    """Audit-grade manifest for a campaign artifact.

    Storage requirement: backing object is content-addressed
    (SHA-256 in S3 key); manifest is KMS-signed; bucket has Object
    Lock compliance mode with retention matching the tenant's
    compliance profile.
    """

    artifact_id: str  # SHA-256 of content
    s3_object_key: str  # content-addressed
    campaign_id: str
    phase_id: str
    tenant_id: str
    parent_artifact_hashes: tuple[str, ...] = ()  # chain-of-custody
    timestamp_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    producing_principal_arn: str = ""
    model_id: str = ""
    model_version: str = ""
    prompt_hash: str = ""
    tool_invocations: tuple[ToolInvocation, ...] = ()
    seed: Optional[int] = None
    temperature: float = 0.0
    context_window_snapshot_ref: str = ""
    is_negative: bool = False  # True => rejected output captured for audit
    rejection_reason: str = ""
    kms_signature: str = ""  # populated by the artifact writer

    @property
    def has_signature(self) -> bool:
        return bool(self.kms_signature)


@dataclass(frozen=True)
class ArtifactRef:
    """Lightweight pointer to an artifact (avoids inlining large content).

    Phase checkpoints reference artifacts by manifest hash; the orchestrator
    fetches manifests from the artifact catalog only when needed.
    """

    artifact_id: str
    manifest_s3_key: str
    is_quarantined: bool = False  # True => Mythos PoC, separate bucket+CMK


# -----------------------------------------------------------------------------
# Campaign definition (immutable input)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class CampaignDefinition:
    """Immutable definition of a campaign.

    Created via the API; never mutated after creation. The
    ``definition_signature`` is a KMS-signed hash of the canonical
    serialization; orchestrators verify it on every checkpoint load
    (mitigation for T1 in the ADR).
    """

    campaign_id: str
    tenant_id: str
    campaign_type: CampaignType
    target: dict[str, Any]  # JSON-Schema-validated per campaign_type
    success_criteria: dict[str, Any]
    cost_cap_usd: float
    wall_clock_budget_hours: float
    autonomy_policy_id: str  # ADR-032 policy reference
    hitl_milestones: tuple[str, ...]  # phase_ids requiring approval
    approver_quorum: int  # minimum approvers per milestone
    creator_principal_arn: str  # for separation-of-duties
    definition_signature: str = ""  # KMS-signed hash; "" until signing wired
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# -----------------------------------------------------------------------------
# Campaign state (mutable runtime state, persisted at phase boundaries)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class CostSnapshot:
    """Per-tier cost snapshot for a campaign at a point in time."""

    standard_cost_usd: float = 0.0
    advanced_cost_usd: float = 0.0
    sandbox_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    cleanup_reservation_usd: float = 0.0
    in_cleanup_mode: bool = False


@dataclass(frozen=True)
class ClockSnapshot:
    """Wall-clock accounting using monotonic deltas (per agent feedback).

    Total seconds is the sum of monotonic per-phase deltas, never the
    difference between started_at and now (which would silently
    accumulate clock drift across resume).
    """

    total_seconds: int = 0
    phases_completed: int = 0


@dataclass(frozen=True)
class CompletedPhaseRef:
    """Pointer to a completed phase's checkpoint in S3."""

    phase_id: str
    checkpoint_s3_key: str
    outcome: PhaseOutcome
    duration_seconds: int


@dataclass(frozen=True)
class HitlMilestone:
    """A milestone awaiting HITL approval."""

    milestone_id: str
    phase_id: str
    requested_at: datetime
    approver_quorum: int
    approvals: tuple[str, ...] = ()  # principal_arns of approvers so far
    sfn_task_token: str = ""  # for waitForTaskToken callback


@dataclass(frozen=True)
class CampaignState:
    """Mutable runtime state of a campaign.

    Stored under PK ``tenant_id#campaign_id`` in DynamoDB. Updates are
    via conditional writes keyed by ``version`` to prevent lost
    updates from concurrent state mutations (e.g. orchestrator
    progress + HITL approval racing).
    """

    campaign_id: str
    tenant_id: str
    status: CampaignStatus
    current_phase_id: Optional[str]
    phase_history: tuple[CompletedPhaseRef, ...] = ()
    cost: CostSnapshot = field(default_factory=CostSnapshot)
    clock: ClockSnapshot = field(default_factory=ClockSnapshot)
    pending_hitl_approval: Optional[HitlMilestone] = None
    artifacts: tuple[ArtifactRef, ...] = ()
    last_checkpoint_s3_key: Optional[str] = None
    sfn_execution_arn: str = ""
    drift_score: float = 0.0  # rolling, [0, 1]
    cap_raises: int = 0  # count of approved cap raises
    version: int = 0  # for optimistic concurrency control
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def with_status(self, new_status: CampaignStatus) -> "CampaignState":
        """Return a copy with the new status and bumped version."""
        return replace(
            self,
            status=new_status,
            version=self.version + 1,
            updated_at=datetime.now(timezone.utc),
        )

    def with_phase(self, phase_id: Optional[str]) -> "CampaignState":
        """Return a copy advanced to a new current phase."""
        return replace(
            self,
            current_phase_id=phase_id,
            version=self.version + 1,
            updated_at=datetime.now(timezone.utc),
        )

    def with_cost(self, cost: CostSnapshot) -> "CampaignState":
        return replace(
            self,
            cost=cost,
            version=self.version + 1,
            updated_at=datetime.now(timezone.utc),
        )

    def with_pending_hitl(
        self, milestone: Optional[HitlMilestone]
    ) -> "CampaignState":
        return replace(
            self,
            pending_hitl_approval=milestone,
            status=(
                CampaignStatus.AWAITING_HITL if milestone else self.status
            ),
            version=self.version + 1,
            updated_at=datetime.now(timezone.utc),
        )


# -----------------------------------------------------------------------------
# Phase checkpoint (the minimum-viable payload from ADR-089 §Memory Strategy)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class TitanReceipt:
    """Receipt for a Titan memory write at phase exit."""

    write_id: str
    namespace: str  # always "campaign:{campaign_id}" per ADR
    bytes_written: int


@dataclass(frozen=True)
class SuccessCriteriaProgress:
    """Per-criterion progress vector, [0, 1]."""

    criterion_id: str
    progress: float  # 0.0 means not started, 1.0 means complete

    def __post_init__(self) -> None:
        if not 0.0 <= self.progress <= 1.0:
            raise ValueError(
                f"progress must be in [0,1]; got {self.progress!r}"
            )


@dataclass(frozen=True)
class PhaseCheckpoint:
    """Minimum viable checkpoint persisted at phase exit.

    Reasoning traces are NOT in here — they go to S3 for forensics.
    Forcing this information bottleneck prevents drift accumulation
    across phases (per agent feedback / ADR §Memory Strategy).
    """

    campaign_id: str
    phase_id: str
    artifact_manifest: tuple[ArtifactRef, ...]
    success_criteria_progress: tuple[SuccessCriteriaProgress, ...]
    phase_summary: str  # 2-4K tokens, deterministic critic prompt
    titan_receipt: Optional[TitanReceipt] = None
    cost_counters: CostSnapshot = field(default_factory=CostSnapshot)
    wall_clock_counters: ClockSnapshot = field(default_factory=ClockSnapshot)
    operation_ledger_cursor: str = ""
    kms_signature: str = ""  # signed for tamper detection on resume
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# -----------------------------------------------------------------------------
# Operation ledger (D2 - idempotency contract)
# -----------------------------------------------------------------------------


class OperationStatus(enum.Enum):
    CLAIMED = "claimed"  # claim succeeded; caller may execute
    ALREADY_EXECUTED = "already_executed"  # prior outcome attached


@dataclass(frozen=True)
class OperationOutcome:
    """Outcome of a single recorded operation in the ledger."""

    success: bool
    summary: str  # short human-readable
    payload_ref: str = ""  # S3 key for full payload if any
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class OperationClaim:
    """Result of attempting to claim an operation key."""

    status: OperationStatus
    prior_outcome: Optional[OperationOutcome] = None
