"""
Palantir AIP Adapter

Implements ADR-074: Palantir AIP Integration

Concrete implementation of EnterpriseDataPlatformAdapter for Palantir AIP,
providing:
- Ontology object retrieval (ThreatActor, Vulnerability, Asset)
- Event publishing to Foundry pipelines
- mTLS authentication support
- Circuit breaker integration for resilience
"""

import json
import logging
import os
import ssl
import time
from datetime import datetime, timezone
from typing import Any

import aiohttp

from src.services.palantir.base_adapter import (
    ConnectorResult,
    ConnectorStatus,
    EnterpriseDataPlatformAdapter,
)
from src.services.palantir.types import (
    AssetContext,
    DataClassification,
    PalantirObjectType,
    RemediationEvent,
    SyncResult,
    SyncStatus,
    ThreatActor,
    ThreatContext,
)

logger = logging.getLogger(__name__)


class PalantirAIPAdapter(EnterpriseDataPlatformAdapter):
    """
    Palantir AIP-specific implementation of the data platform adapter.

    Provides integration with Palantir Ontology and Foundry APIs for:
    - Threat intelligence retrieval
    - Asset criticality lookup
    - Remediation event publishing
    - Object synchronization

    Supports both commercial and GovCloud deployments with mTLS auth.

    Usage:
        >>> adapter = PalantirAIPAdapter(
        ...     ontology_api_url="https://org.palantirfoundry.com/ontology",
        ...     foundry_api_url="https://org.palantirfoundry.com/foundry",
        ...     api_key="your-api-key",
        ... )
        >>> threats = await adapter.get_threat_context(["CVE-2024-1234"])
    """

    def __init__(
        self,
        ontology_api_url: str,
        foundry_api_url: str,
        api_key: str,
        client_cert_path: str | None = None,
        client_key_path: str | None = None,
        ca_cert_path: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        verify_ssl: bool = True,
    ) -> None:
        """
        Initialize the Palantir AIP adapter.

        Args:
            ontology_api_url: Palantir Ontology API base URL
            foundry_api_url: Palantir Foundry API base URL
            api_key: API key for authentication
            client_cert_path: Path to mTLS client certificate (optional)
            client_key_path: Path to mTLS client key (optional)
            ca_cert_path: Path to CA certificate bundle (optional)
            timeout_seconds: HTTP request timeout
            max_retries: Maximum retry attempts
            verify_ssl: Whether to verify SSL certificates
        """
        super().__init__(
            name="palantir_aip",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

        self.ontology_api_url = ontology_api_url.rstrip("/")
        self.foundry_api_url = foundry_api_url.rstrip("/")
        self._api_key = api_key
        self._client_cert_path = client_cert_path
        self._client_key_path = client_key_path
        self._ca_cert_path = ca_cert_path
        self._verify_ssl = verify_ssl

        # Session management
        self._session: aiohttp.ClientSession | None = None
        self._ssl_context: ssl.SSLContext | None = None

        # Cache for frequently accessed data
        self._threat_cache: dict[str, tuple[ThreatContext, datetime]] = {}
        self._asset_cache: dict[str, tuple[AssetContext, datetime]] = {}
        self._cache_ttl_seconds = int(os.getenv("PALANTIR_CACHE_TTL_SECONDS", "300"))

        # Circuit breaker state (managed externally via PalantirCircuitBreaker)
        self._circuit_open = False

    # =========================================================================
    # Session Management
    # =========================================================================

    def _get_ssl_context(self) -> ssl.SSLContext | None:
        """Create SSL context for mTLS authentication."""
        if self._ssl_context is not None:
            return self._ssl_context

        if not self._verify_ssl:
            return False  # Disable SSL verification

        if self._client_cert_path and self._client_key_path:
            # mTLS configuration
            self._ssl_context = ssl.create_default_context()
            self._ssl_context.load_cert_chain(
                certfile=self._client_cert_path,
                keyfile=self._client_key_path,
            )
            if self._ca_cert_path:
                self._ssl_context.load_verify_locations(cafile=self._ca_cert_path)
            logger.info("[palantir_aip] mTLS configured with client certificate")
            return self._ssl_context

        return None  # Use default SSL verification

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            ssl_context = self._get_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=connector,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Aura-Platform/1.0 (ADR-074)",
                },
            )
        return self._session

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Aura-Platform/1.0 (ADR-074)",
        }

    # =========================================================================
    # Cache Management
    # =========================================================================

    def _get_cached_threat(self, cve_id: str) -> ThreatContext | None:
        """Get threat from cache if not expired."""
        if cve_id in self._threat_cache:
            threat, cached_at = self._threat_cache[cve_id]
            age_seconds = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age_seconds < self._cache_ttl_seconds:
                return threat
            # Expired, remove from cache
            del self._threat_cache[cve_id]
        return None

    def _cache_threat(self, cve_id: str, threat: ThreatContext) -> None:
        """Cache threat context."""
        self._threat_cache[cve_id] = (threat, datetime.now(timezone.utc))

    def _get_cached_asset(self, repo_id: str) -> AssetContext | None:
        """Get asset from cache if not expired."""
        if repo_id in self._asset_cache:
            asset, cached_at = self._asset_cache[repo_id]
            age_seconds = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age_seconds < self._cache_ttl_seconds:
                return asset
            del self._asset_cache[repo_id]
        return None

    def _cache_asset(self, repo_id: str, asset: AssetContext) -> None:
        """Cache asset context."""
        self._asset_cache[repo_id] = (asset, datetime.now(timezone.utc))

    # =========================================================================
    # API Methods
    # =========================================================================

    async def _make_request(
        self,
        method: str,
        url: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        """Make HTTP request to Palantir API."""
        if self._circuit_open:
            return ConnectorResult.fail(
                error="Circuit breaker is open",
                status_code=503,
            )

        start_time = time.perf_counter()
        session = await self._get_session()

        try:
            async with session.request(
                method=method,
                url=url,
                json=data,
                params=params,
            ) as response:
                latency_ms = (time.perf_counter() - start_time) * 1000
                body = await response.text()

                if response.status == 200:
                    self._set_status(ConnectorStatus.CONNECTED)
                    return ConnectorResult.ok(
                        data=json.loads(body) if body else {},
                        latency_ms=latency_ms,
                    )
                elif response.status == 401:
                    self._set_status(ConnectorStatus.AUTH_FAILED)
                    return ConnectorResult.fail(
                        error="Authentication failed",
                        status_code=401,
                        latency_ms=latency_ms,
                    )
                elif response.status == 429:
                    self._set_status(ConnectorStatus.RATE_LIMITED)
                    return ConnectorResult.fail(
                        error="Rate limited",
                        status_code=429,
                        latency_ms=latency_ms,
                    )
                else:
                    return ConnectorResult.fail(
                        error=f"Request failed: {response.status} - {body[:200]}",
                        status_code=response.status,
                        latency_ms=latency_ms,
                    )

        except aiohttp.ClientError as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._record_error(str(e))
            return ConnectorResult.fail(
                error=f"Connection error: {str(e)}",
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._record_error(str(e))
            return ConnectorResult.fail(
                error=f"Unexpected error: {str(e)}",
                latency_ms=latency_ms,
            )

    # =========================================================================
    # Abstract Method Implementations
    # =========================================================================

    async def get_threat_context(
        self,
        cve_ids: list[str],
    ) -> list[ThreatContext]:
        """
        Retrieve threat context for given CVEs from Palantir Ontology.

        Queries the ThreatActor and Vulnerability objects to get:
        - EPSS scores
        - Active threat campaigns
        - MITRE ATT&CK techniques
        - Targeted industries

        Args:
            cve_ids: List of CVE identifiers

        Returns:
            List of ThreatContext objects
        """
        threats: list[ThreatContext] = []

        for cve_id in cve_ids:
            # Check cache first
            cached = self._get_cached_threat(cve_id)
            if cached:
                self._cache_hits += 1
                threats.append(cached)
                continue

            self._cache_misses += 1

            # Query Palantir Ontology
            url = f"{self.ontology_api_url}/api/v2/objects/Vulnerability/search"
            result = await self._make_request(
                method="POST",
                url=url,
                data={
                    "query": {
                        "type": "eq",
                        "field": "cve_id",
                        "value": cve_id,
                    },
                    "pageSize": 1,
                },
            )

            if result.success and result.data.get("objects"):
                vuln_obj = result.data["objects"][0]
                threat = self._map_vulnerability_to_threat_context(vuln_obj)
                self._cache_threat(cve_id, threat)
                threats.append(threat)
            else:
                # Create minimal threat context for unknown CVE
                threat = ThreatContext(
                    threat_id=cve_id,
                    source_platform="palantir_aip",
                    cves=[cve_id],
                    severity="medium",
                )
                threats.append(threat)

            self._record_request(
                latency_ms=result.latency_ms,
                success=result.success,
                cached=False,
            )

        return threats

    async def get_asset_criticality(
        self,
        repo_id: str,
    ) -> AssetContext | None:
        """
        Get asset criticality for a repository from Palantir CMDB.

        Args:
            repo_id: Repository identifier

        Returns:
            AssetContext if found, None otherwise
        """
        # Check cache first
        cached = self._get_cached_asset(repo_id)
        if cached:
            self._cache_hits += 1
            return cached

        self._cache_misses += 1

        # Query Palantir Ontology for Asset mapping
        url = f"{self.ontology_api_url}/api/v2/objects/Asset/search"
        result = await self._make_request(
            method="POST",
            url=url,
            data={
                "query": {
                    "type": "eq",
                    "field": "repository_id",
                    "value": repo_id,
                },
                "pageSize": 1,
            },
        )

        self._record_request(
            latency_ms=result.latency_ms,
            success=result.success,
            cached=False,
        )

        if result.success and result.data.get("objects"):
            asset_obj = result.data["objects"][0]
            asset = self._map_asset_to_context(asset_obj)
            self._cache_asset(repo_id, asset)
            return asset

        return None

    async def publish_remediation_event(
        self,
        event: RemediationEvent,
    ) -> bool:
        """
        Publish remediation event to Palantir Foundry.

        Args:
            event: RemediationEvent to publish

        Returns:
            True if published successfully
        """
        url = f"{self.foundry_api_url}/api/v1/datasets/aura-remediation-events/transactions/commit"

        result = await self._make_request(
            method="POST",
            url=url,
            data={
                "records": [event.to_dict()],
            },
        )

        self._record_request(
            latency_ms=result.latency_ms,
            success=result.success,
            cached=False,
        )

        if not result.success:
            logger.error(
                f"[palantir_aip] Failed to publish event {event.event_id}: {result.error}"
            )

        return result.success

    async def sync_objects(
        self,
        object_type: PalantirObjectType,
        full_sync: bool = False,
    ) -> SyncResult:
        """
        Sync objects from Palantir Ontology.

        Args:
            object_type: Type of objects to sync
            full_sync: If True, sync all objects

        Returns:
            SyncResult with statistics
        """
        result = SyncResult(
            object_type=object_type,
            status=SyncStatus.PENDING,
        )

        # Map object type to Palantir Ontology object name
        object_names = {
            PalantirObjectType.THREAT_ACTOR: "ThreatActor",
            PalantirObjectType.VULNERABILITY: "Vulnerability",
            PalantirObjectType.ASSET: "Asset",
            PalantirObjectType.REPOSITORY: "Repository",
            PalantirObjectType.COMPLIANCE: "ComplianceControl",
        }

        ontology_object = object_names.get(object_type)
        if not ontology_object:
            result.status = SyncStatus.FAILED
            result.error_message = f"Unknown object type: {object_type}"
            return result

        url = f"{self.ontology_api_url}/api/v2/objects/{ontology_object}/search"
        page_token: str | None = None
        page_size = 1000

        try:
            while True:
                request_data: dict[str, Any] = {
                    "pageSize": page_size,
                    "query": {"type": "matchAll"},
                }
                if page_token:
                    request_data["pageToken"] = page_token

                api_result = await self._make_request(
                    method="POST",
                    url=url,
                    data=request_data,
                )

                if not api_result.success:
                    result.status = SyncStatus.FAILED
                    result.error_message = api_result.error
                    result.objects_failed += 1
                    break

                objects = api_result.data.get("objects", [])
                result.objects_synced += len(objects)

                # Get next page token
                page_token = api_result.data.get("nextPageToken")
                if not page_token:
                    break

            if result.error_message is None:
                result.status = SyncStatus.SYNCED
            result.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            result.status = SyncStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now(timezone.utc)
            logger.error(f"[palantir_aip] Sync failed for {object_type.value}: {e}")

        return result

    async def health_check(self) -> bool:
        """
        Verify Palantir API connectivity.

        Returns:
            True if API is reachable and authenticated
        """
        url = f"{self.ontology_api_url}/api/v2/health"
        result = await self._make_request(method="GET", url=url)

        self._record_request(
            latency_ms=result.latency_ms,
            success=result.success,
            cached=False,
        )

        if result.success:
            self._set_status(ConnectorStatus.CONNECTED)
            return True

        return False

    # =========================================================================
    # Additional Methods
    # =========================================================================

    async def get_active_threats(self) -> list[ThreatContext]:
        """Get currently active threat campaigns from Palantir."""
        url = f"{self.ontology_api_url}/api/v2/objects/ThreatActor/search"
        result = await self._make_request(
            method="POST",
            url=url,
            data={
                "query": {
                    "type": "eq",
                    "field": "is_active",
                    "value": True,
                },
                "pageSize": 100,
            },
        )

        self._record_request(
            latency_ms=result.latency_ms,
            success=result.success,
            cached=False,
        )

        threats: list[ThreatContext] = []
        if result.success:
            for actor_obj in result.data.get("objects", []):
                threats.append(self._map_threat_actor_to_context(actor_obj))

        return threats

    async def get_threat_actors(self) -> list[ThreatActor]:
        """Get known threat actors from Palantir Ontology."""
        url = f"{self.ontology_api_url}/api/v2/objects/ThreatActor/search"
        result = await self._make_request(
            method="POST",
            url=url,
            data={
                "query": {"type": "matchAll"},
                "pageSize": 1000,
            },
        )

        self._record_request(
            latency_ms=result.latency_ms,
            success=result.success,
            cached=False,
        )

        actors: list[ThreatActor] = []
        if result.success:
            for actor_obj in result.data.get("objects", []):
                actors.append(self._map_to_threat_actor(actor_obj))

        return actors

    async def close(self) -> None:
        """Close HTTP session and clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._threat_cache.clear()
        self._asset_cache.clear()
        self._set_status(ConnectorStatus.DISCONNECTED)
        logger.info("[palantir_aip] Adapter closed")

    # =========================================================================
    # Mapping Methods
    # =========================================================================

    def _map_vulnerability_to_threat_context(
        self,
        vuln_obj: dict[str, Any],
    ) -> ThreatContext:
        """Map Palantir Vulnerability object to ThreatContext."""
        props = vuln_obj.get("properties", {})
        return ThreatContext(
            threat_id=vuln_obj.get("primaryKey", props.get("cve_id", "")),
            source_platform="palantir_aip",
            cves=[props.get("cve_id", "")],
            epss_score=props.get("epss_score"),
            mitre_ttps=props.get("mitre_techniques", []),
            targeted_industries=props.get("targeted_industries", []),
            active_campaigns=props.get("active_campaigns", []),
            threat_actors=props.get("associated_actors", []),
            first_seen=(
                datetime.fromisoformat(props["first_seen"])
                if props.get("first_seen")
                else None
            ),
            last_seen=(
                datetime.fromisoformat(props["last_seen"])
                if props.get("last_seen")
                else None
            ),
            severity=props.get("severity", "medium"),
            raw_metadata=props,
        )

    def _map_threat_actor_to_context(
        self,
        actor_obj: dict[str, Any],
    ) -> ThreatContext:
        """Map Palantir ThreatActor object to ThreatContext."""
        props = actor_obj.get("properties", {})
        return ThreatContext(
            threat_id=actor_obj.get("primaryKey", props.get("actor_id", "")),
            source_platform="palantir_aip",
            cves=props.get("exploited_cves", []),
            epss_score=None,  # Actors don't have EPSS
            mitre_ttps=props.get("ttps", []),
            targeted_industries=props.get("targeted_industries", []),
            active_campaigns=props.get("active_campaigns", []),
            threat_actors=[props.get("name", "")],
            severity="high" if props.get("is_active") else "medium",
            raw_metadata=props,
        )

    def _map_to_threat_actor(
        self,
        actor_obj: dict[str, Any],
    ) -> ThreatActor:
        """Map Palantir ThreatActor object to ThreatActor dataclass."""
        props = actor_obj.get("properties", {})
        return ThreatActor(
            actor_id=actor_obj.get("primaryKey", props.get("actor_id", "")),
            name=props.get("name", "Unknown"),
            aliases=props.get("aliases", []),
            ttps=props.get("ttps", []),
            targeted_industries=props.get("targeted_industries", []),
            targeted_regions=props.get("targeted_regions", []),
            active_since=(
                datetime.fromisoformat(props["active_since"])
                if props.get("active_since")
                else None
            ),
            last_activity=(
                datetime.fromisoformat(props["last_activity"])
                if props.get("last_activity")
                else None
            ),
            attribution=props.get("attribution"),
            description=props.get("description"),
        )

    def _map_asset_to_context(
        self,
        asset_obj: dict[str, Any],
    ) -> AssetContext:
        """Map Palantir Asset object to AssetContext."""
        props = asset_obj.get("properties", {})

        # Map data classification string to enum
        classification_str = props.get("data_classification", "internal").lower()
        classification_map = {
            "public": DataClassification.PUBLIC,
            "internal": DataClassification.INTERNAL,
            "confidential": DataClassification.CONFIDENTIAL,
            "restricted": DataClassification.RESTRICTED,
            "top_secret": DataClassification.TOP_SECRET,
        }
        classification = classification_map.get(
            classification_str, DataClassification.INTERNAL
        )

        return AssetContext(
            asset_id=asset_obj.get("primaryKey", props.get("asset_id", "")),
            criticality_score=props.get("criticality_score", 5),
            data_classification=classification,
            business_owner=props.get("business_owner"),
            technical_owner=props.get("technical_owner"),
            department=props.get("department"),
            cost_center=props.get("cost_center"),
            pii_handling=props.get("handles_pii", False),
            phi_handling=props.get("handles_phi", False),
            pci_scope=props.get("pci_scope", False),
            internet_facing=props.get("internet_facing", False),
            environment=props.get("environment", "unknown"),
            tags=props.get("tags", {}),
        )

    # =========================================================================
    # Circuit Breaker Support
    # =========================================================================

    def set_circuit_state(self, is_open: bool) -> None:
        """Set circuit breaker state (called by PalantirCircuitBreaker)."""
        self._circuit_open = is_open
        if is_open:
            self._set_status(ConnectorStatus.CIRCUIT_OPEN)
        else:
            self._set_status(ConnectorStatus.CONNECTED)

    def get_cached_threat_context(self, cve_ids: list[str]) -> list[ThreatContext]:
        """
        Get cached threat context for fallback when circuit is open.

        Returns whatever is available in cache, even if expired.
        """
        threats: list[ThreatContext] = []
        for cve_id in cve_ids:
            if cve_id in self._threat_cache:
                threat, _ = self._threat_cache[cve_id]
                threats.append(threat)
        return threats

    def get_cached_asset_context(self, repo_id: str) -> AssetContext | None:
        """
        Get cached asset context for fallback when circuit is open.

        Returns whatever is available in cache, even if expired.
        """
        if repo_id in self._asset_cache:
            asset, _ = self._asset_cache[repo_id]
            return asset
        return None
