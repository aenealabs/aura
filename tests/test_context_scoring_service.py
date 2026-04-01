"""
Project Aura - Context Scoring Service Tests

Tests for the ContextScoringService that implements
relevance-based context pruning per ADR-034.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.context_scoring_service import (
    ContextScoringConfig,
    ContextScoringService,
    ScoredContext,
)


class TestScoredContext:
    """Tests for ScoredContext dataclass."""

    def test_scored_context_creation(self):
        """Test basic ScoredContext creation."""
        ctx = ScoredContext(
            content="def hello(): pass",
            source="graph",
            relevance_score=0.85,
            recency_weight=0.9,
            information_density=0.6,
            final_score=0.75,
            token_count=100,
        )
        assert ctx.content == "def hello(): pass"
        assert ctx.source == "graph"
        assert ctx.relevance_score == 0.85
        assert ctx.recency_weight == 0.9
        assert ctx.information_density == 0.6
        assert ctx.final_score == 0.75
        assert ctx.token_count == 100
        assert ctx.metadata == {}

    def test_scored_context_with_metadata(self):
        """Test ScoredContext with metadata."""
        metadata = {"file": "test.py", "line": 42}
        ctx = ScoredContext(
            content="test",
            source="vector",
            relevance_score=0.5,
            recency_weight=0.5,
            information_density=0.5,
            final_score=0.5,
            token_count=10,
            metadata=metadata,
        )
        assert ctx.metadata == metadata

    def test_scored_context_default_metadata(self):
        """Test that metadata defaults to empty dict."""
        ctx = ScoredContext(
            content="test",
            source="graph",
            relevance_score=0.5,
            recency_weight=0.5,
            information_density=0.5,
            final_score=0.5,
            token_count=10,
        )
        assert ctx.metadata == {}


class TestContextScoringConfig:
    """Tests for ContextScoringConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ContextScoringConfig()
        assert config.relevance_weight == 0.50
        assert config.recency_weight == 0.30
        assert config.density_weight == 0.20
        assert config.min_score_threshold == 0.3
        assert config.max_context_tokens == 100000
        assert config.recency_half_life_days == 30
        assert config.content_truncation_limit == 2000

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ContextScoringConfig(
            relevance_weight=0.6,
            recency_weight=0.2,
            density_weight=0.2,
            min_score_threshold=0.5,
            max_context_tokens=50000,
        )
        assert config.relevance_weight == 0.6
        assert config.min_score_threshold == 0.5
        assert config.max_context_tokens == 50000


