"""
Project Aura - Aura-Enhanced SWE-Bench Pro Adapter.

Composes the existing single-call ``AuraBedrockAdapter`` with two of
Aura's actual production primitives:

1. **GraphRAG repo-context retrieval** — pulls relevant code context
   from the affected repository before prompting the model. Mirrors
   what ``ContextRetrievalService`` does for the vulnerability scanner
   (ADR-084) and what the Coder agent receives in production
   (ADR-032 multi-agent flow).

2. **Single Reviewer pass with one targeted revision** — after the
   Coder produces a draft diff, a Reviewer agent (constitutional-AI
   style critique) inspects it. If material issues are flagged, the
   Coder gets one revision attempt with the critique as feedback.

The goal: validate that Aura's primitives **compose** to produce
better SWE-Bench Pro performance than the bare model, without going
all the way to a full multi-hour, multi-agent campaign run. A
1-2 week wiring exercise, not a 12-week optimization push.

Status: scaffolding only. Production wiring requires:

- A ``RepoContextRetriever`` backed by GraphRAG (Neptune + OpenSearch).
  ``NullRetriever`` is the default; tests use ``StubRetriever`` /
  ``CannedRetriever``.
- A ``Reviewer`` backed by a constitutional-AI critique prompt.
  ``NullReviewer`` is the default; tests use ``StubReviewer`` /
  ``ScriptedReviewer``.

When both production components are wired in, this adapter takes the
same SWE-Bench Pro task and routes through the enhanced flow rather
than the single-call flow. Switch via the runner with a future
``--mode unofficial-enhanced`` once you've decided to invest in it.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from src.services.vulnerability_scanner.analysis.capability import (
    ModelCapabilityTier,
)
from src.services.vulnerability_scanner.analysis.cost_tracker import (
    DEFAULT_TIER_PRICING,
    CostCapExceededError,
    CostTracker,
    TierPricing,
)

from .adapter import Adapter, AdapterError
from .aura_adapter import LLMClient, _extract_unified_diff
from .contracts import SWEBenchPrediction, SWEBenchTask
from .prompts import build_user_prompt, system_prompt

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Pluggable component protocols
# -----------------------------------------------------------------------------


class RepoContextRetriever(Protocol):
    """Pulls relevant repository context for a SWE-Bench Pro task.

    Production implementation backed by Aura's GraphRAG stack —
    Neptune for structural graph, OpenSearch for semantic vector
    retrieval, BM25 for keyword recall. Tests inject deterministic
    stubs that return canned context.

    The contract is intentionally simple: take a task, return a
    string of context to splice into the prompt. Whatever context-
    selection / token-budgeting logic the retriever wants to apply
    is internal.
    """

    async def retrieve(self, task: SWEBenchTask) -> str:
        """Return relevant repo context for ``task``, or '' if none."""
        ...


class Reviewer(Protocol):
    """Critiques a draft diff and decides whether revision is needed.

    Production implementation backed by Aura's constitutional-AI
    critic (ADR-063). Tests inject deterministic stubs that return
    pre-scripted critiques. The contract surfaces both a binary
    ``revision_required`` flag and the critique text so the Coder
    can use it as targeted feedback.
    """

    async def review(
        self, task: SWEBenchTask, draft_patch: str
    ) -> "ReviewResult":
        """Return a ``ReviewResult`` for the draft."""
        ...


@dataclass(frozen=True)
class ReviewResult:
    """Outcome of a single Reviewer pass."""

    revision_required: bool
    critique: str  # human-readable; passed back to Coder for revision
    confidence: float = 0.0  # in [0, 1]; for telemetry


# -----------------------------------------------------------------------------
# Default pass-through implementations
# -----------------------------------------------------------------------------


class NullRetriever:
    """Returns empty context. Used when GraphRAG isn't wired in.

    With a NullRetriever, the enhanced adapter's behaviour reduces to
    "the bare adapter + a Reviewer pass" — useful for measuring the
    Reviewer's contribution in isolation.
    """

    async def retrieve(self, task: SWEBenchTask) -> str:
        return ""


class NullReviewer:
    """Always passes the draft. Used when the constitutional-AI critic
    isn't wired in.

    With a NullReviewer, the enhanced adapter's behaviour reduces to
    "the bare adapter + GraphRAG retrieval" — useful for measuring
    retrieval's contribution in isolation.
    """

    async def review(
        self, task: SWEBenchTask, draft_patch: str
    ) -> ReviewResult:
        return ReviewResult(revision_required=False, critique="", confidence=1.0)


# -----------------------------------------------------------------------------
# Test stubs
# -----------------------------------------------------------------------------


class StubRetriever:
    """Returns the same canned context for every task. Test helper."""

    def __init__(self, context: str) -> None:
        self._context = context
        self.calls: int = 0

    async def retrieve(self, task: SWEBenchTask) -> str:
        self.calls += 1
        return self._context


class CannedRetriever:
    """Returns per-task context from a mapping. Test helper.

    Configure with ``{instance_id: context_string}``. Instances not
    in the mapping receive an empty context (graceful degradation
    matches production behaviour when GraphRAG returns nothing).
    """

    def __init__(self, contexts: dict[str, str]) -> None:
        self._contexts = contexts
        self.calls: int = 0

    async def retrieve(self, task: SWEBenchTask) -> str:
        self.calls += 1
        return self._contexts.get(task.instance_id, "")


class StubReviewer:
    """Always returns the same canned ``ReviewResult``. Test helper."""

    def __init__(
        self,
        revision_required: bool = False,
        critique: str = "",
        confidence: float = 1.0,
    ) -> None:
        self._template = ReviewResult(
            revision_required=revision_required,
            critique=critique,
            confidence=confidence,
        )
        self.calls: int = 0

    async def review(
        self, task: SWEBenchTask, draft_patch: str
    ) -> ReviewResult:
        self.calls += 1
        return self._template


class ScriptedReviewer:
    """Per-task scripted ``ReviewResult``. Test helper.

    Used to test mixed-outcome runs (e.g. some tasks pass review on
    first try, others trigger revision).
    """

    def __init__(self, scripts: dict[str, ReviewResult]) -> None:
        self._scripts = scripts
        self.calls: int = 0

    async def review(
        self, task: SWEBenchTask, draft_patch: str
    ) -> ReviewResult:
        self.calls += 1
        return self._scripts.get(
            task.instance_id,
            ReviewResult(revision_required=False, critique="", confidence=1.0),
        )


# -----------------------------------------------------------------------------
# Enhanced adapter
# -----------------------------------------------------------------------------


_REVIEWER_FEEDBACK_PROMPT = """\
A previous attempt at this task produced the diff below. A reviewer
identified the following concerns. Produce a revised diff that
addresses the concerns while still resolving the original issue.

