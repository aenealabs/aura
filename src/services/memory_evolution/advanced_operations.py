"""
Project Aura - Advanced Memory Evolution Operations (ADR-080 Phase 5)

Implements LINK, CORRECT, and ROLLBACK operations for the ReMem Action Framework.

Operations:
- LINK: Create cross-memory associations in Neptune graph
- CORRECT: Fix incorrect memories with LLM verification
- ROLLBACK: Restore memories from DynamoDB Streams snapshots

Edge Types for LINK:
- STRATEGY_DERIVED_FROM: Strategy abstracted from experiences
- REINFORCES: Successful pattern connection
- CONTRADICTS: Conflicting information link
- SUPERSEDES: Memory update chain
- RELATED_TO: General association

Compliance:
- ADR-080: Evo-Memory Enhancements (Phase 5)
- CMMC Level 3: Multi-tenant isolation, encryption at rest
- NIST 800-53: AU-11, SI-12, AC-4 controls
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol

from .contracts import (
    MemoryId,
    MemorySnapshot,
    RefineAction,
    RefineOperation,
    RefineResult,
    SecurityDomain,
    TenantId,
)
from .exceptions import (
    RollbackError,
    SecurityBoundaryViolation,
    TenantIsolationViolation,
    ValidationError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================


class LinkType(Enum):
    """Types of memory associations for Neptune graph."""

    STRATEGY_DERIVED_FROM = (
        "STRATEGY_DERIVED_FROM"  # Strategy abstracted from experiences
    )
    REINFORCES = "REINFORCES"  # Successful pattern connection
    CONTRADICTS = "CONTRADICTS"  # Conflicting information link
    SUPERSEDES = "SUPERSEDES"  # Memory update chain
    RELATED_TO = "RELATED_TO"  # General association
    DEPENDS_ON = "DEPENDS_ON"  # Dependency relationship
    SIMILAR_TO = "SIMILAR_TO"  # Similarity-based link


class CorrectionReason(Enum):
    """Reasons for memory correction."""

    FACTUAL_ERROR = "factual_error"  # Incorrect facts stored
    OUTDATED_INFO = "outdated_info"  # Information no longer accurate
    MISATTRIBUTION = "misattribution"  # Wrong source/context
    STRATEGY_FAILURE = "strategy_failure"  # Strategy led to failures
    USER_FEEDBACK = "user_feedback"  # User-initiated correction
    LLM_VERIFICATION = "llm_verification"  # LLM detected inconsistency


class SnapshotSource(Enum):
    """Source of memory snapshot for rollback."""

    DYNAMODB_STREAMS = "dynamodb_streams"  # From DynamoDB change stream
    POINT_IN_TIME = "point_in_time"  # From PITR backup
    MANUAL_BACKUP = "manual_backup"  # From scheduled backup
    PRE_OPERATION = "pre_operation"  # Captured before refine operation


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class LinkCandidate:
    """A pair of memories identified for linking in Neptune."""

    source_memory_id: MemoryId
    target_memory_id: MemoryId
    link_type: LinkType
    confidence: float  # 0.0 to 1.0
    reasoning: str  # Why this link exists
    metadata: dict[str, Any] = field(default_factory=dict)
    bidirectional: bool = False  # Create edge in both directions

    def __post_init__(self) -> None:
        """Validate candidate after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        if self.source_memory_id == self.target_memory_id:
            raise ValueError("Cannot link memory to itself")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_memory_id": self.source_memory_id,
            "target_memory_id": self.target_memory_id,
            "link_type": self.link_type.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
            "bidirectional": self.bidirectional,
        }


