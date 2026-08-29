"""Tests for tool-failure observability in the MCP tool server.

Covers the gap where a handler that catches its own error and returns a
well-formed failure payload was counted as a success: the per-tool error
counters never fired, and nothing at the metric layer distinguished "returned
normally with a failure payload" from "actually succeeded".

The three outcomes under test:

    SUCCESS           handler returned, payload reports no failure
    ERROR             handler raised / timed out / was rejected pre-dispatch
    REPORTED_FAILURE  handler returned, payload reports a failure
"""

import pytest

from src.services.mcp_tool_server import (
    MCPServerStats,
    MCPToolResult,
    MCPToolServer,
    ToolOutcome,
    classify_tool_payload,
)

pytestmark = pytest.mark.unit


# =============================================================================
# Payload classification contract
# =============================================================================


class TestClassifyToolPayload:
    """The documented failure-marker contract."""

    @pytest.mark.parametrize(
        "payload",
        [
            {"error": "connection refused"},
            {"isError": True},
            {"is_error": True},
            {"error_message": "boom"},
            {"errors": ["a", "b"]},
            {"ok": False},
            {"success": False},
            {"succeeded": False},
            {"errorMessage": "lambda boom"},
        ],
        ids=lambda p: str(p),
    )
    def test_recognised_failure_markers(self, payload):
        """Each documented marker is detected as a failure."""
        assert classify_tool_payload(payload) is not None

    @pytest.mark.parametrize(
        "payload",
        [
            {"results": [], "count": 0},
            {"cached": False},
            {"indexed": True},
            {"status": "running"},
            {"status": "provisioning"},
            # ``status`` describes the SUBJECT, not the call. A status query
            # that correctly answers "the sandbox failed" is a successful call.
            {"sandbox_id": "s1", "status": "failed"},
            {"decision": "deny", "status": "denied"},
            {"status": "error"},
            # Scalar ``errors`` is a count field on reporting tools.
            {"errors": 5},
            {"errors": 0},
            {"error": False},
            {"result": {"error": "nested errors are not inspected"}},
            {"error": None},
            {"error": ""},
            {"errors": []},
            {"ok": True},
            {"success": True},
            {},
        ],
        ids=lambda p: str(p),
    )
    def test_successes_are_not_flagged(self, payload):
        """Legitimate payloads are not misread as failures.

        A tool layer that cries wolf gets ignored as fast as a silent one, so
        false positives matter as much as false negatives here. Note that
        ``count: 0``, an empty result list, and ``cached: False`` are all
        ordinary successes.
        """
        assert classify_tool_payload(payload) is None

    @pytest.mark.parametrize("payload", ["a string", 42, None, ["a", "list"], True])
    def test_non_dict_payloads_are_unclassifiable(self, payload):
        """Non-dict payloads return None rather than guessing."""
        assert classify_tool_payload(payload) is None

    def test_reason_is_human_readable_and_bounded(self):
        """The reason names the marker and does not dump an unbounded blob."""
        reason = classify_tool_payload({"error": "x" * 5000})
        assert reason is not None
        assert "error" in reason
        assert len(reason) < 300

    def test_zero_is_not_a_failure(self):
        """``0`` is falsey but is not the documented ``False`` marker."""
        assert classify_tool_payload({"ok": 0}) is None
        assert classify_tool_payload({"success": 0}) is None


# =============================================================================
# Stats reconciliation
# =============================================================================


class TestStatsReconciliation:
    """Outcome buckets must sum to the total."""

    def test_empty_stats_reconcile(self):
        assert MCPServerStats().counters_reconcile is True

    def test_balanced_buckets_reconcile(self):
        stats = MCPServerStats(
            total_invocations=6,
            successful_invocations=3,
            failed_invocations=2,
            reported_failure_invocations=1,
        )
        assert stats.counters_reconcile is True

    def test_missing_outcome_is_detected(self):
        """A total incremented without an outcome is caught."""
        stats = MCPServerStats(total_invocations=3, successful_invocations=2)
        assert stats.counters_reconcile is False

    def test_failure_rate_includes_reported_failures(self):
        """``success_rate`` alone would hide reported failures."""
        stats = MCPServerStats(
            total_invocations=4,
            successful_invocations=2,
            failed_invocations=1,
            reported_failure_invocations=1,
        )
        assert stats.success_rate == 0.5
        assert stats.failure_rate == 0.5

    def test_to_dict_exposes_reported_failures(self):
        stats = MCPServerStats(
            total_invocations=2,
            successful_invocations=1,
            reported_failure_invocations=1,
        )
        d = stats.to_dict()
        assert d["reported_failure_invocations"] == 1
        assert d["counters_reconcile"] is True


