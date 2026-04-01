"""
Tests for Team Invitation Service.

Tests DynamoDB-backed team invitation management including:
- Invitation creation
- Token generation and validation
- Invitation acceptance
- Batch invitations
- Revocation and resend
"""

import json
import platform
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

# Run tests in isolated subprocesses to prevent state pollution
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.team_invitation_service import (
    InvitationStatus,
    InviteeRole,
    TeamInvitation,
    TeamInvitationService,
    get_team_invitation_service,
    set_team_invitation_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def service():
    """Create a team invitation service for testing."""
    return TeamInvitationService(
        table_name="test-invitations",
        sns_topic_arn="arn:aws:sns:us-east-1:123456789:test-topic",
    )


@pytest.fixture
def service_no_sns():
    """Create a service without SNS configuration."""
    return TeamInvitationService(table_name="test-invitations")


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table."""
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}
    mock_table.put_item.return_value = {}
    mock_table.update_item.return_value = {}
    mock_table.delete_item.return_value = {}
    mock_table.query.return_value = {"Items": []}
    return mock_table


@pytest.fixture
def mock_sns_client():
    """Create a mock SNS client."""
    mock_sns = MagicMock()
    mock_sns.publish.return_value = {"MessageId": "test-message-id"}
    return mock_sns


@pytest.fixture
def sample_invitation():
    """Create a sample invitation for testing."""
    now = datetime.now(timezone.utc)
    return TeamInvitation(
        invitation_id="inv_test123",
        organization_id="org_001",
        inviter_id="user_001",
        inviter_email="inviter@example.com",
        invitee_email="invitee@example.com",
        role=InviteeRole.DEVELOPER.value,
        status=InvitationStatus.PENDING.value,
        invitation_token="test_token_abc123",
        created_at=now.isoformat(),
        expires_at=(now + timedelta(days=7)).isoformat(),
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestServiceInitialization:
    """Test service initialization."""

    def test_default_initialization(self):
        """Test default initialization values."""
        service = TeamInvitationService()
        assert "team-invitations" in service.table_name
        assert service._table is None
        assert service._sns is None

    def test_custom_initialization(self, service):
        """Test custom initialization."""
        assert service.table_name == "test-invitations"
        assert service.sns_topic_arn == "arn:aws:sns:us-east-1:123456789:test-topic"

    def test_singleton_pattern(self):
        """Test get/set singleton functions."""
        original = get_team_invitation_service()

        custom_service = TeamInvitationService(table_name="custom-table")
        set_team_invitation_service(custom_service)

        assert get_team_invitation_service() is custom_service

        # Reset
        set_team_invitation_service(original)


# =============================================================================
# TeamInvitation Model Tests
# =============================================================================


class TestTeamInvitationModel:
    """Test TeamInvitation dataclass."""

    def test_to_dict(self, sample_invitation):
        """Test converting invitation to dictionary."""
        data = sample_invitation.to_dict()

        assert data["invitation_id"] == "inv_test123"
        assert data["organization_id"] == "org_001"
        assert data["invitee_email"] == "invitee@example.com"
        assert data["role"] == "developer"
        assert data["status"] == "pending"
        assert "invitation_token" in data

    def test_to_dict_excludes_none(self):
        """Test that None values are excluded from dict."""
        invitation = TeamInvitation(
            invitation_id="inv_123",
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            role="developer",
            status="pending",
            invitation_token="token123",
            message=None,  # Should be excluded
            accepted_at=None,  # Should be excluded
        )

        data = invitation.to_dict()

        assert "message" not in data
        assert "accepted_at" not in data

    def test_from_dynamodb_item(self):
        """Test creating invitation from DynamoDB item."""
        item = {
            "invitation_id": "inv_456",
            "organization_id": "org_002",
            "inviter_id": "user_002",
            "inviter_email": "inviter2@example.com",
            "invitee_email": "invitee2@example.com",
            "role": "admin",
            "status": "accepted",
            "invitation_token": "token456",
            "message": "Welcome to the team!",
            "created_at": "2025-01-01T00:00:00+00:00",
            "expires_at": "2025-01-08T00:00:00+00:00",
            "accepted_at": "2025-01-02T00:00:00+00:00",
        }

        invitation = TeamInvitation.from_dynamodb_item(item)

        assert invitation.invitation_id == "inv_456"
        assert invitation.role == "admin"
        assert invitation.status == "accepted"
        assert invitation.message == "Welcome to the team!"
        assert invitation.accepted_at == "2025-01-02T00:00:00+00:00"


# =============================================================================
# Invitation Status and Role Enums
# =============================================================================


class TestEnums:
    """Test enum values."""

    def test_invitation_status_values(self):
        """Test InvitationStatus enum values."""
        assert InvitationStatus.PENDING.value == "pending"
        assert InvitationStatus.ACCEPTED.value == "accepted"
        assert InvitationStatus.EXPIRED.value == "expired"
        assert InvitationStatus.REVOKED.value == "revoked"

    def test_invitee_role_values(self):
        """Test InviteeRole enum values."""
        assert InviteeRole.ADMIN.value == "admin"
        assert InviteeRole.DEVELOPER.value == "developer"
        assert InviteeRole.VIEWER.value == "viewer"


# =============================================================================
# Token Generation Tests
# =============================================================================


class TestTokenGeneration:
    """Test token and ID generation."""

    def test_generate_token_format(self, service):
        """Test generated token format."""
        token = service._generate_token()

        assert len(token) > 30  # URL-safe base64 of 32 bytes
        assert isinstance(token, str)

    def test_generate_token_uniqueness(self, service):
        """Test tokens are unique."""
        tokens = [service._generate_token() for _ in range(100)]
        assert len(set(tokens)) == 100

    def test_generate_invitation_id_format(self, service):
        """Test generated invitation ID format."""
        inv_id = service._generate_invitation_id()

        assert inv_id.startswith("inv_")
        assert len(inv_id) > 10

    def test_generate_invitation_id_uniqueness(self, service):
        """Test invitation IDs are unique."""
        ids = [service._generate_invitation_id() for _ in range(100)]
        assert len(set(ids)) == 100


# =============================================================================
# Create Invitation Tests
# =============================================================================


class TestCreateInvitation:
    """Test invitation creation."""

    @pytest.mark.asyncio
    async def test_create_invitation_basic(self, service):
        """Test basic invitation creation."""
        invitation = await service.create_invitation(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
        )

        assert invitation.organization_id == "org_001"
        assert invitation.inviter_id == "user_001"
        assert invitation.invitee_email == "invitee@example.com"
        assert invitation.role == InviteeRole.DEVELOPER.value
        assert invitation.status == InvitationStatus.PENDING.value
        assert invitation.invitation_id.startswith("inv_")
        assert invitation.invitation_token is not None

    @pytest.mark.asyncio
    async def test_create_invitation_with_role(self, service):
        """Test invitation with custom role."""
        invitation = await service.create_invitation(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="admin@example.com",
            role=InviteeRole.ADMIN.value,
        )

        assert invitation.role == "admin"

    @pytest.mark.asyncio
    async def test_create_invitation_with_message(self, service):
        """Test invitation with personal message."""
        invitation = await service.create_invitation(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            message="Welcome to our team!",
        )

        assert invitation.message == "Welcome to our team!"

    @pytest.mark.asyncio
    async def test_create_invitation_email_lowercase(self, service):
        """Test email is lowercased."""
        invitation = await service.create_invitation(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="INVITEE@EXAMPLE.COM",
        )

        assert invitation.invitee_email == "invitee@example.com"

    @pytest.mark.asyncio
    async def test_create_invitation_expiry(self, service):
        """Test invitation has correct expiry."""
        invitation = await service.create_invitation(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
        )

        created = datetime.fromisoformat(invitation.created_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(invitation.expires_at.replace("Z", "+00:00"))

        # Default expiry is 7 days
        delta = expires - created
        assert delta.days == 7

    @pytest.mark.asyncio
    async def test_create_invitation_with_dynamodb(self, service, mock_dynamodb_table):
        """Test invitation is persisted to DynamoDB."""
        service._table = mock_dynamodb_table

        await service.create_invitation(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
        )

        mock_dynamodb_table.put_item.assert_called_once()


# =============================================================================
# Batch Invitation Tests
# =============================================================================


class TestBatchInvitations:
    """Test batch invitation creation."""

    @pytest.mark.asyncio
    async def test_create_batch_invitations(self, service):
        """Test creating multiple invitations."""
        invitees = [
            {"email": "user1@example.com", "role": "developer"},
            {"email": "user2@example.com", "role": "viewer"},
            {"email": "user3@example.com", "role": "admin"},
        ]

        invitations = await service.create_batch_invitations(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitees=invitees,
        )

        assert len(invitations) == 3
        assert invitations[0].invitee_email == "user1@example.com"
        assert invitations[0].role == "developer"
        assert invitations[1].invitee_email == "user2@example.com"
        assert invitations[1].role == "viewer"
        assert invitations[2].invitee_email == "user3@example.com"
        assert invitations[2].role == "admin"

    @pytest.mark.asyncio
    async def test_batch_invitations_with_message(self, service):
        """Test batch invitations with shared message."""
        invitees = [
            {"email": "user1@example.com"},
            {"email": "user2@example.com"},
        ]

        invitations = await service.create_batch_invitations(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitees=invitees,
            message="Join our project!",
        )

        assert all(inv.message == "Join our project!" for inv in invitations)

    @pytest.mark.asyncio
    async def test_batch_invitations_default_role(self, service):
        """Test batch invitations use default role."""
        invitees = [{"email": "user1@example.com"}]

        invitations = await service.create_batch_invitations(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitees=invitees,
        )

        assert invitations[0].role == InviteeRole.DEVELOPER.value


# =============================================================================
# Get Invitation Tests
# =============================================================================


class TestGetInvitation:
    """Test invitation retrieval."""

    @pytest.mark.asyncio
    async def test_get_invitation_not_found(self, service):
        """Test getting non-existent invitation."""
        result = await service.get_invitation("inv_nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_invitation_by_id(
        self, service, mock_dynamodb_table, sample_invitation
    ):
        """Test getting invitation by ID."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {
            "Item": sample_invitation.to_dict()
        }

        result = await service.get_invitation("inv_test123")

        assert result is not None
        assert result.invitation_id == "inv_test123"

    @pytest.mark.asyncio
    async def test_get_invitation_by_token(
        self, service, mock_dynamodb_table, sample_invitation
    ):
        """Test getting invitation by token."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_invitation.to_dict()]
        }

        result = await service.get_invitation_by_token("test_token_abc123")

        assert result is not None
        assert result.invitation_token == "test_token_abc123"

    @pytest.mark.asyncio
    async def test_get_invitation_by_token_not_found(
        self, service, mock_dynamodb_table
    ):
        """Test getting invitation by non-existent token."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {"Items": []}

        result = await service.get_invitation_by_token("invalid_token")
        assert result is None


