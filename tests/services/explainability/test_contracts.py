"""
Tests for explainability contracts.
"""

from dataclasses import asdict

from src.services.explainability.contracts import (
    Alternative,
    AlternativesReport,
    CalibrationMethod,
    ClaimVerification,
    ConfidenceInterval,
    ConsistencyReport,
    Contradiction,
    ContradictionSeverity,
    DecisionSeverity,
    ExplainabilityRecord,
    ExplainabilityScore,
    ReasoningChain,
    ReasoningStep,
    VerificationReport,
    VerificationStatus,
)


class TestDecisionSeverity:
    """Tests for DecisionSeverity enum."""

    def test_severity_values(self):
        """Test all severity levels exist."""
        assert DecisionSeverity.TRIVIAL.value == "trivial"
        assert DecisionSeverity.NORMAL.value == "normal"
        assert DecisionSeverity.SIGNIFICANT.value == "significant"
        assert DecisionSeverity.CRITICAL.value == "critical"

    def test_severity_ordering(self):
        """Test severity levels can be compared."""
        severities = [s.value for s in DecisionSeverity]
        assert severities == ["trivial", "normal", "significant", "critical"]


class TestContradictionSeverity:
    """Tests for ContradictionSeverity enum."""

    def test_contradiction_severity_values(self):
        """Test all contradiction severity levels exist."""
        assert ContradictionSeverity.MINOR.value == "minor"
        assert ContradictionSeverity.MODERATE.value == "moderate"
        assert ContradictionSeverity.MAJOR.value == "major"
        assert ContradictionSeverity.CRITICAL.value == "critical"


class TestVerificationStatus:
    """Tests for VerificationStatus enum."""

    def test_verification_status_values(self):
        """Test all verification statuses exist."""
        assert VerificationStatus.VERIFIED.value == "verified"
        assert VerificationStatus.UNVERIFIED.value == "unverified"
        assert VerificationStatus.FAILED.value == "failed"
        assert VerificationStatus.PENDING.value == "pending"


class TestCalibrationMethod:
    """Tests for CalibrationMethod enum."""

    def test_calibration_method_values(self):
        """Test all calibration methods exist."""
        assert CalibrationMethod.ENSEMBLE_DISAGREEMENT.value == "ensemble_disagreement"
        assert CalibrationMethod.MONTE_CARLO_DROPOUT.value == "monte_carlo_dropout"
        assert CalibrationMethod.TEMPERATURE_SCALING.value == "temperature_scaling"
        assert CalibrationMethod.PLATT_SCALING.value == "platt_scaling"


class TestReasoningStep:
    """Tests for ReasoningStep dataclass."""

    def test_create_reasoning_step(self):
        """Test creating a reasoning step."""
        step = ReasoningStep(
            step_number=1,
            description="Analyzed the code",
            evidence=["Found vulnerability"],
            confidence=0.9,
            references=["CWE-94"],
        )
        assert step.step_number == 1
        assert step.description == "Analyzed the code"
        assert step.confidence == 0.9
        assert len(step.evidence) == 1
        assert len(step.references) == 1

    def test_default_values(self):
        """Test default values for reasoning step."""
        step = ReasoningStep(
            step_number=1,
            description="Test step",
        )
        assert step.evidence == []
        assert step.confidence == 1.0
        assert step.references == []


