"""
Project Aura - Health Endpoints Tests

Tests for the health check API endpoints used by Kubernetes probes
and AWS load balancers.

Target: 85% coverage of src/api/health_endpoints.py
"""

import os
import platform
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

# Set environment before importing
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

from src.api.health_endpoints import (
    HealthCheckEndpoints,
    setup_health_endpoints_fastapi,
)
from src.services.observability_service import ServiceHealth


def create_mock_monitor(health=ServiceHealth.HEALTHY, start_time=None):
    """Create a mock monitor with configurable settings."""
    mock = MagicMock()
    mock.get_service_health.return_value = health
    mock.service_start_time = start_time or datetime.now(timezone.utc)
    mock.get_health_report.return_value = {
        "service_name": "test-service",
        "status": health.value,
        "metrics": {},
    }
    return mock


class TestHealthCheckEndpointsInit:
    """Tests for HealthCheckEndpoints initialization."""

    def test_init_without_services(self):
        """Test initialization without any services."""
        health = HealthCheckEndpoints()

        assert health.neptune is None
        assert health.opensearch is None
        assert health.bedrock is None
        assert health.startup_complete is False
        assert isinstance(health.startup_time, datetime)

    def test_init_with_all_services(self):
        """Test initialization with all services."""
        mock_neptune = MagicMock()
        mock_opensearch = MagicMock()
        mock_bedrock = MagicMock()

        health = HealthCheckEndpoints(
            neptune_service=mock_neptune,
            opensearch_service=mock_opensearch,
            bedrock_service=mock_bedrock,
        )

        assert health.neptune == mock_neptune
        assert health.opensearch == mock_opensearch
        assert health.bedrock == mock_bedrock

    def test_init_with_partial_services(self):
        """Test initialization with only some services."""
        mock_neptune = MagicMock()

        health = HealthCheckEndpoints(neptune_service=mock_neptune)

        assert health.neptune == mock_neptune
        assert health.opensearch is None
        assert health.bedrock is None


class TestLivenessProbe:
    """Tests for the liveness probe endpoint."""

    @pytest.mark.asyncio
    async def test_liveness_probe_success(self):
        """Test liveness probe returns alive status."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.HEALTHY)

        result = await health.liveness_probe()

        assert result["status"] == "alive"
        assert result["health"] == "healthy"
        assert "timestamp" in result
        assert "uptime_seconds" in result
        assert result["uptime_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_liveness_probe_degraded(self):
        """Test liveness probe with degraded health."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.DEGRADED)

        result = await health.liveness_probe()

        assert result["status"] == "alive"
        assert result["health"] == "degraded"

    @pytest.mark.asyncio
    async def test_liveness_probe_unhealthy_still_alive(self):
        """Test liveness probe returns alive even when unhealthy (service is running)."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.UNHEALTHY)

        result = await health.liveness_probe()

        assert result["status"] == "alive"
        assert result["health"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_liveness_probe_exception(self):
        """Test liveness probe handles exception."""
        health = HealthCheckEndpoints()
        mock_monitor = MagicMock()
        mock_monitor.get_service_health.side_effect = Exception("Monitor error")
        health.monitor = mock_monitor

        result = await health.liveness_probe()

        assert result["status"] == "dead"
        assert "Monitor error" in result["error"]
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_liveness_probe_timestamp_format(self):
        """Test liveness probe timestamp is ISO format."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.HEALTHY)

        result = await health.liveness_probe()

        # Verify timestamp is valid ISO format
        timestamp = result["timestamp"]
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert isinstance(parsed, datetime)


