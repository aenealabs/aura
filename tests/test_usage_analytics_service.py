"""
Tests for Project Aura - Usage Analytics Service

Comprehensive tests for tracking and aggregating platform usage metrics
including API usage, feature adoption, agent execution, and user engagement.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.services.usage_analytics_service import (
    FeatureAdoption,
    MetricType,
    TimeGranularity,
    UsageAnalyticsService,
    UsageEvent,
    UsageMetric,
    UsageSummary,
    UserEngagement,
    get_usage_analytics_service,
)

# =============================================================================
# MetricType Enum Tests
# =============================================================================


class TestMetricType:
    """Tests for MetricType enum."""

    def test_api_request(self):
        """Test API_REQUEST metric type."""
        assert MetricType.API_REQUEST.value == "api_request"

    def test_feature_usage(self):
        """Test FEATURE_USAGE metric type."""
        assert MetricType.FEATURE_USAGE.value == "feature_usage"

    def test_agent_execution(self):
        """Test AGENT_EXECUTION metric type."""
        assert MetricType.AGENT_EXECUTION.value == "agent_execution"

    def test_login(self):
        """Test LOGIN metric type."""
        assert MetricType.LOGIN.value == "login"

    def test_page_view(self):
        """Test PAGE_VIEW metric type."""
        assert MetricType.PAGE_VIEW.value == "page_view"

    def test_search(self):
        """Test SEARCH metric type."""
        assert MetricType.SEARCH.value == "search"

    def test_export(self):
        """Test EXPORT metric type."""
        assert MetricType.EXPORT.value == "export"

    def test_error(self):
        """Test ERROR metric type."""
        assert MetricType.ERROR.value == "error"

    def test_all_metric_types_exist(self):
        """Test all expected metric types are defined."""
        expected = {
            "api_request",
            "feature_usage",
            "agent_execution",
            "login",
            "page_view",
            "search",
            "export",
            "error",
        }
        actual = {m.value for m in MetricType}
        assert actual == expected


# =============================================================================
# TimeGranularity Enum Tests
# =============================================================================


class TestTimeGranularity:
    """Tests for TimeGranularity enum."""

    def test_hourly(self):
        """Test HOURLY granularity."""
        assert TimeGranularity.HOURLY.value == "hourly"

    def test_daily(self):
        """Test DAILY granularity."""
        assert TimeGranularity.DAILY.value == "daily"

    def test_weekly(self):
        """Test WEEKLY granularity."""
        assert TimeGranularity.WEEKLY.value == "weekly"

    def test_monthly(self):
        """Test MONTHLY granularity."""
        assert TimeGranularity.MONTHLY.value == "monthly"

    def test_all_granularities_exist(self):
        """Test all expected granularities are defined."""
        expected = {"hourly", "daily", "weekly", "monthly"}
        actual = {g.value for g in TimeGranularity}
        assert actual == expected


# =============================================================================
# UsageEvent Tests
# =============================================================================


class TestUsageEvent:
    """Tests for UsageEvent dataclass."""

    def test_minimal_event(self):
        """Test creating minimal usage event."""
        event = UsageEvent(
            event_id="evt_123",
            customer_id="cust_abc",
            user_id="user_xyz",
            metric_type=MetricType.API_REQUEST,
            event_name="vulnerability_scan",
            timestamp=datetime.now(timezone.utc),
        )

        assert event.event_id == "evt_123"
        assert event.customer_id == "cust_abc"
        assert event.user_id == "user_xyz"
        assert event.metric_type == MetricType.API_REQUEST
        assert event.event_name == "vulnerability_scan"
        assert event.metadata == {}
        assert event.duration_ms is None
        assert event.status == "success"
        assert event.error_message is None

    def test_full_event(self):
        """Test creating full usage event."""
        event = UsageEvent(
            event_id="evt_456",
            customer_id="cust_def",
            user_id="user_uvw",
            metric_type=MetricType.AGENT_EXECUTION,
            event_name="coder_agent",
            timestamp=datetime.now(timezone.utc),
            metadata={"agent_type": "coder", "model": "gpt-4"},
            duration_ms=5000,
            status="success",
            error_message=None,
        )

        assert event.metadata["agent_type"] == "coder"
        assert event.duration_ms == 5000

    def test_error_event(self):
        """Test creating error event."""
        event = UsageEvent(
            event_id="evt_err",
            customer_id="cust_123",
            user_id="user_123",
            metric_type=MetricType.ERROR,
            event_name="rate_limit_exceeded",
            timestamp=datetime.now(timezone.utc),
            status="error",
            error_message="Rate limit exceeded: 100 requests/minute",
        )

        assert event.status == "error"
        assert "Rate limit" in event.error_message


# =============================================================================
# UsageMetric Tests
# =============================================================================


class TestUsageMetric:
    """Tests for UsageMetric dataclass."""

    def test_basic_metric(self):
        """Test basic usage metric."""
        metric = UsageMetric(
            metric_name="API Requests",
            value=1500.0,
            unit="requests",
        )

        assert metric.metric_name == "API Requests"
        assert metric.value == 1500.0
        assert metric.unit == "requests"
        assert metric.change_percent is None
        assert metric.trend == "stable"

    def test_metric_with_trend(self):
        """Test metric with change and trend."""
        metric = UsageMetric(
            metric_name="Active Users",
            value=250.0,
            unit="users",
            change_percent=15.5,
            trend="up",
        )

        assert metric.change_percent == 15.5
        assert metric.trend == "up"

    def test_metric_with_down_trend(self):
        """Test metric with downward trend."""
        metric = UsageMetric(
            metric_name="Error Rate",
            value=2.5,
            unit="%",
            change_percent=-30.0,
            trend="down",
        )

        assert metric.change_percent == -30.0
        assert metric.trend == "down"


# =============================================================================
# FeatureAdoption Tests
# =============================================================================


class TestFeatureAdoption:
    """Tests for FeatureAdoption dataclass."""

    def test_feature_adoption(self):
        """Test feature adoption statistics."""
        adoption = FeatureAdoption(
            feature_name="vulnerability_scanner",
            total_users=100,
            active_users=75,
            adoption_rate=75.0,
            usage_count=500,
            avg_daily_usage=16.7,
        )

        assert adoption.feature_name == "vulnerability_scanner"
        assert adoption.total_users == 100
        assert adoption.active_users == 75
        assert adoption.adoption_rate == 75.0
        assert adoption.trend == "stable"

    def test_feature_with_trend(self):
        """Test feature with growth trend."""
        adoption = FeatureAdoption(
            feature_name="code_review",
            total_users=200,
            active_users=180,
            adoption_rate=90.0,
            usage_count=1000,
            avg_daily_usage=33.3,
            trend="up",
        )

        assert adoption.trend == "up"


# =============================================================================
# UserEngagement Tests
# =============================================================================


class TestUserEngagement:
    """Tests for UserEngagement dataclass."""

    def test_user_engagement(self):
        """Test user engagement metrics."""
        engagement = UserEngagement(
            total_users=500,
            active_users_daily=150,
            active_users_weekly=350,
            active_users_monthly=450,
            avg_session_duration_minutes=25.5,
            avg_actions_per_session=12.3,
            retention_rate_7d=70.0,
            retention_rate_30d=55.0,
        )

        assert engagement.total_users == 500
        assert engagement.active_users_daily == 150
        assert engagement.active_users_weekly == 350
        assert engagement.active_users_monthly == 450
        assert engagement.avg_session_duration_minutes == 25.5
        assert engagement.retention_rate_7d == 70.0


# =============================================================================
# UsageSummary Tests
# =============================================================================


class TestUsageSummary:
    """Tests for UsageSummary dataclass."""

    def test_usage_summary(self):
        """Test complete usage summary."""
        now = datetime.now(timezone.utc)
        engagement = UserEngagement(
            total_users=100,
            active_users_daily=50,
            active_users_weekly=80,
            active_users_monthly=95,
            avg_session_duration_minutes=20.0,
            avg_actions_per_session=10.0,
            retention_rate_7d=80.0,
            retention_rate_30d=60.0,
        )

        summary = UsageSummary(
            period_start=now - timedelta(days=30),
            period_end=now,
            total_api_calls=10000,
            total_agent_executions=500,
            total_active_users=95,
            key_metrics=[
                UsageMetric(metric_name="Requests", value=10000, unit="count")
            ],
            feature_adoption=[
                FeatureAdoption(
                    feature_name="scanner",
                    total_users=100,
                    active_users=80,
                    adoption_rate=80.0,
                    usage_count=400,
                    avg_daily_usage=13.3,
                )
            ],
            engagement=engagement,
            top_features=["scanner", "reviewer", "coder"],
            top_errors=[{"error": "timeout", "count": 10}],
        )

        assert summary.total_api_calls == 10000
        assert summary.total_agent_executions == 500
        assert len(summary.key_metrics) == 1
        assert len(summary.feature_adoption) == 1
        assert len(summary.top_features) == 3


# =============================================================================
# UsageAnalyticsService Initialization Tests
# =============================================================================


class TestUsageAnalyticsServiceInit:
    """Tests for UsageAnalyticsService initialization."""

    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        service = UsageAnalyticsService(mode="mock")

        assert service.mode == "mock"
        assert service._events == []
        assert service._metrics_cache == {}

    def test_init_default_mode(self):
        """Test default mode is mock."""
        service = UsageAnalyticsService()
        assert service.mode == "mock"

    def test_init_aws_mode(self):
        """Test initialization in AWS mode - lines 136-139."""
        with (
            patch("boto3.client") as mock_client,
            patch("boto3.resource") as mock_resource,
        ):
            mock_client.return_value = "mock_cloudwatch"
            mock_resource.return_value = "mock_dynamodb"

            service = UsageAnalyticsService(mode="aws")

            assert service.mode == "aws"
            mock_client.assert_called_once_with("cloudwatch")
            mock_resource.assert_called_once_with("dynamodb")


# =============================================================================
# UsageAnalyticsService Event Tracking Tests
# =============================================================================


class TestUsageAnalyticsServiceTracking:
    """Tests for event tracking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = UsageAnalyticsService(mode="mock")

    @pytest.mark.asyncio
    async def test_track_event(self):
        """Test tracking a usage event."""
        event = await self.service.track_event(
            customer_id="cust_123",
            user_id="user_456",
            metric_type=MetricType.API_REQUEST,
            event_name="vulnerability_scan",
        )

        assert event.event_id.startswith("evt_")
        assert event.customer_id == "cust_123"
        assert event.user_id == "user_456"
        assert event.metric_type == MetricType.API_REQUEST
        assert len(self.service._events) == 1

    @pytest.mark.asyncio
    async def test_track_event_with_metadata(self):
        """Test tracking event with metadata."""
        event = await self.service.track_event(
            customer_id="cust_123",
            user_id="user_456",
            metric_type=MetricType.API_REQUEST,
            event_name="api_call",
            metadata={"endpoint": "/api/v1/scan", "method": "POST"},
        )

        assert event.metadata["endpoint"] == "/api/v1/scan"
        assert event.metadata["method"] == "POST"

    @pytest.mark.asyncio
    async def test_track_event_with_duration(self):
        """Test tracking timed event."""
        event = await self.service.track_event(
            customer_id="cust_123",
            user_id="user_456",
            metric_type=MetricType.AGENT_EXECUTION,
            event_name="coder_agent",
            duration_ms=3500,
        )

        assert event.duration_ms == 3500

    @pytest.mark.asyncio
    async def test_track_error_event(self):
        """Test tracking error event."""
        event = await self.service.track_event(
            customer_id="cust_123",
            user_id="user_456",
            metric_type=MetricType.ERROR,
            event_name="validation_failed",
            status="error",
            error_message="Invalid input format",
        )

        assert event.status == "error"
        assert event.error_message == "Invalid input format"