# =============================================================================
# List Invitations Tests
# =============================================================================


class TestListInvitations:
    """Test listing invitations."""

    @pytest.mark.asyncio
    async def test_list_invitations_empty(self, service):
        """Test listing invitations when none exist."""
        invitations = await service.list_invitations("org_001")
        assert invitations == []

    @pytest.mark.asyncio
    async def test_list_invitations_by_org(
        self, service, mock_dynamodb_table, sample_invitation
    ):
        """Test listing invitations for an organization."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_invitation.to_dict()]
        }

        invitations = await service.list_invitations("org_001")

        assert len(invitations) == 1
        mock_dynamodb_table.query.assert_called()

    @pytest.mark.asyncio
    async def test_list_invitations_with_status_filter(
        self, service, mock_dynamodb_table
    ):
        """Test listing invitations with status filter."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {"Items": []}

        await service.list_invitations("org_001", status="pending")

        # Verify query was called with status filter
        mock_dynamodb_table.query.assert_called()
        call_args = mock_dynamodb_table.query.call_args
        assert ":status" in str(call_args)


# =============================================================================
# Validate Token Tests
# =============================================================================


class TestValidateToken:
    """Test token validation."""

    @pytest.mark.asyncio
    async def test_validate_token_invalid(self, service):
        """Test validating invalid token."""
        result = await service.validate_token("invalid_token")

        assert result["valid"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_validate_token_revoked(self, service, mock_dynamodb_table):
        """Test validating revoked invitation."""
        service._table = mock_dynamodb_table
        revoked_invitation = TeamInvitation(
            invitation_id="inv_revoked",
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            role="developer",
            status=InvitationStatus.REVOKED.value,
            invitation_token="revoked_token",
        )
        mock_dynamodb_table.query.return_value = {
            "Items": [revoked_invitation.to_dict()]
        }

        result = await service.validate_token("revoked_token")

        assert result["valid"] is False
        assert "revoked" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_validate_token_accepted(self, service, mock_dynamodb_table):
        """Test validating already accepted invitation."""
        service._table = mock_dynamodb_table
        accepted_invitation = TeamInvitation(
            invitation_id="inv_accepted",
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            role="developer",
            status=InvitationStatus.ACCEPTED.value,
            invitation_token="accepted_token",
        )
        mock_dynamodb_table.query.return_value = {
            "Items": [accepted_invitation.to_dict()]
        }

        result = await service.validate_token("accepted_token")

        assert result["valid"] is False
        assert "accepted" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_validate_token_expired(self, service, mock_dynamodb_table):
        """Test validating expired invitation."""
        service._table = mock_dynamodb_table
        expired_invitation = TeamInvitation(
            invitation_id="inv_expired",
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            role="developer",
            status=InvitationStatus.PENDING.value,
            invitation_token="expired_token",
            expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        )
        mock_dynamodb_table.query.return_value = {
            "Items": [expired_invitation.to_dict()]
        }

        result = await service.validate_token("expired_token")

        assert result["valid"] is False
        assert "expired" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_validate_token_valid(
        self, service, mock_dynamodb_table, sample_invitation
    ):
        """Test validating valid token."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_invitation.to_dict()]
        }

        result = await service.validate_token("test_token_abc123")

        assert result["valid"] is True
        assert result["invitation_id"] == "inv_test123"
        assert result["organization_id"] == "org_001"
        assert result["invitee_email"] == "invitee@example.com"


# =============================================================================
# Accept Invitation Tests
# =============================================================================


class TestAcceptInvitation:
    """Test invitation acceptance."""

    @pytest.mark.asyncio
    async def test_accept_invitation_invalid_token(self, service):
        """Test accepting with invalid token."""
        result = await service.accept_invitation("invalid_token", "user_new")

        assert result.get("valid") is False or result.get("success") is False

    @pytest.mark.asyncio
    async def test_accept_invitation_success(
        self, service, mock_dynamodb_table, sample_invitation
    ):
        """Test successful invitation acceptance."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_invitation.to_dict()]
        }

        result = await service.accept_invitation("test_token_abc123", "user_new")

        assert result["success"] is True
        assert result["organization_id"] == "org_001"
        assert result["role"] == "developer"
        mock_dynamodb_table.update_item.assert_called()


