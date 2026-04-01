"""
OpenTelemetry Instrumentation for Project Aura (ADR-028 Phase 1)

Provides distributed tracing and metrics for agent executions,
LLM calls, and tool invocations using OpenTelemetry SDK.

Exports to AWS X-Ray via OTel Collector for visualization and analysis.
"""

import functools
import logging
import os
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Callable, TypeVar

logger = logging.getLogger(__name__)

# OpenTelemetry imports
try:
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.propagate import set_global_textmap
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import SpanKind, Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning(
        "OpenTelemetry SDK not installed. Tracing disabled. Install with: pip install opentelemetry-sdk opentelemetry-exporter-otlp"
    )

if TYPE_CHECKING:
    from opentelemetry.metrics import Counter, Histogram, Meter
    from opentelemetry.trace import Tracer

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

# Module-level tracer and meter (initialized by setup_otel)
if TYPE_CHECKING:
    _tracer: Tracer | None = None
    _meter: Meter | None = None
else:
    _tracer: Any = None
    _meter: Any = None
_initialized = False


# Semantic conventions for Aura agents (extending OTel GenAI conventions)
class AuraSpanAttributes:
    """Custom span attributes for Aura agent tracing."""

    # Agent attributes
    AGENT_NAME = "aura.agent.name"
    AGENT_TIER = "aura.agent.tier"
    AGENT_OPERATION = "aura.agent.operation"

    # LLM attributes (following OTel GenAI conventions)
    LLM_SYSTEM = "gen_ai.system"
    LLM_REQUEST_MODEL = "gen_ai.request.model"
    LLM_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
    LLM_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
    LLM_RESPONSE_MODEL = "gen_ai.response.model"
    LLM_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
    LLM_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

    # Tool attributes
    TOOL_NAME = "aura.tool.name"
    TOOL_PARAMETERS = "aura.tool.parameters"

    # Cost tracking
    COST_USD = "aura.cost.usd"
    MODEL_TIER = "aura.model.tier"


def setup_otel(
    service_name: str = "aura-agents",
    service_version: str = "1.0.0",
    environment: str | None = None,
    otlp_endpoint: str | None = None,
) -> bool:
    """
    Initialize OpenTelemetry tracing and metrics.

    Args:
        service_name: Name of the service for tracing
        service_version: Version of the service
        environment: Deployment environment (dev/staging/prod)
        otlp_endpoint: OTLP collector endpoint (default: localhost:4317)

    Returns:
        True if initialization successful, False otherwise
    """
    global _tracer, _meter, _initialized

    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available. Tracing disabled.")
        return False

    if _initialized:
        logger.debug("OpenTelemetry already initialized")
        return True

    try:
        # Get configuration from environment or parameters
        environment = environment or os.environ.get("AURA_ENV", "dev")
        otlp_endpoint = otlp_endpoint or os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "otel-collector.otel-system.svc.cluster.local:4317",
        )

        # Create resource with service information
        resource = Resource.create(
            {
                SERVICE_NAME: service_name,
                SERVICE_VERSION: service_version,
                "deployment.environment": environment,
                "service.namespace": "aura",
            }
        )

        # Setup trace provider
        trace_provider = TracerProvider(resource=resource)
        trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
        trace.set_tracer_provider(trace_provider)

        # Setup metrics provider
        metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
        metric_reader = PeriodicExportingMetricReader(
            metric_exporter, export_interval_millis=60000
        )
        meter_provider = MeterProvider(
            resource=resource, metric_readers=[metric_reader]
        )
        metrics.set_meter_provider(meter_provider)

        # Set W3C Trace Context propagator
        set_global_textmap(TraceContextTextMapPropagator())

        # Get tracer and meter
        _tracer = trace.get_tracer(__name__, service_version)
        _meter = metrics.get_meter(__name__, service_version)

        _initialized = True
        logger.info(
            f"OpenTelemetry initialized for {service_name} v{service_version} in {environment}"
        )
        logger.info(f"OTLP endpoint: {otlp_endpoint}")

        return True

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
        return False


def get_tracer():
    """Get the global tracer instance."""
    if _tracer is None and OTEL_AVAILABLE:
        setup_otel()
    return _tracer


def get_meter():
    """Get the global meter instance."""
    if _meter is None and OTEL_AVAILABLE:
        setup_otel()
    return _meter


