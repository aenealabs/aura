"""
Project Aura - Notification Service

Provides SNS/SES notification capabilities for the HITL approval workflow.
Sends alerts to security teams when patches require review.

Implements notification requirements from docs/design/HITL_SANDBOX_ARCHITECTURE.md
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Boto3 imports (available in AWS environment)
try:
    import boto3
    from botocore.exceptions import ClientError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("Boto3 not available - using mock mode")


class NotificationMode(Enum):
    """Operating modes for notification service."""

    MOCK = "mock"  # Log-only mode for testing
    AWS = "aws"  # Real SNS/SES


class NotificationChannel(Enum):
    """Notification delivery channels."""

    EMAIL = "email"  # SES email
    SNS = "sns"  # SNS topic
    SLACK = "slack"  # Slack incoming webhook
    TEAMS = "teams"  # Microsoft Teams incoming webhook
    WEBHOOK = "webhook"  # Generic webhook
    PAGERDUTY = "pagerduty"  # PagerDuty events API


class NotificationPriority(Enum):
    """Notification priority levels."""

    CRITICAL = "critical"  # Immediate attention required
    HIGH = "high"  # Urgent review needed
    NORMAL = "normal"  # Standard notification
    LOW = "low"  # Informational


class NotificationError(Exception):
    """Notification delivery error."""


@dataclass
class NotificationResult:
    """Result of a notification delivery attempt."""

    success: bool
    message_id: str | None = None
    channel: NotificationChannel | None = None
    error: str | None = None


class NotificationService:
    """
    Service for sending notifications via SNS and SES.

    Features:
    - Send approval request notifications via email (SES)
    - Publish to SNS topics for broader distribution
    - Template-based message formatting
    - Delivery tracking and logging

    Usage:
        >>> service = NotificationService(mode=NotificationMode.AWS)
        >>> service.send_approval_notification(
        ...     approval_request=request,
        ...     recipients=["security-team@company.com"]
        ... )
    """

    # Email templates
    EMAIL_SUBJECT_TEMPLATE = (
        "[AURA] {priority} - Security Patch Awaiting Review: {patch_id}"
    )

    EMAIL_BODY_TEMPLATE = """
Project Aura - Security Patch Approval Request

Approval ID: {approval_id}
Patch ID: {patch_id}
Vulnerability: {vulnerability_id}
Severity: {severity}
Created: {created_at}
Expires: {expires_at}

--- SANDBOX TEST RESULTS ---
Tests Passed: {tests_passed}
Tests Failed: {tests_failed}
Test Coverage: {test_coverage}%

--- PATCH DIFF ---
{patch_diff}

--- ACTION REQUIRED ---
Please review this security patch and approve or reject within {timeout_hours} hours.

Review URL: {review_url}

