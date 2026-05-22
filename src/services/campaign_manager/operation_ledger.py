"""
Project Aura - Campaign Operation Ledger.

Idempotency contract for phases that perform external side effects
(open a PR, mutate a sandbox, write to Neptune, deploy a patch).
A Bedrock 5xx mid-phase will trigger phase retry; without the ledger,
retries duplicate side effects.

Implements ADR-089 D2.

The contract:
1. Compute a deterministic ``operation_id`` for the side effect from
   the phase's checkpoint state (so retries produce the same id).
2. Call ``claim`` BEFORE executing. If it returns CLAIMED, proceed.
   If it returns ALREADY_EXECUTED, return the prior outcome.
3. After executing, call ``record_outcome`` to attach the outcome to
   the claim.

The DynamoDB-backed implementation lives in a follow-up; this module
ships an in-memory implementation that satisfies the same contract,
suitable for tests and for in-process use during development.

#214-S5: ``tenant_id`` is part of the key, not derived from the
campaign_id. Two tenants with colliding campaign UUIDs (or a malicious
tenant_id-spoof attempt) cannot replay or read each other's outcomes.
``record_outcome`` enforces monotonic ``recorded_at`` per
(tenant, campaign) so a clock-rewind or write-race cannot serve a
stale outcome as fresh.

Author: Project Aura Team
Created: 2026-05-07
Updated: 2026-05-22 (issue #214-S5 -- tenant scoping + monotonic recorded_at)
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Protocol

from .contracts import OperationClaim, OperationOutcome, OperationStatus
from .exceptions import OperationAlreadyClaimedError


class OperationLedger(Protocol):
    """Contract every operation-ledger backend must satisfy."""

    async def claim(
        self,
        tenant_id: str,
        campaign_id: str,
        phase_id: str,
        operation_id: str,
    ) -> OperationClaim:
        """Atomically claim an operation key.

        Returns ``OperationClaim(status=CLAIMED)`` if no prior entry
        exists; the caller may now execute the side effect.

        Returns ``OperationClaim(status=ALREADY_EXECUTED, prior_outcome=...)``
        if a prior entry exists; the caller MUST NOT re-execute and
        should return the prior outcome.
        """
        ...

    async def record_outcome(
        self,
        tenant_id: str,
        campaign_id: str,
        phase_id: str,
        operation_id: str,
        outcome: OperationOutcome,
    ) -> None:
        """Attach an outcome to a previously claimed operation.

        Raises ``OperationAlreadyClaimedError`` if an outcome is
        already recorded for this key (cannot overwrite). Raises the
        same exception if the outcome's ``recorded_at`` is earlier
        than the most-recent outcome for this (tenant, campaign)
        (#214-S5 monotonic guarantee).
        """
        ...

    async def get_outcome(
        self,
        tenant_id: str,
        campaign_id: str,
        phase_id: str,
        operation_id: str,
    ) -> OperationOutcome | None:
        """Read the recorded outcome, or ``None`` if not recorded."""
        ...


class InMemoryOperationLedger:
    """In-memory ``OperationLedger`` for tests and development.

    Backed by a dict keyed by ``(tenant_id, campaign_id, phase_id,
    operation_id)``. A lock guards mutations so concurrent ``claim``
    calls behave like DynamoDB conditional writes.

    Production code will swap in a DynamoDB implementation against the
    same Protocol; tests target the Protocol, so this implementation
    is a faithful behavioural model.

    Tenant scoping (#214-S5): the tenant_id is part of the key, not
    derived. Cross-tenant replay (same operation_id from a different
    tenant) is impossible because the key does not match.

    Monotonic ``recorded_at`` (#214-S5): per (tenant_id, campaign_id),
    each ``record_outcome`` call must carry a ``recorded_at`` that is
    >= the most-recent prior outcome's. A clock-rewind or out-of-order
    write raises ``OperationAlreadyClaimedError`` rather than silently
    overwriting the ordering.
    """

    def __init__(self) -> None:
        self._claims: dict[tuple[str, str, str, str], OperationOutcome | None] = {}
        # Per-(tenant, campaign) high-water-mark for monotonic ordering.
        self._last_recorded_at: dict[tuple[str, str], datetime] = {}
        self._lock = threading.Lock()

    async def claim(
        self,
        tenant_id: str,
        campaign_id: str,
        phase_id: str,
        operation_id: str,
    ) -> OperationClaim:
        key = (tenant_id, campaign_id, phase_id, operation_id)
        with self._lock:
            if key in self._claims:
                prior = self._claims[key]
                # Either: claim exists with no outcome yet (rare; usually
                # means a prior worker crashed mid-execution before
                # recording) -> still ALREADY_EXECUTED, surface a placeholder
                # outcome so the caller does not re-execute.
                # Or: claim exists with outcome -> standard case.
                if prior is None:
                    return OperationClaim(
                        status=OperationStatus.ALREADY_EXECUTED,
                        prior_outcome=OperationOutcome(
                            success=False,
                            summary=(
                                "operation was claimed but no outcome was "
                                "recorded; treat as in-flight crash"
                            ),
                        ),
                    )
                return OperationClaim(
                    status=OperationStatus.ALREADY_EXECUTED,
                    prior_outcome=prior,
                )
            self._claims[key] = None
            return OperationClaim(status=OperationStatus.CLAIMED)

    async def record_outcome(
        self,
        tenant_id: str,
        campaign_id: str,
        phase_id: str,
        operation_id: str,
        outcome: OperationOutcome,
    ) -> None:
        key = (tenant_id, campaign_id, phase_id, operation_id)
        watermark_key = (tenant_id, campaign_id)
        with self._lock:
            existing = self._claims.get(key)
            if key not in self._claims:
                raise OperationAlreadyClaimedError(
                    f"Cannot record outcome for unclaimed operation {key!r}"
                )
            if existing is not None:
                raise OperationAlreadyClaimedError(
                    f"Outcome already recorded for operation {key!r}"
                )
            # #214-S5: monotonic recorded_at per (tenant, campaign).
            high_water = self._last_recorded_at.get(watermark_key)
            if high_water is not None and outcome.recorded_at < high_water:
                raise OperationAlreadyClaimedError(
                    f"OperationOutcome.recorded_at "
                    f"({outcome.recorded_at.isoformat()}) is earlier than "
                    f"the most-recent outcome for tenant={tenant_id} "
                    f"campaign={campaign_id} "
                    f"({high_water.isoformat()}). Monotonic ordering is "
                    f"required to prevent out-of-order replay (#214-S5)."
                )
            self._claims[key] = outcome
            self._last_recorded_at[watermark_key] = outcome.recorded_at

    async def get_outcome(
        self,
        tenant_id: str,
        campaign_id: str,
        phase_id: str,
        operation_id: str,
    ) -> OperationOutcome | None:
        key = (tenant_id, campaign_id, phase_id, operation_id)
        with self._lock:
            return self._claims.get(key)
