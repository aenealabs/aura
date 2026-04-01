"""
Tests for Cloud Abstraction Layer.

Tests for CloudServiceFactory, mock providers, and service creation patterns.
"""

import platform

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
import os
from unittest.mock import MagicMock, patch

from src.abstractions.cloud_provider import CloudConfig, CloudProvider
from src.abstractions.graph_database import (
    EntityType,
    GraphEntity,
    GraphQueryResult,
    GraphRelationship,
    RelationshipType,
)
from src.abstractions.llm_service import LLMRequest
from src.abstractions.vector_database import IndexConfig, SearchResult, VectorDocument
from src.services.providers.factory import (
    CloudServiceFactory,
    get_graph_service,
    get_llm_service,
    get_secrets_service,
    get_storage_service,
    get_vector_service,
)
from src.services.providers.mock.mock_graph_service import MockGraphService
from src.services.providers.mock.mock_llm_service import MockLLMService
from src.services.providers.mock.mock_secrets_service import MockSecretsService
from src.services.providers.mock.mock_storage_service import MockStorageService
from src.services.providers.mock.mock_vector_service import MockVectorService


# Duck typing helper for forked process class identity issues
def assert_is_mock_service(obj, expected_class_name: str):
    """Check service type by class name (duck typing for forked processes)."""
    actual_name = obj.__class__.__name__
    assert (
        actual_name == expected_class_name
    ), f"Expected {expected_class_name} but got {actual_name}"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_graph_service():
    """Create mock graph service."""
    return MockGraphService()


@pytest.fixture
def mock_vector_service():
    """Create mock vector service."""
    return MockVectorService()


@pytest.fixture
def mock_llm_service():
    """Create mock LLM service."""
    return MockLLMService()


@pytest.fixture
def mock_storage_service():
    """Create mock storage service."""
    return MockStorageService()


@pytest.fixture
def mock_secrets_service():
    """Create mock secrets service."""
    return MockSecretsService()


@pytest.fixture
def sample_entity():
    """Sample graph entity."""
    return GraphEntity(
        id="entity-123",
        entity_type=EntityType.FUNCTION,
        name="test_function",
        file_path="src/test.py",
        repository="test-repo",
        properties={
            "line_start": 10,
            "line_end": 20,
            "parameters": ["arg1", "arg2"],
        },
    )


@pytest.fixture
def sample_entity_class():
    """Sample class entity."""
    return GraphEntity(
        id="entity-456",
        entity_type=EntityType.CLASS,
        name="TestClass",
        file_path="src/test.py",
        repository="test-repo",
        properties={"line_start": 1, "line_end": 50},
    )


@pytest.fixture
def sample_relationship(sample_entity, sample_entity_class):
    """Sample graph relationship."""
    return GraphRelationship(
        id="rel-123",
        source_id=sample_entity_class.id,
        target_id=sample_entity.id,
        relationship_type=RelationshipType.CONTAINS,
        properties={},
    )


@pytest.fixture
def sample_vector_document():
    """Sample vector document."""
    return VectorDocument(
        id="doc-123",
        content="def test_function(): pass",
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
        entity_type="function",
        file_path="src/test.py",
        repository="test-repo",
    )


@pytest.fixture
def sample_index_config():
    """Sample index configuration."""
    return IndexConfig(
        name="test-index",
        dimension=1536,
        similarity_metric="cosine",
    )


@pytest.fixture
def mock_factory():
    """Create factory for mock/testing."""
    config = CloudConfig(provider=CloudProvider.MOCK, region="local")
    return CloudServiceFactory(config)


@pytest.fixture
def aws_factory():
    """Create factory for AWS."""
    config = CloudConfig(provider=CloudProvider.AWS, region="us-east-1")
    return CloudServiceFactory(config)


# =============================================================================
# CloudServiceFactory Tests
# =============================================================================


class TestCloudServiceFactory:
    """Tests for CloudServiceFactory class."""

    def test_init(self, mock_factory):
        """Test factory initialization."""
        assert mock_factory.config.provider == CloudProvider.MOCK
        assert mock_factory._cached_services == {}

    def test_from_environment(self):
        """Test creating factory from environment."""
        with patch.dict(
            os.environ, {"CLOUD_PROVIDER": "mock", "AWS_REGION": "us-east-1"}
        ):
            factory = CloudServiceFactory.from_environment()
            assert factory is not None

    def test_for_provider(self):
        """Test creating factory for specific provider."""
        factory = CloudServiceFactory.for_provider(CloudProvider.AWS, "us-west-2")
        assert factory.config.provider == CloudProvider.AWS
        assert factory.config.region == "us-west-2"

    def test_clear_cache(self, mock_factory):
        """Test clearing service cache."""
        mock_factory._cached_services["test"] = "value"
        mock_factory.clear_cache()
        assert mock_factory._cached_services == {}


