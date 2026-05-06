"""
Project Aura - Token Normalization Service

Normalizes tokens from various identity providers into unified Aura JWTs.
This ensures consistent token format regardless of source IdP.

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from src.services.identity.models import (
    AuraTokens,
    AuthResult,
    AuthSession,
    IdentityProviderConfig,
    TokenValidationResult,
)

logger = logging.getLogger(__name__)


class TokenNormalizationService:
    """
    Normalizes IdP tokens into unified Aura JWTs.

    Ensures consistent token format regardless of source identity provider,
    enabling uniform authorization across the platform.

    Features:
    - Issues access and refresh tokens
    - Consistent claims structure
    - Token refresh with rotation
    - Session tracking for revocation
    """

    # Standard Aura JWT claims
    AURA_CLAIMS = [
        "sub",  # User ID (unique across IdPs)
        "email",  # User email
        "name",  # Display name
        "roles",  # Aura roles
        "org_id",  # Organization ID
        "idp",  # Source IdP identifier
        "idp_type",  # IdP type
    ]

    def __init__(
        self,
        signing_key_secret_arn: str | None = None,
        issuer: str | None = None,
        access_token_ttl: int = 3600,  # 1 hour
        refresh_token_ttl: int = 2592000,  # 30 days
        algorithm: str = "RS256",
    ):
        """
        Initialize token service.

        Args:
            signing_key_secret_arn: Secrets Manager ARN for JWT signing key
            issuer: JWT issuer (iss claim)
            access_token_ttl: Access token lifetime in seconds
            refresh_token_ttl: Refresh token lifetime in seconds
            algorithm: JWT signing algorithm (RS256 for RSA, HS256 for symmetric)
        """
        import os as _os

        self.signing_key_secret_arn = signing_key_secret_arn
        self.issuer = issuer or _os.environ.get("JWT_ISSUER", "https://api.aura.local")
        self.access_token_ttl = access_token_ttl
        self.refresh_token_ttl = refresh_token_ttl
        self.algorithm = algorithm

        self._signing_key: str | None = None
        self._public_key: str | None = None
        self._key_loaded = False

    async def _load_signing_key(self) -> None:
        """Load signing key from Secrets Manager."""
        if self._key_loaded:
            return

        if not self.signing_key_secret_arn:
            # For development, generate a symmetric key
            logger.warning(
                "No signing key ARN configured - using development symmetric key"
            )
            self._signing_key = secrets.token_urlsafe(32)
            self.algorithm = "HS256"
            self._key_loaded = True
            return

        try:
            import boto3

            secrets_client = boto3.client("secretsmanager")
            response = secrets_client.get_secret_value(
                SecretId=self.signing_key_secret_arn
            )
            secret_data = json.loads(response["SecretString"])

            self._signing_key = secret_data.get("private_key")
            self._public_key = secret_data.get("public_key")

            if not self._signing_key:
                raise ValueError("private_key not found in secret")

            self._key_loaded = True
            logger.info("JWT signing key loaded from Secrets Manager")

        except Exception as e:
            logger.error(f"Failed to load signing key: {e}")
            raise

    async def issue_tokens(
        self,
        auth_result: AuthResult,
        idp_config: IdentityProviderConfig,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[AuraTokens, AuthSession]:
        """
        Issue Aura access and refresh tokens from IdP auth result.

        Args:
            auth_result: Successful authentication result from IdP
            idp_config: IdP configuration
            client_ip: Client IP address for session tracking
            user_agent: Client user agent for session tracking

        Returns:
            Tuple of (AuraTokens, AuthSession)
        """
        await self._load_signing_key()

        now = datetime.now(timezone.utc)

        # Generate unique subject for this IdP + user combination
        aura_sub = self._generate_subject(
            idp_id=idp_config.idp_id,
            provider_user_id=auth_result.user_id or "",
        )

        # Generate session ID and refresh token JTI
        session_id = secrets.token_urlsafe(24)
        refresh_jti = secrets.token_urlsafe(32)

        # Access token claims
        access_claims = {
            "sub": aura_sub,
            "email": auth_result.email,
            "name": auth_result.name,
            "roles": auth_result.roles,
            "org_id": idp_config.organization_id,
            "idp": idp_config.idp_id,
            "idp_type": idp_config.idp_type.value,
            "session_id": session_id,
            "iss": self.issuer,
            "aud": "aura-api",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self.access_token_ttl)).timestamp()),
            "token_type": "access",
        }

        # Sign access token
        access_token = jwt.encode(
            access_claims,
            self._signing_key,
            algorithm=self.algorithm,
        )

        # Refresh token claims (minimal, long-lived)
        refresh_claims = {
            "sub": aura_sub,
            "org_id": idp_config.organization_id,
            "idp": idp_config.idp_id,
            "session_id": session_id,
            "iss": self.issuer,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self.refresh_token_ttl)).timestamp()),
            "token_type": "refresh",
            "jti": refresh_jti,
        }

        refresh_token = jwt.encode(
            refresh_claims,
            self._signing_key,
            algorithm=self.algorithm,
        )

        # Create session record
        session = AuthSession(
            session_id=session_id,
            user_sub=aura_sub,
            idp_id=idp_config.idp_id,
            organization_id=idp_config.organization_id,
            email=auth_result.email,
            roles=auth_result.roles,
            refresh_token_jti=refresh_jti,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=self.refresh_token_ttl)).isoformat(),
            last_activity=now.isoformat(),
            ip_address=client_ip,
            user_agent=user_agent,
        )

        tokens = AuraTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=self.access_token_ttl,
        )

        logger.info(
            f"Issued tokens for user {auth_result.email} via IdP {idp_config.idp_id}"
        )

        return tokens, session

    async def refresh_tokens(
        self,
        refresh_token: str,
        session: AuthSession,
        idp_config: IdentityProviderConfig,
    ) -> tuple[AuraTokens, AuthSession]:
        """
        Refresh access token and rotate refresh token.

        Args:
            refresh_token: Current refresh token
            session: Current session
            idp_config: IdP configuration

        Returns:
            Tuple of (new AuraTokens, updated AuthSession)
        """
        await self._load_signing_key()

        # Validate refresh token
        validation = await self.validate_token(refresh_token)
        if not validation.valid:
            raise ValueError(f"Invalid refresh token: {validation.error}")

        claims = validation.claims

        # Verify JTI matches session
        if claims.get("jti") != session.refresh_token_jti:
            raise ValueError("Refresh token JTI mismatch - possible token reuse")

        now = datetime.now(timezone.utc)

        # Generate new refresh token JTI (rotation)
        new_refresh_jti = secrets.token_urlsafe(32)

        # New access token claims
        access_claims = {
            "sub": session.user_sub,
            "email": session.email,
            "name": None,  # Name from original auth, could be stored in session
            "roles": session.roles,
            "org_id": session.organization_id,
            "idp": session.idp_id,
            "idp_type": idp_config.idp_type.value,
            "session_id": session.session_id,
            "iss": self.issuer,
            "aud": "aura-api",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self.access_token_ttl)).timestamp()),
            "token_type": "access",
        }

        access_token = jwt.encode(
            access_claims,
            self._signing_key,
            algorithm=self.algorithm,
        )

        # New refresh token
        refresh_claims = {
            "sub": session.user_sub,
            "org_id": session.organization_id,
            "idp": session.idp_id,
            "session_id": session.session_id,
            "iss": self.issuer,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self.refresh_token_ttl)).timestamp()),
            "token_type": "refresh",
            "jti": new_refresh_jti,
        }

        new_refresh_token = jwt.encode(
            refresh_claims,
            self._signing_key,
            algorithm=self.algorithm,
        )

        # Update session
        session.refresh_token_jti = new_refresh_jti
        session.last_activity = now.isoformat()
        session.expires_at = (
            now + timedelta(seconds=self.refresh_token_ttl)
        ).isoformat()

        tokens = AuraTokens(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="Bearer",
            expires_in=self.access_token_ttl,
        )

        logger.info(f"Refreshed tokens for session {session.session_id}")

        return tokens, session

    async def validate_token(self, token: str) -> TokenValidationResult:
        """Validate an Aura JWT token."""
        await self._load_signing_key()

        try:
            # For RS256, use public key; for HS256, use signing key
            verify_key = self._public_key or self._signing_key

            # First decode without signature verification to check token type
            unverified = jwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=[self.algorithm],
            )
            is_refresh = unverified.get("token_type") == "refresh"

            claims = jwt.decode(
                token,
                verify_key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=None if is_refresh else "aura-api",
                options={
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_aud": not is_refresh,
                },
            )

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
                error="Token has expired",
            )
        except jwt.InvalidTokenError as e:
            return TokenValidationResult(
                valid=False,
                error=f"Invalid claims: {e}",
            )
        except Exception as e:
            return TokenValidationResult(
                valid=False,
                error=str(e),
            )

    def _generate_subject(self, idp_id: str, provider_user_id: str) -> str:
        """
        Generate globally unique subject for user.

        Creates a consistent hash from IdP ID and user ID to ensure
        users from different IdPs don't collide.
        """
        combined = f"{idp_id}:{provider_user_id}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def decode_token_unverified(self, token: str) -> dict[str, Any]:
        """Decode token without verification (for inspection only).

        SECURITY: never trust the result for control decisions. The returned
        claims are attacker-controlled. This is a debugging / introspection
        helper for surfacing kid/iss/sub before signature verification can
        be performed.

        The algorithm allowlist is pinned to the configured signing algorithm
        rather than ``["HS256","RS256"]``. The previous broad list created an
        algorithm-confusion footgun: if any caller mishandled the result and
        re-used the public RSA key as an HMAC secret, signed-by-attacker
        tokens would validate.
        """
        return jwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=[self.algorithm],
        )

    def get_token_header(self, token: str) -> dict[str, Any]:
        """Get token header without verification."""
        return jwt.get_unverified_header(token)


# Singleton instance
_token_service: TokenNormalizationService | None = None


def get_token_service() -> TokenNormalizationService:
    """Get or create token service singleton."""
    global _token_service
    if _token_service is None:
        import os

        _token_service = TokenNormalizationService(
            signing_key_secret_arn=os.environ.get("JWT_SIGNING_KEY_ARN"),
            issuer=os.environ.get("JWT_ISSUER", "https://api.aura.local"),
        )
    return _token_service
