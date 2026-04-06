"""
Project Aura - OIDC Provider Tests

Tests for the OpenID Connect identity provider.
Focuses on configuration and basic functionality that can be tested without
making actual network calls.
"""

import base64
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.identity.base_provider import AuthenticationError, ConfigurationError
from src.services.identity.models import (
    AuthCredentials,
    ConnectionStatus,
    IdPType,
    TokenResult,
    TokenValidationResult,
)
from src.services.identity.providers.oidc_provider import OIDCProvider


class TestOIDCProviderConfiguration:
    """Tests for OIDC provider configuration."""

    def test_valid_configuration(self, oidc_config):
        """Test valid configuration creates provider."""
        provider = OIDCProvider(oidc_config)
        assert provider.issuer == "https://oidc.test.com"
        assert provider.client_id == "test-client-id"
        assert provider.use_pkce is True

    def test_missing_issuer(self, oidc_config):
        """Test error when issuer is missing."""
        oidc_config.connection_settings["issuer"] = None
        with pytest.raises(ConfigurationError) as exc_info:
            OIDCProvider(oidc_config)
        assert "issuer is required" in str(exc_info.value)

    def test_missing_client_id(self, oidc_config):
        """Test error when client_id is missing."""
        oidc_config.connection_settings["client_id"] = None
        with pytest.raises(ConfigurationError) as exc_info:
            OIDCProvider(oidc_config)
        assert "client_id is required" in str(exc_info.value)

    def test_wrong_idp_type(self, oidc_config):
        """Test error when IdP type is not OIDC."""
        oidc_config.idp_type = IdPType.LDAP
        with pytest.raises(ConfigurationError) as exc_info:
            OIDCProvider(oidc_config)
        assert "Invalid IdP type" in str(exc_info.value)

    def test_default_scopes(self, oidc_config):
        """Test default scopes are applied."""
        del oidc_config.connection_settings["scopes"]
        provider = OIDCProvider(oidc_config)
        assert "openid" in provider.scopes

    def test_pkce_default_enabled(self, oidc_config):
        """Test PKCE is enabled by default."""
        del oidc_config.connection_settings["use_pkce"]
        provider = OIDCProvider(oidc_config)
        assert provider.use_pkce is True

    def test_additional_connection_settings(self, oidc_config):
        """Test additional connection settings are stored."""
        oidc_config.connection_settings["custom_param"] = "value"
        provider = OIDCProvider(oidc_config)
        assert provider.config.connection_settings["custom_param"] == "value"


class TestOIDCProviderAuthRequest:
    """Tests for OIDC authorization request generation."""

    @pytest.fixture
    def provider(self, oidc_config):
        """Create OIDC provider with mocked discovery."""
        provider = OIDCProvider(oidc_config)
        # Manually set endpoints to avoid discovery (note: underscore prefix)
        provider._authorization_endpoint = "https://oidc.test.com/authorize"
        provider._token_endpoint = "https://oidc.test.com/token"
        provider._userinfo_endpoint = "https://oidc.test.com/userinfo"
        provider._jwks_uri = "https://oidc.test.com/.well-known/jwks.json"
        provider._discovery_loaded = True
        return provider

    def test_generate_auth_request_basic(self, provider):
        """Test generating authorization request URL."""
        # Note: generate_auth_request is synchronous
        request = provider.generate_auth_request()

        assert request.authorization_url is not None
        assert "client_id=test-client-id" in request.authorization_url
        assert request.state is not None
        assert request.nonce is not None

    def test_generate_auth_request_with_pkce(self, provider):
        """Test PKCE parameters are included."""
        request = provider.generate_auth_request()

        assert request.code_verifier is not None
        assert "code_challenge" in request.authorization_url
        assert "code_challenge_method=S256" in request.authorization_url

    def test_generate_auth_request_scopes(self, provider):
        """Test scopes are included."""
        request = provider.generate_auth_request()

        assert "scope=" in request.authorization_url
        assert "openid" in request.authorization_url

    def test_code_challenge_calculation(self, provider):
        """Test PKCE code challenge is correctly calculated."""
        request = provider.generate_auth_request()

        verifier = request.code_verifier
        expected_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )

        assert expected_challenge in request.authorization_url


