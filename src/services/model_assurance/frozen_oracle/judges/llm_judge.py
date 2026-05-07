"""Pinned LLM judge (ADR-088 Phase 2.2 §Stage 4).

Uses a pinned external model (e.g. ``claude-3-5-sonnet-20241022``)
to grade natural-language reasoning where programmatic judging is
insufficient. Per ADR condition #9 (security team, not ML team,
owns rotation) and the recursive-degradation guard:

    candidate_model_id != judge_model_id

is enforced at construction. The guard is also exposed as a
standalone validator (:func:`assert_no_self_grading`) so the
test conftest can call it on every fixture that wires a judge +
candidate.

The actual LLM invocation is delegated to a callable injected at
construction. v1 supplies an in-memory mock; production wires a
Bedrock invocation. The judge body is the policy + scoring math
that turns a free-form LLM verdict into a deterministic pass/fail.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle.contracts import (
    GoldenTestCase,
    JudgeKind,
    JudgeResult,
)


@dataclass(frozen=True)
class LLMJudgeRequest:
    """Inputs the LLM judge sees per case."""

    case_id: str
    prompt: str
    candidate_response: str


@dataclass(frozen=True)
class LLMJudgeResponse:
    """The LLM's structured verdict on one case.

    The judge module enforces ``confidence in [0,1]`` and that the
    grader's pass/fail decision is recorded explicitly — not
    inferred from prose.
    """

    passed: bool
    confidence: float
    rationale: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"LLMJudgeResponse.confidence must be in [0,1]; "
                f"got {self.confidence}"
            )


@dataclass(frozen=True)
class LLMJudgeCandidateOutput:
    """The candidate's natural-language response."""

    case_id: str
    prompt: str
    response: str


class SelfGradingError(Exception):
    """Raised when judge_model_id == candidate_model_id."""


def assert_no_self_grading(
    *, candidate_model_id: str, judge_model_id: str
) -> None:
    if candidate_model_id == judge_model_id:
        raise SelfGradingError(
            f"recursive degradation guard: candidate ({candidate_model_id!r}) "
            f"and judge ({judge_model_id!r}) cannot be the same model"
        )


class LLMJudge:
    """Pinned-model LLM judge.

    The constructor enforces the self-grading guard immediately;
    callers cannot wire an LLM judge whose model id matches the
    candidate's. Confidence below ``confidence_floor`` (default
    0.6) demotes the verdict to fail — a low-confidence
    "yeah-probably-passes" judgement isn't allowed to slip through.
    """

    judge_kind = JudgeKind.LLM

    def __init__(
        self,
        *,
        judge_model_id: str,
        candidate_model_id: str,
        invoke: Callable[[LLMJudgeRequest], LLMJudgeResponse],
        target_axis: ModelAssuranceAxis = ModelAssuranceAxis.CODE_COMPREHENSION,
        confidence_floor: float = 0.6,
        judge_id: str = "llm_v1",
    ) -> None:
        assert_no_self_grading(
            candidate_model_id=candidate_model_id,
            judge_model_id=judge_model_id,
        )
        if not 0.0 <= confidence_floor <= 1.0:
            raise ValueError(
                f"confidence_floor must be in [0,1]; got {confidence_floor}"
            )
        self._judge_model_id = judge_model_id
        self._candidate_model_id = candidate_model_id
        self._invoke = invoke
        self._axis = target_axis
        self._confidence_floor = confidence_floor
        self.judge_id = judge_id

    @property
    def judge_model_id(self) -> str:
        return self._judge_model_id

    @property
    def candidate_model_id(self) -> str:
        return self._candidate_model_id

    def evaluate(
        self,
        *,
        case: GoldenTestCase,
        candidate_output: LLMJudgeCandidateOutput,
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
        request = LLMJudgeRequest(
            case_id=case.case_id,
            prompt=candidate_output.prompt,
            candidate_response=candidate_output.response,
        )
        response = self._invoke(request)
        if response.confidence < self._confidence_floor:
            return JudgeResult(
                case_id=case.case_id,
                judge_id=self.judge_id,
                judge_kind=self.judge_kind,
                passed=False,
                confidence=response.confidence,
                reason=(
                    f"confidence {response.confidence:.3f} below floor "
                    f"{self._confidence_floor}; demoting to fail"
                ),
                axis_scores=((self._axis, 0.0),),
            )
        return JudgeResult(
            case_id=case.case_id,
            judge_id=self.judge_id,
            judge_kind=self.judge_kind,
            passed=response.passed,
            confidence=response.confidence,
            reason=response.rationale,
            axis_scores=(
                (self._axis, 1.0 if response.passed else 0.0),
            ),
        )
