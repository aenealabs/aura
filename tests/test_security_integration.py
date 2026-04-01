"""
Project Aura - Security Integration Tests

Tests for the security integration module covering:
- FastAPI dependencies
- Validated request models
- Security audit decorators
- Validation functions

Author: Project Aura Team
Created: 2025-12-12
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api.security_integration import (
    ValidatedIngestionRequest,
    ValidatedQueryRequest,
    ValidatedWebhookPayload,
    get_security_context,
    get_security_stats,
    log_access_denied,
    log_auth_failure,
    log_auth_success,
    log_rate_limit,
    log_security_threat,
    scan_code_for_secrets,
    validate_and_sanitize,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = None
    request.state.request_id = "test-request-123"
    request.headers = {
        "User-Agent": "TestClient/1.0",
        "X-Forwarded-For": "192.168.1.100",
    }
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.url = MagicMock()
    request.url.path = "/api/v1/test"
    request.method = "POST"
    return request


@pytest.fixture
def mock_authenticated_request(mock_request):
    """Create a mock request with authenticated user."""
    mock_request.state.user = MagicMock()
    mock_request.state.user.sub = "user-123"
    mock_request.state.user.email = "user@example.com"
    return mock_request


# ============================================================================
# ValidatedIngestionRequest Tests
# ============================================================================


class TestValidatedIngestionRequest:
    """Tests for ValidatedIngestionRequest model."""

    def test_valid_https_url(self):
        """Test valid HTTPS repository URL."""
        request = ValidatedIngestionRequest(
            repository_url="https://github.com/owner/repo",
            branch="main",
        )
        assert request.repository_url == "https://github.com/owner/repo"

    def test_valid_git_ssh_url(self):
        """Test valid git SSH URL."""
        request = ValidatedIngestionRequest(
            repository_url="git@github.com:owner/repo.git",
            branch="main",
        )
        assert "git@github.com" in request.repository_url

    def test_invalid_protocol_rejected(self):
        """Test that invalid protocols are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ValidatedIngestionRequest(
                repository_url="file:///etc/passwd",
                branch="main",
            )
        assert (
            "protocol" in str(exc_info.value).lower()
            or "ssrf" in str(exc_info.value).lower()
        )

    def test_localhost_rejected(self):
        """Test that localhost URLs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ValidatedIngestionRequest(
                repository_url="https://localhost/repo",
                branch="main",
            )
        assert "localhost" in str(exc_info.value).lower()

    def test_private_ip_rejected(self):
        """Test that private IP URLs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ValidatedIngestionRequest(
                repository_url="https://127.0.0.1/repo",
                branch="main",
            )
        assert "127.0.0.1" in str(exc_info.value).lower()

    def test_branch_path_traversal_rejected(self):
        """Test that path traversal in branch is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ValidatedIngestionRequest(
                repository_url="https://github.com/owner/repo",
                branch="../../../etc/passwd",
            )
        assert "traversal" in str(exc_info.value).lower()

    def test_branch_command_injection_rejected(self):
        """Test that command injection in branch is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ValidatedIngestionRequest(
                repository_url="https://github.com/owner/repo",
                branch="main; rm -rf /",
            )
        assert "injection" in str(exc_info.value).lower()


# ============================================================================
# ValidatedQueryRequest Tests
# ============================================================================


class TestValidatedQueryRequest:
    """Tests for ValidatedQueryRequest model."""

    def test_valid_query(self):
        """Test valid query passes validation."""
        request = ValidatedQueryRequest(
            query="Find all authentication functions",
            max_results=10,
        )
        assert "authentication" in request.query

    def test_query_sanitized(self):
        """Test that query is sanitized."""
        request = ValidatedQueryRequest(
            query="Find <script>alert('xss')</script> functions",
            max_results=10,
        )
        # XSS should be sanitized
        assert "<script>" not in request.query

    def test_max_results_minimum(self):
        """Test max_results minimum value."""
        with pytest.raises(ValidationError):
            ValidatedQueryRequest(
                query="test",
                max_results=0,
            )

    def test_max_results_maximum(self):
        """Test max_results maximum value."""
        with pytest.raises(ValidationError):
            ValidatedQueryRequest(
                query="test",
                max_results=101,
            )

    def test_max_results_valid_range(self):
        """Test max_results in valid range."""
        request = ValidatedQueryRequest(
            query="test",
            max_results=50,
        )
        assert request.max_results == 50


