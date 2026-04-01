"""
Tests for GPU Cost Service

ADR-061: GPU Workload Scheduler - Phase 4 Observability & Cost
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.services.gpu_scheduler.gpu_cost_service import (
    ON_DEMAND_PRICES,
    SPOT_PRICE_ESTIMATES,
    CostSummary,
    GPUCostService,
    JobCostEstimate,
    OrganizationBudget,
)


@pytest.fixture
def mock_dynamodb():
    """Create mock DynamoDB resource."""
    mock = MagicMock()
    mock_table = MagicMock()
    mock.Table.return_value = mock_table
    return mock, mock_table


@pytest.fixture
def mock_ec2():
    """Create mock EC2 client."""
    mock = MagicMock()
    mock.describe_spot_price_history.return_value = {
        "SpotPriceHistory": [
            {
                "InstanceType": "g4dn.xlarge",
                "SpotPrice": "0.15",
                "Timestamp": datetime.now(timezone.utc),
            }
        ]
    }
    return mock


@pytest.fixture
def mock_sns():
    """Create mock SNS client."""
    mock = MagicMock()
    mock.publish.return_value = {"MessageId": "test-message-id"}
    return mock


@pytest.fixture
def cost_service(mock_dynamodb, mock_ec2, mock_sns):
    """Create GPU cost service with mocks."""
    mock_resource, mock_table = mock_dynamodb

    with (
        patch("boto3.resource") as mock_boto_resource,
        patch("boto3.client") as mock_boto_client,
    ):
        mock_boto_resource.return_value = mock_resource
        mock_boto_client.side_effect = lambda service, **kwargs: {
            "ec2": mock_ec2,
            "sns": mock_sns,
        }.get(service)

        service = GPUCostService(
            dynamodb_table_name="test-jobs",
            quotas_table_name="test-quotas",
            region="us-east-1",
            environment="test",
        )
        service._jobs_table = mock_table
        service._quotas_table = mock_table
        service._ec2 = mock_ec2
        service._sns = mock_sns

        return service


class TestGPUCostServiceInit:
    """Tests for GPUCostService initialization."""

    def test_init_default_values(self, cost_service):
        """Test initialization with default values."""
        assert cost_service.region == "us-east-1"
        assert cost_service.environment == "test"
        assert cost_service._alert_topic_arn is None

    def test_set_alert_topic(self, cost_service):
        """Test setting alert topic ARN."""
        cost_service.set_alert_topic("arn:aws:sns:us-east-1:123:test-topic")
        assert cost_service._alert_topic_arn == "arn:aws:sns:us-east-1:123:test-topic"


class TestSpotPricing:
    """Tests for Spot pricing functionality."""

    def test_spot_price_estimates_exist(self):
        """Test Spot price estimates are defined."""
        assert "g4dn.xlarge" in SPOT_PRICE_ESTIMATES
        assert "g4dn.12xlarge" in SPOT_PRICE_ESTIMATES
        assert SPOT_PRICE_ESTIMATES["g4dn.xlarge"] == 0.16

    def test_on_demand_prices_exist(self):
        """Test on-demand prices are defined."""
        assert "g4dn.xlarge" in ON_DEMAND_PRICES
        assert ON_DEMAND_PRICES["g4dn.xlarge"] == 0.526

    @pytest.mark.asyncio
    async def test_get_current_spot_price_cached(self, cost_service, mock_ec2):
        """Test Spot price fetching with cache."""
        # First call should fetch from API
        price = await cost_service.get_current_spot_price("g4dn.xlarge")
        assert price == 0.15  # From mock

        # Verify API was called
        mock_ec2.describe_spot_price_history.assert_called()

    @pytest.mark.asyncio
    async def test_get_current_spot_price_fallback(self, cost_service, mock_ec2):
        """Test Spot price fallback on API error."""
        # Use ClientError which is what the service catches
        mock_ec2.describe_spot_price_history.side_effect = ClientError(
            {"Error": {"Code": "RequestLimitExceeded", "Message": "API Rate limit"}},
            "DescribeSpotPriceHistory",
        )

        price = await cost_service.get_current_spot_price("g4dn.xlarge")
        assert price == SPOT_PRICE_ESTIMATES["g4dn.xlarge"]


class TestJobCostCalculation:
    """Tests for job cost calculation."""

    @pytest.mark.asyncio
    async def test_calculate_job_cost_spot(self, cost_service):
        """Test job cost calculation with Spot pricing."""
        # 1 hour at $0.15/hour
        cost = await cost_service.calculate_job_cost(
            duration_seconds=3600,
            instance_type="g4dn.xlarge",
            pricing_type="spot",
        )

        # Should be close to 0.15
        assert 0.14 <= cost <= 0.16

    @pytest.mark.asyncio
    async def test_calculate_job_cost_on_demand(self, cost_service):
        """Test job cost calculation with on-demand pricing."""
        # 1 hour at $0.526/hour
        cost = await cost_service.calculate_job_cost(
            duration_seconds=3600,
            instance_type="g4dn.xlarge",
            pricing_type="on_demand",
        )

        assert cost == pytest.approx(0.526, rel=0.01)

    @pytest.mark.asyncio
    async def test_calculate_job_cost_partial_hour(self, cost_service):
        """Test job cost calculation for partial hours."""
        # 30 minutes at $0.15/hour = $0.075
        cost = await cost_service.calculate_job_cost(
            duration_seconds=1800,
            instance_type="g4dn.xlarge",
            pricing_type="spot",
        )

        assert cost == pytest.approx(0.075, rel=0.1)


class TestCostEstimation:
    """Tests for pre-submission cost estimation."""

    @pytest.mark.asyncio
    async def test_estimate_job_cost_embedding(self, cost_service):
        """Test cost estimation for embedding generation."""
        estimate = await cost_service.estimate_job_cost(
            job_type="embedding_generation",
            priority="normal",
            instance_type="g4dn.xlarge",
        )

        assert isinstance(estimate, JobCostEstimate)
        assert estimate.estimated_duration_minutes == 30
        assert estimate.confidence == 0.85
        assert estimate.pricing_type == "spot"
        assert estimate.estimated_cost_usd > 0

    @pytest.mark.asyncio
    async def test_estimate_job_cost_training(self, cost_service):
        """Test cost estimation for SWE-RL training."""
        estimate = await cost_service.estimate_job_cost(
            job_type="swe_rl_training",
            priority="high",
            instance_type="g4dn.xlarge",
        )

        assert estimate.estimated_duration_minutes == 180  # 3 hours
        assert estimate.confidence == 0.65  # Lower confidence for training

    @pytest.mark.asyncio
    async def test_estimate_job_cost_with_config(self, cost_service):
        """Test cost estimation adjusts for config."""
        # Large repository should increase duration
        estimate = await cost_service.estimate_job_cost(
            job_type="embedding_generation",
            priority="normal",
            config={"repository_size_mb": 2000},  # Large repo
        )

        # Duration should be 1.5x baseline
        assert estimate.estimated_duration_minutes == 45  # 30 * 1.5

    @pytest.mark.asyncio
    async def test_estimate_includes_breakdown(self, cost_service):
        """Test cost estimate includes breakdown."""
        estimate = await cost_service.estimate_job_cost(
            job_type="embedding_generation",
            priority="normal",
        )

        assert "compute" in estimate.breakdown
        assert "storage" in estimate.breakdown
        assert "network" in estimate.breakdown


class TestCostAggregation:
    """Tests for cost aggregation."""

    @pytest.mark.asyncio
    async def test_get_cost_summary(self, cost_service):
        """Test getting cost summary for a period."""
        # Setup mock response
        cost_service._jobs_table.query.return_value = {
            "Items": [
                {
                    "job_id": "job-1",
                    "job_type": "embedding_generation",
                    "priority": "normal",
                    "status": "completed",
                    "cost_usd": Decimal("0.50"),
                    "created_at": "2026-01-13T10:00:00Z",
                    "started_at": "2026-01-13T10:05:00Z",
                    "completed_at": "2026-01-13T10:35:00Z",
                },
                {
                    "job_id": "job-2",
                    "job_type": "swe_rl_training",
                    "priority": "high",
                    "status": "completed",
                    "cost_usd": Decimal("1.20"),
                    "created_at": "2026-01-13T11:00:00Z",
                    "started_at": "2026-01-13T11:05:00Z",
                    "completed_at": "2026-01-13T13:05:00Z",
                },
            ]
        }

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        summary = await cost_service.get_cost_summary("org-123", start, end)

        assert isinstance(summary, CostSummary)
        assert summary.total_cost_usd == 1.70
        assert summary.jobs_count == 2
        assert "embedding_generation" in summary.by_job_type
        assert "swe_rl_training" in summary.by_job_type

    @pytest.mark.asyncio
    async def test_get_cost_summary_empty(self, cost_service):
        """Test cost summary with no jobs."""
        cost_service._jobs_table.query.return_value = {"Items": []}

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 31, tzinfo=timezone.utc)

        summary = await cost_service.get_cost_summary("org-123", start, end)

        assert summary.total_cost_usd == 0.0
        assert summary.jobs_count == 0
        assert summary.avg_job_cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_get_monthly_cost(self, cost_service):
        """Test getting monthly cost summary."""
        cost_service._jobs_table.query.return_value = {"Items": []}

        summary = await cost_service.get_monthly_cost("org-123", 2026, 1)

        assert summary.period_start.year == 2026
        assert summary.period_start.month == 1


class TestBudgetManagement:
    """Tests for budget management."""

    @pytest.mark.asyncio
    async def test_set_budget(self, cost_service):
        """Test setting organization budget."""
        budget = await cost_service.set_budget(
            organization_id="org-123",
            monthly_budget_usd=100.0,
            daily_budget_usd=10.0,
            alert_threshold_percent=80.0,
            hard_limit_enabled=False,
        )

        assert isinstance(budget, OrganizationBudget)
        assert budget.organization_id == "org-123"
        assert budget.monthly_budget_usd == 100.0
        assert budget.alert_threshold_percent == 80.0

        # Verify DynamoDB update was called
        cost_service._quotas_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_budget(self, cost_service):
        """Test getting organization budget."""
        cost_service._quotas_table.get_item.return_value = {
            "Item": {
                "PK": "ORG#org-123",
                "SK": "BUDGET",
                "monthly_budget_usd": Decimal("100"),
                "daily_budget_usd": Decimal("10"),
                "alert_threshold_percent": Decimal("80"),
                "hard_limit_enabled": False,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        }

        budget = await cost_service.get_budget("org-123")

        assert budget is not None
        assert budget.monthly_budget_usd == 100.0
        assert budget.alert_threshold_percent == 80.0

    @pytest.mark.asyncio
    async def test_get_budget_not_found(self, cost_service):
        """Test getting budget that doesn't exist."""
        cost_service._quotas_table.get_item.return_value = {}

        budget = await cost_service.get_budget("org-999")

        assert budget is None


