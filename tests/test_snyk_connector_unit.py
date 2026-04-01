"""
Tests for Snyk Connector Service.

Uses unittest.mock for mocking aiohttp HTTP requests.
Target: 60%+ coverage
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set enterprise mode before importing
os.environ["AURA_INTEGRATION_MODE"] = "enterprise"

# Import the module - clear any cached imports first
import sys

if "src.services.snyk_connector" in sys.modules:
    del sys.modules["src.services.snyk_connector"]
if "src.config" in sys.modules:
    from src.config.integration_config import clear_integration_config_cache

    clear_integration_config_cache()

import aiohttp

from src.services.external_tool_connectors import ConnectorResult, ConnectorStatus
from src.services.snyk_connector import (
    SnykConnector,
    SnykExploitMaturity,
    SnykIssue,
    SnykIssueType,
    SnykProject,
    SnykProjectType,
    SnykSeverity,
    SnykVulnerability,
)

# Note: Forked marker removed to enable proper coverage collection
# The services/__init__.py now catches RuntimeError from torch

# =============================================================================
# URL Constants
# =============================================================================

SNYK_V1_URL = "https://api.snyk.io/v1"
SNYK_REST_URL = "https://api.snyk.io/rest"


# =============================================================================
# Mock Helper Functions
# =============================================================================


def create_mock_response(status_code: int, json_data):
    """Create a mock aiohttp response as an async context manager."""
    mock_response = MagicMock()
    mock_response.status = status_code
    mock_response.json = AsyncMock(return_value=json_data)
    return mock_response


def create_mock_session(mock_response):
    """Create a mock aiohttp ClientSession with proper async context manager support."""
    # Create the inner context manager for get/post responses
    inner_cm = MagicMock()
    inner_cm.__aenter__ = AsyncMock(return_value=mock_response)
    inner_cm.__aexit__ = AsyncMock(return_value=None)

    # Create the session mock
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=inner_cm)
    mock_session.post = MagicMock(return_value=inner_cm)

    # Make session itself an async context manager
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


def create_exception_session(exception: Exception):
    """Create a mock session that raises an exception on get/post."""
    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=exception)
    mock_session.post = MagicMock(side_effect=exception)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


# =============================================================================
# SnykSeverity Enum Tests
# =============================================================================


class TestSnykSeverity:
    """Tests for SnykSeverity enum."""

    def test_critical(self):
        """Test critical severity."""
        assert SnykSeverity.CRITICAL.value == "critical"

    def test_high(self):
        """Test high severity."""
        assert SnykSeverity.HIGH.value == "high"

    def test_medium(self):
        """Test medium severity."""
        assert SnykSeverity.MEDIUM.value == "medium"

    def test_low(self):
        """Test low severity."""
        assert SnykSeverity.LOW.value == "low"

    def test_severity_count(self):
        """Test that all 4 severities exist."""
        assert len(SnykSeverity) == 4


# =============================================================================
# SnykExploitMaturity Enum Tests
# =============================================================================


class TestSnykExploitMaturity:
    """Tests for SnykExploitMaturity enum."""

    def test_no_known_exploit(self):
        """Test no known exploit maturity."""
        assert SnykExploitMaturity.NO_KNOWN_EXPLOIT.value == "No Known Exploit"

    def test_proof_of_concept(self):
        """Test proof of concept maturity."""
        assert SnykExploitMaturity.PROOF_OF_CONCEPT.value == "Proof of Concept"

    def test_functional(self):
        """Test functional exploit maturity."""
        assert SnykExploitMaturity.FUNCTIONAL.value == "Functional"

    def test_mature(self):
        """Test mature exploit maturity."""
        assert SnykExploitMaturity.MATURE.value == "Mature"

    def test_maturity_count(self):
        """Test that all 4 maturity levels exist."""
        assert len(SnykExploitMaturity) == 4


# =============================================================================
# SnykIssueType Enum Tests
# =============================================================================


class TestSnykIssueType:
    """Tests for SnykIssueType enum."""

    def test_vuln(self):
        """Test vulnerability type."""
        assert SnykIssueType.VULN.value == "vuln"

    def test_license(self):
        """Test license issue type."""
        assert SnykIssueType.LICENSE.value == "license"

    def test_code(self):
        """Test code issue type."""
        assert SnykIssueType.CODE.value == "code"

    def test_type_count(self):
        """Test that all 3 types exist."""
        assert len(SnykIssueType) == 3


# =============================================================================
# SnykProjectType Enum Tests
# =============================================================================


class TestSnykProjectType:
    """Tests for SnykProjectType enum."""

    def test_npm(self):
        """Test npm project type."""
        assert SnykProjectType.NPM.value == "npm"

    def test_maven(self):
        """Test maven project type."""
        assert SnykProjectType.MAVEN.value == "maven"

    def test_gradle(self):
        """Test gradle project type."""
        assert SnykProjectType.GRADLE.value == "gradle"

    def test_pip(self):
        """Test pip project type."""
        assert SnykProjectType.PIP.value == "pip"

    def test_poetry(self):
        """Test poetry project type."""
        assert SnykProjectType.POETRY.value == "poetry"

    def test_gomodules(self):
        """Test gomodules project type."""
        assert SnykProjectType.GOMODULES.value == "gomodules"

    def test_nuget(self):
        """Test nuget project type."""
        assert SnykProjectType.NUGET.value == "nuget"

    def test_docker(self):
        """Test docker project type."""
        assert SnykProjectType.DOCKER.value == "docker"

    def test_rubygems(self):
        """Test rubygems project type."""
        assert SnykProjectType.RUBYGEMS.value == "rubygems"

    def test_composer(self):
        """Test composer project type."""
        assert SnykProjectType.COMPOSER.value == "composer"

    def test_cocoapods(self):
        """Test cocoapods project type."""
        assert SnykProjectType.COCOAPODS.value == "cocoapods"

    def test_hex(self):
        """Test hex project type."""
        assert SnykProjectType.HEX.value == "hex"

    def test_deb(self):
        """Test deb project type."""
        assert SnykProjectType.DEB.value == "deb"

    def test_rpm(self):
        """Test rpm project type."""
        assert SnykProjectType.RPM.value == "rpm"

    def test_apk(self):
        """Test apk project type."""
        assert SnykProjectType.APK.value == "apk"

    def test_project_type_count(self):
        """Test that all 15 project types exist."""
        assert len(SnykProjectType) == 15


# =============================================================================
# SnykVulnerability Dataclass Tests
# =============================================================================


class TestSnykVulnerability:
    """Tests for SnykVulnerability dataclass."""

    def test_create_basic_vulnerability(self):
        """Test creating a basic vulnerability."""
        vuln = SnykVulnerability(
            id="SNYK-JS-LODASH-1234",
            title="Prototype Pollution in lodash",
            severity=SnykSeverity.HIGH,
            package_name="lodash",
            version="4.17.15",
        )
        assert vuln.id == "SNYK-JS-LODASH-1234"
        assert vuln.title == "Prototype Pollution in lodash"
        assert vuln.severity == SnykSeverity.HIGH
        assert vuln.package_name == "lodash"
        assert vuln.version == "4.17.15"

    def test_default_values(self):
        """Test default values for optional fields."""
        vuln = SnykVulnerability(
            id="SNYK-TEST-001",
            title="Test Vuln",
            severity=SnykSeverity.MEDIUM,
            package_name="test-pkg",
            version="1.0.0",
        )
        assert vuln.cve_ids == []
        assert vuln.cwe_ids == []
        assert vuln.cvss_score is None
        assert vuln.exploit_maturity is None
        assert vuln.description == ""
        assert vuln.remediation == ""
        assert vuln.fixed_in == []
        assert vuln.introduced_through == []
        assert vuln.is_upgradable is False
        assert vuln.is_patchable is False
        assert vuln.publication_date is None
        assert vuln.disclosure_date is None
        assert vuln.url is None

    def test_full_vulnerability(self):
        """Test vulnerability with all fields."""
        vuln = SnykVulnerability(
            id="SNYK-JS-LODASH-5678",
            title="Command Injection",
            severity=SnykSeverity.CRITICAL,
            package_name="lodash",
            version="4.17.10",
            cve_ids=["CVE-2024-1234"],
            cwe_ids=["CWE-78"],
            cvss_score=9.8,
            exploit_maturity=SnykExploitMaturity.MATURE,
            description="A critical vulnerability",
            remediation="Upgrade to 4.17.21",
            fixed_in=["4.17.21"],
            introduced_through=["express@4.0.0"],
            is_upgradable=True,
            is_patchable=True,
            publication_date="2024-01-01",
            disclosure_date="2024-01-02",
            url="https://snyk.io/vuln/SNYK-JS-LODASH-5678",
        )
        assert vuln.cve_ids == ["CVE-2024-1234"]
        assert vuln.cvss_score == 9.8
        assert vuln.is_upgradable is True
        assert vuln.exploit_maturity == SnykExploitMaturity.MATURE


# =============================================================================
# SnykProject Dataclass Tests
# =============================================================================


class TestSnykProject:
    """Tests for SnykProject dataclass."""

    def test_create_basic_project(self):
        """Test creating a basic project."""
        project = SnykProject(
            id="proj-123",
            name="my-app",
        )
        assert project.id == "proj-123"
        assert project.name == "my-app"

    def test_default_values(self):
        """Test default values for optional fields."""
        project = SnykProject(
            id="proj-123",
            name="my-app",
        )
        assert project.project_type is None
        assert project.origin is None
        assert project.target_reference is None
        assert project.branch is None
        assert project.issue_counts == {}
        assert project.last_tested is None
        assert project.created is None

    def test_full_project(self):
        """Test project with all fields."""
        project = SnykProject(
            id="proj-456",
            name="my-api",
            project_type=SnykProjectType.NPM,
            origin="github",
            target_reference="my-org/my-api",
            branch="main",
            issue_counts={"critical": 2, "high": 5, "medium": 10, "low": 3},
            last_tested="2024-01-15T10:00:00Z",
            created="2024-01-01T00:00:00Z",
        )
        assert project.project_type == SnykProjectType.NPM
        assert project.origin == "github"
        assert project.issue_counts["critical"] == 2


# =============================================================================
# SnykIssue Dataclass Tests
# =============================================================================


class TestSnykIssue:
    """Tests for SnykIssue dataclass."""

    def test_create_basic_issue(self):
        """Test creating a basic issue."""
        issue = SnykIssue(
            id="SNYK-JS-TEST-001",
            issue_type=SnykIssueType.VULN,
            package_name="test-pkg",
            version="1.0.0",
            severity=SnykSeverity.HIGH,
            title="Test Vulnerability",
            project_id="proj-123",
        )
        assert issue.id == "SNYK-JS-TEST-001"
        assert issue.issue_type == SnykIssueType.VULN
        assert issue.severity == SnykSeverity.HIGH

    def test_default_values(self):
        """Test default values for optional fields."""
        issue = SnykIssue(
            id="SNYK-JS-TEST-002",
            issue_type=SnykIssueType.LICENSE,
            package_name="gpl-pkg",
            version="2.0.0",
            severity=SnykSeverity.MEDIUM,
            title="GPL License",
            project_id="proj-456",
        )
        assert issue.introduced_through == []
        assert issue.is_fixed is False
        assert issue.fix_info == {}


# =============================================================================
# SnykConnector Initialization Tests
# =============================================================================


class TestSnykConnectorInit:
    """Tests for SnykConnector initialization."""

    def test_basic_initialization(self):
        """Test basic connector initialization."""
        connector = SnykConnector(token="test-token")
        assert connector._token == "test-token"
        assert connector.org_id is None
        assert connector.group_id is None

    def test_initialization_with_org(self):
        """Test initialization with organization."""
        connector = SnykConnector(
            token="test-token",
            org_id="org-123",
        )
        assert connector.org_id == "org-123"

    def test_initialization_with_group(self):
        """Test initialization with group."""
        connector = SnykConnector(
            token="test-token",
            group_id="grp-123",
        )
        assert connector.group_id == "grp-123"

    def test_api_version(self):
        """Test API version setting."""
        connector = SnykConnector(
            token="test-token",
            api_version="2024-06-01",
        )
        assert connector.api_version == "2024-06-01"

    def test_timeout_setting(self):
        """Test custom timeout."""
        connector = SnykConnector(
            token="test-token",
            timeout_seconds=60.0,
        )
        assert connector.timeout.total == 60.0


# =============================================================================
# SnykConnector Header Tests
# =============================================================================


class TestSnykConnectorHeaders:
    """Tests for SnykConnector header generation."""

    def test_get_headers_v1(self):
        """Test getting headers for V1 API."""
        connector = SnykConnector(token="test-token", org_id="org-123")
        headers = connector._get_headers(use_rest=False)
        assert headers["Authorization"] == "token test-token"
        assert headers["Accept"] == "application/json"
        assert "Content-Type" not in headers

    def test_get_headers_rest(self):
        """Test getting headers for REST API."""
        connector = SnykConnector(token="test-token", org_id="org-123")
        headers = connector._get_headers(use_rest=True)
        assert headers["Authorization"] == "token test-token"
        assert headers["Accept"] == "application/json"
        assert headers["Content-Type"] == "application/vnd.api+json"

    def test_get_rest_url(self):
        """Test building REST URL with version."""
        connector = SnykConnector(token="test-token", org_id="org-123")
        url = connector._get_rest_url("orgs/org-123/projects")
        assert "rest" in url
        assert "version=2024-01-04" in url


# =============================================================================
# SnykConnector API Constants Tests
# =============================================================================


class TestSnykConnectorConstants:
    """Tests for SnykConnector constants."""

    def test_api_v1_url(self):
        """Test V1 API URL constant."""
        assert SnykConnector.API_V1_URL == "https://api.snyk.io/v1"

    def test_api_rest_url(self):
        """Test REST API URL constant."""
        assert SnykConnector.API_REST_URL == "https://api.snyk.io/rest"


# =============================================================================
# SnykConnector URL Building Tests
# =============================================================================


class TestSnykConnectorURLBuilding:
    """Tests for SnykConnector URL building."""

    def test_get_rest_url_simple_path(self):
        """Test REST URL with simple path."""
        connector = SnykConnector(token="test-token", org_id="org-123")
        url = connector._get_rest_url("orgs")
        assert url.startswith("https://api.snyk.io/rest/")
        assert "orgs" in url

    def test_get_rest_url_with_org(self):
        """Test REST URL with organization path."""
        connector = SnykConnector(token="test-token", org_id="org-123")
        url = connector._get_rest_url("orgs/my-org/projects")
        assert "orgs/my-org/projects" in url

    def test_get_rest_url_contains_version(self):
        """Test REST URL contains API version."""
        connector = SnykConnector(token="test-token", org_id="org-123")
        url = connector._get_rest_url("test")
        assert "version=" in url


# =============================================================================
# SnykConnector No Org ID Tests
# =============================================================================


class TestSnykConnectorNoOrgId:
    """Tests for SnykConnector methods that require org_id."""

    @pytest.mark.asyncio
    async def test_list_projects_no_org_id(self):
        """Test project listing fails without org_id."""
        connector = SnykConnector(token="test-token")
        result = await connector.list_projects()
        assert result.success is False
        assert "Organization ID required" in result.error

    @pytest.mark.asyncio
    async def test_get_project_issues_no_org_id(self):
        """Test project issues fails without org_id."""
        connector = SnykConnector(token="test-token")
        result = await connector.get_project_issues("proj-1")
        assert result.success is False
        assert "Organization ID required" in result.error

    @pytest.mark.asyncio
    async def test_get_dependencies_no_org_id(self):
        """Test dependencies fails without org_id."""
        connector = SnykConnector(token="test-token")
        result = await connector.get_project_dependencies("proj-1")
        assert result.success is False
        assert "Organization ID required" in result.error

    @pytest.mark.asyncio
    async def test_ignore_issue_no_org_id(self):
        """Test ignore issue fails without org_id."""
        connector = SnykConnector(token="test-token")
        result = await connector.ignore_issue(
            project_id="proj-1",
            issue_id="SNYK-JS-TEST-001",
            reason="Test",
        )
        assert result.success is False
        assert "Organization ID required" in result.error

    @pytest.mark.asyncio
    async def test_get_org_summary_no_org_id(self):
        """Test org summary fails without org_id."""
        connector = SnykConnector(token="test-token")
        result = await connector.get_org_summary()
        assert result.success is False
        assert "Organization ID required" in result.error


# =============================================================================
# SnykConnector Record Request Tests
# =============================================================================


class TestSnykConnectorRecordRequest:
    """Tests for SnykConnector._record_request method."""

    def test_record_success(self):
        """Test recording successful request."""
        connector = SnykConnector(token="test-token")
        connector._record_request(100.0, True)

        assert connector._request_count == 1
        assert connector._error_count == 0
        assert connector._total_latency_ms == 100.0

    def test_record_failure(self):
        """Test recording failed request."""
        connector = SnykConnector(token="test-token")
        connector._record_request(200.0, False)

        assert connector._request_count == 1
        assert connector._error_count == 1
        assert connector._total_latency_ms == 200.0

    def test_record_multiple(self):
        """Test recording multiple requests."""
        connector = SnykConnector(token="test-token")
        connector._record_request(100.0, True)
        connector._record_request(150.0, True)
        connector._record_request(200.0, False)

        assert connector._request_count == 3
        assert connector._error_count == 1
        assert connector._total_latency_ms == 450.0

    def test_metrics_average_latency(self):
        """Test average latency calculation in metrics."""
        connector = SnykConnector(token="test-token")
        connector._record_request(100.0, True)
        connector._record_request(200.0, True)

        metrics = connector.metrics
        assert metrics["avg_latency_ms"] == 150.0


# =============================================================================
# SnykConnector Metrics Tests
# =============================================================================


class TestSnykConnectorMetrics:
    """Tests for SnykConnector metrics property."""

    def test_metrics_initial_state(self):
        """Test metrics with no requests made."""
        connector = SnykConnector(token="test-token")
        metrics = connector.metrics

        assert metrics["name"] == "snyk"
        assert metrics["status"] == "disconnected"
        assert metrics["request_count"] == 0
        assert metrics["error_count"] == 0
        assert metrics["avg_latency_ms"] == 0.0

    def test_metrics_after_requests(self):
        """Test metrics after recording requests."""
        connector = SnykConnector(token="test-token")
        connector._status = ConnectorStatus.CONNECTED
        connector._record_request(100.0, True)
        connector._record_request(200.0, False)

        metrics = connector.metrics
        assert metrics["status"] == "connected"
        assert metrics["request_count"] == 2
        assert metrics["error_count"] == 1
        assert metrics["avg_latency_ms"] == 150.0


# =============================================================================
# SnykConnector Status Tests
# =============================================================================


class TestSnykConnectorStatus:
    """Tests for SnykConnector status management."""

    def test_initial_status(self):
        """Test initial connector status."""
        connector = SnykConnector(token="test-token")
        assert connector._status == ConnectorStatus.DISCONNECTED

    def test_status_transitions(self):
        """Test status can be changed."""
        connector = SnykConnector(token="test-token")

        connector._status = ConnectorStatus.CONNECTED
        assert connector._status == ConnectorStatus.CONNECTED

        connector._status = ConnectorStatus.AUTH_FAILED
        assert connector._status == ConnectorStatus.AUTH_FAILED

        connector._status = ConnectorStatus.ERROR
        assert connector._status == ConnectorStatus.ERROR


# =============================================================================
# SnykConnector Async HTTP Method Tests (with proper mocking)
# All tests are forked to ensure proper isolation for async mocking
# =============================================================================


# Run all async HTTP tests in forked subprocesses for isolation
pytestmark_http = pytest.mark.forked


class TestSnykConnectorGetVulnerability:
    """Tests for SnykConnector.get_vulnerability method."""

    @pytest.mark.asyncio
    async def test_get_vulnerability_success(self):
        """Test successful vulnerability retrieval."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(
            200,
            {
                "id": "SNYK-JS-LODASH-1234",
                "title": "Prototype Pollution",
                "severity": "high",
                "packageName": "lodash",
                "version": "4.17.15",
                "identifiers": {"CVE": ["CVE-2024-1234"], "CWE": ["CWE-400"]},
                "cvssScore": 7.5,
                "description": "A vulnerability in lodash",
                "remediation": "Upgrade to 4.17.21",
                "fixedIn": ["4.17.21"],
                "isUpgradable": True,
                "isPatchable": False,
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_vulnerability("SNYK-JS-LODASH-1234")

        assert result.success is True
        assert result.status_code == 200
        assert result.data["id"] == "SNYK-JS-LODASH-1234"
        assert result.data["severity"] == "high"

    @pytest.mark.asyncio
    async def test_get_vulnerability_not_found(self):
        """Test vulnerability not found error."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(404, {"message": "Not found"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_vulnerability("SNYK-NOT-FOUND")

        assert result.success is False
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_get_vulnerability_exception(self):
        """Test network error handling."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_session = create_exception_session(Exception("Network timeout"))

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_vulnerability("SNYK-JS-TEST-001")

        assert result.success is False
        assert "Network timeout" in result.error


class TestSnykConnectorSearchByCVE:
    """Tests for SnykConnector.search_vulnerabilities_by_cve method."""

    @pytest.mark.asyncio
    async def test_search_by_cve_success(self):
        """Test successful CVE search."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(
            200,
            [
                {
                    "id": "SNYK-JS-LODASH-1234",
                    "title": "Prototype Pollution",
                    "severity": "high",
                    "packageName": "lodash",
                    "identifiers": {"CVE": ["CVE-2024-1234"]},
                    "cvssScore": 7.5,
                }
            ],
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.search_vulnerabilities_by_cve("CVE-2024-1234")

        assert result.success is True
        assert result.data["cve_id"] == "CVE-2024-1234"
        assert result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_search_by_cve_no_results(self):
        """Test CVE search with no results."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(200, [])
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.search_vulnerabilities_by_cve("CVE-9999-9999")

        assert result.success is True
        assert result.data["count"] == 0


class TestSnykConnectorSearchPackage:
    """Tests for SnykConnector.search_package_vulnerabilities method."""

    @pytest.mark.asyncio
    async def test_search_package_vulns_success(self):
        """Test successful package vulnerability search."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(
            200,
            {
                "ok": False,
                "issues": {
                    "vulnerabilities": [
                        {
                            "id": "SNYK-JS-LODASH-1234",
                            "title": "Prototype Pollution",
                            "severity": "high",
                            "cvssScore": 7.5,
                        }
                    ]
                },
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.search_package_vulnerabilities(
                package_manager="npm",
                package_name="lodash",
                version="4.17.15",
            )

        assert result.success is True
        assert result.data["package"] == "lodash"
        assert result.data["vulnerability_count"] == 1


class TestSnykConnectorListProjectsHTTP:
    """Tests for SnykConnector.list_projects method with HTTP mocking."""

    @pytest.mark.asyncio
    async def test_list_projects_success(self):
        """Test successful project listing."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(
            200,
            {
                "projects": [
                    {
                        "id": "proj-1",
                        "name": "my-app",
                        "type": "npm",
                        "origin": "github",
                        "issueCountsBySeverity": {"critical": 1, "high": 5},
                        "lastTestedDate": "2024-01-15",
                    },
                    {
                        "id": "proj-2",
                        "name": "my-api",
                        "type": "pip",
                    },
                ]
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.list_projects()

        assert result.success is True
        assert result.data["count"] == 2
        assert result.data["projects"][0]["name"] == "my-app"


class TestSnykConnectorGetProjectIssuesHTTP:
    """Tests for SnykConnector.get_project_issues method with HTTP mocking."""

    @pytest.mark.asyncio
    async def test_get_project_issues_success(self):
        """Test successful project issues retrieval."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(
            200,
            {
                "issues": [
                    {
                        "id": "SNYK-JS-LODASH-1234",
                        "issueType": "vuln",
                        "pkgName": "lodash",
                        "pkgVersions": ["4.17.15"],
                        "severity": "high",
                        "title": "Prototype Pollution",
                    }
                ]
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_project_issues("proj-1")

        assert result.success is True
        assert result.data["count"] == 1
        assert "issues" in result.data
        assert "by_severity" in result.data


class TestSnykConnectorGetDependenciesHTTP:
    """Tests for SnykConnector.get_project_dependencies method with HTTP mocking."""

    @pytest.mark.asyncio
    async def test_get_dependencies_success(self):
        """Test successful dependency retrieval."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(
            200,
            {
                "depGraph": {
                    "pkgs": [
                        {
                            "id": "lodash@4.17.15",
                            "info": {"name": "lodash", "version": "4.17.15"},
                        },
                        {
                            "id": "express@4.18.0",
                            "info": {"name": "express", "version": "4.18.0"},
                        },
                    ]
                }
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_project_dependencies("proj-1")

        assert result.success is True
        assert result.data["count"] == 2


class TestSnykConnectorIgnoreIssueHTTP:
    """Tests for SnykConnector.ignore_issue method with HTTP mocking."""

    @pytest.mark.asyncio
    async def test_ignore_issue_success(self):
        """Test successfully ignoring an issue."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(
            200,
            {
                "id": "SNYK-JS-LODASH-1234",
                "ignored": True,
                "reason": "Risk accepted",
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.ignore_issue(
                project_id="proj-1",
                issue_id="SNYK-JS-LODASH-1234",
                reason="Risk accepted",
            )

        assert result.success is True
        # Method returns raw API response
        assert result.data["id"] == "SNYK-JS-LODASH-1234"
        assert result.data["ignored"] is True


class TestSnykConnectorGetOrgSummaryHTTP:
    """Tests for SnykConnector.get_org_summary method with HTTP mocking."""

    @pytest.mark.asyncio
    async def test_get_org_summary_success(self):
        """Test successful organization summary."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        # Mock response matches the actual Snyk org endpoint format
        mock_response = create_mock_response(
            200,
            {
                "name": "Test Org",
                "slug": "test-org",
                "url": "https://snyk.io/org/test-org",
                "created": "2023-01-01T00:00:00Z",
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_org_summary()

        assert result.success is True
        # Method extracts name, slug, url, created from response
        assert result.data["name"] == "Test Org"
        assert result.data["slug"] == "test-org"


class TestSnykConnectorHealthCheckHTTP:
    """Tests for SnykConnector.health_check method with HTTP mocking."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(
            200, {"id": "user-123", "username": "testuser"}
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.health_check()

        assert result is True
        assert connector._status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_health_check_auth_failed(self):
        """Test health check with auth failure."""
        connector = SnykConnector(token="invalid-token", org_id="org-123")

        mock_response = create_mock_response(401, {"message": "Unauthorized"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.health_check()

        assert result is False
        assert connector._status == ConnectorStatus.AUTH_FAILED

    @pytest.mark.asyncio
    async def test_health_check_network_error(self):
        """Test health check with network error."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_session = create_exception_session(Exception("Connection refused"))

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.health_check()

        assert result is False


class TestSnykConnectorGetVulnerabilityReport:
    """Tests for SnykConnector.get_vulnerability_report method."""

    @pytest.mark.asyncio
    async def test_get_vulnerability_report_success(self):
        """Test successful vulnerability report.

        Note: get_vulnerability_report calls list_projects then get_project_issues for each.
        We mock both calls to return consistent data.
        """
        connector = SnykConnector(token="test-token", org_id="org-123")

        # The method calls list_projects first, then get_project_issues for each project
        # We need to mock multiple responses - use side_effect to return different responses
        projects_response = create_mock_response(
            200, {"projects": [{"id": "proj-1", "name": "my-app"}]}
        )
        issues_response = create_mock_response(200, {"issues": []})

        # Create mock that returns different responses for different calls
        call_count = [0]

        def get_mock_response(*args, **kwargs):
            inner_cm = MagicMock()
            if call_count[0] == 0:
                inner_cm.__aenter__ = AsyncMock(return_value=projects_response)
            else:
                inner_cm.__aenter__ = AsyncMock(return_value=issues_response)
            inner_cm.__aexit__ = AsyncMock(return_value=None)
            call_count[0] += 1
            return inner_cm

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=get_mock_response)
        mock_session.post = MagicMock(side_effect=get_mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_vulnerability_report()

        assert result.success is True
        # Method returns summary, issues, generated_at
        assert "summary" in result.data
        assert "issues" in result.data
        assert "generated_at" in result.data


# =============================================================================
# Additional Error Handling Tests for Coverage
# =============================================================================


class TestSnykConnectorListProjectsErrors:
    """Tests for list_projects error handling."""

    @pytest.mark.asyncio
    async def test_list_projects_api_error(self):
        """Test list_projects with API error response."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(500, {"message": "Internal Server Error"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.list_projects()

        assert result.success is False
        assert result.status_code == 500
        assert "Internal Server Error" in result.error

    @pytest.mark.asyncio
    async def test_list_projects_network_error(self):
        """Test list_projects with network exception."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_session = create_exception_session(Exception("Connection timeout"))

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.list_projects()

        assert result.success is False
        assert "Connection timeout" in result.error

    @pytest.mark.asyncio
    async def test_list_projects_with_filters(self):
        """Test list_projects with target and origin filters."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(200, {"projects": []})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.list_projects(
                target_reference="my-repo", origin="github", limit=50
            )

        assert result.success is True
        assert result.data["count"] == 0


class TestSnykConnectorGetProjectIssuesErrors:
    """Tests for get_project_issues error handling."""

    @pytest.mark.asyncio
    async def test_get_project_issues_api_error(self):
        """Test get_project_issues with API error."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(403, {"message": "Forbidden"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_project_issues("proj-1")

        assert result.success is False
        assert result.status_code == 403

    @pytest.mark.asyncio
    async def test_get_project_issues_network_error(self):
        """Test get_project_issues with network exception."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_session = create_exception_session(Exception("Network unreachable"))

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_project_issues("proj-1")

        assert result.success is False
        assert "Network unreachable" in result.error

    @pytest.mark.asyncio
    async def test_get_project_issues_with_filters(self):
        """Test get_project_issues with severity and type filters."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(200, {"issues": []})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_project_issues(
                "proj-1",
                severity=SnykSeverity.HIGH,
                issue_type=SnykIssueType.VULN,
                exploitable=True,
            )

        assert result.success is True


class TestSnykConnectorIgnoreIssueErrors:
    """Tests for ignore_issue error handling."""

    @pytest.mark.asyncio
    async def test_ignore_issue_api_error(self):
        """Test ignore_issue with API error."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(404, {"message": "Issue not found"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.ignore_issue(
                project_id="proj-1", issue_id="SNYK-XXX-0000", reason="Test"
            )

        assert result.success is False
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_ignore_issue_network_error(self):
        """Test ignore_issue with network exception."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_session = create_exception_session(Exception("DNS resolution failed"))

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.ignore_issue(
                project_id="proj-1", issue_id="SNYK-XXX-0000", reason="Test"
            )

        assert result.success is False
        assert "DNS resolution failed" in result.error

    @pytest.mark.asyncio
    async def test_ignore_issue_with_expiration(self):
        """Test ignore_issue with expiration date."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(
            201, {"id": "SNYK-JS-LODASH-1234", "ignored": True, "expires": "2025-12-31"}
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.ignore_issue(
                project_id="proj-1",
                issue_id="SNYK-JS-LODASH-1234",
                reason="Temporary ignore",
                reason_type="temporary-ignore",
                expires_at="2025-12-31",
            )

        assert result.success is True


class TestSnykConnectorGetOrgSummaryErrors:
    """Tests for get_org_summary error handling."""

    @pytest.mark.asyncio
    async def test_get_org_summary_api_error(self):
        """Test get_org_summary with API error."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(401, {"message": "Unauthorized"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_org_summary()

        assert result.success is False
        assert result.status_code == 401

    @pytest.mark.asyncio
    async def test_get_org_summary_network_error(self):
        """Test get_org_summary with network exception."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_session = create_exception_session(Exception("SSL error"))

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_org_summary()

        assert result.success is False
        assert "SSL error" in result.error


class TestSnykConnectorGetDependenciesErrors:
    """Tests for get_project_dependencies error handling."""

    @pytest.mark.asyncio
    async def test_get_dependencies_api_error(self):
        """Test get_dependencies with API error."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(500, {"message": "Server error"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_project_dependencies("proj-1")

        assert result.success is False
        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_get_dependencies_network_error(self):
        """Test get_dependencies with network exception."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_session = create_exception_session(Exception("Connection reset"))

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_project_dependencies("proj-1")

        assert result.success is False
        assert "Connection reset" in result.error


class TestSnykConnectorGetVulnerabilityErrors:
    """Additional tests for get_vulnerability error handling."""

    @pytest.mark.asyncio
    async def test_get_vulnerability_api_error(self):
        """Test get_vulnerability with 500 error."""
        connector = SnykConnector(token="test-token")

        mock_response = create_mock_response(500, {"message": "Server error"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_vulnerability("SNYK-JS-TEST-1234")

        assert result.success is False
        assert result.status_code == 500


class TestSnykConnectorSearchByCVEErrors:
    """Tests for search_vulnerabilities_by_cve error handling."""

    @pytest.mark.asyncio
    async def test_search_by_cve_api_error(self):
        """Test search_by_cve with API error."""
        connector = SnykConnector(token="test-token")

        mock_response = create_mock_response(429, {"message": "Rate limited"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.search_vulnerabilities_by_cve("CVE-2021-44228")

        assert result.success is False
        assert result.status_code == 429

    @pytest.mark.asyncio
    async def test_search_by_cve_network_error(self):
        """Test search_by_cve with network exception."""
        connector = SnykConnector(token="test-token")

        mock_session = create_exception_session(Exception("Timeout exceeded"))

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.search_vulnerabilities_by_cve("CVE-2021-44228")

        assert result.success is False
        assert "Timeout exceeded" in result.error


class TestSnykConnectorSearchPackageErrors:
    """Tests for search_package_vulnerabilities error handling."""

    @pytest.mark.asyncio
    async def test_search_package_api_error(self):
        """Test search_package with API error."""
        connector = SnykConnector(token="test-token")

        mock_response = create_mock_response(400, {"message": "Bad request"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.search_package_vulnerabilities("npm", "lodash")

        assert result.success is False
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_search_package_network_error(self):
        """Test search_package with network exception."""
        connector = SnykConnector(token="test-token")

        mock_session = create_exception_session(Exception("Host unreachable"))

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.search_package_vulnerabilities("npm", "lodash")

        assert result.success is False
        assert "Host unreachable" in result.error


class TestSnykConnectorVulnReportErrors:
    """Tests for get_vulnerability_report error handling."""

    @pytest.mark.asyncio
    async def test_vulnerability_report_list_projects_fails(self):
        """Test vulnerability report when list_projects fails."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(500, {"message": "Server error"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_vulnerability_report()

        assert result.success is False


class TestSnykConnectorVulnReportWithIssues:
    """Tests for get_vulnerability_report with actual issues data.

    These tests mock list_projects and get_project_issues directly on the
    connector instance since get_vulnerability_report calls these methods
    internally. This is simpler than mocking multiple ClientSession instances.
    """

    @pytest.mark.asyncio
    async def test_vulnerability_report_with_issues(self):
        """Test vulnerability report with projects that have issues."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        # Mock data
        projects_result = ConnectorResult(
            success=True,
            data={"projects": [{"id": "proj-1", "name": "my-app"}]},
            latency_ms=10,
        )
        issues_result = ConnectorResult(
            success=True,
            data={
                "issues": [
                    {
                        "id": "SNYK-JS-LODASH-1234",
                        "issueType": "vuln",
                        "pkgName": "lodash",
                        "pkgVersions": ["4.17.15"],
                        "severity": "critical",
                        "title": "Prototype Pollution",
                        "is_fixed": True,
                    },
                    {
                        "id": "SNYK-JS-EXPRESS-5678",
                        "issueType": "vuln",
                        "pkgName": "express",
                        "pkgVersions": ["4.17.0"],
                        "severity": "high",
                        "title": "Open Redirect",
                        "is_fixed": False,
                    },
                ]
            },
            latency_ms=15,
        )

        # Use AsyncMock for async methods
        mock_list = AsyncMock(return_value=projects_result)
        mock_issues = AsyncMock(return_value=issues_result)

        with (
            patch.object(connector, "list_projects", mock_list),
            patch.object(connector, "get_project_issues", mock_issues),
        ):
            result = await connector.get_vulnerability_report()

        assert result.success is True
        assert result.data["summary"]["projects_with_issues"] == 1
        assert result.data["summary"]["total_vulnerabilities"] == 2
        assert result.data["summary"]["by_severity"]["critical"] == 1
        assert result.data["summary"]["by_severity"]["high"] == 1
        assert result.data["summary"]["fixable"] == 1
        mock_list.assert_called_once()
        mock_issues.assert_called_once_with(project_id="proj-1", severity=None)

    @pytest.mark.asyncio
    async def test_vulnerability_report_exploitable_only(self):
        """Test vulnerability report with exploitable_only filter."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        projects_result = ConnectorResult(
            success=True,
            data={"projects": [{"id": "proj-1", "name": "my-app"}]},
            latency_ms=10,
        )
        issues_result = ConnectorResult(
            success=True,
            data={
                "issues": [
                    {
                        "id": "SNYK-JS-LODASH-1234",
                        "severity": "critical",
                        "exploit_maturity": "mature",
                    },
                    {
                        "id": "SNYK-JS-EXPRESS-5678",
                        "severity": "high",
                        "exploit_maturity": "no-known-exploit",
                    },
                    {
                        "id": "SNYK-JS-AXIOS-9999",
                        "severity": "medium",
                        "exploit_maturity": None,
                    },
                ]
            },
            latency_ms=15,
        )

        # Use AsyncMock for async methods
        mock_list = AsyncMock(return_value=projects_result)
        mock_issues = AsyncMock(return_value=issues_result)

        with (
            patch.object(connector, "list_projects", mock_list),
            patch.object(connector, "get_project_issues", mock_issues),
        ):
            result = await connector.get_vulnerability_report(exploitable_only=True)

        assert result.success is True
        # Only the "mature" exploit should be included
        assert result.data["summary"]["total_vulnerabilities"] == 1
        assert result.data["summary"]["by_severity"]["critical"] == 1

    @pytest.mark.asyncio
    async def test_vulnerability_report_multiple_projects(self):
        """Test vulnerability report with multiple projects."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        projects_result = ConnectorResult(
            success=True,
            data={
                "projects": [
                    {"id": "proj-1", "name": "app-frontend"},
                    {"id": "proj-2", "name": "app-backend"},
                ]
            },
            latency_ms=10,
        )

        # Return different issues for each project using async function
        async def mock_get_issues(project_id, severity=None):
            if project_id == "proj-1":
                return ConnectorResult(
                    success=True,
                    data={
                        "issues": [
                            {"id": "VULN-1", "severity": "critical", "is_fixed": False}
                        ]
                    },
                    latency_ms=15,
                )
            else:
                return ConnectorResult(
                    success=True,
                    data={
                        "issues": [
                            {"id": "VULN-2", "severity": "medium", "is_fixed": True},
                            {"id": "VULN-3", "severity": "low", "is_fixed": False},
                        ]
                    },
                    latency_ms=15,
                )

        # Use AsyncMock for async methods
        mock_list = AsyncMock(return_value=projects_result)

        with (
            patch.object(connector, "list_projects", mock_list),
            patch.object(connector, "get_project_issues", side_effect=mock_get_issues),
        ):
            result = await connector.get_vulnerability_report()

        assert result.success is True
        assert result.data["summary"]["total_projects"] == 2
        assert result.data["summary"]["projects_with_issues"] == 2
        assert result.data["summary"]["total_vulnerabilities"] == 3
        assert result.data["summary"]["by_severity"]["critical"] == 1
        assert result.data["summary"]["by_severity"]["medium"] == 1
        assert result.data["summary"]["by_severity"]["low"] == 1
        assert result.data["summary"]["fixable"] == 1

    @pytest.mark.asyncio
    async def test_vulnerability_report_project_with_no_issues(self):
        """Test vulnerability report with a project that has no issues."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        projects_result = ConnectorResult(
            success=True,
            data={"projects": [{"id": "proj-1", "name": "clean-app"}]},
            latency_ms=10,
        )
        issues_result = ConnectorResult(
            success=True,
            data={"issues": []},
            latency_ms=15,
        )

        # Use AsyncMock for async methods
        mock_list = AsyncMock(return_value=projects_result)
        mock_issues = AsyncMock(return_value=issues_result)

        with (
            patch.object(connector, "list_projects", mock_list),
            patch.object(connector, "get_project_issues", mock_issues),
        ):
            result = await connector.get_vulnerability_report()

        assert result.success is True
        assert result.data["summary"]["total_projects"] == 1
        assert result.data["summary"]["projects_with_issues"] == 0
        assert result.data["summary"]["total_vulnerabilities"] == 0

    @pytest.mark.asyncio
    async def test_vulnerability_report_with_severity_filter(self):
        """Test vulnerability report passes severity to get_project_issues."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        projects_result = ConnectorResult(
            success=True,
            data={"projects": [{"id": "proj-1", "name": "my-app"}]},
            latency_ms=10,
        )
        issues_result = ConnectorResult(
            success=True,
            data={"issues": [{"id": "VULN-1", "severity": "critical"}]},
            latency_ms=15,
        )

        # Use AsyncMock for async methods
        mock_list = AsyncMock(return_value=projects_result)
        mock_issues = AsyncMock(return_value=issues_result)

        with (
            patch.object(connector, "list_projects", mock_list),
            patch.object(connector, "get_project_issues", mock_issues),
        ):
            result = await connector.get_vulnerability_report(severity="critical")

        assert result.success is True
        mock_issues.assert_called_once_with(project_id="proj-1", severity="critical")


class TestSnykConnectorHealthCheckErrors:
    """Tests for health_check with various HTTP status codes."""

    @pytest.mark.asyncio
    async def test_health_check_server_error(self):
        """Test health check with 500 server error."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(500, {"message": "Internal Server Error"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.health_check()

        assert result is False
        assert connector._status == ConnectorStatus.ERROR
        assert "HTTP 500" in connector._last_error

    @pytest.mark.asyncio
    async def test_health_check_service_unavailable(self):
        """Test health check with 503 service unavailable."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(503, {"message": "Service Unavailable"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.health_check()

        assert result is False
        assert connector._status == ConnectorStatus.ERROR
        assert "HTTP 503" in connector._last_error

    @pytest.mark.asyncio
    async def test_health_check_forbidden(self):
        """Test health check with 403 forbidden."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(403, {"message": "Forbidden"})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.health_check()

        assert result is False
        assert connector._status == ConnectorStatus.ERROR


class TestSnykConnectorExploitableFiltering:
    """Tests for exploitable filtering in get_project_issues."""

    @pytest.mark.asyncio
    async def test_get_project_issues_exploitable_false(self):
        """Test get_project_issues with exploitable=False filter."""
        connector = SnykConnector(token="test-token", org_id="org-123")

        mock_response = create_mock_response(200, {"issues": []})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_project_issues(
                "proj-1",
                exploitable=False,
            )

        assert result.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
