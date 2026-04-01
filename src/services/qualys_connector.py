"""
Project Aura - Qualys Connector

Implements ADR-028 Phase 8 Extension: Security Tool Connectors

Qualys VMDR REST API connector for:
- Vulnerability scanning and results
- Asset inventory and discovery
- Host detection data
- Compliance reporting
- Knowledge base queries

SECURITY: Only available in ENTERPRISE or HYBRID mode.

Usage:
    >>> from src.services.qualys_connector import QualysConnector
    >>> qualys = QualysConnector(
    ...     username="api_user",
    ...     password="api_password",
    ...     platform="qualysapi.qualys.com"
    ... )
    >>> vulns = await qualys.get_host_detections(ip="192.168.1.100")
"""

import base64
import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiohttp
import defusedxml.ElementTree as DefusedET

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


class QualysPlatform(Enum):
    """Qualys API platform URLs."""

    US1 = "qualysapi.qualys.com"
    US2 = "qualysapi.qg2.apps.qualys.com"
    US3 = "qualysapi.qg3.apps.qualys.com"
    US4 = "qualysapi.qg4.apps.qualys.com"
    EU1 = "qualysapi.qualys.eu"
    EU2 = "qualysapi.qg2.apps.qualys.eu"
    IN1 = "qualysapi.qg1.apps.qualys.in"
    CA1 = "qualysapi.qg1.apps.qualys.ca"
    AE1 = "qualysapi.qg1.apps.qualys.ae"
    UK1 = "qualysapi.qg1.apps.qualys.co.uk"
    AU1 = "qualysapi.qg1.apps.qualys.com.au"


class QualysSeverity(Enum):
    """Qualys vulnerability severity levels (1-5)."""

    INFORMATIONAL = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


class QualysVulnType(Enum):
    """Qualys vulnerability types."""

    CONFIRMED = "Confirmed"
    POTENTIAL = "Potential"
    INFO = "Info"


class QualysAssetType(Enum):
    """Qualys asset types."""

    HOST = "HOST"
    WEBAPP = "WEBAPP"
    CLOUD = "CLOUD"
    CONTAINER = "CONTAINER"


class QualysScanStatus(Enum):
    """Qualys scan status."""

    SUBMITTED = "Submitted"
    RUNNING = "Running"
    FINISHED = "Finished"
    CANCELED = "Canceled"
    PAUSED = "Paused"
    ERROR = "Error"


@dataclass
class QualysVulnerability:
    """Qualys vulnerability details."""

    qid: int  # Qualys ID
    title: str
    severity: QualysSeverity
    vuln_type: QualysVulnType
    category: str = ""
    cve_ids: list[str] = field(default_factory=list)
    cvss_base: float | None = None
    cvss_temporal: float | None = None
    solution: str = ""
    diagnosis: str = ""
    consequence: str = ""
    pci_flag: bool = False
    published_date: str | None = None
    last_service_modification: str | None = None


@dataclass
class QualysHost:
    """Qualys host/asset details."""

    host_id: int
    ip: str
    hostname: str | None = None
    os: str | None = None
    dns: str | None = None
    netbios: str | None = None
    tracking_method: str | None = None
    last_scan: str | None = None
    last_vm_scanned: str | None = None
    last_vm_auth_scanned: str | None = None
    tags: list[str] = field(default_factory=list)
    cloud_provider: str | None = None
    cloud_resource_id: str | None = None


@dataclass
class QualysDetection:
    """Qualys host detection (vulnerability on a host)."""

    host_id: int
    qid: int
    severity: QualysSeverity
    vuln_type: QualysVulnType
    status: str = ""
    first_found: str | None = None
    last_found: str | None = None
    times_found: int = 0
    is_ignored: bool = False
    is_disabled: bool = False
    port: int | None = None
    protocol: str | None = None
    service: str | None = None
    ssl: bool = False
    results: str = ""


# =============================================================================
# Qualys Connector
# =============================================================================


