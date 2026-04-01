"""
SLA Monitoring API Endpoints.

Provides REST API for SLA monitoring and credit management:
- GET /api/v1/sla/status - Get current SLO status
- GET /api/v1/sla/tiers - List available SLA tiers
- GET /api/v1/sla/reports - List SLA reports
- POST /api/v1/sla/reports - Generate SLA report
- GET /api/v1/sla/breaches - List SLA breaches
- GET /api/v1/sla/credits - List SLA credits
- POST /api/v1/sla/credits/{id}/approve - Approve credit
- POST /api/v1/sla/metrics - Record metric (internal)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user, require_role
from src.services.sla_monitoring_service import (
    SLA_TIERS,
    BreachSeverity,
    CreditStatus,
    SLABreach,
    SLACredit,
    SLADefinition,
    SLAReport,
    SLATier,
    SLOMetric,
    SLOStatus,
    get_sla_monitoring_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/sla",
    tags=["SLA Monitoring"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class SLATierResponse(BaseModel):
    """SLA tier definition response."""

    tier: str
    name: str
    uptime_target: float
    latency_p50_ms: int
    latency_p95_ms: int
    latency_p99_ms: int
    error_rate_target: float
    response_time_hours: int
    resolution_time_hours: int
    credit_schedule: Dict[str, float]


class SLOStatusResponse(BaseModel):
    """SLO status response."""

    metric: str
    target: float
    current: float
    is_met: bool
    margin: float
    trend: str
    samples: int


class SLAReportRequest(BaseModel):
    """Request to generate SLA report."""

    period_days: int = Field(default=30, ge=1, le=365)
    invoice_amount_cents: int = Field(default=0, ge=0)


class SLAReportResponse(BaseModel):
    """SLA report response."""

    report_id: str
    customer_id: str
    tier: str
    period_start: str
    period_end: str
    uptime_actual: float
    uptime_target: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    error_rate: float
    slo_statuses: List[SLOStatusResponse]
    is_compliant: bool
    breach_count: int
    credit_eligible: bool
    credit_percentage: float
    credit_amount_cents: int
    generated_at: str


class SLABreachResponse(BaseModel):
    """SLA breach response."""

    breach_id: str
    customer_id: str
    tier: str
    metric: str
    target: float
    actual: float
    severity: str
    started_at: str
    ended_at: Optional[str]
    duration_minutes: int
    acknowledged: bool


class SLACreditResponse(BaseModel):
    """SLA credit response."""

    credit_id: str
    customer_id: str
    period_start: str
    period_end: str
    uptime_actual: float
    credit_percentage: float
    invoice_amount_cents: int
    credit_amount_cents: int
    status: str
    report_id: str
    created_at: str
    approved_at: Optional[str]
    applied_at: Optional[str]


class RecordMetricRequest(BaseModel):
    """Request to record a metric."""

    metric: str = Field(..., description="Metric type: uptime, latency_p95, error_rate")
    value: float = Field(..., description="Metric value")
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp")


class RecordRequestMetricRequest(BaseModel):
    """Request to record API request metrics."""

    latency_ms: float = Field(..., ge=0)
    success: bool
    endpoint: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================


def tier_to_response(sla: SLADefinition) -> SLATierResponse:
    """Convert SLADefinition to response."""
    return SLATierResponse(
        tier=sla.tier.value,
        name=sla.name,
        uptime_target=sla.uptime_target,
        latency_p50_ms=sla.latency_p50_ms,
        latency_p95_ms=sla.latency_p95_ms,
        latency_p99_ms=sla.latency_p99_ms,
        error_rate_target=sla.error_rate_target,
        response_time_hours=sla.response_time_hours,
        resolution_time_hours=sla.resolution_time_hours,
        credit_schedule=sla.credit_schedule,
    )


def slo_status_to_response(status: SLOStatus) -> SLOStatusResponse:
    """Convert SLOStatus to response."""
    return SLOStatusResponse(
        metric=status.metric.value,
        target=status.target,
        current=round(status.current, 2),
        is_met=status.is_met,
        margin=round(status.margin, 2),
        trend=status.trend,
        samples=status.samples,
    )


def report_to_response(report: SLAReport) -> SLAReportResponse:
    """Convert SLAReport to response."""
    return SLAReportResponse(
        report_id=report.report_id,
        customer_id=report.customer_id,
        tier=report.tier.value,
        period_start=report.period_start.isoformat(),
        period_end=report.period_end.isoformat(),
        uptime_actual=round(report.uptime_actual, 4),
        uptime_target=report.uptime_target,
        latency_p50=round(report.latency_p50, 2),
        latency_p95=round(report.latency_p95, 2),
        latency_p99=round(report.latency_p99, 2),
        error_rate=round(report.error_rate, 4),
        slo_statuses=[slo_status_to_response(s) for s in report.slo_statuses],
        is_compliant=report.is_compliant,
        breach_count=len(report.breaches),
        credit_eligible=report.credit_eligible,
        credit_percentage=report.credit_percentage,
        credit_amount_cents=report.credit_amount_cents,
        generated_at=report.generated_at.isoformat(),
    )


def breach_to_response(breach: SLABreach) -> SLABreachResponse:
    """Convert SLABreach to response."""
    return SLABreachResponse(
        breach_id=breach.breach_id,
        customer_id=breach.customer_id,
        tier=breach.tier.value,
        metric=breach.metric.value,
        target=breach.target,
        actual=breach.actual,
        severity=breach.severity.value,
        started_at=breach.started_at.isoformat(),
        ended_at=breach.ended_at.isoformat() if breach.ended_at else None,
        duration_minutes=breach.duration_minutes,
        acknowledged=breach.acknowledged,
    )


def credit_to_response(credit: SLACredit) -> SLACreditResponse:
    """Convert SLACredit to response."""
    return SLACreditResponse(
        credit_id=credit.credit_id,
        customer_id=credit.customer_id,
        period_start=credit.period_start.isoformat(),
        period_end=credit.period_end.isoformat(),
        uptime_actual=round(credit.uptime_actual, 4),
        credit_percentage=credit.credit_percentage,
        invoice_amount_cents=credit.invoice_amount_cents,
        credit_amount_cents=credit.credit_amount_cents,
        status=credit.status.value,
        report_id=credit.report_id,
        created_at=credit.created_at.isoformat(),
        approved_at=credit.approved_at.isoformat() if credit.approved_at else None,
        applied_at=credit.applied_at.isoformat() if credit.applied_at else None,
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.get(
    "/tiers",
    response_model=List[SLATierResponse],
    summary="List SLA tiers",
    description="Get all available SLA tier definitions.",
)
async def list_sla_tiers():
    """List all SLA tier definitions."""
    return [tier_to_response(sla) for sla in SLA_TIERS.values()]


@router.get(
    "/tiers/{tier}",
    response_model=SLATierResponse,
    summary="Get SLA tier",
    description="Get details for a specific SLA tier.",
)
async def get_sla_tier(tier: str):
    """Get a specific SLA tier definition."""
    try:
        sla_tier = SLATier(tier)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"SLA tier not found: {tier}")

    return tier_to_response(SLA_TIERS[sla_tier])


@router.get(
    "/status",
    response_model=List[SLOStatusResponse],
    summary="Get current SLO status",
    description="Get current SLO status for the authenticated customer (last 24 hours).",
)
async def get_slo_status(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get current SLO status for customer."""
    service = get_sla_monitoring_service()
    customer_id = getattr(current_user, "customer_id", "default")

    statuses = service.get_current_slo_status(customer_id)
    return [slo_status_to_response(s) for s in statuses]


