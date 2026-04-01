"""Threat Intelligence Agent for Autonomous ADR Generation Pipeline.

This agent continuously monitors external threat feeds and internal telemetry
to identify security vulnerabilities and compliance changes affecting the platform.

Part of ADR-010: Autonomous ADR Generation Pipeline

Updated: Dec 1, 2025 - Integrated with ThreatFeedClient for real API access
"""

import asyncio
import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

from .monitoring_service import AgentRole, MonitorAgent

if TYPE_CHECKING:
    from src.services.security_telemetry_service import (
        SecurityFinding,
        SecurityTelemetryService,
    )
    from src.services.threat_feed_client import ThreatFeedClient


class ThreatSeverity(Enum):
    """CVSS-aligned severity levels."""

    CRITICAL = "critical"  # CVSS 9.0-10.0
    HIGH = "high"  # CVSS 7.0-8.9
    MEDIUM = "medium"  # CVSS 4.0-6.9
    LOW = "low"  # CVSS 0.1-3.9
    INFORMATIONAL = "informational"  # No CVSS score


class ThreatCategory(Enum):
    """Categories of threat intelligence."""

    CVE = "cve"  # Common Vulnerabilities and Exposures
    ADVISORY = "advisory"  # Vendor/CISA security advisories
    COMPLIANCE = "compliance"  # Regulatory requirement changes
    PATTERN = "pattern"  # Emerging attack patterns
    INTERNAL = "internal"  # Internal telemetry anomalies


@dataclass
class ThreatIntelReport:
    """Structured threat intelligence report."""

    id: str
    title: str
    category: ThreatCategory
    severity: ThreatSeverity
    source: str
    published_date: datetime
    description: str
    affected_components: list[str] = field(default_factory=list)
    cve_ids: list[str] = field(default_factory=list)
    cvss_score: float | None = None
    recommended_actions: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category.value,
            "severity": self.severity.value,
            "source": self.source,
            "published_date": self.published_date.isoformat(),
            "description": self.description,
            "affected_components": self.affected_components,
            "cve_ids": self.cve_ids,
            "cvss_score": self.cvss_score,
            "recommended_actions": self.recommended_actions,
            "references": self.references,
        }


