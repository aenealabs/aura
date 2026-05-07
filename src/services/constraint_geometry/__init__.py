"""
Project Aura - Constraint Geometry Engine (CGE)

Deterministic semantic coherence measurement across a 7-axis constraint space.
Implements ADR-081: Deterministic Cortical Discrimination Layer.

Architecture:
- Step A: Constraint Resolution (Neptune graph / in-memory) - constraint_graph.py
- Step B: Coherence Computation (cosine similarity, NumPy) - coherence_calculator.py
- Step C: Action Determination (threshold comparison) - policy_profile.py

Performance Targets:
- P50 <25ms, P95 <50ms, P99 <100ms
- 100% determinism (same input = same score)
- >95% cache hit rate after warm-up

Usage:
    from src.services.constraint_geometry import (
        ConstraintGeometryEngine,
        CoherenceResult,
        CoherenceAction,
        ConstraintAxis,
        AgentOutput,
    )

    engine = create_engine(config=CGEConfig.for_testing())
    result = await engine.assess_coherence(
        output=AgentOutput(text="agent output text"),
        policy_profile="default",
    )

    if result.is_auto_executable:
        deploy(result)
    elif result.needs_human:
        route_to_hitl(result)

Author: Project Aura Team
Created: 2026-02-11
"""

# Coherence Calculator
from .coherence_calculator import CoherenceCalculator

# Configuration
from .config import (
    AuditConfig,
    CacheConfig,
    CGEConfig,
    EmbeddingConfig,
    MetricsConfig,
    NeptuneConfig,
    OpenSearchConfig,
    get_cge_config,
    reset_config,
)

# Constraint Graph Resolver
from .constraint_graph import ConstraintGraphResolver

# Contracts - Core types
from .contracts import (
    AgentOutput,
    AxisCoherenceScore,
    CoherenceAction,
    CoherenceResult,
    ConstraintAxis,
    ConstraintEdge,
    ConstraintEdgeType,
    ConstraintRule,
    PolicyConstraint,
    PolicyConstraintType,
    ProvenanceContext,
    RegressionFloor,
    RegressionFloorAction,
    RegressionFloorComparisonMode,
    RegressionFloorViolation,
    ResolvedConstraintSet,
    RuleCoherenceScore,
)

# Embedding Cache
from .embedding_cache import EmbeddingCache

# Main Engine
from .engine import (
    ConstraintGeometryEngine,
    create_engine,
    get_cge_engine,
    reset_cge_engine,
)

# Metrics
from .metrics import CGEMetricsPublisher, get_metrics_publisher, reset_metrics_publisher

# Policy Profiles
from .policy_profile import (
    PROFILE_DEFAULT,
    PROFILE_DEVELOPER_SANDBOX,
    PROFILE_DOD_IL5,
    PROFILE_SOX_COMPLIANT,
    PolicyProfile,
    PolicyProfileManager,
    PolicyThresholds,
)

# Provenance Adapter
from .provenance_adapter import ProvenanceAdapter

# Regression Floor Evaluator (ADR-088 Phase 1)
from .regression_floor import (
    IncumbentBaseline,
    evaluate_floors,
    violations_force_reject,
)

__all__ = [
    # Enums
    "ConstraintAxis",
    "CoherenceAction",
    "ConstraintEdgeType",
    # Core data types
    "ConstraintRule",
    "ConstraintEdge",
    "ResolvedConstraintSet",
    "RuleCoherenceScore",
    "AxisCoherenceScore",
    "CoherenceResult",
    "AgentOutput",
    "ProvenanceContext",
    "PolicyConstraint",
    "PolicyConstraintType",
    "RegressionFloor",
    "RegressionFloorAction",
    "RegressionFloorComparisonMode",
    "RegressionFloorViolation",
    "IncumbentBaseline",
    "evaluate_floors",
    "violations_force_reject",
    # Configuration
    "CGEConfig",
    "CacheConfig",
    "NeptuneConfig",
    "EmbeddingConfig",
    "OpenSearchConfig",
    "MetricsConfig",
    "AuditConfig",
    "get_cge_config",
    "reset_config",
    # Policy Profiles
    "PolicyProfile",
    "PolicyThresholds",
    "PolicyProfileManager",
    "PROFILE_DEFAULT",
    "PROFILE_DOD_IL5",
    "PROFILE_DEVELOPER_SANDBOX",
    "PROFILE_SOX_COMPLIANT",
    # Core Services
    "ConstraintGeometryEngine",
    "CoherenceCalculator",
    "ConstraintGraphResolver",
    "EmbeddingCache",
    "ProvenanceAdapter",
    # Metrics
    "CGEMetricsPublisher",
    "get_metrics_publisher",
    "reset_metrics_publisher",
    # Engine Factory
    "create_engine",
    "get_cge_engine",
    "reset_cge_engine",
]

__version__ = "0.1.0"
