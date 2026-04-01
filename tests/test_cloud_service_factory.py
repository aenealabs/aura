"""
Tests for Cloud Service Factory.

Tests the factory pattern for creating cloud-agnostic service instances.
Covers AWS, Azure, Self-Hosted, and Mock provider branches.

Reference: ADR-004 Cloud Abstraction Layer, ADR-049 Self-Hosted Deployment
"""

import os
import platform
from unittest.mock import MagicMock, patch

import pytest

from src.abstractions.cloud_provider import CloudConfig, CloudProvider
from src.services.providers.factory import (
    CloudServiceFactory,
    _get_factory,
    get_document_service,
    get_graph_service,
    get_llm_service,
    get_secrets_service,
    get_storage_service,
    get_vector_service,
)

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestCloudServiceFactoryInit:
    """Tests for CloudServiceFactory initialization."""

    def test_init_with_config(self):
        """Test factory initialization with explicit config."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        factory = CloudServiceFactory(config)

        assert factory.config == config
        assert factory.config.provider == CloudProvider.MOCK
        assert factory.config.region == "us-east-1"
        assert factory._cached_services == {}

    def test_from_environment_mock(self):
        """Test factory creation from environment with MOCK provider."""
        with patch.dict(
            os.environ, {"CLOUD_PROVIDER": "mock", "AWS_REGION": "us-west-2"}
        ):
            factory = CloudServiceFactory.from_environment()

            assert factory.config.provider == CloudProvider.MOCK

    def test_from_environment_aws(self):
        """Test factory creation from environment with AWS provider."""
        with patch.dict(
            os.environ,
            {"CLOUD_PROVIDER": "aws", "AWS_REGION": "us-east-1"},
            clear=False,
        ):
            factory = CloudServiceFactory.from_environment()

            assert factory.config.provider == CloudProvider.AWS
            assert factory.config.region == "us-east-1"

    def test_for_provider(self):
        """Test factory creation for specific provider."""
        factory = CloudServiceFactory.for_provider(
            provider=CloudProvider.AZURE, region="eastus"
        )

        assert factory.config.provider == CloudProvider.AZURE
        assert factory.config.region == "eastus"


class TestMockGraphService:
    """Tests for graph service creation with MOCK provider."""

    @pytest.fixture
    def mock_factory(self):
        """Create a factory with MOCK provider."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        return CloudServiceFactory(config)

    def test_create_mock_graph_service(self, mock_factory):
        """Test creating mock graph service."""
        service = mock_factory.create_graph_service()

        # Verify it's a MockGraphService
        assert service is not None
        assert hasattr(service, "add_entity")
        assert hasattr(service, "connect")

    def test_graph_service_caching(self, mock_factory):
        """Test that graph service is cached."""
        service1 = mock_factory.create_graph_service()
        service2 = mock_factory.create_graph_service()

        assert service1 is service2

    def test_clear_cache(self, mock_factory):
        """Test cache clearing."""
        service1 = mock_factory.create_graph_service()
        mock_factory.clear_cache()
        service2 = mock_factory.create_graph_service()

        # After clear, should be different instance
        assert service1 is not service2


class TestMockVectorService:
    """Tests for vector service creation with MOCK provider."""

    @pytest.fixture
    def mock_factory(self):
        """Create a factory with MOCK provider."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        return CloudServiceFactory(config)

    def test_create_mock_vector_service(self, mock_factory):
        """Test creating mock vector service."""
        service = mock_factory.create_vector_service()

        assert service is not None
        assert hasattr(service, "index_document")
        assert hasattr(service, "connect")

    def test_vector_service_caching(self, mock_factory):
        """Test that vector service is cached."""
        service1 = mock_factory.create_vector_service()
        service2 = mock_factory.create_vector_service()

        assert service1 is service2


class TestMockLLMService:
    """Tests for LLM service creation with MOCK provider."""

    @pytest.fixture
    def mock_factory(self):
        """Create a factory with MOCK provider."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        return CloudServiceFactory(config)

    def test_create_mock_llm_service(self, mock_factory):
        """Test creating mock LLM service."""
        service = mock_factory.create_llm_service()

        assert service is not None
        assert hasattr(service, "invoke")
        assert hasattr(service, "generate_embedding")

    def test_llm_service_caching(self, mock_factory):
        """Test that LLM service is cached."""
        service1 = mock_factory.create_llm_service()
        service2 = mock_factory.create_llm_service()

        assert service1 is service2


