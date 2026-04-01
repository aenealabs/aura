"""
Tests for MCP Tool Server.

Tests internal MCP tool integration (Neptune, OpenSearch, Sandbox).
ADR-029 Phase 1.4 Implementation.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.mcp_tool_server import (
    MCPServerStats,
    MCPToolCategory,
    MCPToolDefinition,
    MCPToolPermission,
    MCPToolResult,
    MCPToolServer,
    create_mcp_tool_server,
)

# =============================================================================
# MCPToolCategory Tests
# =============================================================================


class TestMCPToolCategory:
    """Tests for MCPToolCategory enum."""

    def test_categories_exist(self):
        """Test all expected categories exist."""
        assert MCPToolCategory.GRAPH.value == "graph"
        assert MCPToolCategory.VECTOR.value == "vector"
        assert MCPToolCategory.SANDBOX.value == "sandbox"
        assert MCPToolCategory.EMBEDDING.value == "embedding"
        assert MCPToolCategory.CACHE.value == "cache"


# =============================================================================
# MCPToolDefinition Tests
# =============================================================================


class TestMCPToolDefinition:
    """Tests for MCPToolDefinition dataclass."""

    def test_tool_definition_creation(self):
        """Test creating a tool definition."""
        tool = MCPToolDefinition(
            name="test_tool",
            description="A test tool",
            category=MCPToolCategory.GRAPH,
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
            output_schema={"type": "object"},
            requires_approval=False,
        )

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.category == MCPToolCategory.GRAPH
        assert not tool.requires_approval
        assert tool.version == "1.0"
        assert tool.timeout_seconds == 30

    def test_tool_definition_with_approval(self):
        """Test tool definition requiring approval."""
        tool = MCPToolDefinition(
            name="dangerous_tool",
            description="A dangerous tool",
            category=MCPToolCategory.SANDBOX,
            input_schema={},
            output_schema={},
            requires_approval=True,
        )

        assert tool.requires_approval

    def test_tool_definition_with_permissions(self):
        """Test tool definition with custom permissions."""
        tool = MCPToolDefinition(
            name="write_tool",
            description="A write tool",
            category=MCPToolCategory.GRAPH,
            input_schema={},
            output_schema={},
            permissions=[MCPToolPermission.WRITE, MCPToolPermission.EXECUTE],
        )

        assert MCPToolPermission.WRITE in tool.permissions
        assert MCPToolPermission.EXECUTE in tool.permissions


class TestMCPToolResult:
    """Tests for MCPToolResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = MCPToolResult(
            tool_name="semantic_search",
            success=True,
            data={"key": "value"},
            latency_ms=50.5,
        )

        assert result.success
        assert result.is_success
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_error_result(self):
        """Test error result."""
        result = MCPToolResult(
            tool_name="failed_tool",
            success=False,
            data={},
            error="Something went wrong",
            latency_ms=10.0,
        )

        assert not result.success
        assert not result.is_success
        assert result.error == "Something went wrong"


class TestMCPServerStats:
    """Tests for MCPServerStats dataclass."""

    def test_initial_stats(self):
        """Test initial stats are zero."""
        stats = MCPServerStats()

        assert stats.total_invocations == 0
        assert stats.success_rate == 0.0
        assert stats.avg_latency_ms == 0.0

    def test_stats_calculations(self):
        """Test stats calculations."""
        stats = MCPServerStats(
            total_invocations=10,
            successful_invocations=8,
            failed_invocations=2,
            total_latency_ms=500.0,
        )

        assert stats.success_rate == 0.8
        assert stats.avg_latency_ms == 50.0

    def test_stats_to_dict(self):
        """Test stats to_dict method."""
        stats = MCPServerStats(
            total_invocations=10,
            successful_invocations=9,
            failed_invocations=1,
            total_latency_ms=300.0,
        )

        d = stats.to_dict()
        assert d["total_invocations"] == 10
        assert d["success_rate_percent"] == 90.0
        assert d["avg_latency_ms"] == 30.0


# =============================================================================
# MCPToolServer Tests
# =============================================================================


