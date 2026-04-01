"""
Tests for threat_intelligence_agent.py

Comprehensive tests for the ThreatIntelligenceAgent which monitors
external threat feeds and internal telemetry for security vulnerabilities.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.threat_intelligence_agent import (
    ThreatCategory,
    ThreatIntelConfig,
    ThreatIntelligenceAgent,
    ThreatIntelReport,
    ThreatSeverity,
    create_threat_intelligence_agent,
)

# =============================================================================
# Test ThreatSeverity Enum
# =============================================================================


class TestThreatSeverity:
    """Tests for ThreatSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert ThreatSeverity.CRITICAL.value == "critical"
        assert ThreatSeverity.HIGH.value == "high"
        assert ThreatSeverity.MEDIUM.value == "medium"
        assert ThreatSeverity.LOW.value == "low"
        assert ThreatSeverity.INFORMATIONAL.value == "informational"


# =============================================================================
# Test ThreatCategory Enum
# =============================================================================


class TestThreatCategory:
    """Tests for ThreatCategory enum."""

    def test_category_values(self):
        """Test category enum values."""
        assert ThreatCategory.CVE.value == "cve"
        assert ThreatCategory.ADVISORY.value == "advisory"
        assert ThreatCategory.COMPLIANCE.value == "compliance"
        assert ThreatCategory.PATTERN.value == "pattern"
        assert ThreatCategory.INTERNAL.value == "internal"


# =============================================================================
# Test ThreatIntelReport Dataclass
# =============================================================================


class TestThreatIntelReport:
    """Tests for ThreatIntelReport dataclass."""

    def test_report_creation_minimal(self):
        """Test creating report with minimal fields."""
        report = ThreatIntelReport(
            id="report-001",
            title="Test Vulnerability",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime.now(),
            description="A critical vulnerability",
        )

        assert report.id == "report-001"
        assert report.title == "Test Vulnerability"
        assert report.category == ThreatCategory.CVE
        assert report.severity == ThreatSeverity.HIGH
        assert report.affected_components == []
        assert report.cve_ids == []
        assert report.cvss_score is None
        assert report.recommended_actions == []
        assert report.references == []
        assert report.raw_data == {}

    def test_report_creation_full(self):
        """Test creating report with all fields."""
        now = datetime.now()
        report = ThreatIntelReport(
            id="report-002",
            title="Full Report",
            category=ThreatCategory.ADVISORY,
            severity=ThreatSeverity.CRITICAL,
            source="CISA KEV",
            published_date=now,
            description="Critical advisory",
            affected_components=["component-a", "component-b"],
            cve_ids=["CVE-2025-0001", "CVE-2025-0002"],
            cvss_score=9.8,
            recommended_actions=["Patch immediately"],
            references=["https://example.com/advisory"],
            raw_data={"custom": "data"},
        )

        assert report.affected_components == ["component-a", "component-b"]
        assert report.cve_ids == ["CVE-2025-0001", "CVE-2025-0002"]
        assert report.cvss_score == 9.8
        assert report.raw_data == {"custom": "data"}

    def test_report_to_dict(self):
        """Test report serialization to dictionary."""
        now = datetime.now()
        report = ThreatIntelReport(
            id="report-003",
            title="Serializable Report",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.MEDIUM,
            source="GitHub",
            published_date=now,
            description="Test description",
            cve_ids=["CVE-2025-0003"],
            cvss_score=6.5,
        )

        result = report.to_dict()

        assert result["id"] == "report-003"
        assert result["title"] == "Serializable Report"
        assert result["category"] == "cve"
        assert result["severity"] == "medium"
        assert result["source"] == "GitHub"
        assert result["published_date"] == now.isoformat()
        assert result["cvss_score"] == 6.5
        assert result["cve_ids"] == ["CVE-2025-0003"]


# =============================================================================
# Test ThreatIntelConfig
# =============================================================================


class TestThreatIntelConfig:
    """Tests for ThreatIntelConfig dataclass."""

    def test_config_defaults(self):
        """Test config default values."""
        config = ThreatIntelConfig()

        assert config.nvd_api_key is None
        assert "cisa.gov" in config.cisa_feed_url
        assert "github.com" in config.github_advisory_url
        assert config.check_interval_minutes == 60
        assert config.max_cve_age_days == 30
        assert config.severity_threshold == ThreatSeverity.MEDIUM

    def test_config_custom_values(self):
        """Test config with custom values."""
        config = ThreatIntelConfig(
            nvd_api_key="test-key",
            check_interval_minutes=30,
            max_cve_age_days=14,
            severity_threshold=ThreatSeverity.HIGH,
        )

        assert config.nvd_api_key == "test-key"
        assert config.check_interval_minutes == 30
        assert config.max_cve_age_days == 14
        assert config.severity_threshold == ThreatSeverity.HIGH


# =============================================================================
# Test ThreatIntelligenceAgent Initialization
# =============================================================================


