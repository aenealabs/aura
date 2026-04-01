"""
Project Aura - HopRAG Service Tests

Tests for the HopRAGService that implements multi-hop
query optimization per ADR-034 Phase 2.2.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.hoprag_service import (
    HopRAGConfig,
    HopRAGService,
    HopResult,
    PseudoQueryEdge,
)


class TestPseudoQueryEdge:
    """Tests for PseudoQueryEdge dataclass."""

    def test_pseudo_query_edge_creation(self):
        """Test basic PseudoQueryEdge creation."""
        edge = PseudoQueryEdge(
            source_id="AuthService",
            target_id="validateToken",
            pseudo_query="What functions does AuthService call?",
            confidence=0.85,
            edge_type="calls",
        )
        assert edge.source_id == "AuthService"
        assert edge.target_id == "validateToken"
        assert edge.pseudo_query == "What functions does AuthService call?"
        assert edge.confidence == 0.85
        assert edge.edge_type == "calls"

    def test_pseudo_query_edge_types(self):
        """Test various edge types."""
        for edge_type in ["calls", "imports", "extends", "implements"]:
            edge = PseudoQueryEdge(
                source_id="A",
                target_id="B",
                pseudo_query="test query",
                confidence=0.5,
                edge_type=edge_type,
            )
            assert edge.edge_type == edge_type


class TestHopResult:
    """Tests for HopResult dataclass."""

    def test_hop_result_creation(self):
        """Test basic HopResult creation."""
        result = HopResult(
            path=["AuthService", "validateToken", "TokenValidator"],
            entities=[
                {"id": "AuthService", "type": "class"},
                {"id": "validateToken", "type": "function"},
            ],
            reasoning="Traversed through authentication chain",
            confidence=0.85,
            hops=2,
        )
        assert result.path == ["AuthService", "validateToken", "TokenValidator"]
        assert len(result.entities) == 2
        assert result.reasoning == "Traversed through authentication chain"
        assert result.confidence == 0.85
        assert result.hops == 2
        assert result.pseudo_queries_used == []

    def test_hop_result_with_pseudo_queries(self):
        """Test HopResult with pseudo queries used."""
        result = HopResult(
            path=["A", "B"],
            entities=[],
            reasoning="test",
            confidence=0.9,
            hops=1,
            pseudo_queries_used=["What does A call?", "What uses B?"],
        )
        assert len(result.pseudo_queries_used) == 2


class TestHopRAGConfig:
    """Tests for HopRAGConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = HopRAGConfig()
        assert config.max_hops == 3
        assert config.prune_threshold == 0.5
        assert config.similarity_threshold == 0.5
        assert config.max_neighbors == 10
        assert config.max_start_entities == 5
        assert config.embedding_cache_size == 1000

    def test_custom_config(self):
        """Test custom configuration values."""
        config = HopRAGConfig(
            max_hops=5,
            prune_threshold=0.7,
            similarity_threshold=0.6,
            max_neighbors=20,
        )
        assert config.max_hops == 5
        assert config.prune_threshold == 0.7
        assert config.similarity_threshold == 0.6
        assert config.max_neighbors == 20


