"""
Project Aura - Cloud Runtime Security Exceptions

Custom exceptions for runtime security services.

Based on ADR-077: Cloud Runtime Security Integration
"""


class RuntimeSecurityError(Exception):
    """Base exception for all runtime security errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


# Admission Controller Exceptions


class AdmissionControllerError(RuntimeSecurityError):
    """Base exception for admission controller errors."""


class PolicyEvaluationError(AdmissionControllerError):
    """Error evaluating admission policy."""


class ImageVerificationError(AdmissionControllerError):
    """Error verifying container image signature."""


class SBOMVerificationError(AdmissionControllerError):
    """Error verifying SBOM attestation for image."""


class RegistryAccessError(AdmissionControllerError):
    """Error accessing container registry."""


class CVEThresholdExceededError(AdmissionControllerError):
    """CVE count exceeds allowed threshold."""

    def __init__(
        self,
        message: str,
        critical_count: int = 0,
        high_count: int = 0,
        max_critical: int = 0,
        max_high: int = 0,
    ):
        super().__init__(
            message,
            {
                "critical_count": critical_count,
                "high_count": high_count,
                "max_critical": max_critical,
                "max_high": max_high,
            },
        )
        self.critical_count = critical_count
        self.high_count = high_count


class WebhookConfigurationError(AdmissionControllerError):
    """Error in webhook configuration."""


class TLSConfigurationError(AdmissionControllerError):
    """Error in TLS certificate configuration."""


# Runtime Correlator Exceptions


class CorrelatorError(RuntimeSecurityError):
    """Base exception for runtime correlator errors."""


class EventParsingError(CorrelatorError):
    """Error parsing runtime event."""


class CloudTrailError(CorrelatorError):
    """Error with CloudTrail event processing."""


class GuardDutyError(CorrelatorError):
    """Error with GuardDuty finding processing."""


class ResourceMappingError(CorrelatorError):
    """Error mapping AWS resource to IaC."""


class TerraformStateError(CorrelatorError):
    """Error reading Terraform state."""


class GitBlameError(CorrelatorError):
    """Error running git blame for attribution."""


class CorrelationTimeoutError(CorrelatorError):
    """Correlation operation timed out."""


class IaCParsingError(CorrelatorError):
    """Error parsing Infrastructure as Code files."""


# Container Escape Detector Exceptions


class EscapeDetectorError(RuntimeSecurityError):
    """Base exception for escape detector errors."""


class FalcoConnectionError(EscapeDetectorError):
    """Error connecting to Falco."""


class FalcoRuleError(EscapeDetectorError):
    """Error with Falco rule configuration."""


class EBPFError(EscapeDetectorError):
    """Error with eBPF program."""


class EBPFLoadError(EBPFError):
    """Error loading eBPF program into kernel."""


class EBPFPermissionError(EBPFError):
    """Insufficient permissions for eBPF operations."""


class AlertingError(EscapeDetectorError):
    """Error sending escape detection alerts."""


# Graph Integration Exceptions


class GraphIntegrationError(RuntimeSecurityError):
    """Base exception for graph integration errors."""


class NeptuneConnectionError(GraphIntegrationError):
    """Error connecting to Neptune."""


class NeptuneQueryError(GraphIntegrationError):
    """Error executing Neptune query."""


class VertexCreationError(GraphIntegrationError):
    """Error creating graph vertex."""


class EdgeCreationError(GraphIntegrationError):
    """Error creating graph edge."""


# Storage Exceptions


class StorageError(RuntimeSecurityError):
    """Base exception for storage errors."""


class DynamoDBError(StorageError):
    """Error with DynamoDB operations."""


class OpenSearchError(StorageError):
    """Error with OpenSearch operations."""


class KinesisError(StorageError):
    """Error with Kinesis stream operations."""


# OPA/Rego Policy Exceptions


class PolicyError(RuntimeSecurityError):
    """Base exception for policy errors."""


class RegoCompilationError(PolicyError):
    """Error compiling Rego policy."""


class RegoEvaluationError(PolicyError):
    """Error evaluating Rego policy."""


class PolicyNotFoundError(PolicyError):
    """Requested policy not found."""


class InvalidPolicyError(PolicyError):
    """Policy definition is invalid."""
