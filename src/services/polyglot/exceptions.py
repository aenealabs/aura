"""
Project Aura - Polyglot Dependency Graph Exceptions

Custom exceptions for dependency graph operations including
Neptune errors, indexing errors, and query errors.

Based on ADR-079: Scale & AI Model Security
"""

from typing import Any, Optional


class PolyglotError(Exception):
    """Base exception for all polyglot service errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "POLYGLOT_ERROR"
        self.details = details or {}


# ============================================================================
# Neptune Errors
# ============================================================================


class NeptuneError(PolyglotError):
    """Base exception for Neptune operations."""

    def __init__(
        self,
        message: str,
        cluster: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "NEPTUNE_ERROR", details)
        self.cluster = cluster


class NeptuneConnectionError(NeptuneError):
    """Failed to connect to Neptune."""

    def __init__(self, endpoint: str, reason: Optional[str] = None):
        msg = f"Failed to connect to Neptune: {endpoint}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)
        self.error_code = "NEPTUNE_CONNECTION_ERROR"
        self.endpoint = endpoint


class NeptuneQueryError(NeptuneError):
    """Neptune query failed."""

    def __init__(
        self,
        query_id: str,
        reason: str,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            f"Neptune query failed: {query_id} - {reason}",
            details=details,
        )
        self.error_code = "NEPTUNE_QUERY_ERROR"
        self.query_id = query_id


class NeptuneTimeoutError(NeptuneError):
    """Neptune query timed out."""

    def __init__(self, query_id: str, timeout_ms: int):
        super().__init__(f"Neptune query timed out after {timeout_ms}ms: {query_id}")
        self.error_code = "NEPTUNE_TIMEOUT"
        self.query_id = query_id
        self.timeout_ms = timeout_ms


class NeptuneCapacityError(NeptuneError):
    """Neptune cluster at capacity."""

    def __init__(self, cluster: str):
        super().__init__(
            f"Neptune cluster at capacity: {cluster}",
            cluster=cluster,
        )
        self.error_code = "NEPTUNE_CAPACITY_ERROR"


class NeptuneThrottlingError(NeptuneError):
    """Neptune request was throttled."""

    def __init__(self, retry_after_ms: int = 1000):
        super().__init__("Neptune request throttled")
        self.error_code = "NEPTUNE_THROTTLED"
        self.retry_after_ms = retry_after_ms


# ============================================================================
# Shard Errors
# ============================================================================


class ShardError(PolyglotError):
    """Base exception for shard operations."""

    def __init__(
        self,
        message: str,
        shard_id: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "SHARD_ERROR", details)
        self.shard_id = shard_id


class ShardNotFoundError(ShardError):
    """Shard not found."""

    def __init__(self, shard_id: int):
        super().__init__(f"Shard not found: {shard_id}", shard_id=shard_id)
        self.error_code = "SHARD_NOT_FOUND"


class ShardUnavailableError(ShardError):
    """Shard is unavailable."""

    def __init__(self, shard_id: int, reason: Optional[str] = None):
        msg = f"Shard unavailable: {shard_id}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg, shard_id=shard_id)
        self.error_code = "SHARD_UNAVAILABLE"


class ShardRoutingError(ShardError):
    """Failed to route query to shard."""

    def __init__(self, repository_id: str, reason: str):
        super().__init__(f"Failed to route query for {repository_id}: {reason}")
        self.error_code = "SHARD_ROUTING_ERROR"
        self.repository_id = repository_id


class FederatedQueryError(ShardError):
    """Federated query across shards failed."""

    def __init__(
        self,
        query_id: str,
        failed_shards: list[int],
        reason: str,
    ):
        super().__init__(
            f"Federated query {query_id} failed on shards {failed_shards}: {reason}"
        )
        self.error_code = "FEDERATED_QUERY_ERROR"
        self.query_id = query_id
        self.failed_shards = failed_shards


# ============================================================================
# Indexing Errors
# ============================================================================


class IndexingError(PolyglotError):
    """Base exception for indexing operations."""

    def __init__(
        self,
        message: str,
        repository_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "INDEXING_ERROR", details)
        self.repository_id = repository_id


class RepositoryNotIndexedError(IndexingError):
    """Repository has not been indexed."""

    def __init__(self, repository_id: str):
        super().__init__(
            f"Repository not indexed: {repository_id}",
            repository_id=repository_id,
        )
        self.error_code = "REPOSITORY_NOT_INDEXED"


class IndexingInProgressError(IndexingError):
    """Repository is currently being indexed."""

    def __init__(self, repository_id: str, progress: float = 0.0):
        super().__init__(
            f"Repository indexing in progress: {repository_id} ({progress:.1f}%)",
            repository_id=repository_id,
        )
        self.error_code = "INDEXING_IN_PROGRESS"
        self.progress = progress


class IndexingFailedError(IndexingError):
    """Repository indexing failed."""

    def __init__(
        self,
        repository_id: str,
        reason: str,
        partial_results: bool = False,
    ):
        super().__init__(
            f"Indexing failed for {repository_id}: {reason}",
            repository_id=repository_id,
        )
        self.error_code = "INDEXING_FAILED"
        self.partial_results = partial_results


class FileTooLargeError(IndexingError):
    """File exceeds maximum size for indexing."""

    def __init__(self, file_path: str, size_bytes: int, max_bytes: int):
        super().__init__(
            f"File too large for indexing: {file_path} ({size_bytes} > {max_bytes} bytes)"
        )
        self.error_code = "FILE_TOO_LARGE"
        self.file_path = file_path
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes


class TooManyFilesError(IndexingError):
    """Repository has too many files."""

    def __init__(self, repository_id: str, file_count: int, max_files: int):
        super().__init__(
            f"Repository has too many files: {file_count} > {max_files}",
            repository_id=repository_id,
        )
        self.error_code = "TOO_MANY_FILES"
        self.file_count = file_count
        self.max_files = max_files


class UnsupportedLanguageError(IndexingError):
    """Language is not supported for indexing."""

    def __init__(self, language: str, file_path: Optional[str] = None):
        msg = f"Unsupported language: {language}"
        if file_path:
            msg += f" (file: {file_path})"
        super().__init__(msg)
        self.error_code = "UNSUPPORTED_LANGUAGE"
        self.language = language
        self.file_path = file_path


class ParseError(IndexingError):
    """Failed to parse source file."""

    def __init__(
        self,
        file_path: str,
        language: str,
        line: Optional[int] = None,
        reason: Optional[str] = None,
    ):
        msg = f"Failed to parse {file_path} ({language})"
        if line:
            msg += f" at line {line}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
        self.error_code = "PARSE_ERROR"
        self.file_path = file_path
        self.language = language
        self.line = line


# ============================================================================
# Entity Errors
# ============================================================================


class EntityError(PolyglotError):
    """Base exception for entity operations."""

    def __init__(
        self,
        message: str,
        entity_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "ENTITY_ERROR", details)
        self.entity_id = entity_id


class EntityNotFoundError(EntityError):
    """Entity not found in graph."""

    def __init__(self, entity_id: str):
        super().__init__(f"Entity not found: {entity_id}", entity_id=entity_id)
        self.error_code = "ENTITY_NOT_FOUND"


class DuplicateEntityError(EntityError):
    """Entity already exists."""

    def __init__(self, entity_id: str, qualified_name: str):
        super().__init__(
            f"Entity already exists: {qualified_name} (id: {entity_id})",
            entity_id=entity_id,
        )
        self.error_code = "DUPLICATE_ENTITY"
        self.qualified_name = qualified_name


class InvalidEntityError(EntityError):
    """Entity data is invalid."""

    def __init__(self, entity_id: str, reason: str):
        super().__init__(
            f"Invalid entity {entity_id}: {reason}",
            entity_id=entity_id,
        )
        self.error_code = "INVALID_ENTITY"


# ============================================================================
# Dependency Errors
# ============================================================================


class DependencyError(PolyglotError):
    """Base exception for dependency operations."""

    def __init__(
        self,
        message: str,
        package_name: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "DEPENDENCY_ERROR", details)
        self.package_name = package_name


class PackageNotFoundError(DependencyError):
    """Package not found in ecosystem."""

    def __init__(self, package_name: str, ecosystem: str):
        super().__init__(
            f"Package not found: {package_name} in {ecosystem}",
            package_name=package_name,
        )
        self.error_code = "PACKAGE_NOT_FOUND"
        self.ecosystem = ecosystem


class VersionNotFoundError(DependencyError):
    """Package version not found."""

    def __init__(self, package_name: str, version: str, ecosystem: str):
        super().__init__(
            f"Version not found: {package_name}@{version} in {ecosystem}",
            package_name=package_name,
        )
        self.error_code = "VERSION_NOT_FOUND"
        self.version = version
        self.ecosystem = ecosystem


class CyclicDependencyError(DependencyError):
    """Cyclic dependency detected."""

    def __init__(self, cycle: list[str]):
        cycle_str = " -> ".join(cycle)
        super().__init__(f"Cyclic dependency detected: {cycle_str}")
        self.error_code = "CYCLIC_DEPENDENCY"
        self.cycle = cycle


class DependencyResolutionError(DependencyError):
    """Failed to resolve dependencies."""

    def __init__(
        self,
        package_name: str,
        reason: str,
        conflicts: Optional[list[str]] = None,
    ):
        super().__init__(
            f"Failed to resolve dependencies for {package_name}: {reason}",
            package_name=package_name,
        )
        self.error_code = "DEPENDENCY_RESOLUTION_ERROR"
        self.conflicts = conflicts or []


# ============================================================================
# Impact Analysis Errors
# ============================================================================


class ImpactAnalysisError(PolyglotError):
    """Base exception for impact analysis operations."""

    def __init__(
        self,
        message: str,
        analysis_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "IMPACT_ANALYSIS_ERROR", details)
        self.analysis_id = analysis_id


class AnalysisTimeoutError(ImpactAnalysisError):
    """Impact analysis timed out."""

    def __init__(self, analysis_id: str, timeout_ms: int, depth_reached: int):
        super().__init__(
            f"Impact analysis timed out after {timeout_ms}ms at depth {depth_reached}",
            analysis_id=analysis_id,
        )
        self.error_code = "ANALYSIS_TIMEOUT"
        self.timeout_ms = timeout_ms
        self.depth_reached = depth_reached


class AnalysisDepthExceededError(ImpactAnalysisError):
    """Impact analysis exceeded maximum depth."""

    def __init__(self, analysis_id: str, max_depth: int):
        super().__init__(
            f"Impact analysis exceeded max depth of {max_depth}",
            analysis_id=analysis_id,
        )
        self.error_code = "ANALYSIS_DEPTH_EXCEEDED"
        self.max_depth = max_depth


class TooManyAffectedEntitiesError(ImpactAnalysisError):
    """Too many entities affected by change."""

    def __init__(
        self,
        analysis_id: str,
        affected_count: int,
        max_count: int,
    ):
        super().__init__(
            f"Too many affected entities: {affected_count} > {max_count}",
            analysis_id=analysis_id,
        )
        self.error_code = "TOO_MANY_AFFECTED_ENTITIES"
        self.affected_count = affected_count
        self.max_count = max_count


# ============================================================================
# Vulnerability Errors
# ============================================================================


class VulnerabilityError(PolyglotError):
    """Base exception for vulnerability operations."""

    def __init__(
        self,
        message: str,
        vulnerability_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message, "VULNERABILITY_ERROR", details)
        self.vulnerability_id = vulnerability_id


class VulnerabilityNotFoundError(VulnerabilityError):
    """Vulnerability not found."""

    def __init__(self, vulnerability_id: str):
        super().__init__(
            f"Vulnerability not found: {vulnerability_id}",
            vulnerability_id=vulnerability_id,
        )
        self.error_code = "VULNERABILITY_NOT_FOUND"


class VulnerabilityDatabaseError(VulnerabilityError):
    """Error accessing vulnerability database."""

    def __init__(self, source: str, reason: str):
        super().__init__(f"Vulnerability database error ({source}): {reason}")
        self.error_code = "VULNERABILITY_DB_ERROR"
        self.source = source
