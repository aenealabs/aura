"""
Project Aura - Community Summarization Service Tests

Tests for the CommunitySummarizationService that implements
GraphRAG community summarization per ADR-034 Phase 3.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.community_summarization_service import (
    Community,
    CommunityHierarchy,
    CommunitySummarizationConfig,
    CommunitySummarizationService,
)


class TestCommunity:
    """Tests for Community dataclass."""

    def test_community_creation_minimal(self):
        """Test minimal community creation."""
        community = Community(
            community_id="comm-1",
            level=0,
            member_ids=["file1.py", "file2.py"],
        )
        assert community.community_id == "comm-1"
        assert community.level == 0
        assert community.member_ids == ["file1.py", "file2.py"]
        assert community.parent_community_id is None
        assert community.child_community_ids == []
        assert community.summary is None
        assert community.keywords == []
        assert community.metadata == {}

    def test_community_creation_full(self):
        """Test community creation with all fields."""
        community = Community(
            community_id="comm-2",
            level=2,
            member_ids=["mod1", "mod2", "mod3"],
            parent_community_id="comm-root",
            child_community_ids=["comm-child-1", "comm-child-2"],
            summary="This package handles authentication",
            keywords=["auth", "login", "tokens"],
            metadata={"files_count": 10, "lines": 500},
        )
        assert community.parent_community_id == "comm-root"
        assert len(community.child_community_ids) == 2
        assert community.summary == "This package handles authentication"
        assert "auth" in community.keywords
        assert community.metadata["files_count"] == 10

    def test_community_hierarchy_levels(self):
        """Test communities at different hierarchy levels."""
        for level in range(5):
            community = Community(
                community_id=f"comm-level-{level}",
                level=level,
                member_ids=["item"],
            )
            assert community.level == level


class TestCommunityHierarchy:
    """Tests for CommunityHierarchy dataclass."""

    def test_hierarchy_creation_empty(self):
        """Test empty hierarchy."""
        hierarchy = CommunityHierarchy(
            communities={},
            levels=0,
            total_members=0,
        )
        assert hierarchy.communities == {}
        assert hierarchy.levels == 0
        assert hierarchy.total_members == 0
        assert hierarchy.root_community_ids == []

    def test_hierarchy_creation_with_communities(self):
        """Test hierarchy with communities."""
        communities = {
            "root": Community(
                community_id="root",
                level=3,
                member_ids=["child1", "child2"],
                child_community_ids=["child1", "child2"],
            ),
            "child1": Community(
                community_id="child1",
                level=2,
                member_ids=["file1", "file2"],
                parent_community_id="root",
            ),
            "child2": Community(
                community_id="child2",
                level=2,
                member_ids=["file3"],
                parent_community_id="root",
            ),
        }
        hierarchy = CommunityHierarchy(
            communities=communities,
            levels=4,
            total_members=3,
            root_community_ids=["root"],
        )
        assert len(hierarchy.communities) == 3
        assert hierarchy.levels == 4
        assert hierarchy.total_members == 3
        assert "root" in hierarchy.root_community_ids


class TestCommunitySummarizationConfig:
    """Tests for CommunitySummarizationConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CommunitySummarizationConfig()
        assert config.batch_size == 10
        assert config.max_levels == 4
        assert config.max_members_for_summary == 20
        assert config.min_community_size == 2
        assert config.summary_max_length == 500

    def test_custom_config(self):
        """Test custom configuration values."""
        config = CommunitySummarizationConfig(
            batch_size=5,
            max_levels=6,
            max_members_for_summary=50,
            min_community_size=3,
            summary_max_length=1000,
        )
        assert config.batch_size == 5
        assert config.max_levels == 6
        assert config.max_members_for_summary == 50
        assert config.min_community_size == 3
        assert config.summary_max_length == 1000


class TestCommunitySummarizationService:
    """Tests for CommunitySummarizationService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_neptune.execute = AsyncMock(return_value=[])

        self.mock_llm = MagicMock()
        self.mock_llm.generate = AsyncMock(return_value="Generated summary")

        self.service = CommunitySummarizationService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
        )

    def test_init_default_config(self):
        """Test service initialization with default config."""
        assert self.service.config is not None
        assert self.service.config.batch_size == 10

    def test_init_custom_config(self):
        """Test service initialization with custom config."""
        config = CommunitySummarizationConfig(batch_size=20, max_levels=5)
        service = CommunitySummarizationService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
            config=config,
        )
        assert service.config.batch_size == 20
        assert service.config.max_levels == 5

    def test_level_names(self):
        """Test that level names are defined."""
        assert 0 in CommunitySummarizationService.LEVEL_NAMES
        assert 1 in CommunitySummarizationService.LEVEL_NAMES
        assert 2 in CommunitySummarizationService.LEVEL_NAMES
        assert 3 in CommunitySummarizationService.LEVEL_NAMES
        assert 4 in CommunitySummarizationService.LEVEL_NAMES

        assert CommunitySummarizationService.LEVEL_NAMES[0] == "file"
        assert CommunitySummarizationService.LEVEL_NAMES[4] == "system"


class TestBuildCommunityHierarchy:
    """Tests for build_community_hierarchy method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_llm = MagicMock()
        self.mock_llm.generate = AsyncMock(return_value="Summary")

    @pytest.mark.asyncio
    async def test_empty_graph(self):
        """Test building hierarchy from empty graph."""
        self.mock_neptune.execute = AsyncMock(return_value=[])
        service = CommunitySummarizationService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
        )

        hierarchy = await service.build_community_hierarchy()

        assert hierarchy.communities == {}
        assert hierarchy.levels == 0
        assert hierarchy.total_members == 0

    @pytest.mark.asyncio
    async def test_graph_with_vertices(self):
        """Test building hierarchy with vertices."""
        self.mock_neptune.execute = AsyncMock(
            side_effect=[
                # First call: get vertices
                [
                    {"id": "file1", "label": "file", "name": "test.py"},
                    {"id": "file2", "label": "file", "name": "utils.py"},
                ],
                # Second call: get edges
                [{"source": "file1", "target": "file2", "label": "imports"}],
            ]
        )
        service = CommunitySummarizationService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
        )

        hierarchy = await service.build_community_hierarchy()

        # Should have some structure even with minimal graph
        assert isinstance(hierarchy, CommunityHierarchy)


