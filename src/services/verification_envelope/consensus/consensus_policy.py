"""Project Aura - Consensus policy helpers (ADR-085 Phase 1).

Encapsulates the M-of-N convergence decision in one well-tested
function so the consensus service stays focused on orchestration. The
centroid-selection algorithm picks the output whose AST canonical form
has the minimum total edit distance to all *other* converging
outputs. For a pure-AST-hash-equivalence cluster the distance is
trivially 0 within the cluster, so any member is the centroid; we
break ties by lowest canonical_hash (stable, deterministic).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.services.verification_envelope.contracts import (
    ASTCanonicalForm,
    ConsensusOutcome,
    EquivalenceCheck,
)


@dataclass(frozen=True)
class _ClusterMember:
    index: int
    canonical: ASTCanonicalForm
    raw_output: str


@dataclass(frozen=True)
class ConsensusDecision:
    """Outcome of running the M-of-N policy on N candidates."""

    outcome: ConsensusOutcome
    converged_indices: tuple[int, ...]
    selected_index: int | None
    selection_method: str  # "ast_centroid" | "embedding_centroid" | "none"


def evaluate_convergence(
    *,
    candidates: Sequence[str],
    canonical_forms: Sequence[ASTCanonicalForm],
    pairwise: Sequence[Sequence[EquivalenceCheck]],
    m_required: int,
) -> ConsensusDecision:
    """Decide whether ``m_required`` of ``len(candidates)`` candidates converged.

    ``pairwise[i][j]`` is the equivalence check between candidates i
    and j. The diagonal is ignored. Identifies the largest equivalence
    cluster and, if it meets the M threshold, returns its centroid.
    """
    n = len(candidates)
    if n != len(canonical_forms):
        raise ValueError(
            f"candidates ({n}) and canonical_forms ({len(canonical_forms)}) "
            "must be the same length"
        )
    if any(len(row) != n for row in pairwise):
        raise ValueError("pairwise must be an N×N matrix")

    # Build adjacency from the equivalence matrix.
    adj: list[set[int]] = [set() for _ in range(n)]
    for i in range(n):
        adj[i].add(i)  # An output is equivalent to itself.
        for j in range(i + 1, n):
            if pairwise[i][j].are_equivalent:
                adj[i].add(j)
                adj[j].add(i)

    # Connected components.
    visited: set[int] = set()
    components: list[list[int]] = []
    for start in range(n):
        if start in visited:
            continue
        stack = [start]
        comp: list[int] = []
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.append(cur)
            stack.extend(adj[cur] - visited)
        components.append(sorted(comp))

    components.sort(key=lambda c: (-len(c), c))
    largest = components[0] if components else []

    if len(largest) < m_required:
        return ConsensusDecision(
            outcome=ConsensusOutcome.DIVERGED,
            converged_indices=tuple(largest),
            selected_index=None,
            selection_method="none",
        )

    selected_index, method = _select_centroid(
        cluster=largest,
        canonical_forms=canonical_forms,
        pairwise=pairwise,
    )

    outcome = (
        ConsensusOutcome.CONVERGED
        if len(largest) >= m_required
        else ConsensusOutcome.PARTIAL
    )
    return ConsensusDecision(
        outcome=outcome,
        converged_indices=tuple(largest),
        selected_index=selected_index,
        selection_method=method,
    )


def _select_centroid(
    *,
    cluster: Sequence[int],
    canonical_forms: Sequence[ASTCanonicalForm],
    pairwise: Sequence[Sequence[EquivalenceCheck]],
) -> tuple[int, str]:
    """Pick the cluster member with maximum total similarity to the others.

    For pure-AST equivalence clusters (similarity 1.0 within), this
    degenerates to a deterministic tie-break by lowest canonical hash.
    """
    if len(cluster) == 1:
        return cluster[0], "ast_centroid"

    best_index = cluster[0]
    best_score = -1.0
    best_hash = canonical_forms[best_index].canonical_hash
    used_embedding = False

    for i in cluster:
        score = 0.0
        for j in cluster:
            if i == j:
                continue
            check = pairwise[i][j]
            score += check.similarity
            if check.method == "embedding_cosine":
                used_embedding = True
        # Lower hash wins ties so the choice is stable.
        cur_hash = canonical_forms[i].canonical_hash
        if score > best_score or (
            score == best_score and cur_hash < best_hash
        ):
            best_index = i
            best_score = score
            best_hash = cur_hash

    method = "embedding_centroid" if used_embedding else "ast_centroid"
    return best_index, method
