"""
Tests for confidence calibration services.

ADR-056 Phase 1.5 - Confidence Calibration Infrastructure
"""

import platform
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Platform-specific test isolation
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestFeedbackType:
    """Tests for FeedbackType enum."""

    def test_feedback_type_values(self):
        """Test FeedbackType enum has expected values."""
        from src.services.documentation.confidence_calibration import FeedbackType

        assert FeedbackType.ACCURATE.value == "accurate"
        assert FeedbackType.INACCURATE.value == "inaccurate"
        assert FeedbackType.PARTIAL.value == "partial"

    def test_feedback_type_from_string(self):
        """Test FeedbackType can be created from string."""
        from src.services.documentation.confidence_calibration import FeedbackType

        assert FeedbackType("accurate") == FeedbackType.ACCURATE
        assert FeedbackType("inaccurate") == FeedbackType.INACCURATE
        assert FeedbackType("partial") == FeedbackType.PARTIAL


class TestDocumentationType:
    """Tests for DocumentationType enum."""

    def test_documentation_type_values(self):
        """Test DocumentationType enum has expected values."""
        from src.services.documentation.confidence_calibration import DocumentationType

        assert DocumentationType.DIAGRAM.value == "diagram"
        assert DocumentationType.REPORT.value == "report"
        assert DocumentationType.SERVICE_BOUNDARY.value == "service_boundary"
        assert DocumentationType.DATA_FLOW.value == "data_flow"


class TestFeedbackRecord:
    """Tests for FeedbackRecord dataclass."""

    def test_feedback_record_creation(self):
        """Test FeedbackRecord can be created with required fields."""
        from src.services.documentation.confidence_calibration import (
            DocumentationType,
            FeedbackRecord,
            FeedbackType,
        )

        record = FeedbackRecord(
            feedback_id="test-123",
            job_id="job-456",
            organization_id="org-001",
            documentation_type=DocumentationType.DIAGRAM,
            feedback_type=FeedbackType.ACCURATE,
            raw_confidence=0.85,
        )

        assert record.feedback_id == "test-123"
        assert record.job_id == "job-456"
        assert record.organization_id == "org-001"
        assert record.documentation_type == DocumentationType.DIAGRAM
        assert record.feedback_type == FeedbackType.ACCURATE
        assert record.raw_confidence == 0.85
        assert record.diagram_type == ""
        assert record.correction_text == ""
        assert record.user_id == ""

    def test_feedback_record_auto_timestamp(self):
        """Test FeedbackRecord auto-generates timestamp."""
        from src.services.documentation.confidence_calibration import (
            DocumentationType,
            FeedbackRecord,
            FeedbackType,
        )

        record = FeedbackRecord(
            feedback_id="test-123",
            job_id="job-456",
            organization_id="org-001",
            documentation_type=DocumentationType.DIAGRAM,
            feedback_type=FeedbackType.ACCURATE,
            raw_confidence=0.85,
        )

        assert record.timestamp is not None
        # Verify it's a valid datetime
        assert isinstance(record.timestamp, datetime)

    def test_feedback_record_actual_accuracy(self):
        """Test FeedbackRecord actual_accuracy property."""
        from src.services.documentation.confidence_calibration import (
            DocumentationType,
            FeedbackRecord,
            FeedbackType,
        )

        # Accurate = 1.0
        record = FeedbackRecord(
            feedback_id="test-1",
            job_id="job-1",
            organization_id="org-001",
            documentation_type=DocumentationType.DIAGRAM,
            feedback_type=FeedbackType.ACCURATE,
            raw_confidence=0.85,
        )
        assert record.actual_accuracy == 1.0

        # Inaccurate = 0.0
        record = FeedbackRecord(
            feedback_id="test-2",
            job_id="job-2",
            organization_id="org-001",
            documentation_type=DocumentationType.DIAGRAM,
            feedback_type=FeedbackType.INACCURATE,
            raw_confidence=0.85,
        )
        assert record.actual_accuracy == 0.0

        # Partial = 0.5
        record = FeedbackRecord(
            feedback_id="test-3",
            job_id="job-3",
            organization_id="org-001",
            documentation_type=DocumentationType.DIAGRAM,
            feedback_type=FeedbackType.PARTIAL,
            raw_confidence=0.85,
        )
        assert record.actual_accuracy == 0.5


