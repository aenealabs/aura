"""
Pytest fixtures for air-gap service tests.
"""

import os
import tempfile
from datetime import datetime, timezone

import pytest

from src.services.airgap import (
    AirGapConfig,
    AirGapOrchestrator,
    AnalysisType,
    BundleComponent,
    BundleManifest,
    BundleSignature,
    BundleStatus,
    BundleType,
    CompressionType,
    DeltaUpdate,
    EdgeDeploymentMode,
    EdgeNode,
    EdgeRuntime,
    FirmwareAnalysisResult,
    FirmwareAnalyzer,
    FirmwareFormat,
    FirmwareImage,
    GraphQuery,
    HashAlgorithm,
    InferenceRequest,
    MemorySafetyIssue,
    ModelFormat,
    ModelQuantization,
    ProcessorArchitecture,
    QuantizedModel,
    RTOSTaskInfo,
    RTOSType,
    Severity,
    SignedBundle,
    SigningAlgorithm,
    SyncStatus,
    VulnerabilityType,
    reset_airgap_config,
    reset_airgap_metrics,
    reset_airgap_orchestrator,
    reset_edge_runtime,
    reset_firmware_analyzer,
    set_airgap_config,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before and after each test."""
    reset_airgap_config()
    reset_airgap_metrics()
    reset_airgap_orchestrator()
    reset_firmware_analyzer()
    reset_edge_runtime()
    yield
    reset_airgap_config()
    reset_airgap_metrics()
    reset_airgap_orchestrator()
    reset_firmware_analyzer()
    reset_edge_runtime()


@pytest.fixture
def test_config():
    """Create test configuration."""
    config = AirGapConfig.for_testing()
    set_airgap_config(config)
    return config


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_component(temp_dir):
    """Create a sample bundle component."""
    # Create a test file
    file_path = os.path.join(temp_dir, "test_component.bin")
    with open(file_path, "wb") as f:
        f.write(b"test content for component")

    return BundleComponent(
        component_id="comp-test-001",
        name="test_component.bin",
        version="1.0.0",
        path=file_path,
        size_bytes=26,
        hash="abc123def456",
        hash_algorithm=HashAlgorithm.SHA256,
        required=True,
        metadata={"type": "test"},
    )


@pytest.fixture
def sample_manifest(sample_component):
    """Create a sample bundle manifest."""
    return BundleManifest(
        manifest_id="manifest-test-001",
        bundle_type=BundleType.FULL,
        version="1.0.0",
        components=[sample_component],
        compression=CompressionType.GZIP,
        total_size_bytes=26,
        metadata={"environment": "test"},
    )


@pytest.fixture
def sample_signature():
    """Create a sample bundle signature."""
    return BundleSignature(
        signature_id="sig-test-001",
        bundle_id="bundle-test-001",
        algorithm=SigningAlgorithm.ED25519,
        signature="dGVzdHNpZ25hdHVyZQ==",
        public_key_id="key-test-001",
        signer_identity="test-signer",
    )


@pytest.fixture
def sample_signed_bundle(sample_manifest, sample_signature):
    """Create a sample signed bundle."""
    return SignedBundle(
        bundle_id="bundle-test-001",
        manifest=sample_manifest,
        signature=sample_signature,
        status=BundleStatus.SIGNED,
    )


@pytest.fixture
def sample_delta_update():
    """Create a sample delta update."""
    return DeltaUpdate(
        delta_id="delta-test-001",
        source_version="1.0.0",
        target_version="1.1.0",
        source_hash="sourcehash123",
        target_hash="targethash456",
        patches=[
            {
                "operation": "add",
                "component": "new_file.bin",
                "hash": "newhash",
                "size_bytes": 100,
            },
            {
                "operation": "modify",
                "component": "existing.bin",
                "source_hash": "old",
                "target_hash": "new",
                "size_bytes": 50,
            },
        ],
        size_bytes=150,
    )


@pytest.fixture
def sample_firmware_image():
    """Create a sample firmware image."""
    return FirmwareImage(
        image_id="fw-test-001",
        name="test_firmware.bin",
        version="1.0.0",
        format=FirmwareFormat.ELF,
        architecture=ProcessorArchitecture.ARM_CORTEX_M,
        size_bytes=65536,
        hash="firmwarehash123",
        rtos_type=RTOSType.FREERTOS,
        metadata={"board": "test-board"},
    )


@pytest.fixture
def sample_memory_issue():
    """Create a sample memory safety issue."""
    return MemorySafetyIssue(
        issue_id="issue-test-001",
        vulnerability_type=VulnerabilityType.BUFFER_OVERFLOW,
        severity=Severity.HIGH,
        location="0x00001000",
        file_path="src/main.c",
        line_number=42,
        description="Buffer overflow in strcpy",
        cwe_id="CWE-120",
        cvss_score=7.5,
        exploitable=True,
        remediation="Use strncpy instead",
    )


@pytest.fixture
def sample_rtos_task():
    """Create a sample RTOS task info."""
    return RTOSTaskInfo(
        task_id="task-test-001",
        name="MainTask",
        priority=5,
        stack_size=4096,
        state="running",
        entry_function="main_task_entry",
        stack_base=0x20000000,
        stack_high_water=1024,
        cpu_usage_percent=25.5,
    )


@pytest.fixture
def sample_analysis_result(
    sample_firmware_image, sample_memory_issue, sample_rtos_task
):
    """Create a sample firmware analysis result."""
    result = FirmwareAnalysisResult(
        analysis_id="analysis-test-001",
        image=sample_firmware_image,
        analysis_type=AnalysisType.STATIC,
        issues=[sample_memory_issue],
        tasks=[sample_rtos_task],
        strings=["FreeRTOS", "version 10.0"],
        rtos_detected=True,
        rtos_version="10.0.0",
        passed=False,
        score=75.0,
    )
    result.completed_at = datetime.now(timezone.utc)
    return result


@pytest.fixture
def sample_quantized_model(temp_dir):
    """Create a sample quantized model."""
    # Create a mock model file
    model_path = os.path.join(temp_dir, "test_model.gguf")
    with open(model_path, "wb") as f:
        f.write(b"GGUF" + os.urandom(1024))  # Mock GGUF header

    return QuantizedModel(
        model_id="model-test-001",
        name="test-llama",
        base_model="llama-2-7b",
        quantization=ModelQuantization.GGUF_Q4_K_M,
        format=ModelFormat.GGUF,
        size_bytes=1024 + 4,
        hash="modelhash123",
        context_length=2048,
        min_ram_mb=256,
        recommended_ram_mb=512,
        file_path=model_path,
    )


@pytest.fixture
def sample_edge_node():
    """Create a sample edge node."""
    return EdgeNode(
        node_id="node-test-001",
        name="test-edge-node",
        mode=EdgeDeploymentMode.DISCONNECTED,
        hardware_id="hw-001",
        architecture=ProcessorArchitecture.ARM64,
        ram_mb=2048,
        storage_mb=16384,
        sync_status=SyncStatus.OFFLINE,
        capabilities=["inference", "graph-query"],
    )


@pytest.fixture
def sample_inference_request():
    """Create a sample inference request."""
    return InferenceRequest(
        request_id="req-test-001",
        node_id="node-test-001",
        model_id="model-test-001",
        prompt="Hello, world!",
        max_tokens=128,
        temperature=0.7,
    )


@pytest.fixture
def sample_graph_query():
    """Create a sample graph query."""
    return GraphQuery(
        query_id="query-test-001",
        query_type="sql",
        query_text="SELECT * FROM vertices WHERE label = ?",
        parameters={"label": "test"},
        timeout_ms=5000,
        max_results=100,
    )


@pytest.fixture
def sample_elf_file(temp_dir):
    """Create a sample ELF file for testing."""
    elf_path = os.path.join(temp_dir, "test.elf")

    # Minimal ELF header for ARM
    elf_header = bytes(
        [
            0x7F,
            0x45,
            0x4C,
            0x46,  # Magic number
            0x01,  # 32-bit
            0x01,  # Little endian
            0x01,  # ELF version
            0x00,  # OS/ABI
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,  # Padding
            0x02,
            0x00,  # Executable
            0x28,
            0x00,  # ARM
        ]
    )

    # Add some test content including RTOS signatures
    content = elf_header + b"\x00" * 44 + b"FreeRTOS xTaskCreate vTaskDelay"

    with open(elf_path, "wb") as f:
        f.write(content)

    return elf_path


@pytest.fixture
def sample_firmware_with_vulns(temp_dir):
    """Create a sample firmware with vulnerability patterns."""
    fw_path = os.path.join(temp_dir, "vuln_firmware.bin")

    # ELF header
    elf_header = bytes(
        [
            0x7F,
            0x45,
            0x4C,
            0x46,
            0x01,
            0x01,
            0x01,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x02,
            0x00,
            0x28,
            0x00,
        ]
    )

    # Content with vulnerable functions
    content = (
        elf_header
        + b"\x00" * 44
        + b"strcpy gets sprintf system "
        + b'password="secret123" '
        + b"MD5 DES_encrypt"
    )

    with open(fw_path, "wb") as f:
        f.write(content)

    return fw_path


@pytest.fixture
def orchestrator(test_config):
    """Create an AirGapOrchestrator instance."""
    return AirGapOrchestrator(test_config)


@pytest.fixture
def analyzer(test_config):
    """Create a FirmwareAnalyzer instance."""
    return FirmwareAnalyzer(test_config)


@pytest.fixture
def runtime(test_config):
    """Create an EdgeRuntime instance."""
    return EdgeRuntime(test_config)
