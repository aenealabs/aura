"""
AWS Marketplace Integration Service.

Provides integration with AWS Marketplace for SaaS offerings:
- Customer subscription management via SNS notifications
- Usage metering for consumption-based billing
- Entitlement verification
- Contract management for annual subscriptions

AWS Marketplace SaaS Integration Flow:
1. Customer subscribes via AWS Marketplace
2. AWS sends SNS notification to our endpoint
3. We resolve customer registration token
4. We create/update customer subscription
5. We report usage via Metering Service API
"""

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class MarketplaceProductCode(str, Enum):
    """AWS Marketplace product codes for Aura offerings."""

    AURA_STARTER = "aura-starter-monthly"
    AURA_PROFESSIONAL = "aura-professional-monthly"
    AURA_ENTERPRISE = "aura-enterprise-monthly"
    AURA_ENTERPRISE_ANNUAL = "aura-enterprise-annual"
    AURA_GOVERNMENT = "aura-government-annual"


class SubscriptionAction(str, Enum):
    """SNS notification action types from AWS Marketplace."""

    SUBSCRIBE_SUCCESS = "subscribe-success"
    SUBSCRIBE_FAIL = "subscribe-fail"
    UNSUBSCRIBE_PENDING = "unsubscribe-pending"
    UNSUBSCRIBE_SUCCESS = "unsubscribe-success"
    ENTITLEMENT_UPDATED = "entitlement-updated"


class UsageDimension(str, Enum):
    """Metered usage dimensions for consumption billing."""

    DEVELOPERS = "Developers"
    LLM_TOKENS = "LLMTokens"
    AGENT_EXECUTIONS = "AgentExecutions"
    API_CALLS = "APICalls"
    STORAGE_GB = "StorageGB"
    GRAPH_NODES = "GraphNodes"


