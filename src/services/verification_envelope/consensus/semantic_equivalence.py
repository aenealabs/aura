"""Project Aura - Semantic equivalence check (ADR-085 Phase 1).

Two-stage equivalence: AST canonical hash for the fast path, then
embedding cosine for outputs that are semantically equivalent but
structurally different (e.g. ``for`` loop vs list comprehension).

The embedding service is injected so the consensus engine remains
testable without Bedrock. A protocol-based stub is provided for unit
tests; production wires :class:`BedrockLLMService` (or any service
exposing ``generate_embedding``).
"""

from __future__ import annotations

import logging
import math
from typing import Protocol, Sequence

from src.services.verification_envelope.contracts import (
    ASTCanonicalForm,
    EquivalenceCheck,
)

logger = logging.getLogger(__name__)


class _EmbeddingProvider(Protocol):
    """Protocol for an async embedding source.

    ``generate_embedding`` is the established BedrockLLMService method.
    Anything implementing the same shape works.
    """

    async def generate_embedding(self, text: str) -> Sequence[float]: ...


class SemanticEquivalenceChecker:
    """Checks whether two normalised outputs are semantically equivalent.

    Decision flow (per ADR-085 Pillar 1):

    1. Both forms parsed successfully and canonical hashes match
       → equivalent (fast path; method=``ast_exact``).
    2. Both forms parsed successfully but canonical hashes differ AND
       embedding fallback is enabled → cosine similarity on the
       canonical dumps (method=``embedding_cosine``).
    3. Either form failed to parse → not equivalent
       (method=``parse_fail``).

    The embedding fallback is intentionally invoked on the canonical
    *dump string* rather than the original source. Working on the
    canonical form means trivial whitespace/naming differences don't
    spuriously change the embedding, so the threshold can be tighter.
    """

    def __init__(
        self,
        embedding_provider: _EmbeddingProvider | None,
        *,
        cosine_threshold: float = 0.97,
        enable_embedding_fallback: bool = True,
    ) -> None:
        self._embedding = embedding_provider
        self._cosine_threshold = cosine_threshold
        self._enable_embedding_fallback = enable_embedding_fallback

    async def check(
        self, a: ASTCanonicalForm, b: ASTCanonicalForm
    ) -> EquivalenceCheck:
        if not (a.parse_succeeded and b.parse_succeeded):
            return EquivalenceCheck(
                are_equivalent=False,
                method="parse_fail",
                similarity=0.0,
                rationale=(
                    f"parse_succeeded a={a.parse_succeeded} b={b.parse_succeeded}: "
                    f"{a.parse_error or ''} | {b.parse_error or ''}"
                ).strip(),
            )

        if a.canonical_hash and a.canonical_hash == b.canonical_hash:
            return EquivalenceCheck(
                are_equivalent=True,
                method="ast_exact",
                similarity=1.0,
                rationale="canonical hashes match",
            )

        # Light sanity check: identical canonical_dump strings imply matching
        # hashes; a mismatch here would indicate an internal hashing bug.
        if a.canonical_dump and a.canonical_dump == b.canonical_dump:
            return EquivalenceCheck(
                are_equivalent=True,
                method="ast_dump",
                similarity=1.0,
                rationale="canonical dumps match (defensive check)",
            )

        if not self._enable_embedding_fallback or self._embedding is None:
            return EquivalenceCheck(
                are_equivalent=False,
                method="ast_dump",
                similarity=0.0,
                rationale="canonical hashes differ; embedding fallback disabled",
            )

        try:
            emb_a = await self._embedding.generate_embedding(a.canonical_dump)
            emb_b = await self._embedding.generate_embedding(b.canonical_dump)
        except Exception as exc:  # pragma: no cover — provider failure
            logger.warning("embedding fallback failed: %s", exc)
            return EquivalenceCheck(
                are_equivalent=False,
                method="embedding_cosine",
                similarity=0.0,
                rationale=f"embedding fallback raised: {exc}",
            )

        sim = _cosine(emb_a, emb_b)
        return EquivalenceCheck(
            are_equivalent=sim >= self._cosine_threshold,
            method="embedding_cosine",
            similarity=sim,
            rationale=(
                f"cosine={sim:.4f} threshold={self._cosine_threshold:.4f}"
            ),
        )


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
