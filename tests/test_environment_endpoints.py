"""
Project Aura - Environment Endpoints Tests

API endpoint tests for the environment provisioning endpoints.

Author: Project Aura Team
Created: 2025-12-14

Note: Uses lazy imports inside fixtures to ensure fresh module state
in forked test processes. Module-level imports of src.* modules would
create stale references after process fork.
"""

import os

# Run tests in separate processes to avoid FastAPI dependency injection pollution.
# On Linux (CI), pytest-forked has issues with FastAPI router state, so we skip forked mode there.
import platform
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    user = MagicMock()
    user.user_id = "user-123"
    user.organization_id = "org-456"
    user.email = "test@example.com"
    user.is_admin = False
    return user


@pytest.fixture
def admin_user():
    """Create a mock admin user."""
    user = MagicMock()
    user.user_id = "admin-001"
    user.organization_id = "org-456"
    user.email = "admin@example.com"
    user.is_admin = True
    return user


@pytest.fixture
def sample_environment():
    """Create a sample environment for testing."""
    # Lazy import for fork-safe module state
    from src.services.environment_provisioning_service import (
        EnvironmentStatus,
        EnvironmentType,
        TestEnvironment,
    )

    now = datetime.now(timezone.utc)
    return TestEnvironment(
        environment_id="env-abc123def456",
        user_id="user-123",
        organization_id="org-456",
        environment_type=EnvironmentType.STANDARD,
        template_id="python-fastapi",
        display_name="Test Environment",
        status=EnvironmentStatus.ACTIVE,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=24)).isoformat(),
        dns_name="env-abc123def456.test.aura.local",
        cost_estimate_daily=0.50,
        last_activity_at=now.isoformat(),
    )


@pytest.fixture
def app_with_service(mock_user):
    """Create a test FastAPI app with isolated service - returns (app, service) tuple."""
    from src.api.auth import get_current_user
    from src.api.environment_endpoints import router, set_environment_service
    from src.services.api_rate_limiter import (
        RateLimitResult,
        RateLimitTier,
        standard_rate_limit,
    )
    from src.services.environment_provisioning_service import (
        EnvironmentProvisioningService,
        PersistenceMode,
    )

    with patch.dict(os.environ, {"ENVIRONMENT": "test", "PROJECT_NAME": "aura"}):
        # Create fresh service instance for this test
        service = EnvironmentProvisioningService(mode=PersistenceMode.MOCK)

        # Set the service directly on the module
        set_environment_service(service)

        try:
            test_app = FastAPI()
            test_app.include_router(router)

            # CRITICAL: Use async functions to match the original dependency signatures
            async def override_get_current_user():
                return mock_user

            mock_rate_result = RateLimitResult(
                allowed=True,
                remaining=999,
                reset_at=time.time() + 60,
                limit=1000,
                tier=RateLimitTier.STANDARD,
                client_id="test",
            )

            def override_rate_limit():
                return mock_rate_result

            test_app.dependency_overrides[get_current_user] = override_get_current_user
            test_app.dependency_overrides[standard_rate_limit] = override_rate_limit

            yield test_app, service
        finally:
            # Clean up service reference
            set_environment_service(None)


@pytest.fixture
def client_with_service(app_with_service):
    """Create a test client that returns (client, service) tuple."""
    app, service = app_with_service
    return TestClient(app), service


@pytest.fixture
def client(app_with_service):
    """Create a test client."""
    app, _ = app_with_service
    return TestClient(app)


# ============================================================================
# Template Endpoint Tests
# ============================================================================


class TestListTemplates:
    """Tests for GET /api/v1/environments/templates."""

    def test_list_templates_success(self, client):
        """Test listing all available templates."""
        response = client.get("/api/v1/environments/templates")

        assert response.status_code == 200
        templates = response.json()
        assert isinstance(templates, list)
        assert len(templates) > 0

        # Verify template structure
        template = templates[0]
        assert "template_id" in template
        assert "name" in template
        assert "environment_type" in template
        assert "cost_per_day" in template

    def test_list_templates_includes_all_types(self, client):
        """Test that all environment types are represented."""
        response = client.get("/api/v1/environments/templates")

        templates = response.json()
        types = {t["environment_type"] for t in templates}

        # Should have at least quick and standard
        assert "quick" in types
        assert "standard" in types