class TestCalibratedConfidenceScorer:
    """Tests for CalibratedConfidenceScorer class."""

    def test_initialization_defaults(self):
        """Test scorer initializes with default values."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer()

        assert scorer.min_samples == 100
        assert scorer.organization_id == "default"
        assert scorer.documentation_type == "all"
        assert scorer.is_calibrated is False
        assert scorer.sample_count == 0
        assert scorer.model_version == 0

    def test_initialization_custom_params(self):
        """Test scorer initializes with custom parameters."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(
            min_samples_for_calibration=50,
            organization_id="org-001",
            documentation_type="diagram",
        )

        assert scorer.min_samples == 50
        assert scorer.organization_id == "org-001"
        assert scorer.documentation_type == "diagram"

    def test_calibrate_uncalibrated_returns_raw(self):
        """Test uncalibrated scorer returns raw score."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer()
        result = scorer.calibrate(0.75)

        assert result == 0.75

    def test_calibrate_raises_for_invalid_range(self):
        """Test calibrate raises ValueError for invalid range."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer()

        with pytest.raises(ValueError, match="out of range"):
            scorer.calibrate(-0.5)

        with pytest.raises(ValueError, match="out of range"):
            scorer.calibrate(1.5)

    def test_fit_with_insufficient_samples(self):
        """Test fit returns False with insufficient samples."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=100)

        raw_scores = [0.5, 0.6, 0.7]  # Only 3 samples
        outcomes = [1.0, 0.0, 1.0]

        result = scorer.fit(raw_scores, outcomes)

        assert result is False
        assert scorer.is_calibrated is False

    def test_fit_with_sufficient_samples_no_sklearn(self):
        """Test fit returns False when sklearn not available."""
        from src.services.documentation.confidence_calibration import (
            SKLEARN_AVAILABLE,
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=10)

        # Create 20 samples
        raw_scores = [i / 20 for i in range(20)]
        outcomes = [1.0 if i > 10 else 0.0 for i in range(20)]

        result = scorer.fit(raw_scores, outcomes)

        # Result depends on sklearn availability
        if SKLEARN_AVAILABLE:
            assert result is True
            assert scorer.is_calibrated is True
            assert scorer.sample_count == 20
            assert scorer.model_version == 1
        else:
            assert result is False

    @pytest.mark.skipif(
        not __import__(
            "src.services.documentation.confidence_calibration",
            fromlist=["SKLEARN_AVAILABLE"],
        ).SKLEARN_AVAILABLE,
        reason="sklearn not available",
    )
    def test_calibrate_after_fit(self):
        """Test calibration works after fitting."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=10)

        # Create training data with clear pattern
        raw_scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
        outcomes = [0.0, 0.0, 0.0, 0.0, 0.5, 0.5, 1.0, 1.0, 1.0, 1.0]

        scorer.fit(raw_scores, outcomes)

        # Low raw scores should calibrate low
        low_result = scorer.calibrate(0.2)
        # High raw scores should calibrate high
        high_result = scorer.calibrate(0.9)

        assert low_result < high_result
        assert 0.0 <= low_result <= 1.0
        assert 0.0 <= high_result <= 1.0

    def test_calculate_ece(self):
        """Test ECE calculation."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer()

        # Perfect calibration: predicted = actual
        predicted = [0.0, 0.5, 1.0]
        actual = [0.0, 0.5, 1.0]
        ece = scorer._calculate_ece(predicted, actual)
        assert ece < 0.1  # Near-perfect

        # Poor calibration: always predict 0.9 but actual is 0.5
        predicted = [0.9, 0.9, 0.9, 0.9, 0.9]
        actual = [0.5, 0.5, 0.5, 0.5, 0.5]
        ece = scorer._calculate_ece(predicted, actual)
        assert ece > 0.3  # Poor calibration

    def test_calculate_ece_empty_input(self):
        """Test ECE calculation with empty input returns 0.0."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer()

        # Implementation returns 0.0 for empty input
        assert scorer._calculate_ece([], []) == 0.0

    def test_get_stats_uncalibrated(self):
        """Test get_stats for uncalibrated scorer."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=100)
        stats = scorer.get_stats()

        assert stats["is_calibrated"] is False
        assert stats["sample_count"] == 0
        assert stats["min_samples_required"] == 100
        assert stats["model_version"] == 0
        assert stats["ece_before"] == 0.0
        assert stats["ece_after"] == 0.0

    @pytest.mark.skipif(
        not __import__(
            "src.services.documentation.confidence_calibration",
            fromlist=["SKLEARN_AVAILABLE"],
        ).SKLEARN_AVAILABLE,
        reason="sklearn not available",
    )
    def test_get_stats_calibrated(self):
        """Test get_stats for calibrated scorer."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=10)

        raw_scores = [i / 20 for i in range(20)]
        outcomes = [1.0 if i > 10 else 0.0 for i in range(20)]
        scorer.fit(raw_scores, outcomes)

        stats = scorer.get_stats()

        assert stats["is_calibrated"] is True
        assert stats["sample_count"] == 20
        assert stats["model_version"] == 1
        assert 0.0 <= stats["ece_before"] <= 1.0
        assert 0.0 <= stats["ece_after"] <= 1.0

    def test_thread_safety(self):
        """Test scorer is thread-safe."""
        import threading

        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=10)

        raw_scores = [i / 20 for i in range(20)]
        outcomes = [1.0 if i > 10 else 0.0 for i in range(20)]

        results = []
        errors = []

        def fit_and_calibrate():
            try:
                scorer.fit(raw_scores, outcomes)
                result = scorer.calibrate(0.5)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=fit_and_calibrate) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5
        # All results should be valid
        for r in results:
            assert 0.0 <= r <= 1.0


