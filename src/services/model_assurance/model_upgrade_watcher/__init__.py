"""Model-upgrade consensus re-validation watcher (issue #212).

When the configured Bedrock model version bumps for any Aura tier,
the statistical convergence properties of ADR-085's N-of-M consensus
may shift. This module detects bumps, gates DAL A/B auto-promotion
behind an SSM-backed feature flag, triggers the Frozen Reference
Oracle (ADR-088) to re-run its reference cases against the new model,
and either clears the flag (re-run pass) or opens a HITL incident
(re-run fail).
"""

from src.services.model_assurance.model_upgrade_watcher.contracts import (
    BedrockModelVersion,
    ModelUpgradeEvent,
    RevalidationOutcome,
    RevalidationStatus,
)
from src.services.model_assurance.model_upgrade_watcher.coordinator import (
    RevalidationCoordinator,
)
from src.services.model_assurance.model_upgrade_watcher.ports import (
    BedrockModelRegistryPort,
    HitlIncidentPort,
    MetricEmitterPort,
    OracleRerunPort,
    RevalidationFlagPort,
)
from src.services.model_assurance.model_upgrade_watcher.watcher import (
    ModelVersionWatcher,
)

__all__ = [
    "BedrockModelRegistryPort",
    "BedrockModelVersion",
    "HitlIncidentPort",
    "MetricEmitterPort",
    "ModelUpgradeEvent",
    "ModelVersionWatcher",
    "OracleRerunPort",
    "RevalidationCoordinator",
    "RevalidationFlagPort",
    "RevalidationOutcome",
    "RevalidationStatus",
]
