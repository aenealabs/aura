"""Graph utilities and shared contracts for Aura's GraphRAG layer.

Per ADR-090, this package owns canonical graph contracts that must
remain consistent between write paths (NeptuneGraphService) and read
paths (context_retrieval_service). Adding a new edge label or vertex
type that bypasses this package is a contract violation and is
rejected by scripts/lint_edge_labels.py.
"""

from src.services.graph.edge_labels import EdgeLabel, LegacyAlias

__all__ = ["EdgeLabel", "LegacyAlias"]
