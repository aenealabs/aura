"""
Tests for Parallel Query Executor (ADR-028 Phase 3)

Tests parallel subquery execution and result aggregation.
"""

from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from src.services.parallel_query_executor import (
    ExecutionMode,
    SubQueryResult,
    create_parallel_executor,
)
from src.services.query_analyzer import QueryDecomposition, QueryIntent, SubQuery


@dataclass
class MockFileMatch:
    """Mock FileMatch for testing."""

    file_path: str
    score: float = 0.0
    estimated_tokens: int = 500
    file_size: int = 2000


class TestSubQueryResult:
    """Test SubQueryResult dataclass."""

    def test_subquery_result_creation(self):
        """Test creating a SubQueryResult."""
        result = SubQueryResult(
            subquery_id="sq_1",
            query_text="Find auth functions",
            search_type="graph",
            results=[MockFileMatch("src/auth.py")],
            execution_time_ms=150.5,
            tokens_used=500,
        )

        assert result.subquery_id == "sq_1"
        assert result.error is None
        assert len(result.results) == 1

    def test_subquery_result_with_error(self):
        """Test SubQueryResult with error."""
        result = SubQueryResult(
            subquery_id="sq_1",
            query_text="test",
            search_type="vector",
            results=[],
            execution_time_ms=50,
            tokens_used=0,
            error="Connection failed",
        )

        assert result.error == "Connection failed"
        assert len(result.results) == 0


class TestExecutionMode:
    """Test ExecutionMode enum."""

    def test_execution_modes(self):
        """Verify execution modes are defined."""
        assert ExecutionMode.LOCAL.value == "local"
        assert ExecutionMode.STEP_FUNCTIONS.value == "step_functions"


class TestParallelQueryExecutorExecutionPhases:
    """Test execution phase planning."""

    @pytest.fixture
    def executor(self):
        """Create executor with mocks."""
        return create_parallel_executor(use_mock=True)

    def test_plan_single_phase_no_dependencies(self, executor):
        """Test planning with no dependencies."""
        subqueries = [
            SubQuery(
                id="sq_1",
                query_text="a",
                intent=QueryIntent.SEMANTIC,
                search_type="vector",
                priority=10,
            ),
            SubQuery(
                id="sq_2",
                query_text="b",
                intent=QueryIntent.STRUCTURAL,
                search_type="graph",
                priority=8,
            ),
        ]

        phases = executor._plan_execution_phases(subqueries)

        assert len(phases) == 1
        assert len(phases[0]) == 2

    def test_plan_multiple_phases_with_dependencies(self, executor):
        """Test planning with dependencies creates multiple phases."""
        subqueries = [
            SubQuery(
                id="sq_1",
                query_text="a",
                intent=QueryIntent.SEMANTIC,
                search_type="vector",
                priority=10,
                depends_on=[],
            ),
            SubQuery(
                id="sq_2",
                query_text="b",
                intent=QueryIntent.STRUCTURAL,
                search_type="graph",
                priority=8,
                depends_on=["sq_1"],
            ),
            SubQuery(
                id="sq_3",
                query_text="c",
                intent=QueryIntent.TEMPORAL,
                search_type="git",
                priority=6,
                depends_on=["sq_2"],
            ),
        ]

        phases = executor._plan_execution_phases(subqueries)

        assert len(phases) == 3
        assert phases[0][0].id == "sq_1"
        assert phases[1][0].id == "sq_2"
        assert phases[2][0].id == "sq_3"

    def test_plan_parallel_within_phase(self, executor):
        """Test independent subqueries in same phase."""
        subqueries = [
            SubQuery(
                id="sq_1",
                query_text="a",
                intent=QueryIntent.SEMANTIC,
                search_type="vector",
                priority=10,
                depends_on=[],
            ),
            SubQuery(
                id="sq_2",
                query_text="b",
                intent=QueryIntent.STRUCTURAL,
                search_type="graph",
                priority=8,
                depends_on=[],
            ),
            SubQuery(
                id="sq_3",
                query_text="c",
                intent=QueryIntent.TEMPORAL,
                search_type="git",
                priority=6,
                depends_on=["sq_1", "sq_2"],
            ),
        ]

        phases = executor._plan_execution_phases(subqueries)

        assert len(phases) == 2
        assert len(phases[0]) == 2  # sq_1 and sq_2 in parallel
        assert len(phases[1]) == 1  # sq_3 depends on both