class EntitlementStatus(str, Enum):
    """Customer entitlement status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class MarketplaceCustomer:
    """AWS Marketplace customer record."""

    customer_id: str
    aws_customer_id: str
    product_code: str
    dimension: str
    entitlement_status: EntitlementStatus
    subscription_start: datetime
    subscription_end: Optional[datetime] = None
    aws_account_id: Optional[str] = None
    customer_email: Optional[str] = None
    company_name: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageRecord:
    """Metered usage record for AWS Marketplace."""

    record_id: str
    customer_id: str
    product_code: str
    dimension: UsageDimension
    quantity: int
    timestamp: datetime
    reported: bool = False
    report_id: Optional[str] = None
    reported_at: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class MeteringResult:
    """Result of usage metering submission."""

    success: bool
    metering_record_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EntitlementCheck:
    """Result of entitlement verification."""

    is_entitled: bool
    product_code: str
    dimension: str
    value: int = 0
    expiration: Optional[datetime] = None
    status: EntitlementStatus = EntitlementStatus.PENDING


# =============================================================================
# Marketplace Service
# =============================================================================


class MarketplaceService:
    """
    AWS Marketplace Integration Service.

    Handles all AWS Marketplace SaaS integration:
    - SNS subscription notifications
    - Customer registration resolution
    - Usage metering
    - Entitlement verification
    """

    def __init__(
        self,
        product_code: Optional[str] = None,
        region: str = "us-east-1",
        sns_topic_arn: Optional[str] = None,
    ):
        """
        Initialize Marketplace service.

        Args:
            product_code: AWS Marketplace product code
            region: AWS region for API calls
            sns_topic_arn: SNS topic ARN for subscription notifications
        """
        self.product_code = product_code or os.environ.get(
            "AWS_MARKETPLACE_PRODUCT_CODE", "aura-saas-prod"
        )
        self.region = region
        self.sns_topic_arn = sns_topic_arn or os.environ.get(
            "AWS_MARKETPLACE_SNS_TOPIC_ARN"
        )

        # In-memory storage (production would use DynamoDB)
        self._customers: Dict[str, MarketplaceCustomer] = {}
        self._usage_records: Dict[str, UsageRecord] = {}
        self._pending_usage: List[UsageRecord] = []

        # AWS clients (initialized lazily)
        self._metering_client = None
        self._entitlement_client = None

        # Configuration
        self.metering_batch_size = 25  # AWS limit
        self.metering_interval_hours = 1

        logger.info(f"MarketplaceService initialized for product: {self.product_code}")

    # -------------------------------------------------------------------------
    # AWS Client Initialization
    # -------------------------------------------------------------------------

    def _get_metering_client(self):
        """Get or create AWS Marketplace Metering client."""
        if self._metering_client is None:
            self._metering_client = boto3.client(
                "meteringmarketplace",
                region_name=self.region,
            )
        return self._metering_client

    def _get_entitlement_client(self):
        """Get or create AWS Marketplace Entitlement client."""
        if self._entitlement_client is None:
            self._entitlement_client = boto3.client(
                "marketplace-entitlement",
                region_name=self.region,
            )
        return self._entitlement_client

    # -------------------------------------------------------------------------
    # Customer Registration
    # -------------------------------------------------------------------------

    async def resolve_customer(
        self,
        registration_token: str,
    ) -> Optional[MarketplaceCustomer]:
        """
        Resolve customer from AWS Marketplace registration token.

        Called after customer completes subscription in AWS Marketplace.
        The registration token is provided via redirect URL.

        Args:
            registration_token: Token from AWS Marketplace redirect

        Returns:
            MarketplaceCustomer if resolution successful, None otherwise
        """
        try:
            client = self._get_metering_client()

            # Call AWS Marketplace to resolve the token
            response = client.resolve_customer(RegistrationToken=registration_token)

            aws_customer_id = response["CustomerIdentifier"]
            product_code = response["ProductCode"]
            aws_account_id = response.get("CustomerAWSAccountId")

            # Create internal customer record
            customer_id = str(uuid.uuid4())
            customer = MarketplaceCustomer(
                customer_id=customer_id,
                aws_customer_id=aws_customer_id,
                product_code=product_code,
                dimension="Base",
                entitlement_status=EntitlementStatus.ACTIVE,
                subscription_start=datetime.now(timezone.utc),
                aws_account_id=aws_account_id,
            )

            self._customers[customer_id] = customer
            logger.info(
                f"Resolved marketplace customer: {aws_customer_id} -> {customer_id}"
            )

            return customer

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Failed to resolve customer: {error_code} - {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error resolving customer: {e}")
            return None

    async def handle_sns_notification(
        self,
        message: Dict[str, Any],
        signature: Optional[str] = None,
    ) -> bool:
        """
        Handle SNS notification from AWS Marketplace.

        AWS Marketplace sends notifications for:
        - subscribe-success: Customer completed subscription
        - unsubscribe-pending: Customer initiated cancellation
        - unsubscribe-success: Subscription cancelled
        - entitlement-updated: Entitlements changed

        Args:
            message: SNS message payload
            signature: Optional message signature for verification

        Returns:
            True if notification handled successfully
        """
        try:
            action = message.get("action")
            aws_customer_id = message.get("customer-identifier")
            product_code = message.get("product-code")

            logger.info(
                f"Processing marketplace notification: {action} for {aws_customer_id}"
            )

            # Validate required fields
            if aws_customer_id is None:
                logger.error("Missing customer-identifier in notification")
                return False

            if action == SubscriptionAction.SUBSCRIBE_SUCCESS.value:
                if product_code is None:
                    logger.error("Missing product-code for subscribe notification")
                    return False
                return await self._handle_subscribe_success(
                    aws_customer_id, product_code, message
                )

            elif action == SubscriptionAction.UNSUBSCRIBE_PENDING.value:
                return await self._handle_unsubscribe_pending(aws_customer_id, message)

            elif action == SubscriptionAction.UNSUBSCRIBE_SUCCESS.value:
                return await self._handle_unsubscribe_success(aws_customer_id, message)

            elif action == SubscriptionAction.ENTITLEMENT_UPDATED.value:
                return await self._handle_entitlement_updated(aws_customer_id, message)

            else:
                logger.warning(f"Unknown marketplace action: {action}")
                return False

        except Exception as e:
            logger.error(f"Error handling SNS notification: {e}")
            return False

    async def _handle_subscribe_success(
        self,
        aws_customer_id: str,
        product_code: str,
        message: Dict[str, Any],
    ) -> bool:
        """Handle successful subscription notification."""
        # Find or create customer
        customer = self._find_customer_by_aws_id(aws_customer_id)

        if customer:
            # Update existing customer
            customer.entitlement_status = EntitlementStatus.ACTIVE
            customer.product_code = product_code
            customer.updated_at = datetime.now(timezone.utc)
        else:
            # Create new customer (will need registration token resolution)
            customer_id = str(uuid.uuid4())
            customer = MarketplaceCustomer(
                customer_id=customer_id,
                aws_customer_id=aws_customer_id,
                product_code=product_code,
                dimension="Base",
                entitlement_status=EntitlementStatus.PENDING,
                subscription_start=datetime.now(timezone.utc),
            )
            self._customers[customer_id] = customer

        logger.info(f"Subscription activated for {aws_customer_id}")
        return True

    async def _handle_unsubscribe_pending(
        self,
        aws_customer_id: str,
        message: Dict[str, Any],
    ) -> bool:
        """Handle pending cancellation notification."""
        customer = self._find_customer_by_aws_id(aws_customer_id)

        if customer:
            customer.entitlement_status = EntitlementStatus.SUSPENDED
            customer.updated_at = datetime.now(timezone.utc)
            logger.info(f"Subscription pending cancellation for {aws_customer_id}")
            return True

        logger.warning(f"Customer not found for cancellation: {aws_customer_id}")
        return False

    async def _handle_unsubscribe_success(
        self,
        aws_customer_id: str,
        message: Dict[str, Any],
    ) -> bool:
        """Handle successful cancellation notification."""
        customer = self._find_customer_by_aws_id(aws_customer_id)

        if customer:
            customer.entitlement_status = EntitlementStatus.CANCELLED
            customer.subscription_end = datetime.now(timezone.utc)
            customer.updated_at = datetime.now(timezone.utc)
            logger.info(f"Subscription cancelled for {aws_customer_id}")
            return True

        logger.warning(f"Customer not found for cancellation: {aws_customer_id}")
        return False

    async def _handle_entitlement_updated(
        self,
        aws_customer_id: str,
        message: Dict[str, Any],
    ) -> bool:
        """Handle entitlement update notification."""
        customer = self._find_customer_by_aws_id(aws_customer_id)

        if customer:
            # Refresh entitlements from AWS
            _entitlements = await self.check_entitlements(  # noqa: F841
                customer.customer_id
            )
            customer.updated_at = datetime.now(timezone.utc)
            logger.info(f"Entitlements updated for {aws_customer_id}")
            return True

        logger.warning(f"Customer not found for entitlement update: {aws_customer_id}")
        return False

    def _find_customer_by_aws_id(
        self, aws_customer_id: str
    ) -> Optional[MarketplaceCustomer]:
        """Find customer by AWS Marketplace customer ID."""
        for customer in self._customers.values():
            if customer.aws_customer_id == aws_customer_id:
                return customer
        return None

    # -------------------------------------------------------------------------
    # Usage Metering
    # -------------------------------------------------------------------------

    async def record_usage(
        self,
        customer_id: str,
        dimension: UsageDimension,
        quantity: int,
        timestamp: Optional[datetime] = None,
    ) -> UsageRecord:
        """
        Record usage for metered billing.

        Usage is batched and submitted hourly to AWS Marketplace.

        Args:
            customer_id: Internal customer ID
            dimension: Usage dimension (e.g., LLMTokens, AgentExecutions)
            quantity: Usage quantity
            timestamp: Optional timestamp (defaults to now)

        Returns:
            UsageRecord with pending status
        """
        customer = self._customers.get(customer_id)
        if not customer:
            raise ValueError(f"Customer not found: {customer_id}")

        if customer.entitlement_status != EntitlementStatus.ACTIVE:
            raise ValueError(
                f"Customer not active: {customer.entitlement_status.value}"
            )

        record_id = str(uuid.uuid4())
        record = UsageRecord(
            record_id=record_id,
            customer_id=customer_id,
            product_code=customer.product_code,
            dimension=dimension,
            quantity=quantity,
            timestamp=timestamp or datetime.now(timezone.utc),
        )

        self._usage_records[record_id] = record
        self._pending_usage.append(record)

        logger.debug(f"Recorded usage: {dimension.value}={quantity} for {customer_id}")

        return record

    async def submit_usage_batch(self) -> List[MeteringResult]:
        """
        Submit pending usage records to AWS Marketplace.

        Should be called periodically (e.g., hourly) to report usage.

        Returns:
            List of metering results for each submission
        """
        if not self._pending_usage:
            return []

        results = []
        client = self._get_metering_client()

        # Group by customer and dimension for batching
        usage_groups: Dict[str, List[UsageRecord]] = {}
        for record in self._pending_usage:
            key = f"{record.customer_id}:{record.dimension.value}"
            if key not in usage_groups:
                usage_groups[key] = []
            usage_groups[key].append(record)

        for key, records in usage_groups.items():
            customer_id, dimension = key.split(":", 1)
            customer = self._customers.get(customer_id)

            if not customer:
                continue

            # Aggregate quantity for the hour
            total_quantity = sum(r.quantity for r in records)
            timestamp = records[-1].timestamp  # Use latest timestamp

            try:
                response = client.meter_usage(
                    ProductCode=customer.product_code,
                    Timestamp=timestamp,
                    UsageDimension=dimension,
                    UsageQuantity=total_quantity,
                    DryRun=False,
                )

                metering_record_id = response.get("MeteringRecordId")

                result = MeteringResult(
                    success=True,
                    metering_record_id=metering_record_id,
                )

                # Mark records as reported
                for record in records:
                    record.reported = True
                    record.report_id = metering_record_id
                    record.reported_at = datetime.now(timezone.utc)

                logger.info(
                    f"Submitted usage: {dimension}={total_quantity} for {customer_id}"
                )

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_message = str(e)

                result = MeteringResult(
                    success=False,
                    error_code=error_code,
                    error_message=error_message,
                )

                # Mark records with error
                for record in records:
                    record.error_message = error_message

                logger.error(f"Failed to submit usage: {error_code} - {e}")

            results.append(result)

        # Clear pending (keep failed for retry)
        self._pending_usage = [r for r in self._pending_usage if not r.reported]

        return results

    async def batch_meter_usage(
        self,
        customer_id: str,
        usage_records: List[Dict[str, Any]],
    ) -> MeteringResult:
        """
        Submit batch usage records for a customer.

        Uses BatchMeterUsage API for efficiency.

        Args:
            customer_id: Internal customer ID
            usage_records: List of {dimension, quantity, timestamp}

        Returns:
            MeteringResult for the batch
        """
        customer = self._customers.get(customer_id)
        if not customer:
            return MeteringResult(
                success=False,
                error_code="CustomerNotFound",
                error_message=f"Customer not found: {customer_id}",
            )

        try:
            client = self._get_metering_client()

            # Format records for API
            formatted_records = []
            for record in usage_records[: self.metering_batch_size]:
                formatted_records.append(
                    {
                        "Timestamp": record.get(
                            "timestamp", datetime.now(timezone.utc)
                        ),
                        "CustomerIdentifier": customer.aws_customer_id,
                        "Dimension": record["dimension"],
                        "Quantity": record["quantity"],
                    }
                )

            response = client.batch_meter_usage(
                ProductCode=customer.product_code,
                UsageRecords=formatted_records,
            )

            _processed = len(response.get("Results", []))  # noqa: F841
            unprocessed = len(response.get("UnprocessedRecords", []))

            if unprocessed > 0:
                logger.warning(f"Batch metering: {unprocessed} records unprocessed")

            return MeteringResult(
                success=True,
                metering_record_id=f"batch-{uuid.uuid4()}",
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            return MeteringResult(
                success=False,
                error_code=error_code,
                error_message=str(e),
            )

    # -------------------------------------------------------------------------
    # Entitlement Management
    # -------------------------------------------------------------------------

    async def check_entitlements(
        self,
        customer_id: str,
    ) -> List[EntitlementCheck]:
        """
        Check customer entitlements from AWS Marketplace.

        Args:
            customer_id: Internal customer ID

        Returns:
            List of entitlement checks for each dimension
        """
        customer = self._customers.get(customer_id)
        if not customer:
            return []

        try:
            client = self._get_entitlement_client()

            response = client.get_entitlements(
                ProductCode=customer.product_code,
                Filter={"CUSTOMER_IDENTIFIER": [customer.aws_customer_id]},
            )

            entitlements = []
            for item in response.get("Entitlements", []):
                dimension = item.get("Dimension", "Base")
                value = item.get("Value", {})

                # Parse value based on type
                if "IntegerValue" in value:
                    quantity = value["IntegerValue"]
                elif "BooleanValue" in value:
                    quantity = 1 if value["BooleanValue"] else 0
                else:
                    quantity = 0

                expiration = item.get("ExpirationDate")
                if expiration:
                    expiration = datetime.fromisoformat(
                        expiration.replace("Z", "+00:00")
                    )

                entitlements.append(
                    EntitlementCheck(
                        is_entitled=True,
                        product_code=customer.product_code,
                        dimension=dimension,
                        value=quantity,
                        expiration=expiration,
                        status=EntitlementStatus.ACTIVE,
                    )
                )

            return entitlements

        except ClientError as e:
            logger.error(f"Failed to check entitlements: {e}")
            return [
                EntitlementCheck(
                    is_entitled=False,
                    product_code=customer.product_code,
                    dimension="Base",
                    status=EntitlementStatus.PENDING,
                )
            ]

    async def verify_entitlement(
        self,
        customer_id: str,
        dimension: str = "Base",
    ) -> bool:
        """
        Quick entitlement verification for API access control.

        Args:
            customer_id: Internal customer ID
            dimension: Entitlement dimension to check

        Returns:
            True if customer is entitled
        """
        customer = self._customers.get(customer_id)
        if not customer:
            return False

        if customer.entitlement_status != EntitlementStatus.ACTIVE:
            return False

        # Check expiration
        if customer.subscription_end:
            if customer.subscription_end < datetime.now(timezone.utc):
                return False

        # For detailed checks, call AWS API
        entitlements = await self.check_entitlements(customer_id)
        for ent in entitlements:
            if ent.dimension == dimension and ent.is_entitled:
                return True

        return len(entitlements) > 0

    # -------------------------------------------------------------------------
    # Customer Management
    # -------------------------------------------------------------------------

    async def get_customer(
        self,
        customer_id: str,
    ) -> Optional[MarketplaceCustomer]:
        """Get customer by internal ID."""
        return self._customers.get(customer_id)

    async def get_customer_by_aws_id(
        self,
        aws_customer_id: str,
    ) -> Optional[MarketplaceCustomer]:
        """Get customer by AWS Marketplace customer ID."""
        return self._find_customer_by_aws_id(aws_customer_id)

    async def list_customers(
        self,
        status: Optional[EntitlementStatus] = None,
        limit: int = 100,
    ) -> List[MarketplaceCustomer]:
        """
        List marketplace customers.

        Args:
            status: Optional status filter
            limit: Maximum customers to return

        Returns:
            List of matching customers
        """
        customers = list(self._customers.values())

        if status:
            customers = [c for c in customers if c.entitlement_status == status]

        customers.sort(key=lambda c: c.created_at, reverse=True)
        return customers[:limit]

    async def update_customer_info(
        self,
        customer_id: str,
        email: Optional[str] = None,
        company_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[MarketplaceCustomer]:
        """
        Update customer information.

        Args:
            customer_id: Internal customer ID
            email: Customer email
            company_name: Company name
            metadata: Additional metadata

        Returns:
            Updated customer or None
        """
        customer = self._customers.get(customer_id)
        if not customer:
            return None

        if email:
            customer.customer_email = email
        if company_name:
            customer.company_name = company_name
        if metadata:
            customer.metadata.update(metadata)

        customer.updated_at = datetime.now(timezone.utc)
        return customer

    # -------------------------------------------------------------------------
    # Reporting and Analytics
    # -------------------------------------------------------------------------

    async def get_usage_summary(
        self,
        customer_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get usage summary for a customer.

        Args:
            customer_id: Internal customer ID
            days: Days of history

        Returns:
            Usage summary by dimension
        """
        customer = self._customers.get(customer_id)
        if not customer:
            return {}

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Aggregate by dimension
        by_dimension: Dict[str, int] = {}
        for record in self._usage_records.values():
            if record.customer_id != customer_id:
                continue
            if record.timestamp < cutoff:
                continue

            dim = record.dimension.value
            by_dimension[dim] = by_dimension.get(dim, 0) + record.quantity

        return {
            "customer_id": customer_id,
            "product_code": customer.product_code,
            "period_days": days,
            "usage_by_dimension": by_dimension,
            "total_records": len(
                [
                    r
                    for r in self._usage_records.values()
                    if r.customer_id == customer_id
                ]
            ),
        }

    async def get_revenue_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get revenue report across all customers.

        Args:
            start_date: Report start date
            end_date: Report end date

        Returns:
            Revenue report with breakdown
        """
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        active_customers = len(
            [
                c
                for c in self._customers.values()
                if c.entitlement_status == EntitlementStatus.ACTIVE
            ]
        )

        by_product: Dict[str, int] = {}
        for customer in self._customers.values():
            by_product[customer.product_code] = (
                by_product.get(customer.product_code, 0) + 1
            )

        total_usage: Dict[str, int] = {}
        for record in self._usage_records.values():
            if record.timestamp < start_date or record.timestamp > end_date:
                continue
            dim = record.dimension.value
            total_usage[dim] = total_usage.get(dim, 0) + record.quantity

        return {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_customers": len(self._customers),
            "active_customers": active_customers,
            "customers_by_product": by_product,
            "usage_by_dimension": total_usage,
        }


# =============================================================================
# Service Factory
# =============================================================================

_marketplace_service: Optional[MarketplaceService] = None


def get_marketplace_service() -> MarketplaceService:
    """Get or create the marketplace service singleton."""
    global _marketplace_service
    if _marketplace_service is None:
        _marketplace_service = MarketplaceService()
    return _marketplace_service


def reset_marketplace_service() -> None:
    """Reset the marketplace service (for testing)."""
    global _marketplace_service
    _marketplace_service = None
