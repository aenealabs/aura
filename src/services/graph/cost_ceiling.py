"""Per-tenant amortized cost ceiling for Tier 3 LLM resolution.

Phase 4c.2 of ADR-090. Per Mike's review (Thread 2 / Thread 4 / ML),
the per-job call budget in Phase 4c.1 prevents runaway cost on a
single pathological repo but does not bound a tenant's amortized
spend over a rolling window. This module provides that bound.

The tracker exposes a small interface so the resolver can ask
"may I spend up to N more tokens for tenant X?" before invoking
Bedrock and "I just spent N tokens for tenant X" after. When the
window's spend would exceed the configured ceiling, the tracker
denies admission and the resolver emits a deferred placeholder
edge.

Two backends:

  - :class:`InMemoryCostCeiling` -- single-process, per-tenant
    sliding window. Useful for tests and single-tenant deploys.
  - :class:`DynamoDBCostCeiling` -- shared across workers, soft
    dependency on a DynamoDB table. Falls back to in-memory when
    the table is unreachable.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

logger = logging.getLogger(__name__)


@dataclass
class CostUsage:
    """Per-tenant spend within the rolling window."""

    tenant_id: str
    tokens_in_window: int
    window_started_at: float
    samples: int


class CostCeiling(Protocol):
    """Common interface for the per-tenant cost tracker."""

    def admit(self, tenant_id: str, requested_tokens: int) -> bool: ...
    def record(self, tenant_id: str, spent_tokens: int) -> None: ...
    def usage(self, tenant_id: str) -> CostUsage: ...


@dataclass
class CeilingConfig:
    """Tunables for an in-memory cost ceiling."""

    # Maximum tokens per tenant per window.
    tokens_per_window: int = 10_000_000
    # Window size in seconds. Default 24h matches the ADR's
    # per-tenant amortized horizon.
    window_seconds: float = 24 * 60 * 60


class InMemoryCostCeiling:
    """Process-local per-tenant cost ceiling.

    Each tenant has a single rolling window; when the window is
    older than ``window_seconds`` the counter resets. This is
    deliberately approximate (a true rolling window would integrate
    over the full sample history) because the bound's job is to
    prevent runaway spend, not to be a billing system.
    """

    def __init__(
        self,
        config: CeilingConfig | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.config = config or CeilingConfig()
        self._clock = clock
        self._tenants: dict[str, _TenantWindow] = {}
        self._lock = threading.Lock()

    def admit(self, tenant_id: str, requested_tokens: int) -> bool:
        with self._lock:
            window = self._window(tenant_id)
            return window.tokens + requested_tokens <= self.config.tokens_per_window

    def record(self, tenant_id: str, spent_tokens: int) -> None:
        with self._lock:
            window = self._window(tenant_id)
            window.tokens += spent_tokens
            window.samples += 1

    def usage(self, tenant_id: str) -> CostUsage:
        with self._lock:
            window = self._window(tenant_id)
            return CostUsage(
                tenant_id=tenant_id,
                tokens_in_window=window.tokens,
                window_started_at=window.started_at,
                samples=window.samples,
            )

    def _window(self, tenant_id: str) -> "_TenantWindow":
        now = self._clock()
        window = self._tenants.get(tenant_id)
        if window is None or now - window.started_at >= self.config.window_seconds:
            window = _TenantWindow(started_at=now)
            self._tenants[tenant_id] = window
        return window


@dataclass
class _TenantWindow:
    started_at: float
    tokens: int = 0
    samples: int = 0


class DynamoDBCostCeiling:
    """Cross-worker cost ceiling backed by DynamoDB.

    Schema: ``tenant_id`` is the partition key; the item carries
    ``window_started_at``, ``tokens_in_window``, ``samples``. An
    atomic conditional update enforces the window roll-over and
    increment in a single round trip.

    Soft dependency: failure to reach the table falls through to
    the wrapped in-memory ceiling and increments
    ``self._unavailable``. Production deploys gate this with a
    health check; the fallback exists so a transient DynamoDB
    blip does not halt all ingestion.
    """

    DEFAULT_TABLE_NAME = "aura-symbol-resolution-cost"

    def __init__(
        self,
        table_name: str | None = None,
        client=None,
        fallback: CostCeiling | None = None,
        config: CeilingConfig | None = None,
    ):
        self.table_name = table_name or self.DEFAULT_TABLE_NAME
        self._client = client
        self._fallback = fallback or InMemoryCostCeiling(config)
        self.config = config or CeilingConfig()
        self._unavailable = client is None

    @property
    def available(self) -> bool:
        return not self._unavailable

    def admit(self, tenant_id: str, requested_tokens: int) -> bool:
        if self._unavailable:
            return self._fallback.admit(tenant_id, requested_tokens)
        try:
            response = self._client.get_item(
                TableName=self.table_name,
                Key={"tenant_id": {"S": tenant_id}},
                ConsistentRead=True,
            )
        except Exception as e:
            logger.warning(f"DynamoDB cost ceiling GET failed: {e}; fallback")
            self._unavailable = True
            return self._fallback.admit(tenant_id, requested_tokens)
        item = response.get("Item")
        usage = self._item_to_usage(tenant_id, item)
        # Apply window roll-over check.
        now = time.time()
        if now - usage.window_started_at >= self.config.window_seconds:
            return True  # New window; full ceiling available.
        return (
            usage.tokens_in_window + requested_tokens <= self.config.tokens_per_window
        )

    def record(self, tenant_id: str, spent_tokens: int) -> None:
        if self._unavailable:
            self._fallback.record(tenant_id, spent_tokens)
            return
        try:
            self._client.update_item(
                TableName=self.table_name,
                Key={"tenant_id": {"S": tenant_id}},
                UpdateExpression=(
                    "SET window_started_at = if_not_exists(window_started_at, :now), "
                    "tokens_in_window = if_not_exists(tokens_in_window, :zero) + :delta, "
                    "samples = if_not_exists(samples, :zero) + :one"
                ),
                ExpressionAttributeValues={
                    ":now": {"N": f"{time.time()}"},
                    ":zero": {"N": "0"},
                    ":delta": {"N": f"{spent_tokens}"},
                    ":one": {"N": "1"},
                },
            )
        except Exception as e:
            logger.warning(f"DynamoDB cost ceiling RECORD failed: {e}; fallback")
            self._unavailable = True
            self._fallback.record(tenant_id, spent_tokens)

    def usage(self, tenant_id: str) -> CostUsage:
        if self._unavailable:
            return self._fallback.usage(tenant_id)
        try:
            response = self._client.get_item(
                TableName=self.table_name,
                Key={"tenant_id": {"S": tenant_id}},
                ConsistentRead=True,
            )
        except Exception as e:
            logger.warning(f"DynamoDB cost ceiling USAGE failed: {e}; fallback")
            self._unavailable = True
            return self._fallback.usage(tenant_id)
        return self._item_to_usage(tenant_id, response.get("Item"))

    @staticmethod
    def _item_to_usage(tenant_id: str, item: dict | None) -> CostUsage:
        if not item:
            return CostUsage(
                tenant_id=tenant_id,
                tokens_in_window=0,
                window_started_at=time.time(),
                samples=0,
            )
        return CostUsage(
            tenant_id=tenant_id,
            tokens_in_window=int(item.get("tokens_in_window", {}).get("N", "0") or "0"),
            window_started_at=float(
                item.get("window_started_at", {}).get("N", "0") or "0"
            ),
            samples=int(item.get("samples", {}).get("N", "0") or "0"),
        )
