"""
Project Aura - Agent Orchestrator Integration for Memory Evolution (ADR-080)

Integrates the ReMem Action Framework with the Agent Orchestrator,
enabling agents to perform memory refinement as part of their action loop.

Integration Points:
1. AgentOrchestrator: Adds Refine step after Observe
2. Feature Flags: Controls which operations are enabled
3. Async Routing: Routes low-confidence operations to SQS

Usage:
    from src.services.memory_evolution.refine_integration import (
        RefineActionRouter,
        get_refine_router,
    )

    # In AgentOrchestrator
    router = get_refine_router(
        memory_refiner=refiner,
        titan_integration=titan_integration,
    )

    # After Observe step
    if should_refine(observation):
        action = create_refine_action(observation)
        result = await router.route_action(action, outcome)
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from .config import MemoryEvolutionConfig, get_memory_evolution_config
from .contracts import RefineAction, RefineOperation, RefineResult
from .exceptions import FeatureDisabledError, QueueError
from .memory_refiner import MemoryRefiner
from .titan_integration import TaskOutcome, TitanRefineIntegration

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOLS
# =============================================================================


class SQSClientProtocol(Protocol):
    """Protocol for SQS client operations."""

    async def send_message(
        self,
        QueueUrl: str,
        MessageBody: str,
        MessageAttributes: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Send a message to SQS queue."""
        ...


class MetricsPublisherProtocol(Protocol):
    """Protocol for metrics publishing."""

    async def publish_routing_decision(
        self,
        operation: RefineOperation,
        route: str,  # "sync" or "async"
        confidence: float,
        latency_ms: float,
    ) -> None:
        """Publish routing decision metrics."""
        ...


# =============================================================================
# REFINE DECISION LOGIC
# =============================================================================


@dataclass
class RefineDecision:
    """Decision about whether and how to refine."""

    should_refine: bool
    operation: Optional[RefineOperation] = None
    target_memory_ids: list[str] = None  # type: ignore
    reasoning: str = ""
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if self.target_memory_ids is None:
            self.target_memory_ids = []


