"""Tests for Custom Widget Service (ADR-064 Phase 3)."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.services.dashboard import (
    CustomWidgetCreate,
    CustomWidgetService,
    CustomWidgetUpdate,
    DataSourceType,
    QueryDefinition,
    QueryType,
    WidgetCategory,
    WidgetType,
    get_custom_widget_service,
)


@pytest.fixture
def custom_widget_service():
    """Create a fresh CustomWidgetService instance."""
    return CustomWidgetService()


@pytest.fixture
def sample_query_definition():
    """Create a sample query definition."""
    return QueryDefinition(
        query_type=QueryType.METRIC,
        data_source=DataSourceType.SECURITY_API,
        endpoint="security/vulnerabilities",
        parameters={"severity": "critical"},
        filters=[{"field": "status", "operator": "eq", "value": "open"}],
        aggregation="count",
        time_range="24h",
        limit=100,
    )


@pytest.fixture
def sample_custom_widget_create(sample_query_definition):
    """Create a sample CustomWidgetCreate request."""
    return CustomWidgetCreate(
        name="Critical Vulnerabilities",
        description="Count of critical vulnerabilities",
        widget_type=WidgetType.METRIC,
        category=WidgetCategory.SECURITY,
        query=sample_query_definition,
        display_config={"color": "red", "icon": "shield"},
        refresh_seconds=60,
    )


class TestQueryDefinitionValidation:
    """Tests for QueryDefinition validation."""

    def test_valid_query_definition(self, sample_query_definition):
        """Test valid query definition creates successfully."""
        assert sample_query_definition.query_type == QueryType.METRIC
        assert sample_query_definition.data_source == DataSourceType.SECURITY_API
        assert sample_query_definition.endpoint == "security/vulnerabilities"

    def test_invalid_endpoint_format(self):
        """Test endpoint validation rejects invalid characters."""
        with pytest.raises(ValidationError) as exc_info:
            QueryDefinition(
                query_type=QueryType.METRIC,
                data_source=DataSourceType.SECURITY_API,
                endpoint="security/vuln;DROP TABLE",  # SQL injection attempt
                time_range="24h",
            )
        assert "Invalid endpoint format" in str(exc_info.value)

    def test_invalid_endpoint_with_special_chars(self):
        """Test endpoint validation rejects special characters."""
        with pytest.raises(ValidationError) as exc_info:
            QueryDefinition(
                query_type=QueryType.METRIC,
                data_source=DataSourceType.SECURITY_API,
                endpoint="security/../admin",  # Path traversal attempt
                time_range="24h",
            )
        # The .. contains a dot which is not in allowed regex
        assert "Invalid endpoint format" in str(exc_info.value)

    def test_invalid_group_by_field(self):
        """Test group_by validation rejects invalid field names."""
        with pytest.raises(ValidationError) as exc_info:
            QueryDefinition(
                query_type=QueryType.AGGREGATION,
                data_source=DataSourceType.SECURITY_API,
                endpoint="security/metrics",
                group_by=["123invalid"],  # Starts with number
                time_range="24h",
            )
        assert "Invalid field name" in str(exc_info.value)

    def test_invalid_time_range_format(self):
        """Test time_range validation rejects invalid formats."""
        with pytest.raises(ValidationError):
            QueryDefinition(
                query_type=QueryType.METRIC,
                data_source=DataSourceType.SECURITY_API,
                endpoint="security/metrics",
                time_range="invalid",  # Invalid format
            )

    def test_limit_bounds(self):
        """Test limit validation enforces bounds."""
        # Below minimum
        with pytest.raises(ValidationError):
            QueryDefinition(
                query_type=QueryType.METRIC,
                data_source=DataSourceType.SECURITY_API,
                endpoint="security/metrics",
                time_range="24h",
                limit=0,
            )

        # Above maximum
        with pytest.raises(ValidationError):
            QueryDefinition(
                query_type=QueryType.METRIC,
                data_source=DataSourceType.SECURITY_API,
                endpoint="security/metrics",
                time_range="24h",
                limit=10000,
            )


class TestCustomWidgetCreate:
    """Tests for CustomWidgetCreate validation."""

    def test_valid_create_request(self, sample_custom_widget_create):
        """Test valid create request validates successfully."""
        assert sample_custom_widget_create.name == "Critical Vulnerabilities"
        assert sample_custom_widget_create.widget_type == WidgetType.METRIC
        assert sample_custom_widget_create.refresh_seconds == 60

    def test_name_length_validation(self, sample_query_definition):
        """Test name length validation."""
        # Too short
        with pytest.raises(ValidationError):
            CustomWidgetCreate(
                name="",  # Empty name
                widget_type=WidgetType.METRIC,
                query=sample_query_definition,
            )

        # Too long
        with pytest.raises(ValidationError):
            CustomWidgetCreate(
                name="x" * 101,  # Over 100 chars
                widget_type=WidgetType.METRIC,
                query=sample_query_definition,
            )

    def test_refresh_seconds_bounds(self, sample_query_definition):
        """Test refresh_seconds validation."""
        # Below minimum
        with pytest.raises(ValidationError):
            CustomWidgetCreate(
                name="Test Widget",
                widget_type=WidgetType.METRIC,
                query=sample_query_definition,
                refresh_seconds=5,  # Below 10
            )

        # Above maximum
        with pytest.raises(ValidationError):
            CustomWidgetCreate(
                name="Test Widget",
                widget_type=WidgetType.METRIC,
                query=sample_query_definition,
                refresh_seconds=7200,  # Above 3600
            )


class TestCreateCustomWidget:
    """Tests for custom widget creation."""

    def test_create_widget_success(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test successful widget creation."""
        widget = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )

        assert widget.widget_id.startswith("cw-")
        assert widget.user_id == "user-123"
        assert widget.name == "Critical Vulnerabilities"
        assert widget.version == 1
        assert widget.is_published is False
        assert isinstance(widget.created_at, datetime)
        assert isinstance(widget.updated_at, datetime)

    def test_create_widget_limit_exceeded(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test widget creation fails when limit exceeded."""
        # Create max widgets
        for i in range(CustomWidgetService.MAX_WIDGETS_PER_USER):
            widget_data = sample_custom_widget_create.model_copy()
            widget_data.name = f"Widget {i}"
            custom_widget_service.create_custom_widget(
                user_id="user-123",
                widget_data=widget_data,
            )

        # Attempt to create one more
        with pytest.raises(ValueError) as exc_info:
            custom_widget_service.create_custom_widget(
                user_id="user-123",
                widget_data=sample_custom_widget_create,
            )

        assert "Maximum 25 custom widgets" in str(exc_info.value)

    def test_create_widget_invalid_endpoint(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test widget creation fails with invalid endpoint for data source."""
        query = QueryDefinition(
            query_type=QueryType.METRIC,
            data_source=DataSourceType.SECURITY_API,
            endpoint="cost/monthly",  # Cost endpoint for security data source
            time_range="24h",
        )

        widget_data = CustomWidgetCreate(
            name="Test Widget",
            widget_type=WidgetType.METRIC,
            query=query,
        )

        with pytest.raises(ValueError) as exc_info:
            custom_widget_service.create_custom_widget(
                user_id="user-123",
                widget_data=widget_data,
            )

        assert "not allowed for security_api" in str(exc_info.value)


class TestGetCustomWidget:
    """Tests for custom widget retrieval."""

    def test_get_widget_success(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test successful widget retrieval by owner."""
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )

        widget = custom_widget_service.get_custom_widget(
            widget_id=created.widget_id,
            user_id="user-123",
        )

        assert widget.widget_id == created.widget_id
        assert widget.name == "Critical Vulnerabilities"

    def test_get_widget_not_found(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test widget retrieval when not found."""
        with pytest.raises(KeyError) as exc_info:
            custom_widget_service.get_custom_widget(
                widget_id="cw-nonexistent",
                user_id="user-123",
            )

        assert "not found" in str(exc_info.value)

    def test_get_widget_access_denied(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test widget retrieval access denied for non-owner of unpublished widget."""
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )

        with pytest.raises(PermissionError) as exc_info:
            custom_widget_service.get_custom_widget(
                widget_id=created.widget_id,
                user_id="user-456",  # Different user
            )

        assert "Access denied" in str(exc_info.value)

    def test_get_published_widget_by_other_user(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test published widget can be accessed by other users."""
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )

        # Publish the widget
        custom_widget_service.update_custom_widget(
            widget_id=created.widget_id,
            user_id="user-123",
            updates=CustomWidgetUpdate(is_published=True),
        )

        # Other user can access
        widget = custom_widget_service.get_custom_widget(
            widget_id=created.widget_id,
            user_id="user-456",
        )

        assert widget.widget_id == created.widget_id
        assert widget.is_published is True


class TestUpdateCustomWidget:
    """Tests for custom widget updates."""

    def test_update_widget_success(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test successful widget update."""
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )

        updates = CustomWidgetUpdate(
            name="Updated Widget Name",
            description="Updated description",
        )

        updated = custom_widget_service.update_custom_widget(
            widget_id=created.widget_id,
            user_id="user-123",
            updates=updates,
        )

        assert updated.name == "Updated Widget Name"
        assert updated.description == "Updated description"
        assert updated.version == 2

    def test_update_widget_not_found(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test widget update when not found."""
        with pytest.raises(KeyError):
            custom_widget_service.update_custom_widget(
                widget_id="cw-nonexistent",
                user_id="user-123",
                updates=CustomWidgetUpdate(name="New Name"),
            )

    def test_update_widget_not_owner(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test widget update by non-owner fails."""
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )

        with pytest.raises(PermissionError) as exc_info:
            custom_widget_service.update_custom_widget(
                widget_id=created.widget_id,
                user_id="user-456",  # Different user
                updates=CustomWidgetUpdate(name="New Name"),
            )

        assert "Only the owner" in str(exc_info.value)

    def test_update_widget_query_validation(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test widget update validates query changes."""
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )

        # Try to update with invalid query
        invalid_query = QueryDefinition(
            query_type=QueryType.METRIC,
            data_source=DataSourceType.SECURITY_API,
            endpoint="invalid/endpoint",  # Not allowed
            time_range="24h",
        )

        with pytest.raises(ValueError):
            custom_widget_service.update_custom_widget(
                widget_id=created.widget_id,
                user_id="user-123",
                updates=CustomWidgetUpdate(query=invalid_query),
            )


class TestDeleteCustomWidget:
    """Tests for custom widget deletion."""

    def test_delete_widget_success(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test successful widget deletion."""
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )

        custom_widget_service.delete_custom_widget(
            widget_id=created.widget_id,
            user_id="user-123",
        )

        # Verify widget is deleted
        with pytest.raises(KeyError):
            custom_widget_service.get_custom_widget(
                widget_id=created.widget_id,
                user_id="user-123",
            )

    def test_delete_widget_not_found(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test widget deletion when not found."""
        with pytest.raises(KeyError):
            custom_widget_service.delete_custom_widget(
                widget_id="cw-nonexistent",
                user_id="user-123",
            )

    def test_delete_widget_not_owner(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test widget deletion by non-owner fails."""
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )

        with pytest.raises(PermissionError) as exc_info:
            custom_widget_service.delete_custom_widget(
                widget_id=created.widget_id,
                user_id="user-456",  # Different user
            )

        assert "Only the owner" in str(exc_info.value)


class TestListCustomWidgets:
    """Tests for listing custom widgets."""

    def test_list_widgets_empty(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test listing widgets when none exist."""
        widgets = custom_widget_service.list_custom_widgets(user_id="user-123")
        assert widgets == []

    def test_list_own_widgets(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test listing user's own widgets."""
        # Create widgets
        for i in range(3):
            widget_data = sample_custom_widget_create.model_copy()
            widget_data.name = f"Widget {i}"
            custom_widget_service.create_custom_widget(
                user_id="user-123",
                widget_data=widget_data,
            )

        widgets = custom_widget_service.list_custom_widgets(user_id="user-123")
        assert len(widgets) == 3

    def test_list_includes_published(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test listing includes published widgets from other users."""
        # User 1 creates and publishes a widget
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )
        custom_widget_service.update_custom_widget(
            widget_id=created.widget_id,
            user_id="user-123",
            updates=CustomWidgetUpdate(is_published=True),
        )

        # User 2 can see published widget
        widgets = custom_widget_service.list_custom_widgets(user_id="user-456")
        assert len(widgets) == 1
        assert widgets[0].is_published is True

    def test_list_excludes_published(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test listing can exclude published widgets."""
        # User 1 creates and publishes a widget
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )
        custom_widget_service.update_custom_widget(
            widget_id=created.widget_id,
            user_id="user-123",
            updates=CustomWidgetUpdate(is_published=True),
        )

        # User 2 with include_published=False sees no widgets
        widgets = custom_widget_service.list_custom_widgets(
            user_id="user-456",
            include_published=False,
        )
        assert len(widgets) == 0


class TestExecuteQuery:
    """Tests for query execution."""

    def test_execute_query_success(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test successful query execution."""
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )

        result = custom_widget_service.execute_query(
            widget_id=created.widget_id,
            user_id="user-123",
        )

        assert result.success is True
        assert result.data is not None
        assert result.execution_time_ms >= 0
        assert result.error is None

    def test_execute_query_metric_result(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test metric query returns metric data."""
        query = QueryDefinition(
            query_type=QueryType.METRIC,
            data_source=DataSourceType.METRICS_API,
            endpoint="metrics/custom",
            time_range="24h",
        )
        widget_data = CustomWidgetCreate(
            name="Test Metric",
            widget_type=WidgetType.METRIC,
            query=query,
        )
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=widget_data,
        )

        result = custom_widget_service.execute_query(
            widget_id=created.widget_id,
            user_id="user-123",
        )

        assert result.success is True
        assert "value" in result.data
        assert "trend" in result.data

    def test_execute_query_time_series_result(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test time series query returns chart data."""
        query = QueryDefinition(
            query_type=QueryType.TIME_SERIES,
            data_source=DataSourceType.METRICS_API,
            endpoint="metrics/timeseries",
            time_range="7d",
        )
        widget_data = CustomWidgetCreate(
            name="Test Time Series",
            widget_type=WidgetType.CHART_LINE,
            query=query,
        )
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=widget_data,
        )

        result = custom_widget_service.execute_query(
            widget_id=created.widget_id,
            user_id="user-123",
        )

        assert result.success is True
        assert "labels" in result.data
        assert "datasets" in result.data

    def test_execute_query_table_result(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test table query returns tabular data."""
        query = QueryDefinition(
            query_type=QueryType.TABLE,
            data_source=DataSourceType.SECURITY_API,
            endpoint="security/vulnerabilities",
            time_range="24h",
        )
        widget_data = CustomWidgetCreate(
            name="Test Table",
            widget_type=WidgetType.TABLE,
            query=query,
        )
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=widget_data,
        )

        result = custom_widget_service.execute_query(
            widget_id=created.widget_id,
            user_id="user-123",
        )

        assert result.success is True
        assert "columns" in result.data
        assert "rows" in result.data

    def test_execute_query_widget_not_found(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test query execution with nonexistent widget."""
        result = custom_widget_service.execute_query(
            widget_id="cw-nonexistent",
            user_id="user-123",
        )

        assert result.success is False
        assert "not found" in result.error

    def test_execute_query_access_denied(
        self,
        custom_widget_service: CustomWidgetService,
        sample_custom_widget_create: CustomWidgetCreate,
    ):
        """Test query execution access denied for non-owner."""
        created = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=sample_custom_widget_create,
        )

        result = custom_widget_service.execute_query(
            widget_id=created.widget_id,
            user_id="user-456",  # Different user
        )

        assert result.success is False
        assert "Access denied" in result.error


class TestPreviewQuery:
    """Tests for query preview."""

    def test_preview_query_success(
        self,
        custom_widget_service: CustomWidgetService,
        sample_query_definition: QueryDefinition,
    ):
        """Test successful query preview."""
        result = custom_widget_service.preview_query(
            query=sample_query_definition,
            user_id="user-123",
        )

        assert result.success is True
        assert result.data is not None
        assert result.execution_time_ms >= 0

    def test_preview_query_invalid(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test query preview with invalid query."""
        invalid_query = QueryDefinition(
            query_type=QueryType.METRIC,
            data_source=DataSourceType.SECURITY_API,
            endpoint="invalid/endpoint",  # Not allowed
            time_range="24h",
        )

        result = custom_widget_service.preview_query(
            query=invalid_query,
            user_id="user-123",
        )

        assert result.success is False
        assert "not allowed" in result.error


class TestValidateQuery:
    """Tests for query validation."""

    def test_validate_metrics_api_endpoints(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test validation of metrics API endpoints."""
        # Valid metrics endpoints
        valid_endpoints = ["metrics/custom", "metrics/aggregate", "metrics/timeseries"]
        for endpoint in valid_endpoints:
            query = QueryDefinition(
                query_type=QueryType.METRIC,
                data_source=DataSourceType.METRICS_API,
                endpoint=endpoint,
                time_range="24h",
            )
            # Should not raise
            custom_widget_service._validate_query(query)

    def test_validate_security_api_endpoints(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test validation of security API endpoints."""
        valid_endpoints = [
            "security/vulnerabilities",
            "security/alerts",
            "security/cve",
        ]
        for endpoint in valid_endpoints:
            query = QueryDefinition(
                query_type=QueryType.METRIC,
                data_source=DataSourceType.SECURITY_API,
                endpoint=endpoint,
                time_range="24h",
            )
            # Should not raise
            custom_widget_service._validate_query(query)

    def test_validate_cross_source_endpoint_rejected(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test that endpoint for wrong data source is rejected."""
        query = QueryDefinition(
            query_type=QueryType.METRIC,
            data_source=DataSourceType.COST_API,
            endpoint="security/vulnerabilities",  # Security endpoint for cost API
            time_range="24h",
        )

        with pytest.raises(ValueError) as exc_info:
            custom_widget_service._validate_query(query)

        assert "not allowed for cost_api" in str(exc_info.value)

    def test_validate_filter_field_names(
        self,
        custom_widget_service: CustomWidgetService,
    ):
        """Test validation of filter field names."""
        # Valid filter
        query = QueryDefinition(
            query_type=QueryType.METRIC,
            data_source=DataSourceType.SECURITY_API,
            endpoint="security/metrics",
            filters=[{"field": "valid_field", "operator": "eq", "value": "test"}],
            time_range="24h",
        )
        # Should not raise
        custom_widget_service._validate_query(query)

        # Invalid filter field
        query_invalid = QueryDefinition(
            query_type=QueryType.METRIC,
            data_source=DataSourceType.SECURITY_API,
            endpoint="security/metrics",
            filters=[{"field": "invalid;field", "operator": "eq", "value": "test"}],
            time_range="24h",
        )
        with pytest.raises(ValueError) as exc_info:
            custom_widget_service._validate_query(query_invalid)
        assert "Invalid filter field" in str(exc_info.value)


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_custom_widget_service_singleton(self):
        """Test get_custom_widget_service returns same instance."""
        # Reset singleton for test
        import src.services.dashboard.custom_widget_service as module

        module._service_instance = None

        service1 = get_custom_widget_service()
        service2 = get_custom_widget_service()

        assert service1 is service2


class TestAllDataSources:
    """Tests for all data source types."""

    @pytest.mark.parametrize(
        "data_source,endpoint",
        [
            (DataSourceType.METRICS_API, "metrics/custom"),
            (DataSourceType.SECURITY_API, "security/vulnerabilities"),
            (DataSourceType.OPERATIONS_API, "agents/health"),
            (DataSourceType.COMPLIANCE_API, "compliance/progress"),
            (DataSourceType.COST_API, "cost/monthly"),
        ],
    )
    def test_all_data_sources_work(
        self,
        custom_widget_service: CustomWidgetService,
        data_source: DataSourceType,
        endpoint: str,
    ):
        """Test all data source types can create widgets."""
        query = QueryDefinition(
            query_type=QueryType.METRIC,
            data_source=data_source,
            endpoint=endpoint,
            time_range="24h",
        )
        widget_data = CustomWidgetCreate(
            name=f"Test {data_source.value}",
            widget_type=WidgetType.METRIC,
            query=query,
        )

        widget = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=widget_data,
        )

        assert widget.widget_id.startswith("cw-")
        assert widget.query.data_source == data_source


class TestAllQueryTypes:
    """Tests for all query types."""

    @pytest.mark.parametrize(
        "query_type,expected_keys",
        [
            (QueryType.METRIC, ["value", "trend"]),
            (QueryType.TIME_SERIES, ["labels", "datasets"]),
            (QueryType.TABLE, ["columns", "rows"]),
            (QueryType.AGGREGATION, ["groups"]),
        ],
    )
    def test_all_query_types_return_data(
        self,
        custom_widget_service: CustomWidgetService,
        query_type: QueryType,
        expected_keys: list[str],
    ):
        """Test all query types return appropriate data structure."""
        query = QueryDefinition(
            query_type=query_type,
            data_source=DataSourceType.METRICS_API,
            endpoint="metrics/custom",
            time_range="24h",
        )
        widget_data = CustomWidgetCreate(
            name=f"Test {query_type.value}",
            widget_type=WidgetType.METRIC,
            query=query,
        )
        widget = custom_widget_service.create_custom_widget(
            user_id="user-123",
            widget_data=widget_data,
        )

        result = custom_widget_service.execute_query(
            widget_id=widget.widget_id,
            user_id="user-123",
        )

        assert result.success is True
        for key in expected_keys:
            assert key in result.data
