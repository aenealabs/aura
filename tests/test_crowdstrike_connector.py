"""
Project Aura - CrowdStrike Connector Unit Tests

Test Type: UNIT
Dependencies: All external calls mocked (aiohttp, CrowdStrike API)
Isolation: pytest.mark.forked (prevents aiohttp mock pollution between tests)
Run Command: pytest tests/test_crowdstrike_connector.py -v

These tests validate:
- CrowdStrike connector initialization and configuration
- OAuth2 token management and authentication
- Host/device management API operations
- Detection and incident query operations
- IOC (Indicators of Compromise) management
- Response parsing and error handling

Mock Strategy:
- aiohttp.ClientSession: Mocked via create_mock_aiohttp_session()
- Environment variables: Set via enable_enterprise_mode fixture
- All CrowdStrike API responses are simulated

Related E2E Tests:
- tests/e2e/test_crowdstrike_e2e.py (requires RUN_E2E_TESTS=1 and real credentials)
"""

import json
import os
import platform
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Explicit test type markers
# - unit: All external dependencies are mocked
# - forked: Run in isolated subprocess on non-Linux to prevent aiohttp mock pollution
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = [pytest.mark.unit, pytest.mark.forked]

import src.services.crowdstrike_connector as crowdstrike_module
from src.config.integration_config import clear_integration_config_cache
from src.services.crowdstrike_connector import (
    CrowdStrikeCloud,
    CrowdStrikeConnector,
    CrowdStrikeDetection,
    CrowdStrikeHost,
    CrowdStrikeIOC,
    DetectionSeverity,
    DetectionStatus,
    HostStatus,
    IOCAction,
    IOCType,
)
from src.services.external_tool_connectors import ConnectorStatus

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
    mock_session_instance.patch.return_value = mock_request_context

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


class TestCrowdStrikeCloud:
    """Tests for CrowdStrikeCloud enum."""

    def test_us1(self):
        assert CrowdStrikeCloud.US1.value == "api.crowdstrike.com"

    def test_us2(self):
        assert CrowdStrikeCloud.US2.value == "api.us-2.crowdstrike.com"

    def test_eu1(self):
        assert CrowdStrikeCloud.EU1.value == "api.eu-1.crowdstrike.com"

    def test_gov(self):
        assert CrowdStrikeCloud.GOV.value == "api.laggar.gcw.crowdstrike.com"


class TestDetectionSeverity:
    """Tests for DetectionSeverity enum."""

    def test_informational(self):
        assert DetectionSeverity.INFORMATIONAL.value == "informational"

    def test_low(self):
        assert DetectionSeverity.LOW.value == "low"

    def test_medium(self):
        assert DetectionSeverity.MEDIUM.value == "medium"

    def test_high(self):
        assert DetectionSeverity.HIGH.value == "high"

    def test_critical(self):
        assert DetectionSeverity.CRITICAL.value == "critical"


class TestDetectionStatus:
    """Tests for DetectionStatus enum."""

    def test_new(self):
        assert DetectionStatus.NEW.value == "new"

    def test_in_progress(self):
        assert DetectionStatus.IN_PROGRESS.value == "in_progress"

    def test_true_positive(self):
        assert DetectionStatus.TRUE_POSITIVE.value == "true_positive"

    def test_false_positive(self):
        assert DetectionStatus.FALSE_POSITIVE.value == "false_positive"

    def test_ignored(self):
        assert DetectionStatus.IGNORED.value == "ignored"

    def test_closed(self):
        assert DetectionStatus.CLOSED.value == "closed"


class TestHostStatus:
    """Tests for HostStatus enum."""

    def test_normal(self):
        assert HostStatus.NORMAL.value == "normal"

    def test_containment_pending(self):
        assert HostStatus.CONTAINMENT_PENDING.value == "containment_pending"

    def test_contained(self):
        assert HostStatus.CONTAINED.value == "contained"

    def test_lift_containment_pending(self):
        assert HostStatus.LIFT_CONTAINMENT_PENDING.value == "lift_containment_pending"


