"""
Project Aura - Filesystem Navigator Agent

Intelligent filesystem exploration with adaptive search refinement.
Executes multi-hop file discovery using OpenSearch filesystem index.

Author: Project Aura Team
Created: 2025-11-18
Version: 1.0.0
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService

logger = logging.getLogger(__name__)

# Constants
MIN_TEXT_LENGTH_FOR_EMBEDDING = 3


@dataclass
class FileMatch:
    """Represents a matched file with metadata."""

    file_path: str
    file_size: int
    last_modified: datetime
    language: str
    num_lines: int
    last_author: str | None = None
    relevance_score: float = 0.0
    is_test_file: bool = False
    is_config_file: bool = False
    estimated_tokens: int = 0

    def __hash__(self):
        """Make FileMatch hashable for set operations."""
        return hash(self.file_path)

    def __eq__(self, other):
        """Compare FileMatch objects by file_path."""
        if isinstance(other, FileMatch):
            return self.file_path == other.file_path
        return False


class FilesystemNavigatorAgent:
    """
    Intelligent filesystem exploration with adaptive search refinement.

    Capabilities:
    - Pattern-based file discovery (glob, regex)
    - Directory structure analysis (monorepo vs microservice detection)
    - Related file discovery (tests, configs, dependencies)
    - Git-aware search (recent changes, blame data)
    - Semantic path search using embeddings

    Usage:
        navigator = FilesystemNavigatorAgent(
            opensearch_client=opensearch,
            embedding_service=embeddings,
            git_repo_path="/path/to/repo"
        )

        # Pattern search
        results = await navigator.search(
            pattern="**/auth/*.py",
            search_type="pattern",
            max_results=50
        )

        # Semantic search
        results = await navigator.search(
            pattern="authentication logic",
            search_type="semantic",
            max_results=50
        )
    """

    def __init__(
        self,
        opensearch_client,
        embedding_service,
        filesystem_index: str = "aura-filesystem-metadata",
        llm_client: "BedrockLLMService | None" = None,
    ):
        """
        Initialize filesystem navigator agent.

        Args:
            opensearch_client: OpenSearch client instance
            embedding_service: Service for generating embeddings
            filesystem_index: OpenSearch index name
            llm_client: Optional LLM service for intelligent query expansion
        """
        self.opensearch = opensearch_client
        self.embeddings = embedding_service
        self.filesystem_index = filesystem_index
        self.llm_client = llm_client

        logger.info(
            f"Initialized FilesystemNavigatorAgent (LLM: {'enabled' if llm_client else 'disabled'})"
        )

    async def search(
        self,
        pattern: str,
        search_type: str = "pattern",
        max_results: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> list[FileMatch]:
        """
        Search filesystem using various strategies.

        Args:
            pattern: Search pattern (glob, regex, or natural language)
            search_type: "pattern" | "semantic" | "recent_changes"
            max_results: Maximum files to return
            filters: Optional filters (language, is_test_file, etc.)

        Returns:
            List of FileMatch objects with metadata
        """
        logger.info(f"Searching filesystem: pattern={pattern}, type={search_type}")

        if search_type == "pattern":
            return await self._pattern_search(pattern, max_results, filters)
        if search_type == "semantic":
            return await self._semantic_search(pattern, max_results, filters)
        if search_type == "recent_changes":
            return await self._recent_changes_search(pattern, max_results, filters)
        raise ValueError(f"Unknown search type: {search_type}")

    async def _pattern_search(
        self,
        pattern: str,
        max_results: int,
        filters: dict[str, Any] | None = None,
    ) -> list[FileMatch]:
        """
        Pattern-based file search using OpenSearch filesystem index.

        Supports:
        - Glob patterns: "**/auth/*.py"
        - Wildcards: "test_*.py"
        - Path segments: "src/services/*"

        Args:
            pattern: Glob or wildcard pattern
            max_results: Maximum results to return
            filters: Additional filters

        Returns:
            List of FileMatch objects
        """
        # Build OpenSearch query
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "wildcard": {
                                "file_path.keyword": {
                                    "value": pattern,
                                    "case_insensitive": True,
                                }
                            }
                        }
                    ]
                }
            },
            "size": max_results,
            "sort": [
                {"last_modified": "desc"},  # Prefer recent files
                {"file_size": "desc"},  # Larger files likely more important
            ],
        }

        # Apply filters
        if filters:
            # Type assertion for mypy (query is a dict, safe to index)
            query["query"]["bool"]["filter"] = self._build_filters(filters)  # type: ignore[index]

        # Execute search
        response = await self.opensearch.search(index=self.filesystem_index, body=query)

        return [self._parse_file_match(hit) for hit in response["hits"]["hits"]]

    async def _semantic_search(
        self,
        query_text: str,
        max_results: int,
        filters: dict[str, Any] | None = None,
    ) -> list[FileMatch]:
        """
        Semantic search across file paths + docstrings.

        Uses KNN vector search on path and docstring embeddings.

        Args:
            query_text: Natural language query
            max_results: Maximum results
            filters: Additional filters

        Returns:
            List of FileMatch objects
        """
        # Generate query embedding
        query_embedding = await self._embed_text(query_text)

        # KNN search on path and docstring embeddings
        opensearch_query = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "script_score": {
                                "query": {"match_all": {}},
                                "script": {
                                    "source": "cosineSimilarity(params.query_vector, 'path_embedding') + 1.0",
                                    "params": {"query_vector": query_embedding},
                                },
                            }
                        },
                        {
                            "script_score": {
                                "query": {"match_all": {}},
                                "script": {
                                    "source": "cosineSimilarity(params.query_vector, 'docstring_embedding') + 1.0",
                                    "params": {"query_vector": query_embedding},
                                },
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            },
            "size": max_results,
        }

        # Apply filters
        if filters:
            # Type assertion for mypy (opensearch_query is a dict, safe to index)
            opensearch_query["query"]["bool"]["filter"] = self._build_filters(filters)  # type: ignore[index]

        response = await self.opensearch.search(
            index=self.filesystem_index, body=opensearch_query
        )

        return [self._parse_file_match(hit) for hit in response["hits"]["hits"]]

    async def _recent_changes_search(
        self,
        file_pattern: str,
        max_results: int,
        filters: dict[str, Any] | None = None,
        days: int = 30,
    ) -> list[FileMatch]:
        """
        Find files matching pattern that changed recently.

        Args:
            file_pattern: File pattern to match
            max_results: Maximum results
            filters: Additional filters
            days: Look back N days

        Returns:
            List of FileMatch objects
        """
        since_date = datetime.now() - timedelta(days=days)

        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "wildcard": {
                                "file_path.keyword": {
                                    "value": file_pattern,
                                    "case_insensitive": True,
                                }
                            }
                        },
                        {"range": {"last_modified": {"gte": since_date.isoformat()}}},
                    ]
                }
            },
            "size": max_results,
            "sort": [{"last_modified": "desc"}],
        }

        # Apply filters
        if filters:
            # Type assertion for mypy (query is a dict, safe to index)
            query["query"]["bool"]["filter"] = self._build_filters(filters)  # type: ignore[index]

        response = await self.opensearch.search(index=self.filesystem_index, body=query)

        return [self._parse_file_match(hit) for hit in response["hits"]["hits"]]

    async def find_related_files(self, file_path: str) -> dict[str, list[FileMatch]]:
        """
        Find files related to given file (tests, configs, dependencies).

        Discovery strategies:
        1. Test files: test_<filename>.py or <filename>_test.py
        2. Same module: Files in same directory
        3. Config files: *.yaml, *.json in config/ directories
        4. Imports: (requires graph search integration)

        Args:
            file_path: Path to file

        Returns:
            Dictionary with categories of related files
        """
        related: dict[str, list[FileMatch]] = {
            "tests": [],
            "same_module": [],
            "config": [],
        }

        path = Path(file_path)
        file_stem = path.stem

        # Find test files
        test_patterns = [
            f"**/test_{file_stem}.py",
            f"**/{file_stem}_test.py",
            f"**/tests/*{file_stem}*.py",
        ]

        for pattern in test_patterns:
            test_files = await self._pattern_search(pattern, max_results=10)
            related["tests"].extend(test_files)

        # Find files in same directory
        parent_dir = path.parent
        same_module_pattern = f"{parent_dir}/*.py"
        same_module_files = await self._pattern_search(
            same_module_pattern, max_results=20
        )
        related["same_module"] = same_module_files

        # Find config files
        config_patterns = ["**/config/**/*.yaml", "**/config/**/*.json"]

        for pattern in config_patterns:
            config_files = await self._pattern_search(pattern, max_results=5)
            related["config"].extend(config_files)

        # Deduplicate
        related["tests"] = list(set(related["tests"]))
        related["same_module"] = list(set(related["same_module"]))
        related["config"] = list(set(related["config"]))

        logger.info(
            f"Found {len(related['tests'])} test files, "
            f"{len(related['same_module'])} same-module files, "
            f"{len(related['config'])} config files for {file_path}"
        )

        return related

    async def intelligent_search(
        self,
        query: str,
        max_results: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> list[FileMatch]:
        """
        LLM-enhanced semantic search with query understanding.

        This method uses an LLM to:
        1. Understand the intent behind the query
        2. Generate expanded search terms and patterns
        3. Identify relevant file types and locations
        4. Rank results by semantic relevance

        Args:
            query: Natural language query (e.g., "find the authentication logic")
            max_results: Maximum files to return
            filters: Optional filters (language, is_test_file, etc.)

        Returns:
            List of FileMatch objects ranked by LLM-assessed relevance
        """
        if not self.llm_client:
            logger.warning(
                "LLM client not configured, falling back to basic semantic search"
            )
            return await self._semantic_search(query, max_results, filters)

        logger.info(f"Intelligent search for: {query}")

        # Step 1: Understand query intent and expand search terms
        search_plan = await self._analyze_query_intent(query)

        # Step 2: Execute multiple search strategies based on plan
        all_results: list[FileMatch] = []

        # Pattern searches
        for pattern in search_plan.get("patterns", []):
            try:
                results = await self._pattern_search(
                    pattern, max_results=20, filters=filters
                )
                all_results.extend(results)
            except Exception as e:
                logger.debug(f"Pattern search failed for {pattern}: {e}")

        # Semantic searches with expanded terms
        for term in search_plan.get("semantic_terms", [query]):
            try:
                results = await self._semantic_search(
                    term, max_results=20, filters=filters
                )
                all_results.extend(results)
            except Exception as e:
                logger.debug(f"Semantic search failed for {term}: {e}")

        # Deduplicate by file path
        seen: dict[str, FileMatch] = {}
        for match in all_results:
            if (
                match.file_path not in seen
                or match.relevance_score > seen[match.file_path].relevance_score
            ):
                seen[match.file_path] = match

        unique_results = list(seen.values())

        # Step 3: LLM-rank the results
        if unique_results:
            ranked_results = await self._llm_rank_results(
                query, unique_results, max_results
            )
            return ranked_results

        return unique_results[:max_results]

    async def _analyze_query_intent(self, query: str) -> dict[str, Any]:
        """
        Use LLM to understand query intent and generate search plan.

        Args:
            query: User's natural language query

        Returns:
            Search plan with patterns, semantic terms, and filters
        """
        if not self.llm_client:
            return {"semantic_terms": [query], "patterns": []}

        prompt = f"""Analyze this code search query and generate a search plan.

