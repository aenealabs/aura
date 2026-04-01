"""
Tests for Query Analyzer Service (ADR-028 Phase 3)

Tests LLM-powered query decomposition for complex code intelligence queries.
"""

import json
from unittest.mock import AsyncMock

import pytest

from src.services.query_analyzer import (
    QueryAnalyzer,
    QueryDecomposition,
    QueryIntent,
    SubQuery,
    create_query_analyzer,
)


class TestQueryIntent:
    """Test QueryIntent enum."""

    def test_intent_values(self):
        """Verify all intent values are defined."""
        assert QueryIntent.STRUCTURAL.value == "structural"
        assert QueryIntent.SEMANTIC.value == "semantic"
        assert QueryIntent.TEMPORAL.value == "temporal"
        assert QueryIntent.HYBRID.value == "hybrid"
        assert QueryIntent.NAVIGATIONAL.value == "navigational"


class TestSubQuery:
    """Test SubQuery dataclass."""

    def test_subquery_creation(self):
        """Test creating a SubQuery."""
        sq = SubQuery(
            id="sq_1",
            query_text="Find auth functions",
            intent=QueryIntent.STRUCTURAL,
            search_type="graph",
            priority=10,
            depends_on=["sq_0"],
            estimated_tokens=5000,
            reasoning="Test reasoning",
        )

        assert sq.id == "sq_1"
        assert sq.intent == QueryIntent.STRUCTURAL
        assert sq.search_type == "graph"
        assert sq.depends_on == ["sq_0"]

    def test_subquery_defaults(self):
        """Test SubQuery default values."""
        sq = SubQuery(
            id="sq_1",
            query_text="test",
            intent=QueryIntent.SEMANTIC,
            search_type="vector",
            priority=5,
        )

        assert sq.depends_on == []
        assert sq.estimated_tokens == 5000
        assert sq.reasoning == ""


class TestQueryDecomposition:
    """Test QueryDecomposition dataclass."""

    def test_decomposition_creation(self):
        """Test creating a QueryDecomposition."""
        subqueries = [
            SubQuery(
                id="sq_1",
                query_text="test",
                intent=QueryIntent.SEMANTIC,
                search_type="vector",
                priority=10,
            )
        ]

        decomp = QueryDecomposition(
            original_query="Find authentication code",
            intent=QueryIntent.SEMANTIC,
            subqueries=subqueries,
            execution_plan="parallel",
            reasoning="Simple query",
        )

        assert decomp.original_query == "Find authentication code"
        assert len(decomp.subqueries) == 1
        assert decomp.cache_key == ""


class TestQueryAnalyzerIntentClassification:
    """Test intent classification logic."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with mock LLM."""
        mock_llm = AsyncMock()
        return QueryAnalyzer(llm_client=mock_llm, enable_caching=False)

    @pytest.mark.asyncio
    async def test_classify_structural_intent(self, analyzer):
        """Test classification of structural queries."""
        intent = await analyzer._classify_intent(
            "Find functions that call the database"
        )
        assert intent == QueryIntent.STRUCTURAL

    @pytest.mark.asyncio
    async def test_classify_temporal_intent(self, analyzer):
        """Test classification of temporal queries."""
        intent = await analyzer._classify_intent("Files modified in the last week")
        assert intent == QueryIntent.TEMPORAL

    @pytest.mark.asyncio
    async def test_classify_semantic_intent(self, analyzer):
        """Test classification of semantic queries."""
        intent = await analyzer._classify_intent(
            "Code similar to error handling patterns"
        )
        assert intent == QueryIntent.SEMANTIC

    @pytest.mark.asyncio
    async def test_classify_navigational_intent(self, analyzer):
        """Test classification of navigational queries."""
        intent = await analyzer._classify_intent(
            "Where is the authentication service defined"
        )
        assert intent == QueryIntent.NAVIGATIONAL

    @pytest.mark.asyncio
    async def test_classify_hybrid_intent(self, analyzer):
        """Test classification of hybrid queries."""
        intent = await analyzer._classify_intent(
            "Functions that call the database and were modified recently"
        )
        assert intent == QueryIntent.HYBRID


