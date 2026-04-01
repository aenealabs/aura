"""
Project Aura - Parallel Query Executor (ADR-028 Phase 3)

Executes decomposed subqueries in parallel with intelligent result
aggregation and relevance ranking.

Supports both local async execution and AWS Step Functions for
complex multi-hop workflows.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.services.otel_instrumentation import (
    record_agent_invocation,
    trace_agent_execution,
    trace_tool_call,
)
from src.services.query_analyzer import QueryDecomposition, SubQuery

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution mode for parallel queries."""

    LOCAL = "local"  # asyncio.gather for simple parallel
    STEP_FUNCTIONS = "step_functions"  # AWS Step Functions for complex workflows


@dataclass
class SubQueryResult:
    """Result from a single subquery execution."""

    subquery_id: str
    query_text: str
    search_type: str
    results: list[Any]  # FileMatch objects or similar
    execution_time_ms: float
    tokens_used: int
    error: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class AggregatedResult:
    """Aggregated results from all subqueries."""

    original_query: str
    total_results: int
    unique_files: int
    ranked_results: list[Any]  # Deduplicated and ranked FileMatch objects
    subquery_results: list[SubQueryResult]
    total_execution_time_ms: float
    total_tokens_used: int
    relevance_scores: dict[str, float]  # file_path -> relevance score
    execution_mode: ExecutionMode


