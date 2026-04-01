"""
Customer Health Metrics Service.

Aggregates per-customer metrics for the Customer Health Dashboard.
Supports both SaaS (multi-tenant) and self-hosted (single-tenant) modes.

Metrics tracked:
- API request count, latency, error rate
- Agent execution count, success rate
- Token usage (LLM costs)
- Storage usage (S3, Neptune, OpenSearch)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DeploymentMode(Enum):
    """Deployment mode for metrics collection."""

    SAAS = "saas"  # Multi-tenant, metrics per CustomerId
    SELF_HOSTED = "self_hosted"  # Single-tenant, no CustomerId dimension


class MetricTimeRange(Enum):
    """Time range for metric queries."""

    HOUR = "1h"
    DAY = "24h"
    WEEK = "7d"
    MONTH = "30d"


@dataclass
class APIMetrics:
    """API usage metrics."""

    request_count: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0


@dataclass
class AgentMetrics:
    """Agent execution metrics."""

    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    success_rate: float = 0.0
    avg_execution_time_seconds: float = 0.0
    executions_by_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class TokenMetrics:
    """LLM token usage metrics."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    tokens_by_model: Dict[str, int] = field(default_factory=dict)


@dataclass
class StorageMetrics:
    """Storage usage metrics."""

    s3_storage_bytes: int = 0
    s3_storage_gb: float = 0.0
    neptune_storage_bytes: int = 0
    neptune_storage_gb: float = 0.0
    opensearch_storage_bytes: int = 0
    opensearch_storage_gb: float = 0.0
    total_storage_gb: float = 0.0


@dataclass
class HealthStatus:
    """Overall health status."""

    status: str = "healthy"  # healthy, degraded, unhealthy
    score: int = 100  # 0-100
    issues: List[str] = field(default_factory=list)
    last_checked: Optional[datetime] = None


@dataclass
class CustomerHealth:
    """Complete customer health metrics."""

    customer_id: str
    customer_name: Optional[str] = None
    time_range: str = "24h"
    api: APIMetrics = field(default_factory=APIMetrics)
    agents: AgentMetrics = field(default_factory=AgentMetrics)
    tokens: TokenMetrics = field(default_factory=TokenMetrics)
    storage: StorageMetrics = field(default_factory=StorageMetrics)
    health: HealthStatus = field(default_factory=HealthStatus)
    collected_at: Optional[datetime] = None