class TestFeedbackLearningService:
    """Tests for FeedbackLearningService class."""

    def test_initialization_mock_mode(self):
        """Test service initializes in mock mode."""
        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
        )

        service = FeedbackLearningService(use_mock=True)

        assert service.use_mock is True

    def test_initialization_with_table_name(self):
        """Test service initializes with table name."""
        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
        )

        service = FeedbackLearningService(use_mock=False, table_name="test-table")

        assert service.use_mock is False
        assert service.table_name == "test-table"

    def test_store_feedback_mock_mode(self):
        """Test storing feedback in mock mode."""
        from src.services.documentation.confidence_calibration import (
            DocumentationType,
            FeedbackLearningService,
            FeedbackRecord,
            FeedbackType,
        )

        service = FeedbackLearningService(use_mock=True)

        record = FeedbackRecord(
            feedback_id="test-123",
            job_id="job-456",
            organization_id="org-001",
            documentation_type=DocumentationType.DIAGRAM,
            feedback_type=FeedbackType.ACCURATE,
            raw_confidence=0.85,
        )

        result = service.store_feedback(record)

        assert result is True

    def test_get_feedback_for_calibration_mock_mode(self):
        """Test getting feedback for calibration in mock mode."""
        from src.services.documentation.confidence_calibration import (
            DocumentationType,
            FeedbackLearningService,
            FeedbackRecord,
            FeedbackType,
        )

        service = FeedbackLearningService(use_mock=True)

        # Store some feedback first
        for i in range(5):
            record = FeedbackRecord(
                feedback_id=f"test-{i}",
                job_id=f"job-{i}",
                organization_id="org-001",
                documentation_type=DocumentationType.DIAGRAM,
                feedback_type=(
                    FeedbackType.ACCURATE if i % 2 == 0 else FeedbackType.INACCURATE
                ),
                raw_confidence=0.5 + i * 0.1,
            )
            service.store_feedback(record)

        # Retrieve feedback
        feedback = service.get_feedback_for_calibration("org-001")

        assert len(feedback) == 5
        assert all(f.organization_id == "org-001" for f in feedback)

    def test_get_feedback_for_calibration_filtered_by_type(self):
        """Test feedback filtering by documentation type."""
        from src.services.documentation.confidence_calibration import (
            DocumentationType,
            FeedbackLearningService,
            FeedbackRecord,
            FeedbackType,
        )

        service = FeedbackLearningService(use_mock=True)

        # Store mixed feedback
        for i, doc_type in enumerate(
            [
                DocumentationType.DIAGRAM,
                DocumentationType.REPORT,
                DocumentationType.DIAGRAM,
            ]
        ):
            record = FeedbackRecord(
                feedback_id=f"test-{i}",
                job_id=f"job-{i}",
                organization_id="org-001",
                documentation_type=doc_type,
                feedback_type=FeedbackType.ACCURATE,
                raw_confidence=0.8,
            )
            service.store_feedback(record)

        # Retrieve only diagrams (use value string, not enum)
        feedback = service.get_feedback_for_calibration(
            "org-001", documentation_type="diagram"
        )

        assert len(feedback) == 2
        assert all(f.documentation_type == DocumentationType.DIAGRAM for f in feedback)

    def test_get_feedback_count_mock_mode(self):
        """Test getting feedback count in mock mode."""
        from src.services.documentation.confidence_calibration import (
            DocumentationType,
            FeedbackLearningService,
            FeedbackRecord,
            FeedbackType,
        )

        service = FeedbackLearningService(use_mock=True)

        # Store feedback
        for i in range(10):
            record = FeedbackRecord(
                feedback_id=f"test-{i}",
                job_id=f"job-{i}",
                organization_id="org-001" if i < 7 else "org-002",
                documentation_type=DocumentationType.DIAGRAM,
                feedback_type=FeedbackType.ACCURATE,
                raw_confidence=0.8,
            )
            service.store_feedback(record)

        # Count for org-001
        count = service.get_feedback_count("org-001")
        assert count == 7

        # Count for org-002
        count = service.get_feedback_count("org-002")
        assert count == 3

    def test_get_stats(self):
        """Test getting feedback statistics."""
        from src.services.documentation.confidence_calibration import (
            DocumentationType,
            FeedbackLearningService,
            FeedbackRecord,
            FeedbackType,
        )

        service = FeedbackLearningService(use_mock=True)

        # Store mixed feedback
        feedback_types = [
            FeedbackType.ACCURATE,
            FeedbackType.ACCURATE,
            FeedbackType.INACCURATE,
            FeedbackType.PARTIAL,
            FeedbackType.PARTIAL,
        ]
        for i, ft in enumerate(feedback_types):
            record = FeedbackRecord(
                feedback_id=f"test-{i}",
                job_id=f"job-{i}",
                organization_id="org-001",
                documentation_type=DocumentationType.DIAGRAM,
                feedback_type=ft,
                raw_confidence=0.8,
            )
            service.store_feedback(record)

        stats = service.get_stats("org-001")

        assert stats["total_feedback"] == 5
        assert stats["accurate_count"] == 2
        assert stats["inaccurate_count"] == 1
        assert stats["partial_count"] == 2
        assert stats["accuracy_rate"] == 0.4  # 2/5


