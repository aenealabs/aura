"""Pydantic models for Dashboard Customization service.

Implements strictly-typed dashboard configurations per ADR-064 to support
customizable widgets, role-based defaults, and audit compliance.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class UserRole(str, Enum):
    """User roles for role-based dashboard defaults."""

    SECURITY_ENGINEER = "security-engineer"
    DEVOPS = "devops"
    ENGINEERING_MANAGER = "engineering-manager"
    EXECUTIVE = "executive"
    SUPERUSER = "superuser"


class WidgetType(str, Enum):
    """Types of widgets available in the widget library."""

    METRIC = "metric"
    CHART_LINE = "chart_line"
    CHART_BAR = "chart_bar"
    CHART_DONUT = "chart_donut"
    TABLE = "table"
    STATUS_GRID = "status_grid"
    ACTIVITY_FEED = "activity_feed"
    GAUGE = "gauge"
    PROGRESS = "progress"


class WidgetCategory(str, Enum):
    """Categories for organizing widgets in the library."""

    SECURITY = "security"
    OPERATIONS = "operations"
    ANALYTICS = "analytics"
    COMPLIANCE = "compliance"
    COST = "cost"
    VULNERABILITY_SCANNER = "vulnerability_scanner"


class SharePermission(str, Enum):
    """Permission levels for shared dashboards."""

    VIEW = "view"
    EDIT = "edit"


class DashboardSortField(str, Enum):
    """Fields available for sorting dashboard lists."""

    NAME = "name"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class SortOrder(str, Enum):
    """Sort order direction."""

    ASC = "asc"
    DESC = "desc"


# =============================================================================
# Widget Configuration Models
# =============================================================================


class WidgetDataSource(BaseModel):
    """Configuration for widget data source."""

    endpoint: str = Field(..., description="API endpoint for widget data")
    refresh_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Auto-refresh interval in seconds",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Query parameters for the endpoint",
    )

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """Validate endpoint format to prevent injection."""
        # Allow only alphanumeric, slashes, hyphens, underscores
        if not re.match(r"^[a-zA-Z0-9/_-]+$", v):
            raise ValueError("Invalid endpoint format")
        return v


class WidgetConfig(BaseModel):
    """Configuration for a single widget instance."""

    id: str = Field(..., description="Unique widget instance ID")
    type: WidgetType = Field(..., description="Widget type from library")
    title: str = Field(..., min_length=1, max_length=100, description="Widget title")
    data_source: WidgetDataSource = Field(..., description="Data source configuration")
    color: str = Field(
        default="aura",
        pattern=r"^(aura|olive|critical|warning|surface)$",
        description="Widget color theme",
    )
    show_sparkline: bool = Field(default=False, description="Show sparkline chart")
    show_trend: bool = Field(default=True, description="Show trend indicator")
    inverse_trend: bool = Field(
        default=False,
        description="Invert trend colors (down is good)",
    )

    @field_validator("id")
    @classmethod
    def validate_widget_id(cls, v: str) -> str:
        """Validate widget ID format."""
        if not re.match(r"^widget-[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Widget ID must start with 'widget-' and contain only alphanumeric, hyphens, underscores"
            )
        return v


class LayoutItem(BaseModel):
    """Position and size of a widget in the grid layout."""

    i: str = Field(..., description="Widget ID (matches WidgetConfig.id)")
    x: int = Field(..., ge=0, le=11, description="X position in grid (0-11)")
    y: int = Field(..., ge=0, description="Y position in grid")
    w: int = Field(..., ge=1, le=12, description="Width in grid units (1-12)")
    h: int = Field(..., ge=1, le=10, description="Height in grid units (1-10)")
    min_w: int = Field(default=1, ge=1, description="Minimum width")
    min_h: int = Field(default=1, ge=1, description="Minimum height")
    static: bool = Field(default=False, description="Prevent dragging/resizing")


class LayoutConfig(BaseModel):
    """Grid layout configuration for react-grid-layout."""

    columns: int = Field(default=12, ge=1, le=24, description="Number of columns")
    row_height: int = Field(
        default=100, ge=50, le=200, description="Row height in pixels"
    )
    items: list[LayoutItem] = Field(
        default_factory=list, description="Widget positions"
    )


# =============================================================================
# Dashboard Models
# =============================================================================


class DashboardBase(BaseModel):
    """Base fields for dashboard creation and updates."""

    name: str = Field(..., min_length=1, max_length=100, description="Dashboard name")
    description: str = Field(
        default="", max_length=500, description="Dashboard description"
    )


class DashboardCreate(DashboardBase):
    """Request model for creating a new dashboard."""

    layout: LayoutConfig = Field(
        default_factory=LayoutConfig, description="Grid layout"
    )
    widgets: list[WidgetConfig] = Field(
        default_factory=list, description="Widget configurations"
    )
    is_default: bool = Field(
        default=False, description="Set as user's default dashboard"
    )


class DashboardUpdate(BaseModel):
    """Request model for updating an existing dashboard."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    layout: LayoutConfig | None = Field(default=None)
    widgets: list[WidgetConfig] | None = Field(default=None)
    is_default: bool | None = Field(default=None)


