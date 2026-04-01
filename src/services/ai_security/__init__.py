"""
Project Aura - AI Security Service

Protects AI model weights from unauthorized access and
detects data poisoning attacks in fine-tuning datasets.

Based on ADR-079: Scale & AI Model Security

Services:
- ModelWeightGuardian: AI model weight protection
- TrainingDataSentinel: Training data poisoning detection

Key Features:
- Access pattern monitoring and anomaly detection
- Exfiltration detection
- Policy enforcement for model access
- Statistical poisoning detection
- Backdoor trigger detection
- Label consistency verification
- Data provenance tracking
- PII/sensitive data detection
"""

# Configuration
from .config import (
    AISecurityConfig,
    AlertingConfig,
    MetricsConfig,
    ModelGuardianConfig,
    PIIDetectionConfig,
    StorageConfig,
    TrainingSentinelConfig,
    get_ai_security_config,
    reset_ai_security_config,
    set_ai_security_config,
)

# Contracts
from .contracts import (
    AccessPattern,
    AccessType,
    AlertStatus,
    AuditReport,
    BackdoorPattern,
    DataQualityIssue,
    DatasetAnalysis,
    DatasetPolicy,
    DuplicateCluster,
    LabelConsistencyResult,
    ModelSecurityPolicy,
    ModelStatus,
    ModelWeightAccess,
    MonitoredModel,
    PIIType,
    PoisonDetection,
    PoisonType,
    ProvenanceChain,
    QuarantineRecord,
    SampleStatus,
    ThreatSeverity,
    ThreatType,
    TrainingSample,
    WeightThreatDetection,
)

# Exceptions
from .exceptions import (
    AccessDeniedError,
    AISecurityError,
    AlertDeliveryError,
    AlertError,
    AlertRateLimitedError,
    AnalysisTimeoutError,
    AnomalyDetectedError,
    BackdoorDetectedError,
    DataQualityError,
    DatasetNotFoundError,
    EmbeddingError,
    ExfiltrationAttemptError,
    InvalidPolicyError,
    LabelInconsistencyError,
    ModelAlreadyRegisteredError,
    ModelGuardianError,
    ModelNotRegisteredError,
    PIIDetectedError,
    PoisonDetectedError,
    PolicyNotFoundError,
    PolicyViolationError,
    ProvenanceVerificationError,
    QuarantineError,
    SampleNotFoundError,
    TooManySamplesError,
    TrainingSentinelError,
    WeightHashMismatchError,
)

# Services
from .model_weight_guardian import (
    ModelWeightGuardian,
    get_model_guardian,
    reset_model_guardian,
)
from .training_data_sentinel import (
    TrainingDataSentinel,
    get_training_sentinel,
    reset_training_sentinel,
)

__all__ = [
    # Contracts
    "AccessPattern",
    "AccessType",
    "AlertStatus",
    "AuditReport",
    "BackdoorPattern",
    "DataQualityIssue",
    "DatasetAnalysis",
    "DatasetPolicy",
    "DuplicateCluster",
    "LabelConsistencyResult",
    "ModelSecurityPolicy",
    "ModelStatus",
    "ModelWeightAccess",
    "MonitoredModel",
    "PIIType",
    "PoisonDetection",
    "PoisonType",
    "ProvenanceChain",
    "QuarantineRecord",
    "SampleStatus",
    "ThreatSeverity",
    "ThreatType",
    "TrainingSample",
    "WeightThreatDetection",
    # Configuration
    "AISecurityConfig",
    "AlertingConfig",
    "MetricsConfig",
    "ModelGuardianConfig",
    "PIIDetectionConfig",
    "StorageConfig",
    "TrainingSentinelConfig",
    "get_ai_security_config",
    "reset_ai_security_config",
    "set_ai_security_config",
    # Exceptions
    "AccessDeniedError",
    "AISecurityError",
    "AlertDeliveryError",
    "AlertError",
    "AlertRateLimitedError",
    "AnalysisTimeoutError",
    "AnomalyDetectedError",
    "BackdoorDetectedError",
    "DataQualityError",
    "DatasetNotFoundError",
    "EmbeddingError",
    "ExfiltrationAttemptError",
    "InvalidPolicyError",
    "LabelInconsistencyError",
    "ModelAlreadyRegisteredError",
    "ModelGuardianError",
    "ModelNotRegisteredError",
    "PIIDetectedError",
    "PoisonDetectedError",
    "PolicyNotFoundError",
    "PolicyViolationError",
    "ProvenanceVerificationError",
    "QuarantineError",
    "SampleNotFoundError",
    "TooManySamplesError",
    "TrainingSentinelError",
    "WeightHashMismatchError",
    # Services
    "ModelWeightGuardian",
    "get_model_guardian",
    "reset_model_guardian",
    "TrainingDataSentinel",
    "get_training_sentinel",
    "reset_training_sentinel",
]
