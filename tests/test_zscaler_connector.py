"""
Project Aura - Zscaler Connector Unit Tests

Test Type: UNIT
Dependencies: All external calls mocked (aiohttp, Zscaler REST API)
Isolation: pytest.mark.forked (prevents aiohttp mock pollution between tests)
Run Command: pytest tests/test_zscaler_connector.py -v

These tests validate:
- Zscaler connector initialization and configuration
- ZIA authentication with API key obfuscation
- ZPA authentication with OAuth2
- Threat log retrieval and parsing
- DLP incident retrieval
- URL filtering rules
- User risk scoring
- ZPA application and policy management
- Error handling and rate limiting
- GovCloud auto-detection

Mock Strategy:
- aiohttp.ClientSession: Mocked via create_mock_aiohttp_session()
- Environment variables: Set via enable_enterprise_mode fixture
- All Zscaler API responses are simulated

Related ADR: ADR-053 Enterprise Security Integrations
"""

import json
import os
import platform
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Explicit test type markers
# - unit: All external dependencies are mocked
# - forked: Run in isolated subprocess on non-Linux to prevent aiohttp mock pollution
if platform.system() == "Linux":
    pytestmark = pytest.mark.skip(
        reason="Skipped on Linux CI: requires pytest-forked for isolation"
    )
else:
    pytestmark = [pytest.mark.unit, pytest.mark.forked]

from src.config.integration_config import clear_integration_config_cache
from src.services.external_tool_connectors import ConnectorStatus
from src.services.zscaler_connector import (
    ZscalerAction,
    ZscalerCloud,
    ZscalerConnector,
    ZscalerDLPIncident,
    ZscalerDLPSeverity,
    ZscalerThreatCategory,
    ZscalerThreatEvent,
    ZscalerURLFilteringRule,
    ZscalerUserRisk,
    ZscalerZPAApplication,
)

# =============================================================================
# Test Helpers
# =============================================================================


def create_mock_aiohttp_session(
    response_status: int,
    response_body: str | dict,
    cookies: dict | None = None,
    headers: dict | None = None,
):
    """Create a properly mocked aiohttp session for async context managers."""
    mock_response = MagicMock()
    mock_response.status = response_status

    if isinstance(response_body, dict):
        mock_response.json = AsyncMock(return_value=response_body)
        mock_response.text = AsyncMock(return_value=json.dumps(response_body))
    else:
        mock_response.text = AsyncMock(return_value=response_body)
        mock_response.json = AsyncMock(return_value={"error": response_body})

    # Mock cookies for ZIA session
    if cookies:
        mock_cookies = MagicMock()
        for key, value in cookies.items():
            cookie_mock = MagicMock()
            cookie_mock.value = value
            mock_cookies.get.return_value = cookie_mock
        mock_response.cookies = mock_cookies
    else:
        mock_response.cookies = MagicMock()
        mock_response.cookies.get.return_value = None

    mock_response.headers = headers if headers else {"Retry-After": "60"}

    mock_request_context = MagicMock()
    mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_request_context.__aexit__ = AsyncMock(return_value=None)

    mock_session_instance = MagicMock()
    mock_session_instance.post.return_value = mock_request_context
    mock_session_instance.get.return_value = mock_request_context
    mock_session_instance.request.return_value = mock_request_context

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


@pytest.fixture
def zscaler_connector():
    """Create a Zscaler connector instance for testing."""
    return ZscalerConnector(
        zia_api_key="test-api-key-12345",
        zia_username="test@company.com",
        zia_password="test-password",
        zia_cloud=ZscalerCloud.ZSCALER,
        zpa_client_id="test-client-id",
        zpa_client_secret="test-client-secret",
        zpa_customer_id="12345",
        timeout_seconds=30.0,
    )


# =============================================================================
# Enum Tests
# =============================================================================


