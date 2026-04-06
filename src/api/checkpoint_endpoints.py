"""
REST API Endpoints for Checkpoint Management.

Provides REST interface for checkpoint operations alongside
WebSocket real-time interface (ADR-042).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.execution_checkpoint_service import (
from src.api.log_sanitizer import sanitize_log
    CheckpointStatus,
    ExecutionCheckpointService,
    InterventionMode,
    RiskLevel,
    TrustRule,
    autonomy_level_to_intervention_mode,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["checkpoints"])

# Service instance (initialized at startup)
_checkpoint_service: Optional[ExecutionCheckpointService] = None


def get_checkpoint_service() -> ExecutionCheckpointService:
    """Dependency to get checkpoint service instance."""
    if _checkpoint_service is None:
        raise HTTPException(
            status_code=503,
            detail="Checkpoint service not initialized",
        )
    return _checkpoint_service


def init_checkpoint_service(table_name: str, event_publisher=None) -> None:
    """Initialize checkpoint service at application startup."""
    global _checkpoint_service
    _checkpoint_service = ExecutionCheckpointService(
        dynamodb_table_name=table_name,
        event_publisher=event_publisher,
    )
    logger.info("Checkpoint service initialized")


# Request/Response Models


class ApproveCheckpointRequest(BaseModel):
    """Request to approve a checkpoint."""

    user_id: str = Field(..., description="User approving the action")


class ApproveWithModificationsRequest(BaseModel):
    """Request to approve a checkpoint with parameter modifications."""

    user_id: str = Field(..., description="User approving the action")
    modifications: Dict[str, Any] = Field(
        ..., description="Parameter modifications to apply"
    )


class DenyCheckpointRequest(BaseModel):
    """Request to deny a checkpoint."""

    user_id: str = Field(..., description="User denying the action")
    reason: str = Field(..., description="Reason for denial")


class TrustSettingsRequest(BaseModel):
    """Request to update trust settings."""

    rules: List[Dict[str, Any]] = Field(
        default_factory=list, description="Trust rules to apply"
    )
    intervention_mode: Optional[str] = Field(
        None, description="Intervention mode (maps to autonomy level)"
    )


class EmergencyStopRequest(BaseModel):
    """Request for emergency stop."""

    user_id: str = Field(..., description="User initiating stop")
    reason: str = Field(default="Emergency stop", description="Reason for stop")


class CheckpointResponse(BaseModel):
    """Response containing checkpoint details."""

    checkpoint_id: str
    execution_id: str
    agent_id: str
    action_type: str
    action_name: str
    parameters: Dict[str, Any]
    risk_level: str
    status: str
    reversible: bool
    created_at: str
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Response after approval/denial action."""

    checkpoint_id: str
    status: str
    decided_by: str
    decided_at: str
    message: str


# Endpoints


@router.post(
    "/checkpoints/{checkpoint_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve a pending checkpoint",
)
async def approve_checkpoint(
    checkpoint_id: str,
    request: ApproveCheckpointRequest,
    service: ExecutionCheckpointService = Depends(get_checkpoint_service),  # noqa: B008
):
    """
    Approve a pending checkpoint to allow execution to continue.

    The checkpoint must be in AWAITING_APPROVAL status.
    """
    try:
        result = await service.approve_checkpoint(
            checkpoint_id=checkpoint_id,
            user_id=request.user_id,
        )

        return ApprovalResponse(
            checkpoint_id=result.checkpoint_id,
            status=result.status.value,
            decided_by=result.decided_by or "unknown",
            decided_at=result.decided_at or "",
            message="Checkpoint approved successfully",
        )

    except Exception as e:
        logger.error("Error approving checkpoint: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to approve checkpoint")


