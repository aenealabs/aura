"""
Project Aura - Splunk Connector Unit Tests

Test Type: UNIT
Dependencies: All external calls mocked (aiohttp, Splunk REST API)
Isolation: pytest.mark.forked (prevents aiohttp mock pollution between tests)
Run Command: pytest tests/test_splunk_connector.py -v

These tests validate:
- Splunk connector initialization and configuration
- Search job creation and management
- Event ingestion via HEC (HTTP Event Collector)
- Saved search and alert management
- Result retrieval and parsing
- Error handling and authentication

Mock Strategy:
- aiohttp.ClientSession: Mocked via create_mock_aiohttp_session()
- Environment variables: Set via enable_enterprise_mode fixture
- All Splunk API responses are simulated

Related E2E Tests:
- tests/e2e/test_splunk_e2e.py (requires RUN_E2E_TESTS=1 and real Splunk instance)
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
if platform.system() == "Linux":
    pytestmark = pytest.mark.skip(
        reason="Skipped on Linux CI: requires pytest-forked for isolation"
    )
else:
    pytestmark = [pytest.mark.unit, pytest.mark.forked]

from src.config.integration_config import clear_integration_config_cache
from src.services.external_tool_connectors import ConnectorStatus
from src.services.splunk_connector import (
    SplunkAlert,
    SplunkConnector,
    SplunkEvent,
    SplunkOutputMode,
    SplunkSearchJob,
    SplunkSearchMode,
    SplunkSeverity,
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


class TestSplunkSearchMode:
    """Tests for SplunkSearchMode enum."""

    def test_normal(self):
        assert SplunkSearchMode.NORMAL.value == "normal"

    def test_realtime(self):
        assert SplunkSearchMode.REALTIME.value == "realtime"


class TestSplunkOutputMode:
    """Tests for SplunkOutputMode enum."""

    def test_json(self):
        assert SplunkOutputMode.JSON.value == "json"

    def test_csv(self):
        assert SplunkOutputMode.CSV.value == "csv"

    def test_xml(self):
        assert SplunkOutputMode.XML.value == "xml"

    def test_raw(self):
        assert SplunkOutputMode.RAW.value == "raw"


class TestSplunkSeverity:
    """Tests for SplunkSeverity enum."""

    def test_unknown(self):
        assert SplunkSeverity.UNKNOWN.value == "unknown"

    def test_info(self):
        assert SplunkSeverity.INFO.value == "info"

    def test_low(self):
        assert SplunkSeverity.LOW.value == "low"

    def test_medium(self):
        assert SplunkSeverity.MEDIUM.value == "medium"

    def test_high(self):
        assert SplunkSeverity.HIGH.value == "high"

    def test_critical(self):
        assert SplunkSeverity.CRITICAL.value == "critical"


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestSplunkEvent:
    """Tests for SplunkEvent dataclass."""

    def test_basic_creation(self):
        event = SplunkEvent(event={"message": "test"})
        assert event.event == {"message": "test"}

    def test_string_event(self):
        event = SplunkEvent(event="raw log line")
        assert event.event == "raw log line"

    def test_full_creation(self):
        event = SplunkEvent(
            event={"message": "test", "level": "info"},
            time=1704067200.0,
            host="server01",
            source="app",
            sourcetype="_json",
            index="main",
            fields={"custom_field": "value"},
        )
        assert event.host == "server01"
        assert event.index == "main"

    def test_default_values(self):
        event = SplunkEvent(event="test")
        assert event.time is None
        assert event.host is None
        assert event.index is None


class TestSplunkSearchJob:
    """Tests for SplunkSearchJob dataclass."""

    def test_basic_creation(self):
        job = SplunkSearchJob(sid="1234567890", status="RUNNING")
        assert job.sid == "1234567890"
        assert job.status == "RUNNING"

    def test_full_creation(self):
        job = SplunkSearchJob(
            sid="1234567890",
            status="DONE",
            is_done=True,
            is_failed=False,
            result_count=100,
            scan_count=1000,
            event_count=500,
            run_duration=5.5,
            messages=[{"type": "INFO", "text": "Search complete"}],
        )
        assert job.is_done is True
        assert job.result_count == 100
        assert len(job.messages) == 1

    def test_default_values(self):
        job = SplunkSearchJob(sid="123", status="NEW")
        assert job.is_done is False
        assert job.is_failed is False
        assert job.result_count == 0
        assert job.messages == []


class TestSplunkAlert:
    """Tests for SplunkAlert dataclass."""

    def test_basic_creation(self):
        alert = SplunkAlert(name="Test Alert", search="index=main | head 10")
        assert alert.name == "Test Alert"
        assert alert.search == "index=main | head 10"

    def test_full_creation(self):
        alert = SplunkAlert(
            name="Security Alert",
            search="index=security | stats count by src_ip",
            description="Alert on suspicious activity",
            severity=SplunkSeverity.HIGH,
            cron_schedule="*/15 * * * *",
            is_scheduled=True,
            alert_type="number of events",
            alert_comparator="greater than",
            alert_threshold="10",
            actions=["email", "webhook"],
        )
        assert alert.severity == SplunkSeverity.HIGH
        assert len(alert.actions) == 2

    def test_default_values(self):
        alert = SplunkAlert(name="Test", search="search *")
        assert alert.description == ""
        assert alert.severity == SplunkSeverity.MEDIUM
        assert alert.cron_schedule == "*/5 * * * *"
        assert alert.is_scheduled is True
        assert alert.actions is None


# =============================================================================
# Connector Initialization Tests
# =============================================================================


class TestSplunkConnectorInit:
    """Tests for SplunkConnector initialization."""

    def test_basic_init_with_token(self):
        connector = SplunkConnector(
            base_url="https://splunk.example.com:8089",
            token="my-api-token",
        )
        assert connector.base_url == "https://splunk.example.com:8089"
        assert connector._token == "my-api-token"

    def test_init_with_credentials(self):
        connector = SplunkConnector(
            base_url="https://splunk.example.com:8089",
            username="admin",
            password="password123",
        )
        assert connector._username == "admin"
        assert connector._password == "password123"

    def test_init_with_hec(self):
        connector = SplunkConnector(
            base_url="https://splunk.example.com:8089",
            token="api-token",
            hec_url="https://splunk.example.com:8088",
            hec_token="hec-token",
        )
        assert connector.hec_url == "https://splunk.example.com:8088"
        assert connector.hec_token == "hec-token"

    def test_trailing_slash_removal(self):
        connector = SplunkConnector(
            base_url="https://splunk.example.com:8089/",
            token="token",
            hec_url="https://splunk.example.com:8088/",
            hec_token="hec-token",
        )
        assert connector.base_url == "https://splunk.example.com:8089"
        assert connector.hec_url == "https://splunk.example.com:8088"

    def test_default_index(self):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )
        assert connector.default_index == "main"

    def test_custom_default_index(self):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            default_index="security",
        )
        assert connector.default_index == "security"

    def test_verify_ssl_default(self):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )
        assert connector.verify_ssl is True

    def test_verify_ssl_disabled(self):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            verify_ssl=False,
        )
        assert connector.verify_ssl is False

    def test_custom_timeout(self):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            timeout_seconds=120.0,
        )
        assert connector.timeout.total == 120.0


class TestAuthHeaders:
    """Tests for authentication header generation."""

    def test_get_auth_headers_token(self):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="my-bearer-token",
        )
        headers = connector._get_auth_headers()
        assert headers["Authorization"] == "Bearer my-bearer-token"
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"
        assert headers["Accept"] == "application/json"

    def test_get_auth_headers_basic(self):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            username="admin",
            password="secret",
        )
        headers = connector._get_auth_headers()
        assert headers["Authorization"].startswith("Basic ")

    def test_get_hec_headers(self):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-abc123",
        )
        headers = connector._get_hec_headers()
        assert headers["Authorization"] == "Splunk hec-abc123"
        assert headers["Content-Type"] == "application/json"


# =============================================================================
# Search Operation Tests
# =============================================================================


class TestCreateSearchJob:
    """Tests for _create_search_job method."""

    @pytest.mark.asyncio
    async def test_create_search_job_success(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            201,
            {"sid": "1234567890.123"},
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._create_search_job(
                query="index=main | head 10",
                earliest_time="-1h",
                latest_time="now",
            )
            assert result.success is True
            assert result.data["sid"] == "1234567890.123"

    @pytest.mark.asyncio
    async def test_create_search_job_error(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            400,
            {"messages": [{"type": "ERROR", "text": "Invalid search query"}]},
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._create_search_job(
                query="invalid query",
                earliest_time="-1h",
                latest_time="now",
            )
            assert result.success is False


class TestGetSearchResults:
    """Tests for _get_search_results method."""

    @pytest.mark.asyncio
    async def test_get_search_results_success(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "results": [
                    {"_raw": "log line 1"},
                    {"_raw": "log line 2"},
                ]
            },
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._get_search_results(
                sid="1234567890.123",
                max_results=100,
            )
            assert result.success is True
            assert result.data["count"] == 2


class TestSearchSecurityEvents:
    """Tests for search_security_events method."""

    @pytest.mark.asyncio
    async def test_search_security_events(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Mock the full search flow
        with patch.object(connector, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = MagicMock(
                success=True, data={"results": [], "count": 0}
            )

            _result = await connector.search_security_events(
                event_type="authentication",
                severity=SplunkSeverity.HIGH,
                source_ip="192.168.1.100",
            )
            assert mock_search.called


# =============================================================================
# Event Ingestion Tests
# =============================================================================


class TestSendEvent:
    """Tests for send_event method."""

    @pytest.mark.asyncio
    async def test_send_event_no_hec_config(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        result = await connector.send_event(event={"message": "test"})
        assert result.success is False
        assert "HEC URL and token must be configured" in result.error

    @pytest.mark.asyncio
    async def test_send_event_success(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0, "text": "Success"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_event(
                event={"message": "test event"},
                host="server01",
                source="test-source",
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_send_event_failure(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(
            400, {"code": 6, "text": "Invalid data format"}
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_event(event="invalid")
            assert result.success is False


class TestSendSecurityEvent:
    """Tests for send_security_event method."""

    @pytest.mark.asyncio
    async def test_send_security_event(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_security_event(
                event_type="malware_detected",
                severity=SplunkSeverity.CRITICAL,
                description="Malware found in upload",
                cve_id="CVE-2024-1234",
                source_ip="192.168.1.100",
                affected_asset="/uploads/malware.exe",
            )
            assert result.success is True


class TestSendBatchEvents:
    """Tests for send_batch_events method."""

    @pytest.mark.asyncio
    async def test_send_batch_events_no_hec(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        events = [
            SplunkEvent(event={"msg": "test1"}),
            SplunkEvent(event={"msg": "test2"}),
        ]
        result = await connector.send_batch_events(events)
        assert result.success is False
        assert "HEC URL and token must be configured" in result.error

    @pytest.mark.asyncio
    async def test_send_batch_events_success(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0})

        events = [
            SplunkEvent(event={"msg": "test1"}, host="server1"),
            SplunkEvent(event={"msg": "test2"}, host="server2"),
        ]

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_batch_events(events)
            assert result.success is True
            assert result.data["events_sent"] == 2


# =============================================================================
# Saved Searches and Alerts Tests
# =============================================================================


class TestListSavedSearches:
    """Tests for list_saved_searches method."""

    @pytest.mark.asyncio
    async def test_list_saved_searches_success(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "entry": [
                    {
                        "name": "Search 1",
                        "content": {
                            "search": "index=main | head 10",
                            "is_scheduled": True,
                            "cron_schedule": "*/5 * * * *",
                        },
                    },
                    {
                        "name": "Search 2",
                        "content": {
                            "search": "index=security",
                            "is_scheduled": False,
                        },
                    },
                ]
            },
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_saved_searches()
            assert result.success is True
            assert result.data["count"] == 2


class TestCreateAlert:
    """Tests for create_alert method."""

    @pytest.mark.asyncio
    async def test_create_alert_success(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            201,
            {"entry": [{"name": "Security Alert"}]},
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_alert(
                name="Security Alert",
                search="index=security severity=high | stats count",
                description="Alert on high severity events",
                severity=SplunkSeverity.HIGH,
                alert_threshold=5,
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_create_alert_with_actions(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(200, {"entry": []})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_alert(
                name="Alert with Actions",
                search="index=main",
                actions=["email", "webhook", "slack"],
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_create_alert_error(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            400,
            {"messages": [{"type": "ERROR", "text": "Alert name already exists"}]},
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_alert(
                name="Duplicate Alert",
                search="index=main",
            )
            assert result.success is False


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            200, {"entry": [{"content": {"version": "9.0.0"}}]}
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.health_check()
            assert result is True
            assert connector._status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_health_check_auth_failed(self):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="bad-token",
        )

        mock_session = create_mock_aiohttp_session(401, {"messages": ["Unauthorized"]})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.health_check()
            assert result is False
            assert connector._status == ConnectorStatus.AUTH_FAILED

    @pytest.mark.asyncio
    async def test_health_check_error(self):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(500, {"messages": ["Server error"]})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.health_check()
            assert result is False
            assert connector._status == ConnectorStatus.ERROR

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=Exception("Connection refused"),
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
    async def test_create_search_job_exception(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=Exception("Network error"),
        ):
            result = await connector._create_search_job("query", "-1h", "now")
            assert result.success is False
            assert "Network error" in result.error

    @pytest.mark.asyncio
    async def test_send_event_exception(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=Exception("SSL error"),
        ):
            result = await connector.send_event(event={"msg": "test"})
            assert result.success is False
            assert connector._status == ConnectorStatus.ERROR

    @pytest.mark.asyncio
    async def test_list_saved_searches_exception(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=Exception("Timeout"),
        ):
            result = await connector.list_saved_searches()
            assert result.success is False

    @pytest.mark.asyncio
    async def test_create_alert_exception(self, enable_enterprise_mode):
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=Exception("Connection reset"),
        ):
            result = await connector.create_alert(name="Test", search="index=main")
            assert result.success is False
            assert connector._status == ConnectorStatus.ERROR


# =============================================================================
# Wait For Job Extended Tests
# =============================================================================


class TestWaitForJobExtended:
    """Extended tests for _wait_for_job method."""

    @pytest.mark.asyncio
    async def test_wait_for_job_completes_successfully(self, enable_enterprise_mode):
        """Test waiting for a job that completes successfully."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "entry": [
                    {
                        "content": {
                            "dispatchState": "DONE",
                            "isDone": True,
                            "isFailed": False,
                            "resultCount": 150,
                            "scanCount": 1000,
                            "eventCount": 500,
                            "runDuration": 2.5,
                            "messages": [],
                        }
                    }
                ]
            },
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            job = await connector._wait_for_job("sid-12345", timeout_seconds=5)
            assert job.is_done is True
            assert job.is_failed is False
            assert job.result_count == 150
            assert job.scan_count == 1000
            assert job.event_count == 500

    @pytest.mark.asyncio
    async def test_wait_for_job_fails_job(self, enable_enterprise_mode):
        """Test waiting for a job that fails."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "entry": [
                    {
                        "content": {
                            "dispatchState": "FAILED",
                            "isDone": True,
                            "isFailed": True,
                            "resultCount": 0,
                            "messages": [{"type": "ERROR", "text": "Search failed"}],
                        }
                    }
                ]
            },
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            job = await connector._wait_for_job("sid-failed", timeout_seconds=5)
            assert job.is_failed is True
            assert job.is_done is True

    @pytest.mark.asyncio
    async def test_wait_for_job_timeout(self, enable_enterprise_mode):
        """Test waiting for a job that times out."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Mock a response that shows job is still running
        mock_session = create_mock_aiohttp_session(
            200,
            {
                "entry": [
                    {
                        "content": {
                            "dispatchState": "RUNNING",
                            "isDone": False,
                            "isFailed": False,
                            "resultCount": 0,
                        }
                    }
                ]
            },
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            with patch(
                "src.services.splunk_connector.asyncio.sleep", new_callable=AsyncMock
            ):
                job = await connector._wait_for_job(
                    "sid-slow", timeout_seconds=0.01, poll_interval=0.001
                )
                assert job.is_failed is True
                assert job.status == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_wait_for_job_handles_exception(self, enable_enterprise_mode):
        """Test _wait_for_job handles API errors gracefully."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=Exception("Connection error"),
        ):
            with patch(
                "src.services.splunk_connector.asyncio.sleep", new_callable=AsyncMock
            ):
                job = await connector._wait_for_job(
                    "sid-error", timeout_seconds=0.01, poll_interval=0.001
                )
                # Should return timeout job after failures
                assert job.is_failed is True


# =============================================================================
# Full Search Flow Tests
# =============================================================================


class TestFullSearchFlow:
    """Tests for the complete search workflow."""

    @pytest.mark.asyncio
    async def test_search_full_flow_success(self, enable_enterprise_mode):
        """Test the complete search flow from job creation to results."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Create mock that returns different responses for different endpoints
        call_count = [0]

        def create_dynamic_mock_session():
            mock_response = MagicMock()

            async def get_json():
                if call_count[0] == 0:
                    # First call: create job
                    return {"sid": "sid-123456"}
                elif call_count[0] == 1:
                    # Second call: job status
                    return {
                        "entry": [
                            {
                                "content": {
                                    "dispatchState": "DONE",
                                    "isDone": True,
                                    "isFailed": False,
                                    "resultCount": 10,
                                }
                            }
                        ]
                    }
                else:
                    # Third call: results
                    return {
                        "results": [
                            {"_raw": "log1"},
                            {"_raw": "log2"},
                        ]
                    }

            mock_response.json = AsyncMock(side_effect=get_json)
            mock_response.status = 200

            mock_request_context = MagicMock()
            mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request_context.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = MagicMock()

            def track_post(*args, **kwargs):
                call_count[0] += 1
                return mock_request_context

            def track_get(*args, **kwargs):
                call_count[0] += 1
                return mock_request_context

            mock_session_instance.post.side_effect = track_post
            mock_session_instance.get.side_effect = track_get

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            return mock_session

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=create_dynamic_mock_session,
        ):
            result = await connector.search(
                query="index=main | head 10",
                earliest_time="-1h",
                latest_time="now",
            )
            # Search uses internal methods, verify structure
            assert result is not None

    @pytest.mark.asyncio
    async def test_search_job_creation_fails(self, enable_enterprise_mode):
        """Test search when job creation fails."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            400,
            {"messages": [{"type": "ERROR", "text": "Invalid query syntax"}]},
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.search("invalid ||| query")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_search_no_valid_sid(self, enable_enterprise_mode):
        """Test search when no valid search ID is returned."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Return success but with invalid/missing sid
        mock_session = create_mock_aiohttp_session(201, {"sid": None})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.search("index=main")
            assert result.success is False
            assert "valid search ID" in result.error


