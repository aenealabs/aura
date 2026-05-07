"""
Project Aura - Compliance Hardening Worker (Phase 1).

The wedge campaign type: drive a target codebase to pass a target
compliance standard (NIST 800-53, SOC 2, CMMC, FedRAMP). Exercises
every primitive the campaign manager composes (scanner, capability
governance, verification envelope, HITL milestones, audit-grade
artifacts) and produces a sellable artifact (compliance evidence
package).

This module ships the **phase graph and worker shell**. Each phase's
``execute`` body delegates to the existing scanner / governance /
verification primitives — those integrations land in follow-up PRs as
the rest of the campaign manager goes live. The shell is sufficient
to exercise the orchestrator, operation ledger, cost tracker, and
HITL milestone machinery against fakes.

Implements ADR-089 Phase 1.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

from ..contracts import (
    CampaignPhase,
    CampaignType,
    PhaseOutcome,
    SuccessCriteriaProgress,
)
from .base import CampaignWorker, Phase, PhaseExecutionContext, PhaseResult


# Phase graph for Compliance Hardening. Order is significant: each
# phase consumes artifacts produced by the previous one.

_BASELINE_SCAN = CampaignPhase(
    phase_id="baseline_scan",
    label="Baseline compliance scan",
    order=0,
    is_milestone=False,
    is_high_consequence=False,
    estimated_cost_usd=15.0,
)

_GAP_ANALYSIS = CampaignPhase(
    phase_id="gap_analysis",
    label="Compliance gap analysis vs target standard",
    order=1,
    is_milestone=True,  # operator approves the gap list before remediation
    is_high_consequence=False,
    estimated_cost_usd=20.0,
)

_REMEDIATION_PLAN = CampaignPhase(
    phase_id="remediation_plan",
    label="Generate ranked remediation plan",
    order=2,
    is_milestone=False,
    is_high_consequence=False,
    estimated_cost_usd=10.0,
)

_PATCH_GENERATION = CampaignPhase(
    phase_id="patch_generation",
    label="Generate + sandbox-verify patches",
    order=3,
    is_milestone=False,
    is_high_consequence=True,  # patches mutate code; constitutional critique runs
    estimated_cost_usd=40.0,
)

_HITL_REVIEW = CampaignPhase(
    phase_id="hitl_review",
    label="Human review of patch set",
    order=4,
    is_milestone=True,  # mandatory; no auto-deploy from this phase
    is_high_consequence=True,
    estimated_cost_usd=0.0,  # human time, not LLM
)

_DEPLOYMENT = CampaignPhase(
    phase_id="deployment",
    label="Deploy approved patches via existing change-control gate",
    order=5,
    is_milestone=False,
    is_high_consequence=True,
    estimated_cost_usd=5.0,
)

_EVIDENCE_PACKAGE = CampaignPhase(
    phase_id="evidence_package",
    label="Produce signed compliance evidence package",
    order=6,
    is_milestone=False,
    is_high_consequence=False,
    estimated_cost_usd=10.0,
)


# Concrete phases: each currently a stub that records the success
# criterion the phase advances. Real execution bodies are wired in as
# the integrations land. Stubs are still useful — they let the
# orchestrator be tested end-to-end with a deterministic worker.


class _StubPhase(Phase):
    """Phase whose body produces a fixed PhaseResult.

    Useful for tests and for incremental wiring of the real phases.
    Subclasses override ``criterion_id`` to identify which success
    criterion this phase advances.
    """

    criterion_id: str = ""

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        progress = (
            SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
        ) if self.criterion_id else ()
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=progress,
            phase_summary=(
                f"[stub] Compliance Hardening phase "
                f"{self.definition.label} advanced "
                f"criterion={self.criterion_id!r}."
            ),
        )


class BaselineScanPhase(_StubPhase):
    criterion_id = "baseline_scan_complete"


class GapAnalysisPhase(_StubPhase):
    criterion_id = "gap_analysis_approved"


class RemediationPlanPhase(_StubPhase):
    criterion_id = "remediation_plan_ranked"


class PatchGenerationPhase(_StubPhase):
    criterion_id = "patches_sandbox_verified"


class HitlReviewPhase(_StubPhase):
    criterion_id = "patches_human_approved"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        # The HITL review phase always emits HITL_PENDING; the
        # orchestrator translates that into the state-machine pause.
        # Real workers would surface the patch set to the approver
        # via an EventBridge event with the SFN task token.
        return PhaseResult(
            outcome=PhaseOutcome.HITL_PENDING,
            phase_summary=(
                "[stub] Compliance Hardening: HITL review requested; "
                "campaign awaits operator approval of patch set."
            ),
        )


class DeploymentPhase(_StubPhase):
    criterion_id = "patches_deployed"


class EvidencePackagePhase(_StubPhase):
    criterion_id = "evidence_package_signed"


class ComplianceHardeningWorker(CampaignWorker):
    """Worker for Compliance Hardening campaigns.

    Defines the static phase graph and the concrete phase
    implementations. The phases here are stubs that produce
    deterministic outcomes; real integrations land in subsequent PRs.
    Production wiring will inject the scanner, verification envelope,
    capability router, and audit artifact writer via the
    ``PhaseExecutionContext.extra`` dict.
    """

    _PHASE_GRAPH: tuple[Phase, ...] = (
        BaselineScanPhase(_BASELINE_SCAN),
        GapAnalysisPhase(_GAP_ANALYSIS),
        RemediationPlanPhase(_REMEDIATION_PLAN),
        PatchGenerationPhase(_PATCH_GENERATION),
        HitlReviewPhase(_HITL_REVIEW),
        DeploymentPhase(_DEPLOYMENT),
        EvidencePackagePhase(_EVIDENCE_PACKAGE),
    )

    @property
    def campaign_type(self) -> CampaignType:
        return CampaignType.COMPLIANCE_HARDENING

    def phase_graph(self) -> tuple[Phase, ...]:
        return self._PHASE_GRAPH
