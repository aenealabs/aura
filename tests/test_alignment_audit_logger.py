"""
Tests for Decision Audit Logger (ADR-052 Phase 1).

Tests cover:
- DecisionSeverity and DecisionOutcome enums
- ReasoningStep, AlternativeOption, UncertaintyDisclosure dataclasses
- DecisionContext and DecisionRecord
- DecisionAuditLogger logging and validation
"""

import platform
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.alignment.audit_logger import (
    AlternativeOption,
    DecisionAuditLogger,
    DecisionContext,
    DecisionOutcome,
    DecisionRecord,
    DecisionSeverity,
    ReasoningStep,
    UncertaintyDisclosure,
)

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestDecisionSeverity:
    """Tests for DecisionSeverity enum."""

    def test_severity_levels(self):
        """Test severity level values."""
        assert DecisionSeverity.TRIVIAL.value == "trivial"
        assert DecisionSeverity.NORMAL.value == "normal"
        assert DecisionSeverity.SIGNIFICANT.value == "significant"
        assert DecisionSeverity.CRITICAL.value == "critical"


class TestDecisionOutcome:
    """Tests for DecisionOutcome enum."""

    def test_outcome_values(self):
        """Test outcome values."""
        assert DecisionOutcome.PENDING.value == "pending"
        assert DecisionOutcome.SUCCESSFUL.value == "successful"
        assert DecisionOutcome.FAILED.value == "failed"
        assert DecisionOutcome.OVERRIDDEN.value == "overridden"
        assert DecisionOutcome.ROLLED_BACK.value == "rolled_back"


class TestReasoningStep:
    """Tests for ReasoningStep dataclass."""

    def test_creation(self):
        """Test creating a reasoning step."""
        step = ReasoningStep(
            step_number=1,
            description="Analyzed the code structure",
            evidence=["Found 10 classes", "5 functions"],
            confidence=0.9,
            references=["/src/main.py"],
        )
        assert step.step_number == 1
        assert step.confidence == 0.9

    def test_defaults(self):
        """Test default values."""
        step = ReasoningStep(step_number=1, description="Test")
        assert step.evidence == []
        assert step.confidence == 1.0
        assert step.references == []

    def test_to_dict(self):
        """Test dictionary conversion."""
        step = ReasoningStep(
            step_number=2,
            description="Test step",
            evidence=["evidence1"],
            confidence=0.8,
            references=["ref1"],
        )
        result = step.to_dict()

        assert result["step"] == 2
        assert result["description"] == "Test step"
        assert result["evidence"] == ["evidence1"]
        assert result["confidence"] == 0.8


class TestAlternativeOption:
    """Tests for AlternativeOption dataclass."""

    def test_creation(self):
        """Test creating an alternative option."""
        alt = AlternativeOption(
            option_id="opt-1",
            description="Use microservices architecture",
            confidence=0.8,
            pros=["Scalable", "Independent deployment"],
            cons=["Complexity", "Network latency"],
            was_chosen=True,
        )
        assert alt.option_id == "opt-1"
        assert alt.was_chosen is True

    def test_defaults(self):
        """Test default values."""
        alt = AlternativeOption(
            option_id="opt-1",
            description="Test",
            confidence=0.5,
        )
        assert alt.pros == []
        assert alt.cons == []
        assert alt.was_chosen is False
        assert alt.rejection_reason is None

    def test_to_dict(self):
        """Test dictionary conversion."""
        alt = AlternativeOption(
            option_id="opt-1",
            description="Option 1",
            confidence=0.7,
            pros=["pro1"],
            cons=["con1"],
            was_chosen=False,
            rejection_reason="Too complex",
        )
        result = alt.to_dict()

        assert result["option_id"] == "opt-1"
        assert result["was_chosen"] is False
        assert result["rejection_reason"] == "Too complex"


class TestUncertaintyDisclosure:
    """Tests for UncertaintyDisclosure dataclass."""

    def test_creation(self):
        """Test creating uncertainty disclosure."""
        uncertainty = UncertaintyDisclosure(
            overall_confidence=0.75,
            confidence_lower_bound=0.65,
            confidence_upper_bound=0.85,
            uncertainty_factors=["Limited data", "New domain"],
            assumptions_made=["Users will follow best practices"],
            validation_recommendations=["Run integration tests"],
            potential_failure_modes=["Memory exhaustion"],
        )
        assert uncertainty.overall_confidence == 0.75

    def test_to_dict(self):
        """Test dictionary conversion."""
        uncertainty = UncertaintyDisclosure(
            overall_confidence=0.8,
            uncertainty_factors=["factor1"],
        )
        result = uncertainty.to_dict()

        assert result["overall_confidence"] == 0.8
        assert "confidence_interval" in result
        assert result["confidence_interval"]["lower"] == 0.0
        assert result["uncertainty_factors"] == ["factor1"]


