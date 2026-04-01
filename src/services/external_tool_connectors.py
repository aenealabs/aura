"""
Project Aura - External Tool Connectors

Implements ADR-023 Phase 3: External Tool Integration

Real API connectors for external tools:
- Slack: Webhook and Web API for notifications
- Jira: REST API for ticket management
- PagerDuty: Events API v2 for incident management

These connectors can be used:
1. Directly by Aura agents for immediate integration
2. Via AgentCore Gateway MCP protocol for enterprise customers

SECURITY: Only available in ENTERPRISE or HYBRID mode.
DEFENSE mode deployments cannot use external tools.

Usage:
    >>> from src.services.external_tool_connectors import SlackConnector
    >>> slack = SlackConnector(webhook_url="https://hooks.slack.com/...")
    >>> await slack.send_message("#security-alerts", "Critical vulnerability found!")
"""

import hashlib
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import aiohttp

from src.config import require_enterprise_mode

logger = logging.getLogger(__name__)


# =============================================================================
# Base Classes
# =============================================================================


class ConnectorStatus(Enum):
    """Status of a connector."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    AUTH_FAILED = "auth_failed"


@dataclass
class ConnectorResult:
    """Result from a connector operation."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    status_code: int | None = None
    latency_ms: float = 0.0
    request_id: str | None = None


