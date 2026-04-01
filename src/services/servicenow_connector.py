"""
Project Aura - ServiceNow Connector

Implements ADR-028 Phase 8: Enterprise Connector Expansion

ServiceNow REST API connector for:
- Incident management (CRUD operations)
- CMDB integration for asset discovery
- Change request management
- Knowledge base queries

SECURITY: Only available in ENTERPRISE or HYBRID mode.

Usage:
    >>> from src.services.servicenow_connector import ServiceNowConnector
    >>> snow = ServiceNowConnector(
    ...     instance_url="${SERVICENOW_INSTANCE_URL}",
    ...     username="${SERVICENOW_USERNAME}",
    ...     password="${SERVICENOW_PASSWORD}"
    ... )
    >>> await snow.create_incident(
    ...     short_description="Critical vulnerability detected",
    ...     category="security",
    ...     urgency=ServiceNowUrgency.HIGH
    ... )
"""

import base64
import logging
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
# Enums and Data Classes
# =============================================================================


class ServiceNowUrgency(Enum):
    """ServiceNow urgency levels (1=High, 2=Medium, 3=Low)."""

    HIGH = 1
    MEDIUM = 2
    LOW = 3


class ServiceNowImpact(Enum):
    """ServiceNow impact levels (1=High, 2=Medium, 3=Low)."""

    HIGH = 1
    MEDIUM = 2
    LOW = 3


class ServiceNowIncidentState(Enum):
    """ServiceNow incident states."""

    NEW = 1
    IN_PROGRESS = 2
    ON_HOLD = 3
    RESOLVED = 6
    CLOSED = 7
    CANCELLED = 8


class ServiceNowPriority(Enum):
    """ServiceNow priority levels (calculated from impact + urgency)."""

    CRITICAL = 1  # P1 - Critical
    HIGH = 2  # P2 - High
    MODERATE = 3  # P3 - Moderate
    LOW = 4  # P4 - Low
    PLANNING = 5  # P5 - Planning


@dataclass
class ServiceNowIncident:
    """ServiceNow incident structure."""

    short_description: str
    description: str = ""
    category: str = "software"
    subcategory: str | None = None
    urgency: ServiceNowUrgency = ServiceNowUrgency.MEDIUM
    impact: ServiceNowImpact = ServiceNowImpact.MEDIUM
    assignment_group: str | None = None
    assigned_to: str | None = None
    caller_id: str | None = None
    cmdb_ci: str | None = None  # Configuration Item sys_id
    business_service: str | None = None
    additional_fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceNowChangeRequest:
    """ServiceNow change request structure."""

    short_description: str
    description: str = ""
    type: str = "normal"  # normal, standard, emergency
    category: str = "software"
    risk: str = "moderate"  # high, moderate, low
    impact: str = "medium"  # high, medium, low
    assignment_group: str | None = None
    requested_by: str | None = None
    cmdb_ci: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    additional_fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class CMDBConfigurationItem:
    """CMDB Configuration Item structure."""

    sys_id: str
    name: str
    sys_class_name: str  # e.g., cmdb_ci_server, cmdb_ci_app_server
    operational_status: str | None = None
    environment: str | None = None
    ip_address: str | None = None
    fqdn: str | None = None
    os: str | None = None
    os_version: str | None = None
    manufacturer: str | None = None
    model_id: str | None = None
    serial_number: str | None = None
    location: str | None = None
    department: str | None = None
    owned_by: str | None = None
    managed_by: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# ServiceNow Connector
# =============================================================================


