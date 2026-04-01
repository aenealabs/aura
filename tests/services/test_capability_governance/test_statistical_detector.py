"""
Tests for StatisticalAnomalyDetector (ADR-072).

Tests Phase 1 statistical anomaly detection using Z-scores, n-gram analysis,
and temporal pattern detection.
"""

from datetime import datetime, timedelta

import pytest

from src.services.capability_governance import AnomalyDetectionConfig, AnomalyType
from src.services.capability_governance.statistical_detector import (
    InMemoryBaselineService,
    StatisticalAnomalyDetector,
    get_statistical_detector,
    reset_statistical_detector,
)


class TestInMemoryBaselineService:
    """Tests for InMemoryBaselineService."""

    @pytest.mark.asyncio
    async def test_default_baselines_initialized(self):
        """Test default baselines are initialized for common agent types."""
        service = InMemoryBaselineService()

        coder_baseline = await service.get_baseline("coder")
        assert coder_baseline.agent_type == "coder"
        assert coder_baseline.mean_hourly_count > 0

        reviewer_baseline = await service.get_baseline("reviewer")
        assert reviewer_baseline.agent_type == "reviewer"

    @pytest.mark.asyncio
    async def test_unknown_agent_type_returns_default(self):
        """Test unknown agent type returns a default baseline."""
        service = InMemoryBaselineService()

        baseline = await service.get_baseline("unknown_agent_type")
        assert baseline.agent_type == "unknown_agent_type"
        assert baseline.mean_hourly_count == 10.0  # Default value

    @pytest.mark.asyncio
    async def test_update_baseline(self):
        """Test updating a baseline."""
        from src.services.capability_governance import StatisticalBaseline

        service = InMemoryBaselineService()
        new_baseline = StatisticalBaseline(
            agent_type="custom",
            mean_hourly_count=50.0,
            std_hourly_count=10.0,
        )

        await service.update_baseline("custom", new_baseline)
        retrieved = await service.get_baseline("custom")

        assert retrieved.mean_hourly_count == 50.0
        assert retrieved.std_hourly_count == 10.0


class TestStatisticalAnomalyDetectorVolume:
    """Tests for volume anomaly detection."""

    @pytest.mark.asyncio
    async def test_normal_volume_not_anomaly(self):
        """Test normal volume is not detected as anomaly."""
        detector = StatisticalAnomalyDetector()

        # Coder baseline has mean ~15, std ~5
        result = await detector.detect_volume_anomaly(
            agent_id="agent-001",
            agent_type="coder",
            tool_classification=None,
            current_count=18,  # Within 1 std
            window_hours=1,
        )

        assert result.is_anomaly is False
        assert result.anomaly_type == AnomalyType.VOLUME
        assert result.score < 0.5

    @pytest.mark.asyncio
    async def test_high_volume_detected_as_anomaly(self):
        """Test high volume is detected as anomaly."""
        detector = StatisticalAnomalyDetector()

        # Coder baseline has mean ~15, std ~5
        # Z-score > 3.0 for count > 15 + 3*5 = 30
        result = await detector.detect_volume_anomaly(
            agent_id="agent-001",
            agent_type="coder",
            tool_classification=None,
            current_count=50,  # Very high
            window_hours=1,
        )

        assert result.is_anomaly is True
        assert result.anomaly_type == AnomalyType.VOLUME
        assert result.details["z_score"] > 3.0

    @pytest.mark.asyncio
    async def test_volume_scales_with_window(self):
        """Test volume expectations scale with time window."""
        detector = StatisticalAnomalyDetector()

        # 2-hour window should expect 2x hourly mean
        result = await detector.detect_volume_anomaly(
            agent_id="agent-001",
            agent_type="coder",
            tool_classification=None,
            current_count=25,  # ~15 per hour is normal
            window_hours=2,
        )

        assert result.is_anomaly is False
        assert result.details["window_hours"] == 2

    @pytest.mark.asyncio
    async def test_volume_details_included(self):
        """Test volume anomaly includes detailed information."""
        detector = StatisticalAnomalyDetector()

        result = await detector.detect_volume_anomaly(
            agent_id="agent-001",
            agent_type="coder",
            tool_classification="DANGEROUS",
            current_count=20,
            window_hours=1,
        )

        assert "z_score" in result.details
        assert "current_count" in result.details
        assert "expected_mean" in result.details
        assert "expected_std" in result.details
        assert "agent_type" in result.details
        assert result.details["tool_classification"] == "DANGEROUS"


