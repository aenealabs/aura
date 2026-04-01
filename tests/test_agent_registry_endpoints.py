"""
Tests for Agent Registry UI Endpoints (GitHub Issue #35)

Tests the Agent Registry and Marketplace API endpoints for:
- Listing internal and external agents
- Browsing marketplace agents
- Connecting and disconnecting agents
- Agent configuration and metrics
- Connection testing
"""

import pytest

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def client():
    """Create a test client for the API.

    Uses module scope to ensure consistent FastAPI validation behavior
    across all tests in this module. All imports are inside the fixture
    to defer loading until test execution time.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.api.agent_registry_endpoints import router

    app = FastAPI()
    app.include_router(router)

    yield TestClient(app)


@pytest.fixture
def sample_connect_request():
    """Sample request to connect an agent."""
    return {
        "agent_id": "snyk-scanner",
        "endpoint": "https://api.snyk.io/a2a",
        "api_key": "test-api-key",
        "custom_config": {"timeout": 30000},
    }


# =============================================================================
# Test List All Agents
# =============================================================================


class TestListAllAgents:
    """Tests for GET /api/v1/agents endpoint."""

    def test_list_all_agents_success(self, client):
        """Test listing all agents returns internal and external."""
        response = client.get("/api/v1/agents")
        assert response.status_code == 200

        data = response.json()
        assert "agents" in data
        assert "total" in data
        assert "internal_count" in data
        assert "external_count" in data
        assert data["total"] > 0

    def test_list_agents_filter_by_type_internal(self, client):
        """Test filtering agents by internal type."""
        response = client.get("/api/v1/agents?agent_type=internal")
        assert response.status_code == 200

        data = response.json()
        for agent in data["agents"]:
            assert agent["agent_type"] == "internal"

    def test_list_agents_filter_by_type_external(self, client):
        """Test filtering agents by external type."""
        response = client.get("/api/v1/agents?agent_type=external")
        assert response.status_code == 200

        data = response.json()
        for agent in data["agents"]:
            assert agent["agent_type"] == "external"

    def test_list_agents_filter_by_status(self, client):
        """Test filtering agents by status."""
        response = client.get("/api/v1/agents?status=active")
        assert response.status_code == 200

        data = response.json()
        for agent in data["agents"]:
            assert agent["status"] == "active"

    def test_list_agents_filter_by_capability(self, client):
        """Test filtering agents by capability."""
        response = client.get("/api/v1/agents?capability=orchestrate")
        assert response.status_code == 200

        data = response.json()
        for agent in data["agents"]:
            assert "orchestrate" in agent["capabilities"]

    def test_list_agents_search_by_name(self, client):
        """Test searching agents by name."""
        response = client.get("/api/v1/agents?search=coder")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] > 0
        # At least one result should contain 'coder' in name
        assert any("coder" in a["name"].lower() for a in data["agents"])

    def test_list_agents_pagination(self, client):
        """Test pagination parameters."""
        response = client.get("/api/v1/agents?limit=2&offset=0")
        assert response.status_code == 200

        data = response.json()
        assert len(data["agents"]) <= 2


# =============================================================================
# Test Internal Agents
# =============================================================================


class TestInternalAgents:
    """Tests for GET /api/v1/agents/internal endpoint."""

    def test_list_internal_agents_success(self, client):
        """Test listing internal Aura agents."""
        response = client.get("/api/v1/agents/internal")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 4  # Orchestrator, Coder, Reviewer, Validator

    def test_internal_agents_have_required_fields(self, client):
        """Test internal agents have all required fields."""
        response = client.get("/api/v1/agents/internal")
        data = response.json()

        required_fields = [
            "agent_id",
            "name",
            "description",
            "agent_type",
            "status",
            "capabilities",
            "metrics",
        ]

        for agent in data:
            for field in required_fields:
                assert field in agent, f"Missing field: {field}"
            assert agent["agent_type"] == "internal"

    def test_internal_agents_have_metrics(self, client):
        """Test internal agents have usage metrics."""
        response = client.get("/api/v1/agents/internal")
        data = response.json()

        for agent in data:
            assert "metrics" in agent
            metrics = agent["metrics"]
            assert "requests_today" in metrics
            assert "avg_latency_ms" in metrics
            assert "success_rate" in metrics


# =============================================================================
# Test External Agents
# =============================================================================


class TestExternalAgents:
    """Tests for GET /api/v1/agents/external endpoint."""

    def test_list_external_agents_success(self, client):
        """Test listing external A2A agents."""
        response = client.get("/api/v1/agents/external")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

    def test_external_agents_have_required_fields(self, client):
        """Test external agents have all required fields."""
        response = client.get("/api/v1/agents/external")
        data = response.json()

        if len(data) > 0:
            required_fields = [
                "agent_id",
                "name",
                "description",
                "agent_type",
                "status",
                "trust_level",
                "capabilities",
                "provider",
                "endpoint",
                "protocol_version",
            ]

            for agent in data:
                for field in required_fields:
                    assert field in agent, f"Missing field: {field}"
                assert agent["agent_type"] == "external"

    def test_external_agents_filter_by_status(self, client):
        """Test filtering external agents by status."""
        response = client.get("/api/v1/agents/external?status=active")
        assert response.status_code == 200

        data = response.json()
        for agent in data:
            assert agent["status"] == "active"


# =============================================================================
# Test Marketplace
# =============================================================================


class TestMarketplace:
    """Tests for GET /api/v1/agents/marketplace endpoint."""

    def test_list_marketplace_agents_success(self, client):
        """Test listing marketplace agents."""
        response = client.get("/api/v1/agents/marketplace")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_marketplace_agents_have_required_fields(self, client):
        """Test marketplace agents have all required fields."""
        response = client.get("/api/v1/agents/marketplace")
        data = response.json()

        required_fields = [
            "agent_id",
            "name",
            "description",
            "provider",
            "capabilities",
            "protocol_version",
            "verified",
        ]

        for agent in data:
            for field in required_fields:
                assert field in agent, f"Missing field: {field}"
            assert agent["agent_type"] == "marketplace"

    def test_marketplace_filter_by_provider(self, client):
        """Test filtering marketplace by provider."""
        response = client.get("/api/v1/agents/marketplace?provider=snyk")
        assert response.status_code == 200

        data = response.json()
        for agent in data:
            assert agent["provider"].lower() == "snyk"

    def test_marketplace_filter_verified_only(self, client):
        """Test filtering marketplace for verified agents only."""
        response = client.get("/api/v1/agents/marketplace?verified_only=true")
        assert response.status_code == 200

        data = response.json()
        for agent in data:
            assert agent["verified"] is True

    def test_marketplace_filter_by_capability(self, client):
        """Test filtering marketplace by capability."""
        response = client.get(
            "/api/v1/agents/marketplace?capability=scan_vulnerabilities"
        )
        assert response.status_code == 200

        data = response.json()
        for agent in data:
            assert "scan_vulnerabilities" in agent["capabilities"]

    def test_marketplace_filter_by_pricing_tier(self, client):
        """Test filtering marketplace by pricing tier."""
        response = client.get("/api/v1/agents/marketplace?pricing_tier=free")
        assert response.status_code == 200

        data = response.json()
        for agent in data:
            assert agent["pricing_tier"] == "free"


# =============================================================================
# Test Get Agent Details
# =============================================================================


class TestGetAgentDetails:
    """Tests for GET /api/v1/agents/{agent_id} endpoint."""

    def test_get_internal_agent_success(self, client):
        """Test getting details for an internal agent."""
        response = client.get("/api/v1/agents/aura-coder")
        assert response.status_code == 200

        data = response.json()
        assert data["agent_id"] == "aura-coder"
        assert data["agent_type"] == "internal"
        assert "capabilities" in data
        assert "metrics" in data

    def test_get_external_agent_success(self, client):
        """Test getting details for an external agent."""
        response = client.get("/api/v1/agents/foundry-research")
        assert response.status_code == 200

        data = response.json()
        assert data["agent_id"] == "foundry-research"
        assert data["agent_type"] == "external"
        assert "provider" in data
        assert "endpoint" in data

    def test_get_marketplace_agent_success(self, client):
        """Test getting details for a marketplace agent."""
        response = client.get("/api/v1/agents/snyk-scanner")
        assert response.status_code == 200

        data = response.json()
        assert data["agent_id"] == "snyk-scanner"
        assert data["agent_type"] == "marketplace"

    def test_get_nonexistent_agent_returns_404(self, client):
        """Test getting a non-existent agent returns 404."""
        response = client.get("/api/v1/agents/nonexistent-agent")
        assert response.status_code == 404


# =============================================================================
# Test Connect Agent
# =============================================================================


class TestConnectAgent:
    """Tests for POST /api/v1/agents/connect endpoint."""

    def test_connect_agent_success(self, client, sample_connect_request):
        """Test connecting a marketplace agent."""
        response = client.post("/api/v1/agents/connect", json=sample_connect_request)
        assert response.status_code == 201

        data = response.json()
        assert data["agent_id"] == sample_connect_request["agent_id"]
        assert data["status"] == "pending"
        assert "trust_level" in data
        assert "connected_at" in data

    def test_connect_agent_without_endpoint_fails(self, client):
        """Test connecting without endpoint fails validation."""
        response = client.post(
            "/api/v1/agents/connect",
            json={"agent_id": "snyk-scanner"},
        )
        assert response.status_code == 422  # Validation error

    def test_connect_nonexistent_agent_fails(self, client):
        """Test connecting a non-existent agent returns 404."""
        response = client.post(
            "/api/v1/agents/connect",
            json={
                "agent_id": "nonexistent-agent",
                "endpoint": "https://example.com/a2a",
            },
        )
        assert response.status_code == 404

    def test_connect_already_connected_agent_fails(self, client):
        """Test connecting an already connected agent returns 409."""
        # First connect an agent
        client.post(
            "/api/v1/agents/connect",
            json={
                "agent_id": "trivy-scanner",
                "endpoint": "https://trivy.aquasec.com/a2a",
            },
        )

        # Try to connect the same agent again
        response = client.post(
            "/api/v1/agents/connect",
            json={
                "agent_id": "trivy-scanner",
                "endpoint": "https://trivy.aquasec.com/a2a",
            },
        )
        assert response.status_code == 409

        # Cleanup
        client.delete("/api/v1/agents/trivy-scanner")


# =============================================================================
# Test Disconnect Agent
# =============================================================================


class TestDisconnectAgent:
    """Tests for DELETE /api/v1/agents/{agent_id} endpoint."""

    def test_disconnect_external_agent_success(self, client, sample_connect_request):
        """Test disconnecting an external agent."""
        # First connect an agent
        client.post("/api/v1/agents/connect", json=sample_connect_request)

        # Then disconnect it
        response = client.delete(f"/api/v1/agents/{sample_connect_request['agent_id']}")
        assert response.status_code == 204

    def test_disconnect_internal_agent_fails(self, client):
        """Test disconnecting an internal agent returns 400."""
        response = client.delete("/api/v1/agents/aura-coder")
        assert response.status_code == 400

    def test_disconnect_nonexistent_agent_fails(self, client):
        """Test disconnecting a non-existent agent returns 404."""
        response = client.delete("/api/v1/agents/nonexistent-agent")
        assert response.status_code == 404


# =============================================================================
# Test Update Agent Config
# =============================================================================


class TestUpdateAgentConfig:
    """Tests for PUT /api/v1/agents/{agent_id}/config endpoint."""

    def test_update_internal_agent_config(self, client):
        """Test updating internal agent configuration."""
        response = client.put(
            "/api/v1/agents/aura-coder/config",
            json={"enabled": False},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "suspended"

        # Re-enable
        response = client.put(
            "/api/v1/agents/aura-coder/config",
            json={"enabled": True},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    def test_update_external_agent_config(self, client):
        """Test updating external agent configuration."""
        response = client.put(
            "/api/v1/agents/foundry-research/config",
            json={
                "enabled": True,
                "custom_config": {"timeout": 60000},
            },
        )
        assert response.status_code == 200

    def test_update_nonexistent_agent_fails(self, client):
        """Test updating a non-existent agent returns 404."""
        response = client.put(
            "/api/v1/agents/nonexistent-agent/config",
            json={"enabled": False},
        )
        assert response.status_code == 404


# =============================================================================
# Test Agent Metrics
# =============================================================================


class TestAgentMetrics:
    """Tests for GET /api/v1/agents/{agent_id}/metrics endpoint."""

    def test_get_internal_agent_metrics(self, client):
        """Test getting metrics for an internal agent."""
        response = client.get("/api/v1/agents/aura-coder/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "requests_today" in data
        assert "requests_total" in data
        assert "avg_latency_ms" in data
        assert "success_rate" in data

    def test_get_external_agent_metrics(self, client):
        """Test getting metrics for an external agent."""
        response = client.get("/api/v1/agents/foundry-research/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "requests_today" in data
        assert "success_rate" in data

    def test_get_metrics_nonexistent_agent_fails(self, client):
        """Test getting metrics for a non-existent agent returns 404."""
        response = client.get("/api/v1/agents/nonexistent-agent/metrics")
        assert response.status_code == 404


# =============================================================================
# Test Connection Testing
# =============================================================================


class TestConnectionTesting:
    """Tests for POST /api/v1/agents/{agent_id}/test endpoint."""

    def test_test_internal_agent_connection(self, client):
        """Test testing connection to an internal agent."""
        response = client.post("/api/v1/agents/aura-coder/test")
        assert response.status_code == 200

        data = response.json()
        assert data["agent_id"] == "aura-coder"
        assert data["status"] == "healthy"
        assert "latency_ms" in data
        assert "tested_at" in data

    def test_test_external_agent_connection(self, client):
        """Test testing connection to an external agent."""
        response = client.post("/api/v1/agents/foundry-research/test")
        assert response.status_code == 200

        data = response.json()
        assert data["agent_id"] == "foundry-research"
        assert data["status"] in ["healthy", "degraded"]
        assert "latency_ms" in data

    def test_test_nonexistent_agent_fails(self, client):
        """Test testing a non-existent agent returns 404."""
        response = client.post("/api/v1/agents/nonexistent-agent/test")
        assert response.status_code == 404


# =============================================================================
# Test Enums and Constants
# =============================================================================


class TestEnums:
    """Tests for enum values."""

    def test_agent_type_values(self):
        """Test AgentType enum values."""
        from src.api.agent_registry_endpoints import AgentType

        assert AgentType.INTERNAL.value == "internal"
        assert AgentType.EXTERNAL.value == "external"
        assert AgentType.MARKETPLACE.value == "marketplace"

    def test_agent_status_values(self):
        """Test AgentStatus enum values."""
        from src.api.agent_registry_endpoints import AgentStatus

        assert AgentStatus.ACTIVE.value == "active"
        assert AgentStatus.INACTIVE.value == "inactive"
        assert AgentStatus.DEGRADED.value == "degraded"
        assert AgentStatus.PENDING.value == "pending"
        assert AgentStatus.SUSPENDED.value == "suspended"

    def test_trust_level_values(self):
        """Test TrustLevel enum values."""
        from src.api.agent_registry_endpoints import TrustLevel

        assert TrustLevel.VERIFIED.value == "verified"
        assert TrustLevel.TRUSTED.value == "trusted"
        assert TrustLevel.STANDARD.value == "standard"
        assert TrustLevel.UNTRUSTED.value == "untrusted"


# =============================================================================
# Test Agent Workflows
# =============================================================================


class TestAgentWorkflows:
    """Integration tests for complete agent workflows."""

    def test_full_connect_test_disconnect_workflow(self, client):
        """Test the full workflow of connecting, testing, and disconnecting an agent."""
        # Step 1: Connect agent from marketplace
        connect_response = client.post(
            "/api/v1/agents/connect",
            json={
                "agent_id": "datadog-apm",
                "endpoint": "https://api.datadoghq.com/a2a",
            },
        )
        assert connect_response.status_code == 201
        assert connect_response.json()["status"] == "pending"

        # Step 2: Verify agent appears in external list
        external_response = client.get("/api/v1/agents/external")
        agent_ids = [a["agent_id"] for a in external_response.json()]
        assert "datadog-apm" in agent_ids

        # Step 3: Test connection
        test_response = client.post("/api/v1/agents/datadog-apm/test")
        assert test_response.status_code == 200
        assert test_response.json()["status"] in ["healthy", "degraded"]

        # Step 4: Get agent details
        detail_response = client.get("/api/v1/agents/datadog-apm")
        assert detail_response.status_code == 200
        assert detail_response.json()["agent_type"] == "external"

        # Step 5: Disconnect
        disconnect_response = client.delete("/api/v1/agents/datadog-apm")
        assert disconnect_response.status_code == 204

        # Step 6: Verify agent no longer in external list
        external_response = client.get("/api/v1/agents/external")
        agent_ids = [a["agent_id"] for a in external_response.json()]
        assert "datadog-apm" not in agent_ids

    def test_marketplace_excludes_connected_agents(self, client):
        """Test that marketplace doesn't show already connected agents."""
        # Get initial marketplace
        initial_response = client.get("/api/v1/agents/marketplace")
        initial_agents = [a["agent_id"] for a in initial_response.json()]
        assert "semgrep-sast" in initial_agents

        # Connect an agent
        client.post(
            "/api/v1/agents/connect",
            json={
                "agent_id": "semgrep-sast",
                "endpoint": "https://semgrep.dev/a2a",
            },
        )

        # Marketplace should no longer show connected agent
        updated_response = client.get("/api/v1/agents/marketplace")
        updated_agents = [a["agent_id"] for a in updated_response.json()]
        assert "semgrep-sast" not in updated_agents

        # Cleanup: disconnect
        client.delete("/api/v1/agents/semgrep-sast")
