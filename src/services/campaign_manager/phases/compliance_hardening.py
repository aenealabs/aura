"""
Project Aura - Compliance Hardening Worker (Phase 1).

The wedge campaign type: drive a target codebase to pass a target
compliance standard (NIST 800-53, SOC 2, CMMC, FedRAMP). Exercises
every primitive the campaign manager composes (scanner, capability
governance, verification envelope, HITL milestones, audit-grade
artifacts) and produces a sellable artifact (compliance evidence
package).

This module ships **real phase bodies** that integrate with the
external services via the Ports defined in ``_ports.py``. When the
ports are not injected (``PhaseExecutionContext.extra`` is empty),
each phase falls back to a deterministic stub path so the
orchestrator-level tests can be exercised in isolation.

Implements ADR-089 Phase 1.

Author: Project Aura Team
Created: 2026-05-07
Updated: 2026-05-22 (real integrations + blackboard)
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

from src.services.vulnerability_scanner.analysis.capability import ModelCapabilityTier

from ..contracts import (
    ArtifactRef,
    CampaignPhase,
    CampaignType,
    OperationOutcome,
    OperationStatus,
    PhaseOutcome,
    SuccessCriteriaProgress,
)
from ._ports import (
    CAMPAIGN_DEPS_KEY,
    ComplianceHardeningDependencies,
    DeploymentRecord,
    EvidencePackage,
    GapAnalysis,
    GeneratedPatch,
    HitlApprovalRequest,
    RemediationPlan,
    SandboxVerdict,
    ScanReport,
)
from .base import CampaignWorker, Phase, PhaseExecutionContext, PhaseResult

# Key under which the per-campaign blackboard lives in ``extra``.
COMPLIANCE_BLACKBOARD_KEY: str = "compliance_blackboard"


# -----------------------------------------------------------------------------
# Per-campaign blackboard
# -----------------------------------------------------------------------------


@dataclass
class ComplianceHardeningBlackboard:
    """Mutable runtime state shared across Phase 1 phases.

    Phases write their typed outputs here as they complete; downstream
    phases read. Lives for the lifetime of one campaign run; not
    persisted (the durable artifact trail lives in checkpoints + S3
    object refs).
    """

    baseline_report: Optional[ScanReport] = None
    gap_analysis: Optional[GapAnalysis] = None
    remediation_plan: Optional[RemediationPlan] = None
    patches: list[GeneratedPatch] = field(default_factory=list)
    verdicts: list[SandboxVerdict] = field(default_factory=list)
    hitl_ticket_id: str = ""
    deployment_record: Optional[DeploymentRecord] = None
    evidence_package: Optional[EvidencePackage] = None


# -----------------------------------------------------------------------------
# Phase graph definitions
# -----------------------------------------------------------------------------


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
    is_milestone=True,
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
    is_high_consequence=True,
    estimated_cost_usd=40.0,
)

_HITL_REVIEW = CampaignPhase(
    phase_id="hitl_review",
    label="Human review of patch set",
    order=4,
    is_milestone=True,
    is_high_consequence=True,
    estimated_cost_usd=0.0,
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


# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------


def _get_deps(
    context: PhaseExecutionContext,
) -> Optional[ComplianceHardeningDependencies]:
    deps = context.extra.get(CAMPAIGN_DEPS_KEY)
    if isinstance(deps, ComplianceHardeningDependencies):
        return deps
    return None


def _get_or_create_blackboard(
    context: PhaseExecutionContext,
) -> ComplianceHardeningBlackboard:
    board = context.extra.get(COMPLIANCE_BLACKBOARD_KEY)
    if isinstance(board, ComplianceHardeningBlackboard):
        return board
    board = ComplianceHardeningBlackboard()
    context.extra[COMPLIANCE_BLACKBOARD_KEY] = board
    return board


def _record_llm_cost(
    context: PhaseExecutionContext,
    *,
    input_tokens: int,
    output_tokens: int,
    tier: ModelCapabilityTier = ModelCapabilityTier.STANDARD,
) -> None:
    """Record cost on the campaign tracker if any tokens were used.

    Wraps the tracker call so phases don't need to know the tier
    enum; defaults to STANDARD which is the right tier for compliance
    workloads.
    """
    if input_tokens <= 0 and output_tokens <= 0:
        return
    context.cost_tracker.record(tier, input_tokens, output_tokens)


def _stub_artifact(phase_id: str, campaign_id: str, tenant_id: str) -> ArtifactRef:
    """Build a deterministic ArtifactRef for stub paths."""
    artifact_id = hashlib.sha256(f"{campaign_id}/{phase_id}".encode()).hexdigest()
    return ArtifactRef(
        artifact_id=artifact_id,
        manifest_s3_key=f"stubs/{tenant_id}/{campaign_id}/{phase_id}.json",
    )


def _stub_result(
    context: PhaseExecutionContext,
    *,
    criterion_id: str,
    note: str,
) -> PhaseResult:
    """Deterministic stub PhaseResult; preserves pre-integration behaviour."""
    artifact = _stub_artifact(
        context.phase.phase_id,
        context.definition.campaign_id,
        context.definition.tenant_id,
    )
    progress = (
        (SuccessCriteriaProgress(criterion_id=criterion_id, progress=1.0),)
        if criterion_id
        else ()
    )
    return PhaseResult(
        outcome=PhaseOutcome.COMPLETED,
        success_criteria_progress=progress,
        phase_summary=(
            f"[stub] Compliance Hardening phase {context.phase.label} "
            f"advanced criterion={criterion_id!r}. {note}"
        ),
        artifacts=(artifact,),
    )


# -----------------------------------------------------------------------------
# Concrete phases
# -----------------------------------------------------------------------------


class BaselineScanPhase(Phase):
    """Run a baseline compliance scan against the target repository."""

    criterion_id = "baseline_scan_complete"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.scanner is None:
            return _stub_result(
                context,
                criterion_id=self.criterion_id,
                note="No scanner port wired; emitting stub baseline.",
            )

        board = _get_or_create_blackboard(context)
        target = context.definition.target or {}
        standard = context.definition.success_criteria.get("standard", "")
        repo_url = target.get("repo", "")
        scan_id = f"scan-{context.definition.campaign_id}-{uuid.uuid4().hex[:8]}"

        report = await deps.scanner.baseline_scan(
            repo_url=repo_url, standard=standard, scan_id=scan_id
        )
        board.baseline_report = report
        _record_llm_cost(
            context,
            input_tokens=report.input_tokens,
            output_tokens=report.output_tokens,
        )

        artifact = ArtifactRef(
            artifact_id=hashlib.sha256(scan_id.encode()).hexdigest(),
            manifest_s3_key=(
                f"baseline-scans/{context.definition.tenant_id}/"
                f"{context.definition.campaign_id}/{scan_id}.json"
            ),
        )
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Baseline scan {scan_id}: {len(report.findings)} findings "
                f"across {report.files_scanned} files against {standard}."
            ),
            artifacts=(artifact,),
        )


class GapAnalysisPhase(Phase):
    """Map findings to controls in the target standard."""

    criterion_id = "gap_analysis_complete"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.gap_analyzer is None:
            return _stub_result(
                context,
                criterion_id=self.criterion_id,
                note="No gap_analyzer port wired; emitting stub gap analysis.",
            )

        board = _get_or_create_blackboard(context)
        if board.baseline_report is None:
            return PhaseResult(
                outcome=PhaseOutcome.FAILED,
                phase_summary=(
                    "gap_analysis prerequisite not met: baseline_report missing "
                    "from blackboard."
                ),
            )

        analysis = await deps.gap_analyzer.analyze(report=board.baseline_report)
        board.gap_analysis = analysis
        _record_llm_cost(
            context,
            input_tokens=analysis.input_tokens,
            output_tokens=analysis.output_tokens,
        )

        critical_gaps = sum(1 for g in analysis.gaps if g.severity == "CRITICAL")
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Gap analysis: {len(analysis.gaps)} gaps mapped against "
                f"{analysis.standard} ({critical_gaps} critical)."
            ),
            artifacts=(
                _stub_artifact(
                    context.phase.phase_id,
                    context.definition.campaign_id,
                    context.definition.tenant_id,
                ),
            ),
        )


class RemediationPlanPhase(Phase):
    """Produce a ranked remediation plan from the gap analysis."""

    criterion_id = "remediation_plan_complete"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.planner is None:
            return _stub_result(
                context,
                criterion_id=self.criterion_id,
                note="No planner port wired; emitting stub plan.",
            )

        board = _get_or_create_blackboard(context)
        if board.gap_analysis is None:
            return PhaseResult(
                outcome=PhaseOutcome.FAILED,
                phase_summary=(
                    "remediation_plan prerequisite not met: gap_analysis missing."
                ),
            )

        plan = await deps.planner.plan(analysis=board.gap_analysis)
        board.remediation_plan = plan
        _record_llm_cost(
            context,
            input_tokens=plan.input_tokens,
            output_tokens=plan.output_tokens,
        )

        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Remediation plan {plan.plan_id}: {len(plan.items)} items "
                f"(est. ${plan.total_estimated_cost_usd:.2f})."
            ),
            artifacts=(
                _stub_artifact(
                    context.phase.phase_id,
                    context.definition.campaign_id,
                    context.definition.tenant_id,
                ),
            ),
        )


class PatchGenerationPhase(Phase):
    """Generate + sandbox-verify a patch per remediation item.

    Iterates over the plan; for each item, claims an op in the ledger
    (idempotency D2), generates a patch, runs it in the sandbox, and
    records the verdict. Halts early on cost-cap or sandbox failure
    so the orchestrator can decide next steps.
    """

    criterion_id = "patches_sandbox_verified"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if (
            deps is None
            or deps.patch_generator is None
            or deps.sandbox_verifier is None
        ):
            return _stub_result(
                context,
                criterion_id=self.criterion_id,
                note="No patch_generator/sandbox_verifier wired; stub run.",
            )

        board = _get_or_create_blackboard(context)
        if board.remediation_plan is None:
            return PhaseResult(
                outcome=PhaseOutcome.FAILED,
                phase_summary="patch_generation prerequisite missing: plan.",
            )

        target = context.definition.target or {}
        repo_url = target.get("repo", "")
        # #214-B3: attempt counter derived from phase-history. The
        # current state machine treats FAILED as terminal, so attempts
        # never exceed 1 today; the counter is forward-compatible for
        # a future retry-from-FAILED mechanism without breaking the
        # current op-ledger idempotency contract.
        attempt = (
            sum(
                1
                for entry in context.state.phase_history
                if entry.phase_id == context.phase.phase_id
                and entry.outcome
                in {PhaseOutcome.FAILED, PhaseOutcome.COST_CAP_REACHED}
            )
            + 1
        )

        patches: list[GeneratedPatch] = []
        verdicts: list[SandboxVerdict] = []
        failed: list[str] = []

        for item in board.remediation_plan.items:
            op_id = f"patch:{item.item_id}:attempt-{attempt}"
            claim = await context.operation_ledger.claim(
                context.definition.tenant_id,
                context.definition.campaign_id,
                context.phase.phase_id,
                op_id,
            )

            if claim.status == OperationStatus.ALREADY_EXECUTED:
                # #214-B1: re-hydrate the blackboard from the prior
                # outcome's payload so DownstreamPhase sees the patch
                # set after a crash + retry within the same attempt.
                if claim.prior_outcome and claim.prior_outcome.payload:
                    payload = claim.prior_outcome.payload
                    patch = GeneratedPatch(**payload["patch"])
                    verdict = SandboxVerdict(**payload["verdict"])
                    patches.append(patch)
                    verdicts.append(verdict)
                    if not verdict.passed:
                        failed.append(patch.patch_id)
                continue

            patch = await deps.patch_generator.generate(item=item, repo_url=repo_url)
            _record_llm_cost(
                context,
                input_tokens=patch.input_tokens,
                output_tokens=patch.output_tokens,
            )
            patches.append(patch)

            verdict = await deps.sandbox_verifier.verify(patch=patch)
            if verdict.sandbox_cost_usd > 0:
                context.cost_tracker.record_sandbox_cost(verdict.sandbox_cost_usd)
            verdicts.append(verdict)

            await context.operation_ledger.record_outcome(
                context.definition.tenant_id,
                context.definition.campaign_id,
                context.phase.phase_id,
                op_id,
                OperationOutcome(
                    success=verdict.passed,
                    summary=(f"patch={patch.patch_id} passed={verdict.passed}"),
                    payload={
                        "patch": asdict(patch),
                        "verdict": asdict(verdict),
                    },
                ),
            )

            if not verdict.passed:
                failed.append(patch.patch_id)

        board.patches.extend(patches)
        board.verdicts.extend(verdicts)

        if failed:
            return PhaseResult(
                outcome=PhaseOutcome.FAILED,
                phase_summary=(
                    f"{len(failed)} of {len(patches)} patches failed sandbox "
                    f"verification: {failed[:3]}{'...' if len(failed) > 3 else ''}"
                ),
                artifacts=(
                    _stub_artifact(
                        context.phase.phase_id,
                        context.definition.campaign_id,
                        context.definition.tenant_id,
                    ),
                ),
            )

        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Generated + verified {len(patches)} patches; all sandbox-passing."
            ),
            artifacts=(
                _stub_artifact(
                    context.phase.phase_id,
                    context.definition.campaign_id,
                    context.definition.tenant_id,
                ),
            ),
        )


class HitlReviewPhase(Phase):
    """Pause the campaign for HITL approval of the patch set.

    Always returns HITL_PENDING; the orchestrator translates that
    into the state-machine pause and surfaces the milestone via the
    API for human approval. If a HITL gateway is wired, the phase
    additionally registers the request and records the ticket id on
    the blackboard for traceability.
    """

    criterion_id = "patches_human_approved"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is not None and deps.hitl_gateway is not None:
            board = _get_or_create_blackboard(context)
            request = HitlApprovalRequest(
                request_id=str(uuid.uuid4()),
                campaign_id=context.definition.campaign_id,
                phase_id=context.phase.phase_id,
                artifact_summary=(f"{len(board.patches)} patches awaiting review"),
                severity="HIGH",
            )
            board.hitl_ticket_id = await deps.hitl_gateway.request_approval(
                request=request
            )

        return PhaseResult(
            outcome=PhaseOutcome.HITL_PENDING,
            phase_summary=(
                "Compliance Hardening: HITL review requested; campaign "
                "awaits operator approval of patch set."
            ),
        )


class DeploymentPhase(Phase):
    """Deploy approved patches via the change-control gate."""

    criterion_id = "patches_deployed"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.deployment_gate is None:
            return _stub_result(
                context,
                criterion_id=self.criterion_id,
                note="No deployment_gate port wired; stub deploy.",
            )

        board = _get_or_create_blackboard(context)
        if not board.patches:
            return PhaseResult(
                outcome=PhaseOutcome.FAILED,
                phase_summary="deployment prerequisite missing: no patches.",
            )

        record = await deps.deployment_gate.deploy(
            patches=tuple(board.patches),
            change_ticket_id=deps.change_ticket_id,
        )
        board.deployment_record = record

        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Deployed {len(record.patch_ids)} patches via "
                f"change-ticket={record.change_ticket_id} "
                f"strategy={record.rollout_strategy}."
            ),
            artifacts=(
                _stub_artifact(
                    context.phase.phase_id,
                    context.definition.campaign_id,
                    context.definition.tenant_id,
                ),
            ),
        )


class EvidencePackagePhase(Phase):
    """Produce a signed compliance evidence package for audit."""

    criterion_id = "evidence_package_signed"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.evidence_packager is None:
            return _stub_result(
                context,
                criterion_id=self.criterion_id,
                note="No evidence_packager port wired; stub package.",
            )

        board = _get_or_create_blackboard(context)
        if (
            board.baseline_report is None
            or board.gap_analysis is None
            or board.remediation_plan is None
            or board.deployment_record is None
        ):
            return PhaseResult(
                outcome=PhaseOutcome.FAILED,
                phase_summary="evidence_package prerequisites missing.",
            )

        package = await deps.evidence_packager.package(
            campaign_id=context.definition.campaign_id,
            tenant_id=context.definition.tenant_id,
            standard=board.gap_analysis.standard,
            baseline=board.baseline_report,
            gaps=board.gap_analysis,
            plan=board.remediation_plan,
            verdicts=tuple(board.verdicts),
            deployment=board.deployment_record,
        )
        board.evidence_package = package

        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Evidence package {package.package_id} signed for "
                f"{package.standard}; s3_key={package.s3_key}."
            ),
            artifacts=(
                ArtifactRef(
                    artifact_id=package.package_id,
                    manifest_s3_key=package.s3_key,
                ),
            ),
        )


# -----------------------------------------------------------------------------
# Worker
# -----------------------------------------------------------------------------


class ComplianceHardeningWorker(CampaignWorker):
    """Worker for Compliance Hardening campaigns.

    Defines the static phase graph. Each phase looks up its
    dependencies in ``PhaseExecutionContext.extra`` under
    ``CAMPAIGN_DEPS_KEY``; absent dependencies fall back to a
    deterministic stub path so the orchestrator can be exercised
    without external services.
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


__all__ = [
    "BaselineScanPhase",
    "ComplianceHardeningBlackboard",
    "ComplianceHardeningWorker",
    "COMPLIANCE_BLACKBOARD_KEY",
    "DeploymentPhase",
    "EvidencePackagePhase",
    "GapAnalysisPhase",
    "HitlReviewPhase",
    "PatchGenerationPhase",
    "RemediationPlanPhase",
]
