"""
Tests for Reversibility Classifier (ADR-052 Phase 1).

Tests cover:
- ActionClass enum and properties
- ActionMetadata, StateSnapshot, RollbackPlan dataclasses
- ActionApproval results
- ReversibilityClassifier classification logic
"""

import platform
from datetime import datetime, timedelta, timezone

import pytest

from src.services.alignment.reversibility import (
    ActionApproval,
    ActionClass,
    ActionMetadata,
    ReversibilityClassifier,
    RollbackPlan,
    StateSnapshot,
)

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestActionClass:
    """Tests for ActionClass enum."""

    def test_class_values(self):
        """Test action class values."""
        assert ActionClass.FULLY_REVERSIBLE.value == "A"
        assert ActionClass.PARTIALLY_REVERSIBLE.value == "B"
        assert ActionClass.IRREVERSIBLE.value == "C"

    def test_description_property(self):
        """Test description for each class."""
        assert "instant" in ActionClass.FULLY_REVERSIBLE.description.lower()
        assert "side effects" in ActionClass.PARTIALLY_REVERSIBLE.description.lower()
        assert "cannot" in ActionClass.IRREVERSIBLE.description.lower()

    def test_min_autonomy_level(self):
        """Test minimum autonomy levels."""
        assert ActionClass.FULLY_REVERSIBLE.min_autonomy_level == 2
        assert ActionClass.PARTIALLY_REVERSIBLE.min_autonomy_level == 1
        assert ActionClass.IRREVERSIBLE.min_autonomy_level == 0

    def test_requires_human_approval(self):
        """Test human approval requirement."""
        assert ActionClass.FULLY_REVERSIBLE.requires_human_approval is False
        assert ActionClass.PARTIALLY_REVERSIBLE.requires_human_approval is False
        assert ActionClass.IRREVERSIBLE.requires_human_approval is True


class TestActionMetadata:
    """Tests for ActionMetadata dataclass."""

    def test_creation(self):
        """Test creating action metadata."""
        metadata = ActionMetadata(
            action_type="code_change",
            target_resource="/src/main.py",
            target_resource_type="file",
            is_production=False,
            affects_external_system=False,
        )
        assert metadata.action_type == "code_change"
        assert metadata.is_production is False

    def test_defaults(self):
        """Test default values."""
        metadata = ActionMetadata(
            action_type="test",
            target_resource="resource",
            target_resource_type="file",
        )
        assert metadata.is_production is False
        assert metadata.affects_external_system is False
        assert metadata.is_destructive is False
        assert metadata.estimated_impact_scope == "local"


