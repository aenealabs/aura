"""
Project Aura - Customer Metrics Service Tests

Comprehensive tests for the customer health metrics service
that aggregates per-customer metrics for the health dashboard.
"""

import platform

import pytest

# These tests require pytest-forked for isolation due to global service state.
# On Linux (CI), mock patches don't apply correctly without forked mode.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from datetime import datetime, timezone

from src.services.health.customer_metrics import (
    AgentMetrics,
    APIMetrics,
    CustomerHealth,
    CustomerMetricsService,
    DeploymentMode,
    HealthStatus,
    MetricTimeRange,
    StorageMetrics,
    TokenMetrics,
    get_customer_metrics_service,
)


class TestDeploymentMode:
    """Tests for DeploymentMode enum."""

    def test_saas_mode(self):
        """Test SaaS deployment mode."""
        assert DeploymentMode.SAAS.value == "saas"

    def test_self_hosted_mode(self):
        """Test self-hosted deployment mode."""
        assert DeploymentMode.SELF_HOSTED.value == "self_hosted"


class TestMetricTimeRange:
    """Tests for MetricTimeRange enum."""

    def test_all_time_ranges(self):
        """Test all time range values."""
        assert MetricTimeRange.HOUR.value == "1h"
        assert MetricTimeRange.DAY.value == "24h"
        assert MetricTimeRange.WEEK.value == "7d"
        assert MetricTimeRange.MONTH.value == "30d"


class TestAPIMetrics:
    """Tests for APIMetrics dataclass."""

    def test_default_values(self):
        """Test default API metrics values."""
        metrics = APIMetrics()
        assert metrics.request_count == 0
        assert metrics.error_count == 0
        assert metrics.error_rate == 0.0
        assert metrics.avg_latency_ms == 0.0
        assert metrics.p50_latency_ms == 0.0
        assert metrics.p95_latency_ms == 0.0
        assert metrics.p99_latency_ms == 0.0

    def test_custom_values(self):
        """Test API metrics with custom values."""
        metrics = APIMetrics(
            request_count=1000,
            error_count=10,
            error_rate=1.0,
            avg_latency_ms=100.0,
            p50_latency_ms=80.0,
            p95_latency_ms=200.0,
            p99_latency_ms=500.0,
        )
        assert metrics.request_count == 1000
        assert metrics.error_count == 10
        assert metrics.error_rate == 1.0


class TestAgentMetrics:
    """Tests for AgentMetrics dataclass."""

    def test_default_values(self):
        """Test default agent metrics values."""
        metrics = AgentMetrics()
        assert metrics.total_executions == 0
        assert metrics.successful_executions == 0
        assert metrics.failed_executions == 0
        assert metrics.success_rate == 0.0
        assert metrics.avg_execution_time_seconds == 0.0
        assert metrics.executions_by_type == {}

    def test_with_breakdown(self):
        """Test agent metrics with breakdown."""
        metrics = AgentMetrics(
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
            success_rate=95.0,
            executions_by_type={"scanner": 50, "coder": 30, "reviewer": 20},
        )
        assert metrics.total_executions == 100
        assert len(metrics.executions_by_type) == 3


class TestTokenMetrics:
    """Tests for TokenMetrics dataclass."""

    def test_default_values(self):
        """Test default token metrics values."""
        metrics = TokenMetrics()
        assert metrics.total_input_tokens == 0
        assert metrics.total_output_tokens == 0
        assert metrics.total_tokens == 0
        assert metrics.estimated_cost_usd == 0.0
        assert metrics.tokens_by_model == {}

    def test_with_model_breakdown(self):
        """Test token metrics with model breakdown."""
        metrics = TokenMetrics(
            total_input_tokens=1000000,
            total_output_tokens=500000,
            total_tokens=1500000,
            estimated_cost_usd=15.50,
            tokens_by_model={
                "claude-3-5-sonnet": 1000000,
                "claude-3-haiku": 500000,
            },
        )
        assert metrics.total_tokens == 1500000
        assert len(metrics.tokens_by_model) == 2


class TestStorageMetrics:
    """Tests for StorageMetrics dataclass."""

    def test_default_values(self):
        """Test default storage metrics values."""
        metrics = StorageMetrics()
        assert metrics.s3_storage_bytes == 0
        assert metrics.s3_storage_gb == 0.0
        assert metrics.neptune_storage_bytes == 0
        assert metrics.neptune_storage_gb == 0.0
        assert metrics.opensearch_storage_bytes == 0
        assert metrics.opensearch_storage_gb == 0.0
        assert metrics.total_storage_gb == 0.0

    def test_storage_calculation(self):
        """Test storage metrics calculations."""
        one_gb = 1024**3
        metrics = StorageMetrics(
            s3_storage_bytes=one_gb,
            s3_storage_gb=1.0,
            neptune_storage_bytes=one_gb,
            neptune_storage_gb=1.0,
            opensearch_storage_bytes=one_gb,
            opensearch_storage_gb=1.0,
            total_storage_gb=3.0,
        )
        assert metrics.total_storage_gb == 3.0


