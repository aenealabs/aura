"""
Tests for Trace Explorer API Endpoints.

Tests the REST API endpoints for OpenTelemetry trace visualization (Issue #30).
"""

import pytest


@pytest.fixture(scope="module")
def client():
    """Create test client for trace endpoints.

    Uses module scope to ensure consistent FastAPI validation behavior
    across all tests in this module. All imports are inside the fixture
    to defer loading until test execution time.

    IMPORTANT: Clears trace_endpoints modules from sys.modules to ensure fresh
    router state. This prevents 404 errors in CI caused by module pollution
    from other tests that run earlier in the test suite.
    """
    import sys

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    # Clear trace modules to ensure fresh router with registered routes
    # This prevents 404 errors caused by module state pollution in CI
    modules_to_clear = [
        k for k in list(sys.modules.keys()) if "trace" in k and k.startswith("src.api")
    ]
    for mod in modules_to_clear:
        del sys.modules[mod]

    from src.api.trace_endpoints import router

    app = FastAPI()
    app.include_router(router)

    yield TestClient(app)


class TestGetTraceMetrics:
    """Tests for GET /api/v1/traces/metrics endpoint."""

    def test_get_metrics_success(self, client):
        """Test successful metrics retrieval."""
        response = client.get("/api/v1/traces/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "total_traces" in data
        assert "avg_latency_ms" in data
        assert "error_rate" in data
        assert "coverage" in data
        assert "traces_by_status" in data
        assert "traces_by_agent" in data
        assert "latency_histogram" in data
        assert "period" in data

    def test_get_metrics_with_period(self, client):
        """Test metrics with custom time period."""
        response = client.get("/api/v1/traces/metrics?period=7d")

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "7d"

    def test_get_metrics_period_options(self, client):
        """Test various period options."""
        periods = ["1h", "6h", "24h", "7d", "30d"]
        for period in periods:
            response = client.get(f"/api/v1/traces/metrics?period={period}")
            assert response.status_code == 200
            assert response.json()["period"] == period

    def test_metrics_status_counts_structure(self, client):
        """Test traces_by_status structure."""
        response = client.get("/api/v1/traces/metrics")

        data = response.json()
        status_counts = data["traces_by_status"]
        assert "success" in status_counts
        assert "error" in status_counts
        assert "timeout" in status_counts

    def test_metrics_latency_histogram(self, client):
        """Test latency histogram structure."""
        response = client.get("/api/v1/traces/metrics")

        data = response.json()
        histogram = data["latency_histogram"]
        assert isinstance(histogram, list)
        if histogram:
            assert "bucket" in histogram[0]
            assert "count" in histogram[0]


class TestListTraces:
    """Tests for GET /api/v1/traces endpoint."""

    def test_list_traces_success(self, client):
        """Test successful trace listing."""
        response = client.get("/api/v1/traces")

        assert response.status_code == 200
        data = response.json()
        assert "traces" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "has_more" in data
        assert isinstance(data["traces"], list)

    def test_list_traces_pagination(self, client):
        """Test pagination parameters."""
        response = client.get("/api/v1/traces?page=1&page_size=5")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5
        assert len(data["traces"]) <= 5

    def test_list_traces_status_filter(self, client):
        """Test filtering by status."""
        response = client.get("/api/v1/traces?status=error")

        assert response.status_code == 200
        data = response.json()
        # All returned traces should have error status
        for trace in data["traces"]:
            assert trace["status"] == "error"

    def test_list_traces_agent_type_filter(self, client):
        """Test filtering by agent type."""
        response = client.get("/api/v1/traces?agent_type=coder")

        assert response.status_code == 200
        data = response.json()
        # All returned traces should have coder agent type
        for trace in data["traces"]:
            assert trace["agent_type"] == "coder"

    def test_list_traces_duration_filter(self, client):
        """Test filtering by duration range."""
        response = client.get("/api/v1/traces?min_duration_ms=100&max_duration_ms=2000")

        assert response.status_code == 200
        data = response.json()
        for trace in data["traces"]:
            assert 100 <= trace["duration_ms"] <= 2000

    def test_list_traces_search(self, client):
        """Test search functionality."""
        response = client.get("/api/v1/traces?search=patch")

        assert response.status_code == 200
        data = response.json()
        # Results should contain search term in name or ID
        for trace in data["traces"]:
            found = (
                "patch" in trace["name"].lower() or "patch" in trace["trace_id"].lower()
            )
            assert found

    def test_list_traces_combined_filters(self, client):
        """Test multiple filters combined."""
        response = client.get("/api/v1/traces?period=24h&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page_size"] == 10

    def test_trace_list_item_structure(self, client):
        """Test trace list item has required fields."""
        response = client.get("/api/v1/traces?page_size=1")

        assert response.status_code == 200
        data = response.json()
        if data["traces"]:
            trace = data["traces"][0]
            assert "trace_id" in trace
            assert "name" in trace
            assert "agent_type" in trace
            assert "status" in trace
            assert "start_time" in trace
            assert "duration_ms" in trace
            assert "span_count" in trace
            assert "error_count" in trace


class TestGetTrace:
    """Tests for GET /api/v1/traces/{trace_id} endpoint."""

    def test_get_trace_success(self, client):
        """Test successful trace retrieval."""
        # First get a trace ID from the list
        list_response = client.get("/api/v1/traces?page_size=1")
        traces = list_response.json()["traces"]

        if traces:
            trace_id = traces[0]["trace_id"]
            response = client.get(f"/api/v1/traces/{trace_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["trace_id"] == trace_id
            assert "spans" in data
            assert isinstance(data["spans"], list)

    def test_get_trace_full_structure(self, client):
        """Test full trace response structure."""
        list_response = client.get("/api/v1/traces?page_size=1")
        traces = list_response.json()["traces"]

        if traces:
            trace_id = traces[0]["trace_id"]
            response = client.get(f"/api/v1/traces/{trace_id}")

            assert response.status_code == 200
            data = response.json()

            # Check trace fields
            assert "trace_id" in data
            assert "name" in data
            assert "agent_type" in data
            assert "status" in data
            assert "start_time" in data
            assert "end_time" in data
            assert "duration_ms" in data
            assert "span_count" in data
            assert "error_count" in data
            assert "spans" in data

    def test_get_trace_span_structure(self, client):
        """Test span structure within trace."""
        list_response = client.get("/api/v1/traces?page_size=1")
        traces = list_response.json()["traces"]

        if traces:
            trace_id = traces[0]["trace_id"]
            response = client.get(f"/api/v1/traces/{trace_id}")

            data = response.json()
            if data["spans"]:
                span = data["spans"][0]
                assert "span_id" in span
                assert "name" in span
                assert "kind" in span
                assert "status" in span
                assert "start_time" in span
                assert "end_time" in span
                assert "duration_ms" in span
                assert "attributes" in span
                assert "events" in span
                assert "links" in span

    def test_get_trace_not_found(self, client):
        """Test retrieving non-existent trace."""
        response = client.get("/api/v1/traces/nonexistent-trace-id-12345")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestTraceEndpointValidation:
    """Tests for input validation on trace endpoints."""

    def test_invalid_page_number(self, client):
        """Test invalid page number."""
        response = client.get("/api/v1/traces?page=0")
        assert response.status_code == 422

    def test_invalid_page_size(self, client):
        """Test page size exceeds maximum."""
        response = client.get("/api/v1/traces?page_size=200")
        assert response.status_code == 422

    def test_invalid_status_filter(self, client):
        """Test invalid status filter value."""
        response = client.get("/api/v1/traces?status=invalid_status")
        assert response.status_code == 422

    def test_invalid_agent_type_filter(self, client):
        """Test invalid agent type filter value."""
        response = client.get("/api/v1/traces?agent_type=invalid_agent")
        assert response.status_code == 422

    def test_negative_duration_filter(self, client):
        """Test negative duration filter."""
        response = client.get("/api/v1/traces?min_duration_ms=-100")
        assert response.status_code == 422


class TestSpanKindsAndStatus:
    """Tests for span kinds and status values."""

    def test_valid_span_kinds_in_response(self, client):
        """Test that spans have valid kind values."""
        list_response = client.get("/api/v1/traces?page_size=1")
        traces = list_response.json()["traces"]

        if traces:
            trace_id = traces[0]["trace_id"]
            response = client.get(f"/api/v1/traces/{trace_id}")

            data = response.json()
            valid_kinds = {"agent", "llm", "tool", "internal"}
            for span in data["spans"]:
                assert span["kind"] in valid_kinds

    def test_valid_status_values_in_response(self, client):
        """Test that traces and spans have valid status values."""
        response = client.get("/api/v1/traces?page_size=5")

        data = response.json()
        valid_statuses = {"success", "error", "timeout"}
        for trace in data["traces"]:
            assert trace["status"] in valid_statuses


class TestAgentTypes:
    """Tests for agent type filtering and values."""

    def test_all_agent_types_filterable(self, client):
        """Test that all agent types can be used as filters."""
        agent_types = ["coder", "reviewer", "validator", "orchestrator", "security"]

        for agent_type in agent_types:
            response = client.get(f"/api/v1/traces?agent_type={agent_type}")
            assert response.status_code == 200

    def test_agent_type_in_metrics(self, client):
        """Test that metrics include agent type breakdown."""
        response = client.get("/api/v1/traces/metrics")

        data = response.json()
        assert "traces_by_agent" in data
        # Should have some agent counts
        assert isinstance(data["traces_by_agent"], dict)
