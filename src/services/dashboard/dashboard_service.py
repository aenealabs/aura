"""Dashboard Service for customizable widget dashboards.

Implements CRUD operations for dashboards with DynamoDB persistence,
role-based defaults, sharing, and audit trail per ADR-064.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from .exceptions import (
    DashboardAccessDeniedError,
    DashboardConflictError,
    DashboardLimitExceededError,
    DashboardNotFoundError,
    DashboardValidationError,
    DynamoDBError,
    RoleDefaultNotFoundError,
    ShareAlreadyExistsError,
    ShareNotFoundError,
)
from .models import (
    ROLE_DEFAULTS,
    Dashboard,
    DashboardCreate,
    DashboardSummary,
    DashboardUpdate,
    LayoutConfig,
    ShareCreate,
    SharePermission,
    ShareRecord,
    UserRole,
    WidgetConfig,
)

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_MAX_DASHBOARDS_PER_USER = 10
TABLE_NAME = os.environ.get("DASHBOARD_TABLE_NAME", "aura-dashboard-configs-dev")


class DashboardService:
    """Service for managing customizable dashboard configurations.

    Provides CRUD operations for dashboards with DynamoDB persistence,
    role-based defaults, sharing capabilities, and optimistic locking.
    """

    def __init__(
        self,
        table_name: str | None = None,
        dynamodb_client: Any | None = None,
        max_dashboards_per_user: int = DEFAULT_MAX_DASHBOARDS_PER_USER,
    ) -> None:
        """Initialize the dashboard service.

        Args:
            table_name: DynamoDB table name (defaults to env var)
            dynamodb_client: Optional boto3 DynamoDB resource for testing
            max_dashboards_per_user: Maximum dashboards allowed per user
        """
        self.table_name = table_name or TABLE_NAME
        self._dynamodb = dynamodb_client or boto3.resource("dynamodb")
        self._table = self._dynamodb.Table(self.table_name)
        self.max_dashboards_per_user = max_dashboards_per_user

    # =========================================================================
    # Dashboard CRUD Operations
    # =========================================================================

    def create_dashboard(
        self,
        user_id: str,
        dashboard_data: DashboardCreate,
        org_id: str | None = None,
    ) -> Dashboard:
        """Create a new dashboard for a user.

        Args:
            user_id: Owner user ID
            dashboard_data: Dashboard creation data
            org_id: Optional organization ID

        Returns:
            Created Dashboard object

        Raises:
            DashboardLimitExceededError: If user has reached max dashboards
            DynamoDBError: If DynamoDB operation fails
        """
        # Check dashboard limit
        existing_count = self._count_user_dashboards(user_id)
        if existing_count >= self.max_dashboards_per_user:
            raise DashboardLimitExceededError(user_id, self.max_dashboards_per_user)

        # Generate new dashboard ID
        dashboard_id = f"dash-{uuid.uuid4()}"
        now = datetime.now(timezone.utc)

        # Build the dashboard item
        dashboard = Dashboard(
            dashboard_id=dashboard_id,
            user_id=user_id,
            org_id=org_id,
            name=dashboard_data.name,
            description=dashboard_data.description,
            layout=dashboard_data.layout,
            widgets=dashboard_data.widgets,
            is_default=dashboard_data.is_default,
            version=1,
            created_at=now,
            updated_at=now,
        )

        # Build DynamoDB item
        item = self._dashboard_to_item(dashboard)

        try:
            # If setting as default, unset any existing default first
            if dashboard_data.is_default:
                self._unset_user_default(user_id)

            self._table.put_item(Item=item)
            logger.info(f"Created dashboard {dashboard_id} for user {user_id}")
            return dashboard

        except ClientError as e:
            logger.error(f"Failed to create dashboard: {e}")
            raise DynamoDBError("put_item", e) from e

    def get_dashboard(self, dashboard_id: str, user_id: str) -> Dashboard:
        """Get a dashboard by ID with access check.

        Args:
            dashboard_id: Dashboard ID to retrieve
            user_id: User requesting access

        Returns:
            Dashboard object

        Raises:
            DashboardNotFoundError: If dashboard doesn't exist
            DashboardAccessDeniedError: If user lacks access
        """
        # Try to find dashboard in user's own dashboards first
        dashboard = self._get_dashboard_by_id(dashboard_id)

        if dashboard is None:
            raise DashboardNotFoundError(dashboard_id)

        # Check access
        if not self._user_has_access(dashboard, user_id):
            raise DashboardAccessDeniedError(dashboard_id, user_id, "view")

        return dashboard

    def update_dashboard(
        self,
        dashboard_id: str,
        user_id: str,
        update_data: DashboardUpdate,
        expected_version: int | None = None,
    ) -> Dashboard:
        """Update an existing dashboard.

        Args:
            dashboard_id: Dashboard ID to update
            user_id: User performing the update
            update_data: Fields to update
            expected_version: Expected version for optimistic locking

        Returns:
            Updated Dashboard object

        Raises:
            DashboardNotFoundError: If dashboard doesn't exist
            DashboardAccessDeniedError: If user lacks edit permission
            DashboardConflictError: If version mismatch
        """
        dashboard = self._get_dashboard_by_id(dashboard_id)

        if dashboard is None:
            raise DashboardNotFoundError(dashboard_id)

        # Check edit permission
        if not self._user_can_edit(dashboard, user_id):
            raise DashboardAccessDeniedError(dashboard_id, user_id, "edit")

        # Check version for optimistic locking
        if expected_version is not None and dashboard.version != expected_version:
            raise DashboardConflictError(
                dashboard_id, expected_version, dashboard.version
            )

        # Apply updates
        now = datetime.now(timezone.utc)
        update_dict = update_data.model_dump(exclude_unset=True)

        if "name" in update_dict:
            dashboard.name = update_dict["name"]
        if "description" in update_dict:
            dashboard.description = update_dict["description"]
        if "layout" in update_dict:
            dashboard.layout = LayoutConfig(**update_dict["layout"])
        if "widgets" in update_dict:
            dashboard.widgets = [WidgetConfig(**w) for w in update_dict["widgets"]]
        if "is_default" in update_dict:
            if update_dict["is_default"] and not dashboard.is_default:
                self._unset_user_default(user_id)
            dashboard.is_default = update_dict["is_default"]

        dashboard.version += 1
        dashboard.updated_at = now

        # Save to DynamoDB
        item = self._dashboard_to_item(dashboard)

        try:
            self._table.put_item(Item=item)
            logger.info(f"Updated dashboard {dashboard_id}")
            return dashboard

        except ClientError as e:
            logger.error(f"Failed to update dashboard: {e}")
            raise DynamoDBError("put_item", e) from e

    def delete_dashboard(self, dashboard_id: str, user_id: str) -> None:
        """Delete a dashboard.

        Args:
            dashboard_id: Dashboard ID to delete
            user_id: User performing the deletion

        Raises:
            DashboardNotFoundError: If dashboard doesn't exist
            DashboardAccessDeniedError: If user is not the owner
        """
        dashboard = self._get_dashboard_by_id(dashboard_id)

        if dashboard is None:
            raise DashboardNotFoundError(dashboard_id)

        # Only owner can delete
        if dashboard.user_id != user_id:
            raise DashboardAccessDeniedError(dashboard_id, user_id, "delete")

        try:
            # Delete the dashboard record
            self._table.delete_item(
                Key={
                    "pk": f"USER#{dashboard.user_id}",
                    "sk": f"DASHBOARD#{dashboard_id}",
                }
            )

            # Delete all share records
            self._delete_dashboard_shares(dashboard_id)

            logger.info(f"Deleted dashboard {dashboard_id}")

        except ClientError as e:
            logger.error(f"Failed to delete dashboard: {e}")
            raise DynamoDBError("delete_item", e) from e

    def list_dashboards(
        self,
        user_id: str,
        include_shared: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DashboardSummary], int]:
        """List dashboards accessible to a user.

        Args:
            user_id: User ID to list dashboards for
            include_shared: Whether to include shared dashboards
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (dashboard summaries, total count)
        """
        dashboards: list[DashboardSummary] = []

        # Get user's own dashboards
        user_dashboards = self._get_user_dashboards(user_id)
        dashboards.extend(user_dashboards)

        # Get shared dashboards if requested
        if include_shared:
            shared_dashboards = self._get_shared_dashboards(user_id)
            dashboards.extend(shared_dashboards)

        # Sort by updated_at descending
        dashboards.sort(key=lambda d: d.updated_at, reverse=True)

        # Apply pagination
        total = len(dashboards)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = dashboards[start_idx:end_idx]

        return paginated, total

    # =========================================================================
    # Clone and Share Operations
    # =========================================================================

    def clone_dashboard(
        self,
        source_dashboard_id: str,
        user_id: str,
        new_name: str | None = None,
    ) -> Dashboard:
        """Clone a dashboard to the user's account.

        Args:
            source_dashboard_id: Dashboard ID to clone
            user_id: User who will own the clone
            new_name: Optional name for the clone

        Returns:
            Cloned Dashboard object
        """
        source = self.get_dashboard(source_dashboard_id, user_id)

        clone_data = DashboardCreate(
            name=new_name or f"{source.name} (Copy)",
            description=source.description,
            layout=source.layout,
            widgets=source.widgets,
            is_default=False,  # Clone is never default
        )

        return self.create_dashboard(user_id, clone_data)

    def share_dashboard(
        self,
        dashboard_id: str,
        owner_user_id: str,
        share_data: ShareCreate,
    ) -> ShareRecord:
        """Share a dashboard with a user or organization.

        Args:
            dashboard_id: Dashboard ID to share
            owner_user_id: Owner performing the share
            share_data: Share configuration

        Returns:
            Created ShareRecord

        Raises:
            DashboardNotFoundError: If dashboard doesn't exist
            DashboardAccessDeniedError: If user is not the owner
            ShareAlreadyExistsError: If share already exists
        """
        dashboard = self._get_dashboard_by_id(dashboard_id)

        if dashboard is None:
            raise DashboardNotFoundError(dashboard_id)

        if dashboard.user_id != owner_user_id:
            raise DashboardAccessDeniedError(dashboard_id, owner_user_id, "share")

        now = datetime.now(timezone.utc)
        target_id = share_data.user_id or share_data.org_id

        # Check if share already exists
        existing = self._get_share_record(dashboard_id, target_id)
        if existing is not None:
            raise ShareAlreadyExistsError(dashboard_id, target_id)

        # Create share record
        share = ShareRecord(
            dashboard_id=dashboard_id,
            shared_with_user_id=share_data.user_id,
            shared_with_org_id=share_data.org_id,
            permission=share_data.permission,
            shared_by=owner_user_id,
            shared_at=now,
        )

        # Build DynamoDB item
        if share_data.user_id:
            sk = f"USER#{share_data.user_id}"
        else:
            sk = f"ORG#{share_data.org_id}"

        item = {
            "pk": f"SHARE#{dashboard_id}",
            "sk": sk,
            "dashboard_id": dashboard_id,
            "permission": share.permission.value,
            "shared_by": share.shared_by,
            "shared_at": share.shared_at.isoformat(),
        }

        if share_data.user_id:
            item["shared_with_user_id"] = share_data.user_id
        if share_data.org_id:
            item["shared_with_org_id"] = share_data.org_id
            item["org_id"] = share_data.org_id

        try:
            self._table.put_item(Item=item)
            logger.info(f"Shared dashboard {dashboard_id} with {target_id}")
            return share

        except ClientError as e:
            logger.error(f"Failed to share dashboard: {e}")
            raise DynamoDBError("put_item", e) from e

    def revoke_share(
        self,
        dashboard_id: str,
        owner_user_id: str,
        target_id: str,
    ) -> None:
        """Revoke a dashboard share.

        Args:
            dashboard_id: Dashboard ID
            owner_user_id: Owner revoking the share
            target_id: User or org ID to revoke access from

        Raises:
            DashboardNotFoundError: If dashboard doesn't exist
            DashboardAccessDeniedError: If user is not the owner
            ShareNotFoundError: If share doesn't exist
        """
        dashboard = self._get_dashboard_by_id(dashboard_id)

        if dashboard is None:
            raise DashboardNotFoundError(dashboard_id)

        if dashboard.user_id != owner_user_id:
            raise DashboardAccessDeniedError(dashboard_id, owner_user_id, "share")

        existing = self._get_share_record(dashboard_id, target_id)
        if existing is None:
            raise ShareNotFoundError(dashboard_id, target_id)

        # Determine SK based on target type
        if existing.shared_with_user_id:
            sk = f"USER#{target_id}"
        else:
            sk = f"ORG#{target_id}"

        try:
            self._table.delete_item(
                Key={
                    "pk": f"SHARE#{dashboard_id}",
                    "sk": sk,
                }
            )
            logger.info(f"Revoked share for dashboard {dashboard_id} from {target_id}")

        except ClientError as e:
            logger.error(f"Failed to revoke share: {e}")
            raise DynamoDBError("delete_item", e) from e

    def list_shares(self, dashboard_id: str, user_id: str) -> list[ShareRecord]:
        """List all shares for a dashboard.

        Args:
            dashboard_id: Dashboard ID
            user_id: User requesting the list (must be owner)

        Returns:
            List of ShareRecords
        """
        dashboard = self.get_dashboard(dashboard_id, user_id)

        if dashboard.user_id != user_id:
            raise DashboardAccessDeniedError(dashboard_id, user_id, "view shares")

        try:
            response = self._table.query(
                KeyConditionExpression=Key("pk").eq(f"SHARE#{dashboard_id}")
            )

            shares = []
            for item in response.get("Items", []):
                shares.append(
                    ShareRecord(
                        dashboard_id=item["dashboard_id"],
                        shared_with_user_id=item.get("shared_with_user_id"),
                        shared_with_org_id=item.get("shared_with_org_id"),
                        permission=SharePermission(item["permission"]),
                        shared_by=item["shared_by"],
                        shared_at=datetime.fromisoformat(item["shared_at"]),
                    )
                )

            return shares

        except ClientError as e:
            logger.error(f"Failed to list shares: {e}")
            raise DynamoDBError("query", e) from e

    # =========================================================================
    # Role Default Operations
    # =========================================================================

    def get_role_default(self, role: UserRole) -> Dashboard:
        """Get the default dashboard for a role.

        Args:
            role: User role

        Returns:
            Dashboard configured as default for the role

        Raises:
            RoleDefaultNotFoundError: If no default exists for the role
        """
        try:
            response = self._table.query(
                IndexName="RoleDefaultIndex",
                KeyConditionExpression=Key("role_default_for").eq(role.value),
                Limit=1,
            )

            items = response.get("Items", [])
            if not items:
                raise RoleDefaultNotFoundError(role.value)

            return self._item_to_dashboard(items[0])

        except ClientError as e:
            logger.error(f"Failed to get role default: {e}")
            raise DynamoDBError("query", e) from e

    def create_role_default(self, role: UserRole, admin_user_id: str) -> Dashboard:
        """Create a default dashboard for a role.

        Args:
            role: User role to create default for
            admin_user_id: Admin user creating the default

        Returns:
            Created Dashboard
        """
        if role not in ROLE_DEFAULTS:
            raise DashboardValidationError(
                f"No default configuration for role: {role.value}"
            )

        # Get the default configuration for this role
        default_config = ROLE_DEFAULTS[role]()

        # Generate dashboard
        dashboard_id = f"dash-{uuid.uuid4()}"
        now = datetime.now(timezone.utc)

        dashboard = Dashboard(
            dashboard_id=dashboard_id,
            user_id=admin_user_id,
            name=default_config.name,
            description=default_config.description,
            layout=default_config.layout,
            widgets=default_config.widgets,
            is_default=False,
            role_default_for=role,
            version=1,
            created_at=now,
            updated_at=now,
        )

        item = self._dashboard_to_item(dashboard)

        try:
            self._table.put_item(Item=item)
            logger.info(f"Created role default for {role.value}")
            return dashboard

        except ClientError as e:
            logger.error(f"Failed to create role default: {e}")
            raise DynamoDBError("put_item", e) from e

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _dashboard_to_item(self, dashboard: Dashboard) -> dict[str, Any]:
        """Convert Dashboard model to DynamoDB item."""
        item = {
            "pk": f"USER#{dashboard.user_id}",
            "sk": f"DASHBOARD#{dashboard.dashboard_id}",
            "dashboard_id": dashboard.dashboard_id,
            "user_id": dashboard.user_id,
            "name": dashboard.name,
            "description": dashboard.description,
            "layout_json": json.dumps(dashboard.layout.model_dump()),
            "widgets_json": json.dumps([w.model_dump() for w in dashboard.widgets]),
            "is_default": dashboard.is_default,
            "version": dashboard.version,
            "created_at": dashboard.created_at.isoformat(),
            "updated_at": dashboard.updated_at.isoformat(),
        }

        if dashboard.org_id:
            item["org_id"] = dashboard.org_id
        if dashboard.role_default_for:
            item["role_default_for"] = dashboard.role_default_for.value

        return item

    def _item_to_dashboard(self, item: dict[str, Any]) -> Dashboard:
        """Convert DynamoDB item to Dashboard model."""
        layout_data = json.loads(item.get("layout_json", "{}"))
        widgets_data = json.loads(item.get("widgets_json", "[]"))

        role_default = None
        if item.get("role_default_for"):
            role_default = UserRole(item["role_default_for"])

        return Dashboard(
            dashboard_id=item["dashboard_id"],
            user_id=item["user_id"],
            org_id=item.get("org_id"),
            name=item["name"],
            description=item.get("description", ""),
            layout=LayoutConfig(**layout_data),
            widgets=[WidgetConfig(**w) for w in widgets_data],
            is_default=item.get("is_default", False),
            role_default_for=role_default,
            version=item.get("version", 1),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )

    def _get_dashboard_by_id(self, dashboard_id: str) -> Dashboard | None:
        """Get dashboard by ID using GSI."""
        try:
            response = self._table.query(
                IndexName="DashboardIdIndex",
                KeyConditionExpression=Key("dashboard_id").eq(dashboard_id),
                Limit=1,
            )

            items = response.get("Items", [])
            if not items:
                return None

            return self._item_to_dashboard(items[0])

        except ClientError as e:
            logger.error(f"Failed to get dashboard by ID: {e}")
            raise DynamoDBError("query", e) from e

    def _get_user_dashboards(self, user_id: str) -> list[DashboardSummary]:
        """Get all dashboards owned by a user."""
        try:
            response = self._table.query(
                KeyConditionExpression=Key("pk").eq(f"USER#{user_id}")
                & Key("sk").begins_with("DASHBOARD#")
            )

            summaries = []
            for item in response.get("Items", []):
                widgets = json.loads(item.get("widgets_json", "[]"))
                role_default = None
                if item.get("role_default_for"):
                    role_default = UserRole(item["role_default_for"])

                summaries.append(
                    DashboardSummary(
                        dashboard_id=item["dashboard_id"],
                        name=item["name"],
                        description=item.get("description", ""),
                        widget_count=len(widgets),
                        is_default=item.get("is_default", False),
                        role_default_for=role_default,
                        updated_at=datetime.fromisoformat(item["updated_at"]),
                        shared=False,
                    )
                )

            return summaries

        except ClientError as e:
            logger.error(f"Failed to get user dashboards: {e}")
            raise DynamoDBError("query", e) from e

    def _get_shared_dashboards(self, user_id: str) -> list[DashboardSummary]:
        """Get dashboards shared with a user."""
        # This would need a GSI on shared_with_user_id to be efficient
        # For now, return empty list - full implementation would query SHARE# records
        return []

    def _count_user_dashboards(self, user_id: str) -> int:
        """Count dashboards owned by a user."""
        try:
            response = self._table.query(
                KeyConditionExpression=Key("pk").eq(f"USER#{user_id}")
                & Key("sk").begins_with("DASHBOARD#"),
                Select="COUNT",
            )
            return response.get("Count", 0)

        except ClientError as e:
            logger.error(f"Failed to count user dashboards: {e}")
            raise DynamoDBError("query", e) from e

    def _user_has_access(self, dashboard: Dashboard, user_id: str) -> bool:
        """Check if user has view access to dashboard."""
        # Owner always has access
        if dashboard.user_id == user_id:
            return True

        # Check for share record
        share = self._get_share_record(dashboard.dashboard_id, user_id)
        return share is not None

    def _user_can_edit(self, dashboard: Dashboard, user_id: str) -> bool:
        """Check if user has edit access to dashboard."""
        # Owner can always edit
        if dashboard.user_id == user_id:
            return True

        # Check for share record with edit permission
        share = self._get_share_record(dashboard.dashboard_id, user_id)
        if share and share.permission == SharePermission.EDIT:
            return True

        return False

    def _get_share_record(
        self, dashboard_id: str, target_id: str
    ) -> ShareRecord | None:
        """Get a specific share record."""
        try:
            # Try user share first
            response = self._table.get_item(
                Key={
                    "pk": f"SHARE#{dashboard_id}",
                    "sk": f"USER#{target_id}",
                }
            )

            if "Item" in response:
                item = response["Item"]
                return ShareRecord(
                    dashboard_id=item["dashboard_id"],
                    shared_with_user_id=item.get("shared_with_user_id"),
                    shared_with_org_id=item.get("shared_with_org_id"),
                    permission=SharePermission(item["permission"]),
                    shared_by=item["shared_by"],
                    shared_at=datetime.fromisoformat(item["shared_at"]),
                )

            # Try org share
            response = self._table.get_item(
                Key={
                    "pk": f"SHARE#{dashboard_id}",
                    "sk": f"ORG#{target_id}",
                }
            )

            if "Item" in response:
                item = response["Item"]
                return ShareRecord(
                    dashboard_id=item["dashboard_id"],
                    shared_with_user_id=item.get("shared_with_user_id"),
                    shared_with_org_id=item.get("shared_with_org_id"),
                    permission=SharePermission(item["permission"]),
                    shared_by=item["shared_by"],
                    shared_at=datetime.fromisoformat(item["shared_at"]),
                )

            return None

        except ClientError as e:
            logger.error(f"Failed to get share record: {e}")
            raise DynamoDBError("get_item", e) from e

    def _unset_user_default(self, user_id: str) -> None:
        """Unset any existing default dashboard for a user."""
        dashboards = self._get_user_dashboards(user_id)
        for dash in dashboards:
            if dash.is_default:
                try:
                    self._table.update_item(
                        Key={
                            "pk": f"USER#{user_id}",
                            "sk": f"DASHBOARD#{dash.dashboard_id}",
                        },
                        UpdateExpression="SET is_default = :false",
                        ExpressionAttributeValues={":false": False},
                    )
                except ClientError as e:
                    logger.error(f"Failed to unset default: {e}")

    def _delete_dashboard_shares(self, dashboard_id: str) -> None:
        """Delete all share records for a dashboard."""
        try:
            response = self._table.query(
                KeyConditionExpression=Key("pk").eq(f"SHARE#{dashboard_id}")
            )

            for item in response.get("Items", []):
                self._table.delete_item(
                    Key={
                        "pk": item["pk"],
                        "sk": item["sk"],
                    }
                )

        except ClientError as e:
            logger.error(f"Failed to delete shares: {e}")
            # Don't raise, shares are secondary to dashboard deletion


# =============================================================================
# Singleton Factory
# =============================================================================

_service_instance: DashboardService | None = None


def get_dashboard_service() -> DashboardService:
    """Get singleton instance of DashboardService.

    Creates the service instance on first call, reuses it for subsequent calls.
    This pattern ensures consistent DynamoDB connection reuse across API calls.

    Returns:
        DashboardService: Singleton service instance

    Example:
        service = get_dashboard_service()
        dashboard = service.get_dashboard(dashboard_id, user_id)
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = DashboardService()
    return _service_instance


def reset_dashboard_service() -> None:
    """Reset the singleton instance. Primarily for testing.

    Clears the cached service instance so a new one will be created
    on the next call to get_dashboard_service().
    """
    global _service_instance
    _service_instance = None
