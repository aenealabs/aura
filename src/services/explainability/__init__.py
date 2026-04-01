"""
Project Aura - Universal Explainability Framework

Provides decision transparency for all AI agent decisions with:
- ReasoningChainBuilder: Build reasoning chains from decisions
- AlternativesAnalyzer: Analyze alternatives considered
- ConfidenceQuantifier: Quantify confidence intervals
- ConsistencyVerifier: Verify reasoning-action consistency
- InterAgentVerifier: Verify upstream agent claims
- UniversalExplainabilityService: Main orchestration service

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

# Alternatives Analyzer
from .alternatives import (
    AlternativesAnalyzer,
    configure_alternatives_analyzer,
    get_alternatives_analyzer,
    reset_alternatives_analyzer,
)

# Confidence Quantifier
from .confidence import (
    ConfidenceQuantifier,
    configure_confidence_quantifier,
    get_confidence_quantifier,
    reset_confidence_quantifier,
)

# Configuration
from .config import (
    AlternativesConfig,
    ConfidenceConfig,
    ConsistencyConfig,
    ExplainabilityConfig,
    InterAgentConfig,
    ReasoningChainConfig,
    configure_explainability,
    get_explainability_config,
    reset_explainability_config,
)

# Consistency Verifier
from .consistency import (
    ConsistencyVerifier,
    configure_consistency_verifier,
    get_consistency_verifier,
    reset_consistency_verifier,
)

# Contracts - Dataclasses
# Contracts - Enums
from .contracts import (
    Alternative,
    AlternativesReport,
    CalibrationMethod,
    ClaimVerification,
    ConfidenceInterval,
    ConsistencyReport,
    Contradiction,
    ContradictionSeverity,
    DecisionSeverity,
    ExplainabilityRecord,
    ExplainabilityScore,
    ReasoningChain,
    ReasoningStep,
    VerificationReport,
    VerificationStatus,
)

# Inter-Agent Verifier
from .inter_agent import (
    InterAgentVerifier,
    configure_inter_agent_verifier,
    get_inter_agent_verifier,
    reset_inter_agent_verifier,
)

# Mixin for Agent Integration
from .mixin import ExplainabilityMixin

# Reasoning Chain Builder
from .reasoning_chain import (
    ReasoningChainBuilder,
    configure_reasoning_chain_builder,
    get_reasoning_chain_builder,
    reset_reasoning_chain_builder,
)

# Main Service
from .service import (
    UniversalExplainabilityService,
    configure_explainability_service,
    get_explainability_service,
    reset_explainability_service,
)

__all__ = [
    # Enums
    "CalibrationMethod",
    "ContradictionSeverity",
    "DecisionSeverity",
    "VerificationStatus",
    # Dataclasses
    "Alternative",
    "AlternativesReport",
    "ClaimVerification",
    "ConfidenceInterval",
    "ConsistencyReport",
    "Contradiction",
    "ExplainabilityRecord",
    "ExplainabilityScore",
    "ReasoningChain",
    "ReasoningStep",
    "VerificationReport",
    # Configuration
    "AlternativesConfig",
    "ConfidenceConfig",
    "ConsistencyConfig",
    "ExplainabilityConfig",
    "InterAgentConfig",
    "ReasoningChainConfig",
    "get_explainability_config",
    "configure_explainability",
    "reset_explainability_config",
    # Reasoning Chain Builder
    "ReasoningChainBuilder",
    "get_reasoning_chain_builder",
    "configure_reasoning_chain_builder",
    "reset_reasoning_chain_builder",
    # Alternatives Analyzer
    "AlternativesAnalyzer",
    "get_alternatives_analyzer",
    "configure_alternatives_analyzer",
    "reset_alternatives_analyzer",
    # Confidence Quantifier
    "ConfidenceQuantifier",
    "get_confidence_quantifier",
    "configure_confidence_quantifier",
    "reset_confidence_quantifier",
    # Consistency Verifier
    "ConsistencyVerifier",
    "get_consistency_verifier",
    "configure_consistency_verifier",
    "reset_consistency_verifier",
    # Inter-Agent Verifier
    "InterAgentVerifier",
    "get_inter_agent_verifier",
    "configure_inter_agent_verifier",
    "reset_inter_agent_verifier",
    # Main Service
    "UniversalExplainabilityService",
    "get_explainability_service",
    "configure_explainability_service",
    "reset_explainability_service",
    # Mixin
    "ExplainabilityMixin",
]
