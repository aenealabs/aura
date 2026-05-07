"""Project Aura - Neptune-backed requirement store (ADR-085 Phase 4).

Adapter that maps the traceability data model onto the Neptune
property-graph schema described in ADR-085 §"Neptune Requirements
Traceability Schema":

* Vertex labels: ``Requirement`` (with ``type=HLR|LLR``), ``Artefact``
  (with ``type=CODE|TEST|REVIEW``).
* Edge labels: ``DERIVED_FROM``, ``TRACES_TO``, ``VERIFIED_BY``,
  ``REVIEWED_BY``.

Phase 4 ships the adapter shape and a Gremlin query builder; the live
Neptune connection is bound on demand via the project's
``neptune_graph_service``. When that service is unavailable (no
endpoint configured, no boto3 credentials, mock mode), the adapter
falls back to an :class:`InMemoryRequirementStore` so the pipeline
keeps working in dev and air-gapped builds.
"""

from __future__ import annotations

import logging
from typing import Any

from src.services.verification_envelope.traceability.contracts import (
    Artefact,
    ArtefactType,
    Requirement,
    RequirementType,
    TraceEdge,
    TraceEdgeType,
)
from src.services.verification_envelope.traceability.in_memory_store import (
    InMemoryRequirementStore,
)

logger = logging.getLogger(__name__)


