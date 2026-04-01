"""
Project Aura - Memory Evolution Contracts (ADR-080)

Data contracts for the ReMem Action Framework implementing
test-time memory evolution operations.

Enums:
- RefineOperation: CONSOLIDATE, PRUNE, REINFORCE, ABSTRACT, LINK, CORRECT, ROLLBACK
- OperationPhase: Phase classification for operation rollout

Dataclasses:
- RefineAction: A discrete refinement action in the agent loop
- RefineResult: Result of a refinement operation
- MemorySnapshot: Point-in-time memory state for rollback
- ConsolidationCandidate: Pair of memories identified for merging
- PruneCandidate: Memory identified for removal
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class RefineOperation(Enum):
    """Memory refinement operations for ReMem framework."""

    # Phase 1a - Low latency operations
    CONSOLIDATE = "consolidate"  # Merge similar experiences
    PRUNE = "prune"  # Remove low-value memories

    # Phase 1b - Titan integration
    REINFORCE = "reinforce"  # Strengthen successful patterns (Titan TTT)

    # Phase 3 - LLM-based abstraction
    ABSTRACT = "abstract"  # Extract generalizable strategy

    # Phase 5 - Advanced operations
    LINK = "link"  # Create cross-memory associations (Neptune)
    CORRECT = "correct"  # Fix incorrect memories
    ROLLBACK = "rollback"  # Restore from DynamoDB Streams snapshot


class OperationPhase(Enum):
    """Phase classification for operation deployment status."""

    PHASE_1A = "1a"  # Low latency: CONSOLIDATE, PRUNE
    PHASE_1B = "1b"  # Titan integration: REINFORCE
    PHASE_3 = "3"  # LLM abstraction: ABSTRACT
    PHASE_5 = "5"  # Advanced: LINK, CORRECT, ROLLBACK

    @classmethod
    def get_phase(cls, operation: RefineOperation) -> "OperationPhase":
        """Get the deployment phase for an operation."""
        phase_map = {
            RefineOperation.CONSOLIDATE: cls.PHASE_1A,
            RefineOperation.PRUNE: cls.PHASE_1A,
            RefineOperation.REINFORCE: cls.PHASE_1B,
            RefineOperation.ABSTRACT: cls.PHASE_3,
            RefineOperation.LINK: cls.PHASE_5,
            RefineOperation.CORRECT: cls.PHASE_5,
            RefineOperation.ROLLBACK: cls.PHASE_5,
        }
        return phase_map[operation]


class RefineStatus(Enum):
    """Status of a refinement operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class SimilarityMetric(Enum):
    """Metrics used for memory similarity calculation."""

    COSINE = "cosine"  # Embedding cosine similarity
    JACCARD = "jaccard"  # Set-based overlap
    LEVENSHTEIN = "levenshtein"  # Edit distance (normalized)
    SEMANTIC = "semantic"  # LLM-based semantic similarity


# Type aliases for domain clarity
MemoryId = str
AgentId = str
TenantId = str
SecurityDomain = str
RollbackToken = str


@dataclass
class RefineAction:
    """A discrete refinement action in the agent loop."""

    operation: RefineOperation
    target_memory_ids: list[str]
    reasoning: str  # Why this refinement (encrypted at rest)
    confidence: float  # 0.0 to 1.0
    tenant_id: TenantId  # Required for multi-tenant isolation
    security_domain: SecurityDomain  # For domain boundary enforcement
    agent_id: Optional[AgentId] = None
    action_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate action after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        if not self.target_memory_ids:
            raise ValueError("At least one target memory ID is required")
        if not self.tenant_id:
            raise ValueError("tenant_id is required for multi-tenant isolation")
        if not self.security_domain:
            raise ValueError(
                "security_domain is required for domain boundary enforcement"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "action_id": self.action_id,
            "operation": self.operation.value,
            "target_memory_ids": self.target_memory_ids,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "tenant_id": self.tenant_id,
            "security_domain": self.security_domain,
            "agent_id": self.agent_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RefineAction":
        """Deserialize from dictionary."""
        return cls(
            action_id=data.get("action_id"),
            operation=RefineOperation(data["operation"]),
            target_memory_ids=data["target_memory_ids"],
            reasoning=data["reasoning"],
            confidence=data["confidence"],
            tenant_id=data["tenant_id"],
            security_domain=data["security_domain"],
            agent_id=data.get("agent_id"),
            metadata=data.get("metadata", {}),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if isinstance(data.get("created_at"), str)
                else data.get("created_at", datetime.now(timezone.utc))
            ),
        )


