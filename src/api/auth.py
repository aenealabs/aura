"""
Cognito JWT Authentication Middleware for FastAPI.

Provides JWT token validation against AWS Cognito User Pool for API authentication.
Supports role-based access control using Cognito groups.

Configuration is loaded from SSM Parameter Store in AWS environments,
or from environment variables for local development.

Author: Project Aura Team
Created: 2025-12-08
Updated: 2025-12-12 - Externalize Cognito config to SSM (#38)
"""

import logging
import os
import threading
import time
from functools import lru_cache
from typing import Any, cast

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError
from pydantic import BaseModel

from src.services.observability_service import get_monitor

logger = logging.getLogger(__name__)

# Lazy boto3 import for reduced cold start time (optimization #6)
# boto3/botocore are heavyweight imports that slow startup
# Import is deferred until SSM fetch is actually needed
_boto3_module: Any = None
_boto3_available: bool | None = None  # None = not yet checked
_ssm_client: Any = None  # Cached SSM client


def _get_boto3():
    """Lazy import of boto3 module. Returns None if not available."""
    global _boto3_module, _boto3_available
    if _boto3_available is None:
        try:
            import boto3

            _boto3_module = boto3
            _boto3_available = True
        except ImportError:
            _boto3_available = False
            logger.warning(
                "boto3 not available - using environment variables for Cognito config"
            )
    return _boto3_module if _boto3_available else None


def _get_ssm_client(region: str):
    """Get cached SSM client, creating it lazily if needed."""
    global _ssm_client
    if _ssm_client is None:
        boto3_mod = _get_boto3()
        if boto3_mod:
            _ssm_client = boto3_mod.client("ssm", region_name=region)
    return _ssm_client


def _clear_boto3_cache() -> None:
    """Clear boto3 caches. Useful for testing."""
    global _boto3_module, _boto3_available, _ssm_client
    _boto3_module = None
    _boto3_available = None
    _ssm_client = None


# Security scheme for Bearer token
security = HTTPBearer(auto_error=False)

# Process-wide HTTP client for connection reuse (keep-alive, DNS cache)
# Reduces TLS handshakes and latency for auth and webhook calls
_http_client: httpx.Client | None = None


def get_http_client() -> httpx.Client:
    """Get or create the process-wide HTTP client with keep-alive.

    Uses connection pooling and keep-alive to reduce TLS handshakes
    for repeated calls to Cognito JWKS endpoint.
    """
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=10.0,
            http2=True,  # Enable HTTP/2 for multiplexing
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=300.0,  # 5 minutes
            ),
        )
    return _http_client


def close_http_client() -> None:
    """Close the HTTP client. Call on application shutdown."""
    global _http_client
    if _http_client is not None:
        _http_client.close()
        _http_client = None
        logger.info("HTTP client closed")


class CognitoConfig(BaseModel):
    """Cognito configuration settings."""

    region: str
    user_pool_id: str
    client_id: str

    @property
    def issuer(self) -> str:
        """Get the JWT issuer URL."""
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"

    @property
    def jwks_url(self) -> str:
        """Get the JWKS URL for public key retrieval."""
        return f"{self.issuer}/.well-known/jwks.json"


class User(BaseModel):
    """Authenticated user model."""

    sub: str  # Cognito user ID
    email: str | None = None
    name: str | None = None
    groups: list[str] = []
    organization_id: str | None = None

    @property
    def roles(self) -> list[str]:
        """Get user roles from Cognito groups."""
        return self.groups

    @property
    def is_platform_admin(self) -> bool:
        """Platform admins manage cross-tenant ("platform") settings.

        Distinct from the broader ``admin`` group used by ``require_admin``:
        an org-level admin has ``admin`` in groups but not ``platform_admin``,
        and must not be granted cross-tenant access via ``is_platform_admin``.
        """
        return "platform_admin" in self.groups


def _fetch_ssm_parameter(ssm_client: Any, name: str) -> str | None:
    """Fetch a single parameter from SSM Parameter Store."""
    try:
        response = ssm_client.get_parameter(Name=name)
        return cast(str, response["Parameter"]["Value"])
    except Exception as e:
        # Catch botocore.exceptions.ClientError without importing it at module level
        # The exception class name check avoids heavyweight import
        if type(e).__name__ == "ClientError":
            logger.warning(f"Failed to fetch SSM parameter {name}: {e}")
        else:
            logger.warning(f"Unexpected error fetching SSM parameter {name}: {e}")
        return None


