"""
Project Aura - OpenID Connect Identity Provider

Implements OIDC client for enterprise IdPs like Azure AD, Google Workspace, Auth0, etc.

Supports:
- Authorization Code flow with PKCE
- Discovery via .well-known/openid-configuration
- JWT validation (RS256, RS384, RS512)
- UserInfo endpoint
- Token refresh

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

import base64
import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import aiohttp
from jose import JWTError, jwt

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


@dataclass
class OIDCAuthRequest:
    """OIDC authorization request data."""

    authorization_url: str
    state: str
    nonce: str
    code_verifier: str
    created_at: str
    expires_at: str


class OIDCDiscoveryError(Exception):
    """Failed to discover OIDC endpoints."""


class OIDCTokenError(Exception):
    """Token exchange or validation failed."""


class OIDCProvider(IdentityProvider):
    """
    OpenID Connect identity provider.

    Implements OIDC Authorization Code flow with PKCE for secure
    authentication with enterprise identity providers.

    Connection Settings (config.connection_settings):
        issuer: str - OIDC issuer URL (e.g., "https://login.microsoftonline.com/{tenant}/v2.0")
        client_id: str - OIDC client ID
        redirect_uri: str - OAuth callback URL
        scopes: list[str] - Requested scopes (default: ["openid", "profile", "email"])
        response_type: str - OAuth response type (default: "code")
        use_pkce: bool - Use PKCE for code exchange (default: True)
        additional_params: dict - Extra authorization parameters

    Credentials (from Secrets Manager):
        client_secret: str - OIDC client secret (optional with PKCE)
    """

    def __init__(self, config: IdentityProviderConfig):
        """Initialize OIDC provider."""
        super().__init__(config)

        if config.idp_type != IdPType.OIDC:
            raise ConfigurationError(
                f"Invalid IdP type for OIDCProvider: {config.idp_type}"
            )

        conn = config.connection_settings
        self.issuer = conn.get("issuer")
        self.client_id = conn.get("client_id")
        self.redirect_uri = conn.get(
            "redirect_uri", "https://api.aenealabs.com/auth/oidc/callback"
        )
        self.scopes = conn.get("scopes", ["openid", "profile", "email"])
        self.response_type = conn.get("response_type", "code")
        self.use_pkce = conn.get("use_pkce", True)
        self.additional_params = conn.get("additional_params", {})

        # Validate required settings
        if not self.issuer:
            raise ConfigurationError("OIDC issuer is required")
        if not self.client_id:
            raise ConfigurationError("OIDC client_id is required")

        # Discovery endpoints (populated from discovery document)
        self._authorization_endpoint: str | None = None
        self._token_endpoint: str | None = None
        self._userinfo_endpoint: str | None = None
        self._jwks_uri: str | None = None
        self._end_session_endpoint: str | None = None

        # JWKS cache
        self._jwks: dict[str, Any] | None = None
        self._jwks_cache_time: float = 0
        self._jwks_cache_ttl = 3600  # 1 hour

        # Client secret from Secrets Manager
        self._client_secret: str | None = None
        self._credentials_loaded = False
        self._discovery_loaded = False

    async def _load_credentials(self) -> None:
        """Load client credentials from Secrets Manager."""
        if self._credentials_loaded:
            return

        if self.config.credentials_secret_arn:
            try:
                import boto3

                secrets_client = boto3.client("secretsmanager")
                response = secrets_client.get_secret_value(
                    SecretId=self.config.credentials_secret_arn
                )
                secret_data = json.loads(response["SecretString"])
                self._client_secret = secret_data.get("client_secret")
            except Exception as e:
                logger.warning(f"Failed to load OIDC client secret: {e}")
                if not self.use_pkce:
                    raise ConfigurationError(
                        f"Client secret required without PKCE: {e}"
                    )

        self._credentials_loaded = True

    async def discover(self) -> None:
        """Fetch OIDC discovery document."""
        if self._discovery_loaded:
            return

        discovery_url = f"{self.issuer.rstrip('/')}/.well-known/openid-configuration"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    discovery_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        raise OIDCDiscoveryError(
                            f"Discovery failed with status {response.status}"
                        )

                    config = await response.json()

                    self._authorization_endpoint = config.get("authorization_endpoint")
                    self._token_endpoint = config.get("token_endpoint")
                    self._userinfo_endpoint = config.get("userinfo_endpoint")
                    self._jwks_uri = config.get("jwks_uri")
                    self._end_session_endpoint = config.get("end_session_endpoint")

                    if not self._authorization_endpoint or not self._token_endpoint:
                        raise OIDCDiscoveryError(
                            "Missing required endpoints in discovery document"
                        )

                    self._discovery_loaded = True
                    logger.info(f"OIDC discovery completed for issuer {self.issuer}")

        except aiohttp.ClientError as e:
            raise OIDCDiscoveryError(f"Discovery request failed: {e}")

    async def _get_jwks(self) -> dict[str, Any]:
        """Fetch and cache JWKS."""
        now = time.time()

        # Return cached JWKS if valid
        if (
            self._jwks is not None
            and (now - self._jwks_cache_time) < self._jwks_cache_ttl
        ):
            return self._jwks

        await self.discover()

        if not self._jwks_uri:
            raise OIDCTokenError("JWKS URI not available")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._jwks_uri,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        raise OIDCTokenError(f"JWKS fetch failed: {response.status}")

                    self._jwks = await response.json()
                    self._jwks_cache_time = now
                    return self._jwks

        except aiohttp.ClientError as e:
            raise OIDCTokenError(f"JWKS fetch failed: {e}")

    def generate_auth_request(
        self,
        state: str | None = None,
        nonce: str | None = None,
    ) -> OIDCAuthRequest:
        """
        Generate authorization URL with PKCE.

        Args:
            state: Optional state parameter (generated if not provided)
            nonce: Optional nonce for ID token validation (generated if not provided)

        Returns:
            OIDCAuthRequest with authorization URL and PKCE verifier
        """
        if not self._authorization_endpoint:
            raise ConfigurationError("OIDC discovery not completed")

        # Generate state and nonce
        state = state or secrets.token_urlsafe(32)
        nonce = nonce or secrets.token_urlsafe(32)

        # Generate PKCE challenge
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )

        # Build authorization URL
        params: dict[str, str] = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": self.response_type,
            "scope": " ".join(self.scopes),
            "state": state,
            "nonce": nonce,
        }

        if self.use_pkce:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        # Add any additional parameters
        params.update(self.additional_params)

        auth_url = f"{self._authorization_endpoint}?{urlencode(params)}"

        created = datetime.now(timezone.utc)
        expires = created + timedelta(minutes=10)

        logger.info(f"Generated OIDC auth request for IdP {self.idp_id}")

        return OIDCAuthRequest(
            authorization_url=auth_url,
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
            created_at=created.isoformat(),
            expires_at=expires.isoformat(),
        )

    async def authenticate(self, credentials: AuthCredentials) -> AuthResult:
        """
        Complete OIDC authentication by validating ID token.

        Args:
            credentials: Must contain either:
                - code + code_verifier + state + nonce (for code exchange)
                - id_token + nonce (for direct ID token validation)

        Returns:
            AuthResult with user info and roles
        """
        start_time = time.time()

        try:
            await self._load_credentials()
            await self.discover()

            # If we have an authorization code, exchange it for tokens
            if credentials.code:
                if not credentials.code_verifier and self.use_pkce:
                    return AuthResult(
                        success=False,
                        error="Code verifier required for PKCE",
                        error_code="MISSING_CODE_VERIFIER",
                    )

                tokens = await self._exchange_code(
                    code=credentials.code,
                    code_verifier=credentials.code_verifier,
                )

                id_token = tokens.id_token
                if not id_token:
                    return AuthResult(
                        success=False,
                        error="No ID token in response",
                        error_code="MISSING_ID_TOKEN",
                    )

            elif credentials.id_token:
                id_token = credentials.id_token
            else:
                return AuthResult(
                    success=False,
                    error="Authorization code or ID token required",
                    error_code="MISSING_CREDENTIALS",
                )

            # Validate ID token
            validation = await self._validate_id_token(id_token, credentials.nonce)

            if not validation.valid:
                latency_ms = (time.time() - start_time) * 1000
                self._record_request(latency_ms, False)
                return AuthResult(
                    success=False,
                    error=validation.error or "ID token validation failed",
                    error_code="INVALID_ID_TOKEN",
                )

            claims = validation.claims

            # Map attributes
            mapped_attrs = self.map_attributes(claims)

            # Get groups
            groups: list[str] = []
            for group_attr in ["groups", "roles", "group"]:
                if group_attr in claims:
                    group_val = claims[group_attr]
                    if isinstance(group_val, list):
                        groups.extend(str(g) for g in group_val)
                    elif isinstance(group_val, str):
                        groups.append(group_val)

            roles = self.map_groups_to_roles(groups)

            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, True)
            self._set_status(ConnectionStatus.CONNECTED)

            logger.info(
                f"OIDC authentication successful for user '{claims.get('sub')}' "
                f"via IdP {self.idp_id}"
            )

            return AuthResult(
                success=True,
                user_id=claims.get("sub"),
                email=mapped_attrs.get("email"),
                name=mapped_attrs.get("name"),
                groups=groups,
                roles=roles,
                attributes=mapped_attrs,
                provider_metadata={
                    "provider": "oidc",
                    "idp_id": self.idp_id,
                    "issuer": self.issuer,
                },
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_request(latency_ms, False)
            self._set_status(ConnectionStatus.ERROR, str(e))
            logger.exception(f"OIDC authentication error: {e}")
            return AuthResult(
                success=False,
                error=str(e),
                error_code="OIDC_ERROR",
            )

    async def _exchange_code(
        self,
        code: str,
        code_verifier: str | None,
    ) -> TokenResult:
        """Exchange authorization code for tokens."""
        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

        if code_verifier:
            data["code_verifier"] = code_verifier

        if self._client_secret:
            data["client_secret"] = self._client_secret

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response_data = await response.json()

                if response.status != 200:
                    error = response_data.get("error", "Unknown error")
                    error_desc = response_data.get("error_description", "")
                    raise OIDCTokenError(
                        f"Token exchange failed: {error} - {error_desc}"
                    )

                return TokenResult(
                    access_token=response_data["access_token"],
                    token_type=response_data.get("token_type", "Bearer"),
                    expires_in=response_data.get("expires_in", 3600),
                    refresh_token=response_data.get("refresh_token"),
                    id_token=response_data.get("id_token"),
                    scope=response_data.get("scope"),
                )

    async def _validate_id_token(
        self,
        id_token: str,
        nonce: str | None,
    ) -> TokenValidationResult:
        """Validate and decode ID token."""
        try:
            # Get JWKS
            jwks = await self._get_jwks()

            # Get key ID from token header
            header = jwt.get_unverified_header(id_token)
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
                    error=f"No matching key found for kid: {kid}",
                )

            # Validate token
            claims = jwt.decode(
                id_token,
                key,
                algorithms=["RS256", "RS384", "RS512"],
                audience=self.client_id,
                issuer=self.issuer,
                options={
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                },
            )

            # Validate nonce if provided
            if nonce and claims.get("nonce") != nonce:
                return TokenValidationResult(
                    valid=False,
                    error="Nonce mismatch",
                )

            # Extract expiration
            exp = claims.get("exp")
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None

            return TokenValidationResult(
                valid=True,
                claims=claims,
                expires_at=expires_at,
            )

        except jwt.ExpiredSignatureError:
            return TokenValidationResult(
                valid=False,
                error="ID token has expired",
            )
        except jwt.JWTClaimsError as e:
            return TokenValidationResult(
                valid=False,
                error=f"Invalid claims: {e}",
            )
        except JWTError as e:
            return TokenValidationResult(
                valid=False,
                error=f"JWT validation failed: {e}",
            )

    async def validate_token(self, token: str) -> TokenValidationResult:
        """Validate an access token."""
        # For access tokens, we can use introspection if available
        # or try to validate as JWT
        try:
            jwks = await self._get_jwks()
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            key = None
            for k in jwks.get("keys", []):
                if k.get("kid") == kid:
                    key = k
                    break

            if not key:
                return TokenValidationResult(valid=False, error="Key not found")

            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256", "RS384", "RS512"],
                options={
                    "verify_aud": False
                },  # Access tokens may have different audience
            )

            return TokenValidationResult(valid=True, claims=claims)

        except JWTError as e:
            return TokenValidationResult(valid=False, error=str(e))

    async def get_user_info(self, token: str) -> UserInfo:
        """Get user info from UserInfo endpoint."""
        await self.discover()

        if not self._userinfo_endpoint:
            raise AuthenticationError("UserInfo endpoint not available")

        async with aiohttp.ClientSession() as session:
            async with session.get(
                self._userinfo_endpoint,
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    raise AuthenticationError(
                        f"UserInfo request failed: {response.status}"
                    )

                data = await response.json()

                return UserInfo(
                    user_id=data.get("sub", ""),
                    email=data.get("email"),
                    name=data.get("name"),
                    username=data.get("preferred_username"),
                    groups=data.get("groups", []),
                    attributes=data,
                )

    async def refresh_token(self, refresh_token: str) -> TokenResult:
        """Refresh access token."""
        await self._load_credentials()
        await self.discover()

        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": refresh_token,
        }

        if self._client_secret:
            data["client_secret"] = self._client_secret

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response_data = await response.json()

                if response.status != 200:
                    error = response_data.get("error", "Unknown error")
                    raise AuthenticationError(f"Token refresh failed: {error}")

                return TokenResult(
                    access_token=response_data["access_token"],
                    token_type=response_data.get("token_type", "Bearer"),
                    expires_in=response_data.get("expires_in", 3600),
                    refresh_token=response_data.get("refresh_token", refresh_token),
                    id_token=response_data.get("id_token"),
                    scope=response_data.get("scope"),
                )

    async def logout(self, token: str) -> bool:
        """Initiate logout via end_session endpoint."""
        await self.discover()

        if not self._end_session_endpoint:
            logger.info("End session endpoint not available, skipping OIDC logout")
            return True

        # For full logout, the frontend should redirect to end_session_endpoint
        logger.info(f"OIDC logout initiated for IdP {self.idp_id}")
        return True

    async def health_check(self) -> HealthCheckResult:
        """Check OIDC provider health via discovery endpoint."""
        start_time = time.time()

        try:
            await self.discover()
            latency_ms = (time.time() - start_time) * 1000

            self._set_status(ConnectionStatus.CONNECTED)
            return HealthCheckResult(
                healthy=True,
                status=ConnectionStatus.CONNECTED,
                latency_ms=latency_ms,
                message="OIDC discovery successful",
                last_checked=datetime.now(timezone.utc).isoformat(),
                details={
                    "issuer": self.issuer,
                    "authorization_endpoint": self._authorization_endpoint,
                    "token_endpoint": self._token_endpoint,
                    "userinfo_endpoint": self._userinfo_endpoint,
                },
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
IdentityProviderFactory.register("oidc", OIDCProvider)
