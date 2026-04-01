"""
Alignment Services Package (ADR-052).

This package implements the AI Alignment Principles and Human-Machine
Collaboration Framework for Project Aura.

Phase 1 - Foundation:
- AlignmentMetricsService: Core metrics collection and storage
- TrustScoreCalculator: Compute and track agent trust scores
- ReversibilityClassifier: Classify actions by reversibility level
- DecisionAuditLogger: Enhanced audit trail with reasoning chains

Phase 2 - Enforcement:
- SycophancyGuard: Pre-response validation for anti-sycophancy
- TrustBasedAutonomy: Dynamic permission adjustment
- RollbackService: Snapshot and restore capabilities

Phase 3 - Dashboard:
- AlignmentAnalyticsService: Historical trend analysis and alerts

Five-Layer Alignment Stack:
1. Reversibility - All actions can be rolled back
2. Safe Experimentation - Sandbox isolation
3. Trust Calibration - Earned autonomy levels
4. Decision Transparency - Full reasoning chains
5. Goal Alignment - Human-defined objectives

Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
"""

# Phase 3 - Dashboard
from src.services.alignment.analytics import (
    AgentComparison,
    AlertSeverity,
    AlertStatus,
    AlertThreshold,
    AlignmentAlert,
    AlignmentAnalyticsService,
    AlignmentReport,
    MetricDataPoint,
    TimeGranularity,
    TrendAnalysis,
    TrendDirection,
)

# Phase 1 - Foundation
from src.services.alignment.audit_logger import (
    AlternativeOption,
    DecisionAuditLogger,
    DecisionRecord,
    ReasoningStep,
    UncertaintyDisclosure,
)
from src.services.alignment.metrics_service import (
    AlignmentHealth,
    AlignmentMetricsService,
    AntiSycophancyMetrics,
    CollaborationMetrics,
    MetricThresholds,
    ReversibilityMetrics,
    TransparencyMetrics,
    TrustMetrics,
)
from src.services.alignment.reversibility import (
    ActionClass,
    ActionMetadata,
    ReversibilityClassifier,
    RollbackPlan,
    StateSnapshot,
)

# Phase 2 - Enforcement
from src.services.alignment.rollback_service import (
    RollbackCapability,
    RollbackExecution,
    RollbackService,
    RollbackStatus,
    SnapshotType,
)
from src.services.alignment.sycophancy_guard import (
    AgentSycophancyProfile,
    ResponseContext,
    ResponseSeverity,
    SycophancyGuard,
    SycophancyViolation,
    SycophancyViolationType,
    ValidationResult,
)
from src.services.alignment.trust_autonomy import (
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorizationResult,
    OverrideRecord,
    PermissionScope,
    TrustBasedAutonomy,
)
from src.services.alignment.trust_calculator import (
    AutonomyLevel,
    TrustScoreCalculator,
    TrustScoreComponents,
    TrustTransition,
)

__all__ = [
    # Phase 1 - Metrics Service
    "AlignmentMetricsService",
    "AlignmentHealth",
    "AntiSycophancyMetrics",
    "TrustMetrics",
    "TransparencyMetrics",
    "ReversibilityMetrics",
    "CollaborationMetrics",
    "MetricThresholds",
    # Phase 1 - Trust Calculator
    "TrustScoreCalculator",
    "TrustScoreComponents",
    "TrustTransition",
    "AutonomyLevel",
    # Phase 1 - Reversibility Classifier
    "ReversibilityClassifier",
    "ActionClass",
    "ActionMetadata",
    "RollbackPlan",
    "StateSnapshot",
    # Phase 1 - Audit Logger
    "DecisionAuditLogger",
    "DecisionRecord",
    "ReasoningStep",
    "AlternativeOption",
    "UncertaintyDisclosure",
    # Phase 2 - Sycophancy Guard
    "SycophancyGuard",
    "SycophancyViolation",
    "SycophancyViolationType",
    "ValidationResult",
    "ResponseContext",
    "ResponseSeverity",
    "AgentSycophancyProfile",
    # Phase 2 - Trust-Based Autonomy
    "TrustBasedAutonomy",
    "AuthorizationDecision",
    "AuthorizationRequest",
    "AuthorizationResult",
    "PermissionScope",
    "OverrideRecord",
    # Phase 2 - Rollback Service
    "RollbackService",
    "RollbackExecution",
    "RollbackStatus",
    "RollbackCapability",
    "SnapshotType",
    # Phase 3 - Analytics
    "AlignmentAnalyticsService",
    "AlignmentAlert",
    "AlignmentReport",
    "AlertSeverity",
    "AlertStatus",
    "AlertThreshold",
    "TrendAnalysis",
    "TrendDirection",
    "TimeGranularity",
    "MetricDataPoint",
    "AgentComparison",
]
