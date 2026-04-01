"""Tests for ServiceBoundaryDetector (ADR-056)."""

import platform
from unittest.mock import MagicMock

import pytest

from src.services.documentation.exceptions import InsufficientDataError
from src.services.documentation.service_boundary_detector import (
    ServiceBoundaryDetector,
    create_service_boundary_detector,
)
from src.services.documentation.types import ServiceBoundary

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestServiceBoundaryDetector:
    """Tests for ServiceBoundaryDetector."""

    @pytest.fixture
    def mock_neptune_service(self):
        """Create a mock Neptune service."""
        service = MagicMock()
        service.is_mock = True
        return service

    @pytest.fixture
    def detector(self):
        """Create a ServiceBoundaryDetector for testing."""
        return ServiceBoundaryDetector(neptune_service=None)

    def test_initialization(self, detector):
        """Test detector initialization."""
        assert detector is not None
        assert detector.neptune is None
        assert detector.resolution == 1.0
        assert detector.min_community_size == 3
        assert detector.seed == 42

    def test_initialization_with_neptune(self, mock_neptune_service):
        """Test detector initialization with Neptune service."""
        detector = ServiceBoundaryDetector(neptune_service=mock_neptune_service)
        assert detector.neptune == mock_neptune_service

    def test_custom_configuration(self, mock_neptune_service):
        """Test detector with custom configuration."""
        detector = ServiceBoundaryDetector(
            neptune_service=mock_neptune_service,
            resolution=1.5,
            min_community_size=5,
            seed=123,
        )
        assert detector.resolution == 1.5
        assert detector.min_community_size == 5
        assert detector.seed == 123

    @pytest.mark.asyncio
    async def test_detect_boundaries_with_mock_data(self):
        """Test boundary detection with mock graph data."""
        detector = ServiceBoundaryDetector()

        # Set up mock data with clear communities
        nodes = {
            "a": {"type": "class", "file_path": "auth/handler.py"},
            "b": {"type": "class", "file_path": "auth/service.py"},
            "c": {"type": "class", "file_path": "auth/validator.py"},
            "d": {"type": "class", "file_path": "auth/token.py"},
            "e": {"type": "class", "file_path": "auth/config.py"},
            "x": {"type": "class", "file_path": "user/handler.py"},
            "y": {"type": "class", "file_path": "user/service.py"},
            "z": {"type": "class", "file_path": "user/repo.py"},
            "w": {"type": "class", "file_path": "user/model.py"},
            "v": {"type": "class", "file_path": "user/utils.py"},
        }
        edges = [
            # Cluster 1: auth
            ("a", "b", {"weight": 1.0}),
            ("b", "c", {"weight": 1.0}),
            ("c", "d", {"weight": 1.0}),
            ("d", "e", {"weight": 1.0}),
            ("a", "c", {"weight": 0.5}),
            # Cluster 2: user
            ("x", "y", {"weight": 1.0}),
            ("y", "z", {"weight": 1.0}),
            ("z", "w", {"weight": 1.0}),
            ("w", "v", {"weight": 1.0}),
            ("x", "z", {"weight": 0.5}),
            # Weak connection between clusters
            ("c", "x", {"weight": 0.1}),
        ]
        detector.set_mock_data(nodes, edges)

        boundaries = await detector.detect_boundaries("test-repo", min_service_size=3)

        assert isinstance(boundaries, list)
        assert len(boundaries) >= 1
        assert all(isinstance(b, ServiceBoundary) for b in boundaries)

    @pytest.mark.asyncio
    async def test_detect_boundaries_returns_service_boundaries(self):
        """Test that detect_boundaries returns ServiceBoundary objects."""
        detector = ServiceBoundaryDetector()

        # Set up mock data
        nodes = {f"node-{i}": {"type": "class"} for i in range(6)}
        edges = [(f"node-{i}", f"node-{i+1}", {"weight": 1.0}) for i in range(5)]
        detector.set_mock_data(nodes, edges)

        boundaries = await detector.detect_boundaries("test-repo", min_service_size=3)

        for boundary in boundaries:
            assert hasattr(boundary, "boundary_id")
            assert hasattr(boundary, "name")
            assert hasattr(boundary, "node_ids")
            assert hasattr(boundary, "confidence")
            assert isinstance(boundary.node_ids, list)
            assert 0 <= boundary.confidence <= 1

    @pytest.mark.asyncio
    async def test_detect_boundaries_limits_services(self):
        """Test that service count is limited."""
        detector = ServiceBoundaryDetector()

        # Set up mock data with many potential communities
        nodes = {f"node-{i}": {"type": "class"} for i in range(30)}
        edges = []
        # Create groups of 5 nodes each
        for i in range(0, 30, 5):
            for j in range(i, min(i + 5, 30) - 1):
                edges.append((f"node-{j}", f"node-{j+1}", {"weight": 1.0}))
        detector.set_mock_data(nodes, edges)

        boundaries = await detector.detect_boundaries(
            "test-repo", min_service_size=3, max_services=2
        )

        assert len(boundaries) <= 2

    @pytest.mark.asyncio
    async def test_detect_boundaries_insufficient_data(self):
        """Test boundary detection with insufficient data."""
        detector = ServiceBoundaryDetector()

        # Set up mock data with too few nodes
        nodes = {"a": {"type": "class"}, "b": {"type": "class"}}
        edges = [("a", "b", {"weight": 1.0})]
        detector.set_mock_data(nodes, edges)

        with pytest.raises(InsufficientDataError) as exc_info:
            await detector.detect_boundaries("test-repo", min_service_size=5)

        assert exc_info.value.confidence == 0.0


