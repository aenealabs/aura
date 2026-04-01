"""Tests for Constitutional AI models.

This module tests the data models used by the Constitutional AI system,
including enums, dataclasses, and their serialization/deserialization.
"""

from datetime import datetime

import pytest

from src.services.constitutional_ai.models import (
    ConstitutionalContext,
    ConstitutionalEvaluationSummary,
    ConstitutionalPrinciple,
    CritiqueResult,
    PrincipleCategory,
    PrincipleSeverity,
    RevisionResult,
)

# =============================================================================
# PrincipleSeverity Enum Tests
# =============================================================================


class TestPrincipleSeverity:
    """Tests for PrincipleSeverity enum."""

    def test_severity_values(self):
        """Test that all severity values are correct."""
        assert PrincipleSeverity.CRITICAL.value == "critical"
        assert PrincipleSeverity.HIGH.value == "high"
        assert PrincipleSeverity.MEDIUM.value == "medium"
        assert PrincipleSeverity.LOW.value == "low"

    def test_from_string_valid(self):
        """Test from_string with valid values."""
        assert PrincipleSeverity.from_string("critical") == PrincipleSeverity.CRITICAL
        assert PrincipleSeverity.from_string("high") == PrincipleSeverity.HIGH
        assert PrincipleSeverity.from_string("medium") == PrincipleSeverity.MEDIUM
        assert PrincipleSeverity.from_string("low") == PrincipleSeverity.LOW

    def test_from_string_case_insensitive(self):
        """Test from_string is case insensitive."""
        assert PrincipleSeverity.from_string("CRITICAL") == PrincipleSeverity.CRITICAL
        assert PrincipleSeverity.from_string("High") == PrincipleSeverity.HIGH
        assert PrincipleSeverity.from_string("MEDIUM") == PrincipleSeverity.MEDIUM

    def test_from_string_invalid(self):
        """Test from_string raises ValueError for invalid input."""
        with pytest.raises(ValueError) as exc_info:
            PrincipleSeverity.from_string("invalid")
        assert "Invalid severity" in str(exc_info.value)

    def test_severity_count(self):
        """Test that there are exactly 4 severity levels."""
        assert len(PrincipleSeverity) == 4


# =============================================================================
# PrincipleCategory Enum Tests
# =============================================================================


class TestPrincipleCategory:
    """Tests for PrincipleCategory enum."""

    def test_category_values(self):
        """Test that all category values are correct."""
        assert PrincipleCategory.SAFETY.value == "safety"
        assert PrincipleCategory.COMPLIANCE.value == "compliance"
        assert PrincipleCategory.TRANSPARENCY.value == "transparency"
        assert PrincipleCategory.HELPFULNESS.value == "helpfulness"
        assert PrincipleCategory.ANTI_SYCOPHANCY.value == "anti_sycophancy"
        assert PrincipleCategory.CODE_QUALITY.value == "code_quality"
        assert PrincipleCategory.META.value == "meta"

    def test_from_string_valid(self):
        """Test from_string with valid values."""
        assert PrincipleCategory.from_string("safety") == PrincipleCategory.SAFETY
        assert (
            PrincipleCategory.from_string("compliance") == PrincipleCategory.COMPLIANCE
        )
        assert (
            PrincipleCategory.from_string("anti_sycophancy")
            == PrincipleCategory.ANTI_SYCOPHANCY
        )

    def test_from_string_case_insensitive(self):
        """Test from_string is case insensitive."""
        assert PrincipleCategory.from_string("SAFETY") == PrincipleCategory.SAFETY
        assert (
            PrincipleCategory.from_string("Compliance") == PrincipleCategory.COMPLIANCE
        )

    def test_from_string_invalid(self):
        """Test from_string raises ValueError for invalid input."""
        with pytest.raises(ValueError) as exc_info:
            PrincipleCategory.from_string("invalid")
        assert "Invalid category" in str(exc_info.value)

    def test_category_count(self):
        """Test that there are exactly 7 categories."""
        assert len(PrincipleCategory) == 7


# =============================================================================
# ConstitutionalPrinciple Tests
# =============================================================================