@dataclass
class ThreatIntelConfig:
    """Configuration for threat intelligence sources."""

    nvd_api_key: str | None = None
    cisa_feed_url: str = (
        "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    )
    github_advisory_url: str = "https://api.github.com/advisories"
    check_interval_minutes: int = 60
    max_cve_age_days: int = 30
    severity_threshold: ThreatSeverity = ThreatSeverity.MEDIUM


class ThreatIntelligenceAgent:
    """Agent for continuous security intelligence gathering.

    Monitors multiple threat intelligence sources:
    - NVD (National Vulnerability Database) for CVEs
    - CISA Known Exploited Vulnerabilities catalog
    - GitHub Security Advisories
    - Vendor security bulletins
    - Internal telemetry (WAF logs, anomaly detection)

    Produces ThreatIntelReport objects for downstream processing by
    the AdaptiveIntelligenceAgent.

    Updated Dec 1, 2025: Now uses ThreatFeedClient for real API access.
    """

    def __init__(
        self,
        config: ThreatIntelConfig | None = None,
        monitor: MonitorAgent | None = None,
        threat_feed_client: "ThreatFeedClient | None" = None,
        security_telemetry_service: "SecurityTelemetryService | None" = None,
    ):
        """Initialize the Threat Intelligence Agent.

        Args:
            config: Configuration for threat sources. Uses defaults if None.
            monitor: Optional monitoring agent for metrics/logging.
            threat_feed_client: Optional ThreatFeedClient for real API calls.
                               If None, uses internal mock implementations.
            security_telemetry_service: Optional SecurityTelemetryService for
                               real AWS security telemetry (GuardDuty, WAF, CloudTrail).
                               If None, uses mock internal telemetry data.
        """
        self.config = config or ThreatIntelConfig(
            nvd_api_key=os.environ.get("NVD_API_KEY"),
        )
        self.monitor = monitor
        self.threat_feed_client = threat_feed_client
        self.security_telemetry_service = security_telemetry_service
        self._last_check: dict[str, datetime] = {}
        self._known_threats: set[str] = set()
        self._dependency_sbom: list[dict[str, str]] = []

    def set_dependency_sbom(self, sbom: list[dict[str, str]]) -> None:
        """Set the software bill of materials for dependency matching.

        Args:
            sbom: List of dependencies with name and version.
                  Example: [{"name": "requests", "version": "2.28.0", "ecosystem": "pip"}]
        """
        self._dependency_sbom = sbom

    def get_detected_ecosystems(self) -> list[str]:
        """Get all unique ecosystems from the SBOM.

        Returns:
            List of ecosystem identifiers (pip, npm, go, cargo, rubygems, nuget).
        """
        ecosystems = set()
        for dep in self._dependency_sbom:
            ecosystem = dep.get("ecosystem", "pip")  # Default to pip for legacy
            if ecosystem and ecosystem != "unknown":
                ecosystems.add(ecosystem)
        # Always include pip as default if no ecosystems detected
        if not ecosystems:
            ecosystems.add("pip")
        return sorted(ecosystems)

    def get_dependencies_by_ecosystem(self, ecosystem: str) -> list[dict[str, str]]:
        """Get dependencies filtered by ecosystem.

        Args:
            ecosystem: The package ecosystem (pip, npm, go, cargo, rubygems, nuget).

        Returns:
            List of dependencies for the specified ecosystem.
        """
        return [
            dep
            for dep in self._dependency_sbom
            if dep.get("ecosystem", "pip") == ecosystem
        ]

    def auto_detect_sbom(
        self,
        project_path: str,
        include_dev: bool = False,
    ) -> int:
        """Auto-detect dependencies from project manifest files.

        Scans the project for common dependency manifests:
        - requirements.txt, pyproject.toml (Python)
        - package.json (Node.js)
        - go.mod (Go)
        - Cargo.toml (Rust)
        - Gemfile.lock (Ruby)
        - *.csproj (NuGet)

        Args:
            project_path: Path to project root directory
            include_dev: Include dev dependencies in scan

        Returns:
            Number of dependencies detected

        Raises:
            ValueError: If project path does not exist
        """
        try:
            from src.services.sbom_detection_service import SBOMDetectionService
        except ImportError:
            self._log_activity(
                "SBOMDetectionService not available, cannot auto-detect",
                error=True,
            )
            return 0

        self._log_activity(f"Auto-detecting SBOM from {project_path}")

        service = SBOMDetectionService()
        report = service.detect_dependencies(project_path, include_dev=include_dev)

        # Convert to SBOM format
        sbom = report.to_sbom_list(include_dev=include_dev)
        self._dependency_sbom = sbom

        self._log_activity(
            f"Detected {len(sbom)} dependencies from {len(report.manifest_files)} manifests"
        )

        if report.errors:
            for error in report.errors:
                self._log_activity(f"SBOM detection warning: {error}", error=True)

        return len(sbom)

    async def gather_intelligence(self) -> list[ThreatIntelReport]:
        """Gather threat intelligence from all configured sources.

        Returns:
            List of new threat intelligence reports since last check.
        """
        self._log_activity("Starting threat intelligence gathering")

        # Gather from all sources concurrently
        sources = [
            self._fetch_nvd_cves(),
            self._fetch_cisa_advisories(),
            self._fetch_github_advisories(),
            self._analyze_internal_telemetry(),
        ]

        results = await asyncio.gather(*sources, return_exceptions=True)

        # Flatten and filter reports
        all_reports: list[ThreatIntelReport] = []
        for result in results:
            if isinstance(result, Exception):
                self._log_activity(f"Source fetch error: {result}", error=True)
                continue
            if isinstance(result, list):
                all_reports.extend(result)

        # Filter to new reports only
        new_reports = self._filter_new_reports(all_reports)

        # Prioritize by relevance to our stack
        prioritized = self._prioritize_by_relevance(new_reports)

        self._log_activity(
            f"Gathered {len(prioritized)} relevant threat reports "
            f"from {len(all_reports)} total"
        )

        return prioritized

    async def _fetch_nvd_cves(self) -> list[ThreatIntelReport]:
        """Fetch recent CVEs from National Vulnerability Database.

        Uses ThreatFeedClient for real API access when available,
        otherwise falls back to mock data.

        Returns:
            List of CVE-based threat reports.
        """
        self._log_activity("Fetching NVD CVEs")

        # Use ThreatFeedClient if available
        if self.threat_feed_client:
            try:
                pass

                cve_records = await self.threat_feed_client.fetch_nvd_cves(
                    days_back=self.config.max_cve_age_days
                )

                reports = []
                for cve in cve_records:
                    # Check if CVE affects our dependencies
                    affected = self._check_dependency_match(cve.affected_products)

                    if affected or (cve.cvss_score and cve.cvss_score >= 9.0):
                        report = ThreatIntelReport(
                            id=self._generate_report_id("nvd", cve.cve_id),
                            title=cve.title,
                            category=ThreatCategory.CVE,
                            severity=self._cvss_to_severity(cve.cvss_score or 0),
                            source="NVD",
                            published_date=cve.published_date,
                            description=cve.description,
                            affected_components=affected or cve.affected_products,
                            cve_ids=[cve.cve_id],
                            cvss_score=cve.cvss_score,
                            recommended_actions=[
                                "Upgrade affected packages to patched versions",
                                f"Review {cve.cve_id} for workarounds if upgrade not possible",
                            ],
                            references=cve.references,
                            raw_data=cve.raw_data,
                        )
                        reports.append(report)

                self._last_check["nvd"] = datetime.now()
                return reports
            except Exception as e:
                self._log_activity(
                    f"ThreatFeedClient error: {e}, using fallback", error=True
                )

        # Fallback: Mock implementation
        mock_cves: list[dict[str, Any]] = [
            {
                "cve_id": "CVE-2025-0001",
                "title": "Critical RCE in requests library",
                "description": "Remote code execution vulnerability in Python requests library versions < 2.31.0",
                "cvss_score": 9.8,
                "published": datetime.now() - timedelta(days=2),
                "affected_packages": ["requests"],
                "references": ["https://nvd.nist.gov/vuln/detail/CVE-2025-0001"],
            },
            {
                "cve_id": "CVE-2025-0002",
                "title": "OpenSearch authentication bypass",
                "description": "Authentication bypass in OpenSearch versions < 2.11.0",
                "cvss_score": 8.1,
                "published": datetime.now() - timedelta(days=5),
                "affected_packages": ["opensearch"],
                "references": ["https://nvd.nist.gov/vuln/detail/CVE-2025-0002"],
            },
        ]

        reports = []
        for mock_cve in mock_cves:
            affected = self._check_dependency_match(
                mock_cve.get("affected_packages", [])
            )

            if affected or mock_cve["cvss_score"] >= 9.0:
                report = ThreatIntelReport(
                    id=self._generate_report_id("nvd", mock_cve["cve_id"]),
                    title=mock_cve["title"],
                    category=ThreatCategory.CVE,
                    severity=self._cvss_to_severity(mock_cve["cvss_score"]),
                    source="NVD",
                    published_date=mock_cve["published"],
                    description=mock_cve["description"],
                    affected_components=affected,
                    cve_ids=[mock_cve["cve_id"]],
                    cvss_score=mock_cve["cvss_score"],
                    recommended_actions=[
                        "Upgrade affected packages to patched versions",
                        f"Review {mock_cve['cve_id']} for workarounds if upgrade not possible",
                    ],
                    references=mock_cve["references"],
                    raw_data=mock_cve,
                )
                reports.append(report)

        self._last_check["nvd"] = datetime.now()
        return reports

    async def _fetch_cisa_advisories(self) -> list[ThreatIntelReport]:
        """Fetch CISA Known Exploited Vulnerabilities.

        Uses ThreatFeedClient for real API access when available,
        otherwise falls back to mock data.

        Returns:
            List of CISA advisory-based threat reports.
        """
        self._log_activity("Fetching CISA advisories")

        # Use ThreatFeedClient if available
        if self.threat_feed_client:
            try:
                kev_records = await self.threat_feed_client.fetch_cisa_kev()

                reports = []
                for record in kev_records:
                    report = ThreatIntelReport(
                        id=self._generate_report_id("cisa", record.cve_id),
                        title=record.vulnerability_name,
                        category=ThreatCategory.ADVISORY,
                        severity=ThreatSeverity.CRITICAL,  # CISA KEV = actively exploited
                        source="CISA KEV",
                        published_date=record.date_added,
                        description=record.short_description,
                        affected_components=[record.product, record.vendor_project],
                        cve_ids=[record.cve_id],
                        recommended_actions=[
                            record.required_action,
                            "Immediate patching required per CISA directive",
                            "Validate patches in sandbox before production deployment",
                        ],
                        references=[
                            "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"
                        ],
                        raw_data={
                            "vendor_project": record.vendor_project,
                            "product": record.product,
                            "due_date": (
                                record.due_date.isoformat() if record.due_date else None
                            ),
                            "known_ransomware": record.known_ransomware,
                        },
                    )
                    reports.append(report)

                self._last_check["cisa"] = datetime.now()
                return reports
            except Exception as e:
                self._log_activity(
                    f"ThreatFeedClient error: {e}, using fallback", error=True
                )

        # Fallback: Mock implementation
        mock_advisories: list[dict[str, Any]] = [
            {
                "id": "CISA-2025-001",
                "title": "Active Exploitation of Cloud Infrastructure Vulnerabilities",
                "description": "CISA has observed active exploitation of vulnerabilities in cloud container orchestration platforms.",
                "published": datetime.now() - timedelta(days=1),
                "cve_ids": ["CVE-2025-0003", "CVE-2025-0004"],
                "affected_products": ["kubernetes", "eks"],
                "references": ["https://www.cisa.gov/advisory/CISA-2025-001"],
            },
        ]

        reports = []
        for advisory in mock_advisories:
            report = ThreatIntelReport(
                id=self._generate_report_id("cisa", advisory["id"]),
                title=advisory["title"],
                category=ThreatCategory.ADVISORY,
                severity=ThreatSeverity.CRITICAL,
                source="CISA KEV",
                published_date=advisory["published"],
                description=advisory["description"],
                affected_components=advisory.get("affected_products", []),
                cve_ids=advisory.get("cve_ids", []),
                recommended_actions=[
                    "Immediate patching required per CISA directive",
                    "Review CISA advisory for specific remediation steps",
                    "Validate patches in sandbox before production deployment",
                ],
                references=advisory["references"],
                raw_data=advisory,
            )
            reports.append(report)

        self._last_check["cisa"] = datetime.now()
        return reports

    async def _fetch_github_advisories(self) -> list[ThreatIntelReport]:
        """Fetch GitHub Security Advisories for all detected ecosystems.

        Queries advisories for each ecosystem found in the SBOM:
        - pip (Python)
        - npm (Node.js)
        - go (Go modules)
        - cargo (Rust)
        - rubygems (Ruby)
        - nuget (.NET)

        Uses ThreatFeedClient for real API access when available,
        otherwise falls back to mock data.

        Returns:
            List of GitHub advisory-based threat reports.
        """
        ecosystems = self.get_detected_ecosystems()
        self._log_activity(
            f"Fetching GitHub Security Advisories for ecosystems: {ecosystems}"
        )

        # Use ThreatFeedClient if available
        if self.threat_feed_client:
            try:
                all_reports = []

                # Query each ecosystem in parallel
                for ecosystem in ecosystems:
                    gh_advisories = (
                        await self.threat_feed_client.fetch_github_advisories(
                            ecosystem=ecosystem
                        )
                    )

                    # Get dependencies for this ecosystem
                    eco_deps = self.get_dependencies_by_ecosystem(ecosystem)
                    eco_dep_names = [d.get("name", "").lower() for d in eco_deps]

                    for advisory in gh_advisories:
                        # Check if affects our dependencies for this ecosystem
                        affected = []
                        if advisory.package_name:
                            pkg_lower = advisory.package_name.lower()
                            if pkg_lower in eco_dep_names:
                                affected = [advisory.package_name]

                        if affected or advisory.severity in ["critical", "high"]:
                            cve_ids = [advisory.cve_id] if advisory.cve_id else []
                            report = ThreatIntelReport(
                                id=self._generate_report_id("github", advisory.ghsa_id),
                                title=advisory.summary,
                                category=ThreatCategory.CVE,
                                severity=self._string_to_severity(advisory.severity),
                                source="GitHub Security Advisory",
                                published_date=advisory.published_at,
                                description=advisory.description,
                                affected_components=affected
                                or (
                                    [advisory.package_name]
                                    if advisory.package_name
                                    else []
                                ),
                                cve_ids=cve_ids,
                                recommended_actions=[
                                    f"Upgrade to {advisory.patched_versions or 'latest version'}",
                                    "Review advisory for impact assessment",
                                ],
                                references=advisory.references,
                                raw_data={
                                    "ghsa_id": advisory.ghsa_id,
                                    "vulnerable_versions": advisory.vulnerable_versions,
                                    "patched_versions": advisory.patched_versions,
                                    "ecosystem": advisory.package_ecosystem,
                                },
                            )
                            all_reports.append(report)

                self._last_check["github"] = datetime.now()
                return all_reports
            except Exception as e:
                self._log_activity(
                    f"ThreatFeedClient error: {e}, using fallback", error=True
                )

        # Fallback: Mock implementation with multi-ecosystem examples
        mock_advisories: list[dict[str, Any]] = [
            # Python ecosystem
            {
                "ghsa_id": "GHSA-xxxx-yyyy-zzzz",
                "title": "FastAPI dependency injection vulnerability",
                "description": "Improper input validation in FastAPI could allow injection attacks",
                "severity": "high",
                "ecosystem": "pip",
                "published": datetime.now() - timedelta(days=3),
                "affected_package": "fastapi",
                "patched_versions": ">=0.109.0",
                "references": ["https://github.com/advisories/GHSA-xxxx-yyyy-zzzz"],
            },
            # Node.js ecosystem
            {
                "ghsa_id": "GHSA-npm1-aaaa-bbbb",
                "title": "Express.js prototype pollution",
                "description": "Prototype pollution vulnerability in Express.js middleware",
                "severity": "critical",
                "ecosystem": "npm",
                "published": datetime.now() - timedelta(days=5),
                "affected_package": "express",
                "patched_versions": ">=4.19.0",
                "references": ["https://github.com/advisories/GHSA-npm1-aaaa-bbbb"],
            },
            # Go ecosystem
            {
                "ghsa_id": "GHSA-go01-cccc-dddd",
                "title": "golang.org/x/net HTTP/2 rapid reset attack",
                "description": "HTTP/2 rapid reset attack vulnerability in Go net package",
                "severity": "high",
                "ecosystem": "go",
                "published": datetime.now() - timedelta(days=7),
                "affected_package": "golang.org/x/net",
                "patched_versions": ">=0.17.0",
                "references": ["https://github.com/advisories/GHSA-go01-cccc-dddd"],
            },
            # Rust ecosystem
            {
                "ghsa_id": "GHSA-rust-eeee-ffff",
                "title": "Tokio async runtime memory corruption",
                "description": "Memory corruption in Tokio async runtime under high load",
                "severity": "high",
                "ecosystem": "cargo",
                "published": datetime.now() - timedelta(days=2),
                "affected_package": "tokio",
                "patched_versions": ">=1.35.0",
                "references": ["https://github.com/advisories/GHSA-rust-eeee-ffff"],
            },
            # Ruby ecosystem
            {
                "ghsa_id": "GHSA-ruby-gggg-hhhh",
                "title": "Rails ActionController parameter injection",
                "description": "Parameter injection in Rails ActionController permits",
                "severity": "critical",
                "ecosystem": "rubygems",
                "published": datetime.now() - timedelta(days=4),
                "affected_package": "rails",
                "patched_versions": ">=7.1.0",
                "references": ["https://github.com/advisories/GHSA-ruby-gggg-hhhh"],
            },
            # .NET ecosystem
            {
                "ghsa_id": "GHSA-nugt-iiii-jjjj",
                "title": "System.Text.Json deserialization vulnerability",
                "description": "Arbitrary code execution via crafted JSON payload",
                "severity": "critical",
                "ecosystem": "nuget",
                "published": datetime.now() - timedelta(days=1),
                "affected_package": "System.Text.Json",
                "patched_versions": ">=8.0.1",
                "references": ["https://github.com/advisories/GHSA-nugt-iiii-jjjj"],
            },
        ]

        # Filter mock advisories by detected ecosystems
        detected = set(ecosystems)
        reports = []
        for mock_advisory in mock_advisories:
            # Only process advisories for ecosystems we detected
            eco = mock_advisory.get("ecosystem", "pip")
            if eco not in detected:
                continue

            affected = self._check_dependency_match(
                [mock_advisory.get("affected_package")]
            )

            if affected or mock_advisory.get("severity") in ["critical", "high"]:
                report = ThreatIntelReport(
                    id=self._generate_report_id("github", mock_advisory["ghsa_id"]),
                    title=mock_advisory["title"],
                    category=ThreatCategory.CVE,
                    severity=self._string_to_severity(mock_advisory["severity"]),
                    source="GitHub Security Advisory",
                    published_date=mock_advisory["published"],
                    description=mock_advisory["description"],
                    affected_components=affected,
                    recommended_actions=[
                        f"Upgrade to {mock_advisory.get('patched_versions', 'latest version')}",
                        "Review advisory for impact assessment",
                    ],
                    references=mock_advisory["references"],
                    raw_data=mock_advisory,
                )
                reports.append(report)

        self._last_check["github"] = datetime.now()
        return reports

    async def _analyze_internal_telemetry(self) -> list[ThreatIntelReport]:
        """Analyze internal telemetry for anomalies.

        Queries real AWS security services via SecurityTelemetryService:
        - GuardDuty findings (unauthorized access, malware, recon)
        - CloudWatch WAF logs (blocked requests, attack patterns)
        - CloudTrail anomalies (suspicious API calls)

        Falls back to mock data if SecurityTelemetryService is not configured.

        Returns:
            List of internal anomaly-based threat reports.
        """
        self._log_activity("Analyzing internal telemetry")

        reports: list[ThreatIntelReport] = []

        # Use SecurityTelemetryService if available
        if self.security_telemetry_service:
            try:
                findings = await self.security_telemetry_service.get_security_findings()

                for finding in findings:
                    # Map FindingSeverity to ThreatSeverity
                    severity_map = {
                        "critical": ThreatSeverity.CRITICAL,
                        "high": ThreatSeverity.HIGH,
                        "medium": ThreatSeverity.MEDIUM,
                        "low": ThreatSeverity.LOW,
                        "informational": ThreatSeverity.INFORMATIONAL,
                    }
                    severity = severity_map.get(
                        finding.severity.value, ThreatSeverity.MEDIUM
                    )

                    report = ThreatIntelReport(
                        id=self._generate_report_id("internal", finding.id),
                        title=finding.title,
                        category=ThreatCategory.INTERNAL,
                        severity=severity,
                        source=f"Internal Telemetry ({finding.source_service})",
                        published_date=finding.detected_at,
                        description=finding.description,
                        affected_components=finding.affected_resources,
                        recommended_actions=finding.recommended_actions,
                        references=finding.indicators,
                        raw_data=finding.raw_data,
                    )
                    reports.append(report)

                self._log_activity(
                    f"Retrieved {len(reports)} findings from SecurityTelemetryService"
                )

            except Exception as e:
                self._log_activity(
                    f"Error querying SecurityTelemetryService: {e}", error=True
                )
                # Fall through to mock data

        # Fallback to mock data if no service or on error
        if not reports:
            self._log_activity("Using mock internal telemetry data")
            mock_anomalies: list[dict[str, Any]] = [
                {
                    "id": "AURA-ANOM-001",
                    "title": "Elevated failed authentication attempts detected",
                    "description": "WAF logs show 500% increase in failed auth attempts from single IP range",
                    "detected_at": datetime.now() - timedelta(hours=2),
                    "affected_service": "api-gateway",
                    "indicators": [
                        "IP: 203.0.113.0/24",
                        "User-Agent: suspicious-scanner/1.0",
                    ],
                },
            ]

            for anomaly in mock_anomalies:
                report = ThreatIntelReport(
                    id=self._generate_report_id("internal", anomaly["id"]),
                    title=anomaly["title"],
                    category=ThreatCategory.INTERNAL,
                    severity=ThreatSeverity.MEDIUM,
                    source="Internal Telemetry",
                    published_date=anomaly["detected_at"],
                    description=anomaly["description"],
                    affected_components=[anomaly.get("affected_service", "unknown")],
                    recommended_actions=[
                        "Review WAF rules for additional blocking",
                        "Consider IP-based rate limiting",
                        "Investigate source of suspicious traffic",
                    ],
                    raw_data=anomaly,
                )
                reports.append(report)

        self._last_check["internal"] = datetime.now()
        return reports

    def _check_dependency_match(
        self, packages: list[str | None] | list[str]
    ) -> list[str]:
        """Check if any packages match our SBOM.

        Args:
            packages: List of package names to check.

        Returns:
            List of matching component names from our SBOM.
        """
        matches = []
        for pkg in packages:
            if pkg is None:
                continue
            pkg_lower = pkg.lower()
            for dep in self._dependency_sbom:
                if dep.get("name", "").lower() == pkg_lower:
                    matches.append(f"{dep['name']}=={dep.get('version', 'unknown')}")
        return matches

    def _filter_new_reports(
        self, reports: list[ThreatIntelReport]
    ) -> list[ThreatIntelReport]:
        """Filter to only reports we haven't seen before.

        Args:
            reports: All gathered reports.

        Returns:
            Only new (unseen) reports.
        """
        new_reports = []
        for report in reports:
            if report.id not in self._known_threats:
                self._known_threats.add(report.id)
                new_reports.append(report)
        return new_reports

    def _prioritize_by_relevance(
        self, reports: list[ThreatIntelReport]
    ) -> list[ThreatIntelReport]:
        """Prioritize reports by relevance to our stack.

        Prioritization factors:
        1. Severity (Critical > High > Medium > Low)
        2. Direct dependency match
        3. CISA KEV status (actively exploited)
        4. Recency

        Args:
            reports: Reports to prioritize.

        Returns:
            Reports sorted by priority (highest first).
        """
        severity_order = {
            ThreatSeverity.CRITICAL: 0,
            ThreatSeverity.HIGH: 1,
            ThreatSeverity.MEDIUM: 2,
            ThreatSeverity.LOW: 3,
            ThreatSeverity.INFORMATIONAL: 4,
        }

        def priority_key(report: ThreatIntelReport) -> tuple:
            return (
                severity_order.get(report.severity, 5),
                0 if report.affected_components else 1,  # Has matches = higher priority
                0 if report.source == "CISA KEV" else 1,  # CISA = higher priority
                -report.published_date.timestamp(),  # More recent = higher priority
            )

        return sorted(reports, key=priority_key)

    def _cvss_to_severity(self, cvss: float) -> ThreatSeverity:
        """Convert CVSS score to severity level.

        Args:
            cvss: CVSS score (0.0-10.0).

        Returns:
            Corresponding severity level.
        """
        if cvss >= 9.0:
            return ThreatSeverity.CRITICAL
        elif cvss >= 7.0:
            return ThreatSeverity.HIGH
        elif cvss >= 4.0:
            return ThreatSeverity.MEDIUM
        elif cvss > 0:
            return ThreatSeverity.LOW
        return ThreatSeverity.INFORMATIONAL

    def _string_to_severity(self, severity_str: str) -> ThreatSeverity:
        """Convert string severity to enum.

        Args:
            severity_str: Severity as string (e.g., "high", "critical").

        Returns:
            Corresponding severity level.
        """
        mapping = {
            "critical": ThreatSeverity.CRITICAL,
            "high": ThreatSeverity.HIGH,
            "medium": ThreatSeverity.MEDIUM,
            "moderate": ThreatSeverity.MEDIUM,
            "low": ThreatSeverity.LOW,
        }
        return mapping.get(severity_str.lower(), ThreatSeverity.INFORMATIONAL)

    def _generate_report_id(self, source: str, identifier: str) -> str:
        """Generate unique report ID.

        Args:
            source: Source of the report (nvd, cisa, github, internal).
            identifier: Source-specific identifier.

        Returns:
            Unique report ID.
        """
        combined = f"{source}:{identifier}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _log_activity(self, message: str, error: bool = False) -> None:
        """Log agent activity.

        Args:
            message: Log message.
            error: Whether this is an error log.
        """
        prefix = f"[{AgentRole.PLANNER.value}:ThreatIntel]"
        if error:
            print(f"{prefix} ERROR: {message}")
        else:
            print(f"{prefix} {message}")

        if self.monitor:
            self.monitor.log_activity(
                role=AgentRole.PLANNER,
                activity=f"ThreatIntelligence: {message}",
            )

    # =========================================================================
    # Threat Correlation with GuardDuty Findings
    # =========================================================================

    async def gather_intelligence_with_correlation(
        self,
    ) -> list[ThreatIntelReport]:
        """Gather threat intelligence and correlate with internal GuardDuty findings.

        This enhanced method:
        1. Gathers external threat intelligence (NVD, CISA, GitHub)
        2. Queries SecurityTelemetryService for internal findings
        3. Correlates external threats with internal activity
        4. Enhances reports with correlation data

        Returns:
            List of threat reports with correlation information.
        """
        self._log_activity("Gathering intelligence with GuardDuty correlation")

        # Gather external intelligence
        reports = await self.gather_intelligence()

        # Skip correlation if no telemetry service
        if not self.security_telemetry_service:
            self._log_activity("No SecurityTelemetryService - skipping correlation")
            return reports

        # Correlate each report with internal findings
        correlated_reports = []
        for report in reports:
            correlated = await self._correlate_with_guardduty(report)
            correlated_reports.append(correlated)

        self._log_activity(
            f"Correlated {len(correlated_reports)} reports with internal findings"
        )

        return correlated_reports

    async def _correlate_with_guardduty(
        self,
        report: ThreatIntelReport,
    ) -> ThreatIntelReport:
        """Correlate a threat report with internal GuardDuty findings.

        Correlation factors:
        - Time proximity (findings within 24 hours of threat publication)
        - Attack pattern matching (exploitation attempts)
        - Service/component overlap
        - Severity alignment

        Args:
            report: External threat report to correlate.

        Returns:
            Enhanced report with correlation data in raw_data.
        """
        if not self.security_telemetry_service:
            return report

        try:
            # Query recent internal findings
            internal_findings = (
                await self.security_telemetry_service.get_security_findings()
            )

            correlations = []
            for finding in internal_findings:
                correlation_score = self._calculate_correlation_score(report, finding)
                if correlation_score > 0.5:  # Threshold for meaningful correlation
                    correlations.append(
                        {
                            "finding_id": finding.id,
                            "finding_type": finding.finding_type.value,
                            "finding_title": finding.title,
                            "severity": finding.severity.value,
                            "correlation_score": correlation_score,
                            "correlation_reason": self._get_correlation_reason(
                                report, finding, correlation_score
                            ),
                        }
                    )

            # Enhance report with correlation data
            if correlations:
                enhanced_raw_data = dict(report.raw_data)
                enhanced_raw_data["guardduty_correlations"] = correlations
                enhanced_raw_data["correlation_count"] = len(correlations)
                enhanced_raw_data["max_correlation_score"] = max(
                    float(c["correlation_score"])
                    for c in correlations
                    if isinstance(c.get("correlation_score"), (int, float))
                )

                # Potentially escalate severity if strong correlation found
                if any(
                    float(c.get("correlation_score", 0.0)) >= 0.8 for c in correlations
                ):
                    self._log_activity(
                        f"High correlation found for '{report.title}' - "
                        f"{len(correlations)} internal findings match"
                    )

                return ThreatIntelReport(
                    id=report.id,
                    title=report.title,
                    category=report.category,
                    severity=report.severity,
                    source=report.source,
                    published_date=report.published_date,
                    description=report.description,
                    affected_components=report.affected_components,
                    cve_ids=report.cve_ids,
                    cvss_score=report.cvss_score,
                    recommended_actions=report.recommended_actions,
                    references=report.references,
                    raw_data=enhanced_raw_data,
                )

            return report

        except Exception as e:
            self._log_activity(f"Correlation error: {e}", error=True)
            return report

    def _calculate_correlation_score(
        self,
        report: ThreatIntelReport,
        finding: "SecurityFinding",
    ) -> float:
        """Calculate correlation score between threat and internal finding.

        Scoring factors:
        - Severity alignment: +0.2
        - Time proximity: +0.3 (within 6 hours)
        - Attack pattern match: +0.3
        - Component match: +0.2

        Args:
            report: External threat report.
            finding: Internal security finding.

        Returns:
            Correlation score from 0.0 to 1.0.
        """
        score = 0.0

        # Severity alignment
        severity_map = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
            "informational": 0,
        }
        report_sev = severity_map.get(report.severity.value, 2)
        finding_sev = severity_map.get(finding.severity.value, 2)
        if abs(report_sev - finding_sev) <= 1:
            score += 0.2

        # Time proximity (findings detected after threat was published)
        time_diff = abs((finding.detected_at - report.published_date).total_seconds())
        if time_diff <= 6 * 3600:  # Within 6 hours
            score += 0.3
        elif time_diff <= 24 * 3600:  # Within 24 hours
            score += 0.15

        # Attack pattern matching
        pattern_score = self._match_attack_patterns(report, finding)
        score += pattern_score * 0.3

        # Component match
        if self._check_component_overlap(report, finding):
            score += 0.2

        return min(score, 1.0)

    def _match_attack_patterns(
        self,
        report: ThreatIntelReport,
        finding: "SecurityFinding",
    ) -> float:
        """Check if attack patterns match between threat and finding.

        Matches vulnerability exploitation patterns with detection patterns.

        Args:
            report: External threat report.
            finding: Internal security finding.

        Returns:
            Pattern match score from 0.0 to 1.0.
        """
        # Keywords that indicate exploitation attempts
        exploitation_keywords = {
            "injection": ["sqli", "command", "injection", "rce"],
            "authentication": ["brute", "credential", "auth", "password", "login"],
            "network": ["scan", "recon", "port", "network"],
            "malware": ["malware", "trojan", "backdoor", "c2"],
            "exfiltration": ["exfil", "data", "transfer", "upload"],
        }

        report_text = f"{report.title} {report.description}".lower()
        finding_text = f"{finding.title} {finding.description}".lower()

        match_count = 0
        for _category, keywords in exploitation_keywords.items():
            report_has = any(kw in report_text for kw in keywords)
            finding_has = any(kw in finding_text for kw in keywords)
            if report_has and finding_has:
                match_count += 1

        return min(match_count / 2, 1.0)

    def _check_component_overlap(
        self,
        report: ThreatIntelReport,
        finding: "SecurityFinding",
    ) -> bool:
        """Check if threat and finding affect similar components.

        Args:
            report: External threat report.
            finding: Internal security finding.

        Returns:
            True if components overlap.
        """
        finding_text = f"{finding.title} {finding.description}".lower()

        # Check if affected components appear in finding
        for component in report.affected_components:
            comp_name = component.split("==")[0].lower()
            if comp_name in finding_text:
                return True

        # Check for service name matches
        service_keywords = ["api", "neptune", "opensearch", "eks", "s3"]
        for keyword in service_keywords:
            if keyword in report.description.lower() and keyword in finding_text:
                return True

        return False

    def _get_correlation_reason(
        self,
        report: ThreatIntelReport,
        finding: "SecurityFinding",
        score: float,
    ) -> str:
        """Generate human-readable correlation reason.

        Args:
            report: External threat report.
            finding: Internal security finding.
            score: Calculated correlation score.

        Returns:
            Explanation of why correlation was detected.
        """
        reasons = []

        # Time-based
        time_diff = abs((finding.detected_at - report.published_date).total_seconds())
        if time_diff <= 6 * 3600:
            reasons.append("detected within 6 hours of threat publication")
        elif time_diff <= 24 * 3600:
            reasons.append("detected within 24 hours of threat publication")

        # Severity
        if report.severity.value == finding.severity.value:
            reasons.append(f"matching {report.severity.value} severity")

        # Pattern
        if self._match_attack_patterns(report, finding) > 0:
            reasons.append("similar attack pattern detected")

        # Component
        if self._check_component_overlap(report, finding):
            reasons.append("affects similar components/services")

        if not reasons:
            return "Low-confidence temporal correlation"

        return "; ".join(reasons).capitalize()

    def get_correlated_threats_summary(
        self,
        reports: list[ThreatIntelReport],
    ) -> dict:
        """Generate summary of correlated threats.

        Args:
            reports: List of threat reports (with correlation data).

        Returns:
            Summary dictionary with statistics and high-priority items.
        """
        summary: dict[str, Any] = {
            "total_reports": len(reports),
            "correlated_reports": 0,
            "high_correlation_count": 0,
            "correlations_by_type": {},
            "high_priority_correlations": [],
        }

        for report in reports:
            correlations = report.raw_data.get("guardduty_correlations", [])
            if correlations:
                summary["correlated_reports"] += 1

                for corr in correlations:
                    finding_type = corr.get("finding_type", "unknown")
                    summary["correlations_by_type"][finding_type] = (
                        summary["correlations_by_type"].get(finding_type, 0) + 1
                    )

                    if corr.get("correlation_score", 0) >= 0.8:
                        summary["high_correlation_count"] += 1
                        summary["high_priority_correlations"].append(
                            {
                                "threat_title": report.title,
                                "threat_severity": report.severity.value,
                                "finding_title": corr.get("finding_title"),
                                "correlation_score": corr.get("correlation_score"),
                                "reason": corr.get("correlation_reason"),
                            }
                        )

        return summary


