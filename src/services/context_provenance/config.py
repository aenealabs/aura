"""
Project Aura - Context Provenance Configuration

Configuration management for the context provenance and integrity system.
Defines thresholds, timeouts, and operational settings.

Author: Project Aura Team
Created: 2026-01-25
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProvenanceConfig:
    """Configuration for the context provenance system."""

    # Trust score thresholds
    min_trust_threshold: float = 0.30
    high_trust_threshold: float = 0.80
    medium_trust_threshold: float = 0.50

    # Anomaly detection thresholds
    anomaly_threshold: float = 0.70
    injection_similarity_threshold: float = 0.70

    # Verification cache settings
    verification_cache_ttl_seconds: int = 300
    provenance_cache_ttl_seconds: int = 600

    # Trust score weights
    repository_weight: float = 0.35
    author_weight: float = 0.25
    age_weight: float = 0.15
    verification_weight: float = 0.25

    # Content age thresholds (days)
    established_age_days: int = 90
    stable_age_days: int = 30
    recent_age_days: int = 7
    new_age_days: int = 1

    # Author trust thresholds
    known_author_commits: int = 10
    contributor_min_commits: int = 1

    # Organization IDs
    internal_org_ids: list[str] = field(default_factory=list)
    partner_org_ids: list[str] = field(default_factory=list)
    flagged_repo_ids: list[str] = field(default_factory=list)

    # DynamoDB table names
    quarantine_table: str = "aura-context-quarantine"
    audit_table: str = "aura-provenance-audit"
    author_trust_table: str = "aura-author-trust"

    # CloudWatch settings
    metrics_namespace: str = "Aura/ContextProvenance"
    log_group: str = "/aura/provenance/audit"

    # SNS settings
    alert_topic_arn: Optional[str] = None

    # EventBridge settings
    event_bus_name: str = "aura-security-events"

    # Performance settings
    batch_verification_size: int = 50
    max_concurrent_verifications: int = 10

    # Quarantine settings
    auto_quarantine_on_integrity_failure: bool = True
    auto_quarantine_on_low_trust: bool = True
    auto_quarantine_on_anomaly: bool = True

    # Audit settings
    audit_all_retrievals: bool = False  # Only audit failures by default
    audit_high_trust_content: bool = False  # Skip audit for trusted content

    # Environment
    environment: str = "dev"

    def get_table_name(self, base_name: str) -> str:
        """Get environment-specific table name."""
        return f"{base_name}-{self.environment}"

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        # Validate thresholds
        if not 0.0 <= self.min_trust_threshold <= 1.0:
            errors.append("min_trust_threshold must be between 0.0 and 1.0")

        if not 0.0 <= self.anomaly_threshold <= 1.0:
            errors.append("anomaly_threshold must be between 0.0 and 1.0")

        # Validate weights sum to 1.0
        weight_sum = (
            self.repository_weight
            + self.author_weight
            + self.age_weight
            + self.verification_weight
        )
        if abs(weight_sum - 1.0) > 0.01:
            errors.append(f"Trust score weights must sum to 1.0, got {weight_sum}")

        # Validate age thresholds are ordered
        if not (
            self.established_age_days
            > self.stable_age_days
            > self.recent_age_days
            > self.new_age_days
        ):
            errors.append("Age thresholds must be in descending order")

        return errors


@dataclass
class TrustScoringConfig:
    """Configuration specific to trust scoring."""

    # Repository trust levels
    repo_trust_internal: float = 1.00
    repo_trust_partner: float = 0.90
    repo_trust_public_high: float = 0.70
    repo_trust_public_low: float = 0.50
    repo_trust_unknown: float = 0.30
    repo_trust_flagged: float = 0.00

    # Author trust levels
    author_trust_employee: float = 1.00
    author_trust_known: float = 0.90
    author_trust_contributor: float = 0.70
    author_trust_first_time: float = 0.50
    author_trust_unverified: float = 0.30
    author_gpg_bonus: float = 0.10

    # Age trust levels
    age_trust_established: float = 1.00
    age_trust_stable: float = 0.90
    age_trust_recent: float = 0.80
    age_trust_new: float = 0.70
    age_trust_brand_new: float = 0.50

    # Verification trust levels
    verification_trust_recent: float = 1.00
    verification_trust_stale: float = 0.90
    verification_trust_old: float = 0.70
    verification_trust_failed: float = 0.00


@dataclass
class AnomalyDetectionConfig:
    """Configuration specific to anomaly detection."""

    # Detection thresholds
    injection_threshold: float = 0.70
    obfuscation_threshold: float = 0.60
    statistical_outlier_threshold: float = 0.50

    # Content characteristics
    max_line_length: int = 500
    max_chunk_size: int = 100000

    # Pattern matching
    scan_comments: bool = True
    scan_strings: bool = True
    scan_docstrings: bool = True

    # Statistical analysis
    enable_statistical_analysis: bool = True
    min_samples_for_stats: int = 100


def get_default_config(environment: str = "dev") -> ProvenanceConfig:
    """Get default configuration for environment."""
    config = ProvenanceConfig(environment=environment)

    # Environment-specific overrides
    if environment == "prod":
        config.audit_all_retrievals = True
        config.audit_high_trust_content = True
        config.verification_cache_ttl_seconds = 60  # Shorter cache in prod
    elif environment == "qa":
        config.audit_all_retrievals = True

    return config


def get_trust_scoring_config() -> TrustScoringConfig:
    """Get default trust scoring configuration."""
    return TrustScoringConfig()


def get_anomaly_detection_config() -> AnomalyDetectionConfig:
    """Get default anomaly detection configuration."""
    return AnomalyDetectionConfig()
