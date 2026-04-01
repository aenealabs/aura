"""
Tests for the Agent Topology Builder.

Covers AgentTopologyBuilder graph construction, node/edge lifecycle,
edge weight incrementing, snapshot generation, and TopologyNode /
TopologyEdge / TopologySnapshot frozen dataclass serialization.
"""

from datetime import datetime, timezone

import pytest

from src.services.runtime_security.discovery import (
    AgentTopologyBuilder,
    TopologyEdge,
    TopologyNode,
    TopologySnapshot,
)
from src.services.runtime_security.discovery.topology import EdgeType, NodeType

# ---------------------------------------------------------------------------
# TopologyNode frozen dataclass
# ---------------------------------------------------------------------------


class TestTopologyNode:
    """Tests for the TopologyNode frozen dataclass."""

    def test_create_node(self):
        """Test creating a TopologyNode with all fields."""
        now = datetime.now(timezone.utc)
        node = TopologyNode(
            node_id="agent:coder",
            node_type=NodeType.AGENT,
            label="coder",
            first_seen=now,
            last_seen=now,
            properties=(("team", "platform"),),
        )
        assert node.node_id == "agent:coder"
        assert node.node_type == NodeType.AGENT
        assert node.label == "coder"

    def test_node_is_frozen(self):
        """Test that TopologyNode is immutable."""
        now = datetime.now(timezone.utc)
        node = TopologyNode(
            node_id="frozen",
            node_type=NodeType.TOOL,
            label="tool",
            first_seen=now,
            last_seen=now,
        )
        with pytest.raises(AttributeError):
            node.node_id = "mutated"  # type: ignore[misc]

    def test_node_to_dict(self):
        """Test TopologyNode.to_dict serialization."""
        now = datetime.now(timezone.utc)
        node = TopologyNode(
            node_id="node-1",
            node_type=NodeType.MCP_SERVER,
            label="MCP Tools",
            first_seen=now,
            last_seen=now,
            properties=(("version", "1.0"),),
        )
        d = node.to_dict()
        assert d["node_id"] == "node-1"
        assert d["node_type"] == "mcp_server"
        assert d["label"] == "MCP Tools"
        assert d["first_seen"] == now.isoformat()
        assert d["last_seen"] == now.isoformat()
        assert d["properties"] == {"version": "1.0"}

    def test_node_to_dict_empty_properties(self):
        """Test to_dict with default empty properties."""
        now = datetime.now(timezone.utc)
        node = TopologyNode(
            node_id="empty",
            node_type=NodeType.LLM_ENDPOINT,
            label="bedrock",
            first_seen=now,
            last_seen=now,
        )
        d = node.to_dict()
        assert d["properties"] == {}


# ---------------------------------------------------------------------------
# TopologyEdge frozen dataclass
# ---------------------------------------------------------------------------


class TestTopologyEdge:
    """Tests for the TopologyEdge frozen dataclass."""

    def test_create_edge(self):
        """Test creating a TopologyEdge with all fields."""
        now = datetime.now(timezone.utc)
        edge = TopologyEdge(
            edge_id="te-abc123",
            edge_type=EdgeType.CALLS,
            source_id="agent:coder",
            target_id="tool:search",
            weight=3,
            first_seen=now,
            last_seen=now,
            properties=(("context", "rag"),),
        )
        assert edge.edge_id == "te-abc123"
        assert edge.edge_type == EdgeType.CALLS
        assert edge.source_id == "agent:coder"
        assert edge.target_id == "tool:search"
        assert edge.weight == 3

    def test_edge_is_frozen(self):
        """Test that TopologyEdge is immutable."""
        now = datetime.now(timezone.utc)
        edge = TopologyEdge(
            edge_id="frozen-edge",
            edge_type=EdgeType.COMMUNICATES,
            source_id="a",
            target_id="b",
            weight=1,
            first_seen=now,
            last_seen=now,
        )
        with pytest.raises(AttributeError):
            edge.weight = 99  # type: ignore[misc]

    def test_edge_to_dict(self):
        """Test TopologyEdge.to_dict serialization."""
        now = datetime.now(timezone.utc)
        edge = TopologyEdge(
            edge_id="te-dict",
            edge_type=EdgeType.SERVES,
            source_id="mcp:server-1",
            target_id="tool:embed",
            weight=5,
            first_seen=now,
            last_seen=now,
            properties=(("protocol", "grpc"),),
        )
        d = edge.to_dict()
        assert d["edge_id"] == "te-dict"
        assert d["edge_type"] == "serves"
        assert d["source_id"] == "mcp:server-1"
        assert d["target_id"] == "tool:embed"
        assert d["weight"] == 5
        assert d["first_seen"] == now.isoformat()
        assert d["last_seen"] == now.isoformat()
        assert d["properties"] == {"protocol": "grpc"}


