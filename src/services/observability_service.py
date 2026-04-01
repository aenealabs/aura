"""
Project Aura - Production Observability Service

Modeled after: Google SRE (Site Reliability Engineering) best practices
References:
- Google SRE Book: The Four Golden Signals
- Netflix: Observability-Driven Development
- Datadog: Modern Monitoring Best Practices

The Four Golden Signals (Google SRE):
1. Latency: How long requests take
2. Traffic: How many requests
3. Errors: Rate of failed requests
4. Saturation: Resource utilization

Author: Project Aura Team
Created: 2025-11-18
Version: 1.0.0
"""

import logging
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ServiceHealth(Enum):
    """Service health status (AWS style)."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Alert severity levels (PagerDuty style)."""

    CRITICAL = "critical"  # Wakes people up at 3am
    HIGH = "high"  # Needs attention within 1 hour
    MEDIUM = "medium"  # Needs attention within 1 day
    LOW = "low"  # Informational only
    INFO = "info"  # Just logging


@dataclass
class Metric:
    """Individual metric measurement."""

    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """Alert for abnormal behavior."""

    severity: AlertSeverity
    service: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class ObservabilityService:
    """
    Production monitoring and observability service.

    Implements Google SRE's Four Golden Signals:
    - Latency tracking
    - Traffic (request rate) tracking
    - Error rate tracking
    - Saturation (resource usage) tracking

    Usage:
        monitor = ObservabilityService()

        # Track latency
        with monitor.track_latency("orchestrator.execute"):
            result = orchestrator.execute(task)

        # Record error
        monitor.record_error("neptune_query", error=e)

        # Check health
        health = monitor.get_service_health()
    """

    def __init__(self) -> None:
        """Initialize observability service."""
        # Golden Signal 1: Latency
        self.latencies: dict[str, list[float]] = defaultdict(list)

        # Golden Signal 2: Traffic
        self.request_counts: dict[str, int] = defaultdict(int)

        # Golden Signal 3: Errors
        self.error_counts: dict[str, int] = defaultdict(int)
        self.success_counts: dict[str, int] = defaultdict(int)

        # Golden Signal 4: Saturation
        self.resource_usage: dict[str, float] = {}

        # Alerting
        self.alerts: list[Alert] = []
        self.alert_thresholds = {
            "error_rate": 0.05,  # 5% error rate triggers alert
            "p95_latency": 5.0,  # 5 second p95 latency triggers alert
            "saturation": 0.80,  # 80% resource usage triggers alert
        }

        # Service health
        self.service_start_time = datetime.now(timezone.utc)
        self.last_health_check = datetime.now(timezone.utc)

    # ========================================================================
    # Golden Signal 1: Latency Tracking
    # ========================================================================

    @contextmanager
    def track_latency(self, operation: str) -> Iterator[None]:
        """
        Track operation latency (context manager).

        Usage:
            with monitor.track_latency("neptune.query"):
                results = neptune.search(query)
        """
        start_time = time.time()
        error_occurred = False

        try:
            yield
        except Exception as e:
            error_occurred = True
            self.record_error(operation, error=e)
            raise
        finally:
            elapsed = time.time() - start_time
            self.record_latency(operation, elapsed)

            if not error_occurred:
                self.record_success(operation)

            # Check SLA violations
            self._check_latency_sla(operation, elapsed)

    def record_latency(self, operation: str, duration_seconds: float) -> None:
        """Record operation latency."""
        self.latencies[operation].append(duration_seconds)

        # Keep only last 1000 measurements (memory management)
        if len(self.latencies[operation]) > 1000:
            self.latencies[operation] = self.latencies[operation][-1000:]

        # Log slow operations
        if duration_seconds > 5.0:
            logger.warning(f"SLOW OPERATION: {operation} took {duration_seconds:.2f}s")

    def get_percentile_latency(self, operation: str, percentile: float) -> float | None:
        """
        Get Nth percentile latency for operation.

        Args:
            operation: Operation name
            percentile: Percentile value (0.0 to 1.0), e.g., 0.95 for p95

        Returns:
            Latency at the given percentile, or None if no data
        """
        if operation not in self.latencies or not self.latencies[operation]:
            return None

        sorted_latencies = sorted(self.latencies[operation])
        index = min(int(len(sorted_latencies) * percentile), len(sorted_latencies) - 1)
        return sorted_latencies[index]

    def get_p95_latency(self, operation: str) -> float | None:
        """Get 95th percentile latency for operation."""
        return self.get_percentile_latency(operation, 0.95)

    def get_p99_latency(self, operation: str) -> float | None:
        """Get 99th percentile latency for operation."""
        return self.get_percentile_latency(operation, 0.99)

    def get_average_latency(self, operation: str) -> float | None:
        """Get average latency for operation."""
        if operation not in self.latencies or not self.latencies[operation]:
            return None

        return sum(self.latencies[operation]) / len(self.latencies[operation])

    # ========================================================================
    # Golden Signal 2: Traffic Tracking
    # ========================================================================

    def record_request(self, endpoint: str) -> None:
        """Record request to endpoint."""
        self.request_counts[endpoint] += 1

    def get_request_rate(self, endpoint: str, window_minutes: int = 5) -> float:
        """
        Get requests per second for endpoint.

        Note: This is simplified. In production, use time-series database.
        """
        total_requests = self.request_counts.get(endpoint, 0)
        uptime_seconds = (
            datetime.now(timezone.utc) - self.service_start_time
        ).total_seconds()

        if uptime_seconds == 0:
            return 0.0

        return total_requests / uptime_seconds

    # ========================================================================
    # Golden Signal 3: Error Tracking
    # ========================================================================

    def record_error(self, operation: str, error: Exception | None = None) -> None:
        """Record error for operation."""
        self.error_counts[operation] += 1

        # Log error
        if error:
            logger.error(f"ERROR in {operation}: {type(error).__name__}: {str(error)}")

        # Check error rate threshold
        self._check_error_rate(operation)

    def record_success(self, operation: str) -> None:
        """Record successful operation."""
        self.success_counts[operation] += 1

    def get_error_rate(self, operation: str) -> float:
        """Get error rate for operation (0.0 to 1.0)."""
        total_errors = self.error_counts.get(operation, 0)
        total_success = self.success_counts.get(operation, 0)
        total_requests = total_errors + total_success

        if total_requests == 0:
            return 0.0

        return total_errors / total_requests

    def get_success_rate(self, operation: str) -> float:
        """Get success rate for operation (0.0 to 1.0)."""
        return 1.0 - self.get_error_rate(operation)

    # ========================================================================
    # Golden Signal 4: Saturation Tracking
    # ========================================================================

    def record_resource_usage(self, resource: str, usage_percent: float) -> None:
        """
        Record resource usage.

        Args:
            resource: Resource name (e.g., "cpu", "memory", "neptune_connections")
            usage_percent: Usage as percentage (0.0 to 100.0)
        """
        self.resource_usage[resource] = usage_percent

        # Check saturation threshold
        if usage_percent > self.alert_thresholds["saturation"] * 100:
            self.create_alert(
                severity=AlertSeverity.HIGH,
                service=resource,
                message=f"{resource} usage at {usage_percent:.1f}% (> {self.alert_thresholds['saturation']*100}% threshold)",
                metadata={"usage_percent": usage_percent},
            )

    def record_event_loop_lag(self, lag_ms: float) -> None:
        """
        Record event loop lag (time tasks wait before execution).

        This metric helps detect when the event loop is blocked by
        synchronous operations, causing request latency to increase.

        Args:
            lag_ms: Event loop lag in milliseconds
        """
        self.record_latency("eventloop.lag", lag_ms / 1000)
        self.resource_usage["eventloop_lag_ms"] = lag_ms

        # Alert if lag exceeds 100ms (indicates blocking operations)
        if lag_ms > 100:
            logger.warning(
                f"EVENT LOOP LAG: {lag_ms:.1f}ms - check for blocking operations"
            )
            self.create_alert(
                severity=AlertSeverity.MEDIUM,
                service="eventloop",
                message=f"Event loop lag {lag_ms:.1f}ms exceeds 100ms threshold",
                metadata={"lag_ms": lag_ms},
            )

    def record_queue_depth(
        self, queue_name: str, current_depth: int, max_depth: int = 100
    ) -> None:
        """
        Record queue depth for backpressure monitoring.

        Args:
            queue_name: Name of the queue (e.g., "ingest", "webhook")
            current_depth: Current number of items in queue
            max_depth: Maximum expected queue depth for saturation calculation
        """
        usage_percent = (current_depth / max_depth) * 100 if max_depth > 0 else 0
        self.resource_usage[f"queue.{queue_name}.depth"] = current_depth
        self.resource_usage[f"queue.{queue_name}.saturation"] = usage_percent

        # Log high queue depths
        if usage_percent > 80:
            logger.warning(
                f"HIGH QUEUE DEPTH: {queue_name} at {current_depth}/{max_depth} ({usage_percent:.1f}%)"
            )
            self.create_alert(
                severity=AlertSeverity.MEDIUM,
                service=f"queue.{queue_name}",
                message=f"Queue depth {current_depth}/{max_depth} ({usage_percent:.1f}% saturation)",
                metadata={"current_depth": current_depth, "max_depth": max_depth},
            )

    def get_queue_stats(self) -> dict[str, dict[str, float]]:
        """Get statistics for all monitored queues."""
        stats: dict[str, dict[str, float]] = {}
        for key, value in self.resource_usage.items():
            if key.startswith("queue.") and key.endswith(".depth"):
                queue_name = key.replace("queue.", "").replace(".depth", "")
                saturation_key = f"queue.{queue_name}.saturation"
                stats[queue_name] = {
                    "depth": value,
                    "saturation": self.resource_usage.get(saturation_key, 0.0),
                }
        return stats

    # ========================================================================
    # Database Query Tracking (Issue #43 - Performance Optimization)
    # ========================================================================

    def track_database_query(
        self,
        database: str,
        operation: str,
        latency_ms: float,
        result_count: int = 0,
        cache_hit: bool = False,
    ) -> None:
        """
        Track database query performance metrics.

        Args:
            database: Database type ("neptune", "opensearch", "dynamodb")
            operation: Query type ("query", "scan", "search", "bulk_index")
            latency_ms: Query latency in milliseconds
            result_count: Number of results returned
            cache_hit: Whether result was served from cache
        """
        key = f"db.{database}.{operation}"

        # Record latency (convert ms to seconds for consistency)
        self.record_latency(key, latency_ms / 1000)

        # Track request count
        self.request_counts[key] += 1

        # Track cache efficiency
        if cache_hit:
            self.request_counts[f"{key}.cache_hit"] += 1
        else:
            self.request_counts[f"{key}.cache_miss"] += 1

        # Log slow queries
        if latency_ms > 1000:
            logger.warning(
                f"SLOW DB QUERY: {database}.{operation} took {latency_ms:.0f}ms "
                f"(results: {result_count}, cached: {cache_hit})"
            )

    def get_database_stats(self, database: str | None = None) -> dict[str, Any]:
        """
        Get database query statistics.

        Args:
            database: Optional filter for specific database

        Returns:
            Dict with query counts, latencies, and cache hit rates
        """
        stats: dict[str, Any] = {"databases": {}}

        for key in self.request_counts:
            if not key.startswith("db."):
                continue

            parts = key.split(".")
            if len(parts) < 3:
                continue

            db_name = parts[1]
            if database and db_name != database:
                continue

            if db_name not in stats["databases"]:
                stats["databases"][db_name] = {
                    "operations": {},
                    "total_queries": 0,
                    "cache_hits": 0,
                    "cache_misses": 0,
                }

            op_name = parts[2]
            if op_name == "cache_hit":
                stats["databases"][db_name]["cache_hits"] = self.request_counts[key]
            elif op_name == "cache_miss":
                stats["databases"][db_name]["cache_misses"] = self.request_counts[key]
            else:
                # Regular operation
                op_key = f"db.{db_name}.{op_name}"
                stats["databases"][db_name]["operations"][op_name] = {
                    "count": self.request_counts[key],
                    "avg_latency_ms": (self.get_average_latency(op_key) or 0) * 1000,
                    "p95_latency_ms": (self.get_p95_latency(op_key) or 0) * 1000,
                }
                stats["databases"][db_name]["total_queries"] += self.request_counts[key]

        # Calculate cache hit rates
        for _db_name, db_stats in stats["databases"].items():
            total_cache_ops = db_stats["cache_hits"] + db_stats["cache_misses"]
            if total_cache_ops > 0:
                db_stats["cache_hit_rate"] = db_stats["cache_hits"] / total_cache_ops
            else:
                db_stats["cache_hit_rate"] = 0.0

        return stats

    # ========================================================================
    # Health Checks (AWS Health Check API style)
    # ========================================================================

    def get_service_health(self) -> ServiceHealth:
        """
        Get overall service health status.

        Health determination (Google SRE style):
        - HEALTHY: Error rate < 1%, P95 latency < 2s
        - DEGRADED: Error rate < 5%, P95 latency < 5s
        - UNHEALTHY: Error rate >= 5% or P95 latency >= 5s
        """
        # Check error rates across all operations
        max_error_rate = 0.0
        for operation in self.error_counts.keys():
            error_rate = self.get_error_rate(operation)
            max_error_rate = max(max_error_rate, error_rate)

        # Check latencies across all operations
        max_p95_latency = 0.0
        for operation in self.latencies.keys():
            p95 = self.get_p95_latency(operation)
            if p95:
                max_p95_latency = max(max_p95_latency, p95)

        # Determine health status
        if max_error_rate >= 0.05 or max_p95_latency >= 5.0:
            return ServiceHealth.UNHEALTHY
        elif max_error_rate >= 0.01 or max_p95_latency >= 2.0:
            return ServiceHealth.DEGRADED
        else:
            return ServiceHealth.HEALTHY

    def get_health_report(self) -> dict[str, Any]:
        """
        Get detailed health report (Datadog/New Relic style).

        Returns comprehensive metrics for dashboard display.
        """
        health = self.get_service_health()
        uptime = datetime.now(timezone.utc) - self.service_start_time

        # Build typed sub-dicts to avoid mypy inference issues
        latency_metrics: dict[str, dict[str, float | int]] = {}
        traffic_metrics: dict[str, dict[str, float | int]] = {}
        error_metrics: dict[str, dict[str, float | int]] = {}

        # Add latency metrics
        for operation, latencies in self.latencies.items():
            if latencies:
                avg_latency = self.get_average_latency(operation)
                latency_metrics[operation] = {
                    "average_ms": (avg_latency * 1000) if avg_latency else 0.0,
                    "p95_ms": (self.get_p95_latency(operation) or 0) * 1000,
                    "p99_ms": (self.get_p99_latency(operation) or 0) * 1000,
                    "sample_count": len(latencies),
                }

        # Add traffic metrics
        for endpoint, count in self.request_counts.items():
            traffic_metrics[endpoint] = {
                "total_requests": count,
                "requests_per_second": self.get_request_rate(endpoint),
            }

        # Add error metrics
        for operation in set(
            list(self.error_counts.keys()) + list(self.success_counts.keys())
        ):
            error_metrics[operation] = {
                "error_rate": self.get_error_rate(operation),
                "success_rate": self.get_success_rate(operation),
                "total_errors": self.error_counts.get(operation, 0),
                "total_success": self.success_counts.get(operation, 0),
            }

        return {
            "status": health.value,
            "uptime_seconds": uptime.total_seconds(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "golden_signals": {
                "latency": latency_metrics,
                "traffic": traffic_metrics,
                "errors": error_metrics,
                "saturation": self.resource_usage.copy(),
            },
            "alerts": [
                {
                    "severity": alert.severity.value,
                    "service": alert.service,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                }
                for alert in self.alerts[-10:]  # Last 10 alerts
            ],
        }

    # ========================================================================
    # Alerting (PagerDuty style)
    # ========================================================================

    def create_alert(
        self,
        severity: AlertSeverity,
        service: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Create alert for abnormal behavior.

        In production, this would send to:
        - PagerDuty (critical alerts)
        - Slack (high/medium alerts)
        - Email (low alerts)
        """
        alert = Alert(
            severity=severity, service=service, message=message, metadata=metadata or {}
        )

        self.alerts.append(alert)

        # Log alert
        log_level = {
            AlertSeverity.CRITICAL: logging.CRITICAL,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.INFO: logging.DEBUG,
        }.get(severity, logging.INFO)

        logger.log(log_level, f"[{severity.value.upper()}] {service}: {message}")

        # In production, send to external alerting service
        # self._send_to_pagerduty(alert)
        # self._send_to_slack(alert)

    # ========================================================================
    # Internal Helper Methods
    # ========================================================================

    def _check_latency_sla(self, operation: str, duration: float) -> None:
        """Check if latency violates SLA."""
        p95_threshold = self.alert_thresholds["p95_latency"]

        if duration > p95_threshold:
            self.create_alert(
                severity=AlertSeverity.MEDIUM,
                service=operation,
                message=f"Operation exceeded latency SLA: {duration:.2f}s (> {p95_threshold}s)",
                metadata={"duration_seconds": duration},
            )

    def _check_error_rate(self, operation: str) -> None:
        """Check if error rate exceeds threshold."""
        error_rate = self.get_error_rate(operation)
        threshold = self.alert_thresholds["error_rate"]

        if error_rate > threshold:
            self.create_alert(
                severity=AlertSeverity.HIGH,
                service=operation,
                message=f"Error rate {error_rate*100:.1f}% exceeds threshold {threshold*100:.1f}%",
                metadata={"error_rate": error_rate},
            )


# ============================================================================
# Global Singleton Instance (for easy access across services)
# ============================================================================

_global_monitor: ObservabilityService | None = None


def get_monitor() -> ObservabilityService:
    """Get global observability service instance (singleton)."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ObservabilityService()
    return _global_monitor


# ============================================================================
# Convenience Decorators (Netflix style)
# ============================================================================


def monitored(
    operation_name: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to automatically monitor function execution.

    Usage:
        @monitored("orchestrator.execute")
        def execute_task(task):
            # Function automatically tracked
            return process(task)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            monitor = get_monitor()

            with monitor.track_latency(op_name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================================
# Async Event Loop Lag Measurement
# ============================================================================


async def measure_event_loop_lag() -> float:
    """
    Measure current event loop lag by scheduling a callback and timing it.

    Returns:
        Event loop lag in milliseconds

    Usage:
        lag_ms = await measure_event_loop_lag()
        get_monitor().record_event_loop_lag(lag_ms)
    """
    import asyncio

    loop = asyncio.get_event_loop()
    start = time.time()

    # Schedule a callback to run immediately - any delay is event loop lag
    future: asyncio.Future[None] = loop.create_future()

    def set_result() -> None:
        if not future.done():
            future.set_result(None)

    loop.call_soon(set_result)
    await future

    lag_ms = (time.time() - start) * 1000
    return lag_ms


async def start_event_loop_monitor(interval_seconds: float = 5.0) -> None:
    """
    Start a background task that periodically measures event loop lag.

    This should be started once when the application starts.

    Args:
        interval_seconds: How often to measure lag (default 5 seconds)

    Usage:
        asyncio.create_task(start_event_loop_monitor())
    """
    import asyncio

    monitor = get_monitor()
    logger.info(f"Starting event loop lag monitor (interval: {interval_seconds}s)")

    while True:
        try:
            lag_ms = await measure_event_loop_lag()
            monitor.record_event_loop_lag(lag_ms)
        except Exception as e:
            logger.warning(f"Failed to measure event loop lag: {e}")

        await asyncio.sleep(interval_seconds)
