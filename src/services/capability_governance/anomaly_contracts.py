"""
Project Aura - Anomaly Detection Contracts

Dataclasses for ML-based anomaly detection of agent behavior.
Implements ADR-072 for behavioral anomaly detection.

Anomaly Types:
- Volume: Unusual invocation counts (Z-score based)
- Sequence: Tool invocation patterns deviating from learned workflows
- Temporal: Activity outside normal operational hours
- Context: Environment confusion indicators
- Cross-Agent: Coordinated suspicious behavior across multiple agents
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AnomalyType(Enum):
    """Types of behavioral anomalies detected."""

    VOLUME = "volume"
    SEQUENCE = "sequence"
    TEMPORAL = "temporal"
    CONTEXT = "context"
    CROSS_AGENT = "cross_agent"
    HONEYPOT = "honeypot"
    ML_ENSEMBLE = "ml_ensemble"


class AlertSeverity(Enum):
    """Alert severity levels for anomaly responses."""

    INFO = "info"  # Score < 0.5: Log only
    SUSPICIOUS = "suspicious"  # Score 0.5-0.7: Enhanced logging
    ALERT = "alert"  # Score 0.7-0.9: Notify security team
    CRITICAL = "critical"  # Score > 0.9: Rate-limit + HITL quarantine approval
    P1 = "P1"  # Honeypot trigger: Immediate auto-quarantine


class QuarantineReason(Enum):
    """Reasons for agent quarantine."""

    HONEYPOT_TRIGGERED = "honeypot_triggered"
    HITL_APPROVED = "hitl_approved"
    CRITICAL_ANOMALY = "critical_anomaly"
    POLICY_VIOLATION = "policy_violation"
    MANUAL_INTERVENTION = "manual_intervention"


@dataclass(frozen=True)
class AnomalyResult:
    """Result of an anomaly detection check."""

    is_anomaly: bool
    score: float  # 0.0 to 1.0, higher = more anomalous
    anomaly_type: AnomalyType
    details: dict[str, Any] = field(default_factory=dict)
    explanation: str | None = None

    def __post_init__(self):
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.score}")

    @property
    def severity(self) -> AlertSeverity:
        """Determine alert severity based on score."""
        if self.anomaly_type == AnomalyType.HONEYPOT:
            return AlertSeverity.P1
        if self.score < 0.5:
            return AlertSeverity.INFO
        if self.score < 0.7:
            return AlertSeverity.SUSPICIOUS
        if self.score < 0.9:
            return AlertSeverity.ALERT
        return AlertSeverity.CRITICAL

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_anomaly": self.is_anomaly,
            "score": self.score,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "details": self.details,
            "explanation": self.explanation,
        }


@dataclass
class StatisticalBaseline:
    """Statistical baseline for agent behavior."""

    agent_type: str
    tool_classification: str | None = None
    mean_hourly_count: float = 0.0
    std_hourly_count: float = 1.0
    mean_daily_count: float = 0.0
    std_daily_count: float = 1.0
    typical_sequences: list[tuple[str, str, str]] = field(default_factory=list)
    active_hours: list[int] = field(
        default_factory=lambda: list(range(8, 20))
    )  # 8am-8pm
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "agent_type": self.agent_type,
            "tool_classification": self.tool_classification,
            "mean_hourly_count": self.mean_hourly_count,
            "std_hourly_count": self.std_hourly_count,
            "mean_daily_count": self.mean_daily_count,
            "std_daily_count": self.std_daily_count,
            "typical_sequences": [list(seq) for seq in self.typical_sequences],
            "active_hours": self.active_hours,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StatisticalBaseline":
        """Create from dictionary."""
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.utcnow()

        return cls(
            agent_type=data["agent_type"],
            tool_classification=data.get("tool_classification"),
            mean_hourly_count=data.get("mean_hourly_count", 0.0),
            std_hourly_count=data.get("std_hourly_count", 1.0),
            mean_daily_count=data.get("mean_daily_count", 0.0),
            std_daily_count=data.get("std_daily_count", 1.0),
            typical_sequences=[tuple(seq) for seq in data.get("typical_sequences", [])],
            active_hours=data.get("active_hours", list(range(8, 20))),
            updated_at=updated_at,
        )


@dataclass
class AgentBehaviorFeatures:
    """Feature vector for ML-based anomaly detection."""

    agent_id: str
    agent_type: str

    # Volume features (windowed counts)
    invocations_1min: int = 0
    invocations_5min: int = 0
    invocations_1hr: int = 0

    # Classification ratios
    safe_ratio: float = 0.0
    monitoring_ratio: float = 0.0
    dangerous_ratio: float = 0.0
    critical_ratio: float = 0.0

    # Sequence features
    sequence_entropy: float = 0.0
    unique_tools_1hr: int = 0

    # Temporal features
    hour_of_day: int = 0
    day_of_week: int = 0  # 0=Monday, 6=Sunday

    # Timing features
    time_since_last_invocation: float = 0.0  # seconds
    mean_inter_invocation_time: float = 0.0  # seconds

    # Denial features
    denial_count_1hr: int = 0
    denial_rate_1hr: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "invocations_1min": self.invocations_1min,
            "invocations_5min": self.invocations_5min,
            "invocations_1hr": self.invocations_1hr,
            "safe_ratio": self.safe_ratio,
            "monitoring_ratio": self.monitoring_ratio,
            "dangerous_ratio": self.dangerous_ratio,
            "critical_ratio": self.critical_ratio,
            "sequence_entropy": self.sequence_entropy,
            "unique_tools_1hr": self.unique_tools_1hr,
            "hour_of_day": self.hour_of_day,
            "day_of_week": self.day_of_week,
            "time_since_last_invocation": self.time_since_last_invocation,
            "mean_inter_invocation_time": self.mean_inter_invocation_time,
            "denial_count_1hr": self.denial_count_1hr,
            "denial_rate_1hr": self.denial_rate_1hr,
        }

    def to_feature_vector(self) -> list[float]:
        """Convert to numeric feature vector for ML models."""
        return [
            float(self.invocations_1min),
            float(self.invocations_5min),
            float(self.invocations_1hr),
            self.safe_ratio,
            self.monitoring_ratio,
            self.dangerous_ratio,
            self.critical_ratio,
            self.sequence_entropy,
            float(self.unique_tools_1hr),
            float(self.hour_of_day),
            float(self.day_of_week),
            self.time_since_last_invocation,
            self.mean_inter_invocation_time,
            float(self.denial_count_1hr),
            self.denial_rate_1hr,
        ]


@dataclass
class HoneypotCapability:
    """Definition of a honeypot capability (trap)."""

    name: str
    description: str
    classification: str = "CRITICAL"
    legitimate_use: bool = False
    alert_severity: AlertSeverity = AlertSeverity.P1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "classification": self.classification,
            "legitimate_use": self.legitimate_use,
            "alert_severity": self.alert_severity.value,
        }


@dataclass
class HoneypotResult:
    """Result of a honeypot check."""

    triggered: bool
    honeypot_name: str | None = None
    action_taken: str | None = None
    agent_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "triggered": self.triggered,
            "honeypot_name": self.honeypot_name,
            "action_taken": self.action_taken,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class QuarantineRecord:
    """Record of an agent quarantine action."""

    agent_id: str
    reason: QuarantineReason
    triggered_by: str  # tool name or anomaly type
    anomaly_score: float | None = None
    quarantined_at: datetime = field(default_factory=datetime.utcnow)
    released_at: datetime | None = None
    hitl_approved_by: str | None = None
    notes: str | None = None

    @property
    def is_active(self) -> bool:
        """Check if quarantine is still active."""
        return self.released_at is None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "reason": self.reason.value,
            "triggered_by": self.triggered_by,
            "anomaly_score": self.anomaly_score,
            "quarantined_at": self.quarantined_at.isoformat(),
            "released_at": self.released_at.isoformat() if self.released_at else None,
            "is_active": self.is_active,
            "hitl_approved_by": self.hitl_approved_by,
            "notes": self.notes,
        }


@dataclass
class AnomalyAlert:
    """Alert generated from anomaly detection."""

    alert_id: str
    agent_id: str
    anomaly_result: AnomalyResult
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    false_positive: bool | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "agent_id": self.agent_id,
            "anomaly_result": self.anomaly_result.to_dict(),
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": (
                self.acknowledged_at.isoformat() if self.acknowledged_at else None
            ),
            "false_positive": self.false_positive,
            "notes": self.notes,
        }


@dataclass
class InvocationContext:
    """Context for a capability invocation."""

    session_id: str
    parent_agent: str | None = None
    environment: str = "development"
    tenant_id: str | None = None
    user_id: str | None = None
    request_id: str | None = None
    parameters_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "parent_agent": self.parent_agent,
            "environment": self.environment,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "parameters_hash": self.parameters_hash,
        }


@dataclass
class CapabilityInvocation:
    """Record of a capability invocation for audit trail."""

    agent_id: str
    tool_name: str
    classification: str
    decision: str  # ALLOW, DENY, etc.
    timestamp: datetime = field(default_factory=datetime.utcnow)
    latency_ms: float | None = None
    context: InvocationContext | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "classification": self.classification,
            "decision": self.decision,
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": self.latency_ms,
            "context": self.context.to_dict() if self.context else None,
        }


@dataclass
class AgentContext:
    """Context information about an agent."""

    agent_id: str
    agent_name: str
    agent_type: str
    environment: str = "development"
    tenant_id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    risk_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "environment": self.environment,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat(),
            "risk_score": self.risk_score,
        }


@dataclass
class AnomalyDetectionConfig:
    """Configuration for anomaly detection."""

    # Volume detection thresholds
    volume_z_score_threshold: float = 3.0  # Z > 3.0 = 99.7% confidence
    volume_suspicious_threshold: float = 2.5

    # Sequence detection
    sequence_unseen_ratio_threshold: float = 0.5

    # Score thresholds for responses
    log_only_threshold: float = 0.5
    enhanced_logging_threshold: float = 0.7
    alert_threshold: float = 0.9

    # Quarantine settings
    rate_limit_factor: float = 0.1  # Reduce to 10% capacity on critical
    hitl_required_for_ml_quarantine: bool = True  # Per ADR-032

    # Baseline settings
    baseline_window_days: int = 14
    min_samples_for_baseline: int = 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "volume_z_score_threshold": self.volume_z_score_threshold,
            "volume_suspicious_threshold": self.volume_suspicious_threshold,
            "sequence_unseen_ratio_threshold": self.sequence_unseen_ratio_threshold,
            "log_only_threshold": self.log_only_threshold,
            "enhanced_logging_threshold": self.enhanced_logging_threshold,
            "alert_threshold": self.alert_threshold,
            "rate_limit_factor": self.rate_limit_factor,
            "hitl_required_for_ml_quarantine": self.hitl_required_for_ml_quarantine,
            "baseline_window_days": self.baseline_window_days,
            "min_samples_for_baseline": self.min_samples_for_baseline,
        }
