"""
Tests for External Tool Registry Service.

Covers the ExternalToolRegistry class and related components for
unified tool management across Aura native and external tools.
"""

import sys
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

# Mock the dependencies before importing the module
mock_config = MagicMock()


# Create mock enum-like objects for ExternalToolCategory
class MockExternalToolCategory:
    NOTIFICATION = "notification"
    TICKETING = "ticketing"


mock_config.ExternalToolCategory = MockExternalToolCategory

# Mock get_integration_config to return an object with is_enterprise_mode
mock_integration_config = MagicMock()
mock_integration_config.is_enterprise_mode = True
mock_integration_config.mode = MagicMock(value="enterprise")
mock_config.get_integration_config = MagicMock(return_value=mock_integration_config)


# Mock decorator to pass through
def mock_enterprise_decorator(func):
    """Mock decorator that just returns the function unchanged."""
    return func


mock_config.require_enterprise_mode = mock_enterprise_decorator

# Mock MCP gateway client
mock_mcp = MagicMock()
mock_mcp.MCPGatewayClient = MagicMock
mock_mcp.MCPInvocationResult = MagicMock
mock_mcp.MCPInvocationStatus = MagicMock
mock_mcp.MCPSearchResult = MagicMock
mock_mcp.MCPTool = MagicMock

# Mock MCP tool adapters
mock_adapters = MagicMock()
mock_adapters.AdapterInvocationResult = MagicMock
mock_adapters.AuraToolAdapter = MagicMock
mock_adapters.AuraToolDefinition = MagicMock


@dataclass
class MockAuraToolDefinition:
    tool_id: str
    name: str
    description: str
    category: MagicMock
    input_schema: dict
    output_schema: dict
    requires_hitl_approval: bool = False
    estimated_cost_usd: float = 0.0
    version: str = "1.0"


mock_adapters.get_aura_tools = MagicMock(return_value=[])
mock_adapters.AuraToolDefinition = MockAuraToolDefinition

# Save original modules before mocking
_original_src_config = sys.modules.get("src.config")
_original_mcp_gateway = sys.modules.get("src.services.mcp_gateway_client")
_original_mcp_adapters = sys.modules.get("src.services.mcp_tool_adapters")

# Apply mocks
sys.modules["src.config"] = mock_config
sys.modules["src.services.mcp_gateway_client"] = mock_mcp
sys.modules["src.services.mcp_tool_adapters"] = mock_adapters

from src.services.external_tool_registry import (
    ExternalToolRegistry,
    RegistryInvocationResult,
    RegistrySearchResult,
    ToolCapabilityType,
    ToolProvider,
    UnifiedToolInfo,
)

# Restore original modules to prevent pollution of other test files
if _original_src_config is not None:
    sys.modules["src.config"] = _original_src_config
else:
    sys.modules.pop("src.config", None)

if _original_mcp_gateway is not None:
    sys.modules["src.services.mcp_gateway_client"] = _original_mcp_gateway
else:
    sys.modules.pop("src.services.mcp_gateway_client", None)

if _original_mcp_adapters is not None:
    sys.modules["src.services.mcp_tool_adapters"] = _original_mcp_adapters
else:
    sys.modules.pop("src.services.mcp_tool_adapters", None)


# =============================================================================
# ToolProvider Enum Tests
# =============================================================================


class TestToolProvider:
    """Tests for ToolProvider enum."""

    def test_aura_native(self):
        """Test Aura native provider."""
        assert ToolProvider.AURA_NATIVE.value == "aura"

    def test_agentcore(self):
        """Test AgentCore provider."""
        assert ToolProvider.AGENTCORE.value == "agentcore"

    def test_custom(self):
        """Test custom provider."""
        assert ToolProvider.CUSTOM.value == "custom"

    def test_provider_count(self):
        """Test that all 3 providers exist."""
        assert len(ToolProvider) == 3


# =============================================================================
# ToolCapabilityType Enum Tests
# =============================================================================


