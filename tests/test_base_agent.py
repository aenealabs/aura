"""
Tests for Base Agent with MCP Tool Support.

Tests MCPToolMixin, BaseAgent, and MCPEnabledAgent classes.
ADR-029 Phase 1.4 Implementation.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.base_agent import (
    AgentResult,
    AgentTask,
    BaseAgent,
    HITLApprovalRequest,
    HITLApprovalResponse,
    MCPEnabledAgent,
    MCPToolMixin,
    ToolInvocationError,
    ToolNotFoundError,
)

# =============================================================================
# Data Class Tests
# =============================================================================


class TestAgentTask:
    """Tests for AgentTask dataclass."""

    def test_task_creation_minimal(self):
        """Test creating task with minimal fields."""
        task = AgentTask(
            task_id="task-001",
            task_type="analysis",
            description="Analyze code for vulnerabilities",
        )

        assert task.task_id == "task-001"
        assert task.task_type == "analysis"
        assert task.parameters == {}
        assert task.context == {}
        assert task.priority == 0
        assert task.timeout_seconds == 300

    def test_task_creation_full(self):
        """Test creating task with all fields."""
        task = AgentTask(
            task_id="task-002",
            task_type="remediation",
            description="Fix SHA1 vulnerability",
            parameters={"file": "main.py", "line": 42},
            context={"severity": "high"},
            priority=10,
            timeout_seconds=600,
        )

        assert task.priority == 10
        assert task.timeout_seconds == 600
        assert task.parameters["file"] == "main.py"


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = AgentResult(
            task_id="task-001",
            success=True,
            data={"analysis": "No vulnerabilities found"},
            execution_time_ms=150.5,
            tools_invoked=["semantic_search"],
        )

        assert result.success
        assert result.error is None
        assert len(result.tools_invoked) == 1

    def test_failure_result(self):
        """Test failure result."""
        result = AgentResult(
            task_id="task-001",
            success=False,
            error="Analysis failed: timeout",
        )

        assert not result.success
        assert result.error == "Analysis failed: timeout"


class TestHITLApprovalRequest:
    """Tests for HITLApprovalRequest dataclass."""

    def test_request_creation(self):
        """Test creating approval request."""
        request = HITLApprovalRequest(
            tool_name="provision_sandbox",
            params={"isolation_level": "vpc"},
            reason="Testing new patch",
        )

        assert request.tool_name == "provision_sandbox"
        assert request.requested_at > 0


class TestHITLApprovalResponse:
    """Tests for HITLApprovalResponse dataclass."""

    def test_approved_response(self):
        """Test approved response."""
        response = HITLApprovalResponse(
            approved=True,
            reason="Approved by admin",
            approver="admin@example.com",
        )

        assert response.approved

    def test_rejected_response(self):
        """Test rejected response."""
        response = HITLApprovalResponse(
            approved=False,
            reason="Security concern",
        )

        assert not response.approved


# =============================================================================
# MCPToolMixin Tests
# =============================================================================


class TestMCPToolMixin:
    """Tests for MCPToolMixin class."""

    @pytest.fixture
    def mock_mcp_server(self):
        """Create mock MCP server."""
        server = MagicMock()

        # Create mock tool definitions
        mock_tool = MagicMock()
        mock_tool.name = "semantic_search"
        mock_tool.description = "Search code semantically"
        mock_tool.input_schema = {"type": "object"}
        mock_tool.requires_approval = False
        mock_tool.category = MagicMock()
        mock_tool.category.value = "vector"

        server.list_tools.return_value = [mock_tool]

        # Create mock invoke result
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {"results": [{"content": "test"}]}
        mock_result.error = None
        mock_result.latency_ms = 50.0

        server.invoke_tool = AsyncMock(return_value=mock_result)

        return server

    @pytest.fixture
    def mixin_instance(self, mock_mcp_server):
        """Create a class instance with MCPToolMixin."""

        class TestMixin(MCPToolMixin):
            def __init__(self, mcp_server):
                self._init_mcp_tools(mcp_server=mcp_server)

        return TestMixin(mock_mcp_server)

    def test_init_mcp_tools(self, mixin_instance):
        """Test MCP tool initialization."""
        assert mixin_instance._tool_invocation_count == 0
        assert len(mixin_instance._pending_approvals) == 0

    def test_discover_tools(self, mixin_instance):
        """Test tool discovery."""
        tools = mixin_instance.get_available_tools()

        assert "semantic_search" in tools
        assert tools["semantic_search"]["source"] == "internal"

    def test_has_tool(self, mixin_instance):
        """Test has_tool method."""
        assert mixin_instance.has_tool("semantic_search")
        assert not mixin_instance.has_tool("nonexistent_tool")

    @pytest.mark.asyncio
    async def test_invoke_tool_success(self, mixin_instance, mock_mcp_server):
        """Test successful tool invocation."""
        result = await mixin_instance.invoke_tool(
            "semantic_search",
            {"query": "authentication", "k": 5},
        )

        assert "results" in result
        assert mixin_instance._tool_invocation_count == 1

    @pytest.mark.asyncio
    async def test_invoke_tool_not_found(self, mixin_instance):
        """Test invoking non-existent tool."""
        with pytest.raises(ToolNotFoundError, match="not available"):
            await mixin_instance.invoke_tool("nonexistent_tool", {})

    @pytest.mark.asyncio
    async def test_invoke_tool_failure(self, mixin_instance, mock_mcp_server):
        """Test tool invocation failure."""
        # Configure mock to fail
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Internal error"
        mock_mcp_server.invoke_tool.return_value = mock_result

        with pytest.raises(ToolInvocationError, match="Internal error"):
            await mixin_instance.invoke_tool("semantic_search", {})

    @pytest.mark.asyncio
    async def test_invoke_tools_parallel(self, mixin_instance):
        """Test parallel tool invocation."""
        invocations = [
            ("semantic_search", {"query": "auth", "k": 5}),
            ("semantic_search", {"query": "crypto", "k": 5}),
        ]

        results = await mixin_instance.invoke_tools_parallel(invocations)

        assert len(results) == 2
        assert mixin_instance._tool_invocation_count == 2

    def test_get_tool_metrics(self, mixin_instance):
        """Test getting tool metrics."""
        metrics = mixin_instance.get_tool_metrics()

        assert "total_invocations" in metrics
        assert "available_tools" in metrics
        assert metrics["available_tools"] == 1


class TestMCPToolMixinWithApproval:
    """Tests for MCPToolMixin with approval-required tools."""

    @pytest.fixture
    def mock_mcp_server_with_approval(self):
        """Create mock MCP server with approval-required tool."""
        server = MagicMock()

        mock_tool = MagicMock()
        mock_tool.name = "provision_sandbox"
        mock_tool.description = "Provision sandbox"
        mock_tool.input_schema = {"type": "object"}
        mock_tool.requires_approval = True
        mock_tool.category = MagicMock()
        mock_tool.category.value = "sandbox"

        server.list_tools.return_value = [mock_tool]

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {"sandbox_id": "sb-123"}
        mock_result.latency_ms = 100.0

        server.invoke_tool = AsyncMock(return_value=mock_result)

        return server

    @pytest.fixture
    def mixin_with_approval(self, mock_mcp_server_with_approval):
        """Create mixin instance with approval-required tool."""

        class TestMixin(MCPToolMixin):
            def __init__(self, mcp_server):
                self._init_mcp_tools(mcp_server=mcp_server)

        return TestMixin(mock_mcp_server_with_approval)

    @pytest.mark.asyncio
    async def test_approval_auto_approved_in_dev(self, mixin_with_approval):
        """Test that approval is auto-approved in dev mode."""
        # In dev mode, _request_hitl_approval auto-approves
        result = await mixin_with_approval.invoke_tool(
            "provision_sandbox",
            {"isolation_level": "container"},
        )

        assert result["sandbox_id"] == "sb-123"

    @pytest.mark.asyncio
    async def test_skip_approval(self, mixin_with_approval):
        """Test skip_approval parameter."""
        result = await mixin_with_approval.invoke_tool(
            "provision_sandbox",
            {"isolation_level": "container"},
            skip_approval=True,
        )

        assert result["sandbox_id"] == "sb-123"


# =============================================================================
# BaseAgent Tests
# =============================================================================


class TestBaseAgent:
    """Tests for BaseAgent abstract class."""

    @pytest.fixture
    def concrete_agent(self):
        """Create a concrete agent implementation for testing."""

        class TestAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"message": "Task completed"},
                )

        return TestAgent(agent_name="TestAgent")

    @pytest.fixture
    def failing_agent(self):
        """Create an agent that fails."""

        class FailingAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                raise ValueError("Simulated failure")

        return FailingAgent(agent_name="FailingAgent")

    @pytest.fixture
    def slow_agent(self):
        """Create a slow agent for timeout testing."""

        class SlowAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                await asyncio.sleep(10)  # Longer than test timeout
                return AgentResult(task_id=task.task_id, success=True)

        return SlowAgent(agent_name="SlowAgent")

    def test_agent_initialization(self, concrete_agent):
        """Test agent initialization."""
        assert concrete_agent.agent_name == "TestAgent"
        assert concrete_agent._tasks_executed == 0

    def test_agent_default_name(self):
        """Test agent uses class name if no name provided."""

        class MyCustomAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                return AgentResult(task_id=task.task_id, success=True)

        agent = MyCustomAgent()
        assert agent.agent_name == "MyCustomAgent"

    @pytest.mark.asyncio
    async def test_run_success(self, concrete_agent):
        """Test successful task execution."""
        task = AgentTask(
            task_id="test-001",
            task_type="test",
            description="Test task",
        )

        result = await concrete_agent.run(task)

        assert result.success
        assert result.task_id == "test-001"
        assert result.execution_time_ms > 0
        assert concrete_agent._tasks_executed == 1
        assert concrete_agent._tasks_succeeded == 1

    @pytest.mark.asyncio
    async def test_run_failure(self, failing_agent):
        """Test failed task execution."""
        task = AgentTask(
            task_id="test-002",
            task_type="test",
            description="Failing task",
        )

        result = await failing_agent.run(task)

        assert not result.success
        assert "Simulated failure" in result.error
        assert failing_agent._tasks_failed == 1

    @pytest.mark.asyncio
    async def test_run_timeout(self, slow_agent):
        """Test task timeout."""
        task = AgentTask(
            task_id="test-003",
            task_type="test",
            description="Slow task",
            timeout_seconds=1,  # 1 second timeout
        )

        result = await slow_agent.run(task)

        assert not result.success
        assert "timed out" in result.error.lower()
        assert slow_agent._tasks_failed == 1

    def test_get_metrics(self, concrete_agent):
        """Test getting agent metrics."""
        metrics = concrete_agent.get_metrics()

        assert metrics["agent_name"] == "TestAgent"
        assert metrics["tasks_executed"] == 0
        assert metrics["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_metrics_after_execution(self, concrete_agent):
        """Test metrics update after execution."""
        task = AgentTask(
            task_id="test-004",
            task_type="test",
            description="Metrics test",
        )

        await concrete_agent.run(task)
        metrics = concrete_agent.get_metrics()

        assert metrics["tasks_executed"] == 1
        assert metrics["tasks_succeeded"] == 1
        assert metrics["success_rate"] == 1.0


# =============================================================================
# MCPEnabledAgent Tests
# =============================================================================


class TestMCPEnabledAgent:
    """Tests for MCPEnabledAgent class."""

    @pytest.fixture
    def mock_mcp_server(self):
        """Create mock MCP server."""
        server = MagicMock()

        mock_tool = MagicMock()
        mock_tool.name = "semantic_search"
        mock_tool.description = "Search code"
        mock_tool.input_schema = {}
        mock_tool.requires_approval = False
        mock_tool.category = MagicMock()
        mock_tool.category.value = "vector"

        server.list_tools.return_value = [mock_tool]

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {"results": []}
        mock_result.latency_ms = 25.0

        server.invoke_tool = AsyncMock(return_value=mock_result)

        return server

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM client."""
        llm = AsyncMock()
        llm.generate.return_value = "Generated response"
        return llm

    @pytest.fixture
    def mcp_enabled_agent(self, mock_llm, mock_mcp_server):
        """Create MCP-enabled agent for testing."""

        class TestMCPAgent(MCPEnabledAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                # Use MCP tools
                search_result = await self.invoke_tool(
                    "semantic_search",
                    {"query": task.description, "k": 5},
                )

                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"search_results": search_result},
                    tools_invoked=["semantic_search"],
                )

        return TestMCPAgent(
            llm_client=mock_llm,
            mcp_server=mock_mcp_server,
            agent_name="TestMCPAgent",
        )

    def test_initialization(self, mcp_enabled_agent):
        """Test MCP-enabled agent initialization."""
        assert mcp_enabled_agent.agent_name == "TestMCPAgent"
        assert mcp_enabled_agent.has_tool("semantic_search")

    @pytest.mark.asyncio
    async def test_execute_with_tools(self, mcp_enabled_agent):
        """Test execution with MCP tools."""
        task = AgentTask(
            task_id="mcp-001",
            task_type="analysis",
            description="Find authentication code",
        )

        result = await mcp_enabled_agent.run(task)

        assert result.success
        assert "semantic_search" in result.tools_invoked

    def test_combined_metrics(self, mcp_enabled_agent):
        """Test combined agent and tool metrics."""
        metrics = mcp_enabled_agent.get_metrics()

        assert "agent_name" in metrics
        assert "tools" in metrics
        assert "available_tools" in metrics["tools"]