class TestCreateServiceBoundaryDetector:
    """Tests for the factory function."""

    def test_create_default(self):
        """Test factory creates detector with defaults."""
        detector = create_service_boundary_detector()
        assert detector is not None
        assert detector.neptune is None
        assert detector.resolution == 1.0

    def test_create_with_neptune_service(self):
        """Test factory with Neptune service."""
        mock_neptune = MagicMock()
        detector = create_service_boundary_detector(
            neptune_service=mock_neptune,
        )
        assert detector.neptune == mock_neptune

    def test_create_with_custom_resolution(self):
        """Test factory with custom resolution."""
        detector = create_service_boundary_detector(resolution=2.0)
        assert detector.resolution == 2.0


class TestLouvainCommunityDetection:
    """Tests for Louvain community detection algorithm usage."""

    @pytest.fixture
    def detector(self):
        """Create detector for Louvain tests."""
        return ServiceBoundaryDetector()

    def test_louvain_on_simple_graph(self, detector):
        """Test Louvain on a simple graph."""
        import networkx as nx

        # Create two distinct clusters
        graph = nx.Graph()
        # Cluster 1
        graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        # Cluster 2
        graph.add_edges_from([("x", "y"), ("y", "z"), ("z", "x")])
        # Weak connection between clusters
        graph.add_edge("c", "x")

        communities = detector._detect_communities(graph)

        assert len(communities) >= 1
        # Each community should be a set of nodes
        for community in communities:
            assert isinstance(community, (set, frozenset))

    def test_louvain_empty_graph(self, detector):
        """Test Louvain on empty graph."""
        import networkx as nx

        graph = nx.Graph()
        communities = detector._detect_communities(graph)

        assert communities == []

    def test_louvain_single_node(self, detector):
        """Test Louvain on single node graph."""
        import networkx as nx

        graph = nx.Graph()
        graph.add_node("single")

        communities = detector._detect_communities(graph)

        # Single node forms its own community or empty
        assert len(communities) <= 1