class TestConstitutionalPrinciple:
    """Tests for ConstitutionalPrinciple dataclass."""

    def test_create_principle(self, sample_principle):
        """Test creating a principle."""
        assert sample_principle.id == "test_principle_1"
        assert sample_principle.name == "Test Principle"
        assert sample_principle.severity == PrincipleSeverity.HIGH
        assert sample_principle.category == PrincipleCategory.SAFETY
        assert sample_principle.enabled is True

    def test_principle_with_defaults(self):
        """Test principle with default values."""
        principle = ConstitutionalPrinciple(
            id="test",
            name="Test",
            critique_prompt="Critique",
            revision_prompt="Revision",
            severity=PrincipleSeverity.LOW,
            category=PrincipleCategory.CODE_QUALITY,
        )
        assert principle.domain_tags == []
        assert principle.enabled is True

    def test_principle_validation_empty_id(self):
        """Test that empty id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ConstitutionalPrinciple(
                id="",
                name="Test",
                critique_prompt="Critique",
                revision_prompt="Revision",
                severity=PrincipleSeverity.LOW,
                category=PrincipleCategory.CODE_QUALITY,
            )
        assert "id cannot be empty" in str(exc_info.value)

    def test_principle_validation_empty_name(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ConstitutionalPrinciple(
                id="test",
                name="",
                critique_prompt="Critique",
                revision_prompt="Revision",
                severity=PrincipleSeverity.LOW,
                category=PrincipleCategory.CODE_QUALITY,
            )
        assert "name cannot be empty" in str(exc_info.value)

    def test_principle_validation_empty_critique_prompt(self):
        """Test that empty critique_prompt raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ConstitutionalPrinciple(
                id="test",
                name="Test",
                critique_prompt="",
                revision_prompt="Revision",
                severity=PrincipleSeverity.LOW,
                category=PrincipleCategory.CODE_QUALITY,
            )
        assert "critique_prompt cannot be empty" in str(exc_info.value)

    def test_principle_to_dict(self, sample_principle):
        """Test principle serialization to dict."""
        data = sample_principle.to_dict()
        assert data["id"] == "test_principle_1"
        assert data["name"] == "Test Principle"
        assert data["severity"] == "high"
        assert data["category"] == "safety"
        assert data["domain_tags"] == ["test", "security"]
        assert data["enabled"] is True

    def test_principle_from_dict(self):
        """Test principle deserialization from dict."""
        data = {
            "id": "test_id",
            "name": "Test Name",
            "critique_prompt": "Critique",
            "revision_prompt": "Revision",
            "severity": "critical",
            "category": "compliance",
            "domain_tags": ["tag1", "tag2"],
            "enabled": False,
        }
        principle = ConstitutionalPrinciple.from_dict(data)
        assert principle.id == "test_id"
        assert principle.severity == PrincipleSeverity.CRITICAL
        assert principle.category == PrincipleCategory.COMPLIANCE
        assert principle.enabled is False

    def test_principle_roundtrip(self, sample_principle):
        """Test that to_dict -> from_dict preserves data."""
        data = sample_principle.to_dict()
        restored = ConstitutionalPrinciple.from_dict(data)
        assert restored.id == sample_principle.id
        assert restored.name == sample_principle.name
        assert restored.severity == sample_principle.severity
        assert restored.category == sample_principle.category


# =============================================================================
# CritiqueResult Tests
# =============================================================================


class TestCritiqueResult:
    """Tests for CritiqueResult dataclass."""

    def test_create_critique_result(self, sample_critique_result):
        """Test creating a critique result."""
        assert sample_critique_result.principle_id == "test_principle_1"
        assert sample_critique_result.severity == PrincipleSeverity.HIGH
        assert sample_critique_result.requires_revision is True
        assert len(sample_critique_result.issues_found) == 2

    def test_critique_result_defaults(self):
        """Test critique result with default values."""
        result = CritiqueResult(
            principle_id="test",
            principle_name="Test",
            severity=PrincipleSeverity.LOW,
            issues_found=[],
            reasoning="Test reasoning",
            requires_revision=False,
        )
        assert result.confidence == 0.0
        assert result.metadata == {}
        assert isinstance(result.timestamp, datetime)

    def test_critique_result_is_critical(self, sample_critical_critique_result):
        """Test is_critical property."""
        assert sample_critical_critique_result.is_critical is True

    def test_critique_result_is_critical_false(self, sample_critique_result):
        """Test is_critical is False for non-critical severity."""
        assert sample_critique_result.is_critical is False

    def test_critique_result_has_issues(self, sample_critique_result):
        """Test has_issues property."""
        assert sample_critique_result.has_issues is True

    def test_critique_result_has_issues_false(self, sample_critique_result_no_issues):
        """Test has_issues is False when no issues."""
        assert sample_critique_result_no_issues.has_issues is False

    def test_critique_result_invalid_confidence_high(self):
        """Test that confidence > 1.0 raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            CritiqueResult(
                principle_id="test",
                principle_name="Test",
                severity=PrincipleSeverity.LOW,
                issues_found=[],
                reasoning="Test",
                requires_revision=False,
                confidence=1.5,
            )
        assert "Confidence must be between" in str(exc_info.value)

    def test_critique_result_invalid_confidence_low(self):
        """Test that confidence < 0.0 raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            CritiqueResult(
                principle_id="test",
                principle_name="Test",
                severity=PrincipleSeverity.LOW,
                issues_found=[],
                reasoning="Test",
                requires_revision=False,
                confidence=-0.1,
            )
        assert "Confidence must be between" in str(exc_info.value)

    def test_critique_result_to_dict(self, sample_critique_result):
        """Test critique result serialization to dict."""
        data = sample_critique_result.to_dict()
        assert data["principle_id"] == "test_principle_1"
        assert data["severity"] == "high"
        assert data["requires_revision"] is True
        assert "timestamp" in data

    def test_critique_result_from_dict(self):
        """Test critique result deserialization from dict."""
        data = {
            "principle_id": "test_id",
            "principle_name": "Test Name",
            "severity": "critical",
            "issues_found": ["issue1"],
            "reasoning": "Test reasoning",
            "requires_revision": True,
            "confidence": 0.9,
        }
        result = CritiqueResult.from_dict(data)
        assert result.principle_id == "test_id"
        assert result.severity == PrincipleSeverity.CRITICAL
        assert result.confidence == 0.9


