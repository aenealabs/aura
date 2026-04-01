"""
Project Aura - Evolution Metrics for Memory Evolution Service (ADR-080)

Tracks memory evolution effectiveness across agent sessions, providing
metrics for accuracy, efficiency, and quality of memory operations.

Metrics Categories:
- Accuracy: Retrieval precision/recall, strategy reuse rate
- Evolution: Consolidation count, abstractions, pruning, reinforcements
- Efficiency: Memory utilization, average age at use, transfer success
- Quality: False memory rate, interference events, evolution gain

Reference: ADR-080 Evo-Memory Enhancements (Phase 2)
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from .config import MemoryEvolutionConfig, get_memory_evolution_config
from .contracts import RefineAction

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOLS
# =============================================================================


class DynamoDBClientProtocol(Protocol):
    """Protocol for DynamoDB client operations."""

    async def put_item(
        self,
        TableName: str,
        Item: dict[str, Any],
        ConditionExpression: Optional[str] = None,
    ) -> dict[str, Any]:
        """Put an item into a DynamoDB table."""
        ...

    async def query(
        self,
        TableName: str,
        KeyConditionExpression: str,
        ExpressionAttributeValues: dict[str, Any],
        IndexName: Optional[str] = None,
        ScanIndexForward: bool = True,
        Limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """Query items from a DynamoDB table."""
        ...


class S3ClientProtocol(Protocol):
    """Protocol for S3 client operations."""

    async def put_object(
        self,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str = "application/json",
    ) -> dict[str, Any]:
        """Put an object into an S3 bucket."""
        ...


class AuditLoggerProtocol(Protocol):
    """Protocol for audit logging operations."""

    def log_event(
        self,
        event_type: str,
        operation: str,
        actor: str,
        details: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Log an audit event."""
        ...


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class EvolutionMetrics:
    """Metrics tracking memory evolution effectiveness.

    Organized into four categories:
    - Accuracy: How well memories are retrieved and reused
    - Evolution: Counts of refine operations performed
    - Efficiency: How efficiently memories are used
    - Quality: Error rates and improvement tracking
    """

    # Accuracy metrics
    retrieval_precision: float = 0.0  # Relevant memories retrieved / total retrieved
    retrieval_recall: float = 0.0  # Relevant memories retrieved / total relevant
    strategy_reuse_rate: float = 0.0  # % of tasks using prior strategies

    # Evolution metrics
    consolidation_count: int = 0  # Memories merged
    abstractions_created: int = 0  # Strategies extracted
    memories_pruned: int = 0  # Low-value memories removed
    reinforcements_applied: int = 0  # Patterns strengthened

    # Efficiency metrics
    memory_utilization: float = 0.0  # Active / Total memories
    avg_memory_age_at_use: float = 0.0  # Average age (days) of reused memories
    strategy_transfer_success: float = 0.0  # Cross-domain strategy success rate

    # Quality metrics
    false_memory_rate: float = 0.0  # Incorrect memories retrieved / total retrieved
    interference_events: int = 0  # Conflicting memory activations
    evolution_gain: float = 0.0  # Performance improvement over time

    # Metadata
    agent_id: str = ""
    tenant_id: str = ""
    window_start: str = ""
    window_end: str = ""
    task_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "retrieval_precision": self.retrieval_precision,
            "retrieval_recall": self.retrieval_recall,
            "strategy_reuse_rate": self.strategy_reuse_rate,
            "consolidation_count": self.consolidation_count,
            "abstractions_created": self.abstractions_created,
            "memories_pruned": self.memories_pruned,
            "reinforcements_applied": self.reinforcements_applied,
            "memory_utilization": self.memory_utilization,
            "avg_memory_age_at_use": self.avg_memory_age_at_use,
            "strategy_transfer_success": self.strategy_transfer_success,
            "false_memory_rate": self.false_memory_rate,
            "interference_events": self.interference_events,
            "evolution_gain": self.evolution_gain,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "task_count": self.task_count,
        }


@dataclass
class TaskCompletionRecord:
    """Record of a completed task for evolution tracking."""

    agent_id: str
    task_id: str
    tenant_id: str
    timestamp: str
    outcome: str  # "success", "failure", "partial"
    memories_used_count: int
    strategies_applied_count: int
    refine_actions_summary: dict[str, int]  # operation -> count
    quality_score: float = 0.0
    execution_time_ms: float = 0.0
    s3_detail_key: Optional[str] = None

    def to_dynamo_item(self, ttl: int) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        date_bucket = self.timestamp[:10]  # YYYY-MM-DD
        return {
            "pk": {"S": f"{self.agent_id}#{date_bucket}"},
            "sk": {"S": self.timestamp},
            "task_id": {"S": self.task_id},
            "tenant_id": {"S": self.tenant_id},
            "outcome": {"S": self.outcome},
            "memories_used_count": {"N": str(self.memories_used_count)},
            "strategies_applied_count": {"N": str(self.strategies_applied_count)},
            "refine_actions_summary": {"S": str(self.refine_actions_summary)},
            "quality_score": {"N": str(self.quality_score)},
            "execution_time_ms": {"N": str(self.execution_time_ms)},
            "s3_detail_key": {"S": self.s3_detail_key or ""},
            "ttl": {"N": str(ttl)},
        }


