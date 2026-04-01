"""Tests for Stalled Job Detector (Phase 5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.services.gpu_scheduler.models import (
    EmbeddingJobConfig,
    GPUJob,
    GPUJobPriority,
    GPUJobStatus,
    GPUJobType,
    StalledJobStatus,
)
from src.services.gpu_scheduler.stalled_job_detector import (
    THRESHOLD_CRITICAL_MINUTES,
    THRESHOLD_STALLED_MINUTES,
    THRESHOLD_WARNING_MINUTES,
    StalledJobDetector,
)


@pytest.fixture
def running_job() -> GPUJob:
    """Create a running GPU job fixture."""
    return GPUJob(
        job_id="job-running-123",
        organization_id="org-test-123",
        user_id="user-test-456",
        job_type=GPUJobType.EMBEDDING_GENERATION,
        status=GPUJobStatus.RUNNING,
        priority=GPUJobPriority.NORMAL,
        config=EmbeddingJobConfig(
            repository_id="test-repo",
            branch="main",
        ),
        gpu_memory_gb=8,
        max_runtime_hours=2,
        checkpoint_enabled=True,
        created_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
        progress_percent=50,
    )


class TestStalledJobDetector:
    """Tests for stalled job detection."""

    def test_healthy_job(
        self,
        stalled_job_detector: StalledJobDetector,
        running_job: GPUJob,
    ):
        """Test job is classified as healthy when progress is recent."""
        # Just started - should be healthy
        stall_info = stalled_job_detector._analyze_job_progress(running_job)

        assert stall_info.status == StalledJobStatus.HEALTHY
        assert stall_info.minutes_since_progress < THRESHOLD_WARNING_MINUTES

    def test_warning_status(
        self,
        stalled_job_detector: StalledJobDetector,
    ):
        """Test job classified as WARNING after 5+ minutes no progress."""
        job = GPUJob(
            job_id="job-warning-123",
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.NORMAL,
            config=EmbeddingJobConfig(repository_id="test-repo", branch="main"),
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            started_at=datetime.now(timezone.utc) - timedelta(minutes=8),
            progress_percent=25,
        )

        stall_info = stalled_job_detector._analyze_job_progress(job)

        assert stall_info.status == StalledJobStatus.WARNING
        assert stall_info.minutes_since_progress >= THRESHOLD_WARNING_MINUTES
        assert stall_info.minutes_since_progress < THRESHOLD_STALLED_MINUTES

    def test_stalled_status(
        self,
        stalled_job_detector: StalledJobDetector,
    ):
        """Test job classified as STALLED after 15+ minutes no progress."""
        job = GPUJob(
            job_id="job-stalled-123",
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.NORMAL,
            config=EmbeddingJobConfig(repository_id="test-repo", branch="main"),
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            started_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            progress_percent=10,
        )

        stall_info = stalled_job_detector._analyze_job_progress(job)

        assert stall_info.status == StalledJobStatus.STALLED
        assert stall_info.minutes_since_progress >= THRESHOLD_STALLED_MINUTES
        assert stall_info.minutes_since_progress < THRESHOLD_CRITICAL_MINUTES

    def test_critical_status(
        self,
        stalled_job_detector: StalledJobDetector,
    ):
        """Test job classified as CRITICAL after 30+ minutes no progress."""
        job = GPUJob(
            job_id="job-critical-123",
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.NORMAL,
            config=EmbeddingJobConfig(repository_id="test-repo", branch="main"),
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=60),
            started_at=datetime.now(timezone.utc) - timedelta(minutes=45),
            progress_percent=5,
        )

        stall_info = stalled_job_detector._analyze_job_progress(job)

        assert stall_info.status == StalledJobStatus.CRITICAL
        assert stall_info.minutes_since_progress >= THRESHOLD_CRITICAL_MINUTES

    def test_overdue_detection(
        self,
        stalled_job_detector: StalledJobDetector,
    ):
        """Test job is marked overdue when exceeding expected duration."""
        # Expected embedding duration is 30 min, mark as overdue at 1.5x (45 min)
        job = GPUJob(
            job_id="job-overdue-123",
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.NORMAL,
            config=EmbeddingJobConfig(repository_id="test-repo", branch="main"),
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=60),
            started_at=datetime.now(timezone.utc) - timedelta(minutes=50),
            progress_percent=75,
        )

        stall_info = stalled_job_detector._analyze_job_progress(job)

        assert stall_info.is_overdue is True


class TestAlertTracking:
    """Tests for alert deduplication and tracking."""

    def test_should_alert_first_time(
        self,
        stalled_job_detector: StalledJobDetector,
    ):
        """Test first alert for a job is always sent."""
        should_alert = stalled_job_detector._should_alert(
            "job-new-123",
            StalledJobStatus.WARNING,
        )

        assert should_alert is True

    def test_should_not_alert_duplicate(
        self,
        stalled_job_detector: StalledJobDetector,
    ):
        """Test duplicate alert is not sent immediately."""
        # Mark job as already alerted
        stalled_job_detector._alerted_jobs["job-alerted-123"] = datetime.now(
            timezone.utc
        )

        should_alert = stalled_job_detector._should_alert(
            "job-alerted-123",
            StalledJobStatus.WARNING,
        )

        assert should_alert is False

    def test_re_alert_after_interval(
        self,
        stalled_job_detector: StalledJobDetector,
    ):
        """Test re-alert sent after cooldown interval."""
        # Mark job as alerted 20 minutes ago
        stalled_job_detector._alerted_jobs["job-old-123"] = datetime.now(
            timezone.utc
        ) - timedelta(minutes=20)

        # CRITICAL re-alerts every 15 min
        should_alert = stalled_job_detector._should_alert(
            "job-old-123",
            StalledJobStatus.CRITICAL,
        )

        assert should_alert is True

    def test_cleanup_old_alerts(
        self,
        stalled_job_detector: StalledJobDetector,
    ):
        """Test old alert tracking entries are cleaned up."""
        # Add old and recent entries
        stalled_job_detector._alerted_jobs["job-old-1"] = datetime.now(
            timezone.utc
        ) - timedelta(hours=25)
        stalled_job_detector._alerted_jobs["job-recent-1"] = datetime.now(timezone.utc)

        stalled_job_detector._cleanup_alert_tracking()

        assert "job-old-1" not in stalled_job_detector._alerted_jobs
        assert "job-recent-1" in stalled_job_detector._alerted_jobs


class TestSNSAlerts:
    """Tests for SNS alert sending."""

    @pytest.mark.asyncio
    async def test_send_alert_with_sns(
        self,
        mock_dynamodb: dict[str, Any],
    ):
        """Test alert is sent via SNS when configured."""
        mock_sns = MagicMock()

        detector = StalledJobDetector(
            jobs_table=mock_dynamodb["jobs_table"],
            sns_client=mock_sns,
            alert_topic_arn="arn:aws:sns:us-east-1:123456789012:gpu-alerts",
        )

        job = GPUJob(
            job_id="job-alert-123",
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.NORMAL,
            config=EmbeddingJobConfig(repository_id="test-repo", branch="main"),
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            started_at=datetime.now(timezone.utc) - timedelta(minutes=18),
            progress_percent=10,
        )

        stall_info = detector._analyze_job_progress(job)
        await detector._send_alert(stall_info)

        mock_sns.publish.assert_called_once()
        call_args = mock_sns.publish.call_args
        assert (
            call_args[1]["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:gpu-alerts"
        )
        # Subject uses first 8 chars of job_id
        assert "job-aler" in call_args[1]["Subject"]

    @pytest.mark.asyncio
    async def test_no_alert_without_sns(
        self,
        stalled_job_detector: StalledJobDetector,
    ):
        """Test no error when SNS not configured."""
        job = GPUJob(
            job_id="job-no-sns-123",
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.NORMAL,
            config=EmbeddingJobConfig(repository_id="test-repo", branch="main"),
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            started_at=datetime.now(timezone.utc) - timedelta(minutes=18),
            progress_percent=10,
        )

        stall_info = stalled_job_detector._analyze_job_progress(job)

        # Should not raise, just log warning
        await stalled_job_detector._send_alert(stall_info)


class TestBatchDetection:
    """Tests for batch stall detection."""

    @pytest.mark.asyncio
    async def test_get_stalled_jobs(
        self,
        stalled_job_detector: StalledJobDetector,
        mock_dynamodb: dict[str, Any],
    ):
        """Test getting all stalled jobs from database."""
        # Insert running job that's stalled
        stalled_job = GPUJob(
            job_id="job-batch-stalled-123",
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.NORMAL,
            config=EmbeddingJobConfig(repository_id="test-repo", branch="main"),
            gpu_memory_gb=8,
            max_runtime_hours=2,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            started_at=datetime.now(timezone.utc) - timedelta(minutes=25),
            progress_percent=5,
        )

        mock_dynamodb["jobs_table"].put_item(Item=stalled_job.to_dynamodb_item())

        # Get stalled jobs
        stalled = await stalled_job_detector.get_stalled_jobs(
            organization_id="org-test-123",
            min_status=StalledJobStatus.WARNING,
        )

        assert len(stalled) >= 1
        assert any(j.job_id == "job-batch-stalled-123" for j in stalled)


class TestJobTypes:
    """Tests for different job types and expected durations."""

    def test_training_job_expected_duration(
        self,
        stalled_job_detector: StalledJobDetector,
    ):
        """Test training jobs have longer expected duration."""
        from src.services.gpu_scheduler.models import SWERLTrainingConfig

        job = GPUJob(
            job_id="job-training-123",
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.SWE_RL_TRAINING,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.NORMAL,
            config=SWERLTrainingConfig(batch_id="batch-123"),
            gpu_memory_gb=16,
            max_runtime_hours=8,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc) - timedelta(hours=3),
            started_at=datetime.now(timezone.utc) - timedelta(hours=3),
            progress_percent=50,
        )

        stall_info = stalled_job_detector._analyze_job_progress(job)

        # 3 hours is within expected duration for training (240 min expected)
        assert stall_info.expected_duration_minutes == 240
        assert stall_info.is_overdue is False

    def test_inference_job_expected_duration(
        self,
        stalled_job_detector: StalledJobDetector,
    ):
        """Test inference jobs have shorter expected duration."""
        from src.services.gpu_scheduler.models import LocalInferenceConfig

        job = GPUJob(
            job_id="job-inference-123",
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.LOCAL_INFERENCE,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.NORMAL,
            config=LocalInferenceConfig(model_id="llama-70b"),
            gpu_memory_gb=24,
            max_runtime_hours=1,
            checkpoint_enabled=False,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            started_at=datetime.now(timezone.utc) - timedelta(minutes=25),
            progress_percent=50,
        )

        stall_info = stalled_job_detector._analyze_job_progress(job)

        # Expected duration for inference is 15 min, 25 min is overdue
        assert stall_info.expected_duration_minutes == 15
        assert stall_info.is_overdue is True


class TestMultiGPUJobs:
    """Tests for multi-GPU job stall detection."""

    def test_multi_gpu_job_detection(
        self,
        stalled_job_detector: StalledJobDetector,
    ):
        """Test stall detection works for multi-GPU jobs."""
        job = GPUJob(
            job_id="job-multi-gpu-123",
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.SWE_RL_TRAINING,
            status=GPUJobStatus.RUNNING,
            priority=GPUJobPriority.HIGH,
            config=EmbeddingJobConfig(repository_id="test-repo", branch="main"),
            gpu_memory_gb=16,
            gpu_count=4,
            max_runtime_hours=8,
            checkpoint_enabled=True,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=40),
            started_at=datetime.now(timezone.utc) - timedelta(minutes=35),
            progress_percent=10,
        )

        stall_info = stalled_job_detector._analyze_job_progress(job)

        # Should detect as stalled regardless of GPU count
        assert stall_info.status == StalledJobStatus.CRITICAL
