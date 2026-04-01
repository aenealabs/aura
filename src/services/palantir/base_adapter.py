"""
Enterprise Data Platform Adapter - Abstract Base Class

Implements ADR-074: Enterprise Data Platform Abstraction Layer

Provides a platform-agnostic interface for integrating with enterprise
data platforms like Palantir AIP, Databricks, Snowflake, and ServiceNow.

This abstraction enables:
- Future platform integrations without architectural changes
- Consistent interface across different data platforms
- Standardized metrics and status tracking
- Unified error handling and resilience patterns
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import aiohttp

from src.services.palantir.types import (
    AssetContext,
    PalantirObjectType,
    RemediationEvent,
    SyncResult,
    ThreatContext,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Status and Result Types
# =============================================================================


class ConnectorStatus(Enum):
    """Status of a data platform connector."""

    CONNECTED = "connected"  # Successfully connected
    DISCONNECTED = "disconnected"  # Not connected
    ERROR = "error"  # Connection error
    RATE_LIMITED = "rate_limited"  # API rate limit hit
    AUTH_FAILED = "auth_failed"  # Authentication failure
    CIRCUIT_OPEN = "circuit_open"  # Circuit breaker is open


@dataclass
class ConnectorResult:
    """Result from a connector operation."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    status_code: int | None = None
    latency_ms: float = 0.0
    request_id: str | None = None
    cached: bool = False

    @classmethod
    def ok(
        cls,
        data: dict[str, Any] | None = None,
        latency_ms: float = 0.0,
        cached: bool = False,
    ) -> "ConnectorResult":
        """Create a successful result."""
        return cls(
            success=True,
            data=data or {},
            latency_ms=latency_ms,
            cached=cached,
        )

    @classmethod
    def fail(
        cls,
        error: str,
        status_code: int | None = None,
        latency_ms: float = 0.0,
    ) -> "ConnectorResult":
        """Create a failed result."""
        return cls(
            success=False,
            error=error,
            status_code=status_code,
            latency_ms=latency_ms,
        )


# =============================================================================
# Abstract Base Class
# =============================================================================