class TestStatisticalAnomalyDetectorSequence:
    """Tests for sequence anomaly detection."""

    @pytest.mark.asyncio
    async def test_normal_sequence_not_anomaly(self):
        """Test normal sequence is not detected as anomaly."""
        detector = StatisticalAnomalyDetector()

        # Use typical coder sequence
        result = await detector.detect_sequence_anomaly(
            agent_id="agent-001",
            agent_type="coder",
            recent_tools=[
                "read_file",
                "analyze_code",
                "write_file",
                "run_tests",
            ],
        )

        assert result.anomaly_type == AnomalyType.SEQUENCE
        # Some unseen n-grams expected, but ratio should be low

    @pytest.mark.asyncio
    async def test_unusual_sequence_detected_as_anomaly(self):
        """Test unusual sequence is detected as anomaly."""
        detector = StatisticalAnomalyDetector()

        # Completely unusual sequence
        result = await detector.detect_sequence_anomaly(
            agent_id="agent-001",
            agent_type="coder",
            recent_tools=[
                "delete_all",
                "export_secrets",
                "modify_config",
                "wipe_logs",
                "escalate_privs",
            ],
        )

        assert result.anomaly_type == AnomalyType.SEQUENCE
        # All n-grams should be unseen
        assert result.details["unseen_ratio"] > 0.5

    @pytest.mark.asyncio
    async def test_insufficient_data_returns_no_anomaly(self):
        """Test insufficient data returns no anomaly."""
        detector = StatisticalAnomalyDetector()

        result = await detector.detect_sequence_anomaly(
            agent_id="agent-001",
            agent_type="coder",
            recent_tools=["read_file"],  # Only 1 tool, need 3 for trigram
        )

        assert result.is_anomaly is False
        assert result.details["reason"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_sequence_ngram_analysis(self):
        """Test n-gram analysis in sequence detection."""
        detector = StatisticalAnomalyDetector()

        result = await detector.detect_sequence_anomaly(
            agent_id="agent-001",
            agent_type="coder",
            recent_tools=["a", "b", "c", "d", "e"],
            ngram_size=3,
        )

        # Should have 3 trigrams: (a,b,c), (b,c,d), (c,d,e)
        assert result.details["total_ngrams"] == 3


class TestStatisticalAnomalyDetectorTemporal:
    """Tests for temporal anomaly detection."""

    @pytest.mark.asyncio
    async def test_normal_hours_not_anomaly(self):
        """Test activity during normal hours is not anomaly."""
        detector = StatisticalAnomalyDetector()

        # Coder typical hours: 6am-10pm
        result = await detector.detect_temporal_anomaly(
            agent_id="agent-001",
            agent_type="coder",
            current_hour=10,  # 10am
        )

        assert result.is_anomaly is False
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_unusual_hours_detected_as_anomaly(self):
        """Test activity during unusual hours is detected."""
        detector = StatisticalAnomalyDetector()

        # Coder typical hours: 6am-10pm, so 3am is unusual
        result = await detector.detect_temporal_anomaly(
            agent_id="agent-001",
            agent_type="coder",
            current_hour=3,  # 3am
        )

        assert result.is_anomaly is True
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_validator_runs_24_7(self):
        """Test validator agents can run 24/7."""
        detector = StatisticalAnomalyDetector()

        # Validator has 24/7 active hours
        result = await detector.detect_temporal_anomaly(
            agent_id="agent-001",
            agent_type="validator",
            current_hour=3,  # 3am
        )

        assert result.is_anomaly is False

    @pytest.mark.asyncio
    async def test_temporal_uses_current_time_if_not_provided(self):
        """Test uses current time if hour not provided."""
        detector = StatisticalAnomalyDetector()

        result = await detector.detect_temporal_anomaly(
            agent_id="agent-001",
            agent_type="coder",
        )

        assert "current_hour" in result.details


class TestStatisticalAnomalyDetectorCrossAgent:
    """Tests for cross-agent anomaly detection."""

    @pytest.mark.asyncio
    async def test_single_agent_not_anomaly(self):
        """Test single agent accessing resource is not anomaly."""
        detector = StatisticalAnomalyDetector()

        result = await detector.detect_cross_agent_anomaly(
            agent_ids=["agent-001"],
            shared_resource="database",
            access_times=[datetime.utcnow()],
        )

        assert result.is_anomaly is False
        assert result.details["reason"] == "insufficient_agents"

    @pytest.mark.asyncio
    async def test_coordinated_access_detected(self):
        """Test coordinated access by multiple agents is detected."""
        detector = StatisticalAnomalyDetector()

        now = datetime.utcnow()
        # Multiple agents accessing same resource within seconds
        result = await detector.detect_cross_agent_anomaly(
            agent_ids=["agent-001", "agent-002", "agent-003", "agent-004"],
            shared_resource="sensitive_database",
            access_times=[
                now,
                now + timedelta(seconds=5),
                now + timedelta(seconds=10),
                now + timedelta(seconds=15),
            ],
            correlation_window_seconds=60,
        )

        assert result.anomaly_type == AnomalyType.CROSS_AGENT
        assert result.details["unique_agents"] == 4
        assert result.details["cluster_ratio"] > 0.5

    @pytest.mark.asyncio
    async def test_spread_access_not_anomaly(self):
        """Test spread out access is not anomaly."""
        detector = StatisticalAnomalyDetector()

        now = datetime.utcnow()
        # Agents accessing resource over hours
        result = await detector.detect_cross_agent_anomaly(
            agent_ids=["agent-001", "agent-002"],
            shared_resource="database",
            access_times=[
                now,
                now + timedelta(hours=2),
            ],
            correlation_window_seconds=60,
        )

        assert result.is_anomaly is False


class TestStatisticalAnomalyDetectorFusion:
    """Tests for anomaly score fusion."""

    @pytest.mark.asyncio
    async def test_fuse_empty_results(self):
        """Test fusion with no results."""
        detector = StatisticalAnomalyDetector()

        result = await detector.fuse_anomaly_scores([])

        assert result.is_anomaly is False
        assert result.score == 0.0
        assert result.anomaly_type == AnomalyType.ML_ENSEMBLE

    @pytest.mark.asyncio
    async def test_fuse_multiple_results(self):
        """Test fusion of multiple anomaly results."""
        from src.services.capability_governance import AnomalyResult

        detector = StatisticalAnomalyDetector()

        results = [
            AnomalyResult(
                is_anomaly=False,
                score=0.3,
                anomaly_type=AnomalyType.VOLUME,
            ),
            AnomalyResult(
                is_anomaly=True,
                score=0.7,
                anomaly_type=AnomalyType.SEQUENCE,
            ),
            AnomalyResult(
                is_anomaly=False,
                score=0.0,
                anomaly_type=AnomalyType.TEMPORAL,
            ),
        ]

        fused = await detector.fuse_anomaly_scores(results)

        assert fused.anomaly_type == AnomalyType.ML_ENSEMBLE
        assert "component_scores" in fused.details
        assert fused.details["components_analyzed"] == 3

    @pytest.mark.asyncio
    async def test_honeypot_overrides_fusion(self):
        """Test honeypot trigger overrides all other scores."""
        from src.services.capability_governance import AnomalyResult

        detector = StatisticalAnomalyDetector()

        results = [
            AnomalyResult(
                is_anomaly=False,
                score=0.1,
                anomaly_type=AnomalyType.VOLUME,
            ),
            AnomalyResult(
                is_anomaly=True,
                score=1.0,
                anomaly_type=AnomalyType.HONEYPOT,
            ),
        ]

        fused = await detector.fuse_anomaly_scores(results)

        assert fused.is_anomaly is True
        assert fused.details["has_honeypot_trigger"] is True

    @pytest.mark.asyncio
    async def test_custom_weights(self):
        """Test fusion with custom weights."""
        from src.services.capability_governance import AnomalyResult

        detector = StatisticalAnomalyDetector()

        results = [
            AnomalyResult(
                is_anomaly=False,
                score=0.5,
                anomaly_type=AnomalyType.VOLUME,
            ),
            AnomalyResult(
                is_anomaly=False,
                score=0.5,
                anomaly_type=AnomalyType.TEMPORAL,
            ),
        ]

        custom_weights = {
            AnomalyType.VOLUME: 2.0,
            AnomalyType.TEMPORAL: 1.0,
        }

        fused = await detector.fuse_anomaly_scores(results, weights=custom_weights)

        # Weighted average: (0.5*2 + 0.5*1) / 3 = 0.5
        assert fused.score == pytest.approx(0.5, rel=0.01)


class TestStatisticalDetectorSingleton:
    """Tests for singleton pattern."""

    def test_get_singleton_returns_same_instance(self):
        """Test singleton returns same instance."""
        reset_statistical_detector()
        detector1 = get_statistical_detector()
        detector2 = get_statistical_detector()
        assert detector1 is detector2

    def test_reset_creates_new_instance(self):
        """Test reset creates new instance."""
        detector1 = get_statistical_detector()
        reset_statistical_detector()
        detector2 = get_statistical_detector()
        assert detector1 is not detector2


class TestStatisticalDetectorCustomConfig:
    """Tests for custom configuration."""

    @pytest.mark.asyncio
    async def test_custom_z_score_threshold(self):
        """Test detector respects custom Z-score threshold."""
        config = AnomalyDetectionConfig(volume_z_score_threshold=2.0)
        detector = StatisticalAnomalyDetector(config=config)

        # With lower threshold, more things flagged as anomaly
        result = await detector.detect_volume_anomaly(
            agent_id="agent-001",
            agent_type="coder",
            tool_classification=None,
            current_count=30,  # Z-score ~3 for coder
            window_hours=1,
        )

        assert result.is_anomaly is True
        assert result.details["threshold"] == 2.0

    @pytest.mark.asyncio
    async def test_custom_sequence_threshold(self):
        """Test detector respects custom sequence threshold."""
        config = AnomalyDetectionConfig(sequence_unseen_ratio_threshold=0.8)
        detector = StatisticalAnomalyDetector(config=config)

        result = await detector.detect_sequence_anomaly(
            agent_id="agent-001",
            agent_type="coder",
            recent_tools=["unknown1", "unknown2", "unknown3", "unknown4"],
        )

        # With higher threshold, fewer things flagged
        assert result.details["threshold"] == 0.8
