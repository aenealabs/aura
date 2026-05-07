"""GoldenTestSet — the frozen 400+ case canonical evaluation suite.

The golden set is mostly read-only. Mutation is restricted to the
quarterly rotation pipeline via :mod:`rotation`, which enforces the
ADR-088 invariants:

  * Total cases >= 400 always.
  * Per-domain minimums met always.
  * No more than 10% of cases rotated per cycle (50% cap on net
    change; production drift would otherwise destroy longitudinal
    comparability).
  * Two human approvals required to materialise a rotation.

This module exposes the read-only set and the validation helpers
the oracle service uses on each evaluation. The mutation gate
(rotation) lives in its own module so the read path is
side-effect-free and trivial to cache.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from src.services.model_assurance.frozen_oracle.contracts import (
    DOMAIN_MINIMUMS,
    GOLDEN_SET_MINIMUM,
    GoldenSetIntegrityError,
    GoldenTestCase,
    TestCaseDomain,
)


@dataclass(frozen=True)
class GoldenTestSet:
    """An immutable ordered collection of :class:`GoldenTestCase`.

    Validation runs at construction so callers can never hold an
    invalid set. The ``cases_by_domain`` index is built post-hoc
    via ``__post_init__`` for O(1) per-domain lookup.
    """

    cases: tuple[GoldenTestCase, ...]
    version: str = ""  # semantic version, e.g. "2026.05.0"

    def __post_init__(self) -> None:
        if not self.cases:
            raise GoldenSetIntegrityError(
                "GoldenTestSet must contain at least one case"
            )
        ids = [c.case_id for c in self.cases]
        duplicates = [cid for cid, n in Counter(ids).items() if n > 1]
        if duplicates:
            raise GoldenSetIntegrityError(
                "duplicate case_ids in golden set",
                detail=f"first 5: {duplicates[:5]}",
            )
        # Build per-domain index
        index: dict[TestCaseDomain, tuple[GoldenTestCase, ...]] = {}
        for domain in TestCaseDomain:
            index[domain] = tuple(c for c in self.cases if c.domain is domain)
        object.__setattr__(self, "_by_domain", index)

    # -------------------------------------------------- read accessors

    def __len__(self) -> int:
        return len(self.cases)

    def __iter__(self):
        return iter(self.cases)

    def get(self, case_id: str) -> GoldenTestCase | None:
        for c in self.cases:
            if c.case_id == case_id:
                return c
        return None

    def by_domain(self, domain: TestCaseDomain) -> tuple[GoldenTestCase, ...]:
        return self._by_domain.get(domain, ())  # type: ignore[attr-defined]

    def domain_counts(self) -> dict[TestCaseDomain, int]:
        return {d: len(self.by_domain(d)) for d in TestCaseDomain}

    @property
    def case_ids(self) -> frozenset[str]:
        return frozenset(c.case_id for c in self.cases)

    # -------------------------------------------------- size validation

    def validate_minimums(self) -> None:
        """Enforce the 400-case + per-domain minimums.

        Called by the oracle service before each evaluation begins.
        Raises on any shortfall so the operator gets an explicit
        error rather than a silent degradation.
        """
        total = len(self.cases)
        if total < GOLDEN_SET_MINIMUM:
            raise GoldenSetIntegrityError(
                f"golden set below minimum: have {total}, "
                f"need >= {GOLDEN_SET_MINIMUM}",
            )
        for domain, minimum in DOMAIN_MINIMUMS.items():
            n = len(self.by_domain(domain))
            if n < minimum:
                raise GoldenSetIntegrityError(
                    f"domain {domain.value} below minimum: "
                    f"have {n}, need >= {minimum}",
                )

    # -------------------------------------------------- selection

    def holdout_sample(
        self,
        *,
        rate: float,
        seed: int,
    ) -> tuple[tuple[str, ...], tuple[GoldenTestCase, ...]]:
        """Return ``(holdout_case_ids, evaluation_cases)``.

        The holdout is randomly sampled but reproducible: same seed
        → same holdout. ``rate`` is in [0, 0.5] so we never withhold
        more than half the set. Per ADR-088 anti-Goodharting, the
        rotation schedule lives outside the agent loop — the seed
        comes from a cron-managed source, never an agent under
        optimisation pressure.
        """
        if not 0.0 <= rate <= 0.5:
            raise ValueError(
                f"holdout rate must be in [0, 0.5]; got {rate}"
            )
        # Reduce per-domain to keep balance — withhold rate*|domain|
        # from each domain rather than rate*|set| globally so the
        # remaining set still satisfies per-domain minimums (when
        # the configured minimums leave headroom).
        rng = random.Random(seed)
        holdout_ids: list[str] = []
        evaluation: list[GoldenTestCase] = []
        for domain in TestCaseDomain:
            cases = list(self.by_domain(domain))
            n_hold = int(round(len(cases) * rate))
            if n_hold > 0:
                rng.shuffle(cases)
                held = cases[:n_hold]
                rest = cases[n_hold:]
                holdout_ids.extend(c.case_id for c in held)
                evaluation.extend(rest)
            else:
                evaluation.extend(cases)
        return tuple(holdout_ids), tuple(evaluation)


def build_test_set(
    cases: Iterable[GoldenTestCase], version: str = ""
) -> GoldenTestSet:
    """Convenience constructor that materialises the iterable once."""
    return GoldenTestSet(cases=tuple(cases), version=version)