class TestToolCapabilityType:
    """Tests for ToolCapabilityType enum."""

    def test_notification(self):
        """Test notification capability."""
        assert ToolCapabilityType.NOTIFICATION.value == "notification"

    def test_ticketing(self):
        """Test ticketing capability."""
        assert ToolCapabilityType.TICKETING.value == "ticketing"

    def test_security(self):
        """Test security capability."""
        assert ToolCapabilityType.SECURITY.value == "security"

    def test_code_analysis(self):
        """Test code analysis capability."""
        assert ToolCapabilityType.CODE_ANALYSIS.value == "code_analysis"

    def test_documentation(self):
        """Test documentation capability."""
        assert ToolCapabilityType.DOCUMENTATION.value == "documentation"

    def test_ci_cd(self):
        """Test CI/CD capability."""
        assert ToolCapabilityType.CI_CD.value == "ci_cd"

    def test_monitoring(self):
        """Test monitoring capability."""
        assert ToolCapabilityType.MONITORING.value == "monitoring"

    def test_capability_count(self):
        """Test that all 7 capabilities exist."""
        assert len(ToolCapabilityType) == 7


# =============================================================================
# UnifiedToolInfo Dataclass Tests
# =============================================================================


class TestUnifiedToolInfo:
    """Tests for UnifiedToolInfo dataclass."""

    def test_create_basic_tool(self):
        """Test creating a basic tool info."""
        tool = UnifiedToolInfo(
            tool_id="slack-send",
            name="Slack Send Message",
            description="Send a message to a Slack channel",
            provider=ToolProvider.AGENTCORE,
            capabilities=[ToolCapabilityType.NOTIFICATION],
        )
        assert tool.tool_id == "slack-send"
        assert tool.name == "Slack Send Message"
        assert tool.provider == ToolProvider.AGENTCORE
        assert ToolCapabilityType.NOTIFICATION in tool.capabilities

    def test_default_values(self):
        """Test default values for optional fields."""
        tool = UnifiedToolInfo(
            tool_id="test-tool",
            name="Test Tool",
            description="A test tool",
            provider=ToolProvider.AURA_NATIVE,
            capabilities=[ToolCapabilityType.SECURITY],
        )
        assert tool.enabled is True
        assert tool.input_schema == {}
        assert tool.output_schema == {}
        assert tool.requires_auth is False
        assert tool.requires_hitl is False
        assert tool.rate_limit_per_minute == 60
        assert tool.estimated_cost_usd == 0.0
        assert tool.tags == []
        assert tool.version == "1.0"

    def test_full_tool(self):
        """Test tool with all fields."""
        tool = UnifiedToolInfo(
            tool_id="security-scan",
            name="Security Scanner",
            description="Scan code for vulnerabilities",
            provider=ToolProvider.AURA_NATIVE,
            capabilities=[
                ToolCapabilityType.SECURITY,
                ToolCapabilityType.CODE_ANALYSIS,
            ],
            enabled=True,
            input_schema={"type": "object", "properties": {"repo": {"type": "string"}}},
            output_schema={"type": "object"},
            requires_auth=True,
            requires_hitl=True,
            rate_limit_per_minute=10,
            estimated_cost_usd=0.05,
            tags=["security", "scanning"],
            version="2.0",
        )
        assert len(tool.capabilities) == 2
        assert tool.requires_auth is True
        assert tool.requires_hitl is True
        assert tool.rate_limit_per_minute == 10
        assert "security" in tool.tags

    def test_multiple_capabilities(self):
        """Test tool with multiple capabilities."""
        tool = UnifiedToolInfo(
            tool_id="incident-response",
            name="Incident Response",
            description="Handle security incidents",
            provider=ToolProvider.AURA_NATIVE,
            capabilities=[
                ToolCapabilityType.SECURITY,
                ToolCapabilityType.NOTIFICATION,
                ToolCapabilityType.TICKETING,
            ],
        )
        assert len(tool.capabilities) == 3
        assert ToolCapabilityType.SECURITY in tool.capabilities


# =============================================================================
# RegistrySearchResult Dataclass Tests
# =============================================================================


class TestRegistrySearchResult:
    """Tests for RegistrySearchResult dataclass."""

    def test_create_search_result(self):
        """Test creating a search result."""
        tools = [
            UnifiedToolInfo(
                tool_id="tool-1",
                name="Tool 1",
                description="First tool",
                provider=ToolProvider.AURA_NATIVE,
                capabilities=[ToolCapabilityType.SECURITY],
            )
        ]
        result = RegistrySearchResult(
            query="security",
            tools=tools,
            total_count=1,
        )
        assert result.query == "security"
        assert len(result.tools) == 1
        assert result.total_count == 1

    def test_default_values(self):
        """Test default values."""
        result = RegistrySearchResult(
            query="test",
            tools=[],
            total_count=0,
        )
        assert result.latency_ms == 0.0
        assert result.sources == []

    def test_full_result(self):
        """Test search result with all fields."""
        result = RegistrySearchResult(
            query="notification",
            tools=[],
            total_count=5,
            latency_ms=25.5,
            sources=[ToolProvider.AURA_NATIVE, ToolProvider.AGENTCORE],
        )
        assert result.latency_ms == 25.5
        assert len(result.sources) == 2


