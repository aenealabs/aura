"""
Project Aura - Security Audit Service Tests

Tests for the comprehensive security audit logging service covering:
- Event logging with proper structure
- Security context handling
- Severity mapping
- Convenience methods for common events
- Statistics tracking

Author: Project Aura Team
Created: 2025-12-12
"""

import json

import pytest

from src.services.security_audit_service import (
    SecurityAuditService,
    SecurityContext,
    SecurityEvent,
    SecurityEventSeverity,
    SecurityEventType,
    get_audit_service,
    log_security_event,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def audit_service():
    """Create a fresh audit service instance for testing."""
    return SecurityAuditService(
        service_name="test-service",
        environment="test",
        enable_console=False,
        enable_file=False,
    )


@pytest.fixture
def sample_context():
    """Create a sample security context."""
    return SecurityContext(
        user_id="user-123",
        user_email="user@example.com",
        ip_address="192.168.1.100",
        user_agent="TestClient/1.0",
        request_id="req-456",
        session_id="sess-789",
        resource="/api/users",
        action="read",
        environment="test",
    )


# ============================================================================
# SecurityContext Tests
# ============================================================================


class TestSecurityContext:
    """Tests for SecurityContext dataclass."""

    def test_context_to_dict(self, sample_context):
        """Test context converts to dictionary properly."""
        result = sample_context.to_dict()

        assert result["user_id"] == "user-123"
        assert result["user_email"] == "user@example.com"
        assert result["ip_address"] == "192.168.1.100"
        assert result["request_id"] == "req-456"

    def test_context_excludes_none_values(self):
        """Test that None values are excluded from dict."""
        context = SecurityContext(
            user_id="user-123",
            ip_address="10.0.0.1",
            # Other fields are None
        )

        result = context.to_dict()

        assert "user_id" in result
        assert "ip_address" in result
        assert "user_email" not in result
        assert "session_id" not in result

    def test_empty_context(self):
        """Test empty context."""
        context = SecurityContext()

        result = context.to_dict()
        assert result == {}


# ============================================================================
# SecurityEvent Tests
# ============================================================================


class TestSecurityEvent:
    """Tests for SecurityEvent dataclass."""

    def test_event_to_dict(self, sample_context):
        """Test event converts to dictionary properly."""
        event = SecurityEvent(
            event_id="evt-123",
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            severity=SecurityEventSeverity.INFO,
            timestamp="2025-12-12T10:00:00Z",
            message="User logged in",
            context=sample_context,
            details={"method": "password"},
            source="test-service",
        )

        result = event.to_dict()

        assert result["event_id"] == "evt-123"
        assert result["event_type"] == "auth.login.success"
        assert result["severity"] == "info"
        assert result["message"] == "User logged in"
        assert result["details"]["method"] == "password"
        assert result["source"] == "test-service"

    def test_event_to_json(self, sample_context):
        """Test event converts to JSON string."""
        event = SecurityEvent(
            event_id="evt-123",
            event_type=SecurityEventType.AUTH_LOGIN_FAILURE,
            severity=SecurityEventSeverity.MEDIUM,
            timestamp="2025-12-12T10:00:00Z",
            message="Login failed",
            context=sample_context,
        )

        json_str = event.to_json()
        parsed = json.loads(json_str)

        assert parsed["event_id"] == "evt-123"
        assert parsed["event_type"] == "auth.login.failure"
        assert parsed["severity"] == "medium"


# ============================================================================
# SecurityAuditService Basic Tests
# ============================================================================


class TestSecurityAuditServiceBasic:
    """Basic tests for SecurityAuditService."""

    def test_service_initialization(self, audit_service):
        """Test service initializes correctly."""
        assert audit_service.service_name == "test-service"
        assert audit_service.environment == "test"

    def test_log_event_returns_event(self, audit_service):
        """Test log_event returns SecurityEvent."""
        event = audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="User logged in",
        )

        assert isinstance(event, SecurityEvent)
        assert event.event_type == SecurityEventType.AUTH_LOGIN_SUCCESS
        assert event.message == "User logged in"

    def test_log_event_generates_uuid(self, audit_service):
        """Test that event ID is a valid UUID."""
        event = audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test event",
        )

        # UUID format: 8-4-4-4-12 characters
        assert len(event.event_id) == 36
        assert event.event_id.count("-") == 4

    def test_log_event_generates_timestamp(self, audit_service):
        """Test that timestamp is generated."""
        event = audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test event",
        )

        assert event.timestamp is not None
        assert "T" in event.timestamp  # ISO format

    def test_log_event_with_context(self, audit_service, sample_context):
        """Test logging event with context."""
        event = audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test event",
            context=sample_context,
        )

        assert event.context.user_id == "user-123"
        assert event.context.ip_address == "192.168.1.100"

    def test_log_event_with_details(self, audit_service):
        """Test logging event with details."""
        event = audit_service.log_event(
            event_type=SecurityEventType.CONFIG_CHANGE,
            message="Config changed",
            details={"key": "rate_limit", "old": 100, "new": 200},
        )

        assert event.details["key"] == "rate_limit"
        assert event.details["old"] == 100
        assert event.details["new"] == 200


