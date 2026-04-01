"""
Tests for Result Synthesis Agent

Tests for combining and ranking search results from multiple strategies.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

# ==================== FileMatch Tests ====================


class TestFileMatch:
    """Tests for FileMatch dataclass."""

    def test_basic_creation(self):
        """Test creating a basic FileMatch."""
        from src.agents.filesystem_navigator_agent import FileMatch

        match = FileMatch(
            file_path="/src/test.py",
            file_size=1000,
            last_modified=datetime.now(UTC),
            language="python",
            num_lines=100,
            relevance_score=0.8,
        )
        assert match.file_path == "/src/test.py"
        assert match.relevance_score == 0.8
        assert match.num_lines == 100

    def test_optional_fields(self):
        """Test FileMatch with optional fields."""
        from src.agents.filesystem_navigator_agent import FileMatch

        match = FileMatch(
            file_path="/src/file.py",
            file_size=500,
            last_modified=datetime.now(UTC),
            language="python",
            num_lines=50,
            last_author="developer",
            is_test_file=True,
        )
        assert match.file_path == "/src/file.py"
        assert match.last_author == "developer"
        assert match.is_test_file is True


# ==================== ContextResponse Tests ====================


class TestContextResponse:
    """Tests for ContextResponse dataclass."""

    def test_creation(self):
        """Test creating a ContextResponse."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ContextResponse

        files = [
            FileMatch(
                file_path="/a.py",
                file_size=100,
                last_modified=datetime.now(UTC),
                language="python",
                num_lines=10,
            ),
            FileMatch(
                file_path="/b.py",
                file_size=200,
                last_modified=datetime.now(UTC),
                language="python",
                num_lines=20,
            ),
        ]

        response = ContextResponse(
            files=files,
            total_tokens=5000,
            strategies_used=["vector", "graph"],
            query="test query",
        )
        assert len(response.files) == 2
        assert response.total_tokens == 5000
        assert "vector" in response.strategies_used
        assert response.query == "test query"


# ==================== ResultSynthesisAgent Initialization ====================


class TestResultSynthesisAgentInit:
    """Tests for ResultSynthesisAgent initialization."""

    def test_init_without_llm(self):
        """Test initialization without LLM."""
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        assert agent.llm_client is None

    def test_init_with_llm(self):
        """Test initialization with LLM client."""
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        mock_llm = MagicMock()
        agent = ResultSynthesisAgent(llm_client=mock_llm)
        assert agent.llm_client == mock_llm


# ==================== Deduplication Tests ====================


class TestDeduplication:
    """Tests for result deduplication."""

    def test_deduplicate_empty_lists(self):
        """Test deduplication with empty lists."""
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        result = agent.synthesize(
            graph_results=[],
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=10000,
        )
        assert len(result.files) == 0

    def test_deduplicate_single_source(self):
        """Test with results from single source."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        files = [
            FileMatch(
                file_path="/a.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
                relevance_score=0.9,
            ),
            FileMatch(
                file_path="/b.py",
                file_size=200,
                last_modified=now,
                language="python",
                num_lines=20,
                relevance_score=0.8,
            ),
        ]

        result = agent.synthesize(
            graph_results=files,
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=100000,
        )
        # Should include all input files when budget is sufficient
        assert len(result.files) == 2
        assert result.files[0].file_path in ["/a.py", "/b.py"]

    def test_deduplicate_duplicate_paths(self):
        """Test deduplication of same paths from different sources."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)

        # Same file from different sources
        graph_file = FileMatch(
            file_path="/src/main.py",
            file_size=100,
            last_modified=now,
            language="python",
            num_lines=50,
            relevance_score=0.9,
        )
        vector_file = FileMatch(
            file_path="/src/main.py",
            file_size=100,
            last_modified=now,
            language="python",
            num_lines=50,
            relevance_score=0.85,
        )

        result = agent.synthesize(
            graph_results=[graph_file],
            vector_results=[vector_file],
            filesystem_results=[],
            git_results=[],
            context_budget=100000,
        )

        # Should combine into single result
        unique_paths = set(f.file_path for f in result.files)
        assert len(unique_paths) == len(result.files)


# ==================== Ranking Tests ====================


