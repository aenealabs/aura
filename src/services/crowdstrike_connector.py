"""
Project Aura - CrowdStrike Falcon Connector

Implements ADR-028 Phase 8 Extension: Security Tool Connectors

CrowdStrike Falcon REST API connector for:
- Host/device management and lookup
- Detection and incident queries
- IOC (Indicators of Compromise) management
- Threat intelligence queries
- Real-time response actions

SECURITY: Only available in ENTERPRISE or HYBRID mode.

Usage:
    >>> from src.services.crowdstrike_connector import CrowdStrikeConnector
    >>> cs = CrowdStrikeConnector(
    ...     client_id="your-client-id",
    ...     client_secret="your-client-secret"
    ... )
    >>> await cs.search_hosts(hostname="server01")
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiohttp

from src.config import require_enterprise_mode
from src.services.external_tool_connectors import (
    ConnectorResult,
    ConnectorStatus,
    ExternalToolConnector,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class CrowdStrikeCloud(Enum):
    """CrowdStrike cloud regions."""

    US1 = "api.crowdstrike.com"
    US2 = "api.us-2.crowdstrike.com"
    EU1 = "api.eu-1.crowdstrike.com"
    GOV = "api.laggar.gcw.crowdstrike.com"


class DetectionSeverity(Enum):
    """CrowdStrike detection severity levels."""

    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DetectionStatus(Enum):
    """CrowdStrike detection status."""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    IGNORED = "ignored"
    CLOSED = "closed"


class HostStatus(Enum):
    """CrowdStrike host status."""

    NORMAL = "normal"
    CONTAINMENT_PENDING = "containment_pending"
    CONTAINED = "contained"
    LIFT_CONTAINMENT_PENDING = "lift_containment_pending"


class IOCType(Enum):
    """CrowdStrike IOC types."""

    SHA256 = "sha256"
    MD5 = "md5"
    DOMAIN = "domain"
    IPV4 = "ipv4"
    IPV6 = "ipv6"


class IOCAction(Enum):
    """CrowdStrike IOC actions."""

    DETECT = "detect"
    PREVENT = "prevent"
    ALLOW = "allow"
    NO_ACTION = "no_action"


@dataclass
class CrowdStrikeHost:
    """CrowdStrike host/device details."""

    device_id: str
    hostname: str
    platform_name: str | None = None
    os_version: str | None = None
    agent_version: str | None = None
    status: HostStatus | None = None
    last_seen: str | None = None
    local_ip: str | None = None
    external_ip: str | None = None
    mac_address: str | None = None
    system_manufacturer: str | None = None
    system_product_name: str | None = None
    groups: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class CrowdStrikeDetection:
    """CrowdStrike detection details."""

    detection_id: str
    device_id: str
    hostname: str
    severity: DetectionSeverity
    status: DetectionStatus
    tactic: str | None = None
    technique: str | None = None
    description: str = ""
    behaviors: list[dict[str, Any]] = field(default_factory=list)
    ioc_type: str | None = None
    ioc_value: str | None = None
    timestamp: str | None = None


@dataclass
class CrowdStrikeIOC:
    """CrowdStrike IOC structure."""

    type: IOCType
    value: str
    action: IOCAction = IOCAction.DETECT
    severity: DetectionSeverity = DetectionSeverity.MEDIUM
    description: str = ""
    platforms: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    expiration: str | None = None


# =============================================================================
# CrowdStrike Connector
# =============================================================================


class CrowdStrikeConnector(ExternalToolConnector):
    """
    CrowdStrike Falcon connector for EDR/XDR integration.

    Supports:
    - Host/device management
    - Detection and incident queries
    - IOC management
    - Threat intelligence
    - Real-time response (containment)
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        cloud: CrowdStrikeCloud = CrowdStrikeCloud.US1,
        timeout_seconds: float = 30.0,
    ):
        """
        Initialize CrowdStrike connector.

        Args:
            client_id: API client ID
            client_secret: API client secret
            cloud: CrowdStrike cloud region
            timeout_seconds: Request timeout
        """
        super().__init__("crowdstrike", timeout_seconds)

        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = f"https://{cloud.value}"

        # OAuth2 token management
        self._access_token: str | None = None
        self._token_expiry: float = 0

    async def _ensure_token(self) -> str:
        """Ensure we have a valid OAuth2 token."""
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.base_url}/oauth2/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if response.status == 201:
                    data = await response.json()
                    self._access_token = data.get("access_token")
                    expires_in = data.get("expires_in", 1800)
                    self._token_expiry = time.time() + expires_in
                    self._status = ConnectorStatus.CONNECTED
                    return self._access_token
                else:
                    self._status = ConnectorStatus.AUTH_FAILED
                    raise RuntimeError(
                        f"Failed to get CrowdStrike token: {response.status}"
                    )

    def _get_headers(self, token: str) -> dict[str, str]:
        """Get request headers with OAuth token."""
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # =========================================================================
    # Host Management
    # =========================================================================

    @require_enterprise_mode
    async def search_hosts(
        self,
        hostname: str | None = None,
        platform: str | None = None,
        status: HostStatus | None = None,
        local_ip: str | None = None,
        external_ip: str | None = None,
        limit: int = 100,
    ) -> ConnectorResult:
        """
        Search for hosts/devices.

        Args:
            hostname: Filter by hostname (supports wildcards)
            platform: Filter by platform (Windows, Mac, Linux)
            status: Filter by containment status
            local_ip: Filter by local IP
            external_ip: Filter by external IP
            limit: Maximum results
        """
        start_time = time.time()

        try:
            token = await self._ensure_token()

            # Build FQL filter
            filters = []
            if hostname:
                filters.append(f"hostname:'{hostname}'")
            if platform:
                filters.append(f"platform_name:'{platform}'")
            if status:
                filters.append(f"status:'{status.value}'")
            if local_ip:
                filters.append(f"local_ip:'{local_ip}'")
            if external_ip:
                filters.append(f"external_ip:'{external_ip}'")

            params: dict[str, Any] = {"limit": limit}
            if filters:
                params["filter"] = "+".join(filters)

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # First get device IDs
                async with session.get(
                    f"{self.base_url}/devices/queries/devices/v1",
                    params=params,
                    headers=self._get_headers(token),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000

                    if response.status != 200:
                        data = await response.json()
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=str(data.get("errors", data)),
                            latency_ms=latency_ms,
                        )

                    data = await response.json()
                    device_ids = data.get("resources", [])

                    if not device_ids:
                        self._record_request(latency_ms, True)
                        return ConnectorResult(
                            success=True,
                            status_code=200,
                            data={"hosts": [], "count": 0},
                            latency_ms=latency_ms,
                        )

                # Get device details
                async with session.post(
                    f"{self.base_url}/devices/entities/devices/v2",
                    json={"ids": device_ids[:100]},
                    headers=self._get_headers(token),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    if response.status == 200:
                        self._record_request(latency_ms, True)
                        hosts = [
                            {
                                "device_id": h.get("device_id"),
                                "hostname": h.get("hostname"),
                                "platform": h.get("platform_name"),
                                "os_version": h.get("os_version"),
                                "agent_version": h.get("agent_version"),
                                "status": h.get("status"),
                                "last_seen": h.get("last_seen"),
                                "local_ip": h.get("local_ip"),
                                "external_ip": h.get("external_ip"),
                            }
                            for h in data.get("resources", [])
                        ]
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={"hosts": hosts, "count": len(hosts)},
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=str(data.get("errors", data)),
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.exception(f"CrowdStrike connector error: {e}")
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def get_host(self, device_id: str) -> ConnectorResult:
        """
        Get host details by device ID.

        Args:
            device_id: CrowdStrike device ID
        """
        start_time = time.time()

        try:
            token = await self._ensure_token()

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/devices/entities/devices/v2",
                    json={"ids": [device_id]},
                    headers=self._get_headers(token),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success and data.get("resources"):
                        host = data["resources"][0]
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "device_id": host.get("device_id"),
                                "hostname": host.get("hostname"),
                                "platform": host.get("platform_name"),
                                "os_version": host.get("os_version"),
                                "agent_version": host.get("agent_version"),
                                "status": host.get("status"),
                                "last_seen": host.get("last_seen"),
                                "local_ip": host.get("local_ip"),
                                "external_ip": host.get("external_ip"),
                                "mac_address": host.get("mac_address"),
                                "system_manufacturer": host.get("system_manufacturer"),
                                "system_product_name": host.get("system_product_name"),
                                "groups": host.get("groups", []),
                                "tags": host.get("tags", []),
                            },
                            request_id=device_id,
                            latency_ms=latency_ms,
                        )
                    else:
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=(
                                "Host not found"
                                if success
                                else str(data.get("errors", data))
                            ),
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def contain_host(self, device_id: str) -> ConnectorResult:
        """
        Contain a host (network isolation).

        Args:
            device_id: Device ID to contain
        """
        start_time = time.time()

        try:
            token = await self._ensure_token()

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/devices/entities/devices-actions/v2",
                    params={"action_name": "contain"},
                    json={"ids": [device_id]},
                    headers=self._get_headers(token),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status in (200, 202)
                    self._record_request(latency_ms, success)

                    if success:
                        logger.info(f"Host contained: {device_id}")

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data=data,
                        request_id=device_id,
                        latency_ms=latency_ms,
                        error=None if success else str(data.get("errors", data)),
                    )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def lift_containment(self, device_id: str) -> ConnectorResult:
        """
        Lift containment from a host.

        Args:
            device_id: Device ID to release
        """
        start_time = time.time()

        try:
            token = await self._ensure_token()

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/devices/entities/devices-actions/v2",
                    params={"action_name": "lift_containment"},
                    json={"ids": [device_id]},
                    headers=self._get_headers(token),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status in (200, 202)
                    self._record_request(latency_ms, success)

                    if success:
                        logger.info(f"Containment lifted: {device_id}")

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data=data,
                        request_id=device_id,
                        latency_ms=latency_ms,
                        error=None if success else str(data.get("errors", data)),
                    )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    # =========================================================================
    # Detection Management
    # =========================================================================

    @require_enterprise_mode
    async def search_detections(
        self,
        severity: DetectionSeverity | None = None,
        status: DetectionStatus | None = None,
        hostname: str | None = None,
        max_severity: DetectionSeverity | None = None,
        limit: int = 100,
    ) -> ConnectorResult:
        """
        Search for detections.

        Args:
            severity: Filter by exact severity
            status: Filter by status
            hostname: Filter by hostname
            max_severity: Filter by maximum severity (critical includes all)
            limit: Maximum results
        """
        start_time = time.time()

        try:
            token = await self._ensure_token()

            # Build FQL filter
            filters = []
            if severity:
                filters.append(f"severity:'{severity.value}'")
            if max_severity:
                severity_levels = ["informational", "low", "medium", "high", "critical"]
                idx = severity_levels.index(max_severity.value)
                filters.append(f"max_severity_displayname:{severity_levels[idx:]}")
            if status:
                filters.append(f"status:'{status.value}'")
            if hostname:
                filters.append(f"device.hostname:'{hostname}'")

            params: dict[str, Any] = {"limit": limit}
            if filters:
                params["filter"] = "+".join(filters)

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Get detection IDs
                async with session.get(
                    f"{self.base_url}/detects/queries/detects/v1",
                    params=params,
                    headers=self._get_headers(token),
                ) as response:
                    if response.status != 200:
                        data = await response.json()
                        latency_ms = (time.time() - start_time) * 1000
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=str(data.get("errors", data)),
                            latency_ms=latency_ms,
                        )

                    data = await response.json()
                    detection_ids = data.get("resources", [])

                    if not detection_ids:
                        latency_ms = (time.time() - start_time) * 1000
                        self._record_request(latency_ms, True)
                        return ConnectorResult(
                            success=True,
                            status_code=200,
                            data={"detections": [], "count": 0},
                            latency_ms=latency_ms,
                        )

                # Get detection details
                async with session.post(
                    f"{self.base_url}/detects/entities/summaries/GET/v1",
                    json={"ids": detection_ids[:100]},
                    headers=self._get_headers(token),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    if response.status == 200:
                        self._record_request(latency_ms, True)
                        detections = [
                            {
                                "detection_id": d.get("detection_id"),
                                "device_id": d.get("device", {}).get("device_id"),
                                "hostname": d.get("device", {}).get("hostname"),
                                "severity": d.get("max_severity_displayname"),
                                "status": d.get("status"),
                                "tactic": (
                                    d.get("behaviors", [{}])[0].get("tactic")
                                    if d.get("behaviors")
                                    else None
                                ),
                                "technique": (
                                    d.get("behaviors", [{}])[0].get("technique")
                                    if d.get("behaviors")
                                    else None
                                ),
                                "description": (
                                    d.get("behaviors", [{}])[0].get("description", "")
                                    if d.get("behaviors")
                                    else ""
                                ),
                                "timestamp": d.get("first_behavior"),
                            }
                            for d in data.get("resources", [])
                        ]
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={"detections": detections, "count": len(detections)},
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=str(data.get("errors", data)),
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def update_detection_status(
        self,
        detection_ids: list[str],
        status: DetectionStatus,
        comment: str = "",
    ) -> ConnectorResult:
        """
        Update detection status.

        Args:
            detection_ids: List of detection IDs
            status: New status
            comment: Optional comment
        """
        start_time = time.time()

        try:
            token = await self._ensure_token()

            payload = {
                "ids": detection_ids,
                "status": status.value,
            }
            if comment:
                payload["comment"] = comment

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.patch(
                    f"{self.base_url}/detects/entities/detects/v2",
                    json=payload,
                    headers=self._get_headers(token),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data=data,
                        latency_ms=latency_ms,
                        error=None if success else str(data.get("errors", data)),
                    )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    # =========================================================================
    # IOC Management
    # =========================================================================

    @require_enterprise_mode
    async def search_iocs(
        self,
        ioc_type: IOCType | None = None,
        value: str | None = None,
        limit: int = 100,
    ) -> ConnectorResult:
        """
        Search for IOCs.

        Args:
            ioc_type: Filter by IOC type
            value: Filter by IOC value (supports wildcards)
            limit: Maximum results
        """
        start_time = time.time()

        try:
            token = await self._ensure_token()

            filters = []
            if ioc_type:
                filters.append(f"type:'{ioc_type.value}'")
            if value:
                filters.append(f"value:'{value}'")

            params: dict[str, Any] = {"limit": limit}
            if filters:
                params["filter"] = "+".join(filters)

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.base_url}/iocs/combined/indicator/v1",
                    params=params,
                    headers=self._get_headers(token),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        iocs = [
                            {
                                "id": i.get("id"),
                                "type": i.get("type"),
                                "value": i.get("value"),
                                "action": i.get("action"),
                                "severity": i.get("severity"),
                                "description": i.get("description", ""),
                                "platforms": i.get("platforms", []),
                                "created_on": i.get("created_on"),
                                "modified_on": i.get("modified_on"),
                            }
                            for i in data.get("resources", [])
                        ]
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={"iocs": iocs, "count": len(iocs)},
                            latency_ms=latency_ms,
                        )
                    else:
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=str(data.get("errors", data)),
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def create_ioc(
        self,
        ioc_type: IOCType,
        value: str,
        action: IOCAction = IOCAction.DETECT,
        severity: DetectionSeverity = DetectionSeverity.MEDIUM,
        description: str = "",
        platforms: list[str] | None = None,
        tags: list[str] | None = None,
        expiration: str | None = None,
    ) -> ConnectorResult:
        """
        Create a custom IOC.

        Args:
            ioc_type: Type of IOC (sha256, md5, domain, ipv4, ipv6)
            value: IOC value
            action: Action to take (detect, prevent, allow)
            severity: Severity level
            description: Description of the IOC
            platforms: Target platforms (windows, mac, linux)
            tags: Tags for organization
            expiration: Expiration date (ISO format)
        """
        start_time = time.time()

        try:
            token = await self._ensure_token()

            payload = {
                "indicators": [
                    {
                        "type": ioc_type.value,
                        "value": value,
                        "action": action.value,
                        "severity": severity.value,
                        "description": description,
                        "platforms": platforms or ["windows", "mac", "linux"],
                        "applied_globally": True,
                    }
                ]
            }

            if tags:
                payload["indicators"][0]["tags"] = tags
            if expiration:
                payload["indicators"][0]["expiration"] = expiration

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/iocs/entities/indicators/v1",
                    json=payload,
                    headers=self._get_headers(token),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status in (200, 201)
                    self._record_request(latency_ms, success)

                    if success:
                        logger.info(f"IOC created: {ioc_type.value}={value}")

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data=data,
                        latency_ms=latency_ms,
                        error=None if success else str(data.get("errors", data)),
                    )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def create_security_ioc(
        self,
        ioc_type: IOCType,
        value: str,
        cve_id: str | None = None,
        severity: str = "HIGH",
        description: str = "",
        source: str = "aura-security-platform",
    ) -> ConnectorResult:
        """
        Create a security-related IOC with standard formatting.

        Args:
            ioc_type: Type of IOC
            value: IOC value
            cve_id: Related CVE ID
            severity: CRITICAL, HIGH, MEDIUM, LOW
            description: Description
            source: Source of the IOC
        """
        severity_map = {
            "CRITICAL": DetectionSeverity.CRITICAL,
            "HIGH": DetectionSeverity.HIGH,
            "MEDIUM": DetectionSeverity.MEDIUM,
            "LOW": DetectionSeverity.LOW,
        }

        full_description = f"[{source}] {description}"
        if cve_id:
            full_description = f"[{cve_id}] {full_description}"

        tags = ["aura-generated", severity.lower()]
        if cve_id:
            tags.append(cve_id.lower())

        result: ConnectorResult = await self.create_ioc(
            ioc_type=ioc_type,
            value=value,
            action=IOCAction.DETECT if severity != "CRITICAL" else IOCAction.PREVENT,
            severity=severity_map.get(severity.upper(), DetectionSeverity.MEDIUM),
            description=full_description,
            tags=tags,
        )
        return result

    # =========================================================================
    # Threat Intelligence
    # =========================================================================

    @require_enterprise_mode
    async def search_threat_intel(
        self,
        indicator: str,
        indicator_type: IOCType | None = None,
    ) -> ConnectorResult:
        """
        Search threat intelligence for an indicator.

        Args:
            indicator: The indicator value to search
            indicator_type: Type of indicator (auto-detected if not provided)
        """
        start_time = time.time()

        try:
            token = await self._ensure_token()

            # Build search query
            params: dict[str, str | int] = {"q": indicator, "limit": 50}
            if indicator_type:
                params["type"] = indicator_type.value

            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.base_url}/intel/combined/indicators/v1",
                    params=params,
                    headers=self._get_headers(token),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        indicators = [
                            {
                                "id": i.get("id"),
                                "indicator": i.get("indicator"),
                                "type": i.get("type"),
                                "malicious_confidence": i.get("malicious_confidence"),
                                "labels": i.get("labels", []),
                                "actors": i.get("actors", []),
                                "malware_families": i.get("malware_families", []),
                                "kill_chains": i.get("kill_chains", []),
                                "last_updated": i.get("last_updated"),
                            }
                            for i in data.get("resources", [])
                        ]
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "indicators": indicators,
                                "count": len(indicators),
                                "query": indicator,
                            },
                            latency_ms=latency_ms,
                        )
                    else:
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=str(data.get("errors", data)),
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> bool:
        """Check if CrowdStrike connector is healthy."""
        try:
            await self._ensure_token()
            return True
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            return False
