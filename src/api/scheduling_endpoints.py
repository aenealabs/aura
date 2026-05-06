"""
Scheduling API Endpoints

REST API for job scheduling and queue management.
ADR-055: Agent Scheduling View and Job Queue Management
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user
from src.services.scheduling import (
    JobType,
    Priority,
    ScheduledJob,
    ScheduleJobRequest,
    ScheduleStatus,
    SchedulingService,
    get_scheduling_service,
)
from src.services.scheduling.scheduling_service import (
    ScheduleNotFoundError,
    ScheduleValidationError,
    SchedulingServiceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schedule", tags=["scheduling"])
queue_router = APIRouter(prefix="/api/v1/queue", tags=["queue"])


# Request/Response Models


class ScheduleJobRequestModel(BaseModel):
    """Request to schedule a new job."""

    job_type: str = Field(..., description="Type of job to schedule")
    scheduled_at: datetime = Field(..., description="When to execute the job (ISO8601)")
    repository_id: Optional[str] = Field(None, description="Target repository ID")
    priority: str = Field(
        "NORMAL", description="Job priority (CRITICAL, HIGH, NORMAL, LOW)"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Job parameters"
    )
    notify_on_completion: bool = Field(
        True, description="Send notification when complete"
    )
    description: Optional[str] = Field(None, description="Job description")


class RescheduleRequestModel(BaseModel):
    """Request to reschedule a job."""

    scheduled_at: datetime = Field(..., description="New scheduled time (ISO8601)")


class ScheduledJobResponse(BaseModel):
    """Response containing a scheduled job."""

    schedule_id: str
    organization_id: str
    job_type: str
    scheduled_at: datetime
    created_at: datetime
    created_by: str
    status: str
    priority: str
    repository_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    notify_on_completion: bool = True
    description: Optional[str] = None
    dispatched_at: Optional[datetime] = None
    dispatched_job_id: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class ScheduledJobListResponse(BaseModel):
    """Response containing a list of scheduled jobs."""

    jobs: List[ScheduledJobResponse]
    next_cursor: Optional[str] = None
    total_count: Optional[int] = None


class QueueStatusResponse(BaseModel):
    """Response containing queue status."""

    total_queued: int
    total_scheduled: int
    active_jobs: int
    by_priority: Dict[str, int]
    by_type: Dict[str, int]
    avg_wait_time_seconds: float
    throughput_per_hour: float
    oldest_queued_at: Optional[datetime] = None
    next_scheduled_at: Optional[datetime] = None


class TimelineEntryResponse(BaseModel):
    """Response containing a timeline entry."""

    job_id: str
    job_type: str
    status: str
    title: str
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    repository_name: Optional[str] = None
    created_by: Optional[str] = None


class TimelineResponse(BaseModel):
    """Response containing timeline entries."""

    entries: List[TimelineEntryResponse]
    start_date: datetime
    end_date: datetime


# Helper functions


def _job_to_response(job: ScheduledJob) -> ScheduledJobResponse:
    """Convert ScheduledJob to response model."""
    return ScheduledJobResponse(
        schedule_id=job.schedule_id,
        organization_id=job.organization_id,
        job_type=job.job_type.value if hasattr(job.job_type, "value") else job.job_type,
        scheduled_at=job.scheduled_at,
        created_at=job.created_at,
        created_by=job.created_by,
        status=job.status.value if hasattr(job.status, "value") else job.status,
        priority=job.priority.value if hasattr(job.priority, "value") else job.priority,
        repository_id=job.repository_id,
        parameters=job.parameters,
        notify_on_completion=job.notify_on_completion,
        description=job.description,
        dispatched_at=job.dispatched_at,
        dispatched_job_id=job.dispatched_job_id,
        cancelled_at=job.cancelled_at,
        cancelled_by=job.cancelled_by,
        error_message=job.error_message,
    )


def _get_service() -> SchedulingService:
    """Get scheduling service instance."""
    return get_scheduling_service()


# Schedule Endpoints


@router.post("", response_model=ScheduledJobResponse)
async def create_scheduled_job(
    request: ScheduleJobRequestModel,
    current_user: User = Depends(get_current_user),
    service: SchedulingService = Depends(_get_service),
) -> ScheduledJobResponse:
    """
    Schedule a new job for future execution.

    Requires `jobs:schedule` permission.
    """
    try:
        # Parse job type
        try:
            job_type = JobType(request.job_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid job_type: {request.job_type}. Valid types: {[t.value for t in JobType]}",
            )

        # Parse priority
        try:
            priority = Priority(request.priority)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority: {request.priority}. Valid: CRITICAL, HIGH, NORMAL, LOW",
            )

        # Create schedule request
        schedule_request = ScheduleJobRequest(
            job_type=job_type,
            scheduled_at=request.scheduled_at,
            repository_id=request.repository_id,
            priority=priority,
            parameters=request.parameters,
            notify_on_completion=request.notify_on_completion,
            description=request.description,
        )

        # Get organization from user
        organization_id = getattr(current_user, "organization_id", "default")

        # Create scheduled job
        job = await service.schedule_job(
            organization_id=organization_id,
            request=schedule_request,
            user_id=current_user.id,
        )

        return _job_to_response(job)

    except ScheduleValidationError as e:
        logger.warning(f"Schedule validation error: {e}")
        raise HTTPException(
            status_code=400, detail="Invalid schedule request parameters"
        )
    except SchedulingServiceError as e:
        logger.error(f"Failed to create scheduled job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create scheduled job")


@router.get("", response_model=ScheduledJobListResponse)
async def list_scheduled_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    current_user: User = Depends(get_current_user),
    service: SchedulingService = Depends(_get_service),
) -> ScheduledJobListResponse:
    """
    List scheduled jobs for the current organization.
    """
    try:
        # Parse status filter
        status_filter = None
        if status:
            try:
                status_filter = ScheduleStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Valid: PENDING, DISPATCHED, CANCELLED, FAILED",
                )

        # Parse cursor
        start_key = None
        if cursor:
            import base64
            import json

            try:
                start_key = json.loads(base64.b64decode(cursor).decode())
            except Exception as e:
                logger.warning(f"Invalid cursor provided: {e}")
                raise HTTPException(status_code=400, detail="Invalid cursor")

        organization_id = getattr(current_user, "organization_id", "default")

        jobs, next_key = await service.list_scheduled_jobs(
            organization_id=organization_id,
            status=status_filter,
            limit=limit,
            start_key=start_key,
        )

        # Encode next cursor
        next_cursor = None
        if next_key:
            import base64
            import json

            next_cursor = base64.b64encode(json.dumps(next_key).encode()).decode()

        return ScheduledJobListResponse(
            jobs=[_job_to_response(job) for job in jobs],
            next_cursor=next_cursor,
        )

    except SchedulingServiceError as e:
        from src.api.dev_mock_fallback import should_serve_mock

        if should_serve_mock(e):
            logger.warning(
                "list_scheduled_jobs: AWS unavailable, returning empty list: %s", e
            )
            return ScheduledJobListResponse(jobs=[], next_cursor=None)
        logger.error(f"Failed to list scheduled jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list scheduled jobs")


# Literal-path routes MUST be declared before /{schedule_id} below so
# FastAPI matches paths like /timeline and /job-types as literals rather
# than parameterised job IDs. The /{schedule_id} route is greedy and would
# otherwise swallow these.


@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(
    start_date: datetime = Query(..., description="Start of time range (ISO8601)"),
    end_date: datetime = Query(..., description="End of time range (ISO8601)"),
    include_scheduled: bool = Query(True, description="Include scheduled jobs"),
    include_completed: bool = Query(True, description="Include completed jobs"),
    limit: int = Query(200, ge=1, le=500, description="Maximum entries"),
    current_user: User = Depends(get_current_user),
    service: SchedulingService = Depends(_get_service),
) -> TimelineResponse:
    """
    Get timeline entries for visualization.
    """
    try:
        organization_id = getattr(current_user, "organization_id", "default")

        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        entries = await service.get_timeline(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            include_scheduled=include_scheduled,
            include_completed=include_completed,
            limit=limit,
        )

        return TimelineResponse(
            entries=[
                TimelineEntryResponse(
                    job_id=e.job_id,
                    job_type=e.job_type,
                    status=e.status,
                    title=e.title,
                    scheduled_at=e.scheduled_at,
                    started_at=e.started_at,
                    completed_at=e.completed_at,
                    duration_seconds=e.duration_seconds,
                    repository_name=e.repository_name,
                    created_by=e.created_by,
                )
                for e in entries
            ],
            start_date=start_date,
            end_date=end_date,
        )

    except SchedulingServiceError as e:
        from src.api.dev_mock_fallback import should_serve_mock

        if should_serve_mock(e):
            logger.warning(
                "get_timeline: AWS unavailable, returning empty timeline: %s", e
            )
            return TimelineResponse(
                entries=[],
                start_date=start_date,
                end_date=end_date,
            )
        logger.error(f"Failed to get timeline: {e}")
        raise HTTPException(status_code=500, detail="Failed to get timeline")


@router.get("/job-types", response_model=List[Dict[str, str]])
async def get_job_types_inline() -> List[Dict[str, str]]:
    """Available job types for the scheduling UI dropdown.

    Re-declared above /{schedule_id} so the literal path matches first.
    Recurring-task router (registered earlier) also serves a richer
    /api/v1/schedule/job-types — that match wins because it's registered
    in main.py before this router.
    """
    return [
        {"value": jt.value, "label": jt.value.replace("_", " ").title()}
        for jt in JobType
    ]


@router.get("/{schedule_id}", response_model=ScheduledJobResponse)
async def get_scheduled_job(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    service: SchedulingService = Depends(_get_service),
) -> ScheduledJobResponse:
    """
    Get a specific scheduled job by ID.
    """
    try:
        organization_id = getattr(current_user, "organization_id", "default")

        job = await service.get_scheduled_job(
            organization_id=organization_id,
            schedule_id=schedule_id,
        )

        return _job_to_response(job)

    except ScheduleNotFoundError:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    except SchedulingServiceError as e:
        logger.error(f"Failed to get scheduled job: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scheduled job")


@router.put("/{schedule_id}", response_model=ScheduledJobResponse)
async def reschedule_job(
    schedule_id: str,
    request: RescheduleRequestModel,
    current_user: User = Depends(get_current_user),
    service: SchedulingService = Depends(_get_service),
) -> ScheduledJobResponse:
    """
    Reschedule a pending job to a new time.

    Only PENDING jobs can be rescheduled.
    """
    try:
        organization_id = getattr(current_user, "organization_id", "default")

        job = await service.reschedule_job(
            organization_id=organization_id,
            schedule_id=schedule_id,
            new_scheduled_at=request.scheduled_at,
            user_id=current_user.id,
        )

        return _job_to_response(job)

    except ScheduleNotFoundError:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    except ScheduleValidationError as e:
        logger.warning(f"Reschedule validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid reschedule parameters")
    except SchedulingServiceError as e:
        logger.error(f"Failed to reschedule job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to reschedule job")


@router.delete("/{schedule_id}", response_model=ScheduledJobResponse)
async def cancel_scheduled_job(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    service: SchedulingService = Depends(_get_service),
) -> ScheduledJobResponse:
    """
    Cancel a pending scheduled job.

    Only PENDING jobs can be cancelled.
    """
    try:
        organization_id = getattr(current_user, "organization_id", "default")

        job = await service.cancel_scheduled_job(
            organization_id=organization_id,
            schedule_id=schedule_id,
            user_id=current_user.id,
        )

        return _job_to_response(job)

    except ScheduleNotFoundError:
        raise HTTPException(status_code=404, detail="Scheduled job not found")
    except ScheduleValidationError as e:
        logger.warning(f"Cancel validation error: {e}")
        raise HTTPException(
            status_code=400, detail="Cannot cancel job in current state"
        )
    except SchedulingServiceError as e:
        logger.error(f"Failed to cancel scheduled job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cancel scheduled job")


# Queue Endpoints


@queue_router.get("/status", response_model=QueueStatusResponse)
async def get_queue_status(
    current_user: User = Depends(get_current_user),
    service: SchedulingService = Depends(_get_service),
) -> QueueStatusResponse:
    """
    Get current queue status and metrics.
    """
    try:
        organization_id = getattr(current_user, "organization_id", "default")

        status = await service.get_queue_status(organization_id=organization_id)

        return QueueStatusResponse(
            total_queued=status.total_queued,
            total_scheduled=status.total_scheduled,
            active_jobs=status.active_jobs,
            by_priority=status.by_priority,
            by_type=status.by_type,
            avg_wait_time_seconds=status.avg_wait_time_seconds,
            throughput_per_hour=status.throughput_per_hour,
            oldest_queued_at=status.oldest_queued_at,
            next_scheduled_at=status.next_scheduled_at,
        )

    except SchedulingServiceError as e:
        from src.api.dev_mock_fallback import should_serve_mock

        if should_serve_mock(e):
            logger.warning(
                "get_queue_status: AWS unavailable, returning idle queue: %s", e
            )
            return QueueStatusResponse(
                total_queued=0,
                total_scheduled=0,
                active_jobs=0,
                by_priority={},
                by_type={},
                avg_wait_time_seconds=0,
                throughput_per_hour=0,
                oldest_queued_at=None,
                next_scheduled_at=None,
            )
        logger.error(f"Failed to get queue status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get queue status")


# /timeline and /job-types are declared earlier in this module, before
# the parameterised /{schedule_id} route, so FastAPI matches the literal
# paths first. See the inline definitions above the /{schedule_id} block.
