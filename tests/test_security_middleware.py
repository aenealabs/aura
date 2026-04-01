"""
Project Aura - Security Middleware Tests

Tests for the security middleware covering:
- Security headers
- Request ID tracking
- Request size limits
- Secure exception handling

Author: Project Aura Team
Created: 2025-12-12
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.api.security_middleware import (
    RequestIDMiddleware,
    RequestSizeLimitMiddleware,
    SecureExceptionMiddleware,
    SecurityHeadersMiddleware,
    add_security_middleware,
    get_request_id,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def base_app():
    """Create a basic FastAPI app for testing."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    @app.post("/data")
    async def data_endpoint(request: Request):
        body = await request.body()
        return {"received": len(body)}

    @app.get("/request-id")
    async def request_id_endpoint(request: Request):
        return {"request_id": getattr(request.state, "request_id", None)}

    return app


# ============================================================================
# Security Headers Tests
# ============================================================================


class TestSecurityHeaders:
    """Tests for security headers middleware."""

    def test_security_headers_present(self, base_app):
        """Test that all security headers are present."""
        base_app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(base_app)

        response = client.get("/test")

        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "strict-origin" in response.headers["Referrer-Policy"]
        assert "Content-Security-Policy" in response.headers
        assert "Permissions-Policy" in response.headers

    def test_hsts_header_when_enabled(self, base_app):
        """Test HSTS header is present when enabled."""
        base_app.add_middleware(SecurityHeadersMiddleware, enable_hsts=True)
        client = TestClient(base_app)

        response = client.get("/test")

        assert "Strict-Transport-Security" in response.headers
        assert "max-age=" in response.headers["Strict-Transport-Security"]
        assert "includeSubDomains" in response.headers["Strict-Transport-Security"]

    def test_custom_frame_options(self, base_app):
        """Test custom X-Frame-Options value."""
        base_app.add_middleware(SecurityHeadersMiddleware, frame_options="SAMEORIGIN")
        client = TestClient(base_app)

        response = client.get("/test")

        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"

    def test_custom_csp(self, base_app):
        """Test custom Content-Security-Policy."""
        custom_csp = "default-src 'self'"
        base_app.add_middleware(
            SecurityHeadersMiddleware, content_security_policy=custom_csp
        )
        client = TestClient(base_app)

        response = client.get("/test")

        assert response.headers["Content-Security-Policy"] == custom_csp

    def test_custom_headers(self, base_app):
        """Test additional custom headers."""
        base_app.add_middleware(
            SecurityHeadersMiddleware,
            custom_headers={"X-Custom-Header": "custom-value"},
        )
        client = TestClient(base_app)

        response = client.get("/test")

        assert response.headers["X-Custom-Header"] == "custom-value"

    def test_cache_control_default(self, base_app):
        """Test default Cache-Control header."""
        base_app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(base_app)

        response = client.get("/test")

        assert "no-store" in response.headers["Cache-Control"]
        assert "private" in response.headers["Cache-Control"]


# ============================================================================
# Request ID Tests
# ============================================================================


class TestRequestID:
    """Tests for request ID middleware."""

    def test_request_id_generated(self, base_app):
        """Test that request ID is generated."""
        base_app.add_middleware(RequestIDMiddleware)
        client = TestClient(base_app)

        response = client.get("/test")

        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 36  # UUID length

    def test_request_id_in_state(self, base_app):
        """Test that request ID is available in request state."""
        base_app.add_middleware(RequestIDMiddleware)
        client = TestClient(base_app)

        response = client.get("/request-id")

        data = response.json()
        assert data["request_id"] is not None
        assert data["request_id"] == response.headers["X-Request-ID"]

    def test_incoming_request_id_used(self, base_app):
        """Test that incoming X-Request-ID is used."""
        base_app.add_middleware(RequestIDMiddleware)
        client = TestClient(base_app)

        custom_id = "custom-request-id-12345"
        response = client.get("/test", headers={"X-Request-ID": custom_id})

        assert response.headers["X-Request-ID"] == custom_id

    def test_unique_ids_per_request(self, base_app):
        """Test that each request gets a unique ID."""
        base_app.add_middleware(RequestIDMiddleware)
        client = TestClient(base_app)

        response1 = client.get("/test")
        response2 = client.get("/test")

        id1 = response1.headers["X-Request-ID"]
        id2 = response2.headers["X-Request-ID"]
        assert id1 != id2


# ============================================================================
# Request Size Limit Tests
# ============================================================================


