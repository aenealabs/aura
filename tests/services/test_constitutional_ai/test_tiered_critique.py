"""Unit tests for tiered critique strategy.

Tests the autonomy-to-tier mapping and principle filtering functionality
for Constitutional AI Phase 3 optimization.
"""

import pytest

from src.services.constitutional_ai.models import PrincipleSeverity
from src.services.constitutional_ai.tiered_critique import (
    AUTONOMY_TO_CRITIQUE_TIER,
    PRINCIPLES_BY_TIER,
    SEVERITIES_BY_TIER,
    CritiqueTier,
    calculate_tier_efficiency,
    filter_principles_by_tier,
    get_critique_tier,
    get_principles_for_tier,
    get_severities_for_tier,
    get_tier_description,
)

# =============================================================================
# Test CritiqueTier Enum
# =============================================================================


class TestCritiqueTier:
    """Tests for CritiqueTier enum."""

    def test_enum_values(self):
        """Should have expected tier values."""
        assert CritiqueTier.FULL.value == "full"
        assert CritiqueTier.STANDARD.value == "standard"
        assert CritiqueTier.REDUCED.value == "reduced"
        assert CritiqueTier.MINIMAL.value == "minimal"

    def test_tier_count(self):
        """Should have exactly 4 tiers."""
        assert len(CritiqueTier) == 4


# =============================================================================
# Test AUTONOMY_TO_CRITIQUE_TIER Mapping
# =============================================================================


class TestAutonomyMapping:
    """Tests for autonomy level to critique tier mapping."""

    def test_full_autonomous_maps_to_full(self):
        """FULL_AUTONOMOUS should map to FULL tier."""
        assert AUTONOMY_TO_CRITIQUE_TIER["FULL_AUTONOMOUS"] == CritiqueTier.FULL

    def test_limited_autonomous_maps_to_reduced(self):
        """LIMITED_AUTONOMOUS should map to REDUCED tier."""
        assert AUTONOMY_TO_CRITIQUE_TIER["LIMITED_AUTONOMOUS"] == CritiqueTier.REDUCED

    def test_collaborative_maps_to_standard(self):
        """COLLABORATIVE should map to STANDARD tier."""
        assert AUTONOMY_TO_CRITIQUE_TIER["COLLABORATIVE"] == CritiqueTier.STANDARD

    def test_full_hitl_maps_to_minimal(self):
        """FULL_HITL should map to MINIMAL tier."""
        assert AUTONOMY_TO_CRITIQUE_TIER["FULL_HITL"] == CritiqueTier.MINIMAL

    def test_all_autonomy_levels_mapped(self):
        """All four autonomy levels should be mapped."""
        expected_levels = {
            "FULL_AUTONOMOUS",
            "LIMITED_AUTONOMOUS",
            "COLLABORATIVE",
            "FULL_HITL",
        }
        assert set(AUTONOMY_TO_CRITIQUE_TIER.keys()) == expected_levels


# =============================================================================
# Test PRINCIPLES_BY_TIER Constants
# =============================================================================


class TestPrinciplesByTier:
    """Tests for PRINCIPLES_BY_TIER constants."""

    def test_full_tier_is_none(self):
        """FULL tier should have None (all principles)."""
        assert PRINCIPLES_BY_TIER[CritiqueTier.FULL] is None

    def test_standard_tier_is_none(self):
        """STANDARD tier should have None (all principles)."""
        assert PRINCIPLES_BY_TIER[CritiqueTier.STANDARD] is None

    def test_reduced_tier_has_7_principles(self):
        """REDUCED tier should have 7 principles (CRITICAL + HIGH)."""
        reduced = PRINCIPLES_BY_TIER[CritiqueTier.REDUCED]
        assert reduced is not None
        assert len(reduced) == 7

    def test_minimal_tier_has_3_principles(self):
        """MINIMAL tier should have 3 principles (CRITICAL only)."""
        minimal = PRINCIPLES_BY_TIER[CritiqueTier.MINIMAL]
        assert minimal is not None
        assert len(minimal) == 3

    def test_minimal_principles_are_critical(self):
        """MINIMAL tier should only include CRITICAL principles."""
        minimal = PRINCIPLES_BY_TIER[CritiqueTier.MINIMAL]
        expected = {
            "principle_1_security_first",
            "principle_2_data_protection",
            "principle_3_sandbox_isolation",
        }
        assert set(minimal) == expected

    def test_reduced_includes_minimal(self):
        """REDUCED tier should include all MINIMAL principles."""
        reduced = set(PRINCIPLES_BY_TIER[CritiqueTier.REDUCED])
        minimal = set(PRINCIPLES_BY_TIER[CritiqueTier.MINIMAL])
        assert minimal.issubset(reduced)


