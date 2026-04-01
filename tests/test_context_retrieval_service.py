"""
Tests for Context Retrieval Service.

Covers the ContextRetrievalService for agentic multi-strategy code search
combining graph, vector, filesystem, and git searches.
"""

import sys
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# Save original modules before mocking to prevent test pollution
# =============================================================================
_modules_to_save = [
    "src.agents.filesystem_navigator_agent",
    "src.agents.query_planning_agent",
    "src.agents.result_synthesis_agent",
    "src.services.context_retrieval_service",
]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}


# =============================================================================
# Mock Dependencies BEFORE importing
# =============================================================================


@dataclass
class MockFileMatch:
    """Mock FileMatch for testing - matches real FileMatch signature."""

    file_path: str
    file_size: int = 0
    last_modified: object = None  # datetime
    language: str = "python"
    num_lines: int = 0
    last_author: str = None
    relevance_score: float = 0.5
    is_test_file: bool = False
    is_config_file: bool = False
    estimated_tokens: int = 0
    match_type: str = "semantic"
    snippet: str = ""
    metadata: dict = field(default_factory=dict)

    def __hash__(self):
        return hash(self.file_path)


@dataclass
class MockSearchStrategy:
    """Mock SearchStrategy for testing."""

    strategy_type: str
    query: str
    priority: int = 5
    estimated_tokens: int = 1000


@dataclass
class MockContextResponse:
    """Mock ContextResponse for testing."""

    files: list = field(default_factory=list)
    total_tokens: int = 0
    metadata: dict = field(default_factory=dict)


# Create proper mock classes (not MagicMock) for agents
class MockQueryPlanningAgent:
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.plan_search = AsyncMock(return_value=[])


class MockFilesystemNavigatorAgent:
    def __init__(self, opensearch_client, embedding_service, llm_client=None):
        self.opensearch = opensearch_client
        self.embedding = embedding_service
        self.llm_client = llm_client
        self.search = AsyncMock(return_value=[])


class MockResultSynthesisAgent:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.synthesize = MagicMock(return_value=MockContextResponse())


# Create mock modules with proper classes
mock_fs_agent = MagicMock()
mock_fs_agent.FileMatch = MockFileMatch
mock_fs_agent.FilesystemNavigatorAgent = MockFilesystemNavigatorAgent

mock_query_agent = MagicMock()
mock_query_agent.QueryPlanningAgent = MockQueryPlanningAgent
mock_query_agent.SearchStrategy = MockSearchStrategy

mock_result_agent = MagicMock()
mock_result_agent.ResultSynthesisAgent = MockResultSynthesisAgent
mock_result_agent.ContextResponse = MockContextResponse

sys.modules["src.agents.filesystem_navigator_agent"] = mock_fs_agent
sys.modules["src.agents.query_planning_agent"] = mock_query_agent
sys.modules["src.agents.result_synthesis_agent"] = mock_result_agent

from src.services.context_retrieval_service import ContextRetrievalService

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


# =============================================================================
# ContextRetrievalService Initialization Tests
# =============================================================================


class TestContextRetrievalServiceInit:
    """Tests for ContextRetrievalService initialization."""

    def test_initialization(self):
        """Test basic service initialization."""
        neptune = MagicMock()
        opensearch = MagicMock()
        llm = MagicMock()
        embedding = MagicMock()

        service = ContextRetrievalService(
            neptune_client=neptune,
            opensearch_client=opensearch,
            llm_client=llm,
            embedding_service=embedding,
            git_repo_path="/path/to/repo",
        )

        assert service.neptune == neptune
        assert service.opensearch == opensearch
        assert service.query_planner is not None
        assert service.fs_navigator is not None
        assert service.result_synthesizer is not None


# =============================================================================
# Manual Plan Tests
# =============================================================================


