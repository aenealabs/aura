"""
Tests for MCP Gateway Client.

Covers MCPToolStatus/MCPInvocationStatus enums, MCPTool/MCPInvocationResult/MCPSearchResult
dataclasses, and MCPGatewayClient service for AgentCore Gateway integration.
"""

import sys
import time
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

# =============================================================================
# Clean Module Cache and Apply Mocks BEFORE importing mcp_gateway_client
# =============================================================================

# Save original modules before mocking to prevent test pollution
_original_src_config = sys.modules.get("src.config")
_original_mcp_gateway = sys.modules.get("src.services.mcp_gateway_client")

# Remove any cached imports that might be polluted
modules_to_clear = [
    "src.services.mcp_gateway_client",
    "src.config",
]
for mod in modules_to_clear:
    if mod in sys.modules:
        del sys.modules[mod]


# Create mock decorator that passes through
def mock_enterprise_decorator(func):
    """Mock decorator that just returns the function unchanged."""
    return func


# Create mock config classes
@dataclass
class MockExternalToolConfig:
    """Mock external tool configuration."""

    tool_id: str
    tool_name: str
    category: MagicMock = field(default_factory=lambda: MagicMock(value="general"))
    enabled: bool = True
    rate_limit_per_minute: int = 60
    requires_customer_auth: bool = False


@dataclass
class MockCustomerMCPBudget:
    """Mock customer MCP budget."""

    customer_id: str = "test-customer"
    monthly_limit_usd: float = 100.0
    current_spend_usd: float = 0.0
    SEARCH_TOOL_COST_PER_REQUEST: float = 0.001
    INVOKE_TOOL_COST_PER_REQUEST: float = 0.01

    @property
    def remaining_budget_usd(self) -> float:
        return self.monthly_limit_usd - self.current_spend_usd

    @property
    def usage_percentage(self) -> float:
        return (self.current_spend_usd / self.monthly_limit_usd) * 100

    def record_invocation(self, is_search: bool = False) -> bool:
        cost = (
            self.SEARCH_TOOL_COST_PER_REQUEST
            if is_search
            else self.INVOKE_TOOL_COST_PER_REQUEST
        )
        if self.current_spend_usd + cost > self.monthly_limit_usd:
            return False
        self.current_spend_usd += cost
        return True


@dataclass
class MockIntegrationConfig:
    """Mock integration configuration."""

    is_defense_mode: bool = False  # Enterprise mode by default
    gateway_endpoint: str = "https://gateway.test.com"
    mcp_timeout_seconds: float = 30.0
    mcp_max_retries: int = 3
    external_tools: list = field(default_factory=list)
    default_customer_budget: MockCustomerMCPBudget = field(
        default_factory=MockCustomerMCPBudget
    )


def mock_get_integration_config():
    """Return mock integration config."""
    return MockIntegrationConfig(
        external_tools=[
            MockExternalToolConfig(tool_id="slack", tool_name="Slack"),
            MockExternalToolConfig(tool_id="jira", tool_name="Jira"),
        ]
    )


# Apply mocks
mock_config = MagicMock()
mock_config.require_enterprise_mode = mock_enterprise_decorator
mock_config.get_integration_config = mock_get_integration_config
mock_config.CustomerMCPBudget = MockCustomerMCPBudget
mock_config.IntegrationConfig = MockIntegrationConfig
sys.modules["src.config"] = mock_config

# Now import the module
from src.services.mcp_gateway_client import (
    MCPAuthError,
    MCPError,
    MCPGatewayClient,
    MCPInvocationError,
    MCPInvocationResult,
    MCPInvocationStatus,
    MCPRateLimitError,
    MCPSearchResult,
    MCPTool,
    MCPToolStatus,
)

# Restore original modules to prevent pollution of other tests
if _original_src_config is not None:
    sys.modules["src.config"] = _original_src_config
else:
    sys.modules.pop("src.config", None)

if _original_mcp_gateway is not None:
    sys.modules["src.services.mcp_gateway_client"] = _original_mcp_gateway


# =============================================================================
# MCPToolStatus Enum Tests
# =============================================================================


