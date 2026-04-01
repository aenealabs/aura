"""
Tests for Generic Export API Endpoints.

ADR-048 Phase 5: Fivetran Connector + Generic Export API
"""

import platform
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Run tests in isolated subprocesses to prevent state pollution
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

app = FastAPI()


@pytest.fixture
def client():
    """Create test client with export router."""
    # Clear any cached module state
    import sys

    for mod in list(sys.modules.keys()):
        if mod.startswith("src.api.export"):
            del sys.modules[mod]

    from src.api.export_endpoints import router

    test_app = FastAPI()
    test_app.include_router(router)
    return TestClient(test_app)


@pytest.fixture
def auth_headers():
    """Standard authentication headers."""
    return {
        "X-User-Id": "user-123",
        "X-User-Role": "admin",
        "X-Organization-Id": "org-456",
    }


@pytest.fixture
def fivetran_headers():
    """Fivetran API headers."""
    return {
        "X-Api-Key": "test-api-key",
        "X-Organization-Id": "org-456",
    }


class TestEntitySchemas:
    """Tests for schema discovery endpoints."""

    def test_get_findings_schema(self, client, auth_headers):
        """Test getting findings entity schema."""
        response = client.get("/api/v1/export/schema/findings", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["entity"] == "findings"
        assert data["version"] == "1.0"
        assert "finding_id" in data["primary_key"]
        assert len(data["fields"]) > 0

    def test_get_code_patterns_schema(self, client, auth_headers):
        """Test getting code patterns entity schema."""
        response = client.get(
            "/api/v1/export/schema/code_patterns", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["entity"] == "code_patterns"
        assert "pattern_id" in data["primary_key"]

    def test_get_repositories_schema(self, client, auth_headers):
        """Test getting repositories entity schema."""
        response = client.get(
            "/api/v1/export/schema/repositories", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["entity"] == "repositories"
        assert "repository_id" in data["primary_key"]

    def test_list_all_schemas(self, client, auth_headers):
        """Test listing all available schemas."""
        response = client.get("/api/v1/export/schemas", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "findings" in data
        assert "code_patterns" in data
        assert "repositories" in data
        assert "scan_history" in data
        assert "metrics" in data

    def test_schema_field_definitions(self, client, auth_headers):
        """Test that schema fields have proper definitions."""
        response = client.get("/api/v1/export/schema/findings", headers=auth_headers)

        assert response.status_code == 200
        fields = response.json()["fields"]

        # Check field has required attributes
        field_names = [f["name"] for f in fields]
        assert "finding_id" in field_names
        assert "severity" in field_names
        assert "file_path" in field_names

        # Check field structure
        finding_id_field = next(f for f in fields if f["name"] == "finding_id")
        assert finding_id_field["type"] == "string"
        assert finding_id_field["nullable"] is False


class TestExportData:
    """Tests for data export endpoint."""

    def test_export_findings_success(self, client, auth_headers):
        """Test successful findings export."""
        response = client.post(
            "/api/v1/export/data",
            headers=auth_headers,
            json={
                "entity": "findings",
                "format": "json",
                "page_size": 100,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "has_more" in data
        assert "export_timestamp" in data

    def test_export_unauthorized(self, client):
        """Test export denied when unauthorized (viewer role can't export findings)."""
        response = client.post(
            "/api/v1/export/data",
            headers={
                "X-User-Id": "user-1",
                "X-User-Role": "viewer",  # Viewers can only export metrics
                "X-Organization-Id": "org-1",
            },
            json={
                "entity": "findings",
                "format": "json",
            },
        )

        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()

    def test_export_with_pagination(self, client, auth_headers):
        """Test export pagination."""
        response = client.post(
            "/api/v1/export/data",
            headers=auth_headers,
            json={
                "entity": "findings",
                "page_size": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Should have data and pagination info
        assert isinstance(data["data"], list)
        assert "next_cursor" in data
        assert isinstance(data["has_more"], bool)

    def test_export_repositories(self, client, auth_headers):
        """Test exporting repositories."""
        response = client.post(
            "/api/v1/export/data",
            headers=auth_headers,
            json={
                "entity": "repositories",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["data"], list)

    @patch("src.api.export_endpoints._secrets_filter")
    def test_export_redacts_secrets(self, mock_secrets, client, auth_headers):
        """Test that secrets are redacted in export."""
        # Return a non-empty list to indicate secrets were detected
        mock_secrets.scan_only.return_value = [MagicMock()]

        response = client.post(
            "/api/v1/export/data",
            headers=auth_headers,
            json={
                "entity": "findings",
            },
        )

        assert response.status_code == 200
        # Secrets filter should have been called
        assert mock_secrets.scan_only.called


class TestExportFormats:
    """Tests for different export formats."""

    def test_export_json_format(self, client, auth_headers):
        """Test JSON export format."""
        response = client.post(
            "/api/v1/export/data",
            headers=auth_headers,
            json={
                "entity": "findings",
                "format": "json",
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


class TestFivetranEndpoints:
    """Tests for Fivetran-specific endpoints."""

    def test_fivetran_test_connection(self, client, fivetran_headers):
        """Test Fivetran test connection endpoint."""
        response = client.post(
            "/api/v1/export/fivetran/test",
            headers=fivetran_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_fivetran_test_missing_api_key(self, client):
        """Test Fivetran test without API key."""
        response = client.post(
            "/api/v1/export/fivetran/test",
            headers={"X-Organization-Id": "org-123"},
        )

        # Should fail due to missing header
        assert response.status_code == 422

    def test_fivetran_schema_discovery(self, client, fivetran_headers):
        """Test Fivetran schema discovery endpoint."""
        response = client.post(
            "/api/v1/export/fivetran/schema",
            headers=fivetran_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "tables" in data
        assert "findings" in data["tables"]
        assert "code_patterns" in data["tables"]

    def test_fivetran_schema_structure(self, client, fivetran_headers):
        """Test Fivetran schema has correct structure."""
        response = client.post(
            "/api/v1/export/fivetran/schema",
            headers=fivetran_headers,
        )

        assert response.status_code == 200
        tables = response.json()["tables"]

        # Check findings table structure
        findings = tables["findings"]
        assert "columns" in findings
        assert "primary_key" in findings
        assert findings["columns"]["finding_id"]["type"] == "STRING"

    @patch("src.api.export_endpoints._secrets_filter")
    def test_fivetran_sync(self, mock_secrets, client, fivetran_headers):
        """Test Fivetran sync endpoint."""
        mock_secrets.scan_only.return_value = []  # No secrets detected

        response = client.post(
            "/api/v1/export/fivetran/sync",
            headers=fivetran_headers,
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert "state" in data
        assert "insert" in data
        assert "hasMore" in data

    @patch("src.api.export_endpoints._secrets_filter")
    def test_fivetran_sync_incremental(self, mock_secrets, client, fivetran_headers):
        """Test Fivetran incremental sync with state."""
        mock_secrets.scan_only.return_value = []  # No secrets detected

        initial_state = {
            "last_sync": "2025-01-01T00:00:00Z",
            "findings_cursor": "100",
        }

        response = client.post(
            "/api/v1/export/fivetran/sync",
            headers=fivetran_headers,
            json=initial_state,
        )

        assert response.status_code == 200
        data = response.json()
        assert "state" in data
        # State should be updated
        assert "last_sync" in data["state"]

    @patch("src.api.export_endpoints._secrets_filter")
    def test_fivetran_sync_redacts_secrets(
        self, mock_secrets, client, fivetran_headers
    ):
        """Test that sync redacts detected secrets."""
        mock_secrets.scan_only.return_value = [MagicMock()]  # Secrets detected

        response = client.post(
            "/api/v1/export/fivetran/sync",
            headers=fivetran_headers,
            json={},
        )

        assert response.status_code == 200
        # Secrets filter should be invoked
        assert mock_secrets.scan_only.called


class TestExportHealth:
    """Tests for export health endpoint."""

    def test_health_check(self, client):
        """Test export API health check."""
        response = client.get("/api/v1/export/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestAuthorizationContext:
    """Tests for authorization context extraction."""

    def test_role_parsing_admin(self, client):
        """Test admin role parsing."""
        response = client.post(
            "/api/v1/export/data",
            headers={
                "X-User-Id": "user-1",
                "X-User-Role": "admin",
                "X-Organization-Id": "org-1",
            },
            json={"entity": "findings"},
        )

        assert response.status_code == 200

    def test_role_parsing_viewer(self, client):
        """Test viewer role parsing - viewer can only export metrics."""
        response = client.post(
            "/api/v1/export/data",
            headers={
                "X-User-Id": "user-1",
                "X-User-Role": "viewer",
                "X-Organization-Id": "org-1",
            },
            json={"entity": "metrics"},  # Viewer can export metrics
        )

        assert response.status_code == 200

    def test_invalid_role_defaults_to_viewer(self, client):
        """Test that invalid role defaults to viewer (can export metrics)."""
        response = client.post(
            "/api/v1/export/data",
            headers={
                "X-User-Id": "user-1",
                "X-User-Role": "invalid_role",
                "X-Organization-Id": "org-1",
            },
            json={"entity": "metrics"},  # Viewer can export metrics
        )

        assert response.status_code == 200

    def test_missing_user_id_fails(self, client):
        """Test that missing user ID fails."""
        response = client.post(
            "/api/v1/export/data",
            headers={
                "X-User-Role": "admin",
                "X-Organization-Id": "org-1",
            },
            json={"entity": "findings"},
        )

        assert response.status_code == 422

    def test_missing_organization_id_fails(self, client):
        """Test that missing organization ID fails."""
        response = client.post(
            "/api/v1/export/data",
            headers={
                "X-User-Id": "user-1",
                "X-User-Role": "admin",
            },
            json={"entity": "findings"},
        )

        assert response.status_code == 422


class TestExportEntityTypes:
    """Tests for different entity type exports."""

    def test_export_scan_history(self, client, auth_headers):
        """Test exporting scan history."""
        response = client.post(
            "/api/v1/export/data",
            headers=auth_headers,
            json={
                "entity": "scan_history",
            },
        )

        assert response.status_code == 200

    def test_export_metrics(self, client, auth_headers):
        """Test exporting metrics."""
        response = client.post(
            "/api/v1/export/data",
            headers=auth_headers,
            json={
                "entity": "metrics",
            },
        )

        assert response.status_code == 200
