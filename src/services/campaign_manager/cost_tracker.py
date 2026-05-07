"""
Project Aura - Campaign-Scoped Cost Tracker.

Per-campaign budget enforcement layered on top of the per-scan
``CostTracker`` from ADR-049. Differences from the per-scan tracker:

1. Per-token enforcement at the Bedrock-client interceptor (D4),
   not at phase boundaries. Phase boundaries commit *cumulative*
   spend; the cap is checked before every individual invocation.
2. 5% graceful-stop reservation. When the cap is reached, the
   campaign halts but a small budget remains for cleanup/rollback
   work (e.g. closing in-flight PRs, tearing down sandboxes).
3. Cap-raise counter. Successive cap raises beyond the second
   require an escalated approver tier (enforced by the API layer
   reading this counter).

The class is intentionally ``threading.Lock``-guarded rather than
asyncio-locked: it is consulted from sync interceptor code paths
(boto3 invocation hooks) as well as async orchestrator paths.

Implements ADR-089 D4 + D9.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from src.services.vulnerability_scanner.analysis.capability import (
    ModelCapabilityTier,
)
from src.services.vulnerability_scanner.analysis.cost_tracker import (
    DEFAULT_TIER_PRICING,
    TierPricing,
)

from .contracts import CostSnapshot
from .exceptions import CostCapExceededError

logger = logging.getLogger(__name__)


# 5% of the cap is held back for cleanup/rollback (D4 graceful-stop).
CLEANUP_RESERVATION_FRACTION: float = 0.05


@dataclass
class _PerTierUsage:
    invocations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class CampaignCostTracker:
    """Per-campaign cost accumulator with hard cap and cleanup reservation.

    Lifecycle:
        1. ``can_invoke(tier, input_tokens, output_tokens)`` BEFORE every
           Bedrock call. Returns False if the call would exceed the cap.
        2. ``record(tier, input_tokens, output_tokens)`` after the call
           (or at the interceptor for at-call commit). Raises
           ``CostCapExceededError`` if the recording would push the
           campaign over its hard cap.
        3. When the orchestrator catches ``CostCapExceededError``, it
           calls ``enter_cleanup_mode()`` which unlocks the 5%
           reservation for rollback work only.
        4. ``record_sandbox_cost(usd)`` for non-Bedrock spend.

    Thread-safe. Suitable for use from boto3 invocation interceptors.
    """

    def __init__(
        self,
        campaign_id: str,
        cost_cap_usd: float,
        pricing: dict[ModelCapabilityTier, TierPricing] | None = None,
    ) -> None:
        if cost_cap_usd < 0:
            raise ValueError(
                f"cost_cap_usd must be non-negative; got {cost_cap_usd!r}"
            )
        self._campaign_id = campaign_id
        self._cap = cost_cap_usd
        self._cleanup_reservation = (
            cost_cap_usd * CLEANUP_RESERVATION_FRACTION
        )
        self._effective_cap = cost_cap_usd - self._cleanup_reservation
        self._pricing = pricing or DEFAULT_TIER_PRICING
        self._tier_usage: dict[ModelCapabilityTier, _PerTierUsage] = {
            tier: _PerTierUsage() for tier in self._pricing
        }
        self._sandbox_cost: float = 0.0
        self._cleanup_mode: bool = False
        self._cap_raises: int = 0
        self._lock = threading.Lock()

    # -- pricing / projection -------------------------------------------------

    def project_cost(
        self,
        tier: ModelCapabilityTier,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        pricing = self._pricing.get(tier)
        if pricing is None:
            raise KeyError(
                f"No pricing configured for tier {tier.name} in this tracker"
            )
        return pricing.cost_for(input_tokens, output_tokens)

    # -- cap enforcement ------------------------------------------------------

    def can_invoke(
        self,
        tier: ModelCapabilityTier,
        input_tokens: int,
        output_tokens: int,
    ) -> bool:
        """Check whether a projected invocation would breach the cap.

        Uses the *effective* cap (cap minus cleanup reservation) when
        the campaign is running normally. Once in cleanup mode, the
        full cap is available — but only for cleanup operations.
        Callers in cleanup mode must self-attest by calling
        ``record_cleanup_cost`` explicitly.
        """
        projected = self.project_cost(tier, input_tokens, output_tokens)
        with self._lock:
            current_total = self._total_cost_locked()
            ceiling = self._cap if self._cleanup_mode else self._effective_cap
            return (current_total + projected) <= ceiling

    def record(
        self,
        tier: ModelCapabilityTier,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Record a normal-mode invocation. Returns USD cost."""
        cost = self.project_cost(tier, input_tokens, output_tokens)
        with self._lock:
            ceiling = (
                self._cap if self._cleanup_mode else self._effective_cap
            )
            current_total = self._total_cost_locked()
            if (current_total + cost) > ceiling:
                raise CostCapExceededError(
                    f"Campaign {self._campaign_id}: invocation would exceed "
                    f"effective cap of ${ceiling:.2f} "
                    f"(current=${current_total:.2f}, +${cost:.4f}); "
                    f"cleanup reservation=${self._cleanup_reservation:.2f}"
                )
            usage = self._tier_usage[tier]
            usage.invocations += 1
            usage.input_tokens += input_tokens
            usage.output_tokens += output_tokens
            usage.cost_usd += cost
        return cost

    def record_sandbox_cost(self, usd: float) -> None:
        """Record non-Bedrock cost (sandbox compute, etc.)."""
        if usd < 0:
            raise ValueError(f"sandbox cost must be non-negative; got {usd}")
        with self._lock:
            ceiling = (
                self._cap if self._cleanup_mode else self._effective_cap
            )
            current_total = self._total_cost_locked()
            if (current_total + usd) > ceiling:
                raise CostCapExceededError(
                    f"Campaign {self._campaign_id}: sandbox cost would "
                    f"exceed effective cap of ${ceiling:.2f}"
                )
            self._sandbox_cost += usd

    # -- cleanup-mode transition ---------------------------------------------

    def enter_cleanup_mode(self) -> None:
        """Unlock the 5% reservation for cleanup/rollback work only.

        Called by the orchestrator after catching ``CostCapExceededError``
        and transitioning the campaign to ``HALTED_AT_CAP``. Subsequent
        calls to ``record`` use the full cap rather than the effective
        cap — but the orchestrator should only invoke cleanup operations
        in this mode.
        """
        with self._lock:
            self._cleanup_mode = True

    @property
    def is_in_cleanup_mode(self) -> bool:
        with self._lock:
            return self._cleanup_mode

    # -- cap raise tracking ---------------------------------------------------

    def raise_cap(self, additional_usd: float) -> int:
        """Increase the cap by ``additional_usd``; returns new raise count.

        Per D4: the third raise and beyond should require an escalated
        approver tier. The API layer reads this counter and routes
        approvals accordingly.
        """
        if additional_usd <= 0:
            raise ValueError("cap raise must be positive")
        with self._lock:
            self._cap += additional_usd
            self._effective_cap = self._cap * (
                1.0 - CLEANUP_RESERVATION_FRACTION
            )
            self._cleanup_reservation = self._cap - self._effective_cap
            self._cleanup_mode = False  # reset; new headroom available
            self._cap_raises += 1
            return self._cap_raises

    @property
    def cap_raises(self) -> int:
        with self._lock:
            return self._cap_raises

    # -- snapshot / introspection --------------------------------------------

    def snapshot(self) -> CostSnapshot:
        """Return an immutable cost snapshot for persistence."""
        with self._lock:
            std = self._tier_usage[ModelCapabilityTier.STANDARD].cost_usd
            adv = self._tier_usage[ModelCapabilityTier.ADVANCED].cost_usd
            return CostSnapshot(
                standard_cost_usd=std,
                advanced_cost_usd=adv,
                sandbox_cost_usd=self._sandbox_cost,
                total_cost_usd=std + adv + self._sandbox_cost,
                cleanup_reservation_usd=self._cleanup_reservation,
                in_cleanup_mode=self._cleanup_mode,
            )

    @property
    def total_cost_usd(self) -> float:
        with self._lock:
            return self._total_cost_locked()

    @property
    def cap_remaining_usd(self) -> float:
        with self._lock:
            ceiling = (
                self._cap if self._cleanup_mode else self._effective_cap
            )
            return max(0.0, ceiling - self._total_cost_locked())

    # -- private helpers ------------------------------------------------------

    def _total_cost_locked(self) -> float:
        std = self._tier_usage[ModelCapabilityTier.STANDARD].cost_usd
        adv = self._tier_usage[ModelCapabilityTier.ADVANCED].cost_usd
        return std + adv + self._sandbox_cost
