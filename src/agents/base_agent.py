"""
Project Aura - Base Agent with MCP Tool Support

Base class for all Aura agents with standardized MCP tool integration.

ADR-029 Phase 1.4 Implementation
Issue #19: SQSConsumerMixin for microservices messaging

Usage:
    >>> from src.agents.base_agent import BaseAgent, MCPToolMixin, SQSConsumerMixin
    >>> class MyAgent(MCPToolMixin, BaseAgent):
    ...     async def execute(self, task):
    ...         results = await self.invoke_tool("semantic_search", {"query": task.query})
    ...         return self.process_results(results)

    >>> # For queue-based agent workers:
    >>> class CoderWorker(SQSConsumerMixin, CoderAgent):
    ...     async def run(self):
    ...         tasks = await self.poll_tasks()
    ...         for task, receipt in tasks:
    ...             result = await self.execute(task)
    ...             await self.ack_task(receipt)
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService
    from src.services.mcp_gateway_client import MCPGatewayClient
    from src.services.mcp_tool_server import MCPToolServer


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AgentTask:
    """Task for agent execution."""

    task_id: str
    task_type: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    timeout_seconds: int = 300


@dataclass
class AgentResult:
    """Result from agent execution."""

    task_id: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time_ms: float = 0.0
    tools_invoked: list[str] = field(default_factory=list)
    tokens_used: int = 0
    cost_usd: float = 0.0


@dataclass
class HITLApprovalRequest:
    """Request for human-in-the-loop approval."""

    tool_name: str
    params: dict[str, Any]
    reason: str
    requested_at: float = field(default_factory=time.time)


@dataclass
class HITLApprovalResponse:
    """Response from HITL approval."""

    approved: bool
    reason: str | None = None
    approver: str | None = None
    approved_at: float | None = None


# =============================================================================
# Exceptions
# =============================================================================


class ToolNotFoundError(Exception):
    """Raised when a requested tool is not available."""


class HITLRejectedError(Exception):
    """Raised when HITL approval is rejected."""


class ToolInvocationError(Exception):
    """Raised when tool invocation fails."""


# =============================================================================
# MCP Tool Mixin
# =============================================================================


class MCPToolMixin:
    """
    Mixin that provides MCP tool invocation capabilities to agents.

    This mixin adds standardized tool discovery and invocation methods
    that work with both internal MCP tools (Neptune, OpenSearch) and
    external MCP tools via AgentCore Gateway.

    Usage:
        class MyAgent(MCPToolMixin):
            def __init__(self, llm_client, mcp_server=None, mcp_client=None):
                self.llm = llm_client
                self._init_mcp_tools(mcp_server, mcp_client)

            async def analyze(self, query):
                results = await self.invoke_tool("semantic_search", {"query": query})
                return results
    """

    _mcp_server: "MCPToolServer | None" = None
    _mcp_client: "MCPGatewayClient | None" = None
    _available_tools: dict[str, dict[str, Any]]
    _tool_invocation_count: int = 0
    _pending_approvals: dict[str, HITLApprovalRequest]

    def _init_mcp_tools(
        self,
        mcp_server: "MCPToolServer | None" = None,
        mcp_client: "MCPGatewayClient | None" = None,
    ) -> None:
        """
        Initialize MCP tool support.

        Args:
            mcp_server: Internal MCP tool server (Neptune, OpenSearch, etc.)
            mcp_client: External MCP gateway client (Slack, Jira, etc.)
        """
        self._mcp_server = mcp_server
        self._mcp_client = mcp_client
        self._available_tools = {}
        self._tool_invocation_count = 0
        self._pending_approvals = {}

        # Discover available tools
        self._discover_tools()

    def _discover_tools(self) -> None:
        """Discover all available MCP tools from server and client."""
        self._available_tools = {}

        # Discover internal tools from MCP server
        if self._mcp_server:
            for tool in self._mcp_server.list_tools():
                self._available_tools[tool.name] = {
                    "source": "internal",
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                    "requires_approval": tool.requires_approval,
                    "category": tool.category.value,
                }

        # Note: External tools from MCP client would be discovered asynchronously
        # in production via await self._mcp_client.list_tools()

        logger.info(f"Discovered {len(self._available_tools)} MCP tools")

    def get_available_tools(self) -> dict[str, dict[str, Any]]:
        """Get all available tools."""
        return self._available_tools.copy()

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available."""
        return tool_name in self._available_tools

    async def invoke_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        skip_approval: bool = False,
    ) -> dict[str, Any]:
        """
        Invoke an MCP tool with automatic validation and auditing.

        Args:
            tool_name: Name of the tool to invoke
            params: Tool parameters
            skip_approval: Skip HITL approval for sensitive tools

        Returns:
            Tool result data

        Raises:
            ToolNotFoundError: If tool is not available
            HITLRejectedError: If HITL approval is rejected
            ToolInvocationError: If tool execution fails
        """
        # Validate tool exists
        if tool_name not in self._available_tools:
            raise ToolNotFoundError(f"Tool '{tool_name}' not available")

        tool_info = self._available_tools[tool_name]

        # Check HITL requirement
        if tool_info.get("requires_approval") and not skip_approval:
            approval = await self._request_hitl_approval(tool_name, params)
            if not approval.approved:
                raise HITLRejectedError(approval.reason or "Approval rejected")

        # Invoke based on source
        self._tool_invocation_count += 1

        if tool_info["source"] == "internal" and self._mcp_server:
            result = await self._mcp_server.invoke_tool(
                tool_name, params, skip_approval=True
            )

            if not result.success:
                raise ToolInvocationError(result.error or "Tool invocation failed")

            # Audit log
            logger.info(
                f"Tool invocation: {tool_name}",
                extra={
                    "tool": tool_name,
                    "params_keys": list(params.keys()),
                    "success": result.success,
                    "latency_ms": result.latency_ms,
                    "agent": getattr(self, "__class__", type(self)).__name__,
                },
            )

            return result.data

        if tool_info["source"] == "external" and self._mcp_client:
            mcp_result = await self._mcp_client.invoke_tool(tool_name, params)

            if not mcp_result.is_success:
                raise ToolInvocationError(
                    mcp_result.error_message or "Tool invocation failed"
                )

            return mcp_result.data

        raise ToolInvocationError(f"No handler available for tool '{tool_name}'")

    async def invoke_tools_parallel(
        self,
        invocations: list[tuple[str, dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """
        Invoke multiple tools in parallel.

        Args:
            invocations: List of (tool_name, params) tuples

        Returns:
            List of results in same order as invocations
        """
        tasks = [
            self.invoke_tool(tool_name, params) for tool_name, params in invocations
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return cast(list[dict[str, Any]], results)

    async def _request_hitl_approval(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> HITLApprovalResponse:
        """
        Request human-in-the-loop approval for sensitive operations.

        In production, this would integrate with the HITL approval workflow.
        For now, it auto-approves with logging.
        """
        request = HITLApprovalRequest(
            tool_name=tool_name,
            params=params,
            reason=f"Agent requesting to invoke {tool_name}",
        )

        request_id = f"{tool_name}_{int(time.time())}"
        self._pending_approvals[request_id] = request

        logger.warning(
            f"HITL approval requested for {tool_name} - auto-approving in dev mode"
        )

        # In production, this would wait for approval via HITL dashboard
        # For development, auto-approve after logging
        return HITLApprovalResponse(
            approved=True,
            reason="Auto-approved in development mode",
            approver="system",
            approved_at=time.time(),
        )

    def get_tool_metrics(self) -> dict[str, Any]:
        """Get tool invocation metrics."""
        return {
            "total_invocations": self._tool_invocation_count,
            "available_tools": len(self._available_tools),
            "pending_approvals": len(self._pending_approvals),
        }


# =============================================================================
# SQS Consumer Mixin (Issue #19 - Microservices Messaging)
# =============================================================================


class SQSConsumerMixin:
    """Mixin for agents to consume tasks from SQS queues.

    Provides queue polling, message acknowledgment, and automatic
    conversion between SQS messages and AgentTask objects.

    Issue: #19 - Microservices messaging with SQS/EventBridge

    Usage:
        >>> class CoderAgentWorker(SQSConsumerMixin, CoderAgent):
        ...     def __init__(self, queue_url: str):
        ...         super().__init__()
        ...         self.init_consumer(queue_url)
        ...
        ...     async def run(self):
        ...         while True:
        ...             tasks = await self.poll_tasks()
        ...             for task, receipt in tasks:
        ...                 try:
        ...                     result = await self.execute(task)
        ...                     await self.ack_task(receipt)
        ...                 except Exception:
        ...                     await self.nack_task(receipt)
    """

    _queue_url: str = ""
    _sqs_client: Any = None
    _visibility_timeout: int = 300
    _wait_time_seconds: int = 20

    def init_consumer(
        self,
        queue_url: str,
        visibility_timeout: int = 300,
        wait_time_seconds: int = 20,
    ) -> None:
        """Initialize the SQS consumer.

        Args:
            queue_url: SQS queue URL to poll
            visibility_timeout: Seconds before unacknowledged message reappears
            wait_time_seconds: Long polling wait time (max 20)
        """
        import boto3
        from botocore.config import Config

        self._queue_url = queue_url
        self._visibility_timeout = visibility_timeout
        self._wait_time_seconds = min(wait_time_seconds, 20)

        boto_config = Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
        )
        self._sqs_client = boto3.client("sqs", config=boto_config)
        logger.info(f"SQS consumer initialized for queue: {queue_url}")

    async def poll_tasks(
        self,
        max_messages: int = 1,
    ) -> list[tuple[AgentTask, str]]:
        """Poll for tasks from the SQS queue.

        Args:
            max_messages: Maximum messages to receive (1-10)

        Returns:
            List of (AgentTask, receipt_handle) tuples
        """
        if not self._sqs_client:
            raise RuntimeError("Consumer not initialized. Call init_consumer() first.")

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._sqs_client.receive_message(
                    QueueUrl=self._queue_url,
                    MaxNumberOfMessages=min(max_messages, 10),
                    WaitTimeSeconds=self._wait_time_seconds,
                    VisibilityTimeout=self._visibility_timeout,
                    MessageAttributeNames=["All"],
                ),
            )

            messages = response.get("Messages", [])
            result = []

            for msg in messages:
                try:
                    task = self._parse_sqs_to_task(msg)
                    result.append((task, msg["ReceiptHandle"]))
                except Exception as e:
                    logger.error(f"Failed to parse SQS message: {e}")
                    continue

            return result

        except Exception as e:
            logger.error(f"Failed to poll tasks: {e}")
            return []

    def _parse_sqs_to_task(self, sqs_message: dict[str, Any]) -> AgentTask:
        """Convert SQS message to AgentTask.

        Args:
            sqs_message: Raw SQS message dict

        Returns:
            AgentTask instance
        """
        import json

        body = json.loads(sqs_message.get("Body", "{}"))

        return AgentTask(
            task_id=body.get("task_id", ""),
            task_type=body.get("message_type", "task"),
            description=body.get("task_description", ""),
            parameters=body.get("payload", {}),
            context=body.get("context", {}),
            priority=body.get("priority", 0),
            timeout_seconds=body.get("timeout_seconds", 300),
        )

    async def ack_task(self, receipt_handle: str) -> None:
        """Acknowledge (delete) a successfully processed message.

        Args:
            receipt_handle: Receipt handle from poll_tasks()
        """
        if not self._sqs_client:
            raise RuntimeError("Consumer not initialized.")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._sqs_client.delete_message(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=receipt_handle,
                ),
            )
            logger.debug("Task acknowledged")
        except Exception as e:
            logger.error(f"Failed to ack task: {e}")
            raise

    async def nack_task(
        self,
        receipt_handle: str,
        visibility_timeout: int = 0,
    ) -> None:
        """Negative acknowledge - make message visible again for retry.

        Args:
            receipt_handle: Receipt handle from poll_tasks()
            visibility_timeout: Seconds before message reappears (0 = immediate)
        """
        if not self._sqs_client:
            raise RuntimeError("Consumer not initialized.")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._sqs_client.change_message_visibility(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=visibility_timeout,
                ),
            )
            logger.debug(f"Task nacked, visibility_timeout={visibility_timeout}")
        except Exception as e:
            logger.error(f"Failed to nack task: {e}")
            raise

    async def extend_visibility(
        self,
        receipt_handle: str,
        additional_seconds: int = 300,
    ) -> None:
        """Extend visibility timeout for long-running tasks.

        Args:
            receipt_handle: Receipt handle from poll_tasks()
            additional_seconds: Additional seconds of visibility
        """
        if not self._sqs_client:
            raise RuntimeError("Consumer not initialized.")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._sqs_client.change_message_visibility(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=additional_seconds,
                ),
            )
            logger.debug(f"Extended visibility by {additional_seconds}s")
        except Exception as e:
            logger.error(f"Failed to extend visibility: {e}")
            raise


