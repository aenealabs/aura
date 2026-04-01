"""
Project Aura - Air-Gapped and Edge Deployment Contracts

Enums and dataclasses for air-gap orchestration, firmware security analysis,
and tactical edge runtime services.

Based on ADR-078: Air-Gapped and Edge Deployment
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Any, Optional

# =============================================================================
# Bundle Management Enums
# =============================================================================


class BundleType(str, Enum):
    """Type of deployment bundle."""

    FULL = "full"
    DELTA = "delta"
    SECURITY_PATCH = "security-patch"
    MODEL_UPDATE = "model-update"
    CONFIG_ONLY = "config-only"


class BundleStatus(str, Enum):
    """Status of a deployment bundle."""

    CREATED = "created"
    SIGNED = "signed"
    VERIFIED = "verified"
    DEPLOYED = "deployed"
    FAILED = "failed"
    EXPIRED = "expired"


class SigningAlgorithm(str, Enum):
    """Cryptographic signing algorithms for bundles."""

    ED25519 = "ed25519"
    ECDSA_P384 = "ecdsa-p384"
    RSA_4096 = "rsa-4096"


class CompressionType(str, Enum):
    """Compression algorithms for bundles."""

    NONE = "none"
    GZIP = "gzip"
    ZSTD = "zstd"
    LZ4 = "lz4"
    XZ = "xz"


class HashAlgorithm(str, Enum):
    """Hash algorithms for integrity verification."""

    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    BLAKE3 = "blake3"


# =============================================================================
# Firmware Analysis Enums
# =============================================================================


class FirmwareFormat(str, Enum):
    """Firmware image formats."""

    ELF = "elf"
    PE = "pe"
    IHEX = "ihex"
    SREC = "srec"
    BIN = "bin"
    UF2 = "uf2"
    UEFI = "uefi"
    UNKNOWN = "unknown"


class RTOSType(str, Enum):
    """Real-Time Operating System types."""

    FREERTOS = "freertos"
    ZEPHYR = "zephyr"
    THREADX = "threadx"
    VXWORKS = "vxworks"
    RIOT = "riot"
    NUTTX = "nuttx"
    MBED = "mbed"
    CONTIKI = "contiki"
    BARE_METAL = "bare-metal"
    LINUX_RT = "linux-rt"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class ProcessorArchitecture(str, Enum):
    """Processor architectures for firmware."""

    ARM_CORTEX_M = "arm-cortex-m"
    ARM_CORTEX_A = "arm-cortex-a"
    ARM_CORTEX_R = "arm-cortex-r"
    ARM64 = "arm64"
    RISCV32 = "riscv32"
    RISCV64 = "riscv64"
    X86 = "x86"
    X86_64 = "x86-64"
    XTENSA = "xtensa"
    MIPS = "mips"
    AVR = "avr"
    UNKNOWN = "unknown"


class VulnerabilityType(str, Enum):
    """Types of firmware vulnerabilities."""

    BUFFER_OVERFLOW = "buffer-overflow"
    STACK_OVERFLOW = "stack-overflow"
    HEAP_OVERFLOW = "heap-overflow"
    INTEGER_OVERFLOW = "integer-overflow"
    INTEGER_UNDERFLOW = "integer-underflow"
    FORMAT_STRING = "format-string"
    USE_AFTER_FREE = "use-after-free"
    DOUBLE_FREE = "double-free"
    NULL_POINTER = "null-pointer"
    RACE_CONDITION = "race-condition"
    MEMORY_LEAK = "memory-leak"
    HARDCODED_CREDENTIALS = "hardcoded-credentials"
    WEAK_CRYPTO = "weak-crypto"
    INSECURE_RANDOM = "insecure-random"
    COMMAND_INJECTION = "command-injection"
    PATH_TRAVERSAL = "path-traversal"
    IMPROPER_INPUT = "improper-input"
    UNINITIALIZED_MEMORY = "uninitialized-memory"
    OUT_OF_BOUNDS_READ = "out-of-bounds-read"
    OUT_OF_BOUNDS_WRITE = "out-of-bounds-write"
    TOCTOU = "time-of-check-to-time-of-use"
    PRIVILEGE_ESCALATION = "privilege-escalation"
    OTHER = "other"


class Severity(IntEnum):
    """Vulnerability severity levels."""

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    def __str__(self) -> str:
        return self.name


class AnalysisType(str, Enum):
    """Types of firmware analysis."""

    STATIC = "static"
    DYNAMIC = "dynamic"
    SYMBOLIC = "symbolic"
    FUZZING = "fuzzing"
    BINARY = "binary"
    SOURCE = "source"


# =============================================================================
# Edge Runtime Enums
# =============================================================================


class EdgeDeploymentMode(str, Enum):
    """Edge deployment connectivity modes."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    TACTICAL = "tactical"
    INTERMITTENT = "intermittent"


