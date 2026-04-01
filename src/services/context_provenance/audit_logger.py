"""
Project Aura - Provenance Audit Logger

Logs all provenance-related events for compliance.
Audit events are written to CloudWatch Logs, DynamoDB,
and EventBridge for downstream processing.

Security Rationale:
- Audit trail enables forensic analysis
- Multi-destination logging ensures durability
- EventBridge enables automated response
- Compliance with CMMC/SOX requirements

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .contracts import AuditRecord, ProvenanceAuditEvent

logger = logging.getLogger(__name__)


class ProvenanceAuditLogger:
    """
    Logs all provenance-related events for compliance.

    Audit events are written to:
    - CloudWatch Logs (immediate, searchable)
    - DynamoDB (long-term retention, queryable)
    - EventBridge (for downstream processing)

    Usage:
        audit_logger = ProvenanceAuditLogger(
            dynamodb_client=dynamodb,
            eventbridge_client=eventbridge,
        )
        audit_id = await audit_logger.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="abc123",
            details={"status": "passed"},
        )
    """

    def __init__(
        self,
        dynamodb_client: Optional[Any] = None,
        eventbridge_client: Optional[Any] = None,
        cloudwatch_logs_client: Optional[Any] = None,
        table_name: str = "aura-provenance-audit",
        log_group: str = "/aura/provenance/audit",
        event_bus: str = "aura-security-events",
        environment: str = "dev",
    ):
        """
        Initialize audit logger.

        Args:
            dynamodb_client: DynamoDB client
            eventbridge_client: EventBridge client
            cloudwatch_logs_client: CloudWatch Logs client
            table_name: DynamoDB table for audit records
            log_group: CloudWatch log group
            event_bus: EventBridge event bus name
            environment: Environment name
        """
        self.dynamodb = dynamodb_client
        self.eventbridge = eventbridge_client
        self.logs = cloudwatch_logs_client
        self.table_name = f"{table_name}-{environment}"
        self.log_group = f"{log_group}/{environment}"
        self.event_bus = event_bus
        self.environment = environment

        # In-memory audit log for testing
        self._in_memory_log: list[AuditRecord] = []

        # Log stream management
        self._log_stream_created = False
        self._current_log_stream: Optional[str] = None

        logger.debug(
            f"ProvenanceAuditLogger initialized "
            f"(table={self.table_name}, log_group={self.log_group})"
        )

    async def log(
        self,
        event_type: ProvenanceAuditEvent,
        chunk_id: str,
        details: dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Log a provenance audit event.

        Args:
            event_type: Type of audit event
            chunk_id: Content chunk ID
            details: Event details
            user_id: Optional user ID
            session_id: Optional session ID

        Returns:
            Audit record ID
        """
        audit_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        record = AuditRecord(
            audit_id=audit_id,
            event_type=event_type,
            chunk_id=chunk_id,
            timestamp=timestamp,
            details=details,
            user_id=user_id,
            session_id=session_id,
        )

        # Store in memory for testing
        self._in_memory_log.append(record)

        # Write to all destinations concurrently
        await self._write_to_dynamodb(record)
        await self._write_to_cloudwatch(record)

        # Send to EventBridge for security-critical events
        if event_type in (
            ProvenanceAuditEvent.INTEGRITY_FAILED,
            ProvenanceAuditEvent.ANOMALY_DETECTED,
            ProvenanceAuditEvent.CONTENT_QUARANTINED,
        ):
            await self._send_to_eventbridge(record)

        logger.info(f"Audit event logged: {event_type.value} for chunk {chunk_id}")

        return audit_id

    async def log_integrity_verified(
        self,
        chunk_id: str,
        hash_match: bool,
        hmac_valid: bool,
        user_id: Optional[str] = None,
    ) -> str:
        """Log an integrity verification event."""
        return await self.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id=chunk_id,
            details={
                "hash_match": hash_match,
                "hmac_valid": hmac_valid,
            },
            user_id=user_id,
        )

    async def log_integrity_failed(
        self,
        chunk_id: str,
        reason: str,
        expected_hash: Optional[str] = None,
        computed_hash: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Log an integrity failure event."""
        return await self.log(
            event_type=ProvenanceAuditEvent.INTEGRITY_FAILED,
            chunk_id=chunk_id,
            details={
                "reason": reason,
                "expected_hash": expected_hash[:16] + "..." if expected_hash else None,
                "computed_hash": computed_hash[:16] + "..." if computed_hash else None,
            },
            user_id=user_id,
        )

    async def log_trust_computed(
        self,
        chunk_id: str,
        trust_score: float,
        trust_level: str,
        components: dict[str, float],
        user_id: Optional[str] = None,
    ) -> str:
        """Log a trust score computation event."""
        return await self.log(
            event_type=ProvenanceAuditEvent.TRUST_COMPUTED,
            chunk_id=chunk_id,
            details={
                "trust_score": trust_score,
                "trust_level": trust_level,
                "components": components,
            },
            user_id=user_id,
        )

    async def log_anomaly_detected(
        self,
        chunk_id: str,
        anomaly_score: float,
        anomaly_types: list[str],
        suspicious_spans: Optional[list[tuple[int, int, str]]] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Log an anomaly detection event."""
        return await self.log(
            event_type=ProvenanceAuditEvent.ANOMALY_DETECTED,
            chunk_id=chunk_id,
            details={
                "anomaly_score": anomaly_score,
                "anomaly_types": anomaly_types,
                "suspicious_spans_count": (
                    len(suspicious_spans) if suspicious_spans else 0
                ),
            },
            user_id=user_id,
        )

    async def log_content_quarantined(
        self,
        chunk_id: str,
        reason: str,
        details: str,
        repository_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Log a content quarantine event."""
        return await self.log(
            event_type=ProvenanceAuditEvent.CONTENT_QUARANTINED,
            chunk_id=chunk_id,
            details={
                "reason": reason,
                "details": details,
                "repository_id": repository_id,
            },
            user_id=user_id,
        )

    async def log_content_served(
        self,
        chunk_id: str,
        trust_score: float,
        served_to: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Log a content serving event."""
        return await self.log(
            event_type=ProvenanceAuditEvent.CONTENT_SERVED,
            chunk_id=chunk_id,
            details={
                "trust_score": trust_score,
                "served_to": served_to,
            },
            session_id=session_id,
        )

    async def query_by_chunk(
        self,
        chunk_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit events for a specific chunk."""
        if self.dynamodb:
            try:
                key_condition = "chunk_id = :chunk_id"
                expression_values: dict[str, Any] = {":chunk_id": {"S": chunk_id}}
                expression_names: Optional[dict[str, str]] = None

                if start_time and end_time:
                    key_condition += " AND #ts BETWEEN :start AND :end"
                    expression_values[":start"] = {"S": start_time.isoformat()}
                    expression_values[":end"] = {"S": end_time.isoformat()}
                    expression_names = {"#ts": "timestamp"}

                query_params: dict[str, Any] = {
                    "TableName": self.table_name,
                    "IndexName": "chunk-id-index",
                    "KeyConditionExpression": key_condition,
                    "ExpressionAttributeValues": expression_values,
                    "Limit": limit,
                }

                if expression_names:
                    query_params["ExpressionAttributeNames"] = expression_names

                response = self.dynamodb.query(**query_params)
                return response.get("Items", [])
            except Exception as e:
                logger.error(f"Failed to query by chunk: {e}")
                return []

        # Fall back to in-memory
        records = [r for r in self._in_memory_log if r.chunk_id == chunk_id]
        if start_time:
            records = [r for r in records if r.timestamp >= start_time]
        if end_time:
            records = [r for r in records if r.timestamp <= end_time]
        return [r.to_dict() for r in records[:limit]]

    async def query_by_event_type(
        self,
        event_type: ProvenanceAuditEvent,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query recent audit events of a specific type."""
        if self.dynamodb:
            try:
                response = self.dynamodb.query(
                    TableName=self.table_name,
                    IndexName="event-type-index",
                    KeyConditionExpression="event_type = :type",
                    ExpressionAttributeValues={":type": {"S": event_type.value}},
                    Limit=limit,
                    ScanIndexForward=False,  # Most recent first
                )
                return response.get("Items", [])
            except Exception as e:
                logger.error(f"Failed to query by event type: {e}")
                return []

        # Fall back to in-memory
        records = [r for r in self._in_memory_log if r.event_type == event_type]
        return [r.to_dict() for r in records[-limit:]]

    async def get_recent_failures(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent integrity failures and anomaly detections."""
        failures = await self.query_by_event_type(
            ProvenanceAuditEvent.INTEGRITY_FAILED, limit // 2
        )
        anomalies = await self.query_by_event_type(
            ProvenanceAuditEvent.ANOMALY_DETECTED, limit // 2
        )
        return failures + anomalies

    async def _write_to_dynamodb(self, record: AuditRecord) -> None:
        """Write audit record to DynamoDB."""
        if not self.dynamodb:
            return

        try:
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    "audit_id": {"S": record.audit_id},
                    "timestamp": {"S": record.timestamp.isoformat()},
                    "event_type": {"S": record.event_type.value},
                    "chunk_id": {"S": record.chunk_id},
                    "details": {"S": json.dumps(record.details)},
                    "user_id": {"S": record.user_id or "system"},
                    "session_id": {"S": record.session_id or ""},
                },
            )
        except Exception as e:
            logger.error(f"Failed to write to DynamoDB: {e}")

    async def _write_to_cloudwatch(self, record: AuditRecord) -> None:
        """Write audit record to CloudWatch Logs."""
        if not self.logs:
            return

        try:
            # Ensure log stream exists
            if not self._log_stream_created:
                await self._ensure_log_stream()

            self.logs.put_log_events(
                logGroupName=self.log_group,
                logStreamName=self._current_log_stream or self._get_log_stream_name(),
                logEvents=[
                    {
                        "timestamp": int(record.timestamp.timestamp() * 1000),
                        "message": json.dumps(record.to_dict()),
                    }
                ],
            )
        except Exception as e:
            logger.error(f"Failed to write to CloudWatch: {e}")

    async def _send_to_eventbridge(self, record: AuditRecord) -> None:
        """Send security-critical event to EventBridge."""
        if not self.eventbridge:
            return

        try:
            self.eventbridge.put_events(
                Entries=[
                    {
                        "Source": "aura.context-provenance",
                        "DetailType": f"Context Provenance - {record.event_type.value}",
                        "Detail": json.dumps(record.to_dict()),
                        "EventBusName": self.event_bus,
                    }
                ]
            )
        except Exception as e:
            logger.error(f"Failed to send to EventBridge: {e}")

    async def _ensure_log_stream(self) -> None:
        """Ensure CloudWatch log stream exists."""
        if not self.logs:
            return

        try:
            stream_name = self._get_log_stream_name()
            self.logs.create_log_stream(
                logGroupName=self.log_group,
                logStreamName=stream_name,
            )
            self._current_log_stream = stream_name
            self._log_stream_created = True
        except Exception as e:
            # Stream might already exist
            if "ResourceAlreadyExistsException" in str(type(e).__name__):
                self._current_log_stream = self._get_log_stream_name()
                self._log_stream_created = True
            else:
                logger.warning(f"Failed to create log stream: {e}")

    def _get_log_stream_name(self) -> str:
        """Get current log stream name."""
        return f"provenance-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    def get_in_memory_logs(self) -> list[AuditRecord]:
        """Get in-memory audit logs (for testing)."""
        return self._in_memory_log.copy()

    def clear_in_memory_logs(self) -> int:
        """Clear in-memory audit logs (for testing)."""
        count = len(self._in_memory_log)
        self._in_memory_log.clear()
        return count


# =============================================================================
# Module-Level Functions
# =============================================================================


_audit_logger: Optional[ProvenanceAuditLogger] = None


def get_audit_logger() -> ProvenanceAuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = ProvenanceAuditLogger()
        logger.info("ProvenanceAuditLogger initialized with defaults")
    return _audit_logger


def configure_audit_logger(
    dynamodb_client: Optional[Any] = None,
    eventbridge_client: Optional[Any] = None,
    cloudwatch_logs_client: Optional[Any] = None,
    table_name: str = "aura-provenance-audit",
    log_group: str = "/aura/provenance/audit",
    event_bus: str = "aura-security-events",
    environment: str = "dev",
) -> ProvenanceAuditLogger:
    """Configure the global audit logger."""
    global _audit_logger
    _audit_logger = ProvenanceAuditLogger(
        dynamodb_client=dynamodb_client,
        eventbridge_client=eventbridge_client,
        cloudwatch_logs_client=cloudwatch_logs_client,
        table_name=table_name,
        log_group=log_group,
        event_bus=event_bus,
        environment=environment,
    )
    return _audit_logger


def reset_audit_logger() -> None:
    """Reset the global audit logger (for testing)."""
    global _audit_logger
    _audit_logger = None
