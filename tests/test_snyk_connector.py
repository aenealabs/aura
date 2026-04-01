"""
Comprehensive tests for Snyk Connector.

Tests the Snyk API connector for vulnerability management including:
- Vulnerability database queries
- Project scanning and monitoring
- Issue management
- Dependency analysis
- Health checks
"""

import os
import platform
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Use forked mode on non-Linux to prevent state pollution
# Skip forked mode when running coverage to allow proper coverage collection
if platform.system() != "Linux" and not os.environ.get("COVERAGE_RUN"):
    pytestmark = pytest.mark.forked


# =============================================================================
# Fixtures and Mocks
# =============================================================================


@pytest.fixture
def mock_aiohttp_response():
    """Create a mock aiohttp response."""

    def _create_response(status: int, json_data: dict):
        response = AsyncMock()
        response.status = status
        response.json = AsyncMock(return_value=json_data)
        return response

    return _create_response


@pytest.fixture
def mock_session(mock_aiohttp_response):
    """Create a mock aiohttp session."""

    def _create_session(status: int = 200, json_data: dict | None = None):
        session = AsyncMock()
        response = mock_aiohttp_response(status, json_data or {})

        # Make it work as an async context manager
        session.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=response))
        )
        session.post = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=response))
        )

        return session

    return _create_session


@pytest.fixture(autouse=True)
def mock_enterprise_mode():
    """Mock enterprise mode for connector tests.

    The @require_enterprise_mode decorator in integration_config.py calls
    get_integration_config() at runtime, so we need to patch it at that location.
    """
    with patch("src.config.integration_config.get_integration_config") as mock:
        config = MagicMock()
        config.is_enterprise_mode = True
        config.is_defense_mode = False
        config.mode.value = "enterprise"
        mock.return_value = config
        yield mock


# =============================================================================
# Enum Tests
# =============================================================================


