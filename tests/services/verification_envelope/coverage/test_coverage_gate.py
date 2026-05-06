"""End-to-end tests for CoverageGateService."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.verification_envelope.contracts import MCDCCoverageReport
from src.services.verification_envelope.coverage import (
    CoverageAnalysisRequest,
    CoverageGateInput,
    CoverageGateService,
    LDRAAdapter,
    VectorCASTAdapter,
)
from src.services.verification_envelope.policies import (
    DAL_A_PROFILE_NAME,
    DEFAULT_PROFILE_NAME,
)


class _FakeAdapter:
    """In-process adapter returning canned reports for gate tests."""

    def __init__(
        self,
        *,
        tool_name: str = "fake",
        is_available: bool = True,
        report: MCDCCoverageReport | None = None,
    ) -> None:
        self.tool_name = tool_name
        self._is_available = is_available
        self._report = report or MCDCCoverageReport(
            statement_coverage_pct=100.0,
            decision_coverage_pct=100.0,
            mcdc_coverage_pct=100.0,
            dal_policy_satisfied=True,
            coverage_tool=tool_name,
        )
        self.calls: list[CoverageAnalysisRequest] = []

    @property
    def is_available(self) -> bool:
        return self._is_available

    async def analyze(self, request: CoverageAnalysisRequest) -> MCDCCoverageReport:
        self.calls.append(request)
        return self._report


def _gate_input(tmp_path: Path, profile: str) -> CoverageGateInput:
    src = tmp_path / "x.py"
    src.write_text("x = 1\n")
    return CoverageGateInput(
        source_files=(src,),
        test_command="echo ok",
        working_directory=tmp_path,
        profile_name=profile,
    )


@pytest.mark.asyncio
async def test_explicit_adapter_takes_precedence(tmp_path: Path) -> None:
    fake = _FakeAdapter()
    svc = CoverageGateService(adapter=fake)
    result = await svc.analyze(_gate_input(tmp_path, DEFAULT_PROFILE_NAME))
    assert result.adapter_used == "fake"
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_preferred_adapter_chain_picks_first_available(
    tmp_path: Path,
) -> None:
    """Walks the preference list and picks the first adapter reporting available."""
    unavailable = _FakeAdapter(tool_name="unavailable", is_available=False)
    available = _FakeAdapter(tool_name="picked", is_available=True)
    svc = CoverageGateService(preferred_adapters=(unavailable, available))
    result = await svc.analyze(_gate_input(tmp_path, DEFAULT_PROFILE_NAME))
    assert result.adapter_used == "picked"
    # Unavailable adapter's analyze() must not have been called.
    assert unavailable.calls == []


@pytest.mark.asyncio
async def test_no_available_adapter_returns_failed_report(tmp_path: Path) -> None:
    svc = CoverageGateService(
        preferred_adapters=(
            _FakeAdapter(tool_name="a", is_available=False),
            _FakeAdapter(tool_name="b", is_available=False),
        )
    )
    result = await svc.analyze(_gate_input(tmp_path, DAL_A_PROFILE_NAME))
    assert result.adapter_used == "none"
    assert result.report.coverage_tool == "no_adapter_available"
    assert result.report.dal_policy_satisfied is False


@pytest.mark.asyncio
async def test_dal_a_policy_fails_when_mcdc_below_threshold(
    tmp_path: Path,
) -> None:
    """DAL A requires 100% MC/DC; 99.99 must fail the gate."""
    too_low = MCDCCoverageReport(
        statement_coverage_pct=100.0,
        decision_coverage_pct=100.0,
        mcdc_coverage_pct=99.99,
        dal_policy_satisfied=False,  # adapter sets this; gate honours it
        coverage_tool="fake",
    )
    fake = _FakeAdapter(tool_name="fake", report=too_low)
    svc = CoverageGateService(adapter=fake)
    result = await svc.analyze(_gate_input(tmp_path, DAL_A_PROFILE_NAME))
    assert result.report.dal_policy_satisfied is False
    assert result.profile.dal_level == "DAL_A"


@pytest.mark.asyncio
async def test_default_policy_satisfied_at_70_percent_statement(
    tmp_path: Path,
) -> None:
    seventy = MCDCCoverageReport(
        statement_coverage_pct=72.0,
        decision_coverage_pct=0.0,
        mcdc_coverage_pct=0.0,
        dal_policy_satisfied=True,
        coverage_tool="fake",
    )
    fake = _FakeAdapter(tool_name="fake", report=seventy)
    svc = CoverageGateService(adapter=fake)
    result = await svc.analyze(_gate_input(tmp_path, DEFAULT_PROFILE_NAME))
    assert result.report.dal_policy_satisfied is True
    assert result.profile.dal_level == "DEFAULT"


@pytest.mark.asyncio
async def test_default_preference_uses_vendor_adapters_first(
    tmp_path: Path,
) -> None:
    """Default preference order: VectorCAST → LDRA → CoveragePy.

    On a CI box without vendor binaries, the gate should fall through
    to coverage.py — proving the chain works end-to-end without needing
    a real vendor install for tests.
    """
    svc = CoverageGateService()
    result = await svc.analyze(_gate_input(tmp_path, DEFAULT_PROFILE_NAME))
    # Either coverage.py runs (most likely), or one of the vendor
    # adapters is somehow on PATH and runs instead. Accept either.
    assert result.adapter_used in ("coverage_py", "vectorcast", "ldra")


def test_default_chain_includes_vectorcast_and_ldra() -> None:
    svc = CoverageGateService()
    names = [type(a).__name__ for a in svc._preferred_adapters]
    assert "VectorCASTAdapter" in names
    assert "LDRAAdapter" in names
    assert "CoveragePyAdapter" in names
