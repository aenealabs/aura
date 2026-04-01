"""
Tests for Repository Onboard Service.

This module tests the RepositoryOnboardService which orchestrates
repository onboarding workflow including configuration, ingestion,
and status tracking.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.repository_onboard_service import (
    IngestionJob,
    IngestionJobStatus,
    Repository,
    RepositoryConfig,
    RepositoryOnboardService,
    RepositoryStatus,
    ScanFrequency,
    get_repository_service,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_repositories_table():
    """Create mock DynamoDB repositories table."""
    table = MagicMock()
    table.query.return_value = {"Items": []}
    table.get_item.return_value = {}
    table.put_item.return_value = {}
    table.update_item.return_value = {}
    table.delete_item.return_value = {}
    return table


@pytest.fixture
def mock_jobs_table():
    """Create mock DynamoDB jobs table."""
    table = MagicMock()
    table.get_item.return_value = {}
    table.put_item.return_value = {}
    table.update_item.return_value = {}
    return table


@pytest.fixture
def mock_dynamodb(mock_repositories_table, mock_jobs_table):
    """Create mock DynamoDB resource."""
    dynamodb = MagicMock()

    def get_table(name):
        if "repositories" in name:
            return mock_repositories_table
        elif "ingestion-jobs" in name:
            mock_jobs_table.table_name = name
            return mock_jobs_table
        return MagicMock()

    dynamodb.Table.side_effect = get_table

    # Default batch_get_item returns empty responses
    dynamodb.batch_get_item.return_value = {
        "Responses": {},
        "UnprocessedKeys": {},
    }

    return dynamodb


@pytest.fixture
def mock_secrets_client():
    """Create mock Secrets Manager client."""
    client = MagicMock()
    client.create_secret.return_value = {
        "ARN": "arn:aws:secretsmanager:us-east-1:123456789:secret:test"
    }
    client.get_secret_value.return_value = {"SecretString": '{"token": "test-token"}'}
    client.delete_secret.return_value = {}
    return client


@pytest.fixture
def mock_oauth_service():
    """Create mock OAuth provider service."""
    oauth = MagicMock()
    oauth.list_connections = AsyncMock(return_value=[])
    oauth.list_repositories = AsyncMock(return_value=[])
    return oauth


@pytest.fixture
def service(mock_dynamodb, mock_secrets_client, mock_oauth_service):
    """Create a repository onboard service for testing."""
    return RepositoryOnboardService(
        dynamodb_client=mock_dynamodb,
        secrets_client=mock_secrets_client,
        oauth_service=mock_oauth_service,
        environment="test",
        project_name="test-aura",
    )


@pytest.fixture
def sample_repository_item():
    """Create sample repository DynamoDB item."""
    return {
        "repository_id": "repo-123",
        "user_id": "user-123",
        "name": "test-repo",
        "provider": "github",
        "clone_url": "https://github.com/org/test-repo.git",
        "branch": "main",
        "languages": ["python"],
        "scan_frequency": "on_push",
        "status": "active",
        "exclude_patterns": [],
        "webhook_id": "webhook-123",
        "last_ingestion_at": "2025-01-01T00:00:00",
        "last_ingestion_job_id": "job-123",
        "file_count": 100,
        "entity_count": 500,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    }


@pytest.fixture
def sample_job_item():
    """Create sample ingestion job DynamoDB item."""
    return {
        "job_id": "job-123",
        "repository_id": "repo-123",
        "user_id": "user-123",
        "status": "completed",
        "progress": 100,
        "files_processed": 50,
        "entities_indexed": 200,
        "embeddings_generated": 150,
        "current_stage": "completed",
        "started_at": "2025-01-01T00:00:00",
        "completed_at": "2025-01-01T01:00:00",
        "created_at": "2025-01-01T00:00:00",
    }


# ============================================================================
# Service Initialization Tests
# ============================================================================


class TestServiceInitialization:
    """Tests for service initialization."""

    def test_creates_service_with_defaults(self, mock_dynamodb, mock_secrets_client):
        """Test creating service with default environment."""
        with patch.dict("os.environ", {"ENVIRONMENT": "dev"}):
            with patch(
                "src.services.repository_onboard_service.get_oauth_service"
            ) as mock_get_oauth:
                mock_get_oauth.return_value = MagicMock()
                service = RepositoryOnboardService(
                    dynamodb_client=mock_dynamodb,
                    secrets_client=mock_secrets_client,
                )
                assert service.environment == "dev"
                assert service.project_name == "aura"

    def test_creates_service_with_custom_environment(
        self, mock_dynamodb, mock_secrets_client, mock_oauth_service
    ):
        """Test creating service with custom environment."""
        service = RepositoryOnboardService(
            dynamodb_client=mock_dynamodb,
            secrets_client=mock_secrets_client,
            oauth_service=mock_oauth_service,
            environment="staging",
            project_name="custom-project",
        )
        assert service.environment == "staging"
        assert service.project_name == "custom-project"

    def test_creates_tables_with_correct_names(
        self, mock_dynamodb, mock_secrets_client, mock_oauth_service
    ):
        """Test table names are constructed correctly."""
        _service = RepositoryOnboardService(
            dynamodb_client=mock_dynamodb,
            secrets_client=mock_secrets_client,
            oauth_service=mock_oauth_service,
            environment="test",
            project_name="aura",
        )

        calls = mock_dynamodb.Table.call_args_list
        table_names = [call[0][0] for call in calls]
        assert "aura-repositories-test" in table_names
        assert "aura-ingestion-jobs-test" in table_names


# ============================================================================
# Repository Listing Tests
# ============================================================================


class TestListRepositories:
    """Tests for listing repositories."""

    @pytest.mark.asyncio
    async def test_list_repositories_empty(self, service, mock_repositories_table):
        """Test listing repositories when none exist."""
        mock_repositories_table.query.return_value = {"Items": []}

        result = await service.list_repositories("user-123")

        assert result == []
        mock_repositories_table.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_repositories_returns_all(
        self, service, mock_repositories_table, sample_repository_item
    ):
        """Test listing repositories returns all user repositories."""
        mock_repositories_table.query.return_value = {"Items": [sample_repository_item]}

        result = await service.list_repositories("user-123")

        assert len(result) == 1
        assert result[0].repository_id == "repo-123"
        assert result[0].name == "test-repo"
        assert result[0].provider == "github"

    @pytest.mark.asyncio
    async def test_list_repositories_uses_user_index(
        self, service, mock_repositories_table
    ):
        """Test that listing uses the user-index GSI."""
        mock_repositories_table.query.return_value = {"Items": []}

        await service.list_repositories("user-456")

        call_kwargs = mock_repositories_table.query.call_args[1]
        assert call_kwargs["IndexName"] == "user-index"
        assert ":uid" in call_kwargs["ExpressionAttributeValues"]

    @pytest.mark.asyncio
    async def test_list_repositories_handles_error(
        self, service, mock_repositories_table
    ):
        """Test listing handles DynamoDB errors gracefully."""
        from botocore.exceptions import ClientError

        mock_repositories_table.query.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal error"}}, "Query"
        )

        result = await service.list_repositories("user-123")

        assert result == []


# ============================================================================
# Add Repository Tests
# ============================================================================


class TestAddRepository:
    """Tests for adding repositories."""

    @pytest.mark.asyncio
    async def test_add_manual_repository(
        self, service, mock_repositories_table, mock_secrets_client
    ):
        """Test adding a repository with manual URL and token."""
        config = RepositoryConfig(
            clone_url="https://github.com/org/repo.git",
            token="github_token_123",
            name="my-repo",
            branch="develop",
            languages=["python", "javascript"],
            scan_frequency="daily",
        )

        with patch(
            "src.services.repository_onboard_service.secrets.token_urlsafe"
        ) as mock_token:
            mock_token.return_value = "generated-repo-id"
            result = await service.add_repository("user-123", config)

        assert result.repository_id == "generated-repo-id"
        assert result.name == "my-repo"
        assert result.branch == "develop"
        assert result.provider == "manual"
        mock_secrets_client.create_secret.assert_called_once()
        mock_repositories_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_repository_without_token(
        self, service, mock_repositories_table, mock_secrets_client
    ):
        """Test adding a repository without token (public repo)."""
        config = RepositoryConfig(
            clone_url="https://github.com/org/public-repo.git",
            name="public-repo",
        )

        result = await service.add_repository("user-123", config)

        assert result.provider == "manual"
        mock_secrets_client.create_secret.assert_not_called()
        mock_repositories_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_repository_extracts_name_from_url(
        self, service, mock_repositories_table
    ):
        """Test that name is extracted from clone URL if not provided."""
        config = RepositoryConfig(
            clone_url="https://github.com/org/extracted-name.git",
        )

        result = await service.add_repository("user-123", config)

        assert result.name == "extracted-name"


# ============================================================================
# Add Repositories From Connection Tests
# ============================================================================


class TestAddRepositoriesFromConnection:
    """Tests for adding repositories from OAuth connection."""

    @pytest.mark.asyncio
    async def test_add_from_connection_success(
        self, service, mock_repositories_table, mock_oauth_service
    ):
        """Test adding repositories from an OAuth connection."""
        from src.services.oauth_provider_service import OAuthConnection

        # Mock connection exists
        mock_connection = OAuthConnection(
            connection_id="conn-123",
            user_id="user-123",
            provider="github",
            provider_user_id="12345",
            provider_username="testuser",
            scopes=["repo", "read:user"],
            status="active",
            created_at="2025-01-01T00:00:00",
        )
        mock_oauth_service.list_connections.return_value = [mock_connection]

        configs = [
            RepositoryConfig(
                provider_repo_id="github-repo-1",
                clone_url="https://github.com/org/repo1.git",
                name="repo1",
            ),
            RepositoryConfig(
                provider_repo_id="github-repo-2",
                clone_url="https://github.com/org/repo2.git",
                name="repo2",
            ),
        ]

        result = await service.add_repositories_from_connection(
            "user-123", "conn-123", configs
        )

        assert len(result) == 2
        assert result[0].provider == "github"
        assert result[1].provider == "github"

    @pytest.mark.asyncio
    async def test_add_from_connection_not_found(self, service, mock_oauth_service):
        """Test error when connection not found."""
        mock_oauth_service.list_connections.return_value = []

        configs = [
            RepositoryConfig(
                provider_repo_id="repo-1",
                clone_url="https://github.com/org/repo.git",
                name="repo",
            )
        ]

        with pytest.raises(ValueError, match="Connection not found"):
            await service.add_repositories_from_connection(
                "user-123", "invalid-conn", configs
            )


# ============================================================================
# Get Repository Tests
# ============================================================================


class TestGetRepository:
    """Tests for getting repository details."""

    @pytest.mark.asyncio
    async def test_get_repository_success(
        self, service, mock_repositories_table, sample_repository_item
    ):
        """Test getting repository by ID."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        result = await service.get_repository("user-123", "repo-123")

        assert result is not None
        assert result.repository_id == "repo-123"
        assert result.name == "test-repo"
        assert result.file_count == 100
        assert result.entity_count == 500

    @pytest.mark.asyncio
    async def test_get_repository_not_found(self, service, mock_repositories_table):
        """Test getting non-existent repository returns None."""
        mock_repositories_table.get_item.return_value = {}

        result = await service.get_repository("user-123", "not-found")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_repository_wrong_user(
        self, service, mock_repositories_table, sample_repository_item
    ):
        """Test repository not returned if user doesn't match."""
        sample_repository_item["user_id"] = "other-user"
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        result = await service.get_repository("user-123", "repo-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_repository_handles_error(self, service, mock_repositories_table):
        """Test get repository handles DynamoDB errors."""
        from botocore.exceptions import ClientError

        mock_repositories_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal error"}}, "GetItem"
        )

        result = await service.get_repository("user-123", "repo-123")

        assert result is None


