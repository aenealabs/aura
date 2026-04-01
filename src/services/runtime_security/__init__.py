"""
Project Aura - Cloud Runtime Security Services

Provides Kubernetes admission control, runtime-to-code correlation, and
container escape detection for enterprise cloud security.

Architecture:
- AdmissionController: Kubernetes ValidatingWebhook for policy enforcement
- RuntimeCorrelator: Maps runtime events to source code via IaC
- ContainerEscapeDetector: eBPF and Falco-based escape detection

Usage:
    from src.services.runtime_security import (
        AdmissionController,
        RuntimeCorrelator,
        ContainerEscapeDetector,
        get_admission_controller,
        get_runtime_correlator,
        get_escape_detector,
    )

    # Validate Kubernetes admission request
    controller = get_admission_controller()
    decision = controller.validate(request)

    # Correlate runtime event to code
    correlator = get_runtime_correlator()
    event = correlator.ingest_cloudtrail_event(raw_event)
    result = correlator.correlate(event)

    # Detect container escape attempts
    detector = get_escape_detector()
    escape = detector.process_ebpf_event(raw_event)

Compliance:
- CMMC 2.0 SI.L2-3.14.6: Container monitoring and alerting
- NIST 800-53 SI-4: Runtime monitoring via eBPF
- NIST 800-53 CM-3: Admission control for configuration changes
- SOC 2 CC6.1: Audit trail for admission decisions

Based on ADR-077: Cloud Runtime Security Integration
"""

# Admission Controller exports
from .admission_controller import (
    AdmissionController,
    get_admission_controller,
    reset_admission_controller,
)

# Configuration exports
from .config import (
    AdmissionControllerConfig,
    EscapeDetectorConfig,
    GraphIntegrationConfig,
    MetricsConfig,
    RuntimeCorrelatorConfig,
    RuntimeSecurityConfig,
    StorageConfig,
    get_runtime_security_config,
    reset_runtime_security_config,
    set_runtime_security_config,
)

# Contract exports - Type aliases
# Contract exports - Dataclasses
# Contract exports - Enums
from .contracts import (
    AdmissionDecision,
    AdmissionDecisionType,
    AdmissionPolicy,
    AdmissionRequest,
    AdmissionWebhookConfig,
    AWSResource,
    ClusterName,
    ContainerImage,
    CorrelationResult,
    CorrelationStatus,
    DecisionId,
    EscapeEvent,
    EscapeTechnique,
    EventId,
    EventType,
    FalcoRule,
    IaCProvider,
    IaCResource,
    ImageDigest,
    PolicyId,
    PolicyMode,
    PolicyType,
    PolicyViolation,
    ResourceARN,
    ResourceMapping,
    ResourceType,
    RuntimeEvent,
    Severity,
)

# Container Escape Detector exports
from .escape_detector import (
    ContainerEscapeDetector,
    get_escape_detector,
    reset_escape_detector,
)

# Exception exports
from .exceptions import (
    AdmissionControllerError,
    AlertingError,
    CloudTrailError,
    CorrelationTimeoutError,
    CorrelatorError,
    CVEThresholdExceededError,
    DynamoDBError,
    EBPFError,
    EBPFLoadError,
    EBPFPermissionError,
    EdgeCreationError,
    EscapeDetectorError,
    EventParsingError,
    FalcoConnectionError,
    FalcoRuleError,
    GitBlameError,
    GraphIntegrationError,
    GuardDutyError,
    IaCParsingError,
    ImageVerificationError,
    InvalidPolicyError,
    KinesisError,
    NeptuneConnectionError,
    NeptuneQueryError,
    OpenSearchError,
    PolicyError,
    PolicyEvaluationError,
    PolicyNotFoundError,
    RegistryAccessError,
    RegoCompilationError,
    RegoEvaluationError,
    ResourceMappingError,
    RuntimeSecurityError,
    SBOMVerificationError,
    StorageError,
    TerraformStateError,
    TLSConfigurationError,
    VertexCreationError,
    WebhookConfigurationError,
)

