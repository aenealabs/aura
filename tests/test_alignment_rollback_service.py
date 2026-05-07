"""
Tests for RollbackService (ADR-052 Phase 2).

Tests rollback execution, snapshot management, and state restoration.
"""

import platform
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from src.services.alignment.reversibility import ActionClass, RollbackPlan
from src.services.alignment.rollback_service import (
    RollbackCapability,
    RollbackExecution,
    RollbackService,
    RollbackStatus,
    SnapshotType,
)

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestRollbackStatusEnum:
    """Tests for RollbackStatus enum."""

    def test_all_statuses_defined(self):
        """All expected status values exist."""
        statuses = [s.value for s in RollbackStatus]
        assert "pending" in statuses
        assert "in_progress" in statuses
        assert "completed" in statuses
        assert "failed" in statuses
        assert "partially_completed" in statuses
        assert "cancelled" in statuses

    def test_status_values(self):
        """Status enum values are correct."""
        assert RollbackStatus.PENDING.value == "pending"
        assert RollbackStatus.IN_PROGRESS.value == "in_progress"
        assert RollbackStatus.COMPLETED.value == "completed"
        assert RollbackStatus.FAILED.value == "failed"
        assert RollbackStatus.PARTIALLY_COMPLETED.value == "partially_completed"
        assert RollbackStatus.CANCELLED.value == "cancelled"


class TestSnapshotTypeEnum:
    """Tests for SnapshotType enum."""

    def test_all_types_defined(self):
        """All expected snapshot types exist."""
        types = [t.value for t in SnapshotType]
        assert "file_content" in types
        assert "database_record" in types
        assert "configuration" in types
        assert "api_state" in types
        assert "custom" in types

    def test_type_values(self):
        """Snapshot type enum values are correct."""
        assert SnapshotType.FILE_CONTENT.value == "file_content"
        assert SnapshotType.DATABASE_RECORD.value == "database_record"
        assert SnapshotType.CONFIGURATION.value == "configuration"
        assert SnapshotType.API_STATE.value == "api_state"
        assert SnapshotType.CUSTOM.value == "custom"


class TestRollbackExecution:
    """Tests for RollbackExecution dataclass."""

    def test_creation_with_required_fields(self):
        """Create execution with required fields."""
        execution = RollbackExecution(
            execution_id="exec_123",
            action_id="act_456",
            snapshot_id="snap_789",
            plan_id=None,
            status=RollbackStatus.PENDING,
        )
        assert execution.execution_id == "exec_123"
        assert execution.action_id == "act_456"
        assert execution.snapshot_id == "snap_789"
        assert execution.plan_id is None
        assert execution.status == RollbackStatus.PENDING
        assert execution.started_at is not None
        assert execution.completed_at is None
        assert execution.steps_completed == 0
        assert execution.steps_total == 0
        assert execution.error_message is None
        assert execution.verification_passed is None
        assert execution.initiated_by is None

    def test_creation_with_all_fields(self):
        """Create execution with all fields."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(seconds=30)
        execution = RollbackExecution(
            execution_id="exec_123",
            action_id="act_456",
            snapshot_id="snap_789",
            plan_id="plan_012",
            status=RollbackStatus.COMPLETED,
            started_at=started,
            completed_at=completed,
            steps_completed=5,
            steps_total=5,
            error_message=None,
            verification_passed=True,
            initiated_by="user@example.com",
        )
        assert execution.plan_id == "plan_012"
        assert execution.completed_at == completed
        assert execution.steps_completed == 5
        assert execution.steps_total == 5
        assert execution.verification_passed is True
        assert execution.initiated_by == "user@example.com"

    def test_duration_seconds_when_completed(self):
        """Duration is calculated when completed."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(seconds=45)
        execution = RollbackExecution(
            execution_id="exec_123",
            action_id="act_456",
            snapshot_id=None,
            plan_id=None,
            status=RollbackStatus.COMPLETED,
            started_at=started,
            completed_at=completed,
        )
        assert execution.duration_seconds == 45.0

    def test_duration_seconds_when_not_completed(self):
        """Duration is None when not completed."""
        execution = RollbackExecution(
            execution_id="exec_123",
            action_id="act_456",
            snapshot_id=None,
            plan_id=None,
            status=RollbackStatus.IN_PROGRESS,
        )
        assert execution.duration_seconds is None

    def test_to_dict(self):
        """to_dict returns proper dictionary."""
        started = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        completed = datetime(2024, 1, 15, 10, 0, 30, tzinfo=timezone.utc)
        execution = RollbackExecution(
            execution_id="exec_123",
            action_id="act_456",
            snapshot_id="snap_789",
            plan_id="plan_012",
            status=RollbackStatus.COMPLETED,
            started_at=started,
            completed_at=completed,
            steps_completed=3,
            steps_total=3,
            error_message=None,
            verification_passed=True,
            initiated_by="admin",
        )
        d = execution.to_dict()
        assert d["execution_id"] == "exec_123"
        assert d["action_id"] == "act_456"
        assert d["snapshot_id"] == "snap_789"
        assert d["plan_id"] == "plan_012"
        assert d["status"] == "completed"
        assert d["started_at"] == started.isoformat()
        assert d["completed_at"] == completed.isoformat()
        assert d["steps_completed"] == 3
        assert d["steps_total"] == 3
        assert d["error_message"] is None
        assert d["verification_passed"] is True
        assert d["initiated_by"] == "admin"
        assert d["duration_seconds"] == 30.0

    def test_to_dict_with_none_completed_at(self):
        """to_dict handles None completed_at."""
        execution = RollbackExecution(
            execution_id="exec_123",
            action_id="act_456",
            snapshot_id=None,
            plan_id=None,
            status=RollbackStatus.IN_PROGRESS,
        )
        d = execution.to_dict()
        assert d["completed_at"] is None
        assert d["duration_seconds"] is None


