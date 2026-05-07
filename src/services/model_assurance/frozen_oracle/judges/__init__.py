"""Frozen Reference Oracle judges (ADR-088 Phase 2.2)."""

from __future__ import annotations

from .ast_judge import ASTDiffJudge, PatchCandidateOutput
from .compile_judge import CompileTestCandidateOutput, CompileTestJudge
from .contracts import CandidateOutput, Judge, JudgeRegistry
from .llm_judge import (
    LLMJudge,
    LLMJudgeCandidateOutput,
    LLMJudgeRequest,
    LLMJudgeResponse,
    SelfGradingError,
    assert_no_self_grading,
)
from .static_analysis_judge import (
    StaticAnalysisCandidateOutput,
    StaticAnalysisJudge,
)

__all__ = [
    "CandidateOutput",
    "Judge",
    "JudgeRegistry",
    "ASTDiffJudge",
    "PatchCandidateOutput",
    "StaticAnalysisJudge",
    "StaticAnalysisCandidateOutput",
    "CompileTestJudge",
    "CompileTestCandidateOutput",
    "LLMJudge",
    "LLMJudgeRequest",
    "LLMJudgeResponse",
    "LLMJudgeCandidateOutput",
    "SelfGradingError",
    "assert_no_self_grading",
]