class TestRequestSizeLimit:
    """Tests for request size limit middleware."""

    def test_small_request_allowed(self, base_app):
        """Test that small requests are allowed."""
        base_app.add_middleware(RequestSizeLimitMiddleware, max_content_length=1000)
        client = TestClient(base_app)

        response = client.post("/data", content=b"x" * 100)

        assert response.status_code == 200
        assert response.json()["received"] == 100

    def test_large_request_rejected(self, base_app):
        """Test that large requests are rejected."""
        base_app.add_middleware(RequestSizeLimitMiddleware, max_content_length=100)
        client = TestClient(base_app)

        response = client.post(
            "/data",
            content=b"x" * 200,
            headers={"Content-Length": "200"},
        )

        assert response.status_code == 413
        assert "Request Entity Too Large" in response.json()["error"]

    def test_exact_limit_allowed(self, base_app):
        """Test that requests at exact limit are allowed."""
        base_app.add_middleware(RequestSizeLimitMiddleware, max_content_length=100)
        client = TestClient(base_app)

        response = client.post("/data", content=b"x" * 100)

        assert response.status_code == 200

    def test_default_limit(self):
        """Test default size limit is 10MB."""
        app = FastAPI()
        middleware = RequestSizeLimitMiddleware(app)
        assert middleware.max_content_length == 10 * 1024 * 1024


# ============================================================================
# Secure Exception Handler Tests
# ============================================================================


class TestSecureExceptionHandler:
    """Tests for secure exception handling middleware."""

    def test_exception_returns_500(self, base_app):
        """Test that exceptions return 500 status."""
        base_app.add_middleware(SecureExceptionMiddleware)
        client = TestClient(base_app, raise_server_exceptions=False)

        response = client.get("/error")

        assert response.status_code == 500

    def test_exception_hides_details(self, base_app):
        """Test that exception details are hidden in production mode."""
        base_app.add_middleware(SecureExceptionMiddleware, debug=False)
        client = TestClient(base_app, raise_server_exceptions=False)

        response = client.get("/error")

        data = response.json()
        assert "Test error" not in data.get("message", "")
        assert "ValueError" not in str(data)
        assert "debug" not in data

    def test_exception_shows_details_in_debug(self, base_app):
        """Test that exception details are shown in debug mode."""
        base_app.add_middleware(SecureExceptionMiddleware, debug=True)
        client = TestClient(base_app, raise_server_exceptions=False)

        response = client.get("/error")

        data = response.json()
        assert "debug" in data
        assert data["debug"]["exception"] == "ValueError"
        assert "Test error" in data["debug"]["message"]

    def test_request_id_in_error_response(self, base_app):
        """Test that request ID is included in error response."""
        base_app.add_middleware(RequestIDMiddleware)
        base_app.add_middleware(SecureExceptionMiddleware, include_request_id=True)
        client = TestClient(base_app, raise_server_exceptions=False)

        response = client.get("/error")

        data = response.json()
        assert "request_id" in data

    def test_generic_error_message(self, base_app):
        """Test that generic error message is returned."""
        base_app.add_middleware(SecureExceptionMiddleware)
        client = TestClient(base_app, raise_server_exceptions=False)

        response = client.get("/error")

        data = response.json()
        assert "Internal Server Error" in data["error"]
        assert "unexpected error" in data["message"].lower()


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for all middleware together."""

    def test_add_security_middleware_helper(self, base_app):
        """Test the add_security_middleware helper function."""
        add_security_middleware(
            base_app,
            enable_hsts=True,
            max_content_length=1024,
            debug=False,
        )
        client = TestClient(base_app)

        response = client.get("/test")

        # Check all middleware is active
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers

    def test_middleware_order(self, base_app):
        """Test that middleware executes in correct order."""
        add_security_middleware(base_app)
        client = TestClient(base_app, raise_server_exceptions=False)

        response = client.get("/error")

        # Should have request ID even on error
        assert "X-Request-ID" in response.headers
        # Should have security headers even on error
        assert "X-Content-Type-Options" in response.headers

    def test_all_security_headers_on_error(self, base_app):
        """Test that security headers are present even on errors."""
        add_security_middleware(base_app)
        client = TestClient(base_app, raise_server_exceptions=False)

        response = client.get("/error")

        assert response.status_code == 500
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"


# ============================================================================
# Context Variable Tests
# ============================================================================


class TestContextVariable:
    """Tests for request ID context variable."""

    def test_get_request_id_default(self):
        """Test get_request_id returns empty string by default."""
        # Outside of request context
        assert get_request_id() == ""
