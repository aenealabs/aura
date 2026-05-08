"""Canonical graph edge labels for Aura's GraphRAG layer.

Per ADR-090, this module is the single source of truth for edge labels
that flow between Aura's ingestion pipeline (writes) and the context
retrieval service (reads). The contract divergence that motivated
ADR-090 was that the read side queried for edge labels the write side
never produced; centralizing the label set here and enforcing it via
the lint at scripts/lint_edge_labels.py prevents recurrence.

Adding a new label requires:

  1. Add the value to EdgeLabel below.
  2. Add at least one writer that calls
     NeptuneGraphService.add_relationship(..., relationship=EdgeLabel.X).
  3. Update the read-side mapping in
     context_retrieval_service._get_relationship_types if the new label
     belongs to one of the documented query types.

The contract test asserts every EdgeLabel value has at least one
writer in the codebase.
"""

from __future__ import annotations

from enum import Enum


class EdgeLabel(str, Enum):
    """Canonical edge labels.

    Inheriting from str means EdgeLabel.CALLS is interchangeable with
    the literal "CALLS" wherever a string is expected (Gremlin queries,
    JSON serialization, log lines), so adopting the enum does not
    require changing existing call sites that pass the string through
    to Neptune.
    """

    # Structural edges (Phase 0 / pre-existing)
    CONTAINS = "CONTAINS"

    # Phase 2 — Python intra-file (deterministic)
    INHERITS = "INHERITS"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"

    # Phase 4 — Cross-file LLM-resolved (Tier 3, inferred)
    CALLS_INFERRED = "CALLS_INFERRED"

    # Phase 5 — Config-layer dependencies (ABAC-gated)
    READS_CONFIG = "READS_CONFIG"
    DEPENDS_ON_ENV = "DEPENDS_ON_ENV"
    USES_KMS_KEY = "USES_KMS_KEY"
    FEATURE_GATED_BY = "FEATURE_GATED_BY"

    # Phase 6 / ADR-083 — Runtime correlation (out of scope here, schema
    # defined so the runtime pipeline targets it without coordination)
    RUNTIME_DEPENDS_ON = "RUNTIME_DEPENDS_ON"
    CACHES_KEY = "CACHES_KEY"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Return True if value is a canonical edge label."""
        try:
            cls(value)
            return True
        except ValueError:
            return False


class LegacyAlias(str, Enum):
    """Pre-ADR-090 edge labels retained for backward compatibility.

    These labels appear in graphs ingested before this ADR shipped and
    are still emitted by code paths that have not yet migrated to
    canonical EdgeLabel values. Validation accepts them at write time
    so existing pipelines continue to function during the migration
    window; read-side query helpers expand them to canonical
    equivalents where possible.

    HAS_* labels are emitted by NeptuneGraphService.add_code_entity
    via the legacy `f"HAS_{entity_type.upper()}"` pattern. Phase 2 of
    ADR-090 replaces these with CONTAINS plus a containment_type
    property; they remain accepted here until that migration ships.
    """

    DEPENDS_ON = "DEPENDS_ON"
    HAS_CLASS = "HAS_CLASS"
    HAS_FUNCTION = "HAS_FUNCTION"
    HAS_METHOD = "HAS_METHOD"
    HAS_VARIABLE = "HAS_VARIABLE"
    HAS_IMPORT = "HAS_IMPORT"


# Read-side aliases: legacy label → canonical labels it expands to.
# Used by context_retrieval_service when queries hit graphs that were
# ingested before this ADR.
LEGACY_EXPANSIONS: dict[LegacyAlias, tuple[EdgeLabel, ...]] = {
    LegacyAlias.DEPENDS_ON: (EdgeLabel.INHERITS, EdgeLabel.IMPORTS),
    # HAS_* labels are structural parent-child edges; they expand to
    # CONTAINS for read queries that ask about containment.
    LegacyAlias.HAS_CLASS: (EdgeLabel.CONTAINS,),
    LegacyAlias.HAS_FUNCTION: (EdgeLabel.CONTAINS,),
    LegacyAlias.HAS_METHOD: (EdgeLabel.CONTAINS,),
    LegacyAlias.HAS_VARIABLE: (EdgeLabel.CONTAINS,),
    LegacyAlias.HAS_IMPORT: (EdgeLabel.CONTAINS,),
}


def is_known_label(value: str) -> bool:
    """Return True if value is a canonical EdgeLabel or a LegacyAlias.

    Used by NeptuneGraphService.add_relationship to validate edge
    labels at write time. Unknown values are rejected; adding a new
    label requires updating EdgeLabel (preferred) or LegacyAlias.
    """
    return EdgeLabel.is_valid(value) or any(
        alias.value == value for alias in LegacyAlias
    )