# =============================================================================
# Revoke Invitation Tests
# =============================================================================


class TestRevokeInvitation:
    """Test invitation revocation."""

    @pytest.mark.asyncio
    async def test_revoke_invitation_no_table(self, service):
        """Test revoke when table not available."""
        result = await service.revoke_invitation("inv_123", "user_001")
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_invitation_success(self, service, mock_dynamodb_table):
        """Test successful revocation."""
        service._table = mock_dynamodb_table

        result = await service.revoke_invitation("inv_123", "user_001")

        assert result is True
        mock_dynamodb_table.update_item.assert_called()


# =============================================================================
# Resend Invitation Tests
# =============================================================================


class TestResendInvitation:
    """Test invitation resend."""

    @pytest.mark.asyncio
    async def test_resend_invitation_not_found(self, service):
        """Test resend when invitation not found."""
        result = await service.resend_invitation("inv_nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_resend_invitation_not_pending(self, service, mock_dynamodb_table):
        """Test resend when invitation is not pending."""
        service._table = mock_dynamodb_table
        accepted_invitation = TeamInvitation(
            invitation_id="inv_accepted",
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            role="developer",
            status=InvitationStatus.ACCEPTED.value,
            invitation_token="token",
        )
        mock_dynamodb_table.get_item.return_value = {
            "Item": accepted_invitation.to_dict()
        }

        result = await service.resend_invitation("inv_accepted")

        assert result is False

    @pytest.mark.asyncio
    async def test_resend_invitation_success(
        self, service, mock_dynamodb_table, sample_invitation
    ):
        """Test successful resend."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {
            "Item": sample_invitation.to_dict()
        }

        result = await service.resend_invitation("inv_test123")

        assert result is True
        mock_dynamodb_table.update_item.assert_called()


# =============================================================================
# Shareable Link Tests
# =============================================================================


class TestShareableLink:
    """Test shareable link generation."""

    @pytest.mark.asyncio
    async def test_generate_shareable_link_default_base(self, service):
        """Test shareable link with default base URL."""
        link = await service.generate_shareable_link("org_001")

        assert "https://app.aenealabs.com/join/org_001/" in link
        # Should contain a token
        assert len(link.split("/")[-1]) > 10

    @pytest.mark.asyncio
    async def test_generate_shareable_link_custom_base(self, service):
        """Test shareable link with custom base URL."""
        link = await service.generate_shareable_link(
            "org_001", base_url="https://custom.example.com"
        )

        assert link.startswith("https://custom.example.com/join/org_001/")


# =============================================================================
# SNS Email Tests
# =============================================================================


class TestSNSEmail:
    """Test SNS email integration."""

    @pytest.mark.asyncio
    async def test_send_email_no_sns(self, service_no_sns, sample_invitation):
        """Test email send when SNS not configured."""
        # Should not raise an exception
        await service_no_sns._send_invitation_email(sample_invitation)

    @pytest.mark.asyncio
    async def test_send_email_success(
        self, service, mock_sns_client, sample_invitation
    ):
        """Test successful email send via SNS."""
        service._sns = mock_sns_client

        await service._send_invitation_email(sample_invitation)

        mock_sns_client.publish.assert_called_once()
        call_args = mock_sns_client.publish.call_args
        message = json.loads(
            call_args.kwargs.get("Message") or call_args[1].get("Message")
        )

        assert message["type"] == "team_invitation"
        assert message["invitee_email"] == "invitee@example.com"


# =============================================================================
# DynamoDB Connection Tests
# =============================================================================


class TestDynamoDBConnection:
    """Test DynamoDB connection handling."""

    def test_lazy_table_initialization(self, service):
        """Test table is lazily initialized."""
        assert service._table is None

    def test_table_initialization_success(self, service):
        """Test successful table initialization with mocked boto3."""
        import sys

        # Create mock boto3 module
        mock_boto3 = MagicMock()
        mock_resource = MagicMock()
        mock_table = MagicMock()
        mock_resource.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_resource

        # Inject mock into sys.modules before accessing property
        with patch.dict(sys.modules, {"boto3": mock_boto3}):
            # Reset service state to trigger re-initialization
            service._table = None
            service._dynamodb = None

            table = service.table

            assert table is mock_table
            mock_boto3.resource.assert_called_once_with("dynamodb")

    def test_sns_initialization_success(self, service):
        """Test successful SNS client initialization with mocked boto3."""
        import sys

        # Create mock boto3 module
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        # Inject mock into sys.modules before accessing property
        with patch.dict(sys.modules, {"boto3": mock_boto3}):
            # Reset service state
            service._sns = None

            sns = service.sns

            assert sns is mock_client
            mock_boto3.client.assert_called_with("sns")


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handle_dynamodb_error_on_create(self, service, mock_dynamodb_table):
        """Test handling DynamoDB error during creation."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.put_item.side_effect = Exception("DynamoDB error")

        with pytest.raises(Exception):
            await service.create_invitation(
                organization_id="org_001",
                inviter_id="user_001",
                inviter_email="inviter@example.com",
                invitee_email="invitee@example.com",
            )

    @pytest.mark.asyncio
    async def test_handle_dynamodb_error_on_get(self, service, mock_dynamodb_table):
        """Test handling DynamoDB error during get."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.side_effect = Exception("DynamoDB error")

        result = await service.get_invitation("inv_123")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_organization_id(self, service):
        """Test with empty organization ID."""
        invitation = await service.create_invitation(
            organization_id="",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
        )

        assert invitation.organization_id == ""

    @pytest.mark.asyncio
    async def test_special_characters_in_email(self, service):
        """Test with special characters in email."""
        invitation = await service.create_invitation(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter+tag@example.com",
            invitee_email="invitee+special@example.com",
        )

        assert invitation.invitee_email == "invitee+special@example.com"


# =============================================================================
# Token Replay Attack Tests - Security Critical
# =============================================================================


class TestTokenReplayAttacks:
    """Test token replay attack prevention."""

    @pytest.mark.asyncio
    async def test_token_replay_after_acceptance(
        self, service, mock_dynamodb_table, sample_invitation
    ):
        """Test that token cannot be reused after acceptance."""
        service._table = mock_dynamodb_table

        # First attempt - pending invitation
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_invitation.to_dict()]
        }

        result1 = await service.accept_invitation("test_token_abc123", "user_new")
        assert result1["success"] is True

        # Now simulate the invitation being accepted
        accepted_invitation = TeamInvitation(
            invitation_id="inv_test123",
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            role=InviteeRole.DEVELOPER.value,
            status=InvitationStatus.ACCEPTED.value,
            invitation_token="test_token_abc123",
        )
        mock_dynamodb_table.query.return_value = {
            "Items": [accepted_invitation.to_dict()]
        }

        # Second attempt - should fail
        result2 = await service.accept_invitation("test_token_abc123", "user_attacker")
        assert result2["valid"] is False
        assert "accepted" in result2["error"].lower()

    @pytest.mark.asyncio
    async def test_token_cannot_be_used_by_different_user(
        self, service, mock_dynamodb_table
    ):
        """Test that accepted token cannot be reused by different user."""
        service._table = mock_dynamodb_table

        accepted_invitation = TeamInvitation(
            invitation_id="inv_test123",
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            role="developer",
            status=InvitationStatus.ACCEPTED.value,
            invitation_token="already_used_token",
        )
        mock_dynamodb_table.query.return_value = {
            "Items": [accepted_invitation.to_dict()]
        }

        result = await service.accept_invitation("already_used_token", "malicious_user")
        assert result["valid"] is False


# =============================================================================
# Expired Invitation Tests
# =============================================================================


class TestExpiredInvitationAcceptance:
    """Test expired invitation handling."""

    @pytest.mark.asyncio
    async def test_accept_expired_invitation_fails(self, service, mock_dynamodb_table):
        """Test that expired invitations cannot be accepted."""
        service._table = mock_dynamodb_table

        expired_invitation = TeamInvitation(
            invitation_id="inv_expired",
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            role="developer",
            status=InvitationStatus.PENDING.value,
            invitation_token="expired_token",
            expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        )
        mock_dynamodb_table.query.return_value = {
            "Items": [expired_invitation.to_dict()]
        }

        result = await service.accept_invitation("expired_token", "user_new")
        assert result["valid"] is False
        assert "expired" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_just_expired_invitation(self, service, mock_dynamodb_table):
        """Test invitation that just expired (edge case)."""
        service._table = mock_dynamodb_table

        # Expired 1 second ago
        just_expired = TeamInvitation(
            invitation_id="inv_just_expired",
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            role="developer",
            status=InvitationStatus.PENDING.value,
            invitation_token="just_expired_token",
            expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        )
        mock_dynamodb_table.query.return_value = {"Items": [just_expired.to_dict()]}

        result = await service.validate_token("just_expired_token")
        assert result["valid"] is False


# =============================================================================
# Email Case Sensitivity Tests
# =============================================================================


class TestEmailCaseSensitivity:
    """Test email case handling."""

    @pytest.mark.asyncio
    async def test_email_normalized_on_creation(self, service):
        """Test that email addresses are normalized to lowercase."""
        invitation = await service.create_invitation(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="Inviter@Example.COM",
            invitee_email="INVITEE@EXAMPLE.COM",
        )

        assert invitation.invitee_email == "invitee@example.com"

    @pytest.mark.asyncio
    async def test_mixed_case_email_stored_lowercase(self, service):
        """Test that mixed case emails are stored in lowercase."""
        invitation = await service.create_invitation(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="UsEr@ExAmPlE.cOm",
        )

        assert invitation.invitee_email == "user@example.com"

    @pytest.mark.asyncio
    async def test_email_with_plus_addressing(self, service):
        """Test email with plus addressing."""
        invitation = await service.create_invitation(
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="USER+TAG@EXAMPLE.COM",
        )

        assert invitation.invitee_email == "user+tag@example.com"


# =============================================================================
# Concurrent Acceptance Race Condition Tests
# =============================================================================


class TestConcurrentAcceptance:
    """Test concurrent invitation acceptance scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_acceptance_second_fails(
        self, service, mock_dynamodb_table, sample_invitation
    ):
        """Test that concurrent acceptance properly handles race conditions."""
        service._table = mock_dynamodb_table

        # First call returns pending invitation
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_invitation.to_dict()]
        }

        # First acceptance succeeds
        result1 = await service.accept_invitation("test_token_abc123", "user1")
        assert result1["success"] is True

        # Simulate that another concurrent request accepted it
        accepted_invitation = TeamInvitation(
            invitation_id=sample_invitation.invitation_id,
            organization_id=sample_invitation.organization_id,
            inviter_id=sample_invitation.inviter_id,
            inviter_email=sample_invitation.inviter_email,
            invitee_email=sample_invitation.invitee_email,
            role=sample_invitation.role,
            status=InvitationStatus.ACCEPTED.value,
            invitation_token=sample_invitation.invitation_token,
        )
        mock_dynamodb_table.query.return_value = {
            "Items": [accepted_invitation.to_dict()]
        }

        # Second attempt should fail
        result2 = await service.accept_invitation("test_token_abc123", "user2")
        assert result2["valid"] is False


