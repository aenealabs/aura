"""Tests for the DO-178C lifecycle-data template generator."""

from __future__ import annotations

import pytest

from src.services.verification_envelope.traceability import (
    InMemoryRequirementStore,
    LifecycleContext,
    LifecycleDataGenerator,
    TraceabilityService,
)


def _ctx(**overrides: object) -> LifecycleContext:
    base = dict(
        program_name="FADEC-X",
        program_id="fadec-x-2026",
        dal_level="DAL_A",
        aircraft="Test 717",
        system="FADEC controller",
        cognizant_aco="LA-ACO",
        cognizant_der="J. Doe",
        project_url="https://internal/fadec-x",
    )
    base.update(overrides)
    return LifecycleContext(**base)  # type: ignore[arg-type]


async def _populated_service() -> TraceabilityService:
    svc = TraceabilityService(InMemoryRequirementStore())
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
        location="tests/t.py",
        verifies=("HLR-1",),
    )
    await svc.add_test(
        artefact_id="test-llr-1",
        title="t",
        location="tests/t.py",
        verifies=("LLR-1",),
    )
    return svc


@pytest.mark.asyncio
async def test_generate_all_returns_five_documents() -> None:
    svc = await _populated_service()
    docs = await LifecycleDataGenerator(svc).generate_all(_ctx())
    names = {d.name for d in docs}
    assert names == {"PSAC", "SDP", "SVP", "SQAP", "SAS"}


@pytest.mark.asyncio
async def test_psac_includes_program_table_and_dal_level() -> None:
    svc = await _populated_service()
    psac = LifecycleDataGenerator(svc).generate_psac(_ctx(), await svc.gap_report())
    assert "Plan for Software Aspects of Certification" in psac.content
    assert "DAL_A" in psac.content
    assert "FADEC-X" in psac.content
    assert "fadec-x-2026" in psac.content
    assert "LA-ACO" in psac.content


@pytest.mark.asyncio
async def test_psac_includes_compliance_table() -> None:
    svc = await _populated_service()
    psac = LifecycleDataGenerator(svc).generate_psac(_ctx(), await svc.gap_report())
    assert "MC/DC structural coverage" in psac.content
    assert "Formal proof of C1-C4" in psac.content
    assert "Bidirectional requirements traceability" in psac.content


@pytest.mark.asyncio
async def test_svp_lists_dal_coverage_table() -> None:
    svc = await _populated_service()
    svp = LifecycleDataGenerator(svc).generate_svp(_ctx(), await svc.gap_report())
    assert "Statement" in svp.content
    assert "MC/DC" in svp.content
    assert "Object Code" in svp.content
    assert "100%" in svp.content


@pytest.mark.asyncio
async def test_sas_reports_quantitative_results() -> None:
    svc = await _populated_service()
    report = await svc.gap_report()
    sas = LifecycleDataGenerator(svc).generate_sas(_ctx(), report)
    assert f"Requirements: {report.requirement_count}" in sas.content
    assert f"Artefacts: {report.artefact_count}" in sas.content
    assert "Forward gaps: 0" in sas.content
    assert "Reverse gaps: 0" in sas.content


@pytest.mark.asyncio
async def test_gap_summary_lists_findings_when_present() -> None:
    """A graph with gaps should produce non-empty 'Open issues' sections."""
    svc = TraceabilityService(InMemoryRequirementStore())
    await svc.add_hlr(
        requirement_id="HLR-orphan",
        title="x",
        description="",
        dal_level="DAL_A",
    )
    await svc.add_code(artefact_id="code-orphan", title="x", location="src/x.py")
    report = await svc.gap_report()
    sas = LifecycleDataGenerator(svc).generate_sas(_ctx(), report)
    assert "HLR-orphan" in sas.content
    assert "code-orphan" in sas.content
    assert "Forward gaps:" in sas.content
    assert "Reverse gaps:" in sas.content


@pytest.mark.asyncio
async def test_extra_fields_appear_in_program_table() -> None:
    svc = await _populated_service()
    ctx = _ctx(extra=(("PSAC submission date", "2026-09-01"), ("Tech POC", "K. Smith")))
    psac = LifecycleDataGenerator(svc).generate_psac(ctx, await svc.gap_report())
    assert "PSAC submission date" in psac.content
    assert "K. Smith" in psac.content


@pytest.mark.asyncio
async def test_lifecycle_documents_are_markdown() -> None:
    svc = await _populated_service()
    docs = await LifecycleDataGenerator(svc).generate_all(_ctx())
    for doc in docs:
        # Every doc should start with a top-level heading.
        assert doc.content.startswith("# ")
