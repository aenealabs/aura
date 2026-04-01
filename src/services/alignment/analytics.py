"""
Alignment Analytics Service (ADR-052 Phase 3).

Provides historical trend analysis for alignment metrics, enabling
visualization and alerting on alignment health over time.

Key Capabilities:
- Time-series aggregation of alignment metrics
- Trend detection and anomaly identification
- Alert threshold monitoring
- Cross-agent comparison analytics
- Exportable reports for compliance

Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
"""

from __future__ import annotations

import logging
import statistics
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TimeGranularity(Enum):
    """Time granularity for analytics aggregation."""

    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class TrendDirection(Enum):
    """Direction of a trend."""

    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Severity levels for alignment alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Status of an alignment alert."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class MetricDataPoint:
    """A single metric observation."""

    timestamp: datetime
    metric_name: str
    value: float
    agent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrendAnalysis:
    """Result of trend analysis on a metric."""

    metric_name: str
    direction: TrendDirection
    slope: float  # Change per time unit
    confidence: float  # 0.0 to 1.0
    current_value: float
    previous_value: float
    change_percent: float
    period_start: datetime
    period_end: datetime
    data_points: int
    is_anomaly: bool = False
    anomaly_score: float = 0.0


@dataclass
class AlignmentAlert:
    """An alert triggered by alignment threshold violations."""

    alert_id: str
    severity: AlertSeverity
    status: AlertStatus
    metric_name: str
    threshold_value: float
    actual_value: float
    message: str
    agent_id: str | None
    triggered_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    suppressed_until: datetime | None = None


@dataclass
class AgentComparison:
    """Comparison of alignment metrics across agents."""

    metric_name: str
    period_start: datetime
    period_end: datetime
    agents: list[dict[str, Any]]  # agent_id, value, rank, percentile
    mean_value: float
    std_deviation: float
    best_agent_id: str
    worst_agent_id: str


@dataclass
class AlignmentReport:
    """Comprehensive alignment report for export."""

    report_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    overall_health_score: float
    trends: list[TrendAnalysis]
    alerts: list[AlignmentAlert]
    comparisons: list[AgentComparison]
    recommendations: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertThreshold:
    """Configuration for an alert threshold."""

    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison: str  # "greater_than", "less_than", "outside_range"
    enabled: bool = True
    cooldown_minutes: int = 15  # Minimum time between alerts


