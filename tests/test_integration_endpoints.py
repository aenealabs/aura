"""
Tests for Integration Hub API Endpoints (Issue #34).

Tests the REST API endpoints for managing external integrations.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.integration_endpoints import (
    AuthType,
    IntegrationCategory,
    IntegrationStatus,
    SyncFrequency,
    _configured_integrations,
    integration_router,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def test_client():
    """Create a test client for the integration endpoints."""
    app = FastAPI()
    app.include_router(integration_router)

    # Clear store before each test
    _configured_integrations.clear()

    return TestClient(app)


@pytest.fixture
def sample_integration_data():
    """Sample data for creating an integration."""
    return {
        "connector_id": "crowdstrike",
        "name": "CrowdStrike Production",
        "description": "Production CrowdStrike integration",
        "config": {
            "client_id": "test-client-id",
            "client_secret": "test-secret",
            "base_url": "https://api.crowdstrike.com",
        },
        "sync_frequency": "daily",
        "field_mappings": [],
    }


# ============================================================================
# Available Integrations Tests
# ============================================================================


class TestAvailableIntegrations:
    """Tests for GET /api/v1/integrations/available endpoint."""

    def test_list_available_integrations(self, test_client):
        """Test listing all available integrations."""
        response = test_client.get("/api/v1/integrations/available")

        assert response.status_code == 200
        data = response.json()

        assert "integrations" in data
        assert "categories" in data
        assert len(data["integrations"]) > 0
        assert (
            len(data["categories"]) == 6
        )  # security, cicd, monitoring, cloud, communication, ticketing

    def test_list_available_by_category(self, test_client):
        """Test filtering available integrations by category."""
        response = test_client.get("/api/v1/integrations/available?category=security")

        assert response.status_code == 200
        data = response.json()

        # All returned integrations should be security category
        for integration in data["integrations"]:
            assert integration["category"] == "security"

    def test_available_integration_structure(self, test_client):
        """Test that available integrations have required fields."""
        response = test_client.get("/api/v1/integrations/available")

        assert response.status_code == 200
        data = response.json()

        for integration in data["integrations"]:
            assert "id" in integration
            assert "name" in integration
            assert "description" in integration
            assert "category" in integration
            assert "icon" in integration
            assert "auth_type" in integration
            assert "config_fields" in integration
            assert "features" in integration

    def test_available_integration_config_fields(self, test_client):
        """Test that config fields have proper structure."""
        response = test_client.get("/api/v1/integrations/available")

        assert response.status_code == 200
        data = response.json()

        for integration in data["integrations"]:
            for field in integration["config_fields"]:
                assert "name" in field
                assert "label" in field
                assert "type" in field
                assert "required" in field


# ============================================================================
# Create Integration Tests
# ============================================================================


class TestCreateIntegration:
    """Tests for POST /api/v1/integrations endpoint."""

    def test_create_integration_success(self, test_client, sample_integration_data):
        """Test successfully creating an integration."""
        response = test_client.post(
            "/api/v1/integrations",
            json=sample_integration_data,
        )

        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["name"] == sample_integration_data["name"]
        assert data["connector_id"] == sample_integration_data["connector_id"]
        assert data["status"] == "pending"
        assert data["category"] == "security"
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_integration_masks_secrets(
        self, test_client, sample_integration_data
    ):
        """Test that sensitive fields are masked in response."""
        response = test_client.post(
            "/api/v1/integrations",
            json=sample_integration_data,
        )

        assert response.status_code == 201
        data = response.json()

        # Password fields should be masked
        assert data["config"]["client_secret"] == "••••••••"
        # Non-password fields should not be masked
        assert data["config"]["client_id"] == "test-client-id"

    def test_create_integration_unknown_connector(self, test_client):
        """Test creating integration with unknown connector fails."""
        response = test_client.post(
            "/api/v1/integrations",
            json={
                "connector_id": "unknown-connector",
                "name": "Test",
                "config": {},
            },
        )

        assert response.status_code == 400
        assert "Unknown connector" in response.json()["detail"]

    def test_create_integration_missing_required_fields(self, test_client):
        """Test creating integration without required config fields."""
        response = test_client.post(
            "/api/v1/integrations",
            json={
                "connector_id": "crowdstrike",
                "name": "Test",
                "config": {
                    "client_id": "test",
                    # Missing required fields: client_secret, base_url
                },
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert "errors" in data["detail"]

    def test_create_integration_sync_frequency(
        self, test_client, sample_integration_data
    ):
        """Test creating integration with different sync frequencies."""
        for frequency in ["realtime", "hourly", "daily", "weekly", "manual"]:
            sample_integration_data["sync_frequency"] = frequency
            sample_integration_data["name"] = f"Test {frequency}"

            response = test_client.post(
                "/api/v1/integrations",
                json=sample_integration_data,
            )

            assert response.status_code == 201
            assert response.json()["sync_frequency"] == frequency


# ============================================================================
# Get Integration Tests
# ============================================================================


class TestGetIntegration:
    """Tests for GET /api/v1/integrations/{id} endpoint."""

    def test_get_integration_success(self, test_client, sample_integration_data):
        """Test getting an integration by ID."""
        # Create first
        create_response = test_client.post(
            "/api/v1/integrations",
            json=sample_integration_data,
        )
        integration_id = create_response.json()["id"]

        # Then retrieve
        response = test_client.get(f"/api/v1/integrations/{integration_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == integration_id
        assert data["name"] == sample_integration_data["name"]

    def test_get_integration_not_found(self, test_client):
        """Test getting a non-existent integration."""
        response = test_client.get("/api/v1/integrations/non-existent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


# ============================================================================
# List Integrations Tests
# ============================================================================


class TestListIntegrations:
    """Tests for GET /api/v1/integrations endpoint."""

    def test_list_integrations_empty(self, test_client):
        """Test listing when no integrations exist."""
        response = test_client.get("/api/v1/integrations")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["integrations"] == []

    def test_list_integrations_with_data(self, test_client, sample_integration_data):
        """Test listing integrations with data."""
        # Create a few integrations
        for i in range(3):
            sample_integration_data["name"] = f"Integration {i}"
            test_client.post("/api/v1/integrations", json=sample_integration_data)

        response = test_client.get("/api/v1/integrations")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["integrations"]) == 3

    def test_list_integrations_filter_by_category(
        self, test_client, sample_integration_data
    ):
        """Test filtering integrations by category."""
        # Create security integration
        test_client.post("/api/v1/integrations", json=sample_integration_data)

        # Create cicd integration
        test_client.post(
            "/api/v1/integrations",
            json={
                "connector_id": "github",
                "name": "GitHub",
                "config": {"token": "test-token"},
            },
        )

        response = test_client.get("/api/v1/integrations?category=security")

        assert response.status_code == 200
        data = response.json()
        assert all(i["category"] == "security" for i in data["integrations"])

    def test_list_integrations_pagination(self, test_client, sample_integration_data):
        """Test pagination of integrations list."""
        # Create 5 integrations
        for i in range(5):
            sample_integration_data["name"] = f"Integration {i}"
            test_client.post("/api/v1/integrations", json=sample_integration_data)

        # Get first 2
        response = test_client.get("/api/v1/integrations?limit=2&offset=0")
        data = response.json()
        assert len(data["integrations"]) == 2
        assert data["total"] == 5

        # Get next 2
        response = test_client.get("/api/v1/integrations?limit=2&offset=2")
        data = response.json()
        assert len(data["integrations"]) == 2


# ============================================================================
# Update Integration Tests
# ============================================================================


class TestUpdateIntegration:
    """Tests for PUT /api/v1/integrations/{id} endpoint."""

    def test_update_integration_name(self, test_client, sample_integration_data):
        """Test updating an integration name."""
        # Create first
        create_response = test_client.post(
            "/api/v1/integrations",
            json=sample_integration_data,
        )
        integration_id = create_response.json()["id"]

        # Update
        response = test_client.put(
            f"/api/v1/integrations/{integration_id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    def test_update_integration_config(self, test_client, sample_integration_data):
        """Test updating integration config resets status."""
        # Create first
        create_response = test_client.post(
            "/api/v1/integrations",
            json=sample_integration_data,
        )
        integration_id = create_response.json()["id"]

        # Update config
        response = test_client.put(
            f"/api/v1/integrations/{integration_id}",
            json={
                "config": {
                    "client_id": "new-client-id",
                    "client_secret": "new-secret",
                    "base_url": "https://api.us-2.crowdstrike.com",
                },
            },
        )

        assert response.status_code == 200
        # Status should be reset to pending when config changes
        assert response.json()["status"] == "pending"

    def test_update_integration_not_found(self, test_client):
        """Test updating a non-existent integration."""
        response = test_client.put(
            "/api/v1/integrations/non-existent-id",
            json={"name": "Test"},
        )

        assert response.status_code == 404


# ============================================================================
# Delete Integration Tests
# ============================================================================


class TestDeleteIntegration:
    """Tests for DELETE /api/v1/integrations/{id} endpoint."""

    def test_delete_integration_success(self, test_client, sample_integration_data):
        """Test deleting an integration."""
        # Create first
        create_response = test_client.post(
            "/api/v1/integrations",
            json=sample_integration_data,
        )
        integration_id = create_response.json()["id"]

        # Delete
        response = test_client.delete(f"/api/v1/integrations/{integration_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = test_client.get(f"/api/v1/integrations/{integration_id}")
        assert get_response.status_code == 404

    def test_delete_integration_not_found(self, test_client):
        """Test deleting a non-existent integration."""
        response = test_client.delete("/api/v1/integrations/non-existent-id")
        assert response.status_code == 404


# ============================================================================
# Test Connection Tests
# ============================================================================


class TestConnectionTest:
    """Tests for POST /api/v1/integrations/{id}/test endpoint."""

    def test_test_connection(self, test_client, sample_integration_data):
        """Test the connection test endpoint."""
        # Create first
        create_response = test_client.post(
            "/api/v1/integrations",
            json=sample_integration_data,
        )
        integration_id = create_response.json()["id"]

        # Test connection
        response = test_client.post(f"/api/v1/integrations/{integration_id}/test")

        assert response.status_code == 200
        data = response.json()

        assert "success" in data
        assert "message" in data
        assert "tested_at" in data

    def test_test_connection_not_found(self, test_client):
        """Test connection test on non-existent integration."""
        response = test_client.post("/api/v1/integrations/non-existent-id/test")
        assert response.status_code == 404

    def test_test_connection_updates_status(self, test_client, sample_integration_data):
        """Test that connection test updates integration status."""
        # Create first
        create_response = test_client.post(
            "/api/v1/integrations",
            json=sample_integration_data,
        )
        integration_id = create_response.json()["id"]

        # Test connection (may succeed or fail, but status should change)
        test_client.post(f"/api/v1/integrations/{integration_id}/test")

        # Get updated integration
        response = test_client.get(f"/api/v1/integrations/{integration_id}")
        data = response.json()

        # Status should no longer be pending
        assert data["status"] in ["connected", "error"]


# ============================================================================
# Enum Tests
# ============================================================================


class TestEnums:
    """Tests for API enums."""

    def test_integration_category_enum(self):
        """Test IntegrationCategory enum values."""
        assert IntegrationCategory.SECURITY.value == "security"
        assert IntegrationCategory.CICD.value == "cicd"
        assert IntegrationCategory.MONITORING.value == "monitoring"
        assert IntegrationCategory.CLOUD.value == "cloud"
        assert IntegrationCategory.COMMUNICATION.value == "communication"
        assert IntegrationCategory.TICKETING.value == "ticketing"

    def test_integration_status_enum(self):
        """Test IntegrationStatus enum values."""
        assert IntegrationStatus.CONNECTED.value == "connected"
        assert IntegrationStatus.DISCONNECTED.value == "disconnected"
        assert IntegrationStatus.ERROR.value == "error"
        assert IntegrationStatus.PENDING.value == "pending"

    def test_auth_type_enum(self):
        """Test AuthType enum values."""
        assert AuthType.API_KEY.value == "api_key"
        assert AuthType.OAUTH2.value == "oauth2"
        assert AuthType.BASIC.value == "basic"
        assert AuthType.TOKEN.value == "token"
        assert AuthType.CERTIFICATE.value == "certificate"

    def test_sync_frequency_enum(self):
        """Test SyncFrequency enum values."""
        assert SyncFrequency.REALTIME.value == "realtime"
        assert SyncFrequency.HOURLY.value == "hourly"
        assert SyncFrequency.DAILY.value == "daily"
        assert SyncFrequency.WEEKLY.value == "weekly"
        assert SyncFrequency.MANUAL.value == "manual"


# ============================================================================
# Available Connectors Tests
# ============================================================================


class TestAvailableConnectors:
    """Tests for available connector catalog."""

    def test_crowdstrike_connector(self, test_client):
        """Test CrowdStrike connector configuration."""
        response = test_client.get("/api/v1/integrations/available")
        data = response.json()

        crowdstrike = next(
            (i for i in data["integrations"] if i["id"] == "crowdstrike"), None
        )
        assert crowdstrike is not None
        assert crowdstrike["name"] == "CrowdStrike Falcon"
        assert crowdstrike["category"] == "security"
        assert crowdstrike["auth_type"] == "oauth2"
        assert "vulnerability-sync" in crowdstrike["features"]

    def test_github_connector(self, test_client):
        """Test GitHub connector configuration."""
        response = test_client.get("/api/v1/integrations/available")
        data = response.json()

        github = next((i for i in data["integrations"] if i["id"] == "github"), None)
        assert github is not None
        assert github["name"] == "GitHub"
        assert github["category"] == "cicd"
        assert github["auth_type"] == "token"

    def test_jira_connector(self, test_client):
        """Test Jira connector configuration."""
        response = test_client.get("/api/v1/integrations/available")
        data = response.json()

        jira = next((i for i in data["integrations"] if i["id"] == "jira"), None)
        assert jira is not None
        assert jira["name"] == "Jira"
        assert jira["category"] == "ticketing"


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegrationWorkflows:
    """Tests for complete integration workflows."""

    def test_full_integration_lifecycle(self, test_client, sample_integration_data):
        """Test complete lifecycle: create -> test -> update -> delete."""
        # 1. Create
        create_response = test_client.post(
            "/api/v1/integrations",
            json=sample_integration_data,
        )
        assert create_response.status_code == 201
        integration_id = create_response.json()["id"]

        # 2. Test connection
        test_response = test_client.post(f"/api/v1/integrations/{integration_id}/test")
        assert test_response.status_code == 200

        # 3. Update
        update_response = test_client.put(
            f"/api/v1/integrations/{integration_id}",
            json={"name": "Updated Integration", "sync_frequency": "hourly"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Integration"
        assert update_response.json()["sync_frequency"] == "hourly"

        # 4. Verify in list
        list_response = test_client.get("/api/v1/integrations")
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1

        # 5. Delete
        delete_response = test_client.delete(f"/api/v1/integrations/{integration_id}")
        assert delete_response.status_code == 204

        # 6. Verify deleted
        list_response = test_client.get("/api/v1/integrations")
        assert list_response.json()["total"] == 0

    def test_multiple_integrations_same_connector(
        self, test_client, sample_integration_data
    ):
        """Test creating multiple integrations of the same connector type."""
        # Create two CrowdStrike integrations
        sample_integration_data["name"] = "CrowdStrike Prod"
        test_client.post("/api/v1/integrations", json=sample_integration_data)

        sample_integration_data["name"] = "CrowdStrike Staging"
        test_client.post("/api/v1/integrations", json=sample_integration_data)

        response = test_client.get("/api/v1/integrations")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert all(i["connector_id"] == "crowdstrike" for i in data["integrations"])
