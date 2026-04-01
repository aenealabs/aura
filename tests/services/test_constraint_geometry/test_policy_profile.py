"""
Project Aura - CGE Policy Profile Tests

Tests for policy profiles, thresholds, and action determination.

Author: Project Aura Team
Created: 2026-02-11
"""

import pytest

from src.services.constraint_geometry.contracts import CoherenceAction, ConstraintAxis
from src.services.constraint_geometry.policy_profile import (
    PROFILE_DEFAULT,
    PROFILE_DEVELOPER_SANDBOX,
    PROFILE_DOD_IL5,
    PROFILE_SOX_COMPLIANT,
    PolicyProfile,
    PolicyThresholds,
)

# =============================================================================
# PolicyThresholds Tests
# =============================================================================


class TestPolicyThresholds:
    """Test deterministic threshold-based action determination."""

    def test_auto_execute_above_threshold(self):
        """CCS above auto_execute threshold -> AUTO_EXECUTE."""
        thresholds = PolicyThresholds(auto_execute_threshold=0.80)
        assert thresholds.determine_action(0.85) == CoherenceAction.AUTO_EXECUTE
        assert thresholds.determine_action(0.80) == CoherenceAction.AUTO_EXECUTE
        assert thresholds.determine_action(1.0) == CoherenceAction.AUTO_EXECUTE

    def test_human_review_in_band(self):
        """CCS in review band -> HUMAN_REVIEW."""
        thresholds = PolicyThresholds(
            auto_execute_threshold=0.80,
            review_threshold=0.55,
        )
        assert thresholds.determine_action(0.79) == CoherenceAction.HUMAN_REVIEW
        assert thresholds.determine_action(0.55) == CoherenceAction.HUMAN_REVIEW
        assert thresholds.determine_action(0.65) == CoherenceAction.HUMAN_REVIEW

    def test_escalate_in_band(self):
        """CCS in escalate band -> ESCALATE."""
        thresholds = PolicyThresholds(
            auto_execute_threshold=0.80,
            review_threshold=0.55,
            escalate_threshold=0.30,
        )
        assert thresholds.determine_action(0.54) == CoherenceAction.ESCALATE
        assert thresholds.determine_action(0.30) == CoherenceAction.ESCALATE
        assert thresholds.determine_action(0.40) == CoherenceAction.ESCALATE

    def test_reject_below_escalate(self):
        """CCS below escalate threshold -> REJECT."""
        thresholds = PolicyThresholds(escalate_threshold=0.30)
        assert thresholds.determine_action(0.29) == CoherenceAction.REJECT
        assert thresholds.determine_action(0.0) == CoherenceAction.REJECT
        assert thresholds.determine_action(0.15) == CoherenceAction.REJECT

    def test_provenance_raises_auto_threshold(self):
        """Provenance adjustment raises auto-execute threshold."""
        thresholds = PolicyThresholds(auto_execute_threshold=0.80)
        # Without provenance: 0.82 -> AUTO_EXECUTE
        assert thresholds.determine_action(0.82) == CoherenceAction.AUTO_EXECUTE
        # With provenance adjustment of 0.08: effective threshold = 0.88
        # 0.82 is now below 0.88, so HUMAN_REVIEW
        assert (
            thresholds.determine_action(0.82, provenance_adjustment=0.08)
            == CoherenceAction.HUMAN_REVIEW
        )

    def test_provenance_capped_at_one(self):
        """Provenance adjustment doesn't push threshold above 1.0."""
        thresholds = PolicyThresholds(auto_execute_threshold=0.95)
        action = thresholds.determine_action(0.98, provenance_adjustment=0.10)
        # Effective auto = min(0.95 + 0.10, 1.0) = 1.0
        # 0.98 < 1.0, so HUMAN_REVIEW
        assert action == CoherenceAction.HUMAN_REVIEW

    def test_boundary_values(self):
        """Test exact boundary values."""
        thresholds = PolicyThresholds(
            auto_execute_threshold=0.80,
            review_threshold=0.55,
            escalate_threshold=0.30,
        )
        assert thresholds.determine_action(0.80) == CoherenceAction.AUTO_EXECUTE
        assert thresholds.determine_action(0.55) == CoherenceAction.HUMAN_REVIEW
        assert thresholds.determine_action(0.30) == CoherenceAction.ESCALATE
        assert thresholds.determine_action(0.29999) == CoherenceAction.REJECT


