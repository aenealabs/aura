"""
Project Aura - Campaign Phase + Worker Base Classes.

A ``Phase`` is the unit the orchestrator drives the state machine over;
a ``CampaignWorker`` is the per-campaign-type implementation that
defines the phase graph and runs each phase.

Per D7 (harness-driven loops), phase termination is determined by the
harness via deterministic exit conditions, NEVER by the LLM declaring
it is done.

Implements ADR-089.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from ..contracts import (
    ArtifactRef,
    CampaignDefinition,
    CampaignPhase,
    CampaignState,
    CampaignType,
    PhaseCheckpoint,
    PhaseOutcome,
    SuccessCriteriaProgress,
)
from ..cost_tracker import CampaignCostTracker
from ..operation_ledger import OperationLedger


@dataclass
class PhaseExecutionContext:
    """Everything a phase needs to run.

    Constructed by the orchestrator and passed into ``Phase.execute``.
    Workers should not retain a reference past the call — the
    orchestrator may rebuild the context after a re-anchor.
    """

    definition: CampaignDefinition
    state: CampaignState
    phase: CampaignPhase
    cost_tracker: CampaignCostTracker
    operation_ledger: OperationLedger
    prior_checkpoint: PhaseCheckpoint | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PhaseResult:
    """Outcome of a single phase execution.

    Workers return one of these; the orchestrator translates the
    outcome into a state-machine transition (advance / pause for
    HITL / halt at cap / re-anchor).
    """

    outcome: PhaseOutcome
    artifacts: tuple[ArtifactRef, ...] = ()
    success_criteria_progress: tuple[SuccessCriteriaProgress, ...] = ()
    phase_summary: str = ""
    notes: str = ""

    @property
    def advances_state_machine(self) -> bool:
        """True iff the orchestrator should move to the next phase."""
        return self.outcome == PhaseOutcome.COMPLETED


class Phase(abc.ABC):
    """A single named phase in a campaign type's phase graph.

    Subclasses implement ``execute`` (do the work) and
    ``is_complete`` (deterministic harness check that stops the loop
    if a phase is internally iterative).
    """

    def __init__(self, definition: CampaignPhase) -> None:
        self._definition = definition

    @property
    def definition(self) -> CampaignPhase:
        return self._definition

    @abc.abstractmethod
    async def execute(self, context: PhaseExecutionContext) -> PhaseResult:
        """Run the phase end-to-end and return its result."""

    def is_complete(self, context: PhaseExecutionContext) -> bool:
        """Harness-driven completion check.

        Default implementation: the phase is complete when the most
        recent ``PhaseResult.outcome`` is ``COMPLETED``. Subclasses
        with internal iteration (e.g. Mythos exploit refinement)
        override this with their own deterministic exit conditions
        — sandbox verdict, verification envelope result, etc.

        Per D7: this method MUST NOT call the LLM. Termination is a
        deterministic property of campaign state.
        """
        latest = context.state.phase_history
        if not latest:
            return False
        return latest[-1].outcome == PhaseOutcome.COMPLETED


class CampaignWorker(abc.ABC):
    """Per-campaign-type worker.

    Defines the phase graph and how phases compose into a campaign
    run. Workers do NOT own state-machine transitions; the
    orchestrator drives those. Workers expose phases and the
    orchestrator picks up.
    """

    @property
    @abc.abstractmethod
    def campaign_type(self) -> CampaignType:
        """Which campaign type this worker handles."""

    @abc.abstractmethod
    def phase_graph(self) -> tuple[Phase, ...]:
        """Static, ordered list of phases for this campaign type.

        Returned tuple is the canonical phase graph; the orchestrator
        walks it left-to-right. Phase objects in this tuple may be
        reused across campaigns — they should not retain per-campaign
        state.
        """

    def get_phase(self, phase_id: str) -> Phase:
        """Look up a phase by id."""
        for phase in self.phase_graph():
            if phase.definition.phase_id == phase_id:
                return phase
        raise KeyError(
            f"No phase with id={phase_id!r} in {type(self).__name__}"
        )

    def first_phase(self) -> Phase:
        """The phase the orchestrator runs first."""
        graph = self.phase_graph()
        if not graph:
            raise ValueError(
                f"{type(self).__name__}.phase_graph() is empty"
            )
        return graph[0]

    def next_phase(self, current_phase_id: str) -> Phase | None:
        """The phase after ``current_phase_id``, or ``None`` if at the end."""
        graph = self.phase_graph()
        for i, phase in enumerate(graph):
            if phase.definition.phase_id == current_phase_id:
                if i + 1 < len(graph):
                    return graph[i + 1]
                return None
        raise KeyError(
            f"No phase with id={current_phase_id!r} in {type(self).__name__}"
        )
