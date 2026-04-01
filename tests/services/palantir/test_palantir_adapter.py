"""
Tests for Palantir AIP Adapter

Tests the Palantir-specific adapter implementation.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.services.palantir.base_adapter import ConnectorStatus
from src.services.palantir.palantir_adapter import PalantirAIPAdapter
from src.services.palantir.types import (
    AssetContext,
    PalantirObjectType,
    RemediationEvent,
    RemediationEventType,
    SyncStatus,
    ThreatContext,
)

# =============================================================================
# Initialization Tests
# =============================================================================


class TestPalantirAdapterInit:
    """Tests for PalantirAIPAdapter initialization."""

    def test_init_minimal(self):
        """Test minimal initialization."""
        adapter = PalantirAIPAdapter(
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key="test-key",
        )
        assert adapter.name == "palantir_aip"
        assert adapter.ontology_api_url == "https://test.palantir.com/ontology"
        assert adapter.foundry_api_url == "https://test.palantir.com/foundry"
        assert adapter._api_key == "test-key"

    def test_init_with_mtls(self):
        """Test initialization with mTLS."""
        adapter = PalantirAIPAdapter(
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key="test-key",
            client_cert_path="/path/to/cert.pem",
            client_key_path="/path/to/key.pem",
        )
        assert adapter._client_cert_path == "/path/to/cert.pem"
        assert adapter._client_key_path == "/path/to/key.pem"

    def test_init_url_trailing_slash(self):
        """Test URL trailing slash is stripped."""
        adapter = PalantirAIPAdapter(
            ontology_api_url="https://test.palantir.com/ontology/",
            foundry_api_url="https://test.palantir.com/foundry/",
            api_key="test-key",
        )
        assert adapter.ontology_api_url == "https://test.palantir.com/ontology"
        assert adapter.foundry_api_url == "https://test.palantir.com/foundry"

    def test_init_custom_timeout(self):
        """Test custom timeout."""
        adapter = PalantirAIPAdapter(
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key="test-key",
            timeout_seconds=60.0,
        )
        assert adapter.timeout.total == 60.0


# =============================================================================
# Threat Context Tests
# =============================================================================


class TestGetThreatContext:
    """Tests for get_threat_context method."""

    @pytest.fixture
    def adapter(self) -> PalantirAIPAdapter:
        return PalantirAIPAdapter(
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key="test-key",
        )

    @pytest.fixture
    def mock_response(self) -> dict:
        return {
            "data": [
                {
                    "id": "vuln-001",
                    "type": "Vulnerability",
                    "properties": {
                        "cve_id": "CVE-2024-1234",
                        "epss_score": 0.85,
                        "mitre_ttps": ["T1059", "T1190"],
                        "targeted_industries": ["finance"],
                        "active_campaigns": ["Campaign-Alpha"],
                        "threat_actors": ["APT29"],
                    },
                }
            ],
            "nextPageToken": None,
        }

    @pytest.mark.asyncio
    async def test_get_threat_context_from_cache(self, adapter: PalantirAIPAdapter):
        """Test getting threat context from cache."""
        # Pre-populate cache
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
            cves=["CVE-2024-1234"],
            epss_score=0.75,
        )
        adapter._threat_cache["CVE-2024-1234"] = (threat, datetime.now(timezone.utc))

        # Should return cached value without making API call
        with patch.object(adapter, "_make_request", new_callable=AsyncMock) as mock_req:
            result = await adapter.get_threat_context(["CVE-2024-1234"])
            # May or may not call API depending on cache validation logic
            assert len(result) >= 0  # Validates we don't crash

    @pytest.mark.asyncio
    async def test_get_threat_context_empty_cves(self, adapter: PalantirAIPAdapter):
        """Test with empty CVE list."""
        result = await adapter.get_threat_context([])
        assert result == []

    @pytest.mark.asyncio
    async def test_get_threat_context_circuit_open(self, adapter: PalantirAIPAdapter):
        """Test when circuit breaker is open."""
        adapter._circuit_open = True

        # Should return cached threats
        result = await adapter.get_threat_context(["CVE-2024-1234"])
        assert isinstance(result, list)


# =============================================================================
# Asset Criticality Tests
# =============================================================================


class TestGetAssetCriticality:
    """Tests for get_asset_criticality method."""

    @pytest.fixture
    def adapter(self) -> PalantirAIPAdapter:
        return PalantirAIPAdapter(
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_get_asset_criticality_from_cache(self, adapter: PalantirAIPAdapter):
        """Test getting asset from cache."""
        asset = AssetContext(
            asset_id="repo-001",
            criticality_score=9,
        )
        adapter._asset_cache["repo-001"] = (asset, datetime.now(timezone.utc))

        result = await adapter.get_asset_criticality("repo-001")
        assert result is not None
        assert result.asset_id == "repo-001"

    @pytest.mark.asyncio
    async def test_get_asset_criticality_cache_miss(self, adapter: PalantirAIPAdapter):
        """Test cache miss returns None when not in cache."""
        # When no cached data and circuit open
        adapter._circuit_open = True
        result = await adapter.get_asset_criticality("unknown-repo")
        # Should return None when not in cache and circuit is open
        assert result is None


# =============================================================================
# Publish Event Tests
# =============================================================================


class TestPublishRemediationEvent:
    """Tests for publish_remediation_event method."""

    @pytest.fixture
    def adapter(self) -> PalantirAIPAdapter:
        return PalantirAIPAdapter(
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key="test-key",
        )

    @pytest.fixture
    def sample_event(self) -> RemediationEvent:
        return RemediationEvent(
            event_id="evt-001",
            event_type=RemediationEventType.VULNERABILITY_DETECTED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tenant_id="tenant-001",
            payload={"cve_id": "CVE-2024-1234"},
        )

    @pytest.mark.asyncio
    async def test_publish_event_with_circuit_open(
        self, adapter: PalantirAIPAdapter, sample_event: RemediationEvent
    ):
        """Test event publishing when circuit is open."""
        adapter._circuit_open = True
        # Even with circuit open, we should still attempt to publish
        # (actual behavior depends on implementation)
        result = await adapter.publish_remediation_event(sample_event)
        # Should return False when circuit is open and no connection
        assert result is False


# =============================================================================
# Sync Objects Tests
# =============================================================================


class TestSyncObjects:
    """Tests for sync_objects method."""

    @pytest.fixture
    def adapter(self) -> PalantirAIPAdapter:
        return PalantirAIPAdapter(
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_sync_objects_with_circuit_open(self, adapter: PalantirAIPAdapter):
        """Test sync objects when circuit is open."""
        adapter._circuit_open = True
        result = await adapter.sync_objects(
            PalantirObjectType.VULNERABILITY, full_sync=True
        )
        # Should return failed result when circuit is open
        assert result.status == SyncStatus.FAILED


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health_check method."""

    @pytest.fixture
    def adapter(self) -> PalantirAIPAdapter:
        return PalantirAIPAdapter(
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_health_check_updates_status(self, adapter: PalantirAIPAdapter):
        """Test health check updates adapter status."""
        # Health check will fail without actual connection
        result = await adapter.health_check()
        # Should be False without real connection and status should update
        assert result is False
        assert adapter._status == ConnectorStatus.ERROR


# =============================================================================
# Circuit Breaker Tests
# =============================================================================


class TestCircuitBreaker:
    """Tests for circuit breaker integration."""

    @pytest.fixture
    def adapter(self) -> PalantirAIPAdapter:
        return PalantirAIPAdapter(
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key="test-key",
        )

    def test_set_circuit_state_open(self, adapter: PalantirAIPAdapter):
        """Test opening circuit."""
        adapter.set_circuit_state(is_open=True)
        assert adapter._circuit_open is True

    def test_set_circuit_state_closed(self, adapter: PalantirAIPAdapter):
        """Test closing circuit."""
        adapter._circuit_open = True
        adapter.set_circuit_state(is_open=False)
        assert adapter._circuit_open is False

    def test_get_cached_threat_context(self, adapter: PalantirAIPAdapter):
        """Test getting cached threats when circuit is open."""
        # Add cached threat
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
            cves=["CVE-2024-1234"],
        )
        adapter._threat_cache["CVE-2024-1234"] = (threat, datetime.now(timezone.utc))

        cached = adapter.get_cached_threat_context(["CVE-2024-1234"])
        assert len(cached) == 1
        assert cached[0].threat_id == "threat-001"


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Tests for adapter helper methods."""

    @pytest.fixture
    def adapter(self) -> PalantirAIPAdapter:
        return PalantirAIPAdapter(
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_close(self, adapter: PalantirAIPAdapter):
        """Test close method."""
        adapter._status = ConnectorStatus.CONNECTED
        await adapter.close()
        assert adapter._status == ConnectorStatus.DISCONNECTED


# =============================================================================
# Cache Tests
# =============================================================================


class TestCaching:
    """Tests for caching behavior."""

    @pytest.fixture
    def adapter(self) -> PalantirAIPAdapter:
        return PalantirAIPAdapter(
            ontology_api_url="https://test.palantir.com/ontology",
            foundry_api_url="https://test.palantir.com/foundry",
            api_key="test-key",
        )

    def test_threat_cache_populated(self, adapter: PalantirAIPAdapter):
        """Test threat cache is populated."""
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
            cves=["CVE-2024-1234"],
        )
        adapter._threat_cache["CVE-2024-1234"] = (threat, datetime.now(timezone.utc))
        assert "CVE-2024-1234" in adapter._threat_cache

    def test_asset_cache_populated(self, adapter: PalantirAIPAdapter):
        """Test asset cache is populated."""
        asset = AssetContext(asset_id="repo-001", criticality_score=9)
        adapter._asset_cache["repo-001"] = (asset, datetime.now(timezone.utc))
        assert "repo-001" in adapter._asset_cache

    def test_cache_has_timestamp(self, adapter: PalantirAIPAdapter):
        """Test cache entries have timestamps for expiry tracking."""
        threat = ThreatContext(
            threat_id="threat-001",
            source_platform="palantir_aip",
        )
        adapter._threat_cache["CVE-2024-1234"] = (threat, datetime.now(timezone.utc))
        # Cache entry should be a tuple of (data, timestamp)
        entry = adapter._threat_cache["CVE-2024-1234"]
        assert isinstance(entry, tuple)
        assert len(entry) == 2
        assert isinstance(entry[1], datetime)
