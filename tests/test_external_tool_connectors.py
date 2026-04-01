"""
Tests for External Tool Connectors.

Tests the Slack, Jira, and PagerDuty connectors for ADR-023 Phase 3.
Uses mocked HTTP responses to avoid real API calls during testing.
"""

import json
import platform
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.external_tool_connectors import (
    ConnectorStatus,
    ExternalToolConnectorFactory,
    JiraConnector,
    JiraIssue,
    PagerDutyConnector,
    PagerDutySeverity,
    SlackConnector,
)

# =============================================================================
# Helper for mocking aiohttp
# =============================================================================


def create_mock_aiohttp_session(response_status: int, response_body: str | dict):
    """Create a properly mocked aiohttp session for async context managers.

    Args:
        response_status: HTTP status code to return
        response_body: Response body - str for text(), dict for json()
    """
    mock_response = MagicMock()
    mock_response.status = response_status

    if isinstance(response_body, dict):
        mock_response.json = AsyncMock(return_value=response_body)
        mock_response.text = AsyncMock(return_value=json.dumps(response_body))
    else:
        mock_response.text = AsyncMock(return_value=response_body)
        mock_response.json = AsyncMock(return_value={"error": response_body})

    # Create context manager for response
    mock_request_context = MagicMock()
    mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_request_context.__aexit__ = AsyncMock(return_value=None)

    # Create session instance
    mock_session_instance = MagicMock()
    mock_session_instance.post.return_value = mock_request_context
    mock_session_instance.get.return_value = mock_request_context

    # Create session context manager
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
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


@pytest.fixture
def slack_connector():
    """Create a Slack connector with test webhook URL."""
    return SlackConnector(
        webhook_url="https://hooks.slack.com/services/TEST/WEBHOOK/URL",
        default_channel="#test-channel",
    )


@pytest.fixture
def slack_connector_with_token():
    """Create a Slack connector with bot token."""
    return SlackConnector(
        bot_token="xoxb-test-token",
        default_channel="#test-channel",
    )


@pytest.fixture
def jira_connector():
    """Create a Jira connector with test credentials."""
    return JiraConnector(
        base_url="https://test.atlassian.net",
        email="test@example.com",
        api_token="test-api-token",
        default_project="SEC",
    )


@pytest.fixture
def pagerduty_connector():
    """Create a PagerDuty connector with test routing key."""
    return PagerDutyConnector(
        routing_key="test-routing-key",
        default_severity=PagerDutySeverity.ERROR,
    )


# =============================================================================
# Slack Connector Tests
# =============================================================================


