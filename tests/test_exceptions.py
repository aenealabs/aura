"""
Tests for Project Aura centralized exception hierarchy.

Tests the base exception classes and utility functions defined in src/exceptions.py.
"""

import logging

import pytest

from src.exceptions import (
    AgentError,
    ApprovalError,
    AuraError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    DatabaseError,
    InjectionError,
    IntegrationError,
    LLMError,
    OrchestrationError,
    SandboxError,
    SchemaValidationError,
    SecurityError,
    ServiceError,
    ToolExecutionError,
    ValidationError,
    WorkflowError,
    api_error_response,
    handle_exception,
    safe_error_message,
)


class TestAuraErrorBase:
    """Tests for base AuraError class."""

    def test_basic_creation(self):
        """Test creating a basic AuraError."""
        err = AuraError("Something went wrong")
        assert str(err) == "Something went wrong"
        assert err.message == "Something went wrong"
        assert err.error_code is None
        assert err.context == {}

    def test_with_error_code(self):
        """Test AuraError with error code."""
        err = AuraError("Failed", error_code="ERR_001")
        assert str(err) == "[ERR_001] Failed"
        assert err.error_code == "ERR_001"

    def test_with_context(self):
        """Test AuraError with context."""
        err = AuraError("Failed", context={"user_id": "123", "operation": "test"})
        assert err.context == {"user_id": "123", "operation": "test"}

    def test_to_dict_basic(self):
        """Test converting error to dict."""
        err = AuraError("Failed", error_code="ERR_001")
        result = err.to_dict()
        assert result == {
            "error": "AuraError",
            "message": "Failed",
            "code": "ERR_001",
        }

    def test_to_dict_with_context(self):
        """Test to_dict includes context when requested."""
        err = AuraError("Failed", context={"key": "value"})
        result = err.to_dict(include_context=True)
        assert result["context"] == {"key": "value"}

    def test_sanitize_context_redacts_sensitive(self):
        """Test that sensitive keys are redacted."""
        err = AuraError(
            "Failed",
            context={
                "user_id": "123",
                "password": "secret123",
                "api_token": "abc",
                "authorization_header": "Bearer xyz",
            },
        )
        sanitized = err._sanitize_context()
        assert sanitized["user_id"] == "123"
        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["api_token"] == "***REDACTED***"
        assert sanitized["authorization_header"] == "***REDACTED***"

    def test_log_method(self, caplog):
        """Test the log method logs appropriately."""
        err = AuraError("Test error", context={"info": "test"})
        with caplog.at_level(logging.ERROR):
            err.log()
        assert "Test error" in caplog.text


class TestValidationErrors:
    """Tests for validation error classes."""

    def test_validation_error_with_field(self):
        """Test ValidationError stores field name."""
        err = ValidationError("Invalid value", field="username")
        assert err.field == "username"
        assert err.context["field"] == "username"
        assert err.error_code == "VALIDATION_ERROR"

    def test_schema_validation_error(self):
        """Test SchemaValidationError stores schema errors."""
        schema_errors = [{"path": "$.name", "message": "required"}]
        err = SchemaValidationError("Schema invalid", schema_errors=schema_errors)
        assert err.context["schema_errors"] == schema_errors
        assert err.error_code == "SCHEMA_VALIDATION_ERROR"


class TestServiceErrors:
    """Tests for service error classes."""

    def test_service_error_with_name(self):
        """Test ServiceError stores service name."""
        err = ServiceError("Connection failed", service_name="neptune")
        assert err.service_name == "neptune"
        assert err.context["service"] == "neptune"

    def test_database_error(self):
        """Test DatabaseError with operation."""
        err = DatabaseError("Query failed", database="neptune", operation="read")
        assert err.service_name == "neptune"
        assert err.operation == "read"
        assert err.error_code == "DATABASE_ERROR"

    def test_llm_error(self):
        """Test LLMError with model_id."""
        err = LLMError("Model unavailable", model_id="claude-3-sonnet")
        assert err.model_id == "claude-3-sonnet"
        assert err.service_name == "bedrock"

    def test_integration_error(self):
        """Test IntegrationError with status code."""
        err = IntegrationError("API failed", integration="github", status_code=429)
        assert err.service_name == "github"
        assert err.status_code == 429