@router.get(
    "/status/{customer_id}",
    response_model=List[SLOStatusResponse],
    summary="Get customer SLO status",
    description="Get current SLO status for a specific customer (admin only).",
)
async def get_customer_slo_status(
    customer_id: str,
    current_user: User = Depends(  # noqa: B008
        require_role("admin", "customer_success")  # noqa: B008
    ),  # noqa: B008
):
    """Get SLO status for a specific customer."""
    service = get_sla_monitoring_service()
    statuses = service.get_current_slo_status(customer_id)
    return [slo_status_to_response(s) for s in statuses]


@router.post(
    "/reports",
    response_model=SLAReportResponse,
    summary="Generate SLA report",
    description="Generate an SLA compliance report for the billing period.",
)
async def generate_sla_report(
    request: SLAReportRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Generate SLA report for customer."""
    service = get_sla_monitoring_service()
    customer_id = getattr(current_user, "customer_id", "default")

    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=request.period_days)

    report = service.generate_report(
        customer_id=customer_id,
        period_start=period_start,
        period_end=period_end,
        invoice_amount_cents=request.invoice_amount_cents,
    )

    return report_to_response(report)


@router.get(
    "/reports/{report_id}",
    response_model=SLAReportResponse,
    summary="Get SLA report",
    description="Get a specific SLA report by ID.",
)
async def get_sla_report(
    report_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get a specific SLA report."""
    service = get_sla_monitoring_service()
    customer_id = getattr(current_user, "customer_id", "default")

    report = service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Verify ownership
    if report.customer_id != customer_id:
        user_roles = getattr(current_user, "roles", [])
        if "admin" not in user_roles and "customer_success" not in user_roles:
            raise HTTPException(status_code=403, detail="Access denied")

    return report_to_response(report)


@router.get(
    "/breaches",
    response_model=List[SLABreachResponse],
    summary="List SLA breaches",
    description="List SLA breaches for the customer.",
)
async def list_breaches(
    active_only: bool = Query(  # noqa: B008
        default=False, description="Only show active breaches"
    ),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=200),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """List SLA breaches."""
    service = get_sla_monitoring_service()
    customer_id = getattr(current_user, "customer_id", "default")

    # Check if user can see all customers
    user_roles = getattr(current_user, "roles", [])
    if "admin" in user_roles or "customer_success" in user_roles:
        breaches = service.get_breaches(active_only=active_only)
    else:
        breaches = service.get_breaches(
            customer_id=customer_id, active_only=active_only
        )

    return [breach_to_response(b) for b in breaches[:limit]]


@router.get(
    "/credits",
    response_model=List[SLACreditResponse],
    summary="List SLA credits",
    description="List SLA credits for the customer.",
)
async def list_credits(
    status: Optional[str] = Query(  # noqa: B008
        default=None, description="Filter by status"
    ),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=200),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """List SLA credits."""
    service = get_sla_monitoring_service()
    customer_id = getattr(current_user, "customer_id", "default")

    status_filter = None
    if status:
        try:
            status_filter = CreditStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    # Check if user can see all customers
    user_roles = getattr(current_user, "roles", [])
    if "admin" in user_roles or "billing_admin" in user_roles:
        credits = service.get_credits(status=status_filter)
    else:
        credits = service.get_credits(customer_id=customer_id, status=status_filter)

    return [credit_to_response(c) for c in credits[:limit]]


@router.post(
    "/credits/{credit_id}/approve",
    response_model=SLACreditResponse,
    summary="Approve SLA credit",
    description="Approve a pending SLA credit (admin only).",
)
async def approve_credit(
    credit_id: str,
    current_user: User = Depends(require_role("admin", "billing_admin")),  # noqa: B008
):
    """Approve an SLA credit."""
    service = get_sla_monitoring_service()

    credits = service.get_credits()
    credit = next((c for c in credits if c.credit_id == credit_id), None)

    if not credit:
        raise HTTPException(status_code=404, detail="Credit not found")

    if credit.status != CreditStatus.PENDING:
        raise HTTPException(
            status_code=400, detail=f"Credit is not pending: {credit.status.value}"
        )

    approved_by = getattr(current_user, "email", current_user.sub)
    success = service.approve_credit(credit_id, approved_by)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to approve credit")

    # Refresh credit data
    credits = service.get_credits()
    credit = next((c for c in credits if c.credit_id == credit_id), None)
    if not credit:
        raise HTTPException(status_code=404, detail="Credit not found after approval")

    return credit_to_response(credit)


@router.post(
    "/credits/{credit_id}/apply",
    response_model=SLACreditResponse,
    summary="Apply SLA credit",
    description="Mark an approved credit as applied to invoice (admin only).",
)
async def apply_credit(
    credit_id: str,
    current_user: User = Depends(require_role("admin", "billing_admin")),  # noqa: B008
):
    """Apply an SLA credit to invoice."""
    service = get_sla_monitoring_service()

    credits = service.get_credits()
    credit = next((c for c in credits if c.credit_id == credit_id), None)

    if not credit:
        raise HTTPException(status_code=404, detail="Credit not found")

    if credit.status != CreditStatus.APPROVED:
        raise HTTPException(
            status_code=400, detail=f"Credit is not approved: {credit.status.value}"
        )

    success = service.apply_credit(credit_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to apply credit")

    # Refresh credit data
    credits = service.get_credits()
    credit = next((c for c in credits if c.credit_id == credit_id), None)
    if not credit:
        raise HTTPException(
            status_code=404, detail="Credit not found after application"
        )

    return credit_to_response(credit)


@router.post(
    "/metrics",
    summary="Record metric",
    description="Record an SLA metric data point (internal/system use).",
)
async def record_metric(
    request: RecordMetricRequest,
    current_user: User = Depends(require_role("admin", "system")),  # noqa: B008
):
    """Record an SLA metric."""
    service = get_sla_monitoring_service()

    try:
        metric = SLOMetric(request.metric)
    except ValueError:
        valid_metrics = [m.value for m in SLOMetric]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric. Valid: {valid_metrics}",
        )

    customer_id = getattr(current_user, "customer_id", "default")

    timestamp = None
    if request.timestamp:
        try:
            timestamp = datetime.fromisoformat(request.timestamp.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format")

    service.record_metric(
        customer_id=customer_id,
        metric=metric,
        value=request.value,
        timestamp=timestamp,
    )

    return {"status": "recorded", "metric": request.metric, "value": request.value}


@router.post(
    "/metrics/request",
    summary="Record request metric",
    description="Record API request metrics for SLA tracking (internal use).",
)
async def record_request_metric(
    request: RecordRequestMetricRequest,
    current_user: User = Depends(require_role("admin", "system")),  # noqa: B008
):
    """Record API request metrics."""
    service = get_sla_monitoring_service()
    customer_id = getattr(current_user, "customer_id", "default")

    service.record_request(
        customer_id=customer_id,
        latency_ms=request.latency_ms,
        success=request.success,
        endpoint=request.endpoint,
    )

    return {
        "status": "recorded",
        "latency_ms": request.latency_ms,
        "success": request.success,
    }


@router.get(
    "/summary",
    summary="Get SLA summary",
    description="Get aggregate SLA summary across all customers (admin only).",
)
async def get_sla_summary(
    current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    """Get aggregate SLA summary."""
    service = get_sla_monitoring_service()

    # Count by tier
    tier_counts: Dict[str, int] = {}
    for tier in service._customer_tiers.values():
        tier_counts[tier.value] = tier_counts.get(tier.value, 0) + 1

    # Active breaches
    active_breaches = service.get_breaches(active_only=True)

    # Pending credits
    pending_credits = service.get_credits(status=CreditStatus.PENDING)
    total_pending_cents = sum(c.credit_amount_cents for c in pending_credits)

    return {
        "total_customers": len(service._customer_tiers),
        "customers_by_tier": tier_counts,
        "active_breaches": len(active_breaches),
        "breach_by_severity": {
            sev.value: len([b for b in active_breaches if b.severity == sev])
            for sev in BreachSeverity
        },
        "pending_credits_count": len(pending_credits),
        "pending_credits_total_cents": total_pending_cents,
    }