class TestMockStorageService:
    """Tests for storage service creation with MOCK provider."""

    @pytest.fixture
    def mock_factory(self):
        """Create a factory with MOCK provider."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        return CloudServiceFactory(config)

    def test_create_mock_storage_service(self, mock_factory):
        """Test creating mock storage service."""
        service = mock_factory.create_storage_service()

        assert service is not None
        assert hasattr(service, "upload_object")
        assert hasattr(service, "download_object")

    def test_storage_service_caching(self, mock_factory):
        """Test that storage service is cached."""
        service1 = mock_factory.create_storage_service()
        service2 = mock_factory.create_storage_service()

        assert service1 is service2


class TestMockSecretsService:
    """Tests for secrets service creation with MOCK provider."""

    @pytest.fixture
    def mock_factory(self):
        """Create a factory with MOCK provider."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        return CloudServiceFactory(config)

    def test_create_mock_secrets_service(self, mock_factory):
        """Test creating mock secrets service."""
        service = mock_factory.create_secrets_service()

        assert service is not None
        assert hasattr(service, "get_secret")
        assert hasattr(service, "create_secret")

    def test_secrets_service_caching(self, mock_factory):
        """Test that secrets service is cached."""
        service1 = mock_factory.create_secrets_service()
        service2 = mock_factory.create_secrets_service()

        assert service1 is service2


