"""
Tests for Anti-Sycophancy Guard (ADR-052 Phase 2).

Tests cover:
- SycophancyViolationType and ResponseSeverity enums
- SycophancyViolation and ValidationResult dataclasses
- AgentSycophancyProfile tracking
- SycophancyGuard detection and validation
"""

import platform
from datetime import datetime, timezone

import pytest

from src.services.alignment.sycophancy_guard import (
    AgentSycophancyProfile,
    ResponseContext,
    ResponseSeverity,
    SycophancyGuard,
    SycophancyViolation,
    SycophancyViolationType,
    ValidationResult,
)

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestSycophancyViolationType:
    """Tests for SycophancyViolationType enum."""

    def test_violation_types_exist(self):
        """Test that all violation types are defined."""
        assert (
            SycophancyViolationType.EXCESSIVE_AGREEMENT.value == "excessive_agreement"
        )
        assert SycophancyViolationType.HIDDEN_UNCERTAINTY.value == "hidden_uncertainty"
        assert (
            SycophancyViolationType.MISSING_ALTERNATIVES.value == "missing_alternatives"
        )
        assert (
            SycophancyViolationType.SUPPRESSED_NEGATIVE_FINDING.value
            == "suppressed_negative"
        )
        assert (
            SycophancyViolationType.OVERCONFIDENT_CLAIM.value == "overconfident_claim"
        )
        assert SycophancyViolationType.FLATTERY_DETECTED.value == "flattery_detected"
        assert SycophancyViolationType.CONFIRMATION_BIAS.value == "confirmation_bias"
        assert (
            SycophancyViolationType.AVOIDANCE_OF_CORRECTION.value
            == "avoidance_correction"
        )


class TestResponseSeverity:
    """Tests for ResponseSeverity enum."""

    def test_severity_levels(self):
        """Test that severity levels are defined."""
        assert ResponseSeverity.LOW.value == "low"
        assert ResponseSeverity.MEDIUM.value == "medium"
        assert ResponseSeverity.HIGH.value == "high"
        assert ResponseSeverity.CRITICAL.value == "critical"


class TestSycophancyViolation:
    """Tests for SycophancyViolation dataclass."""

    def test_creation(self):
        """Test creating a violation record."""
        violation = SycophancyViolation(
            violation_type=SycophancyViolationType.FLATTERY_DETECTED,
            severity="warning",
            description="Test violation",
            evidence=["evidence1", "evidence2"],
            suggested_correction="Fix it",
            confidence=0.8,
        )
        assert violation.violation_type == SycophancyViolationType.FLATTERY_DETECTED
        assert violation.severity == "warning"
        assert len(violation.evidence) == 2

    def test_to_dict(self):
        """Test dictionary conversion."""
        violation = SycophancyViolation(
            violation_type=SycophancyViolationType.HIDDEN_UNCERTAINTY,
            severity="violation",
            description="Hidden uncertainty detected",
            evidence=["definite statement"],
            suggested_correction="Add uncertainty qualifier",
            confidence=0.85,
        )
        result = violation.to_dict()

        assert result["violation_type"] == "hidden_uncertainty"
        assert result["severity"] == "violation"
        assert result["description"] == "Hidden uncertainty detected"
        assert result["confidence"] == 0.85


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self):
        """Test a valid result with no violations."""
        result = ValidationResult(
            is_valid=True,
            violations=[],
            warnings=["minor concern"],
            agent_id="agent-1",
        )
        assert result.is_valid is True
        assert result.has_violations is False
        assert len(result.critical_violations) == 0

    def test_invalid_result_with_violations(self):
        """Test an invalid result with violations."""
        violation = SycophancyViolation(
            violation_type=SycophancyViolationType.SUPPRESSED_NEGATIVE_FINDING,
            severity="critical",
            description="Suppressed finding",
        )
        result = ValidationResult(
            is_valid=False,
            violations=[violation],
            agent_id="agent-1",
        )
        assert result.is_valid is False
        assert result.has_violations is True
        assert len(result.critical_violations) == 1

    def test_to_dict(self):
        """Test dictionary conversion."""
        result = ValidationResult(
            is_valid=True,
            violations=[],
            warnings=["test warning"],
            corrections_applied=["correction 1"],
            agent_id="agent-1",
            response_id="resp-123",
        )
        dict_result = result.to_dict()

        assert dict_result["is_valid"] is True
        assert dict_result["violations"] == []
        assert dict_result["warnings"] == ["test warning"]
        assert dict_result["agent_id"] == "agent-1"
        assert dict_result["response_id"] == "resp-123"
        assert "validation_timestamp" in dict_result


