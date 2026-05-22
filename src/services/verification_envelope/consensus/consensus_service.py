"""Project Aura - N-of-M Consensus Service (ADR-085 Phase 1).

Orchestrates the consensus pillar of the Deterministic Verification
Envelope: invokes a generator N times in parallel, normalises every
output to canonical AST form, builds the pairwise equivalence matrix,
and applies the M-of-N convergence decision.

The generator is protocol-typed so this service is testable without a
real LLM. In production, the orchestrator passes a function bound to
``MetaOrchestrator.spawn_coder_agent`` (or the agent-orchestrator's
equivalent); in tests we pass a lambda that returns canned strings.

Audit trail: every consensus round emits a frozen :class:`ConsensusResult`
with a deterministic ``audit_record_id`` derived from the prompt hash
and the timestamp. The pairwise similarity matrix is included so a
reviewer (HITL or auditor) can reconstruct the decision after the fact.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Sequence

from src.services.verification_envelope.config import DVEConfig
from src.services.verification_envelope.consensus.ast_normalizer import ASTNormalizer
from src.services.verification_envelope.consensus.consensus_policy import (
    evaluate_convergence,
)
from src.services.verification_envelope.consensus.semantic_equivalence import (
    SemanticEquivalenceChecker,
    _EmbeddingProvider,
)
from src.services.verification_envelope.consensus.static_verifier import (
    StaticVerifierDispatcher,
)
from src.services.verification_envelope.contracts import (
    ASTCanonicalForm,
    ConsensusOutcome,
    ConsensusResult,
    EquivalenceCheck,
    StaticVerificationSummary,
)

logger = logging.getLogger(__name__)


# A generator is any callable that, given a prompt, returns the model's
# code output. Passed in by the caller so this service stays decoupled
# from the agent / Bedrock plumbing.
GeneratorFn = Callable[[str], Awaitable[str]]


class ConsensusService:
    """N-of-M consensus generation."""

    def __init__(
        self,
        config: DVEConfig,
        generator: GeneratorFn,
        embedding_provider: _EmbeddingProvider | None = None,
        *,
        normalizer: ASTNormalizer | None = None,
        equivalence_checker: SemanticEquivalenceChecker | None = None,
        static_verifier: StaticVerifierDispatcher | None = None,
    ) -> None:
        self._config = config
        self._generator = generator
        self._normalizer = normalizer or ASTNormalizer()
        self._equivalence = equivalence_checker or SemanticEquivalenceChecker(
            embedding_provider=embedding_provider,
            cosine_threshold=config.embedding_cosine_threshold,
            enable_embedding_fallback=config.enable_embedding_fallback,
        )
        # Non-LLM second voice (issue #209). When None, the consensus
        # service behaves identically to its pre-#209 form. When the
        # dispatcher is provided AND ``require_non_llm_voice`` is set,
        # disagreement on the selected centroid downgrades CONVERGED
        # to DIVERGED.
        self._static_verifier = static_verifier

    async def generate_and_check(
        self, prompt: str, *, audit_id: str | None = None
    ) -> ConsensusResult:
        """Run N generations, build the equivalence matrix, return the result."""
        start = time.time()
        n = self._config.consensus_n
        m = self._config.consensus_m
        record_id = audit_id or self._make_audit_id(prompt)

        outputs = await self._generate_n(prompt, n=n)
        canonical_forms = tuple(self._normalizer.normalize(s) for s in outputs)
        pairwise = await self._build_pairwise_matrix(canonical_forms)

        decision = evaluate_convergence(
            candidates=outputs,
            canonical_forms=canonical_forms,
            pairwise=pairwise,
            m_required=m,
        )

        selected_output: str | None = None
        if (
            decision.outcome == ConsensusOutcome.CONVERGED
            and decision.selected_index is not None
        ):
            selected_output = outputs[decision.selected_index]

        # Convergence rate is the size of the largest cluster / N.
        convergence_rate = len(decision.converged_indices) / n if n > 0 else 0.0

        similarity_matrix = tuple(tuple(c.similarity for c in row) for row in pairwise)

        # Non-LLM second voice (issue #209). Run only when the verifier
        # is configured AND either the policy requires it OR we are in
        # shadow mode. Verdict is recorded in the result regardless; it
        # only overrides the consensus outcome when require_non_llm_voice
        # is set AND the verifier disagrees on the selected centroid.
        outcome = decision.outcome
        static_summary = StaticVerificationSummary()
        should_run_static = (
            self._static_verifier is not None
            and not self._static_verifier.is_empty()
            and (
                self._config.require_non_llm_voice
                or self._config.static_verifier_shadow_mode
            )
        )
        if should_run_static and selected_output is not None:
            report = self._static_verifier.verify(selected_output)
            static_summary = StaticVerificationSummary(
                enabled=True,
                agreed_with_llm=report.agreed_with_llm,
                verifier_count=report.verifier_count,
                verifier_ids=self._static_verifier.verifier_ids,
                blocking_finding_count=sum(
                    1
                    for f in report.aggregated_findings
                    if f.severity.upper() in {"CRITICAL", "HIGH"}
                ),
                aggregate_latency_ms=report.aggregate_latency_ms,
                rationale=(
                    "static voice agreed"
                    if report.agreed_with_llm
                    else "static voice disagreed -- forcing DIVERGED"
                ),
            )
            if (
                self._config.require_non_llm_voice
                and report.disagreed_with_llm
                and outcome == ConsensusOutcome.CONVERGED
            ):
                logger.warning(
                    "consensus %s overridden CONVERGED->DIVERGED by static voice "
                    "(%d blocking findings across %d verifiers)",
                    record_id,
                    static_summary.blocking_finding_count,
                    static_summary.verifier_count,
                )
                outcome = ConsensusOutcome.DIVERGED
                selected_output = None
        elif (
            self._config.require_non_llm_voice
            and selected_output is not None
            and (self._static_verifier is None or self._static_verifier.is_empty())
        ):
            # Policy requires a non-LLM voice but none is configured.
            # Fail closed: downgrade to DIVERGED and surface in audit.
            logger.warning(
                "consensus %s requires non-LLM voice but no verifier configured; "
                "downgrading CONVERGED->DIVERGED",
                record_id,
            )
            outcome = ConsensusOutcome.DIVERGED
            selected_output = None
            static_summary = StaticVerificationSummary(
                enabled=False,
                agreed_with_llm=False,
                rationale="policy requires non-LLM voice; none configured (fail-closed)",
            )

        latency_ms = (time.time() - start) * 1000.0
        logger.info(
            "consensus %s outcome=%s n=%d m_required=%d converged=%d "
            "selection=%s rate=%.2f latency_ms=%.0f "
            "static_voice=%s static_agreed=%s",
            record_id,
            outcome.value,
            n,
            m,
            len(decision.converged_indices),
            decision.selection_method,
            convergence_rate,
            latency_ms,
            static_summary.enabled,
            static_summary.agreed_with_llm,
        )

        return ConsensusResult(
            outcome=outcome,
            n_generated=n,
            m_required=m,
            m_converged=len(decision.converged_indices),
            selected_output=selected_output,
            selection_method=decision.selection_method,
            canonical_forms=canonical_forms,
            pairwise_similarities=similarity_matrix,
            convergence_rate=convergence_rate,
            audit_record_id=record_id,
            computed_at=datetime.now(timezone.utc),
            static_verification=static_summary,
        )

    # ------------------------------------------------------------ helpers

    async def _generate_n(self, prompt: str, *, n: int) -> tuple[str, ...]:
        sem = asyncio.Semaphore(self._config.consensus_max_concurrency)

        async def _one() -> str:
            async with sem:
                return await self._generator(prompt)

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*[_one() for _ in range(n)]),
                timeout=self._config.consensus_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(
                "consensus generation timed out after %.1fs",
                self._config.consensus_timeout_seconds,
            )
            raise
        return tuple(results)

    async def _build_pairwise_matrix(
        self, canonical_forms: Sequence[ASTCanonicalForm]
    ) -> tuple[tuple[EquivalenceCheck, ...], ...]:
        n = len(canonical_forms)
        rows: list[list[EquivalenceCheck]] = [
            [
                EquivalenceCheck(
                    are_equivalent=True,
                    method="self",
                    similarity=1.0,
                    rationale="i == j",
                )
                for _ in range(n)
            ]
            for _ in range(n)
        ]
        for i in range(n):
            for j in range(i + 1, n):
                check = await self._equivalence.check(
                    canonical_forms[i], canonical_forms[j]
                )
                rows[i][j] = check
                rows[j][i] = check
        return tuple(tuple(row) for row in rows)

    @staticmethod
    def _make_audit_id(prompt: str) -> str:
        h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        return f"dve-consensus-{h}-{uuid.uuid4().hex[:8]}"
