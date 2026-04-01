"""
Project Aura - Memory Evolution Service (ADR-080)

Implements the ReMem Action Framework for test-time memory evolution.
This extends the ReAct pattern with explicit memory refinement operations.

Architecture:
- MemoryRefiner: Orchestrates CONSOLIDATE, PRUNE, and future operations
- RefineAction: Discrete refinement action in agent loop
- RefineResult: Operation outcome with rollback support

Phased Rollout:
- Phase 1a: CONSOLIDATE, PRUNE (low latency, DynamoDB-only)
- Phase 1b: REINFORCE (Titan TTT integration)
- Phase 3: ABSTRACT (LLM-based strategy extraction)
- Phase 5: LINK, CORRECT, ROLLBACK (Neptune, advanced)

Usage:
    from src.services.memory_evolution import (
        MemoryRefiner,
        RefineAction,
        RefineOperation,
        get_memory_refiner,
    )

    # Create action
    action = RefineAction(
        operation=RefineOperation.CONSOLIDATE,
        target_memory_ids=["mem-1", "mem-2"],
        reasoning="Similar debugging patterns",
        confidence=0.9,
        tenant_id="tenant-123",
        security_domain="development",
    )

    # Execute refinement
    refiner = get_memory_refiner(memory_store=my_store)
    result = await refiner.refine(action)

Compliance:
- ADR-080: Evo-Memory Enhancements
- ADR-024: Titan Neural Memory (REINFORCE integration)
- CMMC Level 3: Multi-tenant isolation, encryption at rest
"""

# Phase 3: Abstract Operation exports
from .abstract_operation import (
    AbstractionConfig,
    AbstractionError,
    AbstractionService,
    MemoryClusteringService,
    TenantIsolationError,
    get_abstraction_service,
    get_clustering_service,
    reset_abstraction_service,
    reset_clustering_service,
)

# Phase 5: Advanced Operations exports
from .advanced_operations import (
    AdvancedOperationsConfig,
    CorrectionCandidate,
    CorrectionReason,
    CorrectionResult,
    CorrectOperationService,
    LinkCandidate,
    LinkResult,
    LinkType,
    LLMServiceProtocol,
    MemoryLinkService,
    MemoryStoreProtocol,
    NeptuneGraphServiceProtocol,
    RollbackOperationService,
    RollbackResult,
    SnapshotMetadata,
    SnapshotSource,
    SnapshotStoreProtocol,
    get_correct_service,
    get_link_service,
    get_rollback_service,
    reset_correct_service,
    reset_link_service,
    reset_rollback_service,
)

# Phase 2: Audit Integration exports
from .audit_integration import (
    EvolutionAuditAdapter,
    EvolutionAuditEventType,
    EvolutionAuditRecord,
    get_evolution_audit_adapter,
    reset_evolution_audit_adapter,
)

# Configuration exports
from .config import (
    AsyncConfig,
    ConsolidationConfig,
    FeatureFlags,
    MemoryEvolutionConfig,
    MetricsConfig,
    PruneConfig,
    ReinforceConfig,
    SecurityConfig,
    StorageConfig,
    get_memory_evolution_config,
    reset_memory_evolution_config,
    set_memory_evolution_config,
)

# Contract exports - Dataclasses
# Contract exports - Type aliases
# Contract exports - Enums
from .contracts import (
    AbstractedStrategy,
    AbstractionCandidate,
    AgentId,
    ConsolidationCandidate,
    EvolutionRecord,
    MemoryId,
    MemorySnapshot,
    OperationPhase,
    PruneCandidate,
    RefineAction,
    RefineOperation,
    RefineResult,
    RefineStatus,
    RollbackToken,
    SecurityDomain,
    SimilarityMetric,
    TenantId,
)