class ServiceNowConnector(ExternalToolConnector):
    """
    ServiceNow connector for ITSM integration.

    Supports:
    - Incident management (create, read, update, close)
    - CMDB queries for asset discovery
    - Change request management
    - Knowledge base integration
    """

    def __init__(
        self,
        instance_url: str,
        username: str,
        password: str,
        api_version: str = "v2",
        default_assignment_group: str | None = None,
        timeout_seconds: float = 30.0,
    ):
        """
        Initialize ServiceNow connector.

        Args:
            instance_url: ServiceNow instance URL (e.g., https://company.service-now.com)
            username: API username
            password: API password
            api_version: API version (default: v2)
            default_assignment_group: Default assignment group for incidents
            timeout_seconds: Request timeout
        """
        super().__init__("servicenow", timeout_seconds)

        self.instance_url = instance_url.rstrip("/")
        self.api_version = api_version
        self.default_assignment_group = default_assignment_group

        # Build Basic auth header
        credentials = f"{username}:{password}"
        self._auth_header = base64.b64encode(credentials.encode()).decode()

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Basic {self._auth_header}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get_table_url(self, table: str) -> str:
        """Get URL for a ServiceNow table."""
        return f"{self.instance_url}/api/now/{self.api_version}/table/{table}"

    # =========================================================================
    # Incident Management
    # =========================================================================

    @require_enterprise_mode
    async def create_incident(
        self,
        short_description: str,
        description: str = "",
        category: str = "software",
        subcategory: str | None = None,
        urgency: ServiceNowUrgency = ServiceNowUrgency.MEDIUM,
        impact: ServiceNowImpact = ServiceNowImpact.MEDIUM,
        assignment_group: str | None = None,
        assigned_to: str | None = None,
        caller_id: str | None = None,
        cmdb_ci: str | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        """
        Create a new incident.

        Args:
            short_description: Brief incident summary
            description: Detailed description
            category: Incident category
            subcategory: Incident subcategory
            urgency: Urgency level (HIGH, MEDIUM, LOW)
            impact: Impact level (HIGH, MEDIUM, LOW)
            assignment_group: Assignment group sys_id or name
            assigned_to: Assigned user sys_id or username
            caller_id: Caller user sys_id or username
            cmdb_ci: Related configuration item sys_id
            additional_fields: Additional ServiceNow fields

        Returns:
            ConnectorResult with created incident data
        """
        start_time = time.time()

        payload = {
            "short_description": short_description,
            "description": description,
            "category": category,
            "urgency": urgency.value,
            "impact": impact.value,
        }

        if subcategory:
            payload["subcategory"] = subcategory
        if assignment_group:
            payload["assignment_group"] = assignment_group
        elif self.default_assignment_group:
            payload["assignment_group"] = self.default_assignment_group
        if assigned_to:
            payload["assigned_to"] = assigned_to
        if caller_id:
            payload["caller_id"] = caller_id
        if cmdb_ci:
            payload["cmdb_ci"] = cmdb_ci
        if additional_fields:
            payload.update(additional_fields)

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    self._get_table_url("incident"),
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    if response.status in (200, 201):
                        self._status = ConnectorStatus.CONNECTED
                        self._record_request(latency_ms, True)
                        result_data = data.get("result", {})
                        incident_number = result_data.get("number", "Unknown")
                        logger.info(f"ServiceNow incident created: {incident_number}")
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data=result_data,
                            request_id=result_data.get("sys_id"),
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        error_msg = data.get("error", {}).get("message", str(data))
                        self._last_error = error_msg
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
                            data=data,
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.exception(f"ServiceNow connector error: {e}")
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def create_security_incident(
        self,
        title: str,
        cve_id: str | None = None,
        severity: str = "HIGH",
        affected_asset: str | None = None,
        description: str = "",
        recommendation: str | None = None,
        approval_url: str | None = None,
        cmdb_ci: str | None = None,
    ) -> ConnectorResult:
        """
        Create a security-specific incident with standard formatting.

        Args:
            title: Incident title
            cve_id: CVE identifier
            severity: CRITICAL, HIGH, MEDIUM, LOW
            affected_asset: Affected asset/file path
            description: Detailed description
            recommendation: Recommended action
            approval_url: URL to HITL approval dashboard
            cmdb_ci: Related configuration item sys_id
        """
        severity_urgency_map = {
            "CRITICAL": ServiceNowUrgency.HIGH,
            "HIGH": ServiceNowUrgency.HIGH,
            "MEDIUM": ServiceNowUrgency.MEDIUM,
            "LOW": ServiceNowUrgency.LOW,
        }

        severity_impact_map = {
            "CRITICAL": ServiceNowImpact.HIGH,
            "HIGH": ServiceNowImpact.HIGH,
            "MEDIUM": ServiceNowImpact.MEDIUM,
            "LOW": ServiceNowImpact.LOW,
        }

        full_description = f"""
=== Security Vulnerability ===

CVE: {cve_id or 'N/A'}
Severity: {severity}
Affected Asset: {affected_asset or 'N/A'}

=== Description ===
{description}

=== Recommendation ===
{recommendation or 'Review and apply the auto-generated patch.'}

=== Source ===
Detected by: Aura Security Platform (Automated Detection)
Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
"""

        if approval_url:
            full_description += (
                f"\n=== HITL Approval ===\nReview and approve: {approval_url}\n"
            )

        return await self.create_incident(
            short_description=f"[{severity}] Security: {title}",
            description=full_description.strip(),
            category="security",
            subcategory="vulnerability",
            urgency=severity_urgency_map.get(
                severity.upper(), ServiceNowUrgency.MEDIUM
            ),
            impact=severity_impact_map.get(severity.upper(), ServiceNowImpact.MEDIUM),
            cmdb_ci=cmdb_ci,
            additional_fields=(
                {
                    "u_cve_id": cve_id,  # Custom field (if configured in ServiceNow)
                }
                if cve_id
                else None
            ),
        )

    @require_enterprise_mode
    async def get_incident(self, incident_id: str) -> ConnectorResult:
        """
        Get an incident by sys_id or number.

        Args:
            incident_id: Incident sys_id or number (e.g., INC0012345)
        """
        start_time = time.time()

        # Determine if it's a sys_id or number
        if incident_id.startswith("INC"):
            query = f"number={incident_id}"
        else:
            query = f"sys_id={incident_id}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self._get_table_url('incident')}?sysparm_query={query}&sysparm_limit=1",
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    if response.status == 200:
                        self._record_request(latency_ms, True)
                        results = data.get("result", [])
                        if results:
                            return ConnectorResult(
                                success=True,
                                status_code=response.status,
                                data=results[0],
                                request_id=results[0].get("sys_id"),
                                latency_ms=latency_ms,
                            )
                        else:
                            return ConnectorResult(
                                success=False,
                                status_code=404,
                                error=f"Incident not found: {incident_id}",
                                latency_ms=latency_ms,
                            )
                    else:
                        self._record_request(latency_ms, False)
                        error_msg = data.get("error", {}).get("message", str(data))
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
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
    async def update_incident(
        self,
        incident_id: str,
        updates: dict[str, Any],
    ) -> ConnectorResult:
        """
        Update an existing incident.

        Args:
            incident_id: Incident sys_id
            updates: Fields to update
        """
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.patch(
                    f"{self._get_table_url('incident')}/{incident_id}",
                    json=updates,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        logger.info(f"ServiceNow incident updated: {incident_id}")

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data=data.get("result", {}),
                        request_id=incident_id,
                        latency_ms=latency_ms,
                        error=(
                            None
                            if success
                            else data.get("error", {}).get("message", str(data))
                        ),
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
    async def resolve_incident(
        self,
        incident_id: str,
        resolution_code: str = "Solved (Permanently)",
        resolution_notes: str = "",
        close_notes: str | None = None,
    ) -> ConnectorResult:
        """
        Resolve an incident.

        Args:
            incident_id: Incident sys_id
            resolution_code: Resolution code (e.g., "Solved (Permanently)")
            resolution_notes: Notes about the resolution
            close_notes: Additional close notes
        """
        updates = {
            "state": ServiceNowIncidentState.RESOLVED.value,
            "close_code": resolution_code,
            "close_notes": resolution_notes,
        }
        if close_notes:
            updates["close_notes"] = close_notes

        return await self.update_incident(incident_id, updates)

    @require_enterprise_mode
    async def add_incident_comment(
        self,
        incident_id: str,
        comment: str,
        work_notes: bool = False,
    ) -> ConnectorResult:
        """
        Add a comment or work note to an incident.

        Args:
            incident_id: Incident sys_id
            comment: Comment text
            work_notes: If True, add as work notes (internal); else customer-visible
        """
        field = "work_notes" if work_notes else "comments"
        return await self.update_incident(incident_id, {field: comment})

    @require_enterprise_mode
    async def list_incidents(
        self,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "-sys_created_on",
        fields: list[str] | None = None,
    ) -> ConnectorResult:
        """
        List incidents with optional filtering.

        Args:
            query: ServiceNow encoded query string
            limit: Maximum results to return
            offset: Results offset for pagination
            order_by: Field to order by (prefix with - for descending)
            fields: Specific fields to return
        """
        start_time = time.time()

        params = [
            f"sysparm_limit={limit}",
            f"sysparm_offset={offset}",
            f"sysparm_query=ORDERBY{order_by}",
        ]

        if query:
            params[2] = f"sysparm_query={query}^ORDERBY{order_by}"
        if fields:
            params.append(f"sysparm_fields={','.join(fields)}")

        url = f"{self._get_table_url('incident')}?{'&'.join(params)}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data={
                            "incidents": data.get("result", []),
                            "count": len(data.get("result", [])),
                        },
                        latency_ms=latency_ms,
                        error=(
                            None
                            if success
                            else data.get("error", {}).get("message", str(data))
                        ),
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
    # CMDB Integration
    # =========================================================================

    @require_enterprise_mode
    async def get_ci(self, ci_id: str) -> ConnectorResult:
        """
        Get a Configuration Item by sys_id.

        Args:
            ci_id: Configuration Item sys_id
        """
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self._get_table_url('cmdb_ci')}/{ci_id}",
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        result = data.get("result", {})
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data=result,
                            request_id=result.get("sys_id"),
                            latency_ms=latency_ms,
                        )
                    else:
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=data.get("error", {}).get("message", str(data)),
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
    async def search_cmdb(
        self,
        query: str | None = None,
        ci_class: str = "cmdb_ci",
        name_contains: str | None = None,
        ip_address: str | None = None,
        limit: int = 100,
        fields: list[str] | None = None,
    ) -> ConnectorResult:
        """
        Search CMDB for Configuration Items.

        Args:
            query: ServiceNow encoded query string
            ci_class: CI class to search (e.g., cmdb_ci_server, cmdb_ci_app_server)
            name_contains: Filter by name (LIKE query)
            ip_address: Filter by IP address
            limit: Maximum results
            fields: Specific fields to return
        """
        start_time = time.time()

        # Build query
        query_parts = []
        if query:
            query_parts.append(query)
        if name_contains:
            query_parts.append(f"nameLIKE{name_contains}")
        if ip_address:
            query_parts.append(f"ip_address={ip_address}")

        params = [f"sysparm_limit={limit}"]
        if query_parts:
            params.append(f"sysparm_query={'^'.join(query_parts)}")
        if fields:
            params.append(f"sysparm_fields={','.join(fields)}")

        url = f"{self._get_table_url(ci_class)}?{'&'.join(params)}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        results = data.get("result", [])
                        cis = []
                        for r in results:
                            ci = CMDBConfigurationItem(
                                sys_id=r.get("sys_id", ""),
                                name=r.get("name", ""),
                                sys_class_name=r.get("sys_class_name", ""),
                                operational_status=r.get("operational_status"),
                                environment=r.get("environment"),
                                ip_address=r.get("ip_address"),
                                fqdn=r.get("fqdn"),
                                os=r.get("os"),
                                os_version=r.get("os_version"),
                                manufacturer=(
                                    r.get("manufacturer", {}).get("value")
                                    if isinstance(r.get("manufacturer"), dict)
                                    else r.get("manufacturer")
                                ),
                                serial_number=r.get("serial_number"),
                                location=(
                                    r.get("location", {}).get("value")
                                    if isinstance(r.get("location"), dict)
                                    else r.get("location")
                                ),
                                owned_by=(
                                    r.get("owned_by", {}).get("value")
                                    if isinstance(r.get("owned_by"), dict)
                                    else r.get("owned_by")
                                ),
                                managed_by=(
                                    r.get("managed_by", {}).get("value")
                                    if isinstance(r.get("managed_by"), dict)
                                    else r.get("managed_by")
                                ),
                                attributes=r,
                            )
                            cis.append(ci)

                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "configuration_items": [
                                    {
                                        "sys_id": ci.sys_id,
                                        "name": ci.name,
                                        "class": ci.sys_class_name,
                                        "ip_address": ci.ip_address,
                                        "fqdn": ci.fqdn,
                                        "environment": ci.environment,
                                        "os": ci.os,
                                    }
                                    for ci in cis
                                ],
                                "count": len(cis),
                            },
                            latency_ms=latency_ms,
                        )
                    else:
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=data.get("error", {}).get("message", str(data)),
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
    async def get_ci_relationships(
        self, ci_id: str, relationship_type: str | None = None
    ) -> ConnectorResult:
        """
        Get relationships for a Configuration Item.

        Args:
            ci_id: Configuration Item sys_id
            relationship_type: Filter by relationship type
        """
        start_time = time.time()

        query = f"parent={ci_id}^ORchild={ci_id}"
        if relationship_type:
            query += f"^type.name={relationship_type}"

        params = [f"sysparm_query={query}", "sysparm_limit=500"]
        url = f"{self._get_table_url('cmdb_rel_ci')}?{'&'.join(params)}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self._get_headers()) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data={
                            "relationships": data.get("result", []),
                            "count": len(data.get("result", [])),
                        },
                        latency_ms=latency_ms,
                        error=(
                            None
                            if success
                            else data.get("error", {}).get("message", str(data))
                        ),
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
    # Change Request Management
    # =========================================================================

    @require_enterprise_mode
    async def create_change_request(
        self,
        short_description: str,
        description: str = "",
        change_type: str = "normal",
        category: str = "software",
        risk: str = "moderate",
        impact: str = "medium",
        assignment_group: str | None = None,
        cmdb_ci: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        """
        Create a change request.

        Args:
            short_description: Brief change summary
            description: Detailed description
            change_type: normal, standard, emergency
            category: Change category
            risk: high, moderate, low
            impact: high, medium, low
            assignment_group: Assignment group sys_id or name
            cmdb_ci: Related configuration item sys_id
            start_date: Planned start date (ISO format)
            end_date: Planned end date (ISO format)
            additional_fields: Additional ServiceNow fields
        """
        start_time = time.time()

        payload = {
            "short_description": short_description,
            "description": description,
            "type": change_type,
            "category": category,
            "risk": risk,
            "impact": impact,
        }

        if assignment_group:
            payload["assignment_group"] = assignment_group
        elif self.default_assignment_group:
            payload["assignment_group"] = self.default_assignment_group
        if cmdb_ci:
            payload["cmdb_ci"] = cmdb_ci
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date
        if additional_fields:
            payload.update(additional_fields)

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    self._get_table_url("change_request"),
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    if response.status in (200, 201):
                        self._status = ConnectorStatus.CONNECTED
                        self._record_request(latency_ms, True)
                        result_data = data.get("result", {})
                        change_number = result_data.get("number", "Unknown")
                        logger.info(
                            f"ServiceNow change request created: {change_number}"
                        )
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data=result_data,
                            request_id=result_data.get("sys_id"),
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        error_msg = data.get("error", {}).get("message", str(data))
                        self._last_error = error_msg
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
                            data=data,
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.exception(f"ServiceNow connector error: {e}")
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def create_security_change_request(
        self,
        title: str,
        cve_id: str | None = None,
        severity: str = "HIGH",
        affected_asset: str | None = None,
        patch_description: str = "",
        rollback_plan: str = "",
        approval_url: str | None = None,
        cmdb_ci: str | None = None,
    ) -> ConnectorResult:
        """
        Create a security patch change request.

        Args:
            title: Change request title
            cve_id: CVE identifier
            severity: CRITICAL, HIGH, MEDIUM, LOW
            affected_asset: Affected asset/file
            patch_description: Description of the patch
            rollback_plan: Rollback procedure
            approval_url: HITL approval URL
            cmdb_ci: Related configuration item
        """
        risk_map = {
            "CRITICAL": "high",
            "HIGH": "high",
            "MEDIUM": "moderate",
            "LOW": "low",
        }

        description = f"""
=== Security Patch Change Request ===

CVE: {cve_id or 'N/A'}
Severity: {severity}
Affected Asset: {affected_asset or 'N/A'}

=== Patch Description ===
{patch_description}

=== Rollback Plan ===
{rollback_plan or 'Revert to previous version from backup.'}

=== Source ===
Generated by: Aura Security Platform (Automated Patch Generation)
Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
"""

        if approval_url:
            description += (
                f"\n=== HITL Approval ===\nReview and approve: {approval_url}\n"
            )

        return await self.create_change_request(
            short_description=f"[{severity}] Security Patch: {title}",
            description=description.strip(),
            change_type="normal" if severity != "CRITICAL" else "emergency",
            category="security",
            risk=risk_map.get(severity.upper(), "moderate"),
            impact="high" if severity in ("CRITICAL", "HIGH") else "medium",
            cmdb_ci=cmdb_ci,
        )

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> bool:
        """Check if ServiceNow connector is healthy."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Use sys_user endpoint to validate credentials
                async with session.get(
                    f"{self._get_table_url('sys_user')}?sysparm_limit=1",
                    headers=self._get_headers(),
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