class TestIOCType:
    """Tests for IOCType enum."""

    def test_sha256(self):
        assert IOCType.SHA256.value == "sha256"

    def test_md5(self):
        assert IOCType.MD5.value == "md5"

    def test_domain(self):
        assert IOCType.DOMAIN.value == "domain"

    def test_ipv4(self):
        assert IOCType.IPV4.value == "ipv4"

    def test_ipv6(self):
        assert IOCType.IPV6.value == "ipv6"


class TestIOCAction:
    """Tests for IOCAction enum."""

    def test_detect(self):
        assert IOCAction.DETECT.value == "detect"

    def test_prevent(self):
        assert IOCAction.PREVENT.value == "prevent"

    def test_allow(self):
        assert IOCAction.ALLOW.value == "allow"

    def test_no_action(self):
        assert IOCAction.NO_ACTION.value == "no_action"


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestCrowdStrikeHost:
    """Tests for CrowdStrikeHost dataclass."""

    def test_basic_creation(self):
        host = CrowdStrikeHost(
            device_id="device123",
            hostname="server01",
        )
        assert host.device_id == "device123"
        assert host.hostname == "server01"

    def test_full_creation(self):
        host = CrowdStrikeHost(
            device_id="device123",
            hostname="server01",
            platform_name="Windows",
            os_version="10.0.19041",
            agent_version="6.40.0",
            status=HostStatus.NORMAL,
            last_seen="2024-01-01T00:00:00Z",
            local_ip="192.168.1.100",
            external_ip="203.0.113.1",
            mac_address="AA:BB:CC:DD:EE:FF",
            system_manufacturer="Dell",
            system_product_name="PowerEdge R740",
            groups=["Production", "Web Servers"],
            tags=["critical", "pci-scope"],
        )
        assert host.platform_name == "Windows"
        assert host.status == HostStatus.NORMAL
        assert len(host.groups) == 2
        assert len(host.tags) == 2

    def test_default_values(self):
        host = CrowdStrikeHost(device_id="dev1", hostname="host1")
        assert host.platform_name is None
        assert host.os_version is None
        assert host.groups == []
        assert host.tags == []


class TestCrowdStrikeDetection:
    """Tests for CrowdStrikeDetection dataclass."""

    def test_basic_creation(self):
        detection = CrowdStrikeDetection(
            detection_id="det123",
            device_id="device456",
            hostname="server01",
            severity=DetectionSeverity.HIGH,
            status=DetectionStatus.NEW,
        )
        assert detection.detection_id == "det123"
        assert detection.severity == DetectionSeverity.HIGH

    def test_full_creation(self):
        detection = CrowdStrikeDetection(
            detection_id="det123",
            device_id="device456",
            hostname="server01",
            severity=DetectionSeverity.CRITICAL,
            status=DetectionStatus.IN_PROGRESS,
            tactic="Initial Access",
            technique="T1566.001",
            description="Spear-phishing attachment detected",
            behaviors=[{"behavior_id": "b1", "description": "File write"}],
            ioc_type="sha256",
            ioc_value="abc123",
            timestamp="2024-01-01T00:00:00Z",
        )
        assert detection.tactic == "Initial Access"
        assert len(detection.behaviors) == 1

    def test_default_values(self):
        detection = CrowdStrikeDetection(
            detection_id="d1",
            device_id="dev1",
            hostname="h1",
            severity=DetectionSeverity.LOW,
            status=DetectionStatus.NEW,
        )
        assert detection.tactic is None
        assert detection.description == ""
        assert detection.behaviors == []


class TestCrowdStrikeIOC:
    """Tests for CrowdStrikeIOC dataclass."""

    def test_basic_creation(self):
        ioc = CrowdStrikeIOC(
            type=IOCType.SHA256,
            value="a" * 64,
        )
        assert ioc.type == IOCType.SHA256
        assert ioc.action == IOCAction.DETECT  # default

    def test_full_creation(self):
        ioc = CrowdStrikeIOC(
            type=IOCType.DOMAIN,
            value="malware.example.com",
            action=IOCAction.PREVENT,
            severity=DetectionSeverity.CRITICAL,
            description="Known malware domain",
            platforms=["windows", "mac"],
            tags=["apt", "malware"],
            expiration="2024-12-31T23:59:59Z",
        )
        assert ioc.action == IOCAction.PREVENT
        assert len(ioc.platforms) == 2

    def test_default_values(self):
        ioc = CrowdStrikeIOC(type=IOCType.IPV4, value="192.0.2.1")
        assert ioc.action == IOCAction.DETECT
        assert ioc.severity == DetectionSeverity.MEDIUM
        assert ioc.platforms == []
        assert ioc.tags == []