# =============================================================================
# Revocation Tests - Already Accepted
# =============================================================================


class TestRevocationOfAcceptedInvitations:
    """Test revocation of already-accepted invitations."""

    @pytest.mark.asyncio
    async def test_revoke_returns_true_for_any_status(
        self, service, mock_dynamodb_table
    ):
        """Test that revoke always succeeds with valid table."""
        service._table = mock_dynamodb_table

        # Revoke returns True if update succeeds
        result = await service.revoke_invitation("inv_123", "admin_001")
        assert result is True
        mock_dynamodb_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_fails_on_dynamodb_error(self, service, mock_dynamodb_table):
        """Test revoke failure on DynamoDB error."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.update_item.side_effect = Exception("DynamoDB error")

        result = await service.revoke_invitation("inv_123", "admin_001")
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_pending_invitation(self, service, mock_dynamodb_table):
        """Test revoking a pending invitation."""
        service._table = mock_dynamodb_table

        result = await service.revoke_invitation("inv_pending", "admin_001")
        assert result is True

        call_args = mock_dynamodb_table.update_item.call_args
        assert InvitationStatus.REVOKED.value in str(call_args)


# =============================================================================
# DynamoDB Error Handling Tests
# =============================================================================


class TestDynamoDBErrorHandling:
    """Test DynamoDB error handling."""

    @pytest.mark.asyncio
    async def test_get_invitation_query_error(self, service, mock_dynamodb_table):
        """Test handling query error on get_invitation_by_token."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.side_effect = Exception("Query failed")

        result = await service.get_invitation_by_token("some_token")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_invitations_error(self, service, mock_dynamodb_table):
        """Test handling error when listing invitations."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.side_effect = Exception("List failed")

        result = await service.list_invitations("org_001")
        assert result == []

    @pytest.mark.asyncio
    async def test_accept_invitation_update_error(
        self, service, mock_dynamodb_table, sample_invitation
    ):
        """Test handling update error during acceptance."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_invitation.to_dict()]
        }
        mock_dynamodb_table.update_item.side_effect = Exception("Update failed")

        result = await service.accept_invitation("test_token_abc123", "user_new")
        assert result["success"] is False
        assert "Update failed" in result["error"]


