"""Tests for GPU Queue Engine.

Tests priority queue management, fairness scheduling, and starvation prevention
per ADR-061 Phase 2.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.services.gpu_scheduler.models import (
    EmbeddingJobConfig,
    GPUJob,
    GPUJobPriority,
    GPUJobStatus,
    GPUJobType,
)
from src.services.gpu_scheduler.queue_engine import (
    PRIORITY_LIMITS,
    STARVATION_THRESHOLD_MINUTES,
    GPUQueueEngine,
    get_queue_engine,
)


class TestQueueEngineBasics:
    """Basic queue operations tests."""

    def test_enqueue_job(self, sample_gpu_job: GPUJob):
        """Test enqueueing a job."""
        engine = GPUQueueEngine()
        queued_job = engine.enqueue(sample_gpu_job)

        assert queued_job.job_id == sample_gpu_job.job_id
        assert queued_job.priority == sample_gpu_job.priority
        assert queued_job.organization_id == sample_gpu_job.organization_id
        assert engine.size() == 1
        assert not engine.is_empty()

    def test_dequeue_job(self, sample_gpu_job: GPUJob):
        """Test dequeuing a job."""
        engine = GPUQueueEngine()
        engine.enqueue(sample_gpu_job)

        queued_job = engine.dequeue()

        assert queued_job is not None
        assert queued_job.job_id == sample_gpu_job.job_id
        assert engine.size() == 0
        assert engine.is_empty()

    def test_dequeue_empty_queue(self):
        """Test dequeuing from empty queue."""
        engine = GPUQueueEngine()
        result = engine.dequeue()
        assert result is None

    def test_remove_job(self, sample_gpu_job: GPUJob):
        """Test removing a job from queue."""
        engine = GPUQueueEngine()
        engine.enqueue(sample_gpu_job)

        removed = engine.remove(sample_gpu_job.job_id)

        assert removed is not None
        assert removed.job_id == sample_gpu_job.job_id
        # Job is removed from index but lazy deletion from heap
        assert sample_gpu_job.job_id not in engine._jobs_by_id

    def test_remove_nonexistent_job(self):
        """Test removing a job that doesn't exist."""
        engine = GPUQueueEngine()
        result = engine.remove("nonexistent-job")
        assert result is None

    def test_peek_jobs(self, sample_embedding_config: EmbeddingJobConfig):
        """Test peeking at queued jobs."""
        engine = GPUQueueEngine()
        jobs = []
        for i in range(5):
            job = GPUJob(
                job_id=f"job-{i}",
                organization_id="org-1",
                user_id="user-1",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.QUEUED,
                priority=GPUJobPriority.NORMAL,
                config=sample_embedding_config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=datetime.now(timezone.utc),
            )
            engine.enqueue(job)
            jobs.append(job)

        peeked = engine.peek(3)
        assert len(peeked) == 3
        # Original queue should be unchanged
        assert engine.size() == 5

    def test_clear_queue(self, sample_gpu_job: GPUJob):
        """Test clearing the queue."""
        engine = GPUQueueEngine()
        engine.enqueue(sample_gpu_job)
        engine.mark_job_running(
            sample_gpu_job.job_id,
            sample_gpu_job.priority,
            sample_gpu_job.organization_id,
        )

        engine.clear()

        assert engine.is_empty()
        assert engine.get_running_count(GPUJobPriority.NORMAL) == 0


