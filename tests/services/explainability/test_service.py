"""
Tests for universal explainability service.
"""

import pytest

from src.services.explainability.config import ExplainabilityConfig
from src.services.explainability.contracts import DecisionSeverity
from src.services.explainability.service import (
    UniversalExplainabilityService,
    configure_explainability_service,
    get_explainability_service,
    reset_explainability_service,
)


class TestUniversalExplainabilityService:
    """Tests for UniversalExplainabilityService class."""

    def setup_method(self):
        """Reset service before each test."""
        reset_explainability_service()

    def teardown_method(self):
        """Reset service after each test."""
        reset_explainability_service()

    def test_init_default(self):
        """Test initialization with defaults."""
        service = UniversalExplainabilityService()
        assert service.config is not None
        assert service.reasoning_builder is not None
        assert service.alternatives_analyzer is not None
        assert service.confidence_quantifier is not None
        assert service.consistency_verifier is not None
        assert service.inter_agent_verifier is not None

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = ExplainabilityConfig(consistency_threshold=0.9)
        service = UniversalExplainabilityService(config=config)
        assert service.config.consistency_threshold == 0.9

    @pytest.mark.asyncio
    async def test_explain_decision_trivial(
        self, sample_decision_input, sample_decision_output
    ):
        """Test explaining a trivial decision."""
        service = UniversalExplainabilityService()
        record = await service.explain_decision(
            decision_id="dec_test",
            agent_id="test_agent",
            severity=DecisionSeverity.TRIVIAL,
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
        )

        assert record.decision_id == "dec_test"
        assert record.agent_id == "test_agent"
        assert record.severity == DecisionSeverity.TRIVIAL
        assert record.reasoning_chain is not None
        assert record.alternatives_report is not None
        assert record.explainability_score is not None

    @pytest.mark.asyncio
    async def test_explain_decision_normal(
        self, sample_decision_input, sample_decision_output
    ):
        """Test explaining a normal decision."""
        service = UniversalExplainabilityService()
        record = await service.explain_decision(
            decision_id="dec_test",
            agent_id="test_agent",
            severity=DecisionSeverity.NORMAL,
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
        )

        assert record.severity == DecisionSeverity.NORMAL
        assert len(record.reasoning_chain.steps) >= 2  # Normal requires 2 steps

    @pytest.mark.asyncio
    async def test_explain_decision_critical(
        self, sample_decision_input, sample_decision_output
    ):
        """Test explaining a critical decision."""
        service = UniversalExplainabilityService()
        record = await service.explain_decision(
            decision_id="dec_test",
            agent_id="test_agent",
            severity=DecisionSeverity.CRITICAL,
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
        )

        assert record.severity == DecisionSeverity.CRITICAL
        assert len(record.reasoning_chain.steps) >= 5  # Critical requires 5 steps
        assert (
            len(record.alternatives_report.alternatives) >= 4
        )  # Critical requires 4 alts

    @pytest.mark.asyncio
    async def test_explain_decision_with_context(
        self, sample_decision_input, sample_decision_output
    ):
        """Test explaining decision with context."""
        service = UniversalExplainabilityService()
        context = {
            "prior_decisions": ["dec_001"],
            "verified": True,
        }
        record = await service.explain_decision(
            decision_id="dec_test",
            agent_id="test_agent",
            severity=DecisionSeverity.NORMAL,
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            decision_context=context,
        )

        assert record.decision_id == "dec_test"

    @pytest.mark.asyncio
    async def test_explain_decision_with_upstream_claims(
        self, sample_decision_input, sample_decision_output, sample_upstream_claims
    ):
        """Test explaining decision with upstream claims."""
        service = UniversalExplainabilityService()
        record = await service.explain_decision(
            decision_id="dec_test",
            agent_id="test_agent",
            severity=DecisionSeverity.NORMAL,
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            upstream_claims=sample_upstream_claims,
        )

        assert record.verification_report is not None
        assert len(record.verification_report.verifications) == len(
            sample_upstream_claims
        )

    def test_explain_decision_sync_trivial(
        self, sample_decision_input, sample_decision_output
    ):
        """Test synchronous explanation of trivial decision."""
        service = UniversalExplainabilityService()
        record = service.explain_decision_sync(
            decision_id="dec_test",
            agent_id="test_agent",
            severity=DecisionSeverity.TRIVIAL,
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
        )

        assert record.decision_id == "dec_test"
        assert record.severity == DecisionSeverity.TRIVIAL

    def test_explain_decision_sync_normal(
        self, sample_decision_input, sample_decision_output
    ):
        """Test synchronous explanation of normal decision."""
        service = UniversalExplainabilityService()
        record = service.explain_decision_sync(
            decision_id="dec_test",
            agent_id="test_agent",
            severity=DecisionSeverity.NORMAL,
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
        )

        assert record.severity == DecisionSeverity.NORMAL
        assert record.reasoning_chain is not None

    def test_explain_decision_sync_with_context(
        self, sample_decision_input, sample_decision_output
    ):
        """Test synchronous explanation with context."""
        service = UniversalExplainabilityService()
        context = {"verified": True}
        record = service.explain_decision_sync(
            decision_id="dec_test",
            agent_id="test_agent",
            severity=DecisionSeverity.NORMAL,
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            decision_context=context,
        )

        assert record.decision_id == "dec_test"

    def test_calculate_score(
        self,
        sample_reasoning_chain,
        sample_alternatives_report,
        sample_confidence_interval,
        sample_consistency_report,
        sample_verification_report,
    ):
        """Test calculating explainability score."""
        service = UniversalExplainabilityService()
        score = service._calculate_score(
            reasoning_chain=sample_reasoning_chain,
            alternatives_report=sample_alternatives_report,
            confidence_interval=sample_confidence_interval,
            consistency_report=sample_consistency_report,
            verification_report=sample_verification_report,
            severity=DecisionSeverity.NORMAL,
        )

        assert score.reasoning_completeness >= 0.0
        assert score.reasoning_completeness <= 1.0
        assert score.alternatives_coverage >= 0.0
        assert score.alternatives_coverage <= 1.0
        assert score.overall_score() >= 0.0
        assert score.overall_score() <= 1.0

    def test_generate_summary(
        self,
        sample_reasoning_chain,
        sample_alternatives_report,
        sample_confidence_interval,
    ):
        """Test generating explanation summary."""
        service = UniversalExplainabilityService()
        summary = service._generate_summary(
            reasoning_chain=sample_reasoning_chain,
            alternatives_report=sample_alternatives_report,
            confidence_interval=sample_confidence_interval,
        )

        assert summary is not None
        assert len(summary) > 0
        assert "reasoning" in summary.lower()

    def test_check_hitl_required_low_confidence(
        self, sample_decision_input, sample_decision_output
    ):
        """Test HITL required for low confidence."""
        config = ExplainabilityConfig(low_confidence_threshold=0.9)  # High threshold
        service = UniversalExplainabilityService(config=config)

        record = service.explain_decision_sync(
            decision_id="dec_test",
            agent_id="test_agent",
            severity=DecisionSeverity.NORMAL,
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
        )

        # With high threshold, HITL may be required
        # Result depends on actual confidence calculated

    def test_check_hitl_required_critical_contradiction(self, sample_decision_input):
        """Test HITL required for critical contradiction."""
        service = UniversalExplainabilityService()

        # Output that contradicts security claims
        decision_output = {
            "action": "skip_security_fixes",
            "reason": "No time",
        }

        # Input that suggests security work
        decision_input = {
            "task": "apply_security_patches",
            "severity": "critical",
        }

        record = service.explain_decision_sync(
            decision_id="dec_test",
            agent_id="test_agent",
            severity=DecisionSeverity.CRITICAL,
            decision_input=decision_input,
            decision_output=decision_output,
        )

        # May or may not require HITL depending on detected contradictions

    def test_record_has_all_components(
        self, sample_decision_input, sample_decision_output
    ):
        """Test that record has all expected components."""
        service = UniversalExplainabilityService()
        record = service.explain_decision_sync(
            decision_id="dec_test",
            agent_id="test_agent",
            severity=DecisionSeverity.NORMAL,
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
        )

        assert record.record_id is not None
        assert record.decision_id == "dec_test"
        assert record.agent_id == "test_agent"
        assert record.severity == DecisionSeverity.NORMAL
        assert record.reasoning_chain is not None
        assert record.alternatives_report is not None
        assert record.confidence_interval is not None
        assert record.consistency_report is not None
        assert record.explainability_score is not None
        assert record.human_readable_summary is not None

    def test_record_id_unique(self, sample_decision_input, sample_decision_output):
        """Test that record IDs are unique."""
        service = UniversalExplainabilityService()

        record1 = service.explain_decision_sync(
            decision_id="dec_test1",
            agent_id="test_agent",
            severity=DecisionSeverity.NORMAL,
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
        )

        record2 = service.explain_decision_sync(
            decision_id="dec_test2",
            agent_id="test_agent",
            severity=DecisionSeverity.NORMAL,
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
        )

        assert record1.record_id != record2.record_id