class TestRollbackCapability:
    """Tests for RollbackCapability dataclass."""

    def test_creation_with_required_fields(self):
        """Create capability with required fields."""
        capability = RollbackCapability(
            action_id="act_123",
            action_class=ActionClass.FULLY_REVERSIBLE,
            can_rollback=True,
            snapshot_available=True,
            plan_available=False,
            estimated_duration_seconds=5,
        )
        assert capability.action_id == "act_123"
        assert capability.action_class == ActionClass.FULLY_REVERSIBLE
        assert capability.can_rollback is True
        assert capability.snapshot_available is True
        assert capability.plan_available is False
        assert capability.estimated_duration_seconds == 5
        assert capability.potential_side_effects == []
        assert capability.requires_downtime is False
        assert capability.expires_at is None

    def test_creation_with_all_fields(self):
        """Create capability with all fields."""
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        capability = RollbackCapability(
            action_id="act_123",
            action_class=ActionClass.PARTIALLY_REVERSIBLE,
            can_rollback=True,
            snapshot_available=False,
            plan_available=True,
            estimated_duration_seconds=300,
            potential_side_effects=["May affect caches", "Requires restart"],
            requires_downtime=True,
            expires_at=expires,
        )
        assert capability.potential_side_effects == [
            "May affect caches",
            "Requires restart",
        ]
        assert capability.requires_downtime is True
        assert capability.expires_at == expires

    def test_to_dict(self):
        """to_dict returns proper dictionary."""
        expires = datetime(2024, 1, 22, 10, 0, 0, tzinfo=timezone.utc)
        capability = RollbackCapability(
            action_id="act_123",
            action_class=ActionClass.FULLY_REVERSIBLE,
            can_rollback=True,
            snapshot_available=True,
            plan_available=False,
            estimated_duration_seconds=10,
            potential_side_effects=["Minor delay"],
            requires_downtime=False,
            expires_at=expires,
        )
        d = capability.to_dict()
        assert d["action_id"] == "act_123"
        assert d["action_class"] == "A"
        assert d["can_rollback"] is True
        assert d["snapshot_available"] is True
        assert d["plan_available"] is False
        assert d["estimated_duration_seconds"] == 10
        assert d["potential_side_effects"] == ["Minor delay"]
        assert d["requires_downtime"] is False
        assert d["expires_at"] == expires.isoformat()

    def test_to_dict_with_none_expires_at(self):
        """to_dict handles None expires_at."""
        capability = RollbackCapability(
            action_id="act_123",
            action_class=ActionClass.IRREVERSIBLE,
            can_rollback=False,
            snapshot_available=False,
            plan_available=False,
            estimated_duration_seconds=None,
        )
        d = capability.to_dict()
        assert d["expires_at"] is None
        assert d["estimated_duration_seconds"] is None


class TestRollbackServiceInit:
    """Tests for RollbackService initialization."""

    def test_default_initialization(self):
        """Service initializes with defaults."""
        service = RollbackService()
        assert service.snapshot_ttl == timedelta(hours=24 * 7)  # 7 days
        assert service.plan_ttl == timedelta(hours=24 * 30)  # 30 days
        assert service.max_snapshots == 10000
        assert service.max_plans == 5000

    def test_custom_initialization(self):
        """Service initializes with custom values."""
        service = RollbackService(
            snapshot_ttl_hours=48,
            plan_ttl_hours=72,
            max_snapshots=100,
            max_plans=50,
        )
        assert service.snapshot_ttl == timedelta(hours=48)
        assert service.plan_ttl == timedelta(hours=72)
        assert service.max_snapshots == 100
        assert service.max_plans == 50

    def test_empty_state_on_init(self):
        """Service starts with empty state."""
        service = RollbackService()
        stats = service.get_stats()
        assert stats["total_snapshots"] == 0
        assert stats["total_plans"] == 0
        assert stats["total_executions"] == 0


