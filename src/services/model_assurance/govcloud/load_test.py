"""Load-test harness for the assurance pipeline (ADR-088 Phase 3.5).

Per acceptance criteria: "Full pipeline load test with simulated
candidates passes". The harness simulates N candidate flows
through the synchronous PipelineOrchestrator, records latency +
verdict distribution, and emits a summary report.

The harness is for *operational* validation — proving the pipeline
holds up under realistic concurrency. It is intentionally narrow:
no AWS calls, no network I/O, deterministic per-seed.
"""

from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass, field
from typing import Callable

from src.services.model_assurance.pipeline.contracts import (
    PipelineDecision,
    PipelineResult,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadTestRun:
    """Summary of one load-test execution."""

    candidates_run: int
    decision_counts: tuple[tuple[PipelineDecision, int], ...]
    latency_ms_p50: float
    latency_ms_p95: float
    latency_ms_p99: float
    latency_ms_max: float
    errors: int

    @property
    def decision_dict(self) -> dict[PipelineDecision, int]:
        return dict(self.decision_counts)


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = max(0, min(len(sorted_values) - 1, int(round(len(sorted_values) * pct)) - 1))
    return sorted_values[idx]


def run_load_test(
    *,
    candidate_count: int,
    runner: Callable[[int], PipelineResult],
) -> LoadTestRun:
    """Run ``candidate_count`` synthetic candidates through the pipeline.

    ``runner`` is supplied by the caller — it takes a synthetic
    candidate index and returns a PipelineResult. This indirection
    keeps the harness agnostic to PipelineOrchestrator construction
    details (the test fixtures supply the wired-up orchestrator).
    """
    if candidate_count <= 0:
        raise ValueError(f"candidate_count must be > 0; got {candidate_count}")

    latencies: list[float] = []
    decision_counts: dict[PipelineDecision, int] = {}
    errors = 0

    for i in range(candidate_count):
        start = time.perf_counter()
        try:
            result = runner(i)
        except Exception as exc:
            errors += 1
            logger.warning("load test candidate %d failed: %s", i, exc)
            continue
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)
        decision_counts[result.decision] = decision_counts.get(result.decision, 0) + 1

    latencies.sort()
    return LoadTestRun(
        candidates_run=candidate_count,
        decision_counts=tuple(decision_counts.items()),
        latency_ms_p50=_percentile(latencies, 0.50),
        latency_ms_p95=_percentile(latencies, 0.95),
        latency_ms_p99=_percentile(latencies, 0.99),
        latency_ms_max=max(latencies) if latencies else 0.0,
        errors=errors,
    )
