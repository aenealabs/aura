"""
Tests for AWS Marketplace Integration Service.

Validates AWS Marketplace SaaS integration:
- Customer subscription management via SNS notifications
- Usage metering for consumption-based billing
- Entitlement verification
- Contract management for annual subscriptions
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.services.marketplace_service import (
    EntitlementCheck,
    EntitlementStatus,
    MarketplaceCustomer,
    MarketplaceProductCode,
    MarketplaceService,
    SubscriptionAction,
    UsageDimension,
    get_marketplace_service,
    reset_marketplace_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def marketplace_service():
    """Create a fresh marketplace service for each test."""
    reset_marketplace_service()
    return MarketplaceService(
        product_code="aura-test-product",
        region="us-east-1",
    )


@pytest.fixture
def customer_id():
    """Sample customer ID."""
    return str(uuid.uuid4())


@pytest.fixture
def aws_customer_id():
    """Sample AWS Marketplace customer ID."""
    return f"aws-cust-{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def active_customer(marketplace_service, aws_customer_id):
    """Create an active marketplace customer for testing."""
    customer_id = str(uuid.uuid4())
    customer = MarketplaceCustomer(
        customer_id=customer_id,
        aws_customer_id=aws_customer_id,
        product_code="aura-professional-monthly",
        dimension="Base",
        entitlement_status=EntitlementStatus.ACTIVE,
        subscription_start=datetime.now(timezone.utc),
    )
    marketplace_service._customers[customer_id] = customer
    return customer


# =============================================================================
# Customer Registration Tests
# =============================================================================


class TestCustomerRegistration:
    """Tests for customer registration and resolution."""

    @pytest.mark.asyncio
    async def test_resolve_customer_success(self, marketplace_service):
        """Test successful customer resolution from registration token."""
        with patch.object(marketplace_service, "_get_metering_client") as mock_client:
            mock_client.return_value.resolve_customer.return_value = {
                "CustomerIdentifier": "aws-cust-12345",
                "ProductCode": "aura-professional-monthly",
                "CustomerAWSAccountId": "123456789012",
            }

            customer = await marketplace_service.resolve_customer("test-token")

            assert customer is not None
            assert customer.aws_customer_id == "aws-cust-12345"
            assert customer.product_code == "aura-professional-monthly"
            assert customer.aws_account_id == "123456789012"
            assert customer.entitlement_status == EntitlementStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_resolve_customer_error(self, marketplace_service):
        """Test customer resolution with AWS API error."""
        from botocore.exceptions import ClientError

        with patch.object(marketplace_service, "_get_metering_client") as mock_client:
            mock_client.return_value.resolve_customer.side_effect = ClientError(
                {
                    "Error": {
                        "Code": "InvalidTokenException",
                        "Message": "Invalid token",
                    }
                },
                "ResolveCustomer",
            )

            customer = await marketplace_service.resolve_customer("invalid-token")

            assert customer is None

    @pytest.mark.asyncio
    async def test_resolve_customer_unexpected_error(self, marketplace_service):
        """Test customer resolution with unexpected error."""
        with patch.object(marketplace_service, "_get_metering_client") as mock_client:
            mock_client.return_value.resolve_customer.side_effect = Exception(
                "Unexpected error"
            )

            customer = await marketplace_service.resolve_customer("test-token")

            assert customer is None


# =============================================================================
# SNS Notification Handling Tests
# =============================================================================


class TestSNSNotifications:
    """Tests for SNS notification handling."""

    @pytest.mark.asyncio
    async def test_handle_subscribe_success(self, marketplace_service):
        """Test handling successful subscription notification."""
        message = {
            "action": "subscribe-success",
            "customer-identifier": "aws-cust-new",
            "product-code": "aura-enterprise-monthly",
        }

        result = await marketplace_service.handle_sns_notification(message)

        assert result is True
        # Customer should be created with PENDING status
        customer = marketplace_service._find_customer_by_aws_id("aws-cust-new")
        assert customer is not None
        assert customer.product_code == "aura-enterprise-monthly"

    @pytest.mark.asyncio
    async def test_handle_subscribe_success_existing_customer(
        self, marketplace_service, active_customer
    ):
        """Test subscription notification for existing customer."""
        message = {
            "action": "subscribe-success",
            "customer-identifier": active_customer.aws_customer_id,
            "product-code": "aura-enterprise-annual",
        }

        result = await marketplace_service.handle_sns_notification(message)

        assert result is True
        # Customer should be updated
        customer = marketplace_service._find_customer_by_aws_id(
            active_customer.aws_customer_id
        )
        assert customer.product_code == "aura-enterprise-annual"
        assert customer.entitlement_status == EntitlementStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_handle_unsubscribe_pending(
        self, marketplace_service, active_customer
    ):
        """Test handling pending cancellation notification."""
        message = {
            "action": "unsubscribe-pending",
            "customer-identifier": active_customer.aws_customer_id,
            "product-code": active_customer.product_code,
        }

        result = await marketplace_service.handle_sns_notification(message)

        assert result is True
        customer = marketplace_service._find_customer_by_aws_id(
            active_customer.aws_customer_id
        )
        assert customer.entitlement_status == EntitlementStatus.SUSPENDED

    @pytest.mark.asyncio
    async def test_handle_unsubscribe_pending_unknown_customer(
        self, marketplace_service
    ):
        """Test cancellation for unknown customer."""
        message = {
            "action": "unsubscribe-pending",
            "customer-identifier": "aws-cust-unknown",
            "product-code": "aura-test",
        }

        result = await marketplace_service.handle_sns_notification(message)

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_unsubscribe_success(
        self, marketplace_service, active_customer
    ):
        """Test handling successful cancellation notification."""
        message = {
            "action": "unsubscribe-success",
            "customer-identifier": active_customer.aws_customer_id,
            "product-code": active_customer.product_code,
        }

        result = await marketplace_service.handle_sns_notification(message)

        assert result is True
        customer = marketplace_service._find_customer_by_aws_id(
            active_customer.aws_customer_id
        )
        assert customer.entitlement_status == EntitlementStatus.CANCELLED
        assert customer.subscription_end is not None

    @pytest.mark.asyncio
    async def test_handle_entitlement_updated(
        self, marketplace_service, active_customer
    ):
        """Test handling entitlement update notification."""
        with patch.object(
            marketplace_service, "check_entitlements", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = [
                EntitlementCheck(
                    is_entitled=True,
                    product_code="aura-professional-monthly",
                    dimension="Base",
                    value=100,
                    status=EntitlementStatus.ACTIVE,
                )
            ]

            message = {
                "action": "entitlement-updated",
                "customer-identifier": active_customer.aws_customer_id,
                "product-code": active_customer.product_code,
            }

            result = await marketplace_service.handle_sns_notification(message)

            assert result is True
            mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_unknown_action(self, marketplace_service):
        """Test handling unknown action type."""
        message = {
            "action": "unknown-action",
            "customer-identifier": "aws-cust-123",
            "product-code": "aura-test",
        }

        result = await marketplace_service.handle_sns_notification(message)

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_notification_exception(self, marketplace_service):
        """Test notification handling with exception."""
        # Invalid message format
        result = await marketplace_service.handle_sns_notification(None)

        assert result is False


# =============================================================================
# Usage Metering Tests
# =============================================================================


class TestUsageMetering:
    """Tests for usage recording and metering."""

    @pytest.mark.asyncio
    async def test_record_usage(self, marketplace_service, active_customer):
        """Test recording usage for a customer."""
        record = await marketplace_service.record_usage(
            customer_id=active_customer.customer_id,
            dimension=UsageDimension.LLM_TOKENS,
            quantity=50000,
        )

        assert record.record_id is not None
        assert record.customer_id == active_customer.customer_id
        assert record.dimension == UsageDimension.LLM_TOKENS
        assert record.quantity == 50000
        assert record.reported is False

    @pytest.mark.asyncio
    async def test_record_usage_with_timestamp(
        self, marketplace_service, active_customer
    ):
        """Test recording usage with custom timestamp."""
        custom_time = datetime.now(timezone.utc) - timedelta(hours=1)

        record = await marketplace_service.record_usage(
            customer_id=active_customer.customer_id,
            dimension=UsageDimension.AGENT_EXECUTIONS,
            quantity=100,
            timestamp=custom_time,
        )

        assert record.timestamp == custom_time

    @pytest.mark.asyncio
    async def test_record_usage_customer_not_found(self, marketplace_service):
        """Test usage recording for non-existent customer."""
        with pytest.raises(ValueError, match="Customer not found"):
            await marketplace_service.record_usage(
                customer_id="nonexistent",
                dimension=UsageDimension.LLM_TOKENS,
                quantity=1000,
            )

    @pytest.mark.asyncio
    async def test_record_usage_inactive_customer(
        self, marketplace_service, active_customer
    ):
        """Test usage recording for inactive customer."""
        active_customer.entitlement_status = EntitlementStatus.SUSPENDED

        with pytest.raises(ValueError, match="Customer not active"):
            await marketplace_service.record_usage(
                customer_id=active_customer.customer_id,
                dimension=UsageDimension.LLM_TOKENS,
                quantity=1000,
            )

    @pytest.mark.asyncio
    async def test_submit_usage_batch(self, marketplace_service, active_customer):
        """Test submitting usage batch to AWS Marketplace."""
        # Record some usage
        await marketplace_service.record_usage(
            customer_id=active_customer.customer_id,
            dimension=UsageDimension.LLM_TOKENS,
            quantity=10000,
        )
        await marketplace_service.record_usage(
            customer_id=active_customer.customer_id,
            dimension=UsageDimension.LLM_TOKENS,
            quantity=20000,
        )

        with patch.object(marketplace_service, "_get_metering_client") as mock_client:
            mock_client.return_value.meter_usage.return_value = {
                "MeteringRecordId": "meter-123",
            }

            results = await marketplace_service.submit_usage_batch()

            assert len(results) >= 1
            assert results[0].success is True
            assert results[0].metering_record_id == "meter-123"

    @pytest.mark.asyncio
    async def test_submit_usage_batch_empty(self, marketplace_service):
        """Test submitting empty usage batch."""
        results = await marketplace_service.submit_usage_batch()
        assert results == []

    @pytest.mark.asyncio
    async def test_submit_usage_batch_error(self, marketplace_service, active_customer):
        """Test usage batch submission with AWS error."""
        from botocore.exceptions import ClientError

        await marketplace_service.record_usage(
            customer_id=active_customer.customer_id,
            dimension=UsageDimension.API_CALLS,
            quantity=100,
        )

        with patch.object(marketplace_service, "_get_metering_client") as mock_client:
            mock_client.return_value.meter_usage.side_effect = ClientError(
                {
                    "Error": {
                        "Code": "InvalidProductCodeException",
                        "Message": "Invalid",
                    }
                },
                "MeterUsage",
            )

            results = await marketplace_service.submit_usage_batch()

            assert len(results) >= 1
            assert results[0].success is False
            assert results[0].error_code == "InvalidProductCodeException"

    @pytest.mark.asyncio
    async def test_batch_meter_usage(self, marketplace_service, active_customer):
        """Test batch usage metering."""
        usage_records = [
            {"dimension": "LLMTokens", "quantity": 10000},
            {"dimension": "AgentExecutions", "quantity": 50},
        ]

        with patch.object(marketplace_service, "_get_metering_client") as mock_client:
            mock_client.return_value.batch_meter_usage.return_value = {
                "Results": [
                    {"MeteringRecordId": "batch-1"},
                    {"MeteringRecordId": "batch-2"},
                ],
                "UnprocessedRecords": [],
            }

            result = await marketplace_service.batch_meter_usage(
                customer_id=active_customer.customer_id,
                usage_records=usage_records,
            )

            assert result.success is True

    @pytest.mark.asyncio
    async def test_batch_meter_usage_customer_not_found(self, marketplace_service):
        """Test batch metering for non-existent customer."""
        result = await marketplace_service.batch_meter_usage(
            customer_id="nonexistent",
            usage_records=[{"dimension": "LLMTokens", "quantity": 100}],
        )

        assert result.success is False
        assert result.error_code == "CustomerNotFound"

    @pytest.mark.asyncio
    async def test_batch_meter_usage_partial_failure(
        self, marketplace_service, active_customer
    ):
        """Test batch metering with partial failure."""
        with patch.object(marketplace_service, "_get_metering_client") as mock_client:
            mock_client.return_value.batch_meter_usage.return_value = {
                "Results": [{"MeteringRecordId": "batch-1"}],
                "UnprocessedRecords": [
                    {"Dimension": "AgentExecutions", "Quantity": 50}
                ],
            }

            result = await marketplace_service.batch_meter_usage(
                customer_id=active_customer.customer_id,
                usage_records=[
                    {"dimension": "LLMTokens", "quantity": 10000},
                    {"dimension": "AgentExecutions", "quantity": 50},
                ],
            )

            # Should still succeed but log warning
            assert result.success is True


# =============================================================================
# Entitlement Management Tests
# =============================================================================


class TestEntitlementManagement:
    """Tests for entitlement checking and verification."""

    @pytest.mark.asyncio
    async def test_check_entitlements(self, marketplace_service, active_customer):
        """Test checking entitlements from AWS Marketplace."""
        with patch.object(
            marketplace_service, "_get_entitlement_client"
        ) as mock_client:
            mock_client.return_value.get_entitlements.return_value = {
                "Entitlements": [
                    {
                        "Dimension": "Developers",
                        "Value": {"IntegerValue": 100},
                        "ExpirationDate": "2025-12-31T23:59:59Z",
                    },
                    {
                        "Dimension": "Base",
                        "Value": {"BooleanValue": True},
                    },
                ],
            }

            entitlements = await marketplace_service.check_entitlements(
                active_customer.customer_id
            )

            assert len(entitlements) == 2
            assert entitlements[0].dimension == "Developers"
            assert entitlements[0].value == 100
            assert entitlements[0].is_entitled is True

    @pytest.mark.asyncio
    async def test_check_entitlements_customer_not_found(self, marketplace_service):
        """Test checking entitlements for non-existent customer."""
        entitlements = await marketplace_service.check_entitlements("nonexistent")
        assert entitlements == []

    @pytest.mark.asyncio
    async def test_check_entitlements_error(self, marketplace_service, active_customer):
        """Test entitlement check with AWS error."""
        from botocore.exceptions import ClientError

        with patch.object(
            marketplace_service, "_get_entitlement_client"
        ) as mock_client:
            mock_client.return_value.get_entitlements.side_effect = ClientError(
                {"Error": {"Code": "InvalidParameterException", "Message": "Invalid"}},
                "GetEntitlements",
            )

            entitlements = await marketplace_service.check_entitlements(
                active_customer.customer_id
            )

            assert len(entitlements) == 1
            assert entitlements[0].is_entitled is False
            assert entitlements[0].status == EntitlementStatus.PENDING

    @pytest.mark.asyncio
    async def test_verify_entitlement_active_customer(
        self, marketplace_service, active_customer
    ):
        """Test entitlement verification for active customer."""
        with patch.object(
            marketplace_service, "check_entitlements", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = [
                EntitlementCheck(
                    is_entitled=True,
                    product_code="aura-professional-monthly",
                    dimension="Base",
                    status=EntitlementStatus.ACTIVE,
                )
            ]

            is_entitled = await marketplace_service.verify_entitlement(
                customer_id=active_customer.customer_id,
                dimension="Base",
            )

            assert is_entitled is True

    @pytest.mark.asyncio
    async def test_verify_entitlement_inactive_customer(
        self, marketplace_service, active_customer
    ):
        """Test entitlement verification for inactive customer."""
        active_customer.entitlement_status = EntitlementStatus.CANCELLED

        is_entitled = await marketplace_service.verify_entitlement(
            customer_id=active_customer.customer_id,
            dimension="Base",
        )

        assert is_entitled is False

    @pytest.mark.asyncio
    async def test_verify_entitlement_expired_customer(
        self, marketplace_service, active_customer
    ):
        """Test entitlement verification for expired customer."""
        active_customer.subscription_end = datetime.now(timezone.utc) - timedelta(
            days=1
        )

        is_entitled = await marketplace_service.verify_entitlement(
            customer_id=active_customer.customer_id,
            dimension="Base",
        )

        assert is_entitled is False

    @pytest.mark.asyncio
    async def test_verify_entitlement_customer_not_found(self, marketplace_service):
        """Test entitlement verification for non-existent customer."""
        is_entitled = await marketplace_service.verify_entitlement(
            customer_id="nonexistent",
            dimension="Base",
        )

        assert is_entitled is False


# =============================================================================
# Customer Management Tests
# =============================================================================


class TestCustomerManagement:
    """Tests for customer CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_customer(self, marketplace_service, active_customer):
        """Test getting customer by internal ID."""
        customer = await marketplace_service.get_customer(active_customer.customer_id)

        assert customer is not None
        assert customer.customer_id == active_customer.customer_id

    @pytest.mark.asyncio
    async def test_get_customer_not_found(self, marketplace_service):
        """Test getting non-existent customer."""
        customer = await marketplace_service.get_customer("nonexistent")
        assert customer is None

    @pytest.mark.asyncio
    async def test_get_customer_by_aws_id(self, marketplace_service, active_customer):
        """Test getting customer by AWS Marketplace ID."""
        customer = await marketplace_service.get_customer_by_aws_id(
            active_customer.aws_customer_id
        )

        assert customer is not None
        assert customer.aws_customer_id == active_customer.aws_customer_id

    @pytest.mark.asyncio
    async def test_get_customer_by_aws_id_not_found(self, marketplace_service):
        """Test getting non-existent customer by AWS ID."""
        customer = await marketplace_service.get_customer_by_aws_id("aws-nonexistent")
        assert customer is None

    @pytest.mark.asyncio
    async def test_list_customers(self, marketplace_service, active_customer):
        """Test listing all customers."""
        # Add another customer
        another = MarketplaceCustomer(
            customer_id=str(uuid.uuid4()),
            aws_customer_id="aws-another",
            product_code="aura-starter-monthly",
            dimension="Base",
            entitlement_status=EntitlementStatus.ACTIVE,
            subscription_start=datetime.now(timezone.utc),
        )
        marketplace_service._customers[another.customer_id] = another

        customers = await marketplace_service.list_customers()

        assert len(customers) == 2

    @pytest.mark.asyncio
    async def test_list_customers_filter_by_status(
        self, marketplace_service, active_customer
    ):
        """Test listing customers filtered by status."""
        # Add a cancelled customer
        cancelled = MarketplaceCustomer(
            customer_id=str(uuid.uuid4()),
            aws_customer_id="aws-cancelled",
            product_code="aura-starter-monthly",
            dimension="Base",
            entitlement_status=EntitlementStatus.CANCELLED,
            subscription_start=datetime.now(timezone.utc),
        )
        marketplace_service._customers[cancelled.customer_id] = cancelled

        active_customers = await marketplace_service.list_customers(
            status=EntitlementStatus.ACTIVE
        )

        assert len(active_customers) == 1
        assert active_customers[0].entitlement_status == EntitlementStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_list_customers_limit(self, marketplace_service):
        """Test customer listing with limit."""
        # Add several customers
        for i in range(5):
            customer = MarketplaceCustomer(
                customer_id=str(uuid.uuid4()),
                aws_customer_id=f"aws-cust-{i}",
                product_code="aura-starter-monthly",
                dimension="Base",
                entitlement_status=EntitlementStatus.ACTIVE,
                subscription_start=datetime.now(timezone.utc),
            )
            marketplace_service._customers[customer.customer_id] = customer

        customers = await marketplace_service.list_customers(limit=3)

        assert len(customers) == 3

    @pytest.mark.asyncio
    async def test_update_customer_info(self, marketplace_service, active_customer):
        """Test updating customer information."""
        updated = await marketplace_service.update_customer_info(
            customer_id=active_customer.customer_id,
            email="test@example.com",
            company_name="Test Corp",
            metadata={"tier": "enterprise"},
        )

        assert updated is not None
        assert updated.customer_email == "test@example.com"
        assert updated.company_name == "Test Corp"
        assert updated.metadata["tier"] == "enterprise"

    @pytest.mark.asyncio
    async def test_update_customer_info_not_found(self, marketplace_service):
        """Test updating non-existent customer."""
        result = await marketplace_service.update_customer_info(
            customer_id="nonexistent",
            email="test@example.com",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_update_customer_partial(self, marketplace_service, active_customer):
        """Test partial customer update."""
        updated = await marketplace_service.update_customer_info(
            customer_id=active_customer.customer_id,
            email="new@example.com",
        )

        assert updated.customer_email == "new@example.com"
        # Other fields should remain unchanged


# =============================================================================
# Reporting and Analytics Tests
# =============================================================================


class TestReporting:
    """Tests for usage reporting and analytics."""

    @pytest.mark.asyncio
    async def test_get_usage_summary(self, marketplace_service, active_customer):
        """Test getting usage summary for a customer."""
        # Record some usage
        await marketplace_service.record_usage(
            customer_id=active_customer.customer_id,
            dimension=UsageDimension.LLM_TOKENS,
            quantity=50000,
        )
        await marketplace_service.record_usage(
            customer_id=active_customer.customer_id,
            dimension=UsageDimension.AGENT_EXECUTIONS,
            quantity=100,
        )

        summary = await marketplace_service.get_usage_summary(
            customer_id=active_customer.customer_id,
            days=30,
        )

        assert summary["customer_id"] == active_customer.customer_id
        assert summary["product_code"] == active_customer.product_code
        assert "LLMTokens" in summary["usage_by_dimension"]
        assert "AgentExecutions" in summary["usage_by_dimension"]
        assert summary["usage_by_dimension"]["LLMTokens"] == 50000

    @pytest.mark.asyncio
    async def test_get_usage_summary_customer_not_found(self, marketplace_service):
        """Test usage summary for non-existent customer."""
        summary = await marketplace_service.get_usage_summary(
            customer_id="nonexistent",
            days=30,
        )

        assert summary == {}

    @pytest.mark.asyncio
    async def test_get_revenue_report(self, marketplace_service, active_customer):
        """Test getting revenue report."""
        # Add some usage
        await marketplace_service.record_usage(
            customer_id=active_customer.customer_id,
            dimension=UsageDimension.LLM_TOKENS,
            quantity=100000,
        )

        report = await marketplace_service.get_revenue_report()

        assert "total_customers" in report
        assert "active_customers" in report
        assert "customers_by_product" in report
        assert "usage_by_dimension" in report
        assert report["total_customers"] >= 1
        assert report["active_customers"] >= 1

    @pytest.mark.asyncio
    async def test_get_revenue_report_custom_dates(self, marketplace_service):
        """Test revenue report with custom date range."""
        start_date = datetime.now(timezone.utc) - timedelta(days=60)
        end_date = datetime.now(timezone.utc) - timedelta(days=30)

        report = await marketplace_service.get_revenue_report(
            start_date=start_date,
            end_date=end_date,
        )

        assert report["period_start"] == start_date.isoformat()
        assert report["period_end"] == end_date.isoformat()


# =============================================================================
# Singleton Tests
# =============================================================================


class TestMarketplaceSingleton:
    """Tests for singleton pattern."""

    def test_get_marketplace_service(self):
        """Test getting marketplace service singleton."""
        reset_marketplace_service()
        service = get_marketplace_service()

        assert service is not None
        assert isinstance(service, MarketplaceService)

    def test_singleton_returns_same_instance(self):
        """Test that singleton returns same instance."""
        reset_marketplace_service()
        service1 = get_marketplace_service()
        service2 = get_marketplace_service()

        assert service1 is service2

    def test_reset_marketplace_service(self):
        """Test resetting the singleton."""
        reset_marketplace_service()
        service1 = get_marketplace_service()

        reset_marketplace_service()
        service2 = get_marketplace_service()

        assert service1 is not service2


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_find_customer_by_aws_id_empty_list(self, marketplace_service):
        """Test finding customer when no customers exist."""
        customer = marketplace_service._find_customer_by_aws_id("aws-nonexistent")
        assert customer is None

    @pytest.mark.asyncio
    async def test_all_usage_dimensions(self, marketplace_service, active_customer):
        """Test recording usage for all dimension types."""
        dimensions = [
            UsageDimension.DEVELOPERS,
            UsageDimension.LLM_TOKENS,
            UsageDimension.AGENT_EXECUTIONS,
            UsageDimension.API_CALLS,
            UsageDimension.STORAGE_GB,
            UsageDimension.GRAPH_NODES,
        ]

        for dimension in dimensions:
            record = await marketplace_service.record_usage(
                customer_id=active_customer.customer_id,
                dimension=dimension,
                quantity=100,
            )
            assert record.dimension == dimension

    @pytest.mark.asyncio
    async def test_metering_batch_size_limit(
        self, marketplace_service, active_customer
    ):
        """Test that batch metering respects size limits."""
        # Create more records than batch size
        usage_records = [
            {"dimension": "LLMTokens", "quantity": i * 100}
            for i in range(30)  # More than batch size of 25
        ]

        with patch.object(marketplace_service, "_get_metering_client") as mock_client:
            mock_client.return_value.batch_meter_usage.return_value = {
                "Results": [],
                "UnprocessedRecords": [],
            }

            await marketplace_service.batch_meter_usage(
                customer_id=active_customer.customer_id,
                usage_records=usage_records,
            )

            # Check that only batch_size records were sent
            call_args = mock_client.return_value.batch_meter_usage.call_args
            sent_records = call_args.kwargs.get("UsageRecords", [])
            assert len(sent_records) <= marketplace_service.metering_batch_size

    def test_product_codes_enum(self):
        """Test all product codes are defined."""
        codes = list(MarketplaceProductCode)
        assert len(codes) == 5

        assert MarketplaceProductCode.AURA_STARTER.value == "aura-starter-monthly"
        assert MarketplaceProductCode.AURA_GOVERNMENT.value == "aura-government-annual"

    def test_subscription_actions_enum(self):
        """Test all subscription actions are defined."""
        actions = list(SubscriptionAction)
        assert len(actions) == 5

        assert SubscriptionAction.SUBSCRIBE_SUCCESS.value == "subscribe-success"
        assert SubscriptionAction.UNSUBSCRIBE_SUCCESS.value == "unsubscribe-success"
