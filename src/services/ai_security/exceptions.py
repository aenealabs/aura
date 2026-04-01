"""
Project Aura - AI Security Service Exceptions

Custom exceptions for AI model weight protection and
training data poisoning detection operations.

Based on ADR-079: Scale & AI Model Security
"""

from typing import Any, Optional


class AISecurityError(Exception):
    """Base exception for all AI security service errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "AI_SECURITY_ERROR"
        self.details = details or {}


# ============================================================================
# Model Guardian Errors
# ============================================================================


class ModelGuardianError(AISecurityError):
    """Base exception for Model Weight Guardian operations."""

    def __init__(
        self,
        message: str,
        model_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "MODEL_GUARDIAN_ERROR", details)
        self.model_id = model_id


class ModelNotRegisteredError(ModelGuardianError):
    """Model is not registered for monitoring."""

    def __init__(self, model_id: str):
        super().__init__(
            f"Model not registered for monitoring: {model_id}",
            model_id=model_id,
        )
        self.error_code = "MODEL_NOT_REGISTERED"


class ModelAlreadyRegisteredError(ModelGuardianError):
    """Model is already registered."""

    def __init__(self, model_id: str):
        super().__init__(
            f"Model already registered: {model_id}",
            model_id=model_id,
        )
        self.error_code = "MODEL_ALREADY_REGISTERED"


class AccessDeniedError(ModelGuardianError):
    """Access to model weights denied."""

    def __init__(
        self,
        model_id: str,
        accessor: str,
        reason: str,
    ):
        super().__init__(
            f"Access denied to {model_id} for {accessor}: {reason}",
            model_id=model_id,
        )
        self.error_code = "ACCESS_DENIED"
        self.accessor = accessor
        self.reason = reason


class PolicyViolationError(ModelGuardianError):
    """Security policy violation detected."""

    def __init__(
        self,
        model_id: str,
        policy_id: str,
        violation: str,
    ):
        super().__init__(
            f"Policy violation for {model_id}: {violation}",
            model_id=model_id,
        )
        self.error_code = "POLICY_VIOLATION"
        self.policy_id = policy_id
        self.violation = violation


class ExfiltrationAttemptError(ModelGuardianError):
    """Potential exfiltration attempt detected."""

    def __init__(
        self,
        model_id: str,
        accessor: str,
        indicators: list[str],
    ):
        super().__init__(
            f"Potential exfiltration attempt detected for {model_id}",
            model_id=model_id,
        )
        self.error_code = "EXFILTRATION_ATTEMPT"
        self.accessor = accessor
        self.indicators = indicators


class AnomalyDetectedError(ModelGuardianError):
    """Anomalous access pattern detected."""

    def __init__(
        self,
        model_id: str,
        anomaly_type: str,
        confidence: float,
    ):
        super().__init__(
            f"Anomalous access detected for {model_id}: {anomaly_type} (confidence: {confidence:.2f})",
            model_id=model_id,
        )
        self.error_code = "ANOMALY_DETECTED"
        self.anomaly_type = anomaly_type
        self.confidence = confidence


class PolicyNotFoundError(ModelGuardianError):
    """Security policy not found."""

    def __init__(self, policy_id: str):
        super().__init__(f"Policy not found: {policy_id}")
        self.error_code = "POLICY_NOT_FOUND"
        self.policy_id = policy_id


class InvalidPolicyError(ModelGuardianError):
    """Security policy is invalid."""

    def __init__(self, policy_id: str, reason: str):
        super().__init__(f"Invalid policy {policy_id}: {reason}")
        self.error_code = "INVALID_POLICY"
        self.policy_id = policy_id


class WeightHashMismatchError(ModelGuardianError):
    """Model weight hash does not match expected value."""

    def __init__(
        self,
        model_id: str,
        expected_hash: str,
        actual_hash: str,
    ):
        super().__init__(
            f"Weight hash mismatch for {model_id}: expected {expected_hash[:16]}..., got {actual_hash[:16]}...",
            model_id=model_id,
        )
        self.error_code = "WEIGHT_HASH_MISMATCH"
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash


# ============================================================================
# Training Sentinel Errors
# ============================================================================


class TrainingSentinelError(AISecurityError):
    """Base exception for Training Data Sentinel operations."""

    def __init__(
        self,
        message: str,
        dataset_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "TRAINING_SENTINEL_ERROR", details)
        self.dataset_id = dataset_id


class DatasetNotFoundError(TrainingSentinelError):
    """Dataset not found."""

    def __init__(self, dataset_id: str):
        super().__init__(
            f"Dataset not found: {dataset_id}",
            dataset_id=dataset_id,
        )
        self.error_code = "DATASET_NOT_FOUND"


class SampleNotFoundError(TrainingSentinelError):
    """Sample not found in dataset."""

    def __init__(self, sample_id: str, dataset_id: Optional[str] = None):
        msg = f"Sample not found: {sample_id}"
        if dataset_id:
            msg += f" in dataset {dataset_id}"
        super().__init__(msg, dataset_id=dataset_id)
        self.error_code = "SAMPLE_NOT_FOUND"
        self.sample_id = sample_id


class PoisonDetectedError(TrainingSentinelError):
    """Poisoning detected in training data."""

    def __init__(
        self,
        dataset_id: str,
        poison_type: str,
        affected_count: int,
        confidence: float,
    ):
        super().__init__(
            f"Poisoning detected in {dataset_id}: {poison_type} ({affected_count} samples, {confidence:.2f} confidence)",
            dataset_id=dataset_id,
        )
        self.error_code = "POISON_DETECTED"
        self.poison_type = poison_type
        self.affected_count = affected_count
        self.confidence = confidence


class BackdoorDetectedError(TrainingSentinelError):
    """Backdoor trigger pattern detected."""

    def __init__(
        self,
        dataset_id: str,
        pattern_description: str,
        affected_samples: list[str],
    ):
        super().__init__(
            f"Backdoor pattern detected in {dataset_id}: {pattern_description}",
            dataset_id=dataset_id,
        )
        self.error_code = "BACKDOOR_DETECTED"
        self.pattern_description = pattern_description
        self.affected_samples = affected_samples


class PIIDetectedError(TrainingSentinelError):
    """PII detected in training data."""

    def __init__(
        self,
        sample_id: str,
        pii_types: list[str],
        dataset_id: Optional[str] = None,
    ):
        super().__init__(
            f"PII detected in sample {sample_id}: {', '.join(pii_types)}",
            dataset_id=dataset_id,
        )
        self.error_code = "PII_DETECTED"
        self.sample_id = sample_id
        self.pii_types = pii_types


class ProvenanceVerificationError(TrainingSentinelError):
    """Sample provenance verification failed."""

    def __init__(self, sample_id: str, reason: str):
        super().__init__(f"Provenance verification failed for {sample_id}: {reason}")
        self.error_code = "PROVENANCE_VERIFICATION_FAILED"
        self.sample_id = sample_id


class LabelInconsistencyError(TrainingSentinelError):
    """Label inconsistency detected."""

    def __init__(
        self,
        sample_id: str,
        assigned_label: str,
        predicted_label: str,
        confidence: float,
    ):
        super().__init__(
            f"Label inconsistency for {sample_id}: assigned '{assigned_label}', predicted '{predicted_label}' ({confidence:.2f} confidence)"
        )
        self.error_code = "LABEL_INCONSISTENCY"
        self.sample_id = sample_id
        self.assigned_label = assigned_label
        self.predicted_label = predicted_label
        self.confidence = confidence


class QuarantineError(TrainingSentinelError):
    """Error during quarantine operation."""

    def __init__(self, sample_ids: list[str], reason: str):
        super().__init__(f"Quarantine failed for {len(sample_ids)} samples: {reason}")
        self.error_code = "QUARANTINE_ERROR"
        self.sample_ids = sample_ids


class DataQualityError(TrainingSentinelError):
    """Data quality check failed."""

    def __init__(
        self,
        dataset_id: str,
        issue_type: str,
        issue_count: int,
    ):
        super().__init__(
            f"Data quality issue in {dataset_id}: {issue_count} {issue_type} issues",
            dataset_id=dataset_id,
        )
        self.error_code = "DATA_QUALITY_ERROR"
        self.issue_type = issue_type
        self.issue_count = issue_count


class EmbeddingError(TrainingSentinelError):
    """Error generating or processing embeddings."""

    def __init__(self, sample_id: str, reason: str):
        super().__init__(f"Embedding error for {sample_id}: {reason}")
        self.error_code = "EMBEDDING_ERROR"
        self.sample_id = sample_id


class AnalysisTimeoutError(TrainingSentinelError):
    """Dataset analysis timed out."""

    def __init__(
        self,
        dataset_id: str,
        timeout_seconds: int,
        samples_analyzed: int,
    ):
        super().__init__(
            f"Analysis timed out for {dataset_id} after {timeout_seconds}s ({samples_analyzed} samples analyzed)",
            dataset_id=dataset_id,
        )
        self.error_code = "ANALYSIS_TIMEOUT"
        self.timeout_seconds = timeout_seconds
        self.samples_analyzed = samples_analyzed


class TooManySamplesError(TrainingSentinelError):
    """Dataset has too many samples for batch analysis."""

    def __init__(
        self,
        dataset_id: str,
        sample_count: int,
        max_samples: int,
    ):
        super().__init__(
            f"Too many samples in {dataset_id}: {sample_count} > {max_samples}",
            dataset_id=dataset_id,
        )
        self.error_code = "TOO_MANY_SAMPLES"
        self.sample_count = sample_count
        self.max_samples = max_samples


# ============================================================================
# Alert Errors
# ============================================================================


class AlertError(AISecurityError):
    """Base exception for alerting operations."""

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "ALERT_ERROR", details)


class AlertDeliveryError(AlertError):
    """Failed to deliver alert."""

    def __init__(self, channel: str, reason: str):
        super().__init__(f"Failed to deliver alert via {channel}: {reason}")
        self.error_code = "ALERT_DELIVERY_ERROR"
        self.channel = channel


class AlertRateLimitedError(AlertError):
    """Alert rate limit exceeded."""

    def __init__(self, alerts_per_hour: int, max_alerts: int):
        super().__init__(
            f"Alert rate limit exceeded: {alerts_per_hour}/{max_alerts} per hour"
        )
        self.error_code = "ALERT_RATE_LIMITED"
        self.alerts_per_hour = alerts_per_hour
        self.max_alerts = max_alerts
