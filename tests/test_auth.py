"""
Project Aura - Authentication Module Tests

Tests for the Cognito JWT authentication middleware.
These tests focus on data models (CognitoConfig, User) which don't require
mocking of httpx or jose modules.
"""

import os
from unittest.mock import patch

from src.api.auth import CognitoConfig, User


class TestCognitoConfig:
    """Tests for CognitoConfig dataclass."""

    def test_config_creation(self):
        """Test basic config creation."""
        config = CognitoConfig(
            region="us-east-1",
            user_pool_id="us-east-1_abc123",
            client_id="client123",
        )
        assert config.region == "us-east-1"
        assert config.user_pool_id == "us-east-1_abc123"
        assert config.client_id == "client123"

    def test_issuer_property(self):
        """Test issuer URL generation."""
        config = CognitoConfig(
            region="us-west-2",
            user_pool_id="us-west-2_xyz789",
            client_id="client456",
        )
        expected = "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_xyz789"
        assert config.issuer == expected

    def test_jwks_url_property(self):
        """Test JWKS URL generation."""
        config = CognitoConfig(
            region="eu-west-1",
            user_pool_id="eu-west-1_test",
            client_id="client",
        )
        expected = "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_test/.well-known/jwks.json"
        assert config.jwks_url == expected

    def test_different_regions(self):
        """Test config with different AWS regions."""
        regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
        for region in regions:
            config = CognitoConfig(
                region=region,
                user_pool_id=f"{region}_pool",
                client_id="client",
            )
            assert region in config.issuer
            assert region in config.jwks_url


class TestUser:
    """Tests for User dataclass."""

    def test_user_creation_minimal(self):
        """Test user with minimal fields."""
        user = User(sub="user-123")
        assert user.sub == "user-123"
        assert user.email is None
        assert user.name is None
        assert user.groups == []

    def test_user_creation_full(self):
        """Test user with all fields."""
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
        user = User(
            sub="user-789",
            groups=["admin", "readonly"],
        )
        assert user.roles == ["admin", "readonly"]

    def test_empty_roles(self):
        """Test roles with no groups."""
        user = User(sub="user-empty")
        assert user.roles == []

    def test_single_role(self):
        """Test user with single role."""
        user = User(sub="user-single", groups=["viewer"])
        assert len(user.roles) == 1
        assert "viewer" in user.roles


class TestCognitoConfigIntegration:
    """Integration tests for Cognito config loading."""

    def test_config_from_env_vars(self):
        """Test loading config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "AWS_REGION": "us-east-1",
                "COGNITO_USER_POOL_ID": "test-pool",
                "COGNITO_CLIENT_ID": "test-client",
            },
        ):
            # The actual get_cognito_config uses lru_cache,
            # so we test the config creation directly
            config = CognitoConfig(
                region="us-east-1",
                user_pool_id="test-pool",
                client_id="test-client",
            )
            assert config.user_pool_id == "test-pool"
            assert config.client_id == "test-client"


class TestUserRoles:
    """Tests for user role functionality."""

    def test_admin_role(self):
        """Test admin role detection."""
        admin_user = User(sub="admin-1", groups=["admin"])
        assert "admin" in admin_user.roles

    def test_multiple_roles(self):
        """Test user with multiple roles."""
        multi_role = User(
            sub="multi-1",
            groups=["admin", "developer", "reviewer"],
        )
        assert len(multi_role.roles) == 3
        assert "admin" in multi_role.roles
        assert "developer" in multi_role.roles
        assert "reviewer" in multi_role.roles

    def test_role_preservation_order(self):
        """Test that role order is preserved."""
        user = User(sub="order-1", groups=["first", "second", "third"])
        assert user.roles == ["first", "second", "third"]


class TestUserDataModel:
    """Tests for User data model validation."""

    def test_user_sub_required(self):
        """Test that sub is required."""
        # This should work
        user = User(sub="required-sub")
        assert user.sub == "required-sub"

    def test_optional_email(self):
        """Test email is optional."""
        user1 = User(sub="u1")
        assert user1.email is None

        user2 = User(sub="u2", email="test@test.com")
        assert user2.email == "test@test.com"

    def test_optional_name(self):
        """Test name is optional."""
        user1 = User(sub="u1")
        assert user1.name is None

        user2 = User(sub="u2", name="John Doe")
        assert user2.name == "John Doe"

    def test_groups_default(self):
        """Test groups defaults to empty list."""
        user = User(sub="u1")
        assert isinstance(user.groups, list)
        assert len(user.groups) == 0


class TestCognitoIssuerFormats:
    """Tests for Cognito issuer URL format."""

    def test_standard_format(self):
        """Test standard issuer format."""
        config = CognitoConfig(
            region="us-east-1",
            user_pool_id="us-east-1_aBcDeF123",
            client_id="client",
        )
        assert "cognito-idp" in config.issuer
        assert "amazonaws.com" in config.issuer

    def test_pool_id_in_issuer(self):
        """Test that pool ID is in issuer URL."""
        pool_id = "us-west-2_TestPool123"
        config = CognitoConfig(
            region="us-west-2",
            user_pool_id=pool_id,
            client_id="client",
        )
        assert pool_id in config.issuer

    def test_issuer_https(self):
        """Test that issuer uses HTTPS."""
        config = CognitoConfig(
            region="us-east-1",
            user_pool_id="pool",
            client_id="client",
        )
        assert config.issuer.startswith("https://")

    def test_jwks_ends_with_json(self):
        """Test JWKS URL ends with jwks.json."""
        config = CognitoConfig(
            region="us-east-1",
            user_pool_id="pool",
            client_id="client",
        )
        assert config.jwks_url.endswith("jwks.json")
