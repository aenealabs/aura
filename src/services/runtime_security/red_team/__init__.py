"""
Project Aura - Automated Red Teaming Engine

Adversarial testing against live agent deployments using the
AURA-ATT&CK taxonomy of 75 techniques across 8 categories.

Based on ADR-083: Runtime Agent Security Platform
"""

from .engine import (
    RedTeamCampaign,
    RedTeamEngine,
    RedTeamResult,
    TestOutcome,
    get_red_team_engine,
    reset_red_team_engine,
)
from .taxonomy import (
    AURA_ATTACK_TAXONOMY,
    AttackCategory,
    AttackTechnique,
    TechniqueComplexity,
    get_technique_by_id,
    get_techniques_by_category,
)

__all__ = [
    # Taxonomy
    "AttackCategory",
    "AttackTechnique",
    "TechniqueComplexity",
    "AURA_ATTACK_TAXONOMY",
    "get_techniques_by_category",
    "get_technique_by_id",
    # Engine
    "RedTeamEngine",
    "RedTeamResult",
    "RedTeamCampaign",
    "TestOutcome",
    "get_red_team_engine",
    "reset_red_team_engine",
]
