"""
Tests for Execution Checkpoint Service.

Tests the real-time agent intervention checkpoint system (ADR-042).
"""

from unittest.mock import MagicMock, patch

import pytest

from src.services.execution_checkpoint_service import (
    ActionType,
    CheckpointAction,
    CheckpointStatus,
    ExecutionCheckpointService,
    InterventionMode,
    RiskLevel,
    TrustRule,
    autonomy_level_to_intervention_mode,
)
from src.services.realtime_event_publisher import LocalEventPublisher


class TestCheckpointAction:
    """Tests for CheckpointAction dataclass."""

    def test_create_action(self):
        """Test creating a checkpoint action."""
        action = CheckpointAction(
            checkpoint_id="test-123",
            execution_id="exec-456",
            agent_id="coder-agent",
            action_type=ActionType.FILE_WRITE,
            action_name="write_file",
            parameters={"path": "/tmp/test.py", "content": "print('hello')"},
            risk_level=RiskLevel.MEDIUM,
            reversible=True,
            estimated_duration_seconds=5,
            description="Write Python file",
        )

        assert action.checkpoint_id == "test-123"
        assert action.action_type == ActionType.FILE_WRITE
        assert action.risk_level == RiskLevel.MEDIUM
        assert action.reversible is True

    def test_action_default_values(self):
        """Test default values for optional fields."""
        action = CheckpointAction(
            checkpoint_id="test-123",
            execution_id="exec-456",
            agent_id="agent-1",
            action_type=ActionType.TOOL_CALL,
            action_name="search",
            parameters={},
            risk_level=RiskLevel.LOW,
            reversible=False,
            estimated_duration_seconds=1,
        )

        assert action.context == {}
        assert action.description == ""
        assert action.timeout_seconds == 300
        assert action.created_at is not None


class TestCheckpointStatus:
    """Tests for CheckpointStatus enum."""

    def test_all_statuses_exist(self):
        """Test all expected statuses are defined."""
        expected = [
            "PENDING",
            "AWAITING_APPROVAL",
            "AUTO_APPROVED",
            "APPROVED",
            "DENIED",
            "MODIFIED",
            "EXECUTING",
            "COMPLETED",
            "FAILED",
            "SKIPPED",
            "TIMEOUT",
        ]

        for status in expected:
            assert hasattr(CheckpointStatus, status)

    def test_status_values(self):
        """Test status string values."""
        assert CheckpointStatus.PENDING.value == "PENDING"
        assert CheckpointStatus.AWAITING_APPROVAL.value == "AWAITING_APPROVAL"


class TestInterventionMode:
    """Tests for InterventionMode enum."""

    def test_all_modes_exist(self):
        """Test all intervention modes are defined."""
        expected = [
            "ALL_ACTIONS",
            "WRITE_ACTIONS",
            "HIGH_RISK",
            "CRITICAL_ONLY",
            "NONE",
        ]

        for mode in expected:
            assert hasattr(InterventionMode, mode)


class TestAutonomyLevelMapping:
    """Tests for ADR-032 autonomy level to intervention mode mapping."""

    def test_level_0_manual(self):
        """Level 0 (Manual) maps to ALL_ACTIONS."""
        assert autonomy_level_to_intervention_mode(0) == InterventionMode.ALL_ACTIONS

    def test_level_1_observe(self):
        """Level 1 (Observe) maps to ALL_ACTIONS."""
        assert autonomy_level_to_intervention_mode(1) == InterventionMode.ALL_ACTIONS

    def test_level_2_assisted(self):
        """Level 2 (Assisted) maps to WRITE_ACTIONS."""
        assert autonomy_level_to_intervention_mode(2) == InterventionMode.WRITE_ACTIONS

    def test_level_3_supervised(self):
        """Level 3 (Supervised) maps to HIGH_RISK."""
        assert autonomy_level_to_intervention_mode(3) == InterventionMode.HIGH_RISK

    def test_level_4_guided(self):
        """Level 4 (Guided) maps to CRITICAL_ONLY."""
        assert autonomy_level_to_intervention_mode(4) == InterventionMode.CRITICAL_ONLY

    def test_level_5_autonomous(self):
        """Level 5 (Autonomous) maps to NONE."""
        assert autonomy_level_to_intervention_mode(5) == InterventionMode.NONE

    def test_invalid_level_defaults(self):
        """Invalid levels default to HIGH_RISK."""
        assert autonomy_level_to_intervention_mode(99) == InterventionMode.HIGH_RISK