class TestReadinessProbe:
    """Tests for the readiness probe endpoint."""

    @pytest.mark.asyncio
    async def test_readiness_probe_ready(self):
        """Test readiness probe returns ready status."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.HEALTHY)

        result = await health.readiness_probe()

        assert result["status"] == "ready"
        assert result["health"] == "healthy"
        assert "dependencies" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_readiness_probe_degraded_still_ready(self):
        """Test readiness probe returns ready when degraded (still accepting traffic)."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.DEGRADED)

        result = await health.readiness_probe()

        assert result["status"] == "ready"
        assert result["health"] == "degraded"

    @pytest.mark.asyncio
    async def test_readiness_probe_unhealthy_service(self):
        """Test readiness probe returns not_ready when unhealthy."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.UNHEALTHY)

        result = await health.readiness_probe()

        assert result["status"] == "not_ready"
        assert "UNHEALTHY" in result["reason"]

    @pytest.mark.asyncio
    async def test_readiness_probe_dependency_not_ready(self):
        """Test readiness probe when dependencies are not ready."""
        mock_neptune = MagicMock()
        health = HealthCheckEndpoints(neptune_service=mock_neptune)
        health.monitor = create_mock_monitor(ServiceHealth.HEALTHY)

        # Mock _check_neptune to return not ready
        async def mock_check_neptune():
            return {"ready": False, "error": "Connection refused"}

        health._check_neptune = mock_check_neptune

        result = await health.readiness_probe()

        assert result["status"] == "not_ready"
        assert "neptune" in result["reason"]
        assert "dependencies" in result

    @pytest.mark.asyncio
    async def test_readiness_probe_exception(self):
        """Test readiness probe handles exception."""
        health = HealthCheckEndpoints()
        mock_monitor = MagicMock()
        mock_monitor.get_service_health.side_effect = Exception("Check failed")
        health.monitor = mock_monitor

        result = await health.readiness_probe()

        assert result["status"] == "not_ready"
        assert "Probe error" in result["reason"]
        assert "Check failed" in result["reason"]

    @pytest.mark.asyncio
    async def test_readiness_probe_all_dependencies_ready(self):
        """Test readiness probe with all dependencies ready."""
        mock_neptune = MagicMock()
        mock_opensearch = MagicMock()
        mock_bedrock = MagicMock()

        health = HealthCheckEndpoints(
            neptune_service=mock_neptune,
            opensearch_service=mock_opensearch,
            bedrock_service=mock_bedrock,
        )
        health.monitor = create_mock_monitor(ServiceHealth.HEALTHY)

        # Mock all checks to return ready
        async def mock_check_neptune():
            return {"ready": True, "mode": "MOCK"}

        async def mock_check_opensearch():
            return {"ready": True, "latency_ms": 5}

        async def mock_check_bedrock():
            return {"ready": True, "latency_ms": 10}

        health._check_neptune = mock_check_neptune
        health._check_opensearch = mock_check_opensearch
        health._check_bedrock = mock_check_bedrock

        result = await health.readiness_probe()

        assert result["status"] == "ready"
        assert result["dependencies"]["neptune"]["ready"] is True
        assert result["dependencies"]["opensearch"]["ready"] is True
        assert result["dependencies"]["bedrock"]["ready"] is True


class TestStartupProbe:
    """Tests for the startup probe endpoint."""

    @pytest.mark.asyncio
    async def test_startup_probe_started(self):
        """Test startup probe returns started status."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor()

        result = await health.startup_probe()

        assert result["status"] == "started"
        assert "startup_tasks" in result
        assert result["startup_tasks"]["configuration_loaded"] is True
        assert result["startup_tasks"]["monitoring_initialized"] is True
        assert result["startup_tasks"]["dependencies_checked"] is True
        assert "startup_duration_seconds" in result
        assert health.startup_complete is True

    @pytest.mark.asyncio
    async def test_startup_probe_already_complete(self):
        """Test startup probe when already complete."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor()
        health.startup_complete = True

        result = await health.startup_probe()

        assert result["status"] == "started"

    @pytest.mark.asyncio
    async def test_startup_probe_no_monitor(self):
        """Test startup probe when monitor not initialized."""
        health = HealthCheckEndpoints()
        health.monitor = None

        result = await health.startup_probe()

        assert result["status"] == "starting"
        assert result["startup_tasks"]["monitoring_initialized"] is False

    @pytest.mark.asyncio
    async def test_startup_probe_exception(self):
        """Test startup probe handles exception."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor()

        # Make startup_tasks evaluation fail
        async def mock_quick_check():
            raise Exception("Dependency check failed")

        health._quick_dependency_check = mock_quick_check

        result = await health.startup_probe()

        assert result["status"] == "starting"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_startup_probe_duration_is_none_when_not_started(self):
        """Test startup probe returns None duration when not fully started."""
        health = HealthCheckEndpoints()
        health.monitor = None  # Not initialized

        result = await health.startup_probe()

        assert result["status"] == "starting"
        assert result["startup_duration_seconds"] is None

    @pytest.mark.asyncio
    async def test_startup_probe_logs_completion(self):
        """Test startup probe logs completion on first success."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor()
        health.startup_complete = False

        with patch("src.api.health_endpoints.logger") as mock_logger:
            result = await health.startup_probe()

            assert result["status"] == "started"
            assert health.startup_complete is True
            # Logger.info should be called with startup complete message
            mock_logger.info.assert_called()


class TestDetailedHealth:
    """Tests for detailed health endpoint."""

    @pytest.mark.asyncio
    async def test_detailed_health(self):
        """Test detailed health returns comprehensive report."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.HEALTHY)

        result = await health.detailed_health()

        assert "service_name" in result
        assert "dependencies" in result
        assert "probe_results" in result
        assert result["probe_results"]["liveness"] == "alive"
        assert result["probe_results"]["readiness"] == "ready"
        assert result["probe_results"]["startup"] == "started"

    @pytest.mark.asyncio
    async def test_detailed_health_includes_health_report(self):
        """Test detailed health includes monitor health report."""
        health = HealthCheckEndpoints()
        mock_monitor = create_mock_monitor(ServiceHealth.HEALTHY)
        mock_monitor.get_health_report.return_value = {
            "service_name": "aura-orchestrator",
            "status": "healthy",
            "metrics": {"request_count": 100},
        }
        health.monitor = mock_monitor

        result = await health.detailed_health()

        assert result["service_name"] == "aura-orchestrator"
        assert result["status"] == "healthy"
        assert result["metrics"]["request_count"] == 100


