"""
Tests for context provenance configuration.

Tests configuration validation and environment-specific settings.
"""

from src.services.context_provenance import (
    AnomalyDetectionConfig,
    ProvenanceConfig,
    TrustScoringConfig,
    get_anomaly_detection_config,
    get_default_config,
    get_trust_scoring_config,
)


class TestProvenanceConfig:
    """Test ProvenanceConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ProvenanceConfig()
        assert config.min_trust_threshold == 0.30
        assert config.high_trust_threshold == 0.80
        assert config.medium_trust_threshold == 0.50
        assert config.anomaly_threshold == 0.70
        assert config.environment == "dev"

    def test_trust_weight_defaults(self):
        """Test trust weight default values."""
        config = ProvenanceConfig()
        assert config.repository_weight == 0.35
        assert config.author_weight == 0.25
        assert config.age_weight == 0.15
        assert config.verification_weight == 0.25
        # Weights should sum to 1.0
        total = (
            config.repository_weight
            + config.author_weight
            + config.age_weight
            + config.verification_weight
        )
        assert abs(total - 1.0) < 0.01

    def test_age_threshold_defaults(self):
        """Test age threshold default values."""
        config = ProvenanceConfig()
        assert config.established_age_days == 90
        assert config.stable_age_days == 30
        assert config.recent_age_days == 7
        assert config.new_age_days == 1

    def test_table_names(self):
        """Test default table names."""
        config = ProvenanceConfig()
        assert config.quarantine_table == "aura-context-quarantine"
        assert config.audit_table == "aura-provenance-audit"
        assert config.author_trust_table == "aura-author-trust"

    def test_get_table_name(self):
        """Test get_table_name with environment."""
        config = ProvenanceConfig(environment="dev")
        assert config.get_table_name("aura-test") == "aura-test-dev"

        config = ProvenanceConfig(environment="prod")
        assert config.get_table_name("aura-test") == "aura-test-prod"

    def test_validate_success(self):
        """Test validation with valid config."""
        config = ProvenanceConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_validate_invalid_trust_threshold(self):
        """Test validation with invalid trust threshold."""
        config = ProvenanceConfig(min_trust_threshold=1.5)
        errors = config.validate()
        assert any("min_trust_threshold" in e for e in errors)

        config = ProvenanceConfig(min_trust_threshold=-0.1)
        errors = config.validate()
        assert any("min_trust_threshold" in e for e in errors)

    def test_validate_invalid_anomaly_threshold(self):
        """Test validation with invalid anomaly threshold."""
        config = ProvenanceConfig(anomaly_threshold=2.0)
        errors = config.validate()
        assert any("anomaly_threshold" in e for e in errors)

    def test_validate_invalid_weights(self):
        """Test validation with invalid weight sum."""
        config = ProvenanceConfig(
            repository_weight=0.5,
            author_weight=0.5,
            age_weight=0.5,
            verification_weight=0.5,
        )
        errors = config.validate()
        assert any("weights must sum" in e for e in errors)

    def test_validate_invalid_age_order(self):
        """Test validation with invalid age threshold order."""
        config = ProvenanceConfig(
            established_age_days=30,
            stable_age_days=90,  # Out of order
            recent_age_days=7,
            new_age_days=1,
        )
        errors = config.validate()
        assert any("descending order" in e for e in errors)

    def test_custom_org_ids(self):
        """Test custom organization IDs."""
        config = ProvenanceConfig(
            internal_org_ids=["org-1", "org-2"],
            partner_org_ids=["partner-1"],
            flagged_repo_ids=["bad-repo"],
        )
        assert len(config.internal_org_ids) == 2
        assert len(config.partner_org_ids) == 1
        assert "bad-repo" in config.flagged_repo_ids

    def test_auto_quarantine_settings(self):
        """Test auto-quarantine settings."""
        config = ProvenanceConfig()
        assert config.auto_quarantine_on_integrity_failure is True
        assert config.auto_quarantine_on_low_trust is True
        assert config.auto_quarantine_on_anomaly is True

    def test_audit_settings(self):
        """Test audit settings."""
        config = ProvenanceConfig()
        assert config.audit_all_retrievals is False
        assert config.audit_high_trust_content is False

    def test_performance_settings(self):
        """Test performance settings."""
        config = ProvenanceConfig()
        assert config.batch_verification_size == 50
        assert config.max_concurrent_verifications == 10
        assert config.verification_cache_ttl_seconds == 300


class TestTrustScoringConfig:
    """Test TrustScoringConfig dataclass."""

    def test_default_repo_trust_values(self):
        """Test default repository trust values."""
        config = TrustScoringConfig()
        assert config.repo_trust_internal == 1.00
        assert config.repo_trust_partner == 0.90
        assert config.repo_trust_public_high == 0.70
        assert config.repo_trust_public_low == 0.50
        assert config.repo_trust_unknown == 0.30
        assert config.repo_trust_flagged == 0.00

    def test_default_author_trust_values(self):
        """Test default author trust values."""
        config = TrustScoringConfig()
        assert config.author_trust_employee == 1.00
        assert config.author_trust_known == 0.90
        assert config.author_trust_contributor == 0.70
        assert config.author_trust_first_time == 0.50
        assert config.author_trust_unverified == 0.30
        assert config.author_gpg_bonus == 0.10

    def test_default_age_trust_values(self):
        """Test default age trust values."""
        config = TrustScoringConfig()
        assert config.age_trust_established == 1.00
        assert config.age_trust_stable == 0.90
        assert config.age_trust_recent == 0.80
        assert config.age_trust_new == 0.70
        assert config.age_trust_brand_new == 0.50

    def test_default_verification_trust_values(self):
        """Test default verification trust values."""
        config = TrustScoringConfig()
        assert config.verification_trust_recent == 1.00
        assert config.verification_trust_stale == 0.90
        assert config.verification_trust_old == 0.70
        assert config.verification_trust_failed == 0.00

    def test_repo_trust_ordering(self):
        """Test repository trust values are ordered correctly."""
        config = TrustScoringConfig()
        assert config.repo_trust_internal >= config.repo_trust_partner
        assert config.repo_trust_partner >= config.repo_trust_public_high
        assert config.repo_trust_public_high >= config.repo_trust_public_low
        assert config.repo_trust_public_low >= config.repo_trust_unknown
        assert config.repo_trust_unknown >= config.repo_trust_flagged

    def test_age_trust_ordering(self):
        """Test age trust values are ordered correctly."""
        config = TrustScoringConfig()
        assert config.age_trust_established >= config.age_trust_stable
        assert config.age_trust_stable >= config.age_trust_recent
        assert config.age_trust_recent >= config.age_trust_new
        assert config.age_trust_new >= config.age_trust_brand_new


class TestAnomalyDetectionConfig:
    """Test AnomalyDetectionConfig dataclass."""

    def test_default_threshold_values(self):
        """Test default threshold values."""
        config = AnomalyDetectionConfig()
        assert config.injection_threshold == 0.70
        assert config.obfuscation_threshold == 0.60
        assert config.statistical_outlier_threshold == 0.50

    def test_default_content_limits(self):
        """Test default content limit values."""
        config = AnomalyDetectionConfig()
        assert config.max_line_length == 500
        assert config.max_chunk_size == 100000

    def test_default_scan_settings(self):
        """Test default scan settings."""
        config = AnomalyDetectionConfig()
        assert config.scan_comments is True
        assert config.scan_strings is True
        assert config.scan_docstrings is True

    def test_statistical_analysis_settings(self):
        """Test statistical analysis settings."""
        config = AnomalyDetectionConfig()
        assert config.enable_statistical_analysis is True
        assert config.min_samples_for_stats == 100


class TestGetDefaultConfig:
    """Test get_default_config function."""

    def test_dev_environment(self):
        """Test default config for dev environment."""
        config = get_default_config("dev")
        assert config.environment == "dev"
        assert config.audit_all_retrievals is False
        assert config.verification_cache_ttl_seconds == 300

    def test_qa_environment(self):
        """Test default config for QA environment."""
        config = get_default_config("qa")
        assert config.environment == "qa"
        assert config.audit_all_retrievals is True

    def test_prod_environment(self):
        """Test default config for production environment."""
        config = get_default_config("prod")
        assert config.environment == "prod"
        assert config.audit_all_retrievals is True
        assert config.audit_high_trust_content is True
        assert config.verification_cache_ttl_seconds == 60  # Shorter in prod


class TestGetTrustScoringConfig:
    """Test get_trust_scoring_config function."""

    def test_returns_config(self):
        """Test that function returns a TrustScoringConfig."""
        config = get_trust_scoring_config()
        assert isinstance(config, TrustScoringConfig)

    def test_returns_default_values(self):
        """Test that function returns default values."""
        config = get_trust_scoring_config()
        assert config.repo_trust_internal == 1.00
        assert config.author_trust_employee == 1.00


class TestGetAnomalyDetectionConfig:
    """Test get_anomaly_detection_config function."""

    def test_returns_config(self):
        """Test that function returns an AnomalyDetectionConfig."""
        config = get_anomaly_detection_config()
        assert isinstance(config, AnomalyDetectionConfig)

    def test_returns_default_values(self):
        """Test that function returns default values."""
        config = get_anomaly_detection_config()
        assert config.injection_threshold == 0.70
        assert config.scan_comments is True
