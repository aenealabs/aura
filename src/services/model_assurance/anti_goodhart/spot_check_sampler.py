"""Human spot-check sampler (ADR-088 Phase 3.1).

Per ADR-088 §Stage 6 §Stage 7: 5% of shadow-deployment comparisons
are sampled for human review before the HITL approval UI presents
aggregate scores. Disagreements between automated metrics and
human judgement are surfaced prominently in the report (the
``has_human_disagreement`` flag on :class:`ShadowDeploymentReport`).

This module produces the *sampling list* — which cases the human
reviewer is asked to spot-check. The actual human review happens
out-of-band; the operator submits :class:`HumanSpotCheckResult`
objects back into the report-generation flow.

Sampling is:

  * Deterministic in the seed (reproducible across reruns).
  * Stratified per domain so the 5% draws fairly from each section
    of the golden set rather than concentrating on the largest
    domain.
  * Independent of the holdout set used for scoring (a case can be
    in both — the holdout is for the candidate's score; the spot-
    check is for the human's audit).
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass

from src.services.model_assurance.frozen_oracle import (
    GoldenTestCase,
    GoldenTestSet,
    TestCaseDomain,
)

logger = logging.getLogger(__name__)


# Per ADR-088 §Stage 6.
DEFAULT_SPOT_CHECK_RATE = 0.05


@dataclass(frozen=True)
class SpotCheckSample:
    """One case to be spot-checked by a human reviewer."""

    case: GoldenTestCase
    domain: TestCaseDomain


@dataclass(frozen=True)
class SpotCheckSamplingPlan:
    """The full sampling plan for one evaluation run."""

    samples: tuple[SpotCheckSample, ...]
    rate: float
    seed: int

    @property
    def case_ids(self) -> tuple[str, ...]:
        return tuple(s.case.case_id for s in self.samples)


def _stratified_sample_per_domain(
    cases: tuple[GoldenTestCase, ...],
    rate: float,
    rng: random.Random,
) -> tuple[GoldenTestCase, ...]:
    """Sample ``rate * |cases|`` from a single domain bucket."""
    if not cases:
        return ()
    n = max(1, int(round(len(cases) * rate)))
    n = min(n, len(cases))
    pool = list(cases)
    rng.shuffle(pool)
    return tuple(pool[:n])


def build_sampling_plan(
    golden_set: GoldenTestSet,
    *,
    seed: int,
    rate: float = DEFAULT_SPOT_CHECK_RATE,
) -> SpotCheckSamplingPlan:
    """Build a per-domain stratified sampling plan.

    Determinism: same (seed, rate, golden_set contents) → same plan.
    The seed is supplied by the caller (typically the same cron-
    controlled source that drives the holdout sampler) so neither
    the evaluation agent nor the HITL operator can re-roll the
    sample list.
    """
    if not 0.0 < rate <= 0.5:
        raise ValueError(f"spot-check rate must be in (0, 0.5]; got {rate}")
    rng = random.Random(seed)
    samples: list[SpotCheckSample] = []
    for domain in TestCaseDomain:
        domain_cases = golden_set.by_domain(domain)
        sampled = _stratified_sample_per_domain(domain_cases, rate, rng)
        for case in sampled:
            samples.append(SpotCheckSample(case=case, domain=domain))
    return SpotCheckSamplingPlan(
        samples=tuple(samples),
        rate=rate,
        seed=seed,
    )
