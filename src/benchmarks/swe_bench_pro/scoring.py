"""
Project Aura - Unofficial SWE-Bench Pro Scoring.

Heuristic patch-similarity scoring as a CHEAP alternative to running
the official Docker harness. The output is a triage signal, NOT a
correctness metric. Two patches that fix the same bug differently can
have low similarity; two patches with high similarity can both be
broken. Use this to spot-check whether Aura is producing patches in
the right neighborhood, not to claim a benchmark score.

Three signals, increasing strictness:

1. **File-level overlap** — did the generated patch modify the same
   files as the gold patch? Precision / recall / F1 over file sets.
   Coarse but informative; a patch that touches entirely different
   files almost certainly did not fix the issue.
2. **Hunk-overlap rate** — for files both patches touched, fraction
   of gold hunks whose line ranges intersect generated hunks.
3. **Token Jaccard** — Jaccard similarity over the bag of tokens in
   added/removed lines. High = the generated patch is doing work
   in the same conceptual space as the gold patch.

The composite score is a weighted average: file F1 dominates because
it's the cheapest signal that strongly correlates with "did the
agent at least look in the right place." Hunk overlap and token
Jaccard refine it for cases where files match.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable

from .contracts import SWEBenchPrediction, SWEBenchTask

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Diff parsing
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class HunkRange:
    """An ``@@ -start,len +start,len @@`` hunk header range."""

    old_start: int
    old_len: int
    new_start: int
    new_len: int

    def overlaps(self, other: "HunkRange") -> bool:
        """True if the two hunks' OLD line ranges overlap.

        We compare against the old side (the file at base_commit)
        because that's the line space that's stable between the gold
        patch and any candidate that's working from the same base.
        """
        a_end = self.old_start + max(self.old_len, 1) - 1
        b_end = other.old_start + max(other.old_len, 1) - 1
        return not (a_end < other.old_start or b_end < self.old_start)


@dataclass(frozen=True)
class FilePatch:
    """A single file's worth of changes from a unified diff."""

    file_path: str
    hunks: tuple[HunkRange, ...]
    added_tokens: tuple[str, ...]  # tokens in `+` lines (excl. headers)
    removed_tokens: tuple[str, ...]  # tokens in `-` lines


@dataclass(frozen=True)
class ParsedDiff:
    """Parsed unified diff. Empty diff is the canonical "no patch"."""

    files: tuple[FilePatch, ...]

    @property
    def file_paths(self) -> frozenset[str]:
        return frozenset(f.file_path for f in self.files)

    @property
    def is_empty(self) -> bool:
        return not self.files


_HEADER_RE = re.compile(r"^diff --git a/(?P<a>\S+) b/(?P<b>\S+)\s*$")
_RANGE_RE = re.compile(
    r"^@@ -(?P<os>\d+)(?:,(?P<ol>\d+))? \+(?P<ns>\d+)(?:,(?P<nl>\d+))? @@"
)
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+")


def parse_unified_diff(text: str) -> ParsedDiff:
    """Parse a unified diff into a ``ParsedDiff``.

    Tolerant of cosmetic variation (with/without `index ...` headers,
    extra leading whitespace). Refuses to parse diffs that don't have
    a recognizable file header — returns an empty ParsedDiff in that
    case rather than raising.
    """
    if not text.strip():
        return ParsedDiff(files=())

    files: list[FilePatch] = []
    current_file: str | None = None
    current_hunks: list[HunkRange] = []
    added: list[str] = []
    removed: list[str] = []

    def _flush() -> None:
        nonlocal current_file, current_hunks, added, removed
        if current_file is None:
            return
        files.append(
            FilePatch(
                file_path=current_file,
                hunks=tuple(current_hunks),
                added_tokens=tuple(added),
                removed_tokens=tuple(removed),
            )
        )
        current_file = None
        current_hunks = []
        added = []
        removed = []

    for line in text.splitlines():
        m = _HEADER_RE.match(line)
        if m:
            _flush()
            # Prefer the `b` (post-image) path; fall back to `a` if missing.
            current_file = m.group("b") or m.group("a")
            continue
        if line.startswith("--- ") or line.startswith("+++ "):
            # File markers; if we don't already have a file from `diff --git`
            # we can recover one from the `+++` line.
            if current_file is None and line.startswith("+++ "):
                tail = line[4:].strip()
                if tail.startswith("b/"):
                    current_file = tail[2:]
                elif tail and tail != "/dev/null":
                    current_file = tail
            continue
        if line.startswith("@@ "):
            m = _RANGE_RE.match(line)
            if not m:
                continue
            current_hunks.append(
                HunkRange(
                    old_start=int(m.group("os")),
                    old_len=int(m.group("ol") or 1),
                    new_start=int(m.group("ns")),
                    new_len=int(m.group("nl") or 1),
                )
            )
            continue
        if current_file is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added.extend(_TOKEN_RE.findall(line[1:]))
        elif line.startswith("-") and not line.startswith("---"):
            removed.extend(_TOKEN_RE.findall(line[1:]))

    _flush()
    return ParsedDiff(files=tuple(files))


# -----------------------------------------------------------------------------
# Per-task scoring
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class FileSetScore:
    precision: float
    recall: float
    f1: float
    intersection: tuple[str, ...]
    only_in_generated: tuple[str, ...]
    only_in_gold: tuple[str, ...]


