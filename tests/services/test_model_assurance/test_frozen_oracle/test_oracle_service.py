"""End-to-end tests for the OracleService (ADR-088 Phase 2.2)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle import (
    ASTDiffJudge,
    CompileTestCandidateOutput,
    CompileTestJudge,
    DOMAIN_MINIMUMS,
    DEFAULT_HOLDOUT_RATE,
    GoldenSetIntegrityError,
    GoldenTestCase,
    GoldenTestSet,
    JudgeRegistry,
    OracleService,
    PatchCandidateOutput,
    StaticAnalysisCandidateOutput,
    StaticAnalysisJudge,
    TestCaseDomain,
)


def _patch_case(case_id: str, reference: str = "def f(): return 1") -> GoldenTestCase:
    return GoldenTestCase(
        case_id=case_id,
        domain=TestCaseDomain.PATCH_CORRECTNESS,
        title=case_id,
        description="d",
        axes=(
            ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS,
            ModelAssuranceAxis.PATCH_SECURITY_EQUIVALENCE,
        ),
        expected=(("reference_source", reference),),
    )


def _full_set() -> GoldenTestSet:
    """Build a 400-case set with PATCH_CORRECTNESS cases filled with patch payloads."""
    cases: list[GoldenTestCase] = []
    # 100 patch cases
    for i in range(100):
        cases.append(_patch_case(f"patch-{i:04d}"))
    # remaining 300 are filler in the other domains
    fillers = {
        TestCaseDomain.VULNERABILITY_DETECTION: (
            ModelAssuranceAxis.VULNERABILITY_DETECTION_RECALL, 150,
        ),
        TestCaseDomain.FALSE_POSITIVE: (
            ModelAssuranceAxis.GUARDRAIL_COMPLIANCE, 100,
        ),
        TestCaseDomain.REGRESSION: (
            ModelAssuranceAxis.CODE_COMPREHENSION, 50,
        ),
    }
    for domain, (axis, n) in fillers.items():
        for i in range(n):
            cases.append(GoldenTestCase(
                case_id=f"{domain.value}-{i:04d}",
                domain=domain,
                title="t", description="d",
                axes=(axis,),
            ))
    return GoldenTestSet(cases=tuple(cases), version="0.1")


# ----------------------------------------------------- construction


class TestConstruction:
    def test_invalid_set_blocks_construction(self) -> None:
        # Set far below 400-case minimum
        cases = (_patch_case("c1"),)
        s = GoldenTestSet(cases=cases)
        with pytest.raises(GoldenSetIntegrityError):
            OracleService(golden_set=s, judges=JudgeRegistry())

    def test_default_holdout_rate(self) -> None:
        s = _full_set()
        svc = OracleService(golden_set=s, judges=JudgeRegistry())
        # Default = ADR-088 §Stage 6 (20%)
        assert DEFAULT_HOLDOUT_RATE == 0.20
        assert svc.golden_set is s


# ----------------------------------------------------- evaluation


class TestEvaluation:
    def test_no_judges_no_axis_scores(self) -> None:
        s = _full_set()
        svc = OracleService(golden_set=s, judges=JudgeRegistry(), holdout_rate=0.0)
        result = svc.evaluate(
            candidate_id="c1",
            candidate_outputs={},
            seed=1,
        )
        assert result.cases_evaluated == len(s)
        assert result.cases_passed == len(s)  # no judges → all "pass"
        assert all(score == 0.0 for ax, score in result.per_axis_scores)

    def test_ast_judge_against_perfect_candidate(self) -> None:
        s = _full_set()
        registry = JudgeRegistry()
        registry.register(ASTDiffJudge())
        svc = OracleService(golden_set=s, judges=registry, holdout_rate=0.0)

        # Build candidate outputs that exactly mirror the references.
        candidate_outputs = {
            "ast_diff_v1": [
                PatchCandidateOutput(
                    case_id=f"patch-{i:04d}",
                    patched_source="def f(): return 1",
                )
                for i in range(100)
            ],
        }
        result = svc.evaluate(
            candidate_id="c1",
            candidate_outputs=candidate_outputs,
            seed=1,
        )
        # PATCH_FUNCTIONAL_CORRECTNESS axis should be 1.0 averaged across
        # the 100 patch cases. Other axes have 0 contributions.
        per_axis = result.per_axis_dict
        assert per_axis[
            ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS
        ] == 1.0

    def test_failed_judge_drops_axis_average(self) -> None:
        s = _full_set()
        registry = JudgeRegistry()
        registry.register(ASTDiffJudge())
        svc = OracleService(golden_set=s, judges=registry, holdout_rate=0.0)

        # Half perfect, half wrong.
        outputs = []
        for i in range(100):
            source = "def f(): return 1" if i < 50 else "def f(): return 999"
            outputs.append(PatchCandidateOutput(
                case_id=f"patch-{i:04d}", patched_source=source,
            ))
        result = svc.evaluate(
            candidate_id="c1",
            candidate_outputs={"ast_diff_v1": outputs},
            seed=1,
        )
        per_axis = result.per_axis_dict
        # 50 of 100 patch cases pass; pass-rate = 0.5
        assert per_axis[
            ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS
        ] == 0.5

    def test_missing_candidate_output_treated_as_fail(self) -> None:
        s = _full_set()
        registry = JudgeRegistry()
        registry.register(ASTDiffJudge())
        svc = OracleService(golden_set=s, judges=registry, holdout_rate=0.0)
        # Candidate failed to produce ANY outputs for ast_diff_v1.
        result = svc.evaluate(
            candidate_id="c1",
            candidate_outputs={"ast_diff_v1": []},
            seed=1,
        )
        # All cases should fail for that judge — but no axis_scores
        # since the missing-output result records no axis contributions.
        per_axis = result.per_axis_dict
        # No contributions → 0.0 average for all axes.
        assert per_axis[
            ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS
        ] == 0.0


class TestHoldoutBehaviour:
    def test_holdout_excluded_from_scoring(self) -> None:
        s = _full_set()
        registry = JudgeRegistry()
        registry.register(ASTDiffJudge())
        svc = OracleService(golden_set=s, judges=registry, holdout_rate=0.20)

        outputs = [
            PatchCandidateOutput(
                case_id=f"patch-{i:04d}",
                patched_source="def f(): return 1",
            )
            for i in range(100)
        ]
        result = svc.evaluate(
            candidate_id="c",
            candidate_outputs={"ast_diff_v1": outputs},
            seed=42,
        )
        # 20% of 400 ≈ 80 held back
        assert 70 <= len(result.holdout_cases) <= 90
        assert result.cases_evaluated == 400 - len(result.holdout_cases)

    def test_holdout_deterministic_in_seed(self) -> None:
        s = _full_set()
        svc = OracleService(
            golden_set=s, judges=JudgeRegistry(), holdout_rate=0.20,
        )
        a = svc.evaluate(candidate_id="c", candidate_outputs={}, seed=42)
        b = svc.evaluate(candidate_id="c", candidate_outputs={}, seed=42)
        assert a.holdout_cases == b.holdout_cases


class TestMultipleJudges:
    def test_independent_axis_scores(self) -> None:
        """ASTDiff feeds MA3, StaticAnalysis feeds MA4 — both should fill in."""
        s = _full_set()
        registry = JudgeRegistry()
        registry.register(ASTDiffJudge())
        registry.register(StaticAnalysisJudge())
        svc = OracleService(golden_set=s, judges=registry, holdout_rate=0.0)

        ast_outputs = [
            PatchCandidateOutput(
                case_id=f"patch-{i:04d}",
                patched_source="def f(): return 1",
            )
            for i in range(100)
        ]
        sa_outputs = [
            StaticAnalysisCandidateOutput(
                case_id=f"patch-{i:04d}",
                before_findings=(("HIGH", 1),),
                after_findings=(("HIGH", 1),),
            )
            for i in range(100)
        ]
        result = svc.evaluate(
            candidate_id="c",
            candidate_outputs={
                "ast_diff_v1": ast_outputs,
                "static_analysis_v1": sa_outputs,
            },
            seed=1,
        )
        per_axis = result.per_axis_dict
        assert per_axis[
            ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS
        ] == 1.0
        assert per_axis[
            ModelAssuranceAxis.PATCH_SECURITY_EQUIVALENCE
        ] == 1.0