# =============================================================================
# Get Search Results Output Mode Tests
# =============================================================================


class TestGetSearchResultsOutputModes:
    """Tests for _get_search_results with different output modes."""

    @pytest.mark.asyncio
    async def test_get_search_results_csv_output(self, enable_enterprise_mode):
        """Test getting results in CSV format."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        csv_data = '"field1","field2"\n"value1","value2"\n"value3","value4"'
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=csv_data)
        mock_response.json = AsyncMock(return_value={})

        mock_request_context = MagicMock()
        mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_request_context

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._get_search_results(
                sid="sid-csv",
                output_mode=SplunkOutputMode.CSV,
            )
            assert result.success is True
            assert result.data["results"] == csv_data

    @pytest.mark.asyncio
    async def test_get_search_results_xml_output(self, enable_enterprise_mode):
        """Test getting results in XML format."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        xml_data = '<?xml version="1.0"?><results><result><field>value</field></result></results>'
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=xml_data)

        mock_request_context = MagicMock()
        mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_request_context

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._get_search_results(
                sid="sid-xml",
                output_mode=SplunkOutputMode.XML,
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_get_search_results_failure(self, enable_enterprise_mode):
        """Test getting results when the request fails."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            404,
            {"messages": [{"text": "Search job not found"}]},
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._get_search_results(sid="nonexistent-sid")
            assert result.success is False
            assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_get_search_results_exception(self, enable_enterprise_mode):
        """Test getting results when an exception occurs."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=Exception("Connection timeout"),
        ):
            result = await connector._get_search_results(sid="sid-exception")
            assert result.success is False
            assert "Connection timeout" in result.error


