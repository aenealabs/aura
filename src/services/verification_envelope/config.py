"""Project Aura - DVE configuration.

Centralises tunable parameters for the consensus engine. Two preset
constructors are provided so tests and production avoid having to
restate the full parameter set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class DVEConfig:
    """Deterministic Verification Envelope configuration."""

    # ---------------------------------------------------- consensus

    consensus_n: int = 3  # Total generations per task
    consensus_m: int = 2  # Generations that must converge for acceptance
    consensus_temperature: float = 0.2  # Lower = more reproducible
    consensus_max_concurrency: int = 3  # Parallel generation cap
    consensus_timeout_seconds: float = 90.0

    # ---------------------------------- equivalence-check thresholds

    embedding_cosine_threshold: float = 0.97  # Slow-path threshold
    enable_embedding_fallback: bool = True

    # ---------------------------------- audit + telemetry

    audit_record_prefix: str = "dve-consensus"
    log_canonical_dumps: bool = False  # Off by default; can leak source

    # ---------------------------------- policy gating

    # When True, generation continues even after M-of-N convergence
    # (useful for telemetry/A-B testing). Default False — short-circuit
    # as soon as consensus is reached.
    exhaust_all_n_for_telemetry: bool = False

    @classmethod
    def for_testing(cls) -> "DVEConfig":
        """Tight, fast config for unit tests."""
        return cls(
            consensus_n=3,
            consensus_m=2,
            consensus_temperature=0.0,
            consensus_max_concurrency=3,
            consensus_timeout_seconds=10.0,
            embedding_cosine_threshold=0.97,
            enable_embedding_fallback=True,
            audit_record_prefix="dve-test",
            log_canonical_dumps=False,
            exhaust_all_n_for_telemetry=False,
        )

    @classmethod
    def for_production(cls) -> "DVEConfig":
        """Production default. N=3 / M=2 is the ADR-085 recommendation."""
        return cls(
            consensus_n=int(os.environ.get("DVE_CONSENSUS_N", "3")),
            consensus_m=int(os.environ.get("DVE_CONSENSUS_M", "2")),
            consensus_temperature=float(
                os.environ.get("DVE_CONSENSUS_TEMP", "0.2")
            ),
            consensus_max_concurrency=int(
                os.environ.get("DVE_CONSENSUS_MAX_CONCURRENCY", "3")
            ),
            consensus_timeout_seconds=float(
                os.environ.get("DVE_CONSENSUS_TIMEOUT_SEC", "90.0")
            ),
            embedding_cosine_threshold=float(
                os.environ.get("DVE_EMBEDDING_COSINE_THRESHOLD", "0.97")
            ),
            enable_embedding_fallback=os.environ.get(
                "DVE_ENABLE_EMBEDDING_FALLBACK", "true"
            ).lower()
            in ("1", "true", "yes", "on"),
            audit_record_prefix="dve-consensus",
            log_canonical_dumps=False,
            exhaust_all_n_for_telemetry=os.environ.get(
                "DVE_EXHAUST_TELEMETRY", "false"
            ).lower()
            in ("1", "true", "yes", "on"),
        )

    def __post_init__(self) -> None:
        if self.consensus_n < 1:
            raise ValueError("consensus_n must be >= 1")
        if self.consensus_m < 1:
            raise ValueError("consensus_m must be >= 1")
        if self.consensus_m > self.consensus_n:
            raise ValueError(
                f"consensus_m ({self.consensus_m}) cannot exceed "
                f"consensus_n ({self.consensus_n})"
            )
        if not 0.0 <= self.embedding_cosine_threshold <= 1.0:
            raise ValueError(
                "embedding_cosine_threshold must be in [0.0, 1.0]"
            )
        if self.consensus_temperature < 0.0:
            raise ValueError("consensus_temperature must be >= 0")


# ---------------------------------------------------- DAL policy mapping

DALLevel = Literal["DAL_A", "DAL_B", "DAL_C", "DAL_D", "DEFAULT"]
"""Design Assurance Level identifier per DO-178C section 2.2.2."""