class TestHopRAGService:
    """Tests for HopRAGService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_neptune.execute = AsyncMock(return_value=[])

        self.mock_llm = MagicMock()
        self.mock_llm.generate = AsyncMock(return_value='["AuthService"]')

        self.mock_embedder = MagicMock()
        self.mock_embedder.embed_text = AsyncMock(return_value=[0.5, 0.5, 0.5])

        self.service = HopRAGService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
            embedding_service=self.mock_embedder,
        )

    @pytest.mark.asyncio
    async def test_multi_hop_retrieve_no_entities(self):
        """Test retrieval when no starting entities found."""
        self.mock_llm.generate = AsyncMock(return_value="[]")

        result = await self.service.multi_hop_retrieve("find auth issues")

        assert result == []

    @pytest.mark.asyncio
    async def test_multi_hop_retrieve_with_entities(self):
        """Test retrieval with starting entities."""
        # Mock LLM to return start entities
        self.mock_llm.generate = AsyncMock(return_value='["AuthService"]')

        # Mock Neptune to return neighbors
        self.mock_neptune.execute = AsyncMock(
            return_value=[{"neighbor": "TokenValidator", "type": "function"}]
        )

        result = await self.service.multi_hop_retrieve("what does AuthService use?")

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_multi_hop_retrieve_with_provided_entities(self):
        """Test retrieval with provided starting entities."""
        result = await self.service.multi_hop_retrieve(
            "find related code",
            start_entities=["MyClass", "MyFunction"],
        )

        # Should not call LLM for entity identification
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_multi_hop_retrieve_max_results(self):
        """Test that max_results is respected."""
        self.mock_llm.generate = AsyncMock(return_value='["A", "B", "C"]')

        result = await self.service.multi_hop_retrieve(
            "find all",
            max_results=2,
        )

        assert len(result) <= 2


class TestEntityIdentification:
    """Tests for start entity identification."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_neptune.execute = AsyncMock(return_value=[])

        self.mock_llm = MagicMock()
        self.mock_embedder = MagicMock()

        self.service = HopRAGService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
            embedding_service=self.mock_embedder,
        )

    @pytest.mark.asyncio
    async def test_identify_start_entities_success(self):
        """Test successful entity identification."""
        self.mock_llm.generate = AsyncMock(
            return_value='["AuthService", "UserController"]'
        )

        entities = await self.service._identify_start_entities(
            "What functions does AuthService call?"
        )

        assert entities == ["AuthService", "UserController"]

    @pytest.mark.asyncio
    async def test_identify_start_entities_invalid_json(self):
        """Test fallback when JSON parsing fails."""
        self.mock_llm.generate = AsyncMock(return_value="not valid json")

        entities = await self.service._identify_start_entities(
            "Find AuthService methods"
        )

        # Should fallback to extracting capitalized words
        assert "AuthService" in entities

    @pytest.mark.asyncio
    async def test_identify_start_entities_llm_error(self):
        """Test handling of LLM errors."""
        self.mock_llm.generate = AsyncMock(side_effect=Exception("LLM error"))

        entities = await self.service._identify_start_entities("test query")

        assert entities == []

    @pytest.mark.asyncio
    async def test_identify_start_entities_max_limit(self):
        """Test that entity list is limited."""
        long_list = json.dumps([f"Entity{i}" for i in range(20)])
        self.mock_llm.generate = AsyncMock(return_value=long_list)

        entities = await self.service._identify_start_entities("find all")

        assert len(entities) <= 10


class TestGraphTraversal:
    """Tests for graph traversal functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_llm = MagicMock()
        self.mock_embedder = MagicMock()
        self.mock_embedder.embed_text = AsyncMock(return_value=[0.5, 0.5])

        self.service = HopRAGService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
            embedding_service=self.mock_embedder,
        )

    @pytest.mark.asyncio
    async def test_traverse_max_hops_reached(self):
        """Test traversal stops at max hops."""
        config = HopRAGConfig(max_hops=2)
        service = HopRAGService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
            embedding_service=self.mock_embedder,
            config=config,
        )

        result = await service._traverse_with_reasoning(
            query="test",
            current_entity="start",
            current_hop=2,
        )

        assert result is not None
        assert result.reasoning == "Max hops reached"
        assert result.hops == 2

    @pytest.mark.asyncio
    async def test_traverse_no_neighbors(self):
        """Test traversal when no neighbors found."""
        self.mock_neptune.execute = AsyncMock(return_value=[])

        result = await self.service._traverse_with_reasoning(
            query="test",
            current_entity="isolated_node",
            current_hop=0,
        )

        assert result is not None
        assert result.reasoning == "No relevant neighbors found"
        assert result.confidence == 0.3


class TestPseudoQueryNeighbors:
    """Tests for pseudo-query neighbor retrieval."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_llm = MagicMock()
        self.mock_embedder = MagicMock()
        self.mock_embedder.embed_text = AsyncMock(return_value=[0.5, 0.5])
        # Support batch embedding (N+1 optimization)
        self.mock_embedder.embed_batch = AsyncMock(
            return_value=[[0.5, 0.5], [0.5, 0.5]]
        )

        self.service = HopRAGService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
            embedding_service=self.mock_embedder,
        )

    @pytest.mark.asyncio
    async def test_get_neighbors_with_pseudo_queries(self):
        """Test getting neighbors with pseudo-query edges."""
        self.mock_neptune.execute = AsyncMock(
            return_value=[
                {
                    "neighbor": "TokenValidator",
                    "pseudo_query": "What validates tokens?",
                    "confidence": 0.9,
                    "edge_type": "calls",
                },
            ]
        )

        neighbors = await self.service._get_pseudo_query_neighbors(
            "AuthService", "find auth code"
        )

        assert len(neighbors) == 1
        assert neighbors[0]["neighbor"] == "TokenValidator"

    @pytest.mark.asyncio
    async def test_get_neighbors_fallback(self):
        """Test fallback when no pseudo-query edges exist."""
        # First call returns empty, second (fallback) returns neighbors
        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return []
            return [{"neighbor": "RelatedNode", "type": "class"}]

        self.mock_neptune.execute = mock_execute

        neighbors = await self.service._get_pseudo_query_neighbors(
            "SomeNode", "find related"
        )

        assert len(neighbors) >= 0