class TestSecurityErrors:
    """Tests for security error classes."""

    def test_security_error_base(self):
        """Test basic SecurityError."""
        err = SecurityError("Access denied")
        assert err.error_code == "SECURITY_ERROR"

    def test_authentication_error(self):
        """Test AuthenticationError."""
        err = AuthenticationError("Invalid token")
        assert err.error_code == "AUTHENTICATION_ERROR"

    def test_authorization_error(self):
        """Test AuthorizationError with permission."""
        err = AuthorizationError("Permission denied", required_permission="admin:write")
        assert err.required_permission == "admin:write"
        assert err.error_code == "AUTHORIZATION_ERROR"

    def test_injection_error(self):
        """Test InjectionError with type."""
        err = InjectionError(
            "Prompt injection detected", injection_type="system_override"
        )
        assert err.injection_type == "system_override"
        assert err.error_code == "INJECTION_ERROR"


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_configuration_error(self):
        """Test ConfigurationError with config key."""
        err = ConfigurationError("Missing config", config_key="database.host")
        assert err.config_key == "database.host"
        assert err.error_code == "CONFIGURATION_ERROR"


class TestAgentErrors:
    """Tests for agent error classes."""

    def test_agent_error(self):
        """Test AgentError with agent name."""
        err = AgentError("Agent failed", agent_name="coder-agent")
        assert err.agent_name == "coder-agent"
        assert err.error_code == "AGENT_ERROR"

    def test_tool_execution_error(self):
        """Test ToolExecutionError."""
        err = ToolExecutionError(
            "Tool crashed", tool_name="code_search", agent_name="coder"
        )
        assert err.tool_name == "code_search"
        assert err.agent_name == "coder"
        assert err.error_code == "TOOL_EXECUTION_ERROR"

    def test_orchestration_error(self):
        """Test OrchestrationError with workflow_id."""
        err = OrchestrationError("Workflow failed", workflow_id="wf-123")
        assert err.workflow_id == "wf-123"
        assert err.error_code == "ORCHESTRATION_ERROR"


class TestWorkflowErrors:
    """Tests for workflow error classes."""

    def test_workflow_error(self):
        """Test WorkflowError with name."""
        err = WorkflowError("Workflow error", workflow_name="patch_review")
        assert err.workflow_name == "patch_review"

    def test_approval_error(self):
        """Test ApprovalError with approval_id."""
        err = ApprovalError("Approval failed", approval_id="apr-456")
        assert err.approval_id == "apr-456"
        assert err.workflow_name == "hitl_approval"
        assert err.error_code == "APPROVAL_ERROR"

    def test_sandbox_error(self):
        """Test SandboxError with sandbox_id."""
        err = SandboxError("Sandbox failed", sandbox_id="sb-789")
        assert err.sandbox_id == "sb-789"
        assert err.workflow_name == "sandbox"
        assert err.error_code == "SANDBOX_ERROR"


