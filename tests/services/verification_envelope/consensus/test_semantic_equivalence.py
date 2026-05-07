"""Tests for the semantic equivalence checker."""

from __future__ import annotations

from typing import Sequence

import pytest

from src.services.verification_envelope.consensus.ast_normalizer import ASTNormalizer
from src.services.verification_envelope.consensus.semantic_equivalence import (
    SemanticEquivalenceChecker,
)


class _FakeEmbedding:
    """Stub embedding provider returning configurable vectors per text."""

    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self._mapping = mapping
        self.calls: list[str] = []

    async def generate_embedding(self, text: str) -> Sequence[float]:
        self.calls.append(text)
        return self._mapping.get(text, [0.0, 0.0, 1.0])


@pytest.mark.asyncio
async def test_identical_sources_match_via_ast_exact() -> None:
    a = ASTNormalizer().normalize("def f(x): return x + 1\n")
    b = ASTNormalizer().normalize("def f(x): return x + 1\n")
    checker = SemanticEquivalenceChecker(
        embedding_provider=None, enable_embedding_fallback=False
    )
    result = await checker.check(a, b)
    assert result.are_equivalent is True
    assert result.method == "ast_exact"
    assert result.similarity == 1.0


@pytest.mark.asyncio
async def test_renamed_args_match_via_ast_exact() -> None:
    a = ASTNormalizer().normalize("def f(a):\n    return a + 1\n")
    b = ASTNormalizer().normalize("def f(z):\n    return z + 1\n")
    checker = SemanticEquivalenceChecker(
        embedding_provider=None, enable_embedding_fallback=False
    )
    result = await checker.check(a, b)
    assert result.are_equivalent is True
    assert result.method == "ast_exact"


@pytest.mark.asyncio
async def test_structurally_different_falls_back_to_embedding() -> None:
    a = ASTNormalizer().normalize("def f(xs): return [x*2 for x in xs]\n")
    b = ASTNormalizer().normalize(
        "def f(xs):\n"
        "    out = []\n"
        "    for x in xs:\n"
        "        out.append(x*2)\n"
        "    return out\n"
    )
    embedder = _FakeEmbedding(
        {a.canonical_dump: [1.0, 0.0, 0.0], b.canonical_dump: [1.0, 0.0, 0.0]}
    )
    checker = SemanticEquivalenceChecker(
        embedding_provider=embedder,
        cosine_threshold=0.9,
        enable_embedding_fallback=True,
    )
    result = await checker.check(a, b)
    assert result.are_equivalent is True
    assert result.method == "embedding_cosine"
    assert result.similarity > 0.99


@pytest.mark.asyncio
async def test_embedding_below_threshold_marked_not_equivalent() -> None:
    a = ASTNormalizer().normalize("def f(): return 1\n")
    b = ASTNormalizer().normalize("def g(): return 'x'\n")
    embedder = _FakeEmbedding(
        {a.canonical_dump: [1.0, 0.0, 0.0], b.canonical_dump: [0.0, 1.0, 0.0]}
    )
    checker = SemanticEquivalenceChecker(
        embedding_provider=embedder,
        cosine_threshold=0.9,
        enable_embedding_fallback=True,
    )
    result = await checker.check(a, b)
    assert result.are_equivalent is False
    assert result.method == "embedding_cosine"


@pytest.mark.asyncio
async def test_fallback_disabled_returns_not_equivalent_when_hashes_differ() -> None:
    a = ASTNormalizer().normalize("def f(): return 1\n")
    b = ASTNormalizer().normalize("def f(): return 2\n")
    checker = SemanticEquivalenceChecker(
        embedding_provider=None, enable_embedding_fallback=False
    )
    result = await checker.check(a, b)
    assert result.are_equivalent is False
    assert result.method == "ast_dump"


@pytest.mark.asyncio
async def test_parse_failure_short_circuits() -> None:
    a = ASTNormalizer().normalize("def f(: bad\n")
    b = ASTNormalizer().normalize("def f(): return 1\n")
    checker = SemanticEquivalenceChecker(
        embedding_provider=None, enable_embedding_fallback=False
    )
    result = await checker.check(a, b)
    assert result.are_equivalent is False
    assert result.method == "parse_fail"
