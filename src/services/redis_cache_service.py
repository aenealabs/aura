"""
Redis Cache Service for Production State Management

Provides Redis-backed caching with graceful fallback to in-memory storage
when Redis is unavailable. Used by BedrockLLMService for:
- Cost tracking (daily_spend, monthly_spend)
- Rate limiting (request_history)
- Response caching

Environment Variables:
    REDIS_HOST: Redis host (default: localhost)
    REDIS_PORT: Redis port (default: 6379)
    REDIS_PASSWORD: Redis password (optional)
    REDIS_DB: Redis database number (default: 0)
    REDIS_SSL: Enable SSL/TLS (default: false)
    REDIS_CONNECT_TIMEOUT: Connection timeout in seconds (default: 5)
    REDIS_SOCKET_TIMEOUT: Socket timeout in seconds (default: 5)

Author: Project Aura Team
"""

import json
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Redis imports (optional dependency)
try:
    import redis
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import RedisError
    from redis.exceptions import TimeoutError as RedisTimeoutError

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.info("redis package not installed - using in-memory cache only")


class CacheBackend(Enum):
    """Cache backend type."""

    REDIS = "redis"
    MEMORY = "memory"


@dataclass
class CacheConfig:
    """Configuration for Redis cache service."""

    host: str = "localhost"
    port: int = 6379
    password: str | None = None
    db: int = 0
    ssl: bool = False
    connect_timeout: float = 5.0
    socket_timeout: float = 5.0
    max_connections: int = 10
    retry_on_timeout: bool = True
    decode_responses: bool = True
    # Key prefixes for namespacing
    key_prefix: str = "aura:llm:"
    # TTL settings (seconds)
    cost_ttl: int = 86400 * 32  # 32 days (for monthly tracking)
    rate_limit_ttl: int = 86400  # 24 hours
    response_cache_ttl: int = 86400  # 24 hours (default)
    # Memory cache limits (fallback)
    max_memory_cache_size: int = 1000
    max_rate_history_size: int = 10000

    @classmethod
    def from_env(cls) -> "CacheConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD"),
            db=int(os.getenv("REDIS_DB", "0")),
            ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
            connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT", "5")),
            socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
        )


@dataclass
class LRUCacheEntry:
    """Entry in the LRU cache with timestamp."""

    value: Any
    timestamp: float
    ttl: float = 0.0  # 0 = no expiration

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl <= 0:
            return False
        return time.time() - self.timestamp > self.ttl


