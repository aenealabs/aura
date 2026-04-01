"""
Palantir Ontology Bridge Service

Implements ADR-074: Palantir AIP Integration

Synchronizes Palantir Ontology objects with Aura's local cache.
Handles bidirectional sync with conflict resolution per ADR-074 matrix.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.services.palantir.base_adapter import (
    ConnectorStatus,
    EnterpriseDataPlatformAdapter,
)
from src.services.palantir.types import (
    CONFLICT_RESOLUTION_RULES,
    AssetContext,
    ConflictResolutionStrategy,
    PalantirObjectType,
    SyncResult,
    SyncStatus,
    ThreatContext,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Sync State Tracking
# =============================================================================


@dataclass
class ObjectSyncState:
    """State tracking for a single object type sync."""

    object_type: PalantirObjectType
    last_sync_time: datetime | None = None
    last_sync_status: SyncStatus = SyncStatus.PENDING
    objects_synced: int = 0
    objects_failed: int = 0
    conflicts_resolved: int = 0
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "object_type": self.object_type.value,
            "last_sync_time": (
                self.last_sync_time.isoformat() if self.last_sync_time else None
            ),
            "last_sync_status": self.last_sync_status.value,
            "objects_synced": self.objects_synced,
            "objects_failed": self.objects_failed,
            "conflicts_resolved": self.conflicts_resolved,
            "last_error": self.last_error,
        }


@dataclass
class SyncStateStore:
    """In-memory sync state store."""

    states: dict[PalantirObjectType, ObjectSyncState] = field(default_factory=dict)

    def get_state(self, object_type: PalantirObjectType) -> ObjectSyncState:
        """Get or create sync state for object type."""
        if object_type not in self.states:
            self.states[object_type] = ObjectSyncState(object_type=object_type)
        return self.states[object_type]

    def update_state(
        self,
        object_type: PalantirObjectType,
        status: SyncStatus,
        synced: int = 0,
        failed: int = 0,
        conflicts: int = 0,
        error: str | None = None,
    ) -> None:
        """Update sync state after operation."""
        state = self.get_state(object_type)
        state.last_sync_time = datetime.now(timezone.utc)
        state.last_sync_status = status
        state.objects_synced = synced
        state.objects_failed = failed
        state.conflicts_resolved = conflicts
        state.last_error = error

    def get_all_states(self) -> dict[str, dict[str, Any]]:
        """Get all sync states as dictionary."""
        return {k.value: v.to_dict() for k, v in self.states.items()}


# =============================================================================
# Ontology Bridge Service
# =============================================================================


class OntologyBridgeService:
    """
    Synchronizes Palantir Ontology objects with Aura.

    Provides bidirectional sync capabilities with conflict resolution
    following the ADR-074 authoritative source matrix:

    - ThreatActor: Palantir authoritative
    - Vulnerability: Merge (Palantir CVE data + Aura code context)
    - Asset: Palantir authoritative
    - Repository: Aura authoritative
    - Compliance: Merge

    Usage:
        >>> bridge = OntologyBridgeService(adapter)
        >>> result = await bridge.full_sync(PalantirObjectType.THREAT_ACTOR)
        >>> status = bridge.get_sync_status()
    """

    def __init__(
        self,
        adapter: EnterpriseDataPlatformAdapter,
        local_store: dict[str, Any] | None = None,
        sync_interval_seconds: float = 300.0,
    ) -> None:
        """
        Initialize the Ontology Bridge.

        Args:
            adapter: Enterprise data platform adapter (e.g., PalantirAIPAdapter)
            local_store: Optional local data store (dict for now, DynamoDB later)
            sync_interval_seconds: Default interval between incremental syncs
        """
        self.adapter = adapter
        self._local_store = local_store or {}
        self._sync_interval = sync_interval_seconds
        self._state_store = SyncStateStore()
        self._sync_locks: dict[PalantirObjectType, asyncio.Lock] = {
            ot: asyncio.Lock() for ot in PalantirObjectType
        }
        self._last_sync: dict[PalantirObjectType, datetime] = {}

    # =========================================================================
    # Public API
    # =========================================================================

    async def full_sync(
        self,
        object_type: PalantirObjectType,
    ) -> SyncResult:
        """
        Perform full sync of an object type.

        Fetches all objects from Palantir and updates local store,
        applying conflict resolution rules.

        Args:
            object_type: Type of objects to sync

        Returns:
            SyncResult with statistics
        """
        async with self._sync_locks[object_type]:
            logger.info(f"Starting full sync for {object_type.value}")

            try:
                # Perform sync via adapter
                result = await self.adapter.sync_objects(
                    object_type=object_type,
                    full_sync=True,
                )

                # Update local store with synced data
                await self._update_local_store(object_type, result)

                # Update state tracking
                self._state_store.update_state(
                    object_type=object_type,
                    status=SyncStatus.SYNCED,
                    synced=result.objects_synced,
                    failed=result.objects_failed,
                    conflicts=result.conflicts_resolved,
                )
                self._last_sync[object_type] = datetime.now(timezone.utc)

                logger.info(
                    f"Full sync complete for {object_type.value}: "
                    f"{result.objects_synced} synced, "
                    f"{result.conflicts_resolved} conflicts resolved"
                )

                return result

            except Exception as e:
                logger.error(f"Full sync failed for {object_type.value}: {e}")
                self._state_store.update_state(
                    object_type=object_type,
                    status=SyncStatus.FAILED,
                    error=str(e),
                )
                return SyncResult(
                    object_type=object_type,
                    status=SyncStatus.FAILED,
                    error_message=str(e),
                )

    async def incremental_sync(
        self,
        object_type: PalantirObjectType,
    ) -> SyncResult:
        """
        Sync only changed objects since last sync.

        More efficient than full sync for frequent updates.

        Args:
            object_type: Type of objects to sync

        Returns:
            SyncResult with statistics
        """
        async with self._sync_locks[object_type]:
            logger.info(f"Starting incremental sync for {object_type.value}")

            try:
                # Perform incremental sync via adapter
                result = await self.adapter.sync_objects(
                    object_type=object_type,
                    full_sync=False,
                )

                # Update local store
                await self._update_local_store(object_type, result)

                # Update state
                self._state_store.update_state(
                    object_type=object_type,
                    status=SyncStatus.SYNCED,
                    synced=result.objects_synced,
                    failed=result.objects_failed,
                    conflicts=result.conflicts_resolved,
                )
                self._last_sync[object_type] = datetime.now(timezone.utc)

                return result

            except Exception as e:
                logger.error(f"Incremental sync failed for {object_type.value}: {e}")
                self._state_store.update_state(
                    object_type=object_type,
                    status=SyncStatus.FAILED,
                    error=str(e),
                )
                return SyncResult(
                    object_type=object_type,
                    status=SyncStatus.FAILED,
                    error_message=str(e),
                )

    async def sync_all(self, full_sync: bool = False) -> dict[str, SyncResult]:
        """
        Sync all object types.

        Args:
            full_sync: If True, perform full sync; otherwise incremental

        Returns:
            Dict mapping object type names to SyncResults
        """
        sync_fn = self.full_sync if full_sync else self.incremental_sync
        object_types = list(PalantirObjectType)
        sync_results = await asyncio.gather(*(sync_fn(ot) for ot in object_types))
        return {ot.value: result for ot, result in zip(object_types, sync_results)}

    def get_sync_status(self) -> dict[str, dict[str, Any]]:
        """
        Get sync status for all object types.

        Returns:
            Dict mapping object type names to status dictionaries
        """
        return self._state_store.get_all_states()

    def get_object_sync_state(
        self,
        object_type: PalantirObjectType,
    ) -> ObjectSyncState:
        """Get sync state for a specific object type."""
        return self._state_store.get_state(object_type)

    def is_sync_stale(
        self,
        object_type: PalantirObjectType,
        max_age_seconds: float | None = None,
    ) -> bool:
        """
        Check if sync data is stale.

        Args:
            object_type: Object type to check
            max_age_seconds: Maximum age before considered stale

        Returns:
            True if sync is stale or has never occurred
        """
        last_sync = self._last_sync.get(object_type)
        if last_sync is None:
            return True

        max_age = max_age_seconds or self._sync_interval
        elapsed = (datetime.now(timezone.utc) - last_sync).total_seconds()
        return elapsed > max_age

    # =========================================================================
    # Conflict Resolution
    # =========================================================================

    async def resolve_conflict(
        self,
        local: dict[str, Any],
        remote: dict[str, Any],
        object_type: PalantirObjectType,
    ) -> dict[str, Any]:
        """
        Apply conflict resolution per ADR-074 matrix.

        Args:
            local: Local object data
            remote: Remote (Palantir) object data
            object_type: Type of object being resolved

        Returns:
            Resolved object data
        """
        strategy = CONFLICT_RESOLUTION_RULES.get(
            object_type,
            ConflictResolutionStrategy.PALANTIR_AUTHORITATIVE,
        )

        if strategy == ConflictResolutionStrategy.PALANTIR_AUTHORITATIVE:
            # Palantir is authoritative - use remote data
            logger.debug(
                f"Conflict resolution for {object_type.value}: "
                f"using Palantir (authoritative)"
            )
            return remote

        elif strategy == ConflictResolutionStrategy.AURA_AUTHORITATIVE:
            # Aura is authoritative - keep local data
            logger.debug(
                f"Conflict resolution for {object_type.value}: "
                f"keeping Aura (authoritative)"
            )
            return local

        elif strategy == ConflictResolutionStrategy.MERGE:
            # Merge both sources
            return await self._merge_objects(local, remote, object_type)

        elif strategy == ConflictResolutionStrategy.LATEST_WINS:
            # Compare timestamps
            local_ts = local.get("updated_at", "")
            remote_ts = remote.get("updated_at", "")
            if remote_ts >= local_ts:
                return remote
            return local

        else:
            # Default to Palantir authoritative
            return remote

    async def _merge_objects(
        self,
        local: dict[str, Any],
        remote: dict[str, Any],
        object_type: PalantirObjectType,
    ) -> dict[str, Any]:
        """
        Merge local and remote objects.

        For Vulnerability: Merge Palantir CVE data with Aura code context
        For Compliance: Merge both sources

        Args:
            local: Local object data
            remote: Remote object data
            object_type: Type being merged

        Returns:
            Merged object data
        """
        merged = remote.copy()

        if object_type == PalantirObjectType.VULNERABILITY:
            # Palantir provides CVE metadata, Aura provides code context
            aura_fields = [
                "code_location",
                "affected_files",
                "fix_recommendation",
                "patch_status",
                "aura_analysis",
            ]
            for field_name in aura_fields:
                if field_name in local:
                    merged[field_name] = local[field_name]

        elif object_type == PalantirObjectType.COMPLIANCE:
            # Merge compliance data from both sources
            aura_compliance_fields = [
                "aura_scan_results",
                "automated_checks",
                "remediation_status",
            ]
            for field_name in aura_compliance_fields:
                if field_name in local:
                    merged[field_name] = local[field_name]

        merged["merged_at"] = datetime.now(timezone.utc).isoformat()
        merged["merge_sources"] = ["palantir", "aura"]

        logger.debug(f"Merged {object_type.value} object with {len(merged)} fields")
        return merged

    # =========================================================================
    # Local Store Management
    # =========================================================================

    async def _update_local_store(
        self,
        object_type: PalantirObjectType,
        result: SyncResult,
    ) -> None:
        """
        Update local store with sync results.

        Args:
            object_type: Type of objects synced
            result: Sync result containing object data
        """
        store_key = object_type.value.lower()
        if store_key not in self._local_store:
            self._local_store[store_key] = {}

        # Get synced objects from details if available
        synced_objects = result.details.get("synced_objects", {})

        for obj_id, obj_data in synced_objects.items():
            # Check for conflicts
            if obj_id in self._local_store[store_key]:
                local = self._local_store[store_key][obj_id]
                resolved = await self.resolve_conflict(local, obj_data, object_type)
                self._local_store[store_key][obj_id] = resolved
            else:
                self._local_store[store_key][obj_id] = obj_data

    def get_local_object(
        self,
        object_type: PalantirObjectType,
        object_id: str,
    ) -> dict[str, Any] | None:
        """Get object from local store."""
        store_key = object_type.value.lower()
        return self._local_store.get(store_key, {}).get(object_id)

    def get_local_objects(
        self,
        object_type: PalantirObjectType,
    ) -> dict[str, dict[str, Any]]:
        """Get all objects of a type from local store."""
        store_key = object_type.value.lower()
        return self._local_store.get(store_key, {})

    # =========================================================================
    # Threat and Asset Helpers
    # =========================================================================

    async def get_threat_context_for_cves(
        self,
        cve_ids: list[str],
    ) -> list[ThreatContext]:
        """
        Get threat context for CVEs, using local cache if available.

        Args:
            cve_ids: List of CVE identifiers

        Returns:
            List of ThreatContext objects
        """
        # Check adapter health
        if self.adapter.status == ConnectorStatus.ERROR:
            logger.warning("Adapter in error state, using local cache only")
            return self._get_cached_threats(cve_ids)

        # Try to get from adapter
        try:
            return await self.adapter.get_threat_context(cve_ids)
        except Exception as e:
            logger.warning(f"Failed to get threat context from adapter: {e}")
            return self._get_cached_threats(cve_ids)

    def _get_cached_threats(self, cve_ids: list[str]) -> list[ThreatContext]:
        """Get threats from local cache."""
        threats = []
        vuln_store = self._local_store.get("vulnerability", {})
        for cve_id in cve_ids:
            if cve_id in vuln_store:
                # Convert stored dict to ThreatContext
                data = vuln_store[cve_id]
                threats.append(
                    ThreatContext(
                        threat_id=data.get("threat_id", cve_id),
                        source_platform="cache",
                        cves=[cve_id],
                        epss_score=data.get("epss_score"),
                        mitre_ttps=data.get("mitre_ttps", []),
                    )
                )
        return threats

    async def get_asset_criticality(
        self,
        repo_id: str,
    ) -> AssetContext | None:
        """
        Get asset criticality, using local cache if available.

        Args:
            repo_id: Repository identifier

        Returns:
            AssetContext or None
        """
        # Check adapter health
        if self.adapter.status == ConnectorStatus.ERROR:
            logger.warning("Adapter in error state, using local cache")
            return self._get_cached_asset(repo_id)

        try:
            return await self.adapter.get_asset_criticality(repo_id)
        except Exception as e:
            logger.warning(f"Failed to get asset criticality: {e}")
            return self._get_cached_asset(repo_id)

    def _get_cached_asset(self, repo_id: str) -> AssetContext | None:
        """Get asset from local cache."""
        asset_store = self._local_store.get("asset", {})
        data = asset_store.get(repo_id)
        if data:
            return AssetContext(
                asset_id=data.get("asset_id", repo_id),
                criticality_score=data.get("criticality_score", 5),
                pii_handling=data.get("pii_handling", False),
                phi_handling=data.get("phi_handling", False),
            )
        return None
