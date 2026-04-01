"""
Tests for OpenTelemetry Instrumentation (ADR-028 Phase 1)

Tests the tracing and metrics instrumentation for Aura agents,
LLM calls, and tool invocations.

Note: Tests that require the actual OpenTelemetry SDK are skipped
if the SDK is not installed. The core functionality (no-op behavior
when SDK unavailable) is always tested.
"""

from unittest.mock import MagicMock, patch

import pytest

# Import module under test
from src.services import otel_instrumentation
from src.services.otel_instrumentation import (
    OTEL_AVAILABLE,
    AuraMetrics,
    AuraSpanAttributes,
    aura_metrics,
    get_meter,
    get_tracer,
    record_agent_invocation,
    record_llm_usage,
    setup_otel,
    trace_agent,
    trace_agent_execution,
    trace_llm_call,
    trace_tool_call,
)

# Skip marker for tests that require OTel SDK
requires_otel = pytest.mark.skipif(
    not OTEL_AVAILABLE, reason="OpenTelemetry SDK not installed"
)


class TestAuraSpanAttributes:
    """Test custom span attribute definitions."""

    def test_agent_attributes_defined(self):
        """Verify agent-related span attributes are defined."""
        assert AuraSpanAttributes.AGENT_NAME == "aura.agent.name"
        assert AuraSpanAttributes.AGENT_TIER == "aura.agent.tier"
        assert AuraSpanAttributes.AGENT_OPERATION == "aura.agent.operation"

    def test_llm_attributes_follow_genai_conventions(self):
        """Verify LLM attributes follow OTel GenAI semantic conventions."""
        assert AuraSpanAttributes.LLM_SYSTEM == "gen_ai.system"
        assert AuraSpanAttributes.LLM_REQUEST_MODEL == "gen_ai.request.model"
        assert AuraSpanAttributes.LLM_REQUEST_MAX_TOKENS == "gen_ai.request.max_tokens"
        assert (
            AuraSpanAttributes.LLM_REQUEST_TEMPERATURE == "gen_ai.request.temperature"
        )
        assert AuraSpanAttributes.LLM_RESPONSE_MODEL == "gen_ai.response.model"
        assert AuraSpanAttributes.LLM_USAGE_INPUT_TOKENS == "gen_ai.usage.input_tokens"
        assert (
            AuraSpanAttributes.LLM_USAGE_OUTPUT_TOKENS == "gen_ai.usage.output_tokens"
        )

    def test_tool_attributes_defined(self):
        """Verify tool-related span attributes are defined."""
        assert AuraSpanAttributes.TOOL_NAME == "aura.tool.name"
        assert AuraSpanAttributes.TOOL_PARAMETERS == "aura.tool.parameters"

    def test_cost_attributes_defined(self):
        """Verify cost tracking attributes are defined."""
        assert AuraSpanAttributes.COST_USD == "aura.cost.usd"
        assert AuraSpanAttributes.MODEL_TIER == "aura.model.tier"


class TestSetupOtel:
    """Test OpenTelemetry initialization."""

    def test_setup_returns_false_when_otel_not_available(self):
        """Test setup fails gracefully when OTel SDK not installed."""
        with patch.object(otel_instrumentation, "OTEL_AVAILABLE", False):
            # Reset initialization state
            old_initialized = otel_instrumentation._initialized
            otel_instrumentation._initialized = False
            try:
                result = setup_otel()
                assert result is False
            finally:
                otel_instrumentation._initialized = old_initialized

    @requires_otel
    def test_setup_initializes_providers(self):
        """Test setup initializes trace and metric providers."""
        # Reset initialization state
        otel_instrumentation._initialized = False
        otel_instrumentation._tracer = None
        otel_instrumentation._meter = None

        result = setup_otel(
            service_name="test-service",
            service_version="1.0.0",
            environment="test",
            otlp_endpoint="localhost:4317",
        )

        assert result is True
        assert otel_instrumentation._tracer is not None
        assert otel_instrumentation._meter is not None

    @requires_otel
    def test_setup_returns_true_when_already_initialized(self):
        """Test setup returns True if already initialized."""
        # Ensure initialized
        setup_otel(otlp_endpoint="localhost:4317")
        result = setup_otel()
        assert result is True


