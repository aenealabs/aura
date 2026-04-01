"""
Project Aura - Security Audit Logging Service

Comprehensive security event logging for compliance and incident response.
Supports SOC2, CMMC, and NIST 800-53 audit requirements.

Author: Project Aura Team
Created: 2025-12-12
"""

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SecurityEventType(Enum):
    """Types of security events."""

    # Authentication events
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_REFRESH = "auth.token.refresh"
    AUTH_TOKEN_INVALID = "auth.token.invalid"
    AUTH_TOKEN_EXPIRED = "auth.token.expired"
    AUTH_MFA_SUCCESS = "auth.mfa.success"
    AUTH_MFA_FAILURE = "auth.mfa.failure"

    # Authorization events
    AUTHZ_ACCESS_GRANTED = "authz.access.granted"
    AUTHZ_ACCESS_DENIED = "authz.access.denied"
    AUTHZ_PRIVILEGE_ESCALATION = "authz.privilege.escalation"
    AUTHZ_ROLE_CHANGE = "authz.role.change"

    # Rate limiting events
    RATE_LIMIT_EXCEEDED = "rate_limit.exceeded"
    RATE_LIMIT_WARNING = "rate_limit.warning"

    # Input validation events
    INPUT_VALIDATION_FAILURE = "input.validation.failure"
    INPUT_INJECTION_ATTEMPT = "input.injection.attempt"
    INPUT_XSS_ATTEMPT = "input.xss.attempt"
    INPUT_PATH_TRAVERSAL = "input.path_traversal"

    # Security threats
    THREAT_PROMPT_INJECTION = "threat.prompt_injection"
    THREAT_SSRF_ATTEMPT = "threat.ssrf.attempt"
    THREAT_COMMAND_INJECTION = "threat.command_injection"
    THREAT_SECRETS_EXPOSURE = "threat.secrets.exposure"

    # Configuration events
    CONFIG_CHANGE = "config.change"
    CONFIG_SENSITIVE_ACCESS = "config.sensitive_access"

    # Admin actions
    ADMIN_USER_CREATE = "admin.user.create"
    ADMIN_USER_DELETE = "admin.user.delete"
    ADMIN_USER_MODIFY = "admin.user.modify"
    ADMIN_POLICY_CHANGE = "admin.policy.change"

    # Data access events
    DATA_ACCESS = "data.access"
    DATA_EXPORT = "data.export"
    DATA_DELETE = "data.delete"

    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"


