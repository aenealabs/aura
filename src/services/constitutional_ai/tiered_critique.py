"""Tiered critique strategy for Constitutional AI Phase 3.

Maps autonomy levels to principle subsets for efficient evaluation as specified
in ADR-063 Phase 3 (Optimization).

Tiers reduce evaluation overhead based on autonomy level:
- FULL: All 16 principles (high-risk scenarios)
- STANDARD: All 16 principles (default collaborative mode)
- REDUCED: CRITICAL + HIGH only (7 principles, limited autonomy)
- MINIMAL: CRITICAL only (3 principles, human reviews anyway)

This optimization reduces latency by 30-50% for certain autonomy levels
while maintaining security guarantees for CRITICAL principles.
"""

from enum import Enum
from typing import Dict, List, Optional, Set

from src.services.constitutional_ai.models import PrincipleSeverity


class CritiqueTier(Enum):
    """Critique depth tiers for constitutional evaluation.

    Each tier defines a subset of principles to evaluate:
    - FULL: Complete principle set (16 principles)
    - STANDARD: Complete principle set (same as FULL)
    - REDUCED: High-priority subset (CRITICAL + HIGH, 7 principles)
    - MINIMAL: Safety-critical only (CRITICAL, 3 principles)
    """

    FULL = "full"
    STANDARD = "standard"
    REDUCED = "reduced"
    MINIMAL = "minimal"


# Autonomy level to critique tier mapping
# Based on ADR-032 Configurable Autonomy Framework
AUTONOMY_TO_CRITIQUE_TIER: Dict[str, CritiqueTier] = {
    # Full autonomy: When actually invoked, use full critique
    "FULL_AUTONOMOUS": CritiqueTier.FULL,
    # Limited autonomy: Only evaluate CRITICAL + HIGH principles
    "LIMITED_AUTONOMOUS": CritiqueTier.REDUCED,
    # Collaborative mode: Standard full evaluation
    "COLLABORATIVE": CritiqueTier.STANDARD,
    # Full HITL: Minimal critique, human reviews anyway
    "FULL_HITL": CritiqueTier.MINIMAL,
}

# Principle IDs by tier
# CRITICAL principles (safety): 1, 2, 3
# HIGH principles (compliance, anti-sycophancy, meta): 4, 5, 10, 16
# MEDIUM principles: 6, 7, 8, 9, 11
# LOW principles: 12, 13, 14, 15
PRINCIPLES_BY_TIER: Dict[CritiqueTier, Optional[List[str]]] = {
    # All principles (None means no filtering)
    CritiqueTier.FULL: None,
    CritiqueTier.STANDARD: None,
    # CRITICAL (1-3) + HIGH (4, 5, 10, 16)
    CritiqueTier.REDUCED: [
        "principle_1_security_first",
        "principle_2_data_protection",
        "principle_3_sandbox_isolation",
        "principle_4_regulatory_compliance",
        "principle_5_audit_trail",
        "principle_10_independent_judgment",
        "principle_16_conflict_resolution",
    ],
    # CRITICAL only (1-3)
    CritiqueTier.MINIMAL: [
        "principle_1_security_first",
        "principle_2_data_protection",
        "principle_3_sandbox_isolation",
    ],
}

# Severities included in each tier
SEVERITIES_BY_TIER: Dict[CritiqueTier, Set[PrincipleSeverity]] = {
    CritiqueTier.FULL: {
        PrincipleSeverity.CRITICAL,
        PrincipleSeverity.HIGH,
        PrincipleSeverity.MEDIUM,
        PrincipleSeverity.LOW,
    },
    CritiqueTier.STANDARD: {
        PrincipleSeverity.CRITICAL,
        PrincipleSeverity.HIGH,
        PrincipleSeverity.MEDIUM,
        PrincipleSeverity.LOW,
    },
    CritiqueTier.REDUCED: {
        PrincipleSeverity.CRITICAL,
        PrincipleSeverity.HIGH,
    },
    CritiqueTier.MINIMAL: {
        PrincipleSeverity.CRITICAL,
    },
}