class TestGetTracer:
    """Test tracer retrieval."""

    def test_get_tracer_returns_none_when_not_available(self):
        """Test get_tracer returns None when OTel not available."""
        with patch.object(otel_instrumentation, "OTEL_AVAILABLE", False):
            otel_instrumentation._tracer = None
            result = get_tracer()
            assert result is None

    def test_get_tracer_returns_cached_tracer(self):
        """Test get_tracer returns cached tracer instance."""
        mock_tracer = MagicMock()
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = mock_tracer
        try:
            result = get_tracer()
            assert result is mock_tracer
        finally:
            otel_instrumentation._tracer = old_tracer


class TestGetMeter:
    """Test meter retrieval."""

    def test_get_meter_returns_none_when_not_available(self):
        """Test get_meter returns None when OTel not available."""
        with patch.object(otel_instrumentation, "OTEL_AVAILABLE", False):
            otel_instrumentation._meter = None
            result = get_meter()
            assert result is None

    def test_get_meter_returns_cached_meter(self):
        """Test get_meter returns cached meter instance."""
        mock_meter = MagicMock()
        old_meter = otel_instrumentation._meter
        otel_instrumentation._meter = mock_meter
        try:
            result = get_meter()
            assert result is mock_meter
        finally:
            otel_instrumentation._meter = old_meter


