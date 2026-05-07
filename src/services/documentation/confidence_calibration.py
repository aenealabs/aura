"""
Confidence Calibration Service
==============================

Implements confidence score calibration using isotonic regression
to improve documentation accuracy predictions over time.

ADR-056: Documentation Agent - Phase 1.5 Confidence Calibration

The calibration pipeline:
1. Collect user feedback on documentation accuracy
2. Store raw scores and actual outcomes in DynamoDB
3. Train isotonic regression model on collected data
4. Apply calibration to transform raw scores to calibrated scores

Isotonic regression ensures:
- Monotonicity: Higher raw scores always map to higher calibrated scores
- Better probability calibration: Scores reflect true accuracy probabilities
- ECE (Expected Calibration Error) improvement over time
"""

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

# Optional sklearn import for isotonic regression
try:
    from sklearn.isotonic import IsotonicRegression

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("sklearn not available. Calibration will be disabled.")

if TYPE_CHECKING:
    import boto3


class FeedbackType(Enum):
    """Type of user feedback on documentation."""

    ACCURATE = "accurate"  # Documentation was accurate
    INACCURATE = "inaccurate"  # Documentation was inaccurate
    PARTIAL = "partial"  # Partially accurate


class DocumentationType(Enum):
    """Type of documentation being rated."""

    DIAGRAM = "diagram"
    REPORT = "report"
    SERVICE_BOUNDARY = "service_boundary"
    DATA_FLOW = "data_flow"


@dataclass
class FeedbackRecord:
    """Record of user feedback on documentation.

    Attributes:
        feedback_id: Unique feedback identifier
        job_id: Documentation job ID
        organization_id: Organization that owns this feedback
        documentation_type: Type of documentation rated
        diagram_type: Specific diagram type (if applicable)
        raw_confidence: Original raw confidence score (0.0-1.0)
        feedback_type: User's feedback (accurate/inaccurate/partial)
        actual_accuracy: Derived accuracy (1.0 for accurate, 0.0 for inaccurate, 0.5 for partial)
        user_id: ID of user providing feedback
        correction_text: Optional text correction from user
        timestamp: When feedback was submitted
        metadata: Additional metadata
    """

    feedback_id: str
    job_id: str
    organization_id: str
    documentation_type: DocumentationType
    raw_confidence: float
    feedback_type: FeedbackType
    user_id: str = ""
    diagram_type: str = ""
    correction_text: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def actual_accuracy(self) -> float:
        """Convert feedback type to numeric accuracy."""
        if self.feedback_type == FeedbackType.ACCURATE:
            return 1.0
        elif self.feedback_type == FeedbackType.INACCURATE:
            return 0.0
        else:  # PARTIAL
            return 0.5


@dataclass
class CalibrationModel:
    """Calibration model with metadata.

    Attributes:
        model_id: Unique model identifier
        organization_id: Organization this model is for
        documentation_type: Type of documentation (or 'all')
        sample_count: Number of samples used for training
        ece_before: ECE before calibration
        ece_after: ECE after calibration
        trained_at: When model was trained
        version: Model version
        is_active: Whether this model is active
    """

    model_id: str
    organization_id: str
    documentation_type: str = "all"
    sample_count: int = 0
    ece_before: float = 0.0
    ece_after: float = 0.0
    trained_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    is_active: bool = True