def get_critique_tier(autonomy_level: Optional[str]) -> CritiqueTier:
    """Get the critique tier for a given autonomy level.

    Args:
        autonomy_level: Autonomy level string (e.g., "COLLABORATIVE", "FULL_HITL")
                       If None or unrecognized, defaults to STANDARD

    Returns:
        CritiqueTier enum value determining which principles to evaluate

    Example:
        >>> get_critique_tier("FULL_HITL")
        CritiqueTier.MINIMAL
        >>> get_critique_tier("LIMITED_AUTONOMOUS")
        CritiqueTier.REDUCED
        >>> get_critique_tier(None)
        CritiqueTier.STANDARD
    """
    if autonomy_level is None:
        return CritiqueTier.STANDARD

    return AUTONOMY_TO_CRITIQUE_TIER.get(autonomy_level.upper(), CritiqueTier.STANDARD)


def get_principles_for_tier(tier: CritiqueTier) -> Optional[List[str]]:
    """Get the list of principle IDs to evaluate for a given tier.

    Args:
        tier: CritiqueTier enum value

    Returns:
        List of principle IDs to evaluate, or None if all principles should
        be evaluated

    Example:
        >>> get_principles_for_tier(CritiqueTier.MINIMAL)
        ['principle_1_security_first', 'principle_2_data_protection', 'principle_3_sandbox_isolation']
        >>> get_principles_for_tier(CritiqueTier.FULL)
        None
    """
    return PRINCIPLES_BY_TIER.get(tier)


def get_severities_for_tier(tier: CritiqueTier) -> Set[PrincipleSeverity]:
    """Get the set of severities to evaluate for a given tier.

    This is useful for filtering principles by severity when the principle
    IDs aren't known ahead of time.

    Args:
        tier: CritiqueTier enum value

    Returns:
        Set of PrincipleSeverity values included in this tier

    Example:
        >>> get_severities_for_tier(CritiqueTier.REDUCED)
        {PrincipleSeverity.CRITICAL, PrincipleSeverity.HIGH}
    """
    return SEVERITIES_BY_TIER.get(tier, SEVERITIES_BY_TIER[CritiqueTier.STANDARD])


def filter_principles_by_tier(
    all_principle_ids: List[str],
    tier: CritiqueTier,
) -> List[str]:
    """Filter a list of principle IDs to only those included in a tier.

    Args:
        all_principle_ids: Full list of principle IDs to filter
        tier: CritiqueTier to filter against

    Returns:
        Filtered list of principle IDs included in the tier

    Example:
        >>> all_ids = ["principle_1_security_first", "principle_12_maintainability"]
        >>> filter_principles_by_tier(all_ids, CritiqueTier.MINIMAL)
        ['principle_1_security_first']
    """
    tier_principles = get_principles_for_tier(tier)

    # If tier includes all principles, return unfiltered
    if tier_principles is None:
        return all_principle_ids

    # Filter to only included principles
    tier_set = set(tier_principles)
    return [pid for pid in all_principle_ids if pid in tier_set]


def get_tier_description(tier: CritiqueTier) -> str:
    """Get a human-readable description of a critique tier.

    Args:
        tier: CritiqueTier enum value

    Returns:
        Description string suitable for logging or display
    """
    descriptions = {
        CritiqueTier.FULL: "Full evaluation (all 16 principles)",
        CritiqueTier.STANDARD: "Standard evaluation (all 16 principles)",
        CritiqueTier.REDUCED: "Reduced evaluation (CRITICAL + HIGH, 7 principles)",
        CritiqueTier.MINIMAL: "Minimal evaluation (CRITICAL only, 3 principles)",
    }
    return descriptions.get(tier, "Unknown tier")


def calculate_tier_efficiency(tier: CritiqueTier) -> float:
    """Calculate the relative efficiency of a tier vs full evaluation.

    Returns the ratio of principles skipped, useful for cost estimation.

    Args:
        tier: CritiqueTier enum value

    Returns:
        Float between 0.0 and 1.0 representing efficiency gain.
        0.0 = no efficiency gain (full evaluation)
        Higher = more principles skipped

    Example:
        >>> calculate_tier_efficiency(CritiqueTier.MINIMAL)
        0.8125  # (16-3)/16 = 81.25% of principles skipped
    """
    total_principles = 16

    tier_principles = get_principles_for_tier(tier)
    if tier_principles is None:
        return 0.0

    principles_evaluated = len(tier_principles)
    principles_skipped = total_principles - principles_evaluated
    return principles_skipped / total_principles
