"""
Tests for capability governance CloudWatch metrics publisher.

Tests metrics configuration, metric names, publisher functionality,
and CloudWatch integration.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.services.capability_governance import CapabilityCheckResult, CapabilityDecision
from src.services.capability_governance.metrics import (
    CapabilityMetricsPublisher,
    MetricName,
    MetricsConfig,
    get_metrics_publisher,
    reset_metrics_publisher,
)


class TestMetricsConfig:
    """Test MetricsConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = MetricsConfig()
        assert config.namespace == "Aura/CapabilityGovernance"
        assert config.enabled is True
        assert config.batch_size == 20
        assert config.flush_interval_seconds == 60.0
        assert config.storage_resolution == 60
        assert config.high_resolution is False
        assert config.include_environment is True
        assert config.include_region is True
        assert config.default_environment == "dev"

    def test_custom_values(self):
        """Test custom configuration values."""
        config = MetricsConfig(
            namespace="Custom/Namespace",
            enabled=False,
            batch_size=10,
            flush_interval_seconds=30.0,
            storage_resolution=1,
            high_resolution=True,
            include_environment=False,
            include_region=False,
            default_environment="prod",
        )
        assert config.namespace == "Custom/Namespace"
        assert config.enabled is False
        assert config.batch_size == 10
        assert config.flush_interval_seconds == 30.0
        assert config.storage_resolution == 1
        assert config.high_resolution is True
        assert config.include_environment is False
        assert config.include_region is False
        assert config.default_environment == "prod"

    def test_partial_override(self):
        """Test partial configuration override."""
        config = MetricsConfig(
            namespace="Partial/Override",
            batch_size=5,
        )
        assert config.namespace == "Partial/Override"
        assert config.batch_size == 5
        assert config.enabled is True  # Default
        assert config.flush_interval_seconds == 60.0  # Default


class TestMetricName:
    """Test MetricName constants."""

    def test_decision_metrics(self):
        """Test decision metric names exist."""
        assert MetricName.CAPABILITY_CHECKS == "CapabilityChecks"
        assert MetricName.DECISIONS_ALLOW == "DecisionsAllow"
        assert MetricName.DECISIONS_DENY == "DecisionsDeny"
        assert MetricName.DECISIONS_ESCALATE == "DecisionsEscalate"
        assert MetricName.DECISIONS_AUDIT_ONLY == "DecisionsAuditOnly"

    def test_violation_metrics(self):
        """Test violation metric names exist."""
        assert MetricName.VIOLATIONS == "Violations"
        assert MetricName.VIOLATIONS_CRITICAL == "ViolationsCritical"
        assert MetricName.VIOLATIONS_HIGH == "ViolationsHigh"
        assert MetricName.VIOLATIONS_MEDIUM == "ViolationsMedium"

    def test_grant_metrics(self):
        """Test grant metric names exist."""
        assert MetricName.GRANTS_CREATED == "GrantsCreated"
        assert MetricName.GRANTS_USED == "GrantsUsed"
        assert MetricName.GRANTS_REVOKED == "GrantsRevoked"
        assert MetricName.GRANTS_EXPIRED == "GrantsExpired"

    def test_escalation_metrics(self):
        """Test escalation metric names exist."""
        assert MetricName.ESCALATIONS_REQUESTED == "EscalationsRequested"
        assert MetricName.ESCALATIONS_APPROVED == "EscalationsApproved"
        assert MetricName.ESCALATIONS_DENIED == "EscalationsDenied"
        assert MetricName.ESCALATIONS_EXPIRED == "EscalationsExpired"

    def test_performance_metrics(self):
        """Test performance metric names exist."""
        assert MetricName.CHECK_LATENCY_MS == "CheckLatencyMs"
        assert MetricName.CACHE_HIT_RATE == "CacheHitRate"
        assert MetricName.RATE_LIMIT_REJECTIONS == "RateLimitRejections"

    def test_classification_metrics(self):
        """Test classification metric names exist."""
        assert MetricName.SAFE_TOOL_INVOCATIONS == "SafeToolInvocations"
        assert MetricName.MONITORING_TOOL_INVOCATIONS == "MonitoringToolInvocations"
        assert MetricName.DANGEROUS_TOOL_INVOCATIONS == "DangerousToolInvocations"
        assert MetricName.CRITICAL_TOOL_INVOCATIONS == "CriticalToolInvocations"


