"""
Tests for behavioral baseline metrics (ADR-083 Phase 2).

Covers MetricType, MetricWindow, MetricDataPoint, and BaselineMetric
frozen dataclasses, serialization, and statistical property computation.
"""

import math
from datetime import datetime, timezone

import pytest

from src.services.runtime_security.baselines.metrics import (
    BaselineMetric,
    MetricDataPoint,
    MetricType,
    MetricWindow,
)

# ---------------------------------------------------------------------------
# MetricType enum
# ---------------------------------------------------------------------------


class TestMetricType:
    """Tests for the MetricType enum."""

    def test_has_tool_call_frequency(self):
        assert MetricType.TOOL_CALL_FREQUENCY.value == "tool_call_frequency"

    def test_has_token_consumption(self):
        assert MetricType.TOKEN_CONSUMPTION.value == "token_consumption"

    def test_has_approval_rate(self):
        assert MetricType.APPROVAL_RATE.value == "approval_rate"

    def test_has_error_rate(self):
        assert MetricType.ERROR_RATE.value == "error_rate"

    def test_has_response_latency(self):
        assert MetricType.RESPONSE_LATENCY.value == "response_latency"

    def test_has_agent_communication_frequency(self):
        assert (
            MetricType.AGENT_COMMUNICATION_FREQUENCY.value
            == "agent_communication_frequency"
        )

    def test_has_mcp_server_access_frequency(self):
        assert (
            MetricType.MCP_SERVER_ACCESS_FREQUENCY.value
            == "mcp_server_access_frequency"
        )

    def test_has_unique_tools_used(self):
        assert MetricType.UNIQUE_TOOLS_USED.value == "unique_tools_used"

    def test_has_session_duration(self):
        assert MetricType.SESSION_DURATION.value == "session_duration"

    def test_has_checkpoint_frequency(self):
        assert MetricType.CHECKPOINT_FREQUENCY.value == "checkpoint_frequency"

    def test_total_member_count(self):
        """All 10 metric types are defined."""
        assert len(MetricType) == 10


# ---------------------------------------------------------------------------
# MetricWindow enum
# ---------------------------------------------------------------------------


class TestMetricWindow:
    """Tests for the MetricWindow enum."""

    def test_hour_1_value(self):
        assert MetricWindow.HOUR_1.value == 1

    def test_hour_24_value(self):
        assert MetricWindow.HOUR_24.value == 24

    def test_day_7_value(self):
        assert MetricWindow.DAY_7.value == 168

    def test_total_member_count(self):
        """All 3 time windows are defined."""
        assert len(MetricWindow) == 3


# ---------------------------------------------------------------------------
# MetricDataPoint frozen dataclass
# ---------------------------------------------------------------------------


class TestMetricDataPoint:
    """Tests for the MetricDataPoint frozen dataclass."""

    def test_creation(self, now_utc):
        """Create a data point with required fields."""
        dp = MetricDataPoint(
            agent_id="agent-1",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=42.0,
            timestamp=now_utc,
            window=MetricWindow.HOUR_1,
        )
        assert dp.agent_id == "agent-1"
        assert dp.metric_type == MetricType.TOOL_CALL_FREQUENCY
        assert dp.value == 42.0
        assert dp.timestamp == now_utc
        assert dp.window == MetricWindow.HOUR_1
        assert dp.tool_name is None
        assert dp.metadata == ()

    def test_creation_with_tool_name(self, now_utc):
        """Create a data point with an optional tool_name."""
        dp = MetricDataPoint(
            agent_id="agent-1",
            metric_type=MetricType.TOOL_CALL_FREQUENCY,
            value=10.0,
            timestamp=now_utc,
            window=MetricWindow.HOUR_1,
            tool_name="semantic_search",
        )
        assert dp.tool_name == "semantic_search"

    def test_creation_with_metadata(self, now_utc):
        """Metadata stored as tuple of tuples for immutability."""
        dp = MetricDataPoint(
            agent_id="agent-1",
            metric_type=MetricType.TOKEN_CONSUMPTION,
            value=500.0,
            timestamp=now_utc,
            window=MetricWindow.HOUR_24,
            metadata=(("team", "platform"), ("env", "dev")),
        )
        assert dp.metadata == (("team", "platform"), ("env", "dev"))

    def test_frozen_immutability(self, sample_data_point):
        """Frozen dataclass cannot be mutated."""
        with pytest.raises(AttributeError):
            sample_data_point.value = 99.0  # type: ignore[misc]

    def test_frozen_agent_id(self, sample_data_point):
        """Agent ID cannot be changed after construction."""
        with pytest.raises(AttributeError):
            sample_data_point.agent_id = "other"  # type: ignore[misc]

    def test_to_dict_serialization(self, now_utc):
        """to_dict produces expected keys and values."""
        dp = MetricDataPoint(
            agent_id="agent-1",
            metric_type=MetricType.ERROR_RATE,
            value=0.05,
            timestamp=now_utc,
            window=MetricWindow.DAY_7,
            tool_name="write_file",
            metadata=(("env", "prod"),),
        )
        d = dp.to_dict()
        assert d["agent_id"] == "agent-1"
        assert d["metric_type"] == "error_rate"
        assert d["value"] == 0.05
        assert d["timestamp"] == now_utc.isoformat()
        assert d["window"] == 168
        assert d["tool_name"] == "write_file"
        assert d["metadata"] == {"env": "prod"}

    def test_to_dict_none_tool_name(self, sample_data_point):
        """tool_name serializes as None when not provided."""
        d = sample_data_point.to_dict()
        assert d["tool_name"] is None

    def test_to_dict_empty_metadata(self, sample_data_point):
        """Empty metadata serializes to an empty dict."""
        d = sample_data_point.to_dict()
        assert d["metadata"] == {}


