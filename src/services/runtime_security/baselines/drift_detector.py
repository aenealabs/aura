"""
Project Aura - Behavioral Drift Detector

Detects gradual behavioral drift in agents by comparing baselines
across different time windows. Alerts when agent behavior shifts
beyond configured thresholds.

Based on ADR-083: Runtime Agent Security Platform

Compliance:
- NIST 800-53 SI-4: Information system monitoring
- NIST 800-53 CA-7: Continuous monitoring
"""

import logging
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .baseline_engine import BehavioralBaselineEngine, DeviationSeverity
from .metrics import BaselineMetric, MetricType, MetricWindow

logger = logging.getLogger(__name__)


class DriftType(Enum):
    """Types of behavioral drift."""

    GRADUAL_INCREASE = "gradual_increase"
    GRADUAL_DECREASE = "gradual_decrease"
    SUDDEN_SHIFT = "sudden_shift"
    PATTERN_CHANGE = "pattern_change"
    NEW_BEHAVIOR = "new_behavior"


@dataclass(frozen=True)
class DriftAlert:
    """Immutable alert for detected behavioral drift."""

    alert_id: str
    timestamp: datetime
    agent_id: str
    metric_type: MetricType
    drift_type: DriftType
    severity: DeviationSeverity
    short_window_mean: float
    long_window_mean: float
    drift_magnitude: float
    drift_percentage: float
    explanation: str
    recommended_action: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "metric_type": self.metric_type.value,
            "drift_type": self.drift_type.value,
            "severity": self.severity.value,
            "short_window_mean": round(self.short_window_mean, 6),
            "long_window_mean": round(self.long_window_mean, 6),
            "drift_magnitude": round(self.drift_magnitude, 6),
            "drift_percentage": round(self.drift_percentage, 2),
            "explanation": self.explanation,
            "recommended_action": self.recommended_action,
        }