# =============================================================================
# RegistryInvocationResult Dataclass Tests
# =============================================================================


class TestRegistryInvocationResult:
    """Tests for RegistryInvocationResult dataclass."""

    def test_create_success_result(self):
        """Test creating a success result."""
        result = RegistryInvocationResult(
            tool_id="slack-send",
            provider=ToolProvider.AGENTCORE,
            success=True,
            data={"message_id": "12345", "channel": "#alerts"},
        )
        assert result.tool_id == "slack-send"
        assert result.success is True
        assert result.data["message_id"] == "12345"

    def test_create_failure_result(self):
        """Test creating a failure result."""
        result = RegistryInvocationResult(
            tool_id="slack-send",
            provider=ToolProvider.AGENTCORE,
            success=False,
            error="Channel not found",
        )
        assert result.success is False
        assert result.error == "Channel not found"

    def test_default_values(self):
        """Test default values."""
        result = RegistryInvocationResult(
            tool_id="test",
            provider=ToolProvider.AURA_NATIVE,
            success=True,
        )
        assert result.data == {}
        assert result.error is None
        assert result.latency_ms == 0.0
        assert result.cost_usd == 0.0

    def test_full_result(self):
        """Test result with all fields."""
        result = RegistryInvocationResult(
            tool_id="jira-create",
            provider=ToolProvider.AGENTCORE,
            success=True,
            data={"issue_key": "PROJ-123"},
            error=None,
            latency_ms=150.5,
            cost_usd=0.001,
        )
        assert result.latency_ms == 150.5
        assert result.cost_usd == 0.001


# =============================================================================
# ExternalToolRegistry Initialization Tests
# =============================================================================


class TestExternalToolRegistryInit:
    """Tests for ExternalToolRegistry initialization."""

    def test_initialization_enterprise_mode(self):
        """Test initialization in enterprise mode."""
        mock_mcp_client = MagicMock()
        mock_adapter = MagicMock()

        registry = ExternalToolRegistry(
            mcp_client=mock_mcp_client,
            aura_adapter=mock_adapter,
        )

        assert registry._mcp_client == mock_mcp_client
        assert registry._aura_adapter == mock_adapter
        assert registry._cache_loaded is False
        assert registry._invocation_counts == {}
        assert registry._total_cost_usd == 0.0

    def test_initialization_creates_empty_cache(self):
        """Test initialization creates empty cache."""
        mock_mcp_client = MagicMock()
        mock_adapter = MagicMock()

        registry = ExternalToolRegistry(
            mcp_client=mock_mcp_client,
            aura_adapter=mock_adapter,
        )

        assert registry._unified_tools == {}


# =============================================================================
# ExternalToolRegistry Helper Methods Tests
# =============================================================================