class TestManualPlan:
    """Tests for manual search plan creation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ContextRetrievalService(
            neptune_client=MagicMock(),
            opensearch_client=MagicMock(),
            llm_client=MagicMock(),
            embedding_service=MagicMock(),
            git_repo_path="/test/repo",
        )

    def test_manual_plan_graph_strategy(self):
        """Test manual plan with graph strategy."""
        plan = self.service._manual_plan("test query", ["graph"])

        assert len(plan) == 1
        assert plan[0].strategy_type == "graph"
        assert "test query" in plan[0].query

    def test_manual_plan_vector_strategy(self):
        """Test manual plan with vector strategy."""
        plan = self.service._manual_plan("semantic search", ["vector"])

        assert len(plan) == 1
        assert plan[0].strategy_type == "vector"
        assert plan[0].priority == 10  # Highest priority

    def test_manual_plan_filesystem_strategy(self):
        """Test manual plan with filesystem strategy."""
        plan = self.service._manual_plan("auth files", ["filesystem"])

        assert len(plan) == 1
        assert plan[0].strategy_type == "filesystem"

    def test_manual_plan_git_strategy(self):
        """Test manual plan with git strategy."""
        plan = self.service._manual_plan("recent changes", ["git"])

        assert len(plan) == 1
        assert plan[0].strategy_type == "git"

    def test_manual_plan_multiple_strategies(self):
        """Test manual plan with multiple strategies."""
        plan = self.service._manual_plan(
            "find auth code",
            ["graph", "vector", "filesystem", "git"],
        )

        assert len(plan) == 4
        strategy_types = [s.strategy_type for s in plan]
        assert "graph" in strategy_types
        assert "vector" in strategy_types
        assert "filesystem" in strategy_types
        assert "git" in strategy_types

    def test_manual_plan_empty_strategies(self):
        """Test manual plan with no strategies."""
        plan = self.service._manual_plan("test", [])

        assert plan == []


# =============================================================================
# Search Task Building Tests
# =============================================================================


class TestBuildSearchTasks:
    """Tests for building search tasks from plan."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ContextRetrievalService(
            neptune_client=MagicMock(),
            opensearch_client=MagicMock(),
            llm_client=MagicMock(),
            embedding_service=MagicMock(),
            git_repo_path="/test/repo",
        )

    def test_build_tasks_graph(self):
        """Test building graph search task."""
        plan = [MockSearchStrategy(strategy_type="graph", query="find deps")]

        tasks = self.service._build_search_tasks(plan)

        assert len(tasks) == 1
        assert tasks[0][0] == "graph"

    def test_build_tasks_vector(self):
        """Test building vector search task."""
        plan = [MockSearchStrategy(strategy_type="vector", query="semantic")]

        tasks = self.service._build_search_tasks(plan)

        assert len(tasks) == 1
        assert tasks[0][0] == "vector"

    def test_build_tasks_filesystem(self):
        """Test building filesystem search task."""
        plan = [MockSearchStrategy(strategy_type="filesystem", query="*.py")]

        tasks = self.service._build_search_tasks(plan)

        assert len(tasks) == 1
        assert tasks[0][0] == "filesystem"

    def test_build_tasks_git(self):
        """Test building git search task."""
        plan = [MockSearchStrategy(strategy_type="git", query="recent")]

        tasks = self.service._build_search_tasks(plan)

        assert len(tasks) == 1
        assert tasks[0][0] == "git"

    def test_build_tasks_multiple(self):
        """Test building multiple search tasks."""
        plan = [
            MockSearchStrategy(strategy_type="graph", query="q1"),
            MockSearchStrategy(strategy_type="vector", query="q2"),
        ]

        tasks = self.service._build_search_tasks(plan)

        assert len(tasks) == 2


# =============================================================================
# Result Categorization Tests
# =============================================================================


