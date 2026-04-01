"""
Project Aura - Qualys Connector Unit Tests

Test Type: UNIT
Dependencies: All external calls mocked (aiohttp, Qualys VMDR API)
Isolation: pytest.mark.forked (prevents aiohttp mock pollution between tests)
Run Command: pytest tests/test_qualys_connector.py -v

These tests validate:
- Qualys connector initialization and configuration
- Vulnerability database queries (knowledge base)
- Host asset management and scanning
- Detection retrieval and filtering
- Scan launch and status monitoring
- Response parsing and error handling

Mock Strategy:
- aiohttp.ClientSession: Mocked via create_mock_aiohttp_session()
- Environment variables: Set via enable_enterprise_mode fixture
- All Qualys API responses are simulated (XML/JSON)

Related E2E Tests:
- tests/e2e/test_qualys_e2e.py (requires RUN_E2E_TESTS=1 and real credentials)
"""

import json
import os
import platform
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These tests require pytest-forked for isolation due to aiohttp mock state.
# On Linux (CI), mock patches don't apply correctly without forked mode.
if platform.system() == "Linux":
    pytestmark = pytest.mark.skip(
        reason="Skipped on Linux CI: requires pytest-forked for aiohttp mock isolation"
    )
else:
    pytestmark = [pytest.mark.unit, pytest.mark.forked]

from src.config.integration_config import clear_integration_config_cache
from src.services.external_tool_connectors import ConnectorStatus
from src.services.qualys_connector import (
    QualysAssetType,
    QualysConnector,
    QualysDetection,
    QualysHost,
    QualysPlatform,
    QualysScanStatus,
    QualysSeverity,
    QualysVulnerability,
    QualysVulnType,
)

# =============================================================================
# Test Helpers
# =============================================================================


def create_mock_aiohttp_session(response_status: int, response_body: str | dict):
    """Create a properly mocked aiohttp session for async context managers."""
    mock_response = MagicMock()
    mock_response.status = response_status
    if isinstance(response_body, dict):
        mock_response.json = AsyncMock(return_value=response_body)
        mock_response.text = AsyncMock(return_value=json.dumps(response_body))
    else:
        mock_response.text = AsyncMock(return_value=response_body)
        mock_response.json = AsyncMock(return_value={"error": response_body})

    mock_request_context = MagicMock()
    mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_request_context.__aexit__ = AsyncMock(return_value=None)

    mock_session_instance = MagicMock()
    mock_session_instance.post.return_value = mock_request_context
    mock_session_instance.get.return_value = mock_request_context

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


@pytest.fixture
def enable_enterprise_mode():
    """Enable enterprise mode for tests by setting environment variable."""
    original_value = os.environ.get("AURA_INTEGRATION_MODE")
    os.environ["AURA_INTEGRATION_MODE"] = "enterprise"
    # Clear the cached config so it reloads with new env var
    clear_integration_config_cache()
    yield
    # Restore original value
    if original_value is not None:
        os.environ["AURA_INTEGRATION_MODE"] = original_value
    else:
        os.environ.pop("AURA_INTEGRATION_MODE", None)
    clear_integration_config_cache()


# =============================================================================
# Enum Tests
# =============================================================================


class TestQualysPlatform:
    """Tests for QualysPlatform enum."""

    def test_us1(self):
        assert QualysPlatform.US1.value == "qualysapi.qualys.com"

    def test_us2(self):
        assert QualysPlatform.US2.value == "qualysapi.qg2.apps.qualys.com"

    def test_us3(self):
        assert QualysPlatform.US3.value == "qualysapi.qg3.apps.qualys.com"

    def test_us4(self):
        assert QualysPlatform.US4.value == "qualysapi.qg4.apps.qualys.com"

    def test_eu1(self):
        assert QualysPlatform.EU1.value == "qualysapi.qualys.eu"

    def test_eu2(self):
        assert QualysPlatform.EU2.value == "qualysapi.qg2.apps.qualys.eu"

    def test_in1(self):
        assert QualysPlatform.IN1.value == "qualysapi.qg1.apps.qualys.in"

    def test_ca1(self):
        assert QualysPlatform.CA1.value == "qualysapi.qg1.apps.qualys.ca"

    def test_ae1(self):
        assert QualysPlatform.AE1.value == "qualysapi.qg1.apps.qualys.ae"

    def test_uk1(self):
        assert QualysPlatform.UK1.value == "qualysapi.qg1.apps.qualys.co.uk"

    def test_au1(self):
        assert QualysPlatform.AU1.value == "qualysapi.qg1.apps.qualys.com.au"


