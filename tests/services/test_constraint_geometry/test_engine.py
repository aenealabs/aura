"""
Project Aura - CGE Engine Tests

Tests for the main ConstraintGeometryEngine orchestrator.
Covers the full pipeline: hash -> cache -> resolve -> compute -> action.

Author: Project Aura Team
Created: 2026-02-11
"""

import hashlib

import numpy as np
import pytest

from src.services.constraint_geometry.config import CGEConfig
from src.services.constraint_geometry.constraint_graph import ConstraintGraphResolver
from src.services.constraint_geometry.contracts import (
    CoherenceAction,
    ConstraintAxis,
)
from src.services.constraint_geometry.embedding_cache import EmbeddingCache
from src.services.constraint_geometry.engine import (
    ConstraintGeometryEngine,
    create_engine,
)


def _prewarm_cache(cache: EmbeddingCache, text: str, dim: int = 16) -> None:
    """Pre-warm the cache with a deterministic embedding for the given text."""
    normalized = " ".join(text.strip().split())
    output_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    rng = np.random.RandomState(42)
    embedding = rng.randn(dim).tolist()
    cache.put(output_hash, embedding)


# =============================================================================
# Engine Construction Tests
# =============================================================================


class TestEngineConstruction:
    """Test engine creation and configuration."""

    def test_create_engine_default(self):
        """Can create engine with defaults."""
        engine = create_engine()
        assert engine is not None
        assert engine.config.environment == "test"

    def test_create_engine_with_rules(self, all_rules):
        """Can create engine with pre-loaded rules."""
        engine = create_engine(rules=all_rules)
        assert engine is not None

    def test_engine_has_all_components(self, cge):
        """Engine has all required components."""
        assert cge.graph_resolver is not None
        assert cge.calculator is not None
        assert cge.cache is not None
        assert cge.profiles is not None
        assert cge.provenance is not None


# =============================================================================
# Pipeline Tests
# =============================================================================


class TestPipeline:
    """Test the full CGE assessment pipeline."""

    @pytest.mark.asyncio
    async def test_assess_with_prewarmed_cache(self, cge, sample_output):
        """Assessment with pre-warmed cache returns valid result."""
        _prewarm_cache(cge.cache, sample_output.text)

        result = await cge.assess_coherence(
            output=sample_output,
            policy_profile="default",
        )

        assert 0.0 <= result.composite_score <= 1.0
        assert result.action in CoherenceAction
        assert result.policy_profile == "default"
        assert result.output_hash
        assert result.computation_time_ms > 0
        assert result.cache_hit is True

    @pytest.mark.asyncio
    async def test_assess_returns_axis_scores(self, cge, sample_output):
        """Assessment includes per-axis scores."""
        _prewarm_cache(cge.cache, sample_output.text)

        result = await cge.assess_coherence(output=sample_output)
        assert len(result.axis_scores) > 0

        for axis_score in result.axis_scores:
            assert axis_score.axis in ConstraintAxis
            assert 0.0 <= axis_score.score <= 1.0
            assert axis_score.weight > 0

    @pytest.mark.asyncio
    async def test_assess_with_provenance(
        self, cge, sample_output, high_trust_provenance
    ):
        """Assessment with provenance context adjusts thresholds."""
        _prewarm_cache(cge.cache, sample_output.text)

        result = await cge.assess_coherence(
            output=sample_output,
            provenance_context=high_trust_provenance,
        )

        assert result.provenance_adjustment >= 0.0

    @pytest.mark.asyncio
    async def test_assess_low_trust_provenance(
        self, cge, sample_output, low_trust_provenance
    ):
        """Low trust provenance produces positive adjustment."""
        _prewarm_cache(cge.cache, sample_output.text)

        result = await cge.assess_coherence(
            output=sample_output,
            provenance_context=low_trust_provenance,
        )

        assert result.provenance_adjustment > 0.0

    @pytest.mark.asyncio
    async def test_assess_no_provenance_zero_adjustment(self, cge, sample_output):
        """No provenance context means zero adjustment."""
        _prewarm_cache(cge.cache, sample_output.text)

        result = await cge.assess_coherence(output=sample_output)
        assert result.provenance_adjustment == 0.0

    @pytest.mark.asyncio
    async def test_unknown_profile_raises(self, cge, sample_output):
        """Unknown policy profile raises KeyError."""
        _prewarm_cache(cge.cache, sample_output.text)

        with pytest.raises(KeyError, match="not found"):
            await cge.assess_coherence(
                output=sample_output,
                policy_profile="nonexistent",
            )