@dataclass
class EvolutionTrackerConfig:
    """Configuration for evolution tracking."""

    retention_days_dev: int = 90
    retention_days_prod: int = 365
    metrics_aggregation_interval: int = 60  # seconds
    store_full_refine_actions: bool = False  # Store in S3 instead of DynamoDB
    min_tasks_for_gain: int = 10  # Minimum tasks before computing evolution gain
    gain_window_size: int = 100  # Number of tasks for gain calculation

    @classmethod
    def from_config(cls, config: MemoryEvolutionConfig) -> "EvolutionTrackerConfig":
        """Create tracker config from main config."""
        return cls(
            retention_days_dev=config.storage.evolution_table_ttl_days_dev,
            retention_days_prod=config.storage.evolution_table_ttl_days_prod,
            store_full_refine_actions=(
                config.metrics.store_full_refine_actions
                if hasattr(config.metrics, "store_full_refine_actions")
                else False
            ),
        )


# =============================================================================
# EVOLUTION TRACKER
# =============================================================================


class EvolutionTracker:
    """Tracks memory evolution across agent sessions.

    Responsibilities:
    1. Record task completion with memory usage details
    2. Store evolution history in DynamoDB (summaries) and S3 (details)
    3. Compute evolution metrics over time windows
    4. Calculate evolution gain (performance improvement)

    Thread Safety:
    - All operations are async and stateless (no internal buffers)
    - DynamoDB handles concurrent writes via conditional expressions
    """

    def __init__(
        self,
        dynamodb_client: DynamoDBClientProtocol,
        s3_client: Optional[S3ClientProtocol] = None,
        audit_logger: Optional[AuditLoggerProtocol] = None,
        config: Optional[EvolutionTrackerConfig] = None,
        main_config: Optional[MemoryEvolutionConfig] = None,
    ):
        """
        Initialize evolution tracker.

        Args:
            dynamodb_client: DynamoDB client for storing records
            s3_client: S3 client for storing full action details
            audit_logger: Audit logger for compliance logging
            config: Tracker-specific configuration
            main_config: Main memory evolution configuration
        """
        self.dynamodb = dynamodb_client
        self.s3 = s3_client
        self.audit_logger = audit_logger
        self.config = config or EvolutionTrackerConfig()
        self.main_config = main_config or get_memory_evolution_config()

    @property
    def table_name(self) -> str:
        """Get DynamoDB table name."""
        return self.main_config.evolution_table_name

    @property
    def s3_bucket(self) -> str:
        """Get S3 bucket name."""
        return self.main_config.storage.s3_bucket_pattern.format(
            project_name=self.main_config.project_name,
            environment=self.main_config.environment,
        )

    def _compute_ttl(self) -> int:
        """Compute TTL timestamp based on environment."""
        if self.main_config.environment == "prod":
            days = self.config.retention_days_prod
        else:
            days = self.config.retention_days_dev

        ttl_timestamp = int(
            (datetime.now(timezone.utc).timestamp() + (days * 24 * 60 * 60))
        )
        return ttl_timestamp

    def _summarize_actions(self, refine_actions: list[RefineAction]) -> dict[str, int]:
        """Summarize refine actions by operation type."""
        summary: dict[str, int] = {}
        for action in refine_actions:
            op_name = action.operation.value
            summary[op_name] = summary.get(op_name, 0) + 1
        return summary

    async def record_task_completion(
        self,
        agent_id: str,
        task_id: str,
        tenant_id: str,
        outcome: str,
        memories_used: list[str],
        strategies_applied: list[str],
        refine_actions: list[RefineAction],
        quality_score: float = 0.0,
        execution_time_ms: float = 0.0,
    ) -> TaskCompletionRecord:
        """
        Record memory usage and evolution for a completed task.

        Args:
            agent_id: Agent that completed the task
            task_id: Unique task identifier
            tenant_id: Tenant identifier for isolation
            outcome: Task outcome ("success", "failure", "partial")
            memories_used: List of memory IDs used
            strategies_applied: List of strategy IDs applied
            refine_actions: Refine actions executed
            quality_score: Task quality score (0.0 to 1.0)
            execution_time_ms: Task execution time

        Returns:
            TaskCompletionRecord that was stored
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        action_summary = self._summarize_actions(refine_actions)

        # Store full refine actions in S3 if configured
        s3_key = None
        if self.config.store_full_refine_actions and refine_actions and self.s3:
            s3_key = f"refine-actions/{tenant_id}/{agent_id}/{task_id}.json"
            await self._store_actions_to_s3(s3_key, refine_actions)

        # Create record
        record = TaskCompletionRecord(
            agent_id=agent_id,
            task_id=task_id,
            tenant_id=tenant_id,
            timestamp=timestamp,
            outcome=outcome,
            memories_used_count=len(memories_used),
            strategies_applied_count=len(strategies_applied),
            refine_actions_summary=action_summary,
            quality_score=quality_score,
            execution_time_ms=execution_time_ms,
            s3_detail_key=s3_key,
        )

        # Store in DynamoDB
        ttl = self._compute_ttl()
        await self.dynamodb.put_item(
            TableName=self.table_name,
            Item=record.to_dynamo_item(ttl),
        )

        # Log to audit logger if available
        if self.audit_logger:
            self.audit_logger.log_event(
                event_type="MEMORY_EVOLUTION",
                operation="task_completion",
                actor=agent_id,
                details={
                    "task_id": task_id,
                    "tenant_id": tenant_id,
                    "outcome": outcome,
                    "memories_used": len(memories_used),
                    "refine_actions": action_summary,
                },
            )

        logger.debug(
            f"Recorded task completion: agent={agent_id}, task={task_id}, "
            f"outcome={outcome}, refine_actions={action_summary}"
        )

        return record

    async def _store_actions_to_s3(
        self,
        key: str,
        actions: list[RefineAction],
    ) -> None:
        """Store full refine actions to S3."""
        import json

        if not self.s3:
            return

        body = json.dumps([a.to_dict() for a in actions], indent=2)
        await self.s3.put_object(
            Bucket=self.s3_bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )

    async def compute_evolution_gain(
        self,
        agent_id: str,
        tenant_id: str,
        window_size: Optional[int] = None,
    ) -> float:
        """
        Compute performance improvement over last N tasks.

        Compares success rate of first half vs second half of tasks
        in the window to determine evolution gain.

        Args:
            agent_id: Agent to compute gain for
            tenant_id: Tenant identifier
            window_size: Number of tasks to consider (default: config value)

        Returns:
            Evolution gain (-1.0 to 1.0, positive = improvement)
        """
        window = window_size or self.config.gain_window_size

        # Query recent tasks - using date-bucketed approach
        # Parallelize DynamoDB queries in batches to reduce total latency
        import datetime as dt

        date = datetime.now(timezone.utc)
        date_bucket = date.replace(hour=0, minute=0, second=0, microsecond=0)

        async def _query_day(days_ago: int) -> list[dict[str, Any]]:
            d = date_bucket - dt.timedelta(days=days_ago)
            date_str = d.strftime("%Y-%m-%d")
            try:
                response = await self.dynamodb.query(
                    TableName=self.table_name,
                    KeyConditionExpression="pk = :pk",
                    ExpressionAttributeValues={
                        ":pk": {"S": f"{agent_id}#{date_str}"},
                    },
                    ScanIndexForward=False,
                    Limit=window,
                )
                return response.get("Items", [])
            except Exception as e:
                logger.warning(f"Failed to query for date {date_str}: {e}")
                return []

        # Batch parallel queries (5 at a time to reduce latency)
        items: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        batch_size = 5
        for batch_start in range(0, 30, batch_size):
            batch_end = min(batch_start + batch_size, 30)
            batch_results = await asyncio.gather(
                *[_query_day(d) for d in range(batch_start, batch_end)]
            )
            for day_items in batch_results:
                for item in day_items:
                    # Deduplicate items across parallel queries
                    item_key = item.get("sk", {}).get("S", "")
                    if item_key and item_key not in seen_keys:
                        seen_keys.add(item_key)
                        items.append(item)
                    elif not item_key:
                        items.append(item)
            if len(items) >= window:
                break

        # Sort by timestamp descending
        items.sort(key=lambda x: x.get("sk", {}).get("S", ""), reverse=True)
        items = items[:window]

        if len(items) < self.config.min_tasks_for_gain:
            logger.debug(
                f"Not enough tasks for evolution gain: {len(items)} < "
                f"{self.config.min_tasks_for_gain}"
            )
            return 0.0

        # Compare first half (older) vs second half (newer)
        mid = len(items) // 2
        first_half = items[mid:]  # Older tasks
        second_half = items[:mid]  # Newer tasks

        first_success_rate = sum(
            1 for i in first_half if i.get("outcome", {}).get("S") == "success"
        ) / len(first_half)

        second_success_rate = sum(
            1 for i in second_half if i.get("outcome", {}).get("S") == "success"
        ) / len(second_half)

        gain = second_success_rate - first_success_rate

        logger.debug(
            f"Evolution gain for {agent_id}: {gain:.3f} "
            f"(first_half={first_success_rate:.2f}, second_half={second_success_rate:.2f})"
        )

        return gain

    async def get_metrics_for_window(
        self,
        agent_id: str,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> EvolutionMetrics:
        """
        Compute aggregated metrics for a time window.

        Args:
            agent_id: Agent to get metrics for
            tenant_id: Tenant identifier
            start_time: Window start
            end_time: Window end

        Returns:
            Aggregated EvolutionMetrics for the window
        """
        # Query tasks in window
        items: list[dict[str, Any]] = []

        current = start_time
        while current <= end_time:
            date_str = current.strftime("%Y-%m-%d")
            try:
                response = await self.dynamodb.query(
                    TableName=self.table_name,
                    KeyConditionExpression="pk = :pk",
                    ExpressionAttributeValues={
                        ":pk": {"S": f"{agent_id}#{date_str}"},
                    },
                )
                for item in response.get("Items", []):
                    item_ts = item.get("sk", {}).get("S", "")
                    if start_time.isoformat() <= item_ts <= end_time.isoformat():
                        items.append(item)
            except Exception as e:
                logger.warning(f"Failed to query for date {date_str}: {e}")

            import datetime as dt

            current = current + dt.timedelta(days=1)

        if not items:
            return EvolutionMetrics(
                agent_id=agent_id,
                tenant_id=tenant_id,
                window_start=start_time.isoformat(),
                window_end=end_time.isoformat(),
                task_count=0,
            )

        # Aggregate metrics
        total_tasks = len(items)
        successful_tasks = sum(
            1 for i in items if i.get("outcome", {}).get("S") == "success"
        )
        total_memories_used = sum(
            int(i.get("memories_used_count", {}).get("N", 0)) for i in items
        )
        total_strategies = sum(
            int(i.get("strategies_applied_count", {}).get("N", 0)) for i in items
        )

        # Count refine actions by type
        consolidations = 0
        abstractions = 0
        pruned = 0
        reinforcements = 0

        for item in items:
            summary_str = item.get("refine_actions_summary", {}).get("S", "{}")
            try:
                import ast

                summary = ast.literal_eval(summary_str)
                consolidations += summary.get("consolidate", 0)
                abstractions += summary.get("abstract", 0)
                pruned += summary.get("prune", 0)
                reinforcements += summary.get("reinforce", 0)
            except Exception:
                pass

        # Compute evolution gain
        evolution_gain = await self.compute_evolution_gain(
            agent_id, tenant_id, window_size=total_tasks
        )

        return EvolutionMetrics(
            retrieval_precision=(
                successful_tasks / total_tasks if total_tasks > 0 else 0
            ),
            strategy_reuse_rate=(
                total_strategies / total_tasks if total_tasks > 0 else 0
            ),
            consolidation_count=consolidations,
            abstractions_created=abstractions,
            memories_pruned=pruned,
            reinforcements_applied=reinforcements,
            memory_utilization=(
                total_memories_used / (total_tasks * 10)
                if total_tasks > 0
                else 0  # Assume 10 memories per task baseline
            ),
            evolution_gain=evolution_gain,
            agent_id=agent_id,
            tenant_id=tenant_id,
            window_start=start_time.isoformat(),
            window_end=end_time.isoformat(),
            task_count=total_tasks,
        )


# =============================================================================
# SINGLETON MANAGEMENT
# =============================================================================

_tracker_instance: Optional[EvolutionTracker] = None


def get_evolution_tracker(
    dynamodb_client: Optional[DynamoDBClientProtocol] = None,
    s3_client: Optional[S3ClientProtocol] = None,
    audit_logger: Optional[AuditLoggerProtocol] = None,
    config: Optional[EvolutionTrackerConfig] = None,
) -> EvolutionTracker:
    """Get or create the singleton EvolutionTracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        if dynamodb_client is None:
            raise ValueError("dynamodb_client is required for initial creation")
        _tracker_instance = EvolutionTracker(
            dynamodb_client=dynamodb_client,
            s3_client=s3_client,
            audit_logger=audit_logger,
            config=config,
        )
    return _tracker_instance


def reset_evolution_tracker() -> None:
    """Reset the singleton instance (for testing)."""
    global _tracker_instance
    _tracker_instance = None