class TestZscalerCloud:
    """Tests for ZscalerCloud enum."""

    def test_zscaler(self):
        assert ZscalerCloud.ZSCALER.value == "zscaler.net"

    def test_zscalerone(self):
        assert ZscalerCloud.ZSCALERONE.value == "zscalerone.net"

    def test_zscalertwo(self):
        assert ZscalerCloud.ZSCALERTWO.value == "zscalertwo.net"

    def test_zscalerthree(self):
        assert ZscalerCloud.ZSCALERTHREE.value == "zscalerthree.net"

    def test_zscloud(self):
        assert ZscalerCloud.ZSCLOUD.value == "zscloud.net"

    def test_zscalerbeta(self):
        assert ZscalerCloud.ZSCALERBETA.value == "zscalerbeta.net"

    def test_zscalergov(self):
        assert ZscalerCloud.ZSCALERGOV.value == "zscalergov.net"


class TestZscalerThreatCategory:
    """Tests for ZscalerThreatCategory enum."""

    def test_malware(self):
        assert ZscalerThreatCategory.MALWARE.value == "malware"

    def test_phishing(self):
        assert ZscalerThreatCategory.PHISHING.value == "phishing"

    def test_botnet(self):
        assert ZscalerThreatCategory.BOTNET.value == "botnet"

    def test_cryptomining(self):
        assert ZscalerThreatCategory.CRYPTOMINING.value == "cryptomining"

    def test_adware(self):
        assert ZscalerThreatCategory.ADWARE.value == "adware"

    def test_webspam(self):
        assert ZscalerThreatCategory.WEBSPAM.value == "webspam"

    def test_suspicious(self):
        assert ZscalerThreatCategory.SUSPICIOUS.value == "suspicious"


class TestZscalerAction:
    """Tests for ZscalerAction enum."""

    def test_allowed(self):
        assert ZscalerAction.ALLOWED.value == "allowed"

    def test_blocked(self):
        assert ZscalerAction.BLOCKED.value == "blocked"

    def test_cautioned(self):
        assert ZscalerAction.CAUTIONED.value == "cautioned"

    def test_quarantined(self):
        assert ZscalerAction.QUARANTINED.value == "quarantined"


class TestZscalerDLPSeverity:
    """Tests for ZscalerDLPSeverity enum."""

    def test_critical(self):
        assert ZscalerDLPSeverity.CRITICAL.value == "critical"

    def test_high(self):
        assert ZscalerDLPSeverity.HIGH.value == "high"

    def test_medium(self):
        assert ZscalerDLPSeverity.MEDIUM.value == "medium"

    def test_low(self):
        assert ZscalerDLPSeverity.LOW.value == "low"

    def test_info(self):
        assert ZscalerDLPSeverity.INFO.value == "info"


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestZscalerThreatEvent:
    """Tests for ZscalerThreatEvent dataclass."""

    def test_basic_creation(self):
        event = ZscalerThreatEvent(
            event_id="evt-123",
            timestamp="2026-01-05T10:00:00Z",
            user="test@company.com",
        )
        assert event.event_id == "evt-123"
        assert event.user == "test@company.com"

    def test_full_creation(self):
        event = ZscalerThreatEvent(
            event_id="evt-456",
            timestamp="2026-01-05T10:00:00Z",
            user="test@company.com",
            department="Engineering",
            url="https://malicious.example.com",
            threat_category=ZscalerThreatCategory.MALWARE,
            threat_name="Win32.Malware.Test",
            action=ZscalerAction.BLOCKED,
            policy_name="Default Security Policy",
            source_ip="192.168.1.100",
            destination_ip="203.0.113.50",
            hostname="workstation-01",
            file_name="malware.exe",
            file_hash="abc123def456",
            risk_score=85,
        )
        assert event.department == "Engineering"
        assert event.threat_category == ZscalerThreatCategory.MALWARE
        assert event.action == ZscalerAction.BLOCKED
        assert event.risk_score == 85

    def test_to_dict(self):
        event = ZscalerThreatEvent(
            event_id="evt-789",
            timestamp="2026-01-05T10:00:00Z",
            user="test@company.com",
            threat_category=ZscalerThreatCategory.PHISHING,
            action=ZscalerAction.BLOCKED,
        )
        result = event.to_dict()
        assert result["event_id"] == "evt-789"
        assert result["threat_category"] == "phishing"
        assert result["action"] == "blocked"

    def test_default_values(self):
        event = ZscalerThreatEvent(
            event_id="evt-001",
            timestamp="2026-01-05T10:00:00Z",
            user="test@company.com",
        )
        assert event.department is None
        assert event.url is None
        assert event.threat_category is None
        assert event.threat_name == ""
        assert event.action == ZscalerAction.BLOCKED
        assert event.risk_score == 0


