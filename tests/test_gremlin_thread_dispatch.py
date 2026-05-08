"""Tests for the gremlin-python thread-dispatch wrapper that replaced
the nest_asyncio dependency.

The wrapper transparently routes ``client.submit(q).all().result()``
through a worker thread when the caller is inside an asyncio event
loop. Without it, gremlin-python's internal ``loop.run_until_complete``
would re-enter the running loop and raise ``RuntimeError``.

These tests fake the real gremlin client surface and assert:

- Sync-context calls go straight through (no thread hop).
- Async-context calls land on the dispatch executor thread.
- ``close()`` passes through to the real client.
- Identity check: dispatched calls return the real client's result.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from src.services.neptune_graph_service import (
    _ThreadDispatchedGremlinClient,
)


class _FakeSubmitResult:
    """Mimic gremlin-python's submit() return chain."""

    def __init__(self, payload: Any, capture: dict[str, Any]) -> None:
        self._payload = payload
        self._capture = capture

    def all(self) -> "_FakeSubmitResult":
        return self

    def result(self) -> Any:
        # Record which thread executed the actual gremlin work so the
        # tests can assert sync vs async dispatch.
        self._capture["thread_name"] = threading.current_thread().name
        return self._payload


class _FakeGremlinClient:
    """Drop-in stand-in for gremlin-python's ``client.Client``."""

    def __init__(self, payload: Any = None) -> None:
        self._payload = payload if payload is not None else ["v1", "v2"]
        self.submitted_queries: list[str] = []
        self.closed = False
        self.last_call_capture: dict[str, Any] = {}

    def submit(self, query: str) -> _FakeSubmitResult:
        self.submitted_queries.append(query)
        return _FakeSubmitResult(self._payload, self.last_call_capture)

    def close(self) -> None:
        self.closed = True


def test_sync_context_runs_in_calling_thread() -> None:
    """When no event loop is running, the wrapper should pass through
    on the calling thread -- no thread hop needed."""
    real = _FakeGremlinClient(payload=[1, 2, 3])
    wrapped = _ThreadDispatchedGremlinClient(real)

    main_thread = threading.current_thread().name
    result = wrapped.submit("g.V().limit(1)").all().result()

    assert result == [1, 2, 3]
    assert real.submitted_queries == ["g.V().limit(1)"]
    assert real.last_call_capture["thread_name"] == main_thread


def test_async_context_dispatches_to_executor_thread() -> None:
    """When called from inside an asyncio event loop, the wrapper
    must dispatch the blocking gremlin call to a worker thread so the
    caller's loop is not re-entered."""
    real = _FakeGremlinClient(payload=[42])
    wrapped = _ThreadDispatchedGremlinClient(real)

    main_thread = threading.current_thread().name

    async def caller() -> Any:
        # The wrapper detects the running loop and routes through
        # the dispatch executor.
        return wrapped.submit("g.V().count()").all().result()

    result = asyncio.run(caller())

    assert result == [42]
    assert real.submitted_queries == ["g.V().count()"]
    # The actual gremlin work executed on a non-main thread.
    assert real.last_call_capture["thread_name"] != main_thread
    # The executor's threads use the "gremlin-dispatch" prefix.
    assert real.last_call_capture["thread_name"].startswith("gremlin-dispatch")


def test_close_passes_through() -> None:
    real = _FakeGremlinClient()
    wrapped = _ThreadDispatchedGremlinClient(real)
    assert real.closed is False
    wrapped.close()
    assert real.closed is True


def test_multiple_async_calls_reuse_executor() -> None:
    """The dispatch executor is a module-level singleton; concurrent
    async calls should reuse the pool rather than spinning up a fresh
    one each time. Sanity check that consecutive calls don't blow up."""
    real = _FakeGremlinClient(payload=["ok"])
    wrapped = _ThreadDispatchedGremlinClient(real)

    async def caller() -> list[Any]:
        return [
            wrapped.submit(f"g.V('{i}')").all().result() for i in range(3)
        ]

    results = asyncio.run(caller())
    assert results == [["ok"], ["ok"], ["ok"]]
    assert real.submitted_queries == ["g.V('0')", "g.V('1')", "g.V('2')"]
