"""
Project Aura - Team Invitation Service

Service for managing team member invitations.
Handles invitation creation, validation, and acceptance.
"""

import logging
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class InvitationStatus(str, Enum):
    """Invitation status states."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class InviteeRole(str, Enum):
    """Available roles for invitees."""

    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


@dataclass
class TeamInvitation:
    """Team invitation data model."""

    invitation_id: str
    organization_id: str
    inviter_id: str
    inviter_email: str
    invitee_email: str
    role: str
    status: str
    invitation_token: str
    message: Optional[str] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    accepted_at: Optional[str] = None
    revoked_at: Optional[str] = None
    ttl: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "TeamInvitation":
        """Create from DynamoDB item."""
        return cls(
            invitation_id=item.get("invitation_id", ""),
            organization_id=item.get("organization_id", ""),
            inviter_id=item.get("inviter_id", ""),
            inviter_email=item.get("inviter_email", ""),
            invitee_email=item.get("invitee_email", ""),
            role=item.get("role", InviteeRole.DEVELOPER.value),
            status=item.get("status", InvitationStatus.PENDING.value),
            invitation_token=item.get("invitation_token", ""),
            message=item.get("message"),
            created_at=item.get("created_at"),
            expires_at=item.get("expires_at"),
            accepted_at=item.get("accepted_at"),
            revoked_at=item.get("revoked_at"),
            ttl=item.get("ttl"),
        )


class TeamInvitationService:
    """Service for managing team invitations."""

    # Invitation expires after 7 days by default
    DEFAULT_EXPIRY_DAYS = 7

    # TTL for DynamoDB (30 days after creation)
    TTL_DAYS = 30

    def __init__(
        self,
        table_name: Optional[str] = None,
        sns_topic_arn: Optional[str] = None,
    ):
        """Initialize the team invitation service.

        Args:
            table_name: DynamoDB table name for invitations.
            sns_topic_arn: SNS topic ARN for sending invitation emails.
        """
        self.table_name = table_name or os.environ.get(
            "INVITATIONS_TABLE_NAME", "aura-team-invitations-dev"
        )
        self.sns_topic_arn = sns_topic_arn or os.environ.get(
            "INVITATIONS_TOPIC_ARN", ""
        )
        self._table = None
        self._sns = None
        self._dynamodb = None

    @property
    def table(self) -> Any:
        """Lazy-load DynamoDB table resource."""
        if self._table is None:
            try:
                import boto3

                self._dynamodb = boto3.resource("dynamodb")
                self._table = self._dynamodb.Table(self.table_name)
            except Exception as e:
                logger.warning(f"Failed to connect to DynamoDB: {e}")
                self._table = None
        return self._table

    @property
    def sns(self) -> Any:
        """Lazy-load SNS client."""
        if self._sns is None:
            try:
                import boto3

                self._sns = boto3.client("sns")
            except Exception as e:
                logger.warning(f"Failed to connect to SNS: {e}")
                self._sns = None
        return self._sns

    def _generate_token(self) -> str:
        """Generate a secure invitation token."""
        return secrets.token_urlsafe(32)

    def _generate_invitation_id(self) -> str:
        """Generate a unique invitation ID."""
        return f"inv_{secrets.token_hex(16)}"

    async def create_invitation(
        self,
        organization_id: str,
        inviter_id: str,
        inviter_email: str,
        invitee_email: str,
        role: str = InviteeRole.DEVELOPER.value,
        message: Optional[str] = None,
    ) -> TeamInvitation:
        """Create a new team invitation.

        Args:
            organization_id: The organization ID.
            inviter_id: The inviting user's ID.
            inviter_email: The inviting user's email.
            invitee_email: The invitee's email.
            role: The role to assign.
            message: Optional personal message.

        Returns:
            The created invitation.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=self.DEFAULT_EXPIRY_DAYS)
        ttl_timestamp = int((now + timedelta(days=self.TTL_DAYS)).timestamp())

        invitation = TeamInvitation(
            invitation_id=self._generate_invitation_id(),
            organization_id=organization_id,
            inviter_id=inviter_id,
            inviter_email=inviter_email,
            invitee_email=invitee_email.lower(),
            role=role,
            status=InvitationStatus.PENDING.value,
            invitation_token=self._generate_token(),
            message=message,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            ttl=ttl_timestamp,
        )

        if self.table is not None:
            try:
                self.table.put_item(Item=invitation.to_dict())
            except Exception as e:
                logger.error(f"Failed to create invitation: {e}")
                raise

        return invitation

    async def create_batch_invitations(
        self,
        organization_id: str,
        inviter_id: str,
        inviter_email: str,
        invitees: list[dict[str, str]],
        message: Optional[str] = None,
    ) -> list[TeamInvitation]:
        """Create multiple team invitations.

        Args:
            organization_id: The organization ID.
            inviter_id: The inviting user's ID.
            inviter_email: The inviting user's email.
            invitees: List of dicts with 'email' and 'role' keys.
            message: Optional personal message for all invites.

        Returns:
            List of created invitations.
        """
        invitations = []

        for invitee in invitees:
            invitation = await self.create_invitation(
                organization_id=organization_id,
                inviter_id=inviter_id,
                inviter_email=inviter_email,
                invitee_email=invitee["email"],
                role=invitee.get("role", InviteeRole.DEVELOPER.value),
                message=message,
            )
            invitations.append(invitation)

        return invitations

    async def get_invitation(self, invitation_id: str) -> Optional[TeamInvitation]:
        """Get an invitation by ID.

        Args:
            invitation_id: The invitation ID.

        Returns:
            The invitation or None if not found.
        """
        if self.table is None:
            return None

        try:
            response = self.table.get_item(Key={"invitation_id": invitation_id})
            item = response.get("Item")
            return TeamInvitation.from_dynamodb_item(item) if item else None
        except Exception as e:
            logger.error(f"Failed to get invitation: {e}")
            return None

    async def get_invitation_by_token(self, token: str) -> Optional[TeamInvitation]:
        """Get an invitation by token.

        Args:
            token: The invitation token.

        Returns:
            The invitation or None if not found.
        """
        if self.table is None:
            return None

        try:
            response = self.table.query(
                IndexName="token-index",
                KeyConditionExpression="invitation_token = :token",
                ExpressionAttributeValues={":token": token},
            )
            items = response.get("Items", [])
            return TeamInvitation.from_dynamodb_item(items[0]) if items else None
        except Exception as e:
            logger.error(f"Failed to get invitation by token: {e}")
            return None

    async def list_invitations(
        self,
        organization_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[TeamInvitation]:
        """List invitations for an organization.

        Args:
            organization_id: The organization ID.
            status: Optional status filter.
            limit: Maximum number of results.

        Returns:
            List of invitations.
        """
        if self.table is None:
            return []

        try:
            if status:
                response = self.table.query(
                    IndexName="organization-status-index",
                    KeyConditionExpression="organization_id = :org AND #status = :status",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":org": organization_id,
                        ":status": status,
                    },
                    Limit=limit,
                )
            else:
                response = self.table.query(
                    IndexName="organization-status-index",
                    KeyConditionExpression="organization_id = :org",
                    ExpressionAttributeValues={":org": organization_id},
                    Limit=limit,
                )

            return [
                TeamInvitation.from_dynamodb_item(item)
                for item in response.get("Items", [])
            ]
        except Exception as e:
            logger.error(f"Failed to list invitations: {e}")
            return []

    async def validate_token(self, token: str) -> dict[str, Any]:
        """Validate an invitation token.

        Args:
            token: The invitation token.

        Returns:
            Validation result with invitation details.
        """
        invitation = await self.get_invitation_by_token(token)

        if not invitation:
            return {"valid": False, "error": "Invalid invitation token"}

        if invitation.status == InvitationStatus.REVOKED.value:
            return {"valid": False, "error": "Invitation has been revoked"}

        if invitation.status == InvitationStatus.ACCEPTED.value:
            return {"valid": False, "error": "Invitation already accepted"}

        # Check expiration
        if invitation.expires_at:
            expires = datetime.fromisoformat(
                invitation.expires_at.replace("Z", "+00:00")
            )
            if datetime.now(timezone.utc) > expires:
                return {"valid": False, "error": "Invitation has expired"}

        return {
            "valid": True,
            "invitation_id": invitation.invitation_id,
            "organization_id": invitation.organization_id,
            "invitee_email": invitation.invitee_email,
            "role": invitation.role,
            "inviter_email": invitation.inviter_email,
        }

    async def accept_invitation(self, token: str, user_id: str) -> dict[str, Any]:
        """Accept an invitation.

        Args:
            token: The invitation token.
            user_id: The accepting user's ID.

        Returns:
            Result with organization info.
        """
        validation = await self.validate_token(token)

        if not validation["valid"]:
            return validation

        invitation = await self.get_invitation_by_token(token)
        if not invitation:
            return {"success": False, "error": "Invitation not found"}

        now = datetime.now(timezone.utc).isoformat()

        if self.table is not None:
            try:
                self.table.update_item(
                    Key={"invitation_id": invitation.invitation_id},
                    UpdateExpression="SET #status = :status, accepted_at = :accepted_at",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": InvitationStatus.ACCEPTED.value,
                        ":accepted_at": now,
                    },
                )
            except Exception as e:
                logger.error(f"Failed to accept invitation: {e}")
                return {"success": False, "error": str(e)}

        return {
            "success": True,
            "organization_id": invitation.organization_id,
            "role": invitation.role,
        }

    async def revoke_invitation(self, invitation_id: str, revoker_id: str) -> bool:
        """Revoke an invitation.

        Args:
            invitation_id: The invitation ID.
            revoker_id: The user revoking the invitation.

        Returns:
            True if revoked successfully.
        """
        now = datetime.now(timezone.utc).isoformat()

        if self.table is not None:
            try:
                self.table.update_item(
                    Key={"invitation_id": invitation_id},
                    UpdateExpression="SET #status = :status, revoked_at = :revoked_at",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": InvitationStatus.REVOKED.value,
                        ":revoked_at": now,
                    },
                )
                return True
            except Exception as e:
                logger.error(f"Failed to revoke invitation: {e}")
                return False

        return False

    async def resend_invitation(self, invitation_id: str) -> bool:
        """Resend an invitation email.

        Args:
            invitation_id: The invitation ID.

        Returns:
            True if sent successfully.
        """
        invitation = await self.get_invitation(invitation_id)

        if not invitation:
            return False

        if invitation.status != InvitationStatus.PENDING.value:
            return False

        # Generate new token and extend expiry
        now = datetime.now(timezone.utc)
        new_token = self._generate_token()
        new_expires = now + timedelta(days=self.DEFAULT_EXPIRY_DAYS)

        if self.table is not None:
            try:
                self.table.update_item(
                    Key={"invitation_id": invitation_id},
                    UpdateExpression="SET invitation_token = :token, expires_at = :expires",
                    ExpressionAttributeValues={
                        ":token": new_token,
                        ":expires": new_expires.isoformat(),
                    },
                )
            except Exception as e:
                logger.error(f"Failed to resend invitation: {e}")
                return False

        # Publish to SNS for email sending
        await self._send_invitation_email(invitation)

        return True

    async def _send_invitation_email(self, invitation: TeamInvitation) -> None:
        """Send invitation email via SNS.

        Args:
            invitation: The invitation to send.
        """
        if not self.sns_topic_arn or self.sns is None:
            logger.warning("SNS not configured, skipping email send")
            return

        try:
            import json

            message = {
                "type": "team_invitation",
                "invitation_id": invitation.invitation_id,
                "invitee_email": invitation.invitee_email,
                "inviter_email": invitation.inviter_email,
                "organization_id": invitation.organization_id,
                "role": invitation.role,
                "token": invitation.invitation_token,
                "message": invitation.message,
            }

            self.sns.publish(
                TopicArn=self.sns_topic_arn,
                Message=json.dumps(message),
                Subject="Team Invitation",
            )
        except Exception as e:
            logger.error(f"Failed to send invitation email: {e}")

    async def generate_shareable_link(
        self, organization_id: str, base_url: str | None = None
    ) -> str:
        """Generate a shareable organization invite link.

        Args:
            organization_id: The organization ID.
            base_url: The base application URL.

        Returns:
            The shareable invite URL.
        """
        if base_url is None:
            base_url = os.environ.get("APP_BASE_URL", "https://app.aura.local")
        # Generate a generic org invite token
        token = secrets.token_urlsafe(16)
        return f"{base_url}/join/{organization_id}/{token}"


# Singleton instance
_service_instance: Optional[TeamInvitationService] = None


def get_team_invitation_service() -> TeamInvitationService:
    """Get the team invitation service singleton.

    Returns:
        The TeamInvitationService instance.
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = TeamInvitationService()
    return _service_instance


def set_team_invitation_service(service: TeamInvitationService) -> None:
    """Set the team invitation service instance (for testing).

    Args:
        service: The service instance to use.
    """
    global _service_instance
    _service_instance = service
