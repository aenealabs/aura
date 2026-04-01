"""OAuth Delegation Service for Agent-to-Service Authentication

Implements ADR-037 Phase 1.3: OAuth Delegation Service

Enables agents to securely act on behalf of users with third-party services
through OAuth 2.0 delegation with secure token vault storage.

Key Features:
- OAuth 2.0 authorization code flow
- Secure token vault (Secrets Manager)
- Automatic token refresh
- Multi-tenant support with custom claims
- Native IdP integration (Cognito, Okta, Azure AD)
"""

import hashlib
import logging
import secrets
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class OAuthProviderType(Enum):
    """Supported OAuth provider types."""

    COGNITO = "cognito"
    OKTA = "okta"
    AZURE_AD = "azure_ad"
    GOOGLE = "google"
    GITHUB = "github"
    CUSTOM = "custom"


class TokenEncryptionService(Protocol):
    """Protocol for token encryption service."""

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext."""
        ...

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext."""
        ...


class SecretsManagerClient(Protocol):
    """Protocol for secrets manager client."""

    async def get_secret(self, secret_id: str) -> str:
        """Get secret value."""
        ...

    async def put_secret(self, secret_id: str, value: str) -> None:
        """Store secret value."""
        ...

    async def delete_secret(self, secret_id: str) -> bool:
        """Delete secret."""
        ...


class DynamoDBClient(Protocol):
    """Protocol for DynamoDB client."""

    async def put_item(self, table_name: str, item: dict) -> None:
        """Put item."""
        ...

    async def get_item(self, table_name: str, key: dict) -> Optional[dict]:
        """Get item."""
        ...

    async def delete_item(self, table_name: str, key: dict) -> None:
        """Delete item."""
        ...

    async def query(
        self, table_name: str, key_condition: str, values: dict
    ) -> list[dict]:
        """Query items."""
        ...


class HTTPClient(Protocol):
    """Protocol for HTTP client."""

    async def post(self, url: str, data: dict, headers: Optional[dict] = None) -> dict:
        """POST request."""
        ...


@dataclass
class OAuthProvider:
    """OAuth provider configuration."""

    provider_id: str
    provider_type: OAuthProviderType
    client_id: str
    client_secret_arn: str  # Secrets Manager ARN
    authorization_url: str
    token_url: str
    userinfo_url: Optional[str] = None
    scopes: list[str] = field(default_factory=list)
    custom_claims: Optional[dict[str, str]] = None
    audience: Optional[str] = None
    issuer: Optional[str] = None
    pkce_required: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def cognito(
        cls,
        provider_id: str,
        user_pool_id: str,
        client_id: str,
        client_secret_arn: str,
        region: str = "us-east-1",
        scopes: Optional[list[str]] = None,
    ) -> "OAuthProvider":
        """Create Cognito provider configuration."""
        domain = f"https://{user_pool_id}.auth.{region}.amazoncognito.com"
        return cls(
            provider_id=provider_id,
            provider_type=OAuthProviderType.COGNITO,
            client_id=client_id,
            client_secret_arn=client_secret_arn,
            authorization_url=f"{domain}/oauth2/authorize",
            token_url=f"{domain}/oauth2/token",
            userinfo_url=f"{domain}/oauth2/userInfo",
            scopes=scopes or ["openid", "profile", "email"],
        )

    @classmethod
    def okta(
        cls,
        provider_id: str,
        okta_domain: str,
        client_id: str,
        client_secret_arn: str,
        scopes: Optional[list[str]] = None,
    ) -> "OAuthProvider":
        """Create Okta provider configuration."""
        return cls(
            provider_id=provider_id,
            provider_type=OAuthProviderType.OKTA,
            client_id=client_id,
            client_secret_arn=client_secret_arn,
            authorization_url=f"https://{okta_domain}/oauth2/default/v1/authorize",
            token_url=f"https://{okta_domain}/oauth2/default/v1/token",
            userinfo_url=f"https://{okta_domain}/oauth2/default/v1/userinfo",
            scopes=scopes or ["openid", "profile", "email"],
        )

    @classmethod
    def azure_ad(
        cls,
        provider_id: str,
        tenant_id: str,
        client_id: str,
        client_secret_arn: str,
        scopes: Optional[list[str]] = None,
    ) -> "OAuthProvider":
        """Create Azure AD provider configuration."""
        base_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0"
        return cls(
            provider_id=provider_id,
            provider_type=OAuthProviderType.AZURE_AD,
            client_id=client_id,
            client_secret_arn=client_secret_arn,
            authorization_url=f"{base_url}/authorize",
            token_url=f"{base_url}/token",
            scopes=scopes or ["openid", "profile", "email", "offline_access"],
        )