class ParallelQueryExecutor:
    """
    Executes decomposed subqueries in parallel with result aggregation.

    Features:
    - Async parallel execution of independent subqueries
    - Dependency-aware sequential execution when required
    - Intelligent result deduplication and ranking
    - Token budget enforcement
    - Execution metrics and tracing

    Example:
        executor = ParallelQueryExecutor(
            neptune_client=neptune,
            opensearch_client=opensearch,
            fs_navigator=fs_nav
        )

        results = await executor.execute(
            decomposition=query_decomposition,
            context_budget=50000
        )
    """

    def __init__(
        self,
        neptune_client: Any,
        opensearch_client: Any,
        fs_navigator: Any,
        step_functions_client: Any | None = None,
        state_machine_arn: str | None = None,
    ):
        """
        Initialize parallel query executor.

        Args:
            neptune_client: Neptune graph database client
            opensearch_client: OpenSearch client for vector search
            fs_navigator: FilesystemNavigatorAgent for file searches
            step_functions_client: Optional AWS Step Functions client
            state_machine_arn: ARN of Step Functions state machine
        """
        self.neptune = neptune_client
        self.opensearch = opensearch_client
        self.fs_navigator = fs_navigator
        self.sfn_client = step_functions_client
        self.state_machine_arn = state_machine_arn

        logger.info("Initialized ParallelQueryExecutor")

    async def execute(
        self,
        decomposition: QueryDecomposition,
        context_budget: int = 100000,
        execution_mode: ExecutionMode = ExecutionMode.LOCAL,
    ) -> AggregatedResult:
        """
        Execute all subqueries and aggregate results.

        Args:
            decomposition: Query decomposition with subqueries
            context_budget: Maximum tokens for results
            execution_mode: Local async or Step Functions

        Returns:
            AggregatedResult with ranked, deduplicated results
        """
        start_time = time.time()

        with trace_agent_execution(
            "ParallelQueryExecutor",
            "execute",
            attributes={"subquery_count": len(decomposition.subqueries)},
        ):
            if execution_mode == ExecutionMode.STEP_FUNCTIONS and self.sfn_client:
                subquery_results = await self._execute_with_step_functions(
                    decomposition
                )
            else:
                subquery_results = await self._execute_local(decomposition)

            # Aggregate and rank results
            aggregated = self._aggregate_results(
                decomposition.original_query,
                subquery_results,
                context_budget,
                execution_mode,
            )

            total_time = (time.time() - start_time) * 1000
            aggregated.total_execution_time_ms = total_time

            # Record metrics
            record_agent_invocation(
                "ParallelQueryExecutor",
                "execute",
                total_time,
                success=not any(r.error for r in subquery_results),
            )

            logger.info(
                f"Executed {len(subquery_results)} subqueries in {total_time:.0f}ms, "
                f"found {aggregated.unique_files} unique files"
            )

            return aggregated

    async def _execute_local(
        self,
        decomposition: QueryDecomposition,
    ) -> list[SubQueryResult]:
        """
        Execute subqueries using local asyncio.gather.

        Handles dependencies by executing in phases.
        """
        # Group subqueries by dependency level
        execution_phases = self._plan_execution_phases(decomposition.subqueries)

        all_results: list[SubQueryResult] = []
        completed_results: dict[str, SubQueryResult] = {}

        for phase_num, phase_subqueries in enumerate(execution_phases):
            logger.debug(
                f"Executing phase {phase_num + 1}: {len(phase_subqueries)} subqueries"
            )

            # Execute all subqueries in this phase in parallel
            tasks = [
                self._execute_subquery(sq, completed_results) for sq in phase_subqueries
            ]

            phase_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for sq, result in zip(phase_subqueries, phase_results):
                if isinstance(result, Exception):
                    error_result = SubQueryResult(
                        subquery_id=sq.id,
                        query_text=sq.query_text,
                        search_type=sq.search_type,
                        results=[],
                        execution_time_ms=0,
                        tokens_used=0,
                        error=str(result),
                    )
                    all_results.append(error_result)
                    completed_results[sq.id] = error_result
                elif isinstance(result, SubQueryResult):
                    all_results.append(result)
                    completed_results[sq.id] = result

        return all_results

    def _plan_execution_phases(
        self,
        subqueries: list[SubQuery],
    ) -> list[list[SubQuery]]:
        """
        Plan execution phases based on dependencies.

        Returns list of phases, where each phase contains independent subqueries.
        """
        remaining = {sq.id: sq for sq in subqueries}
        completed: set[str] = set()
        phases: list[list[SubQuery]] = []

        while remaining:
            # Find subqueries with all dependencies satisfied
            ready = [
                sq
                for sq in remaining.values()
                if all(dep in completed for dep in sq.depends_on)
            ]

            if not ready:
                # Circular dependency or missing dependency - break cycle
                logger.warning(
                    "Breaking dependency cycle, executing remaining subqueries"
                )
                ready = list(remaining.values())

            # Sort by priority within phase
            ready.sort(key=lambda sq: sq.priority, reverse=True)
            phases.append(ready)

            # Mark as completed
            for sq in ready:
                completed.add(sq.id)
                del remaining[sq.id]

        return phases

    async def _execute_subquery(
        self,
        subquery: SubQuery,
        completed_results: dict[str, SubQueryResult],
    ) -> SubQueryResult:
        """Execute a single subquery."""
        start_time = time.time()

        with trace_tool_call(
            subquery.search_type, {"query": subquery.query_text[:100]}
        ):
            try:
                # Route to appropriate search backend
                if subquery.search_type == "graph":
                    results = await self._graph_search(subquery.query_text)
                elif subquery.search_type == "vector":
                    results = await self._vector_search(subquery.query_text)
                elif subquery.search_type == "filesystem":
                    results = await self._filesystem_search(subquery.query_text)
                elif subquery.search_type == "git":
                    results = await self._git_search(subquery.query_text)
                else:
                    results = await self._vector_search(subquery.query_text)

                execution_time = (time.time() - start_time) * 1000

                # Estimate tokens
                tokens_used = self._estimate_tokens(results)

                return SubQueryResult(
                    subquery_id=subquery.id,
                    query_text=subquery.query_text,
                    search_type=subquery.search_type,
                    results=results,
                    execution_time_ms=execution_time,
                    tokens_used=tokens_used,
                    metadata={
                        "intent": subquery.intent.value,
                        "priority": subquery.priority,
                    },
                )

            except Exception as e:
                logger.error(f"Subquery {subquery.id} failed: {e}")
                return SubQueryResult(
                    subquery_id=subquery.id,
                    query_text=subquery.query_text,
                    search_type=subquery.search_type,
                    results=[],
                    execution_time_ms=(time.time() - start_time) * 1000,
                    tokens_used=0,
                    error=str(e),
                )

    async def _graph_search(self, query: str) -> list[Any]:
        """Execute graph search on Neptune."""
        logger.debug(f"Graph search: {query}")

        try:
            # TODO: Implement actual Neptune Gremlin query
            # Example: Find all functions matching pattern
            # gremlin_query = f"g.V().has('name', TextP.containing('{pattern}')).limit(50)"
            # results = await self.neptune.execute(gremlin_query)

            return []  # Placeholder - Neptune integration pending

        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return []

    async def _vector_search(self, query: str) -> list[Any]:
        """Execute semantic vector search on OpenSearch."""
        logger.debug(f"Vector search: {query}")

        try:
            if self.fs_navigator:
                result: list[Any] = await self.fs_navigator.search(
                    pattern=query, search_type="semantic", max_results=50
                )
                return result
            return []

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def _filesystem_search(self, query: str) -> list[Any]:
        """Execute filesystem pattern search."""
        logger.debug(f"Filesystem search: {query}")

        try:
            if self.fs_navigator:
                result: list[Any] = await self.fs_navigator.search(
                    pattern=query, search_type="pattern", max_results=50
                )
                return result
            return []

        except Exception as e:
            logger.error(f"Filesystem search failed: {e}")
            return []

    async def _git_search(self, query: str) -> list[Any]:
        """Execute git history search."""
        logger.debug(f"Git search: {query}")

        try:
            if self.fs_navigator:
                result: list[Any] = await self.fs_navigator.search(
                    pattern=query, search_type="recent_changes", max_results=30
                )
                return result
            return []

        except Exception as e:
            logger.error(f"Git search failed: {e}")
            return []

    async def _execute_with_step_functions(
        self,
        decomposition: QueryDecomposition,
    ) -> list[SubQueryResult]:
        """
        Execute subqueries using AWS Step Functions.

        For complex multi-hop queries with dependencies.
        """
        if not self.sfn_client or not self.state_machine_arn:
            logger.warning(
                "Step Functions not configured, falling back to local execution"
            )
            return await self._execute_local(decomposition)

        try:
            import json

            # Start execution
            execution_input = json.dumps(
                {
                    "original_query": decomposition.original_query,
                    "subqueries": [
                        {
                            "id": sq.id,
                            "query_text": sq.query_text,
                            "search_type": sq.search_type,
                            "priority": sq.priority,
                            "depends_on": sq.depends_on,
                        }
                        for sq in decomposition.subqueries
                    ],
                }
            )

            response = await self.sfn_client.start_execution(
                stateMachineArn=self.state_machine_arn, input=execution_input
            )

            execution_arn = response["executionArn"]

            # Poll for completion (with timeout)
            max_wait_seconds = 60
            poll_interval = 2
            waited = 0

            while waited < max_wait_seconds:
                status_response = await self.sfn_client.describe_execution(
                    executionArn=execution_arn
                )

                status = status_response["status"]
                if status == "SUCCEEDED":
                    output = json.loads(status_response["output"])
                    return self._parse_sfn_results(output)
                elif status in ("FAILED", "TIMED_OUT", "ABORTED"):
                    raise RuntimeError(f"Step Functions execution {status}")

                await asyncio.sleep(poll_interval)
                waited += poll_interval

            raise TimeoutError("Step Functions execution timed out")

        except Exception as e:
            logger.error(f"Step Functions execution failed: {e}")
            # Fallback to local execution
            return await self._execute_local(decomposition)

    def _parse_sfn_results(self, output: dict) -> list[SubQueryResult]:
        """Parse Step Functions output into SubQueryResults."""
        results = []
        for result_data in output.get("results", []):
            results.append(
                SubQueryResult(
                    subquery_id=result_data.get("subquery_id", ""),
                    query_text=result_data.get("query_text", ""),
                    search_type=result_data.get("search_type", ""),
                    results=result_data.get("results", []),
                    execution_time_ms=result_data.get("execution_time_ms", 0),
                    tokens_used=result_data.get("tokens_used", 0),
                    error=result_data.get("error"),
                )
            )
        return results

    def _aggregate_results(
        self,
        original_query: str,
        subquery_results: list[SubQueryResult],
        context_budget: int,
        execution_mode: ExecutionMode,
    ) -> AggregatedResult:
        """
        Aggregate results from all subqueries.

        - Deduplicates files appearing in multiple results
        - Computes relevance scores based on appearance frequency
        - Ranks by combined relevance and priority
        - Fits within token budget
        """
        # Collect all results with their sources
        file_appearances: dict[str, list[tuple[Any, SubQueryResult]]] = {}

        for sq_result in subquery_results:
            for result in sq_result.results:
                # Get file path (handle different result types)
                file_path = self._get_file_path(result)
                if file_path:
                    if file_path not in file_appearances:
                        file_appearances[file_path] = []
                    file_appearances[file_path].append((result, sq_result))

        # Compute relevance scores
        relevance_scores: dict[str, float] = {}
        for file_path, appearances in file_appearances.items():
            # Base score from number of subqueries that found this file
            appearance_score = len(appearances) * 10

            # Bonus from subquery priorities
            priority_score = sum(
                sq_result.metadata.get("priority", 5) for _, sq_result in appearances
            )

            # Bonus from original result scores (if available)
            result_score = sum(
                self._get_result_score(result) for result, _ in appearances
            )

            relevance_scores[file_path] = (
                appearance_score + priority_score + result_score
            )

        # Sort by relevance and fit to budget
        sorted_files = sorted(
            file_appearances.keys(),
            key=lambda fp: relevance_scores.get(fp, 0),
            reverse=True,
        )

        # Build ranked results within budget
        ranked_results = []
        total_tokens = 0

        for file_path in sorted_files:
            # Get the best result object for this file
            best_result, _ = max(
                file_appearances[file_path],
                key=lambda x: x[1].metadata.get("priority", 0),
            )

            tokens = self._estimate_tokens([best_result])
            if total_tokens + tokens <= context_budget:
                ranked_results.append(best_result)
                total_tokens += tokens
            else:
                break

        return AggregatedResult(
            original_query=original_query,
            total_results=sum(len(r.results) for r in subquery_results),
            unique_files=len(file_appearances),
            ranked_results=ranked_results,
            subquery_results=subquery_results,
            total_execution_time_ms=0,  # Set by caller
            total_tokens_used=total_tokens,
            relevance_scores=relevance_scores,
            execution_mode=execution_mode,
        )

    def _get_file_path(self, result: Any) -> str | None:
        """Extract file path from result object."""
        if hasattr(result, "file_path"):
            file_path = result.file_path
            return str(file_path) if file_path is not None else None
        elif isinstance(result, dict):
            file_path_dict = result.get("file_path") or result.get("path")
            return str(file_path_dict) if file_path_dict is not None else None
        return None

    def _get_result_score(self, result: Any) -> float:
        """Extract score from result object."""
        if hasattr(result, "score"):
            score = result.score
            return float(score) if score is not None else 0.0
        elif hasattr(result, "relevance_score"):
            relevance_score = result.relevance_score
            return float(relevance_score) if relevance_score is not None else 0.0
        elif isinstance(result, dict):
            score_value = result.get("score", 0) or result.get("_score", 0)
            return float(score_value) if score_value is not None else 0.0
        return 0.0

    def _estimate_tokens(self, results: list[Any]) -> int:
        """Estimate token count for results."""
        total = 0
        for result in results:
            if hasattr(result, "estimated_tokens"):
                total += result.estimated_tokens
            elif hasattr(result, "file_size"):
                # Rough estimate: 1 token per 4 characters
                total += result.file_size // 4
            elif isinstance(result, dict):
                total += result.get("estimated_tokens", 500)
            else:
                total += 500  # Default estimate
        return total