If the concerns are unfounded, you may return the original diff
unchanged. If you cannot produce a confident revised fix, return an
empty diff (no output).

OUTPUT REQUIREMENTS:
- Respond with ONLY the unified diff. No prose, no markdown fences,
  no commentary.

<original_diff>
{draft_patch}
</original_diff>

<reviewer_critique>
{critique}
</reviewer_critique>
"""


class AuraEnhancedAdapter(Adapter):
    """SWE-Bench Pro adapter with GraphRAG context + Reviewer pass.

    Composes:

    1. ``retriever.retrieve(task)`` — pull repo context (or '' if
       NullRetriever is configured).
    2. First LLM call (Coder) — generate a draft diff with the
       SWE-Bench prompt augmented by the retrieved context.
    3. ``reviewer.review(task, draft)`` — critique the draft.
    4. If ``revision_required``, a second LLM call (Coder revision)
       with the critique as feedback. Otherwise the draft becomes
       the final patch.

    Tracks aggregate cost across both passes via the same
    ``CostTracker`` used by the bare adapter (ADR-049). Hard cap on
    total run cost; halt-cleanly via ``AdapterError`` when reached.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        model_id: str,
        *,
        retriever: Optional[RepoContextRetriever] = None,
        reviewer: Optional[Reviewer] = None,
        max_tokens_per_request: int = 4096,
        temperature: float = 0.0,
        top_p: float = 1.0,
        run_cost_cap_usd: float = 100.0,
        pricing: Optional[dict[ModelCapabilityTier, TierPricing]] = None,
        max_revision_attempts: int = 1,
    ) -> None:
        self._llm = llm_client
        self._model_id = model_id
        self._retriever: RepoContextRetriever = retriever or NullRetriever()
        self._reviewer: Reviewer = reviewer or NullReviewer()
        self._max_tokens = max_tokens_per_request
        self._temperature = temperature
        self._top_p = top_p
        self._max_revisions = max_revision_attempts
        self._cost_tracker = CostTracker(
            pricing=pricing or DEFAULT_TIER_PRICING,
            caps_usd={
                ModelCapabilityTier.STANDARD: run_cost_cap_usd,
                ModelCapabilityTier.ADVANCED: run_cost_cap_usd,
            },
        )

    @property
    def model_name(self) -> str:
        return f"aura-enhanced+{self._model_id}"

    @property
    def total_cost_usd(self) -> float:
        return self._cost_tracker.total_cost_usd

    async def solve(self, task: SWEBenchTask) -> SWEBenchPrediction:
        # Pre-flight cap check covering both passes (Coder + possible revision).
        # We project a generous ceiling so a single task can't surprise the cap.
        max_passes = 1 + self._max_revisions
        projected_input_per_pass = 12_000  # context-augmented prompts run larger
        if self._cost_tracker.would_exceed_cap(
            ModelCapabilityTier.STANDARD,
            input_tokens=projected_input_per_pass * max_passes,
            output_tokens=self._max_tokens * max_passes,
        ):
            raise AdapterError(
                f"run cost cap would be exceeded; skipping {task.instance_id}"
            )

        repo_context = await self._retriever.retrieve(task)

        # Pass 1: Coder draft with augmented prompt.
        draft_patch, draft_meta = await self._coder_pass(
            task, repo_context=repo_context, prior_critique=""
        )

        if not draft_patch:
            # Empty draft: skip the Reviewer pass; nothing to critique.
            return SWEBenchPrediction(
                instance_id=task.instance_id,
                model_patch="",
                model_name_or_path=self.model_name,
                aura_metadata={
                    "passes": 1,
                    "had_repo_context": bool(repo_context),
                    "review_triggered_revision": False,
                    **draft_meta,
                },
            )

        # Pass 2: Reviewer critique.
        review = await self._reviewer.review(task, draft_patch)

        if not review.revision_required:
            return SWEBenchPrediction(
                instance_id=task.instance_id,
                model_patch=draft_patch,
                model_name_or_path=self.model_name,
                aura_metadata={
                    "passes": 1,
                    "had_repo_context": bool(repo_context),
                    "review_triggered_revision": False,
                    "review_confidence": review.confidence,
                    **draft_meta,
                },
            )

        # Pass 3: Coder revision with critique as feedback.
        revised_patch, revision_meta = await self._coder_pass(
            task,
            repo_context=repo_context,
            prior_critique=review.critique,
            prior_draft=draft_patch,
        )

        # If the revision came back empty, fall back to the draft. The
        # alternative is "Reviewer flagged a problem and Coder couldn't
        # fix it", in which case the draft is at least a *coherent*
        # diff even if imperfect.
        final_patch = revised_patch or draft_patch

        return SWEBenchPrediction(
            instance_id=task.instance_id,
            model_patch=final_patch,
            model_name_or_path=self.model_name,
            aura_metadata={
                "passes": 2,
                "had_repo_context": bool(repo_context),
                "review_triggered_revision": True,
                "review_confidence": review.confidence,
                "revision_was_empty": not revised_patch,
                "draft_input_tokens": draft_meta.get("input_tokens", 0),
                "revision_input_tokens": revision_meta.get("input_tokens", 0),
                "draft_output_tokens": draft_meta.get("output_tokens", 0),
                "revision_output_tokens": revision_meta.get("output_tokens", 0),
                "cost_usd": (
                    float(draft_meta.get("cost_usd", 0))
                    + float(revision_meta.get("cost_usd", 0))
                ),
            },
        )

    # ------------------------------------------------------------------ helpers

    async def _coder_pass(
        self,
        task: SWEBenchTask,
        *,
        repo_context: str,
        prior_critique: str,
        prior_draft: str = "",
    ) -> tuple[str, dict[str, Any]]:
        """Single Coder LLM call. Returns (extracted_patch, metadata)."""
        if prior_critique:
            user_prompt = _REVIEWER_FEEDBACK_PROMPT.format(
                draft_patch=prior_draft,
                critique=prior_critique,
            )
        else:
            user_prompt = build_user_prompt(task, repo_context=repo_context)

        try:
            response = await self._llm.invoke(
                model_id=self._model_id,
                system_prompt=system_prompt(),
                user_prompt=user_prompt,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                top_p=self._top_p,
            )
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(
                f"LLM invocation failed for {task.instance_id}: {exc}"
            ) from exc

        input_tokens = int(response.get("input_tokens", 0))
        output_tokens = int(response.get("output_tokens", 0))
        try:
            cost = self._cost_tracker.record(
                ModelCapabilityTier.STANDARD,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except CostCapExceededError as exc:
            raise AdapterError(
                f"cost cap exceeded for {task.instance_id}: {exc}"
            ) from exc

        patch = _extract_unified_diff(str(response.get("content", "")))
        meta = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "model_id": self._model_id,
        }
        return patch, meta
