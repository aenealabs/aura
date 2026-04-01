"""Project Aura - Episodic Memory Service

Multi-tier memory system for agent learning and personalization with
persistent knowledge across sessions.

Implements AWS Bedrock AgentCore Memory parity (ADR-030 Phase 1.2):
- Short-term working memory (within session)
- Long-term persistent memory (across sessions)
- Episodic experience-based learning
- Semantic factual knowledge
- Industry-leading accuracy for memory retrieval

Author: Project Aura Team
Date: 2025-12-11
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, ValuesView, cast

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of memory in the multi-tier system."""

    SHORT_TERM = "short_term"  # Within session, working memory
    LONG_TERM = "long_term"  # Across sessions, persistent
    EPISODIC = "episodic"  # Experience-based learning
    SEMANTIC = "semantic"  # Factual knowledge


class MemoryImportance(Enum):
    """Importance levels for memory retention."""

    CRITICAL = "critical"  # Never forget (1.0)
    HIGH = "high"  # Very important (0.8)
    MEDIUM = "medium"  # Moderately important (0.5)
    LOW = "low"  # Can be forgotten (0.3)
    TRIVIAL = "trivial"  # Easily forgotten (0.1)


@dataclass
class Memory:
    """A single memory unit in the system."""

    memory_id: str
    memory_type: MemoryType
    agent_id: str
    user_id: str | None = None
    session_id: str | None = None
    content: str = ""
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    importance_score: float = 0.5  # 0.0 - 1.0
    access_count: int = 0
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expires_at: datetime | None = None

    @property
    def is_expired(self) -> bool:
        """Check if memory has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def calculate_relevance(self, recency_weight: float = 0.3) -> float:
        """Calculate overall relevance score combining importance and recency.

        Args:
            recency_weight: Weight for recency factor (0-1)

        Returns:
            Combined relevance score (0-1)
        """
        # Recency decay: memories accessed recently score higher
        hours_since_access = (
            datetime.now(timezone.utc) - self.last_accessed_at
        ).total_seconds() / 3600
        recency_score = max(0, 1 - (hours_since_access / 168))  # Decay over 1 week

        # Access frequency bonus
        access_bonus = min(0.2, self.access_count * 0.02)

        # Combined score
        return (
            self.importance_score * (1 - recency_weight)
            + recency_score * recency_weight
            + access_bonus
        )


@dataclass
class AgentAction:
    """An action taken by an agent during execution."""

    action_id: str
    action_type: str  # tool_call, reasoning, response, error
    description: str
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    success: bool = True
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Episode:
    """A complete interaction episode for learning."""

    episode_id: str
    agent_id: str
    user_id: str | None = None
    session_id: str | None = None
    task_description: str = ""
    task_category: str | None = None
    actions_taken: list[AgentAction] = field(default_factory=list)
    outcome: str = "unknown"  # success, failure, partial, unknown
    outcome_score: float = 0.5  # 0.0 - 1.0
    feedback: str | None = None
    feedback_sentiment: str | None = None  # positive, negative, neutral
    learned_patterns: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class LearnedPattern:
    """A pattern learned from episodes."""

    pattern_id: str
    agent_id: str
    pattern_type: str  # success_strategy, failure_mode, preference, optimization
    description: str
    conditions: list[str]  # When this pattern applies
    recommended_actions: list[str]  # What to do
    confidence: float = 0.5  # 0.0 - 1.0
    supporting_episodes: list[str] = field(default_factory=list)  # Episode IDs
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_applied_at: datetime | None = None
    success_rate: float = 0.0  # When applied, how often successful


@dataclass
class ConsolidationResult:
    """Result of memory consolidation operation."""

    memories_processed: int
    memories_promoted: int  # Short-term → Long-term
    memories_demoted: int  # Long-term → removed (forgotten)
    patterns_extracted: int
    consolidation_time_ms: float


@dataclass
class MemorySearchResult:
    """Result of memory search with relevance scoring."""

    memory: Memory
    relevance_score: float
    similarity_score: float | None = None  # Embedding similarity if available
    match_reason: str = "content_match"


class EpisodicMemoryService:
    """
    Multi-tier memory system for agent learning and personalization.

    Implements AWS AgentCore Memory parity:
    - Short-term working memory
    - Long-term persistent memory
    - Episodic experience-based learning
    - Semantic factual knowledge

    Memory Consolidation Process:
    1. Short-term memories are created during sessions
    2. Important short-term memories are promoted to long-term
    3. Episodes are analyzed to extract learned patterns
    4. Patterns inform future agent behavior

    Example usage:
        memory_service = EpisodicMemoryService()

        # Store a memory
        memory = await memory_service.store_memory(
            agent_id="my-agent",
            content="User prefers concise responses",
            memory_type=MemoryType.LONG_TERM,
            importance=0.8,
        )

        # Retrieve relevant memories
        memories = await memory_service.retrieve_memories(
            agent_id="my-agent",
            query="response style preferences",
            limit=5,
        )

        # Record an episode
        episode = await memory_service.record_episode(
            agent_id="my-agent",
            task="Answer user question about Python",
            actions=[...],
            outcome="success",
        )

        # Extract patterns from episodes
        patterns = await memory_service.extract_patterns(agent_id="my-agent")
    """

    def __init__(
        self,
        dynamodb_client: Any | None = None,
        opensearch_client: Any | None = None,
        bedrock_client: Any | None = None,
        memory_table: str | None = None,
        episode_table: str | None = None,
        pattern_table: str | None = None,
        opensearch_index: str | None = None,
    ):
        """Initialize Episodic Memory Service.

        Args:
            dynamodb_client: Boto3 DynamoDB client for storage
            opensearch_client: OpenSearch client for vector search
            bedrock_client: Bedrock client for embeddings
            memory_table: DynamoDB table for memories
            episode_table: DynamoDB table for episodes
            pattern_table: DynamoDB table for patterns
            opensearch_index: OpenSearch index for vector search
        """
        self.dynamodb = dynamodb_client
        self.opensearch = opensearch_client
        self.bedrock = bedrock_client

        self.memory_table = memory_table or os.getenv(
            "AURA_MEMORY_TABLE", "aura-episodic-memory"
        )
        self.episode_table = episode_table or os.getenv(
            "AURA_EPISODE_TABLE", "aura-episodes"
        )
        self.pattern_table = pattern_table or os.getenv(
            "AURA_PATTERN_TABLE", "aura-learned-patterns"
        )
        self.opensearch_index = opensearch_index or os.getenv(
            "AURA_MEMORY_INDEX", "aura-memory-vectors"
        )

        # In-memory storage (replace with real storage in production)
        self._memories: dict[str, Memory] = {}
        self._episodes: dict[str, Episode] = {}
        self._patterns: dict[str, LearnedPattern] = {}

        # Default TTLs by memory type
        self._default_ttls = {
            MemoryType.SHORT_TERM: timedelta(hours=24),
            MemoryType.LONG_TERM: None,  # No expiration
            MemoryType.EPISODIC: timedelta(days=90),
            MemoryType.SEMANTIC: None,  # No expiration
        }

        logger.info("Initialized EpisodicMemoryService")

    # =========================================================================
    # Memory Storage Operations
    # =========================================================================

    async def store_memory(
        self,
        agent_id: str,
        content: str,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        user_id: str | None = None,
        session_id: str | None = None,
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        ttl_hours: float | None = None,
    ) -> Memory:
        """Store a new memory with automatic embedding.

        Args:
            agent_id: Agent this memory belongs to
            content: Memory content text
            memory_type: Type of memory
            user_id: Optional user for personalization
            session_id: Optional session context
            importance: Importance score (0-1)
            tags: Optional tags for categorization
            metadata: Additional metadata
            ttl_hours: Optional custom TTL

        Returns:
            Created Memory object
        """
        memory_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Calculate expiration
        if ttl_hours is not None:
            expires_at = now + timedelta(hours=ttl_hours)
        else:
            default_ttl = self._default_ttls.get(memory_type)
            if default_ttl is not None:
                expires_at = now + default_ttl
            else:
                expires_at = None

        # Generate embedding if available
        embedding = await self._generate_embedding(content)

        memory = Memory(
            memory_id=memory_id,
            memory_type=memory_type,
            agent_id=agent_id,
            user_id=user_id,
            session_id=session_id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            importance_score=min(1.0, max(0.0, importance)),
            tags=tags or [],
            created_at=now,
            last_accessed_at=now,
            expires_at=expires_at,
        )

        # Store in memory (and persist to DynamoDB/OpenSearch)
        self._memories[memory_id] = memory
        await self._persist_memory(memory)

        logger.info(
            f"Stored {memory_type.value} memory {memory_id} for agent {agent_id} "
            f"(importance: {importance:.2f})"
        )

        return memory

    async def get_memory(self, memory_id: str) -> Memory | None:
        """Get a specific memory by ID.

        Args:
            memory_id: Memory identifier

        Returns:
            Memory or None if not found
        """
        memory = self._memories.get(memory_id)
        if memory and not memory.is_expired:
            memory.access_count += 1
            memory.last_accessed_at = datetime.now(timezone.utc)
            return memory
        return None

    async def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        importance: float | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Memory | None:
        """Update an existing memory.

        Args:
            memory_id: Memory identifier
            content: New content (triggers re-embedding)
            importance: New importance score
            tags: New tags
            metadata: Metadata updates (merged)

        Returns:
            Updated Memory or None if not found
        """
        memory = self._memories.get(memory_id)
        if not memory or memory.is_expired:
            return None

        if content is not None and content != memory.content:
            memory.content = content
            memory.embedding = await self._generate_embedding(content)

        if importance is not None:
            memory.importance_score = min(1.0, max(0.0, importance))

        if tags is not None:
            memory.tags = tags

        if metadata is not None:
            memory.metadata.update(metadata)

        memory.last_accessed_at = datetime.now(timezone.utc)

        await self._persist_memory(memory)
        return memory

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory.

        Args:
            memory_id: Memory identifier

        Returns:
            True if deleted, False if not found
        """
        if memory_id in self._memories:
            del self._memories[memory_id]
            # Also delete from persistent storage
            logger.info(f"Deleted memory: {memory_id}")
            return True
        return False

    # =========================================================================
    # Memory Retrieval
    # =========================================================================

    async def retrieve_memories(
        self,
        agent_id: str,
        query: str,
        memory_types: list[MemoryType] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
        min_relevance: float = 0.3,
        include_expired: bool = False,
    ) -> list[MemorySearchResult]:
        """Retrieve relevant memories using semantic search.

        Args:
            agent_id: Agent to search memories for
            query: Natural language query
            memory_types: Filter by memory types
            user_id: Filter by user
            session_id: Filter by session
            tags: Filter by tags
            limit: Maximum results
            min_relevance: Minimum relevance threshold
            include_expired: Include expired memories

        Returns:
            List of MemorySearchResult sorted by relevance
        """
        # Generate query embedding
        query_embedding = await self._generate_embedding(query)

        # Filter memories
        candidates = []
        for memory in self._memories.values():
            # Skip expired unless requested
            if not include_expired and memory.is_expired:
                continue

            # Agent filter
            if memory.agent_id != agent_id:
                continue

            # Type filter
            if memory_types and memory.memory_type not in memory_types:
                continue

            # User filter
            if user_id and memory.user_id != user_id:
                continue

            # Session filter
            if session_id and memory.session_id != session_id:
                continue

            # Tag filter
            if tags and not any(t in memory.tags for t in tags):
                continue

            candidates.append(memory)

        # Calculate relevance scores
        results = []
        for memory in candidates:
            # Semantic similarity if embeddings available
            if query_embedding and memory.embedding:
                similarity = self._cosine_similarity(query_embedding, memory.embedding)
            else:
                # Fallback to keyword matching
                similarity = self._keyword_similarity(query, memory.content)

            # Combined relevance
            relevance = similarity * 0.6 + memory.calculate_relevance() * 0.4

            if relevance >= min_relevance:
                # Update access stats
                memory.access_count += 1
                memory.last_accessed_at = datetime.now(timezone.utc)

                results.append(
                    MemorySearchResult(
                        memory=memory,
                        relevance_score=relevance,
                        similarity_score=similarity,
                        match_reason=(
                            "semantic_similarity"
                            if query_embedding
                            else "keyword_match"
                        ),
                    )
                )

        # Sort by relevance and limit
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:limit]

    async def retrieve_by_context(
        self,
        agent_id: str,
        context: dict[str, Any],
        limit: int = 10,
    ) -> list[Memory]:
        """Retrieve memories relevant to a context.

        Args:
            agent_id: Agent identifier
            context: Context dictionary with relevant keys
            limit: Maximum results

        Returns:
            List of relevant memories
        """
        # Build query from context
        query_parts = []
        for _key, value in context.items():
            if isinstance(value, str):
                query_parts.append(value)
            elif isinstance(value, list):
                query_parts.extend(str(v) for v in value[:3])

        query = " ".join(query_parts[:10])  # Limit query length

        results = await self.retrieve_memories(
            agent_id=agent_id,
            query=query,
            limit=limit,
        )

        return [r.memory for r in results]

    # =========================================================================
    # Episode Recording
    # =========================================================================

    async def record_episode(
        self,
        agent_id: str,
        task: str,
        actions: list[AgentAction],
        outcome: str,
        outcome_score: float = 0.5,
        user_id: str | None = None,
        session_id: str | None = None,
        feedback: str | None = None,
        context: dict[str, Any] | None = None,
        duration_seconds: float = 0.0,
    ) -> Episode:
        """Record a complete interaction episode for learning.

        Args:
            agent_id: Agent that executed the episode
            task: Description of the task
            actions: Actions taken during episode
            outcome: Outcome classification
            outcome_score: Numeric outcome score (0-1)
            user_id: Optional user identifier
            session_id: Optional session identifier
            feedback: Optional user feedback
            context: Additional context
            duration_seconds: Episode duration

        Returns:
            Created Episode
        """
        episode_id = str(uuid.uuid4())

        # Analyze feedback sentiment if provided
        feedback_sentiment = None
        if feedback:
            feedback_sentiment = await self._analyze_sentiment(feedback)

        episode = Episode(
            episode_id=episode_id,
            agent_id=agent_id,
            user_id=user_id,
            session_id=session_id,
            task_description=task,
            task_category=await self._categorize_task(task),
            actions_taken=actions,
            outcome=outcome,
            outcome_score=outcome_score,
            feedback=feedback,
            feedback_sentiment=feedback_sentiment,
            context=context or {},
            duration_seconds=duration_seconds,
        )

        # Store episode
        self._episodes[episode_id] = episode
        await self._persist_episode(episode)

        # Create episodic memory from the episode
        await self.store_memory(
            agent_id=agent_id,
            content=f"Task: {task}. Outcome: {outcome}. Actions: {len(actions)}",
            memory_type=MemoryType.EPISODIC,
            user_id=user_id,
            session_id=session_id,
            importance=outcome_score if outcome == "success" else 0.3,
            tags=["episode", outcome, episode.task_category or "uncategorized"],
            metadata={
                "episode_id": episode_id,
                "action_count": len(actions),
                "duration_seconds": duration_seconds,
            },
        )

        logger.info(
            f"Recorded episode {episode_id} for agent {agent_id}: "
            f"outcome={outcome}, actions={len(actions)}"
        )

        return episode

    async def get_episode(self, episode_id: str) -> Episode | None:
        """Get an episode by ID.

        Args:
            episode_id: Episode identifier

        Returns:
            Episode or None
        """
        return self._episodes.get(episode_id)

    async def get_episodes_for_agent(
        self,
        agent_id: str,
        outcome_filter: str | None = None,
        limit: int = 100,
    ) -> list[Episode]:
        """Get episodes for an agent.

        Args:
            agent_id: Agent identifier
            outcome_filter: Optional outcome filter
            limit: Maximum results

        Returns:
            List of episodes
        """
        episodes = [
            e
            for e in self._episodes.values()
            if e.agent_id == agent_id
            and (outcome_filter is None or e.outcome == outcome_filter)
        ]
        episodes.sort(key=lambda e: e.created_at, reverse=True)
        return episodes[:limit]

    # =========================================================================
    # Pattern Extraction and Learning
    # =========================================================================

    async def extract_patterns(
        self,
        agent_id: str,
        episode_ids: list[str] | None = None,
        min_confidence: float = 0.6,
    ) -> list[LearnedPattern]:
        """Extract patterns from episodes for future use.

        Analyzes successful and failed episodes to identify:
        - Success strategies: What actions lead to success
        - Failure modes: What to avoid
        - User preferences: Personalization patterns
        - Optimization opportunities: Efficiency improvements

        Args:
            agent_id: Agent to extract patterns for
            episode_ids: Specific episodes to analyze (None = all recent)
            min_confidence: Minimum confidence for pattern extraction

        Returns:
            List of newly extracted patterns
        """
        # Get episodes to analyze
        if episode_ids:
            episodes = [
                self._episodes[eid] for eid in episode_ids if eid in self._episodes
            ]
        else:
            episodes = await self.get_episodes_for_agent(agent_id, limit=100)

        if len(episodes) < 3:
            logger.info(f"Not enough episodes for pattern extraction: {len(episodes)}")
            return []

        new_patterns = []

        # Analyze success patterns
        success_episodes = [e for e in episodes if e.outcome == "success"]
        if len(success_episodes) >= 2:
            pattern = await self._extract_success_pattern(agent_id, success_episodes)
            if pattern and pattern.confidence >= min_confidence:
                self._patterns[pattern.pattern_id] = pattern
                new_patterns.append(pattern)

        # Analyze failure patterns
        failure_episodes = [e for e in episodes if e.outcome == "failure"]
        if len(failure_episodes) >= 2:
            pattern = await self._extract_failure_pattern(agent_id, failure_episodes)
            if pattern and pattern.confidence >= min_confidence:
                self._patterns[pattern.pattern_id] = pattern
                new_patterns.append(pattern)

        # Analyze user preference patterns (if user-specific episodes exist)
        user_episodes: dict[str, list[Episode]] = {}
        for ep in episodes:
            if ep.user_id:
                user_episodes.setdefault(ep.user_id, []).append(ep)

        for user_id, user_eps in user_episodes.items():
            if len(user_eps) >= 3:
                pattern = await self._extract_preference_pattern(
                    agent_id, user_id, user_eps
                )
                if pattern and pattern.confidence >= min_confidence:
                    self._patterns[pattern.pattern_id] = pattern
                    new_patterns.append(pattern)

        logger.info(
            f"Extracted {len(new_patterns)} patterns from {len(episodes)} episodes "
            f"for agent {agent_id}"
        )

        return new_patterns

    async def get_applicable_patterns(
        self,
        agent_id: str,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> list[LearnedPattern]:
        """Get patterns applicable to a task.

        Args:
            agent_id: Agent identifier
            task: Task description
            context: Current context

        Returns:
            List of applicable patterns sorted by confidence
        """
        patterns = [p for p in self._patterns.values() if p.agent_id == agent_id]

        # Score patterns by applicability
        scored_patterns = []
        for pattern in patterns:
            score = await self._score_pattern_applicability(pattern, task, context)
            if score > 0.3:
                scored_patterns.append((pattern, score))

        scored_patterns.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored_patterns]

    async def apply_pattern(
        self,
        pattern_id: str,
        success: bool,
    ) -> None:
        """Record pattern application result.

        Args:
            pattern_id: Pattern that was applied
            success: Whether application was successful
        """
        pattern = self._patterns.get(pattern_id)
        if pattern:
            pattern.last_applied_at = datetime.now(timezone.utc)
            # Update success rate with exponential moving average
            alpha = 0.3
            pattern.success_rate = (
                alpha * (1.0 if success else 0.0) + (1 - alpha) * pattern.success_rate
            )

    # =========================================================================
    # Memory Consolidation
    # =========================================================================

    async def consolidate_memories(
        self,
        agent_id: str,
        promote_threshold: float = 0.7,
        forget_threshold: float = 0.2,
    ) -> ConsolidationResult:
        """Transfer important short-term to long-term memory.

        This implements the memory consolidation process:
        1. Evaluate short-term memories for importance
        2. Promote high-importance memories to long-term
        3. Remove (forget) low-relevance memories
        4. Extract patterns from recent episodes

        Args:
            agent_id: Agent to consolidate memories for
            promote_threshold: Relevance threshold for promotion
            forget_threshold: Relevance threshold for forgetting

        Returns:
            ConsolidationResult with statistics
        """
        import time

        start_time = time.time()

        memories_processed = 0
        memories_promoted = 0
        memories_demoted = 0

        # Find short-term memories to evaluate
        short_term_memories = [
            m
            for m in self._memories.values()
            if m.agent_id == agent_id
            and m.memory_type == MemoryType.SHORT_TERM
            and not m.is_expired
        ]

        for memory in short_term_memories:
            memories_processed += 1
            relevance = memory.calculate_relevance()

            if relevance >= promote_threshold:
                # Promote to long-term
                memory.memory_type = MemoryType.LONG_TERM
                memory.expires_at = None  # No expiration
                memories_promoted += 1
                logger.debug(f"Promoted memory {memory.memory_id} to long-term")

        # Find low-relevance long-term memories to forget
        long_term_memories = [
            m
            for m in self._memories.values()
            if m.agent_id == agent_id and m.memory_type == MemoryType.LONG_TERM
        ]

        for memory in long_term_memories:
            relevance = memory.calculate_relevance()

            if relevance < forget_threshold and memory.access_count < 3:
                # Forget (delete) the memory
                del self._memories[memory.memory_id]
                memories_demoted += 1
                logger.debug(f"Forgot memory {memory.memory_id}")

        # Extract patterns from recent episodes
        patterns = await self.extract_patterns(agent_id)

        consolidation_time_ms = (time.time() - start_time) * 1000

        result = ConsolidationResult(
            memories_processed=memories_processed,
            memories_promoted=memories_promoted,
            memories_demoted=memories_demoted,
            patterns_extracted=len(patterns),
            consolidation_time_ms=consolidation_time_ms,
        )

        logger.info(
            f"Consolidation for agent {agent_id}: "
            f"processed={memories_processed}, promoted={memories_promoted}, "
            f"forgotten={memories_demoted}, patterns={len(patterns)}"
        )

        return result

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _generate_embedding(self, text: str) -> list[float] | None:
        """Generate embedding for text using Bedrock Titan.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if unavailable
        """
        if not self.bedrock:
            return None

        try:
            response = await asyncio.to_thread(
                self.bedrock.invoke_model,
                modelId="amazon.titan-embed-text-v2:0",
                body=json.dumps({"inputText": text[:8000]}),
            )
            result = json.loads(response["body"].read())
            embedding = result.get("embedding")
            if embedding is not None and isinstance(embedding, list):
                return cast(list[float], embedding)
            return None
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            return None

    def _cosine_similarity(
        self,
        vec1: list[float],
        vec2: list[float],
    ) -> float:
        """Calculate cosine similarity between vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score (0-1)
        """
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _keyword_similarity(self, query: str, content: str) -> float:
        """Calculate keyword-based similarity.

        Args:
            query: Query text
            content: Content to compare

        Returns:
            Similarity score (0-1)
        """
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        if not query_words:
            return 0.0

        intersection = query_words & content_words
        return len(intersection) / len(query_words)

    async def _analyze_sentiment(self, text: str) -> str:
        """Analyze sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            Sentiment classification
        """
        # Simple rule-based sentiment (replace with LLM in production)
        positive_words = {"good", "great", "excellent", "thanks", "helpful", "perfect"}
        negative_words = {"bad", "wrong", "error", "failed", "poor", "useless"}

        words = set(text.lower().split())

        positive_count = len(words & positive_words)
        negative_count = len(words & negative_words)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"

    async def _categorize_task(self, task: str) -> str:
        """Categorize a task description.

        Args:
            task: Task description

        Returns:
            Task category
        """
        task_lower = task.lower()

        categories = {
            "code_generation": ["write", "create", "generate", "implement", "code"],
            "code_review": ["review", "check", "analyze", "audit"],
            "debugging": ["fix", "debug", "error", "bug", "issue"],
            "documentation": ["document", "explain", "describe"],
            "security": ["security", "vulnerability", "secure", "protect"],
            "testing": ["test", "verify", "validate"],
            "refactoring": ["refactor", "improve", "optimize"],
        }

        for category, keywords in categories.items():
            if any(kw in task_lower for kw in keywords):
                return category

        return "general"

    async def _extract_success_pattern(
        self,
        agent_id: str,
        episodes: list[Episode],
    ) -> LearnedPattern | None:
        """Extract success pattern from successful episodes."""
        if len(episodes) < 2:
            return None

        # Find common action types
        action_counts: dict[str, int] = {}
        for ep in episodes:
            for action in ep.actions_taken:
                action_counts[action.action_type] = (
                    action_counts.get(action.action_type, 0) + 1
                )

        common_actions = [
            a for a, c in action_counts.items() if c >= len(episodes) * 0.5
        ]

        if not common_actions:
            return None

        return LearnedPattern(
            pattern_id=str(uuid.uuid4()),
            agent_id=agent_id,
            pattern_type="success_strategy",
            description=f"Successful episodes commonly use: {', '.join(common_actions)}",
            conditions=[f"task_category in {[e.task_category for e in episodes[:3]]}"],
            recommended_actions=common_actions,
            confidence=min(0.9, len(episodes) / 10),
            supporting_episodes=[e.episode_id for e in episodes[:10]],
        )

    async def _extract_failure_pattern(
        self,
        agent_id: str,
        episodes: list[Episode],
    ) -> LearnedPattern | None:
        """Extract failure pattern from failed episodes."""
        if len(episodes) < 2:
            return None

        # Find common failure conditions
        error_actions = []
        for ep in episodes:
            for action in ep.actions_taken:
                if not action.success:
                    error_actions.append(action.action_type)

        if not error_actions:
            return None

        common_errors = list(set(error_actions))[:3]

        return LearnedPattern(
            pattern_id=str(uuid.uuid4()),
            agent_id=agent_id,
            pattern_type="failure_mode",
            description=f"Failures often involve: {', '.join(common_errors)}",
            conditions=["similar_task_context"],
            recommended_actions=[f"avoid_{e}" for e in common_errors],
            confidence=min(0.8, len(episodes) / 10),
            supporting_episodes=[e.episode_id for e in episodes[:10]],
        )

    async def _extract_preference_pattern(
        self,
        agent_id: str,
        user_id: str,
        episodes: list[Episode],
    ) -> LearnedPattern | None:
        """Extract user preference pattern."""
        if len(episodes) < 3:
            return None

        # Analyze feedback sentiment
        positive_eps = [e for e in episodes if e.feedback_sentiment == "positive"]

        if len(positive_eps) < 2:
            return None

        return LearnedPattern(
            pattern_id=str(uuid.uuid4()),
            agent_id=agent_id,
            pattern_type="preference",
            description=f"User {user_id} preferences based on {len(positive_eps)} positive interactions",
            conditions=[f"user_id == {user_id}"],
            recommended_actions=["apply_user_preferences"],
            confidence=min(0.85, len(positive_eps) / 5),
            supporting_episodes=[e.episode_id for e in positive_eps[:10]],
        )

    async def _score_pattern_applicability(
        self,
        pattern: LearnedPattern,
        task: str,
        context: dict[str, Any] | None,
    ) -> float:
        """Score how applicable a pattern is to current task."""
        score = pattern.confidence * 0.5

        # Check task category match
        task_category = await self._categorize_task(task)
        if any(task_category in c for c in pattern.conditions):
            score += 0.3

        # Success rate bonus
        if pattern.success_rate > 0.5:
            score += pattern.success_rate * 0.2

        return min(1.0, score)

    async def _persist_memory(self, memory: Memory) -> None:
        """Persist memory to DynamoDB and OpenSearch."""
        # DynamoDB persistence would go here

    async def _persist_episode(self, episode: Episode) -> None:
        """Persist episode to DynamoDB."""
        # DynamoDB persistence would go here

    # =========================================================================
    # Metrics
    # =========================================================================

    def get_memory_metrics(self, agent_id: str | None = None) -> dict[str, Any]:
        """Get memory service metrics.

        Args:
            agent_id: Optional agent filter

        Returns:
            Metrics dictionary
        """
        memories: ValuesView[Memory] | list[Memory] = self._memories.values()
        if agent_id:
            memories = [m for m in memories if m.agent_id == agent_id]

        memories_by_type = {}
        for mt in MemoryType:
            memories_by_type[mt.value] = sum(1 for m in memories if m.memory_type == mt)

        return {
            "total_memories": len(list(memories)),
            "memories_by_type": memories_by_type,
            "total_episodes": len(self._episodes),
            "total_patterns": len(self._patterns),
        }
