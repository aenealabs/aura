"""
Project Aura - Air-Gapped and Edge Deployment Services

This module provides services for air-gap orchestration, firmware security analysis,
and tactical edge runtime for disconnected and resource-constrained environments.

Based on ADR-078: Air-Gapped and Edge Deployment

Services:
    - AirGapOrchestrator: Bundle creation, signing, verification, and deployment
    - FirmwareAnalyzer: Embedded firmware security analysis
    - EdgeRuntime: Tactical edge runtime with quantized LLM inference

Legacy Services (from original implementation):
    - EgressValidator: Network egress blocking validation
    - ModelVerifier: Model weight verification
    - InferenceAuditLogger: Inference audit logging

Usage:
    from src.services.airgap import (
        get_airgap_orchestrator,
        get_firmware_analyzer,
        get_edge_runtime,
    )

    # Bundle management
    orchestrator = get_airgap_orchestrator()
    manifest = orchestrator.create_bundle(
        bundle_type=BundleType.FULL,
        version="1.0.0",
        components=[{"name": "app", "path": "/path/to/app"}],
    )

    # Firmware analysis
    analyzer = get_firmware_analyzer()
    image = analyzer.load_image("/path/to/firmware.bin")
    result = analyzer.analyze(image)

    # Edge inference
    runtime = get_edge_runtime()
    model = runtime.register_model("llama", "llama-2", "/path/to/model.gguf")
    runtime.load_model(model.model_id)
    request = runtime.create_inference_request(model.model_id, "Hello, world!")
    response = runtime.infer(request)
"""

# =============================================================================
# Legacy Exports (preserve backward compatibility)
# =============================================================================
from src.services.airgap.egress_validator import (
    EgressValidator,
    EgressViolation,
    validate_air_gap_mode,
)
from src.services.airgap.inference_audit import (
    InferenceAuditEvent,
    InferenceAuditLogger,
)
from src.services.airgap.model_verifier import (
    ModelIntegrityError,
    ModelVerifier,
    verify_model_checksums,
)

# =============================================================================
# Air-Gap Orchestrator
# =============================================================================
from .air_gap_orchestrator import (
    AirGapOrchestrator,
    get_airgap_orchestrator,
    reset_airgap_orchestrator,
)

# =============================================================================
# Configuration
# =============================================================================
from .config import (
    AirGapConfig,
    BundleConfig,
    EdgeRuntimeConfig,
    FirmwareAnalysisConfig,
    LocalGraphConfig,
    MetricsConfig,
    OfflineCacheConfig,
    QuantizedModelConfig,
    RTOSDetectionConfig,
    SyncConfig,
    TransferConfig,
    get_airgap_config,
    reset_airgap_config,
    set_airgap_config,
)

# =============================================================================
# Contracts - Dataclasses
# =============================================================================
# =============================================================================
# Contracts - Enums
# =============================================================================
from .contracts import (
    AnalysisType,
    BundleComponent,
    BundleManifest,
    BundleSignature,
    BundleStatus,
    BundleType,
    CacheStrategy,
    CompressionType,
    DeltaUpdate,
    EdgeDeploymentMode,
    EdgeNode,
    FirmwareAnalysisResult,
    FirmwareFormat,
    FirmwareImage,
    GraphQuery,
    GraphQueryResult,
    HashAlgorithm,
    InferenceRequest,
    InferenceResponse,
    MemorySafetyIssue,
    ModelFormat,
    ModelQuantization,
    OfflineCache,
    ProcessorArchitecture,
    QuantizedModel,
    RTOSTaskInfo,
    RTOSType,
    Severity,
    SignedBundle,
    SigningAlgorithm,
    SyncState,
    SyncStatus,
    VulnerabilityType,
)

# =============================================================================
# Edge Runtime
# =============================================================================
from .edge_runtime import (
    EdgeRuntime,
    LocalGraphStore,
    OfflineCacheManager,
    get_edge_runtime,
    reset_edge_runtime,
)

# =============================================================================
# Exceptions
# =============================================================================
from .exceptions import (
    AirGapError,
    BinwalkError,
    BundleCorruptedError,
    BundleCreationError,
    BundleError,
    BundleExpiredError,
    BundleNotFoundError,
    BundleSigningError,
    BundleTooLargeError,
    BundleVerificationError,
    CacheError,
    CacheFullError,
    CacheKeyNotFoundError,
    ContextLengthExceededError,
    CryptoError,
    DecryptionError,
    DeltaUpdateError,
    EdgeRuntimeError,
    EncryptionError,
    FirmwareAnalysisError,
    FirmwareError,
    FirmwareParseError,
    FirmwareTooLargeError,
    GhidraError,
    GraphConnectionError,
    GraphError,
    GraphQueryError,
    GraphQueryTimeoutError,
    InferenceError,
    InferenceTimeoutError,
    InsufficientResourcesError,
    KeyNotFoundError,
    ModelError,
    ModelLoadError,
    ModelNotFoundError,
    ModelTooLargeError,
    NodeNotFoundError,
    NodeOfflineError,
    QuarantineError,
    RTOSDetectionError,
    SignatureVerificationError,
    SyncConflictError,
    SyncError,
    SyncTimeoutError,
    TransferError,
    TransferMediumError,
    TransferTimeoutError,
    UnsupportedFirmwareFormat,
)

