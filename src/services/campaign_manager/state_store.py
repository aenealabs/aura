"""
Project Aura - Campaign State Store.

Persistence interface for ``CampaignState``. Optimistic concurrency
control via the ``version`` field on the state record: every update
asserts the prior version, so two concurrent writers (e.g. orchestrator
progress and HITL approval) cannot silently lose updates.

Production: DynamoDB conditional writes keyed by ``tenant_id#campaign_id``
with the version assertion. This module ships an in-memory backend
satisfying the same contract for tests and local use.

Implements ADR-089 D6.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import threading
from typing import Protocol

from .contracts import CampaignState
from .exceptions import CampaignError


class StaleStateError(CampaignError):
    """Update raced with another writer; caller should reload + retry."""


class CampaignStateStore(Protocol):
    """Contract every state-store backend must satisfy."""

    async def put_initial(self, state: CampaignState) -> None:
        """Insert a brand-new campaign state. Fails if one already exists."""
        ...

    async def get(self, tenant_id: str, campaign_id: str) -> CampaignState | None:
        """Read the current state; ``None`` if no such campaign."""
        ...

    async def update(self, expected_version: int, new_state: CampaignState) -> None:
        """Update with optimistic concurrency control.

        Raises ``StaleStateError`` if the on-disk version differs from
        ``expected_version``. Callers reload + retry.
        """
        ...

    async def list_for_tenant(self, tenant_id: str) -> list[CampaignState]:
        """List all campaign states for a tenant."""
        ...


class InMemoryCampaignStateStore:
    """In-memory implementation of ``CampaignStateStore``.

    Models DynamoDB conditional-write semantics: ``update`` enforces
    the version assertion under a lock.
    """

    def __init__(self) -> None:
        self._states: dict[tuple[str, str], CampaignState] = {}
        self._lock = threading.Lock()

    async def put_initial(self, state: CampaignState) -> None:
        key = (state.tenant_id, state.campaign_id)
        with self._lock:
            if key in self._states:
                raise CampaignError(
                    f"Campaign {state.campaign_id} already exists for "
                    f"tenant {state.tenant_id}"
                )
            self._states[key] = state

    async def get(self, tenant_id: str, campaign_id: str) -> CampaignState | None:
        with self._lock:
            return self._states.get((tenant_id, campaign_id))

    async def update(
        self, expected_version: int, new_state: CampaignState
    ) -> None:
        key = (new_state.tenant_id, new_state.campaign_id)
        with self._lock:
            current = self._states.get(key)
            if current is None:
                raise CampaignError(
                    f"Campaign {new_state.campaign_id} does not exist; "
                    f"call put_initial first"
                )
            if current.version != expected_version:
                raise StaleStateError(
                    f"Stale write for campaign {new_state.campaign_id}: "
                    f"expected version {expected_version}, "
                    f"on-disk is {current.version}"
                )
            self._states[key] = new_state

    async def list_for_tenant(self, tenant_id: str) -> list[CampaignState]:
        with self._lock:
            return [s for (t, _), s in self._states.items() if t == tenant_id]