class TestPriorityOrdering:
    """Tests for priority-based queue ordering."""

    def test_high_priority_dequeued_first(
        self, sample_embedding_config: EmbeddingJobConfig
    ):
        """Test that HIGH priority jobs are dequeued before NORMAL."""
        engine = GPUQueueEngine()

        normal_job = GPUJob(
            job_id="job-normal",
            organization_id="org-1",
            user_id="user-1",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.NORMAL,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )

        high_job = GPUJob(
            job_id="job-high",
            organization_id="org-1",
            user_id="user-1",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.HIGH,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )

        # Enqueue normal first, then high
        engine.enqueue(normal_job)
        engine.enqueue(high_job)

        # HIGH should come out first despite being enqueued second
        first = engine.dequeue()
        assert first.job_id == "job-high"
        assert first.priority == GPUJobPriority.HIGH

        second = engine.dequeue()
        assert second.job_id == "job-normal"

    def test_priority_order_high_normal_low(
        self, sample_embedding_config: EmbeddingJobConfig
    ):
        """Test full priority ordering: HIGH > NORMAL > LOW."""
        engine = GPUQueueEngine()

        for priority in [
            GPUJobPriority.LOW,
            GPUJobPriority.NORMAL,
            GPUJobPriority.HIGH,
        ]:
            job = GPUJob(
                job_id=f"job-{priority.value}",
                organization_id="org-1",
                user_id="user-1",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.QUEUED,
                priority=priority,
                config=sample_embedding_config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=datetime.now(timezone.utc),
            )
            engine.enqueue(job)

        first = engine.dequeue()
        assert first.priority == GPUJobPriority.HIGH

        second = engine.dequeue()
        assert second.priority == GPUJobPriority.NORMAL

        third = engine.dequeue()
        assert third.priority == GPUJobPriority.LOW

    def test_fifo_within_same_priority(
        self, sample_embedding_config: EmbeddingJobConfig
    ):
        """Test FIFO ordering within same priority level."""
        engine = GPUQueueEngine()

        # Create jobs with same priority but different times
        base_time = datetime.now(timezone.utc)
        jobs = []
        for i in range(3):
            job = GPUJob(
                job_id=f"job-{i}",
                organization_id="org-1",
                user_id="user-1",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.QUEUED,
                priority=GPUJobPriority.NORMAL,
                config=sample_embedding_config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=base_time + timedelta(seconds=i),
            )
            jobs.append(job)

        # Enqueue in order
        for job in jobs:
            engine.enqueue(job)

        # Should dequeue in FIFO order
        for i in range(3):
            result = engine.dequeue()
            assert result.job_id == f"job-{i}"


