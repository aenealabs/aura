"""Tests for InMemoryRequirementStore."""

from __future__ import annotations

import pytest

from src.services.verification_envelope.traceability import (
    Artefact,
    ArtefactType,
    InMemoryRequirementStore,
    Requirement,
    RequirementType,
    TraceEdge,
    TraceEdgeType,
)


def _hlr(req_id: str = "HLR-1") -> Requirement:
    return Requirement(
        requirement_id=req_id,
        type=RequirementType.HLR,
        title=f"hlr {req_id}",
        description="",
        dal_level="DAL_B",
    )


def _llr(req_id: str = "LLR-1", parent: str = "HLR-1") -> Requirement:
    return Requirement(
        requirement_id=req_id,
        type=RequirementType.LLR,
        title=f"llr {req_id}",
        description="",
        dal_level="DAL_B",
        parent_ids=(parent,),
    )


def _code(art_id: str = "code-1") -> Artefact:
    return Artefact(
        artefact_id=art_id,
        type=ArtefactType.CODE,
        title=art_id,
        location=f"src/{art_id}.py",
    )


@pytest.mark.asyncio
async def test_upsert_and_get_requirement() -> None:
    store = InMemoryRequirementStore()
    req = _hlr()
    await store.upsert_requirement(req)
    assert await store.get_requirement("HLR-1") == req
    assert await store.get_requirement("missing") is None


@pytest.mark.asyncio
async def test_id_collision_between_requirement_and_artefact_rejected() -> None:
    store = InMemoryRequirementStore()
    await store.upsert_requirement(_hlr("X-1"))
    with pytest.raises(ValueError, match="already a requirement"):
        await store.upsert_artefact(_code("X-1"))


@pytest.mark.asyncio
async def test_list_requirements_filters_by_type() -> None:
    store = InMemoryRequirementStore()
    await store.upsert_requirement(_hlr())
    await store.upsert_requirement(_llr())
    hlrs = await store.list_requirements(type_filter=RequirementType.HLR)
    llrs = await store.list_requirements(type_filter=RequirementType.LLR)
    assert len(hlrs) == 1 and hlrs[0].type is RequirementType.HLR
    assert len(llrs) == 1 and llrs[0].type is RequirementType.LLR


@pytest.mark.asyncio
async def test_add_edge_requires_existing_endpoints() -> None:
    store = InMemoryRequirementStore()
    await store.upsert_requirement(_hlr())
    with pytest.raises(ValueError, match="unknown source"):
        await store.add_edge(
            TraceEdge(
                source_id="missing",
                target_id="HLR-1",
                type=TraceEdgeType.DERIVED_FROM,
            )
        )


@pytest.mark.asyncio
async def test_outgoing_and_incoming_filters() -> None:
    store = InMemoryRequirementStore()
    await store.upsert_requirement(_hlr())
    await store.upsert_requirement(_llr())
    await store.add_edge(
        TraceEdge(
            source_id="LLR-1",
            target_id="HLR-1",
            type=TraceEdgeType.DERIVED_FROM,
        )
    )
    out = await store.outgoing_edges("LLR-1")
    inc = await store.incoming_edges("HLR-1")
    assert len(out) == 1 and out[0].type is TraceEdgeType.DERIVED_FROM
    assert len(inc) == 1 and inc[0].type is TraceEdgeType.DERIVED_FROM


@pytest.mark.asyncio
async def test_stats_reflect_state() -> None:
    store = InMemoryRequirementStore()
    await store.upsert_requirement(_hlr())
    await store.upsert_requirement(_llr())
    await store.upsert_artefact(_code())
    await store.add_edge(
        TraceEdge("LLR-1", "HLR-1", TraceEdgeType.DERIVED_FROM)
    )
    stats = await store.stats()
    assert stats == {"requirements": 2, "artefacts": 1, "edges": 1}
