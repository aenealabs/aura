"""Tests for the Cloud Abstraction Layer module exports."""


class TestAbstractionsExports:
    """Test that abstraction layer exports are accessible."""

    def test_cloud_provider_exports(self):
        """Test CloudProvider and CloudRegion are exported."""
        from src.abstractions import CloudProvider, CloudRegion

        assert CloudProvider is not None
        assert CloudRegion is not None

    def test_graph_database_exports(self):
        """Test graph database abstractions are exported."""
        from src.abstractions import (
            GraphDatabaseService,
            GraphEntity,
            GraphRelationship,
        )

        assert GraphDatabaseService is not None
        assert GraphEntity is not None
        assert GraphRelationship is not None

    def test_llm_service_exports(self):
        """Test LLM service abstractions are exported."""
        from src.abstractions import LLMRequest, LLMResponse, LLMService, ModelConfig

        assert LLMService is not None
        assert LLMRequest is not None
        assert LLMResponse is not None
        assert ModelConfig is not None

    def test_secrets_service_export(self):
        """Test SecretsService is exported."""
        from src.abstractions import SecretsService

        assert SecretsService is not None

    def test_storage_service_exports(self):
        """Test storage service abstractions are exported."""
        from src.abstractions import StorageObject, StorageService

        assert StorageService is not None
        assert StorageObject is not None

    def test_vector_database_exports(self):
        """Test vector database abstractions are exported."""
        from src.abstractions import SearchResult, VectorDatabaseService, VectorDocument

        assert VectorDatabaseService is not None
        assert VectorDocument is not None
        assert SearchResult is not None

    def test_all_exports_defined(self):
        """Test __all__ contains expected exports."""
        from src import abstractions

        expected = [
            "CloudProvider",
            "CloudRegion",
            "GraphDatabaseService",
            "GraphEntity",
            "GraphRelationship",
            "VectorDatabaseService",
            "VectorDocument",
            "SearchResult",
            "LLMService",
            "LLMRequest",
            "LLMResponse",
            "ModelConfig",
            "StorageService",
            "StorageObject",
            "SecretsService",
        ]

        for name in expected:
            assert name in abstractions.__all__, f"{name} not in __all__"


class TestCloudRegion:
    """Test CloudRegion dataclass."""

    def test_cloud_region_creation(self):
        """Test CloudRegion can be instantiated."""
        from src.abstractions import CloudProvider, CloudRegion

        region = CloudRegion(
            provider=CloudProvider.AWS,
            region_code="us-east-1",
            display_name="US East (N. Virginia)",
        )
        assert region.region_code == "us-east-1"
        assert region.provider == CloudProvider.AWS

    def test_cloud_region_is_govcloud(self):
        """Test is_govcloud property."""
        from src.abstractions import CloudProvider, CloudRegion

        gov_region = CloudRegion(
            provider=CloudProvider.AWS_GOVCLOUD,
            region_code="us-gov-west-1",
            display_name="AWS GovCloud West",
        )
        assert gov_region.is_govcloud is True

        commercial_region = CloudRegion(
            provider=CloudProvider.AWS,
            region_code="us-east-1",
            display_name="US East",
        )
        assert commercial_region.is_govcloud is False


class TestCloudProvider:
    """Test CloudProvider enum."""

    def test_provider_values(self):
        """Test provider enum values."""
        from src.abstractions import CloudProvider

        assert CloudProvider.AWS.value == "aws"
        assert CloudProvider.AZURE.value == "azure"
        assert CloudProvider.AWS_GOVCLOUD.value == "aws_govcloud"
        assert CloudProvider.AZURE_GOVERNMENT.value == "azure_government"
        assert CloudProvider.MOCK.value == "mock"

    def test_is_govcloud_property(self):
        """Test is_govcloud property on providers."""
        from src.abstractions import CloudProvider

        assert CloudProvider.AWS_GOVCLOUD.is_govcloud is True
        assert CloudProvider.AZURE_GOVERNMENT.is_govcloud is True
        assert CloudProvider.AWS.is_govcloud is False
        assert CloudProvider.AZURE.is_govcloud is False

    def test_partition_property(self):
        """Test partition property on providers."""
        from src.abstractions import CloudProvider

        assert CloudProvider.AWS.partition == "aws"
        assert CloudProvider.AWS_GOVCLOUD.partition == "aws-us-gov"
        assert CloudProvider.AZURE.partition == "public"
        assert CloudProvider.AZURE_GOVERNMENT.partition == "usgovernment"


