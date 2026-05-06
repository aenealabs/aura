"""Tests for the Z3 SMT adapter.

z3-solver is treated as optional — most tests exercise the mock path
that fires when the SDK isn't installed. A single live-Z3 test is
gated on import success and skipped otherwise so CI without z3 still
passes.
"""

from __future__ import annotations

import importlib.util

import pytest

from src.services.verification_envelope.contracts import VerificationVerdict
from src.services.verification_envelope.formal import (
    ConstraintTranslator,
    Z3SMTAdapter,
    build_request,
)


Z3_INSTALLED = importlib.util.find_spec("z3") is not None


@pytest.mark.asyncio
async def test_mock_path_returns_skipped_verdict_when_z3_missing() -> None:
    if Z3_INSTALLED:
        pytest.skip("z3-solver is installed; this test exercises the mock path")
    request = build_request(source_code="def f(x: int) -> int: return x\n")
    result = await Z3SMTAdapter().verify(request)
    assert result.verdict == VerificationVerdict.SKIPPED
    assert result.solver_version == "z3:not_installed"
    assert "z3-solver SDK not installed" in (result.counterexample or "")
    # Formula hash is computed even on the mock path so audit trails
    # remain consistent across mock/real runs.
    assert result.smt_formula_hash


@pytest.mark.asyncio
async def test_mock_path_counterexample_explains_install_path() -> None:
    if Z3_INSTALLED:
        pytest.skip("z3-solver is installed; this test exercises the mock path")
    request = build_request(source_code="def f(x: int) -> int: return x\n")
    result = await Z3SMTAdapter().verify(request)
    assert "install z3-solver" in (result.counterexample or "").lower()


@pytest.mark.asyncio
async def test_proof_hash_is_empty_on_mock_path() -> None:
    if Z3_INSTALLED:
        pytest.skip("z3-solver is installed; this test exercises the mock path")
    request = build_request(source_code="def f(x: int) -> int: return x\n")
    result = await Z3SMTAdapter().verify(request)
    # The mock path doesn't compute a proof hash because there's no
    # solver verdict to bind the hash to.
    assert result.proof_hash == ""


@pytest.mark.asyncio
async def test_formula_hash_is_deterministic() -> None:
    """Two runs of the same translator output produce the same formula hash."""
    request_a = build_request(source_code="def f(x: int) -> int: return x\n")
    request_b = build_request(source_code="def f(x: int) -> int: return x\n")
    result_a = await Z3SMTAdapter().verify(request_a)
    result_b = await Z3SMTAdapter().verify(request_b)
    assert result_a.smt_formula_hash == result_b.smt_formula_hash


@pytest.mark.asyncio
async def test_axes_verified_only_listed_when_proved() -> None:
    """SKIPPED / FAILED / UNKNOWN never claim axes are proven."""
    request = build_request(source_code="def f(x: int) -> int: return x\n")
    result = await Z3SMTAdapter().verify(request)
    if result.verdict != VerificationVerdict.PROVED:
        assert result.axes_verified == ()


@pytest.mark.skipif(not Z3_INSTALLED, reason="requires z3-solver")
@pytest.mark.asyncio
async def test_live_z3_proves_clean_source() -> None:
    """End-to-end with a real Z3 solver when the SDK is installed."""
    request = build_request(source_code="def f(x: int) -> int: return x + 1\n")
    result = await Z3SMTAdapter().verify(request)
    # Clean annotated source with no C3 violations and no C4 bounds
    # supplied → the conjunction is satisfiable; verdict is PROVED.
    assert result.verdict == VerificationVerdict.PROVED
    assert result.proof_hash, "proof hash must be set on PROVED verdicts"
    assert result.solver_version.startswith("z3:")
    assert result.solver_version != "z3:not_installed"
