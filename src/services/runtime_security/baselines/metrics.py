"""
Project Aura - Behavioral Baseline Metrics

Frozen dataclass definitions for behavioral metrics collected from
agent traffic. Used by the baseline engine for profile computation
and deviation scoring.

Based on ADR-083: Runtime Agent Security Platform

Compliance:
- NIST 800-53 SI-4: Information system monitoring
- NIST 800-53 AU-6: Audit review, analysis, and reporting
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class MetricType(Enum):
    """Types of behavioral metrics tracked per agent."""

    TOOL_CALL_FREQUENCY = "tool_call_frequency"
    TOKEN_CONSUMPTION = "token_consumption"
    APPROVAL_RATE = "approval_rate"
    ERROR_RATE = "error_rate"
    RESPONSE_LATENCY = "response_latency"
    AGENT_COMMUNICATION_FREQUENCY = "agent_communication_frequency"
    MCP_SERVER_ACCESS_FREQUENCY = "mcp_server_access_frequency"
    UNIQUE_TOOLS_USED = "unique_tools_used"
    SESSION_DURATION = "session_duration"
    CHECKPOINT_FREQUENCY = "checkpoint_frequency"
    POLICY_WRITE_FREQUENCY = "policy_write_frequency"  # ADR-086 Phase 2


class MetricWindow(Enum):
    """Time windows for baseline computation."""

    HOUR_1 = 1
    HOUR_24 = 24
    DAY_7 = 168  # 7 * 24


@dataclass(frozen=True)
class MetricDataPoint:
    """Immutable data point for a single metric observation."""

    agent_id: str
    metric_type: MetricType
    value: float
    timestamp: datetime
    window: MetricWindow
    tool_name: Optional[str] = None
    metadata: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "metric_type": self.metric_type.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "window": self.window.value,
            "tool_name": self.tool_name,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BaselineMetric:
    """
    Immutable baseline metric with statistical parameters.

    Computed from historical data points to establish normal behavior
    ranges for an agent. Used for deviation scoring.
    """

    agent_id: str
    metric_type: MetricType
    window: MetricWindow
    mean: float
    std_dev: float
    median: float
    p25: float
    p75: float
    p95: float
    min_value: float
    max_value: float
    sample_count: int
    computed_at: datetime
    tool_name: Optional[str] = None

    @property
    def iqr(self) -> float:
        """Interquartile range."""
        return self.p75 - self.p25

    @property
    def lower_fence(self) -> float:
        """Lower fence for IQR-based outlier detection (Q1 - 1.5 * IQR)."""
        return self.p25 - 1.5 * self.iqr

    @property
    def upper_fence(self) -> float:
        """Upper fence for IQR-based outlier detection (Q3 + 1.5 * IQR)."""
        return self.p75 + 1.5 * self.iqr

    def z_score(self, value: float) -> float:
        """Compute z-score for a given value against this baseline."""
        if self.std_dev == 0:
            return 0.0 if value == self.mean else float("inf")
        return (value - self.mean) / self.std_dev

    def is_outlier_zscore(self, value: float, threshold: float = 3.0) -> bool:
        """Check if value is an outlier by z-score."""
        return abs(self.z_score(value)) > threshold

    def is_outlier_iqr(self, value: float) -> bool:
        """Check if value is an outlier by IQR method."""
        return value < self.lower_fence or value > self.upper_fence

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "metric_type": self.metric_type.value,
            "window": self.window.value,
            "mean": round(self.mean, 6),
            "std_dev": round(self.std_dev, 6),
            "median": round(self.median, 6),
            "p25": round(self.p25, 6),
            "p75": round(self.p75, 6),
            "p95": round(self.p95, 6),
            "min_value": round(self.min_value, 6),
            "max_value": round(self.max_value, 6),
            "sample_count": self.sample_count,
            "computed_at": self.computed_at.isoformat(),
            "tool_name": self.tool_name,
            "iqr": round(self.iqr, 6),
            "lower_fence": round(self.lower_fence, 6),
            "upper_fence": round(self.upper_fence, 6),
        }
