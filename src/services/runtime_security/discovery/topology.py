"""
Project Aura - Agent Topology Builder

Builds and maintains a Neptune graph representing the real-time
agent communication topology for visualization and analysis.

Based on ADR-083: Runtime Agent Security Platform

Compliance:
- NIST 800-53 CM-8: Information system component inventory
- NIST 800-53 SA-17: Developer security architecture
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Types of nodes in the agent topology graph."""

    AGENT = "agent"
    TOOL = "tool"
    MCP_SERVER = "mcp_server"
    LLM_ENDPOINT = "llm_endpoint"


class EdgeType(Enum):
    """Types of edges in the agent topology graph."""

    CALLS = "calls"  # Agent → Tool/LLM
    COMMUNICATES = "communicates"  # Agent → Agent
    SERVES = "serves"  # MCP Server → Tool
    REGISTERS = "registers"  # Agent → MCP Server


@dataclass(frozen=True)
class TopologyNode:
    """Immutable node in the agent topology graph."""

    node_id: str
    node_type: NodeType
    label: str
    first_seen: datetime
    last_seen: datetime
    properties: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "label": self.label,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "properties": dict(self.properties),
        }


@dataclass(frozen=True)
class TopologyEdge:
    """Immutable edge in the agent topology graph."""

    edge_id: str
    edge_type: EdgeType
    source_id: str
    target_id: str
    weight: int  # Number of interactions
    first_seen: datetime
    last_seen: datetime
    properties: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "edge_id": self.edge_id,
            "edge_type": self.edge_type.value,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "weight": self.weight,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "properties": dict(self.properties),
        }