class TestDecisionContext:
    """Tests for DecisionContext dataclass."""

    def test_creation(self):
        """Test creating decision context."""
        context = DecisionContext(
            knowledge_sources=["/docs/api.md", "/src/service.py"],
            previous_decisions=["dec-001", "dec-002"],
            user_instructions="Fix the bug in authentication",
            environmental_factors={"environment": "production"},
            constraints=["Must not break API"],
            goals=["Improve security"],
        )
        assert len(context.knowledge_sources) == 2
        assert context.user_instructions == "Fix the bug in authentication"

    def test_defaults(self):
        """Test default values."""
        context = DecisionContext()
        assert context.knowledge_sources == []
        assert context.user_instructions == ""

    def test_to_dict(self):
        """Test dictionary conversion."""
        context = DecisionContext(
            knowledge_sources=["source1"],
            goals=["goal1"],
        )
        result = context.to_dict()

        assert result["knowledge_sources"] == ["source1"]
        assert result["goals"] == ["goal1"]


class TestDecisionRecord:
    """Tests for DecisionRecord dataclass."""

    def test_creation(self):
        """Test creating a decision record."""
        record = DecisionRecord(
            decision_id="dec-123",
            agent_id="agent-1",
            decision_type="code_review",
            decision_summary="Reviewed authentication module",
            severity=DecisionSeverity.SIGNIFICANT,
        )
        assert record.decision_id == "dec-123"
        assert record.severity == DecisionSeverity.SIGNIFICANT
        assert record.outcome == DecisionOutcome.PENDING

    def test_checksum_calculation(self):
        """Test checksum is calculated on creation."""
        record = DecisionRecord(
            decision_id="dec-123",
            agent_id="agent-1",
            decision_type="test",
            decision_summary="Test decision",
        )
        assert record.checksum != ""
        assert len(record.checksum) == 16

    def test_verify_integrity_valid(self):
        """Test integrity verification passes for unchanged record."""
        record = DecisionRecord(
            decision_id="dec-123",
            agent_id="agent-1",
            decision_type="test",
            decision_summary="Test",
        )
        assert record.verify_integrity() is True

    def test_verify_integrity_tampered(self):
        """Test integrity verification fails for tampered record."""
        record = DecisionRecord(
            decision_id="dec-123",
            agent_id="agent-1",
            decision_type="test",
            decision_summary="Test",
        )
        # Tamper with record
        record.decision_summary = "Modified"
        assert record.verify_integrity() is False

    def test_has_complete_transparency(self):
        """Test transparency completeness check."""
        record = DecisionRecord(
            decision_id="dec-123",
            agent_id="agent-1",
            decision_type="test",
            decision_summary="Test",
        )
        # Default record is incomplete
        assert record.has_complete_transparency() is False

        # Add reasoning chain
        record.reasoning_chain.append(
            ReasoningStep(step_number=1, description="Analysis")
        )
        # Add context
        record.context.knowledge_sources = ["/src/file.py"]
        # Uncertainty is already set by default

        assert record.has_complete_transparency() is True

    def test_has_alternatives(self):
        """Test alternatives check."""
        record = DecisionRecord(
            decision_id="dec-123",
            agent_id="agent-1",
        )
        assert record.has_alternatives() is False

        record.alternatives.append(
            AlternativeOption("opt-1", "Option 1", 0.8, was_chosen=True)
        )
        assert record.has_alternatives() is False  # Need >= 2

        record.alternatives.append(
            AlternativeOption("opt-2", "Option 2", 0.6, was_chosen=False)
        )
        assert record.has_alternatives() is True

    def test_to_dict(self):
        """Test dictionary conversion."""
        record = DecisionRecord(
            decision_id="dec-123",
            agent_id="agent-1",
            decision_type="code_review",
            decision_summary="Review complete",
            severity=DecisionSeverity.NORMAL,
        )
        record.action_taken = "Approved PR"
        record.human_reviewed = True
        record.human_reviewer = "reviewer-1"

        result = record.to_dict()

        assert result["decision_id"] == "dec-123"
        assert result["severity"] == "normal"
        assert result["action_taken"] == "Approved PR"
        assert result["human_reviewed"] is True
        assert "checksum" in result