# =============================================================================
# MCPToolResult
# =============================================================================


class TestMCPToolResult:
    def test_outcome_defaults_from_success_flag(self):
        """Results built by older callers stay self-consistent."""
        assert MCPToolResult("t", success=True).outcome == ToolOutcome.SUCCESS
        assert MCPToolResult("t", success=False).outcome == ToolOutcome.ERROR

    def test_explicit_outcome_is_preserved(self):
        result = MCPToolResult("t", success=False, outcome=ToolOutcome.REPORTED_FAILURE)
        assert result.outcome == ToolOutcome.REPORTED_FAILURE
        assert result.reported_failure is True

    def test_reported_failure_is_false_for_other_outcomes(self):
        assert MCPToolResult("t", success=True).reported_failure is False
        assert MCPToolResult("t", success=False).reported_failure is False


# =============================================================================
# End-to-end through invoke_tool
# =============================================================================


@pytest.fixture
def server():
    """Server in mock mode with no backing services."""
    return MCPToolServer()


def _register(server, name, handler):
    """Point an existing tool at a handler, keeping its definition."""
    assert name in server._tools, f"{name} is not a built-in tool"
    server._handlers[name] = handler


class TestInvokeToolOutcomes:
    async def test_success_payload_counts_as_success(self, server):
        async def handler(params):
            return {"results": [], "count": 0}

        _register(server, "query_code_graph", handler)
        result = await server.invoke_tool("query_code_graph", {})

        assert result.success is True
        assert result.outcome == ToolOutcome.SUCCESS
        assert server._stats.successful_invocations == 1
        assert server._stats.reported_failure_invocations == 0
        assert server._stats.counters_reconcile is True

    async def test_failure_payload_is_not_counted_as_success(self, server):
        """The core regression: a well-formed error is not a success."""

        async def handler(params):
            return {"error": "neptune unreachable", "results": []}

        _register(server, "query_code_graph", handler)
        result = await server.invoke_tool("query_code_graph", {})

        assert result.success is False
        assert result.outcome == ToolOutcome.REPORTED_FAILURE
        assert result.reported_failure is True
        # The reason names the marker key but must NOT echo its value -- that
        # string is logged and becomes an exception message, and driver errors
        # routinely embed endpoints and occasionally credentials.
        assert "error" in result.error
        assert "neptune unreachable" not in result.error
        # The value stays in the payload for callers that need it.
        assert result.data["error"] == "neptune unreachable"
        assert result.data["results"] == []

        assert server._stats.successful_invocations == 0
        assert server._stats.reported_failure_invocations == 1
        assert server._stats.failed_invocations == 0
        assert server._stats.counters_reconcile is True

    async def test_reported_failure_increments_per_tool_counter(self, server):
        """Per-tool error counters must fire, not just the server totals."""

        async def handler(params):
            return {"ok": False}

        _register(server, "query_code_graph", handler)
        await server.invoke_tool("query_code_graph", {})

        per_tool = server._tool_stats["query_code_graph"]
        assert per_tool.reported_failure_invocations == 1
        assert per_tool.successful_invocations == 0
        assert per_tool.counters_reconcile is True

    async def test_raised_exception_is_error_not_reported_failure(self, server):
        """Exceptions keep their own bucket and stay distinguishable."""

        async def handler(params):
            raise RuntimeError("kaboom")

        _register(server, "query_code_graph", handler)
        result = await server.invoke_tool("query_code_graph", {})

        assert result.success is False
        assert result.outcome == ToolOutcome.ERROR
        assert result.reported_failure is False
        assert server._stats.failed_invocations == 1
        assert server._stats.reported_failure_invocations == 0
        assert server._stats.counters_reconcile is True

    async def test_unknown_tool_reconciles(self, server):
        result = await server.invoke_tool("no_such_tool", {})
        assert result.outcome == ToolOutcome.ERROR
        assert server._stats.counters_reconcile is True

    async def test_hitl_pending_reconciles(self, server):
        """Regression: this path incremented the total without an outcome."""
        approval_tool = next(
            (n for n, t in server._tools.items() if t.requires_approval), None
        )
        if approval_tool is None:
            pytest.skip("no built-in tool requires approval")

        result = await server.invoke_tool(approval_tool, {}, skip_approval=False)

        assert result.success is False
        assert result.data.get("pending_approval") is True
        assert server._stats.total_invocations == 1
        assert server._stats.counters_reconcile is True

    async def test_mixed_traffic_reconciles_and_rates_are_honest(self, server):
        """A realistic mix: the failure rate must not read as zero."""
        calls = {"n": 0}

        async def handler(params):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"count": 1}
            if calls["n"] == 2:
                return {"error": "downstream 503"}
            raise RuntimeError("hard failure")

        _register(server, "query_code_graph", handler)
        for _ in range(3):
            await server.invoke_tool("query_code_graph", {})

        stats = server._stats
        assert stats.total_invocations == 3
        assert stats.successful_invocations == 1
        assert stats.reported_failure_invocations == 1
        assert stats.failed_invocations == 1
        assert stats.counters_reconcile is True
        # Before the fix this would have read 2/3 success and 1/3 failure.
        assert stats.success_rate == pytest.approx(1 / 3)
        assert stats.failure_rate == pytest.approx(2 / 3)

    async def test_latency_recorded_for_reported_failures(self, server):
        """A failing tool still consumed time; it must not skew latency."""

        async def handler(params):
            return {"error": "nope"}

        _register(server, "query_code_graph", handler)
        await server.invoke_tool("query_code_graph", {})

        assert server._stats.total_latency_ms > 0