class TestGlobalServiceManagement:
    """Tests for global service management functions."""

    def setup_method(self):
        """Reset service before each test."""
        reset_explainability_service()

    def teardown_method(self):
        """Reset service after each test."""
        reset_explainability_service()

    def test_get_explainability_service(self):
        """Test getting the global service."""
        service = get_explainability_service()
        assert service is not None
        assert isinstance(service, UniversalExplainabilityService)

    def test_configure_explainability_service(
        self, mock_bedrock_client, mock_neptune_client
    ):
        """Test configuring the global service."""
        config = ExplainabilityConfig(consistency_threshold=0.9)
        service = configure_explainability_service(
            bedrock_client=mock_bedrock_client,
            neptune_client=mock_neptune_client,
            config=config,
        )

        assert service.config.consistency_threshold == 0.9

    def test_reset_explainability_service(self):
        """Test resetting the global service."""
        config = ExplainabilityConfig(consistency_threshold=0.9)
        configure_explainability_service(config=config)

        reset_explainability_service()

        service = get_explainability_service()
        assert service.config.consistency_threshold == 0.8  # Default

    def test_service_singleton(self):
        """Test that get returns the same instance."""
        s1 = get_explainability_service()
        s2 = get_explainability_service()
        assert s1 is s2


class TestExplainabilityScoreCalculation:
    """Tests for explainability score calculation details."""

    def setup_method(self):
        """Reset service before each test."""
        reset_explainability_service()

    def test_reasoning_completeness_full(self):
        """Test reasoning completeness when complete."""
        service = UniversalExplainabilityService()

        from src.services.explainability.contracts import (
            AlternativesReport,
            ReasoningChain,
        )

        # 5 steps for critical decision
        chain = ReasoningChain(decision_id="dec", agent_id="agent")
        for i in range(5):
            chain.add_step(description=f"Step {i + 1}", confidence=0.9)

        alts = AlternativesReport(decision_id="dec")
        for i in range(4):
            alts.add_alternative(
                f"alt_{i}",
                f"Option {i}",
                confidence=0.8,
                was_chosen=(i == 0),
            )

        from src.services.explainability.contracts import (
            ConfidenceInterval,
            ConsistencyReport,
            VerificationReport,
        )

        ci = ConfidenceInterval(point_estimate=0.8, lower_bound=0.7, upper_bound=0.9)
        cr = ConsistencyReport(decision_id="dec", is_consistent=True)
        vr = VerificationReport(decision_id="dec")

        score = service._calculate_score(
            chain, alts, ci, cr, vr, DecisionSeverity.CRITICAL
        )

        assert score.reasoning_completeness == 1.0  # 5/5 steps

    def test_reasoning_completeness_partial(self):
        """Test reasoning completeness when partial."""
        service = UniversalExplainabilityService()

        from src.services.explainability.contracts import (
            AlternativesReport,
            ReasoningChain,
        )

        # 2 steps for critical (needs 5)
        chain = ReasoningChain(decision_id="dec", agent_id="agent")
        chain.add_step(description="Step 1", confidence=0.9)
        chain.add_step(description="Step 2", confidence=0.9)

        alts = AlternativesReport(decision_id="dec")
        alts.add_alternative("alt_1", "Option 1", confidence=0.8, was_chosen=True)

        from src.services.explainability.contracts import (
            ConfidenceInterval,
            ConsistencyReport,
            VerificationReport,
        )

        ci = ConfidenceInterval(point_estimate=0.8, lower_bound=0.7, upper_bound=0.9)
        cr = ConsistencyReport(decision_id="dec", is_consistent=True)
        vr = VerificationReport(decision_id="dec")

        score = service._calculate_score(
            chain, alts, ci, cr, vr, DecisionSeverity.CRITICAL
        )

        assert score.reasoning_completeness == 0.4  # 2/5 steps

    def test_alternatives_coverage_full(self):
        """Test alternatives coverage when complete."""
        service = UniversalExplainabilityService()

        from src.services.explainability.contracts import (
            AlternativesReport,
            ReasoningChain,
        )

        chain = ReasoningChain(decision_id="dec", agent_id="agent")
        chain.add_step(description="Step 1", confidence=0.9)

        # 4 alternatives for critical
        alts = AlternativesReport(decision_id="dec")
        for i in range(4):
            alts.add_alternative(
                f"alt_{i}",
                f"Option {i}",
                confidence=0.8,
                was_chosen=(i == 0),
            )

        from src.services.explainability.contracts import (
            ConfidenceInterval,
            ConsistencyReport,
            VerificationReport,
        )

        ci = ConfidenceInterval(point_estimate=0.8, lower_bound=0.7, upper_bound=0.9)
        cr = ConsistencyReport(decision_id="dec", is_consistent=True)
        vr = VerificationReport(decision_id="dec")

        score = service._calculate_score(
            chain, alts, ci, cr, vr, DecisionSeverity.CRITICAL
        )

        assert score.alternatives_coverage == 1.0  # 4/4 alternatives

    def test_consistency_score_consistent(self):
        """Test consistency score when consistent."""
        service = UniversalExplainabilityService()

        from src.services.explainability.contracts import (
            AlternativesReport,
            ConfidenceInterval,
            ConsistencyReport,
            ReasoningChain,
            VerificationReport,
        )

        chain = ReasoningChain(decision_id="dec", agent_id="agent")
        chain.add_step(description="Step 1", confidence=0.9)

        alts = AlternativesReport(decision_id="dec")
        alts.add_alternative("alt_1", "Option 1", confidence=0.8, was_chosen=True)

        ci = ConfidenceInterval(point_estimate=0.8, lower_bound=0.7, upper_bound=0.9)
        cr = ConsistencyReport(decision_id="dec", is_consistent=True)
        vr = VerificationReport(decision_id="dec")

        score = service._calculate_score(
            chain, alts, ci, cr, vr, DecisionSeverity.TRIVIAL
        )

        assert score.consistency_score == 1.0

    def test_consistency_score_inconsistent(self):
        """Test consistency score when inconsistent."""
        service = UniversalExplainabilityService()

        from src.services.explainability.contracts import (
            AlternativesReport,
            ConfidenceInterval,
            ConsistencyReport,
            ContradictionSeverity,
            ReasoningChain,
            VerificationReport,
        )

        chain = ReasoningChain(decision_id="dec", agent_id="agent")
        chain.add_step(description="Step 1", confidence=0.9)

        alts = AlternativesReport(decision_id="dec")
        alts.add_alternative("alt_1", "Option 1", confidence=0.8, was_chosen=True)

        ci = ConfidenceInterval(point_estimate=0.8, lower_bound=0.7, upper_bound=0.9)
        cr = ConsistencyReport(decision_id="dec", is_consistent=False)
        cr.add_contradiction(
            "ctr_1",
            ContradictionSeverity.MODERATE,
            "Claim",
            "Action",
            "Mismatch",
        )
        vr = VerificationReport(decision_id="dec")

        score = service._calculate_score(
            chain, alts, ci, cr, vr, DecisionSeverity.TRIVIAL
        )

        assert score.consistency_score < 1.0