class TestSnykEnums:
    """Test Snyk enum values."""

    def test_snyk_severity_values(self):
        """Test SnykSeverity enum values."""
        from src.services.snyk_connector import SnykSeverity

        assert SnykSeverity.CRITICAL.value == "critical"
        assert SnykSeverity.HIGH.value == "high"
        assert SnykSeverity.MEDIUM.value == "medium"
        assert SnykSeverity.LOW.value == "low"

    def test_snyk_exploit_maturity_values(self):
        """Test SnykExploitMaturity enum values."""
        from src.services.snyk_connector import SnykExploitMaturity

        assert SnykExploitMaturity.NO_KNOWN_EXPLOIT.value == "No Known Exploit"
        assert SnykExploitMaturity.PROOF_OF_CONCEPT.value == "Proof of Concept"
        assert SnykExploitMaturity.FUNCTIONAL.value == "Functional"
        assert SnykExploitMaturity.MATURE.value == "Mature"

    def test_snyk_issue_type_values(self):
        """Test SnykIssueType enum values."""
        from src.services.snyk_connector import SnykIssueType

        assert SnykIssueType.VULN.value == "vuln"
        assert SnykIssueType.LICENSE.value == "license"
        assert SnykIssueType.CODE.value == "code"

    def test_snyk_project_type_values(self):
        """Test SnykProjectType enum values."""
        from src.services.snyk_connector import SnykProjectType

        assert SnykProjectType.NPM.value == "npm"
        assert SnykProjectType.MAVEN.value == "maven"
        assert SnykProjectType.PIP.value == "pip"
        assert SnykProjectType.DOCKER.value == "docker"
        assert SnykProjectType.GRADLE.value == "gradle"
        assert SnykProjectType.POETRY.value == "poetry"
        assert SnykProjectType.GOMODULES.value == "gomodules"
        assert SnykProjectType.NUGET.value == "nuget"
        assert SnykProjectType.RUBYGEMS.value == "rubygems"
        assert SnykProjectType.COMPOSER.value == "composer"
        assert SnykProjectType.APK.value == "apk"
        assert SnykProjectType.DEB.value == "deb"
        assert SnykProjectType.RPM.value == "rpm"
        assert SnykProjectType.COCOAPODS.value == "cocoapods"
        assert SnykProjectType.HEX.value == "hex"


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestSnykVulnerability:
    """Test SnykVulnerability dataclass."""

    def test_vulnerability_creation_minimal(self):
        """Test creating vulnerability with minimal fields."""
        from src.services.snyk_connector import SnykSeverity, SnykVulnerability

        vuln = SnykVulnerability(
            id="SNYK-JS-LODASH-1234",
            title="Prototype Pollution",
            severity=SnykSeverity.HIGH,
            package_name="lodash",
            version="4.17.19",
        )

        assert vuln.id == "SNYK-JS-LODASH-1234"
        assert vuln.title == "Prototype Pollution"
        assert vuln.severity == SnykSeverity.HIGH
        assert vuln.package_name == "lodash"
        assert vuln.version == "4.17.19"
        assert vuln.cve_ids == []
        assert vuln.cwe_ids == []
        assert vuln.cvss_score is None
        assert vuln.description == ""
        assert vuln.is_upgradable is False
        assert vuln.is_patchable is False

    def test_vulnerability_creation_full(self):
        """Test creating vulnerability with all fields."""
        from src.services.snyk_connector import (
            SnykExploitMaturity,
            SnykSeverity,
            SnykVulnerability,
        )

        vuln = SnykVulnerability(
            id="SNYK-JS-LODASH-1234",
            title="Prototype Pollution",
            severity=SnykSeverity.CRITICAL,
            package_name="lodash",
            version="4.17.19",
            cve_ids=["CVE-2021-23337"],
            cwe_ids=["CWE-400"],
            cvss_score=9.8,
            exploit_maturity=SnykExploitMaturity.MATURE,
            description="A vulnerability affecting lodash",
            remediation="Upgrade to 4.17.21 or later",
            fixed_in=["4.17.21"],
            introduced_through=["express@4.0.0"],
            is_upgradable=True,
            is_patchable=True,
            publication_date="2021-01-01",
            disclosure_date="2020-12-01",
            url="https://snyk.io/vuln/SNYK-JS-LODASH-1234",
        )

        assert vuln.cvss_score == 9.8
        assert vuln.exploit_maturity == SnykExploitMaturity.MATURE
        assert "CVE-2021-23337" in vuln.cve_ids
        assert vuln.is_upgradable is True
        assert vuln.is_patchable is True
        assert vuln.fixed_in == ["4.17.21"]


class TestSnykProject:
    """Test SnykProject dataclass."""

    def test_project_creation_minimal(self):
        """Test creating project with minimal fields."""
        from src.services.snyk_connector import SnykProject

        project = SnykProject(
            id="proj_123",
            name="my-project",
        )

        assert project.id == "proj_123"
        assert project.name == "my-project"
        assert project.project_type is None
        assert project.origin is None
        assert project.branch is None
        assert project.issue_counts == {}

    def test_project_creation_full(self):
        """Test creating project with all fields."""
        from src.services.snyk_connector import SnykProject, SnykProjectType

        project = SnykProject(
            id="proj_123",
            name="my-project",
            project_type=SnykProjectType.NPM,
            origin="github",
            target_reference="org/repo",
            branch="main",
            issue_counts={"critical": 2, "high": 5},
            last_tested="2025-01-01T00:00:00Z",
            created="2024-01-01T00:00:00Z",
        )

        assert project.project_type == SnykProjectType.NPM
        assert project.origin == "github"
        assert project.branch == "main"
        assert project.issue_counts["critical"] == 2


