"""Regression tests for issue #214 blocking bugs (Jake review of PR #208).

Each test exercises one of the five blocking-correctness bugs the
three-agent design review surfaced. Tests must FAIL against the
pre-fix code and PASS against the fixed code.

  - B1: D2 idempotency -- patch retry drops already-claimed work.
  - B2: approve_milestone assumes HITL is its own phase.
  - B3: Sandbox failure prevents retry (attempt-counter in op_id).
  - B4: Cost tracker hardcodes STANDARD + ADVANCED.
  - B5: Cost-cap exhaustion path skips checkpoint write.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import pytest

from src.services.campaign_manager.checkpoint_store import InMemoryCheckpointStore
from src.services.campaign_manager.contracts import (
    CampaignDefinition,
    CampaignPhase,
    CampaignStatus,
    CampaignType,
    CompletedPhaseRef,
    OperationOutcome,
    OperationStatus,
    PhaseOutcome,
)
from src.services.campaign_manager.cost_tracker import (
    CampaignCostTracker,
    _PerTierUsage,
)
from src.services.campaign_manager.exceptions import (
    CostCapExceededError,
    SeparationOfDutiesError,
)
from src.services.campaign_manager.operation_ledger import InMemoryOperationLedger
from src.services.campaign_manager.orchestrator import CampaignOrchestrator
from src.services.campaign_manager.phases._ports import (
    CAMPAIGN_DEPS_KEY,
    ComplianceHardeningDependencies,
    DeploymentRecord,
    GeneratedPatch,
    HitlApprovalRequest,
    RemediationItem,
    RemediationPlan,
    SandboxVerdict,
    ScanFinding,
    ScanReport,
)
from src.services.campaign_manager.phases.base import (
    CampaignWorker,
    Phase,
    PhaseExecutionContext,
    PhaseResult,
)
from src.services.campaign_manager.phases.compliance_hardening import (
    _PATCH_GENERATION,
    COMPLIANCE_BLACKBOARD_KEY,
    ComplianceHardeningBlackboard,
    ComplianceHardeningWorker,
    PatchGenerationPhase,
)
from src.services.campaign_manager.state_store import InMemoryCampaignStateStore
from src.services.campaign_manager.tenant_cost_rollup import InMemoryTenantCostRollup
from src.services.vulnerability_scanner.analysis.capability import ModelCapabilityTier

# =============================================================================
# Shared fixtures + fakes
# =============================================================================


@pytest.fixture()
def tenant_id() -> str:
    return "tenant-bugs"


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


@dataclass
class _PatchGen:
    calls: int = 0

    async def generate(self, *, item: RemediationItem, repo_url: str) -> GeneratedPatch:
        self.calls += 1
        return GeneratedPatch(
            patch_id=f"p-{item.item_id}",
            remediation_item_id=item.item_id,
            diff="--- a/x\n+++ b/x\n",
            files_touched=("src/x.py",),
            confidence=0.9,
        )


@dataclass
class _Sandbox:
    passed: bool = True

    async def verify(self, *, patch: GeneratedPatch) -> SandboxVerdict:
        return SandboxVerdict(
            patch_id=patch.patch_id,
            passed=self.passed,
            tests_run=10,
            tests_failed=0 if self.passed else 2,
            runtime_seconds=12,
            sandbox_cost_usd=0.01,
        )


def _make_context(
    *,
    definition: CampaignDefinition,
    deps: ComplianceHardeningDependencies,
    board: ComplianceHardeningBlackboard,
    ledger: InMemoryOperationLedger,
    phase_history: tuple[CompletedPhaseRef, ...] = (),
) -> PhaseExecutionContext:
    from src.services.campaign_manager.contracts import CampaignState

    state = CampaignState(
        campaign_id=definition.campaign_id,
        tenant_id=definition.tenant_id,
        status=CampaignStatus.RUNNING,
        current_phase_id=_PATCH_GENERATION.phase_id,
        phase_history=phase_history,
    )
    return PhaseExecutionContext(
        definition=definition,
        state=state,
        phase=_PATCH_GENERATION,
        cost_tracker=CampaignCostTracker(
            campaign_id=definition.campaign_id,
            cost_cap_usd=200.0,
        ),
        operation_ledger=ledger,
        extra={
            CAMPAIGN_DEPS_KEY: deps,
            COMPLIANCE_BLACKBOARD_KEY: board,
        },
    )


# =============================================================================
# B1: D2 idempotency -- re-hydrate blackboard from prior_outcome payload
# =============================================================================


class TestB1IdempotentRehydration:
    @pytest.mark.asyncio
    async def test_rerun_rehydrates_patches_from_prior_outcome(
        self, compliance_definition
    ):
        """First run records ops; on retry within the same attempt, the
        blackboard is empty but the ledger holds the prior outcomes.
        The phase must re-hydrate ``board.patches`` and ``board.verdicts``
        from ``prior_outcome.payload`` so downstream phases see the
        patch set."""
        gen = _PatchGen()
        sandbox = _Sandbox()
        deps = ComplianceHardeningDependencies(
            patch_generator=gen, sandbox_verifier=sandbox
        )
        plan = RemediationPlan(
            plan_id="plan-1",
            items=(
                RemediationItem(
                    item_id="r1",
                    gap_control_id="ctrl-1",
                    target_finding_ids=("f1",),
                    proposed_change_summary="fix r1",
                    estimated_cost_usd=1.0,
                    risk_class="LOW",
                ),
                RemediationItem(
                    item_id="r2",
                    gap_control_id="ctrl-1",
                    target_finding_ids=("f2",),
                    proposed_change_summary="fix r2",
                    estimated_cost_usd=1.0,
                    risk_class="LOW",
                ),
            ),
            total_estimated_cost_usd=2.0,
        )
        ledger = InMemoryOperationLedger()
        phase = PatchGenerationPhase(_PATCH_GENERATION)

        # First run: generates two patches; ledger has two outcomes.
        board_run1 = ComplianceHardeningBlackboard(remediation_plan=plan)
        ctx_run1 = _make_context(
            definition=compliance_definition,
            deps=deps,
            board=board_run1,
            ledger=ledger,
        )
        result1 = await phase.execute(ctx_run1)
        assert result1.outcome == PhaseOutcome.COMPLETED
        assert len(board_run1.patches) == 2
        assert gen.calls == 2

        # Simulate a process crash + retry with a FRESH blackboard.
        # The ledger has prior outcomes; the phase must re-hydrate.
        board_run2 = ComplianceHardeningBlackboard(remediation_plan=plan)
        ctx_run2 = _make_context(
            definition=compliance_definition,
            deps=deps,
            board=board_run2,
            ledger=ledger,
        )
        result2 = await phase.execute(ctx_run2)
        # Generator must NOT be called again (idempotency).
        assert gen.calls == 2
        # But the blackboard must be re-hydrated.
        assert len(board_run2.patches) == 2
        assert len(board_run2.verdicts) == 2
        assert {p.patch_id for p in board_run2.patches} == {"p-r1", "p-r2"}
        assert result2.outcome == PhaseOutcome.COMPLETED


# =============================================================================
# B2: approve_milestone assumes HITL is its own phase
# =============================================================================


class _NonMilestonePhaseEmittingHitl(Phase):
    """Worker that wrongly emits HITL_PENDING from a non-milestone phase."""

    criterion_id = "x"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        return PhaseResult(
            outcome=PhaseOutcome.HITL_PENDING,
            phase_summary="erroneous HITL from non-milestone phase",
        )


class _BadHitlWorker(CampaignWorker):
    """Worker with a phase that emits HITL_PENDING despite is_milestone=False."""

    _PHASE_DEF = CampaignPhase(
        phase_id="bad_hitl_phase",
        label="Bad HITL emitter",
        order=0,
        is_milestone=False,
    )
    _PHASE_GRAPH = (_NonMilestonePhaseEmittingHitl(_PHASE_DEF),)

    @property
    def campaign_type(self) -> CampaignType:
        return CampaignType.VULNERABILITY_REMEDIATION  # not HIGH_IMPACT

    def phase_graph(self) -> tuple[Phase, ...]:
        return self._PHASE_GRAPH


class TestB2ApprovalMilestoneAssertion:
    @pytest.mark.asyncio
    async def test_approve_milestone_rejects_non_milestone_phase(
        self, tenant_id, billing_period
    ):
        rollup = InMemoryTenantCostRollup()
        await rollup.set_cap(tenant_id, billing_period, cap_usd=10_000.0)
        orch = CampaignOrchestrator(
            state_store=InMemoryCampaignStateStore(),
            checkpoint_store=InMemoryCheckpointStore(),
            operation_ledger=InMemoryOperationLedger(),
            tenant_rollup=rollup,
            worker_registry={CampaignType.VULNERABILITY_REMEDIATION: _BadHitlWorker()},
        )
        definition = CampaignDefinition(
            campaign_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            campaign_type=CampaignType.VULNERABILITY_REMEDIATION,
            target={"repo": "x"},
            success_criteria={"goal": "x"},
            cost_cap_usd=100.0,
            wall_clock_budget_hours=1.0,
            autonomy_policy_id="p",
            hitl_milestones=("bad_hitl_phase",),
            approver_quorum=1,
            creator_principal_arn="arn:aws:iam::123:user/alice",
        )
        await orch.create_campaign(definition, billing_period)
        state = await orch.run_next_phase(definition)
        # Worker erroneously emitted HITL_PENDING from a non-milestone.
        assert state.status == CampaignStatus.AWAITING_HITL

        # Approval must fail loudly instead of silently skipping work.
        with pytest.raises(SeparationOfDutiesError, match="is_milestone"):
            await orch.approve_milestone(
                definition,
                approver_principal_arn="arn:aws:iam::123:user/bob",
            )


# =============================================================================
# B3: Sandbox failure prevents retry -- attempt counter in op_id
# =============================================================================


class TestB3AttemptCounterInOpId:
    @pytest.mark.asyncio
    async def test_attempt_counter_advances_on_prior_phase_failure(
        self, compliance_definition
    ):
        """If the phase has failed once already (phase_history records
        FAILED), the next invocation must use a fresh attempt counter
        so previously sandbox-failed patches are eligible for retry."""
        gen = _PatchGen()
        sandbox = _Sandbox(passed=True)
        deps = ComplianceHardeningDependencies(
            patch_generator=gen, sandbox_verifier=sandbox
        )
        plan = RemediationPlan(
            plan_id="plan-2",
            items=(
                RemediationItem(
                    item_id="r1",
                    gap_control_id="c",
                    target_finding_ids=(),
                    proposed_change_summary="",
                    estimated_cost_usd=1.0,
                    risk_class="LOW",
                ),
            ),
            total_estimated_cost_usd=1.0,
        )
        ledger = InMemoryOperationLedger()
        phase = PatchGenerationPhase(_PATCH_GENERATION)

        # Attempt 1: claim patch:r1:attempt-1 and record a failed outcome.
        await ledger.claim(
            compliance_definition.tenant_id,
            compliance_definition.campaign_id,
            _PATCH_GENERATION.phase_id,
            "patch:r1:attempt-1",
        )
        await ledger.record_outcome(
            compliance_definition.tenant_id,
            compliance_definition.campaign_id,
            _PATCH_GENERATION.phase_id,
            "patch:r1:attempt-1",
            OperationOutcome(success=False, summary="sandbox failed"),
        )

        # Attempt 2: phase_history records a prior FAILED. Phase should
        # use attempt-2 op id (fresh) and regenerate the patch.
        history = (
            CompletedPhaseRef(
                phase_id=_PATCH_GENERATION.phase_id,
                checkpoint_s3_key="cp-1",
                outcome=PhaseOutcome.FAILED,
                duration_seconds=5,
            ),
        )
        board = ComplianceHardeningBlackboard(remediation_plan=plan)
        ctx = _make_context(
            definition=compliance_definition,
            deps=deps,
            board=board,
            ledger=ledger,
            phase_history=history,
        )
        result = await phase.execute(ctx)
        # Generator was called for the new attempt; patch landed.
        assert gen.calls == 1
        assert result.outcome == PhaseOutcome.COMPLETED
        assert len(board.patches) == 1

        # The attempt-1 op id is still marked failed (prior outcome).
        claim_attempt1 = await ledger.claim(
            compliance_definition.tenant_id,
            compliance_definition.campaign_id,
            _PATCH_GENERATION.phase_id,
            "patch:r1:attempt-1",
        )
        assert claim_attempt1.status == OperationStatus.ALREADY_EXECUTED
        assert claim_attempt1.prior_outcome.success is False


# =============================================================================
# B4: Cost tracker hardcodes STANDARD + ADVANCED
# =============================================================================


class TestB4CostTrackerAllTiers:
    def test_total_cost_sums_every_configured_tier(self):
        """A synthetic 3rd tier injected into _tier_usage must count
        toward both the cap check and the snapshot total."""
        tracker = CampaignCostTracker(campaign_id="c1", cost_cap_usd=100.0)

        # Synthetic 3rd tier (Mythos / Premium placeholder). Hijack the
        # ADVANCED tier slot conceptually -- we'll spike its usage and
        # also add a deliberately misnamed sentinel to verify the sum.
        class _SentinelTier:
            name = "SENTINEL"

        sentinel = _SentinelTier()
        tracker._tier_usage[sentinel] = _PerTierUsage(  # type: ignore[index]
            invocations=1, input_tokens=0, output_tokens=0, cost_usd=60.0
        )

        # Cap check must now reflect the sentinel's spend.
        assert tracker.total_cost_usd == pytest.approx(60.0)

        # Snapshot total must also include it (back-compat std/adv fields
        # stay at their named values, but total_cost_usd is the truth).
        snap = tracker.snapshot()
        assert snap.total_cost_usd == pytest.approx(60.0)

        # Cap enforcement: with $60 used + sentinel + headroom $35 (after
        # 5% reservation on $100), a $40 STANDARD spend should blow the cap.
        with pytest.raises(CostCapExceededError):
            tracker.record(ModelCapabilityTier.STANDARD, 14_000_000, 0)  # ~$42


# =============================================================================
# B5: Cost-cap path must write a checkpoint before terminal transition
# =============================================================================


class _CapBlowingPhase(Phase):
    """Phase that records some cost successfully, then blows the cap.

    Mirrors the realistic shape that motivates B5: a phase that has
    already done partial work when the cap halts it. The first
    record() commits; the second raises CostCapExceededError. The
    checkpoint must reflect the committed cost so the partial work
    is not lost.
    """

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        # First record commits successfully (small spike, within cap).
        context.cost_tracker.record(ModelCapabilityTier.STANDARD, 100_000, 0)
        # Second record blows the cap.
        context.cost_tracker.record(ModelCapabilityTier.STANDARD, 50_000_000, 0)
        return PhaseResult(outcome=PhaseOutcome.COMPLETED)


class _SmallCapWorker(CampaignWorker):
    _PHASE_DEF = CampaignPhase(
        phase_id="cap_blow",
        label="Cap blower",
        order=0,
    )
    _PHASE_GRAPH = (_CapBlowingPhase(_PHASE_DEF),)

    @property
    def campaign_type(self) -> CampaignType:
        return CampaignType.VULNERABILITY_REMEDIATION

    def phase_graph(self) -> tuple[Phase, ...]:
        return self._PHASE_GRAPH


class TestB5CapHaltCheckpoint:
    @pytest.mark.asyncio
    async def test_cap_halt_writes_checkpoint(self, tenant_id, billing_period):
        rollup = InMemoryTenantCostRollup()
        await rollup.set_cap(tenant_id, billing_period, cap_usd=10_000.0)
        checkpoint_store = InMemoryCheckpointStore()
        orch = CampaignOrchestrator(
            state_store=InMemoryCampaignStateStore(),
            checkpoint_store=checkpoint_store,
            operation_ledger=InMemoryOperationLedger(),
            tenant_rollup=rollup,
            worker_registry={CampaignType.VULNERABILITY_REMEDIATION: _SmallCapWorker()},
        )
        definition = CampaignDefinition(
            campaign_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            campaign_type=CampaignType.VULNERABILITY_REMEDIATION,
            target={"x": "y"},
            success_criteria={"goal": "z"},
            cost_cap_usd=1.0,  # very small -- the phase will blow it
            wall_clock_budget_hours=1.0,
            autonomy_policy_id="p",
            hitl_milestones=(),
            approver_quorum=1,
            creator_principal_arn="arn:aws:iam::123:user/alice",
        )
        await orch.create_campaign(definition, billing_period)
        state = await orch.run_next_phase(definition)
        # Campaign halted at cap, terminal.
        assert state.status == CampaignStatus.HALTED_AT_CAP

        # Checkpoint must have been written (#214-B5 fix).
        cp = await checkpoint_store.read(definition.campaign_id, "cap_blow")
        assert cp is not None
        assert "Halted at cap" in cp.phase_summary
        # Cost snapshot must reflect the spike that caused the halt.
        assert cp.cost_counters.standard_cost_usd > 0
