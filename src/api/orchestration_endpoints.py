"""
Orchestration API Endpoints for Agent Orchestrator Job Management.

Provides REST API endpoints for submitting, tracking, and managing
agent orchestrator jobs.

Endpoints:
    POST /api/v1/orchestrate - Submit new orchestration job
    GET /api/v1/orchestrate/{job_id} - Get job status
    GET /api/v1/orchestrate - List user's jobs
    DELETE /api/v1/orchestrate/{job_id} - Cancel job
    GET /api/v1/orchestrate/health - Service health check
    WS /api/v1/orchestrate/{job_id}/stream - WebSocket for real-time updates
"""

import asyncio
import json
import logging
import os
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user, verify_token
from src.api.log_sanitizer import sanitize_log
from src.services.orchestration_service import (
    JobPriority,
    JobStatus,
    JobSubmission,
    OrchestrationJob,
    OrchestrationService,
    create_orchestration_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/orchestrate", tags=["orchestration"])

# =============================================================================
# Configuration Constants
# =============================================================================

# API validation limits
PROMPT_MIN_LENGTH = int(os.getenv("ORCHESTRATION_PROMPT_MIN_LENGTH", "10"))
PROMPT_MAX_LENGTH = int(os.getenv("ORCHESTRATION_PROMPT_MAX_LENGTH", "10000"))
LIST_JOBS_DEFAULT_LIMIT = int(os.getenv("ORCHESTRATION_LIST_JOBS_DEFAULT", "50"))
LIST_JOBS_MAX_LIMIT = int(os.getenv("ORCHESTRATION_LIST_JOBS_MAX", "100"))

# WebSocket configuration
WEBSOCKET_POLL_INTERVAL = float(os.getenv("WEBSOCKET_POLL_INTERVAL", "2"))
WEBSOCKET_CLIENT_TIMEOUT = float(os.getenv("WEBSOCKET_CLIENT_TIMEOUT", "5"))

# Global service instance (initialized on startup)
_orchestration_service: OrchestrationService | None = None


def get_orchestration_service() -> OrchestrationService:
    """Dependency to get orchestration service."""
    global _orchestration_service
    if _orchestration_service is None:
        _orchestration_service = create_orchestration_service()
    return _orchestration_service


# =============================================================================
# Pydantic Models
# =============================================================================


class OrchestrationRequest(BaseModel):
    """Request to submit an orchestration job."""

    prompt: str = Field(
        ...,
        min_length=PROMPT_MIN_LENGTH,
        max_length=PROMPT_MAX_LENGTH,
        description="The task prompt for the agent orchestrator",
        examples=["Refactor the DataProcessor's checksum method to be FIPS compliant"],
    )
    priority: str = Field(
        default="NORMAL",
        description="Job priority: LOW, NORMAL, HIGH, CRITICAL",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata for the job",
    )
    callback_url: str | None = Field(
        default=None,
        description="Webhook URL for completion notification",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Analyze the authentication module for security vulnerabilities and propose fixes",
                "priority": "HIGH",
                "metadata": {"repository": "myapp", "branch": "main"},
                "callback_url": "https://myapp.example.com/webhooks/orchestrator",
            }
        }


class OrchestrationResponse(BaseModel):
    """Response with job details."""

    job_id: str
    task_id: str
    status: str
    priority: str
    prompt: str
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_job(cls, job: OrchestrationJob) -> "OrchestrationResponse":
        """Create response from OrchestrationJob."""
        return cls(
            job_id=job.job_id,
            task_id=job.task_id,
            status=job.status.value,
            priority=job.priority.value,
            prompt=job.prompt,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            result=job.result,
            error_message=job.error_message,
            metadata=job.metadata,
        )


class JobListResponse(BaseModel):
    """Response with list of jobs."""

    jobs: list[OrchestrationResponse]
    total: int
    has_more: bool


class SubmitResponse(BaseModel):
    """Response after job submission."""

    job_id: str
    task_id: str
    status: str
    message: str
    poll_url: str
    websocket_url: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    mode: str
    queue_depth: int = 0
    details: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Helper Functions
# =============================================================================


async def validate_websocket_token(websocket: WebSocket) -> User | None:
    """
    Validate authentication token from WebSocket connection.

    Checks for token in:
    1. Query parameter: ?token=xxx
    2. Authorization header (during handshake)

    Returns:
        User object if authenticated, None if auth fails
    """
    # Try query parameter first
    token = websocket.query_params.get("token")

    # Try Authorization header if no query param
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    try:
        payload = verify_token(token)
        return User(
            sub=payload.get("sub", ""),
            email=payload.get("email"),
            name=payload.get("name") or payload.get("cognito:username"),
            groups=payload.get("cognito:groups", []),
        )
    except Exception as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        return None


