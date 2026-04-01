"""
Tests for air-gap service configuration.
"""

import os

from src.services.airgap import (
    AirGapConfig,
    BundleConfig,
    CacheStrategy,
    CompressionType,
    EdgeDeploymentMode,
    EdgeRuntimeConfig,
    FirmwareAnalysisConfig,
    LocalGraphConfig,
    MetricsConfig,
    ModelFormat,
    ModelQuantization,
    OfflineCacheConfig,
    QuantizedModelConfig,
    RTOSDetectionConfig,
    SigningAlgorithm,
    SyncConfig,
    TransferConfig,
    get_airgap_config,
    reset_airgap_config,
    set_airgap_config,
)


class TestBundleConfig:
    """Tests for BundleConfig."""

    def test_defaults(self):
        """Test default values."""
        config = BundleConfig()
        assert config.enabled is True
        assert config.default_compression == CompressionType.ZSTD
        assert config.signing_algorithm == SigningAlgorithm.ED25519
        assert config.max_bundle_size_mb == 4096
        assert config.delta_enabled is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = BundleConfig(
            enabled=False,
            default_compression=CompressionType.LZ4,
            compression_level=9,
            max_bundle_size_mb=1024,
        )
        assert config.enabled is False
        assert config.default_compression == CompressionType.LZ4
        assert config.compression_level == 9


class TestTransferConfig:
    """Tests for TransferConfig."""

    def test_defaults(self):
        """Test default values."""
        config = TransferConfig()
        assert config.enabled is True
        assert config.usb_transfer_enabled is True
        assert config.verify_on_import is True
        assert config.max_concurrent_transfers == 4

    def test_custom_values(self):
        """Test custom configuration values."""
        config = TransferConfig(
            enabled=True,
            sneakernet_dir="/custom/transfer",
            retry_count=5,
        )
        assert config.sneakernet_dir == "/custom/transfer"
        assert config.retry_count == 5


class TestFirmwareAnalysisConfig:
    """Tests for FirmwareAnalysisConfig."""

    def test_defaults(self):
        """Test default values."""
        config = FirmwareAnalysisConfig()
        assert config.enabled is True
        assert config.binwalk_enabled is True
        assert config.ghidra_enabled is False
        assert config.max_file_size_mb == 512
        assert config.detect_rtos is True

    def test_allowed_formats(self):
        """Test default allowed formats."""
        config = FirmwareAnalysisConfig()
        assert "elf" in config.allowed_formats
        assert "bin" in config.allowed_formats
        assert "ihex" in config.allowed_formats


class TestRTOSDetectionConfig:
    """Tests for RTOSDetectionConfig."""

    def test_defaults(self):
        """Test default values."""
        config = RTOSDetectionConfig()
        assert config.enabled is True
        assert config.detect_freertos is True
        assert config.detect_zephyr is True
        assert config.analyze_tasks is True


class TestEdgeRuntimeConfig:
    """Tests for EdgeRuntimeConfig."""

    def test_defaults(self):
        """Test default values."""
        config = EdgeRuntimeConfig()
        assert config.enabled is True
        assert config.mode == EdgeDeploymentMode.DISCONNECTED
        assert config.max_ram_mb == 1024
        assert config.gpu_enabled is False

    def test_custom_values(self):
        """Test custom configuration values."""
        config = EdgeRuntimeConfig(
            mode=EdgeDeploymentMode.TACTICAL,
            max_ram_mb=2048,
            gpu_enabled=True,
            gpu_layers=10,
        )
        assert config.mode == EdgeDeploymentMode.TACTICAL
        assert config.max_ram_mb == 2048
        assert config.gpu_layers == 10


class TestQuantizedModelConfig:
    """Tests for QuantizedModelConfig."""

    def test_defaults(self):
        """Test default values."""
        config = QuantizedModelConfig()
        assert config.enabled is True
        assert config.default_quantization == ModelQuantization.GGUF_Q4_K_M
        assert config.default_format == ModelFormat.GGUF
        assert config.max_context_length == 2048
        assert config.threads == 4

    def test_custom_values(self):
        """Test custom configuration values."""
        config = QuantizedModelConfig(
            default_quantization=ModelQuantization.INT8,
            max_context_length=4096,
            threads=8,
        )
        assert config.default_quantization == ModelQuantization.INT8
        assert config.max_context_length == 4096


class TestLocalGraphConfig:
    """Tests for LocalGraphConfig."""

    def test_defaults(self):
        """Test default values."""
        config = LocalGraphConfig()
        assert config.enabled is True
        assert config.wal_mode is True
        assert config.cache_size_mb == 64
        assert config.query_timeout_ms == 5000

    def test_custom_values(self):
        """Test custom configuration values."""
        config = LocalGraphConfig(
            database_path=":memory:",
            cache_size_mb=128,
        )
        assert config.database_path == ":memory:"
        assert config.cache_size_mb == 128


class TestOfflineCacheConfig:
    """Tests for OfflineCacheConfig."""

    def test_defaults(self):
        """Test default values."""
        config = OfflineCacheConfig()
        assert config.enabled is True
        assert config.strategy == CacheStrategy.LRU
        assert config.max_size_mb == 512
        assert config.ttl_seconds == 86400  # 24 hours

    def test_custom_values(self):
        """Test custom configuration values."""
        config = OfflineCacheConfig(
            strategy=CacheStrategy.LFU,
            max_size_mb=1024,
            max_entries=50000,
        )
        assert config.strategy == CacheStrategy.LFU
        assert config.max_entries == 50000


