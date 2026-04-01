"""Tests for Dashboard API Endpoints.

Tests for ADR-064 Phase 2 sharing and collaboration features.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.api.auth import User, get_current_user
from src.api.dashboard_endpoints import router, widget_router
from src.services.dashboard import (
    Dashboard,
    LayoutConfig,
    LayoutItem,
    SharePermission,
    ShareRecord,
    WidgetCategory,
    WidgetConfig,
    WidgetDataSource,
    WidgetType,
)
from src.services.dashboard.exceptions import (
    DashboardAccessDeniedError,
    DashboardLimitExceededError,
    DashboardNotFoundError,
    ShareNotFoundError,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    return User(
        sub="user-123",
        email="test@example.com",
        name="Test User",
        groups=["security-engineer"],
    )


@pytest.fixture
def mock_dashboard():
    """Create a mock dashboard."""
    return Dashboard(
        dashboard_id="dash-001",
        user_id="user-123",
        name="Test Dashboard",
        description="A test dashboard",
        layout=LayoutConfig(
            columns=12,
            row_height=100,
            items=[
                LayoutItem(i="widget-1", x=0, y=0, w=3, h=2),
            ],
        ),
        widgets=[
            WidgetConfig(
                id="widget-1",
                type=WidgetType.METRIC,
                title="Open Vulnerabilities",
                data_source=WidgetDataSource(
                    endpoint="security/vulnerabilities/open",
                    refresh_seconds=60,
                ),
            ),
        ],
        is_default=False,
        version=1,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def mock_share():
    """Create a mock share record."""
    return ShareRecord(
        dashboard_id="dash-001",
        shared_with_user_id="user-456",
        permission=SharePermission.VIEW,
        shared_by="user-123",
        shared_at=datetime.now(),
    )


@pytest.fixture
def app(mock_user):
    """Create test FastAPI app with dependency overrides."""
    app = FastAPI()
    app.include_router(router)
    app.include_router(widget_router)

    # Override auth dependency
    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# =============================================================================
# Dashboard CRUD Tests
# =============================================================================


class TestListDashboards:
    """Tests for listing dashboards."""

    def test_list_dashboards_success(self, client, mock_dashboard):
        """Test listing dashboards returns user's dashboards."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.list_dashboards.return_value = [mock_dashboard]
            mock_get.return_value = mock_service

            response = client.get("/api/v1/dashboards")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 1
            assert len(data["dashboards"]) == 1
            assert data["dashboards"][0]["dashboard_id"] == "dash-001"

    def test_list_dashboards_empty(self, client):
        """Test listing dashboards when user has none."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.list_dashboards.return_value = []
            mock_get.return_value = mock_service

            response = client.get("/api/v1/dashboards")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 0
            assert data["dashboards"] == []


class TestCreateDashboard:
    """Tests for creating dashboards."""

    def test_create_dashboard_success(self, client, mock_dashboard):
        """Test creating a dashboard succeeds."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.create_dashboard.return_value = mock_dashboard
            mock_get.return_value = mock_service

            response = client.post(
                "/api/v1/dashboards",
                json={
                    "name": "New Dashboard",
                    "description": "Test description",
                    "layout": [],
                    "widgets": [],
                },
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Test Dashboard"

    def test_create_dashboard_limit_exceeded(self, client):
        """Test creating dashboard fails when limit exceeded."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.create_dashboard.side_effect = DashboardLimitExceededError(
                "user-123", 10
            )
            mock_get.return_value = mock_service

            response = client.post(
                "/api/v1/dashboards",
                json={"name": "New Dashboard"},
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN


class TestGetDashboard:
    """Tests for getting a single dashboard."""

    def test_get_dashboard_success(self, client, mock_dashboard):
        """Test getting a dashboard by ID."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_dashboard.return_value = mock_dashboard
            mock_get.return_value = mock_service

            response = client.get("/api/v1/dashboards/dash-001")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["dashboard_id"] == "dash-001"
            assert data["name"] == "Test Dashboard"

    def test_get_dashboard_not_found(self, client):
        """Test getting non-existent dashboard returns 404."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_dashboard.side_effect = DashboardNotFoundError("dash-999")
            mock_get.return_value = mock_service

            response = client.get("/api/v1/dashboards/dash-999")

            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_dashboard_access_denied(self, client):
        """Test getting dashboard without access returns 403."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_dashboard.side_effect = DashboardAccessDeniedError(
                "dash-001", "user-123"
            )
            mock_get.return_value = mock_service

            response = client.get("/api/v1/dashboards/dash-001")

            assert response.status_code == status.HTTP_403_FORBIDDEN


