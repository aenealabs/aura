"""
Project Aura - Honeypot Detector

Honeypot capabilities that should never be called by legitimate agents.
Any invocation immediately triggers security alert + automatic quarantine.

Implements ADR-072 for ML-based anomaly detection.

CRITICAL: Honeypots are the ONLY detection mechanism that can trigger
automatic quarantine without HITL approval. This is because honeypot access
has zero false positives by design - if an agent attempts to access a
honeypot capability, it is definitively malicious or confused.
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from .anomaly_contracts import (
    AlertSeverity,
    AnomalyResult,
    AnomalyType,
    HoneypotCapability,
    HoneypotResult,
    InvocationContext,
    QuarantineReason,
    QuarantineRecord,
)

logger = logging.getLogger(__name__)


# Predefined honeypot capabilities - these should NEVER be called
HONEYPOT_CAPABILITIES: dict[str, HoneypotCapability] = {
    "admin_override": HoneypotCapability(
        name="admin_override",
        description="Emergency administrative override - bypasses all security controls",
        classification="CRITICAL",
        legitimate_use=False,
        alert_severity=AlertSeverity.P1,
    ),
    "export_all_credentials": HoneypotCapability(
        name="export_all_credentials",
        description="Bulk credential export - extracts all stored secrets",
        classification="CRITICAL",
        legitimate_use=False,
        alert_severity=AlertSeverity.P1,
    ),
    "disable_audit_logging": HoneypotCapability(
        name="disable_audit_logging",
        description="Disable audit trail - stops all security logging",
        classification="CRITICAL",
        legitimate_use=False,
        alert_severity=AlertSeverity.P1,
    ),
    "bypass_hitl_approval": HoneypotCapability(
        name="bypass_hitl_approval",
        description="Skip human approval for CRITICAL operations",
        classification="CRITICAL",
        legitimate_use=False,
        alert_severity=AlertSeverity.P1,
    ),
    "access_all_tenants": HoneypotCapability(
        name="access_all_tenants",
        description="Cross-tenant data access - reads data from all tenants",
        classification="CRITICAL",
        legitimate_use=False,
        alert_severity=AlertSeverity.P1,
    ),
    "execute_arbitrary_code": HoneypotCapability(
        name="execute_arbitrary_code",
        description="Execute arbitrary code without sandboxing",
        classification="CRITICAL",
        legitimate_use=False,
        alert_severity=AlertSeverity.P1,
    ),
    "delete_all_data": HoneypotCapability(
        name="delete_all_data",
        description="Mass data deletion without confirmation",
        classification="CRITICAL",
        legitimate_use=False,
        alert_severity=AlertSeverity.P1,
    ),
    "modify_security_policies": HoneypotCapability(
        name="modify_security_policies",
        description="Modify capability governance policies",
        classification="CRITICAL",
        legitimate_use=False,
        alert_severity=AlertSeverity.P1,
    ),
    "escalate_privileges": HoneypotCapability(
        name="escalate_privileges",
        description="Self-grant elevated permissions",
        classification="CRITICAL",
        legitimate_use=False,
        alert_severity=AlertSeverity.P1,
    ),
    "access_root_credentials": HoneypotCapability(
        name="access_root_credentials",
        description="Access AWS root account credentials",
        classification="CRITICAL",
        legitimate_use=False,
        alert_severity=AlertSeverity.P1,
    ),
}


class HoneypotDetector:
    """
    Honeypot capabilities detector.

    Honeypots are capabilities that should never be called. Any invocation
    immediately triggers a security alert and automatic quarantine without
    requiring HITL approval.

    Why honeypot-only auto-quarantine:
    - ML models have inherent false positive rates (target <5%, but non-zero)
    - Auto-quarantine from ML could denial-of-service legitimate agents
    - Adversaries could craft inputs that trigger ML false positives
    - Honeypots are binary: any access is unauthorized (zero false positives)
    """

    def __init__(
        self,
        capabilities: dict[str, HoneypotCapability] | None = None,
        sns_client: Any | None = None,
        sns_topic_arn: str | None = None,
    ):
        """
        Initialize the honeypot detector.

        Args:
            capabilities: Custom honeypot capabilities (uses defaults if None)
            sns_client: Boto3 SNS client for alerts (optional)
            sns_topic_arn: SNS topic ARN for security alerts (optional)
        """
        self.capabilities = capabilities or HONEYPOT_CAPABILITIES
        self.sns_client = sns_client
        self.sns_topic_arn = sns_topic_arn

        # In-memory stores for quarantine and forensics (replace with DynamoDB in production)
        self._quarantined_agents: dict[str, QuarantineRecord] = {}
        self._forensic_logs: list[dict[str, Any]] = []
        self._alert_history: list[dict[str, Any]] = []

    def is_honeypot(self, tool_name: str) -> bool:
        """Check if a tool name is a honeypot capability."""
        return tool_name in self.capabilities

    def get_honeypot(self, tool_name: str) -> HoneypotCapability | None:
        """Get honeypot capability definition."""
        return self.capabilities.get(tool_name)

    def list_honeypots(self) -> list[HoneypotCapability]:
        """List all honeypot capabilities."""
        return list(self.capabilities.values())

    async def check_honeypot_access(
        self,
        agent_id: str,
        tool_name: str,
        context: InvocationContext | None = None,
    ) -> HoneypotResult:
        """
        Check if a tool invocation is a honeypot access.

        If the tool is a honeypot, this method:
        1. Immediately publishes a P1 security alert
        2. Quarantines the agent (blocks further actions)
        3. Logs forensic data for investigation

        Args:
            agent_id: Unique identifier for the agent
            tool_name: Name of the tool being invoked
            context: Invocation context for forensics

        Returns:
            HoneypotResult indicating if honeypot was triggered
        """
        if tool_name not in self.capabilities:
            return HoneypotResult(triggered=False)

        honeypot = self.capabilities[tool_name]

        logger.critical(
            f"HONEYPOT TRIGGERED: Agent {agent_id} attempted to access "
            f"honeypot capability '{tool_name}'"
        )

        # Immediate alert
        await self._publish_security_alert(
            severity=honeypot.alert_severity,
            event_type="HONEYPOT_TRIGGERED",
            agent_id=agent_id,
            tool_name=tool_name,
            context=context,
            message=(
                f"Agent {agent_id} attempted to access honeypot capability "
                f"'{tool_name}'. This indicates potential prompt injection, "
                f"agent confusion, or malicious activity."
            ),
        )

        # Quarantine agent (automatic - no HITL required)
        quarantine_record = await self._quarantine_agent(
            agent_id=agent_id,
            reason=QuarantineReason.HONEYPOT_TRIGGERED,
            tool_name=tool_name,
        )

        # Log for forensics
        await self._log_forensic_event(
            agent_id=agent_id,
            tool_name=tool_name,
            context=context,
            quarantine_record=quarantine_record,
        )

        return HoneypotResult(
            triggered=True,
            honeypot_name=tool_name,
            action_taken="quarantine",
            agent_id=agent_id,
            timestamp=datetime.utcnow(),
        )

    async def get_anomaly_result(
        self,
        agent_id: str,
        tool_name: str,
        context: InvocationContext | None = None,
    ) -> AnomalyResult:
        """
        Get an AnomalyResult for honeypot check (for integration with fused scoring).

        Args:
            agent_id: Unique identifier for the agent
            tool_name: Name of the tool being checked
            context: Invocation context

        Returns:
            AnomalyResult with honeypot type
        """
        result = await self.check_honeypot_access(agent_id, tool_name, context)

        return AnomalyResult(
            is_anomaly=result.triggered,
            score=1.0 if result.triggered else 0.0,
            anomaly_type=AnomalyType.HONEYPOT,
            details={
                "honeypot_name": result.honeypot_name,
                "action_taken": result.action_taken,
                "triggered": result.triggered,
            },
        )

    async def _publish_security_alert(
        self,
        severity: AlertSeverity,
        event_type: str,
        agent_id: str,
        tool_name: str,
        context: InvocationContext | None,
        message: str,
    ) -> None:
        """Publish security alert to SNS topic."""
        alert = {
            "alert_id": str(uuid.uuid4()),
            "severity": severity.value,
            "event_type": event_type,
            "agent_id": agent_id,
            "tool_name": tool_name,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context.to_dict() if context else None,
        }

        self._alert_history.append(alert)

        if self.sns_client and self.sns_topic_arn:
            try:
                import json

                await self._async_sns_publish(
                    self.sns_client,
                    self.sns_topic_arn,
                    json.dumps(alert),
                    f"[{severity.value}] Honeypot Triggered: {tool_name}",
                )
            except Exception as e:
                logger.error(f"Failed to publish SNS alert: {e}")

        logger.critical(f"Security Alert [{severity.value}]: {message}")

    async def _async_sns_publish(
        self,
        client: Any,
        topic_arn: str,
        message: str,
        subject: str,
    ) -> None:
        """Async wrapper for SNS publish."""
        import asyncio

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: client.publish(
                TopicArn=topic_arn,
                Message=message,
                Subject=subject,
            ),
        )

    async def _quarantine_agent(
        self,
        agent_id: str,
        reason: QuarantineReason,
        tool_name: str,
    ) -> QuarantineRecord:
        """Quarantine an agent (block further actions)."""
        record = QuarantineRecord(
            agent_id=agent_id,
            reason=reason,
            triggered_by=tool_name,
            anomaly_score=1.0,  # Honeypots always have score of 1.0
            quarantined_at=datetime.utcnow(),
            notes=f"Automatic quarantine due to {reason.value}",
        )

        self._quarantined_agents[agent_id] = record

        logger.warning(f"Agent {agent_id} quarantined: {reason.value}")

        return record

    async def _log_forensic_event(
        self,
        agent_id: str,
        tool_name: str,
        context: InvocationContext | None,
        quarantine_record: QuarantineRecord,
    ) -> None:
        """Log forensic data for investigation."""
        forensic_entry = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": agent_id,
            "tool_name": tool_name,
            "context": context.to_dict() if context else None,
            "quarantine": quarantine_record.to_dict(),
        }

        self._forensic_logs.append(forensic_entry)
        logger.info(f"Forensic event logged: {forensic_entry['event_id']}")

    def is_quarantined(self, agent_id: str) -> bool:
        """Check if an agent is currently quarantined."""
        record = self._quarantined_agents.get(agent_id)
        return record is not None and record.is_active

    def get_quarantine_record(self, agent_id: str) -> QuarantineRecord | None:
        """Get quarantine record for an agent."""
        return self._quarantined_agents.get(agent_id)

    async def release_from_quarantine(
        self,
        agent_id: str,
        released_by: str,
        notes: str | None = None,
    ) -> bool:
        """
        Release an agent from quarantine (requires HITL approval).

        Args:
            agent_id: Agent to release
            released_by: User who approved the release
            notes: Optional notes about the release

        Returns:
            True if released, False if not found or already released
        """
        record = self._quarantined_agents.get(agent_id)
        if record is None or not record.is_active:
            return False

        record.released_at = datetime.utcnow()
        record.hitl_approved_by = released_by
        if notes:
            record.notes = (record.notes or "") + f" | Release: {notes}"

        logger.info(f"Agent {agent_id} released from quarantine by {released_by}")
        return True

    def get_alert_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent alert history."""
        return self._alert_history[-limit:]

    def get_forensic_logs(
        self, agent_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get forensic logs, optionally filtered by agent."""
        logs = self._forensic_logs
        if agent_id:
            logs = [log for log in logs if log["agent_id"] == agent_id]
        return logs[-limit:]


# Singleton instance
_detector_instance: HoneypotDetector | None = None


def get_honeypot_detector() -> HoneypotDetector:
    """Get or create the singleton honeypot detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = HoneypotDetector()
    return _detector_instance


def reset_honeypot_detector() -> None:
    """Reset the singleton instance (for testing)."""
    global _detector_instance
    _detector_instance = None