class TestExceptionHierarchy:
    """Tests verifying the exception hierarchy."""

    def test_all_inherit_from_aura_error(self):
        """All custom exceptions should inherit from AuraError."""
        exceptions = [
            ValidationError("test"),
            SchemaValidationError("test"),
            ServiceError("test"),
            DatabaseError("test"),
            LLMError("test"),
            IntegrationError("test"),
            SecurityError("test"),
            AuthenticationError("test"),
            AuthorizationError("test"),
            InjectionError("test"),
            ConfigurationError("test"),
            AgentError("test"),
            ToolExecutionError("test"),
            OrchestrationError("test"),
            WorkflowError("test"),
            ApprovalError("test"),
            SandboxError("test"),
        ]
        for exc in exceptions:
            assert isinstance(
                exc, AuraError
            ), f"{type(exc).__name__} should inherit AuraError"
            assert isinstance(exc, Exception)

    def test_specific_hierarchies(self):
        """Test specific inheritance chains."""
        assert isinstance(DatabaseError("test"), ServiceError)
        assert isinstance(LLMError("test"), ServiceError)
        assert isinstance(IntegrationError("test"), ServiceError)

        assert isinstance(AuthenticationError("test"), SecurityError)
        assert isinstance(AuthorizationError("test"), SecurityError)
        assert isinstance(InjectionError("test"), SecurityError)

        assert isinstance(ToolExecutionError("test"), AgentError)
        assert isinstance(OrchestrationError("test"), AgentError)

        assert isinstance(ApprovalError("test"), WorkflowError)
        assert isinstance(SandboxError("test"), WorkflowError)


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_handle_exception_aura_error(self, caplog):
        """Test handle_exception with AuraError."""
        err = ValidationError("Invalid input")
        with pytest.raises(ValidationError):
            with caplog.at_level(logging.ERROR):
                handle_exception(err, logging.getLogger(__name__))

    def test_handle_exception_unknown_wraps(self, caplog):
        """Test handle_exception wraps unknown exceptions."""
        err = ValueError("Some value error")
        with pytest.raises(ServiceError) as exc_info:
            with caplog.at_level(logging.ERROR):
                handle_exception(err, logging.getLogger(__name__))
        assert exc_info.value.error_code == "UNEXPECTED_ERROR"
        assert "ValueError" in exc_info.value.context["error_type"]

    def test_handle_exception_no_reraise(self):
        """Test handle_exception with reraise=False."""
        err = ValueError("Some error")
        result = handle_exception(err, logging.getLogger(__name__), reraise=False)
        assert isinstance(result, ServiceError)

    def test_safe_error_message_aura_error(self):
        """Test safe_error_message with AuraError."""
        err = ValidationError("Missing field 'name'")
        msg = safe_error_message(err, "input validation")
        assert msg == "Missing field 'name'"

    def test_safe_error_message_aura_error_with_type(self):
        """Test safe_error_message with include_type."""
        err = ValidationError("Missing field")
        msg = safe_error_message(err, "input validation", include_type=True)
        assert msg == "ValidationError: Missing field"

    def test_safe_error_message_generic_error(self):
        """Test safe_error_message with generic exception."""
        err = ValueError("secret=abc123")
        msg = safe_error_message(err, "user lookup")
        # Should NOT include the actual error message
        assert msg == "Error during user lookup"
        assert "secret" not in msg

    def test_safe_error_message_generic_with_type(self):
        """Test safe_error_message generic with type."""
        err = KeyError("missing_key")
        msg = safe_error_message(err, "config lookup", include_type=True)
        assert msg == "Error during config lookup: KeyError"
        assert "missing_key" not in msg

    def test_api_error_response_aura_error(self, caplog):
        """Test api_error_response with AuraError."""
        err = ValidationError("Invalid email format", field="email")
        with caplog.at_level(logging.ERROR):
            result = api_error_response(
                err, logging.getLogger(__name__), "user registration"
            )
        assert result["error"] == "ValidationError"
        assert result["message"] == "Invalid email format"
        assert result["operation"] == "user registration"

    def test_api_error_response_generic_error(self, caplog):
        """Test api_error_response with generic exception."""
        err = RuntimeError("Internal details: password=secret123")
        with caplog.at_level(logging.ERROR):
            result = api_error_response(
                err, logging.getLogger(__name__), "authentication"
            )
        assert result["error"] == "InternalError"
        assert "password" not in result["message"]
        assert "secret" not in result["message"]
        assert result["message"] == "Error during authentication"


class TestSensitiveDataLeakage:
    """Tests to verify no sensitive data leaks in error messages."""

    @pytest.mark.parametrize(
        "sensitive_key",
        [
            "password",
            "token",
            "secret",
            "api_key",
            "credential",
            "private_key",
            "access_key",
        ],
    )
    def test_context_sanitization(self, sensitive_key):
        """Test that all sensitive keys are sanitized."""
        err = AuraError("Test", context={sensitive_key: "sensitive_value"})
        sanitized = err._sanitize_context()
        assert sanitized[sensitive_key] == "***REDACTED***"

    def test_nested_sensitive_keys(self):
        """Test sensitive keys with prefixes/suffixes are sanitized."""
        err = AuraError(
            "Test",
            context={
                "user_password": "secret1",
                "api_token_header": "secret2",
                "github_secret": "secret3",
            },
        )
        sanitized = err._sanitize_context()
        assert sanitized["user_password"] == "***REDACTED***"
        assert sanitized["api_token_header"] == "***REDACTED***"
        assert sanitized["github_secret"] == "***REDACTED***"

    def test_safe_error_message_never_leaks(self):
        """Test that safe_error_message never leaks internal details."""
        # Create exception with sensitive internal message
        err = RuntimeError(
            "Database error: password='admin123', host='internal.db.local'"
        )
        msg = safe_error_message(err, "database operation")
        # Message should be generic
        assert "password" not in msg.lower()
        assert "admin123" not in msg
        assert "internal.db.local" not in msg