class AlignmentAnalyticsService:
    """
    Historical trend analysis for alignment metrics.

    Aggregates metrics over time, detects trends, triggers alerts,
    and generates compliance reports.
    """

    # Default alert thresholds
    DEFAULT_THRESHOLDS: dict[str, AlertThreshold] = {
        "disagreement_rate": AlertThreshold(
            metric_name="disagreement_rate",
            warning_threshold=0.03,  # Below 3% is concerning
            critical_threshold=0.01,  # Below 1% is critical
            comparison="less_than",
        ),
        "confidence_calibration_error": AlertThreshold(
            metric_name="confidence_calibration_error",
            warning_threshold=0.15,  # Above 15% is concerning
            critical_threshold=0.20,  # Above 20% is critical
            comparison="greater_than",
        ),
        "rollback_success_rate": AlertThreshold(
            metric_name="rollback_success_rate",
            warning_threshold=0.95,  # Below 95% is concerning
            critical_threshold=0.90,  # Below 90% is critical
            comparison="less_than",
        ),
        "trust_score": AlertThreshold(
            metric_name="trust_score",
            warning_threshold=0.50,  # Below 50% is concerning
            critical_threshold=0.30,  # Below 30% is critical
            comparison="less_than",
        ),
        "transparency_score": AlertThreshold(
            metric_name="transparency_score",
            warning_threshold=0.90,  # Below 90% is concerning
            critical_threshold=0.80,  # Below 80% is critical
            comparison="less_than",
        ),
    }

    def __init__(
        self,
        retention_days: int = 90,
        max_data_points: int = 100000,
        thresholds: dict[str, AlertThreshold] | None = None,
    ) -> None:
        """
        Initialize the analytics service.

        Args:
            retention_days: Days to retain historical data
            max_data_points: Maximum data points to store in memory
            thresholds: Custom alert thresholds
        """
        self._retention_days = retention_days
        self._max_data_points = max_data_points
        self._thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()

        # Storage
        self._data_points: list[MetricDataPoint] = []
        self._alerts: dict[str, AlignmentAlert] = {}
        self._reports: dict[str, AlignmentReport] = {}
        self._last_alert_time: dict[str, datetime] = {}

        # Counters
        self._alert_counter = 0
        self._report_counter = 0

        # Thread safety
        self._lock = threading.RLock()

        logger.info(
            "AlignmentAnalyticsService initialized",
            extra={
                "retention_days": retention_days,
                "max_data_points": max_data_points,
                "threshold_count": len(self._thresholds),
            },
        )

    def record_metric(
        self,
        metric_name: str,
        value: float,
        agent_id: str | None = None,
        timestamp: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MetricDataPoint:
        """
        Record a metric observation.

        Args:
            metric_name: Name of the metric
            value: Metric value
            agent_id: Optional agent identifier
            timestamp: Optional timestamp (defaults to now)
            metadata: Optional additional metadata

        Returns:
            The recorded data point
        """
        with self._lock:
            data_point = MetricDataPoint(
                timestamp=timestamp or datetime.now(timezone.utc),
                metric_name=metric_name,
                value=value,
                agent_id=agent_id,
                metadata=metadata or {},
            )

            self._data_points.append(data_point)

            # Check for alerts
            self._check_alert_threshold(metric_name, value, agent_id)

            # Enforce retention limits
            self._enforce_limits()

            return data_point

    def record_metrics_batch(
        self,
        metrics: list[dict[str, Any]],
    ) -> list[MetricDataPoint]:
        """
        Record multiple metrics in a single call.

        Args:
            metrics: List of metric dicts with name, value, agent_id, etc.

        Returns:
            List of recorded data points
        """
        data_points = []
        for metric in metrics:
            dp = self.record_metric(
                metric_name=metric["name"],
                value=metric["value"],
                agent_id=metric.get("agent_id"),
                timestamp=metric.get("timestamp"),
                metadata=metric.get("metadata"),
            )
            data_points.append(dp)
        return data_points

    def analyze_trend(
        self,
        metric_name: str,
        period_hours: int = 24,
        agent_id: str | None = None,
        granularity: TimeGranularity = TimeGranularity.HOUR,
    ) -> TrendAnalysis:
        """
        Analyze trend for a specific metric.

        Args:
            metric_name: Name of the metric to analyze
            period_hours: Hours of history to analyze
            agent_id: Optional filter by agent
            granularity: Time granularity for aggregation

        Returns:
            TrendAnalysis with direction, slope, and statistics
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            period_start = now - timedelta(hours=period_hours)

            # Filter data points
            filtered = [
                dp
                for dp in self._data_points
                if dp.metric_name == metric_name
                and dp.timestamp >= period_start
                and (agent_id is None or dp.agent_id == agent_id)
            ]

            if len(filtered) < 2:
                return TrendAnalysis(
                    metric_name=metric_name,
                    direction=TrendDirection.UNKNOWN,
                    slope=0.0,
                    confidence=0.0,
                    current_value=filtered[-1].value if filtered else 0.0,
                    previous_value=filtered[0].value if filtered else 0.0,
                    change_percent=0.0,
                    period_start=period_start,
                    period_end=now,
                    data_points=len(filtered),
                )

            # Sort by timestamp
            filtered.sort(key=lambda x: x.timestamp)

            # Calculate trend
            values = [dp.value for dp in filtered]
            current = values[-1]
            previous = values[0]
            mean_value = statistics.mean(values)
            std_dev = statistics.stdev(values) if len(values) > 1 else 0.0

            # Simple linear regression for slope
            n = len(values)
            x_vals = list(range(n))
            x_mean = sum(x_vals) / n
            y_mean = mean_value

            numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
            denominator = sum((x - x_mean) ** 2 for x in x_vals)
            slope = numerator / denominator if denominator != 0 else 0.0

            # Calculate confidence (R-squared)
            ss_tot = sum((y - y_mean) ** 2 for y in values)
            ss_res = sum(
                (y - (slope * x + (y_mean - slope * x_mean))) ** 2
                for x, y in zip(x_vals, values)
            )
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
            confidence = max(0.0, min(1.0, r_squared))

            # Determine direction
            if abs(slope) < 0.001:
                direction = TrendDirection.STABLE
            elif slope > 0:
                # For metrics where higher is better
                direction = TrendDirection.IMPROVING
            else:
                direction = TrendDirection.DEGRADING

            # Calculate change percent
            change_percent = (
                ((current - previous) / previous * 100) if previous != 0 else 0.0
            )

            # Anomaly detection (simple z-score based)
            z_score = abs(current - mean_value) / std_dev if std_dev > 0 else 0.0
            is_anomaly = z_score > 3.0  # 3 standard deviations
            anomaly_score = min(1.0, z_score / 5.0)

            return TrendAnalysis(
                metric_name=metric_name,
                direction=direction,
                slope=slope,
                confidence=confidence,
                current_value=current,
                previous_value=previous,
                change_percent=change_percent,
                period_start=period_start,
                period_end=now,
                data_points=len(filtered),
                is_anomaly=is_anomaly,
                anomaly_score=anomaly_score,
            )

    def compare_agents(
        self,
        metric_name: str,
        period_hours: int = 24,
    ) -> AgentComparison:
        """
        Compare a metric across all agents.

        Args:
            metric_name: Name of the metric to compare
            period_hours: Hours of history to analyze

        Returns:
            AgentComparison with rankings and statistics
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            period_start = now - timedelta(hours=period_hours)

            # Filter and group by agent
            agent_values: dict[str, list[float]] = {}
            for dp in self._data_points:
                if (
                    dp.metric_name == metric_name
                    and dp.timestamp >= period_start
                    and dp.agent_id is not None
                ):
                    if dp.agent_id not in agent_values:
                        agent_values[dp.agent_id] = []
                    agent_values[dp.agent_id].append(dp.value)

            if not agent_values:
                return AgentComparison(
                    metric_name=metric_name,
                    period_start=period_start,
                    period_end=now,
                    agents=[],
                    mean_value=0.0,
                    std_deviation=0.0,
                    best_agent_id="",
                    worst_agent_id="",
                )

            # Calculate per-agent averages
            agent_averages = {
                agent_id: statistics.mean(values)
                for agent_id, values in agent_values.items()
            }

            # Sort by average (descending - higher is better)
            sorted_agents = sorted(
                agent_averages.items(), key=lambda x: x[1], reverse=True
            )

            # Calculate global statistics
            all_averages = list(agent_averages.values())
            mean_value = statistics.mean(all_averages)
            std_deviation = (
                statistics.stdev(all_averages) if len(all_averages) > 1 else 0.0
            )

            # Build agent comparison list
            agents = []
            for rank, (agent_id, avg) in enumerate(sorted_agents, 1):
                percentile = (len(sorted_agents) - rank + 1) / len(sorted_agents) * 100
                agents.append(
                    {
                        "agent_id": agent_id,
                        "value": avg,
                        "rank": rank,
                        "percentile": percentile,
                        "data_points": len(agent_values[agent_id]),
                    }
                )

            return AgentComparison(
                metric_name=metric_name,
                period_start=period_start,
                period_end=now,
                agents=agents,
                mean_value=mean_value,
                std_deviation=std_deviation,
                best_agent_id=sorted_agents[0][0],
                worst_agent_id=sorted_agents[-1][0],
            )

    def get_alerts(
        self,
        status: AlertStatus | None = None,
        severity: AlertSeverity | None = None,
        agent_id: str | None = None,
        since: datetime | None = None,
    ) -> list[AlignmentAlert]:
        """
        Get alerts with optional filtering.

        Args:
            status: Filter by status
            severity: Filter by severity
            agent_id: Filter by agent
            since: Filter by triggered_at >= since

        Returns:
            List of matching alerts
        """
        with self._lock:
            alerts = list(self._alerts.values())

            if status is not None:
                alerts = [a for a in alerts if a.status == status]
            if severity is not None:
                alerts = [a for a in alerts if a.severity == severity]
            if agent_id is not None:
                alerts = [a for a in alerts if a.agent_id == agent_id]
            if since is not None:
                alerts = [a for a in alerts if a.triggered_at >= since]

            # Sort by triggered_at descending
            alerts.sort(key=lambda a: a.triggered_at, reverse=True)
            return alerts

    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
    ) -> AlignmentAlert | None:
        """
        Acknowledge an alert.

        Args:
            alert_id: ID of the alert to acknowledge
            acknowledged_by: User acknowledging the alert

        Returns:
            Updated alert or None if not found
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return None

            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now(timezone.utc)
            alert.acknowledged_by = acknowledged_by

            logger.info(
                "Alert acknowledged",
                extra={"alert_id": alert_id, "acknowledged_by": acknowledged_by},
            )
            return alert

    def resolve_alert(
        self,
        alert_id: str,
        resolved_by: str,
    ) -> AlignmentAlert | None:
        """
        Resolve an alert.

        Args:
            alert_id: ID of the alert to resolve
            resolved_by: User resolving the alert

        Returns:
            Updated alert or None if not found
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return None

            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now(timezone.utc)
            alert.resolved_by = resolved_by

            logger.info(
                "Alert resolved",
                extra={"alert_id": alert_id, "resolved_by": resolved_by},
            )
            return alert

    def suppress_alert(
        self,
        alert_id: str,
        suppress_hours: int = 24,
    ) -> AlignmentAlert | None:
        """
        Suppress an alert for a specified duration.

        Args:
            alert_id: ID of the alert to suppress
            suppress_hours: Hours to suppress

        Returns:
            Updated alert or None if not found
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return None

            alert.status = AlertStatus.SUPPRESSED
            alert.suppressed_until = datetime.now(timezone.utc) + timedelta(
                hours=suppress_hours
            )

            logger.info(
                "Alert suppressed",
                extra={"alert_id": alert_id, "suppress_hours": suppress_hours},
            )
            return alert

    def generate_report(
        self,
        period_hours: int = 24,
        include_agent_comparison: bool = True,
    ) -> AlignmentReport:
        """
        Generate a comprehensive alignment report.

        Args:
            period_hours: Hours of history to include
            include_agent_comparison: Whether to include agent comparisons

        Returns:
            AlignmentReport with trends, alerts, and recommendations
        """
        with self._lock:
            self._report_counter += 1
            report_id = f"report-{self._report_counter:08d}"
            now = datetime.now(timezone.utc)
            period_start = now - timedelta(hours=period_hours)

            # Analyze trends for key metrics
            key_metrics = [
                "disagreement_rate",
                "confidence_calibration_error",
                "trust_score",
                "transparency_score",
                "rollback_success_rate",
            ]

            trends = [
                self.analyze_trend(metric, period_hours) for metric in key_metrics
            ]

            # Get recent alerts
            alerts = self.get_alerts(since=period_start)

            # Generate comparisons if requested
            comparisons = []
            if include_agent_comparison:
                comparisons = [
                    self.compare_agents(metric, period_hours) for metric in key_metrics
                ]

            # Calculate overall health score
            health_scores = []
            for trend in trends:
                if trend.direction == TrendDirection.IMPROVING:
                    health_scores.append(1.0)
                elif trend.direction == TrendDirection.STABLE:
                    health_scores.append(0.7)
                elif trend.direction == TrendDirection.DEGRADING:
                    health_scores.append(0.3)
                else:
                    health_scores.append(0.5)

            overall_health = statistics.mean(health_scores) if health_scores else 0.5

            # Generate recommendations
            recommendations = self._generate_recommendations(trends, alerts)

            # Single-pass metadata computation instead of 2 extra scans
            data_points_count = 0
            agents_seen: set[str] = set()
            for dp in self._data_points:
                if dp.timestamp >= period_start:
                    data_points_count += 1
                    if dp.agent_id:
                        agents_seen.add(dp.agent_id)

            report = AlignmentReport(
                report_id=report_id,
                generated_at=now,
                period_start=period_start,
                period_end=now,
                overall_health_score=overall_health,
                trends=trends,
                alerts=alerts,
                comparisons=comparisons,
                recommendations=recommendations,
                metadata={
                    "data_points_analyzed": data_points_count,
                    "agents_analyzed": len(agents_seen),
                },
            )

            self._reports[report_id] = report
            return report

    def get_time_series(
        self,
        metric_name: str,
        period_hours: int = 24,
        granularity: TimeGranularity = TimeGranularity.HOUR,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get time-series data for a metric.

        Args:
            metric_name: Name of the metric
            period_hours: Hours of history
            granularity: Aggregation granularity
            agent_id: Optional agent filter

        Returns:
            List of {timestamp, value, count} dicts
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            period_start = now - timedelta(hours=period_hours)

            # Filter data points
            filtered = [
                dp
                for dp in self._data_points
                if dp.metric_name == metric_name
                and dp.timestamp >= period_start
                and (agent_id is None or dp.agent_id == agent_id)
            ]

            if not filtered:
                return []

            # Determine bucket size
            bucket_seconds = {
                TimeGranularity.MINUTE: 60,
                TimeGranularity.HOUR: 3600,
                TimeGranularity.DAY: 86400,
                TimeGranularity.WEEK: 604800,
                TimeGranularity.MONTH: 2592000,  # 30 days
            }[granularity]

            # Group into buckets
            buckets: dict[int, list[float]] = {}
            for dp in filtered:
                bucket = (
                    int(dp.timestamp.timestamp() // bucket_seconds) * bucket_seconds
                )
                if bucket not in buckets:
                    buckets[bucket] = []
                buckets[bucket].append(dp.value)

            # Calculate aggregates
            result = []
            for bucket_ts, values in sorted(buckets.items()):
                result.append(
                    {
                        "timestamp": datetime.fromtimestamp(
                            bucket_ts, tz=timezone.utc
                        ).isoformat(),
                        "value": statistics.mean(values),
                        "min": min(values),
                        "max": max(values),
                        "count": len(values),
                    }
                )

            return result

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        with self._lock:
            active_alerts = len(
                [a for a in self._alerts.values() if a.status == AlertStatus.ACTIVE]
            )
            return {
                "total_data_points": len(self._data_points),
                "total_alerts": len(self._alerts),
                "active_alerts": active_alerts,
                "total_reports": len(self._reports),
                "threshold_count": len(self._thresholds),
                "retention_days": self._retention_days,
            }

    def set_threshold(self, threshold: AlertThreshold) -> None:
        """Set or update an alert threshold."""
        with self._lock:
            self._thresholds[threshold.metric_name] = threshold
            logger.info(
                "Threshold updated",
                extra={"metric_name": threshold.metric_name},
            )

    def clear_data(self, older_than_hours: int | None = None) -> int:
        """
        Clear historical data.

        Args:
            older_than_hours: Only clear data older than this (None = all)

        Returns:
            Number of data points removed
        """
        with self._lock:
            if older_than_hours is None:
                count = len(self._data_points)
                self._data_points.clear()
                return count

            cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
            original_count = len(self._data_points)
            self._data_points = [
                dp for dp in self._data_points if dp.timestamp >= cutoff
            ]
            return original_count - len(self._data_points)

    def _check_alert_threshold(
        self,
        metric_name: str,
        value: float,
        agent_id: str | None,
    ) -> AlignmentAlert | None:
        """Check if a metric value triggers an alert."""
        threshold = self._thresholds.get(metric_name)
        if threshold is None or not threshold.enabled:
            return None

        # Check cooldown
        cooldown_key = f"{metric_name}:{agent_id or 'global'}"
        last_alert = self._last_alert_time.get(cooldown_key)
        if last_alert is not None:
            cooldown_elapsed = datetime.now(timezone.utc) - last_alert
            if cooldown_elapsed < timedelta(minutes=threshold.cooldown_minutes):
                return None

        # Determine severity
        severity = None
        if threshold.comparison == "greater_than":
            if value >= threshold.critical_threshold:
                severity = AlertSeverity.CRITICAL
            elif value >= threshold.warning_threshold:
                severity = AlertSeverity.WARNING
        elif threshold.comparison == "less_than":
            if value <= threshold.critical_threshold:
                severity = AlertSeverity.CRITICAL
            elif value <= threshold.warning_threshold:
                severity = AlertSeverity.WARNING

        if severity is None:
            return None

        # Create alert
        self._alert_counter += 1
        alert_id = f"alert-{self._alert_counter:08d}"

        message = (
            f"{metric_name} is {value:.3f}, "
            f"{'above' if threshold.comparison == 'greater_than' else 'below'} "
            f"{'critical' if severity == AlertSeverity.CRITICAL else 'warning'} "
            f"threshold of "
            f"{threshold.critical_threshold if severity == AlertSeverity.CRITICAL else threshold.warning_threshold:.3f}"
        )

        alert = AlignmentAlert(
            alert_id=alert_id,
            severity=severity,
            status=AlertStatus.ACTIVE,
            metric_name=metric_name,
            threshold_value=(
                threshold.critical_threshold
                if severity == AlertSeverity.CRITICAL
                else threshold.warning_threshold
            ),
            actual_value=value,
            message=message,
            agent_id=agent_id,
            triggered_at=datetime.now(timezone.utc),
        )

        self._alerts[alert_id] = alert
        self._last_alert_time[cooldown_key] = datetime.now(timezone.utc)

        logger.warning(
            "Alignment alert triggered",
            extra={
                "alert_id": alert_id,
                "severity": severity.value,
                "metric_name": metric_name,
                "value": value,
                "agent_id": agent_id,
            },
        )

        return alert

    def _generate_recommendations(
        self,
        trends: list[TrendAnalysis],
        alerts: list[AlignmentAlert],
    ) -> list[str]:
        """Generate recommendations based on trends and alerts."""
        recommendations = []

        for trend in trends:
            if trend.direction == TrendDirection.DEGRADING:
                if trend.metric_name == "disagreement_rate":
                    recommendations.append(
                        "Consider reviewing agent training for excessive agreement bias. "
                        "Healthy disagreement rates should be between 5-15%."
                    )
                elif trend.metric_name == "trust_score":
                    recommendations.append(
                        "Trust scores are declining. Review recent agent actions for "
                        "accuracy issues and increase human oversight temporarily."
                    )
                elif trend.metric_name == "transparency_score":
                    recommendations.append(
                        "Transparency scores are degrading. Ensure all agent decisions "
                        "include complete reasoning chains and source attribution."
                    )
                elif trend.metric_name == "rollback_success_rate":
                    recommendations.append(
                        "Rollback success rate is declining. Verify snapshot storage "
                        "and rollback procedures are functioning correctly."
                    )

            if trend.is_anomaly:
                recommendations.append(
                    f"Anomaly detected in {trend.metric_name}. "
                    f"Current value ({trend.current_value:.3f}) is significantly "
                    f"different from historical norms."
                )

        # Alert-based recommendations
        critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        if len(critical_alerts) >= 3:
            recommendations.append(
                "Multiple critical alerts detected. Consider pausing autonomous "
                "operations until issues are resolved."
            )

        return recommendations

    def _enforce_limits(self) -> None:
        """Enforce retention and size limits.

        Uses periodic cleanup instead of full list rebuild on every call.
        Only rebuilds when size exceeds threshold (10% over max).
        """
        # Only enforce size limit when significantly over capacity
        # This avoids O(n) rebuild on every record_metric call
        threshold = int(self._max_data_points * 1.1)
        if len(self._data_points) <= threshold:
            return

        # Remove expired data points
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        self._data_points = [dp for dp in self._data_points if dp.timestamp >= cutoff]

        # Enforce max data points (remove oldest first)
        if len(self._data_points) > self._max_data_points:
            excess = len(self._data_points) - self._max_data_points
            self._data_points = self._data_points[excess:]
