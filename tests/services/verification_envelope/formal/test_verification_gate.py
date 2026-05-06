"""End-to-end tests for VerificationGateService."""

from __future__ import annotations

import importlib.util

import pytest

from src.services.constraint_geometry.contracts import ConstraintAxis
from src.services.verification_envelope.contracts import (
    VerificationResult,
    VerificationVerdict,
)
from src.services.verification_envelope.formal import (
    FormalGateInput,
    FormalVerificationAdapter,
    FormalVerificationRequest,
    InMemoryArchiveSink,
    VerificationAuditor,
    VerificationGateService,
    Z3SMTAdapter,
)


Z3_INSTALLED = importlib.util.find_spec("z3") is not None


class _FakeAdapter:
    """Fake adapter returning canned results, useful for gate-only tests."""

    def __init__(
        self,
        *,
        tool_name: str = "fake",
        is_available: bool = True,
        result: VerificationResult | None = None,
    ) -> None:
        self.tool_name = tool_name
        self._is_available = is_available
        self._result = result or VerificationResult(
            verdict=VerificationVerdict.PROVED,
            axes_verified=(ConstraintAxis.SYNTACTIC_VALIDITY,),
            proof_hash="fake-proof",
            solver_version="fake-1.0",
            verification_time_ms=1.0,
            smt_formula_hash="fake-hash",
        )
        self.calls: list[FormalVerificationRequest] = []

    @property
    def is_available(self) -> bool:
        return self._is_available

    @property
    def supported_axes(self) -> tuple[ConstraintAxis, ...]:
        return (
            ConstraintAxis.SYNTACTIC_VALIDITY,
            ConstraintAxis.SEMANTIC_CORRECTNESS,
            ConstraintAxis.SECURITY_POLICY,
            ConstraintAxis.OPERATIONAL_BOUNDS,
        )

    async def verify(
        self, request: FormalVerificationRequest
    ) -> VerificationResult:
        self.calls.append(request)
        # Stamp the formula hash from the request so the gate can chain
        # the result through the auditor without surprise.
        return VerificationResult(
            verdict=self._result.verdict,
            axes_verified=self._result.axes_verified,
            proof_hash=self._result.proof_hash,
            solver_version=self._result.solver_version,
            verification_time_ms=self._result.verification_time_ms,
            smt_formula_hash=self._result.smt_formula_hash,
            counterexample=self._result.counterexample,
        )


@pytest.mark.asyncio
async def test_gate_returns_unknown_when_no_adapter_available() -> None:
    """Empty preferred chain → no auto-pass; verdict is UNKNOWN."""
    svc = VerificationGateService(preferred_adapters=())
    result = await svc.verify(
        FormalGateInput(source_code="def f(x: int) -> int: return x\n")
    )
    assert result.adapter_used == "none"
    assert result.result.verdict == VerificationVerdict.UNKNOWN
    assert result.audit_record is None


@pytest.mark.asyncio
async def test_gate_with_fake_proved_passes() -> None:
    fake = _FakeAdapter()
    svc = VerificationGateService(adapter=fake)
    result = await svc.verify(
        FormalGateInput(source_code="def f(x: int) -> int: return x\n")
    )
    assert result.adapter_used == "fake"
    assert result.result.verdict == VerificationVerdict.PROVED
    assert result.audit_record is not None
    assert ConstraintAxis.SYNTACTIC_VALIDITY in result.result.axes_verified


@pytest.mark.asyncio
async def test_gate_demotes_proved_to_failed_when_translator_flags_axis() -> None:
    """Translator-detected C3 violation overrides the SAT verdict."""
    fake = _FakeAdapter(
        result=VerificationResult(
            verdict=VerificationVerdict.PROVED,
            axes_verified=(ConstraintAxis.SECURITY_POLICY,),
            proof_hash="fake",
            solver_version="fake",
            verification_time_ms=1.0,
            smt_formula_hash="fake",
        )
    )
    svc = VerificationGateService(adapter=fake)
    # Source contains eval() which the translator flags as C3 fail.
    eval_source = "def f(x: int) -> str:\n    return eval(x)\n"
    result = await svc.verify(FormalGateInput(source_code=eval_source))
    assert result.result.verdict == VerificationVerdict.FAILED
    # Counterexample explains the demotion.
    assert "C3" in (result.result.counterexample or "")


@pytest.mark.asyncio
async def test_gate_records_audit_for_every_run() -> None:
    sink = InMemoryArchiveSink()
    fake = _FakeAdapter()
    svc = VerificationGateService(
        adapter=fake, auditor=VerificationAuditor(sink=sink)
    )
    await svc.verify(
        FormalGateInput(source_code="def a(x: int) -> int: return x\n")
    )
    await svc.verify(
        FormalGateInput(source_code="def b(x: int) -> int: return x\n")
    )
    assert sink.count == 2


@pytest.mark.asyncio
async def test_preferred_chain_picks_first_available() -> None:
    unavailable = _FakeAdapter(tool_name="unavailable", is_available=False)
    available = _FakeAdapter(tool_name="picked", is_available=True)
    svc = VerificationGateService(preferred_adapters=(unavailable, available))
    result = await svc.verify(
        FormalGateInput(source_code="def f(x: int) -> int: return x\n")
    )
    assert result.adapter_used == "picked"
    assert unavailable.calls == []


@pytest.mark.asyncio
async def test_explicit_adapter_overrides_preferred_chain() -> None:
    explicit = _FakeAdapter(tool_name="explicit")
    chain_choice = _FakeAdapter(tool_name="chain")
    svc = VerificationGateService(
        adapter=explicit, preferred_adapters=(chain_choice,)
    )
    result = await svc.verify(
        FormalGateInput(source_code="def f(x: int) -> int: return x\n")
    )
    assert result.adapter_used == "explicit"
    assert chain_choice.calls == []


@pytest.mark.asyncio
async def test_default_chain_includes_z3() -> None:
    svc = VerificationGateService()
    names = [type(a).__name__ for a in svc._preferred_adapters]
    assert "Z3SMTAdapter" in names


@pytest.mark.asyncio
async def test_gate_attaches_translator_notes_for_diagnostic_visibility() -> None:
    """When the translator flags violations, the gate result surfaces
    those notes so a reviewer can see what triggered a FAILED verdict.
    """
    fake = _FakeAdapter()
    svc = VerificationGateService(adapter=fake)
    result = await svc.verify(
        FormalGateInput(source_code="def f(x):\n    return eval(x)\n")
    )
    assert result.notes  # translator emitted at least one note
    assert any("C3" in n or "eval" in n.lower() for n in result.notes)


@pytest.mark.skipif(not Z3_INSTALLED, reason="requires z3-solver")
@pytest.mark.asyncio
async def test_default_gate_with_real_z3_proves_clean_source() -> None:
    svc = VerificationGateService()
    result = await svc.verify(
        FormalGateInput(source_code="def f(x: int) -> int: return x + 1\n")
    )
    assert result.adapter_used == "z3_smt"
    assert result.result.verdict == VerificationVerdict.PROVED