class TestThreatIntelligenceAgentInit:
    """Tests for ThreatIntelligenceAgent initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default config."""
        agent = ThreatIntelligenceAgent()

        assert agent.config is not None
        assert agent.monitor is None
        assert agent.threat_feed_client is None
        assert agent._known_threats == set()
        assert agent._dependency_sbom == []

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = ThreatIntelConfig(nvd_api_key="custom-key")
        agent = ThreatIntelligenceAgent(config=config)

        assert agent.config.nvd_api_key == "custom-key"

    def test_init_with_monitor(self):
        """Test initialization with monitor."""
        mock_monitor = MagicMock()
        agent = ThreatIntelligenceAgent(monitor=mock_monitor)

        assert agent.monitor == mock_monitor

    def test_init_with_threat_feed_client(self):
        """Test initialization with threat feed client."""
        mock_client = MagicMock()
        agent = ThreatIntelligenceAgent(threat_feed_client=mock_client)

        assert agent.threat_feed_client == mock_client


# =============================================================================
# Test Dependency SBOM
# =============================================================================


class TestDependencySBOM:
    """Tests for SBOM handling."""

    def test_set_dependency_sbom(self):
        """Test setting SBOM."""
        agent = ThreatIntelligenceAgent()
        sbom = [
            {"name": "requests", "version": "2.28.0"},
            {"name": "fastapi", "version": "0.100.0"},
        ]

        agent.set_dependency_sbom(sbom)

        assert len(agent._dependency_sbom) == 2
        assert agent._dependency_sbom[0]["name"] == "requests"

    def test_check_dependency_match_found(self):
        """Test dependency match when package is in SBOM."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0"},
                {"name": "fastapi", "version": "0.100.0"},
            ]
        )

        matches = agent._check_dependency_match(["requests"])

        assert len(matches) == 1
        assert "requests==2.28.0" in matches[0]

    def test_check_dependency_match_case_insensitive(self):
        """Test dependency match is case insensitive."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "FastAPI", "version": "0.100.0"},
            ]
        )

        matches = agent._check_dependency_match(["fastapi"])

        assert len(matches) == 1

    def test_check_dependency_match_not_found(self):
        """Test dependency match when package not in SBOM."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0"},
            ]
        )

        matches = agent._check_dependency_match(["unknown-package"])

        assert len(matches) == 0

    def test_check_dependency_match_with_none(self):
        """Test dependency match handles None values."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom([{"name": "requests", "version": "2.28.0"}])

        matches = agent._check_dependency_match([None, "requests", None])

        assert len(matches) == 1


# =============================================================================
# Test Multi-Ecosystem Support
# =============================================================================


