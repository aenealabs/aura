"""Constitutional AI Agent Configuration Defaults.

This module provides default Constitutional AI configurations for different
agent types in Project Aura. Each agent can have domain-specific tags and
principle filters applied automatically.
"""

from typing import Dict, List, Optional

from src.agents.constitutional_mixin import ConstitutionalMixinConfig

# Domain tags by agent type
AGENT_DOMAIN_TAGS: Dict[str, List[str]] = {
    # Code generation agents
    "CoderAgent": ["code_generation", "security", "compliance", "best_practices"],
    "CodeGeneratorAgent": ["code_generation", "security", "compliance"],
    # Security-focused agents
    "ReviewerAgent": ["security_review", "vulnerability_analysis", "compliance"],
    "SecurityAgent": [
        "security",
        "threat_analysis",
        "compliance",
        "vulnerability_analysis",
    ],
    "ThreatIntelligenceAgent": ["threat_analysis", "security", "intelligence"],
    "VulnerabilityAgent": ["vulnerability_analysis", "security", "remediation"],
    # Validation and testing agents
    "ValidatorAgent": ["code_validation", "security_testing", "quality"],
    "TestAgent": ["testing", "quality_assurance", "code_validation"],
    # Analysis agents
    "AnalysisAgent": ["code_analysis", "security", "quality"],
    "GraphRAGAgent": ["knowledge_retrieval", "context", "accuracy"],
    # Orchestration agents
    "OrchestratorAgent": ["orchestration", "coordination", "security"],
    "PlannerAgent": ["planning", "coordination", "security"],
    # DevOps agents
    "DeploymentAgent": ["deployment", "security", "compliance", "infrastructure"],
    "InfrastructureAgent": ["infrastructure", "security", "compliance"],
    # General purpose
    "BaseAgent": ["general", "security"],
}

# Principles that should be applied to all agents
UNIVERSAL_PRINCIPLES: List[str] = [
    "safety",
    "accuracy",
    "transparency",
]

# Agent-specific principle overrides (when you want to limit to specific principles)
AGENT_PRINCIPLE_OVERRIDES: Dict[str, List[str]] = {
    # Security agents should have full security principle coverage
    "SecurityAgent": None,  # None means use all applicable
    "ThreatIntelligenceAgent": None,
    # Code generation needs security + code quality principles
    "CoderAgent": None,
    # Orchestrator focuses on coordination safety
    "OrchestratorAgent": [
        "safety",
        "coordination_safety",
        "resource_management",
        "escalation_policy",
    ],
}

# Autonomy levels that skip constitutional checks by agent type
AGENT_SKIP_AUTONOMY_LEVELS: Dict[str, List[str]] = {
    # High-trust agents can skip more
    "OrchestratorAgent": ["FULL_AUTONOMOUS", "HIGH_AUTONOMOUS"],
    # Most agents only skip full autonomous
    "default": ["FULL_AUTONOMOUS"],
}

# Agents that should block on critical issues (most should)
AGENTS_BLOCK_ON_CRITICAL: Dict[str, bool] = {
    "CoderAgent": True,
    "SecurityAgent": True,
    "DeploymentAgent": True,
    "InfrastructureAgent": True,
    # Analysis agents may want to report issues without blocking
    "AnalysisAgent": False,
    "GraphRAGAgent": False,
    "default": True,
}

# Agents that should enable HITL escalation
AGENTS_ENABLE_HITL: Dict[str, bool] = {
    "CoderAgent": True,
    "SecurityAgent": True,
    "DeploymentAgent": True,
    "InfrastructureAgent": True,
    "OrchestratorAgent": True,
    # Some agents handle HITL differently
    "AnalysisAgent": False,
    "default": True,
}


def get_domain_tags(agent_name: str) -> List[str]:
    """Get domain tags for an agent type.

    Args:
        agent_name: Name of the agent class

    Returns:
        List of domain tags for the agent
    """
    return AGENT_DOMAIN_TAGS.get(
        agent_name, AGENT_DOMAIN_TAGS.get("BaseAgent", ["general"])
    )


def get_applicable_principles(agent_name: str) -> Optional[List[str]]:
    """Get applicable principles for an agent type.

    Args:
        agent_name: Name of the agent class

    Returns:
        List of principle IDs or None for all applicable
    """
    return AGENT_PRINCIPLE_OVERRIDES.get(agent_name)


def get_skip_autonomy_levels(agent_name: str) -> List[str]:
    """Get autonomy levels that skip constitutional checks.

    Args:
        agent_name: Name of the agent class

    Returns:
        List of autonomy level strings to skip
    """
    return AGENT_SKIP_AUTONOMY_LEVELS.get(
        agent_name, AGENT_SKIP_AUTONOMY_LEVELS["default"]
    )


def should_block_on_critical(agent_name: str) -> bool:
    """Check if agent should block on critical issues.

    Args:
        agent_name: Name of the agent class

    Returns:
        True if agent should block on critical issues
    """
    return AGENTS_BLOCK_ON_CRITICAL.get(agent_name, AGENTS_BLOCK_ON_CRITICAL["default"])