class TestZscalerDLPIncident:
    """Tests for ZscalerDLPIncident dataclass."""

    def test_basic_creation(self):
        incident = ZscalerDLPIncident(
            incident_id="dlp-123",
            timestamp="2026-01-05T10:00:00Z",
            user="test@company.com",
            dlp_engine="PII Detection",
            dlp_dictionary="SSN Pattern",
            severity=ZscalerDLPSeverity.HIGH,
            action=ZscalerAction.BLOCKED,
        )
        assert incident.incident_id == "dlp-123"
        assert incident.severity == ZscalerDLPSeverity.HIGH

    def test_to_dict(self):
        incident = ZscalerDLPIncident(
            incident_id="dlp-456",
            timestamp="2026-01-05T10:00:00Z",
            user="test@company.com",
            dlp_engine="Credit Card Detection",
            dlp_dictionary="CC Numbers",
            severity=ZscalerDLPSeverity.CRITICAL,
            action=ZscalerAction.QUARANTINED,
            matched_data="****-****-****-1234",
            destination="external-upload.com",
            channel="web",
            file_name="data.csv",
            department="Finance",
            record_count=150,
        )
        result = incident.to_dict()
        assert result["severity"] == "critical"
        assert result["action"] == "quarantined"
        assert result["record_count"] == 150


class TestZscalerURLFilteringRule:
    """Tests for ZscalerURLFilteringRule dataclass."""

    def test_creation(self):
        rule = ZscalerURLFilteringRule(
            rule_id="rule-123",
            name="Block Social Media",
            order=1,
            state="ENABLED",
            action="BLOCK",
            url_categories=["SOCIAL_MEDIA", "STREAMING"],
            departments=["Engineering"],
            description="Block social media sites",
        )
        assert rule.rule_id == "rule-123"
        assert rule.action == "BLOCK"
        assert "SOCIAL_MEDIA" in rule.url_categories


class TestZscalerUserRisk:
    """Tests for ZscalerUserRisk dataclass."""

    def test_creation(self):
        risk = ZscalerUserRisk(
            username="jdoe",
            email="jdoe@company.com",
            risk_score=75,
            risk_level="HIGH",
            last_assessment="2026-01-05T10:00:00Z",
            risk_factors=["Multiple DLP incidents", "Access to sensitive data"],
            department="Finance",
            manager="manager@company.com",
            total_threats_blocked=15,
            dlp_incidents=3,
        )
        assert risk.risk_score == 75
        assert risk.risk_level == "HIGH"
        assert len(risk.risk_factors) == 2


class TestZscalerZPAApplication:
    """Tests for ZscalerZPAApplication dataclass."""

    def test_creation(self):
        app = ZscalerZPAApplication(
            app_id="app-123",
            name="Internal CRM",
            domain_names=["crm.internal.company.com"],
            enabled=True,
            double_encrypt=True,
            bypass_type="NEVER",
            segment_group_id="sg-456",
            server_groups=["Server Group 1"],
        )
        assert app.app_id == "app-123"
        assert app.double_encrypt is True


# =============================================================================
# Connector Initialization Tests
# =============================================================================


