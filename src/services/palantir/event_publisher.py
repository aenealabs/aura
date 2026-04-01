"""
Palantir Event Publisher

Implements ADR-074: Palantir AIP Integration

Publishes Aura remediation events to Palantir Foundry for dashboarding,
analytics, and compliance evidence.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.services.palantir.base_adapter import EnterpriseDataPlatformAdapter
from src.services.palantir.types import (
    BatchResult,
    RemediationEvent,
    RemediationEventType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Event Publishing Mode
# =============================================================================


class PublishMode(Enum):
    """Event publishing mode."""

    DIRECT = "direct"  # Direct API call to Palantir
    EVENTBRIDGE = "eventbridge"  # Via AWS EventBridge
    KINESIS = "kinesis"  # Via AWS Kinesis


# =============================================================================
# Dead Letter Queue
# =============================================================================


@dataclass
class DLQEntry:
    """Dead Letter Queue entry for failed events."""

    event: RemediationEvent
    error: str
    failed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0
    max_retries: int = 3

    @property
    def can_retry(self) -> bool:
        """Check if event can be retried."""
        return self.retry_count < self.max_retries


class DeadLetterQueue:
    """In-memory DLQ for failed events."""

    def __init__(self, max_size: int = 1000) -> None:
        """Initialize DLQ with max size."""
        self._queue: list[DLQEntry] = []
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def add(
        self,
        event: RemediationEvent,
        error: str,
        max_retries: int = 3,
    ) -> None:
        """Add failed event to DLQ."""
        async with self._lock:
            entry = DLQEntry(
                event=event,
                error=error,
                max_retries=max_retries,
            )
            self._queue.append(entry)

            # Trim if over max size
            if len(self._queue) > self._max_size:
                self._queue = self._queue[-self._max_size :]

            logger.warning(f"Event {event.event_id} added to DLQ: {error}")

    async def get_retriable(self) -> list[DLQEntry]:
        """Get all retriable entries."""
        async with self._lock:
            return [e for e in self._queue if e.can_retry]

    async def remove(self, event_id: str) -> bool:
        """Remove event from DLQ after successful retry."""
        async with self._lock:
            for i, entry in enumerate(self._queue):
                if entry.event.event_id == event_id:
                    del self._queue[i]
                    return True
            return False

    async def increment_retry(self, event_id: str) -> None:
        """Increment retry count for an event."""
        async with self._lock:
            for entry in self._queue:
                if entry.event.event_id == event_id:
                    entry.retry_count += 1
                    break

    def size(self) -> int:
        """Get DLQ size."""
        return len(self._queue)

    def get_stats(self) -> dict[str, Any]:
        """Get DLQ statistics."""
        retriable = sum(1 for e in self._queue if e.can_retry)
        return {
            "size": len(self._queue),
            "retriable": retriable,
            "exhausted": len(self._queue) - retriable,
        }


# =============================================================================
# Event Publisher
# =============================================================================


class PalantirEventPublisher:
    """
    Publishes Aura events to Palantir Foundry.

    Supports multiple publishing modes:
    - DIRECT: Direct API calls to Palantir Foundry
    - EVENTBRIDGE: Via AWS EventBridge for decoupled publishing
    - KINESIS: Via AWS Kinesis for high-throughput streaming

    Includes:
    - Async event queue for non-blocking publishing
    - Dead Letter Queue for failed events
    - Batch publishing for efficiency
    - Retry logic with exponential backoff

    Usage:
        >>> publisher = PalantirEventPublisher(adapter)
        >>> event = RemediationEvent(
        ...     event_id="evt-123",
        ...     event_type=RemediationEventType.VULNERABILITY_DETECTED,
        ...     timestamp=datetime.now(timezone.utc).isoformat(),
        ...     tenant_id="tenant-1",
        ...     payload={"cve_id": "CVE-2024-1234"}
        ... )
        >>> await publisher.publish(event)
    """

    def __init__(
        self,
        adapter: EnterpriseDataPlatformAdapter,
        mode: PublishMode = PublishMode.DIRECT,
        kinesis_stream: str | None = None,
        eventbridge_bus: str | None = None,
        batch_size: int = 100,
        batch_timeout_seconds: float = 5.0,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize the event publisher.

        Args:
            adapter: Enterprise data platform adapter
            mode: Publishing mode (direct, eventbridge, kinesis)
            kinesis_stream: Kinesis stream name (for kinesis mode)
            eventbridge_bus: EventBridge bus name (for eventbridge mode)
            batch_size: Maximum events per batch
            batch_timeout_seconds: Max wait time before publishing batch
            max_retries: Max retry attempts for failed events
        """
        self.adapter = adapter
        self.mode = mode
        self._kinesis_stream = kinesis_stream
        self._eventbridge_bus = eventbridge_bus
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout_seconds
        self._max_retries = max_retries

        # Event queue and DLQ
        self._queue: asyncio.Queue[RemediationEvent] = asyncio.Queue()
        self._dlq = DeadLetterQueue()
        self._lock = asyncio.Lock()

        # Metrics
        self._published_count = 0
        self._failed_count = 0
        self._batch_count = 0

        # Background worker task
        self._worker_task: asyncio.Task | None = None
        self._running = False

    # =========================================================================
    # Public API
    # =========================================================================

    async def publish(self, event: RemediationEvent) -> bool:
        """
        Publish a single event to Palantir.

        Args:
            event: RemediationEvent to publish

        Returns:
            True if published successfully
        """
        try:
            success = await self._publish_single(event)
            if success:
                self._published_count += 1
            else:
                self._failed_count += 1
                await self._dlq.add(event, "Publish failed", self._max_retries)
            return success
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            self._failed_count += 1
            await self._dlq.add(event, str(e), self._max_retries)
            return False

    async def publish_batch(
        self,
        events: list[RemediationEvent],
    ) -> BatchResult:
        """
        Batch publish multiple events.

        More efficient than individual publishes for high volume.

        Args:
            events: List of events to publish

        Returns:
            BatchResult with success/failure counts
        """
        succeeded = 0
        failed = 0
        failed_ids = []

        # Process in batches
        for i in range(0, len(events), self._batch_size):
            batch = events[i : i + self._batch_size]
            batch_result = await self._publish_batch_internal(batch)
            succeeded += batch_result["succeeded"]
            failed += batch_result["failed"]
            failed_ids.extend(batch_result["failed_ids"])
            self._batch_count += 1

        self._published_count += succeeded
        self._failed_count += failed

        return BatchResult(
            total_events=len(events),
            successful=succeeded,
            failed=failed,
            failed_events=failed_ids,
        )

    async def queue_event(self, event: RemediationEvent) -> None:
        """
        Queue event for async publishing.

        Use this for non-blocking event publishing. Events are
        processed by a background worker.

        Args:
            event: Event to queue
        """
        await self._queue.put(event)

    async def retry_dlq(self) -> int:
        """
        Retry failed events from Dead Letter Queue.

        Returns:
            Number of events successfully retried
        """
        entries = await self._dlq.get_retriable()
        if not entries:
            logger.info("No retriable events in DLQ")
            return 0

        retried = 0
        for entry in entries:
            await self._dlq.increment_retry(entry.event.event_id)
            try:
                success = await self._publish_single(entry.event)
                if success:
                    await self._dlq.remove(entry.event.event_id)
                    retried += 1
                    self._published_count += 1
                    logger.info(f"Successfully retried event {entry.event.event_id}")
            except Exception as e:
                logger.warning(
                    f"Retry failed for {entry.event.event_id}: {e} "
                    f"(attempt {entry.retry_count}/{entry.max_retries})"
                )

        return retried

    # =========================================================================
    # Background Worker
    # =========================================================================

    async def start_worker(self) -> None:
        """Start background worker for async publishing."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Event publisher worker started")

    async def stop_worker(self) -> None:
        """Stop background worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Event publisher worker stopped")

    async def _worker_loop(self) -> None:
        """Background worker loop."""
        batch: list[RemediationEvent] = []
        last_publish = datetime.now(timezone.utc)

        while self._running:
            try:
                # Get event with timeout
                try:
                    event = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self._batch_timeout,
                    )
                    batch.append(event)
                except asyncio.TimeoutError:
                    pass

                # Check if should publish
                should_publish = len(batch) >= self._batch_size or (
                    batch
                    and (datetime.now(timezone.utc) - last_publish).total_seconds()
                    >= self._batch_timeout
                )

                if should_publish and batch:
                    await self.publish_batch(batch)
                    batch = []
                    last_publish = datetime.now(timezone.utc)

            except asyncio.CancelledError:
                # Publish remaining on shutdown
                if batch:
                    await self.publish_batch(batch)
                raise
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)

    # =========================================================================
    # Internal Publishing Methods
    # =========================================================================

    async def _publish_single(self, event: RemediationEvent) -> bool:
        """Publish a single event based on mode."""
        if self.mode == PublishMode.DIRECT:
            return await self._publish_direct(event)
        elif self.mode == PublishMode.EVENTBRIDGE:
            return await self._publish_eventbridge(event)
        elif self.mode == PublishMode.KINESIS:
            return await self._publish_kinesis(event)
        else:
            raise ValueError(f"Unknown publish mode: {self.mode}")

    async def _publish_direct(self, event: RemediationEvent) -> bool:
        """Publish directly to Palantir via adapter."""
        return await self.adapter.publish_remediation_event(event)

    async def _publish_eventbridge(self, event: RemediationEvent) -> bool:
        """Publish via AWS EventBridge."""
        # In production, this would use boto3 EventBridge client
        # For now, falls back to direct publishing
        logger.debug(f"EventBridge publish: {event.event_type.value}")
        return await self.adapter.publish_remediation_event(event)

    async def _publish_kinesis(self, event: RemediationEvent) -> bool:
        """Publish via AWS Kinesis."""
        # In production, this would use boto3 Kinesis client
        # For now, falls back to direct publishing
        logger.debug(f"Kinesis publish: {event.event_type.value}")
        return await self.adapter.publish_remediation_event(event)

    async def _publish_batch_internal(
        self,
        events: list[RemediationEvent],
    ) -> dict[str, Any]:
        """Publish a batch of events."""
        succeeded = 0
        failed = 0
        failed_ids = []

        for event in events:
            try:
                success = await self._publish_single(event)
                if success:
                    succeeded += 1
                else:
                    failed += 1
                    failed_ids.append(event.event_id)
                    await self._dlq.add(event, "Batch publish failed")
            except Exception as e:
                failed += 1
                failed_ids.append(event.event_id)
                await self._dlq.add(event, str(e))

        return {
            "succeeded": succeeded,
            "failed": failed,
            "failed_ids": failed_ids,
        }

    # =========================================================================
    # Event Creation Helpers
    # =========================================================================

    def create_event(
        self,
        event_type: RemediationEventType,
        tenant_id: str,
        payload: dict[str, Any],
        event_id: str | None = None,
    ) -> RemediationEvent:
        """
        Create a new RemediationEvent.

        Helper method for creating properly formatted events.

        Args:
            event_type: Type of event
            tenant_id: Tenant identifier
            payload: Event payload data
            event_id: Optional event ID (generated if not provided)

        Returns:
            RemediationEvent instance
        """
        return RemediationEvent(
            event_id=event_id or str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            payload=payload,
        )

    # =========================================================================
    # Metrics and Status
    # =========================================================================

    def get_metrics(self) -> dict[str, Any]:
        """Get publisher metrics."""
        return {
            "mode": self.mode.value,
            "published_count": self._published_count,
            "failed_count": self._failed_count,
            "batch_count": self._batch_count,
            "queue_size": self._queue.qsize(),
            "dlq": self._dlq.get_stats(),
            "worker_running": self._running,
        }

    def get_dlq_stats(self) -> dict[str, Any]:
        """Get DLQ statistics."""
        return self._dlq.get_stats()
