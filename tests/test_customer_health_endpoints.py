"""
Tests for Customer Health API Endpoints

Tests for the customer health score management API.
"""

import pytest

# ==================== Response Model Tests ====================


class TestHealthComponentResponse:
    """Tests for HealthComponentResponse model."""

    def test_creation(self):
        """Test model creation."""
        from src.api.customer_health_endpoints import HealthComponentResponse

        response = HealthComponentResponse(
            name="usage",
            score=85.0,
            weight=0.3,
            weighted_score=25.5,
            trend="improving",
            factors=[{"name": "api_calls", "value": 1000}],
        )
        assert response.name == "usage"
        assert response.score == 85.0
        assert response.weighted_score == 25.5


class TestHealthScoreResponse:
    """Tests for HealthScoreResponse model."""

    def test_creation(self):
        """Test model creation."""
        from src.api.customer_health_endpoints import (
            HealthComponentResponse,
            HealthScoreResponse,
        )

        component = HealthComponentResponse(
            name="usage",
            score=85.0,
            weight=0.3,
            weighted_score=25.5,
            trend="improving",
            factors=[],
        )
        response = HealthScoreResponse(
            customer_id="cust-001",
            overall_score=85.0,
            status="healthy",
            churn_risk="low",
            expansion_potential="high",
            components={"usage": component},
            recommendations=["Increase feature adoption"],
            alerts=[],
            calculated_at="2025-01-01T00:00:00Z",
            next_review="2025-02-01T00:00:00Z",
        )
        assert response.customer_id == "cust-001"
        assert response.overall_score == 85.0


class TestHealthTrendResponse:
    """Tests for HealthTrendResponse model."""

    def test_creation(self):
        """Test model creation."""
        from src.api.customer_health_endpoints import HealthTrendResponse

        response = HealthTrendResponse(
            customer_id="cust-001",
            scores=[{"date": "2025-01-01", "score": 80.0}],
            period_start="2024-12-01",
            period_end="2025-01-01",
            trend_direction="improving",
            change_percent=5.0,
        )
        assert response.trend_direction == "improving"
        assert response.change_percent == 5.0


class TestAtRiskCustomerResponse:
    """Tests for AtRiskCustomerResponse model."""

    def test_creation(self):
        """Test model creation."""
        from src.api.customer_health_endpoints import AtRiskCustomerResponse

        response = AtRiskCustomerResponse(
            customer_id="cust-002",
            overall_score=45.0,
            status="at_risk",
            churn_risk="high",
            primary_concerns=["Low usage", "Support tickets"],
            recommended_action="Schedule executive check-in",
        )
        assert response.churn_risk == "high"
        assert len(response.primary_concerns) == 2


class TestExpansionOpportunityResponse:
    """Tests for ExpansionOpportunityResponse model."""

    def test_creation(self):
        """Test model creation."""
        from src.api.customer_health_endpoints import ExpansionOpportunityResponse

        response = ExpansionOpportunityResponse(
            customer_id="cust-003",
            overall_score=92.0,
            expansion_potential="high",
            value_signals=["Rapid growth", "Feature requests"],
            recommended_action="Discuss enterprise tier",
        )
        assert response.expansion_potential == "high"


# ==================== Router Tests ====================


class TestCustomerHealthRouter:
    """Tests for customer health router."""

    def test_router_exists(self):
        """Test router is defined."""
        from src.api.customer_health_endpoints import router

        assert router is not None
        assert router.prefix == "/api/v1/customer-health"

    def test_router_tags(self):
        """Test router has correct tags."""
        from src.api.customer_health_endpoints import router

        assert "Customer Health" in router.tags


# ==================== Service Integration Tests ====================


class TestCustomerHealthService:
    """Tests for CustomerHealthService."""

    def test_service_import(self):
        """Test service can be imported."""
        from src.services.customer_health_service import CustomerHealthService

        service = CustomerHealthService()
        assert service is not None

    def test_health_status_enum(self):
        """Test HealthStatus enum."""
        from src.services.customer_health_service import HealthStatus

        assert HealthStatus.HEALTHY is not None
        assert HealthStatus.AT_RISK is not None
        assert HealthStatus.CRITICAL is not None
        assert HealthStatus.EXCELLENT is not None

    def test_churn_risk_enum(self):
        """Test ChurnRisk enum."""
        from src.services.customer_health_service import ChurnRisk

        assert ChurnRisk.LOW is not None
        assert ChurnRisk.MEDIUM is not None
        assert ChurnRisk.HIGH is not None

    def test_expansion_potential_enum(self):
        """Test ExpansionPotential enum."""
        from src.services.customer_health_service import ExpansionPotential

        assert ExpansionPotential.LOW is not None
        assert ExpansionPotential.MEDIUM is not None
        assert ExpansionPotential.HIGH is not None

    def test_health_trend_dataclass(self):
        """Test HealthTrend dataclass."""
        from datetime import datetime, timezone

        from src.services.customer_health_service import HealthTrend

        trend = HealthTrend(
            customer_id="cust-001",
            scores=[{"date": "2025-01-01", "score": 80}],
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            trend_direction="improving",
            change_percent=5.0,
        )
        assert trend.customer_id == "cust-001"
        assert trend.trend_direction == "improving"


