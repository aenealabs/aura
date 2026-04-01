"""
Unit tests for Semantic Guardrails Metrics Publisher.

Tests cover:
- Metric recording
- Buffer management
- Mock mode operation
- CloudWatch metric formatting
- Flush behavior

Author: Project Aura Team
Created: 2026-01-25
"""

import pytest

from src.services.semantic_guardrails.config import MetricsConfig
from src.services.semantic_guardrails.contracts import (
    LayerResult,
    RecommendedAction,
    ThreatAssessment,
    ThreatCategory,
    ThreatLevel,
)
from src.services.semantic_guardrails.metrics import (
    GuardrailsMetricsPublisher,
    flush_metrics,
    get_metrics_publisher,
    record_threat_assessment,
    reset_metrics_publisher,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton between tests."""
    reset_metrics_publisher()
    yield
    reset_metrics_publisher()


def create_assessment(
    threat_level: ThreatLevel = ThreatLevel.SAFE,
    action: RecommendedAction = RecommendedAction.ALLOW,
    category: ThreatCategory = ThreatCategory.NONE,
    confidence: float = 0.9,
    processing_time: float = 100.0,
    layer_results: list[LayerResult] = None,
) -> ThreatAssessment:
    """Helper to create ThreatAssessment."""
    return ThreatAssessment(
        input_hash="a" * 64,
        threat_level=threat_level,
        recommended_action=action,
        primary_category=category,
        all_categories=[category] if category != ThreatCategory.NONE else [],
        confidence=confidence,
        reasoning="Test reasoning",
        layer_results=layer_results or [],
        session_id="test-session",
        total_processing_time_ms=processing_time,
    )


class TestMetricsPublisherBasics:
    """Basic functionality tests."""

    def test_creation_mock_mode(self):
        """Test publisher creates in mock mode without CloudWatch."""
        publisher = GuardrailsMetricsPublisher()
        assert publisher._mock_mode is True

    def test_namespace_correct(self):
        """Test namespace is correct."""
        publisher = GuardrailsMetricsPublisher()
        assert publisher.NAMESPACE == "Aura/SemanticGuardrails"

    def test_buffer_starts_empty(self):
        """Test buffer starts empty."""
        publisher = GuardrailsMetricsPublisher()
        assert publisher.get_buffer_size() == 0

    def test_buffer_age_starts_zero(self):
        """Test buffer age starts at zero."""
        publisher = GuardrailsMetricsPublisher()
        assert publisher.get_buffer_age_seconds() == 0.0


class TestRecordAssessment:
    """Tests for recording threat assessments."""

    def test_record_assessment_adds_to_buffer(self):
        """Test recording assessment adds metrics to buffer."""
        publisher = GuardrailsMetricsPublisher()
        assessment = create_assessment()

        publisher.record_assessment(assessment)
        assert publisher.get_buffer_size() > 0

    def test_record_threat_detected_metric(self):
        """Test ThreatDetected metric is recorded."""
        publisher = GuardrailsMetricsPublisher()
        assessment = create_assessment(
            threat_level=ThreatLevel.HIGH,
            action=RecommendedAction.BLOCK,
        )

        publisher.record_assessment(assessment)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("ThreatDetected" in k for k in metrics.keys())

    def test_record_threat_by_category(self):
        """Test ThreatByCategory metric is recorded for non-NONE categories."""
        publisher = GuardrailsMetricsPublisher()
        assessment = create_assessment(
            threat_level=ThreatLevel.HIGH,
            category=ThreatCategory.JAILBREAK,
        )

        publisher.record_assessment(assessment)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("ThreatByCategory" in k for k in metrics.keys())

    def test_record_processing_latency(self):
        """Test ProcessingLatencyMs metric is recorded."""
        publisher = GuardrailsMetricsPublisher()
        assessment = create_assessment(processing_time=150.0)

        publisher.record_assessment(assessment)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("ProcessingLatencyMs" in k for k in metrics.keys())

    def test_record_layer_latency(self):
        """Test LayerLatencyMs metric is recorded for each layer."""
        publisher = GuardrailsMetricsPublisher()

        layer_results = [
            LayerResult(
                layer_name="pattern_matcher",
                layer_number=2,
                threat_level=ThreatLevel.SAFE,
                processing_time_ms=5.0,
            ),
            LayerResult(
                layer_name="embedding_detector",
                layer_number=3,
                threat_level=ThreatLevel.SAFE,
                processing_time_ms=30.0,
            ),
        ]
        assessment = create_assessment(layer_results=layer_results)

        publisher.record_assessment(assessment)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("LayerLatencyMs" in k for k in metrics.keys())

    def test_record_confidence(self):
        """Test AssessmentConfidence metric is recorded."""
        publisher = GuardrailsMetricsPublisher()
        assessment = create_assessment(confidence=0.85)

        publisher.record_assessment(assessment)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("AssessmentConfidence" in k for k in metrics.keys())

    def test_record_intervention_required(self):
        """Test InterventionRequired metric is recorded for interventions."""
        publisher = GuardrailsMetricsPublisher()
        assessment = create_assessment(
            threat_level=ThreatLevel.HIGH,
            action=RecommendedAction.BLOCK,
        )

        publisher.record_assessment(assessment)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("InterventionRequired" in k for k in metrics.keys())


class TestRecordCacheHit:
    """Tests for recording cache hits."""

    def test_record_cache_hit(self):
        """Test cache hit is recorded."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_cache_hit("embedding_detector", hit=True)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("CacheAccess" in k and "Hit" in k for k in metrics.keys())

    def test_record_cache_miss(self):
        """Test cache miss is recorded."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_cache_hit("intent_classifier", hit=False)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("CacheAccess" in k and "Miss" in k for k in metrics.keys())


class TestRecordCorpusMatch:
    """Tests for recording corpus matches."""

    def test_record_corpus_match_found(self):
        """Test corpus match found is recorded."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_corpus_match(matched=True, similarity_score=0.92)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("CorpusQuery" in k and "Match" in k for k in metrics.keys())
        assert any("CorpusSimilarityScore" in k for k in metrics.keys())

    def test_record_corpus_no_match(self):
        """Test corpus no match is recorded."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_corpus_match(matched=False)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("CorpusQuery" in k and "NoMatch" in k for k in metrics.keys())


class TestRecordSessionEscalation:
    """Tests for recording session escalations."""

    def test_record_session_escalation(self):
        """Test session escalation is recorded."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_session_escalation(
            session_id="test-session",
            cumulative_score=3.2,
        )
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("SessionEscalation" in k for k in metrics.keys())
        assert any("EscalationCumulativeScore" in k for k in metrics.keys())


