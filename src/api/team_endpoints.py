"""
Project Aura - Team API Endpoints

REST API endpoints for team member management and invitations.

Endpoints:
- GET   /api/v1/team/invitations          - List org invitations
- POST  /api/v1/team/invitations          - Send invitation(s)
- DELETE /api/v1/team/invitations/{id}    - Revoke invitation
- POST  /api/v1/team/invitations/{id}/resend - Resend email
- GET   /api/v1/team/invitations/validate  - Validate token
- POST  /api/v1/team/invitations/accept    - Accept invitation
- GET   /api/v1/team/members               - List team members
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from src.services.team_invitation_service import (
    InviteeRole,
    TeamInvitationService,
    get_team_invitation_service,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/team", tags=["Team"])

# ============================================================================
# Pydantic Models
# ============================================================================


class InviteeModel(BaseModel):
    """Single invitee data."""

    email: EmailStr
    role: str = Field(default=InviteeRole.DEVELOPER.value)


class CreateInvitationsRequest(BaseModel):
    """Request to create invitations."""

    invitees: list[InviteeModel] = Field(min_length=1, max_length=50)
    message: Optional[str] = Field(default=None, max_length=1000)


class InvitationResponse(BaseModel):
    """Invitation response model."""

    invitation_id: str
    invitee_email: str
    role: str
    status: str
    created_at: Optional[str] = None
    expires_at: Optional[str] = None


class CreateInvitationsResponse(BaseModel):
    """Response for batch invitation creation."""

    success: bool
    invitations: list[InvitationResponse]
    shareable_link: Optional[str] = None


class ValidateTokenResponse(BaseModel):
    """Token validation response."""

    valid: bool
    error: Optional[str] = None
    invitation_id: Optional[str] = None
    organization_id: Optional[str] = None
    invitee_email: Optional[str] = None
    role: Optional[str] = None
    inviter_email: Optional[str] = None


class AcceptInvitationRequest(BaseModel):
    """Request to accept an invitation."""

    token: str


class AcceptInvitationResponse(BaseModel):
    """Response for accepting an invitation."""

    success: bool
    error: Optional[str] = None
    organization_id: Optional[str] = None
    role: Optional[str] = None


class TeamMemberModel(BaseModel):
    """Team member data."""

    user_id: str
    email: str
    name: Optional[str] = None
    role: str
    status: str
    joined_at: Optional[str] = None
    last_active: Optional[str] = None


class SuccessResponse(BaseModel):
    """Generic success response."""

    success: bool
    message: Optional[str] = None


# ============================================================================
# Helper Functions
# ============================================================================


def get_user_id_from_request(request: Request) -> str:
    """Extract user ID from request context."""
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "sub"):
        return user.sub
    return "dev-user-001"


def get_user_email_from_request(request: Request) -> str:
    """Extract user email from request context."""
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "email"):
        return user.email
    return "dev@aenealabs.com"


def get_organization_id_from_request(request: Request) -> str:
    """Extract organization ID from request context."""
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "organization_id"):
        return user.organization_id
    return "dev-org-001"


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    request: Request,
    status: Optional[str] = Query(default=None),  # noqa: B008,
    limit: int = Query(default=50, le=100),  # noqa: B008
    service: TeamInvitationService = Depends(get_team_invitation_service),  # noqa: B008
) -> list[InvitationResponse]:
    """List invitations for the organization."""
    org_id = get_organization_id_from_request(request)

    invitations = await service.list_invitations(
        organization_id=org_id,
        status=status,
        limit=limit,
    )

    return [
        InvitationResponse(
            invitation_id=inv.invitation_id,
            invitee_email=inv.invitee_email,
            role=inv.role,
            status=inv.status,
            created_at=inv.created_at,
            expires_at=inv.expires_at,
        )
        for inv in invitations
    ]


@router.post("/invitations", response_model=CreateInvitationsResponse)
async def create_invitations(
    request: Request,
    data: CreateInvitationsRequest,
    service: TeamInvitationService = Depends(get_team_invitation_service),  # noqa: B008
) -> CreateInvitationsResponse:
    """Create team invitations."""
    user_id = get_user_id_from_request(request)
    user_email = get_user_email_from_request(request)
    org_id = get_organization_id_from_request(request)

    invitees = [{"email": inv.email, "role": inv.role} for inv in data.invitees]

    try:
        invitations = await service.create_batch_invitations(
            organization_id=org_id,
            inviter_id=user_id,
            inviter_email=user_email,
            invitees=invitees,
            message=data.message,
        )

        # Generate shareable link
        shareable_link = await service.generate_shareable_link(org_id)

        return CreateInvitationsResponse(
            success=True,
            invitations=[
                InvitationResponse(
                    invitation_id=inv.invitation_id,
                    invitee_email=inv.invitee_email,
                    role=inv.role,
                    status=inv.status,
                    created_at=inv.created_at,
                    expires_at=inv.expires_at,
                )
                for inv in invitations
            ],
            shareable_link=shareable_link,
        )
    except Exception as e:
        logger.error(f"Failed to create invitations: {e}")
        raise HTTPException(status_code=500, detail="Failed to create invitations")


@router.delete("/invitations/{invitation_id}", response_model=SuccessResponse)
async def revoke_invitation(
    request: Request,
    invitation_id: str,
    service: TeamInvitationService = Depends(get_team_invitation_service),  # noqa: B008
) -> SuccessResponse:
    """Revoke an invitation."""
    user_id = get_user_id_from_request(request)

    success = await service.revoke_invitation(invitation_id, user_id)

    if not success:
        raise HTTPException(status_code=404, detail="Invitation not found")

    return SuccessResponse(success=True, message="Invitation revoked")


@router.post("/invitations/{invitation_id}/resend", response_model=SuccessResponse)
async def resend_invitation(
    request: Request,
    invitation_id: str,
    service: TeamInvitationService = Depends(get_team_invitation_service),  # noqa: B008
) -> SuccessResponse:
    """Resend an invitation email."""
    success = await service.resend_invitation(invitation_id)

    if not success:
        raise HTTPException(status_code=400, detail="Unable to resend invitation")

    return SuccessResponse(success=True, message="Invitation resent")


@router.get("/invitations/validate", response_model=ValidateTokenResponse)
async def validate_invitation_token(
    token: str = Query(...),  # noqa: B008
    service: TeamInvitationService = Depends(get_team_invitation_service),  # noqa: B008
) -> ValidateTokenResponse:
    """Validate an invitation token."""
    result = await service.validate_token(token)
    return ValidateTokenResponse(**result)


@router.post("/invitations/accept", response_model=AcceptInvitationResponse)
async def accept_invitation(
    request: Request,
    data: AcceptInvitationRequest,
    service: TeamInvitationService = Depends(get_team_invitation_service),  # noqa: B008
) -> AcceptInvitationResponse:
    """Accept an invitation."""
    user_id = get_user_id_from_request(request)

    result = await service.accept_invitation(data.token, user_id)
    return AcceptInvitationResponse(**result)


@router.get("/members", response_model=list[TeamMemberModel])
async def list_team_members(
    request: Request,
) -> list[TeamMemberModel]:
    """List team members for the organization.

    Note: In production, this would query Cognito or a users table.
    """
    get_organization_id_from_request(request)  # For future org filtering

    # Mock data for development
    return [
        TeamMemberModel(
            user_id="usr_001",
            email="admin@aenealabs.com",
            name="Admin User",
            role="admin",
            status="active",
            joined_at="2024-01-15T10:00:00Z",
            last_active="2025-01-01T14:30:00Z",
        ),
        TeamMemberModel(
            user_id="usr_002",
            email="developer@aenealabs.com",
            name="Dev User",
            role="developer",
            status="active",
            joined_at="2024-06-01T09:00:00Z",
            last_active="2025-01-01T11:00:00Z",
        ),
    ]