class TestMockDocumentService:
    """Tests for document service creation with MOCK provider."""

    @pytest.fixture
    def mock_factory(self):
        """Create a factory with MOCK provider."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        return CloudServiceFactory(config)

    def test_create_mock_document_service(self, mock_factory):
        """Test creating mock document service."""
        service = mock_factory.create_document_service()

        assert service is not None
        assert isinstance(service, dict)
        assert service["_mock"] is True
        assert "_tables" in service

    def test_document_service_caching(self, mock_factory):
        """Test that document service is cached."""
        service1 = mock_factory.create_document_service()
        service2 = mock_factory.create_document_service()

        assert service1 is service2


class TestAWSProvider:
    """Tests for AWS provider service creation."""

    @pytest.fixture
    def aws_factory(self):
        """Create a factory with AWS provider."""
        config = CloudConfig(provider=CloudProvider.AWS, region="us-east-1")
        return CloudServiceFactory(config)

    def test_create_aws_graph_service(self, aws_factory):
        """Test creating AWS Neptune graph service."""
        # Mock the import to avoid actual AWS connection
        with patch.dict(os.environ, {"NEPTUNE_ENDPOINT": "neptune.test.amazonaws.com"}):
            service = aws_factory.create_graph_service()

            assert service is not None
            # Verify it's the Neptune adapter
            assert "NeptuneGraphAdapter" in type(service).__name__

    def test_create_aws_vector_service(self, aws_factory):
        """Test creating AWS OpenSearch vector service."""
        with patch.dict(
            os.environ, {"OPENSEARCH_ENDPOINT": "opensearch.test.amazonaws.com"}
        ):
            service = aws_factory.create_vector_service()

            assert service is not None
            assert "OpenSearchVectorAdapter" in type(service).__name__

    def test_create_aws_llm_service(self, aws_factory):
        """Test creating AWS Bedrock LLM service."""
        service = aws_factory.create_llm_service()

        assert service is not None
        assert "BedrockLLMAdapter" in type(service).__name__

    def test_create_aws_storage_service(self, aws_factory):
        """Test creating AWS S3 storage service."""
        service = aws_factory.create_storage_service()

        assert service is not None
        assert "S3StorageAdapter" in type(service).__name__

    def test_create_aws_secrets_service(self, aws_factory):
        """Test creating AWS Secrets Manager service."""
        service = aws_factory.create_secrets_service()

        assert service is not None
        assert "SecretsManagerAdapter" in type(service).__name__

    def test_create_aws_document_service(self, aws_factory):
        """Test creating AWS DynamoDB document service."""
        with patch("boto3.resource") as mock_boto:
            mock_boto.return_value = MagicMock()
            service = aws_factory.create_document_service()

            assert service is not None
            mock_boto.assert_called_once_with("dynamodb", region_name="us-east-1")


class TestAWSGovCloudProvider:
    """Tests for AWS GovCloud provider service creation."""

    @pytest.fixture
    def govcloud_factory(self):
        """Create a factory with AWS GovCloud provider."""
        config = CloudConfig(
            provider=CloudProvider.AWS_GOVCLOUD, region="us-gov-west-1"
        )
        return CloudServiceFactory(config)

    def test_govcloud_uses_aws_services(self, govcloud_factory):
        """Test that GovCloud uses the same AWS services as commercial."""
        service = govcloud_factory.create_llm_service()
        assert "BedrockLLMAdapter" in type(service).__name__


class TestAzureProvider:
    """Tests for Azure provider service creation."""

    @pytest.fixture
    def azure_factory(self):
        """Create a factory with Azure provider."""
        config = CloudConfig(provider=CloudProvider.AZURE, region="eastus")
        return CloudServiceFactory(config)

    def test_create_azure_graph_service(self, azure_factory):
        """Test creating Azure Cosmos DB graph service."""
        with patch.dict(
            os.environ,
            {
                "COSMOS_ENDPOINT": "https://test.documents.azure.com:443/",
                "COSMOS_DATABASE": "aura-graph",
                "COSMOS_CONTAINER": "code-entities",
            },
        ):
            service = azure_factory.create_graph_service()

            assert service is not None
            assert "CosmosDBGraphService" in type(service).__name__

    def test_create_azure_vector_service(self, azure_factory):
        """Test creating Azure AI Search vector service."""
        with patch.dict(
            os.environ,
            {
                "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
                "AZURE_SEARCH_INDEX": "aura-vectors",
            },
        ):
            service = azure_factory.create_vector_service()

            assert service is not None
            assert "AzureAISearchService" in type(service).__name__

    def test_create_azure_llm_service(self, azure_factory):
        """Test creating Azure OpenAI LLM service."""
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4",
            },
        ):
            service = azure_factory.create_llm_service()

            assert service is not None
            assert "AzureOpenAIService" in type(service).__name__

    def test_create_azure_storage_service(self, azure_factory):
        """Test creating Azure Blob storage service."""
        with patch.dict(
            os.environ,
            {"AZURE_STORAGE_ACCOUNT_URL": "https://teststorage.blob.core.windows.net"},
        ):
            service = azure_factory.create_storage_service()

            assert service is not None
            assert "AzureBlobService" in type(service).__name__

    def test_create_azure_secrets_service(self, azure_factory):
        """Test creating Azure Key Vault secrets service."""
        with patch.dict(
            os.environ,
            {"AZURE_KEYVAULT_URL": "https://test-vault.vault.azure.net/"},
        ):
            service = azure_factory.create_secrets_service()

            assert service is not None
            assert "AzureKeyVaultService" in type(service).__name__

    def test_create_azure_document_service(self, azure_factory):
        """Test creating Azure CosmosDB document service."""
        pytest.importorskip("azure.cosmos")  # Skip if azure-cosmos not installed
        with patch("azure.cosmos.CosmosClient") as mock_cosmos:
            mock_cosmos.return_value = MagicMock()
            with patch.dict(
                os.environ,
                {
                    "COSMOS_ENDPOINT": "https://test.documents.azure.com:443/",
                    "COSMOS_KEY": "test-key",
                },
            ):
                service = azure_factory.create_document_service()

                assert service is not None


class TestSelfHostedProvider:
    """Tests for Self-Hosted provider service creation."""

    @pytest.fixture
    def selfhosted_factory(self):
        """Create a factory with Self-Hosted provider."""
        config = CloudConfig(provider=CloudProvider.SELF_HOSTED, region="local")
        return CloudServiceFactory(config)

    def test_create_selfhosted_graph_service(self, selfhosted_factory):
        """Test creating Neo4j graph service for self-hosted."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USERNAME": "neo4j",
                "NEO4J_PASSWORD": "password",
                "NEO4J_DATABASE": "aura",
            },
        ):
            service = selfhosted_factory.create_graph_service()

            assert service is not None
            assert "Neo4jGraphAdapter" in type(service).__name__

    def test_create_selfhosted_vector_service(self, selfhosted_factory):
        """Test creating self-hosted OpenSearch vector service."""
        with patch.dict(
            os.environ,
            {
                "OPENSEARCH_ENDPOINT": "https://localhost:9200",
                "OPENSEARCH_USERNAME": "admin",
                "OPENSEARCH_PASSWORD": "admin",
            },
        ):
            service = selfhosted_factory.create_vector_service()

            assert service is not None
            assert "SelfHostedOpenSearchAdapter" in type(service).__name__

    def test_create_selfhosted_llm_service(self, selfhosted_factory):
        """Test creating local LLM adapter for self-hosted."""
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "vllm",
                "LLM_ENDPOINT": "http://localhost:8000",
                "LLM_MODEL_ID": "meta-llama/Llama-2-7b",
                "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
            },
        ):
            service = selfhosted_factory.create_llm_service()

            assert service is not None
            assert "LocalLLMAdapter" in type(service).__name__

    def test_create_selfhosted_storage_service(self, selfhosted_factory):
        """Test creating MinIO storage adapter for self-hosted."""
        with patch.dict(
            os.environ,
            {
                "MINIO_ENDPOINT": "localhost:9000",
                "MINIO_ACCESS_KEY": "minioadmin",
                "MINIO_SECRET_KEY": "minioadmin",
            },
        ):
            service = selfhosted_factory.create_storage_service()

            assert service is not None
            assert "MinioStorageAdapter" in type(service).__name__

    def test_create_selfhosted_secrets_service(self, selfhosted_factory):
        """Test creating file-based secrets adapter for self-hosted."""
        with patch.dict(
            os.environ,
            {
                "SECRETS_PATH": "/var/secrets",
                "SECRETS_MASTER_KEY": "master-key-123",
            },
        ):
            service = selfhosted_factory.create_secrets_service()

            assert service is not None
            assert "FileSecretsAdapter" in type(service).__name__

    def test_create_selfhosted_document_service(self, selfhosted_factory):
        """Test creating PostgreSQL document adapter for self-hosted."""
        with patch.dict(
            os.environ,
            {
                "POSTGRES_HOST": "localhost",
                "POSTGRES_DATABASE": "aura",
                "POSTGRES_USERNAME": "postgres",
                "POSTGRES_PASSWORD": "password",
            },
        ):
            service = selfhosted_factory.create_document_service()

            assert service is not None
            assert "PostgresDocumentAdapter" in type(service).__name__


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_graph_service(self):
        """Test get_graph_service convenience function."""
        import src.services.providers.factory as factory_module

        # Reset the default factory
        factory_module._default_factory = None

        with patch.dict(
            os.environ, {"CLOUD_PROVIDER": "mock", "AWS_REGION": "us-east-1"}
        ):
            service = get_graph_service()

            assert service is not None

        # Clean up
        factory_module._default_factory = None

    def test_get_vector_service(self):
        """Test get_vector_service convenience function."""
        import src.services.providers.factory as factory_module

        factory_module._default_factory = None

        with patch.dict(
            os.environ, {"CLOUD_PROVIDER": "mock", "AWS_REGION": "us-east-1"}
        ):
            service = get_vector_service()

            assert service is not None

        factory_module._default_factory = None

    def test_get_llm_service(self):
        """Test get_llm_service convenience function."""
        import src.services.providers.factory as factory_module

        factory_module._default_factory = None

        with patch.dict(
            os.environ, {"CLOUD_PROVIDER": "mock", "AWS_REGION": "us-east-1"}
        ):
            service = get_llm_service()

            assert service is not None

        factory_module._default_factory = None

    def test_get_storage_service(self):
        """Test get_storage_service convenience function."""
        import src.services.providers.factory as factory_module

        factory_module._default_factory = None

        with patch.dict(
            os.environ, {"CLOUD_PROVIDER": "mock", "AWS_REGION": "us-east-1"}
        ):
            service = get_storage_service()

            assert service is not None

        factory_module._default_factory = None

    def test_get_secrets_service(self):
        """Test get_secrets_service convenience function."""
        import src.services.providers.factory as factory_module

        factory_module._default_factory = None

        with patch.dict(
            os.environ, {"CLOUD_PROVIDER": "mock", "AWS_REGION": "us-east-1"}
        ):
            service = get_secrets_service()

            assert service is not None

        factory_module._default_factory = None

    def test_get_document_service(self):
        """Test get_document_service convenience function."""
        import src.services.providers.factory as factory_module

        factory_module._default_factory = None

        with patch.dict(
            os.environ, {"CLOUD_PROVIDER": "mock", "AWS_REGION": "us-east-1"}
        ):
            service = get_document_service()

            assert service is not None
            assert isinstance(service, dict)

        factory_module._default_factory = None

    def test_factory_singleton_pattern(self):
        """Test that _get_factory returns same instance."""
        import src.services.providers.factory as factory_module

        factory_module._default_factory = None

        with patch.dict(
            os.environ, {"CLOUD_PROVIDER": "mock", "AWS_REGION": "us-east-1"}
        ):
            factory1 = _get_factory()
            factory2 = _get_factory()

            assert factory1 is factory2

        factory_module._default_factory = None


