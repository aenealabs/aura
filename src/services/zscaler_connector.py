"""
Project Aura - Zscaler Connector

Implements ADR-053: Enterprise Security Integrations

Zscaler REST API connector for:
- Zero Trust Internet Access (ZIA) - web security policies, threat logs, DLP
- Zero Trust Private Access (ZPA) - private application access policies

SECURITY: Only available in ENTERPRISE or HYBRID mode.

Usage:
    >>> from src.services.zscaler_connector import ZscalerConnector
    >>> zscaler = ZscalerConnector(
    ...     zia_api_key="your-key",
    ...     zia_username="user@company.com",
    ...     zia_password="password",
    ...     zia_cloud="zscaler.net"
    ... )
    >>> threats = await zscaler.get_threat_logs(hours=24)
"""

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
# Enums
# =============================================================================


class ZscalerCloud(Enum):
    """Zscaler cloud instances."""

    ZSCALER = "zscaler.net"
    ZSCALERONE = "zscalerone.net"
    ZSCALERTWO = "zscalertwo.net"
    ZSCALERTHREE = "zscalerthree.net"
    ZSCLOUD = "zscloud.net"
    ZSCALERBETA = "zscalerbeta.net"
    ZSCALERGOV = "zscalergov.net"  # GovCloud - FedRAMP High


class ZscalerThreatCategory(Enum):
    """Zscaler threat categories."""

    MALWARE = "malware"
    PHISHING = "phishing"
    BOTNET = "botnet"
    CRYPTOMINING = "cryptomining"
    ADWARE = "adware"
    WEBSPAM = "webspam"
    SUSPICIOUS = "suspicious"
    MALICIOUS_CONTENT = "malicious_content"


class ZscalerAction(Enum):
    """Zscaler action types."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    CAUTIONED = "cautioned"
    QUARANTINED = "quarantined"


class ZscalerDLPSeverity(Enum):
    """Zscaler DLP severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ZscalerThreatEvent:
    """Zscaler threat event details."""

    event_id: str
    timestamp: str
    user: str
    department: str | None = None
    url: str | None = None
    threat_category: ZscalerThreatCategory | None = None
    threat_name: str = ""
    action: ZscalerAction = ZscalerAction.BLOCKED
    policy_name: str | None = None
    source_ip: str | None = None
    destination_ip: str | None = None
    hostname: str | None = None
    file_name: str | None = None
    file_hash: str | None = None
    risk_score: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "user": self.user,
            "department": self.department,
            "url": self.url,
            "threat_category": (
                self.threat_category.value if self.threat_category else None
            ),
            "threat_name": self.threat_name,
            "action": self.action.value,
            "policy_name": self.policy_name,
            "source_ip": self.source_ip,
            "destination_ip": self.destination_ip,
            "hostname": self.hostname,
            "file_name": self.file_name,
            "file_hash": self.file_hash,
            "risk_score": self.risk_score,
        }


@dataclass
class ZscalerDLPIncident:
    """Zscaler DLP incident details."""

    incident_id: str
    timestamp: str
    user: str
    dlp_engine: str
    dlp_dictionary: str
    severity: ZscalerDLPSeverity
    action: ZscalerAction
    matched_data: str | None = None
    destination: str | None = None
    channel: str | None = None
    file_name: str | None = None
    department: str | None = None
    record_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "incident_id": self.incident_id,
            "timestamp": self.timestamp,
            "user": self.user,
            "dlp_engine": self.dlp_engine,
            "dlp_dictionary": self.dlp_dictionary,
            "severity": self.severity.value,
            "action": self.action.value,
            "matched_data": self.matched_data,
            "destination": self.destination,
            "channel": self.channel,
            "file_name": self.file_name,
            "department": self.department,
            "record_count": self.record_count,
        }


