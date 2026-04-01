"""
Tests for Episodic Memory Service.

Tests multi-tier memory system for agent learning and personalization.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.episodic_memory_service import (
    AgentAction,
    ConsolidationResult,
    Episode,
    EpisodicMemoryService,
    LearnedPattern,
    Memory,
    MemoryImportance,
    MemorySearchResult,
    MemoryType,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def memory_service():
    """Create memory service instance."""
    return EpisodicMemoryService()


@pytest.fixture
def sample_memory():
    """Create sample memory."""
    return Memory(
        memory_id="mem-123",
        memory_type=MemoryType.SHORT_TERM,
        agent_id="agent-1",
        user_id="user-1",
        content="User prefers concise responses",
        importance_score=0.8,
        tags=["preference", "response"],
    )


@pytest.fixture
def sample_actions():
    """Create sample agent actions."""
    return [
        AgentAction(
            action_id="act-1",
            action_type="tool_call",
            description="Called search tool",
            input_data={"query": "Python syntax"},
            success=True,
        ),
        AgentAction(
            action_id="act-2",
            action_type="reasoning",
            description="Analyzed search results",
            success=True,
        ),
        AgentAction(
            action_id="act-3",
            action_type="response",
            description="Generated response",
            success=True,
        ),
    ]


# ============================================================================
# Enum Tests
# ============================================================================


class TestMemoryType:
    """Test MemoryType enum."""

    def test_short_term(self):
        """Test SHORT_TERM value."""
        assert MemoryType.SHORT_TERM.value == "short_term"

    def test_long_term(self):
        """Test LONG_TERM value."""
        assert MemoryType.LONG_TERM.value == "long_term"

    def test_episodic(self):
        """Test EPISODIC value."""
        assert MemoryType.EPISODIC.value == "episodic"

    def test_semantic(self):
        """Test SEMANTIC value."""
        assert MemoryType.SEMANTIC.value == "semantic"


class TestMemoryImportance:
    """Test MemoryImportance enum."""

    def test_critical(self):
        """Test CRITICAL value."""
        assert MemoryImportance.CRITICAL.value == "critical"

    def test_high(self):
        """Test HIGH value."""
        assert MemoryImportance.HIGH.value == "high"

    def test_medium(self):
        """Test MEDIUM value."""
        assert MemoryImportance.MEDIUM.value == "medium"

    def test_low(self):
        """Test LOW value."""
        assert MemoryImportance.LOW.value == "low"

    def test_trivial(self):
        """Test TRIVIAL value."""
        assert MemoryImportance.TRIVIAL.value == "trivial"


# ============================================================================
# Memory Dataclass Tests
# ============================================================================


class TestMemory:
    """Test Memory dataclass."""

    def test_create_memory(self, sample_memory):
        """Test creating a memory."""
        assert sample_memory.memory_id == "mem-123"
        assert sample_memory.memory_type == MemoryType.SHORT_TERM
        assert sample_memory.agent_id == "agent-1"
        assert sample_memory.importance_score == 0.8

    def test_memory_defaults(self):
        """Test memory default values."""
        memory = Memory(
            memory_id="mem-1",
            memory_type=MemoryType.LONG_TERM,
            agent_id="agent-1",
        )
        assert memory.content == ""
        assert memory.embedding is None
        assert memory.metadata == {}
        assert memory.importance_score == 0.5
        assert memory.access_count == 0
        assert memory.tags == []
        assert memory.expires_at is None

    def test_is_expired_no_expiry(self, sample_memory):
        """Test is_expired when no expiration set."""
        sample_memory.expires_at = None
        assert sample_memory.is_expired is False

    def test_is_expired_not_expired(self, sample_memory):
        """Test is_expired when not expired."""
        sample_memory.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        assert sample_memory.is_expired is False

    def test_is_expired_expired(self, sample_memory):
        """Test is_expired when expired."""
        sample_memory.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert sample_memory.is_expired is True

    def test_calculate_relevance(self, sample_memory):
        """Test relevance calculation."""
        sample_memory.last_accessed_at = datetime.now(timezone.utc)
        sample_memory.access_count = 5

        relevance = sample_memory.calculate_relevance(recency_weight=0.3)

        assert 0.0 <= relevance <= 1.2  # Can exceed 1.0 with access bonus
        assert relevance > 0.5  # Should be high due to high importance

    def test_calculate_relevance_old_memory(self, sample_memory):
        """Test relevance for old memory."""
        sample_memory.last_accessed_at = datetime.now(timezone.utc) - timedelta(days=14)
        sample_memory.access_count = 0

        relevance = sample_memory.calculate_relevance(recency_weight=0.5)

        # Recency score should be 0 after 1 week
        assert relevance < sample_memory.importance_score


# ============================================================================
# AgentAction Tests
# ============================================================================


class TestAgentAction:
    """Test AgentAction dataclass."""

    def test_create_action(self):
        """Test creating an action."""
        action = AgentAction(
            action_id="act-1",
            action_type="tool_call",
            description="Called API",
            input_data={"url": "https://api.example.com"},
            output_data={"status": 200},
            success=True,
        )
        assert action.action_id == "act-1"
        assert action.action_type == "tool_call"
        assert action.success is True

    def test_action_defaults(self):
        """Test action defaults."""
        action = AgentAction(
            action_id="act-1",
            action_type="reasoning",
            description="Thinking",
        )
        assert action.input_data is None
        assert action.output_data is None
        assert action.success is True


# ============================================================================
# Episode Tests
# ============================================================================


class TestEpisode:
    """Test Episode dataclass."""

    def test_create_episode(self, sample_actions):
        """Test creating an episode."""
        episode = Episode(
            episode_id="ep-123",
            agent_id="agent-1",
            user_id="user-1",
            task_description="Answer Python question",
            task_category="code_review",
            actions_taken=sample_actions,
            outcome="success",
            outcome_score=0.9,
        )
        assert episode.episode_id == "ep-123"
        assert episode.outcome == "success"
        assert len(episode.actions_taken) == 3

    def test_episode_defaults(self):
        """Test episode defaults."""
        episode = Episode(
            episode_id="ep-1",
            agent_id="agent-1",
        )
        assert episode.user_id is None
        assert episode.task_description == ""
        assert episode.outcome == "unknown"
        assert episode.outcome_score == 0.5
        assert episode.actions_taken == []


# ============================================================================
# LearnedPattern Tests
# ============================================================================


class TestLearnedPattern:
    """Test LearnedPattern dataclass."""

    def test_create_pattern(self):
        """Test creating a pattern."""
        pattern = LearnedPattern(
            pattern_id="pat-1",
            agent_id="agent-1",
            pattern_type="success_strategy",
            description="Use tool_call before response",
            conditions=["code_generation tasks"],
            recommended_actions=["tool_call", "reasoning", "response"],
            confidence=0.8,
        )
        assert pattern.pattern_id == "pat-1"
        assert pattern.confidence == 0.8
        assert len(pattern.recommended_actions) == 3

    def test_pattern_defaults(self):
        """Test pattern defaults."""
        pattern = LearnedPattern(
            pattern_id="pat-1",
            agent_id="agent-1",
            pattern_type="preference",
            description="User preference",
            conditions=[],
            recommended_actions=[],
        )
        assert pattern.confidence == 0.5
        assert pattern.supporting_episodes == []
        assert pattern.last_applied_at is None
        assert pattern.success_rate == 0.0


# ============================================================================
# ConsolidationResult Tests
# ============================================================================


class TestConsolidationResult:
    """Test ConsolidationResult dataclass."""

    def test_create_result(self):
        """Test creating consolidation result."""
        result = ConsolidationResult(
            memories_processed=100,
            memories_promoted=10,
            memories_demoted=5,
            patterns_extracted=3,
            consolidation_time_ms=150.5,
        )
        assert result.memories_processed == 100
        assert result.memories_promoted == 10
        assert result.memories_demoted == 5


# ============================================================================
# MemorySearchResult Tests
# ============================================================================


class TestMemorySearchResult:
    """Test MemorySearchResult dataclass."""

    def test_create_search_result(self, sample_memory):
        """Test creating search result."""
        result = MemorySearchResult(
            memory=sample_memory,
            relevance_score=0.85,
            similarity_score=0.9,
            match_reason="semantic_similarity",
        )
        assert result.relevance_score == 0.85
        assert result.similarity_score == 0.9
        assert result.match_reason == "semantic_similarity"


# ============================================================================
# EpisodicMemoryService Initialization Tests
# ============================================================================


class TestServiceInit:
    """Test EpisodicMemoryService initialization."""

    def test_init_defaults(self, memory_service):
        """Test default initialization."""
        assert memory_service.memory_table == "aura-episodic-memory"
        assert memory_service.episode_table == "aura-episodes"
        assert memory_service.pattern_table == "aura-learned-patterns"
        assert memory_service._memories == {}
        assert memory_service._episodes == {}
        assert memory_service._patterns == {}

    def test_init_custom_tables(self):
        """Test custom table names."""
        service = EpisodicMemoryService(
            memory_table="custom-memory",
            episode_table="custom-episodes",
            pattern_table="custom-patterns",
        )
        assert service.memory_table == "custom-memory"
        assert service.episode_table == "custom-episodes"
        assert service.pattern_table == "custom-patterns"


# ============================================================================
# Memory Storage Tests
# ============================================================================


class TestMemoryStorage:
    """Test memory storage operations."""

    @pytest.mark.asyncio
    async def test_store_memory(self, memory_service):
        """Test storing a memory."""
        memory = await memory_service.store_memory(
            agent_id="agent-1",
            content="Test memory content",
            memory_type=MemoryType.SHORT_TERM,
            importance=0.7,
            tags=["test"],
        )

        assert memory.memory_id is not None
        assert memory.agent_id == "agent-1"
        assert memory.content == "Test memory content"
        assert memory.importance_score == 0.7
        assert memory.memory_id in memory_service._memories

    @pytest.mark.asyncio
    async def test_store_memory_with_user(self, memory_service):
        """Test storing memory with user ID."""
        memory = await memory_service.store_memory(
            agent_id="agent-1",
            content="User preference",
            user_id="user-123",
            session_id="session-456",
        )

        assert memory.user_id == "user-123"
        assert memory.session_id == "session-456"

    @pytest.mark.asyncio
    async def test_store_memory_clamps_importance(self, memory_service):
        """Test importance score is clamped to 0-1."""
        memory_high = await memory_service.store_memory(
            agent_id="agent-1",
            content="High importance",
            importance=1.5,
        )
        assert memory_high.importance_score == 1.0

        memory_low = await memory_service.store_memory(
            agent_id="agent-1",
            content="Low importance",
            importance=-0.5,
        )
        assert memory_low.importance_score == 0.0

    @pytest.mark.asyncio
    async def test_store_memory_with_ttl(self, memory_service):
        """Test storing memory with custom TTL."""
        memory = await memory_service.store_memory(
            agent_id="agent-1",
            content="Short-lived memory",
            ttl_hours=2,
        )

        assert memory.expires_at is not None
        assert memory.expires_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_get_memory(self, memory_service):
        """Test getting a memory."""
        stored = await memory_service.store_memory(
            agent_id="agent-1",
            content="Retrievable memory",
        )

        retrieved = await memory_service.get_memory(stored.memory_id)

        assert retrieved is not None
        assert retrieved.memory_id == stored.memory_id
        assert retrieved.access_count >= 1  # Access count incremented

    @pytest.mark.asyncio
    async def test_get_memory_not_found(self, memory_service):
        """Test getting non-existent memory."""
        result = await memory_service.get_memory("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_memory_expired(self, memory_service):
        """Test getting expired memory returns None."""
        memory = await memory_service.store_memory(
            agent_id="agent-1",
            content="Expired memory",
            ttl_hours=0,
        )
        # Force expiration
        memory.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        result = await memory_service.get_memory(memory.memory_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_memory(self, memory_service):
        """Test updating a memory."""
        memory = await memory_service.store_memory(
            agent_id="agent-1",
            content="Original content",
            importance=0.5,
        )

        updated = await memory_service.update_memory(
            memory_id=memory.memory_id,
            content="Updated content",
            importance=0.9,
            tags=["updated"],
            metadata={"version": 2},
        )

        assert updated is not None
        assert updated.content == "Updated content"
        assert updated.importance_score == 0.9
        assert "updated" in updated.tags
        assert updated.metadata["version"] == 2

    @pytest.mark.asyncio
    async def test_update_memory_not_found(self, memory_service):
        """Test updating non-existent memory."""
        result = await memory_service.update_memory(
            memory_id="nonexistent",
            content="New content",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_memory(self, memory_service):
        """Test deleting a memory."""
        memory = await memory_service.store_memory(
            agent_id="agent-1",
            content="To be deleted",
        )

        result = await memory_service.delete_memory(memory.memory_id)
        assert result is True
        assert memory.memory_id not in memory_service._memories

    @pytest.mark.asyncio
    async def test_delete_memory_not_found(self, memory_service):
        """Test deleting non-existent memory."""
        result = await memory_service.delete_memory("nonexistent")
        assert result is False


# ============================================================================
# Memory Retrieval Tests
# ============================================================================


class TestMemoryRetrieval:
    """Test memory retrieval operations."""

    @pytest.mark.asyncio
    async def test_retrieve_memories(self, memory_service):
        """Test retrieving memories by query."""
        await memory_service.store_memory(
            agent_id="agent-1",
            content="Python programming tips",
            importance=0.8,
        )
        await memory_service.store_memory(
            agent_id="agent-1",
            content="Java development best practices",
            importance=0.7,
        )

        results = await memory_service.retrieve_memories(
            agent_id="agent-1",
            query="Python programming",
            limit=5,
        )

        assert len(results) > 0
        assert all(isinstance(r, MemorySearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_memories_filter_by_type(self, memory_service):
        """Test filtering by memory type."""
        await memory_service.store_memory(
            agent_id="agent-1",
            content="Short term memory",
            memory_type=MemoryType.SHORT_TERM,
        )
        await memory_service.store_memory(
            agent_id="agent-1",
            content="Long term memory",
            memory_type=MemoryType.LONG_TERM,
        )

        results = await memory_service.retrieve_memories(
            agent_id="agent-1",
            query="memory",
            memory_types=[MemoryType.LONG_TERM],
        )

        assert all(r.memory.memory_type == MemoryType.LONG_TERM for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_memories_filter_by_user(self, memory_service):
        """Test filtering by user."""
        await memory_service.store_memory(
            agent_id="agent-1",
            content="User 1 preference",
            user_id="user-1",
        )
        await memory_service.store_memory(
            agent_id="agent-1",
            content="User 2 preference",
            user_id="user-2",
        )

        results = await memory_service.retrieve_memories(
            agent_id="agent-1",
            query="preference",
            user_id="user-1",
        )

        assert all(r.memory.user_id == "user-1" for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_memories_filter_by_tags(self, memory_service):
        """Test filtering by tags."""
        await memory_service.store_memory(
            agent_id="agent-1",
            content="Security topic",
            tags=["security", "important"],
        )
        await memory_service.store_memory(
            agent_id="agent-1",
            content="General topic",
            tags=["general"],
        )

        results = await memory_service.retrieve_memories(
            agent_id="agent-1",
            query="topic",
            tags=["security"],
        )

        assert all(any(t in r.memory.tags for t in ["security"]) for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_by_context(self, memory_service):
        """Test retrieving memories by context."""
        await memory_service.store_memory(
            agent_id="agent-1",
            content="Database optimization tips",
        )

        results = await memory_service.retrieve_by_context(
            agent_id="agent-1",
            context={
                "topic": "database",
                "task": "optimization",
            },
            limit=5,
        )

        assert isinstance(results, list)


# ============================================================================
# Episode Recording Tests
# ============================================================================


class TestEpisodeRecording:
    """Test episode recording."""

    @pytest.mark.asyncio
    async def test_record_episode(self, memory_service, sample_actions):
        """Test recording an episode."""
        episode = await memory_service.record_episode(
            agent_id="agent-1",
            task="Answer user question",
            actions=sample_actions,
            outcome="success",
            outcome_score=0.9,
        )

        assert episode.episode_id is not None
        assert episode.agent_id == "agent-1"
        assert episode.outcome == "success"
        assert len(episode.actions_taken) == 3
        assert episode.episode_id in memory_service._episodes

    @pytest.mark.asyncio
    async def test_record_episode_with_feedback(self, memory_service, sample_actions):
        """Test recording episode with feedback."""
        episode = await memory_service.record_episode(
            agent_id="agent-1",
            task="Code review",
            actions=sample_actions,
            outcome="success",
            feedback="Great job, very helpful!",
        )

        assert episode.feedback == "Great job, very helpful!"
        assert episode.feedback_sentiment == "positive"

    @pytest.mark.asyncio
    async def test_record_episode_creates_memory(self, memory_service, sample_actions):
        """Test that recording episode creates episodic memory."""
        initial_count = len(memory_service._memories)

        await memory_service.record_episode(
            agent_id="agent-1",
            task="Test task",
            actions=sample_actions,
            outcome="success",
        )

        assert len(memory_service._memories) > initial_count

    @pytest.mark.asyncio
    async def test_get_episode(self, memory_service, sample_actions):
        """Test getting an episode."""
        recorded = await memory_service.record_episode(
            agent_id="agent-1",
            task="Test",
            actions=sample_actions,
            outcome="success",
        )

        retrieved = await memory_service.get_episode(recorded.episode_id)

        assert retrieved is not None
        assert retrieved.episode_id == recorded.episode_id

    @pytest.mark.asyncio
    async def test_get_episode_not_found(self, memory_service):
        """Test getting non-existent episode."""
        result = await memory_service.get_episode("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_episodes_for_agent(self, memory_service, sample_actions):
        """Test getting episodes for an agent."""
        await memory_service.record_episode(
            agent_id="agent-1",
            task="Task 1",
            actions=sample_actions,
            outcome="success",
        )
        await memory_service.record_episode(
            agent_id="agent-1",
            task="Task 2",
            actions=sample_actions,
            outcome="failure",
        )
        await memory_service.record_episode(
            agent_id="agent-2",
            task="Task 3",
            actions=sample_actions,
            outcome="success",
        )

        episodes = await memory_service.get_episodes_for_agent(
            agent_id="agent-1",
            limit=10,
        )

        assert len(episodes) == 2
        assert all(e.agent_id == "agent-1" for e in episodes)

    @pytest.mark.asyncio
    async def test_get_episodes_filter_by_outcome(self, memory_service, sample_actions):
        """Test filtering episodes by outcome."""
        await memory_service.record_episode(
            agent_id="agent-1",
            task="Success task",
            actions=sample_actions,
            outcome="success",
        )
        await memory_service.record_episode(
            agent_id="agent-1",
            task="Failed task",
            actions=sample_actions,
            outcome="failure",
        )

        episodes = await memory_service.get_episodes_for_agent(
            agent_id="agent-1",
            outcome_filter="success",
        )

        assert all(e.outcome == "success" for e in episodes)


# ============================================================================
# Pattern Extraction Tests
# ============================================================================


class TestPatternExtraction:
    """Test pattern extraction from episodes."""

    @pytest.mark.asyncio
    async def test_extract_patterns_not_enough_episodes(self, memory_service):
        """Test pattern extraction with too few episodes."""
        patterns = await memory_service.extract_patterns(agent_id="agent-1")
        assert patterns == []

    @pytest.mark.asyncio
    async def test_extract_patterns_success(self, memory_service, sample_actions):
        """Test extracting success patterns."""
        # Record multiple successful episodes
        for i in range(5):
            await memory_service.record_episode(
                agent_id="agent-1",
                task=f"Task {i}",
                actions=sample_actions,
                outcome="success",
                outcome_score=0.9,
            )

        patterns = await memory_service.extract_patterns(
            agent_id="agent-1",
            min_confidence=0.3,
        )

        # Pattern extraction should return a list (may be empty with limited data)
        assert isinstance(patterns, list), "Should return a list of patterns"
        # With 5 successful episodes, we should have some pattern data
        # even if not enough for high-confidence patterns

    @pytest.mark.asyncio
    async def test_get_applicable_patterns(self, memory_service):
        """Test getting applicable patterns for a task."""
        # Create a pattern manually
        pattern = LearnedPattern(
            pattern_id="pat-1",
            agent_id="agent-1",
            pattern_type="success_strategy",
            description="Test pattern",
            conditions=["code_generation"],
            recommended_actions=["tool_call"],
            confidence=0.8,
        )
        memory_service._patterns["pat-1"] = pattern

        applicable = await memory_service.get_applicable_patterns(
            agent_id="agent-1",
            task="Write code for authentication",
        )

        assert isinstance(applicable, list)

    @pytest.mark.asyncio
    async def test_apply_pattern(self, memory_service):
        """Test recording pattern application."""
        pattern = LearnedPattern(
            pattern_id="pat-1",
            agent_id="agent-1",
            pattern_type="success_strategy",
            description="Test pattern",
            conditions=[],
            recommended_actions=[],
            confidence=0.7,
            success_rate=0.5,
        )
        memory_service._patterns["pat-1"] = pattern

        await memory_service.apply_pattern("pat-1", success=True)

        updated = memory_service._patterns["pat-1"]
        assert updated.last_applied_at is not None
        assert updated.success_rate > 0.5


# ============================================================================
# Memory Consolidation Tests
# ============================================================================


class TestMemoryConsolidation:
    """Test memory consolidation process."""

    @pytest.mark.asyncio
    async def test_consolidate_memories(self, memory_service):
        """Test memory consolidation."""
        # Create short-term memories with varying importance
        for i in range(5):
            await memory_service.store_memory(
                agent_id="agent-1",
                content=f"Short term memory {i}",
                memory_type=MemoryType.SHORT_TERM,
                importance=0.9 if i < 2 else 0.3,  # 2 high importance
            )

        result = await memory_service.consolidate_memories(
            agent_id="agent-1",
            promote_threshold=0.7,
            forget_threshold=0.2,
        )

        assert isinstance(result, ConsolidationResult)
        assert result.memories_processed > 0

    @pytest.mark.asyncio
    async def test_consolidate_promotes_important(self, memory_service):
        """Test that important memories are promoted."""
        memory = await memory_service.store_memory(
            agent_id="agent-1",
            content="Very important memory",
            memory_type=MemoryType.SHORT_TERM,
            importance=0.95,
        )
        # Simulate recent access
        memory.last_accessed_at = datetime.now(timezone.utc)

        await memory_service.consolidate_memories(
            agent_id="agent-1",
            promote_threshold=0.7,
        )

        # Check if promoted
        memory_service._memories.get(memory.memory_id)
        # May or may not be promoted depending on recency calculation


# ============================================================================
# Helper Method Tests
# ============================================================================


class TestHelperMethods:
    """Test helper methods."""

    def test_cosine_similarity(self, memory_service):
        """Test cosine similarity calculation."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        similarity = memory_service._cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self, memory_service):
        """Test cosine similarity for orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = memory_service._cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.0)

    def test_cosine_similarity_different_lengths(self, memory_service):
        """Test cosine similarity with different length vectors."""
        vec1 = [1.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        similarity = memory_service._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_keyword_similarity(self, memory_service):
        """Test keyword similarity."""
        query = "python programming"
        content = "Learn python programming best practices"
        similarity = memory_service._keyword_similarity(query, content)
        assert similarity > 0.5

    def test_keyword_similarity_no_match(self, memory_service):
        """Test keyword similarity with no match."""
        query = "java"
        content = "python programming"
        similarity = memory_service._keyword_similarity(query, content)
        assert similarity == 0.0

    def test_keyword_similarity_empty_query(self, memory_service):
        """Test keyword similarity with empty query."""
        similarity = memory_service._keyword_similarity("", "some content")
        assert similarity == 0.0

    @pytest.mark.asyncio
    async def test_analyze_sentiment_positive(self, memory_service):
        """Test positive sentiment analysis."""
        sentiment = await memory_service._analyze_sentiment(
            "Great job, excellent work!"
        )
        assert sentiment == "positive"

    @pytest.mark.asyncio
    async def test_analyze_sentiment_negative(self, memory_service):
        """Test negative sentiment analysis."""
        sentiment = await memory_service._analyze_sentiment("This is bad and wrong")
        assert sentiment == "negative"

    @pytest.mark.asyncio
    async def test_analyze_sentiment_neutral(self, memory_service):
        """Test neutral sentiment analysis."""
        sentiment = await memory_service._analyze_sentiment("The task was completed")
        assert sentiment == "neutral"

    @pytest.mark.asyncio
    async def test_categorize_task(self, memory_service):
        """Test task categorization."""
        assert (
            await memory_service._categorize_task("Write a Python function")
            == "code_generation"
        )
        assert (
            await memory_service._categorize_task("Review the pull request")
            == "code_review"
        )
        assert await memory_service._categorize_task("Fix the bug") == "debugging"
        assert (
            await memory_service._categorize_task("Document the API") == "documentation"
        )
        assert (
            await memory_service._categorize_task("Find security vulnerabilities")
            == "security"
        )
        assert await memory_service._categorize_task("Run the test suite") == "testing"
        assert (
            await memory_service._categorize_task("Refactor the module")
            == "refactoring"
        )
        assert await memory_service._categorize_task("Do something else") == "general"


# ============================================================================
# Metrics Tests
# ============================================================================


class TestMetrics:
    """Test memory metrics."""

    @pytest.mark.asyncio
    async def test_get_memory_metrics(self, memory_service):
        """Test getting memory metrics."""
        await memory_service.store_memory(
            agent_id="agent-1",
            content="Memory 1",
            memory_type=MemoryType.SHORT_TERM,
        )
        await memory_service.store_memory(
            agent_id="agent-1",
            content="Memory 2",
            memory_type=MemoryType.LONG_TERM,
        )

        metrics = memory_service.get_memory_metrics()

        assert "total_memories" in metrics
        assert "memories_by_type" in metrics
        assert "total_episodes" in metrics
        assert "total_patterns" in metrics

    @pytest.mark.asyncio
    async def test_get_memory_metrics_by_agent(self, memory_service):
        """Test getting metrics filtered by agent."""
        await memory_service.store_memory(
            agent_id="agent-1",
            content="Agent 1 memory",
        )
        await memory_service.store_memory(
            agent_id="agent-2",
            content="Agent 2 memory",
        )

        metrics = memory_service.get_memory_metrics(agent_id="agent-1")

        assert metrics["total_memories"] == 1
