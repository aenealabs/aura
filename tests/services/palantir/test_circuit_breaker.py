"""
Tests for Palantir Circuit Breaker

Tests circuit breaker configuration, fallback cache, and registry.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.cloud_discovery.circuit_breaker import CircuitState
from src.services.palantir.circuit_breaker import (
    PALANTIR_CIRCUIT_CONFIG,
    PALANTIR_CRITICAL_CIRCUIT_CONFIG,
    FallbackCache,
    FallbackCacheEntry,
    PalantirCircuitBreaker,
    PalantirCircuitBreakerRegistry,
    get_palantir_circuit_breaker,
    get_palantir_circuit_registry,
)
from src.services.palantir.types import AssetContext, ThreatContext

# =============================================================================
# Configuration Tests
# =============================================================================


class TestPalantirCircuitConfig:
    """Tests for Palantir circuit breaker configuration."""

    def test_standard_config(self):
        """Test standard circuit config values."""
        assert PALANTIR_CIRCUIT_CONFIG.failure_threshold == 5
        assert PALANTIR_CIRCUIT_CONFIG.recovery_timeout_seconds == 60
        assert PALANTIR_CIRCUIT_CONFIG.success_threshold == 3
        assert PALANTIR_CIRCUIT_CONFIG.half_open_max_calls == 1

    def test_critical_config(self):
        """Test critical circuit config values."""
        assert PALANTIR_CRITICAL_CIRCUIT_CONFIG.failure_threshold == 3
        assert PALANTIR_CRITICAL_CIRCUIT_CONFIG.recovery_timeout_seconds == 30
        assert PALANTIR_CRITICAL_CIRCUIT_CONFIG.success_threshold == 2
        assert PALANTIR_CRITICAL_CIRCUIT_CONFIG.half_open_max_calls == 2


# =============================================================================
# FallbackCacheEntry Tests
# =============================================================================


class TestFallbackCacheEntry:
    """Tests for FallbackCacheEntry dataclass."""

    def test_create_entry(self):
        """Test creating cache entry."""
        entry = FallbackCacheEntry(
            data={"key": "value"},
            cached_at=datetime.now(timezone.utc),
        )
        assert entry.ttl_seconds == 3600.0
        assert entry.is_expired is False

    def test_is_expired_false(self):
        """Test is_expired when not expired."""
        entry = FallbackCacheEntry(
            data={},
            cached_at=datetime.now(timezone.utc),
            ttl_seconds=3600.0,
        )
        assert entry.is_expired is False

    def test_is_expired_true(self):
        """Test is_expired when expired."""
        entry = FallbackCacheEntry(
            data={},
            cached_at=datetime.now(timezone.utc) - timedelta(hours=2),
            ttl_seconds=3600.0,
        )
        assert entry.is_expired is True


# =============================================================================
# FallbackCache Tests
# =============================================================================


class TestFallbackCache:
    """Tests for FallbackCache."""

    @pytest.fixture
    def cache(self) -> FallbackCache:
        return FallbackCache()

    @pytest.fixture
    def sample_threat(self) -> ThreatContext:
        return ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
            cves=["CVE-2024-1234"],
        )

    @pytest.fixture
    def sample_asset(self) -> AssetContext:
        return AssetContext(asset_id="asset-001", criticality_score=9)

    def test_set_and_get_threat(
        self, cache: FallbackCache, sample_threat: ThreatContext
    ):
        """Test setting and getting threat from cache."""
        cache.set_threat("CVE-2024-1234", sample_threat)
        result = cache.get_threat("CVE-2024-1234")
        assert result is not None
        assert result.threat_id == "threat-001"

    def test_get_threat_not_found(self, cache: FallbackCache):
        """Test getting non-existent threat."""
        result = cache.get_threat("CVE-UNKNOWN")
        assert result is None

    def test_get_threat_expired(
        self, cache: FallbackCache, sample_threat: ThreatContext
    ):
        """Test getting expired threat."""
        cache.set_threat("CVE-2024-1234", sample_threat, ttl_seconds=0.001)
        # Wait for expiry
        import time

        time.sleep(0.01)
        result = cache.get_threat("CVE-2024-1234")
        assert result is None

    def test_set_and_get_asset(self, cache: FallbackCache, sample_asset: AssetContext):
        """Test setting and getting asset from cache."""
        cache.set_asset("repo-001", sample_asset)
        result = cache.get_asset("repo-001")
        assert result is not None
        assert result.asset_id == "asset-001"

    def test_get_asset_not_found(self, cache: FallbackCache):
        """Test getting non-existent asset."""
        result = cache.get_asset("repo-unknown")
        assert result is None

    def test_clear_expired(
        self,
        cache: FallbackCache,
        sample_threat: ThreatContext,
        sample_asset: AssetContext,
    ):
        """Test clearing expired entries."""
        cache.set_threat("CVE-OLD", sample_threat, ttl_seconds=0.001)
        cache.set_asset("repo-OLD", sample_asset, ttl_seconds=0.001)
        cache.set_threat("CVE-NEW", sample_threat, ttl_seconds=3600)

        import time

        time.sleep(0.01)

        removed = cache.clear_expired()
        assert removed == 2
        assert cache.get_threat("CVE-NEW") is not None


# =============================================================================
# PalantirCircuitBreaker Tests
# =============================================================================


class TestPalantirCircuitBreaker:
    """Tests for PalantirCircuitBreaker."""

    @pytest.fixture
    def breaker(self) -> PalantirCircuitBreaker:
        return PalantirCircuitBreaker(service="test")

    def test_init(self, breaker: PalantirCircuitBreaker):
        """Test initialization."""
        assert breaker.provider == "palantir"
        assert breaker.service == "test"
        assert breaker.config == PALANTIR_CIRCUIT_CONFIG

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        breaker = PalantirCircuitBreaker(
            service="critical",
            config=PALANTIR_CRITICAL_CIRCUIT_CONFIG,
        )
        assert breaker.config.failure_threshold == 3

    def test_fallback_cache_property(self, breaker: PalantirCircuitBreaker):
        """Test fallback_cache property."""
        assert breaker.fallback_cache is not None
        assert isinstance(breaker.fallback_cache, FallbackCache)

    def test_cache_threat_context(self, breaker: PalantirCircuitBreaker):
        """Test caching threat context."""
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
            cves=["CVE-2024-1234"],
        )
        breaker.cache_threat_context("CVE-2024-1234", threat)
        result = breaker._fallback_cache.get_threat("CVE-2024-1234")
        assert result is not None

    def test_cache_asset_context(self, breaker: PalantirCircuitBreaker):
        """Test caching asset context."""
        asset = AssetContext(asset_id="asset-001", criticality_score=9)
        breaker.cache_asset_context("repo-001", asset)
        result = breaker._fallback_cache.get_asset("repo-001")
        assert result is not None

    def test_get_fallback_threat_context(self, breaker: PalantirCircuitBreaker):
        """Test getting fallback threat context."""
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
            cves=["CVE-2024-1234"],
        )
        breaker.cache_threat_context("CVE-2024-1234", threat)

        results = breaker.get_fallback_threat_context(["CVE-2024-1234", "CVE-UNKNOWN"])
        assert len(results) == 1
        assert results[0].threat_id == "threat-001"

    def test_get_fallback_asset_context(self, breaker: PalantirCircuitBreaker):
        """Test getting fallback asset context."""
        asset = AssetContext(asset_id="asset-001", criticality_score=9)
        breaker.cache_asset_context("repo-001", asset)

        result = breaker.get_fallback_asset_context("repo-001")
        assert result is not None
        assert result.asset_id == "asset-001"

    def test_get_fallback_asset_context_not_found(
        self, breaker: PalantirCircuitBreaker
    ):
        """Test getting non-existent fallback asset."""
        result = breaker.get_fallback_asset_context("repo-unknown")
        assert result is None

    def test_get_metrics(self, breaker: PalantirCircuitBreaker):
        """Test get_metrics includes cache stats."""
        metrics = breaker.get_metrics()
        assert "fallback_cache" in metrics
        assert "threat_entries" in metrics["fallback_cache"]
        assert "asset_entries" in metrics["fallback_cache"]


# =============================================================================
# PalantirCircuitBreakerRegistry Tests
# =============================================================================


class TestPalantirCircuitBreakerRegistry:
    """Tests for PalantirCircuitBreakerRegistry."""

    @pytest.fixture
    def registry(self) -> PalantirCircuitBreakerRegistry:
        return PalantirCircuitBreakerRegistry()

    def test_init(self, registry: PalantirCircuitBreakerRegistry):
        """Test initialization."""
        assert registry.default_config == PALANTIR_CIRCUIT_CONFIG

    def test_get_palantir_breaker_creates_new(
        self, registry: PalantirCircuitBreakerRegistry
    ):
        """Test get_palantir_breaker creates new breaker."""
        breaker = registry.get_palantir_breaker("ontology")
        assert isinstance(breaker, PalantirCircuitBreaker)
        assert breaker.service == "ontology"

    def test_get_palantir_breaker_returns_existing(
        self, registry: PalantirCircuitBreakerRegistry
    ):
        """Test get_palantir_breaker returns existing breaker."""
        breaker1 = registry.get_palantir_breaker("ontology")
        breaker2 = registry.get_palantir_breaker("ontology")
        assert breaker1 is breaker2

    def test_get_palantir_breaker_custom_config(
        self, registry: PalantirCircuitBreakerRegistry
    ):
        """Test get_palantir_breaker with custom config."""
        breaker = registry.get_palantir_breaker(
            "critical", config=PALANTIR_CRITICAL_CIRCUIT_CONFIG
        )
        assert breaker.config == PALANTIR_CRITICAL_CIRCUIT_CONFIG

    def test_get_all_palantir_states(self, registry: PalantirCircuitBreakerRegistry):
        """Test get_all_palantir_states."""
        registry.get_palantir_breaker("ontology")
        registry.get_palantir_breaker("foundry")

        states = registry.get_all_palantir_states()
        assert len(states) == 2
        assert "palantir:ontology" in states
        assert "palantir:foundry" in states

    def test_any_circuit_open_false(self, registry: PalantirCircuitBreakerRegistry):
        """Test any_circuit_open when all closed."""
        registry.get_palantir_breaker("ontology")
        assert registry.any_circuit_open() is False

    def test_any_circuit_open_true(self, registry: PalantirCircuitBreakerRegistry):
        """Test any_circuit_open when one is open."""
        breaker = registry.get_palantir_breaker("ontology")
        # Manually set to open
        breaker._state.state = CircuitState.OPEN
        assert registry.any_circuit_open() is True

    def test_get_available_services(self, registry: PalantirCircuitBreakerRegistry):
        """Test get_available_services."""
        registry.get_palantir_breaker("ontology")
        registry.get_palantir_breaker("foundry")

        services = registry.get_available_services()
        assert "ontology" in services
        assert "foundry" in services


# =============================================================================
# Module Function Tests
# =============================================================================


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_palantir_circuit_registry(self):
        """Test get_palantir_circuit_registry returns singleton."""
        registry1 = get_palantir_circuit_registry()
        registry2 = get_palantir_circuit_registry()
        assert registry1 is registry2

    def test_get_palantir_circuit_breaker(self):
        """Test get_palantir_circuit_breaker convenience function."""
        breaker = get_palantir_circuit_breaker("test-service")
        assert isinstance(breaker, PalantirCircuitBreaker)
        assert breaker.service == "test-service"


# =============================================================================
# Circuit Breaker State Tests
# =============================================================================


class TestCircuitBreakerStates:
    """Tests for circuit breaker state transitions."""

    @pytest.fixture
    def breaker(self) -> PalantirCircuitBreaker:
        return PalantirCircuitBreaker(service="test")

    def test_initial_state_closed(self, breaker: PalantirCircuitBreaker):
        """Test initial state is closed."""
        assert breaker.is_closed is True
        assert breaker.is_open is False

    def test_record_failures_opens_circuit(self, breaker: PalantirCircuitBreaker):
        """Test recording failures opens circuit."""
        for _ in range(5):
            breaker.record_failure(Exception("Test error"))
        assert breaker.is_open is True

    def test_record_success_after_failure(self, breaker: PalantirCircuitBreaker):
        """Test recording success resets failure count."""
        breaker.record_failure(Exception("Error"))
        breaker.record_success()
        # Failure count should reset
        assert breaker._state.failure_count == 0

    def test_reset(self, breaker: PalantirCircuitBreaker):
        """Test reset returns to closed state."""
        for _ in range(5):
            breaker.record_failure(Exception("Error"))
        assert breaker.is_open is True

        breaker.reset()
        assert breaker.is_closed is True
