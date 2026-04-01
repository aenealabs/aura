"""
Tests for Ontology Bridge Service

Tests synchronization, conflict resolution, and caching.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.palantir.ontology_bridge import (
    ObjectSyncState,
    SyncStateStore,
)
from src.services.palantir.types import (
    PalantirObjectType,
    SyncStatus,
)

# =============================================================================
# SyncStateStore Tests
# =============================================================================


class TestSyncStateStore:
    """Tests for SyncStateStore."""

    @pytest.fixture
    def store(self) -> SyncStateStore:
        return SyncStateStore()

    def test_get_state_creates_new(self, store: SyncStateStore):
        """Test get_state creates new state if not exists."""
        state = store.get_state(PalantirObjectType.VULNERABILITY)
        assert state.object_type == PalantirObjectType.VULNERABILITY
        assert state.last_sync_status == SyncStatus.PENDING

    def test_get_state_returns_existing(self, store: SyncStateStore):
        """Test get_state returns existing state."""
        state1 = store.get_state(PalantirObjectType.VULNERABILITY)
        state1.objects_synced = 10
        state2 = store.get_state(PalantirObjectType.VULNERABILITY)
        assert state2.objects_synced == 10

    def test_update_state(self, store: SyncStateStore):
        """Test update_state updates values."""
        store.update_state(
            object_type=PalantirObjectType.THREAT_ACTOR,
            status=SyncStatus.SYNCED,
            synced=25,
            failed=2,
            conflicts=3,
        )
        state = store.get_state(PalantirObjectType.THREAT_ACTOR)
        assert state.last_sync_status == SyncStatus.SYNCED
        assert state.objects_synced == 25
        assert state.objects_failed == 2
        assert state.conflicts_resolved == 3
        assert state.last_sync_time is not None

    def test_update_state_with_error(self, store: SyncStateStore):
        """Test update_state with error message."""
        store.update_state(
            object_type=PalantirObjectType.ASSET,
            status=SyncStatus.FAILED,
            error="Connection timeout",
        )
        state = store.get_state(PalantirObjectType.ASSET)
        assert state.last_sync_status == SyncStatus.FAILED
        assert state.last_error == "Connection timeout"

    def test_get_all_states(self, store: SyncStateStore):
        """Test get_all_states returns all states."""
        store.update_state(
            PalantirObjectType.VULNERABILITY, SyncStatus.SYNCED, synced=10
        )
        store.update_state(PalantirObjectType.THREAT_ACTOR, SyncStatus.SYNCED, synced=5)

        all_states = store.get_all_states()
        assert PalantirObjectType.VULNERABILITY.value in all_states
        assert PalantirObjectType.THREAT_ACTOR.value in all_states


# =============================================================================
# ObjectSyncState Tests
# =============================================================================


class TestObjectSyncState:
    """Tests for ObjectSyncState."""

    def test_to_dict(self):
        """Test to_dict conversion."""
        state = ObjectSyncState(
            object_type=PalantirObjectType.VULNERABILITY,
            last_sync_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            last_sync_status=SyncStatus.SYNCED,
            objects_synced=10,
            conflicts_resolved=2,
        )
        d = state.to_dict()
        assert d["object_type"] == "Vulnerability"
        assert d["last_sync_status"] == "synced"
        assert d["objects_synced"] == 10


# =============================================================================
# OntologyBridgeService Tests
# =============================================================================


class TestOntologyBridgeService:
    """Tests for OntologyBridgeService."""

    @pytest.mark.asyncio
    async def test_full_sync_success(self, ontology_bridge):
        """Test successful full sync."""
        result = await ontology_bridge.full_sync(PalantirObjectType.VULNERABILITY)
        assert result.status == SyncStatus.SYNCED
        assert result.objects_synced == 5  # default from mock adapter

        # Verify state updated
        state = ontology_bridge.get_object_sync_state(PalantirObjectType.VULNERABILITY)
        assert state.last_sync_status == SyncStatus.SYNCED

    @pytest.mark.asyncio
    async def test_full_sync_failure(self, mock_adapter, ontology_bridge):
        """Test failed full sync."""
        mock_adapter._healthy = False
        # Use a fresh bridge that will return failure
        from unittest.mock import AsyncMock

        from src.services.palantir.ontology_bridge import OntologyBridgeService

        failing_adapter = mock_adapter
        failing_adapter.sync_objects = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        failing_bridge = OntologyBridgeService(adapter=failing_adapter)

        result = await failing_bridge.full_sync(PalantirObjectType.THREAT_ACTOR)
        assert result.status == SyncStatus.FAILED

    @pytest.mark.asyncio
    async def test_incremental_sync(self, ontology_bridge):
        """Test incremental sync."""
        result = await ontology_bridge.incremental_sync(
            PalantirObjectType.VULNERABILITY
        )
        assert result.status == SyncStatus.SYNCED

    @pytest.mark.asyncio
    async def test_sync_all(self, ontology_bridge):
        """Test syncing all object types."""
        results = await ontology_bridge.sync_all(full_sync=False)
        assert len(results) == len(PalantirObjectType)
        for obj_type in PalantirObjectType:
            assert obj_type.value in results

    def test_get_sync_status(self, ontology_bridge):
        """Test get_sync_status."""
        status = ontology_bridge.get_sync_status()
        assert isinstance(status, dict)

    def test_is_sync_stale_never_synced(self, ontology_bridge):
        """Test is_sync_stale when never synced."""
        assert ontology_bridge.is_sync_stale(PalantirObjectType.VULNERABILITY) is True

    def test_is_sync_stale_recent(self, ontology_bridge):
        """Test is_sync_stale with recent sync."""
        ontology_bridge._last_sync[PalantirObjectType.VULNERABILITY] = datetime.now(
            timezone.utc
        )
        assert (
            ontology_bridge.is_sync_stale(
                PalantirObjectType.VULNERABILITY, max_age_seconds=60
            )
            is False
        )

    def test_is_sync_stale_old(self, ontology_bridge):
        """Test is_sync_stale with old sync."""
        ontology_bridge._last_sync[PalantirObjectType.VULNERABILITY] = datetime.now(
            timezone.utc
        ) - timedelta(hours=1)
        assert (
            ontology_bridge.is_sync_stale(
                PalantirObjectType.VULNERABILITY, max_age_seconds=60
            )
            is True
        )


# =============================================================================
# Conflict Resolution Tests
# =============================================================================


class TestConflictResolution:
    """Tests for conflict resolution logic."""

    @pytest.mark.asyncio
    async def test_resolve_conflict_palantir_authoritative(self, ontology_bridge):
        """Test Palantir authoritative resolution."""
        local = {"id": "threat-001", "name": "Local Name"}
        remote = {"id": "threat-001", "name": "Palantir Name"}

        resolved = await ontology_bridge.resolve_conflict(
            local, remote, PalantirObjectType.THREAT_ACTOR
        )
        assert resolved["name"] == "Palantir Name"

    @pytest.mark.asyncio
    async def test_resolve_conflict_aura_authoritative(self, ontology_bridge):
        """Test Aura authoritative resolution."""
        local = {"id": "repo-001", "name": "Aura Name"}
        remote = {"id": "repo-001", "name": "Palantir Name"}

        resolved = await ontology_bridge.resolve_conflict(
            local, remote, PalantirObjectType.REPOSITORY
        )
        assert resolved["name"] == "Aura Name"

    @pytest.mark.asyncio
    async def test_resolve_conflict_merge_vulnerability(self, ontology_bridge):
        """Test merge resolution for vulnerability."""
        local = {
            "id": "vuln-001",
            "code_location": "src/main.py:42",
            "fix_recommendation": "Update package",
        }
        remote = {
            "id": "vuln-001",
            "cve_id": "CVE-2024-1234",
            "epss_score": 0.85,
        }

        resolved = await ontology_bridge.resolve_conflict(
            local, remote, PalantirObjectType.VULNERABILITY
        )
        # Should have both Palantir and Aura fields
        assert resolved["cve_id"] == "CVE-2024-1234"
        assert resolved["code_location"] == "src/main.py:42"
        assert "merged_at" in resolved

    @pytest.mark.asyncio
    async def test_resolve_conflict_merge_compliance(self, ontology_bridge):
        """Test merge resolution for compliance."""
        local = {
            "id": "compliance-001",
            "aura_scan_results": {"passed": 10, "failed": 2},
        }
        remote = {
            "id": "compliance-001",
            "framework": "SOC2",
            "requirements": ["AC-1", "AC-2"],
        }

        resolved = await ontology_bridge.resolve_conflict(
            local, remote, PalantirObjectType.COMPLIANCE
        )
        assert resolved["framework"] == "SOC2"
        assert "aura_scan_results" in resolved


# =============================================================================
# Local Store Tests
# =============================================================================


class TestLocalStore:
    """Tests for local store operations."""

    def test_get_local_object_exists(self, ontology_bridge):
        """Test getting existing local object."""
        ontology_bridge._local_store["vulnerability"] = {
            "CVE-2024-1234": {"id": "CVE-2024-1234", "severity": "critical"}
        }
        obj = ontology_bridge.get_local_object(
            PalantirObjectType.VULNERABILITY, "CVE-2024-1234"
        )
        assert obj is not None
        assert obj["severity"] == "critical"

    def test_get_local_object_not_exists(self, ontology_bridge):
        """Test getting non-existent local object."""
        obj = ontology_bridge.get_local_object(
            PalantirObjectType.VULNERABILITY, "CVE-UNKNOWN"
        )
        assert obj is None

    def test_get_local_objects(self, ontology_bridge):
        """Test getting all local objects of type."""
        ontology_bridge._local_store["asset"] = {
            "asset-001": {"id": "asset-001"},
            "asset-002": {"id": "asset-002"},
        }
        objects = ontology_bridge.get_local_objects(PalantirObjectType.ASSET)
        assert len(objects) == 2


# =============================================================================
# Threat and Asset Helper Tests
# =============================================================================


class TestThreatAssetHelpers:
    """Tests for threat and asset helper methods."""

    @pytest.mark.asyncio
    async def test_get_threat_context_for_cves(
        self, ontology_bridge, sample_threat_context
    ):
        """Test getting threat context for CVEs."""
        ontology_bridge.adapter._threats.append(sample_threat_context)

        threats = await ontology_bridge.get_threat_context_for_cves(["CVE-2024-1234"])
        assert len(threats) == 1

    @pytest.mark.asyncio
    async def test_get_threat_context_fallback_to_cache(self, ontology_bridge):
        """Test fallback to cache when adapter fails."""
        ontology_bridge.adapter._status = "error"
        ontology_bridge._local_store["vulnerability"] = {
            "CVE-2024-1234": {
                "threat_id": "cached-threat",
                "epss_score": 0.5,
                "mitre_ttps": ["T1059"],
            }
        }

        # This would use cached data
        threats = ontology_bridge._get_cached_threats(["CVE-2024-1234"])
        assert len(threats) == 1

    @pytest.mark.asyncio
    async def test_get_asset_criticality(self, mock_adapter_with_data, ontology_bridge):
        """Test getting asset criticality."""
        # Use the mock adapter with pre-populated data
        from src.services.palantir.ontology_bridge import OntologyBridgeService

        bridge = OntologyBridgeService(adapter=mock_adapter_with_data)

        asset = await bridge.get_asset_criticality("repo-001")
        assert asset is not None
        assert asset.criticality_score == 9

    @pytest.mark.asyncio
    async def test_get_asset_criticality_fallback_to_cache(self, ontology_bridge):
        """Test fallback to cache when adapter fails."""
        ontology_bridge._local_store["asset"] = {
            "repo-001": {
                "asset_id": "repo-001",
                "criticality_score": 7,
                "pii_handling": True,
            }
        }

        asset = ontology_bridge._get_cached_asset("repo-001")
        assert asset is not None
        assert asset.criticality_score == 7