class CustomerMetricsService:
    """
    Service for collecting and aggregating customer health metrics.

    Retrieves metrics from CloudWatch and internal sources, aggregating
    them by customer for the health dashboard.

    Usage:
        service = CustomerMetricsService()
        health = await service.get_customer_health("cust-123", time_range="24h")
        print(f"API error rate: {health.api.error_rate}%")
    """

    # Cost per 1M tokens by model (estimates)
    TOKEN_COSTS = {
        "anthropic.claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
        "anthropic.claude-3-haiku": {"input": 0.25, "output": 1.25},
        "amazon.titan-embed-text-v2": {"input": 0.02, "output": 0.0},
    }

    def __init__(
        self,
        deployment_mode: DeploymentMode = DeploymentMode.SELF_HOSTED,
        cloudwatch_client: Optional[Any] = None,
    ):
        """
        Initialize the customer metrics service.

        Args:
            deployment_mode: SaaS or self-hosted deployment
            cloudwatch_client: Optional boto3 CloudWatch client
        """
        self._mode = deployment_mode
        self._cloudwatch = cloudwatch_client
        self._cache: Dict[str, CustomerHealth] = {}
        self._cache_ttl_seconds = 60
        logger.info(
            f"CustomerMetricsService initialized in {deployment_mode.value} mode"
        )

    async def get_customer_health(
        self,
        customer_id: str,
        time_range: str = "24h",
        include_breakdown: bool = False,
    ) -> CustomerHealth:
        """
        Get comprehensive health metrics for a customer.

        Args:
            customer_id: Customer identifier
            time_range: Time range for metrics (1h, 24h, 7d, 30d)
            include_breakdown: Include detailed breakdowns by agent/model

        Returns:
            CustomerHealth with all metrics aggregated
        """
        cache_key = f"{customer_id}:{time_range}"

        # Check cache
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.collected_at:
                age = (datetime.now(timezone.utc) - cached.collected_at).total_seconds()
                if age < self._cache_ttl_seconds:
                    return cached

        # Collect metrics in parallel
        api_metrics = await self._get_api_metrics(customer_id, time_range)
        agent_metrics = await self._get_agent_metrics(
            customer_id, time_range, include_breakdown
        )
        token_metrics = await self._get_token_metrics(
            customer_id, time_range, include_breakdown
        )
        storage_metrics = await self._get_storage_metrics(customer_id)
        health_status = self._calculate_health_status(
            api_metrics, agent_metrics, token_metrics, storage_metrics
        )

        health = CustomerHealth(
            customer_id=customer_id,
            time_range=time_range,
            api=api_metrics,
            agents=agent_metrics,
            tokens=token_metrics,
            storage=storage_metrics,
            health=health_status,
            collected_at=datetime.now(timezone.utc),
        )

        self._cache[cache_key] = health
        return health

    async def get_all_customers_health(
        self,
        time_range: str = "24h",
    ) -> List[CustomerHealth]:
        """
        Get health metrics for all customers (SaaS mode only).

        Returns:
            List of CustomerHealth for all active customers
        """
        if self._mode != DeploymentMode.SAAS:
            # Self-hosted returns single customer
            return [await self.get_customer_health("default", time_range)]

        # In SaaS mode, get list of active customers from DynamoDB
        customer_ids = await self._get_active_customer_ids()
        results = []
        for customer_id in customer_ids:
            health = await self.get_customer_health(customer_id, time_range)
            results.append(health)

        return results

    async def _get_api_metrics(
        self,
        customer_id: str,
        time_range: str,
    ) -> APIMetrics:
        """Retrieve API metrics from CloudWatch."""
        # In production, query CloudWatch with:
        # - Namespace: Aura/API
        # - Dimensions: CustomerId={customer_id}
        # - Metrics: RequestCount, ErrorCount, Latency

        # For now, return sample data
        return APIMetrics(
            request_count=15234,
            error_count=42,
            error_rate=0.28,
            avg_latency_ms=127.5,
            p50_latency_ms=89.0,
            p95_latency_ms=342.0,
            p99_latency_ms=891.0,
        )

    async def _get_agent_metrics(
        self,
        customer_id: str,
        time_range: str,
        include_breakdown: bool,
    ) -> AgentMetrics:
        """Retrieve agent execution metrics."""
        # In production, query CloudWatch with:
        # - Namespace: Aura/Agents
        # - Dimensions: CustomerId, AgentType

        metrics = AgentMetrics(
            total_executions=1247,
            successful_executions=1198,
            failed_executions=49,
            success_rate=96.07,
            avg_execution_time_seconds=45.3,
        )

        if include_breakdown:
            metrics.executions_by_type = {
                "scanner": 523,
                "coder": 412,
                "reviewer": 189,
                "validator": 123,
            }

        return metrics

    async def _get_token_metrics(
        self,
        customer_id: str,
        time_range: str,
        include_breakdown: bool,
    ) -> TokenMetrics:
        """Retrieve LLM token usage metrics."""
        # In production, query CloudWatch with:
        # - Namespace: Aura/LLM
        # - Dimensions: CustomerId, Model

        total_input = 2_450_000
        total_output = 890_000

        metrics = TokenMetrics(
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
            estimated_cost_usd=self._calculate_token_cost(
                "anthropic.claude-3-5-sonnet", total_input, total_output
            ),
        )

        if include_breakdown:
            metrics.tokens_by_model = {
                "anthropic.claude-3-5-sonnet": 2_800_000,
                "anthropic.claude-3-haiku": 340_000,
                "amazon.titan-embed-text-v2": 200_000,
            }

        return metrics

    async def _get_storage_metrics(self, customer_id: str) -> StorageMetrics:
        """Retrieve storage usage metrics."""
        # In production, query:
        # - S3: GetBucketMetrics or CloudWatch BucketSizeBytes
        # - Neptune: CloudWatch VolumeBytesUsed
        # - OpenSearch: Cluster stats API

        s3_bytes = 2_147_483_648  # 2 GB
        neptune_bytes = 536_870_912  # 512 MB
        opensearch_bytes = 1_073_741_824  # 1 GB

        return StorageMetrics(
            s3_storage_bytes=s3_bytes,
            s3_storage_gb=s3_bytes / (1024**3),
            neptune_storage_bytes=neptune_bytes,
            neptune_storage_gb=neptune_bytes / (1024**3),
            opensearch_storage_bytes=opensearch_bytes,
            opensearch_storage_gb=opensearch_bytes / (1024**3),
            total_storage_gb=(s3_bytes + neptune_bytes + opensearch_bytes) / (1024**3),
        )

    def _calculate_health_status(
        self,
        api: APIMetrics,
        agents: AgentMetrics,
        tokens: TokenMetrics,
        storage: StorageMetrics,
    ) -> HealthStatus:
        """Calculate overall health status based on metrics."""
        issues = []
        score = 100

        # Check API error rate
        if api.error_rate > 5.0:
            issues.append("High API error rate (>5%)")
            score -= 20
        elif api.error_rate > 1.0:
            issues.append("Elevated API error rate (>1%)")
            score -= 10

        # Check API latency
        if api.p95_latency_ms > 1000:
            issues.append("High P95 latency (>1s)")
            score -= 15
        elif api.p95_latency_ms > 500:
            issues.append("Elevated P95 latency (>500ms)")
            score -= 5

        # Check agent success rate
        if agents.success_rate < 90:
            issues.append("Low agent success rate (<90%)")
            score -= 20
        elif agents.success_rate < 95:
            issues.append("Reduced agent success rate (<95%)")
            score -= 10

        # Determine status
        if score >= 90:
            status = "healthy"
        elif score >= 70:
            status = "degraded"
        else:
            status = "unhealthy"

        return HealthStatus(
            status=status,
            score=max(0, score),
            issues=issues,
            last_checked=datetime.now(timezone.utc),
        )

    def _calculate_token_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate estimated cost for token usage."""
        costs = self.TOKEN_COSTS.get(model, {"input": 3.0, "output": 15.0})
        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]
        return round(input_cost + output_cost, 2)

    async def _get_active_customer_ids(self) -> List[str]:
        """Get list of active customer IDs from DynamoDB."""
        # In production, query aura-customers table
        # For now, return sample data
        return ["cust-001", "cust-002", "cust-003"]

    def clear_cache(self, customer_id: Optional[str] = None) -> None:
        """Clear metrics cache."""
        if customer_id:
            keys_to_remove = [
                k for k in self._cache.keys() if k.startswith(f"{customer_id}:")
            ]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()
        logger.info(f"Cleared metrics cache for: {customer_id or 'all'}")


# Module-level service instance
_service: Optional[CustomerMetricsService] = None


def get_customer_metrics_service(
    deployment_mode: DeploymentMode = DeploymentMode.SELF_HOSTED,
) -> CustomerMetricsService:
    """Get singleton metrics service instance."""
    global _service
    if _service is None:
        _service = CustomerMetricsService(deployment_mode=deployment_mode)
    return _service