class TestOIDCProviderAuthentication:
    """Tests for OIDC authentication (code exchange)."""

    @pytest.fixture
    def provider(self, oidc_config):
        """Create OIDC provider with mocked discovery."""
        provider = OIDCProvider(oidc_config)
        provider._authorization_endpoint = "https://oidc.test.com/authorize"
        provider._token_endpoint = "https://oidc.test.com/token"
        provider._userinfo_endpoint = "https://oidc.test.com/userinfo"
        provider._jwks_uri = "https://oidc.test.com/.well-known/jwks.json"
        provider._discovery_loaded = True
        return provider

    @pytest.mark.asyncio
    async def test_authenticate_missing_code(self, provider):
        """Test authentication fails without code."""
        credentials = AuthCredentials(state="some-state")

        with patch.object(provider, "_load_credentials", new_callable=AsyncMock):
            with patch.object(provider, "discover", new_callable=AsyncMock):
                result = await provider.authenticate(credentials)

        assert result.success is False
        # Error should indicate missing code
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_authenticate_success(self, provider, oidc_credentials):
        """Test successful OIDC authentication with mocked internal methods."""
        # Mock token result with id_token
        mock_token_result = TokenResult(
            access_token="access_token_123",
            token_type="Bearer",
            expires_in=3600,
            id_token="test.id.token",
        )

        # Mock validation result with claims
        mock_validation = TokenValidationResult(
            valid=True,
            claims={
                "sub": "user123",
                "email": "test@example.com",
                "name": "Test User",
                "groups": ["admin-group"],
            },
        )

        with patch.object(provider, "_load_credentials", new_callable=AsyncMock):
            with patch.object(provider, "discover", new_callable=AsyncMock):
                with patch.object(
                    provider, "_exchange_code", new_callable=AsyncMock
                ) as mock_exchange:
                    mock_exchange.return_value = mock_token_result

                    with patch.object(
                        provider, "_validate_id_token", new_callable=AsyncMock
                    ) as mock_validate:
                        mock_validate.return_value = mock_validation

                        result = await provider.authenticate(oidc_credentials)

        assert result.success is True
        assert result.email == "test@example.com"
        assert result.user_id == "user123"

    @pytest.mark.asyncio
    async def test_authenticate_token_exchange_failure(
        self, provider, oidc_credentials
    ):
        """Test authentication fails on token exchange error."""
        with patch.object(provider, "_load_credentials", new_callable=AsyncMock):
            with patch.object(provider, "discover", new_callable=AsyncMock):
                with patch.object(
                    provider, "_exchange_code", new_callable=AsyncMock
                ) as mock_exchange:
                    mock_exchange.side_effect = Exception("Token endpoint error")

                    result = await provider.authenticate(oidc_credentials)

        assert result.success is False


class TestOIDCProviderTokenValidation:
    """Tests for OIDC token validation."""

    @pytest.fixture
    def provider(self, oidc_config):
        """Create OIDC provider with mocked discovery."""
        provider = OIDCProvider(oidc_config)
        provider._authorization_endpoint = "https://oidc.test.com/authorize"
        provider._token_endpoint = "https://oidc.test.com/token"
        provider._userinfo_endpoint = "https://oidc.test.com/userinfo"
        provider._jwks_uri = "https://oidc.test.com/.well-known/jwks.json"
        provider._discovery_loaded = True
        return provider

    @pytest.mark.asyncio
    async def test_validate_token_with_valid_claims(self, provider):
        """Test validating a token with mocked JWKS and validation."""
        mock_claims = {
            "sub": "user123",
            "email": "user@example.com",
            "iss": "https://oidc.test.com",
            "aud": "test-client-id",
            "exp": int(time.time()) + 3600,
        }

        # Mock the _get_jwks method to avoid network calls
        with patch.object(provider, "_get_jwks", new_callable=AsyncMock) as mock_jwks:
            mock_jwks.return_value = {
                "keys": [{"kid": "test-key", "kty": "RSA", "n": "abc", "e": "AQAB"}]
            }

            # Mock jwt.get_unverified_header and jwt.decode
            with patch("src.services.identity.providers.oidc_provider.jwt") as mock_jwt:
                mock_jwt.get_unverified_header.return_value = {
                    "kid": "test-key",
                    "alg": "RS256",
                }
                mock_jwt.decode.return_value = mock_claims

                result = await provider.validate_token("valid.jwt.token")

        assert result.valid is True
        assert result.claims["sub"] == "user123"

    @pytest.mark.asyncio
    async def test_validate_token_failure(self, provider):
        """Test validating a token that fails validation."""
        from jwt.exceptions import PyJWTError

        with patch.object(provider, "_get_jwks", new_callable=AsyncMock) as mock_jwks:
            mock_jwks.return_value = {
                "keys": [{"kid": "test-key", "kty": "RSA", "n": "abc", "e": "AQAB"}]
            }

            with patch("src.services.identity.providers.oidc_provider.jwt") as mock_jwt:
                mock_jwt.get_unverified_header.return_value = {"kid": "test-key"}
                mock_jwt.decode.side_effect = PyJWTError("Token has expired")

                result = await provider.validate_token("expired.jwt.token")

        assert result.valid is False
        assert result.error is not None


