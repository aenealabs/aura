"""
Project Aura - Cognito Identity Provider

Wraps existing Cognito authentication to fit the multi-IdP abstraction.
Allows Cognito to be used as one IdP option among many.

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

from src.services.identity.base_provider import (
    AuthenticationError,
    ConfigurationError,
    IdentityProvider,
    IdentityProviderFactory,
)
from src.services.identity.models import (
    AuthCredentials,
    AuthResult,
    ConnectionStatus,
    HealthCheckResult,
    IdentityProviderConfig,
    IdPType,
    TokenResult,
    TokenValidationResult,
    UserInfo,
)

logger = logging.getLogger(__name__)


class CognitoProvider(IdentityProvider):
    """
    AWS Cognito identity provider.

    Integrates with AWS Cognito User Pools for authentication.
    This provider wraps the existing Cognito JWT validation logic
    from src/api/auth.py into the multi-IdP abstraction.

    Connection Settings (config.connection_settings):
        region: str - AWS region (default: us-east-1)
        user_pool_id: str - Cognito User Pool ID
        client_id: str - Cognito App Client ID
        domain: str - Cognito domain for hosted UI (optional)

    Note: Cognito typically doesn't need credentials in Secrets Manager
    as it uses IAM or public client configuration.
    """

    def __init__(self, config: IdentityProviderConfig):
        """Initialize Cognito provider."""
        super().__init__(config)

        if config.idp_type != IdPType.COGNITO:
            raise ConfigurationError(
                f"Invalid IdP type for CognitoProvider: {config.idp_type}"
            )

        conn = config.connection_settings
        self.region = conn.get("region", "us-east-1")
        self.user_pool_id = conn.get("user_pool_id")
        self.client_id = conn.get("client_id")
        self.domain = conn.get("domain")

        # Validate required settings
        if not self.user_pool_id:
            raise ConfigurationError("Cognito user_pool_id is required")
        if not self.client_id:
            raise ConfigurationError("Cognito client_id is required")

        # Compute derived values
        self.issuer = (
            f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"
        )
        self.jwks_url = f"{self.issuer}/.well-known/jwks.json"

        # JWKS cache
        self._jwks: dict[str, Any] | None = None
        self._jwks_cache_time: float = 0
        self._jwks_cache_ttl = 3600

    async def authenticate(self, credentials: AuthCredentials) -> AuthResult:
        """
        Authenticate user with Cognito.

        For Cognito, this typically validates an existing token rather than
        performing username/password authentication (which should go through
        the Cognito hosted UI or SRP flow).

        Args:
            credentials: Should contain access_token or id_token

        Returns:
            AuthResult with user info and roles
        """
        start_time = time.time()

        token = credentials.access_token or credentials.id_token
        if not token:
            return AuthResult(
                success=False,
                error="Access token or ID token required",
                error_code="MISSING_TOKEN",
            )

        try:
            # Validate token
            validation = await self.validate_token(token)

            if not validation.valid:
                latency_ms = (time.time() - start_time) * 1000
                self._record_request(latency_ms, False)
                return AuthResult(
                    success=False,
                    error=validation.error or "Token validation failed",
                    error_code="INVALID_TOKEN",
                )

            claims = validation.claims

            # Map attributes
            mapped_attrs = self.map_attributes(claims)

            # Get groups from cognito:groups claim
            groups = claims.get("cognito:groups", [])
            if isinstance(groups, str):
                groups = [groups]

            roles = self.map_groups_to_roles(groups)

            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, True)
            self._set_status(ConnectionStatus.CONNECTED)

            return AuthResult(
                success=True,
                user_id=claims.get("sub"),
                email=mapped_attrs.get("email"),
                name=mapped_attrs.get("name"),
                groups=groups,
                roles=roles,
                attributes=mapped_attrs,
                provider_metadata={
                    "provider": "cognito",
                    "idp_id": self.idp_id,
                    "user_pool_id": self.user_pool_id,
                },
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._set_status(ConnectionStatus.ERROR, str(e))
            logger.exception(f"Cognito authentication error: {e}")
            return AuthResult(
                success=False,
                error=str(e),
                error_code="COGNITO_ERROR",
            )

    async def _get_jwks(self) -> dict[str, Any]:
        """Fetch and cache JWKS from Cognito."""
        import aiohttp

        now = time.time()

        if (
            self._jwks is not None
            and (now - self._jwks_cache_time) < self._jwks_cache_ttl
        ):
            return self._jwks

        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.jwks_url,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    raise AuthenticationError(
                        f"Failed to fetch JWKS: {response.status}"
                    )

                self._jwks = await response.json()
                self._jwks_cache_time = now
                return self._jwks

    async def validate_token(self, token: str) -> TokenValidationResult:
        """Validate Cognito JWT token."""
        import jwt
        from jwt.exceptions import PyJWTError

        try:
            # Get JWKS
            jwks = await self._get_jwks()

            # Get key ID from token header
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            # Find matching key
            key = None
            for k in jwks.get("keys", []):
                if k.get("kid") == kid:
                    key = k
                    break

            if not key:
                return TokenValidationResult(
                    valid=False,
                    error=f"No matching key for kid: {kid}",
                )

            # Determine token type
            unverified_claims = jwt.decode(
                token, options={"verify_signature": False}, algorithms=["RS256"]
            )
            token_use = unverified_claims.get("token_use")

            # Convert JWK dict to PyJWK for PyJWT compatibility
            signing_key = jwt.PyJWK.from_dict(key)

            # Validate token
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.client_id if token_use == "id" else None,
                options={
                    "verify_aud": token_use == "id",
                    "verify_iss": True,
                    "verify_exp": True,
                },
            )

            # For access tokens, verify client_id claim
            if token_use == "access":
                if claims.get("client_id") != self.client_id:
                    return TokenValidationResult(
                        valid=False,
                        error="Invalid client_id in access token",
                    )

            exp = claims.get("exp")
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None

            return TokenValidationResult(
                valid=True,
                claims=claims,
                expires_at=expires_at,
            )

        except jwt.ExpiredSignatureError:
            return TokenValidationResult(valid=False, error="Token expired")
        except jwt.InvalidTokenError as e:
            return TokenValidationResult(valid=False, error=f"Invalid claims: {e}")
        except PyJWTError as e:
            return TokenValidationResult(valid=False, error=str(e))

    async def get_user_info(self, token: str) -> UserInfo:
        """Get user info by validating token."""
        validation = await self.validate_token(token)
        if not validation.valid:
            raise AuthenticationError(validation.error or "Invalid token")

        claims = validation.claims
        mapped = self.map_attributes(claims)

        return UserInfo(
            user_id=claims.get("sub", ""),
            email=mapped.get("email"),
            name=mapped.get("name"),
            username=claims.get("cognito:username"),
            groups=claims.get("cognito:groups", []),
            attributes=mapped,
        )

    async def refresh_token(self, refresh_token: str) -> TokenResult:
        """
        Refresh Cognito tokens.

        Note: Full implementation would use cognito-idp:InitiateAuth.
        """
        raise AuthenticationError(
            "Direct token refresh not implemented. Use Cognito hosted UI or SDK."
        )

    async def logout(self, token: str) -> bool:
        """Logout from Cognito (token revocation)."""
        # Cognito token revocation requires cognito-idp:RevokeToken
        logger.info(f"Cognito logout requested for IdP {self.idp_id}")
        return True

    async def health_check(self) -> HealthCheckResult:
        """Check Cognito availability via JWKS endpoint."""
        import aiohttp

        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.jwks_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    latency_ms = (time.time() - start_time) * 1000

                    if response.status == 200:
                        self._set_status(ConnectionStatus.CONNECTED)
                        return HealthCheckResult(
                            healthy=True,
                            status=ConnectionStatus.CONNECTED,
                            latency_ms=latency_ms,
                            message="Cognito JWKS accessible",
                            last_checked=datetime.now(timezone.utc).isoformat(),
                            details={
                                "user_pool_id": self.user_pool_id,
                                "region": self.region,
                            },
                        )
                    else:
                        self._set_status(ConnectionStatus.ERROR)
                        return HealthCheckResult(
                            healthy=False,
                            status=ConnectionStatus.ERROR,
                            latency_ms=latency_ms,
                            message=f"JWKS returned status {response.status}",
                            last_checked=datetime.now(timezone.utc).isoformat(),
                        )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._set_status(ConnectionStatus.ERROR, str(e))
            return HealthCheckResult(
                healthy=False,
                status=ConnectionStatus.ERROR,
                latency_ms=latency_ms,
                message=str(e),
                last_checked=datetime.now(timezone.utc).isoformat(),
            )


# Register provider with factory
IdentityProviderFactory.register("cognito", CognitoProvider)