class TestAwsHealthCheck:
    """Tests for AWS ALB health check endpoint."""

    @pytest.mark.asyncio
    async def test_aws_health_check_healthy(self):
        """Test AWS health check returns healthy status."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.HEALTHY)

        result = await health.aws_health_check()

        assert result["status"] == "healthy"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_aws_health_check_degraded(self):
        """Test AWS health check returns degraded status."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.DEGRADED)

        result = await health.aws_health_check()

        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_aws_health_check_unhealthy(self):
        """Test AWS health check returns unhealthy status."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.UNHEALTHY)

        result = await health.aws_health_check()

        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_aws_health_check_unknown(self):
        """Test AWS health check returns unknown status."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.UNKNOWN)

        result = await health.aws_health_check()

        assert result["status"] == "unknown"


class TestCheckDependencies:
    """Tests for dependency checking methods."""

    @pytest.mark.asyncio
    async def test_check_dependencies_no_services(self):
        """Test dependency check without services configured."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor()

        result = await health._check_dependencies()

        assert "neptune" in result
        assert "opensearch" in result
        assert "bedrock" in result
        assert result["neptune"]["ready"] is True
        assert result["neptune"]["note"] == "Not configured"
        assert result["opensearch"]["ready"] is True
        assert result["bedrock"]["ready"] is True

    @pytest.mark.asyncio
    async def test_check_dependencies_with_services(self):
        """Test dependency check with services configured."""
        mock_neptune = MagicMock()
        mock_opensearch = MagicMock()
        mock_bedrock = MagicMock()

        health = HealthCheckEndpoints(
            neptune_service=mock_neptune,
            opensearch_service=mock_opensearch,
            bedrock_service=mock_bedrock,
        )
        health.monitor = create_mock_monitor()

        # Mock the individual check methods
        async def mock_check_neptune():
            return {"ready": True, "mode": "MOCK"}

        async def mock_check_opensearch():
            return {"ready": True, "latency_ms": 5}

        async def mock_check_bedrock():
            return {"ready": True, "latency_ms": 10}

        health._check_neptune = mock_check_neptune
        health._check_opensearch = mock_check_opensearch
        health._check_bedrock = mock_check_bedrock

        result = await health._check_dependencies()

        assert result["neptune"]["ready"] is True
        assert result["opensearch"]["ready"] is True
        assert result["bedrock"]["ready"] is True

    @pytest.mark.asyncio
    async def test_check_dependencies_partial_services(self):
        """Test dependency check with only neptune configured."""
        mock_neptune = MagicMock()

        health = HealthCheckEndpoints(neptune_service=mock_neptune)
        health.monitor = create_mock_monitor()

        async def mock_check_neptune():
            return {"ready": True, "mode": "AWS", "latency_ms": 25}

        health._check_neptune = mock_check_neptune

        result = await health._check_dependencies()

        assert result["neptune"]["ready"] is True
        assert result["opensearch"]["note"] == "Not configured"
        assert result["bedrock"]["note"] == "Not configured"


class TestQuickDependencyCheck:
    """Tests for quick dependency check."""

    @pytest.mark.asyncio
    async def test_quick_dependency_check_success(self):
        """Test quick dependency check returns True."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor()

        result = await health._quick_dependency_check()

        assert result is True