# =============================================================================
# The concrete handler that regressed
# =============================================================================


class TestIndexCodeEmbeddingReportsFailure:
    """``index_code_embedding`` returned ``{"indexed": False}`` on failure.

    ``indexed`` is not a documented failure marker -- and should not be, since
    a bare boolean field name carries no general meaning -- so the handler now
    surfaces an explicit error instead.
    """

    async def test_failed_index_is_classified_as_failure(self):
        class FakeEmbedder:
            def generate_embedding(self, text):
                return [0.0] * 8

        class FakeOpenSearch:
            def index_embedding(self, **kwargs):
                return False

        from src.services.mcp_tool_server import VectorToolHandler

        handler = VectorToolHandler(
            opensearch_service=FakeOpenSearch(),
            embedding_service=FakeEmbedder(),
        )
        handler._mock_mode = False

        payload = await handler.index_code_embedding({"doc_id": "d1", "text": "x"})

        assert payload["indexed"] is False
        assert classify_tool_payload(payload) is not None

    async def test_successful_index_is_not_flagged(self):
        class FakeEmbedder:
            def generate_embedding(self, text):
                return [0.0] * 8

        class FakeOpenSearch:
            def index_embedding(self, **kwargs):
                return True

        from src.services.mcp_tool_server import VectorToolHandler

        handler = VectorToolHandler(
            opensearch_service=FakeOpenSearch(),
            embedding_service=FakeEmbedder(),
        )
        handler._mock_mode = False

        payload = await handler.index_code_embedding({"doc_id": "d1", "text": "x"})

        assert payload["indexed"] is True
        assert classify_tool_payload(payload) is None


# =============================================================================
# Gaps identified in review
# =============================================================================