class Dashboard(DashboardBase):
    """Full dashboard model with all fields."""

    dashboard_id: str = Field(..., description="Unique dashboard identifier (ULID)")
    user_id: str = Field(..., description="Owner user ID")
    org_id: str | None = Field(
        default=None, description="Organization ID if org-shared"
    )
    layout: LayoutConfig = Field(..., description="Grid layout configuration")
    widgets: list[WidgetConfig] = Field(
        default_factory=list, description="Widget configurations"
    )
    is_default: bool = Field(default=False, description="Is user's default dashboard")
    role_default_for: UserRole | None = Field(
        default=None, description="Role this is a default for"
    )
    version: int = Field(default=1, description="Version for optimistic locking")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic config."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class DashboardSummary(BaseModel):
    """Summary view of a dashboard for list endpoints."""

    dashboard_id: str
    name: str
    description: str
    widget_count: int
    is_default: bool
    role_default_for: UserRole | None
    updated_at: datetime
    shared: bool = Field(default=False, description="Whether dashboard has shares")


# =============================================================================
# Share Models
# =============================================================================


class ShareCreate(BaseModel):
    """Request model for sharing a dashboard."""

    user_id: str | None = Field(default=None, description="User ID to share with")
    org_id: str | None = Field(default=None, description="Org ID for org-wide share")
    permission: SharePermission = Field(
        default=SharePermission.VIEW, description="Permission level"
    )

    @field_validator("user_id", "org_id")
    @classmethod
    def validate_id_format(cls, v: str | None) -> str | None:
        """Validate ID format."""
        if v is not None and not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Invalid ID format")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Validate that exactly one of user_id or org_id is provided."""
        if (self.user_id is None) == (self.org_id is None):
            raise ValueError("Exactly one of user_id or org_id must be provided")


class ShareRecord(BaseModel):
    """Share record for a dashboard."""

    dashboard_id: str
    shared_with_user_id: str | None = None
    shared_with_org_id: str | None = None
    permission: SharePermission
    shared_by: str
    shared_at: datetime


# =============================================================================
# Widget Library Models
# =============================================================================


class WidgetDefinition(BaseModel):
    """Definition of an available widget in the library."""

    widget_type: WidgetType
    category: WidgetCategory
    name: str
    description: str
    default_data_source: str
    default_refresh_seconds: int = 60
    supports_sparkline: bool = False
    supports_trend: bool = True
    min_width: int = 1
    min_height: int = 1
    default_width: int = 1
    default_height: int = 2


class WidgetCatalog(BaseModel):
    """Catalog of all available widgets."""

    widgets: list[WidgetDefinition]
    categories: list[WidgetCategory]


# =============================================================================
# API Response Models
# =============================================================================


class DashboardListResponse(BaseModel):
    """Response model for listing dashboards."""

    dashboards: list[DashboardSummary]
    total: int
    page: int
    page_size: int


class DashboardResponse(BaseModel):
    """Response model for single dashboard operations."""

    dashboard: Dashboard
    message: str | None = None


class ShareListResponse(BaseModel):
    """Response model for listing shares."""

    shares: list[ShareRecord]
    total: int


class CloneResponse(BaseModel):
    """Response model for clone operation."""

    dashboard: Dashboard
    source_dashboard_id: str
    message: str


# =============================================================================
# Role Default Configurations
# =============================================================================


