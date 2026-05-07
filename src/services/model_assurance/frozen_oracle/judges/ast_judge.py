"""AST-diff deterministic judge (ADR-088 Phase 2.2).

Compares the candidate-produced patch against the human-authored
reference patch via Python AST canonicalisation. Two patches that
parse to the same canonical AST are equivalent regardless of
whitespace, comment ordering, or trivial expression rewrites.

Per ADR-088 anti-pattern guard ("Do not test golden set content;
test golden set tooling"): this judge tests the *protocol*, not
specific vulnerability case content. It is the same canonicaliser
already used by ADR-085 §Phase 1's consensus engine — reusing keeps
both pipelines on identical equivalence semantics.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle.contracts import (
    GoldenTestCase,
    JudgeKind,
    JudgeResult,
)


@dataclass(frozen=True)
class PatchCandidateOutput:
    """Candidate-produced patch source code keyed by case_id."""

    case_id: str
    patched_source: str


class ASTDiffJudge:
    """AST-equivalence deterministic judge.

    The expected ground truth is supplied via the case's
    ``expected`` mapping, key ``"reference_source"``. Comparison is
    via :func:`ast.dump` after parsing both sides — same dump
    string == same canonical AST.
    """

    judge_kind = JudgeKind.DETERMINISTIC
    judge_id = "ast_diff_v1"

    def evaluate(
        self,
        *,
        case: GoldenTestCase,
        candidate_output: PatchCandidateOutput,
    ) -> JudgeResult:
        if case.case_id != candidate_output.case_id:
            return JudgeResult(
                case_id=case.case_id,
                judge_id=self.judge_id,
                judge_kind=self.judge_kind,
                passed=False,
                confidence=1.0,
                reason=(
                    f"case_id mismatch: candidate={candidate_output.case_id!r}, "
                    f"case={case.case_id!r}"
                ),
            )
        reference = case.expected_dict.get("reference_source")
        if reference is None:
            return JudgeResult(
                case_id=case.case_id,
                judge_id=self.judge_id,
                judge_kind=self.judge_kind,
                passed=False,
                confidence=1.0,
                reason="case has no 'reference_source' in expected",
            )
        try:
            ref_dump = ast.dump(ast.parse(reference), annotate_fields=True)
        except SyntaxError as exc:
            return JudgeResult(
                case_id=case.case_id,
                judge_id=self.judge_id,
                judge_kind=self.judge_kind,
                passed=False,
                confidence=1.0,
                reason=f"reference_source did not parse: {exc}",
            )
        try:
            cand_dump = ast.dump(
                ast.parse(candidate_output.patched_source),
                annotate_fields=True,
            )
        except SyntaxError as exc:
            return JudgeResult(
                case_id=case.case_id,
                judge_id=self.judge_id,
                judge_kind=self.judge_kind,
                passed=False,
                confidence=1.0,
                reason=f"candidate patched_source did not parse: {exc}",
                axis_scores=(
                    (ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS, 0.0),
                ),
            )
        passed = ref_dump == cand_dump
        return JudgeResult(
            case_id=case.case_id,
            judge_id=self.judge_id,
            judge_kind=self.judge_kind,
            passed=passed,
            confidence=1.0,
            reason="" if passed else "AST canonical forms differ",
            axis_scores=(
                (
                    ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS,
                    1.0 if passed else 0.0,
                ),
            ),
        )