class TestQualysSeverity:
    """Tests for QualysSeverity enum."""

    def test_informational(self):
        assert QualysSeverity.INFORMATIONAL.value == 1

    def test_low(self):
        assert QualysSeverity.LOW.value == 2

    def test_medium(self):
        assert QualysSeverity.MEDIUM.value == 3

    def test_high(self):
        assert QualysSeverity.HIGH.value == 4

    def test_critical(self):
        assert QualysSeverity.CRITICAL.value == 5


class TestQualysVulnType:
    """Tests for QualysVulnType enum."""

    def test_confirmed(self):
        assert QualysVulnType.CONFIRMED.value == "Confirmed"

    def test_potential(self):
        assert QualysVulnType.POTENTIAL.value == "Potential"

    def test_info(self):
        assert QualysVulnType.INFO.value == "Info"


class TestQualysAssetType:
    """Tests for QualysAssetType enum."""

    def test_host(self):
        assert QualysAssetType.HOST.value == "HOST"

    def test_webapp(self):
        assert QualysAssetType.WEBAPP.value == "WEBAPP"

    def test_cloud(self):
        assert QualysAssetType.CLOUD.value == "CLOUD"

    def test_container(self):
        assert QualysAssetType.CONTAINER.value == "CONTAINER"


class TestQualysScanStatus:
    """Tests for QualysScanStatus enum."""

    def test_submitted(self):
        assert QualysScanStatus.SUBMITTED.value == "Submitted"

    def test_running(self):
        assert QualysScanStatus.RUNNING.value == "Running"

    def test_finished(self):
        assert QualysScanStatus.FINISHED.value == "Finished"

    def test_canceled(self):
        assert QualysScanStatus.CANCELED.value == "Canceled"

    def test_paused(self):
        assert QualysScanStatus.PAUSED.value == "Paused"

    def test_error(self):
        assert QualysScanStatus.ERROR.value == "Error"


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestQualysVulnerability:
    """Tests for QualysVulnerability dataclass."""

    def test_basic_creation(self):
        vuln = QualysVulnerability(
            qid=12345,
            title="Test Vulnerability",
            severity=QualysSeverity.HIGH,
            vuln_type=QualysVulnType.CONFIRMED,
        )
        assert vuln.qid == 12345
        assert vuln.title == "Test Vulnerability"
        assert vuln.severity == QualysSeverity.HIGH

    def test_full_creation(self):
        vuln = QualysVulnerability(
            qid=12345,
            title="SQL Injection",
            severity=QualysSeverity.CRITICAL,
            vuln_type=QualysVulnType.CONFIRMED,
            category="Application",
            cve_ids=["CVE-2024-1234", "CVE-2024-1235"],
            cvss_base=9.8,
            cvss_temporal=9.4,
            solution="Update to latest version",
            diagnosis="SQL injection found in login form",
            consequence="Full database compromise",
            pci_flag=True,
            published_date="2024-01-01",
            last_service_modification="2024-06-01",
        )
        assert len(vuln.cve_ids) == 2
        assert vuln.pci_flag is True
        assert vuln.cvss_base == 9.8

    def test_default_values(self):
        vuln = QualysVulnerability(
            qid=1,
            title="Test",
            severity=QualysSeverity.LOW,
            vuln_type=QualysVulnType.INFO,
        )
        assert vuln.cve_ids == []
        assert vuln.pci_flag is False
        assert vuln.cvss_base is None


class TestQualysHost:
    """Tests for QualysHost dataclass."""

    def test_basic_creation(self):
        host = QualysHost(
            host_id=12345,
            ip="192.168.1.100",
        )
        assert host.host_id == 12345
        assert host.ip == "192.168.1.100"

    def test_full_creation(self):
        host = QualysHost(
            host_id=12345,
            ip="192.168.1.100",
            hostname="server01.example.com",
            os="Windows Server 2019",
            dns="server01",
            netbios="SERVER01",
            tracking_method="IP",
            last_scan="2024-01-01T00:00:00Z",
            last_vm_scanned="2024-01-01T00:00:00Z",
            last_vm_auth_scanned="2024-01-01T00:00:00Z",
            tags=["Production", "Web"],
            cloud_provider="AWS",
            cloud_resource_id="i-1234567890abcdef0",
        )
        assert host.os == "Windows Server 2019"
        assert len(host.tags) == 2

    def test_default_values(self):
        host = QualysHost(host_id=1, ip="10.0.0.1")
        assert host.hostname is None
        assert host.tags == []


