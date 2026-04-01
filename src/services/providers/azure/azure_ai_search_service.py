"""
Project Aura - Azure AI Search Service

Azure AI Search implementation of VectorDatabaseService.
Provides vector similarity search for Azure Government deployments.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

import logging
import os
from typing import Any

from src.abstractions.vector_database import (
    IndexConfig,
    SearchResult,
    VectorDatabaseService,
    VectorDocument,
)

logger = logging.getLogger(__name__)

# Optional Azure dependencies
try:
    from azure.core.credentials import AzureKeyCredential
    from azure.identity import DefaultAzureCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        VectorSearch,
        VectorSearchProfile,
    )

    AZURE_SEARCH_AVAILABLE = True
except ImportError:
    AZURE_SEARCH_AVAILABLE = False
    logger.warning("Azure AI Search SDK not available - using mock mode")


class AzureAISearchService(VectorDatabaseService):
    """
    Azure AI Search implementation for vector similarity search.

    Compatible with Azure Government regions.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        index_name: str = "aura-vectors",
        key: str | None = None,
    ):
        self.endpoint = endpoint or os.environ.get("AZURE_SEARCH_ENDPOINT")
        self.index_name = index_name
        self.key = key or os.environ.get("AZURE_SEARCH_KEY")

        self._index_client: "SearchIndexClient | None" = None
        self._search_client: "SearchClient | None" = None
        self._connected = False

        # Mock storage
        self._mock_documents: dict[str, dict[str, Any]] = {}

    @property
    def is_mock_mode(self) -> bool:
        """Check if running in mock mode."""
        return not AZURE_SEARCH_AVAILABLE or not self.endpoint

    async def connect(self) -> bool:
        """Connect to Azure AI Search."""
        if self.is_mock_mode:
            logger.info("Azure AI Search running in mock mode")
            self._connected = True
            return True

        try:
            if self.key:
                credential = AzureKeyCredential(self.key)
            else:
                credential = DefaultAzureCredential()

            self._index_client = SearchIndexClient(self.endpoint, credential)
            self._search_client = SearchClient(
                self.endpoint, self.index_name, credential
            )
            self._connected = True
            logger.info(f"Connected to Azure AI Search: {self.index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Azure AI Search: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect."""
        self._connected = False
        self._index_client = None
        self._search_client = None

    async def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    async def create_index(self, config: IndexConfig) -> bool:
        """Create a vector search index."""
        if self.is_mock_mode:
            return True

        if self._index_client is None:
            logger.error("Index client not initialized")
            return False

        try:
            fields = [
                SearchField(name="id", type=SearchFieldDataType.String, key=True),
                SearchField(
                    name="content", type=SearchFieldDataType.String, searchable=True
                ),
                SearchField(
                    name="repository", type=SearchFieldDataType.String, filterable=True
                ),
                SearchField(
                    name="file_path", type=SearchFieldDataType.String, filterable=True
                ),
                SearchField(
                    name="entity_type", type=SearchFieldDataType.String, filterable=True
                ),
                SearchField(
                    name="embedding",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=config.dimension,
                    vector_search_profile_name="vector-profile",
                ),
            ]

            vector_search = VectorSearch(
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="hnsw-config",
                        parameters={
                            "m": config.m,
                            "efConstruction": config.ef_construction,
                            "efSearch": 500,
                            "metric": config.similarity_metric,
                        },
                    ),
                ],
                profiles=[
                    VectorSearchProfile(
                        name="vector-profile",
                        algorithm_configuration_name="hnsw-config",
                    ),
                ],
            )

            index = SearchIndex(
                name=config.name,
                fields=fields,
                vector_search=vector_search,
            )

            self._index_client.create_or_update_index(index)
            logger.info(f"Created index: {config.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            return False

    async def delete_index(self, index_name: str) -> bool:
        """Delete an index."""
        if self.is_mock_mode:
            return True

        if self._index_client is None:
            logger.error("Index client not initialized")
            return False

        try:
            self._index_client.delete_index(index_name)
            return True
        except Exception as e:
            logger.error(f"Failed to delete index: {e}")
            return False

    async def index_exists(self, index_name: str) -> bool:
        """Check if index exists."""
        if self.is_mock_mode:
            return True

        if self._index_client is None:
            return False

        try:
            self._index_client.get_index(index_name)
            return True
        except Exception:
            return False

    async def index_document(self, index_name: str, document: VectorDocument) -> str:
        """Index a document."""
        if self.is_mock_mode:
            self._mock_documents[document.id] = document.to_dict()
            return document.id

        if self._search_client is None:
            logger.error("Search client not initialized")
            return ""

        doc = {
            "id": document.id,
            "content": document.content,
            "embedding": document.embedding,
            "repository": document.repository,
            "file_path": document.file_path,
            "entity_type": document.entity_type,
            **document.metadata,
        }
        self._search_client.upload_documents([doc])
        return document.id

    async def bulk_index(
        self, index_name: str, documents: list[VectorDocument]
    ) -> dict[str, Any]:
        """Bulk index documents."""
        if self.is_mock_mode:
            for doc in documents:
                self._mock_documents[doc.id] = doc.to_dict()
            return {"success_count": len(documents), "error_count": 0}

        if self._search_client is None:
            logger.error("Search client not initialized")
            return {
                "success_count": 0,
                "error_count": len(documents),
                "total": len(documents),
            }

        docs = []
        for doc in documents:
            docs.append(
                {
                    "id": doc.id,
                    "content": doc.content,
                    "embedding": doc.embedding,
                    "repository": doc.repository,
                    "file_path": doc.file_path,
                    "entity_type": doc.entity_type,
                    **doc.metadata,
                }
            )

        results = self._search_client.upload_documents(docs)
        succeeded = sum(1 for r in results if r.succeeded)
        return {
            "success_count": succeeded,
            "error_count": len(documents) - succeeded,
            "total": len(documents),
        }

    async def get_document(
        self, index_name: str, document_id: str
    ) -> VectorDocument | None:
        """Get document by ID."""
        if self.is_mock_mode:
            data = self._mock_documents.get(document_id)
            if data:
                return VectorDocument.from_dict(data)
            return None

        if self._search_client is None:
            return None

        try:
            doc = self._search_client.get_document(document_id)
            return VectorDocument(
                id=doc["id"],
                content=doc.get("content", ""),
                embedding=doc.get("embedding", []),
                repository=doc.get("repository", ""),
                file_path=doc.get("file_path", ""),
                entity_type=doc.get("entity_type", "file"),
            )
        except Exception:
            return None

    async def delete_document(self, index_name: str, document_id: str) -> bool:
        """Delete a document."""
        if self.is_mock_mode:
            if document_id in self._mock_documents:
                del self._mock_documents[document_id]
                return True
            return False

        if self._search_client is None:
            logger.error("Search client not initialized")
            return False

        try:
            self._search_client.delete_documents([{"id": document_id}])
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    async def search_similar(
        self,
        index_name: str,
        query_embedding: list[float],
        k: int = 10,
        filters: dict[str, Any] | None = None,
        min_score: float | None = None,
    ) -> list[SearchResult]:
        """Vector similarity search."""
        if self.is_mock_mode:
            # Simple mock: return first k documents
            results = []
            for i, (_doc_id, data) in enumerate(list(self._mock_documents.items())[:k]):
                doc = VectorDocument.from_dict(data)
                results.append(SearchResult(document=doc, score=1.0 - (i * 0.1)))
            return results

        if self._search_client is None:
            logger.error("Search client not initialized")
            return []

        from azure.search.documents.models import VectorizedQuery

        vector_query = VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=k,
            fields="embedding",
        )

        filter_str = None
        if filters:
            filter_parts = []
            for key, value in filters.items():
                filter_parts.append(f"{key} eq '{value}'")
            filter_str = " and ".join(filter_parts)

        search_results = self._search_client.search(
            search_text=None,
            vector_queries=[vector_query],
            filter=filter_str,
            top=k,
        )

        results = []
        for result in search_results:
            score = result.get("@search.score", 0.0)
            if min_score and score < min_score:
                continue

            doc = VectorDocument(
                id=result["id"],
                content=result.get("content", ""),
                embedding=result.get("embedding", []),
                repository=result.get("repository", ""),
                file_path=result.get("file_path", ""),
                entity_type=result.get("entity_type", "file"),
            )
            results.append(
                SearchResult(
                    document=doc,
                    score=score,
                    highlights=result.get("@search.highlights", {}),
                )
            )

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
        """Hybrid search combining text and vector."""
        if self.is_mock_mode:
            return await self.search_similar(index_name, query_embedding, k, filters)

        if self._search_client is None:
            logger.error("Search client not initialized")
            return []

        from azure.search.documents.models import VectorizedQuery

        vector_query = VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=k,
            fields="embedding",
            weight=vector_weight,
        )

        filter_str = None
        if filters:
            filter_parts = [f"{key} eq '{value}'" for key, value in filters.items()]
            filter_str = " and ".join(filter_parts)

        search_results = self._search_client.search(
            search_text=query_text,
            vector_queries=[vector_query],
            filter=filter_str,
            top=k,
        )

        results = []
        for result in search_results:
            doc = VectorDocument(
                id=result["id"],
                content=result.get("content", ""),
                embedding=result.get("embedding", []),
                repository=result.get("repository", ""),
                file_path=result.get("file_path", ""),
                entity_type=result.get("entity_type", "file"),
            )
            results.append(
                SearchResult(
                    document=doc,
                    score=result.get("@search.score", 0.0),
                    highlights=result.get("@search.highlights", {}),
                )
            )

        return results

    async def delete_by_repository(self, index_name: str, repository: str) -> int:
        """Delete all documents for a repository."""
        if self.is_mock_mode:
            to_delete = [
                k
                for k, v in self._mock_documents.items()
                if v.get("repository") == repository
            ]
            for k in to_delete:
                del self._mock_documents[k]
            return len(to_delete)

        if self._search_client is None:
            logger.error("Search client not initialized")
            return 0

        # Search and delete
        search_results = self._search_client.search(
            search_text="*",
            filter=f"repository eq '{repository}'",
            select=["id"],
        )

        ids_to_delete = [{"id": r["id"]} for r in search_results]
        if ids_to_delete:
            self._search_client.delete_documents(ids_to_delete)

        return len(ids_to_delete)

    async def delete_by_file_path(
        self, index_name: str, file_path: str, repository: str
    ) -> int:
        """Delete documents for a file."""
        if self.is_mock_mode:
            to_delete = [
                k
                for k, v in self._mock_documents.items()
                if v.get("file_path") == file_path and v.get("repository") == repository
            ]
            for k in to_delete:
                del self._mock_documents[k]
            return len(to_delete)

        if self._search_client is None:
            logger.error("Search client not initialized")
            return 0

        search_results = self._search_client.search(
            search_text="*",
            filter=f"file_path eq '{file_path}' and repository eq '{repository}'",
            select=["id"],
        )

        ids_to_delete = [{"id": r["id"]} for r in search_results]
        if ids_to_delete:
            self._search_client.delete_documents(ids_to_delete)

        return len(ids_to_delete)

    async def get_health(self) -> dict[str, Any]:
        """Get health status."""
        return {
            "status": "healthy" if self._connected else "disconnected",
            "mode": "mock" if self.is_mock_mode else "azure",
            "endpoint": self.endpoint,
            "index": self.index_name,
        }

    async def get_index_stats(self, index_name: str) -> dict[str, Any]:
        """Get index statistics."""
        if self.is_mock_mode:
            return {"document_count": len(self._mock_documents)}

        if self._index_client is None:
            return {"document_count": "unknown"}

        try:
            stats = self._index_client.get_index_statistics(index_name)
            return {
                "document_count": stats.document_count,
                "storage_size": stats.storage_size,
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {"document_count": "unknown"}