class TestZscalerConnectorInit:
    """Tests for Zscaler connector initialization."""

    def test_basic_init(self):
        connector = ZscalerConnector(
            zia_api_key="test-key",
            zia_username="test@company.com",
            zia_password="test-pass",
        )
        assert connector.name == "zscaler"
        assert connector.zia_api_key == "test-key"
        assert connector.zia_username == "test@company.com"

    def test_zia_cloud_enum(self):
        connector = ZscalerConnector(
            zia_api_key="test-key",
            zia_username="test@company.com",
            zia_password="test-pass",
            zia_cloud=ZscalerCloud.ZSCALERGOV,
        )
        assert connector.zia_base_url == "https://zsapi.zscalergov.net"
        assert connector.zia_cloud == ZscalerCloud.ZSCALERGOV

    def test_zia_cloud_string(self):
        connector = ZscalerConnector(
            zia_api_key="test-key",
            zia_username="test@company.com",
            zia_password="test-pass",
            zia_cloud="custom.zscaler.net",
        )
        assert connector.zia_base_url == "https://zsapi.custom.zscaler.net"

    def test_zpa_init(self):
        connector = ZscalerConnector(
            zpa_client_id="client-id",
            zpa_client_secret="client-secret",
            zpa_customer_id="12345",
        )
        assert connector.zpa_client_id == "client-id"
        assert connector.zpa_customer_id == "12345"
        assert connector.zpa_base_url == "https://config.private.zscaler.com"

    def test_govcloud_auto_detection(self):
        with patch.dict(os.environ, {"AWS_REGION": "us-gov-west-1"}):
            connector = ZscalerConnector(
                zia_api_key="test-key",
                zia_username="test@company.com",
                zia_password="test-pass",
            )
            assert connector.zia_base_url == "https://zsapi.zscalergov.net"

    def test_custom_timeout(self):
        connector = ZscalerConnector(
            zia_api_key="test-key",
            zia_username="test@company.com",
            zia_password="test-pass",
            timeout_seconds=60.0,
        )
        assert connector.timeout.total == 60.0

    def test_default_status_disconnected(self):
        connector = ZscalerConnector()
        assert connector.status == ConnectorStatus.DISCONNECTED


# =============================================================================
# API Key Obfuscation Tests
# =============================================================================


class TestAPIKeyObfuscation:
    """Tests for ZIA API key obfuscation."""

    def test_obfuscate_api_key(self, zscaler_connector):
        timestamp = "1704067200000"
        result = zscaler_connector._obfuscate_api_key("test-api-key-12345", timestamp)
        # Result should be same length as timestamp
        assert len(result) == len(timestamp)
        # Result should be deterministic
        result2 = zscaler_connector._obfuscate_api_key("test-api-key-12345", timestamp)
        assert result == result2

    def test_obfuscate_different_timestamps(self, zscaler_connector):
        result1 = zscaler_connector._obfuscate_api_key(
            "test-api-key-12345", "1704067200000"
        )
        result2 = zscaler_connector._obfuscate_api_key(
            "test-api-key-12345", "1704067200001"
        )
        # Different timestamps should produce different results
        assert result1 != result2


# =============================================================================
# ZIA Authentication Tests
# =============================================================================


