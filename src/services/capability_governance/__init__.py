"""
Project Aura - Agent Capability Governance Package

Per-agent tool access control, runtime capability enforcement,
and HITL escalation workflows implementing ADR-066.

Core Components:
- Contracts: Data contracts, enums, and dataclasses
- Registry: Tool capability registry and classification
- Policy: Agent capability policies and evaluation
- Middleware: Runtime enforcement middleware
- Audit: Audit logging service
- Dynamic Grants: HITL-approved dynamic capability grants
- Metrics: CloudWatch metrics publisher

Usage:
    from src.services.capability_governance import (
        CapabilityEnforcementMiddleware,
        CapabilityContext,
        CapabilityDecision,
        AgentCapabilityPolicy,
    )

    # Create middleware
    middleware = CapabilityEnforcementMiddleware()

    # Check capability
    context = CapabilityContext(
        agent_id="agent-123",
        agent_type="CoderAgent",
        tool_name="semantic_search",
        action="execute",
        execution_context="sandbox",
    )
    result = await middleware.check(context)

    if result.is_allowed:
        # Proceed with tool invocation
        pass
    elif result.requires_hitl:
        # Request escalation
        pass

Author: Project Aura Team
Created: 2026-01-26
"""

# =============================================================================
# Contracts
# =============================================================================

from .anomaly_contracts import (  # ADR-072 Anomaly Detection Contracts
    AgentBehaviorFeatures,
    AgentContext,
    AlertSeverity,
    AnomalyAlert,
    AnomalyDetectionConfig,
    AnomalyResult,
    AnomalyType,
    CapabilityInvocation,
    HoneypotCapability,
    HoneypotResult,
    InvocationContext,
    QuarantineReason,
    QuarantineRecord,
    StatisticalBaseline,
)
from .anomaly_explainer import (  # ADR-072 Anomaly Explainer
    AnomalyExplainer,
    get_anomaly_explainer,
    reset_anomaly_explainer,
)
from .audit import (
    AuditConfig,
    AuditRecord,
    CapabilityAuditService,
    get_audit_service,
    reset_audit_service,
)
from .contracts import (  # Enums; Dataclasses; Type aliases
    ActionType,
    AgentType,
    CapabilityApprovalResponse,
    CapabilityCheckResult,
    CapabilityContext,
    CapabilityDecision,
    CapabilityEscalationRequest,
    CapabilityScope,
    CapabilityViolation,
    DynamicCapabilityGrant,
    ExecutionContext,
    GrantId,
    PolicyVersion,
    RequestId,
    ToolCapability,
    ToolClassification,
    ToolName,
)
from .dynamic_grants import (
    DynamicGrantManager,
    GrantManagerConfig,
    get_grant_manager,
    reset_grant_manager,
)
from .graph_analyzer import (  # ADR-071 Graph Analyzer
    CapabilityGraphAnalyzer,
    get_capability_graph_analyzer,
    reset_capability_graph_analyzer,
)
from .graph_contracts import (  # ADR-071 Graph Analysis
    AgentId,
    CapabilitySource,
    CombinationId,
    ConflictType,
    CoverageGap,
    EdgeType,
    EffectiveCapabilities,
    EffectiveCapability,
    EscalationPath,
    GapId,
    GraphEdge,
    GraphVertex,
    GraphVisualizationData,
    InheritanceNode,
    InheritanceTree,
    PathId,
    RiskLevel,
    ToxicCombination,
    VertexType,
)
from .graph_sync import (  # ADR-070/071 Graph Sync
    PolicyDeployedEvent,
    PolicyGraphSynchronizer,
    SyncResult,
    SyncStatus,
    get_policy_graph_synchronizer,
    reset_policy_graph_synchronizer,
)
from .honeypot_detector import (  # ADR-072 Honeypot Detector
    HONEYPOT_CAPABILITIES,
    HoneypotDetector,
    get_honeypot_detector,
    reset_honeypot_detector,
)
from .metrics import (
    CapabilityMetricsPublisher,
    MetricName,
    MetricsConfig,
    get_metrics_publisher,
    reset_metrics_publisher,
)
from .middleware import (
    CapabilityDeniedError,
    CapabilityEnforcementMiddleware,
    CapabilityEscalationPending,
    get_capability_middleware,
    reset_capability_middleware,
)
from .policy import (
    DEFAULT_TOOL_CLASSIFICATIONS,
    AgentCapabilityPolicy,
    PolicyRepository,
    get_policy_repository,
    get_tool_classification,
    reset_policy_repository,
)
from .policy_validator import (  # ADR-070 Policy Validator
    PolicyValidator,
    ValidationContext,
    ValidationError,
    ValidationResult,
    ValidationSeverity,
    ValidationWarning,
    get_policy_validator,
    reset_policy_validator,
)
from .registry import (
    DEFAULT_TOOL_CAPABILITIES,
    CapabilityRegistry,
    get_capability_registry,
    reset_capability_registry,
)
from .simulator import (  # ADR-070 Policy Simulator
    PolicyDifference,
    PolicySimulator,
    RegressionTestCase,
    RegressionTestResult,
    SimulatedDecision,
    SimulationMode,
    SimulationResult,
    ToolInvocation,
    get_policy_simulator,
    reset_policy_simulator,
)
from .statistical_detector import (  # ADR-072 Statistical Detector
    BaselineService,
    InMemoryBaselineService,
    StatisticalAnomalyDetector,
    get_statistical_detector,
    reset_statistical_detector,
)

