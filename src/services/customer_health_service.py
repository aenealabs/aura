"""
Customer Success Health Score Service.

Calculates and tracks customer health scores for proactive success management:
- Engagement score (login frequency, feature usage)
- Adoption score (feature breadth, depth of usage)
- Satisfaction score (NPS, support tickets, feedback)
- Value realization score (ROI metrics, goal achievement)

Health scores help identify:
- Customers at risk of churn
- Expansion opportunities
- Onboarding issues
- Product fit problems
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Overall health status categories."""

    EXCELLENT = "excellent"  # 80-100
    HEALTHY = "healthy"  # 60-79
    AT_RISK = "at_risk"  # 40-59
    CRITICAL = "critical"  # 0-39


class ChurnRisk(str, Enum):
    """Churn risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExpansionPotential(str, Enum):
    """Expansion opportunity levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class HealthScoreComponent:
    """Individual component of health score."""

    name: str
    score: float  # 0-100
    weight: float  # 0-1
    weighted_score: float
    trend: str  # improving, declining, stable
    factors: List[Dict[str, Any]]


@dataclass
class CustomerHealthScore:
    """Complete customer health assessment."""

    customer_id: str
    overall_score: float  # 0-100
    status: HealthStatus
    churn_risk: ChurnRisk
    expansion_potential: ExpansionPotential
    components: Dict[str, HealthScoreComponent]
    recommendations: List[str]
    calculated_at: datetime
    next_review: datetime
    alerts: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class HealthTrend:
    """Historical health score trend."""

    customer_id: str
    scores: List[Dict[str, Any]]  # List of {date, score, status}
    period_start: datetime
    period_end: datetime
    trend_direction: str  # improving, declining, stable
    change_percent: float


# Health score component weights
COMPONENT_WEIGHTS = {
    "engagement": 0.25,
    "adoption": 0.25,
    "satisfaction": 0.20,
    "value_realization": 0.15,
    "support_health": 0.15,
}

# Thresholds for status categorization
STATUS_THRESHOLDS = {
    HealthStatus.EXCELLENT: 80,
    HealthStatus.HEALTHY: 60,
    HealthStatus.AT_RISK: 40,
    HealthStatus.CRITICAL: 0,
}

# Churn risk thresholds
CHURN_RISK_THRESHOLDS = {
    ChurnRisk.LOW: 70,
    ChurnRisk.MEDIUM: 50,
    ChurnRisk.HIGH: 30,
    ChurnRisk.CRITICAL: 0,
}


