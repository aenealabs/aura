"""
Tests for supply chain security configuration.
"""

import os
from unittest.mock import patch

from src.services.supply_chain import (
    AttestationConfig,
    ConfusionDetectionConfig,
    LicenseCategory,
    LicenseComplianceConfig,
    MetricsConfig,
    SBOMConfig,
    SBOMFormat,
    SigningMethod,
    StorageConfig,
    SupplyChainConfig,
    get_supply_chain_config,
    reset_supply_chain_config,
    set_supply_chain_config,
)


class TestSBOMConfig:
    """Tests for SBOMConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = SBOMConfig()
        assert config.default_format == SBOMFormat.CYCLONEDX_1_5_JSON
        assert config.include_dev_dependencies is True
        assert config.include_transitive is True
        assert config.max_components == 10000
        assert config.generate_hashes is True
        assert "sha256" in config.hash_algorithms
        assert "sha512" in config.hash_algorithms

    def test_custom_values(self):
        """Test custom configuration values."""
        config = SBOMConfig(
            default_format=SBOMFormat.SPDX_2_3_JSON,
            include_dev_dependencies=False,
            max_components=5000,
        )
        assert config.default_format == SBOMFormat.SPDX_2_3_JSON
        assert config.include_dev_dependencies is False
        assert config.max_components == 5000


class TestAttestationConfig:
    """Tests for AttestationConfig."""

    def test_default_values(self):
        """Test default attestation configuration."""
        config = AttestationConfig()
        assert config.default_signing_method == SigningMethod.SIGSTORE_KEYLESS
        assert config.sigstore_fulcio_url == "https://fulcio.sigstore.dev"
        assert config.sigstore_rekor_url == "https://rekor.sigstore.dev"
        assert config.record_in_rekor is True
        assert config.attestation_ttl_days == 365
        assert config.offline_key_path is None
        assert config.hsm_slot is None

    def test_offline_signing_config(self):
        """Test offline signing configuration."""
        config = AttestationConfig(
            default_signing_method=SigningMethod.OFFLINE_KEY,
            offline_key_path="/path/to/key.pem",
            record_in_rekor=False,
        )
        assert config.default_signing_method == SigningMethod.OFFLINE_KEY
        assert config.offline_key_path == "/path/to/key.pem"
        assert config.record_in_rekor is False


class TestConfusionDetectionConfig:
    """Tests for ConfusionDetectionConfig."""

    def test_default_values(self):
        """Test default confusion detection configuration."""
        config = ConfusionDetectionConfig()
        assert config.enabled is True
        assert config.typosquatting_threshold == 2
        assert config.block_high_risk is True
        assert config.min_popularity_threshold == 1000
        assert config.cache_ttl_hours == 24
        assert config.check_internal_namespaces is True

    def test_with_internal_namespaces(self):
        """Test configuration with internal namespaces."""
        config = ConfusionDetectionConfig(
            internal_namespace_prefixes=["aura-", "internal-"],
        )
        assert "aura-" in config.internal_namespace_prefixes
        assert "internal-" in config.internal_namespace_prefixes


class TestLicenseComplianceConfig:
    """Tests for LicenseComplianceConfig."""

    def test_default_values(self):
        """Test default license compliance configuration."""
        config = LicenseComplianceConfig()
        assert config.enabled is True
        assert config.default_policy == "permissive-only"
        assert LicenseCategory.PERMISSIVE in config.allowed_categories
        assert LicenseCategory.PUBLIC_DOMAIN in config.allowed_categories
        assert "GPL-3.0-only" in config.prohibited_licenses
        assert config.require_osi_approved is False
        assert config.allow_unknown_licenses is False
        assert config.generate_attribution is True
        assert config.attribution_format == "markdown"

    def test_strict_configuration(self):
        """Test strict license configuration."""
        config = LicenseComplianceConfig(
            require_osi_approved=True,
            allow_unknown_licenses=False,
            prohibited_licenses=["GPL-2.0-only", "GPL-3.0-only", "AGPL-3.0-only"],
        )
        assert config.require_osi_approved is True
        assert len(config.prohibited_licenses) == 3


class TestStorageConfig:
    """Tests for StorageConfig."""

    def test_default_values(self):
        """Test default storage configuration."""
        config = StorageConfig()
        assert config.sbom_table_name == "aura-sbom-documents"
        assert config.attestation_table_name == "aura-attestations"
        assert config.s3_bucket_name == "aura-sbom-artifacts"
        assert config.use_mock_storage is True
        assert config.neptune_endpoint is None


class TestMetricsConfig:
    """Tests for MetricsConfig."""

    def test_default_values(self):
        """Test default metrics configuration."""
        config = MetricsConfig()
        assert config.enabled is True
        assert config.namespace == "Aura/SupplyChainSecurity"
        assert config.buffer_size == 20
        assert config.flush_interval_seconds == 60


class TestSupplyChainConfig:
    """Tests for SupplyChainConfig."""

    def test_default_values(self):
        """Test default root configuration."""
        config = SupplyChainConfig()
        assert config.environment == "dev"
        assert config.enabled is True
        assert isinstance(config.sbom, SBOMConfig)
        assert isinstance(config.attestation, AttestationConfig)
        assert isinstance(config.confusion, ConfusionDetectionConfig)
        assert isinstance(config.license, LicenseComplianceConfig)
        assert isinstance(config.storage, StorageConfig)
        assert isinstance(config.metrics, MetricsConfig)

    def test_validate_valid_config(self):
        """Test validation passes for valid config."""
        config = SupplyChainConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_validate_invalid_config(self):
        """Test validation catches invalid values."""
        config = SupplyChainConfig(
            sbom=SBOMConfig(max_components=0),
            confusion=ConfusionDetectionConfig(typosquatting_threshold=0),
            attestation=AttestationConfig(attestation_ttl_days=0),
        )
        errors = config.validate()
        assert len(errors) == 3
        assert any("max_components" in e for e in errors)
        assert any("typosquatting_threshold" in e for e in errors)
        assert any("attestation_ttl_days" in e for e in errors)

    def test_for_production(self):
        """Test production configuration."""
        config = SupplyChainConfig.for_production()
        assert config.environment == "prod"
        assert config.sbom.include_dev_dependencies is False
        assert config.attestation.record_in_rekor is True
        assert config.confusion.block_high_risk is True
        assert config.license.require_osi_approved is True
        assert config.storage.use_mock_storage is False

    def test_for_testing(self):
        """Test test configuration."""
        config = SupplyChainConfig.for_testing()
        assert config.environment == "test"
        assert config.sbom.max_components == 100
        assert config.attestation.default_signing_method == SigningMethod.NONE
        assert config.attestation.record_in_rekor is False
        assert config.storage.use_mock_storage is True
        assert config.metrics.enabled is False

    def test_from_environment_defaults(self):
        """Test loading from environment with defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = SupplyChainConfig.from_environment()
            assert config.environment == "dev"
            assert config.enabled is True

    def test_from_environment_custom(self):
        """Test loading from environment with custom values."""
        env_vars = {
            "ENVIRONMENT": "staging",
            "SUPPLY_CHAIN_ENABLED": "false",
            "SUPPLY_CHAIN_SBOM_FORMAT": "spdx-2.3-json",
            "SUPPLY_CHAIN_SIGNING_METHOD": "offline-key",
            "SUPPLY_CHAIN_INCLUDE_DEV": "false",
            "SUPPLY_CHAIN_CONFUSION_ENABLED": "true",
            "SUPPLY_CHAIN_TYPOSQUAT_THRESHOLD": "3",
            "SUPPLY_CHAIN_LICENSE_ENABLED": "true",
            "SUPPLY_CHAIN_REQUIRE_OSI": "true",
            "SUPPLY_CHAIN_MOCK_STORAGE": "false",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = SupplyChainConfig.from_environment()
            assert config.environment == "staging"
            assert config.enabled is False
            assert config.sbom.default_format == SBOMFormat.SPDX_2_3_JSON
            assert config.sbom.include_dev_dependencies is False
            assert (
                config.attestation.default_signing_method == SigningMethod.OFFLINE_KEY
            )
            assert config.confusion.typosquatting_threshold == 3
            assert config.license.require_osi_approved is True
            assert config.storage.use_mock_storage is False


class TestConfigSingleton:
    """Tests for configuration singleton pattern."""

    def test_get_supply_chain_config(self, test_config):
        """Test getting singleton configuration."""
        config = get_supply_chain_config()
        assert config.environment == "test"

    def test_reset_supply_chain_config(self, test_config):
        """Test resetting singleton."""
        config1 = get_supply_chain_config()
        reset_supply_chain_config()
        # After reset, should create new instance from environment
        with patch.dict(os.environ, {"ENVIRONMENT": "new-env"}, clear=True):
            config2 = get_supply_chain_config()
            assert config2.environment == "new-env"

    def test_set_supply_chain_config(self):
        """Test setting custom configuration."""
        custom = SupplyChainConfig(environment="custom")
        set_supply_chain_config(custom)
        config = get_supply_chain_config()
        assert config.environment == "custom"