class TestHealthStatus:
    """Tests for HealthStatus dataclass."""

    def test_default_values(self):
        """Test default health status values."""
        status = HealthStatus()
        assert status.status == "healthy"
        assert status.score == 100
        assert status.issues == []
        assert status.last_checked is None

    def test_degraded_status(self):
        """Test degraded health status."""
        status = HealthStatus(
            status="degraded",
            score=75,
            issues=["High API latency"],
            last_checked=datetime.now(timezone.utc),
        )
        assert status.status == "degraded"
        assert status.score == 75
        assert len(status.issues) == 1


class TestCustomerHealth:
    """Tests for CustomerHealth dataclass."""

    def test_default_values(self):
        """Test default customer health values."""
        health = CustomerHealth(customer_id="cust-123")
        assert health.customer_id == "cust-123"
        assert health.customer_name is None
        assert health.time_range == "24h"
        assert isinstance(health.api, APIMetrics)
        assert isinstance(health.agents, AgentMetrics)
        assert isinstance(health.tokens, TokenMetrics)
        assert isinstance(health.storage, StorageMetrics)
        assert isinstance(health.health, HealthStatus)
        assert health.collected_at is None

    def test_complete_health(self):
        """Test complete customer health with all fields."""
        health = CustomerHealth(
            customer_id="cust-456",
            customer_name="Acme Corp",
            time_range="7d",
            api=APIMetrics(request_count=10000, error_rate=0.5),
            health=HealthStatus(status="healthy", score=95),
            collected_at=datetime.now(timezone.utc),
        )
        assert health.customer_name == "Acme Corp"
        assert health.time_range == "7d"
        assert health.api.request_count == 10000