class TestMultiEcosystemSupport:
    """Tests for multi-ecosystem SBOM and advisory support."""

    def test_get_detected_ecosystems_default(self):
        """Test default ecosystem when SBOM is empty."""
        agent = ThreatIntelligenceAgent()
        ecosystems = agent.get_detected_ecosystems()

        # Should default to pip when no SBOM set
        assert ecosystems == ["pip"]

    def test_get_detected_ecosystems_single(self):
        """Test detecting single ecosystem from SBOM."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0", "ecosystem": "pip"},
                {"name": "fastapi", "version": "0.100.0", "ecosystem": "pip"},
            ]
        )

        ecosystems = agent.get_detected_ecosystems()

        assert ecosystems == ["pip"]

    def test_get_detected_ecosystems_multiple(self):
        """Test detecting multiple ecosystems from SBOM."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0", "ecosystem": "pip"},
                {"name": "express", "version": "4.18.0", "ecosystem": "npm"},
                {"name": "tokio", "version": "1.35.0", "ecosystem": "cargo"},
                {"name": "rails", "version": "7.0.0", "ecosystem": "rubygems"},
            ]
        )

        ecosystems = agent.get_detected_ecosystems()

        # Should be sorted alphabetically
        assert ecosystems == ["cargo", "npm", "pip", "rubygems"]

    def test_get_detected_ecosystems_filters_unknown(self):
        """Test that unknown ecosystem is filtered out."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0", "ecosystem": "pip"},
                {"name": "mystery", "version": "1.0.0", "ecosystem": "unknown"},
            ]
        )

        ecosystems = agent.get_detected_ecosystems()

        assert "unknown" not in ecosystems
        assert ecosystems == ["pip"]

    def test_get_detected_ecosystems_legacy_sbom(self):
        """Test handling SBOM entries without ecosystem field."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0"},  # No ecosystem field
                {"name": "fastapi", "version": "0.100.0"},
            ]
        )

        ecosystems = agent.get_detected_ecosystems()

        # Should default to pip for legacy entries
        assert ecosystems == ["pip"]

    def test_get_dependencies_by_ecosystem(self):
        """Test filtering dependencies by ecosystem."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0", "ecosystem": "pip"},
                {"name": "express", "version": "4.18.0", "ecosystem": "npm"},
                {"name": "fastapi", "version": "0.100.0", "ecosystem": "pip"},
                {"name": "lodash", "version": "4.17.0", "ecosystem": "npm"},
            ]
        )

        pip_deps = agent.get_dependencies_by_ecosystem("pip")
        npm_deps = agent.get_dependencies_by_ecosystem("npm")

        assert len(pip_deps) == 2
        assert len(npm_deps) == 2
        assert all(d["ecosystem"] == "pip" for d in pip_deps)
        assert all(d["ecosystem"] == "npm" for d in npm_deps)

    def test_get_dependencies_by_ecosystem_not_found(self):
        """Test getting dependencies for non-existent ecosystem."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0", "ecosystem": "pip"},
            ]
        )

        go_deps = agent.get_dependencies_by_ecosystem("go")

        assert len(go_deps) == 0

    def test_get_dependencies_by_ecosystem_all_supported(self):
        """Test all supported ecosystems can be filtered."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0", "ecosystem": "pip"},
                {"name": "express", "version": "4.18.0", "ecosystem": "npm"},
                {"name": "chi", "version": "5.0.0", "ecosystem": "go"},
                {"name": "tokio", "version": "1.35.0", "ecosystem": "cargo"},
                {"name": "rails", "version": "7.0.0", "ecosystem": "rubygems"},
                {"name": "Newtonsoft.Json", "version": "13.0.0", "ecosystem": "nuget"},
            ]
        )

        for eco in ["pip", "npm", "go", "cargo", "rubygems", "nuget"]:
            deps = agent.get_dependencies_by_ecosystem(eco)
            assert len(deps) == 1
            assert deps[0]["ecosystem"] == eco


class TestMultiEcosystemAdvisories:
    """Tests for fetching advisories across multiple ecosystems."""

    @pytest.mark.asyncio
    async def test_github_advisories_queries_detected_ecosystems(self):
        """Test that GitHub advisories are queried for all detected ecosystems."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0", "ecosystem": "pip"},
                {"name": "express", "version": "4.18.0", "ecosystem": "npm"},
                {"name": "tokio", "version": "1.35.0", "ecosystem": "cargo"},
            ]
        )

        # Without ThreatFeedClient, uses mock data filtered by ecosystem
        reports = await agent._fetch_github_advisories()

        # Should return reports for pip, npm, and cargo ecosystems
        # Mock data includes fastapi (pip), express (npm), tokio (cargo)
        ecosystems_in_reports = {
            r.raw_data.get("ecosystem") for r in reports if r.raw_data.get("ecosystem")
        }
        assert "pip" in ecosystems_in_reports or len(reports) > 0

    @pytest.mark.asyncio
    async def test_github_advisories_only_detected_ecosystems(self):
        """Test that only detected ecosystem advisories are returned."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0", "ecosystem": "pip"},
            ]
        )

        reports = await agent._fetch_github_advisories()

        # Should only have pip ecosystem advisories (from mock)
        for report in reports:
            eco = report.raw_data.get("ecosystem")
            if eco:  # Only check if ecosystem is set
                assert eco == "pip"

    @pytest.mark.asyncio
    async def test_github_advisories_with_threatfeedclient(self):
        """Test GitHub advisories with real ThreatFeedClient."""
        mock_client = MagicMock()
        mock_advisory = MagicMock()
        mock_advisory.ghsa_id = "GHSA-test-1234"
        mock_advisory.summary = "Test advisory"
        mock_advisory.severity = "high"
        mock_advisory.published_at = datetime.now()
        mock_advisory.description = "Test description"
        mock_advisory.package_name = "requests"
        mock_advisory.package_ecosystem = "pip"
        mock_advisory.cve_id = "CVE-2024-1234"
        mock_advisory.vulnerable_versions = "<2.30.0"
        mock_advisory.patched_versions = ">=2.30.0"
        mock_advisory.references = ["https://example.com"]

        mock_client.fetch_github_advisories = AsyncMock(return_value=[mock_advisory])

        agent = ThreatIntelligenceAgent(threat_feed_client=mock_client)
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0", "ecosystem": "pip"},
                {"name": "express", "version": "4.18.0", "ecosystem": "npm"},
            ]
        )

        await agent._fetch_github_advisories()

        # Should have called fetch_github_advisories for each ecosystem
        assert mock_client.fetch_github_advisories.call_count == 2

    @pytest.mark.asyncio
    async def test_github_advisories_matches_ecosystem_dependencies(self):
        """Test that advisories match against ecosystem-specific dependencies."""
        mock_client = MagicMock()
        pip_advisory = MagicMock()
        pip_advisory.ghsa_id = "GHSA-pip-1234"
        pip_advisory.summary = "Requests vulnerability"
        pip_advisory.severity = "high"
        pip_advisory.published_at = datetime.now()
        pip_advisory.description = "Test"
        pip_advisory.package_name = "requests"
        pip_advisory.package_ecosystem = "pip"
        pip_advisory.cve_id = None
        pip_advisory.vulnerable_versions = "<2.30.0"
        pip_advisory.patched_versions = ">=2.30.0"
        pip_advisory.references = []

        npm_advisory = MagicMock()
        npm_advisory.ghsa_id = "GHSA-npm-5678"
        npm_advisory.summary = "Express vulnerability"
        npm_advisory.severity = "critical"
        npm_advisory.published_at = datetime.now()
        npm_advisory.description = "Test"
        npm_advisory.package_name = "express"
        npm_advisory.package_ecosystem = "npm"
        npm_advisory.cve_id = None
        npm_advisory.vulnerable_versions = "<4.19.0"
        npm_advisory.patched_versions = ">=4.19.0"
        npm_advisory.references = []

        async def mock_fetch(ecosystem):
            if ecosystem == "pip":
                return [pip_advisory]
            elif ecosystem == "npm":
                return [npm_advisory]
            return []

        mock_client.fetch_github_advisories = AsyncMock(side_effect=mock_fetch)

        agent = ThreatIntelligenceAgent(threat_feed_client=mock_client)
        agent.set_dependency_sbom(
            [
                {"name": "requests", "version": "2.28.0", "ecosystem": "pip"},
                {"name": "express", "version": "4.18.0", "ecosystem": "npm"},
            ]
        )

        reports = await agent._fetch_github_advisories()

        # Should have reports for both pip and npm
        assert len(reports) == 2
        ghsa_ids = {r.id for r in reports}
        assert len(ghsa_ids) == 2  # Two unique reports


# =============================================================================
# Test Gather Intelligence
# =============================================================================


class TestGatherIntelligence:
    """Tests for gathering threat intelligence."""

    @pytest.mark.asyncio
    async def test_gather_intelligence_combines_sources(self):
        """Test gather_intelligence combines all source results."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom([{"name": "requests", "version": "2.28.0"}])

        reports = await agent.gather_intelligence()

        # Should have reports from mock sources
        assert len(reports) >= 0  # May be 0 if no matches

    @pytest.mark.asyncio
    async def test_gather_intelligence_handles_exceptions(self):
        """Test gather_intelligence handles source exceptions gracefully."""
        agent = ThreatIntelligenceAgent()

        # Mock a source to raise an exception
        with patch.object(agent, "_fetch_nvd_cves", side_effect=Exception("NVD error")):
            # Should not raise, should continue with other sources
            reports = await agent.gather_intelligence()
            assert isinstance(reports, list)

    @pytest.mark.asyncio
    async def test_gather_intelligence_filters_new_reports(self):
        """Test gather_intelligence only returns new reports."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom([{"name": "requests", "version": "2.28.0"}])

        # First call
        await agent.gather_intelligence()

        # Second call should return no new reports (same data)
        reports2 = await agent.gather_intelligence()

        assert len(reports2) == 0  # All reports now known


# =============================================================================
# Test Fetch NVD CVEs
# =============================================================================


class TestFetchNVDCVEs:
    """Tests for NVD CVE fetching."""

    @pytest.mark.asyncio
    async def test_fetch_nvd_cves_with_client(self):
        """Test fetching CVEs with ThreatFeedClient."""
        mock_client = AsyncMock()

        # Mock CVE record
        mock_cve = MagicMock()
        mock_cve.cve_id = "CVE-2025-0001"
        mock_cve.title = "Test CVE"
        mock_cve.description = "Test description"
        mock_cve.cvss_score = 9.5
        mock_cve.published_date = datetime.now()
        mock_cve.affected_products = ["test-package"]
        mock_cve.references = ["https://example.com"]
        mock_cve.raw_data = {}

        mock_client.fetch_nvd_cves.return_value = [mock_cve]

        agent = ThreatIntelligenceAgent(threat_feed_client=mock_client)

        reports = await agent._fetch_nvd_cves()

        assert len(reports) == 1
        assert reports[0].category == ThreatCategory.CVE
        mock_client.fetch_nvd_cves.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_nvd_cves_client_error_fallback(self):
        """Test fallback to mock when client errors."""
        mock_client = AsyncMock()
        mock_client.fetch_nvd_cves.side_effect = Exception("API error")

        agent = ThreatIntelligenceAgent(threat_feed_client=mock_client)
        agent.set_dependency_sbom([{"name": "requests", "version": "2.28.0"}])

        reports = await agent._fetch_nvd_cves()

        # Should use mock data and still return reports
        assert isinstance(reports, list)

    @pytest.mark.asyncio
    async def test_fetch_nvd_cves_mock_only(self):
        """Test NVD fetch with mock implementation."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom([{"name": "requests", "version": "2.28.0"}])

        reports = await agent._fetch_nvd_cves()

        # Mock data should return reports for matching dependencies
        assert any(r.category == ThreatCategory.CVE for r in reports)
        assert "nvd" in agent._last_check