class TestParallelQueryExecutorLocalExecution:
    """Test local async execution."""

    @pytest.fixture
    def executor(self):
        """Create executor with mocks."""
        return create_parallel_executor(use_mock=True)

    @pytest.mark.asyncio
    async def test_execute_simple_decomposition(self, executor):
        """Test executing a simple decomposition."""
        decomp = QueryDecomposition(
            original_query="Find auth code",
            intent=QueryIntent.SEMANTIC,
            subqueries=[
                SubQuery(
                    id="sq_1",
                    query_text="auth code",
                    intent=QueryIntent.SEMANTIC,
                    search_type="vector",
                    priority=10,
                ),
            ],
            execution_plan="single",
            reasoning="Simple query",
        )

        result = await executor.execute(decomp, context_budget=50000)

        assert result.original_query == "Find auth code"
        assert len(result.subquery_results) == 1
        assert result.execution_mode == ExecutionMode.LOCAL

    @pytest.mark.asyncio
    async def test_execute_parallel_subqueries(self, executor):
        """Test executing multiple subqueries in parallel."""
        decomp = QueryDecomposition(
            original_query="Find auth code and tests",
            intent=QueryIntent.HYBRID,
            subqueries=[
                SubQuery(
                    id="sq_1",
                    query_text="auth",
                    intent=QueryIntent.SEMANTIC,
                    search_type="vector",
                    priority=10,
                ),
                SubQuery(
                    id="sq_2",
                    query_text="tests",
                    intent=QueryIntent.NAVIGATIONAL,
                    search_type="filesystem",
                    priority=8,
                ),
            ],
            execution_plan="parallel",
            reasoning="Hybrid query",
        )

        result = await executor.execute(decomp, context_budget=50000)

        assert len(result.subquery_results) == 2
        assert result.total_execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_execute_with_dependencies(self, executor):
        """Test executing subqueries with dependencies."""
        decomp = QueryDecomposition(
            original_query="Find base class implementations",
            intent=QueryIntent.STRUCTURAL,
            subqueries=[
                SubQuery(
                    id="sq_1",
                    query_text="base classes",
                    intent=QueryIntent.STRUCTURAL,
                    search_type="graph",
                    priority=10,
                    depends_on=[],
                ),
                SubQuery(
                    id="sq_2",
                    query_text="implementations",
                    intent=QueryIntent.STRUCTURAL,
                    search_type="graph",
                    priority=8,
                    depends_on=["sq_1"],
                ),
            ],
            execution_plan="sequential",
            reasoning="Multi-hop query",
        )

        result = await executor.execute(decomp, context_budget=50000)

        assert len(result.subquery_results) == 2