class CustomerHealthService:
    """
    Service for calculating and tracking customer health scores.

    Uses data from multiple sources:
    - Usage analytics (engagement, adoption)
    - Feedback service (NPS, satisfaction)
    - Ticketing service (support health)
    - Billing service (value realization)
    """

    def __init__(self, mode: str = "mock") -> None:
        """
        Initialize the customer health service.

        Args:
            mode: "mock" for testing, "aws" for production
        """
        self.mode = mode
        self._health_scores: Dict[str, CustomerHealthScore] = {}
        self._health_history: List[Dict[str, Any]] = []

    async def calculate_health_score(
        self,
        customer_id: str,
        days: int = 30,
    ) -> CustomerHealthScore:
        """
        Calculate comprehensive health score for a customer.

        Args:
            customer_id: Customer organization ID
            days: Number of days to analyze

        Returns:
            CustomerHealthScore with all components
        """
        # Calculate each component
        engagement = await self._calculate_engagement_score(customer_id, days)
        adoption = await self._calculate_adoption_score(customer_id, days)
        satisfaction = await self._calculate_satisfaction_score(customer_id, days)
        value_realization = await self._calculate_value_realization_score(
            customer_id, days
        )
        support_health = await self._calculate_support_health_score(customer_id, days)

        components = {
            "engagement": engagement,
            "adoption": adoption,
            "satisfaction": satisfaction,
            "value_realization": value_realization,
            "support_health": support_health,
        }

        # Calculate overall score
        overall_score = sum(
            component.weighted_score for component in components.values()
        )

        # Determine status
        status = self._get_health_status(overall_score)

        # Assess churn risk
        churn_risk = self._assess_churn_risk(overall_score, components)

        # Assess expansion potential
        expansion_potential = self._assess_expansion_potential(
            overall_score, components
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(components, status)

        # Identify alerts
        alerts = self._identify_alerts(components)

        health_score = CustomerHealthScore(
            customer_id=customer_id,
            overall_score=round(overall_score, 1),
            status=status,
            churn_risk=churn_risk,
            expansion_potential=expansion_potential,
            components=components,
            recommendations=recommendations,
            calculated_at=datetime.now(timezone.utc),
            next_review=datetime.now(timezone.utc) + timedelta(days=7),
            alerts=alerts,
        )

        # Store for history
        self._health_scores[customer_id] = health_score
        self._health_history.append(
            {
                "customer_id": customer_id,
                "score": overall_score,
                "status": status.value,
                "calculated_at": datetime.now(timezone.utc),
            }
        )

        logger.info(
            f"Health score calculated for {customer_id}: {overall_score} ({status.value})"
        )
        return health_score

    async def get_health_score(self, customer_id: str) -> Optional[CustomerHealthScore]:
        """Get the most recent health score for a customer."""
        return self._health_scores.get(customer_id)

    async def get_health_trend(
        self,
        customer_id: str,
        days: int = 90,
    ) -> HealthTrend:
        """
        Get health score trend over time.

        Args:
            customer_id: Customer organization ID
            days: Number of days to analyze

        Returns:
            HealthTrend with historical scores
        """
        period_start = datetime.now(timezone.utc) - timedelta(days=days)
        period_end = datetime.now(timezone.utc)

        # Get historical scores
        scores = [
            h
            for h in self._health_history
            if h["customer_id"] == customer_id and h["calculated_at"] >= period_start
        ]

        # Calculate trend
        if len(scores) >= 2:
            first_score = scores[0]["score"]
            last_score = scores[-1]["score"]
            change = last_score - first_score
            change_percent = (change / first_score * 100) if first_score > 0 else 0

            if change_percent > 5:
                trend_direction = "improving"
            elif change_percent < -5:
                trend_direction = "declining"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "stable"
            change_percent = 0

        return HealthTrend(
            customer_id=customer_id,
            scores=[
                {
                    "date": s["calculated_at"].isoformat(),
                    "score": s["score"],
                    "status": s["status"],
                }
                for s in scores
            ],
            period_start=period_start,
            period_end=period_end,
            trend_direction=trend_direction,
            change_percent=round(change_percent, 1),
        )

    async def list_at_risk_customers(
        self,
        limit: int = 20,
    ) -> List[CustomerHealthScore]:
        """
        List customers at risk of churn.

        Returns customers with AT_RISK or CRITICAL status,
        sorted by overall score ascending.
        """
        at_risk = [
            h
            for h in self._health_scores.values()
            if h.status in (HealthStatus.AT_RISK, HealthStatus.CRITICAL)
        ]
        return sorted(at_risk, key=lambda x: x.overall_score)[:limit]

    async def list_expansion_opportunities(
        self,
        limit: int = 20,
    ) -> List[CustomerHealthScore]:
        """
        List customers with expansion potential.

        Returns customers with HIGH expansion potential
        and HEALTHY or EXCELLENT status.
        """
        opportunities = [
            h
            for h in self._health_scores.values()
            if h.expansion_potential == ExpansionPotential.HIGH
            and h.status in (HealthStatus.HEALTHY, HealthStatus.EXCELLENT)
        ]
        return sorted(opportunities, key=lambda x: x.overall_score, reverse=True)[
            :limit
        ]

    # ==========================================================================
    # Score Component Calculations
    # ==========================================================================

    async def _calculate_engagement_score(
        self,
        customer_id: str,
        days: int,
    ) -> HealthScoreComponent:
        """
        Calculate engagement score based on:
        - Login frequency
        - Active users ratio
        - Session duration
        - Feature interaction rate
        """
        # In production, this would query UsageAnalyticsService
        # For mock mode, generate realistic scores

        # Mock data for testing
        login_frequency_score = 75.0
        active_users_score = 80.0
        session_duration_score = 70.0
        interaction_rate_score = 65.0

        raw_score = (
            login_frequency_score * 0.3
            + active_users_score * 0.3
            + session_duration_score * 0.2
            + interaction_rate_score * 0.2
        )

        weight = COMPONENT_WEIGHTS["engagement"]

        return HealthScoreComponent(
            name="engagement",
            score=round(raw_score, 1),
            weight=weight,
            weighted_score=round(raw_score * weight, 1),
            trend="stable",
            factors=[
                {
                    "name": "login_frequency",
                    "score": login_frequency_score,
                    "status": "good",
                },
                {
                    "name": "active_users_ratio",
                    "score": active_users_score,
                    "status": "good",
                },
                {
                    "name": "session_duration",
                    "score": session_duration_score,
                    "status": "fair",
                },
                {
                    "name": "interaction_rate",
                    "score": interaction_rate_score,
                    "status": "fair",
                },
            ],
        )

    async def _calculate_adoption_score(
        self,
        customer_id: str,
        days: int,
    ) -> HealthScoreComponent:
        """
        Calculate adoption score based on:
        - Feature breadth (% of features used)
        - Feature depth (repeat usage)
        - Advanced feature usage
        - Integration completeness
        """
        feature_breadth_score = 70.0
        feature_depth_score = 65.0
        advanced_features_score = 50.0
        integration_score = 80.0

        raw_score = (
            feature_breadth_score * 0.25
            + feature_depth_score * 0.25
            + advanced_features_score * 0.25
            + integration_score * 0.25
        )

        weight = COMPONENT_WEIGHTS["adoption"]

        return HealthScoreComponent(
            name="adoption",
            score=round(raw_score, 1),
            weight=weight,
            weighted_score=round(raw_score * weight, 1),
            trend="improving",
            factors=[
                {
                    "name": "feature_breadth",
                    "score": feature_breadth_score,
                    "status": "fair",
                },
                {
                    "name": "feature_depth",
                    "score": feature_depth_score,
                    "status": "fair",
                },
                {
                    "name": "advanced_features",
                    "score": advanced_features_score,
                    "status": "poor",
                },
                {"name": "integrations", "score": integration_score, "status": "good"},
            ],
        )

    async def _calculate_satisfaction_score(
        self,
        customer_id: str,
        days: int,
    ) -> HealthScoreComponent:
        """
        Calculate satisfaction score based on:
        - NPS score
        - Feedback sentiment
        - Feature request patterns
        - User survey responses
        """
        # In production, query FeedbackService for NPS
        nps_score = 75.0  # Scaled from -100 to 100 -> 0 to 100
        feedback_sentiment_score = 70.0
        feature_request_score = 60.0
        survey_score = 72.0

        raw_score = (
            nps_score * 0.4
            + feedback_sentiment_score * 0.25
            + feature_request_score * 0.15
            + survey_score * 0.20
        )

        weight = COMPONENT_WEIGHTS["satisfaction"]

        return HealthScoreComponent(
            name="satisfaction",
            score=round(raw_score, 1),
            weight=weight,
            weighted_score=round(raw_score * weight, 1),
            trend="stable",
            factors=[
                {"name": "nps_score", "score": nps_score, "status": "good"},
                {
                    "name": "feedback_sentiment",
                    "score": feedback_sentiment_score,
                    "status": "fair",
                },
                {
                    "name": "feature_requests",
                    "score": feature_request_score,
                    "status": "fair",
                },
                {"name": "survey_responses", "score": survey_score, "status": "good"},
            ],
        )

    async def _calculate_value_realization_score(
        self,
        customer_id: str,
        days: int,
    ) -> HealthScoreComponent:
        """
        Calculate value realization score based on:
        - ROI metrics (time saved, bugs fixed)
        - Goal achievement
        - Usage vs. plan limits
        - Business outcomes
        """
        roi_score = 80.0
        goal_achievement_score = 65.0
        plan_utilization_score = 70.0
        outcome_score = 75.0

        raw_score = (
            roi_score * 0.30
            + goal_achievement_score * 0.25
            + plan_utilization_score * 0.20
            + outcome_score * 0.25
        )

        weight = COMPONENT_WEIGHTS["value_realization"]

        return HealthScoreComponent(
            name="value_realization",
            score=round(raw_score, 1),
            weight=weight,
            weighted_score=round(raw_score * weight, 1),
            trend="improving",
            factors=[
                {"name": "roi_metrics", "score": roi_score, "status": "good"},
                {
                    "name": "goal_achievement",
                    "score": goal_achievement_score,
                    "status": "fair",
                },
                {
                    "name": "plan_utilization",
                    "score": plan_utilization_score,
                    "status": "fair",
                },
                {"name": "business_outcomes", "score": outcome_score, "status": "good"},
            ],
        )

    async def _calculate_support_health_score(
        self,
        customer_id: str,
        days: int,
    ) -> HealthScoreComponent:
        """
        Calculate support health score based on:
        - Ticket volume trend
        - Resolution time satisfaction
        - Escalation rate
        - Self-service success
        """
        ticket_volume_score = 85.0  # Lower is better, inverted
        resolution_score = 70.0
        escalation_score = 90.0  # Lower escalations = higher score
        self_service_score = 60.0

        raw_score = (
            ticket_volume_score * 0.25
            + resolution_score * 0.30
            + escalation_score * 0.25
            + self_service_score * 0.20
        )

        weight = COMPONENT_WEIGHTS["support_health"]

        return HealthScoreComponent(
            name="support_health",
            score=round(raw_score, 1),
            weight=weight,
            weighted_score=round(raw_score * weight, 1),
            trend="stable",
            factors=[
                {
                    "name": "ticket_volume",
                    "score": ticket_volume_score,
                    "status": "good",
                },
                {
                    "name": "resolution_time",
                    "score": resolution_score,
                    "status": "fair",
                },
                {
                    "name": "escalation_rate",
                    "score": escalation_score,
                    "status": "good",
                },
                {"name": "self_service", "score": self_service_score, "status": "fair"},
            ],
        )

    # ==========================================================================
    # Status and Risk Assessment
    # ==========================================================================

    def _get_health_status(self, score: float) -> HealthStatus:
        """Determine health status from score."""
        if score >= STATUS_THRESHOLDS[HealthStatus.EXCELLENT]:
            return HealthStatus.EXCELLENT
        elif score >= STATUS_THRESHOLDS[HealthStatus.HEALTHY]:
            return HealthStatus.HEALTHY
        elif score >= STATUS_THRESHOLDS[HealthStatus.AT_RISK]:
            return HealthStatus.AT_RISK
        else:
            return HealthStatus.CRITICAL

    def _assess_churn_risk(
        self,
        overall_score: float,
        components: Dict[str, HealthScoreComponent],
    ) -> ChurnRisk:
        """
        Assess churn risk based on score and component analysis.

        High-weight factors:
        - Declining engagement
        - Low satisfaction
        - High support escalations
        """
        # Base risk from overall score
        if overall_score >= CHURN_RISK_THRESHOLDS[ChurnRisk.LOW]:
            base_risk = ChurnRisk.LOW
        elif overall_score >= CHURN_RISK_THRESHOLDS[ChurnRisk.MEDIUM]:
            base_risk = ChurnRisk.MEDIUM
        elif overall_score >= CHURN_RISK_THRESHOLDS[ChurnRisk.HIGH]:
            base_risk = ChurnRisk.HIGH
        else:
            base_risk = ChurnRisk.CRITICAL

        # Adjust for critical factors
        engagement = components.get("engagement")
        satisfaction = components.get("satisfaction")

        if engagement and engagement.trend == "declining":
            # Increase risk level
            if base_risk == ChurnRisk.LOW:
                return ChurnRisk.MEDIUM
            elif base_risk == ChurnRisk.MEDIUM:
                return ChurnRisk.HIGH

        if satisfaction and satisfaction.score < 50:
            if base_risk == ChurnRisk.LOW:
                return ChurnRisk.MEDIUM
            elif base_risk == ChurnRisk.MEDIUM:
                return ChurnRisk.HIGH

        return base_risk

    def _assess_expansion_potential(
        self,
        overall_score: float,
        components: Dict[str, HealthScoreComponent],
    ) -> ExpansionPotential:
        """
        Assess expansion potential based on:
        - High value realization
        - Plan utilization near limits
        - Growing engagement
        """
        if overall_score < 60:
            return ExpansionPotential.NONE

        value_realization = components.get("value_realization")
        adoption = components.get("adoption")
        engagement = components.get("engagement")

        high_value = value_realization and value_realization.score >= 75
        high_adoption = adoption and adoption.score >= 70
        growing = engagement and engagement.trend == "improving"

        if high_value and high_adoption and growing:
            return ExpansionPotential.HIGH
        elif high_value or (high_adoption and growing):
            return ExpansionPotential.MEDIUM
        elif overall_score >= 70:
            return ExpansionPotential.LOW
        else:
            return ExpansionPotential.NONE

    # ==========================================================================
    # Recommendations and Alerts
    # ==========================================================================

    def _generate_recommendations(
        self,
        components: Dict[str, HealthScoreComponent],
        status: HealthStatus,
    ) -> List[str]:
        """Generate actionable recommendations based on health analysis."""
        recommendations = []

        # Check each component for improvement opportunities
        for name, component in components.items():
            if component.score < 50:
                if name == "engagement":
                    recommendations.append(
                        "Schedule a business review to understand engagement barriers"
                    )
                elif name == "adoption":
                    recommendations.append(
                        "Offer training session on advanced features"
                    )
                elif name == "satisfaction":
                    recommendations.append(
                        "Conduct customer interview to understand satisfaction issues"
                    )
                elif name == "value_realization":
                    recommendations.append(
                        "Review success metrics and adjust goals with customer"
                    )
                elif name == "support_health":
                    recommendations.append(
                        "Analyze support tickets for common issues and provide proactive guidance"
                    )

            # Component-specific recommendations
            for factor in component.factors:
                if factor["status"] == "poor":
                    if factor["name"] == "advanced_features":
                        recommendations.append(
                            "Demonstrate advanced features in next check-in"
                        )
                    elif factor["name"] == "self_service":
                        recommendations.append(
                            "Share documentation and self-service resources"
                        )

        # Status-based recommendations
        if status == HealthStatus.CRITICAL:
            recommendations.insert(
                0, "Immediate executive sponsor outreach recommended"
            )
        elif status == HealthStatus.AT_RISK:
            recommendations.insert(0, "Schedule urgent health check meeting")

        return recommendations[:5]  # Limit to top 5

    def _identify_alerts(
        self,
        components: Dict[str, HealthScoreComponent],
    ) -> List[Dict[str, Any]]:
        """Identify critical alerts requiring immediate attention."""
        alerts = []

        for name, component in components.items():
            # Declining trend alert
            if component.trend == "declining":
                alerts.append(
                    {
                        "type": "declining_metric",
                        "severity": "warning",
                        "component": name,
                        "message": f"{name.replace('_', ' ').title()} score is declining",
                    }
                )

            # Critical score alert
            if component.score < 40:
                alerts.append(
                    {
                        "type": "critical_score",
                        "severity": "critical",
                        "component": name,
                        "message": f"{name.replace('_', ' ').title()} score is critically low ({component.score})",
                    }
                )

            # Check individual factors
            for factor in component.factors:
                if factor["status"] == "poor" and factor["score"] < 30:
                    alerts.append(
                        {
                            "type": "critical_factor",
                            "severity": "warning",
                            "component": name,
                            "factor": factor["name"],
                            "message": f"Low {factor['name'].replace('_', ' ')} score",
                        }
                    )

        return alerts


# =============================================================================
# Singleton Instance
# =============================================================================

_service: Optional[CustomerHealthService] = None


def get_customer_health_service(mode: Optional[str] = None) -> CustomerHealthService:
    """Get the singleton customer health service instance."""
    global _service
    if _service is None:
        resolved_mode = mode or os.getenv("HEALTH_SERVICE_MODE", "mock")
        _service = CustomerHealthService(mode=resolved_mode or "mock")
    return _service