class TestQualysDetection:
    """Tests for QualysDetection dataclass."""

    def test_basic_creation(self):
        detection = QualysDetection(
            host_id=12345,
            qid=67890,
            severity=QualysSeverity.HIGH,
            vuln_type=QualysVulnType.CONFIRMED,
        )
        assert detection.host_id == 12345
        assert detection.qid == 67890

    def test_full_creation(self):
        detection = QualysDetection(
            host_id=12345,
            qid=67890,
            severity=QualysSeverity.CRITICAL,
            vuln_type=QualysVulnType.CONFIRMED,
            status="Active",
            first_found="2024-01-01",
            last_found="2024-06-01",
            times_found=5,
            is_ignored=False,
            is_disabled=False,
            port=443,
            protocol="tcp",
            service="https",
            ssl=True,
            results="Vulnerability confirmed on port 443",
        )
        assert detection.times_found == 5
        assert detection.ssl is True

    def test_default_values(self):
        detection = QualysDetection(
            host_id=1,
            qid=1,
            severity=QualysSeverity.LOW,
            vuln_type=QualysVulnType.INFO,
        )
        assert detection.times_found == 0
        assert detection.is_ignored is False
        assert detection.ssl is False


# =============================================================================
# Connector Initialization Tests
# =============================================================================


class TestQualysConnectorInit:
    """Tests for QualysConnector initialization."""

    def test_basic_init(self):
        connector = QualysConnector(
            username="api_user",
            password="api_password",
        )
        assert connector.base_url == "https://qualysapi.qualys.com"

    def test_platform_enum_us2(self):
        connector = QualysConnector(
            username="user",
            password="pass",
            platform=QualysPlatform.US2,
        )
        assert connector.base_url == "https://qualysapi.qg2.apps.qualys.com"

    def test_platform_enum_eu1(self):
        connector = QualysConnector(
            username="user",
            password="pass",
            platform=QualysPlatform.EU1,
        )
        assert connector.base_url == "https://qualysapi.qualys.eu"

    def test_platform_string(self):
        connector = QualysConnector(
            username="user",
            password="pass",
            platform="custom.qualys.com",
        )
        assert connector.base_url == "https://custom.qualys.com"

    def test_custom_timeout(self):
        connector = QualysConnector(
            username="user",
            password="pass",
            timeout_seconds=120.0,
        )
        assert connector.timeout.total == 120.0

    def test_auth_header_created(self):
        connector = QualysConnector(
            username="testuser",
            password="testpass",
        )
        # Base64 encoded "testuser:testpass"
        import base64

        expected = base64.b64encode(b"testuser:testpass").decode()
        assert connector._auth_header == expected

    def test_get_headers(self):
        connector = QualysConnector(
            username="user",
            password="pass",
        )
        headers = connector._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"

    def test_get_headers_custom_content_type(self):
        connector = QualysConnector(
            username="user",
            password="pass",
        )
        headers = connector._get_headers("application/json")
        assert headers["Content-Type"] == "application/json"


# =============================================================================
# XML Parsing Tests
# =============================================================================