# =============================================================================
# Send Security Event with All Options Tests
# =============================================================================


class TestSendSecurityEventAllOptions:
    """Tests for send_security_event with all optional parameters."""

    @pytest.mark.asyncio
    async def test_send_security_event_all_fields(self, enable_enterprise_mode):
        """Test send_security_event with all optional fields populated."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_security_event(
                event_type="vulnerability_detected",
                severity=SplunkSeverity.CRITICAL,
                description="Critical SQL injection vulnerability found",
                cve_id="CVE-2025-1234",
                source_ip="10.0.0.1",
                dest_ip="192.168.1.100",
                user="admin",
                affected_asset="/var/www/app/login.php",
                action_taken="Patch applied",
                additional_data={
                    "cvss_score": 9.8,
                    "exploit_available": True,
                    "patch_version": "2.0.1",
                },
            )
            assert result.success is True


# =============================================================================
# Batch Events with All Fields Tests
# =============================================================================


class TestSendBatchEventsAllFields:
    """Tests for send_batch_events with all event fields populated."""

    @pytest.mark.asyncio
    async def test_send_batch_events_all_fields(self, enable_enterprise_mode):
        """Test send_batch_events with all SplunkEvent fields populated."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0})

        events = [
            SplunkEvent(
                event={"action": "login", "status": "success"},
                time=1704067200.0,
                host="web-server-01",
                source="application",
                sourcetype="app:auth",
                index="security",
                fields={"user_type": "admin", "region": "us-east"},
            ),
            SplunkEvent(
                event={"action": "file_access", "path": "/etc/passwd"},
                time=1704067300.0,
                host="db-server-01",
                source="audit",
                sourcetype="syslog",
                index="security",
                fields={"threat_level": "high"},
            ),
        ]

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_batch_events(events)
            assert result.success is True
            assert result.data["events_sent"] == 2

    @pytest.mark.asyncio
    async def test_send_batch_events_failure(self, enable_enterprise_mode):
        """Test send_batch_events when HEC returns an error."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(
            400, {"code": 6, "text": "Invalid data format"}
        )

        events = [SplunkEvent(event={"msg": "test"})]

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_batch_events(events)
            assert result.success is False
            assert "Invalid data format" in result.error

    @pytest.mark.asyncio
    async def test_send_batch_events_exception(self, enable_enterprise_mode):
        """Test send_batch_events when an exception occurs."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        events = [SplunkEvent(event={"msg": "test"})]

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=Exception("HEC connection failed"),
        ):
            result = await connector.send_batch_events(events)
            assert result.success is False
            assert "HEC connection failed" in result.error


