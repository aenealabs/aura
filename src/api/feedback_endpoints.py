"""
Customer Feedback API Endpoints.

Provides REST API for beta feedback collection:
- POST /api/v1/feedback - Submit feedback
- GET /api/v1/feedback - List feedback
- GET /api/v1/feedback/{id} - Get feedback details
- PUT /api/v1/feedback/{id}/status - Update status (admin)
- POST /api/v1/feedback/nps - Submit NPS survey
- GET /api/v1/feedback/summary - Get feedback summary
- GET /api/v1/feedback/nps/results - Get NPS results
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user, require_role
from src.services.feedback_service import (
    FeedbackItem,
    FeedbackStatus,
    FeedbackType,
    NPSSurveyResult,
    get_feedback_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/feedback",
    tags=["Feedback"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class FeedbackSubmitRequest(BaseModel):
    """Request to submit feedback."""

    feedback_type: str = Field(
        ...,
        description="Type: general, bug_report, feature_request, usability, documentation, performance",
    )
    title: str = Field(..., min_length=5, max_length=200, description="Short title")
    description: str = Field(
        ..., min_length=10, max_length=5000, description="Detailed description"
    )
    tags: Optional[List[str]] = Field(default=None, description="Optional tags")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context"
    )
    page_url: Optional[str] = Field(
        default=None, description="Page where feedback submitted"
    )


class NPSSubmitRequest(BaseModel):
    """Request to submit NPS survey."""

    score: int = Field(..., ge=0, le=10, description="NPS score 0-10")
    comment: Optional[str] = Field(
        default=None, max_length=2000, description="Optional comment"
    )


class FeedbackStatusUpdateRequest(BaseModel):
    """Request to update feedback status."""

    status: str = Field(
        ...,
        description="Status: acknowledged, in_review, planned, in_progress, completed, wont_fix, duplicate",
    )
    response: Optional[str] = Field(
        default=None, max_length=2000, description="Response to customer"
    )


class FeedbackResponse(BaseModel):
    """Feedback item response."""

    feedback_id: str
    customer_id: str
    user_email: str
    feedback_type: str
    title: str
    description: str
    status: str
    priority: str
    nps_score: Optional[int]
    tags: List[str]
    page_url: Optional[str]
    created_at: str
    updated_at: Optional[str]
    resolved_at: Optional[str]
    response: Optional[str]


class NPSResultsResponse(BaseModel):
    """NPS survey results response."""

    total_responses: int
    promoters: int
    passives: int
    detractors: int
    nps_score: float
    average_score: float
    period_days: int


class FeedbackSummaryResponse(BaseModel):
    """Feedback summary response."""

    total_feedback: int
    by_type: Dict[str, int]
    by_status: Dict[str, int]
    by_priority: Dict[str, int]
    nps: Optional[NPSResultsResponse]
    trending_tags: List[str]


class PaginatedFeedbackResponse(BaseModel):
    """Paginated feedback list response with cursor."""

    items: List[FeedbackResponse]
    next_cursor: Optional[str] = Field(
        default=None, description="Cursor for next page, null if no more results"
    )
    has_more: bool = Field(description="Whether more results are available")


# =============================================================================
# Helper Functions
# =============================================================================


def feedback_to_response(feedback: FeedbackItem) -> FeedbackResponse:
    """Convert FeedbackItem to response model."""
    return FeedbackResponse(
        feedback_id=feedback.feedback_id,
        customer_id=feedback.customer_id,
        user_email=feedback.user_email,
        feedback_type=feedback.feedback_type.value,
        title=feedback.title,
        description=feedback.description,
        status=feedback.status.value,
        priority=feedback.priority.value,
        nps_score=feedback.nps_score,
        tags=feedback.tags,
        page_url=feedback.page_url,
        created_at=feedback.created_at.isoformat(),
        updated_at=feedback.updated_at.isoformat() if feedback.updated_at else None,
        resolved_at=feedback.resolved_at.isoformat() if feedback.resolved_at else None,
        response=feedback.response,
    )


def nps_to_response(nps: NPSSurveyResult, days: int) -> NPSResultsResponse:
    """Convert NPSSurveyResult to response model."""
    return NPSResultsResponse(
        total_responses=nps.total_responses,
        promoters=nps.promoters,
        passives=nps.passives,
        detractors=nps.detractors,
        nps_score=nps.nps_score,
        average_score=nps.average_score,
        period_days=days,
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.post(
    "",
    response_model=FeedbackResponse,
    summary="Submit feedback",
    description="Submit feedback about the platform.",
)
async def submit_feedback(
    request: FeedbackSubmitRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Submit new feedback."""
    try:
        # Validate feedback type
        try:
            feedback_type = FeedbackType(request.feedback_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid feedback type: {request.feedback_type}",
            )

        service = get_feedback_service()
        customer_id = getattr(current_user, "customer_id", "default")

        # Get browser info from headers
        user_agent = http_request.headers.get("user-agent", "")

        feedback = await service.submit_feedback(
            customer_id=customer_id,
            user_id=current_user.sub,
            user_email=current_user.email or "",
            feedback_type=feedback_type,
            title=request.title,
            description=request.description,
            tags=request.tags,
            metadata=request.metadata,
            page_url=request.page_url,
            browser_info=user_agent[:500] if user_agent else None,
        )

        return feedback_to_response(feedback)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit feedback")