class TestCapabilityMetricsPublisherInit:
    """Test CapabilityMetricsPublisher initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        publisher = CapabilityMetricsPublisher()
        assert publisher.config.namespace == "Aura/CapabilityGovernance"
        assert publisher._running is False
        assert publisher._counters == {}
        assert publisher._latencies == []
        assert publisher._environment == "dev"
        assert publisher._region == "us-east-1"

    def test_custom_config(self):
        """Test initialization with custom config."""
        config = MetricsConfig(
            namespace="Custom/Namespace",
            default_environment="staging",
        )
        publisher = CapabilityMetricsPublisher(config=config)
        assert publisher.config.namespace == "Custom/Namespace"
        assert publisher._environment == "staging"

    def test_injected_cloudwatch_client(self):
        """Test initialization with injected CloudWatch client."""
        mock_client = MagicMock()
        publisher = CapabilityMetricsPublisher(cloudwatch_client=mock_client)
        assert publisher._cloudwatch is mock_client


class TestCapabilityMetricsPublisherStartStop:
    """Test publisher start/stop lifecycle."""

    @pytest.fixture
    def publisher(self):
        """Create a publisher with disabled metrics for speed."""
        config = MetricsConfig(enabled=True, flush_interval_seconds=0.1)
        return CapabilityMetricsPublisher(config=config)

    @pytest.mark.asyncio
    async def test_start(self, publisher):
        """Test starting the publisher."""
        await publisher.start()
        try:
            assert publisher._running is True
            assert publisher._flush_task is not None
        finally:
            await publisher.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self, publisher):
        """Test starting multiple times is idempotent."""
        await publisher.start()
        task1 = publisher._flush_task
        await publisher.start()
        try:
            assert publisher._flush_task is task1
        finally:
            await publisher.stop()

    @pytest.mark.asyncio
    async def test_stop(self, publisher):
        """Test stopping the publisher."""
        await publisher.start()
        await publisher.stop()
        assert publisher._running is False

    @pytest.mark.asyncio
    async def test_stop_flushes_metrics(self):
        """Test stopping flushes pending metrics."""
        mock_client = MagicMock()
        config = MetricsConfig(flush_interval_seconds=60.0)
        publisher = CapabilityMetricsPublisher(
            config=config, cloudwatch_client=mock_client
        )

        await publisher.start()
        publisher._increment_counter("TestMetric")
        await publisher.stop()

        mock_client.put_metric_data.assert_called()


class TestCapabilityMetricsPublisherDimensions:
    """Test dimension building."""

    def test_default_dimensions(self):
        """Test default dimensions."""
        publisher = CapabilityMetricsPublisher()
        dimensions = publisher._get_dimensions()

        assert len(dimensions) == 2
        assert {"Name": "Environment", "Value": "dev"} in dimensions
        assert {"Name": "Region", "Value": "us-east-1"} in dimensions

    def test_no_dimensions(self):
        """Test with all dimensions disabled."""
        config = MetricsConfig(
            include_environment=False,
            include_region=False,
        )
        publisher = CapabilityMetricsPublisher(config=config)
        dimensions = publisher._get_dimensions()

        assert dimensions == []

    def test_extra_dimensions(self):
        """Test extra dimensions."""
        publisher = CapabilityMetricsPublisher()
        extra = {"AgentType": "coder", "Tool": "semantic_search"}
        dimensions = publisher._get_dimensions(extra_dimensions=extra)

        assert len(dimensions) == 4
        assert {"Name": "AgentType", "Value": "coder"} in dimensions
        assert {"Name": "Tool", "Value": "semantic_search"} in dimensions

    def test_set_environment(self):
        """Test setting environment dimension."""
        publisher = CapabilityMetricsPublisher()
        publisher.set_environment("prod")
        dimensions = publisher._get_dimensions()

        assert {"Name": "Environment", "Value": "prod"} in dimensions

    def test_set_region(self):
        """Test setting region dimension."""
        publisher = CapabilityMetricsPublisher()
        publisher.set_region("us-west-2")
        dimensions = publisher._get_dimensions()

        assert {"Name": "Region", "Value": "us-west-2"} in dimensions


class TestCapabilityMetricsPublisherRecordCheck:
    """Test recording capability checks."""

    @pytest.fixture
    def publisher(self):
        """Create a publisher."""
        config = MetricsConfig(enabled=True)
        return CapabilityMetricsPublisher(config=config)

    def test_record_check_allow(self, publisher):
        """Test recording an ALLOW decision."""
        result = CapabilityCheckResult(
            agent_id="agent-1",
            agent_type="TestAgent",
            tool_name="semantic_search",
            action="execute",
            context="development",
            decision=CapabilityDecision.ALLOW,
            reason="Allowed by policy",
            policy_version="1.0",
            capability_source="base",
            processing_time_ms=5.0,
        )
        publisher.record_check(result)

        assert publisher._counters[MetricName.CAPABILITY_CHECKS] == 1
        assert publisher._counters[MetricName.DECISIONS_ALLOW] == 1
        assert 5.0 in publisher._latencies

    def test_record_check_deny(self, publisher):
        """Test recording a DENY decision."""
        result = CapabilityCheckResult(
            agent_id="agent-1",
            agent_type="TestAgent",
            tool_name="provision_sandbox",
            action="execute",
            context="development",
            decision=CapabilityDecision.DENY,
            reason="Denied by policy",
            policy_version="1.0",
            capability_source="base",
            processing_time_ms=3.0,
        )
        publisher.record_check(result)

        assert publisher._counters[MetricName.CAPABILITY_CHECKS] == 1
        assert publisher._counters[MetricName.DECISIONS_DENY] == 1

    def test_record_check_escalate(self, publisher):
        """Test recording an ESCALATE decision."""
        result = CapabilityCheckResult(
            agent_id="agent-1",
            agent_type="TestAgent",
            tool_name="deploy_to_production",
            action="execute",
            context="production",
            decision=CapabilityDecision.ESCALATE,
            reason="Requires approval",
            policy_version="1.0",
            capability_source="base",
            processing_time_ms=4.0,
        )
        publisher.record_check(result)

        assert publisher._counters[MetricName.DECISIONS_ESCALATE] == 1

    def test_record_check_audit_only(self, publisher):
        """Test recording an AUDIT_ONLY decision."""
        result = CapabilityCheckResult(
            agent_id="agent-1",
            agent_type="TestAgent",
            tool_name="query_code_graph",
            action="execute",
            context="development",
            decision=CapabilityDecision.AUDIT_ONLY,
            reason="Audit mode",
            policy_version="1.0",
            capability_source="base",
            processing_time_ms=2.0,
        )
        publisher.record_check(result)

        assert publisher._counters[MetricName.DECISIONS_AUDIT_ONLY] == 1

    def test_record_check_classification_safe(self, publisher):
        """Test classification metric for SAFE tool."""
        result = CapabilityCheckResult(
            agent_id="agent-1",
            agent_type="TestAgent",
            tool_name="semantic_search",  # SAFE tool
            action="execute",
            context="development",
            decision=CapabilityDecision.ALLOW,
            reason="OK",
            policy_version="1.0",
            capability_source="base",
            processing_time_ms=1.0,
        )
        publisher.record_check(result)

        assert publisher._counters.get(MetricName.SAFE_TOOL_INVOCATIONS, 0) == 1

    def test_record_check_classification_critical(self, publisher):
        """Test classification metric for CRITICAL tool."""
        result = CapabilityCheckResult(
            agent_id="agent-1",
            agent_type="TestAgent",
            tool_name="provision_sandbox",  # CRITICAL tool
            action="execute",
            context="development",
            decision=CapabilityDecision.DENY,
            reason="Denied",
            policy_version="1.0",
            capability_source="base",
            processing_time_ms=1.0,
        )
        publisher.record_check(result)

        assert publisher._counters.get(MetricName.CRITICAL_TOOL_INVOCATIONS, 0) == 1

    def test_record_check_disabled(self):
        """Test recording when metrics disabled."""
        config = MetricsConfig(enabled=False)
        publisher = CapabilityMetricsPublisher(config=config)

        result = CapabilityCheckResult(
            agent_id="agent-1",
            agent_type="TestAgent",
            tool_name="semantic_search",
            action="execute",
            context="development",
            decision=CapabilityDecision.ALLOW,
            reason="OK",
            policy_version="1.0",
            capability_source="base",
            processing_time_ms=1.0,
        )
        publisher.record_check(result)

        assert publisher._counters == {}
        assert publisher._latencies == []


class TestCapabilityMetricsPublisherRecordViolation:
    """Test recording violations."""

    @pytest.fixture
    def publisher(self):
        """Create a publisher."""
        return CapabilityMetricsPublisher()

    def test_record_violation_critical(self, publisher):
        """Test recording a critical violation."""
        publisher.record_violation("critical")

        assert publisher._counters[MetricName.VIOLATIONS] == 1
        assert publisher._counters[MetricName.VIOLATIONS_CRITICAL] == 1

    def test_record_violation_high(self, publisher):
        """Test recording a high severity violation."""
        publisher.record_violation("high")

        assert publisher._counters[MetricName.VIOLATIONS] == 1
        assert publisher._counters[MetricName.VIOLATIONS_HIGH] == 1

    def test_record_violation_medium(self, publisher):
        """Test recording a medium severity violation."""
        publisher.record_violation("MEDIUM")  # Test case insensitivity

        assert publisher._counters[MetricName.VIOLATIONS] == 1
        assert publisher._counters[MetricName.VIOLATIONS_MEDIUM] == 1

    def test_record_violation_low(self, publisher):
        """Test recording a low severity violation."""
        publisher.record_violation("low")

        assert publisher._counters[MetricName.VIOLATIONS] == 1
        # Low doesn't have a specific counter
        assert MetricName.VIOLATIONS_MEDIUM not in publisher._counters

    def test_record_violation_disabled(self):
        """Test recording when metrics disabled."""
        config = MetricsConfig(enabled=False)
        publisher = CapabilityMetricsPublisher(config=config)

        publisher.record_violation("critical")

        assert publisher._counters == {}


class TestCapabilityMetricsPublisherRecordGrants:
    """Test recording grant operations."""

    @pytest.fixture
    def publisher(self):
        """Create a publisher."""
        return CapabilityMetricsPublisher()

    def test_record_grant_created(self, publisher):
        """Test recording grant creation."""
        publisher.record_grant_created()
        assert publisher._counters[MetricName.GRANTS_CREATED] == 1

    def test_record_grant_used(self, publisher):
        """Test recording grant usage."""
        publisher.record_grant_used()
        assert publisher._counters[MetricName.GRANTS_USED] == 1

    def test_record_grant_revoked(self, publisher):
        """Test recording grant revocation."""
        publisher.record_grant_revoked()
        assert publisher._counters[MetricName.GRANTS_REVOKED] == 1

    def test_record_grant_expired(self, publisher):
        """Test recording grant expiration."""
        publisher.record_grant_expired()
        assert publisher._counters[MetricName.GRANTS_EXPIRED] == 1

    def test_multiple_grants(self, publisher):
        """Test recording multiple grant operations."""
        publisher.record_grant_created()
        publisher.record_grant_created()
        publisher.record_grant_used()
        publisher.record_grant_revoked()

        assert publisher._counters[MetricName.GRANTS_CREATED] == 2
        assert publisher._counters[MetricName.GRANTS_USED] == 1
        assert publisher._counters[MetricName.GRANTS_REVOKED] == 1


class TestCapabilityMetricsPublisherRecordEscalations:
    """Test recording escalation operations."""

    @pytest.fixture
    def publisher(self):
        """Create a publisher."""
        return CapabilityMetricsPublisher()

    def test_record_escalation_requested(self, publisher):
        """Test recording escalation request."""
        publisher.record_escalation_requested()
        assert publisher._counters[MetricName.ESCALATIONS_REQUESTED] == 1

    def test_record_escalation_approved(self, publisher):
        """Test recording escalation approval."""
        publisher.record_escalation_approved()
        assert publisher._counters[MetricName.ESCALATIONS_APPROVED] == 1

    def test_record_escalation_denied(self, publisher):
        """Test recording escalation denial."""
        publisher.record_escalation_denied()
        assert publisher._counters[MetricName.ESCALATIONS_DENIED] == 1

    def test_record_escalation_expired(self, publisher):
        """Test recording escalation expiration."""
        publisher.record_escalation_expired()
        assert publisher._counters[MetricName.ESCALATIONS_EXPIRED] == 1


class TestCapabilityMetricsPublisherRecordPerformance:
    """Test recording performance metrics."""

    @pytest.fixture
    def publisher(self):
        """Create a publisher."""
        return CapabilityMetricsPublisher()

    def test_record_rate_limit_rejection(self, publisher):
        """Test recording rate limit rejection."""
        publisher.record_rate_limit_rejection()
        assert publisher._counters[MetricName.RATE_LIMIT_REJECTIONS] == 1

    def test_record_cache_hit(self, publisher):
        """Test recording cache hit."""
        publisher.record_cache_hit(True)
        assert publisher._counters["cache_hits"] == 1

    def test_record_cache_miss(self, publisher):
        """Test recording cache miss."""
        publisher.record_cache_hit(False)
        assert publisher._counters["cache_misses"] == 1

    def test_cache_hit_rate_calculation(self, publisher):
        """Test multiple cache hits and misses."""
        publisher.record_cache_hit(True)
        publisher.record_cache_hit(True)
        publisher.record_cache_hit(False)

        assert publisher._counters["cache_hits"] == 2
        assert publisher._counters["cache_misses"] == 1


class TestCapabilityMetricsPublisherCounters:
    """Test internal counter functionality."""

    def test_increment_counter_default(self):
        """Test incrementing counter by 1."""
        publisher = CapabilityMetricsPublisher()
        publisher._increment_counter("TestMetric")
        assert publisher._counters["TestMetric"] == 1

    def test_increment_counter_value(self):
        """Test incrementing counter by specific value."""
        publisher = CapabilityMetricsPublisher()
        publisher._increment_counter("TestMetric", 5)
        assert publisher._counters["TestMetric"] == 5

    def test_increment_counter_cumulative(self):
        """Test cumulative counter increments."""
        publisher = CapabilityMetricsPublisher()
        publisher._increment_counter("TestMetric", 3)
        publisher._increment_counter("TestMetric", 2)
        assert publisher._counters["TestMetric"] == 5

    def test_get_pending_metrics_count(self):
        """Test getting pending metrics count."""
        publisher = CapabilityMetricsPublisher()
        assert publisher.get_pending_metrics_count() == 0

        publisher._increment_counter("A")
        publisher._increment_counter("B")
        publisher._latencies.append(5.0)

        assert publisher.get_pending_metrics_count() == 3


class TestCapabilityMetricsPublisherFlush:
    """Test metrics flushing."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock CloudWatch client."""
        return MagicMock()

    @pytest.fixture
    def publisher(self, mock_client):
        """Create a publisher with mock client."""
        config = MetricsConfig(
            batch_size=5,
            flush_interval_seconds=60.0,
        )
        return CapabilityMetricsPublisher(config=config, cloudwatch_client=mock_client)

    @pytest.mark.asyncio
    async def test_flush_counters(self, publisher, mock_client):
        """Test flushing counter metrics."""
        publisher._increment_counter(MetricName.CAPABILITY_CHECKS, 10)
        publisher._increment_counter(MetricName.DECISIONS_ALLOW, 8)
        publisher._increment_counter(MetricName.DECISIONS_DENY, 2)

        await publisher._flush_metrics()

        mock_client.put_metric_data.assert_called()
        call_args = mock_client.put_metric_data.call_args
        assert call_args.kwargs["Namespace"] == "Aura/CapabilityGovernance"

        # Counters should be cleared
        assert publisher._counters == {}

    @pytest.mark.asyncio
    async def test_flush_latencies(self, publisher, mock_client):
        """Test flushing latency metrics."""
        publisher._latencies = [1.0, 2.0, 3.0, 4.0, 5.0]

        await publisher._flush_metrics()

        mock_client.put_metric_data.assert_called()

        # Latencies should be cleared
        assert publisher._latencies == []

    @pytest.mark.asyncio
    async def test_flush_empty(self, publisher, mock_client):
        """Test flushing with no metrics."""
        await publisher._flush_metrics()

        mock_client.put_metric_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_cache_hit_rate(self, publisher, mock_client):
        """Test cache hit rate calculation on flush."""
        publisher._increment_counter("cache_hits", 80)
        publisher._increment_counter("cache_misses", 20)

        await publisher._flush_metrics()

        mock_client.put_metric_data.assert_called()
        # Verify cache hit rate metric is included
        call_args = mock_client.put_metric_data.call_args
        metric_data = call_args.kwargs.get("MetricData", [])
        cache_rate_metric = next(
            (
                m
                for m in metric_data
                if m.get("MetricName") == MetricName.CACHE_HIT_RATE
            ),
            None,
        )
        assert cache_rate_metric is not None
        assert cache_rate_metric["Value"] == 80.0  # 80%

    @pytest.mark.asyncio
    async def test_flush_batching(self, mock_client):
        """Test metrics are sent in batches."""
        config = MetricsConfig(batch_size=2)
        publisher = CapabilityMetricsPublisher(
            config=config, cloudwatch_client=mock_client
        )

        # Add 5 counters
        for i in range(5):
            publisher._increment_counter(f"Metric{i}")

        await publisher._flush_metrics()

        # Should make 3 calls (5 metrics / 2 batch size = 3 batches)
        assert mock_client.put_metric_data.call_count == 3

    @pytest.mark.asyncio
    async def test_flush_high_resolution(self, mock_client):
        """Test high resolution storage."""
        config = MetricsConfig(high_resolution=True)
        publisher = CapabilityMetricsPublisher(
            config=config, cloudwatch_client=mock_client
        )

        publisher._increment_counter("TestMetric")
        await publisher._flush_metrics()

        call_args = mock_client.put_metric_data.call_args
        metric_data = call_args.kwargs.get("MetricData", [])
        assert metric_data[0]["StorageResolution"] == 1

    @pytest.mark.asyncio
    async def test_flush_error_handling(self, publisher, mock_client):
        """Test flush handles errors gracefully."""
        mock_client.put_metric_data.side_effect = Exception("CloudWatch error")

        publisher._increment_counter("TestMetric")
        # Should not raise
        await publisher._flush_metrics()

        # Counters should still be cleared to prevent buildup
        assert publisher._counters == {}

    @pytest.mark.asyncio
    async def test_flush_no_client(self):
        """Test flush when no CloudWatch client available."""
        publisher = CapabilityMetricsPublisher()
        publisher._cloudwatch = None

        # Mock import failure
        with patch.dict("sys.modules", {"boto3": None}):
            publisher._increment_counter("TestMetric")
            # Should not raise
            await publisher._flush_metrics()

            # Counters should be cleared
            assert publisher._counters == {}


