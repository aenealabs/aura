"""Tests for evaluate_convergence (ADR-085 Phase 1)."""

from __future__ import annotations

from src.services.verification_envelope.consensus.ast_normalizer import ASTNormalizer
from src.services.verification_envelope.consensus.consensus_policy import (
    evaluate_convergence,
)
from src.services.verification_envelope.contracts import (
    ConsensusOutcome,
    EquivalenceCheck,
)


def _eq(eq: bool, sim: float = 1.0, method: str = "ast_exact") -> EquivalenceCheck:
    return EquivalenceCheck(
        are_equivalent=eq, method=method, similarity=sim, rationale=""
    )


def _matrix(n: int, equiv_pairs: set[tuple[int, int]]) -> list[list[EquivalenceCheck]]:
    rows: list[list[EquivalenceCheck]] = []
    for i in range(n):
        row: list[EquivalenceCheck] = []
        for j in range(n):
            if i == j:
                row.append(_eq(True, 1.0, "self"))
            elif (min(i, j), max(i, j)) in equiv_pairs:
                row.append(_eq(True, 1.0, "ast_exact"))
            else:
                row.append(_eq(False, 0.5, "ast_dump"))
        rows.append(row)
    return rows


def _forms(*sources: str):
    return tuple(ASTNormalizer().normalize(s) for s in sources)


def test_three_identical_outputs_converge() -> None:
    sources = ("def f(): return 1\n",) * 3
    forms = _forms(*sources)
    pairwise = _matrix(3, {(0, 1), (0, 2), (1, 2)})
    decision = evaluate_convergence(
        candidates=sources,
        canonical_forms=forms,
        pairwise=pairwise,
        m_required=2,
    )
    assert decision.outcome == ConsensusOutcome.CONVERGED
    assert decision.selected_index in (0, 1, 2)
    assert decision.selection_method == "ast_centroid"


def test_two_of_three_converge_meets_threshold() -> None:
    sources = (
        "def f(): return 1\n",
        "def f(): return 1\n",
        "def f(): return 99\n",
    )
    forms = _forms(*sources)
    pairwise = _matrix(3, {(0, 1)})
    decision = evaluate_convergence(
        candidates=sources,
        canonical_forms=forms,
        pairwise=pairwise,
        m_required=2,
    )
    assert decision.outcome == ConsensusOutcome.CONVERGED
    assert decision.selected_index in (0, 1)


def test_one_of_three_below_threshold_diverges() -> None:
    sources = (
        "def f(): return 1\n",
        "def f(): return 2\n",
        "def f(): return 3\n",
    )
    forms = _forms(*sources)
    pairwise = _matrix(3, set())  # nothing equivalent
    decision = evaluate_convergence(
        candidates=sources,
        canonical_forms=forms,
        pairwise=pairwise,
        m_required=2,
    )
    assert decision.outcome == ConsensusOutcome.DIVERGED
    assert decision.selected_index is None
    assert decision.selection_method == "none"


def test_centroid_selection_is_deterministic_for_equal_clusters() -> None:
    """Identical cluster members → tie-break by lowest canonical hash."""
    sources = ("def f(): return 1\n",) * 3
    forms = _forms(*sources)
    pairwise = _matrix(3, {(0, 1), (0, 2), (1, 2)})
    decision_a = evaluate_convergence(
        candidates=sources,
        canonical_forms=forms,
        pairwise=pairwise,
        m_required=2,
    )
    decision_b = evaluate_convergence(
        candidates=sources,
        canonical_forms=forms,
        pairwise=pairwise,
        m_required=2,
    )
    assert decision_a.selected_index == decision_b.selected_index


def test_embedding_centroid_method_when_cluster_used_embedding() -> None:
    sources = ("def f(): return 1\n",) * 2 + ("def f(): return 99\n",)
    forms = _forms(*sources)
    pairwise = _matrix(3, {(0, 1)})
    # Mark the (0,1) edge as embedding-based to exercise that branch.
    pairwise[0][1] = EquivalenceCheck(
        are_equivalent=True,
        method="embedding_cosine",
        similarity=0.99,
        rationale="",
    )
    pairwise[1][0] = pairwise[0][1]
    decision = evaluate_convergence(
        candidates=sources,
        canonical_forms=forms,
        pairwise=pairwise,
        m_required=2,
    )
    assert decision.outcome == ConsensusOutcome.CONVERGED
    assert decision.selection_method == "embedding_centroid"