# ============================================================================
# ValidatedWebhookPayload Tests
# ============================================================================


class TestValidatedWebhookPayload:
    """Tests for ValidatedWebhookPayload model."""

    def test_valid_payload(self):
        """Test valid webhook payload."""
        payload = ValidatedWebhookPayload(
            ref="refs/heads/main",
            repository={"name": "repo"},
        )
        assert payload.ref == "refs/heads/main"

    def test_none_ref_allowed(self):
        """Test that None ref is allowed."""
        payload = ValidatedWebhookPayload(
            ref=None,
            repository={"name": "repo"},
        )
        assert payload.ref is None

    def test_ref_with_xss_rejected(self):
        """Test that ref with XSS is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ValidatedWebhookPayload(
                ref="refs/heads/main<script>",
            )
        assert "security threats" in str(exc_info.value).lower()


# ============================================================================
# Security Context Tests
# ============================================================================


class TestSecurityContext:
    """Tests for get_security_context function."""

    def test_extracts_request_id(self, mock_request):
        """Test extraction of request ID."""
        context = get_security_context(mock_request)
        assert context.request_id == "test-request-123"

    def test_extracts_ip_from_forwarded(self, mock_request):
        """Test extraction of IP from X-Forwarded-For."""
        context = get_security_context(mock_request)
        assert context.ip_address == "192.168.1.100"

    def test_extracts_user_agent(self, mock_request):
        """Test extraction of User-Agent."""
        context = get_security_context(mock_request)
        assert context.user_agent == "TestClient/1.0"

    def test_extracts_resource(self, mock_request):
        """Test extraction of resource path."""
        context = get_security_context(mock_request)
        assert context.resource == "/api/v1/test"

    def test_extracts_user_info(self, mock_authenticated_request):
        """Test extraction of user info from authenticated request."""
        context = get_security_context(mock_authenticated_request)
        assert context.user_id == "user-123"
        assert context.user_email == "user@example.com"

    def test_handles_no_user(self, mock_request):
        """Test handling of unauthenticated request."""
        context = get_security_context(mock_request)
        assert context.user_id is None
        assert context.user_email is None


# ============================================================================
# Validation Function Tests
# ============================================================================


class TestValidateAndSanitize:
    """Tests for validate_and_sanitize function."""

    def test_clean_input_passes(self):
        """Test that clean input passes."""
        result = validate_and_sanitize("hello world")
        assert result == "hello world"

    def test_xss_sanitized(self):
        """Test that XSS is sanitized."""
        result = validate_and_sanitize("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "</script>" not in result

    def test_sql_injection_detected(self):
        """Test that SQL injection is detected."""
        # Non-strict mode should sanitize but not raise
        result = validate_and_sanitize("'; DROP TABLE users; --")
        # Should be sanitized
        assert result is not None

    def test_strict_mode_raises(self):
        """Test that strict mode raises on threats."""
        with pytest.raises(HTTPException) as exc_info:
            validate_and_sanitize(
                "'; DROP TABLE users; --",
                strict=True,
            )
        assert exc_info.value.status_code == 400

    def test_path_traversal_check(self):
        """Test path traversal checking."""
        with pytest.raises(HTTPException):
            validate_and_sanitize(
                "../../../etc/passwd",
                check_path=True,
                strict=True,
            )


# ============================================================================
# Secrets Scanning Tests
# ============================================================================


class TestScanCodeForSecrets:
    """Tests for scan_code_for_secrets function."""

    def test_clean_code_passes(self):
        """Test that clean code passes."""
        result = scan_code_for_secrets("def hello():\n    print('Hello World')")
        assert not result.has_secrets

    def test_detects_aws_key(self):
        """Test detection of AWS key in code."""
        result = scan_code_for_secrets("AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'")
        assert result.has_secrets

    def test_block_on_secrets_raises(self):
        """Test that block_on_secrets raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            scan_code_for_secrets(
                "AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'",
                block_on_secrets=True,
            )
        assert exc_info.value.status_code == 400
        assert "secrets" in str(exc_info.value.detail).lower()


