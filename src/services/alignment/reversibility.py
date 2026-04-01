"""
Reversibility Classifier (ADR-052 Phase 1).

Classifies actions by reversibility level and manages rollback infrastructure.
Ensures all actions can be undone to preserve human control.

Action Classes:
- Class A (FULLY_REVERSIBLE): Code changes, config updates, sandbox modifications
- Class B (PARTIALLY_REVERSIBLE): Data modifications, external API calls, deployments
- Class C (IRREVERSIBLE): Data deletion, credential rotation, external state changes

Autonomy Requirements:
- Class A: Can delegate to Level 2-3 agents
- Class B: Requires Level 1 review before execution
- Class C: ALWAYS requires human approval (Level 0)

Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class ActionClass(Enum):
    """Classification of actions by reversibility."""

    FULLY_REVERSIBLE = "A"  # Can be instantly rolled back
    PARTIALLY_REVERSIBLE = "B"  # Can be rolled back with effort/cost
    IRREVERSIBLE = "C"  # Cannot be undone

    @property
    def description(self) -> str:
        """Human-readable description of the action class."""
        descriptions = {
            ActionClass.FULLY_REVERSIBLE: (
                "Fully reversible - instant rollback available"
            ),
            ActionClass.PARTIALLY_REVERSIBLE: (
                "Partially reversible - rollback possible but may have side effects"
            ),
            ActionClass.IRREVERSIBLE: (
                "Irreversible - cannot be undone, requires human approval"
            ),
        }
        return descriptions[self]

    @property
    def min_autonomy_level(self) -> int:
        """Minimum autonomy level required to execute this action class."""
        levels = {
            ActionClass.FULLY_REVERSIBLE: 2,  # EXECUTE_REVIEW or higher
            ActionClass.PARTIALLY_REVERSIBLE: 1,  # RECOMMEND (with review)
            ActionClass.IRREVERSIBLE: 0,  # OBSERVE (requires human)
        }
        return levels[self]

    @property
    def requires_human_approval(self) -> bool:
        """Whether this action class requires human approval."""
        return self == ActionClass.IRREVERSIBLE


@dataclass
class ActionMetadata:
    """Metadata about an action for classification."""

    action_type: str  # e.g., "code_change", "data_modification", "api_call"
    target_resource: str  # What is being affected
    target_resource_type: str  # e.g., "file", "database", "external_api"
    is_production: bool = False  # Is this affecting production?
    affects_external_system: bool = (
        False  # Does this affect systems outside our control?
    )
    is_destructive: bool = False  # Does this delete or permanently modify data?
    has_side_effects: bool = False  # Does this trigger external notifications/actions?
    estimated_impact_scope: str = "local"  # "local", "service", "system", "external"

    # Optional context
    agent_id: str | None = None
    request_id: str | None = None
    user_id: str | None = None


@dataclass
class StateSnapshot:
    """Snapshot of state before an action for rollback."""

    snapshot_id: str
    action_id: str
    resource_type: str
    resource_id: str
    state_data: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    checksum: str = ""

    def __post_init__(self) -> None:
        """Calculate checksum after initialization."""
        if not self.checksum:
            self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate checksum of state data for integrity verification."""
        data_str = json.dumps(self.state_data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode(), usedforsecurity=False).hexdigest()[:16]

    def verify_integrity(self) -> bool:
        """Verify the snapshot data hasn't been corrupted."""
        return self.checksum == self._calculate_checksum()

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "snapshot_id": self.snapshot_id,
            "action_id": self.action_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "state_data": self.state_data,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "checksum": self.checksum,
        }


