"""
Project Aura - Streaming Analysis Service Exceptions

Custom exceptions for streaming analysis operations including
Kinesis errors, cache errors, analysis errors, and CI/CD notifications.

Based on ADR-079: Scale & AI Model Security
"""

from typing import Any, Optional


class StreamingError(Exception):
    """Base exception for all streaming service errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "STREAMING_ERROR"
        self.details = details or {}


# ============================================================================
# Kinesis Errors
# ============================================================================


class KinesisError(StreamingError):
    """Base exception for Kinesis operations."""

    def __init__(
        self,
        message: str,
        stream_name: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "KINESIS_ERROR", details)
        self.stream_name = stream_name


class KinesisStreamNotFoundError(KinesisError):
    """Stream does not exist."""

    def __init__(self, stream_name: str):
        super().__init__(
            f"Kinesis stream not found: {stream_name}",
            stream_name=stream_name,
        )
        self.error_code = "KINESIS_STREAM_NOT_FOUND"


class KinesisWriteError(KinesisError):
    """Failed to write records to Kinesis."""

    def __init__(
        self,
        stream_name: str,
        failed_count: int,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            f"Failed to write {failed_count} records to stream: {stream_name}",
            stream_name=stream_name,
            details=details,
        )
        self.error_code = "KINESIS_WRITE_ERROR"
        self.failed_count = failed_count


class KinesisReadError(KinesisError):
    """Failed to read records from Kinesis."""

    def __init__(
        self,
        stream_name: str,
        shard_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        msg = f"Failed to read from stream: {stream_name}"
        if shard_id:
            msg += f" (shard: {shard_id})"
        super().__init__(msg, stream_name=stream_name, details=details)
        self.error_code = "KINESIS_READ_ERROR"
        self.shard_id = shard_id


class KinesisThrottlingError(KinesisError):
    """Kinesis request was throttled."""

    def __init__(self, stream_name: str, retry_after_ms: int = 1000):
        super().__init__(
            f"Request throttled for stream: {stream_name}",
            stream_name=stream_name,
        )
        self.error_code = "KINESIS_THROTTLED"
        self.retry_after_ms = retry_after_ms


class ShardIteratorExpiredError(KinesisError):
    """Shard iterator has expired."""

    def __init__(self, stream_name: str, shard_id: str):
        super().__init__(
            f"Shard iterator expired for {stream_name}/{shard_id}",
            stream_name=stream_name,
        )
        self.error_code = "SHARD_ITERATOR_EXPIRED"
        self.shard_id = shard_id


# ============================================================================
# Cache Errors
# ============================================================================


class CacheError(StreamingError):
    """Base exception for cache operations."""

    def __init__(
        self,
        message: str,
        cache_key: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "CACHE_ERROR", details)
        self.cache_key = cache_key


class CacheConnectionError(CacheError):
    """Failed to connect to cache."""

    def __init__(self, endpoint: str, reason: Optional[str] = None):
        msg = f"Failed to connect to cache: {endpoint}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)
        self.error_code = "CACHE_CONNECTION_ERROR"
        self.endpoint = endpoint


class CacheReadError(CacheError):
    """Failed to read from cache."""

    def __init__(self, cache_key: str, reason: Optional[str] = None):
        msg = f"Failed to read cache key: {cache_key}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg, cache_key=cache_key)
        self.error_code = "CACHE_READ_ERROR"


class CacheWriteError(CacheError):
    """Failed to write to cache."""

    def __init__(self, cache_key: str, reason: Optional[str] = None):
        msg = f"Failed to write cache key: {cache_key}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg, cache_key=cache_key)
        self.error_code = "CACHE_WRITE_ERROR"


class CacheCapacityError(CacheError):
    """Cache is at capacity."""

    def __init__(self, current_size_mb: int, max_size_mb: int):
        super().__init__(f"Cache at capacity: {current_size_mb}MB / {max_size_mb}MB")
        self.error_code = "CACHE_CAPACITY_ERROR"
        self.current_size_mb = current_size_mb
        self.max_size_mb = max_size_mb


class ASTCacheError(CacheError):
    """Error with AST caching."""

    def __init__(self, file_path: str, reason: str):
        super().__init__(
            f"AST cache error for {file_path}: {reason}",
            cache_key=file_path,
        )
        self.error_code = "AST_CACHE_ERROR"
        self.file_path = file_path


class EmbeddingCacheError(CacheError):
    """Error with embedding caching."""

    def __init__(self, file_path: str, reason: str):
        super().__init__(
            f"Embedding cache error for {file_path}: {reason}",
            cache_key=file_path,
        )
        self.error_code = "EMBEDDING_CACHE_ERROR"
        self.file_path = file_path


# ============================================================================
# Analysis Errors
# ============================================================================


class AnalysisError(StreamingError):
    """Base exception for analysis operations."""

    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "ANALYSIS_ERROR", details)
        self.request_id = request_id


class AnalysisTimeoutError(AnalysisError):
    """Analysis timed out."""

    def __init__(
        self,
        request_id: str,
        timeout_ms: int,
        files_analyzed: int = 0,
    ):
        super().__init__(
            f"Analysis timed out after {timeout_ms}ms ({files_analyzed} files analyzed)",
            request_id=request_id,
        )
        self.error_code = "ANALYSIS_TIMEOUT"
        self.timeout_ms = timeout_ms
        self.files_analyzed = files_analyzed


class AnalysisCancelledError(AnalysisError):
    """Analysis was cancelled."""

    def __init__(self, request_id: str, reason: Optional[str] = None):
        msg = f"Analysis cancelled: {request_id}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg, request_id=request_id)
        self.error_code = "ANALYSIS_CANCELLED"


class FileTooLargeError(AnalysisError):
    """File exceeds maximum size for analysis."""

    def __init__(self, file_path: str, size_bytes: int, max_bytes: int):
        super().__init__(
            f"File too large for analysis: {file_path} ({size_bytes} > {max_bytes} bytes)"
        )
        self.error_code = "FILE_TOO_LARGE"
        self.file_path = file_path
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes


class TooManyFilesError(AnalysisError):
    """Request contains too many files."""

    def __init__(self, file_count: int, max_files: int):
        super().__init__(f"Too many files in request: {file_count} > {max_files}")
        self.error_code = "TOO_MANY_FILES"
        self.file_count = file_count
        self.max_files = max_files


class UnsupportedLanguageError(AnalysisError):
    """Language is not supported for analysis."""

    def __init__(self, language: str, file_path: str):
        super().__init__(f"Unsupported language '{language}' for file: {file_path}")
        self.error_code = "UNSUPPORTED_LANGUAGE"
        self.language = language
        self.file_path = file_path


class ASTParseError(AnalysisError):
    """Failed to parse file into AST."""

    def __init__(
        self,
        file_path: str,
        language: str,
        reason: Optional[str] = None,
    ):
        msg = f"Failed to parse {file_path} ({language})"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
        self.error_code = "AST_PARSE_ERROR"
        self.file_path = file_path
        self.language = language


class RuleEvaluationError(AnalysisError):
    """Failed to evaluate security rule."""

    def __init__(self, rule_id: str, reason: str):
        super().__init__(f"Failed to evaluate rule {rule_id}: {reason}")
        self.error_code = "RULE_EVALUATION_ERROR"
        self.rule_id = rule_id


class IncrementalScanError(AnalysisError):
    """Error during incremental diff scanning."""

    def __init__(
        self,
        base_sha: str,
        head_sha: str,
        reason: str,
    ):
        super().__init__(f"Incremental scan failed ({base_sha}..{head_sha}): {reason}")
        self.error_code = "INCREMENTAL_SCAN_ERROR"
        self.base_sha = base_sha
        self.head_sha = head_sha


# ============================================================================
# Worker Errors
# ============================================================================


class WorkerError(StreamingError):
    """Base exception for worker operations."""

    def __init__(
        self,
        message: str,
        worker_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "WORKER_ERROR", details)
        self.worker_id = worker_id


class WorkerTimeoutError(WorkerError):
    """Worker task timed out."""

    def __init__(self, worker_id: str, task_id: str, timeout_ms: int):
        super().__init__(
            f"Worker {worker_id} timed out on task {task_id} after {timeout_ms}ms",
            worker_id=worker_id,
        )
        self.error_code = "WORKER_TIMEOUT"
        self.task_id = task_id
        self.timeout_ms = timeout_ms


class WorkerHealthCheckError(WorkerError):
    """Worker health check failed."""

    def __init__(self, worker_id: str, reason: str):
        super().__init__(
            f"Worker {worker_id} health check failed: {reason}",
            worker_id=worker_id,
        )
        self.error_code = "WORKER_HEALTH_CHECK_FAILED"


class NoAvailableWorkersError(WorkerError):
    """No workers available to process request."""

    def __init__(self):
        super().__init__("No workers available to process request")
        self.error_code = "NO_AVAILABLE_WORKERS"


class WorkerPoolExhaustedError(WorkerError):
    """Worker pool is exhausted."""

    def __init__(self, active_workers: int, max_workers: int):
        super().__init__(
            f"Worker pool exhausted: {active_workers}/{max_workers} workers active"
        )
        self.error_code = "WORKER_POOL_EXHAUSTED"
        self.active_workers = active_workers
        self.max_workers = max_workers


# ============================================================================
# CI/CD Notification Errors
# ============================================================================


class NotificationError(StreamingError):
    """Base exception for CI/CD notification operations."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "NOTIFICATION_ERROR", details)
        self.provider = provider