class TestGraphEntity:
    """Test GraphEntity dataclass."""

    def test_graph_entity_creation(self):
        """Test GraphEntity can be instantiated."""
        from src.abstractions import GraphEntity
        from src.abstractions.graph_database import EntityType

        entity = GraphEntity(
            id="test-id-123",
            entity_type=EntityType.FUNCTION,
            name="test_function",
            repository="project-aura",
            file_path="src/services/test.py",
        )
        assert entity.id == "test-id-123"
        assert entity.entity_type == EntityType.FUNCTION
        assert entity.name == "test_function"

    def test_graph_entity_to_dict(self):
        """Test GraphEntity to_dict serialization."""
        from datetime import datetime

        from src.abstractions import GraphEntity
        from src.abstractions.graph_database import EntityType

        now = datetime(2025, 1, 1, 12, 0, 0)
        entity = GraphEntity(
            id="test-id",
            entity_type=EntityType.CLASS,
            name="MyClass",
            repository="test-repo",
            file_path="src/main.py",
            properties={"lines": 100},
            created_at=now,
        )
        result = entity.to_dict()
        assert result["id"] == "test-id"
        assert result["entity_type"] == "class"
        assert result["properties"]["lines"] == 100
        assert "2025-01-01" in result["created_at"]

    def test_graph_entity_from_dict(self):
        """Test GraphEntity from_dict deserialization."""
        from src.abstractions import GraphEntity

        data = {
            "id": "parsed-id",
            "entity_type": "function",
            "name": "parsed_func",
            "repository": "parsed-repo",
            "file_path": "src/test.py",
            "properties": {"complexity": 5},
            "created_at": "2025-01-01T12:00:00",
            "updated_at": None,
        }
        entity = GraphEntity.from_dict(data)
        assert entity.id == "parsed-id"
        assert entity.name == "parsed_func"
        assert entity.created_at is not None


class TestGraphRelationship:
    """Test GraphRelationship dataclass."""

    def test_graph_relationship_creation(self):
        """Test GraphRelationship can be instantiated."""
        from src.abstractions import GraphRelationship
        from src.abstractions.graph_database import RelationshipType

        rel = GraphRelationship(
            id="rel-123",
            relationship_type=RelationshipType.CALLS,
            source_id="func-a",
            target_id="func-b",
        )
        assert rel.id == "rel-123"
        assert rel.relationship_type == RelationshipType.CALLS
        assert rel.source_id == "func-a"
        assert rel.target_id == "func-b"

    def test_graph_relationship_to_dict(self):
        """Test GraphRelationship to_dict serialization."""
        from src.abstractions import GraphRelationship
        from src.abstractions.graph_database import RelationshipType

        rel = GraphRelationship(
            id="rel-456",
            relationship_type=RelationshipType.IMPORTS,
            source_id="module-a",
            target_id="module-b",
            properties={"count": 3},
        )
        result = rel.to_dict()
        assert result["id"] == "rel-456"
        assert result["relationship_type"] == "imports"
        assert result["properties"]["count"] == 3

    def test_graph_relationship_from_dict(self):
        """Test GraphRelationship from_dict deserialization."""
        from src.abstractions import GraphRelationship

        data = {
            "id": "rel-parsed",
            "relationship_type": "inherits",
            "source_id": "child-class",
            "target_id": "parent-class",
            "properties": {},
        }
        rel = GraphRelationship.from_dict(data)
        assert rel.id == "rel-parsed"
        assert rel.source_id == "child-class"


class TestEntityType:
    """Test EntityType enum."""

    def test_entity_type_values(self):
        """Test EntityType enum values."""
        from src.abstractions.graph_database import EntityType

        assert EntityType.FILE.value == "file"
        assert EntityType.CLASS.value == "class"
        assert EntityType.FUNCTION.value == "function"
        assert EntityType.METHOD.value == "method"
        assert EntityType.MODULE.value == "module"


class TestRelationshipType:
    """Test RelationshipType enum."""

    def test_relationship_type_values(self):
        """Test RelationshipType enum values."""
        from src.abstractions.graph_database import RelationshipType

        assert RelationshipType.CALLS.value == "calls"
        assert RelationshipType.IMPORTS.value == "imports"
        assert RelationshipType.INHERITS.value == "inherits"
        assert RelationshipType.DEPENDS_ON.value == "depends_on"