# ---------------------------------------------------------------------------
# TopologySnapshot frozen dataclass
# ---------------------------------------------------------------------------


class TestTopologySnapshot:
    """Tests for the TopologySnapshot frozen dataclass."""

    def _make_snapshot(self, num_agents=1, num_tools=1, num_edges=1):
        """Helper to create a TopologySnapshot with specified counts."""
        now = datetime.now(timezone.utc)
        nodes = []
        for i in range(num_agents):
            nodes.append(
                TopologyNode(
                    node_id=f"agent-{i}",
                    node_type=NodeType.AGENT,
                    label=f"agent-{i}",
                    first_seen=now,
                    last_seen=now,
                )
            )
        for i in range(num_tools):
            nodes.append(
                TopologyNode(
                    node_id=f"tool:{i}",
                    node_type=NodeType.TOOL,
                    label=f"tool-{i}",
                    first_seen=now,
                    last_seen=now,
                )
            )
        edges = []
        for i in range(num_edges):
            edges.append(
                TopologyEdge(
                    edge_id=f"te-{i}",
                    edge_type=EdgeType.CALLS,
                    source_id=f"agent-{i % num_agents}",
                    target_id=f"tool:{i % num_tools}",
                    weight=1,
                    first_seen=now,
                    last_seen=now,
                )
            )
        return TopologySnapshot(
            snapshot_id="ts-test",
            timestamp=now,
            nodes=tuple(nodes),
            edges=tuple(edges),
        )

    def test_snapshot_counts(self):
        """Test node_count, edge_count, agent_count, tool_count properties."""
        snap = self._make_snapshot(num_agents=2, num_tools=3, num_edges=4)
        assert snap.node_count == 5  # 2 agents + 3 tools
        assert snap.edge_count == 4
        assert snap.agent_count == 2
        assert snap.tool_count == 3

    def test_snapshot_is_frozen(self):
        """Test that TopologySnapshot is immutable."""
        snap = self._make_snapshot()
        with pytest.raises(AttributeError):
            snap.snapshot_id = "new-id"  # type: ignore[misc]

    def test_snapshot_to_dict(self):
        """Test TopologySnapshot.to_dict serialization."""
        snap = self._make_snapshot(num_agents=1, num_tools=1, num_edges=1)
        d = snap.to_dict()
        assert d["snapshot_id"] == "ts-test"
        assert isinstance(d["timestamp"], str)
        assert len(d["nodes"]) == 2
        assert len(d["edges"]) == 1
        assert d["node_count"] == 2
        assert d["edge_count"] == 1
        assert d["agent_count"] == 1
        assert d["tool_count"] == 1

    def test_empty_snapshot(self):
        """Test an empty snapshot with no nodes or edges."""
        now = datetime.now(timezone.utc)
        snap = TopologySnapshot(
            snapshot_id="ts-empty",
            timestamp=now,
            nodes=(),
            edges=(),
        )
        assert snap.node_count == 0
        assert snap.edge_count == 0
        assert snap.agent_count == 0
        assert snap.tool_count == 0


# ---------------------------------------------------------------------------
# NodeType and EdgeType enums
# ---------------------------------------------------------------------------


class TestGraphEnums:
    """Tests for NodeType and EdgeType enums."""

    def test_node_types(self):
        """Test all NodeType values."""
        assert NodeType.AGENT.value == "agent"
        assert NodeType.TOOL.value == "tool"
        assert NodeType.MCP_SERVER.value == "mcp_server"
        assert NodeType.LLM_ENDPOINT.value == "llm_endpoint"
        assert len(NodeType) == 4

    def test_edge_types(self):
        """Test all EdgeType values."""
        assert EdgeType.CALLS.value == "calls"
        assert EdgeType.COMMUNICATES.value == "communicates"
        assert EdgeType.SERVES.value == "serves"
        assert EdgeType.REGISTERS.value == "registers"
        assert len(EdgeType) == 4


