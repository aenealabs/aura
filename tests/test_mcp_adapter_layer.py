"""
Tests for Project Aura MCP Adapter Layer (ADR-023 Phase 2)

Tests the MCP Gateway Client, Tool Adapters, and External Tool Registry
for ENTERPRISE mode deployments with AgentCore Gateway integration.
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

from src.config import (
    CustomerMCPBudget,
    IntegrationConfig,
    IntegrationMode,
    clear_integration_config_cache,
)
from src.services.external_tool_registry import (
    ExternalToolRegistry,
    RegistrySearchResult,
    ToolCapabilityType,
    ToolProvider,
    UnifiedToolInfo,
)
from src.services.mcp_gateway_client import (
    MCPGatewayClient,
    MCPInvocationStatus,
    MCPSearchResult,
    MCPTool,
    MCPToolStatus,
)
from src.services.mcp_tool_adapters import (
    AuraToolAdapter,
    AuraToolDefinition,
    get_aura_tool_ids,
    get_aura_tools,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def enterprise_config():
    """Create enterprise mode configuration with external tools."""
    from src.config.integration_config import ExternalToolCategory, ExternalToolConfig

    external_tools = [
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
            enabled=True,
        ),
        ExternalToolConfig(
            tool_id="pagerduty",
            tool_name="PagerDuty",
            category=ExternalToolCategory.ALERTING,
            enabled=True,
        ),
    ]

    return IntegrationConfig(
        mode=IntegrationMode.ENTERPRISE,
        environment="test",
        gateway_region="us-east-1",
        external_tools=external_tools,
    )


@pytest.fixture
def defense_config():
    """Create defense mode configuration."""
    return IntegrationConfig(
        mode=IntegrationMode.DEFENSE,
        environment="test",
    )


@pytest.fixture
def customer_budget():
    """Create test customer budget."""
    return CustomerMCPBudget(
        customer_id="test-customer",
        monthly_limit_usd=100.00,
        current_spend_usd=0.0,
    )


@pytest.fixture
def mcp_client(enterprise_config, customer_budget):
    """Create MCP Gateway Client for testing."""
    return MCPGatewayClient(
        config=enterprise_config,
        customer_budget=customer_budget,
    )


@pytest.fixture(autouse=True)
def clear_config_cache():
    """Clear config cache before and after each test."""
    clear_integration_config_cache()
    yield
    clear_integration_config_cache()


# =============================================================================
# MCPTool Tests
# =============================================================================


class TestMCPTool:
    """Tests for MCPTool data class."""

    def test_tool_creation(self):
        """Should create tool with default values."""
        tool = MCPTool(
            tool_id="test-tool",
            name="Test Tool",
            description="A test tool",
        )
        assert tool.tool_id == "test-tool"
        assert tool.status == MCPToolStatus.AVAILABLE
        assert tool.rate_limit_per_minute == 60

    def test_rate_limiting(self):
        """Should track rate limiting correctly."""
        tool = MCPTool(
            tool_id="test",
            name="Test",
            description="Test",
            rate_limit_per_minute=2,
        )

        assert not tool.is_rate_limited()
        tool.record_invocation()
        assert not tool.is_rate_limited()
        tool.record_invocation()
        assert tool.is_rate_limited()

    def test_rate_limit_reset(self):
        """Should reset rate limit after 60 seconds."""
        tool = MCPTool(
            tool_id="test",
            name="Test",
            description="Test",
            rate_limit_per_minute=1,
        )
        tool.record_invocation()
        assert tool.is_rate_limited()

        # Simulate time passing
        tool.last_rate_reset = tool.last_rate_reset - 61
        assert not tool.is_rate_limited()


# =============================================================================
# MCPGatewayClient Tests
# =============================================================================


class TestMCPGatewayClient:
    """Tests for MCP Gateway Client."""

    def test_client_initialization_enterprise_mode(
        self, enterprise_config, customer_budget
    ):
        """Should initialize in enterprise mode."""
        client = MCPGatewayClient(
            config=enterprise_config,
            customer_budget=customer_budget,
        )
        assert client._config.is_enterprise_mode
        assert client._customer_budget.customer_id == "test-customer"

    def test_client_fails_in_defense_mode(self, defense_config):
        """Should raise error in defense mode."""
        with pytest.raises(RuntimeError) as exc_info:
            MCPGatewayClient(config=defense_config)
        assert "DEFENSE mode" in str(exc_info.value)

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_list_tools(self, enterprise_config):
        """Should list available tools."""
        client = MCPGatewayClient(config=enterprise_config)
        tools = await client.list_tools()
        assert isinstance(tools, list)
        # Should have default tools from config
        tool_ids = [t.tool_id for t in tools]
        assert "slack" in tool_ids
        assert "jira" in tool_ids

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_list_tools_by_category(self, enterprise_config):
        """Should filter tools by category."""
        client = MCPGatewayClient(config=enterprise_config)
        tools = await client.list_tools(category="notification")
        assert all(t.category == "notification" for t in tools)

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_search_tools(self, enterprise_config, customer_budget):
        """Should search tools semantically."""
        client = MCPGatewayClient(
            config=enterprise_config, customer_budget=customer_budget
        )
        result = await client.search_tools("slack")
        assert isinstance(result, MCPSearchResult)
        assert result.query == "slack"
        # Slack should be in results for slack search
        tool_ids = [t.tool_id for t in result.tools]
        assert "slack" in tool_ids

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_get_tool(self, enterprise_config):
        """Should get tool by ID."""
        client = MCPGatewayClient(config=enterprise_config)
        tool = await client.get_tool("slack")
        assert tool is not None
        assert tool.tool_id == "slack"

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_get_tool_not_found(self, enterprise_config):
        """Should return None for unknown tool."""
        client = MCPGatewayClient(config=enterprise_config)
        tool = await client.get_tool("nonexistent-tool")
        assert tool is None

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_tool_success(self, enterprise_config):
        """Should invoke tool successfully."""
        client = MCPGatewayClient(config=enterprise_config)
        result = await client.invoke_tool(
            "slack",
            {"channel": "#test", "message": "Hello"},
        )
        assert result.is_success
        assert result.tool_id == "slack"
        assert result.status == MCPInvocationStatus.SUCCESS
        assert "ok" in result.data

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_tool_not_found(self, enterprise_config):
        """Should handle tool not found."""
        client = MCPGatewayClient(config=enterprise_config)
        result = await client.invoke_tool(
            "nonexistent",
            {"param": "value"},
        )
        assert not result.is_success
        assert result.status == MCPInvocationStatus.TOOL_NOT_FOUND

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_tool_budget_exceeded(self, enterprise_config):
        """Should block when budget exceeded."""
        budget = CustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=0.0,  # Zero budget
            current_spend_usd=0.0,
            hard_limit_enabled=True,
        )
        client = MCPGatewayClient(config=enterprise_config, customer_budget=budget)

        result = await client.invoke_tool(
            "slack", {"channel": "#test", "message": "Hi"}
        )
        assert not result.is_success
        assert result.status == MCPInvocationStatus.BUDGET_EXCEEDED

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_tool_rate_limited(self, enterprise_config):
        """Should handle rate limiting."""
        client = MCPGatewayClient(config=enterprise_config)
        # Get and exhaust rate limit
        tool = await client.get_tool("slack")
        tool.rate_limit_per_minute = 1
        tool.record_invocation()

        result = await client.invoke_tool(
            "slack", {"channel": "#test", "message": "Hi"}
        )
        assert not result.is_success
        assert result.status == MCPInvocationStatus.RATE_LIMITED

    def test_get_metrics(self, enterprise_config, customer_budget):
        """Should return client metrics."""
        client = MCPGatewayClient(
            config=enterprise_config, customer_budget=customer_budget
        )
        metrics = client.get_metrics()
        assert "total_invocations" in metrics
        assert "total_errors" in metrics
        assert "budget_remaining_usd" in metrics


# =============================================================================
# AuraToolAdapter Tests
# =============================================================================


class TestAuraToolAdapter:
    """Tests for Aura Tool Adapters."""

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    def test_adapter_initialization(self):
        """Should initialize with all adapters."""
        adapter = AuraToolAdapter()
        tools = adapter.list_tools()
        assert len(tools) > 0
        assert any(t.tool_id == "security_scanner" for t in tools)

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_security_scanner(self):
        """Should invoke security scanner."""
        adapter = AuraToolAdapter()
        result = await adapter.invoke(
            "security_scanner",
            {"repository": "org/repo", "scan_type": "quick"},
        )
        assert result.success
        assert "vulnerabilities_found" in result.data

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_code_reviewer(self):
        """Should invoke code reviewer."""
        adapter = AuraToolAdapter()
        result = await adapter.invoke(
            "code_reviewer",
            {"file_path": "src/main.py", "review_type": "comprehensive"},
        )
        assert result.success
        assert "issues_found" in result.data
        assert "overall_score" in result.data

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_patch_generator(self):
        """Should invoke patch generator."""
        adapter = AuraToolAdapter()
        result = await adapter.invoke(
            "patch_generator",
            {"vulnerability_id": "CVE-2024-1234", "file_path": "src/auth.py"},
        )
        assert result.success
        assert "patch_generated" in result.data
        assert "diff" in result.data

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_architecture_analyzer(self):
        """Should invoke architecture analyzer."""
        adapter = AuraToolAdapter()
        result = await adapter.invoke(
            "architecture_analyzer",
            {"repository": "org/repo", "depth": "standard"},
        )
        assert result.success
        assert "components" in result.data
        assert "patterns_detected" in result.data

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_threat_intelligence(self):
        """Should invoke threat intelligence."""
        adapter = AuraToolAdapter()
        result = await adapter.invoke(
            "threat_intelligence",
            {"target": "example.com", "type": "comprehensive"},
        )
        assert result.success
        assert "threat_level" in result.data

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_unknown_tool(self):
        """Should handle unknown tool."""
        adapter = AuraToolAdapter()
        result = await adapter.invoke("unknown_tool", {})
        assert not result.success
        assert "Unknown" in result.error

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    def test_describe_tool(self):
        """Should return MCP-compatible description."""
        adapter = AuraToolAdapter()
        description = adapter.describe_tool("security_scanner")
        assert description is not None
        assert "name" in description
        assert "description" in description
        assert "inputSchema" in description

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    def test_get_metrics(self):
        """Should return adapter metrics."""
        adapter = AuraToolAdapter()
        metrics = adapter.get_metrics()
        assert "security_scanner" in metrics


class TestAuraToolDefinitions:
    """Tests for Aura tool definition functions."""

    def test_get_aura_tools(self):
        """Should return list of tool definitions."""
        tools = get_aura_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        assert all(isinstance(t, AuraToolDefinition) for t in tools)

    def test_get_aura_tool_ids(self):
        """Should return list of tool IDs."""
        ids = get_aura_tool_ids()
        assert "security_scanner" in ids
        assert "code_reviewer" in ids
        assert "patch_generator" in ids

    def test_tool_definitions_have_schemas(self):
        """All tools should have input schemas."""
        tools = get_aura_tools()
        for tool in tools:
            assert tool.input_schema
            assert "type" in tool.input_schema


# =============================================================================
# ExternalToolRegistry Tests
# =============================================================================


class TestExternalToolRegistry:
    """Tests for External Tool Registry."""

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_registry_initialization(self):
        """Should initialize registry."""
        registry = ExternalToolRegistry()
        assert registry._config.is_enterprise_mode

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_list_all_tools(self):
        """Should list all tools."""
        registry = ExternalToolRegistry()
        tools = await registry.list_all_tools()
        assert len(tools) > 0

        # Should have both Aura and external tools
        providers = {t.provider for t in tools}
        assert ToolProvider.AURA_NATIVE in providers
        assert ToolProvider.AGENTCORE in providers

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_list_tools_by_provider(self):
        """Should filter by provider."""
        registry = ExternalToolRegistry()
        aura_tools = await registry.list_all_tools(provider=ToolProvider.AURA_NATIVE)
        assert all(t.provider == ToolProvider.AURA_NATIVE for t in aura_tools)

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_list_tools_by_capability(self):
        """Should filter by capability."""
        registry = ExternalToolRegistry()
        security_tools = await registry.list_all_tools(
            capability=ToolCapabilityType.SECURITY
        )
        assert all(
            ToolCapabilityType.SECURITY in t.capabilities for t in security_tools
        )

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_search(self):
        """Should search across all tools."""
        registry = ExternalToolRegistry()
        result = await registry.search("security vulnerability")
        assert isinstance(result, RegistrySearchResult)
        assert result.total_count > 0

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_search_by_provider(self):
        """Should search filtered by provider."""
        registry = ExternalToolRegistry()
        result = await registry.search(
            "notification",
            providers=[ToolProvider.AGENTCORE],
        )
        assert all(t.provider == ToolProvider.AGENTCORE for t in result.tools)

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_get_tool(self):
        """Should get tool by ID."""
        registry = ExternalToolRegistry()
        tool = await registry.get_tool("security_scanner")
        assert tool is not None
        assert tool.tool_id == "security_scanner"
        assert tool.provider == ToolProvider.AURA_NATIVE

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_get_tools_by_capability(self):
        """Should get tools by capability type."""
        registry = ExternalToolRegistry()
        tools = await registry.get_tools_by_capability(ToolCapabilityType.NOTIFICATION)
        assert len(tools) > 0
        assert all(ToolCapabilityType.NOTIFICATION in t.capabilities for t in tools)

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_aura_tool(self):
        """Should invoke Aura native tool."""
        registry = ExternalToolRegistry()
        result = await registry.invoke(
            "security_scanner",
            {"repository": "org/repo"},
        )
        assert result.success
        assert result.provider == ToolProvider.AURA_NATIVE

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_external_tool(self):
        """Should invoke external tool via MCP."""
        registry = ExternalToolRegistry()
        result = await registry.invoke(
            "slack",
            {"channel": "#test", "message": "Hello"},
        )
        assert result.success
        assert result.provider == ToolProvider.AGENTCORE

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_tool_not_found(self):
        """Should handle tool not found."""
        registry = ExternalToolRegistry()
        result = await registry.invoke("nonexistent", {})
        assert not result.success
        assert "not found" in result.error

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_batch_parallel(self):
        """Should invoke multiple tools in parallel."""
        registry = ExternalToolRegistry()
        invocations = [
            ("security_scanner", {"repository": "org/repo"}),
            ("code_reviewer", {"file_path": "main.py"}),
        ]
        results = await registry.invoke_batch(invocations, parallel=True)
        assert len(results) == 2
        assert all(r.success for r in results)

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_invoke_batch_sequential(self):
        """Should invoke multiple tools sequentially."""
        registry = ExternalToolRegistry()
        invocations = [
            ("security_scanner", {"repository": "org/repo"}),
            ("code_reviewer", {"file_path": "main.py"}),
        ]
        results = await registry.invoke_batch(invocations, parallel=False)
        assert len(results) == 2

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_recommend_tools(self):
        """Should recommend tools based on task description."""
        registry = ExternalToolRegistry()
        tools = await registry.recommend_tools(
            "scan code for security vulnerabilities",
            max_recommendations=3,
        )
        assert len(tools) <= 3
        # Security scanner should be recommended
        tool_ids = [t.tool_id for t in tools]
        assert "security_scanner" in tool_ids

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_get_workflow_tools(self):
        """Should get tools for workflow type."""
        registry = ExternalToolRegistry()
        tools = await registry.get_workflow_tools("security_scan")
        assert len(tools) > 0
        # Should include security and notification tools
        capabilities = set()
        for tool in tools:
            capabilities.update(tool.capabilities)
        assert ToolCapabilityType.SECURITY in capabilities

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_refresh_cache(self):
        """Should refresh tool cache."""
        registry = ExternalToolRegistry()
        await registry.list_all_tools()  # Initial load
        await registry.refresh_cache()
        tools = await registry.list_all_tools()
        assert len(tools) > 0

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "enterprise"})
    @pytest.mark.asyncio
    async def test_get_metrics(self):
        """Should return registry metrics."""
        registry = ExternalToolRegistry()
        await registry.list_all_tools()  # Load cache
        metrics = registry.get_metrics()
        assert "total_tools" in metrics
        assert "aura_tools" in metrics
        assert "external_tools" in metrics


# =============================================================================
# Defense Mode Blocking Tests
# =============================================================================


class TestDefenseModeBlocking:
    """Tests that verify defense mode blocks MCP operations."""

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "defense"})
    def test_mcp_client_blocked_in_defense_mode(self):
        """MCPGatewayClient should fail in defense mode."""
        with pytest.raises(RuntimeError) as exc_info:
            MCPGatewayClient()
        assert "DEFENSE mode" in str(exc_info.value)

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "defense"})
    @pytest.mark.asyncio
    async def test_adapter_invoke_blocked_in_defense_mode(self):
        """AuraToolAdapter.invoke should fail in defense mode."""
        # Can create adapter but invoke should fail
        with pytest.raises(RuntimeError):
            adapter = AuraToolAdapter()
            await adapter.invoke("security_scanner", {})

    @patch.dict(os.environ, {"AURA_INTEGRATION_MODE": "defense"})
    def test_registry_initialization_defense_mode(self):
        """Registry should initialize without MCP client in defense mode."""
        registry = ExternalToolRegistry()
        assert registry._mcp_client is None
        assert registry._aura_adapter is None


# =============================================================================
# UnifiedToolInfo Tests
# =============================================================================


class TestUnifiedToolInfo:
    """Tests for UnifiedToolInfo data class."""

    def test_unified_tool_creation(self):
        """Should create unified tool info."""
        tool = UnifiedToolInfo(
            tool_id="test",
            name="Test Tool",
            description="A test tool",
            provider=ToolProvider.AURA_NATIVE,
            capabilities=[ToolCapabilityType.SECURITY],
        )
        assert tool.tool_id == "test"
        assert tool.enabled is True
        assert ToolCapabilityType.SECURITY in tool.capabilities

    def test_unified_tool_defaults(self):
        """Should have sensible defaults."""
        tool = UnifiedToolInfo(
            tool_id="test",
            name="Test",
            description="Test",
            provider=ToolProvider.CUSTOM,
            capabilities=[],
        )
        assert tool.requires_auth is False
        assert tool.requires_hitl is False
        assert tool.rate_limit_per_minute == 60
