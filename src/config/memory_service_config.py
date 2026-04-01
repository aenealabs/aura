"""
Neural Memory Service Configuration Management

Provides environment-specific configuration for Titan/MIRAS neural memory service
with support for YAML configuration files and environment variable overrides.

Configuration loading priority (highest to lowest):
1. Environment variables (prefixed with MEMORY_SERVICE_)
2. YAML config files (deploy/config/memory-service/{environment}.yaml)
3. Default values defined in this module

Related files:
- deploy/config/memory-service/development.yaml
- deploy/config/memory-service/staging.yaml
- deploy/config/memory-service/production.yaml
- deploy/kubernetes/memory-service/configmap.yaml
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml


class Environment(Enum):
    """Environment types for configuration."""

    DEV = "development"
    STAGING = "staging"
    PROD = "production"


@dataclass
class TTTConfig:
    """Test-time training configuration (Titans paper)."""

    enabled: bool = True
    learning_rate: float = 0.001
    momentum: float = 0.9
    steps_per_update: int = 1


@dataclass
class SurpriseConfig:
    """Surprise-driven memorization configuration."""

    enabled: bool = True
    threshold: float = 0.5
    decay_factor: float = 0.99


@dataclass
class MemoryArchitectureConfig:
    """Neural memory architecture configuration."""

    dimension: int = 1024
    layers: int = 3
    heads: int = 8
    max_sequence_length: int = 8192


@dataclass
class MemoryConfig:
    """Complete memory configuration."""

    type: str = "titans"
    architecture: MemoryArchitectureConfig = field(
        default_factory=MemoryArchitectureConfig
    )
    ttt: TTTConfig = field(default_factory=TTTConfig)
    surprise: SurpriseConfig = field(default_factory=SurpriseConfig)


@dataclass
class S3StorageConfig:
    """S3 storage configuration for model checkpoints."""

    bucket: str = "aura-models-dev"
    prefix: str = "neural-memory/checkpoints"
    checkpoint_interval_seconds: int = 3600


@dataclass
class LocalStorageConfig:
    """Local storage configuration."""

    model_cache_dir: str = "/var/lib/memory-service/models"
    state_dir: str = "/var/lib/memory-service/state"


@dataclass
class StorageConfig:
    """Complete storage configuration."""

    s3: S3StorageConfig = field(default_factory=S3StorageConfig)
    local: LocalStorageConfig = field(default_factory=LocalStorageConfig)


@dataclass
class DynamoDBConfig:
    """DynamoDB persistence configuration."""

    table_name: str = "aura-neural-memory-dev"
    sync_interval_seconds: int = 300
    ttl_days: int = 90


@dataclass
class GRPCConfig:
    """gRPC server configuration."""

    max_message_size_bytes: int = 104857600  # 100MB
    keepalive_time_ms: int = 30000
    keepalive_timeout_ms: int = 10000
    max_concurrent_streams: int = 100


@dataclass
class PerformanceConfig:
    """Performance tuning configuration."""

    max_batch_size: int = 32
    batch_timeout_ms: int = 100
    gpu_memory_fraction: float = 0.8
    enable_memory_pool: bool = True
    grpc: GRPCConfig = field(default_factory=GRPCConfig)


@dataclass
class MetricsConfig:
    """CloudWatch metrics configuration."""

    namespace: str = "Aura/NeuralMemory"
    publish_interval_seconds: int = 60


@dataclass
class TracingConfig:
    """Distributed tracing configuration."""

    enabled: bool = True
    sample_rate: float = 1.0
    exporter: str = "otlp"
    endpoint: str = "http://otel-collector:4317"


@dataclass
class ObservabilityConfig:
    """Complete observability configuration."""

    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    tracing: TracingConfig = field(default_factory=TracingConfig)


@dataclass
class ServerConfig:
    """Server ports and settings."""

    grpc_port: int = 50051
    health_port: int = 8080
    metrics_port: int = 9090
    log_level: str = "INFO"
    worker_threads: int = 4


@dataclass
class AWSConfig:
    """AWS configuration."""

    region: str = "us-east-1"
    account_id: str = ""


@dataclass
class FeatureFlagsConfig:
    """Feature flags for gradual rollout."""

    async_memorization: bool = True
    adaptive_learning_rate: bool = False
    memory_compression: bool = False
    distributed_memory: bool = False


@dataclass
class MemoryServiceConfig:
    """Complete memory service configuration."""

    environment: Environment = Environment.DEV
    server: ServerConfig = field(default_factory=ServerConfig)
    aws: AWSConfig = field(default_factory=AWSConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    persistence: DynamoDBConfig = field(default_factory=DynamoDBConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    features: FeatureFlagsConfig = field(default_factory=FeatureFlagsConfig)


def get_environment() -> Environment:
    """
    Get current environment from ENVIRONMENT or AURA_ENV environment variable.
    Defaults to development if not set.

    Returns:
        Environment enum value
    """
    env_str = os.environ.get(
        "ENVIRONMENT", os.environ.get("AURA_ENV", "development")
    ).lower()

    env_map = {
        "development": Environment.DEV,
        "dev": Environment.DEV,
        "staging": Environment.STAGING,
        "stage": Environment.STAGING,
        "production": Environment.PROD,
        "prod": Environment.PROD,
    }

    return env_map.get(env_str, Environment.DEV)


def find_config_file(environment: Environment) -> Optional[Path]:
    """
    Find configuration file for the given environment.

    Searches in order:
    1. deploy/config/memory-service/{environment}.yaml
    2. /etc/aura/memory-service/{environment}.yaml (for container deployments)

    Returns:
        Path to config file if found, None otherwise
    """
    env_name = environment.value

    search_paths = [
        Path(__file__).parent.parent.parent
        / "deploy"
        / "config"
        / "memory-service"
        / f"{env_name}.yaml",
        Path(f"/etc/aura/memory-service/{env_name}.yaml"),
    ]

    for path in search_paths:
        if path.exists():
            return path

    return None


def load_yaml_config(path: Path) -> dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        path: Path to YAML configuration file

    Returns:
        Configuration dictionary
    """
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """
    Apply environment variable overrides to configuration.

    Environment variables prefixed with MEMORY_SERVICE_ override config values.
    Uses double underscore for nested keys.

    Example:
        MEMORY_SERVICE_SERVER__LOG_LEVEL=DEBUG
        MEMORY_SERVICE_MEMORY__TTT__LEARNING_RATE=0.0001

    Args:
        config: Base configuration dictionary

    Returns:
        Configuration with environment overrides applied
    """
    prefix = "MEMORY_SERVICE_"

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue

        # Remove prefix and split by double underscore
        config_key = key[len(prefix) :].lower()
        parts = config_key.split("__")

        # Navigate to nested location
        current = config
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set value with type conversion
        final_key = parts[-1]
        current[final_key] = _convert_env_value(value)

    return config


