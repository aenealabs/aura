"""
Tests for Model Router API Endpoints.

Tests the REST API endpoints for LLM model routing configuration and analytics.
"""

import os

import pytest


@pytest.fixture(scope="module")
def client():
    """Create test client with mocked router to avoid AWS calls.

    Uses module scope to ensure consistent FastAPI validation behavior
    across all tests in this module. All imports are inside the fixture
    to defer loading until test execution time.

    IMPORTANT: Clears model_router modules from sys.modules to ensure fresh
    router state. This prevents 404 errors in CI caused by module pollution
    from other tests that run earlier in the test suite.
    """
    import sys

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    os.environ["TESTING"] = "true"
    os.environ["MODEL_ROUTER_DISABLE_SSM"] = "true"

    # Clear model_router modules to ensure fresh router with registered routes
    # This prevents 404 errors caused by module state pollution in CI
    modules_to_clear = [
        k
        for k in list(sys.modules.keys())
        if "model_router" in k or k.startswith("src.api.model_router")
    ]
    for mod in modules_to_clear:
        del sys.modules[mod]

    from src.api.model_router_endpoints import router

    app = FastAPI()
    app.include_router(router)

    yield TestClient(app)


class TestGetRouterStats:
    """Tests for GET /api/v1/model-router/stats endpoint."""

    def test_get_stats_success(self, client):
        """Test successful stats retrieval."""
        response = client.get("/api/v1/model-router/stats")

        assert response.status_code == 200
        data = response.json()
        assert "cost_savings" in data
        assert "distribution" in data
        assert "ab_test" in data
        assert "total_decisions" in data
        assert isinstance(data["total_decisions"], int)

    def test_get_stats_with_period(self, client):
        """Test stats with custom time period."""
        response = client.get("/api/v1/model-router/stats?period=7d")

        assert response.status_code == 200
        data = response.json()
        assert "cost_savings" in data
        assert data["cost_savings"]["period"] == "7d"

    def test_get_stats_cost_savings_structure(self, client):
        """Test cost savings response structure."""
        response = client.get("/api/v1/model-router/stats")

        assert response.status_code == 200
        data = response.json()
        savings = data["cost_savings"]
        assert "percentage" in savings
        assert "amount" in savings
        assert "trend" in savings
        assert "baseline_cost" in savings
        assert "optimized_cost" in savings


class TestGetModelDistribution:
    """Tests for GET /api/v1/model-router/distribution endpoint."""

    def test_get_distribution_success(self, client):
        """Test successful distribution retrieval."""
        response = client.get("/api/v1/model-router/distribution")

        assert response.status_code == 200
        data = response.json()
        assert "distribution" in data
        assert "total_requests" in data
        assert len(data["distribution"]) == 3

    def test_distribution_contains_all_tiers(self, client):
        """Test that all model tiers are represented."""
        response = client.get("/api/v1/model-router/distribution")

        data = response.json()
        tiers = [item["tier"] for item in data["distribution"]]
        assert "fast" in tiers
        assert "accurate" in tiers
        assert "maximum" in tiers


