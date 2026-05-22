"""
Tests for the Continuous Threat Hunting worker (ADR-089 Phase 4).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    CveFeedEntry,
    HitlApprovalRequest,
    HuntFinding,
    RuntimeTelemetrySnapshot,
    ThreatHuntingDependencies,
)
from src.services.campaign_manager.phases.threat_hunting import (
    THREAT_HUNTING_BLACKBOARD_KEY,
    ContinuousThreatHuntingWorker,
    ThreatHuntingBlackboard,
)
from src.services.campaign_manager.state_store import InMemoryCampaignStateStore
from src.services.campaign_manager.tenant_cost_rollup import InMemoryTenantCostRollup


@dataclass
class FakeCveFeed:
    entries: tuple[CveFeedEntry, ...] = ()
    calls: int = 0

    async def poll(self, *, since: datetime) -> tuple[CveFeedEntry, ...]:
        self.calls += 1
        # First call returns the configured entries; subsequent (budget) polls
        # return nothing so we don't double-count.
        return self.entries if self.calls == 1 else ()


@dataclass
class FakeTelemetry:
    snap: Optional[RuntimeTelemetrySnapshot] = None

    async def snapshot(self) -> RuntimeTelemetrySnapshot:
        if self.snap is not None:
            return self.snap
        return RuntimeTelemetrySnapshot(
            captured_at=datetime.now(timezone.utc),
            components_in_use=("openssl@3.0.5", "log4j@2.16.0"),
        )


@dataclass
class FakeCorrelator:
    findings: tuple[HuntFinding, ...] = ()
    calls: int = 0

    async def correlate(
        self,
        *,
        cves: tuple[CveFeedEntry, ...],
        telemetry: RuntimeTelemetrySnapshot,
    ) -> tuple[HuntFinding, ...]:
        self.calls += 1
        return self.findings


@dataclass
class FakeHitl:
    requests: list[HitlApprovalRequest] = field(default_factory=list)

    async def request_approval(self, *, request: HitlApprovalRequest) -> str:
        self.requests.append(request)
        return f"ticket-{len(self.requests)}"


@pytest.fixture()
def tenant_id() -> str:
    return "tenant-hunt"


@pytest.fixture()
def billing_period() -> str:
    return "2026-05"


@pytest.fixture()
def hunt_definition(tenant_id) -> CampaignDefinition:
    return CampaignDefinition(
        campaign_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        campaign_type=CampaignType.CONTINUOUS_THREAT_HUNTING,
        target={"fleet": "acme-prod"},
        success_criteria={"goal": "watch_for_cves"},
        cost_cap_usd=100.0,
        wall_clock_budget_hours=1.0,
        autonomy_policy_id="policy-standard",
        hitl_milestones=(),
        approver_quorum=1,
        creator_principal_arn="arn:aws:iam::123:user/alice",
    )


@pytest.fixture()
def critical_cves() -> tuple[CveFeedEntry, ...]:
    return (
        CveFeedEntry(
            cve_id="CVE-2026-12345",
            published_at=datetime.now(timezone.utc),
            affected_components=("openssl@3.0.5",),
            severity="CRITICAL",
            summary="OpenSSL memory corruption",
        ),
    )


@pytest.fixture()
def critical_findings() -> tuple[HuntFinding, ...]:
    return (
        HuntFinding(
            finding_id="hf-1",
            cve_id="CVE-2026-12345",
            affected_component="openssl@3.0.5",
            runtime_evidence="openssl@3.0.5 detected in /usr/lib",
            severity="CRITICAL",
            proposed_action="patch",
        ),
        HuntFinding(
            finding_id="hf-2",
            cve_id="CVE-2026-12346",
            affected_component="log4j@2.16.0",
            runtime_evidence="log4j@2.16.0 in service-x",
            severity="MEDIUM",  # below HITL threshold
            proposed_action="monitor",
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
        worker_registry={
            CampaignType.CONTINUOUS_THREAT_HUNTING: ContinuousThreatHuntingWorker()
        },
    )


class TestThreatHunting:
    @pytest.mark.asyncio
    async def test_single_cycle_finds_and_surfaces_critical(
        self,
        configured_orchestrator,
        hunt_definition,
        billing_period,
        critical_cves,
        critical_findings,
    ):
        orch = configured_orchestrator
        await orch.create_campaign(hunt_definition, billing_period)

        hitl = FakeHitl()
        deps = ThreatHuntingDependencies(
            cve_feed=FakeCveFeed(entries=critical_cves),
            telemetry=FakeTelemetry(),
            correlator=FakeCorrelator(findings=critical_findings),
            hitl_gateway=hitl,
            cycle_budget=1,
        )
        board = ThreatHuntingBlackboard()
        extra = {
            CAMPAIGN_DEPS_KEY: deps,
            THREAT_HUNTING_BLACKBOARD_KEY: board,
        }

        for _ in range(15):
            state = await orch.run_next_phase(hunt_definition, phase_extra=extra)
            if state.status.is_terminal:
                break

        assert state.status == CampaignStatus.COMPLETED
        assert board.cycle_count == 1
        assert len(board.findings) == 2
        # Only the CRITICAL one triggered HITL.
        assert len(hitl.requests) == 1
        assert hitl.requests[0].severity == "CRITICAL"

    @pytest.mark.asyncio
    async def test_cycle_budget_caps_polls(
        self,
        configured_orchestrator,
        hunt_definition,
        billing_period,
    ):
        orch = configured_orchestrator
        await orch.create_campaign(hunt_definition, billing_period)

        feed = FakeCveFeed(entries=())  # empty; budget shouldn't matter
        deps = ThreatHuntingDependencies(
            cve_feed=feed,
            telemetry=FakeTelemetry(),
            correlator=FakeCorrelator(findings=()),
            cycle_budget=3,  # should call poll up to 3 times
        )
        board = ThreatHuntingBlackboard()
        extra = {
            CAMPAIGN_DEPS_KEY: deps,
            THREAT_HUNTING_BLACKBOARD_KEY: board,
        }

        for _ in range(15):
            state = await orch.run_next_phase(hunt_definition, phase_extra=extra)
            if state.status.is_terminal:
                break

        assert state.status == CampaignStatus.COMPLETED
        assert feed.calls == 3

    @pytest.mark.asyncio
    async def test_no_deps_stub_run_completes(
        self, configured_orchestrator, hunt_definition, billing_period
    ):
        orch = configured_orchestrator
        await orch.create_campaign(hunt_definition, billing_period)
        for _ in range(15):
            state = await orch.run_next_phase(hunt_definition)
            if state.status.is_terminal:
                break
        assert state.status == CampaignStatus.COMPLETED