# =============================================================================
# Test SEVERITIES_BY_TIER Constants
# =============================================================================


class TestSeveritiesByTier:
    """Tests for SEVERITIES_BY_TIER constants."""

    def test_full_tier_has_all_severities(self):
        """FULL tier should include all severity levels."""
        full_severities = SEVERITIES_BY_TIER[CritiqueTier.FULL]
        assert PrincipleSeverity.CRITICAL in full_severities
        assert PrincipleSeverity.HIGH in full_severities
        assert PrincipleSeverity.MEDIUM in full_severities
        assert PrincipleSeverity.LOW in full_severities

    def test_standard_tier_has_all_severities(self):
        """STANDARD tier should include all severity levels."""
        standard_severities = SEVERITIES_BY_TIER[CritiqueTier.STANDARD]
        assert len(standard_severities) == 4

    def test_reduced_tier_has_critical_and_high(self):
        """REDUCED tier should only include CRITICAL and HIGH."""
        reduced_severities = SEVERITIES_BY_TIER[CritiqueTier.REDUCED]
        assert PrincipleSeverity.CRITICAL in reduced_severities
        assert PrincipleSeverity.HIGH in reduced_severities
        assert PrincipleSeverity.MEDIUM not in reduced_severities
        assert PrincipleSeverity.LOW not in reduced_severities

    def test_minimal_tier_has_critical_only(self):
        """MINIMAL tier should only include CRITICAL."""
        minimal_severities = SEVERITIES_BY_TIER[CritiqueTier.MINIMAL]
        assert minimal_severities == {PrincipleSeverity.CRITICAL}


# =============================================================================
# Test get_critique_tier
# =============================================================================


class TestGetCritiqueTier:
    """Tests for get_critique_tier function."""

    def test_returns_mapped_tier(self):
        """Should return correct tier for known autonomy level."""
        assert get_critique_tier("FULL_AUTONOMOUS") == CritiqueTier.FULL
        assert get_critique_tier("LIMITED_AUTONOMOUS") == CritiqueTier.REDUCED
        assert get_critique_tier("COLLABORATIVE") == CritiqueTier.STANDARD
        assert get_critique_tier("FULL_HITL") == CritiqueTier.MINIMAL

    def test_none_returns_standard(self):
        """None autonomy level should default to STANDARD."""
        assert get_critique_tier(None) == CritiqueTier.STANDARD

    def test_unknown_returns_standard(self):
        """Unknown autonomy level should default to STANDARD."""
        assert get_critique_tier("UNKNOWN_LEVEL") == CritiqueTier.STANDARD
        assert get_critique_tier("invalid") == CritiqueTier.STANDARD

    def test_case_insensitive(self):
        """Should handle case variations."""
        assert get_critique_tier("full_autonomous") == CritiqueTier.FULL
        assert get_critique_tier("collaborative") == CritiqueTier.STANDARD
        assert get_critique_tier("FULL_hitl") == CritiqueTier.MINIMAL


# =============================================================================
# Test get_principles_for_tier
# =============================================================================


