"""
Project Aura - OpenSearch Vector Service Tests

Comprehensive tests for OpenSearch k-NN vector search operations.
Target: 85% coverage of src/services/opensearch_vector_service.py
"""

# ruff: noqa: PLR2004

import os
import platform

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.opensearch_vector_service import (
    OpenSearchError,
    OpenSearchMode,
    OpenSearchVectorService,
)


class TestOpenSearchVectorService:
    """Test suite for OpenSearchVectorService in mock mode."""

    def test_initialization_mock_mode(self):
        """Test service initialization in MOCK mode."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        assert service.mode == OpenSearchMode.MOCK
        assert service.endpoint == "opensearch.aura.local"
        assert service.port == 9200
        assert service.index_name == "aura-code-embeddings"
        assert service.vector_dimension == 1024
        assert service.use_iam_auth is True
        assert isinstance(service.mock_index, dict)
        assert isinstance(service.query_cache, dict)

    def test_initialization_custom_config(self):
        """Test service initialization with custom configuration."""
        service = OpenSearchVectorService(
            mode=OpenSearchMode.MOCK,
            endpoint="custom.opensearch.local",
            port=9443,
            index_name="custom-index",
            vector_dimension=384,
            use_iam_auth=False,
        )

        assert service.endpoint == "custom.opensearch.local"
        assert service.port == 9443
        assert service.index_name == "custom-index"
        assert service.vector_dimension == 384
        assert service.use_iam_auth is False

    def test_initial_sample_data_loaded(self):
        """Test that initial sample data is loaded in mock mode."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Check sample documents
        assert "security_policy_sha256" in service.mock_index
        assert "data_processor_doc" in service.mock_index

        # Check document structure
        doc = service.mock_index["security_policy_sha256"]
        assert "text" in doc
        assert "vector" in doc
        assert "metadata" in doc

    def test_index_embedding_success(self):
        """Test indexing an embedding."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        vector = [0.5] * 1024
        result = service.index_embedding(
            doc_id="test_doc_123",
            text="def hello(): return 'world'",
            vector=vector,
            metadata={"file": "test.py", "line": 10},
        )

        assert result is True
        assert "test_doc_123" in service.mock_index

        doc = service.mock_index["test_doc_123"]
        assert doc["text"] == "def hello(): return 'world'"
        assert doc["vector"] == vector
        assert doc["metadata"]["file"] == "test.py"
        assert "timestamp" in doc

    def test_index_embedding_dimension_mismatch(self):
        """Test indexing with wrong vector dimension raises error."""
        service = OpenSearchVectorService(
            mode=OpenSearchMode.MOCK, vector_dimension=1024
        )

        with pytest.raises(ValueError, match="Vector dimension mismatch"):
            service.index_embedding(
                doc_id="test",
                text="test",
                vector=[0.1] * 512,  # Wrong dimension
            )

    def test_index_embedding_no_metadata(self):
        """Test indexing without metadata."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        result = service.index_embedding(
            doc_id="no_meta",
            text="test text",
            vector=[0.1] * 1024,
        )

        assert result is True
        assert service.mock_index["no_meta"]["metadata"] == {}

    def test_search_similar_success(self):
        """Test similarity search."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Add test document
        vector = [0.3] * 1024
        service.index_embedding(
            doc_id="search_target",
            text="search target text",
            vector=vector,
        )

        # Search with similar vector
        query_vector = [0.3] * 1024
        results = service.search_similar(query_vector, k=5, min_score=0.0)

        assert len(results) > 0
        assert all("id" in r for r in results)
        assert all("text" in r for r in results)
        assert all("score" in r for r in results)

    def test_search_similar_dimension_mismatch(self):
        """Test search with wrong vector dimension raises error."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        with pytest.raises(ValueError, match="Vector dimension mismatch"):
            service.search_similar([0.1] * 512, k=5)

    def test_search_similar_with_min_score(self):
        """Test search respects min_score filter."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Add documents with different scores
        service.index_embedding("high_score", "high", [0.9] * 1024)
        service.index_embedding("low_score", "low", [0.1] * 1024)

        # Search with high min_score
        query_vector = [0.9] * 1024
        results = service.search_similar(query_vector, k=10, min_score=0.8)

        # Should filter out low score document
        assert all(r["score"] >= 0.8 for r in results)

    def test_search_similar_caches_results(self):
        """Test that search results are cached."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        query_vector = [0.5] * 1024
        results1 = service.search_similar(query_vector, k=5, min_score=0.0)

        # Check cache was populated
        assert len(service.query_cache) > 0

        # Second search should hit cache
        results2 = service.search_similar(query_vector, k=5, min_score=0.0)

        assert results1 == results2

    def test_search_similar_respects_k_limit(self):
        """Test search respects k parameter."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Add many documents
        for i in range(10):
            service.index_embedding(f"doc_{i}", f"text {i}", [0.5] * 1024)

        query_vector = [0.5] * 1024
        results = service.search_similar(query_vector, k=3, min_score=0.0)

        assert len(results) <= 3

    def test_search_by_metadata_success(self):
        """Test metadata search."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Add document with specific metadata
        service.index_embedding(
            "meta_search",
            "test",
            [0.1] * 1024,
            metadata={"category": "security"},
        )

        results = service.search_by_metadata({"category": "security"})

        assert len(results) >= 1
        assert any(r["id"] == "meta_search" for r in results)

    def test_search_by_metadata_no_matches(self):
        """Test metadata search with no matches."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        results = service.search_by_metadata({"nonexistent_key": "value"})

        assert results == []

    def test_search_by_metadata_respects_limit(self):
        """Test metadata search respects limit."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Add multiple documents with same category
        for i in range(10):
            service.index_embedding(
                f"cat_{i}",
                f"text {i}",
                [0.1] * 1024,
                metadata={"category": "test"},
            )

        results = service.search_by_metadata({"category": "test"}, limit=3)

        assert len(results) <= 3