class TestReasoningChain:
    """Tests for ReasoningChain dataclass."""

    def test_create_reasoning_chain(self):
        """Test creating a reasoning chain."""
        chain = ReasoningChain(
            decision_id="dec_001",
            agent_id="test_agent",
        )
        assert chain.decision_id == "dec_001"
        assert chain.agent_id == "test_agent"
        assert chain.steps == []

    def test_add_step(self):
        """Test adding a step to the chain."""
        chain = ReasoningChain(decision_id="dec_001", agent_id="test_agent")
        chain.add_step(
            description="First step",
            evidence=["Evidence 1"],
            confidence=0.8,
        )
        assert len(chain.steps) == 1
        assert chain.steps[0].step_number == 1
        assert chain.steps[0].description == "First step"

    def test_add_multiple_steps(self):
        """Test adding multiple steps."""
        chain = ReasoningChain(decision_id="dec_001", agent_id="test_agent")
        chain.add_step(description="Step 1", confidence=0.9)
        chain.add_step(description="Step 2", confidence=0.8)
        chain.add_step(description="Step 3", confidence=0.85)

        assert len(chain.steps) == 3
        assert chain.steps[0].step_number == 1
        assert chain.steps[1].step_number == 2
        assert chain.steps[2].step_number == 3

    def test_total_confidence(self):
        """Test total confidence calculation."""
        chain = ReasoningChain(decision_id="dec_001", agent_id="test_agent")
        chain.add_step(description="Step 1", confidence=0.9)
        chain.add_step(description="Step 2", confidence=0.8)

        # Total confidence should be product of step confidences
        expected = 0.9 * 0.8
        assert abs(chain.total_confidence - expected) < 0.001

    def test_total_confidence_empty_chain(self):
        """Test total confidence with no steps."""
        chain = ReasoningChain(decision_id="dec_001", agent_id="test_agent")
        assert chain.total_confidence == 1.0

    def test_is_complete_trivial(self):
        """Test completeness check for trivial decisions."""
        chain = ReasoningChain(decision_id="dec_001", agent_id="test_agent")
        chain.add_step(description="Step 1", confidence=0.9)

        assert chain.is_complete(DecisionSeverity.TRIVIAL) is True
        assert chain.is_complete(DecisionSeverity.NORMAL) is False

    def test_is_complete_normal(self):
        """Test completeness check for normal decisions."""
        chain = ReasoningChain(decision_id="dec_001", agent_id="test_agent")
        chain.add_step(description="Step 1", confidence=0.9)
        chain.add_step(description="Step 2", confidence=0.85)

        assert chain.is_complete(DecisionSeverity.NORMAL) is True
        assert chain.is_complete(DecisionSeverity.SIGNIFICANT) is False

    def test_is_complete_significant(self):
        """Test completeness check for significant decisions."""
        chain = ReasoningChain(decision_id="dec_001", agent_id="test_agent")
        for i in range(3):
            chain.add_step(description=f"Step {i + 1}", confidence=0.9)

        assert chain.is_complete(DecisionSeverity.SIGNIFICANT) is True

    def test_is_complete_critical(self):
        """Test completeness check for critical decisions."""
        chain = ReasoningChain(decision_id="dec_001", agent_id="test_agent")
        for i in range(5):
            chain.add_step(description=f"Step {i + 1}", confidence=0.9)

        assert chain.is_complete(DecisionSeverity.CRITICAL) is True


class TestAlternative:
    """Tests for Alternative dataclass."""

    def test_create_alternative(self):
        """Test creating an alternative."""
        alt = Alternative(
            alternative_id="alt_001",
            description="Option A",
            confidence=0.8,
            pros=["Pro 1", "Pro 2"],
            cons=["Con 1"],
            was_chosen=True,
            rejection_reason=None,
        )
        assert alt.alternative_id == "alt_001"
        assert alt.was_chosen is True
        assert alt.rejection_reason is None

    def test_rejected_alternative(self):
        """Test creating a rejected alternative."""
        alt = Alternative(
            alternative_id="alt_002",
            description="Option B",
            confidence=0.6,
            pros=["Pro 1"],
            cons=["Con 1", "Con 2"],
            was_chosen=False,
            rejection_reason="Higher risk",
        )
        assert alt.was_chosen is False
        assert alt.rejection_reason == "Higher risk"


class TestAlternativesReport:
    """Tests for AlternativesReport dataclass."""

    def test_create_report(self):
        """Test creating an alternatives report."""
        report = AlternativesReport(
            decision_id="dec_001",
            comparison_criteria=["Security", "Performance"],
        )
        assert report.decision_id == "dec_001"
        assert len(report.comparison_criteria) == 2
        assert report.alternatives == []

    def test_add_alternative(self):
        """Test adding an alternative to the report."""
        report = AlternativesReport(
            decision_id="dec_001",
            comparison_criteria=["Security"],
        )
        report.add_alternative(
            alternative_id="alt_001",
            description="Option A",
            confidence=0.8,
            pros=["Secure"],
            cons=["Complex"],
            was_chosen=True,
        )
        assert len(report.alternatives) == 1
        assert report.alternatives[0].alternative_id == "alt_001"

    def test_get_chosen(self):
        """Test getting the chosen alternative."""
        report = AlternativesReport(decision_id="dec_001")
        report.add_alternative(
            alternative_id="alt_001",
            description="Option A",
            confidence=0.6,
            was_chosen=False,
        )
        report.add_alternative(
            alternative_id="alt_002",
            description="Option B",
            confidence=0.8,
            was_chosen=True,
        )

        chosen = report.get_chosen()
        assert chosen is not None
        assert chosen.alternative_id == "alt_002"

    def test_get_chosen_none(self):
        """Test getting chosen when none is chosen."""
        report = AlternativesReport(decision_id="dec_001")
        report.add_alternative(
            alternative_id="alt_001",
            description="Option A",
            confidence=0.6,
            was_chosen=False,
        )

        chosen = report.get_chosen()
        assert chosen is None

    def test_is_complete(self):
        """Test checking if alternatives meet requirements."""
        report = AlternativesReport(decision_id="dec_001")
        assert report.is_complete(DecisionSeverity.TRIVIAL) is False

        report.add_alternative(
            alternative_id="alt_001",
            description="A",
            confidence=0.8,
            was_chosen=True,
        )
        report.add_alternative(
            alternative_id="alt_002",
            description="B",
            confidence=0.6,
            was_chosen=False,
        )

        assert report.is_complete(DecisionSeverity.TRIVIAL) is True
        assert report.is_complete(DecisionSeverity.NORMAL) is True
        assert report.is_complete(DecisionSeverity.SIGNIFICANT) is False


