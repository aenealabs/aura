"""Tests for audit integration (Phase 2)."""

from unittest.mock import MagicMock

import pytest

from src.services.memory_evolution import (
    MemoryEvolutionConfig,
    RefineAction,
    RefineOperation,
    RefineResult,
    reset_memory_evolution_config,
    set_memory_evolution_config,
)
from src.services.memory_evolution.audit_integration import (
    AuditSeverity,
    EvolutionAuditAdapter,
    EvolutionAuditEventType,
    EvolutionAuditRecord,
    get_evolution_audit_adapter,
    reset_evolution_audit_adapter,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test."""
    reset_memory_evolution_config()
    reset_evolution_audit_adapter()
    yield
    reset_memory_evolution_config()
    reset_evolution_audit_adapter()


@pytest.fixture
def test_config() -> MemoryEvolutionConfig:
    """Create a test configuration."""
    config = MemoryEvolutionConfig(
        environment="test",
        project_name="aura-test",
    )
    set_memory_evolution_config(config)
    return config


@pytest.fixture
def mock_audit_logger() -> MagicMock:
    """Create a mock NeuralMemoryAuditLogger."""
    logger = MagicMock()
    logger.log_event = MagicMock(return_value="event-123")
    return logger


@pytest.fixture
def adapter(
    mock_audit_logger: MagicMock,
    test_config: MemoryEvolutionConfig,
) -> EvolutionAuditAdapter:
    """Create an EvolutionAuditAdapter with mocks."""
    return EvolutionAuditAdapter(
        audit_logger=mock_audit_logger,
        config=test_config,
    )


class TestEvolutionAuditEventType:
    """Tests for EvolutionAuditEventType enum."""

    def test_all_event_types_defined(self):
        """Test all event types are defined."""
        assert EvolutionAuditEventType.REFINE_OPERATION.value == "refine_operation"
        assert EvolutionAuditEventType.EVOLUTION_TRACKING.value == "evolution_tracking"
        assert EvolutionAuditEventType.SECURITY_BOUNDARY.value == "security_boundary"
        assert EvolutionAuditEventType.CIRCUIT_BREAKER.value == "circuit_breaker"
        assert EvolutionAuditEventType.CONFIG_CHANGE.value == "config_change"
        assert EvolutionAuditEventType.ROLLBACK.value == "rollback"


class TestAuditSeverity:
    """Tests for AuditSeverity enum."""

    def test_all_severities_defined(self):
        """Test all severity levels are defined."""
        assert AuditSeverity.INFO.value == "info"
        assert AuditSeverity.WARNING.value == "warning"
        assert AuditSeverity.ERROR.value == "error"
        assert AuditSeverity.CRITICAL.value == "critical"


class TestEvolutionAuditRecord:
    """Tests for EvolutionAuditRecord dataclass."""

    def test_create_record(self):
        """Test creating an audit record."""
        record = EvolutionAuditRecord(
            event_id="evt-123",
            timestamp="2026-02-04T12:00:00Z",
            event_type=EvolutionAuditEventType.REFINE_OPERATION,
            severity=AuditSeverity.INFO,
            operation="consolidate",
            actor="agent-1",
            tenant_id="tenant-123",
            security_domain="development",
            resource="mem-1,mem-2",
            details={"memories_merged": 2},
            outcome="success",
            latency_ms=45.0,
        )
        assert record.event_id == "evt-123"
        assert record.event_type == EvolutionAuditEventType.REFINE_OPERATION
        assert record.outcome == "success"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        record = EvolutionAuditRecord(
            event_id="evt-123",
            timestamp="2026-02-04T12:00:00Z",
            event_type=EvolutionAuditEventType.SECURITY_BOUNDARY,
            severity=AuditSeverity.WARNING,
            operation="security_check",
            actor="agent-1",
            tenant_id="tenant-123",
            security_domain="development",
            resource="tenant:tenant-123",
            details={"allowed": False},
            outcome="blocked",
            latency_ms=5.0,
            correlation_id="corr-456",
        )
        data = record.to_dict()

        assert data["event_id"] == "evt-123"
        assert data["event_type"] == "security_boundary"
        assert data["severity"] == "warning"
        assert data["correlation_id"] == "corr-456"


class TestEvolutionAuditAdapter:
    """Tests for EvolutionAuditAdapter."""

    def test_log_refine_operation_success(
        self,
        adapter: EvolutionAuditAdapter,
        mock_audit_logger: MagicMock,
    ):
        """Test logging successful refine operation."""
        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Similar patterns",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
            agent_id="agent-1",
        )
        result = RefineResult(
            success=True,
            operation=RefineOperation.CONSOLIDATE,
            affected_memory_ids=["mem-merged"],
            rollback_token="rb-123",
            latency_ms=50.0,
        )

        event_id = adapter.log_refine_operation(action, result)

        assert event_id == "event-123"
        mock_audit_logger.log_event.assert_called_once()
        call_args = mock_audit_logger.log_event.call_args
        assert call_args[1]["event_type"] == "refine_operation"
        assert call_args[1]["severity"] == "info"
        assert call_args[1]["operation"] == "consolidate"

    def test_log_refine_operation_failure(
        self,
        adapter: EvolutionAuditAdapter,
        mock_audit_logger: MagicMock,
    ):
        """Test logging failed refine operation."""
        action = RefineAction(
            operation=RefineOperation.PRUNE,
            target_memory_ids=["mem-1"],
            reasoning="Low value",
            confidence=0.8,
            tenant_id="tenant-123",
            security_domain="development",
            agent_id="agent-1",
        )
        result = RefineResult(
            success=False,
            operation=RefineOperation.PRUNE,
            affected_memory_ids=[],
            error="Memory not found",
        )

        adapter.log_refine_operation(action, result)

        call_args = mock_audit_logger.log_event.call_args
        assert call_args[1]["severity"] == "warning"
        assert "error" in call_args[1]["details"]

    def test_log_security_boundary_check_allowed(
        self,
        adapter: EvolutionAuditAdapter,
        mock_audit_logger: MagicMock,
    ):
        """Test logging allowed security boundary check."""
        event_id = adapter.log_security_boundary_check(
            agent_id="agent-1",
            tenant_id="tenant-123",
            security_domain="development",
            memory_ids=["mem-1", "mem-2"],
            allowed=True,
            reason="All memories belong to tenant",
        )

        assert event_id == "event-123"
        call_args = mock_audit_logger.log_event.call_args
        assert call_args[1]["event_type"] == "security_boundary"
        assert call_args[1]["severity"] == "info"
        assert call_args[1]["details"]["allowed"] is True

    def test_log_security_boundary_check_blocked(
        self,
        adapter: EvolutionAuditAdapter,
        mock_audit_logger: MagicMock,
    ):
        """Test logging blocked security boundary check."""
        adapter.log_security_boundary_check(
            agent_id="agent-1",
            tenant_id="tenant-123",
            security_domain="development",
            memory_ids=["mem-other-tenant"],
            allowed=False,
            reason="Memory belongs to different tenant",
        )

        call_args = mock_audit_logger.log_event.call_args
        assert call_args[1]["severity"] == "warning"
        assert call_args[1]["details"]["allowed"] is False

    def test_log_circuit_breaker_open(
        self,
        adapter: EvolutionAuditAdapter,
        mock_audit_logger: MagicMock,
    ):
        """Test logging circuit breaker opening."""
        event_id = adapter.log_circuit_breaker_change(
            operation=RefineOperation.CONSOLIDATE,
            previous_state="closed",
            new_state="open",
            failure_count=5,
            reason="Exceeded failure threshold",
        )

        assert event_id == "event-123"
        call_args = mock_audit_logger.log_event.call_args
        assert call_args[1]["event_type"] == "circuit_breaker"
        assert call_args[1]["severity"] == "warning"  # Opening is warning
        assert call_args[1]["details"]["new_state"] == "open"

    def test_log_circuit_breaker_close(
        self,
        adapter: EvolutionAuditAdapter,
        mock_audit_logger: MagicMock,
    ):
        """Test logging circuit breaker closing."""
        adapter.log_circuit_breaker_change(
            operation=RefineOperation.PRUNE,
            previous_state="half_open",
            new_state="closed",
            failure_count=0,
            reason="Recovery successful",
        )

        call_args = mock_audit_logger.log_event.call_args
        assert call_args[1]["severity"] == "info"  # Closing is info

    def test_log_evolution_tracking(
        self,
        adapter: EvolutionAuditAdapter,
        mock_audit_logger: MagicMock,
    ):
        """Test logging evolution tracking."""
        actions = [
            RefineAction(
                operation=RefineOperation.CONSOLIDATE,
                target_memory_ids=["mem-1"],
                reasoning="Test",
                confidence=0.9,
                tenant_id="t-1",
                security_domain="dev",
            ),
            RefineAction(
                operation=RefineOperation.REINFORCE,
                target_memory_ids=["mem-2"],
                reasoning="Test",
                confidence=0.95,
                tenant_id="t-1",
                security_domain="dev",
            ),
        ]

        event_id = adapter.log_evolution_tracking(
            agent_id="agent-1",
            task_id="task-123",
            tenant_id="tenant-123",
            refine_actions=actions,
            outcome="success",
            correlation_id="corr-456",
        )

        assert event_id == "event-123"
        call_args = mock_audit_logger.log_event.call_args
        assert call_args[1]["event_type"] == "evolution_tracking"
        assert call_args[1]["details"]["refine_action_count"] == 2
        assert call_args[1]["details"]["refine_action_summary"]["consolidate"] == 1
        assert call_args[1]["details"]["refine_action_summary"]["reinforce"] == 1

    def test_log_rollback_success(
        self,
        adapter: EvolutionAuditAdapter,
        mock_audit_logger: MagicMock,
    ):
        """Test logging successful rollback."""
        original_action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
            agent_id="agent-1",
        )

        event_id = adapter.log_rollback(
            rollback_token="rb-123",
            original_action=original_action,
            success=True,
            restored_memory_ids=["mem-1", "mem-2"],
            reason="User requested rollback",
        )

        assert event_id == "event-123"
        call_args = mock_audit_logger.log_event.call_args
        assert call_args[1]["event_type"] == "rollback"
        assert call_args[1]["severity"] == "warning"
        assert call_args[1]["details"]["success"] is True

    def test_log_rollback_failure(
        self,
        adapter: EvolutionAuditAdapter,
        mock_audit_logger: MagicMock,
    ):
        """Test logging failed rollback."""
        original_action = RefineAction(
            operation=RefineOperation.PRUNE,
            target_memory_ids=["mem-1"],
            reasoning="Test",
            confidence=0.8,
            tenant_id="tenant-123",
            security_domain="development",
            agent_id="agent-1",
        )

        adapter.log_rollback(
            rollback_token="rb-456",
            original_action=original_action,
            success=False,
            restored_memory_ids=[],
            reason="Snapshot not found",
        )

        call_args = mock_audit_logger.log_event.call_args
        assert call_args[1]["severity"] == "error"
        assert call_args[1]["details"]["success"] is False


class TestAuditAdapterSingleton:
    """Tests for singleton management."""

    def test_get_returns_same_instance(self, mock_audit_logger: MagicMock):
        """Test singleton returns same instance."""
        adapter1 = get_evolution_audit_adapter(audit_logger=mock_audit_logger)
        adapter2 = get_evolution_audit_adapter()
        assert adapter1 is adapter2

    def test_reset_clears_instance(self, mock_audit_logger: MagicMock):
        """Test reset clears singleton."""
        adapter1 = get_evolution_audit_adapter(audit_logger=mock_audit_logger)
        reset_evolution_audit_adapter()
        adapter2 = get_evolution_audit_adapter(audit_logger=mock_audit_logger)
        assert adapter1 is not adapter2

    def test_get_without_logger_raises(self):
        """Test getting adapter without logger raises."""
        with pytest.raises(ValueError, match="audit_logger is required"):
            get_evolution_audit_adapter()
