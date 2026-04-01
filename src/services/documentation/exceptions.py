"""
Documentation Agent Exception Hierarchy
========================================

Custom exceptions for the Documentation Agent service.
ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.

Exception Hierarchy:
    DocumentationAgentError (base)
    ├── GraphTraversalError - Neptune graph traversal failures
    ├── InsufficientDataError - Not enough data for confident generation
    ├── DiagramGenerationError - Diagram creation failures
    ├── ReportGenerationError - Report creation failures
    ├── CacheError - Caching layer failures
    └── LLMGenerationError - LLM service failures
"""

from typing import Any


class DocumentationAgentError(Exception):
    """Base exception for all Documentation Agent errors.

    Attributes:
        message: Human-readable error message
        details: Additional error details
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class GraphTraversalError(DocumentationAgentError):
    """Raised when Neptune graph traversal fails.

    This exception supports partial results, allowing the agent to
    continue with degraded functionality when some graph queries fail.

    Attributes:
        message: Human-readable error message
        partial_results: Results collected before the failure
        failed_query: The query that failed (if available)
        details: Additional error details
    """

    def __init__(
        self,
        message: str,
        partial_results: list[Any] | None = None,
        failed_query: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)
        self.partial_results = partial_results or []
        self.failed_query = failed_query

    @property
    def has_partial_results(self) -> bool:
        """Check if any partial results are available."""
        return len(self.partial_results) > 0


class InsufficientDataError(DocumentationAgentError):
    """Raised when there's not enough data for confident documentation.

    This exception includes the achieved confidence vs the required
    threshold, allowing callers to decide whether to proceed with
    lower confidence or abort.

    Attributes:
        message: Human-readable error message
        confidence: Achieved confidence score (0.0-1.0)
        threshold: Required confidence threshold
        missing_data: Description of what data is missing
        details: Additional error details
    """

    def __init__(
        self,
        message: str,
        confidence: float,
        threshold: float,
        missing_data: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)
        self.confidence = confidence
        self.threshold = threshold
        self.missing_data = missing_data

    @property
    def confidence_gap(self) -> float:
        """Calculate the gap between achieved and required confidence."""
        return self.threshold - self.confidence

    def __str__(self) -> str:
        base = (
            f"{self.message} (confidence: {self.confidence:.2f}, "
            f"threshold: {self.threshold:.2f})"
        )
        if self.missing_data:
            base += f" - Missing: {self.missing_data}"
        return base


class DiagramGenerationError(DocumentationAgentError):
    """Raised when diagram generation fails.

    This exception can contain component-level errors to help
    identify which parts of the diagram failed to generate.

    Attributes:
        message: Human-readable error message
        diagram_type: Type of diagram that failed to generate
        component_errors: Dict of component_id -> error message
        partial_diagram: Partial Mermaid code if available
        details: Additional error details
    """

    def __init__(
        self,
        message: str,
        diagram_type: str | None = None,
        component_errors: dict[str, str] | None = None,
        partial_diagram: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)
        self.diagram_type = diagram_type
        self.component_errors = component_errors or {}
        self.partial_diagram = partial_diagram

    @property
    def failed_components(self) -> list[str]:
        """Get list of component IDs that failed."""
        return list(self.component_errors.keys())

    @property
    def has_partial_diagram(self) -> bool:
        """Check if a partial diagram is available."""
        return self.partial_diagram is not None and len(self.partial_diagram) > 0


class ReportGenerationError(DocumentationAgentError):
    """Raised when technical report generation fails.

    Attributes:
        message: Human-readable error message
        section: The section that failed to generate
        partial_report: Partial report content if available
        details: Additional error details
    """

    def __init__(
        self,
        message: str,
        section: str | None = None,
        partial_report: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)
        self.section = section
        self.partial_report = partial_report

    @property
    def has_partial_report(self) -> bool:
        """Check if a partial report is available."""
        return self.partial_report is not None and len(self.partial_report) > 0


class CacheError(DocumentationAgentError):
    """Raised when caching operations fail.

    Cache errors are typically non-fatal - operations can continue
    without caching, just with reduced performance.

    Attributes:
        message: Human-readable error message
        cache_tier: Which cache tier failed (memory, redis, s3)
        operation: The operation that failed (get, set, delete)
        cache_key: The key that was being accessed
        details: Additional error details
    """

    def __init__(
        self,
        message: str,
        cache_tier: str | None = None,
        operation: str | None = None,
        cache_key: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)
        self.cache_tier = cache_tier
        self.operation = operation
        self.cache_key = cache_key


class LLMGenerationError(DocumentationAgentError):
    """Raised when LLM-based generation fails.

    Attributes:
        message: Human-readable error message
        model: The LLM model that failed
        prompt_tokens: Number of tokens in the prompt
        is_rate_limited: Whether this was a rate limit error
        is_context_exceeded: Whether context window was exceeded
        details: Additional error details
    """

    def __init__(
        self,
        message: str,
        model: str | None = None,
        prompt_tokens: int | None = None,
        is_rate_limited: bool = False,
        is_context_exceeded: bool = False,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.is_rate_limited = is_rate_limited
        self.is_context_exceeded = is_context_exceeded

    @property
    def is_retryable(self) -> bool:
        """Check if this error might be resolved by retrying."""
        return self.is_rate_limited and not self.is_context_exceeded