def _convert_env_value(value: str) -> Any:
    """Convert environment variable string to appropriate type."""
    # Boolean
    if value.lower() in ("true", "false"):
        return value.lower() == "true"

    # Integer
    try:
        return int(value)
    except ValueError:
        pass

    # Float
    try:
        return float(value)
    except ValueError:
        pass

    # String (default)
    return value


def _dict_to_dataclass(data: dict[str, Any], cls: type) -> Any:
    """
    Convert dictionary to dataclass instance, handling nested dataclasses.

    Args:
        data: Dictionary of configuration values
        cls: Dataclass type to instantiate

    Returns:
        Dataclass instance
    """
    if not data:
        return cls()

    # Get field types for nested conversion
    field_types = {}
    if hasattr(cls, "__dataclass_fields__"):
        for field_name, field_info in cls.__dataclass_fields__.items():
            field_types[field_name] = field_info.type

    kwargs = {}
    for key, value in data.items():
        if key not in field_types:
            continue

        field_type = field_types[key]

        # Handle nested dataclasses
        if isinstance(value, dict) and hasattr(field_type, "__dataclass_fields__"):
            kwargs[key] = _dict_to_dataclass(value, field_type)
        else:
            kwargs[key] = value

    return cls(**kwargs)


def get_config() -> MemoryServiceConfig:
    """
    Get complete memory service configuration.

    Loads configuration from:
    1. Default values
    2. YAML config file (if found)
    3. Environment variable overrides

    Returns:
        MemoryServiceConfig dataclass instance
    """
    environment = get_environment()

    # Start with empty config
    config_dict: dict[str, Any] = {}

    # Load from YAML if available
    config_path = find_config_file(environment)
    if config_path:
        config_dict = load_yaml_config(config_path)

    # Apply environment variable overrides
    config_dict = apply_env_overrides(config_dict)

    # Convert to dataclass
    config = MemoryServiceConfig(
        environment=environment,
        server=_dict_to_dataclass(config_dict.get("server", {}), ServerConfig),
        aws=_dict_to_dataclass(config_dict.get("aws", {}), AWSConfig),
        memory=MemoryConfig(
            type=config_dict.get("memory", {}).get("type", "titans"),
            architecture=_dict_to_dataclass(
                config_dict.get("memory", {}).get("architecture", {}),
                MemoryArchitectureConfig,
            ),
            ttt=_dict_to_dataclass(
                config_dict.get("memory", {}).get("ttt", {}), TTTConfig
            ),
            surprise=_dict_to_dataclass(
                config_dict.get("memory", {}).get("surprise", {}), SurpriseConfig
            ),
        ),
        storage=StorageConfig(
            s3=_dict_to_dataclass(
                config_dict.get("storage", {}).get("s3", {}), S3StorageConfig
            ),
            local=_dict_to_dataclass(
                config_dict.get("storage", {}).get("local", {}), LocalStorageConfig
            ),
        ),
        persistence=_dict_to_dataclass(
            config_dict.get("persistence", {}).get("dynamodb", {}), DynamoDBConfig
        ),
        performance=PerformanceConfig(
            max_batch_size=config_dict.get("performance", {}).get("max_batch_size", 32),
            batch_timeout_ms=config_dict.get("performance", {}).get(
                "batch_timeout_ms", 100
            ),
            gpu_memory_fraction=config_dict.get("performance", {}).get(
                "gpu_memory_fraction", 0.8
            ),
            enable_memory_pool=config_dict.get("performance", {}).get(
                "enable_memory_pool", True
            ),
            grpc=_dict_to_dataclass(
                config_dict.get("performance", {}).get("grpc", {}), GRPCConfig
            ),
        ),
        observability=ObservabilityConfig(
            metrics=_dict_to_dataclass(
                config_dict.get("observability", {}).get("metrics", {}), MetricsConfig
            ),
            tracing=_dict_to_dataclass(
                config_dict.get("observability", {}).get("tracing", {}), TracingConfig
            ),
        ),
        features=_dict_to_dataclass(
            config_dict.get("features", {}), FeatureFlagsConfig
        ),
    )

    return config