# ============================================================================
# Quota Endpoint Tests
# ============================================================================


class TestGetQuota:
    """Tests for GET /api/v1/environments/quota."""

    def test_get_quota_success(self, client):
        """Test getting user quota."""
        response = client.get("/api/v1/environments/quota")

        assert response.status_code == 200
        quota = response.json()

        assert quota["user_id"] == "user-123"
        assert "concurrent_limit" in quota
        assert "active_count" in quota
        assert "available" in quota
        assert "monthly_budget" in quota

    def test_get_quota_no_environments(self, client):
        """Test quota when user has no environments."""
        response = client.get("/api/v1/environments/quota")

        quota = response.json()
        assert quota["active_count"] == 0
        assert quota["available"] == quota["concurrent_limit"]


# ============================================================================
# Health Endpoint Tests
# ============================================================================


class TestHealthCheck:
    """Tests for GET /api/v1/environments/health."""

    def test_health_check_success(self, client):
        """Test health check endpoint."""
        response = client.get("/api/v1/environments/health")

        assert response.status_code == 200
        health = response.json()

        assert health["service"] == "environment_provisioning"
        assert health["mode"] == "mock"
        assert health["healthy"] is True


# ============================================================================
# List Environments Tests
# ============================================================================


class TestListEnvironments:
    """Tests for GET /api/v1/environments."""

    def test_list_environments_empty(self, client):
        """Test listing with no environments."""
        response = client.get("/api/v1/environments")

        assert response.status_code == 200
        data = response.json()
        assert data["environments"] == []
        assert data["total"] == 0

    def test_list_environments_with_data(self, client):
        """Test listing environments with data."""
        # Create an environment via API first
        create_response = client.post(
            "/api/v1/environments",
            json={
                "template_id": "python-fastapi",
                "display_name": "Test Env",
            },
        )
        assert create_response.status_code == 201

        response = client.get("/api/v1/environments")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["environments"]) >= 1

    def test_list_environments_filter_invalid_status(self, client):
        """Test listing with invalid status filter."""
        response = client.get("/api/v1/environments?status=invalid")

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_list_environments_filter_invalid_type(self, client):
        """Test listing with invalid environment type filter."""
        response = client.get("/api/v1/environments?environment_type=invalid")

        assert response.status_code == 400
        assert "Invalid environment_type" in response.json()["detail"]


# ============================================================================
# Create Environment Tests
# ============================================================================


