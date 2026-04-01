"""
Project Aura - Cloud Abstraction Layer Tests

Tests for the multi-cloud abstraction layer (ADR-004).
Tests cover abstract interfaces, provider factory, and mock implementations.
"""

import platform

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.abstractions.cloud_provider import CloudConfig, CloudProvider, CloudRegion
from src.abstractions.graph_database import (
    EntityType,
    GraphEntity,
    GraphRelationship,
    RelationshipType,
)
from src.abstractions.llm_service import LLMRequest, LLMResponse
from src.abstractions.secrets_service import Secret
from src.abstractions.storage_service import StorageClass, StorageObject
from src.abstractions.vector_database import IndexConfig, SearchResult, VectorDocument
from src.services.providers.factory import CloudServiceFactory
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
# Cloud Provider Tests
# =============================================================================


class TestCloudProvider:
    """Tests for CloudProvider enum and CloudConfig."""

    def test_cloud_provider_values(self):
        """Test cloud provider enum values."""
        assert CloudProvider.AWS.value == "aws"
        assert CloudProvider.AWS_GOVCLOUD.value == "aws_govcloud"
        assert CloudProvider.AZURE.value == "azure"
        assert CloudProvider.AZURE_GOVERNMENT.value == "azure_government"
        assert CloudProvider.MOCK.value == "mock"

    def test_is_govcloud(self):
        """Test government cloud detection."""
        assert CloudProvider.AWS_GOVCLOUD.is_govcloud is True
        assert CloudProvider.AZURE_GOVERNMENT.is_govcloud is True
        assert CloudProvider.AWS.is_govcloud is False
        assert CloudProvider.AZURE.is_govcloud is False

    def test_partition(self):
        """Test AWS partition and Azure environment."""
        assert CloudProvider.AWS.partition == "aws"
        assert CloudProvider.AWS_GOVCLOUD.partition == "aws-us-gov"
        assert CloudProvider.AZURE.partition == "public"
        assert CloudProvider.AZURE_GOVERNMENT.partition == "usgovernment"

    def test_cloud_config_from_environment(self, monkeypatch):
        """Test CloudConfig creation from environment."""
        monkeypatch.setenv("CLOUD_PROVIDER", "azure_government")
        monkeypatch.setenv("CLOUD_REGION", "usgovvirginia")

        config = CloudConfig.from_environment()
        assert config.provider == CloudProvider.AZURE_GOVERNMENT
        assert config.region == "usgovvirginia"

    def test_cloud_region(self):
        """Test CloudRegion dataclass."""
        region = CloudRegion(
            provider=CloudProvider.AWS_GOVCLOUD,
            region_code="us-gov-west-1",
            display_name="AWS GovCloud (US-West)",
        )
        assert region.is_govcloud is True
        assert region.region_code == "us-gov-west-1"


# =============================================================================
# Data Model Tests
# =============================================================================