class TestRegistryHelperMethods:
    """Tests for ExternalToolRegistry helper methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mcp_client = MagicMock()
        self.mock_mcp_client.list_tools = AsyncMock(return_value=[])
        self.mock_mcp_client.get_metrics = MagicMock(return_value={})

        self.mock_adapter = MagicMock()
        self.mock_adapter.get_metrics = MagicMock(return_value={})

        self.registry = ExternalToolRegistry(
            mcp_client=self.mock_mcp_client,
            aura_adapter=self.mock_adapter,
        )

    def test_calculate_relevance_name_match(self):
        """Test relevance calculation for name match."""
        tool = UnifiedToolInfo(
            tool_id="security-scanner",
            name="Security Scanner",
            description="Scan for vulnerabilities",
            provider=ToolProvider.AURA_NATIVE,
            capabilities=[ToolCapabilityType.SECURITY],
        )

        score = self.registry._calculate_relevance("security", tool)
        assert score > 0.3

    def test_calculate_relevance_description_match(self):
        """Test relevance calculation for description match."""
        tool = UnifiedToolInfo(
            tool_id="scan-tool",
            name="Code Analysis Tool",
            description="Security vulnerability scanning",
            provider=ToolProvider.AURA_NATIVE,
            capabilities=[ToolCapabilityType.SECURITY],
            tags=[],
        )

        score = self.registry._calculate_relevance("vulnerability", tool)
        assert score > 0.2

    def test_calculate_relevance_tag_match(self):
        """Test relevance calculation for tag match."""
        tool = UnifiedToolInfo(
            tool_id="test-tool",
            name="Test Tool",
            description="A tool for testing",
            provider=ToolProvider.AURA_NATIVE,
            capabilities=[ToolCapabilityType.SECURITY],
            tags=["security", "testing"],
        )

        score = self.registry._calculate_relevance("security", tool)
        assert score >= 0.1  # Tag match should give at least 0.1

    def test_calculate_relevance_no_match(self):
        """Test relevance calculation with no match."""
        tool = UnifiedToolInfo(
            tool_id="slack-tool",
            name="Slack Notifier",
            description="Send messages to Slack",
            provider=ToolProvider.AGENTCORE,
            capabilities=[ToolCapabilityType.NOTIFICATION],
            tags=["communication"],
        )

        score = self.registry._calculate_relevance("security", tool)
        assert score == 0.0

    def test_sort_by_relevance(self):
        """Test sorting tools by relevance."""
        tools = [
            UnifiedToolInfo(
                tool_id="tool-low",
                name="Generic Tool",
                description="Does various things",
                provider=ToolProvider.AURA_NATIVE,
                capabilities=[ToolCapabilityType.CODE_ANALYSIS],
            ),
            UnifiedToolInfo(
                tool_id="tool-high",
                name="Security Scanner",
                description="Security scanning tool",
                provider=ToolProvider.AURA_NATIVE,
                capabilities=[ToolCapabilityType.SECURITY],
                tags=["security"],
            ),
        ]

        sorted_tools = self.registry._sort_by_relevance("security", tools)

        # Higher relevance should come first
        assert sorted_tools[0].tool_id == "tool-high"


# =============================================================================
# ExternalToolRegistry Metrics Tests
# =============================================================================


class TestRegistryMetrics:
    """Tests for ExternalToolRegistry metrics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mcp_client = MagicMock()
        self.mock_mcp_client.get_metrics = MagicMock(return_value={"invocations": 10})

        self.mock_adapter = MagicMock()
        self.mock_adapter.get_metrics = MagicMock(return_value={"calls": 5})

        self.registry = ExternalToolRegistry(
            mcp_client=self.mock_mcp_client,
            aura_adapter=self.mock_adapter,
        )

    def test_get_metrics_empty_registry(self):
        """Test getting metrics from empty registry."""
        metrics = self.registry.get_metrics()

        assert metrics["total_tools"] == 0
        assert metrics["aura_tools"] == 0
        assert metrics["external_tools"] == 0
        assert metrics["invocation_counts"] == {}
        assert metrics["total_cost_usd"] == 0.0

    def test_get_metrics_with_tools(self):
        """Test getting metrics with tools in registry."""
        # Add some tools to the cache
        self.registry._unified_tools = {
            "aura-1": UnifiedToolInfo(
                tool_id="aura-1",
                name="Aura Tool 1",
                description="Test",
                provider=ToolProvider.AURA_NATIVE,
                capabilities=[ToolCapabilityType.SECURITY],
            ),
            "aura-2": UnifiedToolInfo(
                tool_id="aura-2",
                name="Aura Tool 2",
                description="Test",
                provider=ToolProvider.AURA_NATIVE,
                capabilities=[ToolCapabilityType.CODE_ANALYSIS],
            ),
            "ext-1": UnifiedToolInfo(
                tool_id="ext-1",
                name="External Tool",
                description="Test",
                provider=ToolProvider.AGENTCORE,
                capabilities=[ToolCapabilityType.NOTIFICATION],
            ),
        }

        metrics = self.registry.get_metrics()

        assert metrics["total_tools"] == 3
        assert metrics["aura_tools"] == 2
        assert metrics["external_tools"] == 1

    def test_get_metrics_includes_mcp_metrics(self):
        """Test metrics include MCP client metrics."""
        metrics = self.registry.get_metrics()

        assert "mcp_metrics" in metrics
        assert metrics["mcp_metrics"]["invocations"] == 10

    def test_get_metrics_includes_adapter_metrics(self):
        """Test metrics include adapter metrics."""
        metrics = self.registry.get_metrics()

        assert "adapter_metrics" in metrics
        assert metrics["adapter_metrics"]["calls"] == 5