def get_security_engineer_default() -> DashboardCreate:
    """Get default dashboard for Security Engineer role.

    Includes vulnerability scanner widgets (ADR-084) for findings triage,
    scan monitoring, and threat analysis.
    """
    return DashboardCreate(
        name="Security Overview",
        description="Security-focused dashboard for vulnerability management and scanning",
        layout=LayoutConfig(
            columns=12,
            row_height=100,
            items=[
                # Row 0: Scanner approval + active scans + TP rate + alarm status
                LayoutItem(i="widget-scanner-approval", x=0, y=0, w=3, h=2),
                LayoutItem(i="widget-scanner-active-scans", x=3, y=0, w=3, h=3),
                LayoutItem(i="widget-scanner-tp-rate", x=6, y=0, w=3, h=2),
                LayoutItem(i="widget-scanner-alarm-status", x=9, y=0, w=3, h=3),
                # Row 1: Findings by severity + critical findings trend
                LayoutItem(i="widget-scanner-severity", x=0, y=3, w=6, h=3),
                LayoutItem(i="widget-scanner-critical-trend", x=6, y=3, w=6, h=3),
                # Row 2: Recent scan activity + findings by CWE
                LayoutItem(i="widget-scanner-recent-activity", x=0, y=6, w=6, h=3),
                LayoutItem(i="widget-scanner-cwe", x=6, y=6, w=6, h=3),
            ],
        ),
        widgets=[
            WidgetConfig(
                id="widget-scanner-approval",
                type=WidgetType.METRIC,
                title="Findings Requiring Approval",
                data_source=WidgetDataSource(
                    endpoint="scanner/findings/requiring-approval"
                ),
                color="critical",
                show_trend=True,
                inverse_trend=True,
            ),
            WidgetConfig(
                id="widget-scanner-active-scans",
                type=WidgetType.STATUS_GRID,
                title="Active Scans",
                data_source=WidgetDataSource(endpoint="scanner/scans/active"),
                color="aura",
            ),
            WidgetConfig(
                id="widget-scanner-tp-rate",
                type=WidgetType.GAUGE,
                title="True Positive Rate",
                data_source=WidgetDataSource(
                    endpoint="scanner/metrics/true-positive-rate"
                ),
                color="olive",
            ),
            WidgetConfig(
                id="widget-scanner-alarm-status",
                type=WidgetType.STATUS_GRID,
                title="Scanner Alarm Status",
                data_source=WidgetDataSource(endpoint="scanner/alarms/status"),
                color="aura",
            ),
            WidgetConfig(
                id="widget-scanner-severity",
                type=WidgetType.CHART_BAR,
                title="Findings by Severity",
                data_source=WidgetDataSource(endpoint="scanner/findings/by-severity"),
                color="critical",
            ),
            WidgetConfig(
                id="widget-scanner-critical-trend",
                type=WidgetType.CHART_LINE,
                title="Critical Findings Trend",
                data_source=WidgetDataSource(
                    endpoint="scanner/findings/critical-trend"
                ),
                color="critical",
            ),
            WidgetConfig(
                id="widget-scanner-recent-activity",
                type=WidgetType.ACTIVITY_FEED,
                title="Recent Scan Activity",
                data_source=WidgetDataSource(endpoint="scanner/activity/recent"),
                color="aura",
            ),
            WidgetConfig(
                id="widget-scanner-cwe",
                type=WidgetType.CHART_BAR,
                title="Findings by CWE",
                data_source=WidgetDataSource(endpoint="scanner/findings/by-cwe"),
                color="warning",
            ),
        ],
    )


