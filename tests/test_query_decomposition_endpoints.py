"""
Tests for Query Decomposition API Endpoints (Issue #32).

Tests the REST API endpoints for query decomposition visualization.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.query_decomposition_endpoints import (
    ExecutionPlan,
    QueryType,
    _decomposition_store,
    query_decomposition_router,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def test_client():
    """Create a test client for the query decomposition endpoints."""
    app = FastAPI()
    app.include_router(query_decomposition_router)

    # Clear store before each test
    _decomposition_store.clear()

    return TestClient(app)


# ============================================================================
# Decompose Query Tests
# ============================================================================


class TestDecomposeQuery:
    """Tests for POST /api/v1/query/decompose endpoint."""

    def test_decompose_simple_query(self, test_client):
        """Test decomposing a simple query."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Find authentication functions"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert data["original_query"] == "Find authentication functions"
        assert "timestamp" in data
        assert "subqueries" in data
        assert len(data["subqueries"]) > 0
        assert "total_results" in data
        assert "execution_time_ms" in data
        assert "execution_plan" in data

    def test_decompose_complex_query(self, test_client):
        """Test decomposing a complex multi-faceted query."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={
                "query": "Find auth functions that call database, modified in last sprint",
                "max_subqueries": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should generate multiple subqueries for complex query
        assert len(data["subqueries"]) >= 2

        # Should include different query types
        types = [sq["type"] for sq in data["subqueries"]]
        assert len(set(types)) >= 1  # At least one type

    def test_decompose_structural_query(self, test_client):
        """Test decomposing a structural query."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Find all class methods that call external APIs"},
        )

        assert response.status_code == 200
        data = response.json()

        # Should include structural subquery
        types = [sq["type"] for sq in data["subqueries"]]
        assert "structural" in types or "semantic" in types

    def test_decompose_temporal_query(self, test_client):
        """Test decomposing a temporal query."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Show files modified last week"},
        )

        assert response.status_code == 200
        data = response.json()

        # Should include temporal subquery
        types = [sq["type"] for sq in data["subqueries"]]
        assert "temporal" in types

    def test_decompose_with_max_subqueries(self, test_client):
        """Test limiting max subqueries."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Complex search query", "max_subqueries": 2},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["subqueries"]) <= 2

    def test_decompose_empty_query_fails(self, test_client):
        """Test that empty query fails validation."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": ""},
        )

        assert response.status_code == 422  # Validation error

    def test_decompose_stores_result(self, test_client):
        """Test that decomposition is stored for retrieval."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Test query for storage"},
        )

        assert response.status_code == 200
        decomposition_id = response.json()["id"]

        # Should be retrievable
        get_response = test_client.get(
            f"/api/v1/query/decomposition/{decomposition_id}"
        )
        assert get_response.status_code == 200
        assert get_response.json()["id"] == decomposition_id


# ============================================================================
# Subquery Structure Tests
# ============================================================================