class TestSyncConfig:
    """Tests for SyncConfig."""

    def test_defaults(self):
        """Test default values."""
        config = SyncConfig()
        assert config.enabled is True
        assert config.sync_interval_seconds == 3600
        assert config.conflict_resolution == "server-wins"

    def test_custom_values(self):
        """Test custom configuration values."""
        config = SyncConfig(
            enabled=False,
            sync_models=False,
        )
        assert config.enabled is False
        assert config.sync_models is False


class TestMetricsConfig:
    """Tests for MetricsConfig."""

    def test_defaults(self):
        """Test default values."""
        config = MetricsConfig()
        assert config.enabled is True
        assert config.namespace == "Aura/AirGap"
        assert config.buffer_size == 100
        assert config.persist_when_offline is True


class TestAirGapConfig:
    """Tests for AirGapConfig root configuration."""

    def test_defaults(self):
        """Test default values."""
        config = AirGapConfig()
        assert config.environment == "dev"
        assert config.enabled is True
        assert config.bundle.enabled is True
        assert config.firmware.enabled is True
        assert config.edge_runtime.enabled is True

    def test_validate_success(self):
        """Test validation with valid config."""
        config = AirGapConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_validate_invalid_compression_level(self):
        """Test validation with invalid compression level."""
        config = AirGapConfig(
            bundle=BundleConfig(compression_level=25),
        )
        errors = config.validate()
        assert any("compression_level" in e for e in errors)

    def test_validate_invalid_ram(self):
        """Test validation with invalid RAM settings."""
        config = AirGapConfig(
            edge_runtime=EdgeRuntimeConfig(max_ram_mb=100),
        )
        errors = config.validate()
        assert any("max_ram_mb" in e for e in errors)

    def test_validate_ram_reserve_too_large(self):
        """Test validation when reserve RAM >= max RAM."""
        config = AirGapConfig(
            edge_runtime=EdgeRuntimeConfig(
                max_ram_mb=1024,
                reserve_ram_mb=1024,
            ),
        )
        errors = config.validate()
        assert any("reserve_ram_mb" in e for e in errors)

    def test_for_tactical_edge(self):
        """Test configuration for tactical edge deployment."""
        config = AirGapConfig.for_tactical_edge()
        assert config.environment == "tactical"
        assert config.edge_runtime.mode == EdgeDeploymentMode.TACTICAL
        assert config.bundle.default_compression == CompressionType.LZ4
        assert config.firmware.enabled is False
        assert config.model.default_quantization == ModelQuantization.GGUF_Q4_0
        assert config.sync.sync_models is False

    def test_for_air_gapped(self):
        """Test configuration for air-gapped environment."""
        config = AirGapConfig.for_air_gapped()
        assert config.environment == "airgapped"
        assert config.edge_runtime.mode == EdgeDeploymentMode.DISCONNECTED
        assert config.bundle.delta_enabled is True
        assert config.firmware.ghidra_enabled is True
        assert config.sync.enabled is False

    def test_for_testing(self):
        """Test configuration for unit tests."""
        config = AirGapConfig.for_testing()
        assert config.environment == "test"
        assert config.graph.database_path == ":memory:"
        assert config.sync.enabled is False
        assert config.metrics.enabled is False


class TestConfigSingleton:
    """Tests for configuration singleton management."""

    def test_get_singleton(self, test_config):
        """Test getting singleton returns same instance."""
        config1 = get_airgap_config()
        config2 = get_airgap_config()
        assert config1 is config2

    def test_reset_singleton(self, test_config):
        """Test resetting singleton creates new instance."""
        config1 = get_airgap_config()
        reset_airgap_config()
        # After reset, need to set config again for test
        set_airgap_config(AirGapConfig.for_testing())
        config2 = get_airgap_config()
        assert config1 is not config2

    def test_set_singleton(self):
        """Test setting custom singleton."""
        custom_config = AirGapConfig(environment="custom")
        set_airgap_config(custom_config)
        retrieved = get_airgap_config()
        assert retrieved.environment == "custom"


class TestConfigFromEnvironment:
    """Tests for loading configuration from environment."""

    def test_from_environment_defaults(self, monkeypatch):
        """Test loading from environment with defaults."""
        # Clear all AIRGAP_ env vars
        for key in list(os.environ.keys()):
            if key.startswith("AIRGAP_"):
                monkeypatch.delenv(key, raising=False)
        # Clear ENVIRONMENT so from_environment() falls back to default "dev"
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        reset_airgap_config()
        config = AirGapConfig.from_environment()
        assert config.environment == "dev"
        assert config.enabled is True

    def test_from_environment_custom(self, monkeypatch):
        """Test loading from environment with custom values."""
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.setenv("AIRGAP_ENABLED", "false")
        monkeypatch.setenv("AIRGAP_MAX_RAM_MB", "2048")
        monkeypatch.setenv("AIRGAP_EDGE_MODE", "tactical")

        reset_airgap_config()
        config = AirGapConfig.from_environment()
        assert config.environment == "staging"
        assert config.enabled is False
        assert config.edge_runtime.max_ram_mb == 2048
        assert config.edge_runtime.mode == EdgeDeploymentMode.TACTICAL

    def test_from_environment_signing_algorithm(self, monkeypatch):
        """Test loading signing algorithm from environment."""
        monkeypatch.setenv("AIRGAP_SIGNING_ALGORITHM", "ecdsa-p384")

        reset_airgap_config()
        config = AirGapConfig.from_environment()
        assert config.bundle.signing_algorithm == SigningAlgorithm.ECDSA_P384
