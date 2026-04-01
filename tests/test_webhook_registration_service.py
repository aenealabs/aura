"""
Tests for Webhook Registration Service.

This module tests the WebhookRegistrationService which manages
webhook registration on GitHub and GitLab repositories for
incremental code updates.
"""

import hashlib
import hmac
from unittest.mock import MagicMock, patch

import pytest

from src.services.webhook_registration_service import (
    WebhookConfig,
    WebhookInfo,
    WebhookRegistration,
    WebhookRegistrationService,
    WebhookStatus,
    get_webhook_service,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_repositories_table():
    """Create mock DynamoDB repositories table."""
    table = MagicMock()
    table.get_item.return_value = {}
    table.put_item.return_value = {}
    table.update_item.return_value = {}
    table.delete_item.return_value = {}
    return table


@pytest.fixture
def mock_dynamodb(mock_repositories_table):
    """Create mock DynamoDB resource."""
    dynamodb = MagicMock()
    dynamodb.Table.return_value = mock_repositories_table
    return dynamodb


@pytest.fixture
def mock_secrets_client():
    """Create mock Secrets Manager client."""
    client = MagicMock()
    client.create_secret.return_value = {
        "ARN": "arn:aws:secretsmanager:us-east-1:123456789:secret:test"
    }
    client.get_secret_value.return_value = {
        "SecretString": '{"secret": "test-webhook-secret"}'
    }
    client.put_secret_value.return_value = {}
    client.delete_secret.return_value = {}
    return client


@pytest.fixture
def service(mock_dynamodb, mock_secrets_client):
    """Create a webhook registration service for testing."""
    return WebhookRegistrationService(
        dynamodb_client=mock_dynamodb,
        secrets_client=mock_secrets_client,
        environment="test",
        project_name="test-aura",
    )


@pytest.fixture
def sample_repository_item():
    """Create sample repository DynamoDB item with webhook info."""
    return {
        "repository_id": "repo-123",
        "user_id": "user-123",
        "name": "test-repo",
        "provider": "github",
        "webhook_id": "12345678",
        "webhook_secret_arn": "/test-aura/test/webhooks/repo-123",
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    }


# ============================================================================
# Service Initialization Tests
# ============================================================================


class TestServiceInitialization:
    """Tests for service initialization."""

    def test_creates_service_with_defaults(self, mock_dynamodb, mock_secrets_client):
        """Test creating service with default environment."""
        with patch.dict("os.environ", {"ENVIRONMENT": "dev"}):
            service = WebhookRegistrationService(
                dynamodb_client=mock_dynamodb,
                secrets_client=mock_secrets_client,
            )
            assert service.environment == "dev"
            assert service.project_name == "aura"

    def test_creates_service_with_custom_environment(
        self, mock_dynamodb, mock_secrets_client
    ):
        """Test creating service with custom environment."""
        service = WebhookRegistrationService(
            dynamodb_client=mock_dynamodb,
            secrets_client=mock_secrets_client,
            environment="staging",
            project_name="custom-project",
        )
        assert service.environment == "staging"
        assert service.project_name == "custom-project"

    def test_creates_table_with_correct_name(self, mock_dynamodb, mock_secrets_client):
        """Test table name is constructed correctly."""
        _service = WebhookRegistrationService(
            dynamodb_client=mock_dynamodb,
            secrets_client=mock_secrets_client,
            environment="test",
            project_name="aura",
        )

        mock_dynamodb.Table.assert_called_with("aura-repositories-test")

    def test_has_api_urls(self, service):
        """Test service has correct API URLs."""
        assert service.GITHUB_API_URL == "https://api.github.com"
        assert service.GITLAB_API_URL == "https://gitlab.com/api/v4"


# ============================================================================
# Webhook Registration Tests - GitHub
# ============================================================================


class TestGitHubWebhookRegistration:
    """Tests for GitHub webhook registration."""

    @pytest.mark.asyncio
    async def test_register_webhook_success(
        self, service, mock_repositories_table, mock_secrets_client
    ):
        """Test registering a webhook on GitHub."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 12345678}

        with patch(
            "src.services.webhook_registration_service.requests.post"
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await service.register_webhook(
                repository_id="repo-123",
                provider="github",
                repo_full_name="org/test-repo",
                access_token="gho_test_token",
                events=["push", "pull_request"],
            )

            assert result.webhook_id == "12345678"
            assert result.provider == "github"
            assert result.repository_id == "repo-123"
            assert result.active is True
            assert "push" in result.events

    @pytest.mark.asyncio
    async def test_register_webhook_stores_secret(self, service, mock_secrets_client):
        """Test webhook secret is stored in Secrets Manager."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 12345678}

        with patch(
            "src.services.webhook_registration_service.requests.post"
        ) as mock_post:
            mock_post.return_value = mock_response

            await service.register_webhook(
                repository_id="repo-123",
                provider="github",
                repo_full_name="org/test-repo",
                access_token="gho_test_token",
            )

            mock_secrets_client.create_secret.assert_called_once()
            call_kwargs = mock_secrets_client.create_secret.call_args[1]
            assert "secret" in call_kwargs["SecretString"]

    @pytest.mark.asyncio
    async def test_register_webhook_updates_existing_secret(
        self, service, mock_secrets_client
    ):
        """Test updating existing webhook secret."""
        from botocore.exceptions import ClientError

        mock_secrets_client.create_secret.side_effect = ClientError(
            {"Error": {"Code": "ResourceExistsException", "Message": "Secret exists"}},
            "CreateSecret",
        )

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 12345678}

        with patch(
            "src.services.webhook_registration_service.requests.post"
        ) as mock_post:
            mock_post.return_value = mock_response

            await service.register_webhook(
                repository_id="repo-123",
                provider="github",
                repo_full_name="org/test-repo",
                access_token="gho_test_token",
            )

            mock_secrets_client.put_secret_value.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_webhook_handles_existing(
        self, service, mock_secrets_client
    ):
        """Test handling when webhook already exists."""
        mock_response_422 = MagicMock()
        mock_response_422.status_code = 422
        mock_response_422.json.return_value = {"message": "Hook already exists"}

        mock_response_list = MagicMock()
        mock_response_list.status_code = 200
        mock_response_list.json.return_value = [
            {
                "id": 99999,
                "config": {"url": "https://api.aura.local/api/v1/webhooks/github"},
            }
        ]

        with patch(
            "src.services.webhook_registration_service.requests.post"
        ) as mock_post:
            with patch(
                "src.services.webhook_registration_service.requests.get"
            ) as mock_get:
                mock_post.return_value = mock_response_422
                mock_get.return_value = mock_response_list

                result = await service.register_webhook(
                    repository_id="repo-123",
                    provider="github",
                    repo_full_name="org/test-repo",
                    access_token="gho_test_token",
                )

                assert result.webhook_id == "99999"

    @pytest.mark.asyncio
    async def test_register_webhook_uses_default_events(self, service):
        """Test default events are used if not specified."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 12345678}

        with patch(
            "src.services.webhook_registration_service.requests.post"
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await service.register_webhook(
                repository_id="repo-123",
                provider="github",
                repo_full_name="org/test-repo",
                access_token="gho_test_token",
            )

            assert "push" in result.events
            assert "pull_request" in result.events


# ============================================================================
# Webhook Registration Tests - GitLab
# ============================================================================


class TestGitLabWebhookRegistration:
    """Tests for GitLab webhook registration."""

    @pytest.mark.asyncio
    async def test_register_gitlab_webhook_success(self, service):
        """Test registering a webhook on GitLab."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 87654321}
        mock_response.raise_for_status = MagicMock()

        with patch(
            "src.services.webhook_registration_service.requests.post"
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await service.register_webhook(
                repository_id="repo-456",
                provider="gitlab",
                repo_full_name="org/test-repo",
                access_token="glpat_test_token",
                events=["push", "pull_request"],
            )

            assert result.webhook_id == "87654321"
            assert result.provider == "gitlab"

    @pytest.mark.asyncio
    async def test_register_gitlab_encodes_project_path(self, service):
        """Test GitLab project path is URL encoded."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 87654321}
        mock_response.raise_for_status = MagicMock()

        with patch(
            "src.services.webhook_registration_service.requests.post"
        ) as mock_post:
            mock_post.return_value = mock_response

            await service.register_webhook(
                repository_id="repo-456",
                provider="gitlab",
                repo_full_name="org/test-repo",
                access_token="glpat_test_token",
            )

            call_args = mock_post.call_args
            url = call_args[0][0]
            assert "org%2Ftest-repo" in url

    @pytest.mark.asyncio
    async def test_register_unsupported_provider_raises(self, service):
        """Test unsupported provider raises error."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            await service.register_webhook(
                repository_id="repo-789",
                provider="bitbucket",
                repo_full_name="org/test-repo",
                access_token="token",
            )