class RefineDecisionMaker:
    """
    Makes decisions about when to trigger refine operations.

    Decision factors:
    1. Task success/failure pattern
    2. Memory similarity scores
    3. Memory access patterns
    4. Time since last refinement
    """

    def __init__(self, config: Optional[MemoryEvolutionConfig] = None):
        self.config = config or get_memory_evolution_config()
        self._last_refine_time: dict[str, datetime] = {}
        self._consecutive_successes: dict[str, int] = {}
        self._consecutive_failures: dict[str, int] = {}

    def decide(
        self,
        agent_id: str,
        task_outcome: TaskOutcome,
        recent_memories: list[dict[str, Any]],
    ) -> RefineDecision:
        """
        Decide whether to trigger a refine operation.

        Args:
            agent_id: Agent making the decision
            task_outcome: Outcome of the current task
            recent_memories: Recent memories accessed by the agent

        Returns:
            RefineDecision with recommendation
        """
        # Track consecutive outcomes
        if task_outcome.success:
            self._consecutive_successes[agent_id] = (
                self._consecutive_successes.get(agent_id, 0) + 1
            )
            self._consecutive_failures[agent_id] = 0
        else:
            self._consecutive_failures[agent_id] = (
                self._consecutive_failures.get(agent_id, 0) + 1
            )
            self._consecutive_successes[agent_id] = 0

        # Check for REINFORCE trigger (3+ consecutive successes)
        if self._consecutive_successes.get(agent_id, 0) >= 3:
            memory_ids = self._get_recent_memory_ids(recent_memories)
            if memory_ids and self.config.features.reinforce_enabled:
                return RefineDecision(
                    should_refine=True,
                    operation=RefineOperation.REINFORCE,
                    target_memory_ids=memory_ids,
                    reasoning="3+ consecutive successes - reinforce successful pattern",
                    confidence=min(0.95, 0.7 + task_outcome.quality_score * 0.25),
                )

        # Check for CONSOLIDATE trigger (similar memories detected)
        similar_pairs = self._find_similar_memories(recent_memories)
        if similar_pairs and self.config.features.consolidate_enabled:
            # Flatten pairs to unique IDs
            memory_ids = list({mid for pair in similar_pairs for mid in pair})
            return RefineDecision(
                should_refine=True,
                operation=RefineOperation.CONSOLIDATE,
                target_memory_ids=memory_ids[:10],  # Limit batch size
                reasoning=f"Found {len(similar_pairs)} similar memory pairs",
                confidence=0.85,
            )

        # Check for PRUNE trigger (stale memories)
        stale_memories = self._find_stale_memories(recent_memories)
        if stale_memories and self.config.features.prune_enabled:
            return RefineDecision(
                should_refine=True,
                operation=RefineOperation.PRUNE,
                target_memory_ids=[m["memory_id"] for m in stale_memories],
                reasoning=f"Found {len(stale_memories)} stale memories",
                confidence=0.80,
            )

        return RefineDecision(
            should_refine=False,
            reasoning="No refine conditions met",
        )

    def _get_recent_memory_ids(
        self,
        memories: list[dict[str, Any]],
        limit: int = 5,
    ) -> list[str]:
        """Extract memory IDs from recent memories."""
        return [m.get("memory_id", "") for m in memories[:limit] if m.get("memory_id")]

    def _find_similar_memories(
        self,
        memories: list[dict[str, Any]],
    ) -> list[tuple[str, str]]:
        """Find pairs of similar memories (placeholder - real impl uses embeddings)."""
        # In production, this would compute similarity scores
        # For now, return empty (no similar pairs detected)
        return []

    def _find_stale_memories(
        self,
        memories: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Find stale memories that haven't been accessed recently."""
        stale = []
        for m in memories:
            access_count = m.get("access_count", 0)
            age_days = m.get("age_days", 0)
            if access_count == 0 and age_days > self.config.prune.min_age_days:
                stale.append(m)
        return stale

    def reset_agent_state(self, agent_id: str) -> None:
        """Reset tracking state for an agent."""
        self._consecutive_successes.pop(agent_id, None)
        self._consecutive_failures.pop(agent_id, None)
        self._last_refine_time.pop(agent_id, None)


# =============================================================================
# REFINE ACTION ROUTER
# =============================================================================


class RefineActionRouter:
    """
    Routes refine actions to sync or async execution.

    Routing logic:
    - confidence >= sync_threshold: Execute synchronously
    - confidence < sync_threshold: Queue for async execution

    This prevents low-confidence operations from blocking the agent loop.
    """

    def __init__(
        self,
        memory_refiner: MemoryRefiner,
        titan_integration: Optional[TitanRefineIntegration] = None,
        sqs_client: Optional[SQSClientProtocol] = None,
        metrics_publisher: Optional[MetricsPublisherProtocol] = None,
        config: Optional[MemoryEvolutionConfig] = None,
    ):
        """
        Initialize router.

        Args:
            memory_refiner: Memory refiner for CONSOLIDATE/PRUNE
            titan_integration: Titan integration for REINFORCE
            sqs_client: SQS client for async routing
            metrics_publisher: Metrics publisher
            config: Configuration
        """
        self.memory_refiner = memory_refiner
        self.titan_integration = titan_integration
        self.sqs_client = sqs_client
        self.metrics_publisher = metrics_publisher
        self.config = config or get_memory_evolution_config()

    async def route_action(
        self,
        action: RefineAction,
        outcome: Optional[TaskOutcome] = None,
    ) -> RefineResult:
        """
        Route a refine action to appropriate execution path.

        Args:
            action: The refine action to execute
            outcome: Task outcome (required for REINFORCE)

        Returns:
            RefineResult from execution or queue acknowledgment
        """
        start_time = time.time()

        # Determine routing
        if action.confidence >= self.config.async_config.sync_confidence_threshold:
            route = "sync"
            result = await self._execute_sync(action, outcome)
        else:
            if self.config.async_config.async_enabled and self.sqs_client:
                route = "async"
                result = await self._queue_async(action, outcome)
            else:
                # Fall back to sync if async not available
                route = "sync"
                result = await self._execute_sync(action, outcome)

        latency_ms = (time.time() - start_time) * 1000

        # Publish routing metrics
        if self.metrics_publisher:
            try:
                await self.metrics_publisher.publish_routing_decision(
                    operation=action.operation,
                    route=route,
                    confidence=action.confidence,
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.warning(f"Failed to publish routing metrics: {e}")

        return result

    async def _execute_sync(
        self,
        action: RefineAction,
        outcome: Optional[TaskOutcome],
    ) -> RefineResult:
        """Execute action synchronously."""
        if action.operation == RefineOperation.REINFORCE:
            if self.titan_integration is None:
                raise FeatureDisabledError(
                    "reinforce",
                    "1b",
                )
            if outcome is None:
                raise ValueError("TaskOutcome required for REINFORCE operation")
            return await self.titan_integration.reinforce_pattern(action, outcome)
        else:
            # CONSOLIDATE, PRUNE handled by memory_refiner
            return await self.memory_refiner.refine(action)

    async def _queue_async(
        self,
        action: RefineAction,
        outcome: Optional[TaskOutcome],
    ) -> RefineResult:
        """Queue action for async execution."""
        if self.sqs_client is None:
            raise QueueError("SQS client not configured for async operations")

        try:
            message_body = {
                "action": action.to_dict(),
                "outcome": outcome.to_dict() if outcome else None,
                "queued_at": datetime.now(timezone.utc).isoformat(),
            }

            queue_url = self.config.queue_url_pattern.format(
                account_id="self"  # Will be resolved by the worker
            )

            await self.sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes={
                    "Operation": {
                        "DataType": "String",
                        "StringValue": action.operation.value,
                    },
                    "TenantId": {
                        "DataType": "String",
                        "StringValue": action.tenant_id,
                    },
                },
            )

            logger.info(
                f"Queued {action.operation.value} for async execution "
                f"(confidence={action.confidence:.2f})"
            )

            return RefineResult(
                success=True,
                operation=action.operation,
                affected_memory_ids=[],  # Will be populated by worker
                action_id=action.action_id,
                metrics={"route": "async", "queued": True},
            )

        except Exception as e:
            raise QueueError(
                f"Failed to queue action: {e}",
                queue_url=self.config.queue_url_pattern,
                aws_error=str(e),
            ) from e

    def is_operation_enabled(self, operation: RefineOperation) -> bool:
        """Check if an operation is enabled."""
        enabled_map = {
            RefineOperation.CONSOLIDATE: self.config.features.consolidate_enabled,
            RefineOperation.PRUNE: self.config.features.prune_enabled,
            RefineOperation.REINFORCE: self.config.features.reinforce_enabled,
            RefineOperation.ABSTRACT: self.config.features.abstract_enabled,
            RefineOperation.LINK: self.config.features.link_enabled,
            RefineOperation.CORRECT: self.config.features.correct_enabled,
            RefineOperation.ROLLBACK: self.config.features.rollback_enabled,
        }
        return enabled_map.get(operation, False)


# =============================================================================
# SINGLETON MANAGEMENT
# =============================================================================

_router_instance: Optional[RefineActionRouter] = None
_decision_maker_instance: Optional[RefineDecisionMaker] = None


def get_refine_router(
    memory_refiner: Optional[MemoryRefiner] = None,
    titan_integration: Optional[TitanRefineIntegration] = None,
    sqs_client: Optional[SQSClientProtocol] = None,
    metrics_publisher: Optional[MetricsPublisherProtocol] = None,
    config: Optional[MemoryEvolutionConfig] = None,
) -> RefineActionRouter:
    """Get or create the singleton RefineActionRouter instance."""
    global _router_instance
    if _router_instance is None:
        if memory_refiner is None:
            raise ValueError("memory_refiner is required for initial creation")
        _router_instance = RefineActionRouter(
            memory_refiner=memory_refiner,
            titan_integration=titan_integration,
            sqs_client=sqs_client,
            metrics_publisher=metrics_publisher,
            config=config,
        )
    return _router_instance


def get_refine_decision_maker(
    config: Optional[MemoryEvolutionConfig] = None,
) -> RefineDecisionMaker:
    """Get or create the singleton RefineDecisionMaker instance."""
    global _decision_maker_instance
    if _decision_maker_instance is None:
        _decision_maker_instance = RefineDecisionMaker(config=config)
    return _decision_maker_instance


def reset_refine_router() -> None:
    """Reset the router singleton instance (for testing)."""
    global _router_instance
    _router_instance = None


def reset_refine_decision_maker() -> None:
    """Reset the decision maker singleton instance (for testing)."""
    global _decision_maker_instance
    _decision_maker_instance = None