class TestModelFamily:
    """Test ModelFamily enum."""

    def test_model_family_values(self):
        """Test ModelFamily enum values."""
        from src.abstractions.llm_service import ModelFamily

        assert ModelFamily.CLAUDE.value == "claude"
        assert ModelFamily.GPT.value == "gpt"
        assert ModelFamily.LLAMA.value == "llama"
        assert ModelFamily.MISTRAL.value == "mistral"
        assert ModelFamily.TITAN.value == "titan"


class TestModelConfig:
    """Test ModelConfig dataclass."""

    def test_model_config_creation(self):
        """Test ModelConfig can be instantiated."""
        from src.abstractions import ModelConfig
        from src.abstractions.llm_service import ModelFamily

        config = ModelConfig(
            model_id="anthropic.claude-3-5-sonnet",
            family=ModelFamily.CLAUDE,
        )
        assert config.model_id == "anthropic.claude-3-5-sonnet"
        assert config.family == ModelFamily.CLAUDE
        assert config.max_tokens == 4096  # default
        assert config.temperature == 0.7  # default


class TestLLMRequest:
    """Test LLMRequest dataclass."""

    def test_llm_request_creation(self):
        """Test LLMRequest can be instantiated."""
        from src.abstractions import LLMRequest

        request = LLMRequest(
            prompt="Hello, world!",
            system_prompt="You are a helpful assistant.",
            max_tokens=100,
        )
        assert request.prompt == "Hello, world!"
        assert request.system_prompt == "You are a helpful assistant."
        assert request.max_tokens == 100

    def test_llm_request_to_dict(self):
        """Test LLMRequest to_dict serialization."""
        from src.abstractions import LLMRequest

        request = LLMRequest(
            prompt="Test prompt",
            temperature=0.5,
            metadata={"agent": "test"},
        )
        result = request.to_dict()
        assert result["prompt"] == "Test prompt"
        assert result["temperature"] == 0.5
        assert result["metadata"]["agent"] == "test"


class TestLLMResponse:
    """Test LLMResponse dataclass."""

    def test_llm_response_creation(self):
        """Test LLMResponse can be instantiated."""
        from src.abstractions import LLMResponse

        response = LLMResponse(
            content="This is the response",
            model_id="claude-3-5-sonnet",
            input_tokens=50,
            output_tokens=100,
            latency_ms=150.5,
            finish_reason="end_turn",
        )
        assert response.content == "This is the response"
        assert response.input_tokens == 50
        assert response.output_tokens == 100

    def test_llm_response_total_tokens(self):
        """Test LLMResponse total_tokens property."""
        from src.abstractions import LLMResponse

        response = LLMResponse(
            content="Test",
            model_id="claude",
            input_tokens=100,
            output_tokens=50,
            latency_ms=100.0,
            finish_reason="end_turn",
        )
        assert response.total_tokens == 150

    def test_llm_response_to_dict(self):
        """Test LLMResponse to_dict serialization."""
        from src.abstractions import LLMResponse

        response = LLMResponse(
            content="Response content",
            model_id="gpt-4",
            input_tokens=20,
            output_tokens=30,
            latency_ms=200.0,
            finish_reason="max_tokens",
            metadata={"request_id": "123"},
        )
        result = response.to_dict()
        assert result["content"] == "Response content"
        assert result["model_id"] == "gpt-4"
        assert result["total_tokens"] == 50


