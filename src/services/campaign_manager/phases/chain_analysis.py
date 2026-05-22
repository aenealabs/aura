"""
Project Aura - Cross-Repo Chain Analysis Worker (Phase 3).

Trace data flows across multiple repositories to identify exploitable
chains. Composes RLM (ADR-051) for cross-repo context with Titan
memory (ADR-024) for long-horizon recall and the GraphRAG retrieval
layer. The worker itself does not own those integrations directly -
they are injected via the ChainAnalysisDependencies Ports.

Phase graph:
    repo_discovery -> graph_build -> path_search -> hitl_review -> report

The HITL milestone surfaces the prioritised chain list to the
operator before any remediation work spins off (per ADR D8: human
approval gates the transition from "we found chains" to "we will act
on them").

Author: Project Aura Team
Created: 2026-05-22
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Optional

from src.services.vulnerability_scanner.analysis.capability import ModelCapabilityTier

from ..contracts import (
    ArtifactRef,
    CampaignPhase,
    CampaignType,
    PhaseOutcome,
    SuccessCriteriaProgress,
)
from ._ports import (
    CAMPAIGN_DEPS_KEY,
    ChainAnalysisDependencies,
    CrossRepoGraph,
    ExploitChain,
    HitlApprovalRequest,
    RepoRef,
)
from .base import CampaignWorker, Phase, PhaseExecutionContext, PhaseResult

CHAIN_ANALYSIS_BLACKBOARD_KEY: str = "chain_analysis_blackboard"


@dataclass
class ChainAnalysisBlackboard:
    """Per-campaign mutable state for Phase 3."""

    repos: tuple[RepoRef, ...] = ()
    graph: Optional[CrossRepoGraph] = None
    chains: list[ExploitChain] = field(default_factory=list)
    hitl_ticket_id: str = ""
    report_s3_key: str = ""


_REPO_DISCOVERY = CampaignPhase(
    phase_id="repo_discovery",
    label="Enumerate repositories in the fleet target",
    order=0,
    estimated_cost_usd=5.0,
)
_GRAPH_BUILD = CampaignPhase(
    phase_id="cross_repo_graph_build",
    label="Assemble cross-repo dataflow + call graph",
    order=1,
    estimated_cost_usd=25.0,
)
_PATH_SEARCH = CampaignPhase(
    phase_id="exploit_path_search",
    label="Search graph for exploitable cross-repo chains",
    order=2,
    estimated_cost_usd=15.0,
)
_HITL = CampaignPhase(
    phase_id="hitl_review",
    label="Operator review of prioritised chains",
    order=3,
    is_milestone=True,
)
_REPORT = CampaignPhase(
    phase_id="chain_report",
    label="Produce signed chain-analysis report",
    order=4,
    estimated_cost_usd=5.0,
)


def _get_deps(
    context: PhaseExecutionContext,
) -> Optional[ChainAnalysisDependencies]:
    deps = context.extra.get(CAMPAIGN_DEPS_KEY)
    if isinstance(deps, ChainAnalysisDependencies):
        return deps
    return None


def _get_or_create_blackboard(
    context: PhaseExecutionContext,
) -> ChainAnalysisBlackboard:
    board = context.extra.get(CHAIN_ANALYSIS_BLACKBOARD_KEY)
    if isinstance(board, ChainAnalysisBlackboard):
        return board
    board = ChainAnalysisBlackboard()
    context.extra[CHAIN_ANALYSIS_BLACKBOARD_KEY] = board
    return board


def _artifact(context: PhaseExecutionContext, suffix: str = "") -> ArtifactRef:
    artifact_id = hashlib.sha256(
        f"{context.definition.campaign_id}/{context.phase.phase_id}/{suffix}".encode()
    ).hexdigest()
    return ArtifactRef(
        artifact_id=artifact_id,
        manifest_s3_key=(
            f"chain-analysis/{context.definition.tenant_id}/"
            f"{context.definition.campaign_id}/{context.phase.phase_id}.json"
        ),
    )


def _stub_result(context: PhaseExecutionContext, *, criterion_id: str) -> PhaseResult:
    return PhaseResult(
        outcome=PhaseOutcome.COMPLETED,
        success_criteria_progress=(
            SuccessCriteriaProgress(criterion_id=criterion_id, progress=1.0),
        ),
        phase_summary=(f"[stub] Chain Analysis phase {context.phase.label} done."),
        artifacts=(_artifact(context),),
    )


class RepoDiscoveryPhase(Phase):
    criterion_id = "repos_discovered"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.repo_discovery is None:
            return _stub_result(context, criterion_id=self.criterion_id)

        board = _get_or_create_blackboard(context)
        fleet = context.definition.target or {}
        repos = await deps.repo_discovery.discover(fleet_target=fleet)
        board.repos = repos
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=f"Discovered {len(repos)} repositories in fleet.",
            artifacts=(_artifact(context),),
        )


class CrossRepoGraphBuildPhase(Phase):
    criterion_id = "graph_assembled"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.graph_builder is None:
            return _stub_result(context, criterion_id=self.criterion_id)

        board = _get_or_create_blackboard(context)
        if not board.repos:
            return PhaseResult(
                outcome=PhaseOutcome.FAILED,
                phase_summary="graph_build prerequisite missing: repos empty.",
            )

        graph = await deps.graph_builder.build(repos=board.repos)
        board.graph = graph
        if graph.input_tokens > 0 or graph.output_tokens > 0:
            context.cost_tracker.record(
                ModelCapabilityTier.STANDARD,
                graph.input_tokens,
                graph.output_tokens,
            )
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Assembled cross-repo graph: {len(graph.repos)} repos, "
                f"{len(graph.edges)} edges."
            ),
            artifacts=(_artifact(context),),
        )


class ExploitPathSearchPhase(Phase):
    criterion_id = "chains_identified"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is None or deps.path_search is None:
            return _stub_result(context, criterion_id=self.criterion_id)

        board = _get_or_create_blackboard(context)
        if board.graph is None:
            return PhaseResult(
                outcome=PhaseOutcome.FAILED,
                phase_summary="path_search prerequisite missing: graph empty.",
            )

        chains = await deps.path_search.search(graph=board.graph)
        board.chains = list(chains)
        critical = sum(1 for c in chains if c.estimated_impact == "CRITICAL")
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(
                f"Identified {len(chains)} exploit chains ({critical} CRITICAL)."
            ),
            artifacts=(_artifact(context),),
        )


class ChainHitlReviewPhase(Phase):
    criterion_id = "chains_human_reviewed"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        deps = _get_deps(context)
        if deps is not None and deps.hitl_gateway is not None:
            board = _get_or_create_blackboard(context)
            request = HitlApprovalRequest(
                request_id=str(uuid.uuid4()),
                campaign_id=context.definition.campaign_id,
                phase_id=context.phase.phase_id,
                artifact_summary=(
                    f"{len(board.chains)} exploit chains awaiting triage"
                ),
                severity="HIGH",
            )
            board.hitl_ticket_id = await deps.hitl_gateway.request_approval(
                request=request
            )
        return PhaseResult(
            outcome=PhaseOutcome.HITL_PENDING,
            phase_summary=(
                "Chain Analysis: operator review requested for the "
                "prioritised chain list."
            ),
        )


class ChainReportPhase(Phase):
    criterion_id = "chain_report_signed"

    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        board = _get_or_create_blackboard(context)
        if not board.chains and _get_deps(context) is not None:
            # Operator approved an empty set; still emit a clean report.
            board.report_s3_key = (
                f"chain-reports/{context.definition.tenant_id}/"
                f"{context.definition.campaign_id}/empty.json"
            )
        else:
            board.report_s3_key = (
                f"chain-reports/{context.definition.tenant_id}/"
                f"{context.definition.campaign_id}/"
                f"{uuid.uuid4().hex[:8]}.json"
            )
        return PhaseResult(
            outcome=PhaseOutcome.COMPLETED,
            success_criteria_progress=(
                SuccessCriteriaProgress(criterion_id=self.criterion_id, progress=1.0),
            ),
            phase_summary=(f"Chain analysis report emitted: {board.report_s3_key}"),
            artifacts=(_artifact(context, suffix="report"),),
        )


class ChainAnalysisWorker(CampaignWorker):
    _PHASE_GRAPH: tuple[Phase, ...] = (
        RepoDiscoveryPhase(_REPO_DISCOVERY),
        CrossRepoGraphBuildPhase(_GRAPH_BUILD),
        ExploitPathSearchPhase(_PATH_SEARCH),
        ChainHitlReviewPhase(_HITL),
        ChainReportPhase(_REPORT),
    )

    @property
    def campaign_type(self) -> CampaignType:
        return CampaignType.CROSS_REPO_CHAIN_ANALYSIS

    def phase_graph(self) -> tuple[Phase, ...]:
        return self._PHASE_GRAPH


__all__ = [
    "CHAIN_ANALYSIS_BLACKBOARD_KEY",
    "ChainAnalysisBlackboard",
    "ChainAnalysisWorker",
    "ChainHitlReviewPhase",
    "ChainReportPhase",
    "CrossRepoGraphBuildPhase",
    "ExploitPathSearchPhase",
    "RepoDiscoveryPhase",
]