class TestDecisionAuditLogger:
    """Tests for DecisionAuditLogger class."""

    @pytest.fixture
    def logger(self):
        """Create a fresh logger for each test."""
        return DecisionAuditLogger()

    def test_initialization(self, logger):
        """Test logger initialization."""
        assert logger._require_alternatives is True
        assert logger._require_reasoning_chain is True
        assert logger._require_uncertainty is True

    def test_custom_requirements(self):
        """Test custom requirement settings."""
        logger = DecisionAuditLogger(
            require_alternatives=False,
            require_reasoning_chain=False,
            require_uncertainty=False,
        )
        assert logger._require_alternatives is False

    def test_create_decision_record(self, logger):
        """Test creating a decision record."""
        record = logger.create_decision_record(
            decision_id="dec-123",
            agent_id="agent-1",
            decision_type="code_review",
            decision_summary="Review of auth module",
            severity=DecisionSeverity.SIGNIFICANT,
        )

        assert record.decision_id == "dec-123"
        assert record.agent_id == "agent-1"
        assert record.severity == DecisionSeverity.SIGNIFICANT

    def test_add_context(self, logger):
        """Test adding context to a record."""
        record = logger.create_decision_record(
            "dec-123", "agent-1", "test", "Test decision"
        )

        record = logger.add_context(
            record,
            knowledge_sources=["source1", "source2"],
            user_instructions="Fix the bug",
            goals=["Improve quality"],
        )

        assert record.context.knowledge_sources == ["source1", "source2"]
        assert record.context.user_instructions == "Fix the bug"

    def test_add_reasoning_step(self, logger):
        """Test adding reasoning steps."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")

        record = logger.add_reasoning_step(
            record,
            step_number=1,
            description="First step",
            evidence=["evidence1"],
            confidence=0.9,
        )
        record = logger.add_reasoning_step(
            record,
            step_number=2,
            description="Second step",
        )

        assert len(record.reasoning_chain) == 2
        assert record.reasoning_chain[0].step_number == 1
        assert record.reasoning_chain[1].step_number == 2

    def test_reasoning_steps_sorted(self, logger):
        """Test that reasoning steps are kept sorted."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")

        # Add out of order
        logger.add_reasoning_step(record, 3, "Third")
        logger.add_reasoning_step(record, 1, "First")
        logger.add_reasoning_step(record, 2, "Second")

        assert record.reasoning_chain[0].step_number == 1
        assert record.reasoning_chain[1].step_number == 2
        assert record.reasoning_chain[2].step_number == 3

    def test_add_alternative(self, logger):
        """Test adding alternatives."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")

        record = logger.add_alternative(
            record,
            option_id="opt-1",
            description="Option 1",
            confidence=0.8,
            pros=["pro1"],
            cons=["con1"],
            was_chosen=True,
        )
        record = logger.add_alternative(
            record,
            option_id="opt-2",
            description="Option 2",
            confidence=0.6,
            rejection_reason="Too complex",
        )

        assert len(record.alternatives) == 2
        assert record.alternatives[0].was_chosen is True
        assert record.alternatives[1].rejection_reason == "Too complex"

    def test_set_uncertainty(self, logger):
        """Test setting uncertainty."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")

        record = logger.set_uncertainty(
            record,
            overall_confidence=0.75,
            uncertainty_factors=["limited data"],
            assumptions_made=["stable environment"],
        )

        assert record.uncertainty.overall_confidence == 0.75
        assert "limited data" in record.uncertainty.uncertainty_factors

    def test_set_action(self, logger):
        """Test setting action."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")

        record = logger.set_action(
            record,
            action_taken="Applied fix to auth module",
            action_id="action-456",
        )

        assert record.action_taken == "Applied fix to auth module"
        assert record.action_id == "action-456"

    def test_validate_record_missing_reasoning(self, logger):
        """Test validation fails for missing reasoning chain."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        record.context.knowledge_sources = ["source"]

        is_valid, issues = logger.validate_record(record)
        assert is_valid is False
        assert any("reasoning chain" in issue.lower() for issue in issues)

    def test_validate_record_missing_alternatives(self, logger):
        """Test validation fails for significant decisions without alternatives."""
        record = logger.create_decision_record(
            "dec-123",
            "agent-1",
            "test",
            "Test",
            severity=DecisionSeverity.SIGNIFICANT,
        )
        record.context.knowledge_sources = ["source"]
        logger.add_reasoning_step(record, 1, "Step 1")

        is_valid, issues = logger.validate_record(record)
        assert is_valid is False
        assert any("alternatives" in issue.lower() for issue in issues)

    def test_validate_record_missing_context(self, logger):
        """Test validation fails for missing context."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        logger.add_reasoning_step(record, 1, "Step 1")

        is_valid, issues = logger.validate_record(record)
        assert is_valid is False
        assert any("context" in issue.lower() for issue in issues)

    def test_validate_record_valid(self, logger):
        """Test validation passes for complete record."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        logger.add_context(record, knowledge_sources=["source"])
        logger.add_reasoning_step(record, 1, "Analysis")
        logger.set_uncertainty(record, 0.8)

        is_valid, issues = logger.validate_record(record)
        assert is_valid is True

    def test_log_decision_success(self, logger):
        """Test logging a valid decision."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        logger.add_context(record, knowledge_sources=["source"])
        logger.add_reasoning_step(record, 1, "Step 1")
        logger.set_uncertainty(record, 0.8)

        success, issues = logger.log_decision(record)
        assert success is True
        assert logger.get_decision("dec-123") is not None

    def test_log_decision_fail_validation(self, logger):
        """Test logging fails for invalid record."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        # Missing required components

        success, issues = logger.log_decision(record)
        assert success is False
        assert len(issues) > 0

    def test_log_decision_force(self, logger):
        """Test forcing log of invalid record."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        # Missing required components

        success, issues = logger.log_decision(record, force=True)
        assert success is True  # Forced through
        assert len(issues) > 0  # But issues were noted

    def test_update_outcome(self, logger):
        """Test updating decision outcome."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        logger.add_context(record, user_instructions="test")
        logger.add_reasoning_step(record, 1, "Step")
        logger.log_decision(record)

        result = logger.update_outcome(
            "dec-123", DecisionOutcome.SUCCESSFUL, "All tests passed"
        )
        assert result is True

        updated = logger.get_decision("dec-123")
        assert updated.outcome == DecisionOutcome.SUCCESSFUL

    def test_update_outcome_not_found(self, logger):
        """Test updating non-existent decision."""
        result = logger.update_outcome("unknown", DecisionOutcome.FAILED)
        assert result is False

    def test_record_human_review(self, logger):
        """Test recording human review."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        logger.add_context(record, user_instructions="test")
        logger.add_reasoning_step(record, 1, "Step")
        logger.log_decision(record)

        result = logger.record_human_review(
            "dec-123",
            reviewer="reviewer-1",
            comments="Looks good",
        )
        assert result is True

        updated = logger.get_decision("dec-123")
        assert updated.human_reviewed is True
        assert updated.human_reviewer == "reviewer-1"

    def test_record_human_review_with_override(self, logger):
        """Test human review with outcome override."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        logger.add_context(record, user_instructions="test")
        logger.add_reasoning_step(record, 1, "Step")
        logger.log_decision(record)

        result = logger.record_human_review(
            "dec-123",
            reviewer="reviewer-1",
            comments="Rejecting this approach",
            override_outcome=DecisionOutcome.OVERRIDDEN,
        )
        assert result is True

        updated = logger.get_decision("dec-123")
        assert updated.outcome == DecisionOutcome.OVERRIDDEN

    def test_get_decisions_by_agent(self, logger):
        """Test getting decisions by agent."""
        for i in range(5):
            record = logger.create_decision_record(
                f"dec-{i}", "agent-1", "test", "Test"
            )
            logger.add_context(record, user_instructions="test")
            logger.add_reasoning_step(record, 1, "Step")
            logger.log_decision(record)

        decisions = logger.get_decisions_by_agent("agent-1")
        assert len(decisions) == 5

    def test_get_decisions_by_agent_limit(self, logger):
        """Test limit on decisions by agent."""
        for i in range(10):
            record = logger.create_decision_record(
                f"dec-{i}", "agent-1", "test", "Test"
            )
            logger.add_context(record, user_instructions="test")
            logger.add_reasoning_step(record, 1, "Step")
            logger.log_decision(record)

        decisions = logger.get_decisions_by_agent("agent-1", limit=5)
        assert len(decisions) == 5

    def test_get_decisions_needing_review(self, logger):
        """Test getting decisions needing review."""
        # Create significant decision
        record1 = logger.create_decision_record(
            "dec-1",
            "agent-1",
            "test",
            "Test",
            severity=DecisionSeverity.SIGNIFICANT,
        )
        logger.add_context(record1, user_instructions="test")
        logger.add_reasoning_step(record1, 1, "Step")
        logger.add_alternative(record1, "opt-1", "Option 1", 0.8, was_chosen=True)
        logger.add_alternative(record1, "opt-2", "Option 2", 0.6)
        logger.log_decision(record1)

        # Create normal decision
        record2 = logger.create_decision_record(
            "dec-2",
            "agent-1",
            "test",
            "Test",
            severity=DecisionSeverity.NORMAL,
        )
        logger.add_context(record2, user_instructions="test")
        logger.add_reasoning_step(record2, 1, "Step")
        logger.log_decision(record2)

        # Should get significant decision
        needing_review = logger.get_decisions_needing_review(
            severity_threshold=DecisionSeverity.SIGNIFICANT
        )
        assert len(needing_review) == 1
        assert needing_review[0].decision_id == "dec-1"

    def test_get_overridden_decisions(self, logger):
        """Test getting overridden decisions."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        logger.add_context(record, user_instructions="test")
        logger.add_reasoning_step(record, 1, "Step")
        logger.log_decision(record)
        logger.update_outcome("dec-123", DecisionOutcome.OVERRIDDEN)

        overridden = logger.get_overridden_decisions()
        assert len(overridden) == 1

    def test_get_metrics(self, logger):
        """Test getting metrics."""
        # Log some decisions
        for i in range(3):
            record = logger.create_decision_record(
                f"dec-{i}", "agent-1", "test", "Test"
            )
            logger.add_context(record, knowledge_sources=["source"])
            logger.add_reasoning_step(record, 1, "Step")
            logger.log_decision(record)

        metrics = logger.get_metrics()
        assert metrics["total_decisions"] == 3
        assert metrics["transparency_rate"] == 1.0
        assert metrics["decisions_stored"] == 3

    def test_export_decisions(self, logger):
        """Test exporting decisions."""
        for i in range(3):
            record = logger.create_decision_record(
                f"dec-{i}", "agent-1", "test", f"Test {i}"
            )
            logger.add_context(record, user_instructions="test")
            logger.add_reasoning_step(record, 1, "Step")
            logger.log_decision(record)

        exported = logger.export_decisions()
        assert len(exported) == 3

    def test_export_decisions_filtered(self, logger):
        """Test exporting with filters."""
        for i in range(3):
            record = logger.create_decision_record(
                f"dec-{i}", f"agent-{i % 2}", "test", "Test"
            )
            logger.add_context(record, user_instructions="test")
            logger.add_reasoning_step(record, 1, "Step")
            logger.log_decision(record)

        exported = logger.export_decisions(agent_id="agent-0")
        assert len(exported) == 2

    def test_clear_old_decisions(self, logger):
        """Test clearing old decisions."""
        record = logger.create_decision_record("dec-old", "agent-1", "test", "Test")
        record.timestamp = datetime.now(timezone.utc) - timedelta(days=100)
        logger.add_context(record, user_instructions="test")
        logger.add_reasoning_step(record, 1, "Step")
        logger.log_decision(record)

        cleared = logger.clear_old_decisions(older_than=timedelta(days=90))
        assert cleared == 1
        assert logger.get_decision("dec-old") is None

    def test_persistence_callback(self):
        """Test persistence callback is called."""
        mock_callback = MagicMock()
        logger = DecisionAuditLogger(persistence_callback=mock_callback)

        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        logger.add_context(record, user_instructions="test")
        logger.add_reasoning_step(record, 1, "Step")
        logger.log_decision(record)

        assert mock_callback.called

    def test_metrics_override_counting(self, logger):
        """Test that override count is tracked."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        logger.add_context(record, user_instructions="test")
        logger.add_reasoning_step(record, 1, "Step")
        logger.log_decision(record)

        logger.update_outcome("dec-123", DecisionOutcome.OVERRIDDEN)

        metrics = logger.get_metrics()
        assert metrics["decisions_overridden"] == 1

    def test_alternatives_metric(self, logger):
        """Test alternatives metric tracking."""
        record = logger.create_decision_record("dec-123", "agent-1", "test", "Test")
        logger.add_context(record, user_instructions="test")
        logger.add_reasoning_step(record, 1, "Step")
        logger.add_alternative(record, "opt-1", "Option 1", 0.8, was_chosen=True)
        logger.add_alternative(record, "opt-2", "Option 2", 0.6)
        logger.log_decision(record)

        metrics = logger.get_metrics()
        assert metrics["decisions_with_alternatives"] == 1