class TestKwargsOverrides:
    """Tests for kwargs override functionality."""

    @pytest.fixture
    def mock_factory(self):
        """Create a factory with MOCK provider."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        return CloudServiceFactory(config)

    def test_graph_service_with_kwargs(self):
        """Test creating AWS graph service with explicit endpoint."""
        config = CloudConfig(provider=CloudProvider.AWS, region="us-east-1")
        factory = CloudServiceFactory(config)

        service = factory.create_graph_service(endpoint="custom-neptune.amazonaws.com")

        assert service is not None

    def test_vector_service_with_kwargs(self):
        """Test creating Azure vector service with explicit kwargs."""
        config = CloudConfig(provider=CloudProvider.AZURE, region="eastus")
        factory = CloudServiceFactory(config)

        service = factory.create_vector_service(
            endpoint="https://custom.search.windows.net", index="custom-index"
        )

        assert service is not None

    def test_storage_service_with_kwargs(self):
        """Test creating self-hosted storage service with explicit kwargs."""
        config = CloudConfig(provider=CloudProvider.SELF_HOSTED, region="local")
        factory = CloudServiceFactory(config)

        service = factory.create_storage_service(
            endpoint="minio.local:9000",
            access_key="custom-access",
            secret_key="custom-secret",
            secure=False,
        )

        assert service is not None


class TestAllServicesCreation:
    """Integration tests for creating all services from one factory."""

    def test_create_all_mock_services(self):
        """Test creating all mock services from one factory."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        factory = CloudServiceFactory(config)

        # Create all services
        graph = factory.create_graph_service()
        vector = factory.create_vector_service()
        llm = factory.create_llm_service()
        storage = factory.create_storage_service()
        secrets = factory.create_secrets_service()
        document = factory.create_document_service()

        # All should be created
        assert graph is not None
        assert vector is not None
        assert llm is not None
        assert storage is not None
        assert secrets is not None
        assert document is not None

        # All should be cached
        assert len(factory._cached_services) == 6

    def test_create_all_aws_services(self):
        """Test creating all AWS services from one factory."""
        config = CloudConfig(provider=CloudProvider.AWS, region="us-east-1")
        factory = CloudServiceFactory(config)

        with patch.dict(
            os.environ,
            {
                "NEPTUNE_ENDPOINT": "neptune.test.amazonaws.com",
                "OPENSEARCH_ENDPOINT": "opensearch.test.amazonaws.com",
            },
        ):
            with patch("boto3.resource") as mock_boto:
                mock_boto.return_value = MagicMock()

                graph = factory.create_graph_service()
                vector = factory.create_vector_service()
                llm = factory.create_llm_service()
                storage = factory.create_storage_service()
                secrets = factory.create_secrets_service()
                document = factory.create_document_service()

        assert all(
            svc is not None for svc in [graph, vector, llm, storage, secrets, document]
        )