class TestEdgeWeights:
    """Tests for edge weight calculation."""

    @pytest.fixture
    def detector(self):
        """Create detector for edge weight tests."""
        return ServiceBoundaryDetector()

    def test_get_edge_weight_calls(self, detector):
        """Test weight for 'calls' relationship."""
        weight = detector._get_edge_weight("calls")
        assert weight == 1.0

    def test_get_edge_weight_imports(self, detector):
        """Test weight for 'imports' relationship."""
        weight = detector._get_edge_weight("imports")
        assert weight == 0.5

    def test_get_edge_weight_inherits(self, detector):
        """Test weight for 'inherits' relationship."""
        weight = detector._get_edge_weight("inherits")
        assert weight == 0.8

    def test_get_edge_weight_implements(self, detector):
        """Test weight for 'implements' relationship."""
        weight = detector._get_edge_weight("implements")
        assert weight == 0.8

    def test_get_edge_weight_depends_on(self, detector):
        """Test weight for 'depends_on' relationship."""
        weight = detector._get_edge_weight("depends_on")
        assert weight == 0.6

    def test_get_edge_weight_references(self, detector):
        """Test weight for 'references' relationship."""
        weight = detector._get_edge_weight("references")
        assert weight == 0.3

    def test_get_edge_weight_unknown(self, detector):
        """Test weight for unknown relationship type."""
        weight = detector._get_edge_weight("unknown_relationship")
        assert weight == 0.5  # Default weight


class TestMockGraphBehavior:
    """Tests for mock graph data handling."""

    @pytest.fixture
    def detector(self):
        """Create detector for mock graph tests."""
        return ServiceBoundaryDetector()

    def test_build_graph_from_mock_adds_nodes(self, detector):
        """Test that mock data nodes are added to graph."""
        nodes = {
            "a": {"type": "class", "name": "ClassA"},
            "b": {"type": "function", "name": "func_b"},
        }
        edges = []
        detector.set_mock_data(nodes, edges)

        graph = detector._build_graph_from_mock()

        assert "a" in graph.nodes
        assert "b" in graph.nodes
        assert graph.nodes["a"]["type"] == "class"
        assert graph.nodes["b"]["name"] == "func_b"

    def test_build_graph_from_mock_handles_duplicate_edges(self, detector):
        """Test that duplicate edges increment weight."""
        nodes = {"a": {}, "b": {}}
        edges = [
            ("a", "b", {"weight": 1.0}),
            ("a", "b", {"weight": 0.5}),  # Duplicate edge
        ]
        detector.set_mock_data(nodes, edges)

        graph = detector._build_graph_from_mock()

        # Weight should be incremented
        assert graph["a"]["b"]["weight"] == 1.5

    def test_build_graph_from_mock_default_weight(self, detector):
        """Test that edges without weight get default of 1.0."""
        nodes = {"a": {}, "b": {}}
        edges = [("a", "b", {})]  # No weight specified
        detector.set_mock_data(nodes, edges)

        graph = detector._build_graph_from_mock()

        assert graph["a"]["b"]["weight"] == 1.0


class TestDirectoryRefinement:
    """Tests for directory-based community refinement."""

    @pytest.fixture
    def detector(self):
        """Create detector for refinement tests."""
        return ServiceBoundaryDetector()

    def test_refine_with_directories_single_directory(self, detector):
        """Test refinement keeps communities in single directory."""
        import networkx as nx

        G = nx.Graph()
        G.add_node("a", file_path="auth/handler.py")
        G.add_node("b", file_path="auth/service.py")
        G.add_node("c", file_path="auth/utils.py")

        communities = [{"a", "b", "c"}]
        refined = detector._refine_with_directories(communities, G)

        assert len(refined) == 1
        assert refined[0] == {"a", "b", "c"}

    def test_refine_with_directories_multiple_directories(self, detector):
        """Test refinement with nodes from multiple directories."""
        import networkx as nx

        G = nx.Graph()
        G.add_node("a", file_path="auth/handler.py")
        G.add_node("b", file_path="user/service.py")
        G.add_node("c", file_path="api/endpoint.py")
        G.add_node("d", file_path="db/model.py")

        communities = [{"a", "b", "c", "d"}]
        refined = detector._refine_with_directories(communities, G)

        # More than 2 directories - still kept as single community
        assert len(refined) == 1

    def test_refine_with_directories_no_file_paths(self, detector):
        """Test refinement handles nodes without file paths."""
        import networkx as nx

        G = nx.Graph()
        G.add_node("a", type="class")
        G.add_node("b", type="class")

        communities = [{"a", "b"}]
        refined = detector._refine_with_directories(communities, G)

        assert len(refined) == 1

    def test_refine_with_directories_empty_file_path(self, detector):
        """Test refinement handles empty file paths."""
        import networkx as nx

        G = nx.Graph()
        G.add_node("a", file_path="")
        G.add_node("b", file_path="src/service.py")

        communities = [{"a", "b"}]
        refined = detector._refine_with_directories(communities, G)

        assert len(refined) == 1


