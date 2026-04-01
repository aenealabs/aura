"""
Project Aura - API Endpoint Tests

Tests for the FastAPI application including:
- Health check endpoints
- Git ingestion endpoints
- GitHub webhook endpoints

Author: Project Aura Team
Created: 2025-11-28
"""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_git_ingestion_service():
    """Create a mock GitIngestionService."""
    mock = MagicMock()
    mock._generate_job_id.return_value = "test-job-123"
    mock.get_job_status.return_value = MagicMock(
        job_id="test-job-123",
        status=MagicMock(value="completed"),
        files_processed=10,
        entities_indexed=50,
        embeddings_generated=10,
        errors=[],
        metadata={"repository": "test/repo"},
    )
    mock.list_active_jobs.return_value = []
    mock.completed_jobs = []
    mock.ingest_repository = AsyncMock()
    return mock


@pytest.fixture
def mock_webhook_handler():
    """Create a mock GitHubWebhookHandler."""
    mock = MagicMock()
    mock.parse_event.return_value = MagicMock(
        event_type=MagicMock(value="push"),
        repository_url="https://github.com/test/repo",
        repository_name="test/repo",
        branch="main",
        commit_hash="abc123",
        changed_files=["src/main.py"],
    )
    mock.process_event = AsyncMock(return_value={"status": "success"})
    mock.get_queue_status.return_value = {"queue_length": 0, "events": []}
    mock.clear_queue.return_value = 0
    return mock


@pytest.fixture
def mock_health_endpoints():
    """Create a mock HealthCheckEndpoints."""
    mock = MagicMock()
    mock.aws_health_check = AsyncMock(
        return_value={"status": "healthy", "timestamp": "2025-11-28T00:00:00"}
    )
    mock.liveness_probe = AsyncMock(
        return_value={"status": "alive", "timestamp": "2025-11-28T00:00:00"}
    )
    mock.readiness_probe = AsyncMock(
        return_value={"status": "ready", "timestamp": "2025-11-28T00:00:00"}
    )
    mock.startup_probe = AsyncMock(
        return_value={"status": "started", "timestamp": "2025-11-28T00:00:00"}
    )
    mock.detailed_health = AsyncMock(
        return_value={
            "status": "healthy",
            "uptime_seconds": 3600,
            "dependencies": {},
        }
    )
    return mock


@pytest.fixture
def test_client(
    mock_git_ingestion_service, mock_webhook_handler, mock_health_endpoints
):
    """Create a test client with mocked services."""
    import sys

    # Clear ALL src modules to ensure completely fresh imports
    # This prevents module state pollution from other test files
    modules_to_clear = [k for k in list(sys.modules.keys()) if k.startswith("src.")]
    for mod in modules_to_clear:
        del sys.modules[mod]

    # Import module fresh after clearing cache
    import src.api.main as main_module

    # Patch the global service instances
    with (
        patch.object(main_module, "git_ingestion_service", mock_git_ingestion_service),
        patch.object(main_module, "webhook_handler", mock_webhook_handler),
        patch.object(main_module, "health_endpoints", mock_health_endpoints),
    ):
        # Override lifespan to skip real initialization
        main_module.app.router.lifespan_context = None

        client = TestClient(main_module.app, raise_server_exceptions=False)
        yield client


# ============================================================================
# Root Endpoint Tests
# ============================================================================


class TestRootEndpoint:
    """Tests for the root endpoint."""

    def test_root_returns_service_info(self, test_client):
        """Test that root endpoint returns service information."""
        response = test_client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "Project Aura API"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data


