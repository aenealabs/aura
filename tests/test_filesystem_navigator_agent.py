"""
Tests for filesystem_navigator_agent.py

Comprehensive tests for the FilesystemNavigatorAgent which provides
intelligent filesystem exploration with adaptive search refinement.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.filesystem_navigator_agent import FileMatch, FilesystemNavigatorAgent

# =============================================================================
# Test FileMatch Dataclass
# =============================================================================


class TestFileMatch:
    """Tests for FileMatch dataclass."""

    def test_file_match_creation(self):
        """Test creating a FileMatch instance."""
        match = FileMatch(
            file_path="src/auth/login.py",
            file_size=5000,
            last_modified=datetime.now(),
            language="python",
            num_lines=200,
        )

        assert match.file_path == "src/auth/login.py"
        assert match.file_size == 5000
        assert match.language == "python"
        assert match.num_lines == 200
        assert match.relevance_score == 0.0  # Default
        assert match.is_test_file is False  # Default
        assert match.is_config_file is False  # Default

    def test_file_match_with_optional_fields(self):
        """Test FileMatch with optional fields."""
        match = FileMatch(
            file_path="tests/test_auth.py",
            file_size=2000,
            last_modified=datetime.now(),
            language="python",
            num_lines=100,
            last_author="developer@example.com",
            relevance_score=9.5,
            is_test_file=True,
            is_config_file=False,
            estimated_tokens=150,
        )

        assert match.last_author == "developer@example.com"
        assert match.relevance_score == 9.5
        assert match.is_test_file is True
        assert match.estimated_tokens == 150

    def test_file_match_hash(self):
        """Test FileMatch is hashable by file_path."""
        match1 = FileMatch(
            file_path="src/app.py",
            file_size=1000,
            last_modified=datetime.now(),
            language="python",
            num_lines=50,
        )
        match2 = FileMatch(
            file_path="src/app.py",
            file_size=2000,  # Different size, same path
            last_modified=datetime.now(),
            language="python",
            num_lines=100,
        )
        match3 = FileMatch(
            file_path="src/other.py",
            file_size=1000,
            last_modified=datetime.now(),
            language="python",
            num_lines=50,
        )

        # Same path = same hash
        assert hash(match1) == hash(match2)
        # Different path = different hash
        assert hash(match1) != hash(match3)

    def test_file_match_equality(self):
        """Test FileMatch equality by file_path."""
        match1 = FileMatch(
            file_path="src/app.py",
            file_size=1000,
            last_modified=datetime.now(),
            language="python",
            num_lines=50,
        )
        match2 = FileMatch(
            file_path="src/app.py",
            file_size=2000,
            last_modified=datetime.now(),
            language="python",
            num_lines=100,
        )
        match3 = FileMatch(
            file_path="src/other.py",
            file_size=1000,
            last_modified=datetime.now(),
            language="python",
            num_lines=50,
        )

        assert match1 == match2  # Same path
        assert match1 != match3  # Different path
        assert match1 != "src/app.py"  # Not a FileMatch

    def test_file_match_in_set(self):
        """Test FileMatch can be used in sets for deduplication."""
        matches = [
            FileMatch(
                file_path="src/a.py",
                file_size=100,
                last_modified=datetime.now(),
                language="python",
                num_lines=10,
            ),
            FileMatch(
                file_path="src/a.py",  # Duplicate
                file_size=200,
                last_modified=datetime.now(),
                language="python",
                num_lines=20,
            ),
            FileMatch(
                file_path="src/b.py",
                file_size=100,
                last_modified=datetime.now(),
                language="python",
                num_lines=10,
            ),
        ]

        unique = set(matches)
        assert len(unique) == 2  # a.py and b.py


# =============================================================================
# Test FilesystemNavigatorAgent Initialization
# =============================================================================


class TestFilesystemNavigatorAgentInit:
    """Tests for FilesystemNavigatorAgent initialization."""

    def test_init_with_required_params(self):
        """Test initialization with required parameters."""
        mock_opensearch = MagicMock()
        mock_embeddings = MagicMock()

        agent = FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
        )

        assert agent.opensearch == mock_opensearch
        assert agent.embeddings == mock_embeddings
        assert agent.filesystem_index == "aura-filesystem-metadata"
        assert agent.llm_client is None

    def test_init_with_custom_index(self):
        """Test initialization with custom index name."""
        mock_opensearch = MagicMock()
        mock_embeddings = MagicMock()

        agent = FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
            filesystem_index="custom-index",
        )

        assert agent.filesystem_index == "custom-index"

    def test_init_with_llm_client(self):
        """Test initialization with LLM client."""
        mock_opensearch = MagicMock()
        mock_embeddings = MagicMock()
        mock_llm = MagicMock()

        agent = FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
            llm_client=mock_llm,
        )

        assert agent.llm_client == mock_llm


# =============================================================================
# Test Search Methods
# =============================================================================


class TestFilesystemNavigatorSearch:
    """Tests for search methods."""

    @pytest.fixture
    def mock_opensearch_response(self):
        """Provide mock OpenSearch response."""
        return {
            "hits": {
                "hits": [
                    {
                        "_score": 10.5,
                        "_source": {
                            "file_path": "src/auth/service.py",
                            "file_size": 5000,
                            "last_modified": "2025-01-01T10:00:00Z",
                            "language": "python",
                            "num_lines": 250,
                            "last_author": "alice@example.com",
                            "is_test_file": False,
                            "is_config_file": False,
                        },
                    },
                    {
                        "_score": 8.0,
                        "_source": {
                            "file_path": "src/utils/jwt.py",
                            "file_size": 3000,
                            "last_modified": "2025-01-02T15:00:00Z",
                            "language": "python",
                            "num_lines": 150,
                            "is_test_file": False,
                            "is_config_file": False,
                        },
                    },
                ]
            }
        }

    @pytest.fixture
    def agent(self):
        """Provide agent instance with mocks."""
        mock_opensearch = AsyncMock()
        mock_embeddings = AsyncMock()
        return FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
        )

    @pytest.mark.asyncio
    async def test_search_pattern_type(self, agent, mock_opensearch_response):
        """Test pattern-based search."""
        agent.opensearch.search.return_value = mock_opensearch_response

        results = await agent.search(
            pattern="**/auth/*.py",
            search_type="pattern",
            max_results=50,
        )

        assert len(results) == 2
        assert results[0].file_path == "src/auth/service.py"
        assert results[0].relevance_score == 10.5
        agent.opensearch.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_semantic_type(self, agent, mock_opensearch_response):
        """Test semantic search."""
        agent.opensearch.search.return_value = mock_opensearch_response
        agent.embeddings.generate_embedding.return_value = [0.1] * 1536

        results = await agent.search(
            pattern="authentication logic",
            search_type="semantic",
            max_results=50,
        )

        assert len(results) == 2
        agent.embeddings.generate_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_recent_changes_type(self, agent, mock_opensearch_response):
        """Test recent changes search."""
        agent.opensearch.search.return_value = mock_opensearch_response

        results = await agent.search(
            pattern="*.py",
            search_type="recent_changes",
            max_results=50,
        )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_invalid_type(self, agent):
        """Test search with invalid type raises error."""
        with pytest.raises(ValueError, match="Unknown search type"):
            await agent.search(
                pattern="test",
                search_type="invalid_type",
            )

    @pytest.mark.asyncio
    async def test_search_with_filters(self, agent, mock_opensearch_response):
        """Test search with filters applied."""
        agent.opensearch.search.return_value = mock_opensearch_response

        results = await agent.search(
            pattern="*.py",
            search_type="pattern",
            filters={"language": "python", "is_test_file": False},
        )

        assert len(results) == 2
        # Verify filters were added to query
        call_args = agent.opensearch.search.call_args
        query_body = call_args[1]["body"]
        assert "filter" in query_body["query"]["bool"]


# =============================================================================
# Test Pattern Search
# =============================================================================


class TestPatternSearch:
    """Tests for pattern-based search."""

    @pytest.fixture
    def agent(self):
        """Provide agent instance."""
        mock_opensearch = AsyncMock()
        mock_embeddings = AsyncMock()
        return FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
        )

    @pytest.mark.asyncio
    async def test_pattern_search_builds_correct_query(self, agent):
        """Test pattern search builds correct OpenSearch query."""
        agent.opensearch.search.return_value = {"hits": {"hits": []}}

        await agent._pattern_search("**/test_*.py", max_results=20)

        call_args = agent.opensearch.search.call_args
        query = call_args[1]["body"]

        assert "wildcard" in query["query"]["bool"]["must"][0]
        assert (
            query["query"]["bool"]["must"][0]["wildcard"]["file_path.keyword"]["value"]
            == "**/test_*.py"
        )
        assert query["size"] == 20

    @pytest.mark.asyncio
    async def test_pattern_search_with_filters(self, agent):
        """Test pattern search with additional filters."""
        agent.opensearch.search.return_value = {"hits": {"hits": []}}

        filters = {"language": "python", "min_lines": 10}
        await agent._pattern_search("*.py", max_results=50, filters=filters)

        call_args = agent.opensearch.search.call_args
        query = call_args[1]["body"]
        assert "filter" in query["query"]["bool"]


# =============================================================================
# Test Semantic Search
# =============================================================================


class TestSemanticSearch:
    """Tests for semantic search."""

    @pytest.fixture
    def agent(self):
        """Provide agent instance."""
        mock_opensearch = AsyncMock()
        mock_embeddings = AsyncMock()
        mock_embeddings.generate_embedding.return_value = [0.1] * 1536
        return FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
        )

    @pytest.mark.asyncio
    async def test_semantic_search_generates_embedding(self, agent):
        """Test semantic search generates query embedding."""
        agent.opensearch.search.return_value = {"hits": {"hits": []}}

        await agent._semantic_search("find authentication", max_results=50)

        agent.embeddings.generate_embedding.assert_called_once_with(
            "find authentication"
        )

    @pytest.mark.asyncio
    async def test_semantic_search_uses_knn(self, agent):
        """Test semantic search builds KNN query."""
        agent.opensearch.search.return_value = {"hits": {"hits": []}}

        await agent._semantic_search("authentication", max_results=30)

        call_args = agent.opensearch.search.call_args
        query = call_args[1]["body"]

        # Should use script_score for cosine similarity
        assert "should" in query["query"]["bool"]
        should_clauses = query["query"]["bool"]["should"]
        assert len(should_clauses) >= 2  # path and docstring embeddings


# =============================================================================
# Test Recent Changes Search
# =============================================================================


class TestRecentChangesSearch:
    """Tests for recent changes search."""

    @pytest.fixture
    def agent(self):
        """Provide agent instance."""
        mock_opensearch = AsyncMock()
        mock_embeddings = AsyncMock()
        return FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
        )

    @pytest.mark.asyncio
    async def test_recent_changes_search_includes_date_range(self, agent):
        """Test recent changes search includes date range filter."""
        agent.opensearch.search.return_value = {"hits": {"hits": []}}

        await agent._recent_changes_search("*.py", max_results=50, days=7)

        call_args = agent.opensearch.search.call_args
        query = call_args[1]["body"]

        # Should have range query on last_modified
        must_clauses = query["query"]["bool"]["must"]
        range_clause = next((c for c in must_clauses if "range" in c), None)
        assert range_clause is not None
        assert "last_modified" in range_clause["range"]


# =============================================================================
# Test Find Related Files
# =============================================================================


class TestFindRelatedFiles:
    """Tests for finding related files."""

    @pytest.fixture
    def agent(self):
        """Provide agent instance."""
        mock_opensearch = AsyncMock()
        mock_embeddings = AsyncMock()
        return FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
        )

    @pytest.mark.asyncio
    async def test_find_related_files_returns_categories(self, agent):
        """Test find_related_files returns proper categories."""
        agent.opensearch.search.return_value = {"hits": {"hits": []}}

        related = await agent.find_related_files("src/services/auth.py")

        assert "tests" in related
        assert "same_module" in related
        assert "config" in related
        assert isinstance(related["tests"], list)
        assert isinstance(related["same_module"], list)
        assert isinstance(related["config"], list)

    @pytest.mark.asyncio
    async def test_find_related_files_searches_test_patterns(self, agent):
        """Test find_related_files searches for test files."""
        agent.opensearch.search.return_value = {"hits": {"hits": []}}

        await agent.find_related_files("src/services/auth_service.py")

        # Should search for test patterns
        calls = agent.opensearch.search.call_args_list
        patterns_searched = []
        for call in calls:
            query = call[1]["body"]["query"]["bool"]["must"][0]
            if "wildcard" in query:
                patterns_searched.append(
                    query["wildcard"]["file_path.keyword"]["value"]
                )

        assert any("test_auth_service" in p for p in patterns_searched)


# =============================================================================
# Test Intelligent Search
# =============================================================================


class TestIntelligentSearch:
    """Tests for LLM-enhanced intelligent search."""

    @pytest.fixture
    def agent_with_llm(self):
        """Provide agent with LLM client."""
        mock_opensearch = AsyncMock()
        mock_embeddings = AsyncMock()
        mock_embeddings.generate_embedding.return_value = [0.1] * 1536
        mock_llm = AsyncMock()
        return FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
            llm_client=mock_llm,
        )

    @pytest.fixture
    def agent_without_llm(self):
        """Provide agent without LLM client."""
        mock_opensearch = AsyncMock()
        mock_embeddings = AsyncMock()
        mock_embeddings.generate_embedding.return_value = [0.1] * 1536
        return FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
        )

    @pytest.mark.asyncio
    async def test_intelligent_search_without_llm_falls_back(self, agent_without_llm):
        """Test intelligent search falls back to semantic search without LLM."""
        agent_without_llm.opensearch.search.return_value = {"hits": {"hits": []}}

        results = await agent_without_llm.intelligent_search("find auth logic")

        # Should fall back to semantic search
        assert results == []
        agent_without_llm.embeddings.generate_embedding.assert_called()

    @pytest.mark.asyncio
    async def test_intelligent_search_with_llm(self, agent_with_llm):
        """Test intelligent search uses LLM for query analysis."""
        agent_with_llm.opensearch.search.return_value = {"hits": {"hits": []}}
        agent_with_llm.llm_client.generate.return_value = (
            '{"patterns": ["**/auth/*.py"], "semantic_terms": ["authentication"]}'
        )

        await agent_with_llm.intelligent_search("find auth logic")

        # LLM should be called for query analysis
        agent_with_llm.llm_client.generate.assert_called()

    @pytest.mark.asyncio
    async def test_intelligent_search_deduplicates_results(self, agent_with_llm):
        """Test intelligent search deduplicates results."""
        # Return same file from multiple searches
        response = {
            "hits": {
                "hits": [
                    {
                        "_score": 10.0,
                        "_source": {
                            "file_path": "src/auth.py",
                            "file_size": 1000,
                            "last_modified": "2025-01-01T00:00:00Z",
                            "language": "python",
                            "num_lines": 100,
                        },
                    }
                ]
            }
        }
        agent_with_llm.opensearch.search.return_value = response
        agent_with_llm.llm_client.generate.return_value = (
            '{"patterns": ["**/auth/*.py", "**/auth*.py"], "semantic_terms": ["auth"]}'
        )

        results = await agent_with_llm.intelligent_search("find auth")

        # Should deduplicate
        file_paths = [r.file_path for r in results]
        assert len(file_paths) == len(set(file_paths))


# =============================================================================
# Test Query Intent Analysis
# =============================================================================


class TestQueryIntentAnalysis:
    """Tests for LLM query intent analysis."""

    @pytest.fixture
    def agent_with_llm(self):
        """Provide agent with LLM client."""
        mock_opensearch = AsyncMock()
        mock_embeddings = AsyncMock()
        mock_llm = AsyncMock()
        return FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
            llm_client=mock_llm,
        )

    @pytest.mark.asyncio
    async def test_analyze_query_intent_returns_plan(self, agent_with_llm):
        """Test query intent analysis returns search plan."""
        agent_with_llm.llm_client.generate.return_value = """
        {
            "intent": "Find authentication code",
            "patterns": ["**/auth/*.py"],
            "semantic_terms": ["authentication", "login"],
            "file_types": [".py"],
            "exclude_tests": true
        }
        """

        plan = await agent_with_llm._analyze_query_intent("find auth code")

        assert "patterns" in plan
        assert "semantic_terms" in plan

    @pytest.mark.asyncio
    async def test_analyze_query_intent_without_llm(self):
        """Test query intent analysis returns default without LLM."""
        agent = FilesystemNavigatorAgent(
            opensearch_client=AsyncMock(),
            embedding_service=AsyncMock(),
        )

        plan = await agent._analyze_query_intent("find auth")

        assert plan == {"semantic_terms": ["find auth"], "patterns": []}

    @pytest.mark.asyncio
    async def test_analyze_query_intent_handles_json_error(self, agent_with_llm):
        """Test query intent analysis handles JSON parse errors."""
        agent_with_llm.llm_client.generate.return_value = "not valid json"

        plan = await agent_with_llm._analyze_query_intent("find something")

        # Should return default plan
        assert "semantic_terms" in plan
        assert plan["semantic_terms"] == ["find something"]

    @pytest.mark.asyncio
    async def test_analyze_query_intent_handles_exception(self, agent_with_llm):
        """Test query intent analysis handles LLM exceptions."""
        agent_with_llm.llm_client.generate.side_effect = Exception("LLM error")

        plan = await agent_with_llm._analyze_query_intent("find something")

        # Should return default plan
        assert plan == {"semantic_terms": ["find something"], "patterns": []}


# =============================================================================
# Test LLM Ranking
# =============================================================================


class TestLLMRanking:
    """Tests for LLM result ranking."""

    @pytest.fixture
    def agent_with_llm(self):
        """Provide agent with LLM client."""
        mock_opensearch = AsyncMock()
        mock_embeddings = AsyncMock()
        mock_llm = AsyncMock()
        return FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
            llm_client=mock_llm,
        )

    @pytest.fixture
    def sample_results(self):
        """Provide sample FileMatch results."""
        return [
            FileMatch(
                file_path=f"src/file{i}.py",
                file_size=1000,
                last_modified=datetime.now(),
                language="python",
                num_lines=100,
            )
            for i in range(5)
        ]

    @pytest.mark.asyncio
    async def test_llm_rank_results_reorders(self, agent_with_llm, sample_results):
        """Test LLM ranking reorders results."""
        agent_with_llm.llm_client.generate.return_value = "[3, 1, 5, 2, 4]"

        ranked = await agent_with_llm._llm_rank_results(
            "find auth", sample_results, max_results=5
        )

        # Should reorder based on LLM ranking
        assert ranked[0].file_path == "src/file2.py"  # Index 3 in 1-based = index 2
        assert ranked[1].file_path == "src/file0.py"  # Index 1 in 1-based = index 0

    @pytest.mark.asyncio
    async def test_llm_rank_without_llm(self, sample_results):
        """Test ranking returns original order without LLM."""
        agent = FilesystemNavigatorAgent(
            opensearch_client=AsyncMock(),
            embedding_service=AsyncMock(),
        )

        ranked = await agent._llm_rank_results("query", sample_results, max_results=3)

        assert ranked == sample_results[:3]

    @pytest.mark.asyncio
    async def test_llm_rank_single_result(self, agent_with_llm):
        """Test ranking returns single result without LLM call."""
        result = FileMatch(
            file_path="src/single.py",
            file_size=100,
            last_modified=datetime.now(),
            language="python",
            num_lines=10,
        )

        ranked = await agent_with_llm._llm_rank_results(
            "query", [result], max_results=1
        )

        assert ranked == [result]
        agent_with_llm.llm_client.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_rank_handles_json_error(self, agent_with_llm, sample_results):
        """Test ranking handles JSON parse errors."""
        agent_with_llm.llm_client.generate.return_value = "not json"

        ranked = await agent_with_llm._llm_rank_results(
            "query", sample_results, max_results=5
        )

        # Should return original order
        assert ranked == sample_results

    @pytest.mark.asyncio
    async def test_llm_rank_handles_exception(self, agent_with_llm, sample_results):
        """Test ranking handles LLM exceptions."""
        agent_with_llm.llm_client.generate.side_effect = Exception("LLM error")

        ranked = await agent_with_llm._llm_rank_results(
            "query", sample_results, max_results=5
        )

        # Should return original order
        assert ranked == sample_results


# =============================================================================
# Test Embedding Generation
# =============================================================================


class TestEmbeddingGeneration:
    """Tests for text embedding generation."""

    @pytest.fixture
    def agent(self):
        """Provide agent instance."""
        mock_opensearch = AsyncMock()
        mock_embeddings = AsyncMock()
        mock_embeddings.generate_embedding.return_value = [0.1] * 1536
        return FilesystemNavigatorAgent(
            opensearch_client=mock_opensearch,
            embedding_service=mock_embeddings,
        )

    @pytest.mark.asyncio
    async def test_embed_text_generates_embedding(self, agent):
        """Test embedding is generated for valid text."""
        result = await agent._embed_text("authentication logic")

        assert len(result) == 1536
        agent.embeddings.generate_embedding.assert_called_once_with(
            "authentication logic"
        )

    @pytest.mark.asyncio
    async def test_embed_text_short_text_returns_zeros(self, agent):
        """Test short text returns zero embedding."""
        result = await agent._embed_text("ab")  # Less than MIN_TEXT_LENGTH

        assert result == [0.0] * 1536
        agent.embeddings.generate_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_text_empty_string_returns_zeros(self, agent):
        """Test empty string returns zero embedding."""
        result = await agent._embed_text("")

        assert result == [0.0] * 1536
        agent.embeddings.generate_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_text_handles_exception(self, agent):
        """Test embedding error returns zero embedding."""
        agent.embeddings.generate_embedding.side_effect = Exception("Embedding error")

        result = await agent._embed_text("valid text")

        assert result == [0.0] * 1536


# =============================================================================
# Test Filter Building
# =============================================================================


class TestFilterBuilding:
    """Tests for OpenSearch filter clause building."""

    @pytest.fixture
    def agent(self):
        """Provide agent instance."""
        return FilesystemNavigatorAgent(
            opensearch_client=AsyncMock(),
            embedding_service=AsyncMock(),
        )

    def test_build_filters_language(self, agent):
        """Test language filter."""
        filters = agent._build_filters({"language": "python"})

        assert len(filters) == 1
        assert filters[0] == {"term": {"language": "python"}}

    def test_build_filters_is_test_file(self, agent):
        """Test test file filter."""
        filters = agent._build_filters({"is_test_file": True})

        assert len(filters) == 1
        assert filters[0] == {"term": {"is_test_file": True}}

    def test_build_filters_is_config_file(self, agent):
        """Test config file filter."""
        filters = agent._build_filters({"is_config_file": True})

        assert len(filters) == 1
        assert filters[0] == {"term": {"is_config_file": True}}

    def test_build_filters_min_lines(self, agent):
        """Test minimum lines filter."""
        filters = agent._build_filters({"min_lines": 50})

        assert len(filters) == 1
        assert filters[0] == {"range": {"num_lines": {"gte": 50}}}

    def test_build_filters_max_lines(self, agent):
        """Test maximum lines filter."""
        filters = agent._build_filters({"max_lines": 500})

        assert len(filters) == 1
        assert filters[0] == {"range": {"num_lines": {"lte": 500}}}

    def test_build_filters_multiple(self, agent):
        """Test multiple filters combined."""
        filters = agent._build_filters(
            {
                "language": "python",
                "is_test_file": False,
                "min_lines": 10,
                "max_lines": 1000,
            }
        )

        assert len(filters) == 4


# =============================================================================
# Test OpenSearch Hit Parsing
# =============================================================================


class TestParseFileMatch:
    """Tests for parsing OpenSearch hits into FileMatch objects."""

    @pytest.fixture
    def agent(self):
        """Provide agent instance."""
        return FilesystemNavigatorAgent(
            opensearch_client=AsyncMock(),
            embedding_service=AsyncMock(),
        )

    def test_parse_file_match_full(self, agent):
        """Test parsing hit with all fields."""
        hit = {
            "_score": 10.5,
            "_source": {
                "file_path": "src/auth.py",
                "file_size": 5000,
                "last_modified": "2025-01-15T10:30:00Z",
                "language": "python",
                "num_lines": 250,
                "last_author": "developer@example.com",
                "is_test_file": False,
                "is_config_file": False,
            },
        }

        match = agent._parse_file_match(hit)

        assert match.file_path == "src/auth.py"
        assert match.file_size == 5000
        assert match.language == "python"
        assert match.num_lines == 250
        assert match.last_author == "developer@example.com"
        assert match.relevance_score == 10.5
        assert match.is_test_file is False
        assert match.is_config_file is False
        assert match.estimated_tokens == 375  # 250 * 1.5

    def test_parse_file_match_minimal(self, agent):
        """Test parsing hit with minimal fields."""
        hit = {
            "_source": {
                "file_path": "src/minimal.py",
            },
        }

        match = agent._parse_file_match(hit)

        assert match.file_path == "src/minimal.py"
        assert match.file_size == 0
        assert match.language == "unknown"
        assert match.num_lines == 0
        assert match.last_author is None
        assert match.relevance_score == 0.0
        assert match.is_test_file is False
        assert match.is_config_file is False
        assert match.estimated_tokens == 0

    def test_parse_file_match_missing_timestamp(self, agent):
        """Test parsing hit without last_modified uses current time."""
        hit = {
            "_source": {
                "file_path": "src/file.py",
            },
        }

        match = agent._parse_file_match(hit)

        # Should use current datetime (close enough)
        assert (datetime.now() - match.last_modified).total_seconds() < 1

    def test_parse_file_match_test_file(self, agent):
        """Test parsing test file."""
        hit = {
            "_source": {
                "file_path": "tests/test_auth.py",
                "is_test_file": True,
                "is_config_file": False,
            },
        }

        match = agent._parse_file_match(hit)

        assert match.is_test_file is True
        assert match.is_config_file is False

    def test_parse_file_match_config_file(self, agent):
        """Test parsing config file."""
        hit = {
            "_source": {
                "file_path": "config/settings.yaml",
                "is_test_file": False,
                "is_config_file": True,
            },
        }

        match = agent._parse_file_match(hit)

        assert match.is_test_file is False
        assert match.is_config_file is True
