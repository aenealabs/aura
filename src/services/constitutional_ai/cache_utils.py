"""Cache utilities for Constitutional AI Phase 3 optimization.

This module provides cache key generation functions for critique and revision
results, enabling semantic caching integration as specified in ADR-063 Phase 3.

Cache keys are designed to be:
- Deterministic: Same inputs always produce same key
- Collision-resistant: Different logical operations produce different keys
- Efficient: Truncates large outputs to maintain reasonable key sizes
"""

import hashlib
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.services.constitutional_ai.models import (
        ConstitutionalContext,
        CritiqueResult,
    )


# Maximum output length to include in cache key (for efficiency)
MAX_OUTPUT_LENGTH_FOR_CACHE = 2000


def generate_critique_cache_key(
    output: str,
    principle_ids: List[str],
    context: Optional["ConstitutionalContext"] = None,
) -> str:
    """Generate deterministic cache key for critique results.

    The cache key uniquely identifies a critique operation based on:
    - The agent output being critiqued (truncated for efficiency)
    - The specific principles being evaluated
    - The agent context (agent name, operation type)

    Args:
        output: The agent output being critiqued
        principle_ids: List of principle IDs being evaluated
        context: Optional context with agent and operation info

    Returns:
        SHA-256 hash string (64 characters) suitable as cache key

    Example:
        >>> key = generate_critique_cache_key(
        ...     output="def foo(): pass",
        ...     principle_ids=["principle_1_security_first", "principle_2_data_protection"],
        ...     context=ConstitutionalContext(agent_name="CoderAgent", operation_type="code_gen"),
        ... )
        >>> len(key)
        64
    """
    # Truncate output for efficiency
    truncated_output = output[:MAX_OUTPUT_LENGTH_FOR_CACHE]

    # Sort principle IDs for determinism
    sorted_principles = sorted(principle_ids)

    # Build cache key components
    components = [
        "critique",  # Operation type prefix
        truncated_output,
        "|".join(sorted_principles),
    ]

    # Add context components if available
    if context:
        components.extend(
            [
                context.agent_name,
                context.operation_type,
                "|".join(sorted(context.domain_tags)),
            ]
        )

    # Generate hash
    cache_string = "::".join(components)
    return hashlib.sha256(cache_string.encode("utf-8")).hexdigest()


def generate_revision_cache_key(
    output: str,
    critique_ids: List[str],
    context: Optional["ConstitutionalContext"] = None,
) -> str:
    """Generate deterministic cache key for revision results.

    The cache key uniquely identifies a revision operation based on:
    - The original output being revised
    - The critique IDs that triggered revision
    - The agent context

    Revision caching is more aggressive than critique caching because
    the same output with the same critique findings will typically
    result in similar revisions.

    Args:
        output: The original output being revised
        critique_ids: List of critique result IDs or principle violation IDs
        context: Optional context with agent and operation info

    Returns:
        SHA-256 hash string (64 characters) suitable as cache key

    Example:
        >>> key = generate_revision_cache_key(
        ...     output="insecure code here",
        ...     critique_ids=["crit_001", "crit_002"],
        ...     context=ConstitutionalContext(agent_name="CoderAgent", operation_type="patch"),
        ... )
        >>> len(key)
        64
    """
    # Truncate output for efficiency
    truncated_output = output[:MAX_OUTPUT_LENGTH_FOR_CACHE]

    # Sort critique IDs for determinism
    sorted_critiques = sorted(critique_ids)

    # Build cache key components
    components = [
        "revision",  # Operation type prefix
        truncated_output,
        "|".join(sorted_critiques),
    ]

    # Add context components if available
    if context:
        components.extend(
            [
                context.agent_name,
                context.operation_type,
                "|".join(sorted(context.domain_tags)),
            ]
        )

    # Generate hash
    cache_string = "::".join(components)
    return hashlib.sha256(cache_string.encode("utf-8")).hexdigest()


def generate_principle_batch_cache_key(
    output: str,
    principle_batch: List[str],
    batch_index: int,
    context: Optional["ConstitutionalContext"] = None,
) -> str:
    """Generate cache key for a single batch of principle evaluations.

    Used when caching individual batch results within a larger critique
    operation. This enables more granular caching when only some batches
    are cacheable.

    Args:
        output: The agent output being critiqued
        principle_batch: Principle IDs in this specific batch
        batch_index: Index of this batch in the overall evaluation
        context: Optional context with agent and operation info

    Returns:
        SHA-256 hash string (64 characters) suitable as cache key
    """
    # Truncate output for efficiency
    truncated_output = output[:MAX_OUTPUT_LENGTH_FOR_CACHE]

    # Sort principles within batch for determinism
    sorted_principles = sorted(principle_batch)

    # Build cache key components
    components = [
        "batch_critique",
        truncated_output,
        "|".join(sorted_principles),
        str(batch_index),
    ]

    if context:
        components.extend(
            [
                context.agent_name,
                context.operation_type,
            ]
        )

    cache_string = "::".join(components)
    return hashlib.sha256(cache_string.encode("utf-8")).hexdigest()


def generate_critique_summary_cache_key(
    output_hash: str,
    principle_count: int,
    agent_name: str,
    operation_type: str,
) -> str:
    """Generate simplified cache key for critique summary lookup.

    This is a faster cache key generation for when the full output
    has already been hashed, useful for distributed caching scenarios.

    Args:
        output_hash: Pre-computed hash of the output
        principle_count: Number of principles being evaluated
        agent_name: Name of the evaluating agent
        operation_type: Type of operation being performed

    Returns:
        SHA-256 hash string (64 characters) suitable as cache key
    """
    components = [
        "summary",
        output_hash,
        str(principle_count),
        agent_name,
        operation_type,
    ]

    cache_string = "::".join(components)
    return hashlib.sha256(cache_string.encode("utf-8")).hexdigest()


def critique_results_to_cache_ids(critiques: List["CritiqueResult"]) -> List[str]:
    """Extract cache-relevant IDs from critique results.

    Converts a list of CritiqueResult objects into a list of string IDs
    suitable for use in cache key generation.

    Args:
        critiques: List of CritiqueResult objects

    Returns:
        List of string IDs combining principle ID and pass/fail status
    """
    ids = []
    for critique in critiques:
        # Include both principle ID and pass status for cache differentiation
        status = "pass" if critique.passed else "fail"
        ids.append(f"{critique.principle_id}:{status}")
    return ids


def hash_output_for_cache(output: str) -> str:
    """Generate a short hash of output for cache key components.

    Creates a truncated hash suitable for use in composite cache keys
    or as a lookup index.

    Args:
        output: The output to hash

    Returns:
        16-character hexadecimal hash
    """
    truncated = output[:MAX_OUTPUT_LENGTH_FOR_CACHE]
    full_hash = hashlib.sha256(truncated.encode("utf-8")).hexdigest()
    return full_hash[:16]
