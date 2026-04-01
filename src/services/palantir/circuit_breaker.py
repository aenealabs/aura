"""
Palantir AIP Circuit Breaker Configuration

Implements ADR-074: Palantir AIP Integration

Provides Palantir-specific circuit breaker configuration and fallback
behavior for resilient API calls.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.services.cloud_discovery.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
)
from src.services.palantir.types import AssetContext, ThreatContext

logger = logging.getLogger(__name__)


# =============================================================================
# Palantir-Specific Configuration
# =============================================================================

# Per ADR-074: 5 failures in 30s opens circuit, 60s recovery timeout
PALANTIR_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout_seconds=60,
    success_threshold=3,
    half_open_max_calls=1,
)

# Separate config for high-priority operations
PALANTIR_CRITICAL_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,  # Fewer failures tolerated
    recovery_timeout_seconds=30,  # Faster recovery attempts
    success_threshold=2,
    half_open_max_calls=2,  # Allow more test calls
)


# =============================================================================
# Fallback Cache
# =============================================================================


@dataclass
class FallbackCacheEntry:
    """Cache entry for fallback data."""

    data: Any
    cached_at: datetime
    ttl_seconds: float = 3600.0  # 1 hour default

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        elapsed = (datetime.now(timezone.utc) - self.cached_at).total_seconds()
        return elapsed > self.ttl_seconds


@dataclass
class FallbackCache:
    """Cache for fallback data when circuit is open."""

    threat_cache: dict[str, FallbackCacheEntry] = field(default_factory=dict)
    asset_cache: dict[str, FallbackCacheEntry] = field(default_factory=dict)

    def get_threat(self, cve_id: str) -> ThreatContext | None:
        """Get cached threat context."""
        entry = self.threat_cache.get(cve_id)
        if entry and not entry.is_expired:
            return entry.data
        return None

    def set_threat(
        self,
        cve_id: str,
        threat: ThreatContext,
        ttl_seconds: float = 3600.0,
    ) -> None:
        """Cache threat context."""
        self.threat_cache[cve_id] = FallbackCacheEntry(
            data=threat,
            cached_at=datetime.now(timezone.utc),
            ttl_seconds=ttl_seconds,
        )

    def get_asset(self, repo_id: str) -> AssetContext | None:
        """Get cached asset context."""
        entry = self.asset_cache.get(repo_id)
        if entry and not entry.is_expired:
            return entry.data
        return None

    def set_asset(
        self,
        repo_id: str,
        asset: AssetContext,
        ttl_seconds: float = 3600.0,
    ) -> None:
        """Cache asset context."""
        self.asset_cache[repo_id] = FallbackCacheEntry(
            data=asset,
            cached_at=datetime.now(timezone.utc),
            ttl_seconds=ttl_seconds,
        )

    def clear_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        removed = 0
        for cache in [self.threat_cache, self.asset_cache]:
            expired_keys = [k for k, v in cache.items() if v.is_expired]
            for key in expired_keys:
                del cache[key]
                removed += 1
        return removed


# =============================================================================
# Palantir Circuit Breaker
# =============================================================================


class PalantirCircuitBreaker(CircuitBreaker):
    """
    Circuit breaker with Palantir-specific fallback behavior.

    When the circuit is open, provides cached data from the fallback cache
    instead of failing immediately. This ensures graceful degradation.

    Usage:
        >>> breaker = PalantirCircuitBreaker()
        >>> async with breaker:
        ...     result = await palantir_api_call()

        # When circuit is open, get fallback data
        >>> if breaker.is_open:
        ...     threats = breaker.get_fallback_threat_context(["CVE-2024-1234"])
    """

    def __init__(
        self,
        service: str = "integration",
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        """
        Initialize Palantir circuit breaker.

        Args:
            service: Service name (e.g., "ontology", "foundry", "integration")
            config: Optional custom configuration
        """
        super().__init__(
            provider="palantir",
            service=service,
            config=config or PALANTIR_CIRCUIT_CONFIG,
        )
        self._fallback_cache = FallbackCache()

    @property
    def fallback_cache(self) -> FallbackCache:
        """Get fallback cache."""
        return self._fallback_cache

    def cache_threat_context(
        self,
        cve_id: str,
        threat: ThreatContext,
        ttl_seconds: float = 3600.0,
    ) -> None:
        """
        Cache threat context for fallback use.

        Args:
            cve_id: CVE identifier
            threat: Threat context to cache
            ttl_seconds: Cache TTL in seconds
        """
        self._fallback_cache.set_threat(cve_id, threat, ttl_seconds)

    def cache_asset_context(
        self,
        repo_id: str,
        asset: AssetContext,
        ttl_seconds: float = 3600.0,
    ) -> None:
        """
        Cache asset context for fallback use.

        Args:
            repo_id: Repository identifier
            asset: Asset context to cache
            ttl_seconds: Cache TTL in seconds
        """
        self._fallback_cache.set_asset(repo_id, asset, ttl_seconds)

    def get_fallback_threat_context(
        self,
        cve_ids: list[str],
    ) -> list[ThreatContext]:
        """
        Get cached threat context when circuit is open.

        Args:
            cve_ids: List of CVE identifiers

        Returns:
            List of cached ThreatContext objects (may be partial)
        """
        results = []
        for cve_id in cve_ids:
            threat = self._fallback_cache.get_threat(cve_id)
            if threat:
                results.append(threat)
        return results

    def get_fallback_asset_context(self, repo_id: str) -> AssetContext | None:
        """
        Get cached asset context when circuit is open.

        Args:
            repo_id: Repository identifier

        Returns:
            Cached AssetContext or None if not available
        """
        return self._fallback_cache.get_asset(repo_id)

    def get_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics including cache stats."""
        metrics = super().get_metrics()
        metrics.update(
            {
                "fallback_cache": {
                    "threat_entries": len(self._fallback_cache.threat_cache),
                    "asset_entries": len(self._fallback_cache.asset_cache),
                },
            }
        )
        return metrics


