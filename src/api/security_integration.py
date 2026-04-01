"""
Project Aura - Security Services Integration

Integrates all security services into the FastAPI application:
- Input validation as FastAPI dependencies
- Security audit logging for all endpoints
- Secrets detection for code ingestion
- Rate limiting integration

Author: Project Aura Team
Created: 2025-12-12
"""

import functools
import logging
import time
from typing import Any, Callable, cast

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, field_validator

from src.services.input_validation_service import (
    InputValidator,
    ThreatType,
    get_input_validator,
)
from src.services.secrets_detection_service import (
    ScanResult,
    SecretsDetectionService,
    SecretSeverity,
    get_secrets_service,
)
from src.services.security_audit_service import (
    SecurityAuditService,
    SecurityContext,
    SecurityEvent,
    SecurityEventSeverity,
    SecurityEventType,
    get_audit_service,
)

logger = logging.getLogger(__name__)


# =============================================================================
# FastAPI Dependencies for Security Services
# =============================================================================


def get_security_context(request: Request) -> SecurityContext:
    """
    Extract security context from request.

    This dependency extracts user info, IP, request ID, etc.
    from the request for security audit logging.
    """
    # Get user info if authenticated
    user_id = None
    user_email = None
    if hasattr(request.state, "user") and request.state.user:
        user_id = getattr(request.state.user, "sub", None)
        user_email = getattr(request.state.user, "email", None)

    # Get request ID (set by RequestIDMiddleware)
    request_id = getattr(request.state, "request_id", None)

    # Get client IP (handle proxies)
    ip_address: str | None = None
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    elif request.client:
        ip_address = request.client.host

    return SecurityContext(
        user_id=user_id,
        user_email=user_email,
        ip_address=ip_address,
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id,
        resource=str(request.url.path),
        action=request.method,
    )


def get_validator() -> InputValidator:
    """Get input validator dependency."""
    return get_input_validator()


def get_audit() -> SecurityAuditService:
    """Get security audit service dependency."""
    return get_audit_service()


def get_secrets_scanner() -> SecretsDetectionService:
    """Get secrets detection service dependency."""
    return get_secrets_service()


# =============================================================================
# Validated Request Models
# =============================================================================


class ValidatedIngestionRequest(BaseModel):
    """Ingestion request with security validation."""

    repository_url: str
    branch: str = "main"
    force_refresh: bool = False
    shallow_clone: bool = True

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, v: str) -> str:
        """Validate repository URL for security threats."""
        validator = get_input_validator()

        # Check URL for SSRF
        result = validator.validate_url(v)
        if ThreatType.SSRF in result.threats_detected:
            raise ValueError("Invalid repository URL: potential SSRF detected")

        # Ensure it's a valid git URL
        if not any(
            v.startswith(prefix) for prefix in ["https://", "git@", "ssh://", "git://"]
        ):
            raise ValueError("Repository URL must use https, git, or ssh protocol")

        # Block localhost and private IPs
        blocked_hosts = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "169.254.",
        ]  # nosec B104 - blocklist, not binding
        for blocked in blocked_hosts:
            if blocked in v.lower():
                raise ValueError(f"Repository URL cannot reference {blocked}")

        return v

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v: str) -> str:
        """Validate branch name for injection attempts."""
        validator = get_input_validator()

        # Check for path traversal in branch name
        result = validator.validate_path(v)
        if ThreatType.PATH_TRAVERSAL in result.threats_detected:
            raise ValueError("Invalid branch name: path traversal detected")

        # Check for command injection
        result = validator.validate_string(v)
        if ThreatType.COMMAND_INJECTION in result.threats_detected:
            raise ValueError("Invalid branch name: command injection detected")

        # Sanitize
        return cast(str, result.sanitized_value)