---
This is an automated notification from Project Aura.
Do not reply to this email.
"""

    def __init__(
        self,
        mode: NotificationMode = NotificationMode.MOCK,
        region: str | None = None,
        sns_topic_arn: str | None = None,
        ses_sender_email: str | None = None,
        dashboard_url: str | None = None,
    ):
        """
        Initialize Notification Service.

        Args:
            mode: Operating mode (MOCK or AWS)
            region: AWS region
            sns_topic_arn: SNS topic ARN for publishing notifications
            ses_sender_email: Verified SES sender email address
            dashboard_url: URL of the approval dashboard
        """
        self.mode = mode
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")

        # SNS configuration
        env = os.environ.get("ENVIRONMENT", "dev")
        project = os.environ.get("PROJECT_NAME", "aura")
        account_id = os.environ.get("AWS_ACCOUNT_ID", "")

        self.sns_topic_arn = sns_topic_arn or os.environ.get(
            "HITL_SNS_TOPIC_ARN",
            f"arn:aws:sns:{self.region}:{account_id}:{project}-hitl-notifications-{env}",
        )

        # SES configuration
        self.ses_sender_email = ses_sender_email or os.environ.get(
            "SES_SENDER_EMAIL",
            f"aura-noreply@{project}.local",
        )

        # Dashboard URL for review links
        self.dashboard_url = dashboard_url or os.environ.get(
            "HITL_DASHBOARD_URL",
            f"https://{project}-dashboard-{env}.{project}.local/approvals",
        )

        # Slack webhook configuration
        self.slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
        self.slack_channel = os.environ.get("SLACK_CHANNEL", "#aura-notifications")
        self.slack_bot_name = os.environ.get("SLACK_BOT_NAME", "Aura Bot")

        # Microsoft Teams webhook configuration
        self.teams_webhook_url = os.environ.get("TEAMS_WEBHOOK_URL", "")

        # Initialize AWS clients
        if self.mode == NotificationMode.AWS and BOTO3_AVAILABLE:
            self._init_aws_clients()
        else:
            if self.mode == NotificationMode.AWS:
                logger.warning(
                    "AWS mode requested but boto3 not available. Using MOCK mode."
                )
                self.mode = NotificationMode.MOCK
            self._init_mock_mode()

        # Delivery log (for testing/debugging)
        self.delivery_log: list[dict[str, Any]] = []

        logger.info(
            f"NotificationService initialized in {self.mode.value} mode "
            f"(SNS: {self.sns_topic_arn})"
        )

    def _init_aws_clients(self) -> None:
        """Initialize AWS SNS and SES clients."""
        try:
            self.sns_client = boto3.client("sns", region_name=self.region)
            self.ses_client = boto3.client("ses", region_name=self.region)
            logger.info("AWS SNS/SES clients initialized")
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            self.mode = NotificationMode.MOCK
            self._init_mock_mode()

    def _init_mock_mode(self) -> None:
        """Initialize mock mode."""
        self.sns_client = None
        self.ses_client = None
        logger.info("Mock mode initialized (notifications will be logged only)")

    def send_approval_notification(
        self,
        approval_id: str,
        patch_id: str,
        vulnerability_id: str,
        severity: str,
        created_at: str,
        expires_at: str,
        sandbox_results: dict[str, Any],
        patch_diff: str,
        recipients: list[str],
        timeout_hours: int = 24,
    ) -> list[NotificationResult]:
        """
        Send approval request notification to specified recipients.

        Args:
            approval_id: Approval request ID
            patch_id: Patch identifier
            vulnerability_id: Vulnerability identifier
            severity: Patch severity level
            created_at: Creation timestamp
            expires_at: Expiration timestamp
            sandbox_results: Test results from sandbox
            patch_diff: The code changes
            recipients: List of email addresses
            timeout_hours: Hours until expiration

        Returns:
            List of NotificationResult for each recipient
        """
        results = []

        # Determine priority based on severity
        priority_map = {
            "CRITICAL": NotificationPriority.CRITICAL,
            "HIGH": NotificationPriority.HIGH,
            "MEDIUM": NotificationPriority.NORMAL,
            "LOW": NotificationPriority.LOW,
        }
        priority = priority_map.get(severity, NotificationPriority.NORMAL)

        # Build review URL
        review_url = f"{self.dashboard_url}/{approval_id}"

        # Format message content
        subject = self.EMAIL_SUBJECT_TEMPLATE.format(
            priority=priority.value.upper(),
            patch_id=patch_id,
        )

        body = self.EMAIL_BODY_TEMPLATE.format(
            approval_id=approval_id,
            patch_id=patch_id,
            vulnerability_id=vulnerability_id,
            severity=severity,
            created_at=created_at,
            expires_at=expires_at,
            tests_passed=sandbox_results.get("tests_passed", "N/A"),
            tests_failed=sandbox_results.get("tests_failed", "N/A"),
            test_coverage=sandbox_results.get("coverage", "N/A"),
            patch_diff=patch_diff[:2000] if patch_diff else "N/A",  # Truncate if long
            timeout_hours=timeout_hours,
            review_url=review_url,
        )

        # Send to each recipient
        for recipient in recipients:
            result = self._send_email(
                recipient=recipient,
                subject=subject,
                body=body,
                priority=priority,
            )
            results.append(result)

        # Also publish to SNS topic
        sns_result = self._publish_to_sns(
            subject=subject,
            message=body,
            attributes={
                "approval_id": approval_id,
                "severity": severity,
                "priority": priority.value,
            },
        )
        results.append(sns_result)

        return results

    def _send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> NotificationResult:
        """
        Send email via SES.

        Args:
            recipient: Email address
            subject: Email subject
            body: Email body
            priority: Notification priority

        Returns:
            NotificationResult
        """
        log_entry = {
            "channel": NotificationChannel.EMAIL.value,
            "recipient": recipient,
            "subject": subject,
            "priority": priority.value,
        }

        if self.mode == NotificationMode.MOCK:
            logger.info(f"[MOCK] Email to {recipient}: {subject}")
            log_entry["status"] = "mock_sent"
            log_entry["message_id"] = f"mock-email-{len(self.delivery_log)}"
            self.delivery_log.append(log_entry)

            return NotificationResult(
                success=True,
                message_id=log_entry["message_id"],
                channel=NotificationChannel.EMAIL,
            )

        try:
            response = self.ses_client.send_email(
                Source=self.ses_sender_email,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                },
                Tags=[
                    {"Name": "Application", "Value": "ProjectAura"},
                    {"Name": "NotificationType", "Value": "HITL_Approval"},
                    {"Name": "Priority", "Value": priority.value},
                ],
            )

            message_id = response.get("MessageId", "")
            log_entry["status"] = "sent"
            log_entry["message_id"] = message_id
            self.delivery_log.append(log_entry)

            logger.info(f"Email sent to {recipient}: {message_id}")

            return NotificationResult(
                success=True,
                message_id=message_id,
                channel=NotificationChannel.EMAIL,
            )

        except ClientError as e:
            error_msg = str(e)
            log_entry["status"] = "failed"
            log_entry["error"] = error_msg
            self.delivery_log.append(log_entry)

            logger.error(f"Failed to send email to {recipient}: {error_msg}")

            return NotificationResult(
                success=False,
                channel=NotificationChannel.EMAIL,
                error=error_msg,
            )

    def _publish_to_sns(
        self,
        subject: str,
        message: str,
        attributes: dict[str, str] | None = None,
    ) -> NotificationResult:
        """
        Publish notification to SNS topic.

        Args:
            subject: Message subject
            message: Message body
            attributes: Message attributes for filtering

        Returns:
            NotificationResult
        """
        log_entry = {
            "channel": NotificationChannel.SNS.value,
            "topic": self.sns_topic_arn,
            "subject": subject,
        }

        if self.mode == NotificationMode.MOCK:
            logger.info(f"[MOCK] SNS publish to {self.sns_topic_arn}: {subject}")
            log_entry["status"] = "mock_published"
            log_entry["message_id"] = f"mock-sns-{len(self.delivery_log)}"
            self.delivery_log.append(log_entry)

            return NotificationResult(
                success=True,
                message_id=log_entry["message_id"],
                channel=NotificationChannel.SNS,
            )

        try:
            # Build message attributes
            msg_attributes = {}
            if attributes:
                for key, value in attributes.items():
                    msg_attributes[key] = {
                        "DataType": "String",
                        "StringValue": str(value),
                    }

            response = self.sns_client.publish(
                TopicArn=self.sns_topic_arn,
                Subject=subject[:100],  # SNS subject limit
                Message=message,
                MessageAttributes=msg_attributes,
            )

            message_id = response.get("MessageId", "")
            log_entry["status"] = "published"
            log_entry["message_id"] = message_id
            self.delivery_log.append(log_entry)

            logger.info(f"Published to SNS: {message_id}")

            return NotificationResult(
                success=True,
                message_id=message_id,
                channel=NotificationChannel.SNS,
            )

        except ClientError as e:
            error_msg = str(e)
            log_entry["status"] = "failed"
            log_entry["error"] = error_msg
            self.delivery_log.append(log_entry)

            logger.error(f"Failed to publish to SNS: {error_msg}")

            return NotificationResult(
                success=False,
                channel=NotificationChannel.SNS,
                error=error_msg,
            )

    def _send_slack_notification(
        self,
        subject: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        webhook_url: str | None = None,
        channel: str | None = None,
    ) -> NotificationResult:
        """
        Send notification to Slack via incoming webhook.

        Args:
            subject: Message subject/title
            message: Message body
            priority: Notification priority
            webhook_url: Slack webhook URL (uses default if not provided)
            channel: Slack channel override

        Returns:
            NotificationResult
        """
        url = webhook_url or self.slack_webhook_url
        target_channel = channel or self.slack_channel

        log_entry = {
            "channel": NotificationChannel.SLACK.value,
            "target": target_channel,
            "subject": subject,
            "priority": priority.value,
        }

        if self.mode == NotificationMode.MOCK or not url:
            logger.info(f"[MOCK] Slack to {target_channel}: {subject}")
            log_entry["status"] = "mock_sent"
            log_entry["message_id"] = f"mock-slack-{len(self.delivery_log)}"
            self.delivery_log.append(log_entry)

            return NotificationResult(
                success=True,
                message_id=log_entry["message_id"],
                channel=NotificationChannel.SLACK,
            )

        try:
            # Determine color based on priority
            color_map = {
                NotificationPriority.CRITICAL: "#DC2626",  # Red
                NotificationPriority.HIGH: "#EA580C",  # Orange
                NotificationPriority.NORMAL: "#3B82F6",  # Blue
                NotificationPriority.LOW: "#6B7280",  # Gray
            }
            color = color_map.get(priority, "#3B82F6")

            # Build Slack message payload with attachments
            payload = {
                "channel": target_channel,
                "username": self.slack_bot_name,
                "icon_emoji": ":robot_face:",
                "attachments": [
                    {
                        "fallback": f"{subject}: {message[:100]}...",
                        "color": color,
                        "title": subject,
                        "text": message[:3000],  # Slack limit
                        "footer": "Project Aura",
                        "footer_icon": "https://aura.local/icon.png",
                        "ts": int(datetime.now(tz=None).timestamp()),
                    }
                ],
            }

            # Send webhook request
            request = Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urlopen(
                request, timeout=10
            ) as response:  # nosec B310 - trusted webhook URL
                _response_body = response.read().decode("utf-8")  # noqa: F841

            message_id = f"slack-{int(datetime.now(tz=None).timestamp())}"
            log_entry["status"] = "sent"
            log_entry["message_id"] = message_id
            self.delivery_log.append(log_entry)

            logger.info(f"Slack notification sent to {target_channel}: {message_id}")

            return NotificationResult(
                success=True,
                message_id=message_id,
                channel=NotificationChannel.SLACK,
            )

        except (HTTPError, URLError) as e:
            error_msg = str(e)
            log_entry["status"] = "failed"
            log_entry["error"] = error_msg
            self.delivery_log.append(log_entry)

            logger.error(f"Failed to send Slack notification: {error_msg}")

            return NotificationResult(
                success=False,
                channel=NotificationChannel.SLACK,
                error=error_msg,
            )

    def _send_teams_notification(
        self,
        subject: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        webhook_url: str | None = None,
    ) -> NotificationResult:
        """
        Send notification to Microsoft Teams via incoming webhook.

        Args:
            subject: Message subject/title
            message: Message body
            priority: Notification priority
            webhook_url: Teams webhook URL (uses default if not provided)

        Returns:
            NotificationResult
        """
        url = webhook_url or self.teams_webhook_url

        log_entry = {
            "channel": NotificationChannel.TEAMS.value,
            "subject": subject,
            "priority": priority.value,
        }

        if self.mode == NotificationMode.MOCK or not url:
            logger.info(f"[MOCK] Teams: {subject}")
            log_entry["status"] = "mock_sent"
            log_entry["message_id"] = f"mock-teams-{len(self.delivery_log)}"
            self.delivery_log.append(log_entry)

            return NotificationResult(
                success=True,
                message_id=log_entry["message_id"],
                channel=NotificationChannel.TEAMS,
            )

        try:
            # Determine theme color based on priority
            color_map = {
                NotificationPriority.CRITICAL: "DC2626",  # Red (no #)
                NotificationPriority.HIGH: "EA580C",  # Orange
                NotificationPriority.NORMAL: "3B82F6",  # Blue
                NotificationPriority.LOW: "6B7280",  # Gray
            }
            theme_color = color_map.get(priority, "3B82F6")

            # Build Teams Adaptive Card payload
            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": theme_color,
                "summary": subject,
                "sections": [
                    {
                        "activityTitle": subject,
                        "activitySubtitle": f"Priority: {priority.value.upper()}",
                        "activityImage": "https://aura.local/icon.png",
                        "facts": [
                            {
                                "name": "Source",
                                "value": "Project Aura",
                            },
                            {
                                "name": "Time",
                                "value": datetime.now(tz=None).strftime(
                                    "%Y-%m-%d %H:%M:%S UTC"
                                ),
                            },
                        ],
                        "markdown": True,
                        "text": message[:28000],  # Teams limit ~28KB
                    }
                ],
                "potentialAction": [
                    {
                        "@type": "OpenUri",
                        "name": "View in Aura Dashboard",
                        "targets": [
                            {
                                "os": "default",
                                "uri": self.dashboard_url,
                            }
                        ],
                    }
                ],
            }

            # Send webhook request
            request = Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urlopen(
                request, timeout=10
            ) as response:  # nosec B310 - trusted webhook URL
                _response_body = response.read().decode("utf-8")  # noqa: F841

            message_id = f"teams-{int(datetime.now(tz=None).timestamp())}"
            log_entry["status"] = "sent"
            log_entry["message_id"] = message_id
            self.delivery_log.append(log_entry)

            logger.info(f"Teams notification sent: {message_id}")

            return NotificationResult(
                success=True,
                message_id=message_id,
                channel=NotificationChannel.TEAMS,
            )

        except (HTTPError, URLError) as e:
            error_msg = str(e)
            log_entry["status"] = "failed"
            log_entry["error"] = error_msg
            self.delivery_log.append(log_entry)

            logger.error(f"Failed to send Teams notification: {error_msg}")

            return NotificationResult(
                success=False,
                channel=NotificationChannel.TEAMS,
                error=error_msg,
            )

    def send_to_channel(
        self,
        channel_type: str,
        subject: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        config: dict[str, Any] | None = None,
    ) -> NotificationResult:
        """
        Send notification to a specific channel type.

        This is a unified method for sending to any configured channel.

        Args:
            channel_type: Channel type (email, slack, teams, sns, webhook)
            subject: Message subject
            message: Message body
            priority: Notification priority
            config: Channel-specific configuration override

        Returns:
            NotificationResult
        """
        config = config or {}

        if channel_type == NotificationChannel.EMAIL.value:
            recipient = config.get("recipient", config.get("recipients", [""])[0])
            return self._send_email(recipient, subject, message, priority)

        elif channel_type == NotificationChannel.SLACK.value:
            return self._send_slack_notification(
                subject=subject,
                message=message,
                priority=priority,
                webhook_url=config.get("webhook_url"),
                channel=config.get("channel"),
            )

        elif channel_type == NotificationChannel.TEAMS.value:
            return self._send_teams_notification(
                subject=subject,
                message=message,
                priority=priority,
                webhook_url=config.get("webhook_url"),
            )

        elif channel_type == NotificationChannel.SNS.value:
            return self._publish_to_sns(
                subject=subject,
                message=message,
                attributes=config.get("attributes"),
            )

        else:
            logger.warning(f"Unsupported channel type: {channel_type}")
            return NotificationResult(
                success=False,
                channel=None,
                error=f"Unsupported channel type: {channel_type}",
            )

    def send_decision_notification(
        self,
        approval_id: str,
        patch_id: str,
        decision: str,
        reviewer: str,
        reason: str | None,
        recipients: list[str],
    ) -> list[NotificationResult]:
        """
        Send notification about an approval decision.

        Args:
            approval_id: Approval request ID
            patch_id: Patch identifier
            decision: APPROVED or REJECTED
            reviewer: Who made the decision
            reason: Decision reason
            recipients: List of email addresses

        Returns:
            List of NotificationResult
        """
        results = []

        # Format subject based on decision
        emoji = "✅" if decision == "APPROVED" else "❌"
        subject = f"[AURA] {emoji} Patch {decision}: {patch_id}"

        body = f"""
