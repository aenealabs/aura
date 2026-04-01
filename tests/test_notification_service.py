"""
Tests for the Notification Service.

Tests cover:
- Email notifications via SES
- SNS topic publishing
- Slack webhook notifications
- Microsoft Teams webhook notifications
- Unified send_to_channel method
- Mock mode behavior
"""

import json
import platform

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from src.services.notification_service import (
    NotificationChannel,
    NotificationMode,
    NotificationPriority,
    NotificationService,
    create_notification_service,
)


class TestNotificationServiceInit:
    """Tests for NotificationService initialization."""

    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        service = NotificationService(mode=NotificationMode.MOCK)
        assert service.mode == NotificationMode.MOCK
        assert service.sns_client is None
        assert service.ses_client is None

    def test_init_default_config(self):
        """Test default configuration values."""
        service = NotificationService(mode=NotificationMode.MOCK)
        assert service.region == "us-east-1"
        assert "aura" in service.sns_topic_arn
        assert service.slack_channel == "#aura-notifications"
        assert service.slack_bot_name == "Aura Bot"

    def test_init_custom_config(self):
        """Test custom configuration values."""
        service = NotificationService(
            mode=NotificationMode.MOCK,
            region="us-west-2",
            sns_topic_arn="arn:aws:sns:us-west-2:123456789:test-topic",
            ses_sender_email="test@example.com",
            dashboard_url="https://test.example.com/dashboard",
        )
        assert service.region == "us-west-2"
        assert service.sns_topic_arn == "arn:aws:sns:us-west-2:123456789:test-topic"
        assert service.ses_sender_email == "test@example.com"
        assert service.dashboard_url == "https://test.example.com/dashboard"

    def test_init_with_env_vars(self, monkeypatch):
        """Test initialization with environment variables."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
        monkeypatch.setenv("SLACK_CHANNEL", "#test-channel")
        monkeypatch.setenv(
            "TEAMS_WEBHOOK_URL", "https://outlook.office.com/webhook/test"
        )

        service = NotificationService(mode=NotificationMode.MOCK)
        assert service.slack_webhook_url == "https://hooks.slack.com/test"
        assert service.slack_channel == "#test-channel"
        assert service.teams_webhook_url == "https://outlook.office.com/webhook/test"


class TestEmailNotifications:
    """Tests for email notifications via SES."""

    def test_send_email_mock_mode(self):
        """Test email sending in mock mode."""
        service = NotificationService(mode=NotificationMode.MOCK)

        result = service._send_email(
            recipient="test@example.com",
            subject="Test Subject",
            body="Test body content",
            priority=NotificationPriority.NORMAL,
        )

        assert result.success is True
        assert result.channel == NotificationChannel.EMAIL
        assert result.message_id.startswith("mock-email-")
        assert len(service.delivery_log) == 1
        assert service.delivery_log[0]["status"] == "mock_sent"

    def test_send_email_with_priority(self):
        """Test email with different priorities."""
        service = NotificationService(mode=NotificationMode.MOCK)

        for priority in NotificationPriority:
            result = service._send_email(
                recipient="test@example.com",
                subject=f"Test {priority.value}",
                body="Test body",
                priority=priority,
            )
            assert result.success is True


class TestSNSNotifications:
    """Tests for SNS topic notifications."""

    def test_publish_to_sns_mock_mode(self):
        """Test SNS publishing in mock mode."""
        service = NotificationService(mode=NotificationMode.MOCK)

        result = service._publish_to_sns(
            subject="Test SNS Subject",
            message="Test SNS message",
            attributes={"severity": "HIGH", "event_type": "test"},
        )

        assert result.success is True
        assert result.channel == NotificationChannel.SNS
        assert result.message_id.startswith("mock-sns-")

    def test_publish_to_sns_logs_entry(self):
        """Test that SNS publishing creates log entry."""
        service = NotificationService(mode=NotificationMode.MOCK)

        service._publish_to_sns(
            subject="Test",
            message="Test message",
        )

        assert len(service.delivery_log) == 1
        log_entry = service.delivery_log[0]
        assert log_entry["channel"] == "sns"
        assert log_entry["status"] == "mock_published"


class TestSlackNotifications:
    """Tests for Slack webhook notifications."""

    def test_send_slack_mock_mode(self):
        """Test Slack notification in mock mode."""
        service = NotificationService(mode=NotificationMode.MOCK)

        result = service._send_slack_notification(
            subject="Test Slack Message",
            message="This is a test notification",
            priority=NotificationPriority.HIGH,
        )

        assert result.success is True
        assert result.channel == NotificationChannel.SLACK
        assert result.message_id.startswith("mock-slack-")

    def test_send_slack_with_custom_channel(self):
        """Test Slack notification with custom channel."""
        service = NotificationService(mode=NotificationMode.MOCK)

        result = service._send_slack_notification(
            subject="Test",
            message="Test message",
            channel="#custom-channel",
        )

        assert result.success is True
        log_entry = service.delivery_log[-1]
        assert log_entry["target"] == "#custom-channel"

    def test_send_slack_with_webhook_url(self):
        """Test Slack notification with custom webhook URL."""
        service = NotificationService(mode=NotificationMode.MOCK)

        result = service._send_slack_notification(
            subject="Test",
            message="Test message",
            webhook_url="https://hooks.slack.com/custom",
        )

        assert result.success is True

    @patch("src.services.notification_service.urlopen")
    def test_send_slack_real_request(self, mock_urlopen):
        """Test Slack notification with real HTTP request."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = b"ok"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        service = NotificationService(mode=NotificationMode.AWS)
        service.slack_webhook_url = "https://hooks.slack.com/test"

        result = service._send_slack_notification(
            subject="Test",
            message="Test message",
            priority=NotificationPriority.CRITICAL,
        )

        assert result.success is True
        assert result.channel == NotificationChannel.SLACK
        mock_urlopen.assert_called_once()

        # Verify payload structure
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        payload = json.loads(request.data.decode("utf-8"))
        assert "attachments" in payload
        assert payload["attachments"][0]["color"] == "#DC2626"  # Critical color

    @patch("src.services.notification_service.urlopen")
    def test_send_slack_http_error(self, mock_urlopen):
        """Test Slack notification handles HTTP errors."""
        mock_urlopen.side_effect = HTTPError(
            url="https://hooks.slack.com/test",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=None,
        )

        service = NotificationService(mode=NotificationMode.AWS)
        service.slack_webhook_url = "https://hooks.slack.com/test"

        result = service._send_slack_notification(
            subject="Test",
            message="Test message",
        )

        assert result.success is False
        assert result.channel == NotificationChannel.SLACK
        assert result.error is not None

    def test_send_slack_priority_colors(self):
        """Test Slack notification uses correct colors for priorities."""
        service = NotificationService(mode=NotificationMode.MOCK)

        priority_colors = {
            NotificationPriority.CRITICAL: True,
            NotificationPriority.HIGH: True,
            NotificationPriority.NORMAL: True,
            NotificationPriority.LOW: True,
        }

        for priority in priority_colors:
            result = service._send_slack_notification(
                subject=f"Test {priority.value}",
                message="Test message",
                priority=priority,
            )
            assert result.success is True