@router.post(
    "/nps",
    response_model=FeedbackResponse,
    summary="Submit NPS survey",
    description="Submit Net Promoter Score survey response.",
)
async def submit_nps_survey(
    request: NPSSubmitRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Submit NPS survey response."""
    try:
        service = get_feedback_service()
        customer_id = getattr(current_user, "customer_id", "default")

        # Create NPS feedback
        title = f"NPS Survey: Score {request.score}"
        description = request.comment or f"NPS score of {request.score} submitted"

        feedback = await service.submit_feedback(
            customer_id=customer_id,
            user_id=current_user.sub,
            user_email=current_user.email or "",
            feedback_type=FeedbackType.NPS_SURVEY,
            title=title,
            description=description,
            nps_score=request.score,
            tags=["nps", f"nps-{request.score}"],
        )

        return feedback_to_response(feedback)

    except Exception as e:
        logger.error(f"Error submitting NPS survey: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit NPS survey")


@router.get(
    "",
    response_model=PaginatedFeedbackResponse,
    summary="List feedback",
    description="List feedback with optional filters using cursor-based pagination.",
)
async def list_feedback(
    feedback_type: Optional[str] = Query(  # noqa: B008
        default=None, description="Filter by type"
    ),  # noqa: B008
    status: Optional[str] = Query(  # noqa: B008
        default=None, description="Filter by status"
    ),  # noqa: B008
    limit: int = Query(  # noqa: B008
        default=50, ge=1, le=100, description="Max results"
    ),  # noqa: B008
    cursor: Optional[str] = Query(  # noqa: B008
        default=None, description="Pagination cursor from previous response"
    ),
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """List feedback items."""
    try:
        service = get_feedback_service()
        customer_id = getattr(current_user, "customer_id", None)

        # Parse filters
        type_filter = None
        if feedback_type:
            try:
                type_filter = FeedbackType(feedback_type)
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"Invalid feedback type: {feedback_type}"
                )

        status_filter = None
        if status:
            try:
                status_filter = FeedbackStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        # Non-admins can only see their own organization's feedback
        user_roles = getattr(current_user, "roles", [])
        if "admin" not in user_roles and "operator" not in user_roles:
            if not customer_id:
                customer_id = "default"

        feedback_list, next_cursor = await service.list_feedback(
            customer_id=customer_id if "admin" not in user_roles else None,
            feedback_type=type_filter,
            status=status_filter,
            limit=limit,
            cursor=cursor,
        )

        return PaginatedFeedbackResponse(
            items=[feedback_to_response(f) for f in feedback_list],
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list feedback")


@router.get(
    "/summary",
    response_model=FeedbackSummaryResponse,
    summary="Get feedback summary",
    description="Get aggregated feedback summary.",
)
async def get_feedback_summary(
    days: int = Query(  # noqa: B008
        default=30, ge=1, le=365, description="Days to include"
    ),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get feedback summary."""
    try:
        service = get_feedback_service()
        customer_id = getattr(current_user, "customer_id", None)

        # Admins see all, others see their org
        user_roles = getattr(current_user, "roles", [])
        if "admin" not in user_roles:
            customer_id = customer_id or "default"
        else:
            customer_id = None

        summary = await service.get_feedback_summary(
            customer_id=customer_id,
            days=days,
        )

        nps_response = None
        if summary.nps:
            nps_response = nps_to_response(summary.nps, days)

        return FeedbackSummaryResponse(
            total_feedback=summary.total_feedback,
            by_type=summary.by_type,
            by_status=summary.by_status,
            by_priority=summary.by_priority,
            nps=nps_response,
            trending_tags=summary.trending_tags,
        )

    except Exception as e:
        logger.error(f"Error getting feedback summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve feedback summary"
        )


@router.get(
    "/nps/results",
    response_model=NPSResultsResponse,
    summary="Get NPS results",
    description="Get Net Promoter Score calculation results.",
)
async def get_nps_results(
    days: int = Query(  # noqa: B008
        default=30, ge=1, le=365, description="Days to include"
    ),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get NPS survey results."""
    try:
        service = get_feedback_service()
        customer_id = getattr(current_user, "customer_id", None)

        # Admins see all, others see their org
        user_roles = getattr(current_user, "roles", [])
        if "admin" not in user_roles:
            customer_id = customer_id or "default"
        else:
            customer_id = None

        nps = await service.get_nps_results(
            customer_id=customer_id,
            days=days,
        )

        return nps_to_response(nps, days)

    except Exception as e:
        logger.error(f"Error getting NPS results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve NPS results")


@router.get(
    "/{feedback_id}",
    response_model=FeedbackResponse,
    summary="Get feedback",
    description="Get a specific feedback item.",
)
async def get_feedback(
    feedback_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get feedback by ID."""
    try:
        service = get_feedback_service()
        feedback = await service.get_feedback(feedback_id)

        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        # Check access
        customer_id = getattr(current_user, "customer_id", None)
        user_roles = getattr(current_user, "roles", [])
        if "admin" not in user_roles and feedback.customer_id != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return feedback_to_response(feedback)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve feedback")


@router.put(
    "/{feedback_id}/status",
    response_model=FeedbackResponse,
    summary="Update feedback status",
    description="Update feedback status (admin/operator only).",
)
async def update_feedback_status(
    feedback_id: str,
    request: FeedbackStatusUpdateRequest,
    current_user: User = Depends(require_role("admin", "operator")),  # noqa: B008
):
    """Update feedback status."""
    try:
        # Validate status
        try:
            status = FeedbackStatus(request.status)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid status: {request.status}"
            )

        service = get_feedback_service()
        feedback = await service.update_feedback_status(
            feedback_id=feedback_id,
            status=status,
            response=request.response,
        )

        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        return feedback_to_response(feedback)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating feedback status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update feedback status")
