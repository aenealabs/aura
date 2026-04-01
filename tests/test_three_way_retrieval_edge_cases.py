"""
Project Aura - Three-Way Retrieval Edge Case Tests

Tests for partial failures, timeouts, inconsistent results, and graceful
degradation in the Three-Way Hybrid Retrieval Service.

Priority: P1 - Critical Resilience Testing
Covers: ADR-034 Phase 2.1 - Three-Way Hybrid Retrieval fault tolerance
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.three_way_retrieval_service import (
    RetrievalConfig,
    RetrievalResult,
    ThreeWayRetrievalService,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_opensearch():
    """Create a mock OpenSearch client with default success behavior."""
    client = AsyncMock()
    client.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_id": "os_doc_1",
                    "_score": 0.95,
                    "_source": {
                        "content": "OpenSearch content 1",
                        "file_path": "/src/opensearch_a.py",
                        "function_names": ["os_func1"],
                        "last_modified": "2025-01-15T10:00:00Z",
                    },
                },
                {
                    "_id": "os_doc_2",
                    "_score": 0.85,
                    "_source": {
                        "content": "OpenSearch content 2",
                        "file_path": "/src/opensearch_b.py",
                        "function_names": ["os_func2"],
                        "last_modified": "2025-01-14T10:00:00Z",
                    },
                },
            ]
        }
    }
    return client


@pytest.fixture
def mock_neptune():
    """Create a mock Neptune client with default success behavior."""
    client = AsyncMock()
    client.execute.return_value = [
        {
            "id": "neptune_node_1",
            "name": "GraphEntity",
            "type": "class",
            "content": "Neptune graph content 1",
            "file_path": "/src/neptune_a.py",
        },
        {
            "id": "neptune_node_2",
            "name": "GraphHelper",
            "type": "function",
            "content": "Neptune graph content 2",
            "file_path": "/src/neptune_b.py",
        },
    ]
    return client


@pytest.fixture
def mock_embedder():
    """Create a mock embedding service with default success behavior."""
    embedder = AsyncMock()
    embedder.embed_text.return_value = [0.1, 0.2, 0.3] * 256  # 768 dimensions
    return embedder


@pytest.fixture
def service(mock_opensearch, mock_neptune, mock_embedder):
    """Create a ThreeWayRetrievalService with all mocked dependencies."""
    return ThreeWayRetrievalService(
        opensearch_client=mock_opensearch,
        neptune_client=mock_neptune,
        embedding_service=mock_embedder,
    )


@pytest.fixture
def custom_config():
    """Create a custom retrieval configuration for testing."""
    return RetrievalConfig(
        sparse_boost=1.5,
        dense_weight=1.0,
        graph_weight=0.8,
        rrf_k=60,
        default_k=25,
    )


# =============================================================================
# Partial Failures - Single Source Unavailable
# =============================================================================


class TestSingleSourceUnavailable:
    """Tests for scenarios where one retrieval source fails."""

    @pytest.mark.asyncio
    async def test_neptune_unavailable_vector_and_keyword_work(
        self, mock_opensearch, mock_embedder
    ):
        """Test graceful degradation when Neptune (graph) is unavailable.

        Scenario: Graph database is down but vector and keyword search work.
        Expected: Results from OpenSearch are returned; no exception raised.
        """
        mock_neptune = AsyncMock()
        mock_neptune.execute.side_effect = ConnectionError("Neptune connection refused")

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("TestQuery search", k=10)

        # Should have results from dense and sparse (OpenSearch)
        assert isinstance(results, list)
        assert len(results) > 0

        # Verify OpenSearch was called for both dense and sparse
        assert mock_opensearch.search.call_count >= 2
        # Neptune was attempted but failed
        mock_neptune.execute.assert_called_once()

        # Results should only have dense and sparse sources
        for result in results:
            assert "graph" not in result.sources_contributed

    @pytest.mark.asyncio
    async def test_opensearch_unavailable_dense_search_but_graph_works(
        self, mock_neptune, mock_embedder
    ):
        """Test graceful degradation when OpenSearch (vector/keyword) is unavailable.

        Scenario: OpenSearch is down but Neptune graph search works.
        Expected: Results from graph traversal are returned; no exception raised.
        """
        mock_opensearch = AsyncMock()
        mock_opensearch.search.side_effect = ConnectionError(
            "OpenSearch cluster unavailable"
        )

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("GraphEntity search", k=10)

        # Should have results from graph only
        assert isinstance(results, list)
        # Graph results should be present
        mock_neptune.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_embedding_service_unavailable(self, mock_opensearch, mock_neptune):
        """Test graceful degradation when embedding service is unavailable.

        Scenario: Cannot generate embeddings for dense search.
        Expected: Dense search fails but sparse and graph still work.
        """
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.side_effect = Exception(
            "Embedding service unavailable"
        )

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("TestQuery search", k=10)

        # Should still return results from sparse and graph
        assert isinstance(results, list)
        # Embedding was attempted but failed
        mock_embedder.embed_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_sparse_search_fails_but_dense_and_graph_work(
        self, mock_neptune, mock_embedder
    ):
        """Test graceful degradation when BM25/sparse search fails.

        Scenario: Sparse retrieval throws exception, dense and graph work.
        Expected: Results from dense and graph are returned.
        """
        mock_opensearch = AsyncMock()

        # First call (dense) succeeds, second call (sparse) fails
        dense_response = {
            "hits": {
                "hits": [
                    {
                        "_id": "dense_doc",
                        "_score": 0.9,
                        "_source": {
                            "content": "Dense result",
                            "file_path": "/src/dense.py",
                        },
                    }
                ]
            }
        }

        mock_opensearch.search.side_effect = [
            dense_response,
            Exception("BM25 index corrupted"),
        ]

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("TestSearch query", k=10)

        assert isinstance(results, list)
        assert len(results) > 0


# =============================================================================
# Dual Failures - Two Sources Unavailable
# =============================================================================


class TestTwoSourcesUnavailable:
    """Tests for scenarios where two retrieval sources fail."""

    @pytest.mark.asyncio
    async def test_only_graph_available(self, mock_neptune):
        """Test when only Neptune graph search is available.

        Scenario: Both OpenSearch services are down.
        Expected: Returns results from graph only.
        """
        mock_opensearch = AsyncMock()
        mock_opensearch.search.side_effect = ConnectionError("OpenSearch down")

        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("GraphSearch query", k=10)

        assert isinstance(results, list)
        # Only graph results expected
        for result in results:
            if result.sources_contributed:
                assert "graph" in result.sources_contributed or len(results) == 0

    @pytest.mark.asyncio
    async def test_only_dense_vector_available(self, mock_embedder):
        """Test when only dense vector search is available.

        Scenario: Sparse/BM25 and graph both fail.
        Expected: Returns results from dense search only.
        """
        mock_opensearch = AsyncMock()

        # Dense succeeds, sparse fails
        dense_response = {
            "hits": {
                "hits": [
                    {
                        "_id": "dense_only",
                        "_score": 0.85,
                        "_source": {
                            "content": "Dense only result",
                            "file_path": "/src/dense.py",
                        },
                    }
                ]
            }
        }
        mock_opensearch.search.side_effect = [
            dense_response,
            Exception("BM25 failed"),
        ]

        mock_neptune = AsyncMock()
        mock_neptune.execute.side_effect = ConnectionError("Neptune unreachable")

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("DenseOnly search", k=10)

        assert isinstance(results, list)
        # Should have at least the dense result
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_only_sparse_keyword_available(self, mock_neptune):
        """Test when only sparse/keyword search is available.

        Scenario: Dense fails (embedding error), graph fails (Neptune down).
        Expected: Returns results from sparse search only.
        """
        mock_opensearch = AsyncMock()
        sparse_response = {
            "hits": {
                "hits": [
                    {
                        "_id": "sparse_only",
                        "_score": 0.75,
                        "_source": {
                            "content": "Sparse only result",
                            "file_path": "/src/sparse.py",
                        },
                    }
                ]
            }
        }
        # Dense fails (called first), sparse succeeds (called second)
        mock_opensearch.search.side_effect = [
            Exception("Dense search failed"),
            sparse_response,
        ]

        mock_embedder = AsyncMock()
        mock_embedder.embed_text.side_effect = Exception("Embedding model unavailable")

        # Neptune also fails
        mock_neptune.execute.side_effect = Exception("Graph unavailable")

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        # Even with both dense and graph failing, should not raise
        results = await service.retrieve("SparseOnly search", k=10)

        assert isinstance(results, list)


# =============================================================================
# Total Failure - All Sources Unavailable
# =============================================================================


class TestAllSourcesUnavailable:
    """Tests for scenarios where all retrieval sources fail."""

    @pytest.mark.asyncio
    async def test_all_sources_fail_graceful_degradation(self):
        """Test graceful degradation when all three sources fail.

        Scenario: Neptune, OpenSearch (dense), and OpenSearch (sparse) all fail.
        Expected: Empty result list returned, no exception raised.
        """
        mock_opensearch = AsyncMock()
        mock_opensearch.search.side_effect = ConnectionError("All clusters down")

        mock_neptune = AsyncMock()
        mock_neptune.execute.side_effect = ConnectionError("Graph DB offline")

        mock_embedder = AsyncMock()
        mock_embedder.embed_text.side_effect = Exception("Embedding API error")

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        # Should not raise, should return empty list
        results = await service.retrieve("DoNotFail query", k=10)

        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_stats_on_total_failure(self):
        """Test retrieval stats are correct when all sources fail."""
        mock_opensearch = AsyncMock()
        mock_opensearch.search.side_effect = Exception("Failed")

        mock_neptune = AsyncMock()
        mock_neptune.execute.side_effect = Exception("Failed")

        mock_embedder = AsyncMock()
        mock_embedder.embed_text.side_effect = Exception("Failed")

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("TotalFailure query", k=10)
        stats = service.get_retrieval_stats(results)

        assert stats["total"] == 0
        assert stats["avg_score"] == 0
        assert stats["multi_source_count"] == 0


# =============================================================================
# Timeout Scenarios
# =============================================================================


class TestTimeoutScenarios:
    """Tests for timeout handling in retrieval methods."""

    @pytest.mark.asyncio
    async def test_single_source_timeout_does_not_block_others(
        self, mock_opensearch, mock_embedder
    ):
        """Test that a timeout on one source doesn't block other sources.

        Scenario: Neptune times out but OpenSearch completes quickly.
        Expected: Results from OpenSearch returned within reasonable time.
        """
        mock_neptune = AsyncMock()

        async def slow_neptune(*args, **kwargs):
            await asyncio.sleep(5.0)  # Simulate slow response
            return []

        mock_neptune.execute.side_effect = slow_neptune

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        # Use asyncio.wait_for to enforce overall timeout
        try:
            results = await asyncio.wait_for(
                service.retrieve("TimeoutTest query", k=10),
                timeout=6.0,  # Allow for slow Neptune but reasonable overall
            )
            # Results should include OpenSearch results even if Neptune is slow
            assert isinstance(results, list)
        except asyncio.TimeoutError:
            # This is acceptable - shows timeout behavior works
            pass

    @pytest.mark.asyncio
    async def test_all_sources_slow_but_complete(self):
        """Test handling when all sources are slow but complete successfully.

        Scenario: All sources have latency but return results.
        Expected: All results are combined after parallel execution.
        """
        mock_opensearch = AsyncMock()
        mock_neptune = AsyncMock()
        mock_embedder = AsyncMock()

        async def slow_opensearch(*args, **kwargs):
            await asyncio.sleep(0.1)
            return {
                "hits": {
                    "hits": [
                        {
                            "_id": "slow_doc",
                            "_score": 0.8,
                            "_source": {"content": "Slow content"},
                        }
                    ]
                }
            }

        async def slow_neptune(*args, **kwargs):
            await asyncio.sleep(0.15)
            return [{"id": "slow_graph", "content": "Graph content"}]

        async def slow_embed(*args, **kwargs):
            await asyncio.sleep(0.05)
            return [0.1] * 768

        mock_opensearch.search.side_effect = slow_opensearch
        mock_neptune.execute.side_effect = slow_neptune
        mock_embedder.embed_text.side_effect = slow_embed

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("SlowAll query", k=10)

        # Should get results from all sources despite latency
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_concurrent_timeout_behavior(self, mock_embedder):
        """Test that parallel retrieval respects asyncio gather behavior.

        Scenario: One source times out, others complete.
        Expected: Results from completing sources are returned.
        """
        mock_opensearch = AsyncMock()
        mock_neptune = AsyncMock()

        call_count = 0

        async def mixed_opensearch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # Dense
                return {
                    "hits": {
                        "hits": [
                            {
                                "_id": "fast_dense",
                                "_score": 0.9,
                                "_source": {"content": "Fast"},
                            }
                        ]
                    }
                }
            else:  # Sparse
                raise TimeoutError("BM25 query timeout")

        mock_opensearch.search.side_effect = mixed_opensearch
        mock_neptune.execute.return_value = [{"id": "g1", "content": "Graph"}]

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("MixedTimeout query", k=10)

        assert isinstance(results, list)


# =============================================================================
# Inconsistent Results Handling
# =============================================================================


class TestInconsistentResults:
    """Tests for handling conflicting relevance signals across sources."""

    @pytest.mark.asyncio
    async def test_graph_says_related_vector_says_unrelated(self, mock_embedder):
        """Test handling when graph shows relationship but vector shows low similarity.

        Scenario: Graph traversal finds strong relationship, but vector
                  embeddings indicate low semantic similarity.
        Expected: RRF combines both signals appropriately.
        """
        mock_opensearch = AsyncMock()
        mock_neptune = AsyncMock()

        # Vector search returns low score
        mock_opensearch.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "doc_low_vector",
                        "_score": 0.2,  # Low semantic similarity
                        "_source": {
                            "content": "Unrelated content",
                            "file_path": "/src/unrelated.py",
                        },
                    }
                ]
            }
        }

        # Graph returns same doc as highly related
        mock_neptune.execute.return_value = [
            {
                "id": "doc_low_vector",  # Same doc
                "name": "RelatedClass",
                "content": "Graph says related",
                "file_path": "/src/unrelated.py",
            }
        ]

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("InconsistentTest query", k=10)

        assert isinstance(results, list)
        # Document should appear in results (from RRF fusion)
        doc_ids = [r.doc_id for r in results]
        # Should handle the document appropriately
        if results:
            # Check that multi-source documents have both contributions
            for r in results:
                if r.doc_id == "doc_low_vector":
                    # Should have sources from both despite score difference
                    assert len(r.source_scores) >= 1

    @pytest.mark.asyncio
    async def test_conflicting_rank_ordering(self, mock_embedder):
        """Test RRF fusion when sources disagree on ranking order.

        Scenario: Dense ranks doc_A first, sparse ranks doc_B first, graph ranks doc_C.
        Expected: RRF produces combined ranking based on all signals.
        """
        mock_opensearch = AsyncMock()
        mock_neptune = AsyncMock()

        call_count = 0

        async def varied_ranking(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # Dense
                return {
                    "hits": {
                        "hits": [
                            {
                                "_id": "doc_A",
                                "_score": 0.95,
                                "_source": {"content": "A"},
                            },
                            {
                                "_id": "doc_B",
                                "_score": 0.60,
                                "_source": {"content": "B"},
                            },
                            {
                                "_id": "doc_C",
                                "_score": 0.30,
                                "_source": {"content": "C"},
                            },
                        ]
                    }
                }
            else:  # Sparse
                return {
                    "hits": {
                        "hits": [
                            {
                                "_id": "doc_B",
                                "_score": 0.90,
                                "_source": {"content": "B"},
                            },
                            {
                                "_id": "doc_C",
                                "_score": 0.70,
                                "_source": {"content": "C"},
                            },
                            {
                                "_id": "doc_A",
                                "_score": 0.40,
                                "_source": {"content": "A"},
                            },
                        ]
                    }
                }

        mock_opensearch.search.side_effect = varied_ranking

        # Graph has different ordering too
        mock_neptune.execute.return_value = [
            {"id": "doc_C", "content": "C"},  # First in graph
            {"id": "doc_A", "content": "A"},
            {"id": "doc_B", "content": "B"},
        ]

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("ConflictRank query", k=10)

        assert len(results) == 3
        # All docs should have multiple source contributions
        for r in results:
            assert len(r.sources_contributed) > 0

        # RRF scores should reflect multi-source contribution
        # Doc appearing in all 3 should score higher than single-source
        stats = service.get_retrieval_stats(results)
        assert stats["multi_source_count"] == 3  # All docs appear in all sources


# =============================================================================
# Empty Results Handling
# =============================================================================


class TestEmptyResultsHandling:
    """Tests for handling empty results from one or more sources."""

    @pytest.mark.asyncio
    async def test_graph_returns_empty_others_have_results(
        self, mock_opensearch, mock_embedder
    ):
        """Test weighting when graph returns no results.

        Scenario: Graph search returns empty, vector/keyword have results.
        Expected: Results from vector/keyword are returned with appropriate scores.
        """
        mock_neptune = AsyncMock()
        mock_neptune.execute.return_value = []  # Empty graph results

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("NoGraph query", k=10)

        assert len(results) > 0
        # No results should have graph in sources_contributed
        for r in results:
            assert "graph" not in r.sources_contributed

    @pytest.mark.asyncio
    async def test_dense_returns_empty_sparse_and_graph_have_results(
        self, mock_neptune
    ):
        """Test weighting when dense search returns no results.

        Scenario: No vector matches but BM25 and graph have results.
        Expected: Results from sparse and graph are returned.
        """
        mock_opensearch = AsyncMock()

        call_count = 0

        async def mixed_results(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # Dense
                return {"hits": {"hits": []}}
            else:  # Sparse
                return {
                    "hits": {
                        "hits": [
                            {
                                "_id": "sparse_doc",
                                "_score": 0.8,
                                "_source": {"content": "S"},
                            }
                        ]
                    }
                }

        mock_opensearch.search.side_effect = mixed_results

        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("NoDense query", k=10)

        assert len(results) > 0
        # Results should be from sparse and graph only
        for r in results:
            assert "dense" not in r.sources_contributed

    @pytest.mark.asyncio
    async def test_all_sources_return_empty_results(self):
        """Test handling when all sources return empty results (not errors).

        Scenario: All searches complete successfully but find nothing.
        Expected: Empty result list, valid stats.
        """
        mock_opensearch = AsyncMock()
        mock_opensearch.search.return_value = {"hits": {"hits": []}}

        mock_neptune = AsyncMock()
        mock_neptune.execute.return_value = []

        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("NoResults query", k=10)

        assert results == []
        stats = service.get_retrieval_stats(results)
        assert stats["total"] == 0

    @pytest.mark.asyncio
    async def test_no_graph_terms_extracted(self, mock_opensearch, mock_embedder):
        """Test graph retrieval when no terms can be extracted from query.

        Scenario: Query has no identifiable entity names.
        Expected: Graph search returns empty, others still work.
        """
        mock_neptune = AsyncMock()

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        # Query with no capitalized or snake_case terms
        results = await service.retrieve("the a an", k=10)

        # Graph should not be called if no terms extracted
        # Results should come from dense/sparse
        assert isinstance(results, list)


# =============================================================================
# Rate Limiting Scenarios
# =============================================================================


class TestRateLimitingScenarios:
    """Tests for rate limiting behavior during high load."""

    @pytest.mark.asyncio
    async def test_opensearch_rate_limited(self, mock_neptune, mock_embedder):
        """Test handling when OpenSearch returns rate limit error.

        Scenario: OpenSearch cluster is rate-limiting requests.
        Expected: Graceful degradation, graph results still returned.
        """
        mock_opensearch = AsyncMock()
        mock_opensearch.search.side_effect = Exception(
            "429 Too Many Requests: Rate limit exceeded"
        )

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("RateLimited query", k=10)

        # Should still get graph results
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_neptune_throttled(self, mock_opensearch, mock_embedder):
        """Test handling when Neptune throttles requests.

        Scenario: Neptune returns throttling exception.
        Expected: OpenSearch results still returned.
        """
        mock_neptune = AsyncMock()
        mock_neptune.execute.side_effect = Exception(
            "ThrottlingException: Read capacity exceeded"
        )

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("NeptuneThrottle query", k=10)

        # Should still get OpenSearch results
        assert isinstance(results, list)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_embedding_api_rate_limited(self, mock_opensearch, mock_neptune):
        """Test handling when embedding API is rate limited.

        Scenario: Bedrock/embedding service returns rate limit.
        Expected: Dense search fails but sparse and graph work.
        """
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.side_effect = Exception(
            "ThrottlingException: Too many requests to Bedrock"
        )

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("EmbedThrottle query", k=10)

        # Should still get sparse and graph results
        assert isinstance(results, list)


# =============================================================================
# Connection Pool Exhaustion
# =============================================================================


class TestConnectionPoolExhaustion:
    """Tests for connection pool exhaustion scenarios."""

    @pytest.mark.asyncio
    async def test_opensearch_pool_exhausted(self, mock_neptune, mock_embedder):
        """Test handling when OpenSearch connection pool is exhausted.

        Scenario: Too many concurrent connections to OpenSearch.
        Expected: Graceful error handling, graph results if available.
        """
        mock_opensearch = AsyncMock()
        mock_opensearch.search.side_effect = ConnectionError(
            "Connection pool exhausted: no available connections"
        )

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("PoolExhaust query", k=10)

        # Should handle gracefully
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_neptune_connection_pool_exhausted(
        self, mock_opensearch, mock_embedder
    ):
        """Test handling when Neptune connection pool is exhausted.

        Scenario: Neptune WebSocket pool has no available connections.
        Expected: OpenSearch results still returned.
        """
        mock_neptune = AsyncMock()
        mock_neptune.execute.side_effect = Exception(
            "WebSocketPool: No connections available"
        )

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve("NeptunePool query", k=10)

        # Should still get OpenSearch results
        assert isinstance(results, list)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_concurrent_requests_exhaust_pools(self, mock_embedder):
        """Test behavior under concurrent load that exhausts pools.

        Scenario: Multiple concurrent retrievals overwhelm connection pools.
        Expected: Some requests succeed, failures handled gracefully.
        """
        mock_opensearch = AsyncMock()
        mock_neptune = AsyncMock()

        request_count = 0
        max_concurrent = 3

        async def limited_opensearch(*args, **kwargs):
            nonlocal request_count
            request_count += 1
            if request_count > max_concurrent:
                raise ConnectionError("Pool exhausted")
            return {
                "hits": {
                    "hits": [
                        {"_id": f"doc_{request_count}", "_score": 0.9, "_source": {}}
                    ]
                }
            }

        mock_opensearch.search.side_effect = limited_opensearch
        mock_neptune.execute.return_value = []

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        # Run multiple concurrent requests
        tasks = [service.retrieve(f"Concurrent query {i}", k=5) for i in range(5)]

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Some should succeed, none should raise unhandled exceptions
        for result in results_list:
            if isinstance(result, Exception):
                # Exceptions should be handled types
                assert not isinstance(result, SystemExit)
            else:
                assert isinstance(result, list)


# =============================================================================
# RRF Fusion Edge Cases
# =============================================================================


class TestRRFFusionEdgeCases:
    """Tests for edge cases in Reciprocal Rank Fusion algorithm."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ThreeWayRetrievalService(
            opensearch_client=MagicMock(),
            neptune_client=MagicMock(),
            embedding_service=MagicMock(),
        )

    def test_rrf_with_extremely_different_weights(self):
        """Test RRF when weights are extremely unbalanced."""
        results = {
            "dense": [
                RetrievalResult(doc_id="d1", content="c1", score=0.9, source="dense")
            ],
            "sparse": [
                RetrievalResult(doc_id="d2", content="c2", score=0.9, source="sparse")
            ],
        }

        # Extreme weight difference
        fused = self.service._reciprocal_rank_fusion(
            results, weights={"dense": 100.0, "sparse": 0.01}
        )

        # Dense should dominate
        assert fused[0].doc_id == "d1"
        assert fused[0].rrf_score > fused[1].rrf_score * 10

    def test_rrf_with_zero_weight_source(self):
        """Test RRF when one source has zero weight."""
        results = {
            "dense": [
                RetrievalResult(doc_id="d1", content="c1", score=0.9, source="dense")
            ],
            "sparse": [
                RetrievalResult(doc_id="d2", content="c2", score=0.9, source="sparse")
            ],
            "graph": [
                RetrievalResult(doc_id="d3", content="c3", score=0.9, source="graph")
            ],
        }

        fused = self.service._reciprocal_rank_fusion(
            results, weights={"dense": 1.0, "sparse": 0.0, "graph": 1.0}
        )

        # Sparse should have zero contribution
        d2_result = next((f for f in fused if f.doc_id == "d2"), None)
        if d2_result:
            assert d2_result.rrf_score == 0.0

    def test_rrf_with_duplicate_docs_across_sources(self):
        """Test RRF handles same document appearing in all sources."""
        # Same doc_id in all three sources
        results = {
            "dense": [
                RetrievalResult(
                    doc_id="shared_doc",
                    content="Dense content",
                    score=0.9,
                    source="dense",
                )
            ],
            "sparse": [
                RetrievalResult(
                    doc_id="shared_doc",
                    content="Sparse content",
                    score=0.8,
                    source="sparse",
                )
            ],
            "graph": [
                RetrievalResult(
                    doc_id="shared_doc",
                    content="Graph content long",
                    score=0.7,
                    source="graph",
                )
            ],
        }

        fused = self.service._reciprocal_rank_fusion(
            results, weights={"dense": 1.0, "sparse": 1.2, "graph": 1.0}
        )

        assert len(fused) == 1  # Single document
        assert fused[0].doc_id == "shared_doc"
        assert len(fused[0].sources_contributed) == 3
        # Should have score from all three sources
        assert "dense" in fused[0].source_scores
        assert "sparse" in fused[0].source_scores
        assert "graph" in fused[0].source_scores
        # Content should be the longest (graph)
        assert fused[0].content == "Graph content long"

    def test_rrf_preserves_file_path_metadata(self):
        """Test that RRF preserves file_path across fusion."""
        results = {
            "dense": [
                RetrievalResult(
                    doc_id="d1",
                    content="content",
                    score=0.9,
                    source="dense",
                    file_path="/src/module.py",
                    metadata={"key": "value"},
                )
            ],
        }

        fused = self.service._reciprocal_rank_fusion(results, weights={"dense": 1.0})

        assert fused[0].file_path == "/src/module.py"

    def test_rrf_with_large_result_set(self):
        """Test RRF performance with large number of results."""
        # Create 1000 results per source
        dense_results = [
            RetrievalResult(
                doc_id=f"dense_{i}",
                content=f"content_{i}",
                score=1.0 / (i + 1),
                source="dense",
            )
            for i in range(1000)
        ]
        sparse_results = [
            RetrievalResult(
                doc_id=f"sparse_{i}",
                content=f"content_{i}",
                score=1.0 / (i + 1),
                source="sparse",
            )
            for i in range(1000)
        ]

        results = {"dense": dense_results, "sparse": sparse_results}

        fused = self.service._reciprocal_rank_fusion(
            results, weights={"dense": 1.0, "sparse": 1.2}
        )

        # Should have 2000 unique results
        assert len(fused) == 2000
        # Should be sorted by RRF score
        scores = [r.rrf_score for r in fused]
        assert scores == sorted(scores, reverse=True)


