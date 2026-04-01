"""
Project Aura - Vector Database Abstraction

Abstract interface for vector database operations.
Implementations: AWS OpenSearch, Azure AI Search

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class VectorDocument:
    """Represents a document with vector embedding for similarity search."""

    id: str
    content: str
    embedding: list[float]
    repository: str
    file_path: str
    entity_type: str  # file, function, class, etc.
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert document to dictionary for storage."""
        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding,
            "repository": self.repository,
            "file_path": self.file_path,
            "entity_type": self.entity_type,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VectorDocument":
        """Create document from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            embedding=data["embedding"],
            repository=data["repository"],
            file_path=data["file_path"],
            entity_type=data["entity_type"],
            metadata=data.get("metadata", {}),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
        )


@dataclass
class SearchResult:
    """Result from a vector similarity search."""

    document: VectorDocument
    score: float  # Similarity score (higher = more similar)
    highlights: dict[str, list[str]] = field(default_factory=dict)  # Text highlighting

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "document": self.document.to_dict(),
            "score": self.score,
            "highlights": self.highlights,
        }


@dataclass
class IndexConfig:
    """Configuration for vector index."""

    name: str
    dimension: int  # Vector dimension (e.g., 1536 for OpenAI ada-002)
    similarity_metric: str = "cosine"  # cosine, euclidean, dot_product
    ef_construction: int = 128  # HNSW construction parameter
    m: int = 16  # HNSW M parameter
    replicas: int = 1
    shards: int = 1


class VectorDatabaseService(ABC):
    """
    Abstract interface for vector database operations.

    Implementations:
    - AWS: OpenSearchVectorService (k-NN plugin)
    - Azure: AzureAISearchService (vector search)
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the vector database."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the database connection."""

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if the database connection is active."""

    # Index Operations
    @abstractmethod
    async def create_index(self, config: IndexConfig) -> bool:
        """
        Create a vector index.

        Args:
            config: Index configuration

        Returns:
            True if created successfully
        """

    @abstractmethod
    async def delete_index(self, index_name: str) -> bool:
        """
        Delete a vector index.

        Args:
            index_name: Name of the index to delete

        Returns:
            True if deleted successfully
        """

    @abstractmethod
    async def index_exists(self, index_name: str) -> bool:
        """
        Check if an index exists.

        Args:
            index_name: Name of the index

        Returns:
            True if the index exists
        """

    # Document Operations
    @abstractmethod
    async def index_document(self, index_name: str, document: VectorDocument) -> str:
        """
        Index a single document with its embedding.

        Args:
            index_name: Target index name
            document: Document to index

        Returns:
            The document ID
        """

    @abstractmethod
    async def bulk_index(
        self, index_name: str, documents: list[VectorDocument]
    ) -> dict[str, Any]:
        """
        Bulk index multiple documents.

        Args:
            index_name: Target index name
            documents: List of documents to index

        Returns:
            Bulk operation result with success/failure counts
        """

    @abstractmethod
    async def get_document(
        self, index_name: str, document_id: str
    ) -> VectorDocument | None:
        """
        Get a document by ID.

        Args:
            index_name: Index name
            document_id: Document ID

        Returns:
            The document if found, None otherwise
        """

    @abstractmethod
    async def delete_document(self, index_name: str, document_id: str) -> bool:
        """
        Delete a document by ID.

        Args:
            index_name: Index name
            document_id: Document ID

        Returns:
            True if deleted successfully
        """

    # Search Operations
    @abstractmethod
    async def search_similar(
        self,
        index_name: str,
        query_embedding: list[float],
        k: int = 10,
        filters: dict[str, Any] | None = None,
        min_score: float | None = None,
    ) -> list[SearchResult]:
        """
        Search for similar documents using vector similarity.

        Args:
            index_name: Index to search
            query_embedding: Query vector
            k: Number of results to return
            filters: Optional metadata filters
            min_score: Minimum similarity score threshold

        Returns:
            List of search results ordered by similarity
        """

    @abstractmethod
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
        """
        Hybrid search combining text and vector similarity.

        Args:
            index_name: Index to search
            query_text: Text query for BM25/keyword search
            query_embedding: Query vector for similarity search
            k: Number of results to return
            text_weight: Weight for text search score
            vector_weight: Weight for vector similarity score
            filters: Optional metadata filters

        Returns:
            List of search results with combined scores
        """

    # Bulk Operations
    @abstractmethod
    async def delete_by_repository(self, index_name: str, repository: str) -> int:
        """
        Delete all documents for a repository.

        Args:
            index_name: Index name
            repository: Repository identifier

        Returns:
            Number of documents deleted
        """

    @abstractmethod
    async def delete_by_file_path(
        self, index_name: str, file_path: str, repository: str
    ) -> int:
        """
        Delete all documents for a specific file.

        Args:
            index_name: Index name
            file_path: File path
            repository: Repository identifier

        Returns:
            Number of documents deleted
        """

    # Health and Metrics
    @abstractmethod
    async def get_health(self) -> dict[str, Any]:
        """
        Get cluster/service health status.

        Returns:
            Health status including cluster state, node count, etc.
        """

    @abstractmethod
    async def get_index_stats(self, index_name: str) -> dict[str, Any]:
        """
        Get statistics for an index.

        Returns:
            Statistics including document count, index size, etc.
        """