class TestFactoryGraphService:
    """Tests for graph service creation."""

    def test_create_graph_service_mock(self, mock_factory):
        """Test creating mock graph service."""
        service = mock_factory.create_graph_service()
        assert_is_mock_service(service, "MockGraphService")

    def test_create_graph_service_cached(self, mock_factory):
        """Test graph service is cached."""
        service1 = mock_factory.create_graph_service()
        service2 = mock_factory.create_graph_service()
        assert service1 is service2

    def test_create_graph_service_aws(self, aws_factory):
        """Test creating AWS Neptune adapter."""
        with patch(
            "src.services.providers.aws.neptune_adapter.NeptuneGraphAdapter"
        ) as mock_adapter:
            mock_adapter.return_value = MagicMock()
            _service = aws_factory.create_graph_service(endpoint="neptune.example.com")
            mock_adapter.assert_called_once()


class TestFactoryVectorService:
    """Tests for vector service creation."""

    def test_create_vector_service_mock(self, mock_factory):
        """Test creating mock vector service."""
        service = mock_factory.create_vector_service()
        assert_is_mock_service(service, "MockVectorService")

    def test_create_vector_service_cached(self, mock_factory):
        """Test vector service is cached."""
        service1 = mock_factory.create_vector_service()
        service2 = mock_factory.create_vector_service()
        assert service1 is service2


class TestFactoryLLMService:
    """Tests for LLM service creation."""

    def test_create_llm_service_mock(self, mock_factory):
        """Test creating mock LLM service."""
        service = mock_factory.create_llm_service()
        assert_is_mock_service(service, "MockLLMService")

    def test_create_llm_service_cached(self, mock_factory):
        """Test LLM service is cached."""
        service1 = mock_factory.create_llm_service()
        service2 = mock_factory.create_llm_service()
        assert service1 is service2


class TestFactoryStorageService:
    """Tests for storage service creation."""

    def test_create_storage_service_mock(self, mock_factory):
        """Test creating mock storage service."""
        service = mock_factory.create_storage_service()
        assert_is_mock_service(service, "MockStorageService")


class TestFactorySecretsService:
    """Tests for secrets service creation."""

    def test_create_secrets_service_mock(self, mock_factory):
        """Test creating mock secrets service."""
        service = mock_factory.create_secrets_service()
        assert_is_mock_service(service, "MockSecretsService")


# =============================================================================
# MockGraphService Tests
# =============================================================================


