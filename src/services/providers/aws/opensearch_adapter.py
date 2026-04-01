"""
Project Aura - OpenSearch Vector Adapter

Adapter that wraps OpenSearchVectorService to implement VectorDatabaseService interface.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

import logging
from typing import Any, cast

from src.abstractions.vector_database import (
    IndexConfig,
    SearchResult,
    VectorDatabaseService,
    VectorDocument,
)
from src.services.opensearch_vector_service import (
    OpenSearchMode,
    OpenSearchVectorService,
)

logger = logging.getLogger(__name__)


class OpenSearchVectorAdapter(VectorDatabaseService):
    """
    Adapter for AWS OpenSearch that implements VectorDatabaseService interface.

    Wraps the existing OpenSearchVectorService to provide a cloud-agnostic API.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        region: str = "us-east-1",
    ):
        self.endpoint = endpoint
        self.region = region
        self._service: OpenSearchVectorService | None = None
        self._connected = False

    def _get_service(self) -> OpenSearchVectorService:
        """Get or create the underlying OpenSearch service."""
        if self._service is None:
            mode = OpenSearchMode.AWS if self.endpoint else OpenSearchMode.MOCK
            self._service = OpenSearchVectorService(
                mode=mode,
                endpoint=self.endpoint,
            )
        return self._service

    async def connect(self) -> bool:
        """Connect to OpenSearch."""
        try:
            service = self._get_service()
            self._connected = True
            logger.info(f"OpenSearch adapter connected (mode: {service.mode.value})")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to OpenSearch: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from OpenSearch."""
        self._connected = False
        self._service = None

    async def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    async def create_index(self, config: IndexConfig) -> bool:
        """Create a vector index."""
        service = self._get_service()
        # OpenSearchVectorService creates index automatically on first use
        # We just verify it exists or create it manually
        service.index_name = config.name
        service.vector_dimension = config.dimension
        service._create_index_if_not_exists()
        return True

    async def delete_index(self, index_name: str) -> bool:
        """Delete an index."""
        service = self._get_service()
        try:
            if service.mode == OpenSearchMode.MOCK:
                # Clear mock index
                service.mock_index.clear()
                return True
            # Real OpenSearch deletion
            response = service.client.indices.delete(index=index_name)
            return bool(response.get("acknowledged", False))
        except Exception as e:
            logger.error(f"Failed to delete index {index_name}: {e}")
            return False

    async def index_exists(self, index_name: str) -> bool:
        """Check if index exists."""
        service = self._get_service()
        try:
            if service.mode == OpenSearchMode.MOCK:
                return bool(service.mock_index)
            # Real OpenSearch check
            return bool(service.client.indices.exists(index=index_name))
        except Exception:
            return False

    async def index_document(self, index_name: str, document: VectorDocument) -> str:
        """Index a document."""
        service = self._get_service()
        # Set the index name for this operation
        service.index_name = index_name

        # Build metadata with all fields
        metadata: dict[str, Any] = {
            "repository": document.repository,
            "file_path": document.file_path,
            "entity_type": document.entity_type,
        }
        if document.metadata:
            metadata.update(document.metadata)

        # index_embedding returns bool, but we need to return the doc_id
        service.index_embedding(
            doc_id=document.id,
            text=document.content,
            vector=document.embedding,
            metadata=metadata,
        )
        return document.id

    async def bulk_index(
        self, index_name: str, documents: list[VectorDocument]
    ) -> dict[str, Any]:
        """Bulk index documents using OpenSearch bulk API.

        Optimized to use a single bulk API call instead of individual index operations.
        This reduces N API calls to 1, significantly improving performance for large batches.
        """
        service = self._get_service()
        # Set the index name for this operation
        service.index_name = index_name

        # Convert VectorDocument list to format expected by bulk_index_embeddings
        bulk_docs: list[dict[str, Any]] = []
        for doc in documents:
            metadata: dict[str, Any] = {
                "repository": doc.repository,
                "file_path": doc.file_path,
                "entity_type": doc.entity_type,
            }
            if doc.metadata:
                metadata.update(doc.metadata)

            bulk_docs.append(
                {
                    "id": doc.id,
                    "text": doc.content,
                    "vector": doc.embedding,
                    "metadata": metadata,
                }
            )

        result = service.bulk_index_embeddings(bulk_docs, refresh=True)

        return {
            "success_count": result.get("success_count", 0),
            "error_count": result.get("error_count", 0),
            "total": len(documents),
        }

    async def get_document(
        self, index_name: str, document_id: str
    ) -> VectorDocument | None:
        """Get a document by ID."""
        service = self._get_service()
        try:
            if service.mode == OpenSearchMode.MOCK:
                doc_data = service.mock_index.get(document_id)
                if not doc_data:
                    return None
                metadata = cast(dict[str, Any], doc_data.get("metadata", {}))
                return VectorDocument(
                    id=document_id,
                    content=str(doc_data.get("text", "")),
                    embedding=cast(list[float], doc_data.get("vector", [])),
                    repository=str(metadata.get("repository", "")),
                    file_path=str(metadata.get("file_path", "")),
                    entity_type=str(metadata.get("entity_type", "file")),
                    metadata=metadata,
                )
            # Real OpenSearch retrieval
            response = service.client.get(index=index_name, id=document_id)
            if not response or not response.get("found"):
                return None

            source = cast(dict[str, Any], response.get("_source", {}))
            metadata = cast(dict[str, Any], source.get("metadata", {}))
            return VectorDocument(
                id=document_id,
                content=str(source.get("text", "")),
                embedding=cast(list[float], source.get("embedding", [])),
                repository=str(metadata.get("repository", "")),
                file_path=str(metadata.get("file_path", "")),
                entity_type=str(metadata.get("entity_type", "file")),
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {e}")
            return None

    async def delete_document(self, index_name: str, document_id: str) -> bool:
        """Delete a document."""
        service = self._get_service()
        # Set the index name for this operation
        service.index_name = index_name
        return service.delete_document(document_id)

    async def search_similar(
        self,
        index_name: str,
        query_embedding: list[float],
        k: int = 10,
        filters: dict[str, Any] | None = None,
        min_score: float | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents."""
        service = self._get_service()
        # Set the index name for this operation
        service.index_name = index_name

        # search_similar signature: (query_vector, k, min_score, filters)
        results = service.search_similar(
            query_vector=query_embedding,
            k=k,
            min_score=min_score if min_score is not None else 0.7,
            filters=filters,
        )

        search_results: list[SearchResult] = []
        for r in results:
            metadata = cast(dict[str, Any], r.get("metadata", {}))
            doc = VectorDocument(
                id=str(r.get("id", "")),
                content=str(r.get("text", "")),
                embedding=cast(list[float], r.get("embedding", [])),
                repository=str(metadata.get("repository", "")),
                file_path=str(metadata.get("file_path", "")),
                entity_type=str(metadata.get("entity_type", "file")),
                metadata=metadata,
            )
            search_results.append(
                SearchResult(
                    document=doc,
                    score=float(r.get("score", 0.0)),
                    highlights=cast(dict[str, list[str]], r.get("highlights", {})),
                )
            )
        return search_results

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
        """Hybrid search combining text and vector similarity.

        Note: OpenSearchVectorService doesn't have a native hybrid_search method,
        so we fall back to pure vector search with the query_embedding.
        """
        service = self._get_service()
        # Set the index name for this operation
        service.index_name = index_name

        # Use vector search as a fallback (OpenSearchVectorService doesn't have hybrid_search)
        results = service.search_similar(
            query_vector=query_embedding,
            k=k,
            min_score=0.7,
            filters=filters,
        )

        search_results: list[SearchResult] = []
        for r in results:
            metadata = cast(dict[str, Any], r.get("metadata", {}))
            doc = VectorDocument(
                id=str(r.get("id", "")),
                content=str(r.get("text", "")),
                embedding=cast(list[float], r.get("embedding", [])),
                repository=str(metadata.get("repository", "")),
                file_path=str(metadata.get("file_path", "")),
                entity_type=str(metadata.get("entity_type", "file")),
                metadata=metadata,
            )
            # Apply weight to score (approximate hybrid behavior)
            score = float(r.get("score", 0.0)) * vector_weight
            search_results.append(
                SearchResult(
                    document=doc,
                    score=score,
                    highlights=cast(dict[str, list[str]], r.get("highlights", {})),
                )
            )
        return search_results

    async def delete_by_repository(self, index_name: str, repository: str) -> int:
        """Delete all documents for a repository."""
        service = self._get_service()
        # Set the index name for this operation
        service.index_name = index_name
        return service.delete_by_repository(repository)

    async def delete_by_file_path(
        self, index_name: str, file_path: str, repository: str
    ) -> int:
        """Delete documents for a file."""
        service = self._get_service()
        # Set the index name for this operation
        service.index_name = index_name
        # delete_by_file_path only takes file_path parameter
        return service.delete_by_file_path(file_path)

    async def get_health(self) -> dict[str, Any]:
        """Get cluster health."""
        service = self._get_service()
        health = service.get_cluster_health()
        return {
            "status": health.get("status", "unknown"),
            "mode": service.mode.value,
            "endpoint": self.endpoint,
            "region": self.region,
        }

    async def get_index_stats(self, index_name: str) -> dict[str, Any]:
        """Get index statistics."""
        service = self._get_service()
        try:
            if service.mode == OpenSearchMode.MOCK:
                return {
                    "doc_count": len(service.mock_index),
                    "index_name": index_name,
                }
            # Real OpenSearch stats
            stats = service.client.indices.stats(index=index_name)
            indices = cast(dict[str, Any], stats.get("indices", {}))
            index_data = cast(dict[str, Any], indices.get(index_name, {}))
            total = cast(dict[str, Any], index_data.get("total", {}))
            docs = cast(dict[str, Any], total.get("docs", {}))
            return {
                "doc_count": int(docs.get("count", 0)),
                "index_name": index_name,
            }
        except Exception as e:
            logger.error(f"Failed to get index stats for {index_name}: {e}")
            return {"doc_count": 0, "index_name": index_name}