# =============================================================================
# Connector Initialization Tests
# =============================================================================


class TestCrowdStrikeConnectorInit:
    """Tests for CrowdStrikeConnector initialization."""

    def test_basic_init(self):
        connector = CrowdStrikeConnector(
            client_id="client123",
            client_secret="secret456",
        )
        assert connector.client_id == "client123"
        assert connector.client_secret == "secret456"
        assert connector.base_url == "https://api.crowdstrike.com"

    def test_custom_cloud_us2(self):
        connector = CrowdStrikeConnector(
            client_id="id",
            client_secret="secret",
            cloud=CrowdStrikeCloud.US2,
        )
        assert connector.base_url == "https://api.us-2.crowdstrike.com"

    def test_custom_cloud_eu1(self):
        connector = CrowdStrikeConnector(
            client_id="id",
            client_secret="secret",
            cloud=CrowdStrikeCloud.EU1,
        )
        assert connector.base_url == "https://api.eu-1.crowdstrike.com"

    def test_custom_cloud_gov(self):
        connector = CrowdStrikeConnector(
            client_id="id",
            client_secret="secret",
            cloud=CrowdStrikeCloud.GOV,
        )
        assert connector.base_url == "https://api.laggar.gcw.crowdstrike.com"

    def test_custom_timeout(self):
        connector = CrowdStrikeConnector(
            client_id="id",
            client_secret="secret",
            timeout_seconds=60.0,
        )
        assert connector.timeout.total == 60.0

    def test_get_headers(self):
        connector = CrowdStrikeConnector(
            client_id="id",
            client_secret="secret",
        )
        headers = connector._get_headers("test_token")
        assert headers["Authorization"] == "Bearer test_token"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_initial_token_state(self):
        connector = CrowdStrikeConnector(
            client_id="id",
            client_secret="secret",
        )
        assert connector._access_token is None
        assert connector._token_expiry == 0


# =============================================================================
# Token Management Tests
# =============================================================================


class TestEnsureToken:
    """Tests for token management."""

    @pytest.mark.asyncio
    async def test_ensure_token_success(self):
        connector = CrowdStrikeConnector(
            client_id="client123",
            client_secret="secret456",
        )

        mock_session = create_mock_aiohttp_session(
            201,
            {"access_token": "test_token_123", "expires_in": 1800},
        )

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            token = await connector._ensure_token()
            assert token == "test_token_123"
            assert connector._access_token == "test_token_123"

    @pytest.mark.asyncio
    async def test_ensure_token_cached(self):
        connector = CrowdStrikeConnector(
            client_id="client123",
            client_secret="secret456",
        )
        connector._access_token = "cached_token"
        connector._token_expiry = 9999999999  # Far future

        token = await connector._ensure_token()
        assert token == "cached_token"

    @pytest.mark.asyncio
    async def test_ensure_token_auth_failed(self):
        connector = CrowdStrikeConnector(
            client_id="client123",
            client_secret="wrong_secret",
        )

        mock_session = create_mock_aiohttp_session(
            401, {"errors": ["Invalid credentials"]}
        )

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            with pytest.raises(RuntimeError, match="Failed to get CrowdStrike token"):
                await connector._ensure_token()


# =============================================================================
# Host Management Tests
# =============================================================================


