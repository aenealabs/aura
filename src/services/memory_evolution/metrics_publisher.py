"""
Project Aura - CloudWatch Metrics Publisher for Memory Evolution (ADR-080)

Publishes aggregated memory evolution metrics to CloudWatch for monitoring,
alerting, and dashboard visualization.

Metric Namespace: Aura/MemoryEvolution

Reference: ADR-080 Evo-Memory Enhancements (Phase 2)
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from .config import MemoryEvolutionConfig, get_memory_evolution_config
from .contracts import RefineOperation, RefineResult

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOLS
# =============================================================================


class CloudWatchClientProtocol(Protocol):
    """Protocol for CloudWatch client operations."""

    async def put_metric_data(
        self,
        Namespace: str,
        MetricData: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Put metric data to CloudWatch."""
        ...


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class MetricDataPoint:
    """A single metric data point for CloudWatch."""

    name: str
    value: float
    unit: str  # Count, Percent, Milliseconds, etc.
    dimensions: dict[str, str] = field(default_factory=dict)
    timestamp: Optional[datetime] = None

    def to_cloudwatch_format(self) -> dict[str, Any]:
        """Convert to CloudWatch PutMetricData format."""
        data: dict[str, Any] = {
            "MetricName": self.name,
            "Value": self.value,
            "Unit": self.unit,
        }

        if self.dimensions:
            data["Dimensions"] = [
                {"Name": k, "Value": v} for k, v in self.dimensions.items()
            ]

        if self.timestamp:
            data["Timestamp"] = self.timestamp.isoformat()

        return data


@dataclass
class MetricsBuffer:
    """Buffer for batching metric data points."""

    max_size: int = 20  # CloudWatch limit per PutMetricData call
    data_points: list[MetricDataPoint] = field(default_factory=list)

    def add(self, data_point: MetricDataPoint) -> bool:
        """Add a data point. Returns True if buffer is full."""
        self.data_points.append(data_point)
        return len(self.data_points) >= self.max_size

    def flush(self) -> list[MetricDataPoint]:
        """Flush and return all data points."""
        points = self.data_points
        self.data_points = []
        return points

    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return len(self.data_points) == 0


# =============================================================================
# METRICS PUBLISHER
# =============================================================================