# Graph Integration exports
from .graph_integration import (
    EdgeLabel,
    GraphEdge,
    GraphVertex,
    RuntimeSecurityGraphService,
    VertexLabel,
    escape_gremlin_string,
    get_runtime_security_graph_service,
    reset_runtime_security_graph_service,
)

# Metrics exports
from .metrics import (
    MetricsTimer,
    RuntimeSecurityMetricsPublisher,
    get_runtime_security_metrics,
    reset_runtime_security_metrics,
)

# Runtime Correlator exports
from .runtime_correlator import (
    RuntimeCorrelator,
    get_runtime_correlator,
    reset_runtime_correlator,
)

__all__ = [
    # Enums
    "EventType",
    "Severity",
    "AdmissionDecisionType",
    "CorrelationStatus",
    "IaCProvider",
    "ResourceType",
    "EscapeTechnique",
    "PolicyType",
    "PolicyMode",
    "VertexLabel",
    "EdgeLabel",
    # Dataclasses
    "RuntimeEvent",
    "AWSResource",
    "IaCResource",
    "ContainerImage",
    "PolicyViolation",
    "AdmissionPolicy",
    "AdmissionRequest",
    "AdmissionDecision",
    "EscapeEvent",
    "CorrelationResult",
    "ResourceMapping",
    "FalcoRule",
    "AdmissionWebhookConfig",
    "GraphVertex",
    "GraphEdge",
    # Type aliases
    "EventId",
    "ResourceARN",
    "ClusterName",
    "DecisionId",
    "ImageDigest",
    "PolicyId",
    # Configuration
    "RuntimeSecurityConfig",
    "AdmissionControllerConfig",
    "RuntimeCorrelatorConfig",
    "EscapeDetectorConfig",
    "GraphIntegrationConfig",
    "StorageConfig",
    "MetricsConfig",
    "get_runtime_security_config",
    "reset_runtime_security_config",
    "set_runtime_security_config",
    # Exceptions
    "RuntimeSecurityError",
    "AdmissionControllerError",
    "PolicyEvaluationError",
    "ImageVerificationError",
    "SBOMVerificationError",
    "RegistryAccessError",
    "CVEThresholdExceededError",
    "WebhookConfigurationError",
    "TLSConfigurationError",
    "CorrelatorError",
    "EventParsingError",
    "CloudTrailError",
    "GuardDutyError",
    "ResourceMappingError",
    "TerraformStateError",
    "GitBlameError",
    "CorrelationTimeoutError",
    "IaCParsingError",
    "EscapeDetectorError",
    "FalcoConnectionError",
    "FalcoRuleError",
    "EBPFError",
    "EBPFLoadError",
    "EBPFPermissionError",
    "AlertingError",
    "GraphIntegrationError",
    "NeptuneConnectionError",
    "NeptuneQueryError",
    "VertexCreationError",
    "EdgeCreationError",
    "StorageError",
    "DynamoDBError",
    "OpenSearchError",
    "KinesisError",
    "PolicyError",
    "RegoCompilationError",
    "RegoEvaluationError",
    "PolicyNotFoundError",
    "InvalidPolicyError",
    # Metrics
    "RuntimeSecurityMetricsPublisher",
    "get_runtime_security_metrics",
    "reset_runtime_security_metrics",
    "MetricsTimer",
    # Admission Controller
    "AdmissionController",
    "get_admission_controller",
    "reset_admission_controller",
    # Runtime Correlator
    "RuntimeCorrelator",
    "get_runtime_correlator",
    "reset_runtime_correlator",
    # Container Escape Detector
    "ContainerEscapeDetector",
    "get_escape_detector",
    "reset_escape_detector",
    # Graph Integration
    "RuntimeSecurityGraphService",
    "get_runtime_security_graph_service",
    "reset_runtime_security_graph_service",
    "escape_gremlin_string",
]

__version__ = "1.0.0"