# Phase 4: Evolution Benchmark exports
from .evolution_benchmark import (
    AdaptiveSampler,
    BaselineMetrics,
    BenchmarkCategory,
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkSubcategory,
    BenchmarkTask,
    DriftDetector,
    DriftResult,
    DriftSeverity,
    EvolutionMetricsSummary,
    MemoryEvolutionBenchmark,
    TaskGenerator,
    TaskResult,
    get_evolution_benchmark,
    get_task_generator,
    reset_evolution_benchmark,
    reset_task_generator,
)

# Phase 2: Evolution Metrics exports
from .evolution_metrics import (
    EvolutionMetrics,
    EvolutionTracker,
    EvolutionTrackerConfig,
    TaskCompletionRecord,
    get_evolution_tracker,
    reset_evolution_tracker,
)

# Exception exports
from .exceptions import (
    AbstractError,
    CircuitBreakerOpen,
    ConsolidationError,
    FeatureDisabledError,
    MemoryEvolutionError,
    MetricsError,
    PruneError,
    QueueError,
    RefineOperationError,
    ReinforceError,
    RollbackError,
    SecurityBoundaryViolation,
    SnapshotError,
    StorageError,
    TenantIsolationViolation,
    ValidationError,
)

# Service exports
from .memory_refiner import (
    EvolutionRecordStore,
    MemoryRefiner,
    MemoryStore,
    MetricsPublisher,
    get_memory_refiner,
    reset_memory_refiner,
)

# Phase 2: Metrics Publisher exports
from .metrics_publisher import (
    EvolutionMetricsPublisher,
    MetricDataPoint,
    MetricsBuffer,
    get_evolution_metrics_publisher,
    reset_evolution_metrics_publisher,
)

# Phase 6: Multi-Agent Sharing exports
from .multi_agent_sharing import (
    AcceptanceDecision,
    AgentAcceptance,
    AgentRegistryProtocol,
    ApprovalType,
    CrossAgentPropagator,
    MultiAgentSharingConfig,
    NotificationServiceProtocol,
    PropagationResult,
    PropagationScope,
    SharingPolicy,
    SharingRequest,
    SharingRequestStoreProtocol,
    SharingStatus,
    StrategyPromotionService,
    StrategyStoreProtocol,
    get_promotion_service,
    get_propagator,
    reset_promotion_service,
    reset_propagator,
)

# Phase 1b: Refine Integration exports
from .refine_integration import (
    RefineActionRouter,
    RefineDecision,
    RefineDecisionMaker,
    get_refine_decision_maker,
    get_refine_router,
    reset_refine_decision_maker,
    reset_refine_router,
)

# Phase 1b: Titan Integration exports
from .titan_integration import (
    ReinforceMetrics,
    SurpriseCalculator,
    TaskOutcome,
    TitanMemoryServiceProtocol,
    TitanRefineIntegration,
    get_titan_refine_integration,
    reset_titan_refine_integration,
)

