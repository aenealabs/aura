"""
Project Aura - CGE Test Fixtures

Shared fixtures for Constraint Geometry Engine tests.
Provides pre-built constraint rules, embeddings, profiles, and engine instances.

Author: Project Aura Team
Created: 2026-02-11
"""

import numpy as np
import pytest

from src.services.constraint_geometry.coherence_calculator import CoherenceCalculator
from src.services.constraint_geometry.config import CGEConfig
from src.services.constraint_geometry.constraint_graph import ConstraintGraphResolver
from src.services.constraint_geometry.contracts import (
    AgentOutput,
    ConstraintAxis,
    ConstraintRule,
    ProvenanceContext,
)
from src.services.constraint_geometry.embedding_cache import EmbeddingCache
from src.services.constraint_geometry.engine import ConstraintGeometryEngine
from src.services.constraint_geometry.policy_profile import PolicyProfileManager
from src.services.constraint_geometry.provenance_adapter import ProvenanceAdapter

# Dimension for test embeddings (smaller than production 1024 for speed)
TEST_DIM = 16


def _make_unit_vector(seed: int, dim: int = TEST_DIM) -> tuple[float, ...]:
    """Create a deterministic unit vector from seed."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim)
    vec = vec / np.linalg.norm(vec)
    return tuple(vec.tolist())


def _make_similar_vector(
    base: tuple[float, ...], similarity: float = 0.9, seed: int = 42
) -> tuple[float, ...]:
    """Create a vector with approximate cosine similarity to base."""
    rng = np.random.RandomState(seed)
    base_arr = np.array(base)
    noise = rng.randn(len(base))
    noise = noise / np.linalg.norm(noise)
    # Linear interpolation between base and random direction
    mixed = similarity * base_arr + (1 - similarity) * noise
    mixed = mixed / np.linalg.norm(mixed)
    return tuple(mixed.tolist())


# =============================================================================
# Embedding Fixtures
# =============================================================================


@pytest.fixture
def positive_centroid_c1():
    """Positive centroid for C1 (Syntactic Validity)."""
    return _make_unit_vector(seed=101)


@pytest.fixture
def negative_centroid_c1():
    """Negative centroid for C1 (Syntactic Validity)."""
    return _make_unit_vector(seed=201)


@pytest.fixture
def positive_centroid_c3():
    """Positive centroid for C3 (Security Policy)."""
    return _make_unit_vector(seed=103)


@pytest.fixture
def negative_centroid_c3():
    """Negative centroid for C3 (Security Policy)."""
    return _make_unit_vector(seed=203)


@pytest.fixture
def high_coherence_embedding(positive_centroid_c1):
    """Embedding that is highly similar to C1 positive centroid."""
    return list(_make_similar_vector(positive_centroid_c1, similarity=0.95, seed=300))


@pytest.fixture
def low_coherence_embedding(negative_centroid_c1):
    """Embedding that is highly similar to C1 negative centroid."""
    return list(_make_similar_vector(negative_centroid_c1, similarity=0.95, seed=301))


@pytest.fixture
def neutral_embedding():
    """Embedding equidistant from positive and negative centroids."""
    return list(_make_unit_vector(seed=999))


# =============================================================================
# Constraint Rule Fixtures
# =============================================================================


@pytest.fixture
def rule_c1_syntax(positive_centroid_c1, negative_centroid_c1):
    """C1: Syntactic Validity rule."""
    return ConstraintRule(
        rule_id="c1-syntax-001",
        axis=ConstraintAxis.SYNTACTIC_VALIDITY,
        name="AST Parse Check",
        description="Code must parse into valid AST",
        positive_centroid=positive_centroid_c1,
        negative_centroid=negative_centroid_c1,
        boundary_threshold=0.5,
        weight=1.0,
        version="1.0.0",
    )


@pytest.fixture
def rule_c1_types(positive_centroid_c1, negative_centroid_c1):
    """C1: Type check rule."""
    return ConstraintRule(
        rule_id="c1-types-001",
        axis=ConstraintAxis.SYNTACTIC_VALIDITY,
        name="Type Consistency",
        description="Type annotations must be consistent",
        positive_centroid=_make_unit_vector(seed=102),
        negative_centroid=_make_unit_vector(seed=202),
        boundary_threshold=0.5,
        weight=0.8,
        version="1.0.0",
    )


@pytest.fixture
def rule_c3_nist_ac6(positive_centroid_c3, negative_centroid_c3):
    """C3: NIST AC-6 Least Privilege rule."""
    return ConstraintRule(
        rule_id="c3-nist-ac6-001",
        axis=ConstraintAxis.SECURITY_POLICY,
        name="NIST AC-6 Least Privilege",
        description="IAM policies must follow least privilege",
        positive_centroid=positive_centroid_c3,
        negative_centroid=negative_centroid_c3,
        boundary_threshold=0.6,
        weight=1.2,
        version="1.0.0",
    )


@pytest.fixture
def rule_c3_wildcard():
    """C3: IAM Wildcard Prohibition rule."""
    return ConstraintRule(
        rule_id="c3-wildcard-001",
        axis=ConstraintAxis.SECURITY_POLICY,
        name="IAM Wildcard Prohibition",
        description="No wildcard resource ARNs in IAM policies",
        positive_centroid=_make_unit_vector(seed=104),
        negative_centroid=_make_unit_vector(seed=204),
        boundary_threshold=0.7,
        weight=1.5,
        version="1.0.0",
    )


@pytest.fixture
def rule_c5_sox():
    """C5: SOX Compliance rule."""
    return ConstraintRule(
        rule_id="c5-sox-001",
        axis=ConstraintAxis.DOMAIN_COMPLIANCE,
        name="SOX Data Handling",
        description="Financial data handling must comply with SOX",
        positive_centroid=_make_unit_vector(seed=105),
        negative_centroid=_make_unit_vector(seed=205),
        boundary_threshold=0.6,
        weight=1.0,
        version="1.0.0",
    )


@pytest.fixture
def all_rules(
    rule_c1_syntax, rule_c1_types, rule_c3_nist_ac6, rule_c3_wildcard, rule_c5_sox
):
    """All test constraint rules."""
    return [
        rule_c1_syntax,
        rule_c1_types,
        rule_c3_nist_ac6,
        rule_c3_wildcard,
        rule_c5_sox,
    ]


# =============================================================================
# Engine Component Fixtures
# =============================================================================


@pytest.fixture
def calculator():
    """CoherenceCalculator instance."""
    return CoherenceCalculator()


@pytest.fixture
def cache():
    """EmbeddingCache instance (no Redis, no provider)."""
    from src.services.constraint_geometry.config import CacheConfig

    return EmbeddingCache(config=CacheConfig(enable_redis=False, lru_max_size=100))


@pytest.fixture
def profile_manager():
    """PolicyProfileManager with built-in profiles."""
    return PolicyProfileManager()


@pytest.fixture
def provenance_adapter():
    """ProvenanceAdapter instance."""
    return ProvenanceAdapter(default_sensitivity=0.5)


@pytest.fixture
def graph_resolver(all_rules):
    """ConstraintGraphResolver pre-loaded with test rules."""
    resolver = ConstraintGraphResolver()
    resolver.load_rules(all_rules)
    return resolver


@pytest.fixture
def test_config():
    """CGEConfig for testing."""
    return CGEConfig.for_testing()


@pytest.fixture
def cge(
    graph_resolver, calculator, cache, profile_manager, provenance_adapter, test_config
):
    """Fully configured ConstraintGeometryEngine for testing."""
    return ConstraintGeometryEngine(
        graph_resolver=graph_resolver,
        coherence_calculator=calculator,
        embedding_cache=cache,
        profile_manager=profile_manager,
        provenance_adapter=provenance_adapter,
        config=test_config,
    )


# =============================================================================
# Agent Output Fixtures
# =============================================================================


@pytest.fixture
def sample_output():
    """Sample agent output for testing."""
    return AgentOutput(
        text="def validate_user(user_id: str) -> bool:\n    return check_permissions(user_id)",
        agent_id="coder-001",
        task_id="task-001",
        context={"repository": "aura-platform", "language": "python"},
    )


@pytest.fixture
def high_trust_provenance():
    """High trust provenance context."""
    return ProvenanceContext(
        trust_score=0.95,
        source="internal",
        verified=True,
        author="engineer@aenealabs.com",
        commit_signed=True,
    )


@pytest.fixture
def low_trust_provenance():
    """Low trust provenance context."""
    return ProvenanceContext(
        trust_score=0.3,
        source="external",
        verified=False,
        author="unknown",
        commit_signed=False,
    )
