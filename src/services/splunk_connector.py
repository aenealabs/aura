"""
Project Aura - Splunk Connector

Implements ADR-028 Phase 8: Enterprise Connector Expansion

Splunk REST API connector for:
- Search and reporting
- Security event ingestion via HEC (HTTP Event Collector)
- Index management
- Alert management

SECURITY: Only available in ENTERPRISE or HYBRID mode.

Usage:
    >>> from src.services.splunk_connector import SplunkConnector
    >>> splunk = SplunkConnector(
    ...     base_url="https://splunk.company.com:8089",
    ...     token="your-api-token"
    ... )
    >>> results = await splunk.search("index=security sourcetype=syslog | head 100")
"""

import logging
import time
import urllib.parse
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
# Enums and Data Classes
# =============================================================================


class SplunkSearchMode(Enum):
    """Splunk search modes."""

    NORMAL = "normal"
    REALTIME = "realtime"


class SplunkOutputMode(Enum):
    """Splunk output modes."""

    JSON = "json"
    CSV = "csv"
    XML = "xml"
    RAW = "raw"


class SplunkSeverity(Enum):
    """Splunk event severity levels."""

    UNKNOWN = "unknown"
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SplunkEvent:
    """Splunk event structure for HEC ingestion."""

    event: dict[str, Any] | str
    time: float | None = None  # Epoch timestamp
    host: str | None = None
    source: str | None = None
    sourcetype: str | None = None
    index: str | None = None
    fields: dict[str, Any] | None = None


@dataclass
class SplunkSearchJob:
    """Splunk search job details."""

    sid: str  # Search ID
    status: str
    is_done: bool = False
    is_failed: bool = False
    result_count: int = 0
    scan_count: int = 0
    event_count: int = 0
    run_duration: float = 0.0
    messages: list[dict[str, str]] = field(default_factory=list)


@dataclass
class SplunkAlert:
    """Splunk alert structure."""

    name: str
    search: str
    description: str = ""
    severity: SplunkSeverity = SplunkSeverity.MEDIUM
    cron_schedule: str = "*/5 * * * *"  # Every 5 minutes
    is_scheduled: bool = True
    alert_type: str = "number of events"
    alert_comparator: str = "greater than"
    alert_threshold: str = "0"
    actions: list[str] | None = None


# =============================================================================
# Splunk Connector
# =============================================================================


