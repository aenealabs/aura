"""
Tests for Three-Way Hybrid Retrieval Service.

Covers RetrievalResult/FusedResult/RetrievalConfig dataclasses and
ThreeWayRetrievalService for hybrid dense+sparse+graph retrieval with RRF fusion.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.three_way_retrieval_service import (
    FusedResult,
    RetrievalConfig,
    RetrievalResult,
    ThreeWayRetrievalService,
)

# =============================================================================
# RetrievalResult Dataclass Tests
# =============================================================================


class TestRetrievalResult:
    """Tests for RetrievalResult dataclass."""

    def test_create_basic_result(self):
        """Test creating a basic retrieval result."""
        result = RetrievalResult(
            doc_id="doc_123",
            content="Some content here",
            score=0.85,
            source="dense",
        )
        assert result.doc_id == "doc_123"
        assert result.content == "Some content here"
        assert result.score == 0.85
        assert result.source == "dense"

    def test_default_values(self):
        """Test default values for optional fields."""
        result = RetrievalResult(
            doc_id="test",
            content="content",
            score=1.0,
            source="sparse",
        )
        assert result.metadata == {}
        assert result.file_path is None

    def test_full_result(self):
        """Test result with all fields populated."""
        result = RetrievalResult(
            doc_id="doc_456",
            content="Full content",
            score=0.92,
            source="graph",
            metadata={"name": "function_name", "type": "function"},
            file_path="/src/module.py",
        )
        assert result.metadata["name"] == "function_name"
        assert result.file_path == "/src/module.py"

    def test_source_types(self):
        """Test different source types."""
        for source in ["dense", "sparse", "graph"]:
            result = RetrievalResult(
                doc_id="test",
                content="content",
                score=0.5,
                source=source,
            )
            assert result.source == source


# =============================================================================
# FusedResult Dataclass Tests
# =============================================================================


class TestFusedResult:
    """Tests for FusedResult dataclass."""

    def test_create_basic_fused_result(self):
        """Test creating a basic fused result."""
        result = FusedResult(
            doc_id="fused_123",
            content="Fused content",
            rrf_score=0.025,
            source_scores={"dense": 0.015, "sparse": 0.010},
        )
        assert result.doc_id == "fused_123"
        assert result.content == "Fused content"
        assert result.rrf_score == 0.025
        assert result.source_scores["dense"] == 0.015

    def test_default_values(self):
        """Test default values for optional fields."""
        result = FusedResult(
            doc_id="test",
            content="content",
            rrf_score=0.05,
            source_scores={},
        )
        assert result.metadata == {}
        assert result.file_path is None
        assert result.sources_contributed == []

    def test_full_fused_result(self):
        """Test fused result with all fields."""
        result = FusedResult(
            doc_id="doc_789",
            content="Complete content",
            rrf_score=0.045,
            source_scores={"dense": 0.02, "sparse": 0.015, "graph": 0.01},
            metadata={"function_names": ["foo", "bar"]},
            file_path="/src/utils.py",
            sources_contributed=["dense", "sparse", "graph"],
        )
        assert len(result.source_scores) == 3
        assert len(result.sources_contributed) == 3
        assert result.file_path == "/src/utils.py"


# =============================================================================
# RetrievalConfig Dataclass Tests
# =============================================================================


class TestRetrievalConfig:
    """Tests for RetrievalConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RetrievalConfig()

        assert config.sparse_boost == 1.2  # Critical tuned value
        assert config.dense_weight == 1.0
        assert config.graph_weight == 1.0
        assert config.rrf_k == 60
        assert config.index_name == "aura-code-index"
        assert config.dense_field == "embedding"
        assert config.default_k == 50
        assert config.max_graph_terms == 10

    def test_content_fields_default(self):
        """Test default content fields for BM25."""
        config = RetrievalConfig()

        assert "content" in config.content_fields
        assert "file_path" in config.content_fields
        assert "function_names" in config.content_fields

    def test_content_boosts_default(self):
        """Test default field boosts."""
        config = RetrievalConfig()

        assert config.content_boosts["content"] == 1
        assert config.content_boosts["file_path"] == 2
        assert config.content_boosts["function_names"] == 3

    def test_custom_config(self):
        """Test custom configuration."""
        config = RetrievalConfig(
            sparse_boost=1.5,
            dense_weight=0.8,
            graph_weight=0.6,
            rrf_k=40,
            index_name="custom-index",
            default_k=100,
        )
        assert config.sparse_boost == 1.5
        assert config.dense_weight == 0.8
        assert config.rrf_k == 40
        assert config.default_k == 100


