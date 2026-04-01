"""
Project Aura - Onboarding API Endpoints

REST API endpoints for customer onboarding state management.

Endpoints:
- GET   /api/v1/onboarding/state               - Get full onboarding state
- PATCH /api/v1/onboarding/state               - Update state (partial)
- POST  /api/v1/onboarding/tour/start          - Start tour
- POST  /api/v1/onboarding/tour/step           - Complete tour step
- POST  /api/v1/onboarding/tour/complete       - Mark tour complete
- POST  /api/v1/onboarding/tour/skip           - Skip tour
- POST  /api/v1/onboarding/modal/dismiss       - Dismiss welcome modal
- POST  /api/v1/onboarding/tooltip/{id}/dismiss- Dismiss tooltip
- POST  /api/v1/onboarding/checklist/{id}/complete - Complete checklist item
- POST  /api/v1/onboarding/checklist/dismiss   - Dismiss checklist
- POST  /api/v1/onboarding/video/{id}/progress - Update video progress
- GET   /api/v1/onboarding/videos              - Get video catalog
- POST  /api/v1/onboarding/reset               - Reset onboarding state (dev only)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from src.services.onboarding_service import OnboardingService, get_onboarding_service

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/onboarding", tags=["Onboarding"])

# ============================================================================
# Pydantic Models
# ============================================================================


class ChecklistStepsModel(BaseModel):
    """Checklist step completion state."""

    connect_repository: bool = False
    configure_analysis: bool = False
    run_first_scan: bool = False
    review_vulnerabilities: bool = False
    invite_team_member: bool = False


class VideoProgressModel(BaseModel):
    """Video progress data."""

    percent: float = Field(ge=0, le=100)
    completed: bool = False


class OnboardingStateModel(BaseModel):
    """Full onboarding state."""

    user_id: Optional[str] = None
    organization_id: Optional[str] = None

    # Welcome Modal
    welcome_modal_dismissed: bool = False
    welcome_modal_dismissed_at: Optional[str] = None

    # Tour
    tour_completed: bool = False
    tour_step: int = 0
    tour_started_at: Optional[str] = None
    tour_completed_at: Optional[str] = None
    tour_skipped: bool = False

    # Checklist
    checklist_dismissed: bool = False
    checklist_steps: ChecklistStepsModel = Field(default_factory=ChecklistStepsModel)
    checklist_started_at: Optional[str] = None
    checklist_completed_at: Optional[str] = None

    # Tooltips
    dismissed_tooltips: list[str] = Field(default_factory=list)

    # Video progress
    video_progress: dict[str, VideoProgressModel] = Field(default_factory=dict)

    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class OnboardingStateUpdateModel(BaseModel):
    """Partial onboarding state update."""

    welcome_modal_dismissed: Optional[bool] = None
    tour_completed: Optional[bool] = None
    tour_step: Optional[int] = None
    tour_skipped: Optional[bool] = None
    checklist_dismissed: Optional[bool] = None
    checklist_steps: Optional[ChecklistStepsModel] = None
    dismissed_tooltips: Optional[list[str]] = None


class TourStepRequest(BaseModel):
    """Tour step completion request."""

    step: int = Field(ge=0)


class VideoProgressRequest(BaseModel):
    """Video progress update request."""

    progress: float = Field(ge=0, le=100)
    completed: bool = False


class VideoChapterModel(BaseModel):
    """Video chapter metadata."""

    time: int
    title: str


class VideoModel(BaseModel):
    """Video catalog entry."""

    id: str
    title: str
    description: str
    duration: int  # seconds
    thumbnail_url: Optional[str] = None
    video_url: str
    chapters: list[VideoChapterModel] = Field(default_factory=list)


class SuccessResponse(BaseModel):
    """Generic success response."""

    success: bool = True
    message: Optional[str] = None


# ============================================================================
# Helper Functions
# ============================================================================


def get_user_id_from_request(request: Request) -> str:
    """Extract user ID from request context."""
    # In production, this would come from authenticated user context
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "sub"):
        return user.sub
    # For development/testing, use a default
    return "dev-user-001"


def get_organization_id_from_request(request: Request) -> str:
    """Extract organization ID from request context."""
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "organization_id"):
        return user.organization_id
    return "dev-org-001"


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/state", response_model=OnboardingStateModel)
async def get_onboarding_state(
    request: Request,
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> OnboardingStateModel:
    """Get full onboarding state for current user."""
    user_id = get_user_id_from_request(request)
    org_id = get_organization_id_from_request(request)

    state = await service.get_state(user_id, org_id)
    return OnboardingStateModel(**state)


@router.patch("/state", response_model=OnboardingStateModel)
async def update_onboarding_state(
    request: Request,
    updates: OnboardingStateUpdateModel,
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> OnboardingStateModel:
    """Partially update onboarding state."""
    user_id = get_user_id_from_request(request)
    org_id = get_organization_id_from_request(request)

    # Convert to dict, excluding None values
    update_dict = updates.model_dump(exclude_none=True)
    state = await service.update_state(user_id, org_id, update_dict)
    return OnboardingStateModel(**state)


@router.post("/modal/dismiss", response_model=SuccessResponse)
async def dismiss_welcome_modal(
    request: Request,
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> SuccessResponse:
    """Dismiss the welcome modal."""
    user_id = get_user_id_from_request(request)
    org_id = get_organization_id_from_request(request)

    await service.dismiss_modal(user_id, org_id)
    return SuccessResponse(message="Welcome modal dismissed")


@router.post("/tour/start", response_model=SuccessResponse)
async def start_tour(
    request: Request,
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> SuccessResponse:
    """Start the welcome tour."""
    user_id = get_user_id_from_request(request)
    org_id = get_organization_id_from_request(request)

    await service.start_tour(user_id, org_id)
    return SuccessResponse(message="Tour started")


@router.post("/tour/step", response_model=SuccessResponse)
async def complete_tour_step(
    request: Request,
    data: TourStepRequest,
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> SuccessResponse:
    """Complete a tour step."""
    user_id = get_user_id_from_request(request)
    org_id = get_organization_id_from_request(request)

    await service.complete_tour_step(user_id, org_id, data.step)
    return SuccessResponse(message=f"Tour step {data.step} completed")


@router.post("/tour/complete", response_model=SuccessResponse)
async def complete_tour(
    request: Request,
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> SuccessResponse:
    """Mark tour as complete."""
    user_id = get_user_id_from_request(request)
    org_id = get_organization_id_from_request(request)

    await service.complete_tour(user_id, org_id)
    return SuccessResponse(message="Tour completed")


@router.post("/tour/skip", response_model=SuccessResponse)
async def skip_tour(
    request: Request,
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> SuccessResponse:
    """Skip the tour."""
    user_id = get_user_id_from_request(request)
    org_id = get_organization_id_from_request(request)

    await service.skip_tour(user_id, org_id)
    return SuccessResponse(message="Tour skipped")


@router.post("/tooltip/{tooltip_id}/dismiss", response_model=SuccessResponse)
async def dismiss_tooltip(
    request: Request,
    tooltip_id: str,
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> SuccessResponse:
    """Dismiss a feature tooltip."""
    user_id = get_user_id_from_request(request)
    org_id = get_organization_id_from_request(request)

    await service.dismiss_tooltip(user_id, org_id, tooltip_id)
    return SuccessResponse(message=f"Tooltip {tooltip_id} dismissed")


@router.post("/checklist/{item_id}/complete", response_model=SuccessResponse)
async def complete_checklist_item(
    request: Request,
    item_id: str,
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> SuccessResponse:
    """Complete a checklist item."""
    user_id = get_user_id_from_request(request)
    org_id = get_organization_id_from_request(request)

    await service.complete_checklist_item(user_id, org_id, item_id)
    return SuccessResponse(
        message=f"Checklist item {item_id} completed",
    )


@router.post("/checklist/dismiss", response_model=SuccessResponse)
async def dismiss_checklist(
    request: Request,
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> SuccessResponse:
    """Dismiss the onboarding checklist."""
    user_id = get_user_id_from_request(request)
    org_id = get_organization_id_from_request(request)

    await service.dismiss_checklist(user_id, org_id)
    return SuccessResponse(message="Checklist dismissed")


@router.post("/video/{video_id}/progress", response_model=SuccessResponse)
async def update_video_progress(
    request: Request,
    video_id: str,
    data: VideoProgressRequest,
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> SuccessResponse:
    """Update video watch progress."""
    user_id = get_user_id_from_request(request)
    org_id = get_organization_id_from_request(request)

    await service.update_video_progress(
        user_id, org_id, video_id, data.progress, data.completed
    )
    return SuccessResponse(message=f"Video {video_id} progress updated")


@router.get("/videos", response_model=list[VideoModel])
async def get_video_catalog(
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> list[VideoModel]:
    """Get the onboarding video catalog."""
    videos = await service.get_video_catalog()
    return [VideoModel(**v) for v in videos]


@router.post("/reset", response_model=SuccessResponse)
async def reset_onboarding_state(
    request: Request,
    service: OnboardingService = Depends(get_onboarding_service),  # noqa: B008
) -> SuccessResponse:
    """Reset onboarding state (development only)."""
    user_id = get_user_id_from_request(request)
    org_id = get_organization_id_from_request(request)

    await service.reset_state(user_id, org_id)
    return SuccessResponse(message="Onboarding state reset")
