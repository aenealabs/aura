"""
Project Aura - Streaming Analysis Service Contracts

Data models and enums for real-time CI/CD security analysis
with sub-second feedback at billion-line scale.

Based on ADR-079: Scale & AI Model Security
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class AnalysisScope(str, Enum):
    """Scope of streaming analysis."""

    INCREMENTAL = "incremental"  # Only changed files
    AFFECTED = "affected"  # Changed + dependent files
    FULL = "full"  # Complete repository


class FeedbackType(str, Enum):
    """Types of real-time feedback."""

    VULNERABILITY = "vulnerability"
    CODE_SMELL = "code_smell"
    SECURITY_HOTSPOT = "security_hotspot"
    LICENSE_ISSUE = "license_issue"
    DEPENDENCY_ISSUE = "dependency_issue"
    SECRET_DETECTED = "secret_detected"
    COMPLIANCE_VIOLATION = "compliance_violation"
    PERFORMANCE_ISSUE = "performance_issue"


class FeedbackSeverity(str, Enum):
    """Severity levels for feedback."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CIProvider(str, Enum):
    """Supported CI/CD providers."""

    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    JENKINS = "jenkins"
    AWS_CODEBUILD = "aws_codebuild"
    AZURE_DEVOPS = "azure_devops"
    CIRCLECI = "circleci"
    BITBUCKET = "bitbucket"


class AnalysisStatus(str, Enum):
    """Status of streaming analysis."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class CacheStatus(str, Enum):
    """Cache hit/miss status."""

    HIT = "hit"
    MISS = "miss"
    PARTIAL = "partial"
    STALE = "stale"


class DiffType(str, Enum):
    """Types of file changes in a diff."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    COPIED = "copied"


@dataclass
class FileChange:
    """Represents a changed file in a commit."""

    file_path: str
    diff_type: DiffType
    old_path: Optional[str] = None  # For renames
    additions: int = 0
    deletions: int = 0
    content_hash: Optional[str] = None
    language: Optional[str] = None


@dataclass
class StreamingAnalysisRequest:
    """Request for streaming analysis."""

    request_id: str
    repository_id: str
    commit_sha: str
    base_sha: str  # For diff comparison
    changed_files: list[FileChange] = field(default_factory=list)
    analysis_scope: AnalysisScope = AnalysisScope.INCREMENTAL
    timeout_ms: int = 5000
    ci_provider: Optional[CIProvider] = None
    pull_request_id: Optional[str] = None
    branch_name: Optional[str] = None
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamingFeedback:
    """Real-time feedback item."""

    feedback_id: str
    type: FeedbackType
    severity: FeedbackSeverity
    file_path: str
    line_start: int
    line_end: int
    column_start: Optional[int] = None
    column_end: Optional[int] = None
    message: str = ""
    suggestion: Optional[str] = None
    rule_id: str = ""
    rule_name: Optional[str] = None
    cwe_id: Optional[str] = None  # Common Weakness Enumeration
    owasp_category: Optional[str] = None
    fix_available: bool = False
    fix_code: Optional[str] = None
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamingAnalysisResult:
    """Complete streaming analysis result."""

    result_id: str
    request_id: str
    repository_id: str
    commit_sha: str
    status: AnalysisStatus
    files_analyzed: int = 0
    total_feedback: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    latency_ms: int = 0
    feedback_items: list[StreamingFeedback] = field(default_factory=list)
    cache_status: CacheStatus = CacheStatus.MISS
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Check if analysis passed (no critical/high issues)."""
        return self.critical_count == 0 and self.high_count == 0


@dataclass
class ASTCacheEntry:
    """Cached AST for a file."""

    file_path: str
    content_hash: str
    language: str
    ast_data: dict[str, Any]
    symbols: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    cached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None


@dataclass
class EmbeddingCacheEntry:
    """Cached embedding for code."""

    file_path: str
    content_hash: str
    embedding: list[float] = field(default_factory=list)
    embedding_model: str = ""
    dimensions: int = 0
    cached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None


@dataclass
class IncrementalScanResult:
    """Result of incremental diff scanning."""

    scan_id: str
    repository_id: str
    base_sha: str
    head_sha: str
    files_scanned: int = 0
    lines_scanned: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    feedback_items: list[StreamingFeedback] = field(default_factory=list)
    scan_duration_ms: int = 0
    scanned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AffectedFile:
    """File affected by a change via dependency graph."""

    file_path: str
    reason: str  # Why this file is affected
    distance: int  # Hops from changed file
    dependency_chain: list[str] = field(default_factory=list)


@dataclass
class CIWebhookEvent:
    """Incoming CI/CD webhook event."""

    event_id: str
    provider: CIProvider
    event_type: str  # push, pull_request, etc.
    repository_id: str
    repository_url: str
    commit_sha: str
    base_sha: Optional[str] = None
    branch_name: Optional[str] = None
    pull_request_id: Optional[str] = None
    author: Optional[str] = None
    message: Optional[str] = None
    changed_files: list[str] = field(default_factory=list)
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class CINotification:
    """Notification to send back to CI/CD system."""

    notification_id: str
    provider: CIProvider
    repository_id: str
    commit_sha: str
    status: str  # success, failure, pending
    title: str
    summary: str
    annotations: list[dict[str, Any]] = field(default_factory=list)
    check_run_id: Optional[str] = None
    pull_request_id: Optional[str] = None
    target_url: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class StreamingMetrics:
    """Metrics for streaming analysis performance."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    total_files_analyzed: int = 0
    total_feedback_generated: int = 0
    cache_hit_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    throughput_per_minute: float = 0.0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


@dataclass
class SecurityRule:
    """Security rule for analysis."""

    rule_id: str
    name: str
    description: str
    severity: FeedbackSeverity
    feedback_type: FeedbackType
    enabled: bool = True
    languages: list[str] = field(default_factory=list)
    pattern: Optional[str] = None  # Regex pattern
    cwe_ids: list[str] = field(default_factory=list)
    owasp_categories: list[str] = field(default_factory=list)
    fix_template: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleSet:
    """Collection of security rules."""

    ruleset_id: str
    name: str
    description: str
    version: str
    rules: list[SecurityRule] = field(default_factory=list)
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None


@dataclass
class KinesisRecord:
    """Record for Kinesis stream."""

    record_id: str
    partition_key: str
    data: dict[str, Any]
    sequence_number: Optional[str] = None
    shard_id: Optional[str] = None
    approximate_arrival_timestamp: Optional[datetime] = None
