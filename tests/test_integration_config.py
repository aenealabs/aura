"""
Tests for Project Aura Integration Configuration Module

Tests the dual-track architecture configuration (ADR-023):
- Defense mode: No external dependencies, GovCloud-ready
- Enterprise mode: AgentCore Gateway enabled, MCP protocol
- Hybrid mode: Per-repository configuration
"""

import os
import platform

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from unittest.mock import patch

from src.config.integration_config import (
    CustomerMCPBudget,
    ExternalToolCategory,
    ExternalToolConfig,
    IntegrationConfig,
    IntegrationMode,
    _parse_integration_mode,
    clear_integration_config_cache,
    get_integration_config,
    get_mode_for_repository,
    require_defense_mode,
    require_enterprise_mode,
)

# =============================================================================
# IntegrationMode Enum Tests
# =============================================================================


class TestIntegrationMode:
    """Tests for IntegrationMode enum."""

    def test_defense_mode_value(self):
        """Defense mode should have 'defense' string value."""
        assert IntegrationMode.DEFENSE.value == "defense"

    def test_enterprise_mode_value(self):
        """Enterprise mode should have 'enterprise' string value."""
        assert IntegrationMode.ENTERPRISE.value == "enterprise"

    def test_hybrid_mode_value(self):
        """Hybrid mode should have 'hybrid' string value."""
        assert IntegrationMode.HYBRID.value == "hybrid"

    def test_parse_defense_mode(self):
        """Should parse 'defense' string to DEFENSE mode."""
        assert _parse_integration_mode("defense") == IntegrationMode.DEFENSE
        assert _parse_integration_mode("DEFENSE") == IntegrationMode.DEFENSE
        assert _parse_integration_mode("  defense  ") == IntegrationMode.DEFENSE

    def test_parse_enterprise_mode(self):
        """Should parse 'enterprise' string to ENTERPRISE mode."""
        assert _parse_integration_mode("enterprise") == IntegrationMode.ENTERPRISE

    def test_parse_hybrid_mode(self):
        """Should parse 'hybrid' string to HYBRID mode."""
        assert _parse_integration_mode("hybrid") == IntegrationMode.HYBRID

    def test_parse_invalid_mode_defaults_to_defense(self):
        """Invalid mode strings should default to DEFENSE for security."""
        assert _parse_integration_mode("invalid") == IntegrationMode.DEFENSE
        assert _parse_integration_mode("") == IntegrationMode.DEFENSE
        assert _parse_integration_mode("commercial") == IntegrationMode.DEFENSE


# =============================================================================
# CustomerMCPBudget Tests
# =============================================================================


class TestCustomerMCPBudget:
    """Tests for CustomerMCPBudget cost tracking."""

    def test_default_budget(self):
        """Default budget should be $100/month."""
        budget = CustomerMCPBudget(customer_id="test-customer")
        assert budget.monthly_limit_usd == 100.00
        assert budget.current_spend_usd == 0.0
        assert budget.alert_threshold_pct == 0.80

    def test_remaining_budget_calculation(self):
        """Should correctly calculate remaining budget."""
        budget = CustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=100.00,
            current_spend_usd=25.00,
        )
        assert budget.remaining_budget_usd == 75.00

    def test_remaining_budget_never_negative(self):
        """Remaining budget should never be negative."""
        budget = CustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=100.00,
            current_spend_usd=150.00,
        )
        assert budget.remaining_budget_usd == 0.0

    def test_usage_percentage(self):
        """Should correctly calculate usage percentage."""
        budget = CustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=100.00,
            current_spend_usd=80.00,
        )
        assert budget.usage_percentage == 80.0

    def test_usage_percentage_zero_limit(self):
        """Should return 100% when monthly limit is zero."""
        budget = CustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=0.0,
            current_spend_usd=0.0,
        )
        assert budget.usage_percentage == 100.0

    def test_should_alert_at_threshold(self):
        """Should trigger alert at 80% threshold."""
        budget = CustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=100.00,
            current_spend_usd=80.00,
            alert_threshold_pct=0.80,
        )
        assert budget.should_alert is True

    def test_should_not_alert_below_threshold(self):
        """Should not trigger alert below threshold."""
        budget = CustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=100.00,
            current_spend_usd=70.00,
            alert_threshold_pct=0.80,
        )
        assert budget.should_alert is False

    def test_budget_exceeded_with_hard_limit(self):
        """Should detect budget exceeded when hard limit enabled."""
        budget = CustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=100.00,
            current_spend_usd=100.00,
            hard_limit_enabled=True,
        )
        assert budget.is_budget_exceeded is True

    def test_budget_not_exceeded_without_hard_limit(self):
        """Should not block when hard limit disabled."""
        budget = CustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=100.00,
            current_spend_usd=100.00,
            hard_limit_enabled=False,
        )
        assert budget.is_budget_exceeded is False

    def test_record_invocation_success(self):
        """Should record invocation and update spend."""
        budget = CustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=100.00,
            current_spend_usd=0.0,
        )
        result = budget.record_invocation(is_search=False)
        assert result is True
        assert budget.current_spend_usd == budget.INVOKE_TOOL_COST_PER_REQUEST

    def test_record_search_invocation(self):
        """Should record search invocation with higher cost."""
        budget = CustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=100.00,
            current_spend_usd=0.0,
        )
        result = budget.record_invocation(is_search=True)
        assert result is True
        assert budget.current_spend_usd == budget.SEARCH_TOOL_COST_PER_REQUEST

    def test_record_invocation_blocked_at_limit(self):
        """Should block invocation when budget exceeded."""
        budget = CustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=100.00,
            current_spend_usd=100.00,
            hard_limit_enabled=True,
        )
        result = budget.record_invocation()
        assert result is False

    def test_pricing_constants(self):
        """Verify AgentCore Gateway pricing constants."""
        budget = CustomerMCPBudget(customer_id="test")
        assert budget.INVOKE_TOOL_COST_PER_REQUEST == 0.000005  # $5/million
        assert budget.SEARCH_TOOL_COST_PER_REQUEST == 0.000025  # $25/million
        assert budget.TOOL_INDEX_COST_PER_100 == 0.02  # $0.02/100 tools


