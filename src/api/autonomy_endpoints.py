"""
Project Aura - Autonomy Configuration API Endpoints

REST API endpoints for configuring organization autonomy policies.
Enables users to toggle HITL on/off and customize autonomy levels
for different operations, severities, and repositories.

Endpoints:
- GET  /api/v1/autonomy/policies                      - List policies for organization
- POST /api/v1/autonomy/policies                      - Create new policy
- GET  /api/v1/autonomy/policies/{policy_id}          - Get policy details
- PUT  /api/v1/autonomy/policies/{policy_id}          - Update policy
- DELETE /api/v1/autonomy/policies/{policy_id}        - Delete (deactivate) policy
- PUT  /api/v1/autonomy/policies/{policy_id}/toggle   - Toggle HITL on/off
- POST /api/v1/autonomy/policies/{policy_id}/override - Add override
- DELETE /api/v1/autonomy/policies/{policy_id}/override - Remove override
- GET  /api/v1/autonomy/presets                       - Get available presets
- POST /api/v1/autonomy/check                         - Check if HITL required for action
- GET  /api/v1/autonomy/decisions                     - Get autonomy decisions history
"""

import logging
from enum import Enum

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
)
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user, require_admin
from src.services.api_rate_limiter import (
    RateLimitResult,
    admin_rate_limit,
    critical_rate_limit,
    standard_rate_limit,
)
from src.services.autonomy_policy_service import (
    AutonomyLevel,
    AutonomyPolicy,
    AutonomyPolicyService,
    AutonomyServiceMode,
    create_autonomy_policy_service,
)
from src.services.cloudwatch_metrics_publisher import (
    CloudWatchMetricsPublisher,
    get_metrics_publisher,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/autonomy", tags=["Autonomy"])

# Service instance (will be initialized on first request)
_autonomy_service: AutonomyPolicyService | None = None


def get_autonomy_service() -> AutonomyPolicyService:
    """Get or create the autonomy policy service."""
    global _autonomy_service
    if _autonomy_service is None:
        import os

        mode = (
            AutonomyServiceMode.AWS
            if os.environ.get("USE_AWS_DYNAMODB")
            else AutonomyServiceMode.MOCK
        )
        _autonomy_service = create_autonomy_policy_service(mode=mode)
    return _autonomy_service


def get_cloudwatch_publisher() -> CloudWatchMetricsPublisher:
    """Get the CloudWatch metrics publisher."""
    return get_metrics_publisher()


async def publish_autonomy_metric(
    publisher: CloudWatchMetricsPublisher,
    event_type: str,
    organization_id: str,
    policy_id: str | None = None,
    user: str | None = None,
    hitl_enabled: bool | None = None,
    autonomy_level: str | None = None,
    severity: str | None = None,
    operation: str | None = None,
    auto_approved: bool = False,
) -> None:
    """Background task to publish autonomy metrics."""
    try:
        await publisher.publish_autonomy_event(
            event_type=event_type,
            organization_id=organization_id,
            policy_id=policy_id,
            user=user,
            hitl_enabled=hitl_enabled,
            autonomy_level=autonomy_level,
            severity=severity,
            operation=operation,
            auto_approved=auto_approved,
        )
    except Exception as e:
        logger.warning(f"Failed to publish autonomy metric: {e}")


# ============================================================================
# Pydantic Models for API Requests/Responses
# ============================================================================


class AutonomyLevelModel(str, Enum):
    """Autonomy level options for API."""

    FULL_HITL = "full_hitl"
    CRITICAL_HITL = "critical_hitl"
    AUDIT_ONLY = "audit_only"
    FULL_AUTONOMOUS = "full_autonomous"


class CreatePolicyRequest(BaseModel):
    """Request to create a new autonomy policy."""

    organization_id: str = Field(..., description="Organization identifier")
    name: str = Field(default="Default Policy", description="Policy name")
    description: str = Field(default="", description="Policy description")
    hitl_enabled: bool = Field(default=True, description="Master HITL toggle")
    default_level: AutonomyLevelModel = Field(
        default=AutonomyLevelModel.CRITICAL_HITL, description="Default autonomy level"
    )
    preset_name: str | None = Field(default=None, description="Create from preset")


class UpdatePolicyRequest(BaseModel):
    """Request to update an existing policy."""

    name: str | None = Field(default=None, description="New policy name")
    description: str | None = Field(default=None, description="New description")
    hitl_enabled: bool | None = Field(default=None, description="HITL toggle")
    default_level: AutonomyLevelModel | None = Field(
        default=None, description="Default level"
    )


class ToggleHITLRequest(BaseModel):
    """Request to toggle HITL on/off."""

    hitl_enabled: bool = Field(..., description="New HITL state")
    reason: str | None = Field(default=None, description="Reason for change")


class AddOverrideRequest(BaseModel):
    """Request to add an autonomy override."""

    override_type: str = Field(
        ..., description="Type: 'severity', 'operation', or 'repository'"
    )
    context_value: str = Field(
        ..., description="Value to match (e.g., 'HIGH', 'production_deployment')"
    )
    autonomy_level: AutonomyLevelModel = Field(
        ..., description="Autonomy level for this context"
    )
    reason: str | None = Field(default=None, description="Reason for override")


class RemoveOverrideRequest(BaseModel):
    """Request to remove an autonomy override."""

    override_type: str = Field(
        ..., description="Type: 'severity', 'operation', or 'repository'"
    )
    context_value: str = Field(..., description="Value to remove")


class CheckHITLRequest(BaseModel):
    """Request to check if HITL is required."""

    policy_id: str = Field(..., description="Policy to check against")
    severity: str = Field(..., description="Action severity (CRITICAL/HIGH/MEDIUM/LOW)")
    operation: str = Field(..., description="Operation type")
    repository: str = Field(default="", description="Repository (optional)")


class CheckHITLResponse(BaseModel):
    """Response for HITL check."""

    requires_hitl: bool = Field(..., description="Whether HITL approval is required")
    autonomy_level: str = Field(..., description="Autonomy level for this context")
    reason: str = Field(..., description="Explanation of the decision")
    guardrail_triggered: bool = Field(
        default=False, description="Was a guardrail triggered"
    )


class PolicyResponse(BaseModel):
    """Response model for policy details."""

    policy_id: str
    organization_id: str
    name: str
    description: str
    hitl_enabled: bool
    default_level: str
    severity_overrides: dict[str, str]
    operation_overrides: dict[str, str]
    repository_overrides: dict[str, str]
    guardrails: list[str]
    created_at: str
    updated_at: str
    created_by: str | None
    updated_by: str | None
    is_active: bool
    preset_name: str | None


class PresetResponse(BaseModel):
    """Response model for preset info."""

    name: str
    display_name: str
    description: str
    default_level: str
    hitl_enabled: bool


class DecisionResponse(BaseModel):
    """Response model for autonomy decision."""

    decision_id: str
    policy_id: str
    organization_id: str
    execution_id: str
    severity: str
    operation: str
    repository: str
    autonomy_level: str
    hitl_required: bool
    hitl_bypassed: bool
    auto_approved: bool
    timestamp: str


# ============================================================================
# Helper Functions
# ============================================================================


def policy_to_response(policy: AutonomyPolicy) -> PolicyResponse:
    """Convert AutonomyPolicy to API response."""
    return PolicyResponse(
        policy_id=policy.policy_id,
        organization_id=policy.organization_id,
        name=policy.name,
        description=policy.description,
        hitl_enabled=policy.hitl_enabled,
        default_level=policy.default_level.value,
        severity_overrides={k: v.value for k, v in policy.severity_overrides.items()},
        operation_overrides={k: v.value for k, v in policy.operation_overrides.items()},
        repository_overrides={
            k: v.value for k, v in policy.repository_overrides.items()
        },
        guardrails=policy.guardrails,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        created_by=policy.created_by,
        updated_by=policy.updated_by,
        is_active=policy.is_active,
        preset_name=policy.preset_name,
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/policies", response_model=list[PolicyResponse])
async def list_policies(
    request: Request,
    organization_id: str = Query(  # noqa: B008
        ..., description="Organization to list policies for"
    ),  # noqa: B008
    include_inactive: bool = Query(  # noqa: B008
        False, description="Include deactivated policies"
    ),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(  # noqa: B008
        standard_rate_limit
    ),  # 60 req/min - read op  # noqa: B008
):
    """
    List all autonomy policies for an organization.

    Returns active policies by default. Use include_inactive=true to see all.
    Requires authentication.
    """
    logger.info(f"User {user.email} listing policies for org {organization_id}")
    service = get_autonomy_service()
    policies = service.list_policies(
        organization_id=organization_id,
        include_inactive=include_inactive,
    )
    return [policy_to_response(p) for p in policies]


@router.post("/policies", response_model=PolicyResponse, status_code=201)
async def create_policy(
    request: CreatePolicyRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_admin),  # noqa: B008
    publisher: CloudWatchMetricsPublisher = Depends(  # noqa: B008
        get_cloudwatch_publisher
    ),  # noqa: B008
    rate_check: RateLimitResult = Depends(  # noqa: B008
        admin_rate_limit
    ),  # 5 req/min - admin op  # noqa: B008
):
    """
    Create a new autonomy policy.

    Requires admin role.
    Can optionally create from a preset by specifying preset_name.
    Available presets: defense_contractor, financial_services, healthcare,
    fintech_startup, enterprise_standard, internal_tools, fully_autonomous
    """
    service = get_autonomy_service()
    created_by = user.email or user.sub

    try:
        if request.preset_name:
            policy = service.create_policy_from_preset(
                organization_id=request.organization_id,
                preset_name=request.preset_name,
                created_by=created_by,
            )
        else:
            policy = service.create_policy(
                organization_id=request.organization_id,
                name=request.name,
                description=request.description,
                hitl_enabled=request.hitl_enabled,
                default_level=AutonomyLevel(request.default_level.value),
                created_by=created_by,
            )

        logger.info(f"Admin {user.email} created autonomy policy {policy.policy_id}")

        # Publish metric in background
        background_tasks.add_task(
            publish_autonomy_metric,
            publisher=publisher,
            event_type="policy_created",
            organization_id=request.organization_id,
            policy_id=policy.policy_id,
            user=created_by,
            hitl_enabled=policy.hitl_enabled,
        )

        return policy_to_response(policy)

    except ValueError as e:
        logger.warning(f"Policy creation validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid policy configuration")


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str = Path(..., description="Policy ID to retrieve"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    """Get details of a specific autonomy policy. Requires authentication."""
    logger.info(f"User {user.email} retrieving policy {policy_id}")
    service = get_autonomy_service()
    policy = service.get_policy(policy_id)

    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    return policy_to_response(policy)


@router.put("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    request: UpdatePolicyRequest,
    policy_id: str = Path(..., description="Policy ID to update"),  # noqa: B008
    user: User = Depends(require_admin),  # noqa: B008
):
    """Update an existing autonomy policy. Requires admin role."""
    service = get_autonomy_service()
    updated_by = user.email or user.sub

    # Build updates dict from non-None fields
    updates: dict[str, str | bool] = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.description is not None:
        updates["description"] = request.description
    if request.hitl_enabled is not None:
        updates["hitl_enabled"] = request.hitl_enabled
    if request.default_level is not None:
        updates["default_level"] = request.default_level.value

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    policy = service.update_policy(
        policy_id=policy_id,
        updates=updates,
        updated_by=updated_by,
    )

    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    logger.info(f"Admin {user.email} updated autonomy policy {policy_id}")
    return policy_to_response(policy)


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: str = Path(..., description="Policy ID to delete"),  # noqa: B008
    reason: str = Query(default=None, description="Reason for deletion"),  # noqa: B008
    user: User = Depends(require_admin),  # noqa: B008
):
    """Delete (deactivate) an autonomy policy. Requires admin role."""
    service = get_autonomy_service()
    deleted_by = user.email or user.sub

    success = service.delete_policy(
        policy_id=policy_id,
        deleted_by=deleted_by,
        reason=reason,
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    logger.info(f"Admin {user.email} deleted autonomy policy {policy_id}")


@router.put("/policies/{policy_id}/toggle", response_model=PolicyResponse)
async def toggle_hitl(
    request: ToggleHITLRequest,
    background_tasks: BackgroundTasks,
    policy_id: str = Path(..., description="Policy ID"),  # noqa: B008
    user: User = Depends(require_admin),  # noqa: B008
    publisher: CloudWatchMetricsPublisher = Depends(  # noqa: B008
        get_cloudwatch_publisher
    ),  # noqa: B008
    rate_check: RateLimitResult = Depends(  # noqa: B008
        critical_rate_limit
    ),  # 2 req/min - critical op
):
    """
    Toggle HITL on or off for a policy.

    Requires admin role.
    This is the master switch for human-in-the-loop requirements.
    When disabled, only guardrails (production_deployment, credential_modification, etc.)
    will still require human approval.

    Note: This action is logged to CloudWatch for compliance dashboards.
    """
    service = get_autonomy_service()
    updated_by = user.email or user.sub

    policy = service.toggle_hitl(
        policy_id=policy_id,
        hitl_enabled=request.hitl_enabled,
        updated_by=updated_by,
        reason=request.reason,
    )

    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    action = "enabled" if request.hitl_enabled else "disabled"
    logger.info(f"Admin {user.email} {action} HITL for policy {policy_id}")

    # Publish HITL toggle metric for compliance dashboards
    background_tasks.add_task(
        publish_autonomy_metric,
        publisher=publisher,
        event_type="hitl_toggled",
        organization_id=policy.organization_id,
        policy_id=policy_id,
        user=updated_by,
        hitl_enabled=request.hitl_enabled,
    )

    return policy_to_response(policy)


@router.post("/policies/{policy_id}/override", response_model=PolicyResponse)
async def add_override(
    request: AddOverrideRequest,
    policy_id: str = Path(..., description="Policy ID"),  # noqa: B008
    user: User = Depends(require_admin),  # noqa: B008
):
    """
    Add an autonomy override to a policy.

    Requires admin role.
    Override types:
    - severity: Override by severity level (CRITICAL, HIGH, MEDIUM, LOW)
    - operation: Override by operation type (security_patch, deployment, etc.)
    - repository: Override by repository name or pattern
    """
    service = get_autonomy_service()
    updated_by = user.email or user.sub

    if request.override_type not in ("severity", "operation", "repository"):
        raise HTTPException(
            status_code=400, detail=f"Invalid override type: {request.override_type}"
        )

    try:
        policy = service.add_override(
            policy_id=policy_id,
            override_type=request.override_type,
            context_value=request.context_value,
            autonomy_level=AutonomyLevel(request.autonomy_level.value),
            updated_by=updated_by,
            reason=request.reason,
        )

        if not policy:
            raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

        logger.info(
            f"Admin {user.email} added {request.override_type} override "
            f"for {request.context_value} to policy {policy_id}"
        )
        return policy_to_response(policy)

    except ValueError as e:
        logger.warning(f"Override validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid override configuration")


@router.delete("/policies/{policy_id}/override")
async def remove_override(
    request: RemoveOverrideRequest,
    policy_id: str = Path(..., description="Policy ID"),  # noqa: B008
    user: User = Depends(require_admin),  # noqa: B008
):
    """Remove an autonomy override from a policy. Requires admin role."""
    service = get_autonomy_service()
    updated_by = user.email or user.sub

    policy = service.remove_override(
        policy_id=policy_id,
        override_type=request.override_type,
        context_value=request.context_value,
        updated_by=updated_by,
    )

    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    logger.info(
        f"Admin {user.email} removed {request.override_type} override "
        f"for {request.context_value} from policy {policy_id}"
    )
    return policy_to_response(policy)


@router.get("/presets", response_model=list[PresetResponse])
async def get_presets():
    """
    Get available policy presets.

    Presets provide pre-configured autonomy settings for common use cases:
    - defense_contractor: Maximum oversight for CMMC compliance
    - financial_services: High oversight for SOX/PCI-DSS
    - healthcare: High oversight for HIPAA
    - fintech_startup: Balanced autonomy
    - enterprise_standard: Standard enterprise settings
    - internal_tools: High autonomy for internal use
    - fully_autonomous: Maximum autonomy (guardrails still apply)
    """
    service = get_autonomy_service()
    presets = service.get_available_presets()
    return [PresetResponse(**p) for p in presets]


@router.post("/check", response_model=CheckHITLResponse)
async def check_hitl_required(
    check_request: CheckHITLRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),  # noqa: B008
    publisher: CloudWatchMetricsPublisher = Depends(  # noqa: B008
        get_cloudwatch_publisher
    ),  # noqa: B008
    rate_check: RateLimitResult = Depends(  # noqa: B008
        standard_rate_limit
    ),  # 60 req/min - read op  # noqa: B008
):
    """
    Check if HITL approval is required for a specific action.

    Requires authentication.
    Use this endpoint before executing an action to determine if
    human approval is needed based on the organization's policy.

    Note: Auto-approval decisions are logged to CloudWatch for compliance tracking.
    """
    logger.debug(
        f"User {user.email} checking HITL for policy {check_request.policy_id}"
    )
    service = get_autonomy_service()

    policy = service.get_policy(check_request.policy_id)
    if not policy:
        raise HTTPException(
            status_code=404, detail=f"Policy {check_request.policy_id} not found"
        )

    # Get autonomy level for this context
    autonomy_level = policy.get_autonomy_level(
        severity=check_request.severity,
        operation=check_request.operation,
        repository=check_request.repository,
    )

    # Check if HITL is required
    requires_hitl = policy.requires_hitl(
        severity=check_request.severity,
        operation=check_request.operation,
        repository=check_request.repository,
    )

    # Check if guardrail was triggered
    guardrail_triggered = check_request.operation in policy.guardrails

    # Build explanation
    if guardrail_triggered:
        reason = f"Guardrail triggered: '{check_request.operation}' always requires HITL approval"
    elif not policy.hitl_enabled:
        reason = "HITL is disabled for this policy (guardrails still apply)"
    elif requires_hitl:
        if autonomy_level == AutonomyLevel.FULL_HITL:
            reason = "Policy requires HITL approval for all actions"
        else:
            reason = f"Policy requires HITL approval for {check_request.severity} severity actions"
    else:
        reason = f"Autonomy level '{autonomy_level.value}' allows automatic processing"

    # Track auto-approval decisions for compliance monitoring
    if not requires_hitl and not guardrail_triggered:
        background_tasks.add_task(
            publish_autonomy_metric,
            publisher=publisher,
            event_type="auto_approval",
            organization_id=policy.organization_id,
            policy_id=check_request.policy_id,
            user=user.email,
            autonomy_level=autonomy_level.value,
            severity=check_request.severity,
            operation=check_request.operation,
            auto_approved=True,
        )

    return CheckHITLResponse(
        requires_hitl=requires_hitl,
        autonomy_level=autonomy_level.value,
        reason=reason,
        guardrail_triggered=guardrail_triggered,
    )


@router.get("/decisions", response_model=list[DecisionResponse])
async def get_decisions(
    organization_id: str = Query(..., description="Organization ID"),  # noqa: B008
    limit: int = Query(  # noqa: B008
        default=100, le=1000, description="Maximum results"
    ),  # noqa: B008
    execution_id: str | None = Query(  # noqa: B008
        default=None, description="Filter by execution ID"
    ),
    user: User = Depends(get_current_user),  # noqa: B008
):
    """
    Get autonomy decisions history for an organization.

    Requires authentication.
    Returns a log of autonomous decisions made, including whether
    HITL was required or bypassed.
    """
    logger.info(f"User {user.email} retrieving decisions for org {organization_id}")
    service = get_autonomy_service()

    if execution_id:
        decisions = service.get_decisions_for_execution(execution_id)
    else:
        # For now, return empty - would need to implement list_decisions
        decisions = []

    return [
        DecisionResponse(
            decision_id=d.decision_id,
            policy_id=d.policy_id,
            organization_id=d.organization_id,
            execution_id=d.execution_id,
            severity=d.severity,
            operation=d.operation,
            repository=d.repository,
            autonomy_level=d.autonomy_level.value,
            hitl_required=d.hitl_required,
            hitl_bypassed=d.hitl_bypassed,
            auto_approved=d.auto_approved,
            timestamp=d.timestamp,
        )
        for d in decisions[:limit]
    ]


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health")
async def autonomy_health():
    """Health check for autonomy service."""
    service = get_autonomy_service()
    return {
        "status": "healthy",
        "service": "autonomy_policy_service",
        "mode": service.mode.value,
    }
