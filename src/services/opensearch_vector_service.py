"""
AWS OpenSearch Vector Store Service
Production-ready k-NN search for semantic code retrieval
with optimized indexing, caching, and cost controls.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, cast

# TTL cache for bounded memory with expiration
try:
    from cachetools import TTLCache

    CACHETOOLS_AVAILABLE = True
except ImportError:
    CACHETOOLS_AVAILABLE = False

logger = logging.getLogger(__name__)

# OpenSearch imports (will be installed when deploying to AWS)
try:
    import boto3
    from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

    OPENSEARCH_AVAILABLE = True
except ImportError:
    OPENSEARCH_AVAILABLE = False
    logger.warning("OpenSearch Python client not available - using mock mode")


class OpenSearchMode(Enum):
    """Operating modes for OpenSearch service."""

    MOCK = "mock"  # Mock responses for testing
    AWS = "aws"  # Real OpenSearch connection


class OpenSearchError(Exception):
    """General OpenSearch operation error."""


class OpenSearchVectorService:
    """
    Production-ready OpenSearch vector store for semantic search.

    Features:
    - k-NN vector search with HNSW algorithm
    - Automatic index management (creation, mapping, optimization)
    - Response caching with TTL for frequently-accessed vectors
    - Cost optimization (read replicas, query result caching)
    - Comprehensive error handling
    - IAM authentication for security

    Usage:
        >>> service = OpenSearchVectorService(mode=OpenSearchMode.AWS)
        >>> service.index_embedding(
        ...     doc_id='func_123',
        ...     text='def validate_input(data):...',
        ...     vector=[0.1, 0.2, ..., 0.9],  # 1024-dim vector
        ...     metadata={'file': 'src/validators.py', 'line': 42}
        ... )
        >>> results = service.search_similar(query_vector, k=5)

    Cache Configuration:
        MAX_QUERY_CACHE_SIZE: Maximum cached query results (default 1000)
        QUERY_CACHE_TTL_SECONDS: Cache TTL (default 1800 = 30 minutes)
    """

    # Cache size limits (prevents unbounded memory growth)
    MAX_QUERY_CACHE_SIZE = 1000
    # Cache TTL: 30 minutes for queries (relatively short for freshness)
    QUERY_CACHE_TTL_SECONDS = 1800

    def __init__(
        self,
        mode: OpenSearchMode = OpenSearchMode.MOCK,
        endpoint: str | None = None,
        port: int = 9200,
        index_name: str = "aura-code-embeddings",
        vector_dimension: int = 1024,
        use_iam_auth: bool = True,
        cache_ttl_seconds: int | None = None,
    ):
        """
        Initialize OpenSearch Vector Service.

        Args:
            mode: Operating mode (MOCK or AWS)
            endpoint: OpenSearch cluster endpoint (e.g., 'opensearch.aura.local')
            port: OpenSearch port (default 9200)
            index_name: Index name for code embeddings
            vector_dimension: Embedding vector dimension (1024 for Titan, 384 for MiniLM)
            use_iam_auth: Use IAM authentication (recommended)
            cache_ttl_seconds: Cache TTL in seconds (default 1800 = 30 minutes)
        """
        self.mode = mode
        self.endpoint = endpoint or "opensearch.aura.local"
        self.port = port
        self.index_name = index_name
        self.vector_dimension = vector_dimension
        self.use_iam_auth = use_iam_auth

        # In-memory store for mock mode
        self.mock_index: dict[str, dict[str, Any]] = {}

        # Configure cache TTL
        ttl = cache_ttl_seconds or self.QUERY_CACHE_TTL_SECONDS

        # Response cache with TTL (uses cachetools.TTLCache if available)
        if CACHETOOLS_AVAILABLE:
            self.query_cache: (
                TTLCache[str, list[dict[str, Any]]] | dict[str, list[dict[str, Any]]]
            ) = TTLCache(
                maxsize=self.MAX_QUERY_CACHE_SIZE,
                ttl=ttl,
            )
            logger.info(
                f"Query cache initialized with TTLCache: "
                f"maxsize={self.MAX_QUERY_CACHE_SIZE}, ttl={ttl}s"
            )
        else:
            # Fallback to simple dict (no TTL)
            self.query_cache = {}
            logger.warning(
                "cachetools not available - query cache will not have TTL. "
                "Install with: pip install cachetools"
            )

        # Initialize connection
        if self.mode == OpenSearchMode.AWS and OPENSEARCH_AVAILABLE:
            self._init_opensearch_client()
        else:
            if self.mode == OpenSearchMode.AWS:
                logger.warning(
                    "AWS mode requested but OpenSearch not available. Using MOCK mode."
                )
                self.mode = OpenSearchMode.MOCK
            self._init_mock_mode()

        logger.info(f"OpenSearchVectorService initialized in {self.mode.value} mode")

    def _init_opensearch_client(self) -> None:
        """Initialize OpenSearch client with IAM authentication."""
        try:
            host = f"{self.endpoint}:{self.port}"

            if self.use_iam_auth:
                # Use IAM auth (recommended for AWS)
                credentials = boto3.Session().get_credentials()
                region = boto3.Session().region_name or "us-east-1"

                auth = AWSV4SignerAuth(credentials, region, "es")

                self.client = OpenSearch(
                    hosts=[{"host": self.endpoint, "port": self.port}],
                    http_auth=auth,
                    use_ssl=True,
                    verify_certs=True,
                    connection_class=RequestsHttpConnection,
                    timeout=30,
                )
            else:
                # No auth (dev mode only). Refuse to connect over plaintext in
                # production: a misconfigured prod container that loses its IAM
                # credentials must not silently fall through to an unauthenticated,
                # unencrypted OpenSearch session.
                environment = (os.environ.get("ENVIRONMENT") or "dev").lower()
                if environment in ("prod", "production"):
                    raise RuntimeError(
                        "OpenSearch IAM credentials unavailable in production. "
                        "Refusing to fall back to unauthenticated plaintext."
                    )
                logger.warning(
                    "OpenSearch initialized without IAM auth (plaintext, dev only)"
                )
                self.client = OpenSearch(hosts=[host], use_ssl=False, timeout=30)

            # Test connection
            info = self.client.info()
            logger.info(
                f"OpenSearch connection established: {info['version']['number']}"
            )

            # Ensure index exists
            self._create_index_if_not_exists()

        except Exception as e:
            logger.error(f"Failed to connect to OpenSearch: {e}")
            logger.warning("Falling back to MOCK mode")
            self.mode = OpenSearchMode.MOCK
            self._init_mock_mode()

    def _init_mock_mode(self) -> None:
        """Initialize mock mode with sample data."""
        logger.info("Mock mode initialized (no OpenSearch calls will be made)")

        # Sample embedded documents for testing
        self.mock_index = {
            "security_policy_sha256": {
                "text": "All new code must use SHA256 or SHA3-512. SHA1 is prohibited.",
                "vector": [0.1] * self.vector_dimension,  # Mock vector
                "metadata": {
                    "source": "security_policies.md",
                    "category": "cryptography",
                    "compliance": ["SOX", "CMMC"],
                },
            },
            "data_processor_doc": {
                "text": "DataProcessor class handles data pre-processing and checksum generation.",
                "vector": [0.2] * self.vector_dimension,  # Mock vector
                "metadata": {
                    "source": "src/data_processor.py",
                    "type": "class",
                    "line_number": 42,
                },
            },
        }

    def _create_index_if_not_exists(self) -> None:
        """Create OpenSearch index with k-NN configuration if it doesn't exist."""
        if self.mode == OpenSearchMode.MOCK:
            return

        try:
            if self.client.indices.exists(index=self.index_name):
                logger.info(f"Index '{self.index_name}' already exists")
                return

            # Index mapping with k-NN configuration
            index_body = {
                "settings": {
                    "index": {
                        "knn": True,  # Enable k-NN plugin
                        "knn.algo_param.ef_search": 512,  # HNSW search quality
                        "number_of_shards": 2,
                        "number_of_replicas": 1,
                    }
                },
                "mappings": {
                    "properties": {
                        "text": {"type": "text", "analyzer": "standard"},
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": self.vector_dimension,
                            "method": {
                                "name": "hnsw",  # Hierarchical Navigable Small World
                                "space_type": "cosinesimil",  # Cosine similarity
                                "engine": "nmslib",
                                "parameters": {
                                    "ef_construction": 512,  # Build quality
                                    "m": 16,  # Number of connections
                                },
                            },
                        },
                        "metadata": {"type": "object", "enabled": True},
                        "timestamp": {"type": "date"},
                    }
                },
            }

            self.client.indices.create(index=self.index_name, body=index_body)
            logger.info(f"Created index '{self.index_name}' with k-NN configuration")

        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            raise OpenSearchError(f"Failed to create index: {e}") from e

    def index_embedding(
        self,
        doc_id: str,
        text: str,
        vector: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Index a text embedding in OpenSearch.

        Args:
            doc_id: Unique document ID
            text: Original text content
            vector: Embedding vector (must match vector_dimension)
            metadata: Additional metadata (file path, line number, etc.)

        Returns:
            True if successful
        """
        if len(vector) != self.vector_dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.vector_dimension}, got {len(vector)}"
            )

        if self.mode == OpenSearchMode.MOCK:
            self.mock_index[doc_id] = {
                "text": text,
                "vector": vector,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            logger.info(f"[MOCK] Indexed document: {doc_id}")
            return True

        # Real OpenSearch indexing
        try:
            document = {
                "text": text,
                "embedding": vector,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            response = self.client.index(
                index=self.index_name,
                id=doc_id,
                body=document,
                refresh=False,  # Async refresh for performance
            )

            logger.info(f"Indexed document: {doc_id} (result: {response['result']})")
            return response["result"] in ["created", "updated"]

        except Exception as e:
            logger.error(f"Failed to index document: {e}")
            raise OpenSearchError(f"Failed to index document: {e}") from e

    def search_similar(
        self,
        query_vector: list[float],
        k: int = 5,
        min_score: float = 0.7,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar code using k-NN vector search.

        Args:
            query_vector: Query embedding vector
            k: Number of results to return
            min_score: Minimum similarity score (0-1)
            filters: Metadata filters (e.g., {'metadata.source': 'src/validators.py'})

        Returns:
            List of similar documents with scores:
            [
                {
                    'id': str,
                    'text': str,
                    'score': float,
                    'metadata': dict
                },
                ...
            ]
        """
        if len(query_vector) != self.vector_dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.vector_dimension}, got {len(query_vector)}"
            )

        # Check cache first
        cache_key = self._cache_key(query_vector, k, min_score, filters)
        if cache_key in self.query_cache:
            logger.info("Cache hit - returning cached results")
            return self.query_cache[cache_key]

        if self.mode == OpenSearchMode.MOCK:
            # Mock similarity calculation (cosine similarity)
            results = []
            for doc_id, doc in self.mock_index.items():
                # Simple dot product for mock similarity
                score = (
                    sum(
                        a * b for a, b in zip(query_vector, doc["vector"], strict=False)
                    )
                    / self.vector_dimension
                )

                if score >= min_score:
                    results.append(
                        {
                            "id": doc_id,
                            "text": doc["text"],
                            "score": score,
                            "metadata": doc.get("metadata", {}),
                        }
                    )

            # Sort by score desc
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:k]

            logger.info(f"[MOCK] Found {len(results)} similar documents")
            self.query_cache[cache_key] = results
            self._enforce_cache_limit()
            return results

        # Real OpenSearch k-NN search
        try:
            # Build k-NN query
            query_body = {
                "size": k,
                "query": {"knn": {"embedding": {"vector": query_vector, "k": k}}},
                "_source": ["text", "metadata"],
            }

            # Add filters if provided
            if filters:
                query_body["query"] = {
                    "bool": {
                        "must": [query_body["query"]],
                        "filter": [{"term": filters}],
                    }
                }

            # Add minimum score filter
            if min_score > 0:
                query_body["min_score"] = min_score

            response = self.client.search(index=self.index_name, body=query_body)

            # Parse results
            results = []
            for hit in response["hits"]["hits"]:
                results.append(
                    {
                        "id": hit["_id"],
                        "text": hit["_source"]["text"],
                        "score": hit["_score"],
                        "metadata": hit["_source"].get("metadata", {}),
                    }
                )

            logger.info(f"Found {len(results)} similar documents in OpenSearch")

            # Cache results (bounded to MAX_QUERY_CACHE_SIZE)
            self.query_cache[cache_key] = results
            self._enforce_cache_limit()

            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise OpenSearchError(f"Search failed: {e}") from e

    def search_by_metadata(
        self, filters: dict[str, Any], limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Search documents by metadata filters (without vector search).

        Args:
            filters: Metadata filters (e.g., {'metadata.source': 'src/app.py'})
            limit: Maximum results to return

        Returns:
            List of matching documents
        """
        if self.mode == OpenSearchMode.MOCK:
            results = []
            for doc_id, doc in self.mock_index.items():
                # Simple metadata matching
                match = all(
                    doc.get("metadata", {}).get(key) == value
                    for key, value in filters.items()
                )
                if match:
                    results.append(
                        {
                            "id": doc_id,
                            "text": doc["text"],
                            "metadata": doc.get("metadata", {}),
                        }
                    )
            return results[:limit]

        # Real OpenSearch query
        try:
            query_body = {
                "size": limit,
                "query": {"bool": {"filter": [{"term": filters}]}},
                "_source": ["text", "metadata"],
            }

            response = self.client.search(index=self.index_name, body=query_body)

            results = []
            for hit in response["hits"]["hits"]:
                results.append(
                    {
                        "id": hit["_id"],
                        "text": hit["_source"]["text"],
                        "metadata": hit["_source"].get("metadata", {}),
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Metadata search failed: {e}")
            return []

    def _cache_key(
        self,
        query_vector: list[float],
        k: int,
        min_score: float,
        filters: dict[str, Any] | None,
    ) -> str:
        """Generate cache key for query."""
        # Hash vector (first 10 values for brevity) - not used for security
        vector_hash = hashlib.md5(
            str(query_vector[:10]).encode(), usedforsecurity=False
        ).hexdigest()[:8]
        filter_str = json.dumps(filters, sort_keys=True) if filters else ""
        return f"{vector_hash}_{k}_{min_score}_{filter_str}"

    def _invalidate_cache_selective(
        self, repository_id: str | None = None, file_path: str | None = None
    ) -> int:
        """
        Selectively invalidate cache entries related to a repository or file.

        Optimized to only remove affected cache entries instead of clearing all.
        Reduces cache rebuild cost after localized data changes.

        Args:
            repository_id: Invalidate entries for this repository
            file_path: Invalidate entries for this file

        Returns:
            Number of cache entries invalidated
        """
        if not self.query_cache:
            return 0

        keys_to_remove = []
        for key in self.query_cache:
            # Check if cache key contains the repository or file path
            if repository_id and repository_id in key:
                keys_to_remove.append(key)
            elif file_path and file_path in key:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.query_cache[key]

        if keys_to_remove:
            logger.debug(
                f"Invalidated {len(keys_to_remove)} cache entries "
                f"(repo={repository_id}, file={file_path})"
            )

        return len(keys_to_remove)

    def _enforce_cache_limit(self) -> None:
        """Evict oldest cache entries if cache exceeds MAX_QUERY_CACHE_SIZE.

        Note: When using TTLCache, this is handled automatically by the cache.
        This method is kept for fallback dict mode compatibility.
        """
        # TTLCache handles eviction automatically
        if CACHETOOLS_AVAILABLE and isinstance(self.query_cache, TTLCache):
            return

        # Fallback for dict mode
        if len(self.query_cache) > self.MAX_QUERY_CACHE_SIZE:
            # Python 3.7+ dicts maintain insertion order - remove oldest 10%
            evict_count = len(self.query_cache) - self.MAX_QUERY_CACHE_SIZE + 100
            keys_to_evict = list(self.query_cache.keys())[:evict_count]
            for key in keys_to_evict:
                del self.query_cache[key]
            logger.debug(
                f"Evicted {len(keys_to_evict)} cache entries (size limit reached)"
            )

    def delete_by_repository(self, repository_id: str) -> int:
        """
        Delete all documents belonging to a repository.

        Args:
            repository_id: Repository identifier (e.g., 'owner/repo')

        Returns:
            Number of documents deleted
        """
        if self.mode == OpenSearchMode.MOCK:
            to_delete = [
                doc_id
                for doc_id, doc in self.mock_index.items()
                if doc.get("metadata", {}).get("repository") == repository_id
            ]

            for doc_id in to_delete:
                del self.mock_index[doc_id]

            # Selectively invalidate cache entries for this repository
            self._invalidate_cache_selective(repository_id=repository_id)

            logger.info(
                f"[MOCK] Deleted {len(to_delete)} documents for repository: {repository_id}"
            )
            return len(to_delete)

        # Real OpenSearch operation - delete by query
        try:
            query_body = {"query": {"term": {"metadata.repository": repository_id}}}

            response = self.client.delete_by_query(
                index=self.index_name, body=query_body, refresh=True
            )

            deleted_count = cast(int, response.get("deleted", 0))

            # Selectively invalidate cache entries for this repository
            self._invalidate_cache_selective(repository_id=repository_id)

            logger.info(
                f"Deleted {deleted_count} documents for repository: {repository_id}"
            )
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to delete repository from OpenSearch: {e}")
            raise OpenSearchError(f"Failed to delete repository: {e}") from e

    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a specific document.

        Args:
            doc_id: Document identifier

        Returns:
            True if document was deleted
        """
        if self.mode == OpenSearchMode.MOCK:
            if doc_id in self.mock_index:
                del self.mock_index[doc_id]
                self.query_cache.clear()
                logger.info(f"[MOCK] Deleted document: {doc_id}")
                return True
            return False

        # Real OpenSearch operation
        try:
            self.client.delete(index=self.index_name, id=doc_id, refresh=True)
            self.query_cache.clear()
            logger.info(f"Deleted document from OpenSearch: {doc_id}")
            return True

        except Exception as e:
            # Check if document didn't exist
            if "not_found" in str(e).lower():
                logger.warning(f"Document not found: {doc_id}")
                return False
            logger.error(f"Failed to delete document from OpenSearch: {e}")
            raise OpenSearchError(f"Failed to delete document: {e}") from e

    def delete_by_file_path(self, file_path: str) -> int:
        """
        Delete all documents for a specific file.

        Args:
            file_path: Source file path

        Returns:
            Number of documents deleted
        """
        if self.mode == OpenSearchMode.MOCK:
            to_delete = [
                doc_id
                for doc_id, doc in self.mock_index.items()
                if doc.get("metadata", {}).get("file_path") == file_path
            ]

            for doc_id in to_delete:
                del self.mock_index[doc_id]

            # Selectively invalidate cache entries for this file
            self._invalidate_cache_selective(file_path=file_path)

            logger.info(
                f"[MOCK] Deleted {len(to_delete)} documents for file: {file_path}"
            )
            return len(to_delete)

        # Real OpenSearch operation
        try:
            query_body = {"query": {"term": {"metadata.file_path": file_path}}}

            response = self.client.delete_by_query(
                index=self.index_name, body=query_body, refresh=True
            )

            deleted_count = cast(int, response.get("deleted", 0))

            # Selectively invalidate cache entries for this file
            self._invalidate_cache_selective(file_path=file_path)

            logger.info(f"Deleted {deleted_count} documents for file: {file_path}")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to delete file documents from OpenSearch: {e}")
            raise OpenSearchError(f"Failed to delete file documents: {e}") from e

    def get_cluster_health(self) -> dict[str, Any]:
        """
        Get OpenSearch cluster health status.

        Returns:
            Dict with cluster health info:
            {
                'status': 'green' | 'yellow' | 'red',
                'number_of_nodes': int,
                'active_shards': int,
                ...
            }
        """
        if self.mode == OpenSearchMode.MOCK:
            return {
                "status": "green",
                "number_of_nodes": 1,
                "active_primary_shards": 2,
                "active_shards": 4,
            }

        try:
            health = cast(dict[str, Any], self.client.cluster.health())
            return health
        except Exception as e:
            logger.error(f"Failed to get cluster health: {e}")
            raise OpenSearchError(f"Failed to get cluster health: {e}") from e

    def bulk_index_embeddings(
        self,
        documents: list[dict[str, Any]],
        refresh: bool = True,
    ) -> dict[str, Any]:
        """
        Bulk index multiple embeddings.

        Args:
            documents: List of documents, each with:
                - id: str
                - text: str
                - vector: list[float]
                - metadata: dict (optional)
            refresh: Whether to refresh index after bulk operation

        Returns:
            Dict with bulk operation results:
            {
                'success_count': int,
                'error_count': int,
                'errors': list[str]
            }
        """
        if self.mode == OpenSearchMode.MOCK:
            for doc in documents:
                self.mock_index[doc["id"]] = {
                    "text": doc["text"],
                    "vector": doc["vector"],
                    "metadata": doc.get("metadata", {}),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            logger.info(f"[MOCK] Bulk indexed {len(documents)} documents")
            return {"success_count": len(documents), "error_count": 0, "errors": []}

        try:
            # Build bulk request body
            bulk_body: list[dict[str, Any]] = []
            for doc in documents:
                # Index action
                bulk_body.append(
                    {"index": {"_index": self.index_name, "_id": doc["id"]}}
                )
                # Document body
                bulk_body.append(
                    {
                        "text": doc["text"],
                        "embedding": doc["vector"],
                        "metadata": doc.get("metadata", {}),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

            response = self.client.bulk(body=bulk_body, refresh=refresh)

            # Count successes and errors
            success_count = 0
            error_count = 0
            errors = []

            for item in response.get("items", []):
                if "error" in item.get("index", {}):
                    error_count += 1
                    errors.append(str(item["index"]["error"]))
                else:
                    success_count += 1

            logger.info(f"Bulk indexed {success_count} documents, {error_count} errors")
            return {
                "success_count": success_count,
                "error_count": error_count,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Failed to bulk index documents: {e}")
            raise OpenSearchError(f"Failed to bulk index documents: {e}") from e

    def close(self) -> None:
        """Close OpenSearch connection."""
        if self.mode == OpenSearchMode.AWS and hasattr(self, "client"):
            try:
                self.client.close()
                logger.info("OpenSearch connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")


# Convenience function
def create_vector_service(_environment: str | None = None) -> OpenSearchVectorService:
    """
    Create and return an OpenSearchVectorService instance.

    Args:
        _environment: Environment name (reserved for future environment-specific config)

    Returns:
        Configured OpenSearchVectorService instance
    """
    # Auto-detect mode
    mode = (
        OpenSearchMode.AWS
        if OPENSEARCH_AVAILABLE and os.getenv("OPENSEARCH_ENDPOINT")
        else OpenSearchMode.MOCK
    )

    endpoint = os.getenv("OPENSEARCH_ENDPOINT", "opensearch.aura.local")
    port = int(
        os.getenv("OPENSEARCH_PORT", "443")
    )  # AWS OpenSearch uses 443 by default
    vector_dim = int(os.getenv("VECTOR_DIMENSION", "1024"))  # Default to Titan

    return OpenSearchVectorService(
        mode=mode, endpoint=endpoint, port=port, vector_dimension=vector_dim
    )


if __name__ == "__main__":
    # Demo/test usage
    logging.basicConfig(level=logging.INFO)

    print("Project Aura - OpenSearch Vector Service Demo")
    print("=" * 60)

    # Create service (will use mock mode if OpenSearch not configured)
    service = create_vector_service()

    print(f"\nMode: {service.mode.value}")
    print(f"Endpoint: {service.endpoint}:{service.port}")
    print(f"Index: {service.index_name}")
    print(f"Vector Dimension: {service.vector_dimension}")

    # Test operations
    print("\n" + "-" * 60)
    print("Testing vector operations...")

    try:
        # Index embeddings
        service.index_embedding(
            doc_id="func_validate_123",
            text="def validate_input(data): return sanitize(data)",
            vector=[0.1] * service.vector_dimension,  # Mock vector
            metadata={"file": "src/validators.py", "line": 42, "type": "function"},
        )

        service.index_embedding(
            doc_id="func_process_456",
            text="def process_data(input): return transform(input)",
            vector=[0.15] * service.vector_dimension,  # Mock vector
            metadata={"file": "src/processors.py", "line": 78, "type": "function"},
        )

        print("✓ Indexed 2 code embeddings")

        # Search similar code
        query_vector = [0.12] * service.vector_dimension
        results = service.search_similar(query_vector, k=2, min_score=0.5)

        print(f"\n✓ Found {len(results)} similar code snippets:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result['text'][:50]}... (score: {result['score']:.3f})")
            print(f"     File: {result['metadata'].get('file', 'N/A')}")

    except Exception as e:
        print(f"\n✗ Error: {e}")

    # Cleanup
    service.close()

    print("\n" + "=" * 60)
    print("Demo complete!")
