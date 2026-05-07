"""
Project Aura - Tenant-Level Cost Rollup.

Per-tenant cumulative spend across all campaigns in a billing period.
Per-campaign caps respected individually still allow a noisy tenant
with 50 concurrent campaigns to blow contracted spend; the rollup is
the compensating control (D9).

When the rollup hits its hard cap:
- Existing campaigns CONTINUE to their per-campaign caps (no
  retroactive halt)
- New campaigns refuse to start

Implements ADR-089 D9.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .exceptions import TenantCostCapExceededError


@dataclass
class TenantBudget:
    """Per-tenant budget configuration for a billing period."""

    tenant_id: str
    period: str  # e.g. "2026-05" — keyed for monthly rollups
    cap_usd: float
    used_usd: float = 0.0


class TenantCostRollup(Protocol):
    """Contract every tenant-rollup backend must satisfy."""

    async def get(self, tenant_id: str, period: str) -> TenantBudget | None:
        """Read the current rollup for a tenant in a billing period."""
        ...

    async def set_cap(
        self, tenant_id: str, period: str, cap_usd: float
    ) -> None:
        """Establish or update the cap (used at contract time)."""
        ...

    async def record_spend(
        self, tenant_id: str, period: str, additional_usd: float
    ) -> TenantBudget:
        """Atomically add to used spend; raises if doing so exceeds cap."""
        ...

    async def can_start_campaign(
        self,
        tenant_id: str,
        period: str,
        projected_campaign_cap_usd: float,
    ) -> bool:
        """Whether a new campaign with the given cap can start.

        A new campaign whose worst-case spend would push the tenant
        over its rollup cap is refused at creation time.
        """
        ...


class InMemoryTenantCostRollup:
    """In-memory implementation of ``TenantCostRollup`` for tests."""

    def __init__(self) -> None:
        self._budgets: dict[tuple[str, str], TenantBudget] = {}
        self._lock = threading.Lock()

    def _period_for(self, when: datetime | None = None) -> str:
        d = when or datetime.utcnow()
        return d.strftime("%Y-%m")

    async def get(self, tenant_id: str, period: str) -> TenantBudget | None:
        with self._lock:
            return self._budgets.get((tenant_id, period))

    async def set_cap(
        self, tenant_id: str, period: str, cap_usd: float
    ) -> None:
        if cap_usd < 0:
            raise ValueError("cap_usd must be non-negative")
        key = (tenant_id, period)
        with self._lock:
            existing = self._budgets.get(key)
            if existing:
                self._budgets[key] = TenantBudget(
                    tenant_id=tenant_id,
                    period=period,
                    cap_usd=cap_usd,
                    used_usd=existing.used_usd,
                )
            else:
                self._budgets[key] = TenantBudget(
                    tenant_id=tenant_id, period=period, cap_usd=cap_usd
                )

    async def record_spend(
        self, tenant_id: str, period: str, additional_usd: float
    ) -> TenantBudget:
        if additional_usd < 0:
            raise ValueError("additional_usd must be non-negative")
        key = (tenant_id, period)
        with self._lock:
            budget = self._budgets.get(key)
            if budget is None:
                raise TenantCostCapExceededError(
                    f"No tenant budget configured for {tenant_id} in {period}; "
                    f"call set_cap before recording spend"
                )
            new_used = budget.used_usd + additional_usd
            if new_used > budget.cap_usd:
                raise TenantCostCapExceededError(
                    f"Tenant {tenant_id} {period}: recording "
                    f"+${additional_usd:.2f} would exceed cap "
                    f"${budget.cap_usd:.2f} "
                    f"(current=${budget.used_usd:.2f})"
                )
            updated = TenantBudget(
                tenant_id=tenant_id,
                period=period,
                cap_usd=budget.cap_usd,
                used_usd=new_used,
            )
            self._budgets[key] = updated
            return updated

    async def can_start_campaign(
        self,
        tenant_id: str,
        period: str,
        projected_campaign_cap_usd: float,
    ) -> bool:
        with self._lock:
            budget = self._budgets.get((tenant_id, period))
            if budget is None:
                # No tenant budget set; default-deny so the API surfaces the
                # configuration error rather than silently allowing.
                return False
            return (
                budget.used_usd + projected_campaign_cap_usd
            ) <= budget.cap_usd
