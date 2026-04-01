"""Tests for Dashboard models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.services.dashboard import (
    DashboardCreate,
    DashboardUpdate,
    LayoutConfig,
    LayoutItem,
    ShareCreate,
    SharePermission,
    UserRole,
    WidgetCategory,
    WidgetConfig,
    WidgetDataSource,
    WidgetType,
)


class TestWidgetDataSource:
    """Tests for WidgetDataSource model."""

    def test_valid_data_source(self):
        """Test valid data source creation."""
        ds = WidgetDataSource(
            endpoint="security/vulnerabilities/open",
            refresh_interval_seconds=60,
        )
        assert ds.endpoint == "security/vulnerabilities/open"
        assert ds.refresh_interval_seconds == 60

    def test_invalid_endpoint_format(self):
        """Test that invalid endpoint format raises error."""
        with pytest.raises(ValidationError) as exc_info:
            WidgetDataSource(
                endpoint="invalid endpoint with spaces",
                refresh_interval_seconds=60,
            )
        assert "endpoint" in str(exc_info.value)

    def test_invalid_endpoint_injection(self):
        """Test that endpoint with special characters is rejected."""
        with pytest.raises(ValidationError):
            WidgetDataSource(
                endpoint="security/vuln?id=1;DROP TABLE",
                refresh_interval_seconds=60,
            )

    def test_refresh_interval_bounds(self):
        """Test refresh interval validation bounds."""
        # Too low
        with pytest.raises(ValidationError):
            WidgetDataSource(endpoint="test", refresh_interval_seconds=5)

        # Too high
        with pytest.raises(ValidationError):
            WidgetDataSource(endpoint="test", refresh_interval_seconds=7200)

        # Valid bounds
        ds_min = WidgetDataSource(endpoint="test", refresh_interval_seconds=10)
        assert ds_min.refresh_interval_seconds == 10

        ds_max = WidgetDataSource(endpoint="test", refresh_interval_seconds=3600)
        assert ds_max.refresh_interval_seconds == 3600


class TestWidgetConfig:
    """Tests for WidgetConfig model."""

    def test_valid_widget_config(self, sample_widget_config):
        """Test valid widget configuration."""
        assert sample_widget_config.id == "widget-test-1"
        assert sample_widget_config.type == WidgetType.METRIC
        assert sample_widget_config.title == "Test Widget"
        assert sample_widget_config.color == "aura"

    def test_invalid_widget_id_format(self):
        """Test that invalid widget ID format raises error."""
        with pytest.raises(ValidationError) as exc_info:
            WidgetConfig(
                id="invalid_id",  # Missing 'widget-' prefix
                type=WidgetType.METRIC,
                title="Test",
                data_source=WidgetDataSource(endpoint="test"),
            )
        assert "Widget ID must start with 'widget-'" in str(exc_info.value)

    def test_invalid_color(self):
        """Test that invalid color raises error."""
        with pytest.raises(ValidationError):
            WidgetConfig(
                id="widget-test",
                type=WidgetType.METRIC,
                title="Test",
                data_source=WidgetDataSource(endpoint="test"),
                color="invalid-color",
            )

    def test_title_length_limits(self):
        """Test title length validation."""
        # Empty title
        with pytest.raises(ValidationError):
            WidgetConfig(
                id="widget-test",
                type=WidgetType.METRIC,
                title="",
                data_source=WidgetDataSource(endpoint="test"),
            )

        # Title too long
        with pytest.raises(ValidationError):
            WidgetConfig(
                id="widget-test",
                type=WidgetType.METRIC,
                title="a" * 101,
                data_source=WidgetDataSource(endpoint="test"),
            )


class TestLayoutItem:
    """Tests for LayoutItem model."""

    def test_valid_layout_item(self):
        """Test valid layout item creation."""
        item = LayoutItem(i="widget-test", x=0, y=0, w=3, h=2)
        assert item.i == "widget-test"
        assert item.x == 0
        assert item.w == 3

    def test_position_bounds(self):
        """Test position validation bounds."""
        # X out of bounds (0-11)
        with pytest.raises(ValidationError):
            LayoutItem(i="widget-test", x=12, y=0, w=1, h=1)

        # Negative x
        with pytest.raises(ValidationError):
            LayoutItem(i="widget-test", x=-1, y=0, w=1, h=1)

    def test_size_bounds(self):
        """Test size validation bounds."""
        # Width too large (max 12)
        with pytest.raises(ValidationError):
            LayoutItem(i="widget-test", x=0, y=0, w=13, h=1)

        # Width too small (min 1)
        with pytest.raises(ValidationError):
            LayoutItem(i="widget-test", x=0, y=0, w=0, h=1)

        # Height too large (max 10)
        with pytest.raises(ValidationError):
            LayoutItem(i="widget-test", x=0, y=0, w=1, h=11)


class TestLayoutConfig:
    """Tests for LayoutConfig model."""

    def test_default_values(self):
        """Test layout config default values."""
        layout = LayoutConfig()
        assert layout.columns == 12
        assert layout.row_height == 100
        assert layout.items == []

    def test_custom_values(self, sample_layout_config):
        """Test layout config with custom values."""
        assert sample_layout_config.columns == 12
        assert len(sample_layout_config.items) == 2

    def test_column_bounds(self):
        """Test column count bounds."""
        with pytest.raises(ValidationError):
            LayoutConfig(columns=0)

        with pytest.raises(ValidationError):
            LayoutConfig(columns=25)


class TestDashboardCreate:
    """Tests for DashboardCreate model."""

    def test_valid_dashboard_create(self, sample_dashboard_create):
        """Test valid dashboard creation request."""
        assert sample_dashboard_create.name == "Test Dashboard"
        assert sample_dashboard_create.description == "A test dashboard"
        assert len(sample_dashboard_create.widgets) == 1

    def test_name_validation(self):
        """Test dashboard name validation."""
        # Empty name
        with pytest.raises(ValidationError):
            DashboardCreate(name="")

        # Name too long
        with pytest.raises(ValidationError):
            DashboardCreate(name="a" * 101)

    def test_description_validation(self):
        """Test dashboard description validation."""
        # Description too long
        with pytest.raises(ValidationError):
            DashboardCreate(name="Test", description="a" * 501)


class TestDashboardUpdate:
    """Tests for DashboardUpdate model."""

    def test_partial_update(self):
        """Test partial update with only some fields."""
        update = DashboardUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.description is None
        assert update.layout is None

    def test_full_update(self, sample_layout_config, sample_widget_config):
        """Test full update with all fields."""
        update = DashboardUpdate(
            name="Updated Name",
            description="Updated description",
            layout=sample_layout_config,
            widgets=[sample_widget_config],
            is_default=True,
        )
        assert update.name == "Updated Name"
        assert update.is_default is True


class TestDashboard:
    """Tests for Dashboard model."""

    def test_valid_dashboard(self, sample_dashboard):
        """Test valid dashboard model."""
        assert sample_dashboard.dashboard_id == "dash-test-12345678"
        assert sample_dashboard.user_id == "user-123"
        assert sample_dashboard.version == 1

    def test_json_serialization(self, sample_dashboard):
        """Test dashboard JSON serialization."""
        json_data = sample_dashboard.model_dump_json()
        assert "dash-test-12345678" in json_data
        assert "user-123" in json_data


class TestShareCreate:
    """Tests for ShareCreate model."""

    def test_user_share(self):
        """Test creating a user share."""
        share = ShareCreate(user_id="user-456", permission=SharePermission.VIEW)
        assert share.user_id == "user-456"
        assert share.org_id is None

    def test_org_share(self):
        """Test creating an org share."""
        share = ShareCreate(org_id="org-789", permission=SharePermission.VIEW)
        assert share.org_id == "org-789"
        assert share.user_id is None

    def test_share_requires_one_target(self):
        """Test that exactly one of user_id or org_id is required."""
        # Neither provided
        with pytest.raises(ValidationError) as exc_info:
            ShareCreate(permission=SharePermission.VIEW)
        assert "Exactly one" in str(exc_info.value)

        # Both provided
        with pytest.raises(ValidationError) as exc_info:
            ShareCreate(
                user_id="user-123",
                org_id="org-456",
                permission=SharePermission.VIEW,
            )
        assert "Exactly one" in str(exc_info.value)


class TestUserRole:
    """Tests for UserRole enum."""

    def test_all_roles(self):
        """Test all role values."""
        assert UserRole.SECURITY_ENGINEER.value == "security-engineer"
        assert UserRole.DEVOPS.value == "devops"
        assert UserRole.ENGINEERING_MANAGER.value == "engineering-manager"
        assert UserRole.EXECUTIVE.value == "executive"
        assert UserRole.SUPERUSER.value == "superuser"


class TestWidgetType:
    """Tests for WidgetType enum."""

    def test_all_widget_types(self):
        """Test all widget type values."""
        assert WidgetType.METRIC.value == "metric"
        assert WidgetType.CHART_LINE.value == "chart_line"
        assert WidgetType.CHART_BAR.value == "chart_bar"
        assert WidgetType.TABLE.value == "table"
        assert WidgetType.STATUS_GRID.value == "status_grid"
        assert WidgetType.ACTIVITY_FEED.value == "activity_feed"
        assert WidgetType.GAUGE.value == "gauge"
        assert WidgetType.PROGRESS.value == "progress"


class TestWidgetCategory:
    """Tests for WidgetCategory enum."""

    def test_all_categories(self):
        """Test all category values."""
        assert WidgetCategory.SECURITY.value == "security"
        assert WidgetCategory.OPERATIONS.value == "operations"
        assert WidgetCategory.ANALYTICS.value == "analytics"
        assert WidgetCategory.COMPLIANCE.value == "compliance"
        assert WidgetCategory.COST.value == "cost"
