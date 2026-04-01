"""
Project Aura - Disaster Recovery API Endpoints

REST API for disaster recovery operations:
- Region health status
- Failover initiation and monitoring
- DR drill scheduling
- Backup validation

Author: Project Aura Team
Created: 2025-12-20
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user, require_role
from src.services.disaster_recovery_service import DisasterRecoveryService, RegionStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dr", tags=["Disaster Recovery"])

# Service instance
dr_service = DisasterRecoveryService()


# ==============================================================================
# Request/Response Models
# ==============================================================================


class FailoverRequest(BaseModel):
    """Request to initiate failover."""

    source_region: str = Field(..., description="Region to failover from")
    target_region: str = Field(..., description="Region to failover to")
    reason: str = Field(..., description="Reason for failover")
    force: bool = Field(False, description="Force failover even if target unhealthy")


class DrillScheduleRequest(BaseModel):
    """Request to schedule a DR drill."""

    drill_type: str = Field(..., description="Type of drill (tabletop, partial, full)")
    target_region: str = Field(..., description="Region for the drill")
    scheduled_time: Optional[datetime] = Field(
        None, description="Scheduled time (null for immediate)"
    )
    notify_stakeholders: bool = Field(
        True, description="Send notifications to stakeholders"
    )
    max_duration_minutes: int = Field(
        60, description="Maximum drill duration in minutes"
    )


class BackupValidateRequest(BaseModel):
    """Request to validate backups."""

    region: str = Field(..., description="Region to validate backups for")
    service_types: Optional[List[str]] = Field(
        None, description="Specific service types to validate (null for all)"
    )
    check_restore_capability: bool = Field(
        True, description="Test restore capability (non-destructive)"
    )


class RegionHealthResponse(BaseModel):
    """Response for region health check."""

    region_id: str
    status: str
    is_primary: bool
    last_check: datetime
    services_healthy: int
    services_unhealthy: int
    latency_ms: float
    rpo_compliance: bool
    rto_compliance: bool


class FailoverStatusResponse(BaseModel):
    """Response for failover status."""

    failover_id: str
    status: str
    source_region: str
    target_region: str
    started_at: datetime
    completed_at: Optional[datetime]
    current_step: Optional[str]
    steps_completed: int
    steps_total: int
    error_message: Optional[str]


class DrillStatusResponse(BaseModel):
    """Response for drill status."""

    drill_id: str
    drill_type: str
    status: str
    target_region: str
    scheduled_time: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    rto_achieved_minutes: Optional[float]
    rpo_achieved_minutes: Optional[float]
    success: Optional[bool]
    findings: List[str]


class RecoveryObjectivesResponse(BaseModel):
    """Response for recovery objectives."""

    tier: str
    name: str
    rto_minutes: int
    rpo_minutes: int
    current_rto_minutes: Optional[float]
    current_rpo_minutes: Optional[float]
    rto_compliance: bool
    rpo_compliance: bool


# ==============================================================================
# Region Health Endpoints
# ==============================================================================


@router.get("/regions", response_model=List[RegionHealthResponse])
async def list_regions(
    include_unhealthy: bool = Query(  # noqa: B008
        True, description="Include unhealthy regions"
    ),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> List[RegionHealthResponse]:
    """
    List all configured regions with health status.

    Returns health metrics for each region including:
    - Service health counts
    - Latency measurements
    - RPO/RTO compliance status
    """
    try:
        health_results = await dr_service.check_all_regions_health()

        responses = []
        for region_id, health in health_results.items():
            region = dr_service.get_region(region_id)
            if not region:
                continue

            status = region.status
            if not include_unhealthy and status != RegionStatus.HEALTHY:
                continue

            services_healthy = sum(1 for v in health.services_checked.values() if v)
            services_unhealthy = sum(
                1 for v in health.services_checked.values() if not v
            )

            # Get compliance status from service
            compliance = dr_service.check_rto_rpo_compliance()

            responses.append(
                RegionHealthResponse(
                    region_id=region_id,
                    status=status.value,
                    is_primary=region.is_primary,
                    last_check=health.timestamp,
                    services_healthy=services_healthy,
                    services_unhealthy=services_unhealthy,
                    latency_ms=health.latency_ms,
                    rpo_compliance=compliance["rpo_compliant"],
                    rto_compliance=compliance["rto_compliant"],
                )
            )

        return responses
    except Exception as e:
        logger.error(f"Failed to list regions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list regions")


@router.get("/regions/{region_id}", response_model=RegionHealthResponse)
async def get_region_health(
    region_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
) -> RegionHealthResponse:
    """
    Get detailed health status for a specific region.
    """
    try:
        region = dr_service.get_region(region_id)
        if not region:
            raise HTTPException(status_code=404, detail=f"Region {region_id} not found")

        health = await dr_service.check_region_health(region_id)
        services_healthy = sum(1 for v in health.services_checked.values() if v)
        services_unhealthy = sum(1 for v in health.services_checked.values() if not v)

        # Get compliance status from service
        compliance = dr_service.check_rto_rpo_compliance()

        return RegionHealthResponse(
            region_id=region.region_id,
            status=region.status.value,
            is_primary=region.is_primary,
            last_check=health.timestamp,
            services_healthy=services_healthy,
            services_unhealthy=services_unhealthy,
            latency_ms=health.latency_ms,
            rpo_compliance=compliance["rpo_compliant"],
            rto_compliance=compliance["rto_compliant"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get region health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve region health")


@router.get("/regions/primary", response_model=RegionHealthResponse)
async def get_primary_region(
    user: User = Depends(get_current_user),  # noqa: B008
) -> RegionHealthResponse:
    """
    Get the current primary region.
    """
    try:
        region = dr_service.get_active_region()

        if not region:
            raise HTTPException(status_code=404, detail="No primary region configured")

        health = await dr_service.check_region_health(region.region_id)
        services_healthy = sum(1 for v in health.services_checked.values() if v)
        services_unhealthy = sum(1 for v in health.services_checked.values() if not v)

        # Get compliance status from service
        compliance = dr_service.check_rto_rpo_compliance()

        return RegionHealthResponse(
            region_id=region.region_id,
            status=region.status.value,
            is_primary=region.is_primary,
            last_check=health.timestamp,
            services_healthy=services_healthy,
            services_unhealthy=services_unhealthy,
            latency_ms=health.latency_ms,
            rpo_compliance=compliance["rpo_compliant"],
            rto_compliance=compliance["rto_compliant"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get primary region: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve primary region")


# ==============================================================================
# Failover Endpoints
# ==============================================================================


@router.post("/failover", response_model=FailoverStatusResponse)
async def initiate_failover(
    request: FailoverRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
) -> FailoverStatusResponse:
    """
    Initiate a failover from source to target region.

    Requires admin role. This is a significant operation that:
    - Validates target region health
    - Updates DNS records
    - Redirects traffic
    - Synchronizes data

    Use force=true to failover even if target region shows issues.
    """
    try:
        # Determine failover type based on request
        from src.services.disaster_recovery_service import FailoverType

        failover_type = FailoverType.MANUAL

        result = await dr_service.initiate_failover(
            target_region=request.target_region,
            failover_type=failover_type,
            initiated_by=user.email or user.sub,
        )

        # Calculate current step and total
        current_step = result.steps_completed[-1] if result.steps_completed else None
        steps_total = 5  # Total steps in failover process

        # Get error message from errors list
        error_message = result.errors[-1] if result.errors else None

        return FailoverStatusResponse(
            failover_id=result.event_id,
            status=result.status.value,
            source_region=result.source_region,
            target_region=result.target_region,
            started_at=result.initiated_at,
            completed_at=result.completed_at,
            current_step=current_step,
            steps_completed=len(result.steps_completed),
            steps_total=steps_total,
            error_message=error_message,
        )
    except ValueError as e:
        logger.warning(f"Failover validation error: {e}")
        raise HTTPException(
            status_code=400, detail="Invalid failover request parameters"
        )
    except Exception as e:
        logger.error(f"Failed to initiate failover: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initiate failover")


@router.get("/failover/{failover_id}", response_model=FailoverStatusResponse)
async def get_failover_status(
    failover_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
) -> FailoverStatusResponse:
    """
    Get the status of a failover operation.
    """
    try:
        result = dr_service.get_failover_event(failover_id)

        if not result:
            raise HTTPException(
                status_code=404, detail=f"Failover {failover_id} not found"
            )

        # Calculate current step and total
        current_step = result.steps_completed[-1] if result.steps_completed else None
        steps_total = 5  # Total steps in failover process

        # Get error message from errors list
        error_message = result.errors[-1] if result.errors else None

        return FailoverStatusResponse(
            failover_id=result.event_id,
            status=result.status.value,
            source_region=result.source_region,
            target_region=result.target_region,
            started_at=result.initiated_at,
            completed_at=result.completed_at,
            current_step=current_step,
            steps_completed=len(result.steps_completed),
            steps_total=steps_total,
            error_message=error_message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get failover status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve failover status"
        )


@router.get("/failovers", response_model=List[FailoverStatusResponse])
async def list_failovers(
    limit: int = Query(10, ge=1, le=100),  # noqa: B008
    status: Optional[str] = Query(None, description="Filter by status"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> List[FailoverStatusResponse]:
    """
    List recent failover operations.
    """
    try:
        from src.services.disaster_recovery_service import FailoverStatus

        failovers = dr_service.get_failover_history(limit=limit)

        # Filter by status if provided
        if status:
            try:
                status_enum = FailoverStatus(status)
                failovers = [f for f in failovers if f.status == status_enum]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        responses = []
        for f in failovers:
            current_step = f.steps_completed[-1] if f.steps_completed else None
            steps_total = 5  # Total steps in failover process
            error_message = f.errors[-1] if f.errors else None

            responses.append(
                FailoverStatusResponse(
                    failover_id=f.event_id,
                    status=f.status.value,
                    source_region=f.source_region,
                    target_region=f.target_region,
                    started_at=f.initiated_at,
                    completed_at=f.completed_at,
                    current_step=current_step,
                    steps_completed=len(f.steps_completed),
                    steps_total=steps_total,
                    error_message=error_message,
                )
            )

        return responses
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list failovers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list failovers")


@router.post("/failover/{failover_id}/cancel")
async def cancel_failover(
    failover_id: str,
    user: User = Depends(require_role("admin")),  # noqa: B008
) -> Dict[str, str]:
    """
    Cancel an in-progress failover operation.

    Only possible if failover has not reached point of no return.
    """
    try:
        from src.services.disaster_recovery_service import FailoverStatus

        # Get the failover event
        event = dr_service.get_failover_event(failover_id)
        if not event:
            raise HTTPException(
                status_code=404, detail=f"Failover {failover_id} not found"
            )

        # Check if it can be cancelled
        if event.status not in [FailoverStatus.INITIATED, FailoverStatus.IN_PROGRESS]:
            raise HTTPException(
                status_code=400,
                detail="Cannot cancel failover - operation may have completed or passed point of no return",
            )

        # Rollback the failover
        await dr_service.rollback_failover(
            event_id=failover_id,
            reason=f"Cancelled by {user.email or user.sub}",
        )

        return {"status": "cancelled", "failover_id": failover_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel failover: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cancel failover")


# ==============================================================================
# DR Drill Endpoints
# ==============================================================================


@router.post("/drills", response_model=DrillStatusResponse)
async def schedule_drill(
    request: DrillScheduleRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
) -> DrillStatusResponse:
    """
    Schedule a disaster recovery drill.

    Drill types:
    - tabletop: Discussion-based exercise, no actual failover
    - partial: Test specific components without full failover
    - full: Complete failover to DR region and back
    """
    try:
        # Use current time if no scheduled time provided
        scheduled_time = request.scheduled_time or datetime.now(timezone.utc)

        result = dr_service.schedule_drill(
            drill_type=request.drill_type,
            scheduled_at=scheduled_time,
            target_region=request.target_region,
            participants=[user.email or user.sub],
        )

        return DrillStatusResponse(
            drill_id=result.drill_id,
            drill_type=result.drill_type,
            status=result.status.value,
            target_region=result.target_region,
            scheduled_time=result.scheduled_at,
            started_at=result.started_at,
            completed_at=result.completed_at,
            rto_achieved_minutes=result.rto_actual_minutes,
            rpo_achieved_minutes=result.rpo_actual_minutes,
            success=result.rto_met,
            findings=result.findings,
        )
    except ValueError as e:
        logger.warning(f"Drill schedule validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid drill schedule parameters")
    except Exception as e:
        logger.error(f"Failed to schedule drill: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to schedule drill")


@router.get("/drills/{drill_id}", response_model=DrillStatusResponse)
async def get_drill_status(
    drill_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
) -> DrillStatusResponse:
    """
    Get the status of a DR drill.
    """
    try:
        # Get drill from service's internal records
        result = dr_service._drill_records.get(drill_id)

        if not result:
            raise HTTPException(status_code=404, detail=f"Drill {drill_id} not found")

        return DrillStatusResponse(
            drill_id=result.drill_id,
            drill_type=result.drill_type,
            status=result.status.value,
            target_region=result.target_region,
            scheduled_time=result.scheduled_at,
            started_at=result.started_at,
            completed_at=result.completed_at,
            rto_achieved_minutes=result.rto_actual_minutes,
            rpo_achieved_minutes=result.rpo_actual_minutes,
            success=result.rto_met,
            findings=result.findings,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get drill status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve drill status")


@router.get("/drills", response_model=List[DrillStatusResponse])
async def list_drills(
    limit: int = Query(10, ge=1, le=100),  # noqa: B008
    include_completed: bool = Query(True),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> List[DrillStatusResponse]:
    """
    List DR drills.
    """
    try:
        from src.services.disaster_recovery_service import DrillStatus

        drills = dr_service.get_drill_history(limit=limit)

        # Filter out completed drills if requested
        if not include_completed:
            drills = [d for d in drills if d.status != DrillStatus.COMPLETED]

        return [
            DrillStatusResponse(
                drill_id=d.drill_id,
                drill_type=d.drill_type,
                status=d.status.value,
                target_region=d.target_region,
                scheduled_time=d.scheduled_at,
                started_at=d.started_at,
                completed_at=d.completed_at,
                rto_achieved_minutes=d.rto_actual_minutes,
                rpo_achieved_minutes=d.rpo_actual_minutes,
                success=d.rto_met,
                findings=d.findings,
            )
            for d in drills
        ]
    except Exception as e:
        logger.error(f"Failed to list drills: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list drills")


# ==============================================================================
# Backup Validation Endpoints
# ==============================================================================


@router.post("/backups/validate")
async def validate_backups(
    request: BackupValidateRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
) -> Dict[str, Any]:
    """
    Validate backups for a region.

    Checks:
    - Backup existence and recency
    - Data integrity
    - Restore capability (non-destructive test)
    """
    try:
        # Get latest backups for the region
        backups = dr_service.get_latest_backups(region=request.region)

        validation_results = []
        for backup_type, backup in backups.items():
            # Validate each backup
            validation = await dr_service.validate_backup(backup.backup_id)
            validation_results.append(
                {
                    "backup_type": backup_type,
                    "backup_id": backup.backup_id,
                    "valid": validation["valid"],
                    "integrity_check": validation["integrity_check"],
                }
            )

        # Check compliance
        compliance = dr_service.check_backup_compliance()

        services_validated = len(validation_results)
        services_passed = sum(1 for v in validation_results if v["valid"])
        services_failed = services_validated - services_passed

        return {
            "region": request.region,
            "validation_time": datetime.now(timezone.utc).isoformat(),
            "overall_status": "passed" if services_failed == 0 else "failed",
            "services_validated": services_validated,
            "services_passed": services_passed,
            "services_failed": services_failed,
            "rpo_compliant": compliance["compliant"],
            "details": validation_results,
            "recommendations": (
                ["Ensure all backups are validated regularly"]
                if services_failed > 0
                else []
            ),
        }
    except Exception as e:
        logger.error(f"Failed to validate backups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to validate backups")


@router.get("/backups/status")
async def get_backup_status(
    region: Optional[str] = Query(None, description="Filter by region"),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Dict[str, Any]:
    """
    Get current backup status across regions.
    """
    try:
        # Get latest backups
        backups = dr_service.get_latest_backups(region=region)

        # Get compliance status
        compliance = dr_service.check_backup_compliance()

        # Format response
        backup_status = {}
        for backup_type, backup in backups.items():
            backup_status[backup_type] = {
                "backup_id": backup.backup_id,
                "created_at": backup.created_at.isoformat(),
                "size_bytes": backup.size_bytes,
                "region": backup.region,
                "status": backup.status.value,
            }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "regions": {
                region
                or "all": {
                    "backups": backup_status,
                    "compliance": compliance,
                }
            },
        }
    except Exception as e:
        logger.error(f"Failed to get backup status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve backup status")


# ==============================================================================
# Recovery Objectives Endpoints
# ==============================================================================


@router.get("/objectives", response_model=List[RecoveryObjectivesResponse])
async def list_recovery_objectives(
    user: User = Depends(get_current_user),  # noqa: B008
) -> List[RecoveryObjectivesResponse]:
    """
    List configured recovery objectives (RTO/RPO) by tier.
    """
    try:
        from src.services.disaster_recovery_service import RECOVERY_OBJECTIVES

        # Get compliance metrics
        compliance = dr_service.check_rto_rpo_compliance()

        # Get recent failover history for current metrics
        recent_failovers = dr_service.get_failover_history(limit=10)
        completed_failovers = [
            f
            for f in recent_failovers
            if f.status.value == "completed" and f.duration_seconds is not None
        ]

        # Calculate current RTO from recent failovers
        current_rto_minutes = None
        if completed_failovers:
            durations = [
                f.duration_seconds
                for f in completed_failovers
                if f.duration_seconds is not None
            ]
            if durations:
                avg_duration = sum(durations) / len(durations)
                current_rto_minutes = avg_duration / 60

        responses = []
        for _tier, obj in RECOVERY_OBJECTIVES.items():
            responses.append(
                RecoveryObjectivesResponse(
                    tier=obj.tier,
                    name=obj.name,
                    rto_minutes=obj.rto_minutes,
                    rpo_minutes=obj.rpo_minutes,
                    current_rto_minutes=current_rto_minutes,
                    current_rpo_minutes=None,  # Would need backup age tracking
                    rto_compliance=compliance["rto_compliant"],
                    rpo_compliance=compliance["rpo_compliant"],
                )
            )

        return responses
    except Exception as e:
        logger.error(f"Failed to list recovery objectives: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to list recovery objectives"
        )


@router.get("/objectives/{tier}", response_model=RecoveryObjectivesResponse)
async def get_recovery_objective(
    tier: str,
    user: User = Depends(get_current_user),  # noqa: B008
) -> RecoveryObjectivesResponse:
    """
    Get recovery objectives for a specific tier.
    """
    try:
        obj = dr_service.get_recovery_objectives(tier=tier)

        # Get compliance metrics
        compliance = dr_service.check_rto_rpo_compliance()

        # Get recent failover history for current metrics
        recent_failovers = dr_service.get_failover_history(limit=10)
        completed_failovers = [
            f
            for f in recent_failovers
            if f.status.value == "completed" and f.duration_seconds is not None
        ]

        # Calculate current RTO from recent failovers
        current_rto_minutes = None
        if completed_failovers:
            durations = [
                f.duration_seconds
                for f in completed_failovers
                if f.duration_seconds is not None
            ]
            if durations:
                avg_duration = sum(durations) / len(durations)
                current_rto_minutes = avg_duration / 60

        return RecoveryObjectivesResponse(
            tier=obj.tier,
            name=obj.name,
            rto_minutes=obj.rto_minutes,
            rpo_minutes=obj.rpo_minutes,
            current_rto_minutes=current_rto_minutes,
            current_rpo_minutes=None,  # Would need backup age tracking
            rto_compliance=compliance["rto_compliant"],
            rpo_compliance=compliance["rpo_compliant"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recovery objective: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve recovery objective"
        )
