"""
Project Aura - OAuth Delegation Service Tests

Tests for the OAuth delegation service that enables agents to securely
act on behalf of users with third-party services through OAuth 2.0.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.oauth_delegation_service import (
    AuthorizationRequest,
    DelegatedToken,
    OAuthDelegationConfig,
    OAuthDelegationService,
    OAuthProvider,
    OAuthProviderType,
    TokenRevocationResult,
)


class TestOAuthProviderType:
    """Tests for OAuthProviderType enum."""

    def test_cognito(self):
        """Test Cognito provider type."""
        assert OAuthProviderType.COGNITO.value == "cognito"

    def test_okta(self):
        """Test Okta provider type."""
        assert OAuthProviderType.OKTA.value == "okta"

    def test_azure_ad(self):
        """Test Azure AD provider type."""
        assert OAuthProviderType.AZURE_AD.value == "azure_ad"

    def test_google(self):
        """Test Google provider type."""
        assert OAuthProviderType.GOOGLE.value == "google"

    def test_github(self):
        """Test GitHub provider type."""
        assert OAuthProviderType.GITHUB.value == "github"

    def test_custom(self):
        """Test custom provider type."""
        assert OAuthProviderType.CUSTOM.value == "custom"

    def test_all_providers_exist(self):
        """Test all expected providers exist."""
        providers = list(OAuthProviderType)
        assert len(providers) == 6


class TestOAuthProvider:
    """Tests for OAuthProvider dataclass."""

    def test_minimal_provider(self):
        """Test minimal provider creation."""
        provider = OAuthProvider(
            provider_id="test-provider",
            provider_type=OAuthProviderType.CUSTOM,
            client_id="client-123",
            client_secret_arn="arn:aws:secretsmanager:us-east-1:123456:secret:test",
            authorization_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
        )
        assert provider.provider_id == "test-provider"
        assert provider.provider_type == OAuthProviderType.CUSTOM
        assert provider.client_id == "client-123"
        assert provider.pkce_required is True
        assert provider.scopes == []

    def test_full_provider(self):
        """Test full provider creation."""
        provider = OAuthProvider(
            provider_id="full-provider",
            provider_type=OAuthProviderType.OKTA,
            client_id="client-full",
            client_secret_arn="arn:aws:secretsmanager:us-east-1:123456:secret:full",
            authorization_url="https://okta.example.com/authorize",
            token_url="https://okta.example.com/token",
            userinfo_url="https://okta.example.com/userinfo",
            scopes=["openid", "profile", "email"],
            custom_claims={"org": "aura"},
            audience="https://api.example.com",
            issuer="https://okta.example.com",
            pkce_required=True,
        )
        assert provider.userinfo_url == "https://okta.example.com/userinfo"
        assert "openid" in provider.scopes
        assert provider.custom_claims["org"] == "aura"
        assert provider.audience == "https://api.example.com"

    def test_cognito_factory(self):
        """Test Cognito provider factory method."""
        provider = OAuthProvider.cognito(
            provider_id="cognito-prod",
            user_pool_id="us-east-1_abc123",
            client_id="cognito-client",
            client_secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:cog",
            region="us-east-1",
        )
        assert provider.provider_type == OAuthProviderType.COGNITO
        assert "amazoncognito.com" in provider.authorization_url
        assert "amazoncognito.com" in provider.token_url
        assert "openid" in provider.scopes

    def test_okta_factory(self):
        """Test Okta provider factory method."""
        provider = OAuthProvider.okta(
            provider_id="okta-prod",
            okta_domain="dev-12345.okta.com",
            client_id="okta-client",
            client_secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:okta",
        )
        assert provider.provider_type == OAuthProviderType.OKTA
        assert "dev-12345.okta.com" in provider.authorization_url
        assert "dev-12345.okta.com" in provider.token_url

    def test_azure_ad_factory(self):
        """Test Azure AD provider factory method."""
        provider = OAuthProvider.azure_ad(
            provider_id="azure-prod",
            tenant_id="tenant-guid",
            client_id="azure-client",
            client_secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:azure",
        )
        assert provider.provider_type == OAuthProviderType.AZURE_AD
        assert "microsoftonline.com" in provider.authorization_url
        assert "tenant-guid" in provider.token_url
        assert "offline_access" in provider.scopes


class TestAuthorizationRequest:
    """Tests for AuthorizationRequest dataclass."""

    def test_authorization_request_creation(self):
        """Test authorization request creation."""
        request = AuthorizationRequest(
            request_id="req-001",
            agent_id="agent-001",
            user_id="user-001",
            provider_id="okta-prod",
            redirect_uri="https://app.aura.ai/callback",
            scopes=["read", "write"],
            state="random-state-token",
            code_verifier="pkce-verifier",
            code_challenge="pkce-challenge",
            authorization_url="https://okta.example.com/authorize?...",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        assert request.request_id == "req-001"
        assert request.agent_id == "agent-001"
        assert request.user_id == "user-001"
        assert "read" in request.scopes

    def test_authorization_request_with_pkce(self):
        """Test authorization request with PKCE parameters."""
        request = AuthorizationRequest(
            request_id="pkce-req",
            agent_id="agent",
            user_id="user",
            provider_id="provider",
            redirect_uri="https://callback",
            scopes=[],
            state="state",
            code_verifier="verifier-64-chars-long-for-pkce",
            code_challenge="challenge-sha256",
            authorization_url="https://auth",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        assert request.code_verifier is not None
        assert request.code_challenge is not None

    def test_authorization_request_without_pkce(self):
        """Test authorization request without PKCE."""
        request = AuthorizationRequest(
            request_id="no-pkce-req",
            agent_id="agent",
            user_id="user",
            provider_id="provider",
            redirect_uri="https://callback",
            scopes=[],
            state="state",
            code_verifier=None,
            code_challenge=None,
            authorization_url="https://auth",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        assert request.code_verifier is None
        assert request.code_challenge is None


class TestDelegatedToken:
    """Tests for DelegatedToken dataclass."""

    def test_minimal_token(self):
        """Test minimal token creation."""
        token = DelegatedToken(
            token_id="tok-001",
            agent_id="agent-001",
            user_id="user-001",
            provider_id="okta-prod",
            access_token_encrypted="encrypted-access-token",
            refresh_token_encrypted=None,
            id_token_encrypted=None,
            token_type="Bearer",
            scopes=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            refresh_expires_at=None,
            user_info=None,
        )
        assert token.token_id == "tok-001"
        assert token.token_type == "Bearer"
        assert token.refresh_token_encrypted is None

    def test_full_token(self):
        """Test full token creation."""
        token = DelegatedToken(
            token_id="tok-full",
            agent_id="agent",
            user_id="user",
            provider_id="provider",
            access_token_encrypted="access",
            refresh_token_encrypted="refresh",
            id_token_encrypted="id-token",
            token_type="Bearer",
            scopes=["openid", "profile"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            refresh_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            user_info={"email": "user@example.com"},
        )
        assert token.refresh_token_encrypted is not None
        assert token.id_token_encrypted is not None
        assert token.user_info["email"] == "user@example.com"

    def test_is_expired_not_expired(self):
        """Test is_expired returns False for valid token."""
        token = DelegatedToken(
            token_id="tok",
            agent_id="agent",
            user_id="user",
            provider_id="provider",
            access_token_encrypted="access",
            refresh_token_encrypted=None,
            id_token_encrypted=None,
            token_type="Bearer",
            scopes=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            refresh_expires_at=None,
            user_info=None,
        )
        assert token.is_expired() is False

    def test_is_expired_expired(self):
        """Test is_expired returns True for expired token."""
        token = DelegatedToken(
            token_id="tok",
            agent_id="agent",
            user_id="user",
            provider_id="provider",
            access_token_encrypted="access",
            refresh_token_encrypted=None,
            id_token_encrypted=None,
            token_type="Bearer",
            scopes=[],
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            refresh_expires_at=None,
            user_info=None,
        )
        assert token.is_expired() is True

    def test_is_expired_with_buffer(self):
        """Test is_expired with custom buffer."""
        token = DelegatedToken(
            token_id="tok",
            agent_id="agent",
            user_id="user",
            provider_id="provider",
            access_token_encrypted="access",
            refresh_token_encrypted=None,
            id_token_encrypted=None,
            token_type="Bearer",
            scopes=[],
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
            refresh_expires_at=None,
            user_info=None,
        )
        # With 60s buffer, token expiring in 30s is considered expired
        assert token.is_expired(buffer_seconds=60) is True
        # With 10s buffer, token expiring in 30s is not expired
        assert token.is_expired(buffer_seconds=10) is False

    def test_can_refresh_with_refresh_token(self):
        """Test can_refresh with valid refresh token."""
        token = DelegatedToken(
            token_id="tok",
            agent_id="agent",
            user_id="user",
            provider_id="provider",
            access_token_encrypted="access",
            refresh_token_encrypted="refresh",
            id_token_encrypted=None,
            token_type="Bearer",
            scopes=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            refresh_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            user_info=None,
        )
        assert token.can_refresh() is True

    def test_can_refresh_without_refresh_token(self):
        """Test can_refresh without refresh token."""
        token = DelegatedToken(
            token_id="tok",
            agent_id="agent",
            user_id="user",
            provider_id="provider",
            access_token_encrypted="access",
            refresh_token_encrypted=None,
            id_token_encrypted=None,
            token_type="Bearer",
            scopes=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            refresh_expires_at=None,
            user_info=None,
        )
        assert token.can_refresh() is False

    def test_can_refresh_expired_refresh_token(self):
        """Test can_refresh with expired refresh token."""
        token = DelegatedToken(
            token_id="tok",
            agent_id="agent",
            user_id="user",
            provider_id="provider",
            access_token_encrypted="access",
            refresh_token_encrypted="refresh",
            id_token_encrypted=None,
            token_type="Bearer",
            scopes=[],
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            refresh_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            user_info=None,
        )
        assert token.can_refresh() is False


class TestTokenRevocationResult:
    """Tests for TokenRevocationResult dataclass."""

    def test_successful_revocation(self):
        """Test successful revocation result."""
        result = TokenRevocationResult(
            success=True,
            agent_id="agent-001",
            user_id="user-001",
            provider_id="okta-prod",
            tokens_revoked=1,
        )
        assert result.success is True
        assert result.tokens_revoked == 1
        assert result.errors == []

    def test_failed_revocation(self):
        """Test failed revocation result."""
        result = TokenRevocationResult(
            success=False,
            agent_id="agent-001",
            user_id="user-001",
            provider_id="okta-prod",
            tokens_revoked=0,
            errors=["Failed to delete token: AccessDenied"],
        )
        assert result.success is False
        assert result.tokens_revoked == 0
        assert len(result.errors) == 1

    def test_partial_revocation(self):
        """Test partial revocation result."""
        result = TokenRevocationResult(
            success=False,
            agent_id="agent",
            user_id="user",
            provider_id=None,
            tokens_revoked=2,
            errors=["Failed for provider-3"],
        )
        assert result.tokens_revoked == 2
        assert result.provider_id is None


class TestOAuthDelegationConfig:
    """Tests for OAuthDelegationConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = OAuthDelegationConfig()
        assert config.providers_table == "aura-oauth-providers"
        assert config.tokens_table == "aura-delegated-tokens"
        assert config.requests_table == "aura-auth-requests"
        assert config.request_ttl_minutes == 10
        assert config.token_refresh_buffer_seconds == 300
        assert config.max_tokens_per_user_agent == 10

    def test_custom_config(self):
        """Test custom configuration values."""
        config = OAuthDelegationConfig(
            providers_table="custom-providers",
            tokens_table="custom-tokens",
            requests_table="custom-requests",
            request_ttl_minutes=15,
            token_refresh_buffer_seconds=600,
            max_tokens_per_user_agent=20,
        )
        assert config.providers_table == "custom-providers"
        assert config.request_ttl_minutes == 15
        assert config.max_tokens_per_user_agent == 20