# Factory function
def create_parallel_executor(
    neptune_client: Any = None,
    opensearch_client: Any = None,
    fs_navigator: Any = None,
    use_mock: bool = False,
) -> ParallelQueryExecutor:
    """
    Create a ParallelQueryExecutor with optional mock clients.

    Args:
        neptune_client: Neptune client (optional)
        opensearch_client: OpenSearch client (optional)
        fs_navigator: FilesystemNavigatorAgent (optional)
        use_mock: If True, create mock clients

    Returns:
        Configured ParallelQueryExecutor
    """
    if use_mock:
        from unittest.mock import AsyncMock

        neptune = neptune_client or AsyncMock()
        opensearch = opensearch_client or AsyncMock()
        fs_nav = fs_navigator or AsyncMock()

        # Mock fs_navigator.search to return empty list
        fs_nav.search = AsyncMock(return_value=[])

        return ParallelQueryExecutor(
            neptune_client=neptune,
            opensearch_client=opensearch,
            fs_navigator=fs_nav,
        )

    return ParallelQueryExecutor(
        neptune_client=neptune_client,
        opensearch_client=opensearch_client,
        fs_navigator=fs_navigator,
    )


# Example usage
async def example_usage():
    """Example usage of ParallelQueryExecutor."""
    from src.services.query_analyzer import create_query_analyzer

    # Create components
    analyzer = create_query_analyzer(use_mock=True)
    executor = create_parallel_executor(use_mock=True)

    # Decompose query
    query = "Find authentication functions that call database"
    decomposition = await analyzer.analyze(query, context_budget=50000)

    print(f"Query: {query}")
    print(f"Decomposed into {len(decomposition.subqueries)} subqueries")

    # Execute
    results = await executor.execute(decomposition, context_budget=50000)

    print("\nResults:")
    print(f"  Total results: {results.total_results}")
    print(f"  Unique files: {results.unique_files}")
    print(f"  Execution time: {results.total_execution_time_ms:.0f}ms")
    print(f"  Tokens used: {results.total_tokens_used}")

    print("\nSubquery results:")
    for sq_result in results.subquery_results:
        status = "OK" if not sq_result.error else f"ERROR: {sq_result.error}"
        print(
            f"  [{sq_result.subquery_id}] {sq_result.search_type}: "
            f"{len(sq_result.results)} results ({sq_result.execution_time_ms:.0f}ms) - {status}"
        )


if __name__ == "__main__":
    asyncio.run(example_usage())