class TestOpenSearchDeleteOperations:
    """Tests for OpenSearch delete operations in mock mode."""

    def test_delete_document_success(self):
        """Test deleting a document."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        service.index_embedding("to_delete", "text", [0.1] * 1024)
        assert "to_delete" in service.mock_index

        result = service.delete_document("to_delete")

        assert result is True
        assert "to_delete" not in service.mock_index

    def test_delete_document_not_found(self):
        """Test deleting non-existent document returns False."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        result = service.delete_document("nonexistent")

        assert result is False

    def test_delete_document_clears_cache(self):
        """Test that deleting document clears query cache."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Add document and search to populate cache
        service.index_embedding("cache_doc", "text", [0.5] * 1024)
        service.search_similar([0.5] * 1024, k=5, min_score=0.0)
        assert len(service.query_cache) > 0

        # Delete document
        service.delete_document("cache_doc")

        assert len(service.query_cache) == 0

    def test_delete_by_repository_success(self):
        """Test deleting all documents for a repository."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Add documents with repository metadata
        service.index_embedding(
            "repo1_doc1",
            "text1",
            [0.1] * 1024,
            metadata={"repository": "owner/test-repo"},
        )
        service.index_embedding(
            "repo1_doc2",
            "text2",
            [0.1] * 1024,
            metadata={"repository": "owner/test-repo"},
        )
        service.index_embedding(
            "other_doc",
            "text3",
            [0.1] * 1024,
            metadata={"repository": "owner/other-repo"},
        )

        deleted = service.delete_by_repository("owner/test-repo")

        assert deleted == 2
        assert "repo1_doc1" not in service.mock_index
        assert "repo1_doc2" not in service.mock_index
        assert "other_doc" in service.mock_index

    def test_delete_by_repository_no_matches(self):
        """Test delete_by_repository with no matching documents."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        deleted = service.delete_by_repository("nonexistent/repo")

        assert deleted == 0

    def test_delete_by_repository_clears_cache(self):
        """Test that delete_by_repository selectively invalidates cache entries."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Populate cache with entries that include the repository in filter
        service.search_similar(
            [0.5] * 1024, k=5, min_score=0.0, filters={"repository": "owner/test-repo"}
        )
        # Also add an unrelated cache entry
        service.search_similar([0.6] * 1024, k=3, min_score=0.0)
        initial_cache_size = len(service.query_cache)
        assert initial_cache_size >= 1

        # Delete repository - should only invalidate matching cache entries
        service.delete_by_repository("owner/test-repo")

        # Cache may still have unrelated entries (selective invalidation)
        # The key insight is that entries containing "owner/test-repo" are removed
        assert len(service.query_cache) < initial_cache_size or initial_cache_size == 1

    def test_delete_by_file_path_success(self):
        """Test deleting all documents for a file."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        service.index_embedding(
            "file_doc1", "text1", [0.1] * 1024, metadata={"file_path": "src/target.py"}
        )
        service.index_embedding(
            "file_doc2", "text2", [0.1] * 1024, metadata={"file_path": "src/target.py"}
        )
        service.index_embedding(
            "other_file", "text3", [0.1] * 1024, metadata={"file_path": "src/other.py"}
        )

        deleted = service.delete_by_file_path("src/target.py")

        assert deleted == 2
        assert "file_doc1" not in service.mock_index
        assert "file_doc2" not in service.mock_index
        assert "other_file" in service.mock_index

    def test_delete_by_file_path_no_matches(self):
        """Test delete_by_file_path with no matching file."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        deleted = service.delete_by_file_path("nonexistent/file.py")

        assert deleted == 0


