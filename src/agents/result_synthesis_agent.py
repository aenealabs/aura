"""
Project Aura - Result Synthesis Agent

Combines results from multiple search strategies and optimizes for context budget.
Implements intelligent ranking, deduplication, and token budget management.

Author: Project Aura Team
Created: 2025-11-18
Version: 1.0.0
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from src.agents.filesystem_navigator_agent import FileMatch

if TYPE_CHECKING:
    from src.services.bedrock_llm_service import BedrockLLMService

logger = logging.getLogger(__name__)

# Scoring constants
RECENT_DAYS_THRESHOLD = 7
MEDIUM_RECENT_DAYS_THRESHOLD = 30
OPTIMAL_FILE_MIN_LINES = 500
OPTIMAL_FILE_MAX_LINES = 2000
SMALL_FILE_MIN_LINES = 100
SMALL_FILE_MAX_LINES = 500
RECENCY_BOOST_RECENT = 3.0
RECENCY_BOOST_MEDIUM = 1.0
SIZE_BOOST_OPTIMAL = 2.0
SIZE_BOOST_SMALL = 1.0
SIZE_BOOST_LARGE = 0.5


@dataclass
class ContextResponse:
    """Represents synthesized context response."""

    files: list[FileMatch]
    total_tokens: int
    strategies_used: list[str]
    query: str = ""


class ResultSynthesisAgent:
    """
    Combines results from multiple search strategies and optimizes for context budget.

    Responsibilities:
    - Deduplicate files from multiple strategies
    - Rank by relevance (combined scores from graph + vector + filesystem)
    - Prioritize based on file metadata (recent changes, author frequency)
    - Fit results into available token budget

    Ranking algorithm:
    1. Boost files found by multiple strategies (high confidence)
    2. Prioritize recent changes (likely relevant to current work)
    3. Prioritize larger files (more comprehensive context)
    4. De-prioritize test/config files (unless explicitly requested)
    5. Boost files by frequent contributors (domain experts)

    Usage:
        synthesizer = ResultSynthesisAgent()

        response = synthesizer.synthesize(
            graph_results=[...],
            vector_results=[...],
            filesystem_results=[...],
            git_results=[...],
            context_budget=100000
        )
    """

    def __init__(self, llm_client: "BedrockLLMService | None" = None) -> None:
        """Initialize result synthesis agent.

        Args:
            llm_client: Optional LLM service for intelligent ranking.
                If not provided, only deterministic ranking is available.
        """
        self.llm_client = llm_client
        logger.info(
            f"Initialized ResultSynthesisAgent (LLM: {'enabled' if llm_client else 'disabled'})"
        )

    def synthesize(
        self,
        graph_results: list[FileMatch],
        vector_results: list[FileMatch],
        filesystem_results: list[FileMatch],
        git_results: list[FileMatch],
        context_budget: int,
        query: str = "",
    ) -> ContextResponse:
        """
        Combine and rank results from all search strategies.

        Args:
            graph_results: Results from Neptune graph search
            vector_results: Results from OpenSearch vector search
            filesystem_results: Results from filesystem pattern search
            git_results: Results from Git history search
            context_budget: Maximum tokens allowed
            query: Original user query

        Returns:
            ContextResponse with ranked files within budget
        """
        logger.info(
            f"Synthesizing results: graph={len(graph_results)}, "
            f"vector={len(vector_results)}, filesystem={len(filesystem_results)}, "
            f"git={len(git_results)}, budget={context_budget}"
        )

        # Deduplicate
        all_files = self._deduplicate(
            [*graph_results, *vector_results, *filesystem_results, *git_results]
        )

        logger.debug(f"After deduplication: {len(all_files)} unique files")

        # Score each file
        scored_files = []
        for file_match in all_files:
            score = self._calculate_composite_score(
                file_match,
                graph_results,
                vector_results,
                filesystem_results,
                git_results,
            )
            scored_files.append((file_match, score))

        # Sort by score descending
        scored_files.sort(key=lambda x: x[1], reverse=True)

        logger.debug(
            f"Top 5 files by score: "
            f"{[(f.file_path, s) for f, s in scored_files[:5]]}"
        )

        # Fit to budget
        selected_files = self._fit_to_budget(scored_files, context_budget)

        # Calculate strategies used
        strategies_used = []
        if graph_results:
            strategies_used.append("graph")
        if vector_results:
            strategies_used.append("vector")
        if filesystem_results:
            strategies_used.append("filesystem")
        if git_results:
            strategies_used.append("git")

        logger.info(
            f"Synthesis complete: selected {len(selected_files)} files, "
            f"total tokens: {sum(f.estimated_tokens for f in selected_files)}"
        )

        return ContextResponse(
            files=selected_files,
            total_tokens=sum(f.estimated_tokens for f in selected_files),
            strategies_used=strategies_used,
            query=query,
        )

    def _deduplicate(self, file_matches: list[FileMatch]) -> list[FileMatch]:
        """
        Deduplicate file matches by file_path.

        When duplicates exist, keep the one with highest relevance score.
        """
        seen: dict[str, FileMatch] = {}

        for match in file_matches:
            if (
                match.file_path not in seen
                or match.relevance_score > seen[match.file_path].relevance_score
            ):
                seen[match.file_path] = match

        return list(seen.values())

    def _calculate_composite_score(
        self,
        file_match: FileMatch,
        graph_results: list[FileMatch],
        vector_results: list[FileMatch],
        filesystem_results: list[FileMatch],
        git_results: list[FileMatch],
    ) -> float:
        """
        Calculate composite relevance score.

        Scoring factors:
        - Multi-strategy match: +5.0 per additional strategy
        - Base relevance score from searches: 0-10
        - Recent changes (< 7 days): +3.0
        - Recent changes (< 30 days): +1.0
        - Large file (> 500 lines): +2.0
        - Medium file (100-500 lines): +1.0
        - Core module (not test/config): +1.5
        - Multiple contributors (> 3): +1.0
        - Test/config file penalty: -1.0 / -0.5

        Args:
            file_match: File to score
            graph_results: All graph results
            vector_results: All vector results
            filesystem_results: All filesystem results
            git_results: All git results

        Returns:
            Composite score (higher = more relevant)
        """
        score = 0.0

        # Multi-strategy boost
        score += self._calculate_strategy_score(
            file_match, graph_results, vector_results, filesystem_results, git_results
        )

        # Recency boost
        score += self._calculate_recency_score(file_match)

        # Size boost
        score += self._calculate_size_score(file_match)

        # File type boost/penalty
        score += self._calculate_file_type_score(file_match)

        return score

    def _calculate_strategy_score(
        self,
        file_match: FileMatch,
        graph_results: list[FileMatch],
        vector_results: list[FileMatch],
        filesystem_results: list[FileMatch],
        git_results: list[FileMatch],
    ) -> float:
        """Calculate score based on multi-strategy matches."""
        score = 0.0
        strategies_found = 0

        if file_match in graph_results:
            strategies_found += 1
            score += file_match.relevance_score

        if file_match in vector_results:
            strategies_found += 1
            score += file_match.relevance_score

        if file_match in filesystem_results:
            strategies_found += 1

        if file_match in git_results:
            strategies_found += 1

        # Boost multi-strategy matches
        if strategies_found > 1:
            score += (strategies_found - 1) * 5.0

        return score

    def _calculate_recency_score(self, file_match: FileMatch) -> float:
        """Calculate score based on file modification recency."""
        # Handle both timezone-aware and naive datetimes
        now = datetime.now()
        if file_match.last_modified.tzinfo is not None:
            now = datetime.now(UTC)

        days_old = (now - file_match.last_modified).days
        if days_old < RECENT_DAYS_THRESHOLD:
            return RECENCY_BOOST_RECENT
        if days_old < MEDIUM_RECENT_DAYS_THRESHOLD:
            return RECENCY_BOOST_MEDIUM
        return 0.0

    def _calculate_size_score(self, file_match: FileMatch) -> float:
        """Calculate score based on file size (larger files = more context)."""
        if OPTIMAL_FILE_MIN_LINES < file_match.num_lines < OPTIMAL_FILE_MAX_LINES:
            return SIZE_BOOST_OPTIMAL
        if SMALL_FILE_MIN_LINES < file_match.num_lines <= SMALL_FILE_MAX_LINES:
            return SIZE_BOOST_SMALL
        if file_match.num_lines >= OPTIMAL_FILE_MAX_LINES:
            return SIZE_BOOST_LARGE
        return 0.0

    def _calculate_file_type_score(self, file_match: FileMatch) -> float:
        """Calculate score based on file type (core vs test/config)."""
        score = 0.0

        # Core module boost
        if not file_match.is_test_file and not file_match.is_config_file:
            score += 1.5

        # Penalize test/config files
        if file_match.is_test_file:
            score -= 1.0
        if file_match.is_config_file:
            score -= 0.5

        return score

    def _fit_to_budget(
        self, scored_files: list[tuple[FileMatch, float]], context_budget: int
    ) -> list[FileMatch]:
        """
        Select top files that fit within token budget.

        Uses greedy algorithm: select highest-scoring files until budget exhausted.

        Args:
            scored_files: List of (FileMatch, score) tuples, sorted by score desc
            context_budget: Maximum tokens allowed

        Returns:
            List of selected FileMatch objects
        """
        selected = []
        used_tokens = 0

        for file_match, _score in scored_files:
            if used_tokens + file_match.estimated_tokens <= context_budget:
                selected.append(file_match)
                used_tokens += file_match.estimated_tokens
            else:
                logger.debug(
                    f"Budget exhausted: skipping {file_match.file_path} "
                    f"(would use {used_tokens + file_match.estimated_tokens} tokens)"
                )

        logger.info(
            f"Selected {len(selected)} files using {used_tokens}/{context_budget} tokens "
            f"({used_tokens / context_budget * 100:.1f}% of budget)"
        )

        return selected

    async def synthesize_with_llm(
        self,
        graph_results: list[FileMatch],
        vector_results: list[FileMatch],
        filesystem_results: list[FileMatch],
        git_results: list[FileMatch],
        context_budget: int,
        query: str,
    ) -> ContextResponse:
        """
        Synthesize results using LLM-powered relevance ranking.

        This method uses an LLM to assess the semantic relevance of each file
        to the query, providing more nuanced ranking than deterministic scoring.

        Args:
            graph_results: Results from Neptune graph search
            vector_results: Results from OpenSearch vector search
            filesystem_results: Results from filesystem pattern search
            git_results: Results from Git history search
            context_budget: Maximum tokens allowed
            query: Original user query (required for LLM ranking)

        Returns:
            ContextResponse with LLM-ranked files within budget

        Raises:
            ValueError: If LLM client is not configured
        """
        if not self.llm_client:
            logger.warning(
                "LLM client not configured, falling back to deterministic ranking"
            )
            return self.synthesize(
                graph_results,
                vector_results,
                filesystem_results,
                git_results,
                context_budget,
                query,
            )

        logger.info(f"Synthesizing with LLM ranking for query: {query[:100]}...")

        # Deduplicate first
        all_files = self._deduplicate(
            [*graph_results, *vector_results, *filesystem_results, *git_results]
        )

        if not all_files:
            return ContextResponse(
                files=[], total_tokens=0, strategies_used=[], query=query
            )

        # Calculate base scores for all files (deterministic)
        scored_files = []
        for file_match in all_files:
            base_score = self._calculate_composite_score(
                file_match,
                graph_results,
                vector_results,
                filesystem_results,
                git_results,
            )
            scored_files.append((file_match, base_score))

        # Sort by base score and take top candidates for LLM ranking
        scored_files.sort(key=lambda x: x[1], reverse=True)
        top_candidates = scored_files[:20]  # Limit LLM calls

        # Get LLM relevance scores for top candidates
        llm_scores = await self._llm_rank_files(query, [f for f, _ in top_candidates])

        # Combine deterministic and LLM scores
        final_scored = []
        for file_match, base_score in top_candidates:
            llm_score = llm_scores.get(file_match.file_path, 0.0)
            # Weight: 40% deterministic, 60% LLM
            combined_score = (base_score * 0.4) + (llm_score * 10 * 0.6)
            final_scored.append((file_match, combined_score))

        # Add remaining files with their base scores (not LLM ranked)
        for file_match, base_score in scored_files[20:]:
            final_scored.append((file_match, base_score))

        # Sort by combined score
        final_scored.sort(key=lambda x: x[1], reverse=True)

        # Fit to budget
        selected_files = self._fit_to_budget(final_scored, context_budget)

        # Calculate strategies used
        strategies_used = []
        if graph_results:
            strategies_used.append("graph")
        if vector_results:
            strategies_used.append("vector")
        if filesystem_results:
            strategies_used.append("filesystem")
        if git_results:
            strategies_used.append("git")
        strategies_used.append("llm_ranking")

        logger.info(
            f"LLM synthesis complete: selected {len(selected_files)} files, "
            f"total tokens: {sum(f.estimated_tokens for f in selected_files)}"
        )

        return ContextResponse(
            files=selected_files,
            total_tokens=sum(f.estimated_tokens for f in selected_files),
            strategies_used=strategies_used,
            query=query,
        )

    async def _llm_rank_files(
        self, query: str, files: list[FileMatch]
    ) -> dict[str, float]:
        """
        Use LLM to rank files by relevance to query.

        Args:
            query: User's search query
            files: List of files to rank

        Returns:
            Dictionary mapping file_path to relevance score (0.0-1.0)
        """
        if not self.llm_client or not files:
            return {}

        # Build file list for LLM
        file_descriptions = []
        for i, f in enumerate(files):
            file_type = (
                "test" if f.is_test_file else "config" if f.is_config_file else "source"
            )
            file_descriptions.append(
                f"{i+1}. {f.file_path} ({f.language}, {f.num_lines} lines, {file_type})"
            )

        prompt = f"""You are a code search relevance ranker. Given a user query and a list of files,