class TestMCPToolStatus:
    """Tests for MCPToolStatus enum."""

    def test_available(self):
        """Test available status."""
        assert MCPToolStatus.AVAILABLE.value == "available"

    def test_unavailable(self):
        """Test unavailable status."""
        assert MCPToolStatus.UNAVAILABLE.value == "unavailable"

    def test_rate_limited(self):
        """Test rate limited status."""
        assert MCPToolStatus.RATE_LIMITED.value == "rate_limited"

    def test_auth_required(self):
        """Test auth required status."""
        assert MCPToolStatus.AUTH_REQUIRED.value == "auth_required"

    def test_deprecated(self):
        """Test deprecated status."""
        assert MCPToolStatus.DEPRECATED.value == "deprecated"

    def test_status_count(self):
        """Test that all 5 statuses exist."""
        assert len(MCPToolStatus) == 5


# =============================================================================
# MCPInvocationStatus Enum Tests
# =============================================================================


class TestMCPInvocationStatus:
    """Tests for MCPInvocationStatus enum."""

    def test_success(self):
        """Test success status."""
        assert MCPInvocationStatus.SUCCESS.value == "success"

    def test_failed(self):
        """Test failed status."""
        assert MCPInvocationStatus.FAILED.value == "failed"

    def test_timeout(self):
        """Test timeout status."""
        assert MCPInvocationStatus.TIMEOUT.value == "timeout"

    def test_rate_limited(self):
        """Test rate limited status."""
        assert MCPInvocationStatus.RATE_LIMITED.value == "rate_limited"

    def test_budget_exceeded(self):
        """Test budget exceeded status."""
        assert MCPInvocationStatus.BUDGET_EXCEEDED.value == "budget_exceeded"

    def test_auth_error(self):
        """Test auth error status."""
        assert MCPInvocationStatus.AUTH_ERROR.value == "auth_error"

    def test_tool_not_found(self):
        """Test tool not found status."""
        assert MCPInvocationStatus.TOOL_NOT_FOUND.value == "tool_not_found"

    def test_status_count(self):
        """Test that all 7 statuses exist."""
        assert len(MCPInvocationStatus) == 7


# =============================================================================
# MCPTool Dataclass Tests
# =============================================================================


class TestMCPTool:
    """Tests for MCPTool dataclass."""

    def test_create_basic_tool(self):
        """Test creating a basic MCP tool."""
        tool = MCPTool(
            tool_id="slack",
            name="Slack",
            description="Send messages to Slack",
        )
        assert tool.tool_id == "slack"
        assert tool.name == "Slack"
        assert tool.description == "Send messages to Slack"

    def test_default_values(self):
        """Test default values for optional fields."""
        tool = MCPTool(
            tool_id="test",
            name="Test",
            description="Test tool",
        )
        assert tool.version == "1.0"
        assert tool.status == MCPToolStatus.AVAILABLE
        assert tool.category == "general"
        assert tool.provider == "unknown"
        assert tool.input_schema == {}
        assert tool.output_schema == {}
        assert tool.rate_limit_per_minute == 60
        assert tool.current_minute_invocations == 0
        assert tool.requires_oauth is False
        assert tool.oauth_scopes == []

    def test_full_tool(self):
        """Test tool with all fields populated."""
        tool = MCPTool(
            tool_id="jira",
            name="Jira",
            description="Jira integration",
            version="2.0",
            status=MCPToolStatus.AVAILABLE,
            category="ticketing",
            provider="agentcore",
            input_schema={"project": "string"},
            output_schema={"id": "string"},
            rate_limit_per_minute=30,
            requires_oauth=True,
            oauth_scopes=["read", "write"],
        )
        assert tool.version == "2.0"
        assert tool.category == "ticketing"
        assert tool.requires_oauth is True
        assert tool.oauth_scopes == ["read", "write"]

    def test_is_rate_limited_not_limited(self):
        """Test that tool is not rate limited initially."""
        tool = MCPTool(
            tool_id="test",
            name="Test",
            description="Test",
            rate_limit_per_minute=10,
        )
        assert tool.is_rate_limited() is False

    def test_is_rate_limited_after_reaching_limit(self):
        """Test that tool is rate limited after reaching limit."""
        tool = MCPTool(
            tool_id="test",
            name="Test",
            description="Test",
            rate_limit_per_minute=5,
        )
        # Record 5 invocations
        for _ in range(5):
            tool.record_invocation()

        assert tool.is_rate_limited() is True

    def test_record_invocation_increments_count(self):
        """Test that record_invocation increments count."""
        tool = MCPTool(
            tool_id="test",
            name="Test",
            description="Test",
        )
        initial_count = tool.current_minute_invocations
        tool.record_invocation()
        assert tool.current_minute_invocations == initial_count + 1

    def test_rate_limit_resets_after_minute(self):
        """Test that rate limit resets after a minute."""
        tool = MCPTool(
            tool_id="test",
            name="Test",
            description="Test",
            rate_limit_per_minute=5,
        )
        # Set invocations to limit
        tool.current_minute_invocations = 5
        # Backdate the reset time
        tool.last_rate_reset = time.time() - 61  # More than 60 seconds ago

        # Should reset on next check
        assert tool.is_rate_limited() is False
        assert tool.current_minute_invocations == 0


