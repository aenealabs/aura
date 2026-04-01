"""
Project Aura - Behavioral Baseline Engine

Per-agent behavioral profiling with drift detection and alerting.
Extends ADR-072 statistical detector with agent-specific metrics.

Based on ADR-083: Runtime Agent Security Platform
"""

from .baseline_engine import (
    BehavioralBaselineEngine,
    BehavioralProfile,
    DeviationResult,
    DeviationSeverity,
    get_baseline_engine,
    reset_baseline_engine,
)
from .drift_detector import DriftAlert, DriftDetector, DriftType
from .metrics import BaselineMetric, MetricDataPoint, MetricType, MetricWindow

__all__ = [
    # Metrics
    "BaselineMetric",
    "MetricType",
    "MetricWindow",
    "MetricDataPoint",
    # Engine
    "BehavioralBaselineEngine",
    "BehavioralProfile",
    "DeviationResult",
    "DeviationSeverity",
    "get_baseline_engine",
    "reset_baseline_engine",
    # Drift
    "DriftDetector",
    "DriftAlert",
    "DriftType",
]
