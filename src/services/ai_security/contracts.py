"""
Project Aura - AI Security Service Contracts

Data models and enums for AI model weight protection and
training data poisoning detection.

Based on ADR-079: Scale & AI Model Security
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# ============================================================================
# Model Weight Guardian Enums
# ============================================================================


class AccessType(str, Enum):
    """Types of model weight access."""

    READ = "read"
    WRITE = "write"
    COPY = "copy"
    EXPORT = "export"
    NETWORK_TRANSFER = "network_transfer"
    CHECKPOINT_LOAD = "checkpoint_load"
    CHECKPOINT_SAVE = "checkpoint_save"
    INFERENCE = "inference"
    TRAINING = "training"


class ThreatType(str, Enum):
    """Types of model weight threats."""

    EXFILTRATION = "exfiltration"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    TAMPERING = "tampering"
    CLONING = "cloning"
    GRADIENT_LEAKAGE = "gradient_leakage"
    MODEL_INVERSION = "model_inversion"
    MEMBERSHIP_INFERENCE = "membership_inference"
    WEIGHT_THEFT = "weight_theft"


class ThreatSeverity(str, Enum):
    """Severity levels for threats."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, Enum):
    """Status of security alerts."""

    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"
    ESCALATED = "escalated"


class ModelStatus(str, Enum):
    """Status of monitored model."""

    ACTIVE = "active"
    TRAINING = "training"
    ARCHIVED = "archived"
    QUARANTINED = "quarantined"


# ============================================================================
# Training Data Sentinel Enums
# ============================================================================


class PoisonType(str, Enum):
    """Types of training data poisoning."""

    LABEL_FLIP = "label_flip"  # Mislabeled samples
    BACKDOOR = "backdoor"  # Trigger patterns
    GRADIENT_MANIPULATION = "gradient_manipulation"
    DATA_INJECTION = "data_injection"
    FEATURE_COLLISION = "feature_collision"
    CLEAN_LABEL = "clean_label"  # Poisoning without label change
    TROJAN = "trojan"  # Hidden malicious behavior


class DataQualityIssue(str, Enum):
    """Types of data quality issues."""

    DUPLICATE = "duplicate"
    NEAR_DUPLICATE = "near_duplicate"
    OUTLIER = "outlier"
    MISLABELED = "mislabeled"
    CORRUPT = "corrupt"
    PII_DETECTED = "pii_detected"
    BIAS_DETECTED = "bias_detected"
    LOW_QUALITY = "low_quality"


class SampleStatus(str, Enum):
    """Status of training samples."""

    APPROVED = "approved"
    PENDING_REVIEW = "pending_review"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


class PIIType(str, Enum):
    """Types of PII detected."""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    ADDRESS = "address"
    NAME = "name"
    DATE_OF_BIRTH = "date_of_birth"
    IP_ADDRESS = "ip_address"
    API_KEY = "api_key"
    PASSWORD = "password"


# ============================================================================
# Model Weight Guardian Data Classes
# ============================================================================


@dataclass
class ModelWeightAccess:
    """Record of model weight access."""

    access_id: str
    model_id: str
    model_version: str
    access_type: AccessType
    accessor_identity: str
    accessor_ip: str
    timestamp: datetime
    bytes_accessed: int = 0
    file_paths: list[str] = field(default_factory=list)
    approved: bool = True
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WeightThreatDetection:
    """Detected threat to model weights."""

    detection_id: str
    threat_type: ThreatType
    model_id: str
    severity: ThreatSeverity
    confidence: float
    access_events: list[ModelWeightAccess] = field(default_factory=list)
    anomaly_indicators: list[str] = field(default_factory=list)
    recommended_action: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: AlertStatus = AlertStatus.OPEN
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelSecurityPolicy:
    """Security policy for model weights."""

    policy_id: str
    model_id: str
    name: str
    description: str = ""
    allowed_identities: list[str] = field(default_factory=list)
    allowed_ips: list[str] = field(default_factory=list)
    allowed_access_types: list[AccessType] = field(default_factory=list)
    max_daily_reads: int = 100
    max_bytes_per_access: int = 0  # 0 = unlimited
    require_mfa: bool = False
    export_blocked: bool = True
    alert_on_anomaly: bool = True
    alert_threshold: float = 0.7
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None


