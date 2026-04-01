"""
Project Aura - Supply Chain Security Services

Provides SBOM attestation, dependency confusion detection, and license compliance
capabilities for enterprise software supply chain security.

Architecture:
- SBOMAttestationService: Generates and signs SBOMs in CycloneDX/SPDX formats
- DependencyConfusionDetector: Detects typosquatting and namespace hijacking
- LicenseComplianceEngine: Checks license compatibility and generates attribution

Usage:
    from src.services.supply_chain import (
        SBOMAttestationService,
        DependencyConfusionDetector,
        LicenseComplianceEngine,
        get_sbom_attestation_service,
        get_dependency_confusion_detector,
        get_license_compliance_engine,
    )

    # Generate SBOM
    sbom_service = get_sbom_attestation_service()
    sbom = sbom_service.generate_sbom(repository_id="repo-123")

    # Check for dependency confusion
    detector = get_dependency_confusion_detector()
    results = detector.analyze_dependencies(sbom)

    # Check license compliance
    engine = get_license_compliance_engine()
    report = engine.check_compliance(sbom)

Compliance:
- Executive Order 14028: SBOM requirements
- NTIA Minimum Elements: CycloneDX/SPDX format support
- CMMC Level 3: CM-8 (System Component Inventory)
- NIST 800-53: SA-10 (Developer Configuration Management)
"""

# Configuration exports
from .config import (
    AttestationConfig,
    ConfusionDetectionConfig,
    LicenseComplianceConfig,
    MetricsConfig,
    SBOMConfig,
    StorageConfig,
    SupplyChainConfig,
    get_supply_chain_config,
    reset_supply_chain_config,
    set_supply_chain_config,
)

# Contract exports - Type aliases
# Contract exports - Dataclasses
# Contract exports - Enums
from .contracts import (
    Attestation,
    AttestationId,
    ComplianceReport,
    ComplianceStatus,
    ConfusionIndicator,
    ConfusionResult,
    ConfusionType,
    LicenseCategory,
    LicenseInfo,
    LicensePolicy,
    LicenseViolation,
    PackageURL,
    ProvenanceChain,
    RepositoryId,
    RiskLevel,
    SBOMComponent,
    SBOMDocument,
    SBOMFormat,
    SBOMId,
    SigningMethod,
    VerificationResult,
    VerificationStatus,
)

# Dependency Confusion Detector exports
from .dependency_detector import (
    DependencyConfusionDetector,
    get_dependency_confusion_detector,
    reset_dependency_confusion_detector,
)

# Exception exports
from .exceptions import (
    AttestationError,
    ConfusionDetectionError,
    GraphIntegrationError,
    LicenseComplianceError,
    LicenseIdentificationError,
    PackageMetadataError,
    PolicyViolationError,
    RekorError,
    SBOMFormatError,
    SBOMGenerationError,
    SigningError,
    SigstoreError,
    StorageError,
    SupplyChainError,
    VerificationError,
)

# Graph Integration exports
from .graph_integration import (
    SupplyChainGraphService,
    get_supply_chain_graph_service,
    reset_supply_chain_graph_service,
)

# License Compliance Engine exports
from .license_engine import (
    LicenseComplianceEngine,
    get_license_compliance_engine,
    reset_license_compliance_engine,
)

# Metrics exports
from .metrics import (
    MetricsTimer,
    SupplyChainMetricsPublisher,
    get_supply_chain_metrics,
    reset_supply_chain_metrics,
)

# Popular packages database exports
from .popular_packages import (
    PopularPackage,
    get_popular_packages,
    get_similar_popular_packages,
    is_popular_package,
)

# SBOM Attestation Service exports
from .sbom_attestation import (
    SBOMAttestationService,
    get_sbom_attestation_service,
    reset_sbom_attestation_service,
)

__all__ = [
    # Enums
    "SBOMFormat",
    "SigningMethod",
    "ConfusionType",
    "LicenseCategory",
    "RiskLevel",
    "ComplianceStatus",
    "VerificationStatus",
    # Dataclasses
    "SBOMComponent",
    "SBOMDocument",
    "Attestation",
    "VerificationResult",
    "ConfusionIndicator",
    "ConfusionResult",
    "LicenseInfo",
    "LicensePolicy",
    "LicenseViolation",
    "ComplianceReport",
    "ProvenanceChain",
    # Type aliases
    "SBOMId",
    "AttestationId",
    "RepositoryId",
    "PackageURL",
    # Configuration
    "SupplyChainConfig",
    "SBOMConfig",
    "AttestationConfig",
    "ConfusionDetectionConfig",
    "LicenseComplianceConfig",
    "StorageConfig",
    "MetricsConfig",
    "get_supply_chain_config",
    "reset_supply_chain_config",
    "set_supply_chain_config",
    # Exceptions
    "SupplyChainError",
    "SBOMGenerationError",
    "SBOMFormatError",
    "AttestationError",
    "SigningError",
    "VerificationError",
    "SigstoreError",
    "RekorError",
    "ConfusionDetectionError",
    "PackageMetadataError",
    "LicenseComplianceError",
    "LicenseIdentificationError",
    "PolicyViolationError",
    "GraphIntegrationError",
    "StorageError",
    # Metrics
    "SupplyChainMetricsPublisher",
    "get_supply_chain_metrics",
    "reset_supply_chain_metrics",
    "MetricsTimer",
    # SBOM Attestation Service
    "SBOMAttestationService",
    "get_sbom_attestation_service",
    "reset_sbom_attestation_service",
    # Dependency Confusion Detector
    "DependencyConfusionDetector",
    "get_dependency_confusion_detector",
    "reset_dependency_confusion_detector",
    # Popular Packages
    "PopularPackage",
    "get_popular_packages",
    "get_similar_popular_packages",
    "is_popular_package",
    # License Compliance Engine
    "LicenseComplianceEngine",
    "get_license_compliance_engine",
    "reset_license_compliance_engine",
    # Graph Integration
    "SupplyChainGraphService",
    "get_supply_chain_graph_service",
    "reset_supply_chain_graph_service",
]

__version__ = "1.0.0"
