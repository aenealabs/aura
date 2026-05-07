"""
Project Aura - SWE-Bench Pro Runner.

Iterates a list of tasks, drives them through an adapter, collects
results with telemetry. Concurrency is bounded by a semaphore so a
batch of 30 tasks doesn't fan out into 30 concurrent Bedrock calls.

The runner is correctness-only here — it never tells you whether a
patch is correct. That's the official Docker harness's job. The
runner answers "did Aura produce a patch?" and "how long / how much
did it cost?".

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from .adapter import Adapter, AdapterError
from .contracts import (
    SWEBenchPrediction,
    SWEBenchResult,
    SWEBenchTask,
    TaskOutcome,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunReport:
    """Aggregate report over a runner invocation.

    Counts of each outcome plus total / mean cost / duration. The
    runner emits this; the submission writer consumes ``results`` to
    serialise predictions.
    """

    total_tasks: int
    outcome_counts: dict[TaskOutcome, int]
    total_duration_seconds: float
    total_cost_usd: float
    mean_duration_seconds: float
    mean_cost_usd: float
    results: tuple[SWEBenchResult, ...]
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def predictions(self) -> tuple[SWEBenchPrediction, ...]:
        return tuple(r.prediction for r in self.results)

    @property
    def patch_generation_rate(self) -> float:
        """Fraction of tasks for which the adapter produced a non-empty patch.

        NOT a correctness metric. The official harness measures
        correctness; this just answers "is the adapter producing
        output at all?".
        """
        if self.total_tasks == 0:
            return 0.0
        generated = self.outcome_counts.get(TaskOutcome.GENERATED, 0)
        return generated / self.total_tasks


async def run(
    tasks: Iterable[SWEBenchTask],
    *,
    adapter: Adapter,
    max_concurrency: int = 4,
    per_task_timeout_seconds: float = 600.0,
) -> RunReport:
    """Drive ``tasks`` through ``adapter`` and return a ``RunReport``.

    Bounded concurrency via semaphore. Per-task timeout protects the
    overall run from a single hung task — exceeded tasks become
    ``TIMEOUT`` outcomes. ``AdapterError`` becomes ``ADAPTER_ERROR``.
    """
    task_list = list(tasks)
    if not task_list:
        return RunReport(
            total_tasks=0,
            outcome_counts={},
            total_duration_seconds=0.0,
            total_cost_usd=0.0,
            mean_duration_seconds=0.0,
            mean_cost_usd=0.0,
            results=(),
        )

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _run_one(task: SWEBenchTask) -> SWEBenchResult:
        started = time.monotonic()
        started_at = datetime.now(timezone.utc)
        async with semaphore:
            try:
                prediction = await asyncio.wait_for(
                    adapter.solve(task),
                    timeout=per_task_timeout_seconds,
                )
            except asyncio.TimeoutError:
                duration = time.monotonic() - started
                logger.warning(
                    "Task %s timed out after %.1fs",
                    task.instance_id,
                    duration,
                )
                return SWEBenchResult(
                    task=task,
                    prediction=SWEBenchPrediction(
                        instance_id=task.instance_id,
                        model_patch="",
                        model_name_or_path=adapter.model_name,
                        aura_metadata={"error": "timeout"},
                    ),
                    outcome=TaskOutcome.TIMEOUT,
                    duration_seconds=duration,
                    error="timeout",
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                )
            except AdapterError as exc:
                duration = time.monotonic() - started
                logger.warning(
                    "Adapter error on task %s: %s", task.instance_id, exc
                )
                return SWEBenchResult(
                    task=task,
                    prediction=SWEBenchPrediction(
                        instance_id=task.instance_id,
                        model_patch="",
                        model_name_or_path=adapter.model_name,
                        aura_metadata={"error": str(exc)[:500]},
                    ),
                    outcome=TaskOutcome.ADAPTER_ERROR,
                    duration_seconds=duration,
                    error=str(exc)[:500],
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                )

        duration = time.monotonic() - started
        cost = float(prediction.aura_metadata.get("cost_usd", 0.0) or 0.0)
        outcome = (
            TaskOutcome.GENERATED
            if prediction.model_patch.strip()
            else TaskOutcome.EMPTY_PATCH
        )
        return SWEBenchResult(
            task=task,
            prediction=prediction,
            outcome=outcome,
            duration_seconds=duration,
            cost_usd=cost,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )

    coros = [_run_one(t) for t in task_list]
    results = await asyncio.gather(*coros)

    outcome_counts: Counter[TaskOutcome] = Counter(r.outcome for r in results)
    total_duration = sum(r.duration_seconds for r in results)
    total_cost = sum(r.cost_usd for r in results)
    n = len(results)

    return RunReport(
        total_tasks=n,
        outcome_counts=dict(outcome_counts),
        total_duration_seconds=total_duration,
        total_cost_usd=total_cost,
        mean_duration_seconds=total_duration / n if n else 0.0,
        mean_cost_usd=total_cost / n if n else 0.0,
        results=tuple(results),
    )
