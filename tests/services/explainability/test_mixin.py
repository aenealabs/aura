"""
Tests for explainability mixin.
"""

from unittest.mock import MagicMock

import pytest

from src.services.explainability.contracts import DecisionSeverity
from src.services.explainability.mixin import ExplainabilityMixin
from src.services.explainability.service import (
    UniversalExplainabilityService,
    reset_explainability_service,
)


class MockAgent(ExplainabilityMixin):
    """Mock agent for testing the mixin."""

    def __init__(self, agent_id: str = "test_agent"):
        self.agent_id = agent_id


class TestExplainabilityMixin:
    """Tests for ExplainabilityMixin class."""

    def setup_method(self):
        """Reset service before each test."""
        reset_explainability_service()

    def teardown_method(self):
        """Reset service after each test."""
        reset_explainability_service()

    def test_get_explainability_service(self):
        """Test getting explainability service."""
        agent = MockAgent()
        service = agent.get_explainability_service()

        assert service is not None
        assert isinstance(service, UniversalExplainabilityService)

    def test_set_explainability_service(self):
        """Test setting custom explainability service."""
        agent = MockAgent()
        mock_service = MagicMock(spec=UniversalExplainabilityService)
        agent.set_explainability_service(mock_service)

        assert agent._explainability_service is mock_service

    def test_start_explanation(self):
        """Test starting explanation tracking."""
        agent = MockAgent()
        decision_input = {"task": "test"}

        decision_id = agent.start_explanation(
            decision_input=decision_input,
            severity=DecisionSeverity.NORMAL,
        )

        assert decision_id is not None
        assert agent._current_decision_id == decision_id
        assert agent._current_decision_input == decision_input
        assert agent._current_severity == DecisionSeverity.NORMAL

    def test_start_explanation_with_custom_id(self):
        """Test starting explanation with custom decision ID."""
        agent = MockAgent()
        custom_id = "custom_dec_123"

        decision_id = agent.start_explanation(
            decision_input={"task": "test"},
            decision_id=custom_id,
        )

        assert decision_id == custom_id
        assert agent._current_decision_id == custom_id

    def test_start_explanation_with_context(self):
        """Test starting explanation with context."""
        agent = MockAgent()
        context = {"prior_decisions": ["dec_001"]}

        agent.start_explanation(
            decision_input={"task": "test"},
            context=context,
        )

        assert agent._current_context == context

    def test_start_explanation_with_upstream_claims(self):
        """Test starting explanation with upstream claims."""
        agent = MockAgent()
        claims = [{"agent_id": "upstream", "claim_text": "test"}]

        agent.start_explanation(
            decision_input={"task": "test"},
            upstream_claims=claims,
        )

        assert agent._current_upstream_claims == claims

    @pytest.mark.asyncio
    async def test_complete_explanation(self):
        """Test completing explanation."""
        agent = MockAgent()

        agent.start_explanation(
            decision_input={"task": "security_review"},
            severity=DecisionSeverity.NORMAL,
        )

        record = await agent.complete_explanation(
            decision_output={"action": "flag_vulnerability"},
        )

        assert record is not None
        assert record.agent_id == "test_agent"
        # Tracking state should be cleared
        assert agent._current_decision_id is None

    @pytest.mark.asyncio
    async def test_complete_explanation_without_start_raises(self):
        """Test that completing without starting raises error."""
        agent = MockAgent()

        with pytest.raises(ValueError, match="No decision being tracked"):
            await agent.complete_explanation(
                decision_output={"action": "test"},
            )

    @pytest.mark.asyncio
    async def test_complete_explanation_with_additional_context(self):
        """Test completing with additional context."""
        agent = MockAgent()

        agent.start_explanation(
            decision_input={"task": "test"},
            context={"initial": "context"},
        )

        record = await agent.complete_explanation(
            decision_output={"action": "done"},
            additional_context={"additional": "data"},
        )

        assert record is not None

    def test_complete_explanation_sync(self):
        """Test synchronous explanation completion."""
        agent = MockAgent()

        agent.start_explanation(
            decision_input={"task": "test"},
            severity=DecisionSeverity.TRIVIAL,
        )

        record = agent.complete_explanation_sync(
            decision_output={"result": "success"},
        )

        assert record is not None
        assert record.agent_id == "test_agent"
        assert agent._current_decision_id is None

    def test_complete_explanation_sync_without_start_raises(self):
        """Test that sync completing without starting raises error."""
        agent = MockAgent()

        with pytest.raises(ValueError, match="No decision being tracked"):
            agent.complete_explanation_sync(
                decision_output={"action": "test"},
            )

    def test_clear_tracking_state(self):
        """Test clearing tracking state."""
        agent = MockAgent()

        agent.start_explanation(
            decision_input={"task": "test"},
            context={"key": "value"},
            upstream_claims=[{"claim": "test"}],
        )

        agent._clear_tracking_state()

        assert agent._current_decision_id is None
        assert agent._current_decision_input is None
        assert agent._current_severity is None
        assert agent._current_context is None
        assert agent._current_upstream_claims is None

    def test_add_upstream_claim(self):
        """Test adding upstream claim."""
        agent = MockAgent()

        agent.start_explanation(decision_input={"task": "test"})

        agent.add_upstream_claim(
            agent_id="scanner",
            claim_type="security_assessment",
            claim_text="Found vulnerability",
            evidence=["CVE-2024-001"],
            confidence=0.9,
        )

        assert len(agent._current_upstream_claims) == 1
        assert agent._current_upstream_claims[0]["agent_id"] == "scanner"

    def test_add_multiple_upstream_claims(self):
        """Test adding multiple upstream claims."""
        agent = MockAgent()

        agent.start_explanation(decision_input={"task": "test"})

        agent.add_upstream_claim(
            agent_id="scanner",
            claim_type="security",
            claim_text="Claim 1",
        )
        agent.add_upstream_claim(
            agent_id="tester",
            claim_type="test",
            claim_text="Claim 2",
        )

        assert len(agent._current_upstream_claims) == 2

    def test_add_context(self):
        """Test adding context."""
        agent = MockAgent()

        agent.start_explanation(decision_input={"task": "test"})

        agent.add_context("key1", "value1")
        agent.add_context("key2", {"nested": "value"})

        assert agent._current_context["key1"] == "value1"
        assert agent._current_context["key2"] == {"nested": "value"}

    def test_add_context_creates_dict_if_none(self):
        """Test that add_context creates dict if none exists."""
        agent = MockAgent()

        # Don't start with context
        agent.start_explanation(decision_input={"task": "test"})
        agent._current_context = None

        agent.add_context("key", "value")

        assert agent._current_context == {"key": "value"}

    @pytest.mark.asyncio
    async def test_explain_standalone(self):
        """Test standalone explanation."""
        agent = MockAgent()

        record = await agent.explain_standalone(
            decision_id="dec_standalone",
            decision_input={"task": "analyze"},
            decision_output={"result": "done"},
            severity=DecisionSeverity.NORMAL,
        )

        assert record is not None
        assert record.decision_id == "dec_standalone"
        assert record.agent_id == "test_agent"

    @pytest.mark.asyncio
    async def test_explain_standalone_with_context(self):
        """Test standalone explanation with context."""
        agent = MockAgent()

        record = await agent.explain_standalone(
            decision_id="dec_standalone",
            decision_input={"task": "analyze"},
            decision_output={"result": "done"},
            context={"verified": True},
        )

        assert record is not None

    def test_explain_standalone_sync(self):
        """Test synchronous standalone explanation."""
        agent = MockAgent()

        record = agent.explain_standalone_sync(
            decision_id="dec_standalone",
            decision_input={"task": "analyze"},
            decision_output={"result": "done"},
            severity=DecisionSeverity.TRIVIAL,
        )

        assert record is not None
        assert record.decision_id == "dec_standalone"

    def test_requires_hitl(self, sample_explainability_record):
        """Test checking if HITL is required."""
        agent = MockAgent()

        # Record without HITL
        assert agent.requires_hitl(sample_explainability_record) is False

        # Modify to require HITL
        sample_explainability_record.hitl_required = True
        assert agent.requires_hitl(sample_explainability_record) is True

    def test_get_explanation_summary(self, sample_explainability_record):
        """Test getting explanation summary."""
        agent = MockAgent()

        summary = agent.get_explanation_summary(sample_explainability_record)
        assert summary == sample_explainability_record.human_readable_summary

    def test_get_explanation_summary_no_summary(self, sample_explainability_record):
        """Test getting summary when none available."""
        agent = MockAgent()
        sample_explainability_record.human_readable_summary = ""

        summary = agent.get_explanation_summary(sample_explainability_record)
        assert summary == "No summary available"


