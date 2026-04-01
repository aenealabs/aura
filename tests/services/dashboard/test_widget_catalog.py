"""Tests for Widget Catalog."""

from __future__ import annotations

from src.services.dashboard import (
    WidgetCategory,
    WidgetType,
    get_catalog,
    get_widget_by_type,
    get_widget_catalog,
    get_widgets_by_category,
)


class TestWidgetCatalog:
    """Tests for widget catalog functions."""

    def test_get_widget_catalog(self):
        """Test getting the full widget catalog."""
        catalog = get_widget_catalog()

        assert len(catalog.widgets) > 0
        assert len(catalog.categories) == 6
        assert WidgetCategory.SECURITY in catalog.categories
        assert WidgetCategory.OPERATIONS in catalog.categories
        assert WidgetCategory.ANALYTICS in catalog.categories
        assert WidgetCategory.COMPLIANCE in catalog.categories
        assert WidgetCategory.COST in catalog.categories
        assert WidgetCategory.VULNERABILITY_SCANNER in catalog.categories

    def test_get_catalog_singleton(self):
        """Test that get_catalog returns cached instance."""
        catalog1 = get_catalog()
        catalog2 = get_catalog()
        assert catalog1 is catalog2

    def test_catalog_widget_count(self):
        """Test catalog has expected number of widgets."""
        catalog = get_catalog()
        # Should have at least 15 widgets across all categories
        assert len(catalog.widgets) >= 15


class TestGetWidgetsByCategory:
    """Tests for filtering widgets by category."""

    def test_get_security_widgets(self):
        """Test getting security widgets."""
        widgets = get_widgets_by_category(WidgetCategory.SECURITY)

        assert len(widgets) >= 4
        assert all(w.category == WidgetCategory.SECURITY for w in widgets)

    def test_get_operations_widgets(self):
        """Test getting operations widgets."""
        widgets = get_widgets_by_category(WidgetCategory.OPERATIONS)

        assert len(widgets) >= 5
        assert all(w.category == WidgetCategory.OPERATIONS for w in widgets)

    def test_get_analytics_widgets(self):
        """Test getting analytics widgets."""
        widgets = get_widgets_by_category(WidgetCategory.ANALYTICS)

        assert len(widgets) >= 3
        assert all(w.category == WidgetCategory.ANALYTICS for w in widgets)

    def test_get_compliance_widgets(self):
        """Test getting compliance widgets."""
        widgets = get_widgets_by_category(WidgetCategory.COMPLIANCE)

        assert len(widgets) >= 3
        assert all(w.category == WidgetCategory.COMPLIANCE for w in widgets)

    def test_get_cost_widgets(self):
        """Test getting cost widgets."""
        widgets = get_widgets_by_category(WidgetCategory.COST)

        assert len(widgets) >= 2
        assert all(w.category == WidgetCategory.COST for w in widgets)

    def test_get_vulnerability_scanner_widgets(self):
        """Test getting vulnerability scanner widgets (ADR-084)."""
        widgets = get_widgets_by_category(WidgetCategory.VULNERABILITY_SCANNER)

        assert len(widgets) == 20
        assert all(w.category == WidgetCategory.VULNERABILITY_SCANNER for w in widgets)

    def test_scanner_widgets_have_scanner_data_sources(self):
        """Test scanner widgets have scanner-related data sources."""
        widgets = get_widgets_by_category(WidgetCategory.VULNERABILITY_SCANNER)

        for widget in widgets:
            assert "scanner" in widget.default_data_source

    def test_scanner_widget_types_coverage(self):
        """Test scanner widgets cover expected widget types."""
        widgets = get_widgets_by_category(WidgetCategory.VULNERABILITY_SCANNER)
        types_used = {w.widget_type for w in widgets}

        # Scanner widgets should use a variety of widget types
        assert WidgetType.METRIC in types_used
        assert WidgetType.CHART_LINE in types_used
        assert WidgetType.CHART_BAR in types_used
        assert WidgetType.CHART_DONUT in types_used
        assert WidgetType.GAUGE in types_used
        assert WidgetType.STATUS_GRID in types_used
        assert WidgetType.ACTIVITY_FEED in types_used
        assert WidgetType.PROGRESS in types_used


class TestGetWidgetByType:
    """Tests for getting widget by type."""

    def test_get_metric_widget(self):
        """Test getting metric widget definition."""
        widget = get_widget_by_type(WidgetType.METRIC)

        assert widget is not None
        assert widget.widget_type == WidgetType.METRIC

    def test_get_chart_line_widget(self):
        """Test getting line chart widget definition."""
        widget = get_widget_by_type(WidgetType.CHART_LINE)

        assert widget is not None
        assert widget.widget_type == WidgetType.CHART_LINE

    def test_get_table_widget(self):
        """Test getting table widget definition."""
        widget = get_widget_by_type(WidgetType.TABLE)

        assert widget is not None
        assert widget.widget_type == WidgetType.TABLE

    def test_get_status_grid_widget(self):
        """Test getting status grid widget definition."""
        widget = get_widget_by_type(WidgetType.STATUS_GRID)

        assert widget is not None
        assert widget.widget_type == WidgetType.STATUS_GRID

    def test_get_gauge_widget(self):
        """Test getting gauge widget definition."""
        widget = get_widget_by_type(WidgetType.GAUGE)

        assert widget is not None
        assert widget.widget_type == WidgetType.GAUGE


class TestWidgetDefinitionFields:
    """Tests for widget definition field values."""

    def test_widget_has_required_fields(self):
        """Test all widgets have required fields."""
        catalog = get_catalog()

        for widget in catalog.widgets:
            assert widget.widget_type is not None
            assert widget.category is not None
            assert widget.name
            assert widget.description
            assert widget.default_data_source
            assert widget.default_refresh_seconds >= 10
            assert widget.min_width >= 1
            assert widget.min_height >= 1
            assert widget.default_width >= widget.min_width
            assert widget.default_height >= widget.min_height

    def test_security_widgets_have_security_data_sources(self):
        """Test security widgets have security-related data sources."""
        widgets = get_widgets_by_category(WidgetCategory.SECURITY)

        for widget in widgets:
            assert (
                "security" in widget.default_data_source
                or "approvals" in widget.default_data_source
            )

    def test_cost_widgets_have_cost_data_sources(self):
        """Test cost widgets have cost-related data sources."""
        widgets = get_widgets_by_category(WidgetCategory.COST)

        for widget in widgets:
            assert "cost" in widget.default_data_source

    def test_refresh_intervals_reasonable(self):
        """Test refresh intervals are reasonable for widget types."""
        catalog = get_catalog()

        for widget in catalog.widgets:
            # Real-time widgets should refresh frequently
            if "alert" in widget.name.lower() or "queue" in widget.name.lower():
                assert widget.default_refresh_seconds <= 60

            # Cost widgets can refresh less frequently
            if widget.category == WidgetCategory.COST:
                assert widget.default_refresh_seconds >= 300

    def test_widget_sizes_fit_grid(self):
        """Test widget default sizes fit in 12-column grid."""
        catalog = get_catalog()

        for widget in catalog.widgets:
            assert widget.default_width <= 12
            assert widget.min_width <= 12
            assert widget.default_height <= 10
            assert widget.min_height <= 10