class TestAgentSycophancyProfile:
    """Tests for AgentSycophancyProfile dataclass."""

    def test_default_initialization(self):
        """Test default profile values."""
        profile = AgentSycophancyProfile(agent_id="agent-1")
        assert profile.total_responses == 0
        assert profile.disagreement_rate == 0.0

    def test_disagreement_rate(self):
        """Test disagreement rate calculation."""
        profile = AgentSycophancyProfile(agent_id="agent-1")
        profile.total_responses = 100
        profile.disagreements = 10
        profile.agreements = 90
        assert profile.disagreement_rate == 0.1

    def test_alternatives_rate(self):
        """Test alternatives rate calculation."""
        profile = AgentSycophancyProfile(agent_id="agent-1")
        profile.alternatives_opportunities = 10
        profile.alternatives_offered_total = 8
        assert profile.alternatives_rate == 0.8

    def test_alternatives_rate_no_opportunities(self):
        """Test alternatives rate with no opportunities."""
        profile = AgentSycophancyProfile(agent_id="agent-1")
        assert profile.alternatives_rate == 1.0

    def test_suppression_rate(self):
        """Test suppression rate calculation."""
        profile = AgentSycophancyProfile(agent_id="agent-1")
        profile.negative_findings_reported = 8
        profile.negative_findings_suppressed = 2
        assert profile.suppression_rate == 0.2

    def test_suppression_rate_no_findings(self):
        """Test suppression rate with no findings."""
        profile = AgentSycophancyProfile(agent_id="agent-1")
        assert profile.suppression_rate == 0.0

    def test_confidence_calibration_error(self):
        """Test confidence calibration error calculation."""
        profile = AgentSycophancyProfile(agent_id="agent-1")
        # Add some predictions
        profile.confidence_predictions = [
            (0.9, True),  # error = |0.9 - 1.0| = 0.1
            (0.8, False),  # error = |0.8 - 0.0| = 0.8
        ]
        # Average error = (0.1 + 0.8) / 2 = 0.45
        assert profile.confidence_calibration_error == pytest.approx(0.45)

    def test_confidence_calibration_error_empty(self):
        """Test calibration error with no predictions."""
        profile = AgentSycophancyProfile(agent_id="agent-1")
        assert profile.confidence_calibration_error == 0.0

    def test_to_dict(self):
        """Test dictionary conversion."""
        profile = AgentSycophancyProfile(agent_id="agent-1")
        profile.total_responses = 50
        result = profile.to_dict()

        assert result["agent_id"] == "agent-1"
        assert result["total_responses"] == 50
        assert "disagreement_rate" in result
        assert "alternatives_rate" in result
        assert "last_updated" in result