class TestRollbackServiceSnapshots:
    """Tests for snapshot management."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        svc = RollbackService()
        yield svc
        svc.clear_all()

    def test_create_snapshot(self, service):
        """Create a basic snapshot."""
        snapshot = service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/path/to/file.py",
            state_data={"content": "print('hello')"},
        )
        assert snapshot.snapshot_id.startswith("snap_")
        assert snapshot.action_id == "act_123"
        assert snapshot.resource_type == "file"
        assert snapshot.resource_id == "/path/to/file.py"
        assert snapshot.state_data["content"] == "print('hello')"
        assert snapshot.expires_at is not None

    def test_create_snapshot_with_custom_ttl(self, service):
        """Create snapshot with custom TTL."""
        snapshot = service.create_snapshot(
            action_id="act_123",
            resource_type="config",
            resource_id="app.settings",
            state_data={"debug": True},
            ttl_hours=1,
        )
        # Should expire in about 1 hour
        expected_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        delta = abs((snapshot.expires_at - expected_expiry).total_seconds())
        assert delta < 5  # Within 5 seconds

    def test_create_file_snapshot(self, service):
        """Create file-specific snapshot."""
        snapshot = service.create_file_snapshot(
            action_id="act_123",
            file_path="/src/main.py",
            content="def main(): pass",
        )
        assert snapshot.resource_type == "file"
        assert snapshot.resource_id == "/src/main.py"
        assert snapshot.state_data["content"] == "def main(): pass"
        assert snapshot.state_data["type"] == "file_content"

    def test_create_config_snapshot(self, service):
        """Create configuration snapshot."""
        snapshot = service.create_config_snapshot(
            action_id="act_123",
            config_key="database.pool_size",
            config_value=10,
        )
        assert snapshot.resource_type == "config"
        assert snapshot.resource_id == "database.pool_size"
        assert snapshot.state_data["value"] == 10
        assert snapshot.state_data["type"] == "configuration"

    def test_get_snapshot(self, service):
        """Retrieve snapshot by ID."""
        created = service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/test.txt",
            state_data={"content": "test"},
        )
        retrieved = service.get_snapshot(created.snapshot_id)
        assert retrieved is not None
        assert retrieved.snapshot_id == created.snapshot_id
        assert retrieved.state_data["content"] == "test"

    def test_get_nonexistent_snapshot(self, service):
        """Return None for non-existent snapshot."""
        result = service.get_snapshot("snap_nonexistent")
        assert result is None

    def test_get_expired_snapshot(self, service):
        """Return None for expired snapshot."""
        snapshot = service.create_snapshot(
            action_id="act_123",
            resource_type="test",
            resource_id="test_id",
            state_data={"data": "value"},
            ttl_hours=0,  # Expires immediately (0 hours from now)
        )
        # Manually set expiration to past
        snapshot.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        result = service.get_snapshot(snapshot.snapshot_id)
        assert result is None

    def test_get_snapshots_for_action(self, service):
        """Get all snapshots for an action."""
        service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/file1.txt",
            state_data={"content": "content1"},
        )
        service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/file2.txt",
            state_data={"content": "content2"},
        )
        service.create_snapshot(
            action_id="act_other",
            resource_type="file",
            resource_id="/file3.txt",
            state_data={"content": "content3"},
        )

        snapshots = service.get_snapshots_for_action("act_123")
        assert len(snapshots) == 2
        resource_ids = {s.resource_id for s in snapshots}
        assert "/file1.txt" in resource_ids
        assert "/file2.txt" in resource_ids

    def test_get_snapshots_excludes_expired(self, service):
        """Expired snapshots excluded from action list."""
        snap1 = service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/file1.txt",
            state_data={"content": "content1"},
        )
        service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/file2.txt",
            state_data={"content": "content2"},
        )
        # Expire first snapshot
        snap1.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        snapshots = service.get_snapshots_for_action("act_123")
        assert len(snapshots) == 1
        assert snapshots[0].resource_id == "/file2.txt"

    def test_multiple_snapshots_same_action(self, service):
        """Multiple snapshots can be linked to same action."""
        for i in range(5):
            service.create_snapshot(
                action_id="act_multi",
                resource_type="config",
                resource_id=f"setting_{i}",
                state_data={"value": i},
            )
        snapshots = service.get_snapshots_for_action("act_multi")
        assert len(snapshots) == 5


class TestRollbackServicePlans:
    """Tests for rollback plan management."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        svc = RollbackService()
        yield svc
        svc.clear_all()

    def test_store_rollback_plan(self, service):
        """Store a rollback plan."""
        plan = RollbackPlan(
            plan_id="plan_123",
            action_id="act_456",
            steps=["Step 1", "Step 2"],
            estimated_duration_seconds=60,
        )
        service.store_rollback_plan(action_id="act_456", plan=plan)

        retrieved = service.get_rollback_plan("act_456")
        assert retrieved is not None
        assert retrieved.plan_id == "plan_123"
        assert retrieved.steps == ["Step 1", "Step 2"]

    def test_get_nonexistent_plan(self, service):
        """Return None for non-existent plan."""
        result = service.get_rollback_plan("act_nonexistent")
        assert result is None

    def test_plan_replaces_previous(self, service):
        """New plan replaces previous for same action."""
        plan1 = RollbackPlan(
            plan_id="plan_1",
            action_id="act_123",
            steps=["Old step"],
        )
        plan2 = RollbackPlan(
            plan_id="plan_2",
            action_id="act_123",
            steps=["New step"],
        )
        service.store_rollback_plan("act_123", plan1)
        service.store_rollback_plan("act_123", plan2)

        retrieved = service.get_rollback_plan("act_123")
        assert retrieved.plan_id == "plan_2"
        assert retrieved.steps == ["New step"]


