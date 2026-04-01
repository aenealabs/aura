"""
Project Aura - Supply Chain Security Exceptions

Custom exceptions for SBOM attestation, dependency confusion detection,
and license compliance services.
"""


class SupplyChainError(Exception):
    """Base exception for supply chain services."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SBOMGenerationError(SupplyChainError):
    """Error during SBOM generation."""


class SBOMFormatError(SupplyChainError):
    """Error in SBOM format conversion."""


class AttestationError(SupplyChainError):
    """Error during attestation creation or storage."""


class SigningError(SupplyChainError):
    """Error during SBOM signing."""


class VerificationError(SupplyChainError):
    """Error during attestation verification."""


class SigstoreError(SigningError):
    """Error communicating with Sigstore services."""


class RekorError(SupplyChainError):
    """Error communicating with Rekor transparency log."""


class ConfusionDetectionError(SupplyChainError):
    """Error during dependency confusion detection."""


class PackageMetadataError(ConfusionDetectionError):
    """Error fetching package metadata from registry."""


class LicenseComplianceError(SupplyChainError):
    """Error during license compliance checking."""


class LicenseIdentificationError(LicenseComplianceError):
    """Error identifying license for a component."""


class PolicyViolationError(LicenseComplianceError):
    """License policy violation detected."""

    def __init__(
        self,
        message: str,
        component: str,
        license_id: str,
        policy_rule: str,
        details: dict | None = None,
    ):
        super().__init__(message, details)
        self.component = component
        self.license_id = license_id
        self.policy_rule = policy_rule


class GraphIntegrationError(SupplyChainError):
    """Error during Neptune graph operations."""


class StorageError(SupplyChainError):
    """Error during DynamoDB or S3 operations."""