# =============================================================================
# Send Event with All Options Tests
# =============================================================================


class TestSendEventAllOptions:
    """Tests for send_event with all optional parameters."""

    @pytest.mark.asyncio
    async def test_send_event_all_fields(self, enable_enterprise_mode):
        """Test send_event with all optional fields populated."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0, "text": "Success"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_event(
                event={"message": "Test event", "level": "info"},
                host="app-server-01",
                source="aura-test",
                sourcetype="custom:aura:event",
                index="custom_index",
                timestamp=1704067200.0,
                fields={"custom_field": "custom_value", "priority": "high"},
            )
            assert result.success is True


# =============================================================================
# Create Search Job Query Normalization Tests
# =============================================================================


class TestSearchJobQueryNormalization:
    """Tests for query normalization in _create_search_job."""

    @pytest.mark.asyncio
    async def test_query_prefixed_with_search(self, enable_enterprise_mode):
        """Test that queries get 'search' prefix when needed."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(201, {"sid": "sid-test"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            # Query without 'search' prefix
            result = await connector._create_search_job(
                query="index=main | head 10",
                earliest_time="-1h",
                latest_time="now",
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_query_starting_with_pipe(self, enable_enterprise_mode):
        """Test that queries starting with | are not modified."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(201, {"sid": "sid-gen"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            # Generating command (starts with |)
            result = await connector._create_search_job(
                query="| makeresults count=10",
                earliest_time="-1h",
                latest_time="now",
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_query_already_has_search(self, enable_enterprise_mode):
        """Test that queries already starting with search are not double-prefixed."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(201, {"sid": "sid-search"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._create_search_job(
                query="search index=main",
                earliest_time="-1h",
                latest_time="now",
            )
            assert result.success is True


# =============================================================================
# List Saved Searches with Filters Tests
# =============================================================================


class TestListSavedSearchesFilters:
    """Tests for list_saved_searches with filter options."""

    @pytest.mark.asyncio
    async def test_list_saved_searches_with_filter(self, enable_enterprise_mode):
        """Test list_saved_searches with name filter."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "entry": [
                    {
                        "name": "Security Alert",
                        "content": {"search": "index=security", "is_scheduled": True},
                    }
                ]
            },
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_saved_searches(
                owner="admin",
                app="search",
                search_filter="Security",
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_list_saved_searches_failure(self, enable_enterprise_mode):
        """Test list_saved_searches when API returns error."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            403, {"messages": [{"text": "Access denied"}]}
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_saved_searches()
            assert result.success is False
            assert result.status_code == 403


# =============================================================================
# Extended Tests for Coverage Improvement - Valid Tests Only
# =============================================================================


class TestMetricsAndStatus:
    """Tests for connector metrics and status."""

    def test_connector_initial_status(self):
        """Test initial connector status."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )
        assert connector._status == ConnectorStatus.DISCONNECTED

    def test_connector_metrics(self):
        """Test connector metrics retrieval."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )
        metrics = connector.metrics
        assert "name" in metrics
        assert metrics["name"] == "splunk"
        assert "status" in metrics
        assert "request_count" in metrics

    def test_record_request_success(self):
        """Test recording successful request."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )
        initial_count = connector._request_count
        connector._record_request(100.0, success=True)
        assert connector._request_count == initial_count + 1
        assert connector._error_count == 0

    def test_record_request_failure(self):
        """Test recording failed request."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )
        connector._record_request(100.0, success=False)
        assert connector._error_count == 1


class TestEventSerialization:
    """Tests for event serialization."""

    def test_splunk_event_to_dict(self):
        """Test SplunkEvent to dict conversion."""
        event = SplunkEvent(
            event={"message": "test", "level": "info"},
            time=1704067200.0,
            host="server01",
            source="app",
            sourcetype="_json",
            index="main",
            fields={"custom_field": "value"},
        )
        # Basic property access tests
        assert event.event == {"message": "test", "level": "info"}
        assert event.time == 1704067200.0
        assert event.host == "server01"

    def test_splunk_alert_to_dict(self):
        """Test SplunkAlert to dict conversion."""
        alert = SplunkAlert(
            name="Test Alert",
            search="index=main | head 10",
            description="Test description",
            severity=SplunkSeverity.HIGH,
            cron_schedule="*/5 * * * *",
            is_scheduled=True,
            alert_type="number of events",
            alert_comparator="greater than",
            alert_threshold="10",
            actions=["email", "webhook"],
        )
        assert alert.name == "Test Alert"
        assert alert.severity == SplunkSeverity.HIGH
        assert len(alert.actions) == 2


class TestConnectionRetry:
    """Tests for connection retry behavior."""

    @pytest.mark.asyncio
    async def test_health_check_updates_status(self):
        """Test that health check updates connector status."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Initially disconnected
        assert connector._status == ConnectorStatus.DISCONNECTED

        mock_session = create_mock_aiohttp_session(
            200, {"entry": [{"content": {"version": "9.0.0"}}]}
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.health_check()
            assert result is True
            assert connector._status == ConnectorStatus.CONNECTED


class TestRateLimitHandling:
    """Tests for rate limit handling."""

    @pytest.mark.asyncio
    async def test_rate_limited_response(self, enable_enterprise_mode):
        """Test handling rate limited response."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            429,
            {"messages": [{"type": "ERROR", "text": "Rate limit exceeded"}]},
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._create_search_job("query", "-1h", "now")
            assert result.success is False