class EvolutionMetricsPublisher:
    """Publishes aggregated metrics to CloudWatch.

    Metrics Published:
    - RefineOperationCount: Count of refine operations by type
    - RefineOperationLatency: Latency of operations in milliseconds
    - RefineOperationSuccess: Success rate of operations
    - EvolutionGain: Performance improvement over time
    - MemoryUtilization: Active memories / total memories
    - StrategyReuseRate: Rate of strategy reuse across tasks
    - ConsolidationEfficiency: Memories consolidated vs total
    - CircuitBreakerState: 0 (closed) or 1 (open)

    Dimensions:
    - Environment: dev, qa, prod
    - AgentId: Agent identifier
    - TenantId: Tenant identifier
    - Operation: CONSOLIDATE, PRUNE, REINFORCE, etc.
    """

    NAMESPACE = "Aura/MemoryEvolution"

    # Metric names
    METRIC_OPERATION_COUNT = "RefineOperationCount"
    METRIC_OPERATION_LATENCY = "RefineOperationLatency"
    METRIC_OPERATION_SUCCESS = "RefineOperationSuccess"
    METRIC_EVOLUTION_GAIN = "EvolutionGain"
    METRIC_MEMORY_UTILIZATION = "MemoryUtilization"
    METRIC_STRATEGY_REUSE = "StrategyReuseRate"
    METRIC_CONSOLIDATION_EFFICIENCY = "ConsolidationEfficiency"
    METRIC_CIRCUIT_BREAKER = "CircuitBreakerState"
    METRIC_QUEUE_DEPTH = "AsyncQueueDepth"
    METRIC_ROUTING_DECISION = "RoutingDecision"

    def __init__(
        self,
        cloudwatch_client: CloudWatchClientProtocol,
        config: Optional[MemoryEvolutionConfig] = None,
        buffer_size: int = 20,
        auto_flush: bool = True,
    ):
        """
        Initialize metrics publisher.

        Args:
            cloudwatch_client: CloudWatch client for publishing
            config: Memory evolution configuration
            buffer_size: Max metrics before auto-flush
            auto_flush: Whether to auto-flush when buffer is full
        """
        self.cloudwatch = cloudwatch_client
        self.config = config or get_memory_evolution_config()
        self.buffer = MetricsBuffer(max_size=buffer_size)
        self.auto_flush = auto_flush
        self._last_flush_time = time.time()

    def _get_base_dimensions(self) -> dict[str, str]:
        """Get base dimensions for all metrics."""
        return {
            "Environment": self.config.environment,
            "ProjectName": self.config.project_name,
        }

    async def publish_refine_result(
        self,
        result: RefineResult,
        agent_id: str,
        tenant_id: str,
    ) -> None:
        """
        Publish metrics for a completed refine operation.

        Args:
            result: Result of the refine operation
            agent_id: Agent that executed the operation
            tenant_id: Tenant identifier
        """
        dimensions = {
            **self._get_base_dimensions(),
            "AgentId": agent_id,
            "TenantId": tenant_id,
            "Operation": result.operation.value,
        }

        # Operation count
        self._add_metric(
            MetricDataPoint(
                name=self.METRIC_OPERATION_COUNT,
                value=1.0,
                unit="Count",
                dimensions=dimensions,
            )
        )

        # Operation latency
        if result.latency_ms > 0:
            self._add_metric(
                MetricDataPoint(
                    name=self.METRIC_OPERATION_LATENCY,
                    value=result.latency_ms,
                    unit="Milliseconds",
                    dimensions=dimensions,
                )
            )

        # Success rate (1.0 for success, 0.0 for failure)
        self._add_metric(
            MetricDataPoint(
                name=self.METRIC_OPERATION_SUCCESS,
                value=1.0 if result.success else 0.0,
                unit="Count",
                dimensions=dimensions,
            )
        )

        # Memory count affected
        if result.affected_memory_ids:
            self._add_metric(
                MetricDataPoint(
                    name="AffectedMemoryCount",
                    value=float(len(result.affected_memory_ids)),
                    unit="Count",
                    dimensions=dimensions,
                )
            )

    async def publish_routing_decision(
        self,
        operation: RefineOperation,
        route: str,  # "sync" or "async"
        confidence: float,
        latency_ms: float,
    ) -> None:
        """
        Publish routing decision metrics.

        Args:
            operation: The refine operation type
            route: Routing decision ("sync" or "async")
            confidence: Confidence score that determined routing
            latency_ms: Routing decision latency
        """
        dimensions = {
            **self._get_base_dimensions(),
            "Operation": operation.value,
            "Route": route,
        }

        # Routing decision count
        self._add_metric(
            MetricDataPoint(
                name=self.METRIC_ROUTING_DECISION,
                value=1.0,
                unit="Count",
                dimensions=dimensions,
            )
        )

        # Confidence level
        self._add_metric(
            MetricDataPoint(
                name="RoutingConfidence",
                value=confidence,
                unit="None",
                dimensions=dimensions,
            )
        )

        if latency_ms > 0:
            self._add_metric(
                MetricDataPoint(
                    name="RoutingLatency",
                    value=latency_ms,
                    unit="Milliseconds",
                    dimensions=dimensions,
                )
            )

    async def publish_evolution_metrics(
        self,
        agent_id: str,
        tenant_id: str,
        evolution_gain: float,
        memory_utilization: float,
        strategy_reuse_rate: float,
        consolidation_efficiency: float = 0.0,
    ) -> None:
        """
        Publish aggregated evolution metrics.

        Args:
            agent_id: Agent identifier
            tenant_id: Tenant identifier
            evolution_gain: Performance improvement (-1.0 to 1.0)
            memory_utilization: Active/total memories (0.0 to 1.0)
            strategy_reuse_rate: Rate of strategy reuse (0.0 to 1.0)
            consolidation_efficiency: Consolidation efficiency (0.0 to 1.0)
        """
        dimensions = {
            **self._get_base_dimensions(),
            "AgentId": agent_id,
            "TenantId": tenant_id,
        }

        self._add_metric(
            MetricDataPoint(
                name=self.METRIC_EVOLUTION_GAIN,
                value=evolution_gain,
                unit="None",
                dimensions=dimensions,
            )
        )

        self._add_metric(
            MetricDataPoint(
                name=self.METRIC_MEMORY_UTILIZATION,
                value=memory_utilization * 100,
                unit="Percent",
                dimensions=dimensions,
            )
        )

        self._add_metric(
            MetricDataPoint(
                name=self.METRIC_STRATEGY_REUSE,
                value=strategy_reuse_rate * 100,
                unit="Percent",
                dimensions=dimensions,
            )
        )

        if consolidation_efficiency > 0:
            self._add_metric(
                MetricDataPoint(
                    name=self.METRIC_CONSOLIDATION_EFFICIENCY,
                    value=consolidation_efficiency * 100,
                    unit="Percent",
                    dimensions=dimensions,
                )
            )

    async def publish_circuit_breaker_state(
        self,
        operation: RefineOperation,
        is_open: bool,
    ) -> None:
        """
        Publish circuit breaker state metric.

        Args:
            operation: Operation the circuit breaker is for
            is_open: True if circuit is open (blocking operations)
        """
        dimensions = {
            **self._get_base_dimensions(),
            "Operation": operation.value,
        }

        self._add_metric(
            MetricDataPoint(
                name=self.METRIC_CIRCUIT_BREAKER,
                value=1.0 if is_open else 0.0,
                unit="Count",
                dimensions=dimensions,
            )
        )

    async def publish_queue_depth(
        self,
        queue_name: str,
        depth: int,
    ) -> None:
        """
        Publish async queue depth metric.

        Args:
            queue_name: Name of the queue
            depth: Number of messages in queue
        """
        dimensions = {
            **self._get_base_dimensions(),
            "QueueName": queue_name,
        }

        self._add_metric(
            MetricDataPoint(
                name=self.METRIC_QUEUE_DEPTH,
                value=float(depth),
                unit="Count",
                dimensions=dimensions,
            )
        )

    def _add_metric(self, data_point: MetricDataPoint) -> None:
        """Add a metric to the buffer, flushing if needed."""
        data_point.timestamp = datetime.now(timezone.utc)

        if self.buffer.add(data_point) and self.auto_flush:
            # Buffer is full, schedule flush
            import asyncio

            asyncio.create_task(self.flush())

    async def flush(self) -> int:
        """
        Flush buffered metrics to CloudWatch.

        Returns:
            Number of metrics flushed
        """
        if self.buffer.is_empty():
            return 0

        data_points = self.buffer.flush()
        metric_data = [dp.to_cloudwatch_format() for dp in data_points]

        try:
            await self.cloudwatch.put_metric_data(
                Namespace=self.NAMESPACE,
                MetricData=metric_data,
            )
            self._last_flush_time = time.time()
            logger.debug(f"Flushed {len(metric_data)} metrics to CloudWatch")
            return len(metric_data)
        except Exception as e:
            logger.error(f"Failed to flush metrics to CloudWatch: {e}")
            # Re-add failed metrics to buffer for retry
            for dp in data_points:
                self.buffer.add(dp)
            raise


# =============================================================================
# SINGLETON MANAGEMENT
# =============================================================================

_publisher_instance: Optional[EvolutionMetricsPublisher] = None


def get_evolution_metrics_publisher(
    cloudwatch_client: Optional[CloudWatchClientProtocol] = None,
    config: Optional[MemoryEvolutionConfig] = None,
) -> EvolutionMetricsPublisher:
    """Get or create the singleton EvolutionMetricsPublisher instance."""
    global _publisher_instance
    if _publisher_instance is None:
        if cloudwatch_client is None:
            raise ValueError("cloudwatch_client is required for initial creation")
        _publisher_instance = EvolutionMetricsPublisher(
            cloudwatch_client=cloudwatch_client,
            config=config,
        )
    return _publisher_instance


def reset_evolution_metrics_publisher() -> None:
    """Reset the singleton instance (for testing)."""
    global _publisher_instance
    _publisher_instance = None