Project Aura - Approval Decision Notification

Approval ID: {approval_id}
Patch ID: {patch_id}
Decision: {decision}
Reviewed By: {reviewer}
Reason: {reason or 'No reason provided'}

---
This is an automated notification from Project Aura.
"""

        for recipient in recipients:
            result = self._send_email(
                recipient=recipient,
                subject=subject,
                body=body,
                priority=NotificationPriority.NORMAL,
            )
            results.append(result)

        # Also publish to SNS
        sns_result = self._publish_to_sns(
            subject=subject,
            message=body,
            attributes={
                "approval_id": approval_id,
                "decision": decision,
            },
        )
        results.append(sns_result)

        return results

    def send_expiration_warning(
        self,
        approval_id: str,
        patch_id: str,
        severity: str,
        expires_at: str,
        recipients: list[str],
    ) -> list[NotificationResult]:
        """
        Send warning that an approval request is about to expire.

        Args:
            approval_id: Approval request ID
            patch_id: Patch identifier
            severity: Patch severity level
            expires_at: Expiration timestamp
            recipients: List of email addresses

        Returns:
            List of NotificationResult
        """
        results = []

        subject = f"[AURA] ⚠️ EXPIRING SOON: {severity} Patch {patch_id} needs review"

        review_url = f"{self.dashboard_url}/{approval_id}"

        body = f"""
