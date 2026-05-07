"""
Project Aura - Recurring Task API Endpoints

REST API endpoints for managing recurring scheduled tasks.
ADR-055 Phase 3: Recurring Tasks and Advanced Features

Endpoints:
- GET    /api/v1/schedule/recurring            - List recurring tasks
- POST   /api/v1/schedule/recurring            - Create recurring task
- GET    /api/v1/schedule/recurring/{task_id}  - Get task by ID
- PUT    /api/v1/schedule/recurring/{task_id}  - Update task
- DELETE /api/v1/schedule/recurring/{task_id}  - Delete task
- POST   /api/v1/schedule/recurring/{task_id}/toggle - Enable/disable task
- GET    /api/v1/schedule/recurring/due        - Get due tasks (for scheduler)
- POST   /api/v1/schedule/cron/validate        - Validate cron expression
- POST   /api/v1/schedule/cron/describe        - Describe cron expression
- GET    /api/v1/schedule/job-types            - List available job types
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.log_sanitizer import sanitize_log
from src.services.recurring_task_service import (
    JobType,
    RecurringTask,
    RecurringTaskService,
    describe_cron,
    get_recurring_task_service,
    validate_cron_expression,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/schedule", tags=["Scheduling"])

# ============================================================================
# Pydantic Models
# ============================================================================


class CreateRecurringTaskRequest(BaseModel):
    """Request to create a recurring task."""

    name: str = Field(..., min_length=1, max_length=200, description="Task name")
    job_type: str = Field(..., description="Type of job to run")
    cron_expression: str = Field(
        ..., description="Cron schedule (minute hour day-month month day-week)"
    )
    description: str = Field(default="", max_length=1000)
    target_repository: Optional[str] = Field(
        default=None, description="Target repository URL or name"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Job-specific parameters"
    )
    enabled: bool = Field(default=True, description="Whether task is enabled")
    timeout_seconds: int = Field(
        default=3600, ge=60, le=86400, description="Execution timeout"
    )
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts")
    notification_emails: list[str] = Field(
        default_factory=list, description="Emails for notifications"
    )
    tags: list[str] = Field(default_factory=list, description="Task tags")


class UpdateRecurringTaskRequest(BaseModel):
    """Request to update a recurring task."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    cron_expression: Optional[str] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)
    target_repository: Optional[str] = Field(default=None)
    parameters: Optional[dict[str, Any]] = Field(default=None)
    timeout_seconds: Optional[int] = Field(default=None, ge=60, le=86400)
    max_retries: Optional[int] = Field(default=None, ge=0, le=10)
    notification_emails: Optional[list[str]] = Field(default=None)
    tags: Optional[list[str]] = Field(default=None)


class ToggleTaskRequest(BaseModel):
    """Request to toggle task enabled state."""

    enabled: bool = Field(..., description="Whether to enable or disable the task")


class CronValidationRequest(BaseModel):
    """Request to validate a cron expression."""

    cron_expression: str = Field(..., description="Cron expression to validate")


class CronValidationResponse(BaseModel):
    """Response for cron validation."""

    valid: bool
    error: Optional[str] = None
    description: Optional[str] = None
    next_runs: list[str] = Field(default_factory=list)


class RecurringTaskResponse(BaseModel):
    """Response containing a recurring task."""

    task_id: str
    name: str
    job_type: str
    cron_expression: str
    enabled: bool
    description: str = ""
    target_repository: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    organization_id: str = "default"
    created_by: str = "system"
    next_run: Optional[str] = None
    last_run: Optional[str] = None
    run_count: int = 0
    failure_count: int = 0
    timeout_seconds: int = 3600
    max_retries: int = 3
    notification_emails: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""


class RecurringTaskListResponse(BaseModel):
    """Response containing a list of recurring tasks."""

    tasks: list[RecurringTaskResponse]
    total: int


class JobTypeInfo(BaseModel):
    """Information about a job type."""

    value: str
    label: str
    description: str


class JobTypesResponse(BaseModel):
    """Response containing available job types."""

    job_types: list[JobTypeInfo]


# ============================================================================
# Helper Functions
# ============================================================================


def task_to_response(task: RecurringTask) -> RecurringTaskResponse:
    """Convert a RecurringTask to API response."""
    return RecurringTaskResponse(**task.to_dict())


def get_user_info(request) -> tuple[str, str]:
    """Extract user info from request (placeholder for auth integration)."""
    # In production, extract from JWT token
    user_id = getattr(request.state, "user_id", "anonymous")
    org_id = getattr(request.state, "organization_id", "default")
    return user_id, org_id


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/recurring", response_model=RecurringTaskListResponse)
async def list_recurring_tasks(
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    service: RecurringTaskService = Depends(get_recurring_task_service),
) -> RecurringTaskListResponse:
    """List recurring tasks with optional filters."""
    tasks = await service.list_tasks(enabled=enabled, job_type=job_type, limit=limit)
    return RecurringTaskListResponse(
        tasks=[task_to_response(t) for t in tasks], total=len(tasks)
    )


