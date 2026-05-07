"""
Project Aura - Orchestrator Settings API Endpoints

REST API endpoints for configuring orchestrator deployment modes.
Enables users to toggle between on-demand jobs, warm pool, and hybrid modes.
Supports per-organization overrides with platform defaults.

Endpoints:
- GET  /api/v1/orchestrator/settings         - Get settings (platform or org)
- PUT  /api/v1/orchestrator/settings         - Update settings
- GET  /api/v1/orchestrator/settings/modes   - Get available deployment modes
- POST /api/v1/orchestrator/settings/switch  - Switch deployment mode
- GET  /api/v1/orchestrator/settings/status  - Get current mode status
- GET  /api/v1/orchestrator/settings/health  - Health check
- GET  /api/v1/orchestrator/hyperscale       - Get hyperscale settings (ADR-087)
- PUT  /api/v1/orchestrator/hyperscale       - Update hyperscale settings (ADR-087)
"""

import logging
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user, require_admin
from src.api.log_sanitizer import sanitize_log
from src.services.api_rate_limiter import (
    RateLimitResult,
    admin_rate_limit,
    critical_rate_limit,
    standard_rate_limit,
)
from src.services.cloudwatch_metrics_publisher import (
    CloudWatchMetricsPublisher,
    get_metrics_publisher,
)
from src.services.settings_persistence_service import (
    PersistenceMode,
    SettingsPersistenceService,
    create_settings_persistence_service,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(
    prefix="/api/v1/orchestrator/settings", tags=["Orchestrator Settings"]
)

# Service instance (initialized on first request)
_settings_service: SettingsPersistenceService | None = None


def get_settings_service() -> SettingsPersistenceService:
    """Get or create the settings persistence service."""
    global _settings_service
    if _settings_service is None:
        mode = (
            PersistenceMode.AWS
            if os.environ.get("USE_AWS_DYNAMODB")
            else PersistenceMode.MOCK
        )
        _settings_service = create_settings_persistence_service(mode=mode)
    return _settings_service


def get_cloudwatch_publisher() -> CloudWatchMetricsPublisher:
    """Get the CloudWatch metrics publisher."""
    return get_metrics_publisher()


async def publish_mode_change_metric(
    publisher: CloudWatchMetricsPublisher,
    event_type: str,
    organization_id: str | None,
    user: str,
    old_mode: str | None = None,
    new_mode: str | None = None,
    warm_pool_enabled: bool | None = None,
    hybrid_enabled: bool | None = None,
) -> None:
    """Background task to publish orchestrator mode metrics."""
    try:
        await publisher.publish_metric(
            namespace="Aura/Orchestrator",
            metric_name="OrchestratorModeChange",
            value=1.0,
            unit="Count",
            dimensions={
                "EventType": event_type,
                "OrganizationId": organization_id or "platform",
                "User": user,
                "OldMode": old_mode or "n/a",
                "NewMode": new_mode or "n/a",
            },
        )
    except Exception as e:
        logger.warning(f"Failed to publish mode change metric: {e}")


# ============================================================================
# Pydantic Models
# ============================================================================


class DeploymentMode(str, Enum):
    """Orchestrator deployment modes."""

    ON_DEMAND = "on_demand"  # EKS Jobs per request ($0 base cost)
    WARM_POOL = "warm_pool"  # Always-on replica (~$28/mo)
    HYBRID = "hybrid"  # Warm pool + burst jobs


class OrchestratorSettingsResponse(BaseModel):
    """Response model for orchestrator settings."""

    # Deployment mode settings
    on_demand_jobs_enabled: bool = Field(
        True, description="Enable on-demand EKS Jobs pattern ($0/mo base)"
    )
    warm_pool_enabled: bool = Field(
        False, description="Enable always-on warm pool replica (~$28/mo)"
    )
    hybrid_mode_enabled: bool = Field(
        False, description="Enable hybrid mode (warm pool + burst jobs)"
    )
    # Warm pool configuration
    warm_pool_replicas: int = Field(
        1, description="Number of warm pool replicas when enabled"
    )
    # Hybrid mode configuration
    hybrid_threshold_queue_depth: int = Field(
        5, description="Queue depth threshold to trigger burst jobs"
    )
    hybrid_scale_up_cooldown_seconds: int = Field(
        60, description="Minimum seconds between burst job scaling"
    )
    hybrid_max_burst_jobs: int = Field(10, description="Maximum concurrent burst jobs")
    # Cost estimates
    estimated_cost_per_job_usd: float = Field(
        0.15, description="Estimated cost per job (~15 min on m5.large)"
    )
    estimated_warm_pool_monthly_usd: float = Field(
        28.0, description="Estimated monthly cost for warm pool"
    )
    # Mode change tracking
    mode_change_cooldown_seconds: int = Field(
        300, description="Minimum seconds between mode changes"
    )
    last_mode_change_at: str | None = Field(
        None, description="ISO timestamp of last mode change"
    )
    last_mode_change_by: str | None = Field(
        None, description="User who made last mode change"
    )
    # Effective mode (computed)
    effective_mode: str = Field(
        "on_demand", description="Currently active deployment mode"
    )
    # Organization override indicator
    is_organization_override: bool = Field(
        False, description="True if these are org-specific settings"
    )
    organization_id: str | None = Field(
        None, description="Organization ID if org-specific settings"
    )


class UpdateOrchestratorSettingsRequest(BaseModel):
    """Request to update orchestrator settings."""

    on_demand_jobs_enabled: bool | None = Field(
        None, description="Enable on-demand EKS Jobs"
    )
    warm_pool_enabled: bool | None = Field(None, description="Enable warm pool")
    hybrid_mode_enabled: bool | None = Field(None, description="Enable hybrid mode")
    warm_pool_replicas: int | None = Field(
        None, ge=1, le=10, description="Warm pool replicas (1-10)"
    )
    hybrid_threshold_queue_depth: int | None = Field(
        None, ge=1, le=100, description="Hybrid queue depth threshold"
    )
    hybrid_max_burst_jobs: int | None = Field(
        None, ge=1, le=50, description="Max burst jobs"
    )


class SwitchModeRequest(BaseModel):
    """Request to switch deployment mode."""

    target_mode: DeploymentMode = Field(..., description="Target deployment mode")
    reason: str | None = Field(
        None, max_length=500, description="Reason for mode change"
    )
    force: bool = Field(
        False, description="Force change even during cooldown (admin only)"
    )


class ModeInfo(BaseModel):
    """Information about a deployment mode."""

    mode: str
    display_name: str
    description: str
    base_monthly_cost_usd: float
    cold_start_seconds: float
    recommended_for: list[str]


class ModeStatusResponse(BaseModel):
    """Current deployment mode status."""

    current_mode: str
    warm_pool_replicas_desired: int
    warm_pool_replicas_ready: int
    queue_depth: int
    active_burst_jobs: int
    can_switch_mode: bool
    cooldown_remaining_seconds: int
    last_mode_change_at: str | None
    last_mode_change_by: str | None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    mode: str


# ============================================================================
# Helper Functions
# ============================================================================


def compute_effective_mode(settings: dict[str, Any]) -> str:
    """Compute the effective deployment mode from settings."""
    if settings.get("hybrid_mode_enabled"):
        return "hybrid"
    elif settings.get("warm_pool_enabled"):
        return "warm_pool"
    else:
        return "on_demand"


def settings_to_response(
    settings: dict[str, Any],
    organization_id: str | None = None,
    is_override: bool = False,
) -> OrchestratorSettingsResponse:
    """Convert settings dict to API response."""
    return OrchestratorSettingsResponse(
        on_demand_jobs_enabled=settings.get("on_demand_jobs_enabled", True),
        warm_pool_enabled=settings.get("warm_pool_enabled", False),
        hybrid_mode_enabled=settings.get("hybrid_mode_enabled", False),
        warm_pool_replicas=settings.get("warm_pool_replicas", 1),
        hybrid_threshold_queue_depth=settings.get("hybrid_threshold_queue_depth", 5),
        hybrid_scale_up_cooldown_seconds=settings.get(
            "hybrid_scale_up_cooldown_seconds", 60
        ),
        hybrid_max_burst_jobs=settings.get("hybrid_max_burst_jobs", 10),
        estimated_cost_per_job_usd=settings.get("estimated_cost_per_job_usd", 0.15),
        estimated_warm_pool_monthly_usd=settings.get(
            "estimated_warm_pool_monthly_usd", 28.0
        ),
        mode_change_cooldown_seconds=settings.get("mode_change_cooldown_seconds", 300),
        last_mode_change_at=settings.get("last_mode_change_at"),
        last_mode_change_by=settings.get("last_mode_change_by"),
        effective_mode=compute_effective_mode(settings),
        is_organization_override=is_override,
        organization_id=organization_id,
    )


def check_cooldown(settings: dict[str, Any]) -> tuple[bool, int]:
    """
    Check if mode change is allowed based on cooldown.

    Returns:
        Tuple of (can_change, seconds_remaining)
    """
    last_change = settings.get("last_mode_change_at")
    cooldown = settings.get("mode_change_cooldown_seconds", 300)

    if not last_change:
        return True, 0

    try:
        last_change_dt = datetime.fromisoformat(last_change.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        elapsed = (now - last_change_dt).total_seconds()
        remaining = max(0, cooldown - elapsed)

        if remaining > 0:
            return False, int(remaining)
        return True, 0
    except Exception:
        return True, 0


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", response_model=OrchestratorSettingsResponse)
async def get_orchestrator_settings(
    request: Request,
    organization_id: str | None = Query(  # noqa: B008
        None, description="Organization ID for org-specific settings"
    ),
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Get orchestrator deployment mode settings.

    Returns platform defaults if no organization_id is specified.
    If organization_id is specified, returns org-specific settings
    (falling back to platform defaults for unset values).

    Requires authentication.
    """
    logger.info(
        f"User {sanitize_log(user.email)} retrieving orchestrator settings for org={sanitize_log(organization_id)}"
    )
    service = get_settings_service()

    # Get platform defaults
    platform_settings = await service.get_setting("platform", "orchestrator", {})
    platform_settings = platform_settings or {}

    if organization_id:
        # Get org-specific settings
        org_settings = await service.get_organization_setting(
            organization_id, "orchestrator", {}
        )
        org_settings = org_settings or {}

        if org_settings:
            # Merge: org settings override platform defaults
            merged = {**platform_settings, **org_settings}
            return settings_to_response(merged, organization_id, is_override=True)

    return settings_to_response(platform_settings)


@router.put("", response_model=OrchestratorSettingsResponse)
async def update_orchestrator_settings(
    request_body: UpdateOrchestratorSettingsRequest,
    background_tasks: BackgroundTasks,
    organization_id: str | None = Query(  # noqa: B008
        None, description="Organization ID for org-specific settings"
    ),
    user: User = Depends(require_admin),  # noqa: B008
    publisher: CloudWatchMetricsPublisher = Depends(  # noqa: B008
        get_cloudwatch_publisher
    ),  # noqa: B008
    rate_check: RateLimitResult = Depends(admin_rate_limit),  # noqa: B008
):
    """
    Update orchestrator deployment mode settings.

    If organization_id is specified, creates/updates org-specific override.
    Otherwise updates platform defaults.

    Requires admin role.

    Note: Changing mode settings may not take effect immediately.
    Use POST /switch endpoint to explicitly switch modes.
    """
    service = get_settings_service()
    updated_by = user.email or user.sub

    # Build updates dict from non-None fields
    updates: dict[str, Any] = {}
    if request_body.on_demand_jobs_enabled is not None:
        updates["on_demand_jobs_enabled"] = request_body.on_demand_jobs_enabled
    if request_body.warm_pool_enabled is not None:
        updates["warm_pool_enabled"] = request_body.warm_pool_enabled
    if request_body.hybrid_mode_enabled is not None:
        updates["hybrid_mode_enabled"] = request_body.hybrid_mode_enabled
    if request_body.warm_pool_replicas is not None:
        updates["warm_pool_replicas"] = request_body.warm_pool_replicas
    if request_body.hybrid_threshold_queue_depth is not None:
        updates["hybrid_threshold_queue_depth"] = (
            request_body.hybrid_threshold_queue_depth
        )
    if request_body.hybrid_max_burst_jobs is not None:
        updates["hybrid_max_burst_jobs"] = request_body.hybrid_max_burst_jobs

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    # Validate mode combination
    new_warm_pool = updates.get("warm_pool_enabled")
    new_hybrid = updates.get("hybrid_mode_enabled")

    if new_hybrid and not new_warm_pool:
        # If enabling hybrid, warm pool must be enabled too
        if new_warm_pool is False:
            raise HTTPException(
                status_code=400, detail="Hybrid mode requires warm_pool_enabled=true"
            )
        # Auto-enable warm pool if hybrid is enabled
        updates["warm_pool_enabled"] = True

    if organization_id:
        # Update org-specific settings
        settings_type = f"organization:{organization_id}"  # noqa: F841
        current = await service.get_organization_setting(
            organization_id, "orchestrator", {}
        )
        current = current or {}
    else:
        _settings_type = "platform"  # noqa: F841
        current = await service.get_setting("platform", "orchestrator", {})
        current = current or {}

    # Track mode change
    old_mode = compute_effective_mode(current)
    merged = {**current, **updates}
    new_mode = compute_effective_mode(merged)

    if old_mode != new_mode:
        updates["last_mode_change_at"] = datetime.now(timezone.utc).isoformat()
        updates["last_mode_change_by"] = updated_by

    # Save settings
    if organization_id:
        success = await service.update_organization_setting(
            organization_id, "orchestrator", updates, updated_by
        )
    else:
        # Update platform settings
        success = await service.update_setting(
            "platform", "orchestrator", updates, updated_by
        )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update settings")

    logger.info(
        f"Admin {sanitize_log(user.email)} updated orchestrator settings for org={sanitize_log(organization_id)}"
    )

    # Publish metric for mode change
    if old_mode != new_mode:
        background_tasks.add_task(
            publish_mode_change_metric,
            publisher=publisher,
            event_type="mode_updated",
            organization_id=organization_id,
            user=updated_by,
            old_mode=old_mode,
            new_mode=new_mode,
        )

    # Return updated settings
    if organization_id:
        platform_settings = await service.get_setting("platform", "orchestrator", {})
        platform_settings = platform_settings or {}
        org_settings = await service.get_organization_setting(
            organization_id, "orchestrator", {}
        )
        org_settings = org_settings or {}
        merged = {**platform_settings, **org_settings}
        return settings_to_response(merged, organization_id, is_override=True)
    else:
        updated = await service.get_setting("platform", "orchestrator", {})
        updated = updated or {}
        return settings_to_response(updated)


@router.get("/modes", response_model=list[ModeInfo])
async def get_available_modes(
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Get information about available deployment modes.

    Returns details about each mode including cost estimates
    and recommended use cases.
    """
    return [
        ModeInfo(
            mode="on_demand",
            display_name="On-Demand Jobs",
            description="EKS Jobs created per request. Zero base cost, pay per job execution.",
            base_monthly_cost_usd=0.0,
            cold_start_seconds=30.0,
            recommended_for=[
                "Low-volume workloads (<100 jobs/day)",
                "Cost-sensitive environments",
                "Dev/test environments",
                "Unpredictable traffic patterns",
            ],
        ),
        ModeInfo(
            mode="warm_pool",
            display_name="Warm Pool",
            description="Always-on replica for instant job processing. Fixed monthly cost.",
            base_monthly_cost_usd=28.0,
            cold_start_seconds=0.0,
            recommended_for=[
                "High-volume workloads (>500 jobs/day)",
                "Latency-sensitive applications",
                "Production environments",
                "Consistent traffic patterns",
            ],
        ),
        ModeInfo(
            mode="hybrid",
            display_name="Hybrid Mode",
            description="Warm pool + burst jobs. Best of both worlds for variable workloads.",
            base_monthly_cost_usd=28.0,
            cold_start_seconds=0.0,
            recommended_for=[
                "Variable workloads with peaks",
                "High-value production workloads",
                "Latency-sensitive with burst capacity",
                "Enterprise deployments",
            ],
        ),
    ]


@router.post("/switch", response_model=OrchestratorSettingsResponse)
async def switch_deployment_mode(
    request_body: SwitchModeRequest,
    background_tasks: BackgroundTasks,
    organization_id: str | None = Query(  # noqa: B008
        None, description="Organization ID for org-specific switch"
    ),
    user: User = Depends(require_admin),  # noqa: B008
    publisher: CloudWatchMetricsPublisher = Depends(  # noqa: B008
        get_cloudwatch_publisher
    ),  # noqa: B008
    rate_check: RateLimitResult = Depends(critical_rate_limit),  # noqa: B008
):
    """
    Explicitly switch deployment mode.

    This endpoint enforces cooldown periods to prevent mode thrashing.
    Use force=true to bypass cooldown (admin only, logged).

    Requires admin role.
    """
    service = get_settings_service()
    updated_by = user.email or user.sub

    # Get current settings
    if organization_id:
        platform_settings = await service.get_setting("platform", "orchestrator", {})
        platform_settings = platform_settings or {}
        org_settings = await service.get_organization_setting(
            organization_id, "orchestrator", {}
        )
        org_settings = org_settings or {}
        current = {**platform_settings, **org_settings}
    else:
        current_result = await service.get_setting("platform", "orchestrator", {})
        current = current_result or {}

    old_mode = compute_effective_mode(current)
    target_mode = request_body.target_mode.value

    # Check if already in target mode
    if old_mode == target_mode:
        return settings_to_response(
            current, organization_id, is_override=bool(organization_id)
        )

    # Check cooldown
    can_change, remaining = check_cooldown(current)
    if not can_change and not request_body.force:
        raise HTTPException(
            status_code=429,
            detail=f"Mode change cooldown active. {remaining} seconds remaining. "
            f"Use force=true to bypass (admin only).",
        )

    if request_body.force:
        logger.warning(
            f"Admin {sanitize_log(user.email)} forcing mode change during cooldown "
            f"(org={sanitize_log(organization_id)}, reason={sanitize_log(request_body.reason)})"
        )

    # Compute new settings based on target mode
    updates: dict[str, Any] = {
        "last_mode_change_at": datetime.now(timezone.utc).isoformat(),
        "last_mode_change_by": updated_by,
    }

    if target_mode == "on_demand":
        updates["on_demand_jobs_enabled"] = True
        updates["warm_pool_enabled"] = False
        updates["hybrid_mode_enabled"] = False
    elif target_mode == "warm_pool":
        updates["on_demand_jobs_enabled"] = False
        updates["warm_pool_enabled"] = True
        updates["hybrid_mode_enabled"] = False
    elif target_mode == "hybrid":
        updates["on_demand_jobs_enabled"] = True  # For burst jobs
        updates["warm_pool_enabled"] = True
        updates["hybrid_mode_enabled"] = True

    # Save settings
    if organization_id:
        success = await service.update_organization_setting(
            organization_id, "orchestrator", updates, updated_by
        )
    else:
        success = await service.update_setting(
            "platform", "orchestrator", updates, updated_by
        )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to switch mode")

    logger.info(
        f"Admin {sanitize_log(user.email)} switched orchestrator mode: {sanitize_log(old_mode)} -> {sanitize_log(target_mode)} "
        f"(org={sanitize_log(organization_id)}, reason={sanitize_log(request_body.reason)})"
    )

    # Publish metric
    background_tasks.add_task(
        publish_mode_change_metric,
        publisher=publisher,
        event_type="mode_switched",
        organization_id=organization_id,
        user=updated_by,
        old_mode=old_mode,
        new_mode=target_mode,
    )

    # Return updated settings
    if organization_id:
        platform_settings = await service.get_setting("platform", "orchestrator", {})
        platform_settings = platform_settings or {}
        org_settings = await service.get_organization_setting(
            organization_id, "orchestrator", {}
        )
        org_settings = org_settings or {}
        merged = {**platform_settings, **org_settings}
        return settings_to_response(merged, organization_id, is_override=True)
    else:
        updated = await service.get_setting("platform", "orchestrator", {})
        updated = updated or {}
        return settings_to_response(updated)


@router.get("/status", response_model=ModeStatusResponse)
async def get_mode_status(
    organization_id: str | None = Query(  # noqa: B008
        None, description="Organization ID for org-specific status"
    ),
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
):
    """
    Get current deployment mode operational status.

    Returns the current mode, warm pool status, queue depth,
    and whether mode switching is allowed.

    Requires authentication.
    """
    service = get_settings_service()

    # Get settings
    if organization_id:
        platform_settings = await service.get_setting("platform", "orchestrator", {})
        platform_settings = platform_settings or {}
        org_settings = await service.get_organization_setting(
            organization_id, "orchestrator", {}
        )
        org_settings = org_settings or {}
        settings = {**platform_settings, **org_settings}
    else:
        settings_result = await service.get_setting("platform", "orchestrator", {})
        settings = settings_result or {}

    current_mode = compute_effective_mode(settings)
    can_change, remaining = check_cooldown(settings)

    # TODO: Get actual K8s status from warm pool deployment
    # For now, return configured values
    warm_pool_replicas_desired = (
        settings.get("warm_pool_replicas", 1)
        if settings.get("warm_pool_enabled")
        else 0
    )

    return ModeStatusResponse(
        current_mode=current_mode,
        warm_pool_replicas_desired=warm_pool_replicas_desired,
        warm_pool_replicas_ready=0,  # TODO: Query K8s
        queue_depth=0,  # TODO: Query SQS
        active_burst_jobs=0,  # TODO: Query K8s Jobs
        can_switch_mode=can_change,
        cooldown_remaining_seconds=remaining,
        last_mode_change_at=settings.get("last_mode_change_at"),
        last_mode_change_by=settings.get("last_mode_change_by"),
    )


@router.get("/health", response_model=HealthResponse)
async def orchestrator_settings_health():
    """Health check for orchestrator settings service."""
    service = get_settings_service()
    # Determine mode based on environment
    mode = "aws" if service._dynamodb_client or not service._fallback_mode else "mock"
    return HealthResponse(
        status="healthy",
        service="orchestrator_settings",
        mode=mode,
    )


# ============================================================================
# Hyperscale Agent Orchestration (ADR-087)
# ============================================================================


class ExecutionTier(str, Enum):
    """Hyperscale execution tiers."""

    IN_PROCESS = "in_process"
    DISTRIBUTED_SIMPLE = "distributed_simple"
    DISTRIBUTED_ORCHESTRATED = "distributed_orchestrated"


class SecurityGateState(BaseModel):
    """State of a single security gate."""

    validated: bool = False
    validated_at: str | None = None


class HyperscaleSettingsResponse(BaseModel):
    """Response model for hyperscale orchestration settings."""

    enabled: bool = Field(
        False, description="Whether hyperscale orchestration is enabled"
    )
    execution_tier: str = Field("in_process", description="Current execution tier")
    max_parallel_agents: int = Field(10, description="Maximum parallel agents allowed")
    feasibility_gate_enabled: bool = Field(
        True, description="Whether feasibility gate is active"
    )
    cost_circuit_breaker_usd: float = Field(
        500, description="Cost circuit breaker threshold in USD"
    )
    security_gates: dict[str, SecurityGateState] = Field(
        default_factory=lambda: {
            "gate_1": SecurityGateState(),
            "gate_2": SecurityGateState(),
            "gate_3": SecurityGateState(),
        },
        description="Security gate validation states",
    )


class UpdateHyperscaleSettingsRequest(BaseModel):
    """Request to update hyperscale settings."""

    enabled: bool | None = Field(None, description="Enable/disable hyperscale")
    execution_tier: str | None = Field(None, description="Execution tier")
    max_parallel_agents: int | None = Field(
        None, ge=1, le=1000, description="Max parallel agents"
    )
    feasibility_gate_enabled: bool | None = Field(
        None, description="Enable feasibility gate"
    )
    cost_circuit_breaker_usd: float | None = Field(
        None, ge=0, le=10000, description="Cost circuit breaker USD"
    )


# Default hyperscale settings
DEFAULT_HYPERSCALE_SETTINGS = {
    "enabled": False,
    "execution_tier": "in_process",
    "max_parallel_agents": 10,
    "feasibility_gate_enabled": True,
    "cost_circuit_breaker_usd": 500,
    "security_gates": {
        "gate_1": {"validated": False, "validated_at": None},
        "gate_2": {"validated": False, "validated_at": None},
        "gate_3": {"validated": False, "validated_at": None},
    },
}

# In-memory store for hyperscale settings (per-org).
# TODO(ADR-087 Phase 2): persist to DynamoDB. The current dict is module-global
# state that is lost on pod restart and not coherent across replicas, which
# means the cost circuit breaker is best-effort only. See audit finding C2.
_hyperscale_settings: dict[str, dict] = {}


def _resolve_settings_key(requested_org_id: str | None, current_user: User) -> str:
    """Validate that the caller is allowed to read/write the requested org's settings.

    Tenant isolation rule (audit finding C1):
    - The "platform" key is reserved for platform admins only.
    - A regular user may only access their own ``current_user.organization_id``;
      passing a different ``organization_id`` query parameter yields 403.
    - A user without an ``organization_id`` claim may only access "platform",
      and only if they are a platform admin.
    """
    if requested_org_id is None or requested_org_id == "platform":
        if not current_user.is_platform_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="platform settings require platform_admin",
            )
        return "platform"

    # Platform admins may read/write any org's settings (e.g., support workflows).
    if current_user.is_platform_admin:
        return requested_org_id

    user_org = current_user.organization_id
    if user_org is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user has no organization claim",
        )
    if user_org != requested_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cannot access another organization's settings",
        )
    return requested_org_id


