"""
Tests for the Compliance Hardening worker with real (faked) port wiring.

The existing ``test_campaign_manager.py`` covers the orchestrator's
state-machine behaviour against stub phases. This file covers the
*real* phase bodies — exercising each Port via simple in-process
fakes, asserting that:

- Each phase records its typed output on the blackboard.
- LLM cost is recorded on the campaign cost tracker.
- The operation ledger is honoured during patch generation (D2).
- Sandbox failure halts the campaign at PATCH_GENERATION.
- A clean run produces a signed evidence package.
- Idempotent re-runs of patch_generation do not double-spend.
"""

from __future__ import annotations

import asyncio
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
    PhaseOutcome,
)
from src.services.campaign_manager.exceptions import CostCapExceededError
from src.services.campaign_manager.operation_ledger import InMemoryOperationLedger
from src.services.campaign_manager.orchestrator import CampaignOrchestrator
from src.services.campaign_manager.phases._ports import (
    CAMPAIGN_DEPS_KEY,
    ComplianceGap,
    ComplianceHardeningDependencies,
    DeploymentRecord,
    EvidencePackage,
    GapAnalysis,
    GeneratedPatch,
    HitlApprovalRequest,
    RemediationItem,
    RemediationPlan,
    SandboxVerdict,
    ScanFinding,
    ScanReport,
)
from src.services.campaign_manager.phases.compliance_hardening import (
    COMPLIANCE_BLACKBOARD_KEY,
    ComplianceHardeningBlackboard,
    ComplianceHardeningWorker,
)
from src.services.campaign_manager.state_store import InMemoryCampaignStateStore
from src.services.campaign_manager.tenant_cost_rollup import InMemoryTenantCostRollup

# =============================================================================
# Fakes
# =============================================================================


