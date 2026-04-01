"""
Project Aura - Policy Profile Manager

Manages named policy profiles that define per-axis constraint weights
and threshold boundaries for the CGE. Different operational contexts
(DoD-IL5, developer sandbox, SOX compliance) get appropriate tolerances.

Author: Project Aura Team
Created: 2026-02-11
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .contracts import CoherenceAction, ConstraintAxis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolicyThresholds:
    """Deterministic threshold boundaries for action determination.

    CCS >= auto_execute_threshold      -> AUTO_EXECUTE
    review_threshold <= CCS < auto     -> HUMAN_REVIEW
    escalate_threshold <= CCS < review -> ESCALATE
    CCS < escalate_threshold           -> REJECT
    """

    auto_execute_threshold: float = 0.80
    review_threshold: float = 0.55
    escalate_threshold: float = 0.30

    def determine_action(
        self,
        ccs: float,
        provenance_adjustment: float = 0.0,
    ) -> CoherenceAction:
        """Determine action from CCS score and provenance adjustment.

        Provenance adjustment raises thresholds for low-trust contexts,
        making auto-execution harder to achieve.
        """
        effective_auto = min(self.auto_execute_threshold + provenance_adjustment, 1.0)
        effective_review = min(
            self.review_threshold + (provenance_adjustment * 0.5), 1.0
        )

        if ccs >= effective_auto:
            return CoherenceAction.AUTO_EXECUTE
        elif ccs >= effective_review:
            return CoherenceAction.HUMAN_REVIEW
        elif ccs >= self.escalate_threshold:
            return CoherenceAction.ESCALATE
        else:
            return CoherenceAction.REJECT


@dataclass(frozen=True)
class PolicyProfile:
    """Named policy profile with per-axis weights and thresholds.

    Each profile represents an operational context. The axis weights
    control how much each constraint dimension contributes to the
    composite CCS. Thresholds control the action boundaries.
    """

    name: str
    description: str
    axis_weights: dict[ConstraintAxis, float]
    thresholds: PolicyThresholds
    provenance_sensitivity: float = 0.5  # How much trust score affects weights

    def get_axis_weight(self, axis: ConstraintAxis) -> float:
        """Get weight for a specific axis."""
        return self.axis_weights.get(axis, 1.0)

    def determine_action(
        self,
        ccs: float,
        provenance_adjustment: float = 0.0,
    ) -> CoherenceAction:
        """Determine action based on CCS and provenance."""
        return self.thresholds.determine_action(ccs, provenance_adjustment)


# =============================================================================
# Built-in Policy Profiles
# =============================================================================

DEFAULT_AXIS_WEIGHTS = {
    ConstraintAxis.SYNTACTIC_VALIDITY: 1.0,
    ConstraintAxis.SEMANTIC_CORRECTNESS: 1.0,
    ConstraintAxis.SECURITY_POLICY: 1.2,
    ConstraintAxis.OPERATIONAL_BOUNDS: 1.0,
    ConstraintAxis.DOMAIN_COMPLIANCE: 1.0,
    ConstraintAxis.PROVENANCE_TRUST: 0.8,
    ConstraintAxis.TEMPORAL_VALIDITY: 0.8,
}

PROFILE_DEFAULT = PolicyProfile(
    name="default",
    description="Standard operational profile for general use",
    axis_weights=DEFAULT_AXIS_WEIGHTS,
    thresholds=PolicyThresholds(
        auto_execute_threshold=0.80,
        review_threshold=0.55,
        escalate_threshold=0.30,
    ),
    provenance_sensitivity=0.5,
)

PROFILE_DOD_IL5 = PolicyProfile(
    name="dod-il5",
    description="DoD Impact Level 5 - maximum security constraints",
    axis_weights={
        ConstraintAxis.SYNTACTIC_VALIDITY: 1.0,
        ConstraintAxis.SEMANTIC_CORRECTNESS: 1.0,
        ConstraintAxis.SECURITY_POLICY: 1.5,  # Heavily weighted
        ConstraintAxis.OPERATIONAL_BOUNDS: 1.2,
        ConstraintAxis.DOMAIN_COMPLIANCE: 1.3,
        ConstraintAxis.PROVENANCE_TRUST: 1.2,
        ConstraintAxis.TEMPORAL_VALIDITY: 1.0,
    },
    thresholds=PolicyThresholds(
        auto_execute_threshold=0.92,
        review_threshold=0.75,
        escalate_threshold=0.50,
    ),
    provenance_sensitivity=0.8,
)

PROFILE_DEVELOPER_SANDBOX = PolicyProfile(
    name="developer-sandbox",
    description="Relaxed profile for sandbox experimentation",
    axis_weights={
        ConstraintAxis.SYNTACTIC_VALIDITY: 1.0,
        ConstraintAxis.SEMANTIC_CORRECTNESS: 0.8,
        ConstraintAxis.SECURITY_POLICY: 1.0,
        ConstraintAxis.OPERATIONAL_BOUNDS: 0.7,
        ConstraintAxis.DOMAIN_COMPLIANCE: 0.6,
        ConstraintAxis.PROVENANCE_TRUST: 0.5,
        ConstraintAxis.TEMPORAL_VALIDITY: 0.5,
    },
    thresholds=PolicyThresholds(
        auto_execute_threshold=0.60,
        review_threshold=0.35,
        escalate_threshold=0.15,
    ),
    provenance_sensitivity=0.2,
)

PROFILE_SOX_COMPLIANT = PolicyProfile(
    name="sox-compliant",
    description="SOX compliance profile for financial data operations",
    axis_weights={
        ConstraintAxis.SYNTACTIC_VALIDITY: 1.0,
        ConstraintAxis.SEMANTIC_CORRECTNESS: 1.2,
        ConstraintAxis.SECURITY_POLICY: 1.3,
        ConstraintAxis.OPERATIONAL_BOUNDS: 1.1,
        ConstraintAxis.DOMAIN_COMPLIANCE: 1.5,  # Heavily weighted
        ConstraintAxis.PROVENANCE_TRUST: 1.1,
        ConstraintAxis.TEMPORAL_VALIDITY: 1.2,
    },
    thresholds=PolicyThresholds(
        auto_execute_threshold=0.88,
        review_threshold=0.70,
        escalate_threshold=0.45,
    ),
    provenance_sensitivity=0.6,
)

# Registry of built-in profiles
_BUILTIN_PROFILES: dict[str, PolicyProfile] = {
    "default": PROFILE_DEFAULT,
    "dod-il5": PROFILE_DOD_IL5,
    "developer-sandbox": PROFILE_DEVELOPER_SANDBOX,
    "sox-compliant": PROFILE_SOX_COMPLIANT,
}


class PolicyProfileManager:
    """Manages policy profiles for the CGE.

    Provides access to built-in profiles and supports registration
    of custom profiles. Profiles are immutable once registered.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, PolicyProfile] = dict(_BUILTIN_PROFILES)

    def get(self, name: str) -> PolicyProfile:
        """Get a policy profile by name.

        Args:
            name: Profile name

        Returns:
            PolicyProfile

        Raises:
            KeyError: If profile not found
        """
        if name not in self._profiles:
            available = ", ".join(sorted(self._profiles.keys()))
            raise KeyError(f"Policy profile '{name}' not found. Available: {available}")
        return self._profiles[name]

    def register(self, profile: PolicyProfile) -> None:
        """Register a custom policy profile.

        Args:
            profile: PolicyProfile to register

        Raises:
            ValueError: If profile name conflicts with built-in
        """
        if profile.name in _BUILTIN_PROFILES:
            raise ValueError(f"Cannot override built-in profile '{profile.name}'")
        self._profiles[profile.name] = profile
        logger.info("Registered custom policy profile: %s", profile.name)

    def list_profiles(self) -> list[str]:
        """List all available profile names."""
        return sorted(self._profiles.keys())

    @property
    def builtin_profiles(self) -> list[str]:
        """List built-in profile names."""
        return sorted(_BUILTIN_PROFILES.keys())