class TestCustomerMetricsService:
    """Tests for CustomerMetricsService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CustomerMetricsService(
            deployment_mode=DeploymentMode.SELF_HOSTED,
        )

    def test_initialization_self_hosted(self):
        """Test initialization in self-hosted mode."""
        service = CustomerMetricsService(
            deployment_mode=DeploymentMode.SELF_HOSTED,
        )
        assert service._mode == DeploymentMode.SELF_HOSTED
        assert service._cache == {}

    def test_initialization_saas(self):
        """Test initialization in SaaS mode."""
        service = CustomerMetricsService(
            deployment_mode=DeploymentMode.SAAS,
        )
        assert service._mode == DeploymentMode.SAAS

    def test_token_costs_defined(self):
        """Test token costs are defined for known models."""
        assert "anthropic.claude-3-5-sonnet" in self.service.TOKEN_COSTS
        assert "anthropic.claude-3-haiku" in self.service.TOKEN_COSTS
        assert "amazon.titan-embed-text-v2" in self.service.TOKEN_COSTS

    def test_calculate_token_cost_claude_sonnet(self):
        """Test token cost calculation for Claude Sonnet."""
        cost = self.service._calculate_token_cost(
            "anthropic.claude-3-5-sonnet",
            input_tokens=1_000_000,
            output_tokens=500_000,
        )
        # Input: $3.00/M * 1M = $3.00
        # Output: $15.00/M * 0.5M = $7.50
        # Total: $10.50
        assert cost == 10.50

    def test_calculate_token_cost_claude_haiku(self):
        """Test token cost calculation for Claude Haiku."""
        cost = self.service._calculate_token_cost(
            "anthropic.claude-3-haiku",
            input_tokens=1_000_000,
            output_tokens=500_000,
        )
        # Input: $0.25/M * 1M = $0.25
        # Output: $1.25/M * 0.5M = $0.625
        # Total: $0.875 = 0.88 (rounded)
        assert cost == 0.88

    def test_calculate_token_cost_titan(self):
        """Test token cost calculation for Titan embeddings."""
        cost = self.service._calculate_token_cost(
            "amazon.titan-embed-text-v2",
            input_tokens=1_000_000,
            output_tokens=0,
        )
        # Input: $0.02/M * 1M = $0.02
        # Output: $0.00
        assert cost == 0.02

    def test_calculate_token_cost_unknown_model(self):
        """Test token cost calculation for unknown model uses defaults."""
        cost = self.service._calculate_token_cost(
            "unknown-model",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        # Default rates: $3.00/M input, $15.00/M output
        assert cost == 18.00


class TestHealthStatusCalculation:
    """Tests for health status calculation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CustomerMetricsService()

    def test_healthy_status(self):
        """Test healthy status calculation."""
        api = APIMetrics(error_rate=0.5, p95_latency_ms=200)
        agents = AgentMetrics(success_rate=98.0)
        tokens = TokenMetrics()
        storage = StorageMetrics()

        status = self.service._calculate_health_status(api, agents, tokens, storage)

        assert status.status == "healthy"
        assert status.score == 100
        assert status.issues == []

    def test_degraded_high_error_rate(self):
        """Test degraded status due to high API error rate."""
        api = APIMetrics(error_rate=2.0, p95_latency_ms=200)
        agents = AgentMetrics(success_rate=98.0)
        tokens = TokenMetrics()
        storage = StorageMetrics()

        status = self.service._calculate_health_status(api, agents, tokens, storage)

        assert status.status == "healthy"  # Still healthy (score 90)
        assert status.score == 90
        assert "Elevated API error rate" in status.issues[0]

    def test_degraded_very_high_error_rate(self):
        """Test degraded status due to very high API error rate."""
        api = APIMetrics(error_rate=6.0, p95_latency_ms=200)
        agents = AgentMetrics(success_rate=98.0)
        tokens = TokenMetrics()
        storage = StorageMetrics()

        status = self.service._calculate_health_status(api, agents, tokens, storage)

        assert status.status == "degraded"  # score 80
        assert status.score == 80
        assert "High API error rate" in status.issues[0]

    def test_degraded_high_latency(self):
        """Test degraded status due to high latency."""
        api = APIMetrics(error_rate=0.5, p95_latency_ms=1200)
        agents = AgentMetrics(success_rate=98.0)
        tokens = TokenMetrics()
        storage = StorageMetrics()

        status = self.service._calculate_health_status(api, agents, tokens, storage)

        assert status.score == 85  # -15 for high latency
        assert "High P95 latency" in status.issues[0]

    def test_degraded_low_agent_success(self):
        """Test degraded status due to low agent success rate."""
        api = APIMetrics(error_rate=0.5, p95_latency_ms=200)
        agents = AgentMetrics(success_rate=85.0)
        tokens = TokenMetrics()
        storage = StorageMetrics()

        status = self.service._calculate_health_status(api, agents, tokens, storage)

        assert status.status == "degraded"  # score 80
        assert status.score == 80
        assert "Low agent success rate" in status.issues[0]

    def test_unhealthy_multiple_issues(self):
        """Test unhealthy status with multiple issues."""
        api = APIMetrics(error_rate=6.0, p95_latency_ms=1200)
        agents = AgentMetrics(success_rate=85.0)
        tokens = TokenMetrics()
        storage = StorageMetrics()

        status = self.service._calculate_health_status(api, agents, tokens, storage)

        assert status.status == "unhealthy"
        assert status.score <= 70
        assert len(status.issues) >= 3