@dataclass
class RollbackPlan:
    """Plan for rolling back a partially reversible action."""

    plan_id: str
    action_id: str
    steps: list[dict[str, Any]]  # Ordered rollback steps
    estimated_duration_seconds: int = 0
    estimated_cost: float = 0.0
    potential_side_effects: list[str] = field(default_factory=list)
    requires_downtime: bool = False
    is_viable: bool = True
    non_viable_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "plan_id": self.plan_id,
            "action_id": self.action_id,
            "steps": self.steps,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "estimated_cost": self.estimated_cost,
            "potential_side_effects": self.potential_side_effects,
            "requires_downtime": self.requires_downtime,
            "is_viable": self.is_viable,
            "non_viable_reason": self.non_viable_reason,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ActionApproval:
    """Result of action classification and approval check."""

    action_id: str
    action_class: ActionClass
    approved: bool
    requires_human_approval: bool
    rollback_available: bool
    rollback_plan: RollbackPlan | None = None
    snapshot: StateSnapshot | None = None
    rejection_reason: str | None = None
    conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "action_id": self.action_id,
            "action_class": self.action_class.value,
            "approved": self.approved,
            "requires_human_approval": self.requires_human_approval,
            "rollback_available": self.rollback_available,
            "rollback_plan": (
                self.rollback_plan.to_dict() if self.rollback_plan else None
            ),
            "snapshot_id": self.snapshot.snapshot_id if self.snapshot else None,
            "rejection_reason": self.rejection_reason,
            "conditions": self.conditions,
        }


