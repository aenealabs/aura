"""
Project Aura - Neptune Call Graph Tracer

Traverses Neptune CALL_GRAPH, DEPENDENCIES, and INHERITANCE edges
to trace runtime security events back to source code.

Based on ADR-083: Runtime Agent Security Platform

Integration:
- Neptune graph database (Gremlin queries)
- Hybrid GraphRAG (Issue #151)
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CallGraphPath:
    """Immutable path in the call graph from runtime event to source code."""

    path_id: str
    nodes: tuple[str, ...]
    edges: tuple[str, ...]
    source_file: Optional[str] = None
    source_line_start: Optional[int] = None
    source_line_end: Optional[int] = None
    depth: int = 0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "path_id": self.path_id,
            "nodes": list(self.nodes),
            "edges": list(self.edges),
            "source_file": self.source_file,
            "source_line_start": self.source_line_start,
            "source_line_end": self.source_line_end,
            "depth": self.depth,
            "confidence": round(self.confidence, 4),
        }


@dataclass(frozen=True)
class TraceResult:
    """Immutable result of a graph trace operation."""

    trace_id: str
    event_id: str
    paths: tuple[CallGraphPath, ...]
    total_paths_found: int
    max_depth_reached: int
    timestamp: datetime
    query_latency_ms: float

    @property
    def has_source(self) -> bool:
        """True if any path reaches source code."""
        return any(p.source_file is not None for p in self.paths)

    @property
    def best_path(self) -> Optional[CallGraphPath]:
        """Path with highest confidence."""
        if not self.paths:
            return None
        return max(self.paths, key=lambda p: p.confidence)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "trace_id": self.trace_id,
            "event_id": self.event_id,
            "paths": [p.to_dict() for p in self.paths],
            "total_paths_found": self.total_paths_found,
            "max_depth_reached": self.max_depth_reached,
            "timestamp": self.timestamp.isoformat(),
            "query_latency_ms": round(self.query_latency_ms, 3),
            "has_source": self.has_source,
        }


class GraphTracer:
    """
    Traces runtime events to source code via Neptune call graph.

    Traverses CALL_GRAPH, DEPENDENCIES, and INHERITANCE edges to find
    code paths that produced the observed runtime behavior.

    Usage:
        tracer = GraphTracer()
        result = await tracer.trace_event(
            event_id="te-abc123",
            agent_id="coder-agent",
            tool_name="write_file",
        )
        if result.has_source:
            print(f"Root cause: {result.best_path.source_file}")
    """

    def __init__(
        self,
        neptune_client: Optional[Any] = None,
        use_mock: bool = True,
        max_depth: int = 10,
        max_paths: int = 5,
    ):
        self._neptune = neptune_client
        self.use_mock = use_mock
        self.max_depth = max_depth
        self.max_paths = max_paths

        # Mock graph data
        self._mock_graph: dict[str, list[dict[str, Any]]] = {}

    async def trace_event(
        self,
        event_id: str,
        agent_id: str,
        tool_name: Optional[str] = None,
        function_name: Optional[str] = None,
    ) -> TraceResult:
        """
        Trace a runtime event to source code.

        Args:
            event_id: The traffic event ID to trace.
            agent_id: Agent that produced the event.
            tool_name: Optional tool name for narrowing the search.
            function_name: Optional function name for direct lookup.

        Returns:
            TraceResult with call graph paths to source code.
        """
        import time

        start = time.monotonic()

        if self.use_mock:
            paths = self._mock_trace(agent_id, tool_name, function_name)
        else:
            paths = await self._neptune_trace(agent_id, tool_name, function_name)

        elapsed_ms = (time.monotonic() - start) * 1000
        max_depth = max((p.depth for p in paths), default=0)

        return TraceResult(
            trace_id=f"tr-{uuid.uuid4().hex[:16]}",
            event_id=event_id,
            paths=tuple(paths[: self.max_paths]),
            total_paths_found=len(paths),
            max_depth_reached=max_depth,
            timestamp=datetime.now(timezone.utc),
            query_latency_ms=elapsed_ms,
        )

    def add_mock_path(
        self,
        agent_id: str,
        tool_name: str,
        source_file: str,
        source_line_start: int,
        source_line_end: int,
        nodes: Optional[list[str]] = None,
        edges: Optional[list[str]] = None,
    ) -> None:
        """Add a mock graph path for testing."""
        if agent_id not in self._mock_graph:
            self._mock_graph[agent_id] = []

        self._mock_graph[agent_id].append(
            {
                "tool_name": tool_name,
                "source_file": source_file,
                "source_line_start": source_line_start,
                "source_line_end": source_line_end,
                "nodes": nodes or [agent_id, tool_name, source_file],
                "edges": edges or ["CALLS", "DEFINED_IN"],
            }
        )

    def _mock_trace(
        self,
        agent_id: str,
        tool_name: Optional[str],
        function_name: Optional[str],
    ) -> list[CallGraphPath]:
        """Mock trace using in-memory graph data."""
        paths = []
        agent_paths = self._mock_graph.get(agent_id, [])

        for mock_path in agent_paths:
            if tool_name and mock_path["tool_name"] != tool_name:
                continue

            paths.append(
                CallGraphPath(
                    path_id=f"cp-{uuid.uuid4().hex[:12]}",
                    nodes=tuple(mock_path["nodes"]),
                    edges=tuple(mock_path["edges"]),
                    source_file=mock_path["source_file"],
                    source_line_start=mock_path["source_line_start"],
                    source_line_end=mock_path["source_line_end"],
                    depth=len(mock_path["nodes"]) - 1,
                    confidence=0.9,
                )
            )

        return paths

    async def _neptune_trace(
        self,
        agent_id: str,
        tool_name: Optional[str],
        function_name: Optional[str],
    ) -> list[CallGraphPath]:
        """Trace via Neptune Gremlin queries."""
        logger.info("Neptune trace not implemented for mock-first development")
        return []