# =============================================================================
# UsageAnalyticsService API Usage Tests
# =============================================================================


class TestUsageAnalyticsServiceAPIUsage:
    """Tests for API usage analytics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = UsageAnalyticsService(mode="mock")

    @pytest.mark.asyncio
    async def test_get_api_usage_empty(self):
        """Test API usage with no events."""
        result = await self.service.get_api_usage()

        assert result["total_requests"] == 0
        assert result["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_get_api_usage_with_events(self):
        """Test API usage with tracked events."""
        # Track some API events
        for i in range(10):
            await self.service.track_event(
                customer_id="cust_123",
                user_id="user_456",
                metric_type=MetricType.API_REQUEST,
                event_name="api_call",
                metadata={"endpoint": f"/api/v1/endpoint{i % 3}"},
                duration_ms=100 + i * 10,
                status="success",
            )

        result = await self.service.get_api_usage(days=30)

        assert result["total_requests"] == 10
        assert result["success_rate"] == 100.0
        assert "by_endpoint" in result
        assert "latency" in result

    @pytest.mark.asyncio
    async def test_get_api_usage_by_customer(self):
        """Test API usage filtered by customer."""
        await self.service.track_event(
            customer_id="cust_a",
            user_id="user_1",
            metric_type=MetricType.API_REQUEST,
            event_name="api_call",
        )
        await self.service.track_event(
            customer_id="cust_b",
            user_id="user_2",
            metric_type=MetricType.API_REQUEST,
            event_name="api_call",
        )

        result = await self.service.get_api_usage(customer_id="cust_a")

        assert result["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_get_api_usage_latency_percentiles(self):
        """Test API usage latency percentiles calculation."""
        # Track many events for percentile calculation
        for i in range(50):
            await self.service.track_event(
                customer_id="cust_123",
                user_id="user_456",
                metric_type=MetricType.API_REQUEST,
                event_name="api_call",
                duration_ms=50 + i * 2,
            )

        result = await self.service.get_api_usage()

        assert result["latency"]["avg_ms"] > 0
        assert result["latency"]["p50_ms"] > 0
        assert result["latency"]["p95_ms"] >= result["latency"]["p50_ms"]

    @pytest.mark.asyncio
    async def test_get_api_usage_by_status(self):
        """Test API usage with mixed statuses."""
        for i in range(10):
            await self.service.track_event(
                customer_id="cust_123",
                user_id="user_456",
                metric_type=MetricType.API_REQUEST,
                event_name="api_call",
                status="success" if i < 8 else "error",
            )

        result = await self.service.get_api_usage()

        assert result["by_status"]["success"] == 8
        assert result["by_status"]["error"] == 2
        assert result["success_rate"] == 80.0


# =============================================================================
# UsageAnalyticsService Feature Adoption Tests
# =============================================================================


class TestUsageAnalyticsServiceFeatureAdoption:
    """Tests for feature adoption analytics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = UsageAnalyticsService(mode="mock")

    @pytest.mark.asyncio
    async def test_get_feature_adoption_empty(self):
        """Test feature adoption with no events."""
        result = await self.service.get_feature_adoption()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_feature_adoption_with_events(self):
        """Test feature adoption with tracked events."""
        # Multiple users using different features
        for i in range(5):
            await self.service.track_event(
                customer_id="cust_123",
                user_id=f"user_{i}",
                metric_type=MetricType.FEATURE_USAGE,
                event_name="vulnerability_scanner",
            )

        for i in range(3):
            await self.service.track_event(
                customer_id="cust_123",
                user_id=f"user_{i}",
                metric_type=MetricType.FEATURE_USAGE,
                event_name="code_reviewer",
            )

        result = await self.service.get_feature_adoption()

        assert len(result) == 2
        # Should be sorted by adoption rate
        assert result[0].adoption_rate >= result[1].adoption_rate

    @pytest.mark.asyncio
    async def test_get_feature_adoption_calculates_rates(self):
        """Test adoption rate calculation."""
        # 3 unique users
        await self.service.track_event(
            customer_id="cust_123",
            user_id="user_1",
            metric_type=MetricType.FEATURE_USAGE,
            event_name="feature_a",
        )
        await self.service.track_event(
            customer_id="cust_123",
            user_id="user_2",
            metric_type=MetricType.FEATURE_USAGE,
            event_name="feature_a",
        )
        await self.service.track_event(
            customer_id="cust_123",
            user_id="user_3",
            metric_type=MetricType.FEATURE_USAGE,
            event_name="feature_b",
        )

        result = await self.service.get_feature_adoption()

        feature_a = next(f for f in result if f.feature_name == "feature_a")
        assert feature_a.active_users == 2
        assert feature_a.total_users == 3