class TestTrustRule:
    """Tests for TrustRule dataclass."""

    def test_create_trust_rule(self):
        """Test creating a trust rule."""
        rule = TrustRule(
            rule_id="rule-1",
            action_type=ActionType.TOOL_CALL,
            action_name_pattern="search_*",
            max_risk_level=RiskLevel.LOW,
        )

        assert rule.rule_id == "rule-1"
        assert rule.action_type == ActionType.TOOL_CALL
        assert rule.action_name_pattern == "search_*"
        assert rule.max_risk_level == RiskLevel.LOW
        assert rule.enabled is True

    def test_trust_rule_defaults(self):
        """Test default values for trust rules."""
        rule = TrustRule(rule_id="rule-2")

        assert rule.action_type is None
        assert rule.action_name_pattern is None
        assert rule.agent_id_pattern is None
        assert rule.max_risk_level == RiskLevel.LOW
        assert rule.enabled is True


class TestExecutionCheckpointService:
    """Tests for ExecutionCheckpointService."""

    @pytest.fixture
    def mock_dynamodb(self):
        """Mock DynamoDB resource."""
        with patch("boto3.resource") as mock:
            table = MagicMock()
            table.put_item = MagicMock()
            table.get_item = MagicMock(return_value={"Item": {}})
            table.update_item = MagicMock()
            table.query = MagicMock(return_value={"Items": []})
            mock.return_value.Table.return_value = table
            yield mock

    @pytest.fixture
    def service(self, mock_dynamodb):
        """Create service with mocked dependencies."""
        publisher = LocalEventPublisher()
        return ExecutionCheckpointService(
            dynamodb_table_name="test-checkpoints",
            event_publisher=publisher,
            intervention_mode=InterventionMode.HIGH_RISK,
        )

    def test_init(self, service):
        """Test service initialization."""
        assert service.table_name == "test-checkpoints"
        assert service.intervention_mode == InterventionMode.HIGH_RISK
        assert service.default_timeout == 300

    def test_set_intervention_mode(self, service):
        """Test changing intervention mode."""
        service.set_intervention_mode(InterventionMode.ALL_ACTIONS)
        assert service.intervention_mode == InterventionMode.ALL_ACTIONS

        service.set_intervention_mode(InterventionMode.NONE)
        assert service.intervention_mode == InterventionMode.NONE

    def test_requires_intervention_none_mode(self, service):
        """Test no intervention required in NONE mode."""
        service.intervention_mode = InterventionMode.NONE

        action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.FILE_DELETE,
            action_name="delete",
            parameters={},
            risk_level=RiskLevel.CRITICAL,
            reversible=False,
            estimated_duration_seconds=1,
        )

        assert service._requires_intervention(action) is False

    def test_requires_intervention_all_actions_mode(self, service):
        """Test all actions require intervention in ALL_ACTIONS mode."""
        service.intervention_mode = InterventionMode.ALL_ACTIONS

        action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.TOOL_CALL,
            action_name="search",
            parameters={},
            risk_level=RiskLevel.LOW,
            reversible=True,
            estimated_duration_seconds=1,
        )

        assert service._requires_intervention(action) is True

    def test_requires_intervention_write_actions_mode(self, service):
        """Test only writes require intervention in WRITE_ACTIONS mode."""
        service.intervention_mode = InterventionMode.WRITE_ACTIONS

        # Read action should not require intervention
        read_action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.TOOL_CALL,
            action_name="read",
            parameters={},
            risk_level=RiskLevel.LOW,
            reversible=True,
            estimated_duration_seconds=1,
        )
        assert service._requires_intervention(read_action) is False

        # Write action should require intervention
        write_action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.FILE_WRITE,
            action_name="write",
            parameters={},
            risk_level=RiskLevel.MEDIUM,
            reversible=True,
            estimated_duration_seconds=1,
        )
        assert service._requires_intervention(write_action) is True

    def test_requires_intervention_high_risk_mode(self, service):
        """Test only high/critical risk require intervention in HIGH_RISK mode."""
        service.intervention_mode = InterventionMode.HIGH_RISK

        # Low risk should not require intervention
        low_action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.FILE_WRITE,
            action_name="write",
            parameters={},
            risk_level=RiskLevel.LOW,
            reversible=True,
            estimated_duration_seconds=1,
        )
        assert service._requires_intervention(low_action) is False

        # High risk should require intervention
        high_action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.FILE_DELETE,
            action_name="delete",
            parameters={},
            risk_level=RiskLevel.HIGH,
            reversible=False,
            estimated_duration_seconds=1,
        )
        assert service._requires_intervention(high_action) is True

    def test_requires_intervention_critical_only_mode(self, service):
        """Test only critical risk requires intervention in CRITICAL_ONLY mode."""
        service.intervention_mode = InterventionMode.CRITICAL_ONLY

        # High risk should not require intervention
        high_action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.FILE_DELETE,
            action_name="delete",
            parameters={},
            risk_level=RiskLevel.HIGH,
            reversible=False,
            estimated_duration_seconds=1,
        )
        assert service._requires_intervention(high_action) is False

        # Critical risk should require intervention
        critical_action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.RESOURCE_DELETE,
            action_name="delete_cluster",
            parameters={},
            risk_level=RiskLevel.CRITICAL,
            reversible=False,
            estimated_duration_seconds=60,
        )
        assert service._requires_intervention(critical_action) is True