class TestQueryAnalyzerSimpleQuery:
    """Test simple query handling."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with mock LLM."""
        mock_llm = AsyncMock()
        return QueryAnalyzer(llm_client=mock_llm, enable_caching=False)

    def test_is_simple_query_short(self, analyzer):
        """Test short queries are classified as simple."""
        assert analyzer._is_simple_query("Find auth code") is True

    def test_is_simple_query_conjunction(self, analyzer):
        """Test queries with conjunctions are complex."""
        assert analyzer._is_simple_query("Find auth code that calls database") is False

    def test_is_simple_query_long(self, analyzer):
        """Test long queries are complex."""
        assert (
            analyzer._is_simple_query(
                "Find all authentication functions in the codebase"
            )
            is False
        )

    def test_simple_decomposition(self, analyzer):
        """Test simple query decomposition."""
        decomp = analyzer._simple_decomposition("Find auth code", QueryIntent.SEMANTIC)

        assert decomp.original_query == "Find auth code"
        assert len(decomp.subqueries) == 1
        assert decomp.subqueries[0].search_type == "vector"
        assert decomp.execution_plan == "single"


class TestQueryAnalyzerComplexDecomposition:
    """Test complex query decomposition with LLM."""

    @pytest.fixture
    def analyzer_with_mock_response(self):
        """Create analyzer with mocked LLM response."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "intent": "hybrid",
                "reasoning": "Query combines structural and temporal aspects",
                "execution_plan": "parallel_then_intersect",
                "subqueries": [
                    {
                        "id": "sq_1",
                        "query_text": "functions with 'auth' in name",
                        "intent": "structural",
                        "search_type": "graph",
                        "priority": 9,
                        "depends_on": [],
                        "estimated_tokens": 3000,
                        "reasoning": "Find auth functions",
                    },
                    {
                        "id": "sq_2",
                        "query_text": "files modified recently",
                        "intent": "temporal",
                        "search_type": "git",
                        "priority": 7,
                        "depends_on": [],
                        "estimated_tokens": 2000,
                        "reasoning": "Find recent changes",
                    },
                ],
            }
        )
        return QueryAnalyzer(llm_client=mock_llm, enable_caching=False)

    @pytest.mark.asyncio
    async def test_complex_decomposition_calls_llm(self, analyzer_with_mock_response):
        """Test that complex queries use LLM for decomposition."""
        decomp = await analyzer_with_mock_response.analyze(
            "Find authentication functions that were modified recently",
            context_budget=50000,
        )

        assert decomp.intent == QueryIntent.HYBRID
        assert len(decomp.subqueries) == 2
        assert decomp.subqueries[0].search_type == "graph"
        assert decomp.subqueries[1].search_type == "git"

    @pytest.mark.asyncio
    async def test_complex_decomposition_respects_dependencies(
        self, analyzer_with_mock_response
    ):
        """Test dependency parsing in decomposition."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "intent": "hybrid",
                "reasoning": "Multi-hop query",
                "execution_plan": "sequential",
                "subqueries": [
                    {
                        "id": "sq_1",
                        "query_text": "find base classes",
                        "intent": "structural",
                        "search_type": "graph",
                        "priority": 10,
                        "depends_on": [],
                        "estimated_tokens": 3000,
                        "reasoning": "First find base classes",
                    },
                    {
                        "id": "sq_2",
                        "query_text": "find implementations",
                        "intent": "structural",
                        "search_type": "graph",
                        "priority": 8,
                        "depends_on": ["sq_1"],
                        "estimated_tokens": 3000,
                        "reasoning": "Then find implementations",
                    },
                ],
            }
        )
        analyzer = QueryAnalyzer(llm_client=mock_llm, enable_caching=False)

        decomp = await analyzer.analyze("Find implementations of base auth class")

        assert decomp.subqueries[1].depends_on == ["sq_1"]


