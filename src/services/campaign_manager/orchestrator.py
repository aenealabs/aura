"""
Project Aura - Campaign Orchestrator.

Drives the campaign state machine: validate definition, run phases in
order, persist checkpoints at phase boundaries, enforce cost caps at
the per-call interceptor, gate progression on HITL milestones,
detect drift and re-anchor.

Designed so the same logic runs in-process (used by the unit tests
and local development) AND under AWS Step Functions Standard
Workflows (the production substrate per D1). The orchestrator does
not own the workflow runtime — it owns the *domain* transitions and
delegates durability to its substrate.

Implements ADR-089.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional

from .checkpoint_store import CheckpointStore
from .contracts import (
    ArtifactRef,
    CampaignDefinition,
    CampaignOutcome,
    CampaignState,
    CampaignStatus,
    CompletedPhaseRef,
    HIGH_IMPACT_CAMPAIGN_TYPES,
    HitlMilestone,
    PhaseCheckpoint,
    PhaseOutcome,
    SuccessCriteriaProgress,
)
from .cost_tracker import CampaignCostTracker
from .exceptions import (
    CostCapExceededError,
    InvalidCampaignDefinitionError,
    SeparationOfDutiesError,
    TenantCostCapExceededError,
)
from .operation_ledger import OperationLedger
from .phases.base import (
    CampaignWorker,
    Phase,
    PhaseExecutionContext,
    PhaseResult,
)
from .state_store import CampaignStateStore
from .tenant_cost_rollup import TenantCostRollup

logger = logging.getLogger(__name__)


class CampaignOrchestrator:
    """Drives campaigns through their phase graphs.

    Composition root. Constructed once per environment with the four
    persistence abstractions; the campaign API and Step Functions
    workers both call into this object.

    Lifecycle:
        1. ``create_campaign(definition)`` validates and persists the
           definition; returns a CREATED state.
        2. ``run_next_phase(campaign_id)`` runs whichever phase the
           state machine should run next; returns the post-execution
           state.
        3. The API or SFN polls ``run_next_phase`` until the campaign
           reaches a terminal status, with HITL pauses surfacing as
           ``CampaignStatus.AWAITING_HITL``.

    Threading: every public method is async. The persistence stores
    handle their own concurrency control.
    """

    def __init__(
        self,
        state_store: CampaignStateStore,
        checkpoint_store: CheckpointStore,
        operation_ledger: OperationLedger,
        tenant_rollup: TenantCostRollup,
        worker_registry: dict,
    ) -> None:
        self._state_store = state_store
        self._checkpoint_store = checkpoint_store
        self._operation_ledger = operation_ledger
        self._tenant_rollup = tenant_rollup
        self._workers: dict = worker_registry  # CampaignType -> CampaignWorker
        # Per-campaign cost trackers. Indexed by campaign_id; populated on
        # first ``run_next_phase`` after a CREATED transition. In-process
        # implementation — production wraps cost trackers in a side store
        # so SFN workers can resume after a process restart.
        self._cost_trackers: dict[str, CampaignCostTracker] = {}

    # -------------------------------------------------------------------------
    # Campaign creation
    # -------------------------------------------------------------------------

    async def create_campaign(
        self,
        definition: CampaignDefinition,
        billing_period: str,
    ) -> CampaignState:
        """Validate definition and persist initial state.

        Validation enforces (a) campaign type is supported by a registered
        worker, (b) approver_quorum meets the type's minimum, (c) tenant
        cost rollup has headroom, (d) success_criteria is non-empty.
        """
        self._validate_definition(definition)

        # D9: tenant cost rollup gate
        if not await self._tenant_rollup.can_start_campaign(
            definition.tenant_id,
            billing_period,
            definition.cost_cap_usd,
        ):
            raise TenantCostCapExceededError(
                f"Tenant {definition.tenant_id} cannot start campaign "
                f"{definition.campaign_id}: cost rollup exhausted for "
                f"period {billing_period}"
            )

        worker = self._worker_for(definition.campaign_type)
        first_phase = worker.first_phase()

        initial_state = CampaignState(
            campaign_id=definition.campaign_id,
            tenant_id=definition.tenant_id,
            status=CampaignStatus.CREATED,
            current_phase_id=first_phase.definition.phase_id,
        )
        await self._state_store.put_initial(initial_state)
        # Initialise the per-campaign cost tracker.
        self._cost_trackers[definition.campaign_id] = CampaignCostTracker(
            campaign_id=definition.campaign_id,
            cost_cap_usd=definition.cost_cap_usd,
        )
        logger.info(
            "Campaign %s created (tenant=%s, type=%s, cap=$%.2f)",
            definition.campaign_id,
            definition.tenant_id,
            definition.campaign_type.value,
            definition.cost_cap_usd,
        )
        return initial_state

    def _validate_definition(self, definition: CampaignDefinition) -> None:
        if definition.campaign_type not in self._workers:
            raise InvalidCampaignDefinitionError(
                f"No worker registered for campaign type "
                f"{definition.campaign_type.value!r}"
            )
        # D8: high-impact campaigns require approver_quorum >= 2.
        if (
            definition.campaign_type in HIGH_IMPACT_CAMPAIGN_TYPES
            and definition.approver_quorum < 2
        ):
            raise InvalidCampaignDefinitionError(
                f"Campaign type {definition.campaign_type.value} requires "
                f"approver_quorum >= 2; got {definition.approver_quorum}"
            )
        if not definition.success_criteria:
            raise InvalidCampaignDefinitionError(
                "success_criteria must be non-empty"
            )
        if definition.cost_cap_usd <= 0:
            raise InvalidCampaignDefinitionError(
                f"cost_cap_usd must be > 0; got {definition.cost_cap_usd}"
            )
        if definition.wall_clock_budget_hours <= 0:
            raise InvalidCampaignDefinitionError(
                f"wall_clock_budget_hours must be > 0; got "
                f"{definition.wall_clock_budget_hours}"
            )

    # -------------------------------------------------------------------------
    # Phase execution
    # -------------------------------------------------------------------------

    async def run_next_phase(
        self,
        definition: CampaignDefinition,
    ) -> CampaignState:
        """Run whichever phase the state machine says is next.

        Returns the post-execution state. Callers iterate until the
        returned state's status is terminal or AWAITING_HITL.
        """
        state = await self._load_state(definition)
        if state.status.is_terminal:
            return state
        if state.status == CampaignStatus.AWAITING_HITL:
            return state  # blocked on human; caller polls /approve
        if state.status == CampaignStatus.PAUSED:
            return state
        if state.status == CampaignStatus.HALTED_AT_CAP:
            return state
        if state.status == CampaignStatus.HALTED_AT_ANOMALY:
            return state

        worker = self._worker_for(definition.campaign_type)
        if state.current_phase_id is None:
            return await self._mark_terminal(
                state, CampaignStatus.COMPLETED, CampaignOutcome.SUCCESS
            )
        phase = worker.get_phase(state.current_phase_id)

        # Transition CREATED -> RUNNING on first execution.
        if state.status == CampaignStatus.CREATED:
            state = state.with_status(CampaignStatus.RUNNING)
            await self._state_store.update(
                expected_version=state.version - 1, new_state=state
            )

        cost_tracker = self._cost_tracker_for(definition.campaign_id, definition)
        prior_checkpoint = await self._checkpoint_store.read(
            definition.campaign_id, phase.definition.phase_id
        )
        context = PhaseExecutionContext(
            definition=definition,
            state=state,
            phase=phase.definition,
            cost_tracker=cost_tracker,
            operation_ledger=self._operation_ledger,
            prior_checkpoint=prior_checkpoint,
        )

        started_at = datetime.now(timezone.utc)
        try:
            result = await phase.execute(context)
        except CostCapExceededError as exc:
            logger.warning(
                "Campaign %s phase %s halted at cap: %s",
                definition.campaign_id,
                phase.definition.phase_id,
                exc,
            )
            cost_tracker.enter_cleanup_mode()
            return await self._mark_terminal(
                state,
                CampaignStatus.HALTED_AT_CAP,
                CampaignOutcome.HALTED_AT_CAP,
            )
        finished_at = datetime.now(timezone.utc)
        duration_seconds = max(0, int((finished_at - started_at).total_seconds()))

        return await self._apply_phase_result(
            definition=definition,
            state=state,
            worker=worker,
            phase=phase,
            result=result,
            duration_seconds=duration_seconds,
            cost_tracker=cost_tracker,
        )

    async def _apply_phase_result(
        self,
        definition: CampaignDefinition,
        state: CampaignState,
        worker: CampaignWorker,
        phase: Phase,
        result: PhaseResult,
        duration_seconds: int,
        cost_tracker: CampaignCostTracker,
    ) -> CampaignState:
        """Translate a PhaseResult into a state-machine transition."""
        # Persist checkpoint regardless of outcome (resumable on retry).
        checkpoint = PhaseCheckpoint(
            campaign_id=definition.campaign_id,
            phase_id=phase.definition.phase_id,
            artifact_manifest=result.artifacts,
            success_criteria_progress=result.success_criteria_progress,
            phase_summary=result.phase_summary,
            cost_counters=cost_tracker.snapshot(),
            wall_clock_counters=replace(
                state.clock,
                total_seconds=state.clock.total_seconds + duration_seconds,
                phases_completed=state.clock.phases_completed
                + (1 if result.advances_state_machine else 0),
            ),
            kms_signature=_dummy_kms_signature(definition.campaign_id),
        )
        checkpoint_key = await self._checkpoint_store.write(checkpoint)

        completed = CompletedPhaseRef(
            phase_id=phase.definition.phase_id,
            checkpoint_s3_key=checkpoint_key,
            outcome=result.outcome,
            duration_seconds=duration_seconds,
        )

        new_state = replace(
            state,
            phase_history=state.phase_history + (completed,),
            cost=cost_tracker.snapshot(),
            clock=checkpoint.wall_clock_counters,
            artifacts=state.artifacts + result.artifacts,
            last_checkpoint_s3_key=checkpoint_key,
            version=state.version + 1,
            updated_at=datetime.now(timezone.utc),
        )

        if result.outcome == PhaseOutcome.HITL_PENDING:
            milestone = HitlMilestone(
                milestone_id=str(uuid.uuid4()),
                phase_id=phase.definition.phase_id,
                requested_at=datetime.now(timezone.utc),
                approver_quorum=definition.approver_quorum,
            )
            new_state = replace(
                new_state,
                status=CampaignStatus.AWAITING_HITL,
                pending_hitl_approval=milestone,
            )
        elif result.outcome == PhaseOutcome.COST_CAP_REACHED:
            cost_tracker.enter_cleanup_mode()
            new_state = replace(new_state, status=CampaignStatus.HALTED_AT_CAP)
        elif result.outcome == PhaseOutcome.ANOMALY:
            new_state = replace(
                new_state, status=CampaignStatus.HALTED_AT_ANOMALY
            )
        elif result.outcome == PhaseOutcome.FAILED:
            new_state = replace(new_state, status=CampaignStatus.FAILED)
        elif result.outcome == PhaseOutcome.COMPLETED:
            next_phase = worker.next_phase(phase.definition.phase_id)
            if next_phase is None:
                new_state = replace(
                    new_state,
                    status=CampaignStatus.COMPLETED,
                    current_phase_id=None,
                )
            else:
                new_state = replace(
                    new_state,
                    current_phase_id=next_phase.definition.phase_id,
                    status=CampaignStatus.RUNNING,
                )

        await self._state_store.update(
            expected_version=state.version, new_state=new_state
        )
        return new_state

    # -------------------------------------------------------------------------
    # HITL approval (D8)
    # -------------------------------------------------------------------------

    async def approve_milestone(
        self,
        definition: CampaignDefinition,
        approver_principal_arn: str,
    ) -> CampaignState:
        """Record an approval; advance the state machine if quorum is met.

        Per D8: the campaign creator cannot approve their own
        campaign's milestones. High-impact campaigns require
        ``approver_quorum >= 2`` distinct approvers.
        """
        if approver_principal_arn == definition.creator_principal_arn:
            raise SeparationOfDutiesError(
                f"Principal {approver_principal_arn} created campaign "
                f"{definition.campaign_id} and cannot approve its own "
                f"milestones"
            )

        state = await self._load_state(definition)
        if state.status != CampaignStatus.AWAITING_HITL:
            raise SeparationOfDutiesError(
                f"Campaign {definition.campaign_id} is not awaiting HITL "
                f"(status={state.status.value})"
            )
        milestone = state.pending_hitl_approval
        if milestone is None:
            raise SeparationOfDutiesError(
                f"Campaign {definition.campaign_id} has no pending milestone"
            )
        if approver_principal_arn in milestone.approvals:
            raise SeparationOfDutiesError(
                f"Principal {approver_principal_arn} has already approved "
                f"milestone {milestone.milestone_id}"
            )

        new_approvals = milestone.approvals + (approver_principal_arn,)
        new_milestone = replace(milestone, approvals=new_approvals)
        if len(new_approvals) < milestone.approver_quorum:
            # Not enough approvers yet; remain AWAITING_HITL.
            updated = replace(
                state,
                pending_hitl_approval=new_milestone,
                version=state.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
            await self._state_store.update(
                expected_version=state.version, new_state=updated
            )
            return updated

        # Quorum met: clear the milestone and resume execution at the next
        # phase. The orchestrator's next ``run_next_phase`` call will pick
        # this up.
        worker = self._worker_for(definition.campaign_type)
        next_phase = worker.next_phase(milestone.phase_id)
        next_phase_id = (
            next_phase.definition.phase_id if next_phase else None
        )
        new_status = (
            CampaignStatus.RUNNING if next_phase else CampaignStatus.COMPLETED
        )
        updated = replace(
            state,
            pending_hitl_approval=None,
            current_phase_id=next_phase_id,
            status=new_status,
            version=state.version + 1,
            updated_at=datetime.now(timezone.utc),
        )
        await self._state_store.update(
            expected_version=state.version, new_state=updated
        )
        return updated

    # -------------------------------------------------------------------------
    # Cancellation
    # -------------------------------------------------------------------------

    async def cancel_campaign(
        self, definition: CampaignDefinition
    ) -> CampaignState:
        state = await self._load_state(definition)
        if state.status.is_terminal:
            return state
        return await self._mark_terminal(
            state, CampaignStatus.CANCELLED, CampaignOutcome.CANCELLED
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _worker_for(self, campaign_type) -> CampaignWorker:
        worker = self._workers.get(campaign_type)
        if worker is None:
            raise InvalidCampaignDefinitionError(
                f"No worker registered for {campaign_type.value!r}"
            )
        return worker

    async def _load_state(
        self, definition: CampaignDefinition
    ) -> CampaignState:
        state = await self._state_store.get(
            definition.tenant_id, definition.campaign_id
        )
        if state is None:
            raise InvalidCampaignDefinitionError(
                f"Campaign {definition.campaign_id} not found for tenant "
                f"{definition.tenant_id}"
            )
        return state

    def _cost_tracker_for(
        self, campaign_id: str, definition: CampaignDefinition
    ) -> CampaignCostTracker:
        tracker = self._cost_trackers.get(campaign_id)
        if tracker is None:
            tracker = CampaignCostTracker(
                campaign_id=campaign_id,
                cost_cap_usd=definition.cost_cap_usd,
            )
            self._cost_trackers[campaign_id] = tracker
        return tracker

    async def _mark_terminal(
        self,
        state: CampaignState,
        terminal_status: CampaignStatus,
        outcome: CampaignOutcome,
    ) -> CampaignState:
        if state.status == terminal_status:
            return state
        updated = replace(
            state,
            status=terminal_status,
            current_phase_id=None,
            version=state.version + 1,
            updated_at=datetime.now(timezone.utc),
        )
        await self._state_store.update(
            expected_version=state.version, new_state=updated
        )
        logger.info(
            "Campaign %s reached terminal status %s (outcome=%s)",
            state.campaign_id,
            terminal_status.value,
            outcome.value,
        )
        return updated


def _dummy_kms_signature(campaign_id: str) -> str:
    """Stub signature for in-process use.

    Production swaps in a KMS-backed signer; the in-memory checkpoint
    store accepts any non-empty string. Tests that exercise the
    tamper-detection path use ``InMemoryCheckpointStore.simulate_tamper``
    rather than checking signature validity.
    """
    return f"unsigned:{campaign_id}"