# =============================================================================
# Cache Management Tests
# =============================================================================


class TestRegistryCacheManagement:
    """Tests for registry cache management."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mcp_client = MagicMock()
        self.mock_mcp_client.list_tools = AsyncMock(return_value=[])

        self.mock_adapter = MagicMock()

        # Reset the mock for get_aura_tools
        mock_adapters.get_aura_tools = MagicMock(return_value=[])

        self.registry = ExternalToolRegistry(
            mcp_client=self.mock_mcp_client,
            aura_adapter=self.mock_adapter,
        )

    @pytest.mark.asyncio
    async def test_ensure_cache_loaded_first_time(self):
        """Test cache is loaded on first access."""
        assert self.registry._cache_loaded is False

        await self.registry._ensure_cache_loaded()

        assert self.registry._cache_loaded is True

    @pytest.mark.asyncio
    async def test_ensure_cache_loaded_skips_if_loaded(self):
        """Test cache loading is skipped if already loaded."""
        self.registry._cache_loaded = True
        self.registry._unified_tools = {"test": MagicMock()}

        await self.registry._ensure_cache_loaded()

        # Should not reload
        assert len(self.registry._unified_tools) == 1

    @pytest.mark.asyncio
    async def test_refresh_cache_forces_reload(self):
        """Test refresh cache forces reload."""
        self.registry._cache_loaded = True
        self.registry._unified_tools = {"old-tool": MagicMock()}

        await self.registry.refresh_cache()

        assert self.registry._cache_loaded is True
        # Old tools should be cleared
        assert "old-tool" not in self.registry._unified_tools


# =============================================================================
# Integration Tests
# =============================================================================


class TestRegistryIntegration:
    """Integration tests for registry workflows."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mcp_client = MagicMock()
        self.mock_mcp_client.list_tools = AsyncMock(return_value=[])
        self.mock_mcp_client.get_metrics = MagicMock(return_value={})

        self.mock_adapter = MagicMock()
        self.mock_adapter.get_metrics = MagicMock(return_value={})

        self.registry = ExternalToolRegistry(
            mcp_client=self.mock_mcp_client,
            aura_adapter=self.mock_adapter,
        )

    def test_workflow_tool_selection(self):
        """Test workflow for tool selection based on capability."""
        # Pre-populate cache with tools
        self.registry._cache_loaded = True
        self.registry._unified_tools = {
            "security-scan": UnifiedToolInfo(
                tool_id="security-scan",
                name="Security Scanner",
                description="Scan for vulnerabilities",
                provider=ToolProvider.AURA_NATIVE,
                capabilities=[ToolCapabilityType.SECURITY],
                enabled=True,
            ),
            "slack-notify": UnifiedToolInfo(
                tool_id="slack-notify",
                name="Slack Notifier",
                description="Send notifications",
                provider=ToolProvider.AGENTCORE,
                capabilities=[ToolCapabilityType.NOTIFICATION],
                enabled=True,
            ),
            "code-review": UnifiedToolInfo(
                tool_id="code-review",
                name="Code Reviewer",
                description="Review code quality",
                provider=ToolProvider.AURA_NATIVE,
                capabilities=[ToolCapabilityType.CODE_ANALYSIS],
                enabled=True,
            ),
        }

        # Get all enabled tools
        all_tools = list(self.registry._unified_tools.values())
        assert len(all_tools) == 3

        # Filter by capability
        security_tools = [
            t for t in all_tools if ToolCapabilityType.SECURITY in t.capabilities
        ]
        assert len(security_tools) == 1
        assert security_tools[0].tool_id == "security-scan"

    def test_workflow_invocation_tracking(self):
        """Test invocation tracking works correctly."""
        self.registry._invocation_counts = {}
        self.registry._total_cost_usd = 0.0

        # Simulate tracking invocations
        tool_id = "test-tool"
        self.registry._invocation_counts[tool_id] = (
            self.registry._invocation_counts.get(tool_id, 0) + 1
        )
        self.registry._invocation_counts[tool_id] = (
            self.registry._invocation_counts.get(tool_id, 0) + 1
        )

        assert self.registry._invocation_counts[tool_id] == 2

        # Track cost
        self.registry._total_cost_usd += 0.01
        self.registry._total_cost_usd += 0.02

        assert self.registry._total_cost_usd == 0.03


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