@dataclass
class FakeScanner:
    findings: tuple[ScanFinding, ...] = ()
    input_tokens: int = 250_000
    output_tokens: int = 50_000
    calls: int = 0

    async def baseline_scan(
        self, *, repo_url: str, standard: str, scan_id: str
    ) -> ScanReport:
        self.calls += 1
        return ScanReport(
            scan_id=scan_id,
            findings=self.findings,
            standard=standard,
            files_scanned=42,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


@dataclass
class FakeGapAnalyzer:
    gaps: tuple[ComplianceGap, ...] = ()
    input_tokens: int = 100_000
    output_tokens: int = 30_000

    async def analyze(self, *, report: ScanReport) -> GapAnalysis:
        return GapAnalysis(
            standard=report.standard,
            gaps=self.gaps,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


@dataclass
class FakePlanner:
    items: tuple[RemediationItem, ...] = ()
    input_tokens: int = 60_000
    output_tokens: int = 20_000

    async def plan(self, *, analysis: GapAnalysis) -> RemediationPlan:
        return RemediationPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            items=self.items,
            total_estimated_cost_usd=sum(i.estimated_cost_usd for i in self.items),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


@dataclass
class FakePatchGenerator:
    calls: int = 0
    input_tokens_per_call: int = 40_000
    output_tokens_per_call: int = 15_000

    async def generate(self, *, item: RemediationItem, repo_url: str) -> GeneratedPatch:
        self.calls += 1
        return GeneratedPatch(
            patch_id=f"patch-{item.item_id}",
            remediation_item_id=item.item_id,
            diff=f"--- a/{item.item_id}\n+++ b/{item.item_id}\n",
            files_touched=(f"src/{item.item_id}.py",),
            confidence=0.92,
            input_tokens=self.input_tokens_per_call,
            output_tokens=self.output_tokens_per_call,
        )


@dataclass
class FakeSandboxVerifier:
    pass_all: bool = True
    failing_patch_ids: set = field(default_factory=set)
    cost_per_run: float = 0.05

    async def verify(self, *, patch: GeneratedPatch) -> SandboxVerdict:
        failing = (not self.pass_all) or patch.patch_id in self.failing_patch_ids
        return SandboxVerdict(
            patch_id=patch.patch_id,
            passed=not failing,
            tests_run=24,
            tests_failed=0 if not failing else 3,
            runtime_seconds=42,
            sandbox_cost_usd=self.cost_per_run,
            failure_summary=("" if not failing else "3 unit tests broke"),
        )


@dataclass
class FakeHitlGateway:
    last_request: Optional[HitlApprovalRequest] = None
    ticket_id: str = "ticket-123"

    async def request_approval(self, *, request: HitlApprovalRequest) -> str:
        self.last_request = request
        return self.ticket_id


@dataclass
class FakeDeploymentGate:
    last_deploy: Optional[DeploymentRecord] = None

    async def deploy(
        self,
        *,
        patches: tuple[GeneratedPatch, ...],
        change_ticket_id: str,
    ) -> DeploymentRecord:
        record = DeploymentRecord(
            deployment_id=f"deploy-{uuid.uuid4().hex[:8]}",
            patch_ids=tuple(p.patch_id for p in patches),
            deployed_at=datetime.now(timezone.utc),
            change_ticket_id=change_ticket_id,
        )
        self.last_deploy = record
        return record


@dataclass
class FakeEvidencePackager:
    package_id: str = "evidence-deadbeef"

    async def package(
        self,
        *,
        campaign_id: str,
        tenant_id: str,
        standard: str,
        baseline: ScanReport,
        gaps: GapAnalysis,
        plan: RemediationPlan,
        verdicts: tuple[SandboxVerdict, ...],
        deployment: DeploymentRecord,
    ) -> EvidencePackage:
        return EvidencePackage(
            package_id=self.package_id,
            standard=standard,
            campaign_id=campaign_id,
            tenant_id=tenant_id,
            s3_key=(f"evidence/{tenant_id}/{campaign_id}/{self.package_id}.json"),
            signature="kms-fake-sig",
        )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def tenant_id() -> str:
    return "tenant-acme"


@pytest.fixture()
def billing_period() -> str:
    return "2026-05"


@pytest.fixture()
def compliance_definition(tenant_id) -> CampaignDefinition:
    return CampaignDefinition(
        campaign_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        campaign_type=CampaignType.COMPLIANCE_HARDENING,
        target={"repo": "acme/api"},
        success_criteria={"standard": "NIST-800-53"},
        cost_cap_usd=200.0,
        wall_clock_budget_hours=12.0,
        autonomy_policy_id="policy-conservative",
        hitl_milestones=("hitl_review",),
        approver_quorum=2,
        creator_principal_arn="arn:aws:iam::123:user/alice",
    )


@pytest.fixture()
def realistic_findings() -> tuple[ScanFinding, ...]:
    return (
        ScanFinding(
            finding_id="f1",
            severity="CRITICAL",
            cwe_id="CWE-89",
            file_path="api/auth.py",
            line_start=42,
            line_end=58,
            summary="SQL injection in login()",
            confidence=0.93,
        ),
        ScanFinding(
            finding_id="f2",
            severity="HIGH",
            cwe_id="CWE-79",
            file_path="web/templates.py",
            line_start=12,
            line_end=20,
            summary="Unescaped user input in template rendering",
            confidence=0.81,
        ),
    )


@pytest.fixture()
def realistic_gaps() -> tuple[ComplianceGap, ...]:
    return (
        ComplianceGap(
            control_id="NIST-800-53 SI-10",
            description="Information Input Validation",
            related_finding_ids=("f1", "f2"),
            severity="CRITICAL",
            estimated_effort_usd=100.0,
        ),
    )


@pytest.fixture()
def realistic_plan_items() -> tuple[RemediationItem, ...]:
    return (
        RemediationItem(
            item_id="r1",
            gap_control_id="NIST-800-53 SI-10",
            target_finding_ids=("f1",),
            proposed_change_summary="Parameterize SQL in auth.login()",
            estimated_cost_usd=20.0,
            risk_class="MEDIUM",
        ),
        RemediationItem(
            item_id="r2",
            gap_control_id="NIST-800-53 SI-10",
            target_finding_ids=("f2",),
            proposed_change_summary="Escape user input in templates",
            estimated_cost_usd=15.0,
            risk_class="LOW",
        ),
    )


@pytest.fixture()
def all_real_deps(
    realistic_findings, realistic_gaps, realistic_plan_items
) -> ComplianceHardeningDependencies:
    return ComplianceHardeningDependencies(
        scanner=FakeScanner(findings=realistic_findings),
        gap_analyzer=FakeGapAnalyzer(gaps=realistic_gaps),
        planner=FakePlanner(items=realistic_plan_items),
        patch_generator=FakePatchGenerator(),
        sandbox_verifier=FakeSandboxVerifier(),
        hitl_gateway=FakeHitlGateway(),
        deployment_gate=FakeDeploymentGate(),
        evidence_packager=FakeEvidencePackager(),
        change_ticket_id="CHG-0001",
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
            CampaignType.COMPLIANCE_HARDENING: ComplianceHardeningWorker()
        },
    )


# =============================================================================
# Real-bodies end-to-end
# =============================================================================


class TestComplianceHardeningRealBodies:
    @pytest.mark.asyncio
    async def test_full_run_produces_signed_evidence_package(
        self,
        configured_orchestrator,
        compliance_definition,
        billing_period,
        all_real_deps,
    ):
        orch = configured_orchestrator
        await orch.create_campaign(compliance_definition, billing_period)

        board = ComplianceHardeningBlackboard()
        phase_extra = {
            CAMPAIGN_DEPS_KEY: all_real_deps,
            COMPLIANCE_BLACKBOARD_KEY: board,
        }
        bob = "arn:aws:iam::123:user/bob"
        carol = "arn:aws:iam::123:user/carol"

        for _ in range(40):  # safety bound
            state = await orch.run_next_phase(
                compliance_definition, phase_extra=phase_extra
            )
            if state.status == CampaignStatus.AWAITING_HITL:
                await orch.approve_milestone(
                    compliance_definition, approver_principal_arn=bob
                )
                state = await orch.approve_milestone(
                    compliance_definition, approver_principal_arn=carol
                )
                continue
            if state.status.is_terminal:
                break

        assert state.status == CampaignStatus.COMPLETED
        # Blackboard accumulated typed outputs.
        assert board.baseline_report is not None
        assert len(board.baseline_report.findings) == 2
        assert board.gap_analysis is not None
        assert board.remediation_plan is not None
        assert len(board.patches) == 2
        assert all(v.passed for v in board.verdicts)
        assert board.hitl_ticket_id == "ticket-123"
        assert board.deployment_record is not None
        assert board.deployment_record.change_ticket_id == "CHG-0001"
        assert board.evidence_package is not None
        assert board.evidence_package.signature == "kms-fake-sig"

    @pytest.mark.asyncio
    async def test_llm_cost_is_recorded_against_cap(
        self,
        configured_orchestrator,
        compliance_definition,
        billing_period,
        all_real_deps,
    ):
        orch = configured_orchestrator
        await orch.create_campaign(compliance_definition, billing_period)

        board = ComplianceHardeningBlackboard()
        phase_extra = {
            CAMPAIGN_DEPS_KEY: all_real_deps,
            COMPLIANCE_BLACKBOARD_KEY: board,
        }
        bob = "arn:aws:iam::123:user/bob"
        carol = "arn:aws:iam::123:user/carol"

        for _ in range(40):
            state = await orch.run_next_phase(
                compliance_definition, phase_extra=phase_extra
            )
            if state.status == CampaignStatus.AWAITING_HITL:
                await orch.approve_milestone(
                    compliance_definition, approver_principal_arn=bob
                )
                state = await orch.approve_milestone(
                    compliance_definition, approver_principal_arn=carol
                )
                continue
            if state.status.is_terminal:
                break

        # Every phase that called the LLM should have recorded > 0 cost.
        snapshot = state.cost
        assert snapshot.standard_cost_usd > 0
        # Sandbox cost was recorded too (one per patch).
        assert snapshot.sandbox_cost_usd == pytest.approx(0.10, rel=1e-3)

    @pytest.mark.asyncio
    async def test_sandbox_failure_halts_at_patch_generation(
        self,
        configured_orchestrator,
        compliance_definition,
        billing_period,
        realistic_findings,
        realistic_gaps,
        realistic_plan_items,
    ):
        orch = configured_orchestrator
        await orch.create_campaign(compliance_definition, billing_period)

        deps = ComplianceHardeningDependencies(
            scanner=FakeScanner(findings=realistic_findings),
            gap_analyzer=FakeGapAnalyzer(gaps=realistic_gaps),
            planner=FakePlanner(items=realistic_plan_items),
            patch_generator=FakePatchGenerator(),
            sandbox_verifier=FakeSandboxVerifier(pass_all=False),  # fail
            hitl_gateway=FakeHitlGateway(),
            deployment_gate=FakeDeploymentGate(),
            evidence_packager=FakeEvidencePackager(),
            change_ticket_id="CHG-0001",
        )

        board = ComplianceHardeningBlackboard()
        phase_extra = {
            CAMPAIGN_DEPS_KEY: deps,
            COMPLIANCE_BLACKBOARD_KEY: board,
        }

        for _ in range(20):
            state = await orch.run_next_phase(
                compliance_definition, phase_extra=phase_extra
            )
            if state.status.is_terminal:
                break

        assert state.status == CampaignStatus.FAILED
        # Verdicts captured even on failure.
        assert any(not v.passed for v in board.verdicts)
        # Deployment was never reached.
        assert board.deployment_record is None

    @pytest.mark.asyncio
    async def test_patch_generation_is_idempotent(
        self,
        compliance_definition,
        realistic_findings,
        realistic_gaps,
        realistic_plan_items,
    ):
        # Run the patch_generation phase directly twice against the same
        # operation ledger; the second pass must not re-invoke the
        # patch generator (D2).
        from src.services.campaign_manager.contracts import CampaignState
        from src.services.campaign_manager.cost_tracker import CampaignCostTracker
        from src.services.campaign_manager.phases.compliance_hardening import (
            _PATCH_GENERATION,
            PatchGenerationPhase,
        )

        generator = FakePatchGenerator()
        sandbox = FakeSandboxVerifier()
        deps = ComplianceHardeningDependencies(
            patch_generator=generator,
            sandbox_verifier=sandbox,
        )
        plan = RemediationPlan(
            plan_id="plan-xx",
            items=realistic_plan_items,
            total_estimated_cost_usd=35.0,
        )
        board = ComplianceHardeningBlackboard(remediation_plan=plan)

        ledger = InMemoryOperationLedger()
        phase = PatchGenerationPhase(_PATCH_GENERATION)

        def make_ctx():
            from src.services.campaign_manager.phases.base import PhaseExecutionContext

            return PhaseExecutionContext(
                definition=compliance_definition,
                state=CampaignState(
                    campaign_id=compliance_definition.campaign_id,
                    tenant_id=compliance_definition.tenant_id,
                    status=CampaignStatus.RUNNING,
                    current_phase_id=_PATCH_GENERATION.phase_id,
                ),
                phase=_PATCH_GENERATION,
                cost_tracker=CampaignCostTracker(
                    campaign_id=compliance_definition.campaign_id,
                    cost_cap_usd=200.0,
                ),
                operation_ledger=ledger,
                extra={
                    CAMPAIGN_DEPS_KEY: deps,
                    COMPLIANCE_BLACKBOARD_KEY: board,
                },
            )

        first = await phase.execute(make_ctx())
        assert first.outcome == PhaseOutcome.COMPLETED
        assert generator.calls == 2  # two plan items, two generations

        # Re-run; the ledger says ALREADY_EXECUTED so no new gens.
        second = await phase.execute(make_ctx())
        assert second.outcome == PhaseOutcome.COMPLETED
        assert generator.calls == 2  # unchanged

    @pytest.mark.asyncio
    async def test_hitl_phase_registers_request_when_gateway_wired(
        self,
        compliance_definition,
    ):
        from src.services.campaign_manager.contracts import CampaignState
        from src.services.campaign_manager.cost_tracker import CampaignCostTracker
        from src.services.campaign_manager.phases.base import PhaseExecutionContext
        from src.services.campaign_manager.phases.compliance_hardening import (
            _HITL_REVIEW,
            HitlReviewPhase,
        )

        gateway = FakeHitlGateway(ticket_id="ticket-XYZ")
        deps = ComplianceHardeningDependencies(hitl_gateway=gateway)
        board = ComplianceHardeningBlackboard(
            patches=[
                GeneratedPatch(
                    patch_id="p1",
                    remediation_item_id="r1",
                    diff="",
                    files_touched=(),
                    confidence=1.0,
                )
            ]
        )
        phase = HitlReviewPhase(_HITL_REVIEW)
        ctx = PhaseExecutionContext(
            definition=compliance_definition,
            state=CampaignState(
                campaign_id=compliance_definition.campaign_id,
                tenant_id=compliance_definition.tenant_id,
                status=CampaignStatus.RUNNING,
                current_phase_id=_HITL_REVIEW.phase_id,
            ),
            phase=_HITL_REVIEW,
            cost_tracker=CampaignCostTracker(
                campaign_id=compliance_definition.campaign_id,
                cost_cap_usd=200.0,
            ),
            operation_ledger=InMemoryOperationLedger(),
            extra={
                CAMPAIGN_DEPS_KEY: deps,
                COMPLIANCE_BLACKBOARD_KEY: board,
            },
        )

        result = await phase.execute(ctx)
        assert result.outcome == PhaseOutcome.HITL_PENDING
        assert board.hitl_ticket_id == "ticket-XYZ"
        assert gateway.last_request is not None
        assert "1 patches" in gateway.last_request.artifact_summary

    @pytest.mark.asyncio
    async def test_gap_analysis_fails_when_baseline_missing(
        self, compliance_definition
    ):
        from src.services.campaign_manager.contracts import CampaignState
        from src.services.campaign_manager.cost_tracker import CampaignCostTracker
        from src.services.campaign_manager.phases.base import PhaseExecutionContext
        from src.services.campaign_manager.phases.compliance_hardening import (
            _GAP_ANALYSIS,
            GapAnalysisPhase,
        )

        deps = ComplianceHardeningDependencies(
            gap_analyzer=FakeGapAnalyzer(),  # wired, but board has no baseline
        )
        board = ComplianceHardeningBlackboard()  # empty
        phase = GapAnalysisPhase(_GAP_ANALYSIS)
        ctx = PhaseExecutionContext(
            definition=compliance_definition,
            state=CampaignState(
                campaign_id=compliance_definition.campaign_id,
                tenant_id=compliance_definition.tenant_id,
                status=CampaignStatus.RUNNING,
                current_phase_id=_GAP_ANALYSIS.phase_id,
            ),
            phase=_GAP_ANALYSIS,
            cost_tracker=CampaignCostTracker(
                campaign_id=compliance_definition.campaign_id,
                cost_cap_usd=200.0,
            ),
            operation_ledger=InMemoryOperationLedger(),
            extra={
                CAMPAIGN_DEPS_KEY: deps,
                COMPLIANCE_BLACKBOARD_KEY: board,
            },
        )

        result = await phase.execute(ctx)
        assert result.outcome == PhaseOutcome.FAILED
        assert "baseline_report missing" in result.phase_summary


class TestStubFallbacksUnaffected:
    """Sanity checks that the stub fallback still works when deps absent."""

    @pytest.mark.asyncio
    async def test_no_deps_returns_completed_stub(
        self, configured_orchestrator, compliance_definition, billing_period
    ):
        orch = configured_orchestrator
        await orch.create_campaign(compliance_definition, billing_period)

        bob = "arn:aws:iam::123:user/bob"
        carol = "arn:aws:iam::123:user/carol"
        # No phase_extra passed; phases should run stubs end-to-end.
        for _ in range(40):
            state = await orch.run_next_phase(compliance_definition)
            if state.status == CampaignStatus.AWAITING_HITL:
                await orch.approve_milestone(
                    compliance_definition, approver_principal_arn=bob
                )
                state = await orch.approve_milestone(
                    compliance_definition, approver_principal_arn=carol
                )
                continue
            if state.status.is_terminal:
                break
        assert state.status == CampaignStatus.COMPLETED