class RedisCacheService:
    """
    Redis-backed cache service with in-memory fallback.

    Provides thread-safe caching operations with automatic failover
    to in-memory storage when Redis is unavailable.

    Features:
    - Automatic Redis connection with retry
    - Graceful fallback to in-memory when Redis fails
    - LRU eviction for memory cache using OrderedDict (O(1) operations)
    - Key namespacing with configurable prefix
    - TTL support for all cached values
    - Cost tracking aggregation (daily/monthly)
    - Rate limiting with sliding window

    Example:
        >>> cache = RedisCacheService()
        >>> cache.set_cost("daily", 1.50)
        >>> cache.increment_cost("daily", 0.25)
        >>> print(cache.get_cost("daily"))  # 1.75
    """

    def __init__(self, config: CacheConfig | None = None):
        """
        Initialize Redis cache service.

        Args:
            config: Cache configuration (defaults to env-based config)
        """
        self.config = config or CacheConfig.from_env()
        self._redis_client: Any | None = None
        self._backend = CacheBackend.MEMORY
        self._connection_attempts = 0
        self._last_connection_attempt = 0.0
        self._connection_backoff = 30.0  # seconds between reconnection attempts

        # In-memory fallback caches using OrderedDict for O(1) LRU
        self._memory_cache: OrderedDict[str, LRUCacheEntry] = OrderedDict()
        self._cost_cache: dict[str, float] = {}
        self._rate_history: OrderedDict[str, float] = OrderedDict()

        # Try to connect to Redis
        self._init_redis()

        logger.info(
            f"RedisCacheService initialized: backend={self._backend.value}, "
            f"host={self.config.host}:{self.config.port}"
        )

    def _init_redis(self) -> None:
        """Initialize Redis connection."""
        if not REDIS_AVAILABLE:
            logger.info("Redis package not available - using memory backend")
            return

        try:
            self._redis_client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                password=self.config.password,
                db=self.config.db,
                ssl=self.config.ssl,
                socket_connect_timeout=self.config.connect_timeout,
                socket_timeout=self.config.socket_timeout,
                max_connections=self.config.max_connections,
                retry_on_timeout=self.config.retry_on_timeout,
                decode_responses=self.config.decode_responses,
            )

            # Test connection
            self._redis_client.ping()
            self._backend = CacheBackend.REDIS
            self._connection_attempts = 0
            logger.info(
                f"Redis connected: {self.config.host}:{self.config.port}/{self.config.db}"
            )

        except Exception as e:
            logger.warning(f"Redis connection failed: {e} - using memory backend")
            self._redis_client = None
            self._backend = CacheBackend.MEMORY
            self._connection_attempts += 1
            self._last_connection_attempt = time.time()

    def _try_reconnect(self) -> bool:
        """
        Attempt to reconnect to Redis with backoff.

        Returns:
            True if reconnected, False otherwise
        """
        if self._backend == CacheBackend.REDIS:
            return True

        # Check backoff period
        elapsed = time.time() - self._last_connection_attempt
        if elapsed < self._connection_backoff:
            return False

        logger.info("Attempting Redis reconnection...")
        self._init_redis()
        return self._backend == CacheBackend.REDIS

    def _make_key(self, namespace: str, key: str) -> str:
        """Create namespaced Redis key."""
        return f"{self.config.key_prefix}{namespace}:{key}"

    def _evict_lru_memory(self) -> None:
        """Evict oldest entries from memory cache if over limit (O(1) with OrderedDict)."""
        while len(self._memory_cache) > self.config.max_memory_cache_size:
            # popitem(last=False) removes the oldest (first) item in O(1)
            evicted_key, _ = self._memory_cache.popitem(last=False)
            logger.debug(f"LRU evicted from memory cache: {evicted_key}")

    def _evict_lru_rate_history(self) -> None:
        """Evict oldest entries from rate history if over limit (O(1) with OrderedDict)."""
        while len(self._rate_history) > self.config.max_rate_history_size:
            self._rate_history.popitem(last=False)

    # =========================================================================
    # Cost Tracking Methods
    # =========================================================================

    def get_cost(self, period: str) -> float:
        """
        Get cost for a period (e.g., 'daily:2024-01-15' or 'monthly:2024-01').

        Args:
            period: Cost period identifier

        Returns:
            Cost amount in USD
        """
        key = self._make_key("cost", period)

        # Try Redis first
        if self._backend == CacheBackend.REDIS and self._redis_client:
            try:
                value = self._redis_client.get(key)
                if value is not None:
                    return float(value)
                return 0.0
            except (RedisError, RedisConnectionError, RedisTimeoutError) as e:
                logger.warning(f"Redis get_cost failed: {e}")
                self._backend = CacheBackend.MEMORY

        # Fall back to memory
        return self._cost_cache.get(period, 0.0)

    def set_cost(self, period: str, amount: float) -> bool:
        """
        Set cost for a period.

        Args:
            period: Cost period identifier
            amount: Cost amount in USD

        Returns:
            True if successful
        """
        key = self._make_key("cost", period)

        # Try Redis first
        if self._backend == CacheBackend.REDIS and self._redis_client:
            try:
                self._redis_client.setex(key, self.config.cost_ttl, str(amount))
                return True
            except (RedisError, RedisConnectionError, RedisTimeoutError) as e:
                logger.warning(f"Redis set_cost failed: {e}")
                self._backend = CacheBackend.MEMORY

        # Fall back to memory
        self._cost_cache[period] = amount
        return True

    def increment_cost(self, period: str, amount: float) -> float:
        """
        Atomically increment cost for a period.

        Args:
            period: Cost period identifier
            amount: Amount to add in USD

        Returns:
            New total cost
        """
        key = self._make_key("cost", period)

        # Try Redis first (atomic increment)
        if self._backend == CacheBackend.REDIS and self._redis_client:
            try:
                # Use INCRBYFLOAT for atomic increment
                # First check if key exists, if not set with TTL
                if not self._redis_client.exists(key):
                    self._redis_client.setex(key, self.config.cost_ttl, "0")
                new_value = self._redis_client.incrbyfloat(key, amount)
                return float(new_value)
            except (RedisError, RedisConnectionError, RedisTimeoutError) as e:
                logger.warning(f"Redis increment_cost failed: {e}")
                self._backend = CacheBackend.MEMORY

        # Fall back to memory (not atomic but acceptable for fallback)
        current = self._cost_cache.get(period, 0.0)
        new_total = current + amount
        self._cost_cache[period] = new_total
        return new_total

    def get_daily_cost(self) -> float:
        """Get today's cost."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        return self.get_cost(f"daily:{today}")

    def get_monthly_cost(self) -> float:
        """Get current month's cost."""
        month = datetime.now(UTC).strftime("%Y-%m")
        return self.get_cost(f"monthly:{month}")

    def add_cost(self, amount: float) -> tuple[float, float]:
        """
        Add cost to both daily and monthly totals.

        Args:
            amount: Cost amount in USD

        Returns:
            Tuple of (new_daily_total, new_monthly_total)
        """
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        month = datetime.now(UTC).strftime("%Y-%m")

        daily = self.increment_cost(f"daily:{today}", amount)
        monthly = self.increment_cost(f"monthly:{month}", amount)

        return daily, monthly

    # =========================================================================
    # Rate Limiting Methods
    # =========================================================================

    def record_request(self, identifier: str = "global") -> int:
        """
        Record a request timestamp for rate limiting.

        Args:
            identifier: Rate limit bucket identifier

        Returns:
            Current request count in the last minute
        """
        now = time.time()
        key = self._make_key("rate", identifier)

        # Try Redis first (using sorted set for time-based expiration)
        if self._backend == CacheBackend.REDIS and self._redis_client:
            try:
                # Add current timestamp to sorted set
                self._redis_client.zadd(key, {str(now): now})
                # Remove old entries (older than 24 hours)
                cutoff = now - 86400
                self._redis_client.zremrangebyscore(key, 0, cutoff)
                # Set key TTL
                self._redis_client.expire(key, self.config.rate_limit_ttl)
                # Count recent requests (last minute)
                minute_ago = now - 60
                return self._redis_client.zcount(key, minute_ago, now)
            except (RedisError, RedisConnectionError, RedisTimeoutError) as e:
                logger.warning(f"Redis record_request failed: {e}")
                self._backend = CacheBackend.MEMORY

        # Fall back to memory using OrderedDict
        entry_key = f"{identifier}:{now}"
        self._rate_history[entry_key] = now
        self._rate_history.move_to_end(entry_key)  # Mark as most recently used
        self._evict_lru_rate_history()

        # Count requests in last minute
        minute_ago = now - 60
        return sum(1 for ts in self._rate_history.values() if ts > minute_ago)

    def get_request_count(
        self, identifier: str = "global", window_seconds: int = 60
    ) -> int:
        """
        Get request count within a time window.

        Args:
            identifier: Rate limit bucket identifier
            window_seconds: Time window in seconds

        Returns:
            Number of requests in window
        """
        now = time.time()
        key = self._make_key("rate", identifier)

        # Try Redis first
        if self._backend == CacheBackend.REDIS and self._redis_client:
            try:
                cutoff = now - window_seconds
                return self._redis_client.zcount(key, cutoff, now)
            except (RedisError, RedisConnectionError, RedisTimeoutError) as e:
                logger.warning(f"Redis get_request_count failed: {e}")
                self._backend = CacheBackend.MEMORY

        # Fall back to memory
        cutoff = now - window_seconds
        return sum(1 for ts in self._rate_history.values() if ts > cutoff)

    def get_request_history(
        self, identifier: str = "global", max_age_seconds: int = 86400
    ) -> list[float]:
        """
        Get request timestamps within a time window.

        Args:
            identifier: Rate limit bucket identifier
            max_age_seconds: Maximum age of timestamps to return

        Returns:
            List of timestamps
        """
        now = time.time()
        key = self._make_key("rate", identifier)
        cutoff = now - max_age_seconds

        # Try Redis first
        if self._backend == CacheBackend.REDIS and self._redis_client:
            try:
                # Get all timestamps in range
                members = self._redis_client.zrangebyscore(key, cutoff, now)
                return [float(m) for m in members]
            except (RedisError, RedisConnectionError, RedisTimeoutError) as e:
                logger.warning(f"Redis get_request_history failed: {e}")
                self._backend = CacheBackend.MEMORY

        # Fall back to memory
        return [ts for ts in self._rate_history.values() if ts > cutoff]

    def clear_rate_history(self, identifier: str = "global") -> bool:
        """Clear rate limiting history."""
        key = self._make_key("rate", identifier)

        if self._backend == CacheBackend.REDIS and self._redis_client:
            try:
                self._redis_client.delete(key)
                return True
            except (RedisError, RedisConnectionError, RedisTimeoutError):
                pass

        # Clear memory
        to_remove = [k for k in self._rate_history.keys() if k.startswith(identifier)]
        for k in to_remove:
            del self._rate_history[k]
        return True

    # =========================================================================
    # Response Cache Methods
    # =========================================================================

    def get_response(self, cache_key: str) -> dict[str, Any] | None:
        """
        Get cached LLM response.

        Args:
            cache_key: Response cache key (usually hash of prompt+params)

        Returns:
            Cached response dict or None if not found/expired
        """
        key = self._make_key("response", cache_key)

        # Try Redis first
        if self._backend == CacheBackend.REDIS and self._redis_client:
            try:
                value = self._redis_client.get(key)
                if value:
                    return json.loads(value)
                return None
            except (RedisError, RedisConnectionError, RedisTimeoutError) as e:
                logger.warning(f"Redis get_response failed: {e}")
                self._backend = CacheBackend.MEMORY

        # Fall back to memory
        entry = self._memory_cache.get(cache_key)
        if entry is None:
            return None

        if entry.is_expired():
            del self._memory_cache[cache_key]
            return None

        # Move to end (mark as recently used) - O(1) operation
        self._memory_cache.move_to_end(cache_key)
        return entry.value

    def set_response(
        self, cache_key: str, response: dict[str, Any], ttl: int | None = None
    ) -> bool:
        """
        Cache an LLM response.

        Args:
            cache_key: Response cache key
            response: Response dict to cache
            ttl: Time-to-live in seconds (default from config)

        Returns:
            True if successful
        """
        key = self._make_key("response", cache_key)
        ttl = ttl or self.config.response_cache_ttl

        # Try Redis first
        if self._backend == CacheBackend.REDIS and self._redis_client:
            try:
                self._redis_client.setex(key, ttl, json.dumps(response))
                return True
            except (RedisError, RedisConnectionError, RedisTimeoutError) as e:
                logger.warning(f"Redis set_response failed: {e}")
                self._backend = CacheBackend.MEMORY

        # Fall back to memory with LRU eviction
        self._memory_cache[cache_key] = LRUCacheEntry(
            value=response,
            timestamp=time.time(),
            ttl=float(ttl),
        )
        # Move to end (mark as recently used)
        self._memory_cache.move_to_end(cache_key)
        self._evict_lru_memory()
        return True

    def delete_response(self, cache_key: str) -> bool:
        """Delete a cached response."""
        key = self._make_key("response", cache_key)

        if self._backend == CacheBackend.REDIS and self._redis_client:
            try:
                self._redis_client.delete(key)
            except (RedisError, RedisConnectionError, RedisTimeoutError):
                pass

        # Also remove from memory
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]

        return True

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @property
    def backend(self) -> CacheBackend:
        """Get current backend type."""
        return self._backend

    @property
    def is_redis_connected(self) -> bool:
        """Check if Redis is connected."""
        if not self._redis_client:
            return False
        try:
            self._redis_client.ping()
            return True
        except Exception:
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        stats = {
            "backend": self._backend.value,
            "redis_available": REDIS_AVAILABLE,
            "redis_connected": self.is_redis_connected,
            "memory_cache_size": len(self._memory_cache),
            "memory_cache_max_size": self.config.max_memory_cache_size,
            "rate_history_size": len(self._rate_history),
            "cost_cache_entries": len(self._cost_cache),
            "connection_attempts": self._connection_attempts,
        }

        if self._backend == CacheBackend.REDIS and self._redis_client:
            try:
                info = self._redis_client.info("memory")
                stats["redis_used_memory_mb"] = info.get("used_memory", 0) / 1024 / 1024
            except Exception:
                pass

        return stats

    def clear_all(self) -> bool:
        """Clear all caches (use with caution)."""
        self._memory_cache.clear()
        self._cost_cache.clear()
        self._rate_history.clear()

        if self._backend == CacheBackend.REDIS and self._redis_client:
            try:
                # Delete all keys with our prefix
                pattern = f"{self.config.key_prefix}*"
                cursor = 0
                while True:
                    cursor, keys = self._redis_client.scan(
                        cursor=cursor, match=pattern, count=100
                    )
                    if keys:
                        self._redis_client.delete(*keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning(f"Redis clear_all failed: {e}")

        logger.info("All caches cleared")
        return True

    def close(self) -> None:
        """Close Redis connection."""
        if self._redis_client:
            try:
                self._redis_client.close()
            except Exception:
                pass
            self._redis_client = None
            self._backend = CacheBackend.MEMORY
            logger.info("Redis connection closed")


# Singleton instance for shared use
_cache_instance: RedisCacheService | None = None


def get_cache_service(config: CacheConfig | None = None) -> RedisCacheService:
    """
    Get or create the singleton cache service instance.

    Args:
        config: Optional cache configuration

    Returns:
        RedisCacheService instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCacheService(config)
    return _cache_instance


def create_cache_service(config: CacheConfig | None = None) -> RedisCacheService:
    """
    Create a new cache service instance (non-singleton).

    Args:
        config: Optional cache configuration

    Returns:
        New RedisCacheService instance
    """
    return RedisCacheService(config)


if __name__ == "__main__":
    # Demo/test usage
    logging.basicConfig(level=logging.INFO)

    print("Project Aura - Redis Cache Service Demo")
    print("=" * 60)

    # Create cache service
    cache = create_cache_service()

    print(f"\nBackend: {cache.backend.value}")
    print(f"Redis connected: {cache.is_redis_connected}")

    # Test cost tracking
    print("\n--- Cost Tracking ---")
    daily, monthly = cache.add_cost(1.50)
    print(f"Added $1.50 - Daily: ${daily:.2f}, Monthly: ${monthly:.2f}")

    daily, monthly = cache.add_cost(0.75)
    print(f"Added $0.75 - Daily: ${daily:.2f}, Monthly: ${monthly:.2f}")

    # Test rate limiting
    print("\n--- Rate Limiting ---")
    for i in range(5):
        count = cache.record_request()
        print(f"Request {i + 1}: {count} requests in last minute")

    # Test response cache
    print("\n--- Response Cache ---")
    cache.set_response("test_key", {"response": "Hello", "tokens": 10}, ttl=300)
    result = cache.get_response("test_key")
    print(f"Cached response: {result}")

    # Show stats
    print("\n--- Statistics ---")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("Demo complete!")
