"""
Tests for Azure Provider Services.

Tests the Azure cloud abstraction layer implementations:
- AzureBlobService (Azure Blob Storage)
- AzureKeyVaultService (Azure Key Vault)
- AzureOpenAIService (Azure OpenAI)
- AzureAISearchService (Azure AI Search)
- CosmosDBGraphService (Azure Cosmos DB Gremlin)

These services support multi-cloud deployment per ADR-004.
"""

import pytest

# ============================================================================
# AzureBlobService Tests
# ============================================================================


class TestAzureBlobService:
    """Tests for Azure Blob Storage service."""

    @pytest.fixture
    def blob_service(self):
        """Create blob service in mock mode."""
        from src.services.providers.azure.azure_blob_service import AzureBlobService

        return AzureBlobService()

    @pytest.fixture
    def blob_service_with_url(self):
        """Create blob service with URL (still mock due to no SDK)."""
        from src.services.providers.azure.azure_blob_service import AzureBlobService

        return AzureBlobService(account_url="https://test.blob.core.windows.net")

    def test_initialization_defaults(self, blob_service):
        """Test default initialization."""
        assert blob_service.account_url is None
        assert blob_service.connection_string is None
        assert blob_service._client is None
        assert blob_service._connected is False
        assert blob_service._mock_containers == {}

    def test_initialization_with_account_url(self, blob_service_with_url):
        """Test initialization with account URL."""
        assert blob_service_with_url.account_url == "https://test.blob.core.windows.net"

    def test_is_mock_mode_true(self, blob_service):
        """Test mock mode detection when SDK not available."""
        assert blob_service.is_mock_mode is True

    @pytest.mark.asyncio
    async def test_connect_mock_mode(self, blob_service):
        """Test connecting in mock mode."""
        result = await blob_service.connect()
        assert result is True
        assert blob_service._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, blob_service):
        """Test disconnection."""
        await blob_service.connect()
        await blob_service.disconnect()
        assert blob_service._connected is False
        assert blob_service._client is None

    @pytest.mark.asyncio
    async def test_create_bucket_mock(self, blob_service):
        """Test creating a container in mock mode."""
        await blob_service.connect()
        result = await blob_service.create_bucket("test-container")
        assert result is True
        assert "test-container" in blob_service._mock_containers

    @pytest.mark.asyncio
    async def test_delete_bucket_mock(self, blob_service):
        """Test deleting a container in mock mode."""
        await blob_service.connect()
        await blob_service.create_bucket("test-container")
        result = await blob_service.delete_bucket("test-container")
        assert result is True
        assert "test-container" not in blob_service._mock_containers

    @pytest.mark.asyncio
    async def test_delete_bucket_not_found(self, blob_service):
        """Test deleting non-existent container."""
        await blob_service.connect()
        result = await blob_service.delete_bucket("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_bucket_exists_mock(self, blob_service):
        """Test checking if container exists in mock mode."""
        await blob_service.connect()
        await blob_service.create_bucket("test-container")
        assert await blob_service.bucket_exists("test-container") is True
        assert await blob_service.bucket_exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_list_buckets_mock(self, blob_service):
        """Test listing containers in mock mode."""
        await blob_service.connect()
        await blob_service.create_bucket("container-1")
        await blob_service.create_bucket("container-2")
        buckets = await blob_service.list_buckets()
        assert "container-1" in buckets
        assert "container-2" in buckets

    @pytest.mark.asyncio
    async def test_upload_object_mock(self, blob_service):
        """Test uploading an object in mock mode."""
        await blob_service.connect()
        await blob_service.create_bucket("test-container")

        obj = await blob_service.upload_object(
            bucket="test-container",
            key="test-file.txt",
            data=b"Hello World",
            content_type="text/plain",
        )

        assert obj.key == "test-file.txt"
        assert obj.bucket == "test-container"
        assert obj.size_bytes == 11

    @pytest.mark.asyncio
    async def test_upload_object_creates_bucket(self, blob_service):
        """Test uploading creates bucket if not exists."""
        await blob_service.connect()

        obj = await blob_service.upload_object(
            bucket="auto-created",
            key="file.txt",
            data=b"data",
        )

        assert obj.bucket == "auto-created"
        assert "auto-created" in blob_service._mock_containers

    @pytest.mark.asyncio
    async def test_download_object_mock(self, blob_service):
        """Test downloading an object in mock mode."""
        await blob_service.connect()
        await blob_service.upload_object(
            bucket="test",
            key="file.txt",
            data=b"content",
        )

        data = await blob_service.download_object("test", "file.txt")
        assert data == b"content"

    @pytest.mark.asyncio
    async def test_download_object_not_found(self, blob_service):
        """Test downloading non-existent object."""
        await blob_service.connect()
        data = await blob_service.download_object("nonexistent", "file.txt")
        assert data == b""

    @pytest.mark.asyncio
    async def test_download_object_to_file_mock(self, blob_service, tmp_path):
        """Test downloading object to file."""
        await blob_service.connect()
        await blob_service.upload_object(
            bucket="test",
            key="file.txt",
            data=b"file content",
        )

        file_path = str(tmp_path / "downloaded.txt")
        result = await blob_service.download_object_to_file(
            "test", "file.txt", file_path
        )

        assert result is True
        with open(file_path, "rb") as f:
            assert f.read() == b"file content"

    @pytest.mark.asyncio
    async def test_delete_object_mock(self, blob_service):
        """Test deleting an object in mock mode."""
        await blob_service.connect()
        await blob_service.upload_object("test", "file.txt", b"data")

        result = await blob_service.delete_object("test", "file.txt")
        assert result is True
        assert await blob_service.object_exists("test", "file.txt") is False

    @pytest.mark.asyncio
    async def test_delete_object_not_found(self, blob_service):
        """Test deleting non-existent object."""
        await blob_service.connect()
        result = await blob_service.delete_object("test", "nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_objects_bulk(self, blob_service):
        """Test bulk deletion of objects."""
        await blob_service.connect()
        await blob_service.upload_object("test", "file1.txt", b"data1")
        await blob_service.upload_object("test", "file2.txt", b"data2")

        result = await blob_service.delete_objects("test", ["file1.txt", "file2.txt"])
        assert result["deleted"] == 2
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_object_exists_mock(self, blob_service):
        """Test checking if object exists."""
        await blob_service.connect()
        await blob_service.upload_object("test", "file.txt", b"data")

        assert await blob_service.object_exists("test", "file.txt") is True
        assert await blob_service.object_exists("test", "nonexistent.txt") is False

    @pytest.mark.asyncio
    async def test_get_object_info_mock(self, blob_service):
        """Test getting object info in mock mode."""
        await blob_service.connect()
        await blob_service.upload_object("test", "file.txt", b"data")

        info = await blob_service.get_object_info("test", "file.txt")
        assert info is not None
        assert info.key == "file.txt"
        assert info.size_bytes == 4

    @pytest.mark.asyncio
    async def test_get_object_info_not_found(self, blob_service):
        """Test getting info for non-existent object."""
        await blob_service.connect()
        info = await blob_service.get_object_info("test", "nonexistent")
        assert info is None

    @pytest.mark.asyncio
    async def test_list_objects_mock(self, blob_service):
        """Test listing objects in mock mode."""
        await blob_service.connect()
        await blob_service.upload_object("test", "file1.txt", b"data1")
        await blob_service.upload_object("test", "file2.txt", b"data2")
        await blob_service.upload_object("test", "other/file3.txt", b"data3")

        objects, token = await blob_service.list_objects("test")
        assert len(objects) == 3
        assert token is None

    @pytest.mark.asyncio
    async def test_list_objects_with_prefix(self, blob_service):
        """Test listing objects with prefix filter."""
        await blob_service.connect()
        await blob_service.upload_object("test", "docs/file1.txt", b"data1")
        await blob_service.upload_object("test", "docs/file2.txt", b"data2")
        await blob_service.upload_object("test", "other/file3.txt", b"data3")

        objects, _ = await blob_service.list_objects("test", prefix="docs/")
        assert len(objects) == 2

    @pytest.mark.asyncio
    async def test_copy_object_mock(self, blob_service):
        """Test copying an object in mock mode."""
        await blob_service.connect()
        await blob_service.upload_object("source", "original.txt", b"original content")

        result = await blob_service.copy_object(
            "source", "original.txt", "dest", "copy.txt"
        )

        assert result.key == "copy.txt"
        assert result.bucket == "dest"
        copied_data = await blob_service.download_object("dest", "copy.txt")
        assert copied_data == b"original content"

    @pytest.mark.asyncio
    async def test_generate_presigned_url_mock(self, blob_service):
        """Test generating presigned URL in mock mode."""
        await blob_service.connect()

        url = await blob_service.generate_presigned_url(
            bucket="test",
            key="file.txt",
            expires_in_seconds=3600,
        )

        assert url.url is not None
        assert "mock.blob.core.windows.net" in url.url
        assert url.method == "GET"

    @pytest.mark.asyncio
    async def test_get_health_disconnected(self, blob_service):
        """Test health check when disconnected."""
        health = await blob_service.get_health()
        assert health["status"] == "disconnected"
        assert health["mode"] == "mock"

    @pytest.mark.asyncio
    async def test_get_health_connected(self, blob_service):
        """Test health check when connected."""
        await blob_service.connect()
        health = await blob_service.get_health()
        assert health["status"] == "healthy"
        assert health["mode"] == "mock"

    @pytest.mark.asyncio
    async def test_get_bucket_stats_mock(self, blob_service):
        """Test getting bucket statistics in mock mode."""
        await blob_service.connect()
        await blob_service.upload_object("test", "file1.txt", b"data1")
        await blob_service.upload_object("test", "file2.txt", b"data22")

        stats = await blob_service.get_bucket_stats("test")
        assert stats["bucket"] == "test"
        assert stats["object_count"] == 2
        assert stats["total_size_bytes"] == 11  # 5 + 6


# ============================================================================
# AzureKeyVaultService Tests
# ============================================================================


class TestAzureKeyVaultService:
    """Tests for Azure Key Vault service."""

    @pytest.fixture
    def keyvault_service(self):
        """Create Key Vault service in mock mode."""
        from src.services.providers.azure.azure_keyvault_service import (
            AzureKeyVaultService,
        )

        return AzureKeyVaultService()

    def test_initialization_defaults(self, keyvault_service):
        """Test default initialization."""
        assert keyvault_service.vault_url is None
        assert keyvault_service._client is None
        assert keyvault_service._connected is False
        assert keyvault_service._mock_secrets == {}

    def test_is_mock_mode(self, keyvault_service):
        """Test mock mode detection."""
        assert keyvault_service.is_mock_mode is True

    @pytest.mark.asyncio
    async def test_connect_mock_mode(self, keyvault_service):
        """Test connecting in mock mode."""
        result = await keyvault_service.connect()
        assert result is True
        assert keyvault_service._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, keyvault_service):
        """Test disconnection."""
        await keyvault_service.connect()
        await keyvault_service.disconnect()
        assert keyvault_service._connected is False

    @pytest.mark.asyncio
    async def test_create_secret_mock(self, keyvault_service):
        """Test creating a secret in mock mode."""
        await keyvault_service.connect()

        secret = await keyvault_service.create_secret(
            name="test-secret",
            value="secret-value",
            description="Test secret",
            tags={"env": "test"},
        )

        assert secret.name == "test-secret"
        assert secret.value == "secret-value"
        assert "test-secret" in keyvault_service._mock_secrets

    @pytest.mark.asyncio
    async def test_get_secret_mock(self, keyvault_service):
        """Test getting a secret in mock mode."""
        await keyvault_service.connect()
        await keyvault_service.create_secret("test-secret", "secret-value")

        secret = await keyvault_service.get_secret("test-secret")
        assert secret is not None
        assert secret.value == "secret-value"

    @pytest.mark.asyncio
    async def test_get_secret_not_found(self, keyvault_service):
        """Test getting non-existent secret."""
        await keyvault_service.connect()
        secret = await keyvault_service.get_secret("nonexistent")
        assert secret is None

    @pytest.mark.asyncio
    async def test_update_secret_mock(self, keyvault_service):
        """Test updating a secret in mock mode."""
        await keyvault_service.connect()
        await keyvault_service.create_secret("test-secret", "old-value")

        secret = await keyvault_service.update_secret("test-secret", "new-value")
        assert secret.value == "new-value"

    @pytest.mark.asyncio
    async def test_delete_secret_mock(self, keyvault_service):
        """Test deleting a secret in mock mode."""
        await keyvault_service.connect()
        await keyvault_service.create_secret("test-secret", "value")

        result = await keyvault_service.delete_secret("test-secret")
        assert result is True
        assert "test-secret" not in keyvault_service._mock_secrets

    @pytest.mark.asyncio
    async def test_list_secrets_mock(self, keyvault_service):
        """Test listing secrets in mock mode."""
        await keyvault_service.connect()
        await keyvault_service.create_secret("secret-1", "value1")
        await keyvault_service.create_secret("secret-2", "value2")

        secrets = await keyvault_service.list_secrets()
        assert len(secrets) >= 2

    @pytest.mark.asyncio
    async def test_get_health(self, keyvault_service):
        """Test health check."""
        await keyvault_service.connect()
        health = await keyvault_service.get_health()
        assert health["status"] == "healthy"
        assert health["mode"] == "mock"


# ============================================================================
# AzureOpenAIService Tests
# ============================================================================


class TestAzureOpenAIService:
    """Tests for Azure OpenAI service."""

    @pytest.fixture
    def openai_service(self):
        """Create OpenAI service in mock mode."""
        from src.services.providers.azure.azure_openai_service import AzureOpenAIService

        return AzureOpenAIService()

    def test_initialization(self, openai_service):
        """Test default initialization."""
        assert openai_service._client is None
        assert openai_service._initialized is False

    def test_is_mock_mode(self, openai_service):
        """Test mock mode detection."""
        assert openai_service.is_mock_mode is True

    @pytest.mark.asyncio
    async def test_initialize_mock_mode(self, openai_service):
        """Test initializing in mock mode."""
        result = await openai_service.initialize()
        assert result is True
        assert openai_service._initialized is True

    @pytest.mark.asyncio
    async def test_shutdown(self, openai_service):
        """Test shutdown."""
        await openai_service.initialize()
        await openai_service.shutdown()
        assert openai_service._initialized is False

    @pytest.mark.asyncio
    async def test_invoke_mock_mode(self, openai_service):
        """Test invoking model in mock mode."""
        from src.abstractions.llm_service import LLMRequest

        await openai_service.initialize()

        request = LLMRequest(prompt="Hello, world!")
        result = await openai_service.invoke(request)

        assert result.content is not None
        assert "Mock" in result.content

    @pytest.mark.asyncio
    async def test_invoke_with_system_prompt(self, openai_service):
        """Test invoking with system prompt."""
        from src.abstractions.llm_service import LLMRequest

        await openai_service.initialize()

        request = LLMRequest(
            prompt="What is Python?",
            system_prompt="You are a helpful assistant.",
            temperature=0.7,
            max_tokens=100,
        )
        result = await openai_service.invoke(request)

        assert result.content is not None

    @pytest.mark.asyncio
    async def test_generate_embedding_mock(self, openai_service):
        """Test generating embeddings in mock mode."""
        await openai_service.initialize()

        embedding = await openai_service.generate_embedding("Test text for embedding")

        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) == 1536  # Standard embedding dimension

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_mock(self, openai_service):
        """Test generating batch embeddings in mock mode."""
        await openai_service.initialize()

        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = await openai_service.generate_embeddings_batch(texts)

        assert len(embeddings) == 3
        assert all(len(e) == 1536 for e in embeddings)

    @pytest.mark.asyncio
    async def test_health_check(self, openai_service):
        """Test health check."""
        await openai_service.initialize()
        health = await openai_service.health_check()
        assert health["status"] == "healthy"
        assert health["mode"] == "mock"

    @pytest.mark.asyncio
    async def test_list_available_models(self, openai_service):
        """Test listing available models."""
        models = await openai_service.list_available_models()
        assert len(models) >= 1
        model_ids = [m.model_id for m in models]
        assert "gpt-4" in model_ids

    @pytest.mark.asyncio
    async def test_get_model_config(self, openai_service):
        """Test getting model config."""
        config = await openai_service.get_model_config("gpt-4")
        assert config is not None
        assert config.model_id == "gpt-4"

    @pytest.mark.asyncio
    async def test_get_model_config_not_found(self, openai_service):
        """Test getting non-existent model config."""
        config = await openai_service.get_model_config("nonexistent-model")
        assert config is None

    @pytest.mark.asyncio
    async def test_generate_code(self, openai_service):
        """Test generating code."""
        await openai_service.initialize()
        result = await openai_service.generate_code(
            prompt="Write a function to add two numbers",
            language="python",
        )
        assert result.content is not None

    @pytest.mark.asyncio
    async def test_analyze_code(self, openai_service):
        """Test analyzing code."""
        await openai_service.initialize()
        result = await openai_service.analyze_code(
            code="def add(a, b): return a + b",
            language="python",
            analysis_type="quality",
        )
        assert result.content is not None


