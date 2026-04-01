"""
Tests for capability governance tool registry.

Tests tool registration, classification lookup, and validation functions.
"""

from src.services.capability_governance import (
    CapabilityRegistry,
    ToolCapability,
    ToolClassification,
    get_capability_registry,
)
from src.services.capability_governance.registry import DEFAULT_TOOL_CAPABILITIES


class TestDefaultToolCapabilities:
    """Test default tool capability definitions."""

    def test_safe_tools_exist(self):
        """Verify SAFE tool definitions exist."""
        safe_tools = [
            "semantic_search",
            "describe_tool",
            "get_sandbox_status",
            "list_tools",
        ]
        for tool in safe_tools:
            assert tool in DEFAULT_TOOL_CAPABILITIES
            assert (
                DEFAULT_TOOL_CAPABILITIES[tool].classification
                == ToolClassification.SAFE
            )

    def test_monitoring_tools_exist(self):
        """Verify MONITORING tool definitions exist."""
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

    def test_dangerous_tools_exist(self):
        """Verify DANGEROUS tool definitions exist."""
        dangerous_tools = [
            "index_code_embedding",
            "destroy_sandbox",
            "write_config",
            "commit_changes",
        ]
        for tool in dangerous_tools:
            assert tool in DEFAULT_TOOL_CAPABILITIES
            assert (
                DEFAULT_TOOL_CAPABILITIES[tool].classification
                == ToolClassification.DANGEROUS
            )

    def test_critical_tools_exist(self):
        """Verify CRITICAL tool definitions exist."""
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

    def test_tool_count(self):
        """Verify we have a reasonable number of default tools."""
        assert len(DEFAULT_TOOL_CAPABILITIES) >= 20

    def test_all_tools_have_descriptions(self):
        """Verify all tools have descriptions."""
        for name, tool in DEFAULT_TOOL_CAPABILITIES.items():
            assert tool.description, f"Tool {name} lacks description"

    def test_all_tools_have_rate_limits(self):
        """Verify all tools have rate limits."""
        for name, tool in DEFAULT_TOOL_CAPABILITIES.items():
            assert tool.rate_limit_per_minute > 0, f"Tool {name} has invalid rate limit"


class TestCapabilityRegistry:
    """Test CapabilityRegistry."""

    def test_initialization(self, capability_registry: CapabilityRegistry):
        """Test registry initialization loads defaults."""
        assert capability_registry._initialized is True
        assert len(capability_registry._tools) > 0

    def test_get_tool_existing(self, capability_registry: CapabilityRegistry):
        """Test getting an existing tool."""
        tool = capability_registry.get_tool("semantic_search")
        assert tool is not None
        assert tool.tool_name == "semantic_search"
        assert tool.classification == ToolClassification.SAFE

    def test_get_tool_nonexistent(self, capability_registry: CapabilityRegistry):
        """Test getting a nonexistent tool."""
        tool = capability_registry.get_tool("nonexistent_tool")
        assert tool is None

    def test_get_classification_known(self, capability_registry: CapabilityRegistry):
        """Test getting classification for known tool."""
        assert (
            capability_registry.get_classification("semantic_search")
            == ToolClassification.SAFE
        )
        assert (
            capability_registry.get_classification("query_code_graph")
            == ToolClassification.MONITORING
        )
        assert (
            capability_registry.get_classification("destroy_sandbox")
            == ToolClassification.DANGEROUS
        )
        assert (
            capability_registry.get_classification("provision_sandbox")
            == ToolClassification.CRITICAL
        )

    def test_get_classification_unknown(self, capability_registry: CapabilityRegistry):
        """Test getting classification for unknown tool defaults to DANGEROUS."""
        assert (
            capability_registry.get_classification("unknown_tool")
            == ToolClassification.DANGEROUS
        )

    def test_is_registered(self, capability_registry: CapabilityRegistry):
        """Test checking if tool is registered."""
        assert capability_registry.is_registered("semantic_search") is True
        assert capability_registry.is_registered("unknown_tool") is False


class TestCapabilityRegistryRegistration:
    """Test tool registration and unregistration."""

    def test_register_tool(self, capability_registry: CapabilityRegistry):
        """Test registering a new tool."""
        new_tool = ToolCapability(
            tool_name="custom_tool",
            classification=ToolClassification.MONITORING,
            description="A custom test tool",
        )
        capability_registry.register_tool(new_tool)

        assert capability_registry.is_registered("custom_tool")
        retrieved = capability_registry.get_tool("custom_tool")
        assert retrieved is not None
        assert retrieved.classification == ToolClassification.MONITORING

    def test_register_tool_overwrites(self, capability_registry: CapabilityRegistry):
        """Test that registering overwrites existing tool."""
        # First registration
        tool_v1 = ToolCapability(
            tool_name="custom_tool",
            classification=ToolClassification.SAFE,
            description="Version 1",
        )
        capability_registry.register_tool(tool_v1)

        # Second registration with different classification
        tool_v2 = ToolCapability(
            tool_name="custom_tool",
            classification=ToolClassification.DANGEROUS,
            description="Version 2",
        )
        capability_registry.register_tool(tool_v2)

        retrieved = capability_registry.get_tool("custom_tool")
        assert retrieved.classification == ToolClassification.DANGEROUS
        assert retrieved.description == "Version 2"

    def test_unregister_tool_existing(self, capability_registry: CapabilityRegistry):
        """Test unregistering an existing tool."""
        # Add a tool first
        new_tool = ToolCapability(
            tool_name="temp_tool",
            classification=ToolClassification.SAFE,
        )
        capability_registry.register_tool(new_tool)
        assert capability_registry.is_registered("temp_tool")

        # Unregister
        result = capability_registry.unregister_tool("temp_tool")
        assert result is True
        assert capability_registry.is_registered("temp_tool") is False

    def test_unregister_tool_nonexistent(self, capability_registry: CapabilityRegistry):
        """Test unregistering a nonexistent tool."""
        result = capability_registry.unregister_tool("nonexistent_tool")
        assert result is False


