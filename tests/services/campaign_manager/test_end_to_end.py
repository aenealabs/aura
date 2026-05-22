"""
End-to-end integration test for ADR-089: one orchestrator, all six
workers registered, every campaign type runs to its expected terminal
state.

This is the test that justifies the headline claim: Aura's campaign
manager composes the existing primitives into multi-hour autonomous
workloads end-to-end. Phases 1-4 and 6 reach COMPLETED with all
typed outputs on their blackboards; Phase 5 reaches FAILED with the
documented blocked-stub reason (vendor-access-gate, #115).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.services.campaign_manager import (
    CampaignDefinition,
    CampaignStatus,
    CampaignType,
    build_default_worker_registry,
)
from src.services.campaign_manager.checkpoint_store import InMemoryCheckpointStore
from src.services.campaign_manager.operation_ledger import InMemoryOperationLedger
from src.services.campaign_manager.orchestrator import CampaignOrchestrator
from src.services.campaign_manager.phases._ports import (
    CAMPAIGN_DEPS_KEY,
    AdapterPromotionRecord,
    ChainAnalysisDependencies,
    ComplianceGap,
    ComplianceHardeningDependencies,
    CrossRepoEdge,
    CrossRepoGraph,
    CveFeedEntry,
    DeploymentRecord,
    EvalResult,
    EvidencePackage,
    ExploitChain,
    GapAnalysis,
    GeneratedPatch,
    HitlApprovalRequest,
    HuntFinding,
    RemediationItem,
    RemediationPlan,
    RepoRef,
    RuntimeTelemetrySnapshot,
    SandboxVerdict,
    ScanFinding,
    ScanReport,
    SelfPlayTrainingDependencies,
    ThreatHuntingDependencies,
    TrainingCorpusRef,
    TrainingResult,
    VulnerabilityRemediationDependencies,
)
from src.services.campaign_manager.phases.chain_analysis import (
    CHAIN_ANALYSIS_BLACKBOARD_KEY,
    ChainAnalysisBlackboard,
)
from src.services.campaign_manager.phases.compliance_hardening import (
    COMPLIANCE_BLACKBOARD_KEY,
    ComplianceHardeningBlackboard,
)
from src.services.campaign_manager.phases.self_play_training import (
    SELF_PLAY_BLACKBOARD_KEY,
    SelfPlayTrainingBlackboard,
)
from src.services.campaign_manager.phases.threat_hunting import (
    THREAT_HUNTING_BLACKBOARD_KEY,
    ThreatHuntingBlackboard,
)
from src.services.campaign_manager.phases.vulnerability_remediation import (
    VULN_REMEDIATION_BLACKBOARD_KEY,
    VulnerabilityRemediationBlackboard,
)
from src.services.campaign_manager.state_store import InMemoryCampaignStateStore
from src.services.campaign_manager.tenant_cost_rollup import InMemoryTenantCostRollup

# -----------------------------------------------------------------------------
# Composable fakes (one per port type, kept tiny on purpose).
# -----------------------------------------------------------------------------


class _SyntheticScanner:
    """Returns N findings on first call; empty on subsequent calls.

    Lets Phase 2 (vuln-remediation) demonstrate a clean post-deploy
    rescan, and lets Phase 1 surface synthetic findings for the
    compliance flow.
    """

    def __init__(self, n_findings: int = 2):
        self.n_findings = n_findings
        self.calls = 0

    async def baseline_scan(self, *, repo_url, standard, scan_id):
        self.calls += 1
        if self.calls > 1:
            return ScanReport(
                scan_id=scan_id,
                findings=(),
                standard=standard,
                files_scanned=50,
                input_tokens=10_000,
                output_tokens=2_000,
            )
        return ScanReport(
            scan_id=scan_id,
            findings=tuple(
                ScanFinding(
                    finding_id=f"f-{i}",
                    severity="CRITICAL" if i == 0 else "HIGH",
                    cwe_id=f"CWE-{89 + i}",
                    file_path=f"src/mod_{i}.py",
                    line_start=10,
                    line_end=20,
                    summary=f"synthetic finding {i}",
                    confidence=0.9,
                )
                for i in range(self.n_findings)
            ),
            standard=standard,
            files_scanned=50,
            input_tokens=200_000,
            output_tokens=40_000,
        )


class _GapAnalyzer:
    async def analyze(self, *, report):
        return GapAnalysis(
            standard=report.standard,
            gaps=(
                ComplianceGap(
                    control_id="NIST-800-53 SI-10",
                    description="Input Validation",
                    related_finding_ids=tuple(f.finding_id for f in report.findings),
                    severity="HIGH",
                    estimated_effort_usd=50.0,
                ),
            ),
            input_tokens=80_000,
            output_tokens=20_000,
        )


class _Planner:
    async def plan(self, *, analysis):
        items = tuple(
            RemediationItem(
                item_id=f"item-{g.control_id}",
                gap_control_id=g.control_id,
                target_finding_ids=g.related_finding_ids,
                proposed_change_summary=f"fix {g.control_id}",
                estimated_cost_usd=20.0,
                risk_class="MEDIUM",
            )
            for g in analysis.gaps
        )
        return RemediationPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            items=items,
            total_estimated_cost_usd=sum(i.estimated_cost_usd for i in items),
            input_tokens=40_000,
            output_tokens=15_000,
        )


class _PatchGen:
    async def generate(self, *, item, repo_url):
        return GeneratedPatch(
            patch_id=f"patch-{item.item_id}",
            remediation_item_id=item.item_id,
            diff="",
            files_touched=(f"src/{item.item_id}.py",),
            confidence=0.92,
            input_tokens=30_000,
            output_tokens=8_000,
        )


class _Sandbox:
    async def verify(self, *, patch):
        return SandboxVerdict(
            patch_id=patch.patch_id,
            passed=True,
            tests_run=20,
            tests_failed=0,
            runtime_seconds=30,
            sandbox_cost_usd=0.05,
        )


class _Hitl:
    def __init__(self):
        self.requests: list[HitlApprovalRequest] = []

    async def request_approval(self, *, request):
        self.requests.append(request)
        return f"ticket-{len(self.requests)}"


class _Deploy:
    async def deploy(self, *, patches, change_ticket_id):
        return DeploymentRecord(
            deployment_id=f"d-{uuid.uuid4().hex[:6]}",
            patch_ids=tuple(p.patch_id for p in patches),
            deployed_at=datetime.now(timezone.utc),
            change_ticket_id=change_ticket_id,
        )


class _Evidence:
    async def package(
        self,
        *,
        campaign_id,
        tenant_id,
        standard,
        baseline,
        gaps,
        plan,
        verdicts,
        deployment,
    ):
        return EvidencePackage(
            package_id=f"ev-{uuid.uuid4().hex[:8]}",
            standard=standard,
            campaign_id=campaign_id,
            tenant_id=tenant_id,
            s3_key=f"evidence/{tenant_id}/{campaign_id}/pkg.json",
            signature="kms-test",
        )


# -----------------------------------------------------------------------------
# End-to-end multi-campaign harness
# -----------------------------------------------------------------------------


@pytest.fixture()
def tenant_id() -> str:
    return "tenant-e2e"


@pytest.fixture()
def billing_period() -> str:
    return "2026-05"


@pytest.fixture()
async def orchestrator(tenant_id, billing_period) -> CampaignOrchestrator:
    rollup = InMemoryTenantCostRollup()
    await rollup.set_cap(tenant_id, billing_period, cap_usd=100_000.0)
    return CampaignOrchestrator(
        state_store=InMemoryCampaignStateStore(),
        checkpoint_store=InMemoryCheckpointStore(),
        operation_ledger=InMemoryOperationLedger(),
        tenant_rollup=rollup,
        worker_registry=build_default_worker_registry(),
    )


async def _drive(
    orch: CampaignOrchestrator,
    definition: CampaignDefinition,
    *,
    phase_extra=None,
    auto_approvers=("arn:aws:iam::123:user/bob", "arn:aws:iam::123:user/carol"),
    safety_bound: int = 50,
):
    """Run a campaign to its terminal state, auto-approving every milestone."""
    quorum = definition.approver_quorum
    for _ in range(safety_bound):
        state = await orch.run_next_phase(definition, phase_extra=phase_extra)
        if state.status == CampaignStatus.AWAITING_HITL:
            for approver in auto_approvers[:quorum]:
                state = await orch.approve_milestone(
                    definition, approver_principal_arn=approver
                )
            continue
        if state.status.is_terminal:
            return state
    raise AssertionError(
        f"Campaign {definition.campaign_id} did not terminate within "
        f"{safety_bound} iterations; last status={state.status.value}"
    )


class TestEndToEndAllSixCampaignTypes:
    @pytest.mark.asyncio
    async def test_compliance_hardening_completes(
        self, orchestrator, tenant_id, billing_period
    ):
        definition = CampaignDefinition(
            campaign_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            campaign_type=CampaignType.COMPLIANCE_HARDENING,
            target={"repo": "e2e/api"},
            success_criteria={"standard": "NIST-800-53"},
            cost_cap_usd=500.0,
            wall_clock_budget_hours=12.0,
            autonomy_policy_id="policy-conservative",
            hitl_milestones=("hitl_review",),
            approver_quorum=2,
            creator_principal_arn="arn:aws:iam::123:user/alice",
        )
        await orchestrator.create_campaign(definition, billing_period)
        board = ComplianceHardeningBlackboard()
        deps = ComplianceHardeningDependencies(
            scanner=_SyntheticScanner(n_findings=2),
            gap_analyzer=_GapAnalyzer(),
            planner=_Planner(),
            patch_generator=_PatchGen(),
            sandbox_verifier=_Sandbox(),
            hitl_gateway=_Hitl(),
            deployment_gate=_Deploy(),
            evidence_packager=_Evidence(),
            change_ticket_id="CHG-E2E-1",
        )
        state = await _drive(
            orchestrator,
            definition,
            phase_extra={
                CAMPAIGN_DEPS_KEY: deps,
                COMPLIANCE_BLACKBOARD_KEY: board,
            },
        )
        assert state.status == CampaignStatus.COMPLETED
        assert board.evidence_package is not None
        assert board.evidence_package.signature == "kms-test"

    @pytest.mark.asyncio
    async def test_vulnerability_remediation_completes(
        self, orchestrator, tenant_id, billing_period
    ):
        definition = CampaignDefinition(
            campaign_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            campaign_type=CampaignType.VULNERABILITY_REMEDIATION,
            target={"repo": "e2e/api"},
            success_criteria={"goal": "ch_to_zero"},
            cost_cap_usd=500.0,
            wall_clock_budget_hours=6.0,
            autonomy_policy_id="policy-standard",
            hitl_milestones=("hitl_review",),
            approver_quorum=1,
            creator_principal_arn="arn:aws:iam::123:user/alice",
        )
        await orchestrator.create_campaign(definition, billing_period)
        board = VulnerabilityRemediationBlackboard()
        deps = VulnerabilityRemediationDependencies(
            scanner=_SyntheticScanner(n_findings=2),
            patch_generator=_PatchGen(),
            sandbox_verifier=_Sandbox(),
            hitl_gateway=_Hitl(),
            deployment_gate=_Deploy(),
            change_ticket_id="CHG-E2E-2",
        )
        state = await _drive(
            orchestrator,
            definition,
            phase_extra={
                CAMPAIGN_DEPS_KEY: deps,
                VULN_REMEDIATION_BLACKBOARD_KEY: board,
            },
        )
        assert state.status == CampaignStatus.COMPLETED
        assert board.remaining_critical_high == 0
        assert len(board.patches) == 2

    @pytest.mark.asyncio
    async def test_chain_analysis_completes(
        self, orchestrator, tenant_id, billing_period
    ):
        class _RepoDisco:
            async def discover(self, *, fleet_target):
                return (
                    RepoRef(repo_id="r1", url="acme/a", primary_language="py"),
                    RepoRef(repo_id="r2", url="acme/b", primary_language="go"),
                )

        class _GraphBuild:
            async def build(self, *, repos):
                return CrossRepoGraph(
                    repos=repos,
                    edges=(),
                    input_tokens=50_000,
                    output_tokens=10_000,
                )

        class _PathSearch:
            async def search(self, *, graph):
                return (
                    ExploitChain(
                        chain_id="chain-1",
                        edges=(
                            CrossRepoEdge(
                                source_repo_id="r1",
                                source_symbol="a:login",
                                sink_repo_id="r2",
                                sink_symbol="b:exec",
                                edge_type="rpc",
                                confidence=0.85,
                            ),
                        ),
                        estimated_impact="CRITICAL",
                        cwe_ids=("CWE-89",),
                        confidence=0.85,
                    ),
                )

        definition = CampaignDefinition(
            campaign_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            campaign_type=CampaignType.CROSS_REPO_CHAIN_ANALYSIS,
            target={"fleet": "e2e-fleet"},
            success_criteria={"goal": "find_chains"},
            cost_cap_usd=300.0,
            wall_clock_budget_hours=8.0,
            autonomy_policy_id="policy-standard",
            hitl_milestones=("hitl_review",),
            approver_quorum=1,
            creator_principal_arn="arn:aws:iam::123:user/alice",
        )
        await orchestrator.create_campaign(definition, billing_period)
        board = ChainAnalysisBlackboard()
        deps = ChainAnalysisDependencies(
            repo_discovery=_RepoDisco(),
            graph_builder=_GraphBuild(),
            path_search=_PathSearch(),
            hitl_gateway=_Hitl(),
        )
        state = await _drive(
            orchestrator,
            definition,
            phase_extra={
                CAMPAIGN_DEPS_KEY: deps,
                CHAIN_ANALYSIS_BLACKBOARD_KEY: board,
            },
        )
        assert state.status == CampaignStatus.COMPLETED
        assert len(board.chains) == 1

    @pytest.mark.asyncio
    async def test_threat_hunting_completes(
        self, orchestrator, tenant_id, billing_period
    ):
        class _Feed:
            async def poll(self, *, since):
                return (
                    CveFeedEntry(
                        cve_id="CVE-2026-E2E",
                        published_at=datetime.now(timezone.utc),
                        affected_components=("svc-x@1.0",),
                        severity="CRITICAL",
                        summary="e2e cve",
                    ),
                )

        class _Tel:
            async def snapshot(self):
                return RuntimeTelemetrySnapshot(
                    captured_at=datetime.now(timezone.utc),
                    components_in_use=("svc-x@1.0",),
                )

        class _Corr:
            async def correlate(self, *, cves, telemetry):
                return (
                    HuntFinding(
                        finding_id="hf-1",
                        cve_id=cves[0].cve_id,
                        affected_component=cves[0].affected_components[0],
                        runtime_evidence="seen",
                        severity="CRITICAL",
                        proposed_action="patch",
                    ),
                )

        definition = CampaignDefinition(
            campaign_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            campaign_type=CampaignType.CONTINUOUS_THREAT_HUNTING,
            target={"fleet": "e2e"},
            success_criteria={"goal": "watch"},
            cost_cap_usd=100.0,
            wall_clock_budget_hours=1.0,
            autonomy_policy_id="policy-standard",
            hitl_milestones=(),
            approver_quorum=1,
            creator_principal_arn="arn:aws:iam::123:user/alice",
        )
        await orchestrator.create_campaign(definition, billing_period)
        board = ThreatHuntingBlackboard()
        deps = ThreatHuntingDependencies(
            cve_feed=_Feed(),
            telemetry=_Tel(),
            correlator=_Corr(),
            hitl_gateway=_Hitl(),
        )
        state = await _drive(
            orchestrator,
            definition,
            phase_extra={
                CAMPAIGN_DEPS_KEY: deps,
                THREAT_HUNTING_BLACKBOARD_KEY: board,
            },
        )
        assert state.status == CampaignStatus.COMPLETED
        assert board.cycle_count == 1
        assert len(board.findings) == 1

    @pytest.mark.asyncio
    async def test_self_play_training_completes(
        self, orchestrator, tenant_id, billing_period
    ):
        class _Curator:
            async def curate(self, *, domain):
                return TrainingCorpusRef(
                    corpus_id="c1",
                    s3_uri="s3://x",
                    sample_count=100,
                    domain=domain,
                )

        class _DR:
            async def run(self, *, corpus, episode_budget):
                return TrainingResult(
                    run_id="r1",
                    episodes=(),
                    attacker_win_rate=0.5,
                    defender_win_rate=0.5,
                )

        class _Ev:
            async def evaluate(self, *, training):
                return EvalResult(
                    eval_id="e1",
                    pass_rate=0.91,
                    regressions=(),
                    promotion_recommended=True,
                )

        class _Pr:
            async def promote(self, *, eval_result):
                return AdapterPromotionRecord(
                    adapter_id="a1",
                    promoted=True,
                    reason="clean eval",
                )

        definition = CampaignDefinition(
            campaign_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            campaign_type=CampaignType.SELF_PLAY_SECURITY_TRAINING,
            target={"domain": "sec"},
            success_criteria={"goal": "promote"},
            cost_cap_usd=1000.0,
            wall_clock_budget_hours=24.0,
            autonomy_policy_id="policy-research",
            hitl_milestones=("hitl_review",),
            approver_quorum=1,
            creator_principal_arn="arn:aws:iam::123:user/alice",
        )
        await orchestrator.create_campaign(definition, billing_period)
        board = SelfPlayTrainingBlackboard()
        deps = SelfPlayTrainingDependencies(
            corpus_curator=_Curator(),
            dual_role=_DR(),
            evaluator=_Ev(),
            promoter=_Pr(),
            hitl_gateway=_Hitl(),
        )
        state = await _drive(
            orchestrator,
            definition,
            phase_extra={
                CAMPAIGN_DEPS_KEY: deps,
                SELF_PLAY_BLACKBOARD_KEY: board,
            },
        )
        assert state.status == CampaignStatus.COMPLETED
        assert board.promotion is not None
        assert board.promotion.promoted is True

    @pytest.mark.asyncio
    async def test_mythos_terminates_failed_with_blocked_reason(
        self, orchestrator, tenant_id, billing_period
    ):
        definition = CampaignDefinition(
            campaign_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            campaign_type=CampaignType.MYTHOS_EXPLOIT_REFINEMENT,
            target={"finding_id": "f-1"},
            success_criteria={"goal": "poc"},
            cost_cap_usd=200.0,
            wall_clock_budget_hours=4.0,
            autonomy_policy_id="policy-mythos",
            hitl_milestones=(),
            approver_quorum=2,
            creator_principal_arn="arn:aws:iam::123:user/alice",
        )
        await orchestrator.create_campaign(definition, billing_period)
        state = await _drive(orchestrator, definition)
        assert state.status == CampaignStatus.FAILED