@dataclass(frozen=True)
class TaskSimilarityScore:
    """Heuristic similarity between a generated patch and the gold patch."""

    instance_id: str
    has_generated_patch: bool
    has_gold_patch: bool
    file_set: FileSetScore
    hunk_overlap_rate: float  # in [0, 1]; 0 if no overlapping files
    token_jaccard: float  # over added+removed tokens; in [0, 1]
    composite_score: float  # weighted [0, 1]

    @property
    def is_in_neighborhood(self) -> bool:
        """Heuristic: is the generated patch even close to the gold patch?

        True when the generated patch touched at least one of the
        files the gold patch touched. Useful as a precision filter
        before doing more expensive comparisons.
        """
        return self.file_set.f1 > 0.0


@dataclass(frozen=True)
class SimilarityReport:
    """Aggregate report across many tasks."""

    per_task: tuple[TaskSimilarityScore, ...]
    mean_file_f1: float
    mean_hunk_overlap_rate: float
    mean_token_jaccard: float
    mean_composite: float
    in_neighborhood_count: int
    total_tasks: int

    @property
    def in_neighborhood_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.in_neighborhood_count / self.total_tasks


# Composite score weights. File F1 dominates because it's the cheapest
# signal that strongly correlates with "did the agent look in the
# right place." Hunk overlap refines it for matching files; token
# Jaccard catches semantic similarity within hunks.
_W_FILE = 0.5
_W_HUNK = 0.3
_W_TOKEN = 0.2


def score_one(
    instance_id: str,
    generated_patch: str,
    gold_patch: str,
) -> TaskSimilarityScore:
    """Score a single (generated, gold) pair."""
    gen = parse_unified_diff(generated_patch)
    gold = parse_unified_diff(gold_patch)

    file_set = _file_set_score(gen.file_paths, gold.file_paths)
    hunk_rate = _hunk_overlap_rate(gen, gold)
    token_jac = _token_jaccard(gen, gold)
    composite = (
        _W_FILE * file_set.f1 + _W_HUNK * hunk_rate + _W_TOKEN * token_jac
    )

    return TaskSimilarityScore(
        instance_id=instance_id,
        has_generated_patch=not gen.is_empty,
        has_gold_patch=not gold.is_empty,
        file_set=file_set,
        hunk_overlap_rate=hunk_rate,
        token_jaccard=token_jac,
        composite_score=composite,
    )


def score_predictions(
    predictions: Iterable[SWEBenchPrediction],
    gold_patches: dict[str, str],
) -> SimilarityReport:
    """Score every prediction against its gold patch."""
    per_task: list[TaskSimilarityScore] = []
    for pred in predictions:
        gold = gold_patches.get(pred.instance_id, "")
        per_task.append(score_one(pred.instance_id, pred.model_patch, gold))

    n = len(per_task)
    if n == 0:
        return SimilarityReport(
            per_task=(),
            mean_file_f1=0.0,
            mean_hunk_overlap_rate=0.0,
            mean_token_jaccard=0.0,
            mean_composite=0.0,
            in_neighborhood_count=0,
            total_tasks=0,
        )
    return SimilarityReport(
        per_task=tuple(per_task),
        mean_file_f1=sum(s.file_set.f1 for s in per_task) / n,
        mean_hunk_overlap_rate=sum(s.hunk_overlap_rate for s in per_task) / n,
        mean_token_jaccard=sum(s.token_jaccard for s in per_task) / n,
        mean_composite=sum(s.composite_score for s in per_task) / n,
        in_neighborhood_count=sum(1 for s in per_task if s.is_in_neighborhood),
        total_tasks=n,
    )


# -----------------------------------------------------------------------------
# Internal scoring helpers
# -----------------------------------------------------------------------------


def _file_set_score(
    generated: frozenset[str], gold: frozenset[str]
) -> FileSetScore:
    if not generated and not gold:
        # Both patches are empty: vacuously matching, but not informative.
        return FileSetScore(
            precision=0.0,
            recall=0.0,
            f1=0.0,
            intersection=(),
            only_in_generated=(),
            only_in_gold=(),
        )
    inter = generated & gold
    precision = len(inter) / len(generated) if generated else 0.0
    recall = len(inter) / len(gold) if gold else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return FileSetScore(
        precision=precision,
        recall=recall,
        f1=f1,
        intersection=tuple(sorted(inter)),
        only_in_generated=tuple(sorted(generated - gold)),
        only_in_gold=tuple(sorted(gold - generated)),
    )


def _hunk_overlap_rate(gen: ParsedDiff, gold: ParsedDiff) -> float:
    """Fraction of gold hunks (across overlapping files) intersected by
    a generated hunk."""
    gen_by_file = {f.file_path: f.hunks for f in gen.files}
    total_gold_hunks = 0
    matched_gold_hunks = 0
    for gold_file in gold.files:
        gen_hunks = gen_by_file.get(gold_file.file_path, ())
        for g in gold_file.hunks:
            total_gold_hunks += 1
            if any(g.overlaps(h) for h in gen_hunks):
                matched_gold_hunks += 1
    if total_gold_hunks == 0:
        return 0.0
    return matched_gold_hunks / total_gold_hunks


def _token_jaccard(gen: ParsedDiff, gold: ParsedDiff) -> float:
    """Jaccard similarity over added+removed tokens across all files.

    Stop-tokens (single-character symbols, common keywords) are NOT
    filtered — Jaccard is robust enough that universal tokens
    contribute proportionally to both sides.
    """

    def _bag(diff: ParsedDiff) -> set[str]:
        bag: set[str] = set()
        for f in diff.files:
            bag.update(f.added_tokens)
            bag.update(f.removed_tokens)
        return bag

    a = _bag(gen)
    b = _bag(gold)
    if not a and not b:
        return 0.0
    inter = a & b
    union = a | b
    if not union:
        return 0.0
    return len(inter) / len(union)