class SplunkConnector(ExternalToolConnector):
    """
    Splunk connector for SIEM integration.

    Supports:
    - Search and reporting via REST API
    - Event ingestion via HTTP Event Collector (HEC)
    - Saved search management
    - Alert management
    """

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        hec_url: str | None = None,
        hec_token: str | None = None,
        default_index: str = "main",
        verify_ssl: bool = True,
        timeout_seconds: float = 60.0,
    ):
        """
        Initialize Splunk connector.

        Args:
            base_url: Splunk REST API URL (e.g., https://splunk:8089)
            token: Splunk auth token (for token auth)
            username: Splunk username (for basic auth)
            password: Splunk password (for basic auth)
            hec_url: HTTP Event Collector URL (e.g., https://splunk:8088)
            hec_token: HEC token for event ingestion
            default_index: Default index for searches
            verify_ssl: Verify SSL certificates
            timeout_seconds: Request timeout
        """
        super().__init__("splunk", timeout_seconds)

        self.base_url = base_url.rstrip("/")
        self.hec_url = hec_url.rstrip("/") if hec_url else None
        self.hec_token = hec_token
        self.default_index = default_index
        self.verify_ssl = verify_ssl

        # Set up authentication
        self._token = token
        self._username = username
        self._password = password

        if not token and not (username and password):
            logger.warning(
                "SplunkConnector initialized without token or username/password. "
                "Configure authentication before making API calls."
            )

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        elif self._username and self._password:
            import base64

            credentials = f"{self._username}:{self._password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        return headers

    def _get_hec_headers(self) -> dict[str, str]:
        """Get HEC authentication headers."""
        return {
            "Authorization": f"Splunk {self.hec_token}",
            "Content-Type": "application/json",
        }

    # =========================================================================
    # Search Operations
    # =========================================================================

    @require_enterprise_mode
    async def search(
        self,
        query: str,
        earliest_time: str = "-24h",
        latest_time: str = "now",
        max_results: int = 1000,
        output_mode: SplunkOutputMode = SplunkOutputMode.JSON,
    ) -> ConnectorResult:
        """
        Execute a Splunk search and wait for results.

        Args:
            query: SPL search query
            earliest_time: Search start time (e.g., "-24h", "2024-01-01T00:00:00")
            latest_time: Search end time (e.g., "now", "2024-01-02T00:00:00")
            max_results: Maximum results to return
            output_mode: Output format

        Returns:
            ConnectorResult with search results
        """
        start_time = time.time()

        # Create search job
        job_result = await self._create_search_job(query, earliest_time, latest_time)
        if not job_result.success:
            return job_result

        sid = job_result.data.get("sid")
        if not sid or not isinstance(sid, str):
            return ConnectorResult(
                success=False,
                error="No valid search ID returned",
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Wait for job completion
        job = await self._wait_for_job(sid, timeout_seconds=120)
        if job.is_failed:
            return ConnectorResult(
                success=False,
                error=f"Search job failed: {job.messages}",
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Get results
        results = await self._get_search_results(sid, max_results, output_mode)
        results.latency_ms = (time.time() - start_time) * 1000

        return results

    async def _create_search_job(
        self,
        query: str,
        earliest_time: str,
        latest_time: str,
    ) -> ConnectorResult:
        """Create a search job."""
        start_time = time.time()

        # Ensure query starts with "search" if not a generating command
        if not query.strip().startswith("|") and not query.strip().lower().startswith(
            "search"
        ):
            query = f"search {query}"

        data = {
            "search": query,
            "earliest_time": earliest_time,
            "latest_time": latest_time,
            "output_mode": "json",
        }

        # SSL context: False to disable verification, True/omitted for verification
        ssl_verify: bool = self.verify_ssl

        try:
            async with aiohttp.ClientSession(
                timeout=self.timeout,
                connector=aiohttp.TCPConnector(ssl=ssl_verify),
            ) as session:
                async with session.post(
                    f"{self.base_url}/services/search/jobs",
                    data=urllib.parse.urlencode(data),
                    headers=self._get_auth_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    response_data = await response.json()

                    if response.status in (200, 201):
                        self._status = ConnectorStatus.CONNECTED
                        self._record_request(latency_ms, True)
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={"sid": response_data.get("sid")},
                            request_id=response_data.get("sid"),
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        error_msg = response_data.get("messages", [{}])
                        if error_msg and isinstance(error_msg, list):
                            error_msg = error_msg[0].get("text", str(response_data))
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=str(error_msg),
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

    async def _wait_for_job(
        self, sid: str, timeout_seconds: float = 120, poll_interval: float = 1.0
    ) -> SplunkSearchJob:
        """Wait for a search job to complete."""
        deadline = time.time() + timeout_seconds
        ssl_context: bool = self.verify_ssl

        while time.time() < deadline:
            try:
                async with aiohttp.ClientSession(
                    timeout=self.timeout,
                    connector=aiohttp.TCPConnector(ssl=ssl_context),
                ) as session:
                    async with session.get(
                        f"{self.base_url}/services/search/jobs/{sid}",
                        params={"output_mode": "json"},
                        headers=self._get_auth_headers(),
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            entry = data.get("entry", [{}])[0]
                            content = entry.get("content", {})

                            job = SplunkSearchJob(
                                sid=sid,
                                status=content.get("dispatchState", "UNKNOWN"),
                                is_done=content.get("isDone", False),
                                is_failed=content.get("isFailed", False),
                                result_count=content.get("resultCount", 0),
                                scan_count=content.get("scanCount", 0),
                                event_count=content.get("eventCount", 0),
                                run_duration=content.get("runDuration", 0),
                                messages=content.get("messages", []),
                            )

                            if job.is_done or job.is_failed:
                                return job

            except Exception as e:
                logger.warning(f"Error checking job status: {e}")

            await asyncio.sleep(poll_interval)

        # Timeout
        return SplunkSearchJob(
            sid=sid,
            status="TIMEOUT",
            is_failed=True,
            messages=[{"type": "ERROR", "text": "Job timed out"}],
        )

    async def _get_search_results(
        self,
        sid: str,
        max_results: int = 1000,
        output_mode: SplunkOutputMode = SplunkOutputMode.JSON,
    ) -> ConnectorResult:
        """Get results from a completed search job."""
        start_time = time.time()
        ssl_context: bool = self.verify_ssl

        params = {
            "output_mode": output_mode.value,
            "count": max_results,
        }

        try:
            async with aiohttp.ClientSession(
                timeout=self.timeout,
                connector=aiohttp.TCPConnector(ssl=ssl_context),
            ) as session:
                async with session.get(
                    f"{self.base_url}/services/search/jobs/{sid}/results",
                    params=params,
                    headers=self._get_auth_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000

                    if response.status == 200:
                        if output_mode == SplunkOutputMode.JSON:
                            data = await response.json()
                            results = data.get("results", [])
                        else:
                            results = await response.text()

                        self._record_request(latency_ms, True)
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "results": results,
                                "count": (
                                    len(results) if isinstance(results, list) else None
                                ),
                            },
                            request_id=sid,
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=f"Failed to get results: HTTP {response.status}",
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
    async def search_security_events(
        self,
        event_type: str | None = None,
        severity: SplunkSeverity | None = None,
        source_ip: str | None = None,
        dest_ip: str | None = None,
        user: str | None = None,
        earliest_time: str = "-24h",
        max_results: int = 1000,
    ) -> ConnectorResult:
        """
        Search for security events with common filters.

        Args:
            event_type: Event type filter (e.g., "authentication", "malware")
            severity: Severity filter
            source_ip: Source IP filter
            dest_ip: Destination IP filter
            user: Username filter
            earliest_time: Search start time
            max_results: Maximum results
        """
        query_parts = ["index=security"]

        if event_type:
            query_parts.append(f'eventtype="{event_type}"')
        if severity:
            query_parts.append(f'severity="{severity.value}"')
        if source_ip:
            query_parts.append(f'src_ip="{source_ip}"')
        if dest_ip:
            query_parts.append(f'dest_ip="{dest_ip}"')
        if user:
            query_parts.append(f'user="{user}"')

        query = " ".join(query_parts)
        result: ConnectorResult = await self.search(
            query, earliest_time=earliest_time, max_results=max_results
        )
        return result

    # =========================================================================
    # Event Ingestion (HEC)
    # =========================================================================

    @require_enterprise_mode
    async def send_event(
        self,
        event: dict[str, Any] | str,
        host: str | None = None,
        source: str = "aura-security-platform",
        sourcetype: str = "_json",
        index: str | None = None,
        timestamp: float | None = None,
        fields: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        """
        Send an event to Splunk via HEC.

        Args:
            event: Event data (dict or string)
            host: Event host
            source: Event source
            sourcetype: Event sourcetype
            index: Target index
            timestamp: Event timestamp (epoch)
            fields: Additional indexed fields
        """
        if not self.hec_url or not self.hec_token:
            return ConnectorResult(
                success=False,
                error="HEC URL and token must be configured for event ingestion",
            )

        start_time = time.time()

        payload: dict[str, Any] = {
            "event": event,
            "source": source,
            "sourcetype": sourcetype,
            "index": index or self.default_index,
        }

        if host:
            payload["host"] = host
        if timestamp:
            payload["time"] = timestamp
        if fields:
            payload["fields"] = fields

        # SSL context: False to disable verification, True/omitted for verification
        ssl_verify: bool = self.verify_ssl

        try:
            async with aiohttp.ClientSession(
                timeout=self.timeout,
                connector=aiohttp.TCPConnector(ssl=ssl_verify),
            ) as session:
                async with session.post(
                    f"{self.hec_url}/services/collector/event",
                    json=payload,
                    headers=self._get_hec_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200 and data.get("code") == 0
                    self._record_request(latency_ms, success)

                    if success:
                        logger.debug(f"Splunk event sent: {source}")
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data=data,
                            latency_ms=latency_ms,
                        )
                    else:
                        error = data.get("text", str(data))
                        self._last_error = error
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error,
                            data=data,
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
    async def send_security_event(
        self,
        event_type: str,
        severity: SplunkSeverity,
        description: str,
        cve_id: str | None = None,
        source_ip: str | None = None,
        dest_ip: str | None = None,
        user: str | None = None,
        affected_asset: str | None = None,
        action_taken: str | None = None,
        additional_data: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        """
        Send a structured security event to Splunk.

        Args:
            event_type: Type of security event
            severity: Event severity
            description: Event description
            cve_id: CVE identifier if applicable
            source_ip: Source IP address
            dest_ip: Destination IP address
            user: Associated username
            affected_asset: Affected asset/file
            action_taken: Action taken in response
            additional_data: Additional event data
        """
        event = {
            "event_type": event_type,
            "severity": severity.value,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_system": "aura-security-platform",
        }

        if cve_id:
            event["cve_id"] = cve_id
        if source_ip:
            event["src_ip"] = source_ip
        if dest_ip:
            event["dest_ip"] = dest_ip
        if user:
            event["user"] = user
        if affected_asset:
            event["affected_asset"] = affected_asset
        if action_taken:
            event["action_taken"] = action_taken
        if additional_data:
            event.update(additional_data)

        result: ConnectorResult = await self.send_event(
            event=event,
            source="aura-security-platform",
            sourcetype="aura:security:event",
            index="security",
            fields={
                "severity": severity.value,
                "event_type": event_type,
            },
        )
        return result

    @require_enterprise_mode
    async def send_batch_events(
        self,
        events: list[SplunkEvent],
    ) -> ConnectorResult:
        """
        Send multiple events to Splunk in a single request.

        Args:
            events: List of SplunkEvent objects
        """
        if not self.hec_url or not self.hec_token:
            return ConnectorResult(
                success=False,
                error="HEC URL and token must be configured for event ingestion",
            )

        start_time = time.time()

        # Build NDJSON payload
        payload_lines: list[dict[str, Any]] = []
        for event in events:
            line: dict[str, Any] = {"event": event.event}
            if event.time:
                line["time"] = event.time
            if event.host:
                line["host"] = event.host
            if event.source:
                line["source"] = event.source
            if event.sourcetype:
                line["sourcetype"] = event.sourcetype
            if event.index:
                line["index"] = event.index
            if event.fields:
                line["fields"] = event.fields
            payload_lines.append(line)

        ssl_context: bool = self.verify_ssl

        try:
            import json

            # Join events as newline-delimited JSON
            payload = "\n".join(json.dumps(line) for line in payload_lines)

            async with aiohttp.ClientSession(
                timeout=self.timeout,
                connector=aiohttp.TCPConnector(ssl=ssl_context),
            ) as session:
                async with session.post(
                    f"{self.hec_url}/services/collector/event",
                    data=payload,
                    headers=self._get_hec_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200 and data.get("code") == 0
                    self._record_request(latency_ms, success)

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data={
                            "events_sent": len(events),
                            "response": data,
                        },
                        latency_ms=latency_ms,
                        error=None if success else data.get("text", str(data)),
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
    # Saved Searches and Alerts
    # =========================================================================

    @require_enterprise_mode
    async def list_saved_searches(
        self,
        owner: str = "-",
        app: str = "-",
        search_filter: str | None = None,
    ) -> ConnectorResult:
        """
        List saved searches.

        Args:
            owner: Owner filter (- for all)
            app: App context (- for all)
            search_filter: Name filter
        """
        start_time = time.time()
        ssl_context: bool = self.verify_ssl

        params: dict[str, str | int] = {"output_mode": "json", "count": 1000}
        if search_filter:
            params["search"] = search_filter

        try:
            async with aiohttp.ClientSession(
                timeout=self.timeout,
                connector=aiohttp.TCPConnector(ssl=ssl_context),
            ) as session:
                async with session.get(
                    f"{self.base_url}/servicesNS/{owner}/{app}/saved/searches",
                    params=params,
                    headers=self._get_auth_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        entries = data.get("entry", [])
                        searches = [
                            {
                                "name": e.get("name"),
                                "search": e.get("content", {}).get("search"),
                                "is_scheduled": e.get("content", {}).get(
                                    "is_scheduled"
                                ),
                                "cron_schedule": e.get("content", {}).get(
                                    "cron_schedule"
                                ),
                            }
                            for e in entries
                        ]
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={"saved_searches": searches, "count": len(searches)},
                            latency_ms=latency_ms,
                        )
                    else:
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=str(data),
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
    async def create_alert(
        self,
        name: str,
        search: str,
        description: str = "",
        severity: SplunkSeverity = SplunkSeverity.MEDIUM,
        cron_schedule: str = "*/5 * * * *",
        alert_threshold: int = 0,
        actions: list[str] | None = None,
        app: str = "search",
    ) -> ConnectorResult:
        """
        Create a saved search alert.

        Args:
            name: Alert name
            search: SPL search query
            description: Alert description
            severity: Alert severity
            cron_schedule: Cron schedule for alert
            alert_threshold: Trigger when results exceed this
            actions: Alert actions (e.g., ["email", "webhook"])
            app: App context
        """
        start_time = time.time()
        ssl_context: bool = self.verify_ssl

        data = {
            "name": name,
            "search": search,
            "description": description,
            "is_scheduled": "1",
            "cron_schedule": cron_schedule,
            "alert_type": "number of events",
            "alert_comparator": "greater than",
            "alert_threshold": str(alert_threshold),
            "alert.severity": str(severity.value),
            "alert.track": "1",
        }

        if actions:
            data["actions"] = ",".join(actions)

        try:
            async with aiohttp.ClientSession(
                timeout=self.timeout,
                connector=aiohttp.TCPConnector(ssl=ssl_context),
            ) as session:
                async with session.post(
                    f"{self.base_url}/servicesNS/nobody/{app}/saved/searches",
                    data=urllib.parse.urlencode(data),
                    headers=self._get_auth_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    response_data = await response.json()

                    success = response.status in (200, 201)
                    self._record_request(latency_ms, success)

                    if success:
                        logger.info(f"Splunk alert created: {name}")
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data=response_data,
                            request_id=name,
                            latency_ms=latency_ms,
                        )
                    else:
                        error_msg = response_data.get("messages", [{}])
                        if error_msg and isinstance(error_msg, list):
                            error_msg = error_msg[0].get("text", str(response_data))
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=str(error_msg),
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

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> bool:
        """Check if Splunk connector is healthy."""
        # SSL context: False to disable verification, True/omitted for verification
        ssl_verify: bool = self.verify_ssl

        try:
            async with aiohttp.ClientSession(
                timeout=self.timeout,
                connector=aiohttp.TCPConnector(ssl=ssl_verify),
            ) as session:
                async with session.get(
                    f"{self.base_url}/services/server/info",
                    params={"output_mode": "json"},
                    headers=self._get_auth_headers(),
                ) as response:
                    if response.status == 200:
                        self._status = ConnectorStatus.CONNECTED
                        return True
                    elif response.status == 401:
                        self._status = ConnectorStatus.AUTH_FAILED
                        self._last_error = "Authentication failed"
                    else:
                        self._status = ConnectorStatus.ERROR
                        self._last_error = f"HTTP {response.status}"
                    return False
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            return False


# Import asyncio for _wait_for_job
import asyncio
