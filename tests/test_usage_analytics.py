"""
Tests for Usage Analytics Service and API Endpoints.
"""

from datetime import datetime, timezone

import pytest

from src.services.usage_analytics_service import (
    MetricType,
    TimeGranularity,
    UsageAnalyticsService,
    UsageEvent,
    get_usage_analytics_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def analytics_service():
    """Create a fresh analytics service for testing."""
    return UsageAnalyticsService(mode="mock")


@pytest.fixture
async def sample_events(analytics_service):
    """Pre-populate with sample events."""
    # API requests
    for i in range(10):
        await analytics_service.track_event(
            customer_id="customer-1",
            user_id=f"user-{i % 3}",
            metric_type=MetricType.API_REQUEST,
            event_name=f"/api/v1/endpoint-{i % 2}",
            duration_ms=100 + i * 10,
            status="success" if i % 5 != 0 else "failure",
        )

    # Feature usage
    features = ["dashboard", "agents", "approvals", "settings"]
    for i, feature in enumerate(features):
        for j in range(i + 2):
            await analytics_service.track_event(
                customer_id="customer-1",
                user_id=f"user-{j}",
                metric_type=MetricType.FEATURE_USAGE,
                event_name=feature,
                status="success",
            )

    # Agent executions
    for i in range(5):
        await analytics_service.track_event(
            customer_id="customer-1",
            user_id="user-0",
            metric_type=MetricType.AGENT_EXECUTION,
            event_name="code_reviewer",
            duration_ms=5000 + i * 1000,
            status="success",
        )

    return analytics_service


# =============================================================================
# MetricType Enum Tests
# =============================================================================


class TestMetricType:
    """Tests for MetricType enum."""

    def test_all_metric_types_exist(self):
        """Verify all expected metric types exist."""
        expected = [
            "api_request",
            "feature_usage",
            "agent_execution",
            "login",
            "page_view",
            "search",
            "export",
            "error",
        ]
        for metric in expected:
            assert MetricType(metric) is not None

    def test_invalid_metric_type(self):
        """Verify invalid metric type raises ValueError."""
        with pytest.raises(ValueError):
            MetricType("invalid_type")


# =============================================================================
# TimeGranularity Enum Tests
# =============================================================================


class TestTimeGranularity:
    """Tests for TimeGranularity enum."""

    def test_all_granularities_exist(self):
        """Verify all time granularities exist."""
        expected = ["hourly", "daily", "weekly", "monthly"]
        for gran in expected:
            assert TimeGranularity(gran) is not None


# =============================================================================
# UsageEvent Dataclass Tests
# =============================================================================


class TestUsageEvent:
    """Tests for UsageEvent dataclass."""

    def test_create_usage_event(self):
        """Test creating a UsageEvent."""
        event = UsageEvent(
            event_id="evt_123",
            customer_id="cust_1",
            user_id="user_1",
            metric_type=MetricType.API_REQUEST,
            event_name="/api/test",
            timestamp=datetime.now(timezone.utc),
            duration_ms=150,
            status="success",
            metadata={"key": "value"},
        )
        assert event.event_id == "evt_123"
        assert event.metric_type == MetricType.API_REQUEST
        assert event.status == "success"

    def test_event_defaults(self):
        """Test UsageEvent default values."""
        event = UsageEvent(
            event_id="evt_456",
            customer_id="cust_1",
            user_id="user_1",
            metric_type=MetricType.FEATURE_USAGE,
            event_name="dashboard",
            timestamp=datetime.now(timezone.utc),
        )
        assert event.duration_ms is None
        assert event.status == "success"
        assert event.metadata == {}


# =============================================================================
# UsageAnalyticsService Tests
# =============================================================================


class TestUsageAnalyticsService:
    """Tests for UsageAnalyticsService."""

    @pytest.mark.asyncio
    async def test_track_event(self, analytics_service):
        """Test tracking an event."""
        event = await analytics_service.track_event(
            customer_id="customer-1",
            user_id="user-1",
            metric_type=MetricType.API_REQUEST,
            event_name="/api/v1/test",
            duration_ms=100,
            status="success",
        )

        assert event.event_id.startswith("evt_")
        assert event.customer_id == "customer-1"
        assert event.user_id == "user-1"
        assert event.metric_type == MetricType.API_REQUEST
        assert event.event_name == "/api/v1/test"

    @pytest.mark.asyncio
    async def test_track_event_with_metadata(self, analytics_service):
        """Test tracking event with metadata."""
        metadata = {"endpoint": "/api/test", "method": "GET"}
        event = await analytics_service.track_event(
            customer_id="customer-1",
            user_id="user-1",
            metric_type=MetricType.API_REQUEST,
            event_name="api_call",
            metadata=metadata,
        )

        assert event.metadata == metadata

    @pytest.mark.asyncio
    async def test_get_api_usage(self, sample_events):
        """Test getting API usage statistics."""
        usage = await sample_events.get_api_usage(customer_id="customer-1", days=30)

        assert "total_requests" in usage
        assert "success_rate" in usage
        assert "by_status" in usage
        assert "latency" in usage
        assert usage["total_requests"] == 10

    @pytest.mark.asyncio
    async def test_get_api_usage_success_rate(self, sample_events):
        """Test API usage success rate calculation."""
        usage = await sample_events.get_api_usage(customer_id="customer-1", days=30)

        # 8 successful, 2 failed (indices 0 and 5)
        # success_rate is returned as percentage (0-100)
        assert usage["by_status"]["success"] == 8
        assert usage["by_status"]["failure"] == 2
        assert usage["success_rate"] == 80.0

    @pytest.mark.asyncio
    async def test_get_feature_adoption(self, sample_events):
        """Test getting feature adoption metrics."""
        adoption = await sample_events.get_feature_adoption(
            customer_id="customer-1", days=30
        )

        assert len(adoption) > 0
        for feature in adoption:
            assert hasattr(feature, "feature_name")
            assert hasattr(feature, "usage_count")
            assert hasattr(feature, "active_users")
            assert hasattr(feature, "adoption_rate")

    @pytest.mark.asyncio
    async def test_get_agent_statistics(self, sample_events):
        """Test getting agent execution statistics."""
        stats = await sample_events.get_agent_statistics(
            customer_id="customer-1", days=30
        )

        assert "total_executions" in stats
        assert stats["total_executions"] == 5

    @pytest.mark.asyncio
    async def test_empty_customer_returns_empty_metrics(self, analytics_service):
        """Test that a customer with no events returns empty metrics."""
        usage = await analytics_service.get_api_usage(
            customer_id="nonexistent", days=30
        )

        assert usage["total_requests"] == 0
        assert usage["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_filter_by_customer(self, analytics_service):
        """Test filtering events by customer."""
        # Add events for two customers
        await analytics_service.track_event(
            customer_id="customer-1",
            user_id="user-1",
            metric_type=MetricType.API_REQUEST,
            event_name="/api/test",
        )
        await analytics_service.track_event(
            customer_id="customer-2",
            user_id="user-2",
            metric_type=MetricType.API_REQUEST,
            event_name="/api/test",
        )

        usage_1 = await analytics_service.get_api_usage(
            customer_id="customer-1", days=30
        )
        usage_2 = await analytics_service.get_api_usage(
            customer_id="customer-2", days=30
        )

        assert usage_1["total_requests"] == 1
        assert usage_2["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_admin_sees_all_customers(self, analytics_service):
        """Test that admin (customer_id=None) sees all customers."""
        await analytics_service.track_event(
            customer_id="customer-1",
            user_id="user-1",
            metric_type=MetricType.API_REQUEST,
            event_name="/api/test",
        )
        await analytics_service.track_event(
            customer_id="customer-2",
            user_id="user-2",
            metric_type=MetricType.API_REQUEST,
            event_name="/api/test",
        )

        usage_all = await analytics_service.get_api_usage(customer_id=None, days=30)
        assert usage_all["total_requests"] == 2

    @pytest.mark.asyncio
    async def test_date_filtering(self, analytics_service):
        """Test filtering events by date range."""
        # Track an event
        await analytics_service.track_event(
            customer_id="customer-1",
            user_id="user-1",
            metric_type=MetricType.API_REQUEST,
            event_name="/api/test",
        )

        # Get usage for 1 day should include the event
        usage_recent = await analytics_service.get_api_usage(
            customer_id="customer-1", days=1
        )
        assert usage_recent["total_requests"] == 1


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_service_returns_instance(self):
        """Test that get_usage_analytics_service returns an instance."""
        # Reset the singleton
        import src.services.usage_analytics_service as module

        module._service = None

        service = get_usage_analytics_service()
        assert service is not None
        assert isinstance(service, UsageAnalyticsService)

    def test_singleton_returns_same_instance(self):
        """Test that repeated calls return the same instance."""
        import src.services.usage_analytics_service as module

        module._service = None

        service1 = get_usage_analytics_service()
        service2 = get_usage_analytics_service()
        assert service1 is service2


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_track_event_with_zero_duration(self, analytics_service):
        """Test tracking event with zero duration."""
        event = await analytics_service.track_event(
            customer_id="customer-1",
            user_id="user-1",
            metric_type=MetricType.API_REQUEST,
            event_name="/api/test",
            duration_ms=0,
        )
        assert event.duration_ms == 0

    @pytest.mark.asyncio
    async def test_track_failed_event(self, analytics_service):
        """Test tracking a failed event."""
        event = await analytics_service.track_event(
            customer_id="customer-1",
            user_id="user-1",
            metric_type=MetricType.API_REQUEST,
            event_name="/api/test",
            status="failure",
        )
        assert event.status == "failure"

    @pytest.mark.asyncio
    async def test_adoption_rate_percentage(self, sample_events):
        """Test adoption rate is a valid percentage."""
        adoption = await sample_events.get_feature_adoption(
            customer_id="customer-1", days=30
        )

        for feature in adoption:
            assert 0 <= feature.adoption_rate <= 100

    @pytest.mark.asyncio
    async def test_large_metadata(self, analytics_service):
        """Test handling large metadata objects."""
        large_metadata = {f"key_{i}": f"value_{i}" * 100 for i in range(100)}
        event = await analytics_service.track_event(
            customer_id="customer-1",
            user_id="user-1",
            metric_type=MetricType.API_REQUEST,
            event_name="/api/test",
            metadata=large_metadata,
        )
        assert len(event.metadata) == 100


# =============================================================================
# API Endpoint Tests (using TestClient would go here in integration tests)
# =============================================================================


class TestAPIEndpointModels:
    """Tests for API endpoint request/response models."""

    def test_track_event_request_validation(self):
        """Test TrackEventRequest validation."""
        from src.api.usage_analytics_endpoints import TrackEventRequest

        # Valid request
        request = TrackEventRequest(
            metric_type="api_request",
            event_name="test_event",
            success=True,
        )
        assert request.metric_type == "api_request"
        assert request.event_name == "test_event"

    def test_api_usage_response_fields(self):
        """Test APIUsageResponse has all required fields."""
        from src.api.usage_analytics_endpoints import APIUsageResponse

        response = APIUsageResponse(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            success_rate=0.95,
            average_latency_ms=150.5,
            by_endpoint={"/api/test": 50},
            by_day={"2025-12-20": 100},
            period_days=30,
        )
        assert response.total_requests == 100
        assert response.success_rate == 0.95

    def test_feature_adoption_response_fields(self):
        """Test FeatureAdoptionResponse has all required fields."""
        from src.api.usage_analytics_endpoints import FeatureAdoptionResponse

        response = FeatureAdoptionResponse(
            feature_name="dashboard",
            total_uses=500,
            unique_users=50,
            adoption_rate=75.5,
            avg_uses_per_user=10.0,
            trend="increasing",
        )
        assert response.feature_name == "dashboard"
        assert response.trend == "increasing"

    def test_user_engagement_response_fields(self):
        """Test UserEngagementResponse has all required fields."""
        from src.api.usage_analytics_endpoints import UserEngagementResponse

        response = UserEngagementResponse(
            user_id="user-1",
            total_events=100,
            features_used=["dashboard", "agents"],
            last_active="2025-12-20T10:00:00",
            engagement_score=85.5,
            sessions_count=10,
        )
        assert response.user_id == "user-1"
        assert response.engagement_score == 85.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