class TestContextScoringService:
    """Tests for ContextScoringService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_embedder = MagicMock()
        self.mock_embedder.embed_text = AsyncMock(
            return_value=[0.1, 0.2, 0.3, 0.4, 0.5]
        )
        self.service = ContextScoringService(self.mock_embedder)

    @pytest.mark.asyncio
    async def test_score_context_empty_items(self):
        """Test scoring empty context list."""
        result = await self.service.score_context("query", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_score_context_single_item(self):
        """Test scoring single context item."""
        items = [{"content": "def hello(): pass", "source": "graph"}]
        result = await self.service.score_context("hello function", items)

        assert len(result) == 1
        assert result[0].content == "def hello(): pass"
        assert result[0].source == "graph"
        assert 0 <= result[0].final_score <= 1

    @pytest.mark.asyncio
    async def test_score_context_multiple_items_sorted(self):
        """Test that results are sorted by score descending."""
        items = [
            {"content": "low relevance content", "source": "vector"},
            {"content": "high relevance function", "source": "graph"},
            {"content": "medium content", "source": "filesystem"},
        ]
        # Mock different embeddings for different content
        call_count = [0]

        async def varied_embeddings(text):
            call_count[0] += 1
            if "high" in text:
                return [0.9, 0.9, 0.9, 0.9, 0.9]
            elif "medium" in text:
                return [0.5, 0.5, 0.5, 0.5, 0.5]
            return [0.1, 0.1, 0.1, 0.1, 0.1]

        self.mock_embedder.embed_text = varied_embeddings
        result = await self.service.score_context("function", items)

        assert len(result) == 3
        # Verify sorted by score descending
        for i in range(len(result) - 1):
            assert result[i].final_score >= result[i + 1].final_score

    @pytest.mark.asyncio
    async def test_score_context_with_precomputed_embedding(self):
        """Test scoring with pre-computed query embedding."""
        items = [{"content": "test content", "source": "graph"}]
        query_embedding = [0.5, 0.5, 0.5, 0.5, 0.5]

        result = await self.service.score_context(
            "query", items, query_embedding=query_embedding
        )

        assert len(result) == 1
        # Should still call embed_text for content but not query
        assert self.mock_embedder.embed_text.call_count == 1

    @pytest.mark.asyncio
    async def test_score_context_error_handling(self):
        """Test that scoring continues on item errors."""
        items = [
            {"content": "good item", "source": "graph"},
            {"content": None, "source": "bad"},  # This should fail
            {"content": "another good item", "source": "vector"},
        ]

        # Errors on None content
        async def embedder_with_error(text):
            if text is None:
                raise ValueError("Cannot embed None")
            return [0.5, 0.5, 0.5, 0.5, 0.5]

        self.mock_embedder.embed_text = embedder_with_error
        result = await self.service.score_context("query", items)

        # Should have at least one successful result
        assert len(result) >= 1


class TestContextPruning:
    """Tests for context pruning functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_embedder = MagicMock()
        self.mock_embedder.embed_text = AsyncMock(return_value=[0.5, 0.5, 0.5])
        self.service = ContextScoringService(self.mock_embedder)

    @pytest.mark.asyncio
    async def test_prune_context_empty(self):
        """Test pruning empty list."""
        result = await self.service.prune_context([])
        assert result == []

    @pytest.mark.asyncio
    async def test_prune_context_by_score_threshold(self):
        """Test that low-score items are pruned."""
        scored_items = [
            ScoredContext(
                content="high",
                source="a",
                relevance_score=0.9,
                recency_weight=0.9,
                information_density=0.9,
                final_score=0.9,
                token_count=100,
            ),
            ScoredContext(
                content="low",
                source="b",
                relevance_score=0.1,
                recency_weight=0.1,
                information_density=0.1,
                final_score=0.1,
                token_count=100,
            ),
        ]

        result = await self.service.prune_context(scored_items, min_score=0.5)

        assert len(result) == 1
        assert result[0].content == "high"

    @pytest.mark.asyncio
    async def test_prune_context_by_token_budget(self):
        """Test pruning by token budget."""
        scored_items = [
            ScoredContext(
                content="first",
                source="a",
                relevance_score=0.9,
                recency_weight=0.9,
                information_density=0.9,
                final_score=0.9,
                token_count=5000,
            ),
            ScoredContext(
                content="second",
                source="b",
                relevance_score=0.8,
                recency_weight=0.8,
                information_density=0.8,
                final_score=0.8,
                token_count=5000,
            ),
            ScoredContext(
                content="third",
                source="c",
                relevance_score=0.7,
                recency_weight=0.7,
                information_density=0.7,
                final_score=0.7,
                token_count=5000,
            ),
        ]

        result = await self.service.prune_context(scored_items, token_budget=10000)

        assert len(result) == 2
        assert result[0].content == "first"
        assert result[1].content == "second"

    @pytest.mark.asyncio
    async def test_prune_uses_config_defaults(self):
        """Test that pruning uses config defaults."""
        config = ContextScoringConfig(min_score_threshold=0.5, max_context_tokens=1000)
        service = ContextScoringService(self.mock_embedder, config)

        scored_items = [
            ScoredContext(
                content="ok",
                source="a",
                relevance_score=0.6,
                recency_weight=0.6,
                information_density=0.6,
                final_score=0.6,
                token_count=500,
            ),
            ScoredContext(
                content="bad",
                source="b",
                relevance_score=0.3,
                recency_weight=0.3,
                information_density=0.3,
                final_score=0.3,
                token_count=500,
            ),
        ]

        result = await service.prune_context(scored_items)

        assert len(result) == 1
        assert result[0].content == "ok"