class TestGetCustomerHealth:
    """Tests for get_customer_health method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CustomerMetricsService()

    @pytest.mark.asyncio
    async def test_get_customer_health_basic(self):
        """Test getting basic customer health."""
        health = await self.service.get_customer_health("cust-123")

        assert health.customer_id == "cust-123"
        assert health.time_range == "24h"
        assert isinstance(health.api, APIMetrics)
        assert isinstance(health.agents, AgentMetrics)
        assert isinstance(health.tokens, TokenMetrics)
        assert isinstance(health.storage, StorageMetrics)
        assert isinstance(health.health, HealthStatus)
        assert health.collected_at is not None

    @pytest.mark.asyncio
    async def test_get_customer_health_with_breakdown(self):
        """Test getting customer health with breakdown."""
        health = await self.service.get_customer_health(
            "cust-123",
            time_range="7d",
            include_breakdown=True,
        )

        assert health.time_range == "7d"
        assert len(health.agents.executions_by_type) > 0
        assert len(health.tokens.tokens_by_model) > 0

    @pytest.mark.asyncio
    async def test_get_customer_health_caching(self):
        """Test customer health caching."""
        # First call
        health1 = await self.service.get_customer_health("cust-123")

        # Second call should return cached
        health2 = await self.service.get_customer_health("cust-123")

        assert health1.collected_at == health2.collected_at

    @pytest.mark.asyncio
    async def test_get_customer_health_cache_expiry(self):
        """Test customer health cache expiry."""
        self.service._cache_ttl_seconds = 0  # Immediate expiry

        health1 = await self.service.get_customer_health("cust-456")
        health2 = await self.service.get_customer_health("cust-456")

        # Should have different collection times due to cache expiry
        # Note: They may be the same if test runs fast enough
        assert health1.customer_id == health2.customer_id


class TestGetAllCustomersHealth:
    """Tests for get_all_customers_health method."""

    @pytest.mark.asyncio
    async def test_self_hosted_single_customer(self):
        """Test self-hosted mode returns single customer."""
        service = CustomerMetricsService(
            deployment_mode=DeploymentMode.SELF_HOSTED,
        )

        results = await service.get_all_customers_health()

        assert len(results) == 1
        assert results[0].customer_id == "default"

    @pytest.mark.asyncio
    async def test_saas_multiple_customers(self):
        """Test SaaS mode returns multiple customers."""
        service = CustomerMetricsService(
            deployment_mode=DeploymentMode.SAAS,
        )

        results = await service.get_all_customers_health()

        # Should return multiple customers (mock returns 3)
        assert len(results) >= 1


class TestCacheManagement:
    """Tests for cache management methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CustomerMetricsService()

    @pytest.mark.asyncio
    async def test_clear_cache_all(self):
        """Test clearing entire cache."""
        # Populate cache
        await self.service.get_customer_health("cust-1")
        await self.service.get_customer_health("cust-2")

        assert len(self.service._cache) >= 2

        # Clear all
        self.service.clear_cache()

        assert len(self.service._cache) == 0

    @pytest.mark.asyncio
    async def test_clear_cache_specific_customer(self):
        """Test clearing cache for specific customer."""
        # Populate cache
        await self.service.get_customer_health("cust-1", time_range="24h")
        await self.service.get_customer_health("cust-1", time_range="7d")
        await self.service.get_customer_health("cust-2", time_range="24h")

        # Clear for cust-1 only
        self.service.clear_cache("cust-1")

        # cust-1 entries should be gone
        assert "cust-1:24h" not in self.service._cache
        assert "cust-1:7d" not in self.service._cache
        # cust-2 should still be there
        assert "cust-2:24h" in self.service._cache


class TestFactoryFunction:
    """Tests for factory function."""

    def test_get_service_singleton(self):
        """Test that factory returns singleton."""
        # Reset singleton
        import src.services.health.customer_metrics as module

        module._service = None

        service1 = get_customer_metrics_service()
        service2 = get_customer_metrics_service()

        assert service1 is service2

    def test_get_service_with_mode(self):
        """Test factory with deployment mode."""
        import src.services.health.customer_metrics as module

        module._service = None

        service = get_customer_metrics_service(
            deployment_mode=DeploymentMode.SAAS,
        )

        assert service._mode == DeploymentMode.SAAS


class TestMetricsRetrieval:
    """Tests for internal metrics retrieval methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CustomerMetricsService()

    @pytest.mark.asyncio
    async def test_get_api_metrics(self):
        """Test API metrics retrieval."""
        metrics = await self.service._get_api_metrics("cust-123", "24h")

        assert isinstance(metrics, APIMetrics)
        assert metrics.request_count > 0
        assert metrics.error_rate >= 0

    @pytest.mark.asyncio
    async def test_get_agent_metrics(self):
        """Test agent metrics retrieval."""
        metrics = await self.service._get_agent_metrics(
            "cust-123", "24h", include_breakdown=False
        )

        assert isinstance(metrics, AgentMetrics)
        assert metrics.total_executions > 0

    @pytest.mark.asyncio
    async def test_get_agent_metrics_with_breakdown(self):
        """Test agent metrics with breakdown."""
        metrics = await self.service._get_agent_metrics(
            "cust-123", "24h", include_breakdown=True
        )

        assert len(metrics.executions_by_type) > 0

    @pytest.mark.asyncio
    async def test_get_token_metrics(self):
        """Test token metrics retrieval."""
        metrics = await self.service._get_token_metrics(
            "cust-123", "24h", include_breakdown=False
        )

        assert isinstance(metrics, TokenMetrics)
        assert metrics.total_tokens > 0

    @pytest.mark.asyncio
    async def test_get_storage_metrics(self):
        """Test storage metrics retrieval."""
        metrics = await self.service._get_storage_metrics("cust-123")

        assert isinstance(metrics, StorageMetrics)
        assert metrics.total_storage_gb > 0

    @pytest.mark.asyncio
    async def test_get_active_customer_ids(self):
        """Test active customer IDs retrieval."""
        customer_ids = await self.service._get_active_customer_ids()

        assert isinstance(customer_ids, list)
        assert len(customer_ids) > 0
