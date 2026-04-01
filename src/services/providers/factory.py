"""
Project Aura - Cloud Service Factory

Factory pattern for creating cloud-agnostic service instances.
Automatically selects the appropriate implementation based on cloud provider.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
See ADR-049: Self-Hosted Deployment Strategy
"""

import logging
import os
from typing import Any, cast

from src.abstractions.cloud_provider import CloudConfig, CloudProvider
from src.abstractions.graph_database import GraphDatabaseService
from src.abstractions.llm_service import LLMService
from src.abstractions.secrets_service import SecretsService
from src.abstractions.storage_service import StorageService
from src.abstractions.vector_database import VectorDatabaseService

logger = logging.getLogger(__name__)


class CloudServiceFactory:
    """
    Factory for creating cloud service instances.

    Usage:
        factory = CloudServiceFactory.from_environment()
        graph_service = factory.create_graph_service()
        vector_service = factory.create_vector_service()
    """

    def __init__(self, config: CloudConfig) -> None:
        self.config = config
        self._cached_services: dict[str, Any] = {}

    @classmethod
    def from_environment(cls) -> "CloudServiceFactory":
        """Create factory from environment variables."""
        config = CloudConfig.from_environment()
        logger.info(
            f"CloudServiceFactory initialized for {config.provider.value} in {config.region}"
        )
        return cls(config)

    @classmethod
    def for_provider(
        cls, provider: CloudProvider, region: str
    ) -> "CloudServiceFactory":
        """Create factory for a specific provider."""
        config = CloudConfig(provider=provider, region=region)
        return cls(config)

    def create_graph_service(self, **kwargs: Any) -> GraphDatabaseService:
        """
        Create a graph database service instance.

        For AWS: Returns NeptuneGraphAdapter
        For Azure: Returns CosmosDBGraphService
        For Self-Hosted: Returns Neo4jGraphAdapter
        For Mock: Returns MockGraphService

        Returns:
            GraphDatabaseService implementation
        """
        cache_key = "graph_service"
        if cache_key in self._cached_services:
            return cast(GraphDatabaseService, self._cached_services[cache_key])

        service: GraphDatabaseService
        if self.config.provider in (CloudProvider.AWS, CloudProvider.AWS_GOVCLOUD):
            from src.services.providers.aws.neptune_adapter import NeptuneGraphAdapter

            service = NeptuneGraphAdapter(
                endpoint=kwargs.get("endpoint") or os.environ.get("NEPTUNE_ENDPOINT"),
                region=self.config.region,
            )
        elif self.config.provider in (
            CloudProvider.AZURE,
            CloudProvider.AZURE_GOVERNMENT,
        ):
            from src.services.providers.azure.cosmos_graph_service import (
                CosmosDBGraphService,
            )

            service = CosmosDBGraphService(
                endpoint=kwargs.get("endpoint") or os.environ.get("COSMOS_ENDPOINT"),
                database_name=kwargs.get("database")
                or os.environ.get("COSMOS_DATABASE", "aura-graph"),
                container_name=kwargs.get("container")
                or os.environ.get("COSMOS_CONTAINER", "code-entities"),
            )
        elif self.config.provider == CloudProvider.SELF_HOSTED:
            from src.services.providers.self_hosted.neo4j_graph_adapter import (
                Neo4jGraphAdapter,
            )

            service = Neo4jGraphAdapter(
                uri=kwargs.get("uri") or os.environ.get("NEO4J_URI"),
                username=kwargs.get("username") or os.environ.get("NEO4J_USERNAME"),
                password=kwargs.get("password") or os.environ.get("NEO4J_PASSWORD"),
                database=kwargs.get("database") or os.environ.get("NEO4J_DATABASE"),
            )
        else:
            from src.services.providers.mock.mock_graph_service import MockGraphService

            service = MockGraphService()

        self._cached_services[cache_key] = service
        return service

    def create_vector_service(self, **kwargs: Any) -> VectorDatabaseService:
        """
        Create a vector database service instance.

        For AWS: Returns OpenSearchVectorAdapter
        For Azure: Returns AzureAISearchService
        For Self-Hosted: Returns SelfHostedOpenSearchAdapter
        For Mock: Returns MockVectorService

        Returns:
            VectorDatabaseService implementation
        """
        cache_key = "vector_service"
        if cache_key in self._cached_services:
            return cast(VectorDatabaseService, self._cached_services[cache_key])

        service: VectorDatabaseService
        if self.config.provider in (CloudProvider.AWS, CloudProvider.AWS_GOVCLOUD):
            from src.services.providers.aws.opensearch_adapter import (
                OpenSearchVectorAdapter,
            )

            service = OpenSearchVectorAdapter(
                endpoint=kwargs.get("endpoint")
                or os.environ.get("OPENSEARCH_ENDPOINT"),
                region=self.config.region,
            )
        elif self.config.provider in (
            CloudProvider.AZURE,
            CloudProvider.AZURE_GOVERNMENT,
        ):
            from src.services.providers.azure.azure_ai_search_service import (
                AzureAISearchService,
            )

            service = AzureAISearchService(
                endpoint=kwargs.get("endpoint")
                or os.environ.get("AZURE_SEARCH_ENDPOINT"),
                index_name=kwargs.get("index")
                or os.environ.get("AZURE_SEARCH_INDEX", "aura-vectors"),
            )
        elif self.config.provider == CloudProvider.SELF_HOSTED:
            from src.services.providers.self_hosted.selfhosted_opensearch_adapter import (
                SelfHostedOpenSearchAdapter,
            )

            service = SelfHostedOpenSearchAdapter(
                endpoint=kwargs.get("endpoint")
                or os.environ.get("OPENSEARCH_ENDPOINT"),
                username=kwargs.get("username")
                or os.environ.get("OPENSEARCH_USERNAME"),
                password=kwargs.get("password")
                or os.environ.get("OPENSEARCH_PASSWORD"),
            )
        else:
            from src.services.providers.mock.mock_vector_service import (
                MockVectorService,
            )

            service = MockVectorService()

        self._cached_services[cache_key] = service
        return service

    def create_llm_service(self, **kwargs: Any) -> LLMService:
        """
        Create an LLM service instance.

        For AWS: Returns BedrockLLMAdapter
        For Azure: Returns AzureOpenAIService
        For Self-Hosted: Returns LocalLLMAdapter (vLLM, TGI, Ollama)
        For Mock: Returns MockLLMService

        Returns:
            LLMService implementation
        """
        cache_key = "llm_service"
        if cache_key in self._cached_services:
            return cast(LLMService, self._cached_services[cache_key])

        service: LLMService
        if self.config.provider in (CloudProvider.AWS, CloudProvider.AWS_GOVCLOUD):
            from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter

            service = BedrockLLMAdapter(region=self.config.region)
        elif self.config.provider in (
            CloudProvider.AZURE,
            CloudProvider.AZURE_GOVERNMENT,
        ):
            from src.services.providers.azure.azure_openai_service import (
                AzureOpenAIService,
            )

            service = AzureOpenAIService(
                endpoint=kwargs.get("endpoint")
                or os.environ.get("AZURE_OPENAI_ENDPOINT"),
                deployment_name=kwargs.get("deployment")
                or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
            )
        elif self.config.provider == CloudProvider.SELF_HOSTED:
            from src.services.providers.self_hosted.local_llm_adapter import (
                LocalLLMAdapter,
            )

            service = LocalLLMAdapter(
                provider=kwargs.get("provider") or os.environ.get("LLM_PROVIDER"),
                endpoint=kwargs.get("endpoint") or os.environ.get("LLM_ENDPOINT"),
                model_id=kwargs.get("model_id") or os.environ.get("LLM_MODEL_ID"),
                embedding_model=kwargs.get("embedding_model")
                or os.environ.get("EMBEDDING_MODEL"),
            )
        else:
            from src.services.providers.mock.mock_llm_service import MockLLMService

            service = MockLLMService()

        self._cached_services[cache_key] = service
        return service

    def create_storage_service(self, **kwargs: Any) -> StorageService:
        """
        Create a storage service instance.

        For AWS: Returns S3StorageAdapter
        For Azure: Returns AzureBlobService
        For Self-Hosted: Returns MinioStorageAdapter
        For Mock: Returns MockStorageService

        Returns:
            StorageService implementation
        """
        cache_key = "storage_service"
        if cache_key in self._cached_services:
            return cast(StorageService, self._cached_services[cache_key])

        service: StorageService
        if self.config.provider in (CloudProvider.AWS, CloudProvider.AWS_GOVCLOUD):
            from src.services.providers.aws.s3_adapter import S3StorageAdapter

            service = S3StorageAdapter(region=self.config.region)
        elif self.config.provider in (
            CloudProvider.AZURE,
            CloudProvider.AZURE_GOVERNMENT,
        ):
            from src.services.providers.azure.azure_blob_service import AzureBlobService

            service = AzureBlobService(
                account_url=kwargs.get("account_url")
                or os.environ.get("AZURE_STORAGE_ACCOUNT_URL"),
            )
        elif self.config.provider == CloudProvider.SELF_HOSTED:
            from src.services.providers.self_hosted.minio_storage_adapter import (
                MinioStorageAdapter,
            )

            service = MinioStorageAdapter(
                endpoint=kwargs.get("endpoint") or os.environ.get("MINIO_ENDPOINT"),
                access_key=kwargs.get("access_key")
                or os.environ.get("MINIO_ACCESS_KEY"),
                secret_key=kwargs.get("secret_key")
                or os.environ.get("MINIO_SECRET_KEY"),
                secure=kwargs.get("secure"),
            )
        else:
            from src.services.providers.mock.mock_storage_service import (
                MockStorageService,
            )

            service = MockStorageService()

        self._cached_services[cache_key] = service
        return service

    def create_secrets_service(self, **kwargs: Any) -> SecretsService:
        """
        Create a secrets service instance.

        For AWS: Returns SecretsManagerAdapter
        For Azure: Returns AzureKeyVaultService
        For Self-Hosted: Returns FileSecretsAdapter
        For Mock: Returns MockSecretsService

        Returns:
            SecretsService implementation
        """
        cache_key = "secrets_service"
        if cache_key in self._cached_services:
            return cast(SecretsService, self._cached_services[cache_key])

        service: SecretsService
        if self.config.provider in (CloudProvider.AWS, CloudProvider.AWS_GOVCLOUD):
            from src.services.providers.aws.secrets_manager_adapter import (
                SecretsManagerAdapter,
            )

            service = SecretsManagerAdapter(region=self.config.region)
        elif self.config.provider in (
            CloudProvider.AZURE,
            CloudProvider.AZURE_GOVERNMENT,
        ):
            from src.services.providers.azure.azure_keyvault_service import (
                AzureKeyVaultService,
            )

            service = AzureKeyVaultService(
                vault_url=kwargs.get("vault_url")
                or os.environ.get("AZURE_KEYVAULT_URL"),
            )
        elif self.config.provider == CloudProvider.SELF_HOSTED:
            from src.services.providers.self_hosted.file_secrets_adapter import (
                FileSecretsAdapter,
            )

            service = FileSecretsAdapter(
                secrets_path=kwargs.get("secrets_path")
                or os.environ.get("SECRETS_PATH"),
                master_key=kwargs.get("master_key")
                or os.environ.get("SECRETS_MASTER_KEY"),
                key_file=kwargs.get("key_file") or os.environ.get("SECRETS_KEY_FILE"),
            )
        else:
            from src.services.providers.mock.mock_secrets_service import (
                MockSecretsService,
            )

            service = MockSecretsService()

        self._cached_services[cache_key] = service
        return service

    def create_document_service(self, **kwargs: Any) -> Any:
        """
        Create a document storage service instance.

        For AWS: Returns DynamoDB client (boto3)
        For Azure: Returns CosmosDB client
        For Self-Hosted: Returns PostgresDocumentAdapter
        For Mock: Returns dict-based mock

        Returns:
            Document storage service implementation
        """
        cache_key = "document_service"
        if cache_key in self._cached_services:
            return self._cached_services[cache_key]

        service: Any
        if self.config.provider in (CloudProvider.AWS, CloudProvider.AWS_GOVCLOUD):
            # AWS uses boto3 DynamoDB client directly
            import boto3

            service = boto3.resource("dynamodb", region_name=self.config.region)
        elif self.config.provider in (
            CloudProvider.AZURE,
            CloudProvider.AZURE_GOVERNMENT,
        ):
            # Azure uses CosmosDB with SQL API
            from azure.cosmos import CosmosClient

            service = CosmosClient(
                url=kwargs.get("endpoint") or os.environ.get("COSMOS_ENDPOINT", ""),
                credential=kwargs.get("key") or os.environ.get("COSMOS_KEY", ""),
            )
        elif self.config.provider == CloudProvider.SELF_HOSTED:
            from src.services.providers.self_hosted.postgres_document_adapter import (
                PostgresDocumentAdapter,
            )

            service = PostgresDocumentAdapter(
                host=kwargs.get("host") or os.environ.get("POSTGRES_HOST"),
                port=kwargs.get("port"),
                database=kwargs.get("database") or os.environ.get("POSTGRES_DATABASE"),
                username=kwargs.get("username") or os.environ.get("POSTGRES_USERNAME"),
                password=kwargs.get("password") or os.environ.get("POSTGRES_PASSWORD"),
            )
        else:
            # Mock implementation using in-memory dict
            service = {"_mock": True, "_tables": {}}

        self._cached_services[cache_key] = service
        return service

    def clear_cache(self) -> None:
        """Clear cached service instances."""
        self._cached_services.clear()


# Convenience functions for direct service creation
_default_factory: CloudServiceFactory | None = None


def _get_factory() -> CloudServiceFactory:
    """Get or create the default factory."""
    global _default_factory
    if _default_factory is None:
        _default_factory = CloudServiceFactory.from_environment()
    return _default_factory


def get_graph_service(**kwargs: Any) -> GraphDatabaseService:
    """Get a graph database service instance."""
    return _get_factory().create_graph_service(**kwargs)


def get_vector_service(**kwargs: Any) -> VectorDatabaseService:
    """Get a vector database service instance."""
    return _get_factory().create_vector_service(**kwargs)


def get_llm_service(**kwargs: Any) -> LLMService:
    """Get an LLM service instance."""
    return _get_factory().create_llm_service(**kwargs)


def get_storage_service(**kwargs: Any) -> StorageService:
    """Get a storage service instance."""
    return _get_factory().create_storage_service(**kwargs)


def get_secrets_service(**kwargs: Any) -> SecretsService:
    """Get a secrets service instance."""
    return _get_factory().create_secrets_service(**kwargs)


def get_document_service(**kwargs: Any) -> Any:
    """Get a document storage service instance."""
    return _get_factory().create_document_service(**kwargs)
