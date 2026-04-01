"""
Project Aura - Integration Configuration

Implements ADR-023: AgentCore Gateway Integration for Dual-Track Architecture

This module provides the configuration infrastructure for switching between:
- DEFENSE mode: No external dependencies, GovCloud-ready, air-gap compatible
- ENTERPRISE mode: AgentCore Gateway enabled, MCP protocol, external tools
- HYBRID mode: Per-repository configuration

Usage:
    >>> from src.config import IntegrationMode, get_integration_config
    >>> config = get_integration_config()
    >>> if config.mode == IntegrationMode.ENTERPRISE:
    ...     # Enable MCP Gateway features
    ...     pass
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class IntegrationMode(Enum):
    """
    Platform integration mode determining external connectivity.

    DEFENSE: No external dependencies, suitable for GovCloud/air-gap deployments.
             All agent operations use native Aura implementations.
             CMMC Level 3, NIST 800-53, FedRAMP compliant.

    ENTERPRISE: AgentCore Gateway enabled for MCP-compatible tool access.
                Supports Slack, Jira, PagerDuty, and 100+ external tools.
                Configurable autonomy levels (AUDIT_ONLY, FULL_AUTONOMOUS).

    HYBRID: Per-repository configuration allowing mixed deployments.
            Some repositories use DEFENSE mode, others use ENTERPRISE.
            Useful for organizations with both classified and commercial projects.
    """

    DEFENSE = "defense"
    ENTERPRISE = "enterprise"
    HYBRID = "hybrid"


class ExternalToolCategory(Enum):
    """Categories of external tools available in ENTERPRISE mode."""

    NOTIFICATION = "notification"  # Slack, Teams, Email
    TICKETING = "ticketing"  # Jira, ServiceNow, Linear
    ALERTING = "alerting"  # PagerDuty, OpsGenie, VictorOps
    SOURCE_CONTROL = "source_control"  # GitHub, GitLab, Bitbucket
    OBSERVABILITY = "observability"  # Datadog, Splunk, New Relic
    SECURITY = "security"  # Snyk, SonarQube, Veracode
    CI_CD = "ci_cd"  # Jenkins, CircleCI, GitHub Actions


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CustomerMCPBudget:
    """
    Per-customer MCP Gateway budget configuration.

    Prevents runaway costs from excessive external tool invocations.
    Alerts are sent when spend reaches threshold percentage.
    Hard limit blocks further invocations until next billing period.
    """

    customer_id: str
    monthly_limit_usd: float = 100.00  # Default $100/month
    current_spend_usd: float = 0.0
    alert_threshold_pct: float = 0.80  # Alert at 80%
    hard_limit_enabled: bool = True  # Block at 100%

    # Pricing constants (AgentCore Gateway)
    INVOKE_TOOL_COST_PER_REQUEST: float = 0.000005  # $5 per million
    SEARCH_TOOL_COST_PER_REQUEST: float = 0.000025  # $25 per million
    TOOL_INDEX_COST_PER_100: float = 0.02  # $0.02 per 100 tools/month

    @property
    def remaining_budget_usd(self) -> float:
        """Calculate remaining budget for this billing period."""
        return max(0.0, self.monthly_limit_usd - self.current_spend_usd)

    @property
    def usage_percentage(self) -> float:
        """Calculate current usage as percentage of limit."""
        if self.monthly_limit_usd == 0:
            return 100.0
        return (self.current_spend_usd / self.monthly_limit_usd) * 100

    @property
    def should_alert(self) -> bool:
        """Check if alert threshold has been reached."""
        return self.usage_percentage >= (self.alert_threshold_pct * 100)

    @property
    def is_budget_exceeded(self) -> bool:
        """Check if hard budget limit has been exceeded."""
        return (
            self.hard_limit_enabled and self.current_spend_usd >= self.monthly_limit_usd
        )

    def record_invocation(self, is_search: bool = False) -> bool:
        """
        Record a tool invocation and update spend.

        Returns True if invocation is allowed, False if budget exceeded.
        """
        cost = (
            self.SEARCH_TOOL_COST_PER_REQUEST
            if is_search
            else self.INVOKE_TOOL_COST_PER_REQUEST
        )

        if self.is_budget_exceeded:
            logger.warning(
                f"MCP budget exceeded for customer {self.customer_id}: "
                f"${self.current_spend_usd:.2f} / ${self.monthly_limit_usd:.2f}"
            )
            return False

        self.current_spend_usd += cost
        return True


@dataclass
class ExternalToolConfig:
    """Configuration for an external tool integration."""

    tool_id: str
    tool_name: str
    category: ExternalToolCategory
    enabled: bool = True
    mcp_endpoint: str | None = None
    oauth_client_id: str | None = None
    rate_limit_per_minute: int = 60
    requires_customer_auth: bool = False  # Customer must provide OAuth token

    # Tool-specific settings
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class IntegrationConfig:
    """
    Platform-wide integration configuration.

    Loaded from environment variables or SSM Parameter Store.
    Controls which features are available based on deployment mode.
    """

    mode: IntegrationMode = IntegrationMode.DEFENSE
    environment: str = "dev"

    # AgentCore Gateway settings (ENTERPRISE mode only)
    gateway_enabled: bool = False
    gateway_endpoint: str | None = None
    gateway_region: str = "us-east-1"

    # MCP settings
    mcp_protocol_version: str = "1.0"
    mcp_timeout_seconds: int = 30
    mcp_max_retries: int = 3

    # A2A (Agent-to-Agent) settings
    a2a_enabled: bool = False
    a2a_discovery_endpoint: str | None = None

    # External tools configuration
    external_tools: list[ExternalToolConfig] = field(default_factory=list)

    # Default customer budget
    default_customer_budget: CustomerMCPBudget = field(
        default_factory=lambda: CustomerMCPBudget(customer_id="default")
    )

    # Feature flags
    feature_flags: dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set derived values based on mode."""
        if self.mode == IntegrationMode.DEFENSE:
            # Force disable all external integrations in DEFENSE mode
            self.gateway_enabled = False
            self.a2a_enabled = False
            self.external_tools = []
            logger.info("DEFENSE mode: All external integrations disabled")
        elif self.mode == IntegrationMode.ENTERPRISE:
            # Enable gateway by default in ENTERPRISE mode
            if self.gateway_endpoint is None:
                self.gateway_endpoint = (
                    f"https://bedrock-agentcore.{self.gateway_region}.amazonaws.com"
                )
            self.gateway_enabled = True
            logger.info(
                f"ENTERPRISE mode: AgentCore Gateway enabled at {self.gateway_endpoint}"
            )

    @property
    def is_defense_mode(self) -> bool:
        """Check if running in DEFENSE mode (no external deps)."""
        return self.mode == IntegrationMode.DEFENSE

    @property
    def is_enterprise_mode(self) -> bool:
        """Check if running in ENTERPRISE mode (Gateway enabled)."""
        return self.mode == IntegrationMode.ENTERPRISE

    @property
    def is_hybrid_mode(self) -> bool:
        """Check if running in HYBRID mode (per-repo config)."""
        return self.mode == IntegrationMode.HYBRID

    def is_tool_enabled(self, tool_id: str) -> bool:
        """Check if a specific external tool is enabled."""
        if self.is_defense_mode:
            return False
        for tool in self.external_tools:
            if tool.tool_id == tool_id:
                return tool.enabled
        return False

    def get_tool_config(self, tool_id: str) -> ExternalToolConfig | None:
        """Get configuration for a specific tool."""
        for tool in self.external_tools:
            if tool.tool_id == tool_id:
                return tool
        return None

    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature flag is enabled."""
        # DEFENSE mode disables all MCP-related features
        if self.is_defense_mode and feature_name.startswith("mcp_"):
            return False
        return self.feature_flags.get(feature_name, False)


# =============================================================================
# Configuration Loading
# =============================================================================


def _load_from_ssm(parameter_name: str, default: str) -> str:
    """Load configuration value from AWS SSM Parameter Store."""
    try:
        import boto3

        ssm = boto3.client("ssm")
        response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
        return str(response["Parameter"]["Value"])
    except Exception as e:
        logger.debug(f"SSM parameter {parameter_name} not found, using default: {e}")
        return default


def _parse_integration_mode(mode_str: str) -> IntegrationMode:
    """Parse integration mode from string."""
    mode_str = mode_str.lower().strip()
    try:
        return IntegrationMode(mode_str)
    except ValueError:
        logger.warning(f"Invalid integration mode '{mode_str}', defaulting to DEFENSE")
        return IntegrationMode.DEFENSE


def _load_external_tools(config: IntegrationConfig) -> list[ExternalToolConfig]:
    """Load external tool configurations for ENTERPRISE mode."""
    if config.is_defense_mode:
        return []

    # Default external tools available in ENTERPRISE mode
    default_tools = [
        ExternalToolConfig(
            tool_id="slack",
            tool_name="Slack",
            category=ExternalToolCategory.NOTIFICATION,
            enabled=True,
            mcp_endpoint="mcp://slack.mcp.aws.amazon.com",
            requires_customer_auth=True,
            settings={
                "default_channel": "#aura-alerts",
                "mention_on_critical": True,
            },
        ),
        ExternalToolConfig(
            tool_id="jira",
            tool_name="Jira",
            category=ExternalToolCategory.TICKETING,
            enabled=True,
            mcp_endpoint="mcp://jira.mcp.aws.amazon.com",
            requires_customer_auth=True,
            settings={
                "default_project": None,  # Customer must configure
                "default_issue_type": "Bug",
                "auto_assign": False,
            },
        ),
        ExternalToolConfig(
            tool_id="pagerduty",
            tool_name="PagerDuty",
            category=ExternalToolCategory.ALERTING,
            enabled=True,
            mcp_endpoint="mcp://pagerduty.mcp.aws.amazon.com",
            requires_customer_auth=True,
            settings={
                "severity_mapping": {
                    "CRITICAL": "critical",
                    "HIGH": "error",
                    "MEDIUM": "warning",
                    "LOW": "info",
                },
            },
        ),
        ExternalToolConfig(
            tool_id="github",
            tool_name="GitHub",
            category=ExternalToolCategory.SOURCE_CONTROL,
            enabled=True,
            mcp_endpoint="mcp://github.mcp.aws.amazon.com",
            requires_customer_auth=True,
            settings={
                "auto_create_branch": True,
                "require_review": True,
                "default_reviewers": [],
            },
        ),
        ExternalToolConfig(
            tool_id="datadog",
            tool_name="Datadog",
            category=ExternalToolCategory.OBSERVABILITY,
            enabled=False,  # Disabled by default, customer must enable
            mcp_endpoint="mcp://datadog.mcp.aws.amazon.com",
            requires_customer_auth=True,
            settings={
                "metric_prefix": "aura.",
                "default_tags": ["source:aura"],
            },
        ),
    ]

    return default_tools


@lru_cache(maxsize=1)
def get_integration_config() -> IntegrationConfig:
    """
    Get the platform integration configuration.

    Configuration is loaded from (in priority order):
    1. Environment variables
    2. SSM Parameter Store
    3. Default values

    Returns a cached IntegrationConfig instance.
    Use clear_integration_config_cache() to refresh.
    """
    environment = os.getenv("ENVIRONMENT", "dev")

    # Load integration mode
    mode_env = os.getenv("AURA_INTEGRATION_MODE")
    if mode_env is None:
        # Try SSM Parameter Store
        ssm_param = f"/aura/{environment}/integration-mode"
        mode_env = _load_from_ssm(ssm_param, "defense")

    mode = _parse_integration_mode(mode_env)

    # Load gateway region
    gateway_region = os.getenv(
        "AURA_GATEWAY_REGION",
        os.getenv("AWS_REGION", "us-east-1"),
    )

    # Create base config
    config = IntegrationConfig(
        mode=mode,
        environment=environment,
        gateway_region=gateway_region,
        mcp_timeout_seconds=int(os.getenv("AURA_MCP_TIMEOUT", "30")),
        mcp_max_retries=int(os.getenv("AURA_MCP_RETRIES", "3")),
        a2a_enabled=os.getenv("AURA_A2A_ENABLED", "false").lower() == "true",
        feature_flags={
            "mcp_semantic_search": os.getenv("AURA_MCP_SEARCH", "true").lower()
            == "true",
            "mcp_cost_tracking": os.getenv("AURA_MCP_COST_TRACKING", "true").lower()
            == "true",
            "a2a_discovery": os.getenv("AURA_A2A_DISCOVERY", "false").lower() == "true",
        },
    )

    # Load external tools for ENTERPRISE mode
    config.external_tools = _load_external_tools(config)

    logger.info(
        f"Integration config loaded: mode={config.mode.value}, "
        f"env={config.environment}, gateway_enabled={config.gateway_enabled}"
    )

    return config


def clear_integration_config_cache() -> None:
    """Clear the cached integration configuration."""
    get_integration_config.cache_clear()
    logger.info("Integration config cache cleared")


# =============================================================================
# Utility Functions
# =============================================================================


def require_enterprise_mode(func: F) -> F:
    """
    Decorator that raises an error if not in ENTERPRISE mode.

    Use on functions that require external integrations.
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        config = get_integration_config()
        if config.is_defense_mode:
            raise RuntimeError(
                f"Function {func.__name__} requires ENTERPRISE mode. "
                f"Current mode: {config.mode.value}. "
                "This function uses external integrations not available in DEFENSE mode."
            )
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_defense_mode(func: F) -> F:
    """
    Decorator that raises an error if not in DEFENSE mode.

    Use on functions that must not have external dependencies.
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        config = get_integration_config()
        if not config.is_defense_mode:
            raise RuntimeError(
                f"Function {func.__name__} requires DEFENSE mode. "
                f"Current mode: {config.mode.value}. "
                "This function is for air-gapped/GovCloud deployments only."
            )
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def get_mode_for_repository(repository_url: str) -> IntegrationMode:
    """
    Get the integration mode for a specific repository (HYBRID mode).

    In HYBRID mode, repositories can be configured individually.
    Defense/classified repos use DEFENSE mode, others use ENTERPRISE.
    """
    config = get_integration_config()

    if not config.is_hybrid_mode:
        return config.mode

    # TODO: Load repository-specific configuration from database
    # For now, check for common defense/government indicators
    defense_indicators = [
        ".gov",
        ".mil",
        "classified",
        "secret",
        "govcloud",
        "cmmc",
        "fedramp",
    ]

    repo_lower = repository_url.lower()
    for indicator in defense_indicators:
        if indicator in repo_lower:
            logger.info(
                f"Repository {repository_url} matched defense indicator '{indicator}', "
                "using DEFENSE mode"
            )
            return IntegrationMode.DEFENSE

    return IntegrationMode.ENTERPRISE