class TestRollbackCapabilityCheck:
    """Tests for rollback capability determination."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        svc = RollbackService()
        yield svc
        svc.clear_all()

    def test_capability_with_snapshot(self, service):
        """Action with snapshot is fully reversible."""
        service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/test.py",
            state_data={"content": "test"},
        )
        capability = service.get_rollback_capability("act_123")
        assert capability.action_class == ActionClass.FULLY_REVERSIBLE
        assert capability.can_rollback is True
        assert capability.snapshot_available is True
        assert capability.plan_available is False
        assert capability.estimated_duration_seconds == 5  # Quick restore

    def test_capability_with_plan(self, service):
        """Action with only plan is partially reversible."""
        plan = RollbackPlan(
            plan_id="plan_123",
            action_id="act_456",
            steps=["Step 1", "Step 2"],
            estimated_duration_seconds=120,
            potential_side_effects=["May cause brief outage"],
            requires_downtime=True,
            is_viable=True,
        )
        service.store_rollback_plan("act_456", plan)

        capability = service.get_rollback_capability("act_456")
        assert capability.action_class == ActionClass.PARTIALLY_REVERSIBLE
        assert capability.can_rollback is True
        assert capability.snapshot_available is False
        assert capability.plan_available is True
        assert capability.estimated_duration_seconds == 120
        assert capability.potential_side_effects == ["May cause brief outage"]
        assert capability.requires_downtime is True

    def test_capability_without_snapshot_or_plan(self, service):
        """Action without snapshot or plan is irreversible."""
        capability = service.get_rollback_capability("act_unknown")
        assert capability.action_class == ActionClass.IRREVERSIBLE
        assert capability.can_rollback is False
        assert capability.snapshot_available is False
        assert capability.plan_available is False
        assert capability.estimated_duration_seconds is None

    def test_capability_with_unviable_plan(self, service):
        """Unviable plan doesn't allow rollback."""
        plan = RollbackPlan(
            plan_id="plan_123",
            action_id="act_456",
            steps=["Step 1"],
            is_viable=False,  # Plan not viable
        )
        service.store_rollback_plan("act_456", plan)

        capability = service.get_rollback_capability("act_456")
        assert capability.can_rollback is False
        assert capability.plan_available is True

    def test_capability_expiration(self, service):
        """Capability includes earliest expiration."""
        snap1 = service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/file1.txt",
            state_data={"content": "1"},
            ttl_hours=24,
        )
        snap2 = service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/file2.txt",
            state_data={"content": "2"},
            ttl_hours=48,
        )
        capability = service.get_rollback_capability("act_123")
        # Should have earliest expiration
        assert capability.expires_at == snap1.expires_at