score each file's relevance to the query on a scale of 0.0 to 1.0.

User Query: {query}

Files to rank:
{chr(10).join(file_descriptions)}

Return a JSON object mapping file paths to relevance scores. Example:
{{"src/auth/login.py": 0.95, "tests/test_login.py": 0.6}}

Consider:
- File path semantics (does the path suggest relevance to the query?)
- Language appropriateness (e.g., Python for a Python-related query)
- Source files vs test files (source usually more relevant unless query is about tests)
- File size (larger files may have more relevant content)

Return ONLY the JSON object, no explanation."""

        try:
            # Use ACCURATE tier (Sonnet) for security-relevant ranking (ADR-015)
            response = await self.llm_client.generate(
                prompt, max_tokens=1000, operation="security_result_scoring"
            )
            # Parse JSON response
            scores: dict[str, float] = cast(
                dict[str, float], json.loads(response.strip())
            )
            logger.debug(f"LLM ranking scores: {scores}")
            return scores
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM ranking response: {e}")
            return {}
        except Exception as e:
            logger.error(f"LLM ranking failed: {e}")
            return {}

    def explain_ranking(
        self,
        file_match: FileMatch,
        graph_results: list[FileMatch],
        vector_results: list[FileMatch],
        filesystem_results: list[FileMatch],
        git_results: list[FileMatch],
    ) -> dict[str, Any]:
        """
        Explain why a file received its score (for debugging/transparency).

        Args:
            file_match: File to explain
            graph_results: All graph results
            vector_results: All vector results
            filesystem_results: All filesystem results
            git_results: All git results

        Returns:
            Dictionary with scoring breakdown
        """
        explanation: dict[str, Any] = {
            "file_path": file_match.file_path,
            "final_score": self._calculate_composite_score(
                file_match,
                graph_results,
                vector_results,
                filesystem_results,
                git_results,
            ),
            "factors": {},
        }

        # Strategy matches
        explanation["factors"]["strategies"] = self._get_matching_strategies(
            file_match, graph_results, vector_results, filesystem_results, git_results
        )
        explanation["factors"]["multi_strategy_boost"] = (
            len(explanation["factors"]["strategies"]) - 1
        ) * 5.0

        # Recency explanation
        explanation["factors"]["recency"] = self._explain_recency_score(file_match)

        # Size explanation
        explanation["factors"]["size"] = self._explain_size_score(file_match)

        # File type explanation
        explanation["factors"]["file_type"] = self._explain_file_type_score(file_match)

        return explanation

    def _get_matching_strategies(
        self,
        file_match: FileMatch,
        graph_results: list[FileMatch],
        vector_results: list[FileMatch],
        filesystem_results: list[FileMatch],
        git_results: list[FileMatch],
    ) -> list[str]:
        """Get list of strategies that matched this file."""
        strategies = []
        if file_match in graph_results:
            strategies.append("graph")
        if file_match in vector_results:
            strategies.append("vector")
        if file_match in filesystem_results:
            strategies.append("filesystem")
        if file_match in git_results:
            strategies.append("git")
        return strategies

    def _explain_recency_score(self, file_match: FileMatch) -> str:
        """Generate explanation for recency score."""
        now = datetime.now()
        if file_match.last_modified.tzinfo is not None:
            now = datetime.now(UTC)

        days_old = (now - file_match.last_modified).days
        if days_old < RECENT_DAYS_THRESHOLD:
            return f"+{RECENCY_BOOST_RECENT} (< {RECENT_DAYS_THRESHOLD} days)"
        if days_old < MEDIUM_RECENT_DAYS_THRESHOLD:
            return f"+{RECENCY_BOOST_MEDIUM} (< {MEDIUM_RECENT_DAYS_THRESHOLD} days)"
        return f"0.0 (> {MEDIUM_RECENT_DAYS_THRESHOLD} days)"

    def _explain_size_score(self, file_match: FileMatch) -> str:
        """Generate explanation for size score."""
        if OPTIMAL_FILE_MIN_LINES < file_match.num_lines < OPTIMAL_FILE_MAX_LINES:
            return f"+{SIZE_BOOST_OPTIMAL} ({file_match.num_lines} lines)"
        if SMALL_FILE_MIN_LINES < file_match.num_lines <= SMALL_FILE_MAX_LINES:
            return f"+{SIZE_BOOST_SMALL} ({file_match.num_lines} lines)"
        return f"+{SIZE_BOOST_LARGE} ({file_match.num_lines} lines)"

    def _explain_file_type_score(self, file_match: FileMatch) -> str:
        """Generate explanation for file type score."""
        if file_match.is_test_file:
            return "-1.0 (test file)"
        if file_match.is_config_file:
            return "-0.5 (config file)"
        return "+1.5 (core module)"


# Example usage
async def example_usage():
    """Example usage of ResultSynthesisAgent."""
    # Create synthesizer
    synthesizer = ResultSynthesisAgent()

    # Mock results from different strategies
    graph_results = [
        FileMatch(
            file_path="src/services/auth_service.py",
            file_size=5000,
            last_modified=datetime.now() - timedelta(days=2),
            language="python",
            num_lines=250,
            relevance_score=9.5,
        ),
    ]

    vector_results = [
        FileMatch(
            file_path="src/services/auth_service.py",  # Duplicate (will be merged)
            file_size=5000,
            last_modified=datetime.now() - timedelta(days=2),
            language="python",
            num_lines=250,
            relevance_score=8.7,
        ),
        FileMatch(
            file_path="src/utils/jwt_validator.py",
            file_size=3000,
            last_modified=datetime.now() - timedelta(days=10),
            language="python",
            num_lines=150,
            relevance_score=7.2,
        ),
    ]

    filesystem_results = [
        FileMatch(
            file_path="tests/test_auth_service.py",
            file_size=2000,
            last_modified=datetime.now() - timedelta(days=5),
            language="python",
            num_lines=100,
            is_test_file=True,
            relevance_score=5.0,
        ),
    ]

    git_results = [
        FileMatch(
            file_path="src/services/auth_service.py",  # Another duplicate
            file_size=5000,
            last_modified=datetime.now() - timedelta(days=2),
            language="python",
            num_lines=250,
            relevance_score=6.0,
        ),
    ]

    # Synthesize
    response = synthesizer.synthesize(
        graph_results=graph_results,
        vector_results=vector_results,
        filesystem_results=filesystem_results,
        git_results=git_results,
        context_budget=10000,
        query="Find authentication code",
    )

    print("\nSynthesis Results:")
    print(f"Total files: {len(response.files)}")
    print(f"Total tokens: {response.total_tokens}")
    print(f"Strategies used: {', '.join(response.strategies_used)}")
    print("\nRanked files:")
    for i, file in enumerate(response.files, 1):
        print(
            f"{i}. {file.file_path} "
            f"(score: {file.relevance_score:.2f}, tokens: {file.estimated_tokens})"
        )

    # Explain ranking for top file
    if response.files:
        explanation = synthesizer.explain_ranking(
            response.files[0],
            graph_results,
            vector_results,
            filesystem_results,
            git_results,
        )
        print(f"\nRanking explanation for: {explanation['file_path']}")
        print(f"Final score: {explanation['final_score']:.2f}")
        print("Factors:")
        for factor, value in explanation["factors"].items():
            print(f"  {factor}: {value}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