# =============================================================================
# Built-in Profile Tests
# =============================================================================


class TestBuiltinProfiles:
    """Test the 4 built-in policy profiles."""

    def test_default_profile(self):
        """Default profile has standard thresholds."""
        p = PROFILE_DEFAULT
        assert p.name == "default"
        assert p.thresholds.auto_execute_threshold == 0.80
        assert p.thresholds.review_threshold == 0.55

    def test_dod_il5_stricter(self):
        """DoD-IL5 has higher thresholds than default."""
        assert (
            PROFILE_DOD_IL5.thresholds.auto_execute_threshold
            > PROFILE_DEFAULT.thresholds.auto_execute_threshold
        )
        assert (
            PROFILE_DOD_IL5.thresholds.review_threshold
            > PROFILE_DEFAULT.thresholds.review_threshold
        )

    def test_developer_sandbox_relaxed(self):
        """Developer sandbox has lower thresholds than default."""
        assert (
            PROFILE_DEVELOPER_SANDBOX.thresholds.auto_execute_threshold
            < PROFILE_DEFAULT.thresholds.auto_execute_threshold
        )
        assert (
            PROFILE_DEVELOPER_SANDBOX.thresholds.review_threshold
            < PROFILE_DEFAULT.thresholds.review_threshold
        )

    def test_sox_compliant_security_focused(self):
        """SOX profile weights domain compliance heavily."""
        assert (
            PROFILE_SOX_COMPLIANT.axis_weights[ConstraintAxis.DOMAIN_COMPLIANCE] > 1.0
        )

    def test_dod_il5_security_weight(self):
        """DoD-IL5 weights security policy most heavily."""
        c3_weight = PROFILE_DOD_IL5.axis_weights[ConstraintAxis.SECURITY_POLICY]
        assert c3_weight == 1.5

    def test_all_profiles_have_seven_axes(self):
        """All profiles define weights for all 7 axes."""
        for profile in [
            PROFILE_DEFAULT,
            PROFILE_DOD_IL5,
            PROFILE_DEVELOPER_SANDBOX,
            PROFILE_SOX_COMPLIANT,
        ]:
            assert len(profile.axis_weights) == 7
            for axis in ConstraintAxis:
                assert axis in profile.axis_weights

    def test_all_profiles_are_frozen(self):
        """All profiles are frozen dataclasses."""
        for profile in [
            PROFILE_DEFAULT,
            PROFILE_DOD_IL5,
            PROFILE_DEVELOPER_SANDBOX,
            PROFILE_SOX_COMPLIANT,
        ]:
            with pytest.raises(AttributeError):
                profile.name = "modified"


# =============================================================================
# PolicyProfileManager Tests
# =============================================================================


class TestPolicyProfileManager:
    """Test profile management."""

    def test_get_builtin_profile(self, profile_manager):
        """Can retrieve built-in profiles."""
        default = profile_manager.get("default")
        assert default.name == "default"

    def test_get_all_builtins(self, profile_manager):
        """All 4 built-in profiles are available."""
        names = profile_manager.list_profiles()
        assert "default" in names
        assert "dod-il5" in names
        assert "developer-sandbox" in names
        assert "sox-compliant" in names

    def test_get_nonexistent_raises(self, profile_manager):
        """Getting unknown profile raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            profile_manager.get("nonexistent")

    def test_register_custom_profile(self, profile_manager):
        """Can register custom profiles."""
        custom = PolicyProfile(
            name="custom-test",
            description="Test profile",
            axis_weights={axis: 1.0 for axis in ConstraintAxis},
            thresholds=PolicyThresholds(),
        )
        profile_manager.register(custom)
        retrieved = profile_manager.get("custom-test")
        assert retrieved.name == "custom-test"

    def test_cannot_override_builtin(self, profile_manager):
        """Cannot override built-in profiles."""
        fake = PolicyProfile(
            name="default",
            description="Fake default",
            axis_weights={axis: 0.0 for axis in ConstraintAxis},
            thresholds=PolicyThresholds(),
        )
        with pytest.raises(ValueError, match="Cannot override"):
            profile_manager.register(fake)

    def test_builtin_profiles_list(self, profile_manager):
        """Builtin profiles list returns only built-ins."""
        assert len(profile_manager.builtin_profiles) == 4
