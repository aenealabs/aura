"""
Project Aura - Query Planning Agent

Analyzes user queries and generates optimal multi-strategy search plans
for hybrid GraphRAG + filesystem search.

Integrates with BedrockLLMService for production LLM calls.
Uses Chain of Draft (CoD) prompting for 92% token reduction (ADR-029 Phase 1.2).
"""

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    pass

# Import CoD prompts with fallback for testing
# Note: mypy static analysis assumes successful imports, so we silence unreachable warnings
try:
    from src.prompts.cod_templates import (  # type: ignore[unreachable]
        CoDPromptMode,
        build_cod_prompt,
        get_prompt_mode,
    )
except ImportError:  # type: ignore[unreachable]
    # Fallback for testing without full module structure
    CoDPromptMode: Optional[type] = None  # type: ignore[misc, no-redef]
    build_cod_prompt: Optional[Callable[..., str]] = None  # type: ignore[misc, no-redef]
    get_prompt_mode: Optional[Callable[[], Any]] = None  # type: ignore[misc, no-redef]

logger = logging.getLogger(__name__)


@dataclass
class SearchStrategy:
    """Defines a search strategy for context retrieval."""

    strategy_type: str  # "graph", "vector", "filesystem", "git"
    query: str  # Specific query to execute
    priority: int  # 1-10 (10 = highest)
    estimated_tokens: int  # Estimated token cost


class QueryPlanningAgent:
    """
    Analyzes queries and generates multi-strategy search plans.

    Uses LLM to understand query intent and select optimal combination of:
    - Graph search (Neptune): Structural queries (call graphs, dependencies)
    - Vector search (OpenSearch): Semantic similarity
    - Filesystem search: File patterns, metadata, recent changes
    - Git search: Commit history, blame data

    Example:
        Query: "Find all authentication code"
        Plan:
            1. Graph: Find functions calling auth APIs (priority: 10)
            2. Vector: Semantic search for "authentication" (priority: 9)
            3. Filesystem: Files matching *auth*.py (priority: 7)
            4. Git: Recent changes to auth modules (priority: 5)
    """

    def __init__(self, llm_client) -> None:
        """
        Initialize query planning agent.

        Args:
            llm_client: LLM client for query analysis
        """
        self.llm = llm_client
        logger.info("Initialized QueryPlanningAgent")

    async def plan_search(
        self, user_query: str, context_budget: int = 100000
    ) -> list[SearchStrategy]:
        """
        Generate multi-strategy search plan based on query intent.

        Args:
            user_query: Natural language query (e.g., "Find JWT validation code")
            context_budget: Available token budget for context

        Returns:
            List of SearchStrategy objects, ordered by priority
        """
        logger.info(f"Planning search for query: {user_query}")

        # Build LLM prompt for query analysis
        prompt = self._build_planning_prompt(user_query, context_budget)

        # Call LLM
        try:
            response = await self.llm.generate(prompt)
            strategies = self._parse_strategies(response)

            # Sort by priority, filter by budget
            strategies = sorted(strategies, key=lambda s: s.priority, reverse=True)
            strategies = self._fit_to_budget(strategies, context_budget)

            logger.info(
                f"Generated {len(strategies)} search strategies for query: {user_query}"
            )
            return strategies

        except Exception as e:
            logger.error(f"Failed to plan search: {e}")
            # Fallback to default strategy
            return self._default_strategy(user_query, context_budget)

    def _build_planning_prompt(self, user_query: str, context_budget: int) -> str:
        """Build LLM prompt for query planning using Chain of Draft (CoD).

        Uses CoD prompting for 92% token reduction while maintaining accuracy.
        ADR-029 Phase 1.2 implementation.
        """
        # Use CoD prompt if available, otherwise use fallback
        if build_cod_prompt is not None and get_prompt_mode is not None:
            prompt = build_cod_prompt(
                "query_planner",
                query=user_query,
                budget=context_budget,
            )
            logger.debug(f"Using CoD prompt mode: {get_prompt_mode().value}")
            return prompt

        # Fallback to traditional CoT prompt (mypy thinks this is unreachable, but it's not in tests)
        fallback_prompt: str  # type: ignore[unreachable]
        fallback_prompt = f"""You are a search query planner for a code intelligence system.

Given a user's code search query, generate an optimal multi-strategy search plan.

USER QUERY: "{user_query}"
CONTEXT BUDGET: {context_budget} tokens

AVAILABLE SEARCH STRATEGIES:

1. **Graph Search (Neptune)**
   - Purpose: Structural queries (call graphs, dependencies, inheritance)
   - Use when: Query involves relationships between code entities
   - Examples: "functions calling X", "dependencies of Y", "classes extending Z"
   - Cost: Low (typically 1000-5000 tokens per query)

2. **Vector Search (OpenSearch)**
   - Purpose: Semantic similarity search using embeddings
   - Use when: Query is conceptual or semantic in nature
   - Examples: "code similar to authentication", "error handling patterns"
   - Cost: Medium (typically 5000-10000 tokens per query)

3. **Filesystem Search (OpenSearch metadata)**
   - Purpose: File pattern matching, metadata filtering
   - Use when: Query involves file paths, recent changes, file properties
   - Examples: "files matching *auth*.py", "recently modified files", "test files"
   - Cost: Low (typically 1000-3000 tokens per query)

4. **Git Search (commit history)**
   - Purpose: Find files by commit history, authorship, recent changes
   - Use when: Query involves temporal aspects or code evolution
   - Examples: "files changed in last week", "code by author X", "commits fixing bug Y"
   - Cost: Low (typically 1000-2000 tokens per query)

TASK:
Generate a prioritized list of search strategies to answer the user's query.
For each strategy, provide:
- Strategy type (graph/vector/filesystem/git)
- Specific query to execute
- Priority (1-10, where 10 is highest)
- Estimated token cost

RESPOND IN JSON FORMAT:
{{
  "strategies": [
    {{
      "type": "graph",
      "query": "Find all functions calling authenticate()",
      "priority": 10,
      "estimated_tokens": 3000
    }},
    {{
      "type": "vector",
      "query": "Semantic search: authentication implementation",
      "priority": 9,
      "estimated_tokens": 8000
    }}
  ]
}}

Generate the search plan now:"""
        return fallback_prompt

    def _parse_strategies(self, llm_response: str) -> list[SearchStrategy]:
        """Parse LLM response into SearchStrategy objects."""
        try:
            # Extract JSON from response
            json_start = llm_response.find("{")
            json_end = llm_response.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in LLM response")

            json_str = llm_response[json_start:json_end]
            data = json.loads(json_str)

            strategies = []
            for item in data.get("strategies", []):
                strategies.append(
                    SearchStrategy(
                        strategy_type=item["type"],
                        query=item["query"],
                        priority=item["priority"],
                        estimated_tokens=item["estimated_tokens"],
                    )
                )

            return strategies

        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return []

    def _fit_to_budget(
        self, strategies: list[SearchStrategy], budget: int
    ) -> list[SearchStrategy]:
        """Filter strategies to fit within token budget."""
        selected = []
        used_tokens = 0

        for strategy in strategies:
            if used_tokens + strategy.estimated_tokens <= budget:
                selected.append(strategy)
                used_tokens += strategy.estimated_tokens
            else:
                logger.warning(
                    f"Skipping strategy due to budget: {strategy.strategy_type} "
                    f"(would exceed budget by {used_tokens + strategy.estimated_tokens - budget} tokens)"
                )

        return selected

    def _default_strategy(
        self, user_query: str, context_budget: int
    ) -> list[SearchStrategy]:
        """
        Fallback strategy when LLM planning fails.

        Default: Use all strategies with equal priority.
        Adjusts estimated tokens based on context_budget.
        """
        logger.warning(
            f"Using default search strategy (budget: {context_budget} tokens)"
        )

        # Adjust token estimates based on budget
        vector_tokens = min(8000, int(context_budget * 0.6))
        filesystem_tokens = min(2000, int(context_budget * 0.2))

        return [
            SearchStrategy(
                strategy_type="vector",
                query=f"Semantic search: {user_query}",
                priority=10,
                estimated_tokens=vector_tokens,
            ),
            SearchStrategy(
                strategy_type="filesystem",
                query=f"File pattern: *{user_query.split()[0]}*",
                priority=8,
                estimated_tokens=filesystem_tokens,
            ),
            SearchStrategy(
                strategy_type="graph",
                query=f"Related code entities: {user_query}",
                priority=7,
                estimated_tokens=5000,
            ),
        ]


