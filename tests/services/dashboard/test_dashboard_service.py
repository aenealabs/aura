"""Tests for Dashboard service."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from botocore.exceptions import ClientError

from src.services.dashboard import (
    DashboardCreate,
    DashboardService,
    DashboardUpdate,
    ShareCreate,
    SharePermission,
    UserRole,
)
from src.services.dashboard.exceptions import (
    DashboardAccessDeniedError,
    DashboardConflictError,
    DashboardLimitExceededError,
    DashboardNotFoundError,
    DynamoDBError,
    ShareAlreadyExistsError,
    ShareNotFoundError,
)


class TestDashboardServiceInit:
    """Tests for DashboardService initialization."""

    def test_service_init_defaults(self, mock_dynamodb_resource):
        """Test service initializes with default table name from env or fallback."""
        service = DashboardService(dynamodb_client=mock_dynamodb_resource)
        # Default value is used when table_name is not provided and env var is not set
        assert "dashboard-configs" in service.table_name
        assert service.max_dashboards_per_user == 10

    def test_service_init_with_table_name(self, mock_dynamodb_resource):
        """Test service initializes with explicit table name."""
        service = DashboardService(
            table_name="test-table",
            dynamodb_client=mock_dynamodb_resource,
        )
        assert service.table_name == "test-table"

    def test_service_init_custom(self, mock_dynamodb_resource):
        """Test service initializes with custom values."""
        service = DashboardService(
            table_name="custom-table",
            dynamodb_client=mock_dynamodb_resource,
            max_dashboards_per_user=5,
        )
        assert service.table_name == "custom-table"
        assert service.max_dashboards_per_user == 5


class TestCreateDashboard:
    """Tests for dashboard creation."""

    def test_create_dashboard_success(
        self,
        dashboard_service: DashboardService,
        sample_dashboard_create: DashboardCreate,
        mock_dynamodb_table,
    ):
        """Test successful dashboard creation."""
        # Mock count query to return 0 existing dashboards
        mock_dynamodb_table.query.return_value = {"Count": 0, "Items": []}

        dashboard = dashboard_service.create_dashboard(
            user_id="user-123",
            dashboard_data=sample_dashboard_create,
        )

        assert dashboard.dashboard_id is not None
        assert dashboard.dashboard_id.startswith("dash-")
        assert dashboard.user_id == "user-123"
        assert dashboard.name == "Test Dashboard"
        assert dashboard.version == 1
        assert mock_dynamodb_table.put_item.called

    def test_create_dashboard_with_org_id(
        self,
        dashboard_service: DashboardService,
        sample_dashboard_create: DashboardCreate,
        mock_dynamodb_table,
    ):
        """Test dashboard creation with organization ID."""
        mock_dynamodb_table.query.return_value = {"Count": 0, "Items": []}

        dashboard = dashboard_service.create_dashboard(
            user_id="user-123",
            dashboard_data=sample_dashboard_create,
            org_id="org-456",
        )

        assert dashboard.org_id == "org-456"

    def test_create_dashboard_limit_exceeded(
        self,
        dashboard_service: DashboardService,
        sample_dashboard_create: DashboardCreate,
        mock_dynamodb_table,
    ):
        """Test dashboard creation fails when limit exceeded."""
        # Mock count query to return max dashboards
        mock_dynamodb_table.query.return_value = {"Count": 10}

        with pytest.raises(DashboardLimitExceededError) as exc_info:
            dashboard_service.create_dashboard(
                user_id="user-123",
                dashboard_data=sample_dashboard_create,
            )

        assert exc_info.value.user_id == "user-123"
        assert exc_info.value.limit == 10

    def test_create_dashboard_dynamodb_error(
        self,
        dashboard_service: DashboardService,
        sample_dashboard_create: DashboardCreate,
        mock_dynamodb_table,
    ):
        """Test dashboard creation handles DynamoDB errors."""
        mock_dynamodb_table.query.return_value = {"Count": 0, "Items": []}
        mock_dynamodb_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "DynamoDB error"}},
            "PutItem",
        )

        with pytest.raises(DynamoDBError) as exc_info:
            dashboard_service.create_dashboard(
                user_id="user-123",
                dashboard_data=sample_dashboard_create,
            )

        assert exc_info.value.operation == "put_item"


class TestGetDashboard:
    """Tests for dashboard retrieval."""

    def test_get_dashboard_success(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test successful dashboard retrieval."""
        mock_dynamodb_table.query.return_value = {"Items": [sample_dynamodb_item]}

        dashboard = dashboard_service.get_dashboard(
            dashboard_id="dash-test-12345678",
            user_id="user-123",
        )

        assert dashboard.dashboard_id == "dash-test-12345678"
        assert dashboard.user_id == "user-123"

    def test_get_dashboard_not_found(
        self,
        dashboard_service: DashboardService,
        mock_dynamodb_table,
    ):
        """Test dashboard retrieval when not found."""
        mock_dynamodb_table.query.return_value = {"Items": []}

        with pytest.raises(DashboardNotFoundError) as exc_info:
            dashboard_service.get_dashboard(
                dashboard_id="dash-nonexistent",
                user_id="user-123",
            )

        assert exc_info.value.dashboard_id == "dash-nonexistent"

    def test_get_dashboard_access_denied(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test dashboard retrieval when access denied."""
        # Dashboard belongs to user-123, requesting user is different
        mock_dynamodb_table.query.return_value = {"Items": [sample_dynamodb_item]}
        mock_dynamodb_table.get_item.return_value = {}  # No share record

        with pytest.raises(DashboardAccessDeniedError) as exc_info:
            dashboard_service.get_dashboard(
                dashboard_id="dash-test-12345678",
                user_id="user-different",
            )

        assert exc_info.value.user_id == "user-different"
        assert exc_info.value.action == "view"


class TestUpdateDashboard:
    """Tests for dashboard updates."""

    def test_update_dashboard_success(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test successful dashboard update."""
        mock_dynamodb_table.query.side_effect = [
            {"Items": [sample_dynamodb_item]},  # Get dashboard
            {"Items": []},  # Get user dashboards for unset default
        ]

        update_data = DashboardUpdate(name="Updated Name", description="Updated desc")
        dashboard = dashboard_service.update_dashboard(
            dashboard_id="dash-test-12345678",
            user_id="user-123",
            update_data=update_data,
        )

        assert dashboard.name == "Updated Name"
        assert dashboard.description == "Updated desc"
        assert dashboard.version == 2  # Incremented

    def test_update_dashboard_version_conflict(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test dashboard update with version conflict."""
        mock_dynamodb_table.query.return_value = {"Items": [sample_dynamodb_item]}

        update_data = DashboardUpdate(name="Updated Name")

        with pytest.raises(DashboardConflictError) as exc_info:
            dashboard_service.update_dashboard(
                dashboard_id="dash-test-12345678",
                user_id="user-123",
                update_data=update_data,
                expected_version=5,  # Mismatch with actual version 1
            )

        assert exc_info.value.expected_version == 5
        assert exc_info.value.actual_version == 1

    def test_update_dashboard_not_found(
        self,
        dashboard_service: DashboardService,
        mock_dynamodb_table,
    ):
        """Test dashboard update when not found."""
        mock_dynamodb_table.query.return_value = {"Items": []}

        with pytest.raises(DashboardNotFoundError):
            dashboard_service.update_dashboard(
                dashboard_id="dash-nonexistent",
                user_id="user-123",
                update_data=DashboardUpdate(name="New Name"),
            )


class TestDeleteDashboard:
    """Tests for dashboard deletion."""

    def test_delete_dashboard_success(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test successful dashboard deletion."""
        mock_dynamodb_table.query.side_effect = [
            {"Items": [sample_dynamodb_item]},  # Get dashboard
            {"Items": []},  # Get shares to delete
        ]

        dashboard_service.delete_dashboard(
            dashboard_id="dash-test-12345678",
            user_id="user-123",
        )

        assert mock_dynamodb_table.delete_item.called

    def test_delete_dashboard_not_owner(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test dashboard deletion by non-owner fails."""
        mock_dynamodb_table.query.return_value = {"Items": [sample_dynamodb_item]}

        with pytest.raises(DashboardAccessDeniedError) as exc_info:
            dashboard_service.delete_dashboard(
                dashboard_id="dash-test-12345678",
                user_id="user-different",  # Not the owner
            )

        assert exc_info.value.action == "delete"


class TestListDashboards:
    """Tests for listing dashboards."""

    def test_list_dashboards_empty(
        self,
        dashboard_service: DashboardService,
        mock_dynamodb_table,
    ):
        """Test listing dashboards when none exist."""
        mock_dynamodb_table.query.return_value = {"Items": []}

        dashboards, total = dashboard_service.list_dashboards(user_id="user-123")

        assert dashboards == []
        assert total == 0

    def test_list_dashboards_with_items(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test listing dashboards with items."""
        mock_dynamodb_table.query.return_value = {"Items": [sample_dynamodb_item]}

        dashboards, total = dashboard_service.list_dashboards(user_id="user-123")

        assert len(dashboards) == 1
        assert total == 1
        assert dashboards[0].dashboard_id == "dash-test-12345678"

    def test_list_dashboards_pagination(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test dashboard list pagination."""
        # Create multiple items
        items = []
        for i in range(5):
            item = sample_dynamodb_item.copy()
            item["dashboard_id"] = f"dash-{i}"
            item["sk"] = f"DASHBOARD#dash-{i}"
            items.append(item)

        mock_dynamodb_table.query.return_value = {"Items": items}

        # Get page 1
        dashboards, total = dashboard_service.list_dashboards(
            user_id="user-123",
            page=1,
            page_size=2,
        )

        assert len(dashboards) == 2
        assert total == 5


class TestCloneDashboard:
    """Tests for dashboard cloning."""

    def test_clone_dashboard_success(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test successful dashboard clone."""
        mock_dynamodb_table.query.side_effect = [
            {"Items": [sample_dynamodb_item]},  # Get source dashboard
            {"Count": 0, "Items": []},  # Count existing dashboards
        ]

        clone = dashboard_service.clone_dashboard(
            source_dashboard_id="dash-test-12345678",
            user_id="user-123",
        )

        assert clone.dashboard_id != "dash-test-12345678"
        assert clone.name == "Test Dashboard (Copy)"
        assert clone.is_default is False

    def test_clone_dashboard_custom_name(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test dashboard clone with custom name."""
        mock_dynamodb_table.query.side_effect = [
            {"Items": [sample_dynamodb_item]},  # Get source dashboard
            {"Count": 0, "Items": []},  # Count existing dashboards
        ]

        clone = dashboard_service.clone_dashboard(
            source_dashboard_id="dash-test-12345678",
            user_id="user-123",
            new_name="My Custom Clone",
        )

        assert clone.name == "My Custom Clone"


class TestShareDashboard:
    """Tests for dashboard sharing."""

    def test_share_dashboard_with_user(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test sharing dashboard with a user."""
        mock_dynamodb_table.query.return_value = {"Items": [sample_dynamodb_item]}
        mock_dynamodb_table.get_item.return_value = {}  # No existing share

        share = dashboard_service.share_dashboard(
            dashboard_id="dash-test-12345678",
            owner_user_id="user-123",
            share_data=ShareCreate(
                user_id="user-456",
                permission=SharePermission.VIEW,
            ),
        )

        assert share.shared_with_user_id == "user-456"
        assert share.permission == SharePermission.VIEW
        assert share.shared_by == "user-123"

    def test_share_dashboard_already_exists(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test sharing dashboard when share already exists."""
        mock_dynamodb_table.query.return_value = {"Items": [sample_dynamodb_item]}
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "pk": "SHARE#dash-test-12345678",
                "sk": "USER#user-456",
                "permission": "view",
                "shared_by": "user-123",
                "shared_at": datetime.now(timezone.utc).isoformat(),
                "dashboard_id": "dash-test-12345678",
            }
        }

        with pytest.raises(ShareAlreadyExistsError) as exc_info:
            dashboard_service.share_dashboard(
                dashboard_id="dash-test-12345678",
                owner_user_id="user-123",
                share_data=ShareCreate(
                    user_id="user-456",
                    permission=SharePermission.VIEW,
                ),
            )

        assert exc_info.value.target_id == "user-456"

    def test_share_dashboard_not_owner(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test sharing dashboard when not owner fails."""
        mock_dynamodb_table.query.return_value = {"Items": [sample_dynamodb_item]}

        with pytest.raises(DashboardAccessDeniedError) as exc_info:
            dashboard_service.share_dashboard(
                dashboard_id="dash-test-12345678",
                owner_user_id="user-different",  # Not the owner
                share_data=ShareCreate(
                    user_id="user-456",
                    permission=SharePermission.VIEW,
                ),
            )

        assert exc_info.value.action == "share"


class TestRevokShare:
    """Tests for share revocation."""

    def test_revoke_share_success(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test successful share revocation."""
        mock_dynamodb_table.query.return_value = {"Items": [sample_dynamodb_item]}
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "pk": "SHARE#dash-test-12345678",
                "sk": "USER#user-456",
                "permission": "view",
                "shared_by": "user-123",
                "shared_at": datetime.now(timezone.utc).isoformat(),
                "dashboard_id": "dash-test-12345678",
                "shared_with_user_id": "user-456",
            }
        }

        dashboard_service.revoke_share(
            dashboard_id="dash-test-12345678",
            owner_user_id="user-123",
            target_id="user-456",
        )

        assert mock_dynamodb_table.delete_item.called

    def test_revoke_share_not_found(
        self,
        dashboard_service: DashboardService,
        sample_dynamodb_item: dict,
        mock_dynamodb_table,
    ):
        """Test revoke share when share doesn't exist."""
        mock_dynamodb_table.query.return_value = {"Items": [sample_dynamodb_item]}
        mock_dynamodb_table.get_item.return_value = {}  # No share record

        with pytest.raises(ShareNotFoundError):
            dashboard_service.revoke_share(
                dashboard_id="dash-test-12345678",
                owner_user_id="user-123",
                target_id="user-456",
            )


class TestRoleDefaults:
    """Tests for role-based default dashboards."""

    def test_create_role_default(
        self,
        dashboard_service: DashboardService,
        mock_dynamodb_table,
    ):
        """Test creating role default dashboard."""
        dashboard = dashboard_service.create_role_default(
            role=UserRole.SECURITY_ENGINEER,
            admin_user_id="admin-123",
        )

        assert dashboard.role_default_for == UserRole.SECURITY_ENGINEER
        assert dashboard.name == "Security Overview"
        assert len(dashboard.widgets) == 8

    def test_create_role_default_devops(
        self,
        dashboard_service: DashboardService,
        mock_dynamodb_table,
    ):
        """Test creating DevOps role default dashboard."""
        dashboard = dashboard_service.create_role_default(
            role=UserRole.DEVOPS,
            admin_user_id="admin-123",
        )

        assert dashboard.role_default_for == UserRole.DEVOPS
        assert dashboard.name == "Operations Overview"

    def test_create_role_default_executive(
        self,
        dashboard_service: DashboardService,
        mock_dynamodb_table,
    ):
        """Test creating Executive role default dashboard."""
        dashboard = dashboard_service.create_role_default(
            role=UserRole.EXECUTIVE,
            admin_user_id="admin-123",
        )

        assert dashboard.role_default_for == UserRole.EXECUTIVE
        assert dashboard.name == "Executive Summary"
        assert len(dashboard.widgets) == 4
