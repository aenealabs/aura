"""
Project Aura - Token Service Tests

Tests for the token normalization service that issues unified Aura JWTs.

Note: These tests use pytest.mark.forked to run in isolated processes,
avoiding cryptography backend conflicts with cryptography>=42.0.0.
"""

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest

from src.services.identity.models import AuthResult, IdentityProviderConfig, IdPType
from src.services.identity.token_service import (
    TokenNormalizationService,
    get_token_service,
)

# Mark entire module to run tests in forked processes to avoid
# cryptography backend pollution from other tests
pytestmark = pytest.mark.forked


class TestTokenNormalizationService:
    """Tests for TokenNormalizationService."""

    @pytest.fixture
    def token_service(self):
        """Create a token service for testing (no Secrets Manager)."""
        return TokenNormalizationService(
            signing_key_secret_arn=None,  # Use dev mode
            issuer="https://test.aenealabs.com",
            access_token_ttl=3600,
            refresh_token_ttl=86400,
        )

    @pytest.fixture
    def auth_result(self):
        """Create a test auth result."""
        return AuthResult(
            success=True,
            user_id="user-ldap-123",
            email="john.doe@example.com",
            name="John Doe",
            groups=["Admins", "Developers"],
            roles=["admin", "developer"],
        )

    @pytest.fixture
    def idp_config(self):
        """Create a test IdP config."""
        return IdentityProviderConfig(
            idp_id="idp-ldap-456",
            organization_id="org-789",
            idp_type=IdPType.LDAP,
            name="Corporate LDAP",
        )

    @pytest.mark.asyncio
    async def test_issue_tokens_basic(self, token_service, auth_result, idp_config):
        """Test basic token issuance."""
        tokens, session = await token_service.issue_tokens(
            auth_result=auth_result,
            idp_config=idp_config,
        )

        assert tokens.access_token is not None
        assert tokens.refresh_token is not None
        assert tokens.token_type == "Bearer"
        assert tokens.expires_in == 3600

        assert session.idp_id == "idp-ldap-456"
        assert session.organization_id == "org-789"
        assert session.email == "john.doe@example.com"
        assert "admin" in session.roles

    @pytest.mark.asyncio
    async def test_issue_tokens_with_client_info(
        self, token_service, auth_result, idp_config
    ):
        """Test token issuance with client metadata."""
        tokens, session = await token_service.issue_tokens(
            auth_result=auth_result,
            idp_config=idp_config,
            client_ip="192.168.1.100",
            user_agent="Mozilla/5.0",
        )

        assert session.ip_address == "192.168.1.100"
        assert session.user_agent == "Mozilla/5.0"

    @pytest.mark.asyncio
    async def test_access_token_claims(self, token_service, auth_result, idp_config):
        """Test access token contains expected claims."""
        tokens, _ = await token_service.issue_tokens(
            auth_result=auth_result,
            idp_config=idp_config,
        )

        # Decode without verification for inspection
        claims = token_service.decode_token_unverified(tokens.access_token)

        assert claims["email"] == "john.doe@example.com"
        assert claims["name"] == "John Doe"
        assert "admin" in claims["roles"]
        assert claims["org_id"] == "org-789"
        assert claims["idp"] == "idp-ldap-456"
        assert claims["idp_type"] == "ldap"
        assert claims["iss"] == "https://test.aenealabs.com"
        assert claims["aud"] == "aura-api"
        assert claims["token_type"] == "access"
        assert "sub" in claims
        assert "session_id" in claims
        assert "exp" in claims
        assert "iat" in claims

    @pytest.mark.asyncio
    async def test_refresh_token_claims(self, token_service, auth_result, idp_config):
        """Test refresh token has minimal claims."""
        tokens, _ = await token_service.issue_tokens(
            auth_result=auth_result,
            idp_config=idp_config,
        )

        claims = token_service.decode_token_unverified(tokens.refresh_token)

        assert claims["token_type"] == "refresh"
        assert claims["org_id"] == "org-789"
        assert claims["idp"] == "idp-ldap-456"
        assert "jti" in claims  # Unique token ID for rotation
        # Refresh tokens should NOT have email, name, roles
        assert "email" not in claims
        assert "name" not in claims
        assert "roles" not in claims

    @pytest.mark.asyncio
    async def test_subject_generation_consistent(
        self, token_service, auth_result, idp_config
    ):
        """Test subject is consistent for same IdP+user."""
        tokens1, session1 = await token_service.issue_tokens(
            auth_result=auth_result,
            idp_config=idp_config,
        )
        tokens2, session2 = await token_service.issue_tokens(
            auth_result=auth_result,
            idp_config=idp_config,
        )

        # Same IdP + user should produce same subject
        claims1 = token_service.decode_token_unverified(tokens1.access_token)
        claims2 = token_service.decode_token_unverified(tokens2.access_token)
        assert claims1["sub"] == claims2["sub"]

    @pytest.mark.asyncio
    async def test_subject_generation_unique_per_idp(self, token_service, auth_result):
        """Test different IdPs generate different subjects."""
        config1 = IdentityProviderConfig(
            idp_id="idp-1",
            organization_id="org-1",
            idp_type=IdPType.LDAP,
            name="LDAP 1",
        )
        config2 = IdentityProviderConfig(
            idp_id="idp-2",
            organization_id="org-1",
            idp_type=IdPType.LDAP,
            name="LDAP 2",
        )

        tokens1, _ = await token_service.issue_tokens(auth_result, config1)
        tokens2, _ = await token_service.issue_tokens(auth_result, config2)

        claims1 = token_service.decode_token_unverified(tokens1.access_token)
        claims2 = token_service.decode_token_unverified(tokens2.access_token)
        assert claims1["sub"] != claims2["sub"]

    @pytest.mark.asyncio
    async def test_validate_token_valid(self, token_service, auth_result, idp_config):
        """Test validating a valid token."""
        tokens, _ = await token_service.issue_tokens(auth_result, idp_config)

        result = await token_service.validate_token(tokens.access_token)

        assert result.valid is True
        assert result.error is None
        assert result.claims["email"] == "john.doe@example.com"
        assert result.expires_at is not None

    @pytest.mark.asyncio
    async def test_validate_token_expired(self, token_service, auth_result, idp_config):
        """Test validating an expired token."""
        # Create service with very short TTL
        short_ttl_service = TokenNormalizationService(
            signing_key_secret_arn=None,
            issuer="https://test.aenealabs.com",
            access_token_ttl=1,  # 1 second
            refresh_token_ttl=1,
        )

        tokens, _ = await short_ttl_service.issue_tokens(auth_result, idp_config)

        # Wait for token to expire
        time.sleep(2)

        result = await short_ttl_service.validate_token(tokens.access_token)
        assert result.valid is False
        assert "expired" in result.error.lower()

    @pytest.mark.asyncio
    async def test_validate_token_invalid_signature(self, token_service):
        """Test validating a token with invalid signature."""
        # Create a token with a different key
        other_service = TokenNormalizationService(
            signing_key_secret_arn=None,
            issuer="https://test.aenealabs.com",
        )

        # Manually create a token with different key
        await other_service._load_signing_key()
        fake_token = jwt.encode(
            {
                "sub": "fake",
                "iss": "https://test.aenealabs.com",
                "exp": int(time.time()) + 3600,
            },
            other_service._signing_key,
            algorithm="HS256",
        )

        # Load our service's key
        await token_service._load_signing_key()

        result = await token_service.validate_token(fake_token)
        assert result.valid is False

    @pytest.mark.asyncio
    async def test_validate_token_wrong_issuer(self, token_service):
        """Test validating a token with wrong issuer."""
        await token_service._load_signing_key()

        # Create token with wrong issuer
        fake_token = jwt.encode(
            {
                "sub": "user",
                "iss": "https://wrong.issuer.com",
                "exp": int(time.time()) + 3600,
            },
            token_service._signing_key,
            algorithm="HS256",
        )

        result = await token_service.validate_token(fake_token)
        assert result.valid is False
        assert "claims" in result.error.lower() or result.error is not None

    @pytest.mark.asyncio
    async def test_refresh_tokens(self, token_service, auth_result, idp_config):
        """Test token refresh with rotation."""
        # Issue initial tokens
        initial_tokens, session = await token_service.issue_tokens(
            auth_result, idp_config
        )
        initial_jti = session.refresh_token_jti

        # Refresh tokens
        new_tokens, updated_session = await token_service.refresh_tokens(
            refresh_token=initial_tokens.refresh_token,
            session=session,
            idp_config=idp_config,
        )

        assert new_tokens.access_token != initial_tokens.access_token
        assert new_tokens.refresh_token != initial_tokens.refresh_token
        assert updated_session.refresh_token_jti != initial_jti  # Rotation

    @pytest.mark.asyncio
    async def test_refresh_tokens_jti_mismatch(
        self, token_service, auth_result, idp_config
    ):
        """Test refresh fails when JTI doesn't match session."""
        tokens, session = await token_service.issue_tokens(auth_result, idp_config)

        # Tamper with session JTI
        session.refresh_token_jti = "wrong-jti"

        with pytest.raises(ValueError) as exc_info:
            await token_service.refresh_tokens(
                tokens.refresh_token, session, idp_config
            )
        assert "JTI mismatch" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_refresh_tokens_invalid_refresh_token(
        self, token_service, auth_result, idp_config
    ):
        """Test refresh fails with invalid refresh token."""
        _, session = await token_service.issue_tokens(auth_result, idp_config)

        with pytest.raises(ValueError) as exc_info:
            await token_service.refresh_tokens(
                "invalid.token.here", session, idp_config
            )
        assert "Invalid refresh token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_decode_token_unverified(
        self, token_service, auth_result, idp_config
    ):
        """Test decoding token without verification."""
        tokens, _ = await token_service.issue_tokens(auth_result, idp_config)

        claims = token_service.decode_token_unverified(tokens.access_token)
        assert "sub" in claims
        assert "email" in claims

    @pytest.mark.asyncio
    async def test_get_token_header(self, token_service, auth_result, idp_config):
        """Test getting token header."""
        tokens, _ = await token_service.issue_tokens(auth_result, idp_config)

        header = token_service.get_token_header(tokens.access_token)
        assert header["alg"] == "HS256"  # Dev mode uses symmetric key
        assert header["typ"] == "JWT"

    def test_generate_subject_deterministic(self, token_service):
        """Test subject generation is deterministic."""
        sub1 = token_service._generate_subject("idp-123", "user-456")
        sub2 = token_service._generate_subject("idp-123", "user-456")
        assert sub1 == sub2

    def test_generate_subject_unique(self, token_service):
        """Test different inputs produce different subjects."""
        sub1 = token_service._generate_subject("idp-1", "user-1")
        sub2 = token_service._generate_subject("idp-1", "user-2")
        sub3 = token_service._generate_subject("idp-2", "user-1")

        assert sub1 != sub2
        assert sub1 != sub3
        assert sub2 != sub3


