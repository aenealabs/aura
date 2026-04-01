"""
Project Aura - Autonomy Endpoints Tests

Tests for the autonomy configuration API endpoints including:
- Authentication requirements
- Role-based access control (admin vs user)
- CRUD operations for policies
- HITL toggle functionality

Author: Project Aura Team
Created: 2025-12-12

Note: Uses lazy imports inside fixtures to ensure fresh module state
in forked test processes. Module-level imports of src.* modules would
create stale references after process fork.
"""

import platform

import pytest

# These tests require pytest-forked for proper isolation due to complex FastAPI
# router state. On Linux, pytest-forked causes FastAPIError due to
# starlette.requests.Request class identity issues when modules are reimported.
#
# On macOS/Windows, forked mode works correctly and provides test isolation.
# On Linux (CI), skip these tests - they are validated locally before merge.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from unittest.mock import patch

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_auth_state():
    """Reset auth caches before each test to ensure clean state."""
    from src.api.auth import clear_auth_caches

    clear_auth_caches()
    yield
    clear_auth_caches()


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    from src.api.auth import User

    return User(
        sub="admin-user-123",
        email="admin@aenealabs.com",
        name="Admin User",
        groups=["admin"],
    )


@pytest.fixture
def mock_engineer_user():
    """Create a mock security engineer user."""
    from src.api.auth import User

    return User(
        sub="engineer-user-456",
        email="engineer@aenealabs.com",
        name="Engineer User",
        groups=["security-engineer"],
    )


@pytest.fixture
def mock_developer_user():
    """Create a mock developer user."""
    from src.api.auth import User

    return User(
        sub="developer-user-789",
        email="developer@aenealabs.com",
        name="Developer User",
        groups=["developer"],
    )


@pytest.fixture
def mock_viewer_user():
    """Create a mock viewer user."""
    from src.api.auth import User

    return User(
        sub="viewer-user-000",
        email="viewer@aenealabs.com",
        name="Viewer User",
        groups=["viewer"],
    )


@pytest.fixture
def mock_autonomy_service():
    """Create a mock autonomy policy service."""
    from src.services.autonomy_policy_service import (
        AutonomyServiceMode,
        create_autonomy_policy_service,
    )

    service = create_autonomy_policy_service(mode=AutonomyServiceMode.MOCK)
    return service


@pytest.fixture
def sample_policy(mock_autonomy_service):
    """Create a sample policy for testing."""
    from src.services.autonomy_policy_service import AutonomyLevel

    policy = mock_autonomy_service.create_policy(
        organization_id="test-org-123",
        name="Test Policy",
        description="Test description",
        hitl_enabled=True,
        default_level=AutonomyLevel.CRITICAL_HITL,
        created_by="test@example.com",
    )
    return policy


def create_test_app(user_override=None, deny_admin=False):
    """Create a test FastAPI app with optional auth override."""
    import time

    from fastapi import FastAPI, HTTPException

    from src.api.auth import get_current_user, require_admin
    from src.api.autonomy_endpoints import router
    from src.services.api_rate_limiter import (
        RateLimitResult,
        RateLimitTier,
        admin_rate_limit,
        critical_rate_limit,
        public_rate_limit,
        standard_rate_limit,
    )

    app = FastAPI()
    app.include_router(router)

    # Always disable rate limiting in tests
    mock_rate_result = RateLimitResult(
        allowed=True,
        remaining=999,
        reset_at=time.time() + 60,
        limit=1000,
        tier=RateLimitTier.STANDARD,
        client_id="test",
    )
    app.dependency_overrides[standard_rate_limit] = lambda: mock_rate_result
    app.dependency_overrides[admin_rate_limit] = lambda: mock_rate_result
    app.dependency_overrides[critical_rate_limit] = lambda: mock_rate_result
    app.dependency_overrides[public_rate_limit] = lambda: mock_rate_result

    if user_override:
        # Override all auth dependencies
        async def get_user_override():
            return user_override

        async def admin_override():
            if deny_admin:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. Required role: admin",
                )
            return user_override

        app.dependency_overrides[get_current_user] = get_user_override
        app.dependency_overrides[require_admin] = admin_override

    return app


