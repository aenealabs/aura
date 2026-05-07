"""
Project Aura - Aura-Bedrock SWE-Bench Pro Adapter.

The real adapter that drives an Aura LLM client (Bedrock-backed in
production) at SWE-Bench Pro tasks. Per-task cost tracking via the
existing per-scan cost tracker pattern (ADR-049 / vulnerability
scanner). Concurrency control via semaphore.

The LLM client is injected via the ``LLMClient`` Protocol so the
adapter is testable against a mock client that returns canned
responses — no AWS, no Bedrock, no live keys.

Note on output: SWE-Bench evaluates correctness via the harness's
test suite, so this adapter does NOT post-process the diff beyond
trimming markdown fences. We trust the model to produce a valid
unified diff or an empty response (per the system prompt). Aura's
sandbox verification (ADR-085) is not run here — the SWE-Bench
harness has its own verification step.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Protocol

from src.services.vulnerability_scanner.analysis.cost_tracker import (
    DEFAULT_TIER_PRICING,
    CostCapExceededError,
    CostTracker,
    TierPricing,
)
from src.services.vulnerability_scanner.analysis.capability import (
    ModelCapabilityTier,
)

from .adapter import Adapter, AdapterError
from .contracts import SWEBenchPrediction, SWEBenchTask
from .prompts import build_user_prompt, system_prompt

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Subset of Aura's LLM client interface this adapter needs."""

    async def invoke(
        self,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> dict[str, Any]:
        ...


class AuraBedrockAdapter(Adapter):
    """SWE-Bench Pro adapter driven by an injected LLM client.

    Production wiring: pass a Bedrock-backed ``LLMClient``
    (the same one used by the vulnerability scanner). Tests pass a
    mock client that returns canned content with deterministic token
    counts.

    Cost is tracked across all tasks so the runner's ``total_cost_usd``
    aggregates correctly. Cost-cap enforcement uses the existing
    ``CostTracker`` from ADR-049; if the cap is reached mid-run, the
    remaining tasks are skipped with adapter errors so the harness
    sees the partial result rather than a hung run.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        model_id: str,
        *,
        max_tokens_per_request: int = 4096,
        temperature: float = 0.0,  # SWE-Bench prefers determinism
        top_p: float = 1.0,
        run_cost_cap_usd: float = 100.0,
        pricing: Optional[dict[ModelCapabilityTier, TierPricing]] = None,
    ) -> None:
        self._llm = llm_client
        self._model_id = model_id
        self._max_tokens = max_tokens_per_request
        self._temperature = temperature
        self._top_p = top_p
        self._cost_tracker = CostTracker(
            pricing=pricing or DEFAULT_TIER_PRICING,
            caps_usd={
                ModelCapabilityTier.STANDARD: run_cost_cap_usd,
                ModelCapabilityTier.ADVANCED: run_cost_cap_usd,
            },
        )

    @property
    def model_name(self) -> str:
        return f"aura+{self._model_id}"

    @property
    def total_cost_usd(self) -> float:
        return self._cost_tracker.total_cost_usd

    async def solve(self, task: SWEBenchTask) -> SWEBenchPrediction:
        # Cap pre-flight check so a runaway run halts cleanly rather than
        # generating partial junk. We project a conservative ceiling
        # (full max_tokens consumed) — if that would breach the cap, we
        # skip this task with an adapter error so the runner records
        # the right outcome and continues.
        if self._cost_tracker.would_exceed_cap(
            ModelCapabilityTier.STANDARD,
            input_tokens=8_000,
            output_tokens=self._max_tokens,
        ):
            raise AdapterError(
                f"run cost cap reached; skipping {task.instance_id}"
            )

        sys_prompt = system_prompt()
        user_prompt = build_user_prompt(task)

        try:
            response = await self._llm.invoke(
                model_id=self._model_id,
                system_prompt=sys_prompt,
                user_prompt=user_prompt,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                top_p=self._top_p,
            )
        except Exception as exc:  # noqa: BLE001 - infra failures become AdapterError
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
            # Cap breached by the just-completed invocation. Surface as an
            # adapter error so the runner records ADAPTER_ERROR, and so
            # subsequent ``would_exceed_cap`` pre-flight checks see the
            # near-cap state and refuse remaining tasks. The projected
            # cost is recorded best-effort for telemetry.
            raise AdapterError(
                f"cost cap exceeded for {task.instance_id}: {exc}"
            ) from exc

        raw = str(response.get("content", ""))
        patch = _extract_unified_diff(raw)

        return SWEBenchPrediction(
            instance_id=task.instance_id,
            model_patch=patch,
            model_name_or_path=self.model_name,
            aura_metadata={
                "cost_usd": cost,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model_id": self._model_id,
                "raw_length": len(raw),
                "patch_length": len(patch),
            },
        )


def _extract_unified_diff(raw: str) -> str:
    """Pull the unified diff out of a model response.

    Tolerates two common formatting tics:
    - Wrapping the diff in a ```diff fenced block
    - Leading/trailing whitespace

    If the response contains anything other than a unified diff (prose,
    explanations) we DO NOT try to salvage it — the system prompt is
    explicit that prose is forbidden, and best-effort parsing of model
    chatter into "what they probably meant" produces silent quality
    degradation. Empty string ("declined to attempt") is preferred to
    a malformed diff.
    """
    text = raw.strip()
    if not text:
        return ""

    # Strip a single fenced block ```diff ... ``` or ``` ... ``` if
    # the model wrapped the diff against the system prompt's
    # instructions.
    if text.startswith("```"):
        lines = text.split("\n")
        body: list[str] = []
        in_fence = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                body.append(line)
        text = "\n".join(body).strip()

    # Conservative validity check: if it doesn't start with the unified
    # diff `diff --git` or `--- ` marker, treat as invalid and return
    # empty. The model violated the system prompt; an empty patch is
    # the right signal to the harness.
    first_line = text.split("\n", 1)[0]
    if not (
        first_line.startswith("diff --git")
        or first_line.startswith("--- ")
    ):
        return ""
    return text + ("\n" if not text.endswith("\n") else "")