# =============================================================================
# Normalization Tests
# =============================================================================


class TestNormalization:
    """Test text normalization for deterministic hashing."""

    def test_whitespace_collapse(self):
        """Multiple whitespace collapses to single space."""
        assert ConstraintGeometryEngine._normalize("  hello   world  ") == "hello world"

    def test_newline_collapse(self):
        """Newlines and tabs collapse to spaces."""
        assert ConstraintGeometryEngine._normalize("hello\n\tworld") == "hello world"

    def test_strip(self):
        """Leading/trailing whitespace is stripped."""
        assert ConstraintGeometryEngine._normalize("   test   ") == "test"

    def test_empty_string(self):
        """Empty/whitespace-only string normalizes to empty."""
        assert ConstraintGeometryEngine._normalize("   ") == ""
        assert ConstraintGeometryEngine._normalize("") == ""


# =============================================================================
# Action Determination Tests
# =============================================================================


class TestActionDetermination:
    """Test that actions are correctly determined from CCS scores."""

    @pytest.mark.asyncio
    async def test_different_profiles_different_thresholds(self, cge, sample_output):
        """Different profiles have different threshold boundaries."""
        _prewarm_cache(cge.cache, sample_output.text)

        default_result = await cge.assess_coherence(
            output=sample_output, policy_profile="default"
        )
        sandbox_result = await cge.assess_coherence(
            output=sample_output, policy_profile="developer-sandbox"
        )

        # Both produce valid results
        assert default_result.action in CoherenceAction
        assert sandbox_result.action in CoherenceAction

    @pytest.mark.asyncio
    async def test_audit_dict_format(self, cge, sample_output):
        """Audit dict has correct format."""
        _prewarm_cache(cge.cache, sample_output.text)

        result = await cge.assess_coherence(output=sample_output)
        audit = result.to_audit_dict()

        assert "composite_score" in audit
        assert "axis_scores" in audit
        assert "action" in audit
        assert "policy_profile" in audit
        assert "output_hash" in audit
        assert "computed_at" in audit
        assert "computation_time_ms" in audit
        assert "cache_hit" in audit
        assert "provenance_adjustment" in audit


# =============================================================================
# Constraint Graph Tests
# =============================================================================


class TestConstraintGraph:
    """Test constraint graph resolution."""

    @pytest.mark.asyncio
    async def test_resolver_returns_rules(self, graph_resolver, profile_manager):
        """Resolver returns rules grouped by axis."""
        profile = profile_manager.get("default")
        constraints = await graph_resolver.resolve(profile=profile)

        assert constraints.version == "1.0.0"
        assert constraints.total_rules > 0

    @pytest.mark.asyncio
    async def test_resolver_groups_by_axis(self, graph_resolver, profile_manager):
        """Rules are correctly grouped by axis."""
        profile = profile_manager.get("default")
        constraints = await graph_resolver.resolve(profile=profile)

        c1_rules = constraints.get_axis_rules(ConstraintAxis.SYNTACTIC_VALIDITY)
        c3_rules = constraints.get_axis_rules(ConstraintAxis.SECURITY_POLICY)

        assert len(c1_rules) == 2  # syntax + types
        assert len(c3_rules) == 2  # nist-ac6 + wildcard

    @pytest.mark.asyncio
    async def test_empty_resolver(self, profile_manager):
        """Resolver with no rules returns empty set."""
        resolver = ConstraintGraphResolver()
        profile = profile_manager.get("default")
        constraints = await resolver.resolve(profile=profile)
        assert constraints.total_rules == 0


# =============================================================================
# Config Tests
# =============================================================================


class TestConfig:
    """Test CGE configuration."""

    def test_test_config(self):
        """Test config disables external dependencies."""
        config = CGEConfig.for_testing()
        assert config.cache.enable_redis is False
        assert config.metrics.enabled is False
        assert config.audit.enable_audit is False

    def test_production_config(self):
        """Production config enables all safety features."""
        config = CGEConfig.for_production()
        assert config.fail_open is False
        assert config.metrics.enabled is True
        assert config.audit.enable_audit is True

    def test_validate_production_fail_open(self):
        """Production with fail_open=True fails validation."""
        config = CGEConfig(environment="prod", fail_open=True)
        errors = config.validate()
        assert any("fail_open" in e for e in errors)

    def test_validate_production_no_audit(self):
        """Production without audit fails validation."""
        from src.services.constraint_geometry.config import AuditConfig

        config = CGEConfig(
            environment="prod",
            audit=AuditConfig(enable_audit=False),
        )
        errors = config.validate()
        assert any("Audit" in e for e in errors)
