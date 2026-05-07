"""Compile/test-run judge for functional correctness (ADR-088 Phase 2.2).

Takes pre-recorded compile + test outcomes from a sandbox run and
produces a pass/fail verdict for MA3 (Patch Functional Correctness).
The actual sandbox invocation happens in Phase 2.4; this judge
consumes the structured outcome.

Pass rule (deterministic):
    compile_succeeded AND tests_passed
"""

from __future__ import annotations

from dataclasses import dataclass

from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle.contracts import (
    GoldenTestCase,
    JudgeKind,
    JudgeResult,
)


@dataclass(frozen=True)
class CompileTestCandidateOutput:
    """Structured outcome produced by the sandbox harness."""

    case_id: str
    compile_succeeded: bool
    tests_passed: bool
    tests_total: int = 0
    tests_failed_ids: tuple[str, ...] = ()
    notes: str = ""


class CompileTestJudge:
    judge_kind = JudgeKind.DETERMINISTIC
    judge_id = "compile_test_v1"

    def evaluate(
        self,
        *,
        case: GoldenTestCase,
        candidate_output: CompileTestCandidateOutput,
    ) -> JudgeResult:
        if case.case_id != candidate_output.case_id:
            return JudgeResult(
                case_id=case.case_id,
                judge_id=self.judge_id,
                judge_kind=self.judge_kind,
                passed=False,
                confidence=1.0,
                reason="case_id mismatch",
            )
        if not candidate_output.compile_succeeded:
            reason = "compile failed"
        elif not candidate_output.tests_passed:
            failed = ", ".join(candidate_output.tests_failed_ids[:5])
            reason = (
                f"tests failed: {failed}"
                if failed
                else "tests failed (no test ids reported)"
            )
        else:
            reason = ""
        passed = (
            candidate_output.compile_succeeded
            and candidate_output.tests_passed
        )
        return JudgeResult(
            case_id=case.case_id,
            judge_id=self.judge_id,
            judge_kind=self.judge_kind,
            passed=passed,
            confidence=1.0,
            reason=reason,
            axis_scores=(
                (
                    ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS,
                    1.0 if passed else 0.0,
                ),
            ),
        )
