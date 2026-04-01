"""Constitutional AI Integration for Project Aura.

This package implements Constitutional AI (CAI) based on Anthropic's research,
providing self-critique and revision capabilities for AI agent outputs.

Key Components:
    - ConstitutionalCritiqueService: Evaluates outputs against constitutional principles
    - ConstitutionalRevisionService: Revises outputs based on critique results
    - ConstitutionalPrinciple: Data model for individual principles
    - CritiqueResult: Data model for critique evaluation results
    - RevisionResult: Data model for revision outcomes

Phase 4 Components (ADR-063):
    - ConstitutionalJudgeService: LLM-as-Judge evaluation pipeline
    - GoldenSetService: Golden set management and regression detection
    - CAIMetricsPublisher: CloudWatch metrics for Constitutional AI
    - Evaluation models: ResponsePair, GoldenSetCase, EvaluationMetrics

Example:
    >>> from src.services.constitutional_ai import (
    ...     ConstitutionalCritiqueService,
    ...     ConstitutionalRevisionService,
    ... )
    >>> critique_service = ConstitutionalCritiqueService(llm_service)
    >>> critiques = await critique_service.critique_output(output, context)
"""

from src.services.constitutional_ai.cai_metrics_publisher import (
    CAIMetricName,
    CAIMetricsMode,
    CAIMetricsPublisher,
    CAIMetricsPublisherConfig,
    create_cai_metrics_publisher,
)
from src.services.constitutional_ai.critique_service import (
    ConstitutionalCritiqueService,
)

# Phase 4: Evaluation Infrastructure (ADR-063)
from src.services.constitutional_ai.evaluation_models import (
    EvaluationDataset,
    EvaluationMetrics,
    ExpectedCritique,
    GoldenSetCase,
    GoldenSetCategory,
    JudgePreference,
    JudgeResult,
    RegressionItem,
    RegressionReport,
    RegressionSeverity,
    ResponsePair,
)
from src.services.constitutional_ai.exceptions import (
    ConstitutionalAIError,
    ConstitutionLoadError,
    CritiqueParseError,
    CritiqueTimeoutError,
    HITLRequiredError,
    PrincipleValidationError,
    RevisionConvergenceError,
)
from src.services.constitutional_ai.failure_policy import (
    ConstitutionalFailureConfig,
    CritiqueFailurePolicy,
    RevisionFailurePolicy,
    get_failure_config,
)
from src.services.constitutional_ai.golden_set_service import (
    BaselineMetrics,
    GoldenSetMode,
    GoldenSetService,
    GoldenSetServiceConfig,
)
from src.services.constitutional_ai.llm_judge_service import (
    BatchEvaluationResult,
    ConstitutionalJudgeService,
    JudgeMode,
    JudgeServiceConfig,
)
from src.services.constitutional_ai.models import (
    ConstitutionalPrinciple,
    CritiqueResult,
    PrincipleCategory,
    PrincipleSeverity,
    RevisionResult,
)
from src.services.constitutional_ai.revision_service import (
    ConstitutionalRevisionService,
)

__all__ = [
    # Models
    "ConstitutionalPrinciple",
    "CritiqueResult",
    "RevisionResult",
    "PrincipleSeverity",
    "PrincipleCategory",
    # Exceptions
    "ConstitutionalAIError",
    "CritiqueTimeoutError",
    "CritiqueParseError",
    "RevisionConvergenceError",
    "HITLRequiredError",
    "ConstitutionLoadError",
    "PrincipleValidationError",
    # Failure Policy
    "CritiqueFailurePolicy",
    "RevisionFailurePolicy",
    "ConstitutionalFailureConfig",
    "get_failure_config",
    # Services
    "ConstitutionalCritiqueService",
    "ConstitutionalRevisionService",
    # Phase 4: Evaluation Infrastructure (ADR-063)
    # Evaluation Models
    "ResponsePair",
    "JudgeResult",
    "JudgePreference",
    "ExpectedCritique",
    "GoldenSetCase",
    "GoldenSetCategory",
    "RegressionItem",
    "RegressionSeverity",
    "RegressionReport",
    "EvaluationDataset",
    "EvaluationMetrics",
    # LLM-as-Judge Service
    "ConstitutionalJudgeService",
    "JudgeServiceConfig",
    "JudgeMode",
    "BatchEvaluationResult",
    # Golden Set Service
    "GoldenSetService",
    "GoldenSetServiceConfig",
    "GoldenSetMode",
    "BaselineMetrics",
    # Metrics Publisher
    "CAIMetricsPublisher",
    "CAIMetricsPublisherConfig",
    "CAIMetricsMode",
    "CAIMetricName",
    "create_cai_metrics_publisher",
]
