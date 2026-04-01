"""Tests for GPU Position Estimator.

Tests queue position and wait time estimation per ADR-061 Phase 2.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.services.gpu_scheduler.models import (
    EmbeddingJobConfig,
    GPUJob,
    GPUJobPriority,
    GPUJobStatus,
    GPUJobType,
)
from src.services.gpu_scheduler.position_estimator import (
    DEFAULT_DURATION_MINUTES,
    GPU_SCALING_TIME_MINUTES,
    PRIORITY_CONCURRENT_LIMITS,
    PositionEstimator,
    get_position_estimator,
    init_position_estimator,
)
from src.services.gpu_scheduler.queue_engine import GPUQueueEngine


@pytest.fixture
def queue_engine():
    """Create a fresh queue engine for tests."""
    return GPUQueueEngine()


@pytest.fixture
def position_estimator(queue_engine: GPUQueueEngine):
    """Create position estimator with queue engine."""
    return PositionEstimator(queue_engine=queue_engine)


class TestConstants:
    """Tests for module constants."""

    def test_default_duration_minutes(self):
        """Test default job duration estimates."""
        assert DEFAULT_DURATION_MINUTES[GPUJobType.EMBEDDING_GENERATION] == 30
        assert DEFAULT_DURATION_MINUTES[GPUJobType.LOCAL_INFERENCE] == 60
        assert DEFAULT_DURATION_MINUTES[GPUJobType.VULNERABILITY_TRAINING] == 120
        assert DEFAULT_DURATION_MINUTES[GPUJobType.SWE_RL_TRAINING] == 240
        assert DEFAULT_DURATION_MINUTES[GPUJobType.MEMORY_CONSOLIDATION] == 10

    def test_gpu_scaling_time(self):
        """Test GPU scaling time constant."""
        assert GPU_SCALING_TIME_MINUTES == 5

    def test_priority_concurrent_limits(self):
        """Test concurrent limits match ADR-061."""
        assert PRIORITY_CONCURRENT_LIMITS[GPUJobPriority.HIGH] == 2
        assert PRIORITY_CONCURRENT_LIMITS[GPUJobPriority.NORMAL] == 4
        assert PRIORITY_CONCURRENT_LIMITS[GPUJobPriority.LOW] == 2


class TestEstimatePosition:
    """Tests for estimate_position method."""

    def test_job_not_in_queue(
        self,
        position_estimator: PositionEstimator,
    ):
        """Test estimate for job not in queue."""
        estimate = position_estimator.estimate_position(
            job_id="nonexistent-job",
            current_gpu_count=2,
        )

        assert estimate.queue_position == 0
        assert estimate.jobs_ahead == 0
        assert estimate.estimated_wait_minutes == 0
        assert estimate.confidence == 1.0
        assert "not in queue" in estimate.factors[0].lower()

    def test_estimate_with_no_jobs_ahead(
        self,
        position_estimator: PositionEstimator,
        queue_engine: GPUQueueEngine,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test estimate when job is first in queue."""
        job = GPUJob(
            job_id="job-first",
            organization_id="org-test",
            user_id="user-test",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.NORMAL,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        queue_engine.enqueue(job)

        estimate = position_estimator.estimate_position(
            job_id="job-first",
            current_gpu_count=2,
        )

        assert estimate.queue_position == 1
        assert estimate.jobs_ahead == 0
        assert estimate.estimated_wait_minutes == 0

    def test_estimate_with_jobs_ahead(
        self,
        position_estimator: PositionEstimator,
        queue_engine: GPUQueueEngine,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test estimate when there are jobs ahead."""
        # Add jobs ahead
        for i in range(3):
            job = GPUJob(
                job_id=f"job-ahead-{i}",
                organization_id="org-test",
                user_id="user-test",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.QUEUED,
                priority=GPUJobPriority.NORMAL,
                config=sample_embedding_config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=datetime.now(timezone.utc) + timedelta(seconds=i),
            )
            queue_engine.enqueue(job)

        # Add target job
        target_job = GPUJob(
            job_id="job-target",
            organization_id="org-test",
            user_id="user-test",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.NORMAL,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc) + timedelta(seconds=10),
        )
        queue_engine.enqueue(target_job)

        estimate = position_estimator.estimate_position(
            job_id="job-target",
            current_gpu_count=2,
        )

        assert estimate.queue_position == 4
        assert estimate.jobs_ahead == 3
        assert estimate.estimated_wait_minutes > 0

    def test_estimate_includes_gpu_scaling(
        self,
        position_estimator: PositionEstimator,
        queue_engine: GPUQueueEngine,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test estimate includes GPU scaling time when count is 0."""
        job = GPUJob(
            job_id="job-scaling",
            organization_id="org-test",
            user_id="user-test",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.NORMAL,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        queue_engine.enqueue(job)

        estimate = position_estimator.estimate_position(
            job_id="job-scaling",
            current_gpu_count=0,
        )

        assert estimate.gpu_scaling_required is True
        assert estimate.estimated_wait_minutes >= GPU_SCALING_TIME_MINUTES
        assert any("scaling" in f.lower() for f in estimate.factors)

    def test_estimate_preemption_possible_for_high(
        self,
        position_estimator: PositionEstimator,
        queue_engine: GPUQueueEngine,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test preemption possible flag for HIGH priority."""
        # Mark a LOW job as running
        queue_engine.mark_job_running("running-low", GPUJobPriority.LOW, "org-other")

        # Add HIGH priority job
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
        queue_engine.enqueue(high_job)

        estimate = position_estimator.estimate_position(
            job_id="job-high",
            current_gpu_count=2,
        )

        assert estimate.preemption_possible is True
        assert any("preemption" in f.lower() for f in estimate.factors)

    def test_estimate_no_preemption_for_normal(
        self,
        position_estimator: PositionEstimator,
        queue_engine: GPUQueueEngine,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test preemption not possible for NORMAL priority."""
        # Mark a LOW job as running
        queue_engine.mark_job_running("running-low", GPUJobPriority.LOW, "org-other")

        # Add NORMAL priority job
        normal_job = GPUJob(
            job_id="job-normal",
            organization_id="org-test",
            user_id="user-test",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.QUEUED,
            priority=GPUJobPriority.NORMAL,
            config=sample_embedding_config,
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        queue_engine.enqueue(normal_job)

        estimate = position_estimator.estimate_position(
            job_id="job-normal",
            current_gpu_count=2,
        )

        assert estimate.preemption_possible is False

    def test_estimate_without_queue_engine_raises(self):
        """Test that estimate_position raises without queue engine."""
        estimator = PositionEstimator(queue_engine=None)

        with pytest.raises(ValueError, match="Queue engine not configured"):
            estimator.estimate_position("job-id")


class TestEstimateForNewJob:
    """Tests for estimate_for_new_job method."""

    def test_estimate_for_new_job_empty_queue(
        self,
        position_estimator: PositionEstimator,
    ):
        """Test estimate for new job with empty queue."""
        estimate = position_estimator.estimate_for_new_job(
            priority=GPUJobPriority.NORMAL,
            job_type=GPUJobType.EMBEDDING_GENERATION,
            organization_id="org-test",
            current_gpu_count=2,
        )

        assert estimate.job_id == "estimate"
        assert estimate.queue_position == 1
        assert estimate.jobs_ahead == 0

    def test_estimate_for_new_job_with_queue(
        self,
        position_estimator: PositionEstimator,
        queue_engine: GPUQueueEngine,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test estimate for new job when queue has jobs."""
        # Add some jobs to queue
        for i in range(3):
            job = GPUJob(
                job_id=f"job-{i}",
                organization_id="org-test",
                user_id="user-test",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.QUEUED,
                priority=GPUJobPriority.NORMAL,
                config=sample_embedding_config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=datetime.now(timezone.utc),
            )
            queue_engine.enqueue(job)

        estimate = position_estimator.estimate_for_new_job(
            priority=GPUJobPriority.NORMAL,
            job_type=GPUJobType.EMBEDDING_GENERATION,
            organization_id="org-test",
            current_gpu_count=2,
        )

        # Should be 4th in queue (3 ahead + 1)
        assert estimate.queue_position == 4
        assert estimate.jobs_ahead == 3

    def test_estimate_for_high_priority_new_job(
        self,
        position_estimator: PositionEstimator,
        queue_engine: GPUQueueEngine,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test estimate for HIGH priority new job."""
        # Add NORMAL jobs
        for i in range(3):
            job = GPUJob(
                job_id=f"job-normal-{i}",
                organization_id="org-test",
                user_id="user-test",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                status=GPUJobStatus.QUEUED,
                priority=GPUJobPriority.NORMAL,
                config=sample_embedding_config,
                gpu_memory_gb=8,
                max_runtime_hours=2,
                checkpoint_enabled=True,
                created_at=datetime.now(timezone.utc),
            )
            queue_engine.enqueue(job)

        estimate = position_estimator.estimate_for_new_job(
            priority=GPUJobPriority.HIGH,
            job_type=GPUJobType.EMBEDDING_GENERATION,
            organization_id="org-test",
            current_gpu_count=2,
        )

        # HIGH priority should be first (no HIGH jobs ahead)
        assert estimate.queue_position == 1

    def test_estimate_for_new_job_gpu_scaling(
        self,
        position_estimator: PositionEstimator,
    ):
        """Test estimate includes GPU scaling for new job."""
        estimate = position_estimator.estimate_for_new_job(
            priority=GPUJobPriority.NORMAL,
            job_type=GPUJobType.EMBEDDING_GENERATION,
            organization_id="org-test",
            current_gpu_count=0,
        )

        assert estimate.gpu_scaling_required is True
        assert estimate.estimated_wait_minutes >= GPU_SCALING_TIME_MINUTES

    def test_estimate_for_new_job_preemption(
        self,
        position_estimator: PositionEstimator,
        queue_engine: GPUQueueEngine,
    ):
        """Test preemption factor in new job estimate."""
        # Mark a LOW job as running
        queue_engine.mark_job_running("running-low", GPUJobPriority.LOW, "org-other")

        estimate = position_estimator.estimate_for_new_job(
            priority=GPUJobPriority.HIGH,
            job_type=GPUJobType.EMBEDDING_GENERATION,
            organization_id="org-test",
            current_gpu_count=2,
        )

        assert estimate.preemption_possible is True
        assert any("preempt" in f.lower() for f in estimate.factors)

    def test_estimate_without_queue_engine(self):
        """Test estimate for new job without queue engine."""
        estimator = PositionEstimator(queue_engine=None)

        estimate = estimator.estimate_for_new_job(
            priority=GPUJobPriority.NORMAL,
            job_type=GPUJobType.EMBEDDING_GENERATION,
            organization_id="org-test",
            current_gpu_count=0,
        )

        assert estimate.queue_position == 1
        assert estimate.confidence == 0.5


class TestWaitTimeCalculation:
    """Tests for wait time calculation logic."""

    def test_wait_time_with_jobs_ahead(
        self,
        position_estimator: PositionEstimator,
    ):
        """Test wait time calculation with jobs ahead."""
        jobs_ahead = {
            "high": 2,
            "normal": 4,
            "low": 0,
        }

        wait_minutes, factors = position_estimator._estimate_wait_time(
            jobs_ahead,
            current_gpu_count=2,
            scaling_in_progress=False,
        )

        # HIGH: 2 jobs / 2 concurrent = 1 batch * 30 min = 30 min
        # NORMAL: 4 jobs / 4 concurrent = 1 batch * 30 min = 30 min
        # Total: 60 min
        assert wait_minutes == 60
        assert len(factors) >= 2

    def test_wait_time_with_gpu_scaling(
        self,
        position_estimator: PositionEstimator,
    ):
        """Test wait time includes GPU scaling."""
        jobs_ahead = {"high": 0, "normal": 0, "low": 0}

        wait_minutes, factors = position_estimator._estimate_wait_time(
            jobs_ahead,
            current_gpu_count=0,
            scaling_in_progress=False,
        )

        assert wait_minutes == GPU_SCALING_TIME_MINUTES
        assert any("scaling" in f.lower() for f in factors)

    def test_wait_time_no_scaling_when_in_progress(
        self,
        position_estimator: PositionEstimator,
    ):
        """Test no scaling time added when scaling in progress."""
        jobs_ahead = {"high": 0, "normal": 0, "low": 0}

        wait_minutes, factors = position_estimator._estimate_wait_time(
            jobs_ahead,
            current_gpu_count=0,
            scaling_in_progress=True,
        )

        assert wait_minutes == 0
        assert not any("scaling" in f.lower() for f in factors)


class TestConfidenceCalculation:
    """Tests for confidence score calculation."""

    def test_confidence_no_jobs_ahead(
        self,
        position_estimator: PositionEstimator,
    ):
        """Test confidence is high with no jobs ahead."""
        confidence = position_estimator._calculate_confidence(
            jobs_ahead=0,
            factors=[],
        )
        assert confidence == 1.0

    def test_confidence_decreases_with_queue_depth(
        self,
        position_estimator: PositionEstimator,
    ):
        """Test confidence decreases as queue gets longer."""
        conf_0 = position_estimator._calculate_confidence(0, [])
        conf_5 = position_estimator._calculate_confidence(5, [])
        conf_10 = position_estimator._calculate_confidence(10, [])

        assert conf_0 > conf_5 > conf_10

    def test_confidence_decreases_with_scaling(
        self,
        position_estimator: PositionEstimator,
    ):
        """Test confidence decreases when GPU scaling needed."""
        conf_no_scaling = position_estimator._calculate_confidence(
            0,
            [],
        )
        conf_scaling = position_estimator._calculate_confidence(
            0,
            ["GPU scaling required"],
        )

        assert conf_no_scaling > conf_scaling

    def test_confidence_decreases_with_preemption(
        self,
        position_estimator: PositionEstimator,
    ):
        """Test confidence decreases when preemption possible."""
        conf_no_preempt = position_estimator._calculate_confidence(
            0,
            [],
        )
        conf_preempt = position_estimator._calculate_confidence(
            0,
            ["Preemption possible"],
        )

        assert conf_no_preempt > conf_preempt

    def test_confidence_minimum_value(
        self,
        position_estimator: PositionEstimator,
    ):
        """Test confidence has minimum value of 0.1."""
        confidence = position_estimator._calculate_confidence(
            jobs_ahead=100,
            factors=["scaling", "preemption", "lots of factors"],
        )

        assert confidence >= 0.1


class TestPriorityValue:
    """Tests for priority value mapping."""

    def test_priority_ordering(
        self,
        position_estimator: PositionEstimator,
    ):
        """Test priority values are ordered correctly."""
        high_val = position_estimator._priority_value(GPUJobPriority.HIGH)
        normal_val = position_estimator._priority_value(GPUJobPriority.NORMAL)
        low_val = position_estimator._priority_value(GPUJobPriority.LOW)

        # Lower value = higher priority
        assert high_val < normal_val < low_val


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_position_estimator_returns_same_instance(self):
        """Test singleton returns same instance."""
        # Reset singleton
        import src.services.gpu_scheduler.position_estimator as pe_module

        pe_module._position_estimator = None

        estimator1 = get_position_estimator()
        estimator2 = get_position_estimator()

        assert estimator1 is estimator2

    def test_init_position_estimator(self, queue_engine: GPUQueueEngine):
        """Test initializing position estimator with dependencies."""
        # Reset singleton
        import src.services.gpu_scheduler.position_estimator as pe_module

        pe_module._position_estimator = None

        estimator = init_position_estimator(queue_engine=queue_engine)

        assert estimator.queue_engine is queue_engine
        assert get_position_estimator() is estimator