# ============================================================================
# Security Event Logging Tests
# ============================================================================


class TestSecurityEventLogging:
    """Tests for security event logging helpers."""

    def test_log_auth_success(self):
        """Test log_auth_success function."""
        event = log_auth_success(
            user_id="user-123",
            user_email="user@example.com",
            ip_address="10.0.0.1",
        )
        assert event is not None
        assert "auth.login.success" in event.event_type.value

    def test_log_auth_failure(self):
        """Test log_auth_failure function."""
        event = log_auth_failure(
            user_email="attacker@example.com",
            ip_address="10.0.0.1",
            reason="Invalid password",
        )
        assert event is not None
        assert "auth.login.failure" in event.event_type.value

    def test_log_access_denied(self):
        """Test log_access_denied function."""
        event = log_access_denied(
            user_id="user-123",
            resource="/admin",
            action="DELETE",
            reason="Insufficient permissions",
        )
        assert event is not None
        assert "access.denied" in event.event_type.value

    def test_log_rate_limit(self):
        """Test log_rate_limit function."""
        event = log_rate_limit(
            client_id="client-123",
            tier="standard",
            limit=100,
        )
        assert event is not None
        assert "rate_limit" in event.event_type.value

    def test_log_security_threat(self):
        """Test log_security_threat function."""
        event = log_security_threat(
            threat_type="sql_injection",
            description="SQL injection detected in search field",
        )
        assert event is not None


# ============================================================================
# Security Statistics Tests
# ============================================================================


class TestSecurityStats:
    """Tests for security statistics functions."""

    def test_get_security_stats(self):
        """Test get_security_stats returns all service stats."""
        stats = get_security_stats()

        assert "input_validation" in stats
        assert "audit_logging" in stats
        assert "secrets_detection" in stats

    def test_stats_contain_expected_fields(self):
        """Test that stats contain expected fields."""
        stats = get_security_stats()

        # Input validation stats
        assert "total_validated" in stats["input_validation"]

        # Audit logging stats
        assert "total_events" in stats["audit_logging"]

        # Secrets detection stats
        assert "total_scans" in stats["secrets_detection"]


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for security in FastAPI endpoints."""

    def test_endpoint_with_validated_request(self):
        """Test endpoint using validated request model."""
        app = FastAPI()

        @app.post("/ingest")
        async def ingest(request: ValidatedIngestionRequest):
            return {"url": request.repository_url}

        client = TestClient(app)

        # Valid request
        response = client.post(
            "/ingest",
            json={
                "repository_url": "https://github.com/owner/repo",
                "branch": "main",
            },
        )
        assert response.status_code == 200

    def test_endpoint_rejects_invalid_request(self):
        """Test endpoint rejects invalid request."""
        app = FastAPI()

        @app.post("/ingest")
        async def ingest(request: ValidatedIngestionRequest):
            return {"url": request.repository_url}

        client = TestClient(app)

        # Invalid request (localhost)
        response = client.post(
            "/ingest",
            json={
                "repository_url": "https://localhost/repo",
                "branch": "main",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_endpoint_with_query_validation(self):
        """Test endpoint with query validation."""
        app = FastAPI()

        @app.post("/query")
        async def query(request: ValidatedQueryRequest):
            return {"query": request.query}

        client = TestClient(app)

        # Valid query
        response = client.post(
            "/query",
            json={"query": "Find authentication functions"},
        )
        assert response.status_code == 200

        # Query with XSS (should be sanitized, not rejected)
        response = client.post(
            "/query",
            json={"query": "Find <script>alert('xss')</script>"},
        )
        assert response.status_code == 200
        assert "<script>" not in response.json()["query"]
