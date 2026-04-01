"""
Tests for Team API Endpoints.

Tests FastAPI endpoints for team management including:
- Listing invitations
- Creating invitations
- Revoking and resending invitations
- Token validation
- Invitation acceptance
- Team member listing
"""

import platform
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Run tests in isolated subprocesses to prevent state pollution on macOS
# pytest-forked has issues on Linux CI, so only use it on macOS
if platform.system() == "Darwin":
    pytestmark = pytest.mark.forked

# Clear any cached modules to ensure fresh router state
for mod in list(sys.modules.keys()):
    if mod.startswith("src.api.team") or mod.startswith("src.services.team"):
        del sys.modules[mod]

from src.api.team_endpoints import router
from src.services.team_invitation_service import (
    InvitationStatus,
    InviteeRole,
    TeamInvitation,
    TeamInvitationService,
    set_team_invitation_service,
)

# =============================================================================
# Test App Setup
# =============================================================================


@pytest.fixture
def sample_invitation():
    """Create a sample invitation."""
    return TeamInvitation(
        invitation_id="inv_test123",
        organization_id="org_001",
        inviter_id="user_001",
        inviter_email="inviter@example.com",
        invitee_email="invitee@example.com",
        role=InviteeRole.DEVELOPER.value,
        status=InvitationStatus.PENDING.value,
        invitation_token="test_token_abc123",
        created_at="2025-01-01T00:00:00+00:00",
        expires_at="2025-01-08T00:00:00+00:00",
    )


@pytest.fixture
def mock_service(sample_invitation):
    """Create a mock team invitation service."""
    service = MagicMock(spec=TeamInvitationService)

    service.list_invitations = AsyncMock(return_value=[sample_invitation])
    service.create_batch_invitations = AsyncMock(return_value=[sample_invitation])
    service.revoke_invitation = AsyncMock(return_value=True)
    service.resend_invitation = AsyncMock(return_value=True)
    service.validate_token = AsyncMock(
        return_value={
            "valid": True,
            "invitation_id": "inv_test123",
            "organization_id": "org_001",
            "invitee_email": "invitee@example.com",
            "role": "developer",
            "inviter_email": "inviter@example.com",
        }
    )
    service.accept_invitation = AsyncMock(
        return_value={
            "success": True,
            "organization_id": "org_001",
            "role": "developer",
        }
    )
    service.generate_shareable_link = AsyncMock(
        return_value="https://app.aenealabs.com/join/org_001/abc123"
    )

    return service


@pytest.fixture
def app(mock_service):
    """Create test FastAPI app with mocked service."""
    test_app = FastAPI()
    test_app.include_router(router)

    # Override the service dependency
    set_team_invitation_service(mock_service)

    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# =============================================================================
# List Invitations Tests
# =============================================================================


class TestListInvitations:
    """Test invitation listing endpoint."""

    def test_list_invitations(self, client, mock_service):
        """Test listing all invitations."""
        response = client.get("/api/v1/team/invitations")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["invitation_id"] == "inv_test123"
        mock_service.list_invitations.assert_called_once()

    def test_list_invitations_with_status_filter(self, client, mock_service):
        """Test listing invitations with status filter."""
        response = client.get("/api/v1/team/invitations?status=pending")

        assert response.status_code == 200
        mock_service.list_invitations.assert_called()
        call_args = mock_service.list_invitations.call_args
        assert (
            call_args.kwargs.get("status") == "pending"
            or call_args[1].get("status") == "pending"
        )

    def test_list_invitations_with_limit(self, client, mock_service):
        """Test listing invitations with limit."""
        response = client.get("/api/v1/team/invitations?limit=10")

        assert response.status_code == 200
        mock_service.list_invitations.assert_called()

    def test_list_invitations_limit_max(self, client, mock_service):
        """Test listing invitations with limit exceeding max."""
        response = client.get("/api/v1/team/invitations?limit=200")

        # Should fail validation (limit > 100)
        assert response.status_code == 422


# =============================================================================
# Create Invitations Tests
# =============================================================================