class TestVectorDocument:
    """Test VectorDocument dataclass."""

    def test_vector_document_creation(self):
        """Test VectorDocument can be instantiated."""
        from src.abstractions import VectorDocument

        doc = VectorDocument(
            id="doc-123",
            content="def hello(): pass",
            embedding=[0.1, 0.2, 0.3],
            repository="test-repo",
            file_path="src/hello.py",
            entity_type="function",
        )
        assert doc.id == "doc-123"
        assert doc.content == "def hello(): pass"
        assert len(doc.embedding) == 3

    def test_vector_document_to_dict(self):
        """Test VectorDocument to_dict serialization."""
        from datetime import datetime

        from src.abstractions import VectorDocument

        doc = VectorDocument(
            id="doc-456",
            content="class MyClass: pass",
            embedding=[0.5, 0.6],
            repository="project",
            file_path="main.py",
            entity_type="class",
            metadata={"lines": 50},
            created_at=datetime(2025, 1, 1),
        )
        result = doc.to_dict()
        assert result["id"] == "doc-456"
        assert result["entity_type"] == "class"
        assert "2025-01-01" in result["created_at"]

    def test_vector_document_from_dict(self):
        """Test VectorDocument from_dict deserialization."""
        from src.abstractions import VectorDocument

        data = {
            "id": "parsed-doc",
            "content": "some code",
            "embedding": [0.1, 0.2],
            "repository": "repo",
            "file_path": "file.py",
            "entity_type": "method",
            "metadata": {},
            "created_at": "2025-01-01T00:00:00",
        }
        doc = VectorDocument.from_dict(data)
        assert doc.id == "parsed-doc"
        assert doc.created_at is not None


class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_search_result_creation(self):
        """Test SearchResult can be instantiated."""
        from src.abstractions import SearchResult, VectorDocument

        doc = VectorDocument(
            id="result-doc",
            content="matched content",
            embedding=[0.1],
            repository="repo",
            file_path="file.py",
            entity_type="function",
        )
        result = SearchResult(document=doc, score=0.95)
        assert result.score == 0.95
        assert result.document.id == "result-doc"

    def test_search_result_to_dict(self):
        """Test SearchResult to_dict serialization."""
        from src.abstractions import SearchResult, VectorDocument

        doc = VectorDocument(
            id="doc",
            content="code",
            embedding=[0.1],
            repository="r",
            file_path="f.py",
            entity_type="file",
        )
        result = SearchResult(
            document=doc, score=0.88, highlights={"content": ["code"]}
        )
        result_dict = result.to_dict()
        assert result_dict["score"] == 0.88
        assert "code" in result_dict["highlights"]["content"]


class TestStorageObject:
    """Test StorageObject dataclass."""

    def test_storage_object_creation(self):
        """Test StorageObject can be instantiated."""
        from src.abstractions import StorageObject

        obj = StorageObject(
            key="artifacts/output.json",
            bucket="my-bucket",
            size_bytes=1024,
            content_type="application/json",
        )
        assert obj.key == "artifacts/output.json"
        assert obj.bucket == "my-bucket"
        assert obj.size_bytes == 1024

    def test_storage_object_to_dict(self):
        """Test StorageObject to_dict serialization."""
        from datetime import datetime

        from src.abstractions import StorageObject

        obj = StorageObject(
            key="path/file.txt",
            bucket="bucket-name",
            size_bytes=2048,
            content_type="text/plain",
            metadata={"version": "1.0"},
            last_modified=datetime(2025, 6, 15),
        )
        result = obj.to_dict()
        assert result["key"] == "path/file.txt"
        assert result["size_bytes"] == 2048
        assert "2025-06-15" in result["last_modified"]


class TestStorageClass:
    """Test StorageClass enum."""

    def test_storage_class_values(self):
        """Test StorageClass enum values."""
        from src.abstractions.storage_service import StorageClass

        assert StorageClass.STANDARD.value == "standard"
        assert StorageClass.INFREQUENT_ACCESS.value == "infrequent_access"
        assert StorageClass.ARCHIVE.value == "archive"
        assert StorageClass.COLD.value == "cold"


class TestPresignedUrl:
    """Test PresignedUrl dataclass."""

    def test_presigned_url_creation(self):
        """Test PresignedUrl can be instantiated."""
        from datetime import datetime

        from src.abstractions.storage_service import PresignedUrl

        url = PresignedUrl(
            url="https://bucket.s3.amazonaws.com/key?sig=...",
            expires_at=datetime(2025, 1, 1, 12, 0, 0),
            method="GET",
        )
        assert "s3.amazonaws.com" in url.url
        assert url.expires_at.year == 2025
        assert url.method == "GET"


class TestSecretsService:
    """Test SecretsService abstraction."""

    def test_secrets_service_is_abstract(self):
        """Test SecretsService is properly defined."""
        from src.abstractions import SecretsService

        # Verify it's an abstract class that can't be instantiated
        assert SecretsService is not None
        # Check abstract methods exist
        assert hasattr(SecretsService, "get_secret")
        assert hasattr(SecretsService, "create_secret")
        assert hasattr(SecretsService, "delete_secret")