# ---------------------------------------------------------------------------
# AgentTopologyBuilder - record_agent_to_tool
# ---------------------------------------------------------------------------


class TestRecordAgentToTool:
    """Tests for recording agent-to-tool interactions."""

    def test_creates_agent_and_tool_nodes(self, topology_builder):
        """Test that recording creates both agent and tool nodes."""
        topology_builder.record_agent_to_tool("coder-agent", "semantic_search")
        assert topology_builder.node_count == 2

        agent_node = topology_builder.get_node("coder-agent")
        assert agent_node is not None
        assert agent_node.node_type == NodeType.AGENT

        tool_node = topology_builder.get_node("tool:semantic_search")
        assert tool_node is not None
        assert tool_node.node_type == NodeType.TOOL

    def test_creates_calls_edge(self, topology_builder):
        """Test that a CALLS edge is created between agent and tool."""
        edge = topology_builder.record_agent_to_tool("coder-agent", "search")
        assert edge.edge_type == EdgeType.CALLS
        assert edge.source_id == "coder-agent"
        assert edge.target_id == "tool:search"
        assert edge.weight == 1

    def test_edge_weight_increments(self, topology_builder):
        """Test that calling the same interaction increments edge weight."""
        topology_builder.record_agent_to_tool("coder-agent", "search")
        edge = topology_builder.record_agent_to_tool("coder-agent", "search")
        assert edge.weight == 2

    def test_edge_weight_increments_three_times(self, topology_builder):
        """Test edge weight after three interactions."""
        topology_builder.record_agent_to_tool("a", "t")
        topology_builder.record_agent_to_tool("a", "t")
        edge = topology_builder.record_agent_to_tool("a", "t")
        assert edge.weight == 3

    def test_properties_on_edge(self, topology_builder):
        """Test passing properties to the edge."""
        edge = topology_builder.record_agent_to_tool(
            "coder-agent",
            "search",
            properties={"context": "rag-pipeline"},
        )
        assert ("context", "rag-pipeline") in edge.properties


# ---------------------------------------------------------------------------
# AgentTopologyBuilder - record_agent_to_agent
# ---------------------------------------------------------------------------


class TestRecordAgentToAgent:
    """Tests for recording agent-to-agent communication."""

    def test_creates_two_agent_nodes(self, topology_builder):
        """Test that two agent nodes are created."""
        topology_builder.record_agent_to_agent("coder-agent", "reviewer-agent")
        assert topology_builder.node_count == 2

        src = topology_builder.get_node("coder-agent")
        tgt = topology_builder.get_node("reviewer-agent")
        assert src is not None and src.node_type == NodeType.AGENT
        assert tgt is not None and tgt.node_type == NodeType.AGENT

    def test_creates_communicates_edge(self, topology_builder):
        """Test that a COMMUNICATES edge is created."""
        edge = topology_builder.record_agent_to_agent("coder-agent", "reviewer-agent")
        assert edge.edge_type == EdgeType.COMMUNICATES
        assert edge.source_id == "coder-agent"
        assert edge.target_id == "reviewer-agent"
        assert edge.weight == 1

    def test_agent_to_agent_weight_increments(self, topology_builder):
        """Test weight incrementing for agent-to-agent edges."""
        topology_builder.record_agent_to_agent("a", "b")
        edge = topology_builder.record_agent_to_agent("a", "b")
        assert edge.weight == 2


# ---------------------------------------------------------------------------
# AgentTopologyBuilder - record_agent_to_llm
# ---------------------------------------------------------------------------


