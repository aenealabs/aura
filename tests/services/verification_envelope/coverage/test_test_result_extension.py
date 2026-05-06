"""Tests for the TestResult coverage-fields extension (ADR-085 Phase 2)."""

from __future__ import annotations

from src.services.sandbox_test_runner import TestResult, TestResultType


def _base() -> TestResult:
    return TestResult(
        result_id="r-1",
        sandbox_id="sb-1",
        patch_id="p-1",
        status=TestResultType.PASS,
        tests_passed=10,
        tests_failed=0,
    )


def test_default_coverage_fields_zero() -> None:
    r = _base()
    assert r.statement_coverage_pct == 0.0
    assert r.decision_coverage_pct == 0.0
    assert r.mcdc_coverage_pct == 0.0
    assert r.structural_coverage_dal is None
    assert r.coverage_tool_used is None
    assert r.coverage_report_s3_key is None


def test_apply_coverage_returns_copy_with_populated_fields() -> None:
    r = _base()
    enriched = r.apply_coverage(
        statement_pct=100.0,
        decision_pct=100.0,
        mcdc_pct=100.0,
        dal_level="DAL_A",
        tool="vectorcast",
        report_s3_key="s3://bucket/report.json",
    )
    # Original is untouched.
    assert r.statement_coverage_pct == 0.0
    assert r.coverage_tool_used is None
    # Copy carries the new fields.
    assert enriched.statement_coverage_pct == 100.0
    assert enriched.mcdc_coverage_pct == 100.0
    assert enriched.structural_coverage_dal == "DAL_A"
    assert enriched.coverage_tool_used == "vectorcast"
    assert enriched.coverage_report_s3_key == "s3://bucket/report.json"
    # Status / counts roll through unchanged.
    assert enriched.status == r.status
    assert enriched.tests_passed == r.tests_passed
    assert enriched.result_id == r.result_id


def test_to_dict_includes_coverage_fields() -> None:
    enriched = _base().apply_coverage(
        statement_pct=85.5,
        decision_pct=70.0,
        mcdc_pct=0.0,
        dal_level="DEFAULT",
        tool="coverage_py",
    )
    payload = enriched.to_dict()
    assert payload["statement_coverage_pct"] == 85.5
    assert payload["decision_coverage_pct"] == 70.0
    assert payload["mcdc_coverage_pct"] == 0.0
    assert payload["structural_coverage_dal"] == "DEFAULT"
    assert payload["coverage_tool_used"] == "coverage_py"
    # Existing fields still present.
    assert payload["result_id"] == "r-1"
    assert payload["status"] == TestResultType.PASS.value


def test_apply_coverage_chains_idempotently() -> None:
    """Calling apply_coverage twice replaces the previous values."""
    once = _base().apply_coverage(
        statement_pct=70.0,
        decision_pct=0.0,
        mcdc_pct=0.0,
        dal_level="DEFAULT",
        tool="coverage_py",
    )
    twice = once.apply_coverage(
        statement_pct=100.0,
        decision_pct=100.0,
        mcdc_pct=100.0,
        dal_level="DAL_A",
        tool="vectorcast",
    )
    assert twice.statement_coverage_pct == 100.0
    assert twice.structural_coverage_dal == "DAL_A"
    assert twice.coverage_tool_used == "vectorcast"