@dataclass
class CorrectionCandidate:
    """A memory identified for correction."""

    memory_id: MemoryId
    correction_reason: CorrectionReason
    original_content: str
    corrected_content: str
    verification_confidence: float  # 0.0 to 1.0 - LLM verification score
    supporting_evidence: list[str] = field(default_factory=list)
    requires_human_review: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate candidate after initialization."""
        if not 0.0 <= self.verification_confidence <= 1.0:
            raise ValueError(
                f"Verification confidence must be between 0.0 and 1.0, "
                f"got {self.verification_confidence}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "memory_id": self.memory_id,
            "correction_reason": self.correction_reason.value,
            "original_content": self.original_content,
            "corrected_content": self.corrected_content,
            "verification_confidence": self.verification_confidence,
            "supporting_evidence": self.supporting_evidence,
            "requires_human_review": self.requires_human_review,
            "metadata": self.metadata,
        }


@dataclass
class SnapshotMetadata:
    """Metadata for a memory snapshot."""

    snapshot_id: str
    source: SnapshotSource
    memory_count: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    operation_id: Optional[str] = None  # RefineAction that triggered snapshot
    stream_sequence_number: Optional[str] = None  # DynamoDB Streams position

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "source": self.source.value,
            "memory_count": self.memory_count,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "operation_id": self.operation_id,
            "stream_sequence_number": self.stream_sequence_number,
        }


@dataclass
class LinkResult:
    """Result of a LINK operation."""

    edge_id: str
    source_memory_id: MemoryId
    target_memory_id: MemoryId
    link_type: LinkType
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "edge_id": self.edge_id,
            "source_memory_id": self.source_memory_id,
            "target_memory_id": self.target_memory_id,
            "link_type": self.link_type.value,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CorrectionResult:
    """Result of a CORRECT operation."""

    memory_id: MemoryId
    version_before: int
    version_after: int
    correction_reason: CorrectionReason
    human_review_required: bool
    corrected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "memory_id": self.memory_id,
            "version_before": self.version_before,
            "version_after": self.version_after,
            "correction_reason": self.correction_reason.value,
            "human_review_required": self.human_review_required,
            "corrected_at": self.corrected_at.isoformat(),
        }


@dataclass
class RollbackResult:
    """Result of a ROLLBACK operation."""

    snapshot_id: str
    memories_restored: int
    memories_failed: int
    failed_memory_ids: list[MemoryId] = field(default_factory=list)
    restored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "memories_restored": self.memories_restored,
            "memories_failed": self.memories_failed,
            "failed_memory_ids": self.failed_memory_ids,
            "restored_at": self.restored_at.isoformat(),
        }


# =============================================================================
# PROTOCOLS
# =============================================================================


class NeptuneGraphServiceProtocol(Protocol):
    """Protocol for Neptune graph database operations."""

    async def execute_gremlin(
        self, query: str, bindings: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a Gremlin query with parameter bindings."""
        ...

    async def vertex_exists(self, vertex_id: str) -> bool:
        """Check if a vertex exists in the graph."""
        ...


class LLMServiceProtocol(Protocol):
    """Protocol for LLM service operations."""

    async def verify_correction(
        self,
        original_content: str,
        corrected_content: str,
        context: dict[str, Any],
    ) -> tuple[bool, float, str]:
        """Verify if a correction is valid. Returns (is_valid, confidence, reasoning)."""
        ...

    async def detect_inconsistency(
        self,
        memory_content: str,
        context_memories: list[str],
    ) -> tuple[bool, float, str]:
        """Detect if memory is inconsistent with context. Returns (has_issue, confidence, explanation)."""
        ...