@contextmanager
def trace_agent_execution(
    agent_name: str,
    operation: str,
    tier: str = "accurate",
    attributes: dict[str, Any] | None = None,
):
    """
    Context manager for tracing agent execution.

    Args:
        agent_name: Name of the agent (e.g., "CoderAgent", "ReviewerAgent")
        operation: Operation being performed (e.g., "patch_generation")
        tier: Model tier being used (fast/accurate/maximum)
        attributes: Additional span attributes

    Yields:
        The current span for additional instrumentation

    Example:
        >>> with trace_agent_execution("CoderAgent", "patch_generation", "accurate") as span:
        ...     result = agent.generate_patch(...)
        ...     span.set_attribute("patch.lines_changed", 42)
    """
    tracer = get_tracer()

    if tracer is None:
        # No-op context manager when tracing disabled
        yield None
        return

    span_attributes = {
        AuraSpanAttributes.AGENT_NAME: agent_name,
        AuraSpanAttributes.AGENT_OPERATION: operation,
        AuraSpanAttributes.AGENT_TIER: tier,
    }

    if attributes:
        span_attributes.update(attributes)

    with tracer.start_as_current_span(
        f"{agent_name}.{operation}",
        kind=SpanKind.INTERNAL,
        attributes=span_attributes,
    ) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


@contextmanager
def trace_llm_call(
    model: str,
    operation: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
):
    """
    Context manager for tracing LLM API calls.

    Args:
        model: Model identifier (e.g., "anthropic.claude-3-5-sonnet-20240620-v1:0")
        operation: Operation type (e.g., "patch_generation")
        max_tokens: Maximum tokens requested
        temperature: Temperature parameter

    Yields:
        Tuple of (span, record_usage_fn) for recording token usage

    Example:
        >>> with trace_llm_call("claude-3-sonnet", "code_review") as (span, record_usage):
        ...     response = llm.invoke(...)
        ...     record_usage(input_tokens=100, output_tokens=50, cost_usd=0.001)
    """
    tracer = get_tracer()

    if tracer is None:
        yield None, lambda **kwargs: None
        return

    span_attributes: dict[str, Any] = {
        AuraSpanAttributes.LLM_SYSTEM: "aws_bedrock",
        AuraSpanAttributes.LLM_REQUEST_MODEL: model,
        AuraSpanAttributes.AGENT_OPERATION: operation,
    }

    if max_tokens:
        span_attributes[AuraSpanAttributes.LLM_REQUEST_MAX_TOKENS] = max_tokens
    if temperature is not None:
        span_attributes[AuraSpanAttributes.LLM_REQUEST_TEMPERATURE] = temperature

    def record_usage(
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        response_model: str | None = None,
    ):
        """Record LLM usage metrics on the span."""
        if span:
            span.set_attribute(AuraSpanAttributes.LLM_USAGE_INPUT_TOKENS, input_tokens)
            span.set_attribute(
                AuraSpanAttributes.LLM_USAGE_OUTPUT_TOKENS, output_tokens
            )
            span.set_attribute(AuraSpanAttributes.COST_USD, cost_usd)
            if response_model:
                span.set_attribute(
                    AuraSpanAttributes.LLM_RESPONSE_MODEL, response_model
                )

    with tracer.start_as_current_span(
        f"llm.{operation}",
        kind=SpanKind.CLIENT,
        attributes=span_attributes,
    ) as span:
        try:
            yield span, record_usage
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


