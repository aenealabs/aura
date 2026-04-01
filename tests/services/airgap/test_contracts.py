"""
Tests for air-gap service contracts (enums and dataclasses).
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.airgap import (
    AnalysisType,
    BundleStatus,
    BundleType,
    CacheStrategy,
    CompressionType,
    EdgeDeploymentMode,
    FirmwareFormat,
    GraphQueryResult,
    HashAlgorithm,
    InferenceResponse,
    ModelFormat,
    ModelQuantization,
    OfflineCache,
    ProcessorArchitecture,
    RTOSType,
    Severity,
    SigningAlgorithm,
    SyncState,
    SyncStatus,
    VulnerabilityType,
)


class TestBundleEnums:
    """Tests for bundle-related enums."""

    def test_bundle_type_values(self):
        """Test bundle type enum values."""
        assert BundleType.FULL.value == "full"
        assert BundleType.DELTA.value == "delta"
        assert BundleType.SECURITY_PATCH.value == "security-patch"
        assert BundleType.MODEL_UPDATE.value == "model-update"

    def test_bundle_status_values(self):
        """Test bundle status enum values."""
        assert BundleStatus.CREATED.value == "created"
        assert BundleStatus.SIGNED.value == "signed"
        assert BundleStatus.VERIFIED.value == "verified"
        assert BundleStatus.DEPLOYED.value == "deployed"
        assert BundleStatus.FAILED.value == "failed"

    def test_signing_algorithm_values(self):
        """Test signing algorithm enum values."""
        assert SigningAlgorithm.ED25519.value == "ed25519"
        assert SigningAlgorithm.ECDSA_P384.value == "ecdsa-p384"
        assert SigningAlgorithm.RSA_4096.value == "rsa-4096"

    def test_compression_type_values(self):
        """Test compression type enum values."""
        assert CompressionType.NONE.value == "none"
        assert CompressionType.GZIP.value == "gzip"
        assert CompressionType.ZSTD.value == "zstd"
        assert CompressionType.LZ4.value == "lz4"

    def test_hash_algorithm_values(self):
        """Test hash algorithm enum values."""
        assert HashAlgorithm.SHA256.value == "sha256"
        assert HashAlgorithm.SHA384.value == "sha384"
        assert HashAlgorithm.SHA512.value == "sha512"
        assert HashAlgorithm.BLAKE2B.value == "blake2b"


class TestFirmwareEnums:
    """Tests for firmware-related enums."""

    def test_firmware_format_values(self):
        """Test firmware format enum values."""
        assert FirmwareFormat.ELF.value == "elf"
        assert FirmwareFormat.PE.value == "pe"
        assert FirmwareFormat.IHEX.value == "ihex"
        assert FirmwareFormat.BIN.value == "bin"

    def test_rtos_type_values(self):
        """Test RTOS type enum values."""
        assert RTOSType.FREERTOS.value == "freertos"
        assert RTOSType.ZEPHYR.value == "zephyr"
        assert RTOSType.THREADX.value == "threadx"
        assert RTOSType.VXWORKS.value == "vxworks"
        assert RTOSType.UNKNOWN.value == "unknown"

    def test_processor_architecture_values(self):
        """Test processor architecture enum values."""
        assert ProcessorArchitecture.ARM_CORTEX_M.value == "arm-cortex-m"
        assert ProcessorArchitecture.ARM64.value == "arm64"
        assert ProcessorArchitecture.X86_64.value == "x86-64"
        assert ProcessorArchitecture.RISCV32.value == "riscv32"

    def test_vulnerability_type_values(self):
        """Test vulnerability type enum values."""
        assert VulnerabilityType.BUFFER_OVERFLOW.value == "buffer-overflow"
        assert VulnerabilityType.FORMAT_STRING.value == "format-string"
        assert VulnerabilityType.USE_AFTER_FREE.value == "use-after-free"
        assert VulnerabilityType.HARDCODED_CREDENTIALS.value == "hardcoded-credentials"

    def test_severity_ordering(self):
        """Test severity enum ordering."""
        assert Severity.INFO < Severity.LOW
        assert Severity.LOW < Severity.MEDIUM
        assert Severity.MEDIUM < Severity.HIGH
        assert Severity.HIGH < Severity.CRITICAL


class TestEdgeEnums:
    """Tests for edge runtime enums."""

    def test_edge_deployment_mode_values(self):
        """Test edge deployment mode enum values."""
        assert EdgeDeploymentMode.CONNECTED.value == "connected"
        assert EdgeDeploymentMode.DISCONNECTED.value == "disconnected"
        assert EdgeDeploymentMode.TACTICAL.value == "tactical"

    def test_model_quantization_values(self):
        """Test model quantization enum values."""
        assert ModelQuantization.FP32.value == "fp32"
        assert ModelQuantization.INT8.value == "int8"
        assert ModelQuantization.GGUF_Q4_K_M.value == "gguf-q4_k_m"

    def test_sync_status_values(self):
        """Test sync status enum values."""
        assert SyncStatus.SYNCED.value == "synced"
        assert SyncStatus.PENDING.value == "pending"
        assert SyncStatus.OFFLINE.value == "offline"
        assert SyncStatus.ERROR.value == "error"


class TestBundleComponent:
    """Tests for BundleComponent dataclass."""

    def test_create_component(self, sample_component):
        """Test creating a bundle component."""
        assert sample_component.component_id == "comp-test-001"
        assert sample_component.name == "test_component.bin"
        assert sample_component.size_bytes == 26
        assert sample_component.required is True

    def test_to_dict(self, sample_component):
        """Test serialization to dictionary."""
        data = sample_component.to_dict()
        assert data["component_id"] == "comp-test-001"
        assert data["hash_algorithm"] == "sha256"
        assert data["metadata"]["type"] == "test"


class TestBundleManifest:
    """Tests for BundleManifest dataclass."""

    def test_create_manifest(self, sample_manifest):
        """Test creating a bundle manifest."""
        assert sample_manifest.manifest_id == "manifest-test-001"
        assert sample_manifest.bundle_type == BundleType.FULL
        assert sample_manifest.version == "1.0.0"
        assert sample_manifest.component_count == 1

    def test_is_expired_false(self, sample_manifest):
        """Test is_expired when not expired."""
        sample_manifest.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        assert sample_manifest.is_expired is False

    def test_is_expired_true(self, sample_manifest):
        """Test is_expired when expired."""
        sample_manifest.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        assert sample_manifest.is_expired is True

    def test_is_expired_no_expiry(self, sample_manifest):
        """Test is_expired when no expiry set."""
        sample_manifest.expires_at = None
        assert sample_manifest.is_expired is False

    def test_to_dict(self, sample_manifest):
        """Test serialization to dictionary."""
        data = sample_manifest.to_dict()
        assert data["manifest_id"] == "manifest-test-001"
        assert data["bundle_type"] == "full"
        assert data["component_count"] == 1
        assert len(data["components"]) == 1


class TestSignedBundle:
    """Tests for SignedBundle dataclass."""

    def test_create_signed_bundle(self, sample_signed_bundle):
        """Test creating a signed bundle."""
        assert sample_signed_bundle.bundle_id == "bundle-test-001"
        assert sample_signed_bundle.status == BundleStatus.SIGNED
        assert sample_signed_bundle.is_verified is False

    def test_is_verified_when_verified(self, sample_signed_bundle):
        """Test is_verified property when bundle is verified."""
        sample_signed_bundle.status = BundleStatus.VERIFIED
        assert sample_signed_bundle.is_verified is True

    def test_to_dict(self, sample_signed_bundle):
        """Test serialization to dictionary."""
        data = sample_signed_bundle.to_dict()
        assert data["bundle_id"] == "bundle-test-001"
        assert data["status"] == "signed"
        assert "manifest" in data
        assert "signature" in data


class TestDeltaUpdate:
    """Tests for DeltaUpdate dataclass."""

    def test_create_delta(self, sample_delta_update):
        """Test creating a delta update."""
        assert sample_delta_update.delta_id == "delta-test-001"
        assert sample_delta_update.source_version == "1.0.0"
        assert sample_delta_update.target_version == "1.1.0"
        assert sample_delta_update.patch_count == 2

    def test_to_dict(self, sample_delta_update):
        """Test serialization to dictionary."""
        data = sample_delta_update.to_dict()
        assert data["source_version"] == "1.0.0"
        assert data["patch_count"] == 2
        assert len(data["patches"]) == 2


class TestFirmwareImage:
    """Tests for FirmwareImage dataclass."""

    def test_create_image(self, sample_firmware_image):
        """Test creating a firmware image."""
        assert sample_firmware_image.image_id == "fw-test-001"
        assert sample_firmware_image.format == FirmwareFormat.ELF
        assert sample_firmware_image.architecture == ProcessorArchitecture.ARM_CORTEX_M
        assert sample_firmware_image.rtos_type == RTOSType.FREERTOS

    def test_to_dict(self, sample_firmware_image):
        """Test serialization to dictionary."""
        data = sample_firmware_image.to_dict()
        assert data["format"] == "elf"
        assert data["architecture"] == "arm-cortex-m"
        assert data["rtos_type"] == "freertos"


class TestMemorySafetyIssue:
    """Tests for MemorySafetyIssue dataclass."""

    def test_create_issue(self, sample_memory_issue):
        """Test creating a memory safety issue."""
        assert (
            sample_memory_issue.vulnerability_type == VulnerabilityType.BUFFER_OVERFLOW
        )
        assert sample_memory_issue.severity == Severity.HIGH
        assert sample_memory_issue.cwe_id == "CWE-120"
        assert sample_memory_issue.exploitable is True

    def test_to_dict(self, sample_memory_issue):
        """Test serialization to dictionary."""
        data = sample_memory_issue.to_dict()
        assert data["vulnerability_type"] == "buffer-overflow"
        assert data["severity"] == "HIGH"
        assert data["cwe_id"] == "CWE-120"


class TestRTOSTaskInfo:
    """Tests for RTOSTaskInfo dataclass."""

    def test_create_task(self, sample_rtos_task):
        """Test creating RTOS task info."""
        assert sample_rtos_task.name == "MainTask"
        assert sample_rtos_task.priority == 5
        assert sample_rtos_task.stack_size == 4096

    def test_stack_usage_percent(self, sample_rtos_task):
        """Test stack usage calculation."""
        # stack_size=4096, stack_high_water=1024
        # usage = (1 - 1024/4096) * 100 = 75%
        assert sample_rtos_task.stack_usage_percent == 75.0

    def test_to_dict(self, sample_rtos_task):
        """Test serialization to dictionary."""
        data = sample_rtos_task.to_dict()
        assert data["name"] == "MainTask"
        assert data["stack_usage_percent"] == 75.0


class TestFirmwareAnalysisResult:
    """Tests for FirmwareAnalysisResult dataclass."""

    def test_create_result(self, sample_analysis_result):
        """Test creating analysis result."""
        assert sample_analysis_result.analysis_id == "analysis-test-001"
        assert sample_analysis_result.analysis_type == AnalysisType.STATIC
        assert sample_analysis_result.rtos_detected is True
        assert sample_analysis_result.passed is False

    def test_issue_counts(self, sample_analysis_result):
        """Test issue count properties."""
        assert sample_analysis_result.issue_count == 1
        assert sample_analysis_result.high_count == 1
        assert sample_analysis_result.critical_count == 0

    def test_duration(self, sample_analysis_result):
        """Test duration calculation."""
        assert sample_analysis_result.duration_seconds is not None
        assert sample_analysis_result.duration_seconds >= 0

    def test_to_dict(self, sample_analysis_result):
        """Test serialization to dictionary."""
        data = sample_analysis_result.to_dict()
        assert data["rtos_detected"] is True
        assert data["issue_count"] == 1
        assert data["passed"] is False


class TestQuantizedModel:
    """Tests for QuantizedModel dataclass."""

    def test_create_model(self, sample_quantized_model):
        """Test creating a quantized model."""
        assert sample_quantized_model.name == "test-llama"
        assert sample_quantized_model.quantization == ModelQuantization.GGUF_Q4_K_M
        assert sample_quantized_model.format == ModelFormat.GGUF

    def test_size_mb(self, sample_quantized_model):
        """Test size_mb calculation."""
        expected_mb = (1024 + 4) / (1024 * 1024)
        assert sample_quantized_model.size_mb == pytest.approx(expected_mb)

    def test_to_dict(self, sample_quantized_model):
        """Test serialization to dictionary."""
        data = sample_quantized_model.to_dict()
        assert data["quantization"] == "gguf-q4_k_m"
        assert data["format"] == "gguf"


class TestEdgeNode:
    """Tests for EdgeNode dataclass."""

    def test_create_node(self, sample_edge_node):
        """Test creating an edge node."""
        assert sample_edge_node.node_id == "node-test-001"
        assert sample_edge_node.mode == EdgeDeploymentMode.DISCONNECTED
        assert sample_edge_node.ram_mb == 2048

    def test_is_online_offline(self, sample_edge_node):
        """Test is_online when offline."""
        sample_edge_node.sync_status = SyncStatus.OFFLINE
        assert sample_edge_node.is_online is False

    def test_is_online_synced(self, sample_edge_node):
        """Test is_online when synced."""
        sample_edge_node.sync_status = SyncStatus.SYNCED
        assert sample_edge_node.is_online is True

    def test_to_dict(self, sample_edge_node):
        """Test serialization to dictionary."""
        data = sample_edge_node.to_dict()
        assert data["mode"] == "disconnected"
        assert data["architecture"] == "arm64"


class TestOfflineCache:
    """Tests for OfflineCache dataclass."""

    def test_hit_rate_calculation(self):
        """Test cache hit rate calculation."""
        cache = OfflineCache(
            cache_id="cache-001",
            node_id="node-001",
            strategy=CacheStrategy.LRU,
            max_size_mb=512,
            hit_count=80,
            miss_count=20,
        )
        assert cache.hit_rate == 0.8

    def test_hit_rate_no_access(self):
        """Test cache hit rate with no access."""
        cache = OfflineCache(
            cache_id="cache-001",
            node_id="node-001",
            strategy=CacheStrategy.LRU,
            max_size_mb=512,
            hit_count=0,
            miss_count=0,
        )
        assert cache.hit_rate == 0.0

    def test_usage_percent(self):
        """Test cache usage percentage."""
        cache = OfflineCache(
            cache_id="cache-001",
            node_id="node-001",
            strategy=CacheStrategy.LRU,
            max_size_mb=100,
            current_size_mb=75.0,
        )
        assert cache.usage_percent == 75.0


class TestSyncState:
    """Tests for SyncState dataclass."""

    def test_needs_retry_true(self):
        """Test needs_retry when error and retries available."""
        state = SyncState(
            state_id="sync-001",
            node_id="node-001",
            status=SyncStatus.ERROR,
            retry_count=1,
            max_retries=3,
        )
        assert state.needs_retry is True

    def test_needs_retry_false_max_reached(self):
        """Test needs_retry when max retries reached."""
        state = SyncState(
            state_id="sync-001",
            node_id="node-001",
            status=SyncStatus.ERROR,
            retry_count=3,
            max_retries=3,
        )
        assert state.needs_retry is False

    def test_needs_retry_false_not_error(self):
        """Test needs_retry when not in error state."""
        state = SyncState(
            state_id="sync-001",
            node_id="node-001",
            status=SyncStatus.SYNCED,
            retry_count=0,
            max_retries=3,
        )
        assert state.needs_retry is False


class TestInferenceContracts:
    """Tests for inference-related contracts."""

    def test_inference_request(self, sample_inference_request):
        """Test creating an inference request."""
        assert sample_inference_request.prompt == "Hello, world!"
        assert sample_inference_request.max_tokens == 128
        assert sample_inference_request.temperature == 0.7

    def test_inference_response_success(self):
        """Test inference response for success."""
        response = InferenceResponse(
            response_id="resp-001",
            request_id="req-001",
            node_id="node-001",
            model_id="model-001",
            text="Hello! How can I help?",
            tokens_generated=6,
            generation_time_ms=100.0,
        )
        assert response.success is True
        assert response.tokens_per_second == 60.0

    def test_inference_response_error(self):
        """Test inference response with error."""
        response = InferenceResponse(
            response_id="resp-001",
            request_id="req-001",
            node_id="node-001",
            model_id="model-001",
            text="",
            error="Model not loaded",
        )
        assert response.success is False


class TestGraphContracts:
    """Tests for graph-related contracts."""

    def test_graph_query(self, sample_graph_query):
        """Test creating a graph query."""
        assert sample_graph_query.query_type == "sql"
        assert sample_graph_query.timeout_ms == 5000
        assert sample_graph_query.max_results == 100

    def test_graph_query_result_success(self):
        """Test graph query result for success."""
        result = GraphQueryResult(
            result_id="result-001",
            query_id="query-001",
            results=[{"id": "v1", "label": "test"}],
            result_count=1,
            execution_time_ms=10.0,
        )
        assert result.success is True
        assert result.result_count == 1

    def test_graph_query_result_error(self):
        """Test graph query result with error."""
        result = GraphQueryResult(
            result_id="result-001",
            query_id="query-001",
            error="Query timeout",
        )
        assert result.success is False
