"""Unit tests for Constitutional AI cache utilities.

Tests cache key generation functions for determinism, collision resistance,
and proper handling of edge cases.
"""

from unittest.mock import MagicMock

import pytest

from src.services.constitutional_ai.cache_utils import (
    MAX_OUTPUT_LENGTH_FOR_CACHE,
    critique_results_to_cache_ids,
    generate_critique_cache_key,
    generate_critique_summary_cache_key,
    generate_principle_batch_cache_key,
    generate_revision_cache_key,
    hash_output_for_cache,
)
from src.services.constitutional_ai.models import ConstitutionalContext

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_context():
    """Create sample ConstitutionalContext for testing."""
    return ConstitutionalContext(
        agent_name="TestAgent",
        operation_type="code_generation",
        user_request="Generate a function",
        domain_tags=["security", "testing"],
    )


@pytest.fixture
def sample_context_no_tags():
    """Create ConstitutionalContext without domain tags."""
    return ConstitutionalContext(
        agent_name="TestAgent",
        operation_type="code_generation",
    )


# =============================================================================
# Test generate_critique_cache_key
# =============================================================================


class TestGenerateCritiqueCacheKey:
    """Tests for generate_critique_cache_key function."""

    def test_produces_64_char_hash(self):
        """Cache key should be a 64-character SHA-256 hash."""
        key = generate_critique_cache_key(
            output="def foo(): pass",
            principle_ids=["principle_1"],
        )
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_deterministic_same_inputs(self):
        """Same inputs should always produce the same key."""
        output = "def process(): return 42"
        principles = ["principle_1_security_first", "principle_2_data_protection"]

        key1 = generate_critique_cache_key(output, principles)
        key2 = generate_critique_cache_key(output, principles)

        assert key1 == key2

    def test_principle_order_irrelevant(self):
        """Principle order should not affect cache key (sorted internally)."""
        output = "def foo(): pass"
        principles_a = ["principle_2", "principle_1", "principle_3"]
        principles_b = ["principle_1", "principle_3", "principle_2"]

        key_a = generate_critique_cache_key(output, principles_a)
        key_b = generate_critique_cache_key(output, principles_b)

        assert key_a == key_b

    def test_different_outputs_different_keys(self):
        """Different outputs should produce different keys."""
        principles = ["principle_1"]

        key_a = generate_critique_cache_key("output A", principles)
        key_b = generate_critique_cache_key("output B", principles)

        assert key_a != key_b

    def test_different_principles_different_keys(self):
        """Different principle sets should produce different keys."""
        output = "def foo(): pass"

        key_a = generate_critique_cache_key(output, ["principle_1"])
        key_b = generate_critique_cache_key(output, ["principle_2"])

        assert key_a != key_b

    def test_with_context(self, sample_context):
        """Keys should incorporate context when provided."""
        output = "def foo(): pass"
        principles = ["principle_1"]

        key_no_context = generate_critique_cache_key(output, principles)
        key_with_context = generate_critique_cache_key(
            output, principles, sample_context
        )

        assert key_no_context != key_with_context

    def test_different_context_different_keys(self, sample_context):
        """Different contexts should produce different keys."""
        output = "def foo(): pass"
        principles = ["principle_1"]

        other_context = ConstitutionalContext(
            agent_name="OtherAgent",
            operation_type="review",
            domain_tags=["other"],
        )

        key_a = generate_critique_cache_key(output, principles, sample_context)
        key_b = generate_critique_cache_key(output, principles, other_context)

        assert key_a != key_b

    def test_truncates_long_output(self):
        """Long outputs should be truncated for efficiency."""
        short_output = "x" * 100
        long_output = "x" * (MAX_OUTPUT_LENGTH_FOR_CACHE + 1000)

        # Both should produce same key when first MAX_OUTPUT_LENGTH chars are same
        principles = ["principle_1"]
        key_short = generate_critique_cache_key(short_output, principles)
        key_long = generate_critique_cache_key(long_output, principles)

        # They differ because short_output has fewer x's
        assert key_short != key_long

        # But two long outputs with same prefix should match
        long_a = "y" * (MAX_OUTPUT_LENGTH_FOR_CACHE + 500)
        long_b = "y" * (MAX_OUTPUT_LENGTH_FOR_CACHE + 2000)
        key_long_a = generate_critique_cache_key(long_a, principles)
        key_long_b = generate_critique_cache_key(long_b, principles)

        assert key_long_a == key_long_b

    def test_empty_principles_list(self):
        """Should handle empty principles list."""
        key = generate_critique_cache_key("output", [])
        assert len(key) == 64

    def test_empty_output(self):
        """Should handle empty output string."""
        key = generate_critique_cache_key("", ["principle_1"])
        assert len(key) == 64


# =============================================================================
# Test generate_revision_cache_key
# =============================================================================


