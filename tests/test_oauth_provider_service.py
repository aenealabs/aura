"""
Tests for OAuth Provider Service.

Tests OAuth flow handling for GitHub and GitLab providers including:
- Authorization URL generation
- Token exchange
- Connection management
- Repository listing
- Token refresh

Part of ADR-043: Repository Onboarding Wizard
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.services.oauth_provider_service import (
    ConnectionStatus,
    OAuthConnection,
    OAuthProvider,
    OAuthProviderService,
    OAuthTokens,
    ProviderRepository,
    get_oauth_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_dynamodb():
    """Create a mock DynamoDB resource."""
    mock_resource = MagicMock()
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}
    mock_table.put_item.return_value = {}
    mock_table.query.return_value = {"Items": []}
    mock_table.delete_item.return_value = {}
    mock_table.update_item.return_value = {}
    mock_resource.Table.return_value = mock_table
    return mock_resource


@pytest.fixture
def mock_secrets_client():
    """Create a mock Secrets Manager client."""
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "token_type": "bearer",
                "scope": "repo",
                "expires_at": None,
            }
        )
    }
    mock_client.create_secret.return_value = {"ARN": "arn:aws:secretsmanager:test"}
    mock_client.delete_secret.return_value = {}
    return mock_client


@pytest.fixture
def service(mock_dynamodb, mock_secrets_client):
    """Create an OAuth provider service for testing."""
    with patch.dict(
        "os.environ",
        {
            "GITHUB_OAUTH_CLIENT_ID": "test_github_client_id",
            "GITHUB_OAUTH_CLIENT_SECRET": "test_github_client_secret",
            "GITLAB_OAUTH_CLIENT_ID": "test_gitlab_client_id",
            "GITLAB_OAUTH_CLIENT_SECRET": "test_gitlab_client_secret",
        },
    ):
        return OAuthProviderService(
            dynamodb_client=mock_dynamodb,
            secrets_client=mock_secrets_client,
            environment="test",
            project_name="test-aura",
        )


@pytest.fixture
def github_tokens():
    """Create sample GitHub tokens."""
    return OAuthTokens(
        access_token="gho_test_access_token",
        token_type="bearer",
        scope="repo,read:user",
        refresh_token=None,
        expires_at=None,
    )


@pytest.fixture
def gitlab_tokens():
    """Create sample GitLab tokens."""
    return OAuthTokens(
        access_token="glpat_test_access_token",
        token_type="bearer",
        scope="api read_user read_repository",
        refresh_token="glprt_test_refresh_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )


@pytest.fixture
def sample_connection():
    """Create a sample OAuth connection."""
    return OAuthConnection(
        connection_id="conn-12345",
        user_id="user-123",
        provider="github",
        provider_user_id="12345",
        provider_username="testuser",
        scopes=["repo", "read:user"],
        status="active",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# =============================================================================
# Service Initialization Tests
# =============================================================================


class TestServiceInitialization:
    """Test OAuth service initialization."""

    def test_default_initialization(self, mock_dynamodb, mock_secrets_client):
        """Test default initialization values."""
        with patch.dict("os.environ", {"ENVIRONMENT": "dev"}, clear=False):
            service = OAuthProviderService(
                dynamodb_client=mock_dynamodb,
                secrets_client=mock_secrets_client,
            )
            assert service.environment == "dev"
            assert service.project_name == "aura"
            assert service.dynamodb == mock_dynamodb
            assert service.secrets_client == mock_secrets_client

    def test_custom_initialization(self, service):
        """Test custom initialization."""
        assert service.environment == "test"
        assert service.project_name == "test-aura"

    def test_connections_table_name(self, service, mock_dynamodb):
        """Test that connections table is created with correct name."""
        mock_dynamodb.Table.assert_called_with("test-aura-oauth-connections-test")

    def test_singleton_pattern(self):
        """Test get_oauth_service singleton pattern."""
        try:
            service1 = get_oauth_service()
            service2 = get_oauth_service()
            assert service1 is service2
        except Exception:
            pytest.skip("AWS credentials not configured for singleton test")


# =============================================================================
# OAuth Initiation Tests
# =============================================================================


class TestOAuthInitiation:
    """Test OAuth flow initiation."""

    @pytest.mark.asyncio
    async def test_initiate_github_oauth(self, service):
        """Test initiating GitHub OAuth flow."""
        auth_url, state = await service.initiate_oauth(
            provider="github", user_id="user-123"
        )

        assert "github.com/login/oauth/authorize" in auth_url
        assert "client_id=test_github_client_id" in auth_url
        assert "state=" in auth_url
        assert len(state) == 64  # SHA256 hex length

    @pytest.mark.asyncio
    async def test_initiate_gitlab_oauth(self, service):
        """Test initiating GitLab OAuth flow."""
        auth_url, state = await service.initiate_oauth(
            provider="gitlab", user_id="user-123"
        )

        assert "gitlab.com/oauth/authorize" in auth_url
        assert "client_id=test_gitlab_client_id" in auth_url
        assert "response_type=code" in auth_url
        assert "state=" in auth_url

    @pytest.mark.asyncio
    async def test_initiate_oauth_invalid_provider(self, service):
        """Test that invalid provider raises error."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            await service.initiate_oauth(
                provider="invalid_provider", user_id="user-123"
            )

    @pytest.mark.asyncio
    async def test_state_is_stored(self, service, mock_dynamodb):
        """Test that state is stored in DynamoDB."""
        mock_table = mock_dynamodb.Table.return_value

        await service.initiate_oauth(provider="github", user_id="user-123")

        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args
        item = call_args.kwargs.get("Item") or call_args[1].get("Item")
        assert item["user_id"] == "user-123"
        assert item["provider"] == "github"
        assert item["status"] == "pending"


