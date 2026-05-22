"""Bedrock model version watcher (issue #212).

A small, stateful object that the scheduler (production: EventBridge
Lambda) calls on a cadence. The watcher reads the current model
versions from the registry, compares against its last snapshot, and
returns one :class:`ModelUpgradeEvent` per configured tier so the
coordinator can decide what to do.

Stateful between ticks; the snapshot is in-process. Production deploys
this as a Lambda warm container; on cold start the watcher reads the
last-known versions from SSM via a separate restore step (out of
scope here -- a trivial dict-load).
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.services.model_assurance.model_upgrade_watcher.contracts import (
    BedrockModelVersion,
    ModelUpgradeEvent,
)
from src.services.model_assurance.model_upgrade_watcher.ports import (
    BedrockModelRegistryPort,
)


class ModelVersionWatcher:
    """Detect bumps in the registry's reported versions."""

    def __init__(
        self,
        *,
        registry: BedrockModelRegistryPort,
        initial_snapshot: tuple[BedrockModelVersion, ...] = (),
    ) -> None:
        self._registry = registry
        # tier -> version -- mutable across ticks
        self._snapshot: dict[str, BedrockModelVersion] = {
            v.tier: v for v in initial_snapshot
        }

    def snapshot(self) -> tuple[BedrockModelVersion, ...]:
        """Return the watcher's last-known versions (one per tier)."""
        return tuple(self._snapshot.values())

    def tick(self) -> tuple[ModelUpgradeEvent, ...]:
        """Run one detection pass; return per-tier events.

        Events are emitted for every configured tier, not only the
        ones that bumped. The caller filters via ``event.is_bump``.
        That way the audit trail shows we *checked* each tier on
        every tick.
        """
        now = datetime.now(timezone.utc)
        current = self._registry.current_versions()
        events: list[ModelUpgradeEvent] = []
        for cur in current:
            prev = self._snapshot.get(
                cur.tier,
                BedrockModelVersion(tier=cur.tier, model_id="", version=""),
            )
            events.append(
                ModelUpgradeEvent(
                    detected_at=now,
                    tier=cur.tier,
                    previous=prev,
                    current=cur,
                )
            )
            self._snapshot[cur.tier] = cur
        return tuple(events)
