"""Dashboard Customization Service package.

Provides customizable dashboard widgets with DynamoDB persistence,
role-based defaults, and sharing capabilities per ADR-064.

Example usage:
    from services.dashboard import DashboardService, DashboardCreate

    service = DashboardService()
    dashboard = service.create_dashboard(
        user_id="user123",
        dashboard_data=DashboardCreate(
            name="My Dashboard",
            description="Custom security view",
        ),
    )
"""

from .custom_widget_service import (
    CustomWidget,
    CustomWidgetCreate,
    CustomWidgetService,
    CustomWidgetUpdate,
    DataSourceType,
    QueryDefinition,
    QueryResult,
    QueryType,
    get_custom_widget_service,
)
from .dashboard_service import DashboardService, get_dashboard_service
from .embed_service import (
    DashboardEmbedService,
    EmbedDashboardData,
    EmbedMode,
    EmbedTheme,
    EmbedToken,
    EmbedTokenCreate,
    EmbedTokenUpdate,
    EmbedValidationResult,
    get_embed_service,
)
from .exceptions import (
    DashboardAccessDeniedError,
    DashboardConflictError,
    DashboardException,
    DashboardLimitExceededError,
    DashboardNotFoundError,
    DashboardValidationError,
    DynamoDBError,
    RoleDefaultNotFoundError,
    ShareAlreadyExistsError,
    ShareNotFoundError,
    WidgetNotFoundError,
)
from .models import (
    ROLE_DEFAULTS,
    Dashboard,
    DashboardCreate,
    DashboardListResponse,
    DashboardResponse,
    DashboardSummary,
    DashboardUpdate,
    LayoutConfig,
    LayoutItem,
    ShareCreate,
    ShareListResponse,
    SharePermission,
    ShareRecord,
    SortOrder,
    UserRole,
    WidgetCatalog,
    WidgetCategory,
    WidgetConfig,
    WidgetDataSource,
    WidgetDefinition,
    WidgetType,
)
from .scheduled_report_service import (
    DayOfWeek,
    ReportDeliveryResult,
    ReportFormat,
    ScheduleConfig,
    ScheduledReport,
    ScheduledReportCreate,
    ScheduledReportService,
    ScheduledReportUpdate,
    ScheduleFrequency,
    get_scheduled_report_service,
)
from .widget_catalog import (
    get_catalog,
    get_widget_by_type,
    get_widget_catalog,
    get_widgets_by_category,
)

__all__ = [
    # Service
    "DashboardService",
    "get_dashboard_service",
    # Models
    "Dashboard",
    "DashboardCreate",
    "DashboardListResponse",
    "DashboardResponse",
    "DashboardSummary",
    "DashboardUpdate",
    "LayoutConfig",
    "LayoutItem",
    "ShareCreate",
    "ShareListResponse",
    "SharePermission",
    "ShareRecord",
    "SortOrder",
    "UserRole",
    "WidgetCategory",
    "WidgetCatalog",
    "WidgetConfig",
    "WidgetDataSource",
    "WidgetDefinition",
    "WidgetType",
    # Role defaults
    "ROLE_DEFAULTS",
    # Exceptions
    "DashboardException",
    "DashboardNotFoundError",
    "DashboardAccessDeniedError",
    "DashboardConflictError",
    "DashboardLimitExceededError",
    "DashboardValidationError",
    "ShareNotFoundError",
    "ShareAlreadyExistsError",
    "RoleDefaultNotFoundError",
    "WidgetNotFoundError",
    "DynamoDBError",
    # Widget catalog
    "get_catalog",
    "get_widget_catalog",
    "get_widget_by_type",
    "get_widgets_by_category",
    # Custom widget service
    "CustomWidget",
    "CustomWidgetCreate",
    "CustomWidgetService",
    "CustomWidgetUpdate",
    "DataSourceType",
    "QueryDefinition",
    "QueryResult",
    "QueryType",
    "get_custom_widget_service",
    # Scheduled report service
    "DayOfWeek",
    "ReportDeliveryResult",
    "ReportFormat",
    "ScheduleConfig",
    "ScheduledReport",
    "ScheduledReportCreate",
    "ScheduledReportService",
    "ScheduledReportUpdate",
    "ScheduleFrequency",
    "get_scheduled_report_service",
    # Embed service
    "DashboardEmbedService",
    "EmbedDashboardData",
    "EmbedMode",
    "EmbedTheme",
    "EmbedToken",
    "EmbedTokenCreate",
    "EmbedTokenUpdate",
    "EmbedValidationResult",
    "get_embed_service",
]
