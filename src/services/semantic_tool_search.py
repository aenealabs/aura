"""Semantic Tool Search Service

Implements ADR-037 Phase 1.8: Semantic Tool Search

Provides intelligent tool discovery using semantic similarity,
enabling agents to find relevant tools based on natural language
descriptions of what they need to accomplish.

Key Features:
- Semantic embedding-based tool matching
- Multi-criteria tool ranking
- Category-aware filtering
- Usage pattern learning
- Tool recommendation engine
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol, cast

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Tool categories for filtering."""

    FILE_OPERATIONS = "file_operations"
    CODE_ANALYSIS = "code_analysis"
    CODE_GENERATION = "code_generation"
    TESTING = "testing"
    SECURITY = "security"
    DATABASE = "database"
    API = "api"
    COMMUNICATION = "communication"
    BROWSER = "browser"
    SYSTEM = "system"
    MEMORY = "memory"
    SEARCH = "search"
    VISUALIZATION = "visualization"
    DOCUMENTATION = "documentation"


class ToolComplexity(Enum):
    """Tool complexity levels."""

    SIMPLE = "simple"  # Single action, no side effects
    MODERATE = "moderate"  # Multiple steps or side effects
    COMPLEX = "complex"  # Requires careful planning
    DANGEROUS = "dangerous"  # Destructive or irreversible


class EmbeddingService(Protocol):
    """Protocol for embedding service."""

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for text."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for batch of texts."""
        ...


class VectorStore(Protocol):
    """Protocol for vector store."""

    async def upsert(self, id: str, embedding: list[float], metadata: dict) -> None:
        """Upsert vector."""
        ...

    async def search(
        self,
        embedding: list[float],
        limit: int,
        filter: Optional[dict] = None,
    ) -> list[dict]:
        """Search for similar vectors."""
        ...

    async def delete(self, id: str) -> None:
        """Delete vector."""
        ...


