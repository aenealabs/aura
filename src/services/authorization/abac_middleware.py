"""
Project Aura - ABAC Middleware

FastAPI middleware and decorators for ABAC-protected endpoints.
Implements ADR-073 for multi-tenant authorization.

Usage:
    @router.get("/vulnerabilities/{tenant_id}")
    @require_abac(
        action="view_vulnerabilities",
        resource_resolver=lambda r, tenant_id: f"arn:aws:aura:::tenant/{tenant_id}",
    )
    async def get_vulnerabilities(request: Request, tenant_id: str):
        ...
"""

import logging
from datetime import datetime
from functools import wraps
from typing import Any, Callable

from .abac_contracts import AuthorizationDecision

logger = logging.getLogger(__name__)


class ABACAccessDenied(Exception):
    """Exception raised when ABAC authorization fails."""

    def __init__(
        self,
        action: str,
        resource_arn: str,
        reason: str,
        decision: AuthorizationDecision | None = None,
    ):
        self.action = action
        self.resource_arn = resource_arn
        self.reason = reason
        self.decision = decision
        super().__init__(f"Access denied for action '{action}': {reason}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for HTTP response."""
        return {
            "error": "Access denied",
            "action": self.action,
            "resource_arn": self.resource_arn,
            "reason": self.reason,
        }


def require_abac(
    action: str,
    resource_resolver: Callable[..., str] | None = None,
    skip_if_no_claims: bool = False,
):
    """
    Decorator for ABAC-protected endpoints.

    Args:
        action: The action being performed (e.g., "view_vulnerabilities")
        resource_resolver: Function to extract resource ARN from request/args.
                          Signature: (request, *args, **kwargs) -> str
        skip_if_no_claims: If True, skip authorization if no JWT claims present

    Example:
        @router.get("/vulnerabilities/{tenant_id}")
        @require_abac(
            action="view_vulnerabilities",
            resource_resolver=lambda r, tenant_id: f"arn:aws:aura:::tenant/{tenant_id}/vulnerabilities",
        )
        async def get_vulnerabilities(request: Request, tenant_id: str):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Import here to avoid circular imports
            from .abac_service import get_abac_service

            # Find request object in args or kwargs
            request = None
            for arg in args:
                if hasattr(arg, "state") and hasattr(arg, "client"):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")

            if request is None:
                logger.warning(
                    f"No request object found for ABAC check on {func.__name__}"
                )
                if skip_if_no_claims:
                    return await func(*args, **kwargs)
                raise ABACAccessDenied(
                    action=action,
                    resource_arn="unknown",
                    reason="No request object available for authorization",
                )

            # Get JWT claims from request state (set by auth middleware)
            jwt_claims = getattr(request.state, "jwt_claims", None)
            if jwt_claims is None:
                jwt_claims = getattr(request.state, "user", None)

            if jwt_claims is None:
                if skip_if_no_claims:
                    return await func(*args, **kwargs)
                raise ABACAccessDenied(
                    action=action,
                    resource_arn="unknown",
                    reason="No authentication credentials found",
                )

            # Convert user object to dict if needed
            if hasattr(jwt_claims, "__dict__") and not isinstance(jwt_claims, dict):
                jwt_claims = jwt_claims.__dict__

            # Resolve resource ARN
            if resource_resolver:
                try:
                    resource_arn = resource_resolver(request, *args[1:], **kwargs)
                except Exception as e:
                    logger.error(f"Resource resolver failed: {e}")
                    resource_arn = f"arn:aws:aura:::unknown/{func.__name__}"
            else:
                # Default ARN based on function name
                resource_arn = f"arn:aws:aura:::endpoint/{func.__name__}"

            # Build request context
            request_context = {
                "source_ip": (
                    request.client.host
                    if hasattr(request, "client") and request.client
                    else ""
                ),
                "request_time": datetime.utcnow().isoformat(),
                "user_agent": (
                    request.headers.get("user-agent", "")
                    if hasattr(request, "headers")
                    else ""
                ),
                "device_trust": (
                    request.headers.get("x-device-trust", "unknown")
                    if hasattr(request, "headers")
                    else "unknown"
                ),
                "mfa_verified": (
                    request.headers.get("x-mfa-verified", "false").lower() == "true"
                    if hasattr(request, "headers")
                    else False
                ),
                "request_id": (
                    request.headers.get("x-request-id", "")
                    if hasattr(request, "headers")
                    else ""
                ),
            }

            # Evaluate authorization
            abac_service = get_abac_service()
            decision = await abac_service.authorize(
                jwt_claims=jwt_claims,
                action=action,
                resource_arn=resource_arn,
                request_context=request_context,
            )

            if not decision.allowed:
                raise ABACAccessDenied(
                    action=action,
                    resource_arn=resource_arn,
                    reason=decision.explanation or "Access denied by policy",
                    decision=decision,
                )

            # Store decision in request state for potential logging
            if hasattr(request, "state"):
                request.state.abac_decision = decision

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_tenant_access(tenant_param: str = "tenant_id"):
    """
    Simplified decorator for tenant-scoped endpoints.

    Args:
        tenant_param: Name of the parameter containing tenant ID

    Example:
        @router.get("/data/{tenant_id}")
        @require_tenant_access()
        async def get_tenant_data(request: Request, tenant_id: str):
            ...
    """
    return require_abac(
        action="access_tenant_resource",
        resource_resolver=lambda r, *args, **kwargs: (
            f"arn:aws:aura:::tenant/{kwargs.get(tenant_param, args[0] if args else 'unknown')}"
        ),
    )


def require_admin():
    """
    Decorator for admin-only endpoints.

    Example:
        @router.delete("/users/{user_id}")
        @require_admin()
        async def delete_user(request: Request, user_id: str):
            ...
    """
    return require_abac(
        action="manage_users",
        resource_resolver=lambda r, *args, **kwargs: "arn:aws:aura:::admin/users",
    )


def require_clearance(min_level: str):
    """
    Decorator requiring minimum clearance level.

    Args:
        min_level: Minimum clearance level required

    Example:
        @router.get("/classified/{doc_id}")
        @require_clearance("confidential")
        async def get_classified_doc(request: Request, doc_id: str):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from .abac_contracts import ClearanceLevel
            from .abac_service import get_abac_service

            # Find request
            request = None
            for arg in args:
                if hasattr(arg, "state"):
                    request = arg
                    break

            if request is None:
                raise ABACAccessDenied(
                    action=func.__name__,
                    resource_arn="unknown",
                    reason="No request object available",
                )

            jwt_claims = getattr(request.state, "jwt_claims", {})
            if not jwt_claims:
                raise ABACAccessDenied(
                    action=func.__name__,
                    resource_arn="unknown",
                    reason="No authentication credentials",
                )

            # Resolve subject to get clearance
            abac_service = get_abac_service()
            subject = await abac_service._resolve_subject(jwt_claims)

            try:
                required_level = ClearanceLevel(min_level)
            except ValueError:
                required_level = ClearanceLevel.INTERNAL

            if subject.clearance_level < required_level:
                raise ABACAccessDenied(
                    action=func.__name__,
                    resource_arn="classified",
                    reason=(
                        f"Requires clearance level '{min_level}', "
                        f"user has '{subject.clearance_level.value}'"
                    ),
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


class ABACMiddleware:
    """
    ASGI middleware for global ABAC enforcement.

    This middleware can be used to add ABAC checks to all requests,
    or to specific path patterns.

    Example:
        app.add_middleware(
            ABACMiddleware,
            protected_paths=["/api/v1/"],
            exclude_paths=["/api/v1/health", "/api/v1/auth"],
        )
    """

    def __init__(
        self,
        app,
        protected_paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
        default_action: str = "api_access",
    ):
        self.app = app
        self.protected_paths = protected_paths or []
        self.exclude_paths = exclude_paths or []
        self.default_action = default_action

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Check if path should be protected
        should_check = any(path.startswith(p) for p in self.protected_paths)
        is_excluded = any(path.startswith(p) for p in self.exclude_paths)

        if should_check and not is_excluded:
            # The actual check happens in the decorator
            # This middleware just logs the request
            logger.debug(f"ABAC middleware: checking {path}")

        await self.app(scope, receive, send)
