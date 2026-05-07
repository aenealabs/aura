"""Frozen Reference Oracle contracts (ADR-088 Phase 2.2).

The oracle is the deterministic anchor that prevents recursive
degradation in Continuous Model Assurance: a candidate model is
scored against a fixed golden test set evaluated by programmatic
judges. The candidate cannot influence the criteria — that's why
mid-evaluation tampering with these contracts is impossible by
construction (every value type is frozen).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.services.model_assurance.axes import ModelAssuranceAxis


class TestCaseDomain(Enum):
    """The four golden-set domains from ADR-088 §Stage 4.

    Counts (minimum):
        VULNERABILITY_DETECTION  150 — top CWE: injection, auth fail, crypto
                                       misuse, deserialisation, SSRF
        PATCH_CORRECTNESS        100 — across language/framework combinations
        FALSE_POSITIVE            100 — known-clean code samples
        REGRESSION                50 — previously-correct outputs that must not
                                       degrade
    """

    VULNERABILITY_DETECTION = "vulnerability_detection"
    PATCH_CORRECTNESS = "patch_correctness"
    FALSE_POSITIVE = "false_positive"
    REGRESSION = "regression"


# Per-domain minimum case counts. Total minimum = 400 per ADR-088.
DOMAIN_MINIMUMS: dict[TestCaseDomain, int] = {
    TestCaseDomain.VULNERABILITY_DETECTION: 150,
    TestCaseDomain.PATCH_CORRECTNESS: 100,
    TestCaseDomain.FALSE_POSITIVE: 100,
    TestCaseDomain.REGRESSION: 50,
}

GOLDEN_SET_MINIMUM = sum(DOMAIN_MINIMUMS.values())  # 400


class JudgeKind(Enum):
    """How a judge produces its verdict.

    DETERMINISTIC  — output is a pure function of inputs (AST diff,
                     compile/test exit code, static-analysis findings).
                     Preferred where applicable; reproducible across
                     evaluation runs.
    LLM            — uses a pinned external model. Subject to the
                     guard rule ``candidate_model_id != judge_model_id``
                     to prevent recursive degradation.
    """

    DETERMINISTIC = "deterministic"
    LLM = "llm"


@dataclass(frozen=True)
class GoldenTestCase:
    """One ground-truth test case in the frozen golden set.

    Cases are content-addressed by ``case_id`` — once published a
    case is immutable. Modification produces a new case_id; the
    rotation pipeline tracks supersession explicitly.
    """

    case_id: str
    domain: TestCaseDomain
    title: str
    description: str
    # The tagged axis or axes this case primarily measures. A
    # vulnerability-detection case measures MA2; a patch case may
    # measure both MA3 (functional correctness) and MA4 (security
    # equivalence). Keeping the link explicit lets the oracle
    # service produce per-axis aggregates.
    axes: tuple[ModelAssuranceAxis, ...]
    # Programmatic ground truth — what the judge should compute the
    # candidate's response *should* be. The exact shape is judge-
    # specific (e.g. for AST-diff judges this might be the
    # canonicalised AST hash; for static-analysis judges it might be
    # the expected finding count).
    expected: tuple[tuple[str, str], ...] = ()
    # Optional CWE / SPDX / framework tags for reporting and
    # rotation balance.
    tags: tuple[str, ...] = ()
    # Provenance — where the case was sourced from and when. Used
    # by the rotation pipeline to balance the set against
    # production-incident additions.
    sourced_from: str = ""
    added_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("GoldenTestCase.case_id is required")
        if not self.axes:
            raise ValueError(
                f"GoldenTestCase {self.case_id!r}: at least one axis required"
            )

    @property
    def expected_dict(self) -> dict[str, str]:
        return dict(self.expected)


@dataclass(frozen=True)
class JudgeResult:
    """One judge's verdict on one case for one candidate."""

    case_id: str
    judge_id: str
    judge_kind: JudgeKind
    passed: bool
    confidence: float          # [0,1]; deterministic judges report 1.0
    reason: str = ""
    # Per-axis contribution this judge made for this case. The
    # oracle aggregator sums these per axis to compute MA1-MA6 raw
    # scores.
    axis_scores: tuple[tuple[ModelAssuranceAxis, float], ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"JudgeResult.confidence must be in [0,1]; "
                f"got {self.confidence}"
            )

    @property
    def axis_scores_dict(self) -> dict[ModelAssuranceAxis, float]:
        return dict(self.axis_scores)


@dataclass(frozen=True)
class OracleEvaluation:
    """Aggregate result of running the full oracle on a candidate."""

    candidate_id: str
    judge_results: tuple[JudgeResult, ...]
    per_axis_scores: tuple[tuple[ModelAssuranceAxis, float], ...]
    cases_evaluated: int
    cases_passed: int
    holdout_cases: tuple[str, ...] = ()  # case ids withheld this run
    evaluated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def per_axis_dict(self) -> dict[ModelAssuranceAxis, float]:
        return dict(self.per_axis_scores)

    @property
    def overall_pass_rate(self) -> float:
        if self.cases_evaluated == 0:
            return 0.0
        return self.cases_passed / self.cases_evaluated

    def to_audit_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "cases_evaluated": self.cases_evaluated,
            "cases_passed": self.cases_passed,
            "overall_pass_rate": round(self.overall_pass_rate, 6),
            "per_axis_scores": {
                ax.value: round(s, 6) for ax, s in self.per_axis_scores
            },
            "holdout_cases": list(self.holdout_cases),
            "evaluated_at": self.evaluated_at.isoformat(),
        }


@dataclass(frozen=True)
class GoldenSetIntegrityError(Exception):
    """Raised by the rotation/curation tooling when invariants break.

    Frozen+exception means we never mutate it after construction;
    the message survives pickle round-trips.
    """

    message: str
    detail: str = ""

    def __str__(self) -> str:  # type: ignore[override]
        if self.detail:
            return f"{self.message} ({self.detail})"
        return self.message
