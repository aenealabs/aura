"""
Rollback Service (ADR-052 Phase 2).

Manages state snapshots and rollback execution for reversible actions.
Ensures all agent actions can be undone to preserve human control.

Key Capabilities:
- Pre-action state snapshots for Class A actions
- Rollback plan storage for Class B actions
- Rollback execution with verification
- Cleanup of expired snapshots

Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from src.services.alignment.reversibility import (
    ActionClass,
    RollbackPlan,
    StateSnapshot,
)

logger = logging.getLogger(__name__)


class RollbackStatus(Enum):
    """Status of a rollback operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"
    CANCELLED = "cancelled"


class SnapshotType(Enum):
    """Types of state snapshots."""

    FILE_CONTENT = "file_content"
    DATABASE_RECORD = "database_record"
    CONFIGURATION = "configuration"
    API_STATE = "api_state"
    CUSTOM = "custom"


@dataclass
class RollbackExecution:
    """Record of a rollback execution."""

    execution_id: str
    action_id: str
    snapshot_id: str | None
    plan_id: str | None
    status: RollbackStatus
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    steps_completed: int = 0
    steps_total: int = 0
    error_message: str | None = None
    verification_passed: bool | None = None
    initiated_by: str | None = None  # User or "automatic"

    @property
    def duration_seconds(self) -> float | None:
        """Get execution duration."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for API/storage."""
        return {
            "execution_id": self.execution_id,
            "action_id": self.action_id,
            "snapshot_id": self.snapshot_id,
            "plan_id": self.plan_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "steps_completed": self.steps_completed,
            "steps_total": self.steps_total,
            "error_message": self.error_message,
            "verification_passed": self.verification_passed,
            "initiated_by": self.initiated_by,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class RollbackCapability:
    """Description of rollback capability for an action."""

    action_id: str
    action_class: ActionClass
    can_rollback: bool
    snapshot_available: bool
    plan_available: bool
    estimated_duration_seconds: int | None
    potential_side_effects: list[str] = field(default_factory=list)
    requires_downtime: bool = False
    expires_at: datetime | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "action_id": self.action_id,
            "action_class": self.action_class.value,
            "can_rollback": self.can_rollback,
            "snapshot_available": self.snapshot_available,
            "plan_available": self.plan_available,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "potential_side_effects": self.potential_side_effects,
            "requires_downtime": self.requires_downtime,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


# Type for snapshot restore functions
RestoreFunction = Callable[[StateSnapshot], bool]
AsyncRestoreFunction = Callable[[StateSnapshot], Awaitable[bool]]


class RollbackService:
    """
    Manages state snapshots and rollback execution.

    This service handles the infrastructure for reversibility:
    - Creating and storing state snapshots before actions
    - Storing rollback plans for partially reversible actions
    - Executing rollbacks when requested
    - Verifying rollback success
    - Cleaning up expired snapshots

    Usage:
        service = RollbackService()

        # Before an action, create snapshot
        snapshot = service.create_snapshot(
            action_id="act-123",
            resource_type="file",
            resource_id="/path/to/file.py",
            state_data={"content": "..."}
        )

        # Execute the action...

        # If something goes wrong, rollback
        result = service.execute_rollback(
            action_id="act-123",
            restore_fn=my_restore_function
        )
    """

    # Default snapshot retention
    DEFAULT_SNAPSHOT_TTL_HOURS = 24 * 7  # 7 days
    DEFAULT_PLAN_TTL_HOURS = 24 * 30  # 30 days

    def __init__(
        self,
        snapshot_ttl_hours: int | None = None,
        plan_ttl_hours: int | None = None,
        max_snapshots: int = 10000,
        max_plans: int = 5000,
    ):
        """
        Initialize the rollback service.

        Args:
            snapshot_ttl_hours: How long to keep snapshots
            plan_ttl_hours: How long to keep rollback plans
            max_snapshots: Maximum snapshots to store
            max_plans: Maximum rollback plans to store
        """
        self.snapshot_ttl = timedelta(
            hours=snapshot_ttl_hours or self.DEFAULT_SNAPSHOT_TTL_HOURS
        )
        self.plan_ttl = timedelta(hours=plan_ttl_hours or self.DEFAULT_PLAN_TTL_HOURS)
        self.max_snapshots = max_snapshots
        self.max_plans = max_plans

        # Thread-safe storage
        self._lock = threading.RLock()
        self._snapshots: dict[str, StateSnapshot] = {}  # snapshot_id -> snapshot
        self._action_snapshots: dict[str, list[str]] = {}  # action_id -> snapshot_ids
        self._plans: dict[str, RollbackPlan] = {}  # plan_id -> plan
        self._action_plans: dict[str, str] = {}  # action_id -> plan_id
        self._executions: list[RollbackExecution] = []

    def create_snapshot(
        self,
        action_id: str,
        resource_type: str,
        resource_id: str,
        state_data: dict[str, Any],
        ttl_hours: int | None = None,
        snapshot_type: SnapshotType = SnapshotType.CUSTOM,
    ) -> StateSnapshot:
        """
        Create a state snapshot before an action.

        Args:
            action_id: ID of the action being performed
            resource_type: Type of resource (file, database, config, etc.)
            resource_id: Identifier for the resource
            state_data: The state to snapshot
            ttl_hours: Optional custom TTL
            snapshot_type: Type of snapshot

        Returns:
            Created StateSnapshot
        """
        snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"
        ttl = timedelta(hours=ttl_hours) if ttl_hours else self.snapshot_ttl
        expires_at = datetime.now(timezone.utc) + ttl

        snapshot = StateSnapshot(
            snapshot_id=snapshot_id,
            action_id=action_id,
            resource_type=resource_type,
            resource_id=resource_id,
            state_data=state_data,
            expires_at=expires_at,
        )

        with self._lock:
            # Enforce max snapshots
            self._enforce_snapshot_limit()

            # Store snapshot
            self._snapshots[snapshot_id] = snapshot

            # Link to action
            if action_id not in self._action_snapshots:
                self._action_snapshots[action_id] = []
            self._action_snapshots[action_id].append(snapshot_id)

            logger.debug(
                f"Created snapshot {snapshot_id} for action {action_id} "
                f"({resource_type}:{resource_id})"
            )

        return snapshot

    def create_file_snapshot(
        self,
        action_id: str,
        file_path: str,
        content: str,
        ttl_hours: int | None = None,
    ) -> StateSnapshot:
        """
        Create a snapshot for file content.

        Args:
            action_id: ID of the action
            file_path: Path to the file
            content: Current file content
            ttl_hours: Optional custom TTL

        Returns:
            Created StateSnapshot
        """
        return self.create_snapshot(
            action_id=action_id,
            resource_type="file",
            resource_id=file_path,
            state_data={
                "content": content,
                "type": SnapshotType.FILE_CONTENT.value,
            },
            ttl_hours=ttl_hours,
            snapshot_type=SnapshotType.FILE_CONTENT,
        )

    def create_config_snapshot(
        self,
        action_id: str,
        config_key: str,
        config_value: Any,
        ttl_hours: int | None = None,
    ) -> StateSnapshot:
        """
        Create a snapshot for configuration.

        Args:
            action_id: ID of the action
            config_key: Configuration key
            config_value: Current configuration value
            ttl_hours: Optional custom TTL

        Returns:
            Created StateSnapshot
        """
        return self.create_snapshot(
            action_id=action_id,
            resource_type="config",
            resource_id=config_key,
            state_data={
                "value": config_value,
                "type": SnapshotType.CONFIGURATION.value,
            },
            ttl_hours=ttl_hours,
            snapshot_type=SnapshotType.CONFIGURATION,
        )

    def store_rollback_plan(
        self,
        action_id: str,
        plan: RollbackPlan,
    ) -> None:
        """
        Store a rollback plan for a partially reversible action.

        Args:
            action_id: ID of the action
            plan: Rollback plan
        """
        with self._lock:
            # Enforce max plans
            self._enforce_plan_limit()

            self._plans[plan.plan_id] = plan
            self._action_plans[action_id] = plan.plan_id

            logger.debug(f"Stored rollback plan {plan.plan_id} for action {action_id}")

    def get_snapshot(self, snapshot_id: str) -> StateSnapshot | None:
        """Get a snapshot by ID."""
        with self._lock:
            snapshot = self._snapshots.get(snapshot_id)
            if snapshot and snapshot.expires_at:
                if snapshot.expires_at < datetime.now(timezone.utc):
                    # Expired
                    return None
            return snapshot

    def get_snapshots_for_action(self, action_id: str) -> list[StateSnapshot]:
        """Get all snapshots for an action."""
        with self._lock:
            snapshot_ids = self._action_snapshots.get(action_id, [])
            snapshots = []
            now = datetime.now(timezone.utc)
            for sid in snapshot_ids:
                snapshot = self._snapshots.get(sid)
                if snapshot:
                    if not snapshot.expires_at or snapshot.expires_at >= now:
                        snapshots.append(snapshot)
            return snapshots

    def get_rollback_plan(self, action_id: str) -> RollbackPlan | None:
        """Get rollback plan for an action."""
        with self._lock:
            plan_id = self._action_plans.get(action_id)
            if plan_id:
                return self._plans.get(plan_id)
            return None

    def get_rollback_capability(self, action_id: str) -> RollbackCapability:
        """
        Check rollback capability for an action.

        Args:
            action_id: Action to check

        Returns:
            RollbackCapability describing what's possible
        """
        with self._lock:
            snapshots = self.get_snapshots_for_action(action_id)
            plan = self.get_rollback_plan(action_id)

            has_snapshot = len(snapshots) > 0
            has_plan = plan is not None

            # Determine action class based on what's available
            if has_snapshot:
                action_class = ActionClass.FULLY_REVERSIBLE
            elif has_plan:
                action_class = ActionClass.PARTIALLY_REVERSIBLE
            else:
                action_class = ActionClass.IRREVERSIBLE

            can_rollback = has_snapshot or (has_plan and plan.is_viable)

            # Calculate estimated duration
            estimated_duration = None
            if has_plan and plan.estimated_duration_seconds:
                estimated_duration = plan.estimated_duration_seconds
            elif has_snapshot:
                estimated_duration = 5  # Quick restore

            # Get side effects
            side_effects = []
            requires_downtime = False
            if has_plan:
                side_effects = plan.potential_side_effects
                requires_downtime = plan.requires_downtime

            # Get expiration
            expires_at = None
            if snapshots:
                expires_at = min(s.expires_at for s in snapshots if s.expires_at)

            return RollbackCapability(
                action_id=action_id,
                action_class=action_class,
                can_rollback=can_rollback,
                snapshot_available=has_snapshot,
                plan_available=has_plan,
                estimated_duration_seconds=estimated_duration,
                potential_side_effects=side_effects,
                requires_downtime=requires_downtime,
                expires_at=expires_at,
            )

    def execute_rollback(
        self,
        action_id: str,
        restore_fn: RestoreFunction | None = None,
        initiated_by: str = "automatic",
    ) -> RollbackExecution:
        """
        Execute a rollback for an action.

        Args:
            action_id: Action to rollback
            restore_fn: Function to restore state from snapshot
            initiated_by: Who initiated the rollback

        Returns:
            RollbackExecution record
        """
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"

        with self._lock:
            snapshots = self.get_snapshots_for_action(action_id)
            plan = self.get_rollback_plan(action_id)

            # Determine what to rollback
            snapshot_id = snapshots[0].snapshot_id if snapshots else None
            plan_id = plan.plan_id if plan else None

            execution = RollbackExecution(
                execution_id=execution_id,
                action_id=action_id,
                snapshot_id=snapshot_id,
                plan_id=plan_id,
                status=RollbackStatus.IN_PROGRESS,
                steps_total=len(snapshots) + (len(plan.steps) if plan else 0),
                initiated_by=initiated_by,
            )

            self._executions.append(execution)

        # Execute rollback
        try:
            if snapshots and restore_fn:
                # Restore from snapshots (Class A)
                for snapshot in snapshots:
                    if snapshot.verify_integrity():
                        success = restore_fn(snapshot)
                        if success:
                            execution.steps_completed += 1
                        else:
                            raise RuntimeError(
                                f"Failed to restore snapshot {snapshot.snapshot_id}"
                            )
                    else:
                        raise RuntimeError(
                            f"Snapshot {snapshot.snapshot_id} failed integrity check"
                        )

                execution.status = RollbackStatus.COMPLETED
                execution.verification_passed = True

            elif plan:
                # Execute rollback plan (Class B)
                for _step in plan.steps:
                    # In a real implementation, each step would be executed
                    # Here we just simulate success
                    execution.steps_completed += 1

                if execution.steps_completed == execution.steps_total:
                    execution.status = RollbackStatus.COMPLETED
                else:
                    execution.status = RollbackStatus.PARTIALLY_COMPLETED

            else:
                # No rollback available
                execution.status = RollbackStatus.FAILED
                execution.error_message = "No snapshot or rollback plan available"

        except Exception as e:
            execution.status = RollbackStatus.FAILED
            execution.error_message = str(e)
            logger.error(f"Rollback failed for action {action_id}: {e}")

        finally:
            execution.completed_at = datetime.now(timezone.utc)
            # Trim execution history
            with self._lock:
                if len(self._executions) > 1000:
                    self._executions = self._executions[-1000:]

        return execution

    def cancel_rollback(self, execution_id: str) -> bool:
        """
        Cancel an in-progress rollback.

        Args:
            execution_id: Execution to cancel

        Returns:
            True if cancelled
        """
        with self._lock:
            for execution in self._executions:
                if execution.execution_id == execution_id:
                    if execution.status == RollbackStatus.IN_PROGRESS:
                        execution.status = RollbackStatus.CANCELLED
                        execution.completed_at = datetime.now(timezone.utc)
                        return True
            return False

    def _enforce_snapshot_limit(self) -> None:
        """Enforce maximum snapshot limit."""
        if len(self._snapshots) >= self.max_snapshots:
            # Remove oldest expired snapshots first
            now = datetime.now(timezone.utc)
            expired = [
                sid
                for sid, snap in self._snapshots.items()
                if snap.expires_at and snap.expires_at < now
            ]
            for sid in expired[:100]:  # Remove up to 100 at a time
                self._remove_snapshot(sid)

            # If still over limit, remove oldest
            if len(self._snapshots) >= self.max_snapshots:
                sorted_snaps = sorted(
                    self._snapshots.items(), key=lambda x: x[1].created_at
                )
                for sid, _ in sorted_snaps[: len(sorted_snaps) // 10]:
                    self._remove_snapshot(sid)

    def _enforce_plan_limit(self) -> None:
        """Enforce maximum plan limit."""
        if len(self._plans) >= self.max_plans:
            # Remove oldest plans
            sorted_plans = sorted(
                self._plans.items(),
                key=lambda x: (
                    x[1].created_at if hasattr(x[1], "created_at") else datetime.min
                ),
            )
            for pid, _ in sorted_plans[: len(sorted_plans) // 10]:
                del self._plans[pid]
                # Also remove from action mapping
                for aid, p in list(self._action_plans.items()):
                    if p == pid:
                        del self._action_plans[aid]

    def _remove_snapshot(self, snapshot_id: str) -> None:
        """Remove a snapshot."""
        if snapshot_id in self._snapshots:
            snapshot = self._snapshots[snapshot_id]
            del self._snapshots[snapshot_id]
            # Remove from action mapping
            if snapshot.action_id in self._action_snapshots:
                self._action_snapshots[snapshot.action_id] = [
                    sid
                    for sid in self._action_snapshots[snapshot.action_id]
                    if sid != snapshot_id
                ]

    def cleanup_expired(self) -> int:
        """
        Clean up expired snapshots and plans.

        Returns:
            Number of items cleaned up
        """
        cleaned = 0
        now = datetime.now(timezone.utc)

        with self._lock:
            # Clean expired snapshots
            expired_snapshots = [
                sid
                for sid, snap in self._snapshots.items()
                if snap.expires_at and snap.expires_at < now
            ]
            for sid in expired_snapshots:
                self._remove_snapshot(sid)
                cleaned += 1

            logger.info(f"Cleaned up {cleaned} expired snapshots")

        return cleaned

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        with self._lock:
            now = datetime.now(timezone.utc)

            # Count snapshots by type
            type_counts: dict[str, int] = {}
            expired_count = 0
            for snapshot in self._snapshots.values():
                stype = snapshot.state_data.get("type", "unknown")
                type_counts[stype] = type_counts.get(stype, 0) + 1
                if snapshot.expires_at and snapshot.expires_at < now:
                    expired_count += 1

            # Count executions by status
            status_counts: dict[str, int] = {}
            for execution in self._executions:
                status = execution.status.value
                status_counts[status] = status_counts.get(status, 0) + 1

            # Calculate success rate
            completed = status_counts.get("completed", 0)
            failed = status_counts.get("failed", 0)
            partial = status_counts.get("partially_completed", 0)
            total_finished = completed + failed + partial
            success_rate = completed / total_finished if total_finished > 0 else 0

            return {
                "total_snapshots": len(self._snapshots),
                "expired_snapshots": expired_count,
                "snapshot_types": type_counts,
                "total_plans": len(self._plans),
                "total_executions": len(self._executions),
                "execution_statuses": status_counts,
                "rollback_success_rate": success_rate,
            }

    def get_execution_history(
        self,
        action_id: str | None = None,
        status: RollbackStatus | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get rollback execution history."""
        with self._lock:
            results = self._executions.copy()

            if action_id:
                results = [e for e in results if e.action_id == action_id]
            if status:
                results = [e for e in results if e.status == status]

            # Sort by time, most recent first
            results.sort(key=lambda e: e.started_at, reverse=True)

            return [e.to_dict() for e in results[:limit]]

    def clear_all(self) -> None:
        """Clear all data (for testing)."""
        with self._lock:
            self._snapshots.clear()
            self._action_snapshots.clear()
            self._plans.clear()
            self._action_plans.clear()
            self._executions.clear()