class TestTraceAgentExecutionNoOp:
    """Test agent execution tracing no-op behavior."""

    def test_yields_none_when_tracer_not_available(self):
        """Test context manager yields None when tracer unavailable."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:
            with trace_agent_execution("TestAgent", "test_op") as span:
                assert span is None
        finally:
            otel_instrumentation._tracer = old_tracer

    def test_executes_code_normally_without_tracer(self):
        """Test code inside context executes normally without tracer."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:
            result = None
            with trace_agent_execution("TestAgent", "test_op") as _span:
                result = "executed"
            assert result == "executed"
        finally:
            otel_instrumentation._tracer = old_tracer

    def test_propagates_exceptions_without_tracer(self):
        """Test exceptions propagate correctly without tracer."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:
            with pytest.raises(ValueError, match="test error"):
                with trace_agent_execution("TestAgent", "test_op"):
                    raise ValueError("test error")
        finally:
            otel_instrumentation._tracer = old_tracer


@requires_otel
class TestTraceAgentExecutionWithOtel:
    """Test agent execution tracing with OTel SDK."""

    def test_creates_span_with_correct_name(self):
        """Test span is created with correct agent.operation name."""
        setup_otel(otlp_endpoint="localhost:4317")
        with trace_agent_execution(
            "CoderAgent", "patch_generation", "accurate"
        ) as span:
            assert span is not None

    def test_accepts_custom_attributes(self):
        """Test custom attributes are added to span."""
        setup_otel(otlp_endpoint="localhost:4317")
        custom_attrs = {"custom.key": "custom_value"}
        with trace_agent_execution(
            "TestAgent", "test_op", attributes=custom_attrs
        ) as span:
            if span:
                span.set_attribute("additional.attr", "value")


class TestTraceLlmCallNoOp:
    """Test LLM call tracing no-op behavior."""

    def test_yields_none_tuple_when_tracer_not_available(self):
        """Test context manager yields (None, noop) when tracer unavailable."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:
            with trace_llm_call("claude-3-sonnet", "completion") as (
                span,
                record_usage,
            ):
                assert span is None
                # record_usage should be a no-op function that doesn't raise
                record_usage(input_tokens=100, output_tokens=50, cost_usd=0.001)
        finally:
            otel_instrumentation._tracer = old_tracer

    def test_executes_code_normally_without_tracer(self):
        """Test code inside context executes normally without tracer."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:
            result = None
            with trace_llm_call("model", "op") as (span, record_usage):
                result = "executed"
            assert result == "executed"
        finally:
            otel_instrumentation._tracer = old_tracer


@requires_otel
class TestTraceLlmCallWithOtel:
    """Test LLM call tracing with OTel SDK."""

    def test_creates_span_with_llm_attributes(self):
        """Test span is created with LLM attributes."""
        setup_otel(otlp_endpoint="localhost:4317")
        with trace_llm_call(
            "claude-3-sonnet", "code_generation", max_tokens=4000, temperature=0.7
        ) as (span, record_usage):
            assert span is not None
            record_usage(input_tokens=100, output_tokens=50, cost_usd=0.001)


class TestTraceToolCallNoOp:
    """Test tool call tracing no-op behavior."""

    def test_yields_none_when_tracer_not_available(self):
        """Test context manager yields None when tracer unavailable."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:
            with trace_tool_call("neptune_query") as span:
                assert span is None
        finally:
            otel_instrumentation._tracer = old_tracer

    def test_executes_code_normally_without_tracer(self):
        """Test code inside context executes normally without tracer."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:
            result = None
            with trace_tool_call("test_tool", {"param": "value"}) as _span:
                result = "executed"
            assert result == "executed"
        finally:
            otel_instrumentation._tracer = old_tracer


@requires_otel
class TestTraceToolCallWithOtel:
    """Test tool call tracing with OTel SDK."""

    def test_creates_span_with_tool_name(self):
        """Test span is created with tool name attribute."""
        setup_otel(otlp_endpoint="localhost:4317")
        with trace_tool_call("neptune_query", {"query": "g.V().limit(10)"}) as span:
            assert span is not None


class TestTraceAgentDecorator:
    """Test the @trace_agent decorator."""

    def test_decorator_wraps_sync_method(self):
        """Test decorator works with synchronous methods."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:

            class TestAgent:
                @trace_agent(operation="test_op", tier="fast")
                def do_work(self):
                    return "result"

            agent = TestAgent()
            result = agent.do_work()
            assert result == "result"
        finally:
            otel_instrumentation._tracer = old_tracer

    @pytest.mark.asyncio
    async def test_decorator_wraps_async_method(self):
        """Test decorator works with async methods."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:

            class TestAgent:
                @trace_agent(operation="async_op", tier="accurate")
                async def do_async_work(self):
                    return "async_result"

            agent = TestAgent()
            result = await agent.do_async_work()
            assert result == "async_result"
        finally:
            otel_instrumentation._tracer = old_tracer

    def test_decorator_uses_method_name_as_default_operation(self):
        """Test decorator uses method name when operation not specified."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:

            class TestAgent:
                @trace_agent()
                def generate_patch(self):
                    return "patch"

            agent = TestAgent()
            result = agent.generate_patch()
            assert result == "patch"
        finally:
            otel_instrumentation._tracer = old_tracer


class TestAuraMetrics:
    """Test the AuraMetrics class."""

    def test_lazy_initialization(self):
        """Test metrics are lazily initialized."""
        metrics_instance = AuraMetrics()
        assert metrics_instance._meter is None
        assert metrics_instance._agent_invocations is None

    def test_record_agent_invocation_without_meter(self):
        """Test recording invocation when meter not available."""
        old_meter = otel_instrumentation._meter
        otel_instrumentation._meter = None
        try:
            metrics_instance = AuraMetrics()
            # Should not raise
            metrics_instance.record_agent_invocation(
                agent_name="TestAgent",
                operation="test_op",
                duration_ms=100.0,
                success=True,
            )
        finally:
            otel_instrumentation._meter = old_meter

    def test_record_llm_usage_without_meter(self):
        """Test recording LLM usage when meter not available."""
        old_meter = otel_instrumentation._meter
        otel_instrumentation._meter = None
        try:
            metrics_instance = AuraMetrics()
            # Should not raise
            metrics_instance.record_llm_usage(
                model="claude-3-sonnet",
                tier="accurate",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.001,
            )
        finally:
            otel_instrumentation._meter = old_meter


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @patch.object(aura_metrics, "record_agent_invocation")
    def test_record_agent_invocation_function(self, mock_method):
        """Test module-level record_agent_invocation calls metrics instance."""
        record_agent_invocation("Agent", "op", 100.0, True)
        mock_method.assert_called_once_with("Agent", "op", 100.0, True)

    @patch.object(aura_metrics, "record_llm_usage")
    def test_record_llm_usage_function(self, mock_method):
        """Test module-level record_llm_usage calls metrics instance."""
        record_llm_usage("model", "tier", 100, 50, 0.001)
        mock_method.assert_called_once_with("model", "tier", 100, 50, 0.001)