# =============================================================================
# ExternalToolConfig Tests
# =============================================================================


class TestExternalToolConfig:
    """Tests for ExternalToolConfig."""

    def test_tool_config_defaults(self):
        """Tool config should have sensible defaults."""
        tool = ExternalToolConfig(
            tool_id="test-tool",
            tool_name="Test Tool",
            category=ExternalToolCategory.NOTIFICATION,
        )
        assert tool.enabled is True
        assert tool.rate_limit_per_minute == 60
        assert tool.requires_customer_auth is False
        assert tool.settings == {}

    def test_tool_categories(self):
        """All expected tool categories should exist."""
        expected_categories = [
            "NOTIFICATION",
            "TICKETING",
            "ALERTING",
            "SOURCE_CONTROL",
            "OBSERVABILITY",
            "SECURITY",
            "CI_CD",
        ]
        actual = [c.name for c in ExternalToolCategory]
        assert set(expected_categories) == set(actual)


# =============================================================================
# IntegrationConfig Tests
# =============================================================================


class TestIntegrationConfig:
    """Tests for IntegrationConfig."""

    def test_defense_mode_disables_all_integrations(self):
        """Defense mode should force-disable all external integrations."""
        config = IntegrationConfig(
            mode=IntegrationMode.DEFENSE,
            gateway_enabled=True,  # Should be overridden
            a2a_enabled=True,  # Should be overridden
            external_tools=[
                ExternalToolConfig(
                    tool_id="slack",
                    tool_name="Slack",
                    category=ExternalToolCategory.NOTIFICATION,
                )
            ],
        )
        assert config.gateway_enabled is False
        assert config.a2a_enabled is False
        assert config.external_tools == []

    def test_enterprise_mode_enables_gateway(self):
        """Enterprise mode should enable gateway by default."""
        config = IntegrationConfig(
            mode=IntegrationMode.ENTERPRISE,
            gateway_region="us-west-2",
        )
        assert config.gateway_enabled is True
        assert (
            config.gateway_endpoint
            == "https://bedrock-agentcore.us-west-2.amazonaws.com"
        )

    def test_is_defense_mode_property(self):
        """is_defense_mode property should work correctly."""
        defense = IntegrationConfig(mode=IntegrationMode.DEFENSE)
        enterprise = IntegrationConfig(mode=IntegrationMode.ENTERPRISE)
        assert defense.is_defense_mode is True
        assert enterprise.is_defense_mode is False

    def test_is_enterprise_mode_property(self):
        """is_enterprise_mode property should work correctly."""
        defense = IntegrationConfig(mode=IntegrationMode.DEFENSE)
        enterprise = IntegrationConfig(mode=IntegrationMode.ENTERPRISE)
        assert defense.is_enterprise_mode is False
        assert enterprise.is_enterprise_mode is True

    def test_is_hybrid_mode_property(self):
        """is_hybrid_mode property should work correctly."""
        hybrid = IntegrationConfig(mode=IntegrationMode.HYBRID)
        defense = IntegrationConfig(mode=IntegrationMode.DEFENSE)
        assert hybrid.is_hybrid_mode is True
        assert defense.is_hybrid_mode is False

    def test_is_tool_enabled_defense_mode(self):
        """No tools should be enabled in defense mode."""
        config = IntegrationConfig(mode=IntegrationMode.DEFENSE)
        assert config.is_tool_enabled("slack") is False
        assert config.is_tool_enabled("jira") is False

    def test_is_tool_enabled_enterprise_mode(self):
        """Tools should be checkable in enterprise mode."""
        config = IntegrationConfig(
            mode=IntegrationMode.ENTERPRISE,
            external_tools=[
                ExternalToolConfig(
                    tool_id="slack",
                    tool_name="Slack",
                    category=ExternalToolCategory.NOTIFICATION,
                    enabled=True,
                ),
                ExternalToolConfig(
                    tool_id="jira",
                    tool_name="Jira",
                    category=ExternalToolCategory.TICKETING,
                    enabled=False,
                ),
            ],
        )
        assert config.is_tool_enabled("slack") is True
        assert config.is_tool_enabled("jira") is False
        assert config.is_tool_enabled("unknown") is False

    def test_get_tool_config(self):
        """Should return tool config by ID."""
        slack_config = ExternalToolConfig(
            tool_id="slack",
            tool_name="Slack",
            category=ExternalToolCategory.NOTIFICATION,
        )
        config = IntegrationConfig(
            mode=IntegrationMode.ENTERPRISE,
            external_tools=[slack_config],
        )
        assert config.get_tool_config("slack") == slack_config
        assert config.get_tool_config("unknown") is None

    def test_feature_flags_defense_mode_blocks_mcp(self):
        """MCP features should be blocked in defense mode."""
        config = IntegrationConfig(
            mode=IntegrationMode.DEFENSE,
            feature_flags={
                "mcp_semantic_search": True,
                "mcp_cost_tracking": True,
                "regular_feature": True,
            },
        )
        assert config.is_feature_enabled("mcp_semantic_search") is False
        assert config.is_feature_enabled("mcp_cost_tracking") is False
        assert config.is_feature_enabled("regular_feature") is True

    def test_feature_flags_enterprise_mode(self):
        """MCP features should work in enterprise mode."""
        config = IntegrationConfig(
            mode=IntegrationMode.ENTERPRISE,
            feature_flags={
                "mcp_semantic_search": True,
                "mcp_cost_tracking": False,
            },
        )
        assert config.is_feature_enabled("mcp_semantic_search") is True
        assert config.is_feature_enabled("mcp_cost_tracking") is False