class TestCapabilityRegistryListing:
    """Test tool listing functionality."""

    def test_list_tools_all(self, capability_registry: CapabilityRegistry):
        """Test listing all tools."""
        tools = capability_registry.list_tools()
        assert len(tools) > 0
        assert "semantic_search" in tools
        assert "provision_sandbox" in tools

    def test_list_tools_by_classification(
        self, capability_registry: CapabilityRegistry
    ):
        """Test listing tools filtered by classification."""
        safe_tools = capability_registry.list_tools(
            classification=ToolClassification.SAFE
        )
        assert len(safe_tools) > 0
        assert "semantic_search" in safe_tools
        assert "provision_sandbox" not in safe_tools

        critical_tools = capability_registry.list_tools(
            classification=ToolClassification.CRITICAL
        )
        assert len(critical_tools) > 0
        assert "provision_sandbox" in critical_tools
        assert "semantic_search" not in critical_tools

    def test_list_tools_by_classification_grouped(
        self, capability_registry: CapabilityRegistry
    ):
        """Test listing tools grouped by classification."""
        grouped = capability_registry.list_tools_by_classification()

        assert ToolClassification.SAFE in grouped
        assert ToolClassification.MONITORING in grouped
        assert ToolClassification.DANGEROUS in grouped
        assert ToolClassification.CRITICAL in grouped

        assert "semantic_search" in grouped[ToolClassification.SAFE]
        assert "query_code_graph" in grouped[ToolClassification.MONITORING]
        assert "destroy_sandbox" in grouped[ToolClassification.DANGEROUS]
        assert "provision_sandbox" in grouped[ToolClassification.CRITICAL]


class TestCapabilityRegistryValidation:
    """Test tool validation functionality."""

    def test_get_rate_limit_known(self, capability_registry: CapabilityRegistry):
        """Test getting rate limit for known tool."""
        rate_limit = capability_registry.get_rate_limit("semantic_search")
        assert rate_limit > 0
        assert (
            rate_limit
            == DEFAULT_TOOL_CAPABILITIES["semantic_search"].rate_limit_per_minute
        )

    def test_get_rate_limit_unknown(self, capability_registry: CapabilityRegistry):
        """Test getting rate limit for unknown tool returns default."""
        rate_limit = capability_registry.get_rate_limit("unknown_tool")
        assert rate_limit == 60

    def test_requires_justification_true(self, capability_registry: CapabilityRegistry):
        """Test checking justification requirement for tools that require it."""
        assert capability_registry.requires_justification("provision_sandbox") is True
        assert capability_registry.requires_justification("commit_changes") is True

    def test_requires_justification_false(
        self, capability_registry: CapabilityRegistry
    ):
        """Test checking justification requirement for tools that don't require it."""
        # SAFE tools typically don't require justification
        assert capability_registry.requires_justification("semantic_search") is False

    def test_requires_justification_unknown(
        self, capability_registry: CapabilityRegistry
    ):
        """Test unknown tools default to requiring justification."""
        assert capability_registry.requires_justification("unknown_tool") is True

    def test_get_audit_sample_rate(self, capability_registry: CapabilityRegistry):
        """Test getting audit sample rate."""
        # SAFE tools have lower sample rate
        safe_rate = capability_registry.get_audit_sample_rate("semantic_search")
        assert safe_rate == 0.1

        # Critical tools have 100% sample rate
        critical_rate = capability_registry.get_audit_sample_rate("provision_sandbox")
        assert critical_rate == 1.0

    def test_get_audit_sample_rate_unknown(
        self, capability_registry: CapabilityRegistry
    ):
        """Test unknown tools have 100% audit rate."""
        rate = capability_registry.get_audit_sample_rate("unknown_tool")
        assert rate == 1.0

    def test_validate_context_allowed(self, capability_registry: CapabilityRegistry):
        """Test validating allowed contexts."""
        # provision_sandbox requires sandbox or test context
        assert (
            capability_registry.validate_context("provision_sandbox", "sandbox") is True
        )
        assert capability_registry.validate_context("provision_sandbox", "test") is True
        assert (
            capability_registry.validate_context("provision_sandbox", "production")
            is False
        )

    def test_validate_context_blocked(self, capability_registry: CapabilityRegistry):
        """Test validating blocked contexts."""
        # index_code_embedding blocks production
        assert (
            capability_registry.validate_context("index_code_embedding", "development")
            is False
        )
        assert (
            capability_registry.validate_context("index_code_embedding", "sandbox")
            is True
        )
        assert (
            capability_registry.validate_context("index_code_embedding", "production")
            is False
        )

    def test_validate_context_unknown_tool(
        self, capability_registry: CapabilityRegistry
    ):
        """Test validating context for unknown tool returns False."""
        assert (
            capability_registry.validate_context("unknown_tool", "development") is False
        )

    def test_validate_action_allowed(self, capability_registry: CapabilityRegistry):
        """Test validating allowed actions."""
        assert capability_registry.validate_action("semantic_search", "read") is True
        assert capability_registry.validate_action("semantic_search", "execute") is True

    def test_validate_action_not_allowed(self, capability_registry: CapabilityRegistry):
        """Test validating disallowed actions."""
        assert capability_registry.validate_action("semantic_search", "write") is False
        assert capability_registry.validate_action("semantic_search", "admin") is False

    def test_validate_action_unknown_tool(
        self, capability_registry: CapabilityRegistry
    ):
        """Test validating action for unknown tool returns False."""
        assert capability_registry.validate_action("unknown_tool", "read") is False


