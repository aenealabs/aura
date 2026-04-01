"""
Project Aura - Air-Gapped and Edge Deployment Configuration

Configuration dataclasses for air-gap orchestration, firmware security analysis,
and tactical edge runtime services.

Based on ADR-078: Air-Gapped and Edge Deployment
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from .contracts import (
    CacheStrategy,
    CompressionType,
    EdgeDeploymentMode,
    HashAlgorithm,
    ModelFormat,
    ModelQuantization,
    SigningAlgorithm,
)


@dataclass
class BundleConfig:
    """Configuration for bundle creation and management."""

    enabled: bool = True
    default_compression: CompressionType = CompressionType.ZSTD
    compression_level: int = 3  # 1-19 for zstd
    default_hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256
    signing_algorithm: SigningAlgorithm = SigningAlgorithm.ED25519
    private_key_path: Optional[str] = None
    public_key_path: Optional[str] = None
    bundle_output_dir: str = "/var/lib/aura/bundles"
    max_bundle_size_mb: int = 4096  # 4GB max
    expiry_days: int = 90
    include_manifests: bool = True
    include_checksums: bool = True
    delta_enabled: bool = True
    delta_algorithm: str = "bsdiff"


@dataclass
class TransferConfig:
    """Configuration for bundle transfer mechanisms."""

    enabled: bool = True
    usb_transfer_enabled: bool = True
    sneakernet_dir: str = "/mnt/transfer"
    verify_on_import: bool = True
    quarantine_dir: str = "/var/lib/aura/quarantine"
    max_concurrent_transfers: int = 4
    transfer_timeout_seconds: int = 3600  # 1 hour
    retry_count: int = 3
    retry_delay_seconds: int = 30


@dataclass
class FirmwareAnalysisConfig:
    """Configuration for firmware security analysis."""

    enabled: bool = True
    binwalk_enabled: bool = True
    ghidra_enabled: bool = False
    ghidra_path: Optional[str] = None
    angr_enabled: bool = False
    max_analysis_time_seconds: int = 3600
    max_file_size_mb: int = 512
    extract_strings: bool = True
    min_string_length: int = 4
    max_strings: int = 10000
    detect_rtos: bool = True
    detect_crypto: bool = True
    memory_safety_checks: bool = True
    output_dir: str = "/var/lib/aura/firmware"
    temp_dir: str = "/tmp/aura-firmware"  # nosec B108 - test default
    allowed_formats: list[str] = field(
        default_factory=lambda: ["elf", "pe", "bin", "ihex", "srec", "uf2"]
    )


@dataclass
class RTOSDetectionConfig:
    """Configuration for RTOS detection and analysis."""

    enabled: bool = True
    detect_freertos: bool = True
    detect_zephyr: bool = True
    detect_threadx: bool = True
    detect_vxworks: bool = True
    detect_riot: bool = True
    detect_nuttx: bool = True
    detect_mbed: bool = True
    analyze_tasks: bool = True
    analyze_ipc: bool = True
    analyze_memory_pools: bool = True
    signature_database_path: Optional[str] = None


@dataclass
class EdgeRuntimeConfig:
    """Configuration for tactical edge runtime."""

    enabled: bool = True
    mode: EdgeDeploymentMode = EdgeDeploymentMode.DISCONNECTED
    node_id: Optional[str] = None
    node_name: Optional[str] = None
    data_dir: str = "/var/lib/aura/edge"
    max_ram_mb: int = 1024  # Max RAM to use
    reserve_ram_mb: int = 256  # RAM to reserve for OS
    gpu_enabled: bool = False
    gpu_layers: int = 0  # Number of layers to offload to GPU


@dataclass
class QuantizedModelConfig:
    """Configuration for quantized model management."""

    enabled: bool = True
    model_dir: str = "/var/lib/aura/models"
    default_quantization: ModelQuantization = ModelQuantization.GGUF_Q4_K_M
    default_format: ModelFormat = ModelFormat.GGUF
    max_context_length: int = 2048
    batch_size: int = 512
    threads: int = 4
    use_mmap: bool = True
    use_mlock: bool = False
    rope_scaling: float = 1.0
    rope_freq_base: float = 10000.0


@dataclass
class LocalGraphConfig:
    """Configuration for local SQLite-based graph database."""

    enabled: bool = True
    database_path: str = "/var/lib/aura/graph/local.db"
    wal_mode: bool = True
    cache_size_mb: int = 64
    page_size: int = 4096
    max_connections: int = 4
    query_timeout_ms: int = 5000
    vacuum_on_close: bool = False
    sync_mode: str = "NORMAL"  # OFF, NORMAL, FULL


@dataclass
class OfflineCacheConfig:
    """Configuration for offline caching."""

    enabled: bool = True
    strategy: CacheStrategy = CacheStrategy.LRU
    max_size_mb: int = 512
    ttl_seconds: int = 86400  # 24 hours
    persist_to_disk: bool = True
    cache_dir: str = "/var/lib/aura/cache"
    max_entries: int = 10000
    eviction_batch_size: int = 100


@dataclass
class SyncConfig:
    """Configuration for synchronization with central server."""

    enabled: bool = True
    sync_interval_seconds: int = 3600  # 1 hour when connected
    max_retry_count: int = 3
    retry_delay_seconds: int = 60
    batch_size: int = 100
    conflict_resolution: str = "server-wins"  # server-wins, client-wins, manual
    compress_sync_data: bool = True
    sync_models: bool = True
    sync_graph_data: bool = True
    sync_cache_data: bool = False
    sync_logs: bool = True


@dataclass
class MetricsConfig:
    """Configuration for CloudWatch metrics (when connected)."""

    enabled: bool = True
    namespace: str = "Aura/AirGap"
    buffer_size: int = 100
    flush_interval_seconds: int = 60
    persist_when_offline: bool = True
    metrics_file: str = "/var/lib/aura/metrics/buffer.json"


@dataclass
class AirGapConfig:
    """Root configuration for all air-gap services."""

    environment: str = "dev"
    enabled: bool = True
    bundle: BundleConfig = field(default_factory=BundleConfig)
    transfer: TransferConfig = field(default_factory=TransferConfig)
    firmware: FirmwareAnalysisConfig = field(default_factory=FirmwareAnalysisConfig)
    rtos: RTOSDetectionConfig = field(default_factory=RTOSDetectionConfig)
    edge_runtime: EdgeRuntimeConfig = field(default_factory=EdgeRuntimeConfig)
    model: QuantizedModelConfig = field(default_factory=QuantizedModelConfig)
    graph: LocalGraphConfig = field(default_factory=LocalGraphConfig)
    cache: OfflineCacheConfig = field(default_factory=OfflineCacheConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    def validate(self) -> list[str]:
        """Validate configuration consistency."""
        errors: list[str] = []

        if self.bundle.compression_level < 1 or self.bundle.compression_level > 19:
            errors.append("bundle.compression_level must be between 1 and 19")

        if self.bundle.max_bundle_size_mb < 1:
            errors.append("bundle.max_bundle_size_mb must be >= 1")

        if self.bundle.expiry_days < 1:
            errors.append("bundle.expiry_days must be >= 1")

        if self.firmware.max_file_size_mb < 1:
            errors.append("firmware.max_file_size_mb must be >= 1")

        if self.firmware.max_analysis_time_seconds < 1:
            errors.append("firmware.max_analysis_time_seconds must be >= 1")

        if self.edge_runtime.max_ram_mb < 256:
            errors.append("edge_runtime.max_ram_mb must be >= 256")

        if self.edge_runtime.reserve_ram_mb >= self.edge_runtime.max_ram_mb:
            errors.append("edge_runtime.reserve_ram_mb must be < max_ram_mb")

        if self.model.max_context_length < 128:
            errors.append("model.max_context_length must be >= 128")

        if self.model.threads < 1:
            errors.append("model.threads must be >= 1")

        if self.graph.cache_size_mb < 1:
            errors.append("graph.cache_size_mb must be >= 1")

        if self.cache.max_size_mb < 1:
            errors.append("cache.max_size_mb must be >= 1")

        return errors

    @classmethod
    def from_environment(cls) -> "AirGapConfig":
        """Load configuration from environment variables."""
        env = os.environ.get("ENVIRONMENT", "dev")

        return cls(
            environment=env,
            enabled=os.environ.get("AIRGAP_ENABLED", "true").lower() == "true",
            bundle=BundleConfig(
                enabled=os.environ.get("AIRGAP_BUNDLE_ENABLED", "true").lower()
                == "true",
                signing_algorithm=SigningAlgorithm(
                    os.environ.get("AIRGAP_SIGNING_ALGORITHM", "ed25519")
                ),
                private_key_path=os.environ.get("AIRGAP_PRIVATE_KEY_PATH"),
                public_key_path=os.environ.get("AIRGAP_PUBLIC_KEY_PATH"),
                bundle_output_dir=os.environ.get(
                    "AIRGAP_BUNDLE_DIR", "/var/lib/aura/bundles"
                ),
                max_bundle_size_mb=int(
                    os.environ.get("AIRGAP_MAX_BUNDLE_SIZE_MB", "4096")
                ),
                expiry_days=int(os.environ.get("AIRGAP_BUNDLE_EXPIRY_DAYS", "90")),
            ),
            transfer=TransferConfig(
                enabled=os.environ.get("AIRGAP_TRANSFER_ENABLED", "true").lower()
                == "true",
                sneakernet_dir=os.environ.get("AIRGAP_SNEAKERNET_DIR", "/mnt/transfer"),
                verify_on_import=os.environ.get(
                    "AIRGAP_VERIFY_ON_IMPORT", "true"
                ).lower()
                == "true",
            ),
            firmware=FirmwareAnalysisConfig(
                enabled=os.environ.get("AIRGAP_FIRMWARE_ENABLED", "true").lower()
                == "true",
                binwalk_enabled=os.environ.get("AIRGAP_BINWALK_ENABLED", "true").lower()
                == "true",
                ghidra_enabled=os.environ.get("AIRGAP_GHIDRA_ENABLED", "false").lower()
                == "true",
                ghidra_path=os.environ.get("GHIDRA_HOME"),
                max_analysis_time_seconds=int(
                    os.environ.get("AIRGAP_MAX_ANALYSIS_TIME", "3600")
                ),
                max_file_size_mb=int(
                    os.environ.get("AIRGAP_MAX_FIRMWARE_SIZE_MB", "512")
                ),
            ),
            rtos=RTOSDetectionConfig(
                enabled=os.environ.get("AIRGAP_RTOS_DETECTION_ENABLED", "true").lower()
                == "true",
            ),
            edge_runtime=EdgeRuntimeConfig(
                enabled=os.environ.get("AIRGAP_EDGE_ENABLED", "true").lower() == "true",
                mode=EdgeDeploymentMode(
                    os.environ.get("AIRGAP_EDGE_MODE", "disconnected")
                ),
                node_id=os.environ.get("AIRGAP_NODE_ID"),
                node_name=os.environ.get("AIRGAP_NODE_NAME"),
                data_dir=os.environ.get("AIRGAP_EDGE_DATA_DIR", "/var/lib/aura/edge"),
                max_ram_mb=int(os.environ.get("AIRGAP_MAX_RAM_MB", "1024")),
                gpu_enabled=os.environ.get("AIRGAP_GPU_ENABLED", "false").lower()
                == "true",
            ),
            model=QuantizedModelConfig(
                enabled=os.environ.get("AIRGAP_MODEL_ENABLED", "true").lower()
                == "true",
                model_dir=os.environ.get("AIRGAP_MODEL_DIR", "/var/lib/aura/models"),
                max_context_length=int(
                    os.environ.get("AIRGAP_MAX_CONTEXT_LENGTH", "2048")
                ),
                threads=int(os.environ.get("AIRGAP_MODEL_THREADS", "4")),
            ),
            graph=LocalGraphConfig(
                enabled=os.environ.get("AIRGAP_GRAPH_ENABLED", "true").lower()
                == "true",
                database_path=os.environ.get(
                    "AIRGAP_GRAPH_DB_PATH", "/var/lib/aura/graph/local.db"
                ),
                cache_size_mb=int(os.environ.get("AIRGAP_GRAPH_CACHE_MB", "64")),
            ),
            cache=OfflineCacheConfig(
                enabled=os.environ.get("AIRGAP_CACHE_ENABLED", "true").lower()
                == "true",
                max_size_mb=int(os.environ.get("AIRGAP_CACHE_SIZE_MB", "512")),
                ttl_seconds=int(os.environ.get("AIRGAP_CACHE_TTL", "86400")),
            ),
            sync=SyncConfig(
                enabled=os.environ.get("AIRGAP_SYNC_ENABLED", "true").lower() == "true",
                sync_interval_seconds=int(
                    os.environ.get("AIRGAP_SYNC_INTERVAL", "3600")
                ),
            ),
            metrics=MetricsConfig(
                enabled=os.environ.get("AIRGAP_METRICS_ENABLED", "true").lower()
                == "true",
                namespace=os.environ.get("AIRGAP_METRICS_NAMESPACE", "Aura/AirGap"),
            ),
        )

    @classmethod
    def for_tactical_edge(cls) -> "AirGapConfig":
        """Create configuration for tactical edge deployment (<2GB RAM)."""
        return cls(
            environment="tactical",
            enabled=True,
            bundle=BundleConfig(
                enabled=True,
                default_compression=CompressionType.LZ4,  # Faster decompression
                compression_level=1,
                max_bundle_size_mb=512,
            ),
            transfer=TransferConfig(
                enabled=True,
                max_concurrent_transfers=1,
            ),
            firmware=FirmwareAnalysisConfig(
                enabled=False,  # Disabled on edge nodes
            ),
            rtos=RTOSDetectionConfig(
                enabled=False,
            ),
            edge_runtime=EdgeRuntimeConfig(
                enabled=True,
                mode=EdgeDeploymentMode.TACTICAL,
                max_ram_mb=1536,  # 1.5GB
                reserve_ram_mb=512,
            ),
            model=QuantizedModelConfig(
                enabled=True,
                default_quantization=ModelQuantization.GGUF_Q4_0,  # Smallest
                max_context_length=1024,  # Reduced context
                threads=2,
                use_mmap=True,
                use_mlock=False,
            ),
            graph=LocalGraphConfig(
                enabled=True,
                cache_size_mb=32,  # Smaller cache
            ),
            cache=OfflineCacheConfig(
                enabled=True,
                max_size_mb=128,  # Smaller cache
                max_entries=1000,
            ),
            sync=SyncConfig(
                enabled=True,
                sync_models=False,  # Models too large for sync
                sync_cache_data=False,
            ),
            metrics=MetricsConfig(
                enabled=True,
                buffer_size=50,  # Smaller buffer
            ),
        )

    @classmethod
    def for_air_gapped(cls) -> "AirGapConfig":
        """Create configuration for fully air-gapped environment."""
        return cls(
            environment="airgapped",
            enabled=True,
            bundle=BundleConfig(
                enabled=True,
                signing_algorithm=SigningAlgorithm.ED25519,
                delta_enabled=True,
            ),
            transfer=TransferConfig(
                enabled=True,
                usb_transfer_enabled=True,
                verify_on_import=True,
            ),
            firmware=FirmwareAnalysisConfig(
                enabled=True,
                binwalk_enabled=True,
                ghidra_enabled=True,
            ),
            rtos=RTOSDetectionConfig(
                enabled=True,
            ),
            edge_runtime=EdgeRuntimeConfig(
                enabled=True,
                mode=EdgeDeploymentMode.DISCONNECTED,
                max_ram_mb=4096,  # More RAM available
            ),
            model=QuantizedModelConfig(
                enabled=True,
                default_quantization=ModelQuantization.GGUF_Q5_K_M,
                max_context_length=4096,
                threads=8,
            ),
            graph=LocalGraphConfig(
                enabled=True,
                cache_size_mb=256,
            ),
            cache=OfflineCacheConfig(
                enabled=True,
                max_size_mb=2048,
            ),
            sync=SyncConfig(
                enabled=False,  # No sync in air-gapped
            ),
            metrics=MetricsConfig(
                enabled=True,
                persist_when_offline=True,
            ),
        )

    @classmethod
    def for_testing(cls) -> "AirGapConfig":
        """Create configuration for unit tests."""
        return cls(
            environment="test",
            enabled=True,
            bundle=BundleConfig(
                enabled=True,
                bundle_output_dir="/tmp/aura-test/bundles",  # nosec B108
                max_bundle_size_mb=100,
                expiry_days=7,
            ),
            transfer=TransferConfig(
                enabled=True,
                sneakernet_dir="/tmp/aura-test/transfer",  # nosec B108
                quarantine_dir="/tmp/aura-test/quarantine",  # nosec B108
            ),
            firmware=FirmwareAnalysisConfig(
                enabled=True,
                binwalk_enabled=False,
                ghidra_enabled=False,
                max_analysis_time_seconds=30,
                max_file_size_mb=10,
                output_dir="/tmp/aura-test/firmware",  # nosec B108
                temp_dir="/tmp/aura-test/firmware-temp",  # nosec B108
            ),
            rtos=RTOSDetectionConfig(
                enabled=True,
            ),
            edge_runtime=EdgeRuntimeConfig(
                enabled=True,
                mode=EdgeDeploymentMode.DISCONNECTED,
                data_dir="/tmp/aura-test/edge",  # nosec B108
                max_ram_mb=512,
            ),
            model=QuantizedModelConfig(
                enabled=True,
                model_dir="/tmp/aura-test/models",  # nosec B108
                max_context_length=512,
                threads=2,
            ),
            graph=LocalGraphConfig(
                enabled=True,
                database_path=":memory:",  # In-memory for tests
                cache_size_mb=16,
            ),
            cache=OfflineCacheConfig(
                enabled=True,
                max_size_mb=32,
                cache_dir="/tmp/aura-test/cache",  # nosec B108
            ),
            sync=SyncConfig(
                enabled=False,
            ),
            metrics=MetricsConfig(
                enabled=False,
            ),
        )


# Singleton instance
_config_instance: Optional[AirGapConfig] = None


def get_airgap_config() -> AirGapConfig:
    """Get singleton configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = AirGapConfig.from_environment()
    return _config_instance


def reset_airgap_config() -> None:
    """Reset configuration singleton (for testing)."""
    global _config_instance
    _config_instance = None


def set_airgap_config(config: AirGapConfig) -> None:
    """Set configuration singleton (for testing)."""
    global _config_instance
    _config_instance = config