class ExternalToolConnector(ABC):
    """Base class for external tool connectors."""

    def __init__(self, name: str, timeout_seconds: float = 30.0) -> None:
        self.name = name
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._status = ConnectorStatus.DISCONNECTED
        self._last_error: str | None = None
        self._request_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0

    @property
    def status(self) -> ConnectorStatus:
        return self._status

    @property
    def metrics(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self._status.value,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "avg_latency_ms": (
                self._total_latency_ms / self._request_count
                if self._request_count > 0
                else 0
            ),
            "last_error": self._last_error,
        }

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the connector is healthy."""

    def _record_request(self, latency_ms: float, success: bool) -> None:
        """Record request metrics."""
        self._request_count += 1
        self._total_latency_ms += latency_ms
        if not success:
            self._error_count += 1


# =============================================================================
# Slack Connector
# =============================================================================


@dataclass
class SlackMessage:
    """Slack message structure."""

    channel: str
    text: str
    username: str | None = None
    icon_emoji: str | None = None
    attachments: list[dict[str, Any]] | None = None
    blocks: list[dict[str, Any]] | None = None
    thread_ts: str | None = None  # For threaded replies


@dataclass
class SlackAttachment:
    """Slack message attachment."""

    color: str  # hex color or "good", "warning", "danger"
    title: str | None = None
    text: str | None = None
    fields: list[dict[str, str]] | None = None
    footer: str | None = None
    ts: int | None = None  # Unix timestamp


class SlackConnector(ExternalToolConnector):
    """
    Slack connector for sending notifications and alerts.

    Supports both:
    - Incoming Webhooks (simple, no OAuth required)
    - Web API (full features, requires OAuth token)

    For Aura, webhooks are preferred for:
    - Security alerts
    - HITL approval notifications
    - Deployment status updates
    """

    def __init__(
        self,
        webhook_url: str | None = None,
        bot_token: str | None = None,
        default_channel: str = "#aura-alerts",
        timeout_seconds: float = 30.0,
    ):
        """
        Initialize Slack connector.

        Args:
            webhook_url: Incoming webhook URL (simpler, channel-specific)
            bot_token: OAuth bot token (more features, any channel)
            default_channel: Default channel for messages
            timeout_seconds: Request timeout
        """
        super().__init__("slack", timeout_seconds)

        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.default_channel = default_channel

        if not webhook_url and not bot_token:
            logger.warning(
                "SlackConnector initialized without webhook_url or bot_token. "
                "Configure via environment or pass explicitly."
            )

        self._status = ConnectorStatus.DISCONNECTED

    @require_enterprise_mode
    async def send_message(
        self,
        channel: str | None = None,
        text: str = "",
        attachments: list[SlackAttachment] | None = None,
        blocks: list[dict[str, Any]] | None = None,
        thread_ts: str | None = None,
        username: str = "Aura Security Bot",
        icon_emoji: str = ":shield:",
    ) -> ConnectorResult:
        """
        Send a message to Slack.

        Args:
            channel: Channel to post to (uses default if not specified)
            text: Message text (required for webhook, fallback for blocks)
            attachments: Rich attachments
            blocks: Block Kit blocks for rich layouts
            thread_ts: Thread timestamp for replies
            username: Bot username override
            icon_emoji: Bot icon emoji

        Returns:
            ConnectorResult with success status
        """
        start_time = time.time()
        channel = channel or self.default_channel

        try:
            if self.webhook_url:
                result = await self._send_via_webhook(
                    text=text,
                    attachments=attachments,
                    blocks=blocks,
                    username=username,
                    icon_emoji=icon_emoji,
                )
            elif self.bot_token:
                result = await self._send_via_api(
                    channel=channel,
                    text=text,
                    attachments=attachments,
                    blocks=blocks,
                    thread_ts=thread_ts,
                )
            else:
                result = ConnectorResult(
                    success=False,
                    error="No webhook_url or bot_token configured",
                )

            latency_ms = (time.time() - start_time) * 1000
            result.latency_ms = latency_ms
            self._record_request(latency_ms, result.success)

            if result.success:
                self._status = ConnectorStatus.CONNECTED
                logger.info(f"Slack message sent to {channel}: {text[:50]}...")
            else:
                self._last_error = result.error
                logger.error(f"Slack message failed: {result.error}")

            return result

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.exception(f"Slack connector error: {e}")
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def _send_via_webhook(
        self,
        text: str,
        attachments: list[SlackAttachment] | None = None,
        blocks: list[dict[str, Any]] | None = None,
        username: str | None = None,
        icon_emoji: str | None = None,
    ) -> ConnectorResult:
        """Send message via incoming webhook."""
        if not self.webhook_url:
            return ConnectorResult(
                success=False,
                error="Webhook URL not configured",
            )

        payload: dict[str, Any] = {"text": text}

        if username:
            payload["username"] = username
        if icon_emoji:
            payload["icon_emoji"] = icon_emoji
        if blocks:
            payload["blocks"] = blocks
        if attachments:
            payload["attachments"] = [
                {
                    "color": a.color,
                    "title": a.title,
                    "text": a.text,
                    "fields": a.fields,
                    "footer": a.footer,
                    "ts": a.ts,
                }
                for a in attachments
            ]

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:
                response_text = await response.text()

                if response.status == 200 and response_text == "ok":
                    return ConnectorResult(
                        success=True,
                        status_code=response.status,
                        data={"response": "ok"},
                    )
                else:
                    return ConnectorResult(
                        success=False,
                        status_code=response.status,
                        error=response_text,
                    )

    async def _send_via_api(
        self,
        channel: str,
        text: str,
        attachments: list[SlackAttachment] | None = None,
        blocks: list[dict[str, Any]] | None = None,
        thread_ts: str | None = None,
    ) -> ConnectorResult:
        """Send message via Slack Web API."""
        payload: dict[str, Any] = {
            "channel": channel,
            "text": text,
        }

        if blocks:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts
        if attachments:
            payload["attachments"] = [
                {
                    "color": a.color,
                    "title": a.title,
                    "text": a.text,
                    "fields": a.fields,
                    "footer": a.footer,
                    "ts": a.ts,
                }
                for a in attachments
            ]

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                "https://slack.com/api/chat.postMessage",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json",
                },
            ) as response:
                data = await response.json()

                if data.get("ok"):
                    return ConnectorResult(
                        success=True,
                        status_code=response.status,
                        data=data,
                        request_id=data.get("ts"),
                    )
                else:
                    return ConnectorResult(
                        success=False,
                        status_code=response.status,
                        error=data.get("error", "Unknown error"),
                        data=data,
                    )

    @require_enterprise_mode
    async def send_security_alert(
        self,
        severity: str,
        title: str,
        description: str,
        cve_id: str | None = None,
        affected_file: str | None = None,
        recommendation: str | None = None,
        approval_url: str | None = None,
        channel: str | None = None,
    ) -> ConnectorResult:
        """
        Send a formatted security alert to Slack.

        Args:
            severity: CRITICAL, HIGH, MEDIUM, LOW
            title: Alert title
            description: Alert description
            cve_id: CVE identifier if applicable
            affected_file: File path affected
            recommendation: Recommended action
            approval_url: URL to approval dashboard
            channel: Override default channel
        """
        color_map = {
            "CRITICAL": "#DC2626",  # Red
            "HIGH": "#EA580C",  # Orange
            "MEDIUM": "#F59E0B",  # Amber
            "LOW": "#3B82F6",  # Blue
        }
        _color = color_map.get(severity.upper(), "#6B7280")  # noqa: F841

        emoji_map = {
            "CRITICAL": ":rotating_light:",
            "HIGH": ":warning:",
            "MEDIUM": ":large_orange_diamond:",
            "LOW": ":information_source:",
        }
        emoji = emoji_map.get(severity.upper(), ":shield:")

        # Build blocks for rich formatting
        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Security Alert: {title}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity}"},
                    {"type": "mrkdwn", "text": f"*CVE:*\n{cve_id or 'N/A'}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Description:*\n{description}"},
            },
        ]

        if affected_file:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Affected File:*\n`{affected_file}`",
                    },
                }
            )

        if recommendation:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Recommendation:*\n{recommendation}",
                    },
                }
            )

        if approval_url:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Review in Dashboard",
                            },
                            "url": approval_url,
                            "style": "primary",
                        }
                    ],
                }
            )

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Sent by Aura Security Platform • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                    }
                ],
            }
        )

        return await self.send_message(
            channel=channel,
            text=f"Security Alert: {title} ({severity})",
            blocks=blocks,
        )

    async def health_check(self) -> bool:
        """Check if Slack connector is healthy."""
        # For webhooks, we can't really check without posting
        # For API, we can call auth.test
        if self.bot_token:
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(
                        "https://slack.com/api/auth.test",
                        headers={"Authorization": f"Bearer {self.bot_token}"},
                    ) as response:
                        data = await response.json()
                        if data.get("ok"):
                            self._status = ConnectorStatus.CONNECTED
                            return True
                        else:
                            self._status = ConnectorStatus.AUTH_FAILED
                            return False
            except Exception as e:
                self._status = ConnectorStatus.ERROR
                self._last_error = str(e)
                return False
        elif self.webhook_url:
            # Assume healthy if webhook is configured
            self._status = ConnectorStatus.CONNECTED
            return True
        return False


# =============================================================================
# Jira Connector
# =============================================================================


@dataclass
class JiraIssue:
    """Jira issue structure."""

    project_key: str
    summary: str
    description: str
    issue_type: str = "Bug"  # Bug, Task, Story, Epic
    priority: str | None = None  # Highest, High, Medium, Low, Lowest
    labels: list[str] | None = None
    assignee: str | None = None
    components: list[str] | None = None
    custom_fields: dict[str, Any] | None = None


class JiraConnector(ExternalToolConnector):
    """
    Jira connector for issue tracking and project management.

    Supports:
    - Creating security vulnerability tickets
    - Updating issue status
    - Adding comments
    - Linking related issues
    """

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        default_project: str = "SEC",
        timeout_seconds: float = 30.0,
    ):
        """
        Initialize Jira connector.

        Args:
            base_url: Jira instance URL (e.g., https://company.atlassian.net)
            email: User email for authentication
            api_token: API token (not password)
            default_project: Default project key for issues
            timeout_seconds: Request timeout
        """
        super().__init__("jira", timeout_seconds)

        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.default_project = default_project

        # Build auth header (Basic auth with email:token)
        import base64

        credentials = f"{email}:{api_token}"
        self._auth_header = base64.b64encode(credentials.encode()).decode()

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Basic {self._auth_header}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @require_enterprise_mode
    async def create_issue(self, issue: JiraIssue) -> ConnectorResult:
        """
        Create a new Jira issue.

        Args:
            issue: JiraIssue with issue details

        Returns:
            ConnectorResult with created issue data
        """
        start_time = time.time()

        payload: dict[str, Any] = {
            "fields": {
                "project": {"key": issue.project_key},
                "summary": issue.summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": issue.description}],
                        }
                    ],
                },
                "issuetype": {"name": issue.issue_type},
            }
        }

        if issue.priority:
            payload["fields"]["priority"] = {"name": issue.priority}
        if issue.labels:
            payload["fields"]["labels"] = issue.labels
        if issue.assignee:
            payload["fields"]["assignee"] = {"accountId": issue.assignee}
        if issue.components:
            payload["fields"]["components"] = [{"name": c} for c in issue.components]
        if issue.custom_fields:
            for field_id, value in issue.custom_fields.items():
                payload["fields"][field_id] = value

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/rest/api/3/issue",
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    if response.status in (200, 201):
                        self._status = ConnectorStatus.CONNECTED
                        self._record_request(latency_ms, True)
                        logger.info(f"Jira issue created: {data.get('key')}")
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data=data,
                            request_id=data.get("key"),
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        error_msg = data.get("errorMessages", [str(data)])
                        self._last_error = str(error_msg)
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=str(error_msg),
                            data=data,
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.exception(f"Jira connector error: {e}")
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def create_security_issue(
        self,
        summary: str,
        cve_id: str | None = None,
        severity: str = "HIGH",
        affected_file: str | None = None,
        description: str = "",
        project_key: str | None = None,
    ) -> ConnectorResult:
        """
        Create a security vulnerability issue with standard formatting.

        Args:
            summary: Issue summary/title
            cve_id: CVE identifier
            severity: CRITICAL, HIGH, MEDIUM, LOW
            affected_file: Affected file path
            description: Detailed description
            project_key: Override default project
        """
        priority_map = {
            "CRITICAL": "Highest",
            "HIGH": "High",
            "MEDIUM": "Medium",
            "LOW": "Low",
        }

        approval_dashboard_url = os.environ.get(
            "APPROVAL_DASHBOARD_URL", "https://app.aura.local/approvals"
        )
        full_description = f"""
h2. Security Vulnerability

*CVE:* {cve_id or 'N/A'}
*Severity:* {severity}
*Affected File:* {affected_file or 'N/A'}

h3. Description
{description}

h3. Generated By
Aura Security Platform (Automated Detection)

h3. Next Steps
1. Review the vulnerability details
2. Approve or reject the auto-generated patch in [Aura Dashboard|{approval_dashboard_url}]
3. Update this ticket with resolution status
"""

        issue = JiraIssue(
            project_key=project_key or self.default_project,
            summary=f"[{severity}] {summary}",
            description=full_description.strip(),
            issue_type="Bug",
            priority=priority_map.get(severity, "Medium"),
            labels=["security", "aura-generated", severity.lower()],
        )

        return await self.create_issue(issue)

    @require_enterprise_mode
    async def add_comment(self, issue_key: str, comment: str) -> ConnectorResult:
        """
        Add a comment to an existing issue.

        Args:
            issue_key: Issue key (e.g., SEC-123)
            comment: Comment text
        """
        start_time = time.time()

        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment}],
                    }
                ],
            }
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    f"{self.base_url}/rest/api/3/issue/{issue_key}/comment",
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status in (200, 201)
                    self._record_request(latency_ms, success)

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data=data,
                        latency_ms=latency_ms,
                        error=None if success else str(data),
                    )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def transition_issue(
        self, issue_key: str, transition_name: str
    ) -> ConnectorResult:
        """
        Transition an issue to a new status.

        Args:
            issue_key: Issue key (e.g., SEC-123)
            transition_name: Target transition name (e.g., "Done", "In Progress")
        """
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # First, get available transitions
                async with session.get(
                    f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions",
                    headers=self._get_headers(),
                ) as response:
                    transitions_data = await response.json()
                    transitions = transitions_data.get("transitions", [])

                # Find the target transition
                target_transition = None
                for t in transitions:
                    if t["name"].lower() == transition_name.lower():
                        target_transition = t
                        break

                if not target_transition:
                    return ConnectorResult(
                        success=False,
                        error=f"Transition '{transition_name}' not found. Available: {[t['name'] for t in transitions]}",
                        latency_ms=(time.time() - start_time) * 1000,
                    )

                # Execute transition
                async with session.post(
                    f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions",
                    json={"transition": {"id": target_transition["id"]}},
                    headers=self._get_headers(),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    success = response.status == 204
                    self._record_request(latency_ms, success)

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        latency_ms=latency_ms,
                        data={"transition": transition_name},
                    )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def health_check(self) -> bool:
        """Check if Jira connector is healthy."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    f"{self.base_url}/rest/api/3/myself",
                    headers=self._get_headers(),
                ) as response:
                    if response.status == 200:
                        self._status = ConnectorStatus.CONNECTED
                        return True
                    elif response.status == 401:
                        self._status = ConnectorStatus.AUTH_FAILED
                    else:
                        self._status = ConnectorStatus.ERROR
                    return False
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            return False


