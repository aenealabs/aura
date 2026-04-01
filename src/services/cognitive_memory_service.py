"""
Cognitive Memory Service for Project Aura
==========================================

Implements neuroscience-inspired memory systems for specialized agents:
- Episodic Memory: Specific problem-solving instances
- Semantic Memory: Guardrails, patterns, abstractions
- Procedural Memory: Workflows and action sequences
- Working Memory: Active context (capacity-limited)

Architecture inspired by:
- Hippocampal memory consolidation
- Prefrontal cortex executive function
- Pattern completion in CA3 region

Target: 85% accuracy with incomplete context
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Protocol
from uuid import uuid4

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================


class MemoryType(Enum):
    """Types of long-term memory"""

    EPISODIC = "episodic"  # Specific experiences
    SEMANTIC = "semantic"  # General knowledge (guardrails, patterns)
    PROCEDURAL = "procedural"  # Action sequences


class SemanticType(Enum):
    """Types of semantic memory"""

    GUARDRAIL = "guardrail"
    PATTERN = "pattern"
    SCHEMA = "schema"
    CONCEPT = "concept"
    ANTI_PATTERN = "anti_pattern"


class Severity(Enum):
    """Severity levels for semantic memories"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OutcomeStatus(Enum):
    """Outcome status for episodes"""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    ESCALATED = "escalated"


class StrategyType(Enum):
    """Problem-solving strategy types"""

    PROCEDURAL_EXECUTION = "procedural_execution"  # High confidence
    SCHEMA_GUIDED = "schema_guided"  # Medium confidence
    ACTIVE_LEARNING = "active_learning"  # Low confidence
    CAUTIOUS_EXPLORATION = "cautious_exploration"  # Default
    HUMAN_GUIDANCE = "human_guidance"  # Escalation


class RecommendedAction(Enum):
    """Actions based on confidence level"""

    PROCEED_AUTONOMOUS = "proceed_autonomous"  # >= 0.85
    PROCEED_WITH_LOGGING = "proceed_with_logging"  # >= 0.70
    REQUEST_REVIEW = "request_review"  # >= 0.50
    ESCALATE_TO_HUMAN = "escalate_to_human"  # < 0.50


class AgentMode(Enum):
    """
    Agent architecture mode for decision making.

    SINGLE: MemoryAgent only - faster, lower cost, suitable for low-risk decisions
    DUAL: MemoryAgent + CriticAgent - more thorough, prevents overconfidence
    AUTO: Automatically select based on task risk level

    Neuroscience analog:
    - SINGLE = System 1 (fast, intuitive)
    - DUAL = System 2 (slow, deliberate)

    Empirical finding: In cold-start scenarios, both modes perform similarly.
    DUAL mode provides value when MemoryAgent may be overconfident (high-stakes).
    """

    SINGLE = "single"  # MemoryAgent only
    DUAL = "dual"  # MemoryAgent + CriticAgent
    AUTO = "auto"  # Select based on risk level


# Working memory capacity (Miller's Law: 7±2)
WORKING_MEMORY_CAPACITY = 7
# Minimum episodes for pattern extraction
MIN_EPISODES_FOR_PATTERN = 3
# Validation accuracy threshold for pattern creation
PATTERN_VALIDATION_THRESHOLD = 0.85
# Episodic memory default TTL (30 days)
EPISODIC_TTL_DAYS = 30


# =============================================================================
# DATA CLASSES - MEMORY STRUCTURES
# =============================================================================


@dataclass
class EpisodicMemory:
    """
    A specific problem-solving episode with full context.
    Neuroscience analog: Hippocampal episodic memory
    """

    episode_id: str
    timestamp: datetime
    domain: str

    # Context snapshot
    task_description: str
    input_context: dict[str, Any]
    codebase_state: dict[str, Any] = field(default_factory=dict)

    # Decision record
    decision: str = ""
    reasoning: str = ""
    confidence_at_decision: float = 0.5

    # Outcome
    outcome: OutcomeStatus = OutcomeStatus.SUCCESS
    outcome_details: str = ""
    error_message: Optional[str] = None

    # Learning signals
    feedback_received: Optional[str] = None
    guardrail_violated: Optional[str] = None
    pattern_discovered: Optional[str] = None

    # Retrieval optimization
    embedding: list[float] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    # Lifecycle
    ttl: Optional[int] = None  # Unix timestamp for auto-deletion
    consolidated: bool = False

    def __post_init__(self) -> None:
        if self.ttl is None:
            # Default TTL: 30 days, extend for failures (learning value)
            days = (
                EPISODIC_TTL_DAYS * 2
                if self.outcome == OutcomeStatus.FAILURE
                else EPISODIC_TTL_DAYS
            )
            self.ttl = int((datetime.now() + timedelta(days=days)).timestamp())


@dataclass
class SemanticMemory:
    """
    Generalized knowledge extracted from episodes.
    Neuroscience analog: Neocortical semantic memory
    """

    memory_id: str
    memory_type: SemanticType
    domain: str
    title: str
    content: str

    # Reliability metrics
    confidence: float = 0.5
    evidence_count: int = 0
    contradiction_count: int = 0
    last_validated: datetime = field(default_factory=datetime.now)

    # Severity for prioritization
    severity: Severity = Severity.MEDIUM

    # Relationships
    related_memories: list[str] = field(default_factory=list)
    derived_from: list[str] = field(default_factory=list)
    supersedes: Optional[str] = None

    # Applicability
    preconditions: list[str] = field(default_factory=list)
    file_patterns: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)

    # Retrieval optimization
    embedding: list[float] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    # Lifecycle
    status: str = "ACTIVE"


@dataclass
class ProceduralStep:
    """A single step in a procedure"""

    step_id: str
    order: int
    action: str
    tool: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = ""
    on_error: str = "ABORT"


@dataclass
class ProceduralMemory:
    """
    A learned sequence of actions for accomplishing a goal.
    Neuroscience analog: Basal ganglia procedural memory
    """

    procedure_id: str
    name: str
    domain: str
    goal_description: str

    # The procedure
    steps: list[ProceduralStep] = field(default_factory=list)
    trigger_conditions: list[str] = field(default_factory=list)

    # Performance metrics
    success_rate: float = 0.0
    execution_count: int = 0
    avg_duration_ms: int = 0
    last_executed: Optional[datetime] = None

    # Learning metadata
    derived_from: list[str] = field(default_factory=list)
    required_guardrails: list[str] = field(default_factory=list)
    version: int = 1


@dataclass
class MemoryItem:
    """Generic wrapper for any memory type in working memory"""

    id: str
    memory_type: MemoryType
    content: Any  # The actual memory object
    relevance_score: float = 0.0
    salience: float = 1.0
    last_accessed: datetime = field(default_factory=datetime.now)


@dataclass
class WorkingMemory:
    """
    Active context during task execution (limited capacity).
    Neuroscience analog: Prefrontal cortex working memory

    Capacity Management:
    - Item count limit (default: WORKING_MEMORY_CAPACITY)
    - Token budget limit (default: 8000 tokens, ~32KB text)
    - Items evicted by salience when either limit reached
    """

    session_id: str
    capacity: int = WORKING_MEMORY_CAPACITY
    token_budget: int = 8000  # Approximate token limit for context window safety

    # Current task
    current_task: Optional[dict[str, Any]] = None

    # Retrieved memories (capacity-limited)
    retrieved_memories: list[MemoryItem] = field(default_factory=list)

    # Active schema
    active_schema: Optional[str] = None

    # Pending actions
    pending_actions: list[dict[str, Any]] = field(default_factory=list)

    # Attention state
    attention_weights: dict[str, float] = field(default_factory=dict)

    # Token tracking
    _current_tokens: int = field(default=0, repr=False)

    def add_item(self, item: MemoryItem) -> bool:
        """Add item, potentially displacing lowest-salience items.

        Checks both item count and token budget limits.
        Returns False if item is too large to fit even in empty memory.
        """
        item_tokens = self._estimate_tokens(item)

        # Check if single item exceeds entire budget
        if item_tokens > self.token_budget:
            logger.warning(
                f"Memory item {item.id} exceeds token budget "
                f"({item_tokens} > {self.token_budget}), rejecting"
            )
            return False

        # Evict items until we have space (respecting both limits)
        while (
            len(self.retrieved_memories) >= self.capacity
            or self._current_tokens + item_tokens > self.token_budget
        ):
            if not self.retrieved_memories:
                break
            self._evict_lowest_salience()

        # Final check after eviction
        if self._current_tokens + item_tokens > self.token_budget:
            logger.warning(
                f"Cannot fit item {item.id} within token budget after eviction"
            )
            return False

        self.retrieved_memories.append(item)
        self._current_tokens += item_tokens
        self._update_attention(item.id)
        return True

    def _estimate_tokens(self, item: MemoryItem) -> int:
        """Estimate token count for a memory item.

        Uses simple heuristic: ~4 characters per token (common for English text).
        Serializes content to string for measurement.
        """
        try:
            content = item.content
            if hasattr(content, "to_dict"):
                content_str = str(content.to_dict())
            elif hasattr(content, "__dict__"):
                content_str = str(content.__dict__)
            else:
                content_str = str(content)

            # Approximate: 4 chars per token + overhead for metadata
            base_tokens = len(content_str) // 4
            metadata_tokens = 20  # ID, type, scores overhead
            return base_tokens + metadata_tokens
        except Exception:
            # Default estimate if serialization fails
            return 100

    def _evict_lowest_salience(self) -> None:
        """Remove the item with lowest salience (decay)."""
        if not self.retrieved_memories:
            return

        # Find item with lowest salience
        min_salience_idx = min(
            range(len(self.retrieved_memories)),
            key=lambda i: self.retrieved_memories[i].salience,
        )

        evicted = self.retrieved_memories.pop(min_salience_idx)
        evicted_tokens = self._estimate_tokens(evicted)
        self._current_tokens = max(0, self._current_tokens - evicted_tokens)
        logger.debug(
            f"Evicted memory {evicted.id} ({evicted_tokens} tokens) due to low salience"
        )

    def _update_attention(self, item_id: str) -> None:
        """Update attention weights when item is accessed."""
        self.attention_weights[item_id] = 1.0

        # Decay other items
        for id in self.attention_weights:
            if id != item_id:
                self.attention_weights[id] *= 0.9  # 10% decay

    def rehearse(self, item_id: str) -> None:
        """Refresh item to prevent decay (attention refresh)."""
        for item in self.retrieved_memories:
            if item.id == item_id:
                item.salience = 1.0
                item.last_accessed = datetime.now()
                self._update_attention(item_id)
                return

    def get_by_id(self, item_id: str) -> Optional[MemoryItem]:
        """Get item by ID and update attention."""
        for item in self.retrieved_memories:
            if item.id == item_id:
                self.rehearse(item_id)
                return item
        return None

    def get_token_usage(self) -> dict[str, int]:
        """Get current token usage statistics."""
        return {
            "current_tokens": self._current_tokens,
            "token_budget": self.token_budget,
            "remaining_tokens": self.token_budget - self._current_tokens,
            "item_count": len(self.retrieved_memories),
            "item_capacity": self.capacity,
        }