class TestTokenServiceWithSecretsManager:
    """Tests for token service with Secrets Manager integration."""

    @pytest.mark.asyncio
    async def test_load_signing_key_from_secrets_manager(self):
        """Test loading key from Secrets Manager."""
        service = TokenNormalizationService(
            signing_key_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:jwt-key",
            issuer="https://test.aenealabs.com",
        )

        mock_response = {
            "SecretString": '{"private_key": "test-private-key", "public_key": "test-public-key"}'
        }

        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_client.get_secret_value.return_value = mock_response
            mock_boto.return_value = mock_client

            await service._load_signing_key()

            assert service._signing_key == "test-private-key"
            assert service._public_key == "test-public-key"
            assert service._key_loaded is True

    @pytest.mark.asyncio
    async def test_load_signing_key_caches_result(self):
        """Test that signing key is only loaded once."""
        service = TokenNormalizationService(
            signing_key_secret_arn=None,
            issuer="https://test.aenealabs.com",
        )

        await service._load_signing_key()
        first_key = service._signing_key

        await service._load_signing_key()
        second_key = service._signing_key

        # Should be same key (not regenerated)
        assert first_key == second_key

    @pytest.mark.asyncio
    async def test_load_signing_key_error(self):
        """Test error handling when Secrets Manager fails."""
        service = TokenNormalizationService(
            signing_key_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:jwt-key",
            issuer="https://test.aenealabs.com",
        )

        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_client.get_secret_value.side_effect = Exception("Access denied")
            mock_boto.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await service._load_signing_key()
            assert "Access denied" in str(exc_info.value)