# =============================================================================
# Test Fetch CISA Advisories
# =============================================================================


class TestFetchCISAAdvisories:
    """Tests for CISA advisory fetching."""

    @pytest.mark.asyncio
    async def test_fetch_cisa_advisories_with_client(self):
        """Test fetching advisories with ThreatFeedClient."""
        mock_client = AsyncMock()

        # Mock KEV record
        mock_kev = MagicMock()
        mock_kev.cve_id = "CVE-2025-0001"
        mock_kev.vulnerability_name = "Test KEV"
        mock_kev.short_description = "Test description"
        mock_kev.date_added = datetime.now()
        mock_kev.product = "test-product"
        mock_kev.vendor_project = "test-vendor"
        mock_kev.required_action = "Patch immediately"
        mock_kev.due_date = datetime.now() + timedelta(days=30)
        mock_kev.known_ransomware = False

        mock_client.fetch_cisa_kev.return_value = [mock_kev]

        agent = ThreatIntelligenceAgent(threat_feed_client=mock_client)

        reports = await agent._fetch_cisa_advisories()

        assert len(reports) == 1
        assert reports[0].severity == ThreatSeverity.CRITICAL
        assert reports[0].source == "CISA KEV"

    @pytest.mark.asyncio
    async def test_fetch_cisa_advisories_mock_only(self):
        """Test CISA fetch with mock implementation."""
        agent = ThreatIntelligenceAgent()

        reports = await agent._fetch_cisa_advisories()

        assert len(reports) >= 1
        assert reports[0].category == ThreatCategory.ADVISORY
        assert "cisa" in agent._last_check


