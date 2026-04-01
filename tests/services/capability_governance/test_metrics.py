"""
Tests for capability governance metrics module.

Tests CloudWatch metrics publishing, batching, and aggregation.
"""

from unittest.mock import MagicMock

import pytest

from src.services.capability_governance.contracts import (
    CapabilityCheckResult,
    CapabilityDecision,
)
from src.services.capability_governance.metrics import (
    CapabilityMetricsPublisher,
    MetricName,
    MetricsConfig,
    get_metrics_publisher,
    reset_metrics_publisher,
)
from src.services.capability_governance.registry import reset_capability_registry

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def cleanup():
    """Reset singletons after each test."""
    yield
    reset_metrics_publisher()
    reset_capability_registry()


@pytest.fixture
def metrics_config():
    """Create test metrics configuration."""
    return MetricsConfig(
        namespace="Test/CapabilityGovernance",
        enabled=True,
        flush_interval_seconds=1.0,
    )


@pytest.fixture
def metrics_publisher(metrics_config):
    """Create metrics publisher with test config."""
    return CapabilityMetricsPublisher(config=metrics_config)


@pytest.fixture
def mock_cloudwatch():
    """Create mock CloudWatch client."""
    mock = MagicMock()
    mock.put_metric_data = MagicMock(return_value={})
    return mock


@pytest.fixture
def check_result_allow():
    """Create an ALLOW check result."""
    return CapabilityCheckResult(
        decision=CapabilityDecision.ALLOW,
        tool_name="semantic_search",
        agent_id="agent-123",
        agent_type="CoderAgent",
        action="execute",
        context="sandbox",
        reason="Policy allows",
        policy_version="1.0.0",
        capability_source="base",
        processing_time_ms=5.5,
    )


@pytest.fixture
def check_result_deny():
    """Create a DENY check result."""
    return CapabilityCheckResult(
        decision=CapabilityDecision.DENY,
        tool_name="dangerous_tool",
        agent_id="agent-123",
        agent_type="CoderAgent",
        action="execute",
        context="production",
        reason="Not authorized",
        policy_version="1.0.0",
        capability_source="base",
        processing_time_ms=3.2,
    )


@pytest.fixture
def check_result_critical():
    """Create a check result for a CRITICAL tool."""
    return CapabilityCheckResult(
        decision=CapabilityDecision.ESCALATE,
        tool_name="deploy_to_production",
        agent_id="agent-123",
        agent_type="CoderAgent",
        action="execute",
        context="staging",
        reason="Requires approval",
        policy_version="1.0.0",
        capability_source="base",
        processing_time_ms=8.1,
    )


# =============================================================================
# MetricsConfig Tests
# =============================================================================