@lru_cache(maxsize=1)
def get_cognito_config() -> CognitoConfig:
    """
    Get Cognito configuration from SSM Parameter Store or environment variables.

    Priority:
    1. Environment variables (for local development)
    2. SSM Parameter Store (for AWS deployments)

    Uses lazy boto3 import to reduce cold start time when env vars are set.

    Raises:
        RuntimeError: If configuration cannot be loaded from any source
    """
    region = os.environ.get("AWS_REGION", "us-east-1")
    environment = os.environ.get("ENVIRONMENT", "dev")

    # First, try environment variables (allows local dev override)
    user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
    client_id = os.environ.get("COGNITO_CLIENT_ID")

    # If env vars not set, try SSM (lazy boto3 import)
    if not user_pool_id or not client_id:
        ssm = _get_ssm_client(region)
        if ssm:
            logger.info(
                f"Fetching Cognito config from SSM for environment: {environment}"
            )
            try:
                if not user_pool_id:
                    user_pool_id = _fetch_ssm_parameter(
                        ssm, f"/aura/{environment}/cognito/user-pool-id"
                    )

                if not client_id:
                    client_id = _fetch_ssm_parameter(
                        ssm, f"/aura/{environment}/cognito/client-id"
                    )

            except Exception as e:
                logger.error(f"Failed to fetch Cognito config from SSM: {e}")

    # Validate we have required configuration
    if not user_pool_id or not client_id:
        error_msg = (
            "Cognito configuration not found. "
            "Set COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID environment variables, "
            f"or ensure SSM parameters exist at /aura/{environment}/cognito/*"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info(f"Cognito config loaded: pool={user_pool_id}, region={region}")

    return CognitoConfig(
        region=region,
        user_pool_id=user_pool_id,
        client_id=client_id,
    )


# JWKS caching with TTL and thread-safe refresh (security fix)
# Addresses: unbounded cache lifetime and race condition on refresh
_jwks_key_map: dict[str, dict[str, Any]] | None = None
_jwks_cache: dict[str, Any] | None = None
_jwks_cache_time: float = 0.0
_jwks_refresh_lock = threading.Lock()

# JWKS cache TTL in seconds (1 hour)
# Cognito rotates keys periodically; 1 hour ensures we pick up rotations
# while avoiding excessive network calls
JWKS_CACHE_TTL_SECONDS = 3600


def _is_jwks_cache_valid() -> bool:
    """Check if JWKS cache is still valid based on TTL."""
    if _jwks_cache is None:
        return False
    return (time.time() - _jwks_cache_time) < JWKS_CACHE_TTL_SECONDS


def _fetch_jwks_internal() -> dict[str, Any]:
    """Internal JWKS fetch - must be called with lock held."""
    global _jwks_key_map, _jwks_cache, _jwks_cache_time

    config = get_cognito_config()
    monitor = get_monitor()
    start_time = time.time()

    try:
        client = get_http_client()
        response = client.get(config.jwks_url)
        response.raise_for_status()
        jwks: dict[str, Any] = response.json()

        # Record successful fetch latency
        fetch_latency_ms = (time.time() - start_time) * 1000
        monitor.record_latency("auth.jwks_fetch", fetch_latency_ms / 1000)
        monitor.record_success("auth.jwks_fetch")
        logger.info(f"Fetched JWKS from {config.jwks_url} in {fetch_latency_ms:.1f}ms")

        # Build kid->key map for O(1) lookup in get_public_key
        _jwks_key_map = {
            key["kid"]: key for key in jwks.get("keys", []) if "kid" in key
        }
        logger.debug(f"Built JWKS key map with {len(_jwks_key_map)} keys")

        # Update cache with timestamp
        _jwks_cache = jwks
        _jwks_cache_time = time.time()

        return jwks
    except httpx.HTTPError as e:
        # Record failed fetch
        fetch_latency_ms = (time.time() - start_time) * 1000
        monitor.record_latency("auth.jwks_fetch", fetch_latency_ms / 1000)
        monitor.record_error("auth.jwks_fetch", e)
        logger.error(f"Failed to fetch JWKS: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )


def get_jwks() -> dict[str, Any]:
    """
    Fetch and cache JWKS (JSON Web Key Set) from Cognito.

    Security features:
    - TTL-based cache (1 hour) ensures key rotations are picked up
    - Thread-safe refresh prevents thundering herd on cache expiry
    - Uses process-wide HTTP client with keep-alive for connection reuse

    Returns the public keys used to verify JWT signatures.
    """
    # Fast path: return cached value if valid
    if _is_jwks_cache_valid() and _jwks_cache is not None:
        return _jwks_cache

    # Slow path: acquire lock and refresh
    with _jwks_refresh_lock:
        # Double-check after acquiring lock (another thread may have refreshed)
        if _is_jwks_cache_valid() and _jwks_cache is not None:
            return _jwks_cache

        return _fetch_jwks_internal()


def _force_jwks_refresh() -> None:
    """Force JWKS cache refresh. Thread-safe."""
    global _jwks_cache_time
    with _jwks_refresh_lock:
        # Invalidate cache by setting time to 0
        _jwks_cache_time = 0.0
        _fetch_jwks_internal()


def get_public_key(token: str) -> dict[str, Any]:
    """
    Get the public key for verifying a specific JWT token.

    Security features:
    - Uses pre-built kid->key map for O(1) lookup
    - Thread-safe cache refresh on key rotation
    - Matches the token's key ID (kid) with keys from JWKS
    """
    # Ensure JWKS is loaded (populates _jwks_key_map)
    get_jwks()

    # Decode header without verification to get kid
    try:
        unverified_header = jwt.get_unverified_header(token)
    except PyJWTError as e:
        logger.warning(f"Invalid JWT header: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing key ID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # O(1) lookup using pre-built map
    if _jwks_key_map and kid in _jwks_key_map:
        return _jwks_key_map[kid]

    # Key not found - might need to refresh JWKS cache (key rotation)
    # Use thread-safe refresh to prevent thundering herd
    logger.warning(f"Key ID {kid} not found in JWKS key map, refreshing cache")

    with _jwks_refresh_lock:
        # Double-check after acquiring lock
        if _jwks_key_map and kid in _jwks_key_map:
            return _jwks_key_map[kid]

        # Force refresh
        _force_jwks_refresh()

    if _jwks_key_map and kid in _jwks_key_map:
        return _jwks_key_map[kid]

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token signing key not found",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_token(token: str) -> dict[str, Any]:
    """
    Verify and decode a Cognito JWT token.

    Validates:
    - Token signature using public key from JWKS
    - Token expiration
    - Token issuer matches our User Pool
    - Token audience matches our Client ID (for ID tokens)
    - Client ID claim matches our Client ID (for access tokens)

    Security Note:
    - ID tokens contain an 'aud' claim that must match our client_id
    - Access tokens don't have 'aud', they have 'client_id' claim instead
    - Both are validated to prevent cross-tenant token reuse
    """
    monitor = get_monitor()
    start_time = time.time()

    config = get_cognito_config()
    public_key = get_public_key(token)

    # First, decode without verification to inspect token_use
    # This determines whether we validate 'aud' (ID token) or 'client_id' (access token)
    try:
        unverified_claims = jwt.decode(
            token, options={"verify_signature": False}, algorithms=["RS256"]
        )
    except PyJWTError as e:
        logger.warning(f"Failed to decode token claims: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_use = unverified_claims.get("token_use")
    if token_use not in ("access", "id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ID tokens have 'aud' claim, access tokens have 'client_id' claim
    is_id_token = token_use == "id"

    try:
        # Convert JWK dict to PyJWK for PyJWT compatibility
        signing_key = jwt.PyJWK.from_dict(public_key)

        # Decode and verify token with appropriate audience validation
        payload: dict[str, Any] = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=config.issuer,
            audience=config.client_id if is_id_token else None,
            options={
                "verify_aud": is_id_token,  # Only verify aud for ID tokens
                "verify_exp": True,
                "verify_iss": True,
            },
        )

        # For access tokens, manually validate client_id claim
        if not is_id_token:
            token_client_id = payload.get("client_id")
            if token_client_id != config.client_id:
                logger.warning(
                    f"Access token client_id mismatch: expected {config.client_id}, "
                    f"got {token_client_id}"
                )
                # Record failed verification
                verify_latency_ms = (time.time() - start_time) * 1000
                monitor.record_latency("auth.token_verify", verify_latency_ms / 1000)
                monitor.record_error("auth.token_verify")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token audience",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # Record successful verification
        verify_latency_ms = (time.time() - start_time) * 1000
        monitor.record_latency("auth.token_verify", verify_latency_ms / 1000)
        monitor.record_success("auth.token_verify")

        return payload

    except jwt.ExpiredSignatureError:
        # Record expired token (common, not necessarily an attack)
        verify_latency_ms = (time.time() - start_time) * 1000
        monitor.record_latency("auth.token_verify", verify_latency_ms / 1000)
        monitor.record_error("auth.token_verify")
        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        verify_latency_ms = (time.time() - start_time) * 1000
        monitor.record_latency("auth.token_verify", verify_latency_ms / 1000)
        monitor.record_error("auth.token_verify")
        logger.warning(f"Invalid token claims: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except PyJWTError as e:
        verify_latency_ms = (time.time() - start_time) * 1000
        monitor.record_latency("auth.token_verify", verify_latency_ms / 1000)
        monitor.record_error("auth.token_verify")
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
) -> User:
    """
    FastAPI dependency to get the current authenticated user.

    For local development, set AURA_AUTH_BYPASS=true to skip authentication
    and use a mock dev user.

    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"email": user.email}
    """
    # Dev bypass for local testing. Fails closed: requires both AURA_AUTH_BYPASS=true
    # and an explicit non-prod environment indicator. Defaults to "prod" if unset
    # so a misconfigured container cannot accidentally enable bypass. Accepts the
    # canonical ENVIRONMENT variable in addition to AURA_ENVIRONMENT to avoid
    # the dual-env-var footgun flagged in the 2026-05-06 audit (M8).
    if os.environ.get("AURA_AUTH_BYPASS", "").lower() == "true":
        env_raw = (
            os.environ.get("AURA_ENVIRONMENT")
            or os.environ.get("ENVIRONMENT")
            or "prod"
        )
        environment = env_raw.lower()
        if environment in ("dev", "local", "test"):
            logger.warning(
                "Auth bypass enabled - using mock dev user (environment=%s)",
                environment,
            )
            return User(
                sub="dev-user-001",
                email="dev@aenealabs.com",
                name="Dev User",
                groups=["admin", "developers"],
                organization_id="dev-org-001",
            )
        logger.error(
            "AURA_AUTH_BYPASS=true rejected: environment=%s is not dev/local/test",
            environment,
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = verify_token(token)

    # Extract user info from token. The organization claim may live under
    # several names depending on IdP: Cognito custom attributes, OIDC scope,
    # SAML assertion. Accept the first one we find.
    org_id = (
        payload.get("custom:organization_id")
        or payload.get("organization_id")
        or payload.get("org_id")
    )
    return User(
        sub=payload.get("sub", ""),
        email=payload.get("email"),
        name=payload.get("name") or payload.get("cognito:username"),
        groups=payload.get("cognito:groups", []),
        organization_id=org_id,
    )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
) -> User | None:
    """
    FastAPI dependency that returns user if authenticated, None otherwise.

    Useful for endpoints that work differently for authenticated vs anonymous users.

    Usage:
        @app.get("/public")
        async def public_route(user: User | None = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello, {user.email}!"}
            return {"message": "Hello, anonymous!"}
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        payload = verify_token(token)
        return User(
            sub=payload.get("sub", ""),
            email=payload.get("email"),
            name=payload.get("name") or payload.get("cognito:username"),
            groups=payload.get("cognito:groups", []),
        )
    except HTTPException:
        return None


def require_role(*allowed_roles: str):
    """
    Dependency factory for role-based access control.

    Usage:
        @app.get("/admin", dependencies=[Depends(require_role("admin"))])
        async def admin_only():
            return {"message": "Welcome, admin!"}

        @app.get("/team", dependencies=[Depends(require_role("admin", "security-engineer"))])
        async def team_only():
            return {"message": "Welcome, team member!"}
    """

    async def role_checker(
        user: User = Depends(get_current_user),  # noqa: B008
    ) -> User:  # noqa: B008
        if not any(role in user.groups for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {' or '.join(allowed_roles)}",
            )
        return user

    return role_checker


# Pre-built role dependencies for common use cases
require_admin = require_role("admin")
require_security_engineer = require_role("admin", "security-engineer")
require_developer = require_role("admin", "security-engineer", "developer")


def clear_auth_caches() -> None:
    """
    Clear all authentication caches.

    Useful when Cognito configuration changes or for testing.
    """
    global _jwks_key_map, _jwks_cache, _jwks_cache_time
    get_cognito_config.cache_clear()
    # Clear JWKS TTL cache
    _jwks_key_map = None
    _jwks_cache = None
    _jwks_cache_time = 0.0
    _clear_boto3_cache()
    logger.info("Authentication caches cleared")
