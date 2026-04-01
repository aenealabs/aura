"""
Project Aura - Context Retrieval Service

Enhanced context retrieval with agentic filesystem search.
Combines Neptune graph queries, OpenSearch vector search, and intelligent
filesystem navigation for optimal code context retrieval.

Author: Project Aura Team
Created: 2025-11-18
Version: 2.0.0 (with Agentic Search)
"""

import asyncio
import contextlib
import logging
import re
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Union
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService

from src.agents.filesystem_navigator_agent import FileMatch, FilesystemNavigatorAgent


class GraphQueryType(Enum):
    """Types of graph queries for structural code search."""

    CALL_GRAPH = "call_graph"  # Functions that call/are called by target
    DEPENDENCIES = "dependencies"  # Import relationships
    INHERITANCE = "inheritance"  # Class hierarchies
    REFERENCES = "references"  # All references to an entity
    RELATED = "related"  # General related entities


from src.agents.query_planning_agent import QueryPlanningAgent, SearchStrategy
from src.agents.result_synthesis_agent import ContextResponse, ResultSynthesisAgent

logger = logging.getLogger(__name__)


class ContextRetrievalService:
    """
    Enhanced context retrieval with agentic filesystem search.

    Combines:
    - Neptune graph queries (call graphs, dependencies)
    - OpenSearch vector search (semantic similarity)
    - Filesystem metadata search (paths, timestamps, git data)
    - Agentic orchestration (multi-strategy, adaptive refinement)

    Architecture:
        User Query
            ↓
        QueryPlanningAgent (LLM-powered strategy selection)
            ↓
        Parallel Execution:
            - Graph Search (Neptune)
            - Vector Search (OpenSearch)
            - Filesystem Search (FilesystemNavigatorAgent)
            - Git Search (FilesystemNavigatorAgent)
            ↓
        ResultSynthesisAgent (ranking, deduplication, budget fitting)
            ↓
        Optimized Context Response

    Usage:
        service = ContextRetrievalService(
            neptune_client=neptune,
            opensearch_client=opensearch,
            llm_client=bedrock,
            embedding_service=titan,
            git_repo_path="/path/to/repo"
        )

        context = await service.retrieve_context(
            query="Find JWT authentication code",
            context_budget=100000
        )
    """

    def __init__(
        self,
        neptune_client,
        opensearch_client,
        llm_client,
        embedding_service,
        git_repo_path: str,
    ):
        """
        Initialize context retrieval service.

        Args:
            neptune_client: Neptune graph database client
            opensearch_client: OpenSearch client
            llm_client: LLM client for query planning
            embedding_service: Embedding service (e.g., Titan)
            git_repo_path: Path to Git repository
        """
        self.neptune = neptune_client
        self.opensearch = opensearch_client

        # Initialize agentic search components with LLM client
        self.query_planner = QueryPlanningAgent(llm_client)
        self.fs_navigator = FilesystemNavigatorAgent(
            opensearch_client, embedding_service, llm_client=llm_client
        )
        self.result_synthesizer = ResultSynthesisAgent(llm_client=llm_client)

        logger.info(
            f"Initialized ContextRetrievalService with agentic search (repo: {git_repo_path})"
        )

    async def retrieve_context(
        self,
        query: str,
        context_budget: int = 100000,
        strategies: list[str] | None = None,
    ) -> ContextResponse:
        """
        Main entry point for context retrieval.

        Args:
            query: Natural language query (e.g., "Find JWT authentication code")
            context_budget: Maximum tokens for context (default: 100k)
            strategies: Optional list of strategies to use (auto-detect if None)

        Returns:
            ContextResponse with ranked files, metadata, and token count
        """
        logger.info(f"Retrieving context for query: {query} (budget: {context_budget})")

        # Step 1: Plan search strategies
        if strategies is None:
            search_plan = await self.query_planner.plan_search(query, context_budget)
        else:
            search_plan = self._manual_plan(query, strategies)

        logger.info(f"Generated search plan with {len(search_plan)} strategies")

        # Step 2: Execute searches in parallel
        graph_results, vector_results, filesystem_results, git_results = (
            await self._execute_parallel_searches(search_plan)
        )

        logger.info(
            f"Search results: graph={len(graph_results)}, vector={len(vector_results)}, "
            f"filesystem={len(filesystem_results)}, git={len(git_results)}"
        )

        # Step 3: Synthesize and rank results
        context_response = self.result_synthesizer.synthesize(
            graph_results,
            vector_results,
            filesystem_results,
            git_results,
            context_budget,
            query=query,
        )

        # Step 4: Fetch actual code content for top files (on-demand, not pre-fetched)

        logger.info(
            f"Context retrieval complete: {len(context_response.files)} files, "
            f"{context_response.total_tokens} tokens"
        )

        return context_response

    async def _execute_parallel_searches(
        self, search_plan: list[SearchStrategy]
    ) -> tuple[list[FileMatch], list[FileMatch], list[FileMatch], list[FileMatch]]:
        """
        Execute all search strategies in parallel.

        Args:
            search_plan: List of search strategies to execute

        Returns:
            Tuple of (graph_results, vector_results, filesystem_results, git_results)
        """
        # Initialize result collections
        graph_results: list[FileMatch] = []
        vector_results: list[FileMatch] = []
        filesystem_results: list[FileMatch] = []
        git_results: list[FileMatch] = []

        # Build task list
        tasks = self._build_search_tasks(search_plan)

        # Execute all searches in parallel
        results = await asyncio.gather(
            *[task for _, task in tasks], return_exceptions=True
        )

        # Process and categorize results
        self._categorize_search_results(
            tasks,
            results,
            graph_results,
            vector_results,
            filesystem_results,
            git_results,
        )

        return graph_results, vector_results, filesystem_results, git_results

    def _build_search_tasks(
        self, search_plan: list[SearchStrategy]
    ) -> list[tuple[str, Any]]:
        """Build list of search tasks from plan."""
        tasks = []
        for strategy in search_plan:
            if strategy.strategy_type == "graph":
                tasks.append(("graph", self._graph_search(strategy.query)))
            elif strategy.strategy_type == "vector":
                tasks.append(("vector", self._vector_search(strategy.query)))
            elif strategy.strategy_type == "filesystem":
                tasks.append(("filesystem", self._filesystem_search(strategy.query)))
            elif strategy.strategy_type == "git":
                tasks.append(("git", self._git_search(strategy.query)))
        return tasks

    def _categorize_search_results(
        self,
        tasks: list[tuple[str, Any]],
        results: list,
        graph_results: list[FileMatch],
        vector_results: list[FileMatch],
        filesystem_results: list[FileMatch],
        git_results: list[FileMatch],
    ) -> None:
        """Categorize search results by strategy type."""
        for i, (strategy_type, _) in enumerate(tasks):
            result = results[i]

            # Handle exceptions
            if isinstance(result, Exception):
                logger.error(f"Search failed for {strategy_type}: {result}")
                continue

            # Type guard: result is now known to be list[FileMatch]
            if not isinstance(result, list):
                logger.warning(
                    f"Unexpected result type for {strategy_type}: {type(result)}"
                )
                continue

            # Categorize by type (modifies lists in place)
            if strategy_type == "graph":
                graph_results.extend(result)
            elif strategy_type == "vector":
                vector_results.extend(result)
            elif strategy_type == "filesystem":
                filesystem_results.extend(result)
            elif strategy_type == "git":
                git_results.extend(result)

    async def _graph_search(self, query: str) -> list[FileMatch]:
        """
        Query Neptune for structural relationships.

        Searches for code entities and their structural relationships:
        - Call graphs: Functions that call/are called by target functions
        - Dependencies: Import/require relationships between modules
        - Inheritance: Class hierarchies and interface implementations
        - References: All references to a specific entity

        Args:
            query: Natural language query describing what to find

        Returns:
            List of FileMatch objects from graph traversal results
        """
        logger.debug(f"Executing graph search: {query}")

        try:
            # Extract key terms from query (likely function/class names)
            key_terms = self._extract_graph_terms(query)
            if not key_terms:
                logger.debug("No graph terms extracted from query")
                return []

            # Detect query type from natural language
            query_type = self._detect_graph_query_type(query)

            # Execute appropriate graph query
            graph_results = await self._execute_graph_query(
                key_terms, query_type, max_results=50
            )

            # Convert to FileMatch objects
            file_matches = self._convert_graph_results_to_file_matches(graph_results)

            logger.info(
                f"Graph search found {len(file_matches)} results for query type "
                f"{query_type.value} with terms: {key_terms[:3]}"
            )
            return file_matches

        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return []

    def _extract_graph_terms(self, query: str) -> list[str]:
        """
        Extract entity names suitable for graph traversal.

        Identifies likely code entity names from the query:
        - CamelCase words (class names)
        - snake_case words (function names)
        - Quoted strings
        - Words following "function", "class", "method", etc.

        Args:
            query: Natural language query

        Returns:
            List of extracted terms for graph search
        """
        terms = []

        # Extract quoted strings first
        quoted = re.findall(r'["\']([^"\']+)["\']', query)
        terms.extend(quoted)

        # Extract CamelCase words (likely class names)
        camel_case = re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", query)
        terms.extend(camel_case)

        # Extract snake_case words (likely function names)
        snake_case = re.findall(r"\b([a-z]+(?:_[a-z]+)+)\b", query)
        terms.extend(snake_case)

        # Extract words following entity indicators
        entity_patterns = [
            r"(?:function|method|def)\s+(\w+)",
            r"(?:class|type)\s+(\w+)",
            r"(?:module|import|from)\s+(\w+)",
            r"(?:calls?|calling)\s+(\w+)",
            r"(?:extends?|inherits?)\s+(\w+)",
        ]
        for pattern in entity_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            terms.extend(matches)

        # Extract capitalized words that might be class names
        capitalized = re.findall(r"\b([A-Z][a-zA-Z0-9]+)\b", query)
        for word in capitalized:
            # Filter out common non-entity words
            if word.lower() not in {
                "find",
                "get",
                "show",
                "list",
                "the",
                "all",
                "what",
                "how",
                "where",
                "which",
            }:
                terms.append(word)

        # Deduplicate while preserving order
        seen = set()
        unique_terms = []
        for term in terms:
            if term.lower() not in seen and len(term) > 2:
                seen.add(term.lower())
                unique_terms.append(term)

        return unique_terms[:10]  # Limit to prevent expensive queries

    def _detect_graph_query_type(self, query: str) -> GraphQueryType:
        """
        Detect the type of graph query from natural language.

        Args:
            query: Natural language query

        Returns:
            GraphQueryType enum value
        """
        query_lower = query.lower()

        # Check for call graph indicators
        if any(
            kw in query_lower
            for kw in ["call", "calls", "calling", "invokes", "invoked by", "uses"]
        ):
            return GraphQueryType.CALL_GRAPH

        # Check for dependency indicators
        if any(
            kw in query_lower
            for kw in ["import", "imports", "depends", "dependency", "require", "from"]
        ):
            return GraphQueryType.DEPENDENCIES

        # Check for inheritance indicators
        if any(
            kw in query_lower
            for kw in [
                "extend",
                "extends",
                "inherits",
                "subclass",
                "parent",
                "child",
                "hierarchy",
            ]
        ):
            return GraphQueryType.INHERITANCE

        # Check for reference indicators
        if any(
            kw in query_lower
            for kw in ["reference", "references", "used by", "where is", "find all"]
        ):
            return GraphQueryType.REFERENCES

        # Default to general related search
        return GraphQueryType.RELATED

    async def _execute_graph_query(
        self,
        terms: list[str],
        query_type: GraphQueryType,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Execute Gremlin query against Neptune.

        Args:
            terms: Entity names to search for
            query_type: Type of structural query
            max_results: Maximum number of results

        Returns:
            List of entity dictionaries from graph
        """
        if not terms:
            return []

        results = []

        # Try to use Neptune client methods if available
        if hasattr(self.neptune, "find_related_code"):
            # Use NeptuneGraphService API
            relationship_types = self._get_relationship_types(query_type)

            for term in terms[:5]:  # Limit terms to prevent slow queries
                try:
                    related = self.neptune.find_related_code(
                        entity_name=term,
                        max_depth=2,
                        relationship_types=relationship_types,
                    )
                    results.extend(related)
                except Exception as e:
                    logger.warning(f"Graph query failed for term '{term}': {e}")

            # Also search by name pattern
            if hasattr(self.neptune, "search_by_name"):
                for term in terms[:3]:
                    try:
                        matches = self.neptune.search_by_name(
                            name_pattern=term, limit=max_results // len(terms)
                        )
                        results.extend(matches)
                    except Exception as e:
                        logger.warning(f"Name search failed for term '{term}': {e}")

        elif hasattr(self.neptune, "execute"):
            # Use raw Gremlin execution
            gremlin_query = self._build_gremlin_query(terms, query_type, max_results)
            try:
                raw_results = await self.neptune.execute(gremlin_query)
                results = self._parse_gremlin_results(raw_results)
            except Exception as e:
                logger.warning(f"Gremlin query execution failed: {e}")

        # Deduplicate by entity_id or file_path
        seen = set()
        unique_results = []
        for r in results:
            key = r.get("id") or r.get("entity_id") or r.get("file_path", "")
            if key and key not in seen:
                seen.add(key)
                unique_results.append(r)

        return unique_results[:max_results]

    def _get_relationship_types(self, query_type: GraphQueryType) -> list[str] | None:
        """Get Neptune relationship types for a query type."""
        # Use string keys to avoid pytest-forked enum identity issues
        relationship_map: dict[str, list[str] | None] = {
            "call_graph": ["CALLS", "CALLED_BY"],
            "dependencies": ["IMPORTS", "DEPENDS_ON", "REQUIRES"],
            "inheritance": ["EXTENDS", "IMPLEMENTS", "INHERITS"],
            "references": None,  # All relationships
            "related": None,  # All relationships
        }
        return relationship_map.get(query_type.value)

    def _build_gremlin_query(
        self, terms: list[str], query_type: GraphQueryType, limit: int
    ) -> str:
        """
        Build a Gremlin query string for Neptune.

        Args:
            terms: Entity names to search
            query_type: Type of structural query
            limit: Maximum results

        Returns:
            Gremlin query string
        """
        # Escape terms for Gremlin (escape single quotes with backslash)
        escaped_terms = ", ".join(
            f"'{t.replace(chr(39), chr(92) + chr(39))}'" for t in terms
        )

        # Base query - find vertices matching terms
        base_query = f"g.V().has('name', within({escaped_terms}))"

        # Add traversal based on query type (use .value to avoid enum identity issues)
        if query_type.value == "call_graph":
            traversal = ".union(identity(), both('CALLS').dedup())"
        elif query_type.value == "dependencies":
            traversal = ".union(identity(), out('IMPORTS', 'DEPENDS_ON').dedup())"
        elif query_type.value == "inheritance":
            traversal = ".union(identity(), both('EXTENDS', 'IMPLEMENTS').dedup())"
        else:
            # General traversal for REFERENCES and RELATED
            traversal = ".union(identity(), both().dedup())"

        # Complete query with projection
        query = f"""
        {base_query}
        {traversal}
        .dedup()
        .limit({limit})
        .project('id', 'name', 'type', 'file_path', 'line_number')
            .by(id())
            .by(coalesce(values('name'), constant('')))
            .by(coalesce(values('type'), constant('')))
            .by(coalesce(values('file_path'), constant('')))
            .by(coalesce(values('line_number'), constant(0)))
        """

        return query.strip()

    def _parse_gremlin_results(self, raw_results: list) -> list[dict[str, Any]]:
        """Parse raw Gremlin results into entity dictionaries."""
        parsed = []
        for item in raw_results:
            if isinstance(item, dict):
                parsed.append(
                    {
                        "id": item.get("id", ""),
                        "name": item.get("name", ""),
                        "type": item.get("type", ""),
                        "file_path": item.get("file_path", ""),
                        "line_number": item.get("line_number", 0),
                    }
                )
        return parsed

    def _convert_graph_results_to_file_matches(
        self, graph_results: list[dict[str, Any]]
    ) -> list[FileMatch]:
        """
        Convert Neptune graph results to FileMatch objects.

        Args:
            graph_results: List of entity dictionaries from Neptune

        Returns:
            List of FileMatch objects for result synthesis
        """
        file_matches: list[FileMatch] = []
        seen_paths: set[str] = set()

        for entity in graph_results:
            file_path = entity.get("file_path", "")
            if not file_path or file_path in seen_paths:
                continue

            seen_paths.add(file_path)

            # Determine language from file extension
            language = self._detect_language(file_path)

            # Create FileMatch with available data
            # Note: Some fields will have default values since Neptune
            # stores entity-level data, not full file metadata
            file_match = FileMatch(
                file_path=file_path,
                file_size=0,  # Not stored in graph
                last_modified=datetime.now(timezone.utc),
                language=language,
                num_lines=0,  # Not stored in graph
                last_author=None,
                relevance_score=0.85,  # High score for structural matches
                is_test_file="test" in file_path.lower(),
                is_config_file=any(
                    cfg in file_path.lower()
                    for cfg in ["config", "settings", ".env", ".yaml", ".yml", ".json"]
                ),
                estimated_tokens=0,
            )
            file_matches.append(file_match)

        return file_matches

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file path."""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".sh": "shell",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".sql": "sql",
            ".md": "markdown",
        }

        for ext, lang in extension_map.items():
            if file_path.endswith(ext):
                return lang

        return "unknown"

    async def _vector_search(self, query: str) -> list[FileMatch]:
        """
        Query OpenSearch for semantic similarity.

        Uses KNN vector search on code embeddings.

        Args:
            query: Semantic search query

        Returns:
            List of FileMatch objects
        """
        logger.debug(f"Executing vector search: {query}")

        try:
            # Use filesystem navigator's semantic search
            # (which searches both path and docstring embeddings)
            result = await self.fs_navigator.search(
                pattern=query, search_type="semantic", max_results=50
            )
            return result

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def _filesystem_search(self, query: str) -> list[FileMatch]:
        """
        Query filesystem metadata.

        Supports:
        - Glob patterns: "**/auth/*.py"
        - File property filters: language=python, is_test_file=false
        - Path hierarchy search

        Args:
            query: Filesystem search query

        Returns:
            List of FileMatch objects
        """
        logger.debug(f"Executing filesystem search: {query}")

        try:
            result = await self.fs_navigator.search(
                pattern=query, search_type="pattern", max_results=50
            )
            return result

        except Exception as e:
            logger.error(f"Filesystem search failed: {e}")
            return []

    async def _git_search(self, query: str) -> list[FileMatch]:
        """
        Query Git history for recent changes.

        Args:
            query: Git search query (e.g., "files changed in last 30 days matching *auth*")

        Returns:
            List of FileMatch objects
        """
        logger.debug(f"Executing git search: {query}")

        try:
            # Extract pattern and days from query (simple parsing)
            # In production, this would use LLM to parse the query
            pattern = "*"  # Default to all files

            if "last" in query.lower():
                # Try to extract number of days
                words = query.lower().split()
                for i, word in enumerate(words):
                    if word == "last" and i + 1 < len(words):
                        with contextlib.suppress(ValueError):
                            int(words[i + 1])

            result = await self.fs_navigator.search(
                pattern=pattern, search_type="recent_changes", max_results=30
            )
            return result

        except Exception as e:
            logger.error(f"Git search failed: {e}")
            return []

    def _manual_plan(self, query: str, strategies: list[str]) -> list[SearchStrategy]:
        """
        Create manual search plan from strategy list (fallback when LLM unavailable).

        Args:
            query: User query
            strategies: List of strategy types to use

        Returns:
            List of SearchStrategy objects
        """
        plan = []

        if "graph" in strategies:
            plan.append(
                SearchStrategy(
                    strategy_type="graph",
                    query=f"Related code entities: {query}",
                    priority=8,
                    estimated_tokens=5000,
                )
            )

        if "vector" in strategies:
            plan.append(
                SearchStrategy(
                    strategy_type="vector",
                    query=f"Semantic search: {query}",
                    priority=10,
                    estimated_tokens=8000,
                )
            )

        if "filesystem" in strategies:
            plan.append(
                SearchStrategy(
                    strategy_type="filesystem",
                    query=f"*{query.split()[0]}*" if query else "*",
                    priority=7,
                    estimated_tokens=2000,
                )
            )

        if "git" in strategies:
            plan.append(
                SearchStrategy(
                    strategy_type="git",
                    query=f"Recent changes matching: {query}",
                    priority=6,
                    estimated_tokens=1500,
                )
            )

        return plan


