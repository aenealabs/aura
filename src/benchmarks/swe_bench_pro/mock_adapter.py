"""
Project Aura - Mock SWE-Bench Pro Adapters.

In-process adapters used to test the runner, submission writer, and
result aggregation without invoking real models. Three flavours:

- ``StubAdapter`` — returns a fixed patch for every task; useful for
  asserting the runner wires tasks through correctly.
- ``EmptyPatchAdapter`` — always returns an empty patch; exercises the
  EMPTY_PATCH outcome path.
- ``DeterministicMockAdapter`` — accepts a per-instance-id mapping
  ``{instance_id: model_patch}`` so tests can simulate a realistic
  mixed-outcome run.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

from typing import Optional

from .adapter import Adapter, AdapterError
from .contracts import SWEBenchPrediction, SWEBenchTask


class StubAdapter(Adapter):
    """Returns the same fixed patch for every task."""

    def __init__(
        self,
        model_name: str = "stub-1.0",
        fixed_patch: str = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n",
    ) -> None:
        self._model_name = model_name
        self._fixed_patch = fixed_patch
        self.solve_count = 0

    @property
    def model_name(self) -> str:
        return self._model_name

    async def solve(self, task: SWEBenchTask) -> SWEBenchPrediction:
        self.solve_count += 1
        return SWEBenchPrediction(
            instance_id=task.instance_id,
            model_patch=self._fixed_patch,
            model_name_or_path=self._model_name,
            aura_metadata={"adapter": "stub"},
        )


class EmptyPatchAdapter(Adapter):
    """Always declines to attempt; tests the EMPTY_PATCH outcome."""

    @property
    def model_name(self) -> str:
        return "empty-1.0"

    async def solve(self, task: SWEBenchTask) -> SWEBenchPrediction:
        return SWEBenchPrediction(
            instance_id=task.instance_id,
            model_patch="",
            model_name_or_path=self.model_name,
            aura_metadata={"adapter": "empty", "reason": "decline"},
        )


class DeterministicMockAdapter(Adapter):
    """Returns per-task patches from an in-memory mapping.

    Configure with a dict of ``{instance_id: model_patch}``. Instances
    not in the mapping receive an empty patch. Configure
    ``raise_for_ids`` to simulate adapter failures on specific
    instance ids.
    """

    def __init__(
        self,
        patches: dict[str, str],
        model_name: str = "deterministic-mock-1.0",
        raise_for_ids: Optional[set[str]] = None,
    ) -> None:
        self._patches = patches
        self._model_name = model_name
        self._raise_for_ids = raise_for_ids or set()
        self.solve_count = 0

    @property
    def model_name(self) -> str:
        return self._model_name

    async def solve(self, task: SWEBenchTask) -> SWEBenchPrediction:
        self.solve_count += 1
        if task.instance_id in self._raise_for_ids:
            raise AdapterError(
                f"Configured to fail for instance {task.instance_id}"
            )
        patch = self._patches.get(task.instance_id, "")
        return SWEBenchPrediction(
            instance_id=task.instance_id,
            model_patch=patch,
            model_name_or_path=self._model_name,
            aura_metadata={"adapter": "deterministic"},
        )
