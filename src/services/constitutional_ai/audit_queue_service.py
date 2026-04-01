"""SQS-based async audit queue for Constitutional AI Phase 3.

Provides fire-and-forget audit logging to SQS queue for non-blocking
persistence as specified in ADR-063 Phase 3 (Optimization).

Key features:
- Fire-and-forget: Does not block on SQS response
- Graceful degradation: Logs errors but doesn't raise
- FIFO queue: Preserves audit record ordering
- DLQ support: Failed messages go to dead letter queue

The Lambda consumer (src/lambda/constitutional_audit/handler.py) persists
audit entries to DynamoDB for compliance reporting.
"""

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from mypy_boto3_sqs import SQSClient

logger = logging.getLogger(__name__)


class AuditQueueMode(Enum):
    """Operating modes for audit queue."""

    MOCK = "mock"  # In-memory queue for testing
    AWS = "aws"  # Real SQS queue
    DISABLED = "disabled"  # No audit logging


@dataclass
class AuditEntry:
    """Constitutional AI audit entry for SQS.

    Contains all information needed for compliance reporting and
    operational visibility into constitutional AI decisions.

    Attributes:
        timestamp: ISO format timestamp of the audit event
        agent_name: Name of the agent that generated the output
        operation_type: Type of operation being performed
        output_hash: SHA-256 hash of the output (first 16 chars)
        critique_performed: Whether constitutional critique was performed
        critique_summary: Summary of critique results (issues by severity)
        revision_performed: Whether output was revised
        revision_iterations: Number of revision iterations performed
        blocked: Whether output was blocked
        block_reason: Reason for blocking (if applicable)
        hitl_required: Whether HITL escalation was triggered
        hitl_request_id: ID of HITL request (if applicable)
        processing_time_ms: Total processing time in milliseconds
        autonomy_level: Autonomy level of the operation
        critique_tier: Which critique tier was applied
        principles_evaluated: Number of principles evaluated
        issues_found: Count of issues by severity
        cache_hit: Whether result came from cache
        fast_path_blocked: Whether fast-path guardrails blocked
    """

    timestamp: str
    agent_name: str
    operation_type: str
    output_hash: str
    critique_performed: bool = True
    critique_summary: Dict[str, Any] = field(default_factory=dict)
    revision_performed: bool = False
    revision_iterations: int = 0
    blocked: bool = False
    block_reason: Optional[str] = None
    hitl_required: bool = False
    hitl_request_id: Optional[str] = None
    processing_time_ms: float = 0.0
    autonomy_level: str = "COLLABORATIVE"
    critique_tier: str = "STANDARD"
    principles_evaluated: int = 0
    issues_found: Dict[str, int] = field(default_factory=dict)
    cache_hit: bool = False
    fast_path_blocked: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_sqs_message(self) -> str:
        """Serialize for SQS message body.

        Returns:
            JSON string suitable for SQS message body
        """
        return json.dumps(asdict(self), default=str)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation of the audit entry
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        """Create from dictionary.

        Args:
            data: Dictionary with audit entry fields

        Returns:
            AuditEntry instance
        """
        return cls(**data)


def create_audit_entry(
    agent_name: str,
    operation_type: str,
    output: str,
    critique_summary: Optional[Dict[str, Any]] = None,
    revision_performed: bool = False,
    revision_iterations: int = 0,
    blocked: bool = False,
    block_reason: Optional[str] = None,
    hitl_required: bool = False,
    hitl_request_id: Optional[str] = None,
    processing_time_ms: float = 0.0,
    autonomy_level: str = "COLLABORATIVE",
    critique_tier: str = "STANDARD",
    cache_hit: bool = False,
    fast_path_blocked: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditEntry:
    """Create an audit entry with computed fields.

    Helper function to create AuditEntry with automatic timestamp
    and output hash computation.

    Args:
        agent_name: Name of the agent
        operation_type: Type of operation
        output: The output being audited
        critique_summary: Optional critique summary dict
        revision_performed: Whether revision occurred
        revision_iterations: Number of iterations
        blocked: Whether output was blocked
        block_reason: Reason for blocking
        hitl_required: Whether HITL was triggered
        hitl_request_id: HITL request ID
        processing_time_ms: Processing time
        autonomy_level: Autonomy level string
        critique_tier: Critique tier string
        cache_hit: Whether cache was hit
        fast_path_blocked: Whether fast-path blocked
        metadata: Additional metadata

    Returns:
        Populated AuditEntry instance
    """
    # Compute output hash
    output_hash = hashlib.sha256(output[:2000].encode("utf-8")).hexdigest()[:16]

    # Extract issue counts from critique summary
    issues_found = {}
    principles_evaluated = 0
    if critique_summary:
        issues_found = {
            "critical": critique_summary.get("critical_issues", 0),
            "high": critique_summary.get("high_issues", 0),
            "medium": critique_summary.get("medium_issues", 0),
            "low": critique_summary.get("low_issues", 0),
        }
        principles_evaluated = critique_summary.get("total_principles_evaluated", 0)

    return AuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent_name=agent_name,
        operation_type=operation_type,
        output_hash=output_hash,
        critique_performed=critique_summary is not None,
        critique_summary=critique_summary or {},
        revision_performed=revision_performed,
        revision_iterations=revision_iterations,
        blocked=blocked,
        block_reason=block_reason,
        hitl_required=hitl_required,
        hitl_request_id=hitl_request_id,
        processing_time_ms=processing_time_ms,
        autonomy_level=autonomy_level,
        critique_tier=critique_tier,
        principles_evaluated=principles_evaluated,
        issues_found=issues_found,
        cache_hit=cache_hit,
        fast_path_blocked=fast_path_blocked,
        metadata=metadata or {},
    )


