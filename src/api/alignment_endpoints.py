"""
Alignment API Endpoints (ADR-052 Phase 3).

Provides REST API for AI alignment monitoring and control:
- GET /api/v1/alignment/health - Get overall alignment health
- GET /api/v1/alignment/metrics - Get alignment metrics time series
- GET /api/v1/alignment/trends - Get trend analysis
- GET /api/v1/alignment/alerts - Get alignment alerts
- POST /api/v1/alignment/alerts/{id}/acknowledge - Acknowledge alert
- POST /api/v1/alignment/alerts/{id}/resolve - Resolve alert
- GET /api/v1/alignment/agents - Get agent alignment comparison
- GET /api/v1/alignment/reports - Generate alignment report
- POST /api/v1/alignment/override - Grant temporary autonomy override
- DELETE /api/v1/alignment/override/{agent_id} - Revoke override
- POST /api/v1/alignment/rollback/{action_id} - Execute rollback

Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/alignment",
    tags=["Alignment"],
)


# =============================================================================
# Service Singletons (dependency injection)
# =============================================================================

_analytics_service = None
_trust_autonomy_service = None
_sycophancy_guard = None
_rollback_service = None
_metrics_service = None


def get_analytics_service():
    """Get or create analytics service singleton."""
    global _analytics_service
    if _analytics_service is None:
        from src.services.alignment.analytics import AlignmentAnalyticsService

        _analytics_service = AlignmentAnalyticsService()
    return _analytics_service


def set_analytics_service(service) -> None:
    """Set analytics service (for testing)."""
    global _analytics_service
    _analytics_service = service


def get_trust_autonomy_service():
    """Get or create trust autonomy service singleton."""
    global _trust_autonomy_service
    if _trust_autonomy_service is None:
        from src.services.alignment.trust_autonomy import TrustBasedAutonomy

        _trust_autonomy_service = TrustBasedAutonomy()
    return _trust_autonomy_service


def set_trust_autonomy_service(service) -> None:
    """Set trust autonomy service (for testing)."""
    global _trust_autonomy_service
    _trust_autonomy_service = service


def get_sycophancy_guard():
    """Get or create sycophancy guard singleton."""
    global _sycophancy_guard
    if _sycophancy_guard is None:
        from src.services.alignment.sycophancy_guard import SycophancyGuard

        _sycophancy_guard = SycophancyGuard()
    return _sycophancy_guard


def set_sycophancy_guard(service) -> None:
    """Set sycophancy guard (for testing)."""
    global _sycophancy_guard
    _sycophancy_guard = service


def get_rollback_service():
    """Get or create rollback service singleton."""
    global _rollback_service
    if _rollback_service is None:
        from src.services.alignment.rollback_service import RollbackService

        _rollback_service = RollbackService()
    return _rollback_service


def set_rollback_service(service) -> None:
    """Set rollback service (for testing)."""
    global _rollback_service
    _rollback_service = service


def get_metrics_service():
    """Get or create metrics service singleton."""
    global _metrics_service
    if _metrics_service is None:
        from src.services.alignment.metrics_service import AlignmentMetricsService

        _metrics_service = AlignmentMetricsService()
    return _metrics_service


def set_metrics_service(service) -> None:
    """Set metrics service (for testing)."""
    global _metrics_service
    _metrics_service = service


# =============================================================================
# Request/Response Models
# =============================================================================


class AlignmentHealthResponse(BaseModel):
    """Overall alignment health response."""

    overall_score: float = Field(..., description="Overall alignment health 0-1")
    status: str = Field(..., description="healthy, warning, or critical")
    trust_score: float = Field(..., description="Average trust score across agents")
    sycophancy_score: float = Field(..., description="Anti-sycophancy health score")
    transparency_score: float = Field(..., description="Transparency compliance score")
    reversibility_score: float = Field(..., description="Rollback capability score")
    active_alerts: int = Field(..., description="Number of active alerts")
    agents_monitored: int = Field(..., description="Number of agents being monitored")
    last_updated: str = Field(..., description="ISO timestamp of last update")


class MetricTimeSeriesPoint(BaseModel):
    """Single point in a time series."""

    timestamp: str
    value: float
    min_value: float | None = None
    max_value: float | None = None
    count: int = 1


class MetricTimeSeriesResponse(BaseModel):
    """Time series data for a metric."""

    metric_name: str
    period_hours: int
    granularity: str
    data_points: list[MetricTimeSeriesPoint]


class TrendAnalysisResponse(BaseModel):
    """Trend analysis for a metric."""

    metric_name: str
    direction: str  # improving, stable, degrading, unknown
    slope: float
    confidence: float
    current_value: float
    previous_value: float
    change_percent: float
    period_start: str
    period_end: str
    data_points: int
    is_anomaly: bool
    anomaly_score: float


class AlertResponse(BaseModel):
    """Alignment alert response."""

    alert_id: str
    severity: str
    status: str
    metric_name: str
    threshold_value: float
    actual_value: float
    message: str
    agent_id: str | None
    triggered_at: str
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    resolved_at: str | None = None
    resolved_by: str | None = None


class AgentComparisonResponse(BaseModel):
    """Agent comparison response."""

    metric_name: str
    period_hours: int
    agents: list[dict[str, Any]]
    mean_value: float
    std_deviation: float
    best_agent_id: str
    worst_agent_id: str


class AlignmentReportResponse(BaseModel):
    """Comprehensive alignment report."""

    report_id: str
    generated_at: str
    period_start: str
    period_end: str
    overall_health_score: float
    trends: list[TrendAnalysisResponse]
    alerts: list[AlertResponse]
    recommendations: list[str]
    metadata: dict[str, Any]


class OverrideRequest(BaseModel):
    """Request to grant temporary autonomy override."""

    agent_id: str = Field(..., description="Agent to grant override to")
    new_level: str = Field(..., description="New autonomy level")
    reason: str = Field(..., description="Justification for override")
    duration_hours: int = Field(
        default=24, ge=1, le=168, description="Override duration in hours"
    )


class OverrideResponse(BaseModel):
    """Override response."""

    agent_id: str
    previous_level: str
    new_level: str
    expires_at: str
    granted_by: str
    reason: str


class RollbackRequest(BaseModel):
    """Request to execute a rollback."""

    action_id: str = Field(..., description="Action ID to roll back")
    reason: str = Field(default="", description="Reason for rollback")


class RollbackResponse(BaseModel):
    """Rollback execution response."""

    action_id: str
    status: str  # pending, in_progress, completed, failed
    steps_completed: int
    steps_total: int
    initiated_by: str
    started_at: str
    completed_at: str | None = None
    error_message: str | None = None


# =============================================================================
# Health Endpoints
# =============================================================================


@router.get("/health", response_model=AlignmentHealthResponse)
async def get_alignment_health(
    current_user: User = Depends(get_current_user),
) -> AlignmentHealthResponse:
    """
    Get overall alignment health status.

    Returns aggregate health metrics across all alignment dimensions.
    """
    analytics = get_analytics_service()
    metrics = get_metrics_service()
    guard = get_sycophancy_guard()

    # Get current health from metrics service
    health = metrics.get_health()

    # Get alert count
    active_count = len(
        [a for a in analytics.get_alerts() if a.status.value == "active"]
    )

    # Determine overall status
    if health.overall_score >= 0.8:
        status = "healthy"
    elif health.overall_score >= 0.5:
        status = "warning"
    else:
        status = "critical"

    # Get guard stats for sycophancy score
    guard_stats = guard.get_validation_stats()

    return AlignmentHealthResponse(
        overall_score=health.overall_score,
        status=status,
        trust_score=health.trust.avg_trust_score,
        sycophancy_score=1.0 - guard_stats.get("violation_rate", 0.0),
        transparency_score=health.transparency.audit_trail_completeness,
        reversibility_score=health.reversibility.class_a_snapshot_coverage,
        active_alerts=active_count,
        agents_monitored=guard_stats.get("agents_tracked", 0),
        last_updated=datetime.now(timezone.utc).isoformat(),
    )


# =============================================================================
# Metrics Endpoints
# =============================================================================


@router.get("/metrics", response_model=MetricTimeSeriesResponse)
async def get_metrics_time_series(
    metric_name: str = Query(..., description="Name of the metric"),
    period_hours: int = Query(default=24, ge=1, le=720, description="Hours of history"),
    granularity: str = Query(default="hour", description="minute, hour, day, week"),
    agent_id: str | None = Query(default=None, description="Filter by agent ID"),
    current_user: User = Depends(get_current_user),
) -> MetricTimeSeriesResponse:
    """
    Get time series data for a specific alignment metric.

    Supports multiple granularity levels for dashboard visualization.
    """
    from src.services.alignment.analytics import TimeGranularity

    analytics = get_analytics_service()

    # Map string to enum
    granularity_map = {
        "minute": TimeGranularity.MINUTE,
        "hour": TimeGranularity.HOUR,
        "day": TimeGranularity.DAY,
        "week": TimeGranularity.WEEK,
        "month": TimeGranularity.MONTH,
    }

    granularity_enum = granularity_map.get(granularity, TimeGranularity.HOUR)

    data = analytics.get_time_series(
        metric_name=metric_name,
        period_hours=period_hours,
        granularity=granularity_enum,
        agent_id=agent_id,
    )

    return MetricTimeSeriesResponse(
        metric_name=metric_name,
        period_hours=period_hours,
        granularity=granularity,
        data_points=[
            MetricTimeSeriesPoint(
                timestamp=dp["timestamp"],
                value=dp["value"],
                min_value=dp.get("min"),
                max_value=dp.get("max"),
                count=dp.get("count", 1),
            )
            for dp in data
        ],
    )


@router.get("/trends", response_model=list[TrendAnalysisResponse])
async def get_trends(
    period_hours: int = Query(default=24, ge=1, le=720, description="Hours of history"),
    agent_id: str | None = Query(default=None, description="Filter by agent ID"),
    current_user: User = Depends(get_current_user),
) -> list[TrendAnalysisResponse]:
    """
    Get trend analysis for all key alignment metrics.

    Analyzes direction, slope, and anomalies for each metric.
    """
    analytics = get_analytics_service()

    key_metrics = [
        "disagreement_rate",
        "confidence_calibration_error",
        "trust_score",
        "transparency_score",
        "rollback_success_rate",
    ]

    trends = []
    for metric in key_metrics:
        analysis = analytics.analyze_trend(
            metric_name=metric,
            period_hours=period_hours,
            agent_id=agent_id,
        )
        trends.append(
            TrendAnalysisResponse(
                metric_name=analysis.metric_name,
                direction=analysis.direction.value,
                slope=analysis.slope,
                confidence=analysis.confidence,
                current_value=analysis.current_value,
                previous_value=analysis.previous_value,
                change_percent=analysis.change_percent,
                period_start=analysis.period_start.isoformat(),
                period_end=analysis.period_end.isoformat(),
                data_points=analysis.data_points,
                is_anomaly=analysis.is_anomaly,
                anomaly_score=analysis.anomaly_score,
            )
        )

    return trends


# =============================================================================
# Alert Endpoints
# =============================================================================


@router.get("/alerts", response_model=list[AlertResponse])
async def get_alerts(
    status: str | None = Query(default=None, description="Filter by status"),
    severity: str | None = Query(default=None, description="Filter by severity"),
    agent_id: str | None = Query(default=None, description="Filter by agent ID"),
    current_user: User = Depends(get_current_user),
) -> list[AlertResponse]:
    """
    Get alignment alerts with optional filtering.

    Supports filtering by status (active, acknowledged, resolved, suppressed)
    and severity (info, warning, critical).
    """
    from src.services.alignment.analytics import AlertSeverity, AlertStatus

    analytics = get_analytics_service()

    # Map strings to enums
    status_enum = None
    if status:
        status_map = {
            "active": AlertStatus.ACTIVE,
            "acknowledged": AlertStatus.ACKNOWLEDGED,
            "resolved": AlertStatus.RESOLVED,
            "suppressed": AlertStatus.SUPPRESSED,
        }
        status_enum = status_map.get(status)

    severity_enum = None
    if severity:
        severity_map = {
            "info": AlertSeverity.INFO,
            "warning": AlertSeverity.WARNING,
            "critical": AlertSeverity.CRITICAL,
        }
        severity_enum = severity_map.get(severity)

    alerts = analytics.get_alerts(
        status=status_enum,
        severity=severity_enum,
        agent_id=agent_id,
    )

    return [
        AlertResponse(
            alert_id=a.alert_id,
            severity=a.severity.value,
            status=a.status.value,
            metric_name=a.metric_name,
            threshold_value=a.threshold_value,
            actual_value=a.actual_value,
            message=a.message,
            agent_id=a.agent_id,
            triggered_at=a.triggered_at.isoformat(),
            acknowledged_at=(
                a.acknowledged_at.isoformat() if a.acknowledged_at else None
            ),
            acknowledged_by=a.acknowledged_by,
            resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
            resolved_by=a.resolved_by,
        )
        for a in alerts
    ]


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
) -> AlertResponse:
    """
    Acknowledge an alignment alert.

    Marks the alert as acknowledged by the current user.
    """
    analytics = get_analytics_service()

    alert = analytics.acknowledge_alert(
        alert_id=alert_id,
        acknowledged_by=current_user.sub,
    )

    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    return AlertResponse(
        alert_id=alert.alert_id,
        severity=alert.severity.value,
        status=alert.status.value,
        metric_name=alert.metric_name,
        threshold_value=alert.threshold_value,
        actual_value=alert.actual_value,
        message=alert.message,
        agent_id=alert.agent_id,
        triggered_at=alert.triggered_at.isoformat(),
        acknowledged_at=(
            alert.acknowledged_at.isoformat() if alert.acknowledged_at else None
        ),
        acknowledged_by=alert.acknowledged_by,
        resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None,
        resolved_by=alert.resolved_by,
    )


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
) -> AlertResponse:
    """
    Resolve an alignment alert.

    Marks the alert as resolved by the current user.
    """
    analytics = get_analytics_service()

    alert = analytics.resolve_alert(
        alert_id=alert_id,
        resolved_by=current_user.sub,
    )

    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    return AlertResponse(
        alert_id=alert.alert_id,
        severity=alert.severity.value,
        status=alert.status.value,
        metric_name=alert.metric_name,
        threshold_value=alert.threshold_value,
        actual_value=alert.actual_value,
        message=alert.message,
        agent_id=alert.agent_id,
        triggered_at=alert.triggered_at.isoformat(),
        acknowledged_at=(
            alert.acknowledged_at.isoformat() if alert.acknowledged_at else None
        ),
        acknowledged_by=alert.acknowledged_by,
        resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None,
        resolved_by=alert.resolved_by,
    )


# =============================================================================
# Agent Comparison Endpoints
# =============================================================================


@router.get("/agents", response_model=list[AgentComparisonResponse])
async def get_agent_comparisons(
    period_hours: int = Query(default=24, ge=1, le=720, description="Hours of history"),
    current_user: User = Depends(get_current_user),
) -> list[AgentComparisonResponse]:
    """
    Compare alignment metrics across all agents.

    Returns rankings and statistics for each key metric.
    """
    analytics = get_analytics_service()

    key_metrics = [
        "disagreement_rate",
        "trust_score",
        "transparency_score",
    ]

    comparisons = []
    for metric in key_metrics:
        comp = analytics.compare_agents(
            metric_name=metric,
            period_hours=period_hours,
        )
        comparisons.append(
            AgentComparisonResponse(
                metric_name=comp.metric_name,
                period_hours=period_hours,
                agents=comp.agents,
                mean_value=comp.mean_value,
                std_deviation=comp.std_deviation,
                best_agent_id=comp.best_agent_id,
                worst_agent_id=comp.worst_agent_id,
            )
        )

    return comparisons


# =============================================================================
# Report Endpoints
# =============================================================================


@router.get("/reports", response_model=AlignmentReportResponse)
async def generate_report(
    period_hours: int = Query(default=24, ge=1, le=720, description="Hours of history"),
    include_comparisons: bool = Query(
        default=True, description="Include agent comparisons"
    ),
    current_user: User = Depends(get_current_user),
) -> AlignmentReportResponse:
    """
    Generate a comprehensive alignment report.

    Includes trends, alerts, comparisons, and recommendations.
    """
    analytics = get_analytics_service()

    report = analytics.generate_report(
        period_hours=period_hours,
        include_agent_comparison=include_comparisons,
    )

    return AlignmentReportResponse(
        report_id=report.report_id,
        generated_at=report.generated_at.isoformat(),
        period_start=report.period_start.isoformat(),
        period_end=report.period_end.isoformat(),
        overall_health_score=report.overall_health_score,
        trends=[
            TrendAnalysisResponse(
                metric_name=t.metric_name,
                direction=t.direction.value,
                slope=t.slope,
                confidence=t.confidence,
                current_value=t.current_value,
                previous_value=t.previous_value,
                change_percent=t.change_percent,
                period_start=t.period_start.isoformat(),
                period_end=t.period_end.isoformat(),
                data_points=t.data_points,
                is_anomaly=t.is_anomaly,
                anomaly_score=t.anomaly_score,
            )
            for t in report.trends
        ],
        alerts=[
            AlertResponse(
                alert_id=a.alert_id,
                severity=a.severity.value,
                status=a.status.value,
                metric_name=a.metric_name,
                threshold_value=a.threshold_value,
                actual_value=a.actual_value,
                message=a.message,
                agent_id=a.agent_id,
                triggered_at=a.triggered_at.isoformat(),
                acknowledged_at=(
                    a.acknowledged_at.isoformat() if a.acknowledged_at else None
                ),
                acknowledged_by=a.acknowledged_by,
                resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
                resolved_by=a.resolved_by,
            )
            for a in report.alerts
        ],
        recommendations=report.recommendations,
        metadata=report.metadata,
    )


# =============================================================================
# Override Endpoints
# =============================================================================


@router.post("/override", response_model=OverrideResponse)
async def grant_override(
    request: OverrideRequest,
    current_user: User = Depends(require_role("admin", "operator")),
) -> OverrideResponse:
    """
    Grant temporary autonomy override to an agent.

    Requires admin or operator role. Override expires after specified duration.
    """
    from src.services.alignment.trust_calculator import AutonomyLevel

    autonomy = get_trust_autonomy_service()

    # Map string to enum
    level_map = {
        "observe": AutonomyLevel.OBSERVE,
        "recommend": AutonomyLevel.RECOMMEND,
        "execute_review": AutonomyLevel.EXECUTE_REVIEW,
        "autonomous": AutonomyLevel.AUTONOMOUS,
    }

    new_level = level_map.get(request.new_level.lower())
    if new_level is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid autonomy level: {request.new_level}",
        )

    # Get current level for response
    current_level = autonomy.get_agent_autonomy_level(request.agent_id)

    override = autonomy.grant_temporary_override(
        agent_id=request.agent_id,
        new_level=new_level,
        reason=request.reason,
        granted_by=current_user.sub,
        duration_hours=request.duration_hours,
    )

    return OverrideResponse(
        agent_id=request.agent_id,
        previous_level=current_level.value if current_level else "observe",
        new_level=request.new_level,
        expires_at=override.expires_at.isoformat(),
        granted_by=override.granted_by,
        reason=override.reason,
    )


@router.delete("/override/{agent_id}", response_model=dict[str, Any])
async def revoke_override(
    agent_id: str,
    current_user: User = Depends(require_role("admin", "operator")),
) -> dict[str, Any]:
    """
    Revoke temporary autonomy override from an agent.

    Requires admin or operator role.
    """
    autonomy = get_trust_autonomy_service()

    success = autonomy.revoke_override(
        agent_id=agent_id,
        revoked_by=current_user.sub,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"No active override found for agent {agent_id}",
        )

    return {
        "success": True,
        "agent_id": agent_id,
        "revoked_by": current_user.sub,
        "revoked_at": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Rollback Endpoints
# =============================================================================


@router.post("/rollback/{action_id}", response_model=RollbackResponse)
async def execute_rollback(
    action_id: str,
    request: RollbackRequest | None = None,
    current_user: User = Depends(require_role("admin", "operator")),
) -> RollbackResponse:
    """
    Execute a rollback for a specific action.

    Requires admin or operator role. Restores the system to pre-action state.
    """
    rollback = get_rollback_service()

    # Check if rollback is possible
    capability = rollback.get_rollback_capability(action_id)
    if not capability.can_rollback:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot roll back action {action_id}: {capability.reason}",
        )

    # Execute rollback
    execution = rollback.execute_rollback(
        action_id=action_id,
        restore_fn=None,  # Use stored snapshot/plan
        initiated_by=current_user.sub,
    )

    return RollbackResponse(
        action_id=action_id,
        status=execution.status.value,
        steps_completed=execution.steps_completed,
        steps_total=execution.steps_total,
        initiated_by=execution.initiated_by,
        started_at=execution.started_at.isoformat(),
        completed_at=(
            execution.completed_at.isoformat() if execution.completed_at else None
        ),
        error_message=execution.error_message,
    )


@router.get("/rollback/{action_id}/capability", response_model=dict[str, Any])
async def get_rollback_capability(
    action_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Check if an action can be rolled back.

    Returns capability information including reason if rollback is not possible.
    """
    rollback = get_rollback_service()

    capability = rollback.get_rollback_capability(action_id)

    # Calculate time-based fields if expires_at is set
    expires_in_hours = None
    if capability.expires_at:
        delta = capability.expires_at - datetime.now(timezone.utc)
        expires_in_hours = (
            delta.total_seconds() / 3600 if delta.total_seconds() > 0 else 0
        )

    return {
        "action_id": action_id,
        "action_class": capability.action_class.value,
        "can_rollback": capability.can_rollback,
        "snapshot_available": capability.snapshot_available,
        "plan_available": capability.plan_available,
        "estimated_duration_seconds": capability.estimated_duration_seconds,
        "potential_side_effects": capability.potential_side_effects,
        "requires_downtime": capability.requires_downtime,
        "expires_in_hours": expires_in_hours,
    }