class TestDataModels:
    """Tests for data model classes."""

    def test_graph_entity_serialization(self):
        """Test GraphEntity to_dict and from_dict."""
        entity = GraphEntity(
            id="entity-123",
            entity_type=EntityType.FUNCTION,
            name="my_function",
            repository="test-repo",
            file_path="src/utils.py",
            properties={"line_number": 42},
        )

        data = entity.to_dict()
        assert data["id"] == "entity-123"
        assert data["entity_type"] == "function"
        assert data["properties"]["line_number"] == 42

        restored = GraphEntity.from_dict(data)
        assert restored.id == entity.id
        assert restored.entity_type == entity.entity_type

    def test_graph_relationship_serialization(self):
        """Test GraphRelationship serialization."""
        rel = GraphRelationship(
            id="rel-456",
            relationship_type=RelationshipType.CALLS,
            source_id="entity-1",
            target_id="entity-2",
            weight=0.8,
        )

        data = rel.to_dict()
        assert data["relationship_type"] == "calls"
        assert data["weight"] == 0.8

        restored = GraphRelationship.from_dict(data)
        assert restored.relationship_type == RelationshipType.CALLS

    def test_vector_document_serialization(self):
        """Test VectorDocument serialization."""
        doc = VectorDocument(
            id="doc-789",
            content="def hello(): pass",
            embedding=[0.1, 0.2, 0.3],
            repository="test-repo",
            file_path="src/hello.py",
            entity_type="function",
        )

        data = doc.to_dict()
        assert data["embedding"] == [0.1, 0.2, 0.3]

        restored = VectorDocument.from_dict(data)
        assert restored.embedding == doc.embedding

    def test_llm_request_to_dict(self):
        """Test LLMRequest serialization."""
        request = LLMRequest(
            prompt="Write a function",
            system_prompt="You are a helpful assistant",
            max_tokens=1000,
        )

        data = request.to_dict()
        assert data["prompt"] == "Write a function"
        assert data["max_tokens"] == 1000

    def test_llm_response_total_tokens(self):
        """Test LLMResponse total_tokens property."""
        response = LLMResponse(
            content="Hello",
            model_id="test-model",
            input_tokens=100,
            output_tokens=50,
            latency_ms=200.0,
            finish_reason="stop",
        )

        assert response.total_tokens == 150

    def test_storage_object_serialization(self):
        """Test StorageObject serialization."""
        obj = StorageObject(
            key="path/to/file.txt",
            bucket="my-bucket",
            size_bytes=1024,
            content_type="text/plain",
            storage_class=StorageClass.STANDARD,
        )

        data = obj.to_dict()
        assert data["size_bytes"] == 1024
        assert data["storage_class"] == "standard"

    def test_secret_get_value(self):
        """Test Secret.get_value for JSON secrets."""
        secret = Secret(
            name="db-credentials",
            value={"username": "admin", "password": "secret123"},
        )

        assert secret.is_json is True
        assert secret.get_value("username") == "admin"
        assert secret.get_value() == {"username": "admin", "password": "secret123"}


# =============================================================================
# Mock Graph Service Tests
# =============================================================================