@router.post(
    "/checkpoints/{checkpoint_id}/deny",
    response_model=ApprovalResponse,
    summary="Deny a pending checkpoint",
)
async def deny_checkpoint(
    checkpoint_id: str,
    request: DenyCheckpointRequest,
    service: ExecutionCheckpointService = Depends(get_checkpoint_service),  # noqa: B008
):
    """
    Deny a pending checkpoint to halt execution.

    The checkpoint must be in AWAITING_APPROVAL status.
    Execution will stop at this point.
    """
    try:
        result = await service.deny_checkpoint(
            checkpoint_id=checkpoint_id,
            user_id=request.user_id,
            reason=request.reason,
        )

        return ApprovalResponse(
            checkpoint_id=result.checkpoint_id,
            status=result.status.value,
            decided_by=result.decided_by or "unknown",
            decided_at=result.decided_at or "",
            message=f"Checkpoint denied: {request.reason}",
        )

    except Exception as e:
        logger.error("Error denying checkpoint: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to deny checkpoint")


@router.post(
    "/checkpoints/{checkpoint_id}/modify",
    response_model=ApprovalResponse,
    summary="Modify and approve a checkpoint",
)
async def modify_checkpoint(
    checkpoint_id: str,
    request: ApproveWithModificationsRequest,
    service: ExecutionCheckpointService = Depends(get_checkpoint_service),  # noqa: B008
):
    """
    Modify parameters and approve a checkpoint.

    Allows changing action parameters before execution proceeds.
    The checkpoint must be in AWAITING_APPROVAL status.
    """
    try:
        result = await service.approve_checkpoint(
            checkpoint_id=checkpoint_id,
            user_id=request.user_id,
            modifications=request.modifications,
        )

        return ApprovalResponse(
            checkpoint_id=result.checkpoint_id,
            status=result.status.value,
            decided_by=result.decided_by or "unknown",
            decided_at=result.decided_at or "",
            message="Checkpoint modified and approved",
        )

    except Exception as e:
        logger.error("Error modifying checkpoint: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to modify checkpoint")


@router.get(
    "/executions/{execution_id}/checkpoints",
    response_model=List[CheckpointResponse],
    summary="Get checkpoints for an execution",
)
async def get_execution_checkpoints(
    execution_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),  # noqa: B008
    service: ExecutionCheckpointService = Depends(get_checkpoint_service),  # noqa: B008
):
    """
    Get all checkpoints for an execution.

    Optionally filter by status (e.g., AWAITING_APPROVAL, COMPLETED).
    """
    try:
        status_filter = None
        if status:
            try:
                status_filter = [CheckpointStatus(status.upper())]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}",
                )

        checkpoints = await service.get_execution_checkpoints(
            execution_id=execution_id,
            status_filter=status_filter,
        )

        return [
            CheckpointResponse(
                checkpoint_id=cp["checkpoint_id"],
                execution_id=cp["execution_id"],
                agent_id=cp["agent_id"],
                action_type=cp["action_type"],
                action_name=cp["action_name"],
                parameters=cp.get("parameters", {}),
                risk_level=cp["risk_level"],
                status=cp["status"],
                reversible=cp.get("reversible", False),
                created_at=cp["created_at"],
                decided_by=cp.get("decided_by"),
                decided_at=cp.get("decided_at"),
                modifications=cp.get("modifications"),
                reason=cp.get("reason"),
            )
            for cp in checkpoints
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting checkpoints: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get checkpoints")


@router.put(
    "/executions/{execution_id}/trust-settings",
    summary="Update trust settings for an execution",
)
async def update_trust_settings(
    execution_id: str,
    request: TrustSettingsRequest,
    service: ExecutionCheckpointService = Depends(get_checkpoint_service),  # noqa: B008
):
    """
    Update trust settings for auto-approval.

    Trust rules determine which actions can be automatically approved
    without user intervention.
    """
    try:
        # Update intervention mode if provided
        if request.intervention_mode:
            try:
                mode = InterventionMode(request.intervention_mode)
                service.set_intervention_mode(mode)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid intervention mode: {request.intervention_mode}",
                )

        # Clear existing rules and add new ones
        existing_rules = await service.get_trust_rules()
        for rule in existing_rules:
            await service.remove_trust_rule(rule.rule_id)

        # Add new rules
        for rule_data in request.rules:
            rule = TrustRule(
                rule_id=rule_data.get(
                    "rule_id", f"rule-{datetime.now(timezone.utc).timestamp()}"
                ),
                action_type=rule_data.get("action_type"),
                action_name_pattern=rule_data.get("action_name_pattern"),
                agent_id_pattern=rule_data.get("agent_id_pattern"),
                max_risk_level=RiskLevel(rule_data.get("max_risk_level", "low")),
                enabled=rule_data.get("enabled", True),
            )
            await service.add_trust_rule(rule)

        return {
            "message": "Trust settings updated",
            "rules_count": len(request.rules),
            "intervention_mode": service.intervention_mode.value,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating trust settings: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update trust settings")


@router.get(
    "/executions/{execution_id}/trust-settings",
    summary="Get trust settings for an execution",
)
async def get_trust_settings(
    execution_id: str,
    service: ExecutionCheckpointService = Depends(get_checkpoint_service),  # noqa: B008
):
    """
    Get current trust settings including rules and intervention mode.
    """
    try:
        rules = await service.get_trust_rules()

        return {
            "intervention_mode": service.intervention_mode.value,
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "action_type": r.action_type.value if r.action_type else None,
                    "action_name_pattern": r.action_name_pattern,
                    "agent_id_pattern": r.agent_id_pattern,
                    "max_risk_level": r.max_risk_level.value,
                    "enabled": r.enabled,
                }
                for r in rules
            ],
        }

    except Exception as e:
        logger.error("Error getting trust settings: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get trust settings")