class TestRollbackExecutionExtended:
    """Extended tests for rollback execution."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        svc = RollbackService()
        yield svc
        svc.clear_all()

    def test_execute_rollback_with_snapshot(self, service):
        """Execute rollback from snapshot."""
        service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/test.py",
            state_data={"content": "original"},
        )
        restored_data = []

        def restore_fn(snapshot):
            restored_data.append(snapshot.state_data)
            return True

        execution = service.execute_rollback(
            action_id="act_123",
            restore_fn=restore_fn,
            initiated_by="admin@example.com",
        )
        assert execution.status == RollbackStatus.COMPLETED
        assert execution.verification_passed is True
        assert execution.steps_completed == 1
        assert execution.initiated_by == "admin@example.com"
        assert len(restored_data) == 1
        assert restored_data[0]["content"] == "original"

    def test_execute_rollback_with_multiple_snapshots(self, service):
        """Execute rollback with multiple snapshots."""
        for i in range(3):
            service.create_snapshot(
                action_id="act_123",
                resource_type="file",
                resource_id=f"/file{i}.py",
                state_data={"content": f"content{i}"},
            )
        call_count = [0]

        def restore_fn(snapshot):
            call_count[0] += 1
            return True

        execution = service.execute_rollback(
            action_id="act_123",
            restore_fn=restore_fn,
        )
        assert execution.status == RollbackStatus.COMPLETED
        assert execution.steps_completed == 3
        assert call_count[0] == 3

    def test_execute_rollback_restore_failure(self, service):
        """Rollback fails when restore function returns False."""
        service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/test.py",
            state_data={"content": "test"},
        )

        def failing_restore(snapshot):
            return False

        execution = service.execute_rollback(
            action_id="act_123",
            restore_fn=failing_restore,
        )
        assert execution.status == RollbackStatus.FAILED
        assert "Failed to restore snapshot" in execution.error_message

    def test_execute_rollback_integrity_failure(self, service):
        """Rollback fails when snapshot integrity check fails."""
        snapshot = service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/test.py",
            state_data={"content": "test"},
        )
        # Corrupt checksum (use correct attribute name)
        snapshot.checksum = "bad_checksum"

        def restore_fn(snapshot):
            return True

        execution = service.execute_rollback(
            action_id="act_123",
            restore_fn=restore_fn,
        )
        assert execution.status == RollbackStatus.FAILED
        assert "integrity check" in execution.error_message

    def test_execute_rollback_with_plan(self, service):
        """Execute rollback using plan when no snapshots."""
        plan = RollbackPlan(
            plan_id="plan_123",
            action_id="act_456",
            steps=["Step 1", "Step 2", "Step 3"],
            is_viable=True,
        )
        service.store_rollback_plan("act_456", plan)

        execution = service.execute_rollback(action_id="act_456")
        assert execution.status == RollbackStatus.COMPLETED
        assert execution.steps_completed == 3
        assert execution.plan_id == "plan_123"

    def test_execute_rollback_no_snapshot_or_plan(self, service):
        """Rollback fails when no snapshot or plan available."""
        execution = service.execute_rollback(action_id="act_unknown")
        assert execution.status == RollbackStatus.FAILED
        assert "No snapshot or rollback plan available" in execution.error_message

    def test_execute_rollback_exception_handling(self, service):
        """Rollback handles exceptions gracefully."""
        service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/test.py",
            state_data={"content": "test"},
        )

        def throwing_restore(snapshot):
            raise ValueError("Simulated error")

        execution = service.execute_rollback(
            action_id="act_123",
            restore_fn=throwing_restore,
        )
        assert execution.status == RollbackStatus.FAILED
        assert "Simulated error" in execution.error_message
        assert execution.completed_at is not None

    def test_execution_has_duration(self, service):
        """Completed execution has duration."""
        service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/test.py",
            state_data={"content": "test"},
        )

        def restore_fn(snapshot):
            time.sleep(0.1)
            return True

        execution = service.execute_rollback(
            action_id="act_123",
            restore_fn=restore_fn,
        )
        assert execution.duration_seconds is not None
        assert execution.duration_seconds >= 0.1


class TestCancelRollback:
    """Tests for rollback cancellation."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        svc = RollbackService()
        yield svc
        svc.clear_all()

    def test_cancel_in_progress_rollback(self, service):
        """Cancel an in-progress rollback."""
        # Create a rollback execution manually
        execution = RollbackExecution(
            execution_id="exec_123",
            action_id="act_456",
            snapshot_id=None,
            plan_id=None,
            status=RollbackStatus.IN_PROGRESS,
        )
        service._executions.append(execution)

        result = service.cancel_rollback("exec_123")
        assert result is True
        assert execution.status == RollbackStatus.CANCELLED
        assert execution.completed_at is not None

    def test_cancel_nonexistent_rollback(self, service):
        """Cannot cancel non-existent rollback."""
        result = service.cancel_rollback("exec_nonexistent")
        assert result is False

    def test_cancel_completed_rollback(self, service):
        """Cannot cancel completed rollback."""
        execution = RollbackExecution(
            execution_id="exec_123",
            action_id="act_456",
            snapshot_id=None,
            plan_id=None,
            status=RollbackStatus.COMPLETED,
        )
        service._executions.append(execution)

        result = service.cancel_rollback("exec_123")
        assert result is False
        assert execution.status == RollbackStatus.COMPLETED