class TestUpdateDashboard:
    """Tests for updating dashboards."""

    def test_update_dashboard_success(self, client, mock_dashboard):
        """Test updating a dashboard succeeds."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.update_dashboard.return_value = mock_dashboard
            mock_get.return_value = mock_service

            response = client.put(
                "/api/v1/dashboards/dash-001",
                json={"name": "Updated Dashboard"},
            )

            assert response.status_code == status.HTTP_200_OK

    def test_update_dashboard_not_found(self, client):
        """Test updating non-existent dashboard returns 404."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.update_dashboard.side_effect = DashboardNotFoundError(
                "dash-999"
            )
            mock_get.return_value = mock_service

            response = client.put(
                "/api/v1/dashboards/dash-999",
                json={"name": "Updated"},
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteDashboard:
    """Tests for deleting dashboards."""

    def test_delete_dashboard_success(self, client):
        """Test deleting a dashboard succeeds."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.delete_dashboard.return_value = None
            mock_get.return_value = mock_service

            response = client.delete("/api/v1/dashboards/dash-001")

            assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_dashboard_not_found(self, client):
        """Test deleting non-existent dashboard returns 404."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.delete_dashboard.side_effect = DashboardNotFoundError(
                "dash-999"
            )
            mock_get.return_value = mock_service

            response = client.delete("/api/v1/dashboards/dash-999")

            assert response.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# Clone Tests
# =============================================================================


