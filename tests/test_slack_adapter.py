"""
Tests for the Slack Integration Adapter module.

Tests OAuth authentication, message posting, webhook operations,
channel management, and error handling for Slack integration.
"""

import hashlib
import hmac
import json
import platform
import time
from unittest.mock import MagicMock, patch

import pytest

from src.services.integrations.base_adapter import (
    IntegrationConfig,
    IntegrationStatus,
    IntegrationType,
    RateLimitError,
)
from src.services.integrations.slack_adapter import (
    SlackAdapter,
    SlackAuthType,
    SlackChannel,
    SlackConfig,
    SlackMessageType,
    create_slack_adapter,
)

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


@pytest.fixture
def mock_integration_config():
    """Create a mock integration config for Slack."""
    return IntegrationConfig(
        integration_id="slack-test-org",
        integration_type=IntegrationType.MONITORING,
        provider="slack",
        organization_id="test-org",
        credentials={
            "bot_token": "xoxb-test-token-12345",
            "webhook_url": "",
            "signing_secret": "test-signing-secret",
        },
        settings={
            "default_channel": "#security-alerts",
            "bot_name": "Test Aura Bot",
            "channel_mappings": {
                "alerts": "#security-alerts",
                "approvals": "#approvals",
            },
        },
    )


@pytest.fixture
def webhook_config():
    """Create a webhook-only config."""
    return IntegrationConfig(
        integration_id="slack-webhook-test",
        integration_type=IntegrationType.MONITORING,
        provider="slack",
        organization_id="test-org",
        credentials={
            "webhook_url": "https://hooks.slack.com/services/T123/B456/XXXXX",
        },
        settings={
            "default_channel": "#notifications",
        },
    )


@pytest.fixture
def oauth_config():
    """Create an OAuth config."""
    return IntegrationConfig(
        integration_id="slack-oauth-test",
        integration_type=IntegrationType.MONITORING,
        provider="slack",
        organization_id="test-org",
        credentials={
            "client_id": "123456.789012",
            "client_secret": "test-client-secret",
        },
        settings={
            "default_channel": "#security-alerts",
        },
    )


@pytest.fixture
def slack_adapter(mock_integration_config):
    """Create a SlackAdapter instance."""
    return SlackAdapter(mock_integration_config)


@pytest.fixture
def webhook_adapter(webhook_config):
    """Create a webhook-only SlackAdapter."""
    return SlackAdapter(webhook_config)


class TestSlackConfig:
    """Tests for SlackConfig dataclass."""

    def test_config_defaults(self):
        """Test default values are set correctly."""
        config = SlackConfig()

        assert config.default_channel == "#security-alerts"
        assert config.bot_name == "Aura Bot"
        assert config.bot_icon_emoji == ":robot_face:"
        assert "alerts" in config.channel_mappings
        assert "chat:write" in config.scopes

    def test_config_with_values(self):
        """Test config with custom values."""
        config = SlackConfig(
            bot_token="xoxb-custom-token",
            default_channel="#custom-channel",
            bot_name="Custom Bot",
        )

        assert config.bot_token == "xoxb-custom-token"
        assert config.default_channel == "#custom-channel"
        assert config.bot_name == "Custom Bot"


class TestSlackChannel:
    """Tests for SlackChannel dataclass."""

    def test_channel_creation(self):
        """Test creating a channel."""
        channel = SlackChannel(
            id="C123456",
            name="general",
            is_private=False,
            num_members=50,
        )

        assert channel.id == "C123456"
        assert channel.name == "general"
        assert channel.is_private is False
        assert channel.num_members == 50


class TestSlackEnums:
    """Tests for Slack enums."""

    def test_auth_type_values(self):
        """Test SlackAuthType enum values."""
        assert SlackAuthType.OAUTH.value == "oauth"
        assert SlackAuthType.WEBHOOK.value == "webhook"
        assert SlackAuthType.BOT_TOKEN.value == "bot_token"

    def test_message_type_values(self):
        """Test SlackMessageType enum values."""
        assert SlackMessageType.NOTIFICATION.value == "notification"
        assert SlackMessageType.ALERT.value == "alert"
        assert SlackMessageType.APPROVAL_REQUEST.value == "approval_request"


