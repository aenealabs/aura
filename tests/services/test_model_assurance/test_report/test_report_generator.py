"""Tests for the Shadow Deployment Report generator (ADR-088 Phase 2.5)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.services.model_assurance import (
    AdapterRegistry,
    ModelArchitecture,
    ModelProvider,
    TokenizerType,
)
from src.services.model_assurance.adapter_registry import ModelAdapter
from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle import (
    JudgeKind,
    JudgeResult,
    OracleEvaluation,
)
from src.services.model_assurance.pipeline.contracts import (
    PipelineDecision,
    PipelineResult,
    PipelineStage,
    StageOutcome,
)
from src.services.model_assurance.report import (
    EDGE_CASE_LIMIT,
    HumanSpotCheckResult,
    generate_report,
    lookup_adapter,
)
from src.services.supply_chain.model_provenance import (
    ModelArtifact,
    ModelLicense,
    ModelProvenanceRecord,
    ModelRegistry,
    ProvenanceVerdict,
    SignatureStatus,
)


def _adapter(model_id: str, in_cost: float, out_cost: float) -> ModelAdapter:
    return ModelAdapter(
        model_id=model_id,
        provider=ModelProvider.BEDROCK,
        display_name=model_id,
        max_context_tokens=200_000,
        supports_tool_use=True,
        supports_streaming=True,
        tokenizer_type=TokenizerType.CLAUDE,
        architecture=ModelArchitecture.DENSE,
        cost_per_input_mtok=in_cost,
        cost_per_output_mtok=out_cost,
        required_prompt_format="claude_messages_v1",
    )


def _judge_result(case_id: str, passed: bool) -> JudgeResult:
    return JudgeResult(
        case_id=case_id,
        judge_id="ast_diff_v1",
        judge_kind=JudgeKind.DETERMINISTIC,
        passed=passed,
        confidence=1.0,
    )


def _oracle(per_case: dict[str, bool]) -> OracleEvaluation:
    return OracleEvaluation(
        candidate_id="cand",
        judge_results=tuple(
            _judge_result(cid, p) for cid, p in per_case.items()
        ),
        per_axis_scores=(
            (ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS, 0.9),
        ),
        cases_evaluated=len(per_case),
        cases_passed=sum(1 for p in per_case.values() if p),
    )


def _provenance() -> ModelProvenanceRecord:
    art = ModelArtifact(
        model_id="cand",
        provider="anthropic",
        registry=ModelRegistry.BEDROCK,
        weights_digest="a" * 64,
        license=ModelLicense(spdx_id="Apache-2.0"),
    )
    return ModelProvenanceRecord(
        artifact=art,
        verdict=ProvenanceVerdict.APPROVED,
        signature_status=SignatureStatus.UNSIGNED,
        registry_allowlisted=True,
        license_acceptable=True,
        training_data_present=False,
        trust_score=0.9,
    )


def _pipeline_result(
    *,
    decision: PipelineDecision = PipelineDecision.HITL_QUEUED,
    oracle: OracleEvaluation | None = None,
    rejection_reason: str | None = None,
) -> PipelineResult:
    return PipelineResult(
        candidate_id="cand",
        decision=decision,
        stages=(
            StageOutcome(
                stage=PipelineStage.PROVENANCE,
                succeeded=True,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            ),
        ),
        provenance_record=_provenance(),
        oracle_evaluation=oracle,
        rejection_reason=rejection_reason,
    )


# ----------------------------------------------------- generation


class TestReportGeneration:
    def test_basic_fields_populated(self) -> None:
        result = _pipeline_result(
            oracle=_oracle({"c1": True, "c2": True, "c3": False}),
        )
        report = generate_report(
            pipeline_result=result,
            candidate_display_name="Candidate Sonnet",
        )
        assert report.candidate_id == "cand"
        assert report.candidate_display_name == "Candidate Sonnet"
        assert report.pipeline_decision == "hitl_queued"

    def test_axis_scores_passed_through(self) -> None:
        result = _pipeline_result(oracle=_oracle({"c1": True}))
        report = generate_report(
            pipeline_result=result, candidate_display_name="X",
        )
        d = report.axis_scores_dict
        assert d[ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS] == 0.9

    def test_no_oracle_no_axis_scores(self) -> None:
        result = _pipeline_result(oracle=None)
        report = generate_report(
            pipeline_result=result, candidate_display_name="X",
        )
        assert report.axis_scores == ()


class TestRiskNotes:
    def test_missing_training_data_noted(self) -> None:
        result = _pipeline_result(oracle=_oracle({"c1": True}))
        report = generate_report(
            pipeline_result=result, candidate_display_name="X",
        )
        assert any(
            "training-data" in note for note in report.risk_notes
        )

    def test_unsigned_signature_noted(self) -> None:
        result = _pipeline_result(oracle=_oracle({"c1": True}))
        report = generate_report(
            pipeline_result=result, candidate_display_name="X",
        )
        assert any("unsigned" in note for note in report.risk_notes)


class TestProvenanceSummary:
    def test_provenance_summary_present(self) -> None:
        result = _pipeline_result(oracle=_oracle({"c1": True}))
        report = generate_report(
            pipeline_result=result, candidate_display_name="X",
        )
        assert "approved" in report.provenance_summary
        assert "trust=" in report.provenance_summary

    def test_no_provenance_summary_for_early_halt(self) -> None:
        # Pipeline halted before provenance stage.
        result = PipelineResult(
            candidate_id="cand",
            decision=PipelineDecision.DISQUALIFIED,
            stages=(),
        )
        report = generate_report(
            pipeline_result=result, candidate_display_name="X",
        )
        assert "no provenance" in report.provenance_summary.lower()


class TestCostAnalysis:
    def test_cost_analysis_with_both_adapters(self) -> None:
        result = _pipeline_result(oracle=_oracle({"c1": True}))
        cand = _adapter("cand", 6.0, 30.0)
        inc = _adapter("inc", 3.0, 15.0)
        report = generate_report(
            pipeline_result=result,
            candidate_display_name="X",
            candidate_adapter=cand,
            incumbent_adapter=inc,
            monthly_volume_mtok_estimate=100.0,
        )
        assert report.cost_analysis is not None
        # Candidate is 2x more expensive: delta should be positive.
        assert report.cost_analysis.monthly_cost_delta > 0

    def test_no_cost_analysis_without_adapter(self) -> None:
        result = _pipeline_result(oracle=_oracle({"c1": True}))
        report = generate_report(
            pipeline_result=result, candidate_display_name="X",
        )
        assert report.cost_analysis is None


class TestEdgeCaseSpotlight:
    def test_no_edge_cases_without_oracle(self) -> None:
        result = _pipeline_result(oracle=None)
        report = generate_report(
            pipeline_result=result, candidate_display_name="X",
        )
        assert report.edge_cases == ()

    def test_failing_cases_surfaced_without_incumbent(self) -> None:
        per_case = {"c1": True, "c2": False, "c3": False}
        result = _pipeline_result(oracle=_oracle(per_case))
        report = generate_report(
            pipeline_result=result, candidate_display_name="X",
        )
        case_ids = {ec.case_id for ec in report.edge_cases}
        assert "c2" in case_ids
        assert "c3" in case_ids
        # Passing cases not surfaced when there's no incumbent comparison
        assert "c1" not in case_ids

    def test_improved_and_regressed_with_incumbent(self) -> None:
        per_case = {"c1": True, "c2": False, "c3": True}
        result = _pipeline_result(oracle=_oracle(per_case))
        # Incumbent passed c2 but failed c1
        incumbent_results = (
            _judge_result("c1", False),
            _judge_result("c2", True),
            _judge_result("c3", True),  # tied
        )
        report = generate_report(
            pipeline_result=result,
            candidate_display_name="X",
            incumbent_judge_results=incumbent_results,
        )
        labels = {ec.delta_label for ec in report.edge_cases}
        assert "improved" in labels
        assert "regressed" in labels

    def test_edge_case_limit_caps_output(self) -> None:
        # 30 failing cases, no incumbent
        per_case = {f"c{i:03d}": False for i in range(30)}
        result = _pipeline_result(oracle=_oracle(per_case))
        report = generate_report(
            pipeline_result=result, candidate_display_name="X",
        )
        assert len(report.edge_cases) == EDGE_CASE_LIMIT


class TestSpotChecks:
    def test_spot_check_results_passed_through(self) -> None:
        result = _pipeline_result(oracle=_oracle({"c1": True}))
        spot_checks = (
            HumanSpotCheckResult(
                case_id="c1", automated_pass=True, human_pass=True,
            ),
            HumanSpotCheckResult(
                case_id="c2", automated_pass=True, human_pass=False,
                notes="reviewer disagreed",
            ),
        )
        report = generate_report(
            pipeline_result=result,
            candidate_display_name="X",
            spot_check_samples=spot_checks,
        )
        assert len(report.spot_checks) == 2

    def test_human_disagreement_flag(self) -> None:
        result = _pipeline_result(oracle=_oracle({"c1": True}))
        spot_checks = (
            HumanSpotCheckResult(
                case_id="c1", automated_pass=True, human_pass=False,
            ),
        )
        report = generate_report(
            pipeline_result=result,
            candidate_display_name="X",
            spot_check_samples=spot_checks,
        )
        assert report.has_human_disagreement is True


class TestSerializable:
    def test_serializable_dict_has_all_top_level_keys(self) -> None:
        result = _pipeline_result(oracle=_oracle({"c1": True}))
        report = generate_report(
            pipeline_result=result, candidate_display_name="X",
        )
        d = report.to_serialisable_dict()
        for k in (
            "candidate_id", "candidate_display_name", "pipeline_decision",
            "overall_utility", "axis_scores", "risk_notes",
            "provenance_summary", "edge_cases", "spot_checks",
            "generated_at",
        ):
            assert k in d


class TestLookupAdapter:
    def test_existing_id_returns_adapter(self) -> None:
        registry = AdapterRegistry()
        a = lookup_adapter(
            registry, "anthropic.claude-3-5-sonnet-20240620-v1:0",
        )
        assert a is not None

    def test_missing_id_returns_none(self) -> None:
        assert lookup_adapter(AdapterRegistry(), "missing") is None
