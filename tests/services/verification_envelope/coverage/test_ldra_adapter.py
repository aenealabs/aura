"""Tests for the LDRAAdapter mock-fallback and parser paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.verification_envelope.coverage import (
    CoverageAnalysisRequest,
    LDRAAdapter,
)
from src.services.verification_envelope.policies import (
    DAL_A_PROFILE_NAME,
    DEFAULT_PROFILE_NAME,
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
    adapter = LDRAAdapter(binary_path="tbrun-not-installed")
    assert adapter.is_available is False
    report = await adapter.analyze(_request(DAL_A_PROFILE_NAME, tmp_path))
    assert report.coverage_tool.startswith("ldra:unavailable")
    assert report.dal_policy_satisfied is False


@pytest.mark.asyncio
async def test_json_parser_extracts_metrics(tmp_path: Path) -> None:
    adapter = LDRAAdapter(report_format="json")
    raw = (
        '{"coverage": {"statement_pct": 100, "decision_pct": 100, '
        '"mcdc_pct": 100, "uncovered_conditions": []}}'
    )
    report = adapter._parse_json(raw, _request(DAL_A_PROFILE_NAME, tmp_path))
    assert report.statement_coverage_pct == 100.0
    assert report.dal_policy_satisfied is True
    assert report.coverage_tool == "ldra"


@pytest.mark.asyncio
async def test_xml_parser_extracts_attribute_form(tmp_path: Path) -> None:
    """LDRA 2024 emits ``<root statement_pct=...>`` directly on the root."""
    adapter = LDRAAdapter(report_format="xml")
    xml = '<report statement_pct="100" decision_pct="100" mcdc_pct="100"/>'
    report = adapter._parse_xml(xml, _request(DAL_A_PROFILE_NAME, tmp_path))
    assert report.statement_coverage_pct == 100.0
    assert report.dal_policy_satisfied is True


@pytest.mark.asyncio
async def test_xml_parser_extracts_nested_form(tmp_path: Path) -> None:
    """LDRA 2023 emits ``<coverage><statement_pct>...</statement_pct></coverage>``."""
    adapter = LDRAAdapter(report_format="xml")
    xml = (
        "<report><coverage>"
        "<statement_pct>100.0</statement_pct>"
        "<decision_pct>100.0</decision_pct>"
        "<mcdc_pct>100.0</mcdc_pct>"
        "<uncovered_condition>cond1</uncovered_condition>"
        "</coverage></report>"
    )
    report = adapter._parse_xml(xml, _request(DEFAULT_PROFILE_NAME, tmp_path))
    assert report.statement_coverage_pct == 100.0
    assert report.uncovered_conditions == ("cond1",)


@pytest.mark.asyncio
async def test_xml_parser_handles_malformed_input(tmp_path: Path) -> None:
    adapter = LDRAAdapter(report_format="xml")
    report = adapter._parse_xml("<not-valid", _request(DAL_A_PROFILE_NAME, tmp_path))
    assert report.coverage_tool == "ldra:xml_parse_error"
    assert report.dal_policy_satisfied is False