class TestCalibrationMetricsService:
    """Tests for CalibrationMetricsService class."""

    def test_initialization_mock_mode(self):
        """Test service initializes in mock mode."""
        from src.services.documentation.confidence_calibration import (
            CalibrationMetricsService,
        )

        service = CalibrationMetricsService(use_mock=True)

        assert service.use_mock is True
        assert service.namespace == "Aura/DocumentationAgent"

    def test_initialization_custom_namespace(self):
        """Test service initializes with custom namespace."""
        from src.services.documentation.confidence_calibration import (
            CalibrationMetricsService,
        )

        service = CalibrationMetricsService(
            use_mock=True, cloudwatch_namespace="CustomNamespace"
        )

        assert service.namespace == "CustomNamespace"

    def test_record_ece(self):
        """Test recording ECE metric."""
        from src.services.documentation.confidence_calibration import (
            CalibrationMetricsService,
        )

        service = CalibrationMetricsService(use_mock=True)

        # Should not raise
        service.record_ece(
            organization_id="org-001",
            ece_value=0.15,
            documentation_type="diagram",
        )

        # Verify metric was recorded
        metrics = service.get_mock_metrics()
        assert len(metrics) == 1
        assert metrics[0]["Value"] == 0.15

    def test_record_calibration_event(self):
        """Test recording calibration event."""
        from src.services.documentation.confidence_calibration import (
            CalibrationMetricsService,
        )

        service = CalibrationMetricsService(use_mock=True)

        # Should not raise
        service.record_calibration_event(
            organization_id="org-001",
            sample_count=150,
            ece_before=0.25,
            ece_after=0.08,
            model_version=1,
        )

        # Verify metric was recorded
        metrics = service.get_mock_metrics()
        assert len(metrics) == 1
        assert metrics[0]["type"] == "calibration_event"
        assert metrics[0]["sample_count"] == 150

    def test_check_ece_threshold(self):
        """Test ECE threshold checking."""
        from src.services.documentation.confidence_calibration import (
            CalibrationMetricsService,
        )

        service = CalibrationMetricsService(use_mock=True)

        # Below threshold
        assert service.check_ece_threshold(0.03, threshold=0.05) is False

        # Above threshold
        assert service.check_ece_threshold(0.10, threshold=0.05) is True

    @patch("boto3.client")
    def test_record_ece_aws_mode(self, mock_boto_client):
        """Test recording ECE in AWS mode."""
        from src.services.documentation.confidence_calibration import (
            CalibrationMetricsService,
        )

        mock_cw = MagicMock()
        mock_boto_client.return_value = mock_cw

        service = CalibrationMetricsService(use_mock=False)
        service.record_ece("org-001", 0.15)

        mock_cw.put_metric_data.assert_called_once()
        call_args = mock_cw.put_metric_data.call_args
        assert call_args[1]["Namespace"] == "Aura/DocumentationAgent"


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_calibrated_scorer(self):
        """Test create_calibrated_scorer factory."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
            create_calibrated_scorer,
        )

        scorer = create_calibrated_scorer(
            organization_id="org-001",
            documentation_type="diagram",
        )

        assert isinstance(scorer, CalibratedConfidenceScorer)
        assert scorer.organization_id == "org-001"
        assert scorer.documentation_type == "diagram"

    def test_create_feedback_service(self):
        """Test create_feedback_service factory."""
        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
            create_feedback_service,
        )

        service = create_feedback_service(use_mock=True)

        assert isinstance(service, FeedbackLearningService)
        assert service.use_mock is True

    def test_create_metrics_service(self):
        """Test create_metrics_service factory."""
        from src.services.documentation.confidence_calibration import (
            CalibrationMetricsService,
            create_metrics_service,
        )

        service = create_metrics_service(use_mock=True)

        assert isinstance(service, CalibrationMetricsService)
        assert service.use_mock is True


class TestCalibrationModel:
    """Tests for CalibrationModel dataclass."""

    def test_calibration_model_creation(self):
        """Test CalibrationModel can be created."""
        from src.services.documentation.confidence_calibration import CalibrationModel

        model = CalibrationModel(
            model_id="model-001",
            organization_id="org-001",
            documentation_type="diagram",
            sample_count=250,
            ece_before=0.25,
            ece_after=0.08,
            version=3,
        )

        assert model.model_id == "model-001"
        assert model.organization_id == "org-001"
        assert model.documentation_type == "diagram"
        assert model.sample_count == 250
        assert model.ece_before == 0.25
        assert model.ece_after == 0.08
        assert model.version == 3
        assert model.is_active is True

    def test_calibration_model_defaults(self):
        """Test CalibrationModel default values."""
        from src.services.documentation.confidence_calibration import CalibrationModel

        model = CalibrationModel(
            model_id="model-001",
            organization_id="org-001",
        )

        assert model.documentation_type == "all"
        assert model.sample_count == 0
        assert model.ece_before == 0.0
        assert model.ece_after == 0.0
        assert model.version == 1
        assert model.is_active is True


class TestSerializeDeserialize:
    """Tests for serialization and deserialization."""

    @pytest.mark.skipif(
        not __import__(
            "src.services.documentation.confidence_calibration",
            fromlist=["SKLEARN_AVAILABLE"],
        ).SKLEARN_AVAILABLE,
        reason="sklearn not available",
    )
    def test_serialize_calibrator(self):
        """Test serializing a calibrated scorer."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(
            min_samples_for_calibration=10,
            organization_id="org-001",
            documentation_type="diagram",
        )

        # Train the calibrator
        raw_scores = [i / 20 for i in range(20)]
        outcomes = [1.0 if i > 10 else 0.0 for i in range(20)]
        scorer.fit(raw_scores, outcomes)

        # Serialize
        data = scorer.serialize()

        assert isinstance(data, bytes)
        assert len(data) > 0

    @pytest.mark.skipif(
        not __import__(
            "src.services.documentation.confidence_calibration",
            fromlist=["SKLEARN_AVAILABLE"],
        ).SKLEARN_AVAILABLE,
        reason="sklearn not available",
    )
    def test_deserialize_calibrator(self):
        """Test deserializing a calibrated scorer."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        # Create and train original scorer
        original = CalibratedConfidenceScorer(
            min_samples_for_calibration=10,
            organization_id="org-001",
            documentation_type="diagram",
        )
        raw_scores = [i / 20 for i in range(20)]
        outcomes = [1.0 if i > 10 else 0.0 for i in range(20)]
        original.fit(raw_scores, outcomes)

        # Serialize
        data = original.serialize()

        # Deserialize into new scorer
        restored = CalibratedConfidenceScorer()
        restored.deserialize(data)

        # Verify restored state
        assert restored.is_calibrated is True
        assert restored.organization_id == "org-001"
        assert restored.documentation_type == "diagram"
        assert restored.sample_count == 20

        # Verify calibration works the same
        original_result = original.calibrate(0.5)
        restored_result = restored.calibrate(0.5)
        assert abs(original_result - restored_result) < 0.01

    def test_serialize_uncalibrated(self):
        """Test serializing an uncalibrated scorer."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(
            organization_id="org-001",
        )

        # Serialize without training
        data = scorer.serialize()

        assert isinstance(data, bytes)

        # Deserialize
        restored = CalibratedConfidenceScorer()
        restored.deserialize(data)

        assert restored.is_calibrated is False


class TestCalibrateBatch:
    """Tests for batch calibration."""

    def test_calibrate_batch_uncalibrated(self):
        """Test batch calibration returns raw scores when uncalibrated."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer()
        raw_scores = [0.3, 0.5, 0.7, 0.9]

        result = scorer.calibrate_batch(raw_scores)

        assert result == raw_scores

    @pytest.mark.skipif(
        not __import__(
            "src.services.documentation.confidence_calibration",
            fromlist=["SKLEARN_AVAILABLE"],
        ).SKLEARN_AVAILABLE,
        reason="sklearn not available",
    )
    def test_calibrate_batch_calibrated(self):
        """Test batch calibration after fitting."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=10)

        # Train
        raw_scores = [i / 20 for i in range(20)]
        outcomes = [1.0 if i > 10 else 0.0 for i in range(20)]
        scorer.fit(raw_scores, outcomes)

        # Batch calibrate
        test_scores = [0.3, 0.5, 0.7, 0.9]
        result = scorer.calibrate_batch(test_scores)

        assert len(result) == len(test_scores)
        # All results should be in valid range
        for r in result:
            assert 0.0 <= r <= 1.0


