"""
Project Aura - GPU Metrics Service

Collects and publishes GPU workload metrics to CloudWatch for:
- Job execution metrics (submitted, completed, failed, cancelled)
- Queue metrics (depth, wait times, position estimates)
- Resource utilization (GPUs in use, memory, utilization)
- Cost tracking (per job, per organization, per job type)
- DCGM Exporter integration for real GPU hardware metrics

ADR-061: GPU Workload Scheduler - Phase 4 Observability & Cost
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ..cloudwatch_metrics_publisher import (
    CloudWatchMetricsPublisher,
    MetricNamespace,
    PublisherMode,
)
from .models import GPUJob, GPUJobPriority

logger = logging.getLogger(__name__)


# =============================================================================
# GPU Metric Types
# =============================================================================


class GPUMetricName(str, Enum):
    """GPU-specific metric names for CloudWatch."""

    # Job Lifecycle Metrics
    JOBS_SUBMITTED = "JobsSubmitted"
    JOBS_STARTED = "JobsStarted"
    JOBS_COMPLETED = "JobsCompleted"
    JOBS_FAILED = "JobsFailed"
    JOBS_CANCELLED = "JobsCancelled"
    JOBS_PREEMPTED = "JobsPreempted"

    # Queue Metrics
    QUEUE_DEPTH = "QueueDepth"
    QUEUE_WAIT_TIME = "QueueWaitTime"
    QUEUE_POSITION_AVG = "QueuePositionAverage"
    STARVATION_PROMOTIONS = "StarvationPromotions"

    # Resource Metrics
    GPUS_IN_USE = "GPUsInUse"
    GPUS_AVAILABLE = "GPUsAvailable"
    GPU_UTILIZATION = "GPUUtilization"
    GPU_MEMORY_USED = "GPUMemoryUsed"
    GPU_MEMORY_TOTAL = "GPUMemoryTotal"
    GPU_TEMPERATURE = "GPUTemperature"
    GPU_POWER_USAGE = "GPUPowerUsage"

    # Cost Metrics
    JOB_COST = "JobCost"
    DAILY_COST = "DailyCost"
    MONTHLY_COST = "MonthlyCost"
    COST_BY_JOB_TYPE = "CostByJobType"
    COST_BY_ORGANIZATION = "CostByOrganization"

    # Performance Metrics
    JOB_DURATION = "JobDuration"
    JOB_THROUGHPUT = "JobThroughput"
    SCALING_EVENTS = "ScalingEvents"
    SPOT_INTERRUPTIONS = "SpotInterruptions"

    # Budget Metrics
    BUDGET_USAGE_PERCENT = "BudgetUsagePercent"
    BUDGET_FORECAST = "BudgetForecast"
    BUDGET_ALERTS_TRIGGERED = "BudgetAlertsTriggered"


@dataclass
class GPUResourceMetrics:
    """Real-time GPU resource metrics from DCGM or Kubernetes."""

    gpus_in_use: int = 0
    gpus_total: int = 0
    gpus_available: int = 0
    gpu_utilization_percent: float = 0.0
    gpu_memory_used_gb: float = 0.0
    gpu_memory_total_gb: float = 0.0
    gpu_temperature_celsius: float = 0.0
    gpu_power_watts: float = 0.0
    nodes_active: int = 0
    nodes_scaling: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GPUCostMetrics:
    """GPU cost metrics for tracking and budgeting."""

    total_cost_usd: float = 0.0
    gpu_hours: float = 0.0
    jobs_count: int = 0
    avg_job_cost_usd: float = 0.0
    cost_by_job_type: dict[str, float] = field(default_factory=dict)
    cost_by_organization: dict[str, float] = field(default_factory=dict)
    daily_costs: list[dict[str, Any]] = field(default_factory=list)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


@dataclass
class GPUBudgetStatus:
    """GPU budget status for an organization."""

    organization_id: str
    budget_limit_usd: float
    budget_used_usd: float
    budget_remaining_usd: float
    usage_percent: float
    forecast_end_of_month_usd: float
    alert_threshold_percent: float = 80.0
    alert_triggered: bool = False
    days_remaining: int = 0


@dataclass
class GPUQueueMetrics:
    """Queue metrics for GPU workloads."""

    total_queued: int = 0
    by_priority: dict[str, int] = field(default_factory=dict)
    running_jobs: int = 0
    avg_wait_time_seconds: float = 0.0
    max_wait_time_seconds: float = 0.0
    starvation_promotions_last_hour: int = 0
    preemptions_last_hour: int = 0


# =============================================================================
# GPU Metrics Service
# =============================================================================


class GPUMetricsService:
    """
    Collects and publishes GPU workload metrics to CloudWatch.

    Integrates with:
    - GPU Scheduler Service for job metrics
    - DCGM Exporter for hardware metrics (via Prometheus/Kubernetes)
    - DynamoDB for cost tracking
    - CloudWatch for metric publishing

    Usage:
        metrics_service = GPUMetricsService(publisher)

        # Publish job event
        await metrics_service.publish_job_event(job, "completed")

        # Publish queue metrics
        await metrics_service.publish_queue_metrics(queue_metrics)

        # Publish resource metrics (called periodically)
        await metrics_service.publish_resource_metrics(resource_metrics)

        # Publish cost metrics
        await metrics_service.publish_cost_metrics(cost_metrics, "org-123")
    """

    def __init__(
        self,
        publisher: Optional[CloudWatchMetricsPublisher] = None,
        environment: str = "dev",
        service_name: str = "gpu-scheduler",
    ):
        """
        Initialize GPU metrics service.

        Args:
            publisher: CloudWatch metrics publisher (creates default if None)
            environment: Deployment environment (dev, qa, prod)
            service_name: Service name for metric dimensions
        """
        self.publisher = publisher or CloudWatchMetricsPublisher(
            mode=PublisherMode.MOCK if environment == "test" else PublisherMode.AWS
        )
        self.environment = environment
        self.service_name = service_name
        self._default_dimensions = {
            "Environment": environment,
            "Service": service_name,
        }

        # Metric collection state
        self._job_counts: dict[str, int] = {
            "submitted": 0,
            "started": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "preempted": 0,
        }
        self._last_publish_time: Optional[datetime] = None

        logger.info(f"GPUMetricsService initialized for {environment} environment")

    def _merge_dimensions(
        self, custom_dimensions: Optional[dict[str, str]] = None
    ) -> dict[str, str]:
        """Merge custom dimensions with defaults."""
        dimensions = self._default_dimensions.copy()
        if custom_dimensions:
            dimensions.update(custom_dimensions)
        return dimensions

    # =========================================================================
    # Job Lifecycle Metrics
    # =========================================================================

    async def publish_job_event(
        self,
        job: GPUJob,
        event_type: str,
        additional_dimensions: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Publish a job lifecycle event metric.

        Args:
            job: The GPU job
            event_type: Event type (submitted, started, completed, failed, cancelled, preempted)
            additional_dimensions: Extra dimensions to include
        """
        metric_map = {
            "submitted": GPUMetricName.JOBS_SUBMITTED,
            "started": GPUMetricName.JOBS_STARTED,
            "completed": GPUMetricName.JOBS_COMPLETED,
            "failed": GPUMetricName.JOBS_FAILED,
            "cancelled": GPUMetricName.JOBS_CANCELLED,
            "preempted": GPUMetricName.JOBS_PREEMPTED,
        }

        metric_name = metric_map.get(event_type)
        if not metric_name:
            logger.warning(f"Unknown job event type: {event_type}")
            return

        # Update internal counter
        if event_type in self._job_counts:
            self._job_counts[event_type] += 1

        dimensions = self._merge_dimensions(
            {
                "JobType": job.job_type,
                "Priority": (
                    job.priority.value
                    if isinstance(job.priority, GPUJobPriority)
                    else job.priority
                ),
                "OrganizationId": job.organization_id,
                **(additional_dimensions or {}),
            }
        )

        await self.publisher.publish_metric(
            namespace=MetricNamespace.GPU_SCHEDULER,
            metric_name=metric_name.value,
            value=1.0,
            unit="Count",
            dimensions=dimensions,
        )

        # If job completed or failed, also publish duration
        if event_type in ("completed", "failed") and job.started_at:
            duration_minutes = self._calculate_duration_minutes(job)
            if duration_minutes > 0:
                await self.publisher.publish_metric(
                    namespace=MetricNamespace.GPU_SCHEDULER,
                    metric_name=GPUMetricName.JOB_DURATION.value,
                    value=duration_minutes,
                    unit="Count",  # Minutes
                    dimensions=dimensions,
                )

        # If job has cost, publish cost metric
        if job.cost_usd and job.cost_usd > 0:
            await self.publisher.publish_metric(
                namespace=MetricNamespace.GPU_SCHEDULER,
                metric_name=GPUMetricName.JOB_COST.value,
                value=job.cost_usd,
                unit="None",  # USD
                dimensions=dimensions,
            )

        logger.debug(
            f"Published job event: {event_type} for job {job.job_id} "
            f"(type={job.job_type}, priority={job.priority})"
        )

    def _calculate_duration_minutes(self, job: GPUJob) -> float:
        """Calculate job duration in minutes."""
        if not job.started_at:
            return 0.0

        end_time = job.completed_at or datetime.now(timezone.utc)
        if isinstance(job.started_at, str):
            start = datetime.fromisoformat(job.started_at.replace("Z", "+00:00"))
        else:
            start = job.started_at

        if isinstance(end_time, str):
            end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        else:
            end = end_time

        duration_seconds = (end - start).total_seconds()
        return max(0.0, duration_seconds / 60.0)

    # =========================================================================
    # Queue Metrics
    # =========================================================================

    async def publish_queue_metrics(
        self,
        metrics: GPUQueueMetrics,
        additional_dimensions: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Publish queue metrics to CloudWatch.

        Args:
            metrics: Current queue metrics
            additional_dimensions: Extra dimensions to include
        """
        dimensions = self._merge_dimensions(additional_dimensions)

        # Queue depth
        await self.publisher.publish_metric(
            namespace=MetricNamespace.GPU_SCHEDULER,
            metric_name=GPUMetricName.QUEUE_DEPTH.value,
            value=float(metrics.total_queued),
            unit="Count",
            dimensions=dimensions,
        )

        # Queue depth by priority
        for priority, count in metrics.by_priority.items():
            await self.publisher.publish_metric(
                namespace=MetricNamespace.GPU_SCHEDULER,
                metric_name=GPUMetricName.QUEUE_DEPTH.value,
                value=float(count),
                unit="Count",
                dimensions={**dimensions, "Priority": priority},
            )

        # Average wait time
        await self.publisher.publish_metric(
            namespace=MetricNamespace.GPU_SCHEDULER,
            metric_name=GPUMetricName.QUEUE_WAIT_TIME.value,
            value=metrics.avg_wait_time_seconds,
            unit="Seconds",
            dimensions=dimensions,
        )

        # Starvation promotions
        if metrics.starvation_promotions_last_hour > 0:
            await self.publisher.publish_metric(
                namespace=MetricNamespace.GPU_SCHEDULER,
                metric_name=GPUMetricName.STARVATION_PROMOTIONS.value,
                value=float(metrics.starvation_promotions_last_hour),
                unit="Count",
                dimensions=dimensions,
            )

        logger.debug(
            f"Published queue metrics: depth={metrics.total_queued}, "
            f"avg_wait={metrics.avg_wait_time_seconds:.1f}s"
        )

    # =========================================================================
    # Resource Metrics (DCGM Integration)
    # =========================================================================

    async def publish_resource_metrics(
        self,
        metrics: GPUResourceMetrics,
        additional_dimensions: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Publish GPU resource metrics to CloudWatch.

        These metrics come from DCGM Exporter or Kubernetes API.

        Args:
            metrics: Current resource metrics
            additional_dimensions: Extra dimensions to include
        """
        dimensions = self._merge_dimensions(additional_dimensions)

        # GPU availability
        await self.publisher.publish_metric(
            namespace=MetricNamespace.GPU_SCHEDULER,
            metric_name=GPUMetricName.GPUS_IN_USE.value,
            value=float(metrics.gpus_in_use),
            unit="Count",
            dimensions=dimensions,
        )

        await self.publisher.publish_metric(
            namespace=MetricNamespace.GPU_SCHEDULER,
            metric_name=GPUMetricName.GPUS_AVAILABLE.value,
            value=float(metrics.gpus_available),
            unit="Count",
            dimensions=dimensions,
        )

        # GPU utilization (if available from DCGM)
        if metrics.gpu_utilization_percent > 0:
            await self.publisher.publish_metric(
                namespace=MetricNamespace.GPU_SCHEDULER,
                metric_name=GPUMetricName.GPU_UTILIZATION.value,
                value=metrics.gpu_utilization_percent,
                unit="Percent",
                dimensions=dimensions,
            )

        # GPU memory (if available from DCGM)
        if metrics.gpu_memory_total_gb > 0:
            await self.publisher.publish_metric(
                namespace=MetricNamespace.GPU_SCHEDULER,
                metric_name=GPUMetricName.GPU_MEMORY_USED.value,
                value=metrics.gpu_memory_used_gb,
                unit="Gigabytes",
                dimensions=dimensions,
            )

            await self.publisher.publish_metric(
                namespace=MetricNamespace.GPU_SCHEDULER,
                metric_name=GPUMetricName.GPU_MEMORY_TOTAL.value,
                value=metrics.gpu_memory_total_gb,
                unit="Gigabytes",
                dimensions=dimensions,
            )

        # GPU temperature (if available from DCGM)
        if metrics.gpu_temperature_celsius > 0:
            await self.publisher.publish_metric(
                namespace=MetricNamespace.GPU_SCHEDULER,
                metric_name=GPUMetricName.GPU_TEMPERATURE.value,
                value=metrics.gpu_temperature_celsius,
                unit="None",  # Celsius
                dimensions=dimensions,
            )

        # GPU power usage (if available from DCGM)
        if metrics.gpu_power_watts > 0:
            await self.publisher.publish_metric(
                namespace=MetricNamespace.GPU_SCHEDULER,
                metric_name=GPUMetricName.GPU_POWER_USAGE.value,
                value=metrics.gpu_power_watts,
                unit="None",  # Watts
                dimensions=dimensions,
            )

        logger.debug(
            f"Published resource metrics: gpus={metrics.gpus_in_use}/{metrics.gpus_total}, "
            f"utilization={metrics.gpu_utilization_percent:.1f}%"
        )

    # =========================================================================
    # Cost Metrics
    # =========================================================================

    async def publish_cost_metrics(
        self,
        metrics: GPUCostMetrics,
        organization_id: Optional[str] = None,
        additional_dimensions: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Publish GPU cost metrics to CloudWatch.

        Args:
            metrics: Cost metrics for the period
            organization_id: Organization ID for scoping
            additional_dimensions: Extra dimensions to include
        """
        base_dimensions = self._merge_dimensions(additional_dimensions)
        if organization_id:
            base_dimensions["OrganizationId"] = organization_id

        # Total cost
        await self.publisher.publish_metric(
            namespace=MetricNamespace.GPU_SCHEDULER,
            metric_name=GPUMetricName.MONTHLY_COST.value,
            value=metrics.total_cost_usd,
            unit="None",  # USD
            dimensions=base_dimensions,
        )

        # GPU hours
        await self.publisher.publish_metric(
            namespace=MetricNamespace.GPU_SCHEDULER,
            metric_name=GPUMetricName.JOB_THROUGHPUT.value,
            value=metrics.gpu_hours,
            unit="None",  # Hours
            dimensions=base_dimensions,
        )

        # Cost by job type
        for job_type, cost in metrics.cost_by_job_type.items():
            await self.publisher.publish_metric(
                namespace=MetricNamespace.GPU_SCHEDULER,
                metric_name=GPUMetricName.COST_BY_JOB_TYPE.value,
                value=cost,
                unit="None",  # USD
                dimensions={**base_dimensions, "JobType": job_type},
            )

        # Cost by organization (for aggregate views)
        for org_id, cost in metrics.cost_by_organization.items():
            await self.publisher.publish_metric(
                namespace=MetricNamespace.GPU_SCHEDULER,
                metric_name=GPUMetricName.COST_BY_ORGANIZATION.value,
                value=cost,
                unit="None",  # USD
                dimensions={**base_dimensions, "OrganizationId": org_id},
            )

        logger.debug(
            f"Published cost metrics: total=${metrics.total_cost_usd:.2f}, "
            f"gpu_hours={metrics.gpu_hours:.1f}"
        )

    async def publish_daily_cost(
        self,
        cost_usd: float,
        date: datetime,
        organization_id: Optional[str] = None,
        additional_dimensions: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Publish daily cost metric to CloudWatch.

        Args:
            cost_usd: Total cost for the day
            date: The date for the cost
            organization_id: Organization ID for scoping
            additional_dimensions: Extra dimensions to include
        """
        dimensions = self._merge_dimensions(additional_dimensions)
        if organization_id:
            dimensions["OrganizationId"] = organization_id

        await self.publisher.publish_metric(
            namespace=MetricNamespace.GPU_SCHEDULER,
            metric_name=GPUMetricName.DAILY_COST.value,
            value=cost_usd,
            unit="None",  # USD
            dimensions=dimensions,
            timestamp=date,
        )

    # =========================================================================
    # Budget Metrics
    # =========================================================================

    async def publish_budget_status(
        self,
        status: GPUBudgetStatus,
        additional_dimensions: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Publish GPU budget status metrics to CloudWatch.

        Args:
            status: Current budget status
            additional_dimensions: Extra dimensions to include
        """
        dimensions = self._merge_dimensions(
            {
                "OrganizationId": status.organization_id,
                **(additional_dimensions or {}),
            }
        )

        # Budget usage percentage
        await self.publisher.publish_metric(
            namespace=MetricNamespace.GPU_SCHEDULER,
            metric_name=GPUMetricName.BUDGET_USAGE_PERCENT.value,
            value=status.usage_percent,
            unit="Percent",
            dimensions=dimensions,
        )

        # Budget forecast
        await self.publisher.publish_metric(
            namespace=MetricNamespace.GPU_SCHEDULER,
            metric_name=GPUMetricName.BUDGET_FORECAST.value,
            value=status.forecast_end_of_month_usd,
            unit="None",  # USD
            dimensions=dimensions,
        )

        # Alert triggered
        if status.alert_triggered:
            await self.publisher.publish_metric(
                namespace=MetricNamespace.GPU_SCHEDULER,
                metric_name=GPUMetricName.BUDGET_ALERTS_TRIGGERED.value,
                value=1.0,
                unit="Count",
                dimensions=dimensions,
            )

        logger.debug(
            f"Published budget status for {status.organization_id}: "
            f"{status.usage_percent:.1f}% used, forecast=${status.forecast_end_of_month_usd:.2f}"
        )

    # =========================================================================
    # Spot Instance Metrics
    # =========================================================================

    async def publish_spot_interruption(
        self,
        job: GPUJob,
        checkpoint_saved: bool = False,
        additional_dimensions: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Publish a Spot interruption event metric.

        Args:
            job: The interrupted job
            checkpoint_saved: Whether checkpoint was saved successfully
            additional_dimensions: Extra dimensions to include
        """
        dimensions = self._merge_dimensions(
            {
                "JobType": job.job_type,
                "Priority": (
                    job.priority.value
                    if isinstance(job.priority, GPUJobPriority)
                    else job.priority
                ),
                "OrganizationId": job.organization_id,
                "CheckpointSaved": str(checkpoint_saved).lower(),
                **(additional_dimensions or {}),
            }
        )

        await self.publisher.publish_metric(
            namespace=MetricNamespace.GPU_SCHEDULER,
            metric_name=GPUMetricName.SPOT_INTERRUPTIONS.value,
            value=1.0,
            unit="Count",
            dimensions=dimensions,
        )

        logger.info(
            f"Published Spot interruption for job {job.job_id} "
            f"(checkpoint_saved={checkpoint_saved})"
        )

    # =========================================================================
    # Scaling Events
    # =========================================================================

    async def publish_scaling_event(
        self,
        event_type: str,  # scale_up, scale_down
        nodes_before: int,
        nodes_after: int,
        trigger: str,  # queue_depth, scheduled, manual
        additional_dimensions: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Publish a GPU node scaling event metric.

        Args:
            event_type: Type of scaling (scale_up, scale_down)
            nodes_before: Number of nodes before scaling
            nodes_after: Number of nodes after scaling
            trigger: What triggered the scaling
            additional_dimensions: Extra dimensions to include
        """
        dimensions = self._merge_dimensions(
            {
                "ScalingType": event_type,
                "Trigger": trigger,
                **(additional_dimensions or {}),
            }
        )

        node_delta = nodes_after - nodes_before

        await self.publisher.publish_metric(
            namespace=MetricNamespace.GPU_SCHEDULER,
            metric_name=GPUMetricName.SCALING_EVENTS.value,
            value=float(abs(node_delta)),
            unit="Count",
            dimensions=dimensions,
        )

        logger.info(
            f"Published scaling event: {event_type} from {nodes_before} to {nodes_after} nodes "
            f"(trigger={trigger})"
        )

    # =========================================================================
    # Lifecycle Management
    # =========================================================================

    async def start(self) -> None:
        """Start the metrics service and underlying publisher."""
        await self.publisher.start()
        logger.info("GPUMetricsService started")

    async def stop(self) -> None:
        """Stop the metrics service and flush remaining metrics."""
        await self.publisher.stop()
        logger.info("GPUMetricsService stopped")

    async def flush(self) -> None:
        """Flush buffered metrics to CloudWatch."""
        await self.publisher.flush()

    def get_job_counts(self) -> dict[str, int]:
        """Get current job event counts since service start."""
        return self._job_counts.copy()

    def reset_job_counts(self) -> None:
        """Reset job event counters."""
        for key in self._job_counts:
            self._job_counts[key] = 0
