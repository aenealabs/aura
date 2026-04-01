"""
Project Aura - Constraint Geometry Engine Configuration

Centralized configuration for the deterministic CGE pipeline.
All thresholds, cache settings, and feature flags are configurable.

Performance Targets (ADR-081):
- P50 <25ms, P95 <50ms, P99 <100ms
- 100% determinism (same input = same score)
- >95% cache hit rate after warm-up

Author: Project Aura Team
Created: 2026-02-11
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CacheConfig:
    """Configuration for the two-tier embedding cache."""

    # In-process LRU cache
    lru_max_size: int = 10_000
    lru_ttl_seconds: int = 3600  # 1 hour

    # ElastiCache Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_ttl_seconds: int = 86400  # 24 hours
    redis_key_prefix: str = "cge:emb:"
    enable_redis: bool = True

    # Score cache (composite CCS cache)
    enable_score_cache: bool = True
    score_cache_ttl_seconds: int = 3600


@dataclass
class NeptuneConfig:
    """Configuration for Neptune constraint graph access."""

    endpoint: str = "neptune.aura.local:8182"
    enable_ssl: bool = True
    connection_timeout_ms: int = 5000
    request_timeout_ms: int = 15000
    max_concurrent_requests: int = 10

    # Graph traversal limits
    max_traversal_depth: int = 5
    max_rules_per_axis: int = 50


@dataclass
class EmbeddingConfig:
    """Configuration for Bedrock Titan embedding computation."""

    model_id: str = "amazon.titan-embed-text-v2:0"
    dimension: int = 1024
    region: str = "us-east-1"
    timeout_ms: int = 5000


@dataclass
class OpenSearchConfig:
    """Configuration for OpenSearch constraint embedding index."""

    endpoint: str = "opensearch.aura.local:9200"
    index_name: str = "aura-constraint-embeddings"
    enable_ssl: bool = True


@dataclass
class MetricsConfig:
    """Configuration for CloudWatch metrics publishing."""

    namespace: str = "Aura/CGE"
    enabled: bool = True
    buffer_size: int = 50
    flush_interval_seconds: int = 60

    # Metric names
    metric_ccs_score: str = "CCSScore"
    metric_latency: str = "CGELatency"
    metric_cache_hit: str = "CacheHitRate"
    metric_escalation_rate: str = "CGEEscalationRate"
    metric_axis_score: str = "AxisScore"

    # Dimensions
    include_environment: bool = True
    include_profile: bool = True
    include_axis: bool = True


@dataclass
class AuditConfig:
    """Configuration for coherence audit dispatch."""

    # DynamoDB
    table_name: str = "aura-coherence-audit"
    enable_audit: bool = True

    # SQS
    queue_name: str = "aura-coherence-audit"
    enable_async_dispatch: bool = True

    # What to log
    log_auto_execute: bool = True
    log_human_review: bool = True
    log_escalations: bool = True
    log_rejections: bool = True


@dataclass
class CGEConfig:
    """
    Master configuration for the Constraint Geometry Engine.

    Usage:
        # Default configuration
        config = CGEConfig()

        # Custom configuration
        config = CGEConfig(
            enabled=True,
            cache=CacheConfig(lru_max_size=50000),
            default_profile="dod-il5",
        )

        # From environment
        config = CGEConfig.from_environment()
    """

    # Global settings
    enabled: bool = True
    environment: str = "dev"
    default_profile: str = "default"

    # Feature flags
    enable_provenance_weighting: bool = True
    enable_temporal_validity: bool = True
    enable_constraint_caching: bool = True

    # Sub-configurations
    cache: CacheConfig = field(default_factory=CacheConfig)
    neptune: NeptuneConfig = field(default_factory=NeptuneConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    opensearch: OpenSearchConfig = field(default_factory=OpenSearchConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)

    # Performance budget
    target_p50_latency_ms: float = 25.0
    target_p95_latency_ms: float = 50.0
    target_p99_latency_ms: float = 100.0

    # Safety
    fail_open: bool = False  # If CGE fails, block (False) or allow (True)

    @classmethod
    def from_environment(cls) -> "CGEConfig":
        """Create configuration from environment variables.

        Environment variables:
            CGE_ENABLED: Enable/disable CGE (default: true)
            CGE_ENVIRONMENT: Deployment environment (default: dev)
            CGE_DEFAULT_PROFILE: Default policy profile (default: default)
            CGE_FAIL_OPEN: Allow on failure (default: false)
            CGE_REDIS_HOST: ElastiCache endpoint
            CGE_NEPTUNE_ENDPOINT: Neptune endpoint
            CGE_OPENSEARCH_ENDPOINT: OpenSearch endpoint
        """
        return cls(
            enabled=os.environ.get("CGE_ENABLED", "true").lower() == "true",
            environment=os.environ.get("CGE_ENVIRONMENT", "dev"),
            default_profile=os.environ.get("CGE_DEFAULT_PROFILE", "default"),
            fail_open=os.environ.get("CGE_FAIL_OPEN", "false").lower() == "true",
            enable_provenance_weighting=os.environ.get(
                "CGE_PROVENANCE_WEIGHTING", "true"
            ).lower()
            == "true",
            cache=CacheConfig(
                redis_host=os.environ.get("CGE_REDIS_HOST", "localhost"),
                redis_port=int(os.environ.get("CGE_REDIS_PORT", "6379")),
                enable_redis=os.environ.get("CGE_REDIS_ENABLED", "true").lower()
                == "true",
                lru_max_size=int(os.environ.get("CGE_LRU_MAX_SIZE", "10000")),
            ),
            neptune=NeptuneConfig(
                endpoint=os.environ.get(
                    "CGE_NEPTUNE_ENDPOINT", "neptune.aura.local:8182"
                ),
            ),
            embedding=EmbeddingConfig(
                region=os.environ.get("AWS_REGION", "us-east-1"),
            ),
            opensearch=OpenSearchConfig(
                endpoint=os.environ.get(
                    "CGE_OPENSEARCH_ENDPOINT", "opensearch.aura.local:9200"
                ),
            ),
            metrics=MetricsConfig(
                enabled=os.environ.get("CGE_METRICS_ENABLED", "true").lower() == "true",
            ),
            audit=AuditConfig(
                enable_audit=os.environ.get("CGE_AUDIT_ENABLED", "true").lower()
                == "true",
                table_name=os.environ.get("CGE_AUDIT_TABLE", "aura-coherence-audit"),
            ),
        )

    @classmethod
    def for_production(cls) -> "CGEConfig":
        """Create production-hardened configuration."""
        return cls(
            enabled=True,
            environment="prod",
            fail_open=False,
            enable_provenance_weighting=True,
            enable_temporal_validity=True,
            cache=CacheConfig(
                lru_max_size=50_000,
                enable_redis=True,
            ),
            metrics=MetricsConfig(
                enabled=True,
                include_environment=True,
                include_profile=True,
                include_axis=True,
            ),
            audit=AuditConfig(
                enable_audit=True,
                enable_async_dispatch=True,
                log_auto_execute=True,
                log_human_review=True,
                log_escalations=True,
                log_rejections=True,
            ),
        )

    @classmethod
    def for_testing(cls) -> "CGEConfig":
        """Create configuration for unit tests (no external dependencies)."""
        return cls(
            enabled=True,
            environment="test",
            fail_open=False,
            enable_provenance_weighting=True,
            enable_temporal_validity=True,
            cache=CacheConfig(
                lru_max_size=100,
                enable_redis=False,
            ),
            neptune=NeptuneConfig(
                endpoint="localhost:8182",
            ),
            metrics=MetricsConfig(enabled=False),
            audit=AuditConfig(
                enable_audit=False,
                enable_async_dispatch=False,
            ),
        )

    def validate(self) -> list[str]:
        """Validate configuration for consistency and safety.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if self.environment == "prod":
            if self.fail_open:
                errors.append("fail_open=True is dangerous in production")
            if not self.audit.enable_audit:
                errors.append("Audit logging should be enabled in production")
            if not self.metrics.enabled:
                errors.append("Metrics should be enabled in production")

        if self.cache.lru_max_size < 0:
            errors.append("lru_max_size must be non-negative")

        if self.neptune.max_traversal_depth < 1:
            errors.append("max_traversal_depth must be >= 1")

        return errors


# Singleton instance
_config_instance: Optional[CGEConfig] = None


def get_cge_config() -> CGEConfig:
    """Get singleton configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = CGEConfig.from_environment()
    return _config_instance


def reset_config() -> None:
    """Reset configuration singleton (for testing)."""
    global _config_instance
    _config_instance = None