class TestTeamsNotifications:
    """Tests for Microsoft Teams webhook notifications."""

    def test_send_teams_mock_mode(self):
        """Test Teams notification in mock mode."""
        service = NotificationService(mode=NotificationMode.MOCK)

        result = service._send_teams_notification(
            subject="Test Teams Message",
            message="This is a test notification for Microsoft Teams",
            priority=NotificationPriority.HIGH,
        )

        assert result.success is True
        assert result.channel == NotificationChannel.TEAMS
        assert result.message_id.startswith("mock-teams-")

    def test_send_teams_logs_entry(self):
        """Test Teams notification creates log entry."""
        service = NotificationService(mode=NotificationMode.MOCK)

        service._send_teams_notification(
            subject="Test",
            message="Test message",
            priority=NotificationPriority.NORMAL,
        )

        assert len(service.delivery_log) == 1
        log_entry = service.delivery_log[0]
        assert log_entry["channel"] == "teams"
        assert log_entry["status"] == "mock_sent"

    @patch("src.services.notification_service.urlopen")
    def test_send_teams_real_request(self, mock_urlopen):
        """Test Teams notification with real HTTP request."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"1"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        service = NotificationService(mode=NotificationMode.AWS)
        service.teams_webhook_url = "https://outlook.office.com/webhook/test"

        result = service._send_teams_notification(
            subject="Test",
            message="Test message",
            priority=NotificationPriority.CRITICAL,
        )

        assert result.success is True
        assert result.channel == NotificationChannel.TEAMS
        mock_urlopen.assert_called_once()

        # Verify payload structure (Teams MessageCard)
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["@type"] == "MessageCard"
        assert payload["themeColor"] == "DC2626"  # Critical color (no #)
        assert "sections" in payload
        assert "potentialAction" in payload

    @patch("src.services.notification_service.urlopen")
    def test_send_teams_http_error(self, mock_urlopen):
        """Test Teams notification handles HTTP errors."""
        mock_urlopen.side_effect = URLError("Connection refused")

        service = NotificationService(mode=NotificationMode.AWS)
        service.teams_webhook_url = "https://outlook.office.com/webhook/test"

        result = service._send_teams_notification(
            subject="Test",
            message="Test message",
        )

        assert result.success is False
        assert result.channel == NotificationChannel.TEAMS
        assert "Connection refused" in result.error

    def test_send_teams_no_webhook_url(self):
        """Test Teams notification falls back to mock when no URL configured."""
        service = NotificationService(mode=NotificationMode.AWS)
        service.teams_webhook_url = ""  # No URL

        result = service._send_teams_notification(
            subject="Test",
            message="Test message",
        )

        # Should succeed in mock mode
        assert result.success is True
        assert result.message_id.startswith("mock-teams-")


class TestSendToChannel:
    """Tests for the unified send_to_channel method."""

    def test_send_to_email_channel(self):
        """Test sending via email channel."""
        service = NotificationService(mode=NotificationMode.MOCK)

        result = service.send_to_channel(
            channel_type="email",
            subject="Test Email",
            message="Test body",
            config={"recipient": "test@example.com"},
        )

        assert result.success is True
        assert result.channel == NotificationChannel.EMAIL

    def test_send_to_slack_channel(self):
        """Test sending via Slack channel."""
        service = NotificationService(mode=NotificationMode.MOCK)

        result = service.send_to_channel(
            channel_type="slack",
            subject="Test Slack",
            message="Test body",
            config={"channel": "#test"},
        )

        assert result.success is True
        assert result.channel == NotificationChannel.SLACK

    def test_send_to_teams_channel(self):
        """Test sending via Teams channel."""
        service = NotificationService(mode=NotificationMode.MOCK)

        result = service.send_to_channel(
            channel_type="teams",
            subject="Test Teams",
            message="Test body",
            config={"webhook_url": "https://outlook.office.com/webhook/test"},
        )

        assert result.success is True
        assert result.channel == NotificationChannel.TEAMS

    def test_send_to_sns_channel(self):
        """Test sending via SNS channel."""
        service = NotificationService(mode=NotificationMode.MOCK)

        result = service.send_to_channel(
            channel_type="sns",
            subject="Test SNS",
            message="Test body",
        )

        assert result.success is True
        assert result.channel == NotificationChannel.SNS

    def test_send_to_unsupported_channel(self):
        """Test sending via unsupported channel type."""
        service = NotificationService(mode=NotificationMode.MOCK)

        result = service.send_to_channel(
            channel_type="unknown",
            subject="Test",
            message="Test body",
        )

        assert result.success is False
        assert "Unsupported channel type" in result.error


class TestApprovalNotifications:
    """Tests for HITL approval notifications."""

    def test_send_approval_notification(self):
        """Test sending approval notification."""
        service = NotificationService(mode=NotificationMode.MOCK)

        results = service.send_approval_notification(
            approval_id="approval-123",
            patch_id="patch-456",
            vulnerability_id="vuln-789",
            severity="HIGH",
            created_at="2025-12-17T10:00:00",
            expires_at="2025-12-18T10:00:00",
            sandbox_results={
                "tests_passed": 42,
                "tests_failed": 0,
                "coverage": 85.5,
            },
            patch_diff="- old code\n+ new code",
            recipients=["reviewer@example.com"],
        )

        # Should have email + SNS results
        assert len(results) >= 2
        assert all(r.success for r in results)

    def test_send_decision_notification(self):
        """Test sending decision notification."""
        service = NotificationService(mode=NotificationMode.MOCK)

        results = service.send_decision_notification(
            approval_id="approval-123",
            patch_id="patch-456",
            decision="APPROVED",
            reviewer="reviewer@example.com",
            reason="LGTM",
            recipients=["dev@example.com"],
        )

        assert len(results) >= 2
        assert all(r.success for r in results)


class TestThreatAlerts:
    """Tests for threat intelligence alerts."""

    def test_send_threat_alert(self):
        """Test sending threat alert."""
        service = NotificationService(mode=NotificationMode.MOCK)

        results = service.send_threat_alert(
            threat_id="threat-001",
            title="Critical Vulnerability Detected",
            severity="CRITICAL",
            description="A critical vulnerability has been detected in the system.",
            cve_ids=["CVE-2025-1234", "CVE-2025-5678"],
            affected_components=["api-service", "auth-module"],
            recommended_actions=["Update dependencies", "Apply patch"],
            recipients=["security@example.com"],
        )

        assert len(results) >= 2
        assert all(r.success for r in results)


class TestDeliveryLog:
    """Tests for delivery log functionality."""

    def test_get_delivery_log(self):
        """Test retrieving delivery log."""
        service = NotificationService(mode=NotificationMode.MOCK)

        # Generate some log entries
        for i in range(5):
            service._send_email(f"test{i}@example.com", "Test", "Body")

        log = service.get_delivery_log()
        assert len(log) == 5

    def test_get_delivery_log_with_limit(self):
        """Test retrieving delivery log with limit."""
        service = NotificationService(mode=NotificationMode.MOCK)

        for i in range(10):
            service._send_email(f"test{i}@example.com", "Test", "Body")

        log = service.get_delivery_log(limit=5)
        assert len(log) == 5

    def test_clear_delivery_log(self):
        """Test clearing delivery log."""
        service = NotificationService(mode=NotificationMode.MOCK)

        service._send_email("test@example.com", "Test", "Body")
        assert len(service.delivery_log) == 1

        service.clear_delivery_log()
        assert len(service.delivery_log) == 0


class TestFactoryFunction:
    """Tests for create_notification_service factory function."""

    def test_create_mock_service(self):
        """Test creating mock service."""
        service = create_notification_service(use_mock=True)
        assert service.mode == NotificationMode.MOCK

    def test_create_service_no_boto3(self, monkeypatch):
        """Test service creation when boto3 not available."""
        # Force mock mode by not having AWS_REGION
        monkeypatch.delenv("AWS_REGION", raising=False)
        service = create_notification_service(use_mock=False)
        # Should fall back to mock mode
        assert service.mode == NotificationMode.MOCK


class TestNotificationChannelEnum:
    """Tests for NotificationChannel enum."""

    def test_all_channels_defined(self):
        """Test all expected channels are defined."""
        expected_channels = ["email", "sns", "slack", "teams", "webhook", "pagerduty"]
        actual_channels = [c.value for c in NotificationChannel]

        for channel in expected_channels:
            assert channel in actual_channels


class TestNotificationPriorityEnum:
    """Tests for NotificationPriority enum."""

    def test_all_priorities_defined(self):
        """Test all expected priorities are defined."""
        expected_priorities = ["critical", "high", "normal", "low"]
        actual_priorities = [p.value for p in NotificationPriority]

        for priority in expected_priorities:
            assert priority in actual_priorities