class TestCheckNeptune:
    """Tests for Neptune health check."""

    @pytest.mark.asyncio
    async def test_check_neptune_mock_mode(self):
        """Test Neptune check in mock mode."""
        from src.services.neptune_graph_service import NeptuneMode

        mock_neptune = MagicMock()
        mock_neptune.mode = NeptuneMode.MOCK

        health = HealthCheckEndpoints(neptune_service=mock_neptune)
        health.monitor = create_mock_monitor()

        result = await health._check_neptune()

        assert result["ready"] is True
        assert result["mode"] == "MOCK"
        assert result["latency_ms"] == 0

    @pytest.mark.asyncio
    async def test_check_neptune_aws_mode(self):
        """Test Neptune check in AWS mode."""
        from src.services.neptune_graph_service import NeptuneMode

        mock_neptune = MagicMock()
        mock_neptune.mode = NeptuneMode.AWS
        mock_neptune.search_by_name.return_value = []

        health = HealthCheckEndpoints(neptune_service=mock_neptune)
        health.monitor = create_mock_monitor()

        result = await health._check_neptune()

        assert result["ready"] is True
        assert result["mode"] == "AWS"
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_check_neptune_exception(self):
        """Test Neptune check handles exception."""
        from src.services.neptune_graph_service import NeptuneMode

        mock_neptune = MagicMock()
        mock_neptune.mode = NeptuneMode.AWS
        mock_neptune.search_by_name.side_effect = Exception("Connection failed")

        health = HealthCheckEndpoints(neptune_service=mock_neptune)
        health.monitor = create_mock_monitor()

        result = await health._check_neptune()

        assert result["ready"] is False
        assert "Connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_check_neptune_latency_measured(self):
        """Test Neptune check measures latency accurately."""
        from src.services.neptune_graph_service import NeptuneMode

        mock_neptune = MagicMock()
        mock_neptune.mode = NeptuneMode.AWS
        mock_neptune.search_by_name.return_value = []

        health = HealthCheckEndpoints(neptune_service=mock_neptune)
        health.monitor = create_mock_monitor()

        result = await health._check_neptune()

        assert result["latency_ms"] >= 0
        assert isinstance(result["latency_ms"], float)


class TestCheckOpenSearch:
    """Tests for OpenSearch health check."""

    @pytest.mark.asyncio
    async def test_check_opensearch_success(self):
        """Test OpenSearch check returns ready."""
        mock_opensearch = MagicMock()

        health = HealthCheckEndpoints(opensearch_service=mock_opensearch)
        health.monitor = create_mock_monitor()

        result = await health._check_opensearch()

        assert result["ready"] is True
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_check_opensearch_returns_mock_note(self):
        """Test OpenSearch check includes mock note."""
        mock_opensearch = MagicMock()

        health = HealthCheckEndpoints(opensearch_service=mock_opensearch)
        health.monitor = create_mock_monitor()

        result = await health._check_opensearch()

        assert result["note"] == "Mock check"


class TestCheckBedrock:
    """Tests for Bedrock health check."""

    @pytest.mark.asyncio
    async def test_check_bedrock_success(self):
        """Test Bedrock check returns ready."""
        mock_bedrock = MagicMock()

        health = HealthCheckEndpoints(bedrock_service=mock_bedrock)
        health.monitor = create_mock_monitor()

        result = await health._check_bedrock()

        assert result["ready"] is True
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_check_bedrock_returns_mock_note(self):
        """Test Bedrock check includes mock note."""
        mock_bedrock = MagicMock()

        health = HealthCheckEndpoints(bedrock_service=mock_bedrock)
        health.monitor = create_mock_monitor()

        result = await health._check_bedrock()

        assert result["note"] == "Mock check"