class TestPerToolCountersOnEarlyReturns:
    """Every early return must update the per-tool bucket, not just the server.

    A rate-limit storm is exactly when per-tool failure rate needs to be
    non-zero; before this it read 0%.
    """

    async def test_rate_limited_updates_per_tool_counters(self, server):
        import time as _time

        tool = "query_code_graph"
        limit = server._tools[tool].rate_limit_per_minute
        server._rate_limit_tracker[tool] = [_time.time()] * (limit + 1)

        result = await server.invoke_tool(tool, {})

        assert result.outcome == ToolOutcome.ERROR
        assert "Rate limit" in result.error
        assert server._tool_stats[tool].failed_invocations == 1
        assert server._tool_stats[tool].counters_reconcile is True
        assert server._stats.counters_reconcile is True

    async def test_no_handler_updates_per_tool_counters(self, server):
        tool = "query_code_graph"
        del server._handlers[tool]

        result = await server.invoke_tool(tool, {})

        assert result.outcome == ToolOutcome.ERROR
        assert server._tool_stats[tool].failed_invocations == 1
        assert server._tool_stats[tool].counters_reconcile is True

    async def test_hitl_updates_per_tool_counters(self, server):
        """Pinned to a named tool so a refactor fails loudly, not silently."""
        tool = "provision_sandbox"
        assert server._tools[tool].requires_approval, (
            "provision_sandbox no longer requires approval -- re-point this "
            "regression test rather than letting it silently skip"
        )

        await server.invoke_tool(tool, {}, skip_approval=False)

        assert server._tool_stats[tool].failed_invocations == 1
        assert server._tool_stats[tool].counters_reconcile is True
        assert server._stats.counters_reconcile is True


class TestConcurrencyInvariant:
    """``counters_reconcile`` must hold mid-flight, not only at quiescence."""

    async def test_invariant_holds_during_concurrent_calls(self, server):
        import asyncio

        released = asyncio.Event()

        async def slow_handler(params):
            await released.wait()
            return {"count": 1}

        _register(server, "query_code_graph", slow_handler)

        tasks = [
            asyncio.create_task(server.invoke_tool("query_code_graph", {}))
            for _ in range(5)
        ]
        await asyncio.sleep(0)  # let them all reach the handler await

        stats = server._stats.to_dict()
        assert stats["in_flight_invocations"] == 5
        assert stats["completed_invocations"] == 0
        # Must not flap merely because calls are in progress.
        assert stats["counters_reconcile"] is True

        released.set()
        await asyncio.gather(*tasks)

        final = server._stats.to_dict()
        assert final["in_flight_invocations"] == 0
        assert final["completed_invocations"] == 5
        assert final["successful_invocations"] == 5
        assert final["counters_reconcile"] is True
        assert final["success_rate_percent"] == 100.0

    async def test_in_flight_released_when_handler_raises(self, server):
        async def boom(params):
            raise RuntimeError("x")

        _register(server, "query_code_graph", boom)
        await server.invoke_tool("query_code_graph", {})

        assert server._stats.in_flight_invocations == 0
        assert server._stats.counters_reconcile is True


class TestStatusIsNotAFailureMarker:
    """Regression guard for the status-query false positive."""

    async def test_status_query_answering_failed_is_a_successful_call(self, server):
        """``get_sandbox_status`` reporting a failed sandbox is a success.

        Classifying this as a tool failure would raise in the agent layer and
        destroy the answer the caller asked for.
        """

        async def handler(params):
            return {"sandbox_id": "s1", "status": "failed"}

        _register(server, "get_sandbox_status", handler)
        result = await server.invoke_tool("get_sandbox_status", {})

        assert result.success is True
        assert result.outcome == ToolOutcome.SUCCESS
        assert result.data["status"] == "failed"


class TestMCPToolResultConsistency:
    def test_inconsistent_success_and_outcome_is_rejected(self):
        with pytest.raises(ValueError, match="inconsistent"):
            MCPToolResult("t", success=True, outcome=ToolOutcome.ERROR)
        with pytest.raises(ValueError, match="inconsistent"):
            MCPToolResult("t", success=False, outcome=ToolOutcome.SUCCESS)

    def test_consistent_combinations_are_accepted(self):
        assert MCPToolResult("t", success=True, outcome=ToolOutcome.SUCCESS)
        assert MCPToolResult("t", success=False, outcome=ToolOutcome.ERROR)
        assert MCPToolResult("t", success=False, outcome=ToolOutcome.REPORTED_FAILURE)


# =============================================================================
# Metric emission -- makes the outcome operator-visible
# =============================================================================


