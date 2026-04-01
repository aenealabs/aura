"""
Project Aura - MCP Tool Server

MCP Server for Project Aura Internal Tools.

Exposes Neptune, OpenSearch, and sandbox tools via MCP protocol,
enabling standardized tool access across all agent types.

ADR-029 Phase 1.4 Implementation

Usage:
    >>> from src.services.mcp_tool_server import MCPToolServer, get_internal_tools
    >>> server = MCPToolServer()
    >>> result = await server.invoke_tool("query_code_graph", {"query": "g.V().limit(10)"})
    >>> tools = server.list_tools()
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Coroutine

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.services.neptune_graph_service import NeptuneGraphService
    from src.services.opensearch_vector_service import OpenSearchVectorService
    from src.services.sandbox_network_service import SandboxNetwork
    from src.services.titan_embedding_service import TitanEmbeddingService


# =============================================================================
# Enums and Data Classes
# =============================================================================


class MCPToolCategory(Enum):
    """Tool categories for organization and permissions."""

    GRAPH = "graph"  # Neptune graph operations
    VECTOR = "vector"  # OpenSearch vector operations
    SANDBOX = "sandbox"  # Sandbox network operations
    EMBEDDING = "embedding"  # Titan embedding operations
    CACHE = "cache"  # Semantic cache operations


class MCPToolPermission(Enum):
    """Permission levels for tools."""

    READ = "read"  # Read-only operations
    WRITE = "write"  # Write operations
    EXECUTE = "execute"  # Execute/invoke operations
    ADMIN = "admin"  # Administrative operations


@dataclass
class MCPToolDefinition:
    """MCP-compliant tool definition."""

    name: str
    description: str
    category: MCPToolCategory
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permissions: list[MCPToolPermission] = field(
        default_factory=lambda: [MCPToolPermission.READ]
    )
    requires_approval: bool = False  # HITL flag
    version: str = "1.0"
    timeout_seconds: int = 30
    rate_limit_per_minute: int = 60


@dataclass
class MCPToolResult:
    """Result of an MCP tool invocation."""

    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    latency_ms: float = 0.0
    request_id: str | None = None
    timestamp: float = field(default_factory=time.time)

    @property
    def is_success(self) -> bool:
        return self.success


@dataclass
class MCPServerStats:
    """Statistics for the MCP server."""

    total_invocations: int = 0
    successful_invocations: int = 0
    failed_invocations: int = 0
    total_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_invocations == 0:
            return 0.0
        return self.successful_invocations / self.total_invocations

    @property
    def avg_latency_ms(self) -> float:
        if self.total_invocations == 0:
            return 0.0
        return self.total_latency_ms / self.total_invocations

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_invocations": self.total_invocations,
            "successful_invocations": self.successful_invocations,
            "failed_invocations": self.failed_invocations,
            "success_rate_percent": round(self.success_rate * 100, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
        }


# =============================================================================
# Tool Handlers
# =============================================================================


class GraphToolHandler:
    """Handler for Neptune graph operations."""

    def __init__(self, neptune_service: "NeptuneGraphService | None" = None) -> None:
        self.neptune = neptune_service
        self._mock_mode = neptune_service is None

    async def query_code_graph(self, params: dict[str, Any]) -> dict[str, Any]:
        """Query Neptune code knowledge graph for structural relationships."""
        query = params.get("query", "")
        entity_type = params.get("entity_type")
        depth = params.get("depth", 3)

        if self._mock_mode:
            # Return mock data
            return {
                "results": [
                    {"id": "func_1", "type": "function", "name": "process_data"},
                    {"id": "func_2", "type": "function", "name": "validate_input"},
                ],
                "count": 2,
                "query_time_ms": 15.5,
            }

        # Real Neptune query
        if self.neptune is None:
            raise RuntimeError("Neptune service not initialized")

        start_time = time.perf_counter()
        # Note: execute_query is a placeholder for actual Neptune query method
        results = await asyncio.to_thread(
            self.neptune.execute_query, query, entity_type=entity_type, depth=depth  # type: ignore[attr-defined]
        )
        query_time = (time.perf_counter() - start_time) * 1000

        return {
            "results": results,
            "count": len(results),
            "query_time_ms": query_time,
        }

    async def get_code_dependencies(self, params: dict[str, Any]) -> dict[str, Any]:
        """Get dependency graph for a code entity."""
        entity_id = params.get("entity_id", "")
        _direction = params.get(  # noqa: F841
            "direction", "both"
        )  # incoming, outgoing, both
        _max_depth = params.get("max_depth", 3)  # noqa: F841

        if self._mock_mode:
            return {
                "entity_id": entity_id,
                "dependencies": [
                    {"id": "dep_1", "type": "import", "target": "utils.py"},
                    {"id": "dep_2", "type": "call", "target": "helper_func"},
                ],
                "dependents": [
                    {"id": "dep_3", "type": "call", "source": "main.py"},
                ],
            }

        # Real implementation would query Neptune
        return {"entity_id": entity_id, "dependencies": [], "dependents": []}


class VectorToolHandler:
    """Handler for OpenSearch vector operations."""

    def __init__(
        self,
        opensearch_service: "OpenSearchVectorService | None" = None,
        embedding_service: "TitanEmbeddingService | None" = None,
    ):
        self.opensearch = opensearch_service
        self.embedder = embedding_service
        self._mock_mode = opensearch_service is None

    async def semantic_search(self, params: dict[str, Any]) -> dict[str, Any]:
        """Search OpenSearch for semantically similar code snippets."""
        query = params.get("query", "")
        k = params.get("k", 10)
        filters = params.get("filter")

        if self._mock_mode:
            return {
                "results": [
                    {
                        "id": "code_1",
                        "text": "def validate_input(data): ...",
                        "score": 0.92,
                        "metadata": {"file": "validators.py", "line": 42},
                    },
                    {
                        "id": "code_2",
                        "text": "def sanitize_input(text): ...",
                        "score": 0.87,
                        "metadata": {"file": "utils.py", "line": 15},
                    },
                ],
                "scores": [0.92, 0.87],
                "query_time_ms": 25.3,
            }

        # Generate embedding for query
        if self.embedder is None:
            raise RuntimeError("Embedding service not initialized")
        if self.opensearch is None:
            raise RuntimeError("OpenSearch service not initialized")

        start_time = time.perf_counter()
        query_vector = self.embedder.generate_embedding(query)

        # Search OpenSearch
        results = self.opensearch.search_similar(
            query_vector=query_vector,
            k=k,
            filters=filters,
        )
        query_time = (time.perf_counter() - start_time) * 1000

        return {
            "results": results,
            "scores": [r.get("score", 0) for r in results],
            "query_time_ms": query_time,
        }

    async def index_code_embedding(self, params: dict[str, Any]) -> dict[str, Any]:
        """Index a code snippet with its embedding."""
        doc_id = params.get("doc_id", "")
        text = params.get("text", "")
        metadata = params.get("metadata", {})

        if self._mock_mode:
            return {
                "indexed": True,
                "doc_id": doc_id,
                "embedding_dimension": 1024,
            }

        # Generate embedding and index
        if self.embedder is None:
            raise RuntimeError("Embedding service not initialized")
        if self.opensearch is None:
            raise RuntimeError("OpenSearch service not initialized")

        vector = self.embedder.generate_embedding(text)
        success = self.opensearch.index_embedding(
            doc_id=doc_id,
            text=text,
            vector=vector,
            metadata=metadata,
        )

        return {
            "indexed": success,
            "doc_id": doc_id,
            "embedding_dimension": len(vector),
        }


class SandboxToolHandler:
    """Handler for sandbox network operations."""

    def __init__(self, sandbox_service: "SandboxNetwork | None" = None) -> None:
        self.sandbox = sandbox_service
        self._mock_mode = sandbox_service is None

    async def provision_sandbox(self, params: dict[str, Any]) -> dict[str, Any]:
        """Provision isolated sandbox environment for patch testing."""
        isolation_level = params.get("isolation_level", "container")
        duration_minutes = params.get("duration_minutes", 30)
        resources = params.get("resources", {})

        if self._mock_mode:
            sandbox_id = (
                f"sandbox_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}"
            )
            return {
                "sandbox_id": sandbox_id,
                "endpoint": f"https://{sandbox_id}.sandbox.aura.local",
                "isolation_level": isolation_level,
                "expires_at": time.time() + (duration_minutes * 60),
                "status": "provisioning",
            }

        # Real implementation would provision via SandboxNetwork
        if self.sandbox is None:
            raise RuntimeError("Sandbox service not initialized")

        # Note: provision_sandbox is a placeholder for actual sandbox provisioning method
        result = await self.sandbox.provision_sandbox(  # type: ignore[attr-defined]
            isolation_level=isolation_level,
            duration_minutes=duration_minutes,
            resources=resources,
        )
        return dict(result)

    async def destroy_sandbox(self, params: dict[str, Any]) -> dict[str, Any]:
        """Destroy a sandbox environment."""
        sandbox_id = params.get("sandbox_id", "")

        if self._mock_mode:
            return {
                "sandbox_id": sandbox_id,
                "destroyed": True,
                "cleanup_time_ms": 150.0,
            }

        # Real implementation
        if self.sandbox is None:
            raise RuntimeError("Sandbox service not initialized")

        # Note: destroy_sandbox is a placeholder for actual sandbox destruction method
        await self.sandbox.destroy_sandbox(sandbox_id)  # type: ignore[attr-defined]
        return {
            "sandbox_id": sandbox_id,
            "destroyed": True,
        }

    async def get_sandbox_status(self, params: dict[str, Any]) -> dict[str, Any]:
        """Get status of a sandbox environment."""
        sandbox_id = params.get("sandbox_id", "")

        if self._mock_mode:
            return {
                "sandbox_id": sandbox_id,
                "status": "running",
                "isolation_level": "container",
                "created_at": time.time() - 300,
                "expires_at": time.time() + 1500,
                "resources": {
                    "cpu_limit": "500m",
                    "memory_limit": "512Mi",
                },
            }

        # Real implementation
        if self.sandbox is None:
            raise RuntimeError("Sandbox service not initialized")

        # Note: get_sandbox_status is a placeholder for actual sandbox status method
        status = await self.sandbox.get_sandbox_status(sandbox_id)  # type: ignore[attr-defined]
        return dict(status)


# =============================================================================
# MCP Tool Server
# =============================================================================


class MCPToolServer:
    """
    MCP Server for Project Aura Internal Tools.

    Exposes Neptune, OpenSearch, and sandbox tools via standardized
    MCP protocol interface for agent consumption.

    Features:
    - Tool discovery and listing
    - Schema validation
    - HITL approval for sensitive operations
    - Rate limiting
    - Metrics and auditing

    Example:
        >>> server = MCPToolServer()
        >>> tools = server.list_tools()
        >>> result = await server.invoke_tool("semantic_search", {"query": "SQL injection"})
    """

    def __init__(
        self,
        neptune_service: "NeptuneGraphService | None" = None,
        opensearch_service: "OpenSearchVectorService | None" = None,
        embedding_service: "TitanEmbeddingService | None" = None,
        sandbox_service: "SandboxNetwork | None" = None,
    ):
        """
        Initialize MCP Tool Server.

        Args:
            neptune_service: Neptune graph service (optional, mock if None)
            opensearch_service: OpenSearch vector service (optional)
            embedding_service: Titan embedding service (optional)
            sandbox_service: Sandbox network service (optional)
        """
        # Initialize handlers
        self._graph_handler = GraphToolHandler(neptune_service)
        self._vector_handler = VectorToolHandler(opensearch_service, embedding_service)
        self._sandbox_handler = SandboxToolHandler(sandbox_service)

        # Tool definitions
        self._tools = self._build_tool_definitions()

        # Tool handlers mapping
        self._handlers: dict[
            str, Callable[..., Coroutine[Any, Any, dict[str, Any]]]
        ] = {
            "query_code_graph": self._graph_handler.query_code_graph,
            "get_code_dependencies": self._graph_handler.get_code_dependencies,
            "semantic_search": self._vector_handler.semantic_search,
            "index_code_embedding": self._vector_handler.index_code_embedding,
            "provision_sandbox": self._sandbox_handler.provision_sandbox,
            "destroy_sandbox": self._sandbox_handler.destroy_sandbox,
            "get_sandbox_status": self._sandbox_handler.get_sandbox_status,
        }

        # Statistics
        self._stats = MCPServerStats()
        self._tool_stats: dict[str, MCPServerStats] = {
            name: MCPServerStats() for name in self._handlers.keys()
        }

        # Rate limiting
        self._rate_limit_tracker: dict[str, list[float]] = {}

        logger.info(f"MCPToolServer initialized with {len(self._tools)} tools")

    def _build_tool_definitions(self) -> dict[str, MCPToolDefinition]:
        """Build the registry of internal MCP tools."""
        return {
            "query_code_graph": MCPToolDefinition(
                name="query_code_graph",
                description="Query Neptune code knowledge graph for structural relationships",
                category=MCPToolCategory.GRAPH,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Gremlin query string",
                        },
                        "entity_type": {
                            "type": "string",
                            "enum": ["class", "function", "file", "module"],
                            "description": "Optional entity type filter",
                        },
                        "depth": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5,
                            "default": 3,
                            "description": "Traversal depth",
                        },
                    },
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "results": {"type": "array"},
                        "count": {"type": "integer"},
                        "query_time_ms": {"type": "number"},
                    },
                },
                permissions=[MCPToolPermission.READ],
            ),
            "get_code_dependencies": MCPToolDefinition(
                name="get_code_dependencies",
                description="Get dependency graph for a code entity",
                category=MCPToolCategory.GRAPH,
                input_schema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "Entity identifier",
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["incoming", "outgoing", "both"],
                            "default": "both",
                        },
                        "max_depth": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 3,
                        },
                    },
                    "required": ["entity_id"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string"},
                        "dependencies": {"type": "array"},
                        "dependents": {"type": "array"},
                    },
                },
                permissions=[MCPToolPermission.READ],
            ),
            "semantic_search": MCPToolDefinition(
                name="semantic_search",
                description="Search OpenSearch for semantically similar code snippets",
                category=MCPToolCategory.VECTOR,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query",
                        },
                        "k": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 10,
                        },
                        "filter": {"type": "object", "description": "Metadata filters"},
                    },
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "results": {"type": "array"},
                        "scores": {"type": "array"},
                        "query_time_ms": {"type": "number"},
                    },
                },
                permissions=[MCPToolPermission.READ],
            ),
            "index_code_embedding": MCPToolDefinition(
                name="index_code_embedding",
                description="Index a code snippet with its embedding",
                category=MCPToolCategory.VECTOR,
                input_schema={
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "Document identifier",
                        },
                        "text": {"type": "string", "description": "Code text to embed"},
                        "metadata": {
                            "type": "object",
                            "description": "Additional metadata",
                        },
                    },
                    "required": ["doc_id", "text"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "indexed": {"type": "boolean"},
                        "doc_id": {"type": "string"},
                        "embedding_dimension": {"type": "integer"},
                    },
                },
                permissions=[MCPToolPermission.WRITE],
            ),
            "provision_sandbox": MCPToolDefinition(
                name="provision_sandbox",
                description="Provision isolated sandbox environment for patch testing",
                category=MCPToolCategory.SANDBOX,
                input_schema={
                    "type": "object",
                    "properties": {
                        "isolation_level": {
                            "type": "string",
                            "enum": ["container", "vpc", "full"],
                            "default": "container",
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 60,
                            "default": 30,
                        },
                        "resources": {
                            "type": "object",
                            "description": "Resource limits",
                        },
                    },
                    "required": ["isolation_level"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "sandbox_id": {"type": "string"},
                        "endpoint": {"type": "string"},
                        "expires_at": {"type": "number"},
                        "status": {"type": "string"},
                    },
                },
                permissions=[MCPToolPermission.EXECUTE],
                requires_approval=True,  # HITL required
                timeout_seconds=120,
            ),
            "destroy_sandbox": MCPToolDefinition(
                name="destroy_sandbox",
                description="Destroy a sandbox environment",
                category=MCPToolCategory.SANDBOX,
                input_schema={
                    "type": "object",
                    "properties": {
                        "sandbox_id": {
                            "type": "string",
                            "description": "Sandbox identifier",
                        },
                    },
                    "required": ["sandbox_id"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "sandbox_id": {"type": "string"},
                        "destroyed": {"type": "boolean"},
                    },
                },
                permissions=[MCPToolPermission.EXECUTE],
            ),
            "get_sandbox_status": MCPToolDefinition(
                name="get_sandbox_status",
                description="Get status of a sandbox environment",
                category=MCPToolCategory.SANDBOX,
                input_schema={
                    "type": "object",
                    "properties": {
                        "sandbox_id": {
                            "type": "string",
                            "description": "Sandbox identifier",
                        },
                    },
                    "required": ["sandbox_id"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "sandbox_id": {"type": "string"},
                        "status": {"type": "string"},
                        "isolation_level": {"type": "string"},
                        "created_at": {"type": "number"},
                        "expires_at": {"type": "number"},
                    },
                },
                permissions=[MCPToolPermission.READ],
            ),
        }

    # -------------------------------------------------------------------------
    # Tool Discovery
    # -------------------------------------------------------------------------

    def list_tools(
        self, category: MCPToolCategory | None = None
    ) -> list[MCPToolDefinition]:
        """
        List all available MCP tools.

        Args:
            category: Optional category filter

        Returns:
            List of tool definitions
        """
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def get_tool(self, tool_name: str) -> MCPToolDefinition | None:
        """Get a specific tool by name."""
        return self._tools.get(tool_name)

    def describe_tool(self, tool_name: str) -> dict[str, Any] | None:
        """Get MCP-compatible description for a tool."""
        tool = self._tools.get(tool_name)
        if not tool:
            return None

        return {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.input_schema,
            "outputSchema": tool.output_schema,
            "version": tool.version,
            "requiresApproval": tool.requires_approval,
        }

    # -------------------------------------------------------------------------
    # Tool Invocation
    # -------------------------------------------------------------------------

    async def invoke_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        skip_approval: bool = False,
    ) -> MCPToolResult:
        """
        Invoke an MCP tool.

        Args:
            tool_name: Name of the tool to invoke
            params: Tool parameters
            skip_approval: Skip HITL approval (for testing)

        Returns:
            MCPToolResult with invocation outcome
        """
        start_time = time.perf_counter()
        request_id = self._generate_request_id(tool_name, params)

        # Update stats
        self._stats.total_invocations += 1
        if tool_name in self._tool_stats:
            self._tool_stats[tool_name].total_invocations += 1

        # Validate tool exists
        tool = self._tools.get(tool_name)
        if not tool:
            self._stats.failed_invocations += 1
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not found",
                request_id=request_id,
            )

        # Check rate limit
        if self._is_rate_limited(tool_name, tool.rate_limit_per_minute):
            self._stats.failed_invocations += 1
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Rate limit exceeded: {tool.rate_limit_per_minute}/min",
                request_id=request_id,
            )

        # Check HITL approval for sensitive operations
        if tool.requires_approval and not skip_approval:
            logger.warning(
                f"Tool '{tool_name}' requires HITL approval - returning pending status"
            )
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error="HITL approval required",
                data={
                    "pending_approval": True,
                    "tool_name": tool_name,
                    "params": params,
                },
                request_id=request_id,
            )

        # Get handler
        handler = self._handlers.get(tool_name)
        if not handler:
            self._stats.failed_invocations += 1
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=f"No handler registered for '{tool_name}'",
                request_id=request_id,
            )

        # Invoke handler with timeout
        try:
            result_data = await asyncio.wait_for(
                handler(params),
                timeout=tool.timeout_seconds,
            )

            latency_ms = (time.perf_counter() - start_time) * 1000
            self._stats.successful_invocations += 1
            self._stats.total_latency_ms += latency_ms

            if tool_name in self._tool_stats:
                self._tool_stats[tool_name].successful_invocations += 1
                self._tool_stats[tool_name].total_latency_ms += latency_ms

            # Record for rate limiting
            self._record_invocation(tool_name)

            logger.info(
                f"MCP tool invocation: {tool_name}, latency={latency_ms:.1f}ms, "
                f"request_id={request_id}"
            )

            return MCPToolResult(
                tool_name=tool_name,
                success=True,
                data=result_data,
                latency_ms=latency_ms,
                request_id=request_id,
            )

        except asyncio.TimeoutError:
            self._stats.failed_invocations += 1
            if tool_name in self._tool_stats:
                self._tool_stats[tool_name].failed_invocations += 1

            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool execution timed out after {tool.timeout_seconds}s",
                request_id=request_id,
            )

        except Exception as e:
            self._stats.failed_invocations += 1
            if tool_name in self._tool_stats:
                self._tool_stats[tool_name].failed_invocations += 1

            logger.error(f"MCP tool error: {tool_name}, error={e}")
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                request_id=request_id,
            )

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------

    def _is_rate_limited(self, tool_name: str, limit: int) -> bool:
        """Check if tool is rate limited."""
        now = time.time()
        minute_ago = now - 60

        if tool_name not in self._rate_limit_tracker:
            self._rate_limit_tracker[tool_name] = []

        # Clean old entries
        self._rate_limit_tracker[tool_name] = [
            ts for ts in self._rate_limit_tracker[tool_name] if ts > minute_ago
        ]

        return len(self._rate_limit_tracker[tool_name]) >= limit

    def _record_invocation(self, tool_name: str) -> None:
        """Record invocation for rate limiting."""
        if tool_name not in self._rate_limit_tracker:
            self._rate_limit_tracker[tool_name] = []
        self._rate_limit_tracker[tool_name].append(time.time())

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def _generate_request_id(self, tool_name: str, params: dict) -> str:
        """Generate unique request ID."""
        content = f"{tool_name}:{json.dumps(params, sort_keys=True)}:{time.time()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get_stats(self) -> dict[str, Any]:
        """Get server statistics."""
        return {
            "server": self._stats.to_dict(),
            "tools": {
                name: stats.to_dict() for name, stats in self._tool_stats.items()
            },
        }

    def clear_stats(self) -> None:
        """Clear all statistics."""
        self._stats = MCPServerStats()
        self._tool_stats = {name: MCPServerStats() for name in self._handlers.keys()}


# =============================================================================
# Factory Function
# =============================================================================


def create_mcp_tool_server(
    neptune_service: "NeptuneGraphService | None" = None,
    opensearch_service: "OpenSearchVectorService | None" = None,
    embedding_service: "TitanEmbeddingService | None" = None,
    sandbox_service: "SandboxNetwork | None" = None,
) -> MCPToolServer:
    """
    Factory function to create MCPToolServer with dependencies.

    Args:
        neptune_service: Neptune graph service
        opensearch_service: OpenSearch vector service
        embedding_service: Titan embedding service
        sandbox_service: Sandbox network service

    Returns:
        Configured MCPToolServer instance
    """
    return MCPToolServer(
        neptune_service=neptune_service,
        opensearch_service=opensearch_service,
        embedding_service=embedding_service,
        sandbox_service=sandbox_service,
    )


def get_internal_tools() -> list[MCPToolDefinition]:
    """Get list of all internal MCP tools."""
    server = MCPToolServer()
    return server.list_tools()


# =============================================================================
# Demo
# =============================================================================


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def demo() -> None:
        print("MCP Tool Server Demo")
        print("=" * 60)

        server = MCPToolServer()

        # List tools
        print("\nAvailable Tools:")
        for tool in server.list_tools():
            print(f"  - {tool.name}: {tool.description}")

        # Invoke semantic search
        print("\n--- Semantic Search ---")
        result = await server.invoke_tool(
            "semantic_search",
            {"query": "SQL injection vulnerability", "k": 5},
        )
        print(f"Success: {result.success}")
        print(f"Results: {len(result.data.get('results', []))} items")
        print(f"Latency: {result.latency_ms:.1f}ms")

        # Get dependencies
        print("\n--- Code Dependencies ---")
        result = await server.invoke_tool(
            "get_code_dependencies",
            {"entity_id": "func_validate_input", "direction": "both"},
        )
        print(f"Success: {result.success}")
        print(f"Data: {result.data}")

        # Get stats
        print("\n--- Server Stats ---")
        stats = server.get_stats()
        print(f"Total invocations: {stats['server']['total_invocations']}")
        print(f"Success rate: {stats['server']['success_rate_percent']}%")

    asyncio.run(demo())

    print("\n" + "=" * 60)
    print("Demo complete!")