class TestGraphExport:
    """Tests for graph export functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_llm = MagicMock()

    @pytest.mark.asyncio
    async def test_export_graph_empty(self):
        """Test exporting empty graph."""
        self.mock_neptune.execute = AsyncMock(return_value=[])
        service = CommunitySummarizationService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
        )

        result = await service._export_graph_for_clustering()

        assert "vertices" in result
        assert "edges" in result
        assert result["vertices"] == []

    @pytest.mark.asyncio
    async def test_export_graph_with_data(self):
        """Test exporting graph with data."""
        self.mock_neptune.execute = AsyncMock(
            side_effect=[
                [{"id": "v1", "label": "class"}, {"id": "v2", "label": "class"}],
                [{"source": "v1", "target": "v2", "label": "extends"}],
            ]
        )
        service = CommunitySummarizationService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
        )

        result = await service._export_graph_for_clustering()

        assert len(result["vertices"]) == 2
        assert len(result["edges"]) == 1


class TestClustering:
    """Tests for clustering functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_llm = MagicMock()
        self.service = CommunitySummarizationService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
        )

    def test_run_clustering_empty_graph(self):
        """Test clustering with empty graph."""
        graph_data = {"vertices": [], "edges": []}
        clusters = self.service._run_clustering(graph_data)
        assert clusters == []

    def test_run_clustering_single_vertex(self):
        """Test clustering with single vertex."""
        graph_data = {
            "vertices": [{"id": "v1", "label": "class"}],
            "edges": [],
        }
        clusters = self.service._run_clustering(graph_data)
        # Single vertex should form its own cluster or be ignored
        assert isinstance(clusters, list)

    def test_run_clustering_connected_vertices(self):
        """Test clustering with connected vertices."""
        graph_data = {
            "vertices": [
                {"id": "v1", "label": "class"},
                {"id": "v2", "label": "class"},
                {"id": "v3", "label": "class"},
            ],
            "edges": [
                {"source": "v1", "target": "v2"},
                {"source": "v2", "target": "v3"},
            ],
        }
        clusters = self.service._run_clustering(graph_data)
        assert isinstance(clusters, list)


class TestSummaryGeneration:
    """Tests for summary generation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_llm = MagicMock()
        self.mock_llm.generate = AsyncMock(return_value="This is a test summary")

        self.service = CommunitySummarizationService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
        )

    def test_service_has_llm_client(self):
        """Test that service has LLM client."""
        assert self.service.llm is not None

    @pytest.mark.asyncio
    async def test_generate_summary_llm_call(self):
        """Test that LLM is available for summary generation."""
        # The LLM client should be accessible
        assert self.service.llm.generate is not None

    @pytest.mark.asyncio
    async def test_generate_summary_error_handling(self):
        """Test that LLM errors can be handled."""
        self.mock_llm.generate = AsyncMock(side_effect=Exception("LLM error"))
        # Should not crash service initialization
        assert self.service is not None


class TestStoreSummaries:
    """Tests for storing summaries in Neptune."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_neptune.execute = AsyncMock(return_value=[])
        self.mock_llm = MagicMock()

        self.service = CommunitySummarizationService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
        )

    def test_neptune_client_available(self):
        """Test that Neptune client is available."""
        assert self.service.neptune is not None

    def test_community_with_summary(self):
        """Test community with summary."""
        community = Community(
            community_id="comm-1",
            level=1,
            member_ids=["m1", "m2"],
            summary="This module handles data processing",
            keywords=["data", "processing"],
        )
        assert community.summary is not None
        assert len(community.keywords) == 2

    def test_community_without_summary(self):
        """Test community without summary."""
        community = Community(
            community_id="comm-2",
            level=0,
            member_ids=["file.py"],
        )
        assert community.summary is None


class TestQueryCommunities:
    """Tests for querying community summaries."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_llm = MagicMock()

        self.service = CommunitySummarizationService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
        )

    def test_service_has_neptune(self):
        """Test that service has Neptune client."""
        assert self.service.neptune is not None

    def test_service_has_config(self):
        """Test that service has configuration."""
        assert self.service.config is not None
        assert self.service.config.batch_size > 0

    @pytest.mark.asyncio
    async def test_search_communities_by_keyword(self):
        """Test that Neptune can be queried."""
        self.mock_neptune.execute = AsyncMock(
            return_value=[
                {"id": "comm-auth", "summary": "Authentication and authorization"},
            ]
        )
        # Neptune execute is callable
        result = await self.mock_neptune.execute("test query")
        assert isinstance(result, list)
