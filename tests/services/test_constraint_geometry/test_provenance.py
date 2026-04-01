"""
Project Aura - CGE Provenance Adapter Tests

Tests for provenance trust score integration with the CGE.
Verifies that low-trust contexts tighten constraints and raise thresholds.

Author: Project Aura Team
Created: 2026-02-11
"""

import pytest

from src.services.constraint_geometry.contracts import ProvenanceContext
from src.services.constraint_geometry.provenance_adapter import ProvenanceAdapter

# =============================================================================
# Adjustment Computation Tests
# =============================================================================


class TestProvenanceAdjustment:
    """Test provenance adjustment computation."""

    def test_full_trust_zero_adjustment(self, provenance_adapter):
        """Trust score 1.0 produces zero adjustment."""
        ctx = ProvenanceContext(trust_score=1.0)
        adj = provenance_adapter.compute_adjustment(ctx)
        assert adj == pytest.approx(0.0)

    def test_zero_trust_max_adjustment(self, provenance_adapter):
        """Trust score 0.0 produces maximum adjustment."""
        ctx = ProvenanceContext(trust_score=0.0)
        adj = provenance_adapter.compute_adjustment(ctx)
        assert adj == pytest.approx(0.5)  # default sensitivity

    def test_partial_trust(self, provenance_adapter):
        """Partial trust produces proportional adjustment."""
        ctx = ProvenanceContext(trust_score=0.5)
        adj = provenance_adapter.compute_adjustment(ctx)
        assert adj == pytest.approx(0.25)  # (1 - 0.5) * 0.5

    def test_high_trust_minimal(self, provenance_adapter):
        """High trust produces minimal adjustment."""
        ctx = ProvenanceContext(trust_score=0.95)
        adj = provenance_adapter.compute_adjustment(ctx)
        assert adj == pytest.approx(0.025)

    def test_low_trust_significant(self, provenance_adapter):
        """Low trust produces significant adjustment."""
        ctx = ProvenanceContext(trust_score=0.3)
        adj = provenance_adapter.compute_adjustment(ctx)
        assert adj == pytest.approx(0.35)

    def test_custom_sensitivity(self, provenance_adapter):
        """Override sensitivity changes adjustment magnitude."""
        ctx = ProvenanceContext(trust_score=0.5)
        adj = provenance_adapter.compute_adjustment(ctx, sensitivity=0.8)
        assert adj == pytest.approx(0.4)  # (1 - 0.5) * 0.8

    def test_trust_clamped_to_range(self, provenance_adapter):
        """Trust score is clamped to [0, 1]."""
        ctx_low = ProvenanceContext(trust_score=-0.5)
        ctx_high = ProvenanceContext(trust_score=1.5)
        adj_low = provenance_adapter.compute_adjustment(ctx_low)
        adj_high = provenance_adapter.compute_adjustment(ctx_high)
        assert adj_low == pytest.approx(0.5)  # Clamped to 0.0
        assert adj_high == pytest.approx(0.0)  # Clamped to 1.0


# =============================================================================
# Threshold Raising Tests
# =============================================================================


class TestThresholdRaising:
    """Test provenance-based threshold modification."""

    def test_low_trust_raises_threshold(self, provenance_adapter):
        """Low trust raises auto-execute threshold."""
        ctx = ProvenanceContext(trust_score=0.3)
        raised = provenance_adapter.compute_threshold_raise(ctx, base_threshold=0.80)
        assert raised > 0.80
        # 0.80 + (1-0.3)*0.5 = 1.15, but capped at 1.0
        assert raised == pytest.approx(1.0)

    def test_high_trust_barely_raises(self, provenance_adapter):
        """High trust barely raises threshold."""
        ctx = ProvenanceContext(trust_score=0.95)
        raised = provenance_adapter.compute_threshold_raise(ctx, base_threshold=0.80)
        assert raised == pytest.approx(0.825)

    def test_threshold_capped_at_one(self, provenance_adapter):
        """Raised threshold is capped at 1.0."""
        ctx = ProvenanceContext(trust_score=0.0)
        raised = provenance_adapter.compute_threshold_raise(ctx, base_threshold=0.80)
        assert raised <= 1.0


# =============================================================================
# Security Weight Multiplier Tests
# =============================================================================


class TestSecurityWeightMultiplier:
    """Test provenance-based C3 weight adjustment."""

    def test_low_trust_amplifies_security(self, provenance_adapter):
        """Low trust amplifies security axis weight."""
        ctx = ProvenanceContext(trust_score=0.3)
        mult = provenance_adapter.compute_security_weight_multiplier(ctx)
        assert mult > 1.0
        assert mult == pytest.approx(1.35)

    def test_high_trust_minimal_amplification(self, provenance_adapter):
        """High trust barely amplifies security weight."""
        ctx = ProvenanceContext(trust_score=0.95)
        mult = provenance_adapter.compute_security_weight_multiplier(ctx)
        assert mult == pytest.approx(1.025)

    def test_full_trust_no_amplification(self, provenance_adapter):
        """Full trust produces multiplier 1.0."""
        ctx = ProvenanceContext(trust_score=1.0)
        mult = provenance_adapter.compute_security_weight_multiplier(ctx)
        assert mult == pytest.approx(1.0)

    def test_zero_trust_maximum_amplification(self, provenance_adapter):
        """Zero trust produces maximum amplification."""
        ctx = ProvenanceContext(trust_score=0.0)
        mult = provenance_adapter.compute_security_weight_multiplier(ctx)
        assert mult == pytest.approx(1.5)  # 1.0 + 0.5


# =============================================================================
# Integration Behavior Tests
# =============================================================================


class TestProvenanceIntegration:
    """Test provenance adapter behavior in context of CGE pipeline."""

    def test_unverified_repo_high_adjustment(self):
        """Unverified repository gets significant adjustment."""
        adapter = ProvenanceAdapter(default_sensitivity=0.5)
        ctx = ProvenanceContext(
            trust_score=0.2,
            source="external",
            verified=False,
        )
        adj = adapter.compute_adjustment(ctx)
        assert adj > 0.3

    def test_signed_commit_low_adjustment(self):
        """Signed commit from internal source gets minimal adjustment."""
        adapter = ProvenanceAdapter(default_sensitivity=0.5)
        ctx = ProvenanceContext(
            trust_score=0.95,
            source="internal",
            verified=True,
            commit_signed=True,
        )
        adj = adapter.compute_adjustment(ctx)
        assert adj < 0.05

    def test_dod_sensitivity_higher(self):
        """DoD-IL5 profile sensitivity amplifies provenance impact."""
        adapter = ProvenanceAdapter(default_sensitivity=0.5)
        ctx = ProvenanceContext(trust_score=0.5)

        default_adj = adapter.compute_adjustment(ctx, sensitivity=0.5)
        dod_adj = adapter.compute_adjustment(ctx, sensitivity=0.8)

        assert dod_adj > default_adj
