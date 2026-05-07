"""
Project Aura - SWE-Bench Pro Submission Writer.

Serialises predictions into the JSON shape the official harness
consumes:

    [
      {"instance_id": "...", "model_patch": "...", "model_name_or_path": "..."},
      ...
    ]

A separate Aura-side metadata file is written alongside (with cost,
duration, error reasons per task) so the submission file stays in
the exact upstream format while we keep our analysis data nearby.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Iterable

from .contracts import SWEBenchPrediction, SWEBenchResult

logger = logging.getLogger(__name__)


def write_submission(
    predictions: Iterable[SWEBenchPrediction],
    output_path: str | pathlib.Path,
) -> pathlib.Path:
    """Write predictions in the official SWE-Bench submission format.

    Returns the resolved Path so callers can chain it into the harness
    invocation. Overwrites if the file exists.
    """
    path = pathlib.Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [p.to_submission_dict() for p in predictions]
    path.write_text(json.dumps(payload, indent=2))
    logger.info("Wrote %d predictions to %s", len(payload), path)
    return path


def write_metadata(
    results: Iterable[SWEBenchResult],
    output_path: str | pathlib.Path,
) -> pathlib.Path:
    """Write Aura-side per-task telemetry alongside the submission.

    Captures cost, duration, outcome, and error per task so we can
    correlate harness pass/fail results with Aura-side signal.
    """
    path = pathlib.Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for r in results:
        payload.append(
            {
                "instance_id": r.task.instance_id,
                "repo": r.task.repo,
                "outcome": r.outcome.value,
                "duration_seconds": r.duration_seconds,
                "cost_usd": r.cost_usd,
                "has_patch": r.has_patch,
                "model_name_or_path": r.prediction.model_name_or_path,
                "error": r.error,
                "started_at": r.started_at.isoformat(),
                "finished_at": (
                    r.finished_at.isoformat() if r.finished_at else None
                ),
                "aura_metadata": r.prediction.aura_metadata,
            }
        )
    path.write_text(json.dumps(payload, indent=2))
    logger.info("Wrote %d metadata records to %s", len(payload), path)
    return path