# =============================================================================
# Firmware Analyzer
# =============================================================================
from .firmware_analyzer import (
    FirmwareAnalyzer,
    get_firmware_analyzer,
    reset_firmware_analyzer,
)

# =============================================================================
# Metrics
# =============================================================================
from .metrics import AirGapMetricsPublisher, get_airgap_metrics, reset_airgap_metrics

__all__ = [
    # Legacy exports
    "EgressValidator",
    "EgressViolation",
    "validate_air_gap_mode",
    "ModelVerifier",
    "ModelIntegrityError",
    "verify_model_checksums",
    "InferenceAuditLogger",
    "InferenceAuditEvent",
    # Enums
    "AnalysisType",
    "BundleStatus",
    "BundleType",
    "CacheStrategy",
    "CompressionType",
    "EdgeDeploymentMode",
    "FirmwareFormat",
    "HashAlgorithm",
    "ModelFormat",
    "ModelQuantization",
    "ProcessorArchitecture",
    "RTOSType",
    "Severity",
    "SigningAlgorithm",
    "SyncStatus",
    "VulnerabilityType",
    # Dataclasses
    "BundleComponent",
    "BundleManifest",
    "BundleSignature",
    "DeltaUpdate",
    "EdgeNode",
    "FirmwareAnalysisResult",
    "FirmwareImage",
    "GraphQuery",
    "GraphQueryResult",
    "InferenceRequest",
    "InferenceResponse",
    "MemorySafetyIssue",
    "OfflineCache",
    "QuantizedModel",
    "RTOSTaskInfo",
    "SignedBundle",
    "SyncState",
    # Configuration
    "AirGapConfig",
    "BundleConfig",
    "EdgeRuntimeConfig",
    "FirmwareAnalysisConfig",
    "LocalGraphConfig",
    "MetricsConfig",
    "OfflineCacheConfig",
    "QuantizedModelConfig",
    "RTOSDetectionConfig",
    "SyncConfig",
    "TransferConfig",
    "get_airgap_config",
    "reset_airgap_config",
    "set_airgap_config",
    # Exceptions
    "AirGapError",
    "BinwalkError",
    "BundleCorruptedError",
    "BundleCreationError",
    "BundleError",
    "BundleExpiredError",
    "BundleNotFoundError",
    "BundleSigningError",
    "BundleTooLargeError",
    "BundleVerificationError",
    "CacheError",
    "CacheFullError",
    "CacheKeyNotFoundError",
    "ContextLengthExceededError",
    "CryptoError",
    "DecryptionError",
    "DeltaUpdateError",
    "EdgeRuntimeError",
    "EncryptionError",
    "FirmwareAnalysisError",
    "FirmwareError",
    "FirmwareParseError",
    "FirmwareTooLargeError",
    "GhidraError",
    "GraphConnectionError",
    "GraphError",
    "GraphQueryError",
    "GraphQueryTimeoutError",
    "InferenceError",
    "InferenceTimeoutError",
    "InsufficientResourcesError",
    "KeyNotFoundError",
    "ModelError",
    "ModelLoadError",
    "ModelNotFoundError",
    "ModelTooLargeError",
    "NodeNotFoundError",
    "NodeOfflineError",
    "QuarantineError",
    "RTOSDetectionError",
    "SignatureVerificationError",
    "SyncConflictError",
    "SyncError",
    "SyncTimeoutError",
    "TransferError",
    "TransferMediumError",
    "TransferTimeoutError",
    "UnsupportedFirmwareFormat",
    # Metrics
    "AirGapMetricsPublisher",
    "get_airgap_metrics",
    "reset_airgap_metrics",
    # Services
    "AirGapOrchestrator",
    "get_airgap_orchestrator",
    "reset_airgap_orchestrator",
    "FirmwareAnalyzer",
    "get_firmware_analyzer",
    "reset_firmware_analyzer",
    "EdgeRuntime",
    "LocalGraphStore",
    "OfflineCacheManager",
    "get_edge_runtime",
    "reset_edge_runtime",
]