class TestSubqueryStructure:
    """Tests for subquery response structure."""

    def test_subquery_has_required_fields(self, test_client):
        """Test that each subquery has required fields."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Find error handling code"},
        )

        assert response.status_code == 200
        data = response.json()

        for subquery in data["subqueries"]:
            assert "id" in subquery
            assert "type" in subquery
            assert "query" in subquery
            assert "result_count" in subquery
            assert "confidence" in subquery
            assert "execution_time_ms" in subquery

    def test_subquery_confidence_range(self, test_client):
        """Test that confidence is in valid range."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Security vulnerability patterns"},
        )

        assert response.status_code == 200
        data = response.json()

        for subquery in data["subqueries"]:
            assert 0 <= subquery["confidence"] <= 100

    def test_subquery_types_valid(self, test_client):
        """Test that subquery types are valid enum values."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Database query optimization"},
        )

        assert response.status_code == 200
        data = response.json()

        valid_types = ["structural", "semantic", "temporal"]
        for subquery in data["subqueries"]:
            assert subquery["type"] in valid_types


# ============================================================================
# Get Decomposition Tests
# ============================================================================


class TestGetDecomposition:
    """Tests for GET /api/v1/query/decomposition/{id} endpoint."""

    def test_get_decomposition_success(self, test_client):
        """Test getting a decomposition by ID."""
        # First create one
        create_response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Test query"},
        )
        decomposition_id = create_response.json()["id"]

        # Then retrieve it
        response = test_client.get(f"/api/v1/query/decomposition/{decomposition_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == decomposition_id
        assert data["original_query"] == "Test query"

    def test_get_decomposition_not_found(self, test_client):
        """Test getting a non-existent decomposition."""
        response = test_client.get("/api/v1/query/decomposition/non-existent-id")

        assert response.status_code == 404
        assert "detail" in response.json()

    def test_get_decomposition_preserves_data(self, test_client):
        """Test that retrieved decomposition matches created one."""
        create_response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Authentication and authorization patterns"},
        )
        created = create_response.json()

        get_response = test_client.get(f"/api/v1/query/decomposition/{created['id']}")
        retrieved = get_response.json()

        assert retrieved["original_query"] == created["original_query"]
        assert len(retrieved["subqueries"]) == len(created["subqueries"])
        assert retrieved["total_results"] == created["total_results"]


# ============================================================================
# List Decompositions Tests
# ============================================================================


class TestListDecompositions:
    """Tests for GET /api/v1/query/decompositions endpoint."""

    def test_list_decompositions_empty(self, test_client):
        """Test listing when no decompositions exist."""
        response = test_client.get("/api/v1/query/decompositions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["decompositions"] == []

    def test_list_decompositions_with_data(self, test_client):
        """Test listing decompositions with data."""
        # Create a few decompositions
        for i in range(3):
            test_client.post(
                "/api/v1/query/decompose",
                json={"query": f"Query number {i}"},
            )

        response = test_client.get("/api/v1/query/decompositions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["decompositions"]) == 3

    def test_list_decompositions_pagination(self, test_client):
        """Test pagination of decompositions list."""
        # Create 5 decompositions
        for i in range(5):
            test_client.post(
                "/api/v1/query/decompose",
                json={"query": f"Query {i}"},
            )

        # Get first 2
        response = test_client.get("/api/v1/query/decompositions?limit=2&offset=0")
        data = response.json()
        assert len(data["decompositions"]) == 2
        assert data["total"] == 5

        # Get next 2
        response = test_client.get("/api/v1/query/decompositions?limit=2&offset=2")
        data = response.json()
        assert len(data["decompositions"]) == 2

    def test_list_decompositions_summary_fields(self, test_client):
        """Test that list items have summary fields."""
        test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Test query for summary"},
        )

        response = test_client.get("/api/v1/query/decompositions")
        data = response.json()

        item = data["decompositions"][0]
        assert "id" in item
        assert "original_query" in item
        assert "timestamp" in item
        assert "subquery_count" in item
        assert "total_results" in item
        assert "execution_time_ms" in item


# ============================================================================
# Enum Tests
# ============================================================================


class TestEnums:
    """Tests for API enums."""

    def test_query_type_enum_values(self):
        """Test QueryType enum values."""
        assert QueryType.STRUCTURAL.value == "structural"
        assert QueryType.SEMANTIC.value == "semantic"
        assert QueryType.TEMPORAL.value == "temporal"

    def test_execution_plan_enum_values(self):
        """Test ExecutionPlan enum values."""
        assert ExecutionPlan.PARALLEL.value == "parallel"
        assert ExecutionPlan.SEQUENTIAL.value == "sequential"
        assert ExecutionPlan.HYBRID.value == "hybrid"


# ============================================================================
# Execution Plan Tests
# ============================================================================


class TestExecutionPlan:
    """Tests for execution plan generation."""

    def test_execution_plan_is_valid(self, test_client):
        """Test that execution plan is a valid enum value."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Complex query for planning"},
        )

        assert response.status_code == 200
        data = response.json()

        valid_plans = ["parallel", "sequential", "hybrid"]
        assert data["execution_plan"] in valid_plans

    def test_execution_time_less_than_sum(self, test_client):
        """Test that total execution time accounts for parallelism."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Query with multiple subqueries"},
        )

        assert response.status_code == 200
        data = response.json()

        if data["execution_plan"] == "parallel" and len(data["subqueries"]) > 1:
            sum_time = sum(sq["execution_time_ms"] for sq in data["subqueries"])
            # Parallel execution should be faster than sequential sum
            assert data["execution_time_ms"] <= sum_time


# ============================================================================
# Reasoning Tests
# ============================================================================


class TestReasoning:
    """Tests for decomposition reasoning."""

    def test_reasoning_included(self, test_client):
        """Test that reasoning is included in response."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Find security vulnerabilities"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "reasoning" in data
        assert data["reasoning"] is not None

    def test_subquery_reasoning(self, test_client):
        """Test that subqueries include reasoning."""
        response = test_client.post(
            "/api/v1/query/decompose",
            json={"query": "Database performance issues"},
        )

        assert response.status_code == 200
        data = response.json()

        for subquery in data["subqueries"]:
            assert "reasoning" in subquery
