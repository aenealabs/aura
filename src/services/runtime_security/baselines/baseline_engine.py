"""
Project Aura - Behavioral Baseline Engine

Builds per-agent behavioral profiles from intercepted traffic data
and computes deviation scores for anomaly detection.

Extends ADR-072 statistical detector with agent-specific metrics
using z-score and IQR-based anomaly detection.

Based on ADR-083: Runtime Agent Security Platform

Compliance:
- NIST 800-53 SI-4: Information system monitoring
- NIST 800-53 AU-6: Audit review, analysis, and reporting
- NIST 800-53 CA-7: Continuous monitoring
"""

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .metrics import BaselineMetric, MetricDataPoint, MetricType, MetricWindow

logger = logging.getLogger(__name__)


class DeviationSeverity(Enum):
    """Severity of a behavioral deviation."""

    NORMAL = "normal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DeviationResult:
    """Immutable result of a deviation check against a baseline."""

    agent_id: str
    metric_type: MetricType
    current_value: float
    baseline_mean: float
    baseline_std_dev: float
    z_score: float
    is_outlier_zscore: bool
    is_outlier_iqr: bool
    severity: DeviationSeverity
    window: MetricWindow
    timestamp: datetime
    tool_name: Optional[str] = None
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "metric_type": self.metric_type.value,
            "current_value": round(self.current_value, 6),
            "baseline_mean": round(self.baseline_mean, 6),
            "baseline_std_dev": round(self.baseline_std_dev, 6),
            "z_score": round(self.z_score, 4),
            "is_outlier_zscore": self.is_outlier_zscore,
            "is_outlier_iqr": self.is_outlier_iqr,
            "severity": self.severity.value,
            "window": self.window.value,
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class BehavioralProfile:
    """
    Immutable behavioral profile for an agent.

    Contains baseline metrics across all metric types and windows,
    enabling comprehensive deviation analysis.
    """

    agent_id: str
    baselines: tuple[BaselineMetric, ...]
    computed_at: datetime
    data_points_used: int
    windows_computed: tuple[MetricWindow, ...]

    def __post_init__(self) -> None:
        """Build O(1) lookup index for baselines."""
        index: dict[tuple[MetricType, MetricWindow, Optional[str]], BaselineMetric] = {}
        for b in self.baselines:
            index[(b.metric_type, b.window, b.tool_name)] = b
        object.__setattr__(self, "_baseline_index", index)

    @property
    def metric_count(self) -> int:
        """Number of baseline metrics in profile."""
        return len(self.baselines)

    def get_baseline(
        self,
        metric_type: MetricType,
        window: MetricWindow,
        tool_name: Optional[str] = None,
    ) -> Optional[BaselineMetric]:
        """Get a specific baseline metric."""
        return self._baseline_index.get((metric_type, window, tool_name))  # type: ignore[attr-defined]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "baselines": [b.to_dict() for b in self.baselines],
            "computed_at": self.computed_at.isoformat(),
            "data_points_used": self.data_points_used,
            "windows_computed": [w.value for w in self.windows_computed],
            "metric_count": self.metric_count,
        }


