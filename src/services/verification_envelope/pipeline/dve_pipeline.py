"""Project Aura - DVE pipeline orchestrator (ADR-085 Phase 5).

Joins the four DVE pillars into a single async run that converts an
:class:`AgentTask` into a final :class:`DVEResult`:

    1. **Consensus** (Phase 1) — N-of-M generation with AST + embedding
       equivalence check. Diverged outputs short-circuit to HITL.
    2. **Constitutional AI** (ADR-063, existing) — critique-revision pass
       on the consensus output. Optional; disabled when no service is
       supplied.
    3. **Coherence** (ADR-081 CGE, existing) — deterministic 7-axis
       scoring + composite CCS. The CGE is also where the policy
       constraint violations from later stages are accumulated and
       routed through the action determination.
    4. **Formal verification** (Phase 3) — Z3 SMT discharge of the
       translator output. PROVED → continue; FAILED / UNKNOWN with
       DAL A/B → REJECT or HITL.
    5. **Sandbox + structural coverage** (Phase 2) — runs the customer's
       test suite under coverage instrumentation; the gate compares
       results to the DAL coverage policy.
    6. **HITL** (Phase 1 prerequisite, ADR-032) — captured in the
       overall verdict; the surrounding pipeline is responsible for
       creating an approval request when ``HITL_REQUIRED`` is the
       outcome.

The orchestrator is intentionally store-/sink-agnostic — every cloud
side-effect goes through a sink protocol so the same pipeline runs in
dev (in-memory sinks) and production (S3 + DynamoDB sinks) without
swapping the orchestrator.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Sequence

from src.services.verification_envelope.contracts import (
    ConsensusOutcome,
    ConsensusResult,
    DVEOverallVerdict,
    DVEResult,
    MCDCCoverageReport,
    VerificationResult,
    VerificationVerdict,
)
from src.services.verification_envelope.config import DVEConfig
from src.services.verification_envelope.consensus.consensus_service import (
    ConsensusService,
    GeneratorFn,
)
from src.services.verification_envelope.coverage.coverage_gate import (
    CoverageGateInput,
    CoverageGateService,
)
from src.services.verification_envelope.formal.verification_gate import (
    FormalGateInput,
    VerificationGateService,
)
from src.services.verification_envelope.policies import (
    DEFAULT_PROFILE_NAME,
    get_coverage_policy,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- contracts


@dataclass(frozen=True)
class DVEPipelineInput:
    """Inputs for one DVE pipeline run.

    The pipeline is generator-driven (Phase 1's GeneratorFn protocol),
    so the same orchestrator drives Bedrock Coder agents, OpenAI
    direct, Gemini, or test stubs without distinction.
    """

    prompt: str
    coverage_input: CoverageGateInput | None = None
    formal_input: FormalGateInput | None = None
    profile_name: str = DEFAULT_PROFILE_NAME
    audit_id_hint: str | None = None
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)


# Hook for the optional constitutional-AI step. Must accept the
# consensus output and return either the same string (no revision) or a
# revised string. Async to keep the pipeline's event loop free.
ConstitutionalReviser = Callable[[str], Awaitable[str]]


# ---------------------------------------------------------------- service


class DVEPipeline:
    """End-to-end DVE pipeline orchestrator."""

    def __init__(
        self,
        *,
        config: DVEConfig,
        consensus_service: ConsensusService,
        coverage_gate: CoverageGateService | None = None,
        formal_gate: VerificationGateService | None = None,
        constitutional_reviser: ConstitutionalReviser | None = None,
    ) -> None:
        self._config = config
        self._consensus = consensus_service
        self._coverage = coverage_gate
        self._formal = formal_gate
        self._constitutional = constitutional_reviser

    @classmethod
    def from_generator(
        cls,
        *,
        config: DVEConfig,
        generator: GeneratorFn,
        coverage_gate: CoverageGateService | None = None,
        formal_gate: VerificationGateService | None = None,
        constitutional_reviser: ConstitutionalReviser | None = None,
    ) -> "DVEPipeline":
        """Convenience constructor: build the consensus service from a
        generator and forward the rest unchanged."""
        return cls(
            config=config,
            consensus_service=ConsensusService(config=config, generator=generator),
            coverage_gate=coverage_gate,
            formal_gate=formal_gate,
            constitutional_reviser=constitutional_reviser,
        )

    # -------------------------------------------------------------- run

    async def run(self, pipeline_input: DVEPipelineInput) -> DVEResult:
        start = time.time()
        dal_level = self._dal_level_for_profile(pipeline_input.profile_name)

        # Stage 1 — N-of-M consensus.
        consensus = await self._consensus.generate_and_check(
            pipeline_input.prompt, audit_id=pipeline_input.audit_id_hint
        )

        if consensus.outcome == ConsensusOutcome.DIVERGED:
            return self._hitl_escalation(
                consensus,
                start=start,
                dal_level=dal_level,
                reason="consensus_diverged",
            )

        selected_output = consensus.selected_output or ""

        # Stage 2 — Constitutional AI critique-revision (optional).
        if self._constitutional is not None and selected_output:
            try:
                selected_output = await self._constitutional(selected_output)
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning("constitutional reviser raised: %s", exc)

        # Stage 3 — Formal verification (Phase 3).
        formal_result: VerificationResult = self._default_formal()
        if self._formal is not None and pipeline_input.formal_input is not None:
            gate_input = self._formal_input_with_source(
                pipeline_input.formal_input, selected_output
            )
            formal_gate_result = await self._formal.verify(gate_input)
            formal_result = formal_gate_result.result
            if formal_result.verdict == VerificationVerdict.FAILED:
                return self._rejection(
                    consensus=consensus,
                    formal=formal_result,
                    coverage=MCDCCoverageReport(),
                    start=start,
                    dal_level=dal_level,
                    reason="formal_failed",
                )
            if formal_result.verdict == VerificationVerdict.UNKNOWN and dal_level in (
                "DAL_A",
                "DAL_B",
            ):
                # DAL A/B require a definitive proof; UNKNOWN escalates.
                return self._hitl_escalation(
                    consensus,
                    start=start,
                    dal_level=dal_level,
                    reason="formal_unknown_at_dal_ab",
                    formal=formal_result,
                )

        # Stage 4 — Sandbox + structural coverage (Phase 2).
        coverage_report: MCDCCoverageReport = MCDCCoverageReport()
        if self._coverage is not None and pipeline_input.coverage_input is not None:
            coverage_gate_result = await self._coverage.analyze(
                pipeline_input.coverage_input
            )
            coverage_report = coverage_gate_result.report
            if not coverage_report.dal_policy_satisfied and dal_level != "DEFAULT":
                return self._rejection(
                    consensus=consensus,
                    formal=formal_result,
                    coverage=coverage_report,
                    start=start,
                    dal_level=dal_level,
                    reason="coverage_insufficient",
                )

        # All deterministic gates passed; HITL is now the only remaining
        # step before AUTO_EXECUTE. The surrounding pipeline (e.g. the
        # MetaOrchestrator) is responsible for actually creating the
        # approval request — the DVE just signals which path to take.
        verdict = (
            DVEOverallVerdict.HITL_REQUIRED
            if self._policy_requires_hitl(pipeline_input.profile_name)
            else DVEOverallVerdict.ACCEPTED
        )

        return DVEResult(
            consensus=consensus,
            overall_verdict=verdict,
            pipeline_latency_ms=(time.time() - start) * 1000.0,
            dal_level=dal_level,
            audit_record_id=consensus.audit_record_id,
            structural_coverage=coverage_report,
            formal_verification=formal_result,
            rejection_reason=None,
        )

    # ------------------------------------------------------- helpers

    @staticmethod
    def _formal_input_with_source(
        original: FormalGateInput, source: str
    ) -> FormalGateInput:
        """Forward the consensus output as the source code to verify.

        Keeps everything else (rules, axes_in_scope, context) from the
        caller-supplied input so policy decisions remain visible.
        """
        return FormalGateInput(
            source_code=source,
            source_file=original.source_file,
            rules=original.rules,
            axes_in_scope=original.axes_in_scope,
            context=original.context,
            timeout_seconds=original.timeout_seconds,
            metadata=original.metadata,
        )

    @staticmethod
    def _default_formal() -> VerificationResult:
        return VerificationResult(
            verdict=VerificationVerdict.SKIPPED,
            axes_verified=(),
            proof_hash="",
            solver_version="",
            verification_time_ms=0.0,
            smt_formula_hash="",
        )

    @staticmethod
    def _dal_level_for_profile(profile_name: str) -> str:
        try:
            policy = get_coverage_policy(profile_name)
            return policy.dal_level
        except KeyError:
            # Profile name with no coverage policy entry — non-aviation
            # workload. DEFAULT preserves pre-Phase 4 behaviour.
            return "DEFAULT"

    @staticmethod
    def _policy_requires_hitl(profile_name: str) -> bool:
        # HITL is mandatory for DAL A/B per ADR-085 §"DO-330 Certification
        # Argument" premise (f). DEFAULT and DAL D run autonomously.
        try:
            policy = get_coverage_policy(profile_name)
        except KeyError:
            return False
        return policy.dal_level in ("DAL_A", "DAL_B")

    def _hitl_escalation(
        self,
        consensus: ConsensusResult,
        *,
        start: float,
        dal_level: str,
        reason: str,
        formal: VerificationResult | None = None,
    ) -> DVEResult:
        return DVEResult(
            consensus=consensus,
            overall_verdict=DVEOverallVerdict.HITL_REQUIRED,
            pipeline_latency_ms=(time.time() - start) * 1000.0,
            dal_level=dal_level,
            audit_record_id=consensus.audit_record_id,
            formal_verification=formal or self._default_formal(),
            rejection_reason=reason,
        )

    def _rejection(
        self,
        *,
        consensus: ConsensusResult,
        formal: VerificationResult,
        coverage: MCDCCoverageReport,
        start: float,
        dal_level: str,
        reason: str,
    ) -> DVEResult:
        return DVEResult(
            consensus=consensus,
            overall_verdict=DVEOverallVerdict.REJECTED,
            pipeline_latency_ms=(time.time() - start) * 1000.0,
            dal_level=dal_level,
            audit_record_id=consensus.audit_record_id,
            structural_coverage=coverage,
            formal_verification=formal,
            rejection_reason=reason,
        )