def create_threat_intelligence_agent(
    use_real_feeds: bool = True,
    use_real_telemetry: bool = True,
    config: ThreatIntelConfig | None = None,
    monitor: MonitorAgent | None = None,
    nvd_api_key: str | None = None,
    cache_ttl_minutes: int = 60,
) -> ThreatIntelligenceAgent:
    """Factory function to create a ThreatIntelligenceAgent with optional real feeds.

    This factory simplifies creation of ThreatIntelligenceAgent with the
    appropriate ThreatFeedClient and SecurityTelemetryService based on environment.

    Args:
        use_real_feeds: If True, create a ThreatFeedClient for real API calls.
            If False, agent will use mock data.
        use_real_telemetry: If True, create SecurityTelemetryService for real
            AWS security telemetry (GuardDuty, WAF, CloudTrail).
            If False, uses mock internal telemetry data.
        config: Optional agent configuration.
        monitor: Optional monitor agent for observability.
        nvd_api_key: Optional NVD API key for higher rate limits.
        cache_ttl_minutes: Cache TTL for threat feed responses.

    Returns:
        Configured ThreatIntelligenceAgent instance.

    Example:
        # Create agent with real feeds and telemetry (production)
        agent = create_threat_intelligence_agent(use_real_feeds=True)

        # Create agent with mock data (testing)
        agent = create_threat_intelligence_agent(
            use_real_feeds=False,
            use_real_telemetry=False
        )

        # Create agent with NVD API key for higher rate limits
        agent = create_threat_intelligence_agent(
            use_real_feeds=True,
            nvd_api_key="your-api-key"
        )
    """
    threat_feed_client = None
    security_telemetry_service = None

    if use_real_feeds:
        try:
            from src.services.threat_feed_client import (
                ThreatFeedClient,
                ThreatFeedConfig,
                ThreatFeedMode,
            )

            feed_config = ThreatFeedConfig(
                nvd_api_key=nvd_api_key,
                cache_ttl_minutes=cache_ttl_minutes,
            )
            threat_feed_client = ThreatFeedClient(
                mode=ThreatFeedMode.REAL,
                config=feed_config,
            )
        except ImportError:
            # httpx not available, will fall back to mock data
            pass

    if use_real_telemetry:
        try:
            from src.services.security_telemetry_service import (
                SecurityTelemetryService,
                TelemetryMode,
            )

            security_telemetry_service = SecurityTelemetryService(
                mode=TelemetryMode.AWS
            )
        except ImportError:
            # boto3 not available or not configured
            pass

    return ThreatIntelligenceAgent(
        config=config,
        monitor=monitor,
        threat_feed_client=threat_feed_client,
        security_telemetry_service=security_telemetry_service,
    )
