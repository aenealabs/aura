"""
Usage Analytics Service.

Tracks and aggregates platform usage metrics for:
- API usage patterns
- Feature adoption rates
- Agent execution statistics
- User engagement metrics
- Cost attribution

Supports both real-time dashboards and historical analysis.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of usage metrics tracked."""

    API_REQUEST = "api_request"
    FEATURE_USAGE = "feature_usage"
    AGENT_EXECUTION = "agent_execution"
    LOGIN = "login"
    PAGE_VIEW = "page_view"
    SEARCH = "search"
    EXPORT = "export"
    ERROR = "error"


class TimeGranularity(str, Enum):
    """Time granularity for aggregations."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class UsageEvent:
    """A single usage event."""

    event_id: str
    customer_id: str
    user_id: str
    metric_type: MetricType
    event_name: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[int] = None
    status: str = "success"
    error_message: Optional[str] = None


@dataclass
class UsageMetric:
    """Aggregated usage metric."""

    metric_name: str
    value: float
    unit: str
    change_percent: Optional[float] = None
    trend: str = "stable"  # up, down, stable


@dataclass
class FeatureAdoption:
    """Feature adoption statistics."""

    feature_name: str
    total_users: int
    active_users: int
    adoption_rate: float
    usage_count: int
    avg_daily_usage: float
    trend: str = "stable"


@dataclass
class UserEngagement:
    """User engagement metrics."""

    total_users: int
    active_users_daily: int
    active_users_weekly: int
    active_users_monthly: int
    avg_session_duration_minutes: float
    avg_actions_per_session: float
    retention_rate_7d: float
    retention_rate_30d: float


@dataclass
class UsageSummary:
    """Complete usage analytics summary."""

    period_start: datetime
    period_end: datetime
    total_api_calls: int
    total_agent_executions: int
    total_active_users: int
    key_metrics: List[UsageMetric]
    feature_adoption: List[FeatureAdoption]
    engagement: UserEngagement
    top_features: List[str]
    top_errors: List[Dict[str, Any]]


class UsageAnalyticsService:
    """
    Service for tracking and analyzing platform usage.

    In production, uses CloudWatch metrics and DynamoDB for storage.
    In test mode, uses in-memory storage.
    """

    def __init__(self, mode: str = "mock") -> None:
        """
        Initialize the usage analytics service.

        Args:
            mode: "mock" for testing, "aws" for production
        """
        self.mode = mode
        self._events: List[UsageEvent] = []
        self._metrics_cache: Dict[str, Any] = {}

        if mode == "aws":
            import boto3

            self._cloudwatch = boto3.client("cloudwatch")
            self._dynamodb = boto3.resource("dynamodb")

    async def track_event(
        self,
        customer_id: str,
        user_id: str,
        metric_type: MetricType,
        event_name: str,
        metadata: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> UsageEvent:
        """
        Track a usage event.

        Args:
            customer_id: Customer organization ID
            user_id: User who triggered the event
            metric_type: Type of metric
            event_name: Specific event name (e.g., "vulnerability_scan")
            metadata: Additional context
            duration_ms: Duration in milliseconds (for timed events)
            status: success, failure, error
            error_message: Error details if status is error

        Returns:
            Created UsageEvent
        """
        import uuid

        event = UsageEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            customer_id=customer_id,
            user_id=user_id,
            metric_type=metric_type,
            event_name=event_name,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
        )

        if self.mode == "mock":
            self._events.append(event)
        else:
            await self._publish_to_cloudwatch(event)
            await self._store_event(event)

        return event

    async def get_api_usage(
        self,
        customer_id: Optional[str] = None,
        days: int = 30,
        granularity: TimeGranularity = TimeGranularity.DAILY,
    ) -> Dict[str, Any]:
        """
        Get API usage statistics.

        Args:
            customer_id: Optional customer filter
            days: Number of days to analyze
            granularity: Time granularity for breakdown

        Returns:
            API usage statistics with time series data
        """
        period_start = datetime.now(timezone.utc) - timedelta(days=days)

        if self.mode == "mock":
            events = [
                e
                for e in self._events
                if e.metric_type == MetricType.API_REQUEST
                and e.timestamp >= period_start
                and (customer_id is None or e.customer_id == customer_id)
            ]
        else:
            events = await self._query_events(
                metric_type=MetricType.API_REQUEST,
                customer_id=customer_id,
                start_time=period_start,
            )

        # Aggregate by endpoint
        by_endpoint: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        latencies: List[int] = []

        for event in events:
            endpoint = event.metadata.get("endpoint", "unknown")
            by_endpoint[endpoint] = by_endpoint.get(endpoint, 0) + 1
            by_status[event.status] = by_status.get(event.status, 0) + 1
            if event.duration_ms:
                latencies.append(event.duration_ms)

        # Calculate percentiles
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        sorted_latencies = sorted(latencies)
        p50 = sorted_latencies[len(sorted_latencies) // 2] if sorted_latencies else 0
        p95 = (
            sorted_latencies[int(len(sorted_latencies) * 0.95)]
            if len(sorted_latencies) > 20
            else p50
        )
        p99 = (
            sorted_latencies[int(len(sorted_latencies) * 0.99)]
            if len(sorted_latencies) > 100
            else p95
        )

        return {
            "total_requests": len(events),
            "success_rate": (
                by_status.get("success", 0) / len(events) * 100 if events else 0
            ),
            "by_endpoint": dict(
                sorted(by_endpoint.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "by_status": by_status,
            "latency": {
                "avg_ms": round(avg_latency, 1),
                "p50_ms": p50,
                "p95_ms": p95,
                "p99_ms": p99,
            },
            "period_days": days,
        }

    async def get_feature_adoption(
        self,
        customer_id: Optional[str] = None,
        days: int = 30,
    ) -> List[FeatureAdoption]:
        """
        Get feature adoption statistics.

        Args:
            customer_id: Optional customer filter
            days: Number of days to analyze

        Returns:
            List of feature adoption statistics
        """
        period_start = datetime.now(timezone.utc) - timedelta(days=days)

        if self.mode == "mock":
            events = [
                e
                for e in self._events
                if e.metric_type == MetricType.FEATURE_USAGE
                and e.timestamp >= period_start
                and (customer_id is None or e.customer_id == customer_id)
            ]
        else:
            events = await self._query_events(
                metric_type=MetricType.FEATURE_USAGE,
                customer_id=customer_id,
                start_time=period_start,
            )

        # Aggregate by feature
        feature_data: Dict[str, Dict[str, Any]] = {}

        for event in events:
            feature = event.event_name
            if feature not in feature_data:
                feature_data[feature] = {"users": set(), "count": 0}
            feature_data[feature]["users"].add(event.user_id)
            feature_data[feature]["count"] += 1

        # Get total unique users
        all_users = set()
        for data in feature_data.values():
            all_users.update(data["users"])
        total_users = len(all_users) or 1

        # Build adoption list
        adoptions = []
        for feature, data in feature_data.items():
            active_users = len(data["users"])
            adoptions.append(
                FeatureAdoption(
                    feature_name=feature,
                    total_users=total_users,
                    active_users=active_users,
                    adoption_rate=round(active_users / total_users * 100, 1),
                    usage_count=data["count"],
                    avg_daily_usage=round(data["count"] / days, 1),
                    trend="stable",
                )
            )

        return sorted(adoptions, key=lambda x: x.adoption_rate, reverse=True)

    async def get_agent_statistics(
        self,
        customer_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get agent execution statistics.

        Args:
            customer_id: Optional customer filter
            days: Number of days to analyze

        Returns:
            Agent execution statistics
        """
        period_start = datetime.now(timezone.utc) - timedelta(days=days)

        if self.mode == "mock":
            events = [
                e
                for e in self._events
                if e.metric_type == MetricType.AGENT_EXECUTION
                and e.timestamp >= period_start
                and (customer_id is None or e.customer_id == customer_id)
            ]
        else:
            events = await self._query_events(
                metric_type=MetricType.AGENT_EXECUTION,
                customer_id=customer_id,
                start_time=period_start,
            )

        # Aggregate by agent type
        by_agent: Dict[str, Dict[str, Any]] = {}
        durations: List[int] = []

        for event in events:
            agent = event.metadata.get("agent_type", "unknown")
            if agent not in by_agent:
                by_agent[agent] = {"total": 0, "success": 0, "durations": []}

            by_agent[agent]["total"] += 1
            if event.status == "success":
                by_agent[agent]["success"] += 1
            if event.duration_ms:
                by_agent[agent]["durations"].append(event.duration_ms)
                durations.append(event.duration_ms)

        # Calculate metrics per agent
        agent_stats = {}
        for agent, data in by_agent.items():
            avg_duration = (
                sum(data["durations"]) / len(data["durations"])
                if data["durations"]
                else 0
            )
            agent_stats[agent] = {
                "total_executions": data["total"],
                "success_rate": (
                    round(data["success"] / data["total"] * 100, 1)
                    if data["total"]
                    else 0
                ),
                "avg_duration_ms": round(avg_duration, 1),
            }

        return {
            "total_executions": len(events),
            "total_success": sum(1 for e in events if e.status == "success"),
            "success_rate": (
                round(
                    sum(1 for e in events if e.status == "success") / len(events) * 100,
                    1,
                )
                if events
                else 0
            ),
            "avg_duration_ms": (
                round(sum(durations) / len(durations), 1) if durations else 0
            ),
            "by_agent": agent_stats,
            "period_days": days,
        }

    async def get_user_engagement(
        self,
        customer_id: Optional[str] = None,
        days: int = 30,
    ) -> UserEngagement:
        """
        Get user engagement metrics.

        Args:
            customer_id: Optional customer filter
            days: Number of days to analyze

        Returns:
            User engagement statistics
        """
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=days)

        if self.mode == "mock":
            events = [
                e
                for e in self._events
                if e.timestamp >= period_start
                and (customer_id is None or e.customer_id == customer_id)
            ]
        else:
            events = await self._query_events(
                customer_id=customer_id,
                start_time=period_start,
            )

        # Calculate active users by period
        daily_users = set()
        weekly_users = set()
        monthly_users = set()
        all_users = set()

        for event in events:
            all_users.add(event.user_id)
            if event.timestamp >= now - timedelta(days=1):
                daily_users.add(event.user_id)
            if event.timestamp >= now - timedelta(days=7):
                weekly_users.add(event.user_id)
            monthly_users.add(event.user_id)

        # Calculate session metrics (simplified)
        user_actions: Dict[str, int] = {}
        for event in events:
            user_actions[event.user_id] = user_actions.get(event.user_id, 0) + 1

        avg_actions = (
            sum(user_actions.values()) / len(user_actions) if user_actions else 0
        )

        # Simplified retention calculation
        first_week_users = set()
        for event in events:
            if event.timestamp <= period_start + timedelta(days=7):
                first_week_users.add(event.user_id)

        retained_7d = (
            len(weekly_users & first_week_users) / len(first_week_users) * 100
            if first_week_users
            else 0
        )

        return UserEngagement(
            total_users=len(all_users),
            active_users_daily=len(daily_users),
            active_users_weekly=len(weekly_users),
            active_users_monthly=len(monthly_users),
            avg_session_duration_minutes=15.0,  # Placeholder
            avg_actions_per_session=round(avg_actions / 3, 1) if avg_actions else 0,
            retention_rate_7d=round(retained_7d, 1),
            retention_rate_30d=(
                round(len(monthly_users) / len(all_users) * 100, 1) if all_users else 0
            ),
        )

    async def get_usage_summary(
        self,
        customer_id: Optional[str] = None,
        days: int = 30,
    ) -> UsageSummary:
        """
        Get comprehensive usage summary.

        Args:
            customer_id: Optional customer filter
            days: Number of days to analyze

        Returns:
            Complete usage summary
        """
        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(days=days)

        # Gather all metrics
        api_usage = await self.get_api_usage(customer_id, days)
        agent_stats = await self.get_agent_statistics(customer_id, days)
        feature_adoption = await self.get_feature_adoption(customer_id, days)
        engagement = await self.get_user_engagement(customer_id, days)

        # Build key metrics
        key_metrics = [
            UsageMetric(
                metric_name="API Requests",
                value=api_usage["total_requests"],
                unit="requests",
                trend="stable",
            ),
            UsageMetric(
                metric_name="Agent Executions",
                value=agent_stats["total_executions"],
                unit="executions",
                trend="stable",
            ),
            UsageMetric(
                metric_name="API Success Rate",
                value=api_usage["success_rate"],
                unit="%",
                trend="stable",
            ),
            UsageMetric(
                metric_name="Agent Success Rate",
                value=agent_stats["success_rate"],
                unit="%",
                trend="stable",
            ),
            UsageMetric(
                metric_name="Avg API Latency",
                value=api_usage["latency"]["avg_ms"],
                unit="ms",
                trend="stable",
            ),
        ]

        # Get top features
        top_features = [f.feature_name for f in feature_adoption[:5]]

        # Get top errors (simplified)
        top_errors: List[Dict[str, Any]] = []

        return UsageSummary(
            period_start=period_start,
            period_end=period_end,
            total_api_calls=api_usage["total_requests"],
            total_agent_executions=agent_stats["total_executions"],
            total_active_users=engagement.active_users_monthly,
            key_metrics=key_metrics,
            feature_adoption=feature_adoption,
            engagement=engagement,
            top_features=top_features,
            top_errors=top_errors,
        )

    async def _publish_to_cloudwatch(self, event: UsageEvent) -> None:
        """Publish metric to CloudWatch."""
        try:
            namespace = f"Aura/Usage/{os.getenv('ENVIRONMENT', 'dev')}"

            dimensions = [
                {"Name": "CustomerId", "Value": event.customer_id},
                {"Name": "MetricType", "Value": event.metric_type.value},
            ]

            self._cloudwatch.put_metric_data(
                Namespace=namespace,
                MetricData=[
                    {
                        "MetricName": event.event_name,
                        "Dimensions": dimensions,
                        "Timestamp": event.timestamp,
                        "Value": 1,
                        "Unit": "Count",
                    }
                ],
            )

            if event.duration_ms:
                self._cloudwatch.put_metric_data(
                    Namespace=namespace,
                    MetricData=[
                        {
                            "MetricName": f"{event.event_name}_duration",
                            "Dimensions": dimensions,
                            "Timestamp": event.timestamp,
                            "Value": event.duration_ms,
                            "Unit": "Milliseconds",
                        }
                    ],
                )

        except Exception as e:
            logger.error(f"Error publishing to CloudWatch: {e}")

    async def _store_event(self, event: UsageEvent) -> None:
        """Store event to DynamoDB for historical analysis."""
        # Implementation would use DynamoDB

    async def _query_events(
        self,
        metric_type: Optional[MetricType] = None,
        customer_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
    ) -> List[UsageEvent]:
        """Query events from DynamoDB."""
        # Implementation would query DynamoDB
        return []


# =============================================================================
# Singleton Instance
# =============================================================================

_service: Optional[UsageAnalyticsService] = None


def get_usage_analytics_service(mode: Optional[str] = None) -> UsageAnalyticsService:
    """Get the singleton usage analytics service instance."""
    global _service
    if _service is None:
        resolved_mode = mode or os.getenv("USAGE_ANALYTICS_MODE", "mock")
        _service = UsageAnalyticsService(mode=resolved_mode or "mock")
    return _service
