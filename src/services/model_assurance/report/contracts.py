"""Shadow Deployment Report + Integrity Envelope contracts (ADR-088 Phase 2.5).

The Shadow Deployment Report is what the HITL approval queue
presents to a reviewer. It MUST be tamper-evident: a malicious or
buggy modification to the report content between generation and
display would let a regressed candidate slip past human review. The
:class:`IntegrityEnvelope` carries a frozen content hash so the
HITL UI can detect any mismatch.

The Evaluation Integrity Envelope is a separate, larger seal that
covers the *scoring criteria* themselves — benchmark suite version,
CGE axis definitions, floor thresholds, utility weights — so that
mid-run modification invalidates the evaluation. Same sealing
mechanism, different content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.services.model_assurance.axes import ModelAssuranceAxis


class ReportSection(Enum):
    """The seven sections of the Shadow Deployment Report.

    Order matches the rendering order in the HITL UI per ADR-088
    §Stage 7 table — Executive Summary first, edge-case spotlight
    just before spot-check results.
    """

    EXECUTIVE_SUMMARY = "executive_summary"
    FLOOR_VALIDATION = "floor_validation"
    AXIS_RADAR = "axis_radar"
    COST_ANALYSIS = "cost_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    PROVENANCE_CHAIN = "provenance_chain"
    EDGE_CASE_SPOTLIGHT = "edge_case_spotlight"
    HUMAN_SPOT_CHECK = "human_spot_check"


@dataclass(frozen=True)
class IntegrityEnvelope:
    """Tamper-evident wrapper around a JSON-serialisable payload.

    ``content_hash`` is the SHA-256 of the canonical-JSON encoding
    of ``payload``. Hash recomputation on receipt detects any
    modification — including reordering of dict keys, since we use
    sorted-keys canonicalisation. Frozen so an attacker can't
    overwrite the hash after construction.
    """

    payload_json: str       # canonical-JSON serialised payload
    content_hash: str       # SHA-256 hex of payload_json
    created_at: str         # ISO8601 UTC
    envelope_version: str = "1.0"
    signed_by: str = "aura.model_assurance.report"


@dataclass(frozen=True)
class CostAnalysis:
    """Cost delta between candidate and incumbent."""

    candidate_input_cost_per_mtok: float
    candidate_output_cost_per_mtok: float
    incumbent_input_cost_per_mtok: float
    incumbent_output_cost_per_mtok: float
    monthly_volume_mtok_estimate: float = 0.0

    @property
    def candidate_monthly_cost(self) -> float:
        # Assumes 50/50 input/output split for the volume estimate.
        v = self.monthly_volume_mtok_estimate
        return v * (
            (self.candidate_input_cost_per_mtok / 2.0)
            + (self.candidate_output_cost_per_mtok / 2.0)
        )

    @property
    def incumbent_monthly_cost(self) -> float:
        v = self.monthly_volume_mtok_estimate
        return v * (
            (self.incumbent_input_cost_per_mtok / 2.0)
            + (self.incumbent_output_cost_per_mtok / 2.0)
        )

    @property
    def monthly_cost_delta(self) -> float:
        return self.candidate_monthly_cost - self.incumbent_monthly_cost


@dataclass(frozen=True)
class EdgeCaseSpotlight:
    """One case highlighted in the spotlight section."""

    case_id: str
    description: str
    candidate_passed: bool
    incumbent_passed: bool
    delta_label: str           # "improved" / "regressed" / "tied"


@dataclass(frozen=True)
class HumanSpotCheckResult:
    """Result of one operator-driven spot-check sample.

    ADR-088 §Stage 6: 5% of shadow-deployment comparisons are
    sampled for human review before the approval UI presents
    aggregate scores. Disagreements between automated metrics and
    human judgement are surfaced prominently.
    """

    case_id: str
    automated_pass: bool
    human_pass: bool
    notes: str = ""

    @property
    def disagrees_with_automation(self) -> bool:
        return self.automated_pass != self.human_pass


@dataclass(frozen=True)
class ShadowDeploymentReport:
    """The full report. Generated from a PipelineResult."""

    candidate_id: str
    candidate_display_name: str
    incumbent_id: str | None
    pipeline_decision: str               # PipelineDecision.value
    overall_utility: float
    incumbent_utility: float | None
    floor_violations: tuple[str, ...] = ()
    axis_scores: tuple[tuple[ModelAssuranceAxis, float], ...] = ()
    cost_analysis: CostAnalysis | None = None
    risk_notes: tuple[str, ...] = ()
    provenance_summary: str = ""
    edge_cases: tuple[EdgeCaseSpotlight, ...] = ()
    spot_checks: tuple[HumanSpotCheckResult, ...] = ()
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def axis_scores_dict(self) -> dict[ModelAssuranceAxis, float]:
        return dict(self.axis_scores)

    @property
    def has_human_disagreement(self) -> bool:
        return any(s.disagrees_with_automation for s in self.spot_checks)

    def to_serialisable_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "candidate_display_name": self.candidate_display_name,
            "incumbent_id": self.incumbent_id,
            "pipeline_decision": self.pipeline_decision,
            "overall_utility": round(self.overall_utility, 6),
            "incumbent_utility": (
                round(self.incumbent_utility, 6)
                if self.incumbent_utility is not None
                else None
            ),
            "floor_violations": list(self.floor_violations),
            "axis_scores": {
                ax.value: round(score, 6) for ax, score in self.axis_scores
            },
            "cost_analysis": (
                {
                    "candidate_input_mtok": (
                        self.cost_analysis.candidate_input_cost_per_mtok
                    ),
                    "candidate_output_mtok": (
                        self.cost_analysis.candidate_output_cost_per_mtok
                    ),
                    "incumbent_input_mtok": (
                        self.cost_analysis.incumbent_input_cost_per_mtok
                    ),
                    "incumbent_output_mtok": (
                        self.cost_analysis.incumbent_output_cost_per_mtok
                    ),
                    "monthly_delta_estimate": round(
                        self.cost_analysis.monthly_cost_delta, 4
                    ),
                }
                if self.cost_analysis
                else None
            ),
            "risk_notes": list(self.risk_notes),
            "provenance_summary": self.provenance_summary,
            "edge_cases": [
                {
                    "case_id": ec.case_id,
                    "description": ec.description,
                    "candidate_passed": ec.candidate_passed,
                    "incumbent_passed": ec.incumbent_passed,
                    "delta_label": ec.delta_label,
                }
                for ec in self.edge_cases
            ],
            "spot_checks": [
                {
                    "case_id": s.case_id,
                    "automated_pass": s.automated_pass,
                    "human_pass": s.human_pass,
                    "notes": s.notes,
                    "disagrees": s.disagrees_with_automation,
                }
                for s in self.spot_checks
            ],
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass(frozen=True)
class EvaluationIntegrityEnvelope:
    """Sealed scoring criteria for one evaluation run.

    Per ADR-088 §Evaluation Integrity Envelope: the benchmark suite
    version, CGE axis definitions, floor thresholds, and utility
    weights are immutable per run. Sealed before the evaluation
    begins; any modification to the underlying values invalidates
    the seal at verify time.

    The seal is not a cryptographic signature — that lives at the
    storage layer (KMS-encrypted S3 with Object Lock). The hash
    here is a *content* check that catches in-memory mutation
    (e.g. monkey-patching a floor between stages) which would not
    show up in the storage layer.
    """

    benchmark_version: str
    axis_floors: tuple[tuple[str, float], ...]      # axis_id → threshold
    axis_weights: tuple[tuple[str, float], ...]     # axis_id → weight
    sealed_hash: str
    sealed_at: str
