"""Three-Way Hybrid Retrieval Service

Implements ADR-034 Phase 2.1: Three-Way Hybrid Retrieval

Combines:
1. Dense vectors (OpenSearch k-NN) - Semantic similarity
2. BM25 sparse (OpenSearch) - Keyword matching
3. Neptune graph - Structural relationships

Research shows +22-25% MRR improvement over two-way retrieval.
Critical: sparse_boost parameter tuning (start at 1.2).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


class OpenSearchClient(Protocol):
    """Protocol for OpenSearch client."""

    async def search(self, index: str, body: dict) -> dict:
        """Execute search query."""
        ...


class NeptuneClient(Protocol):
    """Protocol for Neptune client."""

    async def execute(self, query: str) -> list:
        """Execute Gremlin query."""
        ...


class EmbeddingService(Protocol):
    """Protocol for embedding service."""

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for text."""
        ...


@dataclass
class RetrievalResult:
    """Single retrieval result with source metadata."""

    doc_id: str
    content: str
    score: float
    source: str  # "dense", "sparse", "graph"
    metadata: dict = field(default_factory=dict)
    file_path: Optional[str] = None


@dataclass
class FusedResult:
    """Result after Reciprocal Rank Fusion."""

    doc_id: str
    content: str
    rrf_score: float
    source_scores: dict  # {source: score}
    metadata: dict = field(default_factory=dict)
    file_path: Optional[str] = None
    sources_contributed: list[str] = field(default_factory=list)


@dataclass
class RetrievalConfig:
    """Configuration for three-way retrieval."""

    # Tuned parameters from research
    sparse_boost: float = 1.2  # Critical: BM25 needs slight boost
    dense_weight: float = 1.0
    graph_weight: float = 1.0
    rrf_k: int = 60  # Standard RRF constant

    # Index configuration
    index_name: str = "aura-code-index"
    dense_field: str = "embedding"
    content_fields: list[str] = field(
        default_factory=lambda: ["content", "file_path", "function_names"]
    )
    content_boosts: dict = field(
        default_factory=lambda: {"content": 1, "file_path": 2, "function_names": 3}
    )

    # Result limits
    default_k: int = 50
    max_graph_terms: int = 10