class TestBudgetChecking:
    """Tests for budget checking and alerts."""

    @pytest.mark.asyncio
    async def test_check_budget_within_limit(self, cost_service):
        """Test budget check when within limit."""
        # Setup budget
        cost_service._quotas_table.get_item.return_value = {
            "Item": {
                "monthly_budget_usd": Decimal("100"),
                "alert_threshold_percent": Decimal("80"),
                "hard_limit_enabled": False,
            }
        }

        # Setup low cost usage
        cost_service._jobs_table.query.return_value = {
            "Items": [{"cost_usd": Decimal("20"), "created_at": "2026-01-13T10:00:00Z"}]
        }

        within_budget, alert = await cost_service.check_budget("org-123")

        assert within_budget is True
        assert alert is None

    @pytest.mark.asyncio
    async def test_check_budget_threshold_warning(self, cost_service, mock_sns):
        """Test budget check triggers threshold warning."""
        cost_service.set_alert_topic("arn:aws:sns:us-east-1:123:alerts")

        # Setup budget
        cost_service._quotas_table.get_item.return_value = {
            "Item": {
                "monthly_budget_usd": Decimal("100"),
                "alert_threshold_percent": Decimal("80"),
                "hard_limit_enabled": False,
            }
        }

        # Setup 85% usage
        cost_service._jobs_table.query.return_value = {
            "Items": [{"cost_usd": Decimal("85"), "created_at": "2026-01-13T10:00:00Z"}]
        }

        within_budget, alert = await cost_service.check_budget("org-123")

        assert within_budget is True
        assert alert is not None
        assert alert.alert_type == "threshold_warning"
        assert alert.usage_percent == 85.0

        # Verify SNS notification sent
        mock_sns.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_budget_exceeded(self, cost_service, mock_sns):
        """Test budget check when exceeded."""
        cost_service.set_alert_topic("arn:aws:sns:us-east-1:123:alerts")

        # Setup budget with hard limit
        cost_service._quotas_table.get_item.return_value = {
            "Item": {
                "monthly_budget_usd": Decimal("100"),
                "alert_threshold_percent": Decimal("80"),
                "hard_limit_enabled": True,
            }
        }

        # Setup 105% usage
        cost_service._jobs_table.query.return_value = {
            "Items": [
                {"cost_usd": Decimal("105"), "created_at": "2026-01-13T10:00:00Z"}
            ]
        }

        within_budget, alert = await cost_service.check_budget("org-123")

        assert within_budget is False  # Hard limit enabled
        assert alert is not None
        assert alert.alert_type == "threshold_exceeded"

    @pytest.mark.asyncio
    async def test_check_budget_no_budget_set(self, cost_service):
        """Test budget check when no budget is set."""
        cost_service._quotas_table.get_item.return_value = {}

        within_budget, alert = await cost_service.check_budget("org-123")

        assert within_budget is True
        assert alert is None