class TestSnykIssue:
    """Test SnykIssue dataclass."""

    def test_issue_creation(self):
        """Test creating a Snyk issue."""
        from src.services.snyk_connector import SnykIssue, SnykIssueType, SnykSeverity

        issue = SnykIssue(
            id="issue_123",
            issue_type=SnykIssueType.VULN,
            package_name="lodash",
            version="4.17.19",
            severity=SnykSeverity.HIGH,
            title="Prototype Pollution",
            project_id="proj_123",
            introduced_through=["express@4.0.0"],
            is_fixed=False,
            fix_info={"upgrade_to": "4.17.21"},
        )

        assert issue.id == "issue_123"
        assert issue.issue_type == SnykIssueType.VULN
        assert issue.severity == SnykSeverity.HIGH
        assert issue.is_fixed is False
        assert issue.fix_info["upgrade_to"] == "4.17.21"


# =============================================================================
# Connector Initialization Tests
# =============================================================================


class TestSnykConnectorInitialization:
    """Test Snyk connector initialization."""

    def test_connector_initialization_minimal(self):
        """Test connector initialization with minimal args."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")

        assert connector._token == "test-token"
        assert connector.org_id is None
        assert connector.group_id is None
        assert connector.api_version == "2024-01-04"
        assert connector.name == "snyk"

    def test_connector_initialization_full(self):
        """Test connector initialization with all args."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(
            token="test-token",
            org_id="org-xxx",
            group_id="group-yyy",
            api_version="2025-01-01",
            timeout_seconds=60.0,
        )

        assert connector._token == "test-token"
        assert connector.org_id == "org-xxx"
        assert connector.group_id == "group-yyy"
        assert connector.api_version == "2025-01-01"

    def test_get_headers_v1(self):
        """Test getting V1 API headers."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="my-token")
        headers = connector._get_headers(use_rest=False)

        assert headers["Authorization"] == "token my-token"
        assert headers["Accept"] == "application/json"
        assert "Content-Type" not in headers

    def test_get_headers_rest(self):
        """Test getting REST API headers."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="my-token")
        headers = connector._get_headers(use_rest=True)

        assert headers["Authorization"] == "token my-token"
        assert headers["Accept"] == "application/json"
        assert headers["Content-Type"] == "application/vnd.api+json"

    def test_get_rest_url(self):
        """Test REST URL building."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test", api_version="2024-01-04")
        url = connector._get_rest_url("orgs/123/projects")

        assert url == "https://api.snyk.io/rest/orgs/123/projects?version=2024-01-04"


# =============================================================================
# Vulnerability Database Tests
# =============================================================================


class TestGetVulnerability:
    """Test vulnerability lookup."""

    @pytest.mark.asyncio
    async def test_get_vulnerability_success(self):
        """Test successful vulnerability lookup."""
        from src.services.snyk_connector import SnykConnector

        vuln_data = {
            "id": "SNYK-JS-LODASH-1234",
            "title": "Prototype Pollution",
            "severity": "high",
            "packageName": "lodash",
            "version": "4.17.19",
            "identifiers": {"CVE": ["CVE-2021-23337"], "CWE": ["CWE-400"]},
            "cvssScore": 7.4,
            "description": "Prototype pollution vulnerability",
            "remediation": "Upgrade to 4.17.21",
            "fixedIn": ["4.17.21"],
            "isUpgradable": True,
            "isPatchable": False,
            "url": "https://snyk.io/vuln/SNYK-JS-LODASH-1234",
        }

        connector = SnykConnector(token="test-token")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=vuln_data)

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.get_vulnerability("SNYK-JS-LODASH-1234")

        assert result.success is True
        assert result.status_code == 200
        assert result.data["id"] == "SNYK-JS-LODASH-1234"
        assert result.data["severity"] == "high"
        assert result.data["cvss_score"] == 7.4
        assert "CVE-2021-23337" in result.data["cve_ids"]

    @pytest.mark.asyncio
    async def test_get_vulnerability_not_found(self):
        """Test vulnerability not found."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_response.json = AsyncMock(
                return_value={"message": "Vulnerability not found"}
            )

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.get_vulnerability("SNYK-XXX-NOTFOUND")

        assert result.success is False
        assert result.status_code == 404
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_vulnerability_network_error(self):
        """Test vulnerability lookup with network error."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(
                side_effect=Exception("Network error")
            )
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.get_vulnerability("SNYK-JS-LODASH-1234")

        assert result.success is False
        assert "Network error" in result.error


class TestSearchVulnerabilitiesByCVE:
    """Test CVE search."""

    @pytest.mark.asyncio
    async def test_search_by_cve_success(self):
        """Test successful CVE search."""
        from src.services.snyk_connector import SnykConnector

        search_data = [
            {
                "id": "SNYK-JS-LODASH-1234",
                "title": "Prototype Pollution",
                "severity": "high",
                "packageName": "lodash",
                "identifiers": {"CVE": ["CVE-2021-23337"]},
                "cvssScore": 7.4,
            }
        ]

        connector = SnykConnector(token="test-token")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=search_data)

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.search_vulnerabilities_by_cve("CVE-2021-23337")

        assert result.success is True
        assert result.data["count"] >= 1
        assert result.data["cve_id"] == "CVE-2021-23337"

    @pytest.mark.asyncio
    async def test_search_by_cve_no_results(self):
        """Test CVE search with no results."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=[])

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.search_vulnerabilities_by_cve("CVE-9999-99999")

        assert result.success is True
        assert result.data["count"] == 0