class ThreeWayRetrievalService:
    """Implements three-way hybrid retrieval with RRF fusion.

    Combines three retrieval methods:
    1. Dense vector search (OpenSearch k-NN) - captures semantic meaning
    2. Sparse BM25 search (OpenSearch) - captures exact keyword matches
    3. Graph traversal (Neptune) - captures structural relationships

    Results are combined using Reciprocal Rank Fusion (RRF):
        score = sum(weight / (k + rank))

    Configuration:
    - sparse_boost: Weight for BM25 results (default 1.2, research-tuned)
    - dense_weight: Weight for vector results (default 1.0)
    - graph_weight: Weight for graph results (default 1.0)
    - rrf_k: RRF constant (default 60)

    Research shows 22-25% MRR improvement over two-way retrieval.
    """

    def __init__(
        self,
        opensearch_client: OpenSearchClient,
        neptune_client: NeptuneClient,
        embedding_service: EmbeddingService,
        config: Optional[RetrievalConfig] = None,
    ):
        """Initialize three-way retrieval service.

        Args:
            opensearch_client: Client for OpenSearch queries
            neptune_client: Client for Neptune Gremlin queries
            embedding_service: Service for generating embeddings
            config: Retrieval configuration
        """
        self.opensearch = opensearch_client
        self.neptune = neptune_client
        self.embedder = embedding_service
        self.config = config or RetrievalConfig()

    async def retrieve(
        self,
        query: str,
        k: Optional[int] = None,
        weights: Optional[dict] = None,
        include_sources: Optional[list[str]] = None,
    ) -> list[FusedResult]:
        """Execute three-way retrieval with RRF fusion.

        Args:
            query: Search query
            k: Number of results per source (default from config)
            weights: Optional weight overrides {source: weight}
            include_sources: Optional list of sources to include
                            ("dense", "sparse", "graph")

        Returns:
            List of fused results sorted by RRF score
        """
        k = k or self.config.default_k
        weights = weights or {
            "dense": self.config.dense_weight,
            "sparse": self.config.sparse_boost,
            "graph": self.config.graph_weight,
        }
        include_sources = include_sources or ["dense", "sparse", "graph"]

        # Build retrieval tasks
        tasks = []
        source_order = []

        if "dense" in include_sources:
            tasks.append(self._dense_retrieval(query, k))
            source_order.append("dense")

        if "sparse" in include_sources:
            tasks.append(self._sparse_retrieval(query, k))
            source_order.append("sparse")

        if "graph" in include_sources:
            tasks.append(self._graph_retrieval(query, k))
            source_order.append("graph")

        # Execute all retrieval methods in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        source_results: dict[str, list[RetrievalResult]] = {}
        for i, result in enumerate(results):
            source = source_order[i]
            if isinstance(result, Exception):
                logger.warning(f"{source} retrieval failed: {result}")
                source_results[source] = []
            elif isinstance(result, list):
                source_results[source] = result
                logger.debug(f"{source} retrieval returned {len(result)} results")

        # Apply Reciprocal Rank Fusion
        fused = self._reciprocal_rank_fusion(source_results, weights)

        # Calculate result counts safely
        dense_count = len(source_results.get("dense", []))
        sparse_count = len(source_results.get("sparse", []))
        graph_count = len(source_results.get("graph", []))

        logger.info(
            f"Three-way retrieval: query='{query[:50]}...', "
            f"results: dense={dense_count}, "
            f"sparse={sparse_count}, "
            f"graph={graph_count}, "
            f"fused={len(fused)}"
        )

        return fused

    async def _dense_retrieval(self, query: str, k: int) -> list[RetrievalResult]:
        """Dense vector retrieval using OpenSearch k-NN.

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of retrieval results from dense search
        """
        # Generate query embedding
        query_embedding = await self.embedder.embed_text(query)

        # k-NN search
        response = await self.opensearch.search(
            index=self.config.index_name,
            body={
                "size": k,
                "query": {
                    "knn": {
                        self.config.dense_field: {
                            "vector": query_embedding,
                            "k": k,
                        }
                    }
                },
                "_source": ["content", "file_path", "function_names", "last_modified"],
            },
        )

        return self._parse_opensearch_response(response, "dense")

    async def _sparse_retrieval(self, query: str, k: int) -> list[RetrievalResult]:
        """BM25 sparse retrieval using OpenSearch.

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of retrieval results from sparse search
        """
        # Build multi-match query with field boosts
        fields = [
            f"{field}^{self.config.content_boosts.get(field, 1)}"
            for field in self.config.content_fields
        ]

        response = await self.opensearch.search(
            index=self.config.index_name,
            body={
                "size": k,
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": fields,
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                },
                "_source": ["content", "file_path", "function_names", "last_modified"],
            },
        )

        return self._parse_opensearch_response(response, "sparse")

    async def _graph_retrieval(self, query: str, k: int) -> list[RetrievalResult]:
        """Graph retrieval using Neptune Gremlin queries.

        Finds code entities structurally related to query concepts.

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of retrieval results from graph traversal
        """
        # Extract key terms for graph traversal
        key_terms = self._extract_graph_terms(query)

        if not key_terms:
            return []

        # Build Gremlin query
        terms_str = ", ".join(f"'{t}'" for t in key_terms)
        gremlin_query = f"""
        g.V().has('name', within({terms_str}))
            .union(
                identity(),
                both().dedup()
            )
            .dedup()
            .limit({k})
            .project('id', 'name', 'type', 'content', 'file_path')
                .by(id())
                .by(coalesce(values('name'), constant('')))
                .by(label())
                .by(coalesce(values('content'), constant('')))
                .by(coalesce(values('file_path'), constant('')))
        """

        try:
            response = await self.neptune.execute(gremlin_query)

            results = []
            for i, item in enumerate(response):
                results.append(
                    RetrievalResult(
                        doc_id=str(item.get("id", f"graph_{i}")),
                        content=item.get("content", ""),
                        score=1.0 / (i + 1),  # Rank-based score
                        source="graph",
                        file_path=item.get("file_path"),
                        metadata={
                            "name": item.get("name", ""),
                            "type": item.get("type", ""),
                        },
                    )
                )

            return results

        except Exception as e:
            logger.warning(f"Graph retrieval failed: {e}")
            return []

    def _parse_opensearch_response(
        self, response: dict, source: str
    ) -> list[RetrievalResult]:
        """Parse OpenSearch response into RetrievalResult objects.

        Args:
            response: OpenSearch response dictionary
            source: Source identifier ("dense" or "sparse")

        Returns:
            List of parsed retrieval results
        """
        results = []
        hits = response.get("hits", {}).get("hits", [])

        for hit in hits:
            source_doc = hit.get("_source", {})
            results.append(
                RetrievalResult(
                    doc_id=hit["_id"],
                    content=source_doc.get("content", ""),
                    score=hit.get("_score", 0.0),
                    source=source,
                    file_path=source_doc.get("file_path"),
                    metadata={
                        "function_names": source_doc.get("function_names", []),
                        "last_modified": source_doc.get("last_modified"),
                    },
                )
            )

        return results

    def _reciprocal_rank_fusion(
        self,
        source_results: dict[str, list[RetrievalResult]],
        weights: dict[str, float],
    ) -> list[FusedResult]:
        """Apply Reciprocal Rank Fusion to combine results.

        RRF formula: score = sum(weight / (k + rank))

        Args:
            source_results: Results by source {"dense": [...], "sparse": [...], ...}
            weights: Source weights

        Returns:
            Fused and re-ranked results
        """
        # Build doc_id -> data mappings
        doc_scores: dict[str, dict[str, float]] = {}
        doc_content: dict[str, str] = {}
        doc_metadata: dict[str, dict] = {}
        doc_file_path: dict[str, str] = {}
        doc_sources: dict[str, list[str]] = {}

        # Process each source
        for source, results in source_results.items():
            weight = weights.get(source, 1.0)

            for rank, result in enumerate(results):
                doc_id = result.doc_id

                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {}
                    doc_content[doc_id] = result.content
                    doc_metadata[doc_id] = result.metadata
                    doc_file_path[doc_id] = result.file_path or ""
                    doc_sources[doc_id] = []

                # RRF score contribution
                rrf_contribution = weight / (self.config.rrf_k + rank + 1)
                doc_scores[doc_id][source] = rrf_contribution
                doc_sources[doc_id].append(source)

                # Keep best content (longer is usually better)
                if len(result.content) > len(doc_content[doc_id]):
                    doc_content[doc_id] = result.content
                    doc_metadata[doc_id].update(result.metadata)

        # Create fused results
        fused = []
        for doc_id, scores in doc_scores.items():
            rrf_score = sum(scores.values())
            fused.append(
                FusedResult(
                    doc_id=doc_id,
                    content=doc_content[doc_id],
                    rrf_score=rrf_score,
                    source_scores=scores,
                    metadata=doc_metadata[doc_id],
                    file_path=doc_file_path[doc_id],
                    sources_contributed=doc_sources[doc_id],
                )
            )

        # Sort by RRF score descending
        fused.sort(key=lambda x: x.rrf_score, reverse=True)

        return fused

    def _extract_graph_terms(self, query: str) -> list[str]:
        """Extract terms suitable for graph traversal.

        Args:
            query: Search query

        Returns:
            List of terms for graph search
        """
        words = query.split()

        # Prefer capitalized words (likely class/function names)
        capitalized = [w for w in words if len(w) > 2 and w[0].isupper()]

        # Fall back to longer words
        if not capitalized:
            capitalized = [w for w in words if len(w) > 4]

        # Clean and limit
        terms = []
        for word in capitalized:
            # Remove punctuation
            clean = "".join(c for c in word if c.isalnum() or c == "_")
            if clean and len(clean) > 2:
                terms.append(clean)

        return terms[: self.config.max_graph_terms]

    async def retrieve_with_reranking(
        self,
        query: str,
        k: int = 50,
        rerank_top_n: int = 20,
    ) -> list[FusedResult]:
        """Retrieve with optional LLM-based reranking.

        First retrieves using three-way fusion, then optionally
        reranks top results using LLM scoring.

        Args:
            query: Search query
            k: Results per source
            rerank_top_n: Number of top results to rerank

        Returns:
            Reranked results
        """
        # Get initial results
        results = await self.retrieve(query, k)

        # For now, return as-is. LLM reranking can be added later.
        # This is a placeholder for future enhancement.
        return results[:rerank_top_n]

    def get_retrieval_stats(self, results: list[FusedResult]) -> dict:
        """Get statistics about retrieval results.

        Args:
            results: List of fused results

        Returns:
            Statistics dictionary
        """
        if not results:
            return {
                "total": 0,
                "avg_score": 0,
                "source_coverage": {},
                "multi_source_count": 0,
            }

        source_counts = {"dense": 0, "sparse": 0, "graph": 0}
        multi_source_count = 0

        for r in results:
            for source in r.sources_contributed:
                source_counts[source] = source_counts.get(source, 0) + 1
            if len(r.sources_contributed) > 1:
                multi_source_count += 1

        return {
            "total": len(results),
            "avg_score": sum(r.rrf_score for r in results) / len(results),
            "max_score": max(r.rrf_score for r in results),
            "min_score": min(r.rrf_score for r in results),
            "source_coverage": source_counts,
            "multi_source_count": multi_source_count,
            "multi_source_pct": multi_source_count / len(results) * 100,
        }
