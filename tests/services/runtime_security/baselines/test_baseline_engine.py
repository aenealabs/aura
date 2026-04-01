"""
Tests for the Behavioral Baseline Engine (ADR-083 Phase 2).

Covers DeviationSeverity, DeviationResult, BehavioralProfile,
recording, profile computation, deviation checking, and singleton
lifecycle.
"""

import math
from datetime import datetime, timezone

import pytest

from src.services.runtime_security.baselines import (
    BehavioralBaselineEngine,
    MetricDataPoint,
    MetricType,
    MetricWindow,
    get_baseline_engine,
    reset_baseline_engine,
)
from src.services.runtime_security.baselines.baseline_engine import (
    BehavioralProfile,
    DeviationResult,
    DeviationSeverity,
)

# ---------------------------------------------------------------------------
# DeviationSeverity enum
# ---------------------------------------------------------------------------


class TestDeviationSeverity:
    """Tests for the DeviationSeverity enum."""

    def test_has_normal(self):
        assert DeviationSeverity.NORMAL.value == "normal"

    def test_has_low(self):
        assert DeviationSeverity.LOW.value == "low"

    def test_has_medium(self):
        assert DeviationSeverity.MEDIUM.value == "medium"

    def test_has_high(self):
        assert DeviationSeverity.HIGH.value == "high"

    def test_has_critical(self):
        assert DeviationSeverity.CRITICAL.value == "critical"

    def test_total_member_count(self):
        """All 5 severity levels are defined."""
        assert len(DeviationSeverity) == 5


# ---------------------------------------------------------------------------
# DeviationResult frozen dataclass
# ---------------------------------------------------------------------------


class TestDeviationResult:
    """Tests for the DeviationResult frozen dataclass."""

    @pytest.fixture
    def result(self, now_utc) -> DeviationResult:
        return DeviationResult(
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            current_value=50.0,
            baseline_mean=10.0,
            baseline_std_dev=2.0,
            z_score=20.0,
            is_outlier_zscore=True,
            is_outlier_iqr=True,
            severity=DeviationSeverity.CRITICAL,
            window=MetricWindow.HOUR_1,
            timestamp=now_utc,
            tool_name="deploy",
            explanation="Very anomalous",
        )

    def test_creation(self, result):
        assert result.agent_id == "coder-agent"
        assert result.severity == DeviationSeverity.CRITICAL
        assert result.z_score == 20.0
        assert result.tool_name == "deploy"

    def test_frozen_immutability(self, result):
        with pytest.raises(AttributeError):
            result.severity = DeviationSeverity.NORMAL  # type: ignore[misc]

    def test_to_dict_serialization(self, result, now_utc):
        d = result.to_dict()
        assert d["agent_id"] == "coder-agent"
        assert d["metric_type"] == "tool_call_frequency"
        assert d["severity"] == "critical"
        assert d["window"] == 1
        assert d["timestamp"] == now_utc.isoformat()
        assert d["tool_name"] == "deploy"
        assert d["explanation"] == "Very anomalous"
        assert d["is_outlier_zscore"] is True
        assert d["is_outlier_iqr"] is True

    def test_default_optional_fields(self, now_utc):
        """Default tool_name and explanation are None / empty."""
        r = DeviationResult(
            agent_id="a",
            metric_type=MetricType.ERROR_RATE,
            current_value=0.0,
            baseline_mean=0.0,
            baseline_std_dev=0.0,
            z_score=0.0,
            is_outlier_zscore=False,
            is_outlier_iqr=False,
            severity=DeviationSeverity.NORMAL,
            window=MetricWindow.HOUR_1,
            timestamp=now_utc,
        )
        assert r.tool_name is None
        assert r.explanation == ""


# ---------------------------------------------------------------------------
# BehavioralProfile frozen dataclass
# ---------------------------------------------------------------------------


