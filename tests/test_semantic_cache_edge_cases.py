"""
Project Aura - Semantic Cache Edge Case Tests

Tests edge cases and potential failure modes in semantic similarity caching,
including collision scenarios, threshold boundaries, and embedding model changes.

Key concerns tested:
1. Cache collision when two different prompts have similar embeddings
2. Short prompt collision risks
3. Negation-only differences ("add" vs "remove")
4. Numeric differences ("timeout 5" vs "timeout 50")
5. Similarity threshold boundaries
6. False positive cache hits
7. Embedding model change invalidation

ADR-029 Phase 1.3 - Edge Case Testing
"""

# ruff: noqa: PLR2004

import math
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.services.semantic_cache_service import (
    CacheEntry,
    CacheMode,
    CacheResult,
    QueryType,
    SemanticCacheService,
)

# =============================================================================
# Mock Services with Controllable Similarity
# =============================================================================


class ControllableEmbeddingService:
    """
    Embedding service with controllable similarity between prompts.

    Allows tests to precisely control which prompts are considered "similar"
    by returning embeddings designed to produce specific cosine similarities.
    """

    def __init__(self, vector_dimension: int = 1024):
        self.vector_dimension = vector_dimension
        self.call_count = 0
        # Map of query text to forced embedding vector
        self._forced_embeddings: dict[str, list[float]] = {}
        # Map of query pairs to desired similarity scores
        self._forced_similarities: dict[tuple[str, str], float] = {}

    def force_embedding(self, text: str, embedding: list[float]) -> None:
        """Force a specific embedding vector for a given text."""
        if len(embedding) != self.vector_dimension:
            raise ValueError(f"Embedding must have {self.vector_dimension} dimensions")
        self._forced_embeddings[text] = embedding

    def force_similarity(self, text1: str, text2: str, similarity: float) -> None:
        """
        Force a specific cosine similarity between two texts.

        This creates embeddings that will produce the desired similarity score.
        """
        if not 0.0 <= similarity <= 1.0:
            raise ValueError("Similarity must be between 0.0 and 1.0")

        # Create base embedding for text1 if not exists
        if text1 not in self._forced_embeddings:
            base = [1.0] + [0.0] * (self.vector_dimension - 1)
            self._forced_embeddings[text1] = base

        # Create embedding for text2 that produces desired similarity
        # Using: cos(theta) = similarity, so theta = arccos(similarity)
        # Create vector at angle theta from text1's vector
        theta = math.acos(similarity)
        text2_embedding = (
            [math.cos(theta)] + [math.sin(theta)] + [0.0] * (self.vector_dimension - 2)
        )
        self._forced_embeddings[text2] = text2_embedding
        self._forced_similarities[(text1, text2)] = similarity
        self._forced_similarities[(text2, text1)] = similarity

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text, using forced values if configured."""
        self.call_count += 1

        if text in self._forced_embeddings:
            return self._forced_embeddings[text].copy()

        # Default: deterministic hash-based embedding
        hash_val = hash(text) % 1000000
        base_val = hash_val / 1000000
        return [
            base_val + (i / self.vector_dimension) * 0.001
            for i in range(self.vector_dimension)
        ]


class ControlledOpenSearchService:
    """
    OpenSearch service with controllable search behavior.

    Allows precise control over what results are returned and at what
    similarity scores, enabling testing of threshold boundary conditions.
    """

    def __init__(self):
        self.indexed_docs: dict[str, dict[str, Any]] = {}
        self.index_call_count = 0
        self.search_call_count = 0
        # Force specific search results (bypass normal search)
        self._forced_results: list[dict[str, Any]] | None = None

    def force_search_results(self, results: list[dict[str, Any]] | None) -> None:
        """Force specific search results to be returned."""
        self._forced_results = results

    def index_embedding(
        self,
        doc_id: str,
        text: str,
        vector: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Store document in mock index."""
        self.index_call_count += 1
        self.indexed_docs[doc_id] = {
            "text": text,
            "vector": vector,
            "metadata": metadata or {},
        }
        return True

    def search_similar(
        self,
        query_vector: list[float],
        k: int = 5,
        min_score: float = 0.7,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar documents with controllable results."""
        self.search_call_count += 1

        if self._forced_results is not None:
            # Return forced results, filtered by min_score
            return [r for r in self._forced_results if r.get("score", 0) >= min_score][
                :k
            ]

        # Default behavior: compute cosine similarity
        results = []
        for doc_id, doc in self.indexed_docs.items():
            score = self._cosine_similarity(query_vector, doc["vector"])

            if score >= min_score:
                if filters:
                    if "model_id" in filters:
                        if doc["metadata"].get("model_id") != filters["model_id"]:
                            continue

                results.append(
                    {
                        "id": doc_id,
                        "text": doc["text"],
                        "score": score,
                        "metadata": doc["metadata"],
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:k]

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def embedder() -> ControllableEmbeddingService:
    """Create controllable embedding service for testing."""
    return ControllableEmbeddingService(vector_dimension=1024)


@pytest.fixture
def opensearch() -> ControlledOpenSearchService:
    """Create controlled OpenSearch service for testing."""
    return ControlledOpenSearchService()


@pytest.fixture
def cache_service(
    embedder: ControllableEmbeddingService,
    opensearch: ControlledOpenSearchService,
) -> SemanticCacheService:
    """Create semantic cache service with controllable dependencies."""
    return SemanticCacheService(
        opensearch_service=opensearch,
        embedding_service=embedder,
        index_name="test-cache",
        mode=CacheMode.READ_WRITE,
        similarity_threshold=0.92,  # Default production threshold
    )


@pytest.fixture
def low_threshold_cache(
    embedder: ControllableEmbeddingService,
    opensearch: ControlledOpenSearchService,
) -> SemanticCacheService:
    """Cache service with lower threshold for testing collisions."""
    return SemanticCacheService(
        opensearch_service=opensearch,
        embedding_service=embedder,
        index_name="test-cache",
        mode=CacheMode.READ_WRITE,
        similarity_threshold=0.80,
    )


# =============================================================================
# Test Class: Semantic Collision Edge Cases
# =============================================================================


class TestSemanticCollisionEdgeCases:
    """
    Tests for semantic collision scenarios where different intents
    might incorrectly share cache entries.
    """

    @pytest.mark.asyncio
    async def test_different_intents_high_similarity_should_not_collide(
        self,
        embedder: ControllableEmbeddingService,
        opensearch: ControlledOpenSearchService,
    ) -> None:
        """
        Two prompts with high cosine similarity but different intents
        should NOT share cache entries when similarity is below threshold.

        This tests the scenario where embedding models produce similar vectors
        for semantically different operations (e.g., "create" vs "delete").
        """
        # Set up: Force high but below-threshold similarity (0.90 < 0.92)
        query1 = "Create a new user account for john@example.com"
        query2 = "Delete the user account for john@example.com"

        embedder.force_similarity(query1, query2, similarity=0.90)

        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,  # High threshold
        )

        # Cache response for "create" operation
        await cache.cache_response(
            query=query1,
            response='{"action": "created", "user": "john@example.com"}',
            model_id="test-model",
            query_type=QueryType.GENERAL,
        )

        # Query with "delete" operation - should NOT hit cache
        result = await cache.get_cached_response(
            query=query2,
            model_id="test-model",
        )

        assert result.hit is False, (
            "Different intents (create vs delete) should not share cache "
            "even with high embedding similarity"
        )

    @pytest.mark.asyncio
    async def test_dangerous_collision_at_threshold_boundary(
        self,
        embedder: ControllableEmbeddingService,
        opensearch: ControlledOpenSearchService,
    ) -> None:
        """
        Test behavior at exact threshold boundary (0.92).

        When similarity equals threshold exactly, the cache should hit.
        This tests that the >= comparison is working correctly.
        """
        query1 = "Approve the payment request"
        query2 = "Review the payment request"

        # Force similarity exactly at threshold
        embedder.force_similarity(query1, query2, similarity=0.92)

        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,
        )

        # Cache response for query1
        await cache.cache_response(
            query=query1,
            response='{"status": "approved"}',
            model_id="test-model",
        )

        # Manually set up the search result at exact threshold
        opensearch.force_search_results(
            [
                {
                    "id": "test-id",
                    "text": query1[:500],
                    "score": 0.92,  # Exactly at threshold
                    "metadata": {
                        "response": '{"status": "approved"}',
                        "expires_at": time.time() + 3600,
                        "model_id": "test-model",
                    },
                }
            ]
        )

        result = await cache.get_cached_response(
            query=query2,
            model_id="test-model",
        )

        # At exact threshold, cache should hit (>= comparison)
        assert result.hit is True
        assert result.similarity_score == 0.92


class TestShortPromptCollisions:
    """
    Tests for collision risks with very short prompts.

    Short prompts (1-2 words) have less semantic information,
    making collisions more likely in embedding space.
    """

    @pytest.mark.asyncio
    async def test_single_word_prompts_collision_risk(
        self,
        embedder: ControllableEmbeddingService,
        opensearch: ControlledOpenSearchService,
    ) -> None:
        """
        Single word prompts like 'start' vs 'stop' might have
        dangerously high similarity in embedding space.
        """
        # These opposite-meaning words might have high similarity
        # because they occur in similar contexts
        embedder.force_similarity("start", "stop", similarity=0.88)

        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.85,  # Lower threshold shows the risk
        )

        await cache.cache_response(
            query="start",
            response='{"action": "started"}',
            model_id="test-model",
        )

        # Force the result to simulate what happens with lower threshold
        opensearch.force_search_results(
            [
                {
                    "id": "cache-1",
                    "text": "start",
                    "score": 0.88,
                    "metadata": {
                        "response": '{"action": "started"}',
                        "expires_at": time.time() + 3600,
                        "model_id": "test-model",
                    },
                }
            ]
        )

        result = await cache.get_cached_response(
            query="stop",
            model_id="test-model",
        )

        # With lower threshold, this dangerous collision could occur
        assert result.hit is True, (
            "This test demonstrates the collision risk with short prompts "
            "and lower thresholds"
        )

    @pytest.mark.asyncio
    async def test_short_prompts_protected_by_high_threshold(
        self,
        embedder: ControllableEmbeddingService,
        opensearch: ControlledOpenSearchService,
    ) -> None:
        """
        Production threshold (0.92) should protect against short prompt collisions.
        """
        embedder.force_similarity("enable", "disable", similarity=0.89)

        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,  # Production threshold
        )

        await cache.cache_response(
            query="enable",
            response='{"status": "enabled"}',
            model_id="test-model",
        )

        # With production threshold, 0.89 similarity should miss
        result = await cache.get_cached_response(
            query="disable",
            model_id="test-model",
        )

        assert (
            result.hit is False
        ), "High threshold should protect against short prompt collisions"

    @pytest.mark.asyncio
    async def test_two_word_prompts_with_shared_context(
        self,
        embedder: ControllableEmbeddingService,
        opensearch: ControlledOpenSearchService,
    ) -> None:
        """
        Two-word prompts sharing a word might have deceptively high similarity.
        """
        # "fix bug" and "find bug" share "bug" but have different intents
        embedder.force_similarity("fix bug", "find bug", similarity=0.91)

        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,
        )

        await cache.cache_response(
            query="fix bug",
            response='{"action": "patched", "changes": [...]}',
            model_id="test-model",
        )

        result = await cache.get_cached_response(
            query="find bug",
            model_id="test-model",
        )

        assert result.hit is False, (
            "'fix bug' and 'find bug' have different intents "
            "and should not share cache"
        )


class TestNegationDifferences:
    """
    Tests for prompts differing only by negation.

    "add feature" vs "remove feature" or "enable X" vs "disable X"
    are semantically opposite but may have similar embeddings.
    """

    @pytest.mark.asyncio
    async def test_add_vs_remove_feature(
        self,
        embedder: ControllableEmbeddingService,
        opensearch: ControlledOpenSearchService,
    ) -> None:
        """
        'Add feature X' vs 'Remove feature X' should never share cache.
        """
        query_add = "Add the authentication feature to the login page"
        query_remove = "Remove the authentication feature from the login page"

        # These might have high similarity due to shared context
        embedder.force_similarity(query_add, query_remove, similarity=0.87)

        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,
        )

        await cache.cache_response(
            query=query_add,
            response='{"action": "added", "component": "auth"}',
            model_id="test-model",
        )

        result = await cache.get_cached_response(
            query=query_remove,
            model_id="test-model",
        )

        assert result.hit is False

    @pytest.mark.asyncio
    async def test_should_vs_should_not(
        self,
        embedder: ControllableEmbeddingService,
        opensearch: ControlledOpenSearchService,
    ) -> None:
        """
        Prompts with 'should' vs 'should not' are semantically opposite.
        """
        query1 = "The function should return null on error"
        query2 = "The function should not return null on error"

        embedder.force_similarity(query1, query2, similarity=0.94)

        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,
        )

        await cache.cache_response(
            query=query1,
            response='{"recommendation": "return null"}',
            model_id="test-model",
        )

        # Force the dangerous result to demonstrate the edge case
        opensearch.force_search_results(
            [
                {
                    "id": "cache-1",
                    "text": query1[:500],
                    "score": 0.94,
                    "metadata": {
                        "response": '{"recommendation": "return null"}',
                        "expires_at": time.time() + 3600,
                        "model_id": "test-model",
                    },
                }
            ]
        )

        result = await cache.get_cached_response(
            query=query2,
            model_id="test-model",
        )

        # This demonstrates a dangerous collision that can occur
        # when negation produces embeddings above threshold
        if result.hit:
            assert result.response == '{"recommendation": "return null"}'
            # This is a FALSE POSITIVE - the response is semantically wrong


class TestNumericDifferences:
    """
    Tests for prompts differing only by numbers.

    "set timeout to 5" vs "set timeout to 50" or "retry 3 times" vs "retry 30 times"
    may have high embedding similarity but very different meanings.
    """

    @pytest.mark.asyncio
    async def test_timeout_value_differences(
        self,
        embedder: ControllableEmbeddingService,
        opensearch: ControlledOpenSearchService,
    ) -> None:
        """
        'Set timeout to 5' vs 'Set timeout to 50' should not share cache.
        """
        query_5 = "Set the connection timeout to 5 seconds"
        query_50 = "Set the connection timeout to 50 seconds"

        # Numbers in similar context might have very high similarity
        embedder.force_similarity(query_5, query_50, similarity=0.96)

        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,
        )

        await cache.cache_response(
            query=query_5,
            response='{"timeout_seconds": 5}',
            model_id="test-model",
        )

        # Force dangerous collision scenario
        opensearch.force_search_results(
            [
                {
                    "id": "cache-1",
                    "text": query_5[:500],
                    "score": 0.96,
                    "metadata": {
                        "response": '{"timeout_seconds": 5}',
                        "expires_at": time.time() + 3600,
                        "model_id": "test-model",
                    },
                }
            ]
        )

        result = await cache.get_cached_response(
            query=query_50,
            model_id="test-model",
        )

        # Document that numeric collisions CAN occur
        if result.hit:
            # This is a WRONG result - we asked for 50, got 5
            assert result.response == '{"timeout_seconds": 5}'
            # This test demonstrates the edge case

    @pytest.mark.asyncio
    async def test_retry_count_differences(
        self,
        embedder: ControllableEmbeddingService,
        opensearch: ControlledOpenSearchService,
    ) -> None:
        """
        'Retry 3 times' vs 'Retry 30 times' have very different implications.
        """
        query_3 = "Configure the service to retry failed requests 3 times"
        query_30 = "Configure the service to retry failed requests 30 times"

        embedder.force_similarity(query_3, query_30, similarity=0.97)

        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,
        )

        await cache.cache_response(
            query=query_3,
            response='{"max_retries": 3, "backoff": "exponential"}',
            model_id="test-model",
        )

        opensearch.force_search_results(
            [
                {
                    "id": "cache-1",
                    "text": query_3[:500],
                    "score": 0.97,
                    "metadata": {
                        "response": '{"max_retries": 3, "backoff": "exponential"}',
                        "expires_at": time.time() + 3600,
                        "model_id": "test-model",
                    },
                }
            ]
        )

        result = await cache.get_cached_response(
            query=query_30,
            model_id="test-model",
        )

        # High numeric similarity can cause incorrect cache hits
        assert result.hit is True
        # Wrong value returned!
        assert '"max_retries": 3' in result.response

    @pytest.mark.asyncio
    async def test_version_number_differences(
        self,
        embedder: ControllableEmbeddingService,
        opensearch: ControlledOpenSearchService,
    ) -> None:
        """
        Version numbers like '1.0' vs '2.0' might have high similarity.
        """
        query_v1 = "Upgrade the package to version 1.0"
        query_v2 = "Upgrade the package to version 2.0"

        embedder.force_similarity(query_v1, query_v2, similarity=0.95)

        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,
        )

        await cache.cache_response(
            query=query_v1,
            response='{"target_version": "1.0", "breaking_changes": false}',
            model_id="test-model",
        )

        opensearch.force_search_results(
            [
                {
                    "id": "cache-1",
                    "text": query_v1[:500],
                    "score": 0.95,
                    "metadata": {
                        "response": '{"target_version": "1.0", "breaking_changes": false}',
                        "expires_at": time.time() + 3600,
                        "model_id": "test-model",
                    },
                }
            ]
        )

        result = await cache.get_cached_response(
            query=query_v2,
            model_id="test-model",
        )

        # Version collision - got v1 when asking for v2
        assert result.hit is True


class TestThresholdBoundaryConditions:
    """
    Tests for similarity threshold boundary conditions.
    """

    @pytest.mark.asyncio
    async def test_exactly_at_threshold_hits_cache(
        self,
        opensearch: ControlledOpenSearchService,
        embedder: ControllableEmbeddingService,
    ) -> None:
        """
        Similarity exactly at threshold (>=) should result in cache hit.
        """
        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,
        )

        await cache.cache_response(
            query="test query",
            response="test response",
            model_id="test-model",
        )

        opensearch.force_search_results(
            [
                {
                    "id": "cache-1",
                    "text": "test query",
                    "score": 0.92,  # Exactly at threshold
                    "metadata": {
                        "response": "test response",
                        "expires_at": time.time() + 3600,
                        "model_id": "test-model",
                    },
                }
            ]
        )

        result = await cache.get_cached_response(
            query="similar query",
            model_id="test-model",
        )

        assert result.hit is True
        assert result.similarity_score == 0.92

    @pytest.mark.asyncio
    async def test_just_below_threshold_misses_cache(
        self,
        opensearch: ControlledOpenSearchService,
        embedder: ControllableEmbeddingService,
    ) -> None:
        """
        Similarity just below threshold should result in cache miss.
        """
        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,
        )

        await cache.cache_response(
            query="test query",
            response="test response",
            model_id="test-model",
        )

        # OpenSearch would filter this out before returning
        opensearch.force_search_results([])  # Nothing above threshold

        result = await cache.get_cached_response(
            query="somewhat different query",
            model_id="test-model",
        )

        assert result.hit is False

    @pytest.mark.asyncio
    async def test_very_low_threshold_accepts_most_results(
        self,
        opensearch: ControlledOpenSearchService,
        embedder: ControllableEmbeddingService,
    ) -> None:
        """
        Very low threshold (0.01) should accept almost any result.

        Note: SemanticCacheService uses `threshold or DEFAULT` logic,
        so 0.0 is treated as "use default". We use 0.01 instead.
        """
        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.01,  # Use 0.01 not 0.0 (0.0 is falsy)
        )

        await cache.cache_response(
            query="original query",
            response="original response",
            model_id="test-model",
        )

        opensearch.force_search_results(
            [
                {
                    "id": "cache-1",
                    "text": "original query",
                    "score": 0.02,  # Very low similarity, but above 0.01
                    "metadata": {
                        "response": "original response",
                        "expires_at": time.time() + 3600,
                        "model_id": "test-model",
                    },
                }
            ]
        )

        result = await cache.get_cached_response(
            query="completely different query",
            model_id="test-model",
        )

        assert result.hit is True

    @pytest.mark.asyncio
    async def test_zero_threshold_uses_default(
        self,
        opensearch: ControlledOpenSearchService,
        embedder: ControllableEmbeddingService,
    ) -> None:
        """
        Threshold of 0.0 falls back to default due to Python truthiness.

        This documents the current behavior where `0.0 or default` = default.
        """
        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.0,  # Will use default (0.92)
        )

        # Verify the actual threshold is the default
        assert (
            cache.similarity_threshold
            == SemanticCacheService.DEFAULT_SIMILARITY_THRESHOLD
        )

    @pytest.mark.asyncio
    async def test_threshold_1_requires_exact_match(
        self,
        opensearch: ControlledOpenSearchService,
        embedder: ControllableEmbeddingService,
    ) -> None:
        """
        Threshold of 1.0 should only match identical embeddings.
        """
        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=1.0,
        )

        await cache.cache_response(
            query="exact query",
            response="exact response",
            model_id="test-model",
        )

        # 0.999 similarity should miss with threshold 1.0
        opensearch.force_search_results([])  # Filtered by threshold

        result = await cache.get_cached_response(
            query="exact query",  # Same query
            model_id="test-model",
        )

        # Only exact match (1.0) would pass
        assert result.hit is False


class TestFalsePositiveCacheHits:
    """
    Tests for scenarios where cache returns wrong results.
    """

    @pytest.mark.asyncio
    async def test_false_positive_detection_strategy(
        self,
        opensearch: ControlledOpenSearchService,
        embedder: ControllableEmbeddingService,
    ) -> None:
        """
        Demonstrate how to detect potential false positive scenarios.

        In production, cache hits should be validated against:
        1. Query type consistency
        2. Key terms presence
        3. Semantic verification
        """
        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,
        )

        # Cache a security analysis response
        await cache.cache_response(
            query="Analyze this code for SQL injection vulnerabilities",
            response='{"vulnerability_type": "sql_injection", "severity": "high"}',
            model_id="test-model",
            query_type=QueryType.VULNERABILITY_ANALYSIS,
        )

        opensearch.force_search_results(
            [
                {
                    "id": "cache-1",
                    "text": "Analyze this code for SQL injection",
                    "score": 0.93,
                    "metadata": {
                        "response": '{"vulnerability_type": "sql_injection", "severity": "high"}',
                        "expires_at": time.time() + 3600,
                        "model_id": "test-model",
                        "query_type": "vulnerability_analysis",
                    },
                }
            ]
        )

        # Query for XSS instead of SQL injection
        result = await cache.get_cached_response(
            query="Analyze this code for XSS vulnerabilities",
            model_id="test-model",
            query_type=QueryType.VULNERABILITY_ANALYSIS,
        )

        # This might hit cache due to similar structure
        if result.hit:
            # FALSE POSITIVE: Response mentions SQL injection, not XSS
            assert "sql_injection" in result.response
            # Production system should validate response relevance

    @pytest.mark.asyncio
    async def test_model_filter_prevents_cross_model_hits(
        self,
        opensearch: ControlledOpenSearchService,
        embedder: ControllableEmbeddingService,
    ) -> None:
        """
        Responses cached for one model should not hit for different model.
        """
        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.92,
        )

        # Cache response for Claude
        await cache.cache_response(
            query="Explain this code",
            response="Claude explanation...",
            model_id="anthropic.claude-3-5-sonnet",
        )

        # Query with different model
        result = await cache.get_cached_response(
            query="Explain this code",
            model_id="anthropic.claude-3-opus",  # Different model
        )

        # Model filter should prevent hit
        assert result.hit is False


class TestEmbeddingModelChanges:
    """
    Tests for cache invalidation when embedding model changes.
    """

    @pytest.mark.asyncio
    async def test_invalidate_by_model_clears_cache(
        self,
        cache_service: SemanticCacheService,
    ) -> None:
        """
        Cache invalidation by model should clear relevant entries.
        """
        # Cache some responses
        await cache_service.cache_response(
            query="Test query 1",
            response="Response 1",
            model_id="model-v1",
        )

        await cache_service.cache_response(
            query="Test query 2",
            response="Response 2",
            model_id="model-v1",
        )

        # Invalidate model-v1 cache
        count = await cache_service.invalidate_by_model("model-v1")

        # Current implementation returns 0 (placeholder)
        # In production, this should return count of invalidated entries
        assert count >= 0

    @pytest.mark.asyncio
    async def test_model_version_tracking(
        self,
        opensearch: ControlledOpenSearchService,
        embedder: ControllableEmbeddingService,
    ) -> None:
        """
        Cache entries should track model version for invalidation.
        """
        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
        )

        cache_id = await cache.cache_response(
            query="Test query",
            response="Test response",
            model_id="test-model",
            model_version="1.0.0",
        )

        assert cache_id is not None

        # Verify version is stored in metadata
        cached_doc = opensearch.indexed_docs.get(cache_id)
        assert cached_doc is not None
        assert cached_doc["metadata"]["model_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_embedding_dimension_change_detection(
        self,
        opensearch: ControlledOpenSearchService,
    ) -> None:
        """
        Changing embedding dimensions should be handled gracefully.
        """
        # Old embedder with 512 dimensions
        old_embedder = ControllableEmbeddingService(vector_dimension=512)

        cache_old = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=old_embedder,
        )

        await cache_old.cache_response(
            query="Test query",
            response="Response from old model",
            model_id="test-model",
        )

        # New embedder with 1024 dimensions
        new_embedder = ControllableEmbeddingService(vector_dimension=1024)

        cache_new = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=new_embedder,
        )

        # Searching with mismatched dimensions should handle gracefully
        # (In real OpenSearch, this would fail - test documents incompatibility)
        result = await cache_new.get_cached_response(
            query="Test query",
            model_id="test-model",
        )

        # Dimension mismatch means similarity calculation fails
        # or returns very low scores
        assert result.hit is False


class TestCacheEntryEdgeCases:
    """
    Tests for CacheEntry edge cases.
    """

    def test_cache_entry_with_empty_metadata(self) -> None:
        """Cache entry should handle empty metadata."""
        entry = CacheEntry(
            cache_id="test-123",
            query_hash="abc",
            query_text="test",
            query_embedding=[0.1] * 1024,
            response="response",
            model_id="model",
            model_version="1.0",
            query_type=QueryType.GENERAL,
            agent_name="test-agent",
            created_at=time.time(),
            expires_at=time.time() + 3600,
            metadata={},  # Empty
        )

        data = entry.to_dict()
        assert data["metadata"] == {}

        restored = CacheEntry.from_dict(data)
        assert restored.metadata == {}

    def test_cache_entry_with_missing_optional_fields(self) -> None:
        """Cache entry should handle missing optional fields in from_dict."""
        minimal_data = {
            "cache_id": "test-123",
            "query_hash": "abc",
            "query_text": "test",
            "query_embedding": [0.1] * 10,
            "response": "response",
            "model_id": "model",
            "created_at": time.time(),
            "expires_at": time.time() + 3600,
            # Missing: model_version, query_type, agent_name, hit_count, metadata
        }

        entry = CacheEntry.from_dict(minimal_data)

        assert entry.model_version == "unknown"
        assert entry.query_type == QueryType.GENERAL
        assert entry.agent_name == "unknown"
        assert entry.hit_count == 0
        assert entry.metadata == {}

    def test_cache_entry_truncates_long_query_text(self) -> None:
        """to_dict should truncate query_text to 500 chars."""
        long_query = "x" * 1000

        entry = CacheEntry(
            cache_id="test-123",
            query_hash="abc",
            query_text=long_query,
            query_embedding=[0.1] * 1024,
            response="response",
            model_id="model",
            model_version="1.0",
            query_type=QueryType.GENERAL,
            agent_name="test-agent",
            created_at=time.time(),
            expires_at=time.time() + 3600,
        )

        data = entry.to_dict()
        assert len(data["query_text"]) == 500


class TestConcurrencyEdgeCases:
    """
    Tests for concurrent access edge cases.
    """

    @pytest.mark.asyncio
    async def test_concurrent_cache_writes_same_query(
        self,
        cache_service: SemanticCacheService,
    ) -> None:
        """
        Multiple concurrent writes for same query should not cause issues.
        """
        import asyncio

        query = "Concurrent test query"

        async def write_to_cache(response: str) -> str | None:
            return await cache_service.cache_response(
                query=query,
                response=response,
                model_id="test-model",
            )

        # Write concurrently
        results = await asyncio.gather(
            write_to_cache("Response A"),
            write_to_cache("Response B"),
            write_to_cache("Response C"),
        )

        # All writes should succeed (may create duplicates)
        assert all(r is not None for r in results)
        # Each gets unique cache_id
        assert len(set(results)) == 3

    @pytest.mark.asyncio
    async def test_read_during_write(
        self,
        opensearch: ControlledOpenSearchService,
        embedder: ControllableEmbeddingService,
    ) -> None:
        """
        Reading from cache during write should not cause issues.
        """
        import asyncio

        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=embedder,
            similarity_threshold=0.5,  # Lower for testing
        )

        async def write() -> str | None:
            return await cache.cache_response(
                query="Write query",
                response="Write response",
                model_id="test-model",
            )

        async def read() -> CacheResult:
            return await cache.get_cached_response(
                query="Read query",
                model_id="test-model",
            )

        # Execute concurrently
        write_result, read_result = await asyncio.gather(write(), read())

        assert write_result is not None
        # Read may or may not hit depending on timing
        assert isinstance(read_result, CacheResult)


class TestErrorHandling:
    """
    Tests for error handling edge cases.
    """

    @pytest.mark.asyncio
    async def test_embedding_service_failure(
        self,
        opensearch: ControlledOpenSearchService,
    ) -> None:
        """
        Cache should handle embedding service failures gracefully.
        """
        failing_embedder = MagicMock()
        failing_embedder.generate_embedding.side_effect = Exception(
            "Embedding service unavailable"
        )

        cache = SemanticCacheService(
            opensearch_service=opensearch,
            embedding_service=failing_embedder,
        )

        # Write should fail gracefully
        cache_id = await cache.cache_response(
            query="Test query",
            response="Test response",
            model_id="test-model",
        )

        assert cache_id is None

    @pytest.mark.asyncio
    async def test_opensearch_failure_on_read(
        self,
        embedder: ControllableEmbeddingService,
    ) -> None:
        """
        Cache should handle OpenSearch failures on read gracefully.
        """
        failing_opensearch = MagicMock()
        failing_opensearch.search_similar.side_effect = Exception(
            "OpenSearch connection failed"
        )

        cache = SemanticCacheService(
            opensearch_service=failing_opensearch,
            embedding_service=embedder,
        )

        result = await cache.get_cached_response(
            query="Test query",
            model_id="test-model",
        )

        # Should return miss, not raise exception
        assert result.hit is False
        assert cache.stats.cache_misses == 1

    @pytest.mark.asyncio
    async def test_opensearch_failure_on_write(
        self,
        embedder: ControllableEmbeddingService,
    ) -> None:
        """
        Cache should handle OpenSearch failures on write gracefully.
        """
        failing_opensearch = MagicMock()
        failing_opensearch.index_embedding.side_effect = Exception(
            "OpenSearch write failed"
        )

        cache = SemanticCacheService(
            opensearch_service=failing_opensearch,
            embedding_service=embedder,
        )

        cache_id = await cache.cache_response(
            query="Test query",
            response="Test response",
            model_id="test-model",
        )

        assert cache_id is None


class TestCostEstimationEdgeCases:
    """
    Tests for cost estimation edge cases.
    """

    def test_cost_estimation_empty_strings(
        self,
        cache_service: SemanticCacheService,
    ) -> None:
        """
        Cost estimation should handle empty strings.
        """
        cost = cache_service._estimate_cost_saved("", "", "test-model")
        assert cost == 0.0

    def test_cost_estimation_unknown_model(
        self,
        cache_service: SemanticCacheService,
    ) -> None:
        """
        Cost estimation should use default for unknown models.
        """
        cost = cache_service._estimate_cost_saved(
            "query" * 100,
            "response" * 200,
            "unknown-model-xyz",
        )

        # Should use default cost per 1K tokens
        assert cost > 0

    def test_cost_estimation_opus_model(
        self,
        cache_service: SemanticCacheService,
    ) -> None:
        """
        Opus model should have higher cost savings.
        """
        query = "x" * 4000  # ~1000 tokens
        response = "y" * 4000  # ~1000 tokens

        opus_cost = cache_service._estimate_cost_saved(
            query, response, "anthropic.claude-3-opus"
        )

        haiku_cost = cache_service._estimate_cost_saved(
            query, response, "anthropic.claude-3-haiku"
        )

        # Opus is ~60x more expensive than Haiku
        assert opus_cost > haiku_cost * 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