class TestSearchHosts:
    """Tests for search_hosts method."""

    @pytest.mark.asyncio
    async def test_search_hosts_success(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(
            client_id="id",
            client_secret="secret",
        )
        connector._access_token = "test_token"
        connector._token_expiry = 9999999999

        # Mock the two-step API call (get IDs, then get details)
        mock_response_ids = MagicMock()
        mock_response_ids.status = 200
        mock_response_ids.json = AsyncMock(return_value={"resources": ["dev1", "dev2"]})

        mock_response_details = MagicMock()
        mock_response_details.status = 200
        mock_response_details.json = AsyncMock(
            return_value={
                "resources": [
                    {
                        "device_id": "dev1",
                        "hostname": "server01",
                        "platform_name": "Windows",
                    },
                    {
                        "device_id": "dev2",
                        "hostname": "server02",
                        "platform_name": "Linux",
                    },
                ]
            }
        )

        mock_ctx_ids = MagicMock()
        mock_ctx_ids.__aenter__ = AsyncMock(return_value=mock_response_ids)
        mock_ctx_ids.__aexit__ = AsyncMock(return_value=None)

        mock_ctx_details = MagicMock()
        mock_ctx_details.__aenter__ = AsyncMock(return_value=mock_response_details)
        mock_ctx_details.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_ctx_ids
        mock_session_instance.post.return_value = mock_ctx_details

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.search_hosts(hostname="server*")
            assert result.success is True
            assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_search_hosts_empty(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"resources": []})

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_ctx

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.search_hosts()
            assert result.success is True
            assert result.data["hosts"] == []
            assert result.data["count"] == 0