class TestSearchPackageVulnerabilities:
    """Test package vulnerability search."""

    @pytest.mark.asyncio
    async def test_search_package_success(self):
        """Test successful package vulnerability search."""
        from src.services.snyk_connector import SnykConnector

        package_data = {
            "ok": False,
            "issues": {
                "vulnerabilities": [
                    {
                        "id": "SNYK-JS-LODASH-1234",
                        "title": "Prototype Pollution",
                        "severity": "high",
                        "cvssScore": 7.4,
                        "identifiers": {"CVE": ["CVE-2021-23337"]},
                        "fixedIn": ["4.17.21"],
                        "isUpgradable": True,
                    }
                ]
            },
        }

        connector = SnykConnector(token="test-token")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=package_data)

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.search_package_vulnerabilities(
                package_manager="npm",
                package_name="lodash",
                version="4.17.19",
            )

        assert result.success is True
        assert result.data["package"] == "lodash"
        assert result.data["version"] == "4.17.19"
        assert result.data["vulnerability_count"] >= 1
        assert result.data["ok"] is False

    @pytest.mark.asyncio
    async def test_search_package_with_slash(self):
        """Test package search with scoped package name (contains /)."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={"ok": True, "issues": {"vulnerabilities": []}}
            )

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.search_package_vulnerabilities(
                package_manager="npm",
                package_name="@scope/package",
            )

        assert result.success is True
        # Verify the URL encoding happened
        call_args = mock_session_instance.get.call_args
        assert "%2F" in str(call_args)  # Slash should be encoded


# =============================================================================
# Project Management Tests
# =============================================================================


class TestListProjects:
    """Test project listing."""

    @pytest.mark.asyncio
    async def test_list_projects_no_org_id(self):
        """Test listing projects without org_id."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")  # No org_id

        result = await connector.list_projects()

        assert result.success is False
        assert "Organization ID required" in result.error

    @pytest.mark.asyncio
    async def test_list_projects_success(self):
        """Test successful project listing."""
        from src.services.snyk_connector import SnykConnector

        projects_data = {
            "projects": [
                {
                    "id": "proj-123",
                    "name": "my-project",
                    "type": "npm",
                    "origin": "github",
                    "targetReference": "org/repo",
                    "branch": "main",
                    "issueCountsBySeverity": {"critical": 2, "high": 5},
                    "lastTestedDate": "2025-01-01T00:00:00Z",
                }
            ]
        }

        connector = SnykConnector(token="test-token", org_id="org-xxx")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=projects_data)

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.list_projects()

        assert result.success is True
        assert result.data["count"] == 1
        assert result.data["projects"][0]["name"] == "my-project"
        assert result.data["projects"][0]["branch"] == "main"

    @pytest.mark.asyncio
    async def test_list_projects_with_filters(self):
        """Test project listing with filters."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token", org_id="org-xxx")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"projects": []})

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.list_projects(
                target_reference="org/repo",
                origin="github",
                limit=50,
            )

        assert result.success is True
        # Verify params were passed
        call_args = mock_session_instance.get.call_args
        assert "params" in call_args.kwargs or len(call_args.args) > 1


class TestGetProjectIssues:
    """Test project issue retrieval."""

    @pytest.mark.asyncio
    async def test_get_project_issues_no_org_id(self):
        """Test getting project issues without org_id."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")  # No org_id

        result = await connector.get_project_issues("proj-123")

        assert result.success is False
        assert "Organization ID required" in result.error

    @pytest.mark.asyncio
    async def test_get_project_issues_success(self):
        """Test successful issue retrieval."""
        from src.services.snyk_connector import SnykConnector

        issues_data = {
            "issues": [
                {
                    "id": "issue-1",
                    "issueType": "vuln",
                    "pkgName": "lodash",
                    "pkgVersions": ["4.17.19"],
                    "severity": "critical",
                    "title": "Prototype Pollution",
                    "introducedThrough": ["express@4.0.0"],
                    "isFixed": False,
                    "issueData": {
                        "cvssScore": 9.8,
                        "identifiers": {"CVE": ["CVE-2021-23337"]},
                    },
                },
                {
                    "id": "issue-2",
                    "issueType": "vuln",
                    "pkgName": "axios",
                    "pkgVersions": ["0.21.0"],
                    "severity": "high",
                    "title": "SSRF",
                    "isFixed": True,
                    "issueData": {},
                },
            ]
        }

        connector = SnykConnector(token="test-token", org_id="org-xxx")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=issues_data)

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.post = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.get_project_issues("proj-123")

        assert result.success is True
        assert result.data["count"] == 2
        assert result.data["by_severity"]["critical"] == 1
        assert result.data["by_severity"]["high"] == 1
        assert result.request_id == "proj-123"

    @pytest.mark.asyncio
    async def test_get_project_issues_with_filters(self):
        """Test issue retrieval with filters."""
        from src.services.snyk_connector import (
            SnykConnector,
            SnykIssueType,
            SnykSeverity,
        )

        connector = SnykConnector(token="test-token", org_id="org-xxx")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"issues": []})

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.post = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.get_project_issues(
                "proj-123",
                severity=SnykSeverity.CRITICAL,
                issue_type=SnykIssueType.VULN,
                exploitable=True,
            )

        assert result.success is True


