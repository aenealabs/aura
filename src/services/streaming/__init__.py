"""
Project Aura - Streaming Analysis Service

High-performance streaming analysis for CI/CD pipelines with
sub-second security feedback at billion-line scale.

Based on ADR-079: Scale & AI Model Security

Services:
- StreamingAnalysisEngine: Main analysis engine with real-time feedback
- IncrementalScanner: Scans only changed code portions

Key Features:
- P50 latency < 500ms for incremental analysis
- Caching for AST and embeddings
- Integration with GitHub, GitLab, Jenkins, CodeBuild
- Security pattern detection
"""

# Services
from .analysis_engine import (
    IncrementalScanner,
    StreamingAnalysisEngine,
    get_streaming_engine,
    reset_streaming_engine,
)

# Configuration
from .config import (
    AnalysisConfig,
    CacheConfig,
    KinesisConfig,
    MetricsConfig,
    NotificationConfig,
    StreamingConfig,
    WorkerConfig,
    get_streaming_config,
    reset_streaming_config,
    set_streaming_config,
)

# Contracts
from .contracts import (
    AffectedFile,
    AnalysisScope,
    AnalysisStatus,
    ASTCacheEntry,
    CacheStatus,
    CINotification,
    CIProvider,
    CIWebhookEvent,
    DiffType,
    EmbeddingCacheEntry,
    FeedbackSeverity,
    FeedbackType,
    FileChange,
    IncrementalScanResult,
    KinesisRecord,
    RuleSet,
    SecurityRule,
    StreamingAnalysisRequest,
    StreamingAnalysisResult,
    StreamingFeedback,
    StreamingMetrics,
)

# Exceptions
from .exceptions import (
    AnalysisCancelledError,
    AnalysisError,
    AnalysisTimeoutError,
    ASTCacheError,
    ASTParseError,
    CacheCapacityError,
    CacheConnectionError,
    CacheError,
    CacheReadError,
    CacheWriteError,
    CommitNotFoundError,
    DiffNotAvailableError,
    EmbeddingCacheError,
    FileTooLargeError,
    IncrementalScanError,
    KinesisError,
    KinesisReadError,
    KinesisStreamNotFoundError,
    KinesisThrottlingError,
    KinesisWriteError,
    NoAvailableWorkersError,
    NotificationDeliveryError,
    NotificationError,
    RateLimitedError,
    RepositoryAccessDeniedError,
    RepositoryError,
    RepositoryNotFoundError,
    RuleEvaluationError,
    ShardIteratorExpiredError,
    StreamingError,
    TooManyFilesError,
    UnsupportedCIProviderError,
    UnsupportedLanguageError,
    WebhookSignatureError,
    WebhookValidationError,
    WorkerError,
    WorkerHealthCheckError,
    WorkerPoolExhaustedError,
    WorkerTimeoutError,
)

# Metrics
from .metrics import (
    StreamingMetricsPublisher,
    get_streaming_metrics,
    reset_streaming_metrics,
)

__all__ = [
    # Contracts
    "AffectedFile",
    "AnalysisScope",
    "AnalysisStatus",
    "ASTCacheEntry",
    "CacheStatus",
    "CINotification",
    "CIProvider",
    "CIWebhookEvent",
    "DiffType",
    "EmbeddingCacheEntry",
    "FeedbackSeverity",
    "FeedbackType",
    "FileChange",
    "IncrementalScanResult",
    "KinesisRecord",
    "RuleSet",
    "SecurityRule",
    "StreamingAnalysisRequest",
    "StreamingAnalysisResult",
    "StreamingFeedback",
    "StreamingMetrics",
    # Configuration
    "AnalysisConfig",
    "CacheConfig",
    "KinesisConfig",
    "MetricsConfig",
    "NotificationConfig",
    "StreamingConfig",
    "WorkerConfig",
    "get_streaming_config",
    "reset_streaming_config",
    "set_streaming_config",
    # Exceptions
    "AnalysisCancelledError",
    "AnalysisError",
    "AnalysisTimeoutError",
    "ASTCacheError",
    "ASTParseError",
    "CacheCapacityError",
    "CacheConnectionError",
    "CacheError",
    "CacheReadError",
    "CacheWriteError",
    "CommitNotFoundError",
    "DiffNotAvailableError",
    "EmbeddingCacheError",
    "FileTooLargeError",
    "IncrementalScanError",
    "KinesisError",
    "KinesisReadError",
    "KinesisStreamNotFoundError",
    "KinesisThrottlingError",
    "KinesisWriteError",
    "NoAvailableWorkersError",
    "NotificationDeliveryError",
    "NotificationError",
    "RateLimitedError",
    "RepositoryAccessDeniedError",
    "RepositoryError",
    "RepositoryNotFoundError",
    "RuleEvaluationError",
    "ShardIteratorExpiredError",
    "StreamingError",
    "TooManyFilesError",
    "UnsupportedCIProviderError",
    "UnsupportedLanguageError",
    "WebhookSignatureError",
    "WebhookValidationError",
    "WorkerError",
    "WorkerHealthCheckError",
    "WorkerPoolExhaustedError",
    "WorkerTimeoutError",
    # Metrics
    "StreamingMetricsPublisher",
    "get_streaming_metrics",
    "reset_streaming_metrics",
    # Services
    "IncrementalScanner",
    "StreamingAnalysisEngine",
    "get_streaming_engine",
    "reset_streaming_engine",
]
