"""Graph utilities and shared contracts for Aura's GraphRAG layer.

Per ADR-090, this package owns canonical graph contracts that must
remain consistent between write paths (NeptuneGraphService) and read
paths (context_retrieval_service). Adding a new edge label or vertex
type that bypasses this package is a contract violation and is
rejected by scripts/lint_edge_labels.py.
"""

from src.services.graph.edge_labels import EdgeLabel, LegacyAlias
from src.services.graph.fqn import (
    FQNBuilder,
    FQNComponents,
    compute_fqn,
    derive_module_path,
    derive_scheme,
)

# symbol_resolver is intentionally NOT re-exported here: it depends on
# CodeEntity / CodeRelationship from src.agents.ast_parser_agent, which
# in turn imports from src.services.graph for EdgeLabel. Re-exporting
# would create a circular import. Consumers import the resolver from
# src.services.graph.symbol_resolver directly.

__all__ = [
    "EdgeLabel",
    "FQNBuilder",
    "FQNComponents",
    "LegacyAlias",
    "compute_fqn",
    "derive_module_path",
    "derive_scheme",
]