class CalibratedConfidenceScorer:
    """
    Calibrated confidence scorer using isotonic regression.

    Isotonic regression transforms raw confidence scores to calibrated
    scores that better reflect true accuracy probabilities. The calibrator
    is trained on user feedback data.

    Features:
    - Per-organization calibration models
    - Per-documentation-type calibration (optional)
    - Minimum sample threshold before calibration activates
    - Thread-safe calibrator access
    - Fallback to raw scores when uncalibrated

    Example:
        >>> scorer = CalibratedConfidenceScorer(min_samples=100)
        >>> # Before calibration (returns raw score)
        >>> scorer.calibrate(0.75)
        0.75
        >>> # After training with 100+ samples
        >>> scorer.fit(raw_scores, actual_outcomes)
        >>> scorer.calibrate(0.75)
        0.82  # Calibrated score
    """

    def __init__(
        self,
        min_samples_for_calibration: int = 100,
        organization_id: str = "default",
        documentation_type: str = "all",
    ):
        """
        Initialize the calibrated confidence scorer.

        Args:
            min_samples_for_calibration: Minimum samples before calibration activates
            organization_id: Organization ID for per-org calibration
            documentation_type: Documentation type for type-specific calibration
        """
        self.min_samples = min_samples_for_calibration
        self.organization_id = organization_id
        self.documentation_type = documentation_type

        # Thread-safe access to calibrator
        self._lock = threading.RLock()
        self._calibrator: "IsotonicRegression | None" = None
        self._is_calibrated = False
        self._sample_count = 0
        self._model_version = 0

        # Metrics
        self._ece_before = 0.0
        self._ece_after = 0.0

        logger.info(
            f"CalibratedConfidenceScorer initialized: "
            f"org={organization_id}, type={documentation_type}, "
            f"min_samples={min_samples_for_calibration}"
        )

    @property
    def is_calibrated(self) -> bool:
        """Check if calibrator has been trained with sufficient data."""
        with self._lock:
            return self._is_calibrated

    @property
    def sample_count(self) -> int:
        """Get number of samples used for calibration."""
        with self._lock:
            return self._sample_count

    @property
    def model_version(self) -> int:
        """Get current model version."""
        with self._lock:
            return self._model_version

    def fit(
        self,
        raw_scores: list[float],
        actual_outcomes: list[float],
    ) -> bool:
        """
        Fit the isotonic regression calibrator on feedback data.

        Args:
            raw_scores: List of raw confidence scores (0.0-1.0)
            actual_outcomes: List of actual accuracy outcomes (0.0-1.0)

        Returns:
            True if calibration was successful

        Raises:
            ValueError: If inputs are invalid
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("sklearn not available, calibration disabled")
            return False

        if len(raw_scores) != len(actual_outcomes):
            raise ValueError(
                f"raw_scores and actual_outcomes must have same length: "
                f"{len(raw_scores)} vs {len(actual_outcomes)}"
            )

        if len(raw_scores) < self.min_samples:
            logger.info(
                f"Insufficient samples for calibration: "
                f"{len(raw_scores)} < {self.min_samples}"
            )
            return False

        # Validate ranges
        for score in raw_scores:
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"Raw score out of range: {score}")
        for outcome in actual_outcomes:
            if not 0.0 <= outcome <= 1.0:
                raise ValueError(f"Actual outcome out of range: {outcome}")

        # Calculate ECE before calibration
        self._ece_before = self._calculate_ece(raw_scores, actual_outcomes)

        with self._lock:
            try:
                calibrator = IsotonicRegression(out_of_bounds="clip")
                calibrator.fit(raw_scores, actual_outcomes)

                # Calculate ECE after calibration
                calibrated = calibrator.predict(raw_scores)
                self._ece_after = self._calculate_ece(list(calibrated), actual_outcomes)

                self._calibrator = calibrator
                self._is_calibrated = True
                self._sample_count = len(raw_scores)
                self._model_version += 1

                logger.info(
                    f"Calibrator trained: samples={len(raw_scores)}, "
                    f"ECE before={self._ece_before:.4f}, after={self._ece_after:.4f}, "
                    f"improvement={((self._ece_before - self._ece_after) / self._ece_before * 100):.1f}%"
                )
                return True

            except Exception as e:
                logger.error(f"Failed to fit calibrator: {e}")
                return False

    def calibrate(self, raw_score: float) -> float:
        """
        Calibrate a raw confidence score.

        Args:
            raw_score: Raw confidence score (0.0-1.0)

        Returns:
            Calibrated score if calibrator is trained, otherwise raw score
        """
        if not 0.0 <= raw_score <= 1.0:
            raise ValueError(f"Raw score out of range: {raw_score}")

        with self._lock:
            if not self._is_calibrated or self._calibrator is None:
                return raw_score

            try:
                calibrated = self._calibrator.predict([[raw_score]])[0]
                # Ensure output is in valid range
                return float(max(0.0, min(1.0, calibrated)))
            except Exception as e:
                logger.warning(f"Calibration failed, using raw score: {e}")
                return raw_score

    def calibrate_batch(self, raw_scores: list[float]) -> list[float]:
        """
        Calibrate multiple raw confidence scores.

        Args:
            raw_scores: List of raw confidence scores

        Returns:
            List of calibrated scores
        """
        with self._lock:
            if not self._is_calibrated or self._calibrator is None:
                return raw_scores

            try:
                calibrated = self._calibrator.predict(raw_scores)
                return [float(max(0.0, min(1.0, s))) for s in calibrated]
            except Exception as e:
                logger.warning(f"Batch calibration failed: {e}")
                return raw_scores

    def _calculate_ece(
        self,
        predicted: list[float],
        actual: list[float],
        n_bins: int = 10,
    ) -> float:
        """
        Calculate Expected Calibration Error (ECE).

        ECE measures how well predicted probabilities match actual outcomes.
        Lower ECE indicates better calibration.

        Args:
            predicted: Predicted confidence scores
            actual: Actual outcomes (0 or 1)
            n_bins: Number of bins for ECE calculation

        Returns:
            ECE value (0.0 = perfect calibration)
        """
        if len(predicted) == 0:
            return 0.0

        # Create bins
        bin_totals = [0] * n_bins
        bin_correct = [0.0] * n_bins
        bin_confidence = [0.0] * n_bins

        for pred, act in zip(predicted, actual):
            # Find bin for this prediction
            bin_idx = min(int(pred * n_bins), n_bins - 1)
            bin_totals[bin_idx] += 1
            bin_correct[bin_idx] += act
            bin_confidence[bin_idx] += pred

        # Calculate ECE
        ece = 0.0
        total_samples = len(predicted)
        for i in range(n_bins):
            if bin_totals[i] > 0:
                avg_confidence = bin_confidence[i] / bin_totals[i]
                avg_accuracy = bin_correct[i] / bin_totals[i]
                ece += (bin_totals[i] / total_samples) * abs(
                    avg_accuracy - avg_confidence
                )

        return ece

    def get_stats(self) -> dict[str, Any]:
        """Get calibration statistics."""
        with self._lock:
            return {
                "is_calibrated": self._is_calibrated,
                "sample_count": self._sample_count,
                "min_samples_required": self.min_samples,
                "model_version": self._model_version,
                "ece_before": self._ece_before,
                "ece_after": self._ece_after,
                "ece_improvement": (
                    (self._ece_before - self._ece_after) / self._ece_before * 100
                    if self._ece_before > 0
                    else 0.0
                ),
                "organization_id": self.organization_id,
                "documentation_type": self.documentation_type,
            }

    SERIALIZATION_VERSION = "v2-json"

    def serialize(self) -> bytes:
        """Serialize the calibrator for storage as JSON.

        Replaces the previous ``pickle.dumps`` representation. Pickle is RCE-
        vulnerable if the storage backend's trust boundary is ever weakened
        (CI fixture write, cross-account replication, leaked credentials);
        JSON is value-only and cannot execute attacker-controlled code on
        load. The IsotonicRegression model is reconstructed from its fitted
        thresholds rather than its in-memory object graph.
        """
        with self._lock:
            calibrator_state: dict[str, Any] | None = None
            if self._calibrator is not None and self._is_calibrated:
                calibrator_state = {
                    "X_thresholds_": (
                        self._calibrator.X_thresholds_.tolist()
                        if hasattr(self._calibrator, "X_thresholds_")
                        else None
                    ),
                    "y_thresholds_": (
                        self._calibrator.y_thresholds_.tolist()
                        if hasattr(self._calibrator, "y_thresholds_")
                        else None
                    ),
                    "increasing_": getattr(self._calibrator, "increasing_", "auto"),
                    "X_min_": float(getattr(self._calibrator, "X_min_", 0.0)),
                    "X_max_": float(getattr(self._calibrator, "X_max_", 1.0)),
                    "out_of_bounds": getattr(self._calibrator, "out_of_bounds", "clip"),
                    "y_min": getattr(self._calibrator, "y_min", None),
                    "y_max": getattr(self._calibrator, "y_max", None),
                }
            data = {
                "version": self.SERIALIZATION_VERSION,
                "calibrator": calibrator_state,
                "is_calibrated": self._is_calibrated,
                "sample_count": self._sample_count,
                "model_version": self._model_version,
                "ece_before": self._ece_before,
                "ece_after": self._ece_after,
                "organization_id": self.organization_id,
                "documentation_type": self.documentation_type,
            }
            return json.dumps(data).encode("utf-8")

    def deserialize(self, data: bytes) -> None:
        """Deserialize a calibrator from JSON storage.

        Refuses to load pickle bytes (legacy v1) — historical calibrators must
        be retrained or re-serialized with this version. The check is a
        belt-and-braces measure on top of the JSON contract: pickle starts
        with a protocol byte (\\x80) which is not valid JSON.
        """
        if not data:
            raise ValueError("empty calibrator payload")
        if data[:1] == b"\x80" or data[:2] == b"\x80\x04":
            raise ValueError(
                "Refusing to deserialize pickle calibrator. Re-train and "
                "re-save with the v2-json format (see audit finding C5)."
            )
        loaded = json.loads(data.decode("utf-8"))
        if loaded.get("version") != self.SERIALIZATION_VERSION:
            raise ValueError(
                f"Unsupported calibrator format: {loaded.get('version')!r}. "
                f"Expected {self.SERIALIZATION_VERSION!r}."
            )

        with self._lock:
            calibrator_state = loaded.get("calibrator")
            if calibrator_state is not None and SKLEARN_AVAILABLE:
                import numpy as np

                calibrator = IsotonicRegression(
                    out_of_bounds=calibrator_state.get("out_of_bounds", "clip"),
                    y_min=calibrator_state.get("y_min"),
                    y_max=calibrator_state.get("y_max"),
                    increasing=calibrator_state.get("increasing_", "auto"),
                )
                if calibrator_state.get("X_thresholds_") is not None:
                    calibrator.X_thresholds_ = np.asarray(
                        calibrator_state["X_thresholds_"], dtype=float
                    )
                    calibrator.y_thresholds_ = np.asarray(
                        calibrator_state["y_thresholds_"], dtype=float
                    )
                    calibrator.X_min_ = calibrator_state["X_min_"]
                    calibrator.X_max_ = calibrator_state["X_max_"]
                    calibrator.increasing_ = calibrator_state["increasing_"]
                    calibrator._build_f(
                        calibrator.X_thresholds_, calibrator.y_thresholds_
                    )
                self._calibrator = calibrator
            else:
                self._calibrator = None
            self._is_calibrated = loaded["is_calibrated"]
            self._sample_count = loaded["sample_count"]
            self._model_version = loaded["model_version"]
            self._ece_before = loaded["ece_before"]
            self._ece_after = loaded["ece_after"]
            self.organization_id = loaded["organization_id"]
            self.documentation_type = loaded["documentation_type"]


class FeedbackLearningService:
    """
    Service for collecting and managing user feedback on documentation.

    Stores feedback in DynamoDB for training calibration models.
    Supports per-organization and per-documentation-type feedback.

    Features:
    - Store feedback with <100ms latency target
    - Query feedback by organization, job, or time range
    - Aggregate feedback for calibration training
    - Track feedback statistics
    """

    def __init__(
        self,
        table_name: str = "",
        dynamodb_client: "boto3.client | None" = None,
        use_mock: bool = False,
    ):
        """
        Initialize the feedback learning service.

        Args:
            table_name: DynamoDB table name for feedback storage
            dynamodb_client: Optional DynamoDB client
            use_mock: Use mock storage for testing
        """
        self.table_name = table_name or os.getenv(
            "DOCUMENTATION_FEEDBACK_TABLE", "aura-documentation-feedback-dev"
        )
        self.use_mock = use_mock
        self._client = dynamodb_client

        # Mock storage
        self._mock_feedback: dict[str, FeedbackRecord] = {}

        logger.info(
            f"FeedbackLearningService initialized: table={self.table_name}, "
            f"mock={use_mock}"
        )

    def _get_client(self) -> Any:
        """Get or create DynamoDB client."""
        if self.use_mock:
            return None

        if self._client is None:
            import boto3

            self._client = boto3.client("dynamodb")
        return self._client

    def store_feedback(self, feedback: FeedbackRecord) -> bool:
        """
        Store user feedback.

        Args:
            feedback: Feedback record to store

        Returns:
            True if successful
        """
        if self.use_mock:
            self._mock_feedback[feedback.feedback_id] = feedback
            logger.info(f"[MOCK] Stored feedback: {feedback.feedback_id}")
            return True

        try:
            client = self._get_client()
            item = {
                "feedback_id": {"S": feedback.feedback_id},
                "job_id": {"S": feedback.job_id},
                "organization_id": {"S": feedback.organization_id},
                "documentation_type": {"S": feedback.documentation_type.value},
                "raw_confidence": {"N": str(feedback.raw_confidence)},
                "feedback_type": {"S": feedback.feedback_type.value},
                "actual_accuracy": {"N": str(feedback.actual_accuracy)},
                "user_id": {"S": feedback.user_id},
                "timestamp": {"S": feedback.timestamp.isoformat()},
            }

            if feedback.diagram_type:
                item["diagram_type"] = {"S": feedback.diagram_type}
            if feedback.correction_text:
                item["correction_text"] = {"S": feedback.correction_text}
            if feedback.metadata:
                item["metadata"] = {"S": json.dumps(feedback.metadata)}

            client.put_item(TableName=self.table_name, Item=item)
            logger.info(f"Stored feedback: {feedback.feedback_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store feedback: {e}")
            return False

    def get_feedback_for_calibration(
        self,
        organization_id: str,
        documentation_type: str | None = None,
        min_timestamp: datetime | None = None,
    ) -> list[FeedbackRecord]:
        """
        Get feedback records for calibration training.

        Args:
            organization_id: Organization to get feedback for
            documentation_type: Optional filter by documentation type
            min_timestamp: Optional minimum timestamp filter

        Returns:
            List of feedback records
        """
        if self.use_mock:
            records = list(self._mock_feedback.values())
            records = [r for r in records if r.organization_id == organization_id]
            if documentation_type:
                records = [
                    r
                    for r in records
                    if r.documentation_type.value == documentation_type
                ]
            if min_timestamp:
                records = [r for r in records if r.timestamp >= min_timestamp]
            return records

        try:
            client = self._get_client()

            # Query by organization_id using GSI
            key_condition = "organization_id = :org_id"
            expression_values: dict[str, Any] = {":org_id": {"S": organization_id}}

            if documentation_type:
                key_condition += " AND documentation_type = :doc_type"
                expression_values[":doc_type"] = {"S": documentation_type}

            response = client.query(
                TableName=self.table_name,
                IndexName="organization-type-index",
                KeyConditionExpression=key_condition,
                ExpressionAttributeValues=expression_values,
            )

            records = []
            for item in response.get("Items", []):
                record = FeedbackRecord(
                    feedback_id=item["feedback_id"]["S"],
                    job_id=item["job_id"]["S"],
                    organization_id=item["organization_id"]["S"],
                    documentation_type=DocumentationType(
                        item["documentation_type"]["S"]
                    ),
                    raw_confidence=float(item["raw_confidence"]["N"]),
                    feedback_type=FeedbackType(item["feedback_type"]["S"]),
                    user_id=item.get("user_id", {}).get("S", ""),
                    diagram_type=item.get("diagram_type", {}).get("S", ""),
                    correction_text=item.get("correction_text", {}).get("S", ""),
                    timestamp=datetime.fromisoformat(item["timestamp"]["S"]),
                )
                if min_timestamp is None or record.timestamp >= min_timestamp:
                    records.append(record)

            return records

        except Exception as e:
            logger.error(f"Failed to get feedback: {e}")
            return []

    def get_feedback_count(self, organization_id: str) -> int:
        """Get total feedback count for an organization."""
        if self.use_mock:
            return len(
                [
                    r
                    for r in self._mock_feedback.values()
                    if r.organization_id == organization_id
                ]
            )

        try:
            client = self._get_client()
            response = client.query(
                TableName=self.table_name,
                IndexName="organization-type-index",
                KeyConditionExpression="organization_id = :org_id",
                ExpressionAttributeValues={":org_id": {"S": organization_id}},
                Select="COUNT",
            )
            return response.get("Count", 0)
        except Exception as e:
            logger.error(f"Failed to get feedback count: {e}")
            return 0

    def get_stats(self, organization_id: str) -> dict[str, Any]:
        """Get feedback statistics for an organization."""
        if self.use_mock:
            records = [
                r
                for r in self._mock_feedback.values()
                if r.organization_id == organization_id
            ]
            if not records:
                return {
                    "total_feedback": 0,
                    "accurate_count": 0,
                    "inaccurate_count": 0,
                    "partial_count": 0,
                    "accuracy_rate": 0.0,
                }

            accurate = sum(
                1 for r in records if r.feedback_type == FeedbackType.ACCURATE
            )
            inaccurate = sum(
                1 for r in records if r.feedback_type == FeedbackType.INACCURATE
            )
            partial = sum(1 for r in records if r.feedback_type == FeedbackType.PARTIAL)

            return {
                "total_feedback": len(records),
                "accurate_count": accurate,
                "inaccurate_count": inaccurate,
                "partial_count": partial,
                "accuracy_rate": accurate / len(records) if records else 0.0,
            }

        # Real DynamoDB implementation would aggregate using Scan
        return {"total_feedback": self.get_feedback_count(organization_id)}


class CalibrationMetricsService:
    """
    Service for tracking calibration metrics and performance.

    Tracks:
    - ECE (Expected Calibration Error) over time
    - Calibration model performance by organization
    - A/B testing results for calibration improvements
    """

    def __init__(
        self,
        cloudwatch_namespace: str = "Aura/DocumentationAgent",
        use_mock: bool = False,
    ):
        """
        Initialize the calibration metrics service.

        Args:
            cloudwatch_namespace: CloudWatch namespace for metrics
            use_mock: Use mock for testing
        """
        self.namespace = cloudwatch_namespace
        self.use_mock = use_mock
        self._metrics: list[dict[str, Any]] = []

        logger.info(
            f"CalibrationMetricsService initialized: namespace={cloudwatch_namespace}"
        )

    def record_ece(
        self,
        organization_id: str,
        ece_value: float,
        documentation_type: str = "all",
        is_calibrated: bool = False,
    ) -> None:
        """
        Record ECE metric to CloudWatch.

        Args:
            organization_id: Organization ID
            ece_value: ECE value (0.0-1.0)
            documentation_type: Documentation type
            is_calibrated: Whether this is for calibrated scores
        """
        metric = {
            "MetricName": "ECE",
            "Value": ece_value,
            "Dimensions": [
                {"Name": "OrganizationId", "Value": organization_id},
                {"Name": "DocumentationType", "Value": documentation_type},
                {"Name": "IsCalibrated", "Value": str(is_calibrated).lower()},
            ],
            "Timestamp": datetime.now(timezone.utc),
        }

        if self.use_mock:
            self._metrics.append(metric)
            logger.info(
                f"[MOCK] Recorded ECE: org={organization_id}, "
                f"value={ece_value:.4f}, calibrated={is_calibrated}"
            )
            return

        try:
            import boto3

            cloudwatch = boto3.client("cloudwatch")
            cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        "MetricName": "ECE",
                        "Value": ece_value,
                        "Unit": "None",
                        "Dimensions": metric["Dimensions"],
                    }
                ],
            )
        except Exception as e:
            logger.error(f"Failed to record ECE metric: {e}")

    def record_calibration_event(
        self,
        organization_id: str,
        sample_count: int,
        ece_before: float,
        ece_after: float,
        model_version: int,
    ) -> None:
        """
        Record a calibration training event.

        Args:
            organization_id: Organization ID
            sample_count: Number of samples used
            ece_before: ECE before calibration
            ece_after: ECE after calibration
            model_version: New model version
        """
        improvement = (
            (ece_before - ece_after) / ece_before * 100 if ece_before > 0 else 0.0
        )

        logger.info(
            f"Calibration event: org={organization_id}, samples={sample_count}, "
            f"ECE {ece_before:.4f} -> {ece_after:.4f} ({improvement:.1f}% improvement), "
            f"version={model_version}"
        )

        if self.use_mock:
            self._metrics.append(
                {
                    "type": "calibration_event",
                    "organization_id": organization_id,
                    "sample_count": sample_count,
                    "ece_before": ece_before,
                    "ece_after": ece_after,
                    "improvement": improvement,
                    "model_version": model_version,
                }
            )
            return

        try:
            import boto3

            cloudwatch = boto3.client("cloudwatch")
            cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        "MetricName": "CalibrationImprovement",
                        "Value": improvement,
                        "Unit": "Percent",
                        "Dimensions": [
                            {"Name": "OrganizationId", "Value": organization_id}
                        ],
                    },
                    {
                        "MetricName": "CalibrationSamples",
                        "Value": sample_count,
                        "Unit": "Count",
                        "Dimensions": [
                            {"Name": "OrganizationId", "Value": organization_id}
                        ],
                    },
                ],
            )
        except Exception as e:
            logger.error(f"Failed to record calibration event: {e}")

    def check_ece_threshold(
        self,
        ece_value: float,
        threshold: float = 0.05,
    ) -> bool:
        """
        Check if ECE exceeds alert threshold.

        Args:
            ece_value: Current ECE value
            threshold: Alert threshold (default 0.05)

        Returns:
            True if ECE exceeds threshold
        """
        if ece_value > threshold:
            logger.warning(f"ECE threshold exceeded: {ece_value:.4f} > {threshold:.4f}")
            return True
        return False

    def get_mock_metrics(self) -> list[dict[str, Any]]:
        """Get recorded mock metrics (for testing)."""
        return self._metrics


# Factory functions


def create_calibrated_scorer(
    organization_id: str = "default",
    documentation_type: str = "all",
    min_samples: int = 100,
) -> CalibratedConfidenceScorer:
    """
    Create a calibrated confidence scorer.

    Args:
        organization_id: Organization ID for per-org calibration
        documentation_type: Documentation type for type-specific calibration
        min_samples: Minimum samples before calibration activates

    Returns:
        CalibratedConfidenceScorer instance
    """
    return CalibratedConfidenceScorer(
        min_samples_for_calibration=min_samples,
        organization_id=organization_id,
        documentation_type=documentation_type,
    )


def create_feedback_service(
    use_mock: bool = False,
    table_name: str = "",
) -> FeedbackLearningService:
    """
    Create a feedback learning service.

    Args:
        use_mock: Use mock storage for testing
        table_name: DynamoDB table name

    Returns:
        FeedbackLearningService instance
    """
    return FeedbackLearningService(table_name=table_name, use_mock=use_mock)


def create_metrics_service(
    use_mock: bool = False,
) -> CalibrationMetricsService:
    """
    Create a calibration metrics service.

    Args:
        use_mock: Use mock for testing

    Returns:
        CalibrationMetricsService instance
    """
    return CalibrationMetricsService(use_mock=use_mock)