@dataclass
class ZscalerURLFilteringRule:
    """Zscaler URL filtering rule."""

    rule_id: str
    name: str
    order: int
    state: str  # ENABLED, DISABLED
    action: str  # ALLOW, BLOCK, CAUTION
    url_categories: list[str] = field(default_factory=list)
    departments: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ZscalerUserRisk:
    """Zscaler user risk score details."""

    username: str
    email: str
    risk_score: int  # 0-100
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    last_assessment: str
    risk_factors: list[str] = field(default_factory=list)
    department: str | None = None
    manager: str | None = None
    total_threats_blocked: int = 0
    dlp_incidents: int = 0


@dataclass
class ZscalerZPAApplication:
    """Zscaler ZPA application details."""

    app_id: str
    name: str
    domain_names: list[str]
    enabled: bool = True
    double_encrypt: bool = False
    bypass_type: str = "NEVER"
    health_check_type: str = "DEFAULT"
    segment_group_id: str | None = None
    server_groups: list[str] = field(default_factory=list)


# =============================================================================
# Zscaler Connector
# =============================================================================


class ZscalerConnector(ExternalToolConnector):
    """
    Zscaler connector for Zero Trust security integration.

    Supports:
    - ZIA threat logs and web security policies
    - ZIA DLP incidents and data classification
    - ZIA URL filtering rules
    - ZIA user risk scores
    - ZPA application inventory
    - ZPA access policies
    """

    # Rate limiting configuration
    MAX_RETRIES = 3
    RATE_LIMIT_REQUESTS_PER_MINUTE = 100
    RATE_LIMIT_BURST = 200

    def __init__(
        self,
        zia_api_key: str | None = None,
        zia_username: str | None = None,
        zia_password: str | None = None,
        zia_cloud: ZscalerCloud | str = ZscalerCloud.ZSCALER,
        zpa_client_id: str | None = None,
        zpa_client_secret: str | None = None,
        zpa_customer_id: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Initialize Zscaler connector.

        Args:
            zia_api_key: ZIA API key
            zia_username: ZIA username (email)
            zia_password: ZIA password
            zia_cloud: ZIA cloud instance (auto-detects GovCloud)
            zpa_client_id: ZPA OAuth client ID
            zpa_client_secret: ZPA OAuth client secret
            zpa_customer_id: ZPA customer ID
            timeout_seconds: Request timeout
            max_retries: Maximum retry attempts
        """
        super().__init__("zscaler", timeout_seconds)

        # ZIA configuration
        self.zia_api_key = zia_api_key
        self.zia_username = zia_username
        self.zia_password = zia_password
        self.max_retries = max_retries

        # Auto-detect GovCloud region
        aws_region = os.environ.get("AWS_REGION", "")
        if aws_region.startswith("us-gov-"):
            zia_cloud = ZscalerCloud.ZSCALERGOV
            logger.info("GovCloud region detected, using zscalergov.net")

        if isinstance(zia_cloud, ZscalerCloud):
            self._zia_cloud = zia_cloud
            self.zia_base_url = f"https://zsapi.{zia_cloud.value}"
        else:
            self._zia_cloud = None
            self.zia_base_url = f"https://zsapi.{zia_cloud}"

        # ZPA configuration
        self.zpa_client_id = zpa_client_id
        self.zpa_client_secret = zpa_client_secret
        self.zpa_customer_id = zpa_customer_id
        self.zpa_base_url = "https://config.private.zscaler.com"

        # Session tokens
        self._zia_jsessionid: str | None = None
        self._zia_session_expiry: float = 0
        self._zpa_token: str | None = None
        self._zpa_token_expiry: float = 0

        # Rate limiting state
        self._request_timestamps: list[float] = []

    @property
    def zia_cloud(self) -> ZscalerCloud | None:
        """Get the ZIA cloud instance."""
        return self._zia_cloud

    # =========================================================================
    # Authentication
    # =========================================================================

    async def _authenticate_zia(self) -> bool:
        """
        Authenticate to ZIA API using obfuscated API key.

        Returns:
            True if authentication succeeded
        """
        if not all([self.zia_api_key, self.zia_username, self.zia_password]):
            logger.warning("ZIA credentials not fully configured")
            return False

        # Check if existing session is still valid
        if self._zia_jsessionid and time.time() < self._zia_session_expiry - 60:
            return True

        # Generate obfuscated API key per Zscaler documentation
        timestamp = str(int(time.time() * 1000))
        api_key_n = self._obfuscate_api_key(self.zia_api_key or "", timestamp)

        payload = {
            "apiKey": api_key_n,
            "username": self.zia_username,
            "password": self.zia_password,
            "timestamp": timestamp,
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.zia_base_url}/api/v1/authenticatedSession",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status == 200:
                        # Extract JSESSIONID from cookies
                        cookies = response.cookies
                        jsessionid = cookies.get("JSESSIONID")
                        if jsessionid:
                            self._zia_jsessionid = jsessionid.value
                            # ZIA sessions typically last 30 minutes
                            self._zia_session_expiry = time.time() + 1800
                            self._status = ConnectorStatus.CONNECTED
                            logger.info("ZIA authentication successful")
                            return True
                        else:
                            self._status = ConnectorStatus.AUTH_FAILED
                            self._last_error = "No JSESSIONID in response"
                            return False
                    elif response.status == 401:
                        self._status = ConnectorStatus.AUTH_FAILED
                        self._last_error = "Invalid credentials"
                        return False
                    else:
                        body = await response.text()
                        self._status = ConnectorStatus.ERROR
                        self._last_error = f"Auth failed: {response.status} - {body}"
                        return False
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.exception(f"ZIA authentication error: {e}")
            return False

    def _obfuscate_api_key(self, api_key: str, timestamp: str) -> str:
        """
        Obfuscate API key per Zscaler documentation.

        The obfuscation algorithm:
        1. Append timestamp to API key
        2. Get MD5 hash
        3. Use first 6 chars of hex digest to generate positions
        4. Build obfuscated key from these positions
        """
        seed = api_key + timestamp
        # MD5 is used for obfuscation, not security - required by Zscaler API
        md5_hash = hashlib.md5(
            seed.encode(), usedforsecurity=False
        ).hexdigest()  # noqa: S324

        # Use MD5 hex to generate positions
        n = len(timestamp)
        obfuscated = []

        for i in range(n):
            # Get position from MD5 hex
            pos = int(md5_hash[i], 16) % n
            obfuscated.append(api_key[pos])

        return "".join(obfuscated)

    async def _authenticate_zpa(self) -> bool:
        """
        Authenticate to ZPA API using OAuth2 client credentials.

        Returns:
            True if authentication succeeded
        """
        if not all([self.zpa_client_id, self.zpa_client_secret, self.zpa_customer_id]):
            logger.warning("ZPA credentials not fully configured")
            return False

        # Check if existing token is still valid
        if self._zpa_token and time.time() < self._zpa_token_expiry - 60:
            return True

        payload = {
            "client_id": self.zpa_client_id,
            "client_secret": self.zpa_client_secret,
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.zpa_base_url}/signin",
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._zpa_token = data.get("access_token")
                        expires_in = data.get("expires_in", 3600)
                        self._zpa_token_expiry = time.time() + expires_in
                        logger.info("ZPA authentication successful")
                        return True
                    else:
                        self._status = ConnectorStatus.AUTH_FAILED
                        self._last_error = f"ZPA auth failed: {response.status}"
                        return False
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.exception(f"ZPA authentication error: {e}")
            return False

    def _get_zia_headers(self) -> dict[str, str]:
        """Get ZIA request headers with session cookie."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cookie": f"JSESSIONID={self._zia_jsessionid}",
        }

    def _get_zpa_headers(self) -> dict[str, str]:
        """Get ZPA request headers with bearer token."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self._zpa_token}",
        }

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting."""
        now = time.time()

        # Clean old timestamps (older than 1 minute)
        self._request_timestamps = [
            ts for ts in self._request_timestamps if now - ts < 60
        ]

        # Check if we're at the limit
        if len(self._request_timestamps) >= self.RATE_LIMIT_REQUESTS_PER_MINUTE:
            # Wait until the oldest request is outside the window
            oldest = self._request_timestamps[0]
            wait_time = 60 - (now - oldest) + 0.1
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
                self._status = ConnectorStatus.RATE_LIMITED
                await asyncio.sleep(wait_time)

        self._request_timestamps.append(time.time())

    # =========================================================================
    # HTTP Request Helper
    # =========================================================================

    async def _make_zia_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        """
        Make an authenticated ZIA API request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON request body

        Returns:
            ConnectorResult with response data
        """
        start_time = time.time()

        # Ensure authenticated
        if not await self._authenticate_zia():
            return ConnectorResult(
                success=False,
                error="ZIA authentication failed",
                latency_ms=(time.time() - start_time) * 1000,
            )

        await self._check_rate_limit()

        url = f"{self.zia_base_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.request(
                        method,
                        url,
                        params=params,
                        json=json_data,
                        headers=self._get_zia_headers(),
                    ) as response:
                        latency_ms = (time.time() - start_time) * 1000
                        self._record_request(latency_ms, response.status < 400)

                        if response.status == 429:
                            # Rate limited
                            retry_after = int(response.headers.get("Retry-After", 60))
                            self._status = ConnectorStatus.RATE_LIMITED
                            logger.warning(f"ZIA rate limited, waiting {retry_after}s")
                            await asyncio.sleep(retry_after)
                            continue

                        if response.status == 401:
                            # Session expired, re-authenticate
                            self._zia_jsessionid = None
                            self._zia_session_expiry = 0
                            if not await self._authenticate_zia():
                                return ConnectorResult(
                                    success=False,
                                    error="Re-authentication failed",
                                    status_code=401,
                                    latency_ms=latency_ms,
                                )
                            continue

                        if response.status >= 500:
                            # Server error, retry with backoff
                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(2**attempt)
                                continue

                        data = await response.json()
                        success = response.status < 400

                        if success:
                            self._status = ConnectorStatus.CONNECTED

                        return ConnectorResult(
                            success=success,
                            status_code=response.status,
                            data=data if success else {},
                            error=data.get("message") if not success else None,
                            latency_ms=latency_ms,
                        )

            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                return ConnectorResult(
                    success=False,
                    error="Request timeout",
                    latency_ms=(time.time() - start_time) * 1000,
                )
            except Exception as e:
                self._status = ConnectorStatus.ERROR
                self._last_error = str(e)
                logger.exception(f"ZIA request error: {e}")
                return ConnectorResult(
                    success=False,
                    error=str(e),
                    latency_ms=(time.time() - start_time) * 1000,
                )

        return ConnectorResult(
            success=False,
            error="Max retries exceeded",
            latency_ms=(time.time() - start_time) * 1000,
        )

    async def _make_zpa_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        """
        Make an authenticated ZPA API request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON request body

        Returns:
            ConnectorResult with response data
        """
        start_time = time.time()

        # Ensure authenticated
        if not await self._authenticate_zpa():
            return ConnectorResult(
                success=False,
                error="ZPA authentication failed",
                latency_ms=(time.time() - start_time) * 1000,
            )

        url = f"{self.zpa_base_url}/mgmtconfig/v1/admin/customers/{self.zpa_customer_id}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.request(
                        method,
                        url,
                        params=params,
                        json=json_data,
                        headers=self._get_zpa_headers(),
                    ) as response:
                        latency_ms = (time.time() - start_time) * 1000
                        self._record_request(latency_ms, response.status < 400)

                        if response.status == 401:
                            # Token expired
                            self._zpa_token = None
                            self._zpa_token_expiry = 0
                            if not await self._authenticate_zpa():
                                return ConnectorResult(
                                    success=False,
                                    error="Re-authentication failed",
                                    status_code=401,
                                    latency_ms=latency_ms,
                                )
                            continue

                        if response.status >= 500:
                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(2**attempt)
                                continue

                        data = await response.json()
                        success = response.status < 400

                        return ConnectorResult(
                            success=success,
                            status_code=response.status,
                            data=data if success else {},
                            error=data.get("message") if not success else None,
                            latency_ms=latency_ms,
                        )

            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                return ConnectorResult(
                    success=False,
                    error="Request timeout",
                    latency_ms=(time.time() - start_time) * 1000,
                )
            except Exception as e:
                self._status = ConnectorStatus.ERROR
                self._last_error = str(e)
                logger.exception(f"ZPA request error: {e}")
                return ConnectorResult(
                    success=False,
                    error=str(e),
                    latency_ms=(time.time() - start_time) * 1000,
                )

        return ConnectorResult(
            success=False,
            error="Max retries exceeded",
            latency_ms=(time.time() - start_time) * 1000,
        )

    # =========================================================================
    # ZIA Threat Intelligence
    # =========================================================================

    @require_enterprise_mode
    async def get_threat_logs(
        self,
        hours: int = 24,
        user: str | None = None,
        threat_category: ZscalerThreatCategory | None = None,
        action: ZscalerAction | None = None,
        limit: int = 1000,
    ) -> ConnectorResult:
        """
        Get threat logs from ZIA.

        Args:
            hours: Hours of logs to retrieve (max 720 = 30 days)
            user: Filter by username/email
            threat_category: Filter by threat category
            action: Filter by action taken
            limit: Maximum results to return

        Returns:
            ConnectorResult with threat events
        """
        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = datetime.fromtimestamp(
            end_time.timestamp() - (hours * 3600), timezone.utc
        )

        params: dict[str, Any] = {
            "startTime": int(start_time.timestamp() * 1000),
            "endTime": int(end_time.timestamp() * 1000),
            "page": 1,
            "pageSize": min(limit, 1000),
        }

        if user:
            params["user"] = user
        if threat_category:
            params["threatCategory"] = threat_category.value
        if action:
            params["action"] = action.value

        result = await self._make_zia_request(
            "GET", "/api/v1/webApplicationRules", params=params
        )

        if result.success and "logs" in result.data:
            # Parse into typed data classes
            events = []
            for log in result.data.get("logs", []):
                try:
                    event = ZscalerThreatEvent(
                        event_id=str(log.get("id", "")),
                        timestamp=log.get("datetime", ""),
                        user=log.get("user", ""),
                        department=log.get("department"),
                        url=log.get("url"),
                        threat_category=(
                            ZscalerThreatCategory(log["threatCategory"])
                            if log.get("threatCategory")
                            else None
                        ),
                        threat_name=log.get("threatName", ""),
                        action=ZscalerAction(log.get("action", "blocked")),
                        policy_name=log.get("policyName"),
                        source_ip=log.get("sourceIP"),
                        destination_ip=log.get("destinationIP"),
                        hostname=log.get("hostname"),
                        file_name=log.get("fileName"),
                        file_hash=log.get("fileHash"),
                        risk_score=log.get("riskScore", 0),
                    )
                    events.append(event.to_dict())
                except (ValueError, KeyError) as e:
                    logger.warning(f"Failed to parse threat event: {e}")
                    continue

            result.data = {"events": events, "total": len(events)}

        return result

    @require_enterprise_mode
    async def get_dlp_incidents(
        self,
        hours: int = 24,
        severity: ZscalerDLPSeverity | None = None,
        user: str | None = None,
        limit: int = 500,
    ) -> ConnectorResult:
        """
        Get DLP incidents from ZIA.

        Args:
            hours: Hours of incidents to retrieve
            severity: Filter by severity
            user: Filter by username
            limit: Maximum results

        Returns:
            ConnectorResult with DLP incidents
        """
        end_time = datetime.now(timezone.utc)
        start_time = datetime.fromtimestamp(
            end_time.timestamp() - (hours * 3600), timezone.utc
        )

        params: dict[str, Any] = {
            "startTime": int(start_time.timestamp() * 1000),
            "endTime": int(end_time.timestamp() * 1000),
            "page": 1,
            "pageSize": min(limit, 500),
        }

        if severity:
            params["severity"] = severity.value
        if user:
            params["user"] = user

        result = await self._make_zia_request(
            "GET", "/api/v1/dlpIncidents", params=params
        )

        if result.success and "incidents" in result.data:
            incidents = []
            for inc in result.data.get("incidents", []):
                try:
                    incident = ZscalerDLPIncident(
                        incident_id=str(inc.get("id", "")),
                        timestamp=inc.get("datetime", ""),
                        user=inc.get("user", ""),
                        dlp_engine=inc.get("dlpEngine", ""),
                        dlp_dictionary=inc.get("dlpDictionary", ""),
                        severity=ZscalerDLPSeverity(inc.get("severity", "medium")),
                        action=ZscalerAction(inc.get("action", "blocked")),
                        matched_data=inc.get("matchedData"),
                        destination=inc.get("destination"),
                        channel=inc.get("channel"),
                        file_name=inc.get("fileName"),
                        department=inc.get("department"),
                        record_count=inc.get("recordCount", 0),
                    )
                    incidents.append(incident.to_dict())
                except (ValueError, KeyError) as e:
                    logger.warning(f"Failed to parse DLP incident: {e}")
                    continue

            result.data = {"incidents": incidents, "total": len(incidents)}

        return result

    @require_enterprise_mode
    async def get_url_filtering_rules(self) -> ConnectorResult:
        """
        Get URL filtering rules from ZIA.

        Returns:
            ConnectorResult with URL filtering rules
        """
        result = await self._make_zia_request("GET", "/api/v1/urlFilteringRules")

        if result.success:
            rules = []
            for rule in result.data.get(
                "rules", result.data if isinstance(result.data, list) else []
            ):
                rules.append(
                    {
                        "rule_id": str(rule.get("id", "")),
                        "name": rule.get("name", ""),
                        "order": rule.get("order", 0),
                        "state": rule.get("state", "ENABLED"),
                        "action": rule.get("action", "BLOCK"),
                        "url_categories": rule.get("urlCategories", []),
                        "departments": rule.get("departments", []),
                        "groups": rule.get("groups", []),
                        "locations": rule.get("locations", []),
                        "description": rule.get("description", ""),
                    }
                )
            result.data = {"rules": rules, "total": len(rules)}

        return result

    @require_enterprise_mode
    async def get_user_risk_score(self, user: str) -> ConnectorResult:
        """
        Get user risk score from ZIA.

        Args:
            user: Username or email

        Returns:
            ConnectorResult with user risk details
        """
        result = await self._make_zia_request("GET", f"/api/v1/userRiskScoring/{user}")

        if result.success:
            data = result.data
            risk_data = ZscalerUserRisk(
                username=data.get("username", user),
                email=data.get("email", user),
                risk_score=data.get("riskScore", 0),
                risk_level=data.get("riskLevel", "LOW"),
                last_assessment=data.get("lastAssessment", ""),
                risk_factors=data.get("riskFactors", []),
                department=data.get("department"),
                manager=data.get("manager"),
                total_threats_blocked=data.get("totalThreatsBlocked", 0),
                dlp_incidents=data.get("dlpIncidents", 0),
            )
            result.data = {
                "username": risk_data.username,
                "email": risk_data.email,
                "risk_score": risk_data.risk_score,
                "risk_level": risk_data.risk_level,
                "last_assessment": risk_data.last_assessment,
                "risk_factors": risk_data.risk_factors,
                "department": risk_data.department,
                "manager": risk_data.manager,
                "total_threats_blocked": risk_data.total_threats_blocked,
                "dlp_incidents": risk_data.dlp_incidents,
            }

        return result

    @require_enterprise_mode
    async def get_security_policy_summary(self) -> ConnectorResult:
        """
        Get a summary of security policies from ZIA.

        Returns:
            ConnectorResult with policy summary
        """
        # Fetch multiple policy types in parallel
        results = await asyncio.gather(
            self._make_zia_request("GET", "/api/v1/security"),
            self._make_zia_request("GET", "/api/v1/advancedThreatProtection"),
            self._make_zia_request("GET", "/api/v1/malwareProtection"),
            return_exceptions=True,
        )

        summary = {
            "security_policies": {},
            "atp_enabled": False,
            "malware_protection_enabled": False,
            "errors": [],
        }

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                summary["errors"].append(str(result))
            elif isinstance(result, ConnectorResult) and result.success:
                if i == 0:
                    summary["security_policies"] = result.data
                elif i == 1:
                    summary["atp_enabled"] = result.data.get("enabled", False)
                elif i == 2:
                    summary["malware_protection_enabled"] = result.data.get(
                        "enabled", False
                    )

        return ConnectorResult(
            success=len(summary["errors"]) == 0,
            data=summary,
            error="; ".join(summary["errors"]) if summary["errors"] else None,
        )

    # =========================================================================
    # ZPA Operations
    # =========================================================================

    @require_enterprise_mode
    async def get_zpa_applications(self) -> ConnectorResult:
        """
        Get private applications from ZPA.

        Returns:
            ConnectorResult with application list
        """
        result = await self._make_zpa_request("GET", "/application")

        if result.success:
            apps = []
            for app in result.data.get("list", []):
                apps.append(
                    {
                        "app_id": app.get("id", ""),
                        "name": app.get("name", ""),
                        "domain_names": app.get("domainNames", []),
                        "enabled": app.get("enabled", True),
                        "double_encrypt": app.get("doubleEncrypt", False),
                        "bypass_type": app.get("bypassType", "NEVER"),
                        "segment_group_id": app.get("segmentGroupId"),
                        "server_groups": [
                            sg.get("name", "") for sg in app.get("serverGroups", [])
                        ],
                    }
                )
            result.data = {"applications": apps, "total": len(apps)}

        return result

    @require_enterprise_mode
    async def get_zpa_access_policies(self) -> ConnectorResult:
        """
        Get access policies from ZPA.

        Returns:
            ConnectorResult with access policies
        """
        result = await self._make_zpa_request("GET", "/policySet/rules")

        if result.success:
            policies = []
            for policy in result.data.get("list", []):
                policies.append(
                    {
                        "policy_id": policy.get("id", ""),
                        "name": policy.get("name", ""),
                        "description": policy.get("description", ""),
                        "action": policy.get("action", ""),
                        "rule_order": policy.get("ruleOrder", 0),
                        "conditions": policy.get("conditions", []),
                        "app_connector_groups": policy.get("appConnectorGroups", []),
                        "app_server_groups": policy.get("appServerGroups", []),
                    }
                )
            result.data = {"policies": policies, "total": len(policies)}

        return result

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> bool:
        """
        Check if Zscaler connector is healthy.

        Tests ZIA and/or ZPA connectivity based on configured credentials.

        Returns:
            True if at least one service is connected
        """
        zia_healthy = False
        zpa_healthy = False

        # Check ZIA
        if all([self.zia_api_key, self.zia_username, self.zia_password]):
            zia_healthy = await self._authenticate_zia()

        # Check ZPA
        if all([self.zpa_client_id, self.zpa_client_secret, self.zpa_customer_id]):
            zpa_healthy = await self._authenticate_zpa()

        if zia_healthy or zpa_healthy:
            self._status = ConnectorStatus.CONNECTED
            return True

        if not any(
            [
                self.zia_api_key,
                self.zia_username,
                self.zpa_client_id,
            ]
        ):
            self._status = ConnectorStatus.DISCONNECTED
            self._last_error = "No credentials configured"
        else:
            self._status = ConnectorStatus.AUTH_FAILED

        return False

    async def logout_zia(self) -> ConnectorResult:
        """
        Logout from ZIA session.

        Returns:
            ConnectorResult indicating success/failure
        """
        if not self._zia_jsessionid:
            return ConnectorResult(success=True, data={"message": "No active session"})

        result = await self._make_zia_request("DELETE", "/api/v1/authenticatedSession")

        if result.success:
            self._zia_jsessionid = None
            self._zia_session_expiry = 0
            self._status = ConnectorStatus.DISCONNECTED

        return result