@router.post("/recurring", response_model=RecurringTaskResponse, status_code=201)
async def create_recurring_task(
    request: CreateRecurringTaskRequest,
    service: RecurringTaskService = Depends(get_recurring_task_service),
) -> RecurringTaskResponse:
    """Create a new recurring task."""
    try:
        task = await service.create_task(
            name=request.name,
            job_type=request.job_type,
            cron_expression=request.cron_expression,
            description=request.description,
            target_repository=request.target_repository,
            parameters=request.parameters,
            enabled=request.enabled,
            timeout_seconds=request.timeout_seconds,
            max_retries=request.max_retries,
            notification_emails=request.notification_emails,
            tags=request.tags,
        )
        return task_to_response(task)
    except ValueError as e:
        logger.warning(f"Recurring task validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid task configuration")
    except Exception as e:
        logger.error(f"Failed to create recurring task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create task")


# NOTE: This route MUST come before /recurring/{task_id} to avoid path conflicts
@router.get("/recurring/due", response_model=RecurringTaskListResponse)
async def get_due_tasks(
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    service: RecurringTaskService = Depends(get_recurring_task_service),
) -> RecurringTaskListResponse:
    """Get tasks that are due for execution (for scheduler service)."""
    tasks = await service.get_due_tasks(limit=limit)
    return RecurringTaskListResponse(
        tasks=[task_to_response(t) for t in tasks], total=len(tasks)
    )


@router.get("/recurring/{task_id}", response_model=RecurringTaskResponse)
async def get_recurring_task(
    task_id: str,
    service: RecurringTaskService = Depends(get_recurring_task_service),
) -> RecurringTaskResponse:
    """Get a recurring task by ID."""
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_to_response(task)


@router.put("/recurring/{task_id}", response_model=RecurringTaskResponse)
async def update_recurring_task(
    task_id: str,
    request: UpdateRecurringTaskRequest,
    service: RecurringTaskService = Depends(get_recurring_task_service),
) -> RecurringTaskResponse:
    """Update a recurring task."""
    # Build updates dict, excluding None values
    updates = {k: v for k, v in request.model_dump().items() if v is not None}

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    try:
        task = await service.update_task(task_id, updates)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task_to_response(task)
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except ValueError as e:
        logger.warning(f"Task update validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid task update parameters")
    except Exception as e:
        logger.error(
            f"Failed to update task {sanitize_log(task_id)}: {sanitize_log(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to update task")


@router.delete("/recurring/{task_id}", status_code=204)
async def delete_recurring_task(
    task_id: str,
    hard: bool = Query(False, description="Permanently delete"),
    service: RecurringTaskService = Depends(get_recurring_task_service),
) -> None:
    """Delete a recurring task."""
    success = await service.delete_task(task_id, hard_delete=hard)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")


@router.post("/recurring/{task_id}/toggle", response_model=RecurringTaskResponse)
async def toggle_recurring_task(
    task_id: str,
    request: ToggleTaskRequest,
    service: RecurringTaskService = Depends(get_recurring_task_service),
) -> RecurringTaskResponse:
    """Enable or disable a recurring task."""
    task = await service.toggle_task(task_id, request.enabled)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_to_response(task)


@router.post("/cron/validate", response_model=CronValidationResponse)
async def validate_cron(request: CronValidationRequest) -> CronValidationResponse:
    """Validate a cron expression and return description."""
    is_valid, error = validate_cron_expression(request.cron_expression)

    if not is_valid:
        return CronValidationResponse(valid=False, error=error)

    # Get description
    description = describe_cron(request.cron_expression)

    # Calculate next few runs
    from datetime import datetime, timezone

    from src.services.recurring_task_service import calculate_next_run

    next_runs = []
    try:
        current = datetime.now(timezone.utc)
        for _ in range(5):
            next_time = calculate_next_run(request.cron_expression, current)
            next_runs.append(next_time.isoformat())
            current = next_time
    except Exception:
        pass  # Skip if can't calculate

    return CronValidationResponse(
        valid=True, description=description, next_runs=next_runs
    )


@router.post("/cron/describe")
async def describe_cron_expression(request: CronValidationRequest) -> dict[str, str]:
    """Get human-readable description of a cron expression."""
    is_valid, error = validate_cron_expression(request.cron_expression)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {error}")

    description = describe_cron(request.cron_expression)
    return {"cron_expression": request.cron_expression, "description": description}


@router.get("/job-types", response_model=JobTypesResponse)
async def list_job_types() -> JobTypesResponse:
    """List available job types for scheduling."""
    job_type_descriptions = {
        JobType.SECURITY_SCAN: "Run automated security vulnerability scan",
        JobType.CODE_REVIEW: "Perform AI-assisted code review",
        JobType.DEPENDENCY_UPDATE: "Check and update dependencies",
        JobType.BACKUP: "Create backup of repository data",
        JobType.COMPLIANCE_CHECK: "Run compliance and policy checks",
        JobType.PATCH_GENERATION: "Generate security patches for vulnerabilities",
        JobType.CUSTOM: "Custom job with user-defined parameters",
    }

    job_types = [
        JobTypeInfo(
            value=jt.value,
            label=jt.value.replace("_", " ").title(),
            description=job_type_descriptions.get(jt, ""),
        )
        for jt in JobType
    ]

    return JobTypesResponse(job_types=job_types)