class TestParallelQueryExecutorResultAggregation:
    """Test result aggregation and ranking."""

    @pytest.fixture
    def executor(self):
        """Create executor with mocks."""
        return create_parallel_executor(use_mock=True)

    def test_aggregate_deduplicates_files(self, executor):
        """Test that duplicate files are deduplicated."""
        subquery_results = [
            SubQueryResult(
                subquery_id="sq_1",
                query_text="auth",
                search_type="vector",
                results=[
                    MockFileMatch("src/auth.py", score=9.5),
                    MockFileMatch("src/login.py", score=8.0),
                ],
                execution_time_ms=100,
                tokens_used=1000,
                metadata={"priority": 10},
            ),
            SubQueryResult(
                subquery_id="sq_2",
                query_text="auth",
                search_type="graph",
                results=[
                    MockFileMatch("src/auth.py", score=8.5),  # Duplicate
                    MockFileMatch("src/user.py", score=7.0),
                ],
                execution_time_ms=80,
                tokens_used=800,
                metadata={"priority": 8},
            ),
        ]

        aggregated = executor._aggregate_results(
            "Find auth code",
            subquery_results,
            context_budget=50000,
            execution_mode=ExecutionMode.LOCAL,
        )

        assert aggregated.unique_files == 3  # auth, login, user
        assert aggregated.total_results == 4  # All results before dedup

    def test_aggregate_computes_relevance_scores(self, executor):
        """Test relevance score computation."""
        subquery_results = [
            SubQueryResult(
                subquery_id="sq_1",
                query_text="auth",
                search_type="vector",
                results=[MockFileMatch("src/auth.py", score=9.5)],
                execution_time_ms=100,
                tokens_used=1000,
                metadata={"priority": 10},
            ),
            SubQueryResult(
                subquery_id="sq_2",
                query_text="auth",
                search_type="graph",
                results=[MockFileMatch("src/auth.py", score=8.5)],
                execution_time_ms=80,
                tokens_used=800,
                metadata={"priority": 8},
            ),
        ]

        aggregated = executor._aggregate_results(
            "Find auth code",
            subquery_results,
            context_budget=50000,
            execution_mode=ExecutionMode.LOCAL,
        )

        # File appearing in 2 subqueries should have higher score
        assert "src/auth.py" in aggregated.relevance_scores
        assert aggregated.relevance_scores["src/auth.py"] > 0

    def test_aggregate_respects_token_budget(self, executor):
        """Test that aggregation respects token budget."""
        # Create results that exceed budget
        large_results = [
            MockFileMatch(f"src/file_{i}.py", score=10 - i, estimated_tokens=10000)
            for i in range(10)
        ]

        subquery_results = [
            SubQueryResult(
                subquery_id="sq_1",
                query_text="auth",
                search_type="vector",
                results=large_results,
                execution_time_ms=100,
                tokens_used=100000,
                metadata={"priority": 10},
            ),
        ]

        aggregated = executor._aggregate_results(
            "Find auth code",
            subquery_results,
            context_budget=25000,  # Only room for ~2 files
            execution_mode=ExecutionMode.LOCAL,
        )

        # Should fit within budget
        assert aggregated.total_tokens_used <= 25000


class TestParallelQueryExecutorSearchMethods:
    """Test individual search method routing."""

    @pytest.fixture
    def executor(self):
        """Create executor with mocks."""
        return create_parallel_executor(use_mock=True)

    @pytest.mark.asyncio
    async def test_vector_search_uses_fs_navigator(self, executor):
        """Test vector search routes to fs_navigator."""
        await executor._vector_search("authentication patterns")

        executor.fs_navigator.search.assert_called_with(
            pattern="authentication patterns", search_type="semantic", max_results=50
        )

    @pytest.mark.asyncio
    async def test_filesystem_search_uses_pattern(self, executor):
        """Test filesystem search uses pattern search type."""
        await executor._filesystem_search("**/auth/*.py")

        executor.fs_navigator.search.assert_called_with(
            pattern="**/auth/*.py", search_type="pattern", max_results=50
        )

    @pytest.mark.asyncio
    async def test_git_search_uses_recent_changes(self, executor):
        """Test git search uses recent_changes search type."""
        await executor._git_search("files modified last week")

        executor.fs_navigator.search.assert_called_with(
            pattern="files modified last week",
            search_type="recent_changes",
            max_results=30,
        )