class ReversibilityClassifier:
    """
    Classifies actions by reversibility and manages rollback infrastructure.

    Ensures all actions can be undone to preserve human control:
    - Class A actions get automatic state snapshots
    - Class B actions require viable rollback plans
    - Class C actions require explicit human approval
    """

    # Action type to class mappings
    FULLY_REVERSIBLE_TYPES = frozenset(
        {
            "code_change",
            "config_update",
            "schema_migration",
            "sandbox_modification",
            "feature_flag_toggle",
            "draft_save",
            "cache_invalidation",
        }
    )

    PARTIALLY_REVERSIBLE_TYPES = frozenset(
        {
            "data_modification",
            "external_api_call",
            "deployment",
            "notification_send",
            "email_send",
            "webhook_trigger",
            "backup_create",
            "log_write",
        }
    )

    IRREVERSIBLE_TYPES = frozenset(
        {
            "data_deletion",
            "credential_rotation",
            "external_state_change",
            "production_incident",
            "customer_data_export",
            "audit_log_modification",
            "compliance_report_submission",
            "payment_processing",
        }
    )

    def __init__(
        self,
        snapshot_store: Callable[[StateSnapshot], None] | None = None,
        snapshot_retriever: Callable[[str], StateSnapshot | None] | None = None,
        rollback_executor: Callable[[RollbackPlan], Awaitable[bool]] | None = None,
    ):
        """
        Initialize the reversibility classifier.

        Args:
            snapshot_store: Callback to persist state snapshots
            snapshot_retriever: Callback to retrieve snapshots by ID
            rollback_executor: Async callback to execute rollback plans
        """
        self._snapshot_store = snapshot_store
        self._snapshot_retriever = snapshot_retriever
        self._rollback_executor = rollback_executor

        # In-memory snapshot cache (for testing or small deployments)
        self._snapshots: dict[str, StateSnapshot] = {}
        self._rollback_plans: dict[str, RollbackPlan] = {}
        self._lock = threading.RLock()

        # Counters for metrics
        self._class_a_count = 0
        self._class_b_count = 0
        self._class_c_count = 0
        self._rollbacks_attempted = 0
        self._rollbacks_successful = 0

        logger.info("ReversibilityClassifier initialized")

    def classify(self, metadata: ActionMetadata) -> ActionClass:
        """
        Classify an action based on its metadata.

        Args:
            metadata: Information about the action

        Returns:
            The appropriate ActionClass
        """
        # Check explicit type mappings first
        if metadata.action_type in self.IRREVERSIBLE_TYPES:
            return ActionClass.IRREVERSIBLE

        if metadata.action_type in self.FULLY_REVERSIBLE_TYPES:
            # Even "fully reversible" types can be escalated
            if metadata.is_production and metadata.is_destructive:
                return ActionClass.IRREVERSIBLE
            elif metadata.is_production or metadata.affects_external_system:
                return ActionClass.PARTIALLY_REVERSIBLE
            return ActionClass.FULLY_REVERSIBLE

        if metadata.action_type in self.PARTIALLY_REVERSIBLE_TYPES:
            # Partially reversible can be escalated to irreversible
            if metadata.is_destructive and metadata.is_production:
                return ActionClass.IRREVERSIBLE
            return ActionClass.PARTIALLY_REVERSIBLE

        # Default classification based on attributes
        if metadata.is_destructive:
            return ActionClass.IRREVERSIBLE
        elif metadata.affects_external_system or metadata.has_side_effects:
            return ActionClass.PARTIALLY_REVERSIBLE
        elif metadata.is_production:
            return ActionClass.PARTIALLY_REVERSIBLE
        else:
            return ActionClass.FULLY_REVERSIBLE

    def pre_action_check(
        self,
        action_id: str,
        metadata: ActionMetadata,
        agent_autonomy_level: int,
        current_state: dict[str, Any] | None = None,
    ) -> ActionApproval:
        """
        Check if an action can proceed and prepare rollback infrastructure.

        Args:
            action_id: Unique identifier for the action
            metadata: Action metadata for classification
            agent_autonomy_level: Current autonomy level of the executing agent
            current_state: Current state data for snapshot (Class A actions)

        Returns:
            ActionApproval with approval status and rollback preparation
        """
        with self._lock:
            action_class = self.classify(metadata)

            # Track classification counts
            if action_class == ActionClass.FULLY_REVERSIBLE:
                self._class_a_count += 1
            elif action_class == ActionClass.PARTIALLY_REVERSIBLE:
                self._class_b_count += 1
            else:
                self._class_c_count += 1

            # Check if agent has sufficient autonomy
            if agent_autonomy_level < action_class.min_autonomy_level:
                return ActionApproval(
                    action_id=action_id,
                    action_class=action_class,
                    approved=False,
                    requires_human_approval=True,
                    rollback_available=False,
                    rejection_reason=(
                        f"Agent autonomy level {agent_autonomy_level} insufficient "
                        f"for {action_class.name} actions (requires {action_class.min_autonomy_level})"
                    ),
                )

            # Handle Class C (irreversible) - always require human approval
            if action_class == ActionClass.IRREVERSIBLE:
                logger.warning(
                    f"Irreversible action {action_id} requires human approval: "
                    f"{metadata.action_type} on {metadata.target_resource}"
                )
                return ActionApproval(
                    action_id=action_id,
                    action_class=action_class,
                    approved=False,
                    requires_human_approval=True,
                    rollback_available=False,
                    rejection_reason="Irreversible action requires explicit human approval",
                    conditions=["Obtain human approval before proceeding"],
                )

            # Handle Class A (fully reversible) - create snapshot
            snapshot = None
            if action_class == ActionClass.FULLY_REVERSIBLE and current_state:
                snapshot = self._create_snapshot(action_id, metadata, current_state)

            # Handle Class B (partially reversible) - generate rollback plan
            rollback_plan = None
            if action_class == ActionClass.PARTIALLY_REVERSIBLE:
                rollback_plan = self._generate_rollback_plan(action_id, metadata)
                if not rollback_plan.is_viable:
                    return ActionApproval(
                        action_id=action_id,
                        action_class=action_class,
                        approved=False,
                        requires_human_approval=True,
                        rollback_available=False,
                        rollback_plan=rollback_plan,
                        rejection_reason=(
                            f"Rollback plan not viable: {rollback_plan.non_viable_reason}"
                        ),
                    )

            return ActionApproval(
                action_id=action_id,
                action_class=action_class,
                approved=True,
                requires_human_approval=False,
                rollback_available=True,
                rollback_plan=rollback_plan,
                snapshot=snapshot,
                conditions=self._get_conditions(action_class, metadata),
            )

    def approve_irreversible_action(
        self,
        action_id: str,
        approved_by: str,
        reason: str,
    ) -> ActionApproval:
        """
        Record human approval for an irreversible action.

        Args:
            action_id: The action being approved
            approved_by: Identifier of the approver
            reason: Reason for approval

        Returns:
            ActionApproval indicating approval granted
        """
        logger.info(
            f"Irreversible action {action_id} approved by {approved_by}: {reason}"
        )

        return ActionApproval(
            action_id=action_id,
            action_class=ActionClass.IRREVERSIBLE,
            approved=True,
            requires_human_approval=False,  # Already approved
            rollback_available=False,
            conditions=[f"Approved by {approved_by}: {reason}"],
        )

    def get_snapshot(self, snapshot_id: str) -> StateSnapshot | None:
        """Retrieve a state snapshot by ID."""
        if self._snapshot_retriever:
            return self._snapshot_retriever(snapshot_id)
        with self._lock:
            return self._snapshots.get(snapshot_id)

    def get_snapshot_for_action(self, action_id: str) -> StateSnapshot | None:
        """Get the snapshot associated with an action."""
        with self._lock:
            for snapshot in self._snapshots.values():
                if snapshot.action_id == action_id:
                    return snapshot
        return None

    def get_rollback_plan(self, action_id: str) -> RollbackPlan | None:
        """Get the rollback plan for an action."""
        with self._lock:
            return self._rollback_plans.get(action_id)

    async def execute_rollback(
        self,
        action_id: str,
    ) -> tuple[bool, str]:
        """
        Execute a rollback for a previously approved action.

        Args:
            action_id: The action to roll back

        Returns:
            Tuple of (success, message)
        """
        with self._lock:
            self._rollbacks_attempted += 1

            # Try snapshot-based rollback (Class A)
            snapshot = self.get_snapshot_for_action(action_id)
            if snapshot:
                if not snapshot.verify_integrity():
                    logger.error(f"Snapshot integrity check failed for {action_id}")
                    return False, "Snapshot integrity verification failed"

                # In a real implementation, this would restore the state
                logger.info(f"Rolling back action {action_id} from snapshot")
                self._rollbacks_successful += 1
                return True, f"Restored state from snapshot {snapshot.snapshot_id}"

            # Try plan-based rollback (Class B)
            plan = self.get_rollback_plan(action_id)
            if plan:
                if not plan.is_viable:
                    return False, f"Rollback plan not viable: {plan.non_viable_reason}"

                if self._rollback_executor:
                    success = await self._rollback_executor(plan)
                    if success:
                        self._rollbacks_successful += 1
                        return (
                            True,
                            f"Rollback plan {plan.plan_id} executed successfully",
                        )
                    return False, "Rollback plan execution failed"

                # Without executor, just log
                logger.info(f"Rollback plan {plan.plan_id} would be executed")
                self._rollbacks_successful += 1
                return True, f"Rollback plan {plan.plan_id} executed (simulated)"

            return False, f"No rollback mechanism found for action {action_id}"

    def _create_snapshot(
        self,
        action_id: str,
        metadata: ActionMetadata,
        current_state: dict[str, Any],
    ) -> StateSnapshot:
        """Create and store a state snapshot."""
        snapshot_id = (
            f"snap_{action_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        )

        snapshot = StateSnapshot(
            snapshot_id=snapshot_id,
            action_id=action_id,
            resource_type=metadata.target_resource_type,
            resource_id=metadata.target_resource,
            state_data=current_state,
        )

        # Store snapshot
        if self._snapshot_store:
            self._snapshot_store(snapshot)
        else:
            self._snapshots[snapshot_id] = snapshot

        logger.debug(f"Created snapshot {snapshot_id} for action {action_id}")
        return snapshot

    def _generate_rollback_plan(
        self,
        action_id: str,
        metadata: ActionMetadata,
    ) -> RollbackPlan:
        """Generate a rollback plan for a partially reversible action."""
        plan_id = (
            f"plan_{action_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        )

        # Generate plan based on action type
        steps = []
        side_effects = []
        is_viable = True
        non_viable_reason = None
        requires_downtime = False
        estimated_duration = 0

        if metadata.action_type == "deployment":
            steps = [
                {"step": 1, "action": "Identify previous version", "type": "query"},
                {"step": 2, "action": "Prepare rollback deployment", "type": "prepare"},
                {"step": 3, "action": "Execute deployment rollback", "type": "execute"},
                {"step": 4, "action": "Verify service health", "type": "verify"},
            ]
            estimated_duration = 300  # 5 minutes
            side_effects = ["Brief service interruption possible"]
            requires_downtime = True

        elif metadata.action_type == "data_modification":
            steps = [
                {"step": 1, "action": "Retrieve backup/history", "type": "query"},
                {"step": 2, "action": "Prepare data restoration", "type": "prepare"},
                {"step": 3, "action": "Execute data restoration", "type": "execute"},
                {"step": 4, "action": "Verify data integrity", "type": "verify"},
            ]
            estimated_duration = 120  # 2 minutes

        elif metadata.action_type == "external_api_call":
            # External API calls may not be reversible
            if metadata.has_side_effects:
                is_viable = False
                non_viable_reason = (
                    "External API call with side effects cannot be reversed"
                )
            else:
                steps = [
                    {"step": 1, "action": "Call compensating API", "type": "execute"},
                    {"step": 2, "action": "Verify external state", "type": "verify"},
                ]
                estimated_duration = 60
                side_effects = ["May trigger additional notifications"]

        elif metadata.action_type in ("notification_send", "email_send"):
            is_viable = False
            non_viable_reason = "Sent communications cannot be unsent"

        else:
            # Generic rollback plan
            steps = [
                {"step": 1, "action": "Assess current state", "type": "query"},
                {"step": 2, "action": "Prepare reversal", "type": "prepare"},
                {"step": 3, "action": "Execute reversal", "type": "execute"},
                {"step": 4, "action": "Verify restoration", "type": "verify"},
            ]
            estimated_duration = 180

        plan = RollbackPlan(
            plan_id=plan_id,
            action_id=action_id,
            steps=steps,
            estimated_duration_seconds=estimated_duration,
            potential_side_effects=side_effects,
            requires_downtime=requires_downtime,
            is_viable=is_viable,
            non_viable_reason=non_viable_reason,
        )

        # Store plan
        self._rollback_plans[action_id] = plan

        logger.debug(
            f"Generated rollback plan {plan_id} for action {action_id} "
            f"(viable: {is_viable})"
        )
        return plan

    def _get_conditions(
        self,
        action_class: ActionClass,
        metadata: ActionMetadata,
    ) -> list[str]:
        """Get conditions/warnings for an approved action."""
        conditions = []

        if action_class == ActionClass.PARTIALLY_REVERSIBLE:
            conditions.append("Rollback plan stored; review before proceeding")

        if metadata.is_production:
            conditions.append("Production environment - proceed with caution")

        if metadata.affects_external_system:
            conditions.append("Affects external systems - verify availability")

        if metadata.estimated_impact_scope == "system":
            conditions.append("System-wide impact - consider staged rollout")

        return conditions

    def get_metrics(self) -> dict:
        """Get reversibility metrics."""
        with self._lock:
            total = self._class_a_count + self._class_b_count + self._class_c_count
            return {
                "classifications": {
                    "class_a": self._class_a_count,
                    "class_b": self._class_b_count,
                    "class_c": self._class_c_count,
                    "total": total,
                },
                "rollbacks": {
                    "attempted": self._rollbacks_attempted,
                    "successful": self._rollbacks_successful,
                    "success_rate": (
                        self._rollbacks_successful / self._rollbacks_attempted
                        if self._rollbacks_attempted > 0
                        else 1.0
                    ),
                },
                "snapshots_stored": len(self._snapshots),
                "rollback_plans_stored": len(self._rollback_plans),
            }

    def cleanup_expired_snapshots(self) -> int:
        """Remove expired snapshots. Returns count of removed snapshots."""
        with self._lock:
            now = datetime.now(timezone.utc)
            expired = [
                sid
                for sid, snap in self._snapshots.items()
                if snap.expires_at and snap.expires_at < now
            ]
            for sid in expired:
                del self._snapshots[sid]

            if expired:
                logger.info(f"Cleaned up {len(expired)} expired snapshots")

            return len(expired)
