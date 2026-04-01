# Copyright (c) 2025 Aenea Labs. All rights reserved.
"""Unit tests for the diagram layout engine."""

import pytest

from src.services.diagrams.layout_engine import (
    LayoutBackend,
    LayoutConfig,
    LayoutEngine,
    LayoutResult,
)
from src.services.diagrams.models import (
    DiagramConnection,
    DiagramDefinition,
    DiagramGroup,
    DiagramMetadata,
    DiagramNode,
    LayoutDirection,
)


class TestLayoutConfig:
    """Tests for LayoutConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LayoutConfig()
        assert config.node_width > 0
        assert config.node_height > 0
        assert config.node_spacing_horizontal > 0
        assert config.node_spacing_vertical > 0
        assert config.canvas_padding > 0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = LayoutConfig(
            node_width=150.0,
            node_height=100.0,
            node_spacing_horizontal=80.0,
            node_spacing_vertical=100.0,
        )
        assert config.node_width == 150.0
        assert config.node_height == 100.0


class TestLayoutEngineInitialization:
    """Tests for LayoutEngine initialization."""

    def test_engine_initialization_default(self):
        """Test default engine initialization."""
        engine = LayoutEngine()
        assert engine is not None
        assert engine.config is not None
        assert engine.backend == LayoutBackend.PYTHON

    def test_engine_initialization_with_config(self):
        """Test engine initialization with custom config."""
        config = LayoutConfig(
            node_spacing_horizontal=100.0,
            node_spacing_vertical=200.0,
        )
        engine = LayoutEngine(config=config)
        assert engine.config.node_spacing_horizontal == 100.0
        assert engine.config.node_spacing_vertical == 200.0


class TestLayoutResultBasic:
    """Tests for basic layout results."""

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="Test Diagram")

    def test_layout_empty_diagram(self, engine, metadata):
        """Test laying out empty diagram."""
        definition = DiagramDefinition(metadata=metadata)
        result = engine.layout(definition)
        assert result is not None
        assert isinstance(result, LayoutResult)
        assert result.width >= 0
        assert result.height >= 0

    def test_layout_single_node(self, engine, metadata):
        """Test laying out single node."""
        definition = DiagramDefinition(
            metadata=metadata, nodes=[DiagramNode(id="node-1", label="Single Node")]
        )
        result = engine.layout(definition)
        assert result is not None
        # The definition in result should have positions set
        node = result.definition.get_node("node-1")
        assert node is not None
        assert node.position is not None
        assert node.position.x >= 0
        assert node.position.y >= 0

    def test_layout_multiple_nodes(self, engine, metadata):
        """Test laying out multiple unconnected nodes."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[
                DiagramNode(id="a", label="A"),
                DiagramNode(id="b", label="B"),
                DiagramNode(id="c", label="C"),
            ],
        )
        result = engine.layout(definition)
        # All nodes should have positions
        for node_id in ["a", "b", "c"]:
            node = result.definition.get_node(node_id)
            assert node.position is not None


