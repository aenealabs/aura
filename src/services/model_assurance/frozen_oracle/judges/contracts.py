"""Judge protocol + registry (ADR-088 Phase 2.2)."""

from __future__ import annotations

from typing import Protocol

from src.services.model_assurance.frozen_oracle.contracts import (
    GoldenTestCase,
    JudgeKind,
    JudgeResult,
)


class CandidateOutput(Protocol):
    """Anything a judge needs to know about the candidate's response.

    Concrete shape is judge-specific — kept loose at the contract
    level so different judges can ask for different artefact
    fields without the oracle service knowing details.
    """

    case_id: str  # which golden case this output addresses


class Judge(Protocol):
    """A judge that turns ``(case, candidate_output)`` into a JudgeResult.

    Implementations are expected to be share-safe and stateless —
    if a judge needs configuration, supply it at construction.
    """

    judge_id: str
    judge_kind: JudgeKind

    def evaluate(
        self,
        *,
        case: GoldenTestCase,
        candidate_output: CandidateOutput,
    ) -> JudgeResult: ...


class JudgeRegistry:
    """Per-domain judge dispatch.

    The oracle service routes a (case, output) pair to every judge
    registered for the case's domain. Multiple judges per domain
    are supported — the aggregator sums per-axis contributions.

    Mutation rules:
        * No silent override on register — a duplicate ``judge_id``
          raises ``ValueError``.
        * No global registry singleton; tests construct their own.
    """

    def __init__(self) -> None:
        self._judges: dict[str, Judge] = {}

    def register(self, judge: Judge) -> None:
        if judge.judge_id in self._judges:
            raise ValueError(
                f"Judge with id={judge.judge_id!r} already registered"
            )
        self._judges[judge.judge_id] = judge

    def unregister(self, judge_id: str) -> Judge:
        if judge_id not in self._judges:
            raise KeyError(f"No judge registered under id={judge_id!r}")
        return self._judges.pop(judge_id)

    def get(self, judge_id: str) -> Judge:
        if judge_id not in self._judges:
            raise KeyError(f"No judge registered under id={judge_id!r}")
        return self._judges[judge_id]

    def __contains__(self, judge_id: object) -> bool:
        return isinstance(judge_id, str) and judge_id in self._judges

    def __len__(self) -> int:
        return len(self._judges)

    def all_judges(self) -> tuple[Judge, ...]:
        return tuple(self._judges.values())

    def deterministic_judges(self) -> tuple[Judge, ...]:
        return tuple(
            j
            for j in self._judges.values()
            if j.judge_kind is JudgeKind.DETERMINISTIC
        )

    def llm_judges(self) -> tuple[Judge, ...]:
        return tuple(
            j
            for j in self._judges.values()
            if j.judge_kind is JudgeKind.LLM
        )
