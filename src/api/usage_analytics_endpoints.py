"""
Usage Analytics API Endpoints.

Provides REST API for usage tracking and analytics:
- GET /api/v1/analytics/usage - Get usage metrics summary
- GET /api/v1/analytics/api - Get API usage statistics
- GET /api/v1/analytics/features - Get feature adoption metrics
- GET /api/v1/analytics/engagement - Get user engagement metrics
- POST /api/v1/analytics/track - Track a usage event
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user, require_role
from src.services.usage_analytics_service import (
    FeatureAdoption,
    MetricType,
    TimeGranularity,
    UsageSummary,
    get_usage_analytics_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["Analytics"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class TrackEventRequest(BaseModel):
    """Request to track a usage event."""

    metric_type: str = Field(
        ...,
        description="Type: api_request, feature_usage, agent_execution, login, etc.",
    )
    event_name: str = Field(..., min_length=1, max_length=200, description="Event name")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )
    duration_ms: Optional[int] = Field(
        default=None, ge=0, description="Duration in milliseconds"
    )
    success: bool = Field(default=True, description="Whether event was successful")


class APIUsageResponse(BaseModel):
    """API usage statistics response."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    average_latency_ms: float
    by_endpoint: Dict[str, int]
    by_day: Dict[str, int]
    period_days: int


class FeatureAdoptionResponse(BaseModel):
    """Feature adoption metrics response."""

    feature_name: str
    total_uses: int
    unique_users: int
    adoption_rate: float
    avg_uses_per_user: float
    trend: str  # increasing, decreasing, stable


class UserEngagementResponse(BaseModel):
    """User engagement metrics response."""

    user_id: str
    total_events: int
    features_used: List[str]
    last_active: str
    engagement_score: float
    sessions_count: int


class UsageSummaryResponse(BaseModel):
    """Usage summary response."""

    total_events: int
    unique_users: int
    api_requests: int
    agent_executions: int
    feature_usages: int
    period_days: int
    by_type: Dict[str, int]
    top_features: List[FeatureAdoptionResponse]
    top_users: List[UserEngagementResponse]


class TrackEventResponse(BaseModel):
    """Response after tracking an event."""

    event_id: str
    tracked: bool
    message: str


# =============================================================================
# Helper Functions
# =============================================================================


def feature_adoption_to_response(adoption: FeatureAdoption) -> FeatureAdoptionResponse:
    """Convert FeatureAdoption to response model."""
    return FeatureAdoptionResponse(
        feature_name=adoption.feature_name,
        total_uses=adoption.usage_count,
        unique_users=adoption.active_users,
        adoption_rate=adoption.adoption_rate,
        avg_uses_per_user=adoption.avg_daily_usage,
        trend=adoption.trend,
    )


def user_engagement_to_response(
    user_id: str,
    total_events: int,
    features_used: List[str],
    last_active: datetime,
    engagement_score: float,
    sessions_count: int,
) -> UserEngagementResponse:
    """Convert user engagement data to response model."""
    return UserEngagementResponse(
        user_id=user_id,
        total_events=total_events,
        features_used=features_used,
        last_active=last_active.isoformat(),
        engagement_score=engagement_score,
        sessions_count=sessions_count,
    )


