"""Custom Widget Builder Service.

Enables power users to create custom widgets with user-defined queries.
Implements ADR-064 Phase 3 custom widget builder functionality.

Features:
- Custom query definitions with validation
- Safe query execution against supported data sources
- Widget preview and testing
- User-scoped custom widget storage
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .models import WidgetCategory, WidgetType

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Supported query types for custom widgets."""

    METRIC = "metric"  # Single value with optional trend
    TIME_SERIES = "time_series"  # Time-based data for charts
    TABLE = "table"  # Tabular data
    AGGREGATION = "aggregation"  # Grouped/aggregated data


class DataSourceType(str, Enum):
    """Supported data source types for custom queries."""

    METRICS_API = "metrics_api"  # Internal metrics endpoints
    SECURITY_API = "security_api"  # Security service endpoints
    OPERATIONS_API = "operations_api"  # Operations/agent endpoints
    COMPLIANCE_API = "compliance_api"  # Compliance endpoints
    COST_API = "cost_api"  # Cost management endpoints


# Allowed API endpoints per data source type
ALLOWED_ENDPOINTS: dict[DataSourceType, list[str]] = {
    DataSourceType.METRICS_API: [
        "metrics/custom",
        "metrics/aggregate",
        "metrics/timeseries",
    ],
    DataSourceType.SECURITY_API: [
        "security/vulnerabilities",
        "security/alerts",
        "security/cve",
        "security/risk-posture",
        "security/metrics",
    ],
    DataSourceType.OPERATIONS_API: [
        "agents/health",
        "agents/metrics",
        "environments/status",
        "environments/sandbox",
        "deployments",
        "gpu/jobs",
        "approvals",
    ],
    DataSourceType.COMPLIANCE_API: [
        "compliance/progress",
        "compliance/controls",
        "compliance/findings",
        "incidents",
    ],
    DataSourceType.COST_API: [
        "cost/monthly",
        "cost/trend",
        "cost/breakdown",
        "cost/forecast",
    ],
}


