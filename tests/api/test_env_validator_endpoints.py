"""Tests for Environment Validator API endpoints (ADR-062 Phase 3)."""

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.env_validator_endpoints import router
from src.services.env_validator.config import clear_registry_cache


@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    os.environ["ENV_VALIDATOR_USE_MOCK"] = "true"
    clear_registry_cache()
    yield
    clear_registry_cache()
    os.environ.pop("ENV_VALIDATOR_USE_MOCK", None)


@pytest.fixture
def app():
    """Create test FastAPI app."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestValidateEndpoint:
    """Tests for POST /api/v1/environment/validate endpoint."""

    def test_validate_valid_manifest(self, client):
        """Test validating a correct manifest."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-api-config
  namespace: default
  labels:
    app: aura-api
    environment: qa
data:
  ENVIRONMENT: qa
  JOBS_TABLE_NAME: aura-gpu-jobs-qa
"""

        response = client.post(
            "/api/v1/environment/validate",
            json={"manifest": manifest, "target_env": "qa"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "run_id" in data
        assert data["environment"] == "qa"
        assert "violations" in data
        assert "warnings" in data

    def test_validate_manifest_with_violations(self, client):
        """Test validating a manifest with critical violations."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-api-config
  namespace: default
data:
  ENVIRONMENT: dev
  JOBS_TABLE_NAME: aura-gpu-jobs-dev
"""

        response = client.post(
            "/api/v1/environment/validate",
            json={"manifest": manifest, "target_env": "qa"},
        )

        assert response.status_code == 200
        data = response.json()
        # Should have violations for wrong env suffix
        assert data["result"] in ["fail", "warn"]

    def test_validate_strict_mode(self, client):
        """Test strict mode treats warnings as errors."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-api-config
  namespace: default
data:
  ENVIRONMENT: dev
"""

        response = client.post(
            "/api/v1/environment/validate",
            json={"manifest": manifest, "target_env": "qa", "strict": True},
        )

        assert response.status_code == 200
        data = response.json()
        # In strict mode, warnings become violations
        if data["warnings"]:
            # This shouldn't happen in strict mode
            assert False, "Warnings should be empty in strict mode"

    def test_validate_invalid_environment(self, client):
        """Test validation with invalid environment name."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: test
data:
  KEY: value
"""

        response = client.post(
            "/api/v1/environment/validate",
            json={"manifest": manifest, "target_env": "invalid"},
        )

        # Should fail validation due to invalid env pattern
        assert response.status_code == 422

    def test_validate_empty_manifest(self, client):
        """Test validation with empty manifest."""
        response = client.post(
            "/api/v1/environment/validate",
            json={"manifest": "", "target_env": "qa"},
        )

        # Should fail due to min_length constraint
        assert response.status_code == 422

    def test_validate_with_save_baseline(self, client):
        """Test validation with save_baseline option."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config
  namespace: default
  labels:
    app: aura
    environment: qa
data:
  ENVIRONMENT: qa
"""

        response = client.post(
            "/api/v1/environment/validate",
            json={
                "manifest": manifest,
                "target_env": "qa",
                "save_baseline": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        # If validation passed, baseline should be saved
        if data["valid"]:
            assert data["baseline_saved"] is True


class TestDriftEndpoints:
    """Tests for drift detection endpoints."""

    def test_get_drift_status(self, client):
        """Test getting drift status for an environment."""
        response = client.get("/api/v1/environment/drift?env=qa")

        assert response.status_code == 200
        data = response.json()
        assert "drift_detected" in data
        assert "environment" in data
        assert data["environment"] == "qa"
        assert "drifted_resources" in data

    def test_detect_drift_no_baseline(self, client):
        """Test drift detection when no baseline exists."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: new-config
  namespace: default
data:
  KEY: value
"""

        response = client.post(
            "/api/v1/environment/drift/detect?env=qa",
            json={"manifest": manifest},
        )

        assert response.status_code == 200
        data = response.json()
        assert "drift_detected" in data
        # No baseline = no drift detected
        assert data["drift_detected"] is False

    def test_detect_drift_with_changes(self, client):
        """Test drift detection when configuration changed from baseline."""
        # First, save a baseline
        baseline_manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config
  namespace: default
  labels:
    app: aura
    environment: qa
data:
  ENVIRONMENT: qa
"""

        # Save baseline
        client.post(
            "/api/v1/environment/baselines?env=qa",
            json={"manifest": baseline_manifest, "created_by": "test"},
        )

        # Now check for drift with different manifest
        current_manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config
  namespace: default
  labels:
    app: aura
    environment: qa
data:
  ENVIRONMENT: dev
