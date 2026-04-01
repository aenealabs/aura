"""Tests for ADR-034 Context Engineering Services

Comprehensive tests for:
- Phase 1: Context Scoring, Hierarchical Tools, Context Stack
- Phase 2: Three-Way Retrieval, HopRAG, MCP Context Manager
- Phase 3: Community Summarization
"""

from unittest.mock import AsyncMock

import pytest

# =============================================================================
# Phase 1.1: Context Scoring Service Tests
# =============================================================================


class TestContextScoringService:
    """Tests for ContextScoringService."""

    @pytest.fixture
    def mock_embedder(self):
        """Create mock embedding service."""
        embedder = AsyncMock()
        embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)
        return embedder

    @pytest.fixture
    def scoring_service(self, mock_embedder):
        """Create context scoring service."""
        from src.services.context_scoring_service import ContextScoringService

        return ContextScoringService(embedding_service=mock_embedder)

    @pytest.mark.asyncio
    async def test_score_context_empty_items(self, scoring_service):
        """Test scoring with empty context items."""
        result = await scoring_service.score_context("test query", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_score_context_basic(self, scoring_service):
        """Test basic context scoring."""
        items = [
            {
                "content": "This is test content about authentication",
                "source": "vector",
            },
            {"content": "Another piece of content about security", "source": "graph"},
        ]
        result = await scoring_service.score_context("authentication security", items)

        assert len(result) == 2
        assert all(0 <= r.final_score <= 1 for r in result)
        assert result[0].final_score >= result[1].final_score  # Sorted descending

    @pytest.mark.asyncio
    async def test_prune_context_below_threshold(self, scoring_service):
        """Test that low-score items are pruned."""
        from src.services.context_scoring_service import ScoredContext

        items = [
            ScoredContext("high", "vector", 0.9, 0.8, 0.7, 0.85, 100),
            ScoredContext("low", "graph", 0.1, 0.1, 0.1, 0.1, 100),  # Below threshold
        ]
        result = await scoring_service.prune_context(items)

        assert len(result) == 1
        assert result[0].content == "high"

    @pytest.mark.asyncio
    async def test_prune_context_token_budget(self, scoring_service):
        """Test token budget enforcement."""
        from src.services.context_scoring_service import ScoredContext

        items = [
            ScoredContext("item1", "vector", 0.9, 0.9, 0.9, 0.9, 50000),
            ScoredContext("item2", "graph", 0.8, 0.8, 0.8, 0.8, 50000),
            ScoredContext("item3", "fs", 0.7, 0.7, 0.7, 0.7, 50000),
        ]
        result = await scoring_service.prune_context(items, token_budget=80000)

        assert len(result) == 1  # Only first item fits
        assert sum(r.token_count for r in result) <= 80000

    def test_compute_recency_no_timestamp(self, scoring_service):
        """Test recency with no timestamp returns neutral."""
        result = scoring_service._compute_recency(None)
        assert result == 0.5

    def test_compute_recency_recent(self, scoring_service):
        """Test recency with recent timestamp."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        result = scoring_service._compute_recency(now)
        assert result > 0.9  # Very recent should be high

    def test_compute_density_empty(self, scoring_service):
        """Test density with empty content."""
        result = scoring_service._compute_density("")
        assert result == 0.0

    def test_compute_density_varied_content(self, scoring_service):
        """Test density with varied content has higher entropy."""
        varied = "The quick brown fox jumps over the lazy dog 12345!@#$%"
        repeated = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

        varied_density = scoring_service._compute_density(varied)
        repeated_density = scoring_service._compute_density(repeated)

        assert varied_density > repeated_density

    def test_tfidf_overlap(self, scoring_service):
        """Test TF-IDF overlap calculation."""
        query = "authentication security login"
        content = "This module handles authentication and security features"

        overlap = scoring_service._tfidf_overlap(query, content)
        assert overlap > 0  # Should have some overlap

    def test_cosine_similarity(self, scoring_service):
        """Test cosine similarity calculation."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = scoring_service._cosine_similarity(vec1, vec2)
        assert similarity == 1.0  # Identical vectors

        vec3 = [0.0, 1.0, 0.0]
        similarity_orthogonal = scoring_service._cosine_similarity(vec1, vec3)
        assert similarity_orthogonal == 0.0  # Orthogonal vectors

    def test_estimate_tokens(self, scoring_service):
        """Test token estimation."""
        content = "This is test content"  # 20 chars
        tokens = scoring_service._estimate_tokens(content)
        assert tokens == 5  # 20 / 4


# =============================================================================
# Phase 1.2: Hierarchical Tool Registry Tests
# =============================================================================


class TestHierarchicalToolRegistry:
    """Tests for HierarchicalToolRegistry."""

    @pytest.fixture
    def registry(self):
        """Create tool registry."""
        from src.services.hierarchical_tool_registry import HierarchicalToolRegistry

        return HierarchicalToolRegistry()

    def test_atomic_tools_registered(self, registry):
        """Test that atomic tools are registered on init."""
        stats = registry.get_registry_stats()
        assert stats["atomic_tools"] > 0
        assert stats["atomic_tools"] <= 20  # Max atomic tools

    def test_get_tool_by_name(self, registry):
        """Test retrieving tool by name."""
        tool = registry.get_tool("file_read")
        assert tool is not None
        assert tool.name == "file_read"

    def test_get_tool_not_found(self, registry):
        """Test retrieving non-existent tool."""
        tool = registry.get_tool("nonexistent_tool")
        assert tool is None

    def test_get_tools_for_context_atomic_only(self, registry):
        """Test getting tools with no domains returns atomic only."""
        from src.services.hierarchical_tool_registry import ToolSelectionContext

        context = ToolSelectionContext()
        tools = registry.get_tools_for_context(context)

        assert len(tools) > 0
        assert all(t.level.value == 1 for t in tools)  # All atomic

    def test_register_domain_tool(self, registry):
        """Test registering a domain-specific tool."""
        from src.services.hierarchical_tool_registry import ToolDefinition, ToolLevel

        tool = ToolDefinition(
            name="vuln_scan",
            description="Scan for vulnerabilities",
            level=ToolLevel.DOMAIN,
            input_schema={"target": "string"},
        )
        registry.register_domain_tool(tool, "security")

        assert registry.get_tool("vuln_scan") is not None
        assert "security" in registry.get_all_domains()

    def test_detect_domains(self, registry):
        """Test domain detection from text."""
        security_text = "Check for SQL injection vulnerabilities in the auth module"
        domains = registry.detect_domains(security_text)

        assert "security" in domains

    def test_assess_complexity(self, registry):
        """Test task complexity assessment."""
        simple = "just fix this one function"
        complex = "do a comprehensive security review of the entire system"

        assert registry.assess_complexity(simple) == "simple"
        assert registry.assess_complexity(complex) == "complex"

    def test_format_tools_compact(self, registry):
        """Test compact tool formatting."""
        from src.services.hierarchical_tool_registry import ToolSelectionContext

        context = ToolSelectionContext()
        tools = registry.get_tools_for_context(context)[:3]
        formatted = registry.format_tools_for_prompt(tools, "compact")

        assert len(formatted) > 0
        assert formatted.count("\n") == len(tools) - 1  # One line per tool

    def test_get_tools_requiring_hitl(self, registry):
        """Test getting HITL-required tools."""
        hitl_tools = registry.get_tools_requiring_hitl()

        assert len(hitl_tools) > 0
        assert all(t.requires_hitl for t in hitl_tools)


# =============================================================================
# Phase 1.3: Context Stack Manager Tests
# =============================================================================


class TestContextStackManager:
    """Tests for ContextStackManager."""

    @pytest.fixture
    def stack_manager(self):
        """Create context stack manager."""
        from src.services.context_stack_manager import ContextStackManager

        return ContextStackManager()

    @pytest.mark.asyncio
    async def test_build_basic_stack(self, stack_manager):
        """Test building a basic context stack."""
        result = await stack_manager.build_context_stack(
            task="Fix the authentication bug",
            agent_type="Coder",
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        assert "System Instructions" in result
        assert "Current Task" in result
        assert "Fix the authentication bug" in result

    @pytest.mark.asyncio
    async def test_build_stack_with_history(self, stack_manager):
        """Test building stack with conversation history."""
        history = [
            {"role": "user", "content": "What does this function do?"},
            {"role": "assistant", "content": "It handles authentication."},
        ]

        result = await stack_manager.build_context_stack(
            task="Now fix it",
            agent_type="Coder",
            conversation_history=history,
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        assert "Conversation History" in result
        assert "What does this function do?" in result

    @pytest.mark.asyncio
    async def test_agent_system_prompts(self, stack_manager):
        """Test different agent types have different system prompts."""
        coder_stack = await stack_manager.build_context_stack(
            task="task",
            agent_type="Coder",
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        reviewer_stack = await stack_manager.build_context_stack(
            task="task",
            agent_type="Reviewer",
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        assert "code generation" in coder_stack.lower()
        assert "security" in reviewer_stack.lower()

    def test_estimate_tokens(self, stack_manager):
        """Test token estimation."""
        text = "a" * 100
        tokens = stack_manager._estimate_tokens(text)
        assert tokens == 25  # 100 / 4

    def test_get_stack_stats(self, stack_manager):
        """Test getting stack statistics."""
        stats = stack_manager.get_stack_stats()

        assert "layer_count" in stats
        assert "total_tokens" in stats
        assert "budget" in stats


# =============================================================================
# Phase 2.1: Three-Way Retrieval Service Tests
# =============================================================================


class TestThreeWayRetrievalService:
    """Tests for ThreeWayRetrievalService."""

    @pytest.fixture
    def mock_opensearch(self):
        """Create mock OpenSearch client."""
        client = AsyncMock()
        client.search = AsyncMock(
            return_value={
                "hits": {
                    "hits": [
                        {
                            "_id": "doc1",
                            "_score": 0.9,
                            "_source": {"content": "test content"},
                        },
                        {
                            "_id": "doc2",
                            "_score": 0.8,
                            "_source": {"content": "more content"},
                        },
                    ]
                }
            }
        )
        return client

    @pytest.fixture
    def mock_neptune(self):
        """Create mock Neptune client."""
        client = AsyncMock()
        client.execute = AsyncMock(
            return_value=[
                {
                    "id": "v1",
                    "name": "TestClass",
                    "type": "class",
                    "content": "class content",
                }
            ]
        )
        return client

    @pytest.fixture
    def mock_embedder(self):
        """Create mock embedding service."""
        embedder = AsyncMock()
        embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)
        return embedder

    @pytest.fixture
    def retrieval_service(self, mock_opensearch, mock_neptune, mock_embedder):
        """Create three-way retrieval service."""
        from src.services.three_way_retrieval_service import ThreeWayRetrievalService

        return ThreeWayRetrievalService(
            opensearch_client=mock_opensearch,
            neptune_client=mock_neptune,
            embedding_service=mock_embedder,
        )

    @pytest.mark.asyncio
    async def test_retrieve_combines_sources(self, retrieval_service):
        """Test that retrieve combines results from all sources."""
        results = await retrieval_service.retrieve("test query", k=10)

        assert len(results) > 0
        # Results should have RRF scores
        assert all(r.rrf_score > 0 for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_with_weights(self, retrieval_service):
        """Test retrieval with custom weights."""
        weights = {"dense": 2.0, "sparse": 1.0, "graph": 0.5}
        results = await retrieval_service.retrieve("test query", weights=weights)

        assert len(results) > 0

    def test_reciprocal_rank_fusion(self, retrieval_service):
        """Test RRF score calculation."""
        from src.services.three_way_retrieval_service import RetrievalResult

        dense = [RetrievalResult("doc1", "content1", 0.9, "dense")]
        sparse = [RetrievalResult("doc1", "content1", 0.8, "sparse")]
        graph = [RetrievalResult("doc2", "content2", 1.0, "graph")]

        source_results = {"dense": dense, "sparse": sparse, "graph": graph}
        weights = {"dense": 1.0, "sparse": 1.2, "graph": 1.0}

        fused = retrieval_service._reciprocal_rank_fusion(source_results, weights)

        assert len(fused) == 2
        # doc1 appears in multiple sources, should have higher score
        assert fused[0].doc_id == "doc1"
        assert len(fused[0].sources_contributed) == 2

    def test_extract_graph_terms(self, retrieval_service):
        """Test graph term extraction."""
        query = "What does the AuthService class do?"
        terms = retrieval_service._extract_graph_terms(query)

        assert "AuthService" in terms


# =============================================================================
# Phase 2.2: HopRAG Service Tests
# =============================================================================


class TestHopRAGService:
    """Tests for HopRAGService."""

    @pytest.fixture
    def mock_neptune(self):
        """Create mock Neptune client."""
        client = AsyncMock()
        client.execute = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM client."""
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value='["AuthService", "validateToken"]')
        return llm

    @pytest.fixture
    def mock_embedder(self):
        """Create mock embedding service."""
        embedder = AsyncMock()
        embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)
        return embedder

    @pytest.fixture
    def hoprag_service(self, mock_neptune, mock_llm, mock_embedder):
        """Create HopRAG service."""
        from src.services.hoprag_service import HopRAGService

        return HopRAGService(
            neptune_client=mock_neptune,
            llm_client=mock_llm,
            embedding_service=mock_embedder,
        )

    @pytest.mark.asyncio
    async def test_identify_start_entities(self, hoprag_service, mock_llm):
        """Test entity identification from query."""
        entities = await hoprag_service._identify_start_entities(
            "How does AuthService validate tokens?"
        )

        assert len(entities) > 0
        assert "AuthService" in entities

    @pytest.mark.asyncio
    async def test_multi_hop_retrieve_no_entities(self, hoprag_service, mock_llm):
        """Test retrieval when no entities found."""
        mock_llm.generate.return_value = "[]"

        results = await hoprag_service.multi_hop_retrieve("random query")

        assert len(results) == 0

    def test_cosine_similarity(self, hoprag_service):
        """Test cosine similarity."""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]

        sim = hoprag_service._cosine_similarity(vec1, vec2)
        assert sim == 0.0

    def test_get_service_stats(self, hoprag_service):
        """Test service statistics."""
        stats = hoprag_service.get_service_stats()

        assert "embedding_cache_size" in stats
        assert "config" in stats


# =============================================================================
# Phase 2.3: MCP Context Manager Tests
# =============================================================================


class TestMCPContextManager:
    """Tests for MCPContextManager."""

    @pytest.fixture
    def mcp_manager(self):
        """Create MCP context manager."""
        from src.services.mcp_context_manager import MCPContextManager

        return MCPContextManager()

    def test_scope_context_for_coder(self, mcp_manager):
        """Test scoping context for coder agent."""
        from src.services.mcp_context_manager import AgentContextScope

        full_context = {
            "system": {"instructions": "You are an assistant"},
            "retrieved": {"code": "function test() {}", "credentials": "secret123"},
            "task": {"description": "Fix the bug"},
        }

        scoped = mcp_manager.scope_context_for_agent(
            full_context, AgentContextScope.CODER
        )

        assert "credentials" not in str(scoped.content)
        assert "task" in scoped.content

    def test_scope_context_for_orchestrator(self, mcp_manager):
        """Test orchestrator gets full context."""
        from src.services.mcp_context_manager import AgentContextScope

        full_context = {
            "system": {"data": "sys"},
            "memory": {"data": "mem"},
            "retrieved": {"data": "ret"},
            "tools": {"data": "tools"},
            "history": {"data": "hist"},
            "task": {"data": "task"},
        }

        scoped = mcp_manager.scope_context_for_agent(
            full_context, AgentContextScope.ORCHESTRATOR
        )

        # Orchestrator should have access to all layers
        assert len(scoped.included_layers) == 6

    def test_validate_context_access(self, mcp_manager):
        """Test field access validation."""
        from src.services.mcp_context_manager import AgentContextScope

        fields = ["code", "credentials", "api_keys", "documentation"]
        allowed, denied = mcp_manager.validate_context_access(
            AgentContextScope.CODER, fields
        )

        assert "code" in allowed
        assert "credentials" in denied
        assert "api_keys" in denied

    def test_get_scope_config(self, mcp_manager):
        """Test getting scope configuration."""
        from src.services.mcp_context_manager import AgentContextScope

        config = mcp_manager.get_scope_config(AgentContextScope.REVIEWER)

        assert config.max_tokens > 0
        assert "security_policies" in config.allowed_domains


# =============================================================================
# Phase 3: Community Summarization Tests
# =============================================================================


class TestCommunitySummarizationService:
    """Tests for CommunitySummarizationService."""

    @pytest.fixture
    def mock_neptune(self):
        """Create mock Neptune client."""
        client = AsyncMock()
        client.execute = AsyncMock(
            return_value=[
                {
                    "id": "v1",
                    "label": "Class",
                    "name": "TestClass",
                    "type": "class",
                    "file_path": "test.py",
                },
                {
                    "id": "v2",
                    "label": "Function",
                    "name": "testFunc",
                    "type": "function",
                    "file_path": "test.py",
                },
            ]
        )
        return client

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM client."""
        llm = AsyncMock()
        llm.generate = AsyncMock(
            return_value="This community handles testing functionality."
        )
        return llm

    @pytest.fixture
    def summarization_service(self, mock_neptune, mock_llm):
        """Create community summarization service."""
        from src.services.community_summarization_service import (
            CommunitySummarizationService,
        )

        return CommunitySummarizationService(
            neptune_client=mock_neptune,
            llm_client=mock_llm,
        )

    def test_fallback_clustering(self, summarization_service):
        """Test fallback clustering algorithm."""
        graph_data = {
            "vertices": [
                {"id": "v1", "label": "Class"},
                {"id": "v2", "label": "Function"},
                {"id": "v3", "label": "Class"},
            ],
            "edges": [
                {"source": "v1", "target": "v2", "label": "contains"},
            ],
        }

        clusters = summarization_service._fallback_clustering(graph_data)

        assert len(clusters) >= 1

    def test_build_hierarchy(self, summarization_service):
        """Test hierarchy building from clusters."""
        clusters = [
            {"cluster_id": "c1", "level": 0, "members": ["v1", "v2"]},
            {"cluster_id": "c2", "level": 0, "members": ["v3", "v4"]},
        ]

        hierarchy = summarization_service._build_hierarchy(clusters)

        assert len(hierarchy.communities) >= 2
        assert hierarchy.total_members == 4

    def test_extract_keywords(self, summarization_service):
        """Test keyword extraction."""
        text = "This module handles authentication and authorization for users"
        keywords = summarization_service._extract_keywords(text)

        assert "authentication" in keywords
        assert "authorization" in keywords
        assert "the" not in keywords  # Stop word removed

    def test_get_service_stats(self, summarization_service):
        """Test service statistics."""
        stats = summarization_service.get_service_stats()

        assert "config" in stats
        assert "level_names" in stats


# =============================================================================
# Integration Tests
# =============================================================================


class TestContextEngineeringIntegration:
    """Integration tests for context engineering services."""

    @pytest.mark.asyncio
    async def test_context_scoring_with_stack_manager(self):
        """Test context scoring integrates with stack manager."""
        from src.services.context_scoring_service import ContextScoringService
        from src.services.context_stack_manager import ContextStackManager

        # Create services
        mock_embedder = AsyncMock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)

        _scorer = ContextScoringService(embedding_service=mock_embedder)
        stack_manager = ContextStackManager()

        # Build stack
        stack = await stack_manager.build_context_stack(
            task="Test task",
            agent_type="Coder",
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        assert len(stack) > 0

    def test_mcp_with_tool_registry(self):
        """Test MCP context manager with tool registry."""
        from src.services.hierarchical_tool_registry import (
            HierarchicalToolRegistry,
            ToolSelectionContext,
        )
        from src.services.mcp_context_manager import (
            AgentContextScope,
            MCPContextManager,
        )

        mcp = MCPContextManager()
        registry = HierarchicalToolRegistry()

        # Get tools for coder context
        coder_scope = mcp.get_scope_config(AgentContextScope.CODER)

        context = ToolSelectionContext(
            detected_domains=[],
            task_complexity="standard",
        )
        tools = registry.get_tools_for_context(context)

        assert len(tools) <= 30  # Within limit
        assert all(t.level.name in coder_scope.allowed_tool_levels for t in tools)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