class TestOpenSearchClusterHealth:
    """Tests for cluster health operations."""

    def test_get_cluster_health_mock(self):
        """Test getting cluster health in mock mode."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        health = service.get_cluster_health()

        assert health["status"] == "green"
        assert "number_of_nodes" in health
        assert "active_shards" in health


class TestOpenSearchBulkOperations:
    """Tests for bulk indexing operations."""

    def test_bulk_index_embeddings_success(self):
        """Test bulk indexing multiple documents."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        documents = [
            {"id": "bulk_1", "text": "text 1", "vector": [0.1] * 1024},
            {"id": "bulk_2", "text": "text 2", "vector": [0.2] * 1024},
            {
                "id": "bulk_3",
                "text": "text 3",
                "vector": [0.3] * 1024,
                "metadata": {"key": "value"},
            },
        ]

        result = service.bulk_index_embeddings(documents)

        assert result["success_count"] == 3
        assert result["error_count"] == 0
        assert result["errors"] == []

        # Check all documents indexed
        assert "bulk_1" in service.mock_index
        assert "bulk_2" in service.mock_index
        assert "bulk_3" in service.mock_index
        assert service.mock_index["bulk_3"]["metadata"]["key"] == "value"

    def test_bulk_index_embeddings_empty_list(self):
        """Test bulk indexing with empty list."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        result = service.bulk_index_embeddings([])

        assert result["success_count"] == 0
        assert result["error_count"] == 0


class TestOpenSearchCacheKey:
    """Tests for cache key generation."""

    def test_cache_key_generation(self):
        """Test cache key is generated correctly."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        vector = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0] + [0.0] * 1014
        key1 = service._cache_key(vector, 5, 0.7, None)
        key2 = service._cache_key(vector, 5, 0.7, None)

        # Same inputs should produce same key
        assert key1 == key2

    def test_cache_key_different_k(self):
        """Test cache key differs for different k values."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        vector = [0.1] * 1024
        key1 = service._cache_key(vector, 5, 0.7, None)
        key2 = service._cache_key(vector, 10, 0.7, None)

        assert key1 != key2

    def test_cache_key_with_filters(self):
        """Test cache key includes filters."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        vector = [0.1] * 1024
        key1 = service._cache_key(vector, 5, 0.7, {"category": "a"})
        key2 = service._cache_key(vector, 5, 0.7, {"category": "b"})

        assert key1 != key2


