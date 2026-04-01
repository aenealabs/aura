"""Project Aura - Agent Module

Core agent implementations for autonomous code intelligence.
"""

from .adaptive_intelligence_agent import (
    AdaptiveIntelligenceAgent,
    AdaptiveRecommendation,
    create_adaptive_intelligence_agent,
)
from .adr_generator_agent import ADRGeneratorAgent, create_adr_generator_agent
from .agent_orchestrator import (
    ContextRetrievalService,
    EmbeddingAgent,
    GraphBuilderAgent,
    InputSanitizer,
    OpenSearchVectorStore,
    System2Orchestrator,
    create_system2_orchestrator,
)
from .architecture_review_agent import (
    ArchitectureReviewAgent,
    create_architecture_review_agent,
)
from .coder_agent import CoderAgent, create_coder_agent
from .context_objects import ContextItem, ContextSource, HybridContext
from .monitoring_service import AgentRole, MonitorAgent
from .reviewer_agent import ReviewerAgent, create_reviewer_agent
from .threat_intelligence_agent import ThreatIntelligenceAgent, ThreatIntelReport
from .validator_agent import ValidatorAgent, create_validator_agent

__all__ = [
    # Core orchestration
    "System2Orchestrator",
    "create_system2_orchestrator",
    # Individual agents
    "CoderAgent",
    "create_coder_agent",
    "ReviewerAgent",
    "create_reviewer_agent",
    "ValidatorAgent",
    "create_validator_agent",
    "AdaptiveIntelligenceAgent",
    "create_adaptive_intelligence_agent",
    "AdaptiveRecommendation",
    "ArchitectureReviewAgent",
    "create_architecture_review_agent",
    "ADRGeneratorAgent",
    "create_adr_generator_agent",
    "ThreatIntelligenceAgent",
    "ThreatIntelReport",
    # Context and retrieval
    "ContextRetrievalService",
    "GraphBuilderAgent",
    "OpenSearchVectorStore",
    "EmbeddingAgent",
    "HybridContext",
    "ContextItem",
    "ContextSource",
    # Utilities
    "InputSanitizer",
    "MonitorAgent",
    "AgentRole",
]