class TestGetHost:
    """Tests for get_host method."""

    @pytest.mark.asyncio
    async def test_get_host_success(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "resources": [
                    {
                        "device_id": "dev123",
                        "hostname": "server01",
                        "platform_name": "Windows",
                        "os_version": "10.0",
                        "groups": ["prod"],
                        "tags": ["critical"],
                    }
                ]
            },
        )

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_host("dev123")
            assert result.success is True
            assert result.data["hostname"] == "server01"

    @pytest.mark.asyncio
    async def test_get_host_not_found(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_session = create_mock_aiohttp_session(200, {"resources": []})

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_host("nonexistent")
            assert result.success is False
            assert "not found" in result.error.lower()


class TestContainHost:
    """Tests for contain_host method."""

    @pytest.mark.asyncio
    async def test_contain_host_success(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_session = create_mock_aiohttp_session(
            202, {"resources": [{"id": "dev123"}]}
        )

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.contain_host("dev123")
            assert result.success is True
            assert result.request_id == "dev123"


class TestLiftContainment:
    """Tests for lift_containment method."""

    @pytest.mark.asyncio
    async def test_lift_containment_success(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_session = create_mock_aiohttp_session(
            200, {"resources": [{"id": "dev123"}]}
        )

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.lift_containment("dev123")
            assert result.success is True


# =============================================================================
# Detection Management Tests
# =============================================================================


class TestSearchDetections:
    """Tests for search_detections method."""

    @pytest.mark.asyncio
    async def test_search_detections_success(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        # Two-step mock
        mock_response_ids = MagicMock()
        mock_response_ids.status = 200
        mock_response_ids.json = AsyncMock(return_value={"resources": ["det1"]})

        mock_response_details = MagicMock()
        mock_response_details.status = 200
        mock_response_details.json = AsyncMock(
            return_value={
                "resources": [
                    {
                        "detection_id": "det1",
                        "device": {"device_id": "dev1", "hostname": "server01"},
                        "max_severity_displayname": "high",
                        "status": "new",
                        "behaviors": [{"tactic": "Execution", "technique": "T1059"}],
                    }
                ]
            }
        )

        mock_ctx_ids = MagicMock()
        mock_ctx_ids.__aenter__ = AsyncMock(return_value=mock_response_ids)
        mock_ctx_ids.__aexit__ = AsyncMock(return_value=None)

        mock_ctx_details = MagicMock()
        mock_ctx_details.__aenter__ = AsyncMock(return_value=mock_response_details)
        mock_ctx_details.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_ctx_ids
        mock_session_instance.post.return_value = mock_ctx_details

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.search_detections(severity=DetectionSeverity.HIGH)
            assert result.success is True
            assert result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_search_detections_empty(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"resources": []})

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_ctx

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.search_detections()
            assert result.success is True
            assert result.data["detections"] == []


class TestUpdateDetectionStatus:
    """Tests for update_detection_status method."""

    @pytest.mark.asyncio
    async def test_update_detection_status_success(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_session = create_mock_aiohttp_session(200, {"resources": []})

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.update_detection_status(
                detection_ids=["det1", "det2"],
                status=DetectionStatus.CLOSED,
                comment="Resolved",
            )
            assert result.success is True


# =============================================================================
# IOC Management Tests
# =============================================================================


class TestSearchIOCs:
    """Tests for search_iocs method."""

    @pytest.mark.asyncio
    async def test_search_iocs_success(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "resources": [
                    {
                        "id": "ioc1",
                        "type": "sha256",
                        "value": "abc123",
                        "action": "detect",
                        "severity": "medium",
                    }
                ]
            },
        )

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.search_iocs(ioc_type=IOCType.SHA256)
            assert result.success is True
            assert result.data["count"] == 1


class TestCreateIOC:
    """Tests for create_ioc method."""

    @pytest.mark.asyncio
    async def test_create_ioc_success(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_session = create_mock_aiohttp_session(
            201, {"resources": [{"id": "new_ioc"}]}
        )

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_ioc(
                ioc_type=IOCType.DOMAIN,
                value="malware.example.com",
                action=IOCAction.PREVENT,
                severity=DetectionSeverity.HIGH,
                description="Known malware domain",
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_create_ioc_with_all_options(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_session = create_mock_aiohttp_session(
            201, {"resources": [{"id": "new_ioc"}]}
        )

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_ioc(
                ioc_type=IOCType.IPV4,
                value="192.0.2.1",
                action=IOCAction.DETECT,
                severity=DetectionSeverity.MEDIUM,
                description="Suspicious IP",
                platforms=["windows", "linux"],
                tags=["aura", "test"],
                expiration="2025-12-31T23:59:59Z",
            )
            assert result.success is True


class TestCreateSecurityIOC:
    """Tests for create_security_ioc method."""

    @pytest.mark.asyncio
    async def test_create_security_ioc_high(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_session = create_mock_aiohttp_session(
            201, {"resources": [{"id": "sec_ioc"}]}
        )

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_security_ioc(
                ioc_type=IOCType.SHA256,
                value="a" * 64,
                cve_id="CVE-2024-1234",
                severity="HIGH",
                description="Malicious file",
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_create_security_ioc_critical(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_session = create_mock_aiohttp_session(
            201, {"resources": [{"id": "sec_ioc"}]}
        )

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_security_ioc(
                ioc_type=IOCType.DOMAIN,
                value="critical-threat.example.com",
                severity="CRITICAL",
                description="Active C2 server",
            )
            assert result.success is True


# =============================================================================
# Threat Intelligence Tests
# =============================================================================


class TestSearchThreatIntel:
    """Tests for search_threat_intel method."""

    @pytest.mark.asyncio
    async def test_search_threat_intel_success(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "resources": [
                    {
                        "id": "intel1",
                        "indicator": "malware.example.com",
                        "type": "domain",
                        "malicious_confidence": "high",
                        "labels": ["malware"],
                        "actors": ["APT28"],
                    }
                ]
            },
        )

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.search_threat_intel("malware.example.com")
            assert result.success is True
            assert result.data["count"] == 1
            assert result.data["query"] == "malware.example.com"

    @pytest.mark.asyncio
    async def test_search_threat_intel_with_type(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        mock_session = create_mock_aiohttp_session(200, {"resources": []})

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.search_threat_intel(
                indicator="192.0.2.1",
                indicator_type=IOCType.IPV4,
            )
            assert result.success is True


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")

        mock_session = create_mock_aiohttp_session(
            201, {"access_token": "token", "expires_in": 1800}
        )

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
        ):
            result = await connector.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")

        mock_session = create_mock_aiohttp_session(401, {"errors": ["Invalid"]})

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            return_value=mock_session,
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
    async def test_search_hosts_exception(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            side_effect=Exception("Network error"),
        ):
            result = await connector.search_hosts()
            assert result.success is False
            assert "Network error" in result.error

    @pytest.mark.asyncio
    async def test_get_host_exception(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            side_effect=Exception("Connection failed"),
        ):
            result = await connector.get_host("dev123")
            assert result.success is False
            assert "Connection failed" in result.error

    @pytest.mark.asyncio
    async def test_contain_host_exception(self, enable_enterprise_mode):
        connector = CrowdStrikeConnector(client_id="id", client_secret="secret")
        connector._access_token = "token"
        connector._token_expiry = 9999999999

        with patch.object(
            crowdstrike_module.aiohttp,
            "ClientSession",
            side_effect=Exception("Timeout"),
        ):
            result = await connector.contain_host("dev123")
            assert result.success is False
            assert "Timeout" in result.error