class TestMetricsConfig:
    """Tests for MetricsConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = MetricsConfig()
        assert config.namespace == "Aura/CapabilityGovernance"
        assert config.enabled is True
        assert config.batch_size == 20
        assert config.flush_interval_seconds == 60.0
        assert config.storage_resolution == 60

    def test_custom_values(self):
        """Test custom configuration values."""
        config = MetricsConfig(
            namespace="Custom/Namespace",
            enabled=False,
            batch_size=10,
            high_resolution=True,
        )
        assert config.namespace == "Custom/Namespace"
        assert config.enabled is False
        assert config.batch_size == 10
        assert config.high_resolution is True


# =============================================================================
# MetricName Tests
# =============================================================================


class TestMetricName:
    """Tests for MetricName constants."""

    def test_decision_metrics_exist(self):
        """Verify decision metrics exist."""
        assert MetricName.CAPABILITY_CHECKS == "CapabilityChecks"
        assert MetricName.DECISIONS_ALLOW == "DecisionsAllow"
        assert MetricName.DECISIONS_DENY == "DecisionsDeny"
        assert MetricName.DECISIONS_ESCALATE == "DecisionsEscalate"
        assert MetricName.DECISIONS_AUDIT_ONLY == "DecisionsAuditOnly"

    def test_violation_metrics_exist(self):
        """Verify violation metrics exist."""
        assert MetricName.VIOLATIONS == "Violations"
        assert MetricName.VIOLATIONS_CRITICAL == "ViolationsCritical"
        assert MetricName.VIOLATIONS_HIGH == "ViolationsHigh"
        assert MetricName.VIOLATIONS_MEDIUM == "ViolationsMedium"

    def test_grant_metrics_exist(self):
        """Verify grant metrics exist."""
        assert MetricName.GRANTS_CREATED == "GrantsCreated"
        assert MetricName.GRANTS_USED == "GrantsUsed"
        assert MetricName.GRANTS_REVOKED == "GrantsRevoked"
        assert MetricName.GRANTS_EXPIRED == "GrantsExpired"

    def test_performance_metrics_exist(self):
        """Verify performance metrics exist."""
        assert MetricName.CHECK_LATENCY_MS == "CheckLatencyMs"
        assert MetricName.CACHE_HIT_RATE == "CacheHitRate"
        assert MetricName.RATE_LIMIT_REJECTIONS == "RateLimitRejections"


# =============================================================================
# CapabilityMetricsPublisher Basic Tests
# =============================================================================


class TestCapabilityMetricsPublisherBasic:
    """Basic tests for CapabilityMetricsPublisher."""

    def test_initialization(self, metrics_publisher):
        """Test publisher initialization."""
        assert metrics_publisher is not None
        assert metrics_publisher.config is not None

    def test_initialization_disabled(self):
        """Test publisher with metrics disabled."""
        config = MetricsConfig(enabled=False)
        publisher = CapabilityMetricsPublisher(config=config)
        assert publisher.config.enabled is False

    def test_record_check_allow(self, metrics_publisher, check_result_allow):
        """Test recording an ALLOW check."""
        metrics_publisher.record_check(check_result_allow)

        assert metrics_publisher._counters.get(MetricName.CAPABILITY_CHECKS, 0) == 1
        assert metrics_publisher._counters.get(MetricName.DECISIONS_ALLOW, 0) == 1
        assert len(metrics_publisher._latencies) == 1

    def test_record_check_deny(self, metrics_publisher, check_result_deny):
        """Test recording a DENY check."""
        metrics_publisher.record_check(check_result_deny)

        assert metrics_publisher._counters.get(MetricName.DECISIONS_DENY, 0) == 1

    def test_record_check_escalate(self, metrics_publisher, check_result_critical):
        """Test recording an ESCALATE check."""
        metrics_publisher.record_check(check_result_critical)

        assert metrics_publisher._counters.get(MetricName.DECISIONS_ESCALATE, 0) == 1

    def test_record_check_disabled(self, check_result_allow):
        """Test that recording is skipped when disabled."""
        config = MetricsConfig(enabled=False)
        publisher = CapabilityMetricsPublisher(config=config)

        publisher.record_check(check_result_allow)

        assert len(publisher._counters) == 0


# =============================================================================
# Classification Metrics Tests
# =============================================================================


class TestClassificationMetrics:
    """Tests for classification-based metrics."""

    def test_record_safe_tool(self, metrics_publisher, check_result_allow):
        """Test recording SAFE tool invocation."""
        metrics_publisher.record_check(check_result_allow)

        assert metrics_publisher._counters.get(MetricName.SAFE_TOOL_INVOCATIONS, 0) == 1

    def test_record_critical_tool(self, metrics_publisher, check_result_critical):
        """Test recording CRITICAL tool invocation."""
        metrics_publisher.record_check(check_result_critical)

        assert (
            metrics_publisher._counters.get(MetricName.CRITICAL_TOOL_INVOCATIONS, 0)
            == 1
        )


# =============================================================================
# Violation Metrics Tests
# =============================================================================


class TestViolationMetrics:
    """Tests for violation metrics."""

    def test_record_violation(self, metrics_publisher):
        """Test recording a violation."""
        metrics_publisher.record_violation("medium")

        assert metrics_publisher._counters.get(MetricName.VIOLATIONS, 0) == 1
        assert metrics_publisher._counters.get(MetricName.VIOLATIONS_MEDIUM, 0) == 1

    def test_record_critical_violation(self, metrics_publisher):
        """Test recording a critical violation."""
        metrics_publisher.record_violation("critical")

        assert metrics_publisher._counters.get(MetricName.VIOLATIONS_CRITICAL, 0) == 1

    def test_record_high_violation(self, metrics_publisher):
        """Test recording a high violation."""
        metrics_publisher.record_violation("high")

        assert metrics_publisher._counters.get(MetricName.VIOLATIONS_HIGH, 0) == 1


# =============================================================================
# Grant Metrics Tests
# =============================================================================


class TestGrantMetrics:
    """Tests for grant metrics."""

    def test_record_grant_created(self, metrics_publisher):
        """Test recording grant creation."""
        metrics_publisher.record_grant_created()

        assert metrics_publisher._counters.get(MetricName.GRANTS_CREATED, 0) == 1

    def test_record_grant_used(self, metrics_publisher):
        """Test recording grant usage."""
        metrics_publisher.record_grant_used()

        assert metrics_publisher._counters.get(MetricName.GRANTS_USED, 0) == 1

    def test_record_grant_revoked(self, metrics_publisher):
        """Test recording grant revocation."""
        metrics_publisher.record_grant_revoked()

        assert metrics_publisher._counters.get(MetricName.GRANTS_REVOKED, 0) == 1

    def test_record_grant_expired(self, metrics_publisher):
        """Test recording grant expiration."""
        metrics_publisher.record_grant_expired()

        assert metrics_publisher._counters.get(MetricName.GRANTS_EXPIRED, 0) == 1


# =============================================================================
# Escalation Metrics Tests
# =============================================================================


class TestEscalationMetrics:
    """Tests for escalation metrics."""

    def test_record_escalation_requested(self, metrics_publisher):
        """Test recording escalation request."""
        metrics_publisher.record_escalation_requested()

        assert metrics_publisher._counters.get(MetricName.ESCALATIONS_REQUESTED, 0) == 1

    def test_record_escalation_approved(self, metrics_publisher):
        """Test recording escalation approval."""
        metrics_publisher.record_escalation_approved()

        assert metrics_publisher._counters.get(MetricName.ESCALATIONS_APPROVED, 0) == 1

    def test_record_escalation_denied(self, metrics_publisher):
        """Test recording escalation denial."""
        metrics_publisher.record_escalation_denied()

        assert metrics_publisher._counters.get(MetricName.ESCALATIONS_DENIED, 0) == 1

    def test_record_escalation_expired(self, metrics_publisher):
        """Test recording escalation expiration."""
        metrics_publisher.record_escalation_expired()

        assert metrics_publisher._counters.get(MetricName.ESCALATIONS_EXPIRED, 0) == 1


# =============================================================================
# Performance Metrics Tests
# =============================================================================


class TestPerformanceMetrics:
    """Tests for performance metrics."""

    def test_record_rate_limit_rejection(self, metrics_publisher):
        """Test recording rate limit rejection."""
        metrics_publisher.record_rate_limit_rejection()

        assert metrics_publisher._counters.get(MetricName.RATE_LIMIT_REJECTIONS, 0) == 1

    def test_record_cache_hit(self, metrics_publisher):
        """Test recording cache hit."""
        metrics_publisher.record_cache_hit(True)

        assert metrics_publisher._counters.get("cache_hits", 0) == 1

    def test_record_cache_miss(self, metrics_publisher):
        """Test recording cache miss."""
        metrics_publisher.record_cache_hit(False)

        assert metrics_publisher._counters.get("cache_misses", 0) == 1


# =============================================================================
# Latency Tracking Tests
# =============================================================================


class TestLatencyTracking:
    """Tests for latency tracking."""

    def test_latencies_recorded(self, metrics_publisher, check_result_allow):
        """Test that latencies are recorded."""
        metrics_publisher.record_check(check_result_allow)

        assert len(metrics_publisher._latencies) == 1
        assert metrics_publisher._latencies[0] == 5.5

    def test_multiple_latencies(self, metrics_publisher):
        """Test recording multiple latencies."""
        for latency in [1.0, 2.0, 3.0, 4.0, 5.0]:
            result = CapabilityCheckResult(
                decision=CapabilityDecision.ALLOW,
                tool_name="semantic_search",
                agent_id="agent-123",
                agent_type="CoderAgent",
                action="execute",
                context="sandbox",
                reason="OK",
                policy_version="1.0.0",
                capability_source="base",
                processing_time_ms=latency,
            )
            metrics_publisher.record_check(result)

        assert len(metrics_publisher._latencies) == 5


# =============================================================================
# Flush Tests
# =============================================================================


class TestMetricsFlush:
    """Tests for metrics flushing."""

    @pytest.mark.asyncio
    async def test_flush_metrics(
        self, metrics_publisher, mock_cloudwatch, check_result_allow
    ):
        """Test flushing metrics to CloudWatch."""
        metrics_publisher._cloudwatch = mock_cloudwatch
        metrics_publisher.record_check(check_result_allow)
        metrics_publisher.record_violation("medium")

        await metrics_publisher._flush_metrics()

        mock_cloudwatch.put_metric_data.assert_called()
        # Counters and latencies should be cleared
        assert len(metrics_publisher._counters) == 0
        assert len(metrics_publisher._latencies) == 0

    @pytest.mark.asyncio
    async def test_flush_empty_metrics(self, metrics_publisher, mock_cloudwatch):
        """Test flushing when no metrics recorded."""
        metrics_publisher._cloudwatch = mock_cloudwatch

        await metrics_publisher._flush_metrics()

        # Should not call CloudWatch if nothing to flush
        mock_cloudwatch.put_metric_data.assert_not_called()


# =============================================================================
# Dimension Tests
# =============================================================================


class TestDimensions:
    """Tests for metric dimensions."""

    def test_get_dimensions_default(self, metrics_publisher):
        """Test default dimensions."""
        dimensions = metrics_publisher._get_dimensions()

        assert any(d["Name"] == "Environment" for d in dimensions)
        assert any(d["Name"] == "Region" for d in dimensions)

    def test_get_dimensions_with_extra(self, metrics_publisher):
        """Test dimensions with extra values."""
        extra = {"AgentType": "CoderAgent", "ToolName": "semantic_search"}
        dimensions = metrics_publisher._get_dimensions(extra)

        assert any(d["Name"] == "AgentType" for d in dimensions)
        assert any(d["Name"] == "ToolName" for d in dimensions)

    def test_set_environment(self, metrics_publisher):
        """Test setting environment dimension."""
        metrics_publisher.set_environment("prod")
        assert metrics_publisher._environment == "prod"

    def test_set_region(self, metrics_publisher):
        """Test setting region dimension."""
        metrics_publisher.set_region("us-west-2")
        assert metrics_publisher._region == "us-west-2"


# =============================================================================
# Pending Metrics Tests
# =============================================================================


class TestPendingMetrics:
    """Tests for pending metrics count."""

    def test_get_pending_metrics_count_empty(self, metrics_publisher):
        """Test pending count when empty."""
        assert metrics_publisher.get_pending_metrics_count() == 0

    def test_get_pending_metrics_count_with_data(
        self, metrics_publisher, check_result_allow
    ):
        """Test pending count with data."""
        metrics_publisher.record_check(check_result_allow)
        metrics_publisher.record_violation("medium")

        # Should have counters + latencies
        assert metrics_publisher.get_pending_metrics_count() > 0


# =============================================================================
# Async Start/Stop Tests
# =============================================================================


class TestAsyncStartStop:
    """Tests for async start/stop."""

    @pytest.mark.asyncio
    async def test_start_stop(self, metrics_publisher):
        """Test starting and stopping the publisher."""
        await metrics_publisher.start()
        assert metrics_publisher._running is True

        await metrics_publisher.stop()
        assert metrics_publisher._running is False


# =============================================================================
# Singleton Tests
# =============================================================================


class TestMetricsSingleton:
    """Tests for metrics publisher singleton."""

    def test_get_metrics_publisher(self):
        """Test getting global metrics publisher."""
        reset_metrics_publisher()
        p1 = get_metrics_publisher()
        p2 = get_metrics_publisher()
        assert p1 is p2

    def test_reset_metrics_publisher(self):
        """Test resetting global metrics publisher."""
        p1 = get_metrics_publisher()
        reset_metrics_publisher()
        p2 = get_metrics_publisher()
        assert p1 is not p2