# ============================================================================
# Update Repository Tests
# ============================================================================


class TestUpdateRepository:
    """Tests for updating repository settings."""

    @pytest.mark.asyncio
    async def test_update_repository_success(
        self, service, mock_repositories_table, sample_repository_item
    ):
        """Test updating repository settings."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        config = RepositoryConfig(
            branch="feature-branch",
            languages=["python", "go"],
            scan_frequency="weekly",
            exclude_patterns=["*.log", "node_modules/"],
        )

        result = await service.update_repository("user-123", "repo-123", config)

        assert result.branch == "feature-branch"
        assert result.languages == ["python", "go"]
        assert result.scan_frequency == "weekly"
        mock_repositories_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_repository_not_found(self, service, mock_repositories_table):
        """Test updating non-existent repository raises error."""
        mock_repositories_table.get_item.return_value = {}

        config = RepositoryConfig(branch="develop")

        with pytest.raises(ValueError, match="Repository not found"):
            await service.update_repository("user-123", "not-found", config)


# ============================================================================
# Delete Repository Tests
# ============================================================================


class TestDeleteRepository:
    """Tests for deleting repositories."""

    @pytest.mark.asyncio
    async def test_delete_repository_success(
        self,
        service,
        mock_repositories_table,
        mock_secrets_client,
        sample_repository_item,
    ):
        """Test deleting a repository."""
        sample_repository_item["secrets_arn"] = "/aura/test/repos/repo-123/token"
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        await service.delete_repository("user-123", "repo-123")

        mock_secrets_client.delete_secret.assert_called_once()
        mock_repositories_table.delete_item.assert_called_once_with(
            Key={"repository_id": "repo-123"}
        )

    @pytest.mark.asyncio
    async def test_delete_repository_without_secret(
        self,
        service,
        mock_repositories_table,
        mock_secrets_client,
        sample_repository_item,
    ):
        """Test deleting a repository that has no stored secret."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        await service.delete_repository("user-123", "repo-123")

        mock_secrets_client.delete_secret.assert_not_called()
        mock_repositories_table.delete_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_repository_not_found(self, service, mock_repositories_table):
        """Test deleting non-existent repository raises error."""
        mock_repositories_table.get_item.return_value = {}

        with pytest.raises(ValueError, match="Repository not found"):
            await service.delete_repository("user-123", "not-found")