# =============================================================================
# RETRIEVAL STRUCTURES
# =============================================================================


@dataclass
class RetrievalCue:
    """Sparse cue for pattern completion retrieval"""

    task_description: str
    domain: Optional[str] = None
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    code_entity: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    embedding: Optional[list[float]] = None
    max_results: int = 5
    memory_types: list[MemoryType] = field(
        default_factory=lambda: [MemoryType.SEMANTIC, MemoryType.PROCEDURAL]
    )
    min_confidence: float = 0.5


@dataclass
class RetrievedMemory:
    """Memory retrieved via pattern completion"""

    memory_id: str
    memory_type: MemoryType
    full_content: Any
    relevant_portions: list[str] = field(default_factory=list)

    # Scores
    keyword_score: float = 0.0
    vector_similarity: float = 0.0
    graph_relevance: float = 0.0
    combined_score: float = 0.0

    # Pattern completion metadata
    completion_confidence: float = 0.0
    completion_method: str = "EXACT_MATCH"

    # Related information
    related_procedures: list[str] = field(default_factory=list)
    related_guardrails: list[str] = field(default_factory=list)


# =============================================================================
# METACOGNITION STRUCTURES
# =============================================================================


@dataclass
class ConfidenceEstimate:
    """Metacognitive confidence assessment"""

    score: float  # Overall confidence 0.0-1.0

    # Component factors
    factors: dict[str, float] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)

    # Uncertainty sources (factors with score < 0.5)
    uncertainties: list[str] = field(default_factory=list)

    # Recommended action
    recommended_action: RecommendedAction = RecommendedAction.REQUEST_REVIEW

    # Confidence interval
    confidence_interval: tuple[float, float] = (0.0, 1.0)


@dataclass
class Strategy:
    """Selected problem-solving strategy"""

    strategy_type: StrategyType
    procedure: Optional[ProceduralMemory] = None
    schema: Optional[dict[str, Any]] = None
    questions: list[str] = field(default_factory=list)
    guardrails: list[str] = field(default_factory=list)
    fallback: Optional[StrategyType] = None
    logging_level: str = "NORMAL"
    checkpoint_frequency: str = "MEDIUM"


# =============================================================================
# STORAGE PROTOCOLS (Dependency Injection)
# =============================================================================


class EpisodicStore(Protocol):
    """Protocol for episodic memory storage"""

    async def put(self, episode: EpisodicMemory) -> None: ...

    async def get(self, episode_id: str) -> Optional[EpisodicMemory]: ...

    async def query_by_domain(
        self, domain: str, since: datetime, limit: int = 100
    ) -> list[EpisodicMemory]: ...

    async def query_unconsolidated(
        self, since: datetime, limit: int = 100
    ) -> list[EpisodicMemory]: ...

    async def mark_consolidated(self, episode_ids: list[str]) -> None: ...

    async def delete(self, episode_id: str) -> None: ...


class SemanticStore(Protocol):
    """Protocol for semantic memory storage"""

    async def put(self, memory: SemanticMemory) -> None: ...

    async def get(self, memory_id: str) -> Optional[SemanticMemory]: ...

    async def query_by_domain(
        self, domain: str, memory_types: list[SemanticType] | None = None
    ) -> list[SemanticMemory]: ...

    async def vector_search(
        self, embedding: list[float], limit: int = 10
    ) -> list[SemanticMemory]: ...

    async def update_confidence(
        self, memory_id: str, delta: float, evidence_ids: list[str]
    ) -> None: ...


class ProceduralStore(Protocol):
    """Protocol for procedural memory storage"""

    async def put(self, procedure: ProceduralMemory) -> None: ...

    async def get(self, procedure_id: str) -> Optional[ProceduralMemory]: ...

    async def query_by_domain(self, domain: str) -> list[ProceduralMemory]: ...

    async def query_by_trigger(self, trigger: str) -> list[ProceduralMemory]: ...

    async def update_metrics(
        self, procedure_id: str, success: bool, duration_ms: int
    ) -> None: ...


class EmbeddingService(Protocol):
    """Protocol for generating embeddings"""

    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


# =============================================================================
# CONFIDENCE ESTIMATOR
# =============================================================================


class ConfidenceEstimator:
    """
    Estimates confidence in decisions based on memory quality and coverage.
    Neuroscience analog: Prefrontal cortex metacognition
    """

    DEFAULT_WEIGHTS = {
        "memory_coverage": 0.25,
        "memory_agreement": 0.25,
        "recency": 0.15,
        "outcome_history": 0.25,
        "schema_match": 0.10,
    }

    def estimate(
        self,
        task: dict[str, Any],
        retrieved_memories: list[RetrievedMemory],
        proposed_action: Optional[str] = None,
    ) -> ConfidenceEstimate:
        """
        Calculate confidence score and identify uncertainty sources.
        """
        factors = {}

        # Factor 1: Memory coverage (do we have relevant experience?)
        factors["memory_coverage"] = self._assess_memory_coverage(
            task, retrieved_memories
        )

        # Factor 2: Memory agreement (do memories agree on approach?)
        factors["memory_agreement"] = self._assess_memory_agreement(retrieved_memories)

        # Factor 3: Recency (how recent are relevant memories?)
        factors["recency"] = self._assess_recency(retrieved_memories)

        # Factor 4: Outcome history (how have similar decisions fared?)
        factors["outcome_history"] = self._assess_outcome_history(
            task, proposed_action, retrieved_memories
        )

        # Factor 5: Schema match (does task match a known schema?)
        factors["schema_match"] = self._assess_schema_match(task, retrieved_memories)

        # Weighted combination
        confidence = sum(factors[k] * self.DEFAULT_WEIGHTS[k] for k in factors)

        # Identify uncertainty sources (factors < 0.5)
        uncertainties = [k for k, v in factors.items() if v < 0.5]

        # Calculate confidence interval
        variance = sum(
            self.DEFAULT_WEIGHTS[k] * (factors[k] - confidence) ** 2 for k in factors
        )
        std_dev = variance**0.5
        ci = (max(0, confidence - 1.96 * std_dev), min(1, confidence + 1.96 * std_dev))

        return ConfidenceEstimate(
            score=confidence,
            factors=factors,
            weights=self.DEFAULT_WEIGHTS,
            uncertainties=uncertainties,
            recommended_action=self._recommend_action(confidence),
            confidence_interval=ci,
        )

    def _assess_memory_coverage(
        self, task: dict[str, Any], memories: list[RetrievedMemory]
    ) -> float:
        """Assess whether we have relevant experience for this task."""
        if not memories:
            return 0.0

        # Check for high-relevance memories
        high_relevance = [m for m in memories if m.combined_score >= 0.7]
        if high_relevance:
            return min(1.0, len(high_relevance) / 3)  # 3+ high-relevance = 1.0

        # Partial coverage
        any_relevance = [m for m in memories if m.combined_score >= 0.4]
        return min(0.6, len(any_relevance) / 5)

    def _assess_memory_agreement(self, memories: list[RetrievedMemory]) -> float:
        """Assess whether retrieved memories agree on approach."""
        if len(memories) < 2:
            return 0.5  # Neutral with insufficient memories

        # Check for contradictions in guardrails
        guardrails = set()
        anti_patterns = set()

        for m in memories:
            if m.memory_type == MemoryType.SEMANTIC:
                content = m.full_content
                if hasattr(content, "memory_type"):
                    if content.memory_type == SemanticType.GUARDRAIL:
                        guardrails.add(content.memory_id)
                    elif content.memory_type == SemanticType.ANTI_PATTERN:
                        anti_patterns.add(content.memory_id)

        # High agreement if no anti-patterns
        if not anti_patterns:
            return 0.9

        # Check for conflicts
        conflicts = guardrails.intersection(anti_patterns)
        if conflicts:
            return 0.3

        return 0.7

    def _assess_recency(self, memories: list[RetrievedMemory]) -> float:
        """Assess how recent the relevant memories are."""
        if not memories:
            return 0.3

        # Calculate average age of memories
        now = datetime.now()
        ages_days = []

        for m in memories:
            content = m.full_content
            if hasattr(content, "last_validated"):
                age = (now - content.last_validated).days
                ages_days.append(age)
            elif hasattr(content, "timestamp"):
                age = (now - content.timestamp).days
                ages_days.append(age)

        if not ages_days:
            return 0.5

        avg_age = sum(ages_days) / len(ages_days)

        # Scoring: very recent (< 7 days) = 1.0, old (> 90 days) = 0.3
        if avg_age < 7:
            return 1.0
        elif avg_age < 30:
            return 0.8
        elif avg_age < 90:
            return 0.6
        else:
            return 0.3

    def _assess_outcome_history(
        self,
        task: dict[str, Any],
        proposed_action: Optional[str],
        memories: list[RetrievedMemory],
    ) -> float:
        """Assess historical success rate for similar decisions."""
        if not memories:
            return 0.5

        # Look for episodic memories with outcomes
        success_count = 0
        total_count = 0

        for m in memories:
            if m.memory_type == MemoryType.EPISODIC:
                content = m.full_content
                if hasattr(content, "outcome"):
                    total_count += 1
                    if content.outcome == OutcomeStatus.SUCCESS:
                        success_count += 1

        if total_count == 0:
            return 0.5

        return success_count / total_count

    def _assess_schema_match(
        self, task: dict[str, Any], memories: list[RetrievedMemory]
    ) -> float:
        """Assess whether the task matches a known schema."""
        # Check for schema-type memories
        for m in memories:
            if m.memory_type == MemoryType.SEMANTIC:
                content = m.full_content
                if hasattr(content, "memory_type"):
                    if content.memory_type == SemanticType.SCHEMA:
                        return min(1.0, m.combined_score + 0.3)

        # Check for procedural matches
        for m in memories:
            if m.memory_type == MemoryType.PROCEDURAL:
                return min(0.8, m.combined_score + 0.2)

        return 0.3

    def _recommend_action(self, confidence: float) -> RecommendedAction:
        """Map confidence score to recommended action."""
        if confidence >= 0.85:
            return RecommendedAction.PROCEED_AUTONOMOUS
        elif confidence >= 0.70:
            return RecommendedAction.PROCEED_WITH_LOGGING
        elif confidence >= 0.50:
            return RecommendedAction.REQUEST_REVIEW
        else:
            return RecommendedAction.ESCALATE_TO_HUMAN


