"""Cron-controlled rotation-seed source (ADR-088 Phase 3.1).

Per ADR-088 §Stage 6 condition #14 (Mike): "rotation managed
outside the agent loop (cron job, not agent-controlled)". The
holdout seed the Oracle uses to sample 20% of cases must come from
a source the evaluation agent cannot influence — otherwise an
agent under optimisation pressure could choose seeds that exclude
the cases it knows it fails.

This module provides three implementations of the
:class:`RotationSeedSource` protocol:

* :class:`CronSeedSource`           — production. Derives the seed
                                      from a stable time-bucket
                                      (UTC date by default). The
                                      agent sees only the value the
                                      source emits; it cannot
                                      influence which value comes
                                      next.
* :class:`InjectedSeedSource`       — test/dev. Wraps a fixed seed
                                      so unit tests are reproducible.
* :class:`AgentControlledSeedSource` — FORBIDDEN at production. Lets
                                      a caller pick the seed
                                      directly. Surfaces the
                                      anti-pattern explicitly so
                                      configuration-validation
                                      tooling can blocklist it
                                      (see :func:`is_agent_controlled`).

The :class:`CronSeedSource` uses a hash of the time bucket plus an
operator-supplied salt. The salt rotates separately (e.g. quarterly,
through a CloudFormation stack update) so even an attacker who
predicts the time bucket can't precompute seed values without the
salt.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Protocol


class SeedBucketGranularity(Enum):
    """How often the cron seed rotates."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class RotationSeedSource(Protocol):
    """Anything that can produce a seed for the oracle's holdout sampler."""

    def current_seed(self) -> int: ...

    @property
    def is_agent_controllable(self) -> bool: ...


@dataclass(frozen=True)
class CronSeedSource:
    """Production seed source — time-bucketed + operator-salted.

    The seed is deterministic for a given (bucket, salt) pair so two
    Oracle invocations within the same time bucket pick the same
    holdout. Bucket rotation guarantees the holdout shifts over time
    without any agent involvement.

    Granularity is operator-tunable. ADR-088 default is DAILY; a
    deployment that wants more frequent rotation (lab/pre-prod) can
    set HOURLY. WEEKLY is the right choice for batch evaluation
    cycles.
    """

    salt: str
    granularity: SeedBucketGranularity = SeedBucketGranularity.DAILY
    # Optional injectable clock so tests aren't time-flaky. Production
    # passes None and we use the real UTC clock.
    clock: "datetime | None" = None

    def __post_init__(self) -> None:
        if not self.salt:
            raise ValueError("CronSeedSource.salt is required (operator-supplied)")

    def current_seed(self) -> int:
        bucket = self._current_bucket()
        digest = hashlib.sha256(f"{self.salt}|{bucket}".encode("utf-8")).digest()
        # Take the first 8 bytes as a 64-bit unsigned integer; truncate to 32-bit
        # so callers using Python's ``random.Random(seed)`` see a sensible space.
        return int.from_bytes(digest[:4], "big")

    def _current_bucket(self) -> str:
        now = self.clock or datetime.now(timezone.utc)
        if self.granularity is SeedBucketGranularity.HOURLY:
            return now.strftime("%Y-%m-%dT%H")
        if self.granularity is SeedBucketGranularity.DAILY:
            return now.strftime("%Y-%m-%d")
        # Weekly — ISO calendar week
        iso = now.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"

    @property
    def is_agent_controllable(self) -> bool:
        return False


@dataclass(frozen=True)
class InjectedSeedSource:
    """Test/dev seed source. Same seed returned every call."""

    seed: int

    def current_seed(self) -> int:
        return self.seed

    @property
    def is_agent_controllable(self) -> bool:
        # Injection is allowed in tests — but the configuration
        # validator must reject it in production deployments.
        return True


@dataclass(frozen=True)
class AgentControlledSeedSource:
    """**FORBIDDEN AT PRODUCTION.** Allows runtime mutation.

    Existence is intentional: the configuration validator
    (:func:`is_agent_controlled`) returns True for this class, so
    pre-flight checks can block any deployment that wires it.
    """

    initial_seed: int

    def current_seed(self) -> int:
        return self.initial_seed

    @property
    def is_agent_controllable(self) -> bool:
        return True


def is_agent_controlled(source: RotationSeedSource) -> bool:
    """True iff the source allows agents to influence the seed.

    Configuration-validation tooling calls this on every deployed
    OracleService; CronSeedSource returns False, the others return
    True. A production deployment must reject any non-cron source.
    """
    return source.is_agent_controllable
