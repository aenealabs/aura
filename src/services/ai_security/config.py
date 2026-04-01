"""
Project Aura - AI Security Service Configuration

Configuration management for AI model weight protection
and training data poisoning detection.

Based on ADR-079: Scale & AI Model Security
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from .contracts import PIIType, ThreatSeverity


@dataclass
class ModelGuardianConfig:
    """Configuration for Model Weight Guardian."""

    enabled: bool = True
    monitor_all_access: bool = True
    anomaly_detection_enabled: bool = True
    anomaly_threshold: float = 0.7
    baseline_window_hours: int = 168  # 7 days
    alert_cooldown_seconds: int = 300
    max_access_log_retention_days: int = 90
    export_monitoring_enabled: bool = True
    network_monitoring_enabled: bool = True
    hash_algorithm: str = "sha256"


@dataclass
class TrainingSentinelConfig:
    """Configuration for Training Data Sentinel."""

    enabled: bool = True
    poison_detection_enabled: bool = True
    pii_detection_enabled: bool = True
    duplicate_detection_enabled: bool = True
    backdoor_detection_enabled: bool = True
    label_consistency_check: bool = True
    provenance_verification: bool = True
    auto_quarantine: bool = True
    similarity_threshold: float = 0.95
    outlier_threshold: float = 3.0  # Standard deviations
    min_embedding_dimension: int = 128
    max_samples_per_batch: int = 10000


@dataclass
class PIIDetectionConfig:
    """Configuration for PII detection."""

    enabled: bool = True
    detection_patterns: list[PIIType] = field(
        default_factory=lambda: [
            PIIType.EMAIL,
            PIIType.PHONE,
            PIIType.SSN,
            PIIType.CREDIT_CARD,
            PIIType.API_KEY,
            PIIType.PASSWORD,
        ]
    )
    scrub_pii: bool = False  # Whether to remove PII
    alert_on_pii: bool = True
    block_on_pii: bool = True


@dataclass
class AlertingConfig:
    """Configuration for security alerting."""

    enabled: bool = True
    min_severity_to_alert: ThreatSeverity = ThreatSeverity.MEDIUM
    sns_topic_arn: Optional[str] = None
    email_recipients: list[str] = field(default_factory=list)
    slack_webhook_url: Optional[str] = None
    alert_aggregation_seconds: int = 60
    max_alerts_per_hour: int = 100


@dataclass
class StorageConfig:
    """Configuration for data storage."""

    dynamodb_enabled: bool = True
    access_log_table: str = "aura-model-access-logs"
    threat_detection_table: str = "aura-threat-detections"
    sample_analysis_table: str = "aura-sample-analysis"
    s3_bucket: Optional[str] = None
    s3_prefix: str = "ai-security/"
    encryption_enabled: bool = True


@dataclass
class MetricsConfig:
    """Configuration for metrics."""

    enabled: bool = True
    namespace: str = "Aura/AISecurity"
    publish_interval_seconds: int = 60
    detailed_access_metrics: bool = True
    detailed_detection_metrics: bool = True


@dataclass
class AISecurityConfig:
    """Root configuration for AI security services."""

    environment: str = "dev"
    enabled: bool = True
    model_guardian: ModelGuardianConfig = field(default_factory=ModelGuardianConfig)
    training_sentinel: TrainingSentinelConfig = field(
        default_factory=TrainingSentinelConfig
    )
    pii_detection: PIIDetectionConfig = field(default_factory=PIIDetectionConfig)
    alerting: AlertingConfig = field(default_factory=AlertingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if (
            self.model_guardian.anomaly_threshold < 0
            or self.model_guardian.anomaly_threshold > 1
        ):
            errors.append("model_guardian.anomaly_threshold must be between 0 and 1")

        if self.model_guardian.baseline_window_hours < 1:
            errors.append("model_guardian.baseline_window_hours must be >= 1")

        if (
            self.training_sentinel.similarity_threshold < 0
            or self.training_sentinel.similarity_threshold > 1
        ):
            errors.append(
                "training_sentinel.similarity_threshold must be between 0 and 1"
            )

        if self.training_sentinel.outlier_threshold < 1:
            errors.append("training_sentinel.outlier_threshold must be >= 1")

        if self.alerting.max_alerts_per_hour < 1:
            errors.append("alerting.max_alerts_per_hour must be >= 1")

        return errors

    @classmethod
    def from_environment(cls) -> "AISecurityConfig":
        """Create configuration from environment variables."""
        environment = os.getenv("ENVIRONMENT", "dev")

        model_guardian = ModelGuardianConfig(
            enabled=os.getenv("AI_SECURITY_MODEL_GUARDIAN_ENABLED", "true").lower()
            == "true",
            anomaly_threshold=float(os.getenv("AI_SECURITY_ANOMALY_THRESHOLD", "0.7")),
        )

        training_sentinel = TrainingSentinelConfig(
            enabled=os.getenv("AI_SECURITY_TRAINING_SENTINEL_ENABLED", "true").lower()
            == "true",
            auto_quarantine=os.getenv("AI_SECURITY_AUTO_QUARANTINE", "true").lower()
            == "true",
        )

        pii_detection = PIIDetectionConfig(
            enabled=os.getenv("AI_SECURITY_PII_DETECTION_ENABLED", "true").lower()
            == "true",
            block_on_pii=os.getenv("AI_SECURITY_BLOCK_ON_PII", "true").lower()
            == "true",
        )

        alerting = AlertingConfig(
            enabled=os.getenv("AI_SECURITY_ALERTING_ENABLED", "true").lower() == "true",
            sns_topic_arn=os.getenv("AI_SECURITY_SNS_TOPIC_ARN"),
            slack_webhook_url=os.getenv("AI_SECURITY_SLACK_WEBHOOK_URL"),
        )

        storage = StorageConfig(
            dynamodb_enabled=os.getenv("AI_SECURITY_DYNAMODB_ENABLED", "true").lower()
            == "true",
            s3_bucket=os.getenv("AI_SECURITY_S3_BUCKET"),
        )

        metrics = MetricsConfig(
            enabled=os.getenv("AI_SECURITY_METRICS_ENABLED", "true").lower() == "true",
            namespace=os.getenv("AI_SECURITY_METRICS_NAMESPACE", "Aura/AISecurity"),
        )

        return cls(
            environment=environment,
            enabled=os.getenv("AI_SECURITY_ENABLED", "true").lower() == "true",
            model_guardian=model_guardian,
            training_sentinel=training_sentinel,
            pii_detection=pii_detection,
            alerting=alerting,
            storage=storage,
            metrics=metrics,
        )

    @classmethod
    def for_testing(cls) -> "AISecurityConfig":
        """Create configuration for unit tests."""
        return cls(
            environment="test",
            enabled=True,
            model_guardian=ModelGuardianConfig(
                enabled=True,
                monitor_all_access=True,
            ),
            training_sentinel=TrainingSentinelConfig(
                enabled=True,
                max_samples_per_batch=100,
            ),
            pii_detection=PIIDetectionConfig(
                enabled=True,
                scrub_pii=False,
            ),
            alerting=AlertingConfig(
                enabled=False,  # Disable in tests
            ),
            storage=StorageConfig(
                dynamodb_enabled=False,  # Disable in tests
            ),
            metrics=MetricsConfig(
                enabled=False,  # Disable in tests
            ),
        )

    @classmethod
    def for_production(cls) -> "AISecurityConfig":
        """Create production configuration."""
        return cls(
            environment="prod",
            enabled=True,
            model_guardian=ModelGuardianConfig(
                monitor_all_access=True,
                anomaly_detection_enabled=True,
                max_access_log_retention_days=365,
            ),
            training_sentinel=TrainingSentinelConfig(
                poison_detection_enabled=True,
                auto_quarantine=True,
            ),
            alerting=AlertingConfig(
                enabled=True,
                min_severity_to_alert=ThreatSeverity.HIGH,
            ),
            metrics=MetricsConfig(
                publish_interval_seconds=30,
            ),
        )


# Singleton pattern
_ai_security_config: Optional[AISecurityConfig] = None


def get_ai_security_config() -> AISecurityConfig:
    """Get singleton configuration instance."""
    global _ai_security_config
    if _ai_security_config is None:
        _ai_security_config = AISecurityConfig.from_environment()
    return _ai_security_config


def set_ai_security_config(config: AISecurityConfig) -> None:
    """Set singleton configuration instance."""
    global _ai_security_config
    _ai_security_config = config


def reset_ai_security_config() -> None:
    """Reset singleton configuration instance."""
    global _ai_security_config
    _ai_security_config = None
