"""Tests for InMemoryScoutStateStore (ADR-088 Phase 1.4)."""

from __future__ import annotations

import threading

from src.services.model_assurance.scout import InMemoryScoutStateStore


class TestSnapshot:
    def test_empty_default(self) -> None:
        s = InMemoryScoutStateStore()
        snap = s.snapshot()
        assert snap.active_evaluations == frozenset()
        assert snap.rejected == frozenset()
        assert snap.pending_availability == frozenset()
        assert snap.incumbent_ids == frozenset()

    def test_initial_incumbents_seeded(self) -> None:
        s = InMemoryScoutStateStore(initial_incumbents=frozenset({"m1"}))
        assert "m1" in s.snapshot().incumbent_ids

    def test_initial_rejected_seeded(self) -> None:
        s = InMemoryScoutStateStore(initial_rejected=frozenset({"m1"}))
        assert "m1" in s.snapshot().rejected


class TestActiveEvaluations:
    def test_mark_active(self) -> None:
        s = InMemoryScoutStateStore()
        s.mark_active("cand-1")
        assert "cand-1" in s.snapshot().active_evaluations

    def test_complete_accepted_promotes_to_incumbent(self) -> None:
        s = InMemoryScoutStateStore()
        s.mark_active("cand-1")
        s.mark_evaluation_complete("cand-1", accepted=True)
        snap = s.snapshot()
        assert "cand-1" not in snap.active_evaluations
        assert "cand-1" in snap.incumbent_ids
        assert "cand-1" not in snap.rejected

    def test_complete_rejected_marks_sticky_rejection(self) -> None:
        s = InMemoryScoutStateStore()
        s.mark_active("cand-1")
        s.mark_evaluation_complete("cand-1", accepted=False)
        snap = s.snapshot()
        assert "cand-1" not in snap.active_evaluations
        assert "cand-1" in snap.rejected


class TestPendingAvailability:
    def test_mark_pending(self) -> None:
        s = InMemoryScoutStateStore()
        s.mark_pending_availability("future-model")
        assert "future-model" in s.snapshot().pending_availability

    def test_clear_pending(self) -> None:
        s = InMemoryScoutStateStore()
        s.mark_pending_availability("future-model")
        s.clear_pending("future-model")
        assert "future-model" not in s.snapshot().pending_availability

    def test_clear_pending_unknown_safe(self) -> None:
        """clear_pending on unknown model is a no-op, not an error."""
        s = InMemoryScoutStateStore()
        s.clear_pending("never-was-pending")  # must not raise


class TestRejectionLifecycle:
    def test_lift_rejection_admin_escape_hatch(self) -> None:
        s = InMemoryScoutStateStore(initial_rejected=frozenset({"bad"}))
        s.lift_rejection("bad")
        assert "bad" not in s.snapshot().rejected

    def test_lift_unknown_safe(self) -> None:
        InMemoryScoutStateStore().lift_rejection("never-rejected")


class TestThreadSafety:
    def test_concurrent_writes_settle_correctly(self) -> None:
        s = InMemoryScoutStateStore()

        def worker(i: int) -> None:
            s.mark_active(f"cand-{i}")
            s.mark_evaluation_complete(f"cand-{i}", accepted=(i % 2 == 0))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snap = s.snapshot()
        assert len(snap.incumbent_ids) == 25
        assert len(snap.rejected) == 25
        assert snap.active_evaluations == frozenset()
