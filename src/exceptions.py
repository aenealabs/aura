"""
Project Aura - Centralized Exception Hierarchy

This module defines the base exception hierarchy for consistent error handling
across the entire Project Aura codebase. All custom exceptions should inherit
from AuraError or one of its subclasses.

Exception Hierarchy:
    AuraError (base)
    ├── ValidationError - Invalid input, parameter, or data format
    ├── ServiceError - External service failures (AWS, databases, APIs)
    │   ├── DatabaseError - Neptune, DynamoDB, OpenSearch failures
    │   ├── LLMError - Bedrock, model invocation failures
    │   └── IntegrationError - Third-party API failures
    ├── SecurityError - Authentication, authorization, injection attempts
    │   ├── AuthenticationError - Login, token validation failures
    │   ├── AuthorizationError - Permission denied
    │   └── InjectionError - Prompt injection, XSS, SQL injection detected
    ├── ConfigurationError - Missing or invalid configuration
    ├── AgentError - Agent execution failures
    │   ├── ToolExecutionError - Agent tool invocation failures
    │   └── OrchestrationError - Agent coordination failures
    └── WorkflowError - Business workflow failures
        ├── ApprovalError - HITL approval workflow failures
        └── SandboxError - Sandbox provisioning/testing failures

Usage:
    from src.exceptions import ValidationError, ServiceError

    def process_input(data: dict) -> None:
        if not data.get("required_field"):
            raise ValidationError(
                message="Missing required field",
                field="required_field",
                context={"received_keys": list(data.keys())}
            )

Security Note:
    - Never include sensitive data (passwords, tokens, PII) in exception messages
    - Use context dict for debugging but sanitize before logging
    - Log full context only at DEBUG level, sanitized at ERROR level
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AuraError(Exception):
    """Base exception for all Project Aura errors.

    Attributes:
        message: Human-readable error description
        error_code: Optional machine-readable error code
        context: Additional debugging context (sanitize before exposing)
    """

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    def to_dict(self, include_context: bool = False) -> dict[str, Any]:
        """Convert exception to dictionary for API responses.

        Args:
            include_context: If True, include full context (DEBUG only)

        Returns:
            Dictionary safe for API response
        """
        result: dict[str, Any] = {
            "error": self.__class__.__name__,
            "message": self.message,
        }
        if self.error_code:
            result["code"] = self.error_code
        if include_context and self.context:
            result["context"] = self._sanitize_context()
        return result

    def _sanitize_context(self) -> dict[str, Any]:
        """Remove sensitive keys from context before exposing.

        Returns:
            Sanitized context dictionary
        """
        sensitive_keys = {
            "password",
            "token",
            "secret",
            "api_key",
            "authorization",
            "credential",
            "private_key",
            "access_key",
            "session",
        }
        return {
            k: "***REDACTED***" if any(s in k.lower() for s in sensitive_keys) else v
            for k, v in self.context.items()
        }

    def log(self, level: int = logging.ERROR) -> None:
        """Log this exception with appropriate context.

        Args:
            level: Logging level (default ERROR)
        """
        if level == logging.DEBUG:
            logger.log(level, "%s - Context: %s", self, self.context)
        else:
            logger.log(level, "%s - Context: %s", self, self._sanitize_context())


# =============================================================================
# Validation Errors
# =============================================================================


class ValidationError(AuraError):
    """Invalid input, parameter, or data format.

    Use for:
        - Missing required fields
        - Invalid data types
        - Out-of-range values
        - Malformed input formats
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        error_code: str = "VALIDATION_ERROR",
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if field:
            ctx["field"] = field
        super().__init__(message, error_code, ctx)
        self.field = field


