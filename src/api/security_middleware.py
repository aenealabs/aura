"""
Project Aura - Security Middleware

Provides security middleware for FastAPI applications:
- Security headers (OWASP recommended)
- Request ID tracking for audit trails
- Request size limits
- Secure exception handling

Author: Project Aura Team
Created: 2025-12-12
"""

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any, Callable, cast

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Context variable for request ID (thread-safe)
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_ctx.get()


# =============================================================================
# Security Headers Middleware
# =============================================================================


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    Implements OWASP security headers recommendations:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Legacy XSS protection for older browsers
    - Strict-Transport-Security: Enforces HTTPS
    - Content-Security-Policy: Controls resource loading
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Controls browser features
    - Cache-Control: Prevents caching of sensitive data
    """

    def __init__(
        self,
        app: ASGIApp,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,  # 1 year
        frame_options: str = "DENY",
        content_security_policy: str | None = None,
        custom_headers: dict[str, str] | None = None,
    ):
        """
        Initialize security headers middleware.

        Args:
            app: The ASGI application
            enable_hsts: Enable HTTP Strict Transport Security
            hsts_max_age: HSTS max-age in seconds
            frame_options: X-Frame-Options value (DENY, SAMEORIGIN)
            content_security_policy: Custom CSP header value
            custom_headers: Additional custom security headers
        """
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.frame_options = frame_options
        self.custom_headers = custom_headers or {}

        # Default CSP for API (restrictive)
        self.csp = content_security_policy or (
            "default-src 'none'; "
            "frame-ancestors 'none'; "
            "form-action 'none'; "
            "base-uri 'none'"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add security headers to response."""
        response: Response = cast(Response, await call_next(request))

        # Core security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = self.frame_options
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = self.csp

        # Permissions Policy (formerly Feature-Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )

        # HSTS (only in production/HTTPS)
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )

        # Cache control for API responses (prevent caching sensitive data)
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, private"
            )

        # Add custom headers
        for header, value in self.custom_headers.items():
            response.headers[header] = value

        return response


# =============================================================================
# Request ID Middleware
# =============================================================================


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add unique request IDs for tracking and audit trails.

    - Generates UUID for each request
    - Adds X-Request-ID header to response
    - Stores in context for logging
    - Accepts incoming X-Request-ID for distributed tracing
    """

    HEADER_NAME = "X-Request-ID"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with unique ID tracking."""
        # Use incoming request ID if provided (for distributed tracing)
        # Otherwise generate a new one
        request_id = request.headers.get(self.HEADER_NAME)
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store in context for use in logging
        token = request_id_ctx.set(request_id)

        # Store on request state for access in endpoints
        request.state.request_id = request_id

        # Record start time for request duration
        start_time = time.time()

        try:
            response: Response = cast(Response, await call_next(request))

            # Add request ID to response headers
            response.headers[self.HEADER_NAME] = request_id

            # Log request completion
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"status={response.status_code} duration={duration_ms:.2f}ms "
                f"request_id={request_id}"
            )

            return response

        finally:
            # Reset context
            request_id_ctx.reset(token)


# =============================================================================
# Request Size Limit Middleware
# =============================================================================


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit request body size.

    Prevents denial of service via oversized requests.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_content_length: int = 10 * 1024 * 1024,  # 10 MB default
    ):
        """
        Initialize request size limit middleware.

        Args:
            app: The ASGI application
            max_content_length: Maximum allowed content length in bytes
        """
        super().__init__(app)
        self.max_content_length = max_content_length

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check request size before processing."""
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                size = int(content_length)
                if size > self.max_content_length:
                    logger.warning(
                        f"Request rejected: Content-Length {size} exceeds "
                        f"limit {self.max_content_length}"
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "Request Entity Too Large",
                            "detail": f"Maximum content length is {self.max_content_length} bytes",
                        },
                    )
            except ValueError:
                # Invalid content-length header
                pass

        return cast(Response, await call_next(request))


# =============================================================================
# Secure Exception Handler
# =============================================================================


class SecureExceptionMiddleware(BaseHTTPMiddleware):
    """
    Middleware for secure exception handling.

    Prevents information leakage by:
    - Catching unhandled exceptions
    - Returning generic error messages
    - Logging full details server-side
    - Including request ID for correlation
    """

    def __init__(
        self,
        app: ASGIApp,
        debug: bool = False,
        include_request_id: bool = True,
    ):
        """
        Initialize secure exception middleware.

        Args:
            app: The ASGI application
            debug: If True, include stack traces in responses (dev only)
            include_request_id: Include request ID in error responses
        """
        super().__init__(app)
        self.debug = debug
        self.include_request_id = include_request_id

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle exceptions securely."""
        try:
            return cast(Response, await call_next(request))
        except Exception as e:
            # Get request ID for correlation
            request_id = getattr(request.state, "request_id", "unknown")

            # Log full exception details server-side
            logger.exception(
                f"Unhandled exception: {type(e).__name__}: {e} "
                f"request_id={request_id} "
                f"path={request.url.path}"
            )

            # Build error response
            error_response: dict[str, Any] = {
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later.",
            }

            if self.include_request_id:
                error_response["request_id"] = request_id

            # In debug mode, include exception details
            if self.debug:
                error_response["debug"] = {
                    "exception": type(e).__name__,
                    "message": str(e),
                }

            return JSONResponse(
                status_code=500,
                content=error_response,
            )


# =============================================================================
# Helper Function to Add All Security Middleware
# =============================================================================


def add_security_middleware(
    app: FastAPI,
    enable_hsts: bool = True,
    max_content_length: int = 10 * 1024 * 1024,
    debug: bool = False,
) -> None:
    """
    Add all security middleware to a FastAPI application.

    Adds middleware in the correct order:
    1. Request ID (outermost - needs to be first)
    2. Request Size Limit
    3. Security Headers
    4. Secure Exception Handler (innermost - catches all errors)

    Args:
        app: FastAPI application instance
        enable_hsts: Enable HTTP Strict Transport Security
        max_content_length: Maximum request body size in bytes
        debug: Enable debug mode (includes exception details)
    """
    # Add in reverse order (last added = first executed)

    # 4. Secure exception handler (innermost)
    app.add_middleware(
        SecureExceptionMiddleware,
        debug=debug,
        include_request_id=True,
    )

    # 3. Security headers
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=enable_hsts,
    )

    # 2. Request size limit
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_content_length=max_content_length,
    )

    # 1. Request ID (outermost)
    app.add_middleware(RequestIDMiddleware)

    logger.info(
        f"Security middleware configured: "
        f"hsts={enable_hsts}, max_size={max_content_length}, debug={debug}"
    )
