"""
Tests for Mock Provider Services

Tests for in-memory mock implementations used for testing.
Reference: ADR-004 Cloud Abstraction Layer for Multi-Cloud Deployment
"""

import pytest

# ==================== MockGraphService Tests ====================


class TestMockGraphService:
    """Tests for MockGraphService class."""

    def test_initialization(self):
        """Test service initialization."""
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        assert service._entities == {}
        assert service._relationships == {}
        assert service._connected is False

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connecting to mock service."""
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        result = await service.connect()
        assert result is True
        assert service._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting from mock service."""
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        await service.connect()
        await service.disconnect()
        assert service._connected is False

    @pytest.mark.asyncio
    async def test_is_connected(self):
        """Test is_connected method."""
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        assert await service.is_connected() is False
        await service.connect()
        assert await service.is_connected() is True

    @pytest.mark.asyncio
    async def test_add_entity(self):
        """Test adding an entity."""
        from src.abstractions.graph_database import EntityType, GraphEntity
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        entity = GraphEntity(
            id="entity-1",
            entity_type=EntityType.FILE,
            name="test.py",
            repository="test-repo",
            file_path="/src/test.py",
            properties={"language": "python"},
        )
        result = await service.add_entity(entity)
        assert result == "entity-1"
        assert "entity-1" in service._entities

    @pytest.mark.asyncio
    async def test_get_entity(self):
        """Test getting an entity."""
        from src.abstractions.graph_database import EntityType, GraphEntity
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        entity = GraphEntity(
            id="entity-1",
            entity_type=EntityType.FUNCTION,
            name="test_func",
            repository="test-repo",
            file_path="/src/test.py",
            properties={},
        )
        await service.add_entity(entity)

        result = await service.get_entity("entity-1")
        assert result is not None
        assert result.name == "test_func"

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self):
        """Test getting a non-existent entity."""
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        result = await service.get_entity("non-existent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_entity(self):
        """Test updating an entity."""
        from src.abstractions.graph_database import EntityType, GraphEntity
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        entity = GraphEntity(
            id="entity-1",
            entity_type=EntityType.CLASS,
            name="OldName",
            repository="test-repo",
            file_path="/src/test.py",
            properties={},
        )
        await service.add_entity(entity)

        updated = GraphEntity(
            id="entity-1",
            entity_type=EntityType.CLASS,
            name="NewName",
            repository="test-repo",
            file_path="/src/test.py",
            properties={"updated": True},
        )
        result = await service.update_entity(updated)
        assert result is True
        assert service._entities["entity-1"].name == "NewName"

    @pytest.mark.asyncio
    async def test_update_entity_not_found(self):
        """Test updating a non-existent entity."""
        from src.abstractions.graph_database import EntityType, GraphEntity
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        entity = GraphEntity(
            id="non-existent",
            entity_type=EntityType.FILE,
            name="test",
            repository="test-repo",
            file_path="/src/test.py",
            properties={},
        )
        result = await service.update_entity(entity)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_entity(self):
        """Test deleting an entity."""
        from src.abstractions.graph_database import EntityType, GraphEntity
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        entity = GraphEntity(
            id="entity-1",
            entity_type=EntityType.FILE,
            name="test",
            repository="test-repo",
            file_path="/src/test.py",
            properties={},
        )
        await service.add_entity(entity)

        result = await service.delete_entity("entity-1")
        assert result is True
        assert "entity-1" not in service._entities

    @pytest.mark.asyncio
    async def test_delete_entity_not_found(self):
        """Test deleting a non-existent entity."""
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        result = await service.delete_entity("non-existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_add_relationship(self):
        """Test adding a relationship."""
        from src.abstractions.graph_database import GraphRelationship, RelationshipType
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        rel = GraphRelationship(
            id="rel-1",
            relationship_type=RelationshipType.IMPORTS,
            source_id="entity-1",
            target_id="entity-2",
            properties={},
        )
        result = await service.add_relationship(rel)
        assert result == "rel-1"

    @pytest.mark.asyncio
    async def test_get_relationships_outgoing(self):
        """Test getting outgoing relationships."""
        from src.abstractions.graph_database import GraphRelationship, RelationshipType
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        rel = GraphRelationship(
            id="rel-1",
            relationship_type=RelationshipType.IMPORTS,
            source_id="entity-1",
            target_id="entity-2",
            properties={},
        )
        await service.add_relationship(rel)

        results = await service.get_relationships("entity-1", direction="out")
        assert len(results) == 1
        assert results[0].id == "rel-1"

    @pytest.mark.asyncio
    async def test_get_relationships_incoming(self):
        """Test getting incoming relationships."""
        from src.abstractions.graph_database import GraphRelationship, RelationshipType
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        rel = GraphRelationship(
            id="rel-1",
            relationship_type=RelationshipType.IMPORTS,
            source_id="entity-1",
            target_id="entity-2",
            properties={},
        )
        await service.add_relationship(rel)

        results = await service.get_relationships("entity-2", direction="in")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_relationships_both(self):
        """Test getting relationships in both directions."""
        from src.abstractions.graph_database import GraphRelationship, RelationshipType
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        rel1 = GraphRelationship(
            id="rel-1",
            relationship_type=RelationshipType.IMPORTS,
            source_id="entity-1",
            target_id="entity-2",
            properties={},
        )
        rel2 = GraphRelationship(
            id="rel-2",
            relationship_type=RelationshipType.CALLS,
            source_id="entity-3",
            target_id="entity-1",
            properties={},
        )
        await service.add_relationship(rel1)
        await service.add_relationship(rel2)

        results = await service.get_relationships("entity-1", direction="both")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_relationships_by_type(self):
        """Test getting relationships filtered by type."""
        from src.abstractions.graph_database import GraphRelationship, RelationshipType
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        rel1 = GraphRelationship(
            id="rel-1",
            relationship_type=RelationshipType.IMPORTS,
            source_id="entity-1",
            target_id="entity-2",
            properties={},
        )
        rel2 = GraphRelationship(
            id="rel-2",
            relationship_type=RelationshipType.CALLS,
            source_id="entity-1",
            target_id="entity-3",
            properties={},
        )
        await service.add_relationship(rel1)
        await service.add_relationship(rel2)

        results = await service.get_relationships(
            "entity-1", relationship_type=RelationshipType.IMPORTS, direction="out"
        )
        assert len(results) == 1
        assert results[0].relationship_type == RelationshipType.IMPORTS

    @pytest.mark.asyncio
    async def test_delete_relationship(self):
        """Test deleting a relationship."""
        from src.abstractions.graph_database import GraphRelationship, RelationshipType
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        rel = GraphRelationship(
            id="rel-1",
            relationship_type=RelationshipType.IMPORTS,
            source_id="entity-1",
            target_id="entity-2",
            properties={},
        )
        await service.add_relationship(rel)

        result = await service.delete_relationship("rel-1")
        assert result is True
        assert "rel-1" not in service._relationships

    @pytest.mark.asyncio
    async def test_delete_relationship_not_found(self):
        """Test deleting a non-existent relationship."""
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()
        result = await service.delete_relationship("non-existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_entity_removes_relationships(self):
        """Test that deleting an entity removes related relationships."""
        from src.abstractions.graph_database import (
            EntityType,
            GraphEntity,
            GraphRelationship,
            RelationshipType,
        )
        from src.services.providers.mock.mock_graph_service import MockGraphService

        service = MockGraphService()

        # Add entities
        entity1 = GraphEntity(
            id="entity-1",
            entity_type=EntityType.FILE,
            name="a",
            repository="repo",
            file_path="a.py",
            properties={},
        )
        entity2 = GraphEntity(
            id="entity-2",
            entity_type=EntityType.FILE,
            name="b",
            repository="repo",
            file_path="b.py",
            properties={},
        )
        await service.add_entity(entity1)
        await service.add_entity(entity2)

        # Add relationship
        rel = GraphRelationship(
            id="rel-1",
            relationship_type=RelationshipType.IMPORTS,
            source_id="entity-1",
            target_id="entity-2",
            properties={},
        )
        await service.add_relationship(rel)

        # Delete source entity
        await service.delete_entity("entity-1")

        # Relationship should be deleted
        assert "rel-1" not in service._relationships


# ==================== MockLLMService Tests ====================


class TestMockLLMService:
    """Tests for MockLLMService class."""

    def test_initialization(self):
        """Test service initialization."""
        from src.services.providers.mock.mock_llm_service import MockLLMService

        service = MockLLMService()
        assert service._initialized is False

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test initialization."""
        from src.services.providers.mock.mock_llm_service import MockLLMService

        service = MockLLMService()
        result = await service.initialize()
        assert result is True
        assert service._initialized is True

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test shutdown."""
        from src.services.providers.mock.mock_llm_service import MockLLMService

        service = MockLLMService()
        await service.initialize()
        await service.shutdown()
        assert service._initialized is False

    @pytest.mark.asyncio
    async def test_invoke(self):
        """Test invoke method."""
        from src.abstractions.llm_service import LLMRequest
        from src.services.providers.mock.mock_llm_service import MockLLMService

        service = MockLLMService()
        request = LLMRequest(prompt="Hello")
        response = await service.invoke(request)

        assert response is not None
        assert response.content != ""
        assert response.input_tokens > 0
        assert response.output_tokens > 0


# ==================== MockStorageService Tests ====================


class TestMockStorageService:
    """Tests for MockStorageService class."""

    def test_initialization(self):
        """Test service initialization."""
        from src.services.providers.mock.mock_storage_service import MockStorageService

        service = MockStorageService()
        assert service._buckets == {}
        assert service._connected is False

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connecting."""
        from src.services.providers.mock.mock_storage_service import MockStorageService

        service = MockStorageService()
        result = await service.connect()
        assert result is True
        assert service._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting."""
        from src.services.providers.mock.mock_storage_service import MockStorageService

        service = MockStorageService()
        await service.connect()
        await service.disconnect()
        assert service._connected is False

    @pytest.mark.asyncio
    async def test_create_bucket(self):
        """Test creating a bucket."""
        from src.services.providers.mock.mock_storage_service import MockStorageService

        service = MockStorageService()
        result = await service.create_bucket("test-bucket")
        assert result is True
        assert "test-bucket" in service._buckets

    @pytest.mark.asyncio
    async def test_delete_bucket(self):
        """Test deleting a bucket."""
        from src.services.providers.mock.mock_storage_service import MockStorageService

        service = MockStorageService()
        await service.create_bucket("test-bucket")
        result = await service.delete_bucket("test-bucket")
        assert result is True
        assert "test-bucket" not in service._buckets

    @pytest.mark.asyncio
    async def test_bucket_exists(self):
        """Test checking if bucket exists."""
        from src.services.providers.mock.mock_storage_service import MockStorageService

        service = MockStorageService()
        assert await service.bucket_exists("test-bucket") is False
        await service.create_bucket("test-bucket")
        assert await service.bucket_exists("test-bucket") is True

    @pytest.mark.asyncio
    async def test_upload_object(self):
        """Test uploading an object."""
        from src.services.providers.mock.mock_storage_service import MockStorageService

        service = MockStorageService()
        await service.create_bucket("test-bucket")
        result = await service.upload_object("test-bucket", "test-key", b"test data")
        assert result is not None
        assert result.key == "test-key"

    @pytest.mark.asyncio
    async def test_download_object(self):
        """Test downloading an object."""
        from src.services.providers.mock.mock_storage_service import MockStorageService

        service = MockStorageService()
        await service.create_bucket("test-bucket")
        await service.upload_object("test-bucket", "test-key", b"test data")
        data = await service.download_object("test-bucket", "test-key")
        assert data == b"test data"

    @pytest.mark.asyncio
    async def test_delete_object(self):
        """Test deleting an object."""
        from src.services.providers.mock.mock_storage_service import MockStorageService

        service = MockStorageService()
        await service.create_bucket("test-bucket")
        await service.upload_object("test-bucket", "test-key", b"test data")
        result = await service.delete_object("test-bucket", "test-key")
        assert result is True

    @pytest.mark.asyncio
    async def test_list_objects(self):
        """Test listing objects."""
        from src.services.providers.mock.mock_storage_service import MockStorageService

        service = MockStorageService()
        await service.create_bucket("test-bucket")
        await service.upload_object("test-bucket", "file1.txt", b"data1")
        await service.upload_object("test-bucket", "file2.txt", b"data2")
        objects = await service.list_objects("test-bucket")
        assert len(objects) == 2


# ==================== MockSecretsService Tests ====================


class TestMockSecretsService:
    """Tests for MockSecretsService class."""

    def test_initialization(self):
        """Test service initialization."""
        from src.services.providers.mock.mock_secrets_service import MockSecretsService

        service = MockSecretsService()
        assert service._secrets == {}
        assert service._connected is False

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connecting."""
        from src.services.providers.mock.mock_secrets_service import MockSecretsService

        service = MockSecretsService()
        result = await service.connect()
        assert result is True
        assert service._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting."""
        from src.services.providers.mock.mock_secrets_service import MockSecretsService

        service = MockSecretsService()
        await service.connect()
        await service.disconnect()
        assert service._connected is False

    @pytest.mark.asyncio
    async def test_create_secret(self):
        """Test creating a secret."""
        from src.services.providers.mock.mock_secrets_service import MockSecretsService

        service = MockSecretsService()
        secret = await service.create_secret("test-secret", {"key": "value"})
        assert secret is not None
        assert secret.name == "test-secret"
        assert "test-secret" in service._secrets

    @pytest.mark.asyncio
    async def test_get_secret(self):
        """Test getting a secret."""
        from src.services.providers.mock.mock_secrets_service import MockSecretsService

        service = MockSecretsService()
        await service.create_secret("test-secret", {"key": "value"})
        secret = await service.get_secret("test-secret")
        assert secret is not None
        assert secret.name == "test-secret"

    @pytest.mark.asyncio
    async def test_get_secret_not_found(self):
        """Test getting a non-existent secret."""
        from src.services.providers.mock.mock_secrets_service import MockSecretsService

        service = MockSecretsService()
        secret = await service.get_secret("non-existent")
        assert secret is None

    @pytest.mark.asyncio
    async def test_delete_secret(self):
        """Test deleting a secret."""
        from src.services.providers.mock.mock_secrets_service import MockSecretsService

        service = MockSecretsService()
        await service.create_secret("test-secret", {"key": "value"})
        result = await service.delete_secret("test-secret")
        assert result is True
        assert "test-secret" not in service._secrets

    @pytest.mark.asyncio
    async def test_secret_exists(self):
        """Test checking if secret exists."""
        from src.services.providers.mock.mock_secrets_service import MockSecretsService

        service = MockSecretsService()
        assert await service.secret_exists("test-secret") is False
        await service.create_secret("test-secret", "value")
        assert await service.secret_exists("test-secret") is True

    @pytest.mark.asyncio
    async def test_list_secrets(self):
        """Test listing secrets."""
        from src.services.providers.mock.mock_secrets_service import MockSecretsService

        service = MockSecretsService()
        await service.create_secret("secret1", "value1")
        await service.create_secret("secret2", "value2")
        secrets = await service.list_secrets()
        assert len(secrets) == 2


# ==================== MockVectorService Tests ====================


class TestMockVectorService:
    """Tests for MockVectorService class."""

    def test_initialization(self):
        """Test service initialization."""
        from src.services.providers.mock.mock_vector_service import MockVectorService

        service = MockVectorService()
        assert service._indices == {}
        assert service._connected is False

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connecting."""
        from src.services.providers.mock.mock_vector_service import MockVectorService

        service = MockVectorService()
        result = await service.connect()
        assert result is True
        assert service._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting."""
        from src.services.providers.mock.mock_vector_service import MockVectorService

        service = MockVectorService()
        await service.connect()
        await service.disconnect()
        assert service._connected is False

    @pytest.mark.asyncio
    async def test_create_index(self):
        """Test creating an index."""
        from src.abstractions.vector_database import IndexConfig
        from src.services.providers.mock.mock_vector_service import MockVectorService

        service = MockVectorService()
        config = IndexConfig(name="test-index", dimension=768)
        result = await service.create_index(config)
        assert result is True
        assert "test-index" in service._indices

    @pytest.mark.asyncio
    async def test_delete_index(self):
        """Test deleting an index."""
        from src.abstractions.vector_database import IndexConfig
        from src.services.providers.mock.mock_vector_service import MockVectorService

        service = MockVectorService()
        config = IndexConfig(name="test-index", dimension=768)
        await service.create_index(config)
        result = await service.delete_index("test-index")
        assert result is True
        assert "test-index" not in service._indices

    @pytest.mark.asyncio
    async def test_index_exists(self):
        """Test checking if index exists."""
        from src.abstractions.vector_database import IndexConfig
        from src.services.providers.mock.mock_vector_service import MockVectorService

        service = MockVectorService()
        assert await service.index_exists("test-index") is False
        config = IndexConfig(name="test-index", dimension=768)
        await service.create_index(config)
        assert await service.index_exists("test-index") is True

    @pytest.mark.asyncio
    async def test_bulk_index(self):
        """Test bulk indexing documents."""
        from src.abstractions.vector_database import IndexConfig, VectorDocument
        from src.services.providers.mock.mock_vector_service import MockVectorService

        service = MockVectorService()
        config = IndexConfig(name="test-index", dimension=3)
        await service.create_index(config)

        docs = [
            VectorDocument(
                id="doc1",
                content="test content",
                embedding=[0.1, 0.2, 0.3],
                repository="repo",
                file_path="a.py",
                entity_type="file",
            ),
            VectorDocument(
                id="doc2",
                content="another content",
                embedding=[0.4, 0.5, 0.6],
                repository="repo",
                file_path="b.py",
                entity_type="file",
            ),
        ]
        result = await service.bulk_index("test-index", docs)
        assert result["success_count"] == 2

    @pytest.mark.asyncio
    async def test_delete_document(self):
        """Test deleting a document."""
        from src.abstractions.vector_database import IndexConfig, VectorDocument
        from src.services.providers.mock.mock_vector_service import MockVectorService

        service = MockVectorService()
        config = IndexConfig(name="test-index", dimension=3)
        await service.create_index(config)

        doc = VectorDocument(
            id="doc1",
            content="test",
            embedding=[0.1, 0.2, 0.3],
            repository="repo",
            file_path="a.py",
            entity_type="file",
        )
        await service.index_document("test-index", doc)

        result = await service.delete_document("test-index", "doc1")
        assert result is True

    @pytest.mark.asyncio
    async def test_search_similar(self):
        """Test searching for similar documents."""
        from src.abstractions.vector_database import IndexConfig, VectorDocument
        from src.services.providers.mock.mock_vector_service import MockVectorService

        service = MockVectorService()
        config = IndexConfig(name="test-index", dimension=3)
        await service.create_index(config)

        docs = [
            VectorDocument(
                id="doc1",
                content="hello world",
                embedding=[0.1, 0.2, 0.3],
                repository="repo",
                file_path="a.py",
                entity_type="file",
            ),
            VectorDocument(
                id="doc2",
                content="goodbye world",
                embedding=[0.9, 0.8, 0.7],
                repository="repo",
                file_path="b.py",
                entity_type="file",
            ),
        ]
        await service.bulk_index("test-index", docs)

        results = await service.search_similar("test-index", [0.1, 0.2, 0.35], k=2)
        assert len(results) >= 1