def should_enable_hitl(agent_name: str) -> bool:
    """Check if agent should enable HITL escalation.

    Args:
        agent_name: Name of the agent class

    Returns:
        True if agent should enable HITL escalation
    """
    return AGENTS_ENABLE_HITL.get(agent_name, AGENTS_ENABLE_HITL["default"])


def get_default_config(agent_name: str) -> ConstitutionalMixinConfig:
    """Get default constitutional config for an agent type.

    Creates a ConstitutionalMixinConfig with appropriate defaults based
    on the agent type. Agents can override these defaults when initializing
    the mixin.

    Args:
        agent_name: Name of the agent class (e.g., "CoderAgent", "SecurityAgent")

    Returns:
        ConstitutionalMixinConfig with agent-appropriate defaults

    Example:
        >>> config = get_default_config("CoderAgent")
        >>> config.domain_tags
        ['code_generation', 'security', 'compliance', 'best_practices']
    """
    return ConstitutionalMixinConfig(
        domain_tags=get_domain_tags(agent_name),
        applicable_principles=get_applicable_principles(agent_name),
        skip_for_autonomy_levels=get_skip_autonomy_levels(agent_name),
        block_on_critical=should_block_on_critical(agent_name),
        enable_hitl_escalation=should_enable_hitl(agent_name),
        max_revision_iterations=None,  # Use service default
        include_in_metrics=True,
        mock_mode=False,
    )


def get_config_with_overrides(
    agent_name: str,
    domain_tags: Optional[List[str]] = None,
    applicable_principles: Optional[List[str]] = None,
    skip_for_autonomy_levels: Optional[List[str]] = None,
    block_on_critical: Optional[bool] = None,
    enable_hitl_escalation: Optional[bool] = None,
    max_revision_iterations: Optional[int] = None,
    include_in_metrics: Optional[bool] = None,
    mock_mode: Optional[bool] = None,
) -> ConstitutionalMixinConfig:
    """Get config with selective overrides.

    Starts with agent defaults and applies any specified overrides.
    This is useful when you want most defaults but need to tweak
    specific settings.

    Args:
        agent_name: Name of the agent class
        domain_tags: Override domain tags
        applicable_principles: Override applicable principles
        skip_for_autonomy_levels: Override skip levels
        block_on_critical: Override block behavior
        enable_hitl_escalation: Override HITL behavior
        max_revision_iterations: Override max iterations
        include_in_metrics: Override metrics inclusion
        mock_mode: Override mock mode

    Returns:
        ConstitutionalMixinConfig with defaults and overrides applied

    Example:
        >>> config = get_config_with_overrides(
        ...     "CoderAgent",
        ...     block_on_critical=False,  # Override just this
        ... )
    """
    base_config = get_default_config(agent_name)

    return ConstitutionalMixinConfig(
        domain_tags=domain_tags if domain_tags is not None else base_config.domain_tags,
        applicable_principles=(
            applicable_principles
            if applicable_principles is not None
            else base_config.applicable_principles
        ),
        skip_for_autonomy_levels=(
            skip_for_autonomy_levels
            if skip_for_autonomy_levels is not None
            else base_config.skip_for_autonomy_levels
        ),
        block_on_critical=(
            block_on_critical
            if block_on_critical is not None
            else base_config.block_on_critical
        ),
        enable_hitl_escalation=(
            enable_hitl_escalation
            if enable_hitl_escalation is not None
            else base_config.enable_hitl_escalation
        ),
        max_revision_iterations=(
            max_revision_iterations
            if max_revision_iterations is not None
            else base_config.max_revision_iterations
        ),
        include_in_metrics=(
            include_in_metrics
            if include_in_metrics is not None
            else base_config.include_in_metrics
        ),
        mock_mode=mock_mode if mock_mode is not None else base_config.mock_mode,
    )


# Pre-configured configs for common scenarios
STRICT_SECURITY_CONFIG = ConstitutionalMixinConfig(
    domain_tags=["security", "compliance", "vulnerability_analysis"],
    applicable_principles=None,  # All applicable
    skip_for_autonomy_levels=[],  # Never skip
    block_on_critical=True,
    enable_hitl_escalation=True,
    max_revision_iterations=5,  # More iterations for security
    include_in_metrics=True,
    mock_mode=False,
)

LENIENT_ANALYSIS_CONFIG = ConstitutionalMixinConfig(
    domain_tags=["analysis", "reporting"],
    applicable_principles=["safety", "accuracy"],
    skip_for_autonomy_levels=["FULL_AUTONOMOUS", "HIGH_AUTONOMOUS"],
    block_on_critical=False,  # Don't block, just report
    enable_hitl_escalation=False,
    max_revision_iterations=2,
    include_in_metrics=True,
    mock_mode=False,
)

DEVELOPMENT_CONFIG = ConstitutionalMixinConfig(
    domain_tags=["development", "testing"],
    applicable_principles=None,
    skip_for_autonomy_levels=["FULL_AUTONOMOUS"],
    block_on_critical=False,  # Don't block in dev
    enable_hitl_escalation=False,  # No HITL in dev
    max_revision_iterations=1,  # Fast iterations
    include_in_metrics=False,  # Don't pollute metrics
    mock_mode=True,  # Use mock responses
)
