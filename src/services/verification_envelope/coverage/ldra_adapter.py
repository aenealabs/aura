"""Project Aura - LDRA coverage adapter (ADR-085 Phase 2).

Subprocess shim for LDRA Testbed. Mirrors :class:`VectorCASTAdapter`'s
defensive design — never throws, marks the report tool field clearly
when the binary is missing or output can't be parsed, falls back to
``dal_policy_satisfied=False`` so a misconfigured environment doesn't
silently pass DAL A/B reviews.

LDRA Testbed emits XML reports by default; this adapter parses the
``coverage_summary.xml`` schema produced by the ``tbrun`` driver. JSON
output is optional in 2024+ releases; we accept either via the
``report_format`` constructor arg.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET

from src.services.verification_envelope.contracts import MCDCCoverageReport
from src.services.verification_envelope.coverage.mcdc_adapter import (
    CoverageAnalysisRequest,
)

logger = logging.getLogger(__name__)


class LDRAAdapter:
    """LDRA Testbed CLI adapter (subprocess + XML/JSON parser)."""

    tool_name: str = "ldra"
    DEFAULT_BINARY: str = "tbrun"

    def __init__(
        self,
        *,
        binary_path: str | None = None,
        report_format: str = "xml",
        extra_args: tuple[str, ...] = (),
    ) -> None:
        self._binary = binary_path or os.environ.get("LDRA_BINARY", self.DEFAULT_BINARY)
        self._report_format = report_format
        self._extra_args = list(extra_args)

    @property
    def is_available(self) -> bool:
        return shutil.which(self._binary) is not None

    async def analyze(self, request: CoverageAnalysisRequest) -> MCDCCoverageReport:
        if not self.is_available:
            return self._unavailable_report(
                f"tbrun binary not found on PATH (looked for {self._binary!r})"
            )
        return await asyncio.to_thread(self._analyze_sync, request)

    # ------------------------------------------------------------ internals

    def _analyze_sync(self, request: CoverageAnalysisRequest) -> MCDCCoverageReport:
        cmd = [
            self._binary,
            "--coverage=statement,branch,mcdc",
            f"--report-format={self._report_format}",
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
            proc = subprocess.run(  # noqa: S603
                cmd,
                cwd=str(request.working_directory),
                env=env,
                timeout=request.timeout_seconds,
                capture_output=True,
                text=True,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return self._unavailable_report(f"tbrun timed out after {exc.timeout}s")
        except FileNotFoundError as exc:
            return self._unavailable_report(f"tbrun invocation failed: {exc}")

        if proc.returncode != 0:
            return MCDCCoverageReport(
                statement_coverage_pct=0.0,
                decision_coverage_pct=0.0,
                mcdc_coverage_pct=0.0,
                dal_policy_satisfied=False,
                coverage_tool=f"{self.tool_name}:exit_{proc.returncode}",
                uncovered_conditions=(
                    f"tbrun exited {proc.returncode}",
                    proc.stderr.strip()[:200] if proc.stderr else "",
                ),
            )

        if self._report_format == "json":
            return self._parse_json(proc.stdout, request)
        return self._parse_xml(proc.stdout, request)

    def _parse_json(
        self, raw: str, request: CoverageAnalysisRequest
    ) -> MCDCCoverageReport:
        try:
            data = json.loads(raw)
            metrics = data.get("coverage", {})
            statement = float(metrics.get("statement_pct", 0.0))
            decision = float(metrics.get("decision_pct", 0.0))
            mcdc = float(metrics.get("mcdc_pct", 0.0))
            uncovered = tuple(str(u) for u in metrics.get("uncovered_conditions", []))
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            return MCDCCoverageReport(
                statement_coverage_pct=0.0,
                decision_coverage_pct=0.0,
                mcdc_coverage_pct=0.0,
                dal_policy_satisfied=False,
                coverage_tool=f"{self.tool_name}:json_parse_error",
                uncovered_conditions=(f"json parse failed: {exc}",),
            )
        return self._build_report(statement, decision, mcdc, uncovered, request)

    def _parse_xml(
        self, raw: str, request: CoverageAnalysisRequest
    ) -> MCDCCoverageReport:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            return MCDCCoverageReport(
                statement_coverage_pct=0.0,
                decision_coverage_pct=0.0,
                mcdc_coverage_pct=0.0,
                dal_policy_satisfied=False,
                coverage_tool=f"{self.tool_name}:xml_parse_error",
                uncovered_conditions=(f"xml parse failed: {exc}",),
            )

        statement = _extract_pct(root, "statement_pct")
        decision = _extract_pct(root, "decision_pct")
        mcdc = _extract_pct(root, "mcdc_pct")
        uncovered = tuple(
            (el.text or "").strip()
            for el in root.iter("uncovered_condition")
            if (el.text or "").strip()
        )
        return self._build_report(statement, decision, mcdc, uncovered, request)

    def _build_report(
        self,
        statement: float,
        decision: float,
        mcdc: float,
        uncovered: tuple[str, ...],
        request: CoverageAnalysisRequest,
    ) -> MCDCCoverageReport:
        satisfied = request.dal_policy.is_satisfied(statement, decision, mcdc)
        return MCDCCoverageReport(
            statement_coverage_pct=statement,
            decision_coverage_pct=decision,
            mcdc_coverage_pct=mcdc,
            dal_policy_satisfied=satisfied,
            coverage_tool=self.tool_name,
            uncovered_conditions=uncovered,
        )

    def _unavailable_report(self, reason: str) -> MCDCCoverageReport:
        logger.warning("LDRA adapter unavailable: %s", reason)
        return MCDCCoverageReport(
            statement_coverage_pct=0.0,
            decision_coverage_pct=0.0,
            mcdc_coverage_pct=0.0,
            dal_policy_satisfied=False,
            coverage_tool=f"{self.tool_name}:unavailable",
            uncovered_conditions=(reason,),
        )


def _extract_pct(root: ET.Element, attr: str) -> float:
    """Read a coverage percentage from either an attribute or child element.

    LDRA's XML schema varies slightly across versions; some emit
    ``<coverage statement_pct="100.0" .../>`` and others emit
    ``<coverage><statement_pct>100.0</statement_pct></coverage>``. Try
    both before giving up.
    """
    if attr in root.attrib:
        try:
            return float(root.attrib[attr])
        except ValueError:
            return 0.0
    cov = root.find("coverage")
    if cov is not None:
        if attr in cov.attrib:
            try:
                return float(cov.attrib[attr])
            except ValueError:
                return 0.0
        child = cov.find(attr)
        if child is not None and child.text:
            try:
                return float(child.text.strip())
            except ValueError:
                return 0.0
    return 0.0