class _RecordingPublisher:
    """Captures publish_tool_invocation calls."""

    def __init__(self, fail=False):
        self.calls = []
        self._fail = fail

    async def publish_tool_invocation(self, tool_name, outcome, latency_ms=None):
        if self._fail:
            raise RuntimeError("cloudwatch unavailable")
        self.calls.append(
            {"tool_name": tool_name, "outcome": outcome, "latency_ms": latency_ms}
        )
        return True


class TestMetricEmission:
    """In-process counters are not observability without emission."""

    async def test_reported_failure_is_emitted(self):
        pub = _RecordingPublisher()
        server = MCPToolServer(metrics_publisher=pub)

        async def handler(params):
            return {"error": "downstream 503"}

        server._handlers["query_code_graph"] = handler
        await server.invoke_tool("query_code_graph", {})

        assert len(pub.calls) == 1
        assert pub.calls[0]["tool_name"] == "query_code_graph"
        assert pub.calls[0]["outcome"] == "reported_failure"

    async def test_success_and_error_outcomes_are_emitted(self):
        pub = _RecordingPublisher()
        server = MCPToolServer(metrics_publisher=pub)

        async def ok(params):
            return {"count": 1}

        async def boom(params):
            raise RuntimeError("x")

        server._handlers["query_code_graph"] = ok
        await server.invoke_tool("query_code_graph", {})
        server._handlers["query_code_graph"] = boom
        await server.invoke_tool("query_code_graph", {})

        assert [c["outcome"] for c in pub.calls] == ["success", "error"]

    async def test_early_return_paths_are_also_emitted(self):
        """Rejections before dispatch must not be invisible."""
        pub = _RecordingPublisher()
        server = MCPToolServer(metrics_publisher=pub)

        await server.invoke_tool("no_such_tool", {})

        assert len(pub.calls) == 1
        assert pub.calls[0]["outcome"] == "error"

    async def test_publisher_failure_never_breaks_the_tool_call(self):
        """Observability must not become a new failure mode."""
        pub = _RecordingPublisher(fail=True)
        server = MCPToolServer(metrics_publisher=pub)

        async def handler(params):
            return {"count": 1}

        server._handlers["query_code_graph"] = handler
        result = await server.invoke_tool("query_code_graph", {})

        assert result.success is True
        assert result.outcome == ToolOutcome.SUCCESS

    async def test_no_publisher_is_a_no_op(self):
        server = MCPToolServer()

        async def handler(params):
            return {"count": 1}

        server._handlers["query_code_graph"] = handler
        result = await server.invoke_tool("query_code_graph", {})

        assert result.success is True


# =============================================================================
# The parallel tool surface: AdapterInvocationResult
# =============================================================================


class TestAdapterInvocationResult:
    """The adapter layer had the identical exception-only defect."""

    def test_failure_payload_downgrades_success(self):
        from src.services.mcp_tool_adapters import AdapterInvocationResult

        result = AdapterInvocationResult(
            tool_id="security_scanner",
            success=True,
            data={"error": "agent unreachable"},
        )

        assert result.success is False
        assert result.reported_failure is True
        assert "error" in result.error
        # Marker value must not be echoed into the reason.
        assert "agent unreachable" not in result.error
        assert result.data["error"] == "agent unreachable"

    def test_clean_payload_stays_successful(self):
        from src.services.mcp_tool_adapters import AdapterInvocationResult

        result = AdapterInvocationResult(
            tool_id="security_scanner",
            success=True,
            data={"vulnerabilities_found": 3, "compliance_status": {"x": "partial"}},
        )

        assert result.success is True
        assert result.reported_failure is False

    def test_explicit_failure_is_not_second_guessed(self):
        """Only downgrade; an adapter reporting failure is authoritative."""
        from src.services.mcp_tool_adapters import AdapterInvocationResult

        result = AdapterInvocationResult(
            tool_id="t", success=False, error="explicit", data={"count": 1}
        )

        assert result.success is False
        assert result.error == "explicit"
        assert result.reported_failure is False

    def test_status_field_does_not_downgrade_adapters_either(self):
        """A scan reporting compliance status is not a failed call."""
        from src.services.mcp_tool_adapters import AdapterInvocationResult

        result = AdapterInvocationResult(
            tool_id="security_scanner",
            success=True,
            data={"status": "failed", "compliance_status": {"owasp": "partial"}},
        )

        assert result.success is True