class TestAzureGovernmentProvider:
    """Tests for Azure Government provider service creation."""

    @pytest.fixture
    def azure_gov_factory(self):
        """Create a factory with Azure Government provider."""
        config = CloudConfig(
            provider=CloudProvider.AZURE_GOVERNMENT, region="usgovvirginia"
        )
        return CloudServiceFactory(config)

    def test_azure_gov_graph_service(self, azure_gov_factory):
        """Test Azure Government uses CosmosDB graph service."""
        with patch.dict(
            os.environ,
            {
                "COSMOS_ENDPOINT": "https://test.documents.azure.us:443/",
                "COSMOS_DATABASE": "aura-graph",
                "COSMOS_CONTAINER": "code-entities",
            },
        ):
            service = azure_gov_factory.create_graph_service()
            assert service is not None
            assert "CosmosDBGraphService" in type(service).__name__

    def test_azure_gov_vector_service(self, azure_gov_factory):
        """Test Azure Government uses Azure AI Search service."""
        with patch.dict(
            os.environ,
            {
                "AZURE_SEARCH_ENDPOINT": "https://test.search.azure.us",
                "AZURE_SEARCH_INDEX": "aura-vectors",
            },
        ):
            service = azure_gov_factory.create_vector_service()
            assert service is not None
            assert "AzureAISearchService" in type(service).__name__

    def test_azure_gov_llm_service(self, azure_gov_factory):
        """Test Azure Government uses Azure OpenAI service."""
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.us/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4",
            },
        ):
            service = azure_gov_factory.create_llm_service()
            assert service is not None
            assert "AzureOpenAIService" in type(service).__name__

    def test_azure_gov_storage_service(self, azure_gov_factory):
        """Test Azure Government uses Azure Blob storage."""
        with patch.dict(
            os.environ,
            {
                "AZURE_STORAGE_ACCOUNT_URL": "https://teststorage.blob.core.usgovcloudapi.net"
            },
        ):
            service = azure_gov_factory.create_storage_service()
            assert service is not None
            assert "AzureBlobService" in type(service).__name__

    def test_azure_gov_secrets_service(self, azure_gov_factory):
        """Test Azure Government uses Azure Key Vault."""
        with patch.dict(
            os.environ,
            {"AZURE_KEYVAULT_URL": "https://test-vault.vault.usgovcloudapi.net/"},
        ):
            service = azure_gov_factory.create_secrets_service()
            assert service is not None
            assert "AzureKeyVaultService" in type(service).__name__

    def test_azure_gov_document_service(self, azure_gov_factory):
        """Test Azure Government uses CosmosDB document service."""
        pytest.importorskip("azure.cosmos")
        with patch("azure.cosmos.CosmosClient") as mock_cosmos:
            mock_cosmos.return_value = MagicMock()
            with patch.dict(
                os.environ,
                {
                    "COSMOS_ENDPOINT": "https://test.documents.azure.us:443/",
                    "COSMOS_KEY": "test-key",
                },
            ):
                service = azure_gov_factory.create_document_service()
                assert service is not None