class TestOAuthDelegationService:
    """Tests for OAuthDelegationService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_secrets = MagicMock()
        self.mock_secrets.get_secret = AsyncMock(return_value="client-secret")
        self.mock_secrets.put_secret = AsyncMock()
        self.mock_secrets.delete_secret = AsyncMock(return_value=True)

        self.mock_dynamodb = MagicMock()
        self.mock_dynamodb.put_item = AsyncMock()
        self.mock_dynamodb.get_item = AsyncMock(return_value=None)
        self.mock_dynamodb.delete_item = AsyncMock()
        self.mock_dynamodb.query = AsyncMock(return_value=[])

        self.mock_http = MagicMock()
        self.mock_http.post = AsyncMock(
            return_value={
                "access_token": "new-access-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "new-refresh-token",
            }
        )

        self.mock_encryption = MagicMock()
        self.mock_encryption.encrypt = MagicMock(side_effect=lambda x: f"encrypted:{x}")
        self.mock_encryption.decrypt = MagicMock(
            side_effect=lambda x: x.replace("encrypted:", "")
        )

        self.service = OAuthDelegationService(
            secrets_client=self.mock_secrets,
            dynamodb_client=self.mock_dynamodb,
            http_client=self.mock_http,
            encryption_service=self.mock_encryption,
        )

    def test_init_default_config(self):
        """Test initialization with default config."""
        assert self.service.config is not None
        assert self.service.config.providers_table == "aura-oauth-providers"

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = OAuthDelegationConfig(providers_table="custom")
        service = OAuthDelegationService(
            secrets_client=self.mock_secrets,
            dynamodb_client=self.mock_dynamodb,
            http_client=self.mock_http,
            encryption_service=self.mock_encryption,
            config=config,
        )
        assert service.config.providers_table == "custom"

    def test_providers_cache_initialized(self):
        """Test providers cache is initialized."""
        assert self.service._providers_cache == {}

    @pytest.mark.asyncio
    async def test_register_provider(self):
        """Test registering an OAuth provider."""
        provider = OAuthProvider(
            provider_id="test-okta",
            provider_type=OAuthProviderType.OKTA,
            client_id="client-123",
            client_secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:test",
            authorization_url="https://test.okta.com/authorize",
            token_url="https://test.okta.com/token",
        )

        await self.service.register_provider(provider)

        self.mock_dynamodb.put_item.assert_called_once()
        assert "test-okta" in self.service._providers_cache

    @pytest.mark.asyncio
    async def test_get_provider_from_cache(self):
        """Test getting provider from cache."""
        provider = OAuthProvider(
            provider_id="cached-provider",
            provider_type=OAuthProviderType.OKTA,
            client_id="client",
            client_secret_arn="arn",
            authorization_url="https://auth",
            token_url="https://token",
        )
        self.service._providers_cache["cached-provider"] = provider

        result = await self.service.get_provider("cached-provider")

        assert result == provider
        self.mock_dynamodb.get_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_provider_not_found(self):
        """Test getting non-existent provider."""
        self.mock_dynamodb.get_item.return_value = None

        result = await self.service.get_provider("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_provider_from_dynamodb(self):
        """Test getting provider from DynamoDB."""
        self.mock_dynamodb.get_item.return_value = {
            "provider_id": "db-provider",
            "provider_type": "okta",
            "client_id": "client",
            "client_secret_arn": "arn",
            "authorization_url": "https://auth",
            "token_url": "https://token",
            "scopes": ["openid"],
            "pkce_required": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        result = await self.service.get_provider("db-provider")

        assert result is not None
        assert result.provider_id == "db-provider"
        assert result.provider_type == OAuthProviderType.OKTA

    @pytest.mark.asyncio
    async def test_initiate_authorization_provider_not_found(self):
        """Test initiate authorization with non-existent provider."""
        with pytest.raises(ValueError, match="OAuth provider not found"):
            await self.service.initiate_authorization(
                agent_id="agent",
                user_id="user",
                provider_id="nonexistent",
                scopes=["read"],
                redirect_uri="https://callback",
            )

    def test_get_service_stats(self):
        """Test getting service statistics."""
        stats = self.service.get_service_stats()

        assert "providers_cached" in stats
        assert "config" in stats
        assert stats["providers_cached"] == 0


class TestOAuthDelegationServiceRevocation:
    """Tests for token revocation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_secrets = MagicMock()
        self.mock_dynamodb = MagicMock()
        self.mock_dynamodb.delete_item = AsyncMock()
        self.mock_dynamodb.query = AsyncMock(return_value=[])
        self.mock_http = MagicMock()
        self.mock_encryption = MagicMock()

        self.service = OAuthDelegationService(
            secrets_client=self.mock_secrets,
            dynamodb_client=self.mock_dynamodb,
            http_client=self.mock_http,
            encryption_service=self.mock_encryption,
        )

    @pytest.mark.asyncio
    async def test_revoke_delegation_specific_provider(self):
        """Test revoking delegation for specific provider."""
        result = await self.service.revoke_delegation(
            agent_id="agent-001",
            user_id="user-001",
            provider_id="okta-prod",
        )

        assert result.success is True
        assert result.tokens_revoked == 1
        self.mock_dynamodb.delete_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_delegation_all_providers(self):
        """Test revoking delegation for all providers."""
        self.mock_dynamodb.query.return_value = [
            {"provider_id": "okta"},
            {"provider_id": "azure"},
        ]

        result = await self.service.revoke_delegation(
            agent_id="agent-001",
            user_id="user-001",
            provider_id=None,
        )

        assert result.tokens_revoked == 2
        assert self.mock_dynamodb.delete_item.call_count == 2