# =============================================================================
# UsageAnalyticsService Agent Statistics Tests
# =============================================================================


class TestUsageAnalyticsServiceAgentStats:
    """Tests for agent execution statistics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = UsageAnalyticsService(mode="mock")

    @pytest.mark.asyncio
    async def test_get_agent_statistics_empty(self):
        """Test agent statistics with no events."""
        result = await self.service.get_agent_statistics()

        assert result["total_executions"] == 0
        assert result["by_agent"] == {}

    @pytest.mark.asyncio
    async def test_get_agent_statistics_with_events(self):
        """Test agent statistics with tracked events."""
        for i in range(10):
            await self.service.track_event(
                customer_id="cust_123",
                user_id="user_456",
                metric_type=MetricType.AGENT_EXECUTION,
                event_name="agent_run",
                metadata={"agent_type": "coder" if i < 6 else "reviewer"},
                duration_ms=1000 + i * 100,
                status="success" if i < 8 else "failure",
            )

        result = await self.service.get_agent_statistics()

        assert result["total_executions"] == 10
        assert result["total_success"] == 8
        assert "coder" in result["by_agent"]
        assert "reviewer" in result["by_agent"]

    @pytest.mark.asyncio
    async def test_get_agent_statistics_success_rate(self):
        """Test agent success rate calculation."""
        for _ in range(8):
            await self.service.track_event(
                customer_id="cust_123",
                user_id="user_456",
                metric_type=MetricType.AGENT_EXECUTION,
                event_name="agent_run",
                metadata={"agent_type": "coder"},
                status="success",
            )

        for _ in range(2):
            await self.service.track_event(
                customer_id="cust_123",
                user_id="user_456",
                metric_type=MetricType.AGENT_EXECUTION,
                event_name="agent_run",
                metadata={"agent_type": "coder"},
                status="failure",
            )

        result = await self.service.get_agent_statistics()

        assert result["success_rate"] == 80.0
        assert result["by_agent"]["coder"]["success_rate"] == 80.0

    @pytest.mark.asyncio
    async def test_get_agent_statistics_avg_duration(self):
        """Test agent average duration calculation."""
        await self.service.track_event(
            customer_id="cust_123",
            user_id="user_456",
            metric_type=MetricType.AGENT_EXECUTION,
            event_name="agent_run",
            metadata={"agent_type": "coder"},
            duration_ms=1000,
        )
        await self.service.track_event(
            customer_id="cust_123",
            user_id="user_456",
            metric_type=MetricType.AGENT_EXECUTION,
            event_name="agent_run",
            metadata={"agent_type": "coder"},
            duration_ms=2000,
        )

        result = await self.service.get_agent_statistics()

        assert result["avg_duration_ms"] == 1500.0


# =============================================================================
# UsageAnalyticsService User Engagement Tests
# =============================================================================


class TestUsageAnalyticsServiceEngagement:
    """Tests for user engagement analytics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = UsageAnalyticsService(mode="mock")

    @pytest.mark.asyncio
    async def test_get_user_engagement_empty(self):
        """Test user engagement with no events."""
        result = await self.service.get_user_engagement()

        assert result.total_users == 0
        assert result.active_users_daily == 0

    @pytest.mark.asyncio
    async def test_get_user_engagement_with_events(self):
        """Test user engagement with tracked events."""
        # Track events for multiple users
        for i in range(5):
            await self.service.track_event(
                customer_id="cust_123",
                user_id=f"user_{i}",
                metric_type=MetricType.PAGE_VIEW,
                event_name="dashboard_view",
            )

        result = await self.service.get_user_engagement()

        assert result.total_users == 5
        assert result.active_users_daily == 5
        assert result.active_users_weekly == 5
        assert result.active_users_monthly == 5

    @pytest.mark.asyncio
    async def test_get_user_engagement_actions_per_session(self):
        """Test average actions per session calculation."""
        # User with multiple actions
        for _ in range(10):
            await self.service.track_event(
                customer_id="cust_123",
                user_id="user_1",
                metric_type=MetricType.PAGE_VIEW,
                event_name="page_view",
            )

        result = await self.service.get_user_engagement()

        assert result.avg_actions_per_session > 0


