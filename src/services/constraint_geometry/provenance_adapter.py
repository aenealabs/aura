"""
Project Aura - Provenance Trust Adapter

Integrates ADR-067 Context Provenance trust scores into the CGE.
Low-trust contexts automatically tighten security constraints and
raise auto-execute thresholds.

Formula:
    adjustment = (1 - trust_score) * sensitivity
    C3 weight multiplied by (1 + adjustment)
    Auto-execute threshold raised by adjustment

Author: Project Aura Team
Created: 2026-02-11
"""

from __future__ import annotations

import logging
from typing import Optional

from .contracts import ProvenanceContext

logger = logging.getLogger(__name__)


class ProvenanceAdapter:
    """Adapter for ADR-067 provenance trust score integration.

    Converts provenance context into deterministic weight adjustments
    for the CGE. The adjustment is a pure function of the trust score
    and the profile's provenance sensitivity.
    """

    def __init__(self, default_sensitivity: float = 0.5):
        """Initialize the provenance adapter.

        Args:
            default_sensitivity: Default provenance sensitivity [0.0, 1.0].
                Higher values mean provenance has more impact on weights.
        """
        self._default_sensitivity = default_sensitivity

    def compute_adjustment(
        self,
        provenance: ProvenanceContext,
        sensitivity: Optional[float] = None,
    ) -> float:
        """Compute provenance-based weight adjustment.

        The adjustment increases as trust decreases. A fully trusted source
        (trust_score=1.0) produces zero adjustment. An untrusted source
        (trust_score=0.0) produces maximum adjustment equal to the sensitivity.

        Formula:
            adjustment = (1.0 - trust_score) * sensitivity

        Examples:
            trust=0.95, sensitivity=0.5 -> adjustment=0.025 (minimal impact)
            trust=0.30, sensitivity=0.5 -> adjustment=0.35  (significant)
            trust=0.00, sensitivity=0.5 -> adjustment=0.50  (maximum)

        Args:
            provenance: Provenance context with trust score
            sensitivity: Override sensitivity (uses default if None)

        Returns:
            Provenance adjustment value [0.0, sensitivity]
        """
        effective_sensitivity = sensitivity or self._default_sensitivity
        trust = max(0.0, min(1.0, provenance.trust_score))
        adjustment = (1.0 - trust) * effective_sensitivity

        logger.debug(
            "Provenance adjustment: trust=%.3f, sensitivity=%.3f, adjustment=%.3f",
            trust,
            effective_sensitivity,
            adjustment,
        )

        return adjustment

    def compute_threshold_raise(
        self,
        provenance: ProvenanceContext,
        base_threshold: float,
        sensitivity: Optional[float] = None,
    ) -> float:
        """Compute raised auto-execute threshold based on provenance.

        Low trust raises the bar for autonomous action, pushing more
        outputs to human review.

        Args:
            provenance: Provenance context
            base_threshold: Original auto-execute threshold
            sensitivity: Override sensitivity

        Returns:
            Raised threshold value, capped at 1.0
        """
        adjustment = self.compute_adjustment(provenance, sensitivity)
        return min(base_threshold + adjustment, 1.0)

    def compute_security_weight_multiplier(
        self,
        provenance: ProvenanceContext,
        sensitivity: Optional[float] = None,
    ) -> float:
        """Compute weight multiplier for C3 (Security Policy) axis.

        Low trust amplifies the security axis weight.

        Formula:
            multiplier = 1.0 + (1.0 - trust_score) * sensitivity

        Examples:
            trust=0.95 -> multiplier=1.025 (barely noticeable)
            trust=0.30 -> multiplier=1.35  (35% more weight)
            trust=0.00 -> multiplier=1.50  (50% more weight)

        Returns:
            Weight multiplier >= 1.0
        """
        adjustment = self.compute_adjustment(provenance, sensitivity)
        return 1.0 + adjustment