class ValidatedQueryRequest(BaseModel):
    """Query request with security validation."""

    query: str
    max_results: int = 10
    include_code: bool = True

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query for injection attempts."""
        validator = get_input_validator()

        # Check for various injection types
        result = validator.validate_string(
            v,
            check_sql_injection=True,
            check_xss=True,
            check_command_injection=True,
        )

        # Log threats but allow query (after sanitization)
        if result.threats_detected:
            logger.warning(
                f"Threats detected in query: {[t.value for t in result.threats_detected]}"
            )
            audit = get_audit_service()
            for threat in result.threats_detected:
                audit.log_injection_attempt(
                    threat_type=threat.value,
                    input_field="query",
                )

        return cast(str, result.sanitized_value)

    @field_validator("max_results")
    @classmethod
    def validate_max_results(cls, v: int) -> int:
        """Validate max_results is within bounds."""
        if v < 1:
            raise ValueError("max_results must be at least 1")
        if v > 100:
            raise ValueError("max_results cannot exceed 100")
        return v


class ValidatedWebhookPayload(BaseModel):
    """Webhook payload with security validation."""

    ref: str | None = None
    repository: dict[str, Any] | None = None
    commits: list[dict[str, Any]] | None = None
    sender: dict[str, Any] | None = None

    @field_validator("ref")
    @classmethod
    def validate_ref(cls, v: str | None) -> str | None:
        """Validate git ref for injection."""
        if v is None:
            return v

        validator = get_input_validator()
        result = validator.validate_string(v)

        if result.threats_detected:
            raise ValueError("Invalid ref: security threats detected")

        return cast(str | None, result.sanitized_value)


# =============================================================================
# Security Audit Decorators
# =============================================================================


def audit_endpoint(
    event_type: SecurityEventType,
    severity: SecurityEventSeverity | None = None,
    include_response: bool = False,
):
    """
    Decorator to automatically audit endpoint calls.

    Usage:
        @app.post("/api/v1/users")
        @audit_endpoint(SecurityEventType.ADMIN_USER_CREATE)
        async def create_user(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            # Get security context
            context = None
            if request:
                context = get_security_context(request)

            # Get audit service
            audit = get_audit_service()

            # Log start of request
            start_time = time.time()

            try:
                # Execute endpoint
                result = await func(*args, **kwargs)

                # Log success
                duration_ms = (time.time() - start_time) * 1000
                details: dict[str, Any] = {"duration_ms": round(duration_ms, 2)}

                if include_response and result:
                    # Include sanitized response info
                    if hasattr(result, "model_dump"):
                        details["response_type"] = type(result).__name__
                    elif isinstance(result, dict):
                        details["response_keys"] = list(result.keys())

                audit.log_event(
                    event_type=event_type,
                    message=f"Endpoint {func.__name__} completed successfully",
                    context=context,
                    severity=severity or SecurityEventSeverity.INFO,
                    details=details,
                )

                return result

            except HTTPException as e:
                # Log HTTP exception
                duration_ms = (time.time() - start_time) * 1000
                audit.log_event(
                    event_type=event_type,
                    message=f"Endpoint {func.__name__} returned {e.status_code}",
                    context=context,
                    severity=(
                        SecurityEventSeverity.MEDIUM
                        if e.status_code >= 400
                        else SecurityEventSeverity.INFO
                    ),
                    details={
                        "status_code": e.status_code,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                raise

            except Exception as e:
                # Log unexpected error
                duration_ms = (time.time() - start_time) * 1000
                audit.log_event(
                    event_type=SecurityEventType.SYSTEM_ERROR,
                    message=f"Endpoint {func.__name__} failed: {type(e).__name__}",
                    context=context,
                    severity=SecurityEventSeverity.HIGH,
                    details={
                        "error_type": type(e).__name__,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                raise

        return wrapper

    return decorator


def require_no_secrets(
    block_on_critical: bool = True,
    block_on_high: bool = False,
):
    """
    Decorator to scan request body for secrets.

    Usage:
        @app.post("/api/v1/code")
        @require_no_secrets(block_on_critical=True)
        async def submit_code(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request:
                # Get request body
                body = await request.body()
                if body:
                    # Scan for secrets
                    scanner = get_secrets_service()
                    result = scanner.scan_text(body.decode("utf-8", errors="ignore"))

                    if result.has_secrets:
                        # Log the detection
                        audit = get_audit_service()
                        context = get_security_context(request)

                        for finding in result.findings:
                            audit.log_event(
                                event_type=SecurityEventType.THREAT_SECRETS_EXPOSURE,
                                message=f"Secret detected in request: {finding.secret_type.value}",
                                context=context,
                                severity=SecurityEventSeverity.HIGH,
                                details={
                                    "secret_type": finding.secret_type.value,
                                    "severity": finding.severity.value,
                                    "line_number": finding.line_number,
                                },
                            )

                        # Block if critical/high secrets found
                        critical_findings = [
                            f
                            for f in result.findings
                            if f.severity == SecretSeverity.CRITICAL
                        ]
                        high_findings = [
                            f
                            for f in result.findings
                            if f.severity == SecretSeverity.HIGH
                        ]

                        if block_on_critical and critical_findings:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail={
                                    "error": "Request contains potential secrets",
                                    "message": "Critical secrets detected in request body. "
                                    "Please remove sensitive data before submitting.",
                                    "secrets_found": len(critical_findings),
                                },
                            )

                        if block_on_high and high_findings:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail={
                                    "error": "Request contains potential secrets",
                                    "message": "Sensitive data detected in request body. "
                                    "Please remove secrets before submitting.",
                                    "secrets_found": len(high_findings),
                                },
                            )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# Security Validation Functions
# =============================================================================


def validate_and_sanitize(
    value: str,
    field_name: str = "input",
    check_sql: bool = True,
    check_xss: bool = True,
    check_path: bool = False,
    check_command: bool = False,
    strict: bool = False,
) -> str:
    """
    Validate and sanitize a string input.

    Args:
        value: Input string to validate
        field_name: Name of field for error messages
        check_sql: Check for SQL injection
        check_xss: Check for XSS
        check_path: Check for path traversal
        check_command: Check for command injection
        strict: Raise exception on any threat (vs just log)

    Returns:
        Sanitized string

    Raises:
        HTTPException: If strict=True and threats detected
    """
    validator = get_input_validator()

    result = validator.validate_string(
        value,
        field_name=field_name,
        check_sql_injection=check_sql,
        check_xss=check_xss,
        check_command_injection=check_command,
    )

    if check_path:
        path_result = validator.validate_path(value)
        if path_result.threats_detected:
            result.threats_detected.extend(path_result.threats_detected)
            result.warnings.extend(path_result.warnings)

    if result.threats_detected:
        # Log threats
        audit = get_audit_service()
        for threat in result.threats_detected:
            audit.log_injection_attempt(
                threat_type=threat.value,
                input_field=field_name,
            )

        if strict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Input validation failed",
                    "field": field_name,
                    "threats": [t.value for t in result.threats_detected],
                },
            )

    return cast(str, result.sanitized_value)


def scan_code_for_secrets(
    code: str,
    file_path: str | None = None,
    block_on_secrets: bool = False,
) -> ScanResult:
    """
    Scan code content for secrets.

    Args:
        code: Code content to scan
        file_path: Optional file path for context
        block_on_secrets: Raise exception if secrets found

    Returns:
        ScanResult with findings

    Raises:
        HTTPException: If block_on_secrets=True and secrets found
    """
    scanner = get_secrets_service()
    result = scanner.scan_text(code, file_path)

    if result.has_secrets:
        # Log findings
        audit = get_audit_service()
        for finding in result.findings:
            audit.log_event(
                event_type=SecurityEventType.THREAT_SECRETS_EXPOSURE,
                message=f"Secret detected: {finding.secret_type.value}",
                severity=SecurityEventSeverity.HIGH,
                details={
                    "secret_type": finding.secret_type.value,
                    "file_path": file_path,
                    "line_number": finding.line_number,
                },
            )

        if block_on_secrets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Secrets detected in code",
                    "secrets_count": len(result.findings),
                    "message": "Please remove secrets before ingesting code",
                },
            )

    return result


# =============================================================================
# Security Event Logging Helpers
# =============================================================================


def log_auth_success(
    user_id: str,
    user_email: str,
    ip_address: str,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> SecurityEvent:
    """Log successful authentication."""
    return get_audit_service().log_login_success(
        user_id=user_id,
        user_email=user_email,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )


def log_auth_failure(
    user_email: str,
    ip_address: str,
    reason: str,
    request_id: str | None = None,
) -> SecurityEvent:
    """Log failed authentication."""
    return get_audit_service().log_login_failure(
        user_email=user_email,
        ip_address=ip_address,
        reason=reason,
        request_id=request_id,
    )


def log_access_denied(
    user_id: str,
    resource: str,
    action: str,
    reason: str,
    request_id: str | None = None,
) -> SecurityEvent:
    """Log access denied event."""
    return get_audit_service().log_access_denied(
        user_id=user_id,
        resource=resource,
        action=action,
        reason=reason,
        request_id=request_id,
    )


def log_rate_limit(
    client_id: str,
    tier: str,
    limit: int,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> SecurityEvent:
    """Log rate limit exceeded."""
    return get_audit_service().log_rate_limit_exceeded(
        client_id=client_id,
        tier=tier,
        limit=limit,
        ip_address=ip_address,
        request_id=request_id,
    )


def log_security_threat(
    threat_type: str,
    description: str,
    context: SecurityContext | None = None,
    details: dict[str, Any] | None = None,
) -> SecurityEvent:
    """Log a security threat detection."""
    event_type_map = {
        "prompt_injection": SecurityEventType.THREAT_PROMPT_INJECTION,
        "ssrf": SecurityEventType.THREAT_SSRF_ATTEMPT,
        "command_injection": SecurityEventType.THREAT_COMMAND_INJECTION,
        "sql_injection": SecurityEventType.INPUT_INJECTION_ATTEMPT,
        "xss": SecurityEventType.INPUT_XSS_ATTEMPT,
        "path_traversal": SecurityEventType.INPUT_PATH_TRAVERSAL,
        "secrets": SecurityEventType.THREAT_SECRETS_EXPOSURE,
    }

    event_type = event_type_map.get(
        threat_type, SecurityEventType.INPUT_INJECTION_ATTEMPT
    )

    return get_audit_service().log_event(
        event_type=event_type,
        message=description,
        context=context,
        severity=SecurityEventSeverity.HIGH,
        details=details,
    )


# =============================================================================
# Security Statistics
# =============================================================================


def get_security_stats() -> dict[str, Any]:
    """Get combined statistics from all security services."""
    return {
        "input_validation": get_input_validator().get_stats(),
        "audit_logging": get_audit_service().get_stats(),
        "secrets_detection": get_secrets_service().get_stats(),
    }


def reset_security_stats() -> None:
    """Reset statistics for all security services."""
    get_input_validator().reset_stats()
    get_audit_service().reset_stats()
    get_secrets_service().reset_stats()