Project Aura - Approval Expiration Warning

⚠️ ACTION REQUIRED: This approval request is about to expire!

Approval ID: {approval_id}
Patch ID: {patch_id}
Severity: {severity}
Expires: {expires_at}

Please review and make a decision before the request expires.

Review URL: {review_url}

---
This is an automated notification from Project Aura.
"""

        for recipient in recipients:
            result = self._send_email(
                recipient=recipient,
                subject=subject,
                body=body,
                priority=NotificationPriority.HIGH,
            )
            results.append(result)

        return results

    def send_escalation_notification(
        self,
        approval_id: str,
        patch_id: str,
        vulnerability_id: str,
        severity: str,
        original_reviewer: str | None,
        escalated_to: str,
        escalation_count: int,
        expires_at: str,
        sandbox_results: dict[str, Any],
        patch_diff: str,
    ) -> list[NotificationResult]:
        """
        Send notification that an approval request has been escalated.

        Args:
            approval_id: Approval request ID
            patch_id: Patch identifier
            vulnerability_id: Vulnerability identifier
            severity: Patch severity level
            original_reviewer: Original reviewer who didn't respond
            escalated_to: New reviewer receiving the escalation
            escalation_count: Number of times this has been escalated
            expires_at: New expiration timestamp
            sandbox_results: Test results from sandbox
            patch_diff: The code changes

        Returns:
            List of NotificationResult
        """
        results = []

        subject = f"[AURA] 🚨 ESCALATED: {severity} Patch {patch_id} requires immediate review"

        review_url = f"{self.dashboard_url}/{approval_id}"

        body = f"""