# =============================================================================
# STRATEGY SELECTOR
# =============================================================================


class StrategySelector:
    """
    Selects problem-solving strategy based on task type and resources.
    Neuroscience analog: Prefrontal executive function
    """

    def select_strategy(
        self,
        task: dict[str, Any],
        confidence: ConfidenceEstimate,
        available_procedures: list[ProceduralMemory],
        available_schemas: list[SemanticMemory],
    ) -> Strategy:
        """Select optimal strategy for current task."""

        # High confidence + matching procedure → Execute procedure
        if confidence.score >= 0.85 and available_procedures:
            matching = self._find_matching_procedure(task, available_procedures)
            if matching:
                return Strategy(
                    strategy_type=StrategyType.PROCEDURAL_EXECUTION,
                    procedure=matching,
                    guardrails=self._get_required_guardrails(matching),
                    fallback=StrategyType.SCHEMA_GUIDED,
                    logging_level="MINIMAL",
                    checkpoint_frequency="LOW",
                )

        # Medium confidence → Schema-guided exploration
        if 0.50 <= confidence.score < 0.85:
            schema = self._find_matching_schema(task, available_schemas)
            guardrails = self._get_domain_guardrails(task.get("domain", "GENERAL"))

            return Strategy(
                strategy_type=StrategyType.SCHEMA_GUIDED,
                schema=(
                    {"name": schema.title, "content": schema.content}
                    if schema
                    else None
                ),
                guardrails=guardrails,
                fallback=StrategyType.HUMAN_GUIDANCE,
                logging_level="NORMAL",
                checkpoint_frequency="MEDIUM",
            )

        # Low confidence → Active learning (ask questions)
        if confidence.score < 0.50:
            questions = self._generate_clarifying_questions(task, confidence)
            return Strategy(
                strategy_type=StrategyType.ACTIVE_LEARNING,
                questions=questions,
                fallback=StrategyType.HUMAN_GUIDANCE,
                logging_level="VERBOSE",
                checkpoint_frequency="HIGH",
            )

        # Default: Cautious exploration
        return Strategy(
            strategy_type=StrategyType.CAUTIOUS_EXPLORATION,
            logging_level="VERBOSE",
            checkpoint_frequency="HIGH",
        )

    def _find_matching_procedure(
        self, task: dict[str, Any], procedures: list[ProceduralMemory]
    ) -> Optional[ProceduralMemory]:
        """Find a procedure that matches the task."""
        task_desc = task.get("description", "").lower()

        for proc in sorted(procedures, key=lambda p: p.success_rate, reverse=True):
            for trigger in proc.trigger_conditions:
                if trigger.lower() in task_desc:
                    return proc
        return None

    def _find_matching_schema(
        self, task: dict[str, Any], schemas: list[SemanticMemory]
    ) -> Optional[SemanticMemory]:
        """Find a schema that matches the task domain."""
        domain = task.get("domain", "GENERAL")

        for schema in schemas:
            if schema.domain == domain and schema.memory_type == SemanticType.SCHEMA:
                return schema
        return None

    def _get_required_guardrails(self, procedure: ProceduralMemory) -> list[str]:
        """Get guardrails required by a procedure."""
        return procedure.required_guardrails

    def _get_domain_guardrails(self, domain: str) -> list[str]:
        """Get guardrails for a domain."""
        # This would query the semantic store in practice
        domain_guardrails = {
            "CICD": ["GR-CICD-001", "GR-SEC-001"],
            "IAM": ["GR-IAM-001", "GR-CFN-001"],
            "SECURITY": ["GR-SEC-001", "GR-IAM-001"],
            "CFN": ["GR-CFN-001", "GR-CFN-002"],
        }
        return domain_guardrails.get(domain, [])

    def _generate_clarifying_questions(
        self, task: dict[str, Any], confidence: ConfidenceEstimate
    ) -> list[str]:
        """Generate questions to reduce uncertainty."""
        questions = []

        for uncertainty in confidence.uncertainties:
            if uncertainty == "memory_coverage":
                questions.append(
                    "I don't have much experience with this type of task. "
                    "Can you provide an example or reference implementation?"
                )
            elif uncertainty == "memory_agreement":
                questions.append(
                    "I found conflicting guidance. Which approach should take priority?"
                )
            elif uncertainty == "schema_match":
                questions.append(
                    "This task doesn't match my known patterns. "
                    "Is there a standard approach I should follow?"
                )

        return questions[:3]  # Limit to 3 questions


# =============================================================================
# PATTERN COMPLETION RETRIEVER
# =============================================================================


class PatternCompletionRetriever:
    """
    Retrieves relevant memories from sparse cues.
    Neuroscience analog: Hippocampal CA3 pattern completion
    """

    def __init__(
        self,
        episodic_store: EpisodicStore,
        semantic_store: SemanticStore,
        procedural_store: ProceduralStore,
        embedding_service: EmbeddingService,
    ):
        self.episodic_store = episodic_store
        self.semantic_store = semantic_store
        self.procedural_store = procedural_store
        self.embedding_service = embedding_service

    async def retrieve(
        self, cue: RetrievalCue, working_memory: WorkingMemory
    ) -> list[RetrievedMemory]:
        """
        Given a sparse cue, retrieve and reconstruct relevant memories.

        Implements multi-stage retrieval:
        1. Keyword filtering (fast, coarse)
        2. Vector similarity (semantic matching)
        3. Graph expansion (structural relationships)
        4. Pattern completion (reconstruct full context)

        Error Handling:
        - Each stage is wrapped in try-except for graceful degradation
        - Partial results are returned if later stages fail
        - Individual memory completion failures don't stop the pipeline
        """
        candidates: list[RetrievedMemory] = []

        # Stage 1: Keyword filtering
        try:
            keyword_candidates = await self._keyword_filter(cue)
            candidates.extend(keyword_candidates)
        except Exception as e:
            logger.warning(f"Keyword filter failed, continuing with other methods: {e}")

        # Stage 2: Vector similarity
        if cue.embedding or cue.task_description:
            try:
                embedding = cue.embedding
                if not embedding:
                    embedding = await self.embedding_service.embed(cue.task_description)

                vector_candidates = await self._vector_search(embedding, cue)
                candidates.extend(vector_candidates)
            except Exception as e:
                logger.warning(
                    f"Vector search failed, continuing with available candidates: {e}"
                )

        # If no candidates from any method, return empty
        if not candidates:
            logger.info("No candidates found from any retrieval method")
            return []

        # Stage 3: Deduplicate and merge scores
        candidates = self._merge_candidates(candidates)

        # Stage 4: Graph expansion (get related memories)
        try:
            expanded = await self._graph_expand(candidates, working_memory)
        except Exception as e:
            logger.warning(f"Graph expansion failed, using unexpanded candidates: {e}")
            expanded = candidates

        # Stage 5: Pattern completion
        completed = []
        for memory in expanded[: cue.max_results]:
            try:
                full = await self._complete_pattern(memory, cue)
                if full.completion_confidence >= cue.min_confidence:
                    completed.append(full)
            except Exception as e:
                logger.warning(
                    f"Pattern completion failed for memory {memory.memory_id}: {e}"
                )
                # Include the memory with lower confidence if completion fails
                memory.completion_confidence = max(0.0, cue.min_confidence - 0.1)
                completed.append(memory)

        # Stage 6: Final ranking
        return self._final_rank(completed, working_memory)

    async def _keyword_filter(self, cue: RetrievalCue) -> list[RetrievedMemory]:
        """Fast keyword-based filtering."""
        results = []

        if cue.domain:
            # Query semantic memories by domain
            semantics = await self.semantic_store.query_by_domain(cue.domain)
            for mem in semantics:
                # Score by keyword overlap
                keyword_overlap = len(set(cue.keywords) & set(mem.keywords))
                score = min(1.0, keyword_overlap / max(1, len(cue.keywords)))

                if score > 0.1:  # Threshold
                    results.append(
                        RetrievedMemory(
                            memory_id=mem.memory_id,
                            memory_type=MemoryType.SEMANTIC,
                            full_content=mem,
                            keyword_score=score,
                            combined_score=score,
                        )
                    )

        return results

    async def _vector_search(
        self, embedding: list[float], cue: RetrievalCue
    ) -> list[RetrievedMemory]:
        """Vector similarity search."""
        results = []

        semantics = await self.semantic_store.vector_search(embedding, limit=20)
        for mem in semantics:
            # Calculate cosine similarity (simplified)
            similarity = self._cosine_similarity(embedding, mem.embedding)

            results.append(
                RetrievedMemory(
                    memory_id=mem.memory_id,
                    memory_type=MemoryType.SEMANTIC,
                    full_content=mem,
                    vector_similarity=similarity,
                    combined_score=similarity,
                )
            )

        return results

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def _merge_candidates(
        self, candidates: list[RetrievedMemory]
    ) -> list[RetrievedMemory]:
        """Merge and deduplicate candidates, combining scores."""
        merged: dict[str, RetrievedMemory] = {}

        for c in candidates:
            if c.memory_id in merged:
                # Combine scores
                existing = merged[c.memory_id]
                existing.keyword_score = max(existing.keyword_score, c.keyword_score)
                existing.vector_similarity = max(
                    existing.vector_similarity, c.vector_similarity
                )
                existing.combined_score = (
                    0.4 * existing.keyword_score + 0.6 * existing.vector_similarity
                )
            else:
                merged[c.memory_id] = c

        return sorted(merged.values(), key=lambda x: x.combined_score, reverse=True)

    async def _graph_expand(
        self, candidates: list[RetrievedMemory], working_memory: WorkingMemory
    ) -> list[RetrievedMemory]:
        """Expand candidates with graph-related memories."""
        expanded = list(candidates)
        seen_ids = {c.memory_id for c in candidates}

        for c in candidates[:5]:  # Expand top 5
            if c.memory_type == MemoryType.SEMANTIC and c.full_content:
                content = c.full_content
                if hasattr(content, "related_memories"):
                    for related_id in content.related_memories:
                        if related_id not in seen_ids:
                            related = await self.semantic_store.get(related_id)
                            if related:
                                expanded.append(
                                    RetrievedMemory(
                                        memory_id=related_id,
                                        memory_type=MemoryType.SEMANTIC,
                                        full_content=related,
                                        graph_relevance=0.5,  # Reduced score for expanded
                                        combined_score=c.combined_score * 0.7,
                                    )
                                )
                                seen_ids.add(related_id)

        return expanded

    async def _complete_pattern(
        self, memory: RetrievedMemory, cue: RetrievalCue
    ) -> RetrievedMemory:
        """
        Complete the pattern - reconstruct full context from partial match.
        Neuroscience analog: CA3 pattern completion
        """
        # Extract relevant portions based on cue
        relevant_portions = []

        content = memory.full_content
        if hasattr(content, "content"):
            # Extract sentences/sections containing keywords
            content_str = content.content
            for keyword in cue.keywords:
                if keyword.lower() in content_str.lower():
                    # Find surrounding context
                    idx = content_str.lower().find(keyword.lower())
                    start = max(0, idx - 100)
                    end = min(len(content_str), idx + 100)
                    relevant_portions.append(content_str[start:end])

        # Calculate completion confidence
        if hasattr(content, "confidence"):
            base_confidence = content.confidence
        else:
            base_confidence = 0.5

        completion_confidence = min(
            1.0, base_confidence * (1 + memory.combined_score) / 2
        )

        memory.relevant_portions = relevant_portions[:3]
        memory.completion_confidence = completion_confidence
        memory.completion_method = (
            "EXACT_MATCH" if memory.combined_score > 0.8 else "PARTIAL_MATCH"
        )

        return memory

    def _final_rank(
        self, memories: list[RetrievedMemory], working_memory: WorkingMemory
    ) -> list[RetrievedMemory]:
        """Final ranking considering working memory context."""
        # Boost memories related to current task
        for m in memories:
            if working_memory.current_task:
                task_domain = working_memory.current_task.get("domain")
                if (
                    hasattr(m.full_content, "domain")
                    and m.full_content.domain == task_domain
                ):
                    m.combined_score *= 1.2  # 20% boost for same domain

        return sorted(memories, key=lambda x: x.combined_score, reverse=True)