class TestCreateEnvironment:
    """Tests for POST /api/v1/environments."""

    def test_create_environment_success(self, client):
        """Test successful environment creation."""
        response = client.post(
            "/api/v1/environments",
            json={
                "template_id": "python-fastapi",
                "display_name": "My Test Environment",
                "description": "Testing API endpoints",
            },
        )

        assert response.status_code == 201
        env = response.json()

        assert env["environment_id"].startswith("env-")
        assert env["user_id"] == "user-123"
        assert env["template_id"] == "python-fastapi"
        assert env["display_name"] == "My Test Environment"
        assert env["dns_name"].endswith(".test.aura.local")

    def test_create_environment_with_custom_ttl(self, client):
        """Test creation with custom TTL."""
        response = client.post(
            "/api/v1/environments",
            json={
                "template_id": "python-fastapi",
                "display_name": "Custom TTL Test",
                "ttl_hours": 12,
            },
        )

        assert response.status_code == 201

    def test_create_environment_invalid_template(self, client):
        """Test creation with invalid template."""
        response = client.post(
            "/api/v1/environments",
            json={
                "template_id": "nonexistent-template",
                "display_name": "Test",
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_environment_missing_required_fields(self, client):
        """Test creation with missing required fields."""
        response = client.post(
            "/api/v1/environments",
            json={
                "template_id": "python-fastapi",
                # Missing display_name
            },
        )

        assert response.status_code == 422  # Validation error

    def test_create_environment_quota_exceeded(self, client):
        """Test creation when quota is exceeded."""
        # Fill up quota by creating 3 environments
        for i in range(3):
            response = client.post(
                "/api/v1/environments",
                json={
                    "template_id": "quick-test",
                    "display_name": f"Quota Env {i}",
                },
            )
            assert response.status_code == 201, f"Failed on env {i}: {response.json()}"

        # Try to create one more - should fail with quota exceeded
        response = client.post(
            "/api/v1/environments",
            json={
                "template_id": "python-fastapi",
                "display_name": "Over Quota",
            },
        )

        assert response.status_code == 429
        assert "quota" in response.json()["detail"].lower()


# ============================================================================
# Get Environment Tests
# ============================================================================


class TestGetEnvironment:
    """Tests for GET /api/v1/environments/{id}."""

    def test_get_environment_success(self, client):
        """Test getting an existing environment."""
        # Create an environment first
        create_response = client.post(
            "/api/v1/environments",
            json={
                "template_id": "python-fastapi",
                "display_name": "Test Env",
            },
        )
        assert create_response.status_code == 201
        env_id = create_response.json()["environment_id"]

        response = client.get(f"/api/v1/environments/{env_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["environment_id"] == env_id

    def test_get_environment_not_found(self, client):
        """Test getting non-existent environment."""
        response = client.get("/api/v1/environments/env-nonexistent")

        assert response.status_code == 404

    def test_get_environment_forbidden(self, client_with_service):
        """Test accessing another user's environment."""
        # Lazy imports for fork-safe module state
        from src.services.environment_provisioning_service import (
            EnvironmentStatus,
            EnvironmentType,
            TestEnvironment,
        )

        client, service = client_with_service

        # Directly create environment for different user by manipulating service state
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        env_id = "env-other-user-123"
        env = TestEnvironment(
            environment_id=env_id,
            user_id="other-user",
            organization_id="org-456",
            environment_type=EnvironmentType.STANDARD,
            template_id="python-fastapi",
            display_name="Other User Env",
            status=EnvironmentStatus.ACTIVE,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=24)).isoformat(),
            dns_name=f"{env_id}.test.aura.local",
            cost_estimate_daily=0.50,
            last_activity_at=now.isoformat(),
        )
        # CRITICAL: Store as dictionary, not TestEnvironment object
        service.mock_store[env_id] = env.to_dict()

        response = client.get(f"/api/v1/environments/{env_id}")

        assert response.status_code == 403


# ============================================================================
# Terminate Environment Tests
# ============================================================================


class TestTerminateEnvironment:
    """Tests for DELETE /api/v1/environments/{id}."""

    def test_terminate_environment_success(self, client_with_service):
        """Test successful termination."""
        # Lazy import for fork-safe module state
        from src.services.environment_provisioning_service import EnvironmentStatus

        client, service = client_with_service

        # Create an environment
        create_response = client.post(
            "/api/v1/environments",
            json={
                "template_id": "python-fastapi",
                "display_name": "To Terminate",
            },
        )
        assert create_response.status_code == 201
        env_id = create_response.json()["environment_id"]

        response = client.delete(f"/api/v1/environments/{env_id}")

        assert response.status_code == 204

        # Verify status changed by checking service state directly
        # mock_store stores dictionaries, not TestEnvironment objects
        updated_dict = service.mock_store.get(env_id)
        assert updated_dict is not None
        assert updated_dict["status"] == EnvironmentStatus.TERMINATING.value

    def test_terminate_environment_not_found(self, client):
        """Test terminating non-existent environment."""
        response = client.delete("/api/v1/environments/env-nonexistent")

        assert response.status_code == 404

    def test_terminate_environment_forbidden(self, client_with_service):
        """Test terminating another user's environment."""
        # Lazy imports for fork-safe module state
        from src.services.environment_provisioning_service import (
            EnvironmentStatus,
            EnvironmentType,
            TestEnvironment,
        )

        client, service = client_with_service

        # Directly create environment for different user by manipulating service state
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        env_id = "env-other-user-term"
        env = TestEnvironment(
            environment_id=env_id,
            user_id="other-user",
            organization_id="org-456",
            environment_type=EnvironmentType.STANDARD,
            template_id="python-fastapi",
            display_name="Other User Env",
            status=EnvironmentStatus.ACTIVE,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=24)).isoformat(),
            dns_name=f"{env_id}.test.aura.local",
            cost_estimate_daily=0.50,
            last_activity_at=now.isoformat(),
        )
        # CRITICAL: Store as dictionary, not TestEnvironment object
        service.mock_store[env_id] = env.to_dict()

        response = client.delete(f"/api/v1/environments/{env_id}")

        assert response.status_code == 403

    def test_terminate_already_terminated(self, client):
        """Test terminating already terminated environment."""
        # Create environment
        create_response = client.post(
            "/api/v1/environments",
            json={
                "template_id": "python-fastapi",
                "display_name": "Already Terminated",
            },
        )
        assert create_response.status_code == 201
        env_id = create_response.json()["environment_id"]

        # Terminate it via API
        term_response = client.delete(f"/api/v1/environments/{env_id}")
        assert term_response.status_code == 204

        # Try to terminate again
        response = client.delete(f"/api/v1/environments/{env_id}")

        assert response.status_code == 400
        assert "terminating" in response.json()["detail"].lower()