# =============================================================================
# ThreeWayRetrievalService Tests
# =============================================================================


class TestThreeWayRetrievalServiceInit:
    """Tests for ThreeWayRetrievalService initialization."""

    def test_initialization(self):
        """Test basic initialization."""
        opensearch = MagicMock()
        neptune = MagicMock()
        embedder = MagicMock()

        service = ThreeWayRetrievalService(
            opensearch_client=opensearch,
            neptune_client=neptune,
            embedding_service=embedder,
        )

        assert service.opensearch == opensearch
        assert service.neptune == neptune
        assert service.embedder == embedder
        assert service.config is not None

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = RetrievalConfig(sparse_boost=2.0, default_k=25)

        service = ThreeWayRetrievalService(
            opensearch_client=MagicMock(),
            neptune_client=MagicMock(),
            embedding_service=MagicMock(),
            config=config,
        )

        assert service.config.sparse_boost == 2.0
        assert service.config.default_k == 25


# =============================================================================
# ThreeWayRetrievalService Retrieval Tests
# =============================================================================


class TestThreeWayRetrievalServiceRetrieval:
    """Tests for ThreeWayRetrievalService retrieval methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.opensearch = AsyncMock()
        self.neptune = AsyncMock()
        self.embedder = AsyncMock()

        # Mock embedding response
        self.embedder.embed_text.return_value = [0.1, 0.2, 0.3] * 256  # 768 dims

        # Mock OpenSearch response
        self.opensearch.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "doc_1",
                        "_score": 0.9,
                        "_source": {
                            "content": "Content 1",
                            "file_path": "/src/a.py",
                            "function_names": ["func1"],
                        },
                    },
                    {
                        "_id": "doc_2",
                        "_score": 0.8,
                        "_source": {
                            "content": "Content 2",
                            "file_path": "/src/b.py",
                            "function_names": ["func2"],
                        },
                    },
                ]
            }
        }

        # Mock Neptune response
        self.neptune.execute.return_value = [
            {
                "id": "graph_1",
                "name": "ClassName",
                "type": "class",
                "content": "class code",
                "file_path": "/src/c.py",
            },
        ]

        self.service = ThreeWayRetrievalService(
            opensearch_client=self.opensearch,
            neptune_client=self.neptune,
            embedding_service=self.embedder,
        )

    @pytest.mark.asyncio
    async def test_retrieve_all_sources(self):
        """Test retrieval from all three sources."""
        results = await self.service.retrieve("search query", k=10)

        assert len(results) > 0
        # Should have called all three retrieval methods
        self.embedder.embed_text.assert_called_once()
        assert self.opensearch.search.call_count >= 1  # At least dense search
        self.neptune.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_dense_only(self):
        """Test retrieval from dense source only."""
        results = await self.service.retrieve(
            "search query",
            include_sources=["dense"],
        )

        assert len(results) > 0
        self.embedder.embed_text.assert_called_once()
        # Neptune should not be called
        self.neptune.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieve_sparse_only(self):
        """Test retrieval from sparse source only."""
        results = await self.service.retrieve(
            "search query",
            include_sources=["sparse"],
        )

        assert len(results) > 0
        # Embedder should not be called for sparse-only
        # (since dense isn't included)

    @pytest.mark.asyncio
    async def test_retrieve_graph_only(self):
        """Test retrieval from graph source only."""
        _results = await self.service.retrieve(
            "ClassName Method search",
            include_sources=["graph"],
        )

        # Graph should be called
        self.neptune.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_handles_source_failure(self):
        """Test that retrieval handles individual source failures."""
        # Make Neptune fail
        self.neptune.execute.side_effect = Exception("Neptune unavailable")

        # Should still return results from other sources
        results = await self.service.retrieve("search query")

        # Should have results from dense/sparse even with graph failure
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieve_with_custom_weights(self):
        """Test retrieval with custom weights."""
        results = await self.service.retrieve(
            "search query",
            weights={"dense": 2.0, "sparse": 1.0, "graph": 0.5},
        )

        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_retrieve_with_custom_k(self):
        """Test retrieval with custom k value."""
        await self.service.retrieve("search query", k=25)

        # Verify k was passed to OpenSearch
        call_args = self.opensearch.search.call_args_list[0]
        body = call_args.kwargs.get("body", call_args[1].get("body", {}))
        assert body.get("size") == 25


# =============================================================================
# RRF Fusion Tests
# =============================================================================


class TestRRFFusion:
    """Tests for Reciprocal Rank Fusion algorithm."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ThreeWayRetrievalService(
            opensearch_client=MagicMock(),
            neptune_client=MagicMock(),
            embedding_service=MagicMock(),
        )

    def test_rrf_single_source(self):
        """Test RRF with single source."""
        results = {
            "dense": [
                RetrievalResult(
                    doc_id="d1", content="content1", score=0.9, source="dense"
                ),
                RetrievalResult(
                    doc_id="d2", content="content2", score=0.8, source="dense"
                ),
            ],
        }

        fused = self.service._reciprocal_rank_fusion(results, weights={"dense": 1.0})

        assert len(fused) == 2
        assert fused[0].doc_id == "d1"  # Higher ranked first
        assert fused[0].rrf_score > fused[1].rrf_score

    def test_rrf_multiple_sources(self):
        """Test RRF with multiple sources."""
        results = {
            "dense": [
                RetrievalResult(
                    doc_id="d1", content="content1", score=0.9, source="dense"
                ),
            ],
            "sparse": [
                RetrievalResult(
                    doc_id="d1", content="content1", score=0.8, source="sparse"
                ),
                RetrievalResult(
                    doc_id="d2", content="content2", score=0.7, source="sparse"
                ),
            ],
        }

        fused = self.service._reciprocal_rank_fusion(
            results, weights={"dense": 1.0, "sparse": 1.0}
        )

        # d1 should be ranked higher (appears in both sources)
        assert len(fused) == 2
        d1_result = next(f for f in fused if f.doc_id == "d1")
        d2_result = next(f for f in fused if f.doc_id == "d2")

        assert d1_result.rrf_score > d2_result.rrf_score
        assert "dense" in d1_result.sources_contributed
        assert "sparse" in d1_result.sources_contributed

    def test_rrf_with_weights(self):
        """Test RRF respects source weights."""
        results = {
            "dense": [
                RetrievalResult(doc_id="d1", content="c1", score=0.9, source="dense"),
            ],
            "sparse": [
                RetrievalResult(doc_id="d2", content="c2", score=0.9, source="sparse"),
            ],
        }

        # Heavy dense weight
        fused = self.service._reciprocal_rank_fusion(
            results, weights={"dense": 10.0, "sparse": 1.0}
        )

        # d1 should win with higher dense weight
        assert fused[0].doc_id == "d1"

    def test_rrf_preserves_content(self):
        """Test RRF preserves content and metadata."""
        results = {
            "dense": [
                RetrievalResult(
                    doc_id="d1",
                    content="Original content",
                    score=0.9,
                    source="dense",
                    file_path="/src/test.py",
                    metadata={"key": "value"},
                ),
            ],
        }

        fused = self.service._reciprocal_rank_fusion(results, weights={"dense": 1.0})

        assert fused[0].content == "Original content"
        assert fused[0].file_path == "/src/test.py"

    def test_rrf_empty_sources(self):
        """Test RRF handles empty sources."""
        results = {
            "dense": [],
            "sparse": [],
            "graph": [],
        }

        fused = self.service._reciprocal_rank_fusion(
            results, weights={"dense": 1.0, "sparse": 1.0, "graph": 1.0}
        )

        assert fused == []