@contextmanager
def trace_tool_call(tool_name: str, parameters: dict[str, Any] | None = None):
    """
    Context manager for tracing tool/function calls.

    Args:
        tool_name: Name of the tool being called
        parameters: Tool parameters (will be serialized)

    Yields:
        The current span

    Example:
        >>> with trace_tool_call("neptune_query", {"query": "g.V().limit(10)"}) as span:
        ...     result = neptune.execute(query)
    """
    tracer = get_tracer()

    if tracer is None:
        yield None
        return

    span_attributes = {
        AuraSpanAttributes.TOOL_NAME: tool_name,
    }

    if parameters:
        # Serialize parameters safely (avoid sensitive data)
        safe_params = {k: str(v)[:100] for k, v in parameters.items()}
        span_attributes[AuraSpanAttributes.TOOL_PARAMETERS] = str(safe_params)

    with tracer.start_as_current_span(
        f"tool.{tool_name}",
        kind=SpanKind.INTERNAL,
        attributes=span_attributes,
    ) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def trace_agent(operation: str | None = None, tier: str = "accurate"):
    """
    Decorator for tracing agent methods.

    Args:
        operation: Operation name (defaults to method name)
        tier: Model tier for the operation

    Example:
        >>> class CoderAgent:
        ...     @trace_agent(operation="patch_generation", tier="accurate")
        ...     def generate_patch(self, vulnerability):
        ...         ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            agent_name = self.__class__.__name__
            op_name = operation or func.__name__

            with trace_agent_execution(agent_name, op_name, tier) as span:  # noqa: F841
                return func(self, *args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            agent_name = self.__class__.__name__
            op_name = operation or func.__name__

            with trace_agent_execution(agent_name, op_name, tier) as span:  # noqa: F841
                return await func(self, *args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


# Metrics helpers
class AuraMetrics:
    """Metrics collection for Aura agents."""

    def __init__(self) -> None:
        if TYPE_CHECKING:
            self._meter: Meter | None = None
            self._agent_invocations: Counter | None = None
            self._agent_duration: Histogram | None = None
            self._llm_tokens: Counter | None = None
            self._llm_cost: Counter | None = None
        else:
            self._meter: Any = None
            self._agent_invocations: Any = None
            self._agent_duration: Any = None
            self._llm_tokens: Any = None
            self._llm_cost: Any = None

    def _ensure_initialized(self) -> None:
        """Initialize metrics instruments lazily."""
        if self._meter is not None:
            return

        meter = get_meter()
        if meter is None:
            return

        self._meter = meter
        self._agent_invocations = meter.create_counter(
            "aura.agent.invocations",
            description="Number of agent invocations",
            unit="1",
        )

        self._agent_duration = meter.create_histogram(
            "aura.agent.duration",
            description="Agent execution duration",
            unit="ms",
        )

        self._llm_tokens = meter.create_counter(
            "aura.llm.tokens",
            description="LLM tokens used",
            unit="1",
        )

        self._llm_cost = meter.create_counter(
            "aura.llm.cost",
            description="LLM cost in USD",
            unit="USD",
        )

    def record_agent_invocation(
        self,
        agent_name: str,
        operation: str,
        duration_ms: float,
        success: bool = True,
    ):
        """Record an agent invocation metric."""
        self._ensure_initialized()
        if self._agent_invocations is None:
            return

        attributes = {
            "agent.name": agent_name,
            "operation": operation,
            "success": str(success).lower(),
        }

        self._agent_invocations.add(1, attributes)
        if self._agent_duration is not None:
            self._agent_duration.record(duration_ms, attributes)

    def record_llm_usage(
        self,
        model: str,
        tier: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ):
        """Record LLM usage metrics."""
        self._ensure_initialized()
        if self._llm_tokens is None:
            return

        attributes = {
            "model": model.split(".")[-1] if "." in model else model,
            "tier": tier,
        }

        self._llm_tokens.add(input_tokens, {**attributes, "type": "input"})
        self._llm_tokens.add(output_tokens, {**attributes, "type": "output"})
        if self._llm_cost is not None:
            self._llm_cost.add(cost_usd, attributes)


# Global metrics instance
aura_metrics = AuraMetrics()


# Convenience functions
def record_agent_invocation(
    agent_name: str, operation: str, duration_ms: float, success: bool = True
):
    """Record an agent invocation metric."""
    aura_metrics.record_agent_invocation(agent_name, operation, duration_ms, success)


def record_llm_usage(
    model: str, tier: str, input_tokens: int, output_tokens: int, cost_usd: float
):
    """Record LLM usage metrics."""
    aura_metrics.record_llm_usage(model, tier, input_tokens, output_tokens, cost_usd)


if __name__ == "__main__":
    # Demo/test usage
    logging.basicConfig(level=logging.INFO)

    print("Project Aura - OpenTelemetry Instrumentation Demo")
    print("=" * 60)

    # Initialize (will use default local collector endpoint)
    success = setup_otel(
        service_name="aura-demo",
        service_version="1.0.0",
        environment="demo",
        otlp_endpoint="localhost:4317",
    )
    print(f"OTel Initialized: {success}")

    if success:
        # Demo agent tracing
        print("\nTracing agent execution...")
        with trace_agent_execution("DemoAgent", "test_operation", "accurate") as span:
            time.sleep(0.1)  # Simulate work
            if span:
                span.set_attribute("demo.attribute", "test_value")
            print("  Agent execution traced")

        # Demo LLM tracing
        print("\nTracing LLM call...")
        with trace_llm_call("claude-3-sonnet", "demo_completion", max_tokens=100) as (
            span,
            record_usage,
        ):
            time.sleep(0.05)  # Simulate API call
            record_usage(input_tokens=50, output_tokens=25, cost_usd=0.0005)
            print("  LLM call traced")

        # Demo tool tracing
        print("\nTracing tool call...")
        with trace_tool_call("neptune_query", {"query": "g.V().limit(10)"}) as span:
            time.sleep(0.02)  # Simulate query
            print("  Tool call traced")

        # Record metrics
        print("\nRecording metrics...")
        record_agent_invocation("DemoAgent", "test_operation", 100.0, True)
        record_llm_usage("claude-3-sonnet", "accurate", 50, 25, 0.0005)
        print("  Metrics recorded")

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("\nNote: Traces will be exported to OTel collector if running.")
    print("View in AWS X-Ray console after collector processes them.")
