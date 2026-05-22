"""
Tests for the Mythos Exploit Refinement blocked-stub worker (ADR-089
Phase 5). Validates that the worker is registered and surfaces a
clear failure path until issue #115 (vendor-access-gate) clears.
"""

from __future__ import annotations

import uuid

import pytest

from src.services.campaign_manager.checkpoint_store import InMemoryCheckpointStore
from src.services.campaign_manager.contracts import (
    CampaignDefinition,
    CampaignStatus,
    CampaignType,
)
from src.services.campaign_manager.operation_ledger import InMemoryOperationLedger
from src.services.campaign_manager.orchestrator import CampaignOrchestrator
from src.services.campaign_manager.phases.mythos_exploit_refinement import (
    MythosExploitRefinementWorker,
)
from src.services.campaign_manager.state_store import InMemoryCampaignStateStore
from src.services.campaign_manager.tenant_cost_rollup import InMemoryTenantCostRollup


@pytest.fixture()
def tenant_id() -> str:
    return "tenant-mythos"


@pytest.fixture()
def billing_period() -> str:
    return "2026-05"


@pytest.fixture()
def mythos_definition(tenant_id) -> CampaignDefinition:
    return CampaignDefinition(
        campaign_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        campaign_type=CampaignType.MYTHOS_EXPLOIT_REFINEMENT,
        target={"finding_id": "f-1"},
        success_criteria={"goal": "produce_verified_poc"},
        cost_cap_usd=200.0,
        wall_clock_budget_hours=4.0,
        autonomy_policy_id="policy-mythos",
        hitl_milestones=(),
        approver_quorum=2,  # high-impact campaign type
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
            CampaignType.MYTHOS_EXPLOIT_REFINEMENT: MythosExploitRefinementWorker()
        },
    )


class TestMythosBlocked:
    @pytest.mark.asyncio
    async def test_campaign_terminates_failed_at_first_phase(
        self, configured_orchestrator, mythos_definition, billing_period
    ):
        orch = configured_orchestrator
        await orch.create_campaign(mythos_definition, billing_period)

        for _ in range(5):
            state = await orch.run_next_phase(mythos_definition)
            if state.status.is_terminal:
                break
        assert state.status == CampaignStatus.FAILED

    def test_blocked_reason_cites_115(self):
        reason = MythosExploitRefinementWorker.blocked_reason()
        assert "#115" in reason
        assert "Mythos" in reason

    def test_worker_phase_graph_has_three_phases(self):
        graph = MythosExploitRefinementWorker().phase_graph()
        assert len(graph) == 3
        ids = [p.definition.phase_id for p in graph]
        assert ids == ["exploit_triage", "exploit_refinement", "poc_quarantine"]