class TestMockGraphService:
    """Tests for MockGraphService."""

    @pytest.fixture
    async def graph_service(self):
        service = MockGraphService()
        await service.connect()
        return service

    @pytest.mark.asyncio
    async def test_connect_disconnect(self, graph_service):
        """Test connection lifecycle."""
        assert await graph_service.is_connected() is True
        await graph_service.disconnect()
        assert await graph_service.is_connected() is False

    @pytest.mark.asyncio
    async def test_add_and_get_entity(self, graph_service):
        """Test adding and retrieving entities."""
        entity = GraphEntity(
            id="test-entity-1",
            entity_type=EntityType.CLASS,
            name="MyClass",
            repository="test-repo",
            file_path="src/myclass.py",
        )

        entity_id = await graph_service.add_entity(entity)
        assert entity_id == "test-entity-1"

        retrieved = await graph_service.get_entity("test-entity-1")
        assert retrieved is not None
        assert retrieved.name == "MyClass"

    @pytest.mark.asyncio
    async def test_update_entity(self, graph_service):
        """Test entity updates."""
        entity = GraphEntity(
            id="update-test",
            entity_type=EntityType.FUNCTION,
            name="original_name",
            repository="test-repo",
            file_path="src/test.py",
        )
        await graph_service.add_entity(entity)

        entity.name = "updated_name"
        result = await graph_service.update_entity(entity)
        assert result is True

        retrieved = await graph_service.get_entity("update-test")
        assert retrieved.name == "updated_name"

    @pytest.mark.asyncio
    async def test_delete_entity(self, graph_service):
        """Test entity deletion."""
        entity = GraphEntity(
            id="delete-test",
            entity_type=EntityType.FILE,
            name="test.py",
            repository="test-repo",
            file_path="src/test.py",
        )
        await graph_service.add_entity(entity)

        result = await graph_service.delete_entity("delete-test")
        assert result is True

        retrieved = await graph_service.get_entity("delete-test")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_add_and_get_relationships(self, graph_service):
        """Test relationship operations."""
        entity1 = GraphEntity(
            id="entity-a",
            entity_type=EntityType.FUNCTION,
            name="func_a",
            repository="repo",
            file_path="a.py",
        )
        entity2 = GraphEntity(
            id="entity-b",
            entity_type=EntityType.FUNCTION,
            name="func_b",
            repository="repo",
            file_path="b.py",
        )
        await graph_service.add_entity(entity1)
        await graph_service.add_entity(entity2)

        rel = GraphRelationship(
            id="rel-1",
            relationship_type=RelationshipType.CALLS,
            source_id="entity-a",
            target_id="entity-b",
        )
        await graph_service.add_relationship(rel)

        rels = await graph_service.get_relationships("entity-a", direction="out")
        assert len(rels) == 1
        assert rels[0].target_id == "entity-b"

    @pytest.mark.asyncio
    async def test_search_by_name(self, graph_service):
        """Test name search."""
        for i in range(5):
            entity = GraphEntity(
                id=f"search-{i}",
                entity_type=EntityType.FUNCTION,
                name=f"test_function_{i}",
                repository="test-repo",
                file_path="test.py",
            )
            await graph_service.add_entity(entity)

        results = await graph_service.search_by_name("test_function")
        assert len(results) == 5

        results = await graph_service.search_by_name("function_2")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_delete_by_repository(self, graph_service):
        """Test bulk delete by repository."""
        for i in range(3):
            entity = GraphEntity(
                id=f"bulk-{i}",
                entity_type=EntityType.FILE,
                name=f"file_{i}.py",
                repository="bulk-repo",
                file_path=f"file_{i}.py",
            )
            await graph_service.add_entity(entity)

        count = await graph_service.delete_by_repository("bulk-repo")
        assert count == 3


# =============================================================================
# Mock Vector Service Tests
# =============================================================================


class TestMockVectorService:
    """Tests for MockVectorService."""

    @pytest.fixture
    async def vector_service(self):
        service = MockVectorService()
        await service.connect()
        await service.create_index(IndexConfig(name="test-index", dimension=1536))
        return service

    @pytest.mark.asyncio
    async def test_index_operations(self, vector_service):
        """Test index creation and deletion."""
        exists = await vector_service.index_exists("test-index")
        assert exists is True

        await vector_service.delete_index("test-index")
        exists = await vector_service.index_exists("test-index")
        assert exists is False

    @pytest.mark.asyncio
    async def test_document_operations(self, vector_service):
        """Test document indexing and retrieval."""
        doc = VectorDocument(
            id="doc-1",
            content="def hello(): return 'Hello, World!'",
            embedding=[0.1] * 1536,
            repository="test-repo",
            file_path="hello.py",
            entity_type="function",
        )

        doc_id = await vector_service.index_document("test-index", doc)
        assert doc_id == "doc-1"

        retrieved = await vector_service.get_document("test-index", "doc-1")
        assert retrieved is not None
        assert retrieved.content == doc.content

    @pytest.mark.asyncio
    async def test_similarity_search(self, vector_service):
        """Test vector similarity search."""
        # Index documents with different embeddings
        for i in range(5):
            doc = VectorDocument(
                id=f"search-doc-{i}",
                content=f"Document content {i}",
                embedding=[0.1 + i * 0.1] * 1536,  # Varying embeddings
                repository="test-repo",
                file_path=f"doc_{i}.py",
                entity_type="file",
            )
            await vector_service.index_document("test-index", doc)

        # Search with query similar to doc-4
        query = [0.5] * 1536
        results = await vector_service.search_similar("test-index", query, k=3)

        assert len(results) <= 3
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_hybrid_search(self, vector_service):
        """Test hybrid search."""
        doc = VectorDocument(
            id="hybrid-doc",
            content="Python function for data processing",
            embedding=[0.5] * 1536,
            repository="test-repo",
            file_path="data.py",
            entity_type="function",
        )
        await vector_service.index_document("test-index", doc)

        results = await vector_service.hybrid_search(
            index_name="test-index",
            query_text="data processing",
            query_embedding=[0.5] * 1536,
            k=5,
        )

        assert len(results) >= 1
        assert "data" in results[0].document.content.lower()