class TestRecordFalsePositive:
    """Tests for recording false positives."""

    def test_record_false_positive(self):
        """Test false positive is recorded."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_false_positive(ThreatCategory.JAILBREAK)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("FalsePositiveReported" in k for k in metrics.keys())


class TestRecordLatencyPercentile:
    """Tests for recording latency percentiles."""

    def test_record_p50_latency(self):
        """Test P50 latency is recorded."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_latency_percentile("P50", 120.5)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("LatencyP50" in k for k in metrics.keys())

    def test_record_p95_latency(self):
        """Test P95 latency is recorded."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_latency_percentile("P95", 250.0)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("LatencyP95" in k for k in metrics.keys())


class TestBufferManagement:
    """Tests for buffer management."""

    def test_auto_flush_on_buffer_full(self):
        """Test buffer auto-flushes when full."""
        config = MetricsConfig(buffer_size=5)
        publisher = GuardrailsMetricsPublisher(config=config)

        # Record more than buffer size
        for _ in range(10):
            publisher.record_cache_hit("test", hit=True)

        # Buffer should have been flushed at least once
        # After recording 10 metrics with buffer_size=5, we should have flushed once
        # and have at most 5 in the buffer (or 0 if last metric triggered flush)
        assert publisher.get_buffer_size() <= 5

    def test_manual_flush(self):
        """Test manual flush clears buffer."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_cache_hit("test", hit=True)

        assert publisher.get_buffer_size() > 0
        count = publisher.flush()
        assert count > 0
        assert publisher.get_buffer_size() == 0

    def test_flush_returns_count(self):
        """Test flush returns metric count."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_cache_hit("test", hit=True)
        publisher.record_cache_hit("test", hit=False)

        count = publisher.flush()
        assert count == 2

    def test_flush_empty_buffer(self):
        """Test flushing empty buffer returns 0."""
        publisher = GuardrailsMetricsPublisher()
        count = publisher.flush()
        assert count == 0

    def test_buffer_age_tracks_time(self):
        """Test buffer age tracks time since first metric."""
        publisher = GuardrailsMetricsPublisher()

        publisher.record_cache_hit("test", hit=True)
        age = publisher.get_buffer_age_seconds()
        assert age >= 0.0

    def test_buffer_age_resets_after_flush(self):
        """Test buffer age resets after flush."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_cache_hit("test", hit=True)
        publisher.flush()

        assert publisher.get_buffer_age_seconds() == 0.0