class TestCreateInvitations:
    """Test invitation creation endpoint."""

    def test_create_single_invitation(self, client, mock_service):
        """Test creating a single invitation."""
        response = client.post(
            "/api/v1/team/invitations",
            json={"invitees": [{"email": "new@example.com", "role": "developer"}]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["invitations"]) == 1
        assert "shareable_link" in data
        mock_service.create_batch_invitations.assert_called_once()

    def test_create_multiple_invitations(self, client, mock_service, sample_invitation):
        """Test creating multiple invitations."""
        # Return multiple invitations
        mock_service.create_batch_invitations.return_value = [
            sample_invitation,
            TeamInvitation(
                invitation_id="inv_test456",
                organization_id="org_001",
                inviter_id="user_001",
                inviter_email="inviter@example.com",
                invitee_email="user2@example.com",
                role="viewer",
                status="pending",
                invitation_token="token456",
                created_at="2025-01-01T00:00:00+00:00",
                expires_at="2025-01-08T00:00:00+00:00",
            ),
        ]

        response = client.post(
            "/api/v1/team/invitations",
            json={
                "invitees": [
                    {"email": "user1@example.com", "role": "developer"},
                    {"email": "user2@example.com", "role": "viewer"},
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["invitations"]) == 2

    def test_create_invitation_with_message(self, client, mock_service):
        """Test creating invitation with custom message."""
        response = client.post(
            "/api/v1/team/invitations",
            json={
                "invitees": [{"email": "new@example.com"}],
                "message": "Welcome to our team!",
            },
        )

        assert response.status_code == 200
        mock_service.create_batch_invitations.assert_called()
        call_args = mock_service.create_batch_invitations.call_args
        assert call_args.kwargs.get("message") == "Welcome to our team!"

    def test_create_invitation_empty_invitees(self, client, mock_service):
        """Test creating invitation with empty invitees list."""
        response = client.post("/api/v1/team/invitations", json={"invitees": []})

        # Should fail validation (min_length=1)
        assert response.status_code == 422

    def test_create_invitation_too_many_invitees(self, client, mock_service):
        """Test creating invitation with too many invitees."""
        invitees = [{"email": f"user{i}@example.com"} for i in range(51)]

        response = client.post("/api/v1/team/invitations", json={"invitees": invitees})

        # Should fail validation (max_length=50)
        assert response.status_code == 422

    def test_create_invitation_invalid_email(self, client, mock_service):
        """Test creating invitation with invalid email."""
        response = client.post(
            "/api/v1/team/invitations",
            json={"invitees": [{"email": "not-an-email", "role": "developer"}]},
        )

        # Should fail validation (EmailStr)
        assert response.status_code == 422

    def test_create_invitation_default_role(self, client, mock_service):
        """Test creating invitation uses default role."""
        response = client.post(
            "/api/v1/team/invitations",
            json={"invitees": [{"email": "new@example.com"}]},  # No role specified
        )

        assert response.status_code == 200


# =============================================================================
# Revoke Invitation Tests
# =============================================================================


class TestRevokeInvitation:
    """Test invitation revocation endpoint."""

    def test_revoke_invitation_success(self, client, mock_service):
        """Test successful invitation revocation."""
        response = client.delete("/api/v1/team/invitations/inv_test123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.revoke_invitation.assert_called_once()

    def test_revoke_invitation_not_found(self, client, mock_service):
        """Test revoking non-existent invitation."""
        mock_service.revoke_invitation.return_value = False

        response = client.delete("/api/v1/team/invitations/inv_nonexistent")

        assert response.status_code == 404


# =============================================================================
# Resend Invitation Tests
# =============================================================================


class TestResendInvitation:
    """Test invitation resend endpoint."""

    def test_resend_invitation_success(self, client, mock_service):
        """Test successful invitation resend."""
        response = client.post("/api/v1/team/invitations/inv_test123/resend")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_service.resend_invitation.assert_called_once()

    def test_resend_invitation_failure(self, client, mock_service):
        """Test resend failure (e.g., already accepted)."""
        mock_service.resend_invitation.return_value = False

        response = client.post("/api/v1/team/invitations/inv_accepted/resend")

        assert response.status_code == 400


# =============================================================================
# Validate Token Tests
# =============================================================================


class TestValidateToken:
    """Test token validation endpoint."""

    def test_validate_token_valid(self, client, mock_service):
        """Test validating a valid token."""
        response = client.get(
            "/api/v1/team/invitations/validate?token=test_token_abc123"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["invitation_id"] == "inv_test123"
        assert data["organization_id"] == "org_001"

    def test_validate_token_invalid(self, client, mock_service):
        """Test validating an invalid token."""
        mock_service.validate_token.return_value = {
            "valid": False,
            "error": "Invalid invitation token",
        }

        response = client.get("/api/v1/team/invitations/validate?token=invalid_token")

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "error" in data

    def test_validate_token_missing(self, client, mock_service):
        """Test validation without token parameter."""
        response = client.get("/api/v1/team/invitations/validate")

        # Should fail validation (missing required query param)
        assert response.status_code == 422


# =============================================================================
# Accept Invitation Tests
# =============================================================================


class TestAcceptInvitation:
    """Test invitation acceptance endpoint."""

    def test_accept_invitation_success(self, client, mock_service):
        """Test successful invitation acceptance."""
        response = client.post(
            "/api/v1/team/invitations/accept", json={"token": "test_token_abc123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["organization_id"] == "org_001"
        assert data["role"] == "developer"
        mock_service.accept_invitation.assert_called_once()

    def test_accept_invitation_invalid_token(self, client, mock_service):
        """Test accepting with invalid token."""
        mock_service.accept_invitation.return_value = {
            "success": False,
            "error": "Invalid invitation token",
        }

        response = client.post(
            "/api/v1/team/invitations/accept", json={"token": "invalid_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_accept_invitation_missing_token(self, client, mock_service):
        """Test accepting without token."""
        response = client.post("/api/v1/team/invitations/accept", json={})

        # Should fail validation (missing required field)
        assert response.status_code == 422


# =============================================================================
# Team Members Tests
# =============================================================================


class TestTeamMembers:
    """Test team members endpoint."""

    def test_list_team_members(self, client, mock_service):
        """Test listing team members."""
        response = client.get("/api/v1/team/members")

        assert response.status_code == 200
        data = response.json()
        # Returns mock data in the endpoint
        assert len(data) == 2
        assert data[0]["email"] == "admin@aenealabs.com"
        assert data[0]["role"] == "admin"

    def test_team_member_structure(self, client, mock_service):
        """Test team member response structure."""
        response = client.get("/api/v1/team/members")

        assert response.status_code == 200
        data = response.json()

        for member in data:
            assert "user_id" in member
            assert "email" in member
            assert "role" in member
            assert "status" in member


# =============================================================================
# Response Model Tests
# =============================================================================


class TestResponseModels:
    """Test response model validation."""

    def test_invitation_response_structure(self, client, mock_service):
        """Test invitation response has all required fields."""
        response = client.get("/api/v1/team/invitations")

        assert response.status_code == 200
        data = response.json()

        for invitation in data:
            assert "invitation_id" in invitation
            assert "invitee_email" in invitation
            assert "role" in invitation
            assert "status" in invitation

    def test_create_response_structure(self, client, mock_service):
        """Test create response has all required fields."""
        response = client.post(
            "/api/v1/team/invitations",
            json={"invitees": [{"email": "new@example.com"}]},
        )

        assert response.status_code == 200
        data = response.json()

        assert "success" in data
        assert "invitations" in data
        assert "shareable_link" in data

    def test_validate_response_structure(self, client, mock_service):
        """Test validate response has all required fields."""
        response = client.get("/api/v1/team/invitations/validate?token=test")

        assert response.status_code == 200
        data = response.json()

        assert "valid" in data
        if data["valid"]:
            assert "invitation_id" in data
            assert "organization_id" in data


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling in endpoints."""

    def test_invalid_json_body(self, client, mock_service):
        """Test handling of invalid JSON body."""
        response = client.post(
            "/api/v1/team/invitations",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_service_error_on_create(self, client, mock_service):
        """Test handling service error during creation."""
        mock_service.create_batch_invitations.side_effect = Exception("Service error")

        response = client.post(
            "/api/v1/team/invitations",
            json={"invitees": [{"email": "new@example.com"}]},
        )

        assert response.status_code == 500


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases."""

    def test_invitation_id_special_chars(self, client, mock_service):
        """Test invitation ID with special characters."""
        response = client.delete("/api/v1/team/invitations/inv_test-123_abc")

        # Should work with hyphens and underscores
        assert response.status_code in [200, 404]

    def test_long_message(self, client, mock_service):
        """Test creating invitation with very long message."""
        long_message = "x" * 1001  # Exceeds max_length=1000

        response = client.post(
            "/api/v1/team/invitations",
            json={"invitees": [{"email": "new@example.com"}], "message": long_message},
        )

        # Should fail validation
        assert response.status_code == 422

    def test_empty_token_validation(self, client, mock_service):
        """Test validating empty token."""
        response = client.get("/api/v1/team/invitations/validate?token=")

        # Empty token should still be processed
        assert response.status_code == 200
