"""
Project Aura - Security Alerts Service

Integrates security events with HITL workflow for approval:
- Monitors security audit events
- Creates HITL approval requests for critical events
- Publishes to SNS for real-time alerting
- Integrates with EventBridge for event routing

Author: Project Aura Team
Created: 2025-12-12
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.services.security_audit_service import (
    SecurityEvent,
    SecurityEventSeverity,
    SecurityEventType,
)

logger = logging.getLogger(__name__)


class AlertPriority(Enum):
    """Alert priority levels."""

    P1_CRITICAL = "P1"  # Immediate response required
    P2_HIGH = "P2"  # Response within 1 hour
    P3_MEDIUM = "P3"  # Response within 4 hours
    P4_LOW = "P4"  # Response within 24 hours
    P5_INFO = "P5"  # Informational, no response required


class AlertStatus(Enum):
    """Alert status values."""

    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


@dataclass
class SecurityAlert:
    """Security alert for HITL review."""

    alert_id: str
    title: str
    description: str
    priority: AlertPriority
    status: AlertStatus
    security_event: SecurityEvent
    created_at: str
    acknowledged_at: str | None = None
    resolved_at: str | None = None
    assigned_to: str | None = None
    remediation_steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "security_event": self.security_event.to_dict(),
            "created_at": self.created_at,
            "acknowledged_at": self.acknowledged_at,
            "resolved_at": self.resolved_at,
            "assigned_to": self.assigned_to,
            "remediation_steps": self.remediation_steps,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class HITLApprovalRequest:
    """HITL approval request for security alerts."""

    request_id: str
    alert_id: str
    approval_type: str
    title: str
    description: str
    priority: str
    requested_action: str
    context: dict[str, Any]
    created_at: str
    expires_at: str | None = None
    status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "alert_id": self.alert_id,
            "approval_type": self.approval_type,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "requested_action": self.requested_action,
            "context": self.context,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "status": self.status,
        }


class SecurityAlertsService:
    """
    Service for managing security alerts and HITL integration.

    Features:
    - Automatic alert creation from security events
    - Priority-based routing
    - SNS notification publishing
    - EventBridge event emission
    - HITL approval request creation
    """

    # Event type to alert configuration mapping
    ALERT_CONFIG: dict[SecurityEventType, dict[str, Any]] = {
        # Critical - P1 (immediate)
        SecurityEventType.AUTHZ_PRIVILEGE_ESCALATION: {
            "priority": AlertPriority.P1_CRITICAL,
            "requires_hitl": True,
            "title_template": "Privilege Escalation Attempt Detected",
            "remediation": [
                "Review the user's current permissions",
                "Check for unauthorized role changes",
                "Verify audit logs for related activity",
                "Consider temporary account suspension if malicious",
            ],
        },
        SecurityEventType.THREAT_COMMAND_INJECTION: {
            "priority": AlertPriority.P1_CRITICAL,
            "requires_hitl": True,
            "title_template": "Command Injection Attack Detected",
            "remediation": [
                "Block the source IP immediately",
                "Review affected endpoints for vulnerabilities",
                "Check for successful command execution",
                "Audit system for unauthorized changes",
            ],
        },
        SecurityEventType.THREAT_SECRETS_EXPOSURE: {
            "priority": AlertPriority.P1_CRITICAL,
            "requires_hitl": True,
            "title_template": "Secrets Exposure Detected",
            "remediation": [
                "Identify exposed credentials",
                "Rotate all affected secrets immediately",
                "Audit access logs for credential usage",
                "Review code for additional exposures",
            ],
        },
        # High - P2 (1 hour)
        SecurityEventType.THREAT_PROMPT_INJECTION: {
            "priority": AlertPriority.P2_HIGH,
            "requires_hitl": True,
            "title_template": "Prompt Injection Attack Detected",
            "remediation": [
                "Review the malicious prompt content",
                "Check if any harmful actions were executed",
                "Update input sanitization rules",
                "Consider blocking the user temporarily",
            ],
        },
        SecurityEventType.THREAT_SSRF_ATTEMPT: {
            "priority": AlertPriority.P2_HIGH,
            "requires_hitl": True,
            "title_template": "SSRF Attack Attempt Detected",
            "remediation": [
                "Block the source IP",
                "Review URL validation logic",
                "Check for internal service exposure",
                "Audit network logs",
            ],
        },
        SecurityEventType.INPUT_INJECTION_ATTEMPT: {
            "priority": AlertPriority.P2_HIGH,
            "requires_hitl": False,
            "title_template": "Injection Attack Detected",
            "remediation": [
                "Review input validation for affected endpoint",
                "Check if attack was successful",
                "Update WAF rules if needed",
            ],
        },
        SecurityEventType.INPUT_XSS_ATTEMPT: {
            "priority": AlertPriority.P2_HIGH,
            "requires_hitl": False,
            "title_template": "XSS Attack Attempt Detected",
            "remediation": [
                "Review output encoding",
                "Update CSP headers if needed",
                "Check for stored XSS",
            ],
        },
        # Medium - P3 (4 hours)
        SecurityEventType.AUTH_LOGIN_FAILURE: {
            "priority": AlertPriority.P3_MEDIUM,
            "requires_hitl": False,
            "title_template": "Multiple Login Failures Detected",
            "remediation": [
                "Review for brute force patterns",
                "Consider account lockout",
                "Check if legitimate user issue",
            ],
        },
        SecurityEventType.AUTHZ_ACCESS_DENIED: {
            "priority": AlertPriority.P3_MEDIUM,
            "requires_hitl": False,
            "title_template": "Access Denied Events Detected",
            "remediation": [
                "Review user permissions",
                "Check if authorization rules are correct",
            ],
        },
        SecurityEventType.RATE_LIMIT_EXCEEDED: {
            "priority": AlertPriority.P3_MEDIUM,
            "requires_hitl": False,
            "title_template": "Rate Limit Exceeded",
            "remediation": [
                "Review client for abuse patterns",
                "Consider temporary blocking",
            ],
        },
        SecurityEventType.ADMIN_USER_DELETE: {
            "priority": AlertPriority.P2_HIGH,
            "requires_hitl": True,
            "title_template": "Admin User Deletion",
            "remediation": [
                "Verify deletion was authorized",
                "Review admin activity logs",
            ],
        },
        SecurityEventType.ADMIN_POLICY_CHANGE: {
            "priority": AlertPriority.P2_HIGH,
            "requires_hitl": True,
            "title_template": "Security Policy Changed",
            "remediation": [
                "Review policy changes",
                "Verify authorization",
                "Check for weakened security settings",
            ],
        },
    }

    def __init__(
        self,
        sns_topic_arn: str | None = None,
        eventbridge_bus_name: str | None = None,
        hitl_table_name: str | None = None,
        auto_create_alerts: bool = True,
    ):
        """
        Initialize security alerts service.

        Args:
            sns_topic_arn: SNS topic ARN for notifications
            eventbridge_bus_name: EventBridge bus name for events
            hitl_table_name: DynamoDB table for HITL requests
            auto_create_alerts: Auto-create alerts from security events
        """
        self.sns_topic_arn = sns_topic_arn or os.environ.get("SECURITY_SNS_TOPIC_ARN")
        self.eventbridge_bus_name = eventbridge_bus_name or os.environ.get(
            "SECURITY_EVENTBRIDGE_BUS", "aura-security-events"
        )
        self.hitl_table_name = hitl_table_name or os.environ.get(
            "HITL_TABLE_NAME", "aura-hitl-requests"
        )
        self.auto_create_alerts = auto_create_alerts

        # Alert storage (in production, use DynamoDB)
        self._alerts: dict[str, SecurityAlert] = {}
        self._hitl_requests: dict[str, HITLApprovalRequest] = {}

        # Statistics
        self._stats = {
            "alerts_created": 0,
            "hitl_requests_created": 0,
            "sns_notifications_sent": 0,
            "events_published": 0,
        }

    def process_security_event(
        self,
        event: SecurityEvent,
    ) -> SecurityAlert | None:
        """
        Process a security event and create alert if needed.

        Args:
            event: Security event to process

        Returns:
            SecurityAlert if created, None otherwise
        """
        # Get alert configuration
        config = self.ALERT_CONFIG.get(event.event_type)

        if not config:
            # No alert needed for this event type
            return None

        # Only create alerts for HIGH and CRITICAL severity
        if event.severity not in [
            SecurityEventSeverity.HIGH,
            SecurityEventSeverity.CRITICAL,
        ]:
            return None

        # Create alert
        alert = self._create_alert(event, config)
        self._alerts[alert.alert_id] = alert
        self._stats["alerts_created"] += 1

        # Publish to SNS
        self._publish_to_sns(alert)

        # Publish to EventBridge
        self._publish_to_eventbridge(alert)

        # Create HITL request if required
        if config.get("requires_hitl", False):
            self._create_hitl_request(alert)

        logger.info(
            f"Security alert created: {alert.alert_id} "
            f"({alert.priority.value}) - {alert.title}"
        )

        return alert

    def _create_alert(
        self,
        event: SecurityEvent,
        config: dict[str, Any],
    ) -> SecurityAlert:
        """Create a security alert from an event."""
        alert_id = f"alert-{uuid.uuid4().hex[:12]}"

        # Build description
        description = (
            f"{event.message}\n\n"
            f"Event ID: {event.event_id}\n"
            f"Event Type: {event.event_type.value}\n"
            f"Severity: {event.severity.value}\n"
            f"Source: {event.source}\n"
            f"Timestamp: {event.timestamp}"
        )

        if event.context:
            ctx = event.context.to_dict()
            if ctx:
                description += "\n\nContext:\n"
                for key, value in ctx.items():
                    description += f"  {key}: {value}\n"

        return SecurityAlert(
            alert_id=alert_id,
            title=config["title_template"],
            description=description,
            priority=config["priority"],
            status=AlertStatus.NEW,
            security_event=event,
            created_at=datetime.now(timezone.utc).isoformat(),
            remediation_steps=config.get("remediation", []),
            metadata={
                "event_type": event.event_type.value,
                "source_ip": event.context.ip_address if event.context else None,
                "user_id": event.context.user_id if event.context else None,
            },
        )

    def _create_hitl_request(self, alert: SecurityAlert) -> HITLApprovalRequest:
        """Create HITL approval request for alert."""
        request_id = f"hitl-{uuid.uuid4().hex[:12]}"

        # Determine requested action based on priority
        if alert.priority == AlertPriority.P1_CRITICAL:
            requested_action = "immediate_response"
        elif alert.priority == AlertPriority.P2_HIGH:
            requested_action = "investigate_and_respond"
        else:
            requested_action = "review_and_acknowledge"

        request = HITLApprovalRequest(
            request_id=request_id,
            alert_id=alert.alert_id,
            approval_type="security_alert",
            title=f"Security Alert: {alert.title}",
            description=alert.description,
            priority=alert.priority.value,
            requested_action=requested_action,
            context={
                "alert": alert.to_dict(),
                "remediation_steps": alert.remediation_steps,
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self._hitl_requests[request.request_id] = request
        self._stats["hitl_requests_created"] += 1

        logger.info(f"HITL request created: {request_id} for alert {alert.alert_id}")

        # In production, write to DynamoDB
        self._persist_hitl_request(request)

        return request

    def _persist_hitl_request(self, request: HITLApprovalRequest) -> None:
        """Persist HITL request to DynamoDB."""
        try:
            import boto3

            dynamodb = boto3.resource("dynamodb")
            table = dynamodb.Table(self.hitl_table_name)
            table.put_item(Item=request.to_dict())
        except Exception as e:
            logger.warning(f"Could not persist HITL request: {e}")

    def _publish_to_sns(self, alert: SecurityAlert) -> None:
        """Publish alert to SNS topic."""
        if not self.sns_topic_arn:
            return

        try:
            import boto3

            sns = boto3.client("sns")
            sns.publish(
                TopicArn=self.sns_topic_arn,
                Subject=f"[{alert.priority.value}] {alert.title}",
                Message=json.dumps(alert.to_dict(), indent=2),
                MessageAttributes={
                    "priority": {
                        "DataType": "String",
                        "StringValue": alert.priority.value,
                    },
                    "alert_id": {
                        "DataType": "String",
                        "StringValue": alert.alert_id,
                    },
                },
            )
            self._stats["sns_notifications_sent"] += 1
        except Exception as e:
            logger.warning(f"Could not publish to SNS: {e}")

    def _publish_to_eventbridge(self, alert: SecurityAlert) -> None:
        """Publish alert to EventBridge."""
        try:
            import boto3

            events = boto3.client("events")
            events.put_events(
                Entries=[
                    {
                        "Source": "aura.security",
                        "DetailType": "SecurityAlert",
                        "Detail": alert.to_json(),
                        "EventBusName": self.eventbridge_bus_name,
                    }
                ]
            )
            self._stats["events_published"] += 1
        except Exception as e:
            logger.warning(f"Could not publish to EventBridge: {e}")

    def acknowledge_alert(
        self,
        alert_id: str,
        user_id: str,
        notes: str | None = None,
    ) -> SecurityAlert | None:
        """Acknowledge a security alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return None

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now(timezone.utc).isoformat()
        alert.assigned_to = user_id

        if notes:
            alert.metadata["acknowledgment_notes"] = notes

        logger.info(f"Alert {alert_id} acknowledged by {user_id}")
        return alert

    def resolve_alert(
        self,
        alert_id: str,
        user_id: str,
        resolution: str,
        is_false_positive: bool = False,
    ) -> SecurityAlert | None:
        """Resolve a security alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return None

        if is_false_positive:
            alert.status = AlertStatus.FALSE_POSITIVE
        else:
            alert.status = AlertStatus.RESOLVED

        alert.resolved_at = datetime.now(timezone.utc).isoformat()
        alert.metadata["resolution"] = resolution
        alert.metadata["resolved_by"] = user_id

        logger.info(f"Alert {alert_id} resolved by {user_id}")
        return alert

    def get_alert(self, alert_id: str) -> SecurityAlert | None:
        """Get alert by ID."""
        return self._alerts.get(alert_id)

    def get_alerts(
        self,
        status: AlertStatus | None = None,
        priority: AlertPriority | None = None,
    ) -> list[SecurityAlert]:
        """Get alerts with optional filtering."""
        alerts = list(self._alerts.values())

        if status:
            alerts = [a for a in alerts if a.status == status]

        if priority:
            alerts = [a for a in alerts if a.priority == priority]

        # Sort by priority and creation time
        priority_order = {
            AlertPriority.P1_CRITICAL: 0,
            AlertPriority.P2_HIGH: 1,
            AlertPriority.P3_MEDIUM: 2,
            AlertPriority.P4_LOW: 3,
            AlertPriority.P5_INFO: 4,
        }
        alerts.sort(key=lambda a: (priority_order[a.priority], a.created_at))

        return alerts

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            **self._stats,
            "active_alerts": len(
                [
                    a
                    for a in self._alerts.values()
                    if a.status in [AlertStatus.NEW, AlertStatus.ACKNOWLEDGED]
                ]
            ),
            "pending_hitl_requests": len(
                [r for r in self._hitl_requests.values() if r.status == "pending"]
            ),
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_alerts_service: SecurityAlertsService | None = None


def get_alerts_service() -> SecurityAlertsService:
    """Get singleton security alerts service instance."""
    global _alerts_service
    if _alerts_service is None:
        _alerts_service = SecurityAlertsService()
    return _alerts_service


def process_security_event(event: SecurityEvent) -> SecurityAlert | None:
    """Convenience function to process a security event."""
    return get_alerts_service().process_security_event(event)
