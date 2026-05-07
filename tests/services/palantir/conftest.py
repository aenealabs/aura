"""
Palantir AIP Integration Test Fixtures

Provides fixtures for testing Palantir integration components.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.palantir.base_adapter import EnterpriseDataPlatformAdapter
from src.services.palantir.circuit_breaker import (
    PalantirCircuitBreaker,
    PalantirCircuitBreakerRegistry,
)
from src.services.palantir.event_publisher import PalantirEventPublisher, PublishMode
from src.services.palantir.ontology_bridge import OntologyBridgeService
from src.services.palantir.palantir_adapter import PalantirAIPAdapter
from src.services.palantir.types import (
    AssetContext,
    DataClassification,
    PalantirObjectType,
    RemediationEvent,
    RemediationEventType,
    SyncResult,
    SyncStatus,
    ThreatContext,
)

# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_threat_context() -> ThreatContext:
    """Sample ThreatContext for testing."""
    return ThreatContext(
        threat_id="threat-001",
        source_platform="palantir_aip",
        cves=["CVE-2024-1234", "CVE-2024-5678"],
        epss_score=0.85,
        mitre_ttps=["T1059", "T1190"],
        targeted_industries=["finance", "healthcare"],
        active_campaigns=["Campaign-Alpha"],
        threat_actors=["APT29"],
        raw_metadata={"source": "test"},
    )


@pytest.fixture
def sample_asset_context() -> AssetContext:
    """Sample AssetContext for testing."""
    return AssetContext(
        asset_id="asset-001",
        criticality_score=9,
        data_classification=DataClassification.CONFIDENTIAL,
        business_owner="security-team",
        pii_handling=True,
        phi_handling=False,
    )


@pytest.fixture
def sample_remediation_event() -> RemediationEvent:
    """Sample RemediationEvent for testing."""
    return RemediationEvent(
        event_id="evt-001",
        event_type=RemediationEventType.VULNERABILITY_DETECTED,
        timestamp=datetime.now(timezone.utc).isoformat(),
        tenant_id="tenant-001",
        payload={
            "cve_id": "CVE-2024-1234",
            "severity": "critical",
            "repo_id": "repo-001",
        },
    )


@pytest.fixture
def sample_sync_result() -> SyncResult:
    """Sample SyncResult for testing."""
    return SyncResult(
        object_type=PalantirObjectType.VULNERABILITY,
        status=SyncStatus.SYNCED,
        objects_synced=10,
        objects_failed=0,
        conflicts_resolved=2,
    )


# =============================================================================
# Mock Response Fixtures
# =============================================================================


@pytest.fixture
def mock_palantir_threat_response() -> dict[str, Any]:
    """Mock Palantir Ontology API response for threats."""
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


@pytest.fixture
def mock_palantir_asset_response() -> dict[str, Any]:
    """Mock Palantir Ontology API response for assets."""
    return {
        "data": [
            {
                "id": "asset-001",
                "type": "Asset",
                "properties": {
                    "asset_id": "repo-001",
                    "criticality_score": 9,
                    "data_classification": "CONFIDENTIAL",
                    "pii_handling": True,
                    "business_owner": "security-team",
                },
            }
        ],
    }


@pytest.fixture
def mock_palantir_health_response() -> dict[str, Any]:
    """Mock Palantir health check response."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Mock Adapter Fixtures
# =============================================================================


class MockAdapter(EnterpriseDataPlatformAdapter):
    """Mock adapter for testing."""

    def __init__(self) -> None:
        super().__init__(name="mock_adapter")
        self._threats: list[ThreatContext] = []
        self._assets: dict[str, AssetContext] = {}
        self._published_events: list[RemediationEvent] = []
        self._sync_results: dict[PalantirObjectType, SyncResult] = {}
        self._healthy = True

    async def get_threat_context(self, cve_ids: list[str]) -> list[ThreatContext]:
        return [t for t in self._threats if any(cve in t.cves for cve in cve_ids)]

    async def get_asset_criticality(self, repo_id: str) -> AssetContext | None:
        return self._assets.get(repo_id)

    async def publish_remediation_event(self, event: RemediationEvent) -> bool:
        self._published_events.append(event)
        return True

    async def sync_objects(
        self, object_type: PalantirObjectType, full_sync: bool = False
    ) -> SyncResult:
        if object_type in self._sync_results:
            return self._sync_results[object_type]
        return SyncResult(
            object_type=object_type,
            status=SyncStatus.SYNCED,
            objects_synced=5,
            objects_failed=0,
            conflicts_resolved=0,
        )

    async def health_check(self) -> bool:
        return self._healthy


@pytest.fixture
def mock_adapter() -> MockAdapter:
    """Create mock adapter for testing."""
    return MockAdapter()


@pytest.fixture
def mock_adapter_with_data(
    mock_adapter: MockAdapter,
    sample_threat_context: ThreatContext,
    sample_asset_context: AssetContext,
) -> MockAdapter:
    """Mock adapter pre-populated with sample data."""
    mock_adapter._threats.append(sample_threat_context)
    mock_adapter._assets["repo-001"] = sample_asset_context
    return mock_adapter


# =============================================================================
# Service Fixtures
# =============================================================================


@pytest.fixture
def palantir_adapter() -> PalantirAIPAdapter:
    """Create Palantir adapter for testing."""
    return PalantirAIPAdapter(
        ontology_api_url="https://test.palantir.com/ontology",
        foundry_api_url="https://test.palantir.com/foundry",
        api_key="test-api-key",
    )


@pytest.fixture
def ontology_bridge(mock_adapter: MockAdapter) -> OntologyBridgeService:
    """Create Ontology Bridge with mock adapter."""
    return OntologyBridgeService(adapter=mock_adapter)


@pytest.fixture
def event_publisher(mock_adapter: MockAdapter) -> PalantirEventPublisher:
    """Create Event Publisher with mock adapter."""
    return PalantirEventPublisher(
        adapter=mock_adapter,
        mode=PublishMode.DIRECT,
    )


@pytest.fixture
def circuit_breaker() -> PalantirCircuitBreaker:
    """Create Palantir circuit breaker for testing."""
    return PalantirCircuitBreaker(service="test")


@pytest.fixture
def circuit_registry() -> PalantirCircuitBreakerRegistry:
    """Create circuit breaker registry for testing."""
    return PalantirCircuitBreakerRegistry()


# =============================================================================
# HTTP Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_aiohttp_session():
    """Create mock aiohttp session."""
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.fixture
def mock_aiohttp_response(mock_palantir_health_response: dict):
    """Create mock aiohttp response."""
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(return_value=mock_palantir_health_response)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


# =============================================================================
# Async Test Utilities
# =============================================================================


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
