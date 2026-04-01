"""REST API Endpoints for GPU Workload Scheduler.

Provides REST interface for GPU job submission, management,
and resource monitoring (ADR-061).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.services.gpu_scheduler.exceptions import (
    GPUJobNotFoundError,
    GPUSchedulerError,
    InvalidJobConfigError,
    JobCancellationError,
    QuotaExceededError,
)
from src.services.gpu_scheduler.gpu_scheduler_service import (
    GPUSchedulerService,
    get_gpu_scheduler_service,
)
from src.services.gpu_scheduler.k8s_client import GPUJobK8sClient, get_k8s_client
from src.services.gpu_scheduler.models import (
    EmbeddingJobConfig,
    GPUJob,
    GPUJobConfig,
    GPUJobCreateRequest,
    GPUJobPriority,
    GPUJobStatus,
    GPUJobType,
    GPUQuota,
    LocalInferenceConfig,
    MemoryConsolidationConfig,
    PositionEstimate,
    QueueMetrics,
    SWERLTrainingConfig,
    VulnerabilityTrainingConfig,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/gpu", tags=["gpu-scheduler"])


# =============================================================================
# Pydantic Request/Response Models for API
# =============================================================================


class GPUJobSubmitRequest(BaseModel):
    """Request to submit a new GPU job."""

    job_type: GPUJobType = Field(..., description="Type of GPU workload")
    config: dict[str, Any] = Field(..., description="Job-specific configuration")
    priority: GPUJobPriority = Field(
        default=GPUJobPriority.NORMAL,
        description="Job priority level",
    )
    gpu_memory_gb: int = Field(
        default=8,
        ge=4,
        le=24,
        description="Required GPU memory in GB",
    )
    max_runtime_hours: int = Field(
        default=2,
        ge=1,
        le=24,
        description="Maximum job runtime in hours",
    )
    checkpoint_enabled: bool = Field(
        default=True,
        description="Enable checkpointing for recovery",
    )


class GPUJobResponse(BaseModel):
    """Response containing GPU job details."""

    job_id: str
    organization_id: str
    user_id: str
    job_type: str
    status: str
    priority: str
    config: dict[str, Any]
    gpu_memory_gb: int
    max_runtime_hours: int
    checkpoint_enabled: bool
    checkpoint_s3_path: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress_percent: int | None = None
    cost_usd: float | None = None
    kubernetes_job_name: str | None = None
    error_message: str | None = None
    error_type: str | None = None

    @classmethod
    def from_job(cls, job: GPUJob) -> GPUJobResponse:
        """Create response from GPUJob model."""
        return cls(
            job_id=job.job_id,
            organization_id=job.organization_id,
            user_id=job.user_id,
            job_type=job.job_type.value,
            status=job.status.value,
            priority=job.priority.value,
            config=job.config.model_dump(),
            gpu_memory_gb=job.gpu_memory_gb,
            max_runtime_hours=job.max_runtime_hours,
            checkpoint_enabled=job.checkpoint_enabled,
            checkpoint_s3_path=job.checkpoint_s3_path,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            progress_percent=job.progress_percent,
            cost_usd=job.cost_usd,
            kubernetes_job_name=job.kubernetes_job_name,
            error_message=job.error_message,
            error_type=job.error_type.value if job.error_type else None,
        )


class GPUJobListResponse(BaseModel):
    """Response containing list of GPU jobs."""

    jobs: list[GPUJobResponse]
    count: int


class GPUQuotaResponse(BaseModel):
    """Response containing GPU quota details."""

    organization_id: str
    max_concurrent_jobs: int
    max_gpu_hours_monthly: int
    max_job_runtime_hours: int
    current_concurrent_jobs: int
    current_month_gpu_hours: float

    @classmethod
    def from_quota(cls, quota: GPUQuota) -> GPUQuotaResponse:
        """Create response from GPUQuota model."""
        return cls(
            organization_id=quota.organization_id,
            max_concurrent_jobs=quota.max_concurrent_jobs,
            max_gpu_hours_monthly=quota.max_gpu_hours_monthly,
            max_job_runtime_hours=quota.max_job_runtime_hours,
            current_concurrent_jobs=quota.current_concurrent_jobs,
            current_month_gpu_hours=quota.current_month_gpu_hours,
        )


class GPUQuotaUpdateRequest(BaseModel):
    """Request to update GPU quota."""

    max_concurrent_jobs: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Maximum concurrent GPU jobs",
    )
    max_gpu_hours_monthly: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Maximum GPU hours per month",
    )
    max_job_runtime_hours: int | None = Field(
        default=None,
        ge=1,
        le=72,
        description="Maximum runtime per job in hours",
    )


class GPUResourceStatusResponse(BaseModel):
    """Response containing GPU resource status."""

    gpus_available: int
    gpus_total: int
    gpus_in_use: int
    queue_depth: int
    estimated_wait_minutes: int | None = None
    node_count: int
    scaling_status: str


class GPUCostSummaryResponse(BaseModel):
    """Response containing GPU cost summary."""

    period: str
    total_cost_usd: float
    total_gpu_hours: float
    job_count: int
    cost_by_job_type: dict[str, float]


class HealthResponse(BaseModel):
    """Response for health check."""

    service: str
    healthy: bool
    region: str
    jobs_table: str
    quotas_table: str
    queue_url: str
    dynamodb_status: str
    sqs_status: str


# =============================================================================
# Helper Functions
# =============================================================================


def _parse_job_config(
    job_type: GPUJobType, config_dict: dict[str, Any]
) -> GPUJobConfig:
    """Parse job config dict into typed config object."""
    if job_type == GPUJobType.EMBEDDING_GENERATION:
        return EmbeddingJobConfig(**config_dict)
    elif job_type == GPUJobType.VULNERABILITY_TRAINING:
        return VulnerabilityTrainingConfig(**config_dict)
    elif job_type == GPUJobType.SWE_RL_TRAINING:
        return SWERLTrainingConfig(**config_dict)
    elif job_type == GPUJobType.MEMORY_CONSOLIDATION:
        return MemoryConsolidationConfig(**config_dict)
    elif job_type == GPUJobType.LOCAL_INFERENCE:
        return LocalInferenceConfig(**config_dict)
    else:
        raise InvalidJobConfigError(f"Unknown job type: {job_type}")


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/jobs",
    response_model=GPUJobResponse,
    summary="Submit a new GPU job",
    status_code=201,
)
async def submit_job(
    request: GPUJobSubmitRequest,
    organization_id: str = Query(..., description="Organization ID"),
    user_id: str = Query(..., description="User ID"),
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
):
    """Submit a new GPU workload job for execution.

    The job will be queued and executed when GPU resources are available.
    Priority determines queue position relative to other jobs.
    """
    try:
        # Parse config into typed object
        config = _parse_job_config(request.job_type, request.config)

        # Create internal request object
        create_request = GPUJobCreateRequest(
            job_type=request.job_type,
            config=config,
            priority=request.priority,
            gpu_memory_gb=request.gpu_memory_gb,
            max_runtime_hours=request.max_runtime_hours,
            checkpoint_enabled=request.checkpoint_enabled,
        )

        job = await service.submit_job(
            organization_id=organization_id,
            user_id=user_id,
            request=create_request,
        )

        return GPUJobResponse.from_job(job)

    except QuotaExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except InvalidJobConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GPUSchedulerError as e:
        logger.error(f"Failed to submit GPU job: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit job")


@router.get(
    "/jobs",
    response_model=GPUJobListResponse,
    summary="List GPU jobs",
)
async def list_jobs(
    organization_id: str = Query(..., description="Organization ID"),
    status: GPUJobStatus | None = Query(default=None, description="Filter by status"),
    user_id: str | None = Query(default=None, description="Filter by user"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results"),
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
):
    """List GPU jobs for an organization.

    Optionally filter by status or user.
    """
    try:
        jobs = await service.list_jobs(
            organization_id=organization_id,
            status=status,
            user_id=user_id,
            limit=limit,
        )

        return GPUJobListResponse(
            jobs=[GPUJobResponse.from_job(job) for job in jobs],
            count=len(jobs),
        )

    except GPUSchedulerError as e:
        logger.error(f"Failed to list GPU jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list jobs")


@router.get(
    "/jobs/{job_id}",
    response_model=GPUJobResponse,
    summary="Get GPU job details",
)
async def get_job(
    job_id: str,
    organization_id: str = Query(..., description="Organization ID"),
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
):
    """Get details of a specific GPU job."""
    try:
        job = await service.get_job(
            organization_id=organization_id,
            job_id=job_id,
        )
        return GPUJobResponse.from_job(job)

    except GPUJobNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    except GPUSchedulerError as e:
        logger.error(f"Failed to get GPU job: {e}")
        raise HTTPException(status_code=500, detail="Failed to get job")


@router.delete(
    "/jobs/{job_id}",
    response_model=GPUJobResponse,
    summary="Cancel a GPU job",
)
async def cancel_job(
    job_id: str,
    organization_id: str = Query(..., description="Organization ID"),
    user_id: str = Query(..., description="User ID"),
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
):
    """Cancel a queued or running GPU job.

    Completed, failed, or already cancelled jobs cannot be cancelled.
    """
    try:
        job = await service.cancel_job(
            organization_id=organization_id,
            job_id=job_id,
            user_id=user_id,
        )
        return GPUJobResponse.from_job(job)

    except GPUJobNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    except JobCancellationError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except GPUSchedulerError as e:
        logger.error(f"Failed to cancel GPU job: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel job")


@router.get(
    "/jobs/{job_id}/logs",
    summary="Stream GPU job logs",
)
async def stream_job_logs(
    job_id: str,
    organization_id: str = Query(..., description="Organization ID"),
    follow: bool = Query(default=False, description="Follow log output"),
    tail: int = Query(default=100, ge=1, le=1000, description="Lines to tail"),
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
    k8s_client: GPUJobK8sClient = Depends(get_k8s_client),
):
    """Stream logs from a running GPU job.

    Returns logs from the Kubernetes pod running the job.
    """
    # Verify job exists and belongs to organization
    try:
        await service.get_job(organization_id=organization_id, job_id=job_id)
    except GPUJobNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    async def generate_logs():
        async for line in k8s_client.stream_pod_logs(
            job_id=job_id,
            follow=follow,
            tail_lines=tail,
        ):
            yield f"{line}\n"

    return StreamingResponse(
        generate_logs(),
        media_type="text/plain",
    )


@router.get(
    "/resources",
    response_model=GPUResourceStatusResponse,
    summary="Get GPU resource status",
)
async def get_resource_status(
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
):
    """Get current GPU resource availability and queue status."""
    try:
        status = await service.get_resource_status()
        return GPUResourceStatusResponse(
            gpus_available=status.gpus_available,
            gpus_total=status.gpus_total,
            gpus_in_use=status.gpus_in_use,
            queue_depth=status.queue_depth,
            estimated_wait_minutes=status.estimated_wait_minutes,
            node_count=status.node_count,
            scaling_status=status.scaling_status,
        )

    except GPUSchedulerError as e:
        logger.error(f"Failed to get resource status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource status")


@router.get(
    "/quota",
    response_model=GPUQuotaResponse,
    summary="Get GPU quota",
)
async def get_quota(
    organization_id: str = Query(..., description="Organization ID"),
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
):
    """Get GPU quota for an organization."""
    try:
        quota = await service.get_quota(organization_id=organization_id)
        return GPUQuotaResponse.from_quota(quota)

    except GPUSchedulerError as e:
        logger.error(f"Failed to get GPU quota: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quota")


@router.put(
    "/quota",
    response_model=GPUQuotaResponse,
    summary="Update GPU quota",
)
async def update_quota(
    request: GPUQuotaUpdateRequest,
    organization_id: str = Query(..., description="Organization ID"),
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
):
    """Update GPU quota for an organization.

    Requires admin permissions.
    """
    try:
        quota = await service.update_quota(
            organization_id=organization_id,
            max_concurrent_jobs=request.max_concurrent_jobs,
            max_gpu_hours_monthly=request.max_gpu_hours_monthly,
            max_job_runtime_hours=request.max_job_runtime_hours,
        )
        return GPUQuotaResponse.from_quota(quota)

    except GPUSchedulerError as e:
        logger.error(f"Failed to update GPU quota: {e}")
        raise HTTPException(status_code=500, detail="Failed to update quota")


@router.get(
    "/costs",
    response_model=GPUCostSummaryResponse,
    summary="Get GPU cost summary",
)
async def get_cost_summary(
    organization_id: str = Query(..., description="Organization ID"),
    period: str = Query(default="month", description="Cost period (day/week/month)"),
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
):
    """Get GPU cost summary for an organization.

    Breaks down costs by job type for the specified period.
    """
    # Get all completed jobs for the period
    try:
        jobs = await service.list_jobs(
            organization_id=organization_id,
            status=GPUJobStatus.COMPLETED,
            limit=100,
        )

        # Calculate totals
        total_cost = sum(job.cost_usd or 0 for job in jobs)
        total_hours = sum(
            (
                (job.completed_at - job.started_at).total_seconds() / 3600
                if job.completed_at and job.started_at
                else 0
            )
            for job in jobs
        )

        # Group by job type
        cost_by_type: dict[str, float] = {}
        for job in jobs:
            job_type = job.job_type.value
            cost_by_type[job_type] = cost_by_type.get(job_type, 0) + (job.cost_usd or 0)

        return GPUCostSummaryResponse(
            period=period,
            total_cost_usd=round(total_cost, 2),
            total_gpu_hours=round(total_hours, 2),
            job_count=len(jobs),
            cost_by_job_type=cost_by_type,
        )

    except GPUSchedulerError as e:
        logger.error(f"Failed to get cost summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cost summary")


# =============================================================================
# Phase 2: Queue Management Endpoints (ADR-061)
# =============================================================================


class PositionEstimateResponse(BaseModel):
    """Response containing queue position estimate."""

    job_id: str
    queue_position: int
    jobs_ahead: int
    jobs_ahead_by_priority: dict[str, int]
    estimated_wait_minutes: int
    estimated_start_time: datetime
    confidence: float
    factors: list[str]
    gpu_scaling_required: bool
    preemption_possible: bool

    @classmethod
    def from_estimate(cls, estimate: PositionEstimate) -> "PositionEstimateResponse":
        """Create response from PositionEstimate model."""
        return cls(
            job_id=estimate.job_id,
            queue_position=estimate.queue_position,
            jobs_ahead=estimate.jobs_ahead,
            jobs_ahead_by_priority=estimate.jobs_ahead_by_priority,
            estimated_wait_minutes=estimate.estimated_wait_minutes,
            estimated_start_time=estimate.estimated_start_time,
            confidence=estimate.confidence,
            factors=estimate.factors,
            gpu_scaling_required=estimate.gpu_scaling_required,
            preemption_possible=estimate.preemption_possible,
        )


class QueueMetricsResponse(BaseModel):
    """Response containing queue metrics."""

    total_queued: int
    by_priority: dict[str, int]
    by_organization: dict[str, int]
    running_jobs: int
    running_by_priority: dict[str, int]
    avg_wait_time_seconds: float
    oldest_queued_at: datetime | None = None
    estimated_drain_time_minutes: int
    preemptions_last_hour: int
    starvation_promotions_last_hour: int

    @classmethod
    def from_metrics(cls, metrics: QueueMetrics) -> "QueueMetricsResponse":
        """Create response from QueueMetrics model."""
        return cls(
            total_queued=metrics.total_queued,
            by_priority=metrics.by_priority,
            by_organization=metrics.by_organization,
            running_jobs=metrics.running_jobs,
            running_by_priority=metrics.running_by_priority,
            avg_wait_time_seconds=metrics.avg_wait_time_seconds,
            oldest_queued_at=metrics.oldest_queued_at,
            estimated_drain_time_minutes=metrics.estimated_drain_time_minutes,
            preemptions_last_hour=metrics.preemptions_last_hour,
            starvation_promotions_last_hour=metrics.starvation_promotions_last_hour,
        )


class QueueEstimateRequest(BaseModel):
    """Request to estimate queue position for a potential job."""

    priority: GPUJobPriority = Field(..., description="Job priority level")
    job_type: GPUJobType = Field(..., description="Type of GPU workload")


@router.get(
    "/queue/position/{job_id}",
    response_model=PositionEstimateResponse,
    summary="Get queue position estimate",
)
async def get_queue_position(
    job_id: str,
    organization_id: str = Query(..., description="Organization ID"),
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
):
    """Get estimated queue position and wait time for a queued job.

    Returns position in queue, jobs ahead, and estimated wait time.
    """
    try:
        estimate = await service.get_queue_position(
            organization_id=organization_id,
            job_id=job_id,
        )
        return PositionEstimateResponse.from_estimate(estimate)

    except GPUJobNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    except GPUSchedulerError as e:
        logger.error(f"Failed to get queue position: {e}")
        raise HTTPException(status_code=500, detail="Failed to get queue position")


@router.get(
    "/queue/metrics",
    response_model=QueueMetricsResponse,
    summary="Get queue metrics",
)
async def get_queue_metrics(
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
):
    """Get current queue metrics and statistics.

    Returns queue depth, jobs by priority, wait times, and preemption stats.
    """
    try:
        metrics = await service.get_queue_metrics()
        return QueueMetricsResponse.from_metrics(metrics)

    except GPUSchedulerError as e:
        logger.error(f"Failed to get queue metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get queue metrics")


@router.post(
    "/queue/estimate",
    response_model=PositionEstimateResponse,
    summary="Estimate position for new job",
)
async def estimate_queue_position(
    request: QueueEstimateRequest,
    organization_id: str = Query(..., description="Organization ID"),
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
):
    """Estimate queue position before submitting a job.

    Used by the UI to show expected wait time in the schedule modal.
    """
    try:
        estimate = await service.estimate_position_for_new_job(
            organization_id=organization_id,
            priority=request.priority,
            job_type=request.job_type,
        )
        return PositionEstimateResponse.from_estimate(estimate)

    except GPUSchedulerError as e:
        logger.error(f"Failed to estimate queue position: {e}")
        raise HTTPException(status_code=500, detail="Failed to estimate queue position")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
async def health_check(
    service: GPUSchedulerService = Depends(get_gpu_scheduler_service),
):
    """Check GPU scheduler service health."""
    status = await service.health_check()
    return HealthResponse(**status)