# =============================================================================
# Registry
# =============================================================================


# =============================================================================
# Policy
# =============================================================================


# =============================================================================
# Middleware
# =============================================================================


# =============================================================================
# Audit
# =============================================================================


# =============================================================================
# Dynamic Grants
# =============================================================================


# =============================================================================
# Metrics
# =============================================================================


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Enums
    "ActionType",
    "CapabilityDecision",
    "CapabilityScope",
    "ExecutionContext",
    "ToolClassification",
    # Graph Enums (ADR-071)
    "ConflictType",
    "EdgeType",
    "RiskLevel",
    "VertexType",
    # Contracts
    "CapabilityApprovalResponse",
    "CapabilityCheckResult",
    "CapabilityContext",
    "CapabilityEscalationRequest",
    "CapabilityViolation",
    "DynamicCapabilityGrant",
    "ToolCapability",
    # Graph Contracts (ADR-071)
    "CapabilitySource",
    "CoverageGap",
    "EffectiveCapabilities",
    "EffectiveCapability",
    "EscalationPath",
    "GraphEdge",
    "GraphVertex",
    "GraphVisualizationData",
    "InheritanceNode",
    "InheritanceTree",
    "ToxicCombination",
    # Type Aliases
    "AgentId",
    "AgentType",
    "CombinationId",
    "GapId",
    "GrantId",
    "PathId",
    "PolicyVersion",
    "RequestId",
    "ToolName",
    # Registry
    "CapabilityRegistry",
    "DEFAULT_TOOL_CAPABILITIES",
    "get_capability_registry",
    "reset_capability_registry",
    # Policy
    "AgentCapabilityPolicy",
    "DEFAULT_TOOL_CLASSIFICATIONS",
    "PolicyRepository",
    "get_policy_repository",
    "get_tool_classification",
    "reset_policy_repository",
    # Middleware
    "CapabilityDeniedError",
    "CapabilityEnforcementMiddleware",
    "CapabilityEscalationPending",
    "get_capability_middleware",
    "reset_capability_middleware",
    # Audit
    "AuditConfig",
    "AuditRecord",
    "CapabilityAuditService",
    "get_audit_service",
    "reset_audit_service",
    # Dynamic Grants
    "DynamicGrantManager",
    "GrantManagerConfig",
    "get_grant_manager",
    "reset_grant_manager",
    # Metrics
    "CapabilityMetricsPublisher",
    "MetricName",
    "MetricsConfig",
    "get_metrics_publisher",
    "reset_metrics_publisher",
    # Graph Analyzer (ADR-071)
    "CapabilityGraphAnalyzer",
    "get_capability_graph_analyzer",
    "reset_capability_graph_analyzer",
    # Graph Sync (ADR-070/071)
    "PolicyDeployedEvent",
    "PolicyGraphSynchronizer",
    "SyncResult",
    "SyncStatus",
    "get_policy_graph_synchronizer",
    "reset_policy_graph_synchronizer",
    # Anomaly Detection Contracts (ADR-072)
    "AgentBehaviorFeatures",
    "AgentContext",
    "AlertSeverity",
    "AnomalyAlert",
    "AnomalyDetectionConfig",
    "AnomalyResult",
    "AnomalyType",
    "CapabilityInvocation",
    "HoneypotCapability",
    "HoneypotResult",
    "InvocationContext",
    "QuarantineReason",
    "QuarantineRecord",
    "StatisticalBaseline",
    # Anomaly Explainer (ADR-072)
    "AnomalyExplainer",
    "get_anomaly_explainer",
    "reset_anomaly_explainer",
    # Honeypot Detector (ADR-072)
    "HONEYPOT_CAPABILITIES",
    "HoneypotDetector",
    "get_honeypot_detector",
    "reset_honeypot_detector",
    # Statistical Detector (ADR-072)
    "BaselineService",
    "InMemoryBaselineService",
    "StatisticalAnomalyDetector",
    "get_statistical_detector",
    "reset_statistical_detector",
    # Policy Validator (ADR-070)
    "PolicyValidator",
    "ValidationContext",
    "ValidationError",
    "ValidationResult",
    "ValidationSeverity",
    "ValidationWarning",
    "get_policy_validator",
    "reset_policy_validator",
    # Policy Simulator (ADR-070)
    "PolicyDifference",
    "PolicySimulator",
    "RegressionTestCase",
    "RegressionTestResult",
    "SimulatedDecision",
    "SimulationMode",
    "SimulationResult",
    "ToolInvocation",
    "get_policy_simulator",
    "reset_policy_simulator",
]

# =============================================================================
# Module Version
# =============================================================================

__version__ = "1.0.0"