# =============================================================================
# PagerDuty Connector
# =============================================================================


class PagerDutySeverity(Enum):
    """PagerDuty event severity levels."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class PagerDutyEvent:
    """PagerDuty event structure."""

    routing_key: str
    summary: str
    severity: PagerDutySeverity
    source: str = "aura-security-platform"
    dedup_key: str | None = None
    timestamp: str | None = None
    component: str | None = None
    group: str | None = None
    event_class: str | None = None
    custom_details: dict[str, Any] | None = None
    links: list[dict[str, str]] | None = None
    images: list[dict[str, str]] | None = None


class PagerDutyConnector(ExternalToolConnector):
    """
    PagerDuty connector for incident management.

    Supports Events API v2 for:
    - Triggering incidents
    - Acknowledging incidents
    - Resolving incidents
    """

    EVENTS_API_URL = "https://events.pagerduty.com/v2/enqueue"

    def __init__(
        self,
        routing_key: str,
        default_severity: PagerDutySeverity = PagerDutySeverity.ERROR,
        timeout_seconds: float = 30.0,
    ):
        """
        Initialize PagerDuty connector.

        Args:
            routing_key: Integration key (Events API v2)
            default_severity: Default severity for events
            timeout_seconds: Request timeout
        """
        super().__init__("pagerduty", timeout_seconds)

        self.routing_key = routing_key
        self.default_severity = default_severity

    @require_enterprise_mode
    async def trigger_incident(
        self,
        summary: str,
        severity: PagerDutySeverity | None = None,
        dedup_key: str | None = None,
        source: str = "aura-security-platform",
        component: str | None = None,
        group: str | None = None,
        custom_details: dict[str, Any] | None = None,
        links: list[dict[str, str]] | None = None,
    ) -> ConnectorResult:
        """
        Trigger a new PagerDuty incident.

        Args:
            summary: Incident summary
            severity: Event severity
            dedup_key: Deduplication key (auto-generated if not provided)
            source: Source of the event
            component: Affected component
            group: Logical grouping
            custom_details: Additional details
            links: Related links

        Returns:
            ConnectorResult with incident data
        """
        start_time = time.time()
        severity = severity or self.default_severity

        # Generate dedup key if not provided
        if not dedup_key:
            dedup_key = hashlib.sha256(
                f"{summary}:{source}:{time.time()}".encode()
            ).hexdigest()[:32]

        payload: dict[str, Any] = {
            "routing_key": self.routing_key,
            "event_action": "trigger",
            "dedup_key": dedup_key,
            "payload": {
                "summary": summary,
                "severity": severity.value,
                "source": source,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        if component:
            payload["payload"]["component"] = component
        if group:
            payload["payload"]["group"] = group
        if custom_details:
            payload["payload"]["custom_details"] = custom_details
        if links:
            payload["links"] = links

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    self.EVENTS_API_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    if response.status == 202:
                        self._status = ConnectorStatus.CONNECTED
                        self._record_request(latency_ms, True)
                        logger.info(f"PagerDuty incident triggered: {dedup_key}")
                        return ConnectorResult(
                            success=True,
                            status_code=response.status,
                            data=data,
                            request_id=dedup_key,
                            latency_ms=latency_ms,
                        )
                    else:
                        self._record_request(latency_ms, False)
                        error = data.get("message", str(data))
                        self._last_error = error
                        return ConnectorResult(
                            success=False,
                            status_code=response.status,
                            error=error,
                            data=data,
                            latency_ms=latency_ms,
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            logger.exception(f"PagerDuty connector error: {e}")
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    @require_enterprise_mode
    async def trigger_security_incident(
        self,
        title: str,
        cve_id: str | None = None,
        severity: str = "HIGH",
        affected_file: str | None = None,
        description: str = "",
        approval_url: str | None = None,
    ) -> ConnectorResult:
        """
        Trigger a security-specific incident with standard formatting.

        Args:
            title: Incident title
            cve_id: CVE identifier
            severity: CRITICAL, HIGH, MEDIUM, LOW
            affected_file: Affected file path
            description: Detailed description
            approval_url: URL to approval dashboard
        """
        severity_map = {
            "CRITICAL": PagerDutySeverity.CRITICAL,
            "HIGH": PagerDutySeverity.ERROR,
            "MEDIUM": PagerDutySeverity.WARNING,
            "LOW": PagerDutySeverity.INFO,
        }

        pd_severity = severity_map.get(severity.upper(), PagerDutySeverity.ERROR)

        custom_details = {
            "cve_id": cve_id or "N/A",
            "severity": severity,
            "affected_file": affected_file or "N/A",
            "description": description,
            "detected_by": "Aura Security Platform",
        }

        links = []
        if approval_url:
            links.append({"href": approval_url, "text": "Review in Aura Dashboard"})

        # Use CVE as dedup key if available for better deduplication
        dedup_key = cve_id if cve_id else None

        return await self.trigger_incident(
            summary=f"[{severity}] {title}",
            severity=pd_severity,
            dedup_key=dedup_key,
            component="security",
            group="vulnerabilities",
            custom_details=custom_details,
            links=links,
        )

    @require_enterprise_mode
    async def acknowledge_incident(self, dedup_key: str) -> ConnectorResult:
        """
        Acknowledge an existing incident.

        Args:
            dedup_key: Deduplication key of the incident
        """
        return await self._send_event_action(dedup_key, "acknowledge")

    @require_enterprise_mode
    async def resolve_incident(self, dedup_key: str) -> ConnectorResult:
        """
        Resolve an existing incident.

        Args:
            dedup_key: Deduplication key of the incident
        """
        return await self._send_event_action(dedup_key, "resolve")

    async def _send_event_action(self, dedup_key: str, action: str) -> ConnectorResult:
        """Send an event action (acknowledge/resolve)."""
        start_time = time.time()

        payload = {
            "routing_key": self.routing_key,
            "event_action": action,
            "dedup_key": dedup_key,
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    self.EVENTS_API_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    data = await response.json()

                    success = response.status == 202
                    self._record_request(latency_ms, success)

                    return ConnectorResult(
                        success=success,
                        status_code=response.status,
                        data=data,
                        request_id=dedup_key,
                        latency_ms=latency_ms,
                        error=None if success else data.get("message"),
                    )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            return ConnectorResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def health_check(self) -> bool:
        """Check if PagerDuty connector is healthy."""
        # PagerDuty Events API doesn't have a health endpoint
        # We consider it healthy if routing key is configured
        if self.routing_key:
            self._status = ConnectorStatus.CONNECTED
            return True
        self._status = ConnectorStatus.DISCONNECTED
        return False


# =============================================================================
# Connector Factory
# =============================================================================


class ExternalToolConnectorFactory:
    """Factory for creating external tool connectors from configuration."""

    @staticmethod
    def create_slack(
        webhook_url: str | None = None,
        bot_token: str | None = None,
        **kwargs,
    ) -> SlackConnector:
        """Create a Slack connector."""
        return SlackConnector(
            webhook_url=webhook_url,
            bot_token=bot_token,
            **kwargs,
        )

    @staticmethod
    def create_jira(
        base_url: str,
        email: str,
        api_token: str,
        **kwargs,
    ) -> JiraConnector:
        """Create a Jira connector."""
        return JiraConnector(
            base_url=base_url,
            email=email,
            api_token=api_token,
            **kwargs,
        )

    @staticmethod
    def create_pagerduty(
        routing_key: str,
        **kwargs,
    ) -> PagerDutyConnector:
        """Create a PagerDuty connector."""
        return PagerDutyConnector(
            routing_key=routing_key,
            **kwargs,
        )

    @staticmethod
    def from_config(tool_id: str, config: dict[str, Any]) -> ExternalToolConnector:
        """
        Create a connector from configuration dictionary.

        Args:
            tool_id: Tool identifier (slack, jira, pagerduty)
            config: Configuration dictionary

        Returns:
            Configured connector instance
        """
        creators = {
            "slack": ExternalToolConnectorFactory.create_slack,
            "jira": ExternalToolConnectorFactory.create_jira,
            "pagerduty": ExternalToolConnectorFactory.create_pagerduty,
        }

        creator = creators.get(tool_id.lower())
        if creator is None:
            raise ValueError(
                f"Unknown tool: {tool_id}. Available: {list(creators.keys())}"
            )

        return creator(**config)  # type: ignore[no-any-return, operator]
