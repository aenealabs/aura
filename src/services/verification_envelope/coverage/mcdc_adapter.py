"""Project Aura - MC/DC coverage adapter protocol (ADR-085 Phase 2).

Defines the contract every coverage adapter must implement so the
:class:`CoverageGateService` can stay decoupled from any specific tool.

The adapter pattern is the integration point for customer-procured
DO-178C tooling: VectorCAST and LDRA are the two enterprise tools the
ADR explicitly names, plus :class:`CoveragePyAdapter` (the open-source
default that ships with the platform). Other adapters (Cantata, Tessy,
RapidCover) can be added by implementing :class:`MCDCCoverageAdapter`
without touching the gate orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from src.services.verification_envelope.contracts import MCDCCoverageReport
from src.services.verification_envelope.policies import DALCoveragePolicy


@dataclass(frozen=True)
class CoverageAnalysisRequest:
    """Inputs to a coverage adapter analyse() call.

    Bundled into one dataclass so adapter interfaces stay stable as new
    fields are added (e.g. branch hint files, test selector specs).
    """

    source_files: tuple[Path, ...]
    test_command: str
    working_directory: Path
    dal_policy: DALCoveragePolicy
    timeout_seconds: float = 600.0
    extra_env: tuple[tuple[str, str], ...] = ()


@runtime_checkable
class MCDCCoverageAdapter(Protocol):
    """Protocol every MC/DC coverage tool must satisfy.

    Implementers should be safe to call in mock mode when the backing
    tool is unavailable (no license, binary not on PATH, no source to
    analyse) — they should return an :class:`MCDCCoverageReport` with
    ``coverage_tool`` set to a clearly-mocked value rather than raising.
    The gate service handles the policy decision; adapters only report.
    """

    @property
    def tool_name(self) -> str:
        """Stable identifier (used in audit records and policy docs)."""

    @property
    def is_available(self) -> bool:
        """True when the backing tool is installed and usable."""

    async def analyze(self, request: CoverageAnalysisRequest) -> MCDCCoverageReport:
        """Run the analysis and return a structural-coverage report."""
