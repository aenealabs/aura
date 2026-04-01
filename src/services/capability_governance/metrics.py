"""
Project Aura - Capability Governance CloudWatch Metrics

CloudWatch metrics publisher for capability governance monitoring.
Tracks capability checks, decisions, violations, and performance.

Security Rationale:
- Metrics enable anomaly detection
- Dashboards provide security visibility
- Alarms trigger incident response

Author: Project Aura Team
Created: 2026-01-26
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .contracts import CapabilityCheckResult, CapabilityDecision, ToolClassification
from .registry import get_capability_registry

logger = logging.getLogger(__name__)


# =============================================================================
# Metrics Configuration
# =============================================================================


@dataclass
class MetricsConfig:
    """Configuration for CloudWatch metrics."""

    # CloudWatch settings
    namespace: str = "Aura/CapabilityGovernance"
    enabled: bool = True

    # Batch settings
    batch_size: int = 20
    flush_interval_seconds: float = 60.0

    # Metric resolution
    storage_resolution: int = 60  # 1 minute (standard resolution)
    high_resolution: bool = False  # Set to True for 1-second resolution

    # Dimensions
    include_environment: bool = True
    include_region: bool = True
    default_environment: str = "dev"


# =============================================================================
# Metric Names
# =============================================================================


class MetricName:
    """Metric name constants."""

    # Decision metrics
    CAPABILITY_CHECKS = "CapabilityChecks"
    DECISIONS_ALLOW = "DecisionsAllow"
    DECISIONS_DENY = "DecisionsDeny"
    DECISIONS_ESCALATE = "DecisionsEscalate"
    DECISIONS_AUDIT_ONLY = "DecisionsAuditOnly"

    # Violation metrics
    VIOLATIONS = "Violations"
    VIOLATIONS_CRITICAL = "ViolationsCritical"
    VIOLATIONS_HIGH = "ViolationsHigh"
    VIOLATIONS_MEDIUM = "ViolationsMedium"

    # Grant metrics
    GRANTS_CREATED = "GrantsCreated"
    GRANTS_USED = "GrantsUsed"
    GRANTS_REVOKED = "GrantsRevoked"
    GRANTS_EXPIRED = "GrantsExpired"

    # Escalation metrics
    ESCALATIONS_REQUESTED = "EscalationsRequested"
    ESCALATIONS_APPROVED = "EscalationsApproved"
    ESCALATIONS_DENIED = "EscalationsDenied"
    ESCALATIONS_EXPIRED = "EscalationsExpired"

    # Performance metrics
    CHECK_LATENCY_MS = "CheckLatencyMs"
    CACHE_HIT_RATE = "CacheHitRate"
    RATE_LIMIT_REJECTIONS = "RateLimitRejections"

    # Classification metrics
    SAFE_TOOL_INVOCATIONS = "SafeToolInvocations"
    MONITORING_TOOL_INVOCATIONS = "MonitoringToolInvocations"
    DANGEROUS_TOOL_INVOCATIONS = "DangerousToolInvocations"
    CRITICAL_TOOL_INVOCATIONS = "CriticalToolInvocations"


# =============================================================================
# Metrics Publisher
# =============================================================================


class CapabilityMetricsPublisher:
    """
    CloudWatch metrics publisher for capability governance.

    Handles:
    - Decision metrics
    - Violation metrics
    - Grant metrics
    - Performance metrics

    Usage:
        publisher = CapabilityMetricsPublisher()
        await publisher.start()
        publisher.record_check(result)
        publisher.record_violation("critical")
    """

    def __init__(
        self,
        config: Optional[MetricsConfig] = None,
        cloudwatch_client: Optional[Any] = None,
    ):
        """
        Initialize the metrics publisher.

        Args:
            config: Metrics configuration
            cloudwatch_client: Optional boto3 CloudWatch client (for testing)
        """
        self.config = config or MetricsConfig()
        self._cloudwatch = cloudwatch_client
        self._registry = get_capability_registry()

        # Metric buffer
        self._metric_buffer: list[dict[str, Any]] = []
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

        # Internal counters for batch aggregation
        self._counters: dict[str, int] = {}
        self._latencies: list[float] = []
        self._last_flush = time.time()

        # Environment and region
        self._environment = self.config.default_environment
        self._region = "us-east-1"

        logger.debug(
            f"CapabilityMetricsPublisher initialized "
            f"(namespace={self.config.namespace})"
        )

    async def start(self) -> None:
        """Start the metrics publisher."""
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("Capability metrics publisher started")

    async def stop(self) -> None:
        """Stop the metrics publisher and flush pending metrics."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self._flush_metrics()
        logger.info("Capability metrics publisher stopped")

    def _get_cloudwatch_client(self) -> Any:
        """Get or create CloudWatch client."""
        if self._cloudwatch is None:
            try:
                import boto3

                self._cloudwatch = boto3.client("cloudwatch")
            except ImportError:
                logger.warning("boto3 not available, metrics publishing disabled")
                return None
        return self._cloudwatch

    def _get_dimensions(
        self,
        extra_dimensions: Optional[dict[str, str]] = None,
    ) -> list[dict[str, str]]:
        """Build CloudWatch dimensions."""
        dimensions = []

        if self.config.include_environment:
            dimensions.append(
                {
                    "Name": "Environment",
                    "Value": self._environment,
                }
            )

        if self.config.include_region:
            dimensions.append(
                {
                    "Name": "Region",
                    "Value": self._region,
                }
            )

        if extra_dimensions:
            for name, value in extra_dimensions.items():
                dimensions.append(
                    {
                        "Name": name,
                        "Value": value,
                    }
                )

        return dimensions

    def record_check(
        self,
        result: CapabilityCheckResult,
    ) -> None:
        """
        Record a capability check result.

        Args:
            result: The capability check result
        """
        if not self.config.enabled:
            return

        # Increment total checks
        self._increment_counter(MetricName.CAPABILITY_CHECKS)

        # Record decision
        decision_metric = {
            CapabilityDecision.ALLOW: MetricName.DECISIONS_ALLOW,
            CapabilityDecision.DENY: MetricName.DECISIONS_DENY,
            CapabilityDecision.ESCALATE: MetricName.DECISIONS_ESCALATE,
            CapabilityDecision.AUDIT_ONLY: MetricName.DECISIONS_AUDIT_ONLY,
        }.get(result.decision)

        if decision_metric:
            self._increment_counter(decision_metric)

        # Record classification
        classification = self._registry.get_classification(result.tool_name)
        classification_metric = {
            ToolClassification.SAFE: MetricName.SAFE_TOOL_INVOCATIONS,
            ToolClassification.MONITORING: MetricName.MONITORING_TOOL_INVOCATIONS,
            ToolClassification.DANGEROUS: MetricName.DANGEROUS_TOOL_INVOCATIONS,
            ToolClassification.CRITICAL: MetricName.CRITICAL_TOOL_INVOCATIONS,
        }.get(classification)

        if classification_metric:
            self._increment_counter(classification_metric)

        # Record latency
        self._latencies.append(result.processing_time_ms)

    def record_violation(
        self,
        severity: str,
        agent_type: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> None:
        """
        Record a capability violation.

        Args:
            severity: Violation severity (low, medium, high, critical)
            agent_type: Optional agent type
            tool_name: Optional tool name
        """
        if not self.config.enabled:
            return

        self._increment_counter(MetricName.VIOLATIONS)

        severity_metric = {
            "critical": MetricName.VIOLATIONS_CRITICAL,
            "high": MetricName.VIOLATIONS_HIGH,
            "medium": MetricName.VIOLATIONS_MEDIUM,
        }.get(severity.lower())

        if severity_metric:
            self._increment_counter(severity_metric)

    def record_grant_created(self) -> None:
        """Record a grant creation."""
        if self.config.enabled:
            self._increment_counter(MetricName.GRANTS_CREATED)

    def record_grant_used(self) -> None:
        """Record a grant usage."""
        if self.config.enabled:
            self._increment_counter(MetricName.GRANTS_USED)

    def record_grant_revoked(self) -> None:
        """Record a grant revocation."""
        if self.config.enabled:
            self._increment_counter(MetricName.GRANTS_REVOKED)

    def record_grant_expired(self) -> None:
        """Record a grant expiration."""
        if self.config.enabled:
            self._increment_counter(MetricName.GRANTS_EXPIRED)

    def record_escalation_requested(self) -> None:
        """Record an escalation request."""
        if self.config.enabled:
            self._increment_counter(MetricName.ESCALATIONS_REQUESTED)

    def record_escalation_approved(self) -> None:
        """Record an escalation approval."""
        if self.config.enabled:
            self._increment_counter(MetricName.ESCALATIONS_APPROVED)

    def record_escalation_denied(self) -> None:
        """Record an escalation denial."""
        if self.config.enabled:
            self._increment_counter(MetricName.ESCALATIONS_DENIED)

    def record_escalation_expired(self) -> None:
        """Record an escalation expiration."""
        if self.config.enabled:
            self._increment_counter(MetricName.ESCALATIONS_EXPIRED)

    def record_rate_limit_rejection(self) -> None:
        """Record a rate limit rejection."""
        if self.config.enabled:
            self._increment_counter(MetricName.RATE_LIMIT_REJECTIONS)

    def record_cache_hit(self, hit: bool) -> None:
        """Record a cache hit or miss."""
        if self.config.enabled:
            # Track for hit rate calculation
            counter_name = "cache_hits" if hit else "cache_misses"
            self._increment_counter(counter_name)

    def _increment_counter(self, name: str, value: int = 1) -> None:
        """Increment a counter."""
        self._counters[name] = self._counters.get(name, 0) + value

    async def _flush_loop(self) -> None:
        """Background task to flush metrics periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.config.flush_interval_seconds)
                await self._flush_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics flush error: {e}")

    async def _flush_metrics(self) -> None:
        """Flush accumulated metrics to CloudWatch."""
        if not self._counters and not self._latencies:
            return

        client = self._get_cloudwatch_client()
        if not client:
            self._counters.clear()
            self._latencies.clear()
            return

        now = datetime.now(timezone.utc)
        metric_data = []
        dimensions = self._get_dimensions()

        # Add counter metrics
        for name, value in self._counters.items():
            if name in ("cache_hits", "cache_misses"):
                continue  # Handle separately for hit rate

            metric_data.append(
                {
                    "MetricName": name,
                    "Dimensions": dimensions,
                    "Timestamp": now,
                    "Value": value,
                    "Unit": "Count",
                    "StorageResolution": (
                        1
                        if self.config.high_resolution
                        else self.config.storage_resolution
                    ),
                }
            )

        # Calculate and add cache hit rate
        cache_hits = self._counters.get("cache_hits", 0)
        cache_misses = self._counters.get("cache_misses", 0)
        total_cache = cache_hits + cache_misses
        if total_cache > 0:
            hit_rate = (cache_hits / total_cache) * 100
            metric_data.append(
                {
                    "MetricName": MetricName.CACHE_HIT_RATE,
                    "Dimensions": dimensions,
                    "Timestamp": now,
                    "Value": hit_rate,
                    "Unit": "Percent",
                    "StorageResolution": (
                        1
                        if self.config.high_resolution
                        else self.config.storage_resolution
                    ),
                }
            )

        # Add latency statistics
        if self._latencies:
            sorted_latencies = sorted(self._latencies)
            p50_idx = int(len(sorted_latencies) * 0.50)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p99_idx = int(len(sorted_latencies) * 0.99)

            latency_stats = {
                "Min": min(sorted_latencies),
                "Max": max(sorted_latencies),
                "Sum": sum(sorted_latencies),
                "SampleCount": len(sorted_latencies),
            }

            metric_data.append(
                {
                    "MetricName": MetricName.CHECK_LATENCY_MS,
                    "Dimensions": dimensions,
                    "Timestamp": now,
                    "StatisticValues": latency_stats,
                    "Unit": "Milliseconds",
                    "StorageResolution": (
                        1
                        if self.config.high_resolution
                        else self.config.storage_resolution
                    ),
                }
            )

            # Add percentile metrics
            metric_data.append(
                {
                    "MetricName": f"{MetricName.CHECK_LATENCY_MS}P50",
                    "Dimensions": dimensions,
                    "Timestamp": now,
                    "Value": sorted_latencies[p50_idx] if sorted_latencies else 0,
                    "Unit": "Milliseconds",
                }
            )
            metric_data.append(
                {
                    "MetricName": f"{MetricName.CHECK_LATENCY_MS}P95",
                    "Dimensions": dimensions,
                    "Timestamp": now,
                    "Value": (
                        sorted_latencies[p95_idx]
                        if len(sorted_latencies) > p95_idx
                        else 0
                    ),
                    "Unit": "Milliseconds",
                }
            )
            metric_data.append(
                {
                    "MetricName": f"{MetricName.CHECK_LATENCY_MS}P99",
                    "Dimensions": dimensions,
                    "Timestamp": now,
                    "Value": (
                        sorted_latencies[p99_idx]
                        if len(sorted_latencies) > p99_idx
                        else 0
                    ),
                    "Unit": "Milliseconds",
                }
            )

        # Send metrics in batches
        try:
            for i in range(0, len(metric_data), self.config.batch_size):
                batch = metric_data[i : i + self.config.batch_size]
                client.put_metric_data(
                    Namespace=self.config.namespace,
                    MetricData=batch,
                )

            logger.debug(
                f"Flushed {len(metric_data)} metrics to CloudWatch "
                f"(counters={len(self._counters)}, latencies={len(self._latencies)})"
            )
        except Exception as e:
            logger.error(f"Failed to publish metrics: {e}")

        # Clear buffers
        self._counters.clear()
        self._latencies.clear()
        self._last_flush = time.time()

    def set_environment(self, environment: str) -> None:
        """Set the environment dimension."""
        self._environment = environment

    def set_region(self, region: str) -> None:
        """Set the region dimension."""
        self._region = region

    def get_pending_metrics_count(self) -> int:
        """Get count of pending metrics."""
        return len(self._counters) + len(self._latencies)


# =============================================================================
# Global Publisher Singleton
# =============================================================================

_metrics_publisher: Optional[CapabilityMetricsPublisher] = None


def get_metrics_publisher() -> CapabilityMetricsPublisher:
    """Get the global metrics publisher instance."""
    global _metrics_publisher
    if _metrics_publisher is None:
        _metrics_publisher = CapabilityMetricsPublisher()
    return _metrics_publisher


def reset_metrics_publisher() -> None:
    """Reset the global metrics publisher (for testing)."""
    global _metrics_publisher
    _metrics_publisher = None