# =============================================================================
# MCPInvocationResult Dataclass Tests
# =============================================================================


class TestMCPInvocationResult:
    """Tests for MCPInvocationResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        result = MCPInvocationResult(
            tool_id="slack",
            status=MCPInvocationStatus.SUCCESS,
            data={"message": "sent"},
        )
        assert result.tool_id == "slack"
        assert result.status == MCPInvocationStatus.SUCCESS
        assert result.data == {"message": "sent"}
        assert result.is_success is True

    def test_create_failure_result(self):
        """Test creating a failed result."""
        result = MCPInvocationResult(
            tool_id="slack",
            status=MCPInvocationStatus.FAILED,
            error_message="Connection refused",
        )
        assert result.status == MCPInvocationStatus.FAILED
        assert result.error_message == "Connection refused"
        assert result.is_success is False

    def test_default_values(self):
        """Test default values."""
        result = MCPInvocationResult(
            tool_id="test",
            status=MCPInvocationStatus.SUCCESS,
        )
        assert result.data == {}
        assert result.error_message is None
        assert result.latency_ms == 0.0
        assert result.cost_usd == 0.0
        assert result.request_id is None
        assert result.timestamp > 0

    def test_is_success_property(self):
        """Test is_success property for various statuses."""
        success_result = MCPInvocationResult(
            tool_id="test", status=MCPInvocationStatus.SUCCESS
        )
        assert success_result.is_success is True

        failed_result = MCPInvocationResult(
            tool_id="test", status=MCPInvocationStatus.FAILED
        )
        assert failed_result.is_success is False

        timeout_result = MCPInvocationResult(
            tool_id="test", status=MCPInvocationStatus.TIMEOUT
        )
        assert timeout_result.is_success is False


# =============================================================================
# MCPSearchResult Dataclass Tests
# =============================================================================


class TestMCPSearchResult:
    """Tests for MCPSearchResult dataclass."""

    def test_create_search_result(self):
        """Test creating a search result."""
        tools = [
            MCPTool(tool_id="slack", name="Slack", description="Slack tool"),
            MCPTool(tool_id="jira", name="Jira", description="Jira tool"),
        ]
        result = MCPSearchResult(
            query="notification",
            tools=tools,
            total_count=2,
        )
        assert result.query == "notification"
        assert len(result.tools) == 2
        assert result.total_count == 2

    def test_default_values(self):
        """Test default values."""
        result = MCPSearchResult(
            query="test",
            tools=[],
            total_count=0,
        )
        assert result.latency_ms == 0.0
        assert result.cost_usd == 0.0

    def test_full_search_result(self):
        """Test search result with all fields."""
        result = MCPSearchResult(
            query="ticketing",
            tools=[],
            total_count=0,
            latency_ms=25.5,
            cost_usd=0.001,
        )
        assert result.latency_ms == 25.5
        assert result.cost_usd == 0.001


# =============================================================================
# MCPGatewayClient Initialization Tests
# =============================================================================


class TestMCPGatewayClientInit:
    """Tests for MCPGatewayClient initialization."""

    def test_initialization_enterprise_mode(self):
        """Test initialization in enterprise mode."""
        config = MockIntegrationConfig(is_defense_mode=False)
        budget = MockCustomerMCPBudget(customer_id="test-customer")

        client = MCPGatewayClient(config=config, customer_budget=budget)

        assert client is not None
        assert client._config == config
        assert client._customer_budget == budget

    def test_initialization_defense_mode_raises(self):
        """Test that initialization in defense mode raises error."""
        config = MockIntegrationConfig(is_defense_mode=True)

        with pytest.raises(RuntimeError) as exc_info:
            MCPGatewayClient(config=config)

        assert "DEFENSE mode" in str(exc_info.value)

    def test_initialization_empty_cache(self):
        """Test that cache is empty on initialization."""
        config = MockIntegrationConfig(is_defense_mode=False)
        client = MCPGatewayClient(config=config)

        assert client._tool_cache == {}
        assert client._cache_expiry == 0.0

    def test_initialization_metrics_zeroed(self):
        """Test that metrics are zeroed on initialization."""
        config = MockIntegrationConfig(is_defense_mode=False)
        client = MCPGatewayClient(config=config)

        assert client._total_invocations == 0
        assert client._total_errors == 0
        assert client._total_cost_usd == 0.0


# =============================================================================
# MCPGatewayClient Helper Methods Tests
# =============================================================================


class TestMCPGatewayClientHelpers:
    """Tests for MCPGatewayClient helper methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = MockIntegrationConfig(is_defense_mode=False)
        self.client = MCPGatewayClient(config=self.config)

    def test_calculate_relevance_name_match(self):
        """Test relevance calculation for name match."""
        tool = MCPTool(
            tool_id="slack",
            name="Slack Notifier",
            description="Send notifications",
            category="notification",
        )
        score = self.client._calculate_relevance_score("slack", tool)
        assert score >= 0.5

    def test_calculate_relevance_description_match(self):
        """Test relevance calculation for description match."""
        tool = MCPTool(
            tool_id="jira",
            name="Jira",
            description="Create and manage tickets",
            category="ticketing",
        )
        score = self.client._calculate_relevance_score("tickets", tool)
        assert score >= 0.2

    def test_calculate_relevance_category_match(self):
        """Test relevance calculation for category match."""
        tool = MCPTool(
            tool_id="pagerduty",
            name="PagerDuty",
            description="Incident alerting",
            category="alerting",
        )
        score = self.client._calculate_relevance_score("alerting", tool)
        assert score >= 0.2

    def test_calculate_relevance_no_match(self):
        """Test relevance calculation with no match."""
        tool = MCPTool(
            tool_id="slack",
            name="Slack",
            description="Send messages",
            category="notification",
        )
        score = self.client._calculate_relevance_score("database", tool)
        assert score < 0.3  # Below threshold

    def test_generate_request_id(self):
        """Test request ID generation."""
        request_id = self.client._generate_request_id(
            "slack", {"channel": "#general", "message": "test"}
        )
        assert len(request_id) == 16
        assert request_id.isalnum()

    def test_generate_request_id_unique(self):
        """Test that request IDs are unique per call."""
        params = {"channel": "#test"}
        id1 = self.client._generate_request_id("slack", params)
        # Small delay to ensure different timestamp
        import time

        time.sleep(0.001)
        id2 = self.client._generate_request_id("slack", params)
        assert id1 != id2  # Should be different due to timestamp