def create_context_retrieval_service(
    neptune_client=None,
    opensearch_client=None,
    embedding_service=None,
    git_repo_path: str = ".",
    use_mock: bool = False,
) -> ContextRetrievalService:
    """
    Factory function to create ContextRetrievalService with real Bedrock LLM.

    This wires all agents (QueryPlanningAgent, FilesystemNavigatorAgent,
    ResultSynthesisAgent) to the real Bedrock LLM service.

    Args:
        neptune_client: Neptune graph client (optional, creates mock if None)
        opensearch_client: OpenSearch client (optional, creates mock if None)
        embedding_service: Embedding service (optional, creates mock if None)
        git_repo_path: Path to Git repository
        use_mock: If True, use mock LLM instead of real Bedrock

    Returns:
        Fully configured ContextRetrievalService with LLM-powered agents

    Example:
        # Production usage with real Bedrock
        service = create_context_retrieval_service(
            neptune_client=neptune,
            opensearch_client=opensearch,
            embedding_service=titan,
            git_repo_path="/path/to/repo"
        )

        context = await service.retrieve_context("Find JWT auth code")
    """
    from unittest.mock import AsyncMock

    # Create or use provided clients
    neptune = neptune_client or AsyncMock()
    opensearch = opensearch_client or AsyncMock()
    embeddings = embedding_service or AsyncMock()

    # Get LLM client
    llm_client: Union[AsyncMock, "BedrockLLMService"]
    if use_mock:
        llm_client = AsyncMock()
        llm_client.generate.return_value = '{"strategies": []}'
        logger.info("Created ContextRetrievalService with MOCK LLM")
    else:
        from src.services.bedrock_llm_service import create_llm_service

        llm_client = create_llm_service()
        logger.info("Created ContextRetrievalService with REAL Bedrock LLM")

    return ContextRetrievalService(
        neptune_client=neptune,
        opensearch_client=opensearch,
        llm_client=llm_client,
        embedding_service=embeddings,
        git_repo_path=git_repo_path,
    )