# =============================================================================
# Mock LLM Service Tests
# =============================================================================


class TestMockLLMService:
    """Tests for MockLLMService."""

    @pytest.fixture
    async def llm_service(self):
        service = MockLLMService()
        await service.initialize()
        return service

    @pytest.mark.asyncio
    async def test_invoke(self, llm_service):
        """Test basic invocation."""
        request = LLMRequest(prompt="Write a hello world function")
        response = await llm_service.invoke(request)

        assert response.content is not None
        assert response.model_id == "mock-model"
        assert response.input_tokens > 0
        assert response.latency_ms > 0

    @pytest.mark.asyncio
    async def test_generate_code(self, llm_service):
        """Test code generation."""
        response = await llm_service.generate_code(
            prompt="Create a sorting function",
            language="python",
        )

        assert "def" in response.content
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_analyze_code(self, llm_service):
        """Test code analysis."""
        code = "def foo(x): return x * 2"
        response = await llm_service.analyze_code(
            code=code,
            language="python",
            analysis_type="quality",
        )

        assert "analysis" in response.content.lower()

    @pytest.mark.asyncio
    async def test_generate_embedding(self, llm_service):
        """Test embedding generation."""
        embedding = await llm_service.generate_embedding("test text")

        assert isinstance(embedding, list)
        assert len(embedding) == 1536
        assert all(isinstance(v, float) for v in embedding)

    @pytest.mark.asyncio
    async def test_budget_check(self, llm_service):
        """Test budget checking."""
        budget = await llm_service.check_budget(daily_limit=100.0, monthly_limit=1000.0)

        assert budget["daily_exceeded"] is False
        assert budget["monthly_exceeded"] is False
        assert budget["daily_remaining"] == 100.0


# =============================================================================
# Mock Storage Service Tests
# =============================================================================


class TestMockStorageService:
    """Tests for MockStorageService."""

    @pytest.fixture
    async def storage_service(self):
        service = MockStorageService()
        await service.connect()
        await service.create_bucket("test-bucket")
        return service

    @pytest.mark.asyncio
    async def test_bucket_operations(self, storage_service):
        """Test bucket creation and deletion."""
        exists = await storage_service.bucket_exists("test-bucket")
        assert exists is True

        await storage_service.delete_bucket("test-bucket")
        exists = await storage_service.bucket_exists("test-bucket")
        assert exists is False

    @pytest.mark.asyncio
    async def test_upload_download(self, storage_service):
        """Test object upload and download."""
        content = b"Hello, World!"
        obj = await storage_service.upload_object(
            bucket="test-bucket",
            key="hello.txt",
            data=content,
            content_type="text/plain",
        )

        assert obj.size_bytes == len(content)

        downloaded = await storage_service.download_object("test-bucket", "hello.txt")
        assert downloaded == content

    @pytest.mark.asyncio
    async def test_object_info(self, storage_service):
        """Test getting object info."""
        await storage_service.upload_object(
            bucket="test-bucket",
            key="info-test.txt",
            data=b"Test data",
        )

        info = await storage_service.get_object_info("test-bucket", "info-test.txt")
        assert info is not None
        assert info.key == "info-test.txt"

    @pytest.mark.asyncio
    async def test_list_objects(self, storage_service):
        """Test listing objects."""
        for i in range(3):
            await storage_service.upload_object(
                bucket="test-bucket",
                key=f"list-{i}.txt",
                data=f"Content {i}".encode(),
            )

        objects, _ = await storage_service.list_objects("test-bucket")
        assert len(objects) >= 3

    @pytest.mark.asyncio
    async def test_presigned_url(self, storage_service):
        """Test presigned URL generation."""
        await storage_service.upload_object(
            bucket="test-bucket",
            key="presigned.txt",
            data=b"Data",
        )

        url = await storage_service.generate_presigned_url(
            "test-bucket", "presigned.txt"
        )
        assert url.url is not None
        assert url.method == "GET"