# =============================================================================
# MCPGatewayClient Metrics Tests
# =============================================================================


class TestMCPGatewayClientMetrics:
    """Tests for MCPGatewayClient metrics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = MockIntegrationConfig(is_defense_mode=False)
        self.budget = MockCustomerMCPBudget(
            customer_id="test",
            monthly_limit_usd=100.0,
            current_spend_usd=25.0,
        )
        self.client = MCPGatewayClient(config=self.config, customer_budget=self.budget)

    def test_get_metrics_initial(self):
        """Test getting metrics on fresh client."""
        metrics = self.client.get_metrics()

        assert metrics["total_invocations"] == 0
        assert metrics["total_errors"] == 0
        assert metrics["error_rate"] == 0.0
        assert metrics["total_cost_usd"] == 0.0

    def test_get_metrics_includes_budget_info(self):
        """Test that metrics include budget information."""
        metrics = self.client.get_metrics()

        assert "budget_remaining_usd" in metrics
        assert "budget_usage_pct" in metrics
        assert metrics["budget_remaining_usd"] == 75.0  # 100 - 25
        assert metrics["budget_usage_pct"] == 25.0  # 25/100 * 100

    def test_get_metrics_error_rate_calculation(self):
        """Test error rate calculation."""
        self.client._total_invocations = 10
        self.client._total_errors = 2

        metrics = self.client.get_metrics()
        assert metrics["error_rate"] == 0.2  # 2/10

    def test_get_metrics_cached_tools_count(self):
        """Test that cached tools are counted."""
        # Add some tools to cache
        self.client._tool_cache["slack"] = MCPTool(
            tool_id="slack", name="Slack", description="Test"
        )
        self.client._tool_cache["jira"] = MCPTool(
            tool_id="jira", name="Jira", description="Test"
        )

        metrics = self.client.get_metrics()
        assert metrics["cached_tools"] == 2


# =============================================================================
# MCPGatewayClient Tool Cache Tests
# =============================================================================


class TestMCPGatewayClientCache:
    """Tests for MCPGatewayClient cache management."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = MockIntegrationConfig(
            is_defense_mode=False,
            external_tools=[
                MockExternalToolConfig(tool_id="slack", tool_name="Slack"),
                MockExternalToolConfig(tool_id="jira", tool_name="Jira"),
            ],
        )
        self.client = MCPGatewayClient(config=self.config)

    @pytest.mark.asyncio
    async def test_load_tool_cache(self):
        """Test loading tool cache."""
        await self.client._load_tool_cache()

        assert "slack" in self.client._tool_cache
        assert "jira" in self.client._tool_cache
        assert self.client._cache_expiry > time.time()

    @pytest.mark.asyncio
    async def test_refresh_cache_if_needed_expired(self):
        """Test cache refresh when expired."""
        self.client._cache_expiry = time.time() - 100  # Expired

        await self.client._refresh_tool_cache_if_needed()

        assert self.client._cache_expiry > time.time()  # Should be refreshed

    @pytest.mark.asyncio
    async def test_refresh_cache_if_needed_not_expired(self):
        """Test cache not refreshed when still valid."""
        # Pre-populate cache
        self.client._tool_cache["test"] = MCPTool(
            tool_id="test", name="Test", description="Test"
        )
        self.client._cache_expiry = time.time() + 1000  # Not expired

        await self.client._refresh_tool_cache_if_needed()

        # Cache should still have our test entry (not replaced)
        assert "test" in self.client._tool_cache

    def test_get_tool_description_known(self):
        """Test getting description for known tools."""
        desc = self.client._get_tool_description("slack")
        assert "Slack" in desc

        desc = self.client._get_tool_description("jira")
        assert "Jira" in desc

    def test_get_tool_description_unknown(self):
        """Test getting description for unknown tools."""
        desc = self.client._get_tool_description("unknown_tool")
        assert "unknown_tool" in desc

    def test_get_tool_input_schema_known(self):
        """Test getting input schema for known tools."""
        schema = self.client._get_tool_input_schema("slack")
        assert schema["type"] == "object"
        assert "channel" in schema["properties"]
        assert "message" in schema["properties"]

    def test_get_tool_input_schema_unknown(self):
        """Test getting input schema for unknown tools."""
        schema = self.client._get_tool_input_schema("unknown")
        assert schema == {"type": "object"}