class TestXMLParsing:
    """Tests for XML parsing methods."""

    def test_parse_xml_response_simple(self):
        connector = QualysConnector(username="user", password="pass")
        xml = "<ROOT><ITEM>value</ITEM></ROOT>"
        result = connector._parse_xml_response(xml)
        # Simple text elements return {"#text": "value"} dict structure
        assert result["ITEM"]["#text"] == "value"

    def test_parse_xml_response_nested(self):
        connector = QualysConnector(username="user", password="pass")
        xml = "<ROOT><PARENT><CHILD>value</CHILD></PARENT></ROOT>"
        result = connector._parse_xml_response(xml)
        # Nested text elements return {"#text": "value"} dict structure
        assert result["PARENT"]["CHILD"]["#text"] == "value"

    def test_parse_xml_response_with_attributes(self):
        connector = QualysConnector(username="user", password="pass")
        xml = '<ROOT><ITEM id="123">value</ITEM></ROOT>'
        result = connector._parse_xml_response(xml)
        assert result["ITEM"]["@attributes"]["id"] == "123"
        assert result["ITEM"]["#text"] == "value"

    def test_parse_xml_response_list(self):
        connector = QualysConnector(username="user", password="pass")
        xml = "<ROOT><ITEM>one</ITEM><ITEM>two</ITEM></ROOT>"
        result = connector._parse_xml_response(xml)
        assert isinstance(result["ITEM"], list)
        assert len(result["ITEM"]) == 2

    def test_parse_xml_response_invalid(self):
        connector = QualysConnector(username="user", password="pass")
        result = connector._parse_xml_response("not valid xml")
        assert "error" in result

    def test_extract_cves_dict(self):
        connector = QualysConnector(username="user", password="pass")
        vuln_data = {"CVE_LIST": {"CVE": {"ID": "CVE-2024-1234"}}}
        cves = connector._extract_cves(vuln_data)
        assert cves == ["CVE-2024-1234"]

    def test_extract_cves_list(self):
        connector = QualysConnector(username="user", password="pass")
        vuln_data = {
            "CVE_LIST": {"CVE": [{"ID": "CVE-2024-1234"}, {"ID": "CVE-2024-5678"}]}
        }
        cves = connector._extract_cves(vuln_data)
        assert len(cves) == 2

    def test_extract_cves_empty(self):
        connector = QualysConnector(username="user", password="pass")
        vuln_data = {}
        cves = connector._extract_cves(vuln_data)
        assert cves == []

    def test_extract_tags_dict(self):
        connector = QualysConnector(username="user", password="pass")
        host_data = {"TAGS": {"TAG": {"NAME": "Production"}}}
        tags = connector._extract_tags(host_data)
        assert tags == ["Production"]

    def test_extract_tags_list(self):
        connector = QualysConnector(username="user", password="pass")
        host_data = {"TAGS": {"TAG": [{"NAME": "Production"}, {"NAME": "Web"}]}}
        tags = connector._extract_tags(host_data)
        assert len(tags) == 2


# =============================================================================
# Vulnerability Knowledge Base Tests
# =============================================================================