class ConstitutionalAuditQueueService:
    """Fire-and-forget audit queue service for Constitutional AI.

    Sends audit entries to SQS queue without blocking the critical path.
    Uses asyncio.create_task for non-blocking sends.

    Attributes:
        mode: Operating mode (MOCK, AWS, DISABLED)
        queue_url: SQS queue URL (required for AWS mode)
    """

    def __init__(
        self,
        mode: AuditQueueMode = AuditQueueMode.MOCK,
        queue_url: Optional[str] = None,
        sqs_client: Optional["SQSClient"] = None,
    ):
        """Initialize the audit queue service.

        Args:
            mode: Operating mode
            queue_url: SQS queue URL (required for AWS mode)
            sqs_client: Pre-configured SQS client
        """
        self.mode = mode
        self.queue_url = queue_url or os.environ.get("CONSTITUTIONAL_AUDIT_QUEUE_URL")
        self._sqs = sqs_client

        # Mock queue for testing
        self._mock_queue: List[AuditEntry] = []

        # Metrics
        self._entries_queued = 0
        self._entries_failed = 0

        if mode == AuditQueueMode.AWS and not self.queue_url:
            logger.warning(
                "AuditQueueService AWS mode requires queue_url, "
                "falling back to MOCK mode"
            )
            self.mode = AuditQueueMode.MOCK

    async def send_audit_async(self, entry: AuditEntry) -> None:
        """Send audit entry to SQS (fire-and-forget).

        Does not block on SQS response. Errors are logged but not raised.
        This ensures audit logging never impacts the critical path latency.

        Args:
            entry: AuditEntry to send to queue
        """
        if self.mode == AuditQueueMode.DISABLED:
            return

        if self.mode == AuditQueueMode.MOCK:
            self._mock_queue.append(entry)
            self._entries_queued += 1
            logger.debug(
                f"Mock audit queued: {entry.agent_name}/{entry.operation_type}"
            )
            return

        # AWS mode: Fire-and-forget using create_task
        try:
            asyncio.create_task(self._send_to_sqs(entry))
        except Exception as e:
            self._entries_failed += 1
            logger.warning(f"Failed to queue audit entry: {e}")

    async def _send_to_sqs(self, entry: AuditEntry) -> None:
        """Actual SQS send (runs in background).

        Args:
            entry: AuditEntry to send
        """
        if not self._sqs:
            logger.error("SQS client not configured")
            self._entries_failed += 1
            return

        try:
            # Use asyncio.to_thread for the blocking boto3 call
            await asyncio.to_thread(
                self._sqs.send_message,
                QueueUrl=self.queue_url,
                MessageBody=entry.to_sqs_message(),
                MessageGroupId="constitutional-audit",
                MessageDeduplicationId=f"{entry.timestamp}-{entry.output_hash}",
            )
            self._entries_queued += 1
            logger.debug(
                f"Audit entry sent to SQS: {entry.agent_name}/{entry.operation_type}"
            )

        except Exception as e:
            self._entries_failed += 1
            logger.error(f"SQS audit send failed: {e}")

    def send_audit_sync(self, entry: AuditEntry) -> bool:
        """Synchronous audit send for Lambda/non-async contexts.

        Unlike send_audit_async, this blocks until the send completes.
        Use sparingly, as it adds latency to the critical path.

        Args:
            entry: AuditEntry to send

        Returns:
            True if sent successfully, False otherwise
        """
        if self.mode == AuditQueueMode.DISABLED:
            return True

        if self.mode == AuditQueueMode.MOCK:
            self._mock_queue.append(entry)
            self._entries_queued += 1
            return True

        if not self._sqs:
            logger.error("SQS client not configured")
            self._entries_failed += 1
            return False

        try:
            self._sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=entry.to_sqs_message(),
                MessageGroupId="constitutional-audit",
                MessageDeduplicationId=f"{entry.timestamp}-{entry.output_hash}",
            )
            self._entries_queued += 1
            return True

        except Exception as e:
            self._entries_failed += 1
            logger.error(f"SQS audit send failed: {e}")
            return False

    def get_mock_queue(self) -> List[AuditEntry]:
        """Get entries from mock queue (for testing).

        Returns:
            List of AuditEntry objects in mock queue
        """
        return self._mock_queue.copy()

    def clear_mock_queue(self) -> None:
        """Clear the mock queue (for testing)."""
        self._mock_queue.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dictionary with queue metrics
        """
        return {
            "mode": self.mode.value,
            "entries_queued": self._entries_queued,
            "entries_failed": self._entries_failed,
            "queue_url": self.queue_url if self.mode == AuditQueueMode.AWS else None,
            "mock_queue_size": (
                len(self._mock_queue) if self.mode == AuditQueueMode.MOCK else 0
            ),
        }

    def is_enabled(self) -> bool:
        """Check if audit queue is enabled.

        Returns:
            True if mode is not DISABLED
        """
        return self.mode != AuditQueueMode.DISABLED
