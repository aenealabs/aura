"""
Project Aura - Polyglot Dependency Graph Configuration

Configuration management for polyglot dependency graph service
with Neptune sharding support for billion-node scalability.

Based on ADR-079: Scale & AI Model Security
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from .contracts import Language


@dataclass
class NeptuneConfig:
    """Configuration for Neptune graph database."""

    enabled: bool = True
    cluster_endpoint: str = "localhost"
    reader_endpoint: str = "localhost"
    port: int = 8182
    region: str = "us-east-1"
    use_iam_auth: bool = True
    connection_timeout_ms: int = 5000
    query_timeout_ms: int = 30000
    max_connections: int = 50
    ssl_enabled: bool = True


@dataclass
class ShardingConfig:
    """Configuration for Neptune sharding."""

    enabled: bool = True
    num_shards: int = 8
    rebalance_threshold: float = 0.2
    shard_endpoints: list[str] = field(default_factory=list)
    parallel_queries: bool = True
    max_parallel_shards: int = 4


@dataclass
class IndexingConfig:
    """Configuration for repository indexing."""

    enabled: bool = True
    max_file_size_bytes: int = 10_000_000  # 10 MB
    max_files_per_repo: int = 100_000
    batch_size: int = 1000
    parallel_workers: int = 4
    supported_languages: list[Language] = field(
        default_factory=lambda: [
            Language.PYTHON,
            Language.JAVASCRIPT,
            Language.TYPESCRIPT,
            Language.GO,
            Language.JAVA,
            Language.RUST,
        ]
    )
    exclude_patterns: list[str] = field(
        default_factory=lambda: [
            "node_modules/*",
            "vendor/*",
            ".git/*",
            "__pycache__/*",
            "*.min.js",
            "*.bundle.js",
        ]
    )


@dataclass
class CacheConfig:
    """Configuration for caching."""

    enabled: bool = True
    entity_cache_ttl_seconds: int = 3600
    query_cache_ttl_seconds: int = 300
    max_cache_size_mb: int = 512
    redis_endpoint: Optional[str] = None


@dataclass
class ImpactAnalysisConfig:
    """Configuration for impact analysis."""

    enabled: bool = True
    max_depth: int = 10
    max_affected_entities: int = 10000
    include_tests: bool = True
    include_transitive: bool = True
    timeout_ms: int = 30000


@dataclass
class VulnerabilityConfig:
    """Configuration for vulnerability tracking."""

    enabled: bool = True
    auto_scan: bool = True
    scan_interval_hours: int = 24
    sources: list[str] = field(
        default_factory=lambda: ["nvd", "github-advisories", "osv"]
    )
    severity_threshold: str = "medium"


@dataclass
class MetricsConfig:
    """Configuration for metrics."""

    enabled: bool = True
    namespace: str = "Aura/Polyglot"
    publish_interval_seconds: int = 60
    detailed_query_metrics: bool = True


@dataclass
class PolyglotConfig:
    """Root configuration for polyglot dependency graph service."""

    environment: str = "dev"
    enabled: bool = True
    neptune: NeptuneConfig = field(default_factory=NeptuneConfig)
    sharding: ShardingConfig = field(default_factory=ShardingConfig)
    indexing: IndexingConfig = field(default_factory=IndexingConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    impact_analysis: ImpactAnalysisConfig = field(default_factory=ImpactAnalysisConfig)
    vulnerability: VulnerabilityConfig = field(default_factory=VulnerabilityConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if self.neptune.port < 1 or self.neptune.port > 65535:
            errors.append("neptune.port must be between 1 and 65535")

        if self.sharding.num_shards < 1:
            errors.append("sharding.num_shards must be >= 1")

        if self.sharding.max_parallel_shards < 1:
            errors.append("sharding.max_parallel_shards must be >= 1")

        if self.indexing.batch_size < 1:
            errors.append("indexing.batch_size must be >= 1")

        if self.indexing.parallel_workers < 1:
            errors.append("indexing.parallel_workers must be >= 1")

        if self.impact_analysis.max_depth < 1:
            errors.append("impact_analysis.max_depth must be >= 1")

        return errors

    @classmethod
    def from_environment(cls) -> "PolyglotConfig":
        """Create configuration from environment variables."""
        environment = os.getenv("ENVIRONMENT", "dev")

        neptune = NeptuneConfig(
            enabled=os.getenv("POLYGLOT_NEPTUNE_ENABLED", "true").lower() == "true",
            cluster_endpoint=os.getenv("POLYGLOT_NEPTUNE_ENDPOINT", "localhost"),
            reader_endpoint=os.getenv("POLYGLOT_NEPTUNE_READER_ENDPOINT", "localhost"),
            port=int(os.getenv("POLYGLOT_NEPTUNE_PORT", "8182")),
            region=os.getenv("AWS_REGION", "us-east-1"),
            use_iam_auth=os.getenv("POLYGLOT_NEPTUNE_IAM_AUTH", "true").lower()
            == "true",
        )

        sharding = ShardingConfig(
            enabled=os.getenv("POLYGLOT_SHARDING_ENABLED", "true").lower() == "true",
            num_shards=int(os.getenv("POLYGLOT_NUM_SHARDS", "8")),
        )

        indexing = IndexingConfig(
            parallel_workers=int(os.getenv("POLYGLOT_INDEX_WORKERS", "4")),
            batch_size=int(os.getenv("POLYGLOT_INDEX_BATCH_SIZE", "1000")),
        )

        cache = CacheConfig(
            enabled=os.getenv("POLYGLOT_CACHE_ENABLED", "true").lower() == "true",
            redis_endpoint=os.getenv("POLYGLOT_REDIS_ENDPOINT"),
        )

        metrics = MetricsConfig(
            enabled=os.getenv("POLYGLOT_METRICS_ENABLED", "true").lower() == "true",
            namespace=os.getenv("POLYGLOT_METRICS_NAMESPACE", "Aura/Polyglot"),
        )

        return cls(
            environment=environment,
            enabled=os.getenv("POLYGLOT_ENABLED", "true").lower() == "true",
            neptune=neptune,
            sharding=sharding,
            indexing=indexing,
            cache=cache,
            metrics=metrics,
        )

    @classmethod
    def for_testing(cls) -> "PolyglotConfig":
        """Create configuration for unit tests."""
        return cls(
            environment="test",
            enabled=True,
            neptune=NeptuneConfig(
                enabled=False,  # Disable Neptune in tests
            ),
            sharding=ShardingConfig(
                enabled=False,
                num_shards=1,
            ),
            indexing=IndexingConfig(
                parallel_workers=1,
                batch_size=100,
            ),
            cache=CacheConfig(
                enabled=False,
            ),
            impact_analysis=ImpactAnalysisConfig(
                max_depth=5,
                timeout_ms=5000,
            ),
            vulnerability=VulnerabilityConfig(
                enabled=False,
            ),
            metrics=MetricsConfig(
                enabled=False,
            ),
        )

    @classmethod
    def for_production(cls) -> "PolyglotConfig":
        """Create production configuration."""
        return cls(
            environment="prod",
            enabled=True,
            neptune=NeptuneConfig(
                max_connections=100,
            ),
            sharding=ShardingConfig(
                num_shards=8,
                max_parallel_shards=8,
            ),
            indexing=IndexingConfig(
                parallel_workers=8,
                batch_size=5000,
            ),
            cache=CacheConfig(
                max_cache_size_mb=2048,
            ),
            metrics=MetricsConfig(
                publish_interval_seconds=30,
            ),
        )


# Singleton pattern
_polyglot_config: Optional[PolyglotConfig] = None


def get_polyglot_config() -> PolyglotConfig:
    """Get singleton configuration instance."""
    global _polyglot_config
    if _polyglot_config is None:
        _polyglot_config = PolyglotConfig.from_environment()
    return _polyglot_config


def set_polyglot_config(config: PolyglotConfig) -> None:
    """Set singleton configuration instance."""
    global _polyglot_config
    _polyglot_config = config


def reset_polyglot_config() -> None:
    """Reset singleton configuration instance."""
    global _polyglot_config
    _polyglot_config = None