class ModelQuantization(str, Enum):
    """Model quantization levels."""

    FP32 = "fp32"
    FP16 = "fp16"
    BF16 = "bf16"
    INT8 = "int8"
    INT4 = "int4"
    GGUF_Q4_0 = "gguf-q4_0"
    GGUF_Q4_K_M = "gguf-q4_k_m"
    GGUF_Q5_K_M = "gguf-q5_k_m"
    GGUF_Q8_0 = "gguf-q8_0"


class ModelFormat(str, Enum):
    """Model file formats."""

    GGUF = "gguf"
    ONNX = "onnx"
    TFLITE = "tflite"
    PYTORCH = "pytorch"
    SAFETENSORS = "safetensors"
    OPENVINO = "openvino"


class SyncStatus(str, Enum):
    """Synchronization status for edge nodes."""

    SYNCED = "synced"
    PENDING = "pending"
    SYNCING = "syncing"
    CONFLICT = "conflict"
    OFFLINE = "offline"
    ERROR = "error"


class CacheStrategy(str, Enum):
    """Caching strategies for offline operation."""

    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL = "ttl"
    PRIORITY = "priority"


# =============================================================================
# Bundle Management Dataclasses
# =============================================================================


@dataclass
class BundleComponent:
    """A component included in a deployment bundle."""

    component_id: str
    name: str
    version: str
    path: str
    size_bytes: int
    hash: str
    hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "component_id": self.component_id,
            "name": self.name,
            "version": self.version,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "hash": self.hash,
            "hash_algorithm": self.hash_algorithm.value,
            "required": self.required,
            "metadata": self.metadata,
        }