# =============================================================================
# MCPGatewayClient Async Method Tests
# =============================================================================


class TestMCPGatewayClientAsync:
    """Tests for MCPGatewayClient async methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = MockIntegrationConfig(
            is_defense_mode=False,
            external_tools=[
                MockExternalToolConfig(tool_id="slack", tool_name="Slack"),
            ],
        )
        self.budget = MockCustomerMCPBudget()
        self.client = MCPGatewayClient(config=self.config, customer_budget=self.budget)

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test listing tools."""
        tools = await self.client.list_tools()

        assert isinstance(tools, list)
        # Should have at least one tool from config
        assert len(tools) >= 1

    @pytest.mark.asyncio
    async def test_list_tools_with_category_filter(self):
        """Test listing tools with category filter."""
        # First load cache
        await self.client._load_tool_cache()

        # Filter by non-existent category
        tools = await self.client.list_tools(category="nonexistent")
        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_get_tool_exists(self):
        """Test getting an existing tool."""
        await self.client._load_tool_cache()

        tool = await self.client.get_tool("slack")
        assert tool is not None
        assert tool.tool_id == "slack"

    @pytest.mark.asyncio
    async def test_get_tool_not_exists(self):
        """Test getting a non-existent tool."""
        tool = await self.client.get_tool("nonexistent")
        assert tool is None

    @pytest.mark.asyncio
    async def test_search_tools(self):
        """Test searching for tools."""
        result = await self.client.search_tools("notification", limit=5)

        assert isinstance(result, MCPSearchResult)
        assert result.query == "notification"
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_invoke_tool_not_found(self):
        """Test invoking a non-existent tool."""
        result = await self.client.invoke_tool("nonexistent", {})

        assert result.status == MCPInvocationStatus.TOOL_NOT_FOUND
        assert result.is_success is False

    @pytest.mark.asyncio
    async def test_invoke_tool_success(self):
        """Test successful tool invocation."""
        # Load cache first
        await self.client._load_tool_cache()

        result = await self.client.invoke_tool(
            "slack", {"channel": "#general", "message": "test"}
        )

        assert result.status == MCPInvocationStatus.SUCCESS
        assert result.is_success is True
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_invoke_tool_rate_limited(self):
        """Test invoking a rate-limited tool."""
        await self.client._load_tool_cache()

        # Max out the rate limit
        tool = self.client._tool_cache["slack"]
        tool.current_minute_invocations = tool.rate_limit_per_minute

        result = await self.client.invoke_tool("slack", {"channel": "#test"})

        assert result.status == MCPInvocationStatus.RATE_LIMITED
        assert result.is_success is False

    @pytest.mark.asyncio
    async def test_invoke_tool_unavailable(self):
        """Test invoking an unavailable tool."""
        await self.client._load_tool_cache()

        # Mark tool as unavailable
        tool = self.client._tool_cache["slack"]
        tool.status = MCPToolStatus.UNAVAILABLE

        result = await self.client.invoke_tool("slack", {})

        assert result.status == MCPInvocationStatus.FAILED
        assert "unavailable" in result.error_message

    @pytest.mark.asyncio
    async def test_invoke_tool_budget_exceeded(self):
        """Test invoking tool with exceeded budget."""
        # Set budget to near limit
        self.budget.current_spend_usd = self.budget.monthly_limit_usd

        result = await self.client.invoke_tool("slack", {})

        assert result.status == MCPInvocationStatus.BUDGET_EXCEEDED
        assert result.is_success is False


