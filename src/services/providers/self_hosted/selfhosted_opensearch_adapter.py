"""
Project Aura - Self-Hosted OpenSearch Adapter

Adapter for self-managed OpenSearch implementing VectorDatabaseService interface.
Uses the same OpenSearch as AWS but with different endpoint configuration.

See ADR-049: Self-Hosted Deployment Strategy

Environment Variables:
    OPENSEARCH_ENDPOINT: OpenSearch endpoint (default: http://localhost:9200)
    OPENSEARCH_USERNAME: Username (optional)
    OPENSEARCH_PASSWORD: Password (optional)
    OPENSEARCH_USE_SSL: Use SSL/TLS (default: false for local)
    OPENSEARCH_VERIFY_CERTS: Verify SSL certificates (default: true)
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

from src.abstractions.vector_database import (
    IndexConfig,
    SearchResult,
    VectorDatabaseService,
    VectorDocument,
)

logger = logging.getLogger(__name__)

# Lazy import opensearchpy
_opensearch = None


def _get_opensearch():
    """Lazy import opensearchpy."""
    global _opensearch
    if _opensearch is None:
        try:
            from opensearchpy import OpenSearch, RequestsHttpConnection

            _opensearch = {
                "OpenSearch": OpenSearch,
                "RequestsHttpConnection": RequestsHttpConnection,
            }
        except ImportError:
            raise ImportError(
                "opensearch-py package not installed. Install with: pip install opensearch-py"
            )
    return _opensearch


class SelfHostedOpenSearchAdapter(VectorDatabaseService):
    """
    Self-hosted OpenSearch adapter implementing VectorDatabaseService interface.

    Provides vector search capabilities for self-hosted deployments using
    self-managed or Docker-based OpenSearch instances.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        username: str | None = None,
        password: str | None = None,
        use_ssl: bool | None = None,
        verify_certs: bool | None = None,
    ):
        """
        Initialize self-hosted OpenSearch adapter.

        Args:
            endpoint: OpenSearch endpoint URL
            username: Username for authentication
            password: Password for authentication
            use_ssl: Use SSL/TLS connection
            verify_certs: Verify SSL certificates
        """
        self.endpoint = endpoint or os.environ.get(
            "OPENSEARCH_ENDPOINT", "http://localhost:9200"
        )
        self.username = username or os.environ.get("OPENSEARCH_USERNAME", "")
        self.password = password or os.environ.get("OPENSEARCH_PASSWORD", "")

        if use_ssl is None:
            use_ssl_str = os.environ.get("OPENSEARCH_USE_SSL", "false")
            use_ssl = use_ssl_str.lower() in ("true", "1", "yes")
        self.use_ssl = use_ssl

        if verify_certs is None:
            verify_str = os.environ.get("OPENSEARCH_VERIFY_CERTS", "true")
            verify_certs = verify_str.lower() in ("true", "1", "yes")
        self.verify_certs = verify_certs

        self._client = None
        self._connected = False

    def _get_client(self):
        """Get or create OpenSearch client."""
        if self._client is None:
            os_mod = _get_opensearch()

            # Parse endpoint URL
            from urllib.parse import urlparse

            parsed = urlparse(self.endpoint)
            host = parsed.hostname or "localhost"
            port = parsed.port or 9200

            auth = None
            if self.username and self.password:
                auth = (self.username, self.password)

            self._client = os_mod["OpenSearch"](
                hosts=[{"host": host, "port": port}],
                http_auth=auth,
                use_ssl=self.use_ssl,
                verify_certs=self.verify_certs,
                connection_class=os_mod["RequestsHttpConnection"],
            )
        return self._client

    async def connect(self) -> bool:
        """Establish connection to OpenSearch."""
        try:
            client = self._get_client()
            info = client.info()
            self._connected = True
            logger.info(
                f"OpenSearch adapter connected to {self.endpoint} "
                f"(version: {info.get('version', {}).get('number', 'unknown')})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to OpenSearch: {e}")
            return False

    async def disconnect(self) -> None:
        """Close OpenSearch connection."""
        if self._client:
            self._client.close()
            self._client = None
        self._connected = False
        logger.info("OpenSearch adapter disconnected")

    async def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    async def create_index(self, config: IndexConfig) -> bool:
        """Create a vector index."""
        client = self._get_client()

        # Build index settings for KNN
        index_body = {
            "settings": {
                "index": {
                    "knn": True,
                    "number_of_shards": config.shards,
                    "number_of_replicas": config.replicas,
                },
            },
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "content": {"type": "text"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": config.dimension,
                        "method": {
                            "name": "hnsw",
                            "space_type": self._map_similarity(
                                config.similarity_metric
                            ),
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": config.ef_construction,
                                "m": config.m,
                            },
                        },
                    },
                    "repository": {"type": "keyword"},
                    "file_path": {"type": "keyword"},
                    "entity_type": {"type": "keyword"},
                    "metadata": {"type": "object", "enabled": True},
                    "created_at": {"type": "date"},
                }
            },
        }

        try:
            if not client.indices.exists(index=config.name):
                client.indices.create(index=config.name, body=index_body)
                logger.info(f"Created index: {config.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create index {config.name}: {e}")
            return False

    def _map_similarity(self, metric: str) -> str:
        """Map similarity metric to OpenSearch space type."""
        mapping = {
            "cosine": "cosinesimil",
            "euclidean": "l2",
            "dot_product": "innerproduct",
        }
        return mapping.get(metric, "cosinesimil")

    async def delete_index(self, index_name: str) -> bool:
        """Delete an index."""
        try:
            client = self._get_client()
            if client.indices.exists(index=index_name):
                client.indices.delete(index=index_name)
                logger.info(f"Deleted index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete index {index_name}: {e}")
            return False

    async def index_exists(self, index_name: str) -> bool:
        """Check if an index exists."""
        client = self._get_client()
        return client.indices.exists(index=index_name)

    async def index_document(self, index_name: str, document: VectorDocument) -> str:
        """Index a single document."""
        client = self._get_client()

        doc_body = {
            "id": document.id,
            "content": document.content,
            "embedding": document.embedding,
            "repository": document.repository,
            "file_path": document.file_path,
            "entity_type": document.entity_type,
            "metadata": document.metadata,
            "created_at": (
                document.created_at.isoformat()
                if document.created_at
                else datetime.now(timezone.utc).isoformat()
            ),
        }

        client.index(index=index_name, id=document.id, body=doc_body, refresh=True)
        return document.id

    async def bulk_index(
        self, index_name: str, documents: list[VectorDocument]
    ) -> dict[str, Any]:
        """Bulk index documents."""
        client = self._get_client()

        # Build bulk request body
        bulk_body = []
        for doc in documents:
            bulk_body.append({"index": {"_index": index_name, "_id": doc.id}})
            bulk_body.append(
                {
                    "id": doc.id,
                    "content": doc.content,
                    "embedding": doc.embedding,
                    "repository": doc.repository,
                    "file_path": doc.file_path,
                    "entity_type": doc.entity_type,
                    "metadata": doc.metadata,
                    "created_at": (
                        doc.created_at.isoformat()
                        if doc.created_at
                        else datetime.now(timezone.utc).isoformat()
                    ),
                }
            )

        response = client.bulk(body=bulk_body, refresh=True)

        return {
            "indexed": len(documents) - len(response.get("errors", [])),
            "errors": response.get("errors", []),
        }

    async def get_document(
        self, index_name: str, document_id: str
    ) -> VectorDocument | None:
        """Get a document by ID."""
        try:
            client = self._get_client()
            response = client.get(index=index_name, id=document_id)

            if response.get("found"):
                source = response["_source"]
                return VectorDocument(
                    id=source["id"],
                    content=source["content"],
                    embedding=source["embedding"],
                    repository=source["repository"],
                    file_path=source["file_path"],
                    entity_type=source["entity_type"],
                    metadata=source.get("metadata", {}),
                    created_at=(
                        datetime.fromisoformat(source["created_at"])
                        if source.get("created_at")
                        else None
                    ),
                )
            return None
        except Exception:
            return None

    async def delete_document(self, index_name: str, document_id: str) -> bool:
        """Delete a document."""
        try:
            client = self._get_client()
            client.delete(index=index_name, id=document_id, refresh=True)
            return True
        except Exception:
            return False

    async def search_similar(
        self,
        index_name: str,
        query_embedding: list[float],
        k: int = 10,
        filters: dict[str, Any] | None = None,
        min_score: float | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents by embedding."""
        client = self._get_client()

        # Build KNN query
        query = {
            "size": k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_embedding,
                        "k": k,
                    }
                }
            },
        }

        # Add filters if provided
        if filters:
            filter_clauses = []
            for field, value in filters.items():
                filter_clauses.append({"term": {field: value}})

            query["query"] = {
                "bool": {
                    "must": [query["query"]],
                    "filter": filter_clauses,
                }
            }

        response = client.search(index=index_name, body=query)

        results = []
        for hit in response.get("hits", {}).get("hits", []):
            score = hit.get("_score", 0.0)
            if min_score and score < min_score:
                continue

            source = hit["_source"]
            doc = VectorDocument(
                id=source["id"],
                content=source["content"],
                embedding=source["embedding"],
                repository=source["repository"],
                file_path=source["file_path"],
                entity_type=source["entity_type"],
                metadata=source.get("metadata", {}),
                created_at=(
                    datetime.fromisoformat(source["created_at"])
                    if source.get("created_at")
                    else None
                ),
            )
            results.append(SearchResult(document=doc, score=score))

        return results

    async def hybrid_search(
        self,
        index_name: str,
        query_text: str,
        query_embedding: list[float],
        k: int = 10,
        text_weight: float = 0.3,
        vector_weight: float = 0.7,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform hybrid text + vector search."""
        client = self._get_client()

        # Build hybrid query with script score
        query = {
            "size": k,
            "query": {
                "script_score": {
                    "query": {
                        "bool": {
                            "should": [
                                {
                                    "match": {
                                        "content": {
                                            "query": query_text,
                                            "boost": text_weight,
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    "script": {
                        "source": f"cosineSimilarity(params.query_vector, 'embedding') * {vector_weight} + _score * {text_weight}",
                        "params": {"query_vector": query_embedding},
                    },
                }
            },
        }

        # Add filters
        if filters:
            filter_clauses = [{"term": {k: v}} for k, v in filters.items()]
            query["query"]["script_score"]["query"]["bool"]["filter"] = filter_clauses

        response = client.search(index=index_name, body=query)

        results = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit["_source"]
            doc = VectorDocument(
                id=source["id"],
                content=source["content"],
                embedding=source["embedding"],
                repository=source["repository"],
                file_path=source["file_path"],
                entity_type=source["entity_type"],
                metadata=source.get("metadata", {}),
                created_at=(
                    datetime.fromisoformat(source["created_at"])
                    if source.get("created_at")
                    else None
                ),
            )
            results.append(SearchResult(document=doc, score=hit.get("_score", 0.0)))

        return results

    async def delete_by_repository(self, index_name: str, repository: str) -> int:
        """Delete all documents for a repository."""
        client = self._get_client()

        query = {"query": {"term": {"repository": repository}}}
        response = client.delete_by_query(index=index_name, body=query, refresh=True)

        return response.get("deleted", 0)

    async def delete_by_file_path(
        self, index_name: str, file_path: str, repository: str
    ) -> int:
        """Delete all documents for a file."""
        client = self._get_client()

        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"file_path": file_path}},
                        {"term": {"repository": repository}},
                    ]
                }
            }
        }
        response = client.delete_by_query(index=index_name, body=query, refresh=True)

        return response.get("deleted", 0)

    async def get_health(self) -> dict[str, Any]:
        """Get OpenSearch health status."""
        try:
            client = self._get_client()
            health = client.cluster.health()
            info = client.info()

            return {
                "status": health.get("status", "unknown"),
                "cluster_name": health.get("cluster_name", ""),
                "number_of_nodes": health.get("number_of_nodes", 0),
                "active_shards": health.get("active_shards", 0),
                "version": info.get("version", {}).get("number", "unknown"),
                "endpoint": self.endpoint,
                "connected": self._connected,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "endpoint": self.endpoint,
            }

    async def get_index_stats(self, index_name: str) -> dict[str, Any]:
        """Get statistics for an index."""
        try:
            client = self._get_client()
            stats = client.indices.stats(index=index_name)
            index_stats = stats.get("indices", {}).get(index_name, {})

            primaries = index_stats.get("primaries", {})
            return {
                "index": index_name,
                "document_count": primaries.get("docs", {}).get("count", 0),
                "size_bytes": primaries.get("store", {}).get("size_in_bytes", 0),
                "size_mb": round(
                    primaries.get("store", {}).get("size_in_bytes", 0) / (1024 * 1024),
                    2,
                ),
            }
        except Exception as e:
            return {
                "index": index_name,
                "error": str(e),
            }