class TestOAuthDelegationServiceListDelegations:
    """Tests for listing delegations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_secrets = MagicMock()
        self.mock_dynamodb = MagicMock()
        self.mock_http = MagicMock()
        self.mock_encryption = MagicMock()

        self.service = OAuthDelegationService(
            secrets_client=self.mock_secrets,
            dynamodb_client=self.mock_dynamodb,
            http_client=self.mock_http,
            encryption_service=self.mock_encryption,
        )

    @pytest.mark.asyncio
    async def test_list_delegations_with_agent_and_user(self):
        """Test listing delegations with agent and user filter."""
        self.mock_dynamodb.query = AsyncMock(
            return_value=[
                {
                    "agent_id": "agent",
                    "user_id": "user",
                    "provider_id": "okta",
                    "scopes": ["read"],
                    "expires_at": "2025-12-31T00:00:00",
                    "created_at": "2025-01-01T00:00:00",
                }
            ]
        )

        result = await self.service.list_delegations(
            agent_id="agent",
            user_id="user",
        )

        assert len(result) == 1
        assert result[0]["provider_id"] == "okta"

    @pytest.mark.asyncio
    async def test_list_delegations_without_filters(self):
        """Test listing delegations without filters returns empty."""
        result = await self.service.list_delegations()

        assert result == []


class TestCodeChallengeGeneration:
    """Tests for PKCE code challenge generation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_secrets = MagicMock()
        self.mock_dynamodb = MagicMock()
        self.mock_http = MagicMock()
        self.mock_encryption = MagicMock()

        self.service = OAuthDelegationService(
            secrets_client=self.mock_secrets,
            dynamodb_client=self.mock_dynamodb,
            http_client=self.mock_http,
            encryption_service=self.mock_encryption,
        )

    def test_generate_code_challenge(self):
        """Test PKCE code challenge generation."""
        verifier = "test-code-verifier-for-pkce"
        challenge = self.service._generate_code_challenge(verifier)

        # Challenge should be base64url encoded SHA256 hash
        assert challenge is not None
        assert len(challenge) > 0
        # Should not contain padding characters
        assert "=" not in challenge

    def test_generate_code_challenge_deterministic(self):
        """Test code challenge is deterministic for same verifier."""
        verifier = "deterministic-verifier"
        challenge1 = self.service._generate_code_challenge(verifier)
        challenge2 = self.service._generate_code_challenge(verifier)

        assert challenge1 == challenge2

    def test_generate_code_challenge_different_verifiers(self):
        """Test different verifiers produce different challenges."""
        challenge1 = self.service._generate_code_challenge("verifier-1")
        challenge2 = self.service._generate_code_challenge("verifier-2")

        assert challenge1 != challenge2