class TestMCPToolServer:
    """Tests for MCPToolServer."""

    @pytest.fixture
    def mock_server(self):
        """Create server in mock mode (no real services)."""
        return MCPToolServer()

    @pytest.fixture
    def server_with_services(self):
        """Create server with mock services."""
        neptune = MagicMock()
        neptune.query.return_value = []

        opensearch = MagicMock()
        opensearch.search.return_value = {"hits": {"hits": []}}

        embedding = AsyncMock()
        embedding.embed.return_value = [0.1] * 1536

        sandbox = AsyncMock()
        sandbox.provision.return_value = {"sandbox_id": "sb-123", "status": "running"}

        return MCPToolServer(
            neptune_service=neptune,
            opensearch_service=opensearch,
            embedding_service=embedding,
            sandbox_service=sandbox,
        )

    def test_list_tools(self, mock_server):
        """Test listing all tools."""
        tools = mock_server.list_tools()

        assert len(tools) == 7  # 2 graph + 2 vector + 3 sandbox
        tool_names = {t.name for t in tools}
        assert "query_code_graph" in tool_names
        assert "semantic_search" in tool_names
        assert "provision_sandbox" in tool_names

    def test_list_tools_by_category(self, mock_server):
        """Test listing tools by category."""
        graph_tools = mock_server.list_tools(category=MCPToolCategory.GRAPH)
        vector_tools = mock_server.list_tools(category=MCPToolCategory.VECTOR)
        sandbox_tools = mock_server.list_tools(category=MCPToolCategory.SANDBOX)

        assert len(graph_tools) == 2
        assert len(vector_tools) == 2
        assert len(sandbox_tools) == 3

    def test_get_tool(self, mock_server):
        """Test getting a specific tool."""
        tool = mock_server.get_tool("semantic_search")

        assert tool is not None
        assert tool.name == "semantic_search"
        assert tool.category == MCPToolCategory.VECTOR

    def test_get_tool_not_found(self, mock_server):
        """Test getting non-existent tool returns None."""
        tool = mock_server.get_tool("nonexistent_tool")

        assert tool is None

    @pytest.mark.asyncio
    async def test_invoke_tool_success(self, mock_server):
        """Test successful tool invocation."""
        params = {"query": "test query", "k": 5}

        result = await mock_server.invoke_tool("semantic_search", params)

        assert result.success
        assert result.latency_ms >= 0
        assert result.tool_name == "semantic_search"

    @pytest.mark.asyncio
    async def test_invoke_tool_not_found(self, mock_server):
        """Test invoking non-existent tool."""
        result = await mock_server.invoke_tool("nonexistent_tool", {})

        assert not result.success
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invoke_tool_skip_approval(self, mock_server):
        """Test tool with skip_approval=True."""
        params = {"sandbox_id": "sb-123"}

        result = await mock_server.invoke_tool(
            "destroy_sandbox", params, skip_approval=True
        )

        assert result.success

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_server):
        """Test getting server stats."""
        # Invoke a tool first
        await mock_server.invoke_tool("semantic_search", {"query": "test", "k": 5})

        stats = mock_server.get_stats()

        # get_stats returns {"server": {...}, "tools": {...}}
        assert "server" in stats
        assert "tools" in stats
        assert stats["server"]["total_invocations"] == 1
        assert stats["server"]["successful_invocations"] == 1

    def test_list_tools_returns_definitions(self, mock_server):
        """Test list_tools returns tool definitions."""
        tools = mock_server.list_tools()

        assert len(tools) == 7
        assert all(isinstance(t, MCPToolDefinition) for t in tools)

    @pytest.mark.asyncio
    async def test_stats_increment_on_invocation(self, mock_server):
        """Test stats increment on invocation."""
        initial_stats = mock_server.get_stats()
        initial_count = initial_stats["server"]["total_invocations"]

        await mock_server.invoke_tool("semantic_search", {"query": "test", "k": 5})

        updated_stats = mock_server.get_stats()
        assert updated_stats["server"]["total_invocations"] == initial_count + 1


