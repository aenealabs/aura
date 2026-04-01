"""
Project Aura - GPU Cost Tracking Service

Tracks and aggregates GPU workload costs for:
- Per-job cost calculation based on GPU hours and Spot pricing
- Organization-level cost aggregation and budgeting
- Cost forecasting and budget alerts
- Cost drill-down by job type, priority, and time period

ADR-061: GPU Workload Scheduler - Phase 4 Observability & Cost
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# =============================================================================
# Cost Configuration
# =============================================================================


class GPUInstanceType(str, Enum):
    """Supported GPU instance types with pricing."""

    G4DN_XLARGE = "g4dn.xlarge"
    G4DN_2XLARGE = "g4dn.2xlarge"
    G4DN_4XLARGE = "g4dn.4xlarge"
    G4DN_8XLARGE = "g4dn.8xlarge"
    G4DN_12XLARGE = "g4dn.12xlarge"
    G4DN_16XLARGE = "g4dn.16xlarge"


# Spot pricing estimates (us-east-1, subject to change)
# These are baseline estimates; actual prices fetched from EC2 Spot API
SPOT_PRICE_ESTIMATES: dict[str, float] = {
    "g4dn.xlarge": 0.16,  # 1 GPU, 4 vCPU, 16 GB
    "g4dn.2xlarge": 0.24,  # 1 GPU, 8 vCPU, 32 GB
    "g4dn.4xlarge": 0.36,  # 1 GPU, 16 vCPU, 64 GB
    "g4dn.8xlarge": 0.69,  # 1 GPU, 32 vCPU, 128 GB
    "g4dn.12xlarge": 1.26,  # 4 GPUs, 48 vCPU, 192 GB
    "g4dn.16xlarge": 1.40,  # 1 GPU, 64 vCPU, 256 GB
}

# On-demand pricing for comparison (us-east-1)
ON_DEMAND_PRICES: dict[str, float] = {
    "g4dn.xlarge": 0.526,
    "g4dn.2xlarge": 0.752,
    "g4dn.4xlarge": 1.204,
    "g4dn.8xlarge": 2.176,
    "g4dn.12xlarge": 3.912,
    "g4dn.16xlarge": 4.352,
}


@dataclass
class GPUPricing:
    """GPU instance pricing information."""

    instance_type: str
    spot_price_per_hour: float
    on_demand_price_per_hour: float
    gpus: int
    vcpus: int
    memory_gb: int
    region: str = "us-east-1"
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class JobCostEstimate:
    """Cost estimate for a GPU job."""

    job_id: str
    estimated_duration_minutes: float
    estimated_cost_usd: float
    instance_type: str
    pricing_type: str  # spot, on_demand
    confidence: float  # 0.0 to 1.0
    breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class OrganizationBudget:
    """Budget configuration for an organization."""

    organization_id: str
    monthly_budget_usd: float
    daily_budget_usd: Optional[float] = None
    alert_threshold_percent: float = 80.0
    hard_limit_enabled: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CostSummary:
    """Cost summary for a time period."""

    period_start: datetime
    period_end: datetime
    total_cost_usd: float
    gpu_hours: float
    jobs_count: int
    avg_job_cost_usd: float
    by_job_type: dict[str, float] = field(default_factory=dict)
    by_priority: dict[str, float] = field(default_factory=dict)
    by_status: dict[str, float] = field(default_factory=dict)
    daily_breakdown: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BudgetAlert:
    """Budget alert notification."""

    organization_id: str
    alert_type: str  # threshold_warning, threshold_exceeded, forecast_warning
    current_usage_usd: float
    budget_limit_usd: float
    usage_percent: float
    forecast_usd: Optional[float] = None
    message: str = ""
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# GPU Cost Service
# =============================================================================


class GPUCostService:
    """
    Tracks and manages GPU workload costs.

    Features:
    - Real-time cost calculation based on job duration
    - Spot price fetching from EC2 API
    - Organization budget management
    - Cost forecasting and alerts
    - Historical cost aggregation

    Usage:
        cost_service = GPUCostService(dynamodb_table_name="aura-gpu-costs-dev")

        # Calculate job cost
        cost = await cost_service.calculate_job_cost(job)

        # Get organization cost summary
        summary = await cost_service.get_cost_summary("org-123", start_date, end_date)

        # Check budget status
        status = await cost_service.check_budget("org-123")
    """

    def __init__(
        self,
        dynamodb_table_name: str = "aura-gpu-jobs",
        quotas_table_name: str = "aura-gpu-quotas",
        region: str = "us-east-1",
        environment: str = "dev",
    ):
        """
        Initialize GPU cost service.

        Args:
            dynamodb_table_name: DynamoDB table for job records
            quotas_table_name: DynamoDB table for quotas/budgets
            region: AWS region for pricing
            environment: Deployment environment
        """
        self.dynamodb_table_name = dynamodb_table_name
        self.quotas_table_name = quotas_table_name
        self.region = region
        self.environment = environment

        # AWS clients
        self._dynamodb = boto3.resource("dynamodb", region_name=region)
        self._ec2 = boto3.client("ec2", region_name=region)
        self._sns = boto3.client("sns", region_name=region)

        # Tables
        self._jobs_table = self._dynamodb.Table(dynamodb_table_name)
        self._quotas_table = self._dynamodb.Table(quotas_table_name)

        # Pricing cache
        self._spot_prices: dict[str, GPUPricing] = {}
        self._price_cache_ttl = timedelta(minutes=5)
        self._last_price_fetch: Optional[datetime] = None

        # Alert topic (configured externally)
        self._alert_topic_arn: Optional[str] = None

        logger.info(
            f"GPUCostService initialized for {environment} environment "
            f"(region={region})"
        )

    def set_alert_topic(self, topic_arn: str) -> None:
        """Set the SNS topic ARN for budget alerts."""
        self._alert_topic_arn = topic_arn

    # =========================================================================
    # Pricing
    # =========================================================================

    async def get_current_spot_price(
        self,
        instance_type: str = "g4dn.xlarge",
    ) -> float:
        """
        Get current Spot price for an instance type.

        Fetches from EC2 API with caching.

        Args:
            instance_type: EC2 instance type

        Returns:
            Current Spot price per hour in USD
        """
        # Check cache
        if self._should_refresh_prices():
            await self._refresh_spot_prices()

        if instance_type in self._spot_prices:
            return self._spot_prices[instance_type].spot_price_per_hour

        # Fall back to estimate
        return SPOT_PRICE_ESTIMATES.get(instance_type, 0.16)

    def _should_refresh_prices(self) -> bool:
        """Check if spot prices should be refreshed."""
        if not self._last_price_fetch:
            return True
        return (
            datetime.now(timezone.utc) - self._last_price_fetch > self._price_cache_ttl
        )

    def _fetch_single_spot_price(
        self, instance_type: str
    ) -> tuple[str, Optional[float]]:
        """Fetch spot price for a single instance type (sync, for executor)."""
        response = self._ec2.describe_spot_price_history(
            InstanceTypes=[instance_type],
            ProductDescriptions=["Linux/UNIX"],
            MaxResults=1,
        )
        if response.get("SpotPriceHistory"):
            return instance_type, float(response["SpotPriceHistory"][0]["SpotPrice"])
        return instance_type, None

    async def _refresh_spot_prices(self) -> None:
        """Refresh Spot prices from EC2 API (parallel requests)."""
        try:
            loop = asyncio.get_running_loop()
            instance_types = list(SPOT_PRICE_ESTIMATES.keys())

            with ThreadPoolExecutor(max_workers=len(instance_types)) as pool:
                futures = [
                    loop.run_in_executor(pool, self._fetch_single_spot_price, it)
                    for it in instance_types
                ]
                results = await asyncio.gather(*futures)

            for instance_type, spot_price in results:
                if spot_price is not None:
                    gpus = self._get_gpu_count(instance_type)
                    vcpus, memory = self._get_instance_specs(instance_type)

                    self._spot_prices[instance_type] = GPUPricing(
                        instance_type=instance_type,
                        spot_price_per_hour=spot_price,
                        on_demand_price_per_hour=ON_DEMAND_PRICES.get(
                            instance_type, 0.0
                        ),
                        gpus=gpus,
                        vcpus=vcpus,
                        memory_gb=memory,
                        region=self.region,
                    )

            self._last_price_fetch = datetime.now(timezone.utc)
            logger.debug(
                f"Refreshed Spot prices for {len(self._spot_prices)} instance types"
            )

        except ClientError as e:
            logger.warning(f"Failed to fetch Spot prices: {e}")
            # Use estimates on failure
            self._use_estimated_prices()

    def _use_estimated_prices(self) -> None:
        """Use estimated prices when API fails."""
        for instance_type, price in SPOT_PRICE_ESTIMATES.items():
            if instance_type not in self._spot_prices:
                gpus = self._get_gpu_count(instance_type)
                vcpus, memory = self._get_instance_specs(instance_type)

                self._spot_prices[instance_type] = GPUPricing(
                    instance_type=instance_type,
                    spot_price_per_hour=price,
                    on_demand_price_per_hour=ON_DEMAND_PRICES.get(instance_type, 0.0),
                    gpus=gpus,
                    vcpus=vcpus,
                    memory_gb=memory,
                    region=self.region,
                )

    def _get_gpu_count(self, instance_type: str) -> int:
        """Get GPU count for instance type."""
        gpu_counts = {
            "g4dn.xlarge": 1,
            "g4dn.2xlarge": 1,
            "g4dn.4xlarge": 1,
            "g4dn.8xlarge": 1,
            "g4dn.12xlarge": 4,
            "g4dn.16xlarge": 1,
        }
        return gpu_counts.get(instance_type, 1)

    def _get_instance_specs(self, instance_type: str) -> tuple[int, int]:
        """Get vCPU and memory for instance type."""
        specs = {
            "g4dn.xlarge": (4, 16),
            "g4dn.2xlarge": (8, 32),
            "g4dn.4xlarge": (16, 64),
            "g4dn.8xlarge": (32, 128),
            "g4dn.12xlarge": (48, 192),
            "g4dn.16xlarge": (64, 256),
        }
        return specs.get(instance_type, (4, 16))

    # =========================================================================
    # Job Cost Calculation
    # =========================================================================

    async def calculate_job_cost(
        self,
        duration_seconds: float,
        instance_type: str = "g4dn.xlarge",
        pricing_type: str = "spot",
    ) -> float:
        """
        Calculate cost for a job based on duration.

        Args:
            duration_seconds: Job duration in seconds
            instance_type: EC2 instance type used
            pricing_type: "spot" or "on_demand"

        Returns:
            Cost in USD
        """
        if pricing_type == "spot":
            price_per_hour = await self.get_current_spot_price(instance_type)
        else:
            price_per_hour = ON_DEMAND_PRICES.get(instance_type, 0.526)

        hours = duration_seconds / 3600.0
        cost = hours * price_per_hour

        return round(cost, 4)

    async def estimate_job_cost(
        self,
        job_type: str,
        priority: str,
        instance_type: str = "g4dn.xlarge",
        config: Optional[dict[str, Any]] = None,
    ) -> JobCostEstimate:
        """
        Estimate cost for a new job before submission.

        Args:
            job_type: Type of GPU job
            priority: Job priority
            instance_type: Requested instance type
            config: Job configuration

        Returns:
            Cost estimate with confidence
        """
        # Get typical duration for job type
        typical_durations = {
            "embedding_generation": 30,  # 30 minutes
            "vulnerability_training": 120,  # 2 hours
            "swe_rl_training": 180,  # 3 hours
            "memory_consolidation": 45,  # 45 minutes
            "local_inference": 60,  # 1 hour (continuous, estimate)
        }

        duration_minutes = typical_durations.get(job_type, 60)

        # Adjust based on config if available
        if config:
            # Check for size indicators
            if config.get("repository_size_mb", 0) > 1000:
                duration_minutes *= 1.5  # 50% longer for large repos
            if config.get("batch_size"):
                # Larger batches = longer runtime
                batch_factor = config["batch_size"] / 32
                duration_minutes *= min(2.0, max(0.5, batch_factor))

        # Calculate cost
        spot_price = await self.get_current_spot_price(instance_type)
        estimated_cost = (duration_minutes / 60.0) * spot_price

        # Confidence based on job type predictability
        confidence_map = {
            "embedding_generation": 0.85,
            "vulnerability_training": 0.70,
            "swe_rl_training": 0.65,
            "memory_consolidation": 0.80,
            "local_inference": 0.50,  # Continuous, hard to predict
        }
        confidence = confidence_map.get(job_type, 0.60)

        return JobCostEstimate(
            job_id="",  # Not yet created
            estimated_duration_minutes=duration_minutes,
            estimated_cost_usd=round(estimated_cost, 2),
            instance_type=instance_type,
            pricing_type="spot",
            confidence=confidence,
            breakdown={
                "compute": round(estimated_cost * 0.95, 2),
                "storage": round(estimated_cost * 0.03, 2),
                "network": round(estimated_cost * 0.02, 2),
            },
        )

    # =========================================================================
    # Cost Aggregation
    # =========================================================================

    async def get_cost_summary(
        self,
        organization_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> CostSummary:
        """
        Get cost summary for an organization over a time period.

        Args:
            organization_id: Organization ID
            start_date: Period start
            end_date: Period end

        Returns:
            Cost summary with breakdowns
        """
        try:
            # Query jobs for the organization in the time period
            response = self._jobs_table.query(
                KeyConditionExpression="PK = :pk",
                FilterExpression="created_at BETWEEN :start AND :end",
                ExpressionAttributeValues={
                    ":pk": f"ORG#{organization_id}",
                    ":start": start_date.isoformat(),
                    ":end": end_date.isoformat(),
                },
            )

            jobs = response.get("Items", [])

            # Aggregate costs
            total_cost = 0.0
            total_gpu_hours = 0.0
            by_job_type: dict[str, float] = {}
            by_priority: dict[str, float] = {}
            by_status: dict[str, float] = {}
            daily_costs: dict[str, float] = {}

            for job in jobs:
                cost = float(job.get("cost_usd", 0) or 0)
                total_cost += cost

                # Calculate GPU hours
                if job.get("started_at") and job.get("completed_at"):
                    start = datetime.fromisoformat(
                        job["started_at"].replace("Z", "+00:00")
                    )
                    end = datetime.fromisoformat(
                        job["completed_at"].replace("Z", "+00:00")
                    )
                    hours = (end - start).total_seconds() / 3600.0
                    total_gpu_hours += hours

                # By job type
                job_type = job.get("job_type", "unknown")
                by_job_type[job_type] = by_job_type.get(job_type, 0) + cost

                # By priority
                priority = job.get("priority", "normal")
                by_priority[priority] = by_priority.get(priority, 0) + cost

                # By status
                status = job.get("status", "unknown")
                by_status[status] = by_status.get(status, 0) + cost

                # Daily breakdown
                if job.get("created_at"):
                    day = job["created_at"][:10]  # YYYY-MM-DD
                    daily_costs[day] = daily_costs.get(day, 0) + cost

            jobs_count = len(jobs)
            avg_cost = total_cost / jobs_count if jobs_count > 0 else 0.0

            # Convert daily breakdown to list
            daily_breakdown = [
                {"date": date, "cost_usd": cost}
                for date, cost in sorted(daily_costs.items())
            ]

            return CostSummary(
                period_start=start_date,
                period_end=end_date,
                total_cost_usd=round(total_cost, 2),
                gpu_hours=round(total_gpu_hours, 2),
                jobs_count=jobs_count,
                avg_job_cost_usd=round(avg_cost, 2),
                by_job_type={k: round(v, 2) for k, v in by_job_type.items()},
                by_priority={k: round(v, 2) for k, v in by_priority.items()},
                by_status={k: round(v, 2) for k, v in by_status.items()},
                daily_breakdown=daily_breakdown,
            )

        except ClientError as e:
            logger.error(f"Failed to get cost summary: {e}")
            return CostSummary(
                period_start=start_date,
                period_end=end_date,
                total_cost_usd=0.0,
                gpu_hours=0.0,
                jobs_count=0,
                avg_job_cost_usd=0.0,
            )

    async def get_monthly_cost(
        self,
        organization_id: str,
        year: int,
        month: int,
    ) -> CostSummary:
        """
        Get cost summary for a specific month.

        Args:
            organization_id: Organization ID
            year: Year
            month: Month (1-12)

        Returns:
            Monthly cost summary
        """
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        return await self.get_cost_summary(organization_id, start_date, end_date)

    # =========================================================================
    # Budget Management
    # =========================================================================

    async def set_budget(
        self,
        organization_id: str,
        monthly_budget_usd: float,
        daily_budget_usd: Optional[float] = None,
        alert_threshold_percent: float = 80.0,
        hard_limit_enabled: bool = False,
    ) -> OrganizationBudget:
        """
        Set or update budget for an organization.

        Args:
            organization_id: Organization ID
            monthly_budget_usd: Monthly budget limit
            daily_budget_usd: Optional daily budget limit
            alert_threshold_percent: Alert when this % reached
            hard_limit_enabled: Block jobs when budget exceeded

        Returns:
            Updated budget configuration
        """
        now = datetime.now(timezone.utc)

        budget = OrganizationBudget(
            organization_id=organization_id,
            monthly_budget_usd=monthly_budget_usd,
            daily_budget_usd=daily_budget_usd,
            alert_threshold_percent=alert_threshold_percent,
            hard_limit_enabled=hard_limit_enabled,
            updated_at=now,
        )

        try:
            self._quotas_table.update_item(
                Key={
                    "PK": f"ORG#{organization_id}",
                    "SK": "BUDGET",
                },
                UpdateExpression=(
                    "SET monthly_budget_usd = :monthly, "
                    "daily_budget_usd = :daily, "
                    "alert_threshold_percent = :threshold, "
                    "hard_limit_enabled = :hard_limit, "
                    "updated_at = :updated"
                ),
                ExpressionAttributeValues={
                    ":monthly": Decimal(str(monthly_budget_usd)),
                    ":daily": (
                        Decimal(str(daily_budget_usd)) if daily_budget_usd else None
                    ),
                    ":threshold": Decimal(str(alert_threshold_percent)),
                    ":hard_limit": hard_limit_enabled,
                    ":updated": now.isoformat(),
                },
            )

            logger.info(
                f"Set budget for {organization_id}: "
                f"${monthly_budget_usd}/month, threshold={alert_threshold_percent}%"
            )

        except ClientError as e:
            logger.error(f"Failed to set budget: {e}")
            raise

        return budget

    async def get_budget(self, organization_id: str) -> Optional[OrganizationBudget]:
        """
        Get budget configuration for an organization.

        Args:
            organization_id: Organization ID

        Returns:
            Budget configuration or None if not set
        """
        try:
            response = self._quotas_table.get_item(
                Key={
                    "PK": f"ORG#{organization_id}",
                    "SK": "BUDGET",
                }
            )

            item = response.get("Item")
            if not item:
                return None

            return OrganizationBudget(
                organization_id=organization_id,
                monthly_budget_usd=float(item.get("monthly_budget_usd", 0)),
                daily_budget_usd=(
                    float(item["daily_budget_usd"])
                    if item.get("daily_budget_usd")
                    else None
                ),
                alert_threshold_percent=float(item.get("alert_threshold_percent", 80)),
                hard_limit_enabled=item.get("hard_limit_enabled", False),
                created_at=(
                    datetime.fromisoformat(item["created_at"])
                    if item.get("created_at")
                    else datetime.now(timezone.utc)
                ),
                updated_at=(
                    datetime.fromisoformat(item["updated_at"])
                    if item.get("updated_at")
                    else datetime.now(timezone.utc)
                ),
            )

        except ClientError as e:
            logger.error(f"Failed to get budget: {e}")
            return None

    async def check_budget(
        self,
        organization_id: str,
    ) -> tuple[bool, Optional[BudgetAlert]]:
        """
        Check budget status and generate alerts if needed.

        Args:
            organization_id: Organization ID

        Returns:
            Tuple of (within_budget, alert_if_any)
        """
        budget = await self.get_budget(organization_id)
        if not budget:
            return True, None  # No budget set

        # Get current month's costs
        now = datetime.now(timezone.utc)
        summary = await self.get_monthly_cost(organization_id, now.year, now.month)

        usage_percent = (summary.total_cost_usd / budget.monthly_budget_usd) * 100

        # Check if alert threshold exceeded
        if usage_percent >= budget.alert_threshold_percent:
            alert_type = (
                "threshold_exceeded" if usage_percent >= 100 else "threshold_warning"
            )

            # Calculate forecast
            days_elapsed = now.day
            days_in_month = 30  # Simplified
            daily_avg = summary.total_cost_usd / max(1, days_elapsed)
            forecast = daily_avg * days_in_month

            alert = BudgetAlert(
                organization_id=organization_id,
                alert_type=alert_type,
                current_usage_usd=summary.total_cost_usd,
                budget_limit_usd=budget.monthly_budget_usd,
                usage_percent=usage_percent,
                forecast_usd=round(forecast, 2),
                message=self._format_alert_message(
                    organization_id,
                    summary.total_cost_usd,
                    budget.monthly_budget_usd,
                    usage_percent,
                    forecast,
                ),
            )

            # Send alert notification
            await self._send_budget_alert(alert)

            within_budget = usage_percent < 100 or not budget.hard_limit_enabled
            return within_budget, alert

        # Check forecast warning (>90% of budget projected)
        days_elapsed = now.day
        days_in_month = 30
        if days_elapsed > 0:
            daily_avg = summary.total_cost_usd / days_elapsed
            forecast = daily_avg * days_in_month
            forecast_percent = (forecast / budget.monthly_budget_usd) * 100

            if (
                forecast_percent >= 90
                and usage_percent < budget.alert_threshold_percent
            ):
                alert = BudgetAlert(
                    organization_id=organization_id,
                    alert_type="forecast_warning",
                    current_usage_usd=summary.total_cost_usd,
                    budget_limit_usd=budget.monthly_budget_usd,
                    usage_percent=usage_percent,
                    forecast_usd=round(forecast, 2),
                    message=f"GPU budget forecast warning: Projected ${forecast:.2f} "
                    f"({forecast_percent:.0f}% of ${budget.monthly_budget_usd} budget)",
                )

                await self._send_budget_alert(alert)
                return True, alert

        return True, None

    def _format_alert_message(
        self,
        organization_id: str,
        current: float,
        limit: float,
        percent: float,
        forecast: float,
    ) -> str:
        """Format budget alert message."""
        if percent >= 100:
            return (
                f"GPU budget EXCEEDED for {organization_id}: "
                f"${current:.2f} spent ({percent:.0f}% of ${limit:.2f} budget). "
                f"End-of-month forecast: ${forecast:.2f}"
            )
        return (
            f"GPU budget WARNING for {organization_id}: "
            f"${current:.2f} spent ({percent:.0f}% of ${limit:.2f} budget). "
            f"End-of-month forecast: ${forecast:.2f}"
        )

    async def _send_budget_alert(self, alert: BudgetAlert) -> None:
        """Send budget alert via SNS."""
        if not self._alert_topic_arn:
            logger.warning("No alert topic configured, skipping notification")
            return

        try:
            self._sns.publish(
                TopicArn=self._alert_topic_arn,
                Subject=f"GPU Budget Alert: {alert.alert_type}",
                Message=alert.message,
                MessageAttributes={
                    "organization_id": {
                        "DataType": "String",
                        "StringValue": alert.organization_id,
                    },
                    "alert_type": {
                        "DataType": "String",
                        "StringValue": alert.alert_type,
                    },
                    "usage_percent": {
                        "DataType": "Number",
                        "StringValue": str(alert.usage_percent),
                    },
                },
            )
            logger.info(
                f"Sent budget alert for {alert.organization_id}: {alert.alert_type}"
            )

        except ClientError as e:
            logger.error(f"Failed to send budget alert: {e}")

    # =========================================================================
    # Cost Forecasting
    # =========================================================================

    async def forecast_end_of_month_cost(
        self,
        organization_id: str,
    ) -> dict[str, Any]:
        """
        Forecast end-of-month GPU cost based on current usage patterns.

        Args:
            organization_id: Organization ID

        Returns:
            Forecast with confidence intervals
        """
        now = datetime.now(timezone.utc)
        summary = await self.get_monthly_cost(organization_id, now.year, now.month)

        days_elapsed = now.day
        days_in_month = 30  # Simplified

        if days_elapsed == 0:
            return {
                "forecast_usd": 0.0,
                "confidence_low_usd": 0.0,
                "confidence_high_usd": 0.0,
                "daily_average_usd": 0.0,
                "days_elapsed": 0,
                "days_remaining": days_in_month,
            }

        daily_avg = summary.total_cost_usd / days_elapsed
        forecast = daily_avg * days_in_month

        # Calculate confidence intervals based on variance
        # Simple approach: ±20% for low confidence, ±10% for high confidence
        variance_factor = 0.15  # 15% variance
        confidence_low = forecast * (1 - variance_factor)
        confidence_high = forecast * (1 + variance_factor)

        return {
            "forecast_usd": round(forecast, 2),
            "confidence_low_usd": round(confidence_low, 2),
            "confidence_high_usd": round(confidence_high, 2),
            "daily_average_usd": round(daily_avg, 2),
            "days_elapsed": days_elapsed,
            "days_remaining": days_in_month - days_elapsed,
            "current_total_usd": summary.total_cost_usd,
            "jobs_count": summary.jobs_count,
        }