# =============================================================================
# SNS Error Handling Tests
# =============================================================================


class TestSNSErrorHandling:
    """Test SNS error handling."""

    @pytest.mark.asyncio
    async def test_sns_publish_error_logged_not_raised(
        self, service, mock_sns_client, sample_invitation
    ):
        """Test that SNS errors are logged but not raised."""
        service._sns = mock_sns_client
        mock_sns_client.publish.side_effect = Exception("SNS publish failed")

        # Should not raise exception
        await service._send_invitation_email(sample_invitation)

    @pytest.mark.asyncio
    async def test_send_email_no_topic_arn(self, sample_invitation):
        """Test email send when no topic ARN configured."""
        service = TeamInvitationService(
            table_name="test",
            sns_topic_arn="",  # Empty topic ARN
        )

        # Should not raise exception
        await service._send_invitation_email(sample_invitation)


# =============================================================================
# TeamInvitation Model Edge Cases
# =============================================================================


class TestFromDynamoDBItemEdgeCases:
    """Test TeamInvitation.from_dynamodb_item edge cases."""

    def test_from_dynamodb_item_missing_optional_fields(self):
        """Test creating invitation from item with missing optional fields."""
        item = {
            "invitation_id": "inv_123",
            "organization_id": "org_001",
            "inviter_id": "user_001",
            "inviter_email": "inviter@example.com",
            "invitee_email": "invitee@example.com",
            "invitation_token": "token123",
        }

        invitation = TeamInvitation.from_dynamodb_item(item)

        assert invitation.invitation_id == "inv_123"
        assert invitation.role == InviteeRole.DEVELOPER.value  # Default
        assert invitation.status == InvitationStatus.PENDING.value  # Default
        assert invitation.message is None
        assert invitation.ttl is None

    def test_from_dynamodb_item_empty_dict(self):
        """Test creating invitation from empty item."""
        item = {}

        invitation = TeamInvitation.from_dynamodb_item(item)

        assert invitation.invitation_id == ""
        assert invitation.organization_id == ""
        assert invitation.role == InviteeRole.DEVELOPER.value

    def test_from_dynamodb_item_with_all_fields(self):
        """Test creating invitation with all fields present."""
        now = datetime.now(timezone.utc)
        item = {
            "invitation_id": "inv_full",
            "organization_id": "org_001",
            "inviter_id": "user_001",
            "inviter_email": "inviter@example.com",
            "invitee_email": "invitee@example.com",
            "role": "admin",
            "status": "accepted",
            "invitation_token": "token_full",
            "message": "Welcome!",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
            "accepted_at": now.isoformat(),
            "revoked_at": None,
            "ttl": int(now.timestamp()),
        }

        invitation = TeamInvitation.from_dynamodb_item(item)

        assert invitation.invitation_id == "inv_full"
        assert invitation.role == "admin"
        assert invitation.status == "accepted"
        assert invitation.message == "Welcome!"
        assert invitation.ttl == int(now.timestamp())


