"""Tests for the RevisionHistory append-only log (ADR-088 Phase 3.3)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.rollback import (
    ConfigRevision,
    RevisionHistory,
)


def _rev(rid: str, model: str = "m") -> ConfigRevision:
    return ConfigRevision(revision_id=rid, model_id=model)


class TestAppendAndRead:
    def test_empty_default(self) -> None:
        h = RevisionHistory()
        assert len(h) == 0
        assert h.latest() is None

    def test_append_increments_len(self) -> None:
        h = RevisionHistory()
        h.append(_rev("r1"))
        h.append(_rev("r2"))
        assert len(h) == 2

    def test_latest_returns_most_recent(self) -> None:
        h = RevisionHistory()
        h.append(_rev("r1"))
        h.append(_rev("r2"))
        assert h.latest().revision_id == "r2"  # type: ignore[union-attr]

    def test_duplicate_revision_id_rejected(self) -> None:
        h = RevisionHistory()
        h.append(_rev("r1"))
        with pytest.raises(ValueError, match="already in history"):
            h.append(_rev("r1"))


class TestNthBack:
    def test_n_back_zero_is_latest(self) -> None:
        h = RevisionHistory()
        h.append(_rev("r1"))
        h.append(_rev("r2"))
        assert h.nth_back(0).revision_id == "r2"  # type: ignore[union-attr]

    def test_n_back_one_is_previous(self) -> None:
        h = RevisionHistory()
        h.append(_rev("r1"))
        h.append(_rev("r2"))
        h.append(_rev("r3"))
        assert h.nth_back(1).revision_id == "r2"  # type: ignore[union-attr]

    def test_n_back_two_is_n_minus_2(self) -> None:
        h = RevisionHistory()
        h.append(_rev("r1"))
        h.append(_rev("r2"))
        h.append(_rev("r3"))
        assert h.nth_back(2).revision_id == "r1"  # type: ignore[union-attr]

    def test_n_back_beyond_history_returns_none(self) -> None:
        h = RevisionHistory()
        h.append(_rev("r1"))
        assert h.nth_back(5) is None

    def test_negative_n_rejected(self) -> None:
        h = RevisionHistory()
        h.append(_rev("r1"))
        with pytest.raises(ValueError):
            h.nth_back(-1)


class TestFind:
    def test_find_known(self) -> None:
        h = RevisionHistory()
        h.append(_rev("r1"))
        assert h.find("r1") is not None

    def test_find_unknown(self) -> None:
        h = RevisionHistory()
        assert h.find("r-missing") is None


class TestThreadSafety:
    def test_concurrent_append(self) -> None:
        import threading

        h = RevisionHistory()

        def worker(i: int) -> None:
            h.append(_rev(f"r-{i:04d}"))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(h) == 50


class TestSnapshot:
    def test_all_returns_immutable_tuple(self) -> None:
        h = RevisionHistory()
        h.append(_rev("r1"))
        h.append(_rev("r2"))
        snap = h.all()
        assert isinstance(snap, tuple)
        assert [r.revision_id for r in snap] == ["r1", "r2"]