# =============================================================================
# Configuration Loading Tests
# =============================================================================


class TestGetIntegrationConfig:
    """Tests for get_integration_config function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_integration_config_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_integration_config_cache()

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "defense"}, clear=False)
    def test_load_defense_mode_from_env(self):
        """Should load defense mode from environment variable."""
        config = get_integration_config()
        assert config.mode == IntegrationMode.DEFENSE
        assert config.gateway_enabled is False

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"}, clear=False)
    def test_load_enterprise_mode_from_env(self):
        """Should load enterprise mode from environment variable."""
        config = get_integration_config()
        assert config.mode == IntegrationMode.ENTERPRISE
        assert config.gateway_enabled is True

    @patch.dict(
        os.environ,
        {
            "AURA_INTEGRATION_MODE": "enterprise",
            "AURA_MCP_TIMEOUT": "60",
            "AURA_MCP_RETRIES": "5",
        },
        clear=False,
    )
    def test_load_mcp_settings_from_env(self):
        """Should load MCP settings from environment variables."""
        config = get_integration_config()
        assert config.mcp_timeout_seconds == 60
        assert config.mcp_max_retries == 5

    @patch.dict(
        os.environ,
        {
            "AURA_INTEGRATION_MODE": "enterprise",
            "AURA_A2A_ENABLED": "true",
        },
        clear=False,
    )
    def test_load_a2a_enabled_from_env(self):
        """Should load A2A setting from environment variable."""
        config = get_integration_config()
        assert config.a2a_enabled is True

    @patch.dict(os.environ, {}, clear=True)
    @patch("src.config.integration_config._load_from_ssm")
    def test_fallback_to_ssm(self, mock_ssm):
        """Should fall back to SSM when env var not set."""
        mock_ssm.return_value = "enterprise"
        config = get_integration_config()
        assert config.mode == IntegrationMode.ENTERPRISE
        mock_ssm.assert_called()

    def test_config_is_cached(self):
        """Config should be cached after first load."""
        with patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "defense"}):
            config1 = get_integration_config()
            config2 = get_integration_config()
            assert config1 is config2

    def test_cache_can_be_cleared(self):
        """Cache should be clearable."""
        with patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "defense"}):
            config1 = get_integration_config()
            clear_integration_config_cache()
        with patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"}):
            config2 = get_integration_config()
            assert config1.mode != config2.mode

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"}, clear=False)
    def test_enterprise_mode_loads_default_tools(self):
        """Enterprise mode should load default external tools."""
        config = get_integration_config()
        tool_ids = [t.tool_id for t in config.external_tools]
        assert "slack" in tool_ids
        assert "jira" in tool_ids
        assert "pagerduty" in tool_ids
        assert "github" in tool_ids


# =============================================================================
# Decorator Tests
# =============================================================================


class TestModeDecorators:
    """Tests for require_enterprise_mode and require_defense_mode decorators."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_integration_config_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_integration_config_cache()

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"}, clear=False)
    def test_require_enterprise_mode_allows_enterprise(self):
        """Should allow function execution in enterprise mode."""

        @require_enterprise_mode
        def enterprise_only_function():
            return "success"

        result = enterprise_only_function()
        assert result == "success"

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "defense"}, clear=False)
    def test_require_enterprise_mode_blocks_defense(self):
        """Should block function execution in defense mode."""

        @require_enterprise_mode
        def enterprise_only_function():
            return "success"

        with pytest.raises(RuntimeError) as exc_info:
            enterprise_only_function()
        assert "requires ENTERPRISE mode" in str(exc_info.value)

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "defense"}, clear=False)
    def test_require_defense_mode_allows_defense(self):
        """Should allow function execution in defense mode."""

        @require_defense_mode
        def defense_only_function():
            return "success"

        result = defense_only_function()
        assert result == "success"

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"}, clear=False)
    def test_require_defense_mode_blocks_enterprise(self):
        """Should block function execution in enterprise mode."""

        @require_defense_mode
        def defense_only_function():
            return "success"

        with pytest.raises(RuntimeError) as exc_info:
            defense_only_function()
        assert "requires DEFENSE mode" in str(exc_info.value)