class TestCostForecasting:
    """Tests for cost forecasting."""

    @pytest.mark.asyncio
    async def test_forecast_end_of_month(self, cost_service):
        """Test end-of-month cost forecast."""
        # Setup current usage
        cost_service._jobs_table.query.return_value = {
            "Items": [{"cost_usd": Decimal("30"), "created_at": "2026-01-13T10:00:00Z"}]
        }

        with patch("src.services.gpu_scheduler.gpu_cost_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 15, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            forecast = await cost_service.forecast_end_of_month_cost("org-123")

        assert "forecast_usd" in forecast
        assert "confidence_low_usd" in forecast
        assert "confidence_high_usd" in forecast
        assert "daily_average_usd" in forecast
        assert forecast["days_remaining"] > 0

    @pytest.mark.asyncio
    async def test_forecast_early_month(self, cost_service):
        """Test forecast with limited data early in month."""
        cost_service._jobs_table.query.return_value = {"Items": []}

        forecast = await cost_service.forecast_end_of_month_cost("org-123")

        assert forecast["forecast_usd"] == 0.0


class TestInstanceSpecs:
    """Tests for instance specification helpers."""

    def test_get_gpu_count(self, cost_service):
        """Test GPU count for instance types."""
        assert cost_service._get_gpu_count("g4dn.xlarge") == 1
        assert cost_service._get_gpu_count("g4dn.12xlarge") == 4
        assert cost_service._get_gpu_count("unknown") == 1  # Default

    def test_get_instance_specs(self, cost_service):
        """Test instance specs (vCPU, memory)."""
        vcpus, memory = cost_service._get_instance_specs("g4dn.xlarge")
        assert vcpus == 4
        assert memory == 16

        vcpus, memory = cost_service._get_instance_specs("g4dn.12xlarge")
        assert vcpus == 48
        assert memory == 192


class TestAlertFormatting:
    """Tests for alert message formatting."""

    def test_format_alert_message_warning(self, cost_service):
        """Test warning alert message format."""
        message = cost_service._format_alert_message(
            organization_id="org-123",
            current=80.0,
            limit=100.0,
            percent=80.0,
            forecast=95.0,
        )

        assert "WARNING" in message
        assert "org-123" in message
        assert "$80.00" in message
        assert "80%" in message

    def test_format_alert_message_exceeded(self, cost_service):
        """Test exceeded alert message format."""
        message = cost_service._format_alert_message(
            organization_id="org-123",
            current=105.0,
            limit=100.0,
            percent=105.0,
            forecast=150.0,
        )

        assert "EXCEEDED" in message
        assert "$105.00" in message
