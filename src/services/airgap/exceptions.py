"""
Project Aura - Air-Gapped and Edge Deployment Exceptions

Custom exception classes for air-gap orchestration, firmware security analysis,
and tactical edge runtime services.

Based on ADR-078: Air-Gapped and Edge Deployment
"""

from typing import Any, Optional


class AirGapError(Exception):
    """Base exception for all air-gap related errors."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code or "AIRGAP_ERROR"
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to dictionary."""
        return {
            "error": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# Bundle Errors
# =============================================================================


class BundleError(AirGapError):
    """Base exception for bundle-related errors."""

    def __init__(
        self,
        message: str,
        bundle_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "BUNDLE_ERROR", details)
        self.bundle_id = bundle_id
        if bundle_id:
            self.details["bundle_id"] = bundle_id


class BundleCreationError(BundleError):
    """Error creating a deployment bundle."""

    def __init__(
        self,
        message: str,
        bundle_id: Optional[str] = None,
        component: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, bundle_id, details)
        self.code = "BUNDLE_CREATION_ERROR"
        self.component = component
        if component:
            self.details["component"] = component


class BundleSigningError(BundleError):
    """Error signing a bundle."""

    def __init__(
        self,
        message: str,
        bundle_id: Optional[str] = None,
        algorithm: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, bundle_id, details)
        self.code = "BUNDLE_SIGNING_ERROR"
        self.algorithm = algorithm
        if algorithm:
            self.details["algorithm"] = algorithm


class BundleVerificationError(BundleError):
    """Error verifying bundle signature or integrity."""

    def __init__(
        self,
        message: str,
        bundle_id: Optional[str] = None,
        expected_hash: Optional[str] = None,
        actual_hash: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, bundle_id, details)
        self.code = "BUNDLE_VERIFICATION_ERROR"
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        if expected_hash:
            self.details["expected_hash"] = expected_hash
        if actual_hash:
            self.details["actual_hash"] = actual_hash


class BundleNotFoundError(BundleError):
    """Bundle not found."""

    def __init__(
        self,
        bundle_id: str,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(f"Bundle not found: {bundle_id}", bundle_id, details)
        self.code = "BUNDLE_NOT_FOUND"


class BundleExpiredError(BundleError):
    """Bundle has expired."""

    def __init__(
        self,
        bundle_id: str,
        expired_at: str,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            f"Bundle expired at {expired_at}: {bundle_id}",
            bundle_id,
            details,
        )
        self.code = "BUNDLE_EXPIRED"
        self.expired_at = expired_at
        self.details["expired_at"] = expired_at


class BundleCorruptedError(BundleError):
    """Bundle is corrupted."""

    def __init__(
        self,
        message: str,
        bundle_id: Optional[str] = None,
        corruption_type: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, bundle_id, details)
        self.code = "BUNDLE_CORRUPTED"
        self.corruption_type = corruption_type
        if corruption_type:
            self.details["corruption_type"] = corruption_type


class BundleTooLargeError(BundleError):
    """Bundle exceeds size limit."""

    def __init__(
        self,
        bundle_id: str,
        size_bytes: int,
        max_size_bytes: int,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            f"Bundle size {size_bytes} exceeds limit {max_size_bytes}",
            bundle_id,
            details,
        )
        self.code = "BUNDLE_TOO_LARGE"
        self.size_bytes = size_bytes
        self.max_size_bytes = max_size_bytes
        self.details["size_bytes"] = size_bytes
        self.details["max_size_bytes"] = max_size_bytes


class DeltaUpdateError(BundleError):
    """Error creating or applying delta update."""

    def __init__(
        self,
        message: str,
        source_version: Optional[str] = None,
        target_version: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, None, details)
        self.code = "DELTA_UPDATE_ERROR"
        self.source_version = source_version
        self.target_version = target_version
        if source_version:
            self.details["source_version"] = source_version
        if target_version:
            self.details["target_version"] = target_version


# =============================================================================
# Transfer Errors
# =============================================================================


class TransferError(AirGapError):
    """Base exception for transfer-related errors."""

    def __init__(
        self,
        message: str,
        transfer_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "TRANSFER_ERROR", details)
        self.transfer_id = transfer_id
        if transfer_id:
            self.details["transfer_id"] = transfer_id


class TransferTimeoutError(TransferError):
    """Transfer operation timed out."""

    def __init__(
        self,
        message: str,
        transfer_id: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, transfer_id, details)
        self.code = "TRANSFER_TIMEOUT"
        self.timeout_seconds = timeout_seconds
        if timeout_seconds:
            self.details["timeout_seconds"] = timeout_seconds


class TransferMediumError(TransferError):
    """Error with transfer medium (USB, disk, etc.)."""

    def __init__(
        self,
        message: str,
        medium_type: Optional[str] = None,
        device_path: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, None, details)
        self.code = "TRANSFER_MEDIUM_ERROR"
        self.medium_type = medium_type
        self.device_path = device_path
        if medium_type:
            self.details["medium_type"] = medium_type
        if device_path:
            self.details["device_path"] = device_path


class QuarantineError(TransferError):
    """Error during quarantine process."""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        reason: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, None, details)
        self.code = "QUARANTINE_ERROR"
        self.file_path = file_path
        self.reason = reason
        if file_path:
            self.details["file_path"] = file_path
        if reason:
            self.details["reason"] = reason


# =============================================================================
# Firmware Analysis Errors
# =============================================================================


class FirmwareError(AirGapError):
    """Base exception for firmware analysis errors."""

    def __init__(
        self,
        message: str,
        image_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "FIRMWARE_ERROR", details)
        self.image_id = image_id
        if image_id:
            self.details["image_id"] = image_id


class FirmwareParseError(FirmwareError):
    """Error parsing firmware image."""

    def __init__(
        self,
        message: str,
        image_id: Optional[str] = None,
        format: Optional[str] = None,
        offset: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, image_id, details)
        self.code = "FIRMWARE_PARSE_ERROR"
        self.format = format
        self.offset = offset
        if format:
            self.details["format"] = format
        if offset is not None:
            self.details["offset"] = offset


class FirmwareAnalysisError(FirmwareError):
    """Error during firmware analysis."""

    def __init__(
        self,
        message: str,
        image_id: Optional[str] = None,
        analysis_type: Optional[str] = None,
        tool: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, image_id, details)
        self.code = "FIRMWARE_ANALYSIS_ERROR"
        self.analysis_type = analysis_type
        self.tool = tool
        if analysis_type:
            self.details["analysis_type"] = analysis_type
        if tool:
            self.details["tool"] = tool


class FirmwareTooLargeError(FirmwareError):
    """Firmware image exceeds size limit."""

    def __init__(
        self,
        image_id: str,
        size_bytes: int,
        max_size_bytes: int,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            f"Firmware size {size_bytes} exceeds limit {max_size_bytes}",
            image_id,
            details,
        )
        self.code = "FIRMWARE_TOO_LARGE"
        self.size_bytes = size_bytes
        self.max_size_bytes = max_size_bytes
        self.details["size_bytes"] = size_bytes
        self.details["max_size_bytes"] = max_size_bytes


class UnsupportedFirmwareFormat(FirmwareError):
    """Firmware format not supported."""

    def __init__(
        self,
        format: str,
        supported_formats: Optional[list[str]] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(f"Unsupported firmware format: {format}", None, details)
        self.code = "UNSUPPORTED_FIRMWARE_FORMAT"
        self.format = format
        self.supported_formats = supported_formats or []
        self.details["format"] = format
        self.details["supported_formats"] = self.supported_formats


class RTOSDetectionError(FirmwareError):
    """Error detecting RTOS."""

    def __init__(
        self,
        message: str,
        image_id: Optional[str] = None,
        detected_signatures: Optional[list[str]] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, image_id, details)
        self.code = "RTOS_DETECTION_ERROR"
        self.detected_signatures = detected_signatures or []
        if detected_signatures:
            self.details["detected_signatures"] = detected_signatures


class BinwalkError(FirmwareError):
    """Error running Binwalk analysis."""

    def __init__(
        self,
        message: str,
        image_id: Optional[str] = None,
        exit_code: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, image_id, details)
        self.code = "BINWALK_ERROR"
        self.exit_code = exit_code
        if exit_code is not None:
            self.details["exit_code"] = exit_code


class GhidraError(FirmwareError):
    """Error running Ghidra analysis."""

    def __init__(
        self,
        message: str,
        image_id: Optional[str] = None,
        script: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, image_id, details)
        self.code = "GHIDRA_ERROR"
        self.script = script
        if script:
            self.details["script"] = script


# =============================================================================
# Edge Runtime Errors
# =============================================================================


class EdgeRuntimeError(AirGapError):
    """Base exception for edge runtime errors."""

    def __init__(
        self,
        message: str,
        node_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "EDGE_RUNTIME_ERROR", details)
        self.node_id = node_id
        if node_id:
            self.details["node_id"] = node_id


class NodeNotFoundError(EdgeRuntimeError):
    """Edge node not found."""

    def __init__(
        self,
        node_id: str,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(f"Edge node not found: {node_id}", node_id, details)
        self.code = "NODE_NOT_FOUND"


class NodeOfflineError(EdgeRuntimeError):
    """Edge node is offline."""

    def __init__(
        self,
        node_id: str,
        last_seen: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(f"Edge node is offline: {node_id}", node_id, details)
        self.code = "NODE_OFFLINE"
        self.last_seen = last_seen
        if last_seen:
            self.details["last_seen"] = last_seen


class InsufficientResourcesError(EdgeRuntimeError):
    """Insufficient resources on edge node."""

    def __init__(
        self,
        message: str,
        node_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        required: Optional[int] = None,
        available: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, node_id, details)
        self.code = "INSUFFICIENT_RESOURCES"
        self.resource_type = resource_type
        self.required = required
        self.available = available
        if resource_type:
            self.details["resource_type"] = resource_type
        if required is not None:
            self.details["required"] = required
        if available is not None:
            self.details["available"] = available


# =============================================================================
# Model Errors
# =============================================================================


class ModelError(AirGapError):
    """Base exception for model-related errors."""

    def __init__(
        self,
        message: str,
        model_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "MODEL_ERROR", details)
        self.model_id = model_id
        if model_id:
            self.details["model_id"] = model_id


class ModelNotFoundError(ModelError):
    """Model not found."""

    def __init__(
        self,
        model_id: str,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(f"Model not found: {model_id}", model_id, details)
        self.code = "MODEL_NOT_FOUND"


class ModelLoadError(ModelError):
    """Error loading model."""

    def __init__(
        self,
        message: str,
        model_id: Optional[str] = None,
        format: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, model_id, details)
        self.code = "MODEL_LOAD_ERROR"
        self.format = format
        if format:
            self.details["format"] = format


class ModelTooLargeError(ModelError):
    """Model exceeds memory limit."""

    def __init__(
        self,
        model_id: str,
        required_mb: int,
        available_mb: int,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            f"Model requires {required_mb}MB but only {available_mb}MB available",
            model_id,
            details,
        )
        self.code = "MODEL_TOO_LARGE"
        self.required_mb = required_mb
        self.available_mb = available_mb
        self.details["required_mb"] = required_mb
        self.details["available_mb"] = available_mb


class InferenceError(ModelError):
    """Error during inference."""

    def __init__(
        self,
        message: str,
        model_id: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, model_id, details)
        self.code = "INFERENCE_ERROR"
        self.request_id = request_id
        if request_id:
            self.details["request_id"] = request_id


class InferenceTimeoutError(InferenceError):
    """Inference operation timed out."""

    def __init__(
        self,
        model_id: str,
        timeout_seconds: int,
        tokens_generated: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            f"Inference timed out after {timeout_seconds}s",
            model_id,
            None,
            details,
        )
        self.code = "INFERENCE_TIMEOUT"
        self.timeout_seconds = timeout_seconds
        self.tokens_generated = tokens_generated
        self.details["timeout_seconds"] = timeout_seconds
        if tokens_generated is not None:
            self.details["tokens_generated"] = tokens_generated


class ContextLengthExceededError(InferenceError):
    """Input exceeds model context length."""

    def __init__(
        self,
        model_id: str,
        input_tokens: int,
        max_tokens: int,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            f"Input ({input_tokens} tokens) exceeds context length ({max_tokens})",
            model_id,
            None,
            details,
        )
        self.code = "CONTEXT_LENGTH_EXCEEDED"
        self.input_tokens = input_tokens
        self.max_tokens = max_tokens
        self.details["input_tokens"] = input_tokens
        self.details["max_tokens"] = max_tokens


# =============================================================================
# Graph Errors
# =============================================================================


class GraphError(AirGapError):
    """Base exception for local graph database errors."""

    def __init__(
        self,
        message: str,
        query_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "GRAPH_ERROR", details)
        self.query_id = query_id
        if query_id:
            self.details["query_id"] = query_id


class GraphConnectionError(GraphError):
    """Error connecting to local graph database."""

    def __init__(
        self,
        message: str,
        database_path: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, None, details)
        self.code = "GRAPH_CONNECTION_ERROR"
        self.database_path = database_path
        if database_path:
            self.details["database_path"] = database_path


class GraphQueryError(GraphError):
    """Error executing graph query."""

    def __init__(
        self,
        message: str,
        query_id: Optional[str] = None,
        query_text: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, query_id, details)
        self.code = "GRAPH_QUERY_ERROR"
        self.query_text = query_text
        if query_text:
            self.details["query_text"] = query_text[:500]  # Truncate for safety


class GraphQueryTimeoutError(GraphQueryError):
    """Graph query timed out."""

    def __init__(
        self,
        query_id: str,
        timeout_ms: int,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            f"Query timed out after {timeout_ms}ms",
            query_id,
            None,
            details,
        )
        self.code = "GRAPH_QUERY_TIMEOUT"
        self.timeout_ms = timeout_ms
        self.details["timeout_ms"] = timeout_ms


# =============================================================================
# Sync Errors
# =============================================================================


class SyncError(AirGapError):
    """Base exception for synchronization errors."""

    def __init__(
        self,
        message: str,
        node_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "SYNC_ERROR", details)
        self.node_id = node_id
        if node_id:
            self.details["node_id"] = node_id


class SyncConflictError(SyncError):
    """Synchronization conflict detected."""

    def __init__(
        self,
        message: str,
        node_id: Optional[str] = None,
        local_version: Optional[str] = None,
        remote_version: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, node_id, details)
        self.code = "SYNC_CONFLICT"
        self.local_version = local_version
        self.remote_version = remote_version
        if local_version:
            self.details["local_version"] = local_version
        if remote_version:
            self.details["remote_version"] = remote_version


class SyncTimeoutError(SyncError):
    """Synchronization operation timed out."""

    def __init__(
        self,
        node_id: str,
        timeout_seconds: int,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            f"Sync timed out after {timeout_seconds}s",
            node_id,
            details,
        )
        self.code = "SYNC_TIMEOUT"
        self.timeout_seconds = timeout_seconds
        self.details["timeout_seconds"] = timeout_seconds


# =============================================================================
# Cache Errors
# =============================================================================


class CacheError(AirGapError):
    """Base exception for cache errors."""

    def __init__(
        self,
        message: str,
        cache_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "CACHE_ERROR", details)
        self.cache_id = cache_id
        if cache_id:
            self.details["cache_id"] = cache_id


class CacheFullError(CacheError):
    """Cache is full."""

    def __init__(
        self,
        cache_id: str,
        current_size_mb: float,
        max_size_mb: int,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            f"Cache full: {current_size_mb}MB / {max_size_mb}MB",
            cache_id,
            details,
        )
        self.code = "CACHE_FULL"
        self.current_size_mb = current_size_mb
        self.max_size_mb = max_size_mb
        self.details["current_size_mb"] = current_size_mb
        self.details["max_size_mb"] = max_size_mb


class CacheKeyNotFoundError(CacheError):
    """Cache key not found."""

    def __init__(
        self,
        key: str,
        cache_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(f"Cache key not found: {key}", cache_id, details)
        self.code = "CACHE_KEY_NOT_FOUND"
        self.key = key
        self.details["key"] = key


# =============================================================================
# Cryptographic Errors
# =============================================================================


class CryptoError(AirGapError):
    """Base exception for cryptographic errors."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "CRYPTO_ERROR", details)
        self.operation = operation
        if operation:
            self.details["operation"] = operation


class KeyNotFoundError(CryptoError):
    """Cryptographic key not found."""

    def __init__(
        self,
        key_id: str,
        key_type: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(f"Key not found: {key_id}", None, details)
        self.code = "KEY_NOT_FOUND"
        self.key_id = key_id
        self.key_type = key_type
        self.details["key_id"] = key_id
        if key_type:
            self.details["key_type"] = key_type


class SignatureVerificationError(CryptoError):
    """Signature verification failed."""

    def __init__(
        self,
        message: str,
        signature_id: Optional[str] = None,
        algorithm: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "verify", details)
        self.code = "SIGNATURE_VERIFICATION_ERROR"
        self.signature_id = signature_id
        self.algorithm = algorithm
        if signature_id:
            self.details["signature_id"] = signature_id
        if algorithm:
            self.details["algorithm"] = algorithm


class EncryptionError(CryptoError):
    """Encryption operation failed."""

    def __init__(
        self,
        message: str,
        algorithm: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "encrypt", details)
        self.code = "ENCRYPTION_ERROR"
        self.algorithm = algorithm
        if algorithm:
            self.details["algorithm"] = algorithm


class DecryptionError(CryptoError):
    """Decryption operation failed."""

    def __init__(
        self,
        message: str,
        algorithm: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "decrypt", details)
        self.code = "DECRYPTION_ERROR"
        self.algorithm = algorithm
        if algorithm:
            self.details["algorithm"] = algorithm