class NotificationDeliveryError(NotificationError):
    """Failed to deliver notification to CI/CD system."""

    def __init__(
        self,
        provider: str,
        target: str,
        reason: str,
    ):
        super().__init__(
            f"Failed to deliver notification to {provider} ({target}): {reason}",
            provider=provider,
        )
        self.error_code = "NOTIFICATION_DELIVERY_ERROR"
        self.target = target


class WebhookValidationError(NotificationError):
    """Webhook payload validation failed."""

    def __init__(self, provider: str, reason: str):
        super().__init__(
            f"Invalid webhook payload from {provider}: {reason}",
            provider=provider,
        )
        self.error_code = "WEBHOOK_VALIDATION_ERROR"


class WebhookSignatureError(NotificationError):
    """Webhook signature verification failed."""

    def __init__(self, provider: str):
        super().__init__(
            f"Invalid webhook signature from {provider}",
            provider=provider,
        )
        self.error_code = "WEBHOOK_SIGNATURE_ERROR"


class UnsupportedCIProviderError(NotificationError):
    """CI/CD provider is not supported."""

    def __init__(self, provider: str):
        super().__init__(
            f"Unsupported CI/CD provider: {provider}",
            provider=provider,
        )
        self.error_code = "UNSUPPORTED_CI_PROVIDER"