Query: "{query}"

Return a JSON object with:
1. "intent": Brief description of what the user is looking for
2. "patterns": List of glob patterns to try (e.g., "**/auth/*.py", "**/*login*")
3. "semantic_terms": List of semantic search terms to use
4. "file_types": List of likely file extensions (e.g., [".py", ".ts"])
5. "exclude_tests": Boolean - should test files be excluded?

Example response:
{{
  "intent": "Find authentication implementation code",
  "patterns": ["**/auth/**/*.py", "**/authentication/**/*", "**/*login*.py"],
  "semantic_terms": ["authentication", "user login", "session management", "JWT token"],
  "file_types": [".py"],
  "exclude_tests": true
}}

Return ONLY the JSON object, no explanation."""

        try:
            # Use FAST tier (Haiku) for query intent analysis (ADR-015)
            response = await self.llm_client.generate(
                prompt, max_tokens=500, operation="query_intent_analysis"
            )
            plan: dict[str, Any] = cast(dict[str, Any], json.loads(response.strip()))
            logger.debug(f"Query analysis: {plan}")
            return plan
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse query analysis: {e}")
            return {"semantic_terms": [query], "patterns": []}
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return {"semantic_terms": [query], "patterns": []}

    async def _llm_rank_results(
        self, query: str, results: list[FileMatch], max_results: int
    ) -> list[FileMatch]:
        """
        Use LLM to rank search results by relevance.

        Args:
            query: Original user query
            results: Unranked search results
            max_results: Maximum results to return

        Returns:
            Ranked list of FileMatch objects
        """
        if not self.llm_client or len(results) <= 1:
            return results[:max_results]

        # Limit to top 30 for LLM ranking
        candidates = results[:30]

        # Build file list for LLM
        file_list = []
        for i, f in enumerate(candidates):
            file_type = (
                "test" if f.is_test_file else "config" if f.is_config_file else "source"
            )
            file_list.append(
                f"{i+1}. {f.file_path} ({f.language}, {f.num_lines} lines, {file_type})"
            )

        prompt = f"""Rank these files by relevance to the query. Return the file numbers in order of relevance.