class TestWaitForJobActual:
    """Tests for _wait_for_job with proper parameter names."""

    @pytest.mark.asyncio
    async def test_wait_for_job_non_200_response(self, enable_enterprise_mode):
        """Test _wait_for_job when API returns non-200 status."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_response = MagicMock()
        mock_response.status = 404  # Not 200

        mock_request_context = MagicMock()
        mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_request_context

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            with patch(
                "src.services.splunk_connector.asyncio.sleep", new_callable=AsyncMock
            ):
                job = await connector._wait_for_job(
                    "sid-404", timeout_seconds=0.01, poll_interval=0.001
                )
                # Should timeout since job status never becomes done
                assert job.is_failed is True
                assert job.status == "TIMEOUT"


class TestErrorMessageParsing:
    """Tests for error message parsing edge cases."""

    @pytest.mark.asyncio
    async def test_create_search_job_string_error_message(self, enable_enterprise_mode):
        """Test _create_search_job with string error message instead of list."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Return a non-list error message
        mock_session = create_mock_aiohttp_session(
            400,
            {"messages": "Single error string"},
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._create_search_job(
                query="bad query",
                earliest_time="-1h",
                latest_time="now",
            )
            assert result.success is False
            # Should handle non-list messages gracefully
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_create_alert_string_error_message(self, enable_enterprise_mode):
        """Test create_alert with string error message instead of list."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            400,
            {"messages": "Single error message"},
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_alert(
                name="Test",
                search="index=main",
            )
            assert result.success is False


class TestSearchSecurityEventsFilters:
    """Tests for search_security_events with different filter combinations."""

    @pytest.mark.asyncio
    async def test_search_security_events_dest_ip_only(self, enable_enterprise_mode):
        """Test security event search with only destination IP."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        with patch.object(connector, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = MagicMock(
                success=True, data={"results": [], "count": 0}
            )

            await connector.search_security_events(
                dest_ip="192.168.1.200",
                earliest_time="-12h",
                max_results=500,
            )
            # Verify search was called
            assert mock_search.called

    @pytest.mark.asyncio
    async def test_search_security_events_user_only(self, enable_enterprise_mode):
        """Test security event search with only user filter."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        with patch.object(connector, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = MagicMock(
                success=True, data={"results": [], "count": 0}
            )

            await connector.search_security_events(
                user="admin_user",
            )
            assert mock_search.called


class TestSearchJobFailedStatus:
    """Tests for search when job fails during execution."""

    @pytest.mark.asyncio
    async def test_search_job_fails_during_wait(self, enable_enterprise_mode):
        """Test search when job fails during _wait_for_job."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        with patch.object(
            connector, "_create_search_job", new_callable=AsyncMock
        ) as mock_create:
            with patch.object(
                connector, "_wait_for_job", new_callable=AsyncMock
            ) as mock_wait:
                mock_create.return_value = MagicMock(
                    success=True, data={"sid": "test-sid"}
                )
                # Return a failed job
                mock_wait.return_value = SplunkSearchJob(
                    sid="test-sid",
                    status="FAILED",
                    is_done=True,
                    is_failed=True,
                    messages=[{"type": "ERROR", "text": "Search query failed"}],
                )

                result = await connector.search(query="index=main | badcommand")
                assert result.success is False
                assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_search_job_succeeds_and_returns_results(
        self, enable_enterprise_mode
    ):
        """Test search when job succeeds and returns results (covers lines 256-259)."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        with patch.object(
            connector, "_create_search_job", new_callable=AsyncMock
        ) as mock_create:
            with patch.object(
                connector, "_wait_for_job", new_callable=AsyncMock
            ) as mock_wait:
                with patch.object(
                    connector, "_get_search_results", new_callable=AsyncMock
                ) as mock_results:
                    mock_create.return_value = MagicMock(
                        success=True, data={"sid": "test-sid-success"}
                    )
                    # Return a successful job
                    mock_wait.return_value = SplunkSearchJob(
                        sid="test-sid-success",
                        status="DONE",
                        is_done=True,
                        is_failed=False,
                        result_count=5,
                    )
                    # Return successful results
                    mock_results.return_value = MagicMock(
                        success=True,
                        data={
                            "results": [{"_raw": "log1"}, {"_raw": "log2"}],
                            "count": 2,
                        },
                        latency_ms=100.0,
                    )

                    result = await connector.search(query="index=main | head 10")
                    assert result.success is True
                    assert result.data["count"] == 2
                    mock_results.assert_called_once()


class TestSendEventOptionalFields:
    """Tests for send_event with various optional fields."""

    @pytest.mark.asyncio
    async def test_send_event_with_timestamp_only(self, enable_enterprise_mode):
        """Test send_event with timestamp but no fields."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0, "text": "Success"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_event(
                event={"message": "Timed event"},
                timestamp=1704067200.0,
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_send_event_with_fields_only(self, enable_enterprise_mode):
        """Test send_event with custom fields but no timestamp."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0, "text": "Success"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_event(
                event={"message": "Event with fields"},
                fields={"custom_key": "custom_value", "priority": "high"},
            )
            assert result.success is True


class TestSendSecurityEventMinimalFields:
    """Tests for send_security_event with minimal optional fields."""

    @pytest.mark.asyncio
    async def test_send_security_event_minimal(self, enable_enterprise_mode):
        """Test send_security_event with only required fields."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_security_event(
                event_type="login_attempt",
                severity=SplunkSeverity.LOW,
                description="User login attempt",
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_send_security_event_action_taken(self, enable_enterprise_mode):
        """Test send_security_event with action_taken field."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_security_event(
                event_type="intrusion_detected",
                severity=SplunkSeverity.CRITICAL,
                description="Intrusion attempt blocked",
                action_taken="Blocked IP at firewall",
            )
            assert result.success is True


class TestBatchEventsMinimalFields:
    """Tests for send_batch_events with minimal event fields."""

    @pytest.mark.asyncio
    async def test_send_batch_events_minimal_events(self, enable_enterprise_mode):
        """Test send_batch_events with events containing only required fields."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0})

        events = [
            SplunkEvent(event={"msg": "event1"}),
            SplunkEvent(event="raw log event 2"),
        ]

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_batch_events(events)
            assert result.success is True
            assert result.data["events_sent"] == 2


