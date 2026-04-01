"""
Tests for Palantir Event Publisher

Tests event publishing, batching, DLQ, and retry logic.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.services.palantir.event_publisher import (
    DeadLetterQueue,
    DLQEntry,
    PalantirEventPublisher,
    PublishMode,
)
from src.services.palantir.types import RemediationEvent, RemediationEventType

# =============================================================================
# PublishMode Tests
# =============================================================================


class TestPublishMode:
    """Tests for PublishMode enum."""

    def test_publish_modes(self):
        """Test all publish modes."""
        assert PublishMode.DIRECT.value == "direct"
        assert PublishMode.EVENTBRIDGE.value == "eventbridge"
        assert PublishMode.KINESIS.value == "kinesis"


# =============================================================================
# DLQEntry Tests
# =============================================================================


class TestDLQEntry:
    """Tests for DLQEntry dataclass."""

    @pytest.fixture
    def sample_event(self) -> RemediationEvent:
        return RemediationEvent(
            event_id="evt-001",
            event_type=RemediationEventType.VULNERABILITY_DETECTED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tenant_id="tenant-001",
            payload={},
        )

    def test_create_entry(self, sample_event):
        """Test creating DLQ entry."""
        entry = DLQEntry(
            event=sample_event,
            error="Connection timeout",
        )
        assert entry.retry_count == 0
        assert entry.max_retries == 3
        assert entry.can_retry is True

    def test_can_retry_true(self, sample_event):
        """Test can_retry when retries available."""
        entry = DLQEntry(event=sample_event, error="Error", retry_count=2)
        assert entry.can_retry is True

    def test_can_retry_false(self, sample_event):
        """Test can_retry when retries exhausted."""
        entry = DLQEntry(event=sample_event, error="Error", retry_count=3)
        assert entry.can_retry is False


# =============================================================================
# DeadLetterQueue Tests
# =============================================================================


class TestDeadLetterQueue:
    """Tests for DeadLetterQueue."""

    @pytest.fixture
    def dlq(self) -> DeadLetterQueue:
        return DeadLetterQueue(max_size=100)

    @pytest.fixture
    def sample_event(self) -> RemediationEvent:
        return RemediationEvent(
            event_id="evt-001",
            event_type=RemediationEventType.PATCH_GENERATED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tenant_id="tenant-001",
            payload={},
        )

    @pytest.mark.asyncio
    async def test_add_event(self, dlq: DeadLetterQueue, sample_event):
        """Test adding event to DLQ."""
        await dlq.add(sample_event, "Test error")
        assert dlq.size() == 1

    @pytest.mark.asyncio
    async def test_add_event_max_size(self, sample_event):
        """Test DLQ respects max size."""
        dlq = DeadLetterQueue(max_size=2)
        for i in range(5):
            event = RemediationEvent(
                event_id=f"evt-{i}",
                event_type=RemediationEventType.VULNERABILITY_DETECTED,
                timestamp=datetime.now(timezone.utc).isoformat(),
                tenant_id="tenant-001",
                payload={},
            )
            await dlq.add(event, "Error")
        assert dlq.size() == 2

    @pytest.mark.asyncio
    async def test_get_retriable(self, dlq: DeadLetterQueue, sample_event):
        """Test getting retriable entries."""
        await dlq.add(sample_event, "Error", max_retries=3)
        entries = await dlq.get_retriable()
        assert len(entries) == 1
        assert entries[0].can_retry is True

    @pytest.mark.asyncio
    async def test_get_retriable_none(self, dlq: DeadLetterQueue, sample_event):
        """Test getting retriable when none available."""
        entry = DLQEntry(
            event=sample_event, error="Error", retry_count=5, max_retries=3
        )
        dlq._queue.append(entry)
        entries = await dlq.get_retriable()
        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_remove(self, dlq: DeadLetterQueue, sample_event):
        """Test removing event from DLQ."""
        await dlq.add(sample_event, "Error")
        removed = await dlq.remove("evt-001")
        assert removed is True
        assert dlq.size() == 0

    @pytest.mark.asyncio
    async def test_remove_not_found(self, dlq: DeadLetterQueue):
        """Test removing non-existent event."""
        removed = await dlq.remove("evt-unknown")
        assert removed is False

    @pytest.mark.asyncio
    async def test_increment_retry(self, dlq: DeadLetterQueue, sample_event):
        """Test incrementing retry count."""
        await dlq.add(sample_event, "Error")
        await dlq.increment_retry("evt-001")
        entries = await dlq.get_retriable()
        assert entries[0].retry_count == 1

    def test_get_stats(self, dlq: DeadLetterQueue):
        """Test get_stats."""
        stats = dlq.get_stats()
        assert "size" in stats
        assert "retriable" in stats
        assert "exhausted" in stats


# =============================================================================
# PalantirEventPublisher Tests
# =============================================================================


class TestPalantirEventPublisher:
    """Tests for PalantirEventPublisher."""

    @pytest.mark.asyncio
    async def test_publish_success(self, event_publisher, sample_remediation_event):
        """Test successful event publishing."""
        result = await event_publisher.publish(sample_remediation_event)
        assert result is True
        assert event_publisher._published_count == 1

    @pytest.mark.asyncio
    async def test_publish_failure(self, event_publisher, sample_remediation_event):
        """Test failed event publishing."""
        event_publisher.adapter._should_fail = True

        # Mock the adapter to fail
        original_publish = event_publisher.adapter.publish_remediation_event
        event_publisher.adapter.publish_remediation_event = AsyncMock(
            return_value=False
        )

        result = await event_publisher.publish(sample_remediation_event)
        assert result is False
        assert event_publisher._failed_count == 1
        assert event_publisher._dlq.size() == 1

        event_publisher.adapter.publish_remediation_event = original_publish

    @pytest.mark.asyncio
    async def test_publish_batch(self, event_publisher):
        """Test batch publishing."""
        events = [
            RemediationEvent(
                event_id=f"evt-{i}",
                event_type=RemediationEventType.VULNERABILITY_DETECTED,
                timestamp=datetime.now(timezone.utc).isoformat(),
                tenant_id="tenant-001",
                payload={"index": i},
            )
            for i in range(5)
        ]

        result = await event_publisher.publish_batch(events)
        assert result.total_events == 5
        assert result.successful == 5
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_publish_batch_partial_failure(self, event_publisher):
        """Test batch with partial failures."""
        events = [
            RemediationEvent(
                event_id=f"evt-{i}",
                event_type=RemediationEventType.PATCH_GENERATED,
                timestamp=datetime.now(timezone.utc).isoformat(),
                tenant_id="tenant-001",
                payload={},
            )
            for i in range(3)
        ]

        # Make publishing fail for some events
        call_count = [0]
        original_publish = event_publisher._publish_single

        async def mock_publish(event):
            call_count[0] += 1
            if call_count[0] == 2:
                return False
            return True

        event_publisher._publish_single = mock_publish

        result = await event_publisher.publish_batch(events)
        assert result.successful == 2
        assert result.failed == 1

        event_publisher._publish_single = original_publish

    @pytest.mark.asyncio
    async def test_queue_event(self, event_publisher, sample_remediation_event):
        """Test queueing event."""
        await event_publisher.queue_event(sample_remediation_event)
        assert event_publisher._queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_retry_dlq_success(self, event_publisher, sample_remediation_event):
        """Test successful DLQ retry."""
        # Add event to DLQ
        await event_publisher._dlq.add(sample_remediation_event, "Initial error")

        retried = await event_publisher.retry_dlq()
        assert retried == 1
        assert event_publisher._dlq.size() == 0

    @pytest.mark.asyncio
    async def test_retry_dlq_empty(self, event_publisher):
        """Test retry when DLQ is empty."""
        retried = await event_publisher.retry_dlq()
        assert retried == 0


# =============================================================================
# Event Creation Helper Tests
# =============================================================================


class TestEventCreationHelper:
    """Tests for create_event helper method."""

    def test_create_event(self, event_publisher):
        """Test creating event."""
        event = event_publisher.create_event(
            event_type=RemediationEventType.SANDBOX_VALIDATED,
            tenant_id="tenant-001",
            payload={"sandbox_id": "sandbox-001"},
        )
        assert event.event_type == RemediationEventType.SANDBOX_VALIDATED
        assert event.tenant_id == "tenant-001"
        assert event.payload["sandbox_id"] == "sandbox-001"
        assert event.event_id is not None

    def test_create_event_with_id(self, event_publisher):
        """Test creating event with specified ID."""
        event = event_publisher.create_event(
            event_type=RemediationEventType.REMEDIATION_COMPLETE,
            tenant_id="tenant-001",
            payload={},
            event_id="custom-id-001",
        )
        assert event.event_id == "custom-id-001"


# =============================================================================
# Metrics Tests
# =============================================================================


class TestMetrics:
    """Tests for publisher metrics."""

    @pytest.mark.asyncio
    async def test_get_metrics(self, event_publisher, sample_remediation_event):
        """Test get_metrics returns expected structure."""
        await event_publisher.publish(sample_remediation_event)

        metrics = event_publisher.get_metrics()
        assert metrics["mode"] == "direct"
        assert metrics["published_count"] == 1
        assert "queue_size" in metrics
        assert "dlq" in metrics

    def test_get_dlq_stats(self, event_publisher):
        """Test get_dlq_stats."""
        stats = event_publisher.get_dlq_stats()
        assert "size" in stats
        assert "retriable" in stats


# =============================================================================
# Background Worker Tests
# =============================================================================


class TestBackgroundWorker:
    """Tests for background worker."""

    @pytest.mark.asyncio
    async def test_start_worker(self, event_publisher):
        """Test starting worker."""
        await event_publisher.start_worker()
        assert event_publisher._running is True
        assert event_publisher._worker_task is not None
        await event_publisher.stop_worker()

    @pytest.mark.asyncio
    async def test_stop_worker(self, event_publisher):
        """Test stopping worker."""
        await event_publisher.start_worker()
        await event_publisher.stop_worker()
        assert event_publisher._running is False

    @pytest.mark.asyncio
    async def test_worker_processes_queue(
        self, event_publisher, sample_remediation_event
    ):
        """Test worker processes queued events."""
        await event_publisher.start_worker()
        await event_publisher.queue_event(sample_remediation_event)

        # Give worker time to process - batch timeout is 5s, use shorter wait
        await asyncio.sleep(6)

        await event_publisher.stop_worker()
        # Event should be processed (queue empty)
        assert event_publisher._queue.qsize() == 0


# =============================================================================
# Publish Mode Tests
# =============================================================================


class TestPublishModes:
    """Tests for different publish modes."""

    @pytest.mark.asyncio
    async def test_direct_mode(self, mock_adapter, sample_remediation_event):
        """Test direct publishing mode."""
        publisher = PalantirEventPublisher(
            adapter=mock_adapter,
            mode=PublishMode.DIRECT,
        )
        result = await publisher.publish(sample_remediation_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_eventbridge_mode(self, mock_adapter, sample_remediation_event):
        """Test EventBridge publishing mode."""
        publisher = PalantirEventPublisher(
            adapter=mock_adapter,
            mode=PublishMode.EVENTBRIDGE,
            eventbridge_bus="test-bus",
        )
        # Currently falls back to direct, but should not error
        result = await publisher.publish(sample_remediation_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_kinesis_mode(self, mock_adapter, sample_remediation_event):
        """Test Kinesis publishing mode."""
        publisher = PalantirEventPublisher(
            adapter=mock_adapter,
            mode=PublishMode.KINESIS,
            kinesis_stream="test-stream",
        )
        # Currently falls back to direct, but should not error
        result = await publisher.publish(sample_remediation_event)
        assert result is True
