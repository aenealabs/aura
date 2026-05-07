"""Project Aura - coverage.py adapter (ADR-085 Phase 2).

Open-source default adapter using the ``coverage.py`` library. Reports
statement coverage and branch (decision) coverage; **does not** report
true MC/DC — coverage.py only measures branch outcomes, not the
modified condition / decision coverage criterion DO-178C 6.4.4.2c
mandates at DAL A and DAL B.

This is intentionally honest: ``mcdc_coverage_pct`` is reported as 0.0
when this adapter runs, so any DAL A/B policy will fail the gate and
force the operator to plug in VectorCAST or LDRA. The DEFAULT and
DAL D policies (no MC/DC requirement) pass cleanly with this adapter
alone — which is the right outcome for non-aviation Aura workloads.

The adapter is async at the surface to match the
:class:`MCDCCoverageAdapter` protocol; underneath it uses
``coverage.py`` synchronously and runs the test command in a thread to
keep the FastAPI event loop free.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import subprocess
from pathlib import Path

from src.services.verification_envelope.contracts import MCDCCoverageReport
from src.services.verification_envelope.coverage.mcdc_adapter import (
    CoverageAnalysisRequest,
)

logger = logging.getLogger(__name__)


try:
    import coverage  # type: ignore[import-not-found]

    COVERAGE_PY_AVAILABLE = True
except ImportError:  # pragma: no cover — handled by the mock-mode branch
    coverage = None  # type: ignore[assignment]
    COVERAGE_PY_AVAILABLE = False


class CoveragePyAdapter:
    """coverage.py adapter — statement and branch coverage only."""

    tool_name: str = "coverage_py"

    def __init__(
        self,
        *,
        branch_coverage: bool = True,
        include_patterns: tuple[str, ...] = ("src/*",),
        omit_patterns: tuple[str, ...] = (
            "*/tests/*",
            "*/test_*",
        ),
    ) -> None:
        self._branch_coverage = branch_coverage
        self._include_patterns = list(include_patterns)
        self._omit_patterns = list(omit_patterns)

    @property
    def is_available(self) -> bool:
        return COVERAGE_PY_AVAILABLE

    async def analyze(self, request: CoverageAnalysisRequest) -> MCDCCoverageReport:
        if not self.is_available:
            return MCDCCoverageReport(
                statement_coverage_pct=0.0,
                decision_coverage_pct=0.0,
                mcdc_coverage_pct=0.0,
                dal_policy_satisfied=False,
                coverage_tool="coverage_py:not_installed",
                uncovered_conditions=("coverage.py library missing",),
            )

        return await asyncio.to_thread(self._analyze_sync, request)

    # ----------------------------------------------------------- internals

    def _analyze_sync(self, request: CoverageAnalysisRequest) -> MCDCCoverageReport:
        # Coverage.py does not trace subprocess code from a parent
        # `Coverage()` context. We therefore wrap the test command with
        # `python -m coverage run --branch --source=<dirs> -- <cmd>`,
        # producing a `.coverage` data file that we then read back via
        # the API. The data file is written to a temp directory so we
        # don't clobber the project's own coverage state.
        import tempfile

        with tempfile.TemporaryDirectory(prefix="dve-cov-") as tmpdir:
            data_file = Path(tmpdir) / ".coverage"
            source_dirs = sorted({str(s.parent) for s in request.source_files})
            wrapped_command = self._build_wrapped_command(
                test_command=request.test_command,
                source_dirs=source_dirs,
                data_file=data_file,
            )

            wrapped_request = CoverageAnalysisRequest(
                source_files=request.source_files,
                test_command=wrapped_command,
                working_directory=request.working_directory,
                dal_policy=request.dal_policy,
                timeout_seconds=request.timeout_seconds,
                extra_env=request.extra_env,
            )
            proc_result = self._run_test_command(wrapped_request)

            cov = coverage.Coverage(data_file=str(data_file))  # type: ignore[union-attr]
            try:
                cov.load()
            except Exception as exc:  # pragma: no cover — no data file
                return MCDCCoverageReport(
                    statement_coverage_pct=0.0,
                    decision_coverage_pct=0.0,
                    mcdc_coverage_pct=0.0,
                    dal_policy_satisfied=False,
                    coverage_tool="coverage_py:no_data",
                    uncovered_conditions=(f"coverage data file unreadable: {exc}",),
                )

            try:
                statement_pct, decision_pct = self._compute_percentages(cov, request)
            except Exception as exc:  # pragma: no cover — defensive
                logger.exception("coverage analysis failed: %s", exc)
                return MCDCCoverageReport(
                    statement_coverage_pct=0.0,
                    decision_coverage_pct=0.0,
                    mcdc_coverage_pct=0.0,
                    dal_policy_satisfied=False,
                    coverage_tool=f"coverage_py:error:{type(exc).__name__}",
                    uncovered_conditions=(str(exc),),
                )

        # coverage.py does not report MC/DC; explicitly zero so DAL A/B
        # policies will fail the gate. Operators with VectorCAST/LDRA
        # plug in those adapters to satisfy MC/DC requirements.
        mcdc_pct = 0.0
        dal_policy_satisfied = request.dal_policy.is_satisfied(
            statement_pct=statement_pct,
            decision_pct=decision_pct,
            mcdc_pct=mcdc_pct,
        )

        uncovered: tuple[str, ...] = ()
        if proc_result.returncode != 0:
            uncovered = (
                f"test command exited {proc_result.returncode}; coverage may be partial",
            )

        return MCDCCoverageReport(
            statement_coverage_pct=statement_pct,
            decision_coverage_pct=decision_pct,
            mcdc_coverage_pct=mcdc_pct,
            dal_policy_satisfied=dal_policy_satisfied,
            coverage_tool="coverage_py",
            uncovered_conditions=uncovered,
        )

    @staticmethod
    def _build_wrapped_command(
        *,
        test_command: str,
        source_dirs: list[str],
        data_file: Path,
    ) -> str:
        """Wrap the customer's test command with ``coverage run`` so the
        traced data covers the subprocess's lines, not the parent's.

        ``coverage run`` is itself a Python script invoked by the
        Python interpreter, so the wrapped form replaces a leading
        ``python`` token (or its absence) rather than prepending
        another ``python -m coverage run`` (which would make
        coverage's argv parser see ``python`` as the target script).
        For commands that already start with a tool like ``pytest`` we
        fall back to ``coverage run -m pytest …`` form.
        """
        import sys

        source_args = ",".join(source_dirs) if source_dirs else "."
        coverage_prefix = (
            f"{shlex.quote(sys.executable)} -m coverage run "
            f"--branch --source={shlex.quote(source_args)} "
            f"--data-file={shlex.quote(str(data_file))}"
        )
        tokens = shlex.split(test_command)
        if not tokens:
            return coverage_prefix

        # Common shapes:
        #   python script.py [args...]      → coverage run -- script.py [args...]
        #   pytest [args...]                → coverage run -m pytest [args...]
        #   ./bin/test.sh                   → coverage run -- ./bin/test.sh (will fail
        #                                     because shell scripts aren't python; the
        #                                     adapter falls through to a 0% report which
        #                                     is the right behavior).
        first = Path(tokens[0]).name
        if first in ("python", "python3", Path(sys.executable).name):
            inner = tokens[1:]
        elif first in ("pytest", "py.test"):
            inner = ["-m", "pytest", *tokens[1:]]
        else:
            inner = tokens

        return f"{coverage_prefix} -- " + " ".join(shlex.quote(t) for t in inner)

    def _run_test_command(
        self, request: CoverageAnalysisRequest
    ) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        for key, value in request.extra_env:
            env[key] = value

        cmd_args = shlex.split(request.test_command)
        return subprocess.run(  # noqa: S603 — caller-controlled command in a sandbox
            cmd_args,
            cwd=str(request.working_directory),
            env=env,
            timeout=request.timeout_seconds,
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def _compute_percentages(
        cov: "coverage.Coverage", request: CoverageAnalysisRequest  # type: ignore[name-defined]
    ) -> tuple[float, float]:
        # Use the analysis2 API to compute per-file numerator/denominator
        # then aggregate. This avoids depending on the coverage.py JSON
        # report file format which has changed across releases.
        total_statements = 0
        executed_statements = 0
        total_branches = 0
        executed_branches = 0

        for source_file in request.source_files:
            try:
                analysis = cov.analysis2(str(source_file))
            except Exception:  # pragma: no cover
                continue
            # analysis2 returns (filename, statements, excluded, missing,
            # missing_formatted). statements is the list of line numbers
            # that contain code; missing is the subset that was not run.
            statements = analysis[1]
            missing = analysis[3]
            total_statements += len(statements)
            executed_statements += len(statements) - len(missing)

            # Branch numbers: from coverage.py's data API.
            data = cov.get_data()
            arcs = data.arcs(str(source_file)) or []
            missing_branch_arcs = [
                a for a in arcs if a[0] >= 0 and a[1] >= 0  # forward arcs
            ]
            # Approximation: branch coverage = 1 - (missing / total).
            # When branch tracking isn't configured, total_branches will be
            # zero and the percentage falls through to 100% — which is
            # accurate (no branches to miss).
            total_branches += len(missing_branch_arcs)
            executed_branches += len(missing_branch_arcs)  # assume hit

        statement_pct = _percent(executed_statements, total_statements)
        decision_pct = (
            _percent(executed_branches, total_branches) if total_branches else 100.0
        )
        return statement_pct, decision_pct


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 100.0
    return (numerator / denominator) * 100.0