# ---------------------------------------------------------------------------
# BaselineMetric frozen dataclass
# ---------------------------------------------------------------------------


class TestBaselineMetric:
    """Tests for BaselineMetric frozen dataclass and statistical properties."""

    @pytest.fixture
    def baseline(self, now_utc) -> BaselineMetric:
        """Representative baseline metric for property tests."""
        return BaselineMetric(
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
            sample_count=100,
            computed_at=now_utc,
        )

    def test_creation(self, baseline):
        """All fields accessible after creation."""
        assert baseline.agent_id == "coder-agent"
        assert baseline.metric_type == MetricType.TOOL_CALL_FREQUENCY
        assert baseline.window == MetricWindow.HOUR_1
        assert baseline.mean == 10.0
        assert baseline.std_dev == 2.0
        assert baseline.sample_count == 100

    def test_frozen_immutability(self, baseline):
        """Frozen dataclass cannot be mutated."""
        with pytest.raises(AttributeError):
            baseline.mean = 99.0  # type: ignore[misc]

    def test_iqr_property(self, baseline):
        """IQR = p75 - p25."""
        assert baseline.iqr == pytest.approx(4.0)

    def test_lower_fence(self, baseline):
        """Lower fence = p25 - 1.5 * IQR."""
        expected = 8.0 - 1.5 * 4.0  # 2.0
        assert baseline.lower_fence == pytest.approx(expected)

    def test_upper_fence(self, baseline):
        """Upper fence = p75 + 1.5 * IQR."""
        expected = 12.0 + 1.5 * 4.0  # 18.0
        assert baseline.upper_fence == pytest.approx(expected)

    def test_z_score_normal_case(self, baseline):
        """z-score = (value - mean) / std_dev."""
        z = baseline.z_score(14.0)
        assert z == pytest.approx(2.0)

    def test_z_score_negative(self, baseline):
        """Negative z-score for values below the mean."""
        z = baseline.z_score(6.0)
        assert z == pytest.approx(-2.0)

    def test_z_score_zero_std_dev_equal_mean(self, now_utc):
        """When std_dev=0 and value equals mean, z-score is 0."""
        bl = BaselineMetric(
            agent_id="a",
            metric_type=MetricType.ERROR_RATE,
            window=MetricWindow.HOUR_1,
            mean=5.0,
            std_dev=0.0,
            median=5.0,
            p25=5.0,
            p75=5.0,
            p95=5.0,
            min_value=5.0,
            max_value=5.0,
            sample_count=10,
            computed_at=now_utc,
        )
        assert bl.z_score(5.0) == 0.0

    def test_z_score_zero_std_dev_returns_inf(self, now_utc):
        """When std_dev=0 and value differs from mean, z-score is inf."""
        bl = BaselineMetric(
            agent_id="a",
            metric_type=MetricType.ERROR_RATE,
            window=MetricWindow.HOUR_1,
            mean=5.0,
            std_dev=0.0,
            median=5.0,
            p25=5.0,
            p75=5.0,
            p95=5.0,
            min_value=5.0,
            max_value=5.0,
            sample_count=10,
            computed_at=now_utc,
        )
        assert bl.z_score(10.0) == float("inf")

    def test_z_score_value_equals_mean(self, baseline):
        """z-score is 0 when value equals mean and std_dev > 0."""
        assert baseline.z_score(10.0) == pytest.approx(0.0)

    def test_is_outlier_zscore_within_threshold(self, baseline):
        """Value within z-score threshold is not flagged."""
        # z = (12 - 10)/2 = 1.0, default threshold 3.0
        assert baseline.is_outlier_zscore(12.0) is False

    def test_is_outlier_zscore_outside_threshold(self, baseline):
        """Value beyond z-score threshold is flagged."""
        # z = (17 - 10)/2 = 3.5 > default 3.0
        assert baseline.is_outlier_zscore(17.0) is True

    def test_is_outlier_zscore_custom_threshold(self, baseline):
        """Custom threshold changes outlier boundary."""
        # z = (14 - 10)/2 = 2.0 > threshold 1.5
        assert baseline.is_outlier_zscore(14.0, threshold=1.5) is True
        # same value with higher threshold
        assert baseline.is_outlier_zscore(14.0, threshold=3.0) is False

    def test_is_outlier_iqr_within_fences(self, baseline):
        """Value within IQR fences is not an outlier."""
        # fences: [2.0, 18.0], value=10.0
        assert baseline.is_outlier_iqr(10.0) is False

    def test_is_outlier_iqr_above_upper_fence(self, baseline):
        """Value above upper fence is an outlier."""
        assert baseline.is_outlier_iqr(20.0) is True

    def test_is_outlier_iqr_below_lower_fence(self, baseline):
        """Value below lower fence is an outlier."""
        assert baseline.is_outlier_iqr(1.0) is True

    def test_to_dict_serialization(self, baseline):
        """to_dict includes all fields plus computed properties."""
        d = baseline.to_dict()
        assert d["agent_id"] == "coder-agent"
        assert d["metric_type"] == "tool_call_frequency"
        assert d["window"] == 1
        assert d["mean"] == pytest.approx(10.0)
        assert d["std_dev"] == pytest.approx(2.0)
        assert d["sample_count"] == 100
        assert d["tool_name"] is None
        # Computed properties included in dict
        assert d["iqr"] == pytest.approx(4.0)
        assert d["lower_fence"] == pytest.approx(2.0)
        assert d["upper_fence"] == pytest.approx(18.0)

    def test_to_dict_with_tool_name(self, now_utc):
        """tool_name appears in serialized dict when provided."""
        bl = BaselineMetric(
            agent_id="a",
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
            tool_name="read_logs",
        )
        assert bl.to_dict()["tool_name"] == "read_logs"