# =============================================================================
# CONSOLIDATION PIPELINE
# =============================================================================


class ConsolidationPipeline:
    """
    Background process that consolidates episodic memories into semantic knowledge.
    Neuroscience analog: Hippocampal replay during sleep
    """

    def __init__(
        self,
        episodic_store: EpisodicStore,
        semantic_store: SemanticStore,
        embedding_service: EmbeddingService,
    ):
        self.episodic_store = episodic_store
        self.semantic_store = semantic_store
        self.embedding_service = embedding_service

    async def consolidate(
        self, time_window: timedelta = timedelta(hours=24)  # noqa: B008
    ) -> dict[str, Any]:
        """
        Main consolidation loop.
        Returns summary of consolidation actions.

        Error Handling:
        - Each phase is wrapped in try-except for graceful degradation
        - Partial results are returned on failure
        - Episodes are only marked consolidated after successful pattern extraction
        """
        summary = {
            "episodes_processed": 0,
            "patterns_extracted": 0,
            "memories_created": 0,
            "memories_strengthened": 0,
            "episodes_pruned": 0,
            "errors": [],
        }

        # Create typed variables for accessing dict fields
        episodes_processed: int = 0
        patterns_extracted: int = 0
        memories_created: int = 0
        memories_strengthened: int = 0
        episodes_pruned: int = 0
        errors: list[str] = []

        # Phase 1: Retrieve recent unconsolidated episodes
        since = datetime.now() - time_window
        try:
            episodes = await self.episodic_store.query_unconsolidated(since, limit=100)
            episodes_processed = len(episodes)
            summary["episodes_processed"] = episodes_processed
        except Exception as e:
            error_msg = f"Failed to query unconsolidated episodes: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            summary["errors"] = errors
            return summary

        if len(episodes) < MIN_EPISODES_FOR_PATTERN:
            logger.info(
                f"Insufficient episodes ({len(episodes)}) for pattern extraction"
            )
            return summary

        # Phase 2: Cluster episodes by similarity
        clusters = self._cluster_episodes(episodes)

        # Phase 3: Extract patterns from each cluster
        successfully_processed_ids: list[str] = []
        for cluster in clusters:
            try:
                pattern = await self._extract_pattern(cluster)

                if (
                    pattern
                    and pattern["validation_score"] >= PATTERN_VALIDATION_THRESHOLD
                ):
                    patterns_extracted += 1

                    # Check if pattern updates existing memory
                    try:
                        existing = await self._find_similar_semantic(pattern)
                    except Exception as e:
                        logger.warning(f"Failed to find similar semantic: {e}")
                        existing = None

                    if existing:
                        # Strengthen existing
                        try:
                            await self._strengthen_semantic(existing, pattern)
                            memories_strengthened += 1
                        except Exception as e:
                            error_msg = f"Failed to strengthen semantic memory: {e}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                    else:
                        # Create new
                        try:
                            await self._create_semantic_memory(pattern)
                            memories_created += 1
                        except Exception as e:
                            error_msg = f"Failed to create semantic memory: {e}"
                            logger.error(error_msg)
                            errors.append(error_msg)

                    # Track successfully processed episode IDs
                    successfully_processed_ids.extend([e.episode_id for e in cluster])
            except Exception as e:
                error_msg = f"Failed to extract pattern from cluster: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                # Continue with next cluster

        # Phase 4: Mark only successfully processed episodes as consolidated
        if successfully_processed_ids:
            try:
                await self.episodic_store.mark_consolidated(successfully_processed_ids)
            except Exception as e:
                error_msg = f"Failed to mark episodes as consolidated: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Phase 5: Prune old, low-value episodes
        try:
            pruned = await self._prune_episodes()
            episodes_pruned = pruned
        except Exception as e:
            error_msg = f"Failed to prune episodes: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        # Update summary with typed variables
        summary["patterns_extracted"] = patterns_extracted
        summary["memories_created"] = memories_created
        summary["memories_strengthened"] = memories_strengthened
        summary["episodes_pruned"] = episodes_pruned
        summary["errors"] = errors

        if errors:
            logger.warning(
                f"Consolidation completed with {len(errors)} errors: {summary}"
            )
        else:
            logger.info(f"Consolidation complete: {summary}")
        return summary

    def _cluster_episodes(
        self, episodes: list[EpisodicMemory]
    ) -> list[list[EpisodicMemory]]:
        """Cluster episodes by domain and outcome similarity."""
        clusters: dict[str, list[EpisodicMemory]] = {}

        for episode in episodes:
            # Simple clustering by domain + outcome
            key = f"{episode.domain}_{episode.outcome.value}"
            if key not in clusters:
                clusters[key] = []
            clusters[key].append(episode)

        # Filter clusters with minimum size
        return [c for c in clusters.values() if len(c) >= MIN_EPISODES_FOR_PATTERN]

    async def _extract_pattern(
        self, cluster: list[EpisodicMemory]
    ) -> Optional[dict[str, Any]]:
        """Extract generalizable pattern from episode cluster."""
        if len(cluster) < MIN_EPISODES_FOR_PATTERN:
            return None

        # Find common elements across episodes
        common_keywords = self._find_common_keywords(cluster)
        common_decision_elements = self._find_common_decisions(cluster)
        outcome = cluster[0].outcome  # All in cluster have same outcome

        # Validate on held-out episodes
        _train = cluster[:-2]  # noqa: F841
        test = cluster[-2:]
        validation_score = self._validate_pattern(
            common_decision_elements, test, outcome
        )

        return {
            "domain": cluster[0].domain,
            "keywords": common_keywords,
            "decision_pattern": common_decision_elements,
            "outcome": outcome,
            "evidence_count": len(cluster),
            "source_episodes": [e.episode_id for e in cluster],
            "validation_score": validation_score,
        }

    def _find_common_keywords(self, cluster: list[EpisodicMemory]) -> list[str]:
        """Find keywords common to all episodes in cluster."""
        if not cluster:
            return []

        common = set(cluster[0].keywords)
        for episode in cluster[1:]:
            common &= set(episode.keywords)

        return list(common)

    def _find_common_decisions(self, cluster: list[EpisodicMemory]) -> str:
        """Extract common decision pattern from cluster."""
        # Simplified: look for common substrings in decisions
        decisions = [e.decision for e in cluster if e.decision]
        if not decisions:
            return ""

        # Return the most common decision (simplified)
        from collections import Counter

        decision_counts = Counter(decisions)
        return decision_counts.most_common(1)[0][0] if decision_counts else ""

    def _validate_pattern(
        self,
        pattern: str,
        test_episodes: list[EpisodicMemory],
        expected_outcome: OutcomeStatus,
    ) -> float:
        """Validate pattern against held-out episodes."""
        if not test_episodes or not pattern:
            return 0.0

        correct = 0
        for episode in test_episodes:
            # Check if pattern would have predicted the outcome
            if pattern.lower() in episode.decision.lower():
                if episode.outcome == expected_outcome:
                    correct += 1

        return correct / len(test_episodes)

    async def _find_similar_semantic(
        self, pattern: dict[str, Any]
    ) -> Optional[SemanticMemory]:
        """Find existing semantic memory similar to pattern."""
        # Create embedding for pattern
        pattern_text = f"{pattern['domain']} {pattern['decision_pattern']} {' '.join(pattern['keywords'])}"
        embedding = await self.embedding_service.embed(pattern_text)

        # Search for similar
        results = await self.semantic_store.vector_search(embedding, limit=5)

        for result in results:
            # Check if sufficiently similar
            similarity = self._calculate_similarity(pattern, result)
            if similarity > 0.8:
                return result

        return None

    def _calculate_similarity(
        self, pattern: dict[str, Any], memory: SemanticMemory
    ) -> float:
        """Calculate similarity between pattern and existing memory."""
        # Simple keyword overlap
        pattern_keywords = set(pattern.get("keywords", []))
        memory_keywords = set(memory.keywords)

        if not pattern_keywords or not memory_keywords:
            return 0.0

        overlap = len(pattern_keywords & memory_keywords)
        union = len(pattern_keywords | memory_keywords)

        return overlap / union if union > 0 else 0.0

    async def _strengthen_semantic(
        self, existing: SemanticMemory, pattern: dict[str, Any]
    ) -> None:
        """Strengthen existing semantic memory with new evidence."""
        await self.semantic_store.update_confidence(
            existing.memory_id,
            delta=0.05,  # Small confidence boost
            evidence_ids=pattern.get("source_episodes", []),
        )

    async def _create_semantic_memory(self, pattern: dict[str, Any]) -> None:
        """Create new semantic memory from pattern.

        Content Limits:
        - Keywords: Max 20 keywords, each truncated to 50 chars
        - Decision pattern: Max 2000 chars
        - Total content: Max 4000 chars (safe for embedding models)
        """
        # Content size limits
        MAX_KEYWORDS = 20
        MAX_KEYWORD_LENGTH = 50
        MAX_PATTERN_LENGTH = 2000
        MAX_CONTENT_LENGTH = 4000

        # Determine memory type based on outcome
        decision_pattern = pattern.get("decision_pattern", "")[:MAX_PATTERN_LENGTH]
        if pattern["outcome"] == OutcomeStatus.FAILURE:
            memory_type = SemanticType.ANTI_PATTERN
            title = f"Anti-pattern: {decision_pattern[:50]}"
        else:
            memory_type = SemanticType.PATTERN
            title = f"Pattern: {decision_pattern[:50]}"

        # Truncate keywords list and individual keywords
        keywords = pattern.get("keywords", [])[:MAX_KEYWORDS]
        keywords_truncated = [kw[:MAX_KEYWORD_LENGTH] for kw in keywords]
        keywords_str = ", ".join(keywords_truncated)
        if len(pattern.get("keywords", [])) > MAX_KEYWORDS:
            keywords_str += f" (+{len(pattern['keywords']) - MAX_KEYWORDS} more)"

        # Truncate decision pattern with indicator
        if len(pattern.get("decision_pattern", "")) > MAX_PATTERN_LENGTH:
            decision_pattern = decision_pattern + "... [truncated]"

        content = f"""
## Context
Domain: {pattern.get('domain', 'unknown')}
Keywords: {keywords_str}

## Pattern
{decision_pattern}

## Outcome
{pattern['outcome'].value}

## Evidence
Extracted from {pattern.get('evidence_count', 0)} episodes.
Validation score: {pattern.get('validation_score', 0.0):.2f}
"""

        # Final content length check
        if len(content) > MAX_CONTENT_LENGTH:
            content = content[: MAX_CONTENT_LENGTH - 20] + "\n... [truncated]"
            logger.warning(
                f"Semantic memory content truncated from {len(content)} to {MAX_CONTENT_LENGTH} chars"
            )

        embedding = await self.embedding_service.embed(content)

        memory = SemanticMemory(
            memory_id=f"sem-{uuid4().hex[:8]}",
            memory_type=memory_type,
            domain=pattern["domain"],
            title=title,
            content=content,
            confidence=pattern["validation_score"],
            evidence_count=pattern["evidence_count"],
            derived_from=pattern.get("source_episodes", []),
            keywords=pattern.get("keywords", []),
            embedding=embedding,
            severity=Severity.MEDIUM,
        )

        await self.semantic_store.put(memory)

    async def _prune_episodes(self) -> int:
        """Prune old, low-value episodic memories."""
        # Implementation would query for old, consolidated, successful episodes
        # and delete them. Keep failures longer for learning.
        # Simplified: return 0 for now
        return 0