hyperscale_router = APIRouter(
    prefix="/api/v1/orchestrator/hyperscale", tags=["Hyperscale Orchestration"]
)


@hyperscale_router.get("", response_model=HyperscaleSettingsResponse)
async def get_hyperscale_settings(
    request: Request,
    organization_id: str | None = Query(None, description="Organization ID"),
    current_user: User = Depends(get_current_user),
    rate_limit: RateLimitResult = Depends(standard_rate_limit),
):
    """Get hyperscale orchestration settings (ADR-087)."""
    key = _resolve_settings_key(organization_id, current_user)
    settings = _hyperscale_settings.get(key, DEFAULT_HYPERSCALE_SETTINGS.copy())

    return HyperscaleSettingsResponse(**settings)


@hyperscale_router.put("", response_model=HyperscaleSettingsResponse)
async def update_hyperscale_settings(
    request: Request,
    updates: UpdateHyperscaleSettingsRequest,
    organization_id: str | None = Query(None, description="Organization ID"),
    current_user: User = Depends(require_admin),
    rate_limit: RateLimitResult = Depends(admin_rate_limit),
):
    """Update hyperscale orchestration settings (ADR-087)."""
    key = _resolve_settings_key(organization_id, current_user)
    current = _hyperscale_settings.get(key, DEFAULT_HYPERSCALE_SETTINGS.copy())

    # Apply updates
    update_data = updates.model_dump(exclude_none=True)
    current.update(update_data)

    # Enforce tier-based agent limits
    tier = current.get("execution_tier", "in_process")
    max_agents = current.get("max_parallel_agents", 10)

    tier_limits = {
        "in_process": (1, 20),
        "distributed_simple": (20, 200),
        "distributed_orchestrated": (200, 1000),
    }
    min_agents, max_allowed = tier_limits.get(tier, (1, 20))
    current["max_parallel_agents"] = max(min_agents, min(max_agents, max_allowed))

    _hyperscale_settings[key] = current

    logger.info(
        sanitize_log(
            f"Hyperscale settings updated by {current_user.email} "
            f"for {key}: tier={tier}, max_agents={current['max_parallel_agents']}"
        )
    )

    return HyperscaleSettingsResponse(**current)
