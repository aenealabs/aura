"""
Project Aura - Query Decomposition API Endpoints

REST API endpoints for the Query Decomposition Panel (ADR-028 Phase 3).
Provides transparency into how complex queries are decomposed into
parallel subqueries for agentic retrieval.

Endpoints:
- POST /api/v1/query/decompose - Decompose a query into subqueries
- GET  /api/v1/query/decomposition/{id} - Get decomposition by ID
- GET  /api/v1/query/decompositions - List recent decompositions
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/query", tags=["Query Decomposition"])


# ============================================================================
# Enums
# ============================================================================


class QueryType(str, Enum):
    """Type of query/subquery."""

    STRUCTURAL = "structural"  # Graph-based (Neptune)
    SEMANTIC = "semantic"  # Vector-based (OpenSearch)
    TEMPORAL = "temporal"  # Time-based filters


class ExecutionPlan(str, Enum):
    """Execution strategy for subqueries."""

    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    HYBRID = "hybrid"


# ============================================================================
# Pydantic Models
# ============================================================================


class SubqueryResult(BaseModel):
    """Individual subquery with execution results."""

    id: str = Field(description="Unique subquery identifier")
    type: QueryType = Field(description="Type of query")
    query: str = Field(description="The subquery text")
    result_count: int = Field(ge=0, description="Number of results")
    confidence: float = Field(ge=0, le=100, description="Confidence score 0-100")
    execution_time_ms: float = Field(ge=0, description="Execution time in ms")
    reasoning: str | None = Field(None, description="Why this subquery was generated")
    source: str | None = Field(None, description="Data source (neptune, opensearch)")


class DecomposeRequest(BaseModel):
    """Request to decompose a query."""

    query: str = Field(..., min_length=1, description="The query to decompose")
    context: str | None = Field(None, description="Optional context for decomposition")
    max_subqueries: int = Field(
        5, ge=1, le=10, description="Max subqueries to generate"
    )


class QueryDecompositionResponse(BaseModel):
    """Full query decomposition response."""

    id: str = Field(description="Decomposition ID")
    original_query: str = Field(description="The original query")
    timestamp: str = Field(description="ISO timestamp")
    subqueries: list[SubqueryResult] = Field(description="Decomposed subqueries")
    total_results: int = Field(ge=0, description="Total results across all subqueries")
    execution_time_ms: float = Field(ge=0, description="Total execution time")
    execution_plan: ExecutionPlan = Field(description="Execution strategy")
    reasoning: str | None = Field(None, description="Why this decomposition was chosen")


class DecompositionListItem(BaseModel):
    """Summary item for decomposition list."""

    id: str
    original_query: str
    timestamp: str
    subquery_count: int
    total_results: int
    execution_time_ms: float


class DecompositionListResponse(BaseModel):
    """Response for listing decompositions."""

    decompositions: list[DecompositionListItem]
    total: int


# ============================================================================
# In-Memory Data Store (Replace with service in production)
# ============================================================================

_decomposition_store: dict[str, dict[str, Any]] = {}


def _generate_decomposition(query: str, max_subqueries: int = 5) -> dict[str, Any]:
    """Generate a query decomposition (mock implementation)."""
    import random
    import re

    decomposition_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc)

    # Analyze query for keywords to generate relevant subqueries
    query_lower = query.lower()
    subqueries: list[dict[str, Any]] = []

    # Detect structural patterns (function names, classes, files)
    structural_keywords = [
        "function",
        "class",
        "method",
        "file",
        "module",
        "import",
        "call",
    ]
    semantic_keywords = [
        "auth",
        "security",
        "database",
        "api",
        "user",
        "login",
        "password",
        "error",
        "exception",
    ]
    temporal_keywords = [
        "recent",
        "last",
        "modified",
        "changed",
        "updated",
        "sprint",
        "week",
        "month",
        "today",
    ]

    has_structural = any(kw in query_lower for kw in structural_keywords)
    has_semantic = any(kw in query_lower for kw in semantic_keywords)
    has_temporal = any(kw in query_lower for kw in temporal_keywords)

    # Always include at least one semantic search
    if not has_structural and not has_temporal:
        has_semantic = True

    # Generate structural subquery
    if has_structural or len(subqueries) < max_subqueries:
        # Extract potential entity names
        words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", query)
        entity_hint = next(
            (w for w in words if len(w) > 3 and w.lower() not in structural_keywords),
            "entity",
        )

        subqueries.append(
            {
                "id": f"sq_{len(subqueries) + 1}",
                "type": QueryType.STRUCTURAL,
                "query": f"Find code entities matching '{entity_hint}' pattern",
                "result_count": random.randint(20, 80),
                "confidence": round(random.uniform(75, 98), 1),
                "execution_time_ms": round(random.uniform(15, 60), 1),
                "reasoning": "Graph traversal to find structurally related code entities",
                "source": "neptune",
            }
        )

    # Generate semantic subquery
    if has_semantic or len(subqueries) < max_subqueries:
        subqueries.append(
            {
                "id": f"sq_{len(subqueries) + 1}",
                "type": QueryType.SEMANTIC,
                "query": f"Semantic search: {query[:100]}",
                "result_count": random.randint(15, 50),
                "confidence": round(random.uniform(65, 92), 1),
                "execution_time_ms": round(random.uniform(50, 150), 1),
                "reasoning": "Vector similarity search for conceptually related code",
                "source": "opensearch",
            }
        )

    # Generate temporal subquery
    if has_temporal:
        time_hint = "last 14 days"
        if "week" in query_lower:
            time_hint = "last 7 days"
        elif "month" in query_lower:
            time_hint = "last 30 days"
        elif "sprint" in query_lower:
            time_hint = "last 14 days"

        subqueries.append(
            {
                "id": f"sq_{len(subqueries) + 1}",
                "type": QueryType.TEMPORAL,
                "query": f"Files modified in {time_hint}",
                "result_count": random.randint(5, 25),
                "confidence": round(random.uniform(85, 99), 1),
                "execution_time_ms": round(random.uniform(8, 25), 1),
                "reasoning": f"Time-filtered search for recently modified code ({time_hint})",
                "source": "git",
            }
        )

    # Add additional semantic subqueries for complex queries
    if len(query.split()) > 5 and len(subqueries) < max_subqueries:
        subqueries.append(
            {
                "id": f"sq_{len(subqueries) + 1}",
                "type": QueryType.SEMANTIC,
                "query": "Related patterns and implementations",
                "result_count": random.randint(10, 35),
                "confidence": round(random.uniform(55, 80), 1),
                "execution_time_ms": round(random.uniform(60, 120), 1),
                "reasoning": "Secondary semantic search for related implementation patterns",
                "source": "opensearch",
            }
        )

    # Calculate totals
    total_results = sum(sq["result_count"] for sq in subqueries)
    total_time = sum(sq["execution_time_ms"] for sq in subqueries)

    # Determine execution plan based on dependencies
    execution_plan = (
        ExecutionPlan.PARALLEL if len(subqueries) <= 3 else ExecutionPlan.HYBRID
    )

    decomposition = {
        "id": decomposition_id,
        "original_query": query,
        "timestamp": timestamp.isoformat(),
        "subqueries": subqueries,
        "total_results": total_results,
        "execution_time_ms": round(total_time * 0.7, 1),  # Parallel saves ~30%
        "execution_plan": execution_plan,
        "reasoning": _generate_reasoning(query, subqueries),
    }

    # Store for retrieval
    _decomposition_store[decomposition_id] = decomposition

    return decomposition


def _generate_reasoning(query: str, subqueries: list[dict]) -> str:
    """Generate human-readable reasoning for the decomposition."""
    types = [
        sq["type"].value if isinstance(sq["type"], Enum) else sq["type"]
        for sq in subqueries
    ]

    if len(set(types)) == 1:
        return f"Single-strategy search using {types[0]} analysis"

    strategies = []
    if QueryType.STRUCTURAL.value in types:
        strategies.append("graph traversal for code structure")
    if QueryType.SEMANTIC.value in types:
        strategies.append("vector search for semantic similarity")
    if QueryType.TEMPORAL.value in types:
        strategies.append("temporal filtering for recent changes")

    return (
        f"Multi-strategy decomposition using {', '.join(strategies)} to maximize recall"
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/decompose", response_model=QueryDecompositionResponse)
async def decompose_query(request: DecomposeRequest) -> QueryDecompositionResponse:
    """
    Decompose a complex query into parallel subqueries.

    Analyzes the query intent and generates optimized subqueries for:
    - Structural analysis (graph database)
    - Semantic search (vector database)
    - Temporal filtering (git history)

    Returns the decomposition plan with confidence scores.
    """
    logger.info(f"Decomposing query: {sanitize_log(request.query[:100])}...")

    decomposition = _generate_decomposition(request.query, request.max_subqueries)

    return QueryDecompositionResponse(
        id=decomposition["id"],
        original_query=decomposition["original_query"],
        timestamp=decomposition["timestamp"],
        subqueries=[SubqueryResult(**sq) for sq in decomposition["subqueries"]],
        total_results=decomposition["total_results"],
        execution_time_ms=decomposition["execution_time_ms"],
        execution_plan=decomposition["execution_plan"],
        reasoning=decomposition["reasoning"],
    )


@router.get(
    "/decomposition/{decomposition_id}", response_model=QueryDecompositionResponse
)
async def get_decomposition(decomposition_id: str) -> QueryDecompositionResponse:
    """
    Get a previously generated query decomposition by ID.
    """
    decomposition = _decomposition_store.get(decomposition_id)
    if not decomposition:
        raise HTTPException(
            status_code=404, detail=f"Decomposition {decomposition_id} not found"
        )

    return QueryDecompositionResponse(
        id=decomposition["id"],
        original_query=decomposition["original_query"],
        timestamp=decomposition["timestamp"],
        subqueries=[SubqueryResult(**sq) for sq in decomposition["subqueries"]],
        total_results=decomposition["total_results"],
        execution_time_ms=decomposition["execution_time_ms"],
        execution_plan=decomposition["execution_plan"],
        reasoning=decomposition["reasoning"],
    )


@router.get("/decompositions", response_model=DecompositionListResponse)
async def list_decompositions(
    limit: int = Query(20, ge=1, le=100, description="Max results"),  # noqa: B008
    offset: int = Query(0, ge=0, description="Offset for pagination"),  # noqa: B008
) -> DecompositionListResponse:
    """
    List recent query decompositions.
    """
    all_decompositions = list(_decomposition_store.values())

    # Sort by timestamp descending
    all_decompositions.sort(key=lambda x: x["timestamp"], reverse=True)

    # Paginate
    total = len(all_decompositions)
    decompositions = all_decompositions[offset : offset + limit]

    items = [
        DecompositionListItem(
            id=d["id"],
            original_query=d["original_query"],
            timestamp=d["timestamp"],
            subquery_count=len(d["subqueries"]),
            total_results=d["total_results"],
            execution_time_ms=d["execution_time_ms"],
        )
        for d in decompositions
    ]

    return DecompositionListResponse(decompositions=items, total=total)


# ============================================================================
# Export Router
# ============================================================================

query_decomposition_router = router