@pytest.fixture
def admin_client(mock_admin_user, mock_autonomy_service):
    """Create a test client with admin user."""
    from fastapi.testclient import TestClient

    app = create_test_app(mock_admin_user, deny_admin=False)

    with patch(
        "src.api.autonomy_endpoints.get_autonomy_service",
        return_value=mock_autonomy_service,
    ):
        client = TestClient(app, raise_server_exceptions=False)
        yield client


@pytest.fixture
def engineer_client(mock_engineer_user, mock_autonomy_service):
    """Create a test client with security engineer user."""
    from fastapi.testclient import TestClient

    app = create_test_app(mock_engineer_user, deny_admin=True)

    with patch(
        "src.api.autonomy_endpoints.get_autonomy_service",
        return_value=mock_autonomy_service,
    ):
        client = TestClient(app, raise_server_exceptions=False)
        yield client


@pytest.fixture
def unauthenticated_client(mock_autonomy_service):
    """Create a test client without authentication."""
    from fastapi import HTTPException
    from fastapi.testclient import TestClient

    from src.api.auth import get_current_user, require_admin

    async def deny_auth():
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    app = create_test_app()
    app.dependency_overrides[get_current_user] = deny_auth
    app.dependency_overrides[require_admin] = deny_auth

    with patch(
        "src.api.autonomy_endpoints.get_autonomy_service",
        return_value=mock_autonomy_service,
    ):
        client = TestClient(app, raise_server_exceptions=False)
        yield client


# ============================================================================
# Authentication Tests
# ============================================================================


class TestAuthentication:
    """Tests for endpoint authentication requirements."""

    def test_list_policies_requires_auth(self, unauthenticated_client):
        """Test that listing policies requires authentication."""
        response = unauthenticated_client.get(
            "/api/v1/autonomy/policies",
            params={"organization_id": "test-org"},
        )
        assert response.status_code == 401

    def test_create_policy_requires_auth(self, unauthenticated_client):
        """Test that creating a policy requires authentication."""
        response = unauthenticated_client.post(
            "/api/v1/autonomy/policies",
            json={"organization_id": "test-org", "name": "Test"},
        )
        assert response.status_code == 401

    def test_get_policy_requires_auth(self, unauthenticated_client):
        """Test that getting a policy requires authentication."""
        response = unauthenticated_client.get(
            "/api/v1/autonomy/policies/some-id",
        )
        assert response.status_code == 401

    def test_check_hitl_requires_auth(self, unauthenticated_client):
        """Test that checking HITL requires authentication."""
        response = unauthenticated_client.post(
            "/api/v1/autonomy/check",
            json={
                "policy_id": "test",
                "severity": "HIGH",
                "operation": "test",
            },
        )
        assert response.status_code == 401

    def test_presets_is_public(self, unauthenticated_client):
        """Test that presets endpoint is public."""
        response = unauthenticated_client.get("/api/v1/autonomy/presets")
        assert response.status_code == 200

    def test_health_is_public(self, unauthenticated_client):
        """Test that health endpoint is public."""
        response = unauthenticated_client.get("/api/v1/autonomy/health")
        assert response.status_code == 200


# ============================================================================
# Role-Based Access Control Tests
# ============================================================================