@router.post(
    "/executions/{execution_id}/emergency-stop",
    summary="Emergency stop an execution",
)
async def emergency_stop(
    execution_id: str,
    request: EmergencyStopRequest,
    service: ExecutionCheckpointService = Depends(get_checkpoint_service),  # noqa: B008
):
    """
    Immediately stop an execution.

    This will:
    1. Mark all pending checkpoints as DENIED
    2. Signal the orchestrator to halt
    3. Log the emergency stop event
    """
    try:
        # Get all pending checkpoints
        pending = await service.get_execution_checkpoints(
            execution_id=execution_id,
            status_filter=[CheckpointStatus.AWAITING_APPROVAL],
        )

        # Deny all pending checkpoints
        denied_count = 0
        for cp in pending:
            await service.deny_checkpoint(
                checkpoint_id=cp["checkpoint_id"],
                user_id=request.user_id,
                reason=f"Emergency stop: {request.reason}",
            )
            denied_count += 1

        logger.warning(
            f"Emergency stop on execution {sanitize_log(execution_id)} by {sanitize_log(request.user_id)}: "
            f"{request.reason} (denied {denied_count} checkpoints)"
        )

        return {
            "message": "Emergency stop executed",
            "execution_id": execution_id,
            "denied_checkpoints": denied_count,
            "stopped_by": request.user_id,
            "reason": request.reason,
        }

    except Exception as e:
        logger.error("Error executing emergency stop: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to execute emergency stop")


@router.put(
    "/executions/{execution_id}/autonomy-level",
    summary="Set autonomy level (ADR-032 integration)",
)
async def set_autonomy_level(
    execution_id: str,
    level: int = Query(..., ge=0, le=5, description="Autonomy level 0-5"),  # noqa: B008
    service: ExecutionCheckpointService = Depends(get_checkpoint_service),  # noqa: B008
):
    """
    Set intervention mode based on ADR-032 autonomy level.

    Levels:
        0 - Manual: All actions require approval
        1 - Observe: All actions require approval
        2 - Assisted: Write operations require approval
        3 - Supervised: High/critical risk only
        4 - Guided: Critical only
        5 - Autonomous: No intervention
    """
    try:
        mode = autonomy_level_to_intervention_mode(level)
        service.set_intervention_mode(mode)

        return {
            "execution_id": execution_id,
            "autonomy_level": level,
            "intervention_mode": mode.value,
            "message": f"Autonomy level set to {level}",
        }

    except Exception as e:
        logger.error("Error setting autonomy level: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to set autonomy level")