class TestBehavioralProfile:
    """Tests for the BehavioralProfile frozen dataclass."""

    @pytest.fixture
    def profile(self, now_utc):
        from src.services.runtime_security.baselines.metrics import BaselineMetric

        bl = BaselineMetric(
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            window=MetricWindow.HOUR_1,
            mean=10.0,
            std_dev=2.0,
            median=10.0,
            p25=8.0,
            p75=12.0,
            p95=14.0,
            min_value=6.0,
            max_value=16.0,
            sample_count=50,
            computed_at=now_utc,
        )
        bl2 = BaselineMetric(
            agent_id="coder-agent",
            metric_type=MetricType.TOKEN_CONSUMPTION,
            window=MetricWindow.HOUR_24,
            mean=500.0,
            std_dev=50.0,
            median=510.0,
            p25=470.0,
            p75=530.0,
            p95=580.0,
            min_value=400.0,
            max_value=600.0,
            sample_count=30,
            computed_at=now_utc,
        )
        return BehavioralProfile(
            agent_id="coder-agent",
            baselines=(bl, bl2),
            computed_at=now_utc,
            data_points_used=80,
            windows_computed=(MetricWindow.HOUR_1, MetricWindow.HOUR_24),
        )

    def test_creation(self, profile):
        assert profile.agent_id == "coder-agent"
        assert profile.data_points_used == 80

    def test_frozen_immutability(self, profile):
        with pytest.raises(AttributeError):
            profile.agent_id = "other"  # type: ignore[misc]

    def test_metric_count(self, profile):
        assert profile.metric_count == 2

    def test_get_baseline_found(self, profile):
        bl = profile.get_baseline(MetricType.TOOL_CALL_FREQUENCY, MetricWindow.HOUR_1)
        assert bl is not None
        assert bl.mean == 10.0

    def test_get_baseline_not_found(self, profile):
        bl = profile.get_baseline(MetricType.ERROR_RATE, MetricWindow.HOUR_1)
        assert bl is None

    def test_get_baseline_wrong_window(self, profile):
        """Correct metric type but wrong window returns None."""
        bl = profile.get_baseline(MetricType.TOOL_CALL_FREQUENCY, MetricWindow.DAY_7)
        assert bl is None

    def test_to_dict_serialization(self, profile, now_utc):
        d = profile.to_dict()
        assert d["agent_id"] == "coder-agent"
        assert d["data_points_used"] == 80
        assert d["metric_count"] == 2
        assert len(d["baselines"]) == 2
        assert d["computed_at"] == now_utc.isoformat()
        assert set(d["windows_computed"]) == {1, 24}


# ---------------------------------------------------------------------------
# Recording data points
# ---------------------------------------------------------------------------


class TestRecord:
    """Tests for recording data points into the engine."""

    def test_single_record_increments_count(self, engine, sample_data_point):
        assert engine.record_count == 0
        engine.record(sample_data_point)
        assert engine.record_count == 1

    def test_batch_recording(self, engine, now_utc):
        points = [
            MetricDataPoint(
                agent_id="a",
                metric_type=MetricType.ERROR_RATE,
                value=float(i),
                timestamp=now_utc,
                window=MetricWindow.HOUR_1,
            )
            for i in range(5)
        ]
        count = engine.record_batch(points)
        assert count == 5
        assert engine.record_count == 5

    def test_agent_count_increases(self, engine, now_utc):
        assert engine.agent_count == 0
        engine.record(
            MetricDataPoint(
                agent_id="agent-1",
                metric_type=MetricType.ERROR_RATE,
                value=1.0,
                timestamp=now_utc,
                window=MetricWindow.HOUR_1,
            )
        )
        assert engine.agent_count == 1
        engine.record(
            MetricDataPoint(
                agent_id="agent-2",
                metric_type=MetricType.ERROR_RATE,
                value=2.0,
                timestamp=now_utc,
                window=MetricWindow.HOUR_1,
            )
        )
        assert engine.agent_count == 2

    def test_batch_returns_length(self, engine, now_utc):
        """record_batch returns the number of items recorded."""
        points = [
            MetricDataPoint(
                agent_id="a",
                metric_type=MetricType.TOKEN_CONSUMPTION,
                value=100.0,
                timestamp=now_utc,
                window=MetricWindow.HOUR_1,
            )
        ]
        assert engine.record_batch(points) == 1

    def test_empty_batch(self, engine):
        """Recording an empty batch is a no-op."""
        assert engine.record_batch([]) == 0
        assert engine.record_count == 0


