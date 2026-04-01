"""
Tests for the Behavioral Drift Detector (ADR-083 Phase 2).

Covers DriftType, DriftAlert, drift detection across windows,
drift severity classification, new behavior detection, drift type
classification, multi-agent detection, and alert tracking.
"""

from datetime import datetime, timezone

import pytest

from src.services.runtime_security.baselines import (
    BehavioralBaselineEngine,
    MetricDataPoint,
    MetricType,
    MetricWindow,
)
from src.services.runtime_security.baselines.baseline_engine import DeviationSeverity
from src.services.runtime_security.baselines.drift_detector import (
    DriftAlert,
    DriftDetector,
    DriftType,
)

# ---------------------------------------------------------------------------
# DriftType enum
# ---------------------------------------------------------------------------


class TestDriftType:
    """Tests for the DriftType enum."""

    def test_has_gradual_increase(self):
        assert DriftType.GRADUAL_INCREASE.value == "gradual_increase"

    def test_has_gradual_decrease(self):
        assert DriftType.GRADUAL_DECREASE.value == "gradual_decrease"

    def test_has_sudden_shift(self):
        assert DriftType.SUDDEN_SHIFT.value == "sudden_shift"

    def test_has_pattern_change(self):
        assert DriftType.PATTERN_CHANGE.value == "pattern_change"

    def test_has_new_behavior(self):
        assert DriftType.NEW_BEHAVIOR.value == "new_behavior"

    def test_total_member_count(self):
        """All 5 drift types are defined."""
        assert len(DriftType) == 5


# ---------------------------------------------------------------------------
# DriftAlert frozen dataclass
# ---------------------------------------------------------------------------


class TestDriftAlert:
    """Tests for the DriftAlert frozen dataclass."""

    @pytest.fixture
    def alert(self, now_utc) -> DriftAlert:
        return DriftAlert(
            alert_id="da-abc123",
            timestamp=now_utc,
            agent_id="coder-agent",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            drift_type=DriftType.GRADUAL_INCREASE,
            severity=DeviationSeverity.HIGH,
            short_window_mean=20.0,
            long_window_mean=10.0,
            drift_magnitude=10.0,
            drift_percentage=100.0,
            explanation="Gradual Increase detected",
            recommended_action="Review agent configuration",
        )

    def test_creation(self, alert):
        assert alert.alert_id == "da-abc123"
        assert alert.agent_id == "coder-agent"
        assert alert.drift_type == DriftType.GRADUAL_INCREASE
        assert alert.severity == DeviationSeverity.HIGH

    def test_frozen_immutability(self, alert):
        with pytest.raises(AttributeError):
            alert.severity = DeviationSeverity.LOW  # type: ignore[misc]

    def test_to_dict_serialization(self, alert, now_utc):
        d = alert.to_dict()
        assert d["alert_id"] == "da-abc123"
        assert d["timestamp"] == now_utc.isoformat()
        assert d["agent_id"] == "coder-agent"
        assert d["metric_type"] == "tool_call_frequency"
        assert d["drift_type"] == "gradual_increase"
        assert d["severity"] == "high"
        assert d["short_window_mean"] == pytest.approx(20.0)
        assert d["long_window_mean"] == pytest.approx(10.0)
        assert d["drift_magnitude"] == pytest.approx(10.0)
        assert d["drift_percentage"] == pytest.approx(100.0)
        assert "Gradual Increase" in d["explanation"]
        assert "Review" in d["recommended_action"]


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


