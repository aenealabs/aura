"""
Tests for GPU Metrics Service

ADR-061: GPU Workload Scheduler - Phase 4 Observability & Cost
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.cloudwatch_metrics_publisher import (
    CloudWatchMetricsPublisher,
)
from src.services.gpu_scheduler.gpu_metrics_service import (
    GPUBudgetStatus,
    GPUCostMetrics,
    GPUMetricName,
    GPUMetricsService,
    GPUQueueMetrics,
    GPUResourceMetrics,
)
from src.services.gpu_scheduler.models import GPUJobPriority, GPUJobStatus


@dataclass
class MockGPUJob:
    """Mock GPU job for testing (simpler than Pydantic model)."""

    job_id: str
    organization_id: str
    user_id: str
    job_type: str
    priority: GPUJobPriority
    status: GPUJobStatus
    config: dict = field(default_factory=dict)
    gpu_memory_gb: int = 8
    max_runtime_hours: int = 2
    checkpoint_enabled: bool = True
    progress_percent: Optional[int] = None
    cost_usd: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None


@pytest.fixture
def mock_publisher():
    """Create a mock CloudWatch metrics publisher."""
    publisher = MagicMock(spec=CloudWatchMetricsPublisher)
    publisher.publish_metric = AsyncMock()
    publisher.start = AsyncMock()
    publisher.stop = AsyncMock()
    publisher.flush = AsyncMock()
    return publisher


@pytest.fixture
def metrics_service(mock_publisher):
    """Create a GPU metrics service with mock publisher."""
    return GPUMetricsService(
        publisher=mock_publisher,
        environment="test",
        service_name="gpu-scheduler",
    )


@pytest.fixture
def sample_job():
    """Create a sample GPU job for testing."""
    return MockGPUJob(
        job_id="gpu-job-001",
        organization_id="org-123",
        user_id="user-456",
        job_type="embedding_generation",
        priority=GPUJobPriority.NORMAL,
        status=GPUJobStatus.COMPLETED,
        progress_percent=100,
        cost_usd=0.54,
        started_at=datetime(2026, 1, 13, 10, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 13, 10, 30, 0, tzinfo=timezone.utc),
    )


class TestGPUMetricsServiceInit:
    """Tests for GPUMetricsService initialization."""

    def test_init_with_publisher(self, mock_publisher):
        """Test initialization with provided publisher."""
        service = GPUMetricsService(
            publisher=mock_publisher,
            environment="dev",
            service_name="test-service",
        )

        assert service.publisher == mock_publisher
        assert service.environment == "dev"
        assert service.service_name == "test-service"
        assert service._default_dimensions == {
            "Environment": "dev",
            "Service": "test-service",
        }

    def test_init_without_publisher(self):
        """Test initialization creates default publisher."""
        with patch.object(CloudWatchMetricsPublisher, "__init__", return_value=None):
            service = GPUMetricsService(environment="test")
            assert service.environment == "test"

    def test_job_counts_initialized(self, metrics_service):
        """Test job counts are initialized to zero."""
        counts = metrics_service.get_job_counts()
        assert all(v == 0 for v in counts.values())
        assert "submitted" in counts
        assert "completed" in counts
        assert "failed" in counts


class TestJobEventMetrics:
    """Tests for job lifecycle event metrics."""

    @pytest.mark.asyncio
    async def test_publish_job_submitted(
        self, metrics_service, mock_publisher, sample_job
    ):
        """Test publishing job submitted event."""
        sample_job.status = GPUJobStatus.QUEUED
        sample_job.cost_usd = None  # Clear cost to avoid extra JOB_COST metric

        await metrics_service.publish_job_event(sample_job, "submitted")

        mock_publisher.publish_metric.assert_called()
        # First call should be JOBS_SUBMITTED
        call_args = mock_publisher.publish_metric.call_args_list[0]
        assert call_args.kwargs["metric_name"] == GPUMetricName.JOBS_SUBMITTED.value
        assert call_args.kwargs["value"] == 1.0

    @pytest.mark.asyncio
    async def test_publish_job_completed(
        self, metrics_service, mock_publisher, sample_job
    ):
        """Test publishing job completed event with duration."""
        await metrics_service.publish_job_event(sample_job, "completed")

        # Should publish both completed count and duration
        calls = mock_publisher.publish_metric.call_args_list
        metric_names = [c.kwargs["metric_name"] for c in calls]

        assert GPUMetricName.JOBS_COMPLETED.value in metric_names
        assert GPUMetricName.JOB_DURATION.value in metric_names

    @pytest.mark.asyncio
    async def test_publish_job_failed(
        self, metrics_service, mock_publisher, sample_job
    ):
        """Test publishing job failed event."""
        sample_job.status = GPUJobStatus.FAILED
        sample_job.error_message = "OOM error"

        await metrics_service.publish_job_event(sample_job, "failed")

        call_args = mock_publisher.publish_metric.call_args_list[0]
        assert call_args.kwargs["metric_name"] == GPUMetricName.JOBS_FAILED.value

    @pytest.mark.asyncio
    async def test_publish_job_with_cost(
        self, metrics_service, mock_publisher, sample_job
    ):
        """Test job cost metric is published when cost is set."""
        sample_job.cost_usd = 1.25

        await metrics_service.publish_job_event(sample_job, "completed")

        calls = mock_publisher.publish_metric.call_args_list
        metric_names = [c.kwargs["metric_name"] for c in calls]

        assert GPUMetricName.JOB_COST.value in metric_names

    @pytest.mark.asyncio
    async def test_job_counts_updated(
        self, metrics_service, mock_publisher, sample_job
    ):
        """Test internal job counts are updated."""
        await metrics_service.publish_job_event(sample_job, "submitted")
        await metrics_service.publish_job_event(sample_job, "completed")
        await metrics_service.publish_job_event(sample_job, "failed")

        counts = metrics_service.get_job_counts()
        assert counts["submitted"] == 1
        assert counts["completed"] == 1
        assert counts["failed"] == 1

    @pytest.mark.asyncio
    async def test_unknown_event_type_ignored(
        self, metrics_service, mock_publisher, sample_job
    ):
        """Test unknown event type is ignored."""
        await metrics_service.publish_job_event(sample_job, "unknown_event")

        mock_publisher.publish_metric.assert_not_called()


class TestQueueMetrics:
    """Tests for queue metrics publishing."""

    @pytest.mark.asyncio
    async def test_publish_queue_metrics(self, metrics_service, mock_publisher):
        """Test publishing queue metrics."""
        queue_metrics = GPUQueueMetrics(
            total_queued=5,
            by_priority={"high": 1, "normal": 3, "low": 1},
            running_jobs=2,
            avg_wait_time_seconds=420.0,
            max_wait_time_seconds=900.0,
            starvation_promotions_last_hour=1,
        )

        await metrics_service.publish_queue_metrics(queue_metrics)

        calls = mock_publisher.publish_metric.call_args_list
        metric_names = [c.kwargs["metric_name"] for c in calls]

        assert GPUMetricName.QUEUE_DEPTH.value in metric_names
        assert GPUMetricName.QUEUE_WAIT_TIME.value in metric_names
        assert GPUMetricName.STARVATION_PROMOTIONS.value in metric_names

    @pytest.mark.asyncio
    async def test_queue_depth_by_priority(self, metrics_service, mock_publisher):
        """Test queue depth published for each priority."""
        queue_metrics = GPUQueueMetrics(
            total_queued=6,
            by_priority={"high": 2, "normal": 3, "low": 1},
            running_jobs=1,
            avg_wait_time_seconds=300.0,
        )

        await metrics_service.publish_queue_metrics(queue_metrics)

        calls = mock_publisher.publish_metric.call_args_list
        priority_calls = [
            c
            for c in calls
            if c.kwargs["metric_name"] == GPUMetricName.QUEUE_DEPTH.value
            and "Priority" in c.kwargs.get("dimensions", {})
        ]

        assert len(priority_calls) == 3  # high, normal, low


class TestResourceMetrics:
    """Tests for GPU resource metrics publishing."""

    @pytest.mark.asyncio
    async def test_publish_resource_metrics(self, metrics_service, mock_publisher):
        """Test publishing resource metrics."""
        resource_metrics = GPUResourceMetrics(
            gpus_in_use=3,
            gpus_total=4,
            gpus_available=1,
            gpu_utilization_percent=75.0,
            gpu_memory_used_gb=12.0,
            gpu_memory_total_gb=16.0,
            gpu_temperature_celsius=65.0,
            gpu_power_watts=150.0,
        )

        await metrics_service.publish_resource_metrics(resource_metrics)

        calls = mock_publisher.publish_metric.call_args_list
        metric_names = [c.kwargs["metric_name"] for c in calls]

        assert GPUMetricName.GPUS_IN_USE.value in metric_names
        assert GPUMetricName.GPUS_AVAILABLE.value in metric_names
        assert GPUMetricName.GPU_UTILIZATION.value in metric_names
        assert GPUMetricName.GPU_MEMORY_USED.value in metric_names
        assert GPUMetricName.GPU_TEMPERATURE.value in metric_names

    @pytest.mark.asyncio
    async def test_resource_metrics_skip_zero_dcgm(
        self, metrics_service, mock_publisher
    ):
        """Test DCGM metrics skipped when zero (not available)."""
        resource_metrics = GPUResourceMetrics(
            gpus_in_use=1,
            gpus_total=4,
            gpus_available=3,
            gpu_utilization_percent=0.0,  # Not available
            gpu_memory_total_gb=0.0,  # Not available
            gpu_temperature_celsius=0.0,  # Not available
        )

        await metrics_service.publish_resource_metrics(resource_metrics)

        calls = mock_publisher.publish_metric.call_args_list
        metric_names = [c.kwargs["metric_name"] for c in calls]

        # Basic metrics should be present
        assert GPUMetricName.GPUS_IN_USE.value in metric_names
        assert GPUMetricName.GPUS_AVAILABLE.value in metric_names

        # DCGM metrics should be skipped
        assert GPUMetricName.GPU_UTILIZATION.value not in metric_names
        assert GPUMetricName.GPU_TEMPERATURE.value not in metric_names


class TestCostMetrics:
    """Tests for cost metrics publishing."""

    @pytest.mark.asyncio
    async def test_publish_cost_metrics(self, metrics_service, mock_publisher):
        """Test publishing cost metrics."""
        cost_metrics = GPUCostMetrics(
            total_cost_usd=47.82,
            gpu_hours=142.5,
            jobs_count=89,
            avg_job_cost_usd=0.54,
            cost_by_job_type={
                "embedding_generation": 18.23,
                "swe_rl_training": 24.15,
            },
            cost_by_organization={
                "org-123": 30.00,
                "org-456": 17.82,
            },
        )

        await metrics_service.publish_cost_metrics(cost_metrics, "org-123")

        calls = mock_publisher.publish_metric.call_args_list
        metric_names = [c.kwargs["metric_name"] for c in calls]

        assert GPUMetricName.MONTHLY_COST.value in metric_names
        assert GPUMetricName.JOB_THROUGHPUT.value in metric_names
        assert GPUMetricName.COST_BY_JOB_TYPE.value in metric_names
        assert GPUMetricName.COST_BY_ORGANIZATION.value in metric_names

    @pytest.mark.asyncio
    async def test_publish_daily_cost(self, metrics_service, mock_publisher):
        """Test publishing daily cost metric."""
        await metrics_service.publish_daily_cost(
            cost_usd=5.67,
            date=datetime(2026, 1, 13, tzinfo=timezone.utc),
            organization_id="org-123",
        )

        call_args = mock_publisher.publish_metric.call_args
        assert call_args.kwargs["metric_name"] == GPUMetricName.DAILY_COST.value
        assert call_args.kwargs["value"] == 5.67


class TestBudgetMetrics:
    """Tests for budget metrics publishing."""

    @pytest.mark.asyncio
    async def test_publish_budget_status(self, metrics_service, mock_publisher):
        """Test publishing budget status metrics."""
        budget_status = GPUBudgetStatus(
            organization_id="org-123",
            budget_limit_usd=100.0,
            budget_used_usd=85.0,
            budget_remaining_usd=15.0,
            usage_percent=85.0,
            forecast_end_of_month_usd=120.0,
            alert_threshold_percent=80.0,
            alert_triggered=True,
        )

        await metrics_service.publish_budget_status(budget_status)

        calls = mock_publisher.publish_metric.call_args_list
        metric_names = [c.kwargs["metric_name"] for c in calls]

        assert GPUMetricName.BUDGET_USAGE_PERCENT.value in metric_names
        assert GPUMetricName.BUDGET_FORECAST.value in metric_names
        assert GPUMetricName.BUDGET_ALERTS_TRIGGERED.value in metric_names

    @pytest.mark.asyncio
    async def test_budget_alert_not_triggered(self, metrics_service, mock_publisher):
        """Test budget alert metric not published when not triggered."""
        budget_status = GPUBudgetStatus(
            organization_id="org-123",
            budget_limit_usd=100.0,
            budget_used_usd=50.0,
            budget_remaining_usd=50.0,
            usage_percent=50.0,
            forecast_end_of_month_usd=75.0,
            alert_triggered=False,
        )

        await metrics_service.publish_budget_status(budget_status)

        calls = mock_publisher.publish_metric.call_args_list
        metric_names = [c.kwargs["metric_name"] for c in calls]

        assert GPUMetricName.BUDGET_ALERTS_TRIGGERED.value not in metric_names


class TestSpotInterruptionMetrics:
    """Tests for Spot interruption metrics."""

    @pytest.mark.asyncio
    async def test_publish_spot_interruption(
        self, metrics_service, mock_publisher, sample_job
    ):
        """Test publishing Spot interruption event."""
        await metrics_service.publish_spot_interruption(
            job=sample_job,
            checkpoint_saved=True,
        )

        call_args = mock_publisher.publish_metric.call_args
        assert call_args.kwargs["metric_name"] == GPUMetricName.SPOT_INTERRUPTIONS.value
        assert call_args.kwargs["dimensions"]["CheckpointSaved"] == "true"

    @pytest.mark.asyncio
    async def test_spot_interruption_no_checkpoint(
        self, metrics_service, mock_publisher, sample_job
    ):
        """Test Spot interruption without checkpoint."""
        await metrics_service.publish_spot_interruption(
            job=sample_job,
            checkpoint_saved=False,
        )

        call_args = mock_publisher.publish_metric.call_args
        assert call_args.kwargs["dimensions"]["CheckpointSaved"] == "false"


class TestScalingEventMetrics:
    """Tests for scaling event metrics."""

    @pytest.mark.asyncio
    async def test_publish_scale_up_event(self, metrics_service, mock_publisher):
        """Test publishing scale up event."""
        await metrics_service.publish_scaling_event(
            event_type="scale_up",
            nodes_before=2,
            nodes_after=4,
            trigger="queue_depth",
        )

        call_args = mock_publisher.publish_metric.call_args
        assert call_args.kwargs["metric_name"] == GPUMetricName.SCALING_EVENTS.value
        assert call_args.kwargs["value"] == 2.0  # abs(4-2)
        assert call_args.kwargs["dimensions"]["ScalingType"] == "scale_up"
        assert call_args.kwargs["dimensions"]["Trigger"] == "queue_depth"

    @pytest.mark.asyncio
    async def test_publish_scale_down_event(self, metrics_service, mock_publisher):
        """Test publishing scale down event."""
        await metrics_service.publish_scaling_event(
            event_type="scale_down",
            nodes_before=4,
            nodes_after=2,
            trigger="scheduled",
        )

        call_args = mock_publisher.publish_metric.call_args
        assert call_args.kwargs["value"] == 2.0  # abs(2-4)
        assert call_args.kwargs["dimensions"]["ScalingType"] == "scale_down"


class TestLifecycleManagement:
    """Tests for service lifecycle management."""

    @pytest.mark.asyncio
    async def test_start(self, metrics_service, mock_publisher):
        """Test starting the metrics service."""
        await metrics_service.start()
        mock_publisher.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop(self, metrics_service, mock_publisher):
        """Test stopping the metrics service."""
        await metrics_service.stop()
        mock_publisher.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_flush(self, metrics_service, mock_publisher):
        """Test flushing metrics."""
        await metrics_service.flush()
        mock_publisher.flush.assert_awaited_once()

    def test_reset_job_counts(self, metrics_service, mock_publisher):
        """Test resetting job counts."""
        metrics_service._job_counts["submitted"] = 10
        metrics_service._job_counts["completed"] = 5

        metrics_service.reset_job_counts()

        counts = metrics_service.get_job_counts()
        assert all(v == 0 for v in counts.values())


class TestDimensionMerging:
    """Tests for dimension merging."""

    @pytest.mark.asyncio
    async def test_default_dimensions_included(
        self, metrics_service, mock_publisher, sample_job
    ):
        """Test default dimensions are included in all metrics."""
        await metrics_service.publish_job_event(sample_job, "completed")

        call_args = mock_publisher.publish_metric.call_args_list[0]
        dimensions = call_args.kwargs["dimensions"]

        assert dimensions["Environment"] == "test"
        assert dimensions["Service"] == "gpu-scheduler"

    @pytest.mark.asyncio
    async def test_custom_dimensions_merged(
        self, metrics_service, mock_publisher, sample_job
    ):
        """Test custom dimensions are merged with defaults."""
        await metrics_service.publish_job_event(
            sample_job,
            "completed",
            additional_dimensions={"CustomKey": "CustomValue"},
        )

        call_args = mock_publisher.publish_metric.call_args_list[0]
        dimensions = call_args.kwargs["dimensions"]

        assert dimensions["Environment"] == "test"
        assert dimensions["CustomKey"] == "CustomValue"