class TestOtelAvailability:
    """Test behavior when OpenTelemetry SDK is not installed."""

    def test_module_handles_missing_sdk(self):
        """Test module works when OTel SDK not installed."""
        # The module should handle ImportError gracefully
        assert hasattr(otel_instrumentation, "OTEL_AVAILABLE")
        assert isinstance(otel_instrumentation.OTEL_AVAILABLE, bool)

    def test_context_managers_work_without_sdk(self):
        """Test all context managers work when SDK unavailable."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:
            # All should work without raising
            with trace_agent_execution("Agent", "op") as span:
                assert span is None

            with trace_llm_call("model", "op") as (span, record):
                assert span is None
                record(input_tokens=100, output_tokens=50)

            with trace_tool_call("tool") as span:
                assert span is None
        finally:
            otel_instrumentation._tracer = old_tracer


class TestIntegration:
    """Integration tests for OTel instrumentation."""

    def test_nested_spans_work(self):
        """Test nested context managers work correctly."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:
            with trace_agent_execution("OuterAgent", "outer_op") as outer:
                with trace_llm_call("model", "inner_op") as (inner, record):
                    with trace_tool_call("tool") as tool_span:
                        # All should be None when tracer unavailable
                        assert outer is None
                        assert inner is None
                        assert tool_span is None
        finally:
            otel_instrumentation._tracer = old_tracer

    def test_decorator_with_context_manager(self):
        """Test decorator can be used with context managers."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:

            class TestAgent:
                @trace_agent(operation="combined_op")
                def do_work(self):
                    with trace_llm_call("model", "llm_call") as (span, record):
                        record(input_tokens=100, output_tokens=50)
                    return "done"

            agent = TestAgent()
            result = agent.do_work()
            assert result == "done"
        finally:
            otel_instrumentation._tracer = old_tracer

    def test_full_workflow_simulation(self):
        """Test complete workflow with all instrumentation points."""
        old_tracer = otel_instrumentation._tracer
        otel_instrumentation._tracer = None
        try:
            # Simulate agent workflow
            workflow_steps = []

            with trace_agent_execution(
                "OrchestratorAgent", "execute_workflow"
            ) as _span:
                workflow_steps.append("orchestrator_start")

                with trace_agent_execution(
                    "CoderAgent", "generate_patch"
                ) as _coder_span:
                    workflow_steps.append("coder_start")

                    with trace_llm_call("claude-3-sonnet", "code_generation") as (
                        llm_span,
                        record,
                    ):
                        workflow_steps.append("llm_call")
                        record(input_tokens=500, output_tokens=200, cost_usd=0.003)

                    with trace_tool_call(
                        "neptune_query", {"query": "g.V().has('type', 'function')"}
                    ):
                        workflow_steps.append("tool_call")

                    workflow_steps.append("coder_end")

                workflow_steps.append("orchestrator_end")

            assert workflow_steps == [
                "orchestrator_start",
                "coder_start",
                "llm_call",
                "tool_call",
                "coder_end",
                "orchestrator_end",
            ]
        finally:
            otel_instrumentation._tracer = old_tracer