class TestCalibrateExceptionHandling:
    """Tests for calibrate exception handling."""

    @pytest.mark.skipif(
        not __import__(
            "src.services.documentation.confidence_calibration",
            fromlist=["SKLEARN_AVAILABLE"],
        ).SKLEARN_AVAILABLE,
        reason="sklearn not available",
    )
    def test_calibrate_handles_prediction_error(self):
        """Test calibrate returns raw score on prediction error."""
        from unittest.mock import MagicMock

        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=10)

        # Train
        raw_scores = [i / 20 for i in range(20)]
        outcomes = [1.0 if i > 10 else 0.0 for i in range(20)]
        scorer.fit(raw_scores, outcomes)

        # Mock calibrator to raise an exception
        original_calibrator = scorer._calibrator
        scorer._calibrator = MagicMock()
        scorer._calibrator.predict.side_effect = Exception("Prediction error")

        # Should return raw score on error
        result = scorer.calibrate(0.5)
        assert result == 0.5

        # Restore original
        scorer._calibrator = original_calibrator

    @pytest.mark.skipif(
        not __import__(
            "src.services.documentation.confidence_calibration",
            fromlist=["SKLEARN_AVAILABLE"],
        ).SKLEARN_AVAILABLE,
        reason="sklearn not available",
    )
    def test_calibrate_batch_handles_prediction_error(self):
        """Test calibrate_batch returns raw scores on prediction error."""
        from unittest.mock import MagicMock

        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=10)

        # Train
        raw_scores = [i / 20 for i in range(20)]
        outcomes = [1.0 if i > 10 else 0.0 for i in range(20)]
        scorer.fit(raw_scores, outcomes)

        # Mock calibrator to raise an exception
        original_calibrator = scorer._calibrator
        scorer._calibrator = MagicMock()
        scorer._calibrator.predict.side_effect = Exception("Batch prediction error")

        # Should return raw scores on error
        test_scores = [0.3, 0.5, 0.7]
        result = scorer.calibrate_batch(test_scores)
        assert result == test_scores

        # Restore original
        scorer._calibrator = original_calibrator


