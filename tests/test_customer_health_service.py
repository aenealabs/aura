"""
Tests for Customer Health Score Service.

Validates customer health score calculation and tracking:
- Engagement score calculation
- Adoption score calculation
- Satisfaction score calculation
- Value realization score calculation
- Support health score calculation
- Churn risk assessment
- Expansion potential assessment
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.services.customer_health_service import (
    CHURN_RISK_THRESHOLDS,
    COMPONENT_WEIGHTS,
    STATUS_THRESHOLDS,
    ChurnRisk,
    CustomerHealthScore,
    CustomerHealthService,
    ExpansionPotential,
    HealthScoreComponent,
    HealthStatus,
    get_customer_health_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def health_service():
    """Create a fresh customer health service for each test."""
    return CustomerHealthService(mode="mock")


@pytest.fixture
def customer_id():
    """Sample customer ID."""
    return f"cust_{uuid.uuid4().hex[:12]}"


@pytest.fixture
async def customer_with_health_score(health_service, customer_id):
    """Create a customer with a calculated health score."""
    score = await health_service.calculate_health_score(customer_id)
    return customer_id, score


# =============================================================================
# Health Score Calculation Tests
# =============================================================================


class TestHealthScoreCalculation:
    """Tests for health score calculation."""

    @pytest.mark.asyncio
    async def test_calculate_health_score(self, health_service, customer_id):
        """Test basic health score calculation."""
        score = await health_service.calculate_health_score(customer_id)

        assert score is not None
        assert score.customer_id == customer_id
        assert 0 <= score.overall_score <= 100
        assert isinstance(score.status, HealthStatus)
        assert isinstance(score.churn_risk, ChurnRisk)
        assert isinstance(score.expansion_potential, ExpansionPotential)
        assert score.calculated_at is not None
        assert score.next_review is not None

    @pytest.mark.asyncio
    async def test_health_score_has_all_components(self, health_service, customer_id):
        """Test that health score includes all expected components."""
        score = await health_service.calculate_health_score(customer_id)

        expected_components = [
            "engagement",
            "adoption",
            "satisfaction",
            "value_realization",
            "support_health",
        ]

        for component_name in expected_components:
            assert component_name in score.components
            component = score.components[component_name]
            assert isinstance(component, HealthScoreComponent)
            assert component.name == component_name
            assert 0 <= component.score <= 100
            assert 0 <= component.weight <= 1
            assert component.trend in ["improving", "declining", "stable"]

    @pytest.mark.asyncio
    async def test_health_score_weights_sum_to_one(self, health_service, customer_id):
        """Test that component weights sum to 1.0."""
        total_weight = sum(COMPONENT_WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_health_score_weighted_calculation(self, health_service, customer_id):
        """Test that overall score is correctly weighted."""
        score = await health_service.calculate_health_score(customer_id)

        # Recalculate expected overall score
        expected = sum(c.weighted_score for c in score.components.values())

        assert abs(score.overall_score - expected) < 0.1

    @pytest.mark.asyncio
    async def test_health_score_recommendations(self, health_service, customer_id):
        """Test that recommendations are generated."""
        score = await health_service.calculate_health_score(customer_id)

        assert isinstance(score.recommendations, list)
        # Should have at least some recommendations based on mock data

    @pytest.mark.asyncio
    async def test_health_score_alerts(self, health_service, customer_id):
        """Test that alerts are generated."""
        score = await health_service.calculate_health_score(customer_id)

        assert isinstance(score.alerts, list)
        # Each alert should have required fields
        for alert in score.alerts:
            assert "type" in alert
            assert "severity" in alert
            assert "message" in alert

    @pytest.mark.asyncio
    async def test_calculate_with_custom_days(self, health_service, customer_id):
        """Test health score calculation with custom analysis period."""
        score = await health_service.calculate_health_score(customer_id, days=60)

        assert score is not None
        assert score.customer_id == customer_id


# =============================================================================
# Health Status Tests
# =============================================================================


class TestHealthStatus:
    """Tests for health status determination."""

    def test_excellent_status(self, health_service):
        """Test EXCELLENT status for high scores."""
        status = health_service._get_health_status(85.0)
        assert status == HealthStatus.EXCELLENT

    def test_healthy_status(self, health_service):
        """Test HEALTHY status for moderate-high scores."""
        status = health_service._get_health_status(70.0)
        assert status == HealthStatus.HEALTHY

    def test_at_risk_status(self, health_service):
        """Test AT_RISK status for moderate-low scores."""
        status = health_service._get_health_status(50.0)
        assert status == HealthStatus.AT_RISK

    def test_critical_status(self, health_service):
        """Test CRITICAL status for low scores."""
        status = health_service._get_health_status(30.0)
        assert status == HealthStatus.CRITICAL

    def test_status_boundary_excellent(self, health_service):
        """Test boundary at EXCELLENT threshold."""
        status = health_service._get_health_status(80.0)
        assert status == HealthStatus.EXCELLENT

    def test_status_boundary_healthy(self, health_service):
        """Test boundary at HEALTHY threshold."""
        status = health_service._get_health_status(60.0)
        assert status == HealthStatus.HEALTHY

    def test_status_boundary_at_risk(self, health_service):
        """Test boundary at AT_RISK threshold."""
        status = health_service._get_health_status(40.0)
        assert status == HealthStatus.AT_RISK

    def test_status_zero_score(self, health_service):
        """Test status for zero score."""
        status = health_service._get_health_status(0.0)
        assert status == HealthStatus.CRITICAL


# =============================================================================
# Churn Risk Assessment Tests
# =============================================================================


class TestChurnRiskAssessment:
    """Tests for churn risk assessment."""

    def test_low_churn_risk_high_score(self, health_service):
        """Test LOW churn risk for high-scoring customer."""
        components = {
            "engagement": HealthScoreComponent(
                name="engagement",
                score=80.0,
                weight=0.25,
                weighted_score=20.0,
                trend="stable",
                factors=[],
            ),
            "satisfaction": HealthScoreComponent(
                name="satisfaction",
                score=80.0,
                weight=0.20,
                weighted_score=16.0,
                trend="stable",
                factors=[],
            ),
        }

        risk = health_service._assess_churn_risk(80.0, components)
        assert risk == ChurnRisk.LOW

    def test_medium_churn_risk(self, health_service):
        """Test MEDIUM churn risk for moderate score."""
        components = {}
        risk = health_service._assess_churn_risk(60.0, components)
        assert risk == ChurnRisk.MEDIUM

    def test_high_churn_risk(self, health_service):
        """Test HIGH churn risk for low score."""
        components = {}
        risk = health_service._assess_churn_risk(40.0, components)
        assert risk == ChurnRisk.HIGH

    def test_critical_churn_risk(self, health_service):
        """Test CRITICAL churn risk for very low score."""
        components = {}
        risk = health_service._assess_churn_risk(20.0, components)
        assert risk == ChurnRisk.CRITICAL

    def test_declining_engagement_increases_risk(self, health_service):
        """Test that declining engagement increases churn risk."""
        components = {
            "engagement": HealthScoreComponent(
                name="engagement",
                score=75.0,
                weight=0.25,
                weighted_score=18.75,
                trend="declining",  # Declining trend
                factors=[],
            ),
        }

        risk = health_service._assess_churn_risk(75.0, components)
        # Should be elevated from LOW to MEDIUM due to declining engagement
        assert risk == ChurnRisk.MEDIUM

    def test_low_satisfaction_increases_risk(self, health_service):
        """Test that low satisfaction increases churn risk."""
        components = {
            "satisfaction": HealthScoreComponent(
                name="satisfaction",
                score=45.0,  # Below 50 threshold
                weight=0.20,
                weighted_score=9.0,
                trend="stable",
                factors=[],
            ),
        }

        risk = health_service._assess_churn_risk(75.0, components)
        # Should be elevated from LOW to MEDIUM due to low satisfaction
        assert risk == ChurnRisk.MEDIUM


# =============================================================================
# Expansion Potential Tests
# =============================================================================


class TestExpansionPotential:
    """Tests for expansion potential assessment."""

    def test_high_expansion_potential(self, health_service):
        """Test HIGH expansion potential for ideal conditions."""
        components = {
            "value_realization": HealthScoreComponent(
                name="value_realization",
                score=80.0,
                weight=0.15,
                weighted_score=12.0,
                trend="stable",
                factors=[],
            ),
            "adoption": HealthScoreComponent(
                name="adoption",
                score=75.0,
                weight=0.25,
                weighted_score=18.75,
                trend="stable",
                factors=[],
            ),
            "engagement": HealthScoreComponent(
                name="engagement",
                score=80.0,
                weight=0.25,
                weighted_score=20.0,
                trend="improving",
                factors=[],
            ),
        }

        potential = health_service._assess_expansion_potential(80.0, components)
        assert potential == ExpansionPotential.HIGH

    def test_medium_expansion_potential(self, health_service):
        """Test MEDIUM expansion potential."""
        components = {
            "value_realization": HealthScoreComponent(
                name="value_realization",
                score=80.0,
                weight=0.15,
                weighted_score=12.0,
                trend="stable",
                factors=[],
            ),
            "adoption": HealthScoreComponent(
                name="adoption",
                score=60.0,
                weight=0.25,
                weighted_score=15.0,
                trend="stable",
                factors=[],
            ),
            "engagement": HealthScoreComponent(
                name="engagement",
                score=70.0,
                weight=0.25,
                weighted_score=17.5,
                trend="stable",
                factors=[],
            ),
        }

        potential = health_service._assess_expansion_potential(75.0, components)
        assert potential == ExpansionPotential.MEDIUM

    def test_low_expansion_potential(self, health_service):
        """Test LOW expansion potential."""
        components = {
            "value_realization": HealthScoreComponent(
                name="value_realization",
                score=60.0,
                weight=0.15,
                weighted_score=9.0,
                trend="stable",
                factors=[],
            ),
            "adoption": HealthScoreComponent(
                name="adoption",
                score=60.0,
                weight=0.25,
                weighted_score=15.0,
                trend="stable",
                factors=[],
            ),
            "engagement": HealthScoreComponent(
                name="engagement",
                score=70.0,
                weight=0.25,
                weighted_score=17.5,
                trend="stable",
                factors=[],
            ),
        }

        potential = health_service._assess_expansion_potential(70.0, components)
        assert potential == ExpansionPotential.LOW

    def test_no_expansion_potential_low_score(self, health_service):
        """Test NONE expansion potential for low-scoring customer."""
        components = {}
        potential = health_service._assess_expansion_potential(50.0, components)
        assert potential == ExpansionPotential.NONE


# =============================================================================
# Component Score Tests
# =============================================================================


class TestComponentScores:
    """Tests for individual component score calculations."""

    @pytest.mark.asyncio
    async def test_engagement_score_calculation(self, health_service, customer_id):
        """Test engagement score component calculation."""
        component = await health_service._calculate_engagement_score(customer_id, 30)

        assert component.name == "engagement"
        assert 0 <= component.score <= 100
        assert component.weight == COMPONENT_WEIGHTS["engagement"]
        assert len(component.factors) == 4

        factor_names = {f["name"] for f in component.factors}
        assert "login_frequency" in factor_names
        assert "active_users_ratio" in factor_names
        assert "session_duration" in factor_names
        assert "interaction_rate" in factor_names

    @pytest.mark.asyncio
    async def test_adoption_score_calculation(self, health_service, customer_id):
        """Test adoption score component calculation."""
        component = await health_service._calculate_adoption_score(customer_id, 30)

        assert component.name == "adoption"
        assert 0 <= component.score <= 100
        assert len(component.factors) == 4

        factor_names = {f["name"] for f in component.factors}
        assert "feature_breadth" in factor_names
        assert "feature_depth" in factor_names
        assert "advanced_features" in factor_names
        assert "integrations" in factor_names

    @pytest.mark.asyncio
    async def test_satisfaction_score_calculation(self, health_service, customer_id):
        """Test satisfaction score component calculation."""
        component = await health_service._calculate_satisfaction_score(customer_id, 30)

        assert component.name == "satisfaction"
        assert 0 <= component.score <= 100
        assert len(component.factors) == 4

        factor_names = {f["name"] for f in component.factors}
        assert "nps_score" in factor_names
        assert "feedback_sentiment" in factor_names
        assert "feature_requests" in factor_names
        assert "survey_responses" in factor_names

    @pytest.mark.asyncio
    async def test_value_realization_score_calculation(
        self, health_service, customer_id
    ):
        """Test value realization score component calculation."""
        component = await health_service._calculate_value_realization_score(
            customer_id, 30
        )

        assert component.name == "value_realization"
        assert 0 <= component.score <= 100
        assert len(component.factors) == 4

        factor_names = {f["name"] for f in component.factors}
        assert "roi_metrics" in factor_names
        assert "goal_achievement" in factor_names
        assert "plan_utilization" in factor_names
        assert "business_outcomes" in factor_names

    @pytest.mark.asyncio
    async def test_support_health_score_calculation(self, health_service, customer_id):
        """Test support health score component calculation."""
        component = await health_service._calculate_support_health_score(
            customer_id, 30
        )

        assert component.name == "support_health"
        assert 0 <= component.score <= 100
        assert len(component.factors) == 4

        factor_names = {f["name"] for f in component.factors}
        assert "ticket_volume" in factor_names
        assert "resolution_time" in factor_names
        assert "escalation_rate" in factor_names
        assert "self_service" in factor_names


# =============================================================================
# Recommendations Tests
# =============================================================================


class TestRecommendations:
    """Tests for recommendation generation."""

    def test_recommendations_for_low_engagement(self, health_service):
        """Test recommendations for low engagement score."""
        components = {
            "engagement": HealthScoreComponent(
                name="engagement",
                score=40.0,  # Below 50 threshold
                weight=0.25,
                weighted_score=10.0,
                trend="stable",
                factors=[],
            ),
        }

        recommendations = health_service._generate_recommendations(
            components, HealthStatus.AT_RISK
        )

        assert any(
            "engagement" in r.lower() or "review" in r.lower() for r in recommendations
        )

    def test_recommendations_for_low_adoption(self, health_service):
        """Test recommendations for low adoption score."""
        components = {
            "adoption": HealthScoreComponent(
                name="adoption",
                score=40.0,
                weight=0.25,
                weighted_score=10.0,
                trend="stable",
                factors=[],
            ),
        }

        recommendations = health_service._generate_recommendations(
            components, HealthStatus.AT_RISK
        )

        assert any(
            "training" in r.lower() or "feature" in r.lower() for r in recommendations
        )

    def test_recommendations_for_low_satisfaction(self, health_service):
        """Test recommendations for low satisfaction score."""
        components = {
            "satisfaction": HealthScoreComponent(
                name="satisfaction",
                score=40.0,
                weight=0.20,
                weighted_score=8.0,
                trend="stable",
                factors=[],
            ),
        }

        recommendations = health_service._generate_recommendations(
            components, HealthStatus.AT_RISK
        )

        assert any(
            "interview" in r.lower() or "satisfaction" in r.lower()
            for r in recommendations
        )

    def test_recommendations_for_critical_status(self, health_service):
        """Test that critical status gets urgent recommendations."""
        components = {}

        recommendations = health_service._generate_recommendations(
            components, HealthStatus.CRITICAL
        )

        assert any(
            "executive" in r.lower() or "immediate" in r.lower()
            for r in recommendations
        )

    def test_recommendations_for_poor_factors(self, health_service):
        """Test recommendations for poor individual factors."""
        components = {
            "adoption": HealthScoreComponent(
                name="adoption",
                score=60.0,
                weight=0.25,
                weighted_score=15.0,
                trend="stable",
                factors=[
                    {"name": "advanced_features", "score": 25.0, "status": "poor"},
                ],
            ),
        }

        recommendations = health_service._generate_recommendations(
            components, HealthStatus.HEALTHY
        )

        assert any(
            "advanced" in r.lower() or "feature" in r.lower() for r in recommendations
        )

    def test_recommendations_limited_to_five(self, health_service):
        """Test that recommendations are limited to 5."""
        components = {
            "engagement": HealthScoreComponent(
                name="engagement",
                score=30.0,
                weight=0.25,
                weighted_score=7.5,
                trend="stable",
                factors=[
                    {"name": "factor1", "score": 20.0, "status": "poor"},
                    {"name": "factor2", "score": 20.0, "status": "poor"},
                ],
            ),
            "adoption": HealthScoreComponent(
                name="adoption",
                score=30.0,
                weight=0.25,
                weighted_score=7.5,
                trend="stable",
                factors=[
                    {"name": "advanced_features", "score": 20.0, "status": "poor"},
                    {"name": "self_service", "score": 20.0, "status": "poor"},
                ],
            ),
            "satisfaction": HealthScoreComponent(
                name="satisfaction",
                score=30.0,
                weight=0.20,
                weighted_score=6.0,
                trend="stable",
                factors=[],
            ),
            "value_realization": HealthScoreComponent(
                name="value_realization",
                score=30.0,
                weight=0.15,
                weighted_score=4.5,
                trend="stable",
                factors=[],
            ),
            "support_health": HealthScoreComponent(
                name="support_health",
                score=30.0,
                weight=0.15,
                weighted_score=4.5,
                trend="stable",
                factors=[],
            ),
        }

        recommendations = health_service._generate_recommendations(
            components, HealthStatus.CRITICAL
        )

        assert len(recommendations) <= 5


# =============================================================================
# Alerts Tests
# =============================================================================


class TestAlerts:
    """Tests for alert identification."""

    def test_alert_for_declining_trend(self, health_service):
        """Test alert generation for declining trends."""
        components = {
            "engagement": HealthScoreComponent(
                name="engagement",
                score=70.0,
                weight=0.25,
                weighted_score=17.5,
                trend="declining",
                factors=[],
            ),
        }

        alerts = health_service._identify_alerts(components)

        declining_alerts = [a for a in alerts if a["type"] == "declining_metric"]
        assert len(declining_alerts) >= 1
        assert declining_alerts[0]["severity"] == "warning"
        assert declining_alerts[0]["component"] == "engagement"

    def test_alert_for_critical_score(self, health_service):
        """Test alert generation for critical scores."""
        components = {
            "adoption": HealthScoreComponent(
                name="adoption",
                score=35.0,  # Below 40 threshold
                weight=0.25,
                weighted_score=8.75,
                trend="stable",
                factors=[],
            ),
        }

        alerts = health_service._identify_alerts(components)

        critical_alerts = [a for a in alerts if a["type"] == "critical_score"]
        assert len(critical_alerts) >= 1
        assert critical_alerts[0]["severity"] == "critical"

    def test_alert_for_critical_factor(self, health_service):
        """Test alert generation for critical individual factors."""
        components = {
            "support_health": HealthScoreComponent(
                name="support_health",
                score=70.0,
                weight=0.15,
                weighted_score=10.5,
                trend="stable",
                factors=[
                    {"name": "escalation_rate", "score": 25.0, "status": "poor"},
                ],
            ),
        }

        alerts = health_service._identify_alerts(components)

        factor_alerts = [a for a in alerts if a["type"] == "critical_factor"]
        assert len(factor_alerts) >= 1
        assert factor_alerts[0]["factor"] == "escalation_rate"


# =============================================================================
# Health Trend Tests
# =============================================================================


class TestHealthTrend:
    """Tests for health score trend analysis."""

    @pytest.mark.asyncio
    async def test_get_health_trend(self, health_service, customer_id):
        """Test getting health trend for a customer."""
        # Calculate a few health scores to build history
        await health_service.calculate_health_score(customer_id)
        await health_service.calculate_health_score(customer_id)

        trend = await health_service.get_health_trend(customer_id, days=90)

        assert trend.customer_id == customer_id
        assert isinstance(trend.scores, list)
        assert trend.trend_direction in ["improving", "declining", "stable"]
        assert isinstance(trend.change_percent, float)

    @pytest.mark.asyncio
    async def test_health_trend_improving(self, health_service, customer_id):
        """Test detection of improving trend."""
        # Manually add history with improving scores
        health_service._health_history = [
            {
                "customer_id": customer_id,
                "score": 50.0,
                "status": "at_risk",
                "calculated_at": datetime.now(timezone.utc) - timedelta(days=30),
            },
            {
                "customer_id": customer_id,
                "score": 70.0,
                "status": "healthy",
                "calculated_at": datetime.now(timezone.utc),
            },
        ]

        trend = await health_service.get_health_trend(customer_id, days=90)

        assert trend.trend_direction == "improving"
        assert trend.change_percent > 0

    @pytest.mark.asyncio
    async def test_health_trend_declining(self, health_service, customer_id):
        """Test detection of declining trend."""
        health_service._health_history = [
            {
                "customer_id": customer_id,
                "score": 80.0,
                "status": "excellent",
                "calculated_at": datetime.now(timezone.utc) - timedelta(days=30),
            },
            {
                "customer_id": customer_id,
                "score": 60.0,
                "status": "healthy",
                "calculated_at": datetime.now(timezone.utc),
            },
        ]

        trend = await health_service.get_health_trend(customer_id, days=90)

        assert trend.trend_direction == "declining"
        assert trend.change_percent < 0

    @pytest.mark.asyncio
    async def test_health_trend_stable(self, health_service, customer_id):
        """Test detection of stable trend."""
        health_service._health_history = [
            {
                "customer_id": customer_id,
                "score": 70.0,
                "status": "healthy",
                "calculated_at": datetime.now(timezone.utc) - timedelta(days=30),
            },
            {
                "customer_id": customer_id,
                "score": 71.0,
                "status": "healthy",
                "calculated_at": datetime.now(timezone.utc),
            },
        ]

        trend = await health_service.get_health_trend(customer_id, days=90)

        assert trend.trend_direction == "stable"

    @pytest.mark.asyncio
    async def test_health_trend_single_data_point(self, health_service, customer_id):
        """Test trend with only one data point."""
        health_service._health_history = [
            {
                "customer_id": customer_id,
                "score": 70.0,
                "status": "healthy",
                "calculated_at": datetime.now(timezone.utc),
            },
        ]

        trend = await health_service.get_health_trend(customer_id, days=90)

        assert trend.trend_direction == "stable"
        assert trend.change_percent == 0

    @pytest.mark.asyncio
    async def test_health_trend_no_data(self, health_service, customer_id):
        """Test trend with no historical data."""
        trend = await health_service.get_health_trend(customer_id, days=90)

        assert trend.scores == []
        assert trend.trend_direction == "stable"


# =============================================================================
# Customer Listing Tests
# =============================================================================


class TestCustomerListing:
    """Tests for customer listing operations."""

    @pytest.mark.asyncio
    async def test_list_at_risk_customers(self, health_service):
        """Test listing at-risk customers."""
        # Create some customers with different statuses
        customer1 = f"cust_{uuid.uuid4().hex[:8]}"
        customer2 = f"cust_{uuid.uuid4().hex[:8]}"
        customer3 = f"cust_{uuid.uuid4().hex[:8]}"

        # We need to mock to control the scores
        health_service._health_scores = {
            customer1: CustomerHealthScore(
                customer_id=customer1,
                overall_score=35.0,
                status=HealthStatus.CRITICAL,
                churn_risk=ChurnRisk.CRITICAL,
                expansion_potential=ExpansionPotential.NONE,
                components={},
                recommendations=[],
                calculated_at=datetime.now(timezone.utc),
                next_review=datetime.now(timezone.utc) + timedelta(days=7),
            ),
            customer2: CustomerHealthScore(
                customer_id=customer2,
                overall_score=45.0,
                status=HealthStatus.AT_RISK,
                churn_risk=ChurnRisk.HIGH,
                expansion_potential=ExpansionPotential.NONE,
                components={},
                recommendations=[],
                calculated_at=datetime.now(timezone.utc),
                next_review=datetime.now(timezone.utc) + timedelta(days=7),
            ),
            customer3: CustomerHealthScore(
                customer_id=customer3,
                overall_score=80.0,
                status=HealthStatus.EXCELLENT,
                churn_risk=ChurnRisk.LOW,
                expansion_potential=ExpansionPotential.HIGH,
                components={},
                recommendations=[],
                calculated_at=datetime.now(timezone.utc),
                next_review=datetime.now(timezone.utc) + timedelta(days=7),
            ),
        }

        at_risk = await health_service.list_at_risk_customers()

        assert len(at_risk) == 2
        # Should be sorted by score ascending (worst first)
        assert at_risk[0].overall_score <= at_risk[1].overall_score
        assert all(
            c.status in [HealthStatus.AT_RISK, HealthStatus.CRITICAL] for c in at_risk
        )

    @pytest.mark.asyncio
    async def test_list_expansion_opportunities(self, health_service):
        """Test listing expansion opportunities."""
        customer1 = f"cust_{uuid.uuid4().hex[:8]}"
        customer2 = f"cust_{uuid.uuid4().hex[:8]}"
        customer3 = f"cust_{uuid.uuid4().hex[:8]}"

        health_service._health_scores = {
            customer1: CustomerHealthScore(
                customer_id=customer1,
                overall_score=90.0,
                status=HealthStatus.EXCELLENT,
                churn_risk=ChurnRisk.LOW,
                expansion_potential=ExpansionPotential.HIGH,
                components={},
                recommendations=[],
                calculated_at=datetime.now(timezone.utc),
                next_review=datetime.now(timezone.utc) + timedelta(days=7),
            ),
            customer2: CustomerHealthScore(
                customer_id=customer2,
                overall_score=75.0,
                status=HealthStatus.HEALTHY,
                churn_risk=ChurnRisk.LOW,
                expansion_potential=ExpansionPotential.HIGH,
                components={},
                recommendations=[],
                calculated_at=datetime.now(timezone.utc),
                next_review=datetime.now(timezone.utc) + timedelta(days=7),
            ),
            customer3: CustomerHealthScore(
                customer_id=customer3,
                overall_score=50.0,
                status=HealthStatus.AT_RISK,
                churn_risk=ChurnRisk.HIGH,
                expansion_potential=ExpansionPotential.NONE,
                components={},
                recommendations=[],
                calculated_at=datetime.now(timezone.utc),
                next_review=datetime.now(timezone.utc) + timedelta(days=7),
            ),
        }

        opportunities = await health_service.list_expansion_opportunities()

        assert len(opportunities) == 2
        # Should be sorted by score descending (best first)
        assert opportunities[0].overall_score >= opportunities[1].overall_score
        assert all(
            c.expansion_potential == ExpansionPotential.HIGH for c in opportunities
        )

    @pytest.mark.asyncio
    async def test_list_at_risk_customers_limit(self, health_service):
        """Test listing at-risk customers with limit."""
        # Create more at-risk customers than the limit
        for i in range(25):
            customer_id = f"cust_{i}"
            health_service._health_scores[customer_id] = CustomerHealthScore(
                customer_id=customer_id,
                overall_score=35.0 + i,
                status=HealthStatus.AT_RISK,
                churn_risk=ChurnRisk.HIGH,
                expansion_potential=ExpansionPotential.NONE,
                components={},
                recommendations=[],
                calculated_at=datetime.now(timezone.utc),
                next_review=datetime.now(timezone.utc) + timedelta(days=7),
            )

        at_risk = await health_service.list_at_risk_customers(limit=10)

        assert len(at_risk) == 10

    @pytest.mark.asyncio
    async def test_get_health_score(self, customer_with_health_score, health_service):
        """Test getting a stored health score."""
        customer_id, original_score = customer_with_health_score

        retrieved = await health_service.get_health_score(customer_id)

        assert retrieved is not None
        assert retrieved.customer_id == customer_id
        assert retrieved.overall_score == original_score.overall_score

    @pytest.mark.asyncio
    async def test_get_health_score_not_found(self, health_service):
        """Test getting health score for unknown customer."""
        result = await health_service.get_health_score("unknown_customer")
        assert result is None


# =============================================================================
# Singleton Tests
# =============================================================================


class TestCustomerHealthSingleton:
    """Tests for singleton pattern."""

    def test_get_customer_health_service(self):
        """Test getting customer health service singleton."""
        import src.services.customer_health_service as module

        module._service = None

        service = get_customer_health_service()

        assert service is not None
        assert isinstance(service, CustomerHealthService)

    def test_singleton_returns_same_instance(self):
        """Test that singleton returns same instance."""
        import src.services.customer_health_service as module

        module._service = None

        service1 = get_customer_health_service()
        service2 = get_customer_health_service()

        assert service1 is service2

    def test_get_service_with_explicit_mode(self):
        """Test getting service with explicit mode."""
        import src.services.customer_health_service as module

        module._service = None

        service = get_customer_health_service(mode="mock")

        assert service.mode == "mock"


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_health_score_stored_in_history(self, health_service, customer_id):
        """Test that calculated scores are stored in history."""
        initial_history_len = len(health_service._health_history)

        await health_service.calculate_health_score(customer_id)

        assert len(health_service._health_history) == initial_history_len + 1
        assert health_service._health_history[-1]["customer_id"] == customer_id

    @pytest.mark.asyncio
    async def test_next_review_date_set(self, health_service, customer_id):
        """Test that next review date is correctly set."""
        score = await health_service.calculate_health_score(customer_id)

        expected_review = score.calculated_at + timedelta(days=7)
        time_diff = abs((score.next_review - expected_review).total_seconds())

        # Allow for small timing differences
        assert time_diff < 60

    def test_component_weights_are_valid(self):
        """Test that all component weights are between 0 and 1."""
        for name, weight in COMPONENT_WEIGHTS.items():
            assert 0 <= weight <= 1, f"Weight for {name} is out of range"

    def test_status_thresholds_are_ordered(self):
        """Test that status thresholds are properly ordered."""
        assert (
            STATUS_THRESHOLDS[HealthStatus.EXCELLENT]
            > STATUS_THRESHOLDS[HealthStatus.HEALTHY]
        )
        assert (
            STATUS_THRESHOLDS[HealthStatus.HEALTHY]
            > STATUS_THRESHOLDS[HealthStatus.AT_RISK]
        )
        assert (
            STATUS_THRESHOLDS[HealthStatus.AT_RISK]
            > STATUS_THRESHOLDS[HealthStatus.CRITICAL]
        )

    def test_churn_risk_thresholds_are_ordered(self):
        """Test that churn risk thresholds are properly ordered."""
        assert (
            CHURN_RISK_THRESHOLDS[ChurnRisk.LOW]
            > CHURN_RISK_THRESHOLDS[ChurnRisk.MEDIUM]
        )
        assert (
            CHURN_RISK_THRESHOLDS[ChurnRisk.MEDIUM]
            > CHURN_RISK_THRESHOLDS[ChurnRisk.HIGH]
        )
        assert (
            CHURN_RISK_THRESHOLDS[ChurnRisk.HIGH]
            > CHURN_RISK_THRESHOLDS[ChurnRisk.CRITICAL]
        )

    @pytest.mark.asyncio
    async def test_health_score_format(self, health_service, customer_id):
        """Test that health score values are properly formatted."""
        score = await health_service.calculate_health_score(customer_id)

        # Score should be rounded to 1 decimal place
        assert score.overall_score == round(score.overall_score, 1)

        # All component scores should be properly weighted
        for component in score.components.values():
            expected_weighted = round(component.score * component.weight, 1)
            assert abs(component.weighted_score - expected_weighted) < 0.1

    @pytest.mark.asyncio
    async def test_health_score_persistence(self, health_service, customer_id):
        """Test that health scores are stored correctly."""
        # Calculate health score
        score = await health_service.calculate_health_score(customer_id)

        # Retrieve it back
        stored = await health_service.get_health_score(customer_id)

        assert stored is not None
        assert stored.customer_id == score.customer_id
        assert stored.overall_score == score.overall_score
        assert stored.status == score.status

    def test_health_status_enum_values(self):
        """Test HealthStatus enum values."""
        assert HealthStatus.EXCELLENT.value == "excellent"
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.AT_RISK.value == "at_risk"
        assert HealthStatus.CRITICAL.value == "critical"

    def test_churn_risk_enum_values(self):
        """Test ChurnRisk enum values."""
        assert ChurnRisk.LOW.value == "low"
        assert ChurnRisk.MEDIUM.value == "medium"
        assert ChurnRisk.HIGH.value == "high"
        assert ChurnRisk.CRITICAL.value == "critical"

    def test_expansion_potential_enum_values(self):
        """Test ExpansionPotential enum values."""
        assert ExpansionPotential.HIGH.value == "high"
        assert ExpansionPotential.MEDIUM.value == "medium"
        assert ExpansionPotential.LOW.value == "low"
        assert ExpansionPotential.NONE.value == "none"
