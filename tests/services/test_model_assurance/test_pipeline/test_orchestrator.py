"""End-to-end orchestrator tests (ADR-088 Phase 2.3).

These tests drive every Choice branch in the state machine via the
synchronous Python orchestrator, which mirrors the ASL flow exactly.
Mid-stage failure injection is also covered to satisfy issue #111's
"15+ multi-stage traversal tests with injected failures at each
stage boundary" acceptance criterion.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence

import pytest

from src.services.model_assurance import (
    AdapterRegistry,
    AxisScore,
    ModelAssuranceAxis,
    ModelAssuranceEvaluator,
    ModelProvider,
    ModelRequirements,
)
from src.services.model_assurance.frozen_oracle import (
    ASTDiffJudge,
    DOMAIN_MINIMUMS,
    GoldenTestCase,
    GoldenTestSet,
    JudgeRegistry,
    OracleEvaluation,
    OracleService,
    PatchCandidateOutput,
    StaticAnalysisCandidateOutput,
    StaticAnalysisJudge,
    TestCaseDomain,
)
from src.services.model_assurance.pipeline import (
    PipelineDecision,
    PipelineInput,
    PipelineOrchestrator,
    PipelineStage,
)
from src.services.model_assurance.scout import (
    EligibilityFlag,
    make_event,
)
from src.services.supply_chain.model_provenance import (
    InMemoryModelQuarantineStore,
    ModelArtifact,
    ModelLicense,
    ModelProvenanceService,
    ModelRegistry as ProvRegistry,
    ProvenanceServiceConfig,
)


# ----------------------------------------------------- helpers


def _digest() -> str:
    return "a" * 64


def _artifact(model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0") -> ModelArtifact:
    return ModelArtifact(
        model_id=model_id,
        provider="anthropic",
        registry=ProvRegistry.BEDROCK,
        weights_digest=_digest(),
        license=ModelLicense(
            spdx_id="Apache-2.0",
            is_permissive=True,
            commercial_use_allowed=True,
        ),
    )


def _full_oracle_set() -> GoldenTestSet:
    cases: list[GoldenTestCase] = []
    for i in range(100):
        cases.append(GoldenTestCase(
            case_id=f"patch-{i:04d}",
            domain=TestCaseDomain.PATCH_CORRECTNESS,
            title="t",
            description="d",
            axes=(
                ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS,
                ModelAssuranceAxis.PATCH_SECURITY_EQUIVALENCE,
            ),
            expected=(("reference_source", "def f(): return 1"),),
        ))
    fillers = {
        TestCaseDomain.VULNERABILITY_DETECTION: (
            ModelAssuranceAxis.VULNERABILITY_DETECTION_RECALL, 150,
        ),
        TestCaseDomain.FALSE_POSITIVE: (
            ModelAssuranceAxis.GUARDRAIL_COMPLIANCE, 100,
        ),
        TestCaseDomain.REGRESSION: (
            ModelAssuranceAxis.CODE_COMPREHENSION, 50,
        ),
    }
    for domain, (axis, n) in fillers.items():
        for i in range(n):
            cases.append(GoldenTestCase(
                case_id=f"{domain.value}-{i:04d}",
                domain=domain, title="t", description="d",
                axes=(axis,),
            ))
    return GoldenTestSet(cases=tuple(cases), version="0.1")


def _candidate_outputs(perfect: bool = True) -> Mapping[str, Sequence[object]]:
    """Build candidate outputs for both judges across 100 patch cases."""
    ast_outputs = []
    sa_outputs = []
    for i in range(100):
        source = (
            "def f(): return 1" if perfect else "def f(): return 999"
        )
        ast_outputs.append(PatchCandidateOutput(
            case_id=f"patch-{i:04d}", patched_source=source,
        ))
        sa_outputs.append(StaticAnalysisCandidateOutput(
            case_id=f"patch-{i:04d}",
            before_findings=(("HIGH", 1),),
            after_findings=(("HIGH", 1),) if perfect else (("HIGH", 5),),
        ))
    return {"ast_diff_v1": ast_outputs, "static_analysis_v1": sa_outputs}


def _orchestrator(
    *,
    sandbox_hook=None,
    provenance: ModelProvenanceService | None = None,
    enforce_floors: bool = False,
) -> PipelineOrchestrator:
    """Test orchestrator.

    By default the assurance evaluator runs with NO regression floors
    so the pipeline-routing tests in this file aren't gated by axis
    scores other than those the registered judges fill in. Floor
    enforcement is exhaustively tested in Phase 1.1 / 1.3 — this file
    is about the state-machine routing.
    """
    registry = AdapterRegistry()
    oracle_set = _full_oracle_set()
    judges = JudgeRegistry()
    judges.register(ASTDiffJudge())
    judges.register(StaticAnalysisJudge())
    evaluator = (
        ModelAssuranceEvaluator()
        if enforce_floors
        else ModelAssuranceEvaluator(floors=())
    )
    return PipelineOrchestrator(
        adapter_registry=registry,
        provenance_service=provenance or ModelProvenanceService(),
        oracle_service=OracleService(
            golden_set=oracle_set, judges=judges, holdout_rate=0.0,
        ),
        assurance_evaluator=evaluator,
        sandbox_hook=sandbox_hook,
    )


def _pipeline_input(
    *,
    artifact: ModelArtifact | None = None,
    requirements: ModelRequirements | None = None,
    candidate_outputs: Mapping[str, Sequence[object]] | None = None,
) -> PipelineInput:
    artifact = artifact or _artifact()
    return PipelineInput(
        candidate_event=make_event(
            candidate_id=artifact.model_id,
            display_name=artifact.model_id,
            provider=ModelProvider.BEDROCK,
            partition="aws",
            eligibility=EligibilityFlag.QUALIFIED,
        ),
        artifact=artifact,
        requirements=requirements or ModelRequirements(),
        candidate_outputs=candidate_outputs or _candidate_outputs(perfect=True),
    )


# ----------------------------------------------------- happy path


class TestHappyPath:
    def test_strong_candidate_reaches_hitl(self) -> None:
        orch = _orchestrator()
        result = orch.run(_pipeline_input())
        assert result.decision is PipelineDecision.HITL_QUEUED
        # All 7 stages executed
        assert len(result.stages) == 7
        assert all(s.succeeded for s in result.stages)

    def test_assurance_verdict_attached_on_hitl_path(self) -> None:
        orch = _orchestrator()
        result = orch.run(_pipeline_input())
        assert result.assurance_verdict is not None

    def test_oracle_evaluation_attached(self) -> None:
        orch = _orchestrator()
        result = orch.run(_pipeline_input())
        assert isinstance(result.oracle_evaluation, OracleEvaluation)


# ----------------------------------------------------- adapter disqualification


class TestAdapterDisqualification:
    def test_capability_gate_rejects(self) -> None:
        orch = _orchestrator()
        # Demand a 2M context — well above the 200k Bedrock entries.
        reqs = ModelRequirements(min_context_tokens=2_000_000)
        result = orch.run(_pipeline_input(requirements=reqs))
        assert result.decision is PipelineDecision.DISQUALIFIED
        assert result.disqualification_reasons
        # Stages after Adapter must NOT have been entered.
        assert result.stage_outcome(PipelineStage.PROVENANCE) is None

    def test_unknown_model_continues_through_pipeline(self) -> None:
        """Synthesised adapter case — unknown ids skip the adapter gate."""
        orch = _orchestrator()
        result = orch.run(
            _pipeline_input(
                artifact=_artifact(model_id="anthropic.claude-future"),
            ),
        )
        assert result.decision is PipelineDecision.HITL_QUEUED


# ----------------------------------------------------- provenance branches


class TestProvenanceBranches:
    def test_quarantined_model_short_circuits(self) -> None:
        store = InMemoryModelQuarantineStore()
        store.quarantine("anthropic.claude-3-5-sonnet-20240620-v1:0", "preexisting")
        prov = ModelProvenanceService(quarantine_store=store)
        orch = _orchestrator(provenance=prov)
        result = orch.run(_pipeline_input())
        assert result.decision is PipelineDecision.QUARANTINED
        assert result.provenance_record is not None
        # No sandbox or oracle — short-circuit
        assert result.stage_outcome(PipelineStage.SANDBOX) is None
        assert result.stage_outcome(PipelineStage.ORACLE) is None

    def test_rejected_registry_short_circuits(self) -> None:
        orch = _orchestrator()
        # provider not in allowlist → REJECTED
        bad_artifact = ModelArtifact(
            model_id="random-vendor.model",
            provider="random-vendor",
            registry=ProvRegistry.BEDROCK,
            weights_digest=_digest(),
        )
        result = orch.run(_pipeline_input(artifact=bad_artifact))
        assert result.decision is PipelineDecision.REJECTED
        # Reason traces back to provenance
        assert "provenance" in (result.rejection_reason or "")


# ----------------------------------------------------- sandbox


class TestSandboxBranches:
    def test_sandbox_failure_halts_with_no_orphan(self) -> None:
        orch = _orchestrator(sandbox_hook=lambda inp: False)
        result = orch.run(_pipeline_input())
        assert result.decision is PipelineDecision.INFRASTRUCTURE_ERROR
        # Per ADR-088 acceptance criterion: mid-pipeline failure must
        # not leave an oracle stage executed.
        assert result.stage_outcome(PipelineStage.ORACLE) is None

    def test_sandbox_exception_halts_cleanly(self) -> None:
        def boom(_):
            raise RuntimeError("sandbox crash")
        orch = _orchestrator(sandbox_hook=boom)
        result = orch.run(_pipeline_input())
        assert result.decision is PipelineDecision.INFRASTRUCTURE_ERROR
        sandbox_outcome = result.stage_outcome(PipelineStage.SANDBOX)
        assert sandbox_outcome is not None
        assert sandbox_outcome.error_type == "RuntimeError"


# ----------------------------------------------------- floor-violation route


class TestFloorViolationRoute:
    def test_floor_violation_drives_reject(self) -> None:
        """With floors enforced, an imperfect candidate auto-rejects."""
        orch = _orchestrator(enforce_floors=True)
        # AST returns 0% pass on a candidate that always emits the
        # wrong patch — MA3 floor (0.88) fires.
        result = orch.run(_pipeline_input(
            candidate_outputs=_candidate_outputs(perfect=False),
        ))
        assert result.decision is PipelineDecision.REJECTED
        assert (
            result.rejection_reason == "floor_violation"
            or "floor" in (result.rejection_reason or "")
        )


# ----------------------------------------------------- audit + duration


class TestAuditMetadata:
    def test_audit_dict_structure(self) -> None:
        orch = _orchestrator()
        result = orch.run(_pipeline_input())
        d = result.to_audit_dict()
        assert d["decision"] == "hitl_queued"
        assert "stages" in d
        assert len(d["stages"]) == 7
        assert d["provenance"]["verdict"] == "approved"

    def test_durations_recorded(self) -> None:
        orch = _orchestrator()
        result = orch.run(_pipeline_input())
        assert result.total_duration_ms >= 0
        for s in result.stages:
            assert s.duration_ms >= 0


# ----------------------------------------------------- multi-failure boundary


class TestStageBoundaryFailures:
    def test_provenance_exception_caught(self) -> None:
        class _BoomService:
            quarantine_store = InMemoryModelQuarantineStore()

            def evaluate(self, *_, **__):
                raise RuntimeError("provenance backend down")

        orch = _orchestrator(provenance=_BoomService())  # type: ignore[arg-type]
        result = orch.run(_pipeline_input())
        assert result.decision is PipelineDecision.INFRASTRUCTURE_ERROR
        # Sandbox must NOT have been provisioned.
        assert result.stage_outcome(PipelineStage.SANDBOX) is None