class TestConfidenceInterval:
    """Tests for ConfidenceInterval dataclass."""

    def test_create_confidence_interval(self):
        """Test creating a confidence interval."""
        ci = ConfidenceInterval(
            point_estimate=0.85,
            lower_bound=0.75,
            upper_bound=0.92,
            uncertainty_sources=["Limited data"],
        )
        assert ci.point_estimate == 0.85
        assert ci.lower_bound == 0.75
        assert ci.upper_bound == 0.92

    def test_interval_width(self):
        """Test interval width calculation."""
        ci = ConfidenceInterval(
            point_estimate=0.85,
            lower_bound=0.75,
            upper_bound=0.95,
        )
        assert abs(ci.interval_width() - 0.2) < 0.001

    def test_is_well_calibrated(self):
        """Test well-calibrated check."""
        # Well-calibrated: expected_width = 2 * (1 - 0.85) = 0.3
        # Actual width should be between 0.15 and 0.6
        ci1 = ConfidenceInterval(
            point_estimate=0.85,
            lower_bound=0.70,
            upper_bound=0.95,  # width = 0.25, within [0.15, 0.6]
        )
        assert ci1.is_well_calibrated() is True

        # Poorly calibrated: width too large for this high confidence
        # expected_width = 2 * (1 - 0.95) = 0.10
        # Range for well-calibrated is [0.05, 0.20]
        # Actual width = 0.49, which is > 0.20 (2 * expected_width)
        ci2 = ConfidenceInterval(
            point_estimate=0.95,
            lower_bound=0.50,
            upper_bound=0.99,  # width = 0.49, way outside [0.05, 0.20]
        )
        assert ci2.is_well_calibrated() is False


class TestContradiction:
    """Tests for Contradiction dataclass."""

    def test_create_contradiction(self):
        """Test creating a contradiction."""
        c = Contradiction(
            contradiction_id="ctr_001",
            severity=ContradictionSeverity.MAJOR,
            stated_claim="Fixed all bugs",
            actual_action="Fixed one bug",
            explanation="Scope mismatch",
            evidence=["Claim: 5 bugs", "Fixed: 1 bug"],
            requires_hitl=True,  # Explicitly set for MAJOR severity
        )
        assert c.contradiction_id == "ctr_001"
        assert c.severity == ContradictionSeverity.MAJOR
        assert c.requires_hitl is True

    def test_requires_hitl_via_consistency_report(self):
        """Test HITL requirement is set when adding via ConsistencyReport."""
        report = ConsistencyReport(decision_id="dec_001", is_consistent=True)

        # Add minor contradiction - should not require HITL
        report.add_contradiction(
            contradiction_id="ctr_001",
            severity=ContradictionSeverity.MINOR,
            stated_claim="Test",
            actual_action="Test",
            explanation="Minor issue",
        )
        assert report.contradictions[0].requires_hitl is False

        # Add critical contradiction - should require HITL
        report.add_contradiction(
            contradiction_id="ctr_002",
            severity=ContradictionSeverity.CRITICAL,
            stated_claim="Test",
            actual_action="Test",
            explanation="Critical issue",
        )
        assert report.contradictions[1].requires_hitl is True


class TestConsistencyReport:
    """Tests for ConsistencyReport dataclass."""

    def test_create_consistent_report(self):
        """Test creating a consistent report."""
        report = ConsistencyReport(
            decision_id="dec_001",
            is_consistent=True,
        )
        assert report.is_consistent is True
        assert report.contradictions == []

    def test_add_contradiction(self):
        """Test adding a contradiction."""
        report = ConsistencyReport(decision_id="dec_001", is_consistent=True)
        report.add_contradiction(
            contradiction_id="ctr_001",
            severity=ContradictionSeverity.MODERATE,
            stated_claim="Claim",
            actual_action="Action",
            explanation="Mismatch",
        )

        assert report.is_consistent is False
        assert len(report.contradictions) == 1


