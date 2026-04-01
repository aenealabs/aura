"""
Project Aura - Integration Tests for Agentic Search System

Tests end-to-end agentic search workflow:
- Query planning with LLM
- Multi-strategy search execution
- Result synthesis and ranking
- Context budget optimization

Author: Project Aura Team
Created: 2025-11-18
"""

# ruff: noqa: PLR2004

import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.agents.filesystem_navigator_agent import FileMatch, FilesystemNavigatorAgent
from src.agents.query_planning_agent import QueryPlanningAgent, SearchStrategy
from src.agents.result_synthesis_agent import ContextResponse, ResultSynthesisAgent
from src.services.context_retrieval_service import ContextRetrievalService


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for query planning."""
    mock = AsyncMock()
    mock.generate.return_value = """
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
        },
        {
          "type": "graph",
          "query": "Find functions calling authenticate()",
          "priority": 7,
          "estimated_tokens": 3000
        }
      ]
    }
    """
    return mock


@pytest.fixture
def mock_opensearch_client():
    """Mock OpenSearch client for filesystem and vector searches."""
    mock = AsyncMock()
    mock.search.return_value = {
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
                {
                    "_score": 7.2,
                    "_source": {
                        "file_path": "tests/test_auth_service.py",
                        "file_size": 2000,
                        "last_modified": "2025-11-16T12:00:00Z",
                        "language": "python",
                        "num_lines": 100,
                        "last_author": "charlie@example.com",
                        "is_test_file": True,
                        "is_config_file": False,
                    },
                },
            ]
        }
    }
    return mock


@pytest.fixture
def mock_neptune_client():
    """Mock Neptune client for graph searches."""
    return AsyncMock()


@pytest.fixture
def mock_embeddings_service():
    """Mock embeddings service."""
    mock = AsyncMock()
    mock.generate_embedding.return_value = [0.1] * 1536
    return mock


@pytest.fixture
def context_service(
    mock_neptune_client,
    mock_opensearch_client,
    mock_llm_client,
    mock_embeddings_service,
):
    """Create ContextRetrievalService with mocked dependencies."""
    return ContextRetrievalService(
        neptune_client=mock_neptune_client,
        opensearch_client=mock_opensearch_client,
        llm_client=mock_llm_client,
        embedding_service=mock_embeddings_service,
        git_repo_path="/test/repo",
    )


# =============================================================================
# Query Planning Tests
# =============================================================================


@pytest.mark.anyio
async def test_query_planning_generates_strategies(mock_llm_client):
    """Test that query planner generates multi-strategy plan."""
    planner = QueryPlanningAgent(mock_llm_client)

    strategies = await planner.plan_search(
        user_query="Find JWT authentication code", context_budget=50000
    )

    # Should generate 3 strategies from mock response
    assert len(strategies) == 3

    # Verify strategies are sorted by priority
    assert strategies[0].priority >= strategies[1].priority
    assert strategies[1].priority >= strategies[2].priority

    # Verify strategy types
    strategy_types = {s.strategy_type for s in strategies}
    assert "vector" in strategy_types
    assert "filesystem" in strategy_types
    assert "graph" in strategy_types


@pytest.mark.anyio
async def test_query_planning_respects_budget(mock_llm_client):
    """Test that query planner fits strategies within token budget."""
    planner = QueryPlanningAgent(mock_llm_client)

    # Small budget - should exclude some strategies
    strategies = await planner.plan_search(
        user_query="Find JWT authentication code", context_budget=5000
    )

    # Should only include strategies that fit budget
    total_tokens = sum(s.estimated_tokens for s in strategies)
    assert total_tokens <= 5000


@pytest.mark.anyio
async def test_query_planning_fallback_on_llm_failure():
    """Test fallback strategy when LLM fails."""
    mock_llm = AsyncMock()
    mock_llm.generate.side_effect = Exception("LLM API error")

    planner = QueryPlanningAgent(mock_llm)

    strategies = await planner.plan_search(
        user_query="Find authentication code", context_budget=50000
    )

    # Should return default strategies
    assert len(strategies) > 0
    assert all(isinstance(s, SearchStrategy) for s in strategies)


# =============================================================================
# Filesystem Navigator Tests
# =============================================================================


@pytest.mark.anyio
async def test_filesystem_pattern_search(
    mock_opensearch_client, mock_embeddings_service
):
    """Test pattern-based filesystem search."""
    navigator = FilesystemNavigatorAgent(
        mock_opensearch_client, mock_embeddings_service
    )

    results = await navigator.search(
        pattern="**/auth/*.py", search_type="pattern", max_results=50
    )

    # Should return 3 files from mock
    assert len(results) == 3

    # Verify FileMatch objects
    assert all(isinstance(r, FileMatch) for r in results)
    assert results[0].file_path == "src/services/auth_service.py"


@pytest.mark.anyio
async def test_filesystem_semantic_search(
    mock_opensearch_client, mock_embeddings_service
):
    """Test semantic filesystem search with embeddings."""
    navigator = FilesystemNavigatorAgent(
        mock_opensearch_client, mock_embeddings_service
    )

    results = await navigator.search(
        pattern="authentication logic", search_type="semantic", max_results=50
    )

    # Should generate embedding and search
    mock_embeddings_service.generate_embedding.assert_called_once()
    assert len(results) == 3


@pytest.mark.anyio
async def test_filesystem_recent_changes_search(
    mock_opensearch_client, mock_embeddings_service
):
    """Test recent changes search (Git integration)."""
    navigator = FilesystemNavigatorAgent(
        mock_opensearch_client, mock_embeddings_service
    )

    results = await navigator.search(
        pattern="*", search_type="recent_changes", max_results=30
    )

    # Should search OpenSearch with date range filter
    assert mock_opensearch_client.search.called
    call_args = mock_opensearch_client.search.call_args
    query = call_args.kwargs["body"]

    # Verify date range filter exists
    assert "range" in str(query)
    assert len(results) == 3


@pytest.mark.anyio
async def test_find_related_files(mock_opensearch_client, mock_embeddings_service):
    """Test finding related files (tests, configs, same module)."""
    navigator = FilesystemNavigatorAgent(
        mock_opensearch_client, mock_embeddings_service
    )

    related = await navigator.find_related_files("src/services/auth_service.py")

    # Should return dictionary with categories
    assert "tests" in related
    assert "same_module" in related
    assert "config" in related

    # Should make multiple searches (test patterns, same module, configs)
    assert mock_opensearch_client.search.call_count >= 3


# =============================================================================
# Result Synthesis Tests
# =============================================================================


def test_result_synthesis_deduplication():
    """Test deduplication of files from multiple strategies."""
    synthesizer = ResultSynthesisAgent()

    # Create duplicate FileMatch objects with same path
    file1 = FileMatch(
        file_path="src/auth.py",
        file_size=1000,
        last_modified=datetime.now(),
        language="python",
        num_lines=100,
        relevance_score=9.0,
    )

    file2 = FileMatch(
        file_path="src/auth.py",
        file_size=1000,
        last_modified=datetime.now(),
        language="python",
        num_lines=100,
        relevance_score=7.0,  # Lower score
    )

    graph_results = [file1]
    vector_results = [file2]

    response = synthesizer.synthesize(
        graph_results=graph_results,
        vector_results=vector_results,
        filesystem_results=[],
        git_results=[],
        context_budget=10000,
        query="test query",
    )

    # Should keep only one copy (with higher score)
    assert len(response.files) == 1
    assert response.files[0].relevance_score == 9.0


def test_result_synthesis_multi_strategy_boost():
    """Test that files found by multiple strategies get boosted score."""
    synthesizer = ResultSynthesisAgent()

    # File found by both graph and vector search
    file_both = FileMatch(
        file_path="src/auth.py",
        file_size=1000,
        last_modified=datetime.now() - timedelta(days=2),
        language="python",
        num_lines=200,
        relevance_score=8.0,
    )

    # File found only by vector search
    file_vector = FileMatch(
        file_path="src/utils.py",
        file_size=1000,
        last_modified=datetime.now() - timedelta(days=2),
        language="python",
        num_lines=200,
        relevance_score=8.0,  # Same base score
    )

    graph_results = [file_both]
    vector_results = [file_both, file_vector]

    response = synthesizer.synthesize(
        graph_results=graph_results,
        vector_results=vector_results,
        filesystem_results=[],
        git_results=[],
        context_budget=10000,
        query="test query",
    )

    # Multi-strategy file should rank higher
    assert response.files[0].file_path == "src/auth.py"
    assert response.files[1].file_path == "src/utils.py"


def test_result_synthesis_budget_fitting():
    """Test that result synthesis respects token budget."""
    synthesizer = ResultSynthesisAgent()

    # Create 10 large files
    large_files = [
        FileMatch(
            file_path=f"src/file_{i}.py",
            file_size=10000,
            last_modified=datetime.now(),
            language="python",
            num_lines=500,  # ~750 tokens each
            relevance_score=10.0 - i,  # Descending scores
            estimated_tokens=750,  # Set explicit token count
        )
        for i in range(10)
    ]

    response = synthesizer.synthesize(
        graph_results=[],
        vector_results=large_files,
        filesystem_results=[],
        git_results=[],
        context_budget=3000,  # Only ~4 files should fit
        query="test query",
    )

    # Should select only files that fit budget
    assert response.total_tokens <= 3000
    assert len(response.files) <= 5  # Approximately 4 files (4 * 750 = 3000)


def test_result_synthesis_recency_boost():
    """Test that recent files get scoring boost."""
    synthesizer = ResultSynthesisAgent()

    # Recent file (2 days old)
    recent_file = FileMatch(
        file_path="src/recent.py",
        file_size=1000,
        last_modified=datetime.now() - timedelta(days=2),
        language="python",
        num_lines=100,
        relevance_score=5.0,
    )

    # Old file (100 days old)
    old_file = FileMatch(
        file_path="src/old.py",
        file_size=1000,
        last_modified=datetime.now() - timedelta(days=100),
        language="python",
        num_lines=100,
        relevance_score=5.0,  # Same base score
    )

    response = synthesizer.synthesize(
        graph_results=[],
        vector_results=[recent_file, old_file],
        filesystem_results=[],
        git_results=[],
        context_budget=10000,
        query="test query",
    )

    # Recent file should rank higher
    assert response.files[0].file_path == "src/recent.py"


def test_result_synthesis_test_file_penalty():
    """Test that test files get scoring penalty."""
    synthesizer = ResultSynthesisAgent()

    # Core file
    core_file = FileMatch(
        file_path="src/core.py",
        file_size=1000,
        last_modified=datetime.now() - timedelta(days=10),
        language="python",
        num_lines=100,
        relevance_score=5.0,
        is_test_file=False,
    )

    # Test file
    test_file = FileMatch(
        file_path="tests/test_core.py",
        file_size=1000,
        last_modified=datetime.now() - timedelta(days=10),
        language="python",
        num_lines=100,
        relevance_score=5.0,  # Same base score
        is_test_file=True,
    )

    response = synthesizer.synthesize(
        graph_results=[],
        vector_results=[core_file, test_file],
        filesystem_results=[],
        git_results=[],
        context_budget=10000,
        query="test query",
    )

    # Core file should rank higher
    assert response.files[0].file_path == "src/core.py"


# =============================================================================
# End-to-End Integration Tests
# =============================================================================


@pytest.mark.anyio
async def test_end_to_end_context_retrieval(context_service):
    """Test complete end-to-end context retrieval workflow."""
    # Execute full context retrieval
    context_response = await context_service.retrieve_context(
        query="Find JWT authentication code", context_budget=50000
    )

    # Verify response structure
    assert isinstance(context_response, ContextResponse)
    assert context_response.files is not None
    assert len(context_response.files) > 0
    assert context_response.total_tokens > 0
    assert len(context_response.strategies_used) > 0

    # Verify files are ranked
    scores = [
        f.relevance_score for f in context_response.files if f.relevance_score > 0
    ]
    if len(scores) > 1:
        assert scores == sorted(scores, reverse=True)


@pytest.mark.anyio
async def test_context_retrieval_with_manual_strategies(context_service):
    """Test context retrieval with manually specified strategies."""
    # Force specific strategies
    context_response = await context_service.retrieve_context(
        query="Find authentication code",
        context_budget=20000,
        strategies=["vector", "filesystem"],
    )

    # Should use only specified strategies
    assert "vector" in context_response.strategies_used
    assert "filesystem" in context_response.strategies_used
    # Graph and git should not be used
    assert (
        "graph" not in context_response.strategies_used
        or len(context_response.strategies_used) == 2
    )


@pytest.mark.anyio
async def test_context_retrieval_handles_search_failures(
    mock_neptune_client,
    mock_opensearch_client,
    mock_llm_client,
    mock_embeddings_service,
):
    """Test graceful handling of search strategy failures."""
    # Make vector search fail
    mock_opensearch_client.search.side_effect = Exception("OpenSearch error")

    service = ContextRetrievalService(
        neptune_client=mock_neptune_client,
        opensearch_client=mock_opensearch_client,
        llm_client=mock_llm_client,
        embedding_service=mock_embeddings_service,
        git_repo_path="/test/repo",
    )

    # Should not crash, should return partial results
    context_response = await service.retrieve_context(
        query="Find code", context_budget=10000
    )

    # Should still return response (even if empty)
    assert isinstance(context_response, ContextResponse)


@pytest.mark.anyio
async def test_parallel_strategy_execution(context_service, mock_opensearch_client):
    """Test that multiple strategies execute in parallel."""
    # Execute context retrieval
    await context_service.retrieve_context(
        query="Find authentication code", context_budget=50000
    )

    # Verify multiple searches were made (parallelized)
    # Should have at least 2 search calls (vector + filesystem)
    assert mock_opensearch_client.search.call_count >= 2


@pytest.mark.anyio
async def test_context_response_within_budget(context_service):
    """Test that final context stays within token budget."""
    budget = 5000

    context_response = await context_service.retrieve_context(
        query="Find code", context_budget=budget
    )

    # Total tokens should not exceed budget
    assert context_response.total_tokens <= budget


# =============================================================================
# Performance Tests
# =============================================================================


@pytest.mark.slow
@pytest.mark.anyio
async def test_large_result_set_performance(
    mock_neptune_client, mock_llm_client, mock_embeddings_service
):
    """Test performance with large result sets."""
    # Create mock with 1000 files
    large_mock = AsyncMock()
    large_mock.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_score": 10.0 - i,
                    "_source": {
                        "file_path": f"src/file_{i}.py",
                        "file_size": 1000 + i,
                        "last_modified": "2025-11-18T10:00:00Z",
                        "language": "python",
                        "num_lines": 100,
                        "is_test_file": False,
                        "is_config_file": False,
                    },
                }
                for i in range(1000)
            ]
        }
    }

    service = ContextRetrievalService(
        neptune_client=mock_neptune_client,
        opensearch_client=large_mock,
        llm_client=mock_llm_client,
        embedding_service=mock_embeddings_service,
        git_repo_path="/test/repo",
    )

    # Should handle large result set efficiently
    start = time.time()
    context_response = await service.retrieve_context(
        query="Find code", context_budget=50000
    )
    elapsed = time.time() - start

    # Should complete in reasonable time (< 5 seconds for 1000 files)
    assert elapsed < 5.0

    # Should return results within budget
    assert context_response.total_tokens <= 50000


# =============================================================================
# Explanation and Transparency Tests
# =============================================================================


def test_ranking_explanation():
    """Test ranking explanation for transparency."""
    synthesizer = ResultSynthesisAgent()

    file_match = FileMatch(
        file_path="src/auth.py",
        file_size=5000,
        last_modified=datetime.now() - timedelta(days=3),
        language="python",
        num_lines=250,
        relevance_score=9.5,
    )

    graph_results = [file_match]
    vector_results = [file_match]

    explanation = synthesizer.explain_ranking(
        file_match, graph_results, vector_results, [], []
    )

    # Verify explanation structure
    assert "file_path" in explanation
    assert "final_score" in explanation
    assert "factors" in explanation

    # Verify factors are explained
    factors = explanation["factors"]
    assert "strategies" in factors
    assert "multi_strategy_boost" in factors
    assert "recency" in factors
    assert "size" in factors
    assert "file_type" in factors