class TestRecordAgentToLLM:
    """Tests for recording agent-to-LLM interactions."""

    def test_creates_agent_and_llm_nodes(self, topology_builder):
        """Test that agent and LLM endpoint nodes are created."""
        topology_builder.record_agent_to_llm("coder-agent", "bedrock-claude")
        assert topology_builder.node_count == 2

        llm_node = topology_builder.get_node("llm:bedrock-claude")
        assert llm_node is not None
        assert llm_node.node_type == NodeType.LLM_ENDPOINT
        assert llm_node.label == "bedrock-claude"

    def test_creates_calls_edge_to_llm(self, topology_builder):
        """Test that a CALLS edge is created for LLM interaction."""
        edge = topology_builder.record_agent_to_llm("coder-agent", "bedrock-claude")
        assert edge.edge_type == EdgeType.CALLS
        assert edge.source_id == "coder-agent"
        assert edge.target_id == "llm:bedrock-claude"

    def test_llm_edge_weight_increments(self, topology_builder):
        """Test weight incrementing for LLM edges."""
        topology_builder.record_agent_to_llm("a", "llm-1")
        edge = topology_builder.record_agent_to_llm("a", "llm-1")
        assert edge.weight == 2


# ---------------------------------------------------------------------------
# AgentTopologyBuilder - record_mcp_server
# ---------------------------------------------------------------------------


class TestRecordMCPServer:
    """Tests for recording MCP servers in the topology."""

    def test_creates_mcp_server_node(self, topology_builder):
        """Test that an MCP server node is created."""
        topology_builder.record_mcp_server("srv-1", "Tools Server")
        node = topology_builder.get_node("mcp:srv-1")
        assert node is not None
        assert node.node_type == NodeType.MCP_SERVER
        assert node.label == "Tools Server"

    def test_creates_tool_nodes_and_serves_edges(self, topology_builder):
        """Test that tools and SERVES edges are created."""
        topology_builder.record_mcp_server(
            "srv-1",
            "Tools Server",
            tools_provided=["search", "embed"],
        )
        # 1 MCP + 2 tools = 3 nodes
        assert topology_builder.node_count == 3
        # 2 SERVES edges
        assert topology_builder.edge_count == 2

        search_node = topology_builder.get_node("tool:search")
        assert search_node is not None
        assert search_node.node_type == NodeType.TOOL

    def test_mcp_server_no_tools(self, topology_builder):
        """Test recording an MCP server with no tools."""
        topology_builder.record_mcp_server("srv-empty", "Empty Server")
        assert topology_builder.node_count == 1
        assert topology_builder.edge_count == 0


# ---------------------------------------------------------------------------
# AgentTopologyBuilder - snapshot
# ---------------------------------------------------------------------------


class TestSnapshot:
    """Tests for topology snapshot creation."""

    def test_empty_snapshot(self, topology_builder):
        """Test snapshot of empty topology."""
        snap = topology_builder.snapshot()
        assert snap.node_count == 0
        assert snap.edge_count == 0
        assert snap.snapshot_id.startswith("ts-")

    def test_snapshot_captures_all_nodes_and_edges(self, topology_builder):
        """Test that snapshot captures the full graph."""
        topology_builder.record_agent_to_tool("coder", "search")
        topology_builder.record_agent_to_agent("coder", "reviewer")
        topology_builder.record_agent_to_llm("coder", "claude")

        snap = topology_builder.snapshot()
        # Nodes: coder, tool:search, reviewer, llm:claude = 4
        assert snap.node_count == 4
        # Edges: coder->tool:search, coder->reviewer, coder->llm:claude = 3
        assert snap.edge_count == 3
        assert snap.agent_count == 2
        assert snap.tool_count == 1

    def test_snapshot_immutability(self, topology_builder):
        """Test that snapshot is not affected by later mutations."""
        topology_builder.record_agent_to_tool("a", "t1")
        snap1 = topology_builder.snapshot()
        count_before = snap1.node_count

        topology_builder.record_agent_to_tool("b", "t2")
        # snap1 should still have old count
        assert snap1.node_count == count_before

    def test_snapshot_unique_ids(self, topology_builder):
        """Test that successive snapshots have unique IDs."""
        s1 = topology_builder.snapshot()
        s2 = topology_builder.snapshot()
        assert s1.snapshot_id != s2.snapshot_id


# ---------------------------------------------------------------------------
# AgentTopologyBuilder - get_node
# ---------------------------------------------------------------------------


class TestGetNode:
    """Tests for the get_node method."""

    def test_get_existing_node(self, topology_builder):
        """Test getting an existing node by ID."""
        topology_builder.record_agent_to_tool("coder", "search")
        node = topology_builder.get_node("coder")
        assert node is not None
        assert node.node_id == "coder"
        assert node.node_type == NodeType.AGENT

    def test_get_nonexistent_node(self, topology_builder):
        """Test getting a node that does not exist."""
        assert topology_builder.get_node("missing") is None

    def test_get_tool_node_with_prefix(self, topology_builder):
        """Test getting a tool node (tool:name prefix)."""
        topology_builder.record_agent_to_tool("coder", "search")
        node = topology_builder.get_node("tool:search")
        assert node is not None
        assert node.node_type == NodeType.TOOL


