"""
Project Aura - Snyk Connector

Implements ADR-028 Phase 8: Enterprise Connector Expansion

Snyk REST API connector for:
- Vulnerability database lookup
- Project scanning
- Issue management
- Dependency analysis

SECURITY: Only available in ENTERPRISE or HYBRID mode.

Usage:
    >>> from src.services.snyk_connector import SnykConnector
    >>> snyk = SnykConnector(token="snyk-api-token", org_id="org-xxx")
    >>> vulns = await snyk.search_vulnerabilities("CVE-2024-1234")
"""

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


class SnykSeverity(Enum):
    """Snyk severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SnykExploitMaturity(Enum):
    """Snyk exploit maturity levels."""

    NO_KNOWN_EXPLOIT = "No Known Exploit"
    PROOF_OF_CONCEPT = "Proof of Concept"
    FUNCTIONAL = "Functional"
    MATURE = "Mature"


class SnykIssueType(Enum):
    """Snyk issue types."""

    VULN = "vuln"
    LICENSE = "license"
    CODE = "code"


class SnykProjectType(Enum):
    """Snyk project types."""

    NPM = "npm"
    MAVEN = "maven"
    GRADLE = "gradle"
    PIP = "pip"
    POETRY = "poetry"
    GOMODULES = "gomodules"
    NUGET = "nuget"
    RUBYGEMS = "rubygems"
    COMPOSER = "composer"
    DOCKER = "docker"
    APK = "apk"
    DEB = "deb"
    RPM = "rpm"
    COCOAPODS = "cocoapods"
    HEX = "hex"


@dataclass
class SnykVulnerability:
    """Snyk vulnerability details."""

    id: str
    title: str
    severity: SnykSeverity
    package_name: str
    version: str
    cve_ids: list[str] = field(default_factory=list)
    cwe_ids: list[str] = field(default_factory=list)
    cvss_score: float | None = None
    exploit_maturity: SnykExploitMaturity | None = None
    description: str = ""
    remediation: str = ""
    fixed_in: list[str] = field(default_factory=list)
    introduced_through: list[str] = field(default_factory=list)
    is_upgradable: bool = False
    is_patchable: bool = False
    publication_date: str | None = None
    disclosure_date: str | None = None
    url: str | None = None


@dataclass
class SnykProject:
    """Snyk project details."""

    id: str
    name: str
    project_type: SnykProjectType | None = None
    origin: str | None = None
    target_reference: str | None = None
    branch: str | None = None
    issue_counts: dict[str, int] = field(default_factory=dict)
    last_tested: str | None = None
    created: str | None = None


@dataclass
class SnykIssue:
    """Snyk issue (vulnerability or license issue)."""

    id: str
    issue_type: SnykIssueType
    package_name: str
    version: str
    severity: SnykSeverity
    title: str
    project_id: str
    introduced_through: list[str] = field(default_factory=list)
    is_fixed: bool = False
    fix_info: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Snyk Connector
# =============================================================================


class SnykConnector(ExternalToolConnector):
    """
    Snyk connector for vulnerability management.

    Supports:
    - Vulnerability database queries
    - Project scanning and monitoring
    - Issue management
    - Dependency analysis
    """

    API_V1_URL = "https://api.snyk.io/v1"
    API_REST_URL = "https://api.snyk.io/rest"

    def __init__(
        self,
        token: str,
        org_id: str | None = None,
        group_id: str | None = None,
        api_version: str = "2024-01-04",
        timeout_seconds: float = 30.0,
    ) -> None:
        """
        Initialize Snyk connector.

        Args:
            token: Snyk API token
            org_id: Organization ID (required for most operations)
            group_id: Group ID (for enterprise features)
            api_version: REST API version
            timeout_seconds: Request timeout
        """
        super().__init__("snyk", timeout_seconds)

        self._token = token
        self.org_id = org_id
        self.group_id = group_id
        self.api_version = api_version

    def _get_headers(self, use_rest: bool = False) -> dict[str, str]:
        """Get request headers."""
        headers = {
            "Authorization": f"token {self._token}",
            "Accept": "application/json",
        }

        if use_rest:
            headers["Content-Type"] = "application/vnd.api+json"

        return headers

    def _get_rest_url(self, path: str) -> str:
        """Build REST API URL with version."""
        return f"{self.API_REST_URL}/{path}?version={self.api_version}"

    # =========================================================================
    # Vulnerability Database
    # =========================================================================

    @require_enterprise_mode
    async def get_vulnerability(self, vuln_id: str) -> ConnectorResult:
        """
        Get vulnerability details by ID.

        Args:
            vuln_id: Vulnerability ID (e.g., SNYK-JS-LODASH-1234)
        """
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.API_V1_URL}/vuln/{vuln_id}",
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        vuln = SnykVulnerability(
                            id=data.get("id", vuln_id),
                            title=data.get("title", ""),
                            severity=SnykSeverity(data.get("severity", "medium")),
                            package_name=data.get("packageName", ""),
                            version=data.get("version", "*"),
                            cve_ids=data.get("identifiers", {}).get("CVE", []),
                            cwe_ids=data.get("identifiers", {}).get("CWE", []),
                            cvss_score=data.get("cvssScore"),
                            description=data.get("description", ""),
                            remediation=data.get("remediation", ""),
                            fixed_in=data.get("fixedIn", []),
                            is_upgradable=data.get("isUpgradable", False),
                            is_patchable=data.get("isPatchable", False),
                            publication_date=data.get("publicationTime"),
                            disclosure_date=data.get("disclosureTime"),
                            url=data.get("url"),
                        )
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "id": vuln.id,
                                "title": vuln.title,
                                "severity": vuln.severity.value,
                                "package_name": vuln.package_name,
                                "cve_ids": vuln.cve_ids,
                                "cwe_ids": vuln.cwe_ids,
                                "cvss_score": vuln.cvss_score,
                                "description": vuln.description,
                                "remediation": vuln.remediation,
                                "fixed_in": vuln.fixed_in,
                                "url": vuln.url,
                            },
                            request_id=vuln_id,
                            latency_ms=latency_ms,
                        )
                    else:
                        error_msg = data.get("message", str(data))
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
    async def search_vulnerabilities_by_cve(self, cve_id: str) -> ConnectorResult:
        """
        Search for Snyk vulnerabilities by CVE ID.

        Args:
            cve_id: CVE identifier (e.g., CVE-2024-1234)
        """
        start_time = time.time()

        # Use the issues endpoint to search by CVE
        params = {
            "type": "vuln",
            "identifier": cve_id,
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.API_V1_URL}/vuln/",
                    params=params,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        vulns = []
                        for v in data if isinstance(data, list) else [data]:
                            if v.get("identifiers", {}).get("CVE"):
                                if cve_id in v.get("identifiers", {}).get("CVE", []):
                                    vulns.append(
                                        {
                                            "id": v.get("id"),
                                            "title": v.get("title"),
                                            "severity": v.get("severity"),
                                            "package_name": v.get("packageName"),
                                            "cve_ids": v.get("identifiers", {}).get(
                                                "CVE", []
                                            ),
                                            "cvss_score": v.get("cvssScore"),
                                        }
                                    )
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "vulnerabilities": vulns,
                                "count": len(vulns),
                                "cve_id": cve_id,
                            },
                            latency_ms=latency_ms,
                        )
                    else:
                        error_msg = data.get("message", str(data))
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
    async def search_package_vulnerabilities(
        self,
        package_manager: str,
        package_name: str,
        version: str | None = None,
    ) -> ConnectorResult:
        """
        Search for vulnerabilities in a specific package.

        Args:
            package_manager: Package ecosystem (npm, maven, pip, etc.)
            package_name: Package name
            version: Specific version (optional)
        """
        start_time = time.time()

        # Encode package name for URL
        encoded_name = package_name.replace("/", "%2F")
        url = f"{self.API_V1_URL}/test/{package_manager}/{encoded_name}"
        if version:
            url += f"/{version}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    url,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        issues = data.get("issues", {}).get("vulnerabilities", [])
                        vulns = [
                            {
                                "id": v.get("id"),
                                "title": v.get("title"),
                                "severity": v.get("severity"),
                                "cvss_score": v.get("cvssScore"),
                                "cve_ids": v.get("identifiers", {}).get("CVE", []),
                                "fixed_in": v.get("fixedIn", []),
                                "is_upgradable": v.get("isUpgradable", False),
                            }
                            for v in issues
                        ]
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "package": package_name,
                                "version": version or "latest",
                                "vulnerabilities": vulns,
                                "vulnerability_count": len(vulns),
                                "ok": data.get("ok", False),
                            },
                            latency_ms=latency_ms,
                        )
                    else:
                        error_msg = data.get("message", str(data))
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

    # =========================================================================
    # Project Management
    # =========================================================================

    @require_enterprise_mode
    async def list_projects(
        self,
        target_reference: str | None = None,
        origin: str | None = None,
        limit: int = 100,
    ) -> ConnectorResult:
        """
        List projects in the organization.

        Args:
            target_reference: Filter by target (repo name, image, etc.)
            origin: Filter by origin (github, docker-hub, etc.)
            limit: Maximum results
        """
        if not self.org_id:
            return ConnectorResult(
                success=False,
                error="Organization ID required for project listing",
            )

        start_time = time.time()

        params: dict[str, Any] = {"limit": limit}
        if target_reference:
            params["targetReference"] = target_reference
        if origin:
            params["origin"] = origin

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.API_V1_URL}/org/{self.org_id}/projects",
                    params=params,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        projects = [
                            {
                                "id": p.get("id"),
                                "name": p.get("name"),
                                "type": p.get("type"),
                                "origin": p.get("origin"),
                                "target_reference": p.get("targetReference"),
                                "branch": p.get("branch"),
                                "issue_counts": p.get("issueCountsBySeverity", {}),
                                "last_tested": p.get("lastTestedDate"),
                            }
                            for p in data.get("projects", [])
                        ]
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={"projects": projects, "count": len(projects)},
                            latency_ms=latency_ms,
                        )
                    else:
                        error_msg = data.get("message", str(data))
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
    async def get_project_issues(
        self,
        project_id: str,
        severity: SnykSeverity | None = None,
        issue_type: SnykIssueType | None = None,
        exploitable: bool | None = None,
    ) -> ConnectorResult:
        """
        Get issues for a specific project.

        Args:
            project_id: Project ID
            severity: Filter by severity
            issue_type: Filter by type (vuln, license, code)
            exploitable: Filter by exploitability
        """
        if not self.org_id:
            return ConnectorResult(
                success=False,
                error="Organization ID required for project issues",
            )

        start_time = time.time()

        filters = {}
        if severity:
            filters["severity"] = [severity.value]
        if issue_type:
            filters["types"] = [issue_type.value]
        if exploitable is not None:
            filters["exploitMaturity"] = (
                ["mature", "proof-of-concept"] if exploitable else ["no-known-exploit"]
            )

        payload = {"filters": filters} if filters else {}

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.API_V1_URL}/org/{self.org_id}/project/{project_id}/aggregated-issues",
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        issues = [
                            {
                                "id": i.get("id"),
                                "issue_type": i.get("issueType"),
                                "package_name": i.get("pkgName"),
                                "version": i.get("pkgVersions", ["*"])[0],
                                "severity": i.get("severity"),
                                "title": i.get("title"),
                                "introduced_through": i.get("introducedThrough", []),
                                "is_fixed": i.get("isFixed", False),
                                "cvss_score": i.get("issueData", {}).get("cvssScore"),
                                "cve_ids": i.get("issueData", {})
                                .get("identifiers", {})
                                .get("CVE", []),
                            }
                            for i in data.get("issues", [])
                        ]

                        # Group by severity
                        by_severity = {
                            "critical": sum(
                                1 for i in issues if i["severity"] == "critical"
                            ),
                            "high": sum(1 for i in issues if i["severity"] == "high"),
                            "medium": sum(
                                1 for i in issues if i["severity"] == "medium"
                            ),
                            "low": sum(1 for i in issues if i["severity"] == "low"),
                        }

                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "issues": issues,
                                "count": len(issues),
                                "by_severity": by_severity,
                            },
                            request_id=project_id,
                            latency_ms=latency_ms,
                        )
                    else:
                        error_msg = data.get("message", str(data))
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
    async def get_project_dependencies(self, project_id: str) -> ConnectorResult:
        """
        Get dependency tree for a project.

        Args:
            project_id: Project ID
        """
        if not self.org_id:
            return ConnectorResult(
                success=False,
                error="Organization ID required for dependencies",
            )

        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.API_V1_URL}/org/{self.org_id}/project/{project_id}/dep-graph",
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        dep_graph = data.get("depGraph", {})
                        pkgs = dep_graph.get("pkgs", [])

                        dependencies = [
                            {
                                "id": p.get("id"),
                                "name": p.get("info", {}).get("name"),
                                "version": p.get("info", {}).get("version"),
                            }
                            for p in pkgs
                        ]

                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "dependencies": dependencies,
                                "count": len(dependencies),
                                "schema_version": dep_graph.get("schemaVersion"),
                            },
                            request_id=project_id,
                            latency_ms=latency_ms,
                        )
                    else:
                        error_msg = data.get("message", str(data))
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

    # =========================================================================
    # Issue Management
    # =========================================================================

    @require_enterprise_mode
    async def ignore_issue(
        self,
        project_id: str,
        issue_id: str,
        reason: str,
        reason_type: str = "wont-fix",
        expires_at: str | None = None,
    ) -> ConnectorResult:
        """
        Ignore an issue in a project.

        Args:
            project_id: Project ID
            issue_id: Issue ID
            reason: Reason for ignoring
            reason_type: not-vulnerable, wont-fix, temporary-ignore
            expires_at: Expiration date for the ignore (ISO format)
        """
        if not self.org_id:
            return ConnectorResult(
                success=False,
                error="Organization ID required for ignoring issues",
            )

        start_time = time.time()

        payload = {
            "reason": reason,
            "reasonType": reason_type,
        }
        if expires_at:
            payload["expires"] = expires_at

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.API_V1_URL}/org/{self.org_id}/project/{project_id}/ignore/{issue_id}",
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status in (200, 201)
                    self._record_request(latency_ms, success)

                    if success:
                        logger.info(f"Snyk issue ignored: {issue_id}")
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data=data,
                            request_id=issue_id,
                            latency_ms=latency_ms,
                        )
                    else:
                        error_msg = data.get("message", str(data))
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

    # =========================================================================
    # Reporting
    # =========================================================================

    @require_enterprise_mode
    async def get_org_summary(self) -> ConnectorResult:
        """
        Get vulnerability summary for the organization.
        """
        if not self.org_id:
            return ConnectorResult(
                success=False,
                error="Organization ID required for org summary",
            )

        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.API_V1_URL}/org/{self.org_id}",
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 200
                    self._record_request(latency_ms, success)

                    if success:
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data={
                                "name": data.get("name"),
                                "slug": data.get("slug"),
                                "url": data.get("url"),
                                "created": data.get("created"),
                            },
                            latency_ms=latency_ms,
                        )
                    else:
                        error_msg = data.get("message", str(data))
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
    async def get_vulnerability_report(
        self,
        severity: SnykSeverity | None = None,
        exploitable_only: bool = False,
    ) -> ConnectorResult:
        """
        Generate a vulnerability report across all projects.

        Args:
            severity: Filter by minimum severity
            exploitable_only: Only include exploitable vulnerabilities
        """
        # List all projects
        projects_result: ConnectorResult = await self.list_projects()
        if not projects_result.success:
            return projects_result

        all_issues = []
        summary: dict[str, Any] = {
            "total_projects": 0,
            "projects_with_issues": 0,
            "total_vulnerabilities": 0,
            "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "fixable": 0,
        }

        for project in projects_result.data.get("projects", []):
            summary["total_projects"] += 1
            project_id = project.get("id")

            # Get issues for each project
            issues_result = await self.get_project_issues(
                project_id=project_id,
                severity=severity,
            )

            if issues_result.success:
                issues = issues_result.data.get("issues", [])
                if issues:
                    summary["projects_with_issues"] += 1

                for issue in issues:
                    if exploitable_only:
                        # Skip non-exploitable issues
                        if issue.get("exploit_maturity") in [
                            "no-known-exploit",
                            None,
                        ]:
                            continue

                    summary["total_vulnerabilities"] += 1
                    sev = issue.get("severity", "medium")
                    if sev in summary["by_severity"]:
                        summary["by_severity"][sev] += 1
                    if issue.get("is_fixed"):
                        summary["fixable"] += 1

                    all_issues.append(
                        {
                            **issue,
                            "project_name": project.get("name"),
                            "project_id": project_id,
                        }
                    )

        return ConnectorResult(
            success=True,
            data={
                "summary": summary,
                "issues": all_issues,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            latency_ms=0,  # Aggregate operation
        )

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> bool:
        """Check if Snyk connector is healthy."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Use the user endpoint to validate token
                async with session.get(
                    f"{self.API_V1_URL}/user/me",
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
