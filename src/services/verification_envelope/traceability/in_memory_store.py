"""Project Aura - In-memory requirement store (ADR-085 Phase 4).

Pure-Python backend for the traceability service. Used in tests and
for dev demos; production deployments swap in
:class:`NeptuneRequirementStore` when the Neptune cluster is
provisioned (Phase 5 infrastructure).

Thread safety: not currently a concern because the DVE pipeline
serialises traceability writes per-patch. If concurrent writes are
ever needed, wrap the public methods with :class:`asyncio.Lock`.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterable

from src.services.verification_envelope.traceability.contracts import (
    Artefact,
    ArtefactType,
    Requirement,
    RequirementType,
    TraceEdge,
    TraceEdgeType,
)

logger = logging.getLogger(__name__)


class InMemoryRequirementStore:
    """In-memory backend for the traceability service."""

    def __init__(self) -> None:
        self._requirements: dict[str, Requirement] = {}
        self._artefacts: dict[str, Artefact] = {}
        # adjacency_out[node_id] = list of edges originating from node_id.
        self._adj_out: dict[str, list[TraceEdge]] = defaultdict(list)
        # adjacency_in[node_id] = list of edges pointing at node_id.
        self._adj_in: dict[str, list[TraceEdge]] = defaultdict(list)

    # ------------------------------------------------------- requirements

    async def upsert_requirement(self, requirement: Requirement) -> None:
        if requirement.requirement_id in self._artefacts:
            raise ValueError(
                f"id collision: {requirement.requirement_id} already an artefact"
            )
        self._requirements[requirement.requirement_id] = requirement

    async def get_requirement(self, requirement_id: str) -> Requirement | None:
        return self._requirements.get(requirement_id)

    async def list_requirements(
        self, *, type_filter: RequirementType | None = None
    ) -> tuple[Requirement, ...]:
        items = self._requirements.values()
        if type_filter is not None:
            items = (r for r in items if r.type is type_filter)
        return tuple(sorted(items, key=lambda r: r.requirement_id))

    # ---------------------------------------------------------- artefacts

    async def upsert_artefact(self, artefact: Artefact) -> None:
        if artefact.artefact_id in self._requirements:
            raise ValueError(
                f"id collision: {artefact.artefact_id} already a requirement"
            )
        self._artefacts[artefact.artefact_id] = artefact

    async def get_artefact(self, artefact_id: str) -> Artefact | None:
        return self._artefacts.get(artefact_id)

    async def list_artefacts(
        self, *, type_filter: ArtefactType | None = None
    ) -> tuple[Artefact, ...]:
        items = self._artefacts.values()
        if type_filter is not None:
            items = (a for a in items if a.type is type_filter)
        return tuple(sorted(items, key=lambda a: a.artefact_id))

    # -------------------------------------------------------------- edges

    async def add_edge(self, edge: TraceEdge) -> None:
        if not self._exists(edge.source_id):
            raise ValueError(f"unknown source node: {edge.source_id}")
        if not self._exists(edge.target_id):
            raise ValueError(f"unknown target node: {edge.target_id}")
        self._adj_out[edge.source_id].append(edge)
        self._adj_in[edge.target_id].append(edge)

    async def outgoing_edges(
        self,
        node_id: str,
        *,
        type_filter: TraceEdgeType | None = None,
    ) -> tuple[TraceEdge, ...]:
        edges = self._adj_out.get(node_id, [])
        if type_filter is not None:
            edges = [e for e in edges if e.type is type_filter]
        return tuple(edges)

    async def incoming_edges(
        self,
        node_id: str,
        *,
        type_filter: TraceEdgeType | None = None,
    ) -> tuple[TraceEdge, ...]:
        edges = self._adj_in.get(node_id, [])
        if type_filter is not None:
            edges = [e for e in edges if e.type is type_filter]
        return tuple(edges)

    async def all_edges(self) -> tuple[TraceEdge, ...]:
        out: list[TraceEdge] = []
        for edges in self._adj_out.values():
            out.extend(edges)
        return tuple(out)

    # -------------------------------------------------------- diagnostics

    async def stats(self) -> dict[str, int]:
        return {
            "requirements": len(self._requirements),
            "artefacts": len(self._artefacts),
            "edges": sum(len(e) for e in self._adj_out.values()),
        }

    # ----------------------------------------------------------- internals

    def _exists(self, node_id: str) -> bool:
        return (
            node_id in self._requirements or node_id in self._artefacts
        )