async def publish_job_metrics(job: OrchestrationJob) -> None:
    """Publish job metrics to CloudWatch (background task)."""
    # TODO: Implement CloudWatch metrics publishing
    logger.debug(f"Would publish metrics for job {job.job_id}")


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "",
    response_model=SubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit orchestration job",
    description="Submit a new task to the agent orchestrator for autonomous processing.",
)
async def submit_job(
    request: OrchestrationRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),  # noqa: B008
    service: OrchestrationService = Depends(get_orchestration_service),  # noqa: B008
) -> SubmitResponse:
    """
    Submit a new orchestration job.

    The job is queued for processing by the agent orchestrator. Use the returned
    job_id to poll for status or connect via WebSocket for real-time updates.

    Requires authentication via Bearer token.

    Returns HTTP 202 Accepted with job details and polling URLs.
    """
    user_id = user.sub

    try:
        priority = JobPriority[request.priority.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority: {request.priority}. Must be LOW, NORMAL, HIGH, or CRITICAL",
        )

    submission = JobSubmission(
        prompt=request.prompt,
        user_id=user_id,
        priority=priority,
        metadata=request.metadata,
        callback_url=request.callback_url,
    )

    try:
        job = await service.submit_job(submission)
    except Exception as e:
        logger.error(f"Failed to submit job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit orchestration job",
        )

    # Publish metrics in background
    background_tasks.add_task(publish_job_metrics, job)

    return SubmitResponse(
        job_id=job.job_id,
        task_id=job.task_id,
        status=job.status.value,
        message="Job queued for processing. Poll the status endpoint or connect via WebSocket.",
        poll_url=f"/api/v1/orchestrate/{job.job_id}",
        websocket_url=f"/api/v1/orchestrate/{job.job_id}/stream",
    )


@router.get(
    "/{job_id}",
    response_model=OrchestrationResponse,
    summary="Get job status",
    description="Get the current status and details of an orchestration job.",
)
async def get_job(
    job_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
    service: OrchestrationService = Depends(get_orchestration_service),  # noqa: B008
) -> OrchestrationResponse:
    """
    Get job status by ID.

    Requires authentication. Users can only view their own jobs.

    Returns the current status, result (if completed), or error message (if failed).
    """
    job = await service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Verify user owns this job (or is admin)
    if job.user_id != user.sub and "admin" not in user.groups:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this job",
        )

    return OrchestrationResponse.from_job(job)


@router.get(
    "",
    response_model=JobListResponse,
    summary="List jobs",
    description="List orchestration jobs for the current user.",
)
async def list_jobs(
    status_filter: str | None = Query(  # noqa: B008
        None,
        alias="status",
        description="Filter by status: QUEUED, RUNNING, SUCCEEDED, FAILED",
    ),
    limit: int = Query(  # noqa: B008
        LIST_JOBS_DEFAULT_LIMIT,
        ge=1,
        le=LIST_JOBS_MAX_LIMIT,
        description="Maximum number of jobs to return",
    ),
    user: User = Depends(get_current_user),  # noqa: B008
    service: OrchestrationService = Depends(get_orchestration_service),  # noqa: B008
) -> JobListResponse:
    """
    List jobs for the current user.

    Requires authentication. Users see only their own jobs.
    Supports filtering by status and pagination.
    """
    user_id = user.sub

    job_status = None
    if status_filter:
        try:
            job_status = JobStatus[status_filter.upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )

    jobs = await service.list_jobs(user_id=user_id, status=job_status, limit=limit + 1)

    has_more = len(jobs) > limit
    if has_more:
        jobs = jobs[:limit]

    return JobListResponse(
        jobs=[OrchestrationResponse.from_job(j) for j in jobs],
        total=len(jobs),
        has_more=has_more,
    )


@router.delete(
    "/{job_id}",
    response_model=OrchestrationResponse,
    summary="Cancel job",
    description="Cancel a queued or running orchestration job.",
)
async def cancel_job(
    job_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
    service: OrchestrationService = Depends(get_orchestration_service),  # noqa: B008
) -> OrchestrationResponse:
    """
    Cancel an orchestration job.

    Requires authentication. Users can only cancel their own jobs.
    Only jobs in QUEUED or RUNNING status can be cancelled.
    """
    user_id = user.sub

    try:
        job = await service.cancel_job(job_id, user_id)
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return OrchestrationResponse.from_job(job)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check health of the orchestration service.",
    tags=["health"],
)
async def health_check(
    service: OrchestrationService = Depends(get_orchestration_service),  # noqa: B008
) -> HealthResponse:
    """Health check endpoint."""
    health = await service.health_check()

    return HealthResponse(
        status=health.get("status", "unknown"),
        mode=health.get("mode", "unknown"),
        queue_depth=health.get("queue_depth", 0),
        details=health,
    )


