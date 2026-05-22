"""
Project Aura - Self-Play Security Training Worker (Phase 6).

Long-horizon dual-role attacker-vs-defender self-play campaigns
producing trained adapters that are evaluated against a held-out
probe set and promoted only on HITL approval. Composes ADR-050
SWE-RL training infrastructure via the SelfPlayTrainingDependencies
Ports.

Phase graph:
    corpus_curation -> dual_role_training -> eval -> hitl_review ->
    adapter_promotion

The HITL milestone is mandatory before any adapter is promoted into
production -- per ADR-089 D8, model-promotion is a high-impact
action that requires human sign-off.

Author: Project Aura Team
Created: 2026-05-22
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Optional

from src.services.vulnerability_scanner.analysis.capability import ModelCapabilityTier

from ..contracts import (
    ArtifactRef,
    CampaignPhase,
    CampaignType,
    PhaseOutcome,
    SuccessCriteriaProgress,
)
from ._ports import (
    CAMPAIGN_DEPS_KEY,
    AdapterPromotionRecord,
    EvalResult,
    HitlApprovalRequest,
    SelfPlayTrainingDependencies,
    TrainingCorpusRef,
    TrainingResult,
)
from .base import CampaignWorker, Phase, PhaseExecutionContext, PhaseResult

SELF_PLAY_BLACKBOARD_KEY: str = "self_play_blackboard"


@dataclass
class SelfPlayTrainingBlackboard:
    """Per-campaign mutable state for Phase 6."""

    corpus: Optional[TrainingCorpusRef] = None
    training: Optional[TrainingResult] = None
    eval_result: Optional[EvalResult] = None
    hitl_ticket_id: str = ""
    promotion: Optional[AdapterPromotionRecord] = None


_CORPUS = CampaignPhase(
    phase_id="corpus_curation",
    label="Curate training corpus",
    order=0,
    estimated_cost_usd=5.0,
)
_TRAIN = CampaignPhase(
    phase_id="dual_role_training",
    label="Attacker vs Defender self-play training",
    order=1,
    is_high_consequence=True,
    estimated_cost_usd=200.0,
)
_EVAL = CampaignPhase(
    phase_id="eval",
    label="Evaluate trained adapter against probe set",
    order=2,
    estimated_cost_usd=15.0,
)
_HITL = CampaignPhase(
    phase_id="hitl_review",
    label="Operator review of promotion recommendation",
    order=3,
    is_milestone=True,
    is_high_consequence=True,
)
_PROMOTE = CampaignPhase(
    phase_id="adapter_promotion",
    label="Promote (or refuse to promote) trained adapter",
    order=4,
    is_high_consequence=True,
)


def _get_deps(
    context: PhaseExecutionContext,
) -> Optional[SelfPlayTrainingDependencies]:
    deps = context.extra.get(CAMPAIGN_DEPS_KEY)
    if isinstance(deps, SelfPlayTrainingDependencies):
        return deps
    return None


def _get_or_create_blackboard(
    context: PhaseExecutionContext,
) -> SelfPlayTrainingBlackboard:
    board = context.extra.get(SELF_PLAY_BLACKBOARD_KEY)
    if isinstance(board, SelfPlayTrainingBlackboard):
        return board
    board = SelfPlayTrainingBlackboard()
    context.extra[SELF_PLAY_BLACKBOARD_KEY] = board
    return board


def _artifact(context: PhaseExecutionContext) -> ArtifactRef:
    artifact_id = hashlib.sha256(
        f"{context.definition.campaign_id}/{context.phase.phase_id}".encode()
    ).hexdigest()
    return ArtifactRef(
        artifact_id=artifact_id,
        manifest_s3_key=(
            f"self-play/{context.definition.tenant_id}/"
            f"{context.definition.campaign_id}/{context.phase.phase_id}.json"
        ),
    )


def _stub_result(context: PhaseExecutionContext, *, criterion_id: str) -> PhaseResult:
    return PhaseResult(
        outcome=PhaseOutcome.COMPLETED,
        success_criteria_progress=(
            SuccessCriteriaProgress(criterion_id=criterion_id, progress=1.0),
        ),
        phase_summary=f"[stub] Self-Play phase {context.phase.label} done.",
        artifacts=(_artifact(context),),
    )


class CorpusCurationPhase(Phase):
    criterion_id = "corpus_curated"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.corpus_curator is None:
            return _stub_result(context, criterion_id=self.criterion_id)

        board = _get_or_create_blackboard(context)
        corpus = await deps.corpus_curator.curate(domain=deps.domain)
        board.corpus = corpus
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Curated corpus {corpus.corpus_id}: "
                f"{corpus.sample_count} samples, domain={corpus.domain}."
            ),
            artifacts=(_artifact(context),),
        )


class DualRoleTrainingPhase(Phase):
    criterion_id = "training_completed"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.dual_role is None:
            return _stub_result(context, criterion_id=self.criterion_id)

        board = _get_or_create_blackboard(context)
        if board.corpus is None:
            return PhaseResult(
                outcome=PhaseOutcome.FAILED,
                phase_summary="training prerequisite missing: corpus.",
            )

        training = await deps.dual_role.run(
            corpus=board.corpus,
            episode_budget=deps.episode_budget,
        )
        board.training = training
        # Training is expensive: record as ADVANCED-tier compute time.
        # The fake adapters don't know token usage, so we charge a flat
        # per-episode cost using sandbox_cost (it is a non-LLM bookkeeping
        # bucket that still counts against the cap).
        context.cost_tracker.record_sandbox_cost(0.5 * len(training.episodes))
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Ran {len(training.episodes)} dual-role episodes; "
                f"attacker_win={training.attacker_win_rate:.2f} "
                f"defender_win={training.defender_win_rate:.2f}."
            ),
            artifacts=(_artifact(context),),
        )


class EvalPhase(Phase):
    criterion_id = "eval_complete"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.evaluator is None:
            return _stub_result(context, criterion_id=self.criterion_id)

        board = _get_or_create_blackboard(context)
        if board.training is None:
            return PhaseResult(
                outcome=PhaseOutcome.FAILED,
                phase_summary="eval prerequisite missing: training.",
            )

        result = await deps.evaluator.evaluate(training=board.training)
        board.eval_result = result
        context.cost_tracker.record(
            ModelCapabilityTier.STANDARD,
            150_000,
            30_000,
        )
        if result.regressions:
            # Eval-time regressions block promotion downstream.
            return PhaseResult(
                outcome=PhaseOutcome.COMPLETED,
                success_criteria_progress=(
                    SuccessCriteriaProgress(
                        criterion_id=self.criterion_id, progress=1.0
                    ),
                ),
                phase_summary=(
                    f"Eval pass_rate={result.pass_rate:.2f} with "
                    f"{len(result.regressions)} regression(s); "
                    f"promotion_recommended={result.promotion_recommended}."
                ),
                artifacts=(_artifact(context),),
            )
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Eval pass_rate={result.pass_rate:.2f}; clean. "
                f"promotion_recommended={result.promotion_recommended}."
            ),
            artifacts=(_artifact(context),),
        )


class SelfPlayHitlPhase(Phase):
    criterion_id = "promotion_human_approved"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is not None and deps.hitl_gateway is not None:
            board = _get_or_create_blackboard(context)
            eval_result = board.eval_result
            summary = "no eval"
            if eval_result is not None:
                summary = (
                    f"pass_rate={eval_result.pass_rate:.2f} "
                    f"recommend={eval_result.promotion_recommended} "
                    f"regressions={len(eval_result.regressions)}"
                )
            request = HitlApprovalRequest(
                request_id=str(uuid.uuid4()),
                campaign_id=context.definition.campaign_id,
                phase_id=context.phase.phase_id,
                artifact_summary=f"Adapter promotion review ({summary})",
                severity="HIGH",
            )
            board.hitl_ticket_id = await deps.hitl_gateway.request_approval(
                request=request
            )
        return PhaseResult(
            outcome=PhaseOutcome.HITL_PENDING,
            phase_summary=(
                "Self-Play Training: adapter promotion gated on human review."
            ),
        )


class AdapterPromotionPhase(Phase):
    """Promote the adapter; honour eval recommendation."""

    criterion_id = "promotion_decided"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.promoter is None:
            return _stub_result(context, criterion_id=self.criterion_id)

        board = _get_or_create_blackboard(context)
        if board.eval_result is None:
            return PhaseResult(
                outcome=PhaseOutcome.FAILED,
                phase_summary="promotion prerequisite missing: eval_result.",
            )

        record = await deps.promoter.promote(eval_result=board.eval_result)
        board.promotion = record
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Adapter {record.adapter_id} "
                f"{'promoted' if record.promoted else 'refused'}: "
                f"{record.reason}"
            ),
            artifacts=(_artifact(context),),
        )


class SelfPlayTrainingWorker(CampaignWorker):
    _PHASE_GRAPH: tuple[Phase, ...] = (
        CorpusCurationPhase(_CORPUS),
        DualRoleTrainingPhase(_TRAIN),
        EvalPhase(_EVAL),
        SelfPlayHitlPhase(_HITL),
        AdapterPromotionPhase(_PROMOTE),
    )

    @property
    def campaign_type(self) -> CampaignType:
        return CampaignType.SELF_PLAY_SECURITY_TRAINING

    def phase_graph(self) -> tuple[Phase, ...]:
        return self._PHASE_GRAPH


__all__ = [
    "AdapterPromotionPhase",
    "CorpusCurationPhase",
    "DualRoleTrainingPhase",
    "EvalPhase",
    "SELF_PLAY_BLACKBOARD_KEY",
    "SelfPlayHitlPhase",
    "SelfPlayTrainingBlackboard",
    "SelfPlayTrainingWorker",
]