Project Aura - Escalated Approval Request

🚨 ESCALATION NOTICE: This security patch has been escalated to you for immediate review.

Approval ID: {approval_id}
Patch ID: {patch_id}
Vulnerability: {vulnerability_id}
Severity: {severity}
Escalation Count: {escalation_count}
Original Reviewer: {original_reviewer or 'Unassigned'}
New Expires: {expires_at}

--- SANDBOX TEST RESULTS ---
Tests Passed: {sandbox_results.get("tests_passed", "N/A")}
Tests Failed: {sandbox_results.get("tests_failed", "N/A")}
Test Coverage: {sandbox_results.get("coverage", "N/A")}%

--- PATCH DIFF ---
{patch_diff[:2000] if patch_diff else "N/A"}

--- URGENT ACTION REQUIRED ---
This patch was escalated because the previous reviewer did not respond in time.
{severity} severity vulnerabilities require immediate attention.

Review URL: {review_url}

---
This is an automated notification from Project Aura.
Do not reply to this email.
"""

        # Send to escalated reviewer
        result = self._send_email(
            recipient=escalated_to,
            subject=subject,
            body=body,
            priority=NotificationPriority.CRITICAL,
        )
        results.append(result)

        # Also publish to SNS for visibility
        sns_result = self._publish_to_sns(
            subject=subject,
            message=body,
            attributes={
                "approval_id": approval_id,
                "severity": severity,
                "event_type": "escalation",
                "escalation_count": str(escalation_count),
            },
        )
        results.append(sns_result)

        return results

    def send_expiration_notification(
        self,
        approval_id: str,
        patch_id: str,
        vulnerability_id: str,
        severity: str,
        recipients: list[str],
        requeued: bool = True,
    ) -> list[NotificationResult]:
        """
        Send notification that an approval request has expired.

        Args:
            approval_id: Approval request ID
            patch_id: Patch identifier
            vulnerability_id: Vulnerability identifier
            severity: Patch severity level
            recipients: List of email addresses
            requeued: Whether the patch was re-queued for next pipeline run

        Returns:
            List of NotificationResult
        """
        results = []

        subject = f"[AURA] ⏰ EXPIRED: Patch {patch_id} approval timeout"

        requeue_msg = (
            "The patch has been re-queued for the next pipeline run."
            if requeued
            else "Manual intervention may be required."
        )

        body = f"""