class TestGetProjectDependencies:
    """Test project dependency retrieval."""

    @pytest.mark.asyncio
    async def test_get_dependencies_no_org_id(self):
        """Test getting dependencies without org_id."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")

        result = await connector.get_project_dependencies("proj-123")

        assert result.success is False
        assert "Organization ID required" in result.error

    @pytest.mark.asyncio
    async def test_get_dependencies_success(self):
        """Test successful dependency retrieval."""
        from src.services.snyk_connector import SnykConnector

        dep_data = {
            "depGraph": {
                "schemaVersion": "1.2.0",
                "pkgs": [
                    {
                        "id": "lodash@4.17.19",
                        "info": {"name": "lodash", "version": "4.17.19"},
                    },
                    {
                        "id": "express@4.17.0",
                        "info": {"name": "express", "version": "4.17.0"},
                    },
                ],
            }
        }

        connector = SnykConnector(token="test-token", org_id="org-xxx")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=dep_data)

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.get_project_dependencies("proj-123")

        assert result.success is True
        assert result.data["count"] == 2
        assert result.data["schema_version"] == "1.2.0"


# =============================================================================
# Issue Management Tests
# =============================================================================


class TestIgnoreIssue:
    """Test issue ignoring."""

    @pytest.mark.asyncio
    async def test_ignore_issue_no_org_id(self):
        """Test ignoring issue without org_id."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")

        result = await connector.ignore_issue("proj-123", "issue-456", "Not applicable")

        assert result.success is False
        assert "Organization ID required" in result.error

    @pytest.mark.asyncio
    async def test_ignore_issue_success(self):
        """Test successful issue ignoring."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token", org_id="org-xxx")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 201
            mock_response.json = AsyncMock(return_value={"ignored": True})

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.post = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.ignore_issue(
                "proj-123",
                "issue-456",
                "Not applicable to our use case",
                reason_type="not-vulnerable",
            )

        assert result.success is True
        assert result.request_id == "issue-456"

    @pytest.mark.asyncio
    async def test_ignore_issue_with_expiry(self):
        """Test ignoring issue with expiration."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token", org_id="org-xxx")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"ignored": True})

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.post = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.ignore_issue(
                "proj-123",
                "issue-456",
                "Temporary ignore",
                reason_type="temporary-ignore",
                expires_at="2025-12-31T23:59:59Z",
            )

        assert result.success is True