class TestServiceBoundaryBuilding:
    """Tests for building ServiceBoundary objects."""

    @pytest.fixture
    def detector(self):
        """Create detector for boundary building tests."""
        return ServiceBoundaryDetector()

    def test_generate_service_name_from_directory(self, detector):
        """Test name generation from common directory."""
        import networkx as nx

        G = nx.Graph()
        G.add_node("a", file_path="authentication/handler.py")
        G.add_node("b", file_path="authentication/service.py")
        G.add_node("c", file_path="authentication/utils.py")

        name = detector._generate_service_name(["a", "b", "c"], G, 0)

        assert "Authentication" in name

    def test_generate_service_name_fallback(self, detector):
        """Test name generation falls back to index."""
        import networkx as nx

        G = nx.Graph()
        G.add_node("a", type="class")  # No file_path

        name = detector._generate_service_name(["a"], G, 0)

        assert name == "Service 1"

    def test_generate_service_description_with_types(self, detector):
        """Test description generation with node types."""
        import networkx as nx

        G = nx.Graph()
        G.add_node("a", type="class")
        G.add_node("b", type="class")
        G.add_node("c", type="function")

        desc = detector._generate_service_description(["a", "b", "c"], G)

        assert "class" in desc
        assert "function" in desc

    def test_generate_service_description_fallback(self, detector):
        """Test description fallback when nodes not in graph."""
        import networkx as nx

        G = nx.Graph()
        # Don't add any nodes to the graph - this triggers the fallback

        desc = detector._generate_service_description(["a", "b"], G)

        # Falls back to component count when nodes aren't in graph
        assert "2" in desc and "components" in desc

    def test_find_entry_points(self, detector):
        """Test finding entry points."""
        import networkx as nx

        G = nx.Graph()
        G.add_edge("external", "entry")
        G.add_edge("entry", "internal1")
        G.add_edge("internal1", "internal2")

        community = {"entry", "internal1", "internal2"}
        entry_points = detector._find_entry_points(community, G)

        assert "entry" in entry_points

    def test_find_entry_points_limit(self, detector):
        """Test entry points are limited to 10."""
        import networkx as nx

        G = nx.Graph()
        # Create 15 entry points
        for i in range(15):
            G.add_edge("external", f"entry_{i}")

        community = {f"entry_{i}" for i in range(15)}
        entry_points = detector._find_entry_points(community, G)

        assert len(entry_points) <= 10

    @pytest.mark.asyncio
    async def test_build_service_boundaries_calculates_modularity(self, detector):
        """Test that boundary confidence is based on modularity."""
        nodes = {
            "a": {"type": "class"},
            "b": {"type": "class"},
            "c": {"type": "class"},
            "d": {"type": "class"},
            "e": {"type": "class"},
            "x": {"type": "class"},
        }
        edges = [
            # Tight cluster
            ("a", "b", {"weight": 1.0}),
            ("b", "c", {"weight": 1.0}),
            ("c", "d", {"weight": 1.0}),
            ("d", "e", {"weight": 1.0}),
            ("a", "c", {"weight": 1.0}),
            ("a", "d", {"weight": 1.0}),
            # Weak external connection
            ("e", "x", {"weight": 0.1}),
        ]
        detector.set_mock_data(nodes, edges)

        boundaries = await detector.detect_boundaries("test-repo", min_service_size=3)

        # Should have confidence based on internal vs external edges
        assert all(b.confidence >= 0.5 for b in boundaries)
        assert all(b.confidence <= 0.95 for b in boundaries)