class RateLimitedError(NotificationError):
    """CI/CD API rate limited."""

    def __init__(
        self,
        provider: str,
        retry_after_seconds: int = 60,
    ):
        super().__init__(
            f"Rate limited by {provider} API",
            provider=provider,
        )
        self.error_code = "RATE_LIMITED"
        self.retry_after_seconds = retry_after_seconds


# ============================================================================
# Repository Errors
# ============================================================================


class RepositoryError(StreamingError):
    """Base exception for repository operations."""

    def __init__(
        self,
        message: str,
        repository_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "REPOSITORY_ERROR", details)
        self.repository_id = repository_id


class RepositoryNotFoundError(RepositoryError):
    """Repository not found."""

    def __init__(self, repository_id: str):
        super().__init__(
            f"Repository not found: {repository_id}",
            repository_id=repository_id,
        )
        self.error_code = "REPOSITORY_NOT_FOUND"


class CommitNotFoundError(RepositoryError):
    """Commit not found in repository."""

    def __init__(self, repository_id: str, commit_sha: str):
        super().__init__(
            f"Commit not found: {commit_sha} in {repository_id}",
            repository_id=repository_id,
        )
        self.error_code = "COMMIT_NOT_FOUND"
        self.commit_sha = commit_sha


class DiffNotAvailableError(RepositoryError):
    """Diff between commits not available."""

    def __init__(
        self,
        repository_id: str,
        base_sha: str,
        head_sha: str,
    ):
        super().__init__(
            f"Diff not available: {base_sha}..{head_sha} in {repository_id}",
            repository_id=repository_id,
        )
        self.error_code = "DIFF_NOT_AVAILABLE"
        self.base_sha = base_sha
        self.head_sha = head_sha


class RepositoryAccessDeniedError(RepositoryError):
    """Access to repository denied."""

    def __init__(self, repository_id: str):
        super().__init__(
            f"Access denied to repository: {repository_id}",
            repository_id=repository_id,
        )
        self.error_code = "REPOSITORY_ACCESS_DENIED"