# =============================================================================
# Base Agent
# =============================================================================


class BaseAgent(ABC):
    """
    Base class for all Aura agents.

    Provides common functionality for:
    - LLM integration
    - Task execution
    - Result handling
    - Metrics tracking

    Subclasses should implement the execute() method.

    Example:
        >>> class SecurityAgent(MCPToolMixin, BaseAgent):
        ...     async def execute(self, task: AgentTask) -> AgentResult:
        ...         # Perform security analysis
        ...         results = await self.invoke_tool("semantic_search", {"query": task.description})
        ...         return AgentResult(task_id=task.task_id, success=True, data=results)
    """

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        agent_name: str | None = None,
    ):
        """
        Initialize base agent.

        Args:
            llm_client: Bedrock LLM service for inference
            agent_name: Name of this agent instance
        """
        self.llm = llm_client
        self.agent_name = agent_name or self.__class__.__name__

        # Metrics
        self._tasks_executed = 0
        self._tasks_succeeded = 0
        self._tasks_failed = 0
        self._total_execution_time_ms = 0.0

        logger.info(f"BaseAgent initialized: {self.agent_name}")

    @abstractmethod
    async def execute(self, task: AgentTask) -> AgentResult:
        """
        Execute an agent task.

        Args:
            task: Task to execute

        Returns:
            AgentResult with execution outcome
        """

    async def run(self, task: AgentTask) -> AgentResult:
        """
        Run a task with metrics tracking.

        Args:
            task: Task to execute

        Returns:
            AgentResult with execution outcome
        """
        start_time = time.perf_counter()
        self._tasks_executed += 1

        try:
            result = await asyncio.wait_for(
                self.execute(task),
                timeout=task.timeout_seconds,
            )

            execution_time = (time.perf_counter() - start_time) * 1000
            result.execution_time_ms = execution_time
            self._total_execution_time_ms += execution_time

            if result.success:
                self._tasks_succeeded += 1
            else:
                self._tasks_failed += 1

            return result

        except asyncio.TimeoutError:
            self._tasks_failed += 1
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=f"Task timed out after {task.timeout_seconds}s",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        except Exception as e:
            self._tasks_failed += 1
            logger.error(f"Task execution failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

    def get_metrics(self) -> dict[str, Any]:
        """Get agent metrics."""
        return {
            "agent_name": self.agent_name,
            "tasks_executed": self._tasks_executed,
            "tasks_succeeded": self._tasks_succeeded,
            "tasks_failed": self._tasks_failed,
            "success_rate": (
                self._tasks_succeeded / self._tasks_executed
                if self._tasks_executed > 0
                else 0.0
            ),
            "avg_execution_time_ms": (
                self._total_execution_time_ms / self._tasks_executed
                if self._tasks_executed > 0
                else 0.0
            ),
        }


# =============================================================================
# MCP-Enabled Base Agent
# =============================================================================


class MCPEnabledAgent(MCPToolMixin, BaseAgent):
    """
    Base agent with full MCP tool support.

    Combines BaseAgent functionality with MCPToolMixin for agents
    that need to invoke MCP tools.

    Example:
        >>> class MySecurityAgent(MCPEnabledAgent):
        ...     async def execute(self, task: AgentTask) -> AgentResult:
        ...         # Search for related code
        ...         search_results = await self.invoke_tool(
        ...             "semantic_search",
        ...             {"query": task.description, "k": 10}
        ...         )
        ...         # Process results with LLM
        ...         analysis = await self.llm.generate(
        ...             f"Analyze these results: {search_results}",
        ...             agent=self.agent_name
        ...         )
        ...         return AgentResult(task_id=task.task_id, success=True, data={"analysis": analysis})
    """

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        mcp_server: "MCPToolServer | None" = None,
        mcp_client: "MCPGatewayClient | None" = None,
        agent_name: str | None = None,
    ):
        """
        Initialize MCP-enabled agent.

        Args:
            llm_client: Bedrock LLM service
            mcp_server: Internal MCP tool server
            mcp_client: External MCP gateway client
            agent_name: Agent name
        """
        super().__init__(llm_client=llm_client, agent_name=agent_name)
        self._init_mcp_tools(mcp_server=mcp_server, mcp_client=mcp_client)

    def get_metrics(self) -> dict[str, Any]:
        """Get combined agent and tool metrics."""
        metrics = super().get_metrics()
        metrics["tools"] = self.get_tool_metrics()
        return metrics


# =============================================================================
# Demo
# =============================================================================


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def demo():
        print("Base Agent Demo")
        print("=" * 60)

        # Create a simple test agent
        class TestAgent(MCPEnabledAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                # Simulate tool invocation
                tools = self.get_available_tools()
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={
                        "available_tools": list(tools.keys()),
                        "message": f"Executed task: {task.description}",
                    },
                )

        # Create agent without MCP server (mock mode)
        agent = TestAgent(agent_name="TestAgent")

        # Create and run task
        task = AgentTask(
            task_id="test_001",
            task_type="test",
            description="Test task execution",
        )

        result = await agent.run(task)

        print(f"\nTask: {task.description}")
        print(f"Success: {result.success}")
        print(f"Data: {result.data}")
        print(f"Execution time: {result.execution_time_ms:.1f}ms")

        # Show metrics
        print("\n--- Agent Metrics ---")
        metrics = agent.get_metrics()
        for key, value in metrics.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"{key}: {value}")

    asyncio.run(demo())

    print("\n" + "=" * 60)
    print("Demo complete!")
