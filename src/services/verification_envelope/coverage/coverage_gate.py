"""Project Aura - Coverage gate orchestrator (ADR-085 Phase 2, Pillar 2).

Sits at stage 6 of the sandbox validation pipeline (per the ADR-085
Enhanced Pipeline Diagram). Receives the agent output and a DAL level,
selects an appropriate :class:`MCDCCoverageAdapter`, runs it, and
returns an :class:`MCDCCoverageReport` whose ``dal_policy_satisfied``
flag determines whether the pipeline proceeds to HITL approval or
rejects the patch.

Adapter selection rules:

1. If an explicit adapter is passed at construction time, use it.
2. Otherwise, walk ``preferred_adapters`` in order and pick the first
   that reports ``is_available=True``.
3. If nothing is available, return a clearly-marked unavailable
   report — failing the gate so DAL A/B workloads cannot silently
   pass without a real coverage tool.

The DEFAULT DAL policy (70% statement coverage, no MC/DC) is satisfied
by the open-source :class:`CoveragePyAdapter`, so the gate is usable
on non-aviation Aura workloads without any customer-procured tooling.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from src.services.verification_envelope.contracts import MCDCCoverageReport
from src.services.verification_envelope.coverage.coverage_py_adapter import (
    CoveragePyAdapter,
)
from src.services.verification_envelope.coverage.ldra_adapter import LDRAAdapter
from src.services.verification_envelope.coverage.mcdc_adapter import (
    CoverageAnalysisRequest,
    MCDCCoverageAdapter,
)
from src.services.verification_envelope.coverage.vectorcast_adapter import (
    VectorCASTAdapter,
)
from src.services.verification_envelope.policies import (
    DEFAULT_PROFILE_NAME,
    DALCoveragePolicy,
    get_coverage_policy,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CoverageGateInput:
    """Inputs to a coverage gate evaluation.

    A separate dataclass keeps the public surface stable as we add
    fields (e.g. patch_id linkage, sandbox_id for trace correlation).
    """

    source_files: tuple[Path, ...]
    test_command: str
    working_directory: Path
    profile_name: str = DEFAULT_PROFILE_NAME
    timeout_seconds: float = 600.0
    extra_env: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CoverageGateResult:
    """Outcome of a gate evaluation, including which adapter ran."""

    report: MCDCCoverageReport
    adapter_used: str
    profile: DALCoveragePolicy
    duration_ms: float


class CoverageGateService:
    """Orchestrates structural-coverage analysis across pluggable adapters."""

    def __init__(
        self,
        *,
        adapter: MCDCCoverageAdapter | None = None,
        preferred_adapters: Sequence[MCDCCoverageAdapter] | None = None,
    ) -> None:
        self._explicit_adapter = adapter
        if preferred_adapters is None:
            # Default preference: try the enterprise tools first (so DAL
            # A/B workloads use them when available), fall back to the
            # open-source adapter for DEFAULT/DAL D / non-aviation runs.
            preferred_adapters = (
                VectorCASTAdapter(),
                LDRAAdapter(),
                CoveragePyAdapter(),
            )
        self._preferred_adapters = list(preferred_adapters)

    async def analyze(self, gate_input: CoverageGateInput) -> CoverageGateResult:
        policy = get_coverage_policy(gate_input.profile_name)
        adapter = self._select_adapter()
        if adapter is None:
            unavailable = MCDCCoverageReport(
                statement_coverage_pct=0.0,
                decision_coverage_pct=0.0,
                mcdc_coverage_pct=0.0,
                dal_policy_satisfied=False,
                coverage_tool="no_adapter_available",
                uncovered_conditions=(
                    "no MCDCCoverageAdapter available in this environment; "
                    "install coverage.py or configure VectorCAST/LDRA",
                ),
            )
            return CoverageGateResult(
                report=unavailable,
                adapter_used="none",
                profile=policy,
                duration_ms=0.0,
            )

        request = CoverageAnalysisRequest(
            source_files=gate_input.source_files,
            test_command=gate_input.test_command,
            working_directory=gate_input.working_directory,
            dal_policy=policy,
            timeout_seconds=gate_input.timeout_seconds,
            extra_env=gate_input.extra_env,
        )

        start = time.time()
        report = await adapter.analyze(request)
        duration_ms = (time.time() - start) * 1000.0

        logger.info(
            "coverage gate adapter=%s profile=%s satisfied=%s "
            "stmt=%.1f%% dec=%.1f%% mcdc=%.1f%% duration_ms=%.0f",
            adapter.tool_name,
            policy.profile_name,
            report.dal_policy_satisfied,
            report.statement_coverage_pct,
            report.decision_coverage_pct,
            report.mcdc_coverage_pct,
            duration_ms,
        )

        return CoverageGateResult(
            report=report,
            adapter_used=adapter.tool_name,
            profile=policy,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------ internals

    def _select_adapter(self) -> MCDCCoverageAdapter | None:
        if self._explicit_adapter is not None:
            return self._explicit_adapter
        for adapter in self._preferred_adapters:
            try:
                if adapter.is_available:
                    return adapter
            except Exception as exc:  # pragma: no cover — adapter availability check failure
                logger.warning(
                    "adapter %s availability check raised: %s",
                    type(adapter).__name__,
                    exc,
                )
        return None