class TestMockMetrics:
    """Tests for mock metrics tracking."""

    def test_get_mock_metrics(self):
        """Test getting mock metrics."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_cache_hit("test", hit=True)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert isinstance(metrics, dict)
        assert len(metrics) > 0

    def test_clear_mock_metrics(self):
        """Test clearing mock metrics."""
        publisher = GuardrailsMetricsPublisher()
        publisher.record_cache_hit("test", hit=True)
        publisher.flush()

        publisher.clear_mock_metrics()
        metrics = publisher.get_mock_metrics()
        assert len(metrics) == 0

    def test_mock_metrics_accumulate(self):
        """Test mock metrics accumulate values."""
        publisher = GuardrailsMetricsPublisher()

        publisher.record_cache_hit("test", hit=True)
        publisher.record_cache_hit("test", hit=True)
        publisher.record_cache_hit("test", hit=True)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        # Should have accumulated to 3
        hit_metrics = [v for k, v in metrics.items() if "Hit" in k]
        assert sum(hit_metrics) == 3


class TestDisabledMetrics:
    """Tests for disabled metrics."""

    def test_disabled_metrics_no_record(self):
        """Test disabled metrics don't record."""
        config = MetricsConfig(enabled=False)
        publisher = GuardrailsMetricsPublisher(config=config)

        publisher.record_cache_hit("test", hit=True)
        assert publisher.get_buffer_size() == 0

    def test_disabled_metrics_no_assessment(self):
        """Test disabled metrics don't record assessments."""
        config = MetricsConfig(enabled=False)
        publisher = GuardrailsMetricsPublisher(config=config)

        assessment = create_assessment()
        publisher.record_assessment(assessment)
        assert publisher.get_buffer_size() == 0


class TestMetricDimensions:
    """Tests for metric dimensions."""

    def test_threat_level_dimension(self):
        """Test ThreatLevel dimension is included."""
        publisher = GuardrailsMetricsPublisher()
        assessment = create_assessment(threat_level=ThreatLevel.HIGH)

        publisher.record_assessment(assessment)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("ThreatLevel=HIGH" in k for k in metrics.keys())

    def test_action_dimension(self):
        """Test Action dimension is included."""
        publisher = GuardrailsMetricsPublisher()
        assessment = create_assessment(action=RecommendedAction.BLOCK)

        publisher.record_assessment(assessment)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("Action=block" in k for k in metrics.keys())

    def test_category_dimension(self):
        """Test Category dimension is included."""
        publisher = GuardrailsMetricsPublisher()
        assessment = create_assessment(category=ThreatCategory.JAILBREAK)

        publisher.record_assessment(assessment)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        assert any("Category=jailbreak" in k for k in metrics.keys())


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_metrics_publisher_singleton(self):
        """Test get_metrics_publisher returns singleton."""
        p1 = get_metrics_publisher()
        p2 = get_metrics_publisher()
        assert p1 is p2

    def test_record_threat_assessment_function(self):
        """Test record_threat_assessment convenience function."""
        assessment = create_assessment()
        # Should not raise
        record_threat_assessment(assessment)

    def test_flush_metrics_function(self):
        """Test flush_metrics convenience function."""
        assessment = create_assessment()
        record_threat_assessment(assessment)

        count = flush_metrics()
        assert count > 0

    def test_reset_metrics_publisher(self):
        """Test reset_metrics_publisher clears singleton."""
        p1 = get_metrics_publisher()
        reset_metrics_publisher()
        p2 = get_metrics_publisher()
        assert p1 is not p2


class TestConfigurationOptions:
    """Tests for configuration options."""

    def test_custom_buffer_size(self):
        """Test custom buffer size."""
        config = MetricsConfig(buffer_size=100)
        publisher = GuardrailsMetricsPublisher(config=config)
        assert publisher.config.buffer_size == 100

    def test_custom_flush_interval(self):
        """Test custom flush interval."""
        config = MetricsConfig(flush_interval_seconds=30)
        publisher = GuardrailsMetricsPublisher(config=config)
        assert publisher.config.flush_interval_seconds == 30


class TestSafeCategory:
    """Tests for safe threat category handling."""

    def test_none_category_no_category_metric(self):
        """Test NONE category doesn't record ThreatByCategory."""
        publisher = GuardrailsMetricsPublisher()
        assessment = create_assessment(category=ThreatCategory.NONE)

        publisher.record_assessment(assessment)
        publisher.flush()

        metrics = publisher.get_mock_metrics()
        # Should not have ThreatByCategory for NONE
        assert not any("ThreatByCategory" in k and "NONE" in k for k in metrics.keys())