# =============================================================================
# Palantir Circuit Breaker Registry
# =============================================================================


class PalantirCircuitBreakerRegistry(CircuitBreakerRegistry):
    """
    Registry for Palantir circuit breakers.

    Manages circuit breakers for different Palantir services:
    - ontology: Palantir Ontology API calls
    - foundry: Palantir Foundry dataset operations
    - integration: General Palantir integration calls
    """

    def __init__(self) -> None:
        """Initialize with Palantir-specific config."""
        super().__init__(default_config=PALANTIR_CIRCUIT_CONFIG)
        self._palantir_breakers: dict[str, PalantirCircuitBreaker] = {}

    def get_palantir_breaker(
        self,
        service: str = "integration",
        config: CircuitBreakerConfig | None = None,
    ) -> PalantirCircuitBreaker:
        """
        Get or create a Palantir-specific circuit breaker.

        Args:
            service: Service name
            config: Optional custom config

        Returns:
            PalantirCircuitBreaker instance
        """
        key = f"palantir:{service}"

        if key not in self._palantir_breakers:
            self._palantir_breakers[key] = PalantirCircuitBreaker(
                service=service,
                config=config,
            )
            # Also register in parent registry
            self._breakers[key] = self._palantir_breakers[key]

        return self._palantir_breakers[key]

    def get_all_palantir_states(self) -> dict[str, dict[str, Any]]:
        """Get states of all Palantir circuit breakers."""
        return {
            key: breaker.get_metrics()
            for key, breaker in self._palantir_breakers.items()
        }

    def any_circuit_open(self) -> bool:
        """Check if any Palantir circuit is open."""
        return any(breaker.is_open for breaker in self._palantir_breakers.values())

    def get_available_services(self) -> list[str]:
        """Get list of services with closed circuits."""
        return [
            breaker.service
            for breaker in self._palantir_breakers.values()
            if breaker.is_closed and breaker.service
        ]


# =============================================================================
# Module-Level Registry
# =============================================================================

_palantir_registry: PalantirCircuitBreakerRegistry | None = None


def get_palantir_circuit_registry() -> PalantirCircuitBreakerRegistry:
    """Get the Palantir circuit breaker registry."""
    global _palantir_registry
    if _palantir_registry is None:
        _palantir_registry = PalantirCircuitBreakerRegistry()
    return _palantir_registry


def get_palantir_circuit_breaker(
    service: str = "integration",
) -> PalantirCircuitBreaker:
    """
    Convenience function to get a Palantir circuit breaker.

    Args:
        service: Service name (ontology, foundry, integration)

    Returns:
        PalantirCircuitBreaker instance
    """
    return get_palantir_circuit_registry().get_palantir_breaker(service)
