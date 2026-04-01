"""
Tests for the Neptune Call Graph Tracer.

Covers CallGraphPath and TraceResult frozen dataclasses, serialization,
mock graph traversal, tool_name filtering, and max_paths limits.
"""

import dataclasses
from datetime import datetime, timezone

import pytest

from src.services.runtime_security.correlation.graph_tracer import (
    CallGraphPath,
    GraphTracer,
    TraceResult,
)

# =========================================================================
# CallGraphPath Tests
# =========================================================================


class TestCallGraphPath:
    """Tests for the CallGraphPath frozen dataclass."""

    def test_create_with_all_fields(self):
        """Test creating a CallGraphPath with all fields populated."""
        path = CallGraphPath(
            path_id="cp-test001",
            nodes=("agent-a", "tool-x", "file.py"),
            edges=("CALLS", "DEFINED_IN"),
            source_file="src/file.py",
            source_line_start=10,
            source_line_end=20,
            depth=2,
            confidence=0.95,
        )
        assert path.path_id == "cp-test001"
        assert path.nodes == ("agent-a", "tool-x", "file.py")
        assert path.edges == ("CALLS", "DEFINED_IN")
        assert path.source_file == "src/file.py"
        assert path.source_line_start == 10
        assert path.source_line_end == 20
        assert path.depth == 2
        assert path.confidence == 0.95

    def test_create_with_defaults(self):
        """Test that optional fields default correctly."""
        path = CallGraphPath(
            path_id="cp-defaults",
            nodes=("a",),
            edges=(),
        )
        assert path.source_file is None
        assert path.source_line_start is None
        assert path.source_line_end is None
        assert path.depth == 0
        assert path.confidence == 0.0

    def test_frozen_immutability_path_id(self):
        """Test that path_id cannot be mutated after creation."""
        path = CallGraphPath(
            path_id="cp-frozen",
            nodes=("a",),
            edges=(),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            path.path_id = "cp-mutated"  # type: ignore[misc]

    def test_frozen_immutability_confidence(self):
        """Test that confidence cannot be mutated after creation."""
        path = CallGraphPath(
            path_id="cp-frozen2",
            nodes=("a",),
            edges=(),
            confidence=0.5,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            path.confidence = 1.0  # type: ignore[misc]

    def test_frozen_immutability_source_file(self):
        """Test that source_file cannot be mutated after creation."""
        path = CallGraphPath(
            path_id="cp-frozen3",
            nodes=("a",),
            edges=(),
            source_file="original.py",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            path.source_file = "hacked.py"  # type: ignore[misc]

    def test_to_dict_serialization(self):
        """Test to_dict produces expected keys and value types."""
        path = CallGraphPath(
            path_id="cp-dict001",
            nodes=("agent", "tool", "file"),
            edges=("CALLS", "DEFINED_IN"),
            source_file="src/handler.py",
            source_line_start=42,
            source_line_end=58,
            depth=2,
            confidence=0.8765,
        )
        d = path.to_dict()
        assert d["path_id"] == "cp-dict001"
        assert d["nodes"] == ["agent", "tool", "file"]
        assert d["edges"] == ["CALLS", "DEFINED_IN"]
        assert d["source_file"] == "src/handler.py"
        assert d["source_line_start"] == 42
        assert d["source_line_end"] == 58
        assert d["depth"] == 2
        assert d["confidence"] == 0.8765

    def test_to_dict_nodes_edges_are_lists(self):
        """Test that nodes and edges are serialized as lists, not tuples."""
        path = CallGraphPath(
            path_id="cp-lists",
            nodes=("x", "y"),
            edges=("E1",),
        )
        d = path.to_dict()
        assert isinstance(d["nodes"], list)
        assert isinstance(d["edges"], list)

    def test_to_dict_optional_fields_null(self):
        """Test that unset optional fields serialize as None."""
        path = CallGraphPath(
            path_id="cp-nulls",
            nodes=(),
            edges=(),
        )
        d = path.to_dict()
        assert d["source_file"] is None
        assert d["source_line_start"] is None
        assert d["source_line_end"] is None

    def test_empty_path(self):
        """Test creating a path with empty nodes and edges."""
        path = CallGraphPath(
            path_id="cp-empty",
            nodes=(),
            edges=(),
        )
        assert len(path.nodes) == 0
        assert len(path.edges) == 0
        d = path.to_dict()
        assert d["nodes"] == []
        assert d["edges"] == []

    def test_confidence_rounding_in_to_dict(self):
        """Test that confidence is rounded to 4 decimal places in to_dict."""
        path = CallGraphPath(
            path_id="cp-round",
            nodes=("a",),
            edges=(),
            confidence=0.123456789,
        )
        d = path.to_dict()
        assert d["confidence"] == 0.1235


# =========================================================================
# TraceResult Tests
# =========================================================================


class TestTraceResult:
    """Tests for the TraceResult frozen dataclass."""

    def test_create_with_paths(self, now_utc: datetime):
        """Test creating a TraceResult with populated paths."""
        path = CallGraphPath(
            path_id="cp-tr001",
            nodes=("agent", "tool", "file"),
            edges=("CALLS", "DEFINED_IN"),
            source_file="src/handler.py",
            confidence=0.9,
        )
        result = TraceResult(
            trace_id="tr-test001",
            event_id="te-event001",
            paths=(path,),
            total_paths_found=1,
            max_depth_reached=2,
            timestamp=now_utc,
            query_latency_ms=5.123,
        )
        assert result.trace_id == "tr-test001"
        assert result.event_id == "te-event001"
        assert len(result.paths) == 1
        assert result.total_paths_found == 1
        assert result.max_depth_reached == 2
        assert result.timestamp == now_utc
        assert result.query_latency_ms == 5.123

    def test_frozen_immutability(self, now_utc: datetime):
        """Test that TraceResult fields cannot be mutated."""
        result = TraceResult(
            trace_id="tr-frozen",
            event_id="te-frozen",
            paths=(),
            total_paths_found=0,
            max_depth_reached=0,
            timestamp=now_utc,
            query_latency_ms=0.0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.trace_id = "tr-mutated"  # type: ignore[misc]

    def test_has_source_true(self, now_utc: datetime):
        """Test has_source is True when a path has source_file."""
        path = CallGraphPath(
            path_id="cp-src",
            nodes=("a",),
            edges=(),
            source_file="src/found.py",
        )
        result = TraceResult(
            trace_id="tr-src",
            event_id="te-src",
            paths=(path,),
            total_paths_found=1,
            max_depth_reached=0,
            timestamp=now_utc,
            query_latency_ms=1.0,
        )
        assert result.has_source is True

    def test_has_source_false_no_source_file(self, now_utc: datetime):
        """Test has_source is False when no path has source_file."""
        path = CallGraphPath(
            path_id="cp-nosrc",
            nodes=("a",),
            edges=(),
        )
        result = TraceResult(
            trace_id="tr-nosrc",
            event_id="te-nosrc",
            paths=(path,),
            total_paths_found=1,
            max_depth_reached=0,
            timestamp=now_utc,
            query_latency_ms=1.0,
        )
        assert result.has_source is False

    def test_has_source_false_empty_paths(self, now_utc: datetime):
        """Test has_source is False when paths is empty."""
        result = TraceResult(
            trace_id="tr-empty",
            event_id="te-empty",
            paths=(),
            total_paths_found=0,
            max_depth_reached=0,
            timestamp=now_utc,
            query_latency_ms=0.0,
        )
        assert result.has_source is False

    def test_best_path_highest_confidence(self, now_utc: datetime):
        """Test best_path returns the path with highest confidence."""
        low = CallGraphPath(path_id="cp-low", nodes=("a",), edges=(), confidence=0.3)
        high = CallGraphPath(path_id="cp-high", nodes=("b",), edges=(), confidence=0.9)
        mid = CallGraphPath(path_id="cp-mid", nodes=("c",), edges=(), confidence=0.6)
        result = TraceResult(
            trace_id="tr-best",
            event_id="te-best",
            paths=(low, high, mid),
            total_paths_found=3,
            max_depth_reached=0,
            timestamp=now_utc,
            query_latency_ms=1.0,
        )
        assert result.best_path is high
        assert result.best_path.confidence == 0.9

    def test_best_path_none_when_empty(self, now_utc: datetime):
        """Test best_path returns None when paths is empty."""
        result = TraceResult(
            trace_id="tr-none",
            event_id="te-none",
            paths=(),
            total_paths_found=0,
            max_depth_reached=0,
            timestamp=now_utc,
            query_latency_ms=0.0,
        )
        assert result.best_path is None

    def test_to_dict_serialization(self, now_utc: datetime):
        """Test to_dict produces expected keys and value types."""
        path = CallGraphPath(
            path_id="cp-ser",
            nodes=("a", "b"),
            edges=("E1",),
            source_file="src/test.py",
            confidence=0.8,
        )
        result = TraceResult(
            trace_id="tr-ser",
            event_id="te-ser",
            paths=(path,),
            total_paths_found=1,
            max_depth_reached=1,
            timestamp=now_utc,
            query_latency_ms=3.456,
        )
        d = result.to_dict()
        assert d["trace_id"] == "tr-ser"
        assert d["event_id"] == "te-ser"
        assert len(d["paths"]) == 1
        assert d["total_paths_found"] == 1
        assert d["max_depth_reached"] == 1
        assert d["timestamp"] == now_utc.isoformat()
        assert d["query_latency_ms"] == 3.456
        assert d["has_source"] is True


# =========================================================================
# GraphTracer Tests
# =========================================================================


class TestGraphTracer:
    """Tests for the GraphTracer mock-mode operations."""

    async def test_trace_event_returns_trace_result(
        self, mock_graph_tracer: GraphTracer
    ):
        """Test that trace_event returns a TraceResult."""
        result = await mock_graph_tracer.trace_event(
            event_id="te-001",
            agent_id="coder-agent",
            tool_name="write_file",
        )
        assert isinstance(result, TraceResult)
        assert result.event_id == "te-001"
        assert result.trace_id.startswith("tr-")

    async def test_trace_event_with_mock_paths(self, mock_graph_tracer: GraphTracer):
        """Test that trace_event returns paths from pre-loaded mock data."""
        result = await mock_graph_tracer.trace_event(
            event_id="te-002",
            agent_id="coder-agent",
            tool_name="write_file",
        )
        assert len(result.paths) == 2
        assert result.total_paths_found == 2
        assert result.has_source is True

    async def test_trace_event_unknown_agent_returns_empty(
        self, mock_graph_tracer: GraphTracer
    ):
        """Test that unknown agent returns empty paths."""
        result = await mock_graph_tracer.trace_event(
            event_id="te-003",
            agent_id="unknown-agent",
        )
        assert len(result.paths) == 0
        assert result.total_paths_found == 0
        assert result.has_source is False

    async def test_add_mock_path_populates_data(self):
        """Test that add_mock_path makes data available for tracing."""
        tracer = GraphTracer(use_mock=True)
        tracer.add_mock_path(
            agent_id="test-agent",
            tool_name="read_file",
            source_file="src/reader.py",
            source_line_start=1,
            source_line_end=10,
        )
        result = await tracer.trace_event(
            event_id="te-add",
            agent_id="test-agent",
            tool_name="read_file",
        )
        assert len(result.paths) == 1
        assert result.paths[0].source_file == "src/reader.py"
        assert result.paths[0].source_line_start == 1
        assert result.paths[0].source_line_end == 10

    async def test_tool_name_filter(self, mock_graph_tracer: GraphTracer):
        """Test that tool_name filter restricts returned paths."""
        # Add a path for a different tool
        mock_graph_tracer.add_mock_path(
            agent_id="coder-agent",
            tool_name="read_file",
            source_file="src/other.py",
            source_line_start=1,
            source_line_end=5,
        )
        result = await mock_graph_tracer.trace_event(
            event_id="te-filter",
            agent_id="coder-agent",
            tool_name="read_file",
        )
        # Only the read_file path should be returned
        assert len(result.paths) == 1
        assert result.paths[0].source_file == "src/other.py"

    async def test_tool_name_none_returns_all(self, mock_graph_tracer: GraphTracer):
        """Test that tool_name=None returns all paths for the agent."""
        result = await mock_graph_tracer.trace_event(
            event_id="te-all",
            agent_id="coder-agent",
        )
        # conftest loads 2 write_file paths for coder-agent
        assert len(result.paths) == 2

    async def test_max_paths_limits_results(self):
        """Test that max_paths limits the number of returned paths."""
        tracer = GraphTracer(use_mock=True, max_paths=2)
        for i in range(5):
            tracer.add_mock_path(
                agent_id="busy-agent",
                tool_name="write_file",
                source_file=f"src/file_{i}.py",
                source_line_start=1,
                source_line_end=10,
            )
        result = await tracer.trace_event(
            event_id="te-limit",
            agent_id="busy-agent",
            tool_name="write_file",
        )
        assert len(result.paths) == 2
        assert result.total_paths_found == 5

    async def test_trace_event_latency_recorded(self, mock_graph_tracer: GraphTracer):
        """Test that query_latency_ms is recorded."""
        result = await mock_graph_tracer.trace_event(
            event_id="te-latency",
            agent_id="coder-agent",
        )
        assert result.query_latency_ms >= 0.0

    async def test_trace_event_timestamp_is_utc(self, mock_graph_tracer: GraphTracer):
        """Test that timestamp is UTC."""
        result = await mock_graph_tracer.trace_event(
            event_id="te-tz",
            agent_id="coder-agent",
        )
        assert result.timestamp.tzinfo is not None

    async def test_trace_event_max_depth_reached(self):
        """Test that max_depth_reached reflects the deepest path."""
        tracer = GraphTracer(use_mock=True)
        tracer.add_mock_path(
            agent_id="deep-agent",
            tool_name="tool",
            source_file="src/deep.py",
            source_line_start=1,
            source_line_end=5,
            nodes=["a", "b", "c", "d", "e"],
            edges=["E1", "E2", "E3", "E4"],
        )
        result = await tracer.trace_event(
            event_id="te-depth",
            agent_id="deep-agent",
        )
        # depth = len(nodes) - 1 = 4
        assert result.max_depth_reached == 4

    def test_default_mock_mode(self):
        """Test that GraphTracer defaults to use_mock=True."""
        tracer = GraphTracer()
        assert tracer.use_mock is True

    def test_custom_max_depth(self):
        """Test that max_depth can be customized."""
        tracer = GraphTracer(max_depth=20)
        assert tracer.max_depth == 20

    def test_custom_max_paths(self):
        """Test that max_paths can be customized."""
        tracer = GraphTracer(max_paths=10)
        assert tracer.max_paths == 10

    async def test_path_confidence_is_0_9_for_mock(self):
        """Test that mock paths have confidence 0.9."""
        tracer = GraphTracer(use_mock=True)
        tracer.add_mock_path(
            agent_id="agent",
            tool_name="tool",
            source_file="f.py",
            source_line_start=1,
            source_line_end=2,
        )
        result = await tracer.trace_event(
            event_id="te-conf",
            agent_id="agent",
            tool_name="tool",
        )
        assert result.paths[0].confidence == 0.9