class TestMCPEnabledAgentWithLLM:
    """Tests for MCPEnabledAgent with LLM integration."""

    @pytest.fixture
    def full_agent_setup(self):
        """Create full agent setup with LLM and MCP."""
        # Mock LLM
        llm = AsyncMock()
        llm.generate.return_value = "Analysis complete: no vulnerabilities found"

        # Mock MCP server
        server = MagicMock()

        search_tool = MagicMock()
        search_tool.name = "semantic_search"
        search_tool.description = "Search code"
        search_tool.input_schema = {}
        search_tool.requires_approval = False
        search_tool.category = MagicMock()
        search_tool.category.value = "vector"

        graph_tool = MagicMock()
        graph_tool.name = "query_code_graph"
        graph_tool.description = "Query graph"
        graph_tool.input_schema = {}
        graph_tool.requires_approval = False
        graph_tool.category = MagicMock()
        graph_tool.category.value = "graph"

        server.list_tools.return_value = [search_tool, graph_tool]

        search_result = MagicMock()
        search_result.success = True
        search_result.data = {"results": [{"content": "def auth(): pass"}]}
        search_result.latency_ms = 30.0

        server.invoke_tool = AsyncMock(return_value=search_result)

        class SecurityAgent(MCPEnabledAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                # Step 1: Search for relevant code
                search_results = await self.invoke_tool(
                    "semantic_search",
                    {"query": task.description, "k": 10},
                )

                # Step 2: Analyze with LLM
                if self.llm:
                    analysis = await self.llm.generate(
                        f"Analyze: {search_results}",
                        agent=self.agent_name,
                    )
                else:
                    analysis = "No LLM available"

                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={
                        "search_results": search_results,
                        "analysis": analysis,
                    },
                    tools_invoked=["semantic_search"],
                )

        agent = SecurityAgent(
            llm_client=llm,
            mcp_server=server,
            agent_name="SecurityAgent",
        )

        return agent, llm, server

    @pytest.mark.asyncio
    async def test_full_workflow(self, full_agent_setup):
        """Test full agent workflow with LLM and tools."""
        agent, llm, _ = full_agent_setup

        task = AgentTask(
            task_id="sec-001",
            task_type="security_analysis",
            description="Analyze authentication code for vulnerabilities",
        )

        result = await agent.run(task)

        assert result.success
        assert "analysis" in result.data
        llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_tasks(self, full_agent_setup):
        """Test agent handling multiple tasks."""
        agent, _, _ = full_agent_setup

        tasks = [
            AgentTask(task_id=f"task-{i}", task_type="test", description=f"Test {i}")
            for i in range(3)
        ]

        results = []
        for task in tasks:
            result = await agent.run(task)
            results.append(result)

        assert all(r.success for r in results)
        assert agent._tasks_executed == 3


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_mixin_without_mcp_server(self):
        """Test mixin works without MCP server."""

        class TestMixin(MCPToolMixin):
            def __init__(self):
                self._init_mcp_tools()

        mixin = TestMixin()
        tools = mixin.get_available_tools()

        assert tools == {}

    @pytest.mark.asyncio
    async def test_agent_with_empty_task_description(self):
        """Test agent handles empty task description."""

        class TestAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"description": task.description},
                )

        agent = TestAgent()
        task = AgentTask(
            task_id="empty-001",
            task_type="test",
            description="",
        )

        result = await agent.run(task)
        assert result.success

    def test_agent_metrics_division_by_zero(self):
        """Test metrics handle zero executions."""

        class TestAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                return AgentResult(task_id=task.task_id, success=True)

        agent = TestAgent()
        metrics = agent.get_metrics()

        assert metrics["success_rate"] == 0.0
        assert metrics["avg_execution_time_ms"] == 0.0
