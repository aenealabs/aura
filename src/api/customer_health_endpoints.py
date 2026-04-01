"""
Customer Health API Endpoints.

Provides REST API for customer health score management:
- GET /api/v1/customer-health/score - Get health score for customer
- GET /api/v1/customer-health/trend - Get health trend
- GET /api/v1/customer-health/at-risk - List at-risk customers
- GET /api/v1/customer-health/expansion - List expansion opportunities
- POST /api/v1/customer-health/calculate - Recalculate health score
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.auth import User, get_current_user, require_role
from src.services.customer_health_service import (
    ChurnRisk,
    CustomerHealthScore,
    ExpansionPotential,
    HealthScoreComponent,
    HealthStatus,
    HealthTrend,
    get_customer_health_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/customer-health",
    tags=["Customer Health"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class HealthComponentResponse(BaseModel):
    """Health score component response."""

    name: str
    score: float
    weight: float
    weighted_score: float
    trend: str
    factors: List[Dict[str, Any]]


class HealthScoreResponse(BaseModel):
    """Complete health score response."""

    customer_id: str
    overall_score: float
    status: str
    churn_risk: str
    expansion_potential: str
    components: Dict[str, HealthComponentResponse]
    recommendations: List[str]
    alerts: List[Dict[str, Any]]
    calculated_at: str
    next_review: str


class HealthTrendResponse(BaseModel):
    """Health trend response."""

    customer_id: str
    scores: List[Dict[str, Any]]
    period_start: str
    period_end: str
    trend_direction: str
    change_percent: float


class AtRiskCustomerResponse(BaseModel):
    """At-risk customer summary."""

    customer_id: str
    overall_score: float
    status: str
    churn_risk: str
    primary_concerns: List[str]
    recommended_action: str


class ExpansionOpportunityResponse(BaseModel):
    """Expansion opportunity summary."""

    customer_id: str
    overall_score: float
    expansion_potential: str
    value_signals: List[str]
    recommended_action: str


# =============================================================================
# Helper Functions
# =============================================================================


def component_to_response(component: HealthScoreComponent) -> HealthComponentResponse:
    """Convert HealthScoreComponent to response model."""
    return HealthComponentResponse(
        name=component.name,
        score=component.score,
        weight=component.weight,
        weighted_score=component.weighted_score,
        trend=component.trend,
        factors=component.factors,
    )


def health_score_to_response(score: CustomerHealthScore) -> HealthScoreResponse:
    """Convert CustomerHealthScore to response model."""
    return HealthScoreResponse(
        customer_id=score.customer_id,
        overall_score=score.overall_score,
        status=score.status.value,
        churn_risk=score.churn_risk.value,
        expansion_potential=score.expansion_potential.value,
        components={
            name: component_to_response(comp) for name, comp in score.components.items()
        },
        recommendations=score.recommendations,
        alerts=score.alerts,
        calculated_at=score.calculated_at.isoformat(),
        next_review=score.next_review.isoformat(),
    )


def trend_to_response(trend: HealthTrend) -> HealthTrendResponse:
    """Convert HealthTrend to response model."""
    return HealthTrendResponse(
        customer_id=trend.customer_id,
        scores=trend.scores,
        period_start=trend.period_start.isoformat(),
        period_end=trend.period_end.isoformat(),
        trend_direction=trend.trend_direction,
        change_percent=trend.change_percent,
    )


def to_at_risk_response(score: CustomerHealthScore) -> AtRiskCustomerResponse:
    """Convert health score to at-risk summary."""
    # Identify primary concerns
    concerns = []
    for name, comp in score.components.items():
        if comp.score < 50:
            concerns.append(f"Low {name.replace('_', ' ')} ({comp.score})")
        elif comp.trend == "declining":
            concerns.append(f"Declining {name.replace('_', ' ')}")

    # Determine recommended action
    if score.status == HealthStatus.CRITICAL:
        action = "Immediate executive outreach"
    elif score.churn_risk == ChurnRisk.HIGH:
        action = "Schedule urgent review meeting"
    else:
        action = "Schedule health check call"

    return AtRiskCustomerResponse(
        customer_id=score.customer_id,
        overall_score=score.overall_score,
        status=score.status.value,
        churn_risk=score.churn_risk.value,
        primary_concerns=concerns[:3],
        recommended_action=action,
    )


def to_expansion_response(score: CustomerHealthScore) -> ExpansionOpportunityResponse:
    """Convert health score to expansion opportunity summary."""
    # Identify value signals
    signals = []
    for name, comp in score.components.items():
        if comp.score >= 75:
            signals.append(f"High {name.replace('_', ' ')} ({comp.score})")
        if comp.trend == "improving":
            signals.append(f"Growing {name.replace('_', ' ')}")

    # Determine recommended action
    if score.expansion_potential == ExpansionPotential.HIGH:
        action = "Discuss upgrade options in next meeting"
    else:
        action = "Monitor for expansion readiness"

    return ExpansionOpportunityResponse(
        customer_id=score.customer_id,
        overall_score=score.overall_score,
        expansion_potential=score.expansion_potential.value,
        value_signals=signals[:3],
        recommended_action=action,
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.get(
    "/score",
    response_model=Optional[HealthScoreResponse],
    summary="Get health score",
    description="Get the current health score for the customer.",
)
async def get_health_score(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get health score for current customer."""
    service = get_customer_health_service()
    customer_id = getattr(current_user, "customer_id", "default")

    score = await service.get_health_score(customer_id)
    if not score:
        # Calculate if not available
        score = await service.calculate_health_score(customer_id)

    return health_score_to_response(score)