# Example usage
async def example_usage():
    """Example usage of ContextRetrievalService."""
    # Mock clients
    mock_neptune = AsyncMock()
    mock_opensearch = AsyncMock()
    mock_llm = AsyncMock()
    mock_embeddings = AsyncMock()

    # Mock LLM response for query planning
    mock_llm.generate.return_value = """
    {
      "strategies": [
        {
          "type": "vector",
          "query": "Semantic search: JWT authentication implementation",
          "priority": 10,
          "estimated_tokens": 8000
        },
        {
          "type": "filesystem",
          "query": "*auth*.py",
          "priority": 8,
          "estimated_tokens": 2000
        }
      ]
    }
    """

    # Mock OpenSearch responses
    mock_opensearch.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_score": 9.5,
                    "_source": {
                        "file_path": "src/services/auth_service.py",
                        "file_size": 5000,
                        "last_modified": "2025-11-18T10:00:00Z",
                        "language": "python",
                        "num_lines": 250,
                        "is_test_file": False,
                        "is_config_file": False,
                    },
                }
            ]
        }
    }

    mock_embeddings.generate_embedding.return_value = [0.1] * 1536

    # Create service
    service = ContextRetrievalService(
        neptune_client=mock_neptune,
        opensearch_client=mock_opensearch,
        llm_client=mock_llm,
        embedding_service=mock_embeddings,
        git_repo_path="/path/to/repo",
    )

    # Retrieve context
    context = await service.retrieve_context(
        query="Find JWT authentication code", context_budget=50000
    )

    print("\nContext Retrieval Results:")
    print(f"Query: {context.query}")
    print(f"Files found: {len(context.files)}")
    print(f"Total tokens: {context.total_tokens}")
    print(f"Strategies used: {', '.join(context.strategies_used)}")
    print("\nTop files:")
    for i, file in enumerate(context.files[:5], 1):
        print(f"{i}. {file.file_path} ({file.estimated_tokens} tokens)")


if __name__ == "__main__":
    asyncio.run(example_usage())