# =============================================================================
# WebSocket for Real-Time Updates (Phase 3)
# =============================================================================


class ConnectionManager:
    """Manages WebSocket connections for job streaming."""

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str):
        """Accept and track a new WebSocket connection."""
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)
        logger.info(f"WebSocket connected for job {sanitize_log(job_id)}")

    def disconnect(self, websocket: WebSocket, job_id: str):
        """Remove a WebSocket connection."""
        if job_id in self.active_connections:
            try:
                self.active_connections[job_id].remove(websocket)
                if not self.active_connections[job_id]:
                    del self.active_connections[job_id]
            except ValueError:
                pass
        logger.info(f"WebSocket disconnected for job {sanitize_log(job_id)}")

    async def broadcast_update(self, job_id: str, message: dict[str, Any]):
        """Broadcast update to all connections for a job."""
        if job_id in self.active_connections:
            for websocket in self.active_connections[job_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send WebSocket message: {e}")


# Global connection manager
connection_manager = ConnectionManager()


@router.websocket("/{job_id}/stream")
async def job_stream(
    websocket: WebSocket,
    job_id: str,
):
    """
    WebSocket endpoint for real-time job updates.

    Requires authentication via query parameter (?token=xxx) or Authorization header.

    Connect to receive streaming updates for a specific job.

    Message format:
    {
        "type": "status_update" | "progress" | "log" | "result" | "error",
        "job_id": "job-xxx",
        "data": { ... }
    }
    """
    # Validate authentication
    user = await validate_websocket_token(websocket)
    if not user:
        await websocket.close(code=4001, reason="Authentication required")
        return

    service = get_orchestration_service()

    # Verify job exists
    job = await service.get_job(job_id)
    if not job:
        await websocket.close(code=4004, reason="Job not found")
        return

    # Verify user owns this job (or is admin)
    if job.user_id != user.sub and "admin" not in user.groups:
        await websocket.close(code=4003, reason="Access denied")
        return

    await connection_manager.connect(websocket, job_id)

    try:
        # Send initial status
        await websocket.send_json(
            {
                "type": "status_update",
                "job_id": job_id,
                "data": OrchestrationResponse.from_job(job).model_dump(),
            }
        )

        # Poll for updates until job completes or client disconnects
        while True:
            # Check for client messages (ping/pong, cancel request)
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=WEBSOCKET_CLIENT_TIMEOUT,
                )
                message = json.loads(data)

                if message.get("action") == "cancel":
                    try:
                        job = await service.cancel_job(job_id, user.sub)
                        if job is None:
                            raise ValueError("Job not found")
                        await websocket.send_json(
                            {
                                "type": "status_update",
                                "job_id": job_id,
                                "data": OrchestrationResponse.from_job(
                                    job
                                ).model_dump(),
                            }
                        )
                    except PermissionError as e:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "job_id": job_id,
                                "data": {"message": str(e)},
                            }
                        )

            except asyncio.TimeoutError:
                # No message from client, continue polling
                pass

            # Poll job status
            job = await service.get_job(job_id)
            if not job:
                await websocket.send_json(
                    {
                        "type": "error",
                        "job_id": job_id,
                        "data": {"message": "Job not found"},
                    }
                )
                break

            # Send status update
            await websocket.send_json(
                {
                    "type": "status_update",
                    "job_id": job_id,
                    "data": OrchestrationResponse.from_job(job).model_dump(),
                }
            )

            # Check if job is in terminal state
            if job.status in (
                JobStatus.SUCCEEDED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
                JobStatus.TIMED_OUT,
            ):
                if job.result:
                    await websocket.send_json(
                        {
                            "type": "result",
                            "job_id": job_id,
                            "data": job.result,
                        }
                    )
                break

            # Wait before next poll
            await asyncio.sleep(WEBSOCKET_POLL_INTERVAL)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from job {sanitize_log(job_id)} stream")
    except Exception as e:
        logger.error(
            f"WebSocket error for job {sanitize_log(job_id)}: {sanitize_log(e)}"
        )
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "job_id": job_id,
                    "data": {"message": str(e)},
                }
            )
        except Exception:
            pass
    finally:
        connection_manager.disconnect(websocket, job_id)


# =============================================================================
# Startup/Shutdown Events
# =============================================================================


async def startup():
    """Initialize orchestration service on startup."""
    global _orchestration_service
    _orchestration_service = create_orchestration_service()
    logger.info("Orchestration service initialized")


async def shutdown():
    """Cleanup on shutdown."""
    global _orchestration_service
    _orchestration_service = None
    logger.info("Orchestration service shutdown")