class TestTrustRuleMatching:
    """Tests for trust rule matching logic."""

    @pytest.fixture
    def mock_dynamodb(self):
        """Mock DynamoDB resource."""
        with patch("boto3.resource") as mock:
            table = MagicMock()
            mock.return_value.Table.return_value = table
            yield mock

    @pytest.fixture
    def service(self, mock_dynamodb):
        """Create service with mocked dependencies."""
        return ExecutionCheckpointService(
            dynamodb_table_name="test-checkpoints",
        )

    @pytest.mark.asyncio
    async def test_no_rules_no_auto_approve(self, service):
        """Test no auto-approval when no rules exist."""
        action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.TOOL_CALL,
            action_name="search",
            parameters={},
            risk_level=RiskLevel.LOW,
            reversible=True,
            estimated_duration_seconds=1,
        )

        result = await service._should_auto_approve(action)
        assert result is False

    @pytest.mark.asyncio
    async def test_matching_action_type_rule(self, service):
        """Test auto-approval when action type matches."""
        rule = TrustRule(
            rule_id="rule-1",
            action_type=ActionType.TOOL_CALL,
            max_risk_level=RiskLevel.LOW,
        )
        await service.add_trust_rule(rule)

        action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.TOOL_CALL,
            action_name="search",
            parameters={},
            risk_level=RiskLevel.LOW,
            reversible=True,
            estimated_duration_seconds=1,
        )

        result = await service._should_auto_approve(action)
        assert result is True

    @pytest.mark.asyncio
    async def test_non_matching_action_type(self, service):
        """Test no auto-approval when action type doesn't match."""
        rule = TrustRule(
            rule_id="rule-1",
            action_type=ActionType.TOOL_CALL,
            max_risk_level=RiskLevel.LOW,
        )
        await service.add_trust_rule(rule)

        action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.FILE_WRITE,
            action_name="write",
            parameters={},
            risk_level=RiskLevel.LOW,
            reversible=True,
            estimated_duration_seconds=1,
        )

        result = await service._should_auto_approve(action)
        assert result is False

    @pytest.mark.asyncio
    async def test_risk_level_exceeds_rule(self, service):
        """Test no auto-approval when risk exceeds rule limit."""
        rule = TrustRule(
            rule_id="rule-1",
            action_type=ActionType.TOOL_CALL,
            max_risk_level=RiskLevel.LOW,
        )
        await service.add_trust_rule(rule)

        action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.TOOL_CALL,
            action_name="search",
            parameters={},
            risk_level=RiskLevel.HIGH,
            reversible=True,
            estimated_duration_seconds=1,
        )

        result = await service._should_auto_approve(action)
        assert result is False

    @pytest.mark.asyncio
    async def test_action_name_pattern_matching(self, service):
        """Test action name pattern matching."""
        rule = TrustRule(
            rule_id="rule-1",
            action_name_pattern="search_*",
            max_risk_level=RiskLevel.MEDIUM,
        )
        await service.add_trust_rule(rule)

        matching_action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.TOOL_CALL,
            action_name="search_code",
            parameters={},
            risk_level=RiskLevel.LOW,
            reversible=True,
            estimated_duration_seconds=1,
        )
        assert await service._should_auto_approve(matching_action) is True

        non_matching_action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.TOOL_CALL,
            action_name="delete_file",
            parameters={},
            risk_level=RiskLevel.LOW,
            reversible=True,
            estimated_duration_seconds=1,
        )
        assert await service._should_auto_approve(non_matching_action) is False

    @pytest.mark.asyncio
    async def test_disabled_rule_ignored(self, service):
        """Test disabled rules are not matched."""
        rule = TrustRule(
            rule_id="rule-1",
            action_type=ActionType.TOOL_CALL,
            max_risk_level=RiskLevel.MEDIUM,
            enabled=False,
        )
        await service.add_trust_rule(rule)

        action = CheckpointAction(
            checkpoint_id="test",
            execution_id="exec",
            agent_id="agent",
            action_type=ActionType.TOOL_CALL,
            action_name="search",
            parameters={},
            risk_level=RiskLevel.LOW,
            reversible=True,
            estimated_duration_seconds=1,
        )

        result = await service._should_auto_approve(action)
        assert result is False

    @pytest.mark.asyncio
    async def test_remove_trust_rule(self, service):
        """Test removing a trust rule."""
        rule = TrustRule(
            rule_id="rule-1",
            action_type=ActionType.TOOL_CALL,
        )
        await service.add_trust_rule(rule)

        assert len(await service.get_trust_rules()) == 1

        result = await service.remove_trust_rule("rule-1")
        assert result is True
        assert len(await service.get_trust_rules()) == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_rule(self, service):
        """Test removing a rule that doesn't exist."""
        result = await service.remove_trust_rule("nonexistent")
        assert result is False


class TestLocalEventPublisher:
    """Tests for LocalEventPublisher (test helper)."""

    @pytest.mark.asyncio
    async def test_publish_to_execution(self):
        """Test publishing events to execution subscribers."""
        publisher = LocalEventPublisher()

        await publisher.register_connection("conn-1", "exec-1", "user-1")
        await publisher.register_connection("conn-2", "exec-1", "user-2")
        await publisher.register_connection("conn-3", "exec-2", "user-3")

        count = await publisher.publish("exec-1", {"type": "test"})
        assert count == 2

        # Verify events received
        events1 = await publisher.get_events("conn-1")
        assert len(events1) == 1
        assert events1[0]["type"] == "test"

        events2 = await publisher.get_events("conn-2")
        assert len(events2) == 1

        # exec-2 subscriber should not receive
        events3 = await publisher.get_events("conn-3")
        assert len(events3) == 0

    @pytest.mark.asyncio
    async def test_unregister_connection(self):
        """Test unregistering a connection."""
        publisher = LocalEventPublisher()

        await publisher.register_connection("conn-1", "exec-1", "user-1")
        await publisher.unregister_connection("conn-1")

        count = await publisher.publish("exec-1", {"type": "test"})
        assert count == 0
