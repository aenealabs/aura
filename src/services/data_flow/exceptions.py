"""
Data Flow Exception Definitions
================================

ADR-056 Phase 3: Data Flow Analysis

Custom exceptions for data flow analysis operations.
"""

from typing import Any


class DataFlowError(Exception):
    """Base exception for data flow analysis operations.

    All data flow exceptions inherit from this base class,
    enabling broad exception handling when needed.

    Attributes:
        message: Error message
        details: Additional error details
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize DataFlowError.

        Args:
            message: Error message
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConnectionParseError(DataFlowError):
    """Exception raised when parsing connection strings fails.

    Raised when:
    - Database connection string is malformed
    - Queue URL/ARN cannot be parsed
    - API endpoint URL is invalid

    Attributes:
        source_file: File containing the connection
        line_number: Line number where parse failed
        connection_type: Type of connection (database, queue, api)
    """

    def __init__(
        self,
        message: str,
        source_file: str | None = None,
        line_number: int | None = None,
        connection_type: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ConnectionParseError.

        Args:
            message: Error message
            source_file: File path
            line_number: Line number
            connection_type: Type of connection
            details: Additional details
        """
        super().__init__(message, details)
        self.source_file = source_file
        self.line_number = line_number
        self.connection_type = connection_type


class PIIDetectionError(DataFlowError):
    """Exception raised when PII detection fails.

    Raised when:
    - Pattern matching fails
    - Classification cannot be determined
    - Compliance tagging errors

    Attributes:
        field_name: Field that caused the error
        source_file: File containing the field
        detection_stage: Stage of detection that failed
    """

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        source_file: str | None = None,
        detection_stage: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize PIIDetectionError.

        Args:
            message: Error message
            field_name: Name of field
            source_file: File path
            detection_stage: Detection stage
            details: Additional details
        """
        super().__init__(message, details)
        self.field_name = field_name
        self.source_file = source_file
        self.detection_stage = detection_stage


class FlowAnalysisError(DataFlowError):
    """Exception raised when data flow analysis fails.

    Raised when:
    - Flow tracing encounters cycles
    - Entity resolution fails
    - Cross-boundary analysis errors

    Attributes:
        source_entity: Source of the flow
        target_entity: Target of the flow
        flow_type: Type of flow being analyzed
        reason: Specific reason for failure
    """

    def __init__(
        self,
        message: str,
        source_entity: str | None = None,
        target_entity: str | None = None,
        flow_type: str | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize FlowAnalysisError.

        Args:
            message: Error message
            source_entity: Source entity
            target_entity: Target entity
            flow_type: Type of flow
            reason: Failure reason
            details: Additional details
        """
        super().__init__(message, details)
        self.source_entity = source_entity
        self.target_entity = target_entity
        self.flow_type = flow_type
        self.reason = reason


class ReportGenerationError(DataFlowError):
    """Exception raised when report generation fails.

    Raised when:
    - Diagram rendering fails
    - Template processing errors
    - Export format not supported

    Attributes:
        report_section: Section that failed
        export_format: Format being generated
        reason: Specific reason for failure
    """

    def __init__(
        self,
        message: str,
        report_section: str | None = None,
        export_format: str | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ReportGenerationError.

        Args:
            message: Error message
            report_section: Report section
            export_format: Export format
            reason: Failure reason
            details: Additional details
        """
        super().__init__(message, details)
        self.report_section = report_section
        self.export_format = export_format
        self.reason = reason