class TestFitEdgeCases:
    """Tests for fit method edge cases."""

    @pytest.mark.skipif(
        not __import__(
            "src.services.documentation.confidence_calibration",
            fromlist=["SKLEARN_AVAILABLE"],
        ).SKLEARN_AVAILABLE,
        reason="sklearn not available - length check happens after sklearn check",
    )
    def test_fit_mismatched_lengths(self):
        """Test fit raises ValueError for mismatched lengths."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=5)

        with pytest.raises(ValueError, match="must have same length"):
            scorer.fit([0.5, 0.6, 0.7], [1.0, 0.0])

    def test_fit_invalid_raw_score_range(self):
        """Test fit raises ValueError for invalid raw score range."""
        from src.services.documentation.confidence_calibration import (
            SKLEARN_AVAILABLE,
            CalibratedConfidenceScorer,
        )

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not available")

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=5)

        with pytest.raises(ValueError, match="out of range"):
            scorer.fit([0.5, 1.5, 0.7, 0.6, 0.8], [1.0, 0.0, 1.0, 0.0, 1.0])

    def test_fit_invalid_outcome_range(self):
        """Test fit raises ValueError for invalid outcome range."""
        from src.services.documentation.confidence_calibration import (
            SKLEARN_AVAILABLE,
            CalibratedConfidenceScorer,
        )

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not available")

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=5)

        with pytest.raises(ValueError, match="out of range"):
            scorer.fit([0.5, 0.6, 0.7, 0.8, 0.9], [1.0, 0.0, 1.5, 0.0, 1.0])


class TestFeedbackLearningServiceTimestampFilter:
    """Tests for timestamp filtering in FeedbackLearningService."""

    def test_get_feedback_filtered_by_timestamp(self):
        """Test feedback filtering by timestamp."""
        from datetime import timedelta

        from src.services.documentation.confidence_calibration import (
            DocumentationType,
            FeedbackLearningService,
            FeedbackRecord,
            FeedbackType,
        )

        service = FeedbackLearningService(use_mock=True)

        # Store feedback with different timestamps
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=30)
        recent_time = now - timedelta(hours=1)

        # Old feedback
        old_record = FeedbackRecord(
            feedback_id="old-1",
            job_id="job-old",
            organization_id="org-001",
            documentation_type=DocumentationType.DIAGRAM,
            feedback_type=FeedbackType.ACCURATE,
            raw_confidence=0.8,
            timestamp=old_time,
        )
        service.store_feedback(old_record)

        # Recent feedback
        recent_record = FeedbackRecord(
            feedback_id="recent-1",
            job_id="job-recent",
            organization_id="org-001",
            documentation_type=DocumentationType.DIAGRAM,
            feedback_type=FeedbackType.ACCURATE,
            raw_confidence=0.9,
            timestamp=recent_time,
        )
        service.store_feedback(recent_record)

        # Filter by timestamp (only recent)
        cutoff = now - timedelta(days=7)
        feedback = service.get_feedback_for_calibration("org-001", min_timestamp=cutoff)

        assert len(feedback) == 1
        assert feedback[0].feedback_id == "recent-1"


class TestFeedbackLearningServiceEmptyStats:
    """Tests for empty stats in FeedbackLearningService."""

    def test_get_stats_empty_organization(self):
        """Test get_stats returns zeros for empty organization."""
        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
        )

        service = FeedbackLearningService(use_mock=True)

        stats = service.get_stats("nonexistent-org")

        assert stats["total_feedback"] == 0
        assert stats["accurate_count"] == 0
        assert stats["inaccurate_count"] == 0
        assert stats["partial_count"] == 0
        assert stats["accuracy_rate"] == 0.0


class TestFeedbackLearningServiceAwsMode:
    """Tests for FeedbackLearningService in AWS mode."""

    @patch("boto3.client")
    def test_store_feedback_aws_mode(self, mock_boto_client):
        """Test storing feedback in AWS mode."""
        from src.services.documentation.confidence_calibration import (
            DocumentationType,
            FeedbackLearningService,
            FeedbackRecord,
            FeedbackType,
        )

        mock_dynamodb = MagicMock()
        mock_boto_client.return_value = mock_dynamodb

        service = FeedbackLearningService(use_mock=False, table_name="test-table")

        record = FeedbackRecord(
            feedback_id="test-123",
            job_id="job-456",
            organization_id="org-001",
            documentation_type=DocumentationType.DIAGRAM,
            feedback_type=FeedbackType.ACCURATE,
            raw_confidence=0.85,
            diagram_type="architecture",
            correction_text="Fixed typo",
            metadata={"key": "value"},
        )

        result = service.store_feedback(record)

        assert result is True
        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]["TableName"] == "test-table"
        item = call_args[1]["Item"]
        assert item["feedback_id"]["S"] == "test-123"
        assert item["diagram_type"]["S"] == "architecture"
        assert item["correction_text"]["S"] == "Fixed typo"
        assert "metadata" in item

    @patch("boto3.client")
    def test_store_feedback_aws_mode_failure(self, mock_boto_client):
        """Test storing feedback handles AWS errors."""
        from src.services.documentation.confidence_calibration import (
            DocumentationType,
            FeedbackLearningService,
            FeedbackRecord,
            FeedbackType,
        )

        mock_dynamodb = MagicMock()
        mock_dynamodb.put_item.side_effect = Exception("DynamoDB error")
        mock_boto_client.return_value = mock_dynamodb

        service = FeedbackLearningService(use_mock=False, table_name="test-table")

        record = FeedbackRecord(
            feedback_id="test-123",
            job_id="job-456",
            organization_id="org-001",
            documentation_type=DocumentationType.DIAGRAM,
            feedback_type=FeedbackType.ACCURATE,
            raw_confidence=0.85,
        )

        result = service.store_feedback(record)

        assert result is False

    @patch("boto3.client")
    def test_get_feedback_for_calibration_aws_mode(self, mock_boto_client):
        """Test getting feedback for calibration in AWS mode."""
        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
        )

        mock_dynamodb = MagicMock()
        mock_dynamodb.query.return_value = {
            "Items": [
                {
                    "feedback_id": {"S": "test-1"},
                    "job_id": {"S": "job-1"},
                    "organization_id": {"S": "org-001"},
                    "documentation_type": {"S": "diagram"},
                    "raw_confidence": {"N": "0.85"},
                    "feedback_type": {"S": "accurate"},
                    "user_id": {"S": "user-1"},
                    "diagram_type": {"S": "architecture"},
                    "correction_text": {"S": ""},
                    "timestamp": {"S": "2026-01-01T12:00:00+00:00"},
                },
            ]
        }
        mock_boto_client.return_value = mock_dynamodb

        service = FeedbackLearningService(use_mock=False, table_name="test-table")

        records = service.get_feedback_for_calibration(
            "org-001", documentation_type="diagram"
        )

        assert len(records) == 1
        assert records[0].feedback_id == "test-1"
        assert records[0].raw_confidence == 0.85

    @patch("boto3.client")
    def test_get_feedback_for_calibration_aws_mode_with_timestamp_filter(
        self, mock_boto_client
    ):
        """Test getting feedback with timestamp filter in AWS mode."""
        from datetime import timedelta

        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
        )

        mock_dynamodb = MagicMock()
        recent_ts = datetime.now(timezone.utc) - timedelta(hours=1)
        old_ts = datetime.now(timezone.utc) - timedelta(days=30)
        mock_dynamodb.query.return_value = {
            "Items": [
                {
                    "feedback_id": {"S": "recent-1"},
                    "job_id": {"S": "job-1"},
                    "organization_id": {"S": "org-001"},
                    "documentation_type": {"S": "diagram"},
                    "raw_confidence": {"N": "0.85"},
                    "feedback_type": {"S": "accurate"},
                    "timestamp": {"S": recent_ts.isoformat()},
                },
                {
                    "feedback_id": {"S": "old-1"},
                    "job_id": {"S": "job-2"},
                    "organization_id": {"S": "org-001"},
                    "documentation_type": {"S": "diagram"},
                    "raw_confidence": {"N": "0.75"},
                    "feedback_type": {"S": "inaccurate"},
                    "timestamp": {"S": old_ts.isoformat()},
                },
            ]
        }
        mock_boto_client.return_value = mock_dynamodb

        service = FeedbackLearningService(use_mock=False, table_name="test-table")

        # Filter by timestamp
        min_ts = datetime.now(timezone.utc) - timedelta(days=7)
        records = service.get_feedback_for_calibration("org-001", min_timestamp=min_ts)

        # Should only return the recent record
        assert len(records) == 1
        assert records[0].feedback_id == "recent-1"

    @patch("boto3.client")
    def test_get_feedback_for_calibration_aws_mode_failure(self, mock_boto_client):
        """Test getting feedback handles AWS errors."""
        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
        )

        mock_dynamodb = MagicMock()
        mock_dynamodb.query.side_effect = Exception("DynamoDB error")
        mock_boto_client.return_value = mock_dynamodb

        service = FeedbackLearningService(use_mock=False, table_name="test-table")

        records = service.get_feedback_for_calibration("org-001")

        assert records == []

    @patch("boto3.client")
    def test_get_feedback_count_aws_mode(self, mock_boto_client):
        """Test getting feedback count in AWS mode."""
        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
        )

        mock_dynamodb = MagicMock()
        mock_dynamodb.query.return_value = {"Count": 42}
        mock_boto_client.return_value = mock_dynamodb

        service = FeedbackLearningService(use_mock=False, table_name="test-table")

        count = service.get_feedback_count("org-001")

        assert count == 42
        mock_dynamodb.query.assert_called_once()

    @patch("boto3.client")
    def test_get_feedback_count_aws_mode_failure(self, mock_boto_client):
        """Test getting feedback count handles AWS errors."""
        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
        )

        mock_dynamodb = MagicMock()
        mock_dynamodb.query.side_effect = Exception("DynamoDB error")
        mock_boto_client.return_value = mock_dynamodb

        service = FeedbackLearningService(use_mock=False, table_name="test-table")

        count = service.get_feedback_count("org-001")

        assert count == 0

    def test_get_client_returns_none_in_mock_mode(self):
        """Test _get_client returns None in mock mode."""
        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
        )

        service = FeedbackLearningService(use_mock=True)
        client = service._get_client()

        assert client is None

    @patch("boto3.client")
    def test_get_client_creates_dynamodb_client(self, mock_boto_client):
        """Test _get_client creates DynamoDB client."""
        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
        )

        mock_dynamodb = MagicMock()
        mock_boto_client.return_value = mock_dynamodb

        service = FeedbackLearningService(use_mock=False)
        client = service._get_client()

        assert client is not None
        mock_boto_client.assert_called_once_with("dynamodb")

    @patch("boto3.client")
    def test_get_client_reuses_existing_client(self, mock_boto_client):
        """Test _get_client reuses existing client."""
        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
        )

        mock_dynamodb = MagicMock()
        mock_boto_client.return_value = mock_dynamodb

        service = FeedbackLearningService(use_mock=False)
        client1 = service._get_client()
        client2 = service._get_client()

        assert client1 is client2
        mock_boto_client.assert_called_once()


class TestCalibrationMetricsServiceAwsMode:
    """Tests for CalibrationMetricsService in AWS mode."""

    @patch("boto3.client")
    def test_record_ece_aws_mode(self, mock_boto_client):
        """Test recording ECE in AWS mode."""
        from src.services.documentation.confidence_calibration import (
            CalibrationMetricsService,
        )

        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch

        service = CalibrationMetricsService(use_mock=False)
        service.record_ece(
            "org-001", 0.15, documentation_type="diagram", is_calibrated=True
        )

        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args
        assert call_args[1]["Namespace"] == "Aura/DocumentationAgent"

    @patch("boto3.client")
    def test_record_ece_aws_mode_failure(self, mock_boto_client):
        """Test recording ECE handles AWS errors gracefully."""
        from src.services.documentation.confidence_calibration import (
            CalibrationMetricsService,
        )

        mock_cloudwatch = MagicMock()
        mock_cloudwatch.put_metric_data.side_effect = Exception("CloudWatch error")
        mock_boto_client.return_value = mock_cloudwatch

        service = CalibrationMetricsService(use_mock=False)
        # Should not raise, just log the error
        service.record_ece("org-001", 0.15)

    @patch("boto3.client")
    def test_record_calibration_event_aws_mode(self, mock_boto_client):
        """Test recording calibration event in AWS mode."""
        from src.services.documentation.confidence_calibration import (
            CalibrationMetricsService,
        )

        mock_cloudwatch = MagicMock()
        mock_boto_client.return_value = mock_cloudwatch

        service = CalibrationMetricsService(use_mock=False)
        service.record_calibration_event(
            organization_id="org-001",
            sample_count=150,
            ece_before=0.25,
            ece_after=0.08,
            model_version=2,
        )

        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args
        metric_data = call_args[1]["MetricData"]
        assert len(metric_data) == 2
        # First metric should be CalibrationImprovement
        assert metric_data[0]["MetricName"] == "CalibrationImprovement"
        # Second metric should be CalibrationSamples
        assert metric_data[1]["MetricName"] == "CalibrationSamples"
        assert metric_data[1]["Value"] == 150

    @patch("boto3.client")
    def test_record_calibration_event_aws_mode_failure(self, mock_boto_client):
        """Test recording calibration event handles AWS errors gracefully."""
        from src.services.documentation.confidence_calibration import (
            CalibrationMetricsService,
        )

        mock_cloudwatch = MagicMock()
        mock_cloudwatch.put_metric_data.side_effect = Exception("CloudWatch error")
        mock_boto_client.return_value = mock_cloudwatch

        service = CalibrationMetricsService(use_mock=False)
        # Should not raise, just log the error
        service.record_calibration_event(
            organization_id="org-001",
            sample_count=100,
            ece_before=0.20,
            ece_after=0.10,
            model_version=1,
        )

    def test_record_calibration_event_zero_ece_before(self):
        """Test calibration event with zero ECE before (division by zero edge case)."""
        from src.services.documentation.confidence_calibration import (
            CalibrationMetricsService,
        )

        service = CalibrationMetricsService(use_mock=True)
        # Should not raise even with zero ece_before
        service.record_calibration_event(
            organization_id="org-001",
            sample_count=100,
            ece_before=0.0,
            ece_after=0.0,
            model_version=1,
        )

        metrics = service.get_mock_metrics()
        assert len(metrics) == 1
        assert metrics[0]["improvement"] == 0.0


class TestGetStatsEdgeCases:
    """Tests for get_stats edge cases."""

    @pytest.mark.skipif(
        not __import__(
            "src.services.documentation.confidence_calibration",
            fromlist=["SKLEARN_AVAILABLE"],
        ).SKLEARN_AVAILABLE,
        reason="sklearn not available",
    )
    def test_get_stats_ece_improvement_calculation(self):
        """Test ECE improvement calculation in stats."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer(min_samples_for_calibration=10)

        # Create training data
        raw_scores = [i / 20 for i in range(20)]
        outcomes = [1.0 if i > 10 else 0.0 for i in range(20)]
        scorer.fit(raw_scores, outcomes)

        stats = scorer.get_stats()

        # ECE improvement should be calculated
        if stats["ece_before"] > 0:
            expected_improvement = (
                (stats["ece_before"] - stats["ece_after"]) / stats["ece_before"] * 100
            )
            assert abs(stats["ece_improvement"] - expected_improvement) < 0.01

    def test_get_stats_ece_improvement_zero_before(self):
        """Test ECE improvement when ece_before is 0."""
        from src.services.documentation.confidence_calibration import (
            CalibratedConfidenceScorer,
        )

        scorer = CalibratedConfidenceScorer()
        stats = scorer.get_stats()

        # Should handle zero division gracefully
        assert stats["ece_improvement"] == 0.0