class TestParallelQueryExecutorErrorHandling:
    """Test error handling in execution."""

    @pytest.fixture
    def executor_with_errors(self):
        """Create executor that raises errors."""
        executor = create_parallel_executor(use_mock=True)
        executor.fs_navigator.search = AsyncMock(side_effect=Exception("Search failed"))
        return executor

    @pytest.mark.asyncio
    async def test_handles_subquery_errors(self, executor_with_errors):
        """Test graceful handling of subquery errors."""
        decomp = QueryDecomposition(
            original_query="Find auth code",
            intent=QueryIntent.SEMANTIC,
            subqueries=[
                SubQuery(
                    id="sq_1",
                    query_text="auth",
                    intent=QueryIntent.SEMANTIC,
                    search_type="vector",
                    priority=10,
                ),
            ],
            execution_plan="single",
            reasoning="Simple query",
        )

        result = await executor_with_errors.execute(decomp, context_budget=50000)

        # Should complete without raising
        assert len(result.subquery_results) == 1
        # Error is caught and logged, results are empty but no error field
        # (error handling is internal to search methods)
        assert result.subquery_results[0].results == []


class TestParallelQueryExecutorHelpers:
    """Test helper methods."""

    @pytest.fixture
    def executor(self):
        """Create executor with mocks."""
        return create_parallel_executor(use_mock=True)

    def test_get_file_path_from_object(self, executor):
        """Test extracting file path from object with attribute."""
        result = MockFileMatch("src/test.py")
        path = executor._get_file_path(result)
        assert path == "src/test.py"

    def test_get_file_path_from_dict(self, executor):
        """Test extracting file path from dict."""
        result = {"file_path": "src/test.py"}
        path = executor._get_file_path(result)
        assert path == "src/test.py"

    def test_get_file_path_from_dict_path_key(self, executor):
        """Test extracting file path from dict with 'path' key."""
        result = {"path": "src/test.py"}
        path = executor._get_file_path(result)
        assert path == "src/test.py"

    def test_get_result_score_from_object(self, executor):
        """Test extracting score from object."""
        result = MockFileMatch("src/test.py", score=9.5)
        score = executor._get_result_score(result)
        assert score == 9.5

    def test_estimate_tokens_from_estimated_tokens(self, executor):
        """Test token estimation from estimated_tokens attribute."""
        results = [MockFileMatch("src/test.py", estimated_tokens=1500)]
        tokens = executor._estimate_tokens(results)
        assert tokens == 1500

    def test_estimate_tokens_multiple_files(self, executor):
        """Test token estimation with multiple files."""
        results = [
            MockFileMatch("src/a.py", estimated_tokens=500),
            MockFileMatch("src/b.py", estimated_tokens=700),
        ]
        tokens = executor._estimate_tokens(results)
        assert tokens == 1200


class TestCreateParallelExecutor:
    """Test factory function."""

    def test_create_mock_executor(self):
        """Test creating executor with mocks."""
        executor = create_parallel_executor(use_mock=True)

        assert executor is not None
        assert executor.neptune is not None
        assert executor.opensearch is not None
        assert executor.fs_navigator is not None

    def test_create_executor_with_clients(self):
        """Test creating executor with provided clients."""
        mock_neptune = AsyncMock()
        mock_opensearch = AsyncMock()
        mock_fs_nav = AsyncMock()

        executor = create_parallel_executor(
            neptune_client=mock_neptune,
            opensearch_client=mock_opensearch,
            fs_navigator=mock_fs_nav,
        )

        assert executor.neptune is mock_neptune
        assert executor.opensearch is mock_opensearch
        assert executor.fs_navigator is mock_fs_nav


class TestIntegration:
    """Integration tests with QueryAnalyzer."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """Test full query analysis and execution pipeline."""
        from src.services.query_analyzer import create_query_analyzer

        analyzer = create_query_analyzer(use_mock=True, enable_caching=False)
        executor = create_parallel_executor(use_mock=True)

        # Analyze query
        decomp = await analyzer.analyze(
            "Find authentication functions", context_budget=50000
        )

        # Execute
        results = await executor.execute(decomp, context_budget=50000)

        assert results.original_query == "Find authentication functions"
        assert len(results.subquery_results) >= 1
        assert results.total_execution_time_ms >= 0
