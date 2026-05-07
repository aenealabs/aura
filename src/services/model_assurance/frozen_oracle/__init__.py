"""Frozen Reference Oracle (ADR-088 Phase 2.2)."""

from __future__ import annotations

from .contracts import (
    DOMAIN_MINIMUMS,
    GOLDEN_SET_MINIMUM,
    GoldenSetIntegrityError,
    GoldenTestCase,
    JudgeKind,
    JudgeResult,
    OracleEvaluation,
    TestCaseDomain,
)
from .golden_set import GoldenTestSet, build_test_set
from .judges import (
    ASTDiffJudge,
    CandidateOutput,
    CompileTestCandidateOutput,
    CompileTestJudge,
    Judge,
    JudgeRegistry,
    LLMJudge,
    LLMJudgeCandidateOutput,
    LLMJudgeRequest,
    LLMJudgeResponse,
    PatchCandidateOutput,
    SelfGradingError,
    StaticAnalysisCandidateOutput,
    StaticAnalysisJudge,
    assert_no_self_grading,
)
from .oracle_service import DEFAULT_HOLDOUT_RATE, OracleService
from .rotation import (
    REQUIRED_APPROVALS,
    ROTATION_CAP_FRACTION,
    RotationApproval,
    RotationProposal,
    apply_rotation,
    explain_rotation_cap,
)

__all__ = [
    "GOLDEN_SET_MINIMUM",
    "DOMAIN_MINIMUMS",
    "GoldenSetIntegrityError",
    "GoldenTestCase",
    "JudgeKind",
    "JudgeResult",
    "OracleEvaluation",
    "TestCaseDomain",
    "GoldenTestSet",
    "build_test_set",
    "Judge",
    "JudgeRegistry",
    "CandidateOutput",
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
    "DEFAULT_HOLDOUT_RATE",
    "OracleService",
    "REQUIRED_APPROVALS",
    "ROTATION_CAP_FRACTION",
    "RotationApproval",
    "RotationProposal",
    "apply_rotation",
    "explain_rotation_cap",
]