def summary_to_response(summary: UsageSummary, days: int) -> UsageSummaryResponse:
    """Convert UsageSummary to response model."""
    # Calculate total events from key metrics
    total_events = summary.total_api_calls + summary.total_agent_executions

    # Build by_type dict from key metrics
    by_type: Dict[str, int] = {
        "api_request": summary.total_api_calls,
        "agent_execution": summary.total_agent_executions,
    }

    return UsageSummaryResponse(
        total_events=total_events,
        unique_users=summary.total_active_users,
        api_requests=summary.total_api_calls,
        agent_executions=summary.total_agent_executions,
        feature_usages=sum(f.usage_count for f in summary.feature_adoption),
        period_days=days,
        by_type=by_type,
        top_features=[
            feature_adoption_to_response(f) for f in summary.feature_adoption[:5]
        ],
        top_users=[],  # Per-user engagement not supported by service
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.post(
    "/track",
    response_model=TrackEventResponse,
    summary="Track usage event",
    description="Track a usage event for analytics.",
)
async def track_event(
    request: TrackEventRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Track a usage event."""
    try:
        # Validate metric type
        try:
            metric_type = MetricType(request.metric_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metric type: {request.metric_type}",
            )

        service = get_usage_analytics_service()
        customer_id = getattr(current_user, "customer_id", "default")

        event = await service.track_event(
            customer_id=customer_id,
            user_id=current_user.sub,
            metric_type=metric_type,
            event_name=request.event_name,
            metadata=request.metadata,
            duration_ms=request.duration_ms,
            status="success" if request.success else "failure",
        )

        return TrackEventResponse(
            event_id=event.event_id,
            tracked=True,
            message="Event tracked successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error tracking event: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to track event")


@router.get(
    "/usage",
    response_model=UsageSummaryResponse,
    summary="Get usage summary",
    description="Get aggregated usage analytics summary.",
)
async def get_usage_summary(
    days: int = Query(  # noqa: B008
        default=30, ge=1, le=365, description="Days to include"
    ),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get usage analytics summary."""
    try:
        service = get_usage_analytics_service()
        customer_id = getattr(current_user, "customer_id", None)

        # Admins see all, others see their org
        user_roles = getattr(current_user, "roles", [])
        if "admin" not in user_roles:
            customer_id = customer_id or "default"
        else:
            customer_id = None

        summary = await service.get_usage_summary(
            customer_id=customer_id,
            days=days,
        )

        return summary_to_response(summary, days)

    except Exception as e:
        logger.error("Error getting usage summary: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve usage summary")


@router.get(
    "/api",
    response_model=APIUsageResponse,
    summary="Get API usage",
    description="Get API request statistics.",
)
async def get_api_usage(
    days: int = Query(  # noqa: B008
        default=30, ge=1, le=365, description="Days to include"
    ),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get API usage statistics."""
    try:
        service = get_usage_analytics_service()
        customer_id = getattr(current_user, "customer_id", None)

        # Admins see all, others see their org
        user_roles = getattr(current_user, "roles", [])
        if "admin" not in user_roles:
            customer_id = customer_id or "default"
        else:
            customer_id = None

        api_usage = await service.get_api_usage(
            customer_id=customer_id,
            days=days,
        )

        return APIUsageResponse(
            total_requests=api_usage["total_requests"],
            successful_requests=api_usage["successful_requests"],
            failed_requests=api_usage["failed_requests"],
            success_rate=api_usage["success_rate"],
            average_latency_ms=api_usage["average_latency_ms"],
            by_endpoint=api_usage["by_endpoint"],
            by_day=api_usage["by_day"],
            period_days=days,
        )

    except Exception as e:
        logger.error("Error getting API usage: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve API usage")


@router.get(
    "/features",
    response_model=List[FeatureAdoptionResponse],
    summary="Get feature adoption",
    description="Get feature adoption metrics.",
)
async def get_feature_adoption(
    days: int = Query(  # noqa: B008
        default=30, ge=1, le=365, description="Days to include"
    ),  # noqa: B008
    limit: int = Query(  # noqa: B008
        default=20, ge=1, le=100, description="Max features to return"
    ),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get feature adoption metrics."""
    try:
        service = get_usage_analytics_service()
        customer_id = getattr(current_user, "customer_id", None)

        # Admins see all, others see their org
        user_roles = getattr(current_user, "roles", [])
        if "admin" not in user_roles:
            customer_id = customer_id or "default"
        else:
            customer_id = None

        features = await service.get_feature_adoption(
            customer_id=customer_id,
            days=days,
        )

        return [feature_adoption_to_response(f) for f in features[:limit]]

    except Exception as e:
        logger.error("Error getting feature adoption: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve feature adoption"
        )


@router.get(
    "/engagement",
    response_model=List[UserEngagementResponse],
    summary="Get user engagement",
    description="Get user engagement metrics.",
)
async def get_user_engagement(
    days: int = Query(  # noqa: B008
        default=30, ge=1, le=365, description="Days to include"
    ),  # noqa: B008
    limit: int = Query(  # noqa: B008
        default=20, ge=1, le=100, description="Max users to return"
    ),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get user engagement metrics."""
    try:
        service = get_usage_analytics_service()
        customer_id = getattr(current_user, "customer_id", None)

        # Admins see all, others see their org
        user_roles = getattr(current_user, "roles", [])
        if "admin" not in user_roles:
            customer_id = customer_id or "default"
        else:
            customer_id = None

        # Note: service.get_user_engagement returns aggregate UserEngagement object,
        # not per-user data. Returning empty list until service supports per-user metrics.
        await service.get_user_engagement(  # noqa: F841 - result unused until per-user tracking
            customer_id=customer_id,
            days=days,
        )

        # TODO: Implement per-user engagement tracking in service
        return []

    except Exception as e:
        logger.error("Error getting user engagement: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve user engagement"
        )


@router.get(
    "/export",
    summary="Export analytics data",
    description="Export analytics data as CSV (admin only).",
)
async def export_analytics(
    days: int = Query(  # noqa: B008
        default=30, ge=1, le=365, description="Days to include"
    ),  # noqa: B008
    granularity: str = Query(  # noqa: B008
        default="day", description="Time granularity: hour, day, week"
    ),
    current_user: User = Depends(require_role("admin", "operator")),  # noqa: B008
):
    """Export analytics data for reporting."""
    try:
        # Validate granularity
        try:
            _time_granularity = TimeGranularity(granularity)  # noqa: F841
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid granularity: {granularity}. Use: hour, day, week",
            )

        service = get_usage_analytics_service()

        # Get all data for export
        summary = await service.get_usage_summary(customer_id=None, days=days)
        api_usage = await service.get_api_usage(customer_id=None, days=days)
        features = await service.get_feature_adoption(customer_id=None, days=days)

        return {
            "export_date": datetime.now().isoformat(),
            "period_days": days,
            "granularity": granularity,
            "summary": {
                "total_events": summary.total_api_calls
                + summary.total_agent_executions,
                "unique_users": summary.total_active_users,
                "api_requests": summary.total_api_calls,
                "agent_executions": summary.total_agent_executions,
                "feature_usages": sum(f.usage_count for f in summary.feature_adoption),
                "by_type": {
                    "api_request": summary.total_api_calls,
                    "agent_execution": summary.total_agent_executions,
                },
            },
            "api_usage": api_usage,
            "feature_adoption": [
                {
                    "feature": f.feature_name,
                    "uses": f.usage_count,
                    "users": f.active_users,
                    "adoption_rate": f.adoption_rate,
                    "trend": f.trend,
                }
                for f in features
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error exporting analytics: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to export analytics")