# =============================================================================
# COGNITIVE MEMORY SERVICE (Main Interface)
# =============================================================================


class CognitiveMemoryService:
    """
    Main service interface for cognitive memory operations.
    Coordinates retrieval, metacognition, and consolidation.
    """

    def __init__(
        self,
        episodic_store: EpisodicStore,
        semantic_store: SemanticStore,
        procedural_store: ProceduralStore,
        embedding_service: EmbeddingService,
    ):
        self.episodic_store = episodic_store
        self.semantic_store = semantic_store
        self.procedural_store = procedural_store
        self.embedding_service = embedding_service

        self.retriever = PatternCompletionRetriever(
            episodic_store, semantic_store, procedural_store, embedding_service
        )
        self.confidence_estimator = ConfidenceEstimator()
        self.strategy_selector = StrategySelector()
        self.consolidation_pipeline = ConsolidationPipeline(
            episodic_store, semantic_store, embedding_service
        )

    async def load_cognitive_context(
        self, task_description: str, domain: str, session_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Load cognitive context for a task.
        Returns retrieved memories, confidence estimate, and strategy.
        """
        # Initialize working memory
        working_memory = WorkingMemory(
            session_id=session_id or str(uuid4()),
            current_task={"description": task_description, "domain": domain},
        )

        # Create retrieval cue
        keywords = self._extract_keywords(task_description)
        embedding = await self.embedding_service.embed(task_description)

        cue = RetrievalCue(
            task_description=task_description,
            domain=domain,
            keywords=keywords,
            embedding=embedding,
        )

        # Retrieve memories
        retrieved = await self.retriever.retrieve(cue, working_memory)

        # Populate working memory
        for mem in retrieved[:WORKING_MEMORY_CAPACITY]:
            working_memory.add_item(
                MemoryItem(
                    id=mem.memory_id,
                    memory_type=mem.memory_type,
                    content=mem.full_content,
                    relevance_score=mem.combined_score,
                )
            )

        # Estimate confidence
        confidence = self.confidence_estimator.estimate(
            task={"description": task_description, "domain": domain},
            retrieved_memories=retrieved,
        )

        # Get available procedures and schemas
        procedures = await self.procedural_store.query_by_domain(domain)
        schemas = await self.semantic_store.query_by_domain(
            domain, memory_types=[SemanticType.SCHEMA]
        )

        # Select strategy
        strategy = self.strategy_selector.select_strategy(
            task={"description": task_description, "domain": domain},
            confidence=confidence,
            available_procedures=procedures,
            available_schemas=schemas,
        )

        return {
            "working_memory": working_memory,
            "retrieved_memories": retrieved,
            "confidence": confidence,
            "strategy": strategy,
            "guardrails": self._get_guardrails_from_memories(retrieved),
        }

    async def record_episode(
        self,
        task_description: str,
        domain: str,
        decision: str,
        reasoning: str,
        outcome: OutcomeStatus,
        outcome_details: str,
        confidence_at_decision: float,
        error_message: Optional[str] = None,
        guardrail_violated: Optional[str] = None,
    ) -> EpisodicMemory:
        """Record an episode for future learning."""
        keywords = self._extract_keywords(task_description + " " + decision)
        embedding = await self.embedding_service.embed(task_description)

        episode = EpisodicMemory(
            episode_id=f"ep-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}",
            timestamp=datetime.now(),
            domain=domain,
            task_description=task_description,
            input_context={},
            decision=decision,
            reasoning=reasoning,
            confidence_at_decision=confidence_at_decision,
            outcome=outcome,
            outcome_details=outcome_details,
            error_message=error_message,
            guardrail_violated=guardrail_violated,
            keywords=keywords,
            embedding=embedding,
        )

        await self.episodic_store.put(episode)
        return episode

    async def run_consolidation(self) -> dict[str, Any]:
        """Trigger consolidation pipeline."""
        return await self.consolidation_pipeline.consolidate()

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text (simplified)."""
        # Remove common words and extract significant terms
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "and",
            "but",
            "if",
            "or",
            "because",
            "until",
            "while",
            "this",
            "that",
            "these",
            "those",
        }

        words = text.lower().split()
        keywords = [
            w.strip(".,!?;:\"'()[]{}")
            for w in words
            if w.lower() not in stopwords and len(w) > 2
        ]

        # Return unique keywords
        return list(set(keywords))[:20]

    def _get_guardrails_from_memories(
        self, memories: list[RetrievedMemory]
    ) -> list[dict[str, Any]]:
        """Extract guardrails from retrieved memories."""
        guardrails = []

        for mem in memories:
            if mem.memory_type == MemoryType.SEMANTIC:
                content = mem.full_content
                if hasattr(content, "memory_type"):
                    if content.memory_type == SemanticType.GUARDRAIL:
                        guardrails.append(
                            {
                                "id": content.memory_id,
                                "title": content.title,
                                "severity": content.severity.value,
                                "content": content.content,
                            }
                        )

        return guardrails


# =============================================================================
# ACCURACY MONITORING
# =============================================================================


# =============================================================================
# CRITIC AGENT - No Institutional Memory
# =============================================================================


class CriticChallenge(Enum):
    """Types of challenges the critic can raise."""

    INSUFFICIENT_CONTEXT = "insufficient_context"
    DOMAIN_MISMATCH = "domain_mismatch"
    LOGICAL_INCONSISTENCY = "logical_inconsistency"
    MISSING_INFORMATION = "missing_information"
    OVERCONFIDENT_LEAP = "overconfident_leap"
    PATTERN_MISMATCH = "pattern_mismatch"
    UNEXPLAINED_REASONING = "unexplained_reasoning"


@dataclass
class CriticEvaluation:
    """Result of critic's evaluation of a decision."""

    challenges: list[tuple[CriticChallenge, str, float]]  # (type, reason, severity)
    overall_challenge_score: float  # 0.0 = no issues, 1.0 = major issues
    confidence_adjustment: float  # Multiplier to reduce confidence
    questions: list[str]  # Questions the critic would ask
    should_escalate: bool  # Whether to force human review