class TestGenerateRevisionCacheKey:
    """Tests for generate_revision_cache_key function."""

    def test_produces_64_char_hash(self):
        """Cache key should be a 64-character SHA-256 hash."""
        key = generate_revision_cache_key(
            output="insecure code",
            critique_ids=["crit_001"],
        )
        assert len(key) == 64

    def test_deterministic(self):
        """Same inputs should always produce the same key."""
        output = "code with issues"
        critique_ids = ["crit_001", "crit_002"]

        key1 = generate_revision_cache_key(output, critique_ids)
        key2 = generate_revision_cache_key(output, critique_ids)

        assert key1 == key2

    def test_critique_order_irrelevant(self):
        """Critique ID order should not affect cache key."""
        output = "code"
        ids_a = ["crit_002", "crit_001"]
        ids_b = ["crit_001", "crit_002"]

        assert generate_revision_cache_key(
            output, ids_a
        ) == generate_revision_cache_key(output, ids_b)

    def test_different_from_critique_key(self):
        """Revision key should differ from critique key with same inputs."""
        output = "code"
        ids = ["principle_1"]

        critique_key = generate_critique_cache_key(output, ids)
        revision_key = generate_revision_cache_key(output, ids)

        assert critique_key != revision_key

    def test_with_context(self, sample_context):
        """Keys should incorporate context when provided."""
        output = "code"
        ids = ["crit_001"]

        key_no_context = generate_revision_cache_key(output, ids)
        key_with_context = generate_revision_cache_key(output, ids, sample_context)

        assert key_no_context != key_with_context


# =============================================================================
# Test generate_principle_batch_cache_key
# =============================================================================


class TestGeneratePrincipleBatchCacheKey:
    """Tests for generate_principle_batch_cache_key function."""

    def test_produces_64_char_hash(self):
        """Cache key should be a 64-character SHA-256 hash."""
        key = generate_principle_batch_cache_key(
            output="code",
            principle_batch=["p1", "p2"],
            batch_index=0,
        )
        assert len(key) == 64

    def test_different_batches_different_keys(self):
        """Different batch indices should produce different keys."""
        output = "code"
        batch = ["p1", "p2"]

        key_0 = generate_principle_batch_cache_key(output, batch, 0)
        key_1 = generate_principle_batch_cache_key(output, batch, 1)

        assert key_0 != key_1

    def test_same_batch_different_principles(self):
        """Different principle batches should produce different keys."""
        output = "code"

        key_a = generate_principle_batch_cache_key(output, ["p1", "p2"], 0)
        key_b = generate_principle_batch_cache_key(output, ["p1", "p3"], 0)

        assert key_a != key_b


# =============================================================================
# Test generate_critique_summary_cache_key
# =============================================================================


class TestGenerateCritiqueSummaryCacheKey:
    """Tests for generate_critique_summary_cache_key function."""

    def test_produces_64_char_hash(self):
        """Cache key should be a 64-character SHA-256 hash."""
        key = generate_critique_summary_cache_key(
            output_hash="abc123",
            principle_count=5,
            agent_name="TestAgent",
            operation_type="review",
        )
        assert len(key) == 64

    def test_deterministic(self):
        """Same inputs should produce same key."""
        args = ("hash", 5, "Agent", "review")

        key1 = generate_critique_summary_cache_key(*args)
        key2 = generate_critique_summary_cache_key(*args)

        assert key1 == key2

    def test_different_counts_different_keys(self):
        """Different principle counts should produce different keys."""
        key_5 = generate_critique_summary_cache_key("hash", 5, "Agent", "review")
        key_10 = generate_critique_summary_cache_key("hash", 10, "Agent", "review")

        assert key_5 != key_10


# =============================================================================
# Test critique_results_to_cache_ids
# =============================================================================


class TestCritiqueResultsToCacheIds:
    """Tests for critique_results_to_cache_ids function."""

    def test_extracts_ids_with_status(self):
        """Should extract principle IDs with pass/fail status."""
        # Create mock critique results
        crit_pass = MagicMock()
        crit_pass.principle_id = "principle_1"
        crit_pass.passed = True

        crit_fail = MagicMock()
        crit_fail.principle_id = "principle_2"
        crit_fail.passed = False

        ids = critique_results_to_cache_ids([crit_pass, crit_fail])

        assert "principle_1:pass" in ids
        assert "principle_2:fail" in ids

    def test_empty_list(self):
        """Should handle empty critique list."""
        ids = critique_results_to_cache_ids([])
        assert ids == []


# =============================================================================
# Test hash_output_for_cache
# =============================================================================


class TestHashOutputForCache:
    """Tests for hash_output_for_cache function."""

    def test_produces_16_char_hash(self):
        """Should produce a 16-character truncated hash."""
        hash_val = hash_output_for_cache("some output")
        assert len(hash_val) == 16
        assert all(c in "0123456789abcdef" for c in hash_val)

    def test_deterministic(self):
        """Same input should produce same hash."""
        hash1 = hash_output_for_cache("test output")
        hash2 = hash_output_for_cache("test output")

        assert hash1 == hash2

    def test_different_outputs_different_hashes(self):
        """Different outputs should produce different hashes."""
        hash_a = hash_output_for_cache("output A")
        hash_b = hash_output_for_cache("output B")

        assert hash_a != hash_b

    def test_truncates_long_input(self):
        """Long outputs should be truncated before hashing."""
        long_same_prefix = "x" * MAX_OUTPUT_LENGTH_FOR_CACHE
        longer = long_same_prefix + "extra content"

        hash_short = hash_output_for_cache(long_same_prefix)
        hash_long = hash_output_for_cache(longer)

        assert hash_short == hash_long