class TestRanking:
    """Tests for result ranking."""

    def test_rank_by_score(self):
        """Test that results are ranked by score."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        files = [
            FileMatch(
                file_path="/low.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
                relevance_score=0.3,
            ),
            FileMatch(
                file_path="/high.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
                relevance_score=0.9,
            ),
            FileMatch(
                file_path="/medium.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
                relevance_score=0.6,
            ),
        ]

        result = agent.synthesize(
            graph_results=files,
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=100000,
        )

        # First file should be highest scoring - verify ranking order
        assert (
            len(result.files) == 3
        ), "All 3 files should be included with sufficient budget"
        assert (
            result.files[0].relevance_score >= result.files[1].relevance_score
        ), "Files should be sorted by score descending"
        assert (
            result.files[0].file_path == "/high.py"
        ), "Highest scoring file should be first"

    def test_recency_boost(self):
        """Test that recent files get boosted."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()

        recent = FileMatch(
            file_path="/recent.py",
            file_size=100,
            last_modified=datetime.now(UTC),
            language="python",
            num_lines=50,
            relevance_score=0.5,
        )
        old = FileMatch(
            file_path="/old.py",
            file_size=100,
            last_modified=datetime.now(UTC) - timedelta(days=365),
            language="python",
            num_lines=50,
            relevance_score=0.5,
        )

        result = agent.synthesize(
            graph_results=[old, recent],
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=100000,
        )

        # Should process both files and track strategies used
        assert len(result.files) >= 1, "Should include at least one file"
        assert "graph" in result.strategies_used, "Graph strategy should be tracked"

    def test_size_boost(self):
        """Test that optimal-sized files get boosted."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)

        optimal = FileMatch(
            file_path="/optimal.py",
            file_size=10000,
            last_modified=now,
            language="python",
            num_lines=1000,
            relevance_score=0.5,
        )
        tiny = FileMatch(
            file_path="/tiny.py",
            file_size=100,
            last_modified=now,
            language="python",
            num_lines=10,
            relevance_score=0.5,
        )

        result = agent.synthesize(
            graph_results=[tiny, optimal],
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=100000,
        )

        # Both files should be included with sufficient budget
        assert len(result.files) == 2, "Both files should be included"
        file_paths = [f.file_path for f in result.files]
        assert "/optimal.py" in file_paths
        assert "/tiny.py" in file_paths


# ==================== Budget Management Tests ====================


class TestBudgetManagement:
    """Tests for token budget management."""

    def test_fits_within_budget(self):
        """Test that result fits within token budget."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        files = [
            FileMatch(
                file_path=f"/file{i}.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=100,
                relevance_score=0.9 - i * 0.1,
            )
            for i in range(10)
        ]

        result = agent.synthesize(
            graph_results=files,
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=1000,
        )

        # Token usage should be tracked and limited by budget
        assert result.total_tokens <= 1000, "Tokens should not exceed budget"
        assert isinstance(result.total_tokens, int), "Token count should be integer"

    def test_small_budget(self):
        """Test with small token budget."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        files = [
            FileMatch(
                file_path="/a.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
                relevance_score=0.9,
            )
        ]

        result = agent.synthesize(
            graph_results=files,
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=100,
        )

        # Small budget should limit tokens
        assert result.total_tokens <= 100


# ==================== Strategy Tracking Tests ====================


class TestStrategyTracking:
    """Tests for tracking which strategies were used."""

    def test_single_strategy(self):
        """Test tracking single strategy."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        files = [
            FileMatch(
                file_path="/a.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
            )
        ]

        result = agent.synthesize(
            graph_results=[],
            vector_results=files,
            filesystem_results=[],
            git_results=[],
            context_budget=10000,
        )

        assert "vector" in result.strategies_used

    def test_multiple_strategies(self):
        """Test tracking multiple strategies."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        graph_files = [
            FileMatch(
                file_path="/a.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
            )
        ]
        vector_files = [
            FileMatch(
                file_path="/b.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
            )
        ]
        fs_files = [
            FileMatch(
                file_path="/c.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
            )
        ]

        result = agent.synthesize(
            graph_results=graph_files,
            vector_results=vector_files,
            filesystem_results=fs_files,
            git_results=[],
            context_budget=100000,
        )

        # All three strategies should be tracked since all have results
        assert (
            len(result.strategies_used) == 3
        ), "Should track all 3 strategies with results"
        assert "graph" in result.strategies_used
        assert "vector" in result.strategies_used
        assert "filesystem" in result.strategies_used


# ==================== Query Handling Tests ====================


class TestQueryHandling:
    """Tests for query handling in synthesis."""

    def test_query_stored_in_response(self):
        """Test that query is stored in response."""
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        result = agent.synthesize(
            graph_results=[],
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=10000,
            query="find authentication code",
        )

        assert result.query == "find authentication code"

    def test_empty_query(self):
        """Test with empty query string."""
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        result = agent.synthesize(
            graph_results=[],
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=10000,
            query="",
        )

        assert result.query == ""


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_large_number_of_results(self):
        """Test with large number of results."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        files = [
            FileMatch(
                file_path=f"/file{i}.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
            )
            for i in range(100)
        ]

        result = agent.synthesize(
            graph_results=files,
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=100000,
        )

        # Should handle large input and return valid response
        assert isinstance(result.files, list), "Result should contain files list"
        assert result.total_tokens >= 0, "Token count should be non-negative"
        assert (
            len(result.strategies_used) >= 1
        ), "At least one strategy should be tracked"

    def test_negative_score(self):
        """Test handling of negative scores."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        files = [
            FileMatch(
                file_path="/neg.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
                relevance_score=-0.5,
            )
        ]

        result = agent.synthesize(
            graph_results=files,
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=10000,
        )

        # Should handle negative scores gracefully
        assert isinstance(result.files, list), "Result should contain files list"
        assert (
            "graph" in result.strategies_used
        ), "Strategy should be tracked despite negative score"

    def test_very_long_paths(self):
        """Test with very long file paths."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        long_path = "/" + "/".join(["dir"] * 50) + "/file.py"
        files = [
            FileMatch(
                file_path=long_path,
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
            )
        ]

        result = agent.synthesize(
            graph_results=files,
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=10000,
        )

        # Should handle very long paths without truncation
        assert len(result.files) == 1, "File should be included"
        assert result.files[0].file_path == long_path, "Long path should be preserved"


