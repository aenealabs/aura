"""End-to-end tests for the DVE pipeline orchestrator (ADR-085 Phase 5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.verification_envelope.config import DVEConfig
from src.services.verification_envelope.contracts import (
    DVEOverallVerdict,
    MCDCCoverageReport,
    VerificationResult,
    VerificationVerdict,
)
from src.services.verification_envelope.coverage import (
    CoverageGateInput,
    CoverageGateService,
)
from src.services.verification_envelope.formal import (
    ConstraintTranslator,
    FormalGateInput,
    VerificationGateService,
    Z3SMTAdapter,
)
from src.services.verification_envelope.formal.formal_adapter import (
    FormalVerificationRequest,
)
from src.services.constraint_geometry.contracts import ConstraintAxis
from src.services.verification_envelope.pipeline import (
    DVEPipeline,
    DVEPipelineInput,
)

# ---------------------------------------------------------------- generators


class _ScriptedGenerator:
    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self._idx = 0

    async def __call__(self, prompt: str) -> str:
        out = self._outputs[self._idx % len(self._outputs)]
        self._idx += 1
        return out


# --------------------------------------------------------------- fake gates


class _FakeFormalAdapter:
    """Returns a canned VerificationResult; useful for routing tests."""

    tool_name: str = "fake-formal"

    def __init__(
        self,
        *,
        verdict: VerificationVerdict = VerificationVerdict.PROVED,
        is_available: bool = True,
    ) -> None:
        self._verdict = verdict
        self._is_available = is_available

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

    async def verify(self, request: FormalVerificationRequest) -> VerificationResult:
        return VerificationResult(
            verdict=self._verdict,
            axes_verified=request.axes_in_scope,
            proof_hash="fake",
            solver_version="fake",
            verification_time_ms=1.0,
            smt_formula_hash="fake",
        )


class _FakeCoverageAdapter:
    """Returns a canned MCDCCoverageReport for gate routing tests."""

    tool_name: str = "fake-coverage"

    def __init__(
        self, *, report: MCDCCoverageReport, is_available: bool = True
    ) -> None:
        self._report = report
        self._is_available = is_available

    @property
    def is_available(self) -> bool:
        return self._is_available

    async def analyze(self, request) -> MCDCCoverageReport:  # type: ignore[no-untyped-def]
        return self._report


# ----------------------------------------------------------------- fixtures


def _identical_outputs() -> list[str]:
    return ["def f(x: int) -> int:\n    return x + 1\n"] * 3


def _formal_input() -> FormalGateInput:
    return FormalGateInput(
        source_code="",
        source_file=Path("/tmp/x.py"),
        rules=(),
        axes_in_scope=(ConstraintAxis.SYNTACTIC_VALIDITY,),
    )


def _coverage_input(tmp_path: Path) -> CoverageGateInput:
    src = tmp_path / "target.py"
    src.write_text("def f(x: int) -> int:\n    return x + 1\n")
    return CoverageGateInput(
        source_files=(src,),
        test_command="echo run",
        working_directory=tmp_path,
        profile_name="default",
    )


# ------------------------------------------------------------------- tests


@pytest.mark.asyncio
async def test_consensus_diverged_short_circuits_to_hitl() -> None:
    cfg = DVEConfig.for_testing()
    diverging = [
        "def f(): return 1\n",
        "def f(): return 2\n",
        "def f(): return 3\n",
    ]
    pipeline = DVEPipeline.from_generator(
        config=cfg, generator=_ScriptedGenerator(diverging)
    )
    result = await pipeline.run(DVEPipelineInput(prompt="diverge"))
    assert result.overall_verdict == DVEOverallVerdict.HITL_REQUIRED
    assert result.rejection_reason == "consensus_diverged"
    assert result.consensus.outcome.value == "diverged"


@pytest.mark.asyncio
async def test_default_profile_returns_accepted_when_all_gates_pass(
    tmp_path: Path,
) -> None:
    cfg = DVEConfig.for_testing()
    formal = VerificationGateService(adapter=_FakeFormalAdapter())
    coverage = CoverageGateService(
        adapter=_FakeCoverageAdapter(
            report=MCDCCoverageReport(
                statement_coverage_pct=100.0,
                decision_coverage_pct=100.0,
                mcdc_coverage_pct=0.0,
                dal_policy_satisfied=True,
                coverage_tool="fake",
            )
        )
    )
    pipeline = DVEPipeline.from_generator(
        config=cfg,
        generator=_ScriptedGenerator(_identical_outputs()),
        coverage_gate=coverage,
        formal_gate=formal,
    )
    result = await pipeline.run(
        DVEPipelineInput(
            prompt="clean",
            profile_name="default",
            coverage_input=_coverage_input(tmp_path),
            formal_input=_formal_input(),
        )
    )
    assert result.overall_verdict == DVEOverallVerdict.ACCEPTED
    assert result.dal_level == "DEFAULT"
    assert result.rejection_reason is None
    assert result.formal_verification.verdict == VerificationVerdict.PROVED


@pytest.mark.asyncio
async def test_dal_a_profile_routes_through_hitl_even_after_pass(
    tmp_path: Path,
) -> None:
    """DAL A/B always requires HITL after the deterministic gates pass."""
    cfg = DVEConfig.for_testing()
    formal = VerificationGateService(adapter=_FakeFormalAdapter())
    coverage = CoverageGateService(
        adapter=_FakeCoverageAdapter(
            report=MCDCCoverageReport(
                statement_coverage_pct=100.0,
                decision_coverage_pct=100.0,
                mcdc_coverage_pct=100.0,
                dal_policy_satisfied=True,
                coverage_tool="fake",
            )
        )
    )
    pipeline = DVEPipeline.from_generator(
        config=cfg,
        generator=_ScriptedGenerator(_identical_outputs()),
        coverage_gate=coverage,
        formal_gate=formal,
    )
    result = await pipeline.run(
        DVEPipelineInput(
            prompt="dal-a",
            profile_name="do-178c-dal-a",
            coverage_input=_coverage_input(tmp_path),
            formal_input=_formal_input(),
        )
    )
    assert result.overall_verdict == DVEOverallVerdict.HITL_REQUIRED
    assert result.dal_level == "DAL_A"
    # Even though HITL is required, the formal + coverage gates passed.
    assert result.formal_verification.verdict == VerificationVerdict.PROVED


@pytest.mark.asyncio
async def test_formal_failed_rejects_pipeline(tmp_path: Path) -> None:
    cfg = DVEConfig.for_testing()
    formal = VerificationGateService(
        adapter=_FakeFormalAdapter(verdict=VerificationVerdict.FAILED)
    )
    pipeline = DVEPipeline.from_generator(
        config=cfg,
        generator=_ScriptedGenerator(_identical_outputs()),
        formal_gate=formal,
    )
    result = await pipeline.run(
        DVEPipelineInput(
            prompt="formal-fail",
            profile_name="default",
            formal_input=_formal_input(),
        )
    )
    assert result.overall_verdict == DVEOverallVerdict.REJECTED
    assert result.rejection_reason == "formal_failed"


@pytest.mark.asyncio
async def test_formal_unknown_at_dal_a_escalates_to_hitl() -> None:
    cfg = DVEConfig.for_testing()
    formal = VerificationGateService(
        adapter=_FakeFormalAdapter(verdict=VerificationVerdict.UNKNOWN)
    )
    pipeline = DVEPipeline.from_generator(
        config=cfg,
        generator=_ScriptedGenerator(_identical_outputs()),
        formal_gate=formal,
    )
    result = await pipeline.run(
        DVEPipelineInput(
            prompt="unknown-at-a",
            profile_name="do-178c-dal-a",
            formal_input=_formal_input(),
        )
    )
    assert result.overall_verdict == DVEOverallVerdict.HITL_REQUIRED
    assert result.rejection_reason == "formal_unknown_at_dal_ab"


@pytest.mark.asyncio
async def test_formal_unknown_at_default_proceeds(tmp_path: Path) -> None:
    """Outside DAL A/B, UNKNOWN is treated as a soft pass (covered by HITL/CGE)."""
    cfg = DVEConfig.for_testing()
    formal = VerificationGateService(
        adapter=_FakeFormalAdapter(verdict=VerificationVerdict.UNKNOWN)
    )
    coverage = CoverageGateService(
        adapter=_FakeCoverageAdapter(
            report=MCDCCoverageReport(
                statement_coverage_pct=100.0,
                decision_coverage_pct=100.0,
                mcdc_coverage_pct=0.0,
                dal_policy_satisfied=True,
                coverage_tool="fake",
            )
        )
    )
    pipeline = DVEPipeline.from_generator(
        config=cfg,
        generator=_ScriptedGenerator(_identical_outputs()),
        coverage_gate=coverage,
        formal_gate=formal,
    )
    result = await pipeline.run(
        DVEPipelineInput(
            prompt="unknown-default",
            profile_name="default",
            coverage_input=_coverage_input(tmp_path),
            formal_input=_formal_input(),
        )
    )
    # DEFAULT profile doesn't require HITL; UNKNOWN doesn't gate.
    assert result.overall_verdict == DVEOverallVerdict.ACCEPTED


@pytest.mark.asyncio
async def test_coverage_below_dal_threshold_rejects(tmp_path: Path) -> None:
    cfg = DVEConfig.for_testing()
    formal = VerificationGateService(adapter=_FakeFormalAdapter())
    coverage = CoverageGateService(
        adapter=_FakeCoverageAdapter(
            report=MCDCCoverageReport(
                statement_coverage_pct=99.0,
                decision_coverage_pct=99.0,
                mcdc_coverage_pct=99.0,
                dal_policy_satisfied=False,  # adapter declared insufficient
                coverage_tool="fake",
            )
        )
    )
    pipeline = DVEPipeline.from_generator(
        config=cfg,
        generator=_ScriptedGenerator(_identical_outputs()),
        coverage_gate=coverage,
        formal_gate=formal,
    )
    result = await pipeline.run(
        DVEPipelineInput(
            prompt="coverage-fail",
            profile_name="do-178c-dal-a",
            coverage_input=_coverage_input(tmp_path),
            formal_input=_formal_input(),
        )
    )
    assert result.overall_verdict == DVEOverallVerdict.REJECTED
    assert result.rejection_reason == "coverage_insufficient"


@pytest.mark.asyncio
async def test_constitutional_reviser_called_when_supplied(
    tmp_path: Path,
) -> None:
    cfg = DVEConfig.for_testing()
    seen: list[str] = []

    async def reviser(text: str) -> str:
        seen.append(text)
        return text  # no-op revision

    pipeline = DVEPipeline.from_generator(
        config=cfg,
        generator=_ScriptedGenerator(_identical_outputs()),
        constitutional_reviser=reviser,
    )
    await pipeline.run(DVEPipelineInput(prompt="reviser"))
    assert len(seen) == 1
    assert "def f(x: int) -> int" in seen[0]


@pytest.mark.asyncio
async def test_pipeline_without_optional_gates_runs_consensus_only() -> None:
    """A pipeline with no formal/coverage gates still completes."""
    cfg = DVEConfig.for_testing()
    pipeline = DVEPipeline.from_generator(
        config=cfg, generator=_ScriptedGenerator(_identical_outputs())
    )
    result = await pipeline.run(
        DVEPipelineInput(prompt="consensus-only", profile_name="default")
    )
    assert result.overall_verdict == DVEOverallVerdict.ACCEPTED


@pytest.mark.asyncio
async def test_pipeline_records_audit_record_id_from_consensus() -> None:
    cfg = DVEConfig.for_testing()
    pipeline = DVEPipeline.from_generator(
        config=cfg, generator=_ScriptedGenerator(_identical_outputs())
    )
    result = await pipeline.run(DVEPipelineInput(prompt="audit"))
    assert result.audit_record_id == result.consensus.audit_record_id


@pytest.mark.asyncio
async def test_pipeline_dal_level_for_unknown_profile_is_default() -> None:
    cfg = DVEConfig.for_testing()
    pipeline = DVEPipeline.from_generator(
        config=cfg, generator=_ScriptedGenerator(_identical_outputs())
    )
    result = await pipeline.run(
        DVEPipelineInput(prompt="unknown-profile", profile_name="not-a-profile")
    )
    assert result.dal_level == "DEFAULT"


@pytest.mark.asyncio
async def test_pipeline_uses_consensus_output_for_formal_input(
    tmp_path: Path,
) -> None:
    """The formal gate should see the consensus-selected output, not the
    placeholder source on the FormalGateInput."""
    cfg = DVEConfig.for_testing()
    seen_sources: list[str] = []

    class _RecordingFormal:
        tool_name = "recording"
        is_available = True

        @property
        def supported_axes(self) -> tuple[ConstraintAxis, ...]:
            return (ConstraintAxis.SYNTACTIC_VALIDITY,)

        async def verify(self, request):  # type: ignore[no-untyped-def]
            seen_sources.append(request.source_code)
            return VerificationResult(
                verdict=VerificationVerdict.PROVED,
                axes_verified=(),
                proof_hash="r",
                solver_version="r",
                verification_time_ms=0.0,
                smt_formula_hash="r",
            )

    formal_svc = VerificationGateService(adapter=_RecordingFormal())
    pipeline = DVEPipeline.from_generator(
        config=cfg,
        generator=_ScriptedGenerator(_identical_outputs()),
        formal_gate=formal_svc,
    )
    await pipeline.run(
        DVEPipelineInput(
            prompt="sourcecheck",
            profile_name="default",
            formal_input=_formal_input(),
        )
    )
    assert seen_sources, "formal adapter should have been invoked"
    assert "def f(x: int) -> int:" in seen_sources[0]