# ---------------------------------------------------------------------------
# AgentTopologyBuilder - get_neighbors
# ---------------------------------------------------------------------------


class TestGetNeighbors:
    """Tests for the get_neighbors method."""

    def test_neighbors_of_agent(self, topology_builder):
        """Test getting neighbors of an agent node."""
        topology_builder.record_agent_to_tool("coder", "search")
        topology_builder.record_agent_to_agent("coder", "reviewer")
        topology_builder.record_agent_to_llm("coder", "claude")

        neighbors = topology_builder.get_neighbors("coder")
        neighbor_ids = {n.node_id for n in neighbors}
        assert "tool:search" in neighbor_ids
        assert "reviewer" in neighbor_ids
        assert "llm:claude" in neighbor_ids

    def test_neighbors_bidirectional(self, topology_builder):
        """Test that neighbors works from both ends of an edge."""
        topology_builder.record_agent_to_tool("coder", "search")
        # Tool node should see coder as neighbor
        neighbors = topology_builder.get_neighbors("tool:search")
        neighbor_ids = {n.node_id for n in neighbors}
        assert "coder" in neighbor_ids

    def test_neighbors_of_isolated_node(self, topology_builder):
        """Test neighbors of a node with no edges returns empty list."""
        topology_builder.record_mcp_server("isolated", "Alone")
        neighbors = topology_builder.get_neighbors("mcp:isolated")
        assert neighbors == []


# ---------------------------------------------------------------------------
# AgentTopologyBuilder - get_edges_for_node
# ---------------------------------------------------------------------------


class TestGetEdgesForNode:
    """Tests for the get_edges_for_node method."""

    def test_edges_for_agent(self, topology_builder):
        """Test retrieving all edges for an agent."""
        topology_builder.record_agent_to_tool("coder", "search")
        topology_builder.record_agent_to_agent("coder", "reviewer")

        edges = topology_builder.get_edges_for_node("coder")
        assert len(edges) == 2
        edge_types = {e.edge_type for e in edges}
        assert EdgeType.CALLS in edge_types
        assert EdgeType.COMMUNICATES in edge_types

    def test_edges_for_tool_node(self, topology_builder):
        """Test retrieving edges from a tool node perspective."""
        topology_builder.record_agent_to_tool("coder", "search")
        topology_builder.record_agent_to_tool("reviewer", "search")

        edges = topology_builder.get_edges_for_node("tool:search")
        assert len(edges) == 2

    def test_edges_for_nonexistent_node(self, topology_builder):
        """Test edges for a node with no connections."""
        edges = topology_builder.get_edges_for_node("ghost")
        assert edges == []


# ---------------------------------------------------------------------------
# AgentTopologyBuilder - properties
# ---------------------------------------------------------------------------


class TestTopologyProperties:
    """Tests for topology builder property accessors."""

    def test_initial_counts(self, topology_builder):
        """Test initial node and edge counts are zero."""
        assert topology_builder.node_count == 0
        assert topology_builder.edge_count == 0

    def test_counts_after_recording(self, topology_builder):
        """Test counts after recording various interactions."""
        topology_builder.record_agent_to_tool("a", "t1")
        topology_builder.record_agent_to_tool("a", "t2")
        topology_builder.record_agent_to_agent("a", "b")
        # Nodes: a, tool:t1, tool:t2, b = 4
        assert topology_builder.node_count == 4
        # Edges: a->t1, a->t2, a->b = 3
        assert topology_builder.edge_count == 3

    def test_duplicate_nodes_not_counted(self, topology_builder):
        """Test that the same node is not created twice."""
        topology_builder.record_agent_to_tool("coder", "search")
        topology_builder.record_agent_to_tool("coder", "search")
        # Still just 2 nodes (coder, tool:search)
        assert topology_builder.node_count == 2
        # Still just 1 edge (with weight=2)
        assert topology_builder.edge_count == 1
