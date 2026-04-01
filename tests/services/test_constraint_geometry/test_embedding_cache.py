"""
Project Aura - CGE Embedding Cache Tests

Tests for SHA-256 hashing, LRU cache behavior, and cache hit/miss tracking.

Author: Project Aura Team
Created: 2026-02-11
"""

from unittest.mock import AsyncMock

import pytest

from src.services.constraint_geometry.config import CacheConfig
from src.services.constraint_geometry.embedding_cache import EmbeddingCache

# =============================================================================
# Hash Tests
# =============================================================================


class TestHashComputation:
    """Test deterministic hash generation."""

    def test_sha256_deterministic(self):
        """Same text always produces same hash."""
        text = "def validate_user(): pass"
        h1 = EmbeddingCache.compute_hash(text)
        h2 = EmbeddingCache.compute_hash(text)
        assert h1 == h2

    def test_different_text_different_hash(self):
        """Different text produces different hash."""
        h1 = EmbeddingCache.compute_hash("hello world")
        h2 = EmbeddingCache.compute_hash("hello world!")
        assert h1 != h2

    def test_hash_format(self):
        """Hash is a 64-character hex string."""
        h = EmbeddingCache.compute_hash("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_normalize_text(self):
        """Normalization collapses whitespace."""
        assert EmbeddingCache.normalize_text("  hello   world  ") == "hello world"
        assert EmbeddingCache.normalize_text("a\n\tb") == "a b"
        assert EmbeddingCache.normalize_text("  ") == ""


# =============================================================================
# LRU Cache Tests
# =============================================================================


class TestLRUCache:
    """Test in-process LRU cache behavior."""

    def test_put_and_get(self, cache):
        """Can store and retrieve embeddings."""
        cache.put("hash1", [1.0, 2.0, 3.0])
        result = cache.get_cached("hash1")
        assert result == [1.0, 2.0, 3.0]

    def test_miss_returns_none(self, cache):
        """Cache miss returns None."""
        assert cache.get_cached("nonexistent") is None

    def test_lru_eviction(self):
        """LRU evicts oldest entry when at capacity."""
        config = CacheConfig(lru_max_size=3, enable_redis=False)
        cache = EmbeddingCache(config=config)

        cache.put("a", [1.0])
        cache.put("b", [2.0])
        cache.put("c", [3.0])
        cache.put("d", [4.0])  # Should evict "a"

        assert cache.get_cached("a") is None  # Evicted
        assert cache.get_cached("b") == [2.0]
        assert cache.get_cached("d") == [4.0]

    def test_lru_access_refreshes(self):
        """Accessing an entry moves it to most-recently-used."""
        config = CacheConfig(lru_max_size=3, enable_redis=False)
        cache = EmbeddingCache(config=config)

        cache.put("a", [1.0])
        cache.put("b", [2.0])
        cache.put("c", [3.0])

        # Access "a" to refresh it
        cache.get_cached("a")

        # Insert "d" - should evict "b" (oldest unused), not "a"
        cache.put("d", [4.0])

        assert cache.get_cached("a") == [1.0]  # Still present
        assert cache.get_cached("b") is None  # Evicted

    def test_clear(self, cache):
        """Clear empties the cache and resets stats."""
        cache.put("a", [1.0])
        cache.clear()
        assert cache.get_cached("a") is None
        assert cache.stats["total_requests"] == 0


# =============================================================================
# Cache Hit/Miss Tracking Tests
# =============================================================================


class TestCacheStats:
    """Test cache statistics tracking."""

    @pytest.mark.asyncio
    async def test_lru_hit_tracked(self, cache):
        """LRU hit increments hit counter."""
        cache.put("hash1", [1.0, 2.0])
        await cache.get_or_compute("hash1", "text")
        assert cache.last_was_hit is True
        assert cache.stats["hits_lru"] == 1
        assert cache.stats["misses"] == 0

    @pytest.mark.asyncio
    async def test_miss_tracked(self):
        """Cache miss increments miss counter."""
        provider = AsyncMock()
        provider.compute_embedding.return_value = [1.0, 2.0, 3.0]

        config = CacheConfig(enable_redis=False, lru_max_size=100)
        cache = EmbeddingCache(provider=provider, config=config)

        await cache.get_or_compute("hash1", "some text")
        assert cache.last_was_hit is False
        assert cache.stats["misses"] == 1
        provider.compute_embedding.assert_called_once_with("some text")

    @pytest.mark.asyncio
    async def test_miss_then_hit(self):
        """Second request for same hash is a hit."""
        provider = AsyncMock()
        provider.compute_embedding.return_value = [1.0, 2.0, 3.0]

        config = CacheConfig(enable_redis=False, lru_max_size=100)
        cache = EmbeddingCache(provider=provider, config=config)

        # First call: miss
        await cache.get_or_compute("hash1", "text")
        assert cache.last_was_hit is False

        # Second call: hit
        await cache.get_or_compute("hash1", "text")
        assert cache.last_was_hit is True
        assert cache.stats["hits_lru"] == 1
        assert cache.stats["misses"] == 1

        # Provider called only once
        assert provider.compute_embedding.call_count == 1

    @pytest.mark.asyncio
    async def test_no_provider_raises(self, cache):
        """Cache miss without provider raises RuntimeError."""
        with pytest.raises(RuntimeError, match="No embedding provider"):
            await cache.get_or_compute("unknown-hash", "text")

    def test_hit_rate_calculation(self, cache):
        """Hit rate is correctly calculated."""
        cache._hits_lru = 8
        cache._hits_redis = 1
        cache._misses = 1
        stats = cache.stats
        assert stats["hit_rate"] == pytest.approx(0.9)
