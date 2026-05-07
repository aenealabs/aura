"""Frozen Reference Oracle service (ADR-088 Phase 2.2).

Top-level orchestrator. Per evaluation:

    1. Validate the golden set (400-case minimum, per-domain
       minimums, no duplicates).
    2. Sample a holdout per ADR-088 anti-Goodharting (20% default,
       cron-managed seed).
    3. For each remaining case, dispatch to every judge via
       :class:`JudgeRegistry`, gathering per-axis contributions.
    4. Aggregate per-axis scores by averaging across cases that
       have contributions from any judge for that axis.
    5. Return :class:`OracleEvaluation` with per-axis scores ready
       to be fed into the model_assurance evaluator (Phase 1.3).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Mapping, Sequence

from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle.contracts import (
    GoldenTestCase,
    JudgeResult,
    OracleEvaluation,
)
from src.services.model_assurance.frozen_oracle.golden_set import (
    GoldenTestSet,
)
from src.services.model_assurance.frozen_oracle.judges.contracts import (
    JudgeRegistry,
)

logger = logging.getLogger(__name__)


# Default holdout rate per ADR-088 §Stage 6.
DEFAULT_HOLDOUT_RATE = 0.20


class OracleService:
    """Stateless oracle service.

    Construction takes a frozen golden set and a judge registry.
    Evaluation is a pure function of (candidate_id, candidate_outputs,
    seed).
    """

    def __init__(
        self,
        *,
        golden_set: GoldenTestSet,
        judges: JudgeRegistry,
        holdout_rate: float = DEFAULT_HOLDOUT_RATE,
    ) -> None:
        self._golden_set = golden_set
        self._judges = judges
        self._holdout_rate = holdout_rate
        # Validate at construction so the service can never be
        # instantiated against an invalid set.
        golden_set.validate_minimums()

    @property
    def golden_set(self) -> GoldenTestSet:
        return self._golden_set

    @property
    def judges(self) -> JudgeRegistry:
        return self._judges

    def evaluate(
        self,
        *,
        candidate_id: str,
        candidate_outputs: Mapping[str, Sequence[object]],
        seed: int,
    ) -> OracleEvaluation:
        """Run every judge against every case (minus holdout).

        ``candidate_outputs`` maps ``judge_id`` → sequence of judge-
        specific candidate-output objects. Each object's ``case_id``
        identifies which case it addresses; the oracle dispatches
        accordingly. Cases without a matching candidate output for
        a given judge are recorded as a fail for that judge (the
        candidate failed to produce an answer).
        """
        holdout_ids, eval_cases = self._golden_set.holdout_sample(
            rate=self._holdout_rate, seed=seed
        )
        holdout_set = set(holdout_ids)

        # Build per-judge case_id index for O(1) lookup.
        per_judge_outputs: dict[str, dict[str, object]] = {
            judge_id: {getattr(o, "case_id"): o for o in outs}
            for judge_id, outs in candidate_outputs.items()
        }

        all_results: list[JudgeResult] = []
        # Per-axis running sums for averaging.
        axis_sums: dict[ModelAssuranceAxis, float] = {
            ax: 0.0 for ax in ModelAssuranceAxis
        }
        axis_counts: dict[ModelAssuranceAxis, int] = {
            ax: 0 for ax in ModelAssuranceAxis
        }
        cases_passed = 0
        cases_evaluated = 0

        for case in eval_cases:
            if case.case_id in holdout_set:
                continue  # belt-and-braces; eval_cases already excludes
            cases_evaluated += 1
            case_passed_overall = True

            for judge in self._judges.all_judges():
                output = per_judge_outputs.get(judge.judge_id, {}).get(
                    case.case_id
                )
                if output is None:
                    # Missing output for this (judge, case) pair —
                    # treat as a fail for that judge on this case.
                    result = JudgeResult(
                        case_id=case.case_id,
                        judge_id=judge.judge_id,
                        judge_kind=judge.judge_kind,
                        passed=False,
                        confidence=1.0,
                        reason="no candidate output for this judge",
                    )
                else:
                    result = judge.evaluate(case=case, candidate_output=output)

                all_results.append(result)
                if not result.passed:
                    case_passed_overall = False
                for ax, contribution in result.axis_scores:
                    axis_sums[ax] += contribution
                    axis_counts[ax] += 1

            if case_passed_overall:
                cases_passed += 1

        per_axis_scores = tuple(
            (ax, axis_sums[ax] / axis_counts[ax] if axis_counts[ax] else 0.0)
            for ax in ModelAssuranceAxis
        )

        return OracleEvaluation(
            candidate_id=candidate_id,
            judge_results=tuple(all_results),
            per_axis_scores=per_axis_scores,
            cases_evaluated=cases_evaluated,
            cases_passed=cases_passed,
            holdout_cases=tuple(holdout_ids),
        )