@dataclass
class BundleManifest:
    """Manifest describing a deployment bundle."""

    manifest_id: str
    bundle_type: BundleType
    version: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    source_version: Optional[str] = None
    target_version: Optional[str] = None
    components: list[BundleComponent] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    min_edge_version: Optional[str] = None
    max_edge_version: Optional[str] = None
    compression: CompressionType = CompressionType.ZSTD
    total_size_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def component_count(self) -> int:
        """Get number of components."""
        return len(self.components)

    @property
    def is_expired(self) -> bool:
        """Check if bundle has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "manifest_id": self.manifest_id,
            "bundle_type": self.bundle_type.value,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "components": [c.to_dict() for c in self.components],
            "dependencies": self.dependencies,
            "min_edge_version": self.min_edge_version,
            "max_edge_version": self.max_edge_version,
            "compression": self.compression.value,
            "total_size_bytes": self.total_size_bytes,
            "component_count": self.component_count,
            "is_expired": self.is_expired,
            "metadata": self.metadata,
        }


@dataclass
class BundleSignature:
    """Cryptographic signature for a bundle."""

    signature_id: str
    bundle_id: str
    algorithm: SigningAlgorithm
    signature: str  # Base64-encoded signature
    public_key_id: str
    signed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    signer_identity: Optional[str] = None
    certificate_chain: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "signature_id": self.signature_id,
            "bundle_id": self.bundle_id,
            "algorithm": self.algorithm.value,
            "signature": self.signature,
            "public_key_id": self.public_key_id,
            "signed_at": self.signed_at.isoformat(),
            "signer_identity": self.signer_identity,
            "certificate_chain": self.certificate_chain,
        }


@dataclass
class SignedBundle:
    """A signed deployment bundle ready for transfer."""

    bundle_id: str
    manifest: BundleManifest
    signature: BundleSignature
    status: BundleStatus = BundleStatus.SIGNED
    archive_path: Optional[str] = None
    archive_hash: Optional[str] = None
    transferred_at: Optional[datetime] = None
    deployed_at: Optional[datetime] = None
    deployment_nodes: list[str] = field(default_factory=list)

    @property
    def is_verified(self) -> bool:
        """Check if bundle has been verified."""
        return self.status in (BundleStatus.VERIFIED, BundleStatus.DEPLOYED)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "bundle_id": self.bundle_id,
            "manifest": self.manifest.to_dict(),
            "signature": self.signature.to_dict(),
            "status": self.status.value,
            "archive_path": self.archive_path,
            "archive_hash": self.archive_hash,
            "transferred_at": (
                self.transferred_at.isoformat() if self.transferred_at else None
            ),
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "deployment_nodes": self.deployment_nodes,
            "is_verified": self.is_verified,
        }


@dataclass
class DeltaUpdate:
    """Delta update between two bundle versions."""

    delta_id: str
    source_version: str
    target_version: str
    source_hash: str
    target_hash: str
    patches: list[dict[str, Any]] = field(default_factory=list)
    size_bytes: int = 0
    compression: CompressionType = CompressionType.ZSTD
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def patch_count(self) -> int:
        """Get number of patches."""
        return len(self.patches)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "delta_id": self.delta_id,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "source_hash": self.source_hash,
            "target_hash": self.target_hash,
            "patches": self.patches,
            "patch_count": self.patch_count,
            "size_bytes": self.size_bytes,
            "compression": self.compression.value,
            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# Firmware Analysis Dataclasses
# =============================================================================


@dataclass
class FirmwareImage:
    """Firmware image for analysis."""

    image_id: str
    name: str
    version: str
    format: FirmwareFormat
    architecture: ProcessorArchitecture
    size_bytes: int
    hash: str
    hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256
    file_path: Optional[str] = None
    entry_point: Optional[int] = None
    load_address: Optional[int] = None
    rtos_type: RTOSType = RTOSType.UNKNOWN
    build_timestamp: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "image_id": self.image_id,
            "name": self.name,
            "version": self.version,
            "format": self.format.value,
            "architecture": self.architecture.value,
            "size_bytes": self.size_bytes,
            "hash": self.hash,
            "hash_algorithm": self.hash_algorithm.value,
            "file_path": self.file_path,
            "entry_point": self.entry_point,
            "load_address": self.load_address,
            "rtos_type": self.rtos_type.value,
            "build_timestamp": (
                self.build_timestamp.isoformat() if self.build_timestamp else None
            ),
            "metadata": self.metadata,
        }


@dataclass
class MemorySafetyIssue:
    """Memory safety vulnerability found in firmware."""

    issue_id: str
    vulnerability_type: VulnerabilityType
    severity: Severity
    location: str  # Function or address
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    description: str = ""
    cwe_id: Optional[str] = None
    cvss_score: Optional[float] = None
    exploitable: bool = False
    remediation: Optional[str] = None
    stack_trace: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "issue_id": self.issue_id,
            "vulnerability_type": self.vulnerability_type.value,
            "severity": str(self.severity),
            "location": self.location,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "description": self.description,
            "cwe_id": self.cwe_id,
            "cvss_score": self.cvss_score,
            "exploitable": self.exploitable,
            "remediation": self.remediation,
            "stack_trace": self.stack_trace,
        }


@dataclass
class RTOSTaskInfo:
    """Information about an RTOS task."""

    task_id: str
    name: str
    priority: int
    stack_size: int
    state: str = "unknown"
    entry_function: Optional[str] = None
    stack_base: Optional[int] = None
    stack_high_water: Optional[int] = None
    cpu_usage_percent: Optional[float] = None
    runtime_ticks: int = 0

    @property
    def stack_usage_percent(self) -> Optional[float]:
        """Calculate stack usage percentage."""
        if self.stack_size and self.stack_high_water is not None:
            return (1 - self.stack_high_water / self.stack_size) * 100
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "priority": self.priority,
            "stack_size": self.stack_size,
            "state": self.state,
            "entry_function": self.entry_function,
            "stack_base": self.stack_base,
            "stack_high_water": self.stack_high_water,
            "stack_usage_percent": self.stack_usage_percent,
            "cpu_usage_percent": self.cpu_usage_percent,
            "runtime_ticks": self.runtime_ticks,
        }


@dataclass
class FirmwareAnalysisResult:
    """Result of firmware security analysis."""

    analysis_id: str
    image: FirmwareImage
    analysis_type: AnalysisType
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    issues: list[MemorySafetyIssue] = field(default_factory=list)
    tasks: list[RTOSTaskInfo] = field(default_factory=list)
    symbols: dict[str, int] = field(default_factory=dict)
    strings: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    rtos_detected: bool = False
    rtos_version: Optional[str] = None
    compiler_info: Optional[str] = None
    debug_info_present: bool = False
    passed: bool = True
    score: float = 100.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        """Count critical issues."""
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        """Count high severity issues."""
        return sum(1 for i in self.issues if i.severity == Severity.HIGH)

    @property
    def medium_count(self) -> int:
        """Count medium severity issues."""
        return sum(1 for i in self.issues if i.severity == Severity.MEDIUM)

    @property
    def issue_count(self) -> int:
        """Total issue count."""
        return len(self.issues)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get analysis duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "analysis_id": self.analysis_id,
            "image": self.image.to_dict(),
            "analysis_type": self.analysis_type.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_seconds": self.duration_seconds,
            "issues": [i.to_dict() for i in self.issues],
            "issue_count": self.issue_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "tasks": [t.to_dict() for t in self.tasks],
            "symbol_count": len(self.symbols),
            "string_count": len(self.strings),
            "import_count": len(self.imports),
            "export_count": len(self.exports),
            "section_count": len(self.sections),
            "rtos_detected": self.rtos_detected,
            "rtos_version": self.rtos_version,
            "compiler_info": self.compiler_info,
            "debug_info_present": self.debug_info_present,
            "passed": self.passed,
            "score": self.score,
            "metadata": self.metadata,
        }


# =============================================================================
# Edge Runtime Dataclasses
# =============================================================================


@dataclass
class QuantizedModel:
    """A quantized LLM model for edge deployment."""

    model_id: str
    name: str
    base_model: str
    quantization: ModelQuantization
    format: ModelFormat
    size_bytes: int
    hash: str
    hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256
    context_length: int = 2048
    vocab_size: int = 32000
    embedding_dim: int = 4096
    num_layers: int = 32
    num_heads: int = 32
    min_ram_mb: int = 512
    recommended_ram_mb: int = 1024
    supports_gpu: bool = False
    file_path: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def size_mb(self) -> float:
        """Get size in megabytes."""
        return self.size_bytes / (1024 * 1024)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "model_id": self.model_id,
            "name": self.name,
            "base_model": self.base_model,
            "quantization": self.quantization.value,
            "format": self.format.value,
            "size_bytes": self.size_bytes,
            "size_mb": self.size_mb,
            "hash": self.hash,
            "hash_algorithm": self.hash_algorithm.value,
            "context_length": self.context_length,
            "vocab_size": self.vocab_size,
            "embedding_dim": self.embedding_dim,
            "num_layers": self.num_layers,
            "num_heads": self.num_heads,
            "min_ram_mb": self.min_ram_mb,
            "recommended_ram_mb": self.recommended_ram_mb,
            "supports_gpu": self.supports_gpu,
            "file_path": self.file_path,
            "metadata": self.metadata,
        }


@dataclass
class EdgeNode:
    """An edge deployment node."""

    node_id: str
    name: str
    mode: EdgeDeploymentMode
    hardware_id: str
    architecture: ProcessorArchitecture
    ram_mb: int
    storage_mb: int
    last_seen: Optional[datetime] = None
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    current_version: Optional[str] = None
    installed_models: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    sync_status: SyncStatus = SyncStatus.OFFLINE
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_online(self) -> bool:
        """Check if node is online."""
        return self.sync_status not in (SyncStatus.OFFLINE, SyncStatus.ERROR)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "mode": self.mode.value,
            "hardware_id": self.hardware_id,
            "architecture": self.architecture.value,
            "ram_mb": self.ram_mb,
            "storage_mb": self.storage_mb,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "registered_at": self.registered_at.isoformat(),
            "current_version": self.current_version,
            "installed_models": self.installed_models,
            "capabilities": self.capabilities,
            "sync_status": self.sync_status.value,
            "is_online": self.is_online,
            "metadata": self.metadata,
        }


@dataclass
class OfflineCache:
    """Cache for offline operation."""

    cache_id: str
    node_id: str
    strategy: CacheStrategy
    max_size_mb: int
    current_size_mb: float = 0.0
    entry_count: int = 0
    hit_count: int = 0
    miss_count: int = 0
    eviction_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: Optional[datetime] = None

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0

    @property
    def usage_percent(self) -> float:
        """Calculate cache usage percentage."""
        return (
            (self.current_size_mb / self.max_size_mb) * 100
            if self.max_size_mb > 0
            else 0.0
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "cache_id": self.cache_id,
            "node_id": self.node_id,
            "strategy": self.strategy.value,
            "max_size_mb": self.max_size_mb,
            "current_size_mb": self.current_size_mb,
            "usage_percent": self.usage_percent,
            "entry_count": self.entry_count,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "eviction_count": self.eviction_count,
            "hit_rate": self.hit_rate,
            "created_at": self.created_at.isoformat(),
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed else None
            ),
        }


@dataclass
class SyncState:
    """Synchronization state for an edge node."""

    state_id: str
    node_id: str
    status: SyncStatus
    last_sync: Optional[datetime] = None
    next_sync: Optional[datetime] = None
    pending_changes: int = 0
    synced_version: Optional[str] = None
    target_version: Optional[str] = None
    bytes_transferred: int = 0
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    @property
    def needs_retry(self) -> bool:
        """Check if sync needs retry."""
        return self.status == SyncStatus.ERROR and self.retry_count < self.max_retries

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "state_id": self.state_id,
            "node_id": self.node_id,
            "status": self.status.value,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "next_sync": self.next_sync.isoformat() if self.next_sync else None,
            "pending_changes": self.pending_changes,
            "synced_version": self.synced_version,
            "target_version": self.target_version,
            "bytes_transferred": self.bytes_transferred,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "needs_retry": self.needs_retry,
        }


@dataclass
class InferenceRequest:
    """Request for edge inference."""

    request_id: str
    node_id: str
    model_id: str
    prompt: str
    max_tokens: int = 256
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: int = 0
    timeout_seconds: int = 60
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "request_id": self.request_id,
            "node_id": self.node_id,
            "model_id": self.model_id,
            "prompt": self.prompt,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "created_at": self.created_at.isoformat(),
            "priority": self.priority,
            "timeout_seconds": self.timeout_seconds,
            "metadata": self.metadata,
        }


@dataclass
class InferenceResponse:
    """Response from edge inference."""

    response_id: str
    request_id: str
    node_id: str
    model_id: str
    text: str
    tokens_generated: int = 0
    prompt_tokens: int = 0
    generation_time_ms: float = 0.0
    cached: bool = False
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None

    @property
    def tokens_per_second(self) -> float:
        """Calculate tokens per second."""
        if self.generation_time_ms > 0:
            return (self.tokens_generated / self.generation_time_ms) * 1000
        return 0.0

    @property
    def success(self) -> bool:
        """Check if inference succeeded."""
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "response_id": self.response_id,
            "request_id": self.request_id,
            "node_id": self.node_id,
            "model_id": self.model_id,
            "text": self.text,
            "tokens_generated": self.tokens_generated,
            "prompt_tokens": self.prompt_tokens,
            "generation_time_ms": self.generation_time_ms,
            "tokens_per_second": self.tokens_per_second,
            "cached": self.cached,
            "completed_at": self.completed_at.isoformat(),
            "error": self.error,
            "success": self.success,
        }


@dataclass
class GraphQuery:
    """Query for the local graph database."""

    query_id: str
    query_type: str  # e.g., "gremlin", "cypher", "sparql"
    query_text: str
    parameters: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 5000
    max_results: int = 100
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "query_id": self.query_id,
            "query_type": self.query_type,
            "query_text": self.query_text,
            "parameters": self.parameters,
            "timeout_ms": self.timeout_ms,
            "max_results": self.max_results,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class GraphQueryResult:
    """Result of a local graph query."""

    result_id: str
    query_id: str
    results: list[dict[str, Any]] = field(default_factory=list)
    result_count: int = 0
    execution_time_ms: float = 0.0
    truncated: bool = False
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if query succeeded."""
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "result_id": self.result_id,
            "query_id": self.query_id,
            "results": self.results,
            "result_count": self.result_count,
            "execution_time_ms": self.execution_time_ms,
            "truncated": self.truncated,
            "completed_at": self.completed_at.isoformat(),
            "error": self.error,
            "success": self.success,
        }