# ============================================================================
# Start Ingestion Tests
# ============================================================================


class TestStartIngestion:
    """Tests for starting ingestion jobs."""

    @pytest.mark.asyncio
    async def test_start_ingestion_success(
        self, service, mock_repositories_table, mock_jobs_table, sample_repository_item
    ):
        """Test starting ingestion creates job."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        configs = [
            RepositoryConfig(repository_id="repo-123"),
        ]

        with patch(
            "src.services.repository_onboard_service.secrets.token_urlsafe"
        ) as mock_token:
            mock_token.return_value = "job-new-123"
            result = await service.start_ingestion("user-123", configs)

        assert len(result) == 1
        assert result[0].job_id == "job-new-123"
        assert result[0].status == IngestionJobStatus.PENDING.value
        mock_jobs_table.put_item.assert_called_once()
        mock_repositories_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_ingestion_multiple_repos(
        self, service, mock_repositories_table, mock_jobs_table, sample_repository_item
    ):
        """Test starting ingestion for multiple repositories."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        configs = [
            RepositoryConfig(repository_id="repo-1"),
            RepositoryConfig(repository_id="repo-2"),
        ]

        result = await service.start_ingestion("user-123", configs)

        assert len(result) == 2
        assert mock_jobs_table.put_item.call_count == 2

    @pytest.mark.asyncio
    async def test_start_ingestion_skips_missing_repo(
        self, service, mock_repositories_table, mock_jobs_table
    ):
        """Test ingestion skips repositories not found."""
        mock_repositories_table.get_item.return_value = {}

        configs = [
            RepositoryConfig(repository_id="not-found"),
        ]

        result = await service.start_ingestion("user-123", configs)

        assert len(result) == 0
        mock_jobs_table.put_item.assert_not_called()