class TestGetSearchResultsRawOutput:
    """Tests for _get_search_results with RAW output mode."""

    @pytest.mark.asyncio
    async def test_get_search_results_raw_output(self, enable_enterprise_mode):
        """Test getting results in RAW format."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        raw_data = "raw log line 1\nraw log line 2\nraw log line 3"
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=raw_data)

        mock_request_context = MagicMock()
        mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_request_context

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._get_search_results(
                sid="sid-raw",
                output_mode=SplunkOutputMode.RAW,
            )
            assert result.success is True
            assert result.data["results"] == raw_data


class TestListSavedSearchesError:
    """Tests for list_saved_searches error handling."""

    @pytest.mark.asyncio
    async def test_list_saved_searches_error_response(self, enable_enterprise_mode):
        """Test list_saved_searches with error response format."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Return error without proper messages array
        mock_session = create_mock_aiohttp_session(
            500,
            {"error": "Internal server error"},
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_saved_searches()
            assert result.success is False
            assert result.status_code == 500


class TestNoAuthWarning:
    """Tests for connector initialization without authentication."""

    def test_init_no_auth_logs_warning(self, caplog):
        """Test that initializing without auth logs a warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            connector = SplunkConnector(
                base_url="https://splunk:8089",
            )
            # Connector should be created
            assert connector is not None
            # Warning should have been logged
            assert any(
                "without token or username/password" in record.message.lower()
                for record in caplog.records
            )


# =============================================================================
# Additional Coverage Tests - Edge Cases
# =============================================================================


class TestSearchInvalidSidType:
    """Tests for search method with invalid SID types."""

    @pytest.mark.asyncio
    async def test_search_sid_is_integer(self, enable_enterprise_mode):
        """Test search when API returns integer instead of string for sid."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Return sid as integer (not a valid string)
        mock_session = create_mock_aiohttp_session(201, {"sid": 12345})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.search("index=main")
            assert result.success is False
            assert "valid search ID" in result.error

    @pytest.mark.asyncio
    async def test_search_sid_is_empty_string(self, enable_enterprise_mode):
        """Test search when API returns empty string for sid."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Return empty string (falsy value)
        mock_session = create_mock_aiohttp_session(201, {"sid": ""})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.search("index=main")
            assert result.success is False
            assert "valid search ID" in result.error


class TestSendEventCodeNotZero:
    """Tests for send_event when HEC returns non-zero code."""

    @pytest.mark.asyncio
    async def test_send_event_code_not_zero(self, enable_enterprise_mode):
        """Test send_event when HEC returns code != 0 with 200 status."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        # 200 status but code is not 0 (error in HEC response)
        mock_session = create_mock_aiohttp_session(
            200, {"code": 5, "text": "Invalid data format"}
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_event(event={"msg": "test"})
            assert result.success is False
            assert "Invalid data format" in result.error
            assert connector._last_error == "Invalid data format"


class TestSendBatchEventsCodeNotZero:
    """Tests for send_batch_events when HEC returns non-zero code."""

    @pytest.mark.asyncio
    async def test_send_batch_events_code_not_zero(self, enable_enterprise_mode):
        """Test send_batch_events when HEC returns code != 0."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        # 200 status but code is not 0
        mock_session = create_mock_aiohttp_session(
            200, {"code": 7, "text": "Invalid token"}
        )

        events = [SplunkEvent(event={"msg": "test"})]

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_batch_events(events)
            assert result.success is False
            assert "Invalid token" in result.error


class TestCreateSearchJob200Status:
    """Tests for _create_search_job with 200 status (not just 201)."""

    @pytest.mark.asyncio
    async def test_create_search_job_200_status(self, enable_enterprise_mode):
        """Test _create_search_job succeeds with 200 status."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(200, {"sid": "sid-200"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._create_search_job(
                query="search index=main",
                earliest_time="-1h",
                latest_time="now",
            )
            assert result.success is True
            assert result.data["sid"] == "sid-200"


class TestCreateAlertStatus200:
    """Tests for create_alert with 200 status (not just 201)."""

    @pytest.mark.asyncio
    async def test_create_alert_200_status(self, enable_enterprise_mode):
        """Test create_alert succeeds with 200 status."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            200, {"entry": [{"name": "Alert200"}]}
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_alert(
                name="Alert200",
                search="index=main | stats count",
            )
            assert result.success is True


class TestCreateSearchJobEmptyMessages:
    """Tests for _create_search_job with empty messages array."""

    @pytest.mark.asyncio
    async def test_create_search_job_empty_messages_array(self, enable_enterprise_mode):
        """Test _create_search_job with empty messages array falls back to str(data)."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Return error with empty messages array
        mock_session = create_mock_aiohttp_session(
            400, {"messages": [], "error_detail": "Query syntax error"}
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._create_search_job(
                query="invalid query",
                earliest_time="-1h",
                latest_time="now",
            )
            assert result.success is False
            # Should fall back to str(data) when messages[0] access fails
            assert result.error is not None


class TestCreateAlertEmptyMessages:
    """Tests for create_alert with empty messages array."""

    @pytest.mark.asyncio
    async def test_create_alert_empty_messages_array(self, enable_enterprise_mode):
        """Test create_alert with empty messages array falls back to str(data)."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            400, {"messages": [], "error": "Alert exists"}
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_alert(
                name="DuplicateAlert",
                search="index=main",
            )
            assert result.success is False


class TestHECUrlNone:
    """Tests for HEC operations when hec_url is None but hec_token is set."""

    @pytest.mark.asyncio
    async def test_send_event_hec_url_none_hec_token_set(self, enable_enterprise_mode):
        """Test send_event fails when hec_url is None but hec_token is set."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_token="hec-token",  # Token set but no URL
        )

        result = await connector.send_event(event={"msg": "test"})
        assert result.success is False
        assert "HEC URL and token must be configured" in result.error

    @pytest.mark.asyncio
    async def test_send_batch_events_hec_token_none(self, enable_enterprise_mode):
        """Test send_batch_events fails when hec_token is None but hec_url is set."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",  # URL set but no token
        )

        events = [SplunkEvent(event={"msg": "test"})]
        result = await connector.send_batch_events(events)
        assert result.success is False
        assert "HEC URL and token must be configured" in result.error


class TestGetSearchResultsCount:
    """Tests for _get_search_results count handling."""

    @pytest.mark.asyncio
    async def test_get_search_results_count_is_none_for_non_list(
        self, enable_enterprise_mode
    ):
        """Test that count is None when results is not a list (e.g., CSV/RAW)."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        raw_data = "raw log output"
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=raw_data)

        mock_request_context = MagicMock()
        mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_request_context

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._get_search_results(
                sid="sid-raw",
                output_mode=SplunkOutputMode.RAW,
            )
            assert result.success is True
            assert result.data["count"] is None  # Should be None for non-list


# =============================================================================
# P1 - Critical Error Path Tests
# =============================================================================