class TestScoreAndPrune:
    """Tests for combined score_and_prune method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_embedder = MagicMock()
        self.mock_embedder.embed_text = AsyncMock(return_value=[0.5, 0.5, 0.5, 0.5])
        self.service = ContextScoringService(self.mock_embedder)

    @pytest.mark.asyncio
    async def test_score_and_prune_basic(self):
        """Test combined scoring and pruning."""
        items = [
            {"content": "relevant content", "source": "graph"},
            {"content": "other content", "source": "vector"},
        ]

        result = await self.service.score_and_prune("query", items)

        assert isinstance(result, list)
        assert all(isinstance(item, ScoredContext) for item in result)

    @pytest.mark.asyncio
    async def test_score_and_prune_with_budget(self):
        """Test combined method with token budget."""
        items = [
            {"content": "a" * 1000, "source": "graph"},
            {"content": "b" * 1000, "source": "vector"},
        ]

        result = await self.service.score_and_prune("query", items, token_budget=300)

        # Should be limited by budget
        total_tokens = sum(item.token_count for item in result)
        assert total_tokens <= 300


class TestRelevanceComputation:
    """Tests for relevance score computation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_embedder = MagicMock()
        self.service = ContextScoringService(self.mock_embedder)

    def test_cosine_similarity_identical(self):
        """Test cosine similarity of identical vectors."""
        vec = [1.0, 0.0, 0.0]
        similarity = self.service._cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity of orthogonal vectors."""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        similarity = self.service._cosine_similarity(vec1, vec2)
        assert abs(similarity) < 0.001

    def test_cosine_similarity_empty_vectors(self):
        """Test cosine similarity with empty vectors."""
        assert self.service._cosine_similarity([], []) == 0.0
        assert self.service._cosine_similarity([1.0], []) == 0.0

    def test_cosine_similarity_different_lengths(self):
        """Test cosine similarity with different length vectors."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0]
        assert self.service._cosine_similarity(vec1, vec2) == 0.0

    def test_tfidf_overlap_exact_match(self):
        """Test TF-IDF overlap with exact terms."""
        query = "hello world"
        content = "hello world function"
        score = self.service._tfidf_overlap(query, content)
        assert score > 0

    def test_tfidf_overlap_no_match(self):
        """Test TF-IDF overlap with no matching terms."""
        query = "hello world"
        content = "completely different terms here"
        score = self.service._tfidf_overlap(query, content)
        # Might still have some overlap from common words
        assert 0 <= score <= 1

    def test_tfidf_overlap_empty(self):
        """Test TF-IDF overlap with empty strings."""
        assert self.service._tfidf_overlap("", "content") >= 0
        assert self.service._tfidf_overlap("query", "") >= 0


class TestRecencyComputation:
    """Tests for recency weight computation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_embedder = MagicMock()
        self.service = ContextScoringService(self.mock_embedder)

    def test_recency_none_timestamp(self):
        """Test recency with no timestamp returns neutral."""
        assert self.service._compute_recency(None) == 0.5

    def test_recency_recent_timestamp(self):
        """Test recency with very recent timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        recency = self.service._compute_recency(now)
        # Should be close to 1.0 for very recent
        assert recency > 0.9

    def test_recency_old_timestamp(self):
        """Test recency with old timestamp."""
        old = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        recency = self.service._compute_recency(old)
        # Should be close to 0 for very old
        assert recency < 0.1

    def test_recency_z_suffix(self):
        """Test recency with Z suffix timestamp."""
        now_z = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        recency = self.service._compute_recency(now_z)
        assert recency > 0.9

    def test_recency_invalid_timestamp(self):
        """Test recency with invalid timestamp returns neutral."""
        assert self.service._compute_recency("not-a-date") == 0.5
        assert self.service._compute_recency("12345") == 0.5


class TestDensityComputation:
    """Tests for information density computation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_embedder = MagicMock()
        self.service = ContextScoringService(self.mock_embedder)

    def test_density_empty_content(self):
        """Test density of empty content."""
        assert self.service._compute_density("") == 0.0

    def test_density_single_char(self):
        """Test density of single repeated character."""
        # All same character = 0 entropy
        density = self.service._compute_density("aaaaaaaaaa")
        assert density == 0.0

    def test_density_varied_content(self):
        """Test density of varied content."""
        # Real code with varied characters should have higher density
        code = "def hello(name): return f'Hello, {name}!'"
        density = self.service._compute_density(code)
        assert density > 0.3

    def test_density_normalized(self):
        """Test that density is normalized to 0-1."""
        content = "x" * 1000 + "y" * 1000 + "z" * 1000
        density = self.service._compute_density(content)
        assert 0 <= density <= 1


class TestTokenEstimation:
    """Tests for token count estimation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_embedder = MagicMock()
        self.service = ContextScoringService(self.mock_embedder)

    def test_estimate_tokens_empty(self):
        """Test token estimation for empty string."""
        tokens = self.service._estimate_tokens("")
        # min of 1 token even for empty string
        assert tokens >= 0

    def test_estimate_tokens_short(self):
        """Test token estimation for short content."""
        tokens = self.service._estimate_tokens("hello world")
        assert tokens > 0

    def test_estimate_tokens_code(self):
        """Test token estimation for code content."""
        code = """
def calculate_sum(numbers):
    return sum(numbers)
"""
        tokens = self.service._estimate_tokens(code)
        assert tokens > 5

    def test_estimate_tokens_proportional(self):
        """Test that token count is proportional to content length."""
        short = self.service._estimate_tokens("short")
        long = self.service._estimate_tokens("a" * 1000)
        assert long > short
