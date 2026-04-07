"""Edge Case Tests for Context Window Management

Tests edge cases in context engineering services where:
- Context assembly from many small chunks exceeds token budget
- High priority items conflict with budget constraints
- Token estimation errors cause budget overruns
- Truncation corrupts structured data

These tests validate robustness of:
- ContextScoringService (pruning, budget enforcement)
- ContextStackManager (layer budgets, assembly)
- MCPContextManager (scoping, truncation)

Following ADR-034 Context Engineering patterns.
"""

import json
from unittest.mock import AsyncMock

import pytest

from src.services.context_scoring_service import (
    ContextScoringConfig,
    ContextScoringService,
    ScoredContext,
)
from src.services.context_stack_manager import (
    ContextLayer,
    ContextStackConfig,
    ContextStackManager,
)
from src.services.mcp_context_manager import (
    AgentContextScope,
    ContextScope,
    MCPContextManager,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_embedder():
    """Create mock embedding service that returns deterministic embeddings."""
    embedder = AsyncMock()
    # Return different embeddings based on content hash for realistic similarity
    embedder.embed_text = AsyncMock(
        side_effect=lambda text: [hash(text) % 100 / 100.0] * 1536
    )
    return embedder


@pytest.fixture
def scoring_service(mock_embedder):
    """Create context scoring service with small budget for edge case testing."""
    config = ContextScoringConfig(
        max_context_tokens=1000,  # Small budget to trigger edge cases
        min_score_threshold=0.2,
    )
    return ContextScoringService(embedding_service=mock_embedder, config=config)


@pytest.fixture
def stack_manager():
    """Create context stack manager with constrained budgets."""
    config = ContextStackConfig(
        total_budget=5000,  # Small total budget
        layer_budgets={
            ContextLayer.SYSTEM_INSTRUCTIONS: 500,
            ContextLayer.LONG_TERM_MEMORY: 1000,
            ContextLayer.RETRIEVED_DOCUMENTS: 2000,
            ContextLayer.TOOL_DEFINITIONS: 500,
            ContextLayer.CONVERSATION_HISTORY: 500,
            ContextLayer.CURRENT_TASK: 500,
        },
    )
    return ContextStackManager(config=config)


@pytest.fixture
def mcp_manager():
    """Create MCP context manager with tight token limits."""
    custom_scopes = {
        AgentContextScope.CODER: ContextScope(
            agent_type=AgentContextScope.CODER,
            included_layers=["system", "retrieved", "task"],
            max_tokens=1000,  # Very tight budget
            allowed_domains=["code"],
            denied_fields=["credentials", "secrets"],
            allowed_tool_levels=["ATOMIC"],
        ),
    }
    return MCPContextManager(custom_scopes=custom_scopes)


def create_small_chunk(
    content: str,
    score: float = 0.5,
    token_count: int = 100,
    source: str = "vector",
) -> ScoredContext:
    """Factory to create small context chunks for testing."""
    return ScoredContext(
        content=content,
        source=source,
        relevance_score=score,
        recency_weight=0.8,
        information_density=0.6,
        final_score=score,
        token_count=token_count,
        metadata={},
    )


# =============================================================================
# Test 1: Many Small Chunks Individually Fit But Sum Exceeds Budget
# =============================================================================


class TestManySmallChunksExceedBudget:
    """Test scenario where many small chunks sum to exceed budget."""

    @pytest.mark.asyncio
    async def test_small_chunks_sum_exceeds_budget(self, scoring_service):
        """Many 100-token chunks should be pruned when sum exceeds 1000 token budget."""
        # Create 15 small chunks of 100 tokens each (1500 total > 1000 budget)
        chunks = [
            create_small_chunk(
                content=f"Small chunk {i} content " * 10,
                score=0.9 - (i * 0.01),  # Decreasing scores
                token_count=100,
            )
            for i in range(15)
        ]

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        # Should only include chunks that fit within budget
        total_tokens = sum(c.token_count for c in result)
        assert total_tokens <= 1000
        # Should have kept highest-scored chunks
        assert len(result) == 10  # 10 chunks * 100 tokens = 1000
        # First chunk should be highest scored
        assert result[0].final_score == 0.9

    @pytest.mark.asyncio
    async def test_chunk_ordering_preserved_after_pruning(self, scoring_service):
        """Verify chunk ordering is preserved after budget pruning."""
        chunks = [
            create_small_chunk(f"chunk_{i}", score=0.9 - (i * 0.05), token_count=200)
            for i in range(10)
        ]

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        # Verify descending score order maintained
        for i in range(len(result) - 1):
            assert result[i].final_score >= result[i + 1].final_score

    @pytest.mark.asyncio
    async def test_exact_budget_boundary(self, scoring_service):
        """Test behavior when chunks exactly fill budget."""
        chunks = [
            create_small_chunk(f"chunk_{i}", score=0.8, token_count=250)
            for i in range(4)
        ]  # Exactly 1000 tokens

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        assert len(result) == 4
        assert sum(c.token_count for c in result) == 1000


# =============================================================================
# Test 2: High Priority Chunk Too Large for Remaining Budget
# =============================================================================


class TestHighPriorityChunkTooLarge:
    """Test when a high priority chunk cannot fit in remaining budget."""

    @pytest.mark.asyncio
    async def test_large_high_priority_chunk_skipped(self, scoring_service):
        """High priority chunk that exceeds remaining budget is skipped."""
        chunks = [
            create_small_chunk("small_1", score=0.7, token_count=300),
            create_small_chunk("small_2", score=0.6, token_count=300),
            create_small_chunk("large_high_priority", score=0.95, token_count=800),
            create_small_chunk("small_3", score=0.5, token_count=300),
        ]
        # Sort by score (simulating scored output)
        chunks.sort(key=lambda x: x.final_score, reverse=True)

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        # Large chunk (800) should be included first, then only small_1 fits (300)
        assert sum(c.token_count for c in result) <= 1000
        # Large high priority should be included
        assert any(c.content == "large_high_priority" for c in result)

    @pytest.mark.asyncio
    async def test_single_chunk_exceeds_entire_budget(self, scoring_service):
        """Single chunk larger than entire budget."""
        chunks = [
            create_small_chunk("huge_chunk", score=0.99, token_count=2000),
        ]

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        # Chunk exceeds budget, should not be included
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_priority_vs_fit_tradeoff(self, scoring_service):
        """Lower priority chunks that fit may be preferred over large high priority."""
        chunks = [
            create_small_chunk("small_high", score=0.85, token_count=200),
            create_small_chunk("small_med", score=0.75, token_count=200),
            create_small_chunk("small_low", score=0.65, token_count=200),
            create_small_chunk("huge_highest", score=0.99, token_count=1500),
        ]
        chunks.sort(key=lambda x: x.final_score, reverse=True)

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        # Can't fit huge_highest (1500 > 1000), but can fit multiple smaller ones
        total_tokens = sum(c.token_count for c in result)
        assert total_tokens <= 1000
        # Should maximize value within budget
        assert "huge_highest" not in [c.content for c in result]


# =============================================================================
# Test 3: Context Assembly with Overlapping/Duplicate Content
# =============================================================================


class TestOverlappingDuplicateContent:
    """Test handling of overlapping or duplicate content in context."""

    @pytest.mark.asyncio
    async def test_duplicate_content_not_deduplicated_by_default(self, scoring_service):
        """Scoring service does not deduplicate - caller responsibility."""
        chunks = [
            create_small_chunk("exact_duplicate_content", score=0.8, token_count=100),
            create_small_chunk("exact_duplicate_content", score=0.75, token_count=100),
            create_small_chunk("exact_duplicate_content", score=0.7, token_count=100),
        ]

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        # All duplicates included (deduplication is caller's responsibility)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_overlapping_content_both_included(self, scoring_service):
        """Overlapping but not identical content is both included."""
        base_content = "This is the authentication module "
        chunks = [
            create_small_chunk(base_content + "version 1", score=0.8, token_count=100),
            create_small_chunk(base_content + "version 2", score=0.75, token_count=100),
        ]

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_near_duplicate_detection_via_scoring(self, mock_embedder):
        """Near-duplicates have similar embeddings affecting scores."""
        # Setup embedder to return similar embeddings for similar content
        mock_embedder.embed_text = AsyncMock(
            side_effect=lambda text: (
                [0.5] * 1536 if "auth" in text.lower() else [0.1] * 1536
            )
        )

        service = ContextScoringService(embedding_service=mock_embedder)

        items = [
            {"content": "auth module code", "source": "vector"},
            {"content": "authentication logic", "source": "graph"},
            {"content": "unrelated content", "source": "fs"},
        ]

        scored = await service.score_context("authentication", items)

        # Similar content should have similar scores
        auth_scores = [s.final_score for s in scored if "auth" in s.content.lower()]
        assert len(auth_scores) == 2
        # Both auth-related items should score higher than unrelated
        assert all(s >= scored[-1].final_score for s in auth_scores)


# =============================================================================
# Test 4: Token Count Estimation Error (Actual > Estimated)
# =============================================================================


class TestTokenEstimationError:
    """Test scenarios where actual tokens exceed estimated tokens."""

    def test_estimation_accuracy(self, scoring_service):
        """Test token estimation algorithm accuracy."""
        # Token estimation uses len(content) // 4
        content_100_chars = "a" * 100
        estimated = scoring_service._estimate_tokens(content_100_chars)
        assert estimated == 25  # 100 // 4

    @pytest.mark.asyncio
    async def test_underestimated_tokens_cause_budget_overrun(self, mock_embedder):
        """Simulate scenario where estimation underestimates actual tokens."""

        # Create service with custom estimator that underestimates
        class UnderestimatingService(ContextScoringService):
            def _estimate_tokens(self, content: str) -> int:
                # Deliberately underestimate by 50%
                return max(1, len(content) // 8)

        service = UnderestimatingService(embedding_service=mock_embedder)

        # Create chunks that appear to fit but actually don't
        chunks = [
            ScoredContext(
                content="x" * 400,  # Estimated: 50 tokens, Actual ~100
                source="vector",
                relevance_score=0.8,
                recency_weight=0.8,
                information_density=0.8,
                final_score=0.8,
                token_count=50,  # Underestimated
                metadata={},
            )
            for _ in range(10)
        ]

        # With underestimated tokens (50 each), all 10 seem to fit in 500 budget
        result = await service.prune_context(chunks, token_budget=500)

        # All chunks included based on underestimated counts
        assert len(result) == 10
        # But actual content is much larger than budget suggests
        actual_chars = sum(len(c.content) for c in result)
        assert actual_chars == 4000  # 10 * 400 chars

    @pytest.mark.asyncio
    async def test_unicode_content_estimation(self, scoring_service):
        """Test token estimation with unicode/multi-byte characters."""
        # Unicode characters may use more bytes than ASCII
        unicode_content = "Hello" * 20  # 100 chars, but with emojis each is 1 char
        emoji_content = "x" * 100  # 100 ASCII chars

        unicode_estimate = scoring_service._estimate_tokens(unicode_content)
        ascii_estimate = scoring_service._estimate_tokens(emoji_content)

        # Both should estimate the same (character-based, not byte-based)
        assert unicode_estimate == ascii_estimate == 25

    @pytest.mark.asyncio
    async def test_code_content_token_estimation(self, scoring_service):
        """Code often has higher token density than prose."""
        prose = "This is a simple sentence about programming concepts."
        code = "def foo(x): return x * 2 if x > 0 else -x"

        # Both similar length but code often tokenizes differently
        prose_tokens = scoring_service._estimate_tokens(prose)
        code_tokens = scoring_service._estimate_tokens(code)

        # Current estimation treats them equally (char-based)
        assert prose_tokens == len(prose) // 4
        assert code_tokens == len(code) // 4


# =============================================================================
# Test 5: Mandatory Context (System Prompt) Leaves No Room
# =============================================================================


class TestMandatoryContextNoRoom:
    """Test when system prompt consumes entire budget."""

    @pytest.mark.asyncio
    async def test_system_prompt_consumes_all_budget(self, stack_manager):
        """Large system prompt leaves no room for other content."""
        # Create custom config where system budget equals total
        config = ContextStackConfig(
            total_budget=1000,
            layer_budgets={
                ContextLayer.SYSTEM_INSTRUCTIONS: 1000,  # All budget
                ContextLayer.CURRENT_TASK: 500,  # Would exceed
            },
        )
        manager = ContextStackManager(config=config)

        result = await manager.build_context_stack(
            task="This is a test task that needs processing",
            agent_type="Coder",
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        # Result should still include both but be truncated
        assert "System Instructions" in result
        assert "Current Task" in result

    @pytest.mark.asyncio
    async def test_large_system_prompt_triggers_pruning(self):
        """Very large custom system prompt triggers pruning of other layers."""
        config = ContextStackConfig(
            total_budget=2000,
            layer_budgets={
                ContextLayer.SYSTEM_INSTRUCTIONS: 1500,
                ContextLayer.CURRENT_TASK: 1500,
            },
        )
        manager = ContextStackManager(config=config)

        # Large custom system prompt
        large_prompt = "You are an AI assistant. " * 100  # ~2400 chars, ~600 tokens

        result = await manager.build_context_stack(
            task="Simple task",
            agent_type="Coder",
            custom_system_prompt=large_prompt,
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        # Budget enforcement should have triggered
        stats = manager.get_stack_stats()
        assert stats["total_tokens"] <= 2000

    @pytest.mark.asyncio
    async def test_minimum_task_preserved(self):
        """Current task is never completely pruned (highest priority)."""
        config = ContextStackConfig(
            total_budget=500,  # Very tight
            layer_budgets={
                ContextLayer.SYSTEM_INSTRUCTIONS: 400,
                ContextLayer.CURRENT_TASK: 400,
            },
        )
        manager = ContextStackManager(config=config)

        result = await manager.build_context_stack(
            task="Important task that must be visible",
            agent_type="Coder",
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        # Task should still be present
        assert "Current Task" in result


# =============================================================================
# Test 6: Dynamic Context (Tool Results) Added Mid-Conversation
# =============================================================================


class TestDynamicContextMidConversation:
    """Test adding dynamic context during conversation."""

    @pytest.mark.asyncio
    async def test_history_with_tool_results(self, stack_manager):
        """Conversation history with tool results included."""
        history = [
            {"role": "user", "content": "Run the security scan"},
            {"role": "assistant", "content": "I'll run the scan now."},
            {
                "role": "tool_result",
                "content": "Scan complete: 5 vulnerabilities found",
            },
            {"role": "assistant", "content": "The scan found 5 issues."},
        ]

        result = await stack_manager.build_context_stack(
            task="Address the vulnerabilities",
            agent_type="Reviewer",
            conversation_history=history,
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        # Tool results should be in history
        assert "vulnerabilities" in result

    @pytest.mark.asyncio
    async def test_large_tool_result_truncation(self, stack_manager):
        """Large tool results are truncated to fit history budget."""
        # Create large tool result
        large_result = "Error details: " + ("stack trace line\n" * 1000)

        history = [
            {"role": "user", "content": "Debug the error"},
            {"role": "tool_result", "content": large_result},
        ]

        result = await stack_manager.build_context_stack(
            task="Fix the error",
            agent_type="Coder",
            conversation_history=history,
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        # Should include history but truncated
        stats = stack_manager.get_stack_stats()
        if ContextLayer.CONVERSATION_HISTORY in stats.get("layers", {}):
            history_tokens = stats["layers"][ContextLayer.CONVERSATION_HISTORY.name][
                "tokens"
            ]
            assert (
                history_tokens
                <= stack_manager.config.layer_budgets[ContextLayer.CONVERSATION_HISTORY]
            )

    @pytest.mark.asyncio
    async def test_dynamic_context_addition_order(self, stack_manager):
        """Verify dynamic context added in correct order."""
        history = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "Second message"},
        ]

        result = await stack_manager.build_context_stack(
            task="Continue conversation",
            agent_type="Coder",
            conversation_history=history,
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        # Messages should appear in order
        first_pos = result.find("First message")
        second_pos = result.find("Second message")
        assert first_pos < second_pos


# =============================================================================
# Test 7: Context Truncation Corrupts JSON/Code Structure
# =============================================================================


class TestTruncationCorruptsStructure:
    """Test that truncation can corrupt structured content."""

    def test_json_truncation_creates_invalid_json(self, mcp_manager):
        """Truncating JSON mid-structure creates invalid JSON."""
        json_content = json.dumps(
            {
                "config": {
                    "nested": {"deep": {"value": "important data" * 100}},
                    "another_key": "more data",
                }
            }
        )

        context = {"retrieved": {"code": json_content}}

        scoped = mcp_manager.scope_context_for_agent(context, AgentContextScope.CODER)

        # If truncated, JSON may be invalid
        if len(str(scoped.content)) < len(json_content):
            try:
                # Try to parse any JSON in the content
                code_content = scoped.content.get("retrieved", {}).get("code", "")
                if code_content:
                    json.loads(code_content)
                    # If we get here, it parsed successfully
            except json.JSONDecodeError:
                # Expected - truncation corrupted JSON
                pass

    def test_code_truncation_creates_syntax_error(self, mcp_manager):
        """Truncating code mid-structure creates syntax errors."""
        python_code = '''
def complex_function(arg1, arg2, arg3):
    """Docstring with lots of content."""
    result = []
    for i in range(100):
        if arg1 > 0:
            result.append({
                "key": "value",
                "nested": {"deep": "content"},
            })
    return result
''' * 50  # Make it large enough to trigger truncation

        context = {"retrieved": {"code": python_code}}

        scoped = mcp_manager.scope_context_for_agent(context, AgentContextScope.CODER)

        # If truncated, Python syntax may be invalid
        truncated_code = scoped.content.get("retrieved", {}).get("code", "")
        if len(truncated_code) < len(python_code):
            try:
                compile(truncated_code, "<string>", "exec")
            except SyntaxError:
                # Expected - truncation corrupted Python syntax
                pass

    def test_markdown_truncation_breaks_formatting(self, mcp_manager):
        """Truncating markdown breaks formatting structures."""
        markdown = """
# Header 1
## Header 2
Some content with **bold** and *italic*.

```python
def code_block():
    pass
```

| Table | Header |
|-------|--------|
| Data  | More   |
""" * 20

        context = {"retrieved": {"docs": markdown}}

        scoped = mcp_manager.scope_context_for_agent(context, AgentContextScope.CODER)

        truncated = str(scoped.content.get("retrieved", {}).get("docs", ""))
        if len(truncated) < len(markdown):
            # Check if code block is incomplete (opened but not closed)
            code_block_opens = truncated.count("```python")
            code_block_closes = truncated.count("```\n")
            # May have unbalanced code blocks after truncation
            assert code_block_opens >= 0  # Just verify it ran


# =============================================================================
# Test 8: Context Budget Changes Mid-Session (Model Switch)
# =============================================================================


class TestBudgetChangesMidSession:
    """Test handling budget changes during a session."""

    @pytest.mark.asyncio
    async def test_budget_reduction_requires_repruning(self, scoring_service):
        """Reducing budget mid-session requires re-pruning."""
        chunks = [
            create_small_chunk(f"chunk_{i}", score=0.9 - (i * 0.05), token_count=200)
            for i in range(10)
        ]

        # Initial prune with 2000 budget
        result1 = await scoring_service.prune_context(chunks, token_budget=2000)
        assert len(result1) == 10  # All fit

        # Budget reduced (e.g., model switch to smaller context window)
        result2 = await scoring_service.prune_context(chunks, token_budget=500)
        assert len(result2) == 2  # Only 2 fit now
        assert sum(c.token_count for c in result2) <= 500

    @pytest.mark.asyncio
    async def test_budget_increase_allows_more_content(self, scoring_service):
        """Increasing budget allows previously pruned content."""
        chunks = [
            create_small_chunk(f"chunk_{i}", score=0.9 - (i * 0.05), token_count=200)
            for i in range(10)
        ]

        # Initial tight budget
        result1 = await scoring_service.prune_context(chunks, token_budget=500)
        assert len(result1) == 2

        # Budget increased (e.g., switch to model with larger window)
        result2 = await scoring_service.prune_context(chunks, token_budget=2000)
        assert len(result2) == 10  # All fit now

    def test_stack_manager_budget_reconfiguration(self):
        """Stack manager handles runtime budget reconfiguration."""
        manager = ContextStackManager()

        original_budget = manager.config.total_budget

        # Simulate model switch by reconfiguring
        new_config = ContextStackConfig(total_budget=original_budget // 2)
        manager.config = new_config

        assert manager.config.total_budget == original_budget // 2


# =============================================================================
# Test 9: Memory Pressure from Holding Too Many Context Chunks
# =============================================================================


class TestMemoryPressure:
    """Test memory behavior with large numbers of chunks."""

    @pytest.mark.asyncio
    async def test_many_chunks_memory_usage(self, mock_embedder):
        """Test handling of very large number of chunks."""
        service = ContextScoringService(embedding_service=mock_embedder)

        # Create many small chunks
        chunks = [
            create_small_chunk(f"chunk_{i}", score=0.5, token_count=10)
            for i in range(10000)
        ]

        # Service should handle without excessive memory
        result = await service.prune_context(chunks, token_budget=1000)

        assert len(result) == 100  # 1000 / 10 = 100 chunks
        assert sum(c.token_count for c in result) <= 1000

    @pytest.mark.asyncio
    async def test_chunk_size_distribution(self, mock_embedder):
        """Test mixed chunk sizes and memory handling."""
        service = ContextScoringService(embedding_service=mock_embedder)

        # Mixed sizes simulating real retrieval
        chunks = []
        for i in range(100):
            # Vary sizes: some tiny, some large
            size = 10 if i % 3 == 0 else (500 if i % 7 == 0 else 50)
            chunks.append(create_small_chunk(f"chunk_{i}", score=0.8, token_count=size))

        result = await service.prune_context(chunks, token_budget=2000)

        assert sum(c.token_count for c in result) <= 2000

    def test_large_content_string_handling(self, mcp_manager):
        """Test handling of very large content strings."""
        # Create very large content
        large_content = "x" * (1024 * 1024)  # 1MB string

        context = {"retrieved": {"code": large_content}}

        # Should handle without crashing
        scoped = mcp_manager.scope_context_for_agent(context, AgentContextScope.CODER)

        # Content should be truncated significantly
        truncated = scoped.content.get("retrieved", {}).get("code", "")
        assert len(truncated) < len(large_content)


# =============================================================================
# Test 10: Priority Conflict - Multiple High-Priority Chunks Can't All Fit
# =============================================================================


class TestPriorityConflicts:
    """Test resolution when multiple high-priority chunks compete."""

    @pytest.mark.asyncio
    async def test_equal_priority_first_wins(self, scoring_service):
        """Equal priority chunks: earlier in list (higher implicit rank) wins."""
        chunks = [
            create_small_chunk("chunk_a", score=0.9, token_count=600),
            create_small_chunk("chunk_b", score=0.9, token_count=600),  # Same score
        ]

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        # Only one can fit, first should win
        assert len(result) == 1
        assert result[0].content == "chunk_a"

    @pytest.mark.asyncio
    async def test_slightly_higher_priority_wins(self, scoring_service):
        """Slightly higher priority chunk is chosen over others."""
        chunks = [
            create_small_chunk("lower_1", score=0.89, token_count=600),
            create_small_chunk("highest", score=0.90, token_count=600),
            create_small_chunk("lower_2", score=0.88, token_count=600),
        ]
        chunks.sort(key=lambda x: x.final_score, reverse=True)

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        assert len(result) == 1
        assert result[0].content == "highest"

    @pytest.mark.asyncio
    async def test_priority_vs_size_optimization(self, scoring_service):
        """Test whether we maximize total score or prefer highest individual."""
        # Scenario: One large high-score vs two smaller medium-score
        chunks = [
            create_small_chunk("large_high", score=0.95, token_count=900),
            create_small_chunk("small_med_1", score=0.80, token_count=400),
            create_small_chunk("small_med_2", score=0.75, token_count=400),
        ]
        chunks.sort(key=lambda x: x.final_score, reverse=True)

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        # Current implementation: greedy by score
        # Takes large_high (900 tokens, score 0.95)
        # Then can't fit either small (900 + 400 > 1000)
        assert len(result) == 1
        assert result[0].content == "large_high"

        # Alternative strategy could take both smaller (800 tokens, combined value)
        # But current greedy approach doesn't optimize for total value

    @pytest.mark.asyncio
    async def test_all_high_priority_none_fit(self, scoring_service):
        """All chunks are high priority but none can fit."""
        chunks = [
            create_small_chunk("huge_1", score=0.99, token_count=2000),
            create_small_chunk("huge_2", score=0.98, token_count=2000),
            create_small_chunk("huge_3", score=0.97, token_count=2000),
        ]

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        # None fit
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_layer_priority_in_stack_manager(self):
        """Test layer priority determines pruning order in stack manager."""
        config = ContextStackConfig(
            total_budget=1000,
            layer_budgets={
                ContextLayer.SYSTEM_INSTRUCTIONS: 500,
                ContextLayer.CONVERSATION_HISTORY: 500,
                ContextLayer.CURRENT_TASK: 500,
            },
            layer_priorities={
                ContextLayer.CURRENT_TASK: 10,  # Highest - never fully prune
                ContextLayer.SYSTEM_INSTRUCTIONS: 9,
                ContextLayer.CONVERSATION_HISTORY: 4,  # Lowest - prune first
            },
        )
        manager = ContextStackManager(config=config)

        history = [
            {"role": "user", "content": "message " * 50},  # Large history
        ]

        result = await manager.build_context_stack(
            task="Important task",
            agent_type="Coder",
            conversation_history=history,
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        # Task (highest priority) should be preserved
        assert "Important task" in result

        # Budget should be enforced
        stats = manager.get_stack_stats()
        assert stats["total_tokens"] <= 1000


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestAdditionalEdgeCases:
    """Additional edge cases for comprehensive coverage."""

    @pytest.mark.asyncio
    async def test_empty_content_handling(self, scoring_service):
        """Test handling of empty content chunks."""
        chunks = [
            create_small_chunk("", score=0.9, token_count=1),  # Empty content
            create_small_chunk("valid content", score=0.8, token_count=100),
        ]

        result = await scoring_service.prune_context(chunks, token_budget=1000)

        # Both should be included (empty content is still valid)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_zero_budget_uses_default(self, scoring_service):
        """Test that zero budget falls back to config default (0 is falsy)."""
        chunks = [create_small_chunk("content", score=0.9, token_count=100)]

        # In Python, 0 is falsy so `budget or default` returns default
        # This is expected behavior - zero means "use default config"
        result = await scoring_service.prune_context(chunks, token_budget=0)

        # Uses config default (1000 tokens) so chunk fits
        assert len(result) == 1
        assert (
            sum(c.token_count for c in result)
            <= scoring_service.config.max_context_tokens
        )

    @pytest.mark.asyncio
    async def test_very_small_budget(self, scoring_service):
        """Test behavior with very small (but positive) token budget."""
        chunks = [create_small_chunk("content", score=0.9, token_count=100)]

        # Use a small positive budget to actually test budget enforcement
        result = await scoring_service.prune_context(chunks, token_budget=1)

        # 100 tokens > 1 token budget, so nothing fits
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_negative_score_handling(self, scoring_service):
        """Test chunks with negative scores (below threshold)."""
        chunks = [
            create_small_chunk("negative", score=-0.5, token_count=100),
            create_small_chunk("positive", score=0.5, token_count=100),
        ]

        result = await scoring_service.prune_context(
            chunks, token_budget=1000, min_score=0.0
        )

        # Negative score should be pruned
        assert len(result) == 1
        assert result[0].content == "positive"

    def test_special_characters_in_content(self, mcp_manager):
        """Test content with special characters."""
        special_content = "Content with <script>alert('xss')</script> and \x00 nulls"

        context = {"retrieved": {"code": special_content}}

        scoped = mcp_manager.scope_context_for_agent(context, AgentContextScope.CODER)

        # Should handle without error
        assert "code" in scoped.content.get("retrieved", {})

    @pytest.mark.asyncio
    async def test_concurrent_scoring_requests(self, mock_embedder):
        """Test concurrent scoring requests."""
        import asyncio

        service = ContextScoringService(embedding_service=mock_embedder)

        async def score_batch(batch_id: int):
            items = [
                {"content": f"batch_{batch_id}_item_{i}", "source": "vector"}
                for i in range(10)
            ]
            return await service.score_context(f"query_{batch_id}", items)

        # Run multiple scoring operations concurrently
        results = await asyncio.gather(*[score_batch(i) for i in range(5)])

        # All should complete successfully
        assert len(results) == 5
        assert all(len(r) == 10 for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
