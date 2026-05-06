"""Unit tests for the DVE config dataclass."""

from __future__ import annotations

import pytest

from src.services.verification_envelope.config import DVEConfig


def test_for_testing_returns_tight_defaults() -> None:
    cfg = DVEConfig.for_testing()
    assert cfg.consensus_n == 3
    assert cfg.consensus_m == 2
    assert cfg.consensus_temperature == 0.0
    assert cfg.consensus_timeout_seconds == 10.0


def test_for_production_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DVE_CONSENSUS_N", "5")
    monkeypatch.setenv("DVE_CONSENSUS_M", "3")
    monkeypatch.setenv("DVE_CONSENSUS_TEMP", "0.5")
    cfg = DVEConfig.for_production()
    assert cfg.consensus_n == 5
    assert cfg.consensus_m == 3
    assert cfg.consensus_temperature == 0.5


def test_post_init_rejects_zero_n() -> None:
    with pytest.raises(ValueError, match="consensus_n"):
        DVEConfig(consensus_n=0, consensus_m=1)


def test_post_init_rejects_m_greater_than_n() -> None:
    with pytest.raises(ValueError, match="consensus_m"):
        DVEConfig(consensus_n=2, consensus_m=3)


def test_post_init_rejects_negative_temperature() -> None:
    with pytest.raises(ValueError, match="temperature"):
        DVEConfig(consensus_n=3, consensus_m=2, consensus_temperature=-0.1)


def test_post_init_rejects_invalid_cosine_threshold() -> None:
    with pytest.raises(ValueError, match="cosine_threshold"):
        DVEConfig(consensus_n=3, consensus_m=2, embedding_cosine_threshold=1.5)
