"""
Tests for Enterprise Data Platform Adapter ABC

Tests the abstract base class contract and metrics tracking.
"""

from datetime import datetime, timezone

import pytest

from src.services.palantir.base_adapter import (
    ConnectorResult,
    ConnectorStatus,
    EnterpriseDataPlatformAdapter,
    measure_latency,
)
from src.services.palantir.types import (
    AssetContext,
    PalantirObjectType,
    RemediationEvent,
    RemediationEventType,
    SyncResult,
    SyncStatus,
    ThreatContext,
)

# =============================================================================
# Concrete Test Adapter
# =============================================================================


class TestAdapter(EnterpriseDataPlatformAdapter):
    """Concrete adapter for testing ABC."""

    def __init__(self):
        super().__init__(name="test_adapter", timeout_seconds=10.0)
        self._healthy = True
        self._should_fail = False

    async def get_threat_context(self, cve_ids: list[str]) -> list[ThreatContext]:
        if self._should_fail:
            raise ConnectionError("Test failure")
        return [
            ThreatContext(
                threat_id=f"threat-{cve}",
                source_platform="test",
                cves=[cve],
            )
            for cve in cve_ids
        ]

    async def get_asset_criticality(self, repo_id: str) -> AssetContext | None:
        if self._should_fail:
            raise ConnectionError("Test failure")
        return AssetContext(asset_id=repo_id, criticality_score=5)

    async def publish_remediation_event(self, event: RemediationEvent) -> bool:
        if self._should_fail:
            return False
        return True

    async def sync_objects(
        self, object_type: PalantirObjectType, full_sync: bool = False
    ) -> SyncResult:
        if self._should_fail:
            return SyncResult(
                object_type=object_type,
                status=SyncStatus.FAILED,
                error_message="Test failure",
            )
        return SyncResult(
            object_type=object_type,
            status=SyncStatus.SYNCED,
            objects_synced=10,
        )

    async def health_check(self) -> bool:
        return self._healthy


# =============================================================================
# ConnectorResult Tests
# =============================================================================


class TestConnectorResult:
    """Tests for ConnectorResult dataclass."""

    def test_ok_result(self):
        """Test creating successful result."""
        result = ConnectorResult.ok(data={"key": "value"}, latency_ms=50.0)
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.latency_ms == 50.0
        assert result.error is None

    def test_ok_result_cached(self):
        """Test creating cached result."""
        result = ConnectorResult.ok(data={}, cached=True)
        assert result.cached is True

    def test_fail_result(self):
        """Test creating failed result."""
        result = ConnectorResult.fail(error="Connection timeout", status_code=504)
        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.status_code == 504

    def test_fail_result_with_latency(self):
        """Test failed result with latency."""
        result = ConnectorResult.fail(error="Error", latency_ms=100.0)
        assert result.latency_ms == 100.0


# =============================================================================
# ConnectorStatus Tests
# =============================================================================


class TestConnectorStatus:
    """Tests for ConnectorStatus enum."""

    def test_all_statuses(self):
        """Test all status values."""
        assert ConnectorStatus.CONNECTED.value == "connected"
        assert ConnectorStatus.DISCONNECTED.value == "disconnected"
        assert ConnectorStatus.ERROR.value == "error"
        assert ConnectorStatus.RATE_LIMITED.value == "rate_limited"
        assert ConnectorStatus.AUTH_FAILED.value == "auth_failed"
        assert ConnectorStatus.CIRCUIT_OPEN.value == "circuit_open"


# =============================================================================
# EnterpriseDataPlatformAdapter Tests
# =============================================================================