class NeptuneRequirementStore:
    """Neptune-backed requirement store with in-memory fallback."""

    def __init__(
        self,
        *,
        neptune_client: Any | None = None,
        fallback_store: InMemoryRequirementStore | None = None,
    ) -> None:
        self._client = neptune_client
        self._fallback = fallback_store or InMemoryRequirementStore()

    @property
    def is_live(self) -> bool:
        """True when a real Neptune client is wired up."""
        return self._client is not None

    @property
    def fallback(self) -> InMemoryRequirementStore:
        """Expose the fallback store so tests can introspect it."""
        return self._fallback

    # ------------------------------------------------------- requirements

    async def upsert_requirement(self, requirement: Requirement) -> None:
        if not self.is_live:
            await self._fallback.upsert_requirement(requirement)
            return
        await self._gremlin_upsert_requirement(requirement)

    async def get_requirement(self, requirement_id: str) -> Requirement | None:
        if not self.is_live:
            return await self._fallback.get_requirement(requirement_id)
        return await self._gremlin_get_requirement(requirement_id)

    async def list_requirements(
        self, *, type_filter: RequirementType | None = None
    ) -> tuple[Requirement, ...]:
        if not self.is_live:
            return await self._fallback.list_requirements(type_filter=type_filter)
        return await self._gremlin_list_requirements(type_filter)

    # ---------------------------------------------------------- artefacts

    async def upsert_artefact(self, artefact: Artefact) -> None:
        if not self.is_live:
            await self._fallback.upsert_artefact(artefact)
            return
        await self._gremlin_upsert_artefact(artefact)

    async def get_artefact(self, artefact_id: str) -> Artefact | None:
        if not self.is_live:
            return await self._fallback.get_artefact(artefact_id)
        return await self._gremlin_get_artefact(artefact_id)

    async def list_artefacts(
        self, *, type_filter: ArtefactType | None = None
    ) -> tuple[Artefact, ...]:
        if not self.is_live:
            return await self._fallback.list_artefacts(type_filter=type_filter)
        return await self._gremlin_list_artefacts(type_filter)

    # -------------------------------------------------------------- edges

    async def add_edge(self, edge: TraceEdge) -> None:
        if not self.is_live:
            await self._fallback.add_edge(edge)
            return
        await self._gremlin_add_edge(edge)

    async def outgoing_edges(
        self,
        node_id: str,
        *,
        type_filter: TraceEdgeType | None = None,
    ) -> tuple[TraceEdge, ...]:
        if not self.is_live:
            return await self._fallback.outgoing_edges(node_id, type_filter=type_filter)
        return await self._gremlin_outgoing(node_id, type_filter)

    async def incoming_edges(
        self,
        node_id: str,
        *,
        type_filter: TraceEdgeType | None = None,
    ) -> tuple[TraceEdge, ...]:
        if not self.is_live:
            return await self._fallback.incoming_edges(node_id, type_filter=type_filter)
        return await self._gremlin_incoming(node_id, type_filter)

    async def all_edges(self) -> tuple[TraceEdge, ...]:
        if not self.is_live:
            return await self._fallback.all_edges()
        return await self._gremlin_all_edges()

    async def stats(self) -> dict[str, int]:
        if not self.is_live:
            return await self._fallback.stats()
        return await self._gremlin_stats()

    # ----------------------- Gremlin builders (Phase 5 will wire these)

    @staticmethod
    def build_upsert_vertex_query(
        label: str, vid: str, properties: dict[str, Any]
    ) -> str:
        """Return a Gremlin upsert query string for the given vertex.

        The real Neptune client (Phase 5) will execute this. Public so
        consumers can audit / diff the queries against the schema doc.
        """
        prop_steps = "".join(
            f".property('{k}', {repr(v)})" for k, v in sorted(properties.items())
        )
        return (
            f"g.V().has('{label}', 'id', '{vid}').fold().coalesce("
            f"unfold(), addV('{label}').property('id', '{vid}'))"
            f"{prop_steps}"
        )

    @staticmethod
    def build_add_edge_query(
        edge_label: str,
        source_id: str,
        target_id: str,
        properties: dict[str, Any] | None = None,
    ) -> str:
        props = ""
        if properties:
            props = "".join(
                f".property('{k}', {repr(v)})" for k, v in sorted(properties.items())
            )
        return (
            f"g.V().has('id', '{source_id}').as('s')"
            f".V().has('id', '{target_id}').as('t')"
            f".addE('{edge_label}').from('s').to('t'){props}"
        )

    # ------------------- Gremlin executors (delegate to in-memory in Phase 4)

    async def _gremlin_upsert_requirement(
        self, r: Requirement
    ) -> None:  # pragma: no cover
        # In Phase 5 this dispatches via ``self._client``. For Phase 4
        # we mirror to the fallback so the live-vs-fallback distinction
        # is observable in tests via ``is_live`` without changing data.
        await self._fallback.upsert_requirement(r)

    async def _gremlin_get_requirement(  # pragma: no cover
        self, requirement_id: str
    ) -> Requirement | None:
        return await self._fallback.get_requirement(requirement_id)

    async def _gremlin_list_requirements(  # pragma: no cover
        self, type_filter: RequirementType | None
    ) -> tuple[Requirement, ...]:
        return await self._fallback.list_requirements(type_filter=type_filter)

    async def _gremlin_upsert_artefact(self, a: Artefact) -> None:  # pragma: no cover
        await self._fallback.upsert_artefact(a)

    async def _gremlin_get_artefact(  # pragma: no cover
        self, artefact_id: str
    ) -> Artefact | None:
        return await self._fallback.get_artefact(artefact_id)

    async def _gremlin_list_artefacts(  # pragma: no cover
        self, type_filter: ArtefactType | None
    ) -> tuple[Artefact, ...]:
        return await self._fallback.list_artefacts(type_filter=type_filter)

    async def _gremlin_add_edge(self, edge: TraceEdge) -> None:  # pragma: no cover
        await self._fallback.add_edge(edge)

    async def _gremlin_outgoing(  # pragma: no cover
        self,
        node_id: str,
        type_filter: TraceEdgeType | None,
    ) -> tuple[TraceEdge, ...]:
        return await self._fallback.outgoing_edges(node_id, type_filter=type_filter)

    async def _gremlin_incoming(  # pragma: no cover
        self,
        node_id: str,
        type_filter: TraceEdgeType | None,
    ) -> tuple[TraceEdge, ...]:
        return await self._fallback.incoming_edges(node_id, type_filter=type_filter)

    async def _gremlin_all_edges(self) -> tuple[TraceEdge, ...]:  # pragma: no cover
        return await self._fallback.all_edges()

    async def _gremlin_stats(self) -> dict[str, int]:  # pragma: no cover
        return await self._fallback.stats()