@router.get(
    "/score/{customer_id}",
    response_model=HealthScoreResponse,
    summary="Get health score for customer",
    description="Get health score for a specific customer (admin only).",
)
async def get_customer_health_score(
    customer_id: str,
    current_user: User = Depends(  # noqa: B008
        require_role("admin", "customer_success")  # noqa: B008
    ),  # noqa: B008
):
    """Get health score for a specific customer."""
    service = get_customer_health_service()

    score = await service.get_health_score(customer_id)
    if not score:
        score = await service.calculate_health_score(customer_id)

    return health_score_to_response(score)


@router.post(
    "/calculate",
    response_model=HealthScoreResponse,
    summary="Recalculate health score",
    description="Force recalculation of health score.",
)
async def calculate_health_score(
    days: int = Query(  # noqa: B008
        default=30, ge=1, le=365, description="Days to analyze"
    ),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Recalculate health score for current customer."""
    service = get_customer_health_service()
    customer_id = getattr(current_user, "customer_id", "default")

    try:
        score = await service.calculate_health_score(customer_id, days=days)
        return health_score_to_response(score)

    except Exception as e:
        logger.error("Error calculating health score: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to calculate health score")


@router.get(
    "/trend",
    response_model=HealthTrendResponse,
    summary="Get health trend",
    description="Get health score trend over time.",
)
async def get_health_trend(
    days: int = Query(  # noqa: B008
        default=90, ge=7, le=365, description="Days of history"
    ),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get health trend for current customer."""
    service = get_customer_health_service()
    customer_id = getattr(current_user, "customer_id", "default")

    trend = await service.get_health_trend(customer_id, days=days)
    return trend_to_response(trend)


@router.get(
    "/at-risk",
    response_model=List[AtRiskCustomerResponse],
    summary="List at-risk customers",
    description="Get list of customers at risk of churn (admin/CS only).",
)
async def list_at_risk_customers(
    limit: int = Query(  # noqa: B008
        default=20, ge=1, le=100, description="Max customers"
    ),  # noqa: B008
    current_user: User = Depends(  # noqa: B008
        require_role("admin", "customer_success")  # noqa: B008
    ),  # noqa: B008
):
    """List customers at risk of churn."""
    service = get_customer_health_service()

    at_risk = await service.list_at_risk_customers(limit=limit)
    return [to_at_risk_response(score) for score in at_risk]


@router.get(
    "/expansion",
    response_model=List[ExpansionOpportunityResponse],
    summary="List expansion opportunities",
    description="Get list of customers with expansion potential (admin/CS only).",
)
async def list_expansion_opportunities(
    limit: int = Query(  # noqa: B008
        default=20, ge=1, le=100, description="Max customers"
    ),  # noqa: B008
    current_user: User = Depends(  # noqa: B008
        require_role("admin", "customer_success")  # noqa: B008
    ),  # noqa: B008
):
    """List expansion opportunities."""
    service = get_customer_health_service()

    opportunities = await service.list_expansion_opportunities(limit=limit)
    return [to_expansion_response(score) for score in opportunities]


@router.get(
    "/summary",
    summary="Get health summary",
    description="Get aggregate health summary across all customers (admin only).",
)
async def get_health_summary(
    current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    """Get aggregate health summary."""
    service = get_customer_health_service()

    # Count by status
    all_scores = list(service._health_scores.values())

    by_status: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    total_score: float = 0.0

    for score in all_scores:
        by_status[score.status.value] = by_status.get(score.status.value, 0) + 1
        by_risk[score.churn_risk.value] = by_risk.get(score.churn_risk.value, 0) + 1
        total_score += float(score.overall_score)

    avg_score = total_score / len(all_scores) if all_scores else 0

    return {
        "total_customers": len(all_scores),
        "average_score": round(avg_score, 1),
        "by_status": by_status,
        "by_churn_risk": by_risk,
        "at_risk_count": by_status.get("at_risk", 0) + by_status.get("critical", 0),
        "healthy_count": by_status.get("healthy", 0) + by_status.get("excellent", 0),
    }