class TestMixinIntegration:
    """Integration tests for the mixin with actual agent workflow."""

    def setup_method(self):
        """Reset service before each test."""
        reset_explainability_service()

    def teardown_method(self):
        """Reset service after each test."""
        reset_explainability_service()

    def test_full_workflow_sync(self):
        """Test full synchronous workflow."""
        agent = MockAgent(agent_id="security_agent")

        # Start explanation
        decision_id = agent.start_explanation(
            decision_input={
                "task": "security_review",
                "code": "eval(input)",
            },
            severity=DecisionSeverity.CRITICAL,
        )

        # Add context during processing
        agent.add_context("scan_time", "2024-01-01T00:00:00Z")

        # Add upstream claims
        agent.add_upstream_claim(
            agent_id="static_analyzer",
            claim_type="code_analysis",
            claim_text="Found dangerous eval() usage",
            evidence=["Line 42: eval(input)"],
            confidence=0.95,
        )

        # Complete explanation
        record = agent.complete_explanation_sync(
            decision_output={
                "action": "flag_vulnerability",
                "severity": "critical",
                "recommendation": "Replace eval() with json.loads()",
            },
        )

        # Verify record
        assert record.decision_id == decision_id
        assert record.agent_id == "security_agent"
        assert record.severity == DecisionSeverity.CRITICAL
        assert record.reasoning_chain is not None
        assert record.verification_report is not None
        assert len(record.verification_report.verifications) == 1

    @pytest.mark.asyncio
    async def test_full_workflow_async(self):
        """Test full asynchronous workflow."""
        agent = MockAgent(agent_id="review_agent")

        # Start explanation
        decision_id = agent.start_explanation(
            decision_input={
                "task": "code_review",
                "file": "app.py",
            },
            severity=DecisionSeverity.SIGNIFICANT,
            context={"reviewer": "ai_agent"},
        )

        # Add more context
        agent.add_context("review_depth", "thorough")

        # Complete explanation
        record = await agent.complete_explanation(
            decision_output={
                "recommendation": "approve_with_changes",
                "findings": ["Minor style issues", "Missing docstring"],
            },
            additional_context={"review_completed": True},
        )

        # Verify
        assert record.decision_id == decision_id
        assert record.agent_id == "review_agent"
        assert record.severity == DecisionSeverity.SIGNIFICANT

    def test_multiple_decisions_workflow(self):
        """Test handling multiple decisions sequentially."""
        agent = MockAgent(agent_id="multi_decision_agent")

        # First decision
        agent.start_explanation(
            decision_input={"task": "analyze"},
            severity=DecisionSeverity.NORMAL,
        )
        record1 = agent.complete_explanation_sync(
            decision_output={"result": "analyzed"},
        )

        # Second decision
        agent.start_explanation(
            decision_input={"task": "fix"},
            severity=DecisionSeverity.NORMAL,
        )
        record2 = agent.complete_explanation_sync(
            decision_output={"result": "fixed"},
        )

        # Both should have unique record IDs
        assert record1.record_id != record2.record_id
        assert record1.decision_id != record2.decision_id

    def test_agent_id_inheritance(self):
        """Test that agent_id is properly inherited from implementing class."""

        class CustomAgent(ExplainabilityMixin):
            agent_id = "custom_specialized_agent"

        agent = CustomAgent()
        record = agent.explain_standalone_sync(
            decision_id="dec_test",
            decision_input={"task": "test"},
            decision_output={"result": "done"},
        )

        assert record.agent_id == "custom_specialized_agent"