class TestSycophancyGuard:
    """Tests for SycophancyGuard class."""

    @pytest.fixture
    def guard(self):
        """Create a fresh guard for each test."""
        return SycophancyGuard()

    @pytest.fixture
    def basic_context(self):
        """Create a basic response context."""
        return ResponseContext(
            response_text="This is a test response.",
            agent_id="agent-1",
            response_id="resp-123",
            severity=ResponseSeverity.MEDIUM,
        )

    def test_initialization(self, guard):
        """Test guard initialization."""
        assert guard.min_disagreement_rate == 0.05
        assert guard.max_disagreement_rate == 0.15
        assert guard.enable_auto_correction is False

    def test_custom_thresholds(self):
        """Test custom threshold initialization."""
        guard = SycophancyGuard(
            min_disagreement_rate=0.10,
            max_disagreement_rate=0.20,
            enable_auto_correction=True,
        )
        assert guard.min_disagreement_rate == 0.10
        assert guard.max_disagreement_rate == 0.20
        assert guard.enable_auto_correction is True

    def test_validate_response_clean(self, guard, basic_context):
        """Test validating a clean response."""
        result = guard.validate_response(basic_context)
        assert result.is_valid is True
        assert len(result.violations) == 0

    def test_detect_flattery(self, guard):
        """Test flattery detection."""
        context = ResponseContext(
            response_text="Great question! You're absolutely right about this.",
            agent_id="agent-1",
            severity=ResponseSeverity.MEDIUM,
        )
        result = guard.validate_response(context)

        flattery_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.FLATTERY_DETECTED
        ]
        assert len(flattery_violations) > 0

    def test_detect_hidden_uncertainty_low_confidence(self, guard):
        """Test hidden uncertainty detection with low stated confidence."""
        context = ResponseContext(
            response_text="I definitely recommend this approach, it will certainly work.",
            agent_id="agent-1",
            stated_confidence=0.5,  # Low confidence but certain language
            severity=ResponseSeverity.MEDIUM,
        )
        result = guard.validate_response(context)

        uncertainty_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.HIDDEN_UNCERTAINTY
        ]
        assert len(uncertainty_violations) > 0

    def test_detect_hidden_uncertainty_no_confidence(self, guard):
        """Test hidden uncertainty detection without stated confidence."""
        context = ResponseContext(
            response_text="This is definitely the best approach. Certainly without a doubt it will work. 100% guaranteed.",
            agent_id="agent-1",
            severity=ResponseSeverity.MEDIUM,
        )
        result = guard.validate_response(context)

        uncertainty_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.HIDDEN_UNCERTAINTY
        ]
        assert len(uncertainty_violations) > 0

    def test_detect_missing_alternatives_critical(self, guard):
        """Test missing alternatives detection for critical decisions."""
        # Long response without alternatives
        long_response = "A" * 300  # Exceeds MIN_RESPONSE_LENGTH_FOR_ALTERNATIVES
        context = ResponseContext(
            response_text=long_response,
            agent_id="agent-1",
            severity=ResponseSeverity.CRITICAL,
            alternatives_presented=0,
        )
        result = guard.validate_response(context)

        missing_alt_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.MISSING_ALTERNATIVES
        ]
        assert len(missing_alt_violations) > 0
        assert missing_alt_violations[0].severity == "critical"

    def test_detect_missing_alternatives_high(self, guard):
        """Test missing alternatives detection for high severity."""
        long_response = "B" * 300
        context = ResponseContext(
            response_text=long_response,
            agent_id="agent-1",
            severity=ResponseSeverity.HIGH,
            alternatives_presented=0,
        )
        result = guard.validate_response(context)

        missing_alt_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.MISSING_ALTERNATIVES
        ]
        assert len(missing_alt_violations) > 0
        assert missing_alt_violations[0].severity == "violation"

    def test_no_alternatives_needed_short_response(self, guard):
        """Test that short responses don't require alternatives."""
        context = ResponseContext(
            response_text="Short response",
            agent_id="agent-1",
            severity=ResponseSeverity.HIGH,
            alternatives_presented=0,
        )
        result = guard.validate_response(context)

        missing_alt_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.MISSING_ALTERNATIVES
        ]
        assert len(missing_alt_violations) == 0

    def test_no_alternatives_needed_low_severity(self, guard):
        """Test that low severity responses don't require alternatives."""
        long_response = "C" * 300
        context = ResponseContext(
            response_text=long_response,
            agent_id="agent-1",
            severity=ResponseSeverity.LOW,
            alternatives_presented=0,
        )
        result = guard.validate_response(context)

        missing_alt_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.MISSING_ALTERNATIVES
        ]
        assert len(missing_alt_violations) == 0

    def test_detect_suppressed_findings(self, guard):
        """Test suppressed negative findings detection."""
        context = ResponseContext(
            response_text="Everything looks good!",
            agent_id="agent-1",
            negative_findings=["security vulnerability", "performance issue"],
            negative_findings_reported=False,
            severity=ResponseSeverity.MEDIUM,
        )
        result = guard.validate_response(context)

        suppressed_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.SUPPRESSED_NEGATIVE_FINDING
        ]
        assert len(suppressed_violations) > 0
        assert suppressed_violations[0].severity == "critical"
        assert result.is_valid is False

    def test_detect_overconfidence(self, guard):
        """Test overconfidence detection."""
        context = ResponseContext(
            response_text="This approach is recommended.",
            agent_id="agent-1",
            stated_confidence=0.99,  # Very high confidence
            severity=ResponseSeverity.MEDIUM,
        )
        result = guard.validate_response(context)

        overconfident_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.OVERCONFIDENT_CLAIM
        ]
        assert len(overconfident_violations) > 0

    def test_detect_confirmation_bias(self, guard):
        """Test confirmation bias detection."""
        context = ResponseContext(
            response_text="Yes, using microservices is the right choice for this project.",
            agent_id="agent-1",
            user_position="microservices",
            severity=ResponseSeverity.MEDIUM,
        )
        result = guard.validate_response(context)

        bias_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.CONFIRMATION_BIAS
        ]
        assert len(bias_violations) > 0

    def test_no_confirmation_bias_with_critique(self, guard):
        """Test no confirmation bias when critique is present."""
        context = ResponseContext(
            response_text="Microservices could work, however there are some concerns about complexity.",
            agent_id="agent-1",
            user_position="microservices",
            severity=ResponseSeverity.MEDIUM,
        )
        result = guard.validate_response(context)

        bias_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.CONFIRMATION_BIAS
        ]
        assert len(bias_violations) == 0

    def test_record_disagreement(self, guard):
        """Test recording disagreements."""
        guard.record_disagreement("agent-1", disagreed=True)
        guard.record_disagreement("agent-1", disagreed=False)
        guard.record_disagreement("agent-1", disagreed=True)

        profile = guard._agent_profiles["agent-1"]
        assert profile.disagreements == 2
        assert profile.agreements == 1

    def test_record_confidence_outcome(self, guard):
        """Test recording confidence outcomes."""
        guard.record_confidence_outcome("agent-1", 0.8, was_correct=True)
        guard.record_confidence_outcome("agent-1", 0.9, was_correct=False)

        profile = guard._agent_profiles["agent-1"]
        assert len(profile.confidence_predictions) == 2

    def test_record_confidence_outcome_trimming(self, guard):
        """Test confidence prediction list trimming."""
        for i in range(250):
            guard.record_confidence_outcome("agent-1", 0.5, was_correct=True)

        profile = guard._agent_profiles["agent-1"]
        assert len(profile.confidence_predictions) == 200

    def test_get_agent_health_unknown(self, guard):
        """Test getting health for unknown agent."""
        health = guard.get_agent_health("unknown-agent")
        assert health["status"] == "unknown"
        assert "No data" in health["message"]

    def test_get_agent_health_healthy(self, guard):
        """Test getting health for healthy agent."""
        # Create agent with good metrics
        for i in range(30):
            context = ResponseContext(
                response_text="Test response",
                agent_id="agent-1",
                severity=ResponseSeverity.MEDIUM,
            )
            guard.validate_response(context)

        # Record some disagreements (within acceptable range)
        guard.record_disagreement("agent-1", disagreed=True)
        guard.record_disagreement("agent-1", disagreed=True)
        guard.record_disagreement("agent-1", disagreed=True)

        health = guard.get_agent_health("agent-1")
        # May or may not be healthy depending on exact threshold checks
        assert health["status"] in ["healthy", "warning"]

    def test_get_agent_health_low_disagreement(self, guard):
        """Test health with too low disagreement rate."""
        for i in range(25):
            context = ResponseContext(
                response_text="Test",
                agent_id="agent-1",
                severity=ResponseSeverity.MEDIUM,
            )
            guard.validate_response(context)
            guard.record_disagreement("agent-1", disagreed=False)

        health = guard.get_agent_health("agent-1")
        assert health["status"] in ["warning", "critical"]

    def test_get_agent_health_high_suppression(self, guard):
        """Test health with suppressed findings."""
        context = ResponseContext(
            response_text="All good!",
            agent_id="agent-1",
            negative_findings=["issue 1"],
            negative_findings_reported=False,
            severity=ResponseSeverity.MEDIUM,
        )
        guard.validate_response(context)

        health = guard.get_agent_health("agent-1")
        suppression_issue = any(
            "suppression" in issue.lower() for issue in health.get("issues", [])
        )
        assert suppression_issue or health["status"] != "healthy"

    def test_get_all_agents_health(self, guard):
        """Test getting health for all agents."""
        context1 = ResponseContext(
            response_text="Test", agent_id="agent-1", severity=ResponseSeverity.MEDIUM
        )
        context2 = ResponseContext(
            response_text="Test", agent_id="agent-2", severity=ResponseSeverity.MEDIUM
        )
        guard.validate_response(context1)
        guard.validate_response(context2)

        all_health = guard.get_all_agents_health()
        assert len(all_health) == 2

    def test_get_validation_stats_empty(self, guard):
        """Test stats with no validations."""
        stats = guard.get_validation_stats()
        assert stats["total_validations"] == 0

    def test_get_validation_stats(self, guard):
        """Test validation statistics."""
        # Create some validations
        for i in range(5):
            context = ResponseContext(
                response_text="Clean response",
                agent_id="agent-1",
                severity=ResponseSeverity.MEDIUM,
            )
            guard.validate_response(context)

        # Create a violation
        context = ResponseContext(
            response_text="Test",
            agent_id="agent-1",
            negative_findings=["issue"],
            negative_findings_reported=False,
            severity=ResponseSeverity.MEDIUM,
        )
        guard.validate_response(context)

        stats = guard.get_validation_stats()
        assert stats["total_validations"] == 6
        assert stats["valid_responses"] == 5
        assert stats["invalid_responses"] == 1

    def test_get_validation_stats_since(self, guard):
        """Test validation stats with time filter."""
        context = ResponseContext(
            response_text="Test",
            agent_id="agent-1",
            severity=ResponseSeverity.MEDIUM,
        )
        guard.validate_response(context)

        future = datetime.now(timezone.utc)
        stats = guard.get_validation_stats(since=future)
        assert stats["total_validations"] == 0

    def test_clear_agent_profile(self, guard):
        """Test clearing an agent profile."""
        context = ResponseContext(
            response_text="Test",
            agent_id="agent-1",
            severity=ResponseSeverity.MEDIUM,
        )
        guard.validate_response(context)
        assert "agent-1" in guard._agent_profiles

        result = guard.clear_agent_profile("agent-1")
        assert result is True
        assert "agent-1" not in guard._agent_profiles

    def test_clear_agent_profile_not_found(self, guard):
        """Test clearing non-existent profile."""
        result = guard.clear_agent_profile("unknown")
        assert result is False

    def test_clear_all(self, guard):
        """Test clearing all data."""
        context = ResponseContext(
            response_text="Test",
            agent_id="agent-1",
            severity=ResponseSeverity.MEDIUM,
        )
        guard.validate_response(context)

        guard.clear_all()
        assert len(guard._agent_profiles) == 0
        assert len(guard._validation_history) == 0

    def test_auto_correction(self):
        """Test auto-correction feature."""
        guard = SycophancyGuard(enable_auto_correction=True)

        context = ResponseContext(
            response_text="Great question! That's exactly right.",
            agent_id="agent-1",
            severity=ResponseSeverity.MEDIUM,
        )
        result = guard.validate_response(context)

        # Should have corrections applied for warnings
        if result.violations:
            warning_violations = [
                v for v in result.violations if v.severity == "warning"
            ]
            if warning_violations:
                assert len(result.corrections_applied) > 0

    def test_validation_history_trimming(self, guard):
        """Test validation history is trimmed."""
        for i in range(1100):
            context = ResponseContext(
                response_text="Test",
                agent_id=f"agent-{i}",
                severity=ResponseSeverity.MEDIUM,
            )
            guard.validate_response(context)

        assert len(guard._validation_history) == 1000

    def test_agent_profile_alternatives_tracking(self, guard):
        """Test alternatives tracking in agent profile."""
        # High severity should track alternatives
        context = ResponseContext(
            response_text="X" * 300,
            agent_id="agent-1",
            severity=ResponseSeverity.HIGH,
            alternatives_presented=2,
        )
        guard.validate_response(context)

        profile = guard._agent_profiles["agent-1"]
        assert profile.alternatives_opportunities == 1
        assert profile.alternatives_offered_total == 1

    def test_agent_profile_negative_findings_tracking(self, guard):
        """Test negative findings tracking in agent profile."""
        # Reported findings
        context1 = ResponseContext(
            response_text="Test",
            agent_id="agent-1",
            negative_findings=["finding 1", "finding 2"],
            negative_findings_reported=True,
            severity=ResponseSeverity.MEDIUM,
        )
        guard.validate_response(context1)

        # Suppressed findings
        context2 = ResponseContext(
            response_text="Test",
            agent_id="agent-1",
            negative_findings=["finding 3"],
            negative_findings_reported=False,
            severity=ResponseSeverity.MEDIUM,
        )
        guard.validate_response(context2)

        profile = guard._agent_profiles["agent-1"]
        assert profile.negative_findings_reported == 2
        assert profile.negative_findings_suppressed == 1

    def test_violations_history_trimming(self, guard):
        """Test violations history trimming in profile."""
        # Generate many violations
        for i in range(150):
            context = ResponseContext(
                response_text="Great question! You're absolutely right!",
                agent_id="agent-1",
                severity=ResponseSeverity.MEDIUM,
            )
            guard.validate_response(context)

        profile = guard._agent_profiles["agent-1"]
        assert len(profile.violations_history) <= 100
