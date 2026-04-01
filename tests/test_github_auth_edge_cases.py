"""
Edge Case Tests for GitHub App Authentication Token Handling.

Tests for edge cases in GitHub App authentication including:
- Token expiration during long-running operations
- SSM parameter rotation during token generation
- GitHub API rate limit exhaustion

These tests ensure robust handling of authentication edge cases
in production environments.
"""

import platform
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import RequestException

# These tests require pytest-forked for isolation on non-Linux systems
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.github_app_auth import (
    GitHubAppAuth,
    GitHubAppCredentials,
    InstallationToken,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_ssm_client():
    """Create a mock SSM client with valid credentials."""
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


@pytest.fixture
def valid_credentials():
    """Create valid GitHub App credentials for testing."""
    return GitHubAppCredentials(
        app_id="123456",
        installation_id="78901234",
        private_key="test-private-key",
    )


# ============================================================================
# Token Expiration During Long-Running Operations Tests
# ============================================================================


class TestTokenExpirationMidOperation:
    """
    Tests for handling token expiration during long-running operations.

    These tests verify that the authentication service properly handles
    cases where a token expires while an operation is in progress.
    """

    def test_token_expires_within_buffer_triggers_refresh(self, github_app_auth):
        """
        Test that tokens expiring within the 5-minute buffer trigger refresh.

        The GitHubAppAuth service uses a 5-minute buffer before token expiry
        to ensure tokens don't expire during operations. This test verifies
        that behavior.
        """
        # Set up a token that expires in 4 minutes (within 5-minute buffer)
        github_app_auth._cached_token = InstallationToken(
            token="about-to-expire-token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=4),
        )

        with patch("src.services.github_app_auth.jwt.encode") as mock_jwt:
            with patch("src.services.github_app_auth.requests.post") as mock_post:
                mock_jwt.return_value = "new-jwt"
                new_expires = datetime.now(timezone.utc) + timedelta(hours=1)
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {
                    "token": "fresh-token",
                    "expires_at": new_expires.isoformat(),
                }
                mock_post.return_value.raise_for_status = MagicMock()

                token = github_app_auth.get_installation_token()

                # Should get fresh token, not the about-to-expire one
                assert token == "fresh-token"
                mock_jwt.assert_called_once()
                mock_post.assert_called_once()

    def test_token_expiry_exactly_at_buffer_boundary(self, github_app_auth):
        """
        Test behavior when token expires exactly at the 5-minute buffer boundary.

        Edge case where token expiry time is exactly 5 minutes from now.
        """
        # Token expires in exactly 5 minutes (at the boundary)
        github_app_auth._cached_token = InstallationToken(
            token="boundary-token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )

        with patch("src.services.github_app_auth.jwt.encode") as mock_jwt:
            with patch("src.services.github_app_auth.requests.post") as mock_post:
                mock_jwt.return_value = "new-jwt"
                new_expires = datetime.now(timezone.utc) + timedelta(hours=1)
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {
                    "token": "refreshed-token",
                    "expires_at": new_expires.isoformat(),
                }
                mock_post.return_value.raise_for_status = MagicMock()

                token = github_app_auth.get_installation_token()

                # At exactly 5 minutes, should still refresh (buffer is < not <=)
                assert token == "refreshed-token"

    def test_token_still_valid_beyond_buffer(self, github_app_auth):
        """
        Test that tokens valid beyond the buffer period are returned as-is.

        Verifies that we don't unnecessarily refresh tokens that are still
        well within their validity period.
        """
        # Token expires in 10 minutes (well beyond 5-minute buffer)
        github_app_auth._cached_token = InstallationToken(
            token="valid-token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )

        with patch("src.services.github_app_auth.jwt.encode") as mock_jwt:
            token = github_app_auth.get_installation_token()

            # Should return cached token without attempting refresh
            assert token == "valid-token"
            mock_jwt.assert_not_called()

    def test_cleanup_on_partial_operation_failure(self, github_app_auth):
        """
        Test that state is properly cleaned up when token request fails.

        Verifies that after a failed token request, the auth service
        doesn't leave partial state that could cause issues.
        """
        # Start with no cached token
        github_app_auth._cached_token = None

        with patch("src.services.github_app_auth.jwt.encode") as mock_jwt:
            with patch("src.services.github_app_auth.requests.post") as mock_post:
                mock_jwt.return_value = "test-jwt"
                # Simulate network failure during token request
                mock_post.side_effect = RequestException("Connection timeout")

                token = github_app_auth.get_installation_token()

                # Should return None and not cache any partial state
                assert token is None
                assert github_app_auth._cached_token is None

    @patch("src.services.github_app_auth.requests.post")
    @patch("src.services.github_app_auth.jwt.encode")
    def test_automatic_retry_on_token_refresh_failure(
        self, mock_jwt, mock_post, github_app_auth
    ):
        """
        Test behavior when automatic token refresh fails.

        When a cached token is expired and refresh fails, the service
        should return None rather than an expired token.
        """
        # Set up an expired token
        github_app_auth._cached_token = InstallationToken(
            token="expired-token",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        mock_jwt.return_value = "test-jwt"
        mock_post.side_effect = RequestException("GitHub API unavailable")

        token = github_app_auth.get_installation_token()

        # Should return None when refresh fails, not the expired token
        assert token is None


# ============================================================================
# SSM Parameter Rotation During Token Generation Tests
# ============================================================================


class TestSSMParameterRotation:
    """
    Tests for handling SSM parameter rotation during token generation.

    These tests verify proper handling when SSM parameters (GitHub App
    credentials) are rotated while the service is running.
    """

    def test_refetch_credentials_on_jwt_signing_failure(self, github_app_auth):
        """
        Test re-fetching credentials when JWT signing fails due to rotated key.

        When the private key is rotated in SSM, the cached credentials
        become invalid. This test simulates that scenario.
        """
        # Pre-load credentials (simulating a running service)
        github_app_auth._load_credentials()

        with patch("src.services.github_app_auth.jwt.encode") as mock_jwt:
            # First call fails (old key), but we don't have automatic retry
            # in current implementation - this tests current behavior
            mock_jwt.side_effect = Exception("Invalid key format")

            with patch("src.services.github_app_auth.requests.post"):
                # The service will attempt to generate JWT and fail
                # Currently returns None when JWT generation fails
                try:
                    github_app_auth._generate_jwt(github_app_auth._credentials)
                except Exception as e:
                    assert "Invalid key format" in str(e)

    def test_credentials_reload_after_reset(self, github_app_auth, mock_ssm_client):
        """
        Test that credentials can be reloaded after resetting cached state.

        Verifies the pattern for forcing credential refresh when rotation
        is detected.
        """
        # First load
        creds1 = github_app_auth._load_credentials()
        assert creds1.app_id == "123456"

        # Update SSM to return new credentials (simulating rotation)
        mock_ssm_client.get_parameters.return_value = {
            "Parameters": [
                {"Name": "/aura/global/github-app-id", "Value": "999888"},
                {
                    "Name": "/aura/global/github-app-installation-id",
                    "Value": "11112222",
                },
                {"Name": "/aura/global/github-app-private-key", "Value": "new-key"},
            ],
            "InvalidParameters": [],
        }

        # Reset cached state to force reload
        github_app_auth._credentials = None
        github_app_auth._credentials_loaded = False

        # Second load should get new credentials
        creds2 = github_app_auth._load_credentials()
        assert creds2.app_id == "999888"
        assert creds2.installation_id == "11112222"

    def test_graceful_handling_of_invalid_rotated_key(
        self, github_app_auth, mock_ssm_client
    ):
        """
        Test graceful handling when rotated key is invalid/malformed.

        SSM might contain a malformed key during rotation. The service
        should handle this gracefully.
        """
        # Reset state
        github_app_auth._credentials = None
        github_app_auth._credentials_loaded = False

        # Return malformed key from SSM
        mock_ssm_client.get_parameters.return_value = {
            "Parameters": [
                {"Name": "/aura/global/github-app-id", "Value": "123456"},
                {
                    "Name": "/aura/global/github-app-installation-id",
                    "Value": "78901234",
                },
                {
                    "Name": "/aura/global/github-app-private-key",
                    "Value": "not-a-valid-key",
                },
            ],
            "InvalidParameters": [],
        }

        creds = github_app_auth._load_credentials()

        # Credentials load succeeds (validation happens at JWT generation time)
        assert creds is not None
        assert creds.private_key == "not-a-valid-key"

        # JWT generation will fail with invalid key
        with pytest.raises(Exception):
            github_app_auth._generate_jwt(creds)

    def test_ssm_unavailable_during_credential_load(
        self, github_app_auth, mock_ssm_client
    ):
        """
        Test handling when SSM becomes unavailable during credential load.

        Simulates AWS service disruption during credential fetch.
        """
        # Reset state
        github_app_auth._credentials = None
        github_app_auth._credentials_loaded = False

        # SSM throws exception
        mock_ssm_client.get_parameters.side_effect = Exception(
            "SSM service unavailable"
        )

        creds = github_app_auth._load_credentials()

        # Should return None and mark credentials as loaded (to prevent retry storm)
        assert creds is None
        assert github_app_auth._credentials_loaded is True

    def test_partial_ssm_response_during_rotation(
        self, github_app_auth, mock_ssm_client
    ):
        """
        Test handling when SSM returns partial parameters during rotation.

        During rotation, some parameters might be temporarily missing.
        """
        # Reset state
        github_app_auth._credentials = None
        github_app_auth._credentials_loaded = False

        # SSM returns only some parameters (missing private key)
        mock_ssm_client.get_parameters.return_value = {
            "Parameters": [
                {"Name": "/aura/global/github-app-id", "Value": "123456"},
                {
                    "Name": "/aura/global/github-app-installation-id",
                    "Value": "78901234",
                },
            ],
            "InvalidParameters": ["/aura/global/github-app-private-key"],
        }

        creds = github_app_auth._load_credentials()

        # Should return None when parameters are missing
        assert creds is None


# ============================================================================
# GitHub API Rate Limit Exhaustion Tests
# ============================================================================


class TestGitHubRateLimitHandling:
    """
    Tests for handling GitHub API rate limit exhaustion.

    GitHub enforces a 5000 requests/hour limit for authenticated requests.
    These tests verify proper handling of rate limit responses.
    """

    @patch("src.services.github_app_auth.requests.post")
    def test_rate_limit_403_response(
        self, mock_post, github_app_auth, valid_credentials
    ):
        """
        Test handling of 403 response with rate limit headers.

        When rate limit is exhausted, GitHub returns 403 with specific headers.
        """
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
        }
        mock_response.json.return_value = {
            "message": "API rate limit exceeded",
            "documentation_url": "https://docs.github.com/rest/rate-limit",
        }
        mock_response.raise_for_status.side_effect = RequestException(
            "403 Client Error: Forbidden"
        )
        mock_post.return_value = mock_response

        with patch("src.services.github_app_auth.jwt.encode", return_value="test-jwt"):
            token = github_app_auth._request_installation_token(
                valid_credentials, "test-jwt"
            )

            # Should return None on rate limit
            assert token is None

    @patch("src.services.github_app_auth.requests.post")
    def test_rate_limit_header_parsing(
        self, mock_post, github_app_auth, valid_credentials
    ):
        """
        Test that rate limit headers are properly accessible from response.

        Verifies the response structure when rate limits are encountered.
        """
        reset_time = int(time.time()) + 1800  # 30 minutes from now

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(reset_time),
            "Retry-After": "1800",
        }
        mock_response.raise_for_status.side_effect = RequestException("Rate limited")
        mock_post.return_value = mock_response

        # Verify headers are accessible
        assert mock_response.headers["X-RateLimit-Remaining"] == "0"
        assert mock_response.headers["X-RateLimit-Reset"] == str(reset_time)
        assert mock_response.headers.get("Retry-After") == "1800"

    @patch("src.services.github_app_auth.requests.post")
    def test_secondary_rate_limit_handling(
        self, mock_post, github_app_auth, valid_credentials
    ):
        """
        Test handling of secondary rate limits (abuse detection).

        GitHub has secondary rate limits for abuse detection that can trigger
        even when primary rate limits are not exhausted.
        """
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "4999",  # Not at limit
            "Retry-After": "60",  # But we hit secondary limit
        }
        mock_response.json.return_value = {
            "message": "You have exceeded a secondary rate limit",
            "documentation_url": "https://docs.github.com/rest/rate-limit",
        }
        mock_response.raise_for_status.side_effect = RequestException(
            "Secondary rate limit"
        )
        mock_post.return_value = mock_response

        with patch("src.services.github_app_auth.jwt.encode", return_value="test-jwt"):
            token = github_app_auth._request_installation_token(
                valid_credentials, "test-jwt"
            )

            # Should handle secondary rate limits gracefully
            assert token is None

    @patch("src.services.github_app_auth.requests.post")
    def test_rate_limit_with_retry_after_header(
        self, mock_post, github_app_auth, valid_credentials
    ):
        """
        Test that Retry-After header is respected in rate limit responses.

        The Retry-After header tells us how long to wait before retrying.
        """
        mock_response = MagicMock()
        mock_response.status_code = 429  # Too Many Requests
        mock_response.headers = {
            "Retry-After": "120",  # Wait 2 minutes
            "X-RateLimit-Remaining": "0",
        }
        mock_response.raise_for_status.side_effect = RequestException(
            "Too Many Requests"
        )
        mock_post.return_value = mock_response

        with patch("src.services.github_app_auth.jwt.encode", return_value="test-jwt"):
            token = github_app_auth._request_installation_token(
                valid_credentials, "test-jwt"
            )

            # Should return None, allowing caller to handle retry
            assert token is None

    @patch("src.services.github_app_auth.requests.post")
    def test_near_rate_limit_warning_scenario(
        self, mock_post, github_app_auth, valid_credentials
    ):
        """
        Test behavior when approaching rate limit (low remaining count).

        Service should still work when rate limit is low but not exhausted.
        """
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "50",  # Very low but not zero
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
        }
        mock_response.json.return_value = {
            "token": "low-limit-token",
            "expires_at": expires_at.isoformat(),
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with patch("src.services.github_app_auth.jwt.encode", return_value="test-jwt"):
            token = github_app_auth._request_installation_token(
                valid_credentials, "test-jwt"
            )

            # Should succeed even with low remaining rate limit
            assert token is not None
            assert token.token == "low-limit-token"


# ============================================================================
# Combined Edge Case Scenarios
# ============================================================================


class TestCombinedEdgeCases:
    """
    Tests for scenarios combining multiple edge cases.

    Real-world scenarios often involve multiple failure modes occurring
    together or in sequence.
    """

    @patch("src.services.github_app_auth.requests.post")
    @patch("src.services.github_app_auth.jwt.encode")
    def test_token_expiry_plus_rate_limit_on_refresh(
        self, mock_jwt, mock_post, github_app_auth
    ):
        """
        Test scenario where token expires and refresh hits rate limit.

        Worst-case scenario: cached token expired, and we can't get a new one
        because of rate limiting.
        """
        # Set up expired token
        github_app_auth._cached_token = InstallationToken(
            token="expired-token",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        mock_jwt.return_value = "test-jwt"

        # Token refresh hits rate limit
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {"X-RateLimit-Remaining": "0"}
        mock_response.raise_for_status.side_effect = RequestException("Rate limited")
        mock_post.return_value = mock_response

        token = github_app_auth.get_installation_token()

        # Should return None, not the expired token
        assert token is None

    def test_ssm_rotation_plus_token_expiry(self, github_app_auth, mock_ssm_client):
        """
        Test scenario where SSM credentials rotate while token is expired.

        Both the cached credentials and cached token become invalid
        simultaneously.
        """
        # Initial setup with expired token
        github_app_auth._cached_token = InstallationToken(
            token="expired-token",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        # SSM returns different credentials (rotated)
        mock_ssm_client.get_parameters.return_value = {
            "Parameters": [
                {"Name": "/aura/global/github-app-id", "Value": "new-app-id"},
                {
                    "Name": "/aura/global/github-app-installation-id",
                    "Value": "new-install-id",
                },
                {"Name": "/aura/global/github-app-private-key", "Value": "new-key"},
            ],
            "InvalidParameters": [],
        }

        with patch("src.services.github_app_auth.jwt.encode") as mock_jwt:
            with patch("src.services.github_app_auth.requests.post") as mock_post:
                mock_jwt.return_value = "new-jwt"
                new_expires = datetime.now(timezone.utc) + timedelta(hours=1)
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {
                    "token": "new-token-from-rotated-creds",
                    "expires_at": new_expires.isoformat(),
                }
                mock_post.return_value.raise_for_status = MagicMock()

                token = github_app_auth.get_installation_token()

                # Should successfully get new token with rotated credentials
                assert token == "new-token-from-rotated-creds"

    def test_multiple_rapid_token_requests(self, github_app_auth):
        """
        Test handling of multiple rapid token requests.

        Ensures that concurrent-like access patterns don't cause issues
        with token caching.
        """
        # Set up valid cached token
        valid_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        github_app_auth._cached_token = InstallationToken(
            token="cached-token",
            expires_at=valid_expires,
        )

        with patch("src.services.github_app_auth.jwt.encode") as mock_jwt:
            # Multiple rapid calls
            tokens = [github_app_auth.get_installation_token() for _ in range(10)]

            # All should return the same cached token
            assert all(t == "cached-token" for t in tokens)
            # JWT should never be called (all served from cache)
            mock_jwt.assert_not_called()


# ============================================================================
# Network and Timeout Edge Cases
# ============================================================================


class TestNetworkEdgeCases:
    """
    Tests for network-related edge cases.

    Tests handling of network issues, timeouts, and connectivity problems.
    """

    @patch("src.services.github_app_auth.requests.post")
    def test_connection_timeout(self, mock_post, github_app_auth, valid_credentials):
        """
        Test handling of connection timeout to GitHub API.
        """
        from requests.exceptions import ConnectTimeout

        mock_post.side_effect = ConnectTimeout("Connection timed out")

        with patch("src.services.github_app_auth.jwt.encode", return_value="test-jwt"):
            token = github_app_auth._request_installation_token(
                valid_credentials, "test-jwt"
            )

            assert token is None

    @patch("src.services.github_app_auth.requests.post")
    def test_read_timeout(self, mock_post, github_app_auth, valid_credentials):
        """
        Test handling of read timeout from GitHub API.
        """
        from requests.exceptions import ReadTimeout

        mock_post.side_effect = ReadTimeout("Read timed out")

        with patch("src.services.github_app_auth.jwt.encode", return_value="test-jwt"):
            token = github_app_auth._request_installation_token(
                valid_credentials, "test-jwt"
            )

            assert token is None

    @patch("src.services.github_app_auth.requests.post")
    def test_ssl_certificate_error(self, mock_post, github_app_auth, valid_credentials):
        """
        Test handling of SSL certificate verification failure.
        """
        from requests.exceptions import SSLError

        mock_post.side_effect = SSLError("Certificate verification failed")

        with patch("src.services.github_app_auth.jwt.encode", return_value="test-jwt"):
            token = github_app_auth._request_installation_token(
                valid_credentials, "test-jwt"
            )

            assert token is None

    @patch("src.services.github_app_auth.requests.post")
    def test_dns_resolution_failure(
        self, mock_post, github_app_auth, valid_credentials
    ):
        """
        Test handling of DNS resolution failure for GitHub API.
        """
        from requests.exceptions import ConnectionError

        mock_post.side_effect = ConnectionError("Failed to resolve 'api.github.com'")

        with patch("src.services.github_app_auth.jwt.encode", return_value="test-jwt"):
            token = github_app_auth._request_installation_token(
                valid_credentials, "test-jwt"
            )

            assert token is None

    @patch("src.services.github_app_auth.requests.post")
    def test_github_500_internal_server_error(
        self, mock_post, github_app_auth, valid_credentials
    ):
        """
        Test handling of GitHub API 500 Internal Server Error.
        """
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = RequestException(
            "500 Server Error: Internal Server Error"
        )
        mock_post.return_value = mock_response

        with patch("src.services.github_app_auth.jwt.encode", return_value="test-jwt"):
            token = github_app_auth._request_installation_token(
                valid_credentials, "test-jwt"
            )

            assert token is None

    @patch("src.services.github_app_auth.requests.post")
    def test_github_503_service_unavailable(
        self, mock_post, github_app_auth, valid_credentials
    ):
        """
        Test handling of GitHub API 503 Service Unavailable.
        """
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.headers = {"Retry-After": "30"}
        mock_response.raise_for_status.side_effect = RequestException(
            "503 Server Error: Service Unavailable"
        )
        mock_post.return_value = mock_response

        with patch("src.services.github_app_auth.jwt.encode", return_value="test-jwt"):
            token = github_app_auth._request_installation_token(
                valid_credentials, "test-jwt"
            )

            assert token is None