# ============================================================================
# Severity Mapping Tests
# ============================================================================


class TestSeverityMapping:
    """Tests for default severity mapping."""

    def test_default_severity_for_login_success(self, audit_service):
        """Test default severity for login success."""
        event = audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Login success",
        )

        assert event.severity == SecurityEventSeverity.INFO

    def test_default_severity_for_login_failure(self, audit_service):
        """Test default severity for login failure."""
        event = audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_FAILURE,
            message="Login failed",
        )

        assert event.severity == SecurityEventSeverity.MEDIUM

    def test_default_severity_for_privilege_escalation(self, audit_service):
        """Test default severity for privilege escalation."""
        event = audit_service.log_event(
            event_type=SecurityEventType.AUTHZ_PRIVILEGE_ESCALATION,
            message="Privilege escalation attempt",
        )

        assert event.severity == SecurityEventSeverity.CRITICAL

    def test_default_severity_for_prompt_injection(self, audit_service):
        """Test default severity for prompt injection."""
        event = audit_service.log_event(
            event_type=SecurityEventType.THREAT_PROMPT_INJECTION,
            message="Prompt injection detected",
        )

        assert event.severity == SecurityEventSeverity.HIGH

    def test_default_severity_for_command_injection(self, audit_service):
        """Test default severity for command injection."""
        event = audit_service.log_event(
            event_type=SecurityEventType.THREAT_COMMAND_INJECTION,
            message="Command injection detected",
        )

        assert event.severity == SecurityEventSeverity.CRITICAL

    def test_custom_severity_override(self, audit_service):
        """Test that custom severity overrides default."""
        event = audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Login success",
            severity=SecurityEventSeverity.HIGH,  # Override default INFO
        )

        assert event.severity == SecurityEventSeverity.HIGH


# ============================================================================
# Convenience Method Tests
# ============================================================================