class SecurityEventSeverity(Enum):
    """Severity levels for security events."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityContext:
    """Context information for security events."""

    user_id: str | None = None
    user_email: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    session_id: str | None = None
    resource: str | None = None
    action: str | None = None
    environment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SecurityEvent:
    """Security event record."""

    event_id: str
    event_type: SecurityEventType
    severity: SecurityEventSeverity
    timestamp: str
    message: str
    context: SecurityContext
    details: dict[str, Any] = field(default_factory=dict)
    source: str = "aura-api"

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for logging/storage."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "message": self.message,
            "context": self.context.to_dict(),
            "details": self.details,
            "source": self.source,
        }

    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class SecurityAuditService:
    """
    Security audit logging service.

    Provides comprehensive security event logging with:
    - Structured event format
    - Multiple output handlers (file, CloudWatch, etc.)
    - Event correlation via request ID
    - Compliance-ready format
    """

    # Event type to severity mapping (defaults)
    DEFAULT_SEVERITY: dict[SecurityEventType, SecurityEventSeverity] = {
        SecurityEventType.AUTH_LOGIN_SUCCESS: SecurityEventSeverity.INFO,
        SecurityEventType.AUTH_LOGIN_FAILURE: SecurityEventSeverity.MEDIUM,
        SecurityEventType.AUTH_LOGOUT: SecurityEventSeverity.INFO,
        SecurityEventType.AUTH_TOKEN_INVALID: SecurityEventSeverity.MEDIUM,
        SecurityEventType.AUTH_TOKEN_EXPIRED: SecurityEventSeverity.LOW,
        SecurityEventType.AUTHZ_ACCESS_GRANTED: SecurityEventSeverity.INFO,
        SecurityEventType.AUTHZ_ACCESS_DENIED: SecurityEventSeverity.MEDIUM,
        SecurityEventType.AUTHZ_PRIVILEGE_ESCALATION: SecurityEventSeverity.CRITICAL,
        SecurityEventType.RATE_LIMIT_EXCEEDED: SecurityEventSeverity.MEDIUM,
        SecurityEventType.INPUT_INJECTION_ATTEMPT: SecurityEventSeverity.HIGH,
        SecurityEventType.INPUT_XSS_ATTEMPT: SecurityEventSeverity.HIGH,
        SecurityEventType.INPUT_PATH_TRAVERSAL: SecurityEventSeverity.HIGH,
        SecurityEventType.THREAT_PROMPT_INJECTION: SecurityEventSeverity.HIGH,
        SecurityEventType.THREAT_SSRF_ATTEMPT: SecurityEventSeverity.HIGH,
        SecurityEventType.THREAT_COMMAND_INJECTION: SecurityEventSeverity.CRITICAL,
        SecurityEventType.THREAT_SECRETS_EXPOSURE: SecurityEventSeverity.CRITICAL,
        SecurityEventType.CONFIG_CHANGE: SecurityEventSeverity.MEDIUM,
        SecurityEventType.ADMIN_USER_DELETE: SecurityEventSeverity.HIGH,
        SecurityEventType.ADMIN_POLICY_CHANGE: SecurityEventSeverity.HIGH,
        SecurityEventType.DATA_DELETE: SecurityEventSeverity.MEDIUM,
    }

    def __init__(
        self,
        service_name: str = "aura-api",
        environment: str | None = None,
        enable_console: bool = True,
        enable_file: bool = False,
        log_file_path: str | None = None,
    ):
        """
        Initialize security audit service.

        Args:
            service_name: Name of the service generating events
            environment: Environment name (dev, staging, prod)
            enable_console: Log to console/stdout
            enable_file: Log to file
            log_file_path: Path for audit log file
        """
        self.service_name = service_name
        self.environment = environment or os.environ.get("ENVIRONMENT", "dev")
        self.enable_console = enable_console
        self.enable_file = enable_file
        self.log_file_path = log_file_path or "/var/log/aura/security-audit.log"

        # Statistics
        self._stats: dict[str, Any] = {
            "total_events": 0,
            "by_type": {},
            "by_severity": {s.value: 0 for s in SecurityEventSeverity},
        }

        # Set up audit logger
        self._audit_logger = logging.getLogger("security.audit")
        self._audit_logger.setLevel(logging.INFO)

        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter("%(message)s"))
            self._audit_logger.addHandler(console_handler)

        # File handler
        if enable_file:
            try:
                os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
                file_handler = logging.FileHandler(self.log_file_path)
                file_handler.setFormatter(logging.Formatter("%(message)s"))
                self._audit_logger.addHandler(file_handler)
            except Exception as e:
                logger.warning(f"Could not create audit log file: {e}")

    def log_event(
        self,
        event_type: SecurityEventType,
        message: str,
        context: SecurityContext | None = None,
        severity: SecurityEventSeverity | None = None,
        details: dict[str, Any] | None = None,
    ) -> SecurityEvent:
        """
        Log a security event.

        Args:
            event_type: Type of security event
            message: Human-readable description
            context: Security context information
            severity: Event severity (default based on event type)
            details: Additional event details

        Returns:
            The logged SecurityEvent
        """
        # Generate event ID
        event_id = str(uuid.uuid4())

        # Determine severity
        if severity is None:
            severity = self.DEFAULT_SEVERITY.get(event_type, SecurityEventSeverity.INFO)

        # Create context if not provided
        if context is None:
            context = SecurityContext(environment=self.environment)
        elif context.environment is None:
            context.environment = self.environment

        # Create event
        event = SecurityEvent(
            event_id=event_id,
            event_type=event_type,
            severity=severity,
            timestamp=datetime.now(timezone.utc).isoformat(),
            message=message,
            context=context,
            details=details or {},
            source=self.service_name,
        )

        # Update statistics
        self._stats["total_events"] += 1
        self._stats["by_severity"][severity.value] += 1
        type_key = event_type.value
        self._stats["by_type"][type_key] = self._stats["by_type"].get(type_key, 0) + 1

        # Write to audit log
        self._write_event(event)

        return event

    def _write_event(self, event: SecurityEvent) -> None:
        """Write event to configured outputs."""
        json_event = event.to_json()

        # Log to audit logger
        self._audit_logger.info(json_event)

        # Also log to standard logger for visibility
        log_level = self._severity_to_log_level(event.severity)
        logger.log(
            log_level,
            f"SECURITY_AUDIT: {event.event_type.value} - {event.message} "
            f"[event_id={event.event_id}]",
        )

    def _severity_to_log_level(self, severity: SecurityEventSeverity) -> int:
        """Map security severity to logging level."""
        mapping = {
            SecurityEventSeverity.INFO: logging.INFO,
            SecurityEventSeverity.LOW: logging.INFO,
            SecurityEventSeverity.MEDIUM: logging.WARNING,
            SecurityEventSeverity.HIGH: logging.ERROR,
            SecurityEventSeverity.CRITICAL: logging.CRITICAL,
        }
        return mapping.get(severity, logging.INFO)

    # =========================================================================
    # Convenience Methods for Common Events
    # =========================================================================

    def log_login_success(
        self,
        user_id: str,
        user_email: str,
        ip_address: str,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> SecurityEvent:
        """Log successful login."""
        return self.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message=f"User {user_email} logged in successfully",
            context=SecurityContext(
                user_id=user_id,
                user_email=user_email,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
            ),
        )

    def log_login_failure(
        self,
        user_email: str,
        ip_address: str,
        reason: str,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> SecurityEvent:
        """Log failed login attempt."""
        return self.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_FAILURE,
            message=f"Login failed for {user_email}: {reason}",
            context=SecurityContext(
                user_email=user_email,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
            ),
            details={"reason": reason},
        )

    def log_access_denied(
        self,
        user_id: str,
        resource: str,
        action: str,
        reason: str,
        request_id: str | None = None,
    ) -> SecurityEvent:
        """Log access denied event."""
        return self.log_event(
            event_type=SecurityEventType.AUTHZ_ACCESS_DENIED,
            message=f"Access denied: user={user_id} resource={resource} action={action}",
            context=SecurityContext(
                user_id=user_id,
                resource=resource,
                action=action,
                request_id=request_id,
            ),
            details={"reason": reason},
        )

    def log_rate_limit_exceeded(
        self,
        client_id: str,
        tier: str,
        limit: int,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> SecurityEvent:
        """Log rate limit exceeded event."""
        return self.log_event(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            message=f"Rate limit exceeded for {client_id}: tier={tier} limit={limit}",
            context=SecurityContext(
                user_id=client_id,
                ip_address=ip_address,
                request_id=request_id,
            ),
            details={"tier": tier, "limit": limit},
        )

    def log_injection_attempt(
        self,
        threat_type: str,
        input_field: str,
        client_id: str | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> SecurityEvent:
        """Log injection attempt detection."""
        event_type_map = {
            "sql_injection": SecurityEventType.INPUT_INJECTION_ATTEMPT,
            "xss": SecurityEventType.INPUT_XSS_ATTEMPT,
            "path_traversal": SecurityEventType.INPUT_PATH_TRAVERSAL,
            "prompt_injection": SecurityEventType.THREAT_PROMPT_INJECTION,
            "ssrf": SecurityEventType.THREAT_SSRF_ATTEMPT,
            "command_injection": SecurityEventType.THREAT_COMMAND_INJECTION,
        }
        event_type = event_type_map.get(
            threat_type, SecurityEventType.INPUT_INJECTION_ATTEMPT
        )

        return self.log_event(
            event_type=event_type,
            message=f"Injection attempt detected: type={threat_type} field={input_field}",
            context=SecurityContext(
                user_id=client_id,
                ip_address=ip_address,
                request_id=request_id,
            ),
            details={"threat_type": threat_type, "input_field": input_field},
            severity=SecurityEventSeverity.HIGH,
        )

    def log_config_change(
        self,
        user_id: str,
        config_key: str,
        old_value: Any | None = None,
        new_value: Any | None = None,
        request_id: str | None = None,
    ) -> SecurityEvent:
        """Log configuration change."""
        return self.log_event(
            event_type=SecurityEventType.CONFIG_CHANGE,
            message=f"Configuration changed by {user_id}: {config_key}",
            context=SecurityContext(
                user_id=user_id,
                request_id=request_id,
            ),
            details={
                "config_key": config_key,
                "old_value": str(old_value) if old_value else None,
                "new_value": str(new_value) if new_value else None,
            },
        )

    def log_admin_action(
        self,
        user_id: str,
        action: str,
        target_user: str | None = None,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> SecurityEvent:
        """Log admin action."""
        event_type_map = {
            "user_create": SecurityEventType.ADMIN_USER_CREATE,
            "user_delete": SecurityEventType.ADMIN_USER_DELETE,
            "user_modify": SecurityEventType.ADMIN_USER_MODIFY,
            "policy_change": SecurityEventType.ADMIN_POLICY_CHANGE,
        }
        event_type = event_type_map.get(action, SecurityEventType.CONFIG_CHANGE)

        return self.log_event(
            event_type=event_type,
            message=f"Admin action by {user_id}: {action}",
            context=SecurityContext(
                user_id=user_id,
                request_id=request_id,
            ),
            details={"action": action, "target_user": target_user, **(details or {})},
        )

    def get_stats(self) -> dict[str, Any]:
        """Get audit statistics."""
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "total_events": 0,
            "by_type": {},
            "by_severity": {s.value: 0 for s in SecurityEventSeverity},
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_audit_service: SecurityAuditService | None = None


def get_audit_service() -> SecurityAuditService:
    """Get singleton security audit service instance."""
    global _audit_service
    if _audit_service is None:
        _audit_service = SecurityAuditService()
    return _audit_service


def log_security_event(
    event_type: SecurityEventType,
    message: str,
    context: SecurityContext | None = None,
    details: dict[str, Any] | None = None,
) -> SecurityEvent:
    """Convenience function to log a security event."""
    return get_audit_service().log_event(
        event_type=event_type,
        message=message,
        context=context,
        details=details,
    )