class TestCapabilityRegistrySerialization:
    """Test registry serialization."""

    def test_to_dict(self, capability_registry: CapabilityRegistry):
        """Test converting registry to dictionary."""
        d = capability_registry.to_dict()

        assert "semantic_search" in d
        assert d["semantic_search"]["classification"] == "safe"
        assert "description" in d["semantic_search"]
        assert "allowed_actions" in d["semantic_search"]
        assert "rate_limit_per_minute" in d["semantic_search"]

        assert "provision_sandbox" in d
        assert d["provision_sandbox"]["classification"] == "critical"


class TestCapabilityRegistrySingleton:
    """Test global registry singleton."""

    def test_get_capability_registry_singleton(self):
        """Test global singleton."""
        registry1 = get_capability_registry()
        registry2 = get_capability_registry()
        assert registry1 is registry2


class TestToolCapabilityContextRestrictions:
    """Test tool capability context restrictions in detail."""

    def test_tool_with_required_context(self):
        """Test tool that requires specific context."""
        tool = DEFAULT_TOOL_CAPABILITIES["provision_sandbox"]
        assert ("sandbox", "test") == tool.requires_context
        assert tool.is_allowed_in_context("sandbox") is True
        assert tool.is_allowed_in_context("test") is True
        assert tool.is_allowed_in_context("development") is False

    def test_tool_with_blocked_context(self):
        """Test tool that blocks specific context."""
        tool = DEFAULT_TOOL_CAPABILITIES["index_code_embedding"]
        assert "production" in tool.blocked_contexts
        assert tool.is_allowed_in_context("production") is False

    def test_tool_with_both_requirements_and_blocks(self):
        """Test tool with both required and blocked contexts."""
        tool = DEFAULT_TOOL_CAPABILITIES["execute_arbitrary_code"]
        assert "sandbox" in tool.requires_context
        assert "production" in tool.blocked_contexts
        assert "staging" in tool.blocked_contexts

        assert tool.is_allowed_in_context("sandbox") is True
        assert tool.is_allowed_in_context("production") is False
        assert tool.is_allowed_in_context("staging") is False


class TestToolCapabilityRateLimits:
    """Test tool capability rate limits."""

    def test_safe_tools_have_higher_limits(self):
        """Verify SAFE tools generally have higher rate limits."""
        safe_limits = [
            DEFAULT_TOOL_CAPABILITIES[name].rate_limit_per_minute
            for name in DEFAULT_TOOL_CAPABILITIES
            if DEFAULT_TOOL_CAPABILITIES[name].classification == ToolClassification.SAFE
        ]
        critical_limits = [
            DEFAULT_TOOL_CAPABILITIES[name].rate_limit_per_minute
            for name in DEFAULT_TOOL_CAPABILITIES
            if DEFAULT_TOOL_CAPABILITIES[name].classification
            == ToolClassification.CRITICAL
        ]

        avg_safe = sum(safe_limits) / len(safe_limits)
        avg_critical = sum(critical_limits) / len(critical_limits)

        # SAFE tools should have higher average rate limit
        assert avg_safe > avg_critical

    def test_critical_tools_have_strict_limits(self):
        """Verify CRITICAL tools have strict rate limits."""
        critical_tools = [
            "deploy_to_production",
            "rotate_credentials",
            "delete_repository",
        ]
        for tool_name in critical_tools:
            tool = DEFAULT_TOOL_CAPABILITIES[tool_name]
            assert (
                tool.rate_limit_per_minute <= 5
            ), f"{tool_name} should have strict limit"
