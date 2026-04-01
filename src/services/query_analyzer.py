"""
Project Aura - Query Analyzer Service (ADR-028 Phase 3)

LLM-powered query decomposition for complex code intelligence queries.
Breaks down multi-faceted questions into parallel subqueries for improved
retrieval accuracy.

Inspired by Microsoft Foundry's Agentic Retrieval pattern.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """Classification of query intent for routing."""

    STRUCTURAL = "structural"  # Call graphs, dependencies, inheritance
    SEMANTIC = "semantic"  # Conceptual similarity, patterns
    TEMPORAL = "temporal"  # Recent changes, history, blame
    HYBRID = "hybrid"  # Combination of multiple intents
    NAVIGATIONAL = "navigational"  # Find specific file/function


@dataclass
class SubQuery:
    """A decomposed subquery for parallel execution."""

    id: str  # Unique identifier
    query_text: str  # The subquery to execute
    intent: QueryIntent  # Query intent type
    search_type: str  # graph, vector, filesystem, git
    priority: int  # Execution priority (1-10)
    depends_on: list[str] = field(default_factory=list)  # Dependencies
    estimated_tokens: int = 5000  # Token estimate
    reasoning: str = ""  # Why this subquery was generated


@dataclass
class QueryDecomposition:
    """Result of query decomposition."""

    original_query: str  # Original user query
    intent: QueryIntent  # Overall query intent
    subqueries: list[SubQuery]  # Decomposed subqueries
    execution_plan: str  # Parallel or sequential
    reasoning: str  # Explanation of decomposition
    cache_key: str = ""  # Cache key for this decomposition


class QueryAnalyzer:
    """
    LLM-powered query analyzer that decomposes complex queries.

    Features:
    - Multi-faceted query decomposition
    - Intent classification (structural, semantic, temporal, hybrid)
    - Dependency-aware subquery planning
    - Multi-hop reasoning support
    - Query pattern caching

    Example:
        analyzer = QueryAnalyzer(llm_client)

        decomposition = await analyzer.analyze(
            "Find all authentication functions that call the database
             and were modified in the last sprint"
        )

        # Result:
        # - SubQuery 1: [structural] functions with 'auth' in name
        # - SubQuery 2: [structural] functions that call database entities
        # - SubQuery 3: [temporal] files modified in last 14 days
        # - SubQuery 4: [semantic] authentication and authorization patterns
    """

    def __init__(
        self,
        llm_client: Any,
        cache_client: Any | None = None,
        enable_caching: bool = True,
    ):
        """
        Initialize query analyzer.

        Args:
            llm_client: LLM client for query analysis
            cache_client: Optional cache client (DynamoDB or dict)
            enable_caching: Whether to cache decomposition results
        """
        self.llm = llm_client
        self.cache = cache_client or {}
        self.enable_caching = enable_caching

        logger.info("Initialized QueryAnalyzer")

    async def analyze(
        self,
        query: str,
        context_budget: int = 100000,
        max_subqueries: int = 6,
    ) -> QueryDecomposition:
        """
        Analyze and decompose a complex query into subqueries.

        Args:
            query: Natural language query
            context_budget: Available token budget
            max_subqueries: Maximum number of subqueries to generate

        Returns:
            QueryDecomposition with subqueries for parallel execution
        """
        logger.info(f"Analyzing query: {query}")

        # Check cache first
        cache_key = self._compute_cache_key(query, context_budget)
        if self.enable_caching:
            cached = await self._get_cached(cache_key)
            if cached:
                logger.info(f"Cache hit for query: {query[:50]}...")
                return cached

        # Classify intent first (fast)
        intent = await self._classify_intent(query)

        # Decompose based on complexity
        if self._is_simple_query(query):
            decomposition = self._simple_decomposition(query, intent)
        else:
            decomposition = await self._complex_decomposition(
                query, intent, context_budget, max_subqueries
            )

        # Add cache key
        decomposition.cache_key = cache_key

        # Cache result
        if self.enable_caching:
            await self._cache_result(cache_key, decomposition)

        logger.info(
            f"Decomposed query into {len(decomposition.subqueries)} subqueries "
            f"(intent: {decomposition.intent.value})"
        )

        return decomposition

    async def _classify_intent(self, query: str) -> QueryIntent:
        """
        Classify the primary intent of a query.

        Uses fast heuristics first, falls back to LLM for ambiguous cases.
        """
        query_lower = query.lower()

        # Heuristic classification
        structural_keywords = [
            "call",
            "calls",
            "calling",
            "depends",
            "dependency",
            "dependencies",
            "inherits",
            "extends",
            "implements",
            "imports",
            "references",
            "parent",
            "child",
            "relationship",
        ]

        temporal_keywords = [
            "recent",
            "last",
            "modified",
            "changed",
            "commit",
            "history",
            "sprint",
            "week",
            "month",
            "yesterday",
            "today",
            "ago",
        ]

        semantic_keywords = [
            "similar",
            "like",
            "pattern",
            "implementation",
            "approach",
            "handling",
            "logic",
            "concept",
        ]

        nav_keywords = ["where is", "find file", "locate", "path to", "definition of"]

        has_structural = any(kw in query_lower for kw in structural_keywords)
        has_temporal = any(kw in query_lower for kw in temporal_keywords)
        has_semantic = any(kw in query_lower for kw in semantic_keywords)
        has_nav = any(kw in query_lower for kw in nav_keywords)

        # Determine intent
        intent_count = sum([has_structural, has_temporal, has_semantic, has_nav])

        if intent_count >= 2:
            return QueryIntent.HYBRID
        elif has_nav:
            return QueryIntent.NAVIGATIONAL
        elif has_structural:
            return QueryIntent.STRUCTURAL
        elif has_temporal:
            return QueryIntent.TEMPORAL
        elif has_semantic:
            return QueryIntent.SEMANTIC
        else:
            return QueryIntent.SEMANTIC  # Default to semantic

    def _is_simple_query(self, query: str) -> bool:
        """Determine if a query is simple (doesn't need decomposition)."""
        # Simple queries are short and don't have conjunctions
        conjunctions = [" and ", " that ", " which ", " where ", " when "]
        has_conjunction = any(conj in query.lower() for conj in conjunctions)

        return len(query.split()) < 6 and not has_conjunction

    def _simple_decomposition(
        self,
        query: str,
        intent: QueryIntent,
    ) -> QueryDecomposition:
        """Create simple decomposition for straightforward queries."""
        search_type = self._intent_to_search_type(intent)

        subquery = SubQuery(
            id="sq_1",
            query_text=query,
            intent=intent,
            search_type=search_type,
            priority=10,
            estimated_tokens=8000,
            reasoning="Simple query - single search strategy sufficient",
        )

        return QueryDecomposition(
            original_query=query,
            intent=intent,
            subqueries=[subquery],
            execution_plan="single",
            reasoning="Query is simple and doesn't require decomposition",
        )

    async def _complex_decomposition(
        self,
        query: str,
        intent: QueryIntent,
        context_budget: int,
        max_subqueries: int,
    ) -> QueryDecomposition:
        """
        Decompose complex query using LLM.

        This is the core agentic retrieval logic that breaks down
        multi-faceted queries into parallel subqueries.
        """
        prompt = self._build_decomposition_prompt(query, context_budget, max_subqueries)

        try:
            response = await self.llm.generate(prompt)
            decomposition = self._parse_decomposition(query, response)

            # Validate and fix subquery dependencies
            decomposition = self._validate_dependencies(decomposition)

            return decomposition

        except Exception as e:
            logger.error(f"LLM decomposition failed: {e}")
            return self._fallback_decomposition(query, intent, context_budget)

    def _build_decomposition_prompt(
        self,
        query: str,
        context_budget: int,
        max_subqueries: int,
    ) -> str:
        """Build LLM prompt for query decomposition."""
        return f"""You are a query decomposition expert for a code intelligence system.

TASK: Break down the following complex query into parallel subqueries.

USER QUERY: "{query}"
TOKEN BUDGET: {context_budget}
MAX SUBQUERIES: {max_subqueries}

AVAILABLE SEARCH TYPES:
1. **structural** - Code relationships (call graphs, dependencies, inheritance)
   - Use for: "functions calling X", "classes extending Y", "imports from Z"

2. **semantic** - Conceptual similarity using embeddings
   - Use for: "code similar to X", "authentication patterns", "error handling"

3. **temporal** - Time-based queries (git history, recent changes)
   - Use for: "modified last week", "commits by author", "recent changes"

4. **filesystem** - File patterns and metadata
   - Use for: "**/auth/*.py", "test files", "config files"

DECOMPOSITION RULES:
1. Break compound queries (with "and", "that", "which") into separate subqueries
2. Each subquery should be independently executable
3. Mark dependencies if one subquery's results inform another
4. Prioritize most specific queries (10) over general ones (5)
5. Estimate tokens conservatively to stay within budget

EXAMPLE:
Query: "Find authentication functions that call the database and were modified recently"

Decomposition:
- sq_1: [structural] "functions with 'auth' in name" (priority: 9)
- sq_2: [structural] "functions calling database layer" (priority: 8)
- sq_3: [temporal] "files modified in last 14 days" (priority: 7)
- sq_4: [semantic] "authentication and authorization code" (priority: 6)

RESPOND IN JSON:
{{
  "intent": "hybrid",
  "reasoning": "Query combines structural (auth functions + db calls) and temporal (recent) aspects",
  "execution_plan": "parallel_then_intersect",
  "subqueries": [
    {{
      "id": "sq_1",
      "query_text": "functions with 'auth' in name",
      "intent": "structural",
      "search_type": "graph",
      "priority": 9,
      "depends_on": [],
      "estimated_tokens": 3000,
      "reasoning": "Find authentication-related functions by name pattern"
    }}
  ]
}}

Now decompose the query:"""

    def _parse_decomposition(
        self, original_query: str, llm_response: str
    ) -> QueryDecomposition:
        """Parse LLM response into QueryDecomposition."""
        try:
            # Extract JSON
            json_start = llm_response.find("{")
            json_end = llm_response.rfind("}") + 1

            if json_start == -1:
                raise ValueError("No JSON found in response")

            json_str = llm_response[json_start:json_end]
            data = json.loads(json_str)

            # Parse intent
            intent_str = data.get("intent", "hybrid")
            try:
                intent = QueryIntent(intent_str)
            except ValueError:
                intent = QueryIntent.HYBRID

            # Parse subqueries
            subqueries: list[SubQuery] = []
            for sq_data in data.get("subqueries", []):
                sq_intent_str = sq_data.get("intent", "semantic")
                try:
                    sq_intent = QueryIntent(sq_intent_str)
                except ValueError:
                    sq_intent = QueryIntent.SEMANTIC

                subqueries.append(
                    SubQuery(
                        id=sq_data.get("id", f"sq_{len(subqueries)+1}"),
                        query_text=sq_data.get("query_text", ""),
                        intent=sq_intent,
                        search_type=sq_data.get("search_type", "vector"),
                        priority=sq_data.get("priority", 5),
                        depends_on=sq_data.get("depends_on", []),
                        estimated_tokens=sq_data.get("estimated_tokens", 5000),
                        reasoning=sq_data.get("reasoning", ""),
                    )
                )

            return QueryDecomposition(
                original_query=original_query,
                intent=intent,
                subqueries=subqueries,
                execution_plan=data.get("execution_plan", "parallel"),
                reasoning=data.get("reasoning", ""),
            )

        except Exception as e:
            logger.error(f"Failed to parse decomposition: {e}")
            raise

    def _validate_dependencies(
        self, decomposition: QueryDecomposition
    ) -> QueryDecomposition:
        """Validate and fix subquery dependencies."""
        valid_ids = {sq.id for sq in decomposition.subqueries}

        for sq in decomposition.subqueries:
            # Remove invalid dependencies
            sq.depends_on = [dep for dep in sq.depends_on if dep in valid_ids]

            # Ensure no self-dependencies
            if sq.id in sq.depends_on:
                sq.depends_on.remove(sq.id)

        return decomposition

    def _fallback_decomposition(
        self,
        query: str,
        intent: QueryIntent,
        context_budget: int,
    ) -> QueryDecomposition:
        """Fallback decomposition when LLM fails."""
        logger.warning("Using fallback decomposition")

        # Create balanced multi-strategy decomposition
        subqueries = [
            SubQuery(
                id="sq_1",
                query_text=f"Semantic search: {query}",
                intent=QueryIntent.SEMANTIC,
                search_type="vector",
                priority=10,
                estimated_tokens=min(10000, context_budget // 3),
                reasoning="Primary semantic search for conceptual matches",
            ),
            SubQuery(
                id="sq_2",
                query_text=f"Code entities related to: {query}",
                intent=QueryIntent.STRUCTURAL,
                search_type="graph",
                priority=8,
                estimated_tokens=min(5000, context_budget // 4),
                reasoning="Graph search for structural relationships",
            ),
            SubQuery(
                id="sq_3",
                query_text=f"Files matching: *{query.split()[0]}*",
                intent=QueryIntent.NAVIGATIONAL,
                search_type="filesystem",
                priority=6,
                estimated_tokens=min(3000, context_budget // 6),
                reasoning="Filesystem pattern matching",
            ),
        ]

        return QueryDecomposition(
            original_query=query,
            intent=intent,
            subqueries=subqueries,
            execution_plan="parallel",
            reasoning="Fallback: balanced multi-strategy approach",
        )

    def _intent_to_search_type(self, intent: QueryIntent) -> str:
        """Map query intent to search type."""
        mapping = {
            QueryIntent.STRUCTURAL: "graph",
            QueryIntent.SEMANTIC: "vector",
            QueryIntent.TEMPORAL: "git",
            QueryIntent.NAVIGATIONAL: "filesystem",
            QueryIntent.HYBRID: "vector",  # Default for hybrid
        }
        return mapping.get(intent, "vector")

    def _compute_cache_key(self, query: str, context_budget: int) -> str:
        """Compute cache key for query decomposition."""
        normalized = query.lower().strip()
        budget_bucket = (context_budget // 10000) * 10000  # Bucket by 10k
        key_input = f"{normalized}:{budget_bucket}"
        return hashlib.sha256(key_input.encode()).hexdigest()[:16]

    async def _get_cached(self, cache_key: str) -> QueryDecomposition | None:
        """Get cached decomposition."""
        if isinstance(self.cache, dict):
            return self.cache.get(cache_key)

        # DynamoDB cache (if provided)
        try:
            if hasattr(self.cache, "get_item"):
                response = await self.cache.get_item(
                    TableName="aura-query-cache", Key={"cache_key": {"S": cache_key}}
                )
                if "Item" in response:
                    return self._deserialize_decomposition(response["Item"])
        except Exception as e:
            logger.debug(f"Cache miss: {e}")

        return None

    async def _cache_result(
        self, cache_key: str, decomposition: QueryDecomposition
    ) -> None:
        """Cache decomposition result."""
        if isinstance(self.cache, dict):
            self.cache[cache_key] = decomposition
            return

        # DynamoDB cache (if provided)
        try:
            if hasattr(self.cache, "put_item"):
                await self.cache.put_item(
                    TableName="aura-query-cache",
                    Item=self._serialize_decomposition(cache_key, decomposition),
                    ConditionExpression="attribute_not_exists(cache_key)",
                )
        except Exception as e:
            logger.debug(f"Cache write failed: {e}")

    def _serialize_decomposition(self, cache_key: str, d: QueryDecomposition) -> dict:
        """Serialize decomposition for DynamoDB."""
        return {
            "cache_key": {"S": cache_key},
            "original_query": {"S": d.original_query},
            "intent": {"S": d.intent.value},
            "execution_plan": {"S": d.execution_plan},
            "reasoning": {"S": d.reasoning},
            "subqueries": {
                "S": json.dumps(
                    [
                        {
                            "id": sq.id,
                            "query_text": sq.query_text,
                            "intent": sq.intent.value,
                            "search_type": sq.search_type,
                            "priority": sq.priority,
                            "depends_on": sq.depends_on,
                            "estimated_tokens": sq.estimated_tokens,
                            "reasoning": sq.reasoning,
                        }
                        for sq in d.subqueries
                    ]
                )
            },
            "ttl": {"N": str(86400 * 7)},  # 7 day TTL
        }

    def _deserialize_decomposition(self, item: dict) -> QueryDecomposition:
        """Deserialize decomposition from DynamoDB."""
        subqueries_data = json.loads(item["subqueries"]["S"])
        subqueries = [
            SubQuery(
                id=sq["id"],
                query_text=sq["query_text"],
                intent=QueryIntent(sq["intent"]),
                search_type=sq["search_type"],
                priority=sq["priority"],
                depends_on=sq["depends_on"],
                estimated_tokens=sq["estimated_tokens"],
                reasoning=sq["reasoning"],
            )
            for sq in subqueries_data
        ]

        return QueryDecomposition(
            original_query=item["original_query"]["S"],
            intent=QueryIntent(item["intent"]["S"]),
            subqueries=subqueries,
            execution_plan=item["execution_plan"]["S"],
            reasoning=item["reasoning"]["S"],
            cache_key=item["cache_key"]["S"],
        )


# Factory function
def create_query_analyzer(
    use_mock: bool = False,
    enable_caching: bool = True,
) -> QueryAnalyzer:
    """
    Create a QueryAnalyzer with real or mock LLM.

    Args:
        use_mock: If True, use mock LLM for testing
        enable_caching: Whether to enable query caching

    Returns:
        Configured QueryAnalyzer instance
    """
    if use_mock:
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "intent": "hybrid",
                "reasoning": "Mock decomposition",
                "execution_plan": "parallel",
                "subqueries": [
                    {
                        "id": "sq_1",
                        "query_text": "semantic search",
                        "intent": "semantic",
                        "search_type": "vector",
                        "priority": 10,
                        "depends_on": [],
                        "estimated_tokens": 8000,
                        "reasoning": "Mock semantic search",
                    }
                ],
            }
        )
        return QueryAnalyzer(llm_client=mock_llm, enable_caching=enable_caching)
    else:
        from src.services.bedrock_llm_service import create_llm_service

        llm_service = create_llm_service()
        return QueryAnalyzer(llm_client=llm_service, enable_caching=enable_caching)


# Example usage
async def example_usage():
    """Example usage of QueryAnalyzer."""
    analyzer = create_query_analyzer(use_mock=True)

    # Complex query
    query = "Find all authentication functions that call the database and were modified in the last sprint"

    decomposition = await analyzer.analyze(query, context_budget=50000)

    print(f"\nOriginal Query: {decomposition.original_query}")
    print(f"Intent: {decomposition.intent.value}")
    print(f"Execution Plan: {decomposition.execution_plan}")
    print(f"Reasoning: {decomposition.reasoning}")
    print(f"\nSubqueries ({len(decomposition.subqueries)}):")

    for sq in decomposition.subqueries:
        print(f"  [{sq.id}] {sq.search_type}: {sq.query_text}")
        print(f"       Priority: {sq.priority}, Tokens: {sq.estimated_tokens}")
        if sq.depends_on:
            print(f"       Depends on: {sq.depends_on}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