class TestSetupHealthEndpointsFastapi:
    """Tests for FastAPI integration with mock app."""

    @pytest.mark.asyncio
    async def test_setup_health_endpoints_registers_routes(self):
        """Test that health endpoints are registered in FastAPI app."""
        mock_app = MagicMock()
        mock_app.get = MagicMock(return_value=lambda f: f)

        services = {
            "neptune_service": MagicMock(),
            "opensearch_service": MagicMock(),
            "bedrock_service": MagicMock(),
        }

        await setup_health_endpoints_fastapi(mock_app, services)

        # Verify all routes were registered
        assert mock_app.get.call_count == 5
        call_args = [call[0][0] for call in mock_app.get.call_args_list]
        assert "/health" in call_args
        assert "/health/live" in call_args
        assert "/health/ready" in call_args
        assert "/health/startup" in call_args
        assert "/health/detailed" in call_args

    @pytest.mark.asyncio
    async def test_setup_health_endpoints_empty_services(self):
        """Test setup with empty services dict."""
        mock_app = MagicMock()
        mock_app.get = MagicMock(return_value=lambda f: f)

        await setup_health_endpoints_fastapi(mock_app, {})

        assert mock_app.get.call_count == 5


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_startup_probe_sets_completion_flag(self):
        """Test startup probe sets startup_complete flag when all checks pass."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor()
        health.startup_complete = False

        result = await health.startup_probe()

        # After successful startup probe, the flag should be set to True
        assert health.startup_complete is True
        assert result["status"] == "started"

    @pytest.mark.asyncio
    async def test_readiness_probe_multiple_failed_deps(self):
        """Test readiness probe with multiple failed dependencies."""
        mock_neptune = MagicMock()
        mock_opensearch = MagicMock()

        health = HealthCheckEndpoints(
            neptune_service=mock_neptune, opensearch_service=mock_opensearch
        )
        health.monitor = create_mock_monitor(ServiceHealth.HEALTHY)

        # Mock both dependencies as not ready
        async def mock_check_neptune():
            return {"ready": False, "error": "Neptune down"}

        async def mock_check_opensearch():
            return {"ready": False, "error": "OpenSearch down"}

        health._check_neptune = mock_check_neptune
        health._check_opensearch = mock_check_opensearch

        result = await health.readiness_probe()

        assert result["status"] == "not_ready"
        assert "neptune" in result["reason"]
        assert "opensearch" in result["reason"]

    @pytest.mark.asyncio
    async def test_liveness_probe_uptime_calculation(self):
        """Test liveness probe calculates uptime correctly."""
        health = HealthCheckEndpoints()
        # Set start time 60 seconds ago
        start_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        health.monitor = create_mock_monitor(
            ServiceHealth.HEALTHY, start_time=start_time
        )

        result = await health.liveness_probe()

        assert result["uptime_seconds"] >= 60

    @pytest.mark.asyncio
    async def test_detailed_health_includes_all_probes(self):
        """Test detailed health includes results from all probes."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor(ServiceHealth.HEALTHY)

        result = await health.detailed_health()

        assert "probe_results" in result
        assert all(
            probe in result["probe_results"]
            for probe in ["liveness", "readiness", "startup"]
        )