@dataclass
class ToolParameter:
    """Tool parameter definition."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[list[str]] = None
    examples: list[str] = field(default_factory=list)


@dataclass
class ToolDefinition:
    """Complete tool definition for indexing."""

    tool_id: str
    name: str
    description: str
    detailed_description: Optional[str] = None
    category: ToolCategory = ToolCategory.SYSTEM
    complexity: ToolComplexity = ToolComplexity.SIMPLE
    parameters: list[ToolParameter] = field(default_factory=list)
    return_type: str = "any"
    return_description: Optional[str] = None
    examples: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    requires_approval: bool = False
    deprecated: bool = False
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    usage_count: int = 0
    success_rate: float = 1.0


@dataclass
class ToolSearchResult:
    """Result from tool search."""

    tool: ToolDefinition
    score: float
    match_reasons: list[str] = field(default_factory=list)


@dataclass
class ToolRecommendation:
    """Tool recommendation with context."""

    tool: ToolDefinition
    confidence: float
    reason: str
    usage_hint: Optional[str] = None
    alternatives: list[str] = field(default_factory=list)


@dataclass
class SearchConfig:
    """Configuration for semantic tool search."""

    min_score: float = 0.3
    max_results: int = 10
    boost_frequently_used: bool = True
    boost_high_success_rate: bool = True
    include_deprecated: bool = False
    embedding_weight: float = 0.7
    keyword_weight: float = 0.3


class SemanticToolSearch:
    """Semantic search for tool discovery.

    Enables agents to find relevant tools based on natural language
    descriptions of what they need to accomplish.

    Features:
    - Embedding-based semantic search
    - Keyword matching with boosting
    - Category and complexity filtering
    - Usage-based ranking
    - Tool recommendations

    Usage:
        search = SemanticToolSearch(embedding_service, vector_store)

        # Index tools
        await search.index_tool(ToolDefinition(
            tool_id="file_read",
            name="Read File",
            description="Read contents of a file",
            category=ToolCategory.FILE_OPERATIONS,
        ))

        # Search for tools
        results = await search.search_tools(
            query="I need to read a configuration file",
            limit=5,
        )

        # Get recommendations
        recommendations = await search.recommend_tools(
            task_description="Parse and validate a JSON config file",
            current_context={"file_type": "json"},
        )
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: Optional[VectorStore] = None,
        config: Optional[SearchConfig] = None,
    ):
        """Initialize semantic tool search.

        Args:
            embedding_service: Service for generating embeddings
            vector_store: Vector store for similarity search
            config: Search configuration
        """
        self.embedder = embedding_service
        self.vector_store = vector_store
        self.config = config or SearchConfig()
        self._tools: dict[str, ToolDefinition] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._usage_stats: dict[str, dict] = {}

    async def index_tool(
        self,
        tool: ToolDefinition,
    ) -> None:
        """Index tool for semantic search.

        Args:
            tool: Tool definition to index
        """
        # Build searchable text
        searchable_text = self._build_searchable_text(tool)

        # Generate embedding
        embedding = await self.embedder.embed_text(searchable_text)

        # Store locally
        self._tools[tool.tool_id] = tool
        self._embeddings[tool.tool_id] = embedding

        # Store in vector store if available
        if self.vector_store:
            await self.vector_store.upsert(
                tool.tool_id,
                embedding,
                {
                    "name": tool.name,
                    "category": tool.category.value,
                    "complexity": tool.complexity.value,
                    "deprecated": tool.deprecated,
                    "requires_approval": tool.requires_approval,
                    "tags": tool.tags,
                },
            )

        logger.debug(f"Indexed tool: {tool.tool_id}")

    async def index_tools_batch(
        self,
        tools: list[ToolDefinition],
    ) -> int:
        """Index multiple tools.

        Args:
            tools: Tools to index

        Returns:
            Number of tools indexed
        """
        texts = [self._build_searchable_text(t) for t in tools]
        embeddings = await self.embedder.embed_batch(texts)

        for tool, embedding in zip(tools, embeddings):
            self._tools[tool.tool_id] = tool
            self._embeddings[tool.tool_id] = embedding

            if self.vector_store:
                await self.vector_store.upsert(
                    tool.tool_id,
                    embedding,
                    {
                        "name": tool.name,
                        "category": tool.category.value,
                        "complexity": tool.complexity.value,
                        "deprecated": tool.deprecated,
                        "requires_approval": tool.requires_approval,
                        "tags": tool.tags,
                    },
                )

        logger.info(f"Indexed {len(tools)} tools")
        return len(tools)

    async def remove_tool(self, tool_id: str) -> bool:
        """Remove tool from index.

        Args:
            tool_id: Tool to remove

        Returns:
            True if removed
        """
        if tool_id in self._tools:
            del self._tools[tool_id]
            del self._embeddings[tool_id]

            if self.vector_store:
                await self.vector_store.delete(tool_id)

            return True
        return False

    async def search_tools(
        self,
        query: str,
        limit: int = 5,
        min_score: Optional[float] = None,
        categories: Optional[list[ToolCategory]] = None,
        exclude_deprecated: bool = True,
        exclude_dangerous: bool = False,
    ) -> list[ToolSearchResult]:
        """Find tools matching natural language query.

        Args:
            query: Natural language query
            limit: Maximum results
            min_score: Minimum relevance score
            categories: Filter by categories
            exclude_deprecated: Exclude deprecated tools
            exclude_dangerous: Exclude dangerous complexity tools

        Returns:
            Ranked list of matching tools
        """
        min_score = min_score or self.config.min_score

        # Generate query embedding
        query_embedding = await self.embedder.embed_text(query)

        # Extract keywords for boosting
        keywords = self._extract_keywords(query)

        results = []

        for tool_id, tool in self._tools.items():
            # Apply filters
            if exclude_deprecated and tool.deprecated:
                continue
            if exclude_dangerous and tool.complexity == ToolComplexity.DANGEROUS:
                continue
            if categories and tool.category not in categories:
                continue

            # Calculate semantic similarity
            embedding = self._embeddings.get(tool_id)
            if not embedding:
                continue

            semantic_score = self._cosine_similarity(query_embedding, embedding)

            # Calculate keyword score
            keyword_score = self._keyword_score(keywords, tool)

            # Combined score
            combined_score = (
                self.config.embedding_weight * semantic_score
                + self.config.keyword_weight * keyword_score
            )

            # Apply usage boosts
            if self.config.boost_frequently_used:
                usage_boost = min(0.1, tool.usage_count / 1000)
                combined_score += usage_boost

            if self.config.boost_high_success_rate:
                success_boost = (tool.success_rate - 0.5) * 0.1
                combined_score += success_boost

            if combined_score >= min_score:
                match_reasons = self._generate_match_reasons(
                    query, tool, semantic_score, keyword_score
                )
                results.append(
                    ToolSearchResult(
                        tool=tool,
                        score=combined_score,
                        match_reasons=match_reasons,
                    )
                )

        # Sort by score
        results.sort(key=lambda r: r.score, reverse=True)

        return results[:limit]

    async def recommend_tools(
        self,
        task_description: str,
        current_context: Optional[dict[str, Any]] = None,
        exclude_tools: Optional[list[str]] = None,
    ) -> list[ToolRecommendation]:
        """Recommend tools for a given task.

        Args:
            task_description: Description of task
            current_context: Current execution context
            exclude_tools: Tools to exclude

        Returns:
            Tool recommendations with confidence
        """
        # Search for relevant tools
        results = await self.search_tools(
            query=task_description,
            limit=self.config.max_results,
        )

        recommendations = []

        for result in results:
            if exclude_tools and result.tool.tool_id in exclude_tools:
                continue

            # Generate recommendation
            confidence = min(1.0, result.score)
            reason = self._generate_recommendation_reason(
                result.tool, task_description, current_context
            )

            # Find alternatives
            alternatives = [
                r.tool.tool_id
                for r in results
                if r.tool.tool_id != result.tool.tool_id
                and r.tool.category == result.tool.category
            ][:3]

            # Generate usage hint
            usage_hint = self._generate_usage_hint(result.tool, current_context)

            recommendations.append(
                ToolRecommendation(
                    tool=result.tool,
                    confidence=confidence,
                    reason=reason,
                    usage_hint=usage_hint,
                    alternatives=alternatives,
                )
            )

        return recommendations

    async def find_similar_tools(
        self,
        tool_id: str,
        limit: int = 5,
    ) -> list[ToolSearchResult]:
        """Find tools similar to given tool.

        Args:
            tool_id: Reference tool
            limit: Maximum results

        Returns:
            Similar tools
        """
        if tool_id not in self._embeddings:
            return []

        embedding = self._embeddings[tool_id]
        reference_tool = self._tools[tool_id]

        results = []

        for other_id, other_embedding in self._embeddings.items():
            if other_id == tool_id:
                continue

            score = self._cosine_similarity(embedding, other_embedding)
            other_tool = self._tools[other_id]

            results.append(
                ToolSearchResult(
                    tool=other_tool,
                    score=score,
                    match_reasons=[f"Similar to {reference_tool.name}"],
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def record_tool_usage(
        self,
        tool_id: str,
        success: bool,
        context: Optional[dict] = None,
    ) -> None:
        """Record tool usage for learning.

        Args:
            tool_id: Tool used
            success: Whether usage was successful
            context: Usage context
        """
        if tool_id in self._tools:
            tool = self._tools[tool_id]
            tool.usage_count += 1

            # Update success rate (exponential moving average)
            alpha = 0.1
            tool.success_rate = (
                alpha * (1.0 if success else 0.0) + (1 - alpha) * tool.success_rate
            )

        # Record stats
        if tool_id not in self._usage_stats:
            self._usage_stats[tool_id] = {
                "total": 0,
                "success": 0,
                "contexts": [],
            }

        stats = self._usage_stats[tool_id]
        stats["total"] += 1
        if success:
            stats["success"] += 1
        if context:
            stats["contexts"].append(context)

    def get_tool(self, tool_id: str) -> Optional[ToolDefinition]:
        """Get tool by ID.

        Args:
            tool_id: Tool identifier

        Returns:
            Tool definition or None
        """
        return self._tools.get(tool_id)

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        include_deprecated: bool = False,
    ) -> list[ToolDefinition]:
        """List all indexed tools.

        Args:
            category: Filter by category
            include_deprecated: Include deprecated tools

        Returns:
            List of tools
        """
        tools = list(self._tools.values())

        if category:
            tools = [t for t in tools if t.category == category]

        if not include_deprecated:
            tools = [t for t in tools if not t.deprecated]

        return tools

    def get_categories(self) -> dict[ToolCategory, int]:
        """Get tool count by category.

        Returns:
            Category -> count mapping
        """
        counts: dict[ToolCategory, int] = {}
        for tool in self._tools.values():
            counts[tool.category] = counts.get(tool.category, 0) + 1
        return counts

    def _build_searchable_text(self, tool: ToolDefinition) -> str:
        """Build searchable text from tool definition.

        Args:
            tool: Tool definition

        Returns:
            Searchable text
        """
        parts = [
            tool.name,
            tool.description,
            tool.detailed_description or "",
            tool.category.value.replace("_", " "),
            " ".join(tool.tags),
        ]

        # Include parameter info
        for param in tool.parameters:
            parts.append(f"{param.name}: {param.description}")

        # Include examples
        for example in tool.examples:
            if "description" in example:
                parts.append(example["description"])

        return " ".join(parts)

    def _extract_keywords(self, query: str) -> list[str]:
        """Extract keywords from query.

        Args:
            query: Search query

        Returns:
            List of keywords
        """
        # Remove common words
        stopwords = {
            "a",
            "an",
            "the",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "can",
            "may",
            "might",
            "must",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "i",
            "need",
            "want",
            "like",
            "help",
            "me",
        }

        words = re.findall(r"\b\w+\b", query.lower())
        return [w for w in words if w not in stopwords and len(w) > 2]

    def _keyword_score(self, keywords: list[str], tool: ToolDefinition) -> float:
        """Calculate keyword match score.

        Args:
            keywords: Query keywords
            tool: Tool to score

        Returns:
            Score 0-1
        """
        if not keywords:
            return 0.0

        searchable = self._build_searchable_text(tool).lower()
        matches = sum(1 for kw in keywords if kw in searchable)
        return matches / len(keywords)

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score
        """
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return cast(float, dot_product / (norm1 * norm2))

    def _generate_match_reasons(
        self,
        query: str,
        tool: ToolDefinition,
        semantic_score: float,
        keyword_score: float,
    ) -> list[str]:
        """Generate reasons for match.

        Args:
            query: Search query
            tool: Matched tool
            semantic_score: Semantic similarity
            keyword_score: Keyword match score

        Returns:
            List of match reasons
        """
        reasons = []

        if semantic_score > 0.8:
            reasons.append("High semantic similarity to query")
        elif semantic_score > 0.6:
            reasons.append("Good semantic match")

        if keyword_score > 0.5:
            reasons.append("Strong keyword match")

        if tool.usage_count > 100:
            reasons.append("Frequently used tool")

        if tool.success_rate > 0.95:
            reasons.append("High success rate")

        return reasons or ["Relevant to query"]

    def _generate_recommendation_reason(
        self,
        tool: ToolDefinition,
        task: str,
        context: Optional[dict],
    ) -> str:
        """Generate recommendation reason.

        Args:
            tool: Recommended tool
            task: Task description
            context: Execution context

        Returns:
            Reason string
        """
        return f"{tool.name} is well-suited for {tool.category.value.replace('_', ' ')} tasks"

    def _generate_usage_hint(
        self,
        tool: ToolDefinition,
        context: Optional[dict],
    ) -> str:
        """Generate usage hint.

        Args:
            tool: Tool
            context: Execution context

        Returns:
            Usage hint
        """
        if tool.examples:
            return f"Example: {tool.examples[0].get('description', '')}"

        required_params = [p.name for p in tool.parameters if p.required]
        if required_params:
            return f"Required parameters: {', '.join(required_params)}"

        return ""

    def get_service_stats(self) -> dict:
        """Get service statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "indexed_tools": len(self._tools),
            "categories": len(self.get_categories()),
            "total_usage_records": sum(s["total"] for s in self._usage_stats.values()),
            "config": {
                "min_score": self.config.min_score,
                "embedding_weight": self.config.embedding_weight,
                "keyword_weight": self.config.keyword_weight,
            },
        }