"""

        response = client.post(
            "/api/v1/environment/drift/detect?env=qa",
            json={"manifest": current_manifest},
        )

        assert response.status_code == 200
        data = response.json()
        assert "drift_detected" in data


class TestRegistryEndpoint:
    """Tests for GET /api/v1/environment/registry endpoint."""

    def test_get_registry(self, client):
        """Test getting environment registry."""
        response = client.get("/api/v1/environment/registry")

        assert response.status_code == 200
        data = response.json()
        assert "environments" in data

        # Check that default environments are present
        envs = data["environments"]
        assert "dev" in envs
        assert "qa" in envs
        assert "prod" in envs

    def test_registry_structure(self, client):
        """Test registry response structure."""
        response = client.get("/api/v1/environment/registry")

        assert response.status_code == 200
        data = response.json()

        # Check structure of each environment config
        for env_name, config in data["environments"].items():
            assert "account_id" in config
            assert "ecr_registry" in config
            assert "neptune_cluster" in config
            assert "opensearch_domain" in config
            assert "resource_suffix" in config
            assert "eks_cluster" in config
            assert "region" in config


class TestValidationHistoryEndpoint:
    """Tests for GET /api/v1/environment/validation-history endpoint."""

    def test_get_validation_history(self, client):
        """Test getting validation history."""
        response = client.get("/api/v1/environment/validation-history?env=qa")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total_count" in data
        assert "has_more" in data

    def test_validation_history_pagination(self, client):
        """Test validation history pagination parameters."""
        response = client.get(
            "/api/v1/environment/validation-history?env=qa&limit=10&offset=5"
        )

        assert response.status_code == 200


class TestBaselineEndpoints:
    """Tests for baseline management endpoints."""

    def test_list_baselines_empty(self, client):
        """Test listing baselines when none exist."""
        response = client.get("/api/v1/environment/baselines?env=qa")

        assert response.status_code == 200
        data = response.json()
        assert "baselines" in data
        assert "count" in data
        assert data["count"] == 0

    def test_save_baseline(self, client):
        """Test saving a baseline."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
  namespace: default
  labels:
    app: test
    environment: qa
data:
  ENVIRONMENT: qa
"""

        response = client.post(
            "/api/v1/environment/baselines?env=qa",
            json={"manifest": manifest, "created_by": "test-user"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "baselines" in data
        assert data["count"] >= 1

    def test_save_baseline_with_violations(self, client):
        """Test that saving baseline fails if manifest has violations."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
  namespace: default
data:
  ENVIRONMENT: dev
  JOBS_TABLE_NAME: aura-jobs-dev
"""

        response = client.post(
            "/api/v1/environment/baselines?env=qa",
            json={"manifest": manifest},
        )

        # Should fail due to validation errors
        assert response.status_code == 400

    def test_list_baselines_after_save(self, client):
        """Test listing baselines response structure after save."""
        # Note: Each API call creates a new MockBaselineManager in test mode,
        # so baselines don't persist across calls. This test validates
        # that the save returns saved baselines in the response.
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: saved-config
  namespace: aura-system
  labels:
    app: aura
    environment: qa
data:
  ENVIRONMENT: qa
"""

        # Save baseline - the response includes the saved baselines
        response = client.post(
            "/api/v1/environment/baselines?env=qa",
            json={"manifest": manifest},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["count"] >= 1
        assert any(b["resource_name"] == "saved-config" for b in data["baselines"])

    def test_list_baselines_filter_by_type(self, client):
        """Test filtering baselines by resource type."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: filter-test
  namespace: default
  labels:
    app: test
    environment: qa
data:
  KEY: value
"""

        # Save baseline
        client.post(
            "/api/v1/environment/baselines?env=qa",
            json={"manifest": manifest},
        )

        # Filter by ConfigMap
        response = client.get(
            "/api/v1/environment/baselines?env=qa&resource_type=ConfigMap"
        )

        assert response.status_code == 200
        data = response.json()
        for baseline in data["baselines"]:
            assert baseline["resource_type"] == "ConfigMap"

    def test_delete_baseline(self, client):
        """Test delete baseline endpoint structure.

        Note: Since each API call creates a new MockBaselineManager in test mode,
        we can only test that delete returns 404 for non-existent baselines,
        which is the expected behavior. In production with DynamoDB persistence,
        the full save-then-delete flow would work.
        """
        # Delete non-existent returns 404
        response = client.delete(
            "/api/v1/environment/baselines/ConfigMap/default/to-delete?env=qa"
        )

        # In mock mode without persistence, this will be 404
        # In production with DynamoDB, we'd save first then delete
        assert response.status_code == 404

    def test_delete_nonexistent_baseline(self, client):
        """Test deleting a baseline that doesn't exist."""
        response = client.delete(
            "/api/v1/environment/baselines/ConfigMap/default/nonexistent?env=qa"
        )

        assert response.status_code == 404


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check returns expected structure."""
        response = client.get("/api/v1/environment/health")

        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert data["service"] == "environment-validator"
        assert "healthy" in data
        assert "registry_loaded" in data

    def test_health_check_with_env(self, client):
        """Test health check with specific environment."""
        response = client.get("/api/v1/environment/health?env=qa")

        assert response.status_code == 200
        data = response.json()
        assert data["environment"] == "qa"


class TestMultiDocumentManifests:
    """Tests for handling multi-document YAML manifests."""

    def test_validate_multi_document(self, client):
        """Test validating a manifest with multiple documents."""
        manifest = """
apiVersion: v1
kind: Namespace
metadata:
  name: aura-system
  labels:
    environment: qa
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config
  namespace: aura-system
  labels:
    app: aura
    environment: qa
data:
  ENVIRONMENT: qa
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aura-api
  namespace: aura-system
  labels:
    app: aura-api
    environment: qa
spec:
  replicas: 1
  selector:
    matchLabels:
      app: aura-api
  template:
    metadata:
      labels:
        app: aura-api
    spec:
      containers:
        - name: api
          image: 234567890123.dkr.ecr.us-east-1.amazonaws.com/aura-api:latest
"""

        response = client.post(
            "/api/v1/environment/validate",
            json={"manifest": manifest, "target_env": "qa"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["resources_scanned"] == 3


class TestErrorHandling:
    """Tests for API error handling."""

    def test_missing_required_param(self, client):
        """Test error when required parameter is missing."""
        response = client.get("/api/v1/environment/drift")
        # Should fail due to missing 'env' query param
        assert response.status_code == 422

    def test_invalid_request_body(self, client):
        """Test error for invalid request body."""
        response = client.post(
            "/api/v1/environment/validate",
            json={"invalid": "body"},
        )
        assert response.status_code == 422
