"""
Project Aura - Environment Provisioning API Endpoints

REST API endpoints for self-service test environment provisioning.
Enables users to create, manage, and terminate test environments.

Endpoints:
- GET  /api/v1/environments                 - List user's environments
- POST /api/v1/environments                 - Create new environment
- GET  /api/v1/environments/{id}            - Get environment details
- DELETE /api/v1/environments/{id}          - Terminate environment
- POST /api/v1/environments/{id}/extend     - Extend environment TTL
- GET  /api/v1/environments/templates       - List available templates
- GET  /api/v1/environments/quota           - Get user's quota status
- GET  /api/v1/environments/health          - Health check
"""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user
from src.services.api_rate_limiter import RateLimitResult, standard_rate_limit
from src.services.environment_provisioning_service import (
from src.api.log_sanitizer import sanitize_log
    EnvironmentConfig,
    EnvironmentProvisioningService,
    EnvironmentStatus,
    EnvironmentType,
    PersistenceMode,
    QuotaExceededError,
    TemplateNotFoundError,
    TestEnvironment,
    create_environment_service,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/environments", tags=["Environments"])

# Service instance (will be initialized on first request)
_environment_service: EnvironmentProvisioningService | None = None


def get_environment_service() -> EnvironmentProvisioningService:
    """Get or create the environment provisioning service."""
    global _environment_service
    if _environment_service is None:
        import os

        mode = (
            PersistenceMode.AWS
            if os.environ.get("USE_AWS_DYNAMODB")
            else PersistenceMode.MOCK
        )
        _environment_service = create_environment_service(mode=mode)
    return _environment_service


def set_environment_service(service: EnvironmentProvisioningService | None) -> None:
    """Set the environment service instance (for dependency injection/testing)."""
    global _environment_service
    _environment_service = service


# ============================================================================
# Pydantic Models - Requests
# ============================================================================


class CreateEnvironmentRequest(BaseModel):
    """Request to create a new test environment."""

    template_id: str = Field(..., description="Template to use for environment")
    display_name: str = Field(
        ..., min_length=1, max_length=100, description="Human-readable environment name"
    )
    description: str = Field(
        default="", max_length=500, description="Environment description"
    )
    ttl_hours: int | None = Field(
        default=None, ge=1, le=336, description="Custom TTL in hours (max 14 days)"
    )
    metadata: dict[str, str] = Field(
        default_factory=dict, description="Custom metadata tags"
    )


class ExtendTTLRequest(BaseModel):
    """Request to extend environment TTL."""

    additional_hours: int = Field(
        ..., ge=1, le=168, description="Hours to extend (max 7 days)"
    )
    reason: str = Field(default="", max_length=500, description="Reason for extension")


# ============================================================================
# Pydantic Models - Responses
# ============================================================================


class EnvironmentResponse(BaseModel):
    """Response model for environment details."""

    environment_id: str
    user_id: str
    organization_id: str
    environment_type: str
    template_id: str
    display_name: str
    status: str
    created_at: str
    expires_at: str
    dns_name: str
    approval_id: str | None
    resources: dict[str, Any]
    cost_estimate_daily: float
    last_activity_at: str
    metadata: dict[str, Any]


class EnvironmentListResponse(BaseModel):
    """Response model for environment list."""

    environments: list[EnvironmentResponse]
    total: int


class TemplateResponse(BaseModel):
    """Response model for environment template."""

    template_id: str
    name: str
    description: str
    environment_type: str
    default_ttl_hours: int
    max_ttl_hours: int
    cost_per_day: float
    resources: list[str]
    requires_approval: bool


class QuotaResponse(BaseModel):
    """Response model for user quota status."""

    user_id: str
    concurrent_limit: int
    active_count: int
    available: int
    monthly_budget: float
    monthly_spent: float
    monthly_remaining: float


class HealthResponse(BaseModel):
    """Response model for health check."""

    service: str
    mode: str
    table_name: str
    region: str
    templates_count: int
    healthy: bool
    dynamodb_status: str | None = None


# ============================================================================
# Helper Functions
# ============================================================================


def environment_to_response(env: TestEnvironment) -> EnvironmentResponse:
    """Convert TestEnvironment to API response."""
    return EnvironmentResponse(
        environment_id=env.environment_id,
        user_id=env.user_id,
        organization_id=env.organization_id,
        environment_type=env.environment_type.value,
        template_id=env.template_id,
        display_name=env.display_name,
        status=env.status.value,
        created_at=env.created_at,
        expires_at=env.expires_at,
        dns_name=env.dns_name,
        approval_id=env.approval_id,
        resources=env.resources,
        cost_estimate_daily=env.cost_estimate_daily,
        last_activity_at=env.last_activity_at,
        metadata=env.metadata,
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates() -> list[TemplateResponse]:
    """
    List available environment templates.

    Returns all templates that can be used to create environments.
    This endpoint is public (no authentication required).
    """
    service = get_environment_service()
    templates = service.get_available_templates()

    return [
        TemplateResponse(
            template_id=t.template_id,
            name=t.name,
            description=t.description,
            environment_type=t.environment_type.value,
            default_ttl_hours=t.default_ttl_hours,
            max_ttl_hours=t.max_ttl_hours,
            cost_per_day=t.cost_per_day,
            resources=t.resources,
            requires_approval=t.requires_approval,
        )
        for t in templates
    ]


@router.get("/quota", response_model=QuotaResponse)
async def get_quota(
    user: User = Depends(get_current_user),  # noqa: B008
) -> QuotaResponse:
    """
    Get user's quota status.

    Returns current usage and limits for environment provisioning.
    """
    service = get_environment_service()
    quota = await service.get_user_quota(user.sub)

    return QuotaResponse(**quota.to_dict())


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check for environment provisioning service.

    Returns service status and connectivity information.
    """
    service = get_environment_service()
    health = await service.health_check()

    return HealthResponse(**health)


@router.get("", response_model=EnvironmentListResponse)
async def list_environments(
    user: User = Depends(get_current_user),  # noqa: B008
    status: str | None = Query(  # noqa: B008
        default=None, description="Filter by status (active, terminated, etc.)"
    ),
    environment_type: str | None = Query(  # noqa: B008
        default=None,
        description="Filter by type (quick, standard, extended, compliance)",
    ),
    limit: int = Query(  # noqa: B008
        default=50, ge=1, le=100, description="Maximum results"
    ),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> EnvironmentListResponse:
    """
    List user's environments.

    Returns environments owned by the current user with optional filtering.
    """
    service = get_environment_service()

    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = EnvironmentStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: {[s.value for s in EnvironmentStatus]}",
            )

    # Parse environment type filter
    type_filter = None
    if environment_type:
        try:
            type_filter = EnvironmentType(environment_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid environment_type: {environment_type}. Valid values: {[t.value for t in EnvironmentType]}",
            )

    environments = await service.list_environments(
        user_id=user.sub,
        status=status_filter,
        environment_type=type_filter,
        limit=limit,
    )

    return EnvironmentListResponse(
        environments=[environment_to_response(env) for env in environments],
        total=len(environments),
    )


@router.post("", response_model=EnvironmentResponse, status_code=201)
async def create_environment(
    request: CreateEnvironmentRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> EnvironmentResponse:
    """
    Create a new test environment.

    Creates an environment from the specified template. May require HITL
    approval for extended or compliance environment types.
    """
    service = get_environment_service()

    # Build configuration
    config = EnvironmentConfig(
        template_id=request.template_id,
        display_name=request.display_name,
        description=request.description,
        ttl_hours=request.ttl_hours,
        metadata=request.metadata,
    )

    try:
        env = await service.create_environment(
            user_id=user.sub,
            organization_id=getattr(user, "organization_id", "default"),
            config=config,
        )
    except TemplateNotFoundError as e:
        logger.warning(f"Environment template not found: {e}")
        raise HTTPException(status_code=404, detail="Environment template not found")
    except QuotaExceededError as e:
        logger.warning(f"Environment quota exceeded: {e}")
        raise HTTPException(status_code=429, detail="Environment quota exceeded")

    logger.info(
        f"Environment {sanitize_log(env.environment_id)} created by user {sanitize_log(user.sub)} "
        f"(template={request.template_id}, status={env.status.value})"
    )

    return environment_to_response(env)


@router.get("/{environment_id}", response_model=EnvironmentResponse)
async def get_environment(
    environment_id: str = Path(..., description="Environment ID"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> EnvironmentResponse:
    """
    Get environment details.

    Returns details for a specific environment. Users can only view
    their own environments.
    """
    service = get_environment_service()
    env = await service.get_environment(environment_id)

    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")

    # Check ownership (non-admins can only see their own)
    if env.user_id != user.sub and "admin" not in user.groups:
        raise HTTPException(status_code=403, detail="Access denied")

    return environment_to_response(env)


@router.delete("/{environment_id}", status_code=204)
async def terminate_environment(
    environment_id: str = Path(..., description="Environment ID"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> None:
    """
    Terminate an environment.

    Initiates termination of the specified environment. Users can only
    terminate their own environments.
    """
    service = get_environment_service()
    env = await service.get_environment(environment_id)

    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")

    # Check ownership
    if env.user_id != user.sub and "admin" not in user.groups:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if already terminated/terminating
    if env.status in (EnvironmentStatus.TERMINATED, EnvironmentStatus.TERMINATING):
        raise HTTPException(
            status_code=400,
            detail=f"Environment is already {env.status.value}",
        )

    success = await service.terminate_environment(
        environment_id=environment_id,
        terminated_by=user.sub,
        reason="User requested termination",
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to terminate environment")

    logger.info(f"Environment {sanitize_log(environment_id)} terminated by user {sanitize_log(user.sub)}")


@router.post("/{environment_id}/extend", response_model=EnvironmentResponse)
async def extend_environment(
    request: ExtendTTLRequest,
    environment_id: str = Path(..., description="Environment ID"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> EnvironmentResponse:
    """
    Extend environment TTL.

    Extends the time-to-live of an environment. May require HITL
    approval if extending beyond certain thresholds.
    """
    service = get_environment_service()
    env = await service.get_environment(environment_id)

    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")

    # Check ownership
    if env.user_id != user.sub and "admin" not in user.groups:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if environment is in a state that can be extended
    if env.status not in (EnvironmentStatus.ACTIVE, EnvironmentStatus.EXPIRING):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot extend environment in {env.status.value} status",
        )

    extended = await service.extend_ttl(
        environment_id=environment_id,
        additional_hours=request.additional_hours,
        extended_by=user.sub,
    )

    if not extended:
        raise HTTPException(status_code=500, detail="Failed to extend environment TTL")

    logger.info(
        f"Environment {sanitize_log(environment_id)} TTL extended by {sanitize_log(request.additional_hours)}h "
        f"by user {user.sub}"
    )

    return environment_to_response(extended)
