"""
Tests for AWS Provider Adapters - Cloud Abstraction Layer

Tests for AWS service adapters that implement cloud-agnostic interfaces.
Reference: ADR-004 Cloud Abstraction Layer for Multi-Cloud Deployment
"""

from unittest.mock import MagicMock, patch

import pytest

# ==================== BedrockLLMAdapter Tests ====================


class TestBedrockLLMAdapter:
    """Tests for BedrockLLMAdapter class."""

    def test_initialization(self):
        """Test adapter initialization."""
        from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter

        adapter = BedrockLLMAdapter()
        assert adapter.region == "us-east-1"
        assert adapter._service is None
        assert adapter._initialized is False

    def test_initialization_with_region(self):
        """Test adapter initialization with custom region."""
        from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter

        adapter = BedrockLLMAdapter(region="us-west-2")
        assert adapter.region == "us-west-2"

    def test_get_service_creates_service(self):
        """Test that _get_service creates a new service instance."""
        from src.services.bedrock_llm_service import BedrockMode
        from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter

        with patch(
            "src.services.providers.aws.bedrock_adapter.BedrockLLMService"
        ) as mock_service:
            adapter = BedrockLLMAdapter()
            adapter._get_service()
            mock_service.assert_called_once_with(mode=BedrockMode.AWS)

    def test_get_service_returns_existing(self):
        """Test that _get_service returns existing service if already created."""
        from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter

        with patch(
            "src.services.providers.aws.bedrock_adapter.BedrockLLMService"
        ) as mock_service:
            adapter = BedrockLLMAdapter()
            adapter._service = mock_service.return_value
            service = adapter._get_service()
            # Should not create new service
            assert service == adapter._service

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful initialization."""
        from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter

        with patch(
            "src.services.providers.aws.bedrock_adapter.BedrockLLMService"
        ) as mock_service:
            mock_instance = MagicMock()
            mock_instance.mode.value = "api"
            mock_service.return_value = mock_instance

            adapter = BedrockLLMAdapter()
            result = await adapter.initialize()
            assert result is True
            assert adapter._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Test initialization failure."""
        from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter

        with patch(
            "src.services.providers.aws.bedrock_adapter.BedrockLLMService"
        ) as mock_service:
            mock_service.side_effect = Exception("Connection failed")

            adapter = BedrockLLMAdapter()
            result = await adapter.initialize()
            assert result is False

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test shutdown cleans up resources."""
        from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter

        adapter = BedrockLLMAdapter()
        adapter._initialized = True
        adapter._service = MagicMock()

        await adapter.shutdown()
        assert adapter._initialized is False
        assert adapter._service is None

    @pytest.mark.asyncio
    async def test_invoke(self):
        """Test invoke with a request."""
        from src.abstractions.llm_service import LLMRequest
        from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter

        with patch(
            "src.services.providers.aws.bedrock_adapter.BedrockLLMService"
        ) as mock_service:
            mock_instance = MagicMock()
            mock_instance.invoke_model.return_value = {
                "response": "Test response",
                "model_id": "claude-3",
                "input_tokens": 10,
                "output_tokens": 20,
                "stop_reason": "end_turn",
            }
            mock_service.return_value = mock_instance

            adapter = BedrockLLMAdapter()
            request = LLMRequest(prompt="Hello")
            response = await adapter.invoke(request)

            assert response.content == "Test response"
            assert response.input_tokens == 10
            assert response.output_tokens == 20

    @pytest.mark.asyncio
    async def test_invoke_with_system_prompt(self):
        """Test invoke with system prompt."""
        from src.abstractions.llm_service import LLMRequest
        from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter

        with patch(
            "src.services.providers.aws.bedrock_adapter.BedrockLLMService"
        ) as mock_service:
            mock_instance = MagicMock()
            mock_instance.invoke_model.return_value = {
                "response": "Response",
                "model_id": "claude-3",
            }
            mock_service.return_value = mock_instance

            adapter = BedrockLLMAdapter()
            request = LLMRequest(
                prompt="Hello", system_prompt="You are a helpful assistant"
            )
            await adapter.invoke(request)

            # Verify prompt was combined
            call_args = mock_instance.invoke_model.call_args
            assert "You are a helpful assistant" in call_args.kwargs["prompt"]


# ==================== NeptuneAdapter Tests ====================


class TestNeptuneAdapter:
    """Tests for NeptuneGraphAdapter class."""

    def test_initialization(self):
        """Test adapter initialization."""
        from src.services.providers.aws.neptune_adapter import NeptuneGraphAdapter

        adapter = NeptuneGraphAdapter(endpoint="neptune.aura.local")
        assert adapter.endpoint == "neptune.aura.local"
        assert adapter.region == "us-east-1"
        assert adapter._service is None

    def test_initialization_with_region(self):
        """Test adapter initialization with region."""
        from src.services.providers.aws.neptune_adapter import NeptuneGraphAdapter

        adapter = NeptuneGraphAdapter(endpoint="neptune.aura.local", region="us-west-2")
        assert adapter.region == "us-west-2"

    def test_get_service_creates_service(self):
        """Test that _get_service creates a new service instance."""
        from src.services.providers.aws.neptune_adapter import NeptuneGraphAdapter

        with patch(
            "src.services.providers.aws.neptune_adapter.NeptuneGraphService"
        ) as mock_service:
            adapter = NeptuneGraphAdapter(endpoint="neptune.aura.local")
            adapter._get_service()
            mock_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        from src.services.providers.aws.neptune_adapter import NeptuneGraphAdapter

        with patch(
            "src.services.providers.aws.neptune_adapter.NeptuneGraphService"
        ) as mock_service:
            mock_instance = MagicMock()
            mock_instance.mode.value = "mock"
            mock_service.return_value = mock_instance

            adapter = NeptuneGraphAdapter()
            result = await adapter.connect()
            assert result is True
            assert adapter._connected is True

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure."""
        from src.services.providers.aws.neptune_adapter import NeptuneGraphAdapter

        with patch(
            "src.services.providers.aws.neptune_adapter.NeptuneGraphService"
        ) as mock_service:
            mock_service.side_effect = Exception("Connection failed")

            adapter = NeptuneGraphAdapter()
            result = await adapter.connect()
            assert result is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect cleans up resources."""
        from src.services.providers.aws.neptune_adapter import NeptuneGraphAdapter

        adapter = NeptuneGraphAdapter()
        adapter._connected = True
        adapter._service = MagicMock()

        await adapter.disconnect()
        assert adapter._connected is False
        assert adapter._service is None


# ==================== OpenSearchAdapter Tests ====================


class TestOpenSearchAdapter:
    """Tests for OpenSearchVectorAdapter class."""

    def test_initialization(self):
        """Test adapter initialization."""
        from src.services.providers.aws.opensearch_adapter import (
            OpenSearchVectorAdapter,
        )

        adapter = OpenSearchVectorAdapter(endpoint="opensearch.aura.local")
        assert adapter.endpoint == "opensearch.aura.local"

    def test_initialization_with_region(self):
        """Test adapter initialization with region."""
        from src.services.providers.aws.opensearch_adapter import (
            OpenSearchVectorAdapter,
        )

        adapter = OpenSearchVectorAdapter(
            endpoint="opensearch.aura.local", region="us-west-2"
        )
        assert adapter.region == "us-west-2"

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        from src.services.providers.aws.opensearch_adapter import (
            OpenSearchVectorAdapter,
        )

        with patch(
            "src.services.providers.aws.opensearch_adapter.OpenSearchVectorService"
        ) as mock_service:
            mock_instance = MagicMock()
            mock_instance.mode.value = "mock"
            mock_service.return_value = mock_instance

            adapter = OpenSearchVectorAdapter()
            result = await adapter.connect()
            assert result is True

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure."""
        from src.services.providers.aws.opensearch_adapter import (
            OpenSearchVectorAdapter,
        )

        with patch(
            "src.services.providers.aws.opensearch_adapter.OpenSearchVectorService"
        ) as mock_service:
            mock_service.side_effect = Exception("Connection failed")

            adapter = OpenSearchVectorAdapter()
            result = await adapter.connect()
            assert result is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect cleans up resources."""
        from src.services.providers.aws.opensearch_adapter import (
            OpenSearchVectorAdapter,
        )

        adapter = OpenSearchVectorAdapter()
        adapter._connected = True
        adapter._service = MagicMock()

        await adapter.disconnect()
        assert adapter._connected is False


# ==================== S3Adapter Tests ====================


class TestS3Adapter:
    """Tests for S3StorageAdapter class."""

    def test_initialization(self):
        """Test adapter initialization."""
        from src.services.providers.aws.s3_adapter import S3StorageAdapter

        adapter = S3StorageAdapter()
        assert adapter.region == "us-east-1"
        assert adapter._client is None
        assert adapter._connected is False

    def test_initialization_with_region(self):
        """Test adapter initialization with region."""
        from src.services.providers.aws.s3_adapter import S3StorageAdapter

        adapter = S3StorageAdapter(region="us-west-2")
        assert adapter.region == "us-west-2"

    def test_client_property_lazy_init(self):
        """Test that client property lazy-initializes S3 client."""
        from src.services.providers.aws.s3_adapter import S3StorageAdapter

        with patch("src.services.providers.aws.s3_adapter.boto3") as mock_boto:
            mock_client = MagicMock()
            mock_boto.client.return_value = mock_client

            adapter = S3StorageAdapter()
            client = adapter.client

            mock_boto.client.assert_called_once_with("s3", region_name="us-east-1")
            assert client == mock_client

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        from src.services.providers.aws.s3_adapter import S3StorageAdapter

        with patch("src.services.providers.aws.s3_adapter.boto3") as mock_boto:
            mock_client = MagicMock()
            mock_client.list_buckets.return_value = {"Buckets": []}
            mock_boto.client.return_value = mock_client

            adapter = S3StorageAdapter()
            result = await adapter.connect()
            assert result is True
            assert adapter._connected is True

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure."""
        from src.services.providers.aws.s3_adapter import S3StorageAdapter

        with patch("src.services.providers.aws.s3_adapter.boto3") as mock_boto:
            mock_client = MagicMock()
            mock_client.list_buckets.side_effect = Exception("AWS error")
            mock_boto.client.return_value = mock_client

            adapter = S3StorageAdapter()
            result = await adapter.connect()
            assert result is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect cleans up resources."""
        from src.services.providers.aws.s3_adapter import S3StorageAdapter

        adapter = S3StorageAdapter()
        adapter._connected = True
        adapter._client = MagicMock()

        await adapter.disconnect()
        assert adapter._connected is False
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_create_bucket(self):
        """Test creating an S3 bucket."""
        from src.services.providers.aws.s3_adapter import S3StorageAdapter

        with patch("src.services.providers.aws.s3_adapter.boto3") as mock_boto:
            mock_client = MagicMock()
            mock_boto.client.return_value = mock_client

            adapter = S3StorageAdapter()
            result = await adapter.create_bucket("test-bucket")
            mock_client.create_bucket.assert_called()
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_bucket(self):
        """Test deleting an S3 bucket."""
        from src.services.providers.aws.s3_adapter import S3StorageAdapter

        with patch("src.services.providers.aws.s3_adapter.boto3") as mock_boto:
            mock_client = MagicMock()
            mock_boto.client.return_value = mock_client

            adapter = S3StorageAdapter()
            await adapter.delete_bucket("test-bucket")
            mock_client.delete_bucket.assert_called()


# ==================== SecretsManagerAdapter Tests ====================


class TestSecretsManagerAdapter:
    """Tests for SecretsManagerAdapter class."""

    def test_initialization(self):
        """Test adapter initialization."""
        from src.services.providers.aws.secrets_manager_adapter import (
            SecretsManagerAdapter,
        )

        adapter = SecretsManagerAdapter()
        assert adapter.region == "us-east-1"
        assert adapter._client is None
        assert adapter._connected is False

    def test_initialization_with_region(self):
        """Test adapter initialization with region."""
        from src.services.providers.aws.secrets_manager_adapter import (
            SecretsManagerAdapter,
        )

        adapter = SecretsManagerAdapter(region="us-west-2")
        assert adapter.region == "us-west-2"

    def test_client_property_lazy_init(self):
        """Test that client property lazy-initializes Secrets Manager client."""
        from src.services.providers.aws.secrets_manager_adapter import (
            SecretsManagerAdapter,
        )

        with patch(
            "src.services.providers.aws.secrets_manager_adapter.boto3"
        ) as mock_boto:
            mock_client = MagicMock()
            mock_boto.client.return_value = mock_client

            adapter = SecretsManagerAdapter()
            adapter.client

            mock_boto.client.assert_called_once_with(
                "secretsmanager", region_name="us-east-1"
            )

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        from src.services.providers.aws.secrets_manager_adapter import (
            SecretsManagerAdapter,
        )

        with patch(
            "src.services.providers.aws.secrets_manager_adapter.boto3"
        ) as mock_boto:
            mock_client = MagicMock()
            mock_client.list_secrets.return_value = {"SecretList": []}
            mock_boto.client.return_value = mock_client

            adapter = SecretsManagerAdapter()
            result = await adapter.connect()
            assert result is True
            assert adapter._connected is True

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure."""
        from src.services.providers.aws.secrets_manager_adapter import (
            SecretsManagerAdapter,
        )

        with patch(
            "src.services.providers.aws.secrets_manager_adapter.boto3"
        ) as mock_boto:
            mock_client = MagicMock()
            mock_client.list_secrets.side_effect = Exception("AWS error")
            mock_boto.client.return_value = mock_client

            adapter = SecretsManagerAdapter()
            result = await adapter.connect()
            assert result is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect cleans up resources."""
        from src.services.providers.aws.secrets_manager_adapter import (
            SecretsManagerAdapter,
        )

        adapter = SecretsManagerAdapter()
        adapter._connected = True
        adapter._client = MagicMock()

        await adapter.disconnect()
        assert adapter._connected is False
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_create_secret(self):
        """Test creating a secret."""
        from src.services.providers.aws.secrets_manager_adapter import (
            SecretsManagerAdapter,
        )

        with patch(
            "src.services.providers.aws.secrets_manager_adapter.boto3"
        ) as mock_boto:
            mock_client = MagicMock()
            mock_client.create_secret.return_value = {
                "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret",
                "Name": "test-secret",
                "VersionId": "v1",
            }
            mock_boto.client.return_value = mock_client

            adapter = SecretsManagerAdapter()
            secret = await adapter.create_secret("test-secret", {"key": "value"})
            mock_client.create_secret.assert_called()
            assert secret.name == "test-secret"

    @pytest.mark.asyncio
    async def test_get_secret(self):
        """Test getting a secret."""
        from src.services.providers.aws.secrets_manager_adapter import (
            SecretsManagerAdapter,
        )

        with patch(
            "src.services.providers.aws.secrets_manager_adapter.boto3"
        ) as mock_boto:
            mock_client = MagicMock()
            mock_client.get_secret_value.return_value = {
                "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret",
                "Name": "test-secret",
                "SecretString": '{"key": "value"}',
                "VersionId": "v1",
            }
            mock_boto.client.return_value = mock_client

            adapter = SecretsManagerAdapter()
            secret = await adapter.get_secret("test-secret")
            assert secret is not None
            assert secret.name == "test-secret"

    @pytest.mark.asyncio
    async def test_delete_secret(self):
        """Test deleting a secret."""
        from src.services.providers.aws.secrets_manager_adapter import (
            SecretsManagerAdapter,
        )

        with patch(
            "src.services.providers.aws.secrets_manager_adapter.boto3"
        ) as mock_boto:
            mock_client = MagicMock()
            mock_boto.client.return_value = mock_client

            adapter = SecretsManagerAdapter()
            result = await adapter.delete_secret("test-secret")
            mock_client.delete_secret.assert_called()
            assert result is True

    @pytest.mark.asyncio
    async def test_list_secrets(self):
        """Test listing secrets."""
        from src.services.providers.aws.secrets_manager_adapter import (
            SecretsManagerAdapter,
        )

        with patch(
            "src.services.providers.aws.secrets_manager_adapter.boto3"
        ) as mock_boto:
            mock_client = MagicMock()
            # The method uses a paginator
            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = [
                {"SecretList": [{"Name": "secret1"}, {"Name": "secret2"}]}
            ]
            mock_client.get_paginator.return_value = mock_paginator
            mock_boto.client.return_value = mock_client

            adapter = SecretsManagerAdapter()
            secrets = await adapter.list_secrets()
            assert len(secrets) == 2