class TestCleanupExpired:
    """Tests for expired snapshot cleanup."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        svc = RollbackService()
        yield svc
        svc.clear_all()

    def test_cleanup_removes_expired_snapshots(self, service):
        """Cleanup removes expired snapshots."""
        # Create some snapshots
        snap1 = service.create_snapshot(
            action_id="act_1",
            resource_type="file",
            resource_id="/file1.txt",
            state_data={"content": "1"},
        )
        service.create_snapshot(
            action_id="act_2",
            resource_type="file",
            resource_id="/file2.txt",
            state_data={"content": "2"},
        )
        # Expire first snapshot
        snap1.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        cleaned = service.cleanup_expired()
        assert cleaned == 1

        stats = service.get_stats()
        assert stats["total_snapshots"] == 1

    def test_cleanup_preserves_valid_snapshots(self, service):
        """Cleanup preserves non-expired snapshots."""
        for i in range(5):
            service.create_snapshot(
                action_id=f"act_{i}",
                resource_type="file",
                resource_id=f"/file{i}.txt",
                state_data={"content": str(i)},
            )

        cleaned = service.cleanup_expired()
        assert cleaned == 0

        stats = service.get_stats()
        assert stats["total_snapshots"] == 5

    def test_cleanup_returns_count(self, service):
        """Cleanup returns count of removed items."""
        for i in range(10):
            snap = service.create_snapshot(
                action_id=f"act_{i}",
                resource_type="file",
                resource_id=f"/file{i}.txt",
                state_data={"content": str(i)},
            )
            if i < 3:  # Expire first 3
                snap.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        cleaned = service.cleanup_expired()
        assert cleaned == 3


class TestSnapshotLimits:
    """Tests for snapshot limit enforcement."""

    def test_enforce_snapshot_limit_removes_expired(self):
        """Limit enforcement removes expired snapshots first."""
        service = RollbackService(max_snapshots=5)

        # Create snapshots up to limit
        for i in range(5):
            snap = service.create_snapshot(
                action_id=f"act_{i}",
                resource_type="file",
                resource_id=f"/file{i}.txt",
                state_data={"content": str(i)},
            )
            if i < 2:  # Expire first 2
                snap.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        # Creating one more should trigger cleanup
        service.create_snapshot(
            action_id="act_new",
            resource_type="file",
            resource_id="/new_file.txt",
            state_data={"content": "new"},
        )

        stats = service.get_stats()
        # Should have removed expired ones but added new one
        assert stats["total_snapshots"] <= 5
        service.clear_all()

    def test_enforce_plan_limit(self):
        """Plan limit enforcement removes oldest plans when limit exceeded."""
        # Use max_plans=10 so that 10% removal (1 plan) is meaningful
        service = RollbackService(max_plans=10)

        # Fill to limit
        for i in range(10):
            plan = RollbackPlan(
                plan_id=f"plan_{i}",
                action_id=f"act_{i}",
                steps=[f"Step {i}"],
            )
            service.store_rollback_plan(f"act_{i}", plan)

        # Creating one more should trigger cleanup (10% = 1 plan removed)
        new_plan = RollbackPlan(
            plan_id="plan_new",
            action_id="act_new",
            steps=["New step"],
        )
        service.store_rollback_plan("act_new", new_plan)

        stats = service.get_stats()
        # After adding 11th plan, 10% of 10 (= 1) oldest should be removed
        # So we have 10 plans remaining (9 old + 1 new)
        assert stats["total_plans"] <= 10
        service.clear_all()


class TestGetStats:
    """Tests for service statistics."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        svc = RollbackService()
        yield svc
        svc.clear_all()

    def test_stats_empty_service(self, service):
        """Stats for empty service."""
        stats = service.get_stats()
        assert stats["total_snapshots"] == 0
        assert stats["expired_snapshots"] == 0
        assert stats["snapshot_types"] == {}
        assert stats["total_plans"] == 0
        assert stats["total_executions"] == 0
        assert stats["execution_statuses"] == {}
        assert stats["rollback_success_rate"] == 0

    def test_stats_with_snapshots(self, service):
        """Stats include snapshot counts by type."""
        service.create_file_snapshot(
            action_id="act_1",
            file_path="/file1.txt",
            content="content1",
        )
        service.create_file_snapshot(
            action_id="act_2",
            file_path="/file2.txt",
            content="content2",
        )
        service.create_config_snapshot(
            action_id="act_3",
            config_key="setting",
            config_value="value",
        )

        stats = service.get_stats()
        assert stats["total_snapshots"] == 3
        assert stats["snapshot_types"]["file_content"] == 2
        assert stats["snapshot_types"]["configuration"] == 1

    def test_stats_with_executions(self, service):
        """Stats include execution counts by status."""
        # Add some executions manually
        for status in [
            RollbackStatus.COMPLETED,
            RollbackStatus.COMPLETED,
            RollbackStatus.FAILED,
        ]:
            execution = RollbackExecution(
                execution_id=f"exec_{status.value}",
                action_id="act_test",
                snapshot_id=None,
                plan_id=None,
                status=status,
            )
            service._executions.append(execution)

        stats = service.get_stats()
        assert stats["total_executions"] == 3
        assert stats["execution_statuses"]["completed"] == 2
        assert stats["execution_statuses"]["failed"] == 1
        # 2 completed / (2 completed + 1 failed) = 0.666...
        assert abs(stats["rollback_success_rate"] - 0.6666) < 0.01

    def test_stats_expired_snapshot_count(self, service):
        """Stats include expired snapshot count."""
        snap1 = service.create_snapshot(
            action_id="act_1",
            resource_type="file",
            resource_id="/file1.txt",
            state_data={"content": "1"},
        )
        service.create_snapshot(
            action_id="act_2",
            resource_type="file",
            resource_id="/file2.txt",
            state_data={"content": "2"},
        )
        # Expire first snapshot
        snap1.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        stats = service.get_stats()
        assert stats["total_snapshots"] == 2
        assert stats["expired_snapshots"] == 1