class TestSlackAdapterInit:
    """Tests for SlackAdapter initialization."""

    def test_adapter_creation(self, slack_adapter):
        """Test adapter is created correctly."""
        assert slack_adapter is not None
        assert slack_adapter.slack_config.bot_token == "xoxb-test-token-12345"
        assert slack_adapter.slack_config.default_channel == "#security-alerts"

    def test_adapter_parses_config(self, slack_adapter):
        """Test config parsing."""
        config = slack_adapter.slack_config

        assert config.bot_name == "Test Aura Bot"
        assert config.channel_mappings["alerts"] == "#security-alerts"
        assert config.channel_mappings["approvals"] == "#approvals"

    def test_webhook_adapter_creation(self, webhook_adapter):
        """Test webhook-only adapter creation."""
        assert (
            webhook_adapter.slack_config.webhook_url
            == "https://hooks.slack.com/services/T123/B456/XXXXX"
        )
        assert webhook_adapter.slack_config.bot_token == ""


class TestSlackAdapterConnect:
    """Tests for connect functionality."""

    @pytest.mark.asyncio
    async def test_connect_with_bot_token(self, slack_adapter):
        """Test connection with bot token."""
        mock_response = {
            "ok": True,
            "team_id": "T123456",
            "team": "Test Team",
            "user_id": "U123456",
            "user": "aura_bot",
        }

        with patch.object(slack_adapter, "_api_call", return_value=mock_response):
            result = await slack_adapter.connect()

        assert result.success is True
        assert slack_adapter.status == IntegrationStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_connect_with_webhook(self, webhook_adapter):
        """Test connection with webhook URL."""
        result = await webhook_adapter.connect()

        assert result.success is True
        assert result.data["mode"] == "webhook"

    @pytest.mark.asyncio
    async def test_connect_invalid_token(self, slack_adapter):
        """Test connection failure with invalid token."""
        mock_response = {
            "ok": False,
            "error": "invalid_auth",
        }

        with patch.object(slack_adapter, "_api_call", return_value=mock_response):
            result = await slack_adapter.connect()

        assert result.success is False
        assert slack_adapter.status == IntegrationStatus.ERROR

    @pytest.mark.asyncio
    async def test_connect_no_credentials(self, oauth_config):
        """Test connection fails without valid credentials."""
        # Remove OAuth credentials
        oauth_config.credentials = {}
        adapter = SlackAdapter(oauth_config)

        result = await adapter.connect()

        assert result.success is False
        assert "No valid Slack credentials" in result.error_message


class TestSlackAdapterDisconnect:
    """Tests for disconnect functionality."""

    @pytest.mark.asyncio
    async def test_disconnect(self, slack_adapter):
        """Test disconnect clears state."""
        # First connect
        with patch.object(slack_adapter, "_api_call", return_value={"ok": True}):
            await slack_adapter.connect()

        # Then disconnect
        result = await slack_adapter.disconnect()

        assert result.success is True
        assert slack_adapter.status == IntegrationStatus.DISCONNECTED


class TestSlackAdapterHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, slack_adapter):
        """Test successful health check."""
        mock_response = {
            "ok": True,
            "team": "Test Team",
            "url": "https://test.slack.com",
        }

        with patch.object(slack_adapter, "_api_call", return_value=mock_response):
            result = await slack_adapter.health_check()

        assert result.success is True
        assert result.latency_ms is not None

    @pytest.mark.asyncio
    async def test_health_check_webhook_mode(self, webhook_adapter):
        """Test health check in webhook mode."""
        webhook_adapter._status = IntegrationStatus.CONNECTED

        result = await webhook_adapter.health_check()

        assert result.success is True
        assert result.data["mode"] == "webhook"