@dataclass
class MonitoredModel:
    """Model registered for monitoring."""

    model_id: str
    name: str
    version: str
    weight_paths: list[str] = field(default_factory=list)
    weight_hash: Optional[str] = None
    total_size_bytes: int = 0
    status: ModelStatus = ModelStatus.ACTIVE
    policy_id: Optional[str] = None
    last_accessed_at: Optional[datetime] = None
    access_count_24h: int = 0
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessPattern:
    """Pattern of model access for anomaly detection."""

    pattern_id: str
    model_id: str
    accessor_identity: str
    typical_access_times: list[int] = field(default_factory=list)  # Hours 0-23
    typical_access_days: list[int] = field(default_factory=list)  # Days 0-6
    typical_bytes_per_access: float = 0.0
    typical_access_frequency: float = 0.0  # Per hour
    access_type_distribution: dict[str, float] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AuditReport:
    """Security audit report for model."""

    report_id: str
    model_id: str
    period_start: datetime
    period_end: datetime
    total_accesses: int = 0
    unique_accessors: int = 0
    blocked_accesses: int = 0
    anomalies_detected: int = 0
    policy_violations: int = 0
    threat_detections: list[WeightThreatDetection] = field(default_factory=list)
    access_by_type: dict[str, int] = field(default_factory=dict)
    access_by_identity: dict[str, int] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# Training Data Sentinel Data Classes
# ============================================================================


@dataclass
class TrainingSample:
    """Individual training sample."""

    sample_id: str
    content: str
    label: Optional[str] = None
    embedding: Optional[list[float]] = None
    source: str = ""
    source_url: Optional[str] = None
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    provenance_hash: str = ""
    status: SampleStatus = SampleStatus.PENDING_REVIEW
    quality_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PoisonDetection:
    """Detected poisoning attempt."""

    detection_id: str
    poison_type: PoisonType
    affected_samples: list[str] = field(default_factory=list)
    confidence: float = 0.0
    detection_method: str = ""
    severity: ThreatSeverity = ThreatSeverity.MEDIUM
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DatasetAnalysis:
    """Analysis result for training dataset."""

    analysis_id: str
    dataset_id: str
    total_samples: int = 0
    unique_samples: int = 0
    label_distribution: dict[str, int] = field(default_factory=dict)
    quality_issues: list[tuple[str, DataQualityIssue]] = field(default_factory=list)
    poison_detections: list[PoisonDetection] = field(default_factory=list)
    pii_detections: list[tuple[str, list[PIIType]]] = field(default_factory=list)
    provenance_verified: int = 0
    provenance_failed: int = 0
    overall_risk_score: float = 0.0
    overall_quality_score: float = 1.0
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    analysis_duration_seconds: float = 0.0


@dataclass
class BackdoorPattern:
    """Detected backdoor trigger pattern."""

    pattern_id: str
    pattern_type: str  # text, image, audio
    trigger_pattern: str  # Actual pattern or description
    affected_samples: list[str] = field(default_factory=list)
    target_label: Optional[str] = None
    confidence: float = 0.0
    detection_method: str = ""


@dataclass
class DuplicateCluster:
    """Cluster of duplicate/near-duplicate samples."""

    cluster_id: str
    sample_ids: list[str] = field(default_factory=list)
    similarity_scores: list[float] = field(default_factory=list)
    representative_sample: Optional[str] = None
    cluster_size: int = 0


@dataclass
class LabelConsistencyResult:
    """Result of label consistency check."""

    sample_id: str
    assigned_label: str
    predicted_label: str
    confidence: float = 0.0
    is_consistent: bool = True
    nearest_neighbors: list[str] = field(default_factory=list)
    neighbor_labels: list[str] = field(default_factory=list)


@dataclass
class ProvenanceChain:
    """Chain of provenance for a sample."""

    sample_id: str
    chain: list[dict[str, Any]] = field(default_factory=list)
    verified: bool = False
    verification_errors: list[str] = field(default_factory=list)
    root_source: Optional[str] = None
    chain_length: int = 0


@dataclass
class QuarantineRecord:
    """Record of quarantined samples."""

    quarantine_id: str
    dataset_id: str
    sample_ids: list[str] = field(default_factory=list)
    reason: str = ""
    quarantined_by: str = ""
    quarantined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "active"  # active, restored, deleted
    restore_conditions: Optional[str] = None


@dataclass
class DatasetPolicy:
    """Policy for training dataset validation."""

    policy_id: str
    name: str
    description: str = ""
    max_duplicate_ratio: float = 0.1
    max_outlier_ratio: float = 0.05
    min_samples_per_label: int = 10
    pii_detection_enabled: bool = True
    pii_types_blocked: list[PIIType] = field(default_factory=list)
    poison_detection_enabled: bool = True
    provenance_required: bool = True
    auto_quarantine: bool = True
    enabled: bool = True
