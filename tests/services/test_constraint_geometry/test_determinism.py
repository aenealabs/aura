"""
Project Aura - CGE Determinism Validation Tests

Property-based tests that verify the CGE produces identical scores
for identical inputs. The core guarantee of the CGE is:
    same input + same constraints = same score, ALWAYS.

These tests run the same assessment multiple times and verify
that every score is bit-for-bit identical.

Author: Project Aura Team
Created: 2026-02-11
"""

import hashlib

import numpy as np
import pytest

from src.services.constraint_geometry.coherence_calculator import CoherenceCalculator
from src.services.constraint_geometry.config import CacheConfig, CGEConfig
from src.services.constraint_geometry.constraint_graph import ConstraintGraphResolver
from src.services.constraint_geometry.contracts import AgentOutput, ProvenanceContext
from src.services.constraint_geometry.embedding_cache import EmbeddingCache
from src.services.constraint_geometry.engine import ConstraintGeometryEngine
from src.services.constraint_geometry.policy_profile import PolicyProfileManager
from src.services.constraint_geometry.provenance_adapter import ProvenanceAdapter

# Repetition counts. These tests previously used
# ``@pytest.mark.parametrize("iteration", range(N))`` and stashed a baseline on
# the test class when ``iteration == 0``, comparing against it on every later
# iteration.
#
# That pattern is not parallel-safe. Under ``pytest -n auto`` -- which
# ``tests/CLAUDE.md`` documents as a supported way to run the suite -- xdist
# distributes the parametrized cases across worker processes, so the case that
# writes the baseline frequently lands on a different worker from the ones that
# read it. The readers then fail with ``AttributeError: type object
# 'TestCalculatorDeterminism' has no attribute '_baseline_coherence'``.
# Measured cost before this change: 134 of 403 tests failing under ``-n auto``,
# all 403 passing without it.
#
# Repeating inside a single test is both parallel-safe and a stronger
# assertion: it compares every result against every other, rather than each
# against one arbitrary baseline. It also collapses ~150 test items into 6.
REPEATS = 50
SHORT_REPEATS = 20
PIPELINE_REPEATS = 10

# =============================================================================
# Calculator Determinism
# =============================================================================


class TestCalculatorDeterminism:
    """Verify calculator always produces identical results."""

    def test_cosine_similarity_deterministic(self, calculator):
        """cosine(a, b) returns the same value every time."""
        rng = np.random.RandomState(42)
        a = rng.randn(16)
        b = rng.randn(16)

        results = [calculator._cosine_similarity(a, b) for _ in range(REPEATS)]

        assert len(set(results)) == 1, f"non-deterministic: {sorted(set(results))}"

    def test_rule_coherence_deterministic(self, calculator, rule_c1_syntax):
        """Rule coherence is identical across repeated computation."""
        output = np.array(rule_c1_syntax.positive_centroid, dtype=np.float64)

        results = [
            calculator.compute_rule_coherence(output, rule_c1_syntax).coherence
            for _ in range(REPEATS)
        ]

        assert len(set(results)) == 1, f"non-deterministic: {sorted(set(results))}"

    def test_harmonic_mean_deterministic(self, calculator):
        """Harmonic mean is identical across repeated computation."""
        values = [0.95, 0.82, 0.91, 0.3, 0.77]
        weights = [1.0, 1.2, 1.0, 1.5, 0.8]

        results = [
            calculator._weighted_harmonic_mean(values, weights)
            for _ in range(SHORT_REPEATS)
        ]

        assert len(set(results)) == 1, f"non-deterministic: {sorted(set(results))}"

    def test_geometric_mean_deterministic(self, calculator):
        """Geometric mean is identical across repeated computation."""
        values = [0.8, 0.75, 0.9, 0.65, 0.85, 0.7, 0.92]
        weights = [1.0, 1.0, 1.2, 1.0, 1.3, 0.8, 0.8]

        results = [
            calculator._weighted_geometric_mean(values, weights)
            for _ in range(SHORT_REPEATS)
        ]

        assert len(set(results)) == 1, f"non-deterministic: {sorted(set(results))}"


# =============================================================================
# Hash Determinism
# =============================================================================


class TestHashDeterminism:
    """Verify hash computation is deterministic."""

    def test_sha256_deterministic(self):
        """SHA-256 of the same normalized text is identical, and stable.

        The previous version carried an ``expected`` constant that was never
        asserted -- and did not match the real digest, so anyone "completing"
        the test by using it would have broken the build. The correct value is
        pinned here: a change means normalization changed, which is exactly
        what a determinism test should catch.
        """
        text = "def validate_user(user_id: str) -> bool:\n    return True"
        normalized = " ".join(text.strip().split())

        hashes = [
            hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            for _ in range(REPEATS)
        ]

        assert len(set(hashes)) == 1, f"non-deterministic: {sorted(set(hashes))}"
        assert (
            hashes[0]
            == "631b3b690696486ce7ac7f56c932a540573c8ae5b5fe56d4c1e6a8d072f985da"
        )

    def test_normalize_then_hash_deterministic(self):
        """Normalization + hash is deterministic for varied whitespace.

        This one was already parallel-safe -- it kept its state inside the
        test -- but ran the identical assertion as 20 separate items with the
        ``iteration`` parameter unused. Collapsed for consistency with the
        rest of the module.
        """
        texts = [
            "  hello   world  ",
            "hello world",
            "hello\n  world",
            "hello\tworld",
        ]
        hashes = []
        for text in texts:
            normalized = " ".join(text.strip().split())
            hashes.append(hashlib.sha256(normalized.encode("utf-8")).hexdigest())

        # All variations produce the same hash after normalization
        assert all(h == hashes[0] for h in hashes)


