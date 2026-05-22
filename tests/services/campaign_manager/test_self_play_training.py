"""
Tests for the Self-Play Security Training worker (ADR-089 Phase 6).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

import pytest

from src.services.campaign_manager.checkpoint_store import InMemoryCheckpointStore
from src.services.campaign_manager.contracts import (
    CampaignDefinition,
    CampaignStatus,
    CampaignType,
)
from src.services.campaign_manager.operation_ledger import InMemoryOperationLedger
from src.services.campaign_manager.orchestrator import CampaignOrchestrator
from src.services.campaign_manager.phases._ports import (
    CAMPAIGN_DEPS_KEY,
    AdapterPromotionRecord,
    DualRoleEpisode,
    EvalResult,
    HitlApprovalRequest,
    SelfPlayTrainingDependencies,
    TrainingCorpusRef,
    TrainingResult,
)
from src.services.campaign_manager.phases.self_play_training import (
    SELF_PLAY_BLACKBOARD_KEY,
    SelfPlayTrainingBlackboard,
    SelfPlayTrainingWorker,
)
from src.services.campaign_manager.state_store import InMemoryCampaignStateStore
from src.services.campaign_manager.tenant_cost_rollup import InMemoryTenantCostRollup


@dataclass
class FakeCurator:
    corpus: Optional[TrainingCorpusRef] = None

    async def curate(self, *, domain: str) -> TrainingCorpusRef:
        if self.corpus is not None:
            return self.corpus
        return TrainingCorpusRef(
            corpus_id="corpus-abc",
            s3_uri="s3://aura-train/corpus-abc",
            sample_count=1000,
            domain=domain,
        )


@dataclass
class FakeDualRole:
    result: Optional[TrainingResult] = None

    async def run(
        self,
        *,
        corpus: TrainingCorpusRef,
        episode_budget: int,
    ) -> TrainingResult:
        if self.result is not None:
            return self.result
        eps = tuple(
            DualRoleEpisode(
                episode_id=f"ep-{i}",
                attacker_score=0.6,
                defender_score=0.4,
                transcript_s3_key=f"s3://aura-train/transcript-{i}",
                duration_seconds=12,
            )
            for i in range(min(episode_budget, 8))
        )
        return TrainingResult(
            run_id="run-123",
            episodes=eps,
            attacker_win_rate=0.6,
            defender_win_rate=0.4,
        )


@dataclass
class FakeEval:
    result: Optional[EvalResult] = None

    async def evaluate(self, *, training: TrainingResult) -> EvalResult:
        if self.result is not None:
            return self.result
        return EvalResult(
            eval_id="eval-1",
            pass_rate=0.93,
            regressions=(),
            promotion_recommended=True,
        )


@dataclass
class FakePromoter:
    record: Optional[AdapterPromotionRecord] = None

    async def promote(self, *, eval_result: EvalResult) -> AdapterPromotionRecord:
        if self.record is not None:
            return self.record
        return AdapterPromotionRecord(
            adapter_id="adapter-v3",
            promoted=eval_result.promotion_recommended,
            reason=(
                "pass_rate above threshold"
                if eval_result.promotion_recommended
                else f"regressions={len(eval_result.regressions)}"
            ),
        )


@dataclass
class FakeHitl:
    last: Optional[HitlApprovalRequest] = None

    async def request_approval(self, *, request: HitlApprovalRequest) -> str:
        self.last = request
        return "ticket-SP"


@pytest.fixture()
def tenant_id() -> str:
    return "tenant-sp"


@pytest.fixture()
def billing_period() -> str:
    return "2026-05"


@pytest.fixture()
def sp_definition(tenant_id) -> CampaignDefinition:
    return CampaignDefinition(
        campaign_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        campaign_type=CampaignType.SELF_PLAY_SECURITY_TRAINING,
        target={"domain": "compliance-hardening"},
        success_criteria={"goal": "train_better_adapter"},
        cost_cap_usd=500.0,
        wall_clock_budget_hours=24.0,
        autonomy_policy_id="policy-research",
        hitl_milestones=("hitl_review",),
        approver_quorum=1,
        creator_principal_arn="arn:aws:iam::123:user/alice",
    )


@pytest.fixture()
async def configured_orchestrator(tenant_id, billing_period) -> CampaignOrchestrator:
    rollup = InMemoryTenantCostRollup()
    await rollup.set_cap(tenant_id, billing_period, cap_usd=10_000.0)
    return CampaignOrchestrator(
        state_store=InMemoryCampaignStateStore(),
        checkpoint_store=InMemoryCheckpointStore(),
        operation_ledger=InMemoryOperationLedger(),
        tenant_rollup=rollup,
        worker_registry={
            CampaignType.SELF_PLAY_SECURITY_TRAINING: SelfPlayTrainingWorker()
        },
    )


class TestSelfPlayTraining:
    @pytest.mark.asyncio
    async def test_happy_path_recommends_and_promotes(
        self,
        configured_orchestrator,
        sp_definition,
        billing_period,
    ):
        orch = configured_orchestrator
        await orch.create_campaign(sp_definition, billing_period)

        deps = SelfPlayTrainingDependencies(
            corpus_curator=FakeCurator(),
            dual_role=FakeDualRole(),
            evaluator=FakeEval(),
            promoter=FakePromoter(),
            hitl_gateway=FakeHitl(),
            episode_budget=8,
            domain="compliance-hardening",
        )
        board = SelfPlayTrainingBlackboard()
        extra = {
            CAMPAIGN_DEPS_KEY: deps,
            SELF_PLAY_BLACKBOARD_KEY: board,
        }
        bob = "arn:aws:iam::123:user/bob"

        for _ in range(20):
            state = await orch.run_next_phase(sp_definition, phase_extra=extra)
            if state.status == CampaignStatus.AWAITING_HITL:
                state = await orch.approve_milestone(
                    sp_definition, approver_principal_arn=bob
                )
                continue
            if state.status.is_terminal:
                break

        assert state.status == CampaignStatus.COMPLETED
        assert board.corpus is not None
        assert board.training is not None
        assert len(board.training.episodes) == 8
        assert board.eval_result is not None
        assert board.eval_result.promotion_recommended is True
        assert board.promotion is not None
        assert board.promotion.promoted is True

    @pytest.mark.asyncio
    async def test_promotion_refused_when_eval_recommends_against(
        self,
        configured_orchestrator,
        sp_definition,
        billing_period,
    ):
        orch = configured_orchestrator
        await orch.create_campaign(sp_definition, billing_period)

        deps = SelfPlayTrainingDependencies(
            corpus_curator=FakeCurator(),
            dual_role=FakeDualRole(),
            evaluator=FakeEval(
                result=EvalResult(
                    eval_id="eval-bad",
                    pass_rate=0.60,
                    regressions=("probe-X", "probe-Y"),
                    promotion_recommended=False,
                )
            ),
            promoter=FakePromoter(),
            hitl_gateway=FakeHitl(),
            episode_budget=4,
        )
        board = SelfPlayTrainingBlackboard()
        extra = {
            CAMPAIGN_DEPS_KEY: deps,
            SELF_PLAY_BLACKBOARD_KEY: board,
        }
        bob = "arn:aws:iam::123:user/bob"

        for _ in range(20):
            state = await orch.run_next_phase(sp_definition, phase_extra=extra)
            if state.status == CampaignStatus.AWAITING_HITL:
                state = await orch.approve_milestone(
                    sp_definition, approver_principal_arn=bob
                )
                continue
            if state.status.is_terminal:
                break

        assert state.status == CampaignStatus.COMPLETED
        assert board.promotion is not None
        assert board.promotion.promoted is False
        assert "regressions" in board.promotion.reason

    @pytest.mark.asyncio
    async def test_no_deps_stub_run_completes(
        self, configured_orchestrator, sp_definition, billing_period
    ):
        orch = configured_orchestrator
        await orch.create_campaign(sp_definition, billing_period)
        bob = "arn:aws:iam::123:user/bob"
        for _ in range(20):
            state = await orch.run_next_phase(sp_definition)
            if state.status == CampaignStatus.AWAITING_HITL:
                state = await orch.approve_milestone(
                    sp_definition, approver_principal_arn=bob
                )
                continue
            if state.status.is_terminal:
                break
        assert state.status == CampaignStatus.COMPLETED