# Factory function for production usage
def create_query_planning_agent(use_mock: bool = False) -> "QueryPlanningAgent":
    """
    Create a QueryPlanningAgent with real or mock LLM.

    Args:
        use_mock: If True, use mock LLM for testing. If False, use real Bedrock.

    Returns:
        Configured QueryPlanningAgent instance
    """
    if use_mock:
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = """
        {
          "strategies": [
            {"type": "vector", "query": "Semantic search: user query", "priority": 10, "estimated_tokens": 8000},
            {"type": "graph", "query": "Related code entities", "priority": 8, "estimated_tokens": 3000},
            {"type": "filesystem", "query": "File pattern match", "priority": 6, "estimated_tokens": 2000}
          ]
        }
        """
        return QueryPlanningAgent(llm_client=mock_llm)
    else:
        from src.services.bedrock_llm_service import create_llm_service

        llm_service = create_llm_service()
        return QueryPlanningAgent(llm_client=llm_service)


# Example usage
async def example_usage():
    """Example usage of QueryPlanningAgent with real Bedrock."""
    import os

    # Use mock if AURA_LLM_MOCK is set, otherwise use real Bedrock
    use_mock = os.environ.get("AURA_LLM_MOCK", "false").lower() == "true"

    print(f"Using {'mock' if use_mock else 'real Bedrock'} LLM")

    # Create agent
    agent = create_query_planning_agent(use_mock=use_mock)

    # Plan search
    strategies = await agent.plan_search(
        user_query="Find JWT authentication code", context_budget=50000
    )

    print(f"\nGenerated {len(strategies)} strategies:")
    for i, strategy in enumerate(strategies, 1):
        print(
            f"{i}. [{strategy.strategy_type}] {strategy.query} "
            f"(priority: {strategy.priority}, tokens: {strategy.estimated_tokens})"
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