class TestClaimVerification:
    """Tests for ClaimVerification dataclass."""

    def test_create_verified_claim(self):
        """Test creating a verified claim."""
        cv = ClaimVerification(
            claim_id="clm_001",
            upstream_agent_id="agent_a",
            claim_text="Found vulnerability",
            claim_type="security_assessment",
            is_verified=True,
            verification_evidence=["CVE confirmed"],
            confidence=0.95,
        )
        assert cv.is_verified is True
        assert cv.confidence == 0.95
        assert cv.discrepancy is None

    def test_create_unverified_claim(self):
        """Test creating an unverified claim."""
        cv = ClaimVerification(
            claim_id="clm_002",
            upstream_agent_id="agent_b",
            claim_text="All tests pass",
            claim_type="test_result",
            is_verified=False,
            verification_evidence=[],
            confidence=0.3,
            discrepancy="No test execution evidence found",
        )
        assert cv.is_verified is False
        assert cv.discrepancy is not None


class TestVerificationReport:
    """Tests for VerificationReport dataclass."""

    def test_create_verification_report(self):
        """Test creating a verification report."""
        report = VerificationReport(decision_id="dec_001")
        assert report.decision_id == "dec_001"
        assert report.verifications == []
        assert report.verification_failures == 0
        assert report.trust_adjustment == 0.0

    def test_overall_trust_score(self):
        """Test overall trust score calculation."""
        report = VerificationReport(decision_id="dec_001")
        report.verifications.append(
            ClaimVerification(
                claim_id="clm_001",
                upstream_agent_id="agent_a",
                claim_text="Test",
                claim_type="test",
                is_verified=True,
                confidence=0.9,
            )
        )
        report.verifications.append(
            ClaimVerification(
                claim_id="clm_002",
                upstream_agent_id="agent_b",
                claim_text="Test 2",
                claim_type="test",
                is_verified=True,
                confidence=0.8,
            )
        )

        # Overall trust score is ratio of verified claims
        # Both are verified, so score = 2/2 = 1.0
        assert report.overall_trust_score() == 1.0


class TestExplainabilityScore:
    """Tests for ExplainabilityScore dataclass."""

    def test_create_score(self):
        """Test creating an explainability score."""
        score = ExplainabilityScore(
            reasoning_completeness=0.9,
            alternatives_coverage=0.8,
            confidence_calibration=0.85,
            consistency_score=1.0,
            inter_agent_trust=0.9,
        )
        assert score.reasoning_completeness == 0.9

    def test_overall_score(self):
        """Test overall score calculation."""
        score = ExplainabilityScore(
            reasoning_completeness=1.0,
            alternatives_coverage=1.0,
            confidence_calibration=1.0,
            consistency_score=1.0,
            inter_agent_trust=1.0,
        )
        # All perfect scores should give 1.0
        assert abs(score.overall_score() - 1.0) < 0.001

    def test_weighted_overall_score(self):
        """Test weighted overall score calculation."""
        score = ExplainabilityScore(
            reasoning_completeness=0.8,  # weight: 0.25
            alternatives_coverage=0.7,  # weight: 0.20
            confidence_calibration=0.9,  # weight: 0.15
            consistency_score=0.85,  # weight: 0.25
            inter_agent_trust=0.95,  # weight: 0.15
        )
        # Weighted calculation
        expected = 0.8 * 0.25 + 0.7 * 0.20 + 0.9 * 0.15 + 0.85 * 0.25 + 0.95 * 0.15
        assert abs(score.overall_score() - expected) < 0.001


class TestExplainabilityRecord:
    """Tests for ExplainabilityRecord dataclass."""

    def test_create_record(self, sample_reasoning_chain):
        """Test creating an explainability record."""
        record = ExplainabilityRecord(
            record_id="rec_001",
            decision_id="dec_001",
            agent_id="test_agent",
            severity=DecisionSeverity.NORMAL,
            reasoning_chain=sample_reasoning_chain,
        )
        assert record.record_id == "rec_001"
        assert record.severity == DecisionSeverity.NORMAL
        assert record.hitl_required is False

    def test_record_with_hitl_required(self, sample_reasoning_chain):
        """Test record with HITL required."""
        record = ExplainabilityRecord(
            record_id="rec_002",
            decision_id="dec_002",
            agent_id="test_agent",
            severity=DecisionSeverity.CRITICAL,
            reasoning_chain=sample_reasoning_chain,
            hitl_required=True,
            hitl_reason="Low confidence score",
        )
        assert record.hitl_required is True
        assert record.hitl_reason is not None

    def test_record_to_dict(self, sample_explainability_record):
        """Test converting record to dictionary."""
        record_dict = asdict(sample_explainability_record)
        assert "record_id" in record_dict
        assert "reasoning_chain" in record_dict
        assert "explainability_score" in record_dict