class QualysConnector(ExternalToolConnector):
    """
    Qualys VMDR connector for vulnerability management.

    Supports:
    - Vulnerability scan results
    - Asset inventory
    - Host detection queries
    - Knowledge base queries
    - Compliance reporting
    """

    def __init__(
        self,
        username: str,
        password: str,
        platform: QualysPlatform | str = QualysPlatform.US1,
        timeout_seconds: float = 60.0,
    ):
        """
        Initialize Qualys connector.

        Args:
            username: Qualys API username
            password: Qualys API password
            platform: Qualys platform URL or enum
            timeout_seconds: Request timeout
        """
        super().__init__("qualys", timeout_seconds)

        if isinstance(platform, QualysPlatform):
            self.base_url = f"https://{platform.value}"
        else:
            self.base_url = f"https://{platform}"

        # Build Basic auth header
        credentials = f"{username}:{password}"
        self._auth_header = base64.b64encode(credentials.encode()).decode()

    def _get_headers(
        self, content_type: str = "application/x-www-form-urlencoded"
    ) -> dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Basic {self._auth_header}",
            "Content-Type": content_type,
            "X-Requested-With": "Python aiohttp",
        }

    def _parse_xml_response(self, xml_text: str) -> dict[str, Any]:
        """Parse XML response to dict securely (defusedxml prevents XXE attacks)."""
        try:
            root = DefusedET.fromstring(xml_text)
            return self._element_to_dict(root)
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
            return {"error": str(e), "raw": xml_text[:500]}

    def _element_to_dict(self, element: ET.Element) -> dict[str, Any]:
        """Convert XML element to dictionary."""
        result: dict[str, Any] = {}

        # Add element attributes
        if element.attrib:
            result["@attributes"] = element.attrib

        # Add child elements
        for child in element:
            child_data = self._element_to_dict(child)

            if child.tag in result:
                # Convert to list if multiple same-named children
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data

        # Add text content
        if element.text and element.text.strip():
            if result:
                result["#text"] = element.text.strip()
            else:
                # Return dict with text content to maintain consistent return type
                return {"#text": element.text.strip()}

        return result if result else {}

    # =========================================================================
    # Vulnerability Knowledge Base
    # =========================================================================

    @require_enterprise_mode
    async def get_vulnerability_details(self, qid: int) -> ConnectorResult:
        """
        Get vulnerability details from Knowledge Base.

        Args:
            qid: Qualys vulnerability ID
        """
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/2.0/fo/knowledge_base/vuln/",
                    data={"action": "list", "ids": str(qid), "details": "All"},
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    xml_text = await response.text()

                    if response.status == 200:
                        self._status = ConnectorStatus.CONNECTED
                        self._record_request(latency_ms, True)

                        data = self._parse_xml_response(xml_text)
                        vuln_list = data.get("KNOWLEDGE_BASE_VULN_LIST_OUTPUT", {})
                        response_data = vuln_list.get("RESPONSE", {})
                        vuln_data = response_data.get("VULN_LIST", {}).get("VULN", {})

                        if isinstance(vuln_data, dict):
                            return ConnectorResult(
                                success=True,
                                status_code=response.status,
                                data={
                                    "qid": qid,
                                    "title": vuln_data.get("TITLE", ""),
                                    "severity": int(vuln_data.get("SEVERITY", 1)),
                                    "category": vuln_data.get("CATEGORY", ""),
                                    "cve_ids": self._extract_cves(vuln_data),
                                    "cvss_base": vuln_data.get("CVSS", {}).get("BASE"),
                                    "solution": vuln_data.get("SOLUTION", ""),
                                    "diagnosis": vuln_data.get("DIAGNOSIS", ""),
                                    "consequence": vuln_data.get("CONSEQUENCE", ""),
                                    "pci_flag": vuln_data.get("PCI_FLAG", "0") == "1",
                                },
                                request_id=str(qid),
                                latency_ms=latency_ms,
                            )
                        else:
                            return ConnectorResult(
                                success=False,
                                status_code=404,
                                error=f"Vulnerability QID {qid} not found",
                                latency_ms=latency_ms,
                            )
                    else:
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=f"API error: {response.status}",
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.exception(f"Qualys connector error: {e}")
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    def _extract_cves(self, vuln_data: dict) -> list[str]:
        """Extract CVE IDs from vulnerability data."""
        cves = []
        cve_list = vuln_data.get("CVE_LIST", {}).get("CVE", [])
        if isinstance(cve_list, dict):
            cve_list = [cve_list]
        for cve in cve_list:
            if isinstance(cve, dict):
                cve_id = cve.get("ID", "")
            else:
                cve_id = cve
            if cve_id:
                cves.append(cve_id)
        return cves

    @require_enterprise_mode
    async def search_vulnerabilities_by_cve(self, cve_id: str) -> ConnectorResult:
        """
        Search Qualys Knowledge Base by CVE ID.

        Args:
            cve_id: CVE identifier (e.g., CVE-2024-1234)
        """
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/2.0/fo/knowledge_base/vuln/",
                    data={"action": "list", "details": "All", "cve_id": cve_id},
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    xml_text = await response.text()

                    if response.status == 200:
                        self._status = ConnectorStatus.CONNECTED
                        self._record_request(latency_ms, True)

                        data = self._parse_xml_response(xml_text)
                        vuln_list = data.get("KNOWLEDGE_BASE_VULN_LIST_OUTPUT", {})
                        response_data = vuln_list.get("RESPONSE", {})
                        vulns = response_data.get("VULN_LIST", {}).get("VULN", [])

                        if isinstance(vulns, dict):
                            vulns = [vulns]

                        results = [
                            {
                                "qid": v.get("QID", ""),
                                "title": v.get("TITLE", ""),
                                "severity": int(v.get("SEVERITY", 1)),
                                "category": v.get("CATEGORY", ""),
                                "cve_ids": self._extract_cves(v),
                            }
                            for v in vulns
                            if isinstance(v, dict)
                        ]

                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "vulnerabilities": results,
                                "count": len(results),
                                "cve_id": cve_id,
                            },
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=f"API error: {response.status}",
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
    # Asset Management
    # =========================================================================

    @require_enterprise_mode
    async def list_hosts(
        self,
        ips: str | None = None,
        network_id: str | None = None,
        tracking_method: str | None = None,
        limit: int = 1000,
    ) -> ConnectorResult:
        """
        List hosts/assets.

        Args:
            ips: IP range filter (e.g., "192.168.1.0/24" or "192.168.1.1-192.168.1.100")
            network_id: Network ID filter
            tracking_method: Tracking method filter (IP, DNS, NETBIOS, EC2)
            limit: Maximum results
        """
        start_time = time.time()

        params = {"action": "list", "truncation_limit": str(limit)}
        if ips:
            params["ips"] = ips
        if network_id:
            params["network_id"] = network_id
        if tracking_method:
            params["tracking_method"] = tracking_method

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/2.0/fo/asset/host/",
                    data=params,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    xml_text = await response.text()

                    if response.status == 200:
                        self._status = ConnectorStatus.CONNECTED
                        self._record_request(latency_ms, True)

                        data = self._parse_xml_response(xml_text)
                        host_list = data.get("HOST_LIST_OUTPUT", {})
                        response_data = host_list.get("RESPONSE", {})
                        hosts = response_data.get("HOST_LIST", {}).get("HOST", [])

                        if isinstance(hosts, dict):
                            hosts = [hosts]

                        results = [
                            {
                                "host_id": h.get("ID", ""),
                                "ip": h.get("IP", ""),
                                "hostname": h.get("DNS", ""),
                                "os": h.get("OS", ""),
                                "netbios": h.get("NETBIOS", ""),
                                "tracking_method": h.get("TRACKING_METHOD", ""),
                                "last_scan": h.get("LAST_SCAN_DATETIME", ""),
                            }
                            for h in hosts
                            if isinstance(h, dict)
                        ]

                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={"hosts": results, "count": len(results)},
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=f"API error: {response.status}",
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
    async def get_host_details(self, host_id: int) -> ConnectorResult:
        """
        Get detailed host information.

        Args:
            host_id: Qualys host ID
        """
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/2.0/fo/asset/host/",
                    data={"action": "list", "ids": str(host_id), "details": "All"},
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    xml_text = await response.text()

                    if response.status == 200:
                        self._record_request(latency_ms, True)

                        data = self._parse_xml_response(xml_text)
                        host_list = data.get("HOST_LIST_OUTPUT", {})
                        response_data = host_list.get("RESPONSE", {})
                        host = response_data.get("HOST_LIST", {}).get("HOST", {})

                        if isinstance(host, dict) and host:
                            return ConnectorResult(
                                success=True,
                                status_code=response.status,
                                data={
                                    "host_id": host.get("ID", ""),
                                    "ip": host.get("IP", ""),
                                    "hostname": host.get("DNS", ""),
                                    "os": host.get("OS", ""),
                                    "netbios": host.get("NETBIOS", ""),
                                    "tracking_method": host.get("TRACKING_METHOD", ""),
                                    "last_scan": host.get("LAST_SCAN_DATETIME", ""),
                                    "last_vm_scanned": host.get(
                                        "LAST_VULN_SCAN_DATETIME", ""
                                    ),
                                    "last_vm_auth_scanned": host.get(
                                        "LAST_VM_SCANNED_DATE", ""
                                    ),
                                    "cloud_provider": host.get("CLOUD_PROVIDER", ""),
                                    "tags": self._extract_tags(host),
                                },
                                request_id=str(host_id),
                                latency_ms=latency_ms,
                            )
                        else:
                            return ConnectorResult(
                                success=False,
                                status_code=404,
                                error=f"Host {host_id} not found",
                                latency_ms=latency_ms,
                            )
                    else:
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=f"API error: {response.status}",
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

    def _extract_tags(self, host: dict) -> list[str]:
        """Extract tags from host data."""
        tags = []
        tag_list = host.get("TAGS", {}).get("TAG", [])
        if isinstance(tag_list, dict):
            tag_list = [tag_list]
        for tag in tag_list:
            if isinstance(tag, dict):
                tag_name = tag.get("NAME", "")
            else:
                tag_name = tag
            if tag_name:
                tags.append(tag_name)
        return tags

    # =========================================================================
    # Host Detections (Vulnerabilities on Hosts)
    # =========================================================================

    @require_enterprise_mode
    async def get_host_detections(
        self,
        host_id: int | None = None,
        ip: str | None = None,
        severities: list[int] | None = None,
        status: str | None = None,
        include_ignored: bool = False,
        limit: int = 1000,
    ) -> ConnectorResult:
        """
        Get vulnerability detections for hosts.

        Args:
            host_id: Filter by host ID
            ip: Filter by IP address
            severities: Filter by severity levels (1-5)
            status: Filter by detection status (New, Active, Fixed, Re-Opened)
            include_ignored: Include ignored detections
            limit: Maximum results
        """
        start_time = time.time()

        params = {
            "action": "list",
            "truncation_limit": str(limit),
            "output_format": "XML",
            "show_results": "1",
        }

        if host_id:
            params["host_ids"] = str(host_id)
        if ip:
            params["ips"] = ip
        if severities:
            params["severities"] = ",".join(str(s) for s in severities)
        if status:
            params["status"] = status
        if include_ignored:
            params["include_ignored"] = "1"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/2.0/fo/asset/host/vm/detection/",
                    data=params,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    xml_text = await response.text()

                    if response.status == 200:
                        self._status = ConnectorStatus.CONNECTED
                        self._record_request(latency_ms, True)

                        data = self._parse_xml_response(xml_text)
                        detection_list = data.get("HOST_LIST_VM_DETECTION_OUTPUT", {})
                        response_data = detection_list.get("RESPONSE", {})
                        host_list = response_data.get("HOST_LIST", {}).get("HOST", [])

                        if isinstance(host_list, dict):
                            host_list = [host_list]

                        detections = []
                        for host in host_list:
                            if not isinstance(host, dict):
                                continue

                            host_id_val = host.get("ID", "")
                            detection_entries = host.get("DETECTION_LIST", {}).get(
                                "DETECTION", []
                            )
                            if isinstance(detection_entries, dict):
                                detection_entries = [detection_entries]

                            for det in detection_entries:
                                if isinstance(det, dict):
                                    detections.append(
                                        {
                                            "host_id": host_id_val,
                                            "qid": det.get("QID", ""),
                                            "severity": int(det.get("SEVERITY", 1)),
                                            "type": det.get("TYPE", ""),
                                            "status": det.get("STATUS", ""),
                                            "first_found": det.get(
                                                "FIRST_FOUND_DATETIME", ""
                                            ),
                                            "last_found": det.get(
                                                "LAST_FOUND_DATETIME", ""
                                            ),
                                            "times_found": int(
                                                det.get("TIMES_FOUND", 0)
                                            ),
                                            "port": det.get("PORT", ""),
                                            "protocol": det.get("PROTOCOL", ""),
                                            "service": det.get("SERVICE", ""),
                                            "ssl": det.get("SSL", "0") == "1",
                                            "results": det.get("RESULTS", ""),
                                        }
                                    )

                        # Summary by severity
                        by_severity = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                        for det in detections:
                            sev = det.get("severity", 1)
                            if sev in by_severity:
                                by_severity[sev] += 1

                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "detections": detections,
                                "count": len(detections),
                                "by_severity": by_severity,
                            },
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=f"API error: {response.status}",
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
    async def get_critical_detections(
        self,
        ip_range: str | None = None,
        max_results: int = 500,
    ) -> ConnectorResult:
        """
        Get critical and high severity detections.

        Args:
            ip_range: Optional IP range to filter
            max_results: Maximum results
        """
        result: ConnectorResult = await self.get_host_detections(
            ip=ip_range,
            severities=[4, 5],  # High and Critical
            limit=max_results,
        )
        return result

    @require_enterprise_mode
    async def search_detections_by_cve(
        self,
        cve_id: str,
        ip_range: str | None = None,
    ) -> ConnectorResult:
        """
        Search for hosts affected by a specific CVE.

        Args:
            cve_id: CVE identifier
            ip_range: Optional IP range to filter
        """
        # First, find the QID(s) for this CVE
        vuln_result: ConnectorResult = await self.search_vulnerabilities_by_cve(cve_id)
        if not vuln_result.success:
            return vuln_result

        qids = [str(v.get("qid")) for v in vuln_result.data.get("vulnerabilities", [])]
        if not qids:
            return ConnectorResult(
                success=True,
                data={
                    "detections": [],
                    "count": 0,
                    "cve_id": cve_id,
                    "message": f"No Qualys QIDs found for {cve_id}",
                },
            )

        # Then search for detections with those QIDs
        start_time = time.time()

        params = {
            "action": "list",
            "truncation_limit": "1000",
            "output_format": "XML",
            "show_results": "1",
            "qids": ",".join(qids),
        }
        if ip_range:
            params["ips"] = ip_range

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/2.0/fo/asset/host/vm/detection/",
                    data=params,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    xml_text = await response.text()

                    if response.status == 200:
                        self._record_request(latency_ms, True)

                        data = self._parse_xml_response(xml_text)
                        detection_list = data.get("HOST_LIST_VM_DETECTION_OUTPUT", {})
                        response_data = detection_list.get("RESPONSE", {})
                        host_list = response_data.get("HOST_LIST", {}).get("HOST", [])

                        if isinstance(host_list, dict):
                            host_list = [host_list]

                        affected_hosts = []
                        for host in host_list:
                            if isinstance(host, dict):
                                affected_hosts.append(
                                    {
                                        "host_id": host.get("ID", ""),
                                        "ip": host.get("IP", ""),
                                        "hostname": host.get("DNS", ""),
                                        "os": host.get("OS", ""),
                                    }
                                )

                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "affected_hosts": affected_hosts,
                                "count": len(affected_hosts),
                                "cve_id": cve_id,
                                "qids": qids,
                            },
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=f"API error: {response.status}",
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
    # Scan Management
    # =========================================================================

    @require_enterprise_mode
    async def list_scans(
        self,
        scan_type: str = "On-Demand",
        state: str | None = None,
        limit: int = 100,
    ) -> ConnectorResult:
        """
        List vulnerability scans.

        Args:
            scan_type: Scan type (On-Demand, Scheduled, API)
            state: Filter by state (Running, Finished, etc.)
            limit: Maximum results
        """
        start_time = time.time()

        params = {
            "action": "list",
            "type": scan_type,
            "truncation_limit": str(limit),
        }
        if state:
            params["state"] = state

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/2.0/fo/scan/",
                    data=params,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    xml_text = await response.text()

                    if response.status == 200:
                        self._record_request(latency_ms, True)

                        data = self._parse_xml_response(xml_text)
                        scan_list = data.get("SCAN_LIST_OUTPUT", {})
                        response_data = scan_list.get("RESPONSE", {})
                        scans = response_data.get("SCAN_LIST", {}).get("SCAN", [])

                        if isinstance(scans, dict):
                            scans = [scans]

                        results = [
                            {
                                "ref": s.get("REF", ""),
                                "title": s.get("TITLE", ""),
                                "type": s.get("TYPE", ""),
                                "status": s.get("STATUS", {}).get("STATE", ""),
                                "target": s.get("TARGET", ""),
                                "launch_datetime": s.get("LAUNCH_DATETIME", ""),
                                "duration": s.get("DURATION", ""),
                            }
                            for s in scans
                            if isinstance(s, dict)
                        ]

                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={"scans": results, "count": len(results)},
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=f"API error: {response.status}",
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
    async def launch_scan(
        self,
        title: str,
        ip_range: str,
        option_profile: str | None = None,
        scanner_appliance: str | None = None,
    ) -> ConnectorResult:
        """
        Launch a vulnerability scan.

        Args:
            title: Scan title
            ip_range: IP range to scan
            option_profile: Option profile title
            scanner_appliance: Scanner appliance name
        """
        start_time = time.time()

        params = {
            "action": "launch",
            "scan_title": title,
            "ip": ip_range,
        }
        if option_profile:
            params["option_title"] = option_profile
        if scanner_appliance:
            params["iscanner_name"] = scanner_appliance

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/2.0/fo/scan/",
                    data=params,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    xml_text = await response.text()

                    if response.status == 200:
                        self._record_request(latency_ms, True)

                        data = self._parse_xml_response(xml_text)
                        simple_return = data.get("SIMPLE_RETURN", {})
                        response_data = simple_return.get("RESPONSE", {})

                        scan_ref = (
                            response_data.get("ITEM_LIST", {})
                            .get("ITEM", {})
                            .get("VALUE", "")
                        )

                        if scan_ref:
                            logger.info(f"Qualys scan launched: {scan_ref}")
                            return ConnectorResult(
                                success=True,
                                status_code=response.status,
                                data={
                                    "scan_ref": scan_ref,
                                    "title": title,
                                    "target": ip_range,
                                },
                                request_id=scan_ref,
                                latency_ms=latency_ms,
                            )
                        else:
                            return ConnectorResult(
                                success=False,
                                status_code=response.status,
                                error="Failed to launch scan",
                                latency_ms=latency_ms,
                            )
                    else:
                        self._record_request(latency_ms, False)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=f"API error: {response.status}",
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
        """Check if Qualys connector is healthy."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.base_url}/api/2.0/fo/scan/",
                    params={"action": "list", "truncation_limit": "1"},
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