class TestConvenienceMethods:
    """Tests for convenience logging methods."""

    def test_log_login_success(self, audit_service):
        """Test log_login_success convenience method."""
        event = audit_service.log_login_success(
            user_id="user-123",
            user_email="user@example.com",
            ip_address="10.0.0.1",
            user_agent="Chrome/100",
            request_id="req-456",
        )

        assert event.event_type == SecurityEventType.AUTH_LOGIN_SUCCESS
        assert "user@example.com" in event.message
        assert event.context.user_id == "user-123"
        assert event.context.ip_address == "10.0.0.1"

    def test_log_login_failure(self, audit_service):
        """Test log_login_failure convenience method."""
        event = audit_service.log_login_failure(
            user_email="attacker@example.com",
            ip_address="10.0.0.1",
            reason="Invalid password",
        )

        assert event.event_type == SecurityEventType.AUTH_LOGIN_FAILURE
        assert "attacker@example.com" in event.message
        assert event.details["reason"] == "Invalid password"

    def test_log_access_denied(self, audit_service):
        """Test log_access_denied convenience method."""
        event = audit_service.log_access_denied(
            user_id="user-123",
            resource="/api/admin",
            action="delete",
            reason="Insufficient permissions",
        )

        assert event.event_type == SecurityEventType.AUTHZ_ACCESS_DENIED
        assert "user-123" in event.message
        assert "/api/admin" in event.message
        assert event.details["reason"] == "Insufficient permissions"

    def test_log_rate_limit_exceeded(self, audit_service):
        """Test log_rate_limit_exceeded convenience method."""
        event = audit_service.log_rate_limit_exceeded(
            client_id="client-123",
            tier="standard",
            limit=100,
            ip_address="10.0.0.1",
        )

        assert event.event_type == SecurityEventType.RATE_LIMIT_EXCEEDED
        assert event.details["tier"] == "standard"
        assert event.details["limit"] == 100

    def test_log_injection_attempt_sql(self, audit_service):
        """Test log_injection_attempt for SQL injection."""
        event = audit_service.log_injection_attempt(
            threat_type="sql_injection",
            input_field="username",
            client_id="client-123",
        )

        assert event.event_type == SecurityEventType.INPUT_INJECTION_ATTEMPT
        assert event.severity == SecurityEventSeverity.HIGH
        assert event.details["threat_type"] == "sql_injection"

    def test_log_injection_attempt_xss(self, audit_service):
        """Test log_injection_attempt for XSS."""
        event = audit_service.log_injection_attempt(
            threat_type="xss",
            input_field="comment",
        )

        assert event.event_type == SecurityEventType.INPUT_XSS_ATTEMPT
        assert event.severity == SecurityEventSeverity.HIGH

    def test_log_injection_attempt_prompt_injection(self, audit_service):
        """Test log_injection_attempt for prompt injection."""
        event = audit_service.log_injection_attempt(
            threat_type="prompt_injection",
            input_field="query",
        )

        assert event.event_type == SecurityEventType.THREAT_PROMPT_INJECTION

    def test_log_injection_attempt_ssrf(self, audit_service):
        """Test log_injection_attempt for SSRF."""
        event = audit_service.log_injection_attempt(
            threat_type="ssrf",
            input_field="url",
        )

        assert event.event_type == SecurityEventType.THREAT_SSRF_ATTEMPT

    def test_log_injection_attempt_command(self, audit_service):
        """Test log_injection_attempt for command injection."""
        event = audit_service.log_injection_attempt(
            threat_type="command_injection",
            input_field="filename",
        )

        assert event.event_type == SecurityEventType.THREAT_COMMAND_INJECTION

    def test_log_config_change(self, audit_service):
        """Test log_config_change convenience method."""
        event = audit_service.log_config_change(
            user_id="admin-123",
            config_key="rate_limit.max_requests",
            old_value=100,
            new_value=200,
        )

        assert event.event_type == SecurityEventType.CONFIG_CHANGE
        assert event.details["config_key"] == "rate_limit.max_requests"
        assert event.details["old_value"] == "100"
        assert event.details["new_value"] == "200"

    def test_log_admin_action_user_create(self, audit_service):
        """Test log_admin_action for user creation."""
        event = audit_service.log_admin_action(
            user_id="admin-123",
            action="user_create",
            target_user="newuser@example.com",
        )

        assert event.event_type == SecurityEventType.ADMIN_USER_CREATE
        assert event.details["target_user"] == "newuser@example.com"

    def test_log_admin_action_user_delete(self, audit_service):
        """Test log_admin_action for user deletion."""
        event = audit_service.log_admin_action(
            user_id="admin-123",
            action="user_delete",
            target_user="deleted@example.com",
        )

        assert event.event_type == SecurityEventType.ADMIN_USER_DELETE

    def test_log_admin_action_policy_change(self, audit_service):
        """Test log_admin_action for policy change."""
        event = audit_service.log_admin_action(
            user_id="admin-123",
            action="policy_change",
            details={"policy": "password_policy", "change": "increase_length"},
        )

        assert event.event_type == SecurityEventType.ADMIN_POLICY_CHANGE


