"""
Project Aura - Mock Vector Service

In-memory mock implementation of VectorDatabaseService for testing.
"""

import logging
import math
from typing import Any

from src.abstractions.vector_database import (
    IndexConfig,
    SearchResult,
    VectorDatabaseService,
    VectorDocument,
)

logger = logging.getLogger(__name__)


class MockVectorService(VectorDatabaseService):
    """Mock vector database for testing."""

    def __init__(self) -> None:
        self._indices: dict[str, IndexConfig] = {}
        self._documents: dict[str, dict[str, VectorDocument]] = {}
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        logger.info("MockVectorService connected")
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def create_index(self, config: IndexConfig) -> bool:
        self._indices[config.name] = config
        self._documents[config.name] = {}
        return True

    async def delete_index(self, index_name: str) -> bool:
        if index_name in self._indices:
            del self._indices[index_name]
            del self._documents[index_name]
            return True
        return False

    async def index_exists(self, index_name: str) -> bool:
        return index_name in self._indices

    async def index_document(self, index_name: str, document: VectorDocument) -> str:
        if index_name not in self._documents:
            self._documents[index_name] = {}
        self._documents[index_name][document.id] = document
        return document.id

    async def bulk_index(
        self, index_name: str, documents: list[VectorDocument]
    ) -> dict[str, Any]:
        for doc in documents:
            await self.index_document(index_name, doc)
        return {
            "success_count": len(documents),
            "error_count": 0,
            "total": len(documents),
        }

    async def get_document(
        self, index_name: str, document_id: str
    ) -> VectorDocument | None:
        return self._documents.get(index_name, {}).get(document_id)

    async def delete_document(self, index_name: str, document_id: str) -> bool:
        if index_name in self._documents and document_id in self._documents[index_name]:
            del self._documents[index_name][document_id]
            return True
        return False

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2) or len(vec1) == 0:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def search_similar(
        self,
        index_name: str,
        query_embedding: list[float],
        k: int = 10,
        filters: dict[str, Any] | None = None,
        min_score: float | None = None,
    ) -> list[SearchResult]:
        docs = self._documents.get(index_name, {}).values()

        scored_docs = []
        for doc in docs:
            # Apply filters
            if filters:
                match = True
                for key, value in filters.items():
                    if key == "repository" and doc.repository != value:
                        match = False
                    elif key == "entity_type" and doc.entity_type != value:
                        match = False
                if not match:
                    continue

            score = self._cosine_similarity(query_embedding, doc.embedding)
            if min_score is not None and score < min_score:
                continue
            scored_docs.append((doc, score))

        # Sort by score descending
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        results = []
        for doc, score in scored_docs[:k]:
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
        # Simple hybrid: combine text matching with vector similarity
        docs = self._documents.get(index_name, {}).values()

        scored_docs = []
        query_terms = query_text.lower().split()

        for doc in docs:
            if filters:
                match = True
                for key, value in filters.items():
                    if key == "repository" and doc.repository != value:
                        match = False
                if not match:
                    continue

            # Vector score
            vector_score = self._cosine_similarity(query_embedding, doc.embedding)

            # Text score (simple term matching)
            text_score = 0.0
            doc_text = doc.content.lower()
            for term in query_terms:
                if term in doc_text:
                    text_score += 1.0
            if query_terms:
                text_score /= len(query_terms)

            # Combined score
            combined_score = (text_weight * text_score) + (vector_weight * vector_score)
            scored_docs.append((doc, combined_score))

        scored_docs.sort(key=lambda x: x[1], reverse=True)

        results = []
        for doc, score in scored_docs[:k]:
            results.append(SearchResult(document=doc, score=score))
        return results

    async def delete_by_repository(self, index_name: str, repository: str) -> int:
        if index_name not in self._documents:
            return 0
        to_delete = [
            k
            for k, v in self._documents[index_name].items()
            if v.repository == repository
        ]
        for k in to_delete:
            del self._documents[index_name][k]
        return len(to_delete)

    async def delete_by_file_path(
        self, index_name: str, file_path: str, repository: str
    ) -> int:
        if index_name not in self._documents:
            return 0
        to_delete = [
            k
            for k, v in self._documents[index_name].items()
            if v.file_path == file_path and v.repository == repository
        ]
        for k in to_delete:
            del self._documents[index_name][k]
        return len(to_delete)

    async def get_health(self) -> dict[str, Any]:
        return {"status": "healthy", "mode": "mock"}

    async def get_index_stats(self, index_name: str) -> dict[str, Any]:
        return {"document_count": len(self._documents.get(index_name, {}))}