class TestCategorizeSearchResults:
    """Tests for categorizing search results."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ContextRetrievalService(
            neptune_client=MagicMock(),
            opensearch_client=MagicMock(),
            llm_client=MagicMock(),
            embedding_service=MagicMock(),
            git_repo_path="/test/repo",
        )

    def test_categorize_graph_results(self):
        """Test categorizing graph results."""
        tasks = [("graph", MagicMock())]
        results = [[MockFileMatch(file_path="/src/graph.py")]]

        graph_results = []
        vector_results = []
        filesystem_results = []
        git_results = []

        self.service._categorize_search_results(
            tasks,
            results,
            graph_results,
            vector_results,
            filesystem_results,
            git_results,
        )

        assert len(graph_results) == 1
        assert graph_results[0].file_path == "/src/graph.py"
        assert len(vector_results) == 0

    def test_categorize_vector_results(self):
        """Test categorizing vector results."""
        tasks = [("vector", MagicMock())]
        results = [
            [
                MockFileMatch(file_path="/src/a.py"),
                MockFileMatch(file_path="/src/b.py"),
            ]
        ]

        graph_results = []
        vector_results = []
        filesystem_results = []
        git_results = []

        self.service._categorize_search_results(
            tasks,
            results,
            graph_results,
            vector_results,
            filesystem_results,
            git_results,
        )

        assert len(vector_results) == 2

    def test_categorize_handles_exceptions(self):
        """Test that exceptions are handled gracefully."""
        tasks = [("vector", MagicMock())]
        results = [Exception("Search failed")]

        graph_results = []
        vector_results = []
        filesystem_results = []
        git_results = []

        # Should not raise
        self.service._categorize_search_results(
            tasks,
            results,
            graph_results,
            vector_results,
            filesystem_results,
            git_results,
        )

        assert len(vector_results) == 0

    def test_categorize_handles_unexpected_types(self):
        """Test that unexpected result types are handled."""
        tasks = [("vector", MagicMock())]
        results = ["not a list"]  # Invalid type

        graph_results = []
        vector_results = []
        filesystem_results = []
        git_results = []

        # Should not raise
        self.service._categorize_search_results(
            tasks,
            results,
            graph_results,
            vector_results,
            filesystem_results,
            git_results,
        )

        assert len(vector_results) == 0

    def test_categorize_multiple_strategies(self):
        """Test categorizing results from multiple strategies."""
        tasks = [
            ("graph", MagicMock()),
            ("vector", MagicMock()),
            ("filesystem", MagicMock()),
            ("git", MagicMock()),
        ]
        results = [
            [MockFileMatch(file_path="/g.py")],
            [MockFileMatch(file_path="/v.py")],
            [MockFileMatch(file_path="/f.py")],
            [MockFileMatch(file_path="/git.py")],
        ]

        graph_results = []
        vector_results = []
        filesystem_results = []
        git_results = []

        self.service._categorize_search_results(
            tasks,
            results,
            graph_results,
            vector_results,
            filesystem_results,
            git_results,
        )

        assert len(graph_results) == 1
        assert len(vector_results) == 1
        assert len(filesystem_results) == 1
        assert len(git_results) == 1


# =============================================================================
# Individual Search Method Tests
# =============================================================================


class TestSearchMethods:
    """Tests for individual search methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ContextRetrievalService(
            neptune_client=MagicMock(),
            opensearch_client=MagicMock(),
            llm_client=MagicMock(),
            embedding_service=MagicMock(),
            git_repo_path="/test/repo",
        )

    @pytest.mark.asyncio
    async def test_graph_search_returns_empty(self):
        """Test that graph search returns empty (pending implementation)."""
        results = await self.service._graph_search("find dependencies")

        assert results == []

    @pytest.mark.asyncio
    async def test_vector_search_calls_navigator(self):
        """Test that vector search uses filesystem navigator."""
        mock_results = [MockFileMatch(file_path="/src/test.py")]
        self.service.fs_navigator.search = AsyncMock(return_value=mock_results)

        results = await self.service._vector_search("semantic query")

        self.service.fs_navigator.search.assert_called_once()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_vector_search_handles_error(self):
        """Test that vector search handles errors gracefully."""
        self.service.fs_navigator.search = AsyncMock(
            side_effect=Exception("Search error")
        )

        results = await self.service._vector_search("query")

        assert results == []

    @pytest.mark.asyncio
    async def test_filesystem_search_calls_navigator(self):
        """Test that filesystem search uses navigator."""
        mock_results = [MockFileMatch(file_path="/src/file.py")]
        self.service.fs_navigator.search = AsyncMock(return_value=mock_results)

        results = await self.service._filesystem_search("*.py")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_filesystem_search_handles_error(self):
        """Test that filesystem search handles errors."""
        self.service.fs_navigator.search = AsyncMock(side_effect=Exception("FS error"))

        results = await self.service._filesystem_search("*.py")

        assert results == []

    @pytest.mark.asyncio
    async def test_git_search_calls_navigator(self):
        """Test that git search uses navigator."""
        mock_results = [MockFileMatch(file_path="/src/recent.py")]
        self.service.fs_navigator.search = AsyncMock(return_value=mock_results)

        results = await self.service._git_search("files changed last 7 days")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_git_search_handles_error(self):
        """Test that git search handles errors."""
        self.service.fs_navigator.search = AsyncMock(side_effect=Exception("Git error"))

        results = await self.service._git_search("recent")

        assert results == []


# =============================================================================
# Parallel Search Execution Tests
# =============================================================================