class TestFastAPIEndpointExecution:
    """Tests for FastAPI endpoint execution via TestClient.

    These tests actually exercise the endpoint handler functions
    registered by setup_health_endpoints_fastapi.
    """

    @pytest.mark.asyncio
    async def test_health_endpoint_via_testclient(self):
        """Test /health endpoint returns proper response."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        services = {
            "neptune_service": None,
            "opensearch_service": None,
            "bedrock_service": None,
        }

        await setup_health_endpoints_fastapi(app, services)

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_liveness_endpoint_via_testclient(self):
        """Test /health/live endpoint returns proper response."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        services = {}

        await setup_health_endpoints_fastapi(app, services)

        client = TestClient(app)
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "health" in data
        assert "uptime_seconds" in data

    @pytest.mark.asyncio
    async def test_readiness_endpoint_via_testclient(self):
        """Test /health/ready endpoint returns proper response."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        services = {}

        await setup_health_endpoints_fastapi(app, services)

        client = TestClient(app)
        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["ready", "not_ready"]
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_startup_endpoint_via_testclient(self):
        """Test /health/startup endpoint returns proper response."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        services = {}

        await setup_health_endpoints_fastapi(app, services)

        client = TestClient(app)
        response = client.get("/health/startup")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["started", "starting"]
        assert "startup_tasks" in data

    @pytest.mark.asyncio
    async def test_detailed_endpoint_via_testclient(self):
        """Test /health/detailed endpoint returns proper response."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        services = {}

        await setup_health_endpoints_fastapi(app, services)

        client = TestClient(app)
        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert "probe_results" in data
        assert "dependencies" in data

    @pytest.mark.asyncio
    async def test_all_endpoints_with_mock_services(self):
        """Test all endpoints work with mock services configured."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        mock_neptune = MagicMock()
        mock_opensearch = MagicMock()
        mock_bedrock = MagicMock()

        services = {
            "neptune_service": mock_neptune,
            "opensearch_service": mock_opensearch,
            "bedrock_service": mock_bedrock,
        }

        await setup_health_endpoints_fastapi(app, services)

        client = TestClient(app)

        # Test all endpoints return 200
        endpoints = [
            "/health",
            "/health/live",
            "/health/ready",
            "/health/startup",
            "/health/detailed",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} failed"


class TestLoggingBehavior:
    """Tests for logging behavior in health endpoints."""

    @pytest.mark.asyncio
    async def test_setup_logs_registered_endpoints(self):
        """Test setup_health_endpoints_fastapi logs endpoint registration."""
        from fastapi import FastAPI

        app = FastAPI()
        services = {}

        with patch("src.api.health_endpoints.logger") as mock_logger:
            await setup_health_endpoints_fastapi(app, services)

            # Should log multiple info messages about registered endpoints
            assert mock_logger.info.call_count >= 5

    @pytest.mark.asyncio
    async def test_liveness_probe_logs_critical_on_failure(self):
        """Test liveness probe logs critical when it fails."""
        health = HealthCheckEndpoints()
        mock_monitor = MagicMock()
        mock_monitor.get_service_health.side_effect = Exception("Fatal error")
        health.monitor = mock_monitor

        with patch("src.api.health_endpoints.logger") as mock_logger:
            result = await health.liveness_probe()

            assert result["status"] == "dead"
            mock_logger.critical.assert_called_once()

    @pytest.mark.asyncio
    async def test_readiness_probe_logs_error_on_failure(self):
        """Test readiness probe logs error when it fails."""
        health = HealthCheckEndpoints()
        mock_monitor = MagicMock()
        mock_monitor.get_service_health.side_effect = Exception("Check error")
        health.monitor = mock_monitor

        with patch("src.api.health_endpoints.logger") as mock_logger:
            result = await health.readiness_probe()

            assert result["status"] == "not_ready"
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_probe_logs_error_on_failure(self):
        """Test startup probe logs error when it fails."""
        health = HealthCheckEndpoints()
        health.monitor = create_mock_monitor()

        async def mock_quick_check():
            raise Exception("Startup failed")

        health._quick_dependency_check = mock_quick_check

        with patch("src.api.health_endpoints.logger") as mock_logger:
            result = await health.startup_probe()

            assert result["status"] == "starting"
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_neptune_check_logs_warning_on_failure(self):
        """Test Neptune check logs warning when it fails."""
        from src.services.neptune_graph_service import NeptuneMode

        mock_neptune = MagicMock()
        mock_neptune.mode = NeptuneMode.AWS
        mock_neptune.search_by_name.side_effect = Exception("Neptune error")

        health = HealthCheckEndpoints(neptune_service=mock_neptune)
        health.monitor = create_mock_monitor()

        with patch("src.api.health_endpoints.logger") as mock_logger:
            result = await health._check_neptune()

            assert result["ready"] is False
            mock_logger.warning.assert_called_once()