class TestCloneDashboard:
    """Tests for cloning dashboards."""

    def test_clone_dashboard_success(self, client, mock_dashboard):
        """Test cloning a dashboard succeeds."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            cloned = Dashboard(
                dashboard_id="dash-002",
                user_id="user-123",
                name="Test Dashboard (Copy)",
                description="A test dashboard",
                layout=mock_dashboard.layout,
                widgets=mock_dashboard.widgets,
                is_default=False,
                version=1,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            mock_service = MagicMock()
            mock_service.clone_dashboard.return_value = cloned
            mock_get.return_value = mock_service

            response = client.post("/api/v1/dashboards/dash-001/clone")

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["dashboard_id"] == "dash-002"
            assert "Copy" in data["name"]

    def test_clone_dashboard_with_name(self, client, mock_dashboard):
        """Test cloning a dashboard with custom name."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            cloned = Dashboard(
                dashboard_id="dash-002",
                user_id="user-123",
                name="My Cloned Dashboard",
                description="A test dashboard",
                layout=mock_dashboard.layout,
                widgets=mock_dashboard.widgets,
                is_default=False,
                version=1,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            mock_service = MagicMock()
            mock_service.clone_dashboard.return_value = cloned
            mock_get.return_value = mock_service

            response = client.post(
                "/api/v1/dashboards/dash-001/clone",
                json={"name": "My Cloned Dashboard"},
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "My Cloned Dashboard"

    def test_clone_dashboard_not_found(self, client):
        """Test cloning non-existent dashboard returns 404."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.clone_dashboard.side_effect = DashboardNotFoundError(
                "dash-999"
            )
            mock_get.return_value = mock_service

            response = client.post("/api/v1/dashboards/dash-999/clone")

            assert response.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# Share Tests
# =============================================================================


class TestShareDashboard:
    """Tests for sharing dashboards."""

    def test_share_dashboard_success(self, client, mock_share):
        """Test sharing a dashboard succeeds."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.share_dashboard.return_value = mock_share
            mock_get.return_value = mock_service

            response = client.post(
                "/api/v1/dashboards/dash-001/share",
                json={"user_id": "user-456", "permission": "view"},
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["shared_with_user_id"] == "user-456"
            assert data["permission"] == "view"

    def test_share_dashboard_edit_permission(self, client):
        """Test sharing with edit permission."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            share = ShareRecord(
                dashboard_id="dash-001",
                shared_with_user_id="user-456",
                permission=SharePermission.EDIT,
                shared_by="user-123",
                shared_at=datetime.now(),
            )
            mock_service = MagicMock()
            mock_service.share_dashboard.return_value = share
            mock_get.return_value = mock_service

            response = client.post(
                "/api/v1/dashboards/dash-001/share",
                json={"user_id": "user-456", "permission": "edit"},
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["permission"] == "edit"

    def test_share_dashboard_missing_target(self, client):
        """Test sharing without user_id or org_id returns 400."""
        response = client.post(
            "/api/v1/dashboards/dash-001/share",
            json={"permission": "view"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_share_dashboard_not_owner(self, client):
        """Test sharing dashboard you don't own returns 403."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.share_dashboard.side_effect = DashboardAccessDeniedError(
                "dash-001", "user-123"
            )
            mock_get.return_value = mock_service

            response = client.post(
                "/api/v1/dashboards/dash-001/share",
                json={"user_id": "user-456", "permission": "view"},
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN


class TestListShares:
    """Tests for listing dashboard shares."""

    def test_list_shares_success(self, client, mock_share):
        """Test listing shares returns all share records."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.list_shares.return_value = [mock_share]
            mock_get.return_value = mock_service

            response = client.get("/api/v1/dashboards/dash-001/shares")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 1
            assert len(data["shares"]) == 1

    def test_list_shares_empty(self, client):
        """Test listing shares when none exist."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.list_shares.return_value = []
            mock_get.return_value = mock_service

            response = client.get("/api/v1/dashboards/dash-001/shares")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 0


class TestRevokeShare:
    """Tests for revoking dashboard shares."""

    def test_revoke_share_success(self, client):
        """Test revoking a share succeeds."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.revoke_share.return_value = None
            mock_get.return_value = mock_service

            response = client.delete("/api/v1/dashboards/dash-001/shares/user-456")

            assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_revoke_share_not_found(self, client):
        """Test revoking non-existent share returns 404."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.revoke_share.side_effect = ShareNotFoundError(
                "dash-001", "user-999"
            )
            mock_get.return_value = mock_service

            response = client.delete("/api/v1/dashboards/dash-001/shares/user-999")

            assert response.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# Template Tests
# =============================================================================


class TestTemplates:
    """Tests for dashboard templates."""

    def test_list_templates(self, client):
        """Test listing available templates."""
        response = client.get("/api/v1/dashboards/templates")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "templates" in data
        assert len(data["templates"]) == 5  # 5 role-based templates

    def test_templates_have_required_fields(self, client):
        """Test templates have all required fields."""
        response = client.get("/api/v1/dashboards/templates")

        data = response.json()
        for template in data["templates"]:
            assert "id" in template
            assert "name" in template
            assert "description" in template
            assert "role" in template
            assert "widget_count" in template


class TestRoleDefaults:
    """Tests for role-based default dashboards."""

    def test_get_role_default_success(self, client, mock_dashboard):
        """Test getting role default dashboard."""
        with patch("src.api.dashboard_endpoints.get_dashboard_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_role_default.return_value = mock_dashboard
            mock_get.return_value = mock_service

            response = client.get("/api/v1/dashboards/defaults/security-engineer")

            assert response.status_code == status.HTTP_200_OK

    def test_get_role_default_invalid_role(self, client):
        """Test getting default for invalid role returns 400."""
        response = client.get("/api/v1/dashboards/defaults/invalid-role")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# Widget Catalog Tests
# =============================================================================


class TestWidgetCatalog:
    """Tests for widget catalog endpoint."""

    def test_get_widget_catalog(self, client):
        """Test getting the full widget catalog."""
        response = client.get("/api/v1/widgets/catalog")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "widgets" in data
        assert "categories" in data
        assert len(data["widgets"]) > 0
        assert (
            len(data["categories"]) == 6
        )  # 6 categories (incl. vulnerability_scanner)

    def test_get_widget_catalog_by_category(self, client):
        """Test filtering widgets by category."""
        response = client.get("/api/v1/widgets/catalog?category=security")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for widget in data["widgets"]:
            assert widget["category"] == "security"

    def test_get_widget_catalog_invalid_category(self, client):
        """Test filtering by invalid category returns 400."""
        response = client.get("/api/v1/widgets/catalog?category=invalid")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# Custom Widget Tests (ADR-064 Phase 3)
# =============================================================================


@pytest.fixture
def mock_custom_widget():
    """Create a mock custom widget."""
    from src.services.dashboard import (
        CustomWidget,
        DataSourceType,
        QueryDefinition,
        QueryType,
    )

    return CustomWidget(
        widget_id="cw-test001",
        user_id="user-123",
        name="Critical Vulnerabilities",
        description="Count of critical vulnerabilities",
        widget_type=WidgetType.METRIC,
        category=WidgetCategory.SECURITY,
        query=QueryDefinition(
            query_type=QueryType.METRIC,
            data_source=DataSourceType.SECURITY_API,
            endpoint="security/vulnerabilities",
            time_range="24h",
        ),
        display_config={"color": "red"},
        refresh_seconds=60,
        is_published=False,
        version=1,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def mock_query_result():
    """Create a mock query result."""
    from src.services.dashboard import QueryResult

    return QueryResult(
        success=True,
        data={"value": 42, "trend": 5.2},
        error=None,
        execution_time_ms=15,
        cached=False,
    )


class TestListCustomWidgets:
    """Tests for listing custom widgets."""

    def test_list_custom_widgets_success(self, client, mock_custom_widget):
        """Test listing custom widgets returns user's widgets."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.list_custom_widgets.return_value = [mock_custom_widget]
            mock_get.return_value = mock_service

            response = client.get("/api/v1/widgets/custom")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 1
            assert len(data["widgets"]) == 1
            assert data["widgets"][0]["widget_id"] == "cw-test001"

    def test_list_custom_widgets_empty(self, client):
        """Test listing custom widgets when none exist."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.list_custom_widgets.return_value = []
            mock_get.return_value = mock_service

            response = client.get("/api/v1/widgets/custom")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 0
            assert data["widgets"] == []

    def test_list_custom_widgets_exclude_published(self, client, mock_custom_widget):
        """Test listing custom widgets with include_published=false."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.list_custom_widgets.return_value = [mock_custom_widget]
            mock_get.return_value = mock_service

            response = client.get("/api/v1/widgets/custom?include_published=false")

            assert response.status_code == status.HTTP_200_OK
            mock_service.list_custom_widgets.assert_called_once_with(
                user_id="user-123",
                include_published=False,
            )


class TestCreateCustomWidget:
    """Tests for creating custom widgets."""

    def test_create_custom_widget_success(self, client, mock_custom_widget):
        """Test creating a custom widget succeeds."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.create_custom_widget.return_value = mock_custom_widget
            mock_get.return_value = mock_service

            response = client.post(
                "/api/v1/widgets/custom",
                json={
                    "name": "Critical Vulnerabilities",
                    "widget_type": "metric",
                    "category": "security",
                    "query": {
                        "query_type": "metric",
                        "data_source": "security_api",
                        "endpoint": "security/vulnerabilities",
                        "time_range": "24h",
                    },
                },
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Critical Vulnerabilities"
            assert data["widget_type"] == "metric"

    def test_create_custom_widget_limit_exceeded(self, client):
        """Test creating widget fails when limit exceeded."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.create_custom_widget.side_effect = ValueError(
                "Maximum 25 custom widgets per user"
            )
            mock_get.return_value = mock_service

            response = client.post(
                "/api/v1/widgets/custom",
                json={
                    "name": "Test Widget",
                    "widget_type": "metric",
                    "query": {
                        "query_type": "metric",
                        "data_source": "security_api",
                        "endpoint": "security/vulnerabilities",
                        "time_range": "24h",
                    },
                },
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestGetCustomWidget:
    """Tests for getting a single custom widget."""

    def test_get_custom_widget_success(self, client, mock_custom_widget):
        """Test getting a custom widget by ID."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_custom_widget.return_value = mock_custom_widget
            mock_get.return_value = mock_service

            response = client.get("/api/v1/widgets/custom/cw-test001")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["widget_id"] == "cw-test001"
            assert data["name"] == "Critical Vulnerabilities"

    def test_get_custom_widget_not_found(self, client):
        """Test getting non-existent widget returns 404."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_custom_widget.side_effect = KeyError("Widget not found")
            mock_get.return_value = mock_service

            response = client.get("/api/v1/widgets/custom/cw-nonexistent")

            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_custom_widget_access_denied(self, client):
        """Test getting widget without access returns 403."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_custom_widget.side_effect = PermissionError(
                "Access denied"
            )
            mock_get.return_value = mock_service

            response = client.get("/api/v1/widgets/custom/cw-private")

            assert response.status_code == status.HTTP_403_FORBIDDEN


class TestUpdateCustomWidget:
    """Tests for updating custom widgets."""

    def test_update_custom_widget_success(self, client, mock_custom_widget):
        """Test updating a custom widget succeeds."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.update_custom_widget.return_value = mock_custom_widget
            mock_get.return_value = mock_service

            response = client.put(
                "/api/v1/widgets/custom/cw-test001",
                json={"name": "Updated Widget Name"},
            )

            assert response.status_code == status.HTTP_200_OK

    def test_update_custom_widget_not_found(self, client):
        """Test updating non-existent widget returns 404."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.update_custom_widget.side_effect = KeyError("Widget not found")
            mock_get.return_value = mock_service

            response = client.put(
                "/api/v1/widgets/custom/cw-nonexistent",
                json={"name": "Updated"},
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_custom_widget_not_owner(self, client):
        """Test updating widget by non-owner returns 403."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.update_custom_widget.side_effect = PermissionError(
                "Only owner can update"
            )
            mock_get.return_value = mock_service

            response = client.put(
                "/api/v1/widgets/custom/cw-other",
                json={"name": "Updated"},
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN


class TestDeleteCustomWidget:
    """Tests for deleting custom widgets."""

    def test_delete_custom_widget_success(self, client):
        """Test deleting a custom widget succeeds."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.delete_custom_widget.return_value = None
            mock_get.return_value = mock_service

            response = client.delete("/api/v1/widgets/custom/cw-test001")

            assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_custom_widget_not_found(self, client):
        """Test deleting non-existent widget returns 404."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.delete_custom_widget.side_effect = KeyError("Widget not found")
            mock_get.return_value = mock_service

            response = client.delete("/api/v1/widgets/custom/cw-nonexistent")

            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_custom_widget_not_owner(self, client):
        """Test deleting widget by non-owner returns 403."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.delete_custom_widget.side_effect = PermissionError(
                "Only owner can delete"
            )
            mock_get.return_value = mock_service

            response = client.delete("/api/v1/widgets/custom/cw-other")

            assert response.status_code == status.HTTP_403_FORBIDDEN


class TestExecuteCustomWidgetQuery:
    """Tests for executing custom widget queries."""

    def test_execute_query_success(self, client, mock_query_result):
        """Test executing a widget query returns results."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.execute_query.return_value = mock_query_result
            mock_get.return_value = mock_service

            response = client.post("/api/v1/widgets/custom/cw-test001/execute")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["data"]["value"] == 42
            assert data["execution_time_ms"] == 15

    def test_execute_query_widget_not_found(self, client):
        """Test executing query on non-existent widget returns 404."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.execute_query.side_effect = KeyError("Widget not found")
            mock_get.return_value = mock_service

            response = client.post("/api/v1/widgets/custom/cw-nonexistent/execute")

            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_execute_query_access_denied(self, client):
        """Test executing query without access returns 403."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.execute_query.side_effect = PermissionError("Access denied")
            mock_get.return_value = mock_service

            response = client.post("/api/v1/widgets/custom/cw-private/execute")

            assert response.status_code == status.HTTP_403_FORBIDDEN


class TestPreviewQuery:
    """Tests for query preview."""

    def test_preview_query_success(self, client, mock_query_result):
        """Test preview query returns sample data."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.preview_query.return_value = mock_query_result
            mock_get.return_value = mock_service

            response = client.post(
                "/api/v1/widgets/custom/preview",
                json={
                    "query_type": "metric",
                    "data_source": "security_api",
                    "endpoint": "security/vulnerabilities",
                    "time_range": "24h",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True

    def test_preview_query_invalid_endpoint(self, client):
        """Test preview query with invalid endpoint returns 400."""
        with patch("src.api.dashboard_endpoints.get_custom_widget_service") as mock_get:
            mock_service = MagicMock()
            mock_service.preview_query.side_effect = ValueError(
                "Endpoint not allowed for security_api"
            )
            mock_get.return_value = mock_service

            response = client.post(
                "/api/v1/widgets/custom/preview",
                json={
                    "query_type": "metric",
                    "data_source": "security_api",
                    "endpoint": "invalid/endpoint",
                    "time_range": "24h",
                },
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestDataSources:
    """Tests for data sources endpoint."""

    def test_list_data_sources(self, client):
        """Test listing data sources returns all sources and endpoints."""
        response = client.get("/api/v1/widgets/custom/data-sources")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data_sources" in data
        assert "query_types" in data
        assert len(data["data_sources"]) == 5  # 5 data source types
        assert len(data["query_types"]) == 4  # 4 query types

    def test_data_sources_have_endpoints(self, client):
        """Test data sources include allowed endpoints."""
        response = client.get("/api/v1/widgets/custom/data-sources")

        data = response.json()
        for source in data["data_sources"]:
            assert "type" in source
            assert "name" in source
            assert "endpoints" in source
            assert len(source["endpoints"]) > 0