class TestStateSnapshot:
    """Tests for StateSnapshot dataclass."""

    def test_creation(self):
        """Test creating a state snapshot."""
        snapshot = StateSnapshot(
            snapshot_id="snap-123",
            action_id="action-456",
            resource_type="file",
            resource_id="/src/main.py",
            state_data={"content": "print('hello')"},
        )
        assert snapshot.snapshot_id == "snap-123"
        assert snapshot.checksum != ""

    def test_checksum_calculation(self):
        """Test checksum is calculated."""
        snapshot = StateSnapshot(
            snapshot_id="snap-123",
            action_id="action-456",
            resource_type="file",
            resource_id="/test",
            state_data={"key": "value"},
        )
        assert len(snapshot.checksum) == 16

    def test_verify_integrity_valid(self):
        """Test integrity verification passes."""
        snapshot = StateSnapshot(
            snapshot_id="snap-123",
            action_id="action-456",
            resource_type="file",
            resource_id="/test",
            state_data={"content": "test"},
        )
        assert snapshot.verify_integrity() is True

    def test_verify_integrity_tampered(self):
        """Test integrity verification fails for tampered data."""
        snapshot = StateSnapshot(
            snapshot_id="snap-123",
            action_id="action-456",
            resource_type="file",
            resource_id="/test",
            state_data={"content": "original"},
        )
        # Tamper with data
        snapshot.state_data["content"] = "modified"
        assert snapshot.verify_integrity() is False

    def test_to_dict(self):
        """Test dictionary conversion."""
        snapshot = StateSnapshot(
            snapshot_id="snap-123",
            action_id="action-456",
            resource_type="config",
            resource_id="app.settings",
            state_data={"setting": "value"},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        result = snapshot.to_dict()

        assert result["snapshot_id"] == "snap-123"
        assert result["resource_type"] == "config"
        assert "expires_at" in result
        assert result["expires_at"] is not None


class TestRollbackPlan:
    """Tests for RollbackPlan dataclass."""

    def test_creation(self):
        """Test creating a rollback plan."""
        plan = RollbackPlan(
            plan_id="plan-123",
            action_id="action-456",
            steps=[
                {"step": 1, "action": "Revert deployment"},
                {"step": 2, "action": "Verify health"},
            ],
            estimated_duration_seconds=300,
            potential_side_effects=["Brief downtime"],
            requires_downtime=True,
            is_viable=True,
        )
        assert plan.plan_id == "plan-123"
        assert len(plan.steps) == 2
        assert plan.is_viable is True

    def test_not_viable_plan(self):
        """Test creating a non-viable plan."""
        plan = RollbackPlan(
            plan_id="plan-123",
            action_id="action-456",
            steps=[],
            is_viable=False,
            non_viable_reason="Cannot reverse email send",
        )
        assert plan.is_viable is False
        assert plan.non_viable_reason is not None

    def test_to_dict(self):
        """Test dictionary conversion."""
        plan = RollbackPlan(
            plan_id="plan-123",
            action_id="action-456",
            steps=[{"step": 1, "action": "Rollback"}],
            estimated_duration_seconds=120,
            is_viable=True,
        )
        result = plan.to_dict()

        assert result["plan_id"] == "plan-123"
        assert result["estimated_duration_seconds"] == 120
        assert result["is_viable"] is True


class TestActionApproval:
    """Tests for ActionApproval dataclass."""

    def test_approved(self):
        """Test approved action."""
        approval = ActionApproval(
            action_id="action-123",
            action_class=ActionClass.FULLY_REVERSIBLE,
            approved=True,
            requires_human_approval=False,
            rollback_available=True,
        )
        assert approval.approved is True
        assert approval.requires_human_approval is False

    def test_requires_human_approval(self):
        """Test action requiring human approval."""
        approval = ActionApproval(
            action_id="action-123",
            action_class=ActionClass.IRREVERSIBLE,
            approved=False,
            requires_human_approval=True,
            rollback_available=False,
            rejection_reason="Irreversible action requires approval",
        )
        assert approval.approved is False
        assert approval.requires_human_approval is True

    def test_to_dict(self):
        """Test dictionary conversion."""
        snapshot = StateSnapshot(
            snapshot_id="snap-123",
            action_id="action-123",
            resource_type="file",
            resource_id="/test",
            state_data={},
        )
        approval = ActionApproval(
            action_id="action-123",
            action_class=ActionClass.FULLY_REVERSIBLE,
            approved=True,
            requires_human_approval=False,
            rollback_available=True,
            snapshot=snapshot,
            conditions=["Proceed with caution"],
        )
        result = approval.to_dict()

        assert result["action_id"] == "action-123"
        assert result["action_class"] == "A"
        assert result["snapshot_id"] == "snap-123"
        assert result["conditions"] == ["Proceed with caution"]


class TestReversibilityClassifier:
    """Tests for ReversibilityClassifier class."""

    @pytest.fixture
    def classifier(self):
        """Create a fresh classifier for each test."""
        return ReversibilityClassifier()

    def _create_metadata(
        self,
        action_type: str = "code_change",
        is_production: bool = False,
        is_destructive: bool = False,
        affects_external: bool = False,
        has_side_effects: bool = False,
    ) -> ActionMetadata:
        """Create test metadata."""
        return ActionMetadata(
            action_type=action_type,
            target_resource="/test/resource",
            target_resource_type="file",
            is_production=is_production,
            is_destructive=is_destructive,
            affects_external_system=affects_external,
            has_side_effects=has_side_effects,
        )

    # Classification tests

    def test_classify_fully_reversible(self, classifier):
        """Test classification of fully reversible actions."""
        metadata = self._create_metadata(action_type="code_change")
        assert classifier.classify(metadata) == ActionClass.FULLY_REVERSIBLE

        metadata = self._create_metadata(action_type="config_update")
        assert classifier.classify(metadata) == ActionClass.FULLY_REVERSIBLE

        metadata = self._create_metadata(action_type="feature_flag_toggle")
        assert classifier.classify(metadata) == ActionClass.FULLY_REVERSIBLE

    def test_classify_partially_reversible(self, classifier):
        """Test classification of partially reversible actions."""
        metadata = self._create_metadata(action_type="data_modification")
        assert classifier.classify(metadata) == ActionClass.PARTIALLY_REVERSIBLE

        metadata = self._create_metadata(action_type="deployment")
        assert classifier.classify(metadata) == ActionClass.PARTIALLY_REVERSIBLE

        metadata = self._create_metadata(action_type="external_api_call")
        assert classifier.classify(metadata) == ActionClass.PARTIALLY_REVERSIBLE

    def test_classify_irreversible(self, classifier):
        """Test classification of irreversible actions."""
        metadata = self._create_metadata(action_type="data_deletion")
        assert classifier.classify(metadata) == ActionClass.IRREVERSIBLE

        metadata = self._create_metadata(action_type="credential_rotation")
        assert classifier.classify(metadata) == ActionClass.IRREVERSIBLE

        metadata = self._create_metadata(action_type="payment_processing")
        assert classifier.classify(metadata) == ActionClass.IRREVERSIBLE

    def test_classify_escalation_production_destructive(self, classifier):
        """Test escalation to irreversible for production+destructive."""
        metadata = self._create_metadata(
            action_type="code_change",  # Normally fully reversible
            is_production=True,
            is_destructive=True,
        )
        assert classifier.classify(metadata) == ActionClass.IRREVERSIBLE

    def test_classify_escalation_to_partial(self, classifier):
        """Test escalation to partially reversible."""
        # Production code change escalates to partial
        metadata = self._create_metadata(
            action_type="code_change",
            is_production=True,
        )
        assert classifier.classify(metadata) == ActionClass.PARTIALLY_REVERSIBLE

        # External system involvement escalates to partial
        metadata = self._create_metadata(
            action_type="code_change",
            affects_external=True,
        )
        assert classifier.classify(metadata) == ActionClass.PARTIALLY_REVERSIBLE

    def test_classify_default_destructive(self, classifier):
        """Test default classification for unknown destructive action."""
        metadata = self._create_metadata(
            action_type="unknown_action",
            is_destructive=True,
        )
        assert classifier.classify(metadata) == ActionClass.IRREVERSIBLE

    def test_classify_default_external(self, classifier):
        """Test default classification for unknown external action."""
        metadata = self._create_metadata(
            action_type="unknown_action",
            affects_external=True,
        )
        assert classifier.classify(metadata) == ActionClass.PARTIALLY_REVERSIBLE

    def test_classify_default_side_effects(self, classifier):
        """Test default classification for unknown action with side effects."""
        metadata = self._create_metadata(
            action_type="unknown_action",
            has_side_effects=True,
        )
        assert classifier.classify(metadata) == ActionClass.PARTIALLY_REVERSIBLE

    def test_classify_default_production(self, classifier):
        """Test default classification for unknown production action."""
        metadata = self._create_metadata(
            action_type="unknown_action",
            is_production=True,
        )
        assert classifier.classify(metadata) == ActionClass.PARTIALLY_REVERSIBLE

    def test_classify_default_safe(self, classifier):
        """Test default classification for unknown safe action."""
        metadata = self._create_metadata(action_type="unknown_action")
        assert classifier.classify(metadata) == ActionClass.FULLY_REVERSIBLE

    # Pre-action check tests

    def test_pre_action_check_approved_class_a(self, classifier):
        """Test pre-action check for approved Class A action."""
        metadata = self._create_metadata(action_type="code_change")
        current_state = {"content": "original content"}

        approval = classifier.pre_action_check(
            action_id="action-123",
            metadata=metadata,
            agent_autonomy_level=2,  # EXECUTE_REVIEW
            current_state=current_state,
        )

        assert approval.approved is True
        assert approval.action_class == ActionClass.FULLY_REVERSIBLE
        assert approval.rollback_available is True
        assert approval.snapshot is not None

    def test_pre_action_check_approved_class_b(self, classifier):
        """Test pre-action check for approved Class B action."""
        metadata = self._create_metadata(action_type="deployment")

        approval = classifier.pre_action_check(
            action_id="action-123",
            metadata=metadata,
            agent_autonomy_level=1,  # RECOMMEND
        )

        assert approval.approved is True
        assert approval.action_class == ActionClass.PARTIALLY_REVERSIBLE
        assert approval.rollback_plan is not None

    def test_pre_action_check_denied_insufficient_autonomy(self, classifier):
        """Test denial when autonomy level is insufficient."""
        metadata = self._create_metadata(action_type="code_change")

        approval = classifier.pre_action_check(
            action_id="action-123",
            metadata=metadata,
            agent_autonomy_level=1,  # Needs 2 for FULLY_REVERSIBLE
        )

        assert approval.approved is False
        assert approval.requires_human_approval is True
        assert "insufficient" in approval.rejection_reason.lower()

    def test_pre_action_check_irreversible_requires_approval(self, classifier):
        """Test that irreversible actions require human approval."""
        metadata = self._create_metadata(action_type="data_deletion")

        approval = classifier.pre_action_check(
            action_id="action-123",
            metadata=metadata,
            agent_autonomy_level=3,  # Even autonomous
        )

        assert approval.approved is False
        assert approval.requires_human_approval is True
        assert "human approval" in approval.rejection_reason.lower()

    def test_pre_action_check_non_viable_rollback(self, classifier):
        """Test denial when rollback plan is not viable."""
        metadata = self._create_metadata(
            action_type="email_send",  # Notifications can't be unsent
        )

        approval = classifier.pre_action_check(
            action_id="action-123",
            metadata=metadata,
            agent_autonomy_level=3,
        )

        assert approval.approved is False
        assert approval.rollback_plan is not None
        assert approval.rollback_plan.is_viable is False

    def test_pre_action_check_conditions(self, classifier):
        """Test that conditions are generated appropriately."""
        metadata = self._create_metadata(
            action_type="code_change",
            is_production=True,
        )

        approval = classifier.pre_action_check(
            action_id="action-123",
            metadata=metadata,
            agent_autonomy_level=2,
        )

        # Should have production warning
        assert any("production" in c.lower() for c in approval.conditions)

    # Approval tests

    def test_approve_irreversible_action(self, classifier):
        """Test approving an irreversible action."""
        approval = classifier.approve_irreversible_action(
            action_id="action-123",
            approved_by="admin-user",
            reason="Emergency maintenance required",
        )

        assert approval.approved is True
        assert approval.requires_human_approval is False
        assert approval.action_class == ActionClass.IRREVERSIBLE
        assert "admin-user" in approval.conditions[0]

    # Snapshot tests

    def test_get_snapshot(self, classifier):
        """Test getting a stored snapshot."""
        metadata = self._create_metadata(action_type="code_change")
        classifier.pre_action_check("action-123", metadata, 2, {"content": "test"})

        snapshot = classifier.get_snapshot_for_action("action-123")
        assert snapshot is not None
        assert snapshot.action_id == "action-123"

    def test_get_snapshot_not_found(self, classifier):
        """Test getting non-existent snapshot."""
        snapshot = classifier.get_snapshot("nonexistent")
        assert snapshot is None

    # Rollback plan tests

    def test_get_rollback_plan(self, classifier):
        """Test getting a rollback plan."""
        metadata = self._create_metadata(action_type="deployment")
        classifier.pre_action_check("action-123", metadata, 1)

        plan = classifier.get_rollback_plan("action-123")
        assert plan is not None
        assert len(plan.steps) > 0

    def test_rollback_plan_deployment(self, classifier):
        """Test rollback plan for deployment."""
        metadata = self._create_metadata(action_type="deployment")
        classifier.pre_action_check("action-123", metadata, 1)

        plan = classifier.get_rollback_plan("action-123")
        assert plan.requires_downtime is True
        assert plan.estimated_duration_seconds > 0

    def test_rollback_plan_data_modification(self, classifier):
        """Test rollback plan for data modification."""
        metadata = self._create_metadata(action_type="data_modification")
        classifier.pre_action_check("action-123", metadata, 1)

        plan = classifier.get_rollback_plan("action-123")
        assert plan.is_viable is True

    def test_rollback_plan_external_api_no_side_effects(self, classifier):
        """Test rollback plan for external API without side effects."""
        metadata = self._create_metadata(
            action_type="external_api_call",
            has_side_effects=False,
        )
        classifier.pre_action_check("action-123", metadata, 1)

        plan = classifier.get_rollback_plan("action-123")
        assert plan.is_viable is True

    def test_rollback_plan_external_api_with_side_effects(self, classifier):
        """Test rollback plan for external API with side effects."""
        metadata = self._create_metadata(
            action_type="external_api_call",
            has_side_effects=True,
        )
        classifier.pre_action_check("action-123", metadata, 1)

        plan = classifier.get_rollback_plan("action-123")
        assert plan.is_viable is False

    # Execute rollback tests

    @pytest.mark.asyncio
    async def test_execute_rollback_snapshot(self, classifier):
        """Test rollback from snapshot."""
        metadata = self._create_metadata(action_type="code_change")
        classifier.pre_action_check("action-123", metadata, 2, {"content": "original"})

        success, message = await classifier.execute_rollback("action-123")
        assert success is True
        assert "snapshot" in message.lower()

    @pytest.mark.asyncio
    async def test_execute_rollback_plan(self, classifier):
        """Test rollback from plan."""
        metadata = self._create_metadata(action_type="deployment")
        classifier.pre_action_check("action-123", metadata, 1)

        success, message = await classifier.execute_rollback("action-123")
        assert success is True
        assert "plan" in message.lower()

    @pytest.mark.asyncio
    async def test_execute_rollback_no_mechanism(self, classifier):
        """Test rollback with no mechanism available."""
        success, message = await classifier.execute_rollback("nonexistent")
        assert success is False
        assert "no rollback" in message.lower()

    @pytest.mark.asyncio
    async def test_execute_rollback_corrupted_snapshot(self, classifier):
        """Test rollback with corrupted snapshot."""
        metadata = self._create_metadata(action_type="code_change")
        classifier.pre_action_check("action-123", metadata, 2, {"content": "original"})

        # Corrupt the snapshot
        snapshot = classifier.get_snapshot_for_action("action-123")
        snapshot.state_data["content"] = "corrupted"

        success, message = await classifier.execute_rollback("action-123")
        assert success is False
        assert "integrity" in message.lower()

    @pytest.mark.asyncio
    async def test_execute_rollback_non_viable_plan(self, classifier):
        """Test rollback with non-viable plan."""
        metadata = self._create_metadata(action_type="email_send")
        classifier.pre_action_check("action-123", metadata, 3)

        success, message = await classifier.execute_rollback("action-123")
        assert success is False
        assert "not viable" in message.lower()

    # Metrics tests

    def test_get_metrics(self, classifier):
        """Test getting metrics."""
        # Create some classifications
        classifier.pre_action_check(
            "action-1",
            self._create_metadata(action_type="code_change"),
            2,
        )
        classifier.pre_action_check(
            "action-2",
            self._create_metadata(action_type="deployment"),
            1,
        )
        classifier.pre_action_check(
            "action-3",
            self._create_metadata(action_type="data_deletion"),
            3,
        )

        metrics = classifier.get_metrics()
        assert metrics["classifications"]["class_a"] == 1
        assert metrics["classifications"]["class_b"] == 1
        assert metrics["classifications"]["class_c"] == 1
        assert metrics["classifications"]["total"] == 3

    @pytest.mark.asyncio
    async def test_metrics_rollback_tracking(self, classifier):
        """Test that rollback metrics are tracked."""
        metadata = self._create_metadata(action_type="code_change")
        classifier.pre_action_check("action-123", metadata, 2, {"content": "test"})

        await classifier.execute_rollback("action-123")

        metrics = classifier.get_metrics()
        assert metrics["rollbacks"]["attempted"] == 1
        assert metrics["rollbacks"]["successful"] == 1

    # Cleanup tests

    def test_cleanup_expired_snapshots(self, classifier):
        """Test cleanup of expired snapshots."""
        metadata = self._create_metadata(action_type="code_change")
        approval = classifier.pre_action_check(
            "action-123", metadata, 2, {"content": "test"}
        )

        # Manually expire the snapshot
        snapshot = classifier.get_snapshot_for_action("action-123")
        snapshot.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        cleaned = classifier.cleanup_expired_snapshots()
        assert cleaned == 1

        # Snapshot should be gone
        assert classifier.get_snapshot_for_action("action-123") is None

    def test_cleanup_no_expired(self, classifier):
        """Test cleanup when no snapshots are expired."""
        metadata = self._create_metadata(action_type="code_change")
        classifier.pre_action_check("action-123", metadata, 2, {"content": "test"})

        cleaned = classifier.cleanup_expired_snapshots()
        assert cleaned == 0

    # Custom callback tests

    def test_custom_snapshot_store(self):
        """Test custom snapshot store callback."""
        stored_snapshots = []

        def store_snapshot(snapshot):
            stored_snapshots.append(snapshot)

        classifier = ReversibilityClassifier(snapshot_store=store_snapshot)
        metadata = ActionMetadata(
            action_type="code_change",
            target_resource="/test",
            target_resource_type="file",
        )
        classifier.pre_action_check("action-123", metadata, 2, {"content": "test"})

        assert len(stored_snapshots) == 1

    def test_custom_snapshot_retriever(self):
        """Test custom snapshot retriever callback."""
        custom_snapshot = StateSnapshot(
            snapshot_id="custom-snap",
            action_id="action-123",
            resource_type="file",
            resource_id="/test",
            state_data={"custom": "data"},
        )

        def retrieve_snapshot(snapshot_id):
            if snapshot_id == "custom-snap":
                return custom_snapshot
            return None

        classifier = ReversibilityClassifier(snapshot_retriever=retrieve_snapshot)
        result = classifier.get_snapshot("custom-snap")

        assert result is not None
        assert result.state_data["custom"] == "data"

    @pytest.mark.asyncio
    async def test_custom_rollback_executor(self):
        """Test custom rollback executor callback."""
        executed_plans = []

        async def execute_plan(plan):
            executed_plans.append(plan)
            return True

        classifier = ReversibilityClassifier(rollback_executor=execute_plan)
        metadata = ActionMetadata(
            action_type="deployment",
            target_resource="/app",
            target_resource_type="service",
        )
        classifier.pre_action_check("action-123", metadata, 1)

        success, _ = await classifier.execute_rollback("action-123")
        assert success is True
        assert len(executed_plans) == 1
