"""
Tests for the calibration pipeline Lambda function.

ADR-056 Phase 1.5 - Confidence Calibration Infrastructure
"""

import importlib
import importlib.util
import json
import os
import platform
import sys
from unittest.mock import MagicMock, patch

import pytest

# Platform-specific test isolation
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

# Check sklearn availability
try:
    from sklearn.isotonic import IsotonicRegression  # noqa: F401

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


# Import module with reserved keyword in path
def _import_calibration_pipeline():
    """Import calibration_pipeline from src.lambda package."""
    # lambda is a reserved keyword, so we use importlib
    spec = importlib.util.spec_from_file_location(
        "calibration_pipeline", "src/lambda/calibration_pipeline.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["calibration_pipeline"] = module
    spec.loader.exec_module(module)
    return module


calibration_pipeline = _import_calibration_pipeline()


class TestCalibrationResult:
    """Tests for CalibrationResult dataclass."""

    def test_calibration_result_creation(self):
        """Test CalibrationResult can be created."""
        CalibrationResult = calibration_pipeline.CalibrationResult

        result = CalibrationResult(
            execution_id="test-123",
            timestamp="2026-01-06T00:00:00Z",
            organizations_processed=10,
            organizations_calibrated=8,
            organizations_skipped=2,
            total_feedback_records=1500,
            models_updated=8,
            avg_ece_before=0.25,
            avg_ece_after=0.08,
            avg_improvement_percent=68.0,
        )

        assert result.execution_id == "test-123"
        assert result.organizations_processed == 10
        assert result.organizations_calibrated == 8
        assert result.organizations_skipped == 2
        assert result.total_feedback_records == 1500
        assert result.models_updated == 8
        assert result.avg_ece_before == 0.25
        assert result.avg_ece_after == 0.08
        assert result.avg_improvement_percent == 68.0
        assert result.errors == []
        assert result.org_summaries == []

    def test_calibration_result_to_dict(self):
        """Test CalibrationResult to_dict method."""
        CalibrationResult = calibration_pipeline.CalibrationResult

        result = CalibrationResult(
            execution_id="test-123",
            timestamp="2026-01-06T00:00:00Z",
            organizations_processed=5,
            organizations_calibrated=3,
            organizations_skipped=2,
            total_feedback_records=500,
            models_updated=3,
            avg_ece_before=0.2,
            avg_ece_after=0.05,
            avg_improvement_percent=75.0,
            errors=["Error 1"],
            org_summaries=[{"org": "test"}],
        )

        result_dict = result.to_dict()

        assert result_dict["execution_id"] == "test-123"
        assert result_dict["organizations_processed"] == 5
        assert result_dict["errors"] == ["Error 1"]
        assert result_dict["org_summaries"] == [{"org": "test"}]


class TestCalculateECE:
    """Tests for calculate_ece function."""

    def test_perfect_calibration(self):
        """Test ECE for perfectly calibrated predictions."""
        calculate_ece = calibration_pipeline.calculate_ece

        # Perfect calibration: predicted = actual
        predicted = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        actual = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

        ece = calculate_ece(predicted, actual)

        assert ece < 0.15  # Near-perfect calibration

    def test_poor_calibration(self):
        """Test ECE for poorly calibrated predictions."""
        calculate_ece = calibration_pipeline.calculate_ece

        # Always predict 0.9 when actual is 0.1
        predicted = [0.9, 0.9, 0.9, 0.9, 0.9]
        actual = [0.1, 0.1, 0.1, 0.1, 0.1]

        ece = calculate_ece(predicted, actual)

        assert ece > 0.5  # Poor calibration

    def test_empty_input(self):
        """Test ECE with empty input."""
        calculate_ece = calibration_pipeline.calculate_ece

        assert calculate_ece([], []) == 1.0

    def test_mismatched_lengths(self):
        """Test ECE with mismatched input lengths."""
        calculate_ece = calibration_pipeline.calculate_ece

        assert calculate_ece([0.5, 0.6], [0.5]) == 1.0


class TestTrainCalibrator:
    """Tests for train_calibrator function."""

    @pytest.mark.skipif(not HAS_SKLEARN, reason="sklearn required")
    def test_train_with_valid_data(self):
        """Test training calibrator with valid data."""
        train_calibrator = calibration_pipeline.train_calibrator

        feedback = [
            {"raw_confidence": 0.1, "feedback_type": "inaccurate"},
            {"raw_confidence": 0.2, "feedback_type": "inaccurate"},
            {"raw_confidence": 0.3, "feedback_type": "inaccurate"},
            {"raw_confidence": 0.7, "feedback_type": "accurate"},
            {"raw_confidence": 0.8, "feedback_type": "accurate"},
            {"raw_confidence": 0.9, "feedback_type": "accurate"},
        ]

        calibrator, ece_before, ece_after = train_calibrator(feedback)

        assert calibrator is not None
        assert 0.0 <= ece_before <= 1.0
        assert 0.0 <= ece_after <= 1.0

    @pytest.mark.skipif(not HAS_SKLEARN, reason="sklearn required")
    def test_train_with_partial_feedback(self):
        """Test training with partial feedback type."""
        train_calibrator = calibration_pipeline.train_calibrator

        feedback = [
            {"raw_confidence": 0.5, "feedback_type": "partial"},
            {"raw_confidence": 0.6, "feedback_type": "partial"},
        ]

        calibrator, ece_before, ece_after = train_calibrator(feedback)

        assert calibrator is not None

    def test_train_with_insufficient_data(self):
        """Test training with insufficient data returns None."""
        train_calibrator = calibration_pipeline.train_calibrator

        feedback = [{"raw_confidence": 0.5, "feedback_type": "accurate"}]

        calibrator, ece_before, ece_after = train_calibrator(feedback)

        assert calibrator is None
        assert ece_before == 1.0
        assert ece_after == 1.0

    def test_train_with_invalid_feedback_type(self):
        """Test training skips invalid feedback types."""
        train_calibrator = calibration_pipeline.train_calibrator

        feedback = [
            {"raw_confidence": 0.5, "feedback_type": "unknown"},
            {"raw_confidence": 0.6, "feedback_type": "invalid"},
        ]

        calibrator, ece_before, ece_after = train_calibrator(feedback)

        # Should return None since no valid records
        assert calibrator is None


class TestHandler:
    """Tests for Lambda handler function."""

    @patch.dict(os.environ, {"USE_MOCK": "true", "ENVIRONMENT": "dev"})
    def test_handler_mock_mode(self):
        """Test handler in mock mode."""
        handler = calibration_pipeline.handler

        event = {
            "detail-type": "Scheduled Event",
            "source": "aws.events",
        }

        result = handler(event, None)

        assert result["statusCode"] == 200

        body = json.loads(result["body"])
        assert body["organizations_processed"] == 3
        assert body["organizations_calibrated"] == 2
        assert body["organizations_skipped"] == 1
        assert body["total_feedback_records"] == 350
        assert body["models_updated"] == 2
        assert body["avg_ece_before"] == 0.25
        assert body["avg_ece_after"] == 0.08
        assert body["avg_improvement_percent"] == 68.0

    @patch.dict(os.environ, {"USE_MOCK": "true", "MIN_SAMPLES": "50"})
    def test_handler_respects_min_samples(self):
        """Test handler respects MIN_SAMPLES environment variable."""
        handler = calibration_pipeline.handler

        event = {}
        result = handler(event, None)

        assert result["statusCode"] == 200

    @patch.object(calibration_pipeline, "boto3")
    @patch.dict(
        os.environ,
        {
            "USE_MOCK": "false",
            "ENVIRONMENT": "dev",
            "S3_BUCKET": "test-bucket",
            "DYNAMODB_TABLE": "test-table",
            "MIN_SAMPLES": "10",
        },
    )
    def test_handler_aws_mode_no_organizations(self, mock_boto):
        """Test handler in AWS mode with no organizations."""
        handler = calibration_pipeline.handler

        mock_dynamodb = MagicMock()
        mock_dynamodb.get_paginator.return_value.paginate.return_value = [{"Items": []}]
        mock_boto.client.return_value = mock_dynamodb

        event = {}
        result = handler(event, None)

        assert result["statusCode"] == 200

        body = json.loads(result["body"])
        assert body["organizations_processed"] == 0

    @pytest.mark.skipif(not HAS_SKLEARN, reason="sklearn required")
    @patch.object(calibration_pipeline, "send_notification")
    @patch.object(calibration_pipeline, "record_cloudwatch_metrics")
    @patch.object(calibration_pipeline, "get_current_model_version")
    @patch.object(calibration_pipeline, "save_calibrator_to_s3")
    @patch.object(calibration_pipeline, "query_feedback_by_organization")
    @patch.object(calibration_pipeline, "list_organizations")
    @patch.object(calibration_pipeline, "boto3")
    @patch.dict(
        os.environ,
        {
            "USE_MOCK": "false",
            "ENVIRONMENT": "dev",
            "S3_BUCKET": "test-bucket",
            "DYNAMODB_TABLE": "test-table",
            "MIN_SAMPLES": "5",
            "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test-topic",
        },
    )
    def test_handler_full_calibration_flow(
        self,
        mock_boto,
        mock_orgs,
        mock_feedback,
        mock_save,
        mock_version,
        mock_metrics,
        mock_notification,
    ):
        """Test handler with full calibration flow."""
        handler = calibration_pipeline.handler

        # Setup mocks
        mock_orgs.return_value = ["org-001", "org-002"]

        mock_feedback.side_effect = [
            # org-001: 10 samples
            [
                {
                    "raw_confidence": i / 10,
                    "feedback_type": "accurate" if i > 5 else "inaccurate",
                }
                for i in range(10)
            ],
            # org-002: 3 samples (insufficient)
            [{"raw_confidence": 0.5, "feedback_type": "accurate"} for _ in range(3)],
        ]

        mock_version.return_value = 0
        mock_save.return_value = True

        event = {}
        result = handler(event, None)

        assert result["statusCode"] == 200

        body = json.loads(result["body"])
        assert body["organizations_processed"] == 2
        assert body["organizations_calibrated"] == 1  # org-001 calibrated
        assert body["organizations_skipped"] == 1  # org-002 skipped

        # Verify metrics were recorded for calibrated org
        assert mock_metrics.call_count == 1

        # Verify notification was sent
        assert mock_notification.call_count == 1


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_list_organizations(self):
        """Test list_organizations function."""
        list_organizations = calibration_pipeline.list_organizations

        mock_client = MagicMock()
        mock_client.get_paginator.return_value.paginate.return_value = [
            {
                "Items": [
                    {"organization_id": {"S": "org-001"}},
                    {"organization_id": {"S": "org-002"}},
                    {"organization_id": {"S": "org-001"}},  # Duplicate
                ]
            }
        ]

        orgs = list_organizations(mock_client, "test-table")

        assert len(orgs) == 2
        assert "org-001" in orgs
        assert "org-002" in orgs

    def test_query_feedback_by_organization(self):
        """Test query_feedback_by_organization function."""
        query_feedback_by_organization = (
            calibration_pipeline.query_feedback_by_organization
        )

        mock_client = MagicMock()
        mock_client.get_paginator.return_value.paginate.return_value = [
            {
                "Items": [
                    {
                        "feedback_id": {"S": "fb-001"},
                        "organization_id": {"S": "org-001"},
                        "raw_confidence": {"N": "0.85"},
                        "feedback_type": {"S": "accurate"},
                        "documentation_type": {"S": "diagram"},
                        "created_at": {"S": "2026-01-06T00:00:00Z"},
                    }
                ]
            }
        ]

        feedback = query_feedback_by_organization(mock_client, "test-table", "org-001")

        assert len(feedback) == 1
        assert feedback[0]["feedback_id"] == "fb-001"
        assert feedback[0]["organization_id"] == "org-001"
        assert feedback[0]["raw_confidence"] == 0.85
        assert feedback[0]["feedback_type"] == "accurate"

    @pytest.mark.skipif(not HAS_SKLEARN, reason="sklearn required")
    def test_save_calibrator_to_s3(self):
        """Test save_calibrator_to_s3 function."""
        from sklearn.isotonic import IsotonicRegression

        save_calibrator_to_s3 = calibration_pipeline.save_calibrator_to_s3

        mock_client = MagicMock()

        calibrator = IsotonicRegression(y_min=0.0, y_max=1.0)
        calibrator.fit([0.1, 0.5, 0.9], [0.0, 0.5, 1.0])

        result = save_calibrator_to_s3(
            mock_client, "test-bucket", "org-001", calibrator, 1
        )

        assert result is True
        assert mock_client.put_object.call_count == 2  # version + latest

    def test_get_current_model_version_exists(self):
        """Test get_current_model_version when model exists."""
        get_current_model_version = calibration_pipeline.get_current_model_version

        mock_client = MagicMock()
        mock_client.head_object.return_value = {"Metadata": {"model_version": "5"}}

        version = get_current_model_version(mock_client, "test-bucket", "org-001")

        assert version == 5

    def test_get_current_model_version_not_exists(self):
        """Test get_current_model_version when model doesn't exist."""
        from botocore.exceptions import ClientError

        get_current_model_version = calibration_pipeline.get_current_model_version

        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )

        version = get_current_model_version(mock_client, "test-bucket", "org-001")

        assert version == 0

    def test_record_cloudwatch_metrics(self):
        """Test record_cloudwatch_metrics function."""
        record_cloudwatch_metrics = calibration_pipeline.record_cloudwatch_metrics

        mock_client = MagicMock()

        record_cloudwatch_metrics(
            mock_client,
            "TestNamespace",
            "org-001",
            ece_before=0.25,
            ece_after=0.08,
            sample_count=150,
        )

        mock_client.put_metric_data.assert_called_once()
        call_args = mock_client.put_metric_data.call_args
        assert call_args[1]["Namespace"] == "TestNamespace"
        assert (
            len(call_args[1]["MetricData"]) == 4
        )  # ECE before, after, sample count, improvement

    def test_send_notification(self):
        """Test send_notification function."""
        CalibrationResult = calibration_pipeline.CalibrationResult
        send_notification = calibration_pipeline.send_notification

        mock_client = MagicMock()

        result = CalibrationResult(
            execution_id="test-123",
            timestamp="2026-01-06T00:00:00Z",
            organizations_processed=5,
            organizations_calibrated=3,
            organizations_skipped=2,
            total_feedback_records=500,
            models_updated=3,
            avg_ece_before=0.2,
            avg_ece_after=0.05,
            avg_improvement_percent=75.0,
        )

        send_notification(
            mock_client, "arn:aws:sns:us-east-1:123456789012:test-topic", result
        )

        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        assert "Calibration Complete" in call_args[1]["Subject"]

    def test_send_notification_no_topic(self):
        """Test send_notification with no topic ARN."""
        CalibrationResult = calibration_pipeline.CalibrationResult
        send_notification = calibration_pipeline.send_notification

        result = CalibrationResult(
            execution_id="test-123",
            timestamp="2026-01-06T00:00:00Z",
            organizations_processed=0,
            organizations_calibrated=0,
            organizations_skipped=0,
            total_feedback_records=0,
            models_updated=0,
            avg_ece_before=0.0,
            avg_ece_after=0.0,
            avg_improvement_percent=0.0,
        )

        # Should not raise when topic_arn is empty
        send_notification(MagicMock(), "", result)