# =============================================================================
# Mock Secrets Service Tests
# =============================================================================


class TestMockSecretsService:
    """Tests for MockSecretsService."""

    @pytest.fixture
    async def secrets_service(self):
        service = MockSecretsService()
        await service.connect()
        return service

    @pytest.mark.asyncio
    async def test_create_and_get_secret(self, secrets_service):
        """Test secret creation and retrieval."""
        secret = await secrets_service.create_secret(
            name="test-secret",
            value="my-secret-value",
            description="Test secret",
        )

        assert secret.name == "test-secret"
        assert secret.value == "my-secret-value"

        retrieved = await secrets_service.get_secret("test-secret")
        assert retrieved is not None
        assert retrieved.value == "my-secret-value"

    @pytest.mark.asyncio
    async def test_json_secret(self, secrets_service):
        """Test JSON secret handling."""
        await secrets_service.create_secret(
            name="json-secret",
            value={"key1": "value1", "key2": "value2"},
        )

        value = await secrets_service.get_secret_value("json-secret", "key1")
        assert value == "value1"

    @pytest.mark.asyncio
    async def test_update_secret(self, secrets_service):
        """Test secret updates."""
        await secrets_service.create_secret("update-test", "original")

        updated = await secrets_service.update_secret("update-test", "updated")
        assert updated.value == "updated"

        retrieved = await secrets_service.get_secret("update-test")
        assert retrieved.value == "updated"

    @pytest.mark.asyncio
    async def test_delete_secret(self, secrets_service):
        """Test secret deletion."""
        await secrets_service.create_secret("delete-test", "value")

        result = await secrets_service.delete_secret("delete-test")
        assert result is True

        exists = await secrets_service.secret_exists("delete-test")
        assert exists is False

    @pytest.mark.asyncio
    async def test_list_secrets(self, secrets_service):
        """Test listing secrets."""
        for i in range(3):
            await secrets_service.create_secret(f"list-{i}", f"value-{i}")

        secrets = await secrets_service.list_secrets()
        assert len(secrets) >= 3


# =============================================================================
# Cloud Service Factory Tests
# =============================================================================


class TestCloudServiceFactory:
    """Tests for CloudServiceFactory."""

    def test_factory_from_environment_default(self, monkeypatch):
        """Test factory creation with defaults."""
        monkeypatch.delenv("CLOUD_PROVIDER", raising=False)
        monkeypatch.delenv("NEPTUNE_ENDPOINT", raising=False)

        factory = CloudServiceFactory.from_environment()
        assert factory.config.provider == CloudProvider.AWS

    def test_factory_for_provider(self):
        """Test factory creation for specific provider."""
        factory = CloudServiceFactory.for_provider(
            CloudProvider.AZURE_GOVERNMENT, "usgovvirginia"
        )

        assert factory.config.provider == CloudProvider.AZURE_GOVERNMENT
        assert factory.config.region == "usgovvirginia"

    def test_create_mock_services(self):
        """Test creating mock services."""
        factory = CloudServiceFactory.for_provider(CloudProvider.MOCK, "us-east-1")

        graph = factory.create_graph_service()
        assert_is_mock_service(graph, "MockGraphService")

        vector = factory.create_vector_service()
        assert_is_mock_service(vector, "MockVectorService")

        llm = factory.create_llm_service()
        assert_is_mock_service(llm, "MockLLMService")

        storage = factory.create_storage_service()
        assert_is_mock_service(storage, "MockStorageService")

        secrets = factory.create_secrets_service()
        assert_is_mock_service(secrets, "MockSecretsService")

    def test_service_caching(self):
        """Test that services are cached."""
        factory = CloudServiceFactory.for_provider(CloudProvider.MOCK, "us-east-1")

        graph1 = factory.create_graph_service()
        graph2 = factory.create_graph_service()

        assert graph1 is graph2

    def test_clear_cache(self):
        """Test cache clearing."""
        factory = CloudServiceFactory.for_provider(CloudProvider.MOCK, "us-east-1")

        graph1 = factory.create_graph_service()
        factory.clear_cache()
        graph2 = factory.create_graph_service()

        assert graph1 is not graph2