def validate_config(config: MemoryServiceConfig) -> bool:
    """
    Validate configuration has all required fields and valid values.

    Args:
        config: MemoryServiceConfig instance to validate

    Returns:
        True if valid

    Raises:
        ValueError: If configuration is invalid
    """
    # Validate server ports
    if not (1024 <= config.server.grpc_port <= 65535):
        raise ValueError(f"Invalid gRPC port: {config.server.grpc_port}")

    if not (1024 <= config.server.health_port <= 65535):
        raise ValueError(f"Invalid health port: {config.server.health_port}")

    # Validate memory architecture
    if config.memory.architecture.dimension <= 0:
        raise ValueError("Memory dimension must be positive")

    if config.memory.architecture.layers <= 0:
        raise ValueError("Memory layers must be positive")

    if config.memory.architecture.heads <= 0:
        raise ValueError("Memory heads must be positive")

    # Validate TTT parameters
    if config.memory.ttt.enabled:
        if not (0 < config.memory.ttt.learning_rate < 1):
            raise ValueError("TTT learning rate must be between 0 and 1")

        if not (0 <= config.memory.ttt.momentum <= 1):
            raise ValueError("TTT momentum must be between 0 and 1")

    # Validate surprise parameters
    if config.memory.surprise.enabled:
        if not (0 <= config.memory.surprise.threshold <= 1):
            raise ValueError("Surprise threshold must be between 0 and 1")

        if not (0 < config.memory.surprise.decay_factor <= 1):
            raise ValueError("Surprise decay factor must be between 0 and 1")

    # Validate performance settings
    if config.performance.max_batch_size <= 0:
        raise ValueError("Max batch size must be positive")

    if not (0 < config.performance.gpu_memory_fraction <= 1):
        raise ValueError("GPU memory fraction must be between 0 and 1")

    return True


# Singleton config instance
_config: Optional[MemoryServiceConfig] = None


def get_cached_config() -> MemoryServiceConfig:
    """
    Get cached configuration instance.

    Returns cached config if available, otherwise loads and caches.

    Returns:
        MemoryServiceConfig instance
    """
    global _config
    if _config is None:
        _config = get_config()
        validate_config(_config)
    return _config


def reload_config() -> MemoryServiceConfig:
    """
    Force reload of configuration.

    Useful for testing or when config files change.

    Returns:
        Fresh MemoryServiceConfig instance
    """
    global _config
    _config = get_config()
    validate_config(_config)
    return _config


if __name__ == "__main__":
    # Demo usage
    print("Project Aura - Neural Memory Service Configuration")
    print("=" * 60)

    config = get_cached_config()

    print(f"\nEnvironment: {config.environment.value}")
    print("\nServer Configuration:")
    print(f"  gRPC Port: {config.server.grpc_port}")
    print(f"  Health Port: {config.server.health_port}")
    print(f"  Log Level: {config.server.log_level}")

    print(f"\nMemory Architecture ({config.memory.type}):")
    print(f"  Dimension: {config.memory.architecture.dimension}")
    print(f"  Layers: {config.memory.architecture.layers}")
    print(f"  Heads: {config.memory.architecture.heads}")
    print(f"  Max Sequence Length: {config.memory.architecture.max_sequence_length}")

    print("\nTest-Time Training:")
    print(f"  Enabled: {config.memory.ttt.enabled}")
    print(f"  Learning Rate: {config.memory.ttt.learning_rate}")

    print("\nSurprise-Driven Memorization:")
    print(f"  Enabled: {config.memory.surprise.enabled}")
    print(f"  Threshold: {config.memory.surprise.threshold}")

    print("\nStorage:")
    print(f"  S3 Bucket: {config.storage.s3.bucket}")
    print(f"  DynamoDB Table: {config.persistence.table_name}")

    print("\nFeature Flags:")
    print(f"  Async Memorization: {config.features.async_memorization}")
    print(f"  Adaptive Learning Rate: {config.features.adaptive_learning_rate}")
    print(f"  Memory Compression: {config.features.memory_compression}")

    print("\n" + "=" * 60)
    print("Configuration validation: PASSED")
