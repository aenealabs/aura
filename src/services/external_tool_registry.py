"""
Project Aura - External Tool Registry

Implements ADR-023 Phase 2: MCP Adapter Layer

This module provides a unified registry for both:
1. External tools (Slack, Jira, etc.) available via AgentCore Gateway
2. Aura's native agents exposed as MCP-compatible tools

The registry enables:
- Tool discovery and semantic search
- Capability-based tool selection
- Unified invocation interface
- Usage tracking and cost management

IMPORTANT: Only available in ENTERPRISE mode. DEFENSE mode uses native agents only.

Usage:
    >>> from src.services.external_tool_registry import ExternalToolRegistry
    >>> registry = ExternalToolRegistry()
    >>> tools = await registry.search("send notification")
    >>> result = await registry.invoke("slack", {"channel": "#alerts", "message": "Hello"})
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

from src.config import get_integration_config, require_enterprise_mode
from src.services.mcp_gateway_client import (
    MCPGatewayClient,
    MCPInvocationResult,
    MCPTool,
)
from src.services.mcp_tool_adapters import (
    AdapterInvocationResult,
    AuraToolAdapter,
    AuraToolDefinition,
    get_aura_tools,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class ToolProvider(Enum):
    """Source of tool availability."""

    AURA_NATIVE = "aura"  # Built-in Aura agents
    AGENTCORE = "agentcore"  # External tools via AgentCore Gateway
    CUSTOM = "custom"  # Customer-defined tools


class ToolCapabilityType(Enum):
    """High-level capability categories for tool selection."""

    NOTIFICATION = "notification"  # Send messages, alerts
    TICKETING = "ticketing"  # Create/manage tickets
    SECURITY = "security"  # Vulnerability scanning, threat detection
    CODE_ANALYSIS = "code_analysis"  # Review, architecture analysis
    DOCUMENTATION = "documentation"  # Generate/update docs
    CI_CD = "ci_cd"  # Build, deploy, release
    MONITORING = "monitoring"  # Metrics, observability


@dataclass
class UnifiedToolInfo:
    """
    Unified representation of a tool from any provider.

    Normalizes Aura agents and external tools into a common format.
    """

    tool_id: str
    name: str
    description: str
    provider: ToolProvider
    capabilities: list[ToolCapabilityType]
    enabled: bool = True

    # Schema
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)

    # Constraints
    requires_auth: bool = False
    requires_hitl: bool = False
    rate_limit_per_minute: int = 60

    # Cost
    estimated_cost_usd: float = 0.0

    # Metadata
    tags: list[str] = field(default_factory=list)
    version: str = "1.0"


@dataclass
class RegistrySearchResult:
    """Result from searching the tool registry."""

    query: str
    tools: list[UnifiedToolInfo]
    total_count: int
    latency_ms: float = 0.0
    sources: list[ToolProvider] = field(default_factory=list)


@dataclass
class RegistryInvocationResult:
    """Result from invoking a tool via the registry."""

    tool_id: str
    provider: ToolProvider
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    latency_ms: float = 0.0
    cost_usd: float = 0.0


# =============================================================================
# External Tool Registry
# =============================================================================


class ExternalToolRegistry:
    """
    Unified registry for all tools available to Aura platform.

    Combines:
    - Aura's 16 native agents (security, code review, etc.)
    - External tools via AgentCore Gateway (Slack, Jira, etc.)
    - Customer-defined custom tools

    Provides:
    - Semantic search across all tools
    - Capability-based tool selection
    - Unified invocation interface
    - Usage tracking
    """

    def __init__(
        self,
        mcp_client: MCPGatewayClient | None = None,
        aura_adapter: AuraToolAdapter | None = None,
    ):
        """
        Initialize the tool registry.

        Args:
            mcp_client: Client for AgentCore Gateway. Created if not provided.
            aura_adapter: Adapter for Aura tools. Created if not provided.
        """
        self._config = get_integration_config()

        # Only initialize MCP components in ENTERPRISE mode
        # Type annotations allow None for DEFENSE mode compatibility
        self._mcp_client: MCPGatewayClient | None
        self._aura_adapter: AuraToolAdapter | None

        if self._config.is_enterprise_mode:
            self._mcp_client = mcp_client or MCPGatewayClient()
            self._aura_adapter = aura_adapter or AuraToolAdapter()
        else:
            self._mcp_client = None
            self._aura_adapter = None

        # Tool cache
        self._unified_tools: dict[str, UnifiedToolInfo] = {}
        self._cache_loaded = False

        # Usage tracking
        self._invocation_counts: dict[str, int] = {}
        self._total_cost_usd: float = 0.0

        logger.info(
            f"ExternalToolRegistry initialized: mode={self._config.mode.value}, "
            f"mcp_enabled={self._mcp_client is not None}"
        )

    # -------------------------------------------------------------------------
    # Tool Discovery
    # -------------------------------------------------------------------------

    @require_enterprise_mode
    async def list_all_tools(
        self,
        provider: ToolProvider | None = None,
        capability: ToolCapabilityType | None = None,
        enabled_only: bool = True,
    ) -> list[UnifiedToolInfo]:
        """
        List all tools in the registry.

        Args:
            provider: Filter by provider (AURA_NATIVE, AGENTCORE, CUSTOM)
            capability: Filter by capability type
            enabled_only: Only return enabled tools

        Returns:
            List of UnifiedToolInfo objects
        """
        await self._ensure_cache_loaded()

        tools = list(self._unified_tools.values())

        if provider:
            tools = [t for t in tools if t.provider == provider]

        if capability:
            tools = [t for t in tools if capability in t.capabilities]

        if enabled_only:
            tools = [t for t in tools if t.enabled]

        return tools

    @require_enterprise_mode
    async def search(
        self,
        query: str,
        limit: int = 10,
        providers: list[ToolProvider] | None = None,
    ) -> RegistrySearchResult:
        """
        Semantic search across all tools.

        Args:
            query: Natural language search query
            limit: Maximum results
            providers: Optional filter by providers

        Returns:
            RegistrySearchResult with matching tools
        """
        start_time = time.time()
        await self._ensure_cache_loaded()

        # Search Aura tools
        aura_matches = self._search_aura_tools(query)

        # Search external tools via MCP
        external_matches: list[UnifiedToolInfo] = []
        if self._mcp_client is not None:
            mcp_results = await self._mcp_client.search_tools(query, limit=limit)
            external_matches = [self._mcp_tool_to_unified(t) for t in mcp_results.tools]

        # Combine and filter by provider
        all_matches = aura_matches + external_matches
        if providers:
            all_matches = [t for t in all_matches if t.provider in providers]

        # Sort by relevance and limit
        all_matches = self._sort_by_relevance(query, all_matches)[:limit]

        latency_ms = (time.time() - start_time) * 1000

        return RegistrySearchResult(
            query=query,
            tools=all_matches,
            total_count=len(all_matches),
            latency_ms=latency_ms,
            sources=[ToolProvider.AURA_NATIVE, ToolProvider.AGENTCORE],
        )

    @require_enterprise_mode
    async def get_tool(self, tool_id: str) -> UnifiedToolInfo | None:
        """Get a specific tool by ID."""
        await self._ensure_cache_loaded()
        return self._unified_tools.get(tool_id)

    @require_enterprise_mode
    async def get_tools_by_capability(
        self, capability: ToolCapabilityType
    ) -> list[UnifiedToolInfo]:
        """Get all tools with a specific capability."""
        await self._ensure_cache_loaded()
        return [
            t
            for t in self._unified_tools.values()
            if capability in t.capabilities and t.enabled
        ]

    # -------------------------------------------------------------------------
    # Tool Invocation
    # -------------------------------------------------------------------------

    @require_enterprise_mode
    async def invoke(
        self,
        tool_id: str,
        params: dict[str, Any],
        timeout_seconds: float | None = None,
    ) -> RegistryInvocationResult:
        """
        Invoke a tool by ID.

        Routes to appropriate handler based on tool provider.

        Args:
            tool_id: Tool to invoke
            params: Tool-specific parameters
            timeout_seconds: Optional timeout override

        Returns:
            RegistryInvocationResult with invocation outcome
        """
        start_time = time.time()
        await self._ensure_cache_loaded()

        tool = self._unified_tools.get(tool_id)
        if not tool:
            return RegistryInvocationResult(
                tool_id=tool_id,
                provider=ToolProvider.CUSTOM,
                success=False,
                error=f"Tool '{tool_id}' not found in registry",
            )

        if not tool.enabled:
            return RegistryInvocationResult(
                tool_id=tool_id,
                provider=tool.provider,
                success=False,
                error=f"Tool '{tool_id}' is disabled",
            )

        # Track invocation
        self._invocation_counts[tool_id] = self._invocation_counts.get(tool_id, 0) + 1

        # Route to appropriate handler
        if tool.provider == ToolProvider.AURA_NATIVE:
            result = await self._invoke_aura_tool(tool_id, params)
        elif tool.provider == ToolProvider.AGENTCORE:
            result = await self._invoke_external_tool(tool_id, params, timeout_seconds)
        else:
            result = RegistryInvocationResult(
                tool_id=tool_id,
                provider=tool.provider,
                success=False,
                error=f"Unknown provider: {tool.provider}",
            )

        result.latency_ms = (time.time() - start_time) * 1000
        self._total_cost_usd += result.cost_usd

        logger.info(
            f"Registry invocation: tool={tool_id}, provider={tool.provider.value}, "
            f"success={result.success}, latency={result.latency_ms:.1f}ms"
        )

        return result

    async def _invoke_aura_tool(
        self, tool_id: str, params: dict[str, Any]
    ) -> RegistryInvocationResult:
        """Invoke an Aura native tool."""
        if self._aura_adapter is None:
            return RegistryInvocationResult(
                tool_id=tool_id,
                provider=ToolProvider.AURA_NATIVE,
                success=False,
                error="Aura adapter not available (ENTERPRISE mode required)",
            )

        adapter_result: AdapterInvocationResult = await self._aura_adapter.invoke(
            tool_id, params
        )

        return RegistryInvocationResult(
            tool_id=tool_id,
            provider=ToolProvider.AURA_NATIVE,
            success=adapter_result.success,
            data=adapter_result.data,
            error=adapter_result.error,
            cost_usd=0.0,  # Aura tools don't have MCP cost
        )

    async def _invoke_external_tool(
        self,
        tool_id: str,
        params: dict[str, Any],
        timeout_seconds: float | None,
    ) -> RegistryInvocationResult:
        """Invoke an external tool via MCP Gateway."""
        if self._mcp_client is None:
            return RegistryInvocationResult(
                tool_id=tool_id,
                provider=ToolProvider.AGENTCORE,
                success=False,
                error="MCP client not available (ENTERPRISE mode required)",
            )

        mcp_result: MCPInvocationResult = await self._mcp_client.invoke_tool(
            tool_id, params, timeout_seconds=timeout_seconds
        )

        return RegistryInvocationResult(
            tool_id=tool_id,
            provider=ToolProvider.AGENTCORE,
            success=mcp_result.is_success,
            data=mcp_result.data,
            error=mcp_result.error_message,
            cost_usd=mcp_result.cost_usd,
        )

    # -------------------------------------------------------------------------
    # Batch Operations
    # -------------------------------------------------------------------------

    @require_enterprise_mode
    async def invoke_batch(
        self,
        invocations: list[tuple[str, dict[str, Any]]],
        parallel: bool = True,
    ) -> list[RegistryInvocationResult]:
        """
        Invoke multiple tools in batch.

        Args:
            invocations: List of (tool_id, params) tuples
            parallel: Run invocations in parallel if True

        Returns:
            List of RegistryInvocationResult
        """
        if parallel:
            tasks = [self.invoke(tool_id, params) for tool_id, params in invocations]
            return cast(list[RegistryInvocationResult], await asyncio.gather(*tasks))
        else:
            results = []
            for tool_id, params in invocations:
                result = await self.invoke(tool_id, params)
                results.append(result)
            return results

    # -------------------------------------------------------------------------
    # Recommendation Engine
    # -------------------------------------------------------------------------

    @require_enterprise_mode
    async def recommend_tools(
        self,
        task_description: str,
        max_recommendations: int = 5,
    ) -> list[UnifiedToolInfo]:
        """
        Recommend tools based on task description.

        Uses semantic matching to find the best tools for a given task.

        Args:
            task_description: Natural language description of the task
            max_recommendations: Maximum number of recommendations

        Returns:
            List of recommended UnifiedToolInfo objects
        """
        search_result = await self.search(task_description, limit=max_recommendations)
        return search_result.tools

    @require_enterprise_mode
    async def get_workflow_tools(
        self,
        workflow_type: str,
    ) -> list[UnifiedToolInfo]:
        """
        Get tools for a specific workflow type.

        Args:
            workflow_type: Type of workflow (e.g., "security_scan", "code_review")

        Returns:
            List of tools needed for the workflow
        """
        workflow_tools = {
            "security_scan": [
                ToolCapabilityType.SECURITY,
                ToolCapabilityType.NOTIFICATION,
            ],
            "code_review": [
                ToolCapabilityType.CODE_ANALYSIS,
                ToolCapabilityType.TICKETING,
            ],
            "incident_response": [
                ToolCapabilityType.SECURITY,
                ToolCapabilityType.NOTIFICATION,
                ToolCapabilityType.TICKETING,
            ],
            "release": [
                ToolCapabilityType.CI_CD,
                ToolCapabilityType.NOTIFICATION,
                ToolCapabilityType.DOCUMENTATION,
            ],
        }

        capabilities = workflow_tools.get(workflow_type, [])
        tools = []
        for cap in capabilities:
            cap_tools = await self.get_tools_by_capability(cap)
            tools.extend(cap_tools)

        # Deduplicate
        seen = set()
        unique_tools = []
        for tool in tools:
            if tool.tool_id not in seen:
                seen.add(tool.tool_id)
                unique_tools.append(tool)

        return unique_tools

    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------

    async def _ensure_cache_loaded(self) -> None:
        """Ensure tool cache is populated."""
        if self._cache_loaded:
            return

        await self._load_tool_cache()

    async def _load_tool_cache(self) -> None:
        """Load all tools into unified cache."""
        self._unified_tools.clear()

        # Load Aura native tools
        for aura_tool in get_aura_tools():
            unified = self._aura_tool_to_unified(aura_tool)
            self._unified_tools[unified.tool_id] = unified

        # Load external tools from MCP
        if self._mcp_client is not None:
            external_tools = await self._mcp_client.list_tools()
            for mcp_tool in external_tools:
                unified = self._mcp_tool_to_unified(mcp_tool)
                self._unified_tools[unified.tool_id] = unified

        self._cache_loaded = True
        logger.info(f"Tool cache loaded: {len(self._unified_tools)} tools")

    async def refresh_cache(self) -> None:
        """Force refresh the tool cache."""
        self._cache_loaded = False
        await self._load_tool_cache()

    # -------------------------------------------------------------------------
    # Conversion Helpers
    # -------------------------------------------------------------------------

    def _aura_tool_to_unified(self, tool: AuraToolDefinition) -> UnifiedToolInfo:
        """Convert Aura tool definition to unified format."""
        # Map Aura categories to capability types
        capability_map = {
            "security": ToolCapabilityType.SECURITY,
            "code_analysis": ToolCapabilityType.CODE_ANALYSIS,
            "documentation": ToolCapabilityType.DOCUMENTATION,
            "testing": ToolCapabilityType.SECURITY,
            "intelligence": ToolCapabilityType.SECURITY,
            "orchestration": ToolCapabilityType.CI_CD,
        }

        capabilities = [
            capability_map.get(tool.category.value, ToolCapabilityType.CODE_ANALYSIS)
        ]

        return UnifiedToolInfo(
            tool_id=tool.tool_id,
            name=tool.name,
            description=tool.description,
            provider=ToolProvider.AURA_NATIVE,
            capabilities=capabilities,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema,
            requires_hitl=tool.requires_hitl_approval,
            estimated_cost_usd=tool.estimated_cost_usd,
            version=tool.version,
            tags=["aura", tool.category.value],
        )

    def _mcp_tool_to_unified(self, tool: MCPTool) -> UnifiedToolInfo:
        """Convert MCP tool to unified format."""
        # Map MCP categories to capability types
        category_map = {
            "notification": ToolCapabilityType.NOTIFICATION,
            "ticketing": ToolCapabilityType.TICKETING,
            "alerting": ToolCapabilityType.NOTIFICATION,
            "source_control": ToolCapabilityType.CI_CD,
            "observability": ToolCapabilityType.MONITORING,
            "security": ToolCapabilityType.SECURITY,
            "ci_cd": ToolCapabilityType.CI_CD,
        }

        capabilities = [
            category_map.get(tool.category, ToolCapabilityType.NOTIFICATION)
        ]

        return UnifiedToolInfo(
            tool_id=tool.tool_id,
            name=tool.name,
            description=tool.description,
            provider=ToolProvider.AGENTCORE,
            capabilities=capabilities,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema,
            requires_auth=tool.requires_oauth,
            rate_limit_per_minute=tool.rate_limit_per_minute,
            version=tool.version,
            tags=["external", tool.category],
        )

    # -------------------------------------------------------------------------
    # Search Helpers
    # -------------------------------------------------------------------------

    def _search_aura_tools(self, query: str) -> list[UnifiedToolInfo]:
        """Search Aura tools by query."""
        query_lower = query.lower()
        matches = []

        for _tool_id, tool in self._unified_tools.items():
            if tool.provider != ToolProvider.AURA_NATIVE:
                continue

            score = self._calculate_relevance(query_lower, tool)
            if score > 0.3:
                matches.append((score, tool))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in matches]

    def _calculate_relevance(self, query: str, tool: UnifiedToolInfo) -> float:
        """Calculate relevance score for a tool."""
        score = 0.0

        if query in tool.name.lower():
            score += 0.5
        elif any(word in tool.name.lower() for word in query.split()):
            score += 0.3

        if query in tool.description.lower():
            score += 0.3
        elif any(word in tool.description.lower() for word in query.split()):
            score += 0.2

        for tag in tool.tags:
            if query in tag.lower():
                score += 0.1

        return min(score, 1.0)

    def _sort_by_relevance(
        self, query: str, tools: list[UnifiedToolInfo]
    ) -> list[UnifiedToolInfo]:
        """Sort tools by relevance to query."""
        query_lower = query.lower()
        scored = [(self._calculate_relevance(query_lower, t), t) for t in tools]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored]

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------

    def get_metrics(self) -> dict[str, Any]:
        """Get registry metrics."""
        mcp_metrics = self._mcp_client.get_metrics() if self._mcp_client else {}
        adapter_metrics = self._aura_adapter.get_metrics() if self._aura_adapter else {}

        return {
            "total_tools": len(self._unified_tools),
            "aura_tools": len(
                [
                    t
                    for t in self._unified_tools.values()
                    if t.provider == ToolProvider.AURA_NATIVE
                ]
            ),
            "external_tools": len(
                [
                    t
                    for t in self._unified_tools.values()
                    if t.provider == ToolProvider.AGENTCORE
                ]
            ),
            "invocation_counts": self._invocation_counts,
            "total_cost_usd": self._total_cost_usd,
            "mcp_metrics": mcp_metrics,
            "adapter_metrics": adapter_metrics,
        }
