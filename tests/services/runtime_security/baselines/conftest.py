"""
Test fixtures for behavioral baseline services.

Provides shared fixtures used across test_metrics, test_baseline_engine,
and test_drift_detector modules.
"""

from datetime import datetime, timezone

import pytest

from src.services.runtime_security.baselines import (
    BehavioralBaselineEngine,
    MetricDataPoint,
    MetricType,
    MetricWindow,
    reset_baseline_engine,
)
from src.services.runtime_security.baselines.drift_detector import DriftDetector


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all baseline singletons before and after each test."""
    reset_baseline_engine()
    yield
    reset_baseline_engine()


@pytest.fixture
def now_utc() -> datetime:
    """Consistent UTC timestamp for deterministic tests."""
    return datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_data_point(now_utc) -> MetricDataPoint:
    """A single MetricDataPoint for basic tests."""
    return MetricDataPoint(
        agent_id="coder-agent",
        metric_type=MetricType.TOOL_CALL_FREQUENCY,
        value=15.0,
        timestamp=now_utc,
        window=MetricWindow.HOUR_1,
    )


@pytest.fixture
def engine() -> BehavioralBaselineEngine:
    """BehavioralBaselineEngine with min_samples=3 for easier fixture setup."""
    return BehavioralBaselineEngine(min_samples=3)


@pytest.fixture
def populated_engine(engine, now_utc) -> BehavioralBaselineEngine:
    """
    Engine pre-loaded with 20+ data points across multiple metric types,
    windows, and agents.

    Data layout (all min_samples=3 satisfied):
      coder-agent / TOOL_CALL_FREQUENCY / HOUR_1: 10, 12, 14, 11, 13
      coder-agent / TOOL_CALL_FREQUENCY / DAY_7:  10, 10, 10, 10, 10
      coder-agent / TOKEN_CONSUMPTION   / HOUR_1: 500, 520, 510, 490, 530
      coder-agent / ERROR_RATE          / HOUR_1: 0.01, 0.02, 0.015, 0.01, 0.02
      reviewer-agent / TOOL_CALL_FREQUENCY / HOUR_1: 5, 6, 7, 5, 6
      reviewer-agent / APPROVAL_RATE      / HOUR_1: 0.90, 0.92, 0.91, 0.89, 0.93
    """
    data_sets = [
        # coder-agent / TOOL_CALL_FREQUENCY / HOUR_1
        (
            "coder-agent",
            MetricType.TOOL_CALL_FREQUENCY,
            MetricWindow.HOUR_1,
            [10.0, 12.0, 14.0, 11.0, 13.0],
        ),
        # coder-agent / TOOL_CALL_FREQUENCY / DAY_7 (flat baseline for drift comparison)
        (
            "coder-agent",
            MetricType.TOOL_CALL_FREQUENCY,
            MetricWindow.DAY_7,
            [10.0, 10.0, 10.0, 10.0, 10.0],
        ),
        # coder-agent / TOKEN_CONSUMPTION / HOUR_1
        (
            "coder-agent",
            MetricType.TOKEN_CONSUMPTION,
            MetricWindow.HOUR_1,
            [500.0, 520.0, 510.0, 490.0, 530.0],
        ),
        # coder-agent / ERROR_RATE / HOUR_1
        (
            "coder-agent",
            MetricType.ERROR_RATE,
            MetricWindow.HOUR_1,
            [0.01, 0.02, 0.015, 0.01, 0.02],
        ),
        # reviewer-agent / TOOL_CALL_FREQUENCY / HOUR_1
        (
            "reviewer-agent",
            MetricType.TOOL_CALL_FREQUENCY,
            MetricWindow.HOUR_1,
            [5.0, 6.0, 7.0, 5.0, 6.0],
        ),
        # reviewer-agent / APPROVAL_RATE / HOUR_1
        (
            "reviewer-agent",
            MetricType.APPROVAL_RATE,
            MetricWindow.HOUR_1,
            [0.90, 0.92, 0.91, 0.89, 0.93],
        ),
    ]

    for agent_id, metric_type, window, values in data_sets:
        for v in values:
            engine.record(
                MetricDataPoint(
                    agent_id=agent_id,
                    metric_type=metric_type,
                    value=v,
                    timestamp=now_utc,
                    window=window,
                )
            )

    # Compute profiles so baselines are cached
    engine.compute_profile("coder-agent")
    engine.compute_profile("reviewer-agent")

    return engine


@pytest.fixture
def drift_detector(populated_engine) -> DriftDetector:
    """DriftDetector wired to the populated engine."""
    return DriftDetector(engine=populated_engine)
