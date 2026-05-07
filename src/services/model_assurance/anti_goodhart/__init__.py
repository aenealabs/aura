"""ADR-088 Phase 3.1 — Anti-Goodharting controls."""

from __future__ import annotations

from .augmentation import (
    AdversarialAugmentation,
    CaseProposal,
    DedupReport,
)
from .seed_source import (
    AgentControlledSeedSource,
    CronSeedSource,
    InjectedSeedSource,
    RotationSeedSource,
    SeedBucketGranularity,
    is_agent_controlled,
)
from .spot_check_sampler import (
    DEFAULT_SPOT_CHECK_RATE,
    SpotCheckSample,
    SpotCheckSamplingPlan,
    build_sampling_plan,
)

__all__ = [
    "AdversarialAugmentation",
    "CaseProposal",
    "DedupReport",
    "AgentControlledSeedSource",
    "CronSeedSource",
    "InjectedSeedSource",
    "RotationSeedSource",
    "SeedBucketGranularity",
    "is_agent_controlled",
    "DEFAULT_SPOT_CHECK_RATE",
    "SpotCheckSample",
    "SpotCheckSamplingPlan",
    "build_sampling_plan",
]