class TestOpenSearchClose:
    """Tests for connection close method."""

    def test_close_mock_mode(self):
        """Test close method in mock mode does not raise."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Should not raise exception
        service.close()


class TestCreateVectorService:
    """Tests for create_vector_service factory function."""

    def test_create_vector_service_default_mock_mode(self):
        """Test create_vector_service defaults to mock mode."""
        from src.services.opensearch_vector_service import create_vector_service

        # Ensure no OPENSEARCH_ENDPOINT set
        if "OPENSEARCH_ENDPOINT" in os.environ:
            del os.environ["OPENSEARCH_ENDPOINT"]

        service = create_vector_service()

        assert service.mode == OpenSearchMode.MOCK

    def test_create_vector_service_with_environment(self):
        """Test create_vector_service accepts environment parameter."""
        from src.services.opensearch_vector_service import create_vector_service

        service = create_vector_service("dev")

        assert service is not None
        assert service.mode == OpenSearchMode.MOCK

    def test_create_vector_service_uses_env_vars(self):
        """Test create_vector_service reads from environment variables."""
        from src.services.opensearch_vector_service import create_vector_service

        os.environ["OPENSEARCH_PORT"] = "9999"
        os.environ["VECTOR_DIMENSION"] = "384"

        try:
            service = create_vector_service()
            assert service.port == 9999
            assert service.vector_dimension == 384
        finally:
            del os.environ["OPENSEARCH_PORT"]
            del os.environ["VECTOR_DIMENSION"]


class TestOpenSearchError:
    """Tests for OpenSearchError exception."""

    def test_opensearch_error_can_be_raised(self):
        """Test OpenSearchError exception works correctly."""
        with pytest.raises(OpenSearchError, match="Test error"):
            raise OpenSearchError("Test error")


class TestOpenSearchAWSMode:
    """Tests for OpenSearch AWS mode with mocked client."""

    def test_aws_mode_fallback_to_mock(self):
        """Test AWS mode falls back to MOCK when client unavailable."""
        # OPENSEARCH_AVAILABLE is False by default in tests
        service = OpenSearchVectorService(mode=OpenSearchMode.AWS)

        assert service.mode == OpenSearchMode.MOCK

    def test_init_opensearch_client_failure_fallback(self):
        """Test OpenSearch client initialization failure falls back to mock."""
        from unittest.mock import MagicMock, patch

        mock_session = MagicMock()
        mock_session.return_value.get_credentials.side_effect = Exception("Auth failed")

        with patch("src.services.opensearch_vector_service.OPENSEARCH_AVAILABLE", True):
            with patch(
                "src.services.opensearch_vector_service.boto3.Session", mock_session
            ):
                service = OpenSearchVectorService(
                    mode=OpenSearchMode.AWS,
                    endpoint="test.opensearch.local",
                )

                # Should fall back to MOCK mode
                assert service.mode == OpenSearchMode.MOCK

    def test_index_embedding_aws_mode(self):
        """Test index_embedding in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.index.return_value = {"result": "created"}

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        result = service.index_embedding(
            doc_id="test_doc",
            text="test text",
            vector=[0.1] * 1024,
            metadata={"key": "value"},
        )

        assert result is True
        mock_client.index.assert_called_once()

    def test_index_embedding_aws_mode_updated(self):
        """Test index_embedding returns True for 'updated' result."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.index.return_value = {"result": "updated"}

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        result = service.index_embedding(
            doc_id="existing_doc",
            text="updated text",
            vector=[0.2] * 1024,
        )

        assert result is True

    def test_index_embedding_aws_mode_error(self):
        """Test index_embedding in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.index.side_effect = Exception("OpenSearch error")

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        with pytest.raises(OpenSearchError, match="Failed to index document"):
            service.index_embedding(
                doc_id="test",
                text="test",
                vector=[0.1] * 1024,
            )

    def test_search_similar_aws_mode(self):
        """Test search_similar in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "doc1",
                        "_score": 0.95,
                        "_source": {
                            "text": "matched text",
                            "metadata": {"file": "test.py"},
                        },
                    }
                ]
            }
        }

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client
        service.query_cache = {}  # Clear cache

        results = service.search_similar([0.5] * 1024, k=5, min_score=0.0)

        assert len(results) == 1
        assert results[0]["id"] == "doc1"
        assert results[0]["score"] == 0.95
        assert results[0]["text"] == "matched text"
        mock_client.search.assert_called_once()

    def test_search_similar_aws_mode_with_filters(self):
        """Test search_similar with filters in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.search.return_value = {"hits": {"hits": []}}

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client
        service.query_cache = {}

        results = service.search_similar(
            [0.5] * 1024,
            k=5,
            min_score=0.7,
            filters={"category": "test"},
        )

        assert isinstance(results, list)
        mock_client.search.assert_called_once()

    def test_search_similar_aws_mode_error(self):
        """Test search_similar in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("Search failed")

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client
        service.query_cache = {}

        with pytest.raises(OpenSearchError, match="Search failed"):
            service.search_similar([0.5] * 1024, k=5, min_score=0.0)

    def test_search_by_metadata_aws_mode(self):
        """Test search_by_metadata in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "meta_doc",
                        "_source": {
                            "text": "metadata match",
                            "metadata": {"category": "test"},
                        },
                    }
                ]
            }
        }

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        results = service.search_by_metadata({"category": "test"})

        assert len(results) == 1
        assert results[0]["id"] == "meta_doc"

    def test_search_by_metadata_aws_mode_error(self):
        """Test search_by_metadata in AWS mode handles errors gracefully."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("Search error")

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        # Should return empty list, not raise
        results = service.search_by_metadata({"key": "value"})

        assert results == []

    def test_delete_by_repository_aws_mode(self):
        """Test delete_by_repository in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.delete_by_query.return_value = {"deleted": 5}

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client
        # Use cache key that contains the repository for selective invalidation
        service.query_cache = {
            "abc_5_0.0_owner/repo": "value",
            "unrelated_key": "other",
        }

        deleted = service.delete_by_repository("owner/repo")

        assert deleted == 5
        # Selective invalidation: only keys containing "owner/repo" are removed
        assert "abc_5_0.0_owner/repo" not in service.query_cache
        assert "unrelated_key" in service.query_cache
        mock_client.delete_by_query.assert_called_once()

    def test_delete_by_repository_aws_mode_error(self):
        """Test delete_by_repository in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.delete_by_query.side_effect = Exception("Delete error")

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        with pytest.raises(OpenSearchError, match="Failed to delete repository"):
            service.delete_by_repository("owner/repo")

    def test_delete_document_aws_mode(self):
        """Test delete_document in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.delete.return_value = {"result": "deleted"}

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client
        service.query_cache = {"key": "value"}

        result = service.delete_document("doc_id")

        assert result is True
        assert len(service.query_cache) == 0

    def test_delete_document_aws_mode_not_found(self):
        """Test delete_document returns False when document not found."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.delete.side_effect = Exception("not_found: document missing")

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        result = service.delete_document("nonexistent")

        assert result is False

    def test_delete_document_aws_mode_error(self):
        """Test delete_document in AWS mode handles other errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.delete.side_effect = Exception("Connection error")

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        with pytest.raises(OpenSearchError, match="Failed to delete document"):
            service.delete_document("doc_id")

    def test_delete_by_file_path_aws_mode(self):
        """Test delete_by_file_path in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.delete_by_query.return_value = {"deleted": 3}

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client
        # Use cache key that contains the file path for selective invalidation
        service.query_cache = {
            "abc_5_0.0_src/test.py": "value",
            "unrelated_key": "other",
        }

        deleted = service.delete_by_file_path("src/test.py")

        assert deleted == 3
        # Selective invalidation: only keys containing "src/test.py" are removed
        assert "abc_5_0.0_src/test.py" not in service.query_cache
        assert "unrelated_key" in service.query_cache

    def test_delete_by_file_path_aws_mode_error(self):
        """Test delete_by_file_path in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.delete_by_query.side_effect = Exception("Delete error")

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        with pytest.raises(OpenSearchError, match="Failed to delete file documents"):
            service.delete_by_file_path("src/test.py")

    def test_get_cluster_health_aws_mode(self):
        """Test get_cluster_health in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.cluster.health.return_value = {
            "status": "green",
            "number_of_nodes": 3,
            "active_shards": 10,
        }

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        health = service.get_cluster_health()

        assert health["status"] == "green"
        assert health["number_of_nodes"] == 3

    def test_get_cluster_health_aws_mode_error(self):
        """Test get_cluster_health in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.cluster.health.side_effect = Exception("Health check failed")

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        with pytest.raises(OpenSearchError, match="Failed to get cluster health"):
            service.get_cluster_health()

    def test_bulk_index_aws_mode(self):
        """Test bulk_index_embeddings in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.bulk.return_value = {
            "items": [
                {"index": {"_id": "doc1", "result": "created"}},
                {"index": {"_id": "doc2", "result": "created"}},
                {"index": {"_id": "doc3", "error": {"reason": "validation failed"}}},
            ]
        }

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        documents = [
            {"id": "doc1", "text": "text1", "vector": [0.1] * 1024},
            {"id": "doc2", "text": "text2", "vector": [0.2] * 1024},
            {"id": "doc3", "text": "text3", "vector": [0.3] * 1024},
        ]

        result = service.bulk_index_embeddings(documents)

        assert result["success_count"] == 2
        assert result["error_count"] == 1
        assert len(result["errors"]) == 1

    def test_bulk_index_aws_mode_error(self):
        """Test bulk_index_embeddings in AWS mode handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.bulk.side_effect = Exception("Bulk failed")

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        with pytest.raises(OpenSearchError, match="Failed to bulk index documents"):
            service.bulk_index_embeddings(
                [{"id": "doc", "text": "t", "vector": [0.1] * 1024}]
            )

    def test_close_aws_mode_success(self):
        """Test close method in AWS mode."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        service.close()

        mock_client.close.assert_called_once()

    def test_close_aws_mode_error(self):
        """Test close method in AWS mode handles errors gracefully."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.close.side_effect = Exception("Close error")

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        # Should not raise exception
        service.close()

    def test_create_index_if_not_exists_index_exists(self):
        """Test _create_index_if_not_exists when index already exists."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        service._create_index_if_not_exists()

        # Should not call create since index exists
        mock_client.indices.create.assert_not_called()

    def test_create_index_if_not_exists_creates_index(self):
        """Test _create_index_if_not_exists creates new index."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        service._create_index_if_not_exists()

        mock_client.indices.create.assert_called_once()

    def test_create_index_if_not_exists_error(self):
        """Test _create_index_if_not_exists handles errors."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False
        mock_client.indices.create.side_effect = Exception("Create failed")

        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.mode = OpenSearchMode.AWS
        service.client = mock_client

        with pytest.raises(OpenSearchError, match="Failed to create index"):
            service._create_index_if_not_exists()


class TestOpenSearchImportFallbacks:
    """Tests for import fallback behavior and module-level guards."""

    def test_aws_mode_falls_back_when_opensearch_unavailable(self):
        """Test AWS mode falls back to MOCK when OpenSearch library is not available."""
        from unittest.mock import patch

        with patch(
            "src.services.opensearch_vector_service.OPENSEARCH_AVAILABLE", False
        ):
            service = OpenSearchVectorService(mode=OpenSearchMode.AWS)

            # Should fall back to MOCK mode
            assert service.mode == OpenSearchMode.MOCK

    def test_aws_mode_logs_warning_when_opensearch_unavailable(self):
        """Test that a warning is logged when AWS mode falls back to MOCK."""
        from unittest.mock import patch

        with patch(
            "src.services.opensearch_vector_service.OPENSEARCH_AVAILABLE", False
        ):
            with patch("src.services.opensearch_vector_service.logger") as mock_logger:
                _service = OpenSearchVectorService(mode=OpenSearchMode.AWS)

                # Should log warning about falling back
                mock_logger.warning.assert_called()
                warning_call = mock_logger.warning.call_args[0][0]
                assert (
                    "AWS mode requested" in warning_call or "MOCK mode" in warning_call
                )

    def test_mock_mode_works_without_opensearch(self):
        """Test that MOCK mode works even when OpenSearch is not available."""
        from unittest.mock import patch

        with patch(
            "src.services.opensearch_vector_service.OPENSEARCH_AVAILABLE", False
        ):
            service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

            assert service.mode == OpenSearchMode.MOCK
            # Should be able to use mock functionality
            service.index_embedding(
                doc_id="test-doc",
                text="test text",
                vector=[0.1] * 1024,
            )
            results = service.search_similar([0.1] * 1024, k=5, min_score=0.0)
            assert len(results) >= 0

    def test_opensearch_available_flag_is_boolean(self):
        """Test that OPENSEARCH_AVAILABLE is a boolean flag."""
        from src.services.opensearch_vector_service import OPENSEARCH_AVAILABLE

        assert isinstance(OPENSEARCH_AVAILABLE, bool)

    def test_service_initialization_logs_mode(self):
        """Test that service logs its mode on initialization."""
        from unittest.mock import patch

        with patch("src.services.opensearch_vector_service.logger") as mock_logger:
            _service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

            # Should log info about initialization
            info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
            assert any("MOCK" in call or "mock" in call for call in info_calls)

    def test_create_index_if_not_exists_returns_early_in_mock_mode(self):
        """Test _create_index_if_not_exists returns early in mock mode."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Should not raise any errors
        service._create_index_if_not_exists()

        # No client should be accessed
        assert not hasattr(service, "client") or service.mode == OpenSearchMode.MOCK

    def test_init_opensearch_client_with_iam_auth(self):
        """Test AWS client initialization with IAM auth."""
        from unittest.mock import MagicMock, patch

        mock_opensearch = MagicMock()
        mock_session = MagicMock()
        mock_session.get_credentials.return_value = MagicMock()
        mock_session.region_name = "us-east-1"

        with patch("src.services.opensearch_vector_service.OPENSEARCH_AVAILABLE", True):
            with patch(
                "src.services.opensearch_vector_service.boto3.Session",
                return_value=mock_session,
            ):
                with patch(
                    "src.services.opensearch_vector_service.OpenSearch", mock_opensearch
                ):
                    with patch(
                        "src.services.opensearch_vector_service.AWSV4SignerAuth"
                    ):
                        mock_client = MagicMock()
                        mock_client.info.return_value = {"version": {"number": "2.9"}}
                        mock_client.indices.exists.return_value = True
                        mock_opensearch.return_value = mock_client

                        service = OpenSearchVectorService(
                            mode=OpenSearchMode.AWS,
                            endpoint="test.opensearch.local",
                            use_iam_auth=True,
                        )

                        assert service.mode == OpenSearchMode.AWS

    def test_init_opensearch_client_without_iam_auth(self):
        """Test AWS client initialization without IAM auth."""
        from unittest.mock import MagicMock, patch

        mock_opensearch = MagicMock()
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.9"}}
        mock_client.indices.exists.return_value = True
        mock_opensearch.return_value = mock_client

        with patch("src.services.opensearch_vector_service.OPENSEARCH_AVAILABLE", True):
            with patch(
                "src.services.opensearch_vector_service.OpenSearch", mock_opensearch
            ):
                service = OpenSearchVectorService(
                    mode=OpenSearchMode.AWS,
                    endpoint="test.opensearch.local",
                    use_iam_auth=False,
                )

                assert service.mode == OpenSearchMode.AWS

    def test_init_opensearch_client_failure_fallback(self):
        """Test AWS client initialization failure falls back to mock."""
        from unittest.mock import patch

        with patch("src.services.opensearch_vector_service.OPENSEARCH_AVAILABLE", True):
            with patch(
                "src.services.opensearch_vector_service.boto3.Session"
            ) as mock_session:
                mock_session.side_effect = Exception("Connection failed")

                service = OpenSearchVectorService(
                    mode=OpenSearchMode.AWS,
                    endpoint="invalid.endpoint",
                    use_iam_auth=True,
                )

                # Should fall back to MOCK mode
                assert service.mode == OpenSearchMode.MOCK


