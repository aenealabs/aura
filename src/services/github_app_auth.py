"""
Project Aura - GitHub App Authentication Service

Generates installation access tokens from GitHub App credentials stored in SSM.
Used for authenticating git clone operations for private repositories.

Author: Project Aura Team
Created: 2025-12-06
Version: 1.0.0
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import boto3
import jwt
import requests

logger = logging.getLogger(__name__)


@dataclass
class GitHubAppCredentials:
    """GitHub App credentials from SSM."""

    app_id: str
    installation_id: str
    private_key: str


@dataclass
class InstallationToken:
    """GitHub App installation access token."""

    token: str
    expires_at: datetime


class GitHubAppAuth:
    """
    GitHub App authentication for private repository access.

    Generates short-lived installation access tokens from GitHub App credentials
    stored in AWS SSM Parameter Store.

    SSM Parameters:
        /aura/global/github-app-id - App ID
        /aura/global/github-app-installation-id - Installation ID
        /aura/global/github-app-private-key - Private key (SecureString)

    Usage:
        auth = GitHubAppAuth()
        token = auth.get_installation_token()
        clone_url = f"https://x-access-token:{token}@github.com/org/repo.git"
    """

    # SSM parameter paths
    SSM_APP_ID = "/aura/global/github-app-id"
    SSM_INSTALLATION_ID = "/aura/global/github-app-installation-id"
    SSM_PRIVATE_KEY = "/aura/global/github-app-private-key"

    # GitHub API endpoint
    GITHUB_API_BASE = "https://api.github.com"

    def __init__(self, region: str = "us-east-1") -> None:
        """
        Initialize GitHub App authentication.

        Args:
            region: AWS region for SSM Parameter Store
        """
        self.region = region
        self._ssm_client = None
        self._credentials: GitHubAppCredentials | None = None
        self._cached_token: InstallationToken | None = None
        self._credentials_loaded = False

    @property
    def ssm_client(self):
        """Lazy SSM client initialization."""
        if self._ssm_client is None:
            self._ssm_client = boto3.client("ssm", region_name=self.region)
        return self._ssm_client

    def _load_credentials(self) -> GitHubAppCredentials | None:
        """Load GitHub App credentials from SSM Parameter Store."""
        if self._credentials_loaded:
            return self._credentials

        try:
            logger.info("Loading GitHub App credentials from SSM")

            # Get all parameters in one batch call
            response = self.ssm_client.get_parameters(
                Names=[self.SSM_APP_ID, self.SSM_INSTALLATION_ID, self.SSM_PRIVATE_KEY],
                WithDecryption=True,
            )

            # Check for missing parameters
            if response.get("InvalidParameters"):
                missing = response["InvalidParameters"]
                logger.warning(f"Missing GitHub App SSM parameters: {missing}")
                self._credentials_loaded = True
                return None

            # Extract values
            params = {p["Name"]: p["Value"] for p in response["Parameters"]}

            self._credentials = GitHubAppCredentials(
                app_id=params[self.SSM_APP_ID],
                installation_id=params[self.SSM_INSTALLATION_ID],
                private_key=params[self.SSM_PRIVATE_KEY],
            )
            self._credentials_loaded = True

            logger.info(
                f"Loaded GitHub App credentials: app_id={self._credentials.app_id}, "
                f"installation_id={self._credentials.installation_id}"
            )
            return self._credentials

        except Exception as e:
            logger.error(f"Failed to load GitHub App credentials from SSM: {e}")
            self._credentials_loaded = True
            return None

    def _generate_jwt(self, credentials: GitHubAppCredentials) -> str:
        """
        Generate a JWT for GitHub App authentication.

        The JWT is valid for 10 minutes and used to request installation tokens.

        Args:
            credentials: GitHub App credentials

        Returns:
            Signed JWT string
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued 60 seconds in the past (clock skew)
            "exp": now + (10 * 60),  # Expires in 10 minutes
            "iss": credentials.app_id,  # GitHub App ID
        }

        return jwt.encode(payload, credentials.private_key, algorithm="RS256")

    def _request_installation_token(
        self, credentials: GitHubAppCredentials, app_jwt: str
    ) -> InstallationToken | None:
        """
        Request an installation access token from GitHub API.

        Args:
            credentials: GitHub App credentials
            app_jwt: Signed JWT for app authentication

        Returns:
            InstallationToken if successful, None otherwise
        """
        url = (
            f"{self.GITHUB_API_BASE}/app/installations/"
            f"{credentials.installation_id}/access_tokens"
        )

        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            response = requests.post(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            token = data["token"]
            expires_at_str = data["expires_at"]

            # Parse expiration time (ISO 8601 format)
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))

            logger.info(
                f"Generated GitHub App installation token, expires at {expires_at}"
            )
            return InstallationToken(token=token, expires_at=expires_at)

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to request installation token from GitHub: {e}")
            return None

    def get_installation_token(self) -> str | None:
        """
        Get a valid installation access token.

        Returns a cached token if still valid, otherwise requests a new one.

        Returns:
            Installation access token string, or None if unavailable
        """
        # Check cached token validity (with 5 minute buffer)
        if self._cached_token:
            buffer = timedelta(minutes=5)
            if datetime.now(timezone.utc) + buffer < self._cached_token.expires_at:
                logger.debug("Using cached GitHub App installation token")
                return self._cached_token.token
            logger.debug("Cached token expired, requesting new one")

        # Load credentials if needed
        credentials = self._load_credentials()
        if not credentials:
            logger.warning("GitHub App credentials not configured")
            return None

        # Generate JWT and request installation token
        app_jwt = self._generate_jwt(credentials)
        token = self._request_installation_token(credentials, app_jwt)

        if token:
            self._cached_token = token
            return token.token

        return None

    def is_configured(self) -> bool:
        """Check if GitHub App credentials are configured in SSM."""
        return self._load_credentials() is not None


# Singleton instance for module-level access
_github_app_auth: GitHubAppAuth | None = None


def get_github_app_auth(region: str = "us-east-1") -> GitHubAppAuth:
    """Get the singleton GitHubAppAuth instance."""
    global _github_app_auth
    if _github_app_auth is None:
        _github_app_auth = GitHubAppAuth(region=region)
    return _github_app_auth