class CriticAgent:
    """
    A 'naive' agent without institutional memory that challenges decisions.

    Neuroscience analog: Prefrontal cortex conflict monitoring
    - The anterior cingulate cortex (ACC) detects conflicts between responses
    - It triggers increased cognitive control when uncertainty is detected
    - Acts as an 'error detection' system

    Key principle: The critic has NO access to institutional memory.
    This prevents it from sharing the same biases as the memory agent.
    """

    def __init__(self) -> None:
        # Critic has NO memory stores - this is intentional
        self.challenge_thresholds = {
            "min_context_for_high_confidence": 3,  # Need at least 3 memories
            "min_high_relevance_memories": 2,  # Need at least 2 high-relevance memories
            "min_domain_match_ratio": 0.5,  # 50% of memories should match domain
            "max_confidence_without_procedure": 0.70,  # Can't be confident without procedure
            "max_confidence_without_guardrails": 0.65,  # Can't be confident without guardrails
            "high_relevance_threshold": 0.7,  # Score needed to count as highly relevant
            "moderate_confidence_threshold": 0.70,  # When to start challenging
        }

    def evaluate_decision(
        self,
        task: dict[str, Any],
        proposed_decision: str,
        memory_agent_confidence: float,
        retrieved_memories: list["RetrievedMemory"],
        strategy: "Strategy",
    ) -> CriticEvaluation:
        """
        Evaluate a decision made by the memory agent.

        The critic asks: "What would a smart person without this context think?"
        """
        challenges: list[tuple[CriticChallenge, str, float]] = []
        questions: list[str] = []

        # Challenge 1: Is the context sufficient for this confidence?
        context_challenge = self._challenge_context_sufficiency(
            task, retrieved_memories, memory_agent_confidence
        )
        if context_challenge:
            challenges.append(context_challenge)
            questions.append(
                "What specific prior experience justifies this confidence level?"
            )

        # Challenge 2: Do the retrieved memories match the domain?
        domain_challenge = self._challenge_domain_relevance(task, retrieved_memories)
        if domain_challenge:
            challenges.append(domain_challenge)
            questions.append(
                "Are the retrieved examples actually relevant to this specific problem?"
            )

        # Challenge 3: Is there a logical leap being made?
        leap_challenge = self._challenge_logical_leaps(
            task, proposed_decision, retrieved_memories
        )
        if leap_challenge:
            challenges.append(leap_challenge)
            questions.append(
                "How does the proposed solution follow from the available information?"
            )

        # Challenge 4: Is critical information missing?
        missing_challenge = self._challenge_missing_information(task, proposed_decision)
        if missing_challenge:
            challenges.append(missing_challenge)
            questions.append(
                "What additional information would be needed to be certain?"
            )

        # Challenge 5: Is the strategy appropriate for the uncertainty?
        strategy_challenge = self._challenge_strategy_appropriateness(
            strategy, memory_agent_confidence, len(challenges)
        )
        if strategy_challenge:
            challenges.append(strategy_challenge)
            questions.append("Given the uncertainties, is this the right approach?")

        # Challenge 6: Are retrieval scores actually strong?
        retrieval_challenge = self._challenge_retrieval_quality(
            retrieved_memories, memory_agent_confidence
        )
        if retrieval_challenge:
            challenges.append(retrieval_challenge)
            questions.append(
                "Are the retrieved memories actually relevant to this specific task?"
            )

        # Challenge 7: Complexity detection - scale skepticism with task complexity
        complexity_challenge = self._challenge_task_complexity(
            task, memory_agent_confidence
        )
        if complexity_challenge:
            challenges.append(complexity_challenge)
            questions.append(
                "This task appears complex - has all the complexity been addressed?"
            )

        # Challenge 8: Baseline skepticism - always apply some doubt
        # This is the "naive outsider" perspective
        baseline_challenge = self._apply_baseline_skepticism(
            task, memory_agent_confidence, len(challenges)
        )
        if baseline_challenge:
            challenges.append(baseline_challenge)
            questions.append(
                "Has enough evidence been gathered to justify this confidence?"
            )

        # Calculate overall challenge score
        if challenges:
            # Weight challenges by severity
            total_severity = sum(c[2] for c in challenges)
            # More aggressive normalization: cap at 2 challenges worth
            # This means even 1 moderate challenge (0.5 severity) = 0.25 score
            overall_challenge_score = min(1.0, total_severity / 2.0)
        else:
            overall_challenge_score = 0.0

        # Calculate confidence adjustment
        # Formula: confidence_adjustment = 1 - (challenge_score * adjustment_factor)
        # Aggressive: up to 60% reduction for high challenge scores
        confidence_adjustment = 1.0 - (
            overall_challenge_score * 0.6
        )  # Max 60% reduction

        # Determine if escalation is needed
        should_escalate = overall_challenge_score >= 0.6 or any(
            c[0] == CriticChallenge.LOGICAL_INCONSISTENCY for c in challenges
        )

        return CriticEvaluation(
            challenges=challenges,
            overall_challenge_score=overall_challenge_score,
            confidence_adjustment=confidence_adjustment,
            questions=questions,
            should_escalate=should_escalate,
        )

    def _challenge_context_sufficiency(
        self,
        task: dict[str, Any],
        memories: list["RetrievedMemory"],
        confidence: float,
    ) -> Optional[tuple[CriticChallenge, str, float]]:
        """
        Challenge: Does the available context justify the confidence?
        More aggressive challenging at moderate confidence levels.
        """
        memory_count = len(memories)
        min_required = self.challenge_thresholds["min_context_for_high_confidence"]
        high_rel_threshold = self.challenge_thresholds["high_relevance_threshold"]
        moderate_conf = self.challenge_thresholds["moderate_confidence_threshold"]

        # Count high-relevance memories
        high_relevance = [m for m in memories if m.combined_score >= high_rel_threshold]
        high_rel_count = len(high_relevance)

        # Moderate confidence (>=0.70) with few memories = overconfident
        if confidence >= moderate_conf and memory_count < min_required:
            severity = 0.6 + (confidence - moderate_conf) * 2  # Scale severity
            return (
                CriticChallenge.INSUFFICIENT_CONTEXT,
                f"Confidence ({confidence:.0%}) with only {memory_count} supporting memories",
                min(1.0, severity),
            )

        # Any confidence >=0.70 with no high-relevance memories = overconfident
        if confidence >= moderate_conf and high_rel_count == 0:
            severity = 0.7 + (confidence - moderate_conf)
            return (
                CriticChallenge.OVERCONFIDENT_LEAP,
                f"Confidence ({confidence:.0%}) but no highly relevant memories (all scores < {high_rel_threshold})",
                min(1.0, severity),
            )

        # Confidence >=0.75 with only 1 high-relevance memory = questionable
        if confidence >= 0.75 and high_rel_count < 2:
            return (
                CriticChallenge.INSUFFICIENT_CONTEXT,
                f"Confidence ({confidence:.0%}) with only {high_rel_count} highly relevant memory",
                0.5,
            )

        return None

    def _challenge_domain_relevance(
        self,
        task: dict[str, Any],
        memories: list["RetrievedMemory"],
    ) -> Optional[tuple[CriticChallenge, str, float]]:
        """
        Challenge: Do the retrieved memories actually match the task domain?
        """
        task_domain = task.get("domain", "UNKNOWN")

        # Known domains in our institutional memory
        known_domains = {"CICD", "CFN", "IAM", "SECURITY", "KUBERNETES"}

        # Unknown domain is always a challenge
        if task_domain == "UNKNOWN":
            return (
                CriticChallenge.DOMAIN_MISMATCH,
                "Task domain is unknown - cannot verify memory relevance",
                0.6,
            )

        # Domain outside our known expertise
        if task_domain not in known_domains:
            return (
                CriticChallenge.DOMAIN_MISMATCH,
                f"Domain '{task_domain}' is outside our institutional knowledge base",
                0.7,
            )

        # No memories = nothing to match, but not necessarily a domain issue
        if not memories:
            return None

        # Check domain match ratio
        matching: float = 0.0
        for mem in memories:
            content = mem.full_content
            if hasattr(content, "domain"):
                if content.domain == task_domain:
                    matching += 1
                # Allow partial credit for related domains
                elif self._are_domains_related(content.domain, task_domain):
                    matching += 0.5

        match_ratio = matching / len(memories) if memories else 0

        min_ratio = self.challenge_thresholds["min_domain_match_ratio"]
        if match_ratio < min_ratio:
            severity = (min_ratio - match_ratio) * 2
            return (
                CriticChallenge.DOMAIN_MISMATCH,
                f"Only {match_ratio:.0%} of retrieved memories match domain '{task_domain}'",
                min(1.0, severity),
            )

        return None

    def _are_domains_related(self, domain1: str, domain2: str) -> bool:
        """Check if two domains are semantically related."""
        related_groups = [
            {"CICD", "CFN", "KUBERNETES", "INFRASTRUCTURE"},
            {"IAM", "SECURITY", "COMPLIANCE"},
            {"CFN", "IAM", "TERRAFORM"},
            {"API", "APPLICATION", "SERVICE"},
        ]
        for group in related_groups:
            if domain1 in group and domain2 in group:
                return True
        return False

    def _challenge_logical_leaps(
        self,
        task: dict[str, Any],
        decision: str,
        memories: list["RetrievedMemory"],
    ) -> Optional[tuple[CriticChallenge, str, float]]:
        """
        Challenge: Is the decision logically connected to the memories?
        """
        if not memories:
            # Making a decision with no memories = logical leap
            if decision and "proceed" in decision.lower():
                return (
                    CriticChallenge.LOGICAL_INCONSISTENCY,
                    "Proceeding with no supporting context",
                    0.9,
                )
            return None

        # Check if decision references any memory content
        decision_lower = decision.lower() if decision else ""

        # Look for disconnects
        references_found = False
        for mem in memories:
            content = mem.full_content
            if hasattr(content, "title"):
                if content.title.lower() in decision_lower:
                    references_found = True
                    break
            if hasattr(content, "memory_id"):
                if content.memory_id.lower() in decision_lower:
                    references_found = True
                    break
            # Check for keyword overlap
            if hasattr(content, "keywords"):
                for kw in content.keywords:
                    if kw.lower() in decision_lower:
                        references_found = True
                        break

        # Generic decisions without referencing context are suspicious
        if not references_found and len(memories) > 0:
            # But only if the decision is assertive
            assertive_keywords = ["apply", "execute", "proceed", "use", "implement"]
            is_assertive = any(kw in decision_lower for kw in assertive_keywords)

            if is_assertive:
                return (
                    CriticChallenge.UNEXPLAINED_REASONING,
                    "Decision doesn't clearly reference supporting context",
                    0.4,
                )

        return None

    def _challenge_missing_information(
        self,
        task: dict[str, Any],
        decision: str,
    ) -> Optional[tuple[CriticChallenge, str, float]]:
        """
        Challenge: Is critical information missing from the task?
        """
        task_desc = task.get("description", "")

        # Red flags for missing information
        vague_indicators = [
            ("the thing", "what specific thing?"),
            ("it", "what does 'it' refer to?"),
            ("broken", "what kind of failure?"),
            ("help", "help with what specifically?"),
            ("fix", "what needs fixing?"),
            ("issue", "what specific issue?"),
            ("problem", "what problem exactly?"),
        ]

        missing_info = []
        task_lower = task_desc.lower()

        for indicator, question in vague_indicators:
            if indicator in task_lower:
                # Check if there's enough context to clarify
                words = task_lower.split()
                if len(words) < 10:  # Short vague request
                    missing_info.append(question)

        if missing_info:
            severity = min(1.0, len(missing_info) * 0.3)
            return (
                CriticChallenge.MISSING_INFORMATION,
                f"Task is vague: {', '.join(missing_info[:2])}",
                severity,
            )

        return None

    def _challenge_strategy_appropriateness(
        self,
        strategy: "Strategy",
        confidence: float,
        challenge_count: int,
    ) -> Optional[tuple[CriticChallenge, str, float]]:
        """
        Challenge: Is the strategy appropriate given uncertainties?
        """
        strategy_type = strategy.strategy_type

        # High-confidence strategy with accumulated challenges
        if challenge_count >= 2:
            if strategy_type == StrategyType.PROCEDURAL_EXECUTION:
                return (
                    CriticChallenge.PATTERN_MISMATCH,
                    f"Executing procedure despite {challenge_count} identified uncertainties",
                    0.7,
                )

        # Autonomous action with medium confidence
        if confidence < 0.75 and strategy_type == StrategyType.PROCEDURAL_EXECUTION:
            return (
                CriticChallenge.OVERCONFIDENT_LEAP,
                f"Executing procedure with only {confidence:.0%} confidence",
                0.5,
            )

        return None

    def _challenge_retrieval_quality(
        self,
        memories: list["RetrievedMemory"],
        confidence: float,
    ) -> Optional[tuple[CriticChallenge, str, float]]:
        """
        Challenge: Are the retrieval scores actually strong enough?

        This catches cases where retrieval finds *something* but
        the matches aren't actually highly relevant.
        """
        if not memories:
            return None

        # Get the best retrieval score
        best_score = max(m.combined_score for m in memories)
        avg_score = sum(m.combined_score for m in memories) / len(memories)

        # High confidence but weak best match
        if confidence >= 0.70 and best_score < 0.75:
            return (
                CriticChallenge.PATTERN_MISMATCH,
                f"Confidence ({confidence:.0%}) but best retrieval score is only {best_score:.0%}",
                0.6,
            )

        # High confidence but low average relevance
        if confidence >= 0.70 and avg_score < 0.50:
            return (
                CriticChallenge.INSUFFICIENT_CONTEXT,
                f"Confidence ({confidence:.0%}) but average retrieval score is only {avg_score:.0%}",
                0.5,
            )

        # Moderate confidence with very weak matches
        if confidence >= 0.60 and best_score < 0.50:
            return (
                CriticChallenge.OVERCONFIDENT_LEAP,
                f"Confidence ({confidence:.0%}) but retrieval found only weak matches (best: {best_score:.0%})",
                0.7,
            )

        return None

    def _challenge_task_complexity(
        self,
        task: dict[str, Any],
        confidence: float,
    ) -> Optional[tuple[CriticChallenge, str, float]]:
        """
        Challenge: Does the task complexity warrant this confidence?

        Detects complex tasks through:
        1. Length and structure (requirements, steps)
        2. Risk indicators (production, security, compliance)
        3. Multi-domain signals (multiple AWS services)
        4. Hidden risk signals (new, manual, no tests)
        """
        task_desc = task.get("description", "")
        task_lower = task_desc.lower()
        words = task_desc.split()
        word_count = len(words)

        complexity_score = 0.0
        complexity_reasons = []

        # Factor 1: Length (long tasks are usually complex)
        if word_count > 100:
            complexity_score += 0.3
            complexity_reasons.append("lengthy description")
        elif word_count > 50:
            complexity_score += 0.15

        # Factor 2: Risk indicators
        risk_indicators = [
            "production",
            "urgent",
            "down",
            "incident",
            "outage",
            "security",
            "audit",
            "compliance",
            "cmmc",
            "pii",
            "sensitive",
            "rollback",
            "failed",
            "breaking",
            "critical",
        ]
        risk_count = sum(1 for r in risk_indicators if r in task_lower)
        if risk_count >= 3:
            complexity_score += 0.4
            complexity_reasons.append(f"{risk_count} risk indicators")
        elif risk_count >= 1:
            complexity_score += 0.2
            complexity_reasons.append("risk indicators present")

        # Factor 3: Multi-domain (mentions multiple AWS services/domains)
        domain_indicators = [
            "iam",
            "cloudformation",
            "cfn",
            "neptune",
            "eks",
            "kubernetes",
            "lambda",
            "s3",
            "kms",
            "opensearch",
            "dynamodb",
            "ec2",
            "ecs",
            "vpc",
            "route53",
            "sns",
            "sqs",
            "bedrock",
            "codebuild",
        ]
        domain_count = sum(1 for d in domain_indicators if d in task_lower)
        if domain_count >= 4:
            complexity_score += 0.4
            complexity_reasons.append(f"{domain_count} services/domains mentioned")
        elif domain_count >= 2:
            complexity_score += 0.2
            complexity_reasons.append("multi-domain")

        # Factor 4: Requirements/steps (numbered items)
        requirements = (
            task_lower.count("1.")
            + task_lower.count("2.")
            + task_lower.count("3.")
            + task_lower.count("4.")
            + task_desc.count("- ")
            + task_desc.count("• ")
        )
        if requirements >= 3:
            complexity_score += 0.3
            complexity_reasons.append(f"{requirements} requirements/steps")

        # Factor 5: Hidden complexity signals
        hidden_risk = [
            "new hire",
            "new developer",
            "no test",
            "no documentation",
            "manually",
            "console",
            "workaround",
            "legacy",
            "conflict",
            "circular",
            "dependency",
            "trade-off",
            "tradeoff",
        ]
        hidden_count = sum(1 for h in hidden_risk if h in task_lower)
        if hidden_count >= 1:
            complexity_score += 0.25
            complexity_reasons.append("hidden complexity signals")

        # Only challenge if complexity is significant AND confidence is moderate+
        if complexity_score >= 0.4 and confidence >= 0.60:
            severity = min(0.8, complexity_score * 0.8)
            reasons = ", ".join(complexity_reasons[:3])
            return (
                CriticChallenge.PATTERN_MISMATCH,
                f"Task complexity ({complexity_score:.1f}) suggests caution: {reasons}",
                severity,
            )

        return None

    def _apply_baseline_skepticism(
        self,
        task: dict[str, Any],
        confidence: float,
        existing_challenge_count: int,
    ) -> Optional[tuple[CriticChallenge, str, float]]:
        """
        Apply baseline skepticism - the "naive outsider" perspective.

        Neuroscience insight: The anterior cingulate cortex maintains
        a baseline level of vigilance/doubt that scales with stakes.

        This ensures SOME challenge is always raised at moderate+ confidence,
        preventing the system from being overconfident even when retrieval
        appears to succeed (keyword matching ≠ semantic understanding).
        """
        # If other challenges already raised, skip baseline
        if existing_challenge_count >= 2:
            return None

        # Always challenge confidence >= 0.70 with skepticism
        # This is lower threshold to catch more borderline cases
        if confidence >= 0.70 and existing_challenge_count == 0:
            # Skepticism scales with confidence
            # At 0.70: severity = 0.4, at 0.80: severity = 0.6, at 0.90: severity = 0.8
            severity = 0.4 + (confidence - 0.70) * 2.0
            return (
                CriticChallenge.OVERCONFIDENT_LEAP,
                f"Confidence ({confidence:.0%}) warrants verification - keyword matches don't guarantee semantic relevance",
                min(0.8, severity),
            )

        # Lower confidence (0.60-0.70) with no challenges = mild skepticism
        if 0.60 <= confidence < 0.70 and existing_challenge_count == 0:
            return (
                CriticChallenge.UNEXPLAINED_REASONING,
                f"Moderate confidence ({confidence:.0%}) - recommend verification before autonomous action",
                0.3,
            )

        return None


