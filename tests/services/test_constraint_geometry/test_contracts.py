"""
Project Aura - CGE Contracts Tests

Tests for immutable data types, enums, and serialization.

Author: Project Aura Team
Created: 2026-02-11
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.constraint_geometry.contracts import (
    AgentOutput,
    AxisCoherenceScore,
    CoherenceAction,
    CoherenceResult,
    ConstraintAxis,
    ConstraintEdge,
    ConstraintEdgeType,
    ConstraintRule,
    ProvenanceContext,
    ResolvedConstraintSet,
)

# =============================================================================
# ConstraintAxis Tests
# =============================================================================


class TestConstraintAxis:
    """Test the 7-axis constraint space enum."""

    def test_all_seven_axes_defined(self):
        """All 7 constraint axes must be present."""
        assert len(ConstraintAxis) == 7

    def test_axis_values(self):
        """Axis values must be C1-C7."""
        expected = {"C1", "C2", "C3", "C4", "C5", "C6", "C7"}
        actual = {a.value for a in ConstraintAxis}
        assert actual == expected

    def test_display_names(self):
        """Each axis has a human-readable display name."""
        for axis in ConstraintAxis:
            assert axis.display_name
            assert isinstance(axis.display_name, str)

    def test_security_axis_is_c3(self):
        """Security policy is always C3."""
        assert ConstraintAxis.SECURITY_POLICY.value == "C3"

    def test_provenance_axis_is_c6(self):
        """Provenance trust is always C6."""
        assert ConstraintAxis.PROVENANCE_TRUST.value == "C6"


# =============================================================================
# CoherenceAction Tests
# =============================================================================


class TestCoherenceAction:
    """Test action enum."""

    def test_four_actions_defined(self):
        """Exactly 4 actions must be defined."""
        assert len(CoherenceAction) == 4

    def test_action_values(self):
        """Action values match expected strings."""
        assert CoherenceAction.AUTO_EXECUTE.value == "auto_execute"
        assert CoherenceAction.HUMAN_REVIEW.value == "human_review"
        assert CoherenceAction.ESCALATE.value == "escalate"
        assert CoherenceAction.REJECT.value == "reject"


# =============================================================================
# ConstraintRule Tests
# =============================================================================


class TestConstraintRule:
    """Test immutable constraint rule dataclass."""

    def test_rule_is_frozen(self, rule_c1_syntax):
        """ConstraintRule instances must be immutable."""
        with pytest.raises(AttributeError):
            rule_c1_syntax.name = "Modified"

    def test_rule_fields(self, rule_c1_syntax):
        """Rule has all expected fields."""
        assert rule_c1_syntax.rule_id == "c1-syntax-001"
        assert rule_c1_syntax.axis == ConstraintAxis.SYNTACTIC_VALIDITY
        assert rule_c1_syntax.name == "AST Parse Check"
        assert len(rule_c1_syntax.positive_centroid) > 0
        assert len(rule_c1_syntax.negative_centroid) > 0
        assert rule_c1_syntax.boundary_threshold == 0.5

    def test_rule_is_active_no_dates(self, rule_c1_syntax):
        """Rule without dates is always active."""
        assert rule_c1_syntax.is_active

    def test_rule_is_active_with_future_effective(self):
        """Rule with future effective_at is not active."""
        rule = ConstraintRule(
            rule_id="future-rule",
            axis=ConstraintAxis.SYNTACTIC_VALIDITY,
            name="Future Rule",
            description="Not yet active",
            positive_centroid=(1.0,),
            negative_centroid=(0.0,),
            boundary_threshold=0.5,
            effective_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        assert not rule.is_active

    def test_rule_is_active_with_past_expiry(self):
        """Rule with past expires_at is not active."""
        rule = ConstraintRule(
            rule_id="expired-rule",
            axis=ConstraintAxis.SYNTACTIC_VALIDITY,
            name="Expired Rule",
            description="Already expired",
            positive_centroid=(1.0,),
            negative_centroid=(0.0,),
            boundary_threshold=0.5,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert not rule.is_active

    def test_rule_metadata_dict(self):
        """Frozen metadata tuple converts to dict."""
        rule = ConstraintRule(
            rule_id="meta-rule",
            axis=ConstraintAxis.SECURITY_POLICY,
            name="Metadata Rule",
            description="Has metadata",
            positive_centroid=(1.0,),
            negative_centroid=(0.0,),
            boundary_threshold=0.5,
            metadata=(("source", "NIST"), ("revision", "5")),
        )
        assert rule.metadata_dict == {"source": "NIST", "revision": "5"}


# =============================================================================
# ConstraintEdge Tests
# =============================================================================


class TestConstraintEdge:
    """Test constraint graph edge dataclass."""

    def test_edge_is_frozen(self):
        """ConstraintEdge instances must be immutable."""
        edge = ConstraintEdge(
            source_id="rule-a",
            target_id="rule-b",
            edge_type=ConstraintEdgeType.TIGHTENS,
        )
        with pytest.raises(AttributeError):
            edge.weight = 2.0

    def test_edge_types(self):
        """All 6 edge types must be defined."""
        assert len(ConstraintEdgeType) == 6


# =============================================================================
# ResolvedConstraintSet Tests
# =============================================================================


class TestResolvedConstraintSet:
    """Test resolved constraint set."""

    def test_get_axis_rules(self, rule_c1_syntax, rule_c3_nist_ac6):
        """Can retrieve rules for a specific axis."""
        rcs = ResolvedConstraintSet(
            rules_by_axis=(
                (ConstraintAxis.SYNTACTIC_VALIDITY, (rule_c1_syntax,)),
                (ConstraintAxis.SECURITY_POLICY, (rule_c3_nist_ac6,)),
            ),
            version="1.0.0",
            profile_name="default",
        )
        c1_rules = rcs.get_axis_rules(ConstraintAxis.SYNTACTIC_VALIDITY)
        assert len(c1_rules) == 1
        assert c1_rules[0].rule_id == "c1-syntax-001"

    def test_get_missing_axis_returns_empty(self, rule_c1_syntax):
        """Missing axis returns empty tuple."""
        rcs = ResolvedConstraintSet(
            rules_by_axis=((ConstraintAxis.SYNTACTIC_VALIDITY, (rule_c1_syntax,)),),
            version="1.0.0",
            profile_name="default",
        )
        assert rcs.get_axis_rules(ConstraintAxis.SECURITY_POLICY) == ()

    def test_total_rules(self, rule_c1_syntax, rule_c3_nist_ac6):
        """Total rules counts across all axes."""
        rcs = ResolvedConstraintSet(
            rules_by_axis=(
                (ConstraintAxis.SYNTACTIC_VALIDITY, (rule_c1_syntax,)),
                (ConstraintAxis.SECURITY_POLICY, (rule_c3_nist_ac6,)),
            ),
            version="1.0.0",
            profile_name="default",
        )
        assert rcs.total_rules == 2

    def test_active_axes(self, rule_c1_syntax, rule_c3_nist_ac6):
        """Active axes returns only axes with rules."""
        rcs = ResolvedConstraintSet(
            rules_by_axis=(
                (ConstraintAxis.SYNTACTIC_VALIDITY, (rule_c1_syntax,)),
                (ConstraintAxis.SECURITY_POLICY, (rule_c3_nist_ac6,)),
                (ConstraintAxis.TEMPORAL_VALIDITY, ()),
            ),
            version="1.0.0",
            profile_name="default",
        )
        active = rcs.active_axes
        assert ConstraintAxis.SYNTACTIC_VALIDITY in active
        assert ConstraintAxis.SECURITY_POLICY in active
        assert ConstraintAxis.TEMPORAL_VALIDITY not in active


# =============================================================================
# CoherenceResult Tests
# =============================================================================


class TestCoherenceResult:
    """Test the primary CGE output type."""

    def _make_result(self, score: float, action: CoherenceAction) -> CoherenceResult:
        """Create a minimal CoherenceResult."""
        return CoherenceResult(
            composite_score=score,
            axis_scores=(),
            action=action,
            policy_profile="default",
            constraint_version="1.0.0",
            output_hash="abc123",
            computed_at=datetime.now(timezone.utc),
            computation_time_ms=15.0,
            cache_hit=True,
            provenance_adjustment=0.0,
        )

    def test_result_is_frozen(self):
        """CoherenceResult must be immutable."""
        result = self._make_result(0.85, CoherenceAction.AUTO_EXECUTE)
        with pytest.raises(AttributeError):
            result.composite_score = 0.99

    def test_is_auto_executable(self):
        """AUTO_EXECUTE action means auto-executable."""
        result = self._make_result(0.85, CoherenceAction.AUTO_EXECUTE)
        assert result.is_auto_executable
        assert not result.needs_human
        assert not result.is_rejected

    def test_needs_human_review(self):
        """HUMAN_REVIEW action means needs human."""
        result = self._make_result(0.65, CoherenceAction.HUMAN_REVIEW)
        assert not result.is_auto_executable
        assert result.needs_human
        assert not result.is_rejected

    def test_needs_human_escalate(self):
        """ESCALATE action also means needs human."""
        result = self._make_result(0.40, CoherenceAction.ESCALATE)
        assert result.needs_human

    def test_is_rejected(self):
        """REJECT action means rejected."""
        result = self._make_result(0.10, CoherenceAction.REJECT)
        assert result.is_rejected
        assert not result.is_auto_executable

    def test_get_axis_score(self):
        """Can retrieve specific axis score."""
        axis_score = AxisCoherenceScore(
            axis=ConstraintAxis.SECURITY_POLICY,
            score=0.75,
            weight=1.2,
            weighted_score=0.9,
            contributing_rules=("rule-1",),
            rule_scores=(),
        )
        result = CoherenceResult(
            composite_score=0.75,
            axis_scores=(axis_score,),
            action=CoherenceAction.HUMAN_REVIEW,
            policy_profile="default",
            constraint_version="1.0.0",
            output_hash="abc123",
            computed_at=datetime.now(timezone.utc),
            computation_time_ms=15.0,
            cache_hit=True,
            provenance_adjustment=0.0,
        )
        found = result.get_axis_score(ConstraintAxis.SECURITY_POLICY)
        assert found is not None
        assert found.score == 0.75

    def test_get_missing_axis_returns_none(self):
        """Missing axis returns None."""
        result = self._make_result(0.85, CoherenceAction.AUTO_EXECUTE)
        assert result.get_axis_score(ConstraintAxis.SECURITY_POLICY) is None

    def test_to_audit_dict(self):
        """Audit dict contains all required fields."""
        result = self._make_result(0.85, CoherenceAction.AUTO_EXECUTE)
        audit = result.to_audit_dict()
        assert "composite_score" in audit
        assert "action" in audit
        assert "policy_profile" in audit
        assert "output_hash" in audit
        assert "computed_at" in audit
        assert "cache_hit" in audit
        assert audit["action"] == "auto_execute"
        assert audit["composite_score"] == 0.85


# =============================================================================
# AgentOutput Tests
# =============================================================================


class TestAgentOutput:
    """Test agent output input type."""

    def test_agent_output_mutable(self):
        """AgentOutput is mutable (not frozen)."""
        output = AgentOutput(text="hello")
        output.text = "world"
        assert output.text == "world"

    def test_default_fields(self):
        """Default fields are empty."""
        output = AgentOutput(text="test")
        assert output.agent_id == ""
        assert output.task_id == ""
        assert output.context == {}


# =============================================================================
# ProvenanceContext Tests
# =============================================================================


class TestProvenanceContext:
    """Test provenance context input type."""

    def test_default_trust_score(self):
        """Default trust score is 1.0 (fully trusted)."""
        ctx = ProvenanceContext()
        assert ctx.trust_score == 1.0

    def test_custom_trust_score(self):
        """Can set custom trust score."""
        ctx = ProvenanceContext(trust_score=0.3, source="external")
        assert ctx.trust_score == 0.3
        assert ctx.source == "external"