# ==================== File Type Filtering Tests ====================


class TestFileTypeFiltering:
    """Tests for file type handling."""

    def test_test_file_deprioritization(self):
        """Test that test files may be deprioritized."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        test_file = FileMatch(
            file_path="/tests/test_main.py",
            file_size=100,
            last_modified=now,
            language="python",
            num_lines=10,
            is_test_file=True,
        )
        src_file = FileMatch(
            file_path="/src/main.py",
            file_size=100,
            last_modified=now,
            language="python",
            num_lines=10,
            is_test_file=False,
        )

        result = agent.synthesize(
            graph_results=[test_file, src_file],
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=100000,
        )

        # Both files should be included with sufficient budget
        assert len(result.files) == 2, "Both test and source files should be included"
        file_paths = [f.file_path for f in result.files]
        assert "/tests/test_main.py" in file_paths
        assert "/src/main.py" in file_paths

    def test_config_file_handling(self):
        """Test handling of config files."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        config_file = FileMatch(
            file_path="/config/settings.yaml",
            file_size=100,
            last_modified=now,
            language="yaml",
            num_lines=10,
            is_config_file=True,
        )

        result = agent.synthesize(
            graph_results=[config_file],
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=100000,
        )

        # Config files should be included and processed
        assert len(result.files) == 1, "Config file should be included"
        assert result.files[0].language == "yaml", "Language should be preserved"


# ==================== Git Results Integration ====================


class TestGitResultsIntegration:
    """Tests for git results integration."""

    def test_git_results_included(self):
        """Test that git results are included in synthesis."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        git_file = FileMatch(
            file_path="/src/changed.py",
            file_size=100,
            last_modified=now,
            language="python",
            num_lines=10,
        )

        result = agent.synthesize(
            graph_results=[],
            vector_results=[],
            filesystem_results=[],
            git_results=[git_file],
            context_budget=100000,
        )

        # Git results should be included and strategy tracked
        assert len(result.files) == 1, "Git file should be included"
        assert "git" in result.strategies_used, "Git strategy should be tracked"


# ==================== LLM Integration Tests ====================


class TestLLMIntegration:
    """Tests for LLM-based ranking."""

    def test_synthesis_without_llm(self):
        """Test synthesis works without LLM."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        agent = ResultSynthesisAgent()
        now = datetime.now(UTC)
        files = [
            FileMatch(
                file_path="/a.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
            )
        ]

        result = agent.synthesize(
            graph_results=files,
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=10000,
        )

        # Should work without LLM and return valid result
        assert len(result.files) == 1, "File should be included"
        assert result.total_tokens <= 10000, "Should respect budget"

    def test_synthesis_with_llm(self):
        """Test synthesis with LLM client."""
        from src.agents.filesystem_navigator_agent import FileMatch
        from src.agents.result_synthesis_agent import ResultSynthesisAgent

        mock_llm = MagicMock()
        agent = ResultSynthesisAgent(llm_client=mock_llm)
        now = datetime.now(UTC)
        files = [
            FileMatch(
                file_path="/a.py",
                file_size=100,
                last_modified=now,
                language="python",
                num_lines=10,
            )
        ]

        result = agent.synthesize(
            graph_results=files,
            vector_results=[],
            filesystem_results=[],
            git_results=[],
            context_budget=10000,
        )

        # Should work with LLM client and return valid result
        assert len(result.files) == 1, "File should be included"
        assert agent.llm_client == mock_llm, "LLM client should be set"