# ============================================================================
# Get Ingestion Status Tests
# ============================================================================


class TestGetIngestionStatus:
    """Tests for getting ingestion job status."""

    @pytest.mark.asyncio
    async def test_get_status_single_job(
        self, service, mock_dynamodb, mock_jobs_table, sample_job_item
    ):
        """Test getting status of a single job."""
        # Mock batch_get_item response
        mock_dynamodb.batch_get_item.return_value = {
            "Responses": {mock_jobs_table.table_name: [sample_job_item]},
            "UnprocessedKeys": {},
        }

        result = await service.get_ingestion_status("user-123", ["job-123"])

        assert len(result) == 1
        assert result[0].job_id == "job-123"
        assert result[0].status == "completed"
        assert result[0].progress == 100
        assert result[0].files_processed == 50

    @pytest.mark.asyncio
    async def test_get_status_multiple_jobs(
        self, service, mock_dynamodb, mock_jobs_table, sample_job_item
    ):
        """Test getting status of multiple jobs."""
        # Create two job items
        job1 = {**sample_job_item, "job_id": "job-1"}
        job2 = {**sample_job_item, "job_id": "job-2"}

        mock_dynamodb.batch_get_item.return_value = {
            "Responses": {mock_jobs_table.table_name: [job1, job2]},
            "UnprocessedKeys": {},
        }

        result = await service.get_ingestion_status("user-123", ["job-1", "job-2"])

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_status_filters_by_user(
        self, service, mock_dynamodb, mock_jobs_table, sample_job_item
    ):
        """Test status filters out jobs from other users."""
        sample_job_item["user_id"] = "other-user"
        mock_dynamodb.batch_get_item.return_value = {
            "Responses": {mock_jobs_table.table_name: [sample_job_item]},
            "UnprocessedKeys": {},
        }

        result = await service.get_ingestion_status("user-123", ["job-123"])

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, service, mock_dynamodb, mock_jobs_table):
        """Test getting status of non-existent job."""
        mock_dynamodb.batch_get_item.return_value = {
            "Responses": {mock_jobs_table.table_name: []},
            "UnprocessedKeys": {},
        }

        result = await service.get_ingestion_status("user-123", ["not-found"])

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_status_empty_job_ids(self, service):
        """Test getting status with empty job_ids list."""
        result = await service.get_ingestion_status("user-123", [])

        assert len(result) == 0


