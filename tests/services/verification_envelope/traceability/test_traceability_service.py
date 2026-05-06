"""End-to-end tests for the TraceabilityService."""

from __future__ import annotations

import pytest

from src.services.verification_envelope.traceability import (
    ArtefactType,
    InMemoryRequirementStore,
    RequirementType,
    TraceabilityService,
    TraceEdgeType,
)


@pytest.fixture
def svc() -> TraceabilityService:
    return TraceabilityService(InMemoryRequirementStore())


@pytest.mark.asyncio
async def test_add_hlr_and_retrieve(svc: TraceabilityService) -> None:
    hlr = await svc.add_hlr(
        requirement_id="HLR-1",
        title="boot sequence",
        description="On power-on the FADEC must complete BIT.",
        dal_level="DAL_A",
    )
    assert hlr.type is RequirementType.HLR
    assert hlr.dal_level == "DAL_A"


@pytest.mark.asyncio
async def test_add_llr_creates_derived_from_edge(svc: TraceabilityService) -> None:
    await svc.add_hlr(
        requirement_id="HLR-1",
        title="boot sequence",
        description="",
        dal_level="DAL_A",
    )
    await svc.add_llr(
        requirement_id="LLR-1",
        title="execute BIT",
        description="",
        derived_from=("HLR-1",),
        dal_level="DAL_A",
    )
    parents = await svc.parents_of("LLR-1")
    children = await svc.children_of("HLR-1")
    assert {p.requirement_id for p in parents} == {"HLR-1"}
    assert {c.requirement_id for c in children} == {"LLR-1"}


@pytest.mark.asyncio
async def test_code_traces_to_llr(svc: TraceabilityService) -> None:
    await svc.add_hlr(
        requirement_id="HLR-1",
        title="x",
        description="",
        dal_level="DAL_A",
    )
    await svc.add_llr(
        requirement_id="LLR-1",
        title="x",
        description="",
        derived_from=("HLR-1",),
        dal_level="DAL_A",
    )
    await svc.add_code(
        artefact_id="code-1",
        title="bit_runner.py",
        location="src/fadec/bit_runner.py",
        traces_to=("LLR-1",),
    )
    impl = await svc.implementing_code("LLR-1")
    assert {a.artefact_id for a in impl} == {"code-1"}


@pytest.mark.asyncio
async def test_test_verifies_requirement(svc: TraceabilityService) -> None:
    await svc.add_hlr(
        requirement_id="HLR-1",
        title="x",
        description="",
        dal_level="DAL_A",
    )
    await svc.add_test(
        artefact_id="test-1",
        title="boot_test.py",
        location="tests/test_boot.py",
        verifies=("HLR-1",),
    )
    tests = await svc.verifying_tests("HLR-1")
    assert {t.artefact_id for t in tests} == {"test-1"}


@pytest.mark.asyncio
async def test_gap_report_clean_graph_no_findings(
    svc: TraceabilityService,
) -> None:
    await svc.add_hlr(
        requirement_id="HLR-1",
        title="x",
        description="",
        dal_level="DAL_A",
    )
    await svc.add_llr(
        requirement_id="LLR-1",
        title="x",
        description="",
        derived_from=("HLR-1",),
        dal_level="DAL_A",
    )
    await svc.add_code(
        artefact_id="code-1",
        title="x",
        location="src/x.py",
        traces_to=("LLR-1",),
    )
    await svc.add_test(
        artefact_id="test-hlr-1",
        title="t",
        location="tests/test_x.py",
        verifies=("HLR-1",),
    )
    await svc.add_test(
        artefact_id="test-llr-1",
        title="t",
        location="tests/test_x.py",
        verifies=("LLR-1",),
    )
    report = await svc.gap_report()
    assert report.is_complete is True
    assert report.requirement_count == 2
    assert report.artefact_count == 3
    assert report.edge_count >= 4


@pytest.mark.asyncio
async def test_gap_report_hlr_with_no_llr_is_forward_gap(
    svc: TraceabilityService,
) -> None:
    await svc.add_hlr(
        requirement_id="HLR-orphan",
        title="x",
        description="",
        dal_level="DAL_B",
    )
    report = await svc.gap_report()
    assert report.forward_gaps
    assert any(
        g.node_id == "HLR-orphan" and "no derived LLRs" in g.description
        for g in report.forward_gaps
    )


@pytest.mark.asyncio
async def test_gap_report_orphan_code_is_reverse_gap(
    svc: TraceabilityService,
) -> None:
    await svc.add_code(
        artefact_id="orphan-code",
        title="x",
        location="src/x.py",
    )
    report = await svc.gap_report()
    assert report.reverse_gaps
    assert any(
        g.node_id == "orphan-code" for g in report.reverse_gaps
    )


@pytest.mark.asyncio
async def test_gap_report_orphan_test_is_reverse_gap(
    svc: TraceabilityService,
) -> None:
    await svc.add_test(
        artefact_id="orphan-test",
        title="x",
        location="tests/x.py",
    )
    report = await svc.gap_report()
    assert any(
        g.node_id == "orphan-test" for g in report.reverse_gaps
    )


@pytest.mark.asyncio
async def test_link_helper_creates_arbitrary_edge(
    svc: TraceabilityService,
) -> None:
    await svc.add_hlr(
        requirement_id="HLR-1",
        title="x",
        description="",
        dal_level="DAL_A",
    )
    review = await svc.add_code(
        artefact_id="review-1",
        title="x",
        location="reviews/review-1.md",
    )
    edge = await svc.link(
        source_id="HLR-1",
        target_id=review.artefact_id,
        edge_type=TraceEdgeType.REVIEWED_BY,
    )
    assert edge.type is TraceEdgeType.REVIEWED_BY


@pytest.mark.asyncio
async def test_total_gap_count_aggregates_directions(
    svc: TraceabilityService,
) -> None:
    await svc.add_hlr(
        requirement_id="HLR-1",
        title="x",
        description="",
        dal_level="DAL_A",
    )
    await svc.add_code(artefact_id="orphan", title="x", location="x")
    report = await svc.gap_report()
    assert report.total_gap_count == len(report.forward_gaps) + len(
        report.reverse_gaps
    )