class TestOrganizationCalibration:
    """Tests for OrganizationCalibration dataclass."""

    def test_organization_calibration_creation(self):
        """Test OrganizationCalibration can be created."""
        OrganizationCalibration = calibration_pipeline.OrganizationCalibration

        org_cal = OrganizationCalibration(
            organization_id="org-001",
            sample_count=150,
            ece_before=0.25,
            ece_after=0.08,
            improvement_percent=68.0,
            model_version=3,
            calibrated=True,
        )

        assert org_cal.organization_id == "org-001"
        assert org_cal.sample_count == 150
        assert org_cal.ece_before == 0.25
        assert org_cal.ece_after == 0.08
        assert org_cal.improvement_percent == 68.0
        assert org_cal.model_version == 3
        assert org_cal.calibrated is True
        assert org_cal.error is None

    def test_organization_calibration_with_error(self):
        """Test OrganizationCalibration with error."""
        OrganizationCalibration = calibration_pipeline.OrganizationCalibration

        org_cal = OrganizationCalibration(
            organization_id="org-002",
            sample_count=50,
            ece_before=0.0,
            ece_after=0.0,
            improvement_percent=0.0,
            model_version=0,
            calibrated=False,
            error="Insufficient samples",
        )

        assert org_cal.calibrated is False
        assert org_cal.error == "Insufficient samples"
