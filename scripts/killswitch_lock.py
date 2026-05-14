"""Concurrent-run guard for dev_killswitch.py and qa_killswitch.py.

Audit issue #186 (cluster C3) found that both scripts' pre-flight check
was advisory-only -- a second invocation could race the first into the
destructive CloudFormation-delete phase, leaving the environment in a
state where both invocations had begun deleting the same stack ARNs
and CloudFormation surfaced ``ROLLBACK_FAILED`` on the second-arriving
delete. Recovery required console intervention.

This module gives both scripts a process-level lock. ``fcntl.flock``
holds the lock for the lifetime of the calling process; if the process
crashes or is killed, the kernel releases the lock automatically, so
there is no stale-lock recovery path to maintain. The lock backing
file lives in ``~/.aura/`` (per-operator), which catches the realistic
threat: one operator double-invoking on their own machine.

Cross-machine and CI-runner concurrent invocation is **not** addressed
by this lock. A future enhancement could layer an S3 advisory lock on
top -- the chicken-and-egg with the kill-switch tearing down its own
artifacts bucket makes that a non-trivial design.

Usage::

    from killswitch_lock import KillSwitchLock, KillSwitchLockHeldError

    try:
        with KillSwitchLock("dev-killswitch") as lock:
            # Destructive work happens inside the with-block. The lock
            # is released automatically on context exit, including on
            # exception paths.
            run_destructive_phase()
    except KillSwitchLockHeldError as e:
        error(f"Another kill-switch invocation is already running: {e}")
        return 1
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Lock name validator. Only basic identifier characters are allowed so a
# caller cannot accidentally (or maliciously) traverse out of the lock
# directory via ``..`` or sibling-path segments. ``dev-killswitch`` and
# ``qa-killswitch`` are the only known callers; the pattern is loose
# enough to add future siblings without code changes.
_VALID_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")


class KillSwitchLockHeldError(RuntimeError):
    """Raised when another kill-switch invocation already holds the lock."""


@dataclass
class LockHolder:
    """Identification block written into the lock file at acquire time."""

    pid: int
    hostname: str
    acquired_at: str  # ISO-8601 UTC
    command: str  # "shutdown" | "restore" | "cleanup" | "status"

    @classmethod
    def now(cls, command: str) -> "LockHolder":
        return cls(
            pid=os.getpid(),
            hostname=socket.gethostname(),
            acquired_at=datetime.now(timezone.utc).isoformat(),
            command=command,
        )


class KillSwitchLock:
    """``fcntl.flock``-backed advisory lock scoped to one kill-switch.

    The lock file lives at ``~/.aura/<name>.lock``. Acquire is
    non-blocking; if another process already holds the lock, we raise
    :class:`KillSwitchLockHeldError` with the holder's identification
    block embedded in the message.

    The lock is automatically released when the context manager exits,
    when the process exits cleanly, or when the kernel reaps a crashed
    process. There is no separate stale-lock recovery to maintain.

    Parameters
    ----------
    name:
        A short label that names the lock file (e.g. ``"dev-killswitch"``).
        Both ``dev_killswitch.py`` and ``qa_killswitch.py`` use distinct
        names so a DEV and a QA teardown can run concurrently without
        blocking each other.
    command:
        The kill-switch subcommand being invoked. Recorded in the lock
        file so a blocked invocation can surface "shutdown is running"
        vs "restore is running" to the operator.
    lock_dir:
        Override the lock directory. Defaults to ``~/.aura/`` to match
        the existing state-file location in both scripts.
    """

    def __init__(
        self,
        name: str,
        *,
        command: str = "unknown",
        lock_dir: Optional[Path] = None,
    ) -> None:
        if not _VALID_NAME.match(name or ""):
            raise ValueError(
                f"invalid lock name: {name!r} -- "
                f"only [a-zA-Z0-9_-]+ allowed (no path separators or '..')"
            )
        base = lock_dir if lock_dir is not None else Path.home() / ".aura"
        base.mkdir(parents=True, exist_ok=True)
        self.lock_path = base / f"{name}.lock"
        self.command = command
        self._fd: Optional[int] = None

    def __enter__(self) -> "KillSwitchLock":
        # Open with O_RDWR | O_CREAT so we can both lock and write the
        # holder block. Mode 0o600 so other users on a shared host
        # cannot read the operator's PID / hostname.
        flags = os.O_RDWR | os.O_CREAT
        fd = os.open(self.lock_path, flags, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(fd)
            holder_msg = self._describe_holder()
            raise KillSwitchLockHeldError(
                f"another kill-switch invocation already holds {self.lock_path}: "
                f"{holder_msg}"
            ) from exc

        # We got the lock. Truncate any stale holder block from a prior
        # invocation and write our identification block. Truncation is
        # safe here because the lock guarantees we are the only writer.
        try:
            os.ftruncate(fd, 0)
            holder = LockHolder.now(self.command)
            os.write(fd, json.dumps(asdict(holder), indent=2).encode("utf-8"))
        except OSError:
            # Holder block is informational; failing to write it must
            # not prevent the caller from proceeding under the lock.
            pass

        self._fd = fd
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
            # Best-effort cleanup. The file's existence is harmless --
            # the lock state lives in the kernel, not the file -- but
            # tidying up reduces confusion for operators inspecting
            # ``~/.aura/``.
            try:
                self.lock_path.unlink()
            except (FileNotFoundError, PermissionError):
                pass

    def _describe_holder(self) -> str:
        """Read the lock file's holder block for a more useful error message.

        Returns a short description like ``"pid=12345 hostname=laptop
        command=shutdown acquired_at=2026-05-14T18:22:01+00:00"``. If
        the file is missing or unparseable, returns the path only --
        we never let this method raise, because it runs inside the
        exception path of __enter__.
        """
        try:
            raw = self.lock_path.read_text(encoding="utf-8")
            if not raw.strip():
                return f"holder-block-empty (path={self.lock_path})"
            data = json.loads(raw)
            parts = [
                f"{k}={v}"
                for k, v in data.items()
                if k in {"pid", "hostname", "command", "acquired_at"}
            ]
            return " ".join(parts)
        except (OSError, json.JSONDecodeError):
            return f"holder-block-unreadable (path={self.lock_path})"