class TestSlackAdapterSendMessage:
    """Tests for send_message functionality."""

    @pytest.mark.asyncio
    async def test_send_simple_message(self, slack_adapter):
        """Test sending a simple text message."""
        mock_response = {
            "ok": True,
            "ts": "1234567890.123456",
            "channel": "C123456",
            "message": {"text": "Hello"},
        }

        with patch.object(slack_adapter, "_api_call", return_value=mock_response):
            result = await slack_adapter.execute(
                "send_message",
                {"channel": "#test", "text": "Hello, World!"},
            )

        assert result.success is True
        assert result.data["ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_send_message_with_blocks(self, slack_adapter):
        """Test sending a message with blocks."""
        mock_response = {"ok": True, "ts": "123", "channel": "C123"}
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}]

        with patch.object(slack_adapter, "_api_call", return_value=mock_response):
            result = await slack_adapter.execute(
                "send_message",
                {"channel": "#test", "text": "Fallback", "blocks": blocks},
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_send_message_truncation(self, slack_adapter):
        """Test message truncation for long messages."""
        mock_response = {"ok": True, "ts": "123", "channel": "C123"}
        long_message = "x" * 50000  # Exceeds 40000 limit

        with patch.object(
            slack_adapter, "_api_call", return_value=mock_response
        ) as mock_call:
            await slack_adapter.execute(
                "send_message",
                {"channel": "#test", "text": long_message},
            )

            # Verify the message was truncated
            call_args = mock_call.call_args
            sent_text = call_args[0][1]["text"]
            assert len(sent_text) <= 40000
            assert sent_text.endswith("...")

    @pytest.mark.asyncio
    async def test_send_message_empty_content(self, slack_adapter):
        """Test sending empty message fails validation."""
        result = await slack_adapter.execute(
            "send_message",
            {"channel": "#test"},
        )

        assert result.success is False
        assert "OPERATION_FAILED" in result.error_code


class TestSlackAdapterPostNotification:
    """Tests for post_notification functionality."""

    @pytest.mark.asyncio
    async def test_post_notification_success(self, slack_adapter):
        """Test posting a formatted notification."""
        mock_response = {"ok": True, "ts": "123", "channel": "C123"}

        with patch.object(slack_adapter, "_api_call", return_value=mock_response):
            result = await slack_adapter.execute(
                "post_notification",
                {
                    "type": "alerts",
                    "title": "Security Alert",
                    "message": "Vulnerability detected",
                    "severity": "critical",
                    "fields": [
                        {"title": "CVE", "value": "CVE-2024-1234"},
                    ],
                },
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_post_notification_severity_colors(self, slack_adapter):
        """Test severity colors are applied correctly."""
        mock_response = {"ok": True, "ts": "123", "channel": "C123"}

        severities = ["critical", "high", "medium", "low", "info", "success"]

        for severity in severities:
            with patch.object(slack_adapter, "_api_call", return_value=mock_response):
                result = await slack_adapter.execute(
                    "post_notification",
                    {"title": "Test", "message": "Test", "severity": severity},
                )

                assert result.success is True


class TestSlackAdapterApprovalRequest:
    """Tests for send_approval_request functionality."""

    @pytest.mark.asyncio
    async def test_send_approval_request(self, slack_adapter):
        """Test sending HITL approval request."""
        mock_response = {"ok": True, "ts": "123", "channel": "C123"}

        with patch.object(slack_adapter, "_api_call", return_value=mock_response):
            result = await slack_adapter.execute(
                "send_approval_request",
                {
                    "approval_id": "apr-123",
                    "patch_id": "patch-456",
                    "vulnerability_id": "CVE-2024-1234",
                    "severity": "HIGH",
                    "expires_at": "2024-01-15T12:00:00Z",
                    "sandbox_results": {
                        "tests_passed": 42,
                        "tests_failed": 0,
                        "coverage": 95,
                    },
                    "review_url": "https://aura.example.com/review/apr-123",
                },
            )

        assert result.success is True


class TestSlackAdapterWebhook:
    """Tests for webhook operations."""

    @pytest.mark.asyncio
    async def test_post_webhook_success(self, webhook_adapter):
        """Test posting via incoming webhook."""
        mock_urlopen = MagicMock()
        mock_urlopen.__enter__ = MagicMock(return_value=mock_urlopen)
        mock_urlopen.__exit__ = MagicMock(return_value=False)
        mock_urlopen.read = MagicMock(return_value=b"ok")

        with patch(
            "src.services.integrations.slack_adapter.urlopen", return_value=mock_urlopen
        ):
            result = await webhook_adapter.execute(
                "post_webhook",
                {"text": "Test webhook message"},
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_post_webhook_no_url(self, slack_adapter):
        """Test webhook fails without URL configured."""
        result = await slack_adapter.execute(
            "post_webhook",
            {"text": "Test"},
        )

        assert result.success is False
        assert result.error_code == "NO_WEBHOOK"


class TestSlackAdapterChannelOperations:
    """Tests for channel operations."""

    @pytest.mark.asyncio
    async def test_list_channels(self, slack_adapter):
        """Test listing channels."""
        mock_response = {
            "ok": True,
            "channels": [
                {
                    "id": "C123",
                    "name": "general",
                    "is_private": False,
                    "num_members": 50,
                },
                {
                    "id": "C456",
                    "name": "security",
                    "is_private": True,
                    "num_members": 10,
                },
            ],
        }

        with patch.object(slack_adapter, "_api_call", return_value=mock_response):
            result = await slack_adapter.execute("list_channels", {})

        assert result.success is True
        assert len(result.data["channels"]) == 2

    @pytest.mark.asyncio
    async def test_get_channel_info(self, slack_adapter):
        """Test getting channel info."""
        mock_response = {
            "ok": True,
            "channel": {
                "id": "C123",
                "name": "general",
                "is_private": False,
                "topic": {"value": "General discussion"},
                "purpose": {"value": "Team communication"},
                "num_members": 50,
            },
        }

        with patch.object(slack_adapter, "_api_call", return_value=mock_response):
            result = await slack_adapter.execute(
                "get_channel_info",
                {"channel": "C123"},
            )

        assert result.success is True
        assert result.data["name"] == "general"

    @pytest.mark.asyncio
    async def test_join_channel(self, slack_adapter):
        """Test joining a channel."""
        mock_response = {
            "ok": True,
            "channel": {"id": "C123"},
        }

        with patch.object(slack_adapter, "_api_call", return_value=mock_response):
            result = await slack_adapter.execute(
                "join_channel",
                {"channel": "C123"},
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_lookup_user(self, slack_adapter):
        """Test looking up user by email."""
        mock_response = {
            "ok": True,
            "user": {
                "id": "U123",
                "name": "jdoe",
                "real_name": "John Doe",
                "profile": {
                    "display_name": "John",
                    "email": "john@example.com",
                },
            },
        }

        with patch.object(slack_adapter, "_api_call", return_value=mock_response):
            result = await slack_adapter.execute(
                "lookup_user",
                {"email": "john@example.com"},
            )

        assert result.success is True
        assert result.data["real_name"] == "John Doe"


class TestSlackAdapterValidation:
    """Tests for configuration validation."""

    def test_validate_config_valid(self, slack_adapter):
        """Test validation passes with valid config."""
        errors = slack_adapter.validate_config()
        assert len(errors) == 0

    def test_validate_config_no_auth(self, oauth_config):
        """Test validation fails without any auth method."""
        oauth_config.credentials = {}
        adapter = SlackAdapter(oauth_config)

        errors = adapter.validate_config()
        assert len(errors) > 0
        assert any("bot_token" in e or "webhook_url" in e for e in errors)

    def test_validate_invalid_webhook_url(self, webhook_config):
        """Test validation fails with invalid webhook URL."""
        webhook_config.credentials["webhook_url"] = "https://example.com/webhook"
        adapter = SlackAdapter(webhook_config)

        errors = adapter.validate_config()
        assert any("hooks.slack.com" in e for e in errors)

    def test_validate_invalid_channel_format(self, mock_integration_config):
        """Test validation with invalid channel format."""
        mock_integration_config.settings["default_channel"] = "invalid-channel"
        adapter = SlackAdapter(mock_integration_config)

        errors = adapter.validate_config()
        assert any("channel" in e.lower() for e in errors)


class TestSlackAdapterOAuth:
    """Tests for OAuth functionality."""

    def test_get_oauth_url(self, oauth_config):
        """Test generating OAuth URL."""
        oauth_config.credentials["client_id"] = "123456.789012"
        oauth_config.credentials["client_secret"] = "test-secret"
        adapter = SlackAdapter(oauth_config)

        url = adapter.get_oauth_url(
            redirect_uri="https://app.example.com/callback",
            state="test-state-123",
        )

        assert "slack.com/oauth/v2/authorize" in url
        assert "123456.789012" in url
        assert "test-state-123" in url

    @pytest.mark.asyncio
    async def test_complete_oauth_success(self, oauth_config):
        """Test completing OAuth flow."""
        oauth_config.credentials["client_id"] = "123456.789012"
        oauth_config.credentials["client_secret"] = "test-secret"
        adapter = SlackAdapter(oauth_config)

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read = MagicMock(
            return_value=json.dumps(
                {
                    "ok": True,
                    "access_token": "xoxb-new-token",
                    "team": {"id": "T123", "name": "Test Team"},
                }
            ).encode()
        )

        with patch(
            "src.services.integrations.slack_adapter.urlopen",
            return_value=mock_response,
        ):
            result = await adapter.complete_oauth(
                code="auth-code-123",
                redirect_uri="https://app.example.com/callback",
            )

        assert result.success is True
        assert result.data["access_token"] == "xoxb-new-token"


class TestSlackAdapterRateLimiting:
    """Tests for rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, slack_adapter):
        """Test rate limit error is handled correctly."""
        mock_response = {
            "ok": False,
            "error": "ratelimited",
            "retry_after": 30,
        }

        with patch.object(slack_adapter, "_api_call", return_value=mock_response):
            # This should not raise since rate limit is handled in execute
            result = await slack_adapter.execute(
                "send_message",
                {"channel": "#test", "text": "Hello"},
            )

            assert result.success is False

    def test_local_rate_limit_enforcement(self, slack_adapter):
        """Test local rate limit is enforced."""
        # Fill up request times
        now = time.time()
        slack_adapter._request_times = [now - i for i in range(50)]

        with pytest.raises(RateLimitError):
            slack_adapter._check_rate_limit()


class TestSlackAdapterWebhookSignature:
    """Tests for webhook signature verification."""

    def test_verify_signature_valid(self, slack_adapter):
        """Test valid signature verification."""
        timestamp = str(int(time.time()))
        body = b'{"type":"url_verification"}'

        # Compute expected signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        expected_sig = (
            "v0="
            + hmac.new(
                b"test-signing-secret",
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        result = slack_adapter.verify_webhook_signature(
            timestamp=timestamp,
            signature=expected_sig,
            body=body,
        )

        assert result is True

    def test_verify_signature_invalid(self, slack_adapter):
        """Test invalid signature is rejected."""
        timestamp = str(int(time.time()))
        body = b'{"type":"url_verification"}'

        result = slack_adapter.verify_webhook_signature(
            timestamp=timestamp,
            signature="v0=invalid_signature",
            body=body,
        )

        assert result is False

    def test_verify_signature_old_timestamp(self, slack_adapter):
        """Test old timestamp is rejected."""
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago
        body = b'{"type":"test"}'

        result = slack_adapter.verify_webhook_signature(
            timestamp=old_timestamp,
            signature="v0=test",
            body=body,
        )

        assert result is False

    def test_verify_signature_no_secret(self, webhook_adapter):
        """Test verification passes without signing secret (dev mode)."""
        result = webhook_adapter.verify_webhook_signature(
            timestamp="123",
            signature="v0=test",
            body=b"test",
        )

        # Should return True in dev mode
        assert result is True


class TestSlackAdapterUnknownOperation:
    """Tests for unknown operation handling."""

    @pytest.mark.asyncio
    async def test_unknown_operation(self, slack_adapter):
        """Test unknown operation returns error."""
        result = await slack_adapter.execute(
            "unknown_operation",
            {"param": "value"},
        )

        assert result.success is False
        assert result.error_code == "UNKNOWN_OPERATION"


class TestCreateSlackAdapter:
    """Tests for factory function."""

    def test_create_with_bot_token(self):
        """Test creating adapter with bot token."""
        adapter = create_slack_adapter(
            organization_id="org-123",
            bot_token="xoxb-test-token",
            default_channel="#alerts",
        )

        assert adapter.slack_config.bot_token == "xoxb-test-token"
        assert adapter.slack_config.default_channel == "#alerts"

    def test_create_with_webhook(self):
        """Test creating adapter with webhook."""
        adapter = create_slack_adapter(
            organization_id="org-123",
            webhook_url="https://hooks.slack.com/services/T/B/X",
        )

        assert (
            adapter.slack_config.webhook_url == "https://hooks.slack.com/services/T/B/X"
        )

    def test_create_with_oauth(self):
        """Test creating adapter with OAuth credentials."""
        adapter = create_slack_adapter(
            organization_id="org-123",
            client_id="123.456",
            client_secret="secret",
        )

        assert adapter.slack_config.client_id == "123.456"
        assert adapter.slack_config.client_secret == "secret"
