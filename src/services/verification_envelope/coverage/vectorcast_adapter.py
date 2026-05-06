"""Project Aura - VectorCAST coverage adapter (ADR-085 Phase 2).

Subprocess shim for Vector Software's VectorCAST. The tool is
customer-procured (USD ~50K-150K/year per ADR-085 cost analysis) so
the platform never bundles it; instead the adapter shells out to the
``vcast`` CLI when present and falls back to a clearly-marked mock
result when it isn't.

Output parsing targets the JSON report the CLI emits with
``--format=json`` (VectorCAST 2024+). For older releases a SARIF
fallback is also supported because some regulated environments lock
their toolchain to a 2023 build that only emits SARIF.

Defensive design choices:

* The adapter never throws — a missing binary, a non-zero exit, or
  unparseable output all produce a report with ``dal_policy_satisfied
  = False`` and a populated ``uncovered_conditions`` field naming the
  reason. The audit trail therefore captures exactly why the gate
  failed without requiring the operator to read CLI logs.
* The subprocess timeout defaults to the request timeout. VectorCAST
  runs are typically minutes-to-hours; the gate's per-request timeout
  is the right cap.
* No shell features (``shell=True`` is forbidden) so the command line
  cannot be subverted by malicious source filenames.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from src.services.verification_envelope.contracts import MCDCCoverageReport
from src.services.verification_envelope.coverage.mcdc_adapter import (
    CoverageAnalysisRequest,
)

logger = logging.getLogger(__name__)


class VectorCASTAdapter:
    """VectorCAST CLI adapter (subprocess + JSON/SARIF parser)."""

    tool_name: str = "vectorcast"
    DEFAULT_BINARY: str = "vcast"

    def __init__(
        self,
        *,
        binary_path: str | None = None,
        report_format: str = "json",
        extra_args: tuple[str, ...] = (),
    ) -> None:
        self._binary = binary_path or os.environ.get(
            "VECTORCAST_BINARY", self.DEFAULT_BINARY
        )
        self._report_format = report_format
        self._extra_args = list(extra_args)

    @property
    def is_available(self) -> bool:
        return shutil.which(self._binary) is not None

    async def analyze(self, request: CoverageAnalysisRequest) -> MCDCCoverageReport:
        if not self.is_available:
            return self._unavailable_report(
                f"vcast binary not found on PATH (looked for {self._binary!r})"
            )
        return await asyncio.to_thread(self._analyze_sync, request)

    # ------------------------------------------------------------ internals

    def _analyze_sync(
        self, request: CoverageAnalysisRequest
    ) -> MCDCCoverageReport:
        sources = " ".join(shlex.quote(str(s)) for s in request.source_files)
        cmd = [
            self._binary,
            "--coverage",
            "statement,branch,mcdc",
            "--format",
            self._report_format,
            "--test-command",
            request.test_command,
            "--sources",
            *[str(s) for s in request.source_files],
            *self._extra_args,
        ]

        env = dict(os.environ)
        for key, value in request.extra_env:
            env[key] = value

        try:
            proc = subprocess.run(  # noqa: S603 — controlled binary, no shell
                cmd,
                cwd=str(request.working_directory),
                env=env,
                timeout=request.timeout_seconds,
                capture_output=True,
                text=True,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return self._unavailable_report(
                f"vcast timed out after {exc.timeout}s on sources [{sources}]"
            )
        except FileNotFoundError as exc:
            return self._unavailable_report(f"vcast invocation failed: {exc}")

        if proc.returncode != 0:
            return MCDCCoverageReport(
                statement_coverage_pct=0.0,
                decision_coverage_pct=0.0,
                mcdc_coverage_pct=0.0,
                dal_policy_satisfied=False,
                coverage_tool=f"{self.tool_name}:exit_{proc.returncode}",
                uncovered_conditions=(
                    f"vcast exited {proc.returncode}",
                    proc.stderr.strip()[:200] if proc.stderr else "",
                ),
            )

        if self._report_format == "json":
            return self._parse_json(proc.stdout, request)
        return self._parse_sarif(proc.stdout, request)

    def _parse_json(
        self, raw: str, request: CoverageAnalysisRequest
    ) -> MCDCCoverageReport:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return MCDCCoverageReport(
                statement_coverage_pct=0.0,
                decision_coverage_pct=0.0,
                mcdc_coverage_pct=0.0,
                dal_policy_satisfied=False,
                coverage_tool=f"{self.tool_name}:json_parse_error",
                uncovered_conditions=(f"json decode failed: {exc}",),
            )

        coverage = data.get("coverage", {})
        statement = float(coverage.get("statement_pct", 0.0))
        decision = float(coverage.get("decision_pct", 0.0))
        mcdc = float(coverage.get("mcdc_pct", 0.0))
        uncovered = tuple(
            str(u) for u in coverage.get("uncovered_conditions", [])
        )

        satisfied = request.dal_policy.is_satisfied(statement, decision, mcdc)
        return MCDCCoverageReport(
            statement_coverage_pct=statement,
            decision_coverage_pct=decision,
            mcdc_coverage_pct=mcdc,
            dal_policy_satisfied=satisfied,
            coverage_tool=self.tool_name,
            uncovered_conditions=uncovered,
        )

    def _parse_sarif(
        self, raw: str, request: CoverageAnalysisRequest
    ) -> MCDCCoverageReport:
        # SARIF output for VectorCAST embeds coverage metrics under the
        # ``runs[].properties`` extension; the structure is stable across
        # 2023 releases. Older SARIF emitters lack the metrics block, in
        # which case the parse fails closed.
        try:
            data = json.loads(raw)
            runs = data.get("runs", [])
            if not runs:
                raise ValueError("SARIF document has no runs")
            metrics = runs[0].get("properties", {}).get("coverage", {})
            statement = float(metrics.get("statement_pct", 0.0))
            decision = float(metrics.get("decision_pct", 0.0))
            mcdc = float(metrics.get("mcdc_pct", 0.0))
            uncovered = tuple(
                str(u) for u in metrics.get("uncovered_conditions", [])
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            return MCDCCoverageReport(
                statement_coverage_pct=0.0,
                decision_coverage_pct=0.0,
                mcdc_coverage_pct=0.0,
                dal_policy_satisfied=False,
                coverage_tool=f"{self.tool_name}:sarif_parse_error",
                uncovered_conditions=(f"sarif parse failed: {exc}",),
            )

        satisfied = request.dal_policy.is_satisfied(statement, decision, mcdc)
        return MCDCCoverageReport(
            statement_coverage_pct=statement,
            decision_coverage_pct=decision,
            mcdc_coverage_pct=mcdc,
            dal_policy_satisfied=satisfied,
            coverage_tool=f"{self.tool_name}:sarif",
            uncovered_conditions=uncovered,
        )

    def _unavailable_report(self, reason: str) -> MCDCCoverageReport:
        logger.warning("VectorCAST adapter unavailable: %s", reason)
        return MCDCCoverageReport(
            statement_coverage_pct=0.0,
            decision_coverage_pct=0.0,
            mcdc_coverage_pct=0.0,
            dal_policy_satisfied=False,
            coverage_tool=f"{self.tool_name}:unavailable",
            uncovered_conditions=(reason,),
        )
