"""Project Aura - Traceability service (ADR-085 Phase 4).

Public surface for managing the HLR↔LLR↔Code↔Test traceability graph
and producing :class:`TraceabilityReport`s for the auditor + lifecycle
data templates.

The service is store-agnostic: pass an :class:`InMemoryRequirementStore`
for tests and dev demos, or :class:`NeptuneRequirementStore` for
production. All public methods are ``async`` so the API matches the
backing store's interface and the gate orchestrator can call into
this service without blocking the event loop.
"""

from __future__ import annotations

import logging
from typing import Iterable, Protocol

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

logger = logging.getLogger(__name__)


class _RequirementStore(Protocol):
    """Backend protocol — both in-memory and Neptune adapters satisfy it."""

    async def upsert_requirement(self, requirement: Requirement) -> None: ...
    async def get_requirement(
        self, requirement_id: str
    ) -> Requirement | None: ...
    async def list_requirements(
        self, *, type_filter: RequirementType | None = None
    ) -> tuple[Requirement, ...]: ...
    async def upsert_artefact(self, artefact: Artefact) -> None: ...
    async def get_artefact(self, artefact_id: str) -> Artefact | None: ...
    async def list_artefacts(
        self, *, type_filter: ArtefactType | None = None
    ) -> tuple[Artefact, ...]: ...
    async def add_edge(self, edge: TraceEdge) -> None: ...
    async def outgoing_edges(
        self,
        node_id: str,
        *,
        type_filter: TraceEdgeType | None = None,
    ) -> tuple[TraceEdge, ...]: ...
    async def incoming_edges(
        self,
        node_id: str,
        *,
        type_filter: TraceEdgeType | None = None,
    ) -> tuple[TraceEdge, ...]: ...
    async def all_edges(self) -> tuple[TraceEdge, ...]: ...
    async def stats(self) -> dict[str, int]: ...