class TestOpenSearchCacheManagement:
    """Tests for cache limit enforcement and selective invalidation."""

    def test_cache_limit_enforcement(self):
        """Test that cache is pruned when limit is exceeded."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Temporarily set a very low cache limit for testing
        original_limit = OpenSearchVectorService.MAX_QUERY_CACHE_SIZE
        OpenSearchVectorService.MAX_QUERY_CACHE_SIZE = 5

        try:
            # Add many entries to exceed the limit
            for i in range(10):
                # Create unique search queries to populate cache
                vector = [float(i) / 10] * 1024
                service.search_similar(vector, k=5, min_score=0.0)

            # Cache should be pruned
            assert len(service.query_cache) <= 5

        finally:
            # Restore original limit
            OpenSearchVectorService.MAX_QUERY_CACHE_SIZE = original_limit

    def test_enforce_cache_limit_evicts_oldest(self):
        """Test _enforce_cache_limit evicts oldest entries."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Manually populate cache with ordered entries
        service.query_cache = {f"key_{i}": [{"result": i}] for i in range(1010)}

        # Enforce limit
        original_limit = OpenSearchVectorService.MAX_QUERY_CACHE_SIZE
        OpenSearchVectorService.MAX_QUERY_CACHE_SIZE = 1000

        try:
            service._enforce_cache_limit()

            # Should have evicted 110 entries (10% + excess)
            assert len(service.query_cache) < 1010
            # Oldest entries (key_0, key_1, ...) should be removed
            assert "key_0" not in service.query_cache

        finally:
            OpenSearchVectorService.MAX_QUERY_CACHE_SIZE = original_limit

    def test_invalidate_cache_selective_empty_cache(self):
        """Test selective cache invalidation with empty cache."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.query_cache = {}

        result = service._invalidate_cache_selective(repository_id="test/repo")

        assert result == 0

    def test_invalidate_cache_selective_by_repository(self):
        """Test selective cache invalidation by repository."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.query_cache = {
            "key_with_test/repo_1": [{"result": 1}],
            "key_with_test/repo_2": [{"result": 2}],
            "key_without_match": [{"result": 3}],
        }

        result = service._invalidate_cache_selective(repository_id="test/repo")

        assert result == 2
        assert "key_with_test/repo_1" not in service.query_cache
        assert "key_with_test/repo_2" not in service.query_cache
        assert "key_without_match" in service.query_cache

    def test_invalidate_cache_selective_by_file_path(self):
        """Test selective cache invalidation by file path."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.query_cache = {
            "key_with_src/app.py_1": [{"result": 1}],
            "key_without_match": [{"result": 2}],
        }

        result = service._invalidate_cache_selective(file_path="src/app.py")

        assert result == 1
        assert "key_with_src/app.py_1" not in service.query_cache
        assert "key_without_match" in service.query_cache

    def test_invalidate_cache_selective_no_matches(self):
        """Test selective cache invalidation with no matching keys."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)
        service.query_cache = {
            "key_1": [{"result": 1}],
            "key_2": [{"result": 2}],
        }

        result = service._invalidate_cache_selective(repository_id="nonexistent")

        assert result == 0
        assert len(service.query_cache) == 2


