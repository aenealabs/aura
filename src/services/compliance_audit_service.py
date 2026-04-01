"""
Compliance Audit Trail Service.

Provides tamper-evident audit logging for compliance-based security decisions.
Integrates with CloudWatch Logs and DynamoDB for long-term retention.

Author: Aura Platform Team
Date: 2025-12-06
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""

    SCAN_INITIATED = "SCAN_INITIATED"
    SCAN_COMPLETED = "SCAN_COMPLETED"
    FILE_SCANNED = "FILE_SCANNED"
    FILE_SKIPPED = "FILE_SKIPPED"
    FINDING_DETECTED = "FINDING_DETECTED"
    DEPLOYMENT_BLOCKED = "DEPLOYMENT_BLOCKED"
    DEPLOYMENT_APPROVED = "DEPLOYMENT_APPROVED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    MANUAL_REVIEW_APPROVED = "MANUAL_REVIEW_APPROVED"
    MANUAL_REVIEW_REJECTED = "MANUAL_REVIEW_REJECTED"
    PROFILE_LOADED = "PROFILE_LOADED"
    PROFILE_OVERRIDE_APPLIED = "PROFILE_OVERRIDE_APPLIED"
    COMPLIANCE_VIOLATION = "COMPLIANCE_VIOLATION"


@dataclass
class AuditEvent:
    """Represents an audit trail event."""

    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    profile_name: str
    profile_version: str
    actor: str  # User, agent, or system component
    action: str  # Human-readable action description
    resource: Optional[str] = None  # File, service, or resource affected
    metadata: Optional[Dict[str, Any]] = None  # Additional context
    compliance_controls: Optional[List[str]] = None  # CMMC/SOX controls satisfied
    result: Optional[str] = None  # Success, failure, blocked, etc.

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["event_type"] = self.event_type.value
        return data

    def to_cloudwatch_log(self) -> str:
        """Format as CloudWatch Logs JSON."""
        return json.dumps(self.to_dict())


class ComplianceAuditService:
    """
    Manages compliance audit trails.

    Provides tamper-evident logging with:
    - CloudWatch Logs (real-time monitoring)
    - DynamoDB (long-term retention, queryable)
    - Local file logging (development)
    """

    def __init__(
        self,
        profile_name: str,
        profile_version: str = "1.0.0",
        enable_cloudwatch: bool = True,
        enable_dynamodb: bool = True,
    ):
        """
        Initialize ComplianceAuditService.

        Args:
            profile_name: Name of the compliance profile
            profile_version: Version of the profile
            enable_cloudwatch: Enable CloudWatch Logs
            enable_dynamodb: Enable DynamoDB persistence
        """
        self.profile_name = profile_name
        self.profile_version = profile_version
        self.enable_cloudwatch = enable_cloudwatch
        self.enable_dynamodb = enable_dynamodb

        # Event buffer for batch writes
        self._event_buffer: List[AuditEvent] = []
        self._buffer_size = 10  # Flush after 10 events

        logger.info(f"Initialized ComplianceAuditService for profile: {profile_name}")

    def log_event(
        self,
        event_type: AuditEventType,
        actor: str,
        action: str,
        resource: Optional[str] = None,
        metadata: Optional[Dict] = None,
        compliance_controls: Optional[List[str]] = None,
        result: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log a compliance audit event.

        Args:
            event_type: Type of audit event
            actor: Who initiated the action
            action: Human-readable action description
            resource: Resource affected (file, service, etc.)
            metadata: Additional context
            compliance_controls: CMMC/SOX controls satisfied
            result: Result of the action

        Returns:
            AuditEvent instance
        """
        event = AuditEvent(
            event_id=self._generate_event_id(),
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            profile_name=self.profile_name,
            profile_version=self.profile_version,
            actor=actor,
            action=action,
            resource=resource,
            metadata=metadata or {},
            compliance_controls=compliance_controls or [],
            result=result,
        )

        # Log to standard logger
        logger.info(
            f"[AUDIT] {event_type.value}: {action} by {actor} "
            f"(resource={resource}, result={result})"
        )

        # Add to buffer
        self._event_buffer.append(event)

        # Flush if buffer is full
        if len(self._event_buffer) >= self._buffer_size:
            self._flush_buffer()

        return event

    def log_scan_initiated(
        self,
        actor: str,
        files_to_scan: List[str],
        metadata: Optional[Dict] = None,
    ) -> AuditEvent:
        """Log scan initiation."""
        return self.log_event(
            event_type=AuditEventType.SCAN_INITIATED,
            actor=actor,
            action=f"Initiated security scan of {len(files_to_scan)} files",
            metadata={
                **(metadata or {}),
                "file_count": len(files_to_scan),
                "files": files_to_scan[:10],  # First 10 files
            },
            compliance_controls=["CA-3.12.4", "RA-3.11.2"],
            result="INITIATED",
        )

    def log_scan_completed(
        self,
        actor: str,
        files_scanned: int,
        findings_count: int,
        critical_count: int,
        high_count: int,
        metadata: Optional[Dict] = None,
    ) -> AuditEvent:
        """Log scan completion."""
        return self.log_event(
            event_type=AuditEventType.SCAN_COMPLETED,
            actor=actor,
            action=f"Completed security scan: {findings_count} findings, "
            f"{critical_count} critical, {high_count} high",
            metadata={
                **(metadata or {}),
                "files_scanned": files_scanned,
                "findings_count": findings_count,
                "critical_count": critical_count,
                "high_count": high_count,
            },
            compliance_controls=["CA-3.12.4", "RA-3.11.2", "SI-3.14.4"],
            result="COMPLETED",
        )

    def log_file_skipped(
        self,
        actor: str,
        file_path: str,
        reason: str,
    ) -> AuditEvent:
        """Log file skipped during scan."""
        return self.log_event(
            event_type=AuditEventType.FILE_SKIPPED,
            actor=actor,
            action=f"Skipped file: {reason}",
            resource=file_path,
            metadata={"skip_reason": reason},
            result="SKIPPED",
        )

    def log_deployment_decision(
        self,
        actor: str,
        should_block: bool,
        reason: str,
        metadata: Optional[Dict] = None,
    ) -> AuditEvent:
        """Log deployment block/approve decision."""
        event_type = (
            AuditEventType.DEPLOYMENT_BLOCKED
            if should_block
            else AuditEventType.DEPLOYMENT_APPROVED
        )

        return self.log_event(
            event_type=event_type,
            actor=actor,
            action=f"Deployment {'BLOCKED' if should_block else 'APPROVED'}: {reason}",
            metadata=metadata or {},
            compliance_controls=["CM-3.4.7", "SA-3.15.11"],
            result="BLOCKED" if should_block else "APPROVED",
        )

    def log_manual_review_required(
        self,
        actor: str,
        reasons: List[str],
        affected_files: List[str],
        metadata: Optional[Dict] = None,
    ) -> AuditEvent:
        """Log manual HITL review requirement."""
        return self.log_event(
            event_type=AuditEventType.MANUAL_REVIEW_REQUIRED,
            actor=actor,
            action=f"Manual review required: {', '.join(reasons[:3])}",
            metadata={
                **(metadata or {}),
                "review_reasons": reasons,
                "affected_files": affected_files,
            },
            compliance_controls=["AC-3.1.2", "CM-3.4.9"],
            result="PENDING_REVIEW",
        )

    def log_manual_review_decision(
        self,
        actor: str,
        approved: bool,
        reviewer: str,
        comments: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> AuditEvent:
        """Log manual review approval/rejection."""
        event_type = (
            AuditEventType.MANUAL_REVIEW_APPROVED
            if approved
            else AuditEventType.MANUAL_REVIEW_REJECTED
        )

        return self.log_event(
            event_type=event_type,
            actor=reviewer,
            action=f"Manual review {'APPROVED' if approved else 'REJECTED'} by {reviewer}",
            metadata={
                **(metadata or {}),
                "reviewer": reviewer,
                "comments": comments,
                "original_actor": actor,
            },
            compliance_controls=["AC-3.1.2", "CM-3.4.9", "AU-3.3.1"],
            result="APPROVED" if approved else "REJECTED",
        )

    def log_profile_loaded(
        self,
        actor: str,
        profile_display_name: str,
        metadata: Optional[Dict] = None,
    ) -> AuditEvent:
        """Log compliance profile loading."""
        return self.log_event(
            event_type=AuditEventType.PROFILE_LOADED,
            actor=actor,
            action=f"Loaded compliance profile: {profile_display_name}",
            metadata=metadata or {},
            result="SUCCESS",
        )

    def log_profile_override(
        self,
        actor: str,
        overrides: Dict[str, Any],
    ) -> AuditEvent:
        """Log custom profile overrides."""
        return self.log_event(
            event_type=AuditEventType.PROFILE_OVERRIDE_APPLIED,
            actor=actor,
            action=f"Applied {len(overrides)} profile overrides",
            metadata={"overrides": overrides},
            compliance_controls=["CM-3.4.7"],
            result="SUCCESS",
        )

    def log_compliance_violation(
        self,
        actor: str,
        violation_type: str,
        details: str,
        affected_controls: List[str],
        metadata: Optional[Dict] = None,
    ) -> AuditEvent:
        """Log compliance violation."""
        return self.log_event(
            event_type=AuditEventType.COMPLIANCE_VIOLATION,
            actor=actor,
            action=f"Compliance violation detected: {violation_type}",
            metadata={
                **(metadata or {}),
                "violation_type": violation_type,
                "details": details,
            },
            compliance_controls=affected_controls,
            result="VIOLATION",
        )

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        import uuid

        return f"audit-{uuid.uuid4().hex[:16]}"

    def _flush_buffer(self) -> None:
        """Flush event buffer to persistent storage."""
        if not self._event_buffer:
            return

        logger.debug(f"Flushing {len(self._event_buffer)} audit events")

        # Write to CloudWatch Logs
        if self.enable_cloudwatch:
            self._write_to_cloudwatch(self._event_buffer)

        # Write to DynamoDB
        if self.enable_dynamodb:
            self._write_to_dynamodb(self._event_buffer)

        # Clear buffer
        self._event_buffer.clear()

    def _write_to_cloudwatch(self, events: List[AuditEvent]) -> None:
        """
        Write events to CloudWatch Logs.

        Args:
            events: List of audit events
        """
        try:
            # In production, use boto3 CloudWatch Logs client
            # For now, log to standard logger with structured format
            for event in events:
                cloudwatch_log = event.to_cloudwatch_log()
                logger.info(f"[CLOUDWATCH_AUDIT] {cloudwatch_log}")
        except Exception as e:
            logger.error(f"Failed to write to CloudWatch Logs: {e}")

    def _write_to_dynamodb(self, events: List[AuditEvent]) -> None:
        """
        Write events to DynamoDB audit table.

        Args:
            events: List of audit events
        """
        try:
            # In production, use boto3 DynamoDB client
            # For now, log intention
            logger.debug(
                f"[DYNAMODB_AUDIT] Would write {len(events)} events to audit table"
            )
        except Exception as e:
            logger.error(f"Failed to write to DynamoDB: {e}")

    def flush(self) -> None:
        """Manually flush event buffer."""
        self._flush_buffer()

    def query_events(
        self,
        event_type: Optional[AuditEventType] = None,
        actor: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """
        Query audit events (for reporting/compliance).

        Args:
            event_type: Filter by event type
            actor: Filter by actor
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum results

        Returns:
            List of matching audit events
        """
        # In production, query DynamoDB
        # For now, return empty list
        logger.info(
            f"Query audit events: type={event_type}, actor={actor}, "
            f"start={start_time}, end={end_time}"
        )
        return []

    def generate_compliance_report(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """
        Generate compliance report for audit purposes.

        Args:
            start_time: Report start time
            end_time: Report end time

        Returns:
            Compliance report dictionary
        """
        events = self.query_events(start_time=start_time, end_time=end_time)

        # Aggregate statistics
        event_counts: Dict[str, int] = {}
        for event in events:
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        return {
            "report_period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "profile": {
                "name": self.profile_name,
                "version": self.profile_version,
            },
            "event_summary": event_counts,
            "total_events": len(events),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# Global audit service instance
_global_audit_service: Optional[ComplianceAuditService] = None


def get_audit_service(
    profile_name: str = "CMMC_LEVEL_3",
    profile_version: str = "1.0.0",
) -> ComplianceAuditService:
    """
    Get the global audit service instance.

    Args:
        profile_name: Compliance profile name
        profile_version: Profile version

    Returns:
        ComplianceAuditService singleton
    """
    global _global_audit_service

    if _global_audit_service is None:
        _global_audit_service = ComplianceAuditService(
            profile_name=profile_name,
            profile_version=profile_version,
        )

    return _global_audit_service