# =============================================================================
# UsageAnalyticsService Usage Summary Tests
# =============================================================================


class TestUsageAnalyticsServiceSummary:
    """Tests for usage summary."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = UsageAnalyticsService(mode="mock")

    @pytest.mark.asyncio
    async def test_get_usage_summary_empty(self):
        """Test usage summary with no events."""
        result = await self.service.get_usage_summary()

        assert result.total_api_calls == 0
        assert result.total_agent_executions == 0
        assert len(result.key_metrics) == 5

    @pytest.mark.asyncio
    async def test_get_usage_summary_with_events(self):
        """Test complete usage summary with events."""
        # Track various types of events
        for i in range(5):
            await self.service.track_event(
                customer_id="cust_123",
                user_id=f"user_{i}",
                metric_type=MetricType.API_REQUEST,
                event_name="api_call",
                duration_ms=100,
            )

        for i in range(3):
            await self.service.track_event(
                customer_id="cust_123",
                user_id=f"user_{i}",
                metric_type=MetricType.AGENT_EXECUTION,
                event_name="agent_run",
                metadata={"agent_type": "coder"},
            )

        for i in range(4):
            await self.service.track_event(
                customer_id="cust_123",
                user_id=f"user_{i}",
                metric_type=MetricType.FEATURE_USAGE,
                event_name="vulnerability_scanner",
            )

        result = await self.service.get_usage_summary()

        assert result.total_api_calls == 5
        assert result.total_agent_executions == 3
        assert len(result.feature_adoption) > 0
        assert result.engagement is not None

    @pytest.mark.asyncio
    async def test_get_usage_summary_by_customer(self):
        """Test usage summary filtered by customer."""
        await self.service.track_event(
            customer_id="cust_a",
            user_id="user_1",
            metric_type=MetricType.API_REQUEST,
            event_name="api_call",
        )
        await self.service.track_event(
            customer_id="cust_b",
            user_id="user_2",
            metric_type=MetricType.API_REQUEST,
            event_name="api_call",
        )

        result = await self.service.get_usage_summary(customer_id="cust_a")

        assert result.total_api_calls == 1

    @pytest.mark.asyncio
    async def test_get_usage_summary_key_metrics(self):
        """Test key metrics in usage summary."""
        result = await self.service.get_usage_summary()

        metric_names = [m.metric_name for m in result.key_metrics]
        assert "API Requests" in metric_names
        assert "Agent Executions" in metric_names
        assert "API Success Rate" in metric_names

    @pytest.mark.asyncio
    async def test_get_usage_summary_top_features(self):
        """Test top features in usage summary."""
        for i in range(10):
            await self.service.track_event(
                customer_id="cust_123",
                user_id=f"user_{i}",
                metric_type=MetricType.FEATURE_USAGE,
                event_name="top_feature",
            )

        result = await self.service.get_usage_summary()

        assert "top_feature" in result.top_features


# =============================================================================
# Singleton Factory Tests
# =============================================================================


class TestGetUsageAnalyticsService:
    """Tests for singleton factory function."""

    def teardown_method(self):
        """Reset singleton after each test."""
        import src.services.usage_analytics_service as module

        module._service = None

    def test_get_service_creates_instance(self):
        """Test factory creates service instance."""
        service = get_usage_analytics_service()
        assert service is not None
        assert isinstance(service, UsageAnalyticsService)

    def test_get_service_returns_singleton(self):
        """Test factory returns same instance."""
        service1 = get_usage_analytics_service()
        service2 = get_usage_analytics_service()
        assert service1 is service2

    def test_get_service_with_mode(self):
        """Test factory with explicit mode."""
        service = get_usage_analytics_service(mode="mock")
        assert service.mode == "mock"

    @patch.dict("os.environ", {"USAGE_ANALYTICS_MODE": "mock"})
    def test_get_service_from_env(self):
        """Test factory reads mode from environment."""
        service = get_usage_analytics_service()
        assert service.mode == "mock"


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestUsageAnalyticsEdgeCases:
    """Tests for edge cases and error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = UsageAnalyticsService(mode="mock")

    @pytest.mark.asyncio
    async def test_old_events_excluded(self):
        """Test that old events are excluded from analytics."""
        # Manually add an old event
        old_event = UsageEvent(
            event_id="evt_old",
            customer_id="cust_123",
            user_id="user_456",
            metric_type=MetricType.API_REQUEST,
            event_name="old_call",
            timestamp=datetime.now(timezone.utc) - timedelta(days=60),
        )
        self.service._events.append(old_event)

        result = await self.service.get_api_usage(days=30)

        assert result["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_latency_with_no_duration(self):
        """Test latency calculation when no durations recorded."""
        await self.service.track_event(
            customer_id="cust_123",
            user_id="user_456",
            metric_type=MetricType.API_REQUEST,
            event_name="api_call",
            duration_ms=None,
        )

        result = await self.service.get_api_usage()

        assert result["latency"]["avg_ms"] == 0

    @pytest.mark.asyncio
    async def test_success_rate_no_events(self):
        """Test success rate with no events returns 0."""
        result = await self.service.get_agent_statistics()
        assert result["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_feature_adoption_single_user(self):
        """Test feature adoption with single user."""
        await self.service.track_event(
            customer_id="cust_123",
            user_id="user_1",
            metric_type=MetricType.FEATURE_USAGE,
            event_name="solo_feature",
        )

        result = await self.service.get_feature_adoption()

        assert len(result) == 1
        assert result[0].adoption_rate == 100.0

    @pytest.mark.asyncio
    async def test_multiple_events_same_user(self):
        """Test handling multiple events from same user."""
        for _ in range(10):
            await self.service.track_event(
                customer_id="cust_123",
                user_id="user_1",
                metric_type=MetricType.FEATURE_USAGE,
                event_name="repeat_feature",
            )

        result = await self.service.get_feature_adoption()

        assert result[0].active_users == 1
        assert result[0].usage_count == 10


# =============================================================================
# AWS Mode Tests (CloudWatch + DynamoDB Integration)
# =============================================================================


class TestAwsMode:
    """Tests for AWS mode functionality - covers _publish_to_cloudwatch and _query_events."""

    @pytest.mark.asyncio
    async def test_track_event_aws_mode(self):
        """Test track_event in AWS mode - covers lines 186-187."""
        mock_cloudwatch = type(
            "MockCloudWatch", (), {"put_metric_data": lambda *args, **kwargs: None}
        )()
        mock_dynamodb = type("MockDynamoDB", (), {})()

        with (
            patch("boto3.client", return_value=mock_cloudwatch),
            patch("boto3.resource", return_value=mock_dynamodb),
        ):
            service = UsageAnalyticsService(mode="aws")
            service._cloudwatch = mock_cloudwatch
            service._dynamodb = mock_dynamodb

            event = await service.track_event(
                customer_id="cust_aws",
                user_id="user_aws",
                metric_type=MetricType.API_REQUEST,
                event_name="test_api_call",
                duration_ms=150,
            )

            assert event.customer_id == "cust_aws"
            assert event.metric_type == MetricType.API_REQUEST

    @pytest.mark.asyncio
    async def test_get_api_usage_aws_mode(self):
        """Test get_api_usage in AWS mode - covers line 219."""
        mock_cloudwatch = type(
            "MockCloudWatch", (), {"put_metric_data": lambda *args, **kwargs: None}
        )()
        mock_dynamodb = type("MockDynamoDB", (), {})()

        with (
            patch("boto3.client", return_value=mock_cloudwatch),
            patch("boto3.resource", return_value=mock_dynamodb),
        ):
            service = UsageAnalyticsService(mode="aws")

            result = await service.get_api_usage(customer_id="cust_aws", days=7)

            assert "total_requests" in result
            assert result["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_publish_to_cloudwatch_success(self):
        """Test _publish_to_cloudwatch success path - covers lines 578-597."""
        mock_cloudwatch = MagicMock()

        # Create service in mock mode first, then override _cloudwatch
        service = UsageAnalyticsService(mode="mock")
        service.mode = "aws"  # Switch mode
        service._cloudwatch = mock_cloudwatch

        event = UsageEvent(
            event_id="evt_1",
            customer_id="cust_1",
            user_id="user_1",
            metric_type=MetricType.API_REQUEST,
            event_name="test_event",
            timestamp=datetime.now(timezone.utc),
        )

        await service._publish_to_cloudwatch(event)

        assert mock_cloudwatch.put_metric_data.call_count >= 1

    @pytest.mark.asyncio
    async def test_publish_to_cloudwatch_with_duration(self):
        """Test _publish_to_cloudwatch with duration_ms - covers lines 599-611."""
        mock_cloudwatch = MagicMock()

        # Create service in mock mode first, then override _cloudwatch
        service = UsageAnalyticsService(mode="mock")
        service.mode = "aws"  # Switch mode
        service._cloudwatch = mock_cloudwatch

        event = UsageEvent(
            event_id="evt_2",
            customer_id="cust_2",
            user_id="user_2",
            metric_type=MetricType.API_REQUEST,
            event_name="test_event_with_duration",
            timestamp=datetime.now(timezone.utc),
            duration_ms=250,
        )

        await service._publish_to_cloudwatch(event)

        # Should call twice: once for count, once for duration
        assert mock_cloudwatch.put_metric_data.call_count == 2

    @pytest.mark.asyncio
    async def test_publish_to_cloudwatch_error_handling(self):
        """Test _publish_to_cloudwatch error handling - covers lines 613-614."""

        def mock_put_metric_data(**kwargs):
            raise Exception("CloudWatch error")

        mock_cloudwatch = type(
            "MockCloudWatch", (), {"put_metric_data": mock_put_metric_data}
        )()

        with (
            patch("boto3.client", return_value=mock_cloudwatch),
            patch("boto3.resource"),
        ):
            service = UsageAnalyticsService(mode="aws")
            service._cloudwatch = mock_cloudwatch

            event = UsageEvent(
                event_id="evt_3",
                customer_id="cust_3",
                user_id="user_3",
                metric_type=MetricType.API_REQUEST,
                event_name="test_event_error",
                timestamp=datetime.now(timezone.utc),
            )

            # Should not raise, just log error
            await service._publish_to_cloudwatch(event)

    @pytest.mark.asyncio
    async def test_query_events_returns_empty(self):
        """Test _query_events returns empty list - covers line 628."""
        with patch("boto3.client"), patch("boto3.resource"):
            service = UsageAnalyticsService(mode="aws")

            result = await service._query_events(
                metric_type=MetricType.API_REQUEST,
                customer_id="cust_test",
            )

            assert result == []