# ============================================================================
# Statistics Tests
# ============================================================================


class TestStatistics:
    """Tests for statistics tracking."""

    def test_stats_initialization(self, audit_service):
        """Test stats are initialized correctly."""
        stats = audit_service.get_stats()

        assert stats["total_events"] == 0
        assert stats["by_type"] == {}
        assert "info" in stats["by_severity"]
        assert stats["by_severity"]["info"] == 0

    def test_stats_increment_on_event(self, audit_service):
        """Test stats increment when event is logged."""
        audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test",
        )

        stats = audit_service.get_stats()
        assert stats["total_events"] == 1
        assert stats["by_type"]["auth.login.success"] == 1
        assert stats["by_severity"]["info"] == 1

    def test_stats_multiple_events(self, audit_service):
        """Test stats with multiple events."""
        audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test 1",
        )
        audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_FAILURE,
            message="Test 2",
        )
        audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test 3",
        )

        stats = audit_service.get_stats()
        assert stats["total_events"] == 3
        assert stats["by_type"]["auth.login.success"] == 2
        assert stats["by_type"]["auth.login.failure"] == 1
        assert stats["by_severity"]["info"] == 2
        assert stats["by_severity"]["medium"] == 1

    def test_stats_reset(self, audit_service):
        """Test statistics reset."""
        audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test",
        )
        audit_service.reset_stats()

        stats = audit_service.get_stats()
        assert stats["total_events"] == 0
        assert stats["by_type"] == {}


# ============================================================================
# Singleton Tests
# ============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_audit_service_returns_instance(self):
        """Test get_audit_service returns an instance."""
        service = get_audit_service()
        assert isinstance(service, SecurityAuditService)

    def test_get_audit_service_singleton(self):
        """Test get_audit_service returns same instance."""
        service1 = get_audit_service()
        service2 = get_audit_service()
        assert service1 is service2


# ============================================================================
# Convenience Function Tests
# ============================================================================


class TestConvenienceFunction:
    """Tests for log_security_event convenience function."""

    def test_log_security_event_function(self):
        """Test log_security_event convenience function."""
        event = log_security_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test login",
        )

        assert isinstance(event, SecurityEvent)
        assert event.event_type == SecurityEventType.AUTH_LOGIN_SUCCESS

    def test_log_security_event_with_context(self):
        """Test log_security_event with context."""
        context = SecurityContext(
            user_id="user-123",
            ip_address="10.0.0.1",
        )

        event = log_security_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test login",
            context=context,
        )

        assert event.context.user_id == "user-123"


# ============================================================================
# Event Type Coverage Tests
# ============================================================================