@dataclass(frozen=True)
class TopologySnapshot:
    """Immutable snapshot of the agent topology graph."""

    snapshot_id: str
    timestamp: datetime
    nodes: tuple[TopologyNode, ...]
    edges: tuple[TopologyEdge, ...]

    @property
    def node_count(self) -> int:
        """Total number of nodes."""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Total number of edges."""
        return len(self.edges)

    @property
    def agent_count(self) -> int:
        """Number of agent nodes."""
        return sum(1 for n in self.nodes if n.node_type == NodeType.AGENT)

    @property
    def tool_count(self) -> int:
        """Number of tool nodes."""
        return sum(1 for n in self.nodes if n.node_type == NodeType.TOOL)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp.isoformat(),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "agent_count": self.agent_count,
            "tool_count": self.tool_count,
        }


class AgentTopologyBuilder:
    """
    Builds and maintains the agent communication topology graph.

    Processes traffic events to construct a graph of agents, tools,
    MCP servers, and their interactions. Supports both in-memory
    (testing) and Neptune (production) backends.

    Usage:
        builder = AgentTopologyBuilder()

        # Record interactions from traffic events
        builder.record_agent_to_tool("coder-agent", "semantic_search")
        builder.record_agent_to_agent("coder-agent", "reviewer-agent")
        builder.record_agent_to_llm("coder-agent", "bedrock-claude")

        # Get current topology
        snapshot = builder.snapshot()
    """

    def __init__(
        self,
        neptune_client: Optional[Any] = None,
        use_mock: bool = True,
    ):
        self._neptune = neptune_client
        self.use_mock = use_mock

        # In-memory graph
        self._nodes: dict[str, _MutableNode] = {}
        self._edges: dict[str, _MutableEdge] = {}

    def record_agent_to_tool(
        self,
        agent_id: str,
        tool_name: str,
        properties: Optional[dict[str, str]] = None,
    ) -> TopologyEdge:
        """Record an agent-to-tool interaction."""
        self._ensure_node(agent_id, NodeType.AGENT, agent_id)
        self._ensure_node(f"tool:{tool_name}", NodeType.TOOL, tool_name)
        edge = self._ensure_edge(
            agent_id, f"tool:{tool_name}", EdgeType.CALLS, properties
        )
        return self._freeze_edge(edge)

    def record_agent_to_agent(
        self,
        source_agent_id: str,
        target_agent_id: str,
        properties: Optional[dict[str, str]] = None,
    ) -> TopologyEdge:
        """Record an agent-to-agent communication."""
        self._ensure_node(source_agent_id, NodeType.AGENT, source_agent_id)
        self._ensure_node(target_agent_id, NodeType.AGENT, target_agent_id)
        edge = self._ensure_edge(
            source_agent_id, target_agent_id, EdgeType.COMMUNICATES, properties
        )
        return self._freeze_edge(edge)

    def record_agent_to_llm(
        self,
        agent_id: str,
        llm_endpoint: str,
        properties: Optional[dict[str, str]] = None,
    ) -> TopologyEdge:
        """Record an agent-to-LLM interaction."""
        self._ensure_node(agent_id, NodeType.AGENT, agent_id)
        self._ensure_node(f"llm:{llm_endpoint}", NodeType.LLM_ENDPOINT, llm_endpoint)
        edge = self._ensure_edge(
            agent_id, f"llm:{llm_endpoint}", EdgeType.CALLS, properties
        )
        return self._freeze_edge(edge)

    def record_mcp_server(
        self,
        server_id: str,
        server_name: str,
        tools_provided: Optional[list[str]] = None,
    ) -> None:
        """Record an MCP server and its tool offerings."""
        self._ensure_node(f"mcp:{server_id}", NodeType.MCP_SERVER, server_name)
        if tools_provided:
            for tool in tools_provided:
                self._ensure_node(f"tool:{tool}", NodeType.TOOL, tool)
                self._ensure_edge(f"mcp:{server_id}", f"tool:{tool}", EdgeType.SERVES)

    def snapshot(self) -> TopologySnapshot:
        """Create an immutable snapshot of the current topology."""
        nodes = tuple(self._freeze_node(n) for n in self._nodes.values())
        edges = tuple(self._freeze_edge(e) for e in self._edges.values())

        return TopologySnapshot(
            snapshot_id=f"ts-{uuid.uuid4().hex[:16]}",
            timestamp=datetime.now(timezone.utc),
            nodes=nodes,
            edges=edges,
        )

    def get_node(self, node_id: str) -> Optional[TopologyNode]:
        """Get a specific node."""
        node = self._nodes.get(node_id)
        if node is None:
            return None
        return self._freeze_node(node)

    def get_neighbors(self, node_id: str) -> list[TopologyNode]:
        """Get all nodes connected to the given node."""
        neighbor_ids: set[str] = set()
        for edge in self._edges.values():
            if edge.source_id == node_id:
                neighbor_ids.add(edge.target_id)
            elif edge.target_id == node_id:
                neighbor_ids.add(edge.source_id)

        return [
            self._freeze_node(self._nodes[nid])
            for nid in neighbor_ids
            if nid in self._nodes
        ]

    def get_edges_for_node(self, node_id: str) -> list[TopologyEdge]:
        """Get all edges connected to the given node."""
        return [
            self._freeze_edge(e)
            for e in self._edges.values()
            if e.source_id == node_id or e.target_id == node_id
        ]

    @property
    def node_count(self) -> int:
        """Total number of nodes."""
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        """Total number of edges."""
        return len(self._edges)

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _ensure_node(
        self, node_id: str, node_type: NodeType, label: str
    ) -> _MutableNode:
        """Get or create a node."""
        now = datetime.now(timezone.utc)
        if node_id not in self._nodes:
            self._nodes[node_id] = _MutableNode(
                node_id=node_id,
                node_type=node_type,
                label=label,
                first_seen=now,
                last_seen=now,
            )
        else:
            self._nodes[node_id].last_seen = now
        return self._nodes[node_id]

    def _ensure_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        properties: Optional[dict[str, str]] = None,
    ) -> "_MutableEdge":
        """Get or create an edge, incrementing weight."""
        now = datetime.now(timezone.utc)
        edge_key = f"{source_id}→{target_id}:{edge_type.value}"

        if edge_key not in self._edges:
            self._edges[edge_key] = _MutableEdge(
                edge_id=f"te-{uuid.uuid4().hex[:12]}",
                edge_type=edge_type,
                source_id=source_id,
                target_id=target_id,
                first_seen=now,
                last_seen=now,
            )

        edge = self._edges[edge_key]
        edge.weight += 1
        edge.last_seen = now
        if properties:
            edge.properties.update(properties)
        return edge

    @staticmethod
    def _freeze_node(node: "_MutableNode") -> TopologyNode:
        """Convert mutable node to frozen dataclass."""
        return TopologyNode(
            node_id=node.node_id,
            node_type=node.node_type,
            label=node.label,
            first_seen=node.first_seen,
            last_seen=node.last_seen,
            properties=tuple(sorted(node.properties.items())),
        )

    @staticmethod
    def _freeze_edge(edge: "_MutableEdge") -> TopologyEdge:
        """Convert mutable edge to frozen dataclass."""
        return TopologyEdge(
            edge_id=edge.edge_id,
            edge_type=edge.edge_type,
            source_id=edge.source_id,
            target_id=edge.target_id,
            weight=edge.weight,
            first_seen=edge.first_seen,
            last_seen=edge.last_seen,
            properties=tuple(sorted(edge.properties.items())),
        )


class _MutableNode:
    """Internal mutable node for tracking."""

    def __init__(
        self,
        node_id: str,
        node_type: NodeType,
        label: str,
        first_seen: datetime,
        last_seen: datetime,
    ):
        self.node_id = node_id
        self.node_type = node_type
        self.label = label
        self.first_seen = first_seen
        self.last_seen = last_seen
        self.properties: dict[str, str] = {}


class _MutableEdge:
    """Internal mutable edge for tracking."""

    def __init__(
        self,
        edge_id: str,
        edge_type: EdgeType,
        source_id: str,
        target_id: str,
        first_seen: datetime,
        last_seen: datetime,
    ):
        self.edge_id = edge_id
        self.edge_type = edge_type
        self.source_id = source_id
        self.target_id = target_id
        self.weight: int = 0
        self.first_seen = first_seen
        self.last_seen = last_seen
        self.properties: dict[str, str] = {}
