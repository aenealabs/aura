"""Custom exceptions for Constitutional AI.

This module defines all exception classes used by the Constitutional AI system
to handle various error conditions during critique and revision operations.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.services.constitutional_ai.models import CritiqueResult


class ConstitutionalAIError(Exception):
    """Base exception for all Constitutional AI errors.

    All custom exceptions in this module inherit from this class,
    allowing callers to catch all constitutional AI errors with a
    single except clause.

    Attributes:
        message: Human-readable error description
        details: Additional context about the error
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description
            details: Additional context about the error
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary representation.

        Returns:
            Dictionary with error type, message, and details
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class ConstitutionLoadError(ConstitutionalAIError):
    """Raised when the constitution YAML file cannot be loaded.

    This error occurs when:
    - The constitution file doesn't exist
    - The file contains invalid YAML syntax
    - Required fields are missing from the constitution
    """

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        parse_error: Optional[str] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description
            file_path: Path to the constitution file that failed to load
            parse_error: Specific parsing error message if applicable
        """
        details = {}
        if file_path:
            details["file_path"] = file_path
        if parse_error:
            details["parse_error"] = parse_error
        super().__init__(message, details)
        self.file_path = file_path
        self.parse_error = parse_error


class PrincipleValidationError(ConstitutionalAIError):
    """Raised when a constitutional principle fails validation.

    This error occurs when:
    - Required fields are missing from a principle
    - Field values are invalid (e.g., unknown severity)
    - Prompt templates are malformed
    """

    def __init__(
        self,
        message: str,
        principle_id: Optional[str] = None,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description
            principle_id: ID of the principle that failed validation
            field_name: Name of the field that failed validation
            field_value: Invalid value that was provided
        """
        details = {}
        if principle_id:
            details["principle_id"] = principle_id
        if field_name:
            details["field_name"] = field_name
        if field_value is not None:
            details["field_value"] = str(field_value)
        super().__init__(message, details)
        self.principle_id = principle_id
        self.field_name = field_name
        self.field_value = field_value


class CritiqueTimeoutError(ConstitutionalAIError):
    """Raised when critique evaluation times out.

    This error occurs when the LLM takes too long to respond
    during batch critique evaluation. The timeout is configurable
    and defaults to 30 seconds per batch.

    Attributes:
        timeout_seconds: The timeout that was exceeded
        batch_size: Number of principles in the batch
        principles_evaluated: Principles that were being evaluated
    """

    def __init__(
        self,
        message: str,
        timeout_seconds: float,
        batch_size: int = 0,
        principles_evaluated: Optional[List[str]] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description
            timeout_seconds: The timeout that was exceeded
            batch_size: Number of principles in the batch
            principles_evaluated: List of principle IDs being evaluated
        """
        details = {
            "timeout_seconds": timeout_seconds,
            "batch_size": batch_size,
        }
        if principles_evaluated:
            details["principles_evaluated"] = principles_evaluated
        super().__init__(message, details)
        self.timeout_seconds = timeout_seconds
        self.batch_size = batch_size
        self.principles_evaluated = principles_evaluated or []


class CritiqueParseError(ConstitutionalAIError):
    """Raised when LLM response cannot be parsed into critique results.

    This error occurs when:
    - The LLM response format is unexpected
    - Required fields are missing from the response
    - JSON parsing fails for structured responses
    """

    def __init__(
        self,
        message: str,
        raw_response: Optional[str] = None,
        principle_id: Optional[str] = None,
        parse_error: Optional[str] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description
            raw_response: The raw LLM response that failed to parse
            principle_id: ID of the principle being evaluated
            parse_error: Specific parsing error message
        """
        details = {}
        if raw_response:
            # Truncate long responses to avoid huge error messages
            details["raw_response"] = raw_response[:500] + (
                "..." if len(raw_response) > 500 else ""
            )
        if principle_id:
            details["principle_id"] = principle_id
        if parse_error:
            details["parse_error"] = parse_error
        super().__init__(message, details)
        self.raw_response = raw_response
        self.principle_id = principle_id
        self.parse_error = parse_error


class RevisionConvergenceError(ConstitutionalAIError):
    """Raised when revision fails to resolve all critical issues.

    This error occurs when the maximum number of revision iterations
    is reached but critical issues remain unresolved. This typically
    indicates a fundamental conflict between principles or an output
    that cannot be safely corrected.

    Attributes:
        max_iterations: Maximum iterations that were attempted
        remaining_issues: Critical issues that remain unresolved
    """

    def __init__(
        self,
        message: str,
        max_iterations: int,
        remaining_issues: Optional[List["CritiqueResult"]] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description
            max_iterations: Maximum iterations that were attempted
            remaining_issues: Critical issues that remain unresolved
        """
        details = {"max_iterations": max_iterations}
        if remaining_issues:
            details["remaining_issue_count"] = len(remaining_issues)
            details["remaining_issue_ids"] = [
                issue.principle_id for issue in remaining_issues
            ]
        super().__init__(message, details)
        self.max_iterations = max_iterations
        self.remaining_issues = remaining_issues or []


class HITLRequiredError(ConstitutionalAIError):
    """Raised when human-in-the-loop review is required.

    This error occurs when:
    - Critical issues cannot be resolved automatically
    - Revision reaches maximum iterations with critical issues
    - Configured failure policy requires HITL for this scenario

    The remaining_issues attribute contains the unresolved critiques
    that require human review.

    Attributes:
        remaining_issues: List of unresolved critique results
        revision_iterations: Number of revision iterations attempted
    """

    def __init__(
        self,
        message: str,
        remaining_issues: List["CritiqueResult"],
        revision_iterations: int = 0,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description
            remaining_issues: List of unresolved critique results
            revision_iterations: Number of revision iterations attempted
        """
        details = {
            "remaining_issue_count": len(remaining_issues),
            "remaining_issue_ids": [issue.principle_id for issue in remaining_issues],
            "revision_iterations": revision_iterations,
        }
        super().__init__(message, details)
        self.remaining_issues = remaining_issues
        self.revision_iterations = revision_iterations


class LLMServiceError(ConstitutionalAIError):
    """Raised when the LLM service encounters an error.

    This wraps errors from the underlying Bedrock LLM service
    to provide constitutional AI-specific context.

    Attributes:
        original_error: The underlying error from the LLM service
        operation: The operation that was being performed
    """

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        operation: Optional[str] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description
            original_error: The underlying error from the LLM service
            operation: The operation that was being performed
        """
        details = {}
        if original_error:
            details["original_error_type"] = type(original_error).__name__
            details["original_error_message"] = str(original_error)
        if operation:
            details["operation"] = operation
        super().__init__(message, details)
        self.original_error = original_error
        self.operation = operation


class AuditTrailError(ConstitutionalAIError):
    """Raised when audit trail logging fails.

    This error occurs when required audit logging cannot be completed
    and the failure_config specifies that audit failures should block
    execution.

    Attributes:
        audit_record: The audit record that failed to log
        original_error: The underlying logging error
    """

    def __init__(
        self,
        message: str,
        audit_record: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description
            audit_record: The audit record that failed to log
            original_error: The underlying logging error
        """
        details = {}
        if original_error:
            details["original_error_type"] = type(original_error).__name__
            details["original_error_message"] = str(original_error)
        super().__init__(message, details)
        self.audit_record = audit_record
        self.original_error = original_error
