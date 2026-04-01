"""Tests for GPU Queue Dispatcher.

Tests job dispatch worker and integration with queue engine per ADR-061 Phase 2.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.gpu_scheduler.models import (
    EmbeddingJobConfig,
    GPUJob,
    GPUJobPriority,
    GPUJobStatus,
    GPUJobType,
    PreemptionEvent,
    PreemptionReason,
    QueuedJob,
)
from src.services.gpu_scheduler.queue_dispatcher import (
    MAX_BATCH_SIZE,
    POLL_INTERVAL_SECONDS,
    SQS_WAIT_TIME_SECONDS,
    STARVATION_CHECK_INTERVAL_SECONDS,
    GPUQueueDispatcher,
    get_queue_dispatcher,
    init_queue_dispatcher,
)
from src.services.gpu_scheduler.queue_engine import GPUQueueEngine


@pytest.fixture
def mock_scheduler_service():
    """Create mock GPU scheduler service."""
    service = MagicMock()
    service.get_job = AsyncMock(return_value=None)
    service.update_job_status = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_queue_engine():
    """Create mock queue engine."""
    engine = MagicMock(spec=GPUQueueEngine)
    engine.enqueue = MagicMock()
    engine.dequeue = MagicMock(return_value=None)
    engine.can_start_job = MagicMock(return_value=True)
    engine.mark_job_running = MagicMock()
    engine.mark_job_completed = MagicMock()
    engine.find_preemption_candidate = MagicMock(return_value=None)
    engine.record_preemption = MagicMock()
    engine.promote_starved_jobs = MagicMock(return_value=[])
    engine.size = MagicMock(return_value=0)
    engine._running_by_org = {}
    return engine


@pytest.fixture
def mock_preemption_manager():
    """Create mock preemption manager."""
    manager = MagicMock()
    manager.preempt_job = AsyncMock(
        return_value=PreemptionEvent(
            event_id="event-123",
            preempted_job_id="preempted-job",
            preempting_job_id="preempting-job",
            organization_id="org-test",
            reason=PreemptionReason.HIGH_PRIORITY_JOB,
            checkpoint_saved=True,
            preempted_at=datetime.now(timezone.utc),
            re_queued=True,
            priority_boost_applied=True,
            original_priority=GPUJobPriority.LOW,
            new_priority=GPUJobPriority.NORMAL,
        )
    )
    return manager


@pytest.fixture
def mock_k8s_client():
    """Create mock Kubernetes client."""
    client = MagicMock()
    client.create_job = AsyncMock(return_value="k8s-job-123")
    client.delete_job = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_sqs_client():
    """Create mock SQS client."""
    client = MagicMock()
    client.receive_message = MagicMock(return_value={"Messages": []})
    client.delete_message = MagicMock()
    return client


@pytest.fixture
def queue_dispatcher(
    mock_scheduler_service,
    mock_queue_engine,
    mock_preemption_manager,
    mock_k8s_client,
    mock_sqs_client,
):
    """Create queue dispatcher with all mocked dependencies."""
    return GPUQueueDispatcher(
        scheduler_service=mock_scheduler_service,
        queue_engine=mock_queue_engine,
        preemption_manager=mock_preemption_manager,
        k8s_client=mock_k8s_client,
        sqs_client=mock_sqs_client,
        queue_url="https://sqs.us-east-1.amazonaws.com/123/queue.fifo",
        poll_interval=1,
        starvation_check_interval=5,
    )


class TestConstants:
    """Tests for module constants."""

    def test_poll_interval(self):
        """Test default poll interval."""
        assert POLL_INTERVAL_SECONDS == 5

    def test_starvation_check_interval(self):
        """Test starvation check interval."""
        assert STARVATION_CHECK_INTERVAL_SECONDS == 60

    def test_max_batch_size(self):
        """Test max batch size for SQS."""
        assert MAX_BATCH_SIZE == 10

    def test_sqs_wait_time(self):
        """Test SQS long polling wait time."""
        assert SQS_WAIT_TIME_SECONDS == 20


class TestDispatcherInitialization:
    """Tests for dispatcher initialization."""

    def test_create_dispatcher(self, queue_dispatcher: GPUQueueDispatcher):
        """Test creating dispatcher with dependencies."""
        assert queue_dispatcher.service is not None
        assert queue_dispatcher.queue_engine is not None
        assert queue_dispatcher.preemption_manager is not None
        assert queue_dispatcher.k8s_client is not None
        assert queue_dispatcher.sqs_client is not None

    def test_create_dispatcher_minimal(self):
        """Test creating dispatcher with minimal config."""
        dispatcher = GPUQueueDispatcher()

        assert dispatcher.service is None
        assert dispatcher.queue_engine is None
        assert dispatcher._running is False

    def test_default_intervals(self):
        """Test default interval configuration."""
        dispatcher = GPUQueueDispatcher()

        assert dispatcher.poll_interval == POLL_INTERVAL_SECONDS
        assert dispatcher.starvation_check_interval == STARVATION_CHECK_INTERVAL_SECONDS


class TestSQSPolling:
    """Tests for SQS message polling."""

    @pytest.mark.asyncio
    async def test_poll_sqs_no_messages(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_sqs_client,
    ):
        """Test polling SQS when no messages available."""
        mock_sqs_client.receive_message.return_value = {"Messages": []}

        messages = await queue_dispatcher._poll_sqs()

        assert messages == []
        mock_sqs_client.receive_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_sqs_with_messages(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_sqs_client,
    ):
        """Test polling SQS with messages."""
        mock_sqs_client.receive_message.return_value = {
            "Messages": [
                {
                    "Body": json.dumps(
                        {"job_id": "job-123", "organization_id": "org-test"}
                    ),
                    "ReceiptHandle": "receipt-123",
                }
            ]
        }

        messages = await queue_dispatcher._poll_sqs()

        assert len(messages) == 1
        assert "Body" in messages[0]

    @pytest.mark.asyncio
    async def test_poll_sqs_error_handling(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_sqs_client,
    ):
        """Test SQS polling error handling."""
        mock_sqs_client.receive_message.side_effect = Exception("SQS error")

        messages = await queue_dispatcher._poll_sqs()

        assert messages == []

    @pytest.mark.asyncio
    async def test_poll_sqs_without_client(self):
        """Test polling without SQS client configured."""
        dispatcher = GPUQueueDispatcher()

        messages = await dispatcher._poll_sqs()

        assert messages == []


class TestSQSMessageProcessing:
    """Tests for SQS message processing."""

    @pytest.mark.asyncio
    async def test_process_sqs_message(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_scheduler_service,
        mock_queue_engine,
        sample_gpu_job: GPUJob,
    ):
        """Test processing a valid SQS message."""
        mock_scheduler_service.get_job.return_value = sample_gpu_job

        message = {
            "Body": json.dumps(
                {
                    "job_id": sample_gpu_job.job_id,
                    "organization_id": sample_gpu_job.organization_id,
                }
            ),
            "ReceiptHandle": "receipt-123",
        }

        await queue_dispatcher._process_sqs_message(message)

        mock_scheduler_service.get_job.assert_called_once_with(
            sample_gpu_job.organization_id,
            sample_gpu_job.job_id,
        )
        mock_queue_engine.enqueue.assert_called_once_with(sample_gpu_job)

    @pytest.mark.asyncio
    async def test_process_sqs_message_invalid(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_sqs_client,
    ):
        """Test processing invalid SQS message."""
        message = {
            "Body": json.dumps({}),  # Missing required fields
            "ReceiptHandle": "receipt-123",
        }

        await queue_dispatcher._process_sqs_message(message)

        # Should still delete invalid message
        mock_sqs_client.delete_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_sqs_message_job_not_found(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_scheduler_service,
        mock_queue_engine,
    ):
        """Test processing message for job not in DynamoDB."""
        mock_scheduler_service.get_job.return_value = None

        message = {
            "Body": json.dumps(
                {"job_id": "nonexistent", "organization_id": "org-test"}
            ),
            "ReceiptHandle": "receipt-123",
        }

        await queue_dispatcher._process_sqs_message(message)

        mock_queue_engine.enqueue.assert_not_called()


class TestJobDispatching:
    """Tests for job dispatching logic."""

    @pytest.mark.asyncio
    async def test_dispatch_ready_jobs(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_queue_engine,
        mock_scheduler_service,
        mock_k8s_client,
        sample_gpu_job: GPUJob,
    ):
        """Test dispatching jobs from queue."""
        queued_job = QueuedJob.from_gpu_job(
            sample_gpu_job,
            queued_at=datetime.now(timezone.utc),
        )

        mock_queue_engine.dequeue.side_effect = [queued_job, None]
        mock_queue_engine.can_start_job.return_value = True
        mock_scheduler_service.get_job.return_value = sample_gpu_job

        await queue_dispatcher._dispatch_ready_jobs()

        mock_k8s_client.create_job.assert_called_once_with(sample_gpu_job)

    @pytest.mark.asyncio
    async def test_dispatch_respects_concurrent_limits(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_queue_engine,
        mock_k8s_client,
        sample_gpu_job: GPUJob,
    ):
        """Test that dispatch respects concurrent limits."""
        queued_job = QueuedJob.from_gpu_job(
            sample_gpu_job,
            queued_at=datetime.now(timezone.utc),
        )

        mock_queue_engine.dequeue.return_value = queued_job
        mock_queue_engine.can_start_job.return_value = False  # At capacity

        await queue_dispatcher._dispatch_ready_jobs()

        # Should not start job when at capacity
        mock_k8s_client.create_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_job(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_scheduler_service,
        mock_k8s_client,
        mock_queue_engine,
        sample_gpu_job: GPUJob,
    ):
        """Test starting a single job."""
        queued_job = QueuedJob.from_gpu_job(
            sample_gpu_job,
            queued_at=datetime.now(timezone.utc),
        )
        mock_scheduler_service.get_job.return_value = sample_gpu_job

        await queue_dispatcher._start_job(queued_job)

        mock_k8s_client.create_job.assert_called_once_with(sample_gpu_job)
        mock_scheduler_service.update_job_status.assert_called_once()
        mock_queue_engine.mark_job_running.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_job_increments_count(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_scheduler_service,
        mock_k8s_client,
        sample_gpu_job: GPUJob,
    ):
        """Test that starting job increments dispatch count."""
        queued_job = QueuedJob.from_gpu_job(
            sample_gpu_job,
            queued_at=datetime.now(timezone.utc),
        )
        mock_scheduler_service.get_job.return_value = sample_gpu_job

        initial_count = queue_dispatcher._dispatch_count

        await queue_dispatcher._start_job(queued_job)

        assert queue_dispatcher._dispatch_count == initial_count + 1


class TestPreemption:
    """Tests for preemption handling."""

    @pytest.mark.asyncio
    async def test_handle_preemption_success(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_scheduler_service,
        mock_queue_engine,
        mock_preemption_manager,
        mock_k8s_client,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test successful preemption handling."""
        high_job = GPUJob(
            job_id="job-high",
            organization_id="org-test",
            user_id="user-test",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.HIGH,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )

        low_job = GPUJob(
            job_id="job-low",
            organization_id="org-other",
            user_id="user-test",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.LOW,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )

        high_queued = QueuedJob.from_gpu_job(
            high_job,
            queued_at=datetime.now(timezone.utc),
        )

        mock_queue_engine.find_preemption_candidate.return_value = "job-low"
        mock_scheduler_service.get_job.side_effect = [high_job, low_job, high_job]
        mock_queue_engine._running_by_org = {"org-other": {"job-low"}}

        await queue_dispatcher._handle_preemption(high_queued)

        mock_preemption_manager.preempt_job.assert_called_once()
        mock_queue_engine.record_preemption.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_preemption_no_candidate(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_queue_engine,
        mock_scheduler_service,
        mock_preemption_manager,
        sample_gpu_job: GPUJob,
    ):
        """Test preemption when no candidate available."""
        high_queued = QueuedJob.from_gpu_job(
            sample_gpu_job,
            queued_at=datetime.now(timezone.utc),
        )

        mock_queue_engine.find_preemption_candidate.return_value = None
        mock_scheduler_service.get_job.return_value = sample_gpu_job

        await queue_dispatcher._handle_preemption(high_queued)

        # Should re-queue the high priority job
        mock_queue_engine.enqueue.assert_called()
        mock_preemption_manager.preempt_job.assert_not_called()