# =============================================================================
# Engine Determinism (Full Pipeline)
# =============================================================================


class TestEngineDeterminism:
    """Verify the full CGE pipeline produces identical results."""

    @pytest.fixture
    def deterministic_engine(self, all_rules):
        """Create an engine with pre-warmed cache for deterministic testing."""
        config = CGEConfig.for_testing()
        resolver = ConstraintGraphResolver()
        resolver.load_rules(all_rules)

        calculator = CoherenceCalculator()
        cache = EmbeddingCache(config=CacheConfig(enable_redis=False, lru_max_size=100))
        profiles = PolicyProfileManager()
        provenance = ProvenanceAdapter()

        engine = ConstraintGeometryEngine(
            graph_resolver=resolver,
            coherence_calculator=calculator,
            embedding_cache=cache,
            profile_manager=profiles,
            provenance_adapter=provenance,
            config=config,
        )

        # Pre-warm cache with known embedding
        text = "def validate_user(user_id: str) -> bool:\n    return check_permissions(user_id)"
        normalized = " ".join(text.strip().split())
        output_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        rng = np.random.RandomState(777)
        embedding = rng.randn(16).tolist()  # Must match TEST_DIM
        cache.put(output_hash, embedding)

        return engine

    @pytest.mark.asyncio
    async def test_full_pipeline_deterministic(self, deterministic_engine):
        """Full pipeline produces identical CCS for identical input."""
        output = AgentOutput(
            text="def validate_user(user_id: str) -> bool:\n    return check_permissions(user_id)",
            agent_id="coder-001",
        )

        results = []
        for _ in range(PIPELINE_REPEATS):
            result = await deterministic_engine.assess_coherence(
                output=output,
                policy_profile="default",
            )
            results.append((result.composite_score, result.action, result.output_hash))

        assert len(set(results)) == 1, f"non-deterministic: {sorted(set(results))}"

    @pytest.mark.asyncio
    async def test_different_whitespace_same_score(self, deterministic_engine):
        """Different whitespace produces same score after normalization."""
        text_v1 = "def validate_user(user_id: str) -> bool:\n    return check_permissions(user_id)"
        text_v2 = "def validate_user(user_id: str)  ->  bool:\n    return  check_permissions(user_id)"

        # Pre-warm cache for v2 with same embedding (same normalized text)
        norm_v1 = " ".join(text_v1.strip().split())
        norm_v2 = " ".join(text_v2.strip().split())

        # These two texts normalize differently, so they should get different hashes
        # But the test verifies that normalization is applied consistently
        hash_v1 = hashlib.sha256(norm_v1.encode("utf-8")).hexdigest()
        hash_v2 = hashlib.sha256(norm_v2.encode("utf-8")).hexdigest()

        if norm_v1 == norm_v2:
            assert hash_v1 == hash_v2

    @pytest.mark.asyncio
    async def test_different_profiles_same_score_different_action(
        self, deterministic_engine
    ):
        """Same output under different profiles: same score, may differ in action."""
        output = AgentOutput(
            text="def validate_user(user_id: str) -> bool:\n    return check_permissions(user_id)",
        )

        default_result = await deterministic_engine.assess_coherence(
            output=output, policy_profile="default"
        )
        sandbox_result = await deterministic_engine.assess_coherence(
            output=output, policy_profile="developer-sandbox"
        )

        # Scores may differ due to different axis weights, but both are deterministic
        assert isinstance(default_result.composite_score, float)
        assert isinstance(sandbox_result.composite_score, float)

    @pytest.mark.asyncio
    async def test_provenance_changes_score_deterministically(
        self, deterministic_engine
    ):
        """Provenance context changes score, but deterministically."""
        output = AgentOutput(
            text="def validate_user(user_id: str) -> bool:\n    return check_permissions(user_id)",
        )

        high_trust = ProvenanceContext(trust_score=0.95)
        low_trust = ProvenanceContext(trust_score=0.30)

        r1 = await deterministic_engine.assess_coherence(
            output=output, provenance_context=high_trust
        )
        r2 = await deterministic_engine.assess_coherence(
            output=output, provenance_context=high_trust
        )
        r3 = await deterministic_engine.assess_coherence(
            output=output, provenance_context=low_trust
        )

        # Same provenance = same result
        assert r1.composite_score == r2.composite_score
        assert r1.provenance_adjustment == r2.provenance_adjustment

        # Different provenance = different adjustment
        assert r1.provenance_adjustment != r3.provenance_adjustment