class TestRBAC:
    """Tests for role-based access control."""

    def test_engineer_cannot_create_policy(self, engineer_client):
        """Test that security engineer cannot create a policy."""
        response = engineer_client.post(
            "/api/v1/autonomy/policies",
            json={"organization_id": "test-org", "name": "Test"},
        )
        assert response.status_code == 403

    def test_engineer_can_list_policies(self, engineer_client):
        """Test that security engineer can list policies."""
        response = engineer_client.get(
            "/api/v1/autonomy/policies",
            params={"organization_id": "test-org"},
        )
        assert response.status_code == 200

    def test_admin_can_create_policy(self, admin_client):
        """Test that admin can create a policy."""
        response = admin_client.post(
            "/api/v1/autonomy/policies",
            json={"organization_id": "test-org", "name": "Admin Policy"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Admin Policy"
        assert data["created_by"] == "admin@aenealabs.com"

    def test_admin_can_toggle_hitl(self, admin_client, sample_policy):
        """Test that admin can toggle HITL."""
        response = admin_client.put(
            f"/api/v1/autonomy/policies/{sample_policy.policy_id}/toggle",
            json={"hitl_enabled": False, "reason": "Testing"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hitl_enabled"] is False

    def test_engineer_cannot_toggle_hitl(self, engineer_client, sample_policy):
        """Test that security engineer cannot toggle HITL."""
        response = engineer_client.put(
            f"/api/v1/autonomy/policies/{sample_policy.policy_id}/toggle",
            json={"hitl_enabled": False},
        )
        assert response.status_code == 403

    def test_engineer_cannot_delete_policy(self, engineer_client, sample_policy):
        """Test that security engineer cannot delete a policy."""
        response = engineer_client.delete(
            f"/api/v1/autonomy/policies/{sample_policy.policy_id}",
        )
        assert response.status_code == 403


# ============================================================================
# Policy CRUD Tests
# ============================================================================


class TestPolicyCRUD:
    """Tests for policy CRUD operations."""

    def test_create_policy_from_preset(self, admin_client):
        """Test creating a policy from a preset."""
        response = admin_client.post(
            "/api/v1/autonomy/policies",
            json={
                "organization_id": "test-org",
                "preset_name": "enterprise_standard",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["preset_name"] == "enterprise_standard"

    def test_create_policy_invalid_preset(self, admin_client):
        """Test creating a policy with invalid preset fails."""
        response = admin_client.post(
            "/api/v1/autonomy/policies",
            json={
                "organization_id": "test-org",
                "preset_name": "nonexistent_preset",
            },
        )
        assert response.status_code == 400

    def test_get_policy(self, admin_client, sample_policy):
        """Test getting a specific policy."""
        response = admin_client.get(
            f"/api/v1/autonomy/policies/{sample_policy.policy_id}",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["policy_id"] == sample_policy.policy_id
        assert data["name"] == "Test Policy"

    def test_get_policy_not_found(self, admin_client):
        """Test getting a nonexistent policy returns 404."""
        response = admin_client.get(
            "/api/v1/autonomy/policies/nonexistent-policy-id",
        )
        assert response.status_code == 404

    def test_update_policy(self, admin_client, sample_policy):
        """Test updating a policy."""
        response = admin_client.put(
            f"/api/v1/autonomy/policies/{sample_policy.policy_id}",
            json={"name": "Updated Policy Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Policy Name"
        assert data["updated_by"] == "admin@aenealabs.com"

    def test_update_policy_no_changes(self, admin_client, sample_policy):
        """Test updating a policy with no changes fails."""
        response = admin_client.put(
            f"/api/v1/autonomy/policies/{sample_policy.policy_id}",
            json={},
        )
        assert response.status_code == 400

    def test_delete_policy(self, admin_client, sample_policy):
        """Test deleting a policy."""
        response = admin_client.delete(
            f"/api/v1/autonomy/policies/{sample_policy.policy_id}",
            params={"reason": "No longer needed"},
        )
        assert response.status_code == 204

    def test_list_policies(self, admin_client, sample_policy):
        """Test listing policies for an organization."""
        response = admin_client.get(
            "/api/v1/autonomy/policies",
            params={"organization_id": sample_policy.organization_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(p["policy_id"] == sample_policy.policy_id for p in data)


# ============================================================================
# Override Tests
# ============================================================================


class TestOverrides:
    """Tests for policy override operations."""

    def test_add_severity_override(self, admin_client, sample_policy):
        """Test adding a severity override."""
        response = admin_client.post(
            f"/api/v1/autonomy/policies/{sample_policy.policy_id}/override",
            json={
                "override_type": "severity",
                "context_value": "CRITICAL",
                "autonomy_level": "full_hitl",
                "reason": "Critical actions need approval",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "CRITICAL" in data["severity_overrides"]

    def test_add_operation_override(self, admin_client, sample_policy):
        """Test adding an operation override."""
        response = admin_client.post(
            f"/api/v1/autonomy/policies/{sample_policy.policy_id}/override",
            json={
                "override_type": "operation",
                "context_value": "production_deployment",
                "autonomy_level": "full_hitl",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "production_deployment" in data["operation_overrides"]

    def test_add_invalid_override_type(self, admin_client, sample_policy):
        """Test adding an invalid override type fails."""
        response = admin_client.post(
            f"/api/v1/autonomy/policies/{sample_policy.policy_id}/override",
            json={
                "override_type": "invalid",
                "context_value": "test",
                "autonomy_level": "full_hitl",
            },
        )
        assert response.status_code == 400

    def test_remove_override(self, admin_client, sample_policy):
        """Test removing an override."""
        # First add an override
        admin_client.post(
            f"/api/v1/autonomy/policies/{sample_policy.policy_id}/override",
            json={
                "override_type": "severity",
                "context_value": "HIGH",
                "autonomy_level": "full_hitl",
            },
        )

        # Then remove it
        response = admin_client.request(
            "DELETE",
            f"/api/v1/autonomy/policies/{sample_policy.policy_id}/override",
            json={
                "override_type": "severity",
                "context_value": "HIGH",
            },
        )
        assert response.status_code == 200


# ============================================================================
# HITL Check Tests
# ============================================================================


class TestHITLCheck:
    """Tests for HITL requirement checking."""

    def test_check_hitl_required(self, admin_client, sample_policy):
        """Test checking if HITL is required for an action."""
        response = admin_client.post(
            "/api/v1/autonomy/check",
            json={
                "policy_id": sample_policy.policy_id,
                "severity": "CRITICAL",
                "operation": "security_patch",
                "repository": "test-repo",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "requires_hitl" in data
        assert "autonomy_level" in data
        assert "reason" in data

    def test_check_hitl_policy_not_found(self, admin_client):
        """Test checking HITL for nonexistent policy returns 404."""
        response = admin_client.post(
            "/api/v1/autonomy/check",
            json={
                "policy_id": "nonexistent-policy",
                "severity": "HIGH",
                "operation": "test",
            },
        )
        assert response.status_code == 404

    def test_check_hitl_guardrail_triggered(self, admin_client, sample_policy):
        """Test checking HITL when guardrail is triggered."""
        response = admin_client.post(
            "/api/v1/autonomy/check",
            json={
                "policy_id": sample_policy.policy_id,
                "severity": "HIGH",
                "operation": "production_deployment",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["requires_hitl"] is True
        assert data["guardrail_triggered"] is True


# ============================================================================
# Preset Tests
# ============================================================================


class TestPresets:
    """Tests for preset operations."""

    def test_get_presets(self, admin_client):
        """Test getting available presets."""
        response = admin_client.get("/api/v1/autonomy/presets")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 7  # At least 7 presets

        # Check expected presets exist
        preset_names = [p["name"] for p in data]
        assert "defense_contractor" in preset_names
        assert "enterprise_standard" in preset_names
        assert "fully_autonomous" in preset_names

    def test_preset_has_required_fields(self, admin_client):
        """Test that presets have all required fields."""
        response = admin_client.get("/api/v1/autonomy/presets")
        data = response.json()

        for preset in data:
            assert "name" in preset
            assert "display_name" in preset
            assert "description" in preset
            assert "default_level" in preset
            assert "hitl_enabled" in preset


# ============================================================================
# Health Check Tests
# ============================================================================


class TestHealthCheck:
    """Tests for autonomy service health check."""

    def test_health_check(self, admin_client):
        """Test autonomy service health check."""
        response = admin_client.get("/api/v1/autonomy/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "autonomy_policy_service"
        assert "mode" in data