class TestConcurrentLimits:
    """Tests for concurrent job limits per priority level."""

    def test_priority_limits_from_adr(self):
        """Verify priority limits match ADR-061 spec."""
        assert PRIORITY_LIMITS[GPUJobPriority.HIGH]["max_concurrent"] == 2
        assert PRIORITY_LIMITS[GPUJobPriority.NORMAL]["max_concurrent"] == 4
        assert PRIORITY_LIMITS[GPUJobPriority.LOW]["max_concurrent"] == 2

        assert PRIORITY_LIMITS[GPUJobPriority.HIGH]["can_preempt"] is True
        assert PRIORITY_LIMITS[GPUJobPriority.LOW]["can_be_preempted"] is True

    def test_can_start_job_within_limit(self):
        """Test can_start_job returns True within limits."""
        engine = GPUQueueEngine()
        assert engine.can_start_job(GPUJobPriority.HIGH) is True
        assert engine.can_start_job(GPUJobPriority.NORMAL) is True
        assert engine.can_start_job(GPUJobPriority.LOW) is True

    def test_can_start_job_at_limit(self):
        """Test can_start_job returns False at capacity."""
        engine = GPUQueueEngine()

        # Fill HIGH slots (max 2)
        engine.mark_job_running("job-1", GPUJobPriority.HIGH, "org-1")
        engine.mark_job_running("job-2", GPUJobPriority.HIGH, "org-1")

        assert engine.can_start_job(GPUJobPriority.HIGH) is False
        # Other priorities still have room
        assert engine.can_start_job(GPUJobPriority.NORMAL) is True

    def test_dequeue_respects_concurrent_limits(
        self, sample_embedding_config: EmbeddingJobConfig
    ):
        """Test that dequeue respects concurrent limits."""
        engine = GPUQueueEngine()

        # Fill all HIGH slots
        engine.mark_job_running("running-1", GPUJobPriority.HIGH, "org-1")
        engine.mark_job_running("running-2", GPUJobPriority.HIGH, "org-1")

        # Enqueue a new HIGH priority job
        high_job = GPUJob(
            job_id="job-high-queued",
            organization_id="org-1",
            user_id="user-1",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.HIGH,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        engine.enqueue(high_job)

        # Enqueue a NORMAL priority job
        normal_job = GPUJob(
            job_id="job-normal-queued",
            organization_id="org-1",
            user_id="user-1",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.NORMAL,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        engine.enqueue(normal_job)

        # Should dequeue NORMAL even though HIGH has higher priority
        # because HIGH is at capacity
        result = engine.dequeue()
        assert result.job_id == "job-normal-queued"

    def test_mark_job_completed_frees_slot(self):
        """Test that completing a job frees the concurrent slot."""
        engine = GPUQueueEngine()

        # Fill HIGH slots
        engine.mark_job_running("job-1", GPUJobPriority.HIGH, "org-1")
        engine.mark_job_running("job-2", GPUJobPriority.HIGH, "org-1")

        assert engine.can_start_job(GPUJobPriority.HIGH) is False

        # Complete one job
        engine.mark_job_completed("job-1", GPUJobPriority.HIGH, "org-1")

        assert engine.can_start_job(GPUJobPriority.HIGH) is True
        assert engine.get_running_count(GPUJobPriority.HIGH) == 1


class TestStarvationPrevention:
    """Tests for starvation prevention mechanism."""

    def test_starvation_threshold_from_adr(self):
        """Verify starvation threshold matches ADR-061 spec (30 min)."""
        assert STARVATION_THRESHOLD_MINUTES == 30

    def test_promote_starved_low_priority_jobs(
        self, sample_embedding_config: EmbeddingJobConfig
    ):
        """Test that LOW priority jobs are promoted after 30 min."""
        engine = GPUQueueEngine()

        # Create a LOW priority job with old timestamp
        old_time = datetime.now(timezone.utc) - timedelta(minutes=35)

        low_job = GPUJob(
            job_id="job-low-old",
            organization_id="org-1",
            user_id="user-1",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.LOW,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=old_time,
        )

        # Manually set queued_at in the past
        with patch("src.services.gpu_scheduler.queue_engine.datetime") as mock_datetime:
            mock_datetime.now.return_value = old_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            engine.enqueue(low_job)

        # Manually update queued_at
        engine._jobs_by_id[low_job.job_id].queued_at = old_time
        engine._heap[0].queued_at = old_time

        # Promote starved jobs
        promoted = engine.promote_starved_jobs()

        assert "job-low-old" in promoted
        assert engine._jobs_by_id["job-low-old"].starvation_promoted is True

    def test_promoted_jobs_have_higher_priority(
        self, sample_embedding_config: EmbeddingJobConfig
    ):
        """Test that starvation-promoted jobs are prioritized."""
        engine = GPUQueueEngine()

        # Create an old LOW priority job
        old_time = datetime.now(timezone.utc) - timedelta(minutes=35)

        old_low_job = GPUJob(
            job_id="job-low-old",
            organization_id="org-1",
            user_id="user-1",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.LOW,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=old_time,
        )

        # Create a new LOW priority job
        new_low_job = GPUJob(
            job_id="job-low-new",
            organization_id="org-1",
            user_id="user-1",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.LOW,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )

        engine.enqueue(old_low_job)
        engine.enqueue(new_low_job)

        # Manually set old job's queued_at
        engine._jobs_by_id[old_low_job.job_id].queued_at = old_time
        for job in engine._heap:
            if job.job_id == old_low_job.job_id:
                job.queued_at = old_time

        # Promoted job should come out first even though both are LOW
        first = engine.dequeue()
        assert first.job_id == "job-low-old"
        assert first.starvation_promoted is True

    def test_normal_and_high_not_promoted(
        self, sample_embedding_config: EmbeddingJobConfig
    ):
        """Test that NORMAL and HIGH priority jobs are not promoted."""
        engine = GPUQueueEngine()

        old_time = datetime.now(timezone.utc) - timedelta(minutes=35)

        for priority in [GPUJobPriority.NORMAL, GPUJobPriority.HIGH]:
            job = GPUJob(
                job_id=f"job-{priority.value}",
                organization_id="org-1",
                user_id="user-1",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.QUEUED,
                priority=priority,
                config=sample_embedding_config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=old_time,
            )
            engine.enqueue(job)
            engine._jobs_by_id[job.job_id].queued_at = old_time
            for queued in engine._heap:
                if queued.job_id == job.job_id:
                    queued.queued_at = old_time

        promoted = engine.promote_starved_jobs()
        assert len(promoted) == 0


class TestPreemption:
    """Tests for job preemption functionality."""

    def test_find_preemption_candidate_for_high(self):
        """Test finding preemption candidate for HIGH priority job."""
        engine = GPUQueueEngine()

        # Mark a LOW priority job as running
        engine.mark_job_running("job-low-running", GPUJobPriority.LOW, "org-1")

        candidate = engine.find_preemption_candidate(GPUJobPriority.HIGH)
        assert candidate == "job-low-running"

    def test_no_preemption_candidate_without_low_running(self):
        """Test no candidate when no LOW priority jobs are running."""
        engine = GPUQueueEngine()

        # Only NORMAL jobs running
        engine.mark_job_running("job-normal-running", GPUJobPriority.NORMAL, "org-1")

        candidate = engine.find_preemption_candidate(GPUJobPriority.HIGH)
        assert candidate is None

    def test_normal_cannot_preempt(self):
        """Test that NORMAL priority jobs cannot preempt."""
        engine = GPUQueueEngine()

        # Mark a LOW priority job as running
        engine.mark_job_running("job-low-running", GPUJobPriority.LOW, "org-1")

        candidate = engine.find_preemption_candidate(GPUJobPriority.NORMAL)
        assert candidate is None

    def test_low_cannot_preempt(self):
        """Test that LOW priority jobs cannot preempt."""
        engine = GPUQueueEngine()

        engine.mark_job_running("job-low-running", GPUJobPriority.LOW, "org-1")

        candidate = engine.find_preemption_candidate(GPUJobPriority.LOW)
        assert candidate is None

    def test_get_preemptable_jobs(self):
        """Test getting list of preemptable jobs."""
        engine = GPUQueueEngine()

        # Mark multiple LOW priority jobs as running
        engine.mark_job_running("job-low-1", GPUJobPriority.LOW, "org-1")
        engine.mark_job_running("job-low-2", GPUJobPriority.LOW, "org-2")

        # Also mark a NORMAL job (not preemptable)
        engine.mark_job_running("job-normal-1", GPUJobPriority.NORMAL, "org-1")

        preemptable = engine.get_preemptable_jobs()
        assert len(preemptable) == 2
        assert "job-low-1" in preemptable
        assert "job-low-2" in preemptable
        assert "job-normal-1" not in preemptable

    def test_record_preemption(self):
        """Test recording preemption for metrics."""
        engine = GPUQueueEngine()

        engine.record_preemption()
        engine.record_preemption()

        metrics = engine.get_metrics()
        assert metrics.preemptions_last_hour == 2


class TestQueuePosition:
    """Tests for queue position calculation."""

    def test_get_queue_position(self, sample_embedding_config: EmbeddingJobConfig):
        """Test getting queue position for a job."""
        engine = GPUQueueEngine()

        jobs = []
        for i in range(3):
            job = GPUJob(
                job_id=f"job-{i}",
                organization_id="org-1",
                user_id="user-1",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.QUEUED,
                priority=GPUJobPriority.NORMAL,
                config=sample_embedding_config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=datetime.now(timezone.utc) + timedelta(seconds=i),
            )
            engine.enqueue(job)
            jobs.append(job)

        # First job should be position 1
        assert engine.get_queue_position("job-0") == 1
        # Second job should be position 2
        assert engine.get_queue_position("job-1") == 2
        # Third job should be position 3
        assert engine.get_queue_position("job-2") == 3

    def test_queue_position_respects_priority(
        self, sample_embedding_config: EmbeddingJobConfig
    ):
        """Test queue position accounts for priority."""
        engine = GPUQueueEngine()

        # Enqueue NORMAL first, then HIGH
        normal_job = GPUJob(
            job_id="job-normal",
            organization_id="org-1",
            user_id="user-1",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.NORMAL,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        engine.enqueue(normal_job)

        high_job = GPUJob(
            job_id="job-high",
            organization_id="org-1",
            user_id="user-1",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.HIGH,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        engine.enqueue(high_job)

        # HIGH should be position 1 despite being enqueued second
        assert engine.get_queue_position("job-high") == 1
        assert engine.get_queue_position("job-normal") == 2

    def test_queue_position_nonexistent_job(self):
        """Test getting position for non-existent job."""
        engine = GPUQueueEngine()
        assert engine.get_queue_position("nonexistent") is None


class TestMetrics:
    """Tests for queue metrics."""

    def test_get_metrics_empty_queue(self):
        """Test metrics for empty queue."""
        engine = GPUQueueEngine()
        metrics = engine.get_metrics()

        assert metrics.total_queued == 0
        assert metrics.running_jobs == 0
        assert metrics.avg_wait_time_seconds == 0.0
        assert metrics.preemptions_last_hour == 0

    def test_get_metrics_with_jobs(self, sample_embedding_config: EmbeddingJobConfig):
        """Test metrics with queued and running jobs."""
        engine = GPUQueueEngine()

        # Add jobs of different priorities
        for priority in GPUJobPriority:
            job = GPUJob(
                job_id=f"job-{priority.value}",
                organization_id="org-1",
                user_id="user-1",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.QUEUED,
                priority=priority,
                config=sample_embedding_config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=datetime.now(timezone.utc),
            )
            engine.enqueue(job)

        # Mark some as running
        engine.mark_job_running("running-1", GPUJobPriority.HIGH, "org-1")
        engine.mark_job_running("running-2", GPUJobPriority.NORMAL, "org-2")

        metrics = engine.get_metrics()

        assert metrics.total_queued == 3
        assert metrics.by_priority["high"] == 1
        assert metrics.by_priority["normal"] == 1
        assert metrics.by_priority["low"] == 1
        assert metrics.running_jobs == 2
        assert metrics.running_by_priority["high"] == 1
        assert metrics.running_by_priority["normal"] == 1

    def test_metrics_average_wait_time(
        self, sample_embedding_config: EmbeddingJobConfig
    ):
        """Test average wait time calculation."""
        engine = GPUQueueEngine()

        job = GPUJob(
            job_id="job-1",
            organization_id="org-1",
            user_id="user-1",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.NORMAL,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        engine.enqueue(job)

        # Dequeue updates wait time
        engine.dequeue()

        metrics = engine.get_metrics()
        assert metrics.avg_wait_time_seconds >= 0

    def test_metrics_drain_time_estimation(
        self, sample_embedding_config: EmbeddingJobConfig
    ):
        """Test queue drain time estimation."""
        engine = GPUQueueEngine()

        # Add several jobs
        for i in range(8):
            job = GPUJob(
                job_id=f"job-{i}",
                organization_id="org-1",
                user_id="user-1",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.QUEUED,
                priority=GPUJobPriority.NORMAL,
                config=sample_embedding_config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=datetime.now(timezone.utc),
            )
            engine.enqueue(job)

        metrics = engine.get_metrics()
        # With 8 jobs, total capacity of 8 (2+4+2), ~30 min avg
        assert metrics.estimated_drain_time_minutes > 0


class TestOrganizationTracking:
    """Tests for organization-level tracking."""

    def test_running_jobs_by_org(self, sample_embedding_config: EmbeddingJobConfig):
        """Test tracking running jobs by organization."""
        engine = GPUQueueEngine()

        engine.mark_job_running("job-1", GPUJobPriority.NORMAL, "org-1")
        engine.mark_job_running("job-2", GPUJobPriority.NORMAL, "org-1")
        engine.mark_job_running("job-3", GPUJobPriority.NORMAL, "org-2")

        assert len(engine._running_by_org["org-1"]) == 2
        assert len(engine._running_by_org["org-2"]) == 1

    def test_metrics_by_organization(self, sample_embedding_config: EmbeddingJobConfig):
        """Test metrics include organization breakdown."""
        engine = GPUQueueEngine()

        for i, org in enumerate(["org-1", "org-1", "org-2"]):
            job = GPUJob(
                job_id=f"job-{i}",
                organization_id=org,
                user_id="user-1",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.QUEUED,
                priority=GPUJobPriority.NORMAL,
                config=sample_embedding_config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=datetime.now(timezone.utc),
            )
            engine.enqueue(job)

        metrics = engine.get_metrics()
        assert metrics.by_organization["org-1"] == 2
        assert metrics.by_organization["org-2"] == 1


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_queue_engine_returns_same_instance(self):
        """Test singleton returns same instance."""
        # Reset singleton
        import src.services.gpu_scheduler.queue_engine as qe_module

        qe_module._queue_engine = None

        engine1 = get_queue_engine()
        engine2 = get_queue_engine()

        assert engine1 is engine2
