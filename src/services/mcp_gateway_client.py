"""
Project Aura - MCP Gateway Client

Implements ADR-023 Phase 2: MCP Adapter Layer

This module provides the client for Amazon Bedrock AgentCore Gateway,
enabling MCP (Model Context Protocol) compatible tool invocations for
ENTERPRISE mode deployments.

IMPORTANT: This client is ONLY available in ENTERPRISE mode.
Defense/GovCloud deployments use native Aura agents without external dependencies.

Usage:
    >>> from src.services.mcp_gateway_client import MCPGatewayClient
    >>> client = MCPGatewayClient()
    >>> result = await client.invoke_tool("slack", {"channel": "#alerts", "message": "Hello"})
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.config import (
    CustomerMCPBudget,
    IntegrationConfig,
    get_integration_config,
    require_enterprise_mode,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


class MCPToolStatus(Enum):
    """Status of an MCP tool."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    AUTH_REQUIRED = "auth_required"
    DEPRECATED = "deprecated"


class MCPInvocationStatus(Enum):
    """Status of an MCP tool invocation."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    BUDGET_EXCEEDED = "budget_exceeded"
    AUTH_ERROR = "auth_error"
    TOOL_NOT_FOUND = "tool_not_found"


@dataclass
class MCPTool:
    """Represents an MCP-compatible tool available via AgentCore Gateway."""

    tool_id: str
    name: str
    description: str
    version: str = "1.0"
    status: MCPToolStatus = MCPToolStatus.AVAILABLE
    category: str = "general"
    provider: str = "unknown"

    # Input/output schema (JSON Schema format)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)

    # Rate limiting
    rate_limit_per_minute: int = 60
    current_minute_invocations: int = 0
    last_rate_reset: float = field(default_factory=time.time)

    # Authentication
    requires_oauth: bool = False
    oauth_scopes: list[str] = field(default_factory=list)

    def is_rate_limited(self) -> bool:
        """Check if tool is currently rate limited."""
        current_time = time.time()
        if current_time - self.last_rate_reset >= 60:
            self.current_minute_invocations = 0
            self.last_rate_reset = current_time
        return self.current_minute_invocations >= self.rate_limit_per_minute

    def record_invocation(self) -> None:
        """Record a tool invocation for rate limiting."""
        current_time = time.time()
        if current_time - self.last_rate_reset >= 60:
            self.current_minute_invocations = 0
            self.last_rate_reset = current_time
        self.current_minute_invocations += 1


@dataclass
class MCPInvocationResult:
    """Result of an MCP tool invocation."""

    tool_id: str
    status: MCPInvocationStatus
    data: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    request_id: str | None = None
    timestamp: float = field(default_factory=time.time)

    @property
    def is_success(self) -> bool:
        """Check if invocation was successful."""
        return self.status == MCPInvocationStatus.SUCCESS


@dataclass
class MCPSearchResult:
    """Result of an MCP tool search."""

    query: str
    tools: list[MCPTool]
    total_count: int
    latency_ms: float = 0.0
    cost_usd: float = 0.0


# =============================================================================
# MCP Gateway Client
# =============================================================================


class MCPGatewayClient:
    """
    Client for Amazon Bedrock AgentCore Gateway MCP protocol.

    This client handles:
    - Tool discovery and semantic search
    - Tool invocation with retry logic
    - Cost tracking and budget enforcement
    - Rate limiting
    - OAuth token management (delegated to AgentCore Identity)

    SECURITY: Only available in ENTERPRISE mode. Defense deployments
    use native Aura agents without external network calls.
    """

    def __init__(
        self,
        config: IntegrationConfig | None = None,
        customer_budget: CustomerMCPBudget | None = None,
    ):
        """
        Initialize MCP Gateway Client.

        Args:
            config: Integration configuration. If None, loads from environment.
            customer_budget: Customer-specific budget. If None, uses default.
        """
        self._config = config or get_integration_config()
        self._customer_budget = customer_budget or self._config.default_customer_budget

        # Validate we're in enterprise mode
        if self._config.is_defense_mode:
            raise RuntimeError(
                "MCPGatewayClient cannot be instantiated in DEFENSE mode. "
                "Use native Aura agents for air-gapped deployments."
            )

        # Tool cache (refreshed periodically)
        self._tool_cache: dict[str, MCPTool] = {}
        self._cache_expiry: float = 0.0
        self._cache_ttl_seconds: float = 300.0  # 5 minutes

        # Metrics
        self._total_invocations: int = 0
        self._total_errors: int = 0
        self._total_cost_usd: float = 0.0

        logger.info(
            f"MCPGatewayClient initialized: endpoint={self._config.gateway_endpoint}, "
            f"customer={self._customer_budget.customer_id}"
        )

    # -------------------------------------------------------------------------
    # Tool Discovery
    # -------------------------------------------------------------------------

    @require_enterprise_mode
    async def list_tools(self, category: str | None = None) -> list[MCPTool]:
        """
        List all available MCP tools.

        Args:
            category: Optional category filter (e.g., "notification", "ticketing")

        Returns:
            List of available MCPTool objects
        """
        await self._refresh_tool_cache_if_needed()

        tools = list(self._tool_cache.values())
        if category:
            tools = [t for t in tools if t.category == category]

        return tools

    @require_enterprise_mode
    async def search_tools(self, query: str, limit: int = 10) -> MCPSearchResult:
        """
        Semantic search for MCP tools.

        Uses AgentCore Gateway's semantic search to find tools matching
        the natural language query.

        Args:
            query: Natural language search query
            limit: Maximum number of results

        Returns:
            MCPSearchResult with matching tools
        """
        start_time = time.time()

        # Check budget for search operation
        if not self._customer_budget.record_invocation(is_search=True):
            logger.warning(f"Budget exceeded for search: {query}")
            return MCPSearchResult(
                query=query,
                tools=[],
                total_count=0,
                cost_usd=0.0,
            )

        # In production, this would call AgentCore Gateway API
        # For now, implement local semantic matching
        await self._refresh_tool_cache_if_needed()

        query_lower = query.lower()
        matching_tools = []

        for tool in self._tool_cache.values():
            score = self._calculate_relevance_score(query_lower, tool)
            if score > 0.3:  # Threshold for relevance
                matching_tools.append((score, tool))

        # Sort by relevance and limit
        matching_tools.sort(key=lambda x: x[0], reverse=True)
        result_tools = [t for _, t in matching_tools[:limit]]

        latency_ms = (time.time() - start_time) * 1000
        cost = self._customer_budget.SEARCH_TOOL_COST_PER_REQUEST

        self._total_cost_usd += cost

        return MCPSearchResult(
            query=query,
            tools=result_tools,
            total_count=len(result_tools),
            latency_ms=latency_ms,
            cost_usd=cost,
        )

    @require_enterprise_mode
    async def get_tool(self, tool_id: str) -> MCPTool | None:
        """
        Get a specific tool by ID.

        Args:
            tool_id: The tool identifier

        Returns:
            MCPTool if found, None otherwise
        """
        await self._refresh_tool_cache_if_needed()
        return self._tool_cache.get(tool_id)

    # -------------------------------------------------------------------------
    # Tool Invocation
    # -------------------------------------------------------------------------

    @require_enterprise_mode
    async def invoke_tool(
        self,
        tool_id: str,
        params: dict[str, Any],
        timeout_seconds: float | None = None,
        idempotency_key: str | None = None,
    ) -> MCPInvocationResult:
        """
        Invoke an MCP tool via AgentCore Gateway.

        Args:
            tool_id: The tool to invoke (e.g., "slack", "jira")
            params: Tool-specific parameters
            timeout_seconds: Override default timeout
            idempotency_key: For retry safety (auto-generated if None)

        Returns:
            MCPInvocationResult with status and data
        """
        start_time = time.time()
        timeout = timeout_seconds or self._config.mcp_timeout_seconds
        request_id = idempotency_key or self._generate_request_id(tool_id, params)

        self._total_invocations += 1

        # Check budget
        if not self._customer_budget.record_invocation(is_search=False):
            self._total_errors += 1
            return MCPInvocationResult(
                tool_id=tool_id,
                status=MCPInvocationStatus.BUDGET_EXCEEDED,
                error_message=f"Monthly budget exceeded: ${self._customer_budget.current_spend_usd:.2f} / ${self._customer_budget.monthly_limit_usd:.2f}",
                request_id=request_id,
            )

        # Get tool and validate
        tool = await self.get_tool(tool_id)
        if not tool:
            self._total_errors += 1
            return MCPInvocationResult(
                tool_id=tool_id,
                status=MCPInvocationStatus.TOOL_NOT_FOUND,
                error_message=f"Tool '{tool_id}' not found in registry",
                request_id=request_id,
            )

        # Check rate limiting
        if tool.is_rate_limited():
            self._total_errors += 1
            return MCPInvocationResult(
                tool_id=tool_id,
                status=MCPInvocationStatus.RATE_LIMITED,
                error_message=f"Tool '{tool_id}' rate limited: {tool.rate_limit_per_minute}/min",
                request_id=request_id,
            )

        # Check tool availability
        if tool.status != MCPToolStatus.AVAILABLE:
            self._total_errors += 1
            return MCPInvocationResult(
                tool_id=tool_id,
                status=MCPInvocationStatus.FAILED,
                error_message=f"Tool '{tool_id}' is {tool.status.value}",
                request_id=request_id,
            )

        # Invoke with retry logic
        result = await self._invoke_with_retry(
            tool=tool,
            params=params,
            timeout=timeout,
            request_id=request_id,
        )

        result.latency_ms = (time.time() - start_time) * 1000
        result.cost_usd = self._customer_budget.INVOKE_TOOL_COST_PER_REQUEST
        self._total_cost_usd += result.cost_usd

        # Record invocation for rate limiting
        tool.record_invocation()

        if not result.is_success:
            self._total_errors += 1

        logger.info(
            f"MCP invocation: tool={tool_id}, status={result.status.value}, "
            f"latency={result.latency_ms:.1f}ms, cost=${result.cost_usd:.6f}"
        )

        return result

    async def _invoke_with_retry(
        self,
        tool: MCPTool,
        params: dict[str, Any],
        timeout: float,
        request_id: str,
    ) -> MCPInvocationResult:
        """Invoke tool with retry logic."""
        last_error: str | None = None

        for attempt in range(self._config.mcp_max_retries):
            try:
                # In production, this calls AgentCore Gateway API
                # For now, delegate to tool-specific handler
                result = await self._execute_tool_invocation(
                    tool=tool,
                    params=params,
                    timeout=timeout,
                )

                return MCPInvocationResult(
                    tool_id=tool.tool_id,
                    status=MCPInvocationStatus.SUCCESS,
                    data=result,
                    request_id=request_id,
                )

            except asyncio.TimeoutError:
                last_error = f"Timeout after {timeout}s (attempt {attempt + 1})"
                logger.warning(f"MCP timeout: tool={tool.tool_id}, {last_error}")

            except MCPAuthError as e:
                # Don't retry auth errors
                return MCPInvocationResult(
                    tool_id=tool.tool_id,
                    status=MCPInvocationStatus.AUTH_ERROR,
                    error_message=str(e),
                    request_id=request_id,
                )

            except MCPInvocationError as e:
                last_error = str(e)
                logger.warning(
                    f"MCP error: tool={tool.tool_id}, attempt={attempt + 1}, error={e}"
                )

            # Exponential backoff between retries
            if attempt < self._config.mcp_max_retries - 1:
                await asyncio.sleep(2**attempt)

        # All retries exhausted
        return MCPInvocationResult(
            tool_id=tool.tool_id,
            status=MCPInvocationStatus.FAILED,
            error_message=last_error or "Unknown error after retries",
            request_id=request_id,
        )

    async def _execute_tool_invocation(
        self,
        tool: MCPTool,
        params: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        """
        Execute the actual tool invocation.

        In production, this sends the request to AgentCore Gateway.
        For development/testing, this returns mock responses.
        """
        # Production implementation would be:
        # async with aiohttp.ClientSession() as session:
        #     async with session.post(
        #         f"{self._config.gateway_endpoint}/tools/{tool.tool_id}/invoke",
        #         json={"params": params, "timeout": timeout},
        #         headers=self._get_auth_headers(),
        #         timeout=aiohttp.ClientTimeout(total=timeout),
        #     ) as response:
        #         response.raise_for_status()
        #         return await response.json()

        # Development mock - simulate network latency
        await asyncio.sleep(0.1)

        # Return mock response based on tool type
        mock_responses = {
            "slack": {
                "ok": True,
                "channel": params.get("channel", "#general"),
                "ts": "1234567890.123456",
                "message": {"text": params.get("message", "")},
            },
            "jira": {
                "id": "AURA-123",
                "key": "AURA-123",
                "self": "https://company.atlassian.net/rest/api/2/issue/AURA-123",
            },
            "pagerduty": {
                "incident": {
                    "id": "P1234567",
                    "status": "triggered",
                    "urgency": params.get("urgency", "high"),
                }
            },
            "github": {
                "id": 1,
                "number": 42,
                "html_url": "https://github.com/org/repo/pull/42",
                "state": "open",
            },
            "datadog": {
                "status": "ok",
                "metric": params.get("metric", "custom.metric"),
            },
        }

        return mock_responses.get(
            tool.tool_id, {"status": "ok", "tool": tool.tool_id, "params": params}
        )

    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------

    async def _refresh_tool_cache_if_needed(self) -> None:
        """Refresh tool cache if expired."""
        if time.time() < self._cache_expiry:
            return

        await self._load_tool_cache()

    async def _load_tool_cache(self) -> None:
        """Load available tools into cache."""
        # In production, this would fetch from AgentCore Gateway
        # For now, load from integration config
        self._tool_cache.clear()

        for tool_config in self._config.external_tools:
            if not tool_config.enabled:
                continue

            mcp_tool = MCPTool(
                tool_id=tool_config.tool_id,
                name=tool_config.tool_name,
                description=self._get_tool_description(tool_config.tool_id),
                category=tool_config.category.value,
                provider="agentcore",
                rate_limit_per_minute=tool_config.rate_limit_per_minute,
                requires_oauth=tool_config.requires_customer_auth,
                input_schema=self._get_tool_input_schema(tool_config.tool_id),
            )
            self._tool_cache[tool_config.tool_id] = mcp_tool

        self._cache_expiry = time.time() + self._cache_ttl_seconds

        logger.debug(f"Tool cache refreshed: {len(self._tool_cache)} tools loaded")

    def _get_tool_description(self, tool_id: str) -> str:
        """Get description for a tool."""
        descriptions = {
            "slack": "Send messages and notifications to Slack channels",
            "jira": "Create, update, and manage Jira issues and tickets",
            "pagerduty": "Create and manage PagerDuty incidents for alerting",
            "github": "Create pull requests, add reviews, and manage GitHub repositories",
            "datadog": "Submit metrics and create events in Datadog",
        }
        return descriptions.get(tool_id, f"MCP tool: {tool_id}")

    def _get_tool_input_schema(self, tool_id: str) -> dict[str, Any]:
        """Get JSON Schema for tool input parameters."""
        schemas = {
            "slack": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Slack channel"},
                    "message": {"type": "string", "description": "Message text"},
                    "thread_ts": {
                        "type": "string",
                        "description": "Thread timestamp for replies",
                    },
                },
                "required": ["channel", "message"],
            },
            "jira": {
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Jira project key"},
                    "summary": {"type": "string", "description": "Issue summary"},
                    "description": {
                        "type": "string",
                        "description": "Issue description",
                    },
                    "issue_type": {
                        "type": "string",
                        "enum": ["Bug", "Task", "Story"],
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["Critical", "High", "Medium", "Low"],
                    },
                },
                "required": ["project", "summary"],
            },
            "pagerduty": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Incident title"},
                    "service_id": {
                        "type": "string",
                        "description": "PagerDuty service",
                    },
                    "urgency": {"type": "string", "enum": ["high", "low"]},
                    "body": {"type": "string", "description": "Incident details"},
                },
                "required": ["title", "service_id"],
            },
            "github": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner"},
                    "repo": {"type": "string", "description": "Repository name"},
                    "title": {"type": "string", "description": "PR title"},
                    "body": {"type": "string", "description": "PR description"},
                    "head": {"type": "string", "description": "Source branch"},
                    "base": {"type": "string", "description": "Target branch"},
                },
                "required": ["owner", "repo", "title", "head", "base"],
            },
            "datadog": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "description": "Metric name"},
                    "value": {"type": "number", "description": "Metric value"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Metric tags",
                    },
                },
                "required": ["metric", "value"],
            },
        }
        return schemas.get(tool_id, {"type": "object"})

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def _calculate_relevance_score(self, query: str, tool: MCPTool) -> float:
        """Calculate relevance score for semantic search."""
        score = 0.0

        # Check tool name
        if query in tool.name.lower():
            score += 0.5
        elif any(word in tool.name.lower() for word in query.split()):
            score += 0.3

        # Check tool description
        if query in tool.description.lower():
            score += 0.3
        elif any(word in tool.description.lower() for word in query.split()):
            score += 0.2

        # Check category
        if query in tool.category.lower():
            score += 0.2

        return min(score, 1.0)

    def _generate_request_id(self, tool_id: str, params: dict) -> str:
        """Generate idempotency key for request."""
        content = f"{tool_id}:{json.dumps(params, sort_keys=True)}:{time.time()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------

    def get_metrics(self) -> dict[str, Any]:
        """Get client metrics for monitoring."""
        return {
            "total_invocations": self._total_invocations,
            "total_errors": self._total_errors,
            "error_rate": (
                self._total_errors / self._total_invocations
                if self._total_invocations > 0
                else 0.0
            ),
            "total_cost_usd": self._total_cost_usd,
            "budget_remaining_usd": self._customer_budget.remaining_budget_usd,
            "budget_usage_pct": self._customer_budget.usage_percentage,
            "cached_tools": len(self._tool_cache),
        }


# =============================================================================
# Exceptions
# =============================================================================


class MCPError(Exception):
    """Base exception for MCP operations."""


class MCPAuthError(MCPError):
    """Authentication/authorization error."""


class MCPInvocationError(MCPError):
    """Tool invocation error."""


class MCPRateLimitError(MCPError):
    """Rate limit exceeded."""