# =============================================================================
# RevisionResult Tests
# =============================================================================


class TestRevisionResult:
    """Tests for RevisionResult dataclass."""

    def test_create_revision_result(self, sample_revision_result):
        """Test creating a revision result."""
        assert (
            sample_revision_result.original_output
            != sample_revision_result.revised_output
        )
        assert sample_revision_result.revision_iterations == 1
        assert sample_revision_result.converged is True

    def test_revision_result_was_modified(self, sample_revision_result):
        """Test was_modified property."""
        assert sample_revision_result.was_modified is True

    def test_revision_result_was_modified_false(self):
        """Test was_modified is False when outputs are same."""
        result = RevisionResult(
            original_output="same content",
            revised_output="same content",
            critiques_addressed=[],
            reasoning_chain="No changes needed",
            revision_iterations=0,
        )
        assert result.was_modified is False

    def test_revision_result_critique_count(self, sample_revision_result):
        """Test critique_count property."""
        assert sample_revision_result.critique_count == 1

    def test_revision_result_invalid_iterations(self):
        """Test that negative iterations raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            RevisionResult(
                original_output="test",
                revised_output="test",
                critiques_addressed=[],
                reasoning_chain="",
                revision_iterations=-1,
            )
        assert "revision_iterations must be non-negative" in str(exc_info.value)

    def test_revision_result_to_dict(self, sample_revision_result):
        """Test revision result serialization to dict."""
        data = sample_revision_result.to_dict()
        assert "original_output" in data
        assert "revised_output" in data
        assert data["converged"] is True

    def test_revision_result_from_dict(self):
        """Test revision result deserialization from dict."""
        data = {
            "original_output": "original",
            "revised_output": "revised",
            "critiques_addressed": ["p1", "p2"],
            "reasoning_chain": "reasoning",
            "revision_iterations": 2,
            "converged": True,
        }
        result = RevisionResult.from_dict(data)
        assert result.original_output == "original"
        assert result.revision_iterations == 2


# =============================================================================
# ConstitutionalContext Tests
# =============================================================================


class TestConstitutionalContext:
    """Tests for ConstitutionalContext dataclass."""

    def test_create_context(self, sample_context):
        """Test creating a context."""
        assert sample_context.agent_name == "TestAgent"
        assert sample_context.operation_type == "code_generation"
        assert "security" in sample_context.domain_tags

    def test_context_defaults(self):
        """Test context with default values."""
        context = ConstitutionalContext(
            agent_name="test",
            operation_type="test_op",
        )
        assert context.user_request is None
        assert context.domain_tags == []
        assert context.metadata == {}

    def test_context_to_dict(self, sample_context):
        """Test context serialization to dict."""
        data = sample_context.to_dict()
        assert data["agent_name"] == "TestAgent"
        assert data["operation_type"] == "code_generation"


# =============================================================================
# ConstitutionalEvaluationSummary Tests
# =============================================================================


class TestConstitutionalEvaluationSummary:
    """Tests for ConstitutionalEvaluationSummary dataclass."""

    def test_from_critiques_empty(self):
        """Test creating summary from empty critiques list."""
        summary = ConstitutionalEvaluationSummary.from_critiques([])
        assert summary.total_principles_evaluated == 0
        assert summary.critical_issues == 0
        assert summary.requires_revision is False
        assert summary.requires_hitl is False

    def test_from_critiques_with_issues(
        self, sample_critique_result, sample_critical_critique_result
    ):
        """Test creating summary from critiques with issues."""
        critiques = [sample_critique_result, sample_critical_critique_result]
        summary = ConstitutionalEvaluationSummary.from_critiques(critiques)

        assert summary.total_principles_evaluated == 2
        assert summary.critical_issues == 1
        assert summary.high_issues == 1
        assert summary.requires_revision is True
        assert summary.requires_hitl is True

    def test_from_critiques_no_critical(self, sample_critique_result):
        """Test summary without critical issues."""
        summary = ConstitutionalEvaluationSummary.from_critiques(
            [sample_critique_result]
        )
        assert summary.critical_issues == 0
        assert summary.requires_hitl is False

    def test_summary_to_dict(self, sample_critique_result):
        """Test summary serialization to dict."""
        summary = ConstitutionalEvaluationSummary.from_critiques(
            [sample_critique_result]
        )
        data = summary.to_dict()

        assert "total_principles_evaluated" in data
        assert "critical_issues" in data
        assert "critiques" in data
        assert len(data["critiques"]) == 1