class TestZIAAuthentication:
    """Tests for ZIA authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_zia_success(self, zscaler_connector):
        mock_session = create_mock_aiohttp_session(
            200,
            {"authType": "API_KEY"},
            cookies={"JSESSIONID": "test-session-id-12345"},
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await zscaler_connector._authenticate_zia()
            assert result is True
            assert zscaler_connector._zia_jsessionid == "test-session-id-12345"
            assert zscaler_connector.status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_authenticate_zia_invalid_credentials(self, zscaler_connector):
        mock_session = create_mock_aiohttp_session(
            401,
            {"message": "Invalid credentials"},
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await zscaler_connector._authenticate_zia()
            assert result is False
            assert zscaler_connector.status == ConnectorStatus.AUTH_FAILED

    @pytest.mark.asyncio
    async def test_authenticate_zia_no_credentials(self):
        connector = ZscalerConnector()
        result = await connector._authenticate_zia()
        assert result is False

    @pytest.mark.asyncio
    async def test_authenticate_zia_reuses_valid_session(self, zscaler_connector):
        # Set up existing valid session
        import time

        zscaler_connector._zia_jsessionid = "existing-session"
        zscaler_connector._zia_session_expiry = time.time() + 3600  # 1 hour from now

        result = await zscaler_connector._authenticate_zia()
        assert result is True
        assert zscaler_connector._zia_jsessionid == "existing-session"


# =============================================================================
# ZPA Authentication Tests
# =============================================================================


class TestZPAAuthentication:
    """Tests for ZPA authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_zpa_success(self, zscaler_connector):
        mock_session = create_mock_aiohttp_session(
            200,
            {
                "access_token": "test-access-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await zscaler_connector._authenticate_zpa()
            assert result is True
            assert zscaler_connector._zpa_token == "test-access-token"

    @pytest.mark.asyncio
    async def test_authenticate_zpa_failure(self, zscaler_connector):
        mock_session = create_mock_aiohttp_session(
            401,
            {"error": "invalid_client"},
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await zscaler_connector._authenticate_zpa()
            assert result is False
            assert zscaler_connector.status == ConnectorStatus.AUTH_FAILED

    @pytest.mark.asyncio
    async def test_authenticate_zpa_no_credentials(self):
        connector = ZscalerConnector()
        result = await connector._authenticate_zpa()
        assert result is False


# =============================================================================
# Threat Log Tests
# =============================================================================


class TestThreatLogs:
    """Tests for threat log retrieval."""

    @pytest.mark.asyncio
    async def test_get_threat_logs_success(
        self, zscaler_connector, enable_enterprise_mode
    ):
        mock_auth_session = create_mock_aiohttp_session(
            200,
            {"authType": "API_KEY"},
            cookies={"JSESSIONID": "test-session"},
        )
        mock_api_session = create_mock_aiohttp_session(
            200,
            {
                "logs": [
                    {
                        "id": "evt-001",
                        "datetime": "2026-01-05T10:00:00Z",
                        "user": "test@company.com",
                        "department": "Engineering",
                        "url": "https://malicious.com",
                        "threatCategory": "malware",
                        "threatName": "Test.Malware",
                        "action": "blocked",
                        "sourceIP": "192.168.1.100",
                        "riskScore": 80,
                    }
                ]
            },
        )

        with patch(
            "aiohttp.ClientSession",
            side_effect=[mock_auth_session, mock_api_session],
        ):
            result = await zscaler_connector.get_threat_logs(hours=24)
            assert result.success is True
            assert "events" in result.data
            assert len(result.data["events"]) == 1
            assert result.data["events"][0]["threat_category"] == "malware"

    @pytest.mark.asyncio
    async def test_get_threat_logs_with_filters(
        self, zscaler_connector, enable_enterprise_mode
    ):
        mock_auth_session = create_mock_aiohttp_session(
            200,
            {"authType": "API_KEY"},
            cookies={"JSESSIONID": "test-session"},
        )
        mock_api_session = create_mock_aiohttp_session(
            200,
            {"logs": []},
        )

        with patch(
            "aiohttp.ClientSession",
            side_effect=[mock_auth_session, mock_api_session],
        ):
            result = await zscaler_connector.get_threat_logs(
                hours=24,
                user="test@company.com",
                threat_category=ZscalerThreatCategory.PHISHING,
                action=ZscalerAction.BLOCKED,
                limit=100,
            )
            assert result.success is True


# =============================================================================
# DLP Incident Tests
# =============================================================================


class TestDLPIncidents:
    """Tests for DLP incident retrieval."""

    @pytest.mark.asyncio
    async def test_get_dlp_incidents_success(
        self, zscaler_connector, enable_enterprise_mode
    ):
        mock_auth_session = create_mock_aiohttp_session(
            200,
            {"authType": "API_KEY"},
            cookies={"JSESSIONID": "test-session"},
        )
        mock_api_session = create_mock_aiohttp_session(
            200,
            {
                "incidents": [
                    {
                        "id": "dlp-001",
                        "datetime": "2026-01-05T10:00:00Z",
                        "user": "test@company.com",
                        "dlpEngine": "PII Detection",
                        "dlpDictionary": "SSN Patterns",
                        "severity": "high",
                        "action": "blocked",
                        "recordCount": 10,
                    }
                ]
            },
        )

        with patch(
            "aiohttp.ClientSession",
            side_effect=[mock_auth_session, mock_api_session],
        ):
            result = await zscaler_connector.get_dlp_incidents(hours=24)
            assert result.success is True
            assert "incidents" in result.data
            assert len(result.data["incidents"]) == 1
            assert result.data["incidents"][0]["severity"] == "high"


# =============================================================================
# URL Filtering Tests
# =============================================================================


class TestURLFiltering:
    """Tests for URL filtering rules."""

    @pytest.mark.asyncio
    async def test_get_url_filtering_rules_success(
        self, zscaler_connector, enable_enterprise_mode
    ):
        mock_auth_session = create_mock_aiohttp_session(
            200,
            {"authType": "API_KEY"},
            cookies={"JSESSIONID": "test-session"},
        )
        mock_api_session = create_mock_aiohttp_session(
            200,
            {
                "rules": [
                    {
                        "id": "rule-001",
                        "name": "Block Social Media",
                        "order": 1,
                        "state": "ENABLED",
                        "action": "BLOCK",
                        "urlCategories": ["SOCIAL_MEDIA"],
                        "description": "Block social media sites",
                    }
                ]
            },
        )

        with patch(
            "aiohttp.ClientSession",
            side_effect=[mock_auth_session, mock_api_session],
        ):
            result = await zscaler_connector.get_url_filtering_rules()
            assert result.success is True
            assert "rules" in result.data
            assert len(result.data["rules"]) == 1
            assert result.data["rules"][0]["name"] == "Block Social Media"


# =============================================================================
# User Risk Score Tests
# =============================================================================


class TestUserRiskScore:
    """Tests for user risk score retrieval."""

    @pytest.mark.asyncio
    async def test_get_user_risk_score_success(
        self, zscaler_connector, enable_enterprise_mode
    ):
        mock_auth_session = create_mock_aiohttp_session(
            200,
            {"authType": "API_KEY"},
            cookies={"JSESSIONID": "test-session"},
        )
        mock_api_session = create_mock_aiohttp_session(
            200,
            {
                "username": "jdoe",
                "email": "jdoe@company.com",
                "riskScore": 75,
                "riskLevel": "HIGH",
                "lastAssessment": "2026-01-05T10:00:00Z",
                "riskFactors": ["Multiple policy violations"],
                "department": "Engineering",
                "totalThreatsBlocked": 10,
                "dlpIncidents": 2,
            },
        )

        with patch(
            "aiohttp.ClientSession",
            side_effect=[mock_auth_session, mock_api_session],
        ):
            result = await zscaler_connector.get_user_risk_score("jdoe@company.com")
            assert result.success is True
            assert result.data["risk_score"] == 75
            assert result.data["risk_level"] == "HIGH"


# =============================================================================
# ZPA Tests
# =============================================================================


class TestZPAOperations:
    """Tests for ZPA operations."""

    @pytest.mark.asyncio
    async def test_get_zpa_applications_success(
        self, zscaler_connector, enable_enterprise_mode
    ):
        mock_auth_session = create_mock_aiohttp_session(
            200,
            {"access_token": "test-token", "expires_in": 3600},
        )
        mock_api_session = create_mock_aiohttp_session(
            200,
            {
                "list": [
                    {
                        "id": "app-001",
                        "name": "Internal CRM",
                        "domainNames": ["crm.internal.com"],
                        "enabled": True,
                        "doubleEncrypt": False,
                        "bypassType": "NEVER",
                        "serverGroups": [{"name": "Server Group 1"}],
                    }
                ]
            },
        )

        with patch(
            "aiohttp.ClientSession",
            side_effect=[mock_auth_session, mock_api_session],
        ):
            result = await zscaler_connector.get_zpa_applications()
            assert result.success is True
            assert "applications" in result.data
            assert len(result.data["applications"]) == 1
            assert result.data["applications"][0]["name"] == "Internal CRM"

    @pytest.mark.asyncio
    async def test_get_zpa_access_policies_success(
        self, zscaler_connector, enable_enterprise_mode
    ):
        mock_auth_session = create_mock_aiohttp_session(
            200,
            {"access_token": "test-token", "expires_in": 3600},
        )
        mock_api_session = create_mock_aiohttp_session(
            200,
            {
                "list": [
                    {
                        "id": "policy-001",
                        "name": "Default Access Policy",
                        "description": "Allow access to internal apps",
                        "action": "ALLOW",
                        "ruleOrder": 1,
                        "conditions": [],
                    }
                ]
            },
        )

        with patch(
            "aiohttp.ClientSession",
            side_effect=[mock_auth_session, mock_api_session],
        ):
            result = await zscaler_connector.get_zpa_access_policies()
            assert result.success is True
            assert "policies" in result.data
            assert len(result.data["policies"]) == 1


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_zia_success(self, zscaler_connector):
        mock_session = create_mock_aiohttp_session(
            200,
            {"authType": "API_KEY"},
            cookies={"JSESSIONID": "test-session"},
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await zscaler_connector.health_check()
            assert result is True
            assert zscaler_connector.status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_health_check_no_credentials(self):
        connector = ZscalerConnector()
        result = await connector.health_check()
        assert result is False
        assert connector.status == ConnectorStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_health_check_auth_failed(self, zscaler_connector):
        mock_session = create_mock_aiohttp_session(
            401,
            {"message": "Invalid credentials"},
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await zscaler_connector.health_check()
            assert result is False
            assert zscaler_connector.status == ConnectorStatus.AUTH_FAILED


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_tracking(self, zscaler_connector):
        # Add some timestamps
        import time

        now = time.time()
        zscaler_connector._request_timestamps = [now - 30, now - 20, now - 10]

        await zscaler_connector._check_rate_limit()

        # Should have added a new timestamp
        assert len(zscaler_connector._request_timestamps) == 4

    @pytest.mark.asyncio
    async def test_rate_limit_cleanup_old_timestamps(self, zscaler_connector):
        import time

        now = time.time()
        # Add old timestamps (older than 1 minute)
        zscaler_connector._request_timestamps = [
            now - 120,  # 2 minutes ago (should be cleaned)
            now - 90,  # 1.5 minutes ago (should be cleaned)
            now - 30,  # 30 seconds ago (should remain)
        ]

        await zscaler_connector._check_rate_limit()

        # Old timestamps should be cleaned, new one added
        assert len(zscaler_connector._request_timestamps) == 2


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_handle_rate_limit_response(
        self, zscaler_connector, enable_enterprise_mode
    ):
        mock_auth_session = create_mock_aiohttp_session(
            200,
            {"authType": "API_KEY"},
            cookies={"JSESSIONID": "test-session"},
        )

        # First API call returns 429 (rate limited)
        mock_api_session_429 = create_mock_aiohttp_session(
            429, {}, headers={"Retry-After": "1"}
        )

        # Retry API call returns success
        mock_api_session_200 = create_mock_aiohttp_session(200, {"rules": []})

        # Each retry iteration creates a new ClientSession, so we need 3 mocks:
        # 1. Auth session
        # 2. First API request (429)
        # 3. Retry API request (200)
        with patch(
            "aiohttp.ClientSession",
            side_effect=[mock_auth_session, mock_api_session_429, mock_api_session_200],
        ):
            result = await zscaler_connector.get_url_filtering_rules()
            # Should eventually succeed after retry
            assert result.success is True

    @pytest.mark.asyncio
    async def test_handle_server_error_with_retry(
        self, zscaler_connector, enable_enterprise_mode
    ):
        mock_auth_session = create_mock_aiohttp_session(
            200,
            {"authType": "API_KEY"},
            cookies={"JSESSIONID": "test-session"},
        )
        # Simulate 500 error followed by success
        mock_error_session = create_mock_aiohttp_session(500, {"error": "Server error"})

        with patch(
            "aiohttp.ClientSession",
            side_effect=[mock_auth_session, mock_error_session],
        ):
            result = await zscaler_connector.get_url_filtering_rules()
            # After max retries, should return failure
            assert result.success is False


# =============================================================================
# Logout Tests
# =============================================================================


class TestLogout:
    """Tests for logout functionality."""

    @pytest.mark.asyncio
    async def test_logout_zia_success(self, zscaler_connector, enable_enterprise_mode):
        # Set up active session
        zscaler_connector._zia_jsessionid = "active-session"
        zscaler_connector._zia_session_expiry = 9999999999

        mock_auth_session = create_mock_aiohttp_session(
            200,
            {"authType": "API_KEY"},
            cookies={"JSESSIONID": "test-session"},
        )
        mock_logout_session = create_mock_aiohttp_session(204, {})

        with patch(
            "aiohttp.ClientSession",
            side_effect=[mock_auth_session, mock_logout_session],
        ):
            result = await zscaler_connector.logout_zia()
            assert result.success is True
            assert zscaler_connector._zia_jsessionid is None
            assert zscaler_connector.status == ConnectorStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_logout_zia_no_session(
        self, zscaler_connector, enable_enterprise_mode
    ):
        # No active session
        zscaler_connector._zia_jsessionid = None

        result = await zscaler_connector.logout_zia()
        assert result.success is True
        assert result.data["message"] == "No active session"


# =============================================================================
# Metrics Tests
# =============================================================================


class TestMetrics:
    """Tests for connector metrics."""

    def test_initial_metrics(self, zscaler_connector):
        metrics = zscaler_connector.metrics
        assert metrics["name"] == "zscaler"
        assert metrics["status"] == "disconnected"
        assert metrics["request_count"] == 0
        assert metrics["error_count"] == 0

    def test_record_request_success(self, zscaler_connector):
        zscaler_connector._record_request(latency_ms=150.0, success=True)
        metrics = zscaler_connector.metrics
        assert metrics["request_count"] == 1
        assert metrics["error_count"] == 0
        assert metrics["avg_latency_ms"] == 150.0

    def test_record_request_failure(self, zscaler_connector):
        zscaler_connector._record_request(latency_ms=500.0, success=False)
        metrics = zscaler_connector.metrics
        assert metrics["request_count"] == 1
        assert metrics["error_count"] == 1

    def test_average_latency_calculation(self, zscaler_connector):
        zscaler_connector._record_request(latency_ms=100.0, success=True)
        zscaler_connector._record_request(latency_ms=200.0, success=True)
        zscaler_connector._record_request(latency_ms=300.0, success=True)
        metrics = zscaler_connector.metrics
        assert metrics["avg_latency_ms"] == 200.0


# =============================================================================
# Headers Tests
# =============================================================================


class TestHeaders:
    """Tests for header generation."""

    def test_zia_headers(self, zscaler_connector):
        zscaler_connector._zia_jsessionid = "test-session-id"
        headers = zscaler_connector._get_zia_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
        assert "JSESSIONID=test-session-id" in headers["Cookie"]

    def test_zpa_headers(self, zscaler_connector):
        zscaler_connector._zpa_token = "test-bearer-token"
        headers = zscaler_connector._get_zpa_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer test-bearer-token"
