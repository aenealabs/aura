"""Bidirectional requirements traceability (ADR-085 Phase 4).

Public surface for the HLR↔LLR↔Code↔Test traceability graph plus the
DO-178C lifecycle-data template generators (PSAC/SDP/SVP/SQAP/SAS).

The service is store-agnostic: pass an :class:`InMemoryRequirementStore`
for tests and dev demos, or :class:`NeptuneRequirementStore` for
production.
"""

from src.services.verification_envelope.traceability.contracts import (
    Artefact,
    ArtefactType,
    Requirement,
    RequirementType,
    TraceabilityGap,
    TraceabilityReport,
    TraceEdge,
    TraceEdgeType,
)
from src.services.verification_envelope.traceability.in_memory_store import (
    InMemoryRequirementStore,
)
from src.services.verification_envelope.traceability.lifecycle_data import (
    LifecycleContext,
    LifecycleDataGenerator,
    LifecycleDocument,
)
from src.services.verification_envelope.traceability.neptune_store import (
    NeptuneRequirementStore,
)
from src.services.verification_envelope.traceability.traceability_service import (
    TraceabilityService,
)

__all__ = [
    "Artefact",
    "ArtefactType",
    "InMemoryRequirementStore",
    "LifecycleContext",
    "LifecycleDataGenerator",
    "LifecycleDocument",
    "NeptuneRequirementStore",
    "Requirement",
    "RequirementType",
    "TraceEdge",
    "TraceEdgeType",
    "TraceabilityGap",
    "TraceabilityReport",
    "TraceabilityService",
]
