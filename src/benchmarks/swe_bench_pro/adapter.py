"""
Project Aura - SWE-Bench Pro Adapter Protocol.

The adapter is the seam where "Aura's pipeline" meets "SWE-Bench Pro
task format." Concrete adapters implement ``solve(task)`` and return a
``SWEBenchPrediction``. The runner is adapter-agnostic; mock adapters
let the runner be tested without invoking real models.

Adapters are responsible for:

1. Converting the upstream issue text + repo state into a prompt
   shape Aura's pipeline understands.
2. Driving Aura (Coder + Reviewer agents, or the scanner with a
   "fix this" instruction) to produce a unified diff.
3. Validating the diff is well-formed before returning.

Adapters are NOT responsible for evaluation — the official Docker
harness runs the patches against the test suite. The adapter's job
ends at producing a string that looks like a unified diff.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import abc
from typing import Iterable

from .contracts import SWEBenchPrediction, SWEBenchTask


class AdapterError(Exception):
    """Raised by adapters when an unrecoverable failure occurs.

    The runner catches this, records the task as ``ADAPTER_ERROR``,
    and continues with the next task. A single bad task should not
    abort the whole run.
    """


class Adapter(abc.ABC):
    """Single-task adapter contract.

    Implementations override ``solve`` to produce a
    ``SWEBenchPrediction`` for a given task. The default ``solve_many``
    is a sequential fallback; high-throughput adapters should override
    it to leverage concurrency / batching against their backend.
    """

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Identifier embedded in every prediction (``model_name_or_path``).

        Used by the leaderboard and by Aura's own analysis to
        distinguish runs of different model configurations.
        """

    @abc.abstractmethod
    async def solve(self, task: SWEBenchTask) -> SWEBenchPrediction:
        """Produce a prediction for a single task.

        Implementations may raise ``AdapterError`` for unrecoverable
        failures (rate limits, malformed model output, missing repo
        state). The runner records the failure and continues.

        Empty patches are NOT errors — return a prediction with
        ``model_patch=""`` to signal "agent declined to attempt".
        """

    async def solve_many(
        self, tasks: Iterable[SWEBenchTask]
    ) -> list[SWEBenchPrediction]:
        """Sequential default; override for batched / concurrent backends."""
        out: list[SWEBenchPrediction] = []
        for task in tasks:
            out.append(await self.solve(task))
        return out


class BatchAdapter(Adapter):
    """Adapter base for backends that benefit from batching.

    Subclasses override ``solve_many`` and may delegate ``solve`` to
    it. Useful for adapters wrapping batch inference APIs or for
    running multiple Bedrock calls concurrently with a semaphore.

    Default ``solve`` drives a single-task path through ``solve_many``
    so subclasses only have to implement the batched method.
    """

    async def solve(self, task: SWEBenchTask) -> SWEBenchPrediction:
        results = await self.solve_many([task])
        if not results:
            raise AdapterError(
                f"solve_many returned empty for task {task.instance_id}"
            )
        return results[0]

    async def solve_many(
        self, tasks: Iterable[SWEBenchTask]
    ) -> list[SWEBenchPrediction]:
        # Subclasses MUST override; this default exists so the abstract
        # parent's ``solve`` does not infinitely recurse via the parent's
        # default ``solve_many``.
        raise NotImplementedError(
            f"{type(self).__name__} must override solve_many"
        )