class TestHealthScoreComponent:
    """Tests for HealthScoreComponent dataclass."""

    def test_creation(self):
        """Test component creation."""
        from src.services.customer_health_service import HealthScoreComponent

        component = HealthScoreComponent(
            name="engagement",
            score=75.0,
            weight=0.25,
            weighted_score=18.75,  # 75.0 * 0.25
            trend="improving",
            factors=[{"name": "logins", "value": 50}],
        )
        assert component.name == "engagement"
        assert component.score == 75.0
        assert component.weight == 0.25
        assert component.weighted_score == 18.75


class TestCustomerHealthScore:
    """Tests for CustomerHealthScore dataclass."""

    def test_creation(self):
        """Test health score creation."""
        from src.services.customer_health_service import (
            ChurnRisk,
            CustomerHealthScore,
            ExpansionPotential,
            HealthScoreComponent,
            HealthStatus,
        )

        component = HealthScoreComponent(
            name="usage",
            score=80.0,
            weight=0.3,
            weighted_score=24.0,  # 80.0 * 0.3
            trend="stable",
            factors=[],
        )
        from datetime import datetime, timezone

        score = CustomerHealthScore(
            customer_id="cust-001",
            overall_score=80.0,
            status=HealthStatus.HEALTHY,
            churn_risk=ChurnRisk.LOW,
            expansion_potential=ExpansionPotential.MEDIUM,
            components={"usage": component},
            recommendations=["Keep up the good work"],
            calculated_at=datetime.now(timezone.utc),
            next_review=datetime.now(timezone.utc),
            alerts=[],
        )
        assert score.customer_id == "cust-001"
        assert score.status == HealthStatus.HEALTHY


# ==================== Service Method Tests ====================


class TestCustomerHealthServiceMethods:
    """Tests for CustomerHealthService methods."""

    @pytest.mark.asyncio
    async def test_calculate_health_score(self):
        """Test calculating health score."""
        from src.services.customer_health_service import CustomerHealthService

        service = CustomerHealthService()
        score = await service.calculate_health_score("cust-001")
        assert score is not None
        assert score.customer_id == "cust-001"
        assert 0 <= score.overall_score <= 100

    @pytest.mark.asyncio
    async def test_get_health_score(self):
        """Test getting health score."""
        from src.services.customer_health_service import CustomerHealthService

        service = CustomerHealthService()
        # Calculate first
        await service.calculate_health_score("cust-001")
        # Then get
        score = await service.get_health_score("cust-001")
        assert score is not None

    @pytest.mark.asyncio
    async def test_get_health_trend(self):
        """Test getting health trend."""
        from src.services.customer_health_service import CustomerHealthService

        service = CustomerHealthService()
        await service.calculate_health_score("cust-001")
        trend = await service.get_health_trend("cust-001", days=30)
        assert trend is not None

    @pytest.mark.asyncio
    async def test_list_at_risk_customers(self):
        """Test listing at-risk customers."""
        from src.services.customer_health_service import CustomerHealthService

        service = CustomerHealthService()
        at_risk = await service.list_at_risk_customers()
        assert isinstance(at_risk, list)

    @pytest.mark.asyncio
    async def test_list_expansion_opportunities(self):
        """Test listing expansion opportunities."""
        from src.services.customer_health_service import CustomerHealthService

        service = CustomerHealthService()
        opportunities = await service.list_expansion_opportunities()
        assert isinstance(opportunities, list)


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_recommendations(self):
        """Test response with empty recommendations."""
        from src.api.customer_health_endpoints import HealthScoreResponse

        response = HealthScoreResponse(
            customer_id="cust-001",
            overall_score=100.0,
            status="healthy",
            churn_risk="low",
            expansion_potential="high",
            components={},
            recommendations=[],
            alerts=[],
            calculated_at="2025-01-01T00:00:00Z",
            next_review="2025-02-01T00:00:00Z",
        )
        assert response.recommendations == []

    def test_multiple_alerts(self):
        """Test response with multiple alerts."""
        from src.api.customer_health_endpoints import HealthScoreResponse

        response = HealthScoreResponse(
            customer_id="cust-002",
            overall_score=40.0,
            status="at_risk",
            churn_risk="high",
            expansion_potential="low",
            components={},
            recommendations=["Immediate attention required"],
            alerts=[
                {"type": "low_usage", "severity": "high"},
                {"type": "support_escalation", "severity": "medium"},
            ],
            calculated_at="2025-01-01T00:00:00Z",
            next_review="2025-01-15T00:00:00Z",
        )
        assert len(response.alerts) == 2

    def test_zero_change_percent(self):
        """Test trend with zero change."""
        from src.api.customer_health_endpoints import HealthTrendResponse

        response = HealthTrendResponse(
            customer_id="cust-001",
            scores=[],
            period_start="2024-12-01",
            period_end="2025-01-01",
            trend_direction="stable",
            change_percent=0.0,
        )
        assert response.change_percent == 0.0

    def test_negative_change_percent(self):
        """Test trend with negative change."""
        from src.api.customer_health_endpoints import HealthTrendResponse

        response = HealthTrendResponse(
            customer_id="cust-001",
            scores=[],
            period_start="2024-12-01",
            period_end="2025-01-01",
            trend_direction="declining",
            change_percent=-10.5,
        )
        assert response.change_percent == -10.5
