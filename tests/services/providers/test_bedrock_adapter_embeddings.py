"""Tests for BedrockLLMAdapter embedding methods (Wave 4, #163).

Verifies the wave-4 wiring of ``generate_embedding`` and
``generate_embeddings_batch`` (previously ``NotImplementedError``)
delegates correctly to ``TitanEmbeddingService``.
"""

from __future__ import annotations

import pytest

from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter
from src.services.titan_embedding_service import EmbeddingMode, TitanEmbeddingService


@pytest.fixture
def adapter_with_mock_embeddings() -> BedrockLLMAdapter:
    """Adapter with the embedding delegate forced into MOCK mode."""
    adapter = BedrockLLMAdapter()
    adapter._embedding_service = TitanEmbeddingService(mode=EmbeddingMode.MOCK)
    return adapter


@pytest.mark.asyncio
async def test_generate_embedding_returns_1024d_vector(
    adapter_with_mock_embeddings: BedrockLLMAdapter,
) -> None:
    vector = await adapter_with_mock_embeddings.generate_embedding(
        "def hello(): print('world')"
    )

    assert isinstance(vector, list)
    assert len(vector) == 1024
    assert all(isinstance(x, (int, float)) for x in vector)


@pytest.mark.asyncio
async def test_generate_embedding_rejects_empty_text(
    adapter_with_mock_embeddings: BedrockLLMAdapter,
) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        await adapter_with_mock_embeddings.generate_embedding("")

    with pytest.raises(ValueError, match="non-empty"):
        await adapter_with_mock_embeddings.generate_embedding("   ")


@pytest.mark.asyncio
async def test_generate_embeddings_batch_returns_one_vector_per_input(
    adapter_with_mock_embeddings: BedrockLLMAdapter,
) -> None:
    inputs = ["alpha", "beta", "gamma"]

    vectors = await adapter_with_mock_embeddings.generate_embeddings_batch(inputs)

    assert len(vectors) == 3
    assert all(len(v) == 1024 for v in vectors)


@pytest.mark.asyncio
async def test_generate_embeddings_batch_empty_input(
    adapter_with_mock_embeddings: BedrockLLMAdapter,
) -> None:
    assert await adapter_with_mock_embeddings.generate_embeddings_batch([]) == []


@pytest.mark.asyncio
async def test_generate_embedding_uses_delegate_cache(
    adapter_with_mock_embeddings: BedrockLLMAdapter,
) -> None:
    """Same input twice should hit the delegate's TTLCache the second time."""
    adapter = adapter_with_mock_embeddings
    text = "cached embedding sample"

    v1 = await adapter.generate_embedding(text)
    v2 = await adapter.generate_embedding(text)

    # Mock mode is deterministic per-text, so vectors must match
    assert v1 == v2

    # Cache should report at least one hit on the second call
    service = adapter._embedding_service
    assert service is not None
    assert service.cache_hits >= 1


@pytest.mark.asyncio
async def test_embedding_service_reused_across_calls(
    adapter_with_mock_embeddings: BedrockLLMAdapter,
) -> None:
    """The lazily-built delegate must not be re-created on each call.

    The TTLCache lives on the instance; rebuilding it would defeat the
    cache entirely.
    """
    adapter = adapter_with_mock_embeddings
    service_before = adapter._embedding_service

    await adapter.generate_embedding("first")
    await adapter.generate_embedding("second")

    assert adapter._embedding_service is service_before


def test_embedding_service_rebuilt_when_model_id_changes(
    adapter_with_mock_embeddings: BedrockLLMAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Different ``model_id`` arg => new delegate instance.

    Patched at the constructor so the rebuild stays in MOCK mode.
    The real wiring would re-init against AWS; this test only
    verifies the cache-invalidation invariant.
    """
    original_init = TitanEmbeddingService.__init__

    def force_mock_init(self, *args, **kwargs):  # noqa: ANN001
        kwargs["mode"] = EmbeddingMode.MOCK
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(TitanEmbeddingService, "__init__", force_mock_init)

    adapter = adapter_with_mock_embeddings
    # Force a model_id mismatch to trigger rebuild
    adapter._embedding_service.model_id = "amazon.titan-embed-text-v2:0"
    first = adapter._embedding_service

    service = adapter._get_embedding_service("amazon.titan-embed-image-v1")

    assert service is not first
    assert service.model_id == "amazon.titan-embed-image-v1"
