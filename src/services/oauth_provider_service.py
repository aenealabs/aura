"""
Project Aura - OAuth Provider Service

Handles OAuth flows for GitHub and GitLab repository connections.
Manages token exchange, storage in Secrets Manager, and token refresh.

Author: Project Aura Team
Created: 2025-12-17
Version: 1.0.0
"""

import hashlib
import json
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlencode

import boto3
import requests
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class OAuthProvider(Enum):
    """Supported OAuth providers."""

    GITHUB = "github"
    GITLAB = "gitlab"


class ConnectionStatus(Enum):
    """OAuth connection status."""

    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    ERROR = "error"


@dataclass
class OAuthTokens:
    """OAuth token data."""

    access_token: str
    token_type: str
    scope: str
    refresh_token: str | None = None
    expires_at: datetime | None = None


@dataclass
class OAuthConnection:
    """Represents an OAuth connection."""

    connection_id: str
    user_id: str
    provider: str
    provider_user_id: str
    provider_username: str
    scopes: list[str]
    status: str
    created_at: str
    expires_at: str | None = None


@dataclass
class ProviderRepository:
    """Repository from OAuth provider."""

    provider_repo_id: str
    name: str
    full_name: str
    clone_url: str
    default_branch: str
    private: bool
    language: str | None
    size_kb: int
    updated_at: str


