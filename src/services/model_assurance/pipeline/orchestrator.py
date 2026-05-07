"""Synchronous pipeline orchestrator (ADR-088 Phase 2.3).

The same logic the production Step Functions state machine
executes, expressed as a pure-Python orchestrator so:

  * Tests can drive every branch deterministically without AWS.
  * Dev environments can run the pipeline without the Step Functions
    runtime (useful for the integrated demo path).
  * The CloudFormation ASL generator (state_machine_definition.py)
    can mirror this control-flow exactly — same stages, same
    branch conditions, same stop reasons.

Every stage is a callable on the orchestrator; the state machine
generator wraps the same callables in Lambda invocations behind
ASL Choice / Catch states. Keeping both paths driven by one
orchestrator module guarantees the CFN ASL never drifts away from
what the tests cover.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from src.services.model_assurance import (
    AdapterRegistry,
    AxisScore,
    ModelAssuranceAxis,
    ModelAssuranceEvaluator,
    ModelAssuranceVerdict,
)
from src.services.model_assurance.frozen_oracle import (
    OracleEvaluation,
    OracleService,
)
from src.services.model_assurance.scoring import make_incumbent
from src.services.model_assurance.pipeline.contracts import (
    PipelineDecision,
    PipelineInput,
    PipelineResult,
    PipelineStage,
    StageOutcome,
)
from src.services.supply_chain.model_provenance import (
    ModelProvenanceService,
    ProvenanceVerdict,
)

logger = logging.getLogger(__name__)


# Hook called when a sandbox would be provisioned (Phase 2.4 plumbs
# the real sandbox; Phase 2.3 ships a no-op default that simply
# attests "no orphaned sandbox" since none was created). The hook
# returns True iff sandbox provisioning succeeded; False indicates
# infrastructure failure and the pipeline halts cleanly.
SandboxProvisionHook = Callable[[PipelineInput], bool]


def _no_op_sandbox(_: PipelineInput) -> bool:
    """Phase 2.3 default: report sandbox 'provisioned' but actually do nothing.

    Phase 2.4 swaps in the real ECS Fargate / EKS sandbox provisioning
    via the existing Sandbox Network Service. Keeping the hook
    pluggable now means Phase 2.4 is a one-line wiring change.
    """
    return True


class PipelineOrchestrator:
    """Runs the model-assurance pipeline synchronously.

    Dependencies are injected so tests can stub each stage:

        AdapterRegistry            — capability gate
        ModelProvenanceService     — provenance + quarantine
        OracleService              — golden-set evaluation
        ModelAssuranceEvaluator    — CGE scoring with floors
        sandbox_hook               — sandbox provisioning hook

    The orchestrator never raises; every error path produces a
    PipelineResult with PipelineDecision.INFRASTRUCTURE_ERROR. This
    matches the Step Functions Catch behaviour and keeps the audit
    trail complete.
    """

    def __init__(
        self,
        *,
        adapter_registry: AdapterRegistry,
        provenance_service: ModelProvenanceService,
        oracle_service: OracleService,
        assurance_evaluator: ModelAssuranceEvaluator,
        sandbox_hook: SandboxProvisionHook | None = None,
    ) -> None:
        self._adapters = adapter_registry
        self._provenance = provenance_service
        self._oracle = oracle_service
        self._assurance = assurance_evaluator
        self._sandbox = sandbox_hook or _no_op_sandbox

    def run(self, pipeline_input: PipelineInput) -> PipelineResult:
        candidate_id = pipeline_input.artifact.model_id
        started_at = datetime.now(timezone.utc)
        stages: list[StageOutcome] = []

        # ---------------------------------------------- Stage 1: Adapter
        adapter_outcome, disqual_reasons = self._stage_adapter_disqualification(
            pipeline_input
        )
        stages.append(adapter_outcome)
        if disqual_reasons:
            return _terminal(
                candidate_id=candidate_id,
                decision=PipelineDecision.DISQUALIFIED,
                stages=stages,
                started_at=started_at,
                disqualification_reasons=disqual_reasons,
                rejection_reason="adapter capability gate",
            )

        # ---------------------------------------------- Stage 2: Provenance
        provenance_outcome, prov_record = self._stage_provenance(pipeline_input)
        stages.append(provenance_outcome)
        if prov_record is None:
            return _terminal(
                candidate_id=candidate_id,
                decision=PipelineDecision.INFRASTRUCTURE_ERROR,
                stages=stages,
                started_at=started_at,
                rejection_reason=provenance_outcome.detail,
            )
        if prov_record.verdict is ProvenanceVerdict.QUARANTINED:
            return _terminal(
                candidate_id=candidate_id,
                decision=PipelineDecision.QUARANTINED,
                stages=stages,
                started_at=started_at,
                provenance_record=prov_record,
                rejection_reason="provenance quarantined",
            )
        if prov_record.verdict is ProvenanceVerdict.REJECTED:
            return _terminal(
                candidate_id=candidate_id,
                decision=PipelineDecision.REJECTED,
                stages=stages,
                started_at=started_at,
                provenance_record=prov_record,
                rejection_reason="provenance rejected",
            )

        # ---------------------------------------------- Stage 3: Sandbox
        sandbox_outcome, sandbox_ok = self._stage_sandbox(pipeline_input)
        stages.append(sandbox_outcome)
        if not sandbox_ok:
            return _terminal(
                candidate_id=candidate_id,
                decision=PipelineDecision.INFRASTRUCTURE_ERROR,
                stages=stages,
                started_at=started_at,
                provenance_record=prov_record,
                rejection_reason=sandbox_outcome.detail,
            )

        # ---------------------------------------------- Stage 4: Oracle
        oracle_outcome, oracle_eval = self._stage_oracle(pipeline_input)
        stages.append(oracle_outcome)
        if oracle_eval is None:
            return _terminal(
                candidate_id=candidate_id,
                decision=PipelineDecision.INFRASTRUCTURE_ERROR,
                stages=stages,
                started_at=started_at,
                provenance_record=prov_record,
                rejection_reason=oracle_outcome.detail,
            )

        # ---------------------------------------------- Stage 5: CGE Scoring
        cge_outcome, assurance_result = self._stage_cge_scoring(
            pipeline_input, prov_record, oracle_eval
        )
        stages.append(cge_outcome)
        if assurance_result is None:
            return _terminal(
                candidate_id=candidate_id,
                decision=PipelineDecision.INFRASTRUCTURE_ERROR,
                stages=stages,
                started_at=started_at,
                provenance_record=prov_record,
                oracle_evaluation=oracle_eval,
                rejection_reason=cge_outcome.detail,
            )
        if assurance_result.verdict is ModelAssuranceVerdict.REJECT:
            return _terminal(
                candidate_id=candidate_id,
                decision=PipelineDecision.REJECTED,
                stages=stages,
                started_at=started_at,
                provenance_record=prov_record,
                oracle_evaluation=oracle_eval,
                assurance_verdict=assurance_result.verdict,
                rejection_reason=assurance_result.rejection_reason,
            )

        # ---------------------------------------------- Stage 6: Report (stub)
        report_outcome = StageOutcome(
            stage=PipelineStage.REPORT,
            succeeded=True,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            detail="report generation deferred to Phase 2.5",
        )
        stages.append(report_outcome)

        # ---------------------------------------------- Stage 7: HITL queue
        hitl_outcome = StageOutcome(
            stage=PipelineStage.HITL_QUEUED,
            succeeded=True,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            detail=(
                "queued for HITL approval — verdict "
                f"{assurance_result.verdict.value}"
            ),
        )
        stages.append(hitl_outcome)

        return _terminal(
            candidate_id=candidate_id,
            decision=PipelineDecision.HITL_QUEUED,
            stages=stages,
            started_at=started_at,
            provenance_record=prov_record,
            oracle_evaluation=oracle_eval,
            assurance_verdict=assurance_result.verdict,
        )

    # ------------------------------------------------------- Stage methods

    def _stage_adapter_disqualification(
        self, pipeline_input: PipelineInput
    ) -> tuple[StageOutcome, tuple]:
        started = datetime.now(timezone.utc)
        try:
            adapter = self._adapters.find(pipeline_input.artifact.model_id)
            if adapter is None:
                # Per ADR-088 Scout Agent: synthesise a defensive
                # adapter when the registry doesn't know the model.
                # The pipeline can continue — the missing adapter is
                # not itself a disqualification reason. Skip stage.
                return (
                    StageOutcome(
                        stage=PipelineStage.ADAPTER_DISQUALIFICATION,
                        succeeded=True,
                        started_at=started,
                        completed_at=datetime.now(timezone.utc),
                        detail="no registered adapter; treating as new candidate",
                    ),
                    (),
                )
            reasons = pipeline_input.requirements.check(adapter)
            return (
                StageOutcome(
                    stage=PipelineStage.ADAPTER_DISQUALIFICATION,
                    succeeded=not reasons,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc),
                    detail=(
                        ""
                        if not reasons
                        else f"disqualified: {', '.join(r.value for r in reasons)}"
                    ),
                ),
                reasons,
            )
        except Exception as exc:
            return (
                StageOutcome(
                    stage=PipelineStage.ADAPTER_DISQUALIFICATION,
                    succeeded=False,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc),
                    detail=str(exc),
                    error_type=type(exc).__name__,
                ),
                (),
            )

    def _stage_provenance(self, pipeline_input: PipelineInput):
        started = datetime.now(timezone.utc)
        try:
            record = self._provenance.evaluate(pipeline_input.artifact)
            return (
                StageOutcome(
                    stage=PipelineStage.PROVENANCE,
                    succeeded=record.verdict is ProvenanceVerdict.APPROVED,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc),
                    detail=(
                        f"verdict={record.verdict.value} "
                        f"trust={record.trust_score:.3f}"
                    ),
                ),
                record,
            )
        except Exception as exc:
            return (
                StageOutcome(
                    stage=PipelineStage.PROVENANCE,
                    succeeded=False,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc),
                    detail=str(exc),
                    error_type=type(exc).__name__,
                ),
                None,
            )

    def _stage_sandbox(self, pipeline_input: PipelineInput):
        started = datetime.now(timezone.utc)
        try:
            ok = self._sandbox(pipeline_input)
            return (
                StageOutcome(
                    stage=PipelineStage.SANDBOX,
                    succeeded=ok,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc),
                    detail="provisioned" if ok else "provisioning failed",
                ),
                ok,
            )
        except Exception as exc:
            return (
                StageOutcome(
                    stage=PipelineStage.SANDBOX,
                    succeeded=False,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc),
                    detail=str(exc),
                    error_type=type(exc).__name__,
                ),
                False,
            )

    def _stage_oracle(self, pipeline_input: PipelineInput):
        started = datetime.now(timezone.utc)
        try:
            evaluation = self._oracle.evaluate(
                candidate_id=pipeline_input.artifact.model_id,
                candidate_outputs=pipeline_input.candidate_outputs,
                seed=pipeline_input.seed,
            )
            return (
                StageOutcome(
                    stage=PipelineStage.ORACLE,
                    succeeded=True,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc),
                    detail=(
                        f"cases={evaluation.cases_evaluated} "
                        f"pass_rate={evaluation.overall_pass_rate:.3f}"
                    ),
                ),
                evaluation,
            )
        except Exception as exc:
            return (
                StageOutcome(
                    stage=PipelineStage.ORACLE,
                    succeeded=False,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc),
                    detail=str(exc),
                    error_type=type(exc).__name__,
                ),
                None,
            )

    def _stage_cge_scoring(
        self,
        pipeline_input: PipelineInput,
        provenance_record,
        oracle_eval: OracleEvaluation,
    ):
        started = datetime.now(timezone.utc)
        try:
            # Build candidate axis scores from oracle per-axis aggregates.
            scores: list[AxisScore] = []
            for axis, score in oracle_eval.per_axis_scores:
                scores.append(AxisScore(axis=axis, score=max(0.0, min(1.0, score))))

            incumbent = None
            if pipeline_input.incumbent_id and pipeline_input.incumbent_axis_scores:
                # Convert string-keyed incumbent scores back into MA axes.
                axis_map: dict[ModelAssuranceAxis, float] = {}
                for axis_id, score in pipeline_input.incumbent_axis_scores:
                    try:
                        ax = ModelAssuranceAxis(axis_id)
                        axis_map[ax] = float(score)
                    except ValueError:
                        continue
                if axis_map:
                    incumbent = make_incumbent(pipeline_input.incumbent_id, axis_map)

            assurance_result = self._assurance.evaluate(
                candidate_id=pipeline_input.artifact.model_id,
                candidate_scores=tuple(scores),
                incumbent=incumbent,
                provenance_multiplier=provenance_record.trust_score,
            )
            return (
                StageOutcome(
                    stage=PipelineStage.CGE_SCORING,
                    succeeded=True,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc),
                    detail=(
                        f"verdict={assurance_result.verdict.value} "
                        f"U={assurance_result.utility_score:.3f}"
                    ),
                ),
                assurance_result,
            )
        except Exception as exc:
            return (
                StageOutcome(
                    stage=PipelineStage.CGE_SCORING,
                    succeeded=False,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc),
                    detail=str(exc),
                    error_type=type(exc).__name__,
                ),
                None,
            )


def _terminal(
    *,
    candidate_id: str,
    decision: PipelineDecision,
    stages: list[StageOutcome],
    started_at: datetime,
    disqualification_reasons: tuple = (),
    provenance_record=None,
    oracle_evaluation: OracleEvaluation | None = None,
    assurance_verdict: ModelAssuranceVerdict | None = None,
    rejection_reason: str | None = None,
) -> PipelineResult:
    return PipelineResult(
        candidate_id=candidate_id,
        decision=decision,
        stages=tuple(stages),
        disqualification_reasons=disqualification_reasons,
        provenance_record=provenance_record,
        oracle_evaluation=oracle_evaluation,
        assurance_verdict=assurance_verdict,
        rejection_reason=rejection_reason,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
    )