# =============================================================================
# OAuth Completion Tests
# =============================================================================


class TestOAuthCompletion:
    """Test OAuth flow completion."""

    @pytest.mark.asyncio
    async def test_complete_oauth_invalid_state(self, service, mock_dynamodb):
        """Test that invalid state raises error."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {}  # No state found

        with pytest.raises(ValueError, match="Invalid or expired state"):
            await service.complete_oauth(
                provider="github", code="test_code", state="invalid_state"
            )

    @pytest.mark.asyncio
    async def test_complete_oauth_github(
        self, service, mock_dynamodb, mock_secrets_client
    ):
        """Test completing GitHub OAuth flow."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "connection_id": "state:valid_state",
                "user_id": "user-123",
                "provider": "github",
                "status": "pending",
            }
        }

        with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
            # Mock token exchange
            mock_post.return_value.raise_for_status = MagicMock()
            mock_post.return_value.json.return_value = {
                "access_token": "gho_test_token",
                "token_type": "bearer",
                "scope": "repo",
            }

            # Mock user info
            mock_get.return_value.raise_for_status = MagicMock()
            mock_get.return_value.json.return_value = {
                "id": 12345,
                "login": "testuser",
            }

            connection = await service.complete_oauth(
                provider="github", code="test_code", state="valid_state"
            )

            assert connection.provider == "github"
            assert connection.provider_user_id == "12345"
            assert connection.provider_username == "testuser"
            assert connection.status == ConnectionStatus.ACTIVE.value

            # Verify secret was created
            mock_secrets_client.create_secret.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_oauth_gitlab(
        self, service, mock_dynamodb, mock_secrets_client
    ):
        """Test completing GitLab OAuth flow."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "connection_id": "state:valid_state",
                "user_id": "user-123",
                "provider": "gitlab",
                "status": "pending",
            }
        }

        with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
            # Mock token exchange
            mock_post.return_value.raise_for_status = MagicMock()
            mock_post.return_value.json.return_value = {
                "access_token": "glpat_test_token",
                "token_type": "bearer",
                "scope": "api",
                "refresh_token": "glprt_test_refresh",
                "expires_in": 7200,
            }

            # Mock user info
            mock_get.return_value.raise_for_status = MagicMock()
            mock_get.return_value.json.return_value = {
                "id": 67890,
                "username": "gitlabuser",
            }

            connection = await service.complete_oauth(
                provider="gitlab", code="test_code", state="valid_state"
            )

            assert connection.provider == "gitlab"
            assert connection.provider_user_id == "67890"
            assert connection.provider_username == "gitlabuser"


# =============================================================================
# Connection Management Tests
# =============================================================================


class TestConnectionManagement:
    """Test OAuth connection CRUD operations."""

    @pytest.mark.asyncio
    async def test_list_connections(self, service, mock_dynamodb, sample_connection):
        """Test listing user connections."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.query.return_value = {
            "Items": [
                {
                    "connection_id": sample_connection.connection_id,
                    "user_id": sample_connection.user_id,
                    "provider": sample_connection.provider,
                    "provider_user_id": sample_connection.provider_user_id,
                    "provider_username": sample_connection.provider_username,
                    "scopes": sample_connection.scopes,
                    "status": sample_connection.status,
                    "created_at": sample_connection.created_at,
                }
            ]
        }

        connections = await service.list_connections(user_id="user-123")

        assert len(connections) == 1
        assert connections[0].connection_id == sample_connection.connection_id
        assert connections[0].provider == "github"

    @pytest.mark.asyncio
    async def test_list_connections_empty(self, service, mock_dynamodb):
        """Test listing connections when none exist."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.query.return_value = {"Items": []}

        connections = await service.list_connections(user_id="user-123")

        assert connections == []

    @pytest.mark.asyncio
    async def test_list_connections_filters_state_entries(self, service, mock_dynamodb):
        """Test that state entries are filtered out."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.query.return_value = {
            "Items": [
                {"connection_id": "state:some_state", "user_id": "user-123"},
                {
                    "connection_id": "conn-123",
                    "user_id": "user-123",
                    "provider": "github",
                },
            ]
        }

        connections = await service.list_connections(user_id="user-123")

        assert len(connections) == 1
        assert connections[0].connection_id == "conn-123"

    @pytest.mark.asyncio
    async def test_revoke_connection(self, service, mock_dynamodb, mock_secrets_client):
        """Test revoking a connection."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "connection_id": "conn-123",
                "user_id": "user-123",
                "secrets_arn": "/test-aura/test/oauth/conn-123",
            }
        }

        await service.revoke_connection(user_id="user-123", connection_id="conn-123")

        # Verify secret was deleted
        mock_secrets_client.delete_secret.assert_called_once()

        # Verify connection was updated
        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args
        assert ":status" in str(call_args)

    @pytest.mark.asyncio
    async def test_revoke_connection_not_found(self, service, mock_dynamodb):
        """Test revoking non-existent connection."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {}

        with pytest.raises(ValueError, match="Connection not found"):
            await service.revoke_connection(user_id="user-123", connection_id="invalid")

    @pytest.mark.asyncio
    async def test_revoke_connection_wrong_user(self, service, mock_dynamodb):
        """Test revoking connection owned by different user."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {
            "Item": {"connection_id": "conn-123", "user_id": "other-user"}
        }

        with pytest.raises(ValueError, match="not authorized"):
            await service.revoke_connection(
                user_id="user-123", connection_id="conn-123"
            )


# =============================================================================
# Access Token Tests
# =============================================================================


class TestAccessToken:
    """Test access token retrieval and refresh."""

    @pytest.mark.asyncio
    async def test_get_access_token(self, service, mock_dynamodb, mock_secrets_client):
        """Test getting access token for connection."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "connection_id": "conn-123",
                "provider": "github",
                "secrets_arn": "/test-aura/test/oauth/conn-123",
            }
        }

        token = await service.get_access_token(connection_id="conn-123")

        assert token == "test_access_token"
        mock_secrets_client.get_secret_value.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_access_token_not_found(self, service, mock_dynamodb):
        """Test getting token for non-existent connection."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {}

        with pytest.raises(ValueError, match="Connection not found"):
            await service.get_access_token(connection_id="invalid")

    @pytest.mark.asyncio
    async def test_get_access_token_refreshes_expired(
        self, service, mock_dynamodb, mock_secrets_client
    ):
        """Test that expired tokens are refreshed."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "connection_id": "conn-123",
                "provider": "gitlab",
                "secrets_arn": "/test-aura/test/oauth/conn-123",
            }
        }

        # Token that's about to expire
        expired_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "access_token": "old_token",
                    "refresh_token": "refresh_token",
                    "expires_at": expired_time,
                }
            )
        }

        with patch("requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            mock_post.return_value.json.return_value = {
                "access_token": "new_token",
                "token_type": "bearer",
                "expires_in": 7200,
            }

            token = await service.get_access_token(connection_id="conn-123")

            assert token == "new_token"
            mock_secrets_client.put_secret_value.assert_called_once()


