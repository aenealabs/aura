"""
Project Aura - Identity Audit Service

Audit logging for authentication events and IdP configuration changes.

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.services.identity.models import AuditLogEntry, AuthAction

logger = logging.getLogger(__name__)


class IdentityAuditService:
    """
    Service for logging identity-related audit events.

    Tracks:
    - IdP configuration changes
    - Authentication attempts (success/failure)
    - Token operations (refresh, revoke)
    - Session events (logout)
    """

    # Default TTL: 90 days
    DEFAULT_TTL_DAYS = 90

    def __init__(
        self,
        table_name: str | None = None,
        dynamodb_client: Any = None,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ):
        """
        Initialize audit service.

        Args:
            table_name: DynamoDB audit table name
            dynamodb_client: Optional DynamoDB resource
            ttl_days: Days to retain audit logs
        """
        self.table_name = table_name or os.environ.get(
            "IDP_AUDIT_TABLE", "aura-idp-audit-dev"
        )
        self.dynamodb = dynamodb_client or boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)
        self.ttl_days = ttl_days

    async def log_event(
        self,
        action: AuthAction,
        idp_id: str,
        organization_id: str,
        actor_id: str | None = None,
        target_user_id: str | None = None,
        success: bool = True,
        error_message: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLogEntry:
        """
        Log an audit event.

        Args:
            action: Type of action
            idp_id: IdP identifier
            organization_id: Organization ID
            actor_id: User performing the action
            target_user_id: User affected (for auth events)
            success: Whether the action succeeded
            error_message: Error message if failed
            ip_address: Client IP
            user_agent: Client user agent
            details: Additional details

        Returns:
            Created audit log entry
        """
        now = datetime.now(timezone.utc)
        ttl = int((now + timedelta(days=self.ttl_days)).timestamp())

        entry = AuditLogEntry(
            audit_id=str(uuid.uuid4()),
            idp_id=idp_id,
            organization_id=organization_id,
            action_type=action.value,
            actor_id=actor_id,
            target_user_id=target_user_id,
            timestamp=now.isoformat(),
            success=success,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            ttl=ttl,
        )

        try:
            self.table.put_item(Item=entry.to_dynamodb_item())
            logger.debug(f"Logged audit event: {action.value} for IdP {idp_id}")
        except ClientError as e:
            logger.error(f"Failed to log audit event: {e}")
            # Don't raise - audit logging shouldn't break auth flow

        return entry

    async def log_auth_success(
        self,
        idp_id: str,
        organization_id: str,
        user_id: str,
        email: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLogEntry:
        """Log successful authentication."""
        return await self.log_event(
            action=AuthAction.AUTH_SUCCESS,
            idp_id=idp_id,
            organization_id=organization_id,
            target_user_id=user_id,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"email": email} if email else None,
        )

    async def log_auth_failure(
        self,
        idp_id: str,
        organization_id: str,
        username: str | None = None,
        error: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLogEntry:
        """Log failed authentication."""
        return await self.log_event(
            action=AuthAction.AUTH_FAILURE,
            idp_id=idp_id,
            organization_id=organization_id,
            success=False,
            error_message=error,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"username": username} if username else None,
        )

    async def log_config_change(
        self,
        action: AuthAction,
        idp_id: str,
        organization_id: str,
        actor_id: str,
        changes: dict[str, Any] | None = None,
    ) -> AuditLogEntry:
        """Log IdP configuration change."""
        return await self.log_event(
            action=action,
            idp_id=idp_id,
            organization_id=organization_id,
            actor_id=actor_id,
            success=True,
            details={"changes": changes} if changes else None,
        )

    async def get_audit_logs(
        self,
        idp_id: str | None = None,
        organization_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        action_type: AuthAction | None = None,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        """
        Query audit logs.

        Args:
            idp_id: Filter by IdP
            organization_id: Filter by organization
            start_time: Start of time range
            end_time: End of time range
            action_type: Filter by action type
            limit: Maximum records to return

        Returns:
            List of audit log entries
        """
        try:
            if idp_id:
                # Query by IdP
                key_condition = "idp_id = :idp_id"
                expr_values: dict[str, Any] = {":idp_id": idp_id}

                if start_time and end_time:
                    key_condition += " AND #ts BETWEEN :start AND :end"
                    expr_values[":start"] = start_time.isoformat()
                    expr_values[":end"] = end_time.isoformat()

                response = self.table.query(
                    IndexName="idp-timestamp-index",
                    KeyConditionExpression=key_condition,
                    ExpressionAttributeNames={"#ts": "timestamp"},
                    ExpressionAttributeValues=expr_values,
                    ScanIndexForward=False,  # Most recent first
                    Limit=limit,
                )

            elif organization_id:
                # Query by organization
                key_condition = "organization_id = :org_id"
                expr_values = {":org_id": organization_id}

                if start_time and end_time:
                    key_condition += " AND #ts BETWEEN :start AND :end"
                    expr_values[":start"] = start_time.isoformat()
                    expr_values[":end"] = end_time.isoformat()

                response = self.table.query(
                    IndexName="organization-timestamp-index",
                    KeyConditionExpression=key_condition,
                    ExpressionAttributeNames={"#ts": "timestamp"},
                    ExpressionAttributeValues=expr_values,
                    ScanIndexForward=False,
                    Limit=limit,
                )

            else:
                # Scan (not recommended for large tables)
                response = self.table.scan(Limit=limit)

            entries = []
            for item in response.get("Items", []):
                entry = AuditLogEntry(
                    audit_id=item["audit_id"],
                    idp_id=item["idp_id"],
                    organization_id=item["organization_id"],
                    action_type=item["action_type"],
                    actor_id=item.get("actor_id"),
                    target_user_id=item.get("target_user_id"),
                    timestamp=item["timestamp"],
                    success=item.get("success", True),
                    error_message=item.get("error_message"),
                    ip_address=item.get("ip_address"),
                    user_agent=item.get("user_agent"),
                    details=item.get("details", {}),
                )

                # Filter by action type if specified
                if action_type and entry.action_type != action_type.value:
                    continue

                entries.append(entry)

            return entries

        except ClientError as e:
            logger.error(f"Failed to query audit logs: {e}")
            raise


# Singleton instance
_audit_service: IdentityAuditService | None = None


def get_audit_service() -> IdentityAuditService:
    """Get or create audit service singleton."""
    global _audit_service
    if _audit_service is None:
        _audit_service = IdentityAuditService()
    return _audit_service