# ============================================================================
# AzureAISearchService Tests
# ============================================================================


class TestAzureAISearchService:
    """Tests for Azure AI Search service."""

    @pytest.fixture
    def search_service(self):
        """Create AI Search service in mock mode."""
        from src.services.providers.azure.azure_ai_search_service import (
            AzureAISearchService,
        )

        return AzureAISearchService()

    def test_initialization(self, search_service):
        """Test default initialization."""
        assert search_service._index_client is None
        assert search_service._search_client is None
        assert search_service._connected is False
        assert search_service._mock_documents == {}

    def test_is_mock_mode(self, search_service):
        """Test mock mode detection."""
        assert search_service.is_mock_mode is True

    @pytest.mark.asyncio
    async def test_connect_mock_mode(self, search_service):
        """Test connecting in mock mode."""
        result = await search_service.connect()
        assert result is True
        assert search_service._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, search_service):
        """Test disconnection."""
        await search_service.connect()
        await search_service.disconnect()
        assert search_service._connected is False

    @pytest.mark.asyncio
    async def test_is_connected(self, search_service):
        """Test checking connection status."""
        assert await search_service.is_connected() is False
        await search_service.connect()
        assert await search_service.is_connected() is True

    @pytest.mark.asyncio
    async def test_create_index_mock(self, search_service):
        """Test creating an index in mock mode."""
        from src.abstractions.vector_database import IndexConfig

        await search_service.connect()

        config = IndexConfig(name="test-index", dimension=1536)
        result = await search_service.create_index(config)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_index_mock(self, search_service):
        """Test deleting an index in mock mode."""
        await search_service.connect()
        result = await search_service.delete_index("test-index")
        assert result is True

    @pytest.mark.asyncio
    async def test_index_exists(self, search_service):
        """Test checking if index exists (mock mode always returns True)."""
        await search_service.connect()
        assert await search_service.index_exists("test-index") is True

    @pytest.mark.asyncio
    async def test_index_document_mock(self, search_service):
        """Test indexing a document in mock mode."""
        from src.abstractions.vector_database import VectorDocument

        await search_service.connect()

        doc = VectorDocument(
            id="doc1",
            content="Test content",
            embedding=[0.1] * 1536,
            repository="test-repo",
            file_path="/test/file.py",
            entity_type="file",
        )

        doc_id = await search_service.index_document("test-index", doc)
        assert doc_id == "doc1"
        assert "doc1" in search_service._mock_documents

    @pytest.mark.asyncio
    async def test_bulk_index_mock(self, search_service):
        """Test bulk indexing in mock mode."""
        from src.abstractions.vector_database import VectorDocument

        await search_service.connect()

        docs = [
            VectorDocument(
                id=f"doc{i}",
                content=f"Content {i}",
                embedding=[0.1] * 1536,
                repository="test-repo",
                file_path=f"/test/file{i}.py",
                entity_type="file",
            )
            for i in range(3)
        ]

        result = await search_service.bulk_index("test-index", docs)
        assert result["success_count"] == 3
        assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_get_document_mock(self, search_service):
        """Test getting a document in mock mode."""
        from src.abstractions.vector_database import VectorDocument

        await search_service.connect()

        doc = VectorDocument(
            id="doc1",
            content="Test content",
            embedding=[0.1] * 1536,
            repository="test-repo",
            file_path="/test/file.py",
            entity_type="file",
        )
        await search_service.index_document("test-index", doc)

        retrieved = await search_service.get_document("test-index", "doc1")
        assert retrieved is not None
        assert retrieved.id == "doc1"

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, search_service):
        """Test getting non-existent document."""
        await search_service.connect()
        retrieved = await search_service.get_document("test-index", "nonexistent")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_document_mock(self, search_service):
        """Test deleting a document in mock mode."""
        from src.abstractions.vector_database import VectorDocument

        await search_service.connect()

        doc = VectorDocument(
            id="doc1",
            content="Test",
            embedding=[0.1] * 1536,
            repository="test-repo",
            file_path="/test.py",
            entity_type="file",
        )
        await search_service.index_document("test-index", doc)

        result = await search_service.delete_document("test-index", "doc1")
        assert result is True
        assert "doc1" not in search_service._mock_documents

    @pytest.mark.asyncio
    async def test_search_similar_mock(self, search_service):
        """Test vector search in mock mode."""
        from src.abstractions.vector_database import VectorDocument

        await search_service.connect()

        # Index some documents
        for i in range(3):
            doc = VectorDocument(
                id=f"doc{i}",
                content=f"Content {i}",
                embedding=[0.1] * 1536,
                repository="test-repo",
                file_path=f"/test{i}.py",
                entity_type="file",
            )
            await search_service.index_document("test-index", doc)

        results = await search_service.search_similar(
            index_name="test-index",
            query_embedding=[0.1] * 1536,
            k=10,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_hybrid_search_mock(self, search_service):
        """Test hybrid search in mock mode."""
        await search_service.connect()

        results = await search_service.hybrid_search(
            index_name="test-index",
            query_text="python code",
            query_embedding=[0.1] * 1536,
            k=10,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_get_health(self, search_service):
        """Test health check."""
        await search_service.connect()
        health = await search_service.get_health()
        assert health["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_index_stats_mock(self, search_service):
        """Test getting index statistics in mock mode."""
        await search_service.connect()
        stats = await search_service.get_index_stats("test-index")
        assert "document_count" in stats


# ============================================================================
# CosmosDBGraphService Tests
# ============================================================================


class TestCosmosDBGraphService:
    """Tests for Azure Cosmos DB Gremlin (graph) service."""

    @pytest.fixture
    def graph_service(self):
        """Create Cosmos Graph service in mock mode."""
        from src.services.providers.azure.cosmos_graph_service import (
            CosmosDBGraphService,
        )

        return CosmosDBGraphService()

    def test_initialization(self, graph_service):
        """Test default initialization."""
        assert graph_service._client is None
        assert graph_service._connected is False
        assert graph_service._mock_entities == {}
        assert graph_service._mock_relationships == {}

    def test_is_mock_mode(self, graph_service):
        """Test mock mode detection."""
        assert graph_service.is_mock_mode is True

    @pytest.mark.asyncio
    async def test_connect_mock_mode(self, graph_service):
        """Test connecting in mock mode."""
        result = await graph_service.connect()
        assert result is True
        assert graph_service._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, graph_service):
        """Test disconnection."""
        await graph_service.connect()
        await graph_service.disconnect()
        assert graph_service._connected is False

    @pytest.mark.asyncio
    async def test_add_entity_mock(self, graph_service):
        """Test adding an entity in mock mode."""
        from src.abstractions.graph_database import EntityType, GraphEntity

        await graph_service.connect()

        entity = GraphEntity(
            id="func-1",
            entity_type=EntityType.FUNCTION,
            name="main",
            repository="test-repo",
            file_path="/main.py",
            properties={"language": "python"},
        )

        entity_id = await graph_service.add_entity(entity)
        assert entity_id == "func-1"
        assert "func-1" in graph_service._mock_entities

    @pytest.mark.asyncio
    async def test_get_entity_mock(self, graph_service):
        """Test getting an entity in mock mode."""
        from src.abstractions.graph_database import EntityType, GraphEntity

        await graph_service.connect()

        entity = GraphEntity(
            id="func-1",
            entity_type=EntityType.FUNCTION,
            name="test",
            repository="test-repo",
            file_path="/test.py",
        )
        await graph_service.add_entity(entity)

        retrieved = await graph_service.get_entity("func-1")
        assert retrieved is not None
        assert retrieved.name == "test"

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, graph_service):
        """Test getting non-existent entity."""
        await graph_service.connect()
        entity = await graph_service.get_entity("nonexistent")
        assert entity is None

    @pytest.mark.asyncio
    async def test_update_entity_mock(self, graph_service):
        """Test updating an entity in mock mode."""
        from src.abstractions.graph_database import EntityType, GraphEntity

        await graph_service.connect()

        entity = GraphEntity(
            id="func-1",
            entity_type=EntityType.FUNCTION,
            name="test",
            repository="test-repo",
            file_path="/test.py",
            properties={"version": "1.0"},
        )
        await graph_service.add_entity(entity)

        # Update takes a GraphEntity object
        updated_entity = GraphEntity(
            id="func-1",
            entity_type=EntityType.FUNCTION,
            name="test",
            repository="test-repo",
            file_path="/test.py",
            properties={"version": "2.0"},
        )
        updated = await graph_service.update_entity(updated_entity)
        assert updated is True

    @pytest.mark.asyncio
    async def test_delete_entity_mock(self, graph_service):
        """Test deleting an entity in mock mode."""
        from src.abstractions.graph_database import EntityType, GraphEntity

        await graph_service.connect()

        entity = GraphEntity(
            id="func-1",
            entity_type=EntityType.FUNCTION,
            name="test",
            repository="test-repo",
            file_path="/test.py",
        )
        await graph_service.add_entity(entity)

        result = await graph_service.delete_entity("func-1")
        assert result is True
        assert await graph_service.get_entity("func-1") is None

    @pytest.mark.asyncio
    async def test_add_relationship_mock(self, graph_service):
        """Test adding a relationship in mock mode."""
        from src.abstractions.graph_database import (
            EntityType,
            GraphEntity,
            GraphRelationship,
            RelationshipType,
        )

        await graph_service.connect()

        # Add entities first
        e1 = GraphEntity(
            id="func-1",
            entity_type=EntityType.FUNCTION,
            name="caller",
            repository="r",
            file_path="/a.py",
        )
        e2 = GraphEntity(
            id="func-2",
            entity_type=EntityType.FUNCTION,
            name="callee",
            repository="r",
            file_path="/b.py",
        )
        await graph_service.add_entity(e1)
        await graph_service.add_entity(e2)

        rel = GraphRelationship(
            id="rel-1",
            relationship_type=RelationshipType.CALLS,
            source_id="func-1",
            target_id="func-2",
            properties={"line": 42},
        )

        rel_id = await graph_service.add_relationship(rel)
        assert rel_id == "rel-1"

    @pytest.mark.asyncio
    async def test_get_relationships_mock(self, graph_service):
        """Test getting relationships in mock mode."""
        from src.abstractions.graph_database import (
            EntityType,
            GraphEntity,
            GraphRelationship,
            RelationshipType,
        )

        await graph_service.connect()

        e1 = GraphEntity(
            id="func-1",
            entity_type=EntityType.FUNCTION,
            name="main",
            repository="r",
            file_path="/a.py",
        )
        e2 = GraphEntity(
            id="func-2",
            entity_type=EntityType.FUNCTION,
            name="helper",
            repository="r",
            file_path="/b.py",
        )
        await graph_service.add_entity(e1)
        await graph_service.add_entity(e2)

        rel = GraphRelationship(
            id="rel-1",
            relationship_type=RelationshipType.CALLS,
            source_id="func-1",
            target_id="func-2",
        )
        await graph_service.add_relationship(rel)

        relationships = await graph_service.get_relationships("func-1", direction="out")
        assert isinstance(relationships, list)

    @pytest.mark.asyncio
    async def test_find_related_code_mock(self, graph_service):
        """Test finding related code in mock mode."""
        from src.abstractions.graph_database import EntityType, GraphEntity

        await graph_service.connect()

        entity = GraphEntity(
            id="func-1",
            entity_type=EntityType.FUNCTION,
            name="test",
            repository="test-repo",
            file_path="/test.py",
        )
        await graph_service.add_entity(entity)

        result = await graph_service.find_related_code("func-1", max_depth=2)
        assert hasattr(result, "entities")
        assert hasattr(result, "relationships")

    @pytest.mark.asyncio
    async def test_get_health(self, graph_service):
        """Test health check."""
        await graph_service.connect()
        health = await graph_service.get_health()
        assert health["status"] == "healthy"
        assert health["mode"] == "mock"

    @pytest.mark.asyncio
    async def test_get_statistics_mock(self, graph_service):
        """Test getting graph statistics in mock mode."""
        from src.abstractions.graph_database import EntityType, GraphEntity

        await graph_service.connect()

        e1 = GraphEntity(
            id="func-1",
            entity_type=EntityType.FUNCTION,
            name="f1",
            repository="r",
            file_path="/a.py",
        )
        e2 = GraphEntity(
            id="class-1",
            entity_type=EntityType.CLASS,
            name="c1",
            repository="r",
            file_path="/a.py",
        )
        await graph_service.add_entity(e1)
        await graph_service.add_entity(e2)

        stats = await graph_service.get_statistics()
        assert stats["entity_count"] == 2
        assert stats["relationship_count"] == 0