class TraceabilityService:
    """Bidirectional requirements traceability service."""

    def __init__(self, store: _RequirementStore) -> None:
        self._store = store

    # ------------------------------------------------------------- writes

    async def add_hlr(
        self,
        *,
        requirement_id: str,
        title: str,
        description: str,
        dal_level: str = "DEFAULT",
        metadata: Iterable[tuple[str, str]] = (),
    ) -> Requirement:
        req = Requirement(
            requirement_id=requirement_id,
            type=RequirementType.HLR,
            title=title,
            description=description,
            dal_level=dal_level,
            metadata=tuple(metadata),
        )
        await self._store.upsert_requirement(req)
        return req

    async def add_llr(
        self,
        *,
        requirement_id: str,
        title: str,
        description: str,
        derived_from: Iterable[str],
        dal_level: str = "DEFAULT",
        metadata: Iterable[tuple[str, str]] = (),
    ) -> Requirement:
        parent_ids = tuple(derived_from)
        req = Requirement(
            requirement_id=requirement_id,
            type=RequirementType.LLR,
            title=title,
            description=description,
            dal_level=dal_level,
            parent_ids=parent_ids,
            metadata=tuple(metadata),
        )
        await self._store.upsert_requirement(req)
        # Add DERIVED_FROM edges for each parent.
        for parent_id in parent_ids:
            await self._store.add_edge(
                TraceEdge(
                    source_id=requirement_id,
                    target_id=parent_id,
                    type=TraceEdgeType.DERIVED_FROM,
                )
            )
        return req

    async def add_code(
        self,
        *,
        artefact_id: str,
        title: str,
        location: str,
        traces_to: Iterable[str] = (),
        metadata: Iterable[tuple[str, str]] = (),
    ) -> Artefact:
        art = Artefact(
            artefact_id=artefact_id,
            type=ArtefactType.CODE,
            title=title,
            location=location,
            metadata=tuple(metadata),
        )
        await self._store.upsert_artefact(art)
        for req_id in traces_to:
            await self._store.add_edge(
                TraceEdge(
                    source_id=artefact_id,
                    target_id=req_id,
                    type=TraceEdgeType.TRACES_TO,
                )
            )
        return art

    async def add_test(
        self,
        *,
        artefact_id: str,
        title: str,
        location: str,
        verifies: Iterable[str] = (),
        metadata: Iterable[tuple[str, str]] = (),
    ) -> Artefact:
        art = Artefact(
            artefact_id=artefact_id,
            type=ArtefactType.TEST,
            title=title,
            location=location,
            metadata=tuple(metadata),
        )
        await self._store.upsert_artefact(art)
        # Verification is captured as a Requirement → Test edge so the
        # canonical query "what tests verify this requirement?" walks
        # outgoing VERIFIED_BY edges from the requirement.
        for req_id in verifies:
            await self._store.add_edge(
                TraceEdge(
                    source_id=req_id,
                    target_id=artefact_id,
                    type=TraceEdgeType.VERIFIED_BY,
                )
            )
        return art

    async def link(
        self,
        *,
        source_id: str,
        target_id: str,
        edge_type: TraceEdgeType,
        metadata: Iterable[tuple[str, str]] = (),
    ) -> TraceEdge:
        edge = TraceEdge(
            source_id=source_id,
            target_id=target_id,
            type=edge_type,
            metadata=tuple(metadata),
        )
        await self._store.add_edge(edge)
        return edge

    # -------------------------------------------------------------- reads

    async def parents_of(self, requirement_id: str) -> tuple[Requirement, ...]:
        """HLR(s) an LLR derives from."""
        edges = await self._store.outgoing_edges(
            requirement_id, type_filter=TraceEdgeType.DERIVED_FROM
        )
        out: list[Requirement] = []
        for edge in edges:
            req = await self._store.get_requirement(edge.target_id)
            if req is not None:
                out.append(req)
        return tuple(out)

    async def children_of(self, requirement_id: str) -> tuple[Requirement, ...]:
        """LLR(s) derived from an HLR."""
        edges = await self._store.incoming_edges(
            requirement_id, type_filter=TraceEdgeType.DERIVED_FROM
        )
        out: list[Requirement] = []
        for edge in edges:
            req = await self._store.get_requirement(edge.source_id)
            if req is not None:
                out.append(req)
        return tuple(out)

    async def implementing_code(
        self, requirement_id: str
    ) -> tuple[Artefact, ...]:
        """Source artefacts that TRACES_TO the given requirement."""
        edges = await self._store.incoming_edges(
            requirement_id, type_filter=TraceEdgeType.TRACES_TO
        )
        out: list[Artefact] = []
        for edge in edges:
            art = await self._store.get_artefact(edge.source_id)
            if art is not None and art.type is ArtefactType.CODE:
                out.append(art)
        return tuple(out)

    async def verifying_tests(
        self, requirement_id: str
    ) -> tuple[Artefact, ...]:
        """Test artefacts the requirement is VERIFIED_BY."""
        edges = await self._store.outgoing_edges(
            requirement_id, type_filter=TraceEdgeType.VERIFIED_BY
        )
        out: list[Artefact] = []
        for edge in edges:
            art = await self._store.get_artefact(edge.target_id)
            if art is not None and art.type is ArtefactType.TEST:
                out.append(art)
        return tuple(out)

    # --------------------------------------------------------- gap analysis

    async def gap_report(self) -> TraceabilityReport:
        """Walk the graph and return a TraceabilityReport.

        Forward gaps:
          - HLR with no derived LLRs.
          - LLR with no implementing code.
          - Requirement with no verifying tests.

        Reverse gaps:
          - Code artefact with no TRACES_TO edge.
          - Test artefact with no requirement that VERIFIED_BY it.
        """
        forward: list[TraceabilityGap] = []
        reverse: list[TraceabilityGap] = []

        all_reqs = await self._store.list_requirements()
        all_arts = await self._store.list_artefacts()

        for req in all_reqs:
            implementing = await self.implementing_code(req.requirement_id)
            verifying = await self.verifying_tests(req.requirement_id)
            children = await self.children_of(req.requirement_id)

            if req.type is RequirementType.HLR and not children:
                forward.append(
                    TraceabilityGap.forward(
                        node_id=req.requirement_id,
                        node_type=RequirementType.HLR.value,
                        description="HLR has no derived LLRs",
                    )
                )
            if req.type is RequirementType.LLR and not implementing:
                forward.append(
                    TraceabilityGap.forward(
                        node_id=req.requirement_id,
                        node_type=RequirementType.LLR.value,
                        description="LLR has no implementing code",
                    )
                )
            if not verifying:
                forward.append(
                    TraceabilityGap.forward(
                        node_id=req.requirement_id,
                        node_type=req.type.value,
                        description="requirement has no verifying tests",
                    )
                )

        for art in all_arts:
            if art.type is ArtefactType.CODE:
                outgoing = await self._store.outgoing_edges(
                    art.artefact_id,
                    type_filter=TraceEdgeType.TRACES_TO,
                )
                if not outgoing:
                    reverse.append(
                        TraceabilityGap.reverse(
                            node_id=art.artefact_id,
                            node_type=ArtefactType.CODE.value,
                            description="orphan code: no TRACES_TO requirement",
                        )
                    )
            elif art.type is ArtefactType.TEST:
                incoming = await self._store.incoming_edges(
                    art.artefact_id,
                    type_filter=TraceEdgeType.VERIFIED_BY,
                )
                if not incoming:
                    reverse.append(
                        TraceabilityGap.reverse(
                            node_id=art.artefact_id,
                            node_type=ArtefactType.TEST.value,
                            description="orphan test: no requirement VERIFIED_BY it",
                        )
                    )

        stats = await self._store.stats()
        return TraceabilityReport(
            forward_gaps=tuple(forward),
            reverse_gaps=tuple(reverse),
            requirement_count=stats["requirements"],
            artefact_count=stats["artefacts"],
            edge_count=stats["edges"],
        )
