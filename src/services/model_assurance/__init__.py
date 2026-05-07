"""Project Aura - Continuous Model Assurance (ADR-088).

Continuous evaluation of foundation-model candidates against Aura's
production workloads, gated by deterministic CGE scoring and mandatory
HITL approval. The package is intentionally narrow in v1 — it contains
the Adapter Registry, the model_assurance CGE domain, and the Scout
Agent. Provenance, the Frozen Reference Oracle, and the Step Functions
pipeline ship in Phase 2.

Public surface (Phase 1):

* :class:`ModelAdapter` — declarative model capability descriptor.
* :class:`AdapterRegistry` — registry + disqualification check.
* :data:`BUILTIN_ADAPTERS` — seeded with current Bedrock models.

Future additions (Phase 1.3, 1.4):

* ``model_assurance`` CGE domain with the 6 evaluation axes.
* Scout Agent for Bedrock candidate discovery.
"""

from __future__ import annotations

from .adapter_registry import (
    BUILTIN_ADAPTERS,
    AdapterRegistry,
    DisqualificationReason,
    ModelAdapter,
    ModelArchitecture,
    ModelProvider,
    ModelRequirements,
    TokenizerType,
)
from .axes import (
    AXIS_DEFINITIONS,
    AXIS_DEFINITIONS_BY_AXIS,
    AxisDefinition,
    ModelAssuranceAxis,
    default_floors,
    default_weights,
)
from .scoring import (
    AxisScore,
    ModelAssuranceEvaluator,
    ModelAssuranceResult,
    ModelAssuranceVerdict,
    make_incumbent,
    perfect_axis_scores,
)

__all__ = [
    # Adapter Registry
    "AdapterRegistry",
    "BUILTIN_ADAPTERS",
    "DisqualificationReason",
    "ModelAdapter",
    "ModelArchitecture",
    "ModelProvider",
    "ModelRequirements",
    "TokenizerType",
    # 6-axis assurance domain
    "AXIS_DEFINITIONS",
    "AXIS_DEFINITIONS_BY_AXIS",
    "AxisDefinition",
    "ModelAssuranceAxis",
    "default_floors",
    "default_weights",
    # Scoring
    "AxisScore",
    "ModelAssuranceEvaluator",
    "ModelAssuranceResult",
    "ModelAssuranceVerdict",
    "make_incumbent",
    "perfect_axis_scores",
]
