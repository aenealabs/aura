"""
Tests for API Authentication Module.

Test Type: UNIT
Dependencies: All external calls mocked (Cognito, SSM, httpx)
Isolation: Cache clearing fixture (clears lru_cache between tests)
Run Command: pytest tests/test_api_auth.py -v

Tests for Cognito JWT authentication middleware.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.security import HTTPAuthorizationCredentials


@contextmanager
def assert_http_exception(expected_status: int, detail_contains: str | None = None):
    """
    Context manager to assert HTTPException is raised with expected status.

    This avoids class identity issues with pytest.raises(HTTPException) that occur
    when the exception class is imported differently across module boundaries.
    """
    try:
        yield
        pytest.fail(
            f"Expected HTTPException with status {expected_status} but no exception was raised"
        )
    except Exception as e:
        # Check it's an HTTPException by duck typing (has status_code attribute)
        if not hasattr(e, "status_code"):
            pytest.fail(f"Expected HTTPException but got {type(e).__name__}: {e}")
        if e.status_code != expected_status:
            pytest.fail(f"Expected status {expected_status} but got {e.status_code}")
        if detail_contains and hasattr(e, "detail"):
            if detail_contains.lower() not in str(e.detail).lower():
                pytest.fail(
                    f"Expected detail containing '{detail_contains}' but got '{e.detail}'"
                )


@pytest.fixture(autouse=True)
def clear_auth_state():
    """Clear authentication caches before and after each test."""
    from src.api.auth import clear_auth_caches

    clear_auth_caches()
    yield
    clear_auth_caches()


# ==================== CognitoConfig Tests ====================


class TestCognitoConfig:
    """Tests for CognitoConfig model."""

    def test_initialization(self):
        """Test basic initialization."""
        from src.api.auth import CognitoConfig

        config = CognitoConfig(
            region="us-east-1", user_pool_id="us-east-1_abc123", client_id="client123"
        )
        assert config.region == "us-east-1"
        assert config.user_pool_id == "us-east-1_abc123"
        assert config.client_id == "client123"

    def test_issuer_property(self):
        """Test issuer URL generation."""
        from src.api.auth import CognitoConfig

        config = CognitoConfig(
            region="us-west-2", user_pool_id="us-west-2_xyz789", client_id="myclient"
        )
        expected = "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_xyz789"
        assert config.issuer == expected

    def test_jwks_url_property(self):
        """Test JWKS URL generation."""
        from src.api.auth import CognitoConfig

        config = CognitoConfig(
            region="eu-west-1", user_pool_id="eu-west-1_pool", client_id="euClient"
        )
        expected = "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_pool/.well-known/jwks.json"
        assert config.jwks_url == expected


# ==================== User Tests ====================


class TestUser:
    """Tests for User model."""

    def test_initialization(self):
        """Test basic user initialization."""
        from src.api.auth import User

        user = User(sub="user-123")
        assert user.sub == "user-123"
        assert user.email is None
        assert user.name is None
        assert user.groups == []

    def test_with_all_fields(self):
        """Test user with all fields populated."""
        from src.api.auth import User

        user = User(
            sub="user-456",
            email="test@example.com",
            name="Test User",
            groups=["admin", "developer"],
        )
        assert user.sub == "user-456"
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.groups == ["admin", "developer"]

    def test_roles_property(self):
        """Test roles property returns groups."""
        from src.api.auth import User

        user = User(sub="user-789", groups=["admin", "security-engineer"])
        assert user.roles == ["admin", "security-engineer"]


# ==================== Configuration Tests ====================


class TestFetchSSMParameter:
    """Tests for _fetch_ssm_parameter function."""

    def test_successful_fetch(self):
        """Test successful SSM parameter fetch."""
        from src.api.auth import _fetch_ssm_parameter

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-value"}}

        result = _fetch_ssm_parameter(mock_ssm, "/test/param")
        assert result == "test-value"
        mock_ssm.get_parameter.assert_called_once_with(Name="/test/param")

    def test_fetch_failure(self):
        """Test SSM parameter fetch failure returns None."""
        from botocore.exceptions import ClientError

        from src.api.auth import _fetch_ssm_parameter

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
            "GetParameter",
        )

        result = _fetch_ssm_parameter(mock_ssm, "/missing/param")
        assert result is None


class TestGetCognitoConfig:
    """Tests for get_cognito_config function."""

    def test_from_environment_variables(self):
        """Test loading config from environment variables."""
        from src.api.auth import clear_auth_caches, get_cognito_config

        # Clear cache first
        clear_auth_caches()

        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-2",
                "COGNITO_USER_POOL_ID": "us-east-2_testpool",
                "COGNITO_CLIENT_ID": "testclient123",
            },
        ):
            config = get_cognito_config()
            assert config.region == "us-east-2"
            assert config.user_pool_id == "us-east-2_testpool"
            assert config.client_id == "testclient123"

        # Clean up cache
        clear_auth_caches()

    def test_missing_config_raises_error(self):
        """Test that missing config raises RuntimeError."""
        from src.api.auth import clear_auth_caches, get_cognito_config

        clear_auth_caches()

        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "COGNITO_USER_POOL_ID": "",
                "COGNITO_CLIENT_ID": "",
            },
            clear=True,
        ):
            with patch("src.api.auth._boto3_available", False):
                with pytest.raises(RuntimeError) as exc_info:
                    get_cognito_config()
                assert "Cognito configuration not found" in str(exc_info.value)

        clear_auth_caches()


# ==================== JWKS Tests ====================


class TestGetJWKS:
    """Tests for get_jwks function."""

    def test_successful_fetch(self):
        """Test successful JWKS fetch."""
        import src.api.auth as auth_module

        auth_module.clear_auth_caches()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keys": [{"kid": "key1", "alg": "RS256"}, {"kid": "key2", "alg": "RS256"}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "COGNITO_USER_POOL_ID": "pool123",
                "COGNITO_CLIENT_ID": "client123",
            },
        ):
            # Patch the HTTP client getter to return a mock client
            with patch.object(auth_module, "get_http_client", return_value=mock_client):
                jwks = auth_module.get_jwks()
                assert "keys" in jwks
                assert len(jwks["keys"]) == 2

        auth_module.clear_auth_caches()

    def test_fetch_failure_raises_http_error(self):
        """Test JWKS fetch failure raises HTTPException with 503."""
        import httpx

        import src.api.auth as auth_module

        auth_module.clear_auth_caches()

        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.HTTPError("Network error")

        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "COGNITO_USER_POOL_ID": "pool123",
                "COGNITO_CLIENT_ID": "client123",
            },
        ):
            # Patch the HTTP client getter to return a mock client that raises
            with patch.object(auth_module, "get_http_client", return_value=mock_client):
                with assert_http_exception(503):
                    auth_module.get_jwks()


# ==================== Token Verification Tests ====================


class TestGetPublicKey:
    """Tests for get_public_key function."""

    def test_invalid_token_format(self):
        """Test invalid token format raises 401 error."""
        import src.api.auth as auth_module

        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "COGNITO_USER_POOL_ID": "pool123",
                "COGNITO_CLIENT_ID": "client123",
            },
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {"keys": []}
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response

            # Patch the HTTP client getter to return a mock client
            with patch.object(auth_module, "get_http_client", return_value=mock_client):
                with assert_http_exception(401):
                    auth_module.get_public_key("invalid-token")


class TestVerifyToken:
    """Tests for verify_token function."""

    def test_expired_token(self):
        """Test that expired token raises 401 with 'expired' in detail."""
        import jwt as pyjwt

        import src.api.auth as auth_module

        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "COGNITO_USER_POOL_ID": "pool123",
                "COGNITO_CLIENT_ID": "client123",
            },
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "keys": [{"kid": "testkey", "alg": "RS256"}]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response

            # Patch the HTTP client and jwt on auth's imported modules
            # First decode (unverified) returns token_use,
            # second decode (verified) raises ExpiredSignatureError
            mock_pyJWK = MagicMock()
            with patch.object(auth_module, "get_http_client", return_value=mock_client):
                with patch.object(
                    auth_module.jwt,
                    "get_unverified_header",
                    return_value={"kid": "testkey"},
                ):
                    with patch.object(auth_module.jwt, "PyJWK", mock_pyJWK):
                        with patch.object(
                            auth_module.jwt,
                            "decode",
                            side_effect=[
                                {"token_use": "access"},
                                pyjwt.ExpiredSignatureError("Token expired"),
                            ],
                        ):
                            with assert_http_exception(401, "expired"):
                                auth_module.verify_token("expired.token.here")

    def test_invalid_token_use_rejected(self):
        """Test that tokens with invalid token_use are rejected."""
        import src.api.auth as auth_module

        auth_module.clear_auth_caches()

        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "COGNITO_USER_POOL_ID": "pool123",
                "COGNITO_CLIENT_ID": "client123",
            },
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "keys": [{"kid": "testkey", "alg": "RS256"}]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response

            with patch.object(auth_module, "get_http_client", return_value=mock_client):
                with patch.object(
                    auth_module.jwt,
                    "get_unverified_header",
                    return_value={"kid": "testkey"},
                ):
                    # First decode call (unverified) returns invalid token_use
                    with patch.object(
                        auth_module.jwt,
                        "decode",
                        return_value={"token_use": "refresh"},  # Invalid!
                    ):
                        with assert_http_exception(401, "Invalid token type"):
                            auth_module.verify_token("refresh.token.here")

        auth_module.clear_auth_caches()

    def test_access_token_wrong_client_id_rejected(self):
        """Test that access tokens with wrong client_id are rejected."""
        import src.api.auth as auth_module

        auth_module.clear_auth_caches()

        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "COGNITO_USER_POOL_ID": "pool123",
                "COGNITO_CLIENT_ID": "our-client-id",
            },
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "keys": [{"kid": "testkey", "alg": "RS256"}]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response

            with patch.object(auth_module, "get_http_client", return_value=mock_client):
                with patch.object(
                    auth_module.jwt,
                    "get_unverified_header",
                    return_value={"kid": "testkey"},
                ):
                    # First decode (unverified) returns token_use,
                    # second decode (verified) returns payload with wrong client_id
                    with patch.object(
                        auth_module.jwt,
                        "decode",
                        side_effect=[
                            {"token_use": "access"},
                            {
                                "sub": "user-123",
                                "token_use": "access",
                                "client_id": "wrong-client-id",  # Different client!
                            },
                        ],
                    ):
                        with assert_http_exception(401, "Invalid token audience"):
                            auth_module.verify_token("access.token.here")

        auth_module.clear_auth_caches()

    def test_valid_access_token_passes_client_id_check(self):
        """Test that valid access tokens pass client_id validation."""
        import src.api.auth as auth_module

        auth_module.clear_auth_caches()

        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "COGNITO_USER_POOL_ID": "pool123",
                "COGNITO_CLIENT_ID": "our-client-id",
            },
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "keys": [{"kid": "testkey", "alg": "RS256"}]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response

            with patch.object(auth_module, "get_http_client", return_value=mock_client):
                with patch.object(
                    auth_module.jwt,
                    "get_unverified_header",
                    return_value={"kid": "testkey"},
                ):
                    # Valid access token with correct client_id
                    expected_payload = {
                        "sub": "user-123",
                        "token_use": "access",
                        "client_id": "our-client-id",  # Correct!
                        "cognito:groups": ["admin"],
                    }
                    # First decode (unverified) returns token_use,
                    # second decode (verified) returns full payload
                    with patch.object(
                        auth_module.jwt,
                        "decode",
                        side_effect=[
                            {"token_use": "access"},
                            expected_payload,
                        ],
                    ):
                        result = auth_module.verify_token("valid.access.token")
                        assert result["sub"] == "user-123"
                        assert result["client_id"] == "our-client-id"

        auth_module.clear_auth_caches()

    def test_id_token_uses_audience_validation(self):
        """Test that ID tokens are validated with audience parameter."""
        import src.api.auth as auth_module

        auth_module.clear_auth_caches()

        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "COGNITO_USER_POOL_ID": "pool123",
                "COGNITO_CLIENT_ID": "our-client-id",
            },
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "keys": [{"kid": "testkey", "alg": "RS256"}]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response

            with patch.object(auth_module, "get_http_client", return_value=mock_client):
                with patch.object(
                    auth_module.jwt,
                    "get_unverified_header",
                    return_value={"kid": "testkey"},
                ):
                    expected_payload = {
                        "sub": "user-456",
                        "token_use": "id",
                        "aud": "our-client-id",
                        "email": "test@example.com",
                    }

                    # First decode (unverified) returns token_use,
                    # second decode (verified) returns full payload
                    mock_decode = MagicMock(
                        side_effect=[{"token_use": "id"}, expected_payload]
                    )
                    with patch.object(auth_module.jwt, "decode", mock_decode):
                        result = auth_module.verify_token("valid.id.token")

                        # Verify second decode call was made with audience for ID tokens
                        call_kwargs = mock_decode.call_args_list[1][1]
                        assert call_kwargs["audience"] == "our-client-id"
                        assert call_kwargs["options"]["verify_aud"] is True
                        assert result["email"] == "test@example.com"

        auth_module.clear_auth_caches()

    def test_access_token_skips_audience_validation(self):
        """Test that access tokens skip audience validation in jwt.decode."""
        import src.api.auth as auth_module

        auth_module.clear_auth_caches()

        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "COGNITO_USER_POOL_ID": "pool123",
                "COGNITO_CLIENT_ID": "our-client-id",
            },
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "keys": [{"kid": "testkey", "alg": "RS256"}]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.get.return_value = mock_response

            with patch.object(auth_module, "get_http_client", return_value=mock_client):
                with patch.object(
                    auth_module.jwt,
                    "get_unverified_header",
                    return_value={"kid": "testkey"},
                ):
                    expected_payload = {
                        "sub": "user-789",
                        "token_use": "access",
                        "client_id": "our-client-id",
                    }

                    # First decode (unverified) returns token_use,
                    # second decode (verified) returns full payload
                    mock_decode = MagicMock(
                        side_effect=[{"token_use": "access"}, expected_payload]
                    )
                    with patch.object(auth_module.jwt, "decode", mock_decode):
                        auth_module.verify_token("valid.access.token")

                        # Verify second decode call was made without audience for access tokens
                        call_kwargs = mock_decode.call_args_list[1][1]
                        assert call_kwargs["audience"] is None
                        assert call_kwargs["options"]["verify_aud"] is False

        auth_module.clear_auth_caches()


# ==================== User Extraction Tests ====================


class TestGetCurrentUser:
    """Tests for get_current_user function."""

    @pytest.mark.asyncio
    async def test_no_credentials(self):
        """Test that missing credentials raises 401."""
        from src.api.auth import get_current_user

        with assert_http_exception(401, "Authentication required"):
            await get_current_user(None)

    @pytest.mark.asyncio
    async def test_valid_token(self):
        """Test successful user extraction from valid token."""
        from src.api.auth import clear_auth_caches, get_current_user

        clear_auth_caches()

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid.token.here"
        )

        mock_payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "name": "Test User",
            "cognito:groups": ["admin"],
            "token_use": "access",
        }

        with patch("src.api.auth.verify_token", return_value=mock_payload):
            user = await get_current_user(credentials)
            assert user.sub == "user-123"
            assert user.email == "test@example.com"
            assert user.name == "Test User"
            assert "admin" in user.groups

        clear_auth_caches()


class TestGetOptionalUser:
    """Tests for get_optional_user function."""

    @pytest.mark.asyncio
    async def test_no_credentials_returns_none(self):
        """Test that missing credentials returns None."""
        from src.api.auth import get_optional_user

        result = await get_optional_user(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        """Test valid token returns user."""
        from src.api.auth import clear_auth_caches, get_optional_user

        clear_auth_caches()

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid.token.here"
        )

        mock_payload = {
            "sub": "user-456",
            "email": "optional@example.com",
            "cognito:username": "optuser",
            "cognito:groups": ["developer"],
            "token_use": "id",
        }

        with patch("src.api.auth.verify_token", return_value=mock_payload):
            user = await get_optional_user(credentials)
            assert user is not None
            assert user.sub == "user-456"
            assert user.email == "optional@example.com"

        clear_auth_caches()

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(self):
        """Test invalid token returns None instead of raising."""
        import src.api.auth as auth_module

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid.token"
        )

        # Patch verify_token on auth module and use auth's HTTPException
        # to ensure exception class identity is preserved for the except clause
        with patch.object(
            auth_module,
            "verify_token",
            side_effect=auth_module.HTTPException(status_code=401, detail="Invalid"),
        ):
            result = await auth_module.get_optional_user(credentials)
            assert result is None


# ==================== Role-Based Access Control Tests ====================


class TestRequireRole:
    """Tests for require_role function."""

    @pytest.mark.asyncio
    async def test_allowed_role(self):
        """Test user with allowed role passes."""
        from src.api.auth import User, require_role

        checker = require_role("admin", "developer")

        user = User(sub="user-1", groups=["developer"])

        with patch("src.api.auth.get_current_user", return_value=user):
            result = await checker(user)
            assert result == user

    @pytest.mark.asyncio
    async def test_disallowed_role_raises_403(self):
        """Test user without allowed role gets 403."""
        from src.api.auth import User, require_role

        checker = require_role("admin")

        user = User(sub="user-2", groups=["guest"])

        with assert_http_exception(403, "Access denied"):
            await checker(user)


# ==================== Cache Management Tests ====================


class TestClearAuthCaches:
    """Tests for clear_auth_caches function."""

    def test_clears_caches(self):
        """Test that caches are cleared."""
        from src.api import auth as auth_module
        from src.api.auth import clear_auth_caches, get_cognito_config

        # Verify the function runs without error
        clear_auth_caches()

        # Cognito config cache should be cleared (uses @lru_cache)
        assert get_cognito_config.cache_info().currsize == 0
        # JWKS TTL cache should be cleared (uses custom cache)
        assert auth_module._jwks_cache is None
        assert auth_module._jwks_key_map is None


# ==================== Pre-built Role Dependencies Tests ====================


class TestPrebuiltRoles:
    """Tests for pre-built role dependencies."""

    def test_require_admin_exists(self):
        """Test require_admin dependency exists."""
        from src.api.auth import require_admin

        assert callable(require_admin)

    def test_require_security_engineer_exists(self):
        """Test require_security_engineer dependency exists."""
        from src.api.auth import require_security_engineer

        assert callable(require_security_engineer)

    def test_require_developer_exists(self):
        """Test require_developer dependency exists."""
        from src.api.auth import require_developer

        assert callable(require_developer)