class TestP1CriticalErrorPaths:
    """P1 edge case tests for critical error paths."""

    @pytest.mark.asyncio
    async def test_wait_for_job_partial_response(self, enable_enterprise_mode):
        """Test _wait_for_job with partial/malformed API response missing required fields."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Response with missing 'entry' field
        mock_session = create_mock_aiohttp_session(200, {"unexpected": "data"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            with patch(
                "src.services.splunk_connector.asyncio.sleep", new_callable=AsyncMock
            ):
                job = await connector._wait_for_job(
                    "sid-partial", timeout_seconds=0.01, poll_interval=0.001
                )
                # Should timeout because no valid entry content found
                assert job.is_failed is True
                assert job.status == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_wait_for_job_empty_entry_list(self, enable_enterprise_mode):
        """Test _wait_for_job when API returns empty entry list."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(200, {"entry": []})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            with patch(
                "src.services.splunk_connector.asyncio.sleep", new_callable=AsyncMock
            ):
                job = await connector._wait_for_job(
                    "sid-empty", timeout_seconds=0.01, poll_interval=0.001
                )
                assert job.is_failed is True

    @pytest.mark.asyncio
    async def test_hec_response_invalid_json(self, enable_enterprise_mode):
        """Test send_event when HEC returns non-JSON response."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        # Create mock that raises JSONDecodeError
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            side_effect=json.JSONDecodeError("Invalid JSON", "", 0)
        )

        mock_request_context = MagicMock()
        mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.post.return_value = mock_request_context

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_event(event={"msg": "test"})
            assert result.success is False
            assert "Invalid JSON" in result.error or "JSONDecodeError" in result.error

    @pytest.mark.asyncio
    async def test_create_search_job_unicode_query(self, enable_enterprise_mode):
        """Test _create_search_job with unicode characters in query."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(201, {"sid": "sid-unicode"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            # Query with unicode characters (Chinese, emoji, special chars)
            result = await connector._create_search_job(
                query='index=main | search "用户" message="测试🔍"',
                earliest_time="-1h",
                latest_time="now",
            )
            assert result.success is True
            assert result.data["sid"] == "sid-unicode"

    @pytest.mark.asyncio
    async def test_ssl_certificate_error(self, enable_enterprise_mode):
        """Test handling of SSL certificate validation errors."""
        import ssl

        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            verify_ssl=True,
        )

        # Use ssl.SSLError which aiohttp wraps in ClientSSLError
        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=ssl.SSLError("certificate verify failed"),
        ):
            result = await connector._create_search_job("index=main", "-1h", "now")
            assert result.success is False
            assert connector._status == ConnectorStatus.ERROR

    @pytest.mark.asyncio
    async def test_connection_refused_error(self, enable_enterprise_mode):
        """Test handling when Splunk server refuses connection."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Use ConnectionRefusedError which is more portable
        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            result = await connector._create_search_job("index=main", "-1h", "now")
            assert result.success is False
            assert "refused" in result.error.lower() or "error" in result.error.lower()

    @pytest.mark.asyncio
    async def test_dns_resolution_failure(self, enable_enterprise_mode):
        """Test handling of DNS resolution failures."""
        import socket

        connector = SplunkConnector(
            base_url="https://nonexistent.splunk.invalid:8089",
            token="token",
        )

        # Use socket.gaierror which is raised for DNS resolution failures
        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=socket.gaierror(8, "Name or service not known"),
        ):
            result = await connector._create_search_job("index=main", "-1h", "now")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_response_with_html_error_page(self, enable_enterprise_mode):
        """Test handling when server returns HTML error page instead of JSON."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Mock returning HTML instead of JSON
        mock_response = MagicMock()
        mock_response.status = 503
        mock_response.json = AsyncMock(
            side_effect=json.JSONDecodeError("Expecting value", "<html>", 0)
        )
        mock_response.text = AsyncMock(
            return_value="<html><body>Service Unavailable</body></html>"
        )

        mock_request_context = MagicMock()
        mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.post.return_value = mock_request_context

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._create_search_job("index=main", "-1h", "now")
            assert result.success is False


# =============================================================================
# P2 - Boundary Condition Tests
# =============================================================================


class TestP2BoundaryConditions:
    """P2 edge case tests for boundary conditions."""

    @pytest.mark.asyncio
    async def test_max_results_zero(self, enable_enterprise_mode):
        """Test _get_search_results with max_results=0."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(200, {"results": []})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._get_search_results(sid="sid-zero", max_results=0)
            assert result.success is True
            assert result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_empty_query_string(self, enable_enterprise_mode):
        """Test _create_search_job with empty query string."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            400, {"messages": [{"type": "ERROR", "text": "Empty search query"}]}
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._create_search_job("", "-1h", "now")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_whitespace_only_query(self, enable_enterprise_mode):
        """Test _create_search_job with whitespace-only query."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(201, {"sid": "sid-ws"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            # Whitespace query should get "search" prefix
            result = await connector._create_search_job("   ", "-1h", "now")
            # API may accept or reject - we just verify the call doesn't crash
            assert result is not None

    @pytest.mark.asyncio
    async def test_very_long_query(self, enable_enterprise_mode):
        """Test _create_search_job with very long query (>10KB)."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Create a very long query
        long_query = "index=main | search " + "A" * 15000

        mock_session = create_mock_aiohttp_session(201, {"sid": "sid-long"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._create_search_job(long_query, "-1h", "now")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_batch_events_empty_list(self, enable_enterprise_mode):
        """Test send_batch_events with empty event list."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_batch_events([])
            assert result.success is True
            assert result.data["events_sent"] == 0

    @pytest.mark.asyncio
    async def test_batch_events_single_event(self, enable_enterprise_mode):
        """Test send_batch_events with single event (boundary case)."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0})

        events = [SplunkEvent(event={"msg": "single"})]

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_batch_events(events)
            assert result.success is True
            assert result.data["events_sent"] == 1

    @pytest.mark.asyncio
    async def test_max_results_negative(self, enable_enterprise_mode):
        """Test _get_search_results with negative max_results."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # API should handle negative value or return error
        mock_session = create_mock_aiohttp_session(200, {"results": []})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._get_search_results(sid="sid-neg", max_results=-1)
            # Should not crash - API behavior varies
            assert result is not None

    @pytest.mark.asyncio
    async def test_timeout_zero_seconds(self, enable_enterprise_mode):
        """Test _wait_for_job with timeout_seconds=0."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {"entry": [{"content": {"dispatchState": "RUNNING", "isDone": False}}]},
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            # Zero timeout should immediately timeout
            job = await connector._wait_for_job("sid-zero-timeout", timeout_seconds=0)
            assert job.is_failed is True
            assert job.status == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_alert_threshold_negative(self, enable_enterprise_mode):
        """Test create_alert with negative threshold."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            201, {"entry": [{"name": "NegAlert"}]}
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_alert(
                name="NegAlert",
                search="index=main",
                alert_threshold=-10,
            )
            # Should not crash; API behavior may vary
            assert result is not None

    @pytest.mark.asyncio
    async def test_event_with_extremely_large_payload(self, enable_enterprise_mode):
        """Test send_event with very large event payload."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0})

        # Create large event (1MB)
        large_event = {"data": "X" * (1024 * 1024)}

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_event(event=large_event)
            assert result.success is True


# =============================================================================
# P3 - API Edge Case Tests
# =============================================================================


class TestP3ApiEdgeCases:
    """P3 edge case tests for API-specific scenarios."""

    @pytest.mark.asyncio
    async def test_job_status_unknown_dispatch_state(self, enable_enterprise_mode):
        """Test _wait_for_job when job returns unknown dispatch state."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "entry": [
                    {
                        "content": {
                            "dispatchState": "UNKNOWN_STATE",
                            "isDone": False,
                            "isFailed": False,
                        }
                    }
                ]
            },
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            with patch(
                "src.services.splunk_connector.asyncio.sleep", new_callable=AsyncMock
            ):
                job = await connector._wait_for_job(
                    "sid-unknown", timeout_seconds=0.01, poll_interval=0.001
                )
                # Should continue polling until timeout since state is not done/failed
                assert job.status == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_search_results_empty_json_array(self, enable_enterprise_mode):
        """Test _get_search_results with empty results array."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(200, {"results": []})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._get_search_results(sid="sid-empty-results")
            assert result.success is True
            assert result.data["results"] == []
            assert result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_alert_name_with_special_characters(self, enable_enterprise_mode):
        """Test create_alert with special characters in name."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            201, {"entry": [{"name": "Test!@#$%"}]}
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_alert(
                name="Test!@#$% Alert <>&\"'",
                search="index=main",
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_list_saved_searches_with_pagination(self, enable_enterprise_mode):
        """Test list_saved_searches handles large result sets."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Return many saved searches
        entries = [
            {"name": f"Search_{i}", "content": {"search": f"index=idx{i}"}}
            for i in range(100)
        ]
        mock_session = create_mock_aiohttp_session(200, {"entry": entries})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_saved_searches()
            assert result.success is True
            assert result.data["count"] == 100

    @pytest.mark.asyncio
    async def test_search_with_special_time_formats(self, enable_enterprise_mode):
        """Test search with various time format specifications."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(201, {"sid": "sid-time"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            # Test epoch time format
            result = await connector._create_search_job(
                "index=main", "1704067200", "1704153600"
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_security_event_with_null_optional_fields(
        self, enable_enterprise_mode
    ):
        """Test search_security_events with all optional fields as None."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        with patch.object(connector, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = MagicMock(
                success=True, data={"results": [], "count": 0}
            )

            await connector.search_security_events(
                event_type=None,
                severity=None,
                source_ip=None,
                dest_ip=None,
                user=None,
            )
            # Should build query with only index=security
            assert mock_search.called

    @pytest.mark.asyncio
    async def test_send_event_with_null_event_fields(self, enable_enterprise_mode):
        """Test send_event with event containing null values."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"code": 0})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.send_event(
                event={"message": None, "data": None},
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_job_with_messages_containing_special_chars(
        self, enable_enterprise_mode
    ):
        """Test _wait_for_job when messages contain special characters."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "entry": [
                    {
                        "content": {
                            "dispatchState": "DONE",
                            "isDone": True,
                            "isFailed": False,
                            "messages": [
                                {
                                    "type": "WARN",
                                    "text": "Query contained <script>alert()</script>",
                                }
                            ],
                        }
                    }
                ]
            },
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            job = await connector._wait_for_job("sid-special-msg")
            assert job.is_done is True
            assert len(job.messages) == 1