class TestFeedbackLearningServiceGetStatsAws:
    """Tests for FeedbackLearningService get_stats in AWS mode."""

    @patch("boto3.client")
    def test_get_stats_aws_mode(self, mock_boto_client):
        """Test get_stats in AWS mode returns count-only result."""
        from src.services.documentation.confidence_calibration import (
            FeedbackLearningService,
        )

        mock_dynamodb = MagicMock()
        mock_dynamodb.query.return_value = {"Count": 25}
        mock_boto_client.return_value = mock_dynamodb

        service = FeedbackLearningService(use_mock=False, table_name="test-table")

        stats = service.get_stats("org-001")

        # AWS mode only returns total count (aggregation not implemented)
        assert stats["total_feedback"] == 25


class TestIntegration:
    """Integration tests for calibration workflow."""

    def test_full_calibration_workflow(self):
        """Test complete calibration workflow."""
        from src.services.documentation.confidence_calibration import (
            SKLEARN_AVAILABLE,
            CalibratedConfidenceScorer,
            CalibrationMetricsService,
            DocumentationType,
            FeedbackLearningService,
            FeedbackRecord,
            FeedbackType,
        )

        # Initialize services
        feedback_service = FeedbackLearningService(use_mock=True)
        metrics_service = CalibrationMetricsService(use_mock=True)
        scorer = CalibratedConfidenceScorer(
            min_samples_for_calibration=20,
            organization_id="org-001",
        )

        # Simulate user feedback collection
        for i in range(30):
            raw_score = i / 30  # 0.0 to 0.97
            # Simulate: high confidence tends to be accurate
            is_accurate = raw_score > 0.5 and i % 3 != 0

            record = FeedbackRecord(
                feedback_id=f"feedback-{i}",
                job_id=f"job-{i}",
                organization_id="org-001",
                documentation_type=DocumentationType.DIAGRAM,
                feedback_type=(
                    FeedbackType.ACCURATE if is_accurate else FeedbackType.INACCURATE
                ),
                raw_confidence=raw_score,
            )
            feedback_service.store_feedback(record)

        # Get feedback and train calibrator
        feedback = feedback_service.get_feedback_for_calibration("org-001")
        assert len(feedback) == 30

        # Extract training data
        raw_scores = [f.raw_confidence for f in feedback]
        outcomes = [f.actual_accuracy for f in feedback]

        # Train calibrator
        success = scorer.fit(raw_scores, outcomes)

        if SKLEARN_AVAILABLE:
            assert success is True
            assert scorer.is_calibrated is True

            # Verify calibration improves ECE
            stats = scorer.get_stats()
            # ECE after should be lower than before (or at least not much worse)
            assert stats["ece_after"] <= stats["ece_before"] + 0.1

            # Record metrics
            metrics_service.record_calibration_event(
                organization_id="org-001",
                sample_count=30,
                ece_before=stats["ece_before"],
                ece_after=stats["ece_after"],
                model_version=stats["model_version"],
            )

            # Test calibration
            calibrated_low = scorer.calibrate(0.2)
            calibrated_high = scorer.calibrate(0.9)

            # Higher raw scores should still calibrate to higher values
            assert calibrated_high > calibrated_low
        else:
            # Without sklearn, fit should return False
            assert success is False

    def test_multi_organization_calibration(self):
        """Test calibration for multiple organizations."""
        from src.services.documentation.confidence_calibration import (
            SKLEARN_AVAILABLE,
            CalibratedConfidenceScorer,
            DocumentationType,
            FeedbackLearningService,
            FeedbackRecord,
            FeedbackType,
        )

        feedback_service = FeedbackLearningService(use_mock=True)

        # Store feedback for multiple organizations
        for org in ["org-001", "org-002", "org-003"]:
            for i in range(25):
                record = FeedbackRecord(
                    feedback_id=f"{org}-feedback-{i}",
                    job_id=f"{org}-job-{i}",
                    organization_id=org,
                    documentation_type=DocumentationType.DIAGRAM,
                    feedback_type=(
                        FeedbackType.ACCURATE if i % 2 == 0 else FeedbackType.INACCURATE
                    ),
                    raw_confidence=0.5 + (i % 10) * 0.05,
                )
                feedback_service.store_feedback(record)

        # Create and train scorer for each org
        scorers = {}
        for org in ["org-001", "org-002", "org-003"]:
            scorer = CalibratedConfidenceScorer(
                min_samples_for_calibration=20,
                organization_id=org,
            )

            feedback = feedback_service.get_feedback_for_calibration(org)
            assert len(feedback) == 25

            raw_scores = [f.raw_confidence for f in feedback]
            outcomes = [f.actual_accuracy for f in feedback]

            scorer.fit(raw_scores, outcomes)
            scorers[org] = scorer

        # Check scorers based on sklearn availability
        for org, scorer in scorers.items():
            if SKLEARN_AVAILABLE:
                assert scorer.is_calibrated is True
            else:
                assert scorer.is_calibrated is False
            assert scorer.organization_id == org
