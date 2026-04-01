"""
Project Aura - Supply Chain Security Configuration

Configuration dataclasses for SBOM attestation, dependency confusion detection,
and license compliance services.

Usage:
    from src.services.supply_chain.config import get_supply_chain_config

    config = get_supply_chain_config()
    print(config.sbom.default_format)
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from .contracts import LicenseCategory, SBOMFormat, SigningMethod


@dataclass
class SBOMConfig:
    """Configuration for SBOM generation."""

    default_format: SBOMFormat = SBOMFormat.CYCLONEDX_1_5_JSON
    include_dev_dependencies: bool = True
    include_transitive: bool = True
    max_components: int = 10000  # Safety limit
    generate_hashes: bool = True
    hash_algorithms: list[str] = field(default_factory=lambda: ["sha256", "sha512"])


@dataclass
class AttestationConfig:
    """Configuration for SBOM attestation and signing."""

    default_signing_method: SigningMethod = SigningMethod.SIGSTORE_KEYLESS
    sigstore_fulcio_url: str = "https://fulcio.sigstore.dev"
    sigstore_rekor_url: str = "https://rekor.sigstore.dev"
    sigstore_oidc_issuer: str = "https://oauth2.sigstore.dev/auth"
    offline_key_path: Optional[str] = None  # Path to Ed25519 private key
    hsm_slot: Optional[int] = None  # PKCS#11 slot for HSM
    record_in_rekor: bool = True
    attestation_ttl_days: int = 365


@dataclass
class ConfusionDetectionConfig:
    """Configuration for dependency confusion detection."""

    enabled: bool = True
    typosquatting_threshold: int = 2  # Max Levenshtein distance
    block_high_risk: bool = True  # Block HIGH/CRITICAL by default
    min_popularity_threshold: int = 1000  # Min downloads for popular package
    cache_ttl_hours: int = 24
    check_internal_namespaces: bool = True
    internal_namespace_prefixes: list[str] = field(default_factory=list)


@dataclass
class LicenseComplianceConfig:
    """Configuration for license compliance checking."""

    enabled: bool = True
    default_policy: str = "permissive-only"
    allowed_categories: list[LicenseCategory] = field(
        default_factory=lambda: [
            LicenseCategory.PERMISSIVE,
            LicenseCategory.PUBLIC_DOMAIN,
        ]
    )
    prohibited_licenses: list[str] = field(
        default_factory=lambda: ["GPL-3.0-only", "AGPL-3.0-only"]
    )
    require_osi_approved: bool = False
    allow_unknown_licenses: bool = False
    generate_attribution: bool = True
    attribution_format: str = "markdown"


@dataclass
class StorageConfig:
    """Configuration for storage backends."""

    sbom_table_name: str = "aura-sbom-documents"
    attestation_table_name: str = "aura-attestations"
    s3_bucket_name: str = "aura-sbom-artifacts"
    neptune_endpoint: Optional[str] = None
    opensearch_endpoint: Optional[str] = None
    use_mock_storage: bool = True  # Default to mock for testing


@dataclass
class MetricsConfig:
    """Configuration for CloudWatch metrics."""

    enabled: bool = True
    namespace: str = "Aura/SupplyChainSecurity"
    buffer_size: int = 20
    flush_interval_seconds: int = 60


@dataclass
class SupplyChainConfig:
    """Root configuration for all supply chain services."""

    environment: str = "dev"
    enabled: bool = True
    sbom: SBOMConfig = field(default_factory=SBOMConfig)
    attestation: AttestationConfig = field(default_factory=AttestationConfig)
    confusion: ConfusionDetectionConfig = field(
        default_factory=ConfusionDetectionConfig
    )
    license: LicenseComplianceConfig = field(default_factory=LicenseComplianceConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    def validate(self) -> list[str]:
        """Validate configuration consistency."""
        errors: list[str] = []

        if self.sbom.max_components < 1:
            errors.append("sbom.max_components must be >= 1")

        if self.confusion.typosquatting_threshold < 1:
            errors.append("confusion.typosquatting_threshold must be >= 1")

        if self.attestation.attestation_ttl_days < 1:
            errors.append("attestation.attestation_ttl_days must be >= 1")

        return errors

    @classmethod
    def from_environment(cls) -> "SupplyChainConfig":
        """Load configuration from environment variables."""
        env = os.environ.get("ENVIRONMENT", "dev")

        # Parse signing method
        signing_method_str = os.environ.get(
            "SUPPLY_CHAIN_SIGNING_METHOD", "sigstore-keyless"
        )
        try:
            signing_method = SigningMethod(signing_method_str)
        except ValueError:
            signing_method = SigningMethod.SIGSTORE_KEYLESS

        # Parse SBOM format
        sbom_format_str = os.environ.get(
            "SUPPLY_CHAIN_SBOM_FORMAT", "cyclonedx-1.5-json"
        )
        try:
            sbom_format = SBOMFormat(sbom_format_str)
        except ValueError:
            sbom_format = SBOMFormat.CYCLONEDX_1_5_JSON

        return cls(
            environment=env,
            enabled=os.environ.get("SUPPLY_CHAIN_ENABLED", "true").lower() == "true",
            sbom=SBOMConfig(
                default_format=sbom_format,
                include_dev_dependencies=os.environ.get(
                    "SUPPLY_CHAIN_INCLUDE_DEV", "true"
                ).lower()
                == "true",
            ),
            attestation=AttestationConfig(
                default_signing_method=signing_method,
                sigstore_fulcio_url=os.environ.get(
                    "SIGSTORE_FULCIO_URL", "https://fulcio.sigstore.dev"
                ),
                sigstore_rekor_url=os.environ.get(
                    "SIGSTORE_REKOR_URL", "https://rekor.sigstore.dev"
                ),
                offline_key_path=os.environ.get("SUPPLY_CHAIN_OFFLINE_KEY_PATH"),
                record_in_rekor=os.environ.get(
                    "SUPPLY_CHAIN_RECORD_REKOR", "true"
                ).lower()
                == "true",
            ),
            confusion=ConfusionDetectionConfig(
                enabled=os.environ.get("SUPPLY_CHAIN_CONFUSION_ENABLED", "true").lower()
                == "true",
                typosquatting_threshold=int(
                    os.environ.get("SUPPLY_CHAIN_TYPOSQUAT_THRESHOLD", "2")
                ),
                block_high_risk=os.environ.get(
                    "SUPPLY_CHAIN_BLOCK_HIGH_RISK", "true"
                ).lower()
                == "true",
            ),
            license=LicenseComplianceConfig(
                enabled=os.environ.get("SUPPLY_CHAIN_LICENSE_ENABLED", "true").lower()
                == "true",
                require_osi_approved=os.environ.get(
                    "SUPPLY_CHAIN_REQUIRE_OSI", "false"
                ).lower()
                == "true",
                allow_unknown_licenses=os.environ.get(
                    "SUPPLY_CHAIN_ALLOW_UNKNOWN", "false"
                ).lower()
                == "true",
            ),
            storage=StorageConfig(
                sbom_table_name=os.environ.get(
                    "SUPPLY_CHAIN_SBOM_TABLE", f"aura-sbom-documents-{env}"
                ),
                attestation_table_name=os.environ.get(
                    "SUPPLY_CHAIN_ATTESTATION_TABLE", f"aura-attestations-{env}"
                ),
                s3_bucket_name=os.environ.get(
                    "SUPPLY_CHAIN_S3_BUCKET", f"aura-sbom-artifacts-{env}"
                ),
                neptune_endpoint=os.environ.get("NEPTUNE_ENDPOINT"),
                opensearch_endpoint=os.environ.get("OPENSEARCH_ENDPOINT"),
                use_mock_storage=os.environ.get(
                    "SUPPLY_CHAIN_MOCK_STORAGE", "true"
                ).lower()
                == "true",
            ),
            metrics=MetricsConfig(
                enabled=os.environ.get("SUPPLY_CHAIN_METRICS_ENABLED", "true").lower()
                == "true",
                namespace=os.environ.get(
                    "SUPPLY_CHAIN_METRICS_NAMESPACE", "Aura/SupplyChainSecurity"
                ),
            ),
        )

    @classmethod
    def for_production(cls) -> "SupplyChainConfig":
        """Create production-hardened configuration."""
        return cls(
            environment="prod",
            enabled=True,
            sbom=SBOMConfig(
                default_format=SBOMFormat.CYCLONEDX_1_5_JSON,
                include_dev_dependencies=False,  # Exclude dev deps in prod
                generate_hashes=True,
            ),
            attestation=AttestationConfig(
                default_signing_method=SigningMethod.SIGSTORE_KEYLESS,
                record_in_rekor=True,
            ),
            confusion=ConfusionDetectionConfig(
                enabled=True,
                block_high_risk=True,
            ),
            license=LicenseComplianceConfig(
                enabled=True,
                require_osi_approved=True,
                allow_unknown_licenses=False,
            ),
            storage=StorageConfig(
                use_mock_storage=False,
            ),
            metrics=MetricsConfig(
                enabled=True,
            ),
        )

    @classmethod
    def for_testing(cls) -> "SupplyChainConfig":
        """Create configuration for unit tests."""
        return cls(
            environment="test",
            enabled=True,
            sbom=SBOMConfig(
                default_format=SBOMFormat.INTERNAL,
                max_components=100,
            ),
            attestation=AttestationConfig(
                default_signing_method=SigningMethod.NONE,
                record_in_rekor=False,
            ),
            confusion=ConfusionDetectionConfig(
                enabled=True,
                block_high_risk=False,
            ),
            license=LicenseComplianceConfig(
                enabled=True,
                allow_unknown_licenses=True,
            ),
            storage=StorageConfig(
                use_mock_storage=True,
            ),
            metrics=MetricsConfig(
                enabled=False,
            ),
        )


# Singleton instance
_config_instance: Optional[SupplyChainConfig] = None


def get_supply_chain_config() -> SupplyChainConfig:
    """Get singleton configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = SupplyChainConfig.from_environment()
    return _config_instance


def reset_supply_chain_config() -> None:
    """Reset configuration singleton (for testing)."""
    global _config_instance
    _config_instance = None


def set_supply_chain_config(config: SupplyChainConfig) -> None:
    """Set configuration singleton (for testing)."""
    global _config_instance
    _config_instance = config
