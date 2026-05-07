"""Shadow Deployment Report generator (ADR-088 Phase 2.5).

Turns a :class:`PipelineResult` into a :class:`ShadowDeploymentReport`
ready for the HITL approval queue. The generator is a pure function
of its inputs — same pipeline result + same incumbent baseline
yields the same report bytes, so the integrity hash is reproducible.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from src.services.model_assurance.adapter_registry import (
    AdapterRegistry,
    ModelAdapter,
)
from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle import (
    JudgeResult,
    OracleEvaluation,
)
from src.services.model_assurance.pipeline.contracts import (
    PipelineResult,
    PipelineStage,
)
from src.services.model_assurance.report.contracts import (
    CostAnalysis,
    EdgeCaseSpotlight,
    HumanSpotCheckResult,
    ShadowDeploymentReport,
)


# Per ADR-088 §Stage 7: 10 best-improved + 10 most-degraded cases.
EDGE_CASE_LIMIT = 10


def _build_cost_analysis(
    candidate: ModelAdapter | None,
    incumbent: ModelAdapter | None,
    monthly_volume_mtok: float,
) -> CostAnalysis | None:
    if candidate is None or incumbent is None:
        return None
    return CostAnalysis(
        candidate_input_cost_per_mtok=candidate.cost_per_input_mtok,
        candidate_output_cost_per_mtok=candidate.cost_per_output_mtok,
        incumbent_input_cost_per_mtok=incumbent.cost_per_input_mtok,
        incumbent_output_cost_per_mtok=incumbent.cost_per_output_mtok,
        monthly_volume_mtok_estimate=monthly_volume_mtok,
    )


def _select_edge_cases(
    oracle: OracleEvaluation | None,
    incumbent_results: Sequence[JudgeResult] = (),
) -> tuple[EdgeCaseSpotlight, ...]:
    """Pick the most-improved and most-degraded cases vs incumbent.

    Without an incumbent comparison, we surface the candidate's worst
    failures (most useful signal for the operator). With an incumbent,
    we surface 10 cases where candidate beat incumbent and 10 where
    it lost.
    """
    if oracle is None:
        return ()

    # Build per-case pass/fail for candidate.
    candidate_per_case: dict[str, bool] = {}
    for r in oracle.judge_results:
        # If any judge fails for a case, the case overall fails.
        existing = candidate_per_case.get(r.case_id, True)
        candidate_per_case[r.case_id] = existing and r.passed

    incumbent_per_case: dict[str, bool] = {}
    for r in incumbent_results:
        existing = incumbent_per_case.get(r.case_id, True)
        incumbent_per_case[r.case_id] = existing and r.passed

    spotlights: list[EdgeCaseSpotlight] = []
    if incumbent_per_case:
        improved = []
        regressed = []
        for case_id, passed in candidate_per_case.items():
            inc_passed = incumbent_per_case.get(case_id)
            if inc_passed is None:
                continue
            if passed and not inc_passed:
                improved.append((case_id, inc_passed, passed))
            elif inc_passed and not passed:
                regressed.append((case_id, inc_passed, passed))
        for case_id, inc, cand in improved[:EDGE_CASE_LIMIT]:
            spotlights.append(EdgeCaseSpotlight(
                case_id=case_id,
                description="candidate improved on this case",
                candidate_passed=cand,
                incumbent_passed=inc,
                delta_label="improved",
            ))
        for case_id, inc, cand in regressed[:EDGE_CASE_LIMIT]:
            spotlights.append(EdgeCaseSpotlight(
                case_id=case_id,
                description="candidate regressed on this case",
                candidate_passed=cand,
                incumbent_passed=inc,
                delta_label="regressed",
            ))
    else:
        # No incumbent comparison — surface candidate's failures.
        failures = [
            cid for cid, passed in candidate_per_case.items() if not passed
        ]
        for case_id in failures[:EDGE_CASE_LIMIT]:
            spotlights.append(EdgeCaseSpotlight(
                case_id=case_id,
                description="candidate failed (no incumbent baseline)",
                candidate_passed=False,
                incumbent_passed=False,
                delta_label="regressed",
            ))
    return tuple(spotlights)


def _build_risk_notes(result: PipelineResult) -> tuple[str, ...]:
    notes: list[str] = []
    if result.provenance_record is not None:
        if not result.provenance_record.training_data_present:
            notes.append("training-data lineage missing from provenance")
        if (
            result.provenance_record.signature_status.value
            in ("unsigned", "signing_key_unknown", "signing_key_expired")
        ):
            notes.append(
                f"signature: {result.provenance_record.signature_status.value}"
            )
    if result.assurance_verdict is not None:
        notes.append(f"assurance verdict: {result.assurance_verdict.value}")
    sandbox_outcome = result.stage_outcome(PipelineStage.SANDBOX)
    if sandbox_outcome and not sandbox_outcome.succeeded:
        notes.append(
            f"sandbox stage anomaly: {sandbox_outcome.detail}"
        )
    return tuple(notes)


def _floor_violations(result: PipelineResult) -> tuple[str, ...]:
    if result.assurance_verdict is None:
        return ()
    if result.rejection_reason in ("floor_violation",):
        return (result.rejection_reason,)
    return ()


def generate_report(
    *,
    pipeline_result: PipelineResult,
    candidate_display_name: str,
    candidate_adapter: ModelAdapter | None = None,
    incumbent_adapter: ModelAdapter | None = None,
    monthly_volume_mtok_estimate: float = 0.0,
    incumbent_judge_results: Sequence[JudgeResult] = (),
    spot_check_samples: Sequence[HumanSpotCheckResult] = (),
) -> ShadowDeploymentReport:
    """Build the report from a pipeline run."""
    axis_scores: tuple[tuple[ModelAssuranceAxis, float], ...] = ()
    if pipeline_result.oracle_evaluation is not None:
        axis_scores = pipeline_result.oracle_evaluation.per_axis_scores

    return ShadowDeploymentReport(
        candidate_id=pipeline_result.candidate_id,
        candidate_display_name=candidate_display_name,
        incumbent_id=(
            incumbent_adapter.model_id if incumbent_adapter else None
        ),
        pipeline_decision=pipeline_result.decision.value,
        overall_utility=(
            sum(score for _, score in axis_scores) / max(len(axis_scores), 1)
        ),
        incumbent_utility=None,  # filled in if a comparable baseline is supplied
        floor_violations=_floor_violations(pipeline_result),
        axis_scores=axis_scores,
        cost_analysis=_build_cost_analysis(
            candidate_adapter, incumbent_adapter, monthly_volume_mtok_estimate,
        ),
        risk_notes=_build_risk_notes(pipeline_result),
        provenance_summary=(
            f"verdict={pipeline_result.provenance_record.verdict.value} "
            f"trust={pipeline_result.provenance_record.trust_score:.3f}"
            if pipeline_result.provenance_record
            else "no provenance record (pipeline halted before stage)"
        ),
        edge_cases=_select_edge_cases(
            pipeline_result.oracle_evaluation,
            incumbent_judge_results,
        ),
        spot_checks=tuple(spot_check_samples),
    )


def lookup_adapter(
    registry: AdapterRegistry, model_id: str
) -> ModelAdapter | None:
    """Convenience wrapper that swallows KeyError for unknown ids."""
    return registry.find(model_id)
