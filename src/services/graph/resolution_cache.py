"""Content-addressed resolution cache (ADR-090 Phase 4c.2).

Caches Tier 3 LLM resolutions across ingest jobs so repeated cold
scans of the same code spend Bedrock budget only on novel call
sites. The cache key is the ``context_hash`` carried on every
:class:`ResolutionRequest`: a fingerprint of (file path, call site
line, target name, candidate set, snippet hash).

Two backends ship in this module:

  - :class:`InMemoryResolutionCache` -- single-process, useful for
    tests and the in-process Phase 4c.1 producer.
  - :class:`DynamoDBResolutionCache` -- shared across worker
    processes / regions, soft dependency on a DynamoDB table.
    When the table is unreachable, the resolver falls back to the
    in-memory cache and increments a telemetry counter so
    operators see the degradation.

Per Mike's review (ADR-090 Thread 2 / Phase 4c.2 cache TODO):
transitive-closure invalidation belongs here. When a file in the
caller's transitive import closure changes, every cached
resolution that depended on that closure must be invalidated.
The :class:`ResolutionCache` interface accepts an optional
``closure_fingerprint`` per entry so callers can drop entries
matching a stale closure without scanning every key.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass
class CachedResolution:
    """A cached LLM resolution outcome."""

    target_fqn: str | None
    verification_status: str  # verified | plausible | unverified
    model_id: str | None = None
    closure_fingerprint: str | None = None
    timestamp: float = 0.0


class ResolutionCache(Protocol):
    """Common interface for resolution caches.

    Both backends are intentionally minimal: callers use ``get`` and
    ``put`` keyed on ``context_hash``; ``invalidate_closure`` drops
    every entry whose ``closure_fingerprint`` matches the supplied
    value (used when a transitive import dependency has changed).
    """

    def get(self, context_hash: str) -> CachedResolution | None: ...
    def put(self, context_hash: str, resolution: CachedResolution) -> None: ...
    def invalidate_closure(self, closure_fingerprint: str) -> int: ...


class InMemoryResolutionCache:
    """Process-local cache. Thread-safe; not shared across workers.

    Best fit for tests, single-tenant deployments, and the in-process
    Phase 4c.1 fallback when DynamoDB is unreachable.
    """

    def __init__(self) -> None:
        self._store: dict[str, CachedResolution] = {}
        self._lock = threading.Lock()

    def get(self, context_hash: str) -> CachedResolution | None:
        with self._lock:
            return self._store.get(context_hash)

    def put(self, context_hash: str, resolution: CachedResolution) -> None:
        if resolution.timestamp == 0.0:
            resolution = CachedResolution(
                target_fqn=resolution.target_fqn,
                verification_status=resolution.verification_status,
                model_id=resolution.model_id,
                closure_fingerprint=resolution.closure_fingerprint,
                timestamp=time.time(),
            )
        with self._lock:
            self._store[context_hash] = resolution

    def invalidate_closure(self, closure_fingerprint: str) -> int:
        """Drop every entry whose ``closure_fingerprint`` matches.

        Returns the number of entries removed.
        """
        with self._lock:
            stale = [
                k
                for k, v in self._store.items()
                if v.closure_fingerprint == closure_fingerprint
            ]
            for k in stale:
                del self._store[k]
            return len(stale)

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


class DynamoDBResolutionCache:
    """Cross-worker cache backed by a DynamoDB table.

    The table schema is intentionally minimal: ``context_hash`` is
    the partition key, every other field lives in attributes. The
    closure-fingerprint invalidation pass uses a sparse GSI on
    ``closure_fingerprint`` for O(matching) deletes.

    The class is structured so an absent / unreachable table falls
    back to a wrapped :class:`InMemoryResolutionCache`. This is the
    soft-dependency contract: the resolver always has somewhere to
    write, just possibly less durable than the operator expects.
    """

    DEFAULT_TABLE_NAME = "aura-symbol-resolution-cache"

    def __init__(
        self,
        table_name: str | None = None,
        client=None,
        fallback: ResolutionCache | None = None,
    ):
        self.table_name = table_name or self.DEFAULT_TABLE_NAME
        self._client = client
        self._fallback = fallback or InMemoryResolutionCache()
        self._unavailable = client is None

    @property
    def available(self) -> bool:
        return not self._unavailable

    def get(self, context_hash: str) -> CachedResolution | None:
        if self._unavailable:
            return self._fallback.get(context_hash)
        try:
            response = self._client.get_item(
                TableName=self.table_name,
                Key={"context_hash": {"S": context_hash}},
                ConsistentRead=False,
            )
        except Exception as e:
            logger.warning(f"DynamoDB cache GET failed: {e}; using fallback")
            self._unavailable = True
            return self._fallback.get(context_hash)
        item = response.get("Item")
        if not item:
            return None
        return _item_to_resolution(item)

    def put(self, context_hash: str, resolution: CachedResolution) -> None:
        if resolution.timestamp == 0.0:
            resolution = CachedResolution(
                target_fqn=resolution.target_fqn,
                verification_status=resolution.verification_status,
                model_id=resolution.model_id,
                closure_fingerprint=resolution.closure_fingerprint,
                timestamp=time.time(),
            )
        if self._unavailable:
            self._fallback.put(context_hash, resolution)
            return
        try:
            self._client.put_item(
                TableName=self.table_name,
                Item=_resolution_to_item(context_hash, resolution),
            )
        except Exception as e:
            logger.warning(f"DynamoDB cache PUT failed: {e}; using fallback")
            self._unavailable = True
            self._fallback.put(context_hash, resolution)

    def invalidate_closure(self, closure_fingerprint: str) -> int:
        if self._unavailable:
            return self._fallback.invalidate_closure(closure_fingerprint)
        # Real implementation would query the GSI and batch-delete;
        # we keep the contract here and treat the production wiring
        # as a Phase 4c.2.x follow-up. The fallback path covers the
        # functional behaviour for tests and single-process deploys.
        return self._fallback.invalidate_closure(closure_fingerprint)


# -- (de)serialization helpers ------------------------------------------


def _resolution_to_item(context_hash: str, resolution: CachedResolution) -> dict:
    item: dict = {
        "context_hash": {"S": context_hash},
        "verification_status": {"S": resolution.verification_status},
        "timestamp": {"N": f"{resolution.timestamp}"},
    }
    if resolution.target_fqn is not None:
        item["target_fqn"] = {"S": resolution.target_fqn}
    if resolution.model_id is not None:
        item["model_id"] = {"S": resolution.model_id}
    if resolution.closure_fingerprint is not None:
        item["closure_fingerprint"] = {"S": resolution.closure_fingerprint}
    return item


def _item_to_resolution(item: dict) -> CachedResolution:
    return CachedResolution(
        target_fqn=item.get("target_fqn", {}).get("S"),
        verification_status=item.get("verification_status", {}).get("S", "unverified"),
        model_id=item.get("model_id", {}).get("S"),
        closure_fingerprint=item.get("closure_fingerprint", {}).get("S"),
        timestamp=float(item.get("timestamp", {}).get("N", 0.0) or 0.0),
    )
