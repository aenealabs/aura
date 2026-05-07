"""Tests for the load-test harness (ADR-088 Phase 3.5)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.services.model_assurance.govcloud import LoadTestRun, run_load_test
from src.services.model_assurance.pipeline.contracts import (
    PipelineDecision,
    PipelineResult,
)


def _make_result(
    candidate_id: str = "m",
    decision: PipelineDecision = PipelineDecision.HITL_QUEUED,
) -> PipelineResult:
    now = datetime.now(timezone.utc)
    return PipelineResult(
        candidate_id=candidate_id,
        decision=decision,
        stages=(),
        started_at=now,
        completed_at=now,
    )


class TestLoadTestExecution:
    def test_runs_n_candidates(self) -> None:
        outcome = run_load_test(
            candidate_count=10,
            runner=lambda i: _make_result(f"m-{i}"),
        )
        assert outcome.candidates_run == 10
        decision = outcome.decision_dict
        assert decision.get(PipelineDecision.HITL_QUEUED) == 10

    def test_decision_distribution_recorded(self) -> None:
        def runner(i: int) -> PipelineResult:
            if i % 3 == 0:
                return _make_result(f"m-{i}", PipelineDecision.REJECTED)
            return _make_result(f"m-{i}", PipelineDecision.HITL_QUEUED)

        outcome = run_load_test(candidate_count=9, runner=runner)
        decision = outcome.decision_dict
        # i=0,3,6 → 3 rejections; rest are 6 HITL_QUEUED
        assert decision[PipelineDecision.REJECTED] == 3
        assert decision[PipelineDecision.HITL_QUEUED] == 6


class TestLatencyPercentiles:
    def test_percentiles_non_negative(self) -> None:
        outcome = run_load_test(
            candidate_count=20,
            runner=lambda i: _make_result(f"m-{i}"),
        )
        assert outcome.latency_ms_p50 >= 0.0
        assert outcome.latency_ms_p95 >= outcome.latency_ms_p50
        assert outcome.latency_ms_p99 >= outcome.latency_ms_p95
        assert outcome.latency_ms_max >= outcome.latency_ms_p99

    def test_zero_candidates_rejected(self) -> None:
        with pytest.raises(ValueError):
            run_load_test(candidate_count=0, runner=lambda i: _make_result())


class TestErrorTolerance:
    def test_runner_exception_counted_not_propagated(self) -> None:
        def runner(i: int) -> PipelineResult:
            if i == 2:
                raise RuntimeError("oracle down")
            return _make_result(f"m-{i}")

        outcome = run_load_test(candidate_count=5, runner=runner)
        assert outcome.errors == 1
        # 4 successful results + 1 error
        assert outcome.candidates_run == 5
        # Decision counts only reflect successful runs
        decision = outcome.decision_dict
        assert decision[PipelineDecision.HITL_QUEUED] == 4