class TestProviderSwitchingMidSession:
    """Tests for switching providers mid-session."""

    def test_switch_from_mock_to_aws(self):
        """Test switching from mock to AWS provider."""
        mock_config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        mock_factory = CloudServiceFactory(mock_config)
        mock_graph = mock_factory.create_graph_service()
        assert "MockGraphService" in type(mock_graph).__name__

        aws_config = CloudConfig(provider=CloudProvider.AWS, region="us-east-1")
        aws_factory = CloudServiceFactory(aws_config)
        with patch.dict(os.environ, {"NEPTUNE_ENDPOINT": "neptune.test.amazonaws.com"}):
            aws_graph = aws_factory.create_graph_service()
            assert "NeptuneGraphAdapter" in type(aws_graph).__name__

        assert mock_graph is not aws_graph

    def test_clear_cache_allows_new_provider(self):
        """Test that clearing cache allows creating new services."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        factory = CloudServiceFactory(config)

        graph1 = factory.create_graph_service()
        assert "graph_service" in factory._cached_services

        factory.clear_cache()
        assert len(factory._cached_services) == 0

        graph2 = factory.create_graph_service()
        assert graph1 is not graph2


class TestCacheInvalidation:
    """Tests for service cache invalidation scenarios."""

    def test_cache_key_isolation(self):
        """Test that different service types have isolated caches."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        factory = CloudServiceFactory(config)

        graph = factory.create_graph_service()
        vector = factory.create_vector_service()
        llm = factory.create_llm_service()

        assert factory._cached_services.get("graph_service") is graph
        assert factory._cached_services.get("vector_service") is vector
        assert factory._cached_services.get("llm_service") is llm
        assert graph is not vector
        assert vector is not llm

    def test_clear_cache_clears_all_services(self):
        """Test that clear_cache removes all cached services."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="us-east-1")
        factory = CloudServiceFactory(config)

        factory.create_graph_service()
        factory.create_vector_service()
        factory.create_llm_service()
        factory.create_storage_service()
        factory.create_secrets_service()
        factory.create_document_service()

        assert len(factory._cached_services) == 6
        factory.clear_cache()
        assert len(factory._cached_services) == 0


class TestMissingEnvironmentVariables:
    """Tests for handling missing environment variables."""

    def test_aws_graph_service_missing_endpoint(self):
        """Test AWS graph service with missing Neptune endpoint."""
        config = CloudConfig(provider=CloudProvider.AWS, region="us-east-1")
        factory = CloudServiceFactory(config)

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEPTUNE_ENDPOINT", None)
            service = factory.create_graph_service()
            assert service is not None
            assert "NeptuneGraphAdapter" in type(service).__name__

    def test_selfhosted_llm_missing_config(self):
        """Test self-hosted LLM with missing configuration."""
        config = CloudConfig(provider=CloudProvider.SELF_HOSTED, region="local")
        factory = CloudServiceFactory(config)

        with patch.dict(os.environ, {}, clear=True):
            service = factory.create_llm_service()
            assert service is not None
            assert "LocalLLMAdapter" in type(service).__name__


class TestInvalidRegionSpecifications:
    """Tests for invalid region specifications."""

    def test_empty_region(self):
        """Test factory with empty region string."""
        config = CloudConfig(provider=CloudProvider.AWS, region="")
        factory = CloudServiceFactory(config)
        assert factory.config.region == ""
        service = factory.create_llm_service()
        assert service is not None

    def test_invalid_region_string(self):
        """Test factory with invalid region string."""
        config = CloudConfig(provider=CloudProvider.MOCK, region="invalid-region-xyz")
        factory = CloudServiceFactory(config)
        service = factory.create_graph_service()
        assert service is not None


class TestProviderImportMocking:
    """Tests for mocking individual provider imports."""

    def test_mock_neptune_adapter_import(self):
        """Test mocking Neptune adapter import."""
        config = CloudConfig(provider=CloudProvider.AWS, region="us-east-1")
        factory = CloudServiceFactory(config)

        with patch(
            "src.services.providers.aws.neptune_adapter.NeptuneGraphAdapter"
        ) as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance

            with patch.dict(os.environ, {"NEPTUNE_ENDPOINT": "test.endpoint"}):
                factory.clear_cache()
                service = factory.create_graph_service()

            assert service is mock_instance
            mock_class.assert_called_once()

    def test_mock_bedrock_adapter_import(self):
        """Test mocking Bedrock adapter import."""
        config = CloudConfig(provider=CloudProvider.AWS, region="us-east-1")
        factory = CloudServiceFactory(config)

        with patch(
            "src.services.providers.aws.bedrock_adapter.BedrockLLMAdapter"
        ) as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance

            service = factory.create_llm_service()

            assert service is mock_instance
            mock_class.assert_called_once_with(region="us-east-1")


class TestAWSGovCloudAllServices:
    """Comprehensive tests for AWS GovCloud provider."""

    @pytest.fixture
    def govcloud_factory(self):
        """Create a factory with AWS GovCloud provider."""
        config = CloudConfig(
            provider=CloudProvider.AWS_GOVCLOUD, region="us-gov-west-1"
        )
        return CloudServiceFactory(config)

    def test_govcloud_graph_service(self, govcloud_factory):
        """Test GovCloud creates Neptune graph service."""
        with patch.dict(os.environ, {"NEPTUNE_ENDPOINT": "neptune.test.amazonaws.com"}):
            service = govcloud_factory.create_graph_service()
            assert "NeptuneGraphAdapter" in type(service).__name__

    def test_govcloud_vector_service(self, govcloud_factory):
        """Test GovCloud creates OpenSearch vector service."""
        with patch.dict(
            os.environ, {"OPENSEARCH_ENDPOINT": "opensearch.test.amazonaws.com"}
        ):
            service = govcloud_factory.create_vector_service()
            assert "OpenSearchVectorAdapter" in type(service).__name__

    def test_govcloud_document_service(self, govcloud_factory):
        """Test GovCloud creates DynamoDB document service."""
        with patch("boto3.resource") as mock_boto:
            mock_boto.return_value = MagicMock()
            service = govcloud_factory.create_document_service()
            assert service is not None
            mock_boto.assert_called_once_with("dynamodb", region_name="us-gov-west-1")


class TestSelfHostedAllServices:
    """Comprehensive tests for Self-Hosted provider."""

    @pytest.fixture
    def selfhosted_factory(self):
        """Create a factory with Self-Hosted provider."""
        config = CloudConfig(provider=CloudProvider.SELF_HOSTED, region="local")
        return CloudServiceFactory(config)

    def test_selfhosted_document_service_postgres(self, selfhosted_factory):
        """Test self-hosted creates PostgreSQL document adapter."""
        with patch.dict(
            os.environ,
            {
                "POSTGRES_HOST": "localhost",
                "POSTGRES_DATABASE": "aura",
                "POSTGRES_USERNAME": "postgres",
                "POSTGRES_PASSWORD": "password",
            },
        ):
            service = selfhosted_factory.create_document_service()
            assert "PostgresDocumentAdapter" in type(service).__name__

    def test_selfhosted_secrets_service_file(self, selfhosted_factory):
        """Test self-hosted creates file-based secrets adapter."""
        with patch.dict(
            os.environ,
            {
                "SECRETS_PATH": "/var/secrets",
                "SECRETS_MASTER_KEY": "test-master-key",
                "SECRETS_KEY_FILE": "/var/secrets/keyfile",
            },
        ):
            service = selfhosted_factory.create_secrets_service()
            assert "FileSecretsAdapter" in type(service).__name__


class TestDocumentServiceEdgeCases:
    """Edge case tests for document service."""

    def test_azure_document_service_with_kwargs(self):
        """Test Azure document service with explicit kwargs."""
        pytest.importorskip("azure.cosmos")
        config = CloudConfig(provider=CloudProvider.AZURE, region="eastus")
        factory = CloudServiceFactory(config)

        with patch("azure.cosmos.CosmosClient") as mock_cosmos:
            mock_client = MagicMock()
            mock_cosmos.return_value = mock_client

            service = factory.create_document_service(
                endpoint="https://custom.documents.azure.com:443/",
                key="custom-key-12345",
            )

            assert service is mock_client
            mock_cosmos.assert_called_once_with(
                url="https://custom.documents.azure.com:443/",
                credential="custom-key-12345",
            )

    def test_selfhosted_document_service_with_kwargs(self):
        """Test self-hosted document service with explicit kwargs."""
        config = CloudConfig(provider=CloudProvider.SELF_HOSTED, region="local")
        factory = CloudServiceFactory(config)

        service = factory.create_document_service(
            host="custom-host.local",
            port=5432,
            database="custom-db",
            username="custom-user",
            password="custom-pass",
        )

        assert "PostgresDocumentAdapter" in type(service).__name__


class TestConvenienceFunctionsExtended:
    """Extended tests for module-level convenience functions."""

    def test_get_factory_creates_singleton(self):
        """Test that _get_factory creates and returns singleton."""
        import src.services.providers.factory as factory_module

        factory_module._default_factory = None

        with patch.dict(
            os.environ, {"CLOUD_PROVIDER": "mock", "AWS_REGION": "us-east-1"}
        ):
            factory1 = _get_factory()
            factory2 = _get_factory()

            assert factory1 is factory2
            assert factory_module._default_factory is factory1

        factory_module._default_factory = None


class TestKwargsOverridesExtended:
    """Extended tests for kwargs override functionality."""

    def test_llm_service_kwargs_for_selfhosted(self):
        """Test LLM service kwargs for self-hosted provider."""
        config = CloudConfig(provider=CloudProvider.SELF_HOSTED, region="local")
        factory = CloudServiceFactory(config)

        service = factory.create_llm_service(
            provider="ollama",
            endpoint="http://localhost:11434",
            model_id="llama2",
            embedding_model="nomic-embed-text",
        )

        assert "LocalLLMAdapter" in type(service).__name__

    def test_secrets_service_kwargs_for_selfhosted(self):
        """Test secrets service kwargs for self-hosted provider."""
        config = CloudConfig(provider=CloudProvider.SELF_HOSTED, region="local")
        factory = CloudServiceFactory(config)

        service = factory.create_secrets_service(
            secrets_path="/custom/secrets",
            master_key="custom-master-key",
            key_file="/custom/keyfile",
        )

        assert "FileSecretsAdapter" in type(service).__name__