class TestParallelSearchExecution:
    """Tests for parallel search execution."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ContextRetrievalService(
            neptune_client=MagicMock(),
            opensearch_client=MagicMock(),
            llm_client=MagicMock(),
            embedding_service=MagicMock(),
            git_repo_path="/test/repo",
        )

    @pytest.mark.asyncio
    async def test_execute_parallel_searches_empty_plan(self):
        """Test parallel execution with empty plan."""
        results = await self.service._execute_parallel_searches([])

        graph, vector, fs, git = results
        assert graph == []
        assert vector == []
        assert fs == []
        assert git == []

    @pytest.mark.asyncio
    async def test_execute_parallel_searches_single_strategy(self):
        """Test parallel execution with single strategy."""
        self.service.fs_navigator.search = AsyncMock(
            return_value=[MockFileMatch(file_path="/test.py")]
        )

        plan = [MockSearchStrategy(strategy_type="vector", query="test")]
        results = await self.service._execute_parallel_searches(plan)

        graph, vector, fs, git = results
        assert len(vector) == 1


# =============================================================================
# Full Retrieval Workflow Tests
# =============================================================================


class TestRetrieveContext:
    """Tests for full context retrieval workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ContextRetrievalService(
            neptune_client=MagicMock(),
            opensearch_client=MagicMock(),
            llm_client=MagicMock(),
            embedding_service=MagicMock(),
            git_repo_path="/test/repo",
        )

    @pytest.mark.asyncio
    async def test_retrieve_context_with_manual_strategies(self):
        """Test context retrieval with manual strategy list."""
        # Mock navigator
        self.service.fs_navigator.search = AsyncMock(
            return_value=[MockFileMatch(file_path="/src/auth.py")]
        )

        # Mock synthesizer
        mock_response = MockContextResponse(
            files=[{"path": "/src/auth.py"}],
            total_tokens=500,
        )
        self.service.result_synthesizer.synthesize = MagicMock(
            return_value=mock_response
        )

        result = await self.service.retrieve_context(
            query="find auth code",
            context_budget=10000,
            strategies=["vector"],
        )

        assert result.total_tokens == 500

    @pytest.mark.asyncio
    async def test_retrieve_context_uses_query_planner(self):
        """Test that context retrieval uses query planner when no strategies given."""
        # Mock planner
        mock_plan = [MockSearchStrategy(strategy_type="vector", query="test")]
        self.service.query_planner.plan_search = AsyncMock(return_value=mock_plan)

        # Mock navigator
        self.service.fs_navigator.search = AsyncMock(return_value=[])

        # Mock synthesizer
        mock_response = MockContextResponse(files=[], total_tokens=0)
        self.service.result_synthesizer.synthesize = MagicMock(
            return_value=mock_response
        )

        await self.service.retrieve_context(
            query="find code",
            context_budget=5000,
        )

        self.service.query_planner.plan_search.assert_called_once()


# =============================================================================
# Graph Search Tests
# =============================================================================