# ============================================================================
# Webhook Deletion Tests
# ============================================================================


class TestWebhookDeletion:
    """Tests for webhook deletion."""

    @pytest.mark.asyncio
    async def test_delete_github_webhook_success(
        self, service, mock_repositories_table, sample_repository_item
    ):
        """Test deleting a GitHub webhook."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.raise_for_status = MagicMock()

        with patch(
            "src.services.webhook_registration_service.requests.delete"
        ) as mock_delete:
            mock_delete.return_value = mock_response

            await service.delete_webhook(
                repository_id="repo-123",
                provider="github",
                repo_full_name="org/test-repo",
                access_token="gho_test_token",
            )

            mock_delete.assert_called_once()
            mock_repositories_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_webhook_no_webhook_found(
        self, service, mock_repositories_table
    ):
        """Test deleting when no webhook exists."""
        mock_repositories_table.get_item.return_value = {
            "Item": {"repository_id": "repo-123"}
        }

        # Should not raise, just log warning
        await service.delete_webhook(
            repository_id="repo-123",
            provider="github",
            repo_full_name="org/test-repo",
            access_token="gho_test_token",
        )

    @pytest.mark.asyncio
    async def test_delete_webhook_deletes_secret(
        self,
        service,
        mock_repositories_table,
        mock_secrets_client,
        sample_repository_item,
    ):
        """Test webhook deletion also deletes secret."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.raise_for_status = MagicMock()

        with patch(
            "src.services.webhook_registration_service.requests.delete"
        ) as mock_delete:
            mock_delete.return_value = mock_response

            await service.delete_webhook(
                repository_id="repo-123",
                provider="github",
                repo_full_name="org/test-repo",
                access_token="gho_test_token",
            )

            mock_secrets_client.delete_secret.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_gitlab_webhook_success(
        self, service, mock_repositories_table, sample_repository_item
    ):
        """Test deleting a GitLab webhook."""
        sample_repository_item["provider"] = "gitlab"
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch(
            "src.services.webhook_registration_service.requests.delete"
        ) as mock_delete:
            mock_delete.return_value = mock_response

            await service.delete_webhook(
                repository_id="repo-123",
                provider="gitlab",
                repo_full_name="org/test-repo",
                access_token="glpat_test_token",
            )

            mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_handles_404_gracefully(
        self, service, mock_repositories_table, sample_repository_item
    ):
        """Test deletion handles already deleted webhook."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status = MagicMock()

        with patch(
            "src.services.webhook_registration_service.requests.delete"
        ) as mock_delete:
            mock_delete.return_value = mock_response

            # Should not raise
            await service.delete_webhook(
                repository_id="repo-123",
                provider="github",
                repo_full_name="org/test-repo",
                access_token="gho_test_token",
            )


# ============================================================================
# Webhook Signature Verification Tests
# ============================================================================


class TestSignatureVerification:
    """Tests for webhook signature verification."""

    @pytest.mark.asyncio
    async def test_verify_sha256_signature_valid(
        self,
        service,
        mock_repositories_table,
        mock_secrets_client,
        sample_repository_item,
    ):
        """Test valid SHA256 signature verification."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": '{"secret": "test-webhook-secret"}'
        }

        payload = b'{"action": "opened"}'
        expected_signature = (
            "sha256="
            + hmac.new(b"test-webhook-secret", payload, hashlib.sha256).hexdigest()
        )

        result = await service.verify_webhook_signature(
            repository_id="repo-123",
            signature=expected_signature,
            payload=payload,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_sha256_signature_invalid(
        self,
        service,
        mock_repositories_table,
        mock_secrets_client,
        sample_repository_item,
    ):
        """Test invalid SHA256 signature."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": '{"secret": "test-webhook-secret"}'
        }

        payload = b'{"action": "opened"}'

        result = await service.verify_webhook_signature(
            repository_id="repo-123",
            signature="sha256=invalid_signature",
            payload=payload,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_sha1_signature_valid(
        self,
        service,
        mock_repositories_table,
        mock_secrets_client,
        sample_repository_item,
    ):
        """Test valid SHA1 signature verification."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": '{"secret": "test-webhook-secret"}'
        }

        payload = b'{"action": "opened"}'
        expected_signature = (
            "sha1="
            + hmac.new(b"test-webhook-secret", payload, hashlib.sha1).hexdigest()
        )

        result = await service.verify_webhook_signature(
            repository_id="repo-123",
            signature=expected_signature,
            payload=payload,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_gitlab_token_valid(
        self,
        service,
        mock_repositories_table,
        mock_secrets_client,
        sample_repository_item,
    ):
        """Test valid GitLab token verification."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": '{"secret": "gitlab-token-123"}'
        }

        result = await service.verify_webhook_signature(
            repository_id="repo-123",
            signature="gitlab-token-123",
            payload=b'{"push": true}',
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_no_secret_returns_false(
        self, service, mock_repositories_table
    ):
        """Test verification fails when no secret found."""
        mock_repositories_table.get_item.return_value = {
            "Item": {"repository_id": "repo-123"}
        }

        result = await service.verify_webhook_signature(
            repository_id="repo-123",
            signature="sha256=any",
            payload=b"{}",
        )

        assert result is False


# ============================================================================
# Webhook Status Tests
# ============================================================================


class TestWebhookStatus:
    """Tests for getting webhook status."""

    @pytest.mark.asyncio
    async def test_get_github_webhook_status(
        self, service, mock_repositories_table, sample_repository_item
    ):
        """Test getting GitHub webhook status."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "active": True,
            "events": ["push", "pull_request"],
            "last_response": {"code": 200, "status": "active"},
        }
        mock_response.raise_for_status = MagicMock()

        with patch(
            "src.services.webhook_registration_service.requests.get"
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await service.get_webhook_status(
                repository_id="repo-123",
                provider="github",
                repo_full_name="org/test-repo",
                access_token="gho_test_token",
            )

            assert result["status"] == "active"
            assert "events" in result

    @pytest.mark.asyncio
    async def test_get_webhook_status_not_configured(
        self, service, mock_repositories_table
    ):
        """Test status when no webhook configured."""
        mock_repositories_table.get_item.return_value = {
            "Item": {"repository_id": "repo-123"}
        }

        result = await service.get_webhook_status(
            repository_id="repo-123",
            provider="github",
            repo_full_name="org/test-repo",
            access_token="gho_test_token",
        )

        assert result["status"] == "not_configured"

    @pytest.mark.asyncio
    async def test_get_gitlab_webhook_status(
        self, service, mock_repositories_table, sample_repository_item
    ):
        """Test getting GitLab webhook status."""
        sample_repository_item["provider"] = "gitlab"
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "push_events": True,
            "merge_requests_events": True,
            "enable_ssl_verification": True,
        }
        mock_response.raise_for_status = MagicMock()

        with patch(
            "src.services.webhook_registration_service.requests.get"
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await service.get_webhook_status(
                repository_id="repo-123",
                provider="gitlab",
                repo_full_name="org/test-repo",
                access_token="glpat_test_token",
            )

            assert result["status"] == "active"
            assert "push" in result["events"]


# ============================================================================
# Data Model Tests
# ============================================================================


class TestDataModels:
    """Tests for data models."""

    def test_webhook_status_values(self):
        """Test WebhookStatus constants."""
        assert WebhookStatus.PENDING == "pending"
        assert WebhookStatus.ACTIVE == "active"
        assert WebhookStatus.INACTIVE == "inactive"
        assert WebhookStatus.FAILED == "failed"

    def test_webhook_config_defaults(self):
        """Test WebhookConfig default values."""
        config = WebhookConfig()
        config.__post_init__()
        assert config.events == ["push", "pull_request"]
        assert config.content_type == "json"
        assert config.insecure_ssl is False

    def test_webhook_config_custom(self):
        """Test WebhookConfig with custom values."""
        config = WebhookConfig(
            events=["push", "issues"],
            secret="custom-secret",
            content_type="form",
        )
        assert config.events == ["push", "issues"]
        assert config.secret == "custom-secret"

    def test_webhook_registration_dataclass(self):
        """Test WebhookRegistration dataclass."""
        config = WebhookConfig()
        registration = WebhookRegistration(
            webhook_id="wh-123",
            provider="github",
            repository_id="repo-456",
            repository_name="org/test-repo",
            callback_url="https://api.example.com/webhooks",
            config=config,
            status=WebhookStatus.ACTIVE,
            created_at="2025-01-01T00:00:00",
        )
        assert registration.webhook_id == "wh-123"
        assert registration.provider == "github"
        assert registration.status == WebhookStatus.ACTIVE

    def test_webhook_info_dataclass(self):
        """Test WebhookInfo dataclass."""
        info = WebhookInfo(
            webhook_id="12345",
            provider="github",
            repository_id="repo-123",
            callback_url="https://api.example.com/webhooks",
            events=["push", "pull_request"],
            active=True,
            created_at="2025-01-01T00:00:00",
        )
        assert info.webhook_id == "12345"
        assert info.active is True
        assert len(info.events) == 2


# ============================================================================
# Singleton Tests
# ============================================================================


class TestSingleton:
    """Tests for singleton instance."""

    def test_get_webhook_service_singleton(self):
        """Test singleton returns same instance."""
        import src.services.webhook_registration_service as module

        # Clear singleton state
        module._webhook_service = None

        # Mock boto3 clients that are created during singleton initialization
        mock_dynamodb = MagicMock()
        mock_secrets_client = MagicMock()

        with (
            patch(
                "src.services.webhook_registration_service.boto3.resource",
                return_value=mock_dynamodb,
            ),
            patch(
                "src.services.webhook_registration_service.boto3.client",
                return_value=mock_secrets_client,
            ),
        ):

            service1 = get_webhook_service()
            service2 = get_webhook_service()

            assert service1 is service2

        # Clean up singleton state for other tests
        module._webhook_service = None


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_register_webhook_api_error(self, service):
        """Test handling API errors during registration."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Internal Server Error")

        with patch(
            "src.services.webhook_registration_service.requests.post"
        ) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(Exception):
                await service.register_webhook(
                    repository_id="repo-123",
                    provider="github",
                    repo_full_name="org/test-repo",
                    access_token="gho_test_token",
                )

    @pytest.mark.asyncio
    async def test_delete_provider_failure_continues(
        self, service, mock_repositories_table, sample_repository_item
    ):
        """Test that provider deletion failure doesn't prevent cleanup."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        with patch(
            "src.services.webhook_registration_service.requests.delete"
        ) as mock_delete:
            mock_delete.side_effect = Exception("Network error")

            # Should not raise, but log warning
            await service.delete_webhook(
                repository_id="repo-123",
                provider="github",
                repo_full_name="org/test-repo",
                access_token="gho_test_token",
            )

            # Repository should still be updated
            mock_repositories_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_signature_secret_error(
        self,
        service,
        mock_repositories_table,
        mock_secrets_client,
        sample_repository_item,
    ):
        """Test signature verification handles secret retrieval errors."""
        from botocore.exceptions import ClientError

        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}
        mock_secrets_client.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "GetSecretValue",
        )

        result = await service.verify_webhook_signature(
            repository_id="repo-123",
            signature="sha256=any",
            payload=b"{}",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_get_status_error_returns_error_status(
        self, service, mock_repositories_table, sample_repository_item
    ):
        """Test status check returns error status on failure."""
        mock_repositories_table.get_item.return_value = {"Item": sample_repository_item}

        with patch(
            "src.services.webhook_registration_service.requests.get"
        ) as mock_get:
            mock_get.side_effect = Exception("API unavailable")

            result = await service.get_webhook_status(
                repository_id="repo-123",
                provider="github",
                repo_full_name="org/test-repo",
                access_token="gho_test_token",
            )

            assert result["status"] == "error"
            assert "error" in result