class TestOIDCProviderHealthCheck:
    """Tests for OIDC health check."""

    @pytest.fixture
    def provider(self, oidc_config):
        """Create OIDC provider."""
        return OIDCProvider(oidc_config)

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        """Test successful health check by mocking discover method."""
        with patch.object(
            provider, "discover", new_callable=AsyncMock
        ) as mock_discover:
            mock_discover.return_value = None
            # Set endpoints that health check will include in details
            provider._authorization_endpoint = "https://oidc.test.com/authorize"
            provider._token_endpoint = "https://oidc.test.com/token"
            provider._userinfo_endpoint = "https://oidc.test.com/userinfo"

            result = await provider.health_check()

        # Should attempt discovery
        mock_discover.assert_called_once()
        assert result.healthy is True

    @pytest.mark.asyncio
    async def test_health_check_discovery_failure(self, provider):
        """Test health check on discovery failure."""
        with patch.object(
            provider, "discover", new_callable=AsyncMock
        ) as mock_discover:
            mock_discover.side_effect = Exception("Connection refused")

            result = await provider.health_check()

        assert result.healthy is False
        assert result.status == ConnectionStatus.ERROR


class TestOIDCProviderTokenRefresh:
    """Tests for OIDC token refresh."""

    @pytest.fixture
    def provider(self, oidc_config):
        """Create OIDC provider with mocked discovery."""
        provider = OIDCProvider(oidc_config)
        provider._authorization_endpoint = "https://oidc.test.com/authorize"
        provider._token_endpoint = "https://oidc.test.com/token"
        provider._userinfo_endpoint = "https://oidc.test.com/userinfo"
        provider._jwks_uri = "https://oidc.test.com/.well-known/jwks.json"
        provider._discovery_loaded = True
        return provider

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, provider):
        """Test successful token refresh."""
        mock_response = {
            "access_token": "new_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "new_refresh_token",
        }

        provider._client_secret = "test-secret"

        mock_response_obj = MagicMock()
        mock_response_obj.status = 200
        mock_response_obj.json = AsyncMock(return_value=mock_response)

        mock_session = MagicMock()
        mock_session.post = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_response_obj),
                __aexit__=AsyncMock(),
            )
        )
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch.object(provider, "_load_credentials", new_callable=AsyncMock):
            with patch.object(provider, "discover", new_callable=AsyncMock):
                # Patch aiohttp in the module where it's imported
                with patch(
                    "src.services.identity.providers.oidc_provider.aiohttp.ClientSession",
                    return_value=mock_session,
                ):
                    result = await provider.refresh_token("old_refresh_token")

        assert result.access_token == "new_access_token"


class TestOIDCProviderLogout:
    """Tests for OIDC logout."""

    @pytest.fixture
    def provider(self, oidc_config):
        """Create OIDC provider with mocked discovery."""
        provider = OIDCProvider(oidc_config)
        provider._discovery_loaded = True
        return provider

    @pytest.mark.asyncio
    async def test_logout_success(self, provider):
        """Test logout always succeeds for OIDC."""
        with patch.object(provider, "discover", new_callable=AsyncMock):
            result = await provider.logout("access_token")
        # OIDC logout is typically client-side
        assert result is True


class TestOIDCProviderUserInfo:
    """Tests for OIDC userinfo endpoint."""

    @pytest.fixture
    def provider(self, oidc_config):
        """Create OIDC provider with mocked discovery."""
        provider = OIDCProvider(oidc_config)
        provider._authorization_endpoint = "https://oidc.test.com/authorize"
        provider._token_endpoint = "https://oidc.test.com/token"
        provider._userinfo_endpoint = "https://oidc.test.com/userinfo"
        provider._jwks_uri = "https://oidc.test.com/.well-known/jwks.json"
        provider._discovery_loaded = True
        return provider

    @pytest.mark.asyncio
    async def test_get_user_info_success(self, provider):
        """Test getting user info with mocked response."""
        mock_userinfo = {
            "sub": "user123",
            "email": "user@example.com",
            "name": "Test User",
            "preferred_username": "testuser",
        }

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_userinfo)

        mock_session = MagicMock()
        mock_session.get = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(),
            )
        )
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch.object(provider, "discover", new_callable=AsyncMock):
            # Patch aiohttp in the module where it's imported
            with patch(
                "src.services.identity.providers.oidc_provider.aiohttp.ClientSession",
                return_value=mock_session,
            ):
                result = await provider.get_user_info("access_token")

        assert result.user_id == "user123"
        assert result.email == "user@example.com"

    @pytest.mark.asyncio
    async def test_get_user_info_unauthorized(self, provider):
        """Test error on unauthorized userinfo request."""
        mock_response = MagicMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")

        # Create mock context manager for the get() call
        mock_get_ctx = MagicMock()
        mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get = MagicMock(return_value=mock_get_ctx)

        # Create mock context manager for ClientSession()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch.object(provider, "discover", new_callable=AsyncMock):
            # Patch aiohttp in the module where it's imported
            with patch(
                "src.services.identity.providers.oidc_provider.aiohttp.ClientSession",
                return_value=mock_session_ctx,
            ):
                with pytest.raises(AuthenticationError):
                    await provider.get_user_info("invalid_token")
