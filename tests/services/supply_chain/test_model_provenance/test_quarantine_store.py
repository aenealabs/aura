"""Tests for the in-memory model quarantine store (ADR-088 Phase 2.1)."""

from __future__ import annotations

import threading

from src.services.supply_chain.model_provenance import (
    InMemoryModelQuarantineStore,
)


class TestBasicLifecycle:
    def test_empty_default(self) -> None:
        store = InMemoryModelQuarantineStore()
        assert store.is_quarantined("m") is False
        assert store.get("m") is None

    def test_quarantine_returns_entry(self) -> None:
        store = InMemoryModelQuarantineStore()
        entry = store.quarantine("m", "bad signature")
        assert entry.model_id == "m"
        assert entry.reason == "bad signature"
        assert entry.quarantine_id.startswith("mq-")

    def test_quarantine_is_idempotent(self) -> None:
        store = InMemoryModelQuarantineStore()
        a = store.quarantine("m", "first")
        b = store.quarantine("m", "second")
        assert a.quarantine_id == b.quarantine_id
        assert a.reason == b.reason  # original reason preserved

    def test_lift_removes_entry(self) -> None:
        store = InMemoryModelQuarantineStore()
        store.quarantine("m", "x")
        assert store.lift("m") is True
        assert store.is_quarantined("m") is False

    def test_lift_unknown_returns_false(self) -> None:
        store = InMemoryModelQuarantineStore()
        assert store.lift("never-was") is False


class TestQuarantineIdMonotonic:
    def test_ids_are_sequential(self) -> None:
        store = InMemoryModelQuarantineStore()
        a = store.quarantine("a", "")
        b = store.quarantine("b", "")
        c = store.quarantine("c", "")
        assert a.quarantine_id < b.quarantine_id < c.quarantine_id


class TestThreadSafety:
    def test_concurrent_quarantine(self) -> None:
        store = InMemoryModelQuarantineStore()

        def worker(i: int) -> None:
            store.quarantine(f"m-{i}", "concurrent")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(50):
            assert store.is_quarantined(f"m-{i}") is True

    def test_concurrent_idempotency(self) -> None:
        """Many threads quarantining the same model_id must agree on the ID."""
        store = InMemoryModelQuarantineStore()
        ids: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            entry = store.quarantine("shared", "race")
            with lock:
                ids.append(entry.quarantine_id)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(set(ids)) == 1
