"""Tests for frozen_oracle contracts (ADR-088 Phase 2.2)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle import (
    DOMAIN_MINIMUMS,
    GOLDEN_SET_MINIMUM,
    GoldenSetIntegrityError,
    GoldenTestCase,
    JudgeKind,
    JudgeResult,
    OracleEvaluation,
    TestCaseDomain,
)


class TestDomainMinimums:
    def test_domains_count(self) -> None:
        assert len(TestCaseDomain) == 4

    def test_minimums_sum_to_total(self) -> None:
        assert sum(DOMAIN_MINIMUMS.values()) == GOLDEN_SET_MINIMUM
        assert GOLDEN_SET_MINIMUM == 400

    def test_per_domain_minimums(self) -> None:
        # Numbers come straight from ADR-088 §Stage 4.
        assert DOMAIN_MINIMUMS[TestCaseDomain.VULNERABILITY_DETECTION] == 150
        assert DOMAIN_MINIMUMS[TestCaseDomain.PATCH_CORRECTNESS] == 100
        assert DOMAIN_MINIMUMS[TestCaseDomain.FALSE_POSITIVE] == 100
        assert DOMAIN_MINIMUMS[TestCaseDomain.REGRESSION] == 50


class TestGoldenTestCaseValidation:
    def test_basic_construction(self) -> None:
        c = GoldenTestCase(
            case_id="c1",
            domain=TestCaseDomain.VULNERABILITY_DETECTION,
            title="t",
            description="d",
            axes=(ModelAssuranceAxis.VULNERABILITY_DETECTION_RECALL,),
        )
        assert c.case_id == "c1"
        assert c.expected_dict == {}

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="case_id"):
            GoldenTestCase(
                case_id="",
                domain=TestCaseDomain.VULNERABILITY_DETECTION,
                title="t",
                description="d",
                axes=(ModelAssuranceAxis.CODE_COMPREHENSION,),
            )

    def test_empty_axes_rejected(self) -> None:
        with pytest.raises(ValueError, match="axis required"):
            GoldenTestCase(
                case_id="c1",
                domain=TestCaseDomain.VULNERABILITY_DETECTION,
                title="t",
                description="d",
                axes=(),
            )

    def test_expected_dict_round_trip(self) -> None:
        c = GoldenTestCase(
            case_id="c1",
            domain=TestCaseDomain.PATCH_CORRECTNESS,
            title="t",
            description="d",
            axes=(ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS,),
            expected=(("ref", "x"), ("notes", "y")),
        )
        assert c.expected_dict == {"ref": "x", "notes": "y"}

    def test_case_is_frozen(self) -> None:
        c = GoldenTestCase(
            case_id="c1",
            domain=TestCaseDomain.VULNERABILITY_DETECTION,
            title="t",
            description="d",
            axes=(ModelAssuranceAxis.CODE_COMPREHENSION,),
        )
        with pytest.raises((AttributeError, TypeError)):
            c.case_id = "x"  # type: ignore[misc]


class TestJudgeResultValidation:
    def test_confidence_range(self) -> None:
        with pytest.raises(ValueError, match=r"\[0,1\]"):
            JudgeResult(
                case_id="c", judge_id="j",
                judge_kind=JudgeKind.DETERMINISTIC,
                passed=True, confidence=1.5,
            )

    def test_axis_scores_dict(self) -> None:
        r = JudgeResult(
            case_id="c", judge_id="j",
            judge_kind=JudgeKind.DETERMINISTIC,
            passed=True, confidence=1.0,
            axis_scores=(
                (ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS, 1.0),
            ),
        )
        d = r.axis_scores_dict
        assert d[ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS] == 1.0


class TestOracleEvaluationAggregates:
    def test_overall_pass_rate(self) -> None:
        e = OracleEvaluation(
            candidate_id="c", judge_results=(),
            per_axis_scores=(),
            cases_evaluated=10, cases_passed=7,
        )
        assert e.overall_pass_rate == pytest.approx(0.7)

    def test_zero_cases_pass_rate(self) -> None:
        e = OracleEvaluation(
            candidate_id="c", judge_results=(),
            per_axis_scores=(),
            cases_evaluated=0, cases_passed=0,
        )
        assert e.overall_pass_rate == 0.0

    def test_audit_dict_keys(self) -> None:
        e = OracleEvaluation(
            candidate_id="c", judge_results=(),
            per_axis_scores=(
                (ModelAssuranceAxis.CODE_COMPREHENSION, 0.85),
            ),
            cases_evaluated=10, cases_passed=8,
            holdout_cases=("h1", "h2"),
        )
        d = e.to_audit_dict()
        assert d["candidate_id"] == "c"
        assert d["cases_evaluated"] == 10
        assert d["cases_passed"] == 8
        assert d["per_axis_scores"]["MA1_code_comprehension"] == 0.85
        assert d["holdout_cases"] == ["h1", "h2"]


class TestGoldenSetIntegrityError:
    def test_str_with_detail(self) -> None:
        e = GoldenSetIntegrityError(message="bad", detail="case-x duplicate")
        assert "bad" in str(e)
        assert "case-x duplicate" in str(e)

    def test_str_without_detail(self) -> None:
        e = GoldenSetIntegrityError(message="bad")
        assert str(e) == "bad"