class OAuthProviderService:
    """
    OAuth Provider Service.

    Handles OAuth flows for GitHub and GitLab:
    1. Generate authorization URLs with state parameter
    2. Exchange authorization codes for tokens
    3. Store tokens securely in Secrets Manager
    4. Refresh expired tokens
    5. List repositories from providers
    """

    # OAuth configuration
    GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
    GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
    GITHUB_API_URL = "https://api.github.com"
    GITHUB_SCOPES = ["repo", "admin:repo_hook"]

    GITLAB_AUTH_URL = "https://gitlab.com/oauth/authorize"
    GITLAB_TOKEN_URL = "https://gitlab.com/oauth/token"
    GITLAB_API_URL = "https://gitlab.com/api/v4"
    GITLAB_SCOPES = ["read_repository", "api"]

    def __init__(
        self,
        dynamodb_client: Any | None = None,
        secrets_client: Any | None = None,
        environment: str | None = None,
        project_name: str = "aura",
    ):
        """Initialize OAuth provider service."""
        self.environment = environment or os.getenv("ENVIRONMENT", "dev")
        self.project_name = project_name

        self.dynamodb = dynamodb_client or boto3.resource("dynamodb")
        self.secrets_client = secrets_client or boto3.client("secretsmanager")

        self.connections_table = self.dynamodb.Table(
            f"{project_name}-oauth-connections-{self.environment}"
        )

        # OAuth client credentials from environment/SSM
        self._github_client_id = os.getenv("GITHUB_OAUTH_CLIENT_ID")
        self._github_client_secret = os.getenv("GITHUB_OAUTH_CLIENT_SECRET")
        self._gitlab_client_id = os.getenv("GITLAB_OAUTH_CLIENT_ID")
        self._gitlab_client_secret = os.getenv("GITLAB_OAUTH_CLIENT_SECRET")

        self._callback_url = os.getenv(
            "OAUTH_CALLBACK_URL", "https://api.aura.local/api/v1/oauth/callback"
        )

    def _generate_state(self, user_id: str, provider: str) -> str:
        """Generate secure state parameter for CSRF protection."""
        random_bytes = secrets.token_bytes(32)
        state_data = f"{user_id}:{provider}:{random_bytes.hex()}"
        return hashlib.sha256(state_data.encode()).hexdigest()

    def _store_state(self, state: str, user_id: str, provider: str) -> None:
        """Store OAuth state in DynamoDB with TTL."""
        ttl = int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp())
        self.connections_table.put_item(
            Item={
                "connection_id": f"state:{state}",
                "user_id": user_id,
                "provider": provider,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ttl": ttl,
            }
        )

    def _validate_state(self, state: str) -> dict | None:
        """Validate and consume OAuth state."""
        try:
            response = self.connections_table.get_item(
                Key={"connection_id": f"state:{state}"}
            )
            item = response.get("Item")
            if item and item.get("status") == "pending":
                # Delete state after validation (single use)
                self.connections_table.delete_item(
                    Key={"connection_id": f"state:{state}"}
                )
                return item
            return None
        except ClientError as e:
            logger.error(f"Error validating state: {e}")
            return None

    async def initiate_oauth(self, provider: str, user_id: str) -> tuple[str, str]:
        """
        Generate OAuth authorization URL.

        Args:
            provider: OAuth provider (github, gitlab)
            user_id: Current user ID

        Returns:
            Tuple of (authorization_url, state)
        """
        if provider not in [p.value for p in OAuthProvider]:
            raise ValueError(f"Unsupported provider: {provider}")

        state = self._generate_state(user_id, provider)
        self._store_state(state, user_id, provider)

        if provider == OAuthProvider.GITHUB.value:
            params = {
                "client_id": self._github_client_id,
                "redirect_uri": self._callback_url,
                "scope": " ".join(self.GITHUB_SCOPES),
                "state": state,
            }
            auth_url = f"{self.GITHUB_AUTH_URL}?{urlencode(params)}"
        else:  # GitLab
            params = {
                "client_id": self._gitlab_client_id,
                "redirect_uri": self._callback_url,
                "response_type": "code",
                "scope": " ".join(self.GITLAB_SCOPES),
                "state": state,
            }
            auth_url = f"{self.GITLAB_AUTH_URL}?{urlencode(params)}"

        logger.info(f"Generated OAuth URL for provider={provider}, user={user_id}")
        return auth_url, state

    async def complete_oauth(
        self, provider: str, code: str, state: str
    ) -> OAuthConnection:
        """
        Complete OAuth flow by exchanging code for tokens.

        Args:
            provider: OAuth provider
            code: Authorization code from callback
            state: State parameter for validation

        Returns:
            OAuthConnection object
        """
        # Validate state
        state_data = self._validate_state(state)
        if not state_data:
            raise ValueError("Invalid or expired state parameter")

        user_id = state_data["user_id"]

        # Exchange code for tokens
        if provider == OAuthProvider.GITHUB.value:
            tokens = await self._exchange_github_code(code)
            user_info = await self._get_github_user(tokens.access_token)
        else:  # GitLab
            tokens = await self._exchange_gitlab_code(code)
            user_info = await self._get_gitlab_user(tokens.access_token)

        # Generate connection ID
        connection_id = secrets.token_urlsafe(16)

        # Store tokens in Secrets Manager
        secret_name = f"/{self.project_name}/{self.environment}/oauth/{connection_id}"
        try:
            self.secrets_client.create_secret(
                Name=secret_name,
                SecretString=json.dumps(
                    {
                        "access_token": tokens.access_token,
                        "refresh_token": tokens.refresh_token,
                        "token_type": tokens.token_type,
                        "scope": tokens.scope,
                        "expires_at": (
                            tokens.expires_at.isoformat() if tokens.expires_at else None
                        ),
                    }
                ),
                Tags=[
                    {"Key": "Project", "Value": self.project_name},
                    {"Key": "Environment", "Value": self.environment},
                    {"Key": "Component", "Value": "oauth"},
                ],
            )
        except ClientError as e:
            logger.error(f"Failed to store OAuth tokens: {e}")
            raise

        # Store connection metadata in DynamoDB
        connection = OAuthConnection(
            connection_id=connection_id,
            user_id=user_id,
            provider=provider,
            provider_user_id=user_info["id"],
            provider_username=user_info["username"],
            scopes=tokens.scope.split(" ") if tokens.scope else [],
            status=ConnectionStatus.ACTIVE.value,
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=tokens.expires_at.isoformat() if tokens.expires_at else None,
        )

        self.connections_table.put_item(
            Item={
                "connection_id": connection_id,
                "user_id": user_id,
                "provider": provider,
                "provider_user_id": user_info["id"],
                "provider_username": user_info["username"],
                "scopes": connection.scopes,
                "status": connection.status,
                "secrets_arn": secret_name,
                "created_at": connection.created_at,
                "expires_at": connection.expires_at,
            }
        )

        logger.info(f"Created OAuth connection: {connection_id} for user={user_id}")
        return connection

    async def _exchange_github_code(self, code: str) -> OAuthTokens:
        """Exchange GitHub authorization code for tokens."""
        response = requests.post(
            self.GITHUB_TOKEN_URL,
            data={
                "client_id": self._github_client_id,
                "client_secret": self._github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise ValueError(f"GitHub OAuth error: {data['error_description']}")

        return OAuthTokens(
            access_token=data["access_token"],
            token_type=data.get("token_type", "bearer"),
            scope=data.get("scope", ""),
            refresh_token=data.get("refresh_token"),
            expires_at=None,  # GitHub tokens don't expire by default
        )

    async def _exchange_gitlab_code(self, code: str) -> OAuthTokens:
        """Exchange GitLab authorization code for tokens."""
        response = requests.post(
            self.GITLAB_TOKEN_URL,
            data={
                "client_id": self._gitlab_client_id,
                "client_secret": self._gitlab_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self._callback_url,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise ValueError(f"GitLab OAuth error: {data['error_description']}")

        expires_at = None
        if "expires_in" in data:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=data["expires_in"]
            )

        return OAuthTokens(
            access_token=data["access_token"],
            token_type=data.get("token_type", "bearer"),
            scope=data.get("scope", ""),
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
        )

    async def _get_github_user(self, access_token: str) -> dict:
        """Get GitHub user info."""
        response = requests.get(
            f"{self.GITHUB_API_URL}/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return {"id": str(data["id"]), "username": data["login"]}

    async def _get_gitlab_user(self, access_token: str) -> dict:
        """Get GitLab user info."""
        response = requests.get(
            f"{self.GITLAB_API_URL}/user",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return {"id": str(data["id"]), "username": data["username"]}

    async def list_connections(self, user_id: str) -> list[OAuthConnection]:
        """List user's OAuth connections."""
        try:
            response = self.connections_table.query(
                IndexName="user-provider-index",
                KeyConditionExpression="user_id = :uid",
                FilterExpression="attribute_not_exists(#s) OR #s <> :pending",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":uid": user_id,
                    ":pending": "pending",
                },
            )

            connections = []
            for item in response.get("Items", []):
                connection_id = str(item.get("connection_id", ""))
                if connection_id.startswith("state:"):
                    continue  # Skip state entries
                # Extract scopes with proper type handling
                scopes_value = item.get("scopes")
                scopes_list: list[str] = []
                if scopes_value is not None:
                    if isinstance(scopes_value, list):
                        scopes_list = [str(s) for s in scopes_value]
                    elif isinstance(scopes_value, set):
                        scopes_list = [str(s) for s in scopes_value]
                connections.append(
                    OAuthConnection(
                        connection_id=connection_id,
                        user_id=str(item.get("user_id", "")),
                        provider=str(item.get("provider", "")),
                        provider_user_id=str(item.get("provider_user_id", "")),
                        provider_username=str(item.get("provider_username", "")),
                        scopes=scopes_list,
                        status=str(item.get("status", ConnectionStatus.ACTIVE.value)),
                        created_at=str(item.get("created_at", "")),
                        expires_at=(
                            str(item["expires_at"]) if item.get("expires_at") else None
                        ),
                    )
                )
            return connections
        except ClientError as e:
            logger.error(f"Error listing connections: {e}")
            return []

    async def revoke_connection(self, user_id: str, connection_id: str) -> None:
        """Revoke an OAuth connection."""
        # Verify ownership
        response = self.connections_table.get_item(Key={"connection_id": connection_id})
        item = response.get("Item")
        if not item or item.get("user_id") != user_id:
            raise ValueError("Connection not found or not authorized")

        # Delete secret from Secrets Manager
        secret_arn = item.get("secrets_arn")
        if secret_arn:
            try:
                self.secrets_client.delete_secret(
                    SecretId=secret_arn,
                    ForceDeleteWithoutRecovery=True,
                )
            except ClientError as e:
                logger.warning(f"Failed to delete secret: {e}")

        # Update connection status
        self.connections_table.update_item(
            Key={"connection_id": connection_id},
            UpdateExpression="SET #s = :status",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":status": ConnectionStatus.REVOKED.value},
        )

        logger.info(f"Revoked OAuth connection: {connection_id}")

    async def get_access_token(self, connection_id: str) -> str:
        """Get valid access token for a connection (refreshing if needed)."""
        response = self.connections_table.get_item(Key={"connection_id": connection_id})
        item = response.get("Item")
        if not item:
            raise ValueError("Connection not found")

        secret_arn_value = item.get("secrets_arn")
        if not secret_arn_value:
            raise ValueError("No token stored for connection")
        secret_arn: str = str(secret_arn_value)

        # Extract provider for potential token refresh
        provider: str = str(item.get("provider", ""))

        # Retrieve token from Secrets Manager
        try:
            secret_response = self.secrets_client.get_secret_value(SecretId=secret_arn)
            token_data = json.loads(secret_response["SecretString"])
        except ClientError as e:
            logger.error(f"Failed to retrieve token: {e}")
            raise

        # Check if token needs refresh
        expires_at = token_data.get("expires_at")
        if expires_at:
            expiry = datetime.fromisoformat(expires_at)
            if expiry < datetime.now(timezone.utc) + timedelta(minutes=5):
                # Refresh token
                refresh_token = token_data.get("refresh_token")
                if refresh_token:
                    new_tokens = await self._refresh_token(provider, refresh_token)
                    # Update stored token
                    self.secrets_client.put_secret_value(
                        SecretId=secret_arn,
                        SecretString=json.dumps(
                            {
                                "access_token": new_tokens.access_token,
                                "refresh_token": new_tokens.refresh_token
                                or refresh_token,
                                "token_type": new_tokens.token_type,
                                "scope": new_tokens.scope,
                                "expires_at": (
                                    new_tokens.expires_at.isoformat()
                                    if new_tokens.expires_at
                                    else None
                                ),
                            }
                        ),
                    )
                    return new_tokens.access_token

        access_token: str = str(token_data.get("access_token", ""))
        return access_token

    async def _refresh_token(self, provider: str, refresh_token: str) -> OAuthTokens:
        """Refresh an expired OAuth token."""
        if provider == OAuthProvider.GITHUB.value:
            # GitHub doesn't support token refresh in the standard way
            raise ValueError("GitHub tokens cannot be refreshed")
        else:  # GitLab
            response = requests.post(
                self.GITLAB_TOKEN_URL,
                data={
                    "client_id": self._gitlab_client_id,
                    "client_secret": self._gitlab_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            expires_at = None
            if "expires_in" in data:
                expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=data["expires_in"]
                )

            return OAuthTokens(
                access_token=data["access_token"],
                token_type=data.get("token_type", "bearer"),
                scope=data.get("scope", ""),
                refresh_token=data.get("refresh_token"),
                expires_at=expires_at,
            )

    async def list_repositories(self, connection_id: str) -> list[ProviderRepository]:
        """List repositories accessible via OAuth connection."""
        response = self.connections_table.get_item(Key={"connection_id": connection_id})
        item = response.get("Item")
        if not item:
            raise ValueError("Connection not found")

        access_token = await self.get_access_token(connection_id)
        provider = item["provider"]

        if provider == OAuthProvider.GITHUB.value:
            return await self._list_github_repos(access_token)
        else:  # GitLab
            return await self._list_gitlab_repos(access_token)

    async def _list_github_repos(self, access_token: str) -> list[ProviderRepository]:
        """List GitHub repositories for user."""
        repos = []
        page = 1
        per_page = 100

        while True:
            response = requests.get(
                f"{self.GITHUB_API_URL}/user/repos",
                params={
                    "per_page": str(per_page),
                    "page": str(page),
                    "sort": "updated",
                    "direction": "desc",
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                break

            for repo in data:
                repos.append(
                    ProviderRepository(
                        provider_repo_id=str(repo["id"]),
                        name=repo["name"],
                        full_name=repo["full_name"],
                        clone_url=repo["clone_url"],
                        default_branch=repo.get("default_branch", "main"),
                        private=repo["private"],
                        language=repo.get("language"),
                        size_kb=repo.get("size", 0),
                        updated_at=repo.get("updated_at", ""),
                    )
                )

            if len(data) < per_page:
                break
            page += 1

        return repos

    async def _list_gitlab_repos(self, access_token: str) -> list[ProviderRepository]:
        """List GitLab projects for user."""
        repos = []
        page = 1
        per_page = 100

        while True:
            response = requests.get(
                f"{self.GITLAB_API_URL}/projects",
                params={
                    "per_page": str(per_page),
                    "page": str(page),
                    "membership": "true",
                    "order_by": "updated_at",
                    "sort": "desc",
                },
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                break

            for project in data:
                repos.append(
                    ProviderRepository(
                        provider_repo_id=str(project["id"]),
                        name=project["name"],
                        full_name=project["path_with_namespace"],
                        clone_url=project.get("http_url_to_repo", ""),
                        default_branch=project.get("default_branch", "main"),
                        private=project.get("visibility") == "private",
                        language=None,  # GitLab doesn't provide this in list
                        size_kb=0,
                        updated_at=project.get("last_activity_at", ""),
                    )
                )

            if len(data) < per_page:
                break
            page += 1

        return repos


# Singleton instance
_oauth_service: OAuthProviderService | None = None


def get_oauth_service() -> OAuthProviderService:
    """Get or create OAuth service singleton."""
    global _oauth_service
    if _oauth_service is None:
        _oauth_service = OAuthProviderService()
    return _oauth_service
