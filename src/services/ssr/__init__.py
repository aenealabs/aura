"""
Project Aura - Self-Play SWE-RL (SSR) Training Services

This package implements the Bug Artifact Infrastructure for ADR-050,
enabling autonomous agent improvement through synthetic bug generation
and resolution based on Meta FAIR research (arXiv:2512.18552).

Components:
- bug_artifact: Dataclasses and enums for the 5-file bug artifact format
- validation_pipeline: 7-stage consistency validation pipeline
- artifact_storage_service: S3 + DynamoDB storage operations
- training_service: Step Functions training workflow orchestration
- self_play_orchestrator: Self-play training loop orchestration
- training_data_pipeline: Reward computation and trajectory collection
- failure_analyzer: Categorizes failure modes and extracts learning signals
- higher_order_queue: Priority queue for failed bugs with deduplication
- curriculum_scheduler: Progressive difficulty ramping with forgetting prevention
- model_update_service: Fine-tuning pipeline with A/B testing and rollback
- consent_service: GDPR/CCPA compliant consent management
- git_analyzer: Git history analysis for revertible bug-fix commits
- history_injector: History-aware bug injection with GraphRAG integration

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
GitHub Issues: #162, #163, #164, #165, #166
"""

from src.services.ssr.artifact_storage_service import (
    ArtifactStorageService,
    create_artifact_storage_service,
)
from src.services.ssr.bug_artifact import (
    ArtifactStatus,
    BugArtifact,
    InjectionStrategy,
    StageResult,
    ValidationPipelineResult,
    ValidationResult,
    ValidationStage,
)
from src.services.ssr.consent_service import (
    ConsentAuditEntry,
    ConsentRecord,
    ConsentService,
    ConsentStatus,
    ConsentType,
    CustomerConsentProfile,
    DataSubjectRequest,
    DataSubjectRight,
    LegalBasis,
)
from src.services.ssr.curriculum_scheduler import (
    CurriculumBatch,
    CurriculumScheduler,
    CurriculumState,
    CurriculumStrategy,
    LearningPhase,
    SkillProfile,
)

# Phase 4: Higher-Order Training components
from src.services.ssr.failure_analyzer import (
    FailureAnalysis,
    FailureAnalyzer,
    FailureMode,
    FailureSummary,
    LearningSignalType,
)

# Phase 5: History-Aware Injection components
from src.services.ssr.git_analyzer import (
    AnalysisResult,
    AnalysisStatus,
    CommitCategory,
    CommitInfo,
    GitHistoryAnalyzer,
    RevertCandidate,
    create_git_analyzer,
)
from src.services.ssr.higher_order_queue import (
    BugStatus,
    DeduplicationResult,
    HigherOrderBug,
    HigherOrderQueue,
    QueuePriority,
)
from src.services.ssr.history_injector import (
    CandidateRankingStrategy,
    EnrichedCandidate,
    GraphRAGContext,
    HistoryAwareBugInjector,
    InjectionResult,
    InjectionStatus,
    create_history_injector,
)
from src.services.ssr.model_update_service import (
    ABTest,
    ABTestStatus,
    DeploymentStage,
    ModelCheckpoint,
    ModelStatus,
    ModelUpdateService,
    ModelVersion,
    RollbackDecision,
)

# Self-play orchestrator - imported lazily to avoid circular dependencies
# Use: from src.services.ssr.self_play_orchestrator import SelfPlayOrchestrator
from src.services.ssr.self_play_orchestrator import (
    SessionCheckpoint,
    SessionConfig,
    SessionMetrics,
    SessionStatus,
)
from src.services.ssr.training_data_pipeline import (
    RewardComputer,
    RewardSignal,
    TrainingBatch,
    TrainingDataPipeline,
    TrainingTrajectory,
    TrajectoryType,
)
from src.services.ssr.training_service import (
    SSRTrainingService,
    TrainingJobConfig,
    TrainingJobResult,
    TrainingJobStatus,
    create_training_service,
)
from src.services.ssr.validation_pipeline import (
    SandboxExecutionResult,
    ValidationPipeline,
    create_validation_pipeline,
)

__all__ = [
    # Phase 1-3 Enums
    "ArtifactStatus",
    "ValidationStage",
    "ValidationResult",
    "InjectionStrategy",
    "TrainingJobStatus",
    "SessionStatus",
    "TrajectoryType",
    "RewardSignal",
    # Phase 1-3 Dataclasses
    "BugArtifact",
    "StageResult",
    "ValidationPipelineResult",
    "TrainingJobConfig",
    "TrainingJobResult",
    "SessionConfig",
    "SessionCheckpoint",
    "SessionMetrics",
    "TrainingTrajectory",
    "TrainingBatch",
    # Phase 1-3 Services
    "ArtifactStorageService",
    "create_artifact_storage_service",
    "ValidationPipeline",
    "create_validation_pipeline",
    "SandboxExecutionResult",
    "SSRTrainingService",
    "create_training_service",
    "TrainingDataPipeline",
    "RewardComputer",
    # Phase 4: Failure Analyzer
    "FailureMode",
    "LearningSignalType",
    "FailureAnalysis",
    "FailureSummary",
    "FailureAnalyzer",
    # Phase 4: Higher-Order Queue
    "QueuePriority",
    "BugStatus",
    "HigherOrderBug",
    "DeduplicationResult",
    "HigherOrderQueue",
    # Phase 4: Curriculum Scheduler
    "CurriculumStrategy",
    "LearningPhase",
    "SkillProfile",
    "CurriculumState",
    "CurriculumBatch",
    "CurriculumScheduler",
    # Phase 4: Model Update Service
    "ModelStatus",
    "DeploymentStage",
    "ABTestStatus",
    "ModelCheckpoint",
    "ModelVersion",
    "ABTest",
    "RollbackDecision",
    "ModelUpdateService",
    # Phase 4: Consent Service
    "ConsentType",
    "ConsentStatus",
    "LegalBasis",
    "DataSubjectRight",
    "ConsentRecord",
    "DataSubjectRequest",
    "ConsentAuditEntry",
    "CustomerConsentProfile",
    "ConsentService",
    # Phase 5: Git Analyzer
    "CommitCategory",
    "AnalysisStatus",
    "CommitInfo",
    "RevertCandidate",
    "AnalysisResult",
    "GitHistoryAnalyzer",
    "create_git_analyzer",
    # Phase 5: History-Aware Injector
    "InjectionStatus",
    "CandidateRankingStrategy",
    "GraphRAGContext",
    "EnrichedCandidate",
    "InjectionResult",
    "HistoryAwareBugInjector",
    "create_history_injector",
    # Note: SelfPlayOrchestrator and RoundResult should be imported directly
    # from src.services.ssr.self_play_orchestrator to avoid circular imports
]