class TestEventTypeCoverage:
    """Tests to ensure all event types work correctly."""

    @pytest.mark.parametrize(
        "event_type",
        [
            SecurityEventType.AUTH_LOGIN_SUCCESS,
            SecurityEventType.AUTH_LOGIN_FAILURE,
            SecurityEventType.AUTH_LOGOUT,
            SecurityEventType.AUTH_TOKEN_REFRESH,
            SecurityEventType.AUTH_TOKEN_INVALID,
            SecurityEventType.AUTH_TOKEN_EXPIRED,
            SecurityEventType.AUTH_MFA_SUCCESS,
            SecurityEventType.AUTH_MFA_FAILURE,
            SecurityEventType.AUTHZ_ACCESS_GRANTED,
            SecurityEventType.AUTHZ_ACCESS_DENIED,
            SecurityEventType.AUTHZ_PRIVILEGE_ESCALATION,
            SecurityEventType.AUTHZ_ROLE_CHANGE,
            SecurityEventType.RATE_LIMIT_EXCEEDED,
            SecurityEventType.RATE_LIMIT_WARNING,
            SecurityEventType.INPUT_VALIDATION_FAILURE,
            SecurityEventType.INPUT_INJECTION_ATTEMPT,
            SecurityEventType.INPUT_XSS_ATTEMPT,
            SecurityEventType.INPUT_PATH_TRAVERSAL,
            SecurityEventType.THREAT_PROMPT_INJECTION,
            SecurityEventType.THREAT_SSRF_ATTEMPT,
            SecurityEventType.THREAT_COMMAND_INJECTION,
            SecurityEventType.THREAT_SECRETS_EXPOSURE,
            SecurityEventType.CONFIG_CHANGE,
            SecurityEventType.CONFIG_SENSITIVE_ACCESS,
            SecurityEventType.ADMIN_USER_CREATE,
            SecurityEventType.ADMIN_USER_DELETE,
            SecurityEventType.ADMIN_USER_MODIFY,
            SecurityEventType.ADMIN_POLICY_CHANGE,
            SecurityEventType.DATA_ACCESS,
            SecurityEventType.DATA_EXPORT,
            SecurityEventType.DATA_DELETE,
            SecurityEventType.SYSTEM_STARTUP,
            SecurityEventType.SYSTEM_SHUTDOWN,
            SecurityEventType.SYSTEM_ERROR,
        ],
    )
    def test_all_event_types_can_be_logged(self, audit_service, event_type):
        """Test that all event types can be logged successfully."""
        event = audit_service.log_event(
            event_type=event_type,
            message=f"Test event for {event_type.value}",
        )

        assert event.event_type == event_type
        assert event.event_id is not None
        assert event.timestamp is not None


# ============================================================================
# Environment Handling Tests
# ============================================================================


class TestEnvironmentHandling:
    """Tests for environment handling."""

    def test_default_environment(self):
        """Test default environment is used."""
        _service = SecurityAuditService(
            enable_console=False,
            enable_file=False,
        )
        # Should use ENVIRONMENT env var or default to "dev"

    def test_context_environment_inherited(self, audit_service):
        """Test context inherits environment from service."""
        event = audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test",
        )

        assert event.context.environment == "test"

    def test_context_environment_preserved(self, audit_service):
        """Test existing context environment is preserved."""
        context = SecurityContext(environment="production")
        event = audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test",
            context=context,
        )

        assert event.context.environment == "production"

    def test_context_environment_set_when_none(self, audit_service):
        """Test environment is set when context has None."""
        context = SecurityContext(
            user_id="user-123",
            environment=None,
        )
        event = audit_service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test",
            context=context,
        )

        assert event.context.environment == "test"


class TestFileLogging:
    """Tests for file logging functionality."""

    def test_file_logging_enabled(self, tmp_path):
        """Test file logging with enable_file=True - lines 217-223."""
        log_file = tmp_path / "audit" / "security.log"

        service = SecurityAuditService(
            service_name="test-service",
            environment="test",
            enable_console=False,
            enable_file=True,
            log_file_path=str(log_file),
        )

        event = service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test file logging",
        )

        assert event is not None
        # Log file should be created
        assert log_file.parent.exists()

    def test_file_logging_invalid_path(self):
        """Test file logging with invalid path - line 223 exception handler."""
        service = SecurityAuditService(
            service_name="test-service",
            environment="test",
            enable_console=False,
            enable_file=True,
            log_file_path="/invalid/readonly/path/that/cannot/exist/audit.log",
        )

        # Should not raise, just log warning
        event = service.log_event(
            event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
            message="Test",
        )
        assert event is not None