# ============================================================================
# Cancel Ingestion Tests
# ============================================================================


class TestCancelIngestion:
    """Tests for cancelling ingestion jobs."""

    @pytest.mark.asyncio
    async def test_cancel_ingestion_success(
        self, service, mock_jobs_table, mock_repositories_table, sample_job_item
    ):
        """Test cancelling an in-progress job."""
        sample_job_item["status"] = IngestionJobStatus.CLONING.value
        mock_jobs_table.get_item.return_value = {"Item": sample_job_item}

        await service.cancel_ingestion("user-123", "job-123")

        mock_jobs_table.update_item.assert_called_once()
        mock_repositories_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_ingestion_not_found(self, service, mock_jobs_table):
        """Test cancelling non-existent job raises error."""
        mock_jobs_table.get_item.return_value = {}

        with pytest.raises(ValueError, match="Job not found"):
            await service.cancel_ingestion("user-123", "not-found")

    @pytest.mark.asyncio
    async def test_cancel_ingestion_wrong_user(
        self, service, mock_jobs_table, sample_job_item
    ):
        """Test cancelling job from different user raises error."""
        sample_job_item["user_id"] = "other-user"
        sample_job_item["status"] = IngestionJobStatus.CLONING.value
        mock_jobs_table.get_item.return_value = {"Item": sample_job_item}

        with pytest.raises(ValueError, match="Job not found"):
            await service.cancel_ingestion("user-123", "job-123")

    @pytest.mark.asyncio
    async def test_cancel_completed_job_raises_error(
        self, service, mock_jobs_table, sample_job_item
    ):
        """Test cancelling already completed job raises error."""
        sample_job_item["status"] = IngestionJobStatus.COMPLETED.value
        mock_jobs_table.get_item.return_value = {"Item": sample_job_item}

        with pytest.raises(ValueError, match="already completed"):
            await service.cancel_ingestion("user-123", "job-123")

    @pytest.mark.asyncio
    async def test_cancel_failed_job_raises_error(
        self, service, mock_jobs_table, sample_job_item
    ):
        """Test cancelling failed job raises error."""
        sample_job_item["status"] = IngestionJobStatus.FAILED.value
        mock_jobs_table.get_item.return_value = {"Item": sample_job_item}

        with pytest.raises(ValueError, match="already completed"):
            await service.cancel_ingestion("user-123", "job-123")


# ============================================================================
# Update Job Progress Tests
# ============================================================================


