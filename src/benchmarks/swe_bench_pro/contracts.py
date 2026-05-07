"""
Project Aura - SWE-Bench Pro Data Contracts.

Typed dataclasses for SWE-Bench Pro tasks, predictions, and results.
The shapes follow the upstream dataset schema (instance_id, repo,
base_commit, problem_statement, hints_text, ...) plus Aura-side
metadata (per-task duration, cost, model used).

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


class TaskOutcome(enum.Enum):
    """Terminal outcome of running a single SWE-Bench Pro task."""

    GENERATED = "generated"  # adapter produced a patch (correctness TBD)
    EMPTY_PATCH = "empty_patch"  # adapter returned no patch
    ADAPTER_ERROR = "adapter_error"  # adapter raised
    TIMEOUT = "timeout"  # adapter exceeded its budget


@dataclass(frozen=True)
class SWEBenchTask:
    """A single SWE-Bench Pro instance.

    Mirrors the upstream HuggingFace dataset schema (subset of fields
    Aura's adapter actually consumes). Anything we don't read is
    discarded at load time so the in-process surface stays small.
    """

    instance_id: str
    repo: str  # e.g. "django/django"
    base_commit: str
    problem_statement: str  # the issue text
    hints_text: str = ""  # optional human hints
    test_patch: str = ""  # patch applying tests; not given to the agent
    fail_to_pass: tuple[str, ...] = ()  # tests that should pass after fix
    pass_to_pass: tuple[str, ...] = ()  # tests that must keep passing
    dockerhub_tag: str = ""  # prebuilt image at jefzda/sweap-images:{tag}
    version: str = ""  # repo version
    environment_setup_commit: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SWEBenchPrediction:
    """A single prediction in the SWE-Bench Pro submission format.

    The official harness consumes a JSON list/dict of these. The
    minimum required shape is ``{instance_id, model_patch, model_name_or_path}``;
    Aura attaches additional metadata in ``aura_metadata`` for our own
    analysis (cost, duration, error reason for empty patches).
    """

    instance_id: str
    model_patch: str  # unified diff; empty string for no-prediction
    model_name_or_path: str  # the model / pipeline label
    aura_metadata: dict[str, Any] = field(default_factory=dict)

    def to_submission_dict(self) -> dict[str, Any]:
        """Serialise to the submission-JSON shape the harness expects."""
        return {
            "instance_id": self.instance_id,
            "model_patch": self.model_patch,
            "model_name_or_path": self.model_name_or_path,
        }


@dataclass(frozen=True)
class SWEBenchResult:
    """Per-task result: prediction + adapter-side telemetry.

    The adapter populates outcome, duration, and cost; the runner
    aggregates these into a RunReport. Correctness (pass/fail vs
    test suite) is determined by the official harness Docker run,
    NOT here — this contract intentionally separates "did Aura
    produce a patch" from "is the patch correct".
    """

    task: SWEBenchTask
    prediction: SWEBenchPrediction
    outcome: TaskOutcome
    duration_seconds: float
    cost_usd: float = 0.0
    error: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None

    @property
    def has_patch(self) -> bool:
        return self.outcome == TaskOutcome.GENERATED and bool(
            self.prediction.model_patch.strip()
        )
