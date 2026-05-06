"""Tests for NeptuneRequirementStore.

The live Neptune client isn't available in CI, so these tests target
the in-memory fallback path and verify the Gremlin query builders
emit syntactically reasonable output.
"""

from __future__ import annotations

import pytest

from src.services.verification_envelope.traceability import (
    InMemoryRequirementStore,
    NeptuneRequirementStore,
    Requirement,
    RequirementType,
    TraceEdge,
    TraceEdgeType,
)


@pytest.mark.asyncio
async def test_no_client_falls_back_to_in_memory() -> None:
    store = NeptuneRequirementStore()
    assert store.is_live is False
    req = Requirement(
        requirement_id="HLR-1",
        type=RequirementType.HLR,
        title="x",
        description="",
        dal_level="DAL_B",
    )
    await store.upsert_requirement(req)
    assert await store.get_requirement("HLR-1") == req


@pytest.mark.asyncio
async def test_explicit_fallback_store_used() -> None:
    custom = InMemoryRequirementStore()
    store = NeptuneRequirementStore(fallback_store=custom)
    assert store.fallback is custom
    req = Requirement(
        requirement_id="HLR-2",
        type=RequirementType.HLR,
        title="x",
        description="",
        dal_level="DAL_B",
    )
    await store.upsert_requirement(req)
    # The custom fallback should now contain the record.
    assert await custom.get_requirement("HLR-2") == req


def test_upsert_vertex_query_includes_label_and_properties() -> None:
    q = NeptuneRequirementStore.build_upsert_vertex_query(
        label="Requirement",
        vid="HLR-1",
        properties={"title": "boot sequence", "dal_level": "DAL_A"},
    )
    assert "addV('Requirement')" in q
    assert "'HLR-1'" in q
    assert "'title'" in q
    assert "'dal_level'" in q


def test_add_edge_query_includes_edge_label() -> None:
    q = NeptuneRequirementStore.build_add_edge_query(
        edge_label="DERIVED_FROM",
        source_id="LLR-1",
        target_id="HLR-1",
    )
    assert "addE('DERIVED_FROM')" in q
    assert "'LLR-1'" in q
    assert "'HLR-1'" in q


def test_add_edge_query_serialises_properties() -> None:
    q = NeptuneRequirementStore.build_add_edge_query(
        edge_label="VERIFIED_BY",
        source_id="HLR-1",
        target_id="test-1",
        properties={"author": "alice@aenealabs.com"},
    )
    assert ".property('author'" in q


@pytest.mark.asyncio
async def test_is_live_true_when_client_supplied() -> None:
    class _StubClient:
        pass

    store = NeptuneRequirementStore(neptune_client=_StubClient())
    assert store.is_live is True