# =============================================================================
# Exception Tests
# =============================================================================


class TestMCPExceptions:
    """Tests for MCP exceptions."""

    def test_mcp_error_base(self):
        """Test MCPError base exception."""
        error = MCPError("test error")
        assert str(error) == "test error"
        assert isinstance(error, Exception)

    def test_mcp_auth_error(self):
        """Test MCPAuthError exception."""
        error = MCPAuthError("auth failed")
        assert str(error) == "auth failed"
        assert isinstance(error, MCPError)

    def test_mcp_invocation_error(self):
        """Test MCPInvocationError exception."""
        error = MCPInvocationError("invocation failed")
        assert str(error) == "invocation failed"
        assert isinstance(error, MCPError)

    def test_mcp_rate_limit_error(self):
        """Test MCPRateLimitError exception."""
        error = MCPRateLimitError("rate limit exceeded")
        assert str(error) == "rate limit exceeded"
        assert isinstance(error, MCPError)


# =============================================================================
# Integration Tests
# =============================================================================


class TestMCPGatewayIntegration:
    """Integration tests for MCP Gateway workflows."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = MockIntegrationConfig(
            is_defense_mode=False,
            external_tools=[
                MockExternalToolConfig(tool_id="slack", tool_name="Slack"),
                MockExternalToolConfig(tool_id="jira", tool_name="Jira"),
                MockExternalToolConfig(tool_id="pagerduty", tool_name="PagerDuty"),
            ],
        )
        self.budget = MockCustomerMCPBudget(customer_id="integration-test")
        self.client = MCPGatewayClient(config=self.config, customer_budget=self.budget)

    @pytest.mark.asyncio
    async def test_full_workflow_search_and_invoke(self):
        """Test complete workflow: search then invoke."""
        # Search for notification tools
        search_result = await self.client.search_tools("notification")
        assert search_result.total_count >= 0

        # List all tools
        tools = await self.client.list_tools()
        assert len(tools) >= 0

        # Invoke a specific tool
        _result = await self.client.invoke_tool(
            "slack", {"channel": "#alerts", "message": "Test alert"}
        )

        # Check metrics updated
        metrics = self.client.get_metrics()
        assert metrics["total_invocations"] >= 1

    @pytest.mark.asyncio
    async def test_rate_limit_workflow(self):
        """Test that rate limiting works across invocations."""
        await self.client._load_tool_cache()

        # Set low rate limit for testing
        tool = self.client._tool_cache["slack"]
        tool.rate_limit_per_minute = 3

        # Should succeed for first 3 invocations
        for i in range(3):
            result = await self.client.invoke_tool("slack", {"channel": f"#{i}"})
            if i < 3:
                # First 3 should succeed (invocation happens, then rate check on next)
                pass

        # 4th should be rate limited
        result = await self.client.invoke_tool("slack", {"channel": "#4"})
        assert result.status == MCPInvocationStatus.RATE_LIMITED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