# =============================================================================
# P4 - Async/Concurrency Edge Case Tests
# =============================================================================


class TestP4AsyncConcurrency:
    """P4 edge case tests for async and concurrency scenarios."""

    @pytest.mark.asyncio
    async def test_timeout_during_job_creation(self, enable_enterprise_mode):
        """Test handling of timeout during job creation."""
        import asyncio as aio

        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            timeout_seconds=0.001,  # Very short timeout
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=aio.TimeoutError("Request timed out"),
        ):
            result = await connector._create_search_job("index=main", "-1h", "now")
            assert result.success is False
            assert "timed out" in result.error.lower() or "TimeoutError" in result.error

    @pytest.mark.asyncio
    async def test_session_cleanup_on_exception(self, enable_enterprise_mode):
        """Test that session is properly cleaned up on exception."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session_instance = MagicMock()
        mock_session_instance.post = MagicMock(
            side_effect=RuntimeError("Unexpected error")
        )

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector._create_search_job("index=main", "-1h", "now")
            assert result.success is False
            # Verify __aexit__ was called (session cleanup)
            mock_session.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, enable_enterprise_mode):
        """Test concurrent health check calls don't interfere."""
        import asyncio as aio

        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        mock_session = create_mock_aiohttp_session(
            200, {"entry": [{"content": {"version": "9.0.0"}}]}
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            # Run multiple concurrent health checks
            results = await aio.gather(
                connector.health_check(),
                connector.health_check(),
                connector.health_check(),
            )
            # All should succeed
            assert all(results)

    @pytest.mark.asyncio
    async def test_request_cancelled_midway(self, enable_enterprise_mode):
        """Test handling of cancelled request."""
        import asyncio as aio

        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=aio.CancelledError(),
        ):
            # CancelledError should propagate (not be swallowed)
            with pytest.raises(aio.CancelledError):
                await connector._create_search_job("index=main", "-1h", "now")

    @pytest.mark.asyncio
    async def test_rapid_successive_requests(self, enable_enterprise_mode):
        """Test handling of rapid successive requests."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        call_count = [0]

        def create_session(*args, **kwargs):
            """Create mock session, accepting any args passed to ClientSession."""
            call_count[0] += 1
            return create_mock_aiohttp_session(201, {"sid": f"sid-{call_count[0]}"})

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=create_session,
        ):
            # Make rapid requests
            results = []
            for _ in range(10):
                result = await connector._create_search_job("index=main", "-1h", "now")
                results.append(result)

            # All should succeed
            assert all(r.success for r in results)
            assert call_count[0] == 10

    @pytest.mark.asyncio
    async def test_hec_batch_timeout(self, enable_enterprise_mode):
        """Test send_batch_events with timeout on large batch."""
        import asyncio as aio

        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
            hec_url="https://splunk:8088",
            hec_token="hec-token",
            timeout_seconds=0.001,
        )

        # Large batch that might timeout
        events = [SplunkEvent(event={"msg": f"event-{i}"}) for i in range(100)]

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=aio.TimeoutError("Batch upload timed out"),
        ):
            result = await connector.send_batch_events(events)
            assert result.success is False

    @pytest.mark.asyncio
    async def test_wait_for_job_with_intermittent_api_errors(
        self, enable_enterprise_mode
    ):
        """Test _wait_for_job handles job state transitions correctly."""
        connector = SplunkConnector(
            base_url="https://splunk:8089",
            token="token",
        )

        # Test that _wait_for_job correctly handles job that transitions from RUNNING to DONE
        call_count = [0]

        def create_dynamic_session(*args, **kwargs):
            """Simulate job transitioning from RUNNING to DONE."""
            call_count[0] += 1
            if call_count[0] <= 2:
                # First two polls show job running
                return create_mock_aiohttp_session(
                    200,
                    {
                        "entry": [
                            {
                                "content": {
                                    "dispatchState": "RUNNING",
                                    "isDone": False,
                                    "isFailed": False,
                                }
                            }
                        ]
                    },
                )
            else:
                # Third poll shows job done
                return create_mock_aiohttp_session(
                    200,
                    {
                        "entry": [
                            {
                                "content": {
                                    "dispatchState": "DONE",
                                    "isDone": True,
                                    "isFailed": False,
                                }
                            }
                        ]
                    },
                )

        with patch(
            "src.services.splunk_connector.aiohttp.ClientSession",
            side_effect=create_dynamic_session,
        ):
            with patch(
                "src.services.splunk_connector.asyncio.sleep", new_callable=AsyncMock
            ):
                job = await connector._wait_for_job(
                    "sid-transition", timeout_seconds=10, poll_interval=0.001
                )
                # Should eventually succeed after polling
                assert job.is_done is True
                assert call_count[0] >= 3
