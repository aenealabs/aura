"""Unit tests for Observability MCP Adapters (ADR-025 Phase 5)."""

import platform
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.observability_mcp_adapters import ObservabilityMCPAdapters


class AsyncContextManagerMock:
    """Helper class to create proper async context manager mocks."""

    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_enterprise_mode():
    """Mock Enterprise mode configuration."""
    mock_config = MagicMock()
    mock_config.is_defense_mode = False  # Enterprise mode
    mock_config.is_enterprise_mode = True
    with patch(
        "src.config.integration_config.get_integration_config", return_value=mock_config
    ):
        yield


@pytest.fixture
def adapters(mock_enterprise_mode):
    """Create ObservabilityMCPAdapters instance."""
    with patch.dict(
        "os.environ",
        {
            "DATADOG_API_KEY": "test-api-key",
            "DATADOG_APP_KEY": "test-app-key",
            "PROMETHEUS_URL": "http://prometheus.test:9090",
        },
    ):
        return ObservabilityMCPAdapters()


class TestDatadogTraces:
    """Test Datadog APM trace querying."""

    @pytest.mark.asyncio
    async def test_query_traces_success(self, adapters):
        """Test successful Datadog trace query."""
        start = datetime.now(UTC) - timedelta(hours=1)
        end = datetime.now(UTC)

        # Create mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": [
                    {
                        "trace_id": "123",
                        "service": "aura-api",
                        "error": "NullPointerException",
                    }
                ]
            }
        )

        # Create mock session with proper async context managers
        mock_session = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        with patch(
            "aiohttp.ClientSession", return_value=AsyncContextManagerMock(mock_session)
        ):
            traces = await adapters.datadog_query_traces(
                service="aura-api", time_range=(start, end), error_only=True
            )

            assert len(traces) == 1
            assert traces[0]["trace_id"] == "123"

    @pytest.mark.asyncio
    async def test_query_traces_no_credentials(self, mock_enterprise_mode):
        """Test Datadog query without credentials."""
        with patch.dict("os.environ", {}, clear=True):
            adapters = ObservabilityMCPAdapters()

            traces = await adapters.datadog_query_traces(
                service="aura-api", time_range=(datetime.now(UTC), datetime.now(UTC))
            )

            assert traces == []


class TestPrometheusMetrics:
    """Test Prometheus metrics querying."""

    @pytest.mark.asyncio
    async def test_query_range_success(self, adapters):
        """Test successful Prometheus range query."""
        start = datetime.now(UTC) - timedelta(minutes=30)
        end = datetime.now(UTC)

        # Create mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "result": [{"values": [[1638835200, "0.5"], [1638835260, "0.8"]]}]
                }
            }
        )

        # Create mock session with proper async context managers
        mock_session = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        with patch(
            "aiohttp.ClientSession", return_value=AsyncContextManagerMock(mock_session)
        ):
            metrics = await adapters.prometheus_query_range(
                query="rate(http_requests_total[5m])",
                start_time=start,
                end_time=end,
                step="1m",
            )

            assert "data" in metrics
            assert len(metrics["data"]["result"]) == 1

    @pytest.mark.asyncio
    async def test_query_instant_success(self, adapters):
        """Test Prometheus instant query."""
        # Create mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"data": {"result": [{"value": [1638835200, "42"]}]}}
        )

        # Create mock session with proper async context managers
        mock_session = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        with patch(
            "aiohttp.ClientSession", return_value=AsyncContextManagerMock(mock_session)
        ):
            metrics = await adapters.prometheus_query_instant(
                query='up{job="aura-api"}'
            )

            assert "data" in metrics