__all__ = [
    # Enums
    "RefineOperation",
    "OperationPhase",
    "RefineStatus",
    "SimilarityMetric",
    # Type aliases
    "MemoryId",
    "AgentId",
    "TenantId",
    "SecurityDomain",
    "RollbackToken",
    # Dataclasses
    "RefineAction",
    "RefineResult",
    "MemorySnapshot",
    "ConsolidationCandidate",
    "PruneCandidate",
    "EvolutionRecord",
    "AbstractionCandidate",
    "AbstractedStrategy",
    # Configuration
    "MemoryEvolutionConfig",
    "ConsolidationConfig",
    "PruneConfig",
    "ReinforceConfig",
    "AsyncConfig",
    "MetricsConfig",
    "StorageConfig",
    "SecurityConfig",
    "FeatureFlags",
    "get_memory_evolution_config",
    "set_memory_evolution_config",
    "reset_memory_evolution_config",
    # Exceptions
    "MemoryEvolutionError",
    "RefineOperationError",
    "ConsolidationError",
    "PruneError",
    "ReinforceError",
    "AbstractError",
    "RollbackError",
    "SecurityBoundaryViolation",
    "TenantIsolationViolation",
    "FeatureDisabledError",
    "ValidationError",
    "StorageError",
    "QueueError",
    "MetricsError",
    "SnapshotError",
    "CircuitBreakerOpen",
    # Protocols
    "MemoryStore",
    "EvolutionRecordStore",
    "MetricsPublisher",
    # Service
    "MemoryRefiner",
    "get_memory_refiner",
    "reset_memory_refiner",
    # Phase 1b: Titan Integration
    "TitanRefineIntegration",
    "TitanMemoryServiceProtocol",
    "SurpriseCalculator",
    "TaskOutcome",
    "ReinforceMetrics",
    "get_titan_refine_integration",
    "reset_titan_refine_integration",
    # Phase 1b: Refine Integration
    "RefineActionRouter",
    "RefineDecision",
    "RefineDecisionMaker",
    "get_refine_router",
    "reset_refine_router",
    "get_refine_decision_maker",
    "reset_refine_decision_maker",
    # Phase 2: Evolution Metrics
    "EvolutionMetrics",
    "EvolutionTracker",
    "EvolutionTrackerConfig",
    "TaskCompletionRecord",
    "get_evolution_tracker",
    "reset_evolution_tracker",
    # Phase 2: Metrics Publisher
    "EvolutionMetricsPublisher",
    "MetricDataPoint",
    "MetricsBuffer",
    "get_evolution_metrics_publisher",
    "reset_evolution_metrics_publisher",
    # Phase 2: Audit Integration
    "EvolutionAuditAdapter",
    "EvolutionAuditEventType",
    "EvolutionAuditRecord",
    "get_evolution_audit_adapter",
    "reset_evolution_audit_adapter",
    # Phase 3: Abstract Operation
    "AbstractionConfig",
    "AbstractionService",
    "AbstractionError",
    "MemoryClusteringService",
    "TenantIsolationError",
    "get_abstraction_service",
    "reset_abstraction_service",
    "get_clustering_service",
    "reset_clustering_service",
    # Phase 4: Evolution Benchmark
    "BenchmarkConfig",
    "BenchmarkCategory",
    "BenchmarkSubcategory",
    "BenchmarkTask",
    "BenchmarkResult",
    "TaskResult",
    "BaselineMetrics",
    "DriftResult",
    "DriftSeverity",
    "EvolutionMetricsSummary",
    "MemoryEvolutionBenchmark",
    "DriftDetector",
    "AdaptiveSampler",
    "TaskGenerator",
    "get_evolution_benchmark",
    "reset_evolution_benchmark",
    "get_task_generator",
    "reset_task_generator",
    # Phase 5: Advanced Operations
    "AdvancedOperationsConfig",
    "LinkType",
    "LinkCandidate",
    "LinkResult",
    "CorrectionReason",
    "CorrectionCandidate",
    "CorrectionResult",
    "SnapshotSource",
    "SnapshotMetadata",
    "RollbackResult",
    "NeptuneGraphServiceProtocol",
    "LLMServiceProtocol",
    "SnapshotStoreProtocol",
    "MemoryStoreProtocol",
    "MemoryLinkService",
    "CorrectOperationService",
    "RollbackOperationService",
    "get_link_service",
    "reset_link_service",
    "get_correct_service",
    "reset_correct_service",
    "get_rollback_service",
    "reset_rollback_service",
    # Phase 6: Multi-Agent Sharing
    "SharingStatus",
    "ApprovalType",
    "PropagationScope",
    "AcceptanceDecision",
    "SharingPolicy",
    "SharingRequest",
    "PropagationResult",
    "AgentAcceptance",
    "MultiAgentSharingConfig",
    "AgentRegistryProtocol",
    "StrategyStoreProtocol",
    "SharingRequestStoreProtocol",
    "NotificationServiceProtocol",
    "StrategyPromotionService",
    "CrossAgentPropagator",
    "get_promotion_service",
    "reset_promotion_service",
    "get_propagator",
    "reset_propagator",
]

__version__ = "1.6.0"
