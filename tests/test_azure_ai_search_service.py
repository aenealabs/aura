"""
Project Aura - Azure AI Search Service Tests

Comprehensive tests for the Azure AI Search VectorDatabaseService implementation.
Tests mock mode functionality and Azure API mocking.
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
import sys
from unittest.mock import MagicMock, patch

# Check if real Azure SDK is available for tests that require it
try:
    from azure.search.documents.models import VectorizedQuery  # noqa: F401

    REAL_AZURE_SDK_AVAILABLE = True
except ImportError:
    REAL_AZURE_SDK_AVAILABLE = False

# Skip marker for tests that require real Azure SDK imports
requires_azure_sdk = pytest.mark.skipif(
    not REAL_AZURE_SDK_AVAILABLE,
    reason="Azure Search SDK not installed (azure-search-documents)",
)

# Save original modules before mocking to prevent test pollution
_azure_modules_to_save = [
    "azure",
    "azure.search",
    "azure.search.documents",
    "azure.search.documents.indexes",
    "azure.search.documents.indexes.models",
    "azure.search.documents.models",
    "azure.core",
    "azure.core.credentials",
    "azure.identity",
]
_original_azure_modules = {m: sys.modules.get(m) for m in _azure_modules_to_save}
_original_azure_search_service = sys.modules.get(
    "src.services.providers.azure.azure_ai_search_service"
)

# Mock Azure SDK before imports
mock_search_client = MagicMock()
mock_index_client = MagicMock()
mock_credential = MagicMock()

sys.modules["azure"] = MagicMock()
sys.modules["azure.search"] = MagicMock()
sys.modules["azure.search.documents"] = MagicMock()
sys.modules["azure.search.documents"].SearchClient = MagicMock(
    return_value=mock_search_client
)
sys.modules["azure.search.documents.indexes"] = MagicMock()
sys.modules["azure.search.documents.indexes"].SearchIndexClient = MagicMock(
    return_value=mock_index_client
)
sys.modules["azure.search.documents.indexes.models"] = MagicMock()
sys.modules["azure.search.documents.models"] = MagicMock()
sys.modules["azure.core"] = MagicMock()
sys.modules["azure.core.credentials"] = MagicMock()
sys.modules["azure.core.credentials"].AzureKeyCredential = MagicMock(
    return_value=mock_credential
)
sys.modules["azure.identity"] = MagicMock()
sys.modules["azure.identity"].DefaultAzureCredential = MagicMock(
    return_value=mock_credential
)

from src.abstractions.vector_database import IndexConfig, SearchResult, VectorDocument
from src.services.providers.azure.azure_ai_search_service import AzureAISearchService

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_azure_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)

if _original_azure_search_service is not None:
    sys.modules["src.services.providers.azure.azure_ai_search_service"] = (
        _original_azure_search_service
    )


class TestAzureAISearchServiceInit:
    """Tests for AzureAISearchService initialization."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        service = AzureAISearchService()
        assert service.endpoint is None
        assert service.index_name == "aura-vectors"
        assert service.key is None
        assert service._connected is False
        assert service._mock_documents == {}

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        service = AzureAISearchService(
            endpoint="https://test.search.windows.net",
            index_name="custom-index",
            key="test-api-key",
        )
        assert service.endpoint == "https://test.search.windows.net"
        assert service.index_name == "custom-index"
        assert service.key == "test-api-key"

    def test_init_from_environment(self):
        """Test initialization from environment variables."""
        os.environ["AZURE_SEARCH_ENDPOINT"] = "https://env.search.windows.net"
        os.environ["AZURE_SEARCH_KEY"] = "env-key"

        try:
            service = AzureAISearchService()
            assert service.endpoint == "https://env.search.windows.net"
            assert service.key == "env-key"
        finally:
            del os.environ["AZURE_SEARCH_ENDPOINT"]
            del os.environ["AZURE_SEARCH_KEY"]

    def test_is_mock_mode_without_endpoint(self):
        """Test is_mock_mode when no endpoint is set."""
        service = AzureAISearchService()
        # With our mocking AZURE_SEARCH_AVAILABLE is technically available
        # but no endpoint means mock mode
        assert service.is_mock_mode is True

    def test_is_mock_mode_with_endpoint(self):
        """Test is_mock_mode when endpoint is set."""
        service = AzureAISearchService(endpoint="https://test.search.windows.net")
        # With Azure SDK mocked and endpoint present, not mock mode
        assert service.is_mock_mode is False