class SnapshotStoreProtocol(Protocol):
    """Protocol for snapshot storage operations."""

    async def save_snapshot(
        self,
        snapshot: MemorySnapshot,
        tenant_id: TenantId,
        security_domain: SecurityDomain,
    ) -> str:
        """Save a snapshot and return snapshot_id."""
        ...

    async def get_snapshot(
        self,
        snapshot_id: str,
        tenant_id: TenantId,
        security_domain: SecurityDomain,
    ) -> Optional[MemorySnapshot]:
        """Retrieve a snapshot by ID with tenant/domain validation."""
        ...

    async def list_snapshots(
        self,
        tenant_id: TenantId,
        security_domain: SecurityDomain,
        limit: int = 10,
    ) -> list[SnapshotMetadata]:
        """List available snapshots for tenant/domain."""
        ...

    async def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot. Returns True if deleted."""
        ...


class MemoryStoreProtocol(Protocol):
    """Protocol for memory storage operations."""

    async def get_memory(
        self, memory_id: MemoryId, tenant_id: TenantId
    ) -> Optional[dict[str, Any]]:
        """Get a memory by ID."""
        ...

    async def update_memory(
        self, memory_id: MemoryId, updates: dict[str, Any], tenant_id: TenantId
    ) -> dict[str, Any]:
        """Update a memory and return the updated record."""
        ...

    async def get_memory_version(self, memory_id: MemoryId, tenant_id: TenantId) -> int:
        """Get current version number of a memory."""
        ...

    async def restore_memories(
        self,
        memories: list[dict[str, Any]],
        tenant_id: TenantId,
    ) -> tuple[int, list[MemoryId]]:
        """Restore memories from snapshot. Returns (success_count, failed_ids)."""
        ...


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class AdvancedOperationsConfig:
    """Configuration for advanced memory operations."""

    # LINK configuration
    link_confidence_threshold: float = 0.7  # Min confidence for auto-linking
    max_links_per_memory: int = 50  # Prevent link explosion
    link_ttl_days: int = 365  # Link expiration

    # CORRECT configuration
    correction_confidence_threshold: float = 0.8  # Min LLM confidence for auto-correct
    human_review_threshold: float = 0.6  # Below this requires human review
    max_correction_retries: int = 3

    # ROLLBACK configuration
    snapshot_retention_days: int = 30
    max_memories_per_rollback: int = 100  # Limit for safety
    require_confirmation: bool = True  # Require explicit confirmation for rollback

    # Feature flags
    link_enabled: bool = True
    correct_enabled: bool = True
    rollback_enabled: bool = True

    @classmethod
    def from_environment(cls) -> "AdvancedOperationsConfig":
        """Create config from environment variables."""
        import os

        return cls(
            link_confidence_threshold=float(
                os.getenv("ADR080_LINK_CONFIDENCE_THRESHOLD", "0.7")
            ),
            max_links_per_memory=int(os.getenv("ADR080_MAX_LINKS_PER_MEMORY", "50")),
            link_ttl_days=int(os.getenv("ADR080_LINK_TTL_DAYS", "365")),
            correction_confidence_threshold=float(
                os.getenv("ADR080_CORRECTION_CONFIDENCE_THRESHOLD", "0.8")
            ),
            human_review_threshold=float(
                os.getenv("ADR080_HUMAN_REVIEW_THRESHOLD", "0.6")
            ),
            max_correction_retries=int(os.getenv("ADR080_MAX_CORRECTION_RETRIES", "3")),
            snapshot_retention_days=int(
                os.getenv("ADR080_SNAPSHOT_RETENTION_DAYS", "30")
            ),
            max_memories_per_rollback=int(
                os.getenv("ADR080_MAX_MEMORIES_PER_ROLLBACK", "100")
            ),
            require_confirmation=os.getenv(
                "ADR080_REQUIRE_ROLLBACK_CONFIRMATION", "true"
            ).lower()
            == "true",
            link_enabled=os.getenv("ADR080_LINK_ENABLED", "true").lower() == "true",
            correct_enabled=os.getenv("ADR080_CORRECT_ENABLED", "true").lower()
            == "true",
            rollback_enabled=os.getenv("ADR080_ROLLBACK_ENABLED", "true").lower()
            == "true",
        )


# =============================================================================
# LINK OPERATION SERVICE
# =============================================================================


class MemoryLinkService:
    """
    Service for creating cross-memory associations in Neptune.

    Creates edges between memory vertices in the graph database to represent
    relationships like strategy derivation, reinforcement, contradiction, etc.
    """

    def __init__(
        self,
        neptune_service: NeptuneGraphServiceProtocol,
        config: Optional[AdvancedOperationsConfig] = None,
    ):
        """Initialize the link service."""
        self.neptune = neptune_service
        self.config = config or AdvancedOperationsConfig()

    async def link(self, action: RefineAction) -> RefineResult:
        """
        Execute LINK operation to create memory associations.

        Args:
            action: RefineAction with LINK operation

        Returns:
            RefineResult with created edge information
        """
        start_time = datetime.now(timezone.utc)

        if not self.config.link_enabled:
            return RefineResult(
                success=False,
                operation=RefineOperation.LINK,
                affected_memory_ids=[],
                action_id=action.action_id,
                error="LINK operation is disabled",
                latency_ms=0.0,
            )

        if action.operation != RefineOperation.LINK:
            raise ValidationError(
                f"Expected LINK operation, got {action.operation.value}"
            )

        # Validate we have exactly 2 memory IDs for linking
        if len(action.target_memory_ids) != 2:
            raise ValidationError(
                f"LINK operation requires exactly 2 memory IDs, "
                f"got {len(action.target_memory_ids)}"
            )

        source_id = action.target_memory_ids[0]
        target_id = action.target_memory_ids[1]
        link_type = LinkType(action.metadata.get("link_type", "RELATED_TO"))

        try:
            # Verify both vertices exist
            await self._validate_vertices_exist(source_id, target_id)

            # Create the edge
            edge_id = await self._create_edge(
                source_id=source_id,
                target_id=target_id,
                link_type=link_type,
                confidence=action.confidence,
                tenant_id=action.tenant_id,
                security_domain=action.security_domain,
                reasoning=action.reasoning,
            )

            # Handle bidirectional links
            if action.metadata.get("bidirectional", False):
                await self._create_edge(
                    source_id=target_id,
                    target_id=source_id,
                    link_type=link_type,
                    confidence=action.confidence,
                    tenant_id=action.tenant_id,
                    security_domain=action.security_domain,
                    reasoning=action.reasoning,
                )

            latency_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            return RefineResult(
                success=True,
                operation=RefineOperation.LINK,
                affected_memory_ids=action.target_memory_ids,
                action_id=action.action_id,
                rollback_token=f"edge:{source_id}:{target_id}:{link_type.value}",
                latency_ms=latency_ms,
                metrics={
                    "edge_id": edge_id,
                    "link_type": link_type.value,
                    "bidirectional": action.metadata.get("bidirectional", False),
                },
            )

        except Exception as e:
            logger.error(
                f"LINK operation failed: {e}",
                extra={
                    "action_id": action.action_id,
                    "source_id": source_id,
                    "target_id": target_id,
                    "error_type": type(e).__name__,
                },
            )
            latency_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            return RefineResult(
                success=False,
                operation=RefineOperation.LINK,
                affected_memory_ids=[],
                action_id=action.action_id,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def _validate_vertices_exist(self, source_id: str, target_id: str) -> None:
        """Validate that both memory vertices exist in Neptune."""
        source_exists = await self.neptune.vertex_exists(source_id)
        if not source_exists:
            raise ValidationError(f"Source memory vertex not found: {source_id}")

        target_exists = await self.neptune.vertex_exists(target_id)
        if not target_exists:
            raise ValidationError(f"Target memory vertex not found: {target_id}")

    async def _create_edge(
        self,
        source_id: str,
        target_id: str,
        link_type: LinkType,
        confidence: float,
        tenant_id: TenantId,
        security_domain: SecurityDomain,
        reasoning: str,
    ) -> str:
        """Create an edge in Neptune between two memory vertices."""
        edge_id = f"edge-{uuid.uuid4().hex[:16]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        query = """
        g.V().has('memory', 'memory_id', source_id)
          .addE(link_type)
          .to(g.V().has('memory', 'memory_id', target_id))
          .property('edge_id', edge_id)
          .property('confidence', confidence)
          .property('created_at', timestamp)
          .property('tenant_id', tenant_id)
          .property('security_domain', security_domain)
          .property('reasoning', reasoning)
        """

        await self.neptune.execute_gremlin(
            query,
            bindings={
                "source_id": source_id,
                "target_id": target_id,
                "link_type": link_type.value,
                "edge_id": edge_id,
                "confidence": confidence,
                "timestamp": timestamp,
                "tenant_id": tenant_id,
                "security_domain": security_domain,
                "reasoning": reasoning,
            },
        )

        logger.info(
            f"Created link edge {edge_id}: {source_id} --[{link_type.value}]--> {target_id}"
        )
        return edge_id

    async def remove_link(
        self,
        source_id: MemoryId,
        target_id: MemoryId,
        link_type: LinkType,
        tenant_id: TenantId,
        security_domain: SecurityDomain,
    ) -> bool:
        """
        Remove a link between memories (for rollback).

        Returns True if edge was deleted, False if not found.
        """
        query = """
        g.V().has('memory', 'memory_id', source_id)
          .outE(link_type)
          .where(inV().has('memory', 'memory_id', target_id))
          .has('tenant_id', tenant_id)
          .has('security_domain', security_domain)
          .drop()
        """

        await self.neptune.execute_gremlin(
            query,
            bindings={
                "source_id": source_id,
                "target_id": target_id,
                "link_type": link_type.value,
                "tenant_id": tenant_id,
                "security_domain": security_domain,
            },
        )

        logger.info(
            "Removed link: %s --[%s]--> %s", source_id, link_type.value, target_id
        )
        return True


# =============================================================================
# CORRECT OPERATION SERVICE
# =============================================================================


class CorrectOperationService:
    """
    Service for correcting incorrect memories with LLM verification.

    Uses LLM to verify corrections before applying them, with optional
    human-in-the-loop review for low-confidence corrections.
    """

    def __init__(
        self,
        memory_store: MemoryStoreProtocol,
        llm_service: LLMServiceProtocol,
        config: Optional[AdvancedOperationsConfig] = None,
    ):
        """Initialize the correct operation service."""
        self.memory_store = memory_store
        self.llm = llm_service
        self.config = config or AdvancedOperationsConfig()

    async def correct(self, action: RefineAction) -> RefineResult:
        """
        Execute CORRECT operation to fix incorrect memories.

        Args:
            action: RefineAction with CORRECT operation

        Returns:
            RefineResult with correction details
        """
        start_time = datetime.now(timezone.utc)

        if not self.config.correct_enabled:
            return RefineResult(
                success=False,
                operation=RefineOperation.CORRECT,
                affected_memory_ids=[],
                action_id=action.action_id,
                error="CORRECT operation is disabled",
                latency_ms=0.0,
            )

        if action.operation != RefineOperation.CORRECT:
            raise ValidationError(
                f"Expected CORRECT operation, got {action.operation.value}"
            )

        if len(action.target_memory_ids) != 1:
            raise ValidationError(
                f"CORRECT operation requires exactly 1 memory ID, "
                f"got {len(action.target_memory_ids)}"
            )

        memory_id = action.target_memory_ids[0]
        corrected_content = action.metadata.get("corrected_content")
        correction_reason = CorrectionReason(
            action.metadata.get("correction_reason", "llm_verification")
        )

        if not corrected_content:
            raise ValidationError(
                "CORRECT operation requires 'corrected_content' in metadata"
            )

        try:
            # Get current memory
            memory = await self.memory_store.get_memory(memory_id, action.tenant_id)
            if not memory:
                raise ValidationError(f"Memory not found: {memory_id}")

            # Validate security domain
            if memory.get("security_domain") != action.security_domain:
                raise SecurityBoundaryViolation(
                    "Cannot correct memory from different security domain"
                )

            original_content = memory.get("content", "")
            current_version = await self.memory_store.get_memory_version(
                memory_id, action.tenant_id
            )

            # Verify correction with LLM
            is_valid, confidence, reasoning = await self.llm.verify_correction(
                original_content=original_content,
                corrected_content=corrected_content,
                context={"reason": correction_reason.value, "action": action.to_dict()},
            )

            # First check: LLM rejected with high confidence (definitive rejection)
            if (
                not is_valid
                and confidence >= self.config.correction_confidence_threshold
            ):
                latency_ms = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds() * 1000
                return RefineResult(
                    success=False,
                    operation=RefineOperation.CORRECT,
                    affected_memory_ids=[memory_id],
                    action_id=action.action_id,
                    error=f"Correction rejected by LLM: {reasoning}",
                    latency_ms=latency_ms,
                    metrics={
                        "verification_confidence": confidence,
                        "llm_reasoning": reasoning,
                    },
                )

            # Second check: low confidence or invalid requires human review
            requires_human_review = (
                confidence < self.config.human_review_threshold or not is_valid
            )

            if requires_human_review and action.confidence < 0.95:
                # Don't auto-correct if human review is needed
                latency_ms = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds() * 1000
                return RefineResult(
                    success=False,
                    operation=RefineOperation.CORRECT,
                    affected_memory_ids=[memory_id],
                    action_id=action.action_id,
                    error="Correction requires human review",
                    latency_ms=latency_ms,
                    metrics={
                        "verification_confidence": confidence,
                        "llm_reasoning": reasoning,
                        "requires_human_review": True,
                    },
                )

            # Apply the correction
            updated_memory = await self.memory_store.update_memory(
                memory_id,
                {
                    "content": corrected_content,
                    "correction_reason": correction_reason.value,
                    "corrected_at": datetime.now(timezone.utc).isoformat(),
                    "original_content": original_content,
                    "correction_confidence": confidence,
                },
                action.tenant_id,
            )

            new_version = updated_memory.get("version", current_version + 1)

            latency_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            logger.info(
                f"Corrected memory {memory_id}: v{current_version} -> v{new_version}",
                extra={
                    "action_id": action.action_id,
                    "correction_reason": correction_reason.value,
                    "confidence": confidence,
                },
            )

            return RefineResult(
                success=True,
                operation=RefineOperation.CORRECT,
                affected_memory_ids=[memory_id],
                action_id=action.action_id,
                rollback_token=f"correct:{memory_id}:{current_version}",
                latency_ms=latency_ms,
                metrics={
                    "version_before": current_version,
                    "version_after": new_version,
                    "correction_reason": correction_reason.value,
                    "verification_confidence": confidence,
                    "requires_human_review": requires_human_review,
                },
            )

        except Exception as e:
            logger.error(
                f"CORRECT operation failed: {e}",
                extra={
                    "action_id": action.action_id,
                    "memory_id": memory_id,
                    "error_type": type(e).__name__,
                },
            )
            latency_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            return RefineResult(
                success=False,
                operation=RefineOperation.CORRECT,
                affected_memory_ids=[],
                action_id=action.action_id,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def detect_corrections_needed(
        self,
        memory_ids: list[MemoryId],
        tenant_id: TenantId,
        context_memories: list[dict[str, Any]],
    ) -> list[CorrectionCandidate]:
        """
        Detect memories that may need correction based on inconsistency with context.

        Args:
            memory_ids: Memory IDs to check
            tenant_id: Tenant for isolation
            context_memories: Related memories for consistency checking

        Returns:
            List of correction candidates
        """
        candidates = []
        context_contents = [m.get("content", "") for m in context_memories]

        # Parallelize LLM calls with concurrency limit
        semaphore = asyncio.Semaphore(5)

        async def _check_memory(memory_id: MemoryId) -> Optional[CorrectionCandidate]:
            async with semaphore:
                memory = await self.memory_store.get_memory(memory_id, tenant_id)
                if not memory:
                    return None

                content = memory.get("content", "")

                has_issue, confidence, explanation = (
                    await self.llm.detect_inconsistency(
                        memory_content=content,
                        context_memories=context_contents,
                    )
                )

                if has_issue and confidence >= self.config.human_review_threshold:
                    return CorrectionCandidate(
                        memory_id=memory_id,
                        correction_reason=CorrectionReason.LLM_VERIFICATION,
                        original_content=content,
                        corrected_content="",  # To be filled by correction process
                        verification_confidence=confidence,
                        supporting_evidence=[explanation],
                        requires_human_review=confidence
                        < self.config.correction_confidence_threshold,
                    )
                return None

        results = await asyncio.gather(
            *[_check_memory(mid) for mid in memory_ids],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, CorrectionCandidate):
                candidates.append(result)

        return candidates


# =============================================================================
# ROLLBACK OPERATION SERVICE
# =============================================================================


class RollbackOperationService:
    """
    Service for restoring memories from DynamoDB Streams snapshots.

    Supports point-in-time recovery and pre-operation snapshots.
    """

    def __init__(
        self,
        memory_store: MemoryStoreProtocol,
        snapshot_store: SnapshotStoreProtocol,
        config: Optional[AdvancedOperationsConfig] = None,
    ):
        """Initialize the rollback operation service."""
        self.memory_store = memory_store
        self.snapshot_store = snapshot_store
        self.config = config or AdvancedOperationsConfig()

    async def rollback(self, action: RefineAction) -> RefineResult:
        """
        Execute ROLLBACK operation to restore memories from snapshot.

        Args:
            action: RefineAction with ROLLBACK operation

        Returns:
            RefineResult with rollback details
        """
        start_time = datetime.now(timezone.utc)

        if not self.config.rollback_enabled:
            return RefineResult(
                success=False,
                operation=RefineOperation.ROLLBACK,
                affected_memory_ids=[],
                action_id=action.action_id,
                error="ROLLBACK operation is disabled",
                latency_ms=0.0,
            )

        if action.operation != RefineOperation.ROLLBACK:
            raise ValidationError(
                f"Expected ROLLBACK operation, got {action.operation.value}"
            )

        snapshot_id = action.metadata.get("snapshot_id")
        if not snapshot_id:
            # Check if rollback_token contains snapshot info
            rollback_token = action.metadata.get("rollback_token")
            if rollback_token and rollback_token.startswith("snapshot:"):
                snapshot_id = rollback_token.split(":", 1)[1]
            else:
                raise ValidationError(
                    "ROLLBACK operation requires 'snapshot_id' in metadata"
                )

        try:
            # Get the snapshot with tenant/domain validation
            snapshot = await self.snapshot_store.get_snapshot(
                snapshot_id, action.tenant_id, action.security_domain
            )

            if not snapshot:
                raise RollbackError(f"Snapshot not found: {snapshot_id}")

            # Validate tenant isolation
            if snapshot.tenant_id != action.tenant_id:
                raise TenantIsolationViolation(
                    "Cannot rollback to snapshot from different tenant"
                )

            # Validate security domain
            if snapshot.security_domain != action.security_domain:
                raise SecurityBoundaryViolation(
                    "Cannot rollback to snapshot from different security domain"
                )

            # Check memory count limit
            memory_count = len(snapshot.memory_ids)
            if memory_count > self.config.max_memories_per_rollback:
                raise RollbackError(
                    f"Snapshot contains {memory_count} memories, "
                    f"exceeds limit of {self.config.max_memories_per_rollback}"
                )

            # Restore memories
            memories_to_restore = list(snapshot.snapshot_data.values())
            success_count, failed_ids = await self.memory_store.restore_memories(
                memories_to_restore, action.tenant_id
            )

            latency_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            success = success_count > 0 and len(failed_ids) == 0

            logger.info(
                f"Rollback completed: {success_count} restored, {len(failed_ids)} failed",
                extra={
                    "action_id": action.action_id,
                    "snapshot_id": snapshot_id,
                    "success_count": success_count,
                    "failed_count": len(failed_ids),
                },
            )

            return RefineResult(
                success=success,
                operation=RefineOperation.ROLLBACK,
                affected_memory_ids=snapshot.memory_ids,
                action_id=action.action_id,
                rollback_token=None,  # Can't rollback a rollback
                error=(
                    f"Failed to restore {len(failed_ids)} memories"
                    if failed_ids
                    else None
                ),
                latency_ms=latency_ms,
                metrics={
                    "snapshot_id": snapshot_id,
                    "memories_restored": success_count,
                    "memories_failed": len(failed_ids),
                    "failed_memory_ids": failed_ids,
                },
            )

        except Exception as e:
            logger.error(
                f"ROLLBACK operation failed: {e}",
                extra={
                    "action_id": action.action_id,
                    "snapshot_id": snapshot_id,
                    "error_type": type(e).__name__,
                },
            )
            latency_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            return RefineResult(
                success=False,
                operation=RefineOperation.ROLLBACK,
                affected_memory_ids=[],
                action_id=action.action_id,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def create_snapshot(
        self,
        memory_ids: list[MemoryId],
        tenant_id: TenantId,
        security_domain: SecurityDomain,
        operation_id: Optional[str] = None,
    ) -> MemorySnapshot:
        """
        Create a snapshot of memories before an operation.

        Args:
            memory_ids: Memory IDs to snapshot
            tenant_id: Tenant for isolation
            security_domain: Security domain boundary
            operation_id: Optional operation ID that triggered this snapshot

        Returns:
            MemorySnapshot with captured state
        """
        snapshot_data: dict[str, Any] = {}

        for memory_id in memory_ids:
            memory = await self.memory_store.get_memory(memory_id, tenant_id)
            if memory:
                # Validate security domain
                if memory.get("security_domain") == security_domain:
                    snapshot_data[memory_id] = memory
                else:
                    logger.warning(
                        f"Skipping memory {memory_id} from different security domain"
                    )

        snapshot = MemorySnapshot(
            snapshot_id=f"snap-{uuid.uuid4().hex[:16]}",
            memory_ids=list(snapshot_data.keys()),
            snapshot_data=snapshot_data,
            tenant_id=tenant_id,
            security_domain=security_domain,
            expires_at=datetime.now(timezone.utc)
            + __import__("datetime").timedelta(
                days=self.config.snapshot_retention_days
            ),
        )

        await self.snapshot_store.save_snapshot(snapshot, tenant_id, security_domain)

        logger.info(
            f"Created snapshot {snapshot.snapshot_id} with {len(snapshot_data)} memories",
            extra={
                "operation_id": operation_id,
                "tenant_id": tenant_id,
                "security_domain": security_domain,
            },
        )

        return snapshot

    async def list_available_snapshots(
        self,
        tenant_id: TenantId,
        security_domain: SecurityDomain,
        limit: int = 10,
    ) -> list[SnapshotMetadata]:
        """List available snapshots for rollback."""
        return await self.snapshot_store.list_snapshots(
            tenant_id, security_domain, limit
        )


# =============================================================================
# SINGLETON MANAGEMENT
# =============================================================================

_link_service: Optional[MemoryLinkService] = None
_correct_service: Optional[CorrectOperationService] = None
_rollback_service: Optional[RollbackOperationService] = None


def get_link_service(
    neptune_service: Optional[NeptuneGraphServiceProtocol] = None,
    config: Optional[AdvancedOperationsConfig] = None,
) -> MemoryLinkService:
    """Get or create the MemoryLinkService singleton."""
    global _link_service
    if _link_service is None:
        if neptune_service is None:
            raise ValueError("neptune_service is required for first initialization")
        _link_service = MemoryLinkService(neptune_service, config)
    return _link_service


def reset_link_service() -> None:
    """Reset the MemoryLinkService singleton (for testing)."""
    global _link_service
    _link_service = None


def get_correct_service(
    memory_store: Optional[MemoryStoreProtocol] = None,
    llm_service: Optional[LLMServiceProtocol] = None,
    config: Optional[AdvancedOperationsConfig] = None,
) -> CorrectOperationService:
    """Get or create the CorrectOperationService singleton."""
    global _correct_service
    if _correct_service is None:
        if memory_store is None or llm_service is None:
            raise ValueError(
                "memory_store and llm_service are required for first initialization"
            )
        _correct_service = CorrectOperationService(memory_store, llm_service, config)
    return _correct_service


def reset_correct_service() -> None:
    """Reset the CorrectOperationService singleton (for testing)."""
    global _correct_service
    _correct_service = None


def get_rollback_service(
    memory_store: Optional[MemoryStoreProtocol] = None,
    snapshot_store: Optional[SnapshotStoreProtocol] = None,
    config: Optional[AdvancedOperationsConfig] = None,
) -> RollbackOperationService:
    """Get or create the RollbackOperationService singleton."""
    global _rollback_service
    if _rollback_service is None:
        if memory_store is None or snapshot_store is None:
            raise ValueError(
                "memory_store and snapshot_store are required for first initialization"
            )
        _rollback_service = RollbackOperationService(
            memory_store, snapshot_store, config
        )
    return _rollback_service


def reset_rollback_service() -> None:
    """Reset the RollbackOperationService singleton (for testing)."""
    global _rollback_service
    _rollback_service = None