def get_devops_default() -> DashboardCreate:
    """Get default dashboard for DevOps role.

    Includes vulnerability scanner operations widgets (ADR-084) for
    scan performance, resource utilization, and cost monitoring.
    """
    return DashboardCreate(
        name="Operations Overview",
        description="DevOps-focused dashboard with scanner operations",
        layout=LayoutConfig(
            columns=12,
            row_height=100,
            items=[
                # Row 0: Scanner ops metrics
                LayoutItem(i="widget-scanner-active-scans", x=0, y=0, w=3, h=3),
                LayoutItem(i="widget-scanner-utilization", x=3, y=0, w=3, h=2),
                LayoutItem(i="widget-scanner-llm-spend", x=6, y=0, w=3, h=3),
                LayoutItem(i="widget-scanner-alarm-status", x=9, y=0, w=3, h=3),
                # Row 1: Duration analysis
                LayoutItem(i="widget-scanner-stage-duration", x=0, y=3, w=6, h=3),
                LayoutItem(i="widget-scanner-duration-trend", x=6, y=3, w=6, h=3),
            ],
        ),
        widgets=[
            WidgetConfig(
                id="widget-scanner-active-scans",
                type=WidgetType.STATUS_GRID,
                title="Active Scans",
                data_source=WidgetDataSource(endpoint="scanner/scans/active"),
                color="aura",
            ),
            WidgetConfig(
                id="widget-scanner-utilization",
                type=WidgetType.GAUGE,
                title="Concurrent Utilization",
                data_source=WidgetDataSource(
                    endpoint="scanner/metrics/concurrent-utilization"
                ),
                color="aura",
            ),
            WidgetConfig(
                id="widget-scanner-llm-spend",
                type=WidgetType.METRIC,
                title="LLM Token Spend",
                data_source=WidgetDataSource(
                    endpoint="scanner/metrics/llm-token-spend"
                ),
                color="warning",
                show_trend=True,
                inverse_trend=True,
            ),
            WidgetConfig(
                id="widget-scanner-alarm-status",
                type=WidgetType.STATUS_GRID,
                title="Scanner Alarm Status",
                data_source=WidgetDataSource(endpoint="scanner/alarms/status"),
                color="aura",
            ),
            WidgetConfig(
                id="widget-scanner-stage-duration",
                type=WidgetType.CHART_BAR,
                title="Stage Duration Waterfall",
                data_source=WidgetDataSource(endpoint="scanner/metrics/stage-duration"),
                color="aura",
            ),
            WidgetConfig(
                id="widget-scanner-duration-trend",
                type=WidgetType.CHART_LINE,
                title="Scan Duration Trend",
                data_source=WidgetDataSource(endpoint="scanner/metrics/duration-trend"),
                color="aura",
            ),
        ],
    )


def get_executive_default() -> DashboardCreate:
    """Get default dashboard for Executive/CISO role.

    Includes vulnerability scanner headline metrics (ADR-084) for
    risk visibility and LLM cost awareness.
    """
    return DashboardCreate(
        name="Executive Summary",
        description="High-level overview with vulnerability risk metrics",
        layout=LayoutConfig(
            columns=12,
            row_height=100,
            items=[
                LayoutItem(i="widget-risk-posture", x=0, y=0, w=3, h=2),
                LayoutItem(i="widget-scanner-critical-trend", x=3, y=0, w=6, h=3),
                LayoutItem(i="widget-scanner-llm-spend", x=9, y=0, w=3, h=3),
                LayoutItem(i="widget-key-incidents", x=0, y=3, w=12, h=3),
            ],
        ),
        widgets=[
            WidgetConfig(
                id="widget-risk-posture",
                type=WidgetType.GAUGE,
                title="Risk Posture Score",
                data_source=WidgetDataSource(endpoint="security/risk-posture"),
                color="olive",
            ),
            WidgetConfig(
                id="widget-scanner-critical-trend",
                type=WidgetType.CHART_LINE,
                title="Critical Findings Trend",
                data_source=WidgetDataSource(
                    endpoint="scanner/findings/critical-trend"
                ),
                color="critical",
            ),
            WidgetConfig(
                id="widget-scanner-llm-spend",
                type=WidgetType.METRIC,
                title="LLM Token Spend",
                data_source=WidgetDataSource(
                    endpoint="scanner/metrics/llm-token-spend"
                ),
                color="warning",
                show_trend=True,
                inverse_trend=True,
            ),
            WidgetConfig(
                id="widget-key-incidents",
                type=WidgetType.TABLE,
                title="Key Incidents (7 Days)",
                data_source=WidgetDataSource(endpoint="incidents/recent"),
                color="critical",
            ),
        ],
    )


ROLE_DEFAULTS: dict[UserRole, callable] = {
    UserRole.SECURITY_ENGINEER: get_security_engineer_default,
    UserRole.DEVOPS: get_devops_default,
    UserRole.ENGINEERING_MANAGER: get_devops_default,  # Uses DevOps as base
    UserRole.EXECUTIVE: get_executive_default,
    UserRole.SUPERUSER: get_executive_default,  # SuperUser starts with exec view
}
