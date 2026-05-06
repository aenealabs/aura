"""Protocol-conformance tests for the MCDCCoverageAdapter contract."""

from __future__ import annotations

from src.services.verification_envelope.coverage import (
    CoveragePyAdapter,
    LDRAAdapter,
    MCDCCoverageAdapter,
    VectorCASTAdapter,
)


def test_coverage_py_satisfies_protocol() -> None:
    assert isinstance(CoveragePyAdapter(), MCDCCoverageAdapter)


def test_vectorcast_satisfies_protocol() -> None:
    assert isinstance(VectorCASTAdapter(), MCDCCoverageAdapter)


def test_ldra_satisfies_protocol() -> None:
    assert isinstance(LDRAAdapter(), MCDCCoverageAdapter)


def test_each_adapter_exposes_stable_tool_name() -> None:
    assert CoveragePyAdapter().tool_name == "coverage_py"
    assert VectorCASTAdapter().tool_name == "vectorcast"
    assert LDRAAdapter().tool_name == "ldra"


def test_each_adapter_reports_availability_synchronously() -> None:
    # The protocol declares is_available as a property; calling it should
    # not require an event loop. (Important for adapter selection inside
    # CoverageGateService.analyze().)
    for cls in (CoveragePyAdapter, VectorCASTAdapter, LDRAAdapter):
        adapter = cls()
        assert isinstance(adapter.is_available, bool)