class TestGetTokenServiceSingleton:
    """Tests for the token service singleton."""

    def test_get_token_service_creates_instance(self):
        """Test singleton creation."""
        # Reset the global
        import src.services.identity.token_service as ts_module

        ts_module._token_service = None

        with patch.dict(
            "os.environ",
            {
                "JWT_SIGNING_KEY_ARN": "",
                "JWT_ISSUER": "https://test.example.com",
            },
        ):
            service = get_token_service()
            assert service is not None
            assert service.issuer == "https://test.example.com"

    def test_get_token_service_returns_same_instance(self):
        """Test singleton returns same instance."""
        import src.services.identity.token_service as ts_module

        ts_module._token_service = None

        service1 = get_token_service()
        service2 = get_token_service()
        assert service1 is service2


class TestTokenExpiration:
    """Tests for token expiration handling."""

    @pytest.fixture
    def auth_result(self):
        return AuthResult(
            success=True,
            user_id="user-123",
            email="user@example.com",
        )

    @pytest.fixture
    def idp_config(self):
        return IdentityProviderConfig(
            idp_id="idp-123",
            organization_id="org-456",
            idp_type=IdPType.OIDC,
            name="OIDC",
        )

    @pytest.mark.asyncio
    async def test_access_token_expiration_set_correctly(self, auth_result, idp_config):
        """Test access token expiration is set correctly."""
        ttl = 7200  # 2 hours
        service = TokenNormalizationService(
            signing_key_secret_arn=None,
            issuer="https://test.aenealabs.com",
            access_token_ttl=ttl,
        )

        before = int(time.time())
        tokens, _ = await service.issue_tokens(auth_result, idp_config)
        after = int(time.time())

        claims = service.decode_token_unverified(tokens.access_token)
        exp = claims["exp"]
        iat = claims["iat"]

        # Expiration should be iat + ttl (within test execution time)
        assert exp - iat == ttl
        assert before <= iat <= after + 1

    @pytest.mark.asyncio
    async def test_refresh_token_expiration_set_correctly(
        self, auth_result, idp_config
    ):
        """Test refresh token expiration is set correctly."""
        refresh_ttl = 604800  # 7 days
        service = TokenNormalizationService(
            signing_key_secret_arn=None,
            issuer="https://test.aenealabs.com",
            refresh_token_ttl=refresh_ttl,
        )

        tokens, _ = await service.issue_tokens(auth_result, idp_config)
        claims = service.decode_token_unverified(tokens.refresh_token)

        exp = claims["exp"]
        iat = claims["iat"]
        assert exp - iat == refresh_ttl