@dataclass
class AuthorizationRequest:
    """Pending authorization request."""

    request_id: str
    agent_id: str
    user_id: str
    provider_id: str
    redirect_uri: str
    scopes: list[str]
    state: str
    code_verifier: Optional[str]  # For PKCE
    code_challenge: Optional[str]
    authorization_url: str
    expires_at: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DelegatedToken:
    """Token delegated by user to agent."""

    token_id: str
    agent_id: str
    user_id: str
    provider_id: str
    access_token_encrypted: str
    refresh_token_encrypted: Optional[str]
    id_token_encrypted: Optional[str]
    token_type: str
    scopes: list[str]
    expires_at: datetime
    refresh_expires_at: Optional[datetime]
    user_info: Optional[dict[str, Any]]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_refreshed_at: Optional[datetime] = None

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Check if access token is expired or about to expire."""
        return datetime.now(timezone.utc) >= (
            self.expires_at - timedelta(seconds=buffer_seconds)
        )

    def can_refresh(self) -> bool:
        """Check if token can be refreshed."""
        if not self.refresh_token_encrypted:
            return False
        if self.refresh_expires_at:
            return datetime.now(timezone.utc) < self.refresh_expires_at
        return True


@dataclass
class TokenRevocationResult:
    """Result of token revocation."""

    success: bool
    agent_id: str
    user_id: str
    provider_id: Optional[str]
    tokens_revoked: int
    errors: list[str] = field(default_factory=list)


@dataclass
class OAuthDelegationConfig:
    """Configuration for OAuth delegation service."""

    providers_table: str = "aura-oauth-providers"
    tokens_table: str = "aura-delegated-tokens"
    requests_table: str = "aura-auth-requests"
    request_ttl_minutes: int = 10
    token_refresh_buffer_seconds: int = 300
    max_tokens_per_user_agent: int = 10


class OAuthDelegationService:
    """Secure OAuth delegation for agent-to-service authentication.

    Implements AWS AgentCore Identity parity:
    - OAuth 2.0 authorization code flow with PKCE
    - Secure token vault using Secrets Manager + DynamoDB
    - Automatic token refresh before expiration
    - Multi-tenant support with custom claims
    - Support for Cognito, Okta, Azure AD, Google, GitHub

    Security Features:
    - All tokens encrypted at rest
    - PKCE for authorization code flow
    - State parameter for CSRF protection
    - Token revocation support
    - Audit logging of all operations

    Usage:
        service = OAuthDelegationService(
            secrets_client=secrets_client,
            dynamodb_client=dynamodb_client,
            http_client=http_client,
            encryption_service=encryption_service,
        )

        # Start authorization flow
        auth_request = await service.initiate_authorization(
            agent_id="my-agent",
            user_id="user-123",
            provider_id="okta-prod",
            scopes=["read:users", "write:messages"],
            redirect_uri="https://app.aura.local/oauth/callback",
        )

        # User completes authorization...

        # Exchange code for tokens
        token = await service.complete_authorization(
            authorization_code="abc123",
            state=auth_request.state,
        )

        # Get access token (auto-refreshes if needed)
        access_token = await service.get_access_token(
            agent_id="my-agent",
            user_id="user-123",
            provider_id="okta-prod",
        )
    """

    def __init__(
        self,
        secrets_client: SecretsManagerClient,
        dynamodb_client: DynamoDBClient,
        http_client: HTTPClient,
        encryption_service: TokenEncryptionService,
        config: Optional[OAuthDelegationConfig] = None,
    ):
        """Initialize OAuth delegation service.

        Args:
            secrets_client: Client for AWS Secrets Manager
            dynamodb_client: Client for DynamoDB
            http_client: HTTP client for token endpoints
            encryption_service: Service for token encryption/decryption
            config: Service configuration
        """
        self.secrets = secrets_client
        self.dynamodb = dynamodb_client
        self.http = http_client
        self.encryption = encryption_service
        self.config = config or OAuthDelegationConfig()
        self._providers_cache: dict[str, OAuthProvider] = {}

    async def register_provider(self, provider: OAuthProvider) -> None:
        """Register an OAuth provider.

        Args:
            provider: OAuth provider configuration
        """
        await self.dynamodb.put_item(
            self.config.providers_table,
            {
                "provider_id": provider.provider_id,
                "provider_type": provider.provider_type.value,
                "client_id": provider.client_id,
                "client_secret_arn": provider.client_secret_arn,
                "authorization_url": provider.authorization_url,
                "token_url": provider.token_url,
                "userinfo_url": provider.userinfo_url,
                "scopes": provider.scopes,
                "custom_claims": provider.custom_claims,
                "pkce_required": provider.pkce_required,
                "created_at": provider.created_at.isoformat(),
            },
        )
        self._providers_cache[provider.provider_id] = provider
        logger.info(f"Registered OAuth provider: {provider.provider_id}")

    async def get_provider(self, provider_id: str) -> Optional[OAuthProvider]:
        """Get OAuth provider configuration.

        Args:
            provider_id: Provider identifier

        Returns:
            Provider configuration or None
        """
        if provider_id in self._providers_cache:
            return self._providers_cache[provider_id]

        item = await self.dynamodb.get_item(
            self.config.providers_table, {"provider_id": provider_id}
        )
        if not item:
            return None

        provider = OAuthProvider(
            provider_id=item["provider_id"],
            provider_type=OAuthProviderType(item["provider_type"]),
            client_id=item["client_id"],
            client_secret_arn=item["client_secret_arn"],
            authorization_url=item["authorization_url"],
            token_url=item["token_url"],
            userinfo_url=item.get("userinfo_url"),
            scopes=item.get("scopes", []),
            custom_claims=item.get("custom_claims"),
            pkce_required=item.get("pkce_required", True),
            created_at=datetime.fromisoformat(item["created_at"]),
        )
        self._providers_cache[provider_id] = provider
        return provider

    async def initiate_authorization(
        self,
        agent_id: str,
        user_id: str,
        provider_id: str,
        scopes: list[str],
        redirect_uri: str,
        additional_params: Optional[dict[str, str]] = None,
    ) -> AuthorizationRequest:
        """Start OAuth authorization flow.

        Args:
            agent_id: Agent requesting authorization
            user_id: User to authorize
            provider_id: OAuth provider to use
            scopes: Requested scopes
            redirect_uri: OAuth callback URI
            additional_params: Additional authorization parameters

        Returns:
            Authorization request with URL for user

        Raises:
            ValueError: If provider not found
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"OAuth provider not found: {provider_id}")

        # Generate security parameters
        state = secrets.token_urlsafe(32)
        code_verifier = None
        code_challenge = None

        if provider.pkce_required:
            code_verifier = secrets.token_urlsafe(64)
            code_challenge = self._generate_code_challenge(code_verifier)

        # Build authorization URL
        params = {
            "response_type": "code",
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
        }

        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        if provider.audience:
            params["audience"] = provider.audience

        if additional_params:
            params.update(additional_params)

        authorization_url = (
            f"{provider.authorization_url}?{urllib.parse.urlencode(params)}"
        )

        # Create authorization request
        request = AuthorizationRequest(
            request_id=secrets.token_urlsafe(16),
            agent_id=agent_id,
            user_id=user_id,
            provider_id=provider_id,
            redirect_uri=redirect_uri,
            scopes=scopes,
            state=state,
            code_verifier=code_verifier,
            code_challenge=code_challenge,
            authorization_url=authorization_url,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=self.config.request_ttl_minutes),
        )

        # Store request
        await self.dynamodb.put_item(
            self.config.requests_table,
            {
                "state": state,
                "request_id": request.request_id,
                "agent_id": agent_id,
                "user_id": user_id,
                "provider_id": provider_id,
                "redirect_uri": redirect_uri,
                "scopes": scopes,
                "code_verifier": code_verifier,
                "expires_at": request.expires_at.isoformat(),
                "created_at": request.created_at.isoformat(),
                "ttl": int(request.expires_at.timestamp()),
            },
        )

        logger.info(
            f"Initiated OAuth authorization: agent={agent_id}, "
            f"user={user_id}, provider={provider_id}"
        )

        return request

    async def complete_authorization(
        self,
        authorization_code: str,
        state: str,
    ) -> DelegatedToken:
        """Exchange authorization code for tokens.

        Args:
            authorization_code: Code from OAuth callback
            state: State parameter from callback

        Returns:
            Delegated token

        Raises:
            ValueError: If state invalid or expired
        """
        # Retrieve authorization request
        request_item = await self.dynamodb.get_item(
            self.config.requests_table, {"state": state}
        )
        if not request_item:
            raise ValueError("Invalid or expired authorization state")

        expires_at = datetime.fromisoformat(request_item["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            raise ValueError("Authorization request expired")

        # Get provider
        provider = await self.get_provider(request_item["provider_id"])
        if not provider:
            raise ValueError(f"Provider not found: {request_item['provider_id']}")

        # Get client secret
        client_secret = await self.secrets.get_secret(provider.client_secret_arn)

        # Exchange code for tokens
        token_params = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": request_item["redirect_uri"],
            "client_id": provider.client_id,
            "client_secret": client_secret,
        }

        if request_item.get("code_verifier"):
            token_params["code_verifier"] = request_item["code_verifier"]

        token_response = await self.http.post(
            provider.token_url,
            data=token_params,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # Parse token response
        access_token = token_response.get("access_token")
        if not access_token:
            raise ValueError("No access token in response")

        expires_in = token_response.get("expires_in", 3600)
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        refresh_token = token_response.get("refresh_token")
        refresh_expires_at = None
        if refresh_token:
            refresh_expires_in = token_response.get("refresh_expires_in")
            if refresh_expires_in:
                refresh_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=refresh_expires_in
                )

        # Get user info if endpoint available
        user_info = None
        if provider.userinfo_url:
            try:
                user_info = await self._fetch_user_info(
                    provider.userinfo_url, access_token
                )
            except Exception as e:
                logger.warning(f"Failed to fetch user info: {e}")

        # Create delegated token
        token = DelegatedToken(
            token_id=secrets.token_urlsafe(16),
            agent_id=request_item["agent_id"],
            user_id=request_item["user_id"],
            provider_id=request_item["provider_id"],
            access_token_encrypted=self.encryption.encrypt(access_token),
            refresh_token_encrypted=(
                self.encryption.encrypt(refresh_token) if refresh_token else None
            ),
            id_token_encrypted=(
                self.encryption.encrypt(token_response["id_token"])
                if "id_token" in token_response
                else None
            ),
            token_type=token_response.get("token_type", "Bearer"),
            scopes=request_item["scopes"],
            expires_at=token_expires_at,
            refresh_expires_at=refresh_expires_at,
            user_info=user_info,
        )

        # Store token
        await self._store_token(token)

        # Clean up authorization request
        await self.dynamodb.delete_item(self.config.requests_table, {"state": state})

        logger.info(
            f"Completed OAuth authorization: agent={token.agent_id}, "
            f"user={token.user_id}, provider={token.provider_id}"
        )

        return token

    async def get_access_token(
        self,
        agent_id: str,
        user_id: str,
        provider_id: str,
        force_refresh: bool = False,
    ) -> str:
        """Get valid access token, refreshing if needed.

        Args:
            agent_id: Agent identifier
            user_id: User identifier
            provider_id: Provider identifier
            force_refresh: Force token refresh

        Returns:
            Valid access token

        Raises:
            ValueError: If no valid token exists
        """
        token = await self._get_stored_token(agent_id, user_id, provider_id)
        if not token:
            raise ValueError(
                f"No delegated token found: agent={agent_id}, "
                f"user={user_id}, provider={provider_id}"
            )

        # Check if refresh needed
        if force_refresh or token.is_expired(self.config.token_refresh_buffer_seconds):
            if not token.can_refresh():
                raise ValueError("Token expired and cannot be refreshed")

            token = await self._refresh_token(token)

        return self.encryption.decrypt(token.access_token_encrypted)

    async def get_delegated_token(
        self,
        agent_id: str,
        user_id: str,
        provider_id: str,
    ) -> Optional[DelegatedToken]:
        """Get full delegated token info.

        Args:
            agent_id: Agent identifier
            user_id: User identifier
            provider_id: Provider identifier

        Returns:
            Delegated token or None
        """
        return await self._get_stored_token(agent_id, user_id, provider_id)

    async def revoke_delegation(
        self,
        agent_id: str,
        user_id: str,
        provider_id: Optional[str] = None,
    ) -> TokenRevocationResult:
        """Revoke agent's delegated access.

        Args:
            agent_id: Agent identifier
            user_id: User identifier
            provider_id: Optional specific provider (None = all)

        Returns:
            Revocation result
        """
        tokens_revoked = 0
        errors = []

        if provider_id:
            # Revoke specific provider
            try:
                await self.dynamodb.delete_item(
                    self.config.tokens_table,
                    {
                        "agent_user_key": f"{agent_id}#{user_id}",
                        "provider_id": provider_id,
                    },
                )
                tokens_revoked = 1
            except Exception as e:
                errors.append(f"Failed to revoke {provider_id}: {e}")
        else:
            # Revoke all providers for this agent/user
            tokens = await self.dynamodb.query(
                self.config.tokens_table,
                key_condition="agent_user_key = :key",
                values={":key": f"{agent_id}#{user_id}"},
            )

            for token_item in tokens:
                try:
                    await self.dynamodb.delete_item(
                        self.config.tokens_table,
                        {
                            "agent_user_key": f"{agent_id}#{user_id}",
                            "provider_id": token_item["provider_id"],
                        },
                    )
                    tokens_revoked += 1
                except Exception as e:
                    errors.append(f"Failed to revoke {token_item['provider_id']}: {e}")

        result = TokenRevocationResult(
            success=len(errors) == 0,
            agent_id=agent_id,
            user_id=user_id,
            provider_id=provider_id,
            tokens_revoked=tokens_revoked,
            errors=errors,
        )

        logger.info(
            f"Revoked OAuth delegations: agent={agent_id}, user={user_id}, "
            f"revoked={tokens_revoked}, errors={len(errors)}"
        )

        return result

    async def list_delegations(
        self,
        agent_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List active delegations.

        Args:
            agent_id: Filter by agent
            user_id: Filter by user

        Returns:
            List of delegation summaries
        """
        if agent_id and user_id:
            tokens = await self.dynamodb.query(
                self.config.tokens_table,
                key_condition="agent_user_key = :key",
                values={":key": f"{agent_id}#{user_id}"},
            )
        else:
            # Would need GSI for other queries
            tokens = []

        return [
            {
                "agent_id": t.get("agent_id"),
                "user_id": t.get("user_id"),
                "provider_id": t.get("provider_id"),
                "scopes": t.get("scopes", []),
                "expires_at": t.get("expires_at"),
                "created_at": t.get("created_at"),
            }
            for t in tokens
        ]

    async def _refresh_token(self, token: DelegatedToken) -> DelegatedToken:
        """Refresh an expired token.

        Args:
            token: Token to refresh

        Returns:
            Refreshed token
        """
        if not token.refresh_token_encrypted:
            raise ValueError("No refresh token available")

        provider = await self.get_provider(token.provider_id)
        if not provider:
            raise ValueError(f"Provider not found: {token.provider_id}")

        client_secret = await self.secrets.get_secret(provider.client_secret_arn)
        refresh_token = self.encryption.decrypt(token.refresh_token_encrypted)

        token_response = await self.http.post(
            provider.token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": provider.client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        access_token = token_response.get("access_token")
        if not access_token:
            raise ValueError("No access token in refresh response")

        expires_in = token_response.get("expires_in", 3600)

        # Update token
        token.access_token_encrypted = self.encryption.encrypt(access_token)
        token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        token.last_refreshed_at = datetime.now(timezone.utc)

        # Check if new refresh token provided
        new_refresh_token = token_response.get("refresh_token")
        if new_refresh_token:
            token.refresh_token_encrypted = self.encryption.encrypt(new_refresh_token)

        # Store updated token
        await self._store_token(token)

        logger.debug(
            f"Refreshed token for agent={token.agent_id}, user={token.user_id}"
        )

        return token

    async def _store_token(self, token: DelegatedToken) -> None:
        """Store token in DynamoDB.

        Args:
            token: Token to store
        """
        await self.dynamodb.put_item(
            self.config.tokens_table,
            {
                "agent_user_key": f"{token.agent_id}#{token.user_id}",
                "provider_id": token.provider_id,
                "token_id": token.token_id,
                "agent_id": token.agent_id,
                "user_id": token.user_id,
                "access_token_encrypted": token.access_token_encrypted,
                "refresh_token_encrypted": token.refresh_token_encrypted,
                "id_token_encrypted": token.id_token_encrypted,
                "token_type": token.token_type,
                "scopes": token.scopes,
                "expires_at": token.expires_at.isoformat(),
                "refresh_expires_at": (
                    token.refresh_expires_at.isoformat()
                    if token.refresh_expires_at
                    else None
                ),
                "user_info": token.user_info,
                "created_at": token.created_at.isoformat(),
                "last_refreshed_at": (
                    token.last_refreshed_at.isoformat()
                    if token.last_refreshed_at
                    else None
                ),
            },
        )

    async def _get_stored_token(
        self, agent_id: str, user_id: str, provider_id: str
    ) -> Optional[DelegatedToken]:
        """Retrieve stored token.

        Args:
            agent_id: Agent identifier
            user_id: User identifier
            provider_id: Provider identifier

        Returns:
            Token or None
        """
        item = await self.dynamodb.get_item(
            self.config.tokens_table,
            {
                "agent_user_key": f"{agent_id}#{user_id}",
                "provider_id": provider_id,
            },
        )

        if not item:
            return None

        return DelegatedToken(
            token_id=item["token_id"],
            agent_id=item["agent_id"],
            user_id=item["user_id"],
            provider_id=item["provider_id"],
            access_token_encrypted=item["access_token_encrypted"],
            refresh_token_encrypted=item.get("refresh_token_encrypted"),
            id_token_encrypted=item.get("id_token_encrypted"),
            token_type=item.get("token_type", "Bearer"),
            scopes=item.get("scopes", []),
            expires_at=datetime.fromisoformat(item["expires_at"]),
            refresh_expires_at=(
                datetime.fromisoformat(item["refresh_expires_at"])
                if item.get("refresh_expires_at")
                else None
            ),
            user_info=item.get("user_info"),
            created_at=datetime.fromisoformat(item["created_at"]),
            last_refreshed_at=(
                datetime.fromisoformat(item["last_refreshed_at"])
                if item.get("last_refreshed_at")
                else None
            ),
        )

    async def _fetch_user_info(self, userinfo_url: str, access_token: str) -> dict:
        """Fetch user info from provider.

        Args:
            userinfo_url: User info endpoint URL
            access_token: Access token

        Returns:
            User info dictionary
        """
        return await self.http.post(
            userinfo_url,
            data={},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def _generate_code_challenge(self, code_verifier: str) -> str:
        """Generate PKCE code challenge.

        Args:
            code_verifier: Code verifier string

        Returns:
            Base64url encoded code challenge
        """
        digest = hashlib.sha256(code_verifier.encode()).digest()
        import base64

        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    def get_service_stats(self) -> dict:
        """Get service statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "providers_cached": len(self._providers_cache),
            "config": {
                "request_ttl_minutes": self.config.request_ttl_minutes,
                "token_refresh_buffer_seconds": self.config.token_refresh_buffer_seconds,
            },
        }