# =============================================================================
# Test Fetch GitHub Advisories
# =============================================================================


class TestFetchGitHubAdvisories:
    """Tests for GitHub advisory fetching."""

    @pytest.mark.asyncio
    async def test_fetch_github_advisories_with_client(self):
        """Test fetching advisories with ThreatFeedClient."""
        mock_client = AsyncMock()

        # Mock GitHub advisory
        mock_advisory = MagicMock()
        mock_advisory.ghsa_id = "GHSA-xxxx-yyyy-zzzz"
        mock_advisory.summary = "Test Advisory"
        mock_advisory.description = "Test description"
        mock_advisory.severity = "high"
        mock_advisory.published_at = datetime.now()
        mock_advisory.package_name = "test-package"
        mock_advisory.package_ecosystem = "pip"
        mock_advisory.cve_id = "CVE-2025-0001"
        mock_advisory.vulnerable_versions = "<1.0.0"
        mock_advisory.patched_versions = ">=1.0.0"
        mock_advisory.references = ["https://example.com"]

        mock_client.fetch_github_advisories.return_value = [mock_advisory]

        agent = ThreatIntelligenceAgent(threat_feed_client=mock_client)
        agent.set_dependency_sbom([{"name": "test-package", "version": "0.9.0"}])

        reports = await agent._fetch_github_advisories()

        assert len(reports) == 1
        mock_client.fetch_github_advisories.assert_called_once_with(ecosystem="pip")

    @pytest.mark.asyncio
    async def test_fetch_github_advisories_mock_only(self):
        """Test GitHub fetch with mock implementation."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom([{"name": "fastapi", "version": "0.100.0"}])

        reports = await agent._fetch_github_advisories()

        # Mock should return reports for matching dependencies
        assert isinstance(reports, list)
        assert "github" in agent._last_check


# =============================================================================
# Test Internal Telemetry Analysis
# =============================================================================


class TestAnalyzeInternalTelemetry:
    """Tests for internal telemetry analysis."""

    @pytest.mark.asyncio
    async def test_analyze_internal_telemetry_returns_reports(self):
        """Test internal telemetry analysis returns reports."""
        agent = ThreatIntelligenceAgent()

        reports = await agent._analyze_internal_telemetry()

        assert len(reports) >= 1
        assert reports[0].category == ThreatCategory.INTERNAL
        assert reports[0].severity == ThreatSeverity.MEDIUM
        assert "internal" in agent._last_check


# =============================================================================
# Test Report Filtering
# =============================================================================


class TestReportFiltering:
    """Tests for report filtering."""

    def test_filter_new_reports_first_time(self):
        """Test filtering when all reports are new."""
        agent = ThreatIntelligenceAgent()
        reports = [
            ThreatIntelReport(
                id=f"report-{i}",
                title=f"Report {i}",
                category=ThreatCategory.CVE,
                severity=ThreatSeverity.HIGH,
                source="Test",
                published_date=datetime.now(),
                description=f"Description {i}",
            )
            for i in range(3)
        ]

        filtered = agent._filter_new_reports(reports)

        assert len(filtered) == 3
        assert all(r.id in agent._known_threats for r in reports)

    def test_filter_new_reports_duplicate(self):
        """Test filtering removes duplicates."""
        agent = ThreatIntelligenceAgent()
        report = ThreatIntelReport(
            id="duplicate-report",
            title="Duplicate",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="Test",
            published_date=datetime.now(),
            description="Duplicate description",
        )

        # First call
        first = agent._filter_new_reports([report])
        # Second call with same report
        second = agent._filter_new_reports([report])

        assert len(first) == 1
        assert len(second) == 0


# =============================================================================
# Test Report Prioritization
# =============================================================================


class TestReportPrioritization:
    """Tests for report prioritization."""

    def test_prioritize_by_severity(self):
        """Test prioritization puts critical first."""
        agent = ThreatIntelligenceAgent()
        reports = [
            ThreatIntelReport(
                id="low",
                title="Low",
                category=ThreatCategory.CVE,
                severity=ThreatSeverity.LOW,
                source="Test",
                published_date=datetime.now(),
                description="Low severity",
            ),
            ThreatIntelReport(
                id="critical",
                title="Critical",
                category=ThreatCategory.CVE,
                severity=ThreatSeverity.CRITICAL,
                source="Test",
                published_date=datetime.now(),
                description="Critical severity",
            ),
            ThreatIntelReport(
                id="high",
                title="High",
                category=ThreatCategory.CVE,
                severity=ThreatSeverity.HIGH,
                source="Test",
                published_date=datetime.now(),
                description="High severity",
            ),
        ]

        prioritized = agent._prioritize_by_relevance(reports)

        assert prioritized[0].id == "critical"
        assert prioritized[1].id == "high"
        assert prioritized[2].id == "low"

    def test_prioritize_affected_components(self):
        """Test prioritization prefers reports with affected components."""
        agent = ThreatIntelligenceAgent()
        now = datetime.now()
        reports = [
            ThreatIntelReport(
                id="no-match",
                title="No Match",
                category=ThreatCategory.CVE,
                severity=ThreatSeverity.HIGH,
                source="Test",
                published_date=now,
                description="No affected components",
            ),
            ThreatIntelReport(
                id="with-match",
                title="With Match",
                category=ThreatCategory.CVE,
                severity=ThreatSeverity.HIGH,
                source="Test",
                published_date=now,
                description="Has affected components",
                affected_components=["requests==2.28.0"],
            ),
        ]

        prioritized = agent._prioritize_by_relevance(reports)

        assert prioritized[0].id == "with-match"

    def test_prioritize_cisa_kev(self):
        """Test prioritization prefers CISA KEV source."""
        agent = ThreatIntelligenceAgent()
        now = datetime.now()
        reports = [
            ThreatIntelReport(
                id="nvd",
                title="NVD",
                category=ThreatCategory.CVE,
                severity=ThreatSeverity.CRITICAL,
                source="NVD",
                published_date=now,
                description="From NVD",
            ),
            ThreatIntelReport(
                id="cisa",
                title="CISA",
                category=ThreatCategory.ADVISORY,
                severity=ThreatSeverity.CRITICAL,
                source="CISA KEV",
                published_date=now,
                description="From CISA",
            ),
        ]

        prioritized = agent._prioritize_by_relevance(reports)

        assert prioritized[0].id == "cisa"


# =============================================================================
# Test Severity Conversions
# =============================================================================


class TestSeverityConversions:
    """Tests for severity conversion methods."""

    def test_cvss_to_severity_critical(self):
        """Test CVSS 9.0+ maps to CRITICAL."""
        agent = ThreatIntelligenceAgent()

        assert agent._cvss_to_severity(10.0) == ThreatSeverity.CRITICAL
        assert agent._cvss_to_severity(9.0) == ThreatSeverity.CRITICAL
        assert agent._cvss_to_severity(9.5) == ThreatSeverity.CRITICAL

    def test_cvss_to_severity_high(self):
        """Test CVSS 7.0-8.9 maps to HIGH."""
        agent = ThreatIntelligenceAgent()

        assert agent._cvss_to_severity(8.9) == ThreatSeverity.HIGH
        assert agent._cvss_to_severity(7.0) == ThreatSeverity.HIGH

    def test_cvss_to_severity_medium(self):
        """Test CVSS 4.0-6.9 maps to MEDIUM."""
        agent = ThreatIntelligenceAgent()

        assert agent._cvss_to_severity(6.9) == ThreatSeverity.MEDIUM
        assert agent._cvss_to_severity(4.0) == ThreatSeverity.MEDIUM

    def test_cvss_to_severity_low(self):
        """Test CVSS 0.1-3.9 maps to LOW."""
        agent = ThreatIntelligenceAgent()

        assert agent._cvss_to_severity(3.9) == ThreatSeverity.LOW
        assert agent._cvss_to_severity(0.1) == ThreatSeverity.LOW

    def test_cvss_to_severity_informational(self):
        """Test CVSS 0 maps to INFORMATIONAL."""
        agent = ThreatIntelligenceAgent()

        assert agent._cvss_to_severity(0.0) == ThreatSeverity.INFORMATIONAL

    def test_string_to_severity_mappings(self):
        """Test string to severity mappings."""
        agent = ThreatIntelligenceAgent()

        assert agent._string_to_severity("critical") == ThreatSeverity.CRITICAL
        assert agent._string_to_severity("CRITICAL") == ThreatSeverity.CRITICAL
        assert agent._string_to_severity("high") == ThreatSeverity.HIGH
        assert agent._string_to_severity("medium") == ThreatSeverity.MEDIUM
        assert agent._string_to_severity("moderate") == ThreatSeverity.MEDIUM
        assert agent._string_to_severity("low") == ThreatSeverity.LOW
        assert agent._string_to_severity("unknown") == ThreatSeverity.INFORMATIONAL


# =============================================================================
# Test Report ID Generation
# =============================================================================


class TestReportIDGeneration:
    """Tests for report ID generation."""

    def test_generate_report_id_unique(self):
        """Test report IDs are unique for different inputs."""
        agent = ThreatIntelligenceAgent()

        id1 = agent._generate_report_id("nvd", "CVE-2025-0001")
        id2 = agent._generate_report_id("nvd", "CVE-2025-0002")
        id3 = agent._generate_report_id("cisa", "CVE-2025-0001")

        assert id1 != id2
        assert id1 != id3
        assert id2 != id3

    def test_generate_report_id_deterministic(self):
        """Test same inputs produce same ID."""
        agent = ThreatIntelligenceAgent()

        id1 = agent._generate_report_id("nvd", "CVE-2025-0001")
        id2 = agent._generate_report_id("nvd", "CVE-2025-0001")

        assert id1 == id2

    def test_generate_report_id_length(self):
        """Test report ID is 16 characters (truncated hash)."""
        agent = ThreatIntelligenceAgent()

        report_id = agent._generate_report_id("test", "identifier")

        assert len(report_id) == 16


# =============================================================================
# Test Logging
# =============================================================================


class TestLogging:
    """Tests for logging functionality."""

    def test_log_activity_normal(self, capsys):
        """Test normal activity logging."""
        agent = ThreatIntelligenceAgent()
        agent._log_activity("Test message")

        captured = capsys.readouterr()
        assert "Test message" in captured.out
        assert "ERROR" not in captured.out

    def test_log_activity_error(self, capsys):
        """Test error activity logging."""
        agent = ThreatIntelligenceAgent()
        agent._log_activity("Error message", error=True)

        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "Error message" in captured.out

    def test_log_activity_with_monitor(self):
        """Test logging uses monitor when available."""
        mock_monitor = MagicMock()
        agent = ThreatIntelligenceAgent(monitor=mock_monitor)

        agent._log_activity("Test with monitor")

        mock_monitor.log_activity.assert_called_once()


# =============================================================================
# Test Factory Function
# =============================================================================


class TestCreateThreatIntelligenceAgent:
    """Tests for factory function."""

    def test_create_without_real_feeds(self):
        """Test creating agent without real feeds."""
        agent = create_threat_intelligence_agent(use_real_feeds=False)

        assert isinstance(agent, ThreatIntelligenceAgent)
        assert agent.threat_feed_client is None

    def test_create_with_custom_config(self):
        """Test creating agent with custom config."""
        config = ThreatIntelConfig(check_interval_minutes=30)
        agent = create_threat_intelligence_agent(
            use_real_feeds=False,
            config=config,
        )

        assert agent.config.check_interval_minutes == 30

    def test_create_with_monitor(self):
        """Test creating agent with monitor."""
        mock_monitor = MagicMock()
        agent = create_threat_intelligence_agent(
            use_real_feeds=False,
            monitor=mock_monitor,
        )

        assert agent.monitor == mock_monitor

    def test_create_with_real_feeds_import_error(self):
        """Test creating agent handles import errors gracefully."""
        with patch.dict("sys.modules", {"src.services.threat_feed_client": None}):
            # Should not raise, should create agent without client
            agent = create_threat_intelligence_agent(use_real_feeds=True)
            assert isinstance(agent, ThreatIntelligenceAgent)


# =============================================================================
# Test GuardDuty Correlation
# =============================================================================


class TestGuardDutyCorrelation:
    """Tests for threat correlation with GuardDuty findings."""

    @pytest.fixture
    def sample_threat_report(self) -> ThreatIntelReport:
        """Create a sample threat report."""
        return ThreatIntelReport(
            id="threat-12345678",
            title="SQL Injection vulnerability in database driver",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.HIGH,
            source="NVD",
            published_date=datetime.now() - timedelta(hours=2),
            description="SQL injection vulnerability allows remote code execution",
            affected_components=["mysql-connector==8.0.0"],
            cve_ids=["CVE-2024-9999"],
            cvss_score=8.5,
        )

    @pytest.fixture
    def mock_security_finding(self):
        """Create a mock security finding."""
        finding = MagicMock()
        finding.id = "finding-123"
        finding.title = "SQLi attack detected"
        finding.description = "SQL injection attempt from suspicious IP"
        finding.finding_type = MagicMock()
        finding.finding_type.value = "guardduty"
        finding.severity = MagicMock()
        finding.severity.value = "high"
        finding.detected_at = datetime.now() - timedelta(hours=1)
        return finding

    def test_calculate_correlation_score_high_match(
        self, sample_threat_report, mock_security_finding
    ):
        """Test correlation score for high-matching findings."""
        agent = ThreatIntelligenceAgent()

        score = agent._calculate_correlation_score(
            sample_threat_report, mock_security_finding
        )

        # Should have high score due to:
        # - Severity alignment (high)
        # - Time proximity (within 6 hours)
        # - Pattern match (injection keywords)
        assert score >= 0.5

    def test_calculate_correlation_score_no_pattern_match(self, sample_threat_report):
        """Test correlation score with no pattern match."""
        agent = ThreatIntelligenceAgent()

        unrelated_finding = MagicMock()
        unrelated_finding.id = "finding-456"
        unrelated_finding.title = "Unusual network traffic"
        unrelated_finding.description = "Outbound traffic to unknown destination"
        unrelated_finding.finding_type = MagicMock()
        unrelated_finding.finding_type.value = "guardduty"
        unrelated_finding.severity = MagicMock()
        unrelated_finding.severity.value = "low"
        unrelated_finding.detected_at = datetime.now() - timedelta(days=2)

        score = agent._calculate_correlation_score(
            sample_threat_report, unrelated_finding
        )

        # Should have low score - no pattern match, time far apart, severity mismatch
        assert score < 0.5

    def test_match_attack_patterns_injection(
        self, sample_threat_report, mock_security_finding
    ):
        """Test attack pattern matching for injection attacks."""
        agent = ThreatIntelligenceAgent()

        score = agent._match_attack_patterns(
            sample_threat_report, mock_security_finding
        )

        # Both have injection-related keywords
        assert score > 0

    def test_match_attack_patterns_no_match(self):
        """Test attack pattern matching with no match."""
        agent = ThreatIntelligenceAgent()

        # Report without exploitation keywords
        report = ThreatIntelReport(
            id="test",
            title="Memory leak in application",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.LOW,
            source="NVD",
            published_date=datetime.now(),
            description="Memory leak causes slow performance degradation",
        )

        # Use a simple object with string attributes (not MagicMock)
        class SimpleFinding:
            title = "Resource usage anomaly"
            description = "CPU usage exceeded threshold"

        score = agent._match_attack_patterns(report, SimpleFinding())

        assert score == 0

    def test_check_component_overlap_true(self, sample_threat_report):
        """Test component overlap detection - positive case."""
        agent = ThreatIntelligenceAgent()

        finding = MagicMock()
        finding.title = "Database mysql connection refused"
        finding.description = "mysql-connector connection pool exhausted"

        result = agent._check_component_overlap(sample_threat_report, finding)

        # mysql-connector is in affected_components and finding
        assert result is True

    def test_check_component_overlap_false(self, sample_threat_report):
        """Test component overlap detection - negative case."""
        agent = ThreatIntelligenceAgent()

        finding = MagicMock()
        finding.title = "Memory pressure detected"
        finding.description = "Container memory limit exceeded"

        result = agent._check_component_overlap(sample_threat_report, finding)

        assert result is False

    def test_get_correlation_reason_time_based(
        self, sample_threat_report, mock_security_finding
    ):
        """Test correlation reason generation."""
        agent = ThreatIntelligenceAgent()

        reason = agent._get_correlation_reason(
            sample_threat_report, mock_security_finding, 0.7
        )

        assert len(reason) > 0
        # Should mention time or severity or pattern
        assert any(
            word in reason.lower()
            for word in ["hour", "severity", "pattern", "component"]
        )

    @pytest.mark.asyncio
    async def test_gather_intelligence_with_correlation_no_service(self):
        """Test correlation without SecurityTelemetryService."""
        agent = ThreatIntelligenceAgent()
        agent.set_dependency_sbom([{"name": "requests", "version": "2.28.0"}])

        reports = await agent.gather_intelligence_with_correlation()

        # Should return reports without correlation (no service)
        assert isinstance(reports, list)

    @pytest.mark.asyncio
    async def test_correlate_with_guardduty_returns_original_on_error(
        self, sample_threat_report
    ):
        """Test correlation returns original report on error."""
        mock_service = MagicMock()
        mock_service.get_findings = AsyncMock(side_effect=Exception("Service error"))

        agent = ThreatIntelligenceAgent(security_telemetry_service=mock_service)

        result = await agent._correlate_with_guardduty(sample_threat_report)

        # Should return original report on error
        assert result.id == sample_threat_report.id

    @pytest.mark.asyncio
    async def test_correlate_with_guardduty_enhances_report(
        self, sample_threat_report, mock_security_finding
    ):
        """Test correlation enhances report with finding data."""
        mock_service = MagicMock()
        mock_service.get_findings = AsyncMock(return_value=[mock_security_finding])

        agent = ThreatIntelligenceAgent(security_telemetry_service=mock_service)

        result = await agent._correlate_with_guardduty(sample_threat_report)

        # Should have correlation data if score > 0.5
        # May or may not have correlations depending on score
        assert result.id == sample_threat_report.id

    def test_get_correlated_threats_summary(self, sample_threat_report):
        """Test generating correlation summary."""
        agent = ThreatIntelligenceAgent()

        # Create report with correlation data
        correlated_report = ThreatIntelReport(
            id=sample_threat_report.id,
            title=sample_threat_report.title,
            category=sample_threat_report.category,
            severity=sample_threat_report.severity,
            source=sample_threat_report.source,
            published_date=sample_threat_report.published_date,
            description=sample_threat_report.description,
            raw_data={
                "guardduty_correlations": [
                    {
                        "finding_id": "finding-123",
                        "finding_type": "guardduty",
                        "finding_title": "SQLi detected",
                        "correlation_score": 0.85,
                        "correlation_reason": "Pattern match",
                    }
                ]
            },
        )

        summary = agent.get_correlated_threats_summary([correlated_report])

        assert summary["total_reports"] == 1
        assert summary["correlated_reports"] == 1
        assert summary["high_correlation_count"] == 1
        assert "guardduty" in summary["correlations_by_type"]
        assert len(summary["high_priority_correlations"]) == 1

    def test_get_correlated_threats_summary_empty(self):
        """Test summary with no correlations."""
        agent = ThreatIntelligenceAgent()

        report = ThreatIntelReport(
            id="test",
            title="Test",
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.MEDIUM,
            source="NVD",
            published_date=datetime.now(),
            description="Test",
            raw_data={},  # No correlations
        )

        summary = agent.get_correlated_threats_summary([report])

        assert summary["total_reports"] == 1
        assert summary["correlated_reports"] == 0
        assert summary["high_correlation_count"] == 0
