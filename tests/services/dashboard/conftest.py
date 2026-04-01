"""Test fixtures for Dashboard service tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.services.dashboard import (
    Dashboard,
    DashboardCreate,
    DashboardService,
    LayoutConfig,
    LayoutItem,
    SharePermission,
    ShareRecord,
    WidgetConfig,
    WidgetDataSource,
    WidgetType,
)


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table."""
    mock_table = MagicMock()
    mock_table.put_item = MagicMock(return_value={})
    mock_table.get_item = MagicMock(return_value={})
    mock_table.delete_item = MagicMock(return_value={})
    mock_table.query = MagicMock(return_value={"Items": [], "Count": 0})
    mock_table.update_item = MagicMock(return_value={})
    return mock_table


@pytest.fixture
def mock_dynamodb_resource(mock_dynamodb_table):
    """Create a mock DynamoDB resource."""
    mock_resource = MagicMock()
    mock_resource.Table = MagicMock(return_value=mock_dynamodb_table)
    return mock_resource


@pytest.fixture
def dashboard_service(mock_dynamodb_resource):
    """Create a DashboardService with mocked DynamoDB."""
    return DashboardService(
        table_name="test-dashboard-configs",
        dynamodb_client=mock_dynamodb_resource,
        max_dashboards_per_user=10,
    )


@pytest.fixture
def sample_widget_config():
    """Create a sample widget configuration."""
    return WidgetConfig(
        id="widget-test-1",
        type=WidgetType.METRIC,
        title="Test Widget",
        data_source=WidgetDataSource(
            endpoint="test/endpoint",
            refresh_interval_seconds=60,
        ),
        color="aura",
        show_trend=True,
    )


@pytest.fixture
def sample_layout_config():
    """Create a sample layout configuration."""
    return LayoutConfig(
        columns=12,
        row_height=100,
        items=[
            LayoutItem(i="widget-test-1", x=0, y=0, w=3, h=2),
            LayoutItem(i="widget-test-2", x=3, y=0, w=3, h=2),
        ],
    )


@pytest.fixture
def sample_dashboard_create(sample_widget_config, sample_layout_config):
    """Create a sample DashboardCreate request."""
    return DashboardCreate(
        name="Test Dashboard",
        description="A test dashboard",
        layout=sample_layout_config,
        widgets=[sample_widget_config],
        is_default=False,
    )


@pytest.fixture
def sample_dashboard():
    """Create a sample Dashboard object."""
    now = datetime.now(timezone.utc)
    return Dashboard(
        dashboard_id="dash-test-12345678",
        user_id="user-123",
        org_id=None,
        name="Test Dashboard",
        description="A test dashboard",
        layout=LayoutConfig(
            columns=12,
            row_height=100,
            items=[LayoutItem(i="widget-test-1", x=0, y=0, w=3, h=2)],
        ),
        widgets=[
            WidgetConfig(
                id="widget-test-1",
                type=WidgetType.METRIC,
                title="Test Widget",
                data_source=WidgetDataSource(endpoint="test/endpoint"),
            )
        ],
        is_default=False,
        role_default_for=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_share_record():
    """Create a sample ShareRecord."""
    return ShareRecord(
        dashboard_id="dash-test-12345678",
        shared_with_user_id="user-456",
        shared_with_org_id=None,
        permission=SharePermission.VIEW,
        shared_by="user-123",
        shared_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_dynamodb_item():
    """Create a sample DynamoDB item representing a dashboard."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "pk": "USER#user-123",
        "sk": "DASHBOARD#dash-test-12345678",
        "dashboard_id": "dash-test-12345678",
        "user_id": "user-123",
        "name": "Test Dashboard",
        "description": "A test dashboard",
        "layout_json": '{"columns": 12, "row_height": 100, "items": []}',
        "widgets_json": "[]",
        "is_default": False,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