class TestCapabilityMetricsPublisherLatencyStats:
    """Test latency statistics calculation."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock CloudWatch client."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_latency_statistics(self, mock_client):
        """Test latency statistics are calculated correctly."""
        publisher = CapabilityMetricsPublisher(cloudwatch_client=mock_client)
        publisher._latencies = [10.0, 20.0, 30.0, 40.0, 50.0]

        await publisher._flush_metrics()

        call_args = mock_client.put_metric_data.call_args
        metric_data = call_args.kwargs.get("MetricData", [])

        # Find the latency metric with statistics
        latency_stat_metric = next(
            (
                m
                for m in metric_data
                if m.get("MetricName") == MetricName.CHECK_LATENCY_MS
                and "StatisticValues" in m
            ),
            None,
        )

        assert latency_stat_metric is not None
        stats = latency_stat_metric["StatisticValues"]
        assert stats["Min"] == 10.0
        assert stats["Max"] == 50.0
        assert stats["Sum"] == 150.0
        assert stats["SampleCount"] == 5

    @pytest.mark.asyncio
    async def test_latency_percentiles(self, mock_client):
        """Test latency percentiles are emitted."""
        publisher = CapabilityMetricsPublisher(cloudwatch_client=mock_client)
        publisher._latencies = list(range(1, 101))  # 1 to 100

        await publisher._flush_metrics()

        call_args = mock_client.put_metric_data.call_args
        metric_data = call_args.kwargs.get("MetricData", [])

        metric_names = [m.get("MetricName") for m in metric_data]
        assert f"{MetricName.CHECK_LATENCY_MS}P50" in metric_names
        assert f"{MetricName.CHECK_LATENCY_MS}P95" in metric_names
        assert f"{MetricName.CHECK_LATENCY_MS}P99" in metric_names


class TestCapabilityMetricsPublisherFlushLoop:
    """Test background flush loop."""

    @pytest.mark.asyncio
    async def test_flush_loop_runs(self):
        """Test flush loop executes periodically."""
        mock_client = MagicMock()
        config = MetricsConfig(flush_interval_seconds=0.05)
        publisher = CapabilityMetricsPublisher(
            config=config, cloudwatch_client=mock_client
        )

        publisher._increment_counter("TestMetric")

        await publisher.start()
        await asyncio.sleep(0.1)  # Allow flush loop to run
        await publisher.stop()

        # Should have flushed at least once (plus final flush on stop)
        assert mock_client.put_metric_data.call_count >= 1

    @pytest.mark.asyncio
    async def test_flush_loop_handles_errors(self):
        """Test flush loop continues after errors."""
        mock_client = MagicMock()
        mock_client.put_metric_data.side_effect = [
            Exception("Error 1"),
            None,  # Second call succeeds
        ]
        config = MetricsConfig(flush_interval_seconds=0.02)
        publisher = CapabilityMetricsPublisher(
            config=config, cloudwatch_client=mock_client
        )

        await publisher.start()
        publisher._increment_counter("TestMetric1")
        await asyncio.sleep(0.05)
        publisher._increment_counter("TestMetric2")
        await asyncio.sleep(0.05)
        await publisher.stop()

        # Should have made multiple attempts
        assert mock_client.put_metric_data.call_count >= 2


class TestCapabilityMetricsPublisherCloudWatchClient:
    """Test CloudWatch client initialization."""

    def test_get_client_creates_boto3_client(self):
        """Test client is created via boto3."""
        publisher = CapabilityMetricsPublisher()

        with patch("boto3.client") as mock_boto:
            mock_boto.return_value = MagicMock()
            client = publisher._get_cloudwatch_client()

            mock_boto.assert_called_once_with("cloudwatch")
            assert client is not None

    def test_get_client_cached(self):
        """Test client is cached after first creation."""
        mock_client = MagicMock()
        publisher = CapabilityMetricsPublisher(cloudwatch_client=mock_client)

        client1 = publisher._get_cloudwatch_client()
        client2 = publisher._get_cloudwatch_client()

        assert client1 is client2
        assert client1 is mock_client


class TestGlobalMetricsPublisher:
    """Test global singleton pattern."""

    def test_get_metrics_publisher_singleton(self):
        """Test singleton returns same instance."""
        reset_metrics_publisher()  # Ensure clean state

        publisher1 = get_metrics_publisher()
        publisher2 = get_metrics_publisher()

        assert publisher1 is publisher2

    def test_reset_metrics_publisher(self):
        """Test resetting the singleton."""
        reset_metrics_publisher()

        publisher1 = get_metrics_publisher()
        reset_metrics_publisher()
        publisher2 = get_metrics_publisher()

        assert publisher1 is not publisher2


class TestCapabilityMetricsPublisherIntegration:
    """Integration tests for metrics publisher."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock CloudWatch client."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_client):
        """Test complete workflow: start, record, flush, stop."""
        config = MetricsConfig(flush_interval_seconds=60.0)
        publisher = CapabilityMetricsPublisher(
            config=config, cloudwatch_client=mock_client
        )

        await publisher.start()

        # Record various metrics
        result = CapabilityCheckResult(
            agent_id="agent-1",
            agent_type="TestAgent",
            tool_name="semantic_search",
            action="execute",
            context="development",
            decision=CapabilityDecision.ALLOW,
            reason="OK",
            policy_version="1.0",
            capability_source="base",
            processing_time_ms=5.0,
        )
        publisher.record_check(result)

        publisher.record_violation("high")
        publisher.record_grant_created()
        publisher.record_escalation_requested()
        publisher.record_rate_limit_rejection()
        publisher.record_cache_hit(True)

        # Verify pending count
        assert publisher.get_pending_metrics_count() > 0

        await publisher.stop()

        # Should have flushed
        mock_client.put_metric_data.assert_called()
        assert publisher._counters == {}
        assert publisher._latencies == []

    @pytest.mark.asyncio
    async def test_multiple_checks_aggregated(self, mock_client):
        """Test multiple checks are aggregated before flush."""
        config = MetricsConfig(flush_interval_seconds=60.0)
        publisher = CapabilityMetricsPublisher(
            config=config, cloudwatch_client=mock_client
        )

        # Record multiple checks
        for i in range(10):
            result = CapabilityCheckResult(
                agent_id=f"agent-{i}",
                agent_type="TestAgent",
                tool_name="semantic_search",
                action="execute",
                context="development",
                decision=CapabilityDecision.ALLOW,
                reason="OK",
                policy_version="1.0",
                capability_source="base",
                processing_time_ms=float(i + 1),
            )
            publisher.record_check(result)

        # Verify aggregation
        assert publisher._counters[MetricName.CAPABILITY_CHECKS] == 10
        assert publisher._counters[MetricName.DECISIONS_ALLOW] == 10
        assert len(publisher._latencies) == 10

        await publisher._flush_metrics()

        # All flushed
        assert publisher._counters == {}
        assert publisher._latencies == []
