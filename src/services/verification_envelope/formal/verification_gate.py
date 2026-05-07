"""Project Aura - Formal verification gate orchestrator (ADR-085 Phase 3).

Stage between the Constraint Geometry Engine (ADR-081) and sandbox
validation in the DVE pipeline. Calls the constraint translator,
hands the result to a :class:`FormalVerificationAdapter`, records the
outcome via the auditor, and returns a routing-friendly verdict so
the surrounding pipeline can short-circuit on FAILED while continuing
on PROVED or UNKNOWN (UNKNOWN forwards the decision to HITL — never
auto-accepts).

Adapter selection mirrors :class:`CoverageGateService`: explicit
override → preferred chain → unavailable verdict (no auto-pass).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from src.services.constraint_geometry.contracts import ConstraintAxis, ConstraintRule
from src.services.verification_envelope.contracts import (
    VerificationResult,
    VerificationVerdict,
)
from src.services.verification_envelope.formal.constraint_translator import (
    ConstraintTranslator,
    TranslationContext,
)
from src.services.verification_envelope.formal.formal_adapter import (
    FormalVerificationAdapter,
    FormalVerificationRequest,
)
from src.services.verification_envelope.formal.verification_auditor import (
    AuditRecord,
    VerificationAuditor,
)
from src.services.verification_envelope.formal.z3_smt_adapter import Z3SMTAdapter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FormalGateInput:
    """Inputs to the verification gate."""

    source_code: str
    source_file: Path | None = None
    rules: tuple[ConstraintRule, ...] = ()
    axes_in_scope: tuple[ConstraintAxis, ...] = ()
    context: TranslationContext | None = None
    timeout_seconds: float = 30.0
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FormalGateResult:
    """Outcome of one gate evaluation."""

    result: VerificationResult
    adapter_used: str
    audit_record: AuditRecord | None
    duration_ms: float
    notes: tuple[str, ...]


class VerificationGateService:
    """Drives the constraint translator → adapter → auditor pipeline."""

    def __init__(
        self,
        *,
        adapter: FormalVerificationAdapter | None = None,
        preferred_adapters: Sequence[FormalVerificationAdapter] | None = None,
        translator: ConstraintTranslator | None = None,
        auditor: VerificationAuditor | None = None,
    ) -> None:
        self._explicit_adapter = adapter
        if preferred_adapters is None:
            preferred_adapters = (Z3SMTAdapter(),)
        self._preferred_adapters = list(preferred_adapters)
        self._translator = translator or ConstraintTranslator()
        self._auditor = auditor or VerificationAuditor()

    async def verify(self, gate_input: FormalGateInput) -> FormalGateResult:
        adapter = self._select_adapter()
        start = time.time()

        if adapter is None:
            unavailable_result = VerificationResult(
                verdict=VerificationVerdict.UNKNOWN,
                axes_verified=(),
                proof_hash="",
                solver_version="none",
                verification_time_ms=0.0,
                smt_formula_hash="",
                counterexample="no FormalVerificationAdapter available",
            )
            return FormalGateResult(
                result=unavailable_result,
                adapter_used="none",
                audit_record=None,
                duration_ms=(time.time() - start) * 1000.0,
                notes=("no adapter available",),
            )

        translation = self._translator.translate(
            source_code=gate_input.source_code,
            source_file=gate_input.source_file,
            rules=gate_input.rules,
            axes_in_scope=gate_input.axes_in_scope or None,
            context=gate_input.context,
        )

        request = FormalVerificationRequest(
            source_code=gate_input.source_code,
            source_file=gate_input.source_file,
            rules=gate_input.rules,
            axes_in_scope=translation.axes_in_scope,
            smt_assertions=translation.smt_assertions,
            timeout_seconds=gate_input.timeout_seconds,
            metadata=gate_input.metadata,
        )

        result = await adapter.verify(request)
        # Refine axes_verified using translator-decided per-axis booleans.
        # The adapter discharges the SMT formula; the translator's
        # axis_holds is what actually decides which axes were proven
        # (the SMT pass is necessary but not sufficient — a per-axis
        # false from the translator means the axis is FAILED at source-
        # analysis time even when Z3 returns SAT for the conjunction).
        if result.verdict == VerificationVerdict.PROVED:
            verified = tuple(
                axis for axis, holds in translation.axis_holds.items() if holds
            )
            failed_axes = tuple(
                axis.value
                for axis, holds in translation.axis_holds.items()
                if not holds
            )
            if failed_axes:
                # Demote to FAILED so the gate cannot proceed.
                result = VerificationResult(
                    verdict=VerificationVerdict.FAILED,
                    axes_verified=verified,
                    proof_hash=result.proof_hash,
                    solver_version=result.solver_version,
                    verification_time_ms=result.verification_time_ms,
                    smt_formula_hash=result.smt_formula_hash,
                    counterexample=(
                        "translator marked these axes as failed: "
                        + ", ".join(failed_axes)
                    ),
                )
            else:
                result = VerificationResult(
                    verdict=result.verdict,
                    axes_verified=verified,
                    proof_hash=result.proof_hash,
                    solver_version=result.solver_version,
                    verification_time_ms=result.verification_time_ms,
                    smt_formula_hash=result.smt_formula_hash,
                    counterexample=result.counterexample,
                )

        audit_record = await self._auditor.record(request, result)
        duration_ms = (time.time() - start) * 1000.0

        logger.info(
            "formal gate adapter=%s verdict=%s axes=%s duration_ms=%.0f",
            adapter.tool_name,
            result.verdict.value,
            ",".join(a.value for a in result.axes_verified),
            duration_ms,
        )
        return FormalGateResult(
            result=result,
            adapter_used=adapter.tool_name,
            audit_record=audit_record,
            duration_ms=duration_ms,
            notes=translation.notes,
        )

    def _select_adapter(self) -> FormalVerificationAdapter | None:
        if self._explicit_adapter is not None:
            return self._explicit_adapter
        for adapter in self._preferred_adapters:
            try:
                if adapter.is_available:
                    return adapter
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "adapter %s availability check raised: %s",
                    type(adapter).__name__,
                    exc,
                )
        return None