# ---------------------------------------------------------------------------
# Computing profiles
# ---------------------------------------------------------------------------


class TestComputeProfile:
    """Tests for compute_profile."""

    def test_insufficient_samples_returns_empty(self, engine, now_utc):
        """With fewer than min_samples, baselines list is empty."""
        # Only 2 points, but min_samples=3
        for v in [10.0, 12.0]:
            engine.record(
                MetricDataPoint(
                    agent_id="sparse-agent",
                    metric_type=MetricType.TOOL_CALL_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        profile = engine.compute_profile("sparse-agent")
        assert profile.metric_count == 0
        assert profile.data_points_used == 0

    def test_sufficient_samples_computes_correctly(self, engine, now_utc):
        """With min_samples met, baselines contain correct statistics."""
        values = [10.0, 12.0, 14.0, 11.0, 13.0]
        for v in values:
            engine.record(
                MetricDataPoint(
                    agent_id="test-agent",
                    metric_type=MetricType.TOOL_CALL_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        profile = engine.compute_profile("test-agent")
        assert profile.metric_count == 1
        bl = profile.baselines[0]
        assert bl.sample_count == 5
        assert bl.mean == pytest.approx(12.0)
        assert bl.min_value == pytest.approx(10.0)
        assert bl.max_value == pytest.approx(14.0)

    def test_multiple_metric_types(self, populated_engine):
        """Profile contains baselines for each metric type recorded."""
        profile = populated_engine.get_profile("coder-agent")
        assert profile is not None
        # coder-agent has TOOL_CALL_FREQUENCY (HOUR_1 + DAY_7), TOKEN_CONSUMPTION, ERROR_RATE
        assert profile.metric_count >= 3

    def test_multiple_windows(self, populated_engine):
        """Profile computed across different windows."""
        profile = populated_engine.get_profile("coder-agent")
        assert profile is not None
        windows = {bl.window for bl in profile.baselines}
        assert MetricWindow.HOUR_1 in windows
        assert MetricWindow.DAY_7 in windows

    def test_profile_cached(self, engine, now_utc):
        """Computed profile is stored in _profiles cache."""
        for v in [1.0, 2.0, 3.0]:
            engine.record(
                MetricDataPoint(
                    agent_id="cached-agent",
                    metric_type=MetricType.RESPONSE_LATENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        engine.compute_profile("cached-agent")
        assert engine.get_profile("cached-agent") is not None
        assert engine.profile_count == 1

    def test_profile_for_unknown_agent(self, engine):
        """Profile for unknown agent has zero baselines."""
        profile = engine.compute_profile("nonexistent")
        assert profile.metric_count == 0
        assert profile.data_points_used == 0

    def test_data_points_used_accumulates(self, engine, now_utc):
        """data_points_used reflects total points across all baselines."""
        for v in [1.0, 2.0, 3.0, 4.0]:
            engine.record(
                MetricDataPoint(
                    agent_id="multi",
                    metric_type=MetricType.ERROR_RATE,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        for v in [10.0, 20.0, 30.0]:
            engine.record(
                MetricDataPoint(
                    agent_id="multi",
                    metric_type=MetricType.TOKEN_CONSUMPTION,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        profile = engine.compute_profile("multi")
        # ERROR_RATE has 4 >= 3 (included), TOKEN_CONSUMPTION has 3 >= 3 (included)
        assert profile.data_points_used == 7


# ---------------------------------------------------------------------------
# Deviation checking
# ---------------------------------------------------------------------------


class TestCheckDeviation:
    """Tests for check_deviation scoring and severity classification."""

    def test_insufficient_baseline_returns_normal(self, engine, now_utc):
        """No baseline data yields NORMAL severity."""
        result = engine.check_deviation(
            agent_id="unknown-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=999.0,
        )
        assert result.severity == DeviationSeverity.NORMAL
        assert "Insufficient" in result.explanation

    def test_normal_value_returns_normal(self, populated_engine):
        """Value within 1 std dev is NORMAL."""
        result = populated_engine.check_deviation(
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=12.0,
            window=MetricWindow.HOUR_1,
        )
        assert result.severity == DeviationSeverity.NORMAL

    def test_zscore_2_returns_low(self, populated_engine):
        """z-score >= 2.0 returns LOW severity."""
        profile = populated_engine.get_profile("coder-agent")
        bl = profile.get_baseline(MetricType.TOOL_CALL_FREQUENCY, MetricWindow.HOUR_1)
        # Target z = 2.0 -> value = mean + 2.0 * std_dev
        value = bl.mean + 2.0 * bl.std_dev
        result = populated_engine.check_deviation(
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=value,
            window=MetricWindow.HOUR_1,
        )
        assert result.severity == DeviationSeverity.LOW

    def test_zscore_2_5_returns_medium(self, populated_engine):
        """z-score >= 2.5 returns MEDIUM severity."""
        profile = populated_engine.get_profile("coder-agent")
        bl = profile.get_baseline(MetricType.TOOL_CALL_FREQUENCY, MetricWindow.HOUR_1)
        value = bl.mean + 2.5 * bl.std_dev
        result = populated_engine.check_deviation(
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=value,
            window=MetricWindow.HOUR_1,
        )
        assert result.severity == DeviationSeverity.MEDIUM

    def test_zscore_3_returns_high(self, populated_engine):
        """z-score >= 3.0 returns HIGH severity."""
        profile = populated_engine.get_profile("coder-agent")
        bl = profile.get_baseline(MetricType.TOOL_CALL_FREQUENCY, MetricWindow.HOUR_1)
        value = bl.mean + 3.0 * bl.std_dev
        result = populated_engine.check_deviation(
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=value,
            window=MetricWindow.HOUR_1,
        )
        assert result.severity == DeviationSeverity.HIGH

    def test_zscore_4_returns_critical(self, populated_engine):
        """z-score >= 4.0 returns CRITICAL severity."""
        profile = populated_engine.get_profile("coder-agent")
        bl = profile.get_baseline(MetricType.TOOL_CALL_FREQUENCY, MetricWindow.HOUR_1)
        value = bl.mean + 4.0 * bl.std_dev
        result = populated_engine.check_deviation(
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=value,
            window=MetricWindow.HOUR_1,
        )
        assert result.severity == DeviationSeverity.CRITICAL

    def test_explanation_includes_value_and_mean(self, populated_engine):
        """Explanation string contains the current value and baseline mean."""
        profile = populated_engine.get_profile("coder-agent")
        bl = profile.get_baseline(MetricType.TOOL_CALL_FREQUENCY, MetricWindow.HOUR_1)
        extreme_value = bl.mean + 5.0 * bl.std_dev
        result = populated_engine.check_deviation(
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=extreme_value,
            window=MetricWindow.HOUR_1,
        )
        assert f"{extreme_value:.2f}" in result.explanation
        assert f"{bl.mean:.2f}" in result.explanation

    def test_normal_explanation_format(self, populated_engine):
        """Normal result explanation mentions 'within normal range'."""
        result = populated_engine.check_deviation(
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=12.0,
            window=MetricWindow.HOUR_1,
        )
        assert "within normal range" in result.explanation

    def test_tool_specific_baselines(self, engine, now_utc):
        """Deviation check works with tool_name-specific baselines."""
        for v in [10.0, 12.0, 14.0, 11.0, 13.0]:
            engine.record(
                MetricDataPoint(
                    agent_id="tool-agent",
                    metric_type=MetricType.TOOL_CALL_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                    tool_name="semantic_search",
                )
            )
        engine.compute_profile("tool-agent")
        result = engine.check_deviation(
            agent_id="tool-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=12.0,
            window=MetricWindow.HOUR_1,
            tool_name="semantic_search",
        )
        assert result.severity == DeviationSeverity.NORMAL
        assert result.tool_name == "semantic_search"

    def test_negative_zscore_severity(self, populated_engine):
        """Negative deviation (value far below mean) also triggers severity."""
        profile = populated_engine.get_profile("coder-agent")
        bl = profile.get_baseline(MetricType.TOOL_CALL_FREQUENCY, MetricWindow.HOUR_1)
        # Very low value
        value = bl.mean - 4.0 * bl.std_dev
        result = populated_engine.check_deviation(
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=value,
            window=MetricWindow.HOUR_1,
        )
        assert result.severity == DeviationSeverity.CRITICAL

    def test_auto_computes_profile_if_missing(self, engine, now_utc):
        """check_deviation auto-computes profile if not yet cached."""
        for v in [10.0, 12.0, 14.0]:
            engine.record(
                MetricDataPoint(
                    agent_id="auto-agent",
                    metric_type=MetricType.ERROR_RATE,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        # No explicit compute_profile call
        result = engine.check_deviation(
            agent_id="auto-agent",
            metric_type=MetricType.ERROR_RATE,
            value=12.0,
            window=MetricWindow.HOUR_1,
        )
        assert result.severity == DeviationSeverity.NORMAL
        # Profile is now cached
        assert engine.get_profile("auto-agent") is not None


# ---------------------------------------------------------------------------
# Check all deviations
# ---------------------------------------------------------------------------


class TestCheckAllDeviations:
    """Tests for check_all_deviations across multiple metrics."""

    def test_returns_results_for_all_metrics(self, populated_engine):
        """Returns one result per metric type provided."""
        metrics = {
            MetricType.TOOL_CALL_FREQUENCY: 12.0,
            MetricType.TOKEN_CONSUMPTION: 510.0,
        }
        results = populated_engine.check_all_deviations(
            agent_id="coder-agent",
            current_metrics=metrics,
            window=MetricWindow.HOUR_1,
        )
        assert len(results) == 2

    def test_sorted_by_severity_critical_first(self, populated_engine):
        """Results are sorted with highest severity first."""
        profile = populated_engine.get_profile("coder-agent")
        bl_tool = profile.get_baseline(
            MetricType.TOOL_CALL_FREQUENCY, MetricWindow.HOUR_1
        )
        bl_token = profile.get_baseline(
            MetricType.TOKEN_CONSUMPTION, MetricWindow.HOUR_1
        )

        metrics = {
            # Normal value
            MetricType.TOOL_CALL_FREQUENCY: bl_tool.mean,
            # Extreme value for CRITICAL
            MetricType.TOKEN_CONSUMPTION: bl_token.mean + 5.0 * bl_token.std_dev,
        }
        results = populated_engine.check_all_deviations(
            agent_id="coder-agent",
            current_metrics=metrics,
            window=MetricWindow.HOUR_1,
        )
        # First result should have higher severity
        severities = [r.severity for r in results]
        assert severities[0] != DeviationSeverity.NORMAL or all(
            s == DeviationSeverity.NORMAL for s in severities
        )

    def test_empty_metrics_returns_empty(self, populated_engine):
        """Empty metrics dict returns empty results list."""
        results = populated_engine.check_all_deviations(
            agent_id="coder-agent",
            current_metrics={},
        )
        assert results == []


# ---------------------------------------------------------------------------
# Singleton lifecycle
# ---------------------------------------------------------------------------


class TestSingleton:
    """Tests for singleton get/reset pattern."""

    def test_get_returns_same_instance(self):
        """get_baseline_engine returns the same instance on repeated calls."""
        e1 = get_baseline_engine()
        e2 = get_baseline_engine()
        assert e1 is e2

    def test_reset_creates_new_instance(self):
        """reset_baseline_engine clears the singleton so next get creates new."""
        e1 = get_baseline_engine()
        reset_baseline_engine()
        e2 = get_baseline_engine()
        assert e1 is not e2

    def test_reset_does_not_raise_when_none(self):
        """reset works even when singleton was never created."""
        reset_baseline_engine()
        reset_baseline_engine()  # second reset should not raise

    def test_fresh_engine_has_zero_state(self):
        """Newly created singleton has no data."""
        reset_baseline_engine()
        e = get_baseline_engine()
        assert e.record_count == 0
        assert e.agent_count == 0
        assert e.profile_count == 0