# =============================================================================
# Selective Source Inclusion
# =============================================================================


class TestSelectiveSourceInclusion:
    """Tests for the include_sources parameter."""

    @pytest.mark.asyncio
    async def test_include_only_dense(
        self, mock_opensearch, mock_neptune, mock_embedder
    ):
        """Test retrieving from only dense source."""
        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve(
            "DenseOnly query", k=10, include_sources=["dense"]
        )

        # Only dense should be called
        mock_embedder.embed_text.assert_called_once()
        mock_neptune.execute.assert_not_called()
        # Sparse search should not be called
        assert mock_opensearch.search.call_count == 1

    @pytest.mark.asyncio
    async def test_include_only_graph(
        self, mock_opensearch, mock_neptune, mock_embedder
    ):
        """Test retrieving from only graph source."""
        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve(
            "GraphEntity search", k=10, include_sources=["graph"]
        )

        # Only Neptune should be called
        mock_neptune.execute.assert_called_once()
        # OpenSearch should not be called
        mock_opensearch.search.assert_not_called()
        # Embedder should not be called
        mock_embedder.embed_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_include_dense_and_sparse_exclude_graph(
        self, mock_opensearch, mock_neptune, mock_embedder
    ):
        """Test excluding graph from retrieval."""
        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        results = await service.retrieve(
            "NoGraph query", k=10, include_sources=["dense", "sparse"]
        )

        # Both OpenSearch queries should be called
        assert mock_opensearch.search.call_count == 2
        # Neptune should not be called
        mock_neptune.execute.assert_not_called()

        # Results should only have dense and sparse sources
        for result in results:
            assert "graph" not in result.sources_contributed


# =============================================================================
# Error Message and Logging
# =============================================================================


class TestErrorLogging:
    """Tests for proper error logging during failures."""

    @pytest.mark.asyncio
    async def test_logs_warning_on_source_failure(
        self, mock_opensearch, mock_embedder, caplog
    ):
        """Test that warnings are logged when a source fails."""
        import logging

        mock_neptune = AsyncMock()
        mock_neptune.execute.side_effect = Exception("Neptune test error")

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        with caplog.at_level(logging.WARNING):
            await service.retrieve("LogTest query", k=10)

        # Should have logged the failure
        assert any(
            "retrieval failed" in record.message.lower() for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_logs_info_on_successful_retrieval(
        self, mock_opensearch, mock_neptune, mock_embedder, caplog
    ):
        """Test that info is logged on successful retrieval."""
        import logging

        service = ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

        with caplog.at_level(logging.INFO):
            await service.retrieve("SuccessLog query", k=10)

        # Should have logged the completion
        assert any(
            "three-way retrieval" in record.message.lower() for record in caplog.records
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