class TestDetectDrift:
    """Tests for DriftDetector.detect_drift."""

    def test_no_data_returns_empty(self, engine):
        """Agent with no data produces no drift alerts."""
        detector = DriftDetector(engine=engine)
        alerts = detector.detect_drift("nonexistent-agent")
        assert alerts == []

    def test_no_drift_when_short_approx_long(self, now_utc):
        """No alerts when short-window and long-window means are similar."""
        eng = BehavioralBaselineEngine(min_samples=3)
        # Same values for both windows
        for v in [10.0, 10.5, 9.5, 10.0, 10.2]:
            eng.record(
                MetricDataPoint(
                    agent_id="stable",
                    metric_type=MetricType.TOOL_CALL_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
            eng.record(
                MetricDataPoint(
                    agent_id="stable",
                    metric_type=MetricType.TOOL_CALL_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.DAY_7,
                )
            )
        eng.compute_profile("stable")
        detector = DriftDetector(engine=eng)
        alerts = detector.detect_drift("stable")
        assert alerts == []

    def test_low_drift_at_25_percent(self, now_utc):
        """25%+ drift between windows triggers LOW severity."""
        eng = BehavioralBaselineEngine(min_samples=3)
        for v in [12.5, 12.6, 12.4, 12.5, 12.5]:
            eng.record(
                MetricDataPoint(
                    agent_id="drifty",
                    metric_type=MetricType.TOOL_CALL_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        for v in [10.0, 10.0, 10.0, 10.0, 10.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="drifty",
                    metric_type=MetricType.TOOL_CALL_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.DAY_7,
                )
            )
        eng.compute_profile("drifty")
        detector = DriftDetector(engine=eng)
        alerts = detector.detect_drift("drifty")
        assert len(alerts) >= 1
        assert any(a.severity == DeviationSeverity.LOW for a in alerts)

    def test_medium_drift_at_50_percent(self, now_utc):
        """50%+ drift triggers MEDIUM severity."""
        eng = BehavioralBaselineEngine(min_samples=3)
        for v in [15.0, 15.1, 14.9]:
            eng.record(
                MetricDataPoint(
                    agent_id="drifty",
                    metric_type=MetricType.ERROR_RATE,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        for v in [10.0, 10.0, 10.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="drifty",
                    metric_type=MetricType.ERROR_RATE,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.DAY_7,
                )
            )
        eng.compute_profile("drifty")
        detector = DriftDetector(engine=eng)
        alerts = detector.detect_drift("drifty")
        severities = {a.severity for a in alerts}
        assert (
            DeviationSeverity.MEDIUM in severities
            or DeviationSeverity.HIGH in severities
        )

    def test_high_drift_at_100_percent(self, now_utc):
        """100%+ drift triggers HIGH severity."""
        eng = BehavioralBaselineEngine(min_samples=3)
        for v in [20.0, 20.0, 20.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="drifty",
                    metric_type=MetricType.TOKEN_CONSUMPTION,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        for v in [10.0, 10.0, 10.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="drifty",
                    metric_type=MetricType.TOKEN_CONSUMPTION,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.DAY_7,
                )
            )
        eng.compute_profile("drifty")
        detector = DriftDetector(engine=eng)
        alerts = detector.detect_drift("drifty")
        severities = {a.severity for a in alerts}
        assert (
            DeviationSeverity.HIGH in severities
            or DeviationSeverity.CRITICAL in severities
        )

    def test_critical_drift_at_200_percent(self, now_utc):
        """200%+ drift triggers CRITICAL severity."""
        eng = BehavioralBaselineEngine(min_samples=3)
        for v in [30.0, 30.0, 30.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="drifty",
                    metric_type=MetricType.RESPONSE_LATENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        for v in [10.0, 10.0, 10.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="drifty",
                    metric_type=MetricType.RESPONSE_LATENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.DAY_7,
                )
            )
        eng.compute_profile("drifty")
        detector = DriftDetector(engine=eng)
        alerts = detector.detect_drift("drifty")
        severities = {a.severity for a in alerts}
        assert DeviationSeverity.CRITICAL in severities

    def test_new_behavior_detection(self, now_utc):
        """Metric in short window but missing from long window triggers NEW_BEHAVIOR."""
        eng = BehavioralBaselineEngine(min_samples=3)
        # Only short window data, no long window
        for v in [5.0, 6.0, 7.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="new-behavior",
                    metric_type=MetricType.MCP_SERVER_ACCESS_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        eng.compute_profile("new-behavior")
        detector = DriftDetector(engine=eng)
        alerts = detector.detect_drift("new-behavior")
        assert len(alerts) >= 1
        assert any(a.drift_type == DriftType.NEW_BEHAVIOR for a in alerts)

    def test_drift_type_gradual_increase(self, now_utc):
        """Gradual increase is classified correctly.

        Requirements for GRADUAL_INCREASE:
          - short_std_dev <= long_std_dev * 2  (not PATTERN_CHANGE)
          - abs(diff) <= long_std_dev * 3      (not SUDDEN_SHIFT)
          - diff > 0                           (increase, not decrease)
          - drift_pct >= 0.25                  (at least LOW severity alert)

        Using long values [8, 10, 12, 10, 10] -> mean=10, std_dev~=1.41
        Short values [13.0, 13.0, 13.0] -> mean=13, std_dev=0
        diff = 3.0, 3*1.41 = 4.24 -> diff < 4.24 => GRADUAL_INCREASE
        drift_pct = 3.0/10.0 = 0.30 >= 0.25 => LOW alert
        """
        eng = BehavioralBaselineEngine(min_samples=3)
        for v in [13.0, 13.0, 13.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="grad",
                    metric_type=MetricType.TOOL_CALL_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        for v in [8.0, 10.0, 12.0, 10.0, 10.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="grad",
                    metric_type=MetricType.TOOL_CALL_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.DAY_7,
                )
            )
        eng.compute_profile("grad")
        detector = DriftDetector(engine=eng)
        alerts = detector.detect_drift("grad")
        increase_alerts = [
            a for a in alerts if a.drift_type == DriftType.GRADUAL_INCREASE
        ]
        assert len(increase_alerts) >= 1

    def test_drift_type_gradual_decrease(self, now_utc):
        """Gradual decrease is classified correctly.

        Requirements for GRADUAL_DECREASE:
          - short_std_dev <= long_std_dev * 2  (not PATTERN_CHANGE)
          - abs(diff) <= long_std_dev * 3      (not SUDDEN_SHIFT)
          - diff < 0                           (decrease, not increase)
          - drift_pct >= 0.25                  (at least LOW severity alert)

        Using long values [8, 10, 12, 10, 10] -> mean=10, std_dev~=1.41
        Short values [7.0, 7.0, 7.0] -> mean=7, std_dev=0
        diff = -3.0, 3*1.41 = 4.24 -> |diff| < 4.24 => GRADUAL_DECREASE
        drift_pct = 3.0/10.0 = 0.30 >= 0.25 => LOW alert
        """
        eng = BehavioralBaselineEngine(min_samples=3)
        for v in [7.0, 7.0, 7.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="dec",
                    metric_type=MetricType.APPROVAL_RATE,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        for v in [8.0, 10.0, 12.0, 10.0, 10.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="dec",
                    metric_type=MetricType.APPROVAL_RATE,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.DAY_7,
                )
            )
        eng.compute_profile("dec")
        detector = DriftDetector(engine=eng)
        alerts = detector.detect_drift("dec")
        decrease_alerts = [
            a for a in alerts if a.drift_type == DriftType.GRADUAL_DECREASE
        ]
        assert len(decrease_alerts) >= 1

    def test_drift_type_pattern_change(self, now_utc):
        """High short-window variance relative to long-window triggers PATTERN_CHANGE.

        Requirements for PATTERN_CHANGE:
          - short_std_dev > long_std_dev * 2
          - drift_pct >= 0.25 (alert must be generated)

        Using short values [2.0, 20.0, 2.0] -> mean=8.0, std_dev~=10.39
        Long values [10.0, 10.5, 10.0, 9.5, 10.0] -> mean=10.0, std_dev~=0.35
        short_std_dev(10.39) > long_std_dev(0.35)*2 = 0.71 => PATTERN_CHANGE
        drift_pct = |8.0 - 10.0|/10.0 = 0.20 -- need higher short mean diff

        Adjust: short values [2.0, 25.0, 2.0] -> mean=9.67 -- still only 3.3%
        Better: short [3.0, 20.0, 3.0] mean=8.67, diff=1.33, pct=0.133
        Need bigger gap. short [2.0, 20.0, 2.0, 20.0, 2.0] mean=9.2, close to 10

        Solution: shift means apart. long mean ~= 10, short mean ~= 14
        short [4.0, 24.0, 4.0, 24.0, 14.0] mean=14, std_dev~=9.80
        drift_pct = 4/10 = 0.40 >= 0.25 => MEDIUM alert
        short_std(9.80) > long_std(0.35)*2 => PATTERN_CHANGE
        """
        eng = BehavioralBaselineEngine(min_samples=3)
        # Short window: high variance, mean shifted from long
        for v in [4.0, 24.0, 4.0, 24.0, 14.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="pattern",
                    metric_type=MetricType.SESSION_DURATION,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        # Long window: low variance around 10
        for v in [10.0, 10.5, 10.0, 9.5, 10.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="pattern",
                    metric_type=MetricType.SESSION_DURATION,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.DAY_7,
                )
            )
        eng.compute_profile("pattern")
        detector = DriftDetector(engine=eng)
        alerts = detector.detect_drift("pattern")
        pattern_alerts = [a for a in alerts if a.drift_type == DriftType.PATTERN_CHANGE]
        assert len(pattern_alerts) >= 1

    def test_drift_sorted_by_severity(self, now_utc):
        """Returned alerts are sorted with highest severity first."""
        eng = BehavioralBaselineEngine(min_samples=3)
        # Two metrics with different drift magnitudes
        for v in [30.0, 30.0, 30.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="sorted",
                    metric_type=MetricType.TOOL_CALL_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        for v in [10.0, 10.0, 10.0, 10.0, 10.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="sorted",
                    metric_type=MetricType.TOOL_CALL_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.DAY_7,
                )
            )
        # Only short-window data for second metric -> NEW_BEHAVIOR (MEDIUM)
        for v in [5.0, 5.0, 5.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="sorted",
                    metric_type=MetricType.CHECKPOINT_FREQUENCY,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        eng.compute_profile("sorted")
        detector = DriftDetector(engine=eng)
        alerts = detector.detect_drift("sorted")
        if len(alerts) >= 2:
            for i in range(len(alerts) - 1):
                rank_cur = detector._severity_rank(alerts[i].severity)
                rank_next = detector._severity_rank(alerts[i + 1].severity)
                assert rank_cur >= rank_next


# ---------------------------------------------------------------------------
# Multi-agent drift detection
# ---------------------------------------------------------------------------


class TestDetectDriftAllAgents:
    """Tests for detect_drift_all_agents."""

    def test_returns_alerts_across_agents(self, now_utc):
        """detect_drift_all_agents checks all profiled agents."""
        eng = BehavioralBaselineEngine(min_samples=3)

        for agent_id, short_val, long_val in [
            ("agent-a", 30.0, 10.0),  # 200% drift -> CRITICAL
            ("agent-b", 15.0, 10.0),  # 50% drift -> MEDIUM
        ]:
            for v in [short_val] * 3:
                eng.record(
                    MetricDataPoint(
                        agent_id=agent_id,
                        metric_type=MetricType.ERROR_RATE,
                        value=v,
                        timestamp=now_utc,
                        window=MetricWindow.HOUR_1,
                    )
                )
            for v in [long_val] * 3:
                eng.record(
                    MetricDataPoint(
                        agent_id=agent_id,
                        metric_type=MetricType.ERROR_RATE,
                        value=v,
                        timestamp=now_utc,
                        window=MetricWindow.DAY_7,
                    )
                )
            eng.compute_profile(agent_id)

        detector = DriftDetector(engine=eng)
        alerts = detector.detect_drift_all_agents()
        agent_ids = {a.agent_id for a in alerts}
        assert "agent-a" in agent_ids
        assert "agent-b" in agent_ids

    def test_empty_engine_returns_empty(self, engine):
        """No profiled agents yields no alerts."""
        detector = DriftDetector(engine=engine)
        assert detector.detect_drift_all_agents() == []


# ---------------------------------------------------------------------------
# Alert tracking
# ---------------------------------------------------------------------------


class TestAlertTracking:
    """Tests for alert accumulation and retrieval."""

    def test_alerts_accumulate(self, now_utc):
        """detect_drift appends alerts to internal list."""
        eng = BehavioralBaselineEngine(min_samples=3)
        for v in [30.0, 30.0, 30.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="tracked",
                    metric_type=MetricType.ERROR_RATE,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        for v in [10.0, 10.0, 10.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="tracked",
                    metric_type=MetricType.ERROR_RATE,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.DAY_7,
                )
            )
        eng.compute_profile("tracked")
        detector = DriftDetector(engine=eng)

        alerts_round1 = detector.detect_drift("tracked")
        count_after_r1 = detector.total_alerts
        assert count_after_r1 == len(alerts_round1)

        # Second call adds more alerts
        alerts_round2 = detector.detect_drift("tracked")
        assert detector.total_alerts == count_after_r1 + len(alerts_round2)

    def test_get_alerts_for_agent_filters(self, now_utc):
        """get_alerts_for_agent returns only that agent's alerts."""
        eng = BehavioralBaselineEngine(min_samples=3)

        for agent_id in ["alpha", "beta"]:
            for v in [20.0, 20.0, 20.0]:
                eng.record(
                    MetricDataPoint(
                        agent_id=agent_id,
                        metric_type=MetricType.TOOL_CALL_FREQUENCY,
                        value=v,
                        timestamp=now_utc,
                        window=MetricWindow.HOUR_1,
                    )
                )
            for v in [10.0, 10.0, 10.0]:
                eng.record(
                    MetricDataPoint(
                        agent_id=agent_id,
                        metric_type=MetricType.TOOL_CALL_FREQUENCY,
                        value=v,
                        timestamp=now_utc,
                        window=MetricWindow.DAY_7,
                    )
                )
            eng.compute_profile(agent_id)

        detector = DriftDetector(engine=eng)
        detector.detect_drift("alpha")
        detector.detect_drift("beta")

        alpha_alerts = detector.get_alerts_for_agent("alpha")
        beta_alerts = detector.get_alerts_for_agent("beta")

        assert all(a.agent_id == "alpha" for a in alpha_alerts)
        assert all(a.agent_id == "beta" for a in beta_alerts)

    def test_total_alerts_property(self, now_utc):
        """total_alerts matches len of get_all_alerts."""
        eng = BehavioralBaselineEngine(min_samples=3)
        for v in [30.0, 30.0, 30.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="counted",
                    metric_type=MetricType.ERROR_RATE,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        for v in [10.0, 10.0, 10.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="counted",
                    metric_type=MetricType.ERROR_RATE,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.DAY_7,
                )
            )
        eng.compute_profile("counted")
        detector = DriftDetector(engine=eng)
        detector.detect_drift("counted")
        assert detector.total_alerts == len(detector.get_all_alerts())

    def test_get_all_alerts_returns_copy(self, now_utc):
        """get_all_alerts returns a new list, not the internal one."""
        eng = BehavioralBaselineEngine(min_samples=3)
        for v in [25.0, 25.0, 25.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="copy-check",
                    metric_type=MetricType.TOKEN_CONSUMPTION,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.HOUR_1,
                )
            )
        for v in [10.0, 10.0, 10.0]:
            eng.record(
                MetricDataPoint(
                    agent_id="copy-check",
                    metric_type=MetricType.TOKEN_CONSUMPTION,
                    value=v,
                    timestamp=now_utc,
                    window=MetricWindow.DAY_7,
                )
            )
        eng.compute_profile("copy-check")
        detector = DriftDetector(engine=eng)
        detector.detect_drift("copy-check")
        alerts = detector.get_all_alerts()
        original_count = detector.total_alerts
        alerts.clear()  # Mutate the returned list
        assert detector.total_alerts == original_count

    def test_no_alerts_for_unknown_agent(self):
        """get_alerts_for_agent returns empty for unknown agent."""
        eng = BehavioralBaselineEngine(min_samples=3)
        detector = DriftDetector(engine=eng)
        assert detector.get_alerts_for_agent("ghost") == []
