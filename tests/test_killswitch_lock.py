"""Tests for ``scripts/killswitch_lock.py``.

Issue #186 cluster C3: concurrent-run guard for ``dev_killswitch.py``
and ``qa_killswitch.py``. These tests pin the contract every caller
relies on:

* Acquire succeeds when the lock is free.
* Acquire raises :class:`KillSwitchLockHeldError` on a second concurrent
  attempt and identifies the existing holder.
* The lock is released on context-manager exit, including on exception
  paths, so a new acquire after a clean exit succeeds.
* The lock is released by the kernel when the holding process exits
  (the realistic crash-recovery path).
* Sibling locks (different ``name=``) do not block each other -- a DEV
  and QA teardown can run concurrently.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import pytest

# Make ``scripts/`` importable as a top-level module path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from killswitch_lock import (  # noqa: E402
    KillSwitchLock,
    KillSwitchLockHeldError,
    LockHolder,
)


def test_acquire_succeeds_on_clean_dir(tmp_path: Path) -> None:
    with KillSwitchLock("alpha", command="shutdown", lock_dir=tmp_path):
        # No raise == success. The lock file should exist on disk.
        assert (tmp_path / "alpha.lock").exists()


def test_holder_block_is_written(tmp_path: Path) -> None:
    with KillSwitchLock("beta", command="restore", lock_dir=tmp_path):
        body = (tmp_path / "beta.lock").read_text(encoding="utf-8")
        data = json.loads(body)
        assert data["command"] == "restore"
        assert isinstance(data["pid"], int) and data["pid"] > 0
        assert isinstance(data["hostname"], str) and data["hostname"]
        assert data["acquired_at"].endswith("+00:00")


def test_lock_file_is_removed_on_clean_exit(tmp_path: Path) -> None:
    with KillSwitchLock("gamma", lock_dir=tmp_path):
        assert (tmp_path / "gamma.lock").exists()
    assert not (tmp_path / "gamma.lock").exists()


def test_lock_file_is_removed_on_exception_exit(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        with KillSwitchLock("delta", lock_dir=tmp_path):
            raise RuntimeError("boom")
    assert not (tmp_path / "delta.lock").exists()


def test_second_acquire_in_same_process_raises(tmp_path: Path) -> None:
    with KillSwitchLock("epsilon", command="shutdown", lock_dir=tmp_path):
        with pytest.raises(KillSwitchLockHeldError) as excinfo:
            with KillSwitchLock("epsilon", command="shutdown", lock_dir=tmp_path):
                pass
        msg = str(excinfo.value)
        assert "command=shutdown" in msg
        assert "pid=" in msg
        assert str(tmp_path / "epsilon.lock") in msg


def test_acquire_after_release_succeeds(tmp_path: Path) -> None:
    with KillSwitchLock("zeta", lock_dir=tmp_path):
        pass
    # Second acquire after the first has released should work.
    with KillSwitchLock("zeta", lock_dir=tmp_path):
        pass


def test_different_names_do_not_block_each_other(tmp_path: Path) -> None:
    # The whole point of the ``name`` parameter is that DEV and QA
    # kill-switches can run in parallel.
    with KillSwitchLock("dev-killswitch", lock_dir=tmp_path):
        with KillSwitchLock("qa-killswitch", lock_dir=tmp_path):
            # Both locks held simultaneously -- no raise.
            assert (tmp_path / "dev-killswitch.lock").exists()
            assert (tmp_path / "qa-killswitch.lock").exists()


def test_invalid_name_rejected_path_traversal(tmp_path: Path) -> None:
    for bad in ("a/b", "..", "with\0null", "back\\slash"):
        with pytest.raises(ValueError, match="invalid lock name"):
            KillSwitchLock(bad, lock_dir=tmp_path)


def test_invalid_name_rejected_empty(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid lock name"):
        KillSwitchLock("", lock_dir=tmp_path)


def test_lock_holder_now_populates_fields() -> None:
    holder = LockHolder.now("shutdown")
    assert holder.command == "shutdown"
    assert holder.pid > 0
    assert holder.hostname
    # Round-trip the timestamp to confirm it is parseable ISO-8601.
    from datetime import datetime

    parsed = datetime.fromisoformat(holder.acquired_at)
    assert parsed.tzinfo is not None


# ---------------------------------------------------------------------------
# Cross-process tests -- the realistic threat model is two processes,
# not two threads in the same process. ``multiprocessing.Process`` gives
# us real OS-level forks so the kernel-side lock state is exercised.
# ---------------------------------------------------------------------------


def _child_hold_then_signal(lock_dir: str, name: str, ready_path: str) -> None:
    """Child target: acquire the lock, signal ready, sleep, release."""
    with KillSwitchLock(name, command="shutdown", lock_dir=Path(lock_dir)):
        Path(ready_path).write_text("ready", encoding="utf-8")
        time.sleep(2.0)


def test_second_acquire_in_separate_process_raises(tmp_path: Path) -> None:
    """A concurrent process attempting to acquire the same lock raises.

    This is the exact threat model that issue #186 cluster C3 describes:
    two operators (or one operator double-clicking) race the destructive
    phase. The kernel-level ``fcntl.flock`` advisory lock catches it.
    """
    name = "concurrent-test"
    ready = tmp_path / "child_ready"
    ctx = mp.get_context("fork")
    child = ctx.Process(
        target=_child_hold_then_signal,
        args=(str(tmp_path), name, str(ready)),
    )
    child.start()
    try:
        # Wait until the child has acquired the lock.
        deadline = time.time() + 5.0
        while not ready.exists() and time.time() < deadline:
            time.sleep(0.05)
        assert ready.exists(), "child failed to acquire lock"

        # Parent's attempt must fail while child holds the lock.
        with pytest.raises(KillSwitchLockHeldError) as excinfo:
            with KillSwitchLock(name, command="shutdown", lock_dir=tmp_path):
                pytest.fail("acquired despite child holding lock")
        assert "command=shutdown" in str(excinfo.value)
    finally:
        child.join(timeout=5.0)
        if child.is_alive():
            child.terminate()
            child.join(timeout=2.0)


def _child_crash_holding_lock(lock_dir: str, name: str, ready_path: str) -> None:
    """Child target: acquire the lock, signal ready, then crash."""
    # Manually open the lock (don't use the context manager's exit
    # cleanup, so we simulate a crash that leaves the kernel state
    # to clean up rather than a clean release).
    lock = KillSwitchLock(name, command="shutdown", lock_dir=Path(lock_dir))
    lock.__enter__()
    Path(ready_path).write_text("ready", encoding="utf-8")
    # SIGKILL ourselves so __exit__ never runs. The kernel must
    # release the flock and a fresh acquire in the parent must
    # succeed.
    import os
    import signal

    os.kill(os.getpid(), signal.SIGKILL)


def test_kernel_releases_lock_when_holding_process_dies(tmp_path: Path) -> None:
    """If a process crashes while holding the lock, the kernel releases it.

    No stale-lock recovery path is needed in user code because the
    advisory lock state lives in the kernel, not in the file content.
    """
    name = "crash-test"
    ready = tmp_path / "child_ready"
    ctx = mp.get_context("fork")
    child = ctx.Process(
        target=_child_crash_holding_lock,
        args=(str(tmp_path), name, str(ready)),
    )
    child.start()
    try:
        deadline = time.time() + 5.0
        while not ready.exists() and time.time() < deadline:
            time.sleep(0.05)
        assert ready.exists(), "child failed to acquire lock before crashing"

        # Wait for the child to die so the kernel can release.
        child.join(timeout=5.0)
        assert not child.is_alive(), "child did not die"

        # Fresh acquire must succeed even though the file still exists
        # (the child never reached __exit__).
        with KillSwitchLock(name, command="shutdown", lock_dir=tmp_path):
            pass
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=2.0)