class TestMockGraphService:
    """Tests for MockGraphService."""

    @pytest.mark.asyncio
    async def test_connect(self, mock_graph_service):
        """Test connection."""
        result = await mock_graph_service.connect()
        assert result is True
        assert await mock_graph_service.is_connected() is True

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_graph_service):
        """Test disconnection."""
        await mock_graph_service.connect()
        await mock_graph_service.disconnect()
        assert await mock_graph_service.is_connected() is False

    @pytest.mark.asyncio
    async def test_add_entity(self, mock_graph_service, sample_entity):
        """Test adding an entity."""
        entity_id = await mock_graph_service.add_entity(sample_entity)
        assert entity_id == sample_entity.id

    @pytest.mark.asyncio
    async def test_get_entity(self, mock_graph_service, sample_entity):
        """Test getting an entity."""
        await mock_graph_service.add_entity(sample_entity)
        result = await mock_graph_service.get_entity(sample_entity.id)
        assert result is not None
        assert result.name == sample_entity.name

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, mock_graph_service):
        """Test getting non-existent entity."""
        result = await mock_graph_service.get_entity("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_entity(self, mock_graph_service, sample_entity):
        """Test updating an entity."""
        await mock_graph_service.add_entity(sample_entity)
        sample_entity.name = "updated_function"
        result = await mock_graph_service.update_entity(sample_entity)
        assert result is True

        updated = await mock_graph_service.get_entity(sample_entity.id)
        assert updated.name == "updated_function"

    @pytest.mark.asyncio
    async def test_update_entity_not_found(self, mock_graph_service, sample_entity):
        """Test updating non-existent entity."""
        result = await mock_graph_service.update_entity(sample_entity)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_entity(self, mock_graph_service, sample_entity):
        """Test deleting an entity."""
        await mock_graph_service.add_entity(sample_entity)
        result = await mock_graph_service.delete_entity(sample_entity.id)
        assert result is True

        deleted = await mock_graph_service.get_entity(sample_entity.id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_add_relationship(self, mock_graph_service, sample_relationship):
        """Test adding a relationship."""
        rel_id = await mock_graph_service.add_relationship(sample_relationship)
        assert rel_id == sample_relationship.id

    @pytest.mark.asyncio
    async def test_get_relationships(
        self,
        mock_graph_service,
        sample_entity,
        sample_entity_class,
        sample_relationship,
    ):
        """Test getting relationships."""
        await mock_graph_service.add_entity(sample_entity)
        await mock_graph_service.add_entity(sample_entity_class)
        await mock_graph_service.add_relationship(sample_relationship)

        rels = await mock_graph_service.get_relationships(
            sample_entity_class.id, direction="out"
        )
        assert len(rels) == 1

    @pytest.mark.asyncio
    async def test_delete_relationship(self, mock_graph_service, sample_relationship):
        """Test deleting a relationship."""
        await mock_graph_service.add_relationship(sample_relationship)
        result = await mock_graph_service.delete_relationship(sample_relationship.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_find_related_code(
        self,
        mock_graph_service,
        sample_entity,
        sample_entity_class,
        sample_relationship,
    ):
        """Test finding related code entities."""
        await mock_graph_service.add_entity(sample_entity)
        await mock_graph_service.add_entity(sample_entity_class)
        await mock_graph_service.add_relationship(sample_relationship)

        result = await mock_graph_service.find_related_code(sample_entity_class.id)

        assert isinstance(result, GraphQueryResult)
        assert len(result.entities) >= 1

    @pytest.mark.asyncio
    async def test_search_by_name(
        self, mock_graph_service, sample_entity, sample_entity_class
    ):
        """Test searching by name pattern."""
        await mock_graph_service.add_entity(sample_entity)
        await mock_graph_service.add_entity(sample_entity_class)

        results = await mock_graph_service.search_by_name("test")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_delete_by_repository(self, mock_graph_service, sample_entity):
        """Test deleting entities by repository."""
        await mock_graph_service.add_entity(sample_entity)

        count = await mock_graph_service.delete_by_repository("test-repo")
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_health(self, mock_graph_service):
        """Test health check."""
        health = await mock_graph_service.get_health()
        assert health["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_statistics(self, mock_graph_service, sample_entity):
        """Test statistics."""
        await mock_graph_service.add_entity(sample_entity)

        stats = await mock_graph_service.get_statistics()
        assert stats["entity_count"] == 1


# =============================================================================
# MockVectorService Tests
# =============================================================================


class TestMockVectorService:
    """Tests for MockVectorService."""

    @pytest.mark.asyncio
    async def test_connect(self, mock_vector_service):
        """Test connection."""
        result = await mock_vector_service.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_vector_service):
        """Test disconnection."""
        await mock_vector_service.connect()
        await mock_vector_service.disconnect()
        assert await mock_vector_service.is_connected() is False

    @pytest.mark.asyncio
    async def test_create_index(self, mock_vector_service, sample_index_config):
        """Test creating an index."""
        result = await mock_vector_service.create_index(sample_index_config)
        assert result is True

        exists = await mock_vector_service.index_exists("test-index")
        assert exists is True

    @pytest.mark.asyncio
    async def test_delete_index(self, mock_vector_service, sample_index_config):
        """Test deleting an index."""
        await mock_vector_service.create_index(sample_index_config)
        result = await mock_vector_service.delete_index("test-index")
        assert result is True

    @pytest.mark.asyncio
    async def test_index_document(self, mock_vector_service, sample_vector_document):
        """Test indexing a document."""
        doc_id = await mock_vector_service.index_document(
            "default", sample_vector_document
        )
        assert doc_id == sample_vector_document.id

    @pytest.mark.asyncio
    async def test_get_document(self, mock_vector_service, sample_vector_document):
        """Test getting a document."""
        await mock_vector_service.index_document("default", sample_vector_document)
        result = await mock_vector_service.get_document(
            "default", sample_vector_document.id
        )
        assert result is not None
        assert result.content == sample_vector_document.content

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, mock_vector_service):
        """Test getting non-existent document."""
        result = await mock_vector_service.get_document("default", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_document(self, mock_vector_service, sample_vector_document):
        """Test deleting a document."""
        await mock_vector_service.index_document("default", sample_vector_document)
        result = await mock_vector_service.delete_document(
            "default", sample_vector_document.id
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_search_similar(self, mock_vector_service, sample_vector_document):
        """Test vector search."""
        await mock_vector_service.index_document("default", sample_vector_document)

        results = await mock_vector_service.search_similar(
            index_name="default",
            query_embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            k=10,
        )
        assert len(results) >= 1
        assert isinstance(results[0], SearchResult)

    @pytest.mark.asyncio
    async def test_hybrid_search(self, mock_vector_service, sample_vector_document):
        """Test hybrid search."""
        await mock_vector_service.index_document("default", sample_vector_document)

        results = await mock_vector_service.hybrid_search(
            index_name="default",
            query_text="test function",
            query_embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            k=10,
        )
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_bulk_index(self, mock_vector_service, sample_vector_document):
        """Test bulk indexing."""
        docs = [sample_vector_document]
        result = await mock_vector_service.bulk_index("default", docs)
        assert result["success_count"] == 1

    @pytest.mark.asyncio
    async def test_delete_by_repository(
        self, mock_vector_service, sample_vector_document
    ):
        """Test deleting by repository."""
        await mock_vector_service.index_document("default", sample_vector_document)

        count = await mock_vector_service.delete_by_repository("default", "test-repo")
        assert count >= 0

    @pytest.mark.asyncio
    async def test_get_health(self, mock_vector_service):
        """Test health check."""
        health = await mock_vector_service.get_health()
        assert health["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_index_stats(self, mock_vector_service, sample_vector_document):
        """Test index statistics."""
        await mock_vector_service.index_document("default", sample_vector_document)
        stats = await mock_vector_service.get_index_stats("default")
        assert "document_count" in stats


# =============================================================================
# MockLLMService Tests
# =============================================================================


class TestMockLLMService:
    """Tests for MockLLMService."""

    @pytest.mark.asyncio
    async def test_initialize(self, mock_llm_service):
        """Test initialization."""
        result = await mock_llm_service.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_llm_service):
        """Test shutdown."""
        await mock_llm_service.initialize()
        await mock_llm_service.shutdown()

    @pytest.mark.asyncio
    async def test_invoke(self, mock_llm_service):
        """Test invoke."""
        request = LLMRequest(prompt="Hello, world!")
        response = await mock_llm_service.invoke(request)

        assert response is not None
        assert response.content != ""
        assert response.input_tokens > 0

    @pytest.mark.asyncio
    async def test_generate_code(self, mock_llm_service):
        """Test code generation."""
        response = await mock_llm_service.generate_code(
            prompt="Write a hello world function",
            language="python",
        )
        assert response is not None
        assert "def" in response.content

    @pytest.mark.asyncio
    async def test_analyze_code(self, mock_llm_service):
        """Test code analysis."""
        response = await mock_llm_service.analyze_code(
            code="def hello(): pass",
            language="python",
            analysis_type="security",
        )
        assert response is not None

    @pytest.mark.asyncio
    async def test_generate_embedding(self, mock_llm_service):
        """Test embedding generation."""
        embedding = await mock_llm_service.generate_embedding("test text")
        assert isinstance(embedding, list)
        assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self, mock_llm_service):
        """Test batch embedding generation."""
        texts = ["text 1", "text 2", "text 3"]
        embeddings = await mock_llm_service.generate_embeddings_batch(texts)
        assert len(embeddings) == 3

    @pytest.mark.asyncio
    async def test_list_available_models(self, mock_llm_service):
        """Test listing models."""
        models = await mock_llm_service.list_available_models()
        assert len(models) > 0

    @pytest.mark.asyncio
    async def test_health_check(self, mock_llm_service):
        """Test health check."""
        health = await mock_llm_service.health_check()
        assert health["status"] == "healthy"


# =============================================================================
# MockStorageService Tests
# =============================================================================


class TestMockStorageService:
    """Tests for MockStorageService."""

    @pytest.mark.asyncio
    async def test_connect(self, mock_storage_service):
        """Test connection."""
        result = await mock_storage_service.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_create_bucket(self, mock_storage_service):
        """Test creating bucket."""
        result = await mock_storage_service.create_bucket("test-bucket")
        assert result is True

        exists = await mock_storage_service.bucket_exists("test-bucket")
        assert exists is True

    @pytest.mark.asyncio
    async def test_delete_bucket(self, mock_storage_service):
        """Test deleting bucket."""
        await mock_storage_service.create_bucket("test-bucket")
        result = await mock_storage_service.delete_bucket("test-bucket")
        assert result is True

    @pytest.mark.asyncio
    async def test_list_buckets(self, mock_storage_service):
        """Test listing buckets."""
        await mock_storage_service.create_bucket("bucket1")
        await mock_storage_service.create_bucket("bucket2")

        buckets = await mock_storage_service.list_buckets()
        assert len(buckets) >= 2

    @pytest.mark.asyncio
    async def test_upload_object(self, mock_storage_service):
        """Test uploading object."""
        result = await mock_storage_service.upload_object(
            bucket="test-bucket",
            key="test/file.txt",
            data=b"Hello, world!",
        )
        assert result is not None
        assert result.key == "test/file.txt"

    @pytest.mark.asyncio
    async def test_download_object(self, mock_storage_service):
        """Test downloading object."""
        await mock_storage_service.upload_object(
            bucket="test-bucket",
            key="test/file.txt",
            data=b"Hello, world!",
        )

        data = await mock_storage_service.download_object(
            bucket="test-bucket",
            key="test/file.txt",
        )
        assert data == b"Hello, world!"

    @pytest.mark.asyncio
    async def test_delete_object(self, mock_storage_service):
        """Test deleting object."""
        await mock_storage_service.upload_object(
            bucket="test-bucket",
            key="test/file.txt",
            data=b"data",
        )

        result = await mock_storage_service.delete_object(
            bucket="test-bucket",
            key="test/file.txt",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_list_objects(self, mock_storage_service):
        """Test listing objects."""
        await mock_storage_service.upload_object(
            bucket="test-bucket",
            key="prefix/file1.txt",
            data=b"data1",
        )
        await mock_storage_service.upload_object(
            bucket="test-bucket",
            key="prefix/file2.txt",
            data=b"data2",
        )

        objects, _ = await mock_storage_service.list_objects(
            bucket="test-bucket",
            prefix="prefix/",
        )
        assert len(objects) == 2

    @pytest.mark.asyncio
    async def test_object_exists(self, mock_storage_service):
        """Test checking object existence."""
        await mock_storage_service.upload_object(
            bucket="test-bucket",
            key="test.txt",
            data=b"data",
        )

        assert (
            await mock_storage_service.object_exists("test-bucket", "test.txt") is True
        )
        assert (
            await mock_storage_service.object_exists("test-bucket", "nonexistent.txt")
            is False
        )

    @pytest.mark.asyncio
    async def test_copy_object(self, mock_storage_service):
        """Test copying object."""
        await mock_storage_service.upload_object(
            bucket="source-bucket",
            key="source.txt",
            data=b"data",
        )

        result = await mock_storage_service.copy_object(
            source_bucket="source-bucket",
            source_key="source.txt",
            dest_bucket="dest-bucket",
            dest_key="dest.txt",
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_generate_presigned_url(self, mock_storage_service):
        """Test generating presigned URL."""
        url = await mock_storage_service.generate_presigned_url(
            bucket="test-bucket",
            key="test.txt",
        )
        assert url is not None
        assert "mock-storage" in url.url

    @pytest.mark.asyncio
    async def test_get_health(self, mock_storage_service):
        """Test health check."""
        health = await mock_storage_service.get_health()
        assert health["status"] == "healthy"


# =============================================================================
# MockSecretsService Tests
# =============================================================================


class TestMockSecretsService:
    """Tests for MockSecretsService."""

    @pytest.mark.asyncio
    async def test_connect(self, mock_secrets_service):
        """Test connection."""
        result = await mock_secrets_service.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_create_secret(self, mock_secrets_service):
        """Test creating a secret."""
        secret = await mock_secrets_service.create_secret(
            "test-secret",
            "secret-value",
        )
        assert secret.name == "test-secret"
        assert secret.value == "secret-value"

    @pytest.mark.asyncio
    async def test_get_secret(self, mock_secrets_service):
        """Test getting a secret."""
        await mock_secrets_service.create_secret("test-secret", "secret-value")
        secret = await mock_secrets_service.get_secret("test-secret")
        assert secret is not None
        assert secret.value == "secret-value"

    @pytest.mark.asyncio
    async def test_get_secret_not_found(self, mock_secrets_service):
        """Test getting non-existent secret."""
        secret = await mock_secrets_service.get_secret("nonexistent")
        assert secret is None

    @pytest.mark.asyncio
    async def test_get_secret_value(self, mock_secrets_service):
        """Test getting secret value."""
        await mock_secrets_service.create_secret("test-secret", "value123")
        value = await mock_secrets_service.get_secret_value("test-secret")
        assert value == "value123"

    @pytest.mark.asyncio
    async def test_get_secret_value_json_key(self, mock_secrets_service):
        """Test getting JSON secret key."""
        await mock_secrets_service.create_secret(
            "json-secret",
            {"username": "admin", "password": "secret"},
        )
        value = await mock_secrets_service.get_secret_value("json-secret", "username")
        assert value == "admin"

    @pytest.mark.asyncio
    async def test_update_secret(self, mock_secrets_service):
        """Test updating a secret."""
        await mock_secrets_service.create_secret("test-secret", "old-value")
        secret = await mock_secrets_service.update_secret("test-secret", "new-value")
        assert secret.value == "new-value"

    @pytest.mark.asyncio
    async def test_delete_secret(self, mock_secrets_service):
        """Test deleting a secret."""
        await mock_secrets_service.create_secret("delete-me", "value")
        result = await mock_secrets_service.delete_secret("delete-me")
        assert result is True

        secret = await mock_secrets_service.get_secret("delete-me")
        assert secret is None

    @pytest.mark.asyncio
    async def test_secret_exists(self, mock_secrets_service):
        """Test checking secret existence."""
        await mock_secrets_service.create_secret("exists", "value")

        assert await mock_secrets_service.secret_exists("exists") is True
        assert await mock_secrets_service.secret_exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_list_secrets(self, mock_secrets_service):
        """Test listing secrets."""
        await mock_secrets_service.create_secret("secret1", "value1")
        await mock_secrets_service.create_secret("secret2", "value2")

        secrets = await mock_secrets_service.list_secrets()
        assert len(secrets) >= 2

    @pytest.mark.asyncio
    async def test_list_secrets_with_prefix(self, mock_secrets_service):
        """Test listing secrets with prefix."""
        await mock_secrets_service.create_secret("app/secret1", "value1")
        await mock_secrets_service.create_secret("app/secret2", "value2")
        await mock_secrets_service.create_secret("other/secret", "value3")

        secrets = await mock_secrets_service.list_secrets(prefix="app/")
        assert len(secrets) == 2

    @pytest.mark.asyncio
    async def test_get_health(self, mock_secrets_service):
        """Test health check."""
        health = await mock_secrets_service.get_health()
        assert health["status"] == "healthy"


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_graph_service(self):
        """Test get_graph_service function."""
        with patch.dict(os.environ, {"CLOUD_PROVIDER": "mock"}):
            import src.services.providers.factory as factory_module

            factory_module._default_factory = None

            service = get_graph_service()
            assert service is not None

    def test_get_vector_service(self):
        """Test get_vector_service function."""
        with patch.dict(os.environ, {"CLOUD_PROVIDER": "mock"}):
            import src.services.providers.factory as factory_module

            factory_module._default_factory = None

            service = get_vector_service()
            assert service is not None

    def test_get_llm_service(self):
        """Test get_llm_service function."""
        with patch.dict(os.environ, {"CLOUD_PROVIDER": "mock"}):
            import src.services.providers.factory as factory_module

            factory_module._default_factory = None

            service = get_llm_service()
            assert service is not None

    def test_get_storage_service(self):
        """Test get_storage_service function."""
        with patch.dict(os.environ, {"CLOUD_PROVIDER": "mock"}):
            import src.services.providers.factory as factory_module

            factory_module._default_factory = None

            service = get_storage_service()
            assert service is not None

    def test_get_secrets_service(self):
        """Test get_secrets_service function."""
        with patch.dict(os.environ, {"CLOUD_PROVIDER": "mock"}):
            import src.services.providers.factory as factory_module

            factory_module._default_factory = None

            service = get_secrets_service()
            assert service is not None