# =============================================================================
# Integration-Style Tests
# =============================================================================


class TestMultiCloudIntegration:
    """Integration tests for multi-cloud abstraction."""

    @pytest.mark.asyncio
    async def test_graph_workflow(self):
        """Test complete graph workflow."""
        factory = CloudServiceFactory.for_provider(CloudProvider.MOCK, "us-east-1")
        graph = factory.create_graph_service()

        await graph.connect()

        # Add entities
        class_entity = GraphEntity(
            id="myclass",
            entity_type=EntityType.CLASS,
            name="MyClass",
            repository="test-repo",
            file_path="myclass.py",
        )
        method_entity = GraphEntity(
            id="mymethod",
            entity_type=EntityType.METHOD,
            name="my_method",
            repository="test-repo",
            file_path="myclass.py",
        )

        await graph.add_entity(class_entity)
        await graph.add_entity(method_entity)

        # Add relationship
        rel = GraphRelationship(
            id="contains-1",
            relationship_type=RelationshipType.CONTAINS,
            source_id="myclass",
            target_id="mymethod",
        )
        await graph.add_relationship(rel)

        # Query
        result = await graph.find_related_code("myclass", max_depth=1)
        assert len(result.entities) >= 1
        assert len(result.relationships) >= 1

        # Cleanup
        count = await graph.delete_by_repository("test-repo")
        assert count >= 2

    @pytest.mark.asyncio
    async def test_vector_search_workflow(self):
        """Test complete vector search workflow."""
        factory = CloudServiceFactory.for_provider(CloudProvider.MOCK, "us-east-1")
        vector = factory.create_vector_service()

        await vector.connect()

        # Create index
        config = IndexConfig(name="code-index", dimension=1536)
        await vector.create_index(config)

        # Index documents
        docs = []
        for i in range(10):
            docs.append(
                VectorDocument(
                    id=f"code-{i}",
                    content=f"def function_{i}(): pass",
                    embedding=[0.1 * i] * 1536,
                    repository="test-repo",
                    file_path=f"func_{i}.py",
                    entity_type="function",
                )
            )

        result = await vector.bulk_index("code-index", docs)
        assert result["success_count"] == 10

        # Search
        query_embedding = [0.5] * 1536
        results = await vector.search_similar("code-index", query_embedding, k=5)
        assert len(results) <= 5

        # Cleanup
        await vector.delete_index("code-index")

    @pytest.mark.asyncio
    async def test_llm_code_generation_workflow(self):
        """Test LLM code generation workflow."""
        factory = CloudServiceFactory.for_provider(CloudProvider.MOCK, "us-east-1")
        llm = factory.create_llm_service()

        await llm.initialize()

        # Generate code
        response = await llm.generate_code(
            prompt="Create a function to calculate fibonacci",
            language="python",
        )

        assert response.content is not None
        assert response.input_tokens > 0

        # Analyze code
        analysis = await llm.analyze_code(
            code=response.content,
            language="python",
            analysis_type="quality",
        )

        assert analysis.content is not None

        # Check usage
        budget = await llm.check_budget(100.0, 1000.0)
        assert "daily_spend" in budget