class TestGetPrinciplesForTier:
    """Tests for get_principles_for_tier function."""

    def test_full_returns_none(self):
        """FULL tier should return None (all principles)."""
        assert get_principles_for_tier(CritiqueTier.FULL) is None

    def test_standard_returns_none(self):
        """STANDARD tier should return None (all principles)."""
        assert get_principles_for_tier(CritiqueTier.STANDARD) is None

    def test_reduced_returns_list(self):
        """REDUCED tier should return list of principles."""
        principles = get_principles_for_tier(CritiqueTier.REDUCED)
        assert principles is not None
        assert isinstance(principles, list)
        assert len(principles) == 7

    def test_minimal_returns_list(self):
        """MINIMAL tier should return list of principles."""
        principles = get_principles_for_tier(CritiqueTier.MINIMAL)
        assert principles is not None
        assert isinstance(principles, list)
        assert len(principles) == 3


# =============================================================================
# Test get_severities_for_tier
# =============================================================================


class TestGetSeveritiesForTier:
    """Tests for get_severities_for_tier function."""

    def test_returns_correct_severities(self):
        """Should return correct severity set for each tier."""
        full = get_severities_for_tier(CritiqueTier.FULL)
        assert len(full) == 4

        reduced = get_severities_for_tier(CritiqueTier.REDUCED)
        assert len(reduced) == 2

        minimal = get_severities_for_tier(CritiqueTier.MINIMAL)
        assert len(minimal) == 1


# =============================================================================
# Test filter_principles_by_tier
# =============================================================================


class TestFilterPrinciplesByTier:
    """Tests for filter_principles_by_tier function."""

    @pytest.fixture
    def all_principles(self):
        """List of all principle IDs for testing."""
        return [
            "principle_1_security_first",
            "principle_2_data_protection",
            "principle_3_sandbox_isolation",
            "principle_4_regulatory_compliance",
            "principle_5_audit_trail",
            "principle_6_explicit_intent",
            "principle_7_testing_emphasis",
            "principle_8_accuracy_precision",
            "principle_9_honest_uncertainty",
            "principle_10_independent_judgment",
            "principle_11_reproducible_explanations",
            "principle_12_maintainability",
            "principle_13_performance_awareness",
            "principle_14_graceful_degradation",
            "principle_15_comprehensive_documentation",
            "principle_16_conflict_resolution",
        ]

    def test_full_tier_returns_all(self, all_principles):
        """FULL tier should return all principles unfiltered."""
        filtered = filter_principles_by_tier(all_principles, CritiqueTier.FULL)
        assert filtered == all_principles

    def test_standard_tier_returns_all(self, all_principles):
        """STANDARD tier should return all principles unfiltered."""
        filtered = filter_principles_by_tier(all_principles, CritiqueTier.STANDARD)
        assert filtered == all_principles

    def test_reduced_tier_filters_to_7(self, all_principles):
        """REDUCED tier should filter to 7 principles."""
        filtered = filter_principles_by_tier(all_principles, CritiqueTier.REDUCED)
        assert len(filtered) == 7

    def test_minimal_tier_filters_to_3(self, all_principles):
        """MINIMAL tier should filter to 3 principles."""
        filtered = filter_principles_by_tier(all_principles, CritiqueTier.MINIMAL)
        assert len(filtered) == 3

    def test_preserves_order(self, all_principles):
        """Filtered list should preserve input order."""
        filtered = filter_principles_by_tier(all_principles, CritiqueTier.MINIMAL)

        # First three in input are the CRITICAL ones
        assert filtered[0] == "principle_1_security_first"
        assert filtered[1] == "principle_2_data_protection"
        assert filtered[2] == "principle_3_sandbox_isolation"

    def test_handles_subset_input(self):
        """Should handle input that's already a subset."""
        partial_list = [
            "principle_1_security_first",
            "principle_12_maintainability",
        ]
        filtered = filter_principles_by_tier(partial_list, CritiqueTier.MINIMAL)

        # Only principle_1 is in MINIMAL tier
        assert filtered == ["principle_1_security_first"]

    def test_handles_empty_input(self):
        """Should handle empty input list."""
        filtered = filter_principles_by_tier([], CritiqueTier.MINIMAL)
        assert filtered == []


