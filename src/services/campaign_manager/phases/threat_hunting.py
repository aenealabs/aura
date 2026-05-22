"""
Project Aura - Continuous Threat Hunting Worker (Phase 4).

Always-on campaign type: poll CVE feeds, correlate against runtime
telemetry (ADR-083), and surface proactive patch proposals. The
worker models a single cycle (poll -> snapshot -> correlate ->
emit); production wires EventBridge Scheduler to re-invoke the
campaign on a cadence so the system runs continuously.

Phase graph:
    poll_cves -> snapshot_telemetry -> correlate -> emit_findings

The cycle_budget on ThreatHuntingDependencies caps how many sub-polls
happen inside a single phase invocation; defaults to 1.

Author: Project Aura Team
Created: 2026-05-22
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..contracts import (
    ArtifactRef,
    CampaignPhase,
    CampaignType,
    PhaseOutcome,
    SuccessCriteriaProgress,
)
from ._ports import (
    CAMPAIGN_DEPS_KEY,
    CveFeedEntry,
    HitlApprovalRequest,
    HuntFinding,
    RuntimeTelemetrySnapshot,
    ThreatHuntingDependencies,
)
from .base import CampaignWorker, Phase, PhaseExecutionContext, PhaseResult

THREAT_HUNTING_BLACKBOARD_KEY: str = "threat_hunting_blackboard"

# Default poll window when the blackboard has no prior cycle.
_DEFAULT_POLL_WINDOW = timedelta(hours=24)


@dataclass
class ThreatHuntingBlackboard:
    """Per-campaign mutable state for Phase 4."""

    last_poll_at: Optional[datetime] = None
    last_cycle_cves: list[CveFeedEntry] = field(default_factory=list)
    last_telemetry: Optional[RuntimeTelemetrySnapshot] = None
    findings: list[HuntFinding] = field(default_factory=list)
    cycle_count: int = 0
    hitl_ticket_ids: list[str] = field(default_factory=list)


_POLL = CampaignPhase(
    phase_id="poll_cves",
    label="Poll CVE feeds for new entries",
    order=0,
    estimated_cost_usd=1.0,
)
_SNAPSHOT = CampaignPhase(
    phase_id="snapshot_telemetry",
    label="Snapshot runtime telemetry",
    order=1,
    estimated_cost_usd=0.5,
)
_CORRELATE = CampaignPhase(
    phase_id="correlate",
    label="Correlate CVEs against runtime telemetry",
    order=2,
    estimated_cost_usd=8.0,
)
_EMIT = CampaignPhase(
    phase_id="emit_findings",
    label="Surface hunt findings; HITL for critical/high",
    order=3,
)


def _get_deps(
    context: PhaseExecutionContext,
) -> Optional[ThreatHuntingDependencies]:
    deps = context.extra.get(CAMPAIGN_DEPS_KEY)
    if isinstance(deps, ThreatHuntingDependencies):
        return deps
    return None


def _get_or_create_blackboard(
    context: PhaseExecutionContext,
) -> ThreatHuntingBlackboard:
    board = context.extra.get(THREAT_HUNTING_BLACKBOARD_KEY)
    if isinstance(board, ThreatHuntingBlackboard):
        return board
    board = ThreatHuntingBlackboard()
    context.extra[THREAT_HUNTING_BLACKBOARD_KEY] = board
    return board


def _artifact(context: PhaseExecutionContext) -> ArtifactRef:
    artifact_id = hashlib.sha256(
        f"{context.definition.campaign_id}/{context.phase.phase_id}".encode()
    ).hexdigest()
    return ArtifactRef(
        artifact_id=artifact_id,
        manifest_s3_key=(
            f"threat-hunting/{context.definition.tenant_id}/"
            f"{context.definition.campaign_id}/{context.phase.phase_id}.json"
        ),
    )


def _stub_result(context: PhaseExecutionContext, *, criterion_id: str) -> PhaseResult:
    return PhaseResult(
        outcome=PhaseOutcome.COMPLETED,
        success_criteria_progress=(
            SuccessCriteriaProgress(criterion_id=criterion_id, progress=1.0),
        ),
        phase_summary=f"[stub] Threat Hunting phase {context.phase.label} done.",
        artifacts=(_artifact(context),),
    )


class PollCvesPhase(Phase):
    criterion_id = "cves_polled"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.cve_feed is None:
            return _stub_result(context, criterion_id=self.criterion_id)

        board = _get_or_create_blackboard(context)
        now = datetime.now(timezone.utc)
        since = board.last_poll_at or (now - _DEFAULT_POLL_WINDOW)
        # cycle_budget caps how many polls run inside one phase invocation.
        all_entries: list[CveFeedEntry] = []
        for _ in range(max(1, deps.cycle_budget)):
            entries = await deps.cve_feed.poll(since=since)
            all_entries.extend(entries)
            if entries:
                # Advance the "since" cursor past the latest entry so
                # the next budget-pass doesn't refetch the same set.
                latest = max(e.published_at for e in entries)
                since = latest

        board.last_cycle_cves = all_entries
        board.last_poll_at = now
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Polled {len(all_entries)} new CVE entries "
                f"(cycle_budget={deps.cycle_budget})."
            ),
            artifacts=(_artifact(context),),
        )


class SnapshotTelemetryPhase(Phase):
    criterion_id = "telemetry_snapshotted"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.telemetry is None:
            return _stub_result(context, criterion_id=self.criterion_id)

        board = _get_or_create_blackboard(context)
        snap = await deps.telemetry.snapshot()
        board.last_telemetry = snap
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Telemetry: {len(snap.components_in_use)} components in use; "
                f"{len(snap.suspect_processes)} suspect processes."
            ),
            artifacts=(_artifact(context),),
        )


class CorrelatePhase(Phase):
    criterion_id = "findings_correlated"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.correlator is None:
            return _stub_result(context, criterion_id=self.criterion_id)

        board = _get_or_create_blackboard(context)
        if board.last_telemetry is None:
            return PhaseResult(
                outcome=PhaseOutcome.FAILED,
                phase_summary="correlate prerequisite missing: telemetry.",
            )

        findings = await deps.correlator.correlate(
            cves=tuple(board.last_cycle_cves),
            telemetry=board.last_telemetry,
        )
        board.findings.extend(findings)
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(f"Correlated {len(findings)} hunt findings this cycle."),
            artifacts=(_artifact(context),),
        )


class EmitFindingsPhase(Phase):
    """Surface findings; request HITL for any CRITICAL/HIGH."""

    criterion_id = "findings_emitted"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        board = _get_or_create_blackboard(context)
        board.cycle_count += 1

        if deps is not None and deps.hitl_gateway is not None:
            for finding in board.findings:
                if finding.severity.upper() not in {"CRITICAL", "HIGH"}:
                    continue
                request = HitlApprovalRequest(
                    request_id=str(uuid.uuid4()),
                    campaign_id=context.definition.campaign_id,
                    phase_id=context.phase.phase_id,
                    artifact_summary=(
                        f"Hunt finding {finding.finding_id} "
                        f"({finding.cve_id}): {finding.proposed_action}"
                    ),
                    severity=finding.severity,
                )
                ticket = await deps.hitl_gateway.request_approval(request=request)
                board.hitl_ticket_ids.append(ticket)

        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Cycle {board.cycle_count} complete: "
                f"{len(board.findings)} cumulative findings, "
                f"{len(board.hitl_ticket_ids)} HITL tickets opened."
            ),
            artifacts=(_artifact(context),),
        )


class ContinuousThreatHuntingWorker(CampaignWorker):
    """One cycle = one campaign run. Schedule continuously externally."""

    _PHASE_GRAPH: tuple[Phase, ...] = (
        PollCvesPhase(_POLL),
        SnapshotTelemetryPhase(_SNAPSHOT),
        CorrelatePhase(_CORRELATE),
        EmitFindingsPhase(_EMIT),
    )

    @property
    def campaign_type(self) -> CampaignType:
        return CampaignType.CONTINUOUS_THREAT_HUNTING

    def phase_graph(self) -> tuple[Phase, ...]:
        return self._PHASE_GRAPH


__all__ = [
    "ContinuousThreatHuntingWorker",
    "CorrelatePhase",
    "EmitFindingsPhase",
    "PollCvesPhase",
    "SnapshotTelemetryPhase",
    "THREAT_HUNTING_BLACKBOARD_KEY",
    "ThreatHuntingBlackboard",
]