# =============================================================================
# Tool-Specific Tests
# =============================================================================


class TestGraphTools:
    """Tests for graph-related tools."""

    @pytest.fixture
    def mock_server(self):
        """Create mock server."""
        return create_mcp_tool_server()

    @pytest.mark.asyncio
    async def test_query_code_graph(self, mock_server):
        """Test querying code graph."""
        result = await mock_server.invoke_tool(
            "query_code_graph",
            {"query": "g.V().hasLabel('Function').limit(10)", "depth": 2},
        )

        assert result.success
        assert "results" in result.data

    @pytest.mark.asyncio
    async def test_get_code_dependencies(self, mock_server):
        """Test getting code dependencies."""
        result = await mock_server.invoke_tool(
            "get_code_dependencies",
            {"entity_id": "func_123", "direction": "outbound"},
        )

        assert result.success
        assert "dependencies" in result.data


class TestVectorTools:
    """Tests for vector-related tools."""

    @pytest.fixture
    def mock_server(self):
        """Create mock server."""
        return create_mcp_tool_server()

    @pytest.mark.asyncio
    async def test_semantic_search(self, mock_server):
        """Test semantic search."""
        result = await mock_server.invoke_tool(
            "semantic_search",
            {"query": "authentication logic", "k": 5},
        )

        assert result.success
        assert "results" in result.data

    @pytest.mark.asyncio
    async def test_index_code_embedding(self, mock_server):
        """Test indexing code embedding."""
        result = await mock_server.invoke_tool(
            "index_code_embedding",
            {
                "content": "def process_data(data): pass",
                "metadata": {"file": "main.py"},
            },
        )

        assert result.success
        assert result.data.get("indexed", False)


class TestSandboxTools:
    """Tests for sandbox-related tools."""

    @pytest.fixture
    def mock_server(self):
        """Create mock server."""
        return create_mcp_tool_server()

    @pytest.mark.asyncio
    async def test_provision_sandbox(self, mock_server):
        """Test provisioning sandbox."""
        result = await mock_server.invoke_tool(
            "provision_sandbox",
            {"isolation_level": "container", "timeout_minutes": 30},
            skip_approval=True,
        )

        assert result.success
        assert "sandbox_id" in result.data

    @pytest.mark.asyncio
    async def test_destroy_sandbox(self, mock_server):
        """Test destroying sandbox."""
        result = await mock_server.invoke_tool(
            "destroy_sandbox",
            {"sandbox_id": "sb-123"},
            skip_approval=True,
        )

        assert result.success

    @pytest.mark.asyncio
    async def test_get_sandbox_status(self, mock_server):
        """Test getting sandbox status."""
        result = await mock_server.invoke_tool(
            "get_sandbox_status",
            {"sandbox_id": "sb-123"},
        )

        assert result.success
        assert "status" in result.data

    def test_provision_requires_approval(self, mock_server):
        """Test provision sandbox requires approval."""
        tool = mock_server.get_tool("provision_sandbox")
        assert tool.requires_approval

    def test_destroy_does_not_require_approval(self, mock_server):
        """Test destroy sandbox does not require approval by default."""
        # Destroying is safe - cleanup operation
        tool = mock_server.get_tool("destroy_sandbox")
        assert not tool.requires_approval

    def test_get_status_does_not_require_approval(self, mock_server):
        """Test get sandbox status does not require approval."""
        # Read-only operation
        tool = mock_server.get_tool("get_sandbox_status")
        assert not tool.requires_approval


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateMCPToolServer:
    """Tests for create_mcp_tool_server factory."""

    def test_create_server_mock_mode(self):
        """Test creating server in mock mode."""
        server = create_mcp_tool_server()

        assert server is not None
        assert len(server.list_tools()) == 7

    def test_create_server_tools_available(self):
        """Test created server has all expected tools."""
        server = create_mcp_tool_server()
        tool_names = {t.name for t in server.list_tools()}

        expected_tools = {
            "query_code_graph",
            "get_code_dependencies",
            "semantic_search",
            "index_code_embedding",
            "provision_sandbox",
            "destroy_sandbox",
            "get_sandbox_status",
        }

        assert tool_names == expected_tools