class QueryDefinition(BaseModel):
    """Definition of a custom widget query."""

    query_type: QueryType = Field(..., description="Type of query")
    data_source: DataSourceType = Field(..., description="Data source type")
    endpoint: str = Field(..., description="API endpoint path")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Query parameters"
    )
    filters: list[dict[str, Any]] = Field(
        default_factory=list, description="Filter conditions"
    )
    aggregation: str | None = Field(
        default=None,
        pattern=r"^(count|sum|avg|min|max|percentile)$",
        description="Aggregation function",
    )
    group_by: list[str] = Field(default_factory=list, description="Fields to group by")
    time_range: str = Field(
        default="24h",
        pattern=r"^\d+[mhd]$",
        description="Time range (e.g., 1h, 24h, 7d)",
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Result limit")

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """Validate endpoint format to prevent injection."""
        if not re.match(r"^[a-zA-Z0-9/_-]+$", v):
            raise ValueError("Invalid endpoint format")
        return v

    @field_validator("group_by")
    @classmethod
    def validate_group_by(cls, v: list[str]) -> list[str]:
        """Validate group_by field names."""
        for field in v:
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", field):
                raise ValueError(f"Invalid field name: {field}")
        return v


class CustomWidgetCreate(BaseModel):
    """Request model for creating a custom widget."""

    name: str = Field(..., min_length=1, max_length=100, description="Widget name")
    description: str = Field(
        default="", max_length=500, description="Widget description"
    )
    widget_type: WidgetType = Field(..., description="Widget display type")
    category: WidgetCategory = Field(
        default=WidgetCategory.ANALYTICS, description="Widget category"
    )
    query: QueryDefinition = Field(..., description="Query definition")
    display_config: dict[str, Any] = Field(
        default_factory=dict, description="Display configuration"
    )
    refresh_seconds: int = Field(
        default=60, ge=10, le=3600, description="Refresh interval"
    )


class CustomWidgetUpdate(BaseModel):
    """Request model for updating a custom widget."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    widget_type: WidgetType | None = None
    category: WidgetCategory | None = None
    query: QueryDefinition | None = None
    display_config: dict[str, Any] | None = None
    refresh_seconds: int | None = Field(default=None, ge=10, le=3600)
    is_published: bool | None = None


class CustomWidget(BaseModel):
    """Full custom widget model."""

    widget_id: str = Field(..., description="Unique widget identifier")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Widget name")
    description: str = Field(default="", description="Widget description")
    widget_type: WidgetType = Field(..., description="Widget display type")
    category: WidgetCategory = Field(..., description="Widget category")
    query: QueryDefinition = Field(..., description="Query definition")
    display_config: dict[str, Any] = Field(
        default_factory=dict, description="Display configuration"
    )
    refresh_seconds: int = Field(default=60, description="Refresh interval")
    is_published: bool = Field(
        default=False, description="Whether widget is published to library"
    )
    version: int = Field(default=1, description="Version for optimistic locking")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic config."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class QueryResult(BaseModel):
    """Result of executing a custom widget query."""

    success: bool = Field(..., description="Whether query succeeded")
    data: Any = Field(default=None, description="Query result data")
    error: str | None = Field(default=None, description="Error message if failed")
    execution_time_ms: int = Field(default=0, description="Query execution time")
    cached: bool = Field(default=False, description="Whether result was cached")


class CustomWidgetService:
    """Service for managing custom widgets.

    Provides CRUD operations, query validation, and safe query execution
    for user-defined custom widgets.
    """

    # Maximum custom widgets per user
    MAX_WIDGETS_PER_USER = 25

    def __init__(self) -> None:
        """Initialize the custom widget service."""
        self._widgets: dict[str, CustomWidget] = {}
        self._user_widgets: dict[str, list[str]] = {}

    def create_custom_widget(
        self,
        user_id: str,
        widget_data: CustomWidgetCreate,
    ) -> CustomWidget:
        """Create a new custom widget.

        Args:
            user_id: Owner user ID
            widget_data: Widget creation data

        Returns:
            Created CustomWidget

        Raises:
            ValueError: If user has reached widget limit or query is invalid
        """
        # Check user limit
        user_widgets = self._user_widgets.get(user_id, [])
        if len(user_widgets) >= self.MAX_WIDGETS_PER_USER:
            raise ValueError(
                f"Maximum {self.MAX_WIDGETS_PER_USER} custom widgets per user"
            )

        # Validate query
        self._validate_query(widget_data.query)

        # Generate widget ID
        widget_id = f"cw-{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        widget = CustomWidget(
            widget_id=widget_id,
            user_id=user_id,
            name=widget_data.name,
            description=widget_data.description,
            widget_type=widget_data.widget_type,
            category=widget_data.category,
            query=widget_data.query,
            display_config=widget_data.display_config,
            refresh_seconds=widget_data.refresh_seconds,
            is_published=False,
            version=1,
            created_at=now,
            updated_at=now,
        )

        # Store widget
        self._widgets[widget_id] = widget
        if user_id not in self._user_widgets:
            self._user_widgets[user_id] = []
        self._user_widgets[user_id].append(widget_id)

        logger.info(f"Custom widget created: {widget_id} by user {user_id}")
        return widget

    def get_custom_widget(
        self,
        widget_id: str,
        user_id: str,
    ) -> CustomWidget:
        """Get a custom widget by ID.

        Args:
            widget_id: Widget ID
            user_id: Requesting user ID

        Returns:
            CustomWidget

        Raises:
            KeyError: If widget not found
            PermissionError: If user doesn't have access
        """
        widget = self._widgets.get(widget_id)
        if not widget:
            raise KeyError(f"Widget {widget_id} not found")

        # Check access: owner or published
        if widget.user_id != user_id and not widget.is_published:
            raise PermissionError("Access denied to this widget")

        return widget

    def update_custom_widget(
        self,
        widget_id: str,
        user_id: str,
        updates: CustomWidgetUpdate,
    ) -> CustomWidget:
        """Update a custom widget.

        Args:
            widget_id: Widget ID
            user_id: Owner user ID
            updates: Update data

        Returns:
            Updated CustomWidget

        Raises:
            KeyError: If widget not found
            PermissionError: If user is not the owner
        """
        widget = self._widgets.get(widget_id)
        if not widget:
            raise KeyError(f"Widget {widget_id} not found")

        if widget.user_id != user_id:
            raise PermissionError("Only the owner can update this widget")

        # Validate query if being updated
        if updates.query:
            self._validate_query(updates.query)

        # Apply updates
        update_data = updates.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(widget, key, value)

        widget.updated_at = datetime.utcnow()
        widget.version += 1

        logger.info(f"Custom widget updated: {widget_id}")
        return widget

    def delete_custom_widget(
        self,
        widget_id: str,
        user_id: str,
    ) -> None:
        """Delete a custom widget.

        Args:
            widget_id: Widget ID
            user_id: Owner user ID

        Raises:
            KeyError: If widget not found
            PermissionError: If user is not the owner
        """
        widget = self._widgets.get(widget_id)
        if not widget:
            raise KeyError(f"Widget {widget_id} not found")

        if widget.user_id != user_id:
            raise PermissionError("Only the owner can delete this widget")

        del self._widgets[widget_id]
        self._user_widgets[user_id].remove(widget_id)

        logger.info(f"Custom widget deleted: {widget_id}")

    def list_custom_widgets(
        self,
        user_id: str,
        include_published: bool = True,
    ) -> list[CustomWidget]:
        """List custom widgets accessible by a user.

        Args:
            user_id: User ID
            include_published: Whether to include published widgets from others

        Returns:
            List of CustomWidgets
        """
        widgets = []

        # User's own widgets
        for widget_id in self._user_widgets.get(user_id, []):
            if widget_id in self._widgets:
                widgets.append(self._widgets[widget_id])

        # Published widgets from others
        if include_published:
            for widget in self._widgets.values():
                if widget.is_published and widget.user_id != user_id:
                    widgets.append(widget)

        return widgets

    def execute_query(
        self,
        widget_id: str,
        user_id: str,
    ) -> QueryResult:
        """Execute a custom widget's query.

        Args:
            widget_id: Widget ID
            user_id: Requesting user ID

        Returns:
            QueryResult with data or error
        """
        import time

        start_time = time.time()

        try:
            widget = self.get_custom_widget(widget_id, user_id)
            query = widget.query

            # Validate query is allowed
            self._validate_query(query)

            # Execute query (mock implementation)
            data = self._execute_mock_query(query)

            execution_time = int((time.time() - start_time) * 1000)

            return QueryResult(
                success=True,
                data=data,
                execution_time_ms=execution_time,
                cached=False,
            )

        except Exception as e:
            logger.error(f"Query execution failed for widget {widget_id}: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            return QueryResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
            )

    def preview_query(
        self,
        query: QueryDefinition,
        user_id: str,
    ) -> QueryResult:
        """Preview a query without saving the widget.

        Args:
            query: Query definition to preview
            user_id: Requesting user ID

        Returns:
            QueryResult with sample data
        """
        import time

        start_time = time.time()

        try:
            # Validate query
            self._validate_query(query)

            # Execute with limit for preview
            preview_query = query.model_copy()
            preview_query.limit = min(query.limit, 10)

            data = self._execute_mock_query(preview_query)

            execution_time = int((time.time() - start_time) * 1000)

            return QueryResult(
                success=True,
                data=data,
                execution_time_ms=execution_time,
                cached=False,
            )

        except Exception as e:
            logger.error(f"Query preview failed: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            return QueryResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
            )

    def _validate_query(self, query: QueryDefinition) -> None:
        """Validate a query definition.

        Args:
            query: Query to validate

        Raises:
            ValueError: If query is invalid or not allowed
        """
        # Check endpoint is allowed for data source
        allowed = ALLOWED_ENDPOINTS.get(query.data_source, [])
        is_allowed = any(query.endpoint.startswith(prefix) for prefix in allowed)

        if not is_allowed:
            raise ValueError(
                f"Endpoint '{query.endpoint}' not allowed for {query.data_source.value}"
            )

        # Validate filter field names
        for f in query.filters:
            field = f.get("field", "")
            if field and not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", field):
                raise ValueError(f"Invalid filter field: {field}")

    def _execute_mock_query(self, query: QueryDefinition) -> Any:
        """Execute a mock query for testing.

        In production, this would call the actual data APIs.

        Args:
            query: Query to execute

        Returns:
            Mock data based on query type
        """
        if query.query_type == QueryType.METRIC:
            return {
                "value": 42,
                "trend": 5.2,
                "trend_direction": "up",
                "timestamp": datetime.utcnow().isoformat(),
            }
        elif query.query_type == QueryType.TIME_SERIES:
            return {
                "labels": ["Mon", "Tue", "Wed", "Thu", "Fri"],
                "datasets": [
                    {
                        "label": "Series 1",
                        "data": [10, 15, 12, 18, 22],
                    }
                ],
            }
        elif query.query_type == QueryType.TABLE:
            return {
                "columns": ["Name", "Value", "Status"],
                "rows": [
                    ["Item 1", 100, "Active"],
                    ["Item 2", 85, "Active"],
                    ["Item 3", 65, "Inactive"],
                ],
            }
        elif query.query_type == QueryType.AGGREGATION:
            return {
                "groups": [
                    {"label": "Group A", "value": 45},
                    {"label": "Group B", "value": 32},
                    {"label": "Group C", "value": 23},
                ],
            }
        return {}


# Singleton instance
_service_instance: CustomWidgetService | None = None


def get_custom_widget_service() -> CustomWidgetService:
    """Get the custom widget service singleton.

    Returns:
        CustomWidgetService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = CustomWidgetService()
    return _service_instance
