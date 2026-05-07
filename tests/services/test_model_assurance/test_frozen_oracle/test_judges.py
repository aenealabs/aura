"""Tests for the deterministic + LLM judges (ADR-088 Phase 2.2)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle import (
    ASTDiffJudge,
    CompileTestCandidateOutput,
    CompileTestJudge,
    GoldenTestCase,
    JudgeKind,
    JudgeRegistry,
    LLMJudge,
    LLMJudgeCandidateOutput,
    LLMJudgeRequest,
    LLMJudgeResponse,
    PatchCandidateOutput,
    SelfGradingError,
    StaticAnalysisCandidateOutput,
    StaticAnalysisJudge,
    TestCaseDomain,
    assert_no_self_grading,
)


def _patch_case(reference_source: str = "def f(): return 1") -> GoldenTestCase:
    return GoldenTestCase(
        case_id="patch-1",
        domain=TestCaseDomain.PATCH_CORRECTNESS,
        title="t",
        description="d",
        axes=(ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS,),
        expected=(("reference_source", reference_source),),
    )


# ----------------------------------------------------- AST diff judge


class TestASTDiffJudge:
    def test_equivalent_patches_pass(self) -> None:
        judge = ASTDiffJudge()
        case = _patch_case("def f(): return 1")
        # Same AST — different whitespace.
        cand = PatchCandidateOutput(
            case_id="patch-1",
            patched_source="def f():\n    return 1\n",
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is True
        assert result.confidence == 1.0
        assert result.judge_kind is JudgeKind.DETERMINISTIC

    def test_different_patches_fail(self) -> None:
        judge = ASTDiffJudge()
        case = _patch_case("def f(): return 1")
        cand = PatchCandidateOutput(
            case_id="patch-1",
            patched_source="def f(): return 2",
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is False

    def test_syntax_error_fails(self) -> None:
        judge = ASTDiffJudge()
        case = _patch_case()
        cand = PatchCandidateOutput(
            case_id="patch-1",
            patched_source="def f( syntax error",
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is False
        assert "did not parse" in result.reason

    def test_case_id_mismatch_fails(self) -> None:
        judge = ASTDiffJudge()
        case = _patch_case()
        cand = PatchCandidateOutput(
            case_id="other-id", patched_source="x = 1",
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is False
        assert "mismatch" in result.reason

    def test_missing_reference_fails(self) -> None:
        judge = ASTDiffJudge()
        case = GoldenTestCase(
            case_id="patch-1",
            domain=TestCaseDomain.PATCH_CORRECTNESS,
            title="t", description="d",
            axes=(ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS,),
        )
        cand = PatchCandidateOutput(case_id="patch-1", patched_source="x=1")
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is False
        assert "reference_source" in result.reason

    def test_pass_emits_axis_score(self) -> None:
        judge = ASTDiffJudge()
        case = _patch_case("def f(): return 1")
        cand = PatchCandidateOutput(
            case_id="patch-1",
            patched_source="def f(): return 1",
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.axis_scores_dict[
            ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS
        ] == 1.0


# ----------------------------------------------------- Static-analysis judge


class TestStaticAnalysisJudge:
    def test_no_new_findings_passes(self) -> None:
        judge = StaticAnalysisJudge()
        case = _patch_case()
        cand = StaticAnalysisCandidateOutput(
            case_id="patch-1",
            before_findings=(("HIGH", 2), ("MEDIUM", 5)),
            after_findings=(("HIGH", 2), ("MEDIUM", 4)),
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is True

    def test_new_finding_fails(self) -> None:
        judge = StaticAnalysisJudge()
        case = _patch_case()
        cand = StaticAnalysisCandidateOutput(
            case_id="patch-1",
            before_findings=(("HIGH", 0),),
            after_findings=(("HIGH", 1),),
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is False
        assert "HIGH" in result.reason

    def test_severity_only_in_after_counts_as_regression(self) -> None:
        judge = StaticAnalysisJudge()
        case = _patch_case()
        cand = StaticAnalysisCandidateOutput(
            case_id="patch-1",
            before_findings=(),
            after_findings=(("LOW", 3),),
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is False

    def test_pass_emits_security_axis_score(self) -> None:
        judge = StaticAnalysisJudge()
        case = _patch_case()
        cand = StaticAnalysisCandidateOutput(
            case_id="patch-1",
            before_findings=(("HIGH", 1),),
            after_findings=(("HIGH", 1),),
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.axis_scores_dict[
            ModelAssuranceAxis.PATCH_SECURITY_EQUIVALENCE
        ] == 1.0


# ----------------------------------------------------- Compile/test judge


class TestCompileTestJudge:
    def test_compile_and_pass(self) -> None:
        judge = CompileTestJudge()
        case = _patch_case()
        cand = CompileTestCandidateOutput(
            case_id="patch-1",
            compile_succeeded=True,
            tests_passed=True,
            tests_total=10,
        )
        assert judge.evaluate(case=case, candidate_output=cand).passed is True

    def test_compile_failure_fails(self) -> None:
        judge = CompileTestJudge()
        case = _patch_case()
        cand = CompileTestCandidateOutput(
            case_id="patch-1",
            compile_succeeded=False,
            tests_passed=False,
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is False
        assert "compile failed" in result.reason

    def test_test_failure_fails(self) -> None:
        judge = CompileTestJudge()
        case = _patch_case()
        cand = CompileTestCandidateOutput(
            case_id="patch-1",
            compile_succeeded=True,
            tests_passed=False,
            tests_failed_ids=("test_x", "test_y"),
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is False
        assert "test_x" in result.reason


# --------------------------------------------- LLM judge (self-grading)


class TestSelfGradingGuard:
    def test_assert_no_self_grading_passes(self) -> None:
        # No exception
        assert_no_self_grading(
            candidate_model_id="A",
            judge_model_id="B",
        )

    def test_assert_no_self_grading_rejects_match(self) -> None:
        with pytest.raises(SelfGradingError):
            assert_no_self_grading(
                candidate_model_id="X",
                judge_model_id="X",
            )

    def test_constructor_enforces_guard(self, candidate_model_id, judge_model_id) -> None:
        # candidate_model_id and judge_model_id come from the test conftest.
        # Constructor must NOT raise when the two differ.
        LLMJudge(
            judge_model_id=judge_model_id,
            candidate_model_id=candidate_model_id,
            invoke=lambda req: LLMJudgeResponse(passed=True, confidence=1.0),
        )

    def test_constructor_rejects_self_grading(self) -> None:
        with pytest.raises(SelfGradingError):
            LLMJudge(
                judge_model_id="same",
                candidate_model_id="same",
                invoke=lambda req: LLMJudgeResponse(passed=True, confidence=1.0),
            )


# --------------------------------------------- LLM judge behaviour


class TestLLMJudge:
    def _make_judge(
        self,
        invoke,
        candidate_model_id: str,
        judge_model_id: str,
    ) -> LLMJudge:
        return LLMJudge(
            judge_model_id=judge_model_id,
            candidate_model_id=candidate_model_id,
            invoke=invoke,
        )

    def test_passes_when_response_passes_with_confidence(
        self, candidate_model_id, judge_model_id
    ) -> None:
        invoke = lambda req: LLMJudgeResponse(passed=True, confidence=0.95)
        judge = self._make_judge(invoke, candidate_model_id, judge_model_id)
        case = _patch_case()
        cand = LLMJudgeCandidateOutput(
            case_id="patch-1", prompt="p", response="r",
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is True
        assert result.judge_kind is JudgeKind.LLM

    def test_low_confidence_demotes_to_fail(
        self, candidate_model_id, judge_model_id
    ) -> None:
        invoke = lambda req: LLMJudgeResponse(passed=True, confidence=0.3)
        judge = self._make_judge(invoke, candidate_model_id, judge_model_id)
        case = _patch_case()
        cand = LLMJudgeCandidateOutput(
            case_id="patch-1", prompt="p", response="r",
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is False
        assert "below floor" in result.reason

    def test_response_confidence_validation(self) -> None:
        with pytest.raises(ValueError):
            LLMJudgeResponse(passed=True, confidence=2.0)

    def test_case_id_mismatch_fails(
        self, candidate_model_id, judge_model_id
    ) -> None:
        invoke = lambda req: LLMJudgeResponse(passed=True, confidence=1.0)
        judge = self._make_judge(invoke, candidate_model_id, judge_model_id)
        case = _patch_case()
        cand = LLMJudgeCandidateOutput(
            case_id="other-case", prompt="p", response="r",
        )
        result = judge.evaluate(case=case, candidate_output=cand)
        assert result.passed is False


# ----------------------------------------------------- Registry


class TestJudgeRegistry:
    def test_register_and_get(self) -> None:
        r = JudgeRegistry()
        j = ASTDiffJudge()
        r.register(j)
        assert r.get(j.judge_id) is j

    def test_duplicate_register_rejected(self) -> None:
        r = JudgeRegistry()
        r.register(ASTDiffJudge())
        with pytest.raises(ValueError):
            r.register(ASTDiffJudge())

    def test_unregister_returns_judge(self) -> None:
        r = JudgeRegistry()
        j = ASTDiffJudge()
        r.register(j)
        assert r.unregister(j.judge_id) is j

    def test_kind_filters(self) -> None:
        r = JudgeRegistry()
        r.register(ASTDiffJudge())
        r.register(StaticAnalysisJudge())
        det = r.deterministic_judges()
        llm = r.llm_judges()
        assert len(det) == 2
        assert llm == ()

    def test_contains(self) -> None:
        r = JudgeRegistry()
        r.register(ASTDiffJudge())
        assert "ast_diff_v1" in r
        assert "missing" not in r