class TestEnterpriseDataPlatformAdapter:
    """Tests for the abstract base class."""

    @pytest.fixture
    def adapter(self) -> TestAdapter:
        """Create test adapter."""
        return TestAdapter()

    def test_init(self, adapter: TestAdapter):
        """Test adapter initialization."""
        assert adapter.name == "test_adapter"
        assert adapter._status == ConnectorStatus.DISCONNECTED
        assert adapter._request_count == 0
        assert adapter._error_count == 0

    def test_status_property(self, adapter: TestAdapter):
        """Test status property."""
        assert adapter.status == ConnectorStatus.DISCONNECTED
        adapter._status = ConnectorStatus.CONNECTED
        assert adapter.status == ConnectorStatus.CONNECTED

    def test_is_healthy_connected(self, adapter: TestAdapter):
        """Test is_healthy when connected."""
        adapter._status = ConnectorStatus.CONNECTED
        assert adapter.is_healthy is True

    def test_is_healthy_disconnected(self, adapter: TestAdapter):
        """Test is_healthy when disconnected."""
        adapter._status = ConnectorStatus.DISCONNECTED
        assert adapter.is_healthy is True

    def test_is_healthy_error(self, adapter: TestAdapter):
        """Test is_healthy when in error state."""
        adapter._status = ConnectorStatus.ERROR
        assert adapter.is_healthy is False

    def test_metrics_initial(self, adapter: TestAdapter):
        """Test metrics at initialization."""
        metrics = adapter.metrics
        assert metrics["name"] == "test_adapter"
        assert metrics["status"] == "disconnected"
        assert metrics["request_count"] == 0
        assert metrics["error_count"] == 0
        assert metrics["error_rate"] == 0.0
        assert metrics["avg_latency_ms"] == 0.0

    def test_metrics_after_requests(self, adapter: TestAdapter):
        """Test metrics after recording requests."""
        adapter._record_request(latency_ms=100.0, success=True)
        adapter._record_request(latency_ms=200.0, success=True)
        adapter._record_request(latency_ms=150.0, success=False)

        metrics = adapter.metrics
        assert metrics["request_count"] == 3
        assert metrics["error_count"] == 1
        assert metrics["error_rate"] == pytest.approx(1 / 3)
        assert metrics["avg_latency_ms"] == pytest.approx(150.0)

    def test_record_request_success(self, adapter: TestAdapter):
        """Test recording successful request."""
        adapter._record_request(latency_ms=50.0, success=True)
        assert adapter._request_count == 1
        assert adapter._error_count == 0
        assert adapter._total_latency_ms == 50.0

    def test_record_request_failure(self, adapter: TestAdapter):
        """Test recording failed request."""
        adapter._record_request(latency_ms=100.0, success=False)
        assert adapter._request_count == 1
        assert adapter._error_count == 1

    def test_record_request_cached(self, adapter: TestAdapter):
        """Test recording cached request."""
        adapter._record_request(latency_ms=5.0, success=True, cached=True)
        assert adapter._cache_hits == 1
        assert adapter._cache_misses == 0

    def test_record_request_not_cached(self, adapter: TestAdapter):
        """Test recording non-cached request."""
        adapter._record_request(latency_ms=100.0, success=True, cached=False)
        assert adapter._cache_hits == 0
        assert adapter._cache_misses == 1

    def test_record_error(self, adapter: TestAdapter):
        """Test recording error."""
        adapter._record_error("Connection failed")
        assert adapter._last_error == "Connection failed"
        assert adapter._last_error_time is not None
        assert adapter._status == ConnectorStatus.ERROR

    def test_set_status(self, adapter: TestAdapter):
        """Test setting status."""
        adapter._set_status(ConnectorStatus.CONNECTED)
        assert adapter._status == ConnectorStatus.CONNECTED

    def test_set_status_no_change(self, adapter: TestAdapter):
        """Test setting status with no change."""
        adapter._status = ConnectorStatus.CONNECTED
        adapter._set_status(ConnectorStatus.CONNECTED)
        assert adapter._status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_get_threat_context(self, adapter: TestAdapter):
        """Test get_threat_context method."""
        threats = await adapter.get_threat_context(["CVE-2024-1234"])
        assert len(threats) == 1
        assert threats[0].threat_id == "threat-CVE-2024-1234"

    @pytest.mark.asyncio
    async def test_get_asset_criticality(self, adapter: TestAdapter):
        """Test get_asset_criticality method."""
        asset = await adapter.get_asset_criticality("repo-001")
        assert asset is not None
        assert asset.asset_id == "repo-001"

    @pytest.mark.asyncio
    async def test_publish_remediation_event(self, adapter: TestAdapter):
        """Test publish_remediation_event method."""
        event = RemediationEvent(
            event_id="evt-001",
            event_type=RemediationEventType.VULNERABILITY_DETECTED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tenant_id="tenant-001",
            payload={},
        )
        result = await adapter.publish_remediation_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_sync_objects(self, adapter: TestAdapter):
        """Test sync_objects method."""
        result = await adapter.sync_objects(PalantirObjectType.VULNERABILITY)
        assert result.status == SyncStatus.SYNCED
        assert result.objects_synced == 10

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, adapter: TestAdapter):
        """Test health check when healthy."""
        result = await adapter.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, adapter: TestAdapter):
        """Test health check when unhealthy."""
        adapter._healthy = False
        result = await adapter.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_close(self, adapter: TestAdapter):
        """Test close method."""
        adapter._status = ConnectorStatus.CONNECTED
        await adapter.close()
        assert adapter._status == ConnectorStatus.DISCONNECTED


# =============================================================================
# Optional Methods Tests
# =============================================================================


class TestOptionalMethods:
    """Tests for optional adapter methods."""

    @pytest.fixture
    def adapter(self) -> TestAdapter:
        return TestAdapter()

    @pytest.mark.asyncio
    async def test_get_active_threats_default(self, adapter: TestAdapter):
        """Test default get_active_threats implementation."""
        threats = await adapter.get_active_threats()
        assert threats == []

    @pytest.mark.asyncio
    async def test_get_threat_actors_default(self, adapter: TestAdapter):
        """Test default get_threat_actors implementation."""
        actors = await adapter.get_threat_actors()
        assert actors == []

    @pytest.mark.asyncio
    async def test_search_vulnerabilities_default(self, adapter: TestAdapter):
        """Test default search_vulnerabilities implementation."""
        vulns = await adapter.search_vulnerabilities("test")
        assert vulns == []


# =============================================================================
# Measure Latency Decorator Tests
# =============================================================================


class TestMeasureLatencyDecorator:
    """Tests for measure_latency decorator."""

    @pytest.fixture
    def adapter(self) -> TestAdapter:
        return TestAdapter()

    @pytest.mark.asyncio
    async def test_measure_latency_success(self, adapter: TestAdapter):
        """Test latency measurement on success."""

        @measure_latency
        async def test_method(self):
            return {"result": "success"}

        # Bind the method to adapter
        result = await test_method(adapter)
        assert result == {"result": "success"}
        assert adapter._request_count == 1
        assert adapter._total_latency_ms > 0

    @pytest.mark.asyncio
    async def test_measure_latency_failure(self, adapter: TestAdapter):
        """Test latency measurement on failure."""

        @measure_latency
        async def test_method(self):
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await test_method(adapter)

        assert adapter._request_count == 1
        assert adapter._error_count == 1
        assert adapter._last_error == "Test error"
