"""
Project Aura - SWE-Bench Pro Dataset Loader.

Pulls SWE-Bench Pro tasks from the upstream HuggingFace dataset
(``ScaleAI/SWE-bench_Pro``) and adapts them into the Aura-side
``SWEBenchTask`` shape. Includes a ``load_subset`` helper for the
intended workflow ("run on 30 tasks, get a baseline").

The HuggingFace ``datasets`` library is imported lazily so the rest
of this package is testable without it. Tests construct
``SWEBenchTask`` instances directly (see ``mock_adapter`` and the
test fixtures).

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import logging
from typing import Iterable, Iterator, Optional

from .contracts import SWEBenchTask

logger = logging.getLogger(__name__)


# Upstream dataset coordinates. Pinned to a specific revision in
# production runs so a baseline is reproducible against a fixed
# dataset snapshot.
DEFAULT_DATASET_NAME = "ScaleAI/SWE-bench_Pro"
DEFAULT_SPLIT = "test"  # SWE-Bench Pro public set lives in `test`


def _require_datasets():
    """Lazy-import HuggingFace ``datasets`` with a clear error message."""
    try:
        from datasets import load_dataset  # noqa: WPS433 (lazy by design)
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise ImportError(
            "The 'datasets' library is required to load SWE-Bench Pro. "
            "Install with: pip install datasets"
        ) from exc
    return load_dataset


def _row_to_task(row: dict) -> SWEBenchTask:
    """Adapt one HF dataset row into a ``SWEBenchTask``.

    Keeps only the fields Aura's adapters consume; everything else
    lives in ``task.extra`` so debugging tooling can still see it
    without bloating the in-memory adapter surface.
    """
    known_fields = {
        "instance_id",
        "repo",
        "base_commit",
        "problem_statement",
        "hints_text",
        "test_patch",
        "FAIL_TO_PASS",
        "PASS_TO_PASS",
        "dockerhub_tag",
        "version",
        "environment_setup_commit",
    }

    def _string_tuple(value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            # Some HF columns store JSON-encoded lists; we accept both raw
            # lists and JSON strings to be defensive against schema drift.
            try:
                import json  # local import; cheap

                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return tuple(str(x) for x in parsed)
                return (value,)
            except (ValueError, TypeError):
                return (value,)
        if isinstance(value, (list, tuple)):
            return tuple(str(x) for x in value)
        return (str(value),)

    extra = {k: v for k, v in row.items() if k not in known_fields}

    return SWEBenchTask(
        instance_id=str(row.get("instance_id", "")),
        repo=str(row.get("repo", "")),
        base_commit=str(row.get("base_commit", "")),
        problem_statement=str(row.get("problem_statement", "")),
        hints_text=str(row.get("hints_text", "") or ""),
        test_patch=str(row.get("test_patch", "") or ""),
        fail_to_pass=_string_tuple(row.get("FAIL_TO_PASS")),
        pass_to_pass=_string_tuple(row.get("PASS_TO_PASS")),
        dockerhub_tag=str(row.get("dockerhub_tag", "") or ""),
        version=str(row.get("version", "") or ""),
        environment_setup_commit=str(
            row.get("environment_setup_commit", "") or ""
        ),
        extra=extra,
    )


def load_subset(
    n: int,
    *,
    repo_filter: Optional[Iterable[str]] = None,
    dataset_name: str = DEFAULT_DATASET_NAME,
    split: str = DEFAULT_SPLIT,
    seed: Optional[int] = 42,
) -> list[SWEBenchTask]:
    """Load the first ``n`` tasks from the public split.

    Args:
        n: Number of tasks. Pass a small number (30-50) for a quick
            baseline; the public set has 731 instances total.
        repo_filter: If provided, only tasks whose ``repo`` is in the
            iterable are returned. Useful for "show me how Aura does
            on django specifically".
        dataset_name: HuggingFace dataset identifier.
        split: Dataset split. Defaults to "test" (the public subset).
        seed: Shuffle seed for reproducibility. Set to ``None`` to
            disable shuffling.

    Returns:
        A list of ``SWEBenchTask`` instances of length ``<=n`` (fewer
        if the filter is restrictive).

    Notes:
        Requires the ``datasets`` HuggingFace library. The first call
        downloads the dataset and caches it locally; subsequent calls
        are fast.
    """
    if n <= 0:
        raise ValueError(f"n must be positive; got {n}")

    load_dataset = _require_datasets()
    logger.info(
        "Loading SWE-Bench Pro: dataset=%s split=%s n=%d",
        dataset_name,
        split,
        n,
    )
    ds = load_dataset(dataset_name, split=split)
    if seed is not None:
        ds = ds.shuffle(seed=seed)

    repo_set = set(repo_filter) if repo_filter else None
    out: list[SWEBenchTask] = []
    for row in ds:
        task = _row_to_task(dict(row))
        if repo_set is not None and task.repo not in repo_set:
            continue
        out.append(task)
        if len(out) >= n:
            break
    logger.info("Loaded %d SWE-Bench Pro tasks", len(out))
    return out


def iter_tasks(
    *,
    dataset_name: str = DEFAULT_DATASET_NAME,
    split: str = DEFAULT_SPLIT,
) -> Iterator[SWEBenchTask]:
    """Yield every task in the configured split. For full-dataset runs."""
    load_dataset = _require_datasets()
    ds = load_dataset(dataset_name, split=split)
    for row in ds:
        yield _row_to_task(dict(row))


def load_gold_patches(
    instance_ids: Iterable[str],
    *,
    dataset_name: str = DEFAULT_DATASET_NAME,
    split: str = DEFAULT_SPLIT,
) -> dict[str, str]:
    """Load gold patches for the given instance ids.

    Returned dict is ``{instance_id: gold_patch_text}``. Used by
    ``scoring.score_predictions`` and NEVER by adapters — keeping the
    gold patches in a separate code path makes accidental cheating
    structurally impossible: an adapter that wants the gold patch
    has to reach into a dataset module the rest of its inputs don't
    touch, which would be obvious in review.

    Missing instance ids are silently dropped from the result; the
    scorer treats a missing gold as "no gold patch available" rather
    than failing the whole run.
    """
    load_dataset = _require_datasets()
    target_ids = set(instance_ids)
    if not target_ids:
        return {}
    logger.info(
        "Loading gold patches: dataset=%s split=%s n_targets=%d",
        dataset_name,
        split,
        len(target_ids),
    )
    ds = load_dataset(dataset_name, split=split)
    out: dict[str, str] = {}
    for row in ds:
        row_id = str(row.get("instance_id", ""))
        if row_id in target_ids:
            out[row_id] = str(row.get("patch", "") or "")
            if len(out) == len(target_ids):
                break
    return out