class BehavioralBaselineEngine:
    """
    Per-agent behavioral profiling and deviation scoring engine.

    Collects metric data points from intercepted traffic, computes
    statistical baselines (mean, std_dev, percentiles), and scores
    new observations for deviation using z-score and IQR methods.

    Usage:
        engine = BehavioralBaselineEngine()

        # Record data points from traffic
        engine.record(MetricDataPoint(
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=15.0,
            timestamp=now,
            window=MetricWindow.HOUR_1,
        ))

        # Compute profile
        profile = engine.compute_profile("coder-agent")

        # Check deviation
        result = engine.check_deviation(
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=150.0,  # 10x normal
            window=MetricWindow.HOUR_1,
        )
        assert result.severity == DeviationSeverity.CRITICAL
    """

    def __init__(
        self,
        min_samples: int = 10,
        z_score_thresholds: Optional[dict[DeviationSeverity, float]] = None,
        windows: Optional[list[MetricWindow]] = None,
    ):
        self.min_samples = min_samples
        self.z_score_thresholds = z_score_thresholds or {
            DeviationSeverity.LOW: 2.0,
            DeviationSeverity.MEDIUM: 2.5,
            DeviationSeverity.HIGH: 3.0,
            DeviationSeverity.CRITICAL: 4.0,
        }
        self.windows = windows or [
            MetricWindow.HOUR_1,
            MetricWindow.HOUR_24,
            MetricWindow.DAY_7,
        ]

        # Data storage: agent_id -> metric_type -> window -> tool_name -> data points
        self._data: dict[
            str,
            dict[
                MetricType,
                dict[MetricWindow, dict[Optional[str], list[MetricDataPoint]]],
            ],
        ] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        )
        self._profiles: dict[str, BehavioralProfile] = {}
        self._record_count: int = 0

    def record(self, data_point: MetricDataPoint) -> None:
        """
        Record a metric data point.

        Args:
            data_point: The metric observation to record.
        """
        self._data[data_point.agent_id][data_point.metric_type][data_point.window][
            data_point.tool_name
        ].append(data_point)
        self._record_count += 1

    def record_batch(self, data_points: list[MetricDataPoint]) -> int:
        """
        Record multiple data points.

        Args:
            data_points: List of metric observations.

        Returns:
            Number of points recorded.
        """
        for dp in data_points:
            self.record(dp)
        return len(data_points)

    def compute_profile(self, agent_id: str) -> BehavioralProfile:
        """
        Compute a behavioral profile for an agent.

        Args:
            agent_id: The agent to profile.

        Returns:
            BehavioralProfile with baselines for all observed metrics.
        """
        baselines: list[BaselineMetric] = []
        total_points = 0
        windows_used: set[MetricWindow] = set()

        agent_data = self._data.get(agent_id, {})

        for metric_type, window_data in agent_data.items():
            for window, tool_data in window_data.items():
                for tool_name, points in tool_data.items():
                    if len(points) < self.min_samples:
                        continue

                    values = [p.value for p in points]
                    baseline = self._compute_baseline(
                        agent_id, metric_type, window, values, tool_name
                    )
                    baselines.append(baseline)
                    total_points += len(points)
                    windows_used.add(window)

        profile = BehavioralProfile(
            agent_id=agent_id,
            baselines=tuple(baselines),
            computed_at=datetime.now(timezone.utc),
            data_points_used=total_points,
            windows_computed=tuple(sorted(windows_used, key=lambda w: w.value)),
        )
        self._profiles[agent_id] = profile
        return profile

    def check_deviation(
        self,
        agent_id: str,
        metric_type: MetricType,
        value: float,
        window: MetricWindow = MetricWindow.HOUR_1,
        tool_name: Optional[str] = None,
    ) -> DeviationResult:
        """
        Check if a value deviates from the agent's baseline.

        Args:
            agent_id: The agent to check.
            metric_type: Type of metric.
            value: Current observed value.
            window: Time window for baseline.
            tool_name: Optional tool name for tool-specific baselines.

        Returns:
            DeviationResult with severity classification.
        """
        profile = self._profiles.get(agent_id)
        if profile is None:
            profile = self.compute_profile(agent_id)

        baseline = profile.get_baseline(metric_type, window, tool_name)
        now = datetime.now(timezone.utc)

        if baseline is None or baseline.sample_count < self.min_samples:
            return DeviationResult(
                agent_id=agent_id,
                metric_type=metric_type,
                current_value=value,
                baseline_mean=0.0,
                baseline_std_dev=0.0,
                z_score=0.0,
                is_outlier_zscore=False,
                is_outlier_iqr=False,
                severity=DeviationSeverity.NORMAL,
                window=window,
                timestamp=now,
                tool_name=tool_name,
                explanation="Insufficient baseline data",
            )

        z = baseline.z_score(value)
        is_outlier_z = baseline.is_outlier_zscore(value)
        is_outlier_iqr = baseline.is_outlier_iqr(value)
        severity = self._classify_severity(z)
        explanation = self._build_explanation(
            value, baseline, z, is_outlier_z, is_outlier_iqr, severity
        )

        return DeviationResult(
            agent_id=agent_id,
            metric_type=metric_type,
            current_value=value,
            baseline_mean=baseline.mean,
            baseline_std_dev=baseline.std_dev,
            z_score=z,
            is_outlier_zscore=is_outlier_z,
            is_outlier_iqr=is_outlier_iqr,
            severity=severity,
            window=window,
            timestamp=now,
            tool_name=tool_name,
            explanation=explanation,
        )

    def check_all_deviations(
        self,
        agent_id: str,
        current_metrics: dict[MetricType, float],
        window: MetricWindow = MetricWindow.HOUR_1,
    ) -> list[DeviationResult]:
        """
        Check deviations across all provided metrics.

        Args:
            agent_id: The agent to check.
            current_metrics: Map of metric type to current value.
            window: Time window for baselines.

        Returns:
            List of deviation results, sorted by severity (critical first).
        """
        results = []
        for metric_type, value in current_metrics.items():
            result = self.check_deviation(agent_id, metric_type, value, window)
            results.append(result)

        return sorted(
            results,
            key=lambda r: self._severity_rank(r.severity),
            reverse=True,
        )

    def get_profile(self, agent_id: str) -> Optional[BehavioralProfile]:
        """Get the cached profile for an agent."""
        return self._profiles.get(agent_id)

    def get_all_profiles(self) -> list[BehavioralProfile]:
        """Get all cached profiles."""
        return list(self._profiles.values())

    @property
    def record_count(self) -> int:
        """Total number of recorded data points."""
        return self._record_count

    @property
    def agent_count(self) -> int:
        """Number of agents with recorded data."""
        return len(self._data)

    @property
    def profile_count(self) -> int:
        """Number of computed profiles."""
        return len(self._profiles)

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _compute_baseline(
        self,
        agent_id: str,
        metric_type: MetricType,
        window: MetricWindow,
        values: list[float],
        tool_name: Optional[str] = None,
    ) -> BaselineMetric:
        """Compute statistical baseline from values."""
        sorted_values = sorted(values)
        n = len(sorted_values)

        mean = statistics.mean(sorted_values)
        std_dev = statistics.stdev(sorted_values) if n > 1 else 0.0
        median = statistics.median(sorted_values)

        p25_idx = int(n * 0.25)
        p75_idx = int(n * 0.75)
        p95_idx = int(n * 0.95)

        return BaselineMetric(
            agent_id=agent_id,
            metric_type=metric_type,
            window=window,
            mean=mean,
            std_dev=std_dev,
            median=median,
            p25=sorted_values[min(p25_idx, n - 1)],
            p75=sorted_values[min(p75_idx, n - 1)],
            p95=sorted_values[min(p95_idx, n - 1)],
            min_value=sorted_values[0],
            max_value=sorted_values[-1],
            sample_count=n,
            computed_at=datetime.now(timezone.utc),
            tool_name=tool_name,
        )

    def _classify_severity(self, z_score: float) -> DeviationSeverity:
        """Classify deviation severity from z-score."""
        abs_z = abs(z_score)
        if abs_z >= self.z_score_thresholds[DeviationSeverity.CRITICAL]:
            return DeviationSeverity.CRITICAL
        if abs_z >= self.z_score_thresholds[DeviationSeverity.HIGH]:
            return DeviationSeverity.HIGH
        if abs_z >= self.z_score_thresholds[DeviationSeverity.MEDIUM]:
            return DeviationSeverity.MEDIUM
        if abs_z >= self.z_score_thresholds[DeviationSeverity.LOW]:
            return DeviationSeverity.LOW
        return DeviationSeverity.NORMAL

    @staticmethod
    def _build_explanation(
        value: float,
        baseline: BaselineMetric,
        z_score: float,
        is_outlier_z: bool,
        is_outlier_iqr: bool,
        severity: DeviationSeverity,
    ) -> str:
        """Build human-readable explanation of the deviation."""
        if severity == DeviationSeverity.NORMAL:
            return f"Value {value:.2f} is within normal range (mean={baseline.mean:.2f}, std={baseline.std_dev:.2f})"

        direction = "above" if value > baseline.mean else "below"
        methods = []
        if is_outlier_z:
            methods.append(f"z-score={z_score:.2f}")
        if is_outlier_iqr:
            methods.append(
                f"outside IQR [{baseline.lower_fence:.2f}, {baseline.upper_fence:.2f}]"
            )

        return (
            f"Value {value:.2f} is {abs(z_score):.1f} std devs {direction} mean "
            f"({baseline.mean:.2f}); flagged by: {', '.join(methods)}"
        )

    @staticmethod
    def _severity_rank(severity: DeviationSeverity) -> int:
        """Numeric rank for sorting."""
        ranks = {
            DeviationSeverity.NORMAL: 0,
            DeviationSeverity.LOW: 1,
            DeviationSeverity.MEDIUM: 2,
            DeviationSeverity.HIGH: 3,
            DeviationSeverity.CRITICAL: 4,
        }
        return ranks[severity]


# Singleton instance
_engine_instance: Optional[BehavioralBaselineEngine] = None


def get_baseline_engine() -> BehavioralBaselineEngine:
    """Get singleton baseline engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = BehavioralBaselineEngine()
    return _engine_instance


def reset_baseline_engine() -> None:
    """Reset baseline engine singleton (for testing)."""
    global _engine_instance
    _engine_instance = None