# =============================================================================
# Reporting Tests
# =============================================================================


class TestGetOrgSummary:
    """Test organization summary."""

    @pytest.mark.asyncio
    async def test_get_org_summary_no_org_id(self):
        """Test org summary without org_id."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")

        result = await connector.get_org_summary()

        assert result.success is False
        assert "Organization ID required" in result.error

    @pytest.mark.asyncio
    async def test_get_org_summary_success(self):
        """Test successful org summary."""
        from src.services.snyk_connector import SnykConnector

        org_data = {
            "name": "My Org",
            "slug": "my-org",
            "url": "https://snyk.io/org/my-org",
            "created": "2024-01-01T00:00:00Z",
        }

        connector = SnykConnector(token="test-token", org_id="org-xxx")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=org_data)

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.get_org_summary()

        assert result.success is True
        assert result.data["name"] == "My Org"
        assert result.data["slug"] == "my-org"


class TestGetVulnerabilityReport:
    """Test vulnerability report generation."""

    @pytest.mark.asyncio
    async def test_vulnerability_report_success(self):
        """Test successful vulnerability report generation."""
        from src.services.snyk_connector import SnykConnector

        projects_response = {
            "projects": [
                {"id": "proj-1", "name": "project-1"},
                {"id": "proj-2", "name": "project-2"},
            ]
        }

        issues_response = {
            "issues": [
                {
                    "id": "issue-1",
                    "severity": "critical",
                    "pkgName": "lodash",
                    "pkgVersions": ["4.17.19"],
                    "title": "Vuln 1",
                    "isFixed": True,
                    "issueData": {},
                },
            ]
        }

        connector = SnykConnector(token="test-token", org_id="org-xxx")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_get_response = AsyncMock()
            mock_get_response.status = 200
            mock_get_response.json = AsyncMock(return_value=projects_response)

            mock_post_response = AsyncMock()
            mock_post_response.status = 200
            mock_post_response.json = AsyncMock(return_value=issues_response)

            mock_get_ctx = AsyncMock()
            mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_get_response)
            mock_get_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_post_ctx = AsyncMock()
            mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_post_response)
            mock_post_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_get_ctx)
            mock_session_instance.post = MagicMock(return_value=mock_post_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.get_vulnerability_report()

        assert result.success is True
        assert result.data["summary"]["total_projects"] == 2
        assert "generated_at" in result.data


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_auth_failed(self):
        """Test health check with auth failure."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="invalid-token")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 401

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.health_check()

        assert result is False
        assert "Authentication failed" in connector._last_error

    @pytest.mark.asyncio
    async def test_health_check_error(self):
        """Test health check with error."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 500

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(return_value=mock_ctx)
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.health_check()

        assert result is False
        assert "HTTP 500" in connector._last_error

    @pytest.mark.asyncio
    async def test_health_check_network_error(self):
        """Test health check with network error."""
        from src.services.snyk_connector import SnykConnector

        connector = SnykConnector(token="test-token")

        with patch("src.services.snyk_connector.aiohttp.ClientSession") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.get = MagicMock(
                side_effect=Exception("Connection refused")
            )
            mock_session_instance.__aenter__ = AsyncMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await connector.health_check()

        assert result is False
        assert "Connection refused" in connector._last_error