# =============================================================================
# Integration Tests (Mock)
# =============================================================================


class TestMCPToolServerIntegration:
    """Integration tests for MCP tool server."""

    @pytest.mark.asyncio
    async def test_full_workflow_graph_query(self):
        """Test full workflow: graph query."""
        server = create_mcp_tool_server()

        # Query the graph
        result = await server.invoke_tool(
            "query_code_graph",
            {"query": "g.V().hasLabel('Function').limit(10)", "depth": 2},
        )

        assert result.success
        assert "results" in result.data

    @pytest.mark.asyncio
    async def test_full_workflow_semantic_search(self):
        """Test full workflow: semantic search."""
        server = create_mcp_tool_server()

        # Perform semantic search
        result = await server.invoke_tool(
            "semantic_search",
            {"query": "authentication handler", "k": 5},
        )

        assert result.success
        assert "results" in result.data

    @pytest.mark.asyncio
    async def test_full_workflow_sandbox(self):
        """Test full workflow: sandbox operations."""
        server = create_mcp_tool_server()

        # Provision sandbox
        provision_result = await server.invoke_tool(
            "provision_sandbox",
            {"isolation_level": "container", "timeout_minutes": 30},
            skip_approval=True,
        )

        assert provision_result.success
        sandbox_id = provision_result.data.get("sandbox_id")
        assert sandbox_id is not None

        # Get status
        status_result = await server.invoke_tool(
            "get_sandbox_status",
            {"sandbox_id": sandbox_id},
        )

        assert status_result.success

        # Destroy sandbox
        destroy_result = await server.invoke_tool(
            "destroy_sandbox",
            {"sandbox_id": sandbox_id},
            skip_approval=True,
        )

        assert destroy_result.success

    @pytest.mark.asyncio
    async def test_multiple_concurrent_invocations(self):
        """Test multiple concurrent tool invocations."""
        import asyncio

        server = create_mcp_tool_server()

        # Run multiple tools concurrently
        results = await asyncio.gather(
            server.invoke_tool("semantic_search", {"query": "auth", "k": 5}),
            server.invoke_tool("query_code_graph", {"query": "test", "depth": 2}),
            server.invoke_tool("get_sandbox_status", {"sandbox_id": "sb-test"}),
        )

        assert all(r.success for r in results)
        stats = server.get_stats()
        assert stats["server"]["total_invocations"] == 3

    @pytest.mark.asyncio
    async def test_stats_tracking_across_invocations(self):
        """Test stats are tracked correctly across invocations."""
        server = create_mcp_tool_server()

        # Multiple successful invocations
        for _ in range(5):
            await server.invoke_tool("semantic_search", {"query": "test", "k": 5})

        stats = server.get_stats()
        assert stats["server"]["total_invocations"] == 5
        assert stats["server"]["successful_invocations"] == 5
        assert stats["server"]["success_rate_percent"] == 100.0

        # One failed invocation
        await server.invoke_tool("nonexistent_tool", {})

        stats = server.get_stats()
        assert stats["server"]["total_invocations"] == 6
        assert stats["server"]["failed_invocations"] == 1
        # 5/6 = 0.8333... → 83.33%
        assert round(stats["server"]["success_rate_percent"], 2) == 83.33


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_params(self):
        """Test tool invocation with empty params."""
        server = create_mcp_tool_server()

        result = await server.invoke_tool("query_code_graph", {})

        # Should succeed with defaults
        assert result.success

    @pytest.mark.asyncio
    async def test_invalid_tool_name_types(self):
        """Test tool invocation with various invalid inputs."""
        server = create_mcp_tool_server()

        # Empty string
        result = await server.invoke_tool("", {})
        assert not result.success

    @pytest.mark.asyncio
    async def test_large_k_value(self):
        """Test semantic search with large k value."""
        server = create_mcp_tool_server()

        result = await server.invoke_tool(
            "semantic_search",
            {"query": "test", "k": 1000},
        )

        assert result.success