Project Aura - Approval Request Expired

⏰ NOTICE: This approval request has expired without a decision.

Approval ID: {approval_id}
Patch ID: {patch_id}
Vulnerability: {vulnerability_id}
Severity: {severity}

{requeue_msg}

---
This is an automated notification from Project Aura.
"""

        for recipient in recipients:
            result = self._send_email(
                recipient=recipient,
                subject=subject,
                body=body,
                priority=NotificationPriority.NORMAL,
            )
            results.append(result)

        # Publish to SNS
        sns_result = self._publish_to_sns(
            subject=subject,
            message=body,
            attributes={
                "approval_id": approval_id,
                "severity": severity,
                "event_type": "expiration",
            },
        )
        results.append(sns_result)

        return results

    def send_threat_alert(
        self,
        threat_id: str,
        title: str,
        severity: str,
        description: str,
        cve_ids: list[str] | None = None,
        affected_components: list[str] | None = None,
        recommended_actions: list[str] | None = None,
        recipients: list[str] | None = None,
    ) -> list[NotificationResult]:
        """
        Send threat intelligence alert for critical/high security threats.

        Args:
            threat_id: Unique threat identifier
            title: Threat title/headline
            severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
            description: Detailed threat description
            cve_ids: Associated CVE identifiers
            affected_components: List of affected system components
            recommended_actions: List of recommended remediation actions
            recipients: List of email addresses (defaults to security team)

        Returns:
            List of NotificationResult for each channel
        """
        results: list[NotificationResult] = []

        cve_list = ", ".join(cve_ids or []) or "None"
        components_list = ", ".join(affected_components or []) or "Not determined"
        actions_list = "\n".join(
            [
                f"  - {action}"
                for action in (recommended_actions or ["Review and assess impact"])
            ]
        )

        # Determine priority based on severity
        priority = (
            NotificationPriority.CRITICAL
            if severity == "CRITICAL"
            else NotificationPriority.HIGH
        )

        subject = f"[AURA THREAT ALERT] {severity}: {title}"
        body = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THREAT INTELLIGENCE ALERT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Threat ID: {threat_id}
Severity: {severity}
Detected: {datetime.now(tz=None).strftime("%Y-%m-%d %H:%M:%S")} UTC

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THREAT DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Title: {title}

Description:
{description}

CVE IDs: {cve_list}

Affected Components: {components_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RECOMMENDED ACTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{actions_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is an automated alert from Project Aura Threat Intelligence Pipeline.
For questions, contact the security team.
"""

        # Send to recipients (default to security team email from environment)
        default_recipient = os.environ.get(
            "SECURITY_TEAM_EMAIL", "security@example.com"
        )
        for recipient in recipients or [default_recipient]:
            result = self._send_email(
                recipient=recipient,
                subject=subject,
                body=body,
                priority=priority,
            )
            results.append(result)

        # Publish to SNS
        sns_result = self._publish_to_sns(
            subject=subject,
            message=body,
            attributes={
                "threat_id": threat_id,
                "severity": severity,
                "event_type": "threat_alert",
                "cve_ids": ",".join(cve_ids or []),
            },
        )
        results.append(sns_result)

        return results

    def get_delivery_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get recent delivery log entries.

        Args:
            limit: Maximum entries to return

        Returns:
            List of delivery log entries
        """
        return self.delivery_log[-limit:]

    def clear_delivery_log(self) -> None:
        """Clear the delivery log (for testing)."""
        self.delivery_log.clear()


# Factory function
def create_notification_service(
    use_mock: bool = False,
) -> NotificationService:
    """
    Create and return a NotificationService instance.

    Args:
        use_mock: Force mock mode for testing

    Returns:
        Configured NotificationService instance
    """
    if use_mock:
        mode = NotificationMode.MOCK
    else:
        mode = (
            NotificationMode.AWS
            if BOTO3_AVAILABLE and os.environ.get("AWS_REGION")
            else NotificationMode.MOCK
        )

    return NotificationService(mode=mode)


if __name__ == "__main__":
    # Demo/test usage
    logging.basicConfig(level=logging.INFO)

    print("Project Aura - Notification Service Demo")
    print("=" * 60)

    service = create_notification_service(use_mock=True)
    print(f"\nMode: {service.mode.value}")
    print(f"SNS Topic: {service.sns_topic_arn}")
    print(f"SES Sender: {service.ses_sender_email}")

    # Test approval notification
    print("\nSending approval notification...")
    results = service.send_approval_notification(
        approval_id="approval-20251201-abc123",
        patch_id="patch-sha256-upgrade",
        vulnerability_id="vuln-sha1-weak-hash",
        severity="HIGH",
        created_at="2025-12-01T12:00:00",
        expires_at="2025-12-02T12:00:00",
        sandbox_results={
            "tests_passed": 42,
            "tests_failed": 0,
            "coverage": 87.5,
        },
        patch_diff="- hashlib.sha1(data)\n+ hashlib.sha256(data)",
        recipients=["security-team@company.com"],
    )

    print(f"Results: {len(results)} notifications sent")
    for result in results:
        print(
            f"  - {result.channel}: {'✓' if result.success else '✗'} {result.message_id or result.error}"
        )

    # Test decision notification
    print("\nSending decision notification...")
    results = service.send_decision_notification(
        approval_id="approval-20251201-abc123",
        patch_id="patch-sha256-upgrade",
        decision="APPROVED",
        reviewer="security-lead@company.com",
        reason="LGTM - code review passed",
        recipients=["dev-team@company.com"],
    )

    print(f"Results: {len(results)} notifications sent")

    # Show delivery log
    print("\nDelivery Log:")
    for entry in service.get_delivery_log():
        print(f"  - {entry.get('channel')}: {entry.get('status')}")

    print("\n" + "=" * 60)
    print("Demo complete!")
