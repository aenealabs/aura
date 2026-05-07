"""
Project Aura - Constraint Geometry Engine Contracts

Core types, enums, and immutable dataclasses for the deterministic
Constraint Geometry Engine (CGE). All result types are frozen to
guarantee deterministic behavior throughout the scoring pipeline.

Implements ADR-081: Deterministic Cortical Discrimination Layer.

7-Axis Constraint Space:
- C1: Syntactic Validity
- C2: Semantic Correctness
- C3: Security Policy (NIST 800-53)
- C4: Operational Bounds
- C5: Domain Compliance
- C6: Provenance Trust
- C7: Temporal Validity

Author: Project Aura Team
Created: 2026-02-11
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# =============================================================================
# Enums
# =============================================================================


class ConstraintAxis(Enum):
    """The 7 constraint dimensions of the CGE.

    Each axis represents a distinct measurement dimension. Agent outputs
    are scored against constraints on each axis independently, then
    aggregated into a composite Constraint Coherence Score (CCS).
    """

    SYNTACTIC_VALIDITY = "C1"
    SEMANTIC_CORRECTNESS = "C2"
    SECURITY_POLICY = "C3"
    OPERATIONAL_BOUNDS = "C4"
    DOMAIN_COMPLIANCE = "C5"
    PROVENANCE_TRUST = "C6"
    TEMPORAL_VALIDITY = "C7"

    @property
    def display_name(self) -> str:
        """Human-readable axis name."""
        return {
            "C1": "Syntactic Validity",
            "C2": "Semantic Correctness",
            "C3": "Security Policy",
            "C4": "Operational Bounds",
            "C5": "Domain Compliance",
            "C6": "Provenance Trust",
            "C7": "Temporal Validity",
        }[self.value]


class CoherenceAction(Enum):
    """Deterministic action based on CCS thresholds.

    Actions are ordered by severity. The CGE selects exactly one action
    per assessment based on deterministic threshold comparison.
    """

    AUTO_EXECUTE = "auto_execute"
    HUMAN_REVIEW = "human_review"
    ESCALATE = "escalate"
    REJECT = "reject"


class ConstraintEdgeType(Enum):
    """Types of relationships between constraint rules in the Neptune graph."""

    CONTAINS = "CONTAINS"  # ConstraintAxis -> ConstraintRule
    RELAXES = "RELAXES"  # Rule -> Rule (with conditions)
    TIGHTENS = "TIGHTENS"  # Rule -> Rule (with conditions)
    SUPERSEDES = "SUPERSEDES"  # Rule -> Rule (priority override)
    REQUIRES = "REQUIRES"  # Rule -> Rule (prerequisite)
    WEIGHTED_BY = "WEIGHTED_BY"  # PolicyProfile -> Rule (weight)


class PolicyConstraintType(Enum):
    """Mandatory policy invariants imposed beyond per-axis weighting.

    Policy constraints are non-negotiable. Unlike axis weights — which
    let a low score on one dimension be masked by high scores on
    others — a violated policy constraint forces the action to REJECT
    regardless of the composite CCS. Used by ADR-085 DAL A/B profiles
    to require MC/DC coverage and formal verification on every
    auto-executable output.
    """

    MCDC_COVERAGE_REQUIRED = "mcdc_coverage_required"
    DECISION_COVERAGE_REQUIRED = "decision_coverage_required"
    STATEMENT_COVERAGE_REQUIRED = "statement_coverage_required"
    FORMAL_PROOF_REQUIRED = "formal_proof_required"
    OBJECT_CODE_VERIFICATION_REQUIRED = "object_code_verification_required"
    REQUIREMENTS_TRACEABILITY_REQUIRED = "requirements_traceability_required"


class RegressionFloorComparisonMode(Enum):
    """How a regression floor's threshold is interpreted (ADR-088 Phase 1).

    ABSOLUTE              — candidate axis score must be >= threshold (in [0,1]).
    RELATIVE_TO_INCUMBENT — candidate axis score must be >= threshold *
                            incumbent score on the same axis (a 0.7
                            threshold means the candidate must retain
                            >=70% of the incumbent's score).
    """

    ABSOLUTE = "absolute"
    RELATIVE_TO_INCUMBENT = "relative_to_incumbent"


class RegressionFloorAction(Enum):
    """What happens when a regression floor is violated.

    REJECT          — the CoherenceResult action is forced to REJECT, the
                      violation is recorded in ``policy_constraint_violations``,
                      and the violation is also surfaced separately on the
                      result via ``regression_floor_violations``.
    QUARANTINE_FLAG — the violation is recorded but the action is NOT
                      auto-overridden; useful for soft floors during
                      initial profile calibration. Consumers (HITL UI,
                      audit dashboards) can choose to escalate.
    """

    REJECT = "reject"
    QUARANTINE_FLAG = "quarantine_and_flag"


# =============================================================================
# Constraint Data Types
# =============================================================================


@dataclass(frozen=True)
class ConstraintRule:
    """Immutable constraint rule with frozen embeddings.

    Each rule belongs to a single axis and carries pre-computed positive
    and negative centroids for deterministic cosine similarity measurement.
    Embeddings are frozen at constraint definition time.
    """

    rule_id: str
    axis: ConstraintAxis
    name: str
    description: str
    positive_centroid: tuple[float, ...]
    negative_centroid: tuple[float, ...]
    boundary_threshold: float
    weight: float = 1.0
    version: str = "1.0.0"
    effective_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: tuple[tuple[str, Any], ...] = ()

    @property
    def is_active(self) -> bool:
        """Check if rule is currently active based on temporal validity."""
        now = datetime.now(timezone.utc)
        if self.effective_at and now < self.effective_at:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        return True

    @property
    def metadata_dict(self) -> dict[str, Any]:
        """Convert frozen metadata to dict for serialization."""
        return dict(self.metadata)


@dataclass(frozen=True)
class ConstraintEdge:
    """Immutable edge between constraint rules in the Neptune graph."""

    source_id: str
    target_id: str
    edge_type: ConstraintEdgeType
    condition: str = ""
    weight: float = 1.0
    effective_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


@dataclass(frozen=True)
class ResolvedConstraintSet:
    """Result of constraint resolution from Neptune graph traversal.

    Groups resolved rules by axis and tracks the constraint graph version.
    """

    rules_by_axis: tuple[tuple[ConstraintAxis, tuple[ConstraintRule, ...]], ...]
    version: str
    profile_name: str
    resolved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    edges_traversed: int = 0

    def __post_init__(self) -> None:
        """Build O(1) lookup index for axis rules."""
        index = dict(self.rules_by_axis)
        object.__setattr__(self, "_axis_rules_index", index)

    def get_axis_rules(self, axis: ConstraintAxis) -> tuple[ConstraintRule, ...]:
        """Get all rules for a specific axis."""
        return self._axis_rules_index.get(axis, ())  # type: ignore[attr-defined]

    @property
    def total_rules(self) -> int:
        """Count total rules across all axes."""
        return sum(len(rules) for _, rules in self.rules_by_axis)

    @property
    def active_axes(self) -> tuple[ConstraintAxis, ...]:
        """Return axes that have at least one rule."""
        return tuple(ax for ax, rules in self.rules_by_axis if rules)


# =============================================================================
# Score Types
# =============================================================================


@dataclass(frozen=True)
class RuleCoherenceScore:
    """Coherence score for a single constraint rule."""

    rule_id: str
    rule_name: str
    positive_similarity: float
    negative_similarity: float
    coherence: float  # Normalized to [0.0, 1.0]
    weight: float


@dataclass(frozen=True)
class AxisCoherenceScore:
    """Coherence score for a single constraint axis.

    Uses weighted harmonic mean of rule coherences to penalize violations
    more heavily than arithmetic mean. If one rule scores 0.2 while others
    score 0.95, the harmonic mean drops significantly.
    """

    axis: ConstraintAxis
    score: float  # Weighted harmonic mean of rule coherences
    weight: float  # Axis weight from policy profile
    weighted_score: float  # score * weight (for composite calculation)
    contributing_rules: tuple[str, ...]
    rule_scores: tuple[RuleCoherenceScore, ...]

    @property
    def is_passing(self) -> bool:
        """Check if axis score exceeds minimum viability (> 0.0)."""
        return self.score > 0.0


@dataclass(frozen=True)
class PolicyConstraint:
    """A non-negotiable invariant a policy profile imposes (ADR-085 Phase 4).

    Distinct from :class:`ConstraintRule` — rules are evaluated by the
    coherence calculator and produce per-axis scores; policy
    constraints are evaluated *after* the CCS is computed and act as
    hard gates. Examples (DAL A profile):

        PolicyConstraint(
            constraint_id="dal-a-mcdc",
            type=PolicyConstraintType.MCDC_COVERAGE_REQUIRED,
            parameters=(("min_pct", 100.0),),
        )

    Parameters use a frozen tuple-of-tuples (rather than a dict) so
    the dataclass remains hashable for caching.
    """

    constraint_id: str
    name: str
    description: str
    type: PolicyConstraintType
    parameters: tuple[tuple[str, Any], ...] = ()

    @property
    def parameters_dict(self) -> dict[str, Any]:
        return dict(self.parameters)


@dataclass(frozen=True)
class RegressionFloor:
    """A per-axis hard floor evaluated before coherence scoring (ADR-088).

    Regression floors guard against subtle quality regressions that the
    aggregate CCS could otherwise mask: a candidate scoring 0.95 on
    five axes and 0.40 on the sixth still produces a high-looking
    composite, but if that sixth axis is a safety-critical dimension
    (e.g. vulnerability-detection recall) the candidate must be
    rejected outright. Floors short-circuit that compensation by
    forcing REJECT whenever any single axis dips below its threshold.

    Floors are domain-agnostic — the same primitive serves ADR-088
    model assurance, ADR-085 DO-178C structural coverage gates, or any
    future profile that needs hard per-axis minima.

    Floors are **immutable per evaluation run** because they are
    embedded in the frozen ``PolicyProfile``. Mid-run mutation is
    impossible by construction.

    Two comparison modes are supported (see :class:`RegressionFloorComparisonMode`):
    absolute scoring and relative-to-incumbent. Relative mode is
    meaningful only when an incumbent baseline is supplied to the
    evaluator; otherwise relative floors degrade to a "no incumbent —
    skip" outcome (see :func:`evaluate_floors` for details).
    """

    floor_id: str
    name: str
    description: str
    axis: ConstraintAxis
    threshold: float
    comparison: RegressionFloorComparisonMode = RegressionFloorComparisonMode.ABSOLUTE
    action: RegressionFloorAction = RegressionFloorAction.REJECT

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(
                f"RegressionFloor.threshold must be in [0.0, 1.0]; "
                f"got {self.threshold} for floor {self.floor_id!r}"
            )


@dataclass(frozen=True)
class RegressionFloorViolation:
    """Outcome record for a single floor evaluation."""

    floor_id: str
    axis: ConstraintAxis
    candidate_score: float
    threshold: float
    effective_threshold: float  # threshold after relative scaling
    incumbent_score: float | None  # populated only for RELATIVE comparisons
    comparison: RegressionFloorComparisonMode
    action: RegressionFloorAction

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "floor_id": self.floor_id,
            "axis": self.axis.value,
            "candidate_score": round(self.candidate_score, 6),
            "threshold": round(self.threshold, 6),
            "effective_threshold": round(self.effective_threshold, 6),
            "incumbent_score": (
                round(self.incumbent_score, 6)
                if self.incumbent_score is not None
                else None
            ),
            "comparison": self.comparison.value,
            "action": self.action.value,
        }


@dataclass(frozen=True)
class CoherenceResult:
    """Complete deterministic coherence assessment.

    This is the primary output of the CGE. It contains the composite score,
    per-axis breakdown, deterministic action, and full audit metadata.
    Same input + same constraints = same result, always.
    """

    composite_score: float  # Weighted geometric mean across axes [0.0, 1.0]
    axis_scores: tuple[AxisCoherenceScore, ...]
    action: CoherenceAction
    policy_profile: str
    constraint_version: str
    output_hash: str  # SHA-256 of normalized agent output
    computed_at: datetime
    computation_time_ms: float
    cache_hit: bool
    provenance_adjustment: float  # Trust score adjustment applied

    # ADR-085 Phase 4: policy-constraint violations forwarded by the DVE
    # pipeline. When non-empty, the action is forced to REJECT
    # regardless of composite_score. Each entry is a constraint_id
    # reference. The verification proof hash (when available) lets the
    # auditor correlate this CoherenceResult with the proof archive
    # entry generated by the formal-verification gate.
    policy_constraint_violations: tuple[str, ...] = ()
    formal_verification_proof_hash: str | None = None

    # ADR-088 Phase 1: regression floor violations evaluated before
    # coherence scoring. Floors with action=REJECT contribute their
    # floor_id to ``policy_constraint_violations`` so existing audit
    # consumers see them uniformly; this field carries the richer
    # detail (candidate vs threshold vs incumbent) for HITL reports.
    regression_floor_violations: tuple[RegressionFloorViolation, ...] = ()

    def __post_init__(self) -> None:
        """Build O(1) lookup index for axis scores."""
        index = {s.axis: s for s in self.axis_scores}
        object.__setattr__(self, "_axis_score_index", index)

    @property
    def is_auto_executable(self) -> bool:
        """Check if output can be auto-executed."""
        return self.action == CoherenceAction.AUTO_EXECUTE

    @property
    def needs_human(self) -> bool:
        """Check if human review is needed."""
        return self.action in (CoherenceAction.HUMAN_REVIEW, CoherenceAction.ESCALATE)

    @property
    def is_rejected(self) -> bool:
        """Check if output was rejected."""
        return self.action == CoherenceAction.REJECT

    def get_axis_score(self, axis: ConstraintAxis) -> Optional[AxisCoherenceScore]:
        """Get the score for a specific axis."""
        return self._axis_score_index.get(axis)  # type: ignore[attr-defined]

    def to_audit_dict(self) -> dict[str, Any]:
        """Convert to dictionary for audit logging (DynamoDB)."""
        return {
            "composite_score": round(self.composite_score, 6),
            "axis_scores": {
                s.axis.value: {
                    "score": round(s.score, 6),
                    "weight": round(s.weight, 6),
                    "weighted_score": round(s.weighted_score, 6),
                    "rules_evaluated": len(s.contributing_rules),
                }
                for s in self.axis_scores
            },
            "action": self.action.value,
            "policy_profile": self.policy_profile,
            "constraint_version": self.constraint_version,
            "output_hash": self.output_hash,
            "computed_at": self.computed_at.isoformat(),
            "computation_time_ms": round(self.computation_time_ms, 3),
            "cache_hit": self.cache_hit,
            "provenance_adjustment": round(self.provenance_adjustment, 6),
            "policy_constraint_violations": list(self.policy_constraint_violations),
            "formal_verification_proof_hash": self.formal_verification_proof_hash,
            "regression_floor_violations": [
                v.to_audit_dict() for v in self.regression_floor_violations
            ],
        }


# =============================================================================
# Input Types
# =============================================================================


@dataclass
class AgentOutput:
    """Agent output to be assessed by the CGE.

    This is the input to the CGE pipeline. It wraps the text output
    from the Constitutional AI revision step along with execution context.
    """

    text: str
    agent_id: str = ""
    task_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvenanceContext:
    """Provenance trust context from ADR-067.

    Trust scores dynamically adjust constraint weights and thresholds.
    """

    trust_score: float = 1.0  # [0.0, 1.0]
    source: str = ""
    verified: bool = False
    author: str = ""
    commit_signed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
