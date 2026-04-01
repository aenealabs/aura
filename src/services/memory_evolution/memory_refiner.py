"""
Project Aura - Memory Refiner Service (ADR-080)

Core service implementing ReMem Action Framework refine operations.
Phase 1a implements CONSOLIDATE and PRUNE operations.

Architecture:
- MemoryRefiner: Orchestrates refine operations
- ConsolidationStrategy: Merges similar memories
- PruneStrategy: Removes low-value memories

Integration:
- CognitiveMemoryService: Memory CRUD operations
- DynamoDB: Evolution record storage
- CloudWatch: Metrics publishing
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Protocol
from uuid import uuid4

from .config import MemoryEvolutionConfig, get_memory_evolution_config
from .contracts import (
    ConsolidationCandidate,
    EvolutionRecord,
    OperationPhase,
    PruneCandidate,
    RefineAction,
    RefineOperation,
    RefineResult,
    SimilarityMetric,
)
from .exceptions import (
    CircuitBreakerOpen,
    ConsolidationError,
    FeatureDisabledError,
    PruneError,
    SecurityBoundaryViolation,
    TenantIsolationViolation,
    ValidationError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOLS
# =============================================================================


class MemoryStore(Protocol):
    """Protocol for memory storage operations."""

    async def get_memory(self, memory_id: str) -> dict[str, Any]:
        """Get a memory by ID."""
        ...

    async def get_memories(
        self, memory_ids: list[str], tenant_id: str, security_domain: str
    ) -> list[dict[str, Any]]:
        """Get multiple memories by IDs with security filtering."""
        ...

    async def merge_memories(
        self, memory_ids: list[str], merge_strategy: str, tenant_id: str
    ) -> dict[str, Any]:
        """Merge multiple memories into one."""
        ...

    async def soft_delete_memory(
        self, memory_id: str, tenant_id: str, reason: str
    ) -> bool:
        """Soft delete a memory (mark for later permanent deletion)."""
        ...

    async def get_memory_similarity(self, memory_id_a: str, memory_id_b: str) -> float:
        """Get cosine similarity between two memory embeddings."""
        ...

    async def find_similar_memories(
        self, tenant_id: str, security_domain: str, threshold: float
    ) -> list[tuple[str, str, float]]:
        """Find pairs of memories above similarity threshold."""
        ...

    async def get_prune_candidates(
        self, tenant_id: str, security_domain: str, min_age_days: int
    ) -> list[dict[str, Any]]:
        """Get memories that are candidates for pruning."""
        ...


class EvolutionRecordStore(Protocol):
    """Protocol for evolution record storage."""

    async def save_record(self, record: EvolutionRecord) -> None:
        """Save an evolution record to DynamoDB."""
        ...

    async def get_recent_records(
        self, agent_id: str, limit: int = 100
    ) -> list[EvolutionRecord]:
        """Get recent evolution records for an agent."""
        ...


class MetricsPublisher(Protocol):
    """Protocol for metrics publishing."""

    async def publish_refine_result(
        self,
        operation: RefineOperation,
        success: bool,
        latency_ms: float,
        dimensions: dict[str, str],
    ) -> None:
        """Publish refine operation metrics."""
        ...


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================


@dataclass
class CircuitBreakerState:
    """State tracking for circuit breaker pattern."""

    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    is_open: bool = False
    cooldown_until: Optional[datetime] = None

    def record_failure(self, cooldown_seconds: int = 60) -> None:
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        # Open circuit after 3 consecutive failures
        if self.failure_count >= 3:
            self.is_open = True
            self.cooldown_until = datetime.now(timezone.utc) + timedelta(
                seconds=cooldown_seconds
            )

    def record_success(self) -> None:
        """Record a success and reset the circuit."""
        self.failure_count = 0
        self.is_open = False
        self.cooldown_until = None

    def check_open(self) -> bool:
        """Check if circuit is open, auto-close after cooldown."""
        if not self.is_open:
            return False

        if self.cooldown_until and datetime.now(timezone.utc) >= self.cooldown_until:
            # Half-open: allow one request through
            self.is_open = False
            self.failure_count = 2  # Quick re-open on next failure
            return False

        return True


# =============================================================================
# MEMORY REFINER SERVICE
# =============================================================================


class MemoryRefiner:
    """
    Core service for memory refinement operations.

    Implements the ReMem Action Framework with:
    - CONSOLIDATE: Merge similar memories
    - PRUNE: Remove low-value memories

    Security:
    - Enforces tenant isolation on all operations
    - Enforces security domain boundaries
    - Creates audit trail via EvolutionRecord
    """

    def __init__(
        self,
        memory_store: MemoryStore,
        record_store: Optional[EvolutionRecordStore] = None,
        metrics_publisher: Optional[MetricsPublisher] = None,
        config: Optional[MemoryEvolutionConfig] = None,
    ) -> None:
        """
        Initialize the memory refiner.

        Args:
            memory_store: Storage for memory operations
            record_store: Optional storage for evolution records
            metrics_publisher: Optional metrics publisher
            config: Configuration (uses default if not provided)
        """
        self.memory_store = memory_store
        self.record_store = record_store
        self.metrics_publisher = metrics_publisher
        self.config = config or get_memory_evolution_config()

        # Circuit breakers per operation type
        self._circuit_breakers: dict[RefineOperation, CircuitBreakerState] = {
            RefineOperation.CONSOLIDATE: CircuitBreakerState(),
            RefineOperation.PRUNE: CircuitBreakerState(),
        }

    async def refine(self, action: RefineAction) -> RefineResult:
        """
        Execute a refine operation.

        Args:
            action: The refine action to execute

        Returns:
            RefineResult with operation outcome

        Raises:
            FeatureDisabledError: If operation is disabled
            SecurityBoundaryViolation: If action crosses security boundary
            TenantIsolationViolation: If action crosses tenant boundary
            CircuitBreakerOpen: If operation circuit breaker is open
        """
        start_time = time.time()
        action_id = action.action_id or str(uuid4())
        action.action_id = action_id

        try:
            # Validate operation is enabled
            self._validate_operation_enabled(action.operation)

            # Check circuit breaker
            self._check_circuit_breaker(action.operation)

            # Validate security constraints
            await self._validate_security(action)

            # Route to appropriate handler
            if action.operation == RefineOperation.CONSOLIDATE:
                result = await self._execute_consolidate(action)
            elif action.operation == RefineOperation.PRUNE:
                result = await self._execute_prune(action)
            else:
                raise FeatureDisabledError(
                    action.operation.value,
                    OperationPhase.get_phase(action.operation).value,
                )

            # Record success
            self._circuit_breakers[action.operation].record_success()

            # Calculate latency
            result.latency_ms = (time.time() - start_time) * 1000
            result.action_id = action_id

            # Save evolution record
            await self._save_evolution_record(action, result)

            # Publish metrics
            await self._publish_metrics(action, result)

            return result

        except Exception as e:
            # Record failure
            if action.operation in self._circuit_breakers:
                self._circuit_breakers[action.operation].record_failure()

            latency_ms = (time.time() - start_time) * 1000

            # Create failure result
            result = RefineResult(
                success=False,
                operation=action.operation,
                affected_memory_ids=[],
                action_id=action_id,
                error=str(e),
                latency_ms=latency_ms,
            )

            # Save evolution record for failures too
            await self._save_evolution_record(action, result)

            # Publish failure metrics
            await self._publish_metrics(action, result)

            # Re-raise for caller handling
            raise

    def _validate_operation_enabled(self, operation: RefineOperation) -> None:
        """Validate that the operation is enabled in feature flags."""
        enabled_map = {
            RefineOperation.CONSOLIDATE: self.config.features.consolidate_enabled,
            RefineOperation.PRUNE: self.config.features.prune_enabled,
            RefineOperation.REINFORCE: self.config.features.reinforce_enabled,
            RefineOperation.ABSTRACT: self.config.features.abstract_enabled,
            RefineOperation.LINK: self.config.features.link_enabled,
            RefineOperation.CORRECT: self.config.features.correct_enabled,
            RefineOperation.ROLLBACK: self.config.features.rollback_enabled,
        }

        if not enabled_map.get(operation, False):
            phase = OperationPhase.get_phase(operation)
            raise FeatureDisabledError(operation.value, phase.value)

    def _check_circuit_breaker(self, operation: RefineOperation) -> None:
        """Check if circuit breaker is open for operation."""
        if operation not in self._circuit_breakers:
            return

        breaker = self._circuit_breakers[operation]
        if breaker.check_open():
            cooldown_remaining = 0.0
            if breaker.cooldown_until:
                cooldown_remaining = (
                    breaker.cooldown_until - datetime.now(timezone.utc)
                ).total_seconds()

            raise CircuitBreakerOpen(
                f"Circuit breaker open for {operation.value}",
                operation.value,
                breaker.failure_count,
                max(0.0, cooldown_remaining),
            )

    async def _validate_security(self, action: RefineAction) -> None:
        """Validate security constraints for the action."""
        # Validate tenant isolation
        if self.config.security.require_tenant_isolation:
            if not action.tenant_id:
                raise TenantIsolationViolation(
                    "tenant_id is required for all operations"
                )

        # Validate security domain boundary
        if self.config.security.require_domain_boundary:
            if not action.security_domain:
                raise SecurityBoundaryViolation(
                    "security_domain is required for all operations"
                )

        # Validate target memories are accessible
        memories = await self.memory_store.get_memories(
            action.target_memory_ids, action.tenant_id, action.security_domain
        )

        if len(memories) != len(action.target_memory_ids):
            accessible_ids = {m.get("memory_id") for m in memories}
            inaccessible = [
                mid for mid in action.target_memory_ids if mid not in accessible_ids
            ]
            raise SecurityBoundaryViolation(
                f"Cannot access memories: {inaccessible}",
                expected_domain=action.security_domain,
                tenant_id=action.tenant_id,
            )

    async def _execute_consolidate(self, action: RefineAction) -> RefineResult:
        """Execute CONSOLIDATE operation."""
        logger.info(
            f"Executing CONSOLIDATE for {len(action.target_memory_ids)} memories"
        )

        if len(action.target_memory_ids) < 2:
            raise ConsolidationError(
                "CONSOLIDATE requires at least 2 memory IDs",
                memory_ids=action.target_memory_ids,
            )

        if len(action.target_memory_ids) > self.config.consolidation.max_batch_size:
            raise ConsolidationError(
                f"CONSOLIDATE batch size exceeds maximum of {self.config.consolidation.max_batch_size}",
                memory_ids=action.target_memory_ids,
            )

        # Validate confidence threshold
        if action.confidence < self.config.consolidation.min_confidence:
            raise ValidationError(
                f"Confidence {action.confidence} below minimum {self.config.consolidation.min_confidence}",
                field="confidence",
                value=action.confidence,
            )

        # Get merge strategy from action metadata or use default
        merge_strategy = action.metadata.get(
            "merge_strategy", self.config.consolidation.default_merge_strategy
        )

        # Execute merge
        merged_memory = await self.memory_store.merge_memories(
            action.target_memory_ids, merge_strategy, action.tenant_id
        )

        merged_id = merged_memory.get("memory_id", "unknown")
        logger.info(
            f"Consolidated {len(action.target_memory_ids)} memories into {merged_id}"
        )

        return RefineResult(
            success=True,
            operation=RefineOperation.CONSOLIDATE,
            affected_memory_ids=[merged_id],
            rollback_token=str(uuid4()),  # For potential rollback
            metrics={
                "merged_count": len(action.target_memory_ids),
                "merge_strategy": merge_strategy,
            },
        )

    async def _execute_prune(self, action: RefineAction) -> RefineResult:
        """Execute PRUNE operation."""
        logger.info(f"Executing PRUNE for {len(action.target_memory_ids)} memories")

        if len(action.target_memory_ids) > self.config.prune.max_batch_size:
            raise PruneError(
                f"PRUNE batch size exceeds maximum of {self.config.prune.max_batch_size}",
                memory_ids=action.target_memory_ids,
            )

        # Soft delete each memory
        pruned_ids: list[str] = []
        for memory_id in action.target_memory_ids:
            success = await self.memory_store.soft_delete_memory(
                memory_id, action.tenant_id, action.reasoning
            )
            if success:
                pruned_ids.append(memory_id)

        logger.info(
            f"Pruned {len(pruned_ids)} of {len(action.target_memory_ids)} memories"
        )

        return RefineResult(
            success=True,
            operation=RefineOperation.PRUNE,
            affected_memory_ids=pruned_ids,
            rollback_token=str(uuid4()),  # For potential rollback
            metrics={
                "requested_count": len(action.target_memory_ids),
                "pruned_count": len(pruned_ids),
            },
        )

    async def _save_evolution_record(
        self, action: RefineAction, result: RefineResult
    ) -> None:
        """Save evolution record to DynamoDB."""
        if not self.record_store:
            return

        try:
            record = EvolutionRecord(
                record_id=str(uuid4()),
                operation=action.operation,
                agent_id=action.agent_id or "system",
                tenant_id=action.tenant_id,
                security_domain=action.security_domain,
                action=action,
                result=result,
                task_id=action.metadata.get("task_id"),
                task_sequence_number=action.metadata.get("task_sequence_number", 0),
            )
            await self.record_store.save_record(record)
        except Exception as e:
            logger.warning(f"Failed to save evolution record: {e}")

    async def _publish_metrics(
        self, action: RefineAction, result: RefineResult
    ) -> None:
        """Publish metrics to CloudWatch."""
        if not self.metrics_publisher or not self.config.metrics.enabled:
            return

        try:
            dimensions = {
                "Environment": self.config.environment,
                "Operation": action.operation.value,
                "TenantId": action.tenant_id,
            }
            await self.metrics_publisher.publish_refine_result(
                action.operation, result.success, result.latency_ms, dimensions
            )
        except Exception as e:
            logger.warning(f"Failed to publish metrics: {e}")

    # =========================================================================
    # DISCOVERY METHODS
    # =========================================================================

    async def find_consolidation_candidates(
        self, tenant_id: str, security_domain: str
    ) -> list[ConsolidationCandidate]:
        """
        Find memory pairs that are candidates for consolidation.

        Args:
            tenant_id: Tenant ID for isolation
            security_domain: Security domain boundary

        Returns:
            List of consolidation candidates above similarity threshold
        """
        if not self.config.consolidation.auto_discovery_enabled:
            return []

        similar_pairs = await self.memory_store.find_similar_memories(
            tenant_id, security_domain, self.config.consolidation.similarity_threshold
        )

        candidates = [
            ConsolidationCandidate(
                memory_id_a=pair[0],
                memory_id_b=pair[1],
                similarity_score=pair[2],
                similarity_metric=SimilarityMetric.COSINE,
                merge_strategy=self.config.consolidation.default_merge_strategy,
            )
            for pair in similar_pairs
        ]

        logger.info(f"Found {len(candidates)} consolidation candidates")
        return candidates

    async def find_prune_candidates(
        self, tenant_id: str, security_domain: str
    ) -> list[PruneCandidate]:
        """
        Find memories that are candidates for pruning.

        Args:
            tenant_id: Tenant ID for isolation
            security_domain: Security domain boundary

        Returns:
            List of prune candidates above score threshold
        """
        if not self.config.prune.auto_prune_enabled:
            return []

        raw_candidates = await self.memory_store.get_prune_candidates(
            tenant_id, security_domain, self.config.prune.min_age_days
        )

        candidates = []
        for raw in raw_candidates:
            # Calculate prune score based on multiple factors
            access_count = raw.get("access_count", 0)
            value_score = raw.get("value_score", 0.0)
            age_days = raw.get("age_days", 0)

            # Skip if protected by minimum access count
            if access_count >= self.config.prune.min_access_protection:
                continue

            # Calculate composite prune score
            # Higher score = more likely to prune
            prune_score = self._calculate_prune_score(
                access_count, value_score, age_days
            )

            if prune_score >= self.config.prune.prune_threshold:
                reasons = []
                if access_count == 0:
                    reasons.append("Never accessed")
                if value_score < 0.2:
                    reasons.append("Low historical value")
                if age_days > 30:
                    reasons.append("Older than 30 days")

                candidates.append(
                    PruneCandidate(
                        memory_id=raw["memory_id"],
                        prune_score=prune_score,
                        last_accessed=raw.get("last_accessed"),
                        access_count=access_count,
                        value_score=value_score,
                        age_days=age_days,
                        reasons=reasons,
                    )
                )

        logger.info(f"Found {len(candidates)} prune candidates")
        return candidates

    def _calculate_prune_score(
        self, access_count: int, value_score: float, age_days: int
    ) -> float:
        """
        Calculate composite prune score.

        Factors:
        - Access frequency (lower = higher prune score)
        - Historical value (lower = higher prune score)
        - Age (older = higher prune score)

        Returns:
            Score between 0.0 and 1.0
        """
        # Normalize access count (0 accesses = 1.0, 10+ = 0.0)
        access_factor = max(0.0, 1.0 - (access_count / 10.0))

        # Value factor (invert so low value = high prune score)
        value_factor = 1.0 - value_score

        # Age factor (older memories get higher score)
        age_factor = min(1.0, age_days / 90.0)

        # Weighted average
        prune_score = (access_factor * 0.4) + (value_factor * 0.4) + (age_factor * 0.2)

        return round(prune_score, 3)


# =============================================================================
# SINGLETON MANAGEMENT
# =============================================================================

_refiner_instance: Optional[MemoryRefiner] = None


def get_memory_refiner(
    memory_store: Optional[MemoryStore] = None,
    record_store: Optional[EvolutionRecordStore] = None,
    metrics_publisher: Optional[MetricsPublisher] = None,
    config: Optional[MemoryEvolutionConfig] = None,
) -> MemoryRefiner:
    """Get or create the singleton MemoryRefiner instance."""
    global _refiner_instance
    if _refiner_instance is None:
        if memory_store is None:
            raise ValueError("memory_store is required for initial creation")
        _refiner_instance = MemoryRefiner(
            memory_store=memory_store,
            record_store=record_store,
            metrics_publisher=metrics_publisher,
            config=config,
        )
    return _refiner_instance


def reset_memory_refiner() -> None:
    """Reset the singleton instance (for testing)."""
    global _refiner_instance
    _refiner_instance = None
