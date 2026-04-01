"""
Tests for GitHub App Authentication Service.

Tests the GitHubAppAuth class that generates installation access tokens
from GitHub App credentials stored in SSM.
"""

import platform
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.github_app_auth import (
    GitHubAppAuth,
    GitHubAppCredentials,
    InstallationToken,
    get_github_app_auth,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_ssm_client():
    """Create a mock SSM client."""
    client = MagicMock()
    client.get_parameters.return_value = {
        "Parameters": [
            {"Name": "/aura/global/github-app-id", "Value": "123456"},
            {"Name": "/aura/global/github-app-installation-id", "Value": "78901234"},
            {
                "Name": "/aura/global/github-app-private-key",
                "Value": """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7MqNs4yU+1cnMN9DR
H9/Gs8IrJ+p7LqgNJnxsZfHh2l7OYvZqisnH3Qv7Lh7Ckg5c3x3Z5J5Y5Y5Y5Y5Y
Gz5cZ5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5
Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5
Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5
Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5
Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5
Zz5cZ5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5
Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5
Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5
-----END RSA PRIVATE KEY-----""",
            },
        ],
        "InvalidParameters": [],
    }
    return client


@pytest.fixture
def github_app_auth(mock_ssm_client):
    """Create a GitHubAppAuth instance with mocked SSM."""
    auth = GitHubAppAuth()
    auth._ssm_client = mock_ssm_client
    return auth


# ============================================================================
# Unit Tests
# ============================================================================


class TestGitHubAppAuth:
    """Tests for GitHubAppAuth class."""

    def test_load_credentials_success(self, github_app_auth, mock_ssm_client):
        """Test successful credential loading from SSM."""
        credentials = github_app_auth._load_credentials()

        assert credentials is not None
        assert credentials.app_id == "123456"
        assert credentials.installation_id == "78901234"
        assert "PRIVATE KEY" in credentials.private_key

        mock_ssm_client.get_parameters.assert_called_once()

    def test_load_credentials_missing_params(self, github_app_auth, mock_ssm_client):
        """Test handling of missing SSM parameters."""
        mock_ssm_client.get_parameters.return_value = {
            "Parameters": [],
            "InvalidParameters": [
                "/aura/global/github-app-id",
                "/aura/global/github-app-installation-id",
                "/aura/global/github-app-private-key",
            ],
        }

        credentials = github_app_auth._load_credentials()

        assert credentials is None

    def test_load_credentials_ssm_error(self, github_app_auth, mock_ssm_client):
        """Test handling of SSM errors."""
        mock_ssm_client.get_parameters.side_effect = Exception("SSM connection failed")

        credentials = github_app_auth._load_credentials()

        assert credentials is None

    def test_credentials_cached(self, github_app_auth, mock_ssm_client):
        """Test that credentials are cached after first load."""
        # First load
        github_app_auth._load_credentials()
        # Second load
        github_app_auth._load_credentials()

        # SSM should only be called once
        assert mock_ssm_client.get_parameters.call_count == 1

    @patch("src.services.github_app_auth.jwt.encode")
    def test_generate_jwt(self, mock_jwt_encode, github_app_auth):
        """Test JWT generation."""
        mock_jwt_encode.return_value = "mock-jwt-token"

        credentials = GitHubAppCredentials(
            app_id="123456",
            installation_id="78901234",
            private_key="test-private-key",
        )

        jwt_token = github_app_auth._generate_jwt(credentials)

        assert jwt_token == "mock-jwt-token"
        mock_jwt_encode.assert_called_once()

        # Verify JWT payload
        call_args = mock_jwt_encode.call_args
        payload = call_args[0][0]
        assert payload["iss"] == "123456"
        assert "iat" in payload
        assert "exp" in payload

    @patch("src.services.github_app_auth.requests.post")
    def test_request_installation_token_success(self, mock_post, github_app_auth):
        """Test successful installation token request."""
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "token": "ghs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "expires_at": expires_at,
        }
        mock_post.return_value.raise_for_status = MagicMock()

        credentials = GitHubAppCredentials(
            app_id="123456",
            installation_id="78901234",
            private_key="test-private-key",
        )

        token = github_app_auth._request_installation_token(
            credentials, "mock-jwt-token"
        )

        assert token is not None
        assert token.token == "ghs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

    @patch("src.services.github_app_auth.requests.post")
    def test_request_installation_token_failure(self, mock_post, github_app_auth):
        """Test handling of failed token request."""
        from requests.exceptions import RequestException

        mock_post.side_effect = RequestException("GitHub API error")

        credentials = GitHubAppCredentials(
            app_id="123456",
            installation_id="78901234",
            private_key="test-private-key",
        )

        token = github_app_auth._request_installation_token(
            credentials, "mock-jwt-token"
        )

        assert token is None

    def test_get_installation_token_cached(self, github_app_auth):
        """Test that valid cached tokens are returned."""
        # Set up a valid cached token
        github_app_auth._cached_token = InstallationToken(
            token="cached-token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        token = github_app_auth.get_installation_token()

        assert token == "cached-token"

    @patch("src.services.github_app_auth.requests.post")
    @patch("src.services.github_app_auth.jwt.encode")
    def test_get_installation_token_expired_cache(
        self, mock_jwt_encode, mock_post, github_app_auth
    ):
        """Test that expired cached tokens trigger new request."""
        # Set up an expired cached token
        github_app_auth._cached_token = InstallationToken(
            token="expired-token",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        # Mock JWT generation and token request
        mock_jwt_encode.return_value = "mock-jwt"
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "token": "new-token",
            "expires_at": expires_at,
        }
        mock_post.return_value.raise_for_status = MagicMock()

        token = github_app_auth.get_installation_token()

        # Should get new token, not the expired one
        assert token == "new-token"
        mock_jwt_encode.assert_called_once()
        mock_post.assert_called_once()

    def test_is_configured_true(self, github_app_auth):
        """Test is_configured returns True when credentials exist."""
        assert github_app_auth.is_configured() is True

    def test_is_configured_false(self, github_app_auth, mock_ssm_client):
        """Test is_configured returns False when credentials missing."""
        mock_ssm_client.get_parameters.return_value = {
            "Parameters": [],
            "InvalidParameters": ["/aura/global/github-app-id"],
        }
        # Reset cached state
        github_app_auth._credentials = None
        github_app_auth._credentials_loaded = False

        assert github_app_auth.is_configured() is False


class TestGetGitHubAppAuth:
    """Tests for get_github_app_auth singleton function."""

    def test_returns_singleton(self):
        """Test that get_github_app_auth returns the same instance."""
        # Reset singleton
        import src.services.github_app_auth as module

        module._github_app_auth = None

        auth1 = get_github_app_auth()
        auth2 = get_github_app_auth()

        assert auth1 is auth2


# ============================================================================
# Integration Tests
# ============================================================================


class TestGitHubAppAuthIntegration:
    """Integration tests for GitHub App authentication."""

    @pytest.mark.integration
    def test_full_token_generation_flow(self):
        """
        Integration test for full token generation.

        This test requires actual SSM parameters to be configured.
        Skip in CI unless SSM is available.
        """
        pytest.skip("Requires actual SSM configuration")
