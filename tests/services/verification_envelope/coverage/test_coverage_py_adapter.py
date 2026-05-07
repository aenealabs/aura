"""Tests for the open-source CoveragePyAdapter."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.services.verification_envelope.coverage import (
    CoverageAnalysisRequest,
    CoveragePyAdapter,
)
from src.services.verification_envelope.policies import (
    DAL_A_PROFILE_NAME,
    DEFAULT_PROFILE_NAME,
    get_coverage_policy,
)


@pytest.fixture
def tiny_project(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal source + test pair under ``tmp_path``.

    Yields (working_directory, source_file). The test command is
    ``python test_target.py`` which exits 0 when the assertion holds.
    """
    src = tmp_path / "target.py"
    src.write_text(textwrap.dedent("""
            def add(a, b):
                if a < 0:
                    return -1
                return a + b
            """).strip() + "\n")

    runner = tmp_path / "test_target.py"
    runner.write_text(textwrap.dedent("""
            from target import add
            assert add(1, 2) == 3
            assert add(-5, 0) == -1
            """).strip() + "\n")

    return tmp_path, src


def _request(
    cwd: Path, source: Path, profile_name: str = DEFAULT_PROFILE_NAME
) -> CoverageAnalysisRequest:
    return CoverageAnalysisRequest(
        source_files=(source,),
        test_command="python test_target.py",
        working_directory=cwd,
        dal_policy=get_coverage_policy(profile_name),
        timeout_seconds=30.0,
    )


@pytest.mark.asyncio
async def test_coverage_py_runs_against_real_python(
    tiny_project: tuple[Path, Path],
) -> None:
    cwd, src = tiny_project
    adapter = CoveragePyAdapter()
    report = await adapter.analyze(_request(cwd, src))
    assert report.coverage_tool == "coverage_py"
    # Both branches in `add` are exercised by the tests above; statement
    # coverage should be 100%.
    assert report.statement_coverage_pct >= 99.0
    # MC/DC isn't computed by coverage.py; gate stays explicitly 0.
    assert report.mcdc_coverage_pct == 0.0


@pytest.mark.asyncio
async def test_default_policy_satisfied_when_coverage_high(
    tiny_project: tuple[Path, Path],
) -> None:
    cwd, src = tiny_project
    adapter = CoveragePyAdapter()
    report = await adapter.analyze(_request(cwd, src, DEFAULT_PROFILE_NAME))
    # DEFAULT requires 70% statement; we should beat that easily.
    assert report.dal_policy_satisfied is True


@pytest.mark.asyncio
async def test_dal_a_policy_fails_with_coverage_py_alone(
    tiny_project: tuple[Path, Path],
) -> None:
    """coverage.py reports MC/DC=0; DAL A requires 100% MC/DC; gate fails."""
    cwd, src = tiny_project
    adapter = CoveragePyAdapter()
    report = await adapter.analyze(_request(cwd, src, DAL_A_PROFILE_NAME))
    assert report.dal_policy_satisfied is False


@pytest.mark.asyncio
async def test_test_failure_recorded_in_uncovered_conditions(
    tmp_path: Path,
) -> None:
    src = tmp_path / "target.py"
    src.write_text("def f(x):\n    return x * 2\n")
    runner = tmp_path / "test_target.py"
    # Intentionally failing assertion → non-zero exit code.
    runner.write_text("from target import f\nassert f(2) == 999\n")

    request = CoverageAnalysisRequest(
        source_files=(src,),
        test_command="python test_target.py",
        working_directory=tmp_path,
        dal_policy=get_coverage_policy(DEFAULT_PROFILE_NAME),
        timeout_seconds=10.0,
    )
    report = await CoveragePyAdapter().analyze(request)
    assert any("exit" in u for u in report.uncovered_conditions)