Query: "{query}"

Files:
{chr(10).join(file_list)}

Return a JSON array of file numbers in order of relevance (most relevant first).
Example: [3, 1, 5, 2, 4]

Return ONLY the JSON array, no explanation."""

        try:
            # Use ACCURATE tier (Sonnet) for security-relevant ranking (ADR-015)
            response = await self.llm_client.generate(
                prompt, max_tokens=200, operation="security_result_scoring"
            )
            ranking = json.loads(response.strip())

            # Reorder results based on LLM ranking
            ranked = []
            for idx in ranking:
                if isinstance(idx, int) and 1 <= idx <= len(candidates):
                    ranked.append(candidates[idx - 1])

            # Add any files not ranked by LLM
            ranked_paths = {f.file_path for f in ranked}
            for f in candidates:
                if f.file_path not in ranked_paths:
                    ranked.append(f)

            return ranked[:max_results]

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM ranking: {e}")
            return results[:max_results]
        except Exception as e:
            logger.error(f"LLM ranking failed: {e}")
            return results[:max_results]

    async def _embed_text(self, text: str) -> list[float]:
        """Generate embedding for text."""
        if not text or len(text) < MIN_TEXT_LENGTH_FOR_EMBEDDING:
            return [0.0] * 1536

        try:
            return await self.embeddings.generate_embedding(text)  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return [0.0] * 1536

    def _build_filters(self, filters: dict[str, Any]) -> list[dict]:
        """Build OpenSearch filter clauses from filter dictionary."""
        filter_clauses = []

        for key, value in filters.items():
            if key == "language":
                filter_clauses.append({"term": {"language": value}})
            elif key == "is_test_file":
                filter_clauses.append({"term": {"is_test_file": value}})
            elif key == "is_config_file":
                filter_clauses.append({"term": {"is_config_file": value}})
            elif key == "min_lines":
                filter_clauses.append({"range": {"num_lines": {"gte": value}}})
            elif key == "max_lines":
                filter_clauses.append({"range": {"num_lines": {"lte": value}}})

        return filter_clauses

    def _parse_file_match(self, opensearch_hit: dict) -> FileMatch:
        """Parse OpenSearch hit into FileMatch object."""
        source = opensearch_hit["_source"]

        # Parse datetime
        last_modified_str = source.get("last_modified")
        last_modified = (
            datetime.fromisoformat(last_modified_str.replace("Z", "+00:00"))
            if last_modified_str
            else datetime.now()
        )

        # Estimate tokens (rough: 1.5 tokens per line)
        num_lines = source.get("num_lines", 0)
        estimated_tokens = int(num_lines * 1.5)

        return FileMatch(
            file_path=source.get("file_path", ""),
            file_size=source.get("file_size", 0),
            last_modified=last_modified,
            language=source.get("language", "unknown"),
            num_lines=num_lines,
            last_author=source.get("last_author"),
            relevance_score=opensearch_hit.get("_score", 0.0),
            is_test_file=source.get("is_test_file", False),
            is_config_file=source.get("is_config_file", False),
            estimated_tokens=estimated_tokens,
        )


# Example usage
async def example_usage():
    """Example usage of FilesystemNavigatorAgent."""
    # Mock clients
    mock_opensearch = AsyncMock()
    mock_opensearch.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_score": 10.5,
                    "_source": {
                        "file_path": "src/services/auth_service.py",
                        "file_size": 5000,
                        "last_modified": "2025-11-18T10:00:00Z",
                        "language": "python",
                        "num_lines": 250,
                        "last_author": "alice@example.com",
                        "is_test_file": False,
                        "is_config_file": False,
                    },
                },
                {
                    "_score": 8.3,
                    "_source": {
                        "file_path": "src/utils/jwt_validator.py",
                        "file_size": 3000,
                        "last_modified": "2025-11-17T15:30:00Z",
                        "language": "python",
                        "num_lines": 150,
                        "last_author": "bob@example.com",
                        "is_test_file": False,
                        "is_config_file": False,
                    },
                },
            ]
        }
    }

    mock_embeddings = AsyncMock()
    mock_embeddings.generate_embedding.return_value = [0.1] * 1536

    # Create navigator
    navigator = FilesystemNavigatorAgent(
        opensearch_client=mock_opensearch, embedding_service=mock_embeddings
    )

    # Pattern search
    print("Pattern search: **/auth/*.py")
    results = await navigator.search(pattern="**/auth/*.py", search_type="pattern")
    print(f"Found {len(results)} files:")
    for match in results:
        print(f"  - {match.file_path} (score: {match.relevance_score:.2f})")

    # Semantic search
    print("\nSemantic search: authentication logic")
    results = await navigator.search(
        pattern="authentication logic", search_type="semantic"
    )
    print(f"Found {len(results)} files")

    # Find related files
    print("\nFinding related files for: src/services/auth_service.py")
    related = await navigator.find_related_files("src/services/auth_service.py")
    print(f"Tests: {len(related['tests'])}")
    print(f"Same module: {len(related['same_module'])}")
    print(f"Config: {len(related['config'])}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