class TestUpdateJobProgress:
    """Tests for updating job progress."""

    @pytest.mark.asyncio
    async def test_update_progress_basic(self, service, mock_jobs_table):
        """Test updating job progress."""
        await service.update_job_progress(
            job_id="job-123",
            status=IngestionJobStatus.PARSING.value,
            progress=50,
            files_processed=25,
            entities_indexed=100,
        )

        mock_jobs_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_progress_with_stage(self, service, mock_jobs_table):
        """Test updating progress includes current stage."""
        await service.update_job_progress(
            job_id="job-123",
            status=IngestionJobStatus.INDEXING_GRAPH.value,
            progress=75,
            current_stage="indexing_graph",
        )

        call_kwargs = mock_jobs_table.update_item.call_args[1]
        assert ":stage" in call_kwargs["ExpressionAttributeValues"]

    @pytest.mark.asyncio
    async def test_update_progress_completed_updates_repository(
        self, service, mock_jobs_table, mock_repositories_table, sample_job_item
    ):
        """Test completing job updates repository stats."""
        mock_jobs_table.get_item.return_value = {"Item": sample_job_item}

        await service.update_job_progress(
            job_id="job-123",
            status=IngestionJobStatus.COMPLETED.value,
            progress=100,
            files_processed=100,
            entities_indexed=500,
            embeddings_generated=300,
        )

        assert mock_repositories_table.update_item.call_count == 1

    @pytest.mark.asyncio
    async def test_update_progress_with_error(self, service, mock_jobs_table):
        """Test updating progress with error message."""
        await service.update_job_progress(
            job_id="job-123",
            status=IngestionJobStatus.FAILED.value,
            progress=25,
            error_message="Clone failed: authentication error",
        )

        call_kwargs = mock_jobs_table.update_item.call_args[1]
        assert ":error" in call_kwargs["ExpressionAttributeValues"]


# ============================================================================
# List Available Repositories Tests
# ============================================================================


class TestListAvailableRepositories:
    """Tests for listing available repositories from OAuth provider."""

    @pytest.mark.asyncio
    async def test_list_available_success(self, service, mock_oauth_service):
        """Test listing available repositories from connection."""
        from src.services.oauth_provider_service import (
            OAuthConnection,
            ProviderRepository,
        )

        mock_connection = OAuthConnection(
            connection_id="conn-123",
            user_id="user-123",
            provider="github",
            provider_user_id="12345",
            provider_username="testuser",
            scopes=["repo", "read:user"],
            status="active",
            created_at="2025-01-01T00:00:00",
        )
        mock_oauth_service.list_connections.return_value = [mock_connection]

        mock_repos = [
            ProviderRepository(
                provider_repo_id="repo-1",
                name="test-repo",
                full_name="org/test-repo",
                clone_url="https://github.com/org/test-repo.git",
                default_branch="main",
                language="python",
                private=False,
                size_kb=1024,
                updated_at="2025-01-01T00:00:00",
            )
        ]
        mock_oauth_service.list_repositories.return_value = mock_repos

        result = await service.list_available_repositories("user-123", "conn-123")

        assert len(result) == 1
        assert result[0].name == "test-repo"

    @pytest.mark.asyncio
    async def test_list_available_connection_not_found(
        self, service, mock_oauth_service
    ):
        """Test error when connection not owned by user."""
        mock_oauth_service.list_connections.return_value = []

        with pytest.raises(ValueError, match="Connection not found"):
            await service.list_available_repositories("user-123", "invalid-conn")


# ============================================================================
# Data Model Tests
# ============================================================================


