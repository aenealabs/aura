"""Project Aura - Deterministic Verification Envelope (DVE) data contracts.

ADR-085 Phase 1. Frozen dataclasses and enums shared across the
consensus engine, structural coverage gate (Phase 2), and formal
verification gate (Phase 3). Phase 1 only populates the consensus and
top-level result types; coverage/formal/traceability fields are
declared with default values so the Phase 1 result can be returned
even before later phases ship.

Frozen dataclasses are intentional: every DVE outcome is part of a
DO-178C audit trail, so accidentally mutating a result after
construction would compromise traceability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ConsensusOutcome(Enum):
    """N-of-M consensus result."""

    CONVERGED = "converged"
    DIVERGED = "diverged"
    PARTIAL = "partial"


class VerificationVerdict(Enum):
    """Formal verification outcome (Phase 3 will populate)."""

    PROVED = "proved"
    FAILED = "failed"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"


class DVEOverallVerdict(Enum):
    """Top-level verdict on a DVE pipeline execution."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    HITL_REQUIRED = "hitl_required"


# ---------------------------------------------------------------- Phase 1


@dataclass(frozen=True)
class ASTCanonicalForm:
    """Canonical AST representation used for consensus-equivalence comparison.

    Two outputs that produce the same ``canonical_hash`` are exact
    structural matches (variable renames and formatting differences
    have been normalised out). Used as the fast-path equivalence check;
    the slow path is embedding-cosine in :class:`SemanticEquivalenceChecker`.
    """

    source_hash: str  # SHA-256 of the original source string
    canonical_hash: str  # SHA-256 of the normalised ast.dump()
    canonical_dump: str  # ast.dump() of the normalised tree
    variable_count: int
    node_count: int
    parse_succeeded: bool = True
    parse_error: str | None = None


@dataclass(frozen=True)
class EquivalenceCheck:
    """Result of comparing two outputs for semantic equivalence."""

    are_equivalent: bool
    method: str  # "ast_exact" | "ast_dump" | "embedding_cosine" | "parse_fail"
    similarity: float  # 1.0 for exact AST match; cosine score otherwise
    rationale: str = ""


@dataclass(frozen=True)
class ConsensusResult:
    """Result of an N-of-M consensus generation round.

    ``selected_output`` is set to the centroid output when ``outcome
    == CONVERGED``. When ``DIVERGED``, ``selected_output`` is None and
    the orchestrator should escalate to HITL with all candidate outputs
    and the pairwise similarity matrix attached. ``PARTIAL`` is
    intermediate (used by callers that want to surface partial
    convergence without escalating immediately).
    """

    outcome: ConsensusOutcome
    n_generated: int
    m_required: int
    m_converged: int
    selected_output: str | None
    selection_method: str  # "ast_centroid" | "embedding_centroid" | "none"
    canonical_forms: tuple[ASTCanonicalForm, ...]
    pairwise_similarities: tuple[tuple[float, ...], ...]
    convergence_rate: float
    audit_record_id: str
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def needs_hitl(self) -> bool:
        return self.outcome == ConsensusOutcome.DIVERGED

    def to_audit_dict(self) -> dict:
        """Audit-trail-friendly dict (no raw source code, no embeddings)."""
        return {
            "audit_record_id": self.audit_record_id,
            "outcome": self.outcome.value,
            "n_generated": self.n_generated,
            "m_required": self.m_required,
            "m_converged": self.m_converged,
            "selection_method": self.selection_method,
            "convergence_rate": self.convergence_rate,
            "canonical_hashes": [c.canonical_hash for c in self.canonical_forms],
            "pairwise_similarities": [list(row) for row in self.pairwise_similarities],
            "computed_at": self.computed_at.isoformat(),
        }


# ----------------------------------------------------- Phase 2/3 placeholders


@dataclass(frozen=True)
class MCDCCoverageReport:
    """Structural coverage report (Phase 2)."""

    statement_coverage_pct: float = 0.0
    decision_coverage_pct: float = 0.0
    mcdc_coverage_pct: float = 0.0
    dal_policy_satisfied: bool = False
    coverage_tool: str = "uncomputed"
    report_s3_key: str | None = None
    uncovered_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerificationResult:
    """Formal verification outcome (Phase 3)."""

    verdict: VerificationVerdict = VerificationVerdict.SKIPPED
    axes_verified: tuple[str, ...] = ()
    proof_hash: str = ""
    solver_version: str = ""
    verification_time_ms: float = 0.0
    smt_formula_hash: str = ""
    counterexample: str | None = None


@dataclass(frozen=True)
class DVEResult:
    """Top-level DVE pipeline result.

    Phase 1 populates ``consensus`` and leaves the other fields at
    their default (skipped/zero) values. Phase 2 will populate
    ``structural_coverage``; Phase 3 will populate
    ``formal_verification``.
    """

    consensus: ConsensusResult
    overall_verdict: DVEOverallVerdict
    pipeline_latency_ms: float
    dal_level: str = "DEFAULT"
    audit_record_id: str = ""
    structural_coverage: MCDCCoverageReport = field(default_factory=MCDCCoverageReport)
    formal_verification: VerificationResult = field(default_factory=VerificationResult)
    rejection_reason: str | None = None
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