class TestQueryAnalyzerFallback:
    """Test fallback behavior when LLM fails."""

    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self):
        """Test fallback decomposition when LLM fails."""
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = Exception("LLM unavailable")

        analyzer = QueryAnalyzer(llm_client=mock_llm, enable_caching=False)

        decomp = await analyzer.analyze(
            "Find authentication functions that call database", context_budget=50000
        )

        # Should use fallback strategy
        assert len(decomp.subqueries) == 3
        assert decomp.reasoning == "Fallback: balanced multi-strategy approach"

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_json(self):
        """Test fallback when LLM returns invalid JSON."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "This is not valid JSON"

        analyzer = QueryAnalyzer(llm_client=mock_llm, enable_caching=False)

        decomp = await analyzer.analyze(
            "Find authentication code and tests", context_budget=50000
        )

        # Should use fallback strategy
        assert len(decomp.subqueries) >= 1


class TestQueryAnalyzerCaching:
    """Test query decomposition caching."""

    @pytest.mark.asyncio
    async def test_cache_key_generation(self):
        """Test cache key is generated correctly."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "intent": "semantic",
                "reasoning": "test",
                "execution_plan": "single",
                "subqueries": [
                    {
                        "id": "sq_1",
                        "query_text": "test",
                        "intent": "semantic",
                        "search_type": "vector",
                        "priority": 10,
                        "depends_on": [],
                        "estimated_tokens": 5000,
                        "reasoning": "test",
                    }
                ],
            }
        )
        analyzer = QueryAnalyzer(llm_client=mock_llm, enable_caching=True)

        decomp = await analyzer.analyze("Find auth code", context_budget=50000)

        assert decomp.cache_key != ""
        assert len(decomp.cache_key) == 16

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Test cache hit returns cached decomposition."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "intent": "hybrid",
                "reasoning": "test",
                "execution_plan": "parallel",
                "subqueries": [
                    {
                        "id": "sq_1",
                        "query_text": "test",
                        "intent": "semantic",
                        "search_type": "vector",
                        "priority": 10,
                        "depends_on": [],
                        "estimated_tokens": 5000,
                        "reasoning": "test",
                    }
                ],
            }
        )
        analyzer = QueryAnalyzer(llm_client=mock_llm, enable_caching=True)

        # Use a complex query that triggers LLM decomposition
        complex_query = "Find authentication functions that call the database"

        # First call - cache miss, should call LLM
        decomp1 = await analyzer.analyze(complex_query, context_budget=50000)

        # Second call - cache hit, should NOT call LLM
        decomp2 = await analyzer.analyze(complex_query, context_budget=50000)

        # LLM should only be called once (first call)
        assert mock_llm.generate.call_count == 1
        assert decomp1.cache_key == decomp2.cache_key


class TestQueryAnalyzerDependencyValidation:
    """Test dependency validation logic."""

    def test_removes_invalid_dependencies(self):
        """Test invalid dependencies are removed."""
        mock_llm = AsyncMock()
        analyzer = QueryAnalyzer(llm_client=mock_llm, enable_caching=False)

        decomp = QueryDecomposition(
            original_query="test",
            intent=QueryIntent.HYBRID,
            subqueries=[
                SubQuery(
                    id="sq_1",
                    query_text="test",
                    intent=QueryIntent.SEMANTIC,
                    search_type="vector",
                    priority=10,
                    depends_on=["sq_invalid"],  # Invalid dependency
                )
            ],
            execution_plan="parallel",
            reasoning="test",
        )

        validated = analyzer._validate_dependencies(decomp)

        assert validated.subqueries[0].depends_on == []

    def test_removes_self_dependencies(self):
        """Test self-dependencies are removed."""
        mock_llm = AsyncMock()
        analyzer = QueryAnalyzer(llm_client=mock_llm, enable_caching=False)

        decomp = QueryDecomposition(
            original_query="test",
            intent=QueryIntent.HYBRID,
            subqueries=[
                SubQuery(
                    id="sq_1",
                    query_text="test",
                    intent=QueryIntent.SEMANTIC,
                    search_type="vector",
                    priority=10,
                    depends_on=["sq_1"],  # Self dependency
                )
            ],
            execution_plan="parallel",
            reasoning="test",
        )

        validated = analyzer._validate_dependencies(decomp)

        assert "sq_1" not in validated.subqueries[0].depends_on


class TestCreateQueryAnalyzer:
    """Test factory function."""

    def test_create_mock_analyzer(self):
        """Test creating analyzer with mock LLM."""
        analyzer = create_query_analyzer(use_mock=True, enable_caching=False)

        assert analyzer is not None
        assert analyzer.llm is not None

    @pytest.mark.asyncio
    async def test_mock_analyzer_works(self):
        """Test mock analyzer produces valid decomposition."""
        analyzer = create_query_analyzer(use_mock=True, enable_caching=False)

        decomp = await analyzer.analyze("Find auth code")

        assert decomp.original_query == "Find auth code"
        assert len(decomp.subqueries) >= 1
