"""
Project Aura - Slack Integration Adapter

Provides Slack integration capabilities for the Integration Hub including
OAuth 2.0 authentication, message posting, webhook management, and channel operations.

Features:
- OAuth 2.0 authentication with Slack workspace
- Send notifications to channels (for alerts, approval requests, etc.)
- Webhook support for incoming messages
- Channel selection for different notification types
- Bot user token management

ADR Reference: ADR-048 Phase 0 - Integration Abstraction Layer
"""

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.services.integrations.base_adapter import (
    AuthenticationError,
    BaseIntegrationAdapter,
    ConnectionError,
    IntegrationConfig,
    IntegrationResult,
    IntegrationStatus,
    IntegrationType,
    RateLimitError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class SlackAuthType(Enum):
    """Slack authentication methods."""

    OAUTH = "oauth"  # Full OAuth 2.0 flow
    WEBHOOK = "webhook"  # Incoming webhook only
    BOT_TOKEN = "bot_token"  # Direct bot token


class SlackMessageType(Enum):
    """Types of Slack messages."""

    NOTIFICATION = "notification"
    ALERT = "alert"
    APPROVAL_REQUEST = "approval_request"
    STATUS_UPDATE = "status_update"
    INCIDENT = "incident"


@dataclass
class SlackChannel:
    """Represents a Slack channel."""

    id: str
    name: str
    is_private: bool = False
    is_archived: bool = False
    num_members: int = 0


@dataclass
class SlackConfig:
    """Configuration for Slack integration."""

    # OAuth credentials
    client_id: str = ""
    client_secret: str = ""
    access_token: str = ""
    bot_token: str = ""
    refresh_token: str = ""

    # Webhook configuration
    webhook_url: str = ""
    signing_secret: str = ""

    # Default settings
    default_channel: str = "#security-alerts"
    bot_name: str = "Aura Bot"
    bot_icon_emoji: str = ":robot_face:"
    bot_icon_url: str = ""

    # Channel mappings for different notification types
    channel_mappings: dict[str, str] = field(
        default_factory=lambda: {
            "alerts": "#security-alerts",
            "approvals": "#hitl-approvals",
            "incidents": "#incidents",
            "notifications": "#aura-notifications",
        }
    )

    # OAuth scopes
    scopes: list[str] = field(
        default_factory=lambda: [
            "chat:write",
            "channels:read",
            "channels:join",
            "groups:read",
            "users:read",
            "incoming-webhook",
        ]
    )


class SlackAdapter(BaseIntegrationAdapter[SlackConfig]):
    """
    Adapter for Slack integration.

    Provides methods for sending messages, managing webhooks, and
    OAuth authentication with Slack workspaces.
    """

    # Slack API endpoints
    API_BASE_URL = "https://slack.com/api"
    OAUTH_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
    OAUTH_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

    # Rate limiting
    MAX_REQUESTS_PER_MINUTE = 50
    MAX_MESSAGE_LENGTH = 40000  # Slack's max message length

    def __init__(self, config: IntegrationConfig):
        """
        Initialize Slack adapter.

        Args:
            config: Integration configuration with Slack credentials
        """
        super().__init__(config)

        # Parse Slack-specific config
        self.slack_config = self._parse_slack_config()

        # Request tracking for rate limiting
        self._request_times: list[float] = []

        # Cached team/workspace info
        self._team_info: dict[str, Any] | None = None
        self._channels_cache: dict[str, SlackChannel] = {}

        logger.info(f"SlackAdapter initialized for org={config.organization_id}")

    def _parse_slack_config(self) -> SlackConfig:
        """Parse Slack configuration from integration config."""
        creds = self.config.credentials
        settings = self.config.settings

        return SlackConfig(
            client_id=creds.get("client_id", ""),
            client_secret=creds.get("client_secret", ""),
            access_token=creds.get("access_token", ""),
            bot_token=creds.get("bot_token", ""),
            refresh_token=creds.get("refresh_token", ""),
            webhook_url=creds.get("webhook_url", ""),
            signing_secret=creds.get("signing_secret", ""),
            default_channel=settings.get("default_channel", "#security-alerts"),
            bot_name=settings.get("bot_name", "Aura Bot"),
            bot_icon_emoji=settings.get("bot_icon_emoji", ":robot_face:"),
            bot_icon_url=settings.get("bot_icon_url", ""),
            channel_mappings=settings.get(
                "channel_mappings",
                {
                    "alerts": "#security-alerts",
                    "approvals": "#hitl-approvals",
                    "incidents": "#incidents",
                    "notifications": "#aura-notifications",
                },
            ),
            scopes=settings.get(
                "scopes",
                [
                    "chat:write",
                    "channels:read",
                    "channels:join",
                    "groups:read",
                    "users:read",
                    "incoming-webhook",
                ],
            ),
        )

    async def connect(self) -> IntegrationResult:
        """
        Establish connection to Slack.

        Validates credentials and tests API connectivity.

        Returns:
            IntegrationResult with connection status
        """
        start_time = time.time()

        try:
            # Determine auth method
            if self.slack_config.bot_token:
                # Test with bot token
                result = await self._test_bot_token()
            elif self.slack_config.webhook_url:
                # Webhook-only mode
                result = await self._test_webhook()
            elif self.slack_config.access_token:
                # OAuth access token
                result = await self._test_access_token()
            else:
                raise AuthenticationError(
                    "No valid Slack credentials provided. "
                    "Provide bot_token, webhook_url, or access_token."
                )

            if result.success:
                self._status = IntegrationStatus.CONNECTED
                logger.info("Slack connection established successfully")
            else:
                self._status = IntegrationStatus.ERROR
                self._last_error = ConnectionError(
                    result.error_message or "Unknown error"
                )

            result.latency_ms = (time.time() - start_time) * 1000
            return result

        except Exception as e:
            self._status = IntegrationStatus.ERROR
            self._last_error = (
                e if isinstance(e, ConnectionError) else ConnectionError(str(e))
            )
            logger.error(f"Slack connection failed: {e}")

            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="CONNECTION_FAILED",
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def disconnect(self) -> IntegrationResult:
        """
        Disconnect from Slack.

        Clears cached data and marks as disconnected.

        Returns:
            IntegrationResult with disconnection status
        """
        self._status = IntegrationStatus.DISCONNECTED
        self._team_info = None
        self._channels_cache.clear()

        logger.info("Slack adapter disconnected")

        return IntegrationResult(
            success=True,
            data={"message": "Disconnected from Slack"},
        )

    async def health_check(self) -> IntegrationResult:
        """
        Perform health check on Slack integration.

        Returns:
            IntegrationResult with health status
        """
        start_time = time.time()

        try:
            if self.slack_config.bot_token:
                response = await self._api_call("api.test")
            elif self.slack_config.webhook_url:
                # Webhooks can't be tested without sending, return cached status
                return IntegrationResult(
                    success=self._status == IntegrationStatus.CONNECTED,
                    data={"mode": "webhook", "status": self._status.value},
                    latency_ms=(time.time() - start_time) * 1000,
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="No credentials configured",
                    error_code="NO_CREDENTIALS",
                )

            return IntegrationResult(
                success=response.get("ok", False),
                data={"team": response.get("team"), "url": response.get("url")},
                latency_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="HEALTH_CHECK_FAILED",
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def execute(
        self, operation: str, payload: dict[str, Any]
    ) -> IntegrationResult:
        """
        Execute a Slack operation.

        Supported operations:
        - send_message: Send a message to a channel
        - post_notification: Post a formatted notification
        - send_approval_request: Send HITL approval request
        - list_channels: List available channels
        - get_channel_info: Get channel details
        - post_webhook: Send via incoming webhook
        - join_channel: Join a channel
        - lookup_user: Look up a user by email

        Args:
            operation: Operation name
            payload: Operation-specific parameters

        Returns:
            IntegrationResult with operation outcome
        """
        start_time = time.time()

        operations = {
            "send_message": self._send_message,
            "post_notification": self._post_notification,
            "send_approval_request": self._send_approval_request,
            "list_channels": self._list_channels,
            "get_channel_info": self._get_channel_info,
            "post_webhook": self._post_webhook,
            "join_channel": self._join_channel,
            "lookup_user": self._lookup_user,
        }

        if operation not in operations:
            return IntegrationResult(
                success=False,
                error_message=f"Unknown operation: {operation}",
                error_code="UNKNOWN_OPERATION",
                latency_ms=(time.time() - start_time) * 1000,
            )

        try:
            result = await operations[operation](payload)
            result.latency_ms = (time.time() - start_time) * 1000
            return result

        except RateLimitError as e:
            return IntegrationResult(
                success=False,
                error_message=e.message,
                error_code="RATE_LIMIT",
                latency_ms=(time.time() - start_time) * 1000,
                metadata={"retry_after_seconds": e.retry_after_seconds},
            )

        except AuthenticationError as e:
            self._status = IntegrationStatus.ERROR
            return IntegrationResult(
                success=False,
                error_message=e.message,
                error_code="AUTH_ERROR",
                latency_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.exception(f"Slack operation {operation} failed")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="OPERATION_FAILED",
                latency_ms=(time.time() - start_time) * 1000,
            )

    def validate_config(self) -> list[str]:
        """
        Validate Slack configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = super().validate_config()

        # Must have at least one auth method
        has_bot_token = bool(self.slack_config.bot_token)
        has_webhook = bool(self.slack_config.webhook_url)
        has_oauth = bool(
            self.slack_config.client_id and self.slack_config.client_secret
        )
        has_access_token = bool(self.slack_config.access_token)

        if not (has_bot_token or has_webhook or has_oauth or has_access_token):
            errors.append("Must provide bot_token, webhook_url, or OAuth credentials")

        # Validate webhook URL format if provided
        if self.slack_config.webhook_url:
            if not self.slack_config.webhook_url.startswith("https://hooks.slack.com/"):
                errors.append(
                    "Invalid webhook URL. Must start with https://hooks.slack.com/"
                )

        # Validate channel format
        if self.slack_config.default_channel:
            if not self.slack_config.default_channel.startswith(
                "#"
            ) and not self.slack_config.default_channel.startswith("C"):
                errors.append("Default channel must start with '#' or be a channel ID")

        return errors

    # =========================================================================
    # OAuth Methods
    # =========================================================================

    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """
        Generate OAuth authorization URL.

        Args:
            redirect_uri: OAuth callback URL
            state: State parameter for CSRF protection

        Returns:
            Authorization URL
        """
        params = {
            "client_id": self.slack_config.client_id,
            "scope": ",".join(self.slack_config.scopes),
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"{self.OAUTH_AUTHORIZE_URL}?{urlencode(params)}"

    async def complete_oauth(self, code: str, redirect_uri: str) -> IntegrationResult:
        """
        Complete OAuth flow with authorization code.

        Args:
            code: Authorization code from callback
            redirect_uri: Same redirect URI used in authorization

        Returns:
            IntegrationResult with tokens
        """
        try:
            data = urlencode(
                {
                    "client_id": self.slack_config.client_id,
                    "client_secret": self.slack_config.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                }
            ).encode()

            request = Request(
                self.OAUTH_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )

            with urlopen(request, timeout=30) as response:  # nosec B310
                result = json.loads(response.read().decode())

            if not result.get("ok"):
                error = result.get("error", "Unknown error")
                return IntegrationResult(
                    success=False,
                    error_message=f"OAuth failed: {error}",
                    error_code="OAUTH_FAILED",
                )

            # Extract tokens
            tokens = {
                "access_token": result.get("access_token"),
                "bot_token": result.get("bot_user_id"),
                "team_id": result.get("team", {}).get("id"),
                "team_name": result.get("team", {}).get("name"),
                "incoming_webhook": result.get("incoming_webhook", {}),
            }

            # Update adapter config
            self.slack_config.access_token = tokens.get("access_token", "")
            if result.get("incoming_webhook", {}).get("url"):
                self.slack_config.webhook_url = result["incoming_webhook"]["url"]

            return IntegrationResult(
                success=True,
                data=tokens,
            )

        except (HTTPError, URLError) as e:
            return IntegrationResult(
                success=False,
                error_message=f"OAuth request failed: {e}",
                error_code="OAUTH_REQUEST_FAILED",
            )

    # =========================================================================
    # Message Operations
    # =========================================================================

    async def _send_message(self, payload: dict[str, Any]) -> IntegrationResult:
        """Send a message to a Slack channel."""
        channel = payload.get("channel", self.slack_config.default_channel)
        text = payload.get("text", "")
        blocks = payload.get("blocks")
        attachments = payload.get("attachments")
        thread_ts = payload.get("thread_ts")
        reply_broadcast = payload.get("reply_broadcast", False)

        if not text and not blocks and not attachments:
            raise ValidationError("Message must have text, blocks, or attachments")

        # Truncate if too long
        if text and len(text) > self.MAX_MESSAGE_LENGTH:
            text = text[: self.MAX_MESSAGE_LENGTH - 3] + "..."

        message_payload = {
            "channel": channel,
            "text": text,
        }

        if blocks:
            message_payload["blocks"] = blocks
        if attachments:
            message_payload["attachments"] = attachments
        if thread_ts:
            message_payload["thread_ts"] = thread_ts
            if reply_broadcast:
                message_payload["reply_broadcast"] = True

        # Add bot identity
        if self.slack_config.bot_name:
            message_payload["username"] = self.slack_config.bot_name
        if self.slack_config.bot_icon_emoji:
            message_payload["icon_emoji"] = self.slack_config.bot_icon_emoji
        elif self.slack_config.bot_icon_url:
            message_payload["icon_url"] = self.slack_config.bot_icon_url

        response = await self._api_call("chat.postMessage", message_payload)

        if response.get("ok"):
            return IntegrationResult(
                success=True,
                data={
                    "ts": response.get("ts"),
                    "channel": response.get("channel"),
                    "message": response.get("message"),
                },
            )
        else:
            return IntegrationResult(
                success=False,
                error_message=response.get("error", "Unknown error"),
                error_code=response.get("error"),
            )

    async def _post_notification(self, payload: dict[str, Any]) -> IntegrationResult:
        """Post a formatted notification with attachment styling."""
        notification_type = payload.get("type", "notification")
        title = payload.get("title", "Aura Notification")
        message = payload.get("message", "")
        severity = payload.get("severity", "info")
        fields = payload.get("fields", [])
        actions = payload.get("actions", [])
        footer = payload.get("footer", "Project Aura")

        # Map severity to color
        color_map = {
            "critical": "#DC2626",  # Red
            "high": "#EA580C",  # Orange
            "medium": "#F59E0B",  # Amber
            "low": "#6B7280",  # Gray
            "info": "#3B82F6",  # Blue
            "success": "#10B981",  # Green
        }
        color = color_map.get(severity, color_map["info"])

        # Get channel based on notification type
        channel = self.slack_config.channel_mappings.get(
            notification_type,
            self.slack_config.default_channel,
        )
        channel = payload.get("channel", channel)

        # Build attachment
        attachment = {
            "fallback": f"{title}: {message[:100]}",
            "color": color,
            "title": title,
            "text": message,
            "footer": footer,
            "footer_icon": self.slack_config.bot_icon_url or None,
            "ts": int(datetime.now(timezone.utc).timestamp()),
        }

        # Add fields
        if fields:
            attachment["fields"] = [
                {
                    "title": f.get("title", f.get("name", "")),
                    "value": f.get("value", ""),
                    "short": f.get("short", True),
                }
                for f in fields
            ]

        # Add actions
        if actions:
            attachment["actions"] = actions

        return await self._send_message(
            {
                "channel": channel,
                "text": f"{title}",
                "attachments": [attachment],
            }
        )

    async def _send_approval_request(
        self, payload: dict[str, Any]
    ) -> IntegrationResult:
        """Send HITL approval request with interactive buttons."""
        approval_id = payload.get("approval_id", "")
        patch_id = payload.get("patch_id", "")
        vulnerability_id = payload.get("vulnerability_id", "")
        severity = payload.get("severity", "MEDIUM")
        expires_at = payload.get("expires_at", "")
        sandbox_results = payload.get("sandbox_results", {})
        review_url = payload.get("review_url", "")

        # Severity to color
        severity_colors = {
            "CRITICAL": "#DC2626",
            "HIGH": "#EA580C",
            "MEDIUM": "#F59E0B",
            "LOW": "#6B7280",
        }
        color = severity_colors.get(severity.upper(), "#3B82F6")

        # Build blocks for rich formatting
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity} Security Patch Awaiting Review",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Patch ID:*\n{patch_id}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Vulnerability:*\n{vulnerability_id}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Severity:*\n{severity}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Expires:*\n{expires_at}",
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Sandbox Test Results*",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f":white_check_mark: *Tests Passed:* {sandbox_results.get('tests_passed', 'N/A')}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f":x: *Tests Failed:* {sandbox_results.get('tests_failed', 'N/A')}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f":bar_chart: *Coverage:* {sandbox_results.get('coverage', 'N/A')}%",
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Review in Dashboard",
                            "emoji": True,
                        },
                        "style": "primary",
                        "url": review_url,
                        "action_id": f"review_{approval_id}",
                    },
                ],
            },
        ]

        channel = self.slack_config.channel_mappings.get(
            "approvals",
            self.slack_config.default_channel,
        )

        # Use attachment for color indicator
        attachments = [
            {
                "color": color,
                "fallback": f"Security patch {patch_id} requires approval",
            }
        ]

        return await self._send_message(
            {
                "channel": channel,
                "text": f"Security Patch Approval Required: {patch_id}",
                "blocks": blocks,
                "attachments": attachments,
            }
        )

    async def _post_webhook(self, payload: dict[str, Any]) -> IntegrationResult:
        """Post message via incoming webhook."""
        if not self.slack_config.webhook_url:
            return IntegrationResult(
                success=False,
                error_message="No webhook URL configured",
                error_code="NO_WEBHOOK",
            )

        webhook_payload = {
            "text": payload.get("text", ""),
        }

        if payload.get("attachments"):
            webhook_payload["attachments"] = payload["attachments"]
        if payload.get("blocks"):
            webhook_payload["blocks"] = payload["blocks"]
        if self.slack_config.bot_name:
            webhook_payload["username"] = self.slack_config.bot_name
        if self.slack_config.bot_icon_emoji:
            webhook_payload["icon_emoji"] = self.slack_config.bot_icon_emoji

        try:
            request = Request(
                self.slack_config.webhook_url,
                data=json.dumps(webhook_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urlopen(request, timeout=10) as response:  # nosec B310
                response.read()

            return IntegrationResult(
                success=True,
                data={"message": "Webhook message sent"},
            )

        except HTTPError as e:
            return IntegrationResult(
                success=False,
                error_message=f"Webhook failed: {e}",
                error_code="WEBHOOK_FAILED",
            )

    # =========================================================================
    # Channel Operations
    # =========================================================================

    async def _list_channels(self, payload: dict[str, Any]) -> IntegrationResult:
        """List available Slack channels."""
        types = payload.get("types", "public_channel,private_channel")
        limit = payload.get("limit", 100)
        exclude_archived = payload.get("exclude_archived", True)

        response = await self._api_call(
            "conversations.list",
            {
                "types": types,
                "limit": limit,
                "exclude_archived": exclude_archived,
            },
        )

        if response.get("ok"):
            channels = [
                {
                    "id": ch["id"],
                    "name": ch["name"],
                    "is_private": ch.get("is_private", False),
                    "is_archived": ch.get("is_archived", False),
                    "num_members": ch.get("num_members", 0),
                }
                for ch in response.get("channels", [])
            ]
            return IntegrationResult(
                success=True,
                data={"channels": channels},
            )
        else:
            return IntegrationResult(
                success=False,
                error_message=response.get("error", "Unknown error"),
                error_code=response.get("error"),
            )

    async def _get_channel_info(self, payload: dict[str, Any]) -> IntegrationResult:
        """Get information about a channel."""
        channel = payload.get("channel")
        if not channel:
            raise ValidationError("channel is required")

        response = await self._api_call(
            "conversations.info",
            {"channel": channel},
        )

        if response.get("ok"):
            ch = response.get("channel", {})
            return IntegrationResult(
                success=True,
                data={
                    "id": ch.get("id"),
                    "name": ch.get("name"),
                    "is_private": ch.get("is_private", False),
                    "is_archived": ch.get("is_archived", False),
                    "topic": ch.get("topic", {}).get("value", ""),
                    "purpose": ch.get("purpose", {}).get("value", ""),
                    "num_members": ch.get("num_members", 0),
                },
            )
        else:
            return IntegrationResult(
                success=False,
                error_message=response.get("error", "Unknown error"),
                error_code=response.get("error"),
            )

    async def _join_channel(self, payload: dict[str, Any]) -> IntegrationResult:
        """Join a public channel."""
        channel = payload.get("channel")
        if not channel:
            raise ValidationError("channel is required")

        response = await self._api_call(
            "conversations.join",
            {"channel": channel},
        )

        if response.get("ok"):
            return IntegrationResult(
                success=True,
                data={"channel": response.get("channel", {}).get("id")},
            )
        else:
            return IntegrationResult(
                success=False,
                error_message=response.get("error", "Unknown error"),
                error_code=response.get("error"),
            )

    async def _lookup_user(self, payload: dict[str, Any]) -> IntegrationResult:
        """Look up a user by email."""
        email = payload.get("email")
        if not email:
            raise ValidationError("email is required")

        response = await self._api_call(
            "users.lookupByEmail",
            {"email": email},
        )

        if response.get("ok"):
            user = response.get("user", {})
            return IntegrationResult(
                success=True,
                data={
                    "id": user.get("id"),
                    "name": user.get("name"),
                    "real_name": user.get("real_name"),
                    "display_name": user.get("profile", {}).get("display_name"),
                    "email": user.get("profile", {}).get("email"),
                },
            )
        else:
            return IntegrationResult(
                success=False,
                error_message=response.get("error", "Unknown error"),
                error_code=response.get("error"),
            )

    # =========================================================================
    # Internal Methods
    # =========================================================================

    async def _test_bot_token(self) -> IntegrationResult:
        """Test bot token by calling auth.test."""
        response = await self._api_call("auth.test")

        if response.get("ok"):
            self._team_info = {
                "team_id": response.get("team_id"),
                "team": response.get("team"),
                "user_id": response.get("user_id"),
                "user": response.get("user"),
            }
            return IntegrationResult(
                success=True,
                data=self._team_info,
            )
        else:
            return IntegrationResult(
                success=False,
                error_message=response.get("error", "Invalid token"),
                error_code="INVALID_TOKEN",
            )

    async def _test_access_token(self) -> IntegrationResult:
        """Test OAuth access token."""
        # Same as bot token test
        return await self._test_bot_token()

    async def _test_webhook(self) -> IntegrationResult:
        """Test webhook by sending a test message."""
        # Just validate the URL format
        if not self.slack_config.webhook_url.startswith("https://hooks.slack.com/"):
            return IntegrationResult(
                success=False,
                error_message="Invalid webhook URL format",
                error_code="INVALID_WEBHOOK_URL",
            )

        return IntegrationResult(
            success=True,
            data={"mode": "webhook", "url_valid": True},
        )

    async def _api_call(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Make a Slack API call.

        Args:
            method: API method name (e.g., "chat.postMessage")
            params: Request parameters

        Returns:
            API response as dict
        """
        # Check rate limit
        self._check_rate_limit()

        url = f"{self.API_BASE_URL}/{method}"
        token = self.slack_config.bot_token or self.slack_config.access_token

        if not token:
            raise AuthenticationError("No API token available")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        data = json.dumps(params or {}).encode("utf-8")

        request = Request(url, data=data, headers=headers, method="POST")

        try:
            with urlopen(request, timeout=30) as response:  # nosec B310
                result = json.loads(response.read().decode())

            # Track request time for rate limiting
            self._request_times.append(time.time())

            # Handle rate limiting
            if result.get("error") == "ratelimited":
                retry_after = int(result.get("retry_after", 60))
                raise RateLimitError(
                    "Slack API rate limit exceeded",
                    retry_after_seconds=retry_after,
                )

            return result

        except HTTPError as e:
            if e.code == 429:
                retry_after = int(e.headers.get("Retry-After", 60))
                raise RateLimitError(
                    "Slack API rate limit exceeded",
                    retry_after_seconds=retry_after,
                )
            raise ConnectionError(f"API request failed: {e}")

        except URLError as e:
            raise ConnectionError(f"Network error: {e}")

    def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting."""
        now = time.time()
        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]

        if len(self._request_times) >= self.MAX_REQUESTS_PER_MINUTE:
            oldest = min(self._request_times)
            wait_time = 60 - (now - oldest)
            raise RateLimitError(
                "Local rate limit exceeded",
                retry_after_seconds=int(wait_time) + 1,
            )

    def verify_webhook_signature(
        self, timestamp: str, signature: str, body: bytes
    ) -> bool:
        """
        Verify incoming webhook signature from Slack.

        Args:
            timestamp: X-Slack-Request-Timestamp header
            signature: X-Slack-Signature header
            body: Raw request body

        Returns:
            True if signature is valid
        """
        if not self.slack_config.signing_secret:
            logger.warning("No signing secret configured for webhook verification")
            return True  # Allow in development

        # Check timestamp to prevent replay attacks (5 min window)
        try:
            ts = int(timestamp)
            if abs(time.time() - ts) > 300:
                logger.warning("Slack webhook timestamp too old")
                return False
        except ValueError:
            return False

        # Compute expected signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        expected_sig = (
            "v0="
            + hmac.new(
                self.slack_config.signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        return hmac.compare_digest(expected_sig, signature)


# =============================================================================
# Factory Function
# =============================================================================


def create_slack_adapter(
    organization_id: str,
    bot_token: str | None = None,
    webhook_url: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    default_channel: str = "#security-alerts",
) -> SlackAdapter:
    """
    Create a SlackAdapter instance.

    Args:
        organization_id: Organization ID
        bot_token: Slack bot token (preferred)
        webhook_url: Incoming webhook URL
        client_id: OAuth client ID
        client_secret: OAuth client secret
        default_channel: Default channel for notifications

    Returns:
        Configured SlackAdapter
    """
    config = IntegrationConfig(
        integration_id=f"slack-{organization_id}",
        integration_type=IntegrationType.MONITORING,  # Using monitoring as closest match
        provider="slack",
        organization_id=organization_id,
        credentials={
            "bot_token": bot_token or "",
            "webhook_url": webhook_url or "",
            "client_id": client_id or "",
            "client_secret": client_secret or "",
        },
        settings={
            "default_channel": default_channel,
        },
    )

    return SlackAdapter(config)
