"""
Trust Center API Endpoints.

REST API endpoints for the AI Trust Center dashboard, providing
visibility into Constitutional AI safety, autonomy configuration,
and compliance metrics.

Endpoints:
- GET  /api/v1/trust-center/status     - Overall system status
- GET  /api/v1/trust-center/principles - Constitutional AI principles
- GET  /api/v1/trust-center/autonomy   - Current autonomy configuration
- GET  /api/v1/trust-center/metrics    - Safety metrics (24h, 7d, 30d)
- GET  /api/v1/trust-center/decisions  - Decision audit timeline
- POST /api/v1/trust-center/export     - Export data (PDF/JSON)
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user
from src.services.api_rate_limiter import RateLimitResult, standard_rate_limit
from src.services.trust_center_service import (
    TrustCenterService,
    create_trust_center_service,
)
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

# =============================================================================
# Router Configuration
# =============================================================================

router = APIRouter(prefix="/api/v1/trust-center", tags=["Trust Center"])

# Service instance (lazy initialization)
_trust_center_service: Optional[TrustCenterService] = None


def get_trust_center_service() -> TrustCenterService:
    """Get or create the Trust Center service."""
    global _trust_center_service
    if _trust_center_service is None:
        mode = "aws" if os.environ.get("USE_AWS_DYNAMODB") else "mock"
        _trust_center_service = create_trust_center_service(mode=mode)
    return _trust_center_service


def set_trust_center_service(service: TrustCenterService) -> None:
    """Set the Trust Center service (for testing)."""
    global _trust_center_service
    _trust_center_service = service


# =============================================================================
# Response Models
# =============================================================================


class SystemStatusResponse(BaseModel):
    """Response model for system status."""

    overall_status: str = Field(
        ..., description="Overall health: healthy, warning, critical"
    )
    constitutional_ai_active: bool = Field(..., description="Whether CAI is active")
    guardrails_active: bool = Field(..., description="Whether guardrails are active")
    autonomy_level: str = Field(..., description="Current autonomy level")
    active_principles_count: int = Field(..., description="Number of active principles")
    critical_principles_count: int = Field(
        ..., description="Number of critical principles"
    )
    last_evaluation_time: Optional[str] = Field(
        None, description="Last evaluation timestamp"
    )
    decisions_last_24h: int = Field(..., description="Decisions in last 24 hours")
    issues_last_24h: int = Field(..., description="Issues found in last 24 hours")
    compliance_score: float = Field(..., description="Compliance score (0.0-1.0)")
    updated_at: str = Field(..., description="Status update timestamp")


class PrincipleResponse(BaseModel):
    """Response model for a constitutional principle."""

    id: str = Field(..., description="Principle identifier")
    name: str = Field(..., description="Human-readable name")
    category: str = Field(..., description="Category: safety, compliance, etc.")
    severity: str = Field(..., description="Severity: critical, high, medium, low")
    description: str = Field(..., description="Brief description")
    domain_tags: list[str] = Field(..., description="Domain tags")
    enabled: bool = Field(..., description="Whether principle is enabled")
    violation_count_24h: int = Field(0, description="Violations in last 24h")
    last_triggered: Optional[str] = Field(None, description="Last triggered timestamp")


class AutonomyConfigResponse(BaseModel):
    """Response model for autonomy configuration."""

    current_level: str = Field(..., description="Current autonomy level")
    hitl_enabled: bool = Field(..., description="Whether HITL is enabled")
    preset_name: Optional[str] = Field(None, description="Preset name if using preset")
    severity_overrides: dict[str, str] = Field(
        ..., description="Severity-based overrides"
    )
    operation_overrides: dict[str, str] = Field(
        ..., description="Operation-based overrides"
    )
    active_guardrails: list[str] = Field(..., description="Active guardrails")
    last_hitl_decision: Optional[str] = Field(
        None, description="Last HITL decision timestamp"
    )
    auto_approved_24h: int = Field(..., description="Auto-approved in last 24h")
    hitl_required_24h: int = Field(..., description="HITL required in last 24h")


class SafetyMetricResponse(BaseModel):
    """Response model for a safety metric."""

    metric_name: str
    display_name: str
    current_value: float
    target_value: float
    unit: str
    trend: str
    status: str
    change_24h: float
    time_series: list[dict[str, Any]]


class MetricsSnapshotResponse(BaseModel):
    """Response model for metrics snapshot."""

    period: str = Field(..., description="Time period: 24h, 7d, 30d")
    critique_accuracy: SafetyMetricResponse
    revision_convergence_rate: SafetyMetricResponse
    cache_hit_rate: SafetyMetricResponse
    non_evasive_rate: SafetyMetricResponse
    critique_latency_p95: SafetyMetricResponse
    golden_set_pass_rate: SafetyMetricResponse
    total_evaluations: int
    total_critiques: int
    issues_by_severity: dict[str, int]
    generated_at: str


class AuditDecisionResponse(BaseModel):
    """Response model for an audit decision."""

    decision_id: str
    timestamp: str
    agent_name: str
    operation_type: str
    principles_evaluated: int
    issues_found: int
    severity_breakdown: dict[str, int]
    requires_revision: bool
    revised: bool
    hitl_required: bool
    hitl_approved: Optional[bool]
    approved_by: Optional[str]
    execution_time_ms: float


class DecisionListResponse(BaseModel):
    """Response model for paginated decision list."""

    decisions: list[AuditDecisionResponse]
    total_count: int
    limit: int
    offset: int
    has_more: bool


class ExportRequest(BaseModel):
    """Request model for export."""

    format: str = Field(default="json", description="Export format: json or pdf")
    period: str = Field(default="24h", description="Time period: 24h, 7d, 30d")


class ExportResponse(BaseModel):
    """Response model for export."""

    export_id: str
    format: str
    generated_at: str
    period_start: str
    period_end: str
    status: SystemStatusResponse
    principles_count: int
    decisions_count: int
    download_url: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> SystemStatusResponse:
    """
    Get overall AI Trust Center system status.

    Returns the current health status of Constitutional AI, guardrails,
    and autonomy configuration. Includes compliance score and recent
    decision metrics.

    Requires authentication.
    """
    logger.info(f"User {user.email} requesting Trust Center status")

    service = get_trust_center_service()
    status = await service.get_system_status()

    return SystemStatusResponse(
        overall_status=status.overall_status.value,
        constitutional_ai_active=status.constitutional_ai_active,
        guardrails_active=status.guardrails_active,
        autonomy_level=status.autonomy_level,
        active_principles_count=status.active_principles_count,
        critical_principles_count=status.critical_principles_count,
        last_evaluation_time=(
            status.last_evaluation_time.isoformat()
            if status.last_evaluation_time
            else None
        ),
        decisions_last_24h=status.decisions_last_24h,
        issues_last_24h=status.issues_last_24h,
        compliance_score=status.compliance_score,
        updated_at=status.updated_at.isoformat(),
    )


@router.get("/principles", response_model=list[PrincipleResponse])
async def get_principles(
    category: Optional[str] = Query(
        default=None,
        description="Filter by category: safety, compliance, transparency, helpfulness, anti_sycophancy, code_quality, meta",
    ),
    severity: Optional[str] = Query(
        default=None,
        description="Filter by severity: critical, high, medium, low",
    ),
    include_metrics: bool = Query(
        default=False,
        description="Include violation metrics (slower)",
    ),
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> list[PrincipleResponse]:
    """
    Get constitutional AI principles.

    Returns the list of principles governing AI behavior, optionally
    filtered by category or severity. Includes violation metrics if
    requested.

    Requires authentication.
    """
    logger.debug(
        f"User {sanitize_log(user.email)} requesting principles (category={sanitize_log(category)}, severity={sanitize_log(severity)})"
    )

    # Validate filters
    valid_categories = [
        "safety",
        "compliance",
        "transparency",
        "helpfulness",
        "anti_sycophancy",
        "code_quality",
        "meta",
    ]
    valid_severities = ["critical", "high", "medium", "low"]

    if category and category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {valid_categories}",
        )

    if severity and severity not in valid_severities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity. Must be one of: {valid_severities}",
        )

    service = get_trust_center_service()
    principles = await service.get_principles(
        category=category,
        severity=severity,
        include_metrics=include_metrics,
    )

    return [
        PrincipleResponse(
            id=p.id,
            name=p.name,
            category=p.category,
            severity=p.severity,
            description=p.description,
            domain_tags=p.domain_tags,
            enabled=p.enabled,
            violation_count_24h=p.violation_count_24h,
            last_triggered=p.last_triggered.isoformat() if p.last_triggered else None,
        )
        for p in principles
    ]


@router.get("/autonomy", response_model=AutonomyConfigResponse)
async def get_autonomy_config(
    policy_id: Optional[str] = Query(
        default=None,
        description="Specific policy ID (uses default if not specified)",
    ),
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> AutonomyConfigResponse:
    """
    Get current autonomy configuration.

    Returns the HITL settings, autonomy level, overrides, and active
    guardrails for the organization. Includes metrics on auto-approved
    vs HITL-required decisions.

    Requires authentication.
    """
    logger.debug(f"User {user.email} requesting autonomy config")

    service = get_trust_center_service()
    config = await service.get_autonomy_config(policy_id=policy_id)

    return AutonomyConfigResponse(
        current_level=config.current_level,
        hitl_enabled=config.hitl_enabled,
        preset_name=config.preset_name,
        severity_overrides=config.severity_overrides,
        operation_overrides=config.operation_overrides,
        active_guardrails=config.active_guardrails,
        last_hitl_decision=(
            config.last_hitl_decision.isoformat() if config.last_hitl_decision else None
        ),
        auto_approved_24h=config.auto_approved_24h,
        hitl_required_24h=config.hitl_required_24h,
    )


@router.get("/metrics", response_model=MetricsSnapshotResponse)
async def get_safety_metrics(
    period: str = Query(
        default="24h",
        description="Time period: 24h, 7d, or 30d",
    ),
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> MetricsSnapshotResponse:
    """
    Get safety metrics for the specified time period.

    Returns Constitutional AI metrics including critique accuracy,
    revision convergence rate, cache hit rate, and latency. Each
    metric includes current value, target, trend, and time series.

    Requires authentication.
    """
    logger.debug(
        f"User {sanitize_log(user.email)} requesting metrics (period={sanitize_log(period)})"
    )

    # Validate period
    valid_periods = ["24h", "7d", "30d"]
    if period not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period. Must be one of: {valid_periods}",
        )

    service = get_trust_center_service()
    metrics = await service.get_safety_metrics(period=period)

    def to_metric_response(m) -> SafetyMetricResponse:
        return SafetyMetricResponse(
            metric_name=m.metric_name,
            display_name=m.display_name,
            current_value=m.current_value,
            target_value=m.target_value,
            unit=m.unit,
            trend=m.trend,
            status=m.status,
            change_24h=m.change_24h,
            time_series=m.time_series,
        )

    return MetricsSnapshotResponse(
        period=metrics.period,
        critique_accuracy=to_metric_response(metrics.critique_accuracy),
        revision_convergence_rate=to_metric_response(metrics.revision_convergence_rate),
        cache_hit_rate=to_metric_response(metrics.cache_hit_rate),
        non_evasive_rate=to_metric_response(metrics.non_evasive_rate),
        critique_latency_p95=to_metric_response(metrics.critique_latency_p95),
        golden_set_pass_rate=to_metric_response(metrics.golden_set_pass_rate),
        total_evaluations=metrics.total_evaluations,
        total_critiques=metrics.total_critiques,
        issues_by_severity=metrics.issues_by_severity,
        generated_at=metrics.generated_at.isoformat(),
    )


@router.get("/decisions", response_model=DecisionListResponse)
async def get_audit_decisions(
    limit: int = Query(default=50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    agent_name: Optional[str] = Query(
        default=None,
        description="Filter by agent name",
    ),
    start_time: Optional[str] = Query(
        default=None,
        description="Filter by start time (ISO format)",
    ),
    end_time: Optional[str] = Query(
        default=None,
        description="Filter by end time (ISO format)",
    ),
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> DecisionListResponse:
    """
    Get audit decision timeline.

    Returns a paginated list of Constitutional AI evaluation decisions,
    including which principles were checked, issues found, and whether
    HITL approval was required.

    Requires authentication.
    """
    logger.debug(
        f"User {sanitize_log(user.email)} requesting decisions (limit={sanitize_log(limit)}, offset={sanitize_log(offset)})"
    )

    # Parse datetime filters
    start_dt = None
    end_dt = None

    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid start_time format. Use ISO format.",
            )

    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid end_time format. Use ISO format.",
            )

    service = get_trust_center_service()
    decisions = await service.get_audit_decisions(
        limit=limit + 1,  # Request one extra to check has_more
        offset=offset,
        agent_name=agent_name,
        start_time=start_dt,
        end_time=end_dt,
    )

    # Check if there are more results
    has_more = len(decisions) > limit
    if has_more:
        decisions = decisions[:limit]

    return DecisionListResponse(
        decisions=[
            AuditDecisionResponse(
                decision_id=d.decision_id,
                timestamp=d.timestamp.isoformat(),
                agent_name=d.agent_name,
                operation_type=d.operation_type,
                principles_evaluated=d.principles_evaluated,
                issues_found=d.issues_found,
                severity_breakdown=d.severity_breakdown,
                requires_revision=d.requires_revision,
                revised=d.revised,
                hitl_required=d.hitl_required,
                hitl_approved=d.hitl_approved,
                approved_by=d.approved_by,
                execution_time_ms=d.execution_time_ms,
            )
            for d in decisions
        ],
        total_count=len(decisions) + offset,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.post("/export", response_model=ExportResponse)
async def export_data(
    request: ExportRequest,
    user: User = Depends(get_current_user),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
) -> ExportResponse:
    """
    Export Trust Center data.

    Generates an export of the Trust Center data in the specified format.
    JSON exports return data directly. PDF exports return a download URL.

    Requires authentication.
    """
    logger.info(
        f"User {sanitize_log(user.email)} exporting Trust Center data (format={sanitize_log(request.format)}, period={sanitize_log(request.period)})"
    )

    # Validate format
    if request.format not in ["json", "pdf"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid format. Must be 'json' or 'pdf'.",
        )

    # Validate period
    if request.period not in ["24h", "7d", "30d"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid period. Must be '24h', '7d', or '30d'.",
        )

    service = get_trust_center_service()
    export_data = await service.generate_export(
        format=request.format,
        period=request.period,
    )

    # Build status response
    status_response = SystemStatusResponse(
        overall_status=export_data.status.overall_status.value,
        constitutional_ai_active=export_data.status.constitutional_ai_active,
        guardrails_active=export_data.status.guardrails_active,
        autonomy_level=export_data.status.autonomy_level,
        active_principles_count=export_data.status.active_principles_count,
        critical_principles_count=export_data.status.critical_principles_count,
        last_evaluation_time=(
            export_data.status.last_evaluation_time.isoformat()
            if export_data.status.last_evaluation_time
            else None
        ),
        decisions_last_24h=export_data.status.decisions_last_24h,
        issues_last_24h=export_data.status.issues_last_24h,
        compliance_score=export_data.status.compliance_score,
        updated_at=export_data.status.updated_at.isoformat(),
    )

    # For PDF, we would generate and upload to S3
    # For now, just return the export metadata
    download_url = None
    if request.format == "pdf":
        # PDF generation would happen here
        # download_url = await _generate_pdf(export_data)
        download_url = None  # Not implemented yet

    return ExportResponse(
        export_id=export_data.export_id,
        format=export_data.format,
        generated_at=export_data.generated_at.isoformat(),
        period_start=export_data.period_start.isoformat(),
        period_end=export_data.period_end.isoformat(),
        status=status_response,
        principles_count=len(export_data.principles),
        decisions_count=export_data.decisions_count,
        download_url=download_url,
    )


@router.get("/export/{export_id}/data")
async def get_export_data(
    export_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """
    Get full export data by ID.

    Returns the complete export data for the specified export ID.
    This endpoint is used after calling POST /export to get the
    full JSON payload.

    Requires authentication.
    """
    logger.debug(
        f"User {sanitize_log(user.email)} requesting export data {sanitize_log(export_id)}"
    )

    # In a real implementation, we would retrieve from cache or regenerate
    # For now, generate fresh data
    service = get_trust_center_service()
    export_data = await service.generate_export(format="json", period="24h")

    return JSONResponse(content=export_data.to_dict())


# =============================================================================
# Health Check
# =============================================================================


@router.get("/health")
async def trust_center_health() -> dict[str, str]:
    """Health check for Trust Center API."""
    service = get_trust_center_service()
    return {
        "status": "healthy",
        "service": "trust_center",
        "mode": service.mode.value,
    }