class TestSlackConnector:
    """Tests for SlackConnector."""

    def test_initialization_with_webhook(self, slack_connector):
        """Test connector initializes with webhook URL."""
        assert slack_connector.webhook_url is not None
        assert slack_connector.name == "slack"
        assert slack_connector.default_channel == "#test-channel"

    def test_initialization_with_token(self, slack_connector_with_token):
        """Test connector initializes with bot token."""
        assert slack_connector_with_token.bot_token is not None
        assert slack_connector_with_token.webhook_url is None

    def test_initialization_without_credentials(self):
        """Test connector warns when no credentials provided."""
        connector = SlackConnector()
        assert connector.webhook_url is None
        assert connector.bot_token is None

    @pytest.mark.asyncio
    async def test_send_message_via_webhook_success(
        self, slack_connector, mock_enterprise_mode
    ):
        """Test sending message via webhook successfully."""
        mock_session = create_mock_aiohttp_session(200, "ok")

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await slack_connector.send_message(
                channel="#test",
                text="Test message",
            )

            assert result.success is True
            assert result.status_code == 200
            assert slack_connector.status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_send_message_via_webhook_failure(
        self, slack_connector, mock_enterprise_mode
    ):
        """Test handling webhook failure."""
        mock_session = create_mock_aiohttp_session(400, "invalid_payload")

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await slack_connector.send_message(text="Test")

            assert result.success is False
            assert result.error == "invalid_payload"

    @pytest.mark.asyncio
    async def test_send_message_via_api_success(
        self, slack_connector_with_token, mock_enterprise_mode
    ):
        """Test sending message via Web API successfully."""
        mock_session = create_mock_aiohttp_session(
            200, {"ok": True, "ts": "1234567890.123456"}
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await slack_connector_with_token.send_message(
                channel="#test",
                text="Test message",
            )

            assert result.success is True
            assert result.request_id == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_send_security_alert(self, slack_connector, mock_enterprise_mode):
        """Test sending formatted security alert."""
        mock_session = create_mock_aiohttp_session(200, "ok")

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await slack_connector.send_security_alert(
                severity="CRITICAL",
                title="SQL Injection Vulnerability",
                description="User input not sanitized in login form",
                cve_id="CVE-2024-1234",
                affected_file="src/auth/login.py",
                recommendation="Apply auto-generated patch",
                approval_url="https://aura.aenealabs.com/approvals/123",
            )

            assert result.success is True

    @pytest.mark.asyncio
    async def test_health_check_with_token(
        self, slack_connector_with_token, mock_enterprise_mode
    ):
        """Test health check with bot token."""
        mock_session = create_mock_aiohttp_session(200, {"ok": True})

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await slack_connector_with_token.health_check()

            assert result is True
            assert slack_connector_with_token.status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_health_check_with_webhook(
        self, slack_connector, mock_enterprise_mode
    ):
        """Test health check with webhook (assumes healthy if configured)."""
        result = await slack_connector.health_check()
        assert result is True
        assert slack_connector.status == ConnectorStatus.CONNECTED

    def test_metrics_tracking(self, slack_connector):
        """Test that metrics are tracked correctly."""
        slack_connector._record_request(100.0, True)
        slack_connector._record_request(150.0, True)
        slack_connector._record_request(200.0, False)

        metrics = slack_connector.metrics
        assert metrics["request_count"] == 3
        assert metrics["error_count"] == 1
        assert metrics["avg_latency_ms"] == 150.0


# =============================================================================
# Jira Connector Tests
# =============================================================================


class TestJiraConnector:
    """Tests for JiraConnector."""

    def test_initialization(self, jira_connector):
        """Test connector initializes correctly."""
        assert jira_connector.base_url == "https://test.atlassian.net"
        assert jira_connector.email == "test@example.com"
        assert jira_connector.default_project == "SEC"
        assert jira_connector.name == "jira"

    def test_auth_header_generated(self, jira_connector):
        """Test that auth header is properly encoded."""
        # Basic auth should be base64 encoded
        assert jira_connector._auth_header is not None
        assert len(jira_connector._auth_header) > 0

    @pytest.mark.asyncio
    async def test_create_issue_success(self, jira_connector, mock_enterprise_mode):
        """Test creating a Jira issue successfully."""
        mock_session = create_mock_aiohttp_session(
            201,
            {
                "id": "10001",
                "key": "SEC-123",
                "self": "https://test.atlassian.net/rest/api/3/issue/10001",
            },
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            issue = JiraIssue(
                project_key="SEC",
                summary="Test Issue",
                description="Test description",
                issue_type="Bug",
                priority="High",
                labels=["security", "test"],
            )

            result = await jira_connector.create_issue(issue)

            assert result.success is True
            assert result.request_id == "SEC-123"
            assert jira_connector.status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_create_issue_failure(self, jira_connector, mock_enterprise_mode):
        """Test handling issue creation failure."""
        mock_session = create_mock_aiohttp_session(
            400, {"errorMessages": ["Project not found"]}
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            issue = JiraIssue(
                project_key="INVALID",
                summary="Test Issue",
                description="Test",
            )

            result = await jira_connector.create_issue(issue)

            assert result.success is False
            assert "Project not found" in result.error

    @pytest.mark.asyncio
    async def test_create_security_issue(self, jira_connector, mock_enterprise_mode):
        """Test creating a formatted security issue."""
        mock_session = create_mock_aiohttp_session(
            201, {"id": "10002", "key": "SEC-124"}
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await jira_connector.create_security_issue(
                summary="SQL Injection in Login",
                cve_id="CVE-2024-1234",
                severity="HIGH",
                affected_file="src/auth/login.py",
                description="User input not sanitized",
            )

            assert result.success is True
            assert result.request_id == "SEC-124"

    @pytest.mark.asyncio
    async def test_add_comment_success(self, jira_connector, mock_enterprise_mode):
        """Test adding a comment to an issue."""
        mock_session = create_mock_aiohttp_session(
            201, {"id": "10001", "body": "Test comment"}
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await jira_connector.add_comment(
                issue_key="SEC-123",
                comment="Patch has been approved and deployed",
            )

            assert result.success is True

    @pytest.mark.asyncio
    async def test_transition_issue_success(self, jira_connector, mock_enterprise_mode):
        """Test transitioning an issue to a new status."""
        # Create mock responses for GET (transitions) and POST (execute transition)
        mock_transitions_response = MagicMock()
        mock_transitions_response.status = 200
        mock_transitions_response.json = AsyncMock(
            return_value={
                "transitions": [
                    {"id": "21", "name": "Done"},
                    {"id": "31", "name": "In Progress"},
                ]
            }
        )

        mock_transition_response = MagicMock()
        mock_transition_response.status = 204
        mock_transition_response.json = AsyncMock(return_value={})

        # Create context managers for both requests
        mock_get_context = MagicMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_transitions_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_post_context = MagicMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=mock_transition_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_get_context
        mock_session_instance.post.return_value = mock_post_context

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await jira_connector.transition_issue(
                issue_key="SEC-123",
                transition_name="Done",
            )

            assert result.success is True
            assert result.data["transition"] == "Done"

    @pytest.mark.asyncio
    async def test_health_check_success(self, jira_connector, mock_enterprise_mode):
        """Test health check returns healthy."""
        mock_session = create_mock_aiohttp_session(200, {})

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await jira_connector.health_check()

            assert result is True
            assert jira_connector.status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_health_check_auth_failure(
        self, jira_connector, mock_enterprise_mode
    ):
        """Test health check handles auth failure."""
        mock_session = create_mock_aiohttp_session(401, "Unauthorized")

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await jira_connector.health_check()

            assert result is False
            assert jira_connector.status == ConnectorStatus.AUTH_FAILED


# =============================================================================
# PagerDuty Connector Tests
# =============================================================================


class TestPagerDutyConnector:
    """Tests for PagerDutyConnector."""

    def test_initialization(self, pagerduty_connector):
        """Test connector initializes correctly."""
        assert pagerduty_connector.routing_key == "test-routing-key"
        assert pagerduty_connector.default_severity == PagerDutySeverity.ERROR
        assert pagerduty_connector.name == "pagerduty"

    @pytest.mark.asyncio
    async def test_trigger_incident_success(
        self, pagerduty_connector, mock_enterprise_mode
    ):
        """Test triggering an incident successfully."""
        mock_session = create_mock_aiohttp_session(
            202,
            {
                "status": "success",
                "message": "Event processed",
                "dedup_key": "test-dedup-key",
            },
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await pagerduty_connector.trigger_incident(
                summary="Test incident",
                severity=PagerDutySeverity.CRITICAL,
                source="test-source",
                custom_details={"key": "value"},
            )

            assert result.success is True
            assert result.status_code == 202
            assert pagerduty_connector.status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_trigger_incident_with_dedup_key(
        self, pagerduty_connector, mock_enterprise_mode
    ):
        """Test triggering incident with custom dedup key."""
        mock_session = create_mock_aiohttp_session(202, {"status": "success"})

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await pagerduty_connector.trigger_incident(
                summary="Test incident",
                dedup_key="CVE-2024-1234",
            )

            assert result.success is True
            assert result.request_id == "CVE-2024-1234"

    @pytest.mark.asyncio
    async def test_trigger_incident_failure(
        self, pagerduty_connector, mock_enterprise_mode
    ):
        """Test handling incident trigger failure."""
        mock_session = create_mock_aiohttp_session(
            400, {"status": "invalid", "message": "Invalid routing key"}
        )

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await pagerduty_connector.trigger_incident(
                summary="Test incident",
            )

            assert result.success is False
            assert "Invalid routing key" in result.error

    @pytest.mark.asyncio
    async def test_trigger_security_incident(
        self, pagerduty_connector, mock_enterprise_mode
    ):
        """Test triggering a formatted security incident."""
        mock_session = create_mock_aiohttp_session(202, {"status": "success"})

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await pagerduty_connector.trigger_security_incident(
                title="SQL Injection Vulnerability",
                cve_id="CVE-2024-1234",
                severity="CRITICAL",
                affected_file="src/auth/login.py",
                description="Critical vulnerability detected",
                approval_url="https://aura.aenealabs.com/approvals/123",
            )

            assert result.success is True
            # CVE should be used as dedup key
            assert result.request_id == "CVE-2024-1234"

    @pytest.mark.asyncio
    async def test_acknowledge_incident(
        self, pagerduty_connector, mock_enterprise_mode
    ):
        """Test acknowledging an incident."""
        mock_session = create_mock_aiohttp_session(202, {"status": "success"})

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await pagerduty_connector.acknowledge_incident(
                dedup_key="test-dedup-key"
            )

            assert result.success is True

    @pytest.mark.asyncio
    async def test_resolve_incident(self, pagerduty_connector, mock_enterprise_mode):
        """Test resolving an incident."""
        mock_session = create_mock_aiohttp_session(202, {"status": "success"})

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await pagerduty_connector.resolve_incident(
                dedup_key="test-dedup-key"
            )

            assert result.success is True

    @pytest.mark.asyncio
    async def test_health_check(self, pagerduty_connector, mock_enterprise_mode):
        """Test health check returns healthy when configured."""
        result = await pagerduty_connector.health_check()
        assert result is True
        assert pagerduty_connector.status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_health_check_no_routing_key(self, mock_enterprise_mode):
        """Test health check fails without routing key."""
        connector = PagerDutyConnector(routing_key="")
        result = await connector.health_check()
        assert result is False


# =============================================================================
# Connector Factory Tests
# =============================================================================


class TestExternalToolConnectorFactory:
    """Tests for ExternalToolConnectorFactory."""

    def test_create_slack_connector(self):
        """Test creating Slack connector via factory."""
        connector = ExternalToolConnectorFactory.create_slack(
            webhook_url="https://hooks.slack.com/test",
            default_channel="#alerts",
        )
        assert isinstance(connector, SlackConnector)
        assert connector.webhook_url == "https://hooks.slack.com/test"

    def test_create_jira_connector(self):
        """Test creating Jira connector via factory."""
        connector = ExternalToolConnectorFactory.create_jira(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="token",
        )
        assert isinstance(connector, JiraConnector)
        assert connector.base_url == "https://test.atlassian.net"

    def test_create_pagerduty_connector(self):
        """Test creating PagerDuty connector via factory."""
        connector = ExternalToolConnectorFactory.create_pagerduty(
            routing_key="test-key",
        )
        assert isinstance(connector, PagerDutyConnector)
        assert connector.routing_key == "test-key"

    def test_from_config_slack(self):
        """Test creating connector from config dict."""
        config = {
            "webhook_url": "https://hooks.slack.com/test",
            "default_channel": "#security",
        }
        connector = ExternalToolConnectorFactory.from_config("slack", config)
        assert isinstance(connector, SlackConnector)

    def test_from_config_jira(self):
        """Test creating Jira connector from config dict."""
        config = {
            "base_url": "https://company.atlassian.net",
            "email": "user@company.com",
            "api_token": "secret",
            "default_project": "SEC",
        }
        connector = ExternalToolConnectorFactory.from_config("jira", config)
        assert isinstance(connector, JiraConnector)

    def test_from_config_pagerduty(self):
        """Test creating PagerDuty connector from config dict."""
        config = {"routing_key": "test-routing-key"}
        connector = ExternalToolConnectorFactory.from_config("pagerduty", config)
        assert isinstance(connector, PagerDutyConnector)

    def test_from_config_unknown_tool(self):
        """Test factory raises error for unknown tool."""
        with pytest.raises(ValueError, match="Unknown tool"):
            ExternalToolConnectorFactory.from_config("unknown", {})


# =============================================================================
# Integration-like Tests
# =============================================================================


class TestConnectorWorkflows:
    """Test common workflows using multiple connectors."""

    @pytest.mark.asyncio
    async def test_security_alert_workflow(self, mock_enterprise_mode):
        """Test a complete security alert workflow."""
        # Create connectors
        slack = SlackConnector(webhook_url="https://hooks.slack.com/test")
        jira = JiraConnector(
            base_url="https://test.atlassian.net",
            email="test@test.com",
            api_token="token",
        )
        pagerduty = PagerDutyConnector(routing_key="test-key")

        # 1. Send Slack alert (webhooks expect "ok" string response)
        slack_mock = create_mock_aiohttp_session(200, "ok")
        with patch("aiohttp.ClientSession", return_value=slack_mock):
            slack_result = await slack.send_security_alert(
                severity="CRITICAL",
                title="SQL Injection in Authentication",
                cve_id="CVE-2024-1234",
                affected_file="src/auth/login.py",
                description="User input not sanitized",
            )

        # 2. Create Jira ticket (uses JSON response with key)
        jira_mock = create_mock_aiohttp_session(201, {"key": "SEC-123"})
        with patch("aiohttp.ClientSession", return_value=jira_mock):
            jira_result = await jira.create_security_issue(
                summary="SQL Injection in Authentication",
                cve_id="CVE-2024-1234",
                severity="CRITICAL",
                affected_file="src/auth/login.py",
                description="User input not sanitized",
            )

        # 3. Trigger PagerDuty incident (uses status: success)
        pd_mock = create_mock_aiohttp_session(202, {"status": "success"})
        with patch("aiohttp.ClientSession", return_value=pd_mock):
            pd_result = await pagerduty.trigger_security_incident(
                title="SQL Injection in Authentication",
                cve_id="CVE-2024-1234",
                severity="CRITICAL",
                affected_file="src/auth/login.py",
                description="User input not sanitized",
            )

        # All should succeed
        assert slack_result.success is True
        assert jira_result.success is True
        assert pd_result.success is True

    def test_connector_metrics_aggregation(self, mock_enterprise_mode):
        """Test aggregating metrics from multiple connectors."""
        slack = SlackConnector(webhook_url="https://test")
        jira = JiraConnector(
            base_url="https://test", email="test@test.com", api_token="token"
        )
        pagerduty = PagerDutyConnector(routing_key="test")

        # Simulate some requests
        slack._record_request(100, True)
        slack._record_request(150, True)
        jira._record_request(200, True)
        jira._record_request(250, False)
        pagerduty._record_request(50, True)

        # Aggregate metrics
        all_metrics = {
            "slack": slack.metrics,
            "jira": jira.metrics,
            "pagerduty": pagerduty.metrics,
        }

        total_requests = sum(m["request_count"] for m in all_metrics.values())
        total_errors = sum(m["error_count"] for m in all_metrics.values())

        assert total_requests == 5
        assert total_errors == 1


# =============================================================================
# Defense Mode Tests
# =============================================================================


class TestDefenseModeBlocking:
    """Test that connectors properly block operations in Defense mode."""

    @pytest.fixture
    def mock_defense_mode(self):
        """Mock defense mode for testing mode enforcement."""
        with patch("src.config.integration_config.get_integration_config") as mock:
            config = MagicMock()
            config.is_enterprise_mode = False
            config.is_defense_mode = True
            config.mode.value = "defense"
            mock.return_value = config
            yield mock

    @pytest.mark.asyncio
    async def test_slack_blocked_in_defense_mode(
        self, slack_connector, mock_defense_mode
    ):
        """Test Slack operations are blocked in Defense mode."""
        with pytest.raises(RuntimeError, match="requires ENTERPRISE mode"):
            await slack_connector.send_message(text="Test")

    @pytest.mark.asyncio
    async def test_jira_blocked_in_defense_mode(
        self, jira_connector, mock_defense_mode
    ):
        """Test Jira operations are blocked in Defense mode."""
        issue = JiraIssue(project_key="SEC", summary="Test", description="Test")
        with pytest.raises(RuntimeError, match="requires ENTERPRISE mode"):
            await jira_connector.create_issue(issue)

    @pytest.mark.asyncio
    async def test_pagerduty_blocked_in_defense_mode(
        self, pagerduty_connector, mock_defense_mode
    ):
        """Test PagerDuty operations are blocked in Defense mode."""
        with pytest.raises(RuntimeError, match="requires ENTERPRISE mode"):
            await pagerduty_connector.trigger_incident(summary="Test")