class TestLouvainExceptionHandling:
    """Tests for Louvain algorithm exception handling."""

    def test_louvain_fallback_to_connected_components(self):
        """Test fallback to connected components on Louvain failure."""
        from unittest.mock import patch

        import networkx as nx

        detector = ServiceBoundaryDetector()
        G = nx.Graph()
        G.add_edges_from([("a", "b"), ("c", "d")])

        # Mock louvain_communities to raise an exception
        with patch(
            "src.services.documentation.service_boundary_detector.louvain_communities",
            side_effect=Exception("Louvain failed"),
        ):
            communities = detector._detect_communities(G)

        # Should fall back to connected components
        assert len(communities) == 2
        assert any("a" in c and "b" in c for c in communities)
        assert any("c" in c and "d" in c for c in communities)

    def test_detect_communities_without_networkx(self):
        """Test that _detect_communities returns empty without networkx."""
        from unittest.mock import patch

        import networkx as nx

        detector = ServiceBoundaryDetector()
        G = nx.Graph()
        G.add_edges_from([("a", "b"), ("c", "d")])

        # Mock NETWORKX_AVAILABLE to False
        with patch(
            "src.services.documentation.service_boundary_detector.NETWORKX_AVAILABLE",
            False,
        ):
            communities = detector._detect_communities(G)

        # Should return empty list
        assert communities == []


class TestNeptuneIntegration:
    """Tests for Neptune service integration."""

    @pytest.mark.asyncio
    async def test_query_nodes_without_neptune(self):
        """Test _query_nodes returns empty without Neptune service."""
        detector = ServiceBoundaryDetector(neptune_service=None)
        nodes = await detector._query_nodes("test-repo")
        assert nodes == []

    @pytest.mark.asyncio
    async def test_query_edges_without_neptune(self):
        """Test _query_edges returns empty without Neptune service."""
        detector = ServiceBoundaryDetector(neptune_service=None)
        edges = await detector._query_edges("test-repo")
        assert edges == []

    @pytest.mark.asyncio
    async def test_query_nodes_with_neptune(self):
        """Test _query_nodes calls Neptune search_by_name."""
        mock_neptune = MagicMock()
        mock_neptune.search_by_name.return_value = [
            {"entity_id": "a", "name": "ClassA", "type": "class"},
            {"entity_id": "b", "name": "func_b", "type": "function"},
        ]

        detector = ServiceBoundaryDetector(neptune_service=mock_neptune)
        nodes = await detector._query_nodes("test-repo")

        assert len(nodes) == 2
        mock_neptune.search_by_name.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_nodes_neptune_exception(self):
        """Test _query_nodes handles Neptune exception."""
        mock_neptune = MagicMock()
        mock_neptune.search_by_name.side_effect = Exception("Neptune error")

        detector = ServiceBoundaryDetector(neptune_service=mock_neptune)
        nodes = await detector._query_nodes("test-repo")

        # Should return empty list on error
        assert nodes == []

    @pytest.mark.asyncio
    async def test_query_nodes_neptune_returns_none(self):
        """Test _query_nodes handles Neptune returning None."""
        mock_neptune = MagicMock()
        mock_neptune.search_by_name.return_value = None

        detector = ServiceBoundaryDetector(neptune_service=mock_neptune)
        nodes = await detector._query_nodes("test-repo")

        assert nodes == []
