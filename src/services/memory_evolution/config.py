"""
Project Aura - Memory Evolution Configuration (ADR-080)

Configuration management for memory evolution services including
thresholds, feature flags, and AWS resource settings.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

_config_instance: Optional["MemoryEvolutionConfig"] = None


@dataclass
class ConsolidationConfig:
    """Configuration for CONSOLIDATE operations."""

    # Similarity threshold for automatic consolidation
    similarity_threshold: float = 0.85

    # Minimum confidence required to execute consolidation
    min_confidence: float = 0.7

    # Maximum memories to consolidate in single operation
    max_batch_size: int = 10

    # Merge strategy: "weighted_average", "most_recent", "highest_value"
    default_merge_strategy: str = "weighted_average"

    # Enable automatic consolidation discovery
    auto_discovery_enabled: bool = True

    # Discovery scan interval in seconds
    discovery_interval_seconds: int = 300


@dataclass
class PruneConfig:
    """Configuration for PRUNE operations."""

    # Prune score threshold (memories above this are candidates)
    prune_threshold: float = 0.8

    # Minimum age in days before memory can be pruned
    min_age_days: int = 7

    # Maximum memories to prune in single operation
    max_batch_size: int = 50

    # Minimum access count to protect from pruning
    min_access_protection: int = 3

    # Enable automatic pruning
    auto_prune_enabled: bool = True

    # Prune evaluation interval in seconds
    evaluation_interval_seconds: int = 3600

    # Retention period before permanent deletion (soft delete first)
    soft_delete_days: int = 30


@dataclass
class ReinforceConfig:
    """Configuration for REINFORCE operations (Titan TTT integration)."""

    # Titan TTT learning rate adjustment factor
    learning_rate_factor: float = 1.2

    # Memorization threshold adjustment for successful patterns
    threshold_adjustment: float = 0.1

    # Minimum success rate to trigger reinforcement
    min_success_rate: float = 0.7

    # Maximum reinforcement boost
    max_reinforcement_factor: float = 2.0


@dataclass
class AsyncConfig:
    """Configuration for async refine operations via SQS."""

    # Confidence threshold for async routing (below = async)
    sync_confidence_threshold: float = 0.9

    # SQS visibility timeout in seconds
    visibility_timeout: int = 300

    # Maximum retries before DLQ
    max_retries: int = 3

    # Enable async processing
    async_enabled: bool = True


@dataclass
class MetricsConfig:
    """Configuration for CloudWatch metrics publishing."""

    # Aggregation interval in seconds
    aggregation_interval_seconds: int = 60

    # Enable metrics publishing
    enabled: bool = True

    # CloudWatch namespace
    namespace: str = "Aura/MemoryEvolution"

    # Only publish these core metrics to control costs
    core_metrics: list[str] = field(
        default_factory=lambda: [
            "EvolutionGain",
            "StrategyReuseRate",
            "RetrievalPrecision",
            "MemoryUtilization",
            "ConsolidationCount",
        ]
    )


@dataclass
class StorageConfig:
    """Configuration for DynamoDB storage."""

    # Table name pattern
    table_name_pattern: str = "{project_name}-memory-evolution-{environment}"

    # Evolution tracking table name pattern (Phase 2)
    evolution_table_name_pattern: str = "{project_name}-evolution-metrics-{environment}"

    # S3 bucket pattern for storing full refine action details
    s3_bucket_pattern: str = "{project_name}-memory-evolution-{environment}"

    # TTL in days (90 dev, 365 prod)
    ttl_days_dev: int = 90
    ttl_days_qa: int = 180
    ttl_days_prod: int = 365

    # Evolution table TTL (Phase 2)
    evolution_table_ttl_days_dev: int = 90
    evolution_table_ttl_days_prod: int = 365

    # Enable point-in-time recovery
    pitr_enabled: bool = True

    # Enable DynamoDB Streams for rollback
    streams_enabled: bool = True


@dataclass
class SecurityConfig:
    """Security configuration for memory evolution."""

    # Require tenant_id on all operations
    require_tenant_isolation: bool = True

    # Require security_domain on all operations
    require_domain_boundary: bool = True

    # Enable encryption at rest (KMS)
    encryption_enabled: bool = True

    # KMS key alias pattern
    kms_key_alias_pattern: str = "alias/{project_name}-memory-evolution-{environment}"


@dataclass
class FeatureFlags:
    """Feature flags for phased rollout."""

    # Phase 1a: CONSOLIDATE and PRUNE
    consolidate_enabled: bool = True
    prune_enabled: bool = True

    # Phase 1b: REINFORCE (Titan TTT integration)
    reinforce_enabled: bool = False

    # Phase 3: ABSTRACT (LLM-based)
    abstract_enabled: bool = False

    # Phase 5: Advanced operations
    link_enabled: bool = False
    correct_enabled: bool = False
    rollback_enabled: bool = False


@dataclass
class MemoryEvolutionConfig:
    """Complete configuration for memory evolution services."""

    # Environment settings
    environment: str = "dev"
    project_name: str = "aura"
    aws_region: str = "us-east-1"

    # Component configurations
    consolidation: ConsolidationConfig = field(default_factory=ConsolidationConfig)
    prune: PruneConfig = field(default_factory=PruneConfig)
    reinforce: ReinforceConfig = field(default_factory=ReinforceConfig)
    async_config: AsyncConfig = field(default_factory=AsyncConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    features: FeatureFlags = field(default_factory=FeatureFlags)

    @property
    def table_name(self) -> str:
        """Get the DynamoDB table name."""
        return self.storage.table_name_pattern.format(
            project_name=self.project_name, environment=self.environment
        )

    @property
    def evolution_table_name(self) -> str:
        """Get the evolution metrics DynamoDB table name (Phase 2)."""
        return self.storage.evolution_table_name_pattern.format(
            project_name=self.project_name, environment=self.environment
        )

    @property
    def queue_url_pattern(self) -> str:
        """Get the SQS queue URL pattern."""
        return f"https://sqs.{self.aws_region}.amazonaws.com/{{account_id}}/{self.project_name}-refine-async-{self.environment}"

    @property
    def kms_key_alias(self) -> str:
        """Get the KMS key alias."""
        return self.security.kms_key_alias_pattern.format(
            project_name=self.project_name, environment=self.environment
        )

    @property
    def ttl_days(self) -> int:
        """Get TTL based on environment."""
        if self.environment == "prod":
            return self.storage.ttl_days_prod
        elif self.environment == "qa":
            return self.storage.ttl_days_qa
        return self.storage.ttl_days_dev

    @classmethod
    def from_environment(cls) -> "MemoryEvolutionConfig":
        """Create configuration from environment variables."""
        environment = os.getenv("ENVIRONMENT", "dev")
        project_name = os.getenv("PROJECT_NAME", "aura")
        aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

        # Create default config
        config = cls(
            environment=environment, project_name=project_name, aws_region=aws_region
        )

        # Override from environment variables
        if os.getenv("MEMORY_EVOLUTION_CONSOLIDATION_THRESHOLD"):
            config.consolidation.similarity_threshold = float(
                os.getenv("MEMORY_EVOLUTION_CONSOLIDATION_THRESHOLD", "0.85")
            )

        if os.getenv("MEMORY_EVOLUTION_PRUNE_THRESHOLD"):
            config.prune.prune_threshold = float(
                os.getenv("MEMORY_EVOLUTION_PRUNE_THRESHOLD", "0.8")
            )

        if os.getenv("MEMORY_EVOLUTION_ASYNC_ENABLED"):
            config.async_config.async_enabled = (
                os.getenv("MEMORY_EVOLUTION_ASYNC_ENABLED", "true").lower() == "true"
            )

        if os.getenv("MEMORY_EVOLUTION_METRICS_ENABLED"):
            config.metrics.enabled = (
                os.getenv("MEMORY_EVOLUTION_METRICS_ENABLED", "true").lower() == "true"
            )

        # Feature flags from environment
        if os.getenv("MEMORY_EVOLUTION_REINFORCE_ENABLED"):
            config.features.reinforce_enabled = (
                os.getenv("MEMORY_EVOLUTION_REINFORCE_ENABLED", "false").lower()
                == "true"
            )

        if os.getenv("MEMORY_EVOLUTION_ABSTRACT_ENABLED"):
            config.features.abstract_enabled = (
                os.getenv("MEMORY_EVOLUTION_ABSTRACT_ENABLED", "false").lower()
                == "true"
            )

        return config


def get_memory_evolution_config() -> MemoryEvolutionConfig:
    """Get or create the singleton configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = MemoryEvolutionConfig.from_environment()
    return _config_instance


def set_memory_evolution_config(config: MemoryEvolutionConfig) -> None:
    """Set the configuration instance (for testing)."""
    global _config_instance
    _config_instance = config


def reset_memory_evolution_config() -> None:
    """Reset the configuration instance (for testing)."""
    global _config_instance
    _config_instance = None