@dataclass
class RefineResult:
    """Result of a refinement operation."""

    success: bool
    operation: RefineOperation
    affected_memory_ids: list[str]
    action_id: Optional[str] = None
    rollback_token: Optional[RollbackToken] = None  # For ROLLBACK operation
    error: Optional[str] = None
    latency_ms: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "operation": self.operation.value,
            "affected_memory_ids": self.affected_memory_ids,
            "action_id": self.action_id,
            "rollback_token": self.rollback_token,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "metrics": self.metrics,
            "completed_at": self.completed_at.isoformat(),
        }


@dataclass
class MemorySnapshot:
    """Point-in-time snapshot for rollback operations."""

    snapshot_id: str
    memory_ids: list[str]
    snapshot_data: dict[str, Any]  # Serialized memory state
    tenant_id: TenantId
    security_domain: SecurityDomain
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None  # TTL for snapshot retention

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "memory_ids": self.memory_ids,
            "snapshot_data": self.snapshot_data,
            "tenant_id": self.tenant_id,
            "security_domain": self.security_domain,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class ConsolidationCandidate:
    """A pair of memories identified as candidates for consolidation."""

    memory_id_a: MemoryId
    memory_id_b: MemoryId
    similarity_score: float  # 0.0 to 1.0
    similarity_metric: SimilarityMetric
    merge_strategy: str = "weighted_average"
    overlap_analysis: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate candidate after initialization."""
        if not 0.0 <= self.similarity_score <= 1.0:
            raise ValueError(
                f"Similarity score must be between 0.0 and 1.0, got {self.similarity_score}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "memory_id_a": self.memory_id_a,
            "memory_id_b": self.memory_id_b,
            "similarity_score": self.similarity_score,
            "similarity_metric": self.similarity_metric.value,
            "merge_strategy": self.merge_strategy,
            "overlap_analysis": self.overlap_analysis,
        }


@dataclass
class PruneCandidate:
    """A memory identified as a candidate for pruning."""

    memory_id: MemoryId
    prune_score: float  # 0.0 to 1.0 (higher = more likely to prune)
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    value_score: float = 0.0  # Historical usefulness
    age_days: int = 0
    reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate candidate after initialization."""
        if not 0.0 <= self.prune_score <= 1.0:
            raise ValueError(
                f"Prune score must be between 0.0 and 1.0, got {self.prune_score}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "memory_id": self.memory_id,
            "prune_score": self.prune_score,
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed else None
            ),
            "access_count": self.access_count,
            "value_score": self.value_score,
            "age_days": self.age_days,
            "reasons": self.reasons,
        }


