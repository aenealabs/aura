"""Per-worker per-region circuit breaker for Bedrock invocations.

Phase 4c.2 of ADR-090. The breaker wraps the LLM call inside a
:class:`Tier3LLMResolver` worker. When Bedrock throws a sustained
rate of 429s, 5xx responses, or transport timeouts, the breaker
opens and short-circuits subsequent invocations for a configurable
cooldown window. Once cooldown expires, the breaker enters a
half-open state and admits a single probe; success closes the
breaker, failure re-opens with backoff.

Per Thread 2 (Tyler, data engineering) the breaker is intentionally
**per-worker, per-region** rather than cluster-wide:

  - No shared state to coordinate -> no coordination point that
    can itself fail.
  - Faster local recovery: each worker probes independently.
  - Slightly slower cluster-wide reaction to a regional Bedrock
    outage; acceptable since each worker independently detects
    and self-protects.

The breaker is async-friendly (the protected callable is awaited)
but does not introduce additional asyncio machinery; the open/
half-open state is updated synchronously on each call. A monotonic
clock is used so the timing is robust to wall-clock changes.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class BreakerConfig:
    """Tunables for a single circuit breaker instance."""

    # Window in seconds across which failure rate is computed.
    window_seconds: float = 30.0
    # Minimum sample count in-window before a trip is considered.
    # Prevents one-off bursts of error from tripping the breaker.
    min_samples: int = 10
    # Failure rate threshold above which the breaker trips.
    failure_rate_threshold: float = 0.5
    # Cooldown before transitioning from OPEN to HALF_OPEN.
    cooldown_seconds: float = 30.0
    # Maximum cooldown after repeated half-open failures (exp backoff).
    max_cooldown_seconds: float = 600.0


@dataclass
class BreakerStats:
    state: BreakerState = BreakerState.CLOSED
    open_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    short_circuits: int = 0
    last_open_at: float | None = None
    last_close_at: float | None = None


class CircuitBreakerOpen(Exception):
    """Raised when a call is short-circuited because the breaker is open."""


class CircuitBreaker(Generic[T]):
    """Async circuit breaker.

    Usage::

        breaker = CircuitBreaker(BreakerConfig())
        try:
            result = await breaker.call(lambda: bedrock.generate(...))
        except CircuitBreakerOpen:
            # short-circuited; emit deferred-resolution edge.
            ...
    """

    def __init__(
        self,
        config: BreakerConfig | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.config = config or BreakerConfig()
        self._clock = clock
        self._state: BreakerState = BreakerState.CLOSED
        # Each entry is (timestamp, success: bool)
        self._samples: deque[tuple[float, bool]] = deque()
        self._next_probe_at: float = 0.0
        self._consecutive_open_cycles: int = 0
        self.stats = BreakerStats(state=BreakerState.CLOSED)

    @property
    def state(self) -> BreakerState:
        # Lazy state transition: OPEN -> HALF_OPEN when cooldown has
        # elapsed. Computed on read so tests do not need to drive a
        # background tick.
        if self._state == BreakerState.OPEN and self._clock() >= self._next_probe_at:
            self._state = BreakerState.HALF_OPEN
            self.stats.state = self._state
            logger.info("CircuitBreaker -> HALF_OPEN (probe admitted)")
        return self._state

    async def call(self, op: Callable[[], Awaitable[T]]) -> T:
        """Invoke ``op`` if the breaker permits; raise ``CircuitBreakerOpen``
        when the breaker is OPEN.

        HALF_OPEN admits exactly one probe; that probe's outcome
        decides whether to close the breaker or re-open with backoff.
        """
        state = self.state
        if state == BreakerState.OPEN:
            self.stats.short_circuits += 1
            raise CircuitBreakerOpen("Circuit breaker is OPEN; deferring resolution.")

        try:
            result = await op()
        except Exception:
            self._record(success=False)
            raise
        else:
            self._record(success=True)
            return result

    def _record(self, *, success: bool) -> None:
        now = self._clock()
        self._samples.append((now, success))
        self._evict_old(now)

        if success:
            self.stats.success_count += 1
        else:
            self.stats.failure_count += 1

        # In HALF_OPEN, the outcome of the single probe decides the
        # next state.
        if self._state == BreakerState.HALF_OPEN:
            if success:
                self._close(now)
            else:
                self._open(now)
            return

        # CLOSED: trip if failure rate exceeds threshold over a full
        # min_samples window.
        if (
            self._state == BreakerState.CLOSED
            and len(self._samples) >= self.config.min_samples
        ):
            failures = sum(1 for _, s in self._samples if not s)
            rate = failures / len(self._samples)
            if rate >= self.config.failure_rate_threshold:
                self._open(now)

    def _evict_old(self, now: float) -> None:
        cutoff = now - self.config.window_seconds
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def _open(self, now: float) -> None:
        self._state = BreakerState.OPEN
        self.stats.state = self._state
        self.stats.open_count += 1
        self.stats.last_open_at = now
        self._consecutive_open_cycles += 1
        # Exponential backoff on repeated trips, capped at the max.
        cooldown = min(
            self.config.cooldown_seconds * (2 ** (self._consecutive_open_cycles - 1)),
            self.config.max_cooldown_seconds,
        )
        self._next_probe_at = now + cooldown
        # Clear sample window on trip so post-recovery rate counters
        # start fresh.
        self._samples.clear()
        logger.warning(
            f"CircuitBreaker tripped: cooldown={cooldown:.1f}s "
            f"open_cycles={self._consecutive_open_cycles}"
        )

    def _close(self, now: float) -> None:
        self._state = BreakerState.CLOSED
        self.stats.state = self._state
        self.stats.last_close_at = now
        self._consecutive_open_cycles = 0
        self._samples.clear()
        logger.info("CircuitBreaker closed (probe succeeded)")
