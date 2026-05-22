"""
Tests for the Cross-Repo Chain Analysis worker (ADR-089 Phase 3).
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
    ChainAnalysisDependencies,
    CrossRepoEdge,
    CrossRepoGraph,
    ExploitChain,
    HitlApprovalRequest,
    RepoRef,
)
from src.services.campaign_manager.phases.chain_analysis import (
    CHAIN_ANALYSIS_BLACKBOARD_KEY,
    ChainAnalysisBlackboard,
    ChainAnalysisWorker,
)
from src.services.campaign_manager.state_store import InMemoryCampaignStateStore
from src.services.campaign_manager.tenant_cost_rollup import InMemoryTenantCostRollup


@dataclass
class FakeRepoDiscovery:
    repos: tuple[RepoRef, ...] = ()

    async def discover(self, *, fleet_target: dict) -> tuple[RepoRef, ...]:
        return self.repos


@dataclass
class FakeGraphBuilder:
    graph: Optional[CrossRepoGraph] = None

    async def build(self, *, repos: tuple[RepoRef, ...]) -> CrossRepoGraph:
        if self.graph is not None:
            return self.graph
        return CrossRepoGraph(
            repos=repos,
            edges=(),
            input_tokens=80_000,
            output_tokens=15_000,
        )


@dataclass
class FakePathSearch:
    chains: tuple[ExploitChain, ...] = ()

    async def search(self, *, graph: CrossRepoGraph) -> tuple[ExploitChain, ...]:
        return self.chains


@dataclass
class FakeHitl:
    last_request: Optional[HitlApprovalRequest] = None

    async def request_approval(self, *, request: HitlApprovalRequest) -> str:
        self.last_request = request
        return "ticket-C"


@pytest.fixture()
def tenant_id() -> str:
    return "tenant-chain"


@pytest.fixture()
def billing_period() -> str:
    return "2026-05"


@pytest.fixture()
def chain_definition(tenant_id) -> CampaignDefinition:
    return CampaignDefinition(
        campaign_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        campaign_type=CampaignType.CROSS_REPO_CHAIN_ANALYSIS,
        target={"fleet": "acme-microservices"},
        success_criteria={"goal": "discover_exploit_chains"},
        cost_cap_usd=200.0,
        wall_clock_budget_hours=6.0,
        autonomy_policy_id="policy-standard",
        hitl_milestones=("hitl_review",),
        approver_quorum=1,
        creator_principal_arn="arn:aws:iam::123:user/alice",
    )


@pytest.fixture()
def two_repos() -> tuple[RepoRef, ...]:
    return (
        RepoRef(repo_id="r1", url="acme/svc-a", primary_language="python"),
        RepoRef(repo_id="r2", url="acme/svc-b", primary_language="go"),
    )


@pytest.fixture()
def one_chain() -> tuple[ExploitChain, ...]:
    return (
        ExploitChain(
            chain_id="chain-1",
            edges=(
                CrossRepoEdge(
                    source_repo_id="r1",
                    source_symbol="svc-a:auth.login",
                    sink_repo_id="r2",
                    sink_symbol="svc-b:db.execute_raw",
                    edge_type="rpc",
                    confidence=0.85,
                ),
            ),
            estimated_impact="CRITICAL",
            cwe_ids=("CWE-89",),
            confidence=0.85,
        ),
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
        worker_registry={CampaignType.CROSS_REPO_CHAIN_ANALYSIS: ChainAnalysisWorker()},
    )


class TestChainAnalysis:
    @pytest.mark.asyncio
    async def test_happy_path_finds_one_chain(
        self,
        configured_orchestrator,
        chain_definition,
        billing_period,
        two_repos,
        one_chain,
    ):
        orch = configured_orchestrator
        await orch.create_campaign(chain_definition, billing_period)

        deps = ChainAnalysisDependencies(
            repo_discovery=FakeRepoDiscovery(repos=two_repos),
            graph_builder=FakeGraphBuilder(),
            path_search=FakePathSearch(chains=one_chain),
            hitl_gateway=FakeHitl(),
        )
        board = ChainAnalysisBlackboard()
        extra = {
            CAMPAIGN_DEPS_KEY: deps,
            CHAIN_ANALYSIS_BLACKBOARD_KEY: board,
        }
        bob = "arn:aws:iam::123:user/bob"

        for _ in range(20):
            state = await orch.run_next_phase(chain_definition, phase_extra=extra)
            if state.status == CampaignStatus.AWAITING_HITL:
                state = await orch.approve_milestone(
                    chain_definition, approver_principal_arn=bob
                )
                continue
            if state.status.is_terminal:
                break

        assert state.status == CampaignStatus.COMPLETED
        assert board.repos == two_repos
        assert board.graph is not None
        assert len(board.chains) == 1
        assert board.chains[0].estimated_impact == "CRITICAL"
        assert board.hitl_ticket_id == "ticket-C"
        assert "chain-reports/" in board.report_s3_key

    @pytest.mark.asyncio
    async def test_graph_build_fails_without_repos(
        self,
        configured_orchestrator,
        chain_definition,
        billing_period,
        one_chain,
    ):
        orch = configured_orchestrator
        await orch.create_campaign(chain_definition, billing_period)

        deps = ChainAnalysisDependencies(
            repo_discovery=FakeRepoDiscovery(repos=()),  # empty
            graph_builder=FakeGraphBuilder(),
            path_search=FakePathSearch(chains=one_chain),
            hitl_gateway=FakeHitl(),
        )
        board = ChainAnalysisBlackboard()
        extra = {
            CAMPAIGN_DEPS_KEY: deps,
            CHAIN_ANALYSIS_BLACKBOARD_KEY: board,
        }

        for _ in range(20):
            state = await orch.run_next_phase(chain_definition, phase_extra=extra)
            if state.status.is_terminal:
                break

        assert state.status == CampaignStatus.FAILED
        assert board.graph is None

    @pytest.mark.asyncio
    async def test_no_deps_stub_run_completes(
        self, configured_orchestrator, chain_definition, billing_period
    ):
        orch = configured_orchestrator
        await orch.create_campaign(chain_definition, billing_period)
        bob = "arn:aws:iam::123:user/bob"
        for _ in range(20):
            state = await orch.run_next_phase(chain_definition)
            if state.status == CampaignStatus.AWAITING_HITL:
                state = await orch.approve_milestone(
                    chain_definition, approver_principal_arn=bob
                )
                continue
            if state.status.is_terminal:
                break
        assert state.status == CampaignStatus.COMPLETED