# =============================================================================
# Test get_tier_description
# =============================================================================


class TestGetTierDescription:
    """Tests for get_tier_description function."""

    def test_full_description(self):
        """FULL tier should have descriptive text."""
        desc = get_tier_description(CritiqueTier.FULL)
        assert "16 principles" in desc
        assert "Full" in desc

    def test_standard_description(self):
        """STANDARD tier should have descriptive text."""
        desc = get_tier_description(CritiqueTier.STANDARD)
        assert "16 principles" in desc
        assert "Standard" in desc

    def test_reduced_description(self):
        """REDUCED tier should have descriptive text."""
        desc = get_tier_description(CritiqueTier.REDUCED)
        assert "7 principles" in desc
        assert "CRITICAL" in desc
        assert "HIGH" in desc

    def test_minimal_description(self):
        """MINIMAL tier should have descriptive text."""
        desc = get_tier_description(CritiqueTier.MINIMAL)
        assert "3 principles" in desc
        assert "CRITICAL" in desc


# =============================================================================
# Test calculate_tier_efficiency
# =============================================================================


class TestCalculateTierEfficiency:
    """Tests for calculate_tier_efficiency function."""

    def test_full_tier_zero_efficiency(self):
        """FULL tier should have 0% efficiency (no skipping)."""
        efficiency = calculate_tier_efficiency(CritiqueTier.FULL)
        assert efficiency == 0.0

    def test_standard_tier_zero_efficiency(self):
        """STANDARD tier should have 0% efficiency (no skipping)."""
        efficiency = calculate_tier_efficiency(CritiqueTier.STANDARD)
        assert efficiency == 0.0

    def test_reduced_tier_efficiency(self):
        """REDUCED tier should skip ~56% of principles (9/16)."""
        efficiency = calculate_tier_efficiency(CritiqueTier.REDUCED)
        # (16 - 7) / 16 = 0.5625
        assert efficiency == pytest.approx(0.5625)

    def test_minimal_tier_efficiency(self):
        """MINIMAL tier should skip ~81% of principles (13/16)."""
        efficiency = calculate_tier_efficiency(CritiqueTier.MINIMAL)
        # (16 - 3) / 16 = 0.8125
        assert efficiency == pytest.approx(0.8125)

    def test_efficiency_is_float(self):
        """Efficiency should be a float between 0 and 1."""
        for tier in CritiqueTier:
            efficiency = calculate_tier_efficiency(tier)
            assert isinstance(efficiency, float)
            assert 0.0 <= efficiency <= 1.0


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestTierIntegration:
    """Integration-style tests for tier functionality."""

    def test_autonomy_to_tier_to_principles_flow(self):
        """Test full flow from autonomy level to filtered principles."""
        # Start with autonomy level
        autonomy = "LIMITED_AUTONOMOUS"

        # Get tier
        tier = get_critique_tier(autonomy)
        assert tier == CritiqueTier.REDUCED

        # Get principles for tier
        principles = get_principles_for_tier(tier)
        assert principles is not None
        assert len(principles) == 7

        # Verify all are HIGH or CRITICAL
        # (CRITICAL: 1,2,3 and HIGH: 4,5,10,16)
        expected = {
            "principle_1_security_first",
            "principle_2_data_protection",
            "principle_3_sandbox_isolation",
            "principle_4_regulatory_compliance",
            "principle_5_audit_trail",
            "principle_10_independent_judgment",
            "principle_16_conflict_resolution",
        }
        assert set(principles) == expected

    def test_full_hitl_minimal_evaluation(self):
        """FULL_HITL should result in minimal (CRITICAL-only) evaluation."""
        tier = get_critique_tier("FULL_HITL")
        assert tier == CritiqueTier.MINIMAL

        principles = get_principles_for_tier(tier)
        assert len(principles) == 3

        severities = get_severities_for_tier(tier)
        assert severities == {PrincipleSeverity.CRITICAL}

        # High efficiency since human reviews anyway
        efficiency = calculate_tier_efficiency(tier)
        assert efficiency > 0.8
