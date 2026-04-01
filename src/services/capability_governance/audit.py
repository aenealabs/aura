"""
Project Aura - Capability Governance Audit Service

Audit logging service for capability checks, escalations, and violations.
Stores audit records in DynamoDB with configurable retention and sampling.

Security Rationale:
- Full audit trail enables forensic analysis
- Sampling reduces costs for high-volume SAFE operations
- Immutable DynamoDB records prevent tampering

Author: Project Aura Team
Created: 2026-01-26
"""

import asyncio
import logging
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from .contracts import (
    CapabilityApprovalResponse,
    CapabilityCheckResult,
    CapabilityDecision,
    CapabilityEscalationRequest,
    CapabilityViolation,
    ToolClassification,
)
from .registry import get_capability_registry

logger = logging.getLogger(__name__)


# =============================================================================
# Audit Configuration
# =============================================================================


@dataclass
class AuditConfig:
    """Configuration for audit logging."""

    # DynamoDB settings
    table_name: str = "aura-capability-audit"
    escalation_table_name: str = "aura-capability-escalations"
    violation_table_name: str = "aura-capability-violations"

    # Retention settings (TTL in seconds)
    audit_retention_days: int = 90
    escalation_retention_days: int = 365
    violation_retention_days: int = 365

    # Sampling rates by classification
    safe_sample_rate: float = 0.1  # 10% sampling for SAFE tools
    monitoring_sample_rate: float = 1.0  # 100% for MONITORING
    dangerous_sample_rate: float = 1.0  # 100% for DANGEROUS
    critical_sample_rate: float = 1.0  # 100% for CRITICAL

    # Batch settings
    batch_size: int = 25
    batch_flush_interval_seconds: float = 5.0

    # Async queue settings
    queue_max_size: int = 10000
    enable_async_writes: bool = True


# =============================================================================
# Audit Record Types
# =============================================================================


@dataclass
class AuditRecord:
    """
    Audit record for a capability check.

    Stored in DynamoDB for compliance and forensic analysis.
    """

    record_id: str
    timestamp: datetime
    agent_id: str
    agent_type: str
    tool_name: str
    action: str
    context: str
    decision: CapabilityDecision
    reason: str
    policy_version: str
    capability_source: str
    processing_time_ms: float
    parent_agent_id: Optional[str] = None
    execution_id: Optional[str] = None
    session_id: Optional[str] = None
    request_hash: str = ""
    sampled: bool = True

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        ttl_days = 90  # Default retention
        ttl_timestamp = int((self.timestamp.timestamp()) + (ttl_days * 24 * 60 * 60))

        return {
            "PK": {"S": f"AUDIT#{self.agent_id}"},
            "SK": {"S": f"{self.timestamp.isoformat()}#{self.record_id}"},
            "record_id": {"S": self.record_id},
            "timestamp": {"S": self.timestamp.isoformat()},
            "agent_id": {"S": self.agent_id},
            "agent_type": {"S": self.agent_type},
            "tool_name": {"S": self.tool_name},
            "action": {"S": self.action},
            "context": {"S": self.context},
            "decision": {"S": self.decision.value},
            "reason": {"S": self.reason},
            "policy_version": {"S": self.policy_version},
            "capability_source": {"S": self.capability_source},
            "processing_time_ms": {"N": str(self.processing_time_ms)},
            "request_hash": {"S": self.request_hash},
            "sampled": {"BOOL": self.sampled},
            "TTL": {"N": str(ttl_timestamp)},
            # Optional fields
            **(
                {"parent_agent_id": {"S": self.parent_agent_id}}
                if self.parent_agent_id
                else {}
            ),
            **({"execution_id": {"S": self.execution_id}} if self.execution_id else {}),
            **({"session_id": {"S": self.session_id}} if self.session_id else {}),
            # GSI for tool-based queries
            "GSI1PK": {"S": f"TOOL#{self.tool_name}"},
            "GSI1SK": {"S": f"{self.timestamp.isoformat()}#{self.agent_id}"},
            # GSI for decision-based queries
            "GSI2PK": {"S": f"DECISION#{self.decision.value}"},
            "GSI2SK": {"S": f"{self.timestamp.isoformat()}#{self.agent_id}"},
        }

    @classmethod
    def from_check_result(
        cls,
        result: CapabilityCheckResult,
        session_id: Optional[str] = None,
        sampled: bool = True,
    ) -> "AuditRecord":
        """Create audit record from capability check result."""
        return cls(
            record_id=str(uuid.uuid4()),
            timestamp=result.checked_at,
            agent_id=result.agent_id,
            agent_type=result.agent_type,
            tool_name=result.tool_name,
            action=result.action,
            context=result.context,
            decision=result.decision,
            reason=result.reason,
            policy_version=result.policy_version,
            capability_source=result.capability_source,
            processing_time_ms=result.processing_time_ms,
            parent_agent_id=result.parent_agent_id,
            execution_id=result.execution_id,
            session_id=session_id,
            request_hash=result.request_hash,
            sampled=sampled,
        )