# ============================================================================
# Health Endpoint Tests
# ============================================================================


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, test_client, mock_health_endpoints):
        """Test AWS ALB health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"

    def test_liveness_probe_alive(self, test_client, mock_health_endpoints):
        """Test Kubernetes liveness probe when alive."""
        response = test_client.get("/health/live")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "alive"

    def test_liveness_probe_dead(self, test_client, mock_health_endpoints):
        """Test Kubernetes liveness probe when dead."""
        mock_health_endpoints.liveness_probe.return_value = {
            "status": "dead",
            "error": "Service crashed",
        }

        response = test_client.get("/health/live")
        assert response.status_code == 500

    def test_readiness_probe_ready(self, test_client, mock_health_endpoints):
        """Test Kubernetes readiness probe when ready."""
        response = test_client.get("/health/ready")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ready"

    def test_readiness_probe_not_ready(self, test_client, mock_health_endpoints):
        """Test Kubernetes readiness probe when not ready."""
        mock_health_endpoints.readiness_probe.return_value = {
            "status": "not_ready",
            "reason": "Dependencies unavailable",
        }

        response = test_client.get("/health/ready")
        assert response.status_code == 503

    def test_startup_probe_started(self, test_client, mock_health_endpoints):
        """Test Kubernetes startup probe when started."""
        response = test_client.get("/health/startup")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "started"

    def test_startup_probe_starting(self, test_client, mock_health_endpoints):
        """Test Kubernetes startup probe when still starting."""
        mock_health_endpoints.startup_probe.return_value = {
            "status": "starting",
            "progress": "Loading models...",
        }

        response = test_client.get("/health/startup")
        assert response.status_code == 503

    def test_detailed_health(self, test_client, mock_health_endpoints):
        """Test detailed health endpoint."""
        response = test_client.get("/health/detailed")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "uptime_seconds" in data


# ============================================================================
# Ingestion Endpoint Tests
# ============================================================================


class TestIngestionEndpoints:
    """Tests for git ingestion endpoints."""

    def test_trigger_ingestion(self, test_client, mock_git_ingestion_service):
        """Test triggering a repository ingestion."""
        response = test_client.post(
            "/api/v1/ingest",
            json={
                "repository_url": "https://github.com/test/repo",
                "branch": "main",
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "queued"
        assert "job_id" in data

    def test_trigger_ingestion_with_options(
        self, test_client, mock_git_ingestion_service
    ):
        """Test triggering ingestion with all options."""
        response = test_client.post(
            "/api/v1/ingest",
            json={
                "repository_url": "https://github.com/test/repo",
                "branch": "develop",
                "force_refresh": True,
                "shallow_clone": False,
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "queued"

    def test_get_job_status(self, test_client, mock_git_ingestion_service):
        """Test getting job status."""
        response = test_client.get("/api/v1/jobs/test-job-123")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == "test-job-123"
        assert data["status"] == "completed"
        assert data["files_processed"] == 10

    def test_get_job_status_not_found(self, test_client, mock_git_ingestion_service):
        """Test getting status for non-existent job."""
        mock_git_ingestion_service.get_job_status.return_value = None

        response = test_client.get("/api/v1/jobs/nonexistent")
        assert response.status_code == 404

    def test_list_jobs(self, test_client, mock_git_ingestion_service):
        """Test listing all jobs."""
        response = test_client.get("/api/v1/jobs")
        assert response.status_code == 200

        data = response.json()
        assert "jobs" in data
        assert "total" in data

    def test_list_active_jobs_only(self, test_client, mock_git_ingestion_service):
        """Test listing only active jobs."""
        response = test_client.get("/api/v1/jobs?active_only=true")
        assert response.status_code == 200

        mock_git_ingestion_service.list_active_jobs.assert_called_once()


# ============================================================================
# Webhook Endpoint Tests
# ============================================================================


class TestWebhookEndpoints:
    """Tests for GitHub webhook endpoints."""

    def test_github_webhook_push_event(self, test_client, mock_webhook_handler):
        """Test processing a GitHub push webhook."""
        payload = {
            "ref": "refs/heads/main",
            "repository": {
                "full_name": "test/repo",
                "clone_url": "https://github.com/test/repo.git",
            },
            "commits": [
                {"added": ["src/new.py"], "modified": ["src/main.py"], "removed": []}
            ],
        }

        response = test_client.post(
            "/webhook/github",
            content=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-123",
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "accepted"
        assert data["details"]["event_type"] == "push"

    def test_github_webhook_invalid_event(self, test_client, mock_webhook_handler):
        """Test webhook with unsupported event type."""
        mock_webhook_handler.parse_event.return_value = None

        response = test_client.post(
            "/webhook/github",
            content=json.dumps({"action": "created"}),
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "star",  # Unsupported event
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ignored"

    def test_github_webhook_with_signature(self, test_client, mock_webhook_handler):
        """Test webhook with HMAC signature validation."""
        payload = json.dumps({"test": "data"})
        secret = "test-secret"
        signature = (
            "sha256="
            + hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        response = test_client.post(
            "/webhook/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": signature,
            },
        )
        assert response.status_code == 200

    def test_get_webhook_queue(self, test_client, mock_webhook_handler):
        """Test getting webhook queue status."""
        response = test_client.get("/webhook/queue")
        assert response.status_code == 200

        data = response.json()
        assert "queue_length" in data

    def test_clear_webhook_queue(self, test_client, mock_webhook_handler):
        """Test clearing webhook queue."""
        response = test_client.delete("/webhook/queue")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "cleared"


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_json_body(self, test_client):
        """Test handling of invalid JSON in request body."""
        response = test_client.post(
            "/api/v1/ingest",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422  # Validation error

    def test_missing_required_field(self, test_client):
        """Test handling of missing required field."""
        response = test_client.post(
            "/api/v1/ingest",
            json={},  # Missing repository_url
        )
        assert response.status_code == 422

    def test_not_found_endpoint(self, test_client):
        """Test 404 for non-existent endpoint."""
        response = test_client.get("/nonexistent/endpoint")
        assert response.status_code == 404