@dataclass
class AbstractionCandidate:
    """A group of memories identified for abstraction into a strategy."""

    memory_ids: list[MemoryId]
    cluster_id: str  # HDBSCAN cluster identifier
    centroid_embedding: list[float]  # Cluster centroid for similarity
    coherence_score: float  # 0.0 to 1.0 - how related the memories are
    abstraction_potential: float  # 0.0 to 1.0 - likelihood of good abstraction
    common_themes: list[str]  # Detected themes across memories
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate candidate after initialization."""
        if not 0.0 <= self.coherence_score <= 1.0:
            raise ValueError(
                f"Coherence score must be between 0.0 and 1.0, got {self.coherence_score}"
            )
        if not 0.0 <= self.abstraction_potential <= 1.0:
            raise ValueError(
                f"Abstraction potential must be between 0.0 and 1.0, "
                f"got {self.abstraction_potential}"
            )
        if len(self.memory_ids) < 2:
            raise ValueError("At least 2 memories required for abstraction")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "memory_ids": self.memory_ids,
            "cluster_id": self.cluster_id,
            "centroid_embedding": self.centroid_embedding,
            "coherence_score": self.coherence_score,
            "abstraction_potential": self.abstraction_potential,
            "common_themes": self.common_themes,
            "metadata": self.metadata,
        }


@dataclass
class AbstractedStrategy:
    """A generalized strategy extracted from multiple task experiences."""

    strategy_id: str
    title: str  # Short title for the strategy
    description: str  # Full description of the strategy
    source_memory_ids: list[MemoryId]  # Original memories this was derived from
    applicability_conditions: list[str]  # When to apply this strategy
    key_steps: list[str]  # Core steps of the strategy
    success_indicators: list[str]  # How to know if strategy worked
    embedding: list[float]  # Strategy embedding for retrieval
    confidence: float  # 0.0 to 1.0
    tenant_id: TenantId
    security_domain: SecurityDomain
    quality_metrics: dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate strategy after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "strategy_id": self.strategy_id,
            "title": self.title,
            "description": self.description,
            "source_memory_ids": self.source_memory_ids,
            "applicability_conditions": self.applicability_conditions,
            "key_steps": self.key_steps,
            "success_indicators": self.success_indicators,
            "embedding": self.embedding,
            "confidence": self.confidence,
            "tenant_id": self.tenant_id,
            "security_domain": self.security_domain,
            "quality_metrics": self.quality_metrics,
            "created_at": self.created_at.isoformat(),
        }

    def to_dynamo_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            "pk": f"strategy#{self.tenant_id}",
            "sk": f"{self.security_domain}#{self.strategy_id}",
            "strategy_id": self.strategy_id,
            "title": self.title,
            "description": self.description,
            "source_memory_ids": self.source_memory_ids,
            "applicability_conditions": self.applicability_conditions,
            "key_steps": self.key_steps,
            "success_indicators": self.success_indicators,
            "confidence": str(self.confidence),
            "tenant_id": self.tenant_id,
            "security_domain": self.security_domain,
            "quality_metrics": self.quality_metrics,
            "created_at": self.created_at.isoformat(),
            "gsi1pk": f"domain#{self.security_domain}",
            "gsi1sk": self.created_at.isoformat(),
        }


@dataclass
class EvolutionRecord:
    """Record of a memory evolution event for audit trail."""

    record_id: str
    operation: RefineOperation
    agent_id: AgentId
    tenant_id: TenantId
    security_domain: SecurityDomain
    action: RefineAction
    result: RefineResult
    task_id: Optional[str] = None
    task_sequence_number: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dynamo_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        # Use date-bucketed partition key to prevent hot partitions
        date_bucket = self.created_at.strftime("%Y-%m-%d")
        return {
            "pk": f"{self.agent_id}#{date_bucket}",
            "timestamp": self.created_at.isoformat(),
            "record_id": self.record_id,
            "operation": self.operation.value,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "security_domain": self.security_domain,
            "task_id": self.task_id,
            "task_sequence_number": self.task_sequence_number,
            "action": self.action.to_dict(),
            "result": self.result.to_dict(),
            "outcome": "success" if self.result.success else "failure",
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "record_id": self.record_id,
            "operation": self.operation.value,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "security_domain": self.security_domain,
            "task_id": self.task_id,
            "task_sequence_number": self.task_sequence_number,
            "action": self.action.to_dict(),
            "result": self.result.to_dict(),
            "created_at": self.created_at.isoformat(),
        }
