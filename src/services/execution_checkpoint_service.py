"""
Execution Checkpoint Service for Real-Time Agent Intervention.

Implements per-action approval gates with WebSocket streaming for
Claude Code-style real-time intervention (ADR-042).
"""

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import uuid4

if TYPE_CHECKING:
    from src.services.realtime_event_publisher import RealtimeEventPublisher

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CheckpointStatus(str, Enum):
    """Checkpoint lifecycle states."""

    PENDING = "PENDING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AUTO_APPROVED = "AUTO_APPROVED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    MODIFIED = "MODIFIED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    TIMEOUT = "TIMEOUT"


class ActionType(str, Enum):
    """Types of agent actions."""

    TOOL_CALL = "tool_call"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    API_REQUEST = "api_request"
    COMMAND_EXEC = "command_exec"
    DATABASE_WRITE = "database_write"
    NETWORK_REQUEST = "network_request"
    RESOURCE_CREATE = "resource_create"
    RESOURCE_DELETE = "resource_delete"


class RiskLevel(str, Enum):
    """Risk classification for actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InterventionMode(str, Enum):
    """Maps to ADR-032 autonomy levels."""

    ALL_ACTIONS = "all_actions"  # Level 0-1: All actions require approval
    WRITE_ACTIONS = "write_actions"  # Level 2: Only write operations
    HIGH_RISK = "high_risk"  # Level 3: High/critical risk only
    CRITICAL_ONLY = "critical_only"  # Level 4: Critical only
    NONE = "none"  # Level 5: No intervention


@dataclass
class CheckpointAction:
    """Represents an action awaiting approval."""

    checkpoint_id: str
    execution_id: str
    agent_id: str
    action_type: ActionType
    action_name: str
    parameters: Dict[str, Any]
    risk_level: RiskLevel
    reversible: bool
    estimated_duration_seconds: int
    context: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    timeout_seconds: int = 300
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class CheckpointResult:
    """Result of a checkpoint decision."""

    checkpoint_id: str
    status: CheckpointStatus
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None


@dataclass
class TrustRule:
    """Rule for auto-approving actions."""

    rule_id: str
    action_type: Optional[ActionType] = None
    action_name_pattern: Optional[str] = None
    agent_id_pattern: Optional[str] = None
    max_risk_level: RiskLevel = RiskLevel.LOW
    enabled: bool = True
    created_by: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ExecutionCheckpointService:
    """
    Manages real-time approval gates for agent actions.

    Implements checkpoint-based intervention pattern from ADR-042,
    integrating with ADR-032 autonomy framework.
    """

    def __init__(
        self,
        dynamodb_table_name: str,
        event_publisher: Optional["RealtimeEventPublisher"] = None,
        intervention_mode: InterventionMode = InterventionMode.HIGH_RISK,
        default_timeout_seconds: int = 300,
    ):
        """
        Initialize checkpoint service.

        Args:
            dynamodb_table_name: Name of checkpoints DynamoDB table
            event_publisher: WebSocket event publisher for real-time updates
            intervention_mode: Default intervention mode (maps to autonomy level)
            default_timeout_seconds: Default timeout for approval wait
        """
        self.table_name = dynamodb_table_name
        self.event_publisher = event_publisher
        self.intervention_mode = intervention_mode
        self.default_timeout = default_timeout_seconds

        self._dynamodb = boto3.resource("dynamodb")
        self._table = self._dynamodb.Table(dynamodb_table_name)

        # In-memory approval events for async coordination
        self._approval_events: Dict[str, asyncio.Event] = {}
        self._approval_results: Dict[str, CheckpointResult] = {}

        # Trust rules cache
        self._trust_rules: List[TrustRule] = []

        logger.info(
            f"ExecutionCheckpointService initialized with mode={intervention_mode.value}"
        )

    async def create_checkpoint(
        self,
        execution_id: str,
        agent_id: str,
        action: CheckpointAction,
    ) -> CheckpointResult:
        """
        Create checkpoint and wait for approval if required.

        Args:
            execution_id: Parent execution ID
            agent_id: Agent requesting the action
            action: Action details requiring approval

        Returns:
            CheckpointResult with approval decision
        """
        action.checkpoint_id = str(uuid4())
        action.execution_id = execution_id
        action.agent_id = agent_id

        # Check if intervention required for this action
        if not self._requires_intervention(action):
            result = CheckpointResult(
                checkpoint_id=action.checkpoint_id,
                status=CheckpointStatus.SKIPPED,
                reason="Action does not require intervention under current mode",
            )
            await self._persist_checkpoint(action, result)
            return result

        # Check trust rules for auto-approval
        if await self._should_auto_approve(action):
            result = CheckpointResult(
                checkpoint_id=action.checkpoint_id,
                status=CheckpointStatus.AUTO_APPROVED,
                decided_at=datetime.now(timezone.utc).isoformat(),
                reason="Matched trust rule",
            )
            await self._persist_checkpoint(action, result)
            await self._publish_event("checkpoint.auto_approved", action, result)
            logger.info(
                f"Checkpoint {action.checkpoint_id} auto-approved by trust rule"
            )
            return result

        # Persist pending checkpoint
        await self._persist_checkpoint(
            action,
            CheckpointResult(
                checkpoint_id=action.checkpoint_id,
                status=CheckpointStatus.AWAITING_APPROVAL,
            ),
        )

        # Publish to WebSocket for UI display
        await self._publish_event("checkpoint.created", action, None)

        logger.info(
            f"Checkpoint {action.checkpoint_id} awaiting approval for "
            f"{action.action_type.value}:{action.action_name}"
        )

        # Wait for approval with timeout
        result = await self._wait_for_approval(
            action.checkpoint_id,
            timeout_seconds=action.timeout_seconds or self.default_timeout,
        )

        return result

    async def approve_checkpoint(
        self,
        checkpoint_id: str,
        user_id: str,
        modifications: Optional[Dict[str, Any]] = None,
    ) -> CheckpointResult:
        """
        Approve a pending checkpoint.

        Args:
            checkpoint_id: ID of checkpoint to approve
            user_id: User approving the action
            modifications: Optional parameter modifications

        Returns:
            Updated CheckpointResult
        """
        status = (
            CheckpointStatus.MODIFIED if modifications else CheckpointStatus.APPROVED
        )

        result = CheckpointResult(
            checkpoint_id=checkpoint_id,
            status=status,
            decided_by=user_id,
            decided_at=datetime.now(timezone.utc).isoformat(),
            modifications=modifications,
        )

        # Update DynamoDB
        await self._update_checkpoint_status(checkpoint_id, result)

        # Signal waiting coroutine
        self._approval_results[checkpoint_id] = result
        if checkpoint_id in self._approval_events:
            self._approval_events[checkpoint_id].set()

        # Publish approval event
        await self._publish_status_update(checkpoint_id, result)

        logger.info(f"Checkpoint {checkpoint_id} approved by {user_id}")

        return result

    async def deny_checkpoint(
        self,
        checkpoint_id: str,
        user_id: str,
        reason: str,
    ) -> CheckpointResult:
        """
        Deny a pending checkpoint and halt execution.

        Args:
            checkpoint_id: ID of checkpoint to deny
            user_id: User denying the action
            reason: Reason for denial

        Returns:
            Updated CheckpointResult
        """
        result = CheckpointResult(
            checkpoint_id=checkpoint_id,
            status=CheckpointStatus.DENIED,
            decided_by=user_id,
            decided_at=datetime.now(timezone.utc).isoformat(),
            reason=reason,
        )

        # Update DynamoDB
        await self._update_checkpoint_status(checkpoint_id, result)

        # Signal waiting coroutine
        self._approval_results[checkpoint_id] = result
        if checkpoint_id in self._approval_events:
            self._approval_events[checkpoint_id].set()

        # Publish denial event
        await self._publish_status_update(checkpoint_id, result)

        logger.info(f"Checkpoint {checkpoint_id} denied by {user_id}: {reason}")

        return result

    async def mark_executing(self, checkpoint_id: str) -> None:
        """Mark checkpoint as currently executing."""
        result = CheckpointResult(
            checkpoint_id=checkpoint_id,
            status=CheckpointStatus.EXECUTING,
        )
        await self._update_checkpoint_status(checkpoint_id, result)
        await self._publish_status_update(checkpoint_id, result)

    async def mark_completed(
        self,
        checkpoint_id: str,
        execution_result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark checkpoint as completed successfully."""
        result = CheckpointResult(
            checkpoint_id=checkpoint_id,
            status=CheckpointStatus.COMPLETED,
            execution_result=execution_result,
        )
        await self._update_checkpoint_status(checkpoint_id, result)
        await self._publish_status_update(checkpoint_id, result)

    async def mark_failed(
        self,
        checkpoint_id: str,
        error: str,
        execution_result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark checkpoint as failed."""
        result = CheckpointResult(
            checkpoint_id=checkpoint_id,
            status=CheckpointStatus.FAILED,
            reason=error,
            execution_result=execution_result,
        )
        await self._update_checkpoint_status(checkpoint_id, result)
        await self._publish_status_update(checkpoint_id, result)

    async def get_execution_checkpoints(
        self,
        execution_id: str,
        status_filter: Optional[List[CheckpointStatus]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all checkpoints for an execution.

        Args:
            execution_id: Execution to query
            status_filter: Optional filter by status

        Returns:
            List of checkpoint records
        """
        try:
            response = self._table.query(
                IndexName="execution-status-index",
                KeyConditionExpression="execution_id = :eid",
                ExpressionAttributeValues={":eid": execution_id},
            )

            items = response.get("Items", [])

            if status_filter:
                status_values = [s.value for s in status_filter]
                items = [i for i in items if i.get("status") in status_values]

            return items

        except ClientError as e:
            logger.error(f"Error querying checkpoints: {e}")
            return []

    async def add_trust_rule(self, rule: TrustRule) -> None:
        """Add a trust rule for auto-approval."""
        self._trust_rules.append(rule)
        logger.info(f"Added trust rule {rule.rule_id}")

    async def remove_trust_rule(self, rule_id: str) -> bool:
        """Remove a trust rule by ID."""
        for i, rule in enumerate(self._trust_rules):
            if rule.rule_id == rule_id:
                self._trust_rules.pop(i)
                logger.info(f"Removed trust rule {rule_id}")
                return True
        return False

    async def get_trust_rules(self) -> List[TrustRule]:
        """Get all active trust rules."""
        return [r for r in self._trust_rules if r.enabled]

    def set_intervention_mode(self, mode: InterventionMode) -> None:
        """Update intervention mode (maps to ADR-032 autonomy level)."""
        old_mode = self.intervention_mode
        self.intervention_mode = mode
        logger.info(f"Intervention mode changed from {old_mode.value} to {mode.value}")

    def _requires_intervention(self, action: CheckpointAction) -> bool:
        """Check if action requires intervention under current mode."""
        if self.intervention_mode == InterventionMode.NONE:
            return False

        if self.intervention_mode == InterventionMode.ALL_ACTIONS:
            return True

        if self.intervention_mode == InterventionMode.WRITE_ACTIONS:
            write_types = {
                ActionType.FILE_WRITE,
                ActionType.FILE_DELETE,
                ActionType.DATABASE_WRITE,
                ActionType.RESOURCE_CREATE,
                ActionType.RESOURCE_DELETE,
            }
            return action.action_type in write_types

        if self.intervention_mode == InterventionMode.HIGH_RISK:
            return action.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}

        if self.intervention_mode == InterventionMode.CRITICAL_ONLY:
            return action.risk_level == RiskLevel.CRITICAL

        return True  # type: ignore[unreachable]

    async def _should_auto_approve(self, action: CheckpointAction) -> bool:
        """Check if action matches any trust rule for auto-approval."""
        for rule in self._trust_rules:
            if not rule.enabled:
                continue

            # Check action type match
            if rule.action_type and rule.action_type != action.action_type:
                continue

            # Check action name pattern
            if rule.action_name_pattern:
                import fnmatch

                if not fnmatch.fnmatch(action.action_name, rule.action_name_pattern):
                    continue

            # Check agent ID pattern
            if rule.agent_id_pattern:
                import fnmatch

                if not fnmatch.fnmatch(action.agent_id, rule.agent_id_pattern):
                    continue

            # Check risk level
            risk_order = [
                RiskLevel.LOW,
                RiskLevel.MEDIUM,
                RiskLevel.HIGH,
                RiskLevel.CRITICAL,
            ]
            if risk_order.index(action.risk_level) > risk_order.index(
                rule.max_risk_level
            ):
                continue

            # All conditions matched
            logger.debug(f"Action matches trust rule {rule.rule_id}")
            return True

        return False

    async def _wait_for_approval(
        self,
        checkpoint_id: str,
        timeout_seconds: int,
    ) -> CheckpointResult:
        """Wait for approval decision with timeout."""
        event = asyncio.Event()
        self._approval_events[checkpoint_id] = event

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)

            if checkpoint_id in self._approval_results:
                return self._approval_results[checkpoint_id]

            # Shouldn't happen but handle edge case
            return CheckpointResult(
                checkpoint_id=checkpoint_id,
                status=CheckpointStatus.FAILED,
                reason="Approval event signaled but no result found",
            )

        except asyncio.TimeoutError:
            result = CheckpointResult(
                checkpoint_id=checkpoint_id,
                status=CheckpointStatus.TIMEOUT,
                reason=f"Approval timeout after {timeout_seconds} seconds",
            )
            await self._update_checkpoint_status(checkpoint_id, result)
            await self._publish_status_update(checkpoint_id, result)
            logger.warning(f"Checkpoint {checkpoint_id} timed out")
            return result

        finally:
            # Cleanup
            self._approval_events.pop(checkpoint_id, None)
            self._approval_results.pop(checkpoint_id, None)

    async def _persist_checkpoint(
        self,
        action: CheckpointAction,
        result: CheckpointResult,
    ) -> None:
        """Persist checkpoint to DynamoDB."""
        item = {
            "checkpoint_id": action.checkpoint_id,
            "execution_id": action.execution_id,
            "agent_id": action.agent_id,
            "action_type": action.action_type.value,
            "action_name": action.action_name,
            "parameters": action.parameters,
            "risk_level": action.risk_level.value,
            "reversible": action.reversible,
            "estimated_duration_seconds": action.estimated_duration_seconds,
            "context": action.context,
            "description": action.description,
            "status": result.status.value,
            "created_at": action.created_at,
            "ttl": int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp()),
        }

        if result.decided_by:
            item["decided_by"] = result.decided_by
        if result.decided_at:
            item["decided_at"] = result.decided_at
        if result.modifications:
            item["modifications"] = result.modifications
        if result.reason:
            item["reason"] = result.reason

        try:
            self._table.put_item(Item=item)
        except ClientError as e:
            logger.error(f"Error persisting checkpoint: {e}")
            raise

    async def _update_checkpoint_status(
        self,
        checkpoint_id: str,
        result: CheckpointResult,
    ) -> None:
        """Update checkpoint status in DynamoDB."""
        update_expr = "SET #status = :status"
        expr_names = {"#status": "status"}
        expr_values: dict[str, Any] = {":status": result.status.value}

        if result.decided_by:
            update_expr += ", decided_by = :decided_by"
            expr_values[":decided_by"] = result.decided_by

        if result.decided_at:
            update_expr += ", decided_at = :decided_at"
            expr_values[":decided_at"] = result.decided_at

        if result.modifications:
            update_expr += ", modifications = :modifications"
            expr_values[":modifications"] = result.modifications

        if result.reason:
            update_expr += ", reason = :reason"
            expr_values[":reason"] = result.reason

        if result.execution_result:
            update_expr += ", execution_result = :execution_result"
            expr_values[":execution_result"] = result.execution_result

        try:
            self._table.update_item(
                Key={"checkpoint_id": checkpoint_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
        except ClientError as e:
            logger.error(f"Error updating checkpoint status: {e}")
            raise

    async def _publish_event(
        self,
        event_type: str,
        action: CheckpointAction,
        result: Optional[CheckpointResult],
    ) -> None:
        """Publish checkpoint event to WebSocket."""
        if not self.event_publisher:
            return

        payload = {
            "type": event_type,
            "checkpoint": asdict(action),
            "result": asdict(result) if result else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await self.event_publisher.publish(
            execution_id=action.execution_id,
            event=payload,
        )

    async def _publish_status_update(
        self,
        checkpoint_id: str,
        result: CheckpointResult,
    ) -> None:
        """Publish checkpoint status update to WebSocket."""
        if not self.event_publisher:
            return

        # Get execution_id from DynamoDB
        try:
            response = self._table.get_item(Key={"checkpoint_id": checkpoint_id})
            item = response.get("Item", {})
            execution_id = item.get("execution_id")

            if execution_id:
                payload = {
                    "type": "checkpoint.updated",
                    "checkpoint_id": checkpoint_id,
                    "status": result.status.value,
                    "decided_by": result.decided_by,
                    "decided_at": result.decided_at,
                    "reason": result.reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                await self.event_publisher.publish(
                    execution_id=str(execution_id),
                    event=payload,
                )
        except ClientError as e:
            logger.error(f"Error publishing status update: {e}")


def autonomy_level_to_intervention_mode(autonomy_level: int) -> InterventionMode:
    """
    Map ADR-032 autonomy level to intervention mode.

    Args:
        autonomy_level: 0-5 autonomy level from ADR-032

    Returns:
        Corresponding InterventionMode
    """
    mapping = {
        0: InterventionMode.ALL_ACTIONS,  # Manual
        1: InterventionMode.ALL_ACTIONS,  # Observe
        2: InterventionMode.WRITE_ACTIONS,  # Assisted
        3: InterventionMode.HIGH_RISK,  # Supervised
        4: InterventionMode.CRITICAL_ONLY,  # Guided
        5: InterventionMode.NONE,  # Autonomous
    }
    return mapping.get(autonomy_level, InterventionMode.HIGH_RISK)