class TestRoutingRules:
    """Tests for routing rules endpoints."""

    def test_get_rules_success(self, client):
        """Test successful rules retrieval."""
        response = client.get("/api/v1/model-router/rules")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # At least some default rules exist

    def test_get_rules_structure(self, client):
        """Test rule response structure."""
        response = client.get("/api/v1/model-router/rules")

        data = response.json()
        rule = data[0]
        assert "id" in rule
        assert "task_type" in rule
        assert "complexity" in rule
        assert "tier" in rule
        assert "model" in rule
        assert "cost_per_1k" in rule
        assert "enabled" in rule

    def test_create_rule_success(self, client):
        """Test creating a new routing rule."""
        import uuid

        # Use unique task type to avoid conflicts
        unique_task = f"test_task_{uuid.uuid4().hex[:8]}"

        response = client.post(
            "/api/v1/model-router/rules",
            json={
                "task_type": unique_task,
                "complexity": "simple",
                "tier": "fast",
                "description": "A new task",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["task_type"] == unique_task
        assert data["complexity"] == "simple"

    def test_create_rule_duplicate_task_type(self, client):
        """Test creating rule with duplicate task type."""
        response = client.post(
            "/api/v1/model-router/rules",
            json={
                "task_type": "query_intent_analysis",  # Already exists
                "complexity": "simple",
                "tier": "fast",
            },
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_update_rule_success(self, client):
        """Test updating an existing rule."""
        # First get existing rules to find a valid rule ID
        rules_response = client.get("/api/v1/model-router/rules")
        assert rules_response.status_code == 200
        rules = rules_response.json()

        if rules:
            rule_id = rules[0]["id"]
            response = client.put(
                f"/api/v1/model-router/rules/{rule_id}",
                json={"complexity": "medium", "tier": "accurate"},
            )
            assert response.status_code == 200

    def test_update_rule_not_found(self, client):
        """Test updating non-existent rule."""
        response = client.put(
            "/api/v1/model-router/rules/rule-nonexistent-999",
            json={"complexity": "medium"},
        )

        assert response.status_code == 404

    def test_delete_rule_success(self, client):
        """Test deleting an existing rule."""
        import uuid

        # First create a rule to delete
        unique_task = f"delete_test_{uuid.uuid4().hex[:8]}"
        create_response = client.post(
            "/api/v1/model-router/rules",
            json={
                "task_type": unique_task,
                "complexity": "simple",
                "tier": "fast",
            },
        )
        assert create_response.status_code == 201
        rule_id = create_response.json()["id"]

        # Now delete it
        response = client.delete(f"/api/v1/model-router/rules/{rule_id}")
        assert response.status_code == 204

    def test_delete_rule_not_found(self, client):
        """Test deleting non-existent rule."""
        response = client.delete("/api/v1/model-router/rules/rule-nonexistent-999")

        assert response.status_code == 404


class TestABTestConfig:
    """Tests for A/B test configuration endpoints."""

    def test_get_ab_test_config(self, client):
        """Test getting A/B test configuration."""
        response = client.get("/api/v1/model-router/ab-test")

        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "experiment_id" in data
        assert "control_tier" in data
        assert "treatment_tier" in data
        assert "traffic_split" in data

    def test_update_ab_test_enable(self, client):
        """Test enabling A/B testing."""
        response = client.put(
            "/api/v1/model-router/ab-test",
            json={"enabled": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["experiment_id"]  # Should be auto-generated

    def test_update_ab_test_traffic_split(self, client):
        """Test updating traffic split."""
        response = client.put(
            "/api/v1/model-router/ab-test",
            json={"traffic_split": 0.3},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["traffic_split"] == 0.3

    def test_update_ab_test_invalid_split(self, client):
        """Test invalid traffic split value."""
        response = client.put(
            "/api/v1/model-router/ab-test",
            json={"traffic_split": 1.5},  # Invalid, must be 0-1
        )

        assert response.status_code == 422  # Validation error


class TestInvestigationCosts:
    """Tests for investigation costs endpoint."""

    def test_get_investigation_costs(self, client):
        """Test getting investigation costs."""
        response = client.get("/api/v1/model-router/costs")

        assert response.status_code == 200
        data = response.json()
        assert "investigations" in data
        assert "total_cost" in data
        assert "period" in data

    def test_get_investigation_costs_with_limit(self, client):
        """Test costs with custom limit."""
        response = client.get("/api/v1/model-router/costs?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data["investigations"]) <= 5

    def test_investigation_cost_structure(self, client):
        """Test investigation cost item structure."""
        response = client.get("/api/v1/model-router/costs")

        data = response.json()
        if data["investigations"]:
            inv = data["investigations"][0]
            assert "id" in inv
            assert "task" in inv
            assert "model_used" in inv
            assert "tier" in inv
            assert "tokens" in inv
            assert "cost" in inv
            assert "timestamp" in inv


class TestRefreshConfig:
    """Tests for config refresh endpoint."""

    def test_refresh_config_success(self, client):
        """Test refreshing router configuration."""
        response = client.post("/api/v1/model-router/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