class SchemaValidationError(ValidationError):
    """Schema validation failure (JSON Schema, Pydantic, etc)."""

    def __init__(
        self,
        message: str,
        schema_errors: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if schema_errors:
            ctx["schema_errors"] = schema_errors
        super().__init__(message, error_code="SCHEMA_VALIDATION_ERROR", context=ctx)


# =============================================================================
# Service Errors
# =============================================================================


class ServiceError(AuraError):
    """External service failures (AWS, databases, APIs).

    Use for:
        - Database connection failures
        - API timeouts
        - Service unavailable
        - Rate limiting
    """

    def __init__(
        self,
        message: str,
        service_name: str | None = None,
        error_code: str = "SERVICE_ERROR",
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if service_name:
            ctx["service"] = service_name
        super().__init__(message, error_code, ctx)
        self.service_name = service_name


class DatabaseError(ServiceError):
    """Neptune, DynamoDB, OpenSearch failures."""

    def __init__(
        self,
        message: str,
        database: str | None = None,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if operation:
            ctx["operation"] = operation
        super().__init__(
            message, service_name=database, error_code="DATABASE_ERROR", context=ctx
        )
        self.operation = operation


class LLMError(ServiceError):
    """Bedrock, model invocation failures."""

    def __init__(
        self,
        message: str,
        model_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if model_id:
            ctx["model_id"] = model_id
        super().__init__(
            message, service_name="bedrock", error_code="LLM_ERROR", context=ctx
        )
        self.model_id = model_id


class IntegrationError(ServiceError):
    """Third-party API failures (GitHub, Jira, etc)."""

    def __init__(
        self,
        message: str,
        integration: str | None = None,
        status_code: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if status_code:
            ctx["status_code"] = status_code
        super().__init__(
            message,
            service_name=integration,
            error_code="INTEGRATION_ERROR",
            context=ctx,
        )
        self.status_code = status_code


# =============================================================================
# Security Errors
# =============================================================================


class SecurityError(AuraError):
    """Authentication, authorization, injection attempts.

    Use for:
        - Login failures
        - Permission denied
        - Detected attack attempts
    """

    def __init__(
        self,
        message: str,
        error_code: str = "SECURITY_ERROR",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code, context)


class AuthenticationError(SecurityError):
    """Login, token validation failures."""

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, error_code="AUTHENTICATION_ERROR", context=context)


class AuthorizationError(SecurityError):
    """Permission denied."""

    def __init__(
        self,
        message: str,
        required_permission: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if required_permission:
            ctx["required_permission"] = required_permission
        super().__init__(message, error_code="AUTHORIZATION_ERROR", context=ctx)
        self.required_permission = required_permission


class InjectionError(SecurityError):
    """Prompt injection, XSS, SQL injection detected."""

    def __init__(
        self,
        message: str,
        injection_type: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if injection_type:
            ctx["injection_type"] = injection_type
        super().__init__(message, error_code="INJECTION_ERROR", context=ctx)
        self.injection_type = injection_type


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(AuraError):
    """Missing or invalid configuration."""

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if config_key:
            ctx["config_key"] = config_key
        super().__init__(message, error_code="CONFIGURATION_ERROR", context=ctx)
        self.config_key = config_key


# =============================================================================
# Agent Errors
# =============================================================================


class AgentError(AuraError):
    """Agent execution failures."""

    def __init__(
        self,
        message: str,
        agent_name: str | None = None,
        error_code: str = "AGENT_ERROR",
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if agent_name:
            ctx["agent"] = agent_name
        super().__init__(message, error_code, ctx)
        self.agent_name = agent_name


class ToolExecutionError(AgentError):
    """Agent tool invocation failures."""

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        agent_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if tool_name:
            ctx["tool"] = tool_name
        super().__init__(
            message,
            agent_name=agent_name,
            error_code="TOOL_EXECUTION_ERROR",
            context=ctx,
        )
        self.tool_name = tool_name


class OrchestrationError(AgentError):
    """Agent coordination failures."""

    def __init__(
        self,
        message: str,
        workflow_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if workflow_id:
            ctx["workflow_id"] = workflow_id
        super().__init__(message, error_code="ORCHESTRATION_ERROR", context=ctx)
        self.workflow_id = workflow_id


# =============================================================================
# Workflow Errors
# =============================================================================


class WorkflowError(AuraError):
    """Business workflow failures."""

    def __init__(
        self,
        message: str,
        workflow_name: str | None = None,
        error_code: str = "WORKFLOW_ERROR",
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if workflow_name:
            ctx["workflow"] = workflow_name
        super().__init__(message, error_code, ctx)
        self.workflow_name = workflow_name


class ApprovalError(WorkflowError):
    """HITL approval workflow failures."""

    def __init__(
        self,
        message: str,
        approval_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if approval_id:
            ctx["approval_id"] = approval_id
        super().__init__(
            message,
            workflow_name="hitl_approval",
            error_code="APPROVAL_ERROR",
            context=ctx,
        )
        self.approval_id = approval_id


class SandboxError(WorkflowError):
    """Sandbox provisioning/testing failures."""

    def __init__(
        self,
        message: str,
        sandbox_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if sandbox_id:
            ctx["sandbox_id"] = sandbox_id
        super().__init__(
            message, workflow_name="sandbox", error_code="SANDBOX_ERROR", context=ctx
        )
        self.sandbox_id = sandbox_id


# =============================================================================
# Utility Functions
# =============================================================================


def handle_exception(
    exc: Exception,
    logger: logging.Logger,
    reraise: bool = True,
    default_message: str = "An unexpected error occurred",
) -> AuraError:
    """Convert any exception to an AuraError with proper logging.

    Args:
        exc: The exception to handle
        logger: Logger instance for recording the error
        reraise: If True, raise the AuraError after logging
        default_message: Message for non-AuraError exceptions

    Returns:
        AuraError instance (if reraise=False)

    Raises:
        AuraError: If reraise=True
    """
    if isinstance(exc, AuraError):
        exc.log()
        if reraise:
            raise exc
        return exc

    # Wrap unknown exceptions
    wrapped = ServiceError(
        message=default_message,
        error_code="UNEXPECTED_ERROR",
        context={"original_error": str(exc), "error_type": type(exc).__name__},
    )
    logger.exception("Unexpected error: %s", exc)
    if reraise:
        raise wrapped from exc
    return wrapped


def safe_error_message(
    exc: Exception,
    operation: str = "operation",
    include_type: bool = False,
) -> str:
    """Generate a safe error message for API responses.

    Prevents leaking sensitive internal details while providing useful feedback.

    Args:
        exc: The exception to describe
        operation: Human-readable operation name (e.g., "approval lookup")
        include_type: If True, include the exception class name

    Returns:
        Safe error message string

    Example:
        >>> safe_error_message(ValueError("secret=abc123"), "user validation")
        "Error during user validation"
        >>> safe_error_message(ValidationError("Missing field"), "input check", True)
        "Error during input check: ValidationError"
    """
    # For AuraError, we control the message - it's safe
    if isinstance(exc, AuraError):
        if include_type:
            return f"{exc.__class__.__name__}: {exc.message}"
        return exc.message

    # For other exceptions, use generic message
    if include_type:
        return f"Error during {operation}: {exc.__class__.__name__}"
    return f"Error during {operation}"


def api_error_response(
    exc: Exception,
    logger: logging.Logger,
    operation: str,
    status_code: int = 500,
) -> dict[str, Any]:
    """Create a standardized API error response with logging.

    Logs the full exception internally but returns a safe message to the client.

    Args:
        exc: The exception that occurred
        logger: Logger to record the full error
        operation: Human-readable operation name
        status_code: HTTP status code for the response

    Returns:
        Dictionary suitable for FastAPI HTTPException detail

    Example:
        >>> try:
        ...     do_something()
        ... except Exception as e:
        ...     raise HTTPException(
        ...         status_code=500,
        ...         detail=api_error_response(e, logger, "data retrieval")
        ...     )
    """
    # Log the full exception for debugging
    if isinstance(exc, AuraError):
        exc.log()
    else:
        logger.exception("Error during %s: %s", operation, exc)

    # Return safe response
    return {
        "error": (
            exc.__class__.__name__ if isinstance(exc, AuraError) else "InternalError"
        ),
        "message": safe_error_message(exc, operation),
        "operation": operation,
    }


def raise_internal_error(
    exc: Exception,
    logger: logging.Logger,
    operation: str,
) -> None:
    """Raise HTTPException with safe error message for 500 errors.

    Logs the full exception internally but raises with a safe message.
    Use this instead of: raise HTTPException(status_code=500, detail=str(e))

    Args:
        exc: The exception that occurred
        logger: Logger to record the full error
        operation: Human-readable operation name (e.g., "fetch users")

    Raises:
        HTTPException: Always raises with status_code=500 and safe detail

    Example:
        >>> try:
        ...     result = await service.do_something()
        ... except Exception as e:
        ...     raise_internal_error(e, logger, "process request")
    """
    from fastapi import HTTPException

    # Log full exception for debugging
    if isinstance(exc, AuraError):
        exc.log()
    else:
        logger.exception("Error during %s: %s", operation, exc)

    # Raise with safe message
    raise HTTPException(
        status_code=500,
        detail=f"Failed to {operation}. Please try again or contact support.",
    )