# =============================================================================
# DUAL AGENT ORCHESTRATOR
# =============================================================================


class DualAgentOrchestrator:
    """
    Orchestrates interaction between Memory Agent and Critic Agent.

    Neuroscience analog: Prefrontal-ACC interaction
    - Memory Agent = dorsolateral prefrontal cortex (working memory, planning)
    - Critic Agent = anterior cingulate cortex (conflict monitoring, error detection)

    The interaction creates a calibrated confidence through debate.

    Supports three modes:
    - SINGLE: MemoryAgent only (faster, lower cost)
    - DUAL: MemoryAgent + CriticAgent (more thorough)
    - AUTO: Selects based on task risk indicators

    Empirical finding: In cold-start scenarios, both modes perform similarly.
    DUAL mode provides value for high-stakes decisions where overconfidence is risky.
    """

    # Risk indicators that trigger DUAL mode in AUTO
    RISK_INDICATORS = [
        "production",
        "critical",
        "security",
        "compliance",
        "pii",
        "data integrity",
        "migration",
        "rollback",
        "incident",
        "outage",
    ]

    def __init__(
        self,
        memory_service: "CognitiveMemoryService",
        critic_agent: Optional["CriticAgent"] = None,
        default_mode: AgentMode = AgentMode.AUTO,
    ):
        self.memory_service = memory_service
        self.critic = critic_agent or CriticAgent()
        self.default_mode = default_mode

    def _should_use_dual_mode(self, task_description: str, domain: str) -> bool:
        """Determine if dual-agent mode should be used based on risk indicators."""
        task_lower = task_description.lower()

        # Check for risk indicators
        for indicator in self.RISK_INDICATORS:
            if indicator in task_lower:
                return True

        # High-risk domains always use dual mode
        high_risk_domains = ["SECURITY", "COMPLIANCE", "PRODUCTION"]
        if domain.upper() in high_risk_domains:
            return True

        return False

    async def make_decision(
        self,
        task_description: str,
        domain: str,
        proposed_action: Optional[str] = None,
        mode: Optional[AgentMode] = None,
    ) -> dict[str, Any]:
        """
        Execute decision making with configurable agent architecture.

        Args:
            task_description: Description of the task to analyze
            domain: Domain context (CICD, SECURITY, IAM, etc.)
            proposed_action: Optional pre-defined action to evaluate
            mode: Agent mode (SINGLE, DUAL, AUTO). Defaults to instance default.

        Returns:
            Decision result with confidence, strategy, and diagnostics.

        Modes:
            SINGLE: MemoryAgent only - faster, ~50% less latency
            DUAL: MemoryAgent + CriticAgent - prevents overconfidence
            AUTO: Selects based on risk indicators in task
        """
        # Determine effective mode
        effective_mode = mode or self.default_mode
        if effective_mode == AgentMode.AUTO:
            use_dual = self._should_use_dual_mode(task_description, domain)
            effective_mode = AgentMode.DUAL if use_dual else AgentMode.SINGLE

        # Phase 1: Memory Agent makes initial assessment
        memory_context = await self.memory_service.load_cognitive_context(
            task_description=task_description,
            domain=domain,
        )

        initial_confidence = memory_context["confidence"]
        strategy = memory_context["strategy"]
        retrieved_memories = memory_context["retrieved_memories"]
        guardrails = memory_context["guardrails"]

        # Generate initial decision if not provided
        if proposed_action is None:
            proposed_action = self._generate_decision(
                strategy, guardrails, initial_confidence.score
            )

        # SINGLE MODE: Skip critic evaluation
        if effective_mode == AgentMode.SINGLE:
            return {
                "decision": proposed_action,
                "initial_confidence": initial_confidence.score,
                "critic_evaluation": None,
                "calibrated_confidence": initial_confidence.score,
                "strategy": strategy,
                "retrieved_memories": retrieved_memories,
                "guardrails": guardrails,
                "working_memory": memory_context["working_memory"],
                "agent_mode": "SINGLE",
                "diagnostics": {
                    "challenge_count": 0,
                    "confidence_reduction": 0.0,
                    "escalation_recommended": initial_confidence.score < 0.5,
                    "critic_questions": [],
                },
            }

        # DUAL MODE: Full critic evaluation
        # Phase 2: Critic Agent evaluates
        task = {"description": task_description, "domain": domain}
        critic_evaluation = self.critic.evaluate_decision(
            task=task,
            proposed_decision=proposed_action,
            memory_agent_confidence=initial_confidence.score,
            retrieved_memories=retrieved_memories,
            strategy=strategy,
        )

        # Phase 3: Calibrate confidence based on critic feedback
        calibrated_confidence = self._calibrate_confidence(
            initial_confidence, critic_evaluation
        )

        # Phase 4: Possibly adjust strategy based on calibrated confidence
        adjusted_strategy = self._adjust_strategy_if_needed(
            strategy, calibrated_confidence, critic_evaluation
        )

        # Phase 5: Generate final recommendation
        final_decision = self._generate_final_decision(
            proposed_action, critic_evaluation, adjusted_strategy
        )

        return {
            "decision": final_decision,
            "initial_confidence": initial_confidence.score,
            "critic_evaluation": critic_evaluation,
            "calibrated_confidence": calibrated_confidence,
            "strategy": adjusted_strategy,
            "retrieved_memories": retrieved_memories,
            "guardrails": guardrails,
            "working_memory": memory_context["working_memory"],
            "agent_mode": "DUAL",
            # Diagnostic information
            "diagnostics": {
                "challenge_count": len(critic_evaluation.challenges),
                "confidence_reduction": initial_confidence.score
                - calibrated_confidence,
                "escalation_recommended": critic_evaluation.should_escalate,
                "critic_questions": critic_evaluation.questions,
            },
        }

    def _generate_decision(
        self, strategy: "Strategy", guardrails: list, confidence: float
    ) -> str:
        """Generate a decision based on strategy and context."""
        if strategy.strategy_type == StrategyType.PROCEDURAL_EXECUTION:
            if strategy.procedure:
                return f"Execute procedure: {strategy.procedure.name}"
            return "Execute known procedure"

        if guardrails:
            ids = [g["id"] for g in guardrails[:3]]
            return f"Apply guardrails: {', '.join(ids)}"

        if strategy.strategy_type == StrategyType.ACTIVE_LEARNING:
            return "Request human guidance due to low confidence"

        if strategy.strategy_type == StrategyType.HUMAN_GUIDANCE:
            return "Escalate to human for review"

        return "Proceed with caution, log all actions"

    def _calibrate_confidence(
        self,
        initial: "ConfidenceEstimate",
        critic_eval: "CriticEvaluation",
    ) -> float:
        """
        Calibrate confidence based on critic's evaluation.

        Formula: calibrated = initial * adjustment * (1 - challenge_penalty)
        """
        base_confidence = initial.score

        # Apply critic's adjustment
        adjusted = base_confidence * critic_eval.confidence_adjustment

        # Additional penalty for specific high-severity challenges
        high_severity_challenges = [c for c in critic_eval.challenges if c[2] >= 0.7]
        if high_severity_challenges:
            penalty = len(high_severity_challenges) * 0.05
            adjusted = adjusted * (1 - penalty)

        # Ensure bounds
        return max(0.1, min(0.95, adjusted))

    def _adjust_strategy_if_needed(
        self,
        original_strategy: "Strategy",
        calibrated_confidence: float,
        critic_eval: "CriticEvaluation",
    ) -> "Strategy":
        """
        Adjust strategy if calibrated confidence changes the situation.
        """
        # If escalation is recommended, override to HUMAN_GUIDANCE
        if critic_eval.should_escalate:
            return Strategy(
                strategy_type=StrategyType.HUMAN_GUIDANCE,
                questions=critic_eval.questions,
                fallback=original_strategy.strategy_type,
                logging_level="VERBOSE",
                checkpoint_frequency="HIGH",
            )

        # If confidence dropped significantly, downgrade strategy
        if original_strategy.strategy_type == StrategyType.PROCEDURAL_EXECUTION:
            if calibrated_confidence < 0.75:
                return Strategy(
                    strategy_type=StrategyType.SCHEMA_GUIDED,
                    schema=original_strategy.schema,
                    guardrails=original_strategy.guardrails,
                    fallback=StrategyType.HUMAN_GUIDANCE,
                    logging_level="NORMAL",
                    checkpoint_frequency="MEDIUM",
                )

        if original_strategy.strategy_type == StrategyType.SCHEMA_GUIDED:
            if calibrated_confidence < 0.50:
                return Strategy(
                    strategy_type=StrategyType.ACTIVE_LEARNING,
                    questions=critic_eval.questions,
                    fallback=StrategyType.HUMAN_GUIDANCE,
                    logging_level="VERBOSE",
                    checkpoint_frequency="HIGH",
                )

        return original_strategy

    def _generate_final_decision(
        self,
        proposed_action: str,
        critic_eval: "CriticEvaluation",
        strategy: "Strategy",
    ) -> str:
        """Generate final decision incorporating critic feedback."""
        if critic_eval.should_escalate:
            return (
                f"ESCALATE: {proposed_action}\n"
                f"Critic raised {len(critic_eval.challenges)} concerns:\n"
                + "\n".join(f"- {q}" for q in critic_eval.questions[:3])
            )

        if strategy.strategy_type == StrategyType.HUMAN_GUIDANCE:
            return f"Request review: {proposed_action}"

        if strategy.strategy_type == StrategyType.ACTIVE_LEARNING:
            return (
                f"Tentative: {proposed_action}\n"
                f"Questions to clarify:\n"
                + "\n".join(f"- {q}" for q in critic_eval.questions[:2])
            )

        return proposed_action