class EnterpriseDataPlatformAdapter(ABC):
    """
    Abstract adapter for enterprise data platforms.

    Provides a consistent interface for retrieving threat intelligence,
    asset context, and publishing remediation events to platforms like
    Palantir AIP, Databricks, Snowflake, and ServiceNow.

    Subclasses must implement:
    - get_threat_context(): Retrieve threat data for CVEs
    - get_asset_criticality(): Get asset business context
    - publish_remediation_event(): Send events to the platform
    - sync_objects(): Synchronize ontology/catalog objects
    - health_check(): Verify platform connectivity

    Usage:
        >>> class MyPlatformAdapter(EnterpriseDataPlatformAdapter):
        ...     async def get_threat_context(self, cve_ids):
        ...         # Platform-specific implementation
        ...         pass
        >>> adapter = MyPlatformAdapter("my_platform")
        >>> threats = await adapter.get_threat_context(["CVE-2024-1234"])
    """

    def __init__(
        self,
        name: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize the adapter.

        Args:
            name: Platform identifier (e.g., "palantir_aip", "databricks")
            timeout_seconds: HTTP request timeout
            max_retries: Maximum retry attempts for failed requests
        """
        self.name = name
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.max_retries = max_retries

        # Status tracking
        self._status = ConnectorStatus.DISCONNECTED
        self._last_error: str | None = None
        self._last_error_time: datetime | None = None

        # Metrics tracking
        self._request_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0
        self._cache_hits = 0
        self._cache_misses = 0
        self._created_at = datetime.now(timezone.utc)
        self._last_request_time: datetime | None = None

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def status(self) -> ConnectorStatus:
        """Get current connector status."""
        return self._status

    @property
    def is_healthy(self) -> bool:
        """Check if connector is in a healthy state."""
        return self._status in (ConnectorStatus.CONNECTED, ConnectorStatus.DISCONNECTED)

    @property
    def metrics(self) -> dict[str, Any]:
        """Get connector metrics for monitoring."""
        return {
            "name": self.name,
            "status": self._status.value,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": (
                self._error_count / self._request_count
                if self._request_count > 0
                else 0.0
            ),
            "avg_latency_ms": (
                self._total_latency_ms / self._request_count
                if self._request_count > 0
                else 0.0
            ),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0.0
            ),
            "last_error": self._last_error,
            "last_error_time": (
                self._last_error_time.isoformat() if self._last_error_time else None
            ),
            "last_request_time": (
                self._last_request_time.isoformat() if self._last_request_time else None
            ),
            "uptime_seconds": (
                datetime.now(timezone.utc) - self._created_at
            ).total_seconds(),
        }

    # =========================================================================
    # Metrics Recording
    # =========================================================================

    def _record_request(
        self,
        latency_ms: float,
        success: bool,
        cached: bool = False,
    ) -> None:
        """Record request metrics."""
        self._request_count += 1
        self._total_latency_ms += latency_ms
        self._last_request_time = datetime.now(timezone.utc)

        if cached:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

        if not success:
            self._error_count += 1

    def _record_error(self, error: str) -> None:
        """Record an error."""
        self._last_error = error
        self._last_error_time = datetime.now(timezone.utc)
        self._status = ConnectorStatus.ERROR
        logger.error(f"[{self.name}] Error: {error}")

    def _set_status(self, status: ConnectorStatus) -> None:
        """Update connector status."""
        if self._status != status:
            logger.info(
                f"[{self.name}] Status changed: {self._status.value} -> {status.value}"
            )
            self._status = status

    # =========================================================================
    # Abstract Methods - Must be implemented by subclasses
    # =========================================================================

    @abstractmethod
    async def get_threat_context(
        self,
        cve_ids: list[str],
    ) -> list[ThreatContext]:
        """
        Retrieve threat context for given CVEs.

        Queries the data platform for threat intelligence related to
        the specified CVE IDs, including EPSS scores, active campaigns,
        threat actors, and MITRE ATT&CK techniques.

        Args:
            cve_ids: List of CVE identifiers (e.g., ["CVE-2024-1234"])

        Returns:
            List of ThreatContext objects with threat intelligence

        Raises:
            ConnectionError: If platform is unreachable
            AuthenticationError: If credentials are invalid
        """

    @abstractmethod
    async def get_asset_criticality(
        self,
        repo_id: str,
    ) -> AssetContext | None:
        """
        Get asset criticality for a repository.

        Retrieves business context for a repository from the platform's
        CMDB or asset inventory, including criticality score, data
        classification, and compliance requirements.

        Args:
            repo_id: Repository identifier

        Returns:
            AssetContext if found, None if not mapped

        Raises:
            ConnectionError: If platform is unreachable
            AuthenticationError: If credentials are invalid
        """

    @abstractmethod
    async def publish_remediation_event(
        self,
        event: RemediationEvent,
    ) -> bool:
        """
        Publish remediation status to the platform.

        Sends an event to the data platform for dashboarding,
        analytics, and compliance evidence.

        Args:
            event: RemediationEvent to publish

        Returns:
            True if published successfully

        Raises:
            ConnectionError: If platform is unreachable
            PublishError: If event could not be published
        """

    @abstractmethod
    async def sync_objects(
        self,
        object_type: PalantirObjectType,
        full_sync: bool = False,
    ) -> SyncResult:
        """
        Sync objects from the platform.

        Synchronizes ontology objects (threat actors, vulnerabilities,
        assets) from the platform to Aura's local cache.

        Args:
            object_type: Type of objects to sync
            full_sync: If True, sync all objects; if False, incremental

        Returns:
            SyncResult with sync statistics

        Raises:
            ConnectionError: If platform is unreachable
            SyncError: If sync could not be completed
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify platform connectivity.

        Tests the connection to the data platform and updates
        the connector status accordingly.

        Returns:
            True if platform is reachable and authenticated

        Raises:
            No exceptions - always returns bool
        """

    # =========================================================================
    # Optional Methods - Can be overridden by subclasses
    # =========================================================================

    async def get_active_threats(self) -> list[ThreatContext]:
        """
        Get currently active threat campaigns.

        Override this method to provide platform-specific implementation
        for retrieving active threat campaigns.

        Returns:
            List of active ThreatContext objects
        """
        logger.warning(f"[{self.name}] get_active_threats not implemented")
        return []

    async def get_threat_actors(self) -> list[dict[str, Any]]:
        """
        Get known threat actors from the platform.

        Override this method to retrieve threat actor catalog.

        Returns:
            List of threat actor dictionaries
        """
        logger.warning(f"[{self.name}] get_threat_actors not implemented")
        return []

    async def search_vulnerabilities(
        self,
        query: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Search for vulnerabilities matching a query.

        Override this method for platform-specific vulnerability search.

        Args:
            query: Search query string
            limit: Maximum results to return

        Returns:
            List of vulnerability dictionaries
        """
        logger.warning(f"[{self.name}] search_vulnerabilities not implemented")
        return []

    async def close(self) -> None:
        """
        Clean up resources.

        Override this method to close HTTP sessions, database
        connections, or other resources.
        """
        self._set_status(ConnectorStatus.DISCONNECTED)
        logger.info(f"[{self.name}] Adapter closed")


# =============================================================================
# Helper Functions
# =============================================================================


def measure_latency(func):
    """Decorator to measure and record request latency."""

    async def wrapper(self: EnterpriseDataPlatformAdapter, *args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = await func(self, *args, **kwargs)
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._record_request(
                latency_ms=latency_ms,
                success=True,
                cached=(
                    getattr(result, "cached", False)
                    if hasattr(result, "cached")
                    else False
                ),
            )
            return result
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._record_request(latency_ms=latency_ms, success=False)
            self._record_error(str(e))
            raise

    return wrapper