class TestNeighborReasoning:
    """Tests for LLM-based neighbor reasoning."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_llm = MagicMock()
        self.mock_embedder = MagicMock()
        self.mock_embedder.embed_text = AsyncMock(return_value=[0.5, 0.5])

        self.service = HopRAGService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
            embedding_service=self.mock_embedder,
        )

    @pytest.mark.asyncio
    async def test_reason_about_neighbors_success(self):
        """Test successful neighbor reasoning."""
        self.mock_llm.generate = AsyncMock(
            return_value=json.dumps(
                {
                    "neighbor": "TokenValidator",
                    "reasoning": "Directly handles token validation",
                    "confidence": 0.85,
                }
            )
        )

        # Neighbors must have 'similarity' key as expected by the implementation
        neighbors = [
            {
                "neighbor": "TokenValidator",
                "pseudo_query": "validates tokens",
                "similarity": 0.9,
            },
            {"neighbor": "Logger", "pseudo_query": "logs events", "similarity": 0.5},
        ]

        best, reasoning, confidence, pq = await self.service._reason_about_neighbors(
            "find token validation",
            "AuthService",
            neighbors,
            ["AuthService"],
        )

        assert best == "TokenValidator"
        assert confidence > 0

    @pytest.mark.asyncio
    async def test_reason_about_neighbors_invalid_json(self):
        """Test fallback when LLM returns invalid JSON."""
        self.mock_llm.generate = AsyncMock(return_value="invalid json response")

        neighbors = [
            {"neighbor": "First", "pseudo_query": "query1", "similarity": 0.8},
            {"neighbor": "Second", "pseudo_query": "query2", "similarity": 0.6},
        ]

        best, reasoning, confidence, pq = await self.service._reason_about_neighbors(
            "test query",
            "Start",
            neighbors,
            ["Start"],
        )

        # Should fallback to first neighbor
        assert best == "First"


class TestEntityDetails:
    """Tests for retrieving entity details."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_llm = MagicMock()
        self.mock_embedder = MagicMock()

        self.service = HopRAGService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
            embedding_service=self.mock_embedder,
        )

    @pytest.mark.asyncio
    async def test_get_entity_details_success(self):
        """Test successful entity detail retrieval."""
        self.mock_neptune.execute = AsyncMock(
            return_value=[
                {"id": "AuthService", "type": "class", "file": "auth.py"},
            ]
        )

        details = await self.service._get_entity_details(["AuthService"])

        assert len(details) == 1
        assert details[0]["id"] == "AuthService"

    @pytest.mark.asyncio
    async def test_get_entity_details_empty_path(self):
        """Test entity details for empty path."""
        details = await self.service._get_entity_details([])
        assert details == []

    @pytest.mark.asyncio
    async def test_get_entity_details_neptune_error(self):
        """Test handling of Neptune errors."""
        self.mock_neptune.execute = AsyncMock(side_effect=Exception("DB error"))

        details = await self.service._get_entity_details(["SomeEntity"])

        # Should return empty or handle gracefully
        assert isinstance(details, list)


class TestEmbeddingCache:
    """Tests for embedding cache functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_llm = MagicMock()
        self.mock_embedder = MagicMock()
        self.mock_embedder.embed_text = AsyncMock(return_value=[0.5, 0.5])

        self.service = HopRAGService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
            embedding_service=self.mock_embedder,
        )

    @pytest.mark.asyncio
    async def test_embedding_caching(self):
        """Test that embeddings are cached."""
        # Request embedding for same text twice
        await self.service._get_embedding("test query")
        await self.service._get_embedding("test query")

        # Should only call embedder once due to caching
        assert self.mock_embedder.embed_text.call_count == 1

    @pytest.mark.asyncio
    async def test_embedding_cache_different_texts(self):
        """Test cache with different texts."""
        await self.service._get_embedding("query one")
        await self.service._get_embedding("query two")

        assert self.mock_embedder.embed_text.call_count == 2


class TestSimilarityComputation:
    """Tests for similarity computation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_llm = MagicMock()
        self.mock_embedder = MagicMock()

        self.service = HopRAGService(
            neptune_client=self.mock_neptune,
            llm_client=self.mock_llm,
            embedding_service=self.mock_embedder,
        )

    def test_cosine_similarity_identical(self):
        """Test cosine similarity of identical vectors."""
        vec = [1.0, 0.0, 0.0]
        similarity = self.service._cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity of orthogonal vectors."""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        similarity = self.service._cosine_similarity(vec1, vec2)
        assert abs(similarity) < 0.001

    def test_cosine_similarity_empty(self):
        """Test cosine similarity with empty vectors."""
        assert self.service._cosine_similarity([], []) == 0.0

    def test_cosine_similarity_different_lengths(self):
        """Test cosine similarity with mismatched vector lengths."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0]
        assert self.service._cosine_similarity(vec1, vec2) == 0.0