# =============================================================================
# Resend Invitation Error Handling
# =============================================================================


class TestResendInvitationErrors:
    """Test resend invitation error scenarios."""

    @pytest.mark.asyncio
    async def test_resend_invitation_update_fails(
        self, service, mock_dynamodb_table, sample_invitation
    ):
        """Test resend when update fails."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {
            "Item": sample_invitation.to_dict()
        }
        mock_dynamodb_table.update_item.side_effect = Exception("Update failed")

        result = await service.resend_invitation("inv_test123")
        assert result is False

    @pytest.mark.asyncio
    async def test_resend_revoked_invitation_fails(self, service, mock_dynamodb_table):
        """Test that revoked invitations cannot be resent."""
        service._table = mock_dynamodb_table

        revoked_invitation = TeamInvitation(
            invitation_id="inv_revoked",
            organization_id="org_001",
            inviter_id="user_001",
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            role="developer",
            status=InvitationStatus.REVOKED.value,
            invitation_token="revoked_token",
        )
        mock_dynamodb_table.get_item.return_value = {
            "Item": revoked_invitation.to_dict()
        }

        result = await service.resend_invitation("inv_revoked")
        assert result is False


# =============================================================================
# List Invitations Edge Cases
# =============================================================================


class TestListInvitationsEdgeCases:
    """Test list invitations edge cases."""

    @pytest.mark.asyncio
    async def test_list_invitations_with_limit(self, service, mock_dynamodb_table):
        """Test list invitations respects limit parameter."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {"Items": []}

        await service.list_invitations("org_001", limit=10)

        call_args = mock_dynamodb_table.query.call_args
        assert call_args.kwargs.get("Limit") == 10

    @pytest.mark.asyncio
    async def test_list_invitations_no_status_filter(
        self, service, mock_dynamodb_table
    ):
        """Test list invitations without status filter."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {"Items": []}

        await service.list_invitations("org_001")

        mock_dynamodb_table.query.assert_called_once()


# =============================================================================
# Shareable Link Edge Cases
# =============================================================================


class TestShareableLinkEdgeCases:
    """Test shareable link edge cases."""

    @pytest.mark.asyncio
    async def test_generate_shareable_link_unique_tokens(self, service):
        """Test that each shareable link has a unique token."""
        links = [await service.generate_shareable_link("org_001") for _ in range(10)]

        # Extract tokens
        tokens = [link.split("/")[-1] for link in links]

        # All tokens should be unique
        assert len(set(tokens)) == 10

    @pytest.mark.asyncio
    async def test_generate_shareable_link_format(self, service):
        """Test shareable link format."""
        link = await service.generate_shareable_link("org_test")

        assert link.startswith("https://app.aenealabs.com/join/org_test/")
        parts = link.split("/")
        assert len(parts[-1]) > 10  # Token has sufficient length