class TestOpenSearchModeEnum:
    """Tests for OpenSearchMode enum."""

    def test_opensearch_mode_values(self):
        """Test OpenSearchMode enum values."""
        assert OpenSearchMode.MOCK.value == "mock"
        assert OpenSearchMode.AWS.value == "aws"

    def test_opensearch_mode_comparison(self):
        """Test OpenSearchMode enum comparison."""
        assert OpenSearchMode.MOCK == OpenSearchMode.MOCK
        assert OpenSearchMode.AWS == OpenSearchMode.AWS
        assert OpenSearchMode.MOCK != OpenSearchMode.AWS


class TestOpenSearchEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_search_similar_results_sorted_by_score(self):
        """Test that search results are sorted by score in descending order."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Add documents with different similarity scores
        service.index_embedding("doc_low", "low", [0.1] * 1024)
        service.index_embedding("doc_mid", "mid", [0.5] * 1024)
        service.index_embedding("doc_high", "high", [0.9] * 1024)

        # Search with a vector that should match doc_high best
        query_vector = [0.9] * 1024
        results = service.search_similar(query_vector, k=10, min_score=0.0)

        # Verify results are sorted by score descending
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_similar_with_zero_min_score(self):
        """Test search with min_score of exactly 0.0."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        results = service.search_similar([0.5] * 1024, k=5, min_score=0.0)

        # Should return results since min_score is 0
        assert isinstance(results, list)

    def test_index_embedding_overwrites_existing(self):
        """Test that indexing with same doc_id overwrites existing document."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Index initial document
        service.index_embedding("same_id", "original text", [0.1] * 1024)

        # Overwrite with new content
        service.index_embedding("same_id", "updated text", [0.9] * 1024)

        assert service.mock_index["same_id"]["text"] == "updated text"
        assert service.mock_index["same_id"]["vector"] == [0.9] * 1024

    def test_bulk_index_with_mixed_metadata(self):
        """Test bulk indexing with some documents having metadata and some without."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        documents = [
            {
                "id": "with_meta",
                "text": "text1",
                "vector": [0.1] * 1024,
                "metadata": {"key": "value"},
            },
            {"id": "without_meta", "text": "text2", "vector": [0.2] * 1024},
        ]

        result = service.bulk_index_embeddings(documents)

        assert result["success_count"] == 2
        assert service.mock_index["with_meta"]["metadata"]["key"] == "value"
        assert service.mock_index["without_meta"]["metadata"] == {}

    def test_search_by_metadata_multiple_filters(self):
        """Test metadata search with multiple filter criteria."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        service.index_embedding(
            "multi_filter_doc",
            "text",
            [0.1] * 1024,
            metadata={"category": "test", "type": "function"},
        )

        # Search with both filters
        results = service.search_by_metadata({"category": "test", "type": "function"})

        assert len(results) == 1
        assert results[0]["id"] == "multi_filter_doc"

    def test_search_by_metadata_partial_match_fails(self):
        """Test that metadata search requires all filters to match."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        service.index_embedding(
            "partial_match",
            "text",
            [0.1] * 1024,
            metadata={"category": "test"},  # Missing 'type' field
        )

        # Search with both filters - should not match
        results = service.search_by_metadata({"category": "test", "type": "function"})

        assert len(results) == 0

    def test_delete_by_file_path_selective_cache_invalidation(self):
        """Test that delete_by_file_path uses selective cache invalidation."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        # Add documents
        service.index_embedding(
            "file_doc", "text", [0.1] * 1024, metadata={"file_path": "src/app.py"}
        )

        # Populate cache with file path in key
        service.query_cache = {
            "query_src/app.py_key": [{"result": 1}],
            "other_query_key": [{"result": 2}],
        }

        # Delete by file path
        service.delete_by_file_path("src/app.py")

        # Only matching cache entry should be removed
        assert "query_src/app.py_key" not in service.query_cache
        assert "other_query_key" in service.query_cache

    def test_max_query_cache_size_constant(self):
        """Test MAX_QUERY_CACHE_SIZE constant value."""
        assert OpenSearchVectorService.MAX_QUERY_CACHE_SIZE == 1000

    def test_search_similar_caching_with_different_min_scores(self):
        """Test that different min_scores create different cache entries."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        vector = [0.5] * 1024

        # First search with min_score 0.5
        service.search_similar(vector, k=5, min_score=0.5)
        cache_size_after_first = len(service.query_cache)

        # Second search with min_score 0.7 (should create new cache entry)
        service.search_similar(vector, k=5, min_score=0.7)
        cache_size_after_second = len(service.query_cache)

        assert cache_size_after_second == cache_size_after_first + 1