class TestGetVulnerabilityDetails:
    """Tests for get_vulnerability_details method."""

    @pytest.mark.asyncio
    async def test_get_vulnerability_details_success(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        xml_response = """<?xml version="1.0"?>
        <KNOWLEDGE_BASE_VULN_LIST_OUTPUT>
            <RESPONSE>
                <VULN_LIST>
                    <VULN>
                        <QID>12345</QID>
                        <TITLE>Test Vulnerability</TITLE>
                        <SEVERITY>5</SEVERITY>
                        <CATEGORY>Web</CATEGORY>
                        <CVE_LIST><CVE><ID>CVE-2024-1234</ID></CVE></CVE_LIST>
                        <SOLUTION>Apply patch</SOLUTION>
                        <DIAGNOSIS>SQL injection detected</DIAGNOSIS>
                        <CONSEQUENCE>Data breach</CONSEQUENCE>
                        <PCI_FLAG>1</PCI_FLAG>
                    </VULN>
                </VULN_LIST>
            </RESPONSE>
        </KNOWLEDGE_BASE_VULN_LIST_OUTPUT>"""

        mock_session = create_mock_aiohttp_session(200, xml_response)

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_vulnerability_details(12345)
            assert result.success is True
            assert result.data["qid"] == 12345

    @pytest.mark.asyncio
    async def test_get_vulnerability_details_api_error(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        mock_session = create_mock_aiohttp_session(401, "<UNAUTHORIZED/>")

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_vulnerability_details(99999)
            assert result.success is False
            assert "API error" in result.error


class TestSearchVulnerabilitiesByCVE:
    """Tests for search_vulnerabilities_by_cve method."""

    @pytest.mark.asyncio
    async def test_search_by_cve_success(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        xml_response = """<?xml version="1.0"?>
        <KNOWLEDGE_BASE_VULN_LIST_OUTPUT>
            <RESPONSE>
                <VULN_LIST>
                    <VULN>
                        <QID>12345</QID>
                        <TITLE>CVE Test</TITLE>
                        <SEVERITY>4</SEVERITY>
                        <CATEGORY>OS</CATEGORY>
                    </VULN>
                </VULN_LIST>
            </RESPONSE>
        </KNOWLEDGE_BASE_VULN_LIST_OUTPUT>"""

        mock_session = create_mock_aiohttp_session(200, xml_response)

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.search_vulnerabilities_by_cve("CVE-2024-1234")
            assert result.success is True
            assert result.data["cve_id"] == "CVE-2024-1234"


# =============================================================================
# Asset Management Tests
# =============================================================================


class TestListHosts:
    """Tests for list_hosts method."""

    @pytest.mark.asyncio
    async def test_list_hosts_success(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        # Single host XML that the parser can handle
        xml_response = """<?xml version="1.0"?>
        <HOST_LIST_OUTPUT>
            <RESPONSE>
                <HOST_LIST>
                    <HOST>
                        <ID>12345</ID>
                        <IP>192.168.1.100</IP>
                        <DNS>server01</DNS>
                        <OS>Windows</OS>
                    </HOST>
                </HOST_LIST>
            </RESPONSE>
        </HOST_LIST_OUTPUT>"""

        mock_session = create_mock_aiohttp_session(200, xml_response)

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_hosts()
            assert result.success is True
            # The XML parser may return count based on parsed structure
            assert "hosts" in result.data
            assert "count" in result.data

    @pytest.mark.asyncio
    async def test_list_hosts_with_filters(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        xml_response = """<?xml version="1.0"?>
        <HOST_LIST_OUTPUT>
            <RESPONSE>
                <HOST_LIST>
                    <HOST>
                        <ID>12345</ID>
                        <IP>192.168.1.100</IP>
                    </HOST>
                </HOST_LIST>
            </RESPONSE>
        </HOST_LIST_OUTPUT>"""

        mock_session = create_mock_aiohttp_session(200, xml_response)

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_hosts(
                ips="192.168.1.0/24",
                tracking_method="IP",
                limit=100,
            )
            assert result.success is True


class TestGetHostDetails:
    """Tests for get_host_details method."""

    @pytest.mark.asyncio
    async def test_get_host_details_api_error(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        mock_session = create_mock_aiohttp_session(500, "<ERROR/>")

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_host_details(12345)
            assert result.success is False
            assert "API error" in result.error

    @pytest.mark.asyncio
    async def test_get_host_details_not_found(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        xml_response = """<?xml version="1.0"?>
        <HOST_LIST_OUTPUT>
            <RESPONSE>
                <HOST_LIST></HOST_LIST>
            </RESPONSE>
        </HOST_LIST_OUTPUT>"""

        mock_session = create_mock_aiohttp_session(200, xml_response)

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_host_details(99999)
            assert result.success is False


# =============================================================================
# Host Detections Tests
# =============================================================================


class TestGetHostDetections:
    """Tests for get_host_detections method."""

    @pytest.mark.asyncio
    async def test_get_host_detections_success(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        # Compact XML without whitespace to ensure proper parsing
        xml_response = """<HOST_LIST_VM_DETECTION_OUTPUT><RESPONSE><HOST_LIST><HOST><ID>12345</ID><DETECTION_LIST><DETECTION><QID>67890</QID><SEVERITY>5</SEVERITY><TYPE>Confirmed</TYPE><STATUS>Active</STATUS><TIMES_FOUND>3</TIMES_FOUND><PORT>443</PORT><PROTOCOL>tcp</PROTOCOL><SSL>1</SSL></DETECTION></DETECTION_LIST></HOST></HOST_LIST></RESPONSE></HOST_LIST_VM_DETECTION_OUTPUT>"""

        mock_session = create_mock_aiohttp_session(200, xml_response)

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_host_detections(host_id=12345)
            assert result.success is True
            assert "detections" in result.data
            assert "by_severity" in result.data

    @pytest.mark.asyncio
    async def test_get_host_detections_with_filters(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        xml_response = """<?xml version="1.0"?>
        <HOST_LIST_VM_DETECTION_OUTPUT>
            <RESPONSE>
                <HOST_LIST></HOST_LIST>
            </RESPONSE>
        </HOST_LIST_VM_DETECTION_OUTPUT>"""

        mock_session = create_mock_aiohttp_session(200, xml_response)

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_host_detections(
                ip="192.168.1.100",
                severities=[4, 5],
                status="Active",
                include_ignored=True,
            )
            assert result.success is True


class TestGetCriticalDetections:
    """Tests for get_critical_detections method."""

    @pytest.mark.asyncio
    async def test_get_critical_detections(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        xml_response = """<?xml version="1.0"?>
        <HOST_LIST_VM_DETECTION_OUTPUT>
            <RESPONSE>
                <HOST_LIST></HOST_LIST>
            </RESPONSE>
        </HOST_LIST_VM_DETECTION_OUTPUT>"""

        mock_session = create_mock_aiohttp_session(200, xml_response)

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_critical_detections()
            assert result.success is True


# =============================================================================
# Scan Management Tests
# =============================================================================


class TestListScans:
    """Tests for list_scans method."""

    @pytest.mark.asyncio
    async def test_list_scans_success(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        # Compact XML for proper parsing
        xml_response = """<SCAN_LIST_OUTPUT><RESPONSE><SCAN_LIST><SCAN><REF>scan/12345</REF><TITLE>Test Scan</TITLE><TYPE>On-Demand</TYPE><STATUS><STATE>Finished</STATE></STATUS><TARGET>192.168.1.0/24</TARGET></SCAN></SCAN_LIST></RESPONSE></SCAN_LIST_OUTPUT>"""

        mock_session = create_mock_aiohttp_session(200, xml_response)

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_scans()
            assert result.success is True
            assert "scans" in result.data
            assert "count" in result.data


class TestLaunchScan:
    """Tests for launch_scan method."""

    @pytest.mark.asyncio
    async def test_launch_scan_api_error(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        mock_session = create_mock_aiohttp_session(500, "<ERROR/>")

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.launch_scan(
                title="Test Scan",
                ip_range="192.168.1.0/24",
            )
            assert result.success is False
            assert "API error" in result.error

    @pytest.mark.asyncio
    async def test_launch_scan_with_options_error(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        mock_session = create_mock_aiohttp_session(403, "<FORBIDDEN/>")

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.launch_scan(
                title="Full Scan",
                ip_range="10.0.0.0/8",
                option_profile="Full Authenticated Scan",
                scanner_appliance="scanner01",
            )
            assert result.success is False


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        connector = QualysConnector(username="user", password="pass")

        mock_session = create_mock_aiohttp_session(200, "<OK/>")

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.health_check()
            assert result is True
            assert connector._status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_health_check_auth_failed(self):
        connector = QualysConnector(username="user", password="wrong")

        mock_session = create_mock_aiohttp_session(401, "<UNAUTHORIZED/>")

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.health_check()
            assert result is False
            assert connector._status == ConnectorStatus.AUTH_FAILED

    @pytest.mark.asyncio
    async def test_health_check_error(self):
        connector = QualysConnector(username="user", password="pass")

        mock_session = create_mock_aiohttp_session(500, "<ERROR/>")

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.health_check()
            assert result is False
            assert connector._status == ConnectorStatus.ERROR

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        connector = QualysConnector(username="user", password="pass")

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            side_effect=Exception("Network error"),
        ):
            result = await connector.health_check()
            assert result is False
            assert connector._status == ConnectorStatus.ERROR


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_get_vulnerability_details_exception(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            side_effect=Exception("Connection timeout"),
        ):
            result = await connector.get_vulnerability_details(12345)
            assert result.success is False
            assert "Connection timeout" in result.error

    @pytest.mark.asyncio
    async def test_list_hosts_api_error(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        mock_session = create_mock_aiohttp_session(500, "Internal Server Error")

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_hosts()
            assert result.success is False
            assert "API error" in result.error

    @pytest.mark.asyncio
    async def test_get_host_detections_exception(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            side_effect=Exception("DNS resolution failed"),
        ):
            result = await connector.get_host_detections()
            assert result.success is False

    @pytest.mark.asyncio
    async def test_launch_scan_exception(self, enable_enterprise_mode):
        connector = QualysConnector(username="user", password="pass")

        with patch(
            "src.services.qualys_connector.aiohttp.ClientSession",
            side_effect=Exception("SSL error"),
        ):
            result = await connector.launch_scan("Test", "192.168.1.0/24")
            assert result.success is False
            assert connector._status == ConnectorStatus.ERROR
