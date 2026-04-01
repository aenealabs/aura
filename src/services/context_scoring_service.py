"""Context Scoring Service for Relevance-Based Pruning

Implements ADR-034 Phase 1.1: Context Scoring and Pruning

Prevents context rot by scoring and pruning retrieved context
before injection into agent prompts.

Research indicates effective context < 256K tokens.
This service ensures only high-value context is injected.
"""

import datetime
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class EmbeddingService(Protocol):
    """Protocol for embedding services."""

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for text."""
        ...


@dataclass
class ScoredContext:
    """Context item with relevance score."""

    content: str
    source: str  # "graph", "vector", "filesystem", "git"
    relevance_score: float  # 0.0 to 1.0
    recency_weight: float  # Time decay factor
    information_density: float  # Entropy-based
    final_score: float  # Weighted combination
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextScoringConfig:
    """Configuration for context scoring."""

    relevance_weight: float = 0.50
    recency_weight: float = 0.30
    density_weight: float = 0.20
    min_score_threshold: float = 0.3
    max_context_tokens: int = 100000
    recency_half_life_days: int = 30
    content_truncation_limit: int = 2000


class ContextScoringService:
    """Scores and prunes context to prevent context rot.

    Scoring formula:
        final_score = (relevance * 0.5) + (recency * 0.3) + (density * 0.2)

    Research indicates effective context < 256K tokens.
    This service ensures only high-value context is injected.

    Features:
    - Semantic similarity scoring via embeddings
    - TF-IDF keyword overlap
    - Time-decay recency weighting
    - Shannon entropy information density
    - Token budget enforcement
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        config: Optional[ContextScoringConfig] = None,
    ):
        """Initialize context scoring service.

        Args:
            embedding_service: Service for generating text embeddings
            config: Optional scoring configuration
        """
        self.embedder = embedding_service
        self.config = config or ContextScoringConfig()

    async def score_context(
        self,
        query: str,
        context_items: list[dict],
        query_embedding: Optional[list[float]] = None,
    ) -> list[ScoredContext]:
        """Score all context items for relevance to query.

        Args:
            query: The user query
            context_items: List of retrieved context items with keys:
                - content: str (required)
                - source: str (optional, default "unknown")
                - last_modified: str (optional, ISO format)
                - metadata: dict (optional)
            query_embedding: Pre-computed query embedding (optional)

        Returns:
            List of ScoredContext sorted by final_score descending
        """
        if not context_items:
            return []

        if not query_embedding:
            query_embedding = await self.embedder.embed_text(query)

        scored_items = []
        for item in context_items:
            try:
                scored = await self._score_single_item(item, query, query_embedding)
                scored_items.append(scored)
            except Exception as e:
                logger.warning(f"Failed to score context item: {e}")
                continue

        # Sort by final score descending
        scored_items.sort(key=lambda x: x.final_score, reverse=True)

        logger.info(
            f"Scored {len(scored_items)} context items. "
            f"Score range: {scored_items[-1].final_score:.2f} - {scored_items[0].final_score:.2f}"
            if scored_items
            else "No items scored"
        )

        return scored_items

    async def prune_context(
        self,
        scored_items: list[ScoredContext],
        token_budget: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> list[ScoredContext]:
        """Prune context to fit within token budget.

        Args:
            scored_items: Pre-scored context items (should be pre-sorted by score)
            token_budget: Maximum tokens (defaults to config max_context_tokens)
            min_score: Minimum score threshold (defaults to config min_score_threshold)

        Returns:
            Pruned list fitting within token budget and above score threshold
        """
        budget = token_budget or self.config.max_context_tokens
        threshold = min_score or self.config.min_score_threshold

        pruned: list[ScoredContext] = []
        total_tokens = 0

        for item in scored_items:
            # Skip low-score items
            if item.final_score < threshold:
                logger.debug(
                    f"Pruning item (score {item.final_score:.2f} < {threshold}): "
                    f"{item.content[:50]}..."
                )
                continue

            # Check token budget
            if total_tokens + item.token_count > budget:
                logger.debug(
                    f"Token budget exceeded at {total_tokens}/{budget}. "
                    f"Pruned remaining {len(scored_items) - len(pruned)} items."
                )
                break

            pruned.append(item)
            total_tokens += item.token_count

        logger.info(
            f"Pruned context: {len(scored_items)} -> {len(pruned)} items, "
            f"{total_tokens} tokens used of {budget} budget"
        )

        return pruned

    async def score_and_prune(
        self,
        query: str,
        context_items: list[dict],
        token_budget: Optional[int] = None,
        query_embedding: Optional[list[float]] = None,
    ) -> list[ScoredContext]:
        """Convenience method to score and prune in one call.

        Args:
            query: The user query
            context_items: List of retrieved context items
            token_budget: Maximum tokens for pruned result
            query_embedding: Pre-computed query embedding (optional)

        Returns:
            Scored and pruned context list
        """
        scored = await self.score_context(query, context_items, query_embedding)
        return await self.prune_context(scored, token_budget)

    async def _score_single_item(
        self, item: dict, query: str, query_embedding: list[float]
    ) -> ScoredContext:
        """Score a single context item."""
        content = item.get("content", "")

        # 1. Relevance score (semantic similarity + TF-IDF)
        relevance = await self._compute_relevance(content, query, query_embedding)

        # 2. Recency weight (time decay)
        recency = self._compute_recency(item.get("last_modified"))

        # 3. Information density (entropy)
        density = self._compute_density(content)

        # 4. Final weighted score
        final_score = (
            relevance * self.config.relevance_weight
            + recency * self.config.recency_weight
            + density * self.config.density_weight
        )

        return ScoredContext(
            content=content,
            source=item.get("source", "unknown"),
            relevance_score=relevance,
            recency_weight=recency,
            information_density=density,
            final_score=final_score,
            token_count=self._estimate_tokens(content),
            metadata=item.get("metadata", {}),
        )

    async def _compute_relevance(
        self, content: str, query: str, query_embedding: list[float]
    ) -> float:
        """Compute relevance using semantic similarity + TF-IDF.

        Args:
            content: Context content to score
            query: Original query
            query_embedding: Pre-computed query embedding

        Returns:
            Relevance score between 0.0 and 1.0
        """
        # Truncate content for embedding efficiency
        truncated_content = content[: self.config.content_truncation_limit]

        # Semantic similarity (cosine)
        try:
            content_embedding = await self.embedder.embed_text(truncated_content)
            semantic_sim = self._cosine_similarity(query_embedding, content_embedding)
        except Exception as e:
            logger.warning(f"Embedding failed, using TF-IDF only: {e}")
            semantic_sim = 0.0

        # TF-IDF keyword overlap
        tfidf_score = self._tfidf_overlap(query, content)

        # Combined (semantic weighted higher)
        return semantic_sim * 0.7 + tfidf_score * 0.3

    def _compute_recency(self, last_modified: Optional[str]) -> float:
        """Compute recency weight with exponential time decay.

        Args:
            last_modified: ISO format datetime string

        Returns:
            Recency weight between 0.0 and 1.0
        """
        if not last_modified:
            return 0.5  # Neutral if no timestamp

        try:
            # Handle various ISO formats
            if last_modified.endswith("Z"):
                modified_dt = datetime.datetime.fromisoformat(
                    last_modified.replace("Z", "+00:00")
                )
            elif "+" in last_modified or "-" in last_modified[-6:]:
                modified_dt = datetime.datetime.fromisoformat(last_modified)
            else:
                modified_dt = datetime.datetime.fromisoformat(last_modified).replace(
                    tzinfo=datetime.timezone.utc
                )

            now = datetime.datetime.now(datetime.timezone.utc)
            days_old = max(0, (now - modified_dt).days)

            # Exponential decay with configurable half-life
            return math.exp(-days_old / self.config.recency_half_life_days)

        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse timestamp '{last_modified}': {e}")
            return 0.5

    def _compute_density(self, content: str) -> float:
        """Compute information density using character entropy.

        Shannon entropy normalized to 0-1 range.
        Higher entropy = more information density.

        Args:
            content: Text content

        Returns:
            Density score between 0.0 and 1.0
        """
        if not content:
            return 0.0

        # Character frequency
        freq: dict[str, int] = {}
        for char in content:
            freq[char] = freq.get(char, 0) + 1

        # Shannon entropy
        length = len(content)
        entropy = -sum(
            (count / length) * math.log2(count / length) for count in freq.values()
        )

        # Normalize (max entropy for printable ASCII ~ 7 bits)
        return float(min(entropy / 7.0, 1.0))

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Cosine similarity between -1.0 and 1.0, clamped to [0, 1]
        """
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Clamp to [0, 1] since we're measuring similarity, not difference
        return max(0.0, min(1.0, dot / (norm1 * norm2)))

    def _tfidf_overlap(self, query: str, content: str) -> float:
        """Compute simple TF-IDF-based keyword overlap.

        Args:
            query: Query string
            content: Content to check against

        Returns:
            Overlap score between 0.0 and 1.0
        """
        # Normalize and tokenize
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        if not query_words:
            return 0.0

        # Simple overlap ratio
        overlap = query_words & content_words
        return len(overlap) / len(query_words)

    def _estimate_tokens(self, content: str) -> int:
        """Estimate token count.

        Uses approximation of ~4 characters per token for English text.

        Args:
            content: Text content

        Returns:
            Estimated token count
        """
        return max(1, len(content) // 4)

    def get_scoring_stats(self, scored_items: list[ScoredContext]) -> dict[str, Any]:
        """Get statistics about scored context items.

        Args:
            scored_items: List of scored context items

        Returns:
            Dictionary with scoring statistics
        """
        if not scored_items:
            return {
                "count": 0,
                "total_tokens": 0,
                "avg_score": 0.0,
                "min_score": 0.0,
                "max_score": 0.0,
                "sources": {},
            }

        sources: dict[str, int] = {}
        for item in scored_items:
            sources[item.source] = sources.get(item.source, 0) + 1

        scores = [item.final_score for item in scored_items]
        tokens = sum(item.token_count for item in scored_items)

        return {
            "count": len(scored_items),
            "total_tokens": tokens,
            "avg_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "avg_relevance": sum(i.relevance_score for i in scored_items)
            / len(scored_items),
            "avg_recency": sum(i.recency_weight for i in scored_items)
            / len(scored_items),
            "avg_density": sum(i.information_density for i in scored_items)
            / len(scored_items),
            "sources": sources,
        }