# =============================================================================
# Audit Service
# =============================================================================


class CapabilityAuditService:
    """
    Audit logging service for capability governance.

    Handles:
    - Capability check auditing with sampling
    - Escalation request tracking
    - Violation recording
    - Async batch writes to DynamoDB

    Usage:
        audit_service = CapabilityAuditService()
        await audit_service.log_check(check_result)
        await audit_service.log_violation(violation)
    """

    def __init__(
        self,
        config: Optional[AuditConfig] = None,
        dynamodb_client: Optional[Any] = None,
    ):
        """
        Initialize the audit service.

        Args:
            config: Audit configuration
            dynamodb_client: Optional boto3 DynamoDB client (for testing)
        """
        self.config = config or AuditConfig()
        self._dynamodb = dynamodb_client
        self._registry = get_capability_registry()

        # Async write queue
        self._audit_queue: asyncio.Queue = asyncio.Queue(
            maxsize=self.config.queue_max_size
        )
        self._batch_buffer: list[AuditRecord] = []
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

        # Metrics
        self._records_logged = 0
        self._records_sampled_out = 0
        self._batch_writes = 0
        self._write_errors = 0

        logger.debug(
            f"CapabilityAuditService initialized "
            f"(table={self.config.table_name}, "
            f"async={self.config.enable_async_writes})"
        )

    async def start(self) -> None:
        """Start the async batch writer."""
        if self._running:
            return

        self._running = True
        if self.config.enable_async_writes:
            self._flush_task = asyncio.create_task(self._batch_flush_loop())
            logger.info("Audit service batch writer started")

    async def stop(self) -> None:
        """Stop the async batch writer and flush pending records."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Flush any remaining records
        await self._flush_batch()
        logger.info(
            f"Audit service stopped "
            f"(logged={self._records_logged}, "
            f"sampled_out={self._records_sampled_out})"
        )

    def _get_dynamodb_client(self) -> Any:
        """Get or create DynamoDB client."""
        if self._dynamodb is None:
            try:
                import boto3

                self._dynamodb = boto3.client("dynamodb")
            except ImportError:
                logger.warning("boto3 not available, audit logging disabled")
                return None
        return self._dynamodb

    def _should_sample(self, tool_name: str) -> bool:
        """
        Determine if this check should be sampled for audit.

        Args:
            tool_name: Name of the tool

        Returns:
            True if should be logged, False if sampled out
        """
        classification = self._registry.get_classification(tool_name)

        if classification == ToolClassification.SAFE:
            sample_rate = self.config.safe_sample_rate
        elif classification == ToolClassification.MONITORING:
            sample_rate = self.config.monitoring_sample_rate
        elif classification == ToolClassification.DANGEROUS:
            sample_rate = self.config.dangerous_sample_rate
        else:  # CRITICAL
            sample_rate = self.config.critical_sample_rate

        return random.random() < sample_rate

    async def log_check(
        self,
        result: CapabilityCheckResult,
        session_id: Optional[str] = None,
        force_log: bool = False,
    ) -> bool:
        """
        Log a capability check result.

        Args:
            result: The capability check result
            session_id: Optional session ID for correlation
            force_log: If True, bypass sampling

        Returns:
            True if logged, False if sampled out
        """
        # Always log denials, escalations, and audit-only decisions
        should_log = force_log or result.decision in (
            CapabilityDecision.DENY,
            CapabilityDecision.ESCALATE,
            CapabilityDecision.AUDIT_ONLY,
        )

        # Apply sampling for ALLOW decisions on SAFE tools
        if not should_log:
            if not self._should_sample(result.tool_name):
                self._records_sampled_out += 1
                return False

        record = AuditRecord.from_check_result(
            result,
            session_id=session_id,
            sampled=not force_log,
        )

        if self.config.enable_async_writes:
            try:
                self._audit_queue.put_nowait(record)
            except asyncio.QueueFull:
                logger.warning("Audit queue full, dropping record")
                return False
        else:
            await self._write_record(record)

        self._records_logged += 1
        return True

    def log_check_sync(
        self,
        result: CapabilityCheckResult,
        session_id: Optional[str] = None,
        force_log: bool = False,
    ) -> bool:
        """
        Synchronous version of log_check.

        Queues the record for async writing.

        Args:
            result: The capability check result
            session_id: Optional session ID
            force_log: Bypass sampling

        Returns:
            True if queued, False if sampled out or queue full
        """
        should_log = force_log or result.decision in (
            CapabilityDecision.DENY,
            CapabilityDecision.ESCALATE,
            CapabilityDecision.AUDIT_ONLY,
        )

        if not should_log and not self._should_sample(result.tool_name):
            self._records_sampled_out += 1
            return False

        record = AuditRecord.from_check_result(
            result,
            session_id=session_id,
            sampled=not force_log,
        )

        try:
            self._audit_queue.put_nowait(record)
            self._records_logged += 1
            return True
        except asyncio.QueueFull:
            logger.warning("Audit queue full, dropping record")
            return False

    async def log_escalation(
        self,
        request: CapabilityEscalationRequest,
    ) -> None:
        """
        Log an escalation request.

        Args:
            request: The escalation request
        """
        client = self._get_dynamodb_client()
        if not client:
            return

        ttl_days = self.config.escalation_retention_days
        ttl_timestamp = int(time.time()) + (ttl_days * 24 * 60 * 60)

        item = {
            "PK": {"S": f"ESCALATION#{request.agent_id}"},
            "SK": {"S": f"{request.created_at.isoformat()}#{request.request_id}"},
            "request_id": {"S": request.request_id},
            "agent_id": {"S": request.agent_id},
            "agent_type": {"S": request.agent_type},
            "requested_tool": {"S": request.requested_tool},
            "requested_action": {"S": request.requested_action},
            "context": {"S": request.context},
            "justification": {"S": request.justification},
            "task_description": {"S": request.task_description},
            "status": {"S": request.status},
            "priority": {"S": request.priority},
            "created_at": {"S": request.created_at.isoformat()},
            "TTL": {"N": str(ttl_timestamp)},
            # GSI for status-based queries
            "GSI1PK": {"S": f"STATUS#{request.status}"},
            "GSI1SK": {"S": f"{request.created_at.isoformat()}#{request.agent_id}"},
        }

        if request.parent_agent_id:
            item["parent_agent_id"] = {"S": request.parent_agent_id}
        if request.execution_id:
            item["execution_id"] = {"S": request.execution_id}
        if request.expires_at:
            item["expires_at"] = {"S": request.expires_at.isoformat()}

        try:
            client.put_item(
                TableName=self.config.escalation_table_name,
                Item=item,
            )
            logger.debug(f"Logged escalation: {request.request_id}")
        except Exception as e:
            logger.error(f"Failed to log escalation: {e}")
            self._write_errors += 1

    async def log_escalation_response(
        self,
        response: CapabilityApprovalResponse,
    ) -> None:
        """
        Log an escalation approval/denial response.

        Args:
            response: The approval response
        """
        client = self._get_dynamodb_client()
        if not client:
            return

        try:
            # Update the escalation record with response
            client.update_item(
                TableName=self.config.escalation_table_name,
                Key={
                    "PK": {"S": f"ESCALATION#{response.request_id}"},
                    # Note: This requires knowing the SK, which we may need to query first
                },
                UpdateExpression=(
                    "SET #status = :status, "
                    "approved = :approved, "
                    "approver_id = :approver, "
                    "approved_at = :approved_at, "
                    "#scope = :scope, "
                    "response_reason = :reason"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                    "#scope": "scope",
                },
                ExpressionAttributeValues={
                    ":status": {"S": "approved" if response.approved else "denied"},
                    ":approved": {"BOOL": response.approved},
                    ":approver": {"S": response.approver_id},
                    ":approved_at": {"S": response.approved_at.isoformat()},
                    ":scope": {"S": response.scope.value},
                    ":reason": {"S": response.reason or ""},
                },
            )
            logger.debug(
                f"Updated escalation {response.request_id}: "
                f"{'approved' if response.approved else 'denied'}"
            )
        except Exception as e:
            logger.error(f"Failed to log escalation response: {e}")
            self._write_errors += 1

    async def log_violation(
        self,
        violation: CapabilityViolation,
    ) -> None:
        """
        Log a capability violation.

        Args:
            violation: The violation record
        """
        client = self._get_dynamodb_client()
        if not client:
            return

        ttl_days = self.config.violation_retention_days
        ttl_timestamp = int(time.time()) + (ttl_days * 24 * 60 * 60)

        item = {
            "PK": {"S": f"VIOLATION#{violation.agent_id}"},
            "SK": {
                "S": f"{violation.occurred_at.isoformat()}#{violation.violation_id}"
            },
            "violation_id": {"S": violation.violation_id},
            "agent_id": {"S": violation.agent_id},
            "agent_type": {"S": violation.agent_type},
            "tool_name": {"S": violation.tool_name},
            "action": {"S": violation.action},
            "context": {"S": violation.context},
            "decision": {"S": violation.decision.value},
            "reason": {"S": violation.reason},
            "occurred_at": {"S": violation.occurred_at.isoformat()},
            "severity": {"S": violation.severity},
            "acknowledged": {"BOOL": violation.acknowledged},
            "TTL": {"N": str(ttl_timestamp)},
            # GSI for severity-based queries
            "GSI1PK": {"S": f"SEVERITY#{violation.severity}"},
            "GSI1SK": {
                "S": f"{violation.occurred_at.isoformat()}#{violation.agent_id}"
            },
        }

        if violation.parent_agent_id:
            item["parent_agent_id"] = {"S": violation.parent_agent_id}
        if violation.execution_id:
            item["execution_id"] = {"S": violation.execution_id}

        try:
            client.put_item(
                TableName=self.config.violation_table_name,
                Item=item,
            )
            logger.warning(
                f"Logged violation: {violation.violation_id} "
                f"(agent={violation.agent_id}, tool={violation.tool_name}, "
                f"severity={violation.severity})"
            )
        except Exception as e:
            logger.error(f"Failed to log violation: {e}")
            self._write_errors += 1

    async def _write_record(self, record: AuditRecord) -> None:
        """Write a single audit record to DynamoDB."""
        client = self._get_dynamodb_client()
        if not client:
            return

        try:
            client.put_item(
                TableName=self.config.table_name,
                Item=record.to_dynamodb_item(),
            )
        except Exception as e:
            logger.error(f"Failed to write audit record: {e}")
            self._write_errors += 1

    async def _batch_flush_loop(self) -> None:
        """Background task to flush audit records in batches."""
        while self._running:
            try:
                # Collect records until batch size or timeout
                start_time = time.time()
                while len(self._batch_buffer) < self.config.batch_size:
                    remaining = self.config.batch_flush_interval_seconds - (
                        time.time() - start_time
                    )
                    if remaining <= 0:
                        break
                    try:
                        record = await asyncio.wait_for(
                            self._audit_queue.get(),
                            timeout=remaining,
                        )
                        self._batch_buffer.append(record)
                    except asyncio.TimeoutError:
                        break

                # Flush the batch
                if self._batch_buffer:
                    await self._flush_batch()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch flush error: {e}")
                await asyncio.sleep(1.0)

    async def _flush_batch(self) -> None:
        """Flush the current batch buffer to DynamoDB."""
        if not self._batch_buffer:
            return

        client = self._get_dynamodb_client()
        if not client:
            self._batch_buffer.clear()
            return

        # Prepare batch write request
        items = [
            {"PutRequest": {"Item": record.to_dynamodb_item()}}
            for record in self._batch_buffer
        ]

        try:
            # DynamoDB BatchWriteItem has a 25-item limit
            for i in range(0, len(items), 25):
                batch = items[i : i + 25]
                response = client.batch_write_item(
                    RequestItems={self.config.table_name: batch}
                )

                # Handle unprocessed items
                unprocessed = response.get("UnprocessedItems", {})
                if unprocessed:
                    logger.warning(
                        f"Unprocessed audit items: {len(unprocessed.get(self.config.table_name, []))}"
                    )

            self._batch_writes += 1
            logger.debug(f"Flushed {len(self._batch_buffer)} audit records")

        except Exception as e:
            logger.error(f"Batch write failed: {e}")
            self._write_errors += 1

        self._batch_buffer.clear()

    async def query_agent_audit(
        self,
        agent_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query audit records for an agent.

        Args:
            agent_id: Agent ID to query
            start_time: Optional start time filter
            end_time: Optional end time filter
            limit: Maximum records to return

        Returns:
            List of audit records
        """
        client = self._get_dynamodb_client()
        if not client:
            return []

        key_condition = "PK = :pk"
        expression_values = {":pk": {"S": f"AUDIT#{agent_id}"}}

        if start_time and end_time:
            key_condition += " AND SK BETWEEN :start AND :end"
            expression_values[":start"] = {"S": start_time.isoformat()}
            expression_values[":end"] = {"S": end_time.isoformat()}
        elif start_time:
            key_condition += " AND SK >= :start"
            expression_values[":start"] = {"S": start_time.isoformat()}
        elif end_time:
            key_condition += " AND SK <= :end"
            expression_values[":end"] = {"S": end_time.isoformat()}

        try:
            response = client.query(
                TableName=self.config.table_name,
                KeyConditionExpression=key_condition,
                ExpressionAttributeValues=expression_values,
                Limit=limit,
                ScanIndexForward=False,  # Most recent first
            )
            return response.get("Items", [])
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []

    async def query_violations(
        self,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query violation records.

        Args:
            severity: Optional severity filter (low, medium, high, critical)
            limit: Maximum records to return

        Returns:
            List of violation records
        """
        client = self._get_dynamodb_client()
        if not client:
            return []

        try:
            if severity:
                response = client.query(
                    TableName=self.config.violation_table_name,
                    IndexName="GSI1",
                    KeyConditionExpression="GSI1PK = :pk",
                    ExpressionAttributeValues={":pk": {"S": f"SEVERITY#{severity}"}},
                    Limit=limit,
                    ScanIndexForward=False,
                )
            else:
                response = client.scan(
                    TableName=self.config.violation_table_name,
                    Limit=limit,
                )
            return response.get("Items", [])
        except Exception as e:
            logger.error(f"Query violations failed: {e}")
            return []

    def get_metrics(self) -> dict[str, Any]:
        """Get audit service metrics."""
        return {
            "records_logged": self._records_logged,
            "records_sampled_out": self._records_sampled_out,
            "batch_writes": self._batch_writes,
            "write_errors": self._write_errors,
            "queue_size": self._audit_queue.qsize(),
            "buffer_size": len(self._batch_buffer),
        }


# =============================================================================
# Global Service Singleton
# =============================================================================

_audit_service: Optional[CapabilityAuditService] = None


def get_audit_service() -> CapabilityAuditService:
    """Get the global audit service instance."""
    global _audit_service
    if _audit_service is None:
        _audit_service = CapabilityAuditService()
    return _audit_service


def reset_audit_service() -> None:
    """Reset the global audit service (for testing)."""
    global _audit_service
    _audit_service = None