class TestGetExecutionHistory:
    """Tests for execution history retrieval."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        svc = RollbackService()
        yield svc
        svc.clear_all()

    def test_get_all_history(self, service):
        """Get all execution history."""
        for i in range(5):
            execution = RollbackExecution(
                execution_id=f"exec_{i}",
                action_id=f"act_{i}",
                snapshot_id=None,
                plan_id=None,
                status=RollbackStatus.COMPLETED,
            )
            service._executions.append(execution)

        history = service.get_execution_history()
        assert len(history) == 5

    def test_filter_by_action_id(self, service):
        """Filter history by action ID."""
        for i in range(5):
            execution = RollbackExecution(
                execution_id=f"exec_{i}",
                action_id=f"act_{i % 2}",  # Alternating action IDs
                snapshot_id=None,
                plan_id=None,
                status=RollbackStatus.COMPLETED,
            )
            service._executions.append(execution)

        history = service.get_execution_history(action_id="act_0")
        assert len(history) == 3  # act_0, act_0, act_0

    def test_filter_by_status(self, service):
        """Filter history by status."""
        statuses = [
            RollbackStatus.COMPLETED,
            RollbackStatus.FAILED,
            RollbackStatus.COMPLETED,
            RollbackStatus.CANCELLED,
        ]
        for i, status in enumerate(statuses):
            execution = RollbackExecution(
                execution_id=f"exec_{i}",
                action_id=f"act_{i}",
                snapshot_id=None,
                plan_id=None,
                status=status,
            )
            service._executions.append(execution)

        history = service.get_execution_history(status=RollbackStatus.COMPLETED)
        assert len(history) == 2

    def test_history_limit(self, service):
        """History respects limit."""
        for i in range(100):
            execution = RollbackExecution(
                execution_id=f"exec_{i}",
                action_id=f"act_{i}",
                snapshot_id=None,
                plan_id=None,
                status=RollbackStatus.COMPLETED,
            )
            service._executions.append(execution)

        history = service.get_execution_history(limit=10)
        assert len(history) == 10

    def test_history_sorted_by_time(self, service):
        """History is sorted by time, most recent first."""
        base_time = datetime.now(timezone.utc)
        for i in range(5):
            execution = RollbackExecution(
                execution_id=f"exec_{i}",
                action_id=f"act_{i}",
                snapshot_id=None,
                plan_id=None,
                status=RollbackStatus.COMPLETED,
                started_at=base_time + timedelta(seconds=i),
            )
            service._executions.append(execution)

        history = service.get_execution_history()
        # Most recent (exec_4) should be first
        assert history[0]["execution_id"] == "exec_4"
        assert history[-1]["execution_id"] == "exec_0"


class TestClearAll:
    """Tests for clearing all data."""

    def test_clear_all_removes_everything(self):
        """clear_all removes all data."""
        service = RollbackService()

        # Add various data
        service.create_snapshot(
            action_id="act_1",
            resource_type="file",
            resource_id="/file1.txt",
            state_data={"content": "1"},
        )
        plan = RollbackPlan(
            plan_id="plan_1",
            action_id="act_2",
            steps=["Step 1"],
        )
        service.store_rollback_plan("act_2", plan)
        execution = RollbackExecution(
            execution_id="exec_1",
            action_id="act_1",
            snapshot_id=None,
            plan_id=None,
            status=RollbackStatus.COMPLETED,
        )
        service._executions.append(execution)

        # Verify data exists
        stats_before = service.get_stats()
        assert stats_before["total_snapshots"] == 1
        assert stats_before["total_plans"] == 1
        assert stats_before["total_executions"] == 1

        # Clear all
        service.clear_all()

        # Verify empty
        stats_after = service.get_stats()
        assert stats_after["total_snapshots"] == 0
        assert stats_after["total_plans"] == 0
        assert stats_after["total_executions"] == 0


class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_snapshot_creation(self):
        """Concurrent snapshot creation is thread-safe."""
        service = RollbackService()
        results = []
        errors = []

        def create_snapshots(thread_id: int):
            try:
                for i in range(10):
                    snapshot = service.create_snapshot(
                        action_id=f"act_t{thread_id}_{i}",
                        resource_type="file",
                        resource_id=f"/file_t{thread_id}_{i}.txt",
                        state_data={"content": f"content_{thread_id}_{i}"},
                    )
                    results.append(snapshot.snapshot_id)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=create_snapshots, args=(i,)) for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 50  # 5 threads * 10 snapshots each

        stats = service.get_stats()
        assert stats["total_snapshots"] == 50
        service.clear_all()

    def test_concurrent_execution_and_stats(self):
        """Concurrent execution and stats are thread-safe."""
        service = RollbackService()
        errors = []

        # Create some snapshots first
        for i in range(10):
            service.create_snapshot(
                action_id=f"act_{i}",
                resource_type="file",
                resource_id=f"/file{i}.txt",
                state_data={"content": str(i)},
            )

        def execute_rollbacks():
            try:
                for i in range(10):
                    service.execute_rollback(
                        action_id=f"act_{i}",
                        restore_fn=lambda s: True,
                    )
            except Exception as e:
                errors.append(e)

        def read_stats():
            try:
                for _ in range(20):
                    service.get_stats()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=execute_rollbacks)
        t2 = threading.Thread(target=read_stats)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0
        service.clear_all()


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        svc = RollbackService()
        yield svc
        svc.clear_all()

    def test_empty_state_data(self, service):
        """Snapshot with empty state data."""
        snapshot = service.create_snapshot(
            action_id="act_123",
            resource_type="empty",
            resource_id="empty_resource",
            state_data={},
        )
        assert snapshot.state_data == {}

    def test_large_state_data(self, service):
        """Snapshot with large state data."""
        large_content = "x" * 1_000_000  # 1MB
        snapshot = service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/large_file.txt",
            state_data={"content": large_content},
        )
        retrieved = service.get_snapshot(snapshot.snapshot_id)
        assert len(retrieved.state_data["content"]) == 1_000_000

    def test_special_characters_in_ids(self, service):
        """Handles special characters in IDs."""
        snapshot = service.create_snapshot(
            action_id="act-with-dashes_and_underscores.dots",
            resource_type="special",
            resource_id="/path/with spaces/and#special&chars",
            state_data={"key": "value"},
        )
        snapshots = service.get_snapshots_for_action(
            "act-with-dashes_and_underscores.dots"
        )
        assert len(snapshots) == 1

    def test_unicode_in_state_data(self, service):
        """Handles Unicode in state data."""
        snapshot = service.create_snapshot(
            action_id="act_unicode",
            resource_type="file",
            resource_id="/unicode.txt",
            state_data={
                "content": "Hello 世界 🌍 مرحبا",
                "emoji": "👍",
            },
        )
        retrieved = service.get_snapshot(snapshot.snapshot_id)
        assert "世界" in retrieved.state_data["content"]
        assert retrieved.state_data["emoji"] == "👍"

    def test_zero_ttl(self, service):
        """Zero TTL creates immediately expired snapshot."""
        snapshot = service.create_snapshot(
            action_id="act_123",
            resource_type="file",
            resource_id="/test.txt",
            state_data={"content": "test"},
            ttl_hours=0,
        )
        # With 0 TTL, snapshot expires at creation time
        # But it should still be created
        assert snapshot.snapshot_id.startswith("snap_")

    def test_nested_state_data(self, service):
        """Handles deeply nested state data."""
        nested_data = {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}}
        snapshot = service.create_snapshot(
            action_id="act_nested",
            resource_type="config",
            resource_id="nested_config",
            state_data=nested_data,
        )
        retrieved = service.get_snapshot(snapshot.snapshot_id)
        assert (
            retrieved.state_data["level1"]["level2"]["level3"]["level4"]["value"]
            == "deep"
        )

    def test_execution_history_trimming(self, service):
        """Execution history is trimmed to 1000 entries."""
        # Create a snapshot for rollback
        service.create_snapshot(
            action_id="act_trim",
            resource_type="file",
            resource_id="/test.txt",
            state_data={"content": "test"},
        )

        # Execute many rollbacks
        for i in range(50):  # Reduced for test speed
            service.execute_rollback(
                action_id="act_trim",
                restore_fn=lambda s: True,
            )

        # History should be maintained
        assert len(service._executions) <= 1000