class TestGraphSearch:
    """Tests for Neptune graph search functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ContextRetrievalService(
            neptune_client=MagicMock(),
            opensearch_client=MagicMock(),
            llm_client=MagicMock(),
            embedding_service=MagicMock(),
            git_repo_path="/test/repo",
        )

    def test_extract_graph_terms_camel_case(self):
        """Test extraction of CamelCase class names."""
        terms = self.service._extract_graph_terms("Find the SecurityValidator class")
        assert "SecurityValidator" in terms

    def test_extract_graph_terms_snake_case(self):
        """Test extraction of snake_case function names."""
        terms = self.service._extract_graph_terms("find validate_input function")
        assert "validate_input" in terms

    def test_extract_graph_terms_quoted(self):
        """Test extraction of quoted strings."""
        terms = self.service._extract_graph_terms(
            'find references to "authenticate_user"'
        )
        assert "authenticate_user" in terms

    def test_extract_graph_terms_entity_indicators(self):
        """Test extraction following entity keywords."""
        terms = self.service._extract_graph_terms(
            "class UserService extends BaseService"
        )
        assert "UserService" in terms
        assert "BaseService" in terms

    def test_extract_graph_terms_filters_common_words(self):
        """Test that common words are filtered out."""
        terms = self.service._extract_graph_terms("Find the User class")
        # "Find" and "The" should be filtered out
        assert "Find" not in terms
        assert "The" not in terms
        assert "User" in terms

    def test_extract_graph_terms_deduplicates(self):
        """Test that duplicate terms are removed."""
        terms = self.service._extract_graph_terms(
            "AuthService calls AuthService.validate and AuthService.check"
        )
        # Should only have one AuthService
        auth_count = sum(1 for t in terms if t.lower() == "authservice")
        assert auth_count == 1

    def test_extract_graph_terms_limits_results(self):
        """Test that results are limited to prevent expensive queries."""
        # Create query with many terms
        many_terms = " ".join([f"Term{i}" for i in range(20)])
        terms = self.service._extract_graph_terms(many_terms)
        assert len(terms) <= 10

    def test_detect_query_type_call_graph(self):
        """Test detection of call graph queries."""
        query_type = self.service._detect_graph_query_type(
            "what functions call validate_input"
        )
        assert query_type.value == "call_graph"

    def test_detect_query_type_dependencies(self):
        """Test detection of dependency queries."""
        query_type = self.service._detect_graph_query_type(
            "what does auth_service import"
        )
        assert query_type.value == "dependencies"

    def test_detect_query_type_inheritance(self):
        """Test detection of inheritance queries."""
        query_type = self.service._detect_graph_query_type(
            "what classes extend BaseValidator"
        )
        assert query_type.value == "inheritance"

    def test_detect_query_type_references(self):
        """Test detection of reference queries."""
        query_type = self.service._detect_graph_query_type(
            "find all references to UserModel"
        )
        assert query_type.value == "references"

    def test_detect_query_type_default(self):
        """Test default query type for general queries."""
        query_type = self.service._detect_graph_query_type(
            "find SecurityValidator related code"
        )
        assert query_type.value == "related"

    def test_get_relationship_types_call_graph(self):
        """Test relationship types for call graph."""
        # Get GraphQueryType from the same module as the service
        from src.services.context_retrieval_service import GraphQueryType

        # Use the same enum instance for lookup
        for qt in GraphQueryType:
            if qt.value == "call_graph":
                types = self.service._get_relationship_types(qt)
                assert types is not None
                assert "CALLS" in types
                assert "CALLED_BY" in types
                break

    def test_get_relationship_types_inheritance(self):
        """Test relationship types for inheritance."""
        from src.services.context_retrieval_service import GraphQueryType

        for qt in GraphQueryType:
            if qt.value == "inheritance":
                types = self.service._get_relationship_types(qt)
                assert types is not None
                assert "EXTENDS" in types
                assert "IMPLEMENTS" in types
                break

    def test_get_relationship_types_references_returns_none(self):
        """Test that REFERENCES returns None for all relationships."""
        from src.services.context_retrieval_service import GraphQueryType

        for qt in GraphQueryType:
            if qt.value == "references":
                types = self.service._get_relationship_types(qt)
                assert types is None
                break

    def test_detect_language_python(self):
        """Test Python language detection."""
        lang = self.service._detect_language("src/services/auth.py")
        assert lang == "python"

    def test_detect_language_javascript(self):
        """Test JavaScript language detection."""
        lang = self.service._detect_language("src/components/App.jsx")
        assert lang == "javascript"

    def test_detect_language_typescript(self):
        """Test TypeScript language detection."""
        lang = self.service._detect_language("src/types/index.ts")
        assert lang == "typescript"

    def test_detect_language_unknown(self):
        """Test unknown extension defaults to 'unknown'."""
        lang = self.service._detect_language("file.xyz")
        assert lang == "unknown"

    def test_convert_graph_results_creates_file_matches(self):
        """Test conversion of graph results to FileMatch objects."""
        graph_results = [
            {
                "id": "src/auth.py::AuthService",
                "name": "AuthService",
                "type": "class",
                "file_path": "src/auth.py",
                "line_number": 10,
            },
            {
                "id": "src/validators.py::validate",
                "name": "validate",
                "type": "function",
                "file_path": "src/validators.py",
                "line_number": 25,
            },
        ]

        matches = self.service._convert_graph_results_to_file_matches(graph_results)

        assert len(matches) == 2
        assert matches[0].file_path == "src/auth.py"
        assert matches[0].language == "python"
        assert matches[1].file_path == "src/validators.py"

    def test_convert_graph_results_deduplicates_by_path(self):
        """Test that duplicate file paths are removed."""
        graph_results = [
            {"file_path": "src/auth.py", "name": "func1"},
            {"file_path": "src/auth.py", "name": "func2"},  # Same file
            {"file_path": "src/other.py", "name": "func3"},
        ]

        matches = self.service._convert_graph_results_to_file_matches(graph_results)

        assert len(matches) == 2  # Only unique paths

    def test_convert_graph_results_detects_test_files(self):
        """Test that test files are correctly identified."""
        graph_results = [
            {"file_path": "tests/test_auth.py", "name": "test_func"},
        ]

        matches = self.service._convert_graph_results_to_file_matches(graph_results)

        assert matches[0].is_test_file is True

    def test_convert_graph_results_detects_config_files(self):
        """Test that config files are correctly identified."""
        graph_results = [
            {"file_path": "config/settings.py", "name": "Settings"},
        ]

        matches = self.service._convert_graph_results_to_file_matches(graph_results)

        assert matches[0].is_config_file is True

    def test_build_gremlin_query_call_graph(self):
        """Test Gremlin query building for call graphs."""
        from src.services.context_retrieval_service import GraphQueryType

        # Find the CALL_GRAPH enum member
        for qt in GraphQueryType:
            if qt.value == "call_graph":
                query = self.service._build_gremlin_query(["validate_input"], qt, 50)
                assert "g.V()" in query
                assert "validate_input" in query
                assert "CALLS" in query
                assert "limit(50)" in query
                break

    def test_build_gremlin_query_escapes_quotes(self):
        """Test that single quotes are escaped in Gremlin queries."""
        from src.services.context_retrieval_service import GraphQueryType

        for qt in GraphQueryType:
            if qt.value == "related":
                query = self.service._build_gremlin_query(["test'name"], qt, 10)
                # Should escape the single quote
                assert "\\'" in query or "test\\'name" in query
                break

    @pytest.mark.asyncio
    async def test_graph_search_with_neptune_service(self):
        """Test graph search using NeptuneGraphService API."""
        # Mock Neptune service with find_related_code and search_by_name
        self.service.neptune.find_related_code = MagicMock(
            return_value=[
                {
                    "id": "src/auth.py::AuthService",
                    "name": "AuthService",
                    "type": "class",
                    "file_path": "src/auth.py",
                    "line_number": 10,
                }
            ]
        )
        self.service.neptune.search_by_name = MagicMock(return_value=[])

        results = await self.service._graph_search("find AuthService class")

        assert len(results) >= 1
        self.service.neptune.find_related_code.assert_called()

    @pytest.mark.asyncio
    async def test_graph_search_handles_no_terms(self):
        """Test graph search returns empty when no terms extracted."""
        results = await self.service._graph_search("the a an")

        assert results == []

    @pytest.mark.asyncio
    async def test_graph_search_handles_exception(self):
        """Test graph search handles exceptions gracefully."""
        self.service.neptune.find_related_code = MagicMock(
            side_effect=Exception("Neptune error")
        )

        # Should not raise, should return empty list
        results = await self.service._graph_search("find AuthService")

        assert results == []

    @pytest.mark.asyncio
    async def test_execute_graph_query_uses_neptune_api(self):
        """Test that _execute_graph_query calls Neptune methods."""
        from src.services.context_retrieval_service import GraphQueryType

        self.service.neptune.find_related_code = MagicMock(return_value=[])
        self.service.neptune.search_by_name = MagicMock(return_value=[])

        # Get the RELATED enum member from the same module
        for qt in GraphQueryType:
            if qt.value == "related":
                await self.service._execute_graph_query(
                    ["TestClass"], qt, max_results=10
                )
                break

        self.service.neptune.find_related_code.assert_called()

    @pytest.mark.asyncio
    async def test_execute_graph_query_deduplicates(self):
        """Test that duplicate results are removed."""
        from src.services.context_retrieval_service import GraphQueryType

        # Return duplicates from both methods
        duplicate_entity = {
            "id": "src/test.py::Test",
            "file_path": "src/test.py",
        }
        self.service.neptune.find_related_code = MagicMock(
            return_value=[duplicate_entity]
        )
        self.service.neptune.search_by_name = MagicMock(return_value=[duplicate_entity])

        # Get the RELATED enum member from the same module
        for qt in GraphQueryType:
            if qt.value == "related":
                results = await self.service._execute_graph_query(
                    ["Test"], qt, max_results=10
                )
                # Should only have one result despite duplicates
                assert len(results) == 1
                break


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