class TestOpenSearchClientInitialization:
    """Tests for OpenSearch client initialization paths."""

    def test_init_with_default_endpoint(self):
        """Test initialization with default endpoint."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK)

        assert service.endpoint == "opensearch.aura.local"

    def test_init_with_none_endpoint_uses_default(self):
        """Test that None endpoint uses default value."""
        service = OpenSearchVectorService(mode=OpenSearchMode.MOCK, endpoint=None)

        assert service.endpoint == "opensearch.aura.local"

    def test_init_opensearch_client_region_fallback(self):
        """Test AWS client initialization with None region falls back to us-east-1."""
        from unittest.mock import MagicMock, patch

        mock_opensearch = MagicMock()
        mock_session = MagicMock()
        mock_session.get_credentials.return_value = MagicMock()
        mock_session.region_name = None  # Force fallback to us-east-1

        mock_auth = MagicMock()

        with patch("src.services.opensearch_vector_service.OPENSEARCH_AVAILABLE", True):
            with patch(
                "src.services.opensearch_vector_service.boto3.Session",
                return_value=mock_session,
            ):
                with patch(
                    "src.services.opensearch_vector_service.OpenSearch", mock_opensearch
                ):
                    with patch(
                        "src.services.opensearch_vector_service.AWSV4SignerAuth",
                        mock_auth,
                    ):
                        mock_client = MagicMock()
                        mock_client.info.return_value = {"version": {"number": "2.9"}}
                        mock_client.indices.exists.return_value = True
                        mock_opensearch.return_value = mock_client

                        service = OpenSearchVectorService(
                            mode=OpenSearchMode.AWS,
                            endpoint="test.opensearch.local",
                            use_iam_auth=True,
                        )

                        assert service.mode == OpenSearchMode.AWS
                        # Verify AWSV4SignerAuth was called with us-east-1 fallback
                        mock_auth.assert_called()


class TestCreateVectorServiceExtended:
    """Extended tests for create_vector_service factory function."""

    def test_create_vector_service_with_aws_mode_env_var(self):
        """Test create_vector_service detects AWS mode from environment."""
        from unittest.mock import patch

        from src.services.opensearch_vector_service import create_vector_service

        # Even with OPENSEARCH_ENDPOINT set, should fall back to MOCK
        # because OPENSEARCH_AVAILABLE is False
        os.environ["OPENSEARCH_ENDPOINT"] = "test.opensearch.local"

        try:
            with patch(
                "src.services.opensearch_vector_service.OPENSEARCH_AVAILABLE", False
            ):
                service = create_vector_service()
                assert service.mode == OpenSearchMode.MOCK
        finally:
            del os.environ["OPENSEARCH_ENDPOINT"]

    def test_create_vector_service_uses_default_port(self):
        """Test create_vector_service uses default port 443."""
        from src.services.opensearch_vector_service import create_vector_service

        # Clear any port env var
        if "OPENSEARCH_PORT" in os.environ:
            del os.environ["OPENSEARCH_PORT"]

        service = create_vector_service()

        assert service.port == 443  # AWS OpenSearch default

    def test_create_vector_service_uses_default_vector_dimension(self):
        """Test create_vector_service uses default vector dimension 1024."""
        from src.services.opensearch_vector_service import create_vector_service

        # Clear any dimension env var
        if "VECTOR_DIMENSION" in os.environ:
            del os.environ["VECTOR_DIMENSION"]

        service = create_vector_service()

        assert service.vector_dimension == 1024  # Titan default