class DriftDetector:
    """
    Detects behavioral drift by comparing short-term and long-term baselines.

    When an agent's recent behavior (1h window) deviates significantly from
    its historical behavior (7d window), a drift alert is generated.

    Usage:
        detector = DriftDetector(engine=get_baseline_engine())

        # Check for drift
        alerts = detector.detect_drift("coder-agent")
        for alert in alerts:
            if alert.severity == DeviationSeverity.HIGH:
                investigate(alert)
    """

    def __init__(
        self,
        engine: Optional[BehavioralBaselineEngine] = None,
        short_window: MetricWindow = MetricWindow.HOUR_1,
        long_window: MetricWindow = MetricWindow.DAY_7,
        drift_thresholds: Optional[dict[DeviationSeverity, float]] = None,
    ):
        self.engine = engine or BehavioralBaselineEngine()
        self.short_window = short_window
        self.long_window = long_window
        self.drift_thresholds = drift_thresholds or {
            DeviationSeverity.LOW: 0.25,  # 25% drift
            DeviationSeverity.MEDIUM: 0.50,  # 50% drift
            DeviationSeverity.HIGH: 1.00,  # 100% drift
            DeviationSeverity.CRITICAL: 2.00,  # 200% drift
        }

        self._alerts: deque[DriftAlert] = deque(maxlen=10000)

    def detect_drift(self, agent_id: str) -> list[DriftAlert]:
        """
        Detect behavioral drift for an agent.

        Compares short-window baselines against long-window baselines
        for all metric types.

        Args:
            agent_id: The agent to check for drift.

        Returns:
            List of drift alerts, sorted by severity.
        """
        profile = self.engine.get_profile(agent_id)
        if profile is None:
            profile = self.engine.compute_profile(agent_id)

        alerts: list[DriftAlert] = []

        # Group baselines by metric type and tool name
        short_baselines: dict[tuple[MetricType, Optional[str]], BaselineMetric] = {}
        long_baselines: dict[tuple[MetricType, Optional[str]], BaselineMetric] = {}

        for baseline in profile.baselines:
            key = (baseline.metric_type, baseline.tool_name)
            if baseline.window == self.short_window:
                short_baselines[key] = baseline
            elif baseline.window == self.long_window:
                long_baselines[key] = baseline

        # Compare short vs long for each metric
        for key, short_bl in short_baselines.items():
            long_bl = long_baselines.get(key)
            if long_bl is None:
                continue

            alert = self._compare_windows(agent_id, short_bl, long_bl)
            if alert is not None:
                alerts.append(alert)

        # Check for new behaviors (metrics in short that don't exist in long)
        for key in short_baselines:
            if key not in long_baselines:
                metric_type, tool_name = key
                short_bl = short_baselines[key]
                alert = DriftAlert(
                    alert_id=f"da-{uuid.uuid4().hex[:16]}",
                    timestamp=datetime.now(timezone.utc),
                    agent_id=agent_id,
                    metric_type=metric_type,
                    drift_type=DriftType.NEW_BEHAVIOR,
                    severity=DeviationSeverity.MEDIUM,
                    short_window_mean=short_bl.mean,
                    long_window_mean=0.0,
                    drift_magnitude=short_bl.mean,
                    drift_percentage=100.0,
                    explanation=(
                        f"New behavior detected: {metric_type.value}"
                        + (f" for tool '{tool_name}'" if tool_name else "")
                        + f" (mean={short_bl.mean:.2f}, no historical baseline)"
                    ),
                    recommended_action="Investigate new agent behavior pattern",
                )
                alerts.append(alert)

        self._alerts.extend(alerts)
        return sorted(
            alerts,
            key=lambda a: self._severity_rank(a.severity),
            reverse=True,
        )

    def detect_drift_all_agents(self) -> list[DriftAlert]:
        """Detect drift across all profiled agents."""
        all_alerts: list[DriftAlert] = []
        for profile in self.engine.get_all_profiles():
            alerts = self.detect_drift(profile.agent_id)
            all_alerts.extend(alerts)
        return sorted(
            all_alerts,
            key=lambda a: self._severity_rank(a.severity),
            reverse=True,
        )

    def get_all_alerts(self) -> list[DriftAlert]:
        """Get all historical drift alerts."""
        return list(self._alerts)

    def get_alerts_for_agent(self, agent_id: str) -> list[DriftAlert]:
        """Get drift alerts for a specific agent."""
        return [a for a in self._alerts if a.agent_id == agent_id]

    @property
    def total_alerts(self) -> int:
        """Total drift alerts generated."""
        return len(self._alerts)

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _compare_windows(
        self,
        agent_id: str,
        short_bl: BaselineMetric,
        long_bl: BaselineMetric,
    ) -> Optional[DriftAlert]:
        """Compare short and long window baselines for drift."""
        if long_bl.mean == 0:
            if short_bl.mean == 0:
                return None
            drift_pct = 100.0
        else:
            drift_pct = abs(short_bl.mean - long_bl.mean) / abs(long_bl.mean)

        severity = self._classify_drift_severity(drift_pct)
        if severity == DeviationSeverity.NORMAL:
            return None

        drift_type = self._classify_drift_type(short_bl, long_bl)
        magnitude = abs(short_bl.mean - long_bl.mean)

        return DriftAlert(
            alert_id=f"da-{uuid.uuid4().hex[:16]}",
            timestamp=datetime.now(timezone.utc),
            agent_id=agent_id,
            metric_type=short_bl.metric_type,
            drift_type=drift_type,
            severity=severity,
            short_window_mean=short_bl.mean,
            long_window_mean=long_bl.mean,
            drift_magnitude=magnitude,
            drift_percentage=drift_pct * 100,
            explanation=self._build_drift_explanation(
                short_bl, long_bl, drift_type, drift_pct
            ),
            recommended_action=self._recommend_drift_action(severity, drift_type),
        )

    def _classify_drift_severity(self, drift_pct: float) -> DeviationSeverity:
        """Classify drift severity from percentage change."""
        if drift_pct >= self.drift_thresholds[DeviationSeverity.CRITICAL]:
            return DeviationSeverity.CRITICAL
        if drift_pct >= self.drift_thresholds[DeviationSeverity.HIGH]:
            return DeviationSeverity.HIGH
        if drift_pct >= self.drift_thresholds[DeviationSeverity.MEDIUM]:
            return DeviationSeverity.MEDIUM
        if drift_pct >= self.drift_thresholds[DeviationSeverity.LOW]:
            return DeviationSeverity.LOW
        return DeviationSeverity.NORMAL

    @staticmethod
    def _classify_drift_type(
        short_bl: BaselineMetric, long_bl: BaselineMetric
    ) -> DriftType:
        """Classify the type of drift observed."""
        if short_bl.std_dev > long_bl.std_dev * 2:
            return DriftType.PATTERN_CHANGE

        diff = short_bl.mean - long_bl.mean
        if abs(diff) > long_bl.std_dev * 3:
            return DriftType.SUDDEN_SHIFT
        elif diff > 0:
            return DriftType.GRADUAL_INCREASE
        else:
            return DriftType.GRADUAL_DECREASE

    @staticmethod
    def _build_drift_explanation(
        short_bl: BaselineMetric,
        long_bl: BaselineMetric,
        drift_type: DriftType,
        drift_pct: float,
    ) -> str:
        """Build human-readable explanation of the drift."""
        metric_name = short_bl.metric_type.value
        tool_suffix = f" for tool '{short_bl.tool_name}'" if short_bl.tool_name else ""

        return (
            f"{drift_type.value.replace('_', ' ').title()} detected in "
            f"{metric_name}{tool_suffix}: "
            f"recent mean={short_bl.mean:.2f} vs historical mean={long_bl.mean:.2f} "
            f"({drift_pct * 100:.1f}% change)"
        )

    @staticmethod
    def _recommend_drift_action(
        severity: DeviationSeverity, drift_type: DriftType
    ) -> str:
        """Recommend action based on drift severity and type."""
        if severity == DeviationSeverity.CRITICAL:
            return "Immediate investigation required - agent behavior has changed dramatically"
        if severity == DeviationSeverity.HIGH:
            return "Review agent configuration and recent changes - significant drift detected"
        if drift_type == DriftType.SUDDEN_SHIFT:
            return "Check for configuration changes or external events causing sudden shift"
        if drift_type == DriftType.NEW_BEHAVIOR:
            return "Verify new behavior is expected and update baselines if appropriate"
        return "Monitor - gradual drift detected, may indicate model or data changes"

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