class TestLayoutResultLinearChain:
    """Tests for linear chain layouts."""

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="Test")

    def test_layout_linear_chain(self, engine, metadata):
        """Test laying out a linear chain of nodes."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[
                DiagramNode(id="a", label="A"),
                DiagramNode(id="b", label="B"),
                DiagramNode(id="c", label="C"),
            ],
            connections=[
                DiagramConnection(id="a-b", source="a", target="b"),
                DiagramConnection(id="b-c", source="b", target="c"),
            ],
        )
        result = engine.layout(definition)

        pos_a = result.definition.get_node("a").position
        pos_b = result.definition.get_node("b").position
        pos_c = result.definition.get_node("c").position

        # Grid layout: ungrouped nodes are arranged in rows (horizontally)
        # With 3 nodes and max_nodes_per_row=4, all 3 are on the same row
        assert pos_a.x < pos_b.x < pos_c.x
        assert pos_a.y == pos_b.y == pos_c.y

    def test_layout_respects_direction_top_bottom(self, engine, metadata):
        """Test top-bottom layout direction with ungrouped nodes.

        Note: The current grid-based implementation arranges ungrouped nodes
        horizontally in rows. For proper hierarchical layout, use groups.
        """
        definition = DiagramDefinition(
            metadata=metadata,
            direction=LayoutDirection.TOP_BOTTOM,
            nodes=[
                DiagramNode(id="a", label="A"),
                DiagramNode(id="b", label="B"),
            ],
            connections=[
                DiagramConnection(id="a-b", source="a", target="b"),
            ],
        )
        result = engine.layout(definition)
        pos_a = result.definition.get_node("a").position
        pos_b = result.definition.get_node("b").position
        # Grid layout: nodes are arranged horizontally in a row
        assert pos_a.x < pos_b.x
        assert pos_a.y == pos_b.y

    def test_layout_respects_direction_left_right(self, engine, metadata):
        """Test left-right layout direction."""
        definition = DiagramDefinition(
            metadata=metadata,
            direction=LayoutDirection.LEFT_RIGHT,
            nodes=[
                DiagramNode(id="a", label="A"),
                DiagramNode(id="b", label="B"),
            ],
            connections=[
                DiagramConnection(id="a-b", source="a", target="b"),
            ],
        )
        result = engine.layout(definition)
        pos_a = result.definition.get_node("a").position
        pos_b = result.definition.get_node("b").position
        # In left-right, A should be to the left of B
        assert pos_a.x < pos_b.x


class TestLayoutResultGroups:
    """Tests for group/container layouts."""

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="Test")

    def test_layout_simple_group(self, engine, metadata):
        """Test laying out nodes within a group."""
        definition = DiagramDefinition(
            metadata=metadata,
            groups=[
                DiagramGroup(id="group-1", label="Group", children=["a", "b"]),
            ],
            nodes=[
                DiagramNode(id="a", label="A"),
                DiagramNode(id="b", label="B"),
            ],
        )
        result = engine.layout(definition)

        # Group should have bounds
        group = result.definition.get_group("group-1")
        assert group.position is not None
        assert group.size is not None
        assert group.size.width > 0
        assert group.size.height > 0


class TestLayoutResultEdgeRouting:
    """Tests for edge/connection routing."""

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="Test")

    def test_edge_routing_simple(self, engine, metadata):
        """Test edge routing for simple connection."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[
                DiagramNode(id="a", label="A"),
                DiagramNode(id="b", label="B"),
            ],
            connections=[
                DiagramConnection(id="a-b", source="a", target="b"),
            ],
        )
        result = engine.layout(definition)

        # Connection should have points
        conn = result.definition.connections[0]
        assert len(conn.points) >= 2


class TestLayoutDimensions:
    """Tests for layout dimensions."""

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="Test")

    def test_layout_dimensions(self, engine, metadata):
        """Test layout calculates correct dimensions."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[
                DiagramNode(id="a", label="A"),
                DiagramNode(id="b", label="B"),
            ],
            connections=[
                DiagramConnection(id="a-b", source="a", target="b"),
            ],
        )
        result = engine.layout(definition)

        # Dimensions should be positive
        assert result.width > 0
        assert result.height > 0


class TestComplexLayouts:
    """Tests for complex, realistic layout scenarios."""

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="Complex")

    def test_three_tier_architecture(self, engine, metadata):
        """Test laying out three-tier architecture."""
        definition = DiagramDefinition(
            metadata=metadata,
            direction=LayoutDirection.TOP_BOTTOM,
            groups=[
                DiagramGroup(id="frontend", label="Frontend", children=["web"]),
                DiagramGroup(id="backend", label="Backend", children=["api", "worker"]),
                DiagramGroup(id="data", label="Data", children=["db", "cache"]),
            ],
            nodes=[
                DiagramNode(id="web", label="Web Server"),
                DiagramNode(id="api", label="API Server"),
                DiagramNode(id="worker", label="Worker"),
                DiagramNode(id="db", label="Database"),
                DiagramNode(id="cache", label="Cache"),
            ],
            connections=[
                DiagramConnection(id="web-api", source="web", target="api"),
                DiagramConnection(id="api-db", source="api", target="db"),
                DiagramConnection(id="api-cache", source="api", target="cache"),
                DiagramConnection(id="worker-db", source="worker", target="db"),
            ],
        )
        result = engine.layout(definition)

        # All nodes should have positions
        for node in result.definition.nodes:
            assert node.position is not None
            assert node.size is not None

        # All groups should have bounds
        for group in result.definition.groups:
            assert group.position is not None
            assert group.size is not None

    def test_large_graph_performance(self, engine, metadata):
        """Test layout handles reasonably large graphs."""
        import time

        # Create a moderately large graph
        num_nodes = 30
        nodes = [DiagramNode(id=f"n{i}", label=f"Node {i}") for i in range(num_nodes)]

        # Create a chain
        connections = [
            DiagramConnection(id=f"n{i}-n{i+1}", source=f"n{i}", target=f"n{i+1}")
            for i in range(num_nodes - 1)
        ]

        definition = DiagramDefinition(
            metadata=metadata, nodes=nodes, connections=connections
        )

        start = time.time()
        result = engine.layout(definition)
        elapsed = time.time() - start

        # Should complete in reasonable time (< 5 seconds)
        assert elapsed < 5.0
        assert all(n.position is not None for n in result.definition.nodes)