class TestAzureAISearchServiceConnect:
    """Tests for connect/disconnect operations."""

    @pytest.mark.asyncio
    async def test_connect_mock_mode(self):
        """Test connect in mock mode."""
        service = AzureAISearchService()
        result = await service.connect()
        assert result is True
        assert service._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect."""
        service = AzureAISearchService()
        await service.connect()
        await service.disconnect()
        assert service._connected is False
        assert service._index_client is None
        assert service._search_client is None

    @pytest.mark.asyncio
    async def test_is_connected(self):
        """Test is_connected."""
        service = AzureAISearchService()
        assert await service.is_connected() is False
        await service.connect()
        assert await service.is_connected() is True


class TestAzureAISearchServiceIndexOperations:
    """Tests for index operations."""

    @pytest.fixture
    def connected_service(self):
        """Create a connected mock service."""
        service = AzureAISearchService()
        service._connected = True
        return service

    @pytest.mark.asyncio
    async def test_create_index_mock_mode(self, connected_service):
        """Test create_index in mock mode."""
        config = IndexConfig(
            name="test-index", dimension=1536, similarity_metric="cosine"
        )
        result = await connected_service.create_index(config)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_index_mock_mode(self, connected_service):
        """Test delete_index in mock mode."""
        result = await connected_service.delete_index("test-index")
        assert result is True

    @pytest.mark.asyncio
    async def test_index_exists_mock_mode(self, connected_service):
        """Test index_exists in mock mode."""
        result = await connected_service.index_exists("test-index")
        assert result is True


class TestAzureAISearchServiceDocumentOperations:
    """Tests for document CRUD operations."""

    @pytest.fixture
    def connected_service(self):
        """Create a connected mock service."""
        service = AzureAISearchService()
        service._connected = True
        return service

    @pytest.fixture
    def sample_document(self):
        """Create a sample VectorDocument."""
        return VectorDocument(
            id="doc-1",
            content="Sample code content",
            embedding=[0.1] * 1536,
            repository="test/repo",
            file_path="src/main.py",
            entity_type="function",
            metadata={"language": "python"},
        )

    @pytest.mark.asyncio
    async def test_index_document(self, connected_service, sample_document):
        """Test indexing a document."""
        doc_id = await connected_service.index_document("test-index", sample_document)
        assert doc_id == "doc-1"
        assert "doc-1" in connected_service._mock_documents

    @pytest.mark.asyncio
    async def test_get_document_exists(self, connected_service, sample_document):
        """Test getting an existing document."""
        await connected_service.index_document("test-index", sample_document)
        result = await connected_service.get_document("test-index", "doc-1")
        assert result is not None
        assert result.id == "doc-1"
        assert result.content == "Sample code content"

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, connected_service):
        """Test getting a non-existent document."""
        result = await connected_service.get_document("test-index", "non-existent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_document_exists(self, connected_service, sample_document):
        """Test deleting an existing document."""
        await connected_service.index_document("test-index", sample_document)
        result = await connected_service.delete_document("test-index", "doc-1")
        assert result is True
        assert "doc-1" not in connected_service._mock_documents

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, connected_service):
        """Test deleting a non-existent document."""
        result = await connected_service.delete_document("test-index", "non-existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_bulk_index(self, connected_service):
        """Test bulk indexing documents."""
        docs = [
            VectorDocument(
                id=f"doc-{i}",
                content=f"Content {i}",
                embedding=[0.1] * 1536,
                repository="test/repo",
                file_path=f"src/file{i}.py",
                entity_type="function",
            )
            for i in range(5)
        ]
        result = await connected_service.bulk_index("test-index", docs)
        assert result["success_count"] == 5
        assert result["error_count"] == 0
        assert len(connected_service._mock_documents) == 5


class TestAzureAISearchServiceSearchOperations:
    """Tests for search operations."""

    @pytest.fixture
    async def populated_service(self):
        """Create a service with indexed documents."""
        service = AzureAISearchService()
        service._connected = True

        docs = [
            VectorDocument(
                id=f"doc-{i}",
                content=f"Content {i}",
                embedding=[0.1 * i] * 1536,
                repository="test/repo",
                file_path=f"src/file{i}.py",
                entity_type="function",
            )
            for i in range(10)
        ]
        for doc in docs:
            await service.index_document("test-index", doc)
        return service

    @pytest.mark.asyncio
    async def test_search_similar(self, populated_service):
        """Test similarity search."""
        query_embedding = [0.5] * 1536
        results = await populated_service.search_similar(
            "test-index", query_embedding, k=5
        )
        assert len(results) == 5
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_similar_with_limit(self, populated_service):
        """Test similarity search with k limit."""
        query_embedding = [0.5] * 1536
        results = await populated_service.search_similar(
            "test-index", query_embedding, k=3
        )
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_similar_scores_descending(self, populated_service):
        """Test that search results have descending scores."""
        query_embedding = [0.5] * 1536
        results = await populated_service.search_similar(
            "test-index", query_embedding, k=5
        )
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_hybrid_search_mock_mode(self, populated_service):
        """Test hybrid search in mock mode."""
        query_embedding = [0.5] * 1536
        results = await populated_service.hybrid_search(
            "test-index", "sample query", query_embedding, k=5
        )
        # Mock mode falls back to search_similar
        assert len(results) == 5


class TestAzureAISearchServiceDeleteByOperations:
    """Tests for delete_by_* operations."""

    @pytest.fixture
    async def populated_service(self):
        """Create a service with documents from multiple repos."""
        service = AzureAISearchService()
        service._connected = True

        # Add docs from different repositories
        for repo in ["repo-a", "repo-b"]:
            for i in range(3):
                doc = VectorDocument(
                    id=f"{repo}-doc-{i}",
                    content=f"Content for {repo} {i}",
                    embedding=[0.1] * 1536,
                    repository=repo,
                    file_path=f"src/file{i}.py",
                    entity_type="function",
                )
                await service.index_document("test-index", doc)
        return service

    @pytest.mark.asyncio
    async def test_delete_by_repository(self, populated_service):
        """Test deleting all documents for a repository."""
        initial_count = len(populated_service._mock_documents)
        deleted = await populated_service.delete_by_repository("test-index", "repo-a")

        assert deleted == 3
        assert len(populated_service._mock_documents) == initial_count - 3
        # Verify repo-a docs are gone
        for doc_id in populated_service._mock_documents:
            assert "repo-a" not in doc_id

    @pytest.mark.asyncio
    async def test_delete_by_repository_not_found(self, populated_service):
        """Test deleting documents for non-existent repository."""
        deleted = await populated_service.delete_by_repository(
            "test-index", "non-existent"
        )
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_delete_by_file_path(self, populated_service):
        """Test deleting documents by file path."""
        deleted = await populated_service.delete_by_file_path(
            "test-index", "src/file0.py", "repo-a"
        )
        assert deleted == 1

    @pytest.mark.asyncio
    async def test_delete_by_file_path_not_found(self, populated_service):
        """Test deleting by non-existent file path."""
        deleted = await populated_service.delete_by_file_path(
            "test-index", "non/existent.py", "repo-a"
        )
        assert deleted == 0


class TestAzureAISearchServiceHealth:
    """Tests for health and stats operations."""

    @pytest.mark.asyncio
    async def test_get_health_connected(self):
        """Test health check when connected."""
        service = AzureAISearchService(endpoint="https://test.search.windows.net")
        service._connected = True

        health = await service.get_health()
        assert health["status"] == "healthy"
        assert health["index"] == "aura-vectors"
        assert health["endpoint"] == "https://test.search.windows.net"

    @pytest.mark.asyncio
    async def test_get_health_disconnected(self):
        """Test health check when disconnected."""
        service = AzureAISearchService()

        health = await service.get_health()
        assert health["status"] == "disconnected"
        assert health["mode"] == "mock"

    @pytest.mark.asyncio
    async def test_get_index_stats_mock_mode(self):
        """Test index stats in mock mode."""
        service = AzureAISearchService()
        service._connected = True
        service._mock_documents = {"doc-1": {}, "doc-2": {}, "doc-3": {}}

        stats = await service.get_index_stats("test-index")
        assert stats["document_count"] == 3


class TestAzureAISearchServiceAzureMode:
    """Tests for Azure (non-mock) mode with mocked Azure SDK."""

    @pytest.fixture
    def azure_service(self):
        """Create an Azure mode service with mocked clients."""
        # Temporarily set AZURE_SEARCH_AVAILABLE to True at module level
        import src.services.providers.azure.azure_ai_search_service as module

        original_available = module.AZURE_SEARCH_AVAILABLE
        module.AZURE_SEARCH_AVAILABLE = True

        service = AzureAISearchService(
            endpoint="https://test.search.windows.net", key="test-key"
        )

        # Mock the clients
        service._index_client = MagicMock()
        service._search_client = MagicMock()
        service._connected = True

        yield service

        # Restore original value
        module.AZURE_SEARCH_AVAILABLE = original_available

    @pytest.mark.asyncio
    async def test_connect_with_key(self, azure_service):
        """Test connecting with API key."""
        import src.services.providers.azure.azure_ai_search_service as module

        module.AZURE_SEARCH_AVAILABLE = True

        service = AzureAISearchService(
            endpoint="https://test.search.windows.net", key="test-key"
        )

        with patch.object(service, "_connected", True):
            assert await service.is_connected() is True

    @pytest.mark.asyncio
    async def test_create_index_azure_mode(self, azure_service):
        """Test create_index in Azure mode."""
        config = IndexConfig(
            name="test-index",
            dimension=1536,
            similarity_metric="cosine",
            m=16,
            ef_construction=100,
        )

        await azure_service.create_index(config)
        azure_service._index_client.create_or_update_index.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_index_azure_mode_error(self, azure_service):
        """Test create_index error handling in Azure mode."""
        azure_service._index_client.create_or_update_index.side_effect = Exception(
            "Azure error"
        )

        config = IndexConfig(name="test-index", dimension=1536)
        result = await azure_service.create_index(config)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_index_azure_mode(self, azure_service):
        """Test delete_index in Azure mode."""
        await azure_service.delete_index("test-index")
        azure_service._index_client.delete_index.assert_called_once_with("test-index")

    @pytest.mark.asyncio
    async def test_delete_index_azure_mode_error(self, azure_service):
        """Test delete_index error handling."""
        azure_service._index_client.delete_index.side_effect = Exception("Delete error")
        result = await azure_service.delete_index("test-index")
        assert result is False

    @pytest.mark.asyncio
    async def test_index_exists_azure_mode(self, azure_service):
        """Test index_exists in Azure mode."""
        azure_service._index_client.get_index.return_value = MagicMock()
        result = await azure_service.index_exists("test-index")
        assert result is True

    @pytest.mark.asyncio
    async def test_index_exists_not_found(self, azure_service):
        """Test index_exists when index doesn't exist."""
        azure_service._index_client.get_index.side_effect = Exception("Not found")
        result = await azure_service.index_exists("non-existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_index_document_azure_mode(self, azure_service):
        """Test indexing document in Azure mode."""
        doc = VectorDocument(
            id="doc-1",
            content="Test content",
            embedding=[0.1] * 1536,
            repository="test/repo",
            file_path="src/main.py",
            entity_type="function",
        )

        result = await azure_service.index_document("test-index", doc)
        azure_service._search_client.upload_documents.assert_called_once()
        assert result == "doc-1"

    @pytest.mark.asyncio
    async def test_bulk_index_azure_mode(self, azure_service):
        """Test bulk index in Azure mode."""
        docs = [
            VectorDocument(
                id=f"doc-{i}",
                content=f"Content {i}",
                embedding=[0.1] * 1536,
                repository="test/repo",
                file_path=f"src/file{i}.py",
                entity_type="function",
            )
            for i in range(3)
        ]

        # Mock result with succeeded property
        mock_results = [MagicMock(succeeded=True) for _ in range(3)]
        azure_service._search_client.upload_documents.return_value = mock_results

        result = await azure_service.bulk_index("test-index", docs)
        assert result["success_count"] == 3
        assert result["error_count"] == 0
        assert result["total"] == 3

    @pytest.mark.asyncio
    async def test_get_document_azure_mode(self, azure_service):
        """Test get_document in Azure mode."""
        azure_service._search_client.get_document.return_value = {
            "id": "doc-1",
            "content": "Test content",
            "embedding": [0.1] * 10,
            "repository": "test/repo",
            "file_path": "src/main.py",
            "entity_type": "function",
        }

        result = await azure_service.get_document("test-index", "doc-1")
        assert result is not None
        assert result.id == "doc-1"
        assert result.content == "Test content"

    @pytest.mark.asyncio
    async def test_get_document_not_found_azure_mode(self, azure_service):
        """Test get_document when not found in Azure mode."""
        azure_service._search_client.get_document.side_effect = Exception("Not found")
        result = await azure_service.get_document("test-index", "non-existent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_document_azure_mode(self, azure_service):
        """Test delete_document in Azure mode."""
        result = await azure_service.delete_document("test-index", "doc-1")
        azure_service._search_client.delete_documents.assert_called_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_document_error_azure_mode(self, azure_service):
        """Test delete_document error handling."""
        azure_service._search_client.delete_documents.side_effect = Exception(
            "Delete error"
        )
        result = await azure_service.delete_document("test-index", "doc-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_index_stats_azure_mode(self, azure_service):
        """Test get_index_stats in Azure mode."""
        mock_stats = MagicMock()
        mock_stats.document_count = 100
        mock_stats.storage_size = 1024000
        azure_service._index_client.get_index_statistics.return_value = mock_stats

        stats = await azure_service.get_index_stats("test-index")
        assert stats["document_count"] == 100
        assert stats["storage_size"] == 1024000

    @pytest.mark.asyncio
    async def test_get_index_stats_error(self, azure_service):
        """Test get_index_stats error handling."""
        azure_service._index_client.get_index_statistics.side_effect = Exception(
            "Stats error"
        )
        stats = await azure_service.get_index_stats("test-index")
        assert stats["document_count"] == "unknown"


class TestAzureAISearchServiceSearchAzureMode:
    """Tests for search operations in Azure mode."""

    @pytest.fixture
    def azure_service(self):
        """Create an Azure mode service with mocked clients."""
        import src.services.providers.azure.azure_ai_search_service as module

        original_available = module.AZURE_SEARCH_AVAILABLE
        module.AZURE_SEARCH_AVAILABLE = True

        service = AzureAISearchService(
            endpoint="https://test.search.windows.net", key="test-key"
        )
        service._index_client = MagicMock()
        service._search_client = MagicMock()
        service._connected = True

        yield service

        module.AZURE_SEARCH_AVAILABLE = original_available

    @requires_azure_sdk
    @pytest.mark.asyncio
    async def test_search_similar_azure_mode(self, azure_service):
        """Test similarity search in Azure mode."""
        # Mock search results
        mock_results = [
            {
                "id": "doc-1",
                "content": "Content 1",
                "embedding": [0.1] * 10,
                "repository": "test/repo",
                "file_path": "src/main.py",
                "entity_type": "function",
                "@search.score": 0.95,
            }
        ]
        azure_service._search_client.search.return_value = mock_results

        results = await azure_service.search_similar("test-index", [0.5] * 1536, k=10)

        azure_service._search_client.search.assert_called_once()
        assert len(results) == 1
        assert results[0].score == 0.95

    @requires_azure_sdk
    @pytest.mark.asyncio
    async def test_search_similar_with_filters(self, azure_service):
        """Test similarity search with filters."""
        azure_service._search_client.search.return_value = []

        await azure_service.search_similar(
            "test-index",
            [0.5] * 1536,
            k=10,
            filters={"repository": "test/repo", "entity_type": "function"},
        )

        call_kwargs = azure_service._search_client.search.call_args[1]
        assert (
            call_kwargs["filter"]
            == "repository eq 'test/repo' and entity_type eq 'function'"
        )

    @requires_azure_sdk
    @pytest.mark.asyncio
    async def test_search_similar_min_score_filter(self, azure_service):
        """Test similarity search with min_score filter."""
        mock_results = [
            {
                "id": "doc-1",
                "@search.score": 0.9,
                "content": "",
                "embedding": [],
                "repository": "",
                "file_path": "",
                "entity_type": "file",
            },
            {
                "id": "doc-2",
                "@search.score": 0.5,
                "content": "",
                "embedding": [],
                "repository": "",
                "file_path": "",
                "entity_type": "file",
            },
        ]
        azure_service._search_client.search.return_value = mock_results

        results = await azure_service.search_similar(
            "test-index", [0.5] * 1536, k=10, min_score=0.7
        )

        assert len(results) == 1
        assert results[0].document.id == "doc-1"

    @requires_azure_sdk
    @pytest.mark.asyncio
    async def test_hybrid_search_azure_mode(self, azure_service):
        """Test hybrid search in Azure mode."""
        mock_results = [
            {
                "id": "doc-1",
                "content": "Content 1",
                "embedding": [0.1] * 10,
                "repository": "test/repo",
                "file_path": "src/main.py",
                "entity_type": "function",
                "@search.score": 0.95,
                "@search.highlights": {"content": ["<em>highlighted</em>"]},
            }
        ]
        azure_service._search_client.search.return_value = mock_results

        results = await azure_service.hybrid_search(
            "test-index",
            "search query",
            [0.5] * 1536,
            k=10,
            text_weight=0.3,
            vector_weight=0.7,
        )

        assert len(results) == 1
        assert results[0].highlights == {"content": ["<em>highlighted</em>"]}

    @pytest.mark.asyncio
    async def test_delete_by_repository_azure_mode(self, azure_service):
        """Test delete_by_repository in Azure mode."""
        mock_results = [{"id": "doc-1"}, {"id": "doc-2"}]
        azure_service._search_client.search.return_value = mock_results

        deleted = await azure_service.delete_by_repository("test-index", "test/repo")

        assert deleted == 2
        azure_service._search_client.delete_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_repository_empty_azure_mode(self, azure_service):
        """Test delete_by_repository when no docs found."""
        azure_service._search_client.search.return_value = []

        deleted = await azure_service.delete_by_repository("test-index", "test/repo")

        assert deleted == 0
        azure_service._search_client.delete_documents.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_by_file_path_azure_mode(self, azure_service):
        """Test delete_by_file_path in Azure mode."""
        mock_results = [{"id": "doc-1"}]
        azure_service._search_client.search.return_value = mock_results

        deleted = await azure_service.delete_by_file_path(
            "test-index", "src/main.py", "test/repo"
        )

        assert deleted == 1


class TestVectorDocumentHelpers:
    """Tests for VectorDocument helper methods."""

    def test_vector_document_to_dict(self):
        """Test VectorDocument.to_dict()."""
        doc = VectorDocument(
            id="doc-1",
            content="Test content",
            embedding=[0.1, 0.2, 0.3],
            repository="test/repo",
            file_path="src/main.py",
            entity_type="function",
            metadata={"language": "python"},
        )

        d = doc.to_dict()
        assert d["id"] == "doc-1"
        assert d["content"] == "Test content"
        assert d["embedding"] == [0.1, 0.2, 0.3]
        assert d["repository"] == "test/repo"

    def test_vector_document_from_dict(self):
        """Test VectorDocument.from_dict()."""
        data = {
            "id": "doc-1",
            "content": "Test content",
            "embedding": [0.1, 0.2, 0.3],
            "repository": "test/repo",
            "file_path": "src/main.py",
            "entity_type": "function",
        }

        doc = VectorDocument.from_dict(data)
        assert doc.id == "doc-1"
        assert doc.content == "Test content"
        assert doc.embedding == [0.1, 0.2, 0.3]