class TestDataModels:
    """Tests for data models and enums."""

    def test_repository_status_values(self):
        """Test RepositoryStatus enum values."""
        assert RepositoryStatus.PENDING.value == "pending"
        assert RepositoryStatus.ACTIVE.value == "active"
        assert RepositoryStatus.SYNCING.value == "syncing"
        assert RepositoryStatus.ERROR.value == "error"
        assert RepositoryStatus.ARCHIVED.value == "archived"

    def test_ingestion_job_status_values(self):
        """Test IngestionJobStatus enum values."""
        assert IngestionJobStatus.PENDING.value == "pending"
        assert IngestionJobStatus.CLONING.value == "cloning"
        assert IngestionJobStatus.PARSING.value == "parsing"
        assert IngestionJobStatus.INDEXING_GRAPH.value == "indexing_graph"
        assert IngestionJobStatus.INDEXING_VECTORS.value == "indexing_vectors"
        assert IngestionJobStatus.COMPLETED.value == "completed"
        assert IngestionJobStatus.FAILED.value == "failed"
        assert IngestionJobStatus.CANCELLED.value == "cancelled"

    def test_scan_frequency_values(self):
        """Test ScanFrequency enum values."""
        assert ScanFrequency.ON_PUSH.value == "on_push"
        assert ScanFrequency.DAILY.value == "daily"
        assert ScanFrequency.WEEKLY.value == "weekly"
        assert ScanFrequency.MANUAL.value == "manual"

    def test_repository_config_defaults(self):
        """Test RepositoryConfig has correct defaults."""
        config = RepositoryConfig()
        assert config.branch == "main"
        assert config.languages == ["python", "javascript", "typescript"]
        assert config.scan_frequency == "on_push"
        assert config.exclude_patterns == []
        assert config.enable_webhook is True

    def test_repository_dataclass(self):
        """Test Repository dataclass."""
        repo = Repository(
            repository_id="repo-123",
            user_id="user-123",
            name="test-repo",
            provider="github",
            clone_url="https://github.com/org/repo.git",
            branch="main",
            languages=["python"],
            scan_frequency="on_push",
            status="active",
            exclude_patterns=[],
        )
        assert repo.repository_id == "repo-123"
        assert repo.file_count == 0
        assert repo.entity_count == 0

    def test_ingestion_job_dataclass(self):
        """Test IngestionJob dataclass."""
        job = IngestionJob(
            job_id="job-123",
            repository_id="repo-123",
            user_id="user-123",
            status="pending",
        )
        assert job.job_id == "job-123"
        assert job.progress == 0
        assert job.files_processed == 0
        assert job.current_stage == "pending"


# ============================================================================
# Singleton Tests
# ============================================================================


class TestSingleton:
    """Tests for singleton instance."""

    def test_get_repository_service_singleton(self):
        """Test singleton returns same instance."""
        import src.services.repository_onboard_service as module

        # Clear singleton state
        module._repository_service = None

        # Mock boto3 clients that are created during singleton initialization
        mock_dynamodb = MagicMock()
        mock_secrets_client = MagicMock()
        mock_oauth_service = MagicMock()

        with (
            patch(
                "src.services.repository_onboard_service.boto3.resource",
                return_value=mock_dynamodb,
            ),
            patch(
                "src.services.repository_onboard_service.boto3.client",
                return_value=mock_secrets_client,
            ),
            patch(
                "src.services.repository_onboard_service.get_oauth_service",
                return_value=mock_oauth_service,
            ),
        ):

            service1 = get_repository_service()
            service2 = get_repository_service()

            assert service1 is service2

        # Clean up singleton state for other tests
        module._repository_service = None


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_add_repository_secret_creation_fails(
        self, service, mock_secrets_client
    ):
        """Test error when secret creation fails."""
        from botocore.exceptions import ClientError

        mock_secrets_client.create_secret.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "CreateSecret",
        )

        config = RepositoryConfig(
            clone_url="https://github.com/org/repo.git",
            token="test-token",
        )

        with pytest.raises(ClientError):
            await service.add_repository("user-123", config)

    @pytest.mark.asyncio
    async def test_delete_repository_secret_deletion_continues(
        self,
        service,
        mock_repositories_table,
        mock_secrets_client,
        sample_repository_item,
    ):
        """Test that secret deletion failure doesn't prevent repo deletion."""
        from botocore.exceptions import ClientError

        sample_repository_item["secrets_arn"] = "/test/secret"
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}
        mock_secrets_client.delete_secret.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "DeleteSecret",
        )

        # Should not raise
        await service.delete_repository("user-123", "repo-123")

        mock_repositories_table.delete_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_ingestion_status_handles_error(self, service, mock_dynamodb):
        """Test get status handles DynamoDB errors gracefully."""
        from botocore.exceptions import ClientError

        mock_dynamodb.batch_get_item.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal error"}}, "BatchGetItem"
        )

        result = await service.get_ingestion_status("user-123", ["job-123"])

        # Should return empty list, not raise
        assert result == []
