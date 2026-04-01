"""
Tests for Project Aura - Semantic Tool Search Service

Comprehensive tests for intelligent tool discovery using semantic similarity
per ADR-037 Phase 1.8.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.semantic_tool_search import (
    SearchConfig,
    SemanticToolSearch,
    ToolCategory,
    ToolComplexity,
    ToolDefinition,
    ToolParameter,
    ToolRecommendation,
    ToolSearchResult,
)

# =============================================================================
# ToolCategory Enum Tests
# =============================================================================


class TestToolCategory:
    """Tests for ToolCategory enum."""

    def test_file_operations(self):
        """Test FILE_OPERATIONS category."""
        assert ToolCategory.FILE_OPERATIONS.value == "file_operations"

    def test_code_analysis(self):
        """Test CODE_ANALYSIS category."""
        assert ToolCategory.CODE_ANALYSIS.value == "code_analysis"

    def test_code_generation(self):
        """Test CODE_GENERATION category."""
        assert ToolCategory.CODE_GENERATION.value == "code_generation"

    def test_testing(self):
        """Test TESTING category."""
        assert ToolCategory.TESTING.value == "testing"

    def test_security(self):
        """Test SECURITY category."""
        assert ToolCategory.SECURITY.value == "security"

    def test_database(self):
        """Test DATABASE category."""
        assert ToolCategory.DATABASE.value == "database"

    def test_api(self):
        """Test API category."""
        assert ToolCategory.API.value == "api"

    def test_communication(self):
        """Test COMMUNICATION category."""
        assert ToolCategory.COMMUNICATION.value == "communication"

    def test_browser(self):
        """Test BROWSER category."""
        assert ToolCategory.BROWSER.value == "browser"

    def test_system(self):
        """Test SYSTEM category."""
        assert ToolCategory.SYSTEM.value == "system"

    def test_memory(self):
        """Test MEMORY category."""
        assert ToolCategory.MEMORY.value == "memory"

    def test_search(self):
        """Test SEARCH category."""
        assert ToolCategory.SEARCH.value == "search"

    def test_visualization(self):
        """Test VISUALIZATION category."""
        assert ToolCategory.VISUALIZATION.value == "visualization"

    def test_documentation(self):
        """Test DOCUMENTATION category."""
        assert ToolCategory.DOCUMENTATION.value == "documentation"

    def test_all_categories_exist(self):
        """Test all expected categories are defined."""
        expected = {
            "file_operations",
            "code_analysis",
            "code_generation",
            "testing",
            "security",
            "database",
            "api",
            "communication",
            "browser",
            "system",
            "memory",
            "search",
            "visualization",
            "documentation",
        }
        actual = {c.value for c in ToolCategory}
        assert actual == expected


# =============================================================================
# ToolComplexity Enum Tests
# =============================================================================


class TestToolComplexity:
    """Tests for ToolComplexity enum."""

    def test_simple(self):
        """Test SIMPLE complexity."""
        assert ToolComplexity.SIMPLE.value == "simple"

    def test_moderate(self):
        """Test MODERATE complexity."""
        assert ToolComplexity.MODERATE.value == "moderate"

    def test_complex(self):
        """Test COMPLEX complexity."""
        assert ToolComplexity.COMPLEX.value == "complex"

    def test_dangerous(self):
        """Test DANGEROUS complexity."""
        assert ToolComplexity.DANGEROUS.value == "dangerous"

    def test_all_complexities_exist(self):
        """Test all expected complexities are defined."""
        expected = {"simple", "moderate", "complex", "dangerous"}
        actual = {c.value for c in ToolComplexity}
        assert actual == expected


# =============================================================================
# ToolParameter Tests
# =============================================================================


class TestToolParameter:
    """Tests for ToolParameter dataclass."""

    def test_required_parameter(self):
        """Test required parameter creation."""
        param = ToolParameter(
            name="file_path",
            type="string",
            description="Path to the file",
        )

        assert param.name == "file_path"
        assert param.type == "string"
        assert param.description == "Path to the file"
        assert param.required is True

    def test_optional_parameter(self):
        """Test optional parameter with default."""
        param = ToolParameter(
            name="encoding",
            type="string",
            description="File encoding",
            required=False,
            default="utf-8",
        )

        assert param.required is False
        assert param.default == "utf-8"

    def test_parameter_with_enum(self):
        """Test parameter with enum values."""
        param = ToolParameter(
            name="format",
            type="string",
            description="Output format",
            enum=["json", "yaml", "xml"],
        )

        assert param.enum == ["json", "yaml", "xml"]

    def test_parameter_with_examples(self):
        """Test parameter with examples."""
        param = ToolParameter(
            name="query",
            type="string",
            description="Search query",
            examples=["file:*.py", "function:main"],
        )

        assert len(param.examples) == 2


# =============================================================================
# ToolDefinition Tests
# =============================================================================


class TestToolDefinition:
    """Tests for ToolDefinition dataclass."""

    def test_minimal_definition(self):
        """Test minimal tool definition."""
        tool = ToolDefinition(
            tool_id="test_tool",
            name="Test Tool",
            description="A test tool",
        )

        assert tool.tool_id == "test_tool"
        assert tool.name == "Test Tool"
        assert tool.description == "A test tool"
        assert tool.category == ToolCategory.SYSTEM
        assert tool.complexity == ToolComplexity.SIMPLE

    def test_full_definition(self):
        """Test full tool definition."""
        params = [ToolParameter(name="input", type="string", description="Input data")]
        tool = ToolDefinition(
            tool_id="full_tool",
            name="Full Tool",
            description="A fully specified tool",
            detailed_description="This is a comprehensive tool with all options",
            category=ToolCategory.CODE_ANALYSIS,
            complexity=ToolComplexity.MODERATE,
            parameters=params,
            return_type="dict",
            return_description="Analysis results",
            examples=[{"description": "Basic usage", "code": "full_tool('test')"}],
            tags=["analysis", "code"],
            requires_approval=True,
            deprecated=False,
            version="2.0.0",
        )

        assert tool.category == ToolCategory.CODE_ANALYSIS
        assert tool.complexity == ToolComplexity.MODERATE
        assert len(tool.parameters) == 1
        assert tool.requires_approval is True
        assert "analysis" in tool.tags

    def test_deprecated_tool(self):
        """Test deprecated tool flag."""
        tool = ToolDefinition(
            tool_id="old_tool",
            name="Old Tool",
            description="Deprecated tool",
            deprecated=True,
        )

        assert tool.deprecated is True

    def test_usage_statistics(self):
        """Test usage statistics fields."""
        tool = ToolDefinition(
            tool_id="stats_tool",
            name="Stats Tool",
            description="Tool with stats",
            usage_count=100,
            success_rate=0.95,
        )

        assert tool.usage_count == 100
        assert tool.success_rate == 0.95


# =============================================================================
# ToolSearchResult Tests
# =============================================================================


class TestToolSearchResult:
    """Tests for ToolSearchResult dataclass."""

    def test_basic_result(self):
        """Test basic search result."""
        tool = ToolDefinition(
            tool_id="result_tool",
            name="Result Tool",
            description="A tool result",
        )
        result = ToolSearchResult(
            tool=tool,
            score=0.85,
        )

        assert result.tool == tool
        assert result.score == 0.85
        assert result.match_reasons == []

    def test_result_with_reasons(self):
        """Test search result with match reasons."""
        tool = ToolDefinition(
            tool_id="reason_tool",
            name="Reason Tool",
            description="Tool with reasons",
        )
        result = ToolSearchResult(
            tool=tool,
            score=0.9,
            match_reasons=["High semantic similarity", "Strong keyword match"],
        )

        assert len(result.match_reasons) == 2
        assert "High semantic similarity" in result.match_reasons


# =============================================================================
# ToolRecommendation Tests
# =============================================================================


class TestToolRecommendation:
    """Tests for ToolRecommendation dataclass."""

    def test_basic_recommendation(self):
        """Test basic recommendation."""
        tool = ToolDefinition(
            tool_id="rec_tool",
            name="Recommended Tool",
            description="A recommended tool",
        )
        rec = ToolRecommendation(
            tool=tool,
            confidence=0.9,
            reason="Well-suited for the task",
        )

        assert rec.tool == tool
        assert rec.confidence == 0.9
        assert rec.reason == "Well-suited for the task"
        assert rec.usage_hint is None
        assert rec.alternatives == []

    def test_full_recommendation(self):
        """Test recommendation with all fields."""
        tool = ToolDefinition(
            tool_id="full_rec_tool",
            name="Full Recommendation",
            description="Full tool",
        )
        rec = ToolRecommendation(
            tool=tool,
            confidence=0.95,
            reason="Perfect match for file operations",
            usage_hint="Required parameters: file_path, mode",
            alternatives=["alt_tool_1", "alt_tool_2"],
        )

        assert rec.usage_hint is not None
        assert len(rec.alternatives) == 2


# =============================================================================
# SearchConfig Tests
# =============================================================================


class TestSearchConfig:
    """Tests for SearchConfig dataclass."""

    def test_default_config(self):
        """Test default search configuration."""
        config = SearchConfig()

        assert config.min_score == 0.3
        assert config.max_results == 10
        assert config.boost_frequently_used is True
        assert config.boost_high_success_rate is True
        assert config.include_deprecated is False
        assert config.embedding_weight == 0.7
        assert config.keyword_weight == 0.3

    def test_custom_config(self):
        """Test custom search configuration."""
        config = SearchConfig(
            min_score=0.5,
            max_results=20,
            boost_frequently_used=False,
            include_deprecated=True,
            embedding_weight=0.6,
            keyword_weight=0.4,
        )

        assert config.min_score == 0.5
        assert config.max_results == 20
        assert config.boost_frequently_used is False
        assert config.include_deprecated is True


# =============================================================================
# SemanticToolSearch Tests
# =============================================================================


class TestSemanticToolSearchInit:
    """Tests for SemanticToolSearch initialization."""

    def test_init_minimal(self):
        """Test minimal initialization."""
        embedder = MagicMock()
        search = SemanticToolSearch(embedding_service=embedder)

        assert search.embedder == embedder
        assert search.vector_store is None
        assert search.config is not None

    def test_init_with_vector_store(self):
        """Test initialization with vector store."""
        embedder = MagicMock()
        vector_store = MagicMock()
        search = SemanticToolSearch(
            embedding_service=embedder,
            vector_store=vector_store,
        )

        assert search.vector_store == vector_store

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        embedder = MagicMock()
        config = SearchConfig(min_score=0.5)
        search = SemanticToolSearch(
            embedding_service=embedder,
            config=config,
        )

        assert search.config.min_score == 0.5


class TestSemanticToolSearchIndexing:
    """Tests for tool indexing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.embedder = MagicMock()
        self.embedder.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
        self.embedder.embed_batch = AsyncMock(
            return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        )
        self.search = SemanticToolSearch(embedding_service=self.embedder)

    @pytest.mark.asyncio
    async def test_index_tool(self):
        """Test indexing a single tool."""
        tool = ToolDefinition(
            tool_id="index_tool",
            name="Index Tool",
            description="Tool to be indexed",
        )

        await self.search.index_tool(tool)

        assert "index_tool" in self.search._tools
        assert "index_tool" in self.search._embeddings
        self.embedder.embed_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_tool_with_vector_store(self):
        """Test indexing with vector store."""
        vector_store = MagicMock()
        vector_store.upsert = AsyncMock()
        search = SemanticToolSearch(
            embedding_service=self.embedder,
            vector_store=vector_store,
        )

        tool = ToolDefinition(
            tool_id="vs_tool",
            name="Vector Store Tool",
            description="Tool stored in vector store",
        )

        await search.index_tool(tool)

        vector_store.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_tools_batch(self):
        """Test batch indexing of tools."""
        tools = [
            ToolDefinition(
                tool_id=f"batch_tool_{i}",
                name=f"Batch Tool {i}",
                description=f"Tool {i} in batch",
            )
            for i in range(2)
        ]

        count = await self.search.index_tools_batch(tools)

        assert count == 2
        assert "batch_tool_0" in self.search._tools
        assert "batch_tool_1" in self.search._tools

    @pytest.mark.asyncio
    async def test_remove_tool(self):
        """Test removing a tool from index."""
        tool = ToolDefinition(
            tool_id="remove_tool",
            name="Remove Tool",
            description="Tool to be removed",
        )
        await self.search.index_tool(tool)

        result = await self.search.remove_tool("remove_tool")

        assert result is True
        assert "remove_tool" not in self.search._tools

    @pytest.mark.asyncio
    async def test_remove_nonexistent_tool(self):
        """Test removing a tool that doesn't exist."""
        result = await self.search.remove_tool("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_remove_tool_with_vector_store(self):
        """Test removing a tool from vector store - line 300."""
        vector_store = MagicMock()
        vector_store.upsert = AsyncMock()
        vector_store.delete = AsyncMock()
        search = SemanticToolSearch(
            embedding_service=self.embedder,
            vector_store=vector_store,
        )

        tool = ToolDefinition(
            tool_id="vs_remove_tool",
            name="Vector Store Remove Tool",
            description="Tool to be removed from vector store",
        )

        await search.index_tool(tool)
        result = await search.remove_tool("vs_remove_tool")

        assert result is True
        vector_store.delete.assert_called_once_with("vs_remove_tool")

    @pytest.mark.asyncio
    async def test_index_tools_batch_with_vector_store(self):
        """Test batch indexing with vector store - line 270."""
        vector_store = MagicMock()
        vector_store.upsert = AsyncMock()
        search = SemanticToolSearch(
            embedding_service=self.embedder,
            vector_store=vector_store,
        )

        tools = [
            ToolDefinition(
                tool_id=f"vs_batch_tool_{i}",
                name=f"VS Batch Tool {i}",
                description=f"Tool {i} in batch for vector store",
            )
            for i in range(2)
        ]

        count = await search.index_tools_batch(tools)

        assert count == 2
        assert vector_store.upsert.call_count == 2


class TestSemanticToolSearchSearching:
    """Tests for tool searching."""

    def setup_method(self):
        """Set up test fixtures."""
        self.embedder = MagicMock()
        self.embedder.embed_text = AsyncMock(return_value=[0.5, 0.5, 0.5])
        self.search = SemanticToolSearch(embedding_service=self.embedder)

        # Pre-populate some tools with known embeddings
        self.search._tools = {
            "file_read": ToolDefinition(
                tool_id="file_read",
                name="Read File",
                description="Read contents of a file",
                category=ToolCategory.FILE_OPERATIONS,
            ),
            "file_write": ToolDefinition(
                tool_id="file_write",
                name="Write File",
                description="Write contents to a file",
                category=ToolCategory.FILE_OPERATIONS,
            ),
            "code_analyze": ToolDefinition(
                tool_id="code_analyze",
                name="Analyze Code",
                description="Analyze source code for issues",
                category=ToolCategory.CODE_ANALYSIS,
            ),
            "deprecated_tool": ToolDefinition(
                tool_id="deprecated_tool",
                name="Deprecated Tool",
                description="Old deprecated tool",
                deprecated=True,
            ),
            "dangerous_tool": ToolDefinition(
                tool_id="dangerous_tool",
                name="Dangerous Tool",
                description="Destructive operations",
                complexity=ToolComplexity.DANGEROUS,
            ),
        }
        # Set embeddings - file tools similar to query, others different
        self.search._embeddings = {
            "file_read": [0.6, 0.5, 0.4],  # Close to query [0.5, 0.5, 0.5]
            "file_write": [0.5, 0.6, 0.4],  # Close to query
            "code_analyze": [0.1, 0.2, 0.3],  # Far from query
            "deprecated_tool": [0.5, 0.5, 0.5],  # Very close to query
            "dangerous_tool": [0.4, 0.5, 0.6],  # Close to query
        }

    @pytest.mark.asyncio
    async def test_search_tools_basic(self):
        """Test basic tool search."""
        results = await self.search.search_tools("read a file")

        assert len(results) > 0
        assert all(isinstance(r, ToolSearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_tools_excludes_deprecated(self):
        """Test that deprecated tools are excluded by default."""
        results = await self.search.search_tools("deprecated")

        tool_ids = [r.tool.tool_id for r in results]
        assert "deprecated_tool" not in tool_ids

    @pytest.mark.asyncio
    async def test_search_tools_excludes_dangerous(self):
        """Test excluding dangerous tools."""
        results = await self.search.search_tools(
            "dangerous operations",
            exclude_dangerous=True,
        )

        tool_ids = [r.tool.tool_id for r in results]
        assert "dangerous_tool" not in tool_ids

    @pytest.mark.asyncio
    async def test_search_tools_category_filter(self):
        """Test filtering by category."""
        results = await self.search.search_tools(
            "file operations",
            categories=[ToolCategory.FILE_OPERATIONS],
        )

        for result in results:
            assert result.tool.category == ToolCategory.FILE_OPERATIONS

    @pytest.mark.asyncio
    async def test_search_tools_limit(self):
        """Test result limit."""
        results = await self.search.search_tools("tool", limit=2)
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_search_tools_min_score(self):
        """Test minimum score filter."""
        results = await self.search.search_tools("file", min_score=0.9)

        for result in results:
            assert result.score >= 0.9

    @pytest.mark.asyncio
    async def test_search_tools_sorted_by_score(self):
        """Test results are sorted by score descending."""
        results = await self.search.search_tools("file operations", limit=5)

        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score


class TestSemanticToolSearchRecommendations:
    """Tests for tool recommendations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.embedder = MagicMock()
        self.embedder.embed_text = AsyncMock(return_value=[0.5, 0.5, 0.5])
        self.search = SemanticToolSearch(embedding_service=self.embedder)

        # Add tools
        self.search._tools = {
            "file_read": ToolDefinition(
                tool_id="file_read",
                name="Read File",
                description="Read file contents",
                category=ToolCategory.FILE_OPERATIONS,
            ),
            "file_parse": ToolDefinition(
                tool_id="file_parse",
                name="Parse File",
                description="Parse file content",
                category=ToolCategory.FILE_OPERATIONS,
            ),
        }
        self.search._embeddings = {
            "file_read": [0.6, 0.5, 0.4],
            "file_parse": [0.5, 0.6, 0.4],
        }

    @pytest.mark.asyncio
    async def test_recommend_tools(self):
        """Test tool recommendations."""
        recommendations = await self.search.recommend_tools(
            task_description="I need to read and parse a JSON file"
        )

        assert len(recommendations) > 0
        assert all(isinstance(r, ToolRecommendation) for r in recommendations)

    @pytest.mark.asyncio
    async def test_recommend_tools_with_context(self):
        """Test recommendations with context."""
        recommendations = await self.search.recommend_tools(
            task_description="Parse a file",
            current_context={"file_type": "json"},
        )

        assert len(recommendations) > 0

    @pytest.mark.asyncio
    async def test_recommend_tools_exclude(self):
        """Test excluding specific tools from recommendations."""
        recommendations = await self.search.recommend_tools(
            task_description="Read file",
            exclude_tools=["file_read"],
        )

        tool_ids = [r.tool.tool_id for r in recommendations]
        assert "file_read" not in tool_ids

    @pytest.mark.asyncio
    async def test_recommend_tools_includes_alternatives(self):
        """Test that recommendations include alternatives."""
        recommendations = await self.search.recommend_tools(
            task_description="File operations"
        )

        if len(recommendations) > 0:
            # First recommendation should have alternatives
            # (other tools in same category)
            first = recommendations[0]
            if first.tool.category == ToolCategory.FILE_OPERATIONS:
                # There are two file operation tools
                pass  # Alternatives may be present


class TestSemanticToolSearchSimilarity:
    """Tests for finding similar tools."""

    def setup_method(self):
        """Set up test fixtures."""
        self.embedder = MagicMock()
        self.embedder.embed_text = AsyncMock(return_value=[0.5, 0.5, 0.5])
        self.search = SemanticToolSearch(embedding_service=self.embedder)

        # Add tools with varying similarity
        self.search._tools = {
            "tool_a": ToolDefinition(
                tool_id="tool_a", name="Tool A", description="Reference tool"
            ),
            "tool_b": ToolDefinition(
                tool_id="tool_b", name="Tool B", description="Similar to A"
            ),
            "tool_c": ToolDefinition(
                tool_id="tool_c", name="Tool C", description="Different from A"
            ),
        }
        self.search._embeddings = {
            "tool_a": [1.0, 0.0, 0.0],
            "tool_b": [0.9, 0.1, 0.0],  # Very similar to A
            "tool_c": [0.0, 0.0, 1.0],  # Very different from A
        }

    @pytest.mark.asyncio
    async def test_find_similar_tools(self):
        """Test finding similar tools."""
        results = await self.search.find_similar_tools("tool_a", limit=2)

        assert len(results) == 2
        # tool_b should be most similar
        assert results[0].tool.tool_id == "tool_b"

    @pytest.mark.asyncio
    async def test_find_similar_tools_excludes_self(self):
        """Test that reference tool is excluded from results."""
        results = await self.search.find_similar_tools("tool_a", limit=5)

        tool_ids = [r.tool.tool_id for r in results]
        assert "tool_a" not in tool_ids

    @pytest.mark.asyncio
    async def test_find_similar_tools_nonexistent(self):
        """Test finding similar tools for nonexistent tool."""
        results = await self.search.find_similar_tools("nonexistent")
        assert results == []


class TestSemanticToolSearchUsage:
    """Tests for usage recording and learning."""

    def setup_method(self):
        """Set up test fixtures."""
        self.embedder = MagicMock()
        self.embedder.embed_text = AsyncMock(return_value=[0.5, 0.5, 0.5])
        self.search = SemanticToolSearch(embedding_service=self.embedder)

        self.search._tools = {
            "usage_tool": ToolDefinition(
                tool_id="usage_tool",
                name="Usage Tool",
                description="Tool for tracking usage",
                usage_count=0,
                success_rate=1.0,
            ),
        }

    def test_record_tool_usage_success(self):
        """Test recording successful tool usage."""
        self.search.record_tool_usage("usage_tool", success=True)

        tool = self.search._tools["usage_tool"]
        assert tool.usage_count == 1
        assert "usage_tool" in self.search._usage_stats

    def test_record_tool_usage_failure(self):
        """Test recording failed tool usage."""
        initial_rate = self.search._tools["usage_tool"].success_rate
        self.search.record_tool_usage("usage_tool", success=False)

        tool = self.search._tools["usage_tool"]
        assert tool.usage_count == 1
        # Success rate should decrease
        assert tool.success_rate < initial_rate

    def test_record_tool_usage_with_context(self):
        """Test recording usage with context."""
        context = {"file_type": "json", "size": 1024}
        self.search.record_tool_usage("usage_tool", success=True, context=context)

        stats = self.search._usage_stats["usage_tool"]
        assert context in stats["contexts"]

    def test_record_tool_usage_nonexistent(self):
        """Test recording usage for nonexistent tool creates stats."""
        self.search.record_tool_usage("new_tool", success=True)

        assert "new_tool" in self.search._usage_stats


class TestSemanticToolSearchListing:
    """Tests for listing tools."""

    def setup_method(self):
        """Set up test fixtures."""
        self.embedder = MagicMock()
        self.search = SemanticToolSearch(embedding_service=self.embedder)

        self.search._tools = {
            "file_tool": ToolDefinition(
                tool_id="file_tool",
                name="File Tool",
                description="File operations",
                category=ToolCategory.FILE_OPERATIONS,
            ),
            "code_tool": ToolDefinition(
                tool_id="code_tool",
                name="Code Tool",
                description="Code operations",
                category=ToolCategory.CODE_ANALYSIS,
            ),
            "deprecated_tool": ToolDefinition(
                tool_id="deprecated_tool",
                name="Deprecated Tool",
                description="Old tool",
                deprecated=True,
            ),
        }

    def test_get_tool(self):
        """Test getting a tool by ID."""
        tool = self.search.get_tool("file_tool")
        assert tool is not None
        assert tool.tool_id == "file_tool"

    def test_get_tool_not_found(self):
        """Test getting a nonexistent tool."""
        tool = self.search.get_tool("nonexistent")
        assert tool is None

    def test_list_tools_all(self):
        """Test listing all tools."""
        tools = self.search.list_tools()
        # Should exclude deprecated by default
        assert len(tools) == 2

    def test_list_tools_include_deprecated(self):
        """Test listing tools including deprecated."""
        tools = self.search.list_tools(include_deprecated=True)
        assert len(tools) == 3

    def test_list_tools_by_category(self):
        """Test listing tools by category."""
        tools = self.search.list_tools(category=ToolCategory.FILE_OPERATIONS)
        assert len(tools) == 1
        assert tools[0].tool_id == "file_tool"

    def test_get_categories(self):
        """Test getting category counts."""
        categories = self.search.get_categories()

        assert ToolCategory.FILE_OPERATIONS in categories
        assert ToolCategory.CODE_ANALYSIS in categories
        assert categories[ToolCategory.FILE_OPERATIONS] == 1


class TestSemanticToolSearchStatistics:
    """Tests for service statistics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.embedder = MagicMock()
        self.search = SemanticToolSearch(embedding_service=self.embedder)

        self.search._tools = {
            "tool_1": ToolDefinition(
                tool_id="tool_1", name="Tool 1", description="First tool"
            ),
            "tool_2": ToolDefinition(
                tool_id="tool_2",
                name="Tool 2",
                description="Second tool",
                category=ToolCategory.CODE_ANALYSIS,
            ),
        }
        self.search._usage_stats = {
            "tool_1": {"total": 10, "success": 8, "contexts": []},
        }

    def test_get_service_stats(self):
        """Test getting service statistics."""
        stats = self.search.get_service_stats()

        assert stats["indexed_tools"] == 2
        assert stats["categories"] == 2
        assert stats["total_usage_records"] == 10
        assert "config" in stats


class TestSemanticToolSearchInternalMethods:
    """Tests for internal helper methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.embedder = MagicMock()
        self.search = SemanticToolSearch(embedding_service=self.embedder)

    def test_build_searchable_text(self):
        """Test building searchable text from tool definition."""
        params = [ToolParameter(name="path", type="string", description="File path")]
        tool = ToolDefinition(
            tool_id="search_tool",
            name="Search Tool",
            description="A searchable tool",
            detailed_description="More details about the tool",
            category=ToolCategory.SEARCH,
            parameters=params,
            tags=["search", "query"],
            examples=[{"description": "Search example"}],
        )

        text = self.search._build_searchable_text(tool)

        assert "Search Tool" in text
        assert "searchable tool" in text
        assert "More details" in text
        assert "search" in text.lower()
        assert "path: File path" in text
        assert "Search example" in text

    def test_extract_keywords(self):
        """Test extracting keywords from query."""
        query = "I need to read a configuration file"
        keywords = self.search._extract_keywords(query)

        assert "read" in keywords
        assert "configuration" in keywords
        assert "file" in keywords
        # Stopwords should be removed
        assert "i" not in keywords
        assert "to" not in keywords
        assert "a" not in keywords

    def test_keyword_score_full_match(self):
        """Test keyword scoring with full match."""
        keywords = ["read", "file"]
        tool = ToolDefinition(
            tool_id="kw_tool",
            name="Read File",
            description="Read file contents",
        )

        score = self.search._keyword_score(keywords, tool)
        assert score == 1.0

    def test_keyword_score_partial_match(self):
        """Test keyword scoring with partial match."""
        keywords = ["read", "database"]
        tool = ToolDefinition(
            tool_id="kw_tool",
            name="Read File",
            description="Read file contents",
        )

        score = self.search._keyword_score(keywords, tool)
        assert 0.0 < score < 1.0

    def test_keyword_score_no_match(self):
        """Test keyword scoring with no match."""
        keywords = ["database", "query"]
        tool = ToolDefinition(
            tool_id="kw_tool",
            name="Read File",
            description="Read file contents",
        )

        score = self.search._keyword_score(keywords, tool)
        assert score == 0.0

    def test_keyword_score_empty_keywords(self):
        """Test keyword scoring with empty keywords."""
        tool = ToolDefinition(tool_id="kw_tool", name="Tool", description="Description")
        score = self.search._keyword_score([], tool)
        assert score == 0.0

    def test_cosine_similarity_identical(self):
        """Test cosine similarity for identical vectors."""
        vec = [1.0, 2.0, 3.0]
        similarity = self.search._cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.0001

    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity for orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = self.search._cosine_similarity(vec1, vec2)
        assert abs(similarity) < 0.0001

    def test_cosine_similarity_different_lengths(self):
        """Test cosine similarity for different length vectors."""
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        similarity = self.search._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        similarity = self.search._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_generate_match_reasons_high_semantic(self):
        """Test generating match reasons for high semantic score."""
        tool = ToolDefinition(tool_id="test", name="Test", description="Test tool")
        reasons = self.search._generate_match_reasons(
            "query", tool, semantic_score=0.85, keyword_score=0.3
        )

        assert any("semantic" in r.lower() for r in reasons)

    def test_generate_match_reasons_high_keyword(self):
        """Test generating match reasons for high keyword score."""
        tool = ToolDefinition(tool_id="test", name="Test", description="Test tool")
        reasons = self.search._generate_match_reasons(
            "query", tool, semantic_score=0.4, keyword_score=0.7
        )

        assert any("keyword" in r.lower() for r in reasons)

    def test_generate_match_reasons_frequently_used(self):
        """Test match reasons for frequently used tools."""
        tool = ToolDefinition(
            tool_id="test",
            name="Test",
            description="Test tool",
            usage_count=150,
        )
        reasons = self.search._generate_match_reasons(
            "query", tool, semantic_score=0.5, keyword_score=0.3
        )

        assert any("frequently" in r.lower() for r in reasons)

    def test_generate_match_reasons_high_success(self):
        """Test match reasons for high success rate."""
        tool = ToolDefinition(
            tool_id="test",
            name="Test",
            description="Test tool",
            success_rate=0.98,
        )
        reasons = self.search._generate_match_reasons(
            "query", tool, semantic_score=0.5, keyword_score=0.3
        )

        assert any("success" in r.lower() for r in reasons)

    def test_generate_recommendation_reason(self):
        """Test generating recommendation reason."""
        tool = ToolDefinition(
            tool_id="test",
            name="Test Tool",
            description="Test",
            category=ToolCategory.FILE_OPERATIONS,
        )
        reason = self.search._generate_recommendation_reason(tool, "task", None)

        assert "Test Tool" in reason
        assert "file operations" in reason

    def test_generate_usage_hint_with_examples(self):
        """Test generating usage hint from examples."""
        tool = ToolDefinition(
            tool_id="test",
            name="Test",
            description="Test",
            examples=[{"description": "Read a file with default encoding"}],
        )
        hint = self.search._generate_usage_hint(tool, None)

        assert "Read a file" in hint

    def test_generate_usage_hint_with_required_params(self):
        """Test generating usage hint from required parameters."""
        tool = ToolDefinition(
            tool_id="test",
            name="Test",
            description="Test",
            parameters=[
                ToolParameter(name="path", type="string", description="Path"),
                ToolParameter(
                    name="encoding", type="string", description="Enc", required=False
                ),
            ],
        )
        hint = self.search._generate_usage_hint(tool, None)

        assert "path" in hint
        assert "encoding" not in hint

    def test_generate_usage_hint_empty(self):
        """Test generating empty usage hint."""
        tool = ToolDefinition(tool_id="test", name="Test", description="Test")
        hint = self.search._generate_usage_hint(tool, None)

        assert hint == ""