# =============================================================================
# Repository Listing Tests
# =============================================================================


class TestRepositoryListing:
    """Test repository listing functionality."""

    @pytest.mark.asyncio
    async def test_list_github_repositories(
        self, service, mock_dynamodb, mock_secrets_client
    ):
        """Test listing GitHub repositories."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "connection_id": "conn-123",
                "provider": "github",
                "secrets_arn": "/test-aura/test/oauth/conn-123",
            }
        }

        with patch("requests.get") as mock_get:
            mock_get.return_value.raise_for_status = MagicMock()
            mock_get.return_value.json.return_value = [
                {
                    "id": 1001,
                    "name": "test-repo",
                    "full_name": "testuser/test-repo",
                    "clone_url": "https://github.com/testuser/test-repo.git",
                    "default_branch": "main",
                    "private": False,
                    "language": "Python",
                    "size": 1024,
                    "updated_at": "2024-01-15T10:30:00Z",
                },
                {
                    "id": 1002,
                    "name": "private-repo",
                    "full_name": "testuser/private-repo",
                    "clone_url": "https://github.com/testuser/private-repo.git",
                    "default_branch": "develop",
                    "private": True,
                    "language": "TypeScript",
                    "size": 2048,
                    "updated_at": "2024-01-20T15:45:00Z",
                },
            ]

            repos = await service.list_repositories(connection_id="conn-123")

            assert len(repos) == 2
            assert repos[0].name == "test-repo"
            assert repos[0].private is False
            assert repos[1].name == "private-repo"
            assert repos[1].private is True

    @pytest.mark.asyncio
    async def test_list_gitlab_repositories(
        self, service, mock_dynamodb, mock_secrets_client
    ):
        """Test listing GitLab repositories."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "connection_id": "conn-123",
                "provider": "gitlab",
                "secrets_arn": "/test-aura/test/oauth/conn-123",
            }
        }

        with patch("requests.get") as mock_get:
            mock_get.return_value.raise_for_status = MagicMock()
            mock_get.return_value.json.return_value = [
                {
                    "id": 2001,
                    "name": "gitlab-project",
                    "path_with_namespace": "user/gitlab-project",
                    "http_url_to_repo": "https://gitlab.com/user/gitlab-project.git",
                    "default_branch": "main",
                    "visibility": "public",
                    "last_activity_at": "2024-01-18T12:00:00Z",
                },
            ]

            repos = await service.list_repositories(connection_id="conn-123")

            assert len(repos) == 1
            assert repos[0].name == "gitlab-project"
            assert repos[0].full_name == "user/gitlab-project"

    @pytest.mark.asyncio
    async def test_list_repositories_not_found(self, service, mock_dynamodb):
        """Test listing repos for non-existent connection."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {}

        with pytest.raises(ValueError, match="Connection not found"):
            await service.list_repositories(connection_id="invalid")


# =============================================================================
# Data Model Tests
# =============================================================================


class TestDataModels:
    """Test data model validation."""

    def test_oauth_tokens_model(self, github_tokens):
        """Test OAuthTokens model."""
        assert github_tokens.access_token.startswith("gho_")
        assert github_tokens.token_type == "bearer"
        assert github_tokens.scope == "repo,read:user"

    def test_oauth_tokens_with_expiry(self, gitlab_tokens):
        """Test OAuthTokens with expiry."""
        assert gitlab_tokens.refresh_token is not None
        assert gitlab_tokens.expires_at is not None
        assert gitlab_tokens.expires_at > datetime.now(timezone.utc)

    def test_oauth_connection_model(self, sample_connection):
        """Test OAuthConnection model."""
        assert sample_connection.connection_id.startswith("conn-")
        assert sample_connection.provider in ["github", "gitlab"]
        assert sample_connection.status == "active"
        assert len(sample_connection.scopes) > 0

    def test_provider_repository_model(self):
        """Test ProviderRepository model."""
        repo = ProviderRepository(
            provider_repo_id="123",
            name="test-repo",
            full_name="user/test-repo",
            private=False,
            clone_url="https://github.com/user/test-repo.git",
            default_branch="main",
            language="Python",
            size_kb=1024,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        assert repo.name == "test-repo"
        assert repo.private is False
        assert repo.default_branch == "main"

    def test_oauth_provider_enum(self):
        """Test OAuthProvider enum values."""
        assert OAuthProvider.GITHUB.value == "github"
        assert OAuthProvider.GITLAB.value == "gitlab"

    def test_connection_status_enum(self):
        """Test ConnectionStatus enum values."""
        assert ConnectionStatus.ACTIVE.value == "active"
        assert ConnectionStatus.REVOKED.value == "revoked"
        assert ConnectionStatus.EXPIRED.value == "expired"
        assert ConnectionStatus.ERROR.value == "error"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_github_oauth_error_response(self, service, mock_dynamodb):
        """Test handling of GitHub OAuth error."""
        mock_table = mock_dynamodb.Table.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "connection_id": "state:valid_state",
                "user_id": "user-123",
                "provider": "github",
                "status": "pending",
            }
        }

        with patch("requests.post") as mock_post:
            mock_post.return_value.raise_for_status = MagicMock()
            mock_post.return_value.json.return_value = {
                "error": "bad_verification_code",
                "error_description": "The code passed is incorrect or expired.",
            }

            with pytest.raises(ValueError, match="GitHub OAuth error"):
                await service.complete_oauth(
                    provider="github", code="invalid_code", state="valid_state"
                )

    @pytest.mark.asyncio
    async def test_gitlab_token_refresh_error(self, service):
        """Test that GitHub token refresh raises error."""
        with pytest.raises(ValueError, match="cannot be refreshed"):
            await service._refresh_token(
                provider="github", refresh_token="some_refresh_token"
            )
