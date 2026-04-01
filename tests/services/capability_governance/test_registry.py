"""
Tests for capability governance registry module.

Tests tool registration, lookup, and classification.
"""

import pytest

from src.services.capability_governance.contracts import (
    ToolCapability,
    ToolClassification,
)
from src.services.capability_governance.registry import (
    DEFAULT_TOOL_CAPABILITIES,
    CapabilityRegistry,
    get_capability_registry,
    reset_capability_registry,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def registry():
    """Create a fresh registry for each test."""
    reset_capability_registry()
    return CapabilityRegistry()


@pytest.fixture(autouse=True)
def cleanup():
    """Reset singleton after each test."""
    yield
    reset_capability_registry()


# =============================================================================
# DEFAULT_TOOL_CAPABILITIES Tests
# =============================================================================


class TestDefaultToolCapabilities:
    """Tests for default tool capabilities."""

    def test_default_capabilities_exist(self):
        """Verify default capabilities are defined."""
        assert len(DEFAULT_TOOL_CAPABILITIES) > 0
        assert "semantic_search" in DEFAULT_TOOL_CAPABILITIES
        assert "deploy_to_production" in DEFAULT_TOOL_CAPABILITIES

    def test_all_classifications_represented(self):
        """Verify all classification levels are represented."""
        classifications = {
            cap.classification for cap in DEFAULT_TOOL_CAPABILITIES.values()
        }
        assert ToolClassification.SAFE in classifications
        assert ToolClassification.MONITORING in classifications
        assert ToolClassification.DANGEROUS in classifications
        assert ToolClassification.CRITICAL in classifications

    def test_safe_tools(self):
        """Verify SAFE tools are correctly classified."""
        safe_tools = [
            "semantic_search",
            "describe_tool",
            "get_sandbox_status",
            "list_tools",
            "list_agents",
        ]
        for tool in safe_tools:
            assert tool in DEFAULT_TOOL_CAPABILITIES
            assert (
                DEFAULT_TOOL_CAPABILITIES[tool].classification
                == ToolClassification.SAFE
            )

    def test_monitoring_tools(self):
        """Verify MONITORING tools are correctly classified."""
        monitoring_tools = [
            "query_code_graph",
            "get_code_dependencies",
            "get_agent_metrics",
            "query_audit_logs",
        ]
        for tool in monitoring_tools:
            assert tool in DEFAULT_TOOL_CAPABILITIES
            assert (
                DEFAULT_TOOL_CAPABILITIES[tool].classification
                == ToolClassification.MONITORING
            )

    def test_dangerous_tools(self):
        """Verify DANGEROUS tools are correctly classified."""
        dangerous_tools = [
            "index_code_embedding",
            "destroy_sandbox",
            "write_config",
            "delete_index",
        ]
        for tool in dangerous_tools:
            assert tool in DEFAULT_TOOL_CAPABILITIES
            assert (
                DEFAULT_TOOL_CAPABILITIES[tool].classification
                == ToolClassification.DANGEROUS
            )

    def test_critical_tools(self):
        """Verify CRITICAL tools are correctly classified."""
        critical_tools = [
            "provision_sandbox",
            "deploy_to_production",
            "rotate_credentials",
            "modify_iam_policy",
        ]
        for tool in critical_tools:
            assert tool in DEFAULT_TOOL_CAPABILITIES
            assert (
                DEFAULT_TOOL_CAPABILITIES[tool].classification
                == ToolClassification.CRITICAL
            )


# =============================================================================
# CapabilityRegistry Tests
# =============================================================================


class TestCapabilityRegistry:
    """Tests for CapabilityRegistry class."""

    def test_initialization(self, registry):
        """Test registry initialization with defaults."""
        assert registry.is_registered("semantic_search")
        assert registry.is_registered("deploy_to_production")

    def test_register_tool(self, registry):
        """Test registering a new tool."""
        new_tool = ToolCapability(
            tool_name="custom_tool",
            classification=ToolClassification.MONITORING,
            description="A custom tool",
        )
        registry.register_tool(new_tool)

        assert registry.is_registered("custom_tool")
        assert registry.get_tool("custom_tool") == new_tool

    def test_register_tool_override(self, registry):
        """Test overriding an existing tool."""
        original = registry.get_tool("semantic_search")
        assert original is not None

        new_tool = ToolCapability(
            tool_name="semantic_search",
            classification=ToolClassification.MONITORING,
            description="Override",
        )
        registry.register_tool(new_tool)

        updated = registry.get_tool("semantic_search")
        assert updated.classification == ToolClassification.MONITORING

    def test_unregister_tool(self, registry):
        """Test unregistering a tool."""
        assert registry.is_registered("semantic_search")

        result = registry.unregister_tool("semantic_search")
        assert result is True
        assert registry.is_registered("semantic_search") is False

    def test_unregister_nonexistent_tool(self, registry):
        """Test unregistering a non-existent tool."""
        result = registry.unregister_tool("nonexistent_tool")
        assert result is False

    def test_get_tool(self, registry):
        """Test getting a tool capability."""
        tool = registry.get_tool("semantic_search")
        assert tool is not None
        assert tool.tool_name == "semantic_search"
        assert tool.classification == ToolClassification.SAFE

    def test_get_tool_not_found(self, registry):
        """Test getting a non-existent tool."""
        tool = registry.get_tool("nonexistent_tool")
        assert tool is None

    def test_get_classification(self, registry):
        """Test getting tool classification."""
        assert registry.get_classification("semantic_search") == ToolClassification.SAFE
        assert (
            registry.get_classification("query_code_graph")
            == ToolClassification.MONITORING
        )
        assert (
            registry.get_classification("destroy_sandbox")
            == ToolClassification.DANGEROUS
        )
        assert (
            registry.get_classification("deploy_to_production")
            == ToolClassification.CRITICAL
        )

    def test_get_classification_unknown_tool(self, registry):
        """Test getting classification for unknown tool (defaults to DANGEROUS)."""
        classification = registry.get_classification("unknown_tool")
        assert classification == ToolClassification.DANGEROUS

    def test_is_registered(self, registry):
        """Test checking if tool is registered."""
        assert registry.is_registered("semantic_search") is True
        assert registry.is_registered("unknown_tool") is False

    def test_list_tools_all(self, registry):
        """Test listing all tools."""
        tools = registry.list_tools()
        assert len(tools) > 0
        assert "semantic_search" in tools
        assert "deploy_to_production" in tools

    def test_list_tools_by_classification(self, registry):
        """Test listing tools by classification."""
        safe_tools = registry.list_tools(classification=ToolClassification.SAFE)
        assert "semantic_search" in safe_tools
        assert "deploy_to_production" not in safe_tools

        critical_tools = registry.list_tools(classification=ToolClassification.CRITICAL)
        assert "deploy_to_production" in critical_tools
        assert "semantic_search" not in critical_tools

    def test_list_tools_by_classification_grouped(self, registry):
        """Test listing tools grouped by classification."""
        grouped = registry.list_tools_by_classification()

        assert ToolClassification.SAFE in grouped
        assert ToolClassification.MONITORING in grouped
        assert ToolClassification.DANGEROUS in grouped
        assert ToolClassification.CRITICAL in grouped

        assert "semantic_search" in grouped[ToolClassification.SAFE]
        assert "deploy_to_production" in grouped[ToolClassification.CRITICAL]

    def test_get_rate_limit(self, registry):
        """Test getting rate limit for a tool."""
        rate_limit = registry.get_rate_limit("semantic_search")
        assert rate_limit == 120  # Default for semantic_search

        rate_limit = registry.get_rate_limit("deploy_to_production")
        assert rate_limit == 1  # CRITICAL tools have low rate limits

    def test_get_rate_limit_unknown_tool(self, registry):
        """Test getting rate limit for unknown tool."""
        rate_limit = registry.get_rate_limit("unknown_tool")
        assert rate_limit == 60  # Default

    def test_requires_justification(self, registry):
        """Test checking if tool requires justification."""
        assert registry.requires_justification("semantic_search") is False
        assert registry.requires_justification("deploy_to_production") is True
        assert registry.requires_justification("delete_index") is True

    def test_requires_justification_unknown_tool(self, registry):
        """Test checking justification for unknown tool."""
        assert registry.requires_justification("unknown_tool") is True

    def test_get_audit_sample_rate(self, registry):
        """Test getting audit sample rate."""
        assert (
            registry.get_audit_sample_rate("semantic_search") == 0.1
        )  # SAFE tools sampled
        assert (
            registry.get_audit_sample_rate("deploy_to_production") == 1.0
        )  # CRITICAL full audit

    def test_get_audit_sample_rate_unknown_tool(self, registry):
        """Test getting audit sample rate for unknown tool."""
        assert registry.get_audit_sample_rate("unknown_tool") == 1.0

    def test_validate_context(self, registry):
        """Test validating context for a tool."""
        # Tool with no context restrictions
        assert registry.validate_context("semantic_search", "production") is True
        assert registry.validate_context("semantic_search", "sandbox") is True

        # Tool with blocked contexts
        assert registry.validate_context("destroy_sandbox", "sandbox") is True
        assert registry.validate_context("destroy_sandbox", "production") is False

    def test_validate_context_unknown_tool(self, registry):
        """Test validating context for unknown tool."""
        assert registry.validate_context("unknown_tool", "production") is False

    def test_validate_action(self, registry):
        """Test validating action for a tool."""
        assert registry.validate_action("semantic_search", "read") is True
        assert registry.validate_action("semantic_search", "execute") is True
        assert registry.validate_action("semantic_search", "delete") is False

    def test_validate_action_unknown_tool(self, registry):
        """Test validating action for unknown tool."""
        assert registry.validate_action("unknown_tool", "read") is False

    def test_to_dict(self, registry):
        """Test converting registry to dictionary."""
        d = registry.to_dict()

        assert "semantic_search" in d
        assert d["semantic_search"]["classification"] == "safe"
        assert d["semantic_search"]["tool_name"] == "semantic_search"
        assert "rate_limit_per_minute" in d["semantic_search"]


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for global singleton."""

    def test_get_capability_registry(self):
        """Test getting global registry."""
        reset_capability_registry()
        reg1 = get_capability_registry()
        reg2 = get_capability_registry()
        assert reg1 is reg2

    def test_reset_capability_registry(self):
        """Test resetting global registry."""
        reg1 = get_capability_registry()
        reset_capability_registry()
        reg2 = get_capability_registry()
        assert reg1 is not reg2


# =============================================================================
# Tool-Specific Tests
# =============================================================================


class TestToolSpecificCapabilities:
    """Tests for specific tool capabilities."""

    def test_semantic_search_capability(self, registry):
        """Test semantic_search tool capability."""
        tool = registry.get_tool("semantic_search")
        assert tool.classification == ToolClassification.SAFE
        assert "read" in tool.allowed_actions
        assert "execute" in tool.allowed_actions
        assert tool.rate_limit_per_minute == 120
        assert tool.audit_sample_rate == 0.1

    def test_deploy_to_production_capability(self, registry):
        """Test deploy_to_production tool capability."""
        tool = registry.get_tool("deploy_to_production")
        assert tool.classification == ToolClassification.CRITICAL
        assert "execute" in tool.allowed_actions
        assert tool.requires_justification is True
        assert tool.max_concurrent == 1
        assert "staging" in tool.requires_context

    def test_provision_sandbox_capability(self, registry):
        """Test provision_sandbox tool capability."""
        tool = registry.get_tool("provision_sandbox")
        assert tool.classification == ToolClassification.CRITICAL
        assert "sandbox" in tool.requires_context or "test" in tool.requires_context
        assert "production" in tool.blocked_contexts
        assert tool.max_concurrent == 3

    def test_execute_arbitrary_code_capability(self, registry):
        """Test execute_arbitrary_code tool capability."""
        tool = registry.get_tool("execute_arbitrary_code")
        assert tool.classification == ToolClassification.CRITICAL
        assert "sandbox" in tool.requires_context
        assert "production" in tool.blocked_contexts
        assert "staging" in tool.blocked_contexts