class AccuracyMonitor:
    """
    Monitors accuracy to maintain 85% target.
    Triggers improvements when accuracy degrades.
    """

    TARGET_ACCURACY = 0.85
    HIGH_CONFIDENCE_TARGET = 0.95
    MEDIUM_CONFIDENCE_TARGET = 0.85
    LOW_CONFIDENCE_TARGET = 0.75

    def __init__(self, episodic_store: EpisodicStore) -> None:
        self.episodic_store = episodic_store

    async def calculate_accuracy(
        self, window: timedelta = timedelta(days=7)  # noqa: B008
    ) -> dict[str, Any]:
        """Calculate rolling accuracy metrics."""
        since = datetime.now() - window

        # Query all recent episodes
        episodes: list[EpisodicMemory] = []
        for domain in ["CICD", "IAM", "SECURITY", "CFN", "KUBERNETES", "API"]:
            domain_episodes = await self.episodic_store.query_by_domain(
                domain, since, limit=1000
            )
            episodes.extend(domain_episodes)

        if not episodes:
            return {"overall_accuracy": None, "message": "No episodes in window"}

        # Calculate overall accuracy
        successful = [e for e in episodes if e.outcome == OutcomeStatus.SUCCESS]
        overall_accuracy = len(successful) / len(episodes)

        # Calculate by confidence band
        high_conf = [e for e in episodes if e.confidence_at_decision >= 0.85]
        medium_conf = [e for e in episodes if 0.50 <= e.confidence_at_decision < 0.85]
        low_conf = [e for e in episodes if e.confidence_at_decision < 0.50]

        by_band = {
            "high": self._calculate_band_accuracy(high_conf),
            "medium": self._calculate_band_accuracy(medium_conf),
            "low": self._calculate_band_accuracy(low_conf),
        }

        # Calculate by domain
        by_domain = {}
        domains = {e.domain for e in episodes}
        for domain in domains:
            domain_eps = [e for e in episodes if e.domain == domain]
            by_domain[domain] = self._calculate_band_accuracy(domain_eps)

        # Generate alerts
        alerts = []
        if overall_accuracy < self.TARGET_ACCURACY:
            alerts.append(
                {
                    "severity": "CRITICAL",
                    "message": f"Overall accuracy ({overall_accuracy:.1%}) below target ({self.TARGET_ACCURACY:.0%})",
                }
            )

        if by_band["high"]["accuracy"] is not None:
            if by_band["high"]["accuracy"] < self.HIGH_CONFIDENCE_TARGET:
                alerts.append(
                    {
                        "severity": "WARNING",
                        "message": f"High-confidence accuracy ({by_band['high']['accuracy']:.1%}) below target",
                    }
                )

        return {
            "window": str(window),
            "overall_accuracy": overall_accuracy,
            "by_confidence_band": by_band,
            "by_domain": by_domain,
            "alerts": alerts,
            "episode_count": len(episodes),
        }

    def _calculate_band_accuracy(
        self, episodes: list[EpisodicMemory]
    ) -> dict[str, Any]:
        """Calculate accuracy for a set of episodes."""
        if not episodes:
            return {"count": 0, "accuracy": None}

        successful = [e for e in episodes if e.outcome == OutcomeStatus.SUCCESS]
        return {
            "count": len(episodes),
            "accuracy": len(successful) / len(episodes),
        }