# =============================================================================
# Graph Term Extraction Tests
# =============================================================================


class TestGraphTermExtraction:
    """Tests for graph term extraction."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ThreeWayRetrievalService(
            opensearch_client=MagicMock(),
            neptune_client=MagicMock(),
            embedding_service=MagicMock(),
        )

    def test_extract_capitalized_terms(self):
        """Test extraction of capitalized terms (class/function names)."""
        terms = self.service._extract_graph_terms("Find the UserService class")

        assert "UserService" in terms

    def test_extract_falls_back_to_longer_words(self):
        """Test fallback to longer words if no capitalized."""
        terms = self.service._extract_graph_terms("search authentication module")

        assert len(terms) > 0
        assert any(len(t) > 4 for t in terms)

    def test_extract_limits_terms(self):
        """Test that term count is limited."""
        # Many capitalized words
        query = " ".join([f"Class{i}" for i in range(20)])
        terms = self.service._extract_graph_terms(query)

        assert len(terms) <= self.service.config.max_graph_terms

    def test_extract_removes_punctuation(self):
        """Test that punctuation is removed from terms."""
        terms = self.service._extract_graph_terms("Find UserService, AuthManager!")

        assert all(t.isalnum() or "_" in t for t in terms)

    def test_extract_empty_query(self):
        """Test extraction from empty query."""
        terms = self.service._extract_graph_terms("")

        assert terms == []

    def test_extract_short_words_ignored(self):
        """Test that very short words are ignored."""
        terms = self.service._extract_graph_terms("a b c de")

        assert len(terms) == 0


# =============================================================================
# Statistics Tests
# =============================================================================


class TestRetrievalStats:
    """Tests for retrieval statistics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ThreeWayRetrievalService(
            opensearch_client=MagicMock(),
            neptune_client=MagicMock(),
            embedding_service=MagicMock(),
        )

    def test_stats_empty_results(self):
        """Test stats for empty results."""
        stats = self.service.get_retrieval_stats([])

        assert stats["total"] == 0
        assert stats["avg_score"] == 0
        assert stats["multi_source_count"] == 0

    def test_stats_with_results(self):
        """Test stats with actual results."""
        results = [
            FusedResult(
                doc_id="d1",
                content="c1",
                rrf_score=0.05,
                source_scores={"dense": 0.03, "sparse": 0.02},
                sources_contributed=["dense", "sparse"],
            ),
            FusedResult(
                doc_id="d2",
                content="c2",
                rrf_score=0.03,
                source_scores={"dense": 0.03},
                sources_contributed=["dense"],
            ),
            FusedResult(
                doc_id="d3",
                content="c3",
                rrf_score=0.02,
                source_scores={"graph": 0.02},
                sources_contributed=["graph"],
            ),
        ]

        stats = self.service.get_retrieval_stats(results)

        assert stats["total"] == 3
        assert stats["max_score"] == 0.05
        assert stats["min_score"] == 0.02
        assert stats["avg_score"] == pytest.approx(0.0333, rel=0.01)
        assert stats["multi_source_count"] == 1
        assert stats["multi_source_pct"] == pytest.approx(33.33, rel=0.1)

    def test_stats_source_coverage(self):
        """Test source coverage in stats."""
        results = [
            FusedResult(
                doc_id="d1",
                content="c1",
                rrf_score=0.1,
                source_scores={},
                sources_contributed=["dense", "sparse"],
            ),
            FusedResult(
                doc_id="d2",
                content="c2",
                rrf_score=0.1,
                source_scores={},
                sources_contributed=["dense"],
            ),
        ]

        stats = self.service.get_retrieval_stats(results)

        assert stats["source_coverage"]["dense"] == 2
        assert stats["source_coverage"]["sparse"] == 1
        assert stats["source_coverage"]["graph"] == 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestThreeWayRetrievalIntegration:
    """Integration tests for three-way retrieval."""

    def setup_method(self):
        """Set up test fixtures with realistic mocks."""
        self.opensearch = AsyncMock()
        self.neptune = AsyncMock()
        self.embedder = AsyncMock()

        self.embedder.embed_text.return_value = [0.1] * 768

        # Setup realistic OpenSearch responses
        def make_opensearch_response(is_dense=True):
            return {
                "hits": {
                    "hits": [
                        {
                            "_id": f"doc_{i}",
                            "_score": 1.0 / (i + 1),
                            "_source": {
                                "content": f"Content from {'dense' if is_dense else 'sparse'} {i}",
                                "file_path": f"/src/module{i}.py",
                                "function_names": [f"func{i}"],
                            },
                        }
                        for i in range(5)
                    ]
                }
            }

        self.opensearch.search.return_value = make_opensearch_response()

        self.neptune.execute.return_value = [
            {
                "id": "graph_1",
                "name": "ServiceClass",
                "type": "class",
                "content": "class code",
                "file_path": "/src/service.py",
            },
            {
                "id": "graph_2",
                "name": "helperFunc",
                "type": "function",
                "content": "func code",
                "file_path": "/src/helpers.py",
            },
        ]

        self.service = ThreeWayRetrievalService(
            opensearch_client=self.opensearch,
            neptune_client=self.neptune,
            embedding_service=self.embedder,
        )

    @pytest.mark.asyncio
    async def test_full_retrieval_workflow(self):
        """Test complete retrieval workflow."""
        # Execute retrieval
        results = await self.service.retrieve(
            "ServiceClass implementation",
            k=10,
        )

        # Verify results
        assert len(results) > 0
        assert all(isinstance(r, FusedResult) for r in results)
        assert all(r.rrf_score > 0 for r in results)

        # Results should be sorted by score
        scores = [r.rrf_score for r in results]
        assert scores == sorted(scores, reverse=True)

        # Get stats
        stats = self.service.get_retrieval_stats(results)
        assert stats["total"] > 0

    @pytest.mark.asyncio
    async def test_retrieve_with_reranking(self):
        """Test retrieval with reranking placeholder."""
        results = await self.service.retrieve_with_reranking(
            "search query",
            k=50,
            rerank_top_n=10,
        )

        assert len(results) <= 10


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.mock_opensearch = MagicMock()
        self.mock_neptune = MagicMock()
        self.mock_embedding = MagicMock()

        self.service = ThreeWayRetrievalService(
            opensearch_client=self.mock_opensearch,
            neptune_client=self.mock_neptune,
            embedding_service=self.mock_embedding,
        )

    @pytest.mark.asyncio
    async def test_graph_retrieval_empty_key_terms(self):
        """Test _graph_retrieval with empty key terms returns empty list - covers line 293."""
        # Mock _extract_graph_terms to return empty list
        with patch.object(self.service, "_extract_graph_terms", return_value=[]):
            result = await self.service._graph_retrieval("", k=10)
            assert result == []

    @pytest.mark.asyncio
    async def test_hybrid_retrieve_with_failed_source(self):
        """Test hybrid_retrieve handles source failure gracefully - covers lines 187-188."""
        self.mock_embedding.embed_text = AsyncMock(return_value=[0.1] * 768)

        # Make sparse retrieval raise an exception
        async def mock_sparse_fail(*args, **kwargs):
            raise Exception("Sparse retrieval failed")

        async def mock_dense_success(*args, **kwargs):
            return [
                RetrievalResult(
                    doc_id="dense_1",
                    content="Dense result",
                    score=0.9,
                    source="dense",
                )
            ]

        async def mock_graph_success(*args, **kwargs):
            return [
                RetrievalResult(
                    doc_id="graph_1",
                    content="Graph result",
                    score=0.8,
                    source="graph",
                )
            ]

        with (
            patch.object(self.service, "_dense_retrieval", mock_dense_success),
            patch.object(self.service, "_sparse_retrieval", mock_sparse_fail),
            patch.object(self.service, "_graph_retrieval", mock_graph_success),
        ):
            # Should not raise, should handle the failure gracefully
            results = await self.service.retrieve("test query", k=10)

            # Should still get results from the working sources
            assert isinstance(results, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
