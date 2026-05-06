"""Tests for the VectorCASTAdapter mock-fallback paths.

The CI machine almost never has the proprietary ``vcast`` binary on
PATH, so the most useful coverage here is the no-binary code path —
the adapter must produce a clearly-marked unavailable report rather
than throwing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.verification_envelope.coverage import (
    CoverageAnalysisRequest,
    VectorCASTAdapter,
)
from src.services.verification_envelope.policies import (
    DAL_A_PROFILE_NAME,
    get_coverage_policy,
)


def _request(profile: str, tmp_path: Path) -> CoverageAnalysisRequest:
    return CoverageAnalysisRequest(
        source_files=(tmp_path / "target.py",),
        test_command="echo run",
        working_directory=tmp_path,
        dal_policy=get_coverage_policy(profile),
        timeout_seconds=5.0,
    )


@pytest.mark.asyncio
async def test_missing_binary_produces_unavailable_report(tmp_path: Path) -> None:
    adapter = VectorCASTAdapter(binary_path="vcast-does-not-exist")
    assert adapter.is_available is False
    report = await adapter.analyze(_request(DAL_A_PROFILE_NAME, tmp_path))
    assert report.coverage_tool.startswith("vectorcast:unavailable")
    assert report.dal_policy_satisfied is False
    assert report.uncovered_conditions, "must explain why we failed"
    assert "not found on PATH" in report.uncovered_conditions[0]


@pytest.mark.asyncio
async def test_json_parser_handles_well_formed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = VectorCASTAdapter()
    well_formed = (
        '{"coverage": {"statement_pct": 100.0, "decision_pct": 100.0, '
        '"mcdc_pct": 100.0, "uncovered_conditions": []}}'
    )
    request = _request(DAL_A_PROFILE_NAME, tmp_path)
    report = adapter._parse_json(well_formed, request)
    assert report.statement_coverage_pct == 100.0
    assert report.mcdc_coverage_pct == 100.0
    assert report.dal_policy_satisfied is True
    assert report.coverage_tool == "vectorcast"


@pytest.mark.asyncio
async def test_json_parser_handles_malformed_output(tmp_path: Path) -> None:
    adapter = VectorCASTAdapter()
    request = _request(DAL_A_PROFILE_NAME, tmp_path)
    report = adapter._parse_json("not json at all", request)
    assert report.coverage_tool == "vectorcast:json_parse_error"
    assert report.dal_policy_satisfied is False


@pytest.mark.asyncio
async def test_sarif_parser_extracts_metrics(tmp_path: Path) -> None:
    adapter = VectorCASTAdapter(report_format="sarif")
    sarif = (
        '{"runs": [{"properties": {"coverage": {'
        '"statement_pct": 100, "decision_pct": 100, "mcdc_pct": 100, '
        '"uncovered_conditions": []}}}]}'
    )
    report = adapter._parse_sarif(sarif, _request(DAL_A_PROFILE_NAME, tmp_path))
    assert report.statement_coverage_pct == 100.0
    assert report.coverage_tool == "vectorcast:sarif"
    assert report.dal_policy_satisfied is True


@pytest.mark.asyncio
async def test_sarif_parser_failure_marks_report_unsuccessful(
    tmp_path: Path,
) -> None:
    adapter = VectorCASTAdapter(report_format="sarif")
    report = adapter._parse_sarif("{}", _request(DAL_A_PROFILE_NAME, tmp_path))
    assert report.coverage_tool == "vectorcast:sarif_parse_error"
    assert report.dal_policy_satisfied is False