# =============================================================================
# Hybrid Mode Repository Tests
# =============================================================================


class TestGetModeForRepository:
    """Tests for get_mode_for_repository function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_integration_config_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_integration_config_cache()

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "defense"}, clear=False)
    def test_defense_mode_returns_defense_for_all(self):
        """In DEFENSE mode, all repos should use defense."""
        mode = get_mode_for_repository("https://github.com/company/repo")
        assert mode == IntegrationMode.DEFENSE

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "hybrid"}, clear=False)
    def test_hybrid_mode_detects_gov_repos(self):
        """Should detect .gov repositories as defense."""
        mode = get_mode_for_repository("https://github.com/agency.gov/repo")
        assert mode == IntegrationMode.DEFENSE

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "hybrid"}, clear=False)
    def test_hybrid_mode_detects_mil_repos(self):
        """Should detect .mil repositories as defense."""
        mode = get_mode_for_repository("https://github.com/base.mil/project")
        assert mode == IntegrationMode.DEFENSE

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "hybrid"}, clear=False)
    def test_hybrid_mode_detects_classified_repos(self):
        """Should detect 'classified' in URL as defense."""
        mode = get_mode_for_repository("https://github.com/company/classified-project")
        assert mode == IntegrationMode.DEFENSE

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "hybrid"}, clear=False)
    def test_hybrid_mode_detects_cmmc_repos(self):
        """Should detect 'cmmc' in URL as defense."""
        mode = get_mode_for_repository("https://github.com/company/cmmc-compliant-app")
        assert mode == IntegrationMode.DEFENSE

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "hybrid"}, clear=False)
    def test_hybrid_mode_defaults_to_enterprise(self):
        """Regular repos should default to enterprise in hybrid mode."""
        mode = get_mode_for_repository("https://github.com/company/regular-repo")
        assert mode == IntegrationMode.ENTERPRISE

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"}, clear=False)
    def test_enterprise_mode_returns_enterprise_for_all(self):
        """In ENTERPRISE mode, all repos should use enterprise."""
        mode = get_mode_for_repository("https://github.com/agency.gov/repo")
        assert mode == IntegrationMode.ENTERPRISE
