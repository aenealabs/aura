"""
Project Aura - Streaming Analysis Service Configuration

Configuration management for streaming analysis service with
support for Kinesis, ElastiCache, and analysis workers.

Based on ADR-079: Scale & AI Model Security
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from .contracts import AnalysisScope, FeedbackSeverity


@dataclass
class KinesisConfig:
    """Configuration for Kinesis streams."""

    enabled: bool = True
    ci_events_stream: str = "aura-ci-events"
    results_stream: str = "aura-analysis-results"
    shard_count: int = 10
    retention_hours: int = 168  # 7 days
    batch_size: int = 100
    max_batch_interval_ms: int = 1000
    max_retries: int = 3
    consumer_name: str = "aura-streaming-consumer"


@dataclass
class CacheConfig:
    """Configuration for analysis caching."""

    enabled: bool = True
    redis_endpoint: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    ast_cache_ttl_seconds: int = 86400  # 24 hours
    embedding_cache_ttl_seconds: int = 604800  # 7 days
    result_cache_ttl_seconds: int = 3600  # 1 hour
    max_cache_size_mb: int = 1024
    connection_pool_size: int = 10


@dataclass
class WorkerConfig:
    """Configuration for analysis workers."""

    enabled: bool = True
    min_workers: int = 5
    max_workers: int = 50
    worker_timeout_ms: int = 30000
    task_timeout_ms: int = 5000
    batch_size: int = 10
    health_check_interval_seconds: int = 30
    autoscale_cooldown_seconds: int = 60
    autoscale_threshold_high: float = 0.8
    autoscale_threshold_low: float = 0.2


@dataclass
class AnalysisConfig:
    """Configuration for analysis behavior."""

    default_scope: AnalysisScope = AnalysisScope.INCREMENTAL
    default_timeout_ms: int = 5000
    max_timeout_ms: int = 30000
    max_files_per_request: int = 1000
    max_file_size_bytes: int = 10_000_000  # 10 MB
    min_severity_to_fail: FeedbackSeverity = FeedbackSeverity.HIGH
    enable_suggestions: bool = True
    enable_fix_generation: bool = True
    parallel_file_analysis: bool = True
    max_parallel_files: int = 20


@dataclass
class NotificationConfig:
    """Configuration for CI/CD notifications."""

    enabled: bool = True
    github_enabled: bool = True
    gitlab_enabled: bool = True
    jenkins_enabled: bool = True
    codebuild_enabled: bool = True
    max_annotations_per_check: int = 50
    include_suggestions: bool = True
    notification_timeout_ms: int = 5000


@dataclass
class MetricsConfig:
    """Configuration for metrics publishing."""

    enabled: bool = True
    namespace: str = "Aura/Streaming"
    publish_interval_seconds: int = 60
    buffer_size: int = 100
    latency_buckets: list[int] = field(
        default_factory=lambda: [100, 250, 500, 1000, 2000, 5000]
    )


@dataclass
class StreamingConfig:
    """Root configuration for streaming analysis service."""

    environment: str = "dev"
    enabled: bool = True
    kinesis: KinesisConfig = field(default_factory=KinesisConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if self.kinesis.shard_count < 1:
            errors.append("kinesis.shard_count must be >= 1")

        if self.kinesis.retention_hours < 24:
            errors.append("kinesis.retention_hours must be >= 24")

        if self.cache.ast_cache_ttl_seconds < 60:
            errors.append("cache.ast_cache_ttl_seconds must be >= 60")

        if self.worker.min_workers < 1:
            errors.append("worker.min_workers must be >= 1")

        if self.worker.max_workers < self.worker.min_workers:
            errors.append("worker.max_workers must be >= worker.min_workers")

        if self.analysis.default_timeout_ms > self.analysis.max_timeout_ms:
            errors.append(
                "analysis.default_timeout_ms must be <= analysis.max_timeout_ms"
            )

        if self.analysis.max_files_per_request < 1:
            errors.append("analysis.max_files_per_request must be >= 1")

        return errors

    @classmethod
    def from_environment(cls) -> "StreamingConfig":
        """Create configuration from environment variables."""
        environment = os.getenv("ENVIRONMENT", "dev")

        kinesis = KinesisConfig(
            enabled=os.getenv("STREAMING_KINESIS_ENABLED", "true").lower() == "true",
            ci_events_stream=os.getenv(
                "STREAMING_CI_EVENTS_STREAM",
                f"aura-ci-events-{environment}",
            ),
            results_stream=os.getenv(
                "STREAMING_RESULTS_STREAM",
                f"aura-analysis-results-{environment}",
            ),
            shard_count=int(os.getenv("STREAMING_SHARD_COUNT", "10")),
            retention_hours=int(os.getenv("STREAMING_RETENTION_HOURS", "168")),
        )

        cache = CacheConfig(
            enabled=os.getenv("STREAMING_CACHE_ENABLED", "true").lower() == "true",
            redis_endpoint=os.getenv("STREAMING_REDIS_ENDPOINT", "localhost"),
            redis_port=int(os.getenv("STREAMING_REDIS_PORT", "6379")),
            redis_password=os.getenv("STREAMING_REDIS_PASSWORD"),
        )

        worker = WorkerConfig(
            min_workers=int(os.getenv("STREAMING_MIN_WORKERS", "5")),
            max_workers=int(os.getenv("STREAMING_MAX_WORKERS", "50")),
            task_timeout_ms=int(os.getenv("STREAMING_TASK_TIMEOUT_MS", "5000")),
        )

        analysis = AnalysisConfig(
            default_timeout_ms=int(os.getenv("STREAMING_DEFAULT_TIMEOUT_MS", "5000")),
            max_files_per_request=int(
                os.getenv("STREAMING_MAX_FILES_PER_REQUEST", "1000")
            ),
        )

        notification = NotificationConfig(
            enabled=os.getenv("STREAMING_NOTIFICATIONS_ENABLED", "true").lower()
            == "true",
        )

        metrics = MetricsConfig(
            enabled=os.getenv("STREAMING_METRICS_ENABLED", "true").lower() == "true",
            namespace=os.getenv("STREAMING_METRICS_NAMESPACE", "Aura/Streaming"),
        )

        return cls(
            environment=environment,
            enabled=os.getenv("STREAMING_ENABLED", "true").lower() == "true",
            kinesis=kinesis,
            cache=cache,
            worker=worker,
            analysis=analysis,
            notification=notification,
            metrics=metrics,
        )

    @classmethod
    def for_testing(cls) -> "StreamingConfig":
        """Create configuration for unit tests."""
        return cls(
            environment="test",
            enabled=True,
            kinesis=KinesisConfig(
                enabled=False,  # Disable Kinesis in tests
                shard_count=1,
            ),
            cache=CacheConfig(
                enabled=False,  # Disable Redis in tests
            ),
            worker=WorkerConfig(
                min_workers=1,
                max_workers=2,
                task_timeout_ms=1000,
            ),
            analysis=AnalysisConfig(
                default_timeout_ms=1000,
                max_timeout_ms=5000,
            ),
            notification=NotificationConfig(
                enabled=False,
            ),
            metrics=MetricsConfig(
                enabled=False,
            ),
        )

    @classmethod
    def for_production(cls) -> "StreamingConfig":
        """Create production configuration."""
        return cls(
            environment="prod",
            enabled=True,
            kinesis=KinesisConfig(
                shard_count=100,
                retention_hours=168,
            ),
            cache=CacheConfig(
                max_cache_size_mb=4096,
                connection_pool_size=50,
            ),
            worker=WorkerConfig(
                min_workers=20,
                max_workers=100,
            ),
            analysis=AnalysisConfig(
                default_timeout_ms=2000,
                max_parallel_files=50,
            ),
            metrics=MetricsConfig(
                publish_interval_seconds=30,
            ),
        )


# Singleton pattern for configuration
_streaming_config: Optional[StreamingConfig] = None


def get_streaming_config() -> StreamingConfig:
    """Get singleton configuration instance."""
    global _streaming_config
    if _streaming_config is None:
        _streaming_config = StreamingConfig.from_environment()
    return _streaming_config


def set_streaming_config(config: StreamingConfig) -> None:
    """Set singleton configuration instance."""
    global _streaming_config
    _streaming_config = config


def reset_streaming_config() -> None:
    """Reset singleton configuration instance."""
    global _streaming_config
    _streaming_config = None