class TestStarvationCheck:
    """Tests for starvation prevention."""

    @pytest.mark.asyncio
    async def test_check_starvation_promotes_jobs(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_queue_engine,
    ):
        """Test that starvation check promotes starved jobs."""
        # Set last check to be longer than interval ago
        queue_dispatcher._last_starvation_check = datetime.now(
            timezone.utc
        ) - timedelta(seconds=queue_dispatcher.starvation_check_interval + 1)

        mock_queue_engine.promote_starved_jobs.return_value = ["job-1", "job-2"]

        await queue_dispatcher._check_starvation()

        mock_queue_engine.promote_starved_jobs.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_starvation_skips_if_recent(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_queue_engine,
    ):
        """Test that starvation check skips if checked recently."""
        # Set last check to be recent
        queue_dispatcher._last_starvation_check = datetime.now(timezone.utc)

        await queue_dispatcher._check_starvation()

        mock_queue_engine.promote_starved_jobs.assert_not_called()


class TestDispatcherLifecycle:
    """Tests for dispatcher start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_stop_dispatcher(self, queue_dispatcher: GPUQueueDispatcher):
        """Test stopping the dispatcher."""
        queue_dispatcher._running = True

        await queue_dispatcher.stop()

        assert queue_dispatcher._running is False

    def test_get_stats(self, queue_dispatcher: GPUQueueDispatcher):
        """Test getting dispatcher statistics."""
        queue_dispatcher._dispatch_count = 10
        queue_dispatcher._error_count = 2

        stats = queue_dispatcher.get_stats()

        assert stats["dispatch_count"] == 10
        assert stats["error_count"] == 2
        assert "running" in stats
        assert "queue_size" in stats


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_queue_dispatcher_returns_same_instance(self):
        """Test singleton returns same instance."""
        # Reset singleton
        import src.services.gpu_scheduler.queue_dispatcher as qd_module

        qd_module._dispatcher = None

        dispatcher1 = get_queue_dispatcher()
        dispatcher2 = get_queue_dispatcher()

        assert dispatcher1 is dispatcher2

    def test_init_queue_dispatcher(
        self,
        mock_scheduler_service,
        mock_queue_engine,
        mock_preemption_manager,
        mock_k8s_client,
        mock_sqs_client,
    ):
        """Test initializing queue dispatcher with dependencies."""
        # Reset singleton
        import src.services.gpu_scheduler.queue_dispatcher as qd_module

        qd_module._dispatcher = None

        dispatcher = init_queue_dispatcher(
            scheduler_service=mock_scheduler_service,
            queue_engine=mock_queue_engine,
            preemption_manager=mock_preemption_manager,
            k8s_client=mock_k8s_client,
            sqs_client=mock_sqs_client,
            queue_url="https://sqs.us-east-1.amazonaws.com/123/queue.fifo",
        )

        assert dispatcher.service is mock_scheduler_service
        assert dispatcher.queue_engine is mock_queue_engine
        assert get_queue_dispatcher() is dispatcher


class TestFindRunningJob:
    """Tests for finding running jobs."""

    @pytest.mark.asyncio
    async def test_find_running_job(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_queue_engine,
        mock_scheduler_service,
        sample_gpu_job: GPUJob,
    ):
        """Test finding a running job by ID."""
        mock_queue_engine._running_by_org = {
            "org-test": {sample_gpu_job.job_id},
        }
        mock_scheduler_service.get_job.return_value = sample_gpu_job

        result = await queue_dispatcher._find_running_job(sample_gpu_job.job_id)

        assert result is not None
        assert result.job_id == sample_gpu_job.job_id

    @pytest.mark.asyncio
    async def test_find_running_job_not_found(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_queue_engine,
    ):
        """Test finding a job that's not running."""
        mock_queue_engine._running_by_org = {}

        result = await queue_dispatcher._find_running_job("nonexistent")

        assert result is None


class TestDeleteSQSMessage:
    """Tests for SQS message deletion."""

    @pytest.mark.asyncio
    async def test_delete_sqs_message(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_sqs_client,
    ):
        """Test deleting an SQS message."""
        await queue_dispatcher._delete_sqs_message("receipt-123")

        mock_sqs_client.delete_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_sqs_message_error(
        self,
        queue_dispatcher: GPUQueueDispatcher,
        mock_sqs_client,
    ):
        """Test error handling when deleting SQS message fails."""
        mock_sqs_client.delete_message.side_effect = Exception("Delete failed")

        # Should not raise - just log the error
        await queue_dispatcher._delete_sqs_message("receipt-123")

    @pytest.mark.asyncio
    async def test_delete_sqs_message_no_client(self):
        """Test delete without SQS client configured."""
        dispatcher = GPUQueueDispatcher()

        # Should not raise
        await dispatcher._delete_sqs_message("receipt-123")