# ============================================================================
# Extend Environment Tests
# ============================================================================


class TestExtendEnvironment:
    """Tests for POST /api/v1/environments/{id}/extend."""

    def test_extend_environment_success(self, client_with_service):
        """Test successful TTL extension."""
        # Lazy import for fork-safe module state
        from src.services.environment_provisioning_service import EnvironmentStatus

        client, service = client_with_service

        # Create an environment
        create_response = client.post(
            "/api/v1/environments",
            json={
                "template_id": "python-fastapi",
                "display_name": "To Extend",
            },
        )
        assert create_response.status_code == 201
        env_id = create_response.json()["environment_id"]
        original_expiry = create_response.json()["expires_at"]

        # Set status to ACTIVE (normally done by provisioning workflow)
        # mock_store stores dictionaries, update the status field directly
        env_dict = service.mock_store.get(env_id)
        assert env_dict is not None
        env_dict["status"] = EnvironmentStatus.ACTIVE.value

        response = client.post(
            f"/api/v1/environments/{env_id}/extend",
            json={"additional_hours": 4},
        )

        assert response.status_code == 200
        extended = response.json()
        assert extended["expires_at"] > original_expiry

    def test_extend_environment_not_found(self, client):
        """Test extending non-existent environment."""
        response = client.post(
            "/api/v1/environments/env-nonexistent/extend",
            json={"additional_hours": 4},
        )

        assert response.status_code == 404

    def test_extend_environment_forbidden(self, client_with_service):
        """Test extending another user's environment."""
        # Lazy imports for fork-safe module state
        from src.services.environment_provisioning_service import (
            EnvironmentStatus,
            EnvironmentType,
            TestEnvironment,
        )

        client, service = client_with_service

        # Directly create environment for different user by manipulating service state
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        env_id = "env-other-user-extend"
        env = TestEnvironment(
            environment_id=env_id,
            user_id="other-user",
            organization_id="org-456",
            environment_type=EnvironmentType.STANDARD,
            template_id="python-fastapi",
            display_name="Other User Env",
            status=EnvironmentStatus.ACTIVE,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=24)).isoformat(),
            dns_name=f"{env_id}.test.aura.local",
            cost_estimate_daily=0.50,
            last_activity_at=now.isoformat(),
        )
        # CRITICAL: Store as dictionary, not TestEnvironment object
        service.mock_store[env_id] = env.to_dict()

        response = client.post(
            f"/api/v1/environments/{env_id}/extend",
            json={"additional_hours": 4},
        )

        assert response.status_code == 403

    def test_extend_environment_invalid_status(self, client):
        """Test extending environment in invalid status."""
        # Create environment
        create_response = client.post(
            "/api/v1/environments",
            json={
                "template_id": "python-fastapi",
                "display_name": "Terminated Env",
            },
        )
        assert create_response.status_code == 201
        env_id = create_response.json()["environment_id"]

        # Terminate it
        term_response = client.delete(f"/api/v1/environments/{env_id}")
        assert term_response.status_code == 204

        response = client.post(
            f"/api/v1/environments/{env_id}/extend",
            json={"additional_hours": 4},
        )

        assert response.status_code == 400
        assert "cannot extend" in response.json()["detail"].lower()

    def test_extend_environment_invalid_hours(self, client):
        """Test extending with invalid hours."""
        response = client.post(
            "/api/v1/environments/env-test/extend",
            json={"additional_hours": 500},  # Over max (168)
        )

        assert response.status_code == 422  # Validation error
