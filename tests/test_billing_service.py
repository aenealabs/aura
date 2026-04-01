"""
Tests for Billing Service.

Validates subscription billing functionality:
- Subscription lifecycle (create, update, cancel)
- Usage-based billing for LLM tokens
- Invoice generation and history
- Payment method management
- AWS Marketplace integration
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.billing_service import (
    BILLING_PLANS,
    USAGE_PRICING,
    BillingPlan,
    BillingService,
    Invoice,
    InvoiceStatus,
    PaymentMethod,
    Subscription,
    SubscriptionStatus,
    UsageRecord,
    get_billing_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def billing_service():
    """Create a fresh billing service for each test."""
    return BillingService(mode="mock")


@pytest.fixture
def customer_id():
    """Sample customer ID."""
    return f"cust_{uuid.uuid4().hex[:12]}"


@pytest.fixture
async def subscription_with_customer(billing_service, customer_id):
    """Create a subscription for testing."""
    subscription = await billing_service.create_subscription(
        customer_id=customer_id,
        plan=BillingPlan.PROFESSIONAL,
        billing_cycle="monthly",
    )
    return subscription, customer_id


# =============================================================================
# Plan Details Tests
# =============================================================================


class TestPlanDetails:
    """Tests for billing plan configuration."""

    def test_all_plans_defined(self, billing_service):
        """Verify all expected plans are defined."""
        plans = billing_service.list_plans()
        assert len(plans) == 5

        plan_names = {p.name for p in plans}
        assert "Free" in plan_names
        assert "Starter" in plan_names
        assert "Professional" in plan_names
        assert "Enterprise" in plan_names
        assert "Government" in plan_names

    def test_get_plan_details(self, billing_service):
        """Test retrieving plan details."""
        plan = billing_service.get_plan_details(BillingPlan.PROFESSIONAL)

        assert plan is not None
        assert plan.name == "Professional"
        assert plan.monthly_price_cents == 750000  # $7,500
        assert plan.annual_price_cents == 7500000  # $75,000
        assert plan.max_developers == 100
        assert len(plan.features) > 0

    def test_free_plan_has_zero_cost(self, billing_service):
        """Verify free plan has no cost."""
        plan = billing_service.get_plan_details(BillingPlan.FREE)

        assert plan.monthly_price_cents == 0
        assert plan.annual_price_cents == 0
        assert plan.max_developers == 1

    def test_government_plan_custom_pricing(self, billing_service):
        """Government plan should have custom (zero) pricing."""
        plan = billing_service.get_plan_details(BillingPlan.GOVERNMENT)

        assert plan.monthly_price_cents == 0  # Custom pricing
        assert plan.max_developers == 999999  # Unlimited
        assert "FedRAMP ready" in plan.features
        assert "CMMC Level 3" in plan.features

    def test_plan_hierarchy_pricing(self, billing_service):
        """Verify pricing increases with plan tier."""
        starter = billing_service.get_plan_details(BillingPlan.STARTER)
        professional = billing_service.get_plan_details(BillingPlan.PROFESSIONAL)
        enterprise = billing_service.get_plan_details(BillingPlan.ENTERPRISE)

        assert starter.monthly_price_cents < professional.monthly_price_cents
        assert professional.monthly_price_cents < enterprise.monthly_price_cents


# =============================================================================
# Subscription Lifecycle Tests
# =============================================================================


class TestSubscriptionLifecycle:
    """Tests for subscription creation, updates, and cancellation."""

    @pytest.mark.asyncio
    async def test_create_subscription_monthly(self, billing_service, customer_id):
        """Test creating a monthly subscription."""
        subscription = await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.STARTER,
            billing_cycle="monthly",
        )

        assert subscription.subscription_id.startswith("sub_")
        assert subscription.customer_id == customer_id
        assert subscription.plan == BillingPlan.STARTER
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.billing_cycle == "monthly"
        assert subscription.current_period_end > subscription.current_period_start

    @pytest.mark.asyncio
    async def test_create_subscription_annual(self, billing_service, customer_id):
        """Test creating an annual subscription."""
        subscription = await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.ENTERPRISE,
            billing_cycle="annual",
        )

        assert subscription.billing_cycle == "annual"
        # Annual subscription should have ~365 day period
        period_days = (
            subscription.current_period_end - subscription.current_period_start
        ).days
        assert period_days >= 364 and period_days <= 366

    @pytest.mark.asyncio
    async def test_create_subscription_with_trial(self, billing_service, customer_id):
        """Test creating a subscription with trial period."""
        subscription = await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.PROFESSIONAL,
            billing_cycle="monthly",
            trial_days=14,
        )

        assert subscription.status == SubscriptionStatus.TRIALING
        assert subscription.trial_end is not None
        trial_days = (subscription.trial_end - subscription.current_period_start).days
        assert trial_days >= 13 and trial_days <= 15

    @pytest.mark.asyncio
    async def test_get_subscription(self, billing_service, customer_id):
        """Test retrieving a subscription by ID."""
        created = await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.STARTER,
            billing_cycle="monthly",
        )

        retrieved = await billing_service.get_subscription(created.subscription_id)

        assert retrieved is not None
        assert retrieved.subscription_id == created.subscription_id
        assert retrieved.customer_id == customer_id

    @pytest.mark.asyncio
    async def test_get_subscription_not_found(self, billing_service):
        """Test retrieving a non-existent subscription."""
        result = await billing_service.get_subscription("sub_nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_customer_subscription(self, billing_service, customer_id):
        """Test retrieving active subscription for a customer."""
        await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.PROFESSIONAL,
            billing_cycle="monthly",
        )

        subscription = await billing_service.get_customer_subscription(customer_id)

        assert subscription is not None
        assert subscription.customer_id == customer_id
        assert subscription.status in (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
        )

    @pytest.mark.asyncio
    async def test_update_subscription_plan(self, billing_service, customer_id):
        """Test upgrading subscription plan."""
        subscription = await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.STARTER,
            billing_cycle="monthly",
        )

        updated = await billing_service.update_subscription(
            subscription_id=subscription.subscription_id,
            new_plan=BillingPlan.PROFESSIONAL,
        )

        assert updated is not None
        assert updated.plan == BillingPlan.PROFESSIONAL
        assert updated.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_subscription_billing_cycle(
        self, billing_service, customer_id
    ):
        """Test changing billing cycle from monthly to annual."""
        subscription = await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.PROFESSIONAL,
            billing_cycle="monthly",
        )

        updated = await billing_service.update_subscription(
            subscription_id=subscription.subscription_id,
            billing_cycle="annual",
        )

        assert updated is not None
        assert updated.billing_cycle == "annual"

    @pytest.mark.asyncio
    async def test_update_nonexistent_subscription(self, billing_service):
        """Test updating a non-existent subscription returns None."""
        result = await billing_service.update_subscription(
            subscription_id="sub_nonexistent",
            new_plan=BillingPlan.ENTERPRISE,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_cancel_subscription_at_period_end(
        self, billing_service, customer_id
    ):
        """Test canceling subscription at end of billing period."""
        subscription = await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.STARTER,
            billing_cycle="monthly",
        )

        canceled = await billing_service.cancel_subscription(
            subscription_id=subscription.subscription_id,
            at_period_end=True,
        )

        assert canceled is not None
        assert canceled.cancel_at_period_end is True
        # Status should remain active until period end
        assert canceled.status == SubscriptionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_cancel_subscription_immediately(self, billing_service, customer_id):
        """Test immediate subscription cancellation."""
        subscription = await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.STARTER,
            billing_cycle="monthly",
        )

        canceled = await billing_service.cancel_subscription(
            subscription_id=subscription.subscription_id,
            at_period_end=False,
        )

        assert canceled is not None
        assert canceled.status == SubscriptionStatus.CANCELED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_subscription(self, billing_service):
        """Test canceling a non-existent subscription."""
        result = await billing_service.cancel_subscription(
            subscription_id="sub_nonexistent",
        )
        assert result is None


# =============================================================================
# Usage Recording Tests
# =============================================================================


class TestUsageRecording:
    """Tests for metered usage recording."""

    @pytest.mark.asyncio
    async def test_record_llm_token_usage(
        self, subscription_with_customer, billing_service
    ):
        """Test recording LLM token usage."""
        subscription, customer_id = subscription_with_customer

        record = await billing_service.record_usage(
            customer_id=customer_id,
            metric_name="llm_tokens",
            quantity=50000,
        )

        assert record.record_id.startswith("usage_")
        assert record.customer_id == customer_id
        assert record.metric_name == "llm_tokens"
        assert record.quantity == 50000
        assert record.unit_price_cents == USAGE_PRICING["llm_tokens"]
        assert record.total_cents == 50000 * USAGE_PRICING["llm_tokens"]

    @pytest.mark.asyncio
    async def test_record_agent_execution_usage(
        self, subscription_with_customer, billing_service
    ):
        """Test recording agent execution usage."""
        subscription, customer_id = subscription_with_customer

        record = await billing_service.record_usage(
            customer_id=customer_id,
            metric_name="agent_executions",
            quantity=100,
        )

        assert record.metric_name == "agent_executions"
        assert record.quantity == 100
        assert record.total_cents == 100 * USAGE_PRICING["agent_executions"]

    @pytest.mark.asyncio
    async def test_record_usage_with_metadata(
        self, subscription_with_customer, billing_service
    ):
        """Test recording usage with additional metadata."""
        subscription, customer_id = subscription_with_customer

        metadata = {"agent_type": "security", "model": "claude-3"}
        record = await billing_service.record_usage(
            customer_id=customer_id,
            metric_name="llm_tokens",
            quantity=10000,
            metadata=metadata,
        )

        assert record.metadata == metadata

    @pytest.mark.asyncio
    async def test_record_usage_no_subscription(self, billing_service):
        """Test that recording usage without subscription raises error."""
        with pytest.raises(ValueError, match="No active subscription"):
            await billing_service.record_usage(
                customer_id="cust_nonexistent",
                metric_name="llm_tokens",
                quantity=1000,
            )

    @pytest.mark.asyncio
    async def test_get_usage_summary(self, subscription_with_customer, billing_service):
        """Test getting usage summary for a customer."""
        subscription, customer_id = subscription_with_customer

        # Record multiple usage events
        await billing_service.record_usage(
            customer_id=customer_id,
            metric_name="llm_tokens",
            quantity=50000,
        )
        await billing_service.record_usage(
            customer_id=customer_id,
            metric_name="llm_tokens",
            quantity=30000,
        )
        await billing_service.record_usage(
            customer_id=customer_id,
            metric_name="agent_executions",
            quantity=25,
        )

        summary = await billing_service.get_usage_summary(customer_id, days=30)

        assert summary["customer_id"] == customer_id
        assert summary["period_days"] == 30
        assert "llm_tokens" in summary["by_metric"]
        assert "agent_executions" in summary["by_metric"]
        assert summary["by_metric"]["llm_tokens"]["quantity"] == 80000
        assert summary["by_metric"]["llm_tokens"]["count"] == 2
        assert summary["by_metric"]["agent_executions"]["quantity"] == 25

    @pytest.mark.asyncio
    async def test_usage_summary_empty(
        self, subscription_with_customer, billing_service
    ):
        """Test usage summary with no usage records."""
        subscription, customer_id = subscription_with_customer

        summary = await billing_service.get_usage_summary(customer_id, days=30)

        assert summary["customer_id"] == customer_id
        assert summary["by_metric"] == {}
        assert summary["total_usage_cents"] == 0


# =============================================================================
# Invoice Tests
# =============================================================================


class TestInvoices:
    """Tests for invoice generation and management."""

    @pytest.mark.asyncio
    async def test_generate_invoice(self, subscription_with_customer, billing_service):
        """Test generating an invoice for a billing period."""
        subscription, customer_id = subscription_with_customer

        period_start = datetime.now(timezone.utc) - timedelta(days=30)
        period_end = datetime.now(timezone.utc)

        invoice = await billing_service.generate_invoice(
            customer_id=customer_id,
            period_start=period_start,
            period_end=period_end,
        )

        assert invoice.invoice_id.startswith("inv_")
        assert invoice.customer_id == customer_id
        assert invoice.status == InvoiceStatus.OPEN
        assert invoice.currency == "usd"
        assert len(invoice.line_items) >= 1
        assert invoice.amount_due_cents > 0

    @pytest.mark.asyncio
    async def test_generate_invoice_with_usage(
        self, subscription_with_customer, billing_service
    ):
        """Test invoice includes usage charges."""
        subscription, customer_id = subscription_with_customer

        # Record usage
        await billing_service.record_usage(
            customer_id=customer_id,
            metric_name="llm_tokens",
            quantity=100000,
        )

        period_start = datetime.now(timezone.utc) - timedelta(days=30)
        period_end = datetime.now(timezone.utc)

        invoice = await billing_service.generate_invoice(
            customer_id=customer_id,
            period_start=period_start,
            period_end=period_end,
        )

        # Should have base subscription + usage line items
        assert len(invoice.line_items) >= 2

        usage_items = [i for i in invoice.line_items if "Usage" in i["description"]]
        assert len(usage_items) >= 1

    @pytest.mark.asyncio
    async def test_generate_invoice_no_subscription(self, billing_service):
        """Test invoice generation fails without subscription."""
        with pytest.raises(ValueError, match="No active subscription"):
            await billing_service.generate_invoice(
                customer_id="cust_nonexistent",
                period_start=datetime.now(timezone.utc) - timedelta(days=30),
                period_end=datetime.now(timezone.utc),
            )

    @pytest.mark.asyncio
    async def test_list_invoices(self, subscription_with_customer, billing_service):
        """Test listing invoices for a customer."""
        subscription, customer_id = subscription_with_customer

        # Generate multiple invoices
        for i in range(3):
            period_start = datetime.now(timezone.utc) - timedelta(days=30 * (i + 1))
            period_end = datetime.now(timezone.utc) - timedelta(days=30 * i)
            await billing_service.generate_invoice(
                customer_id=customer_id,
                period_start=period_start,
                period_end=period_end,
            )

        invoices = await billing_service.list_invoices(customer_id, limit=10)

        assert len(invoices) == 3
        # Should be sorted by created_at descending
        assert invoices[0].created_at >= invoices[1].created_at

    @pytest.mark.asyncio
    async def test_get_invoice(self, subscription_with_customer, billing_service):
        """Test retrieving a specific invoice."""
        subscription, customer_id = subscription_with_customer

        created = await billing_service.generate_invoice(
            customer_id=customer_id,
            period_start=datetime.now(timezone.utc) - timedelta(days=30),
            period_end=datetime.now(timezone.utc),
        )

        retrieved = await billing_service.get_invoice(created.invoice_id)

        assert retrieved is not None
        assert retrieved.invoice_id == created.invoice_id

    @pytest.mark.asyncio
    async def test_get_invoice_not_found(self, billing_service):
        """Test retrieving a non-existent invoice."""
        result = await billing_service.get_invoice("inv_nonexistent")
        assert result is None


# =============================================================================
# Payment Method Tests
# =============================================================================


class TestPaymentMethods:
    """Tests for payment method management."""

    @pytest.mark.asyncio
    async def test_add_payment_method(self, billing_service, customer_id):
        """Test adding a payment method."""
        payment_method = await billing_service.add_payment_method(
            customer_id=customer_id,
            stripe_payment_method_id="pm_test_123",
            set_as_default=True,
        )

        assert payment_method.payment_method_id.startswith("pm_")
        assert payment_method.customer_id == customer_id
        assert payment_method.type == "card"
        assert payment_method.is_default is True
        assert payment_method.last_four == "4242"

    @pytest.mark.asyncio
    async def test_add_multiple_payment_methods(self, billing_service, customer_id):
        """Test adding multiple payment methods updates default."""
        _pm1 = await billing_service.add_payment_method(
            customer_id=customer_id,
            stripe_payment_method_id="pm_test_1",
            set_as_default=True,
        )

        pm2 = await billing_service.add_payment_method(
            customer_id=customer_id,
            stripe_payment_method_id="pm_test_2",
            set_as_default=True,
        )

        methods = await billing_service.list_payment_methods(customer_id)

        assert len(methods) == 2

        # Only the latest should be default
        defaults = [m for m in methods if m.is_default]
        assert len(defaults) == 1
        assert defaults[0].payment_method_id == pm2.payment_method_id

    @pytest.mark.asyncio
    async def test_add_non_default_payment_method(self, billing_service, customer_id):
        """Test adding a non-default payment method."""
        pm = await billing_service.add_payment_method(
            customer_id=customer_id,
            stripe_payment_method_id="pm_test_1",
            set_as_default=False,
        )

        assert pm.is_default is False

    @pytest.mark.asyncio
    async def test_list_payment_methods(self, billing_service, customer_id):
        """Test listing payment methods for a customer."""
        await billing_service.add_payment_method(
            customer_id=customer_id,
            stripe_payment_method_id="pm_test_1",
        )
        await billing_service.add_payment_method(
            customer_id=customer_id,
            stripe_payment_method_id="pm_test_2",
            set_as_default=False,
        )

        methods = await billing_service.list_payment_methods(customer_id)

        assert len(methods) == 2

    @pytest.mark.asyncio
    async def test_list_payment_methods_empty(self, billing_service, customer_id):
        """Test listing payment methods when none exist."""
        methods = await billing_service.list_payment_methods(customer_id)
        assert methods == []


# =============================================================================
# AWS Marketplace Integration Tests
# =============================================================================


class TestMarketplaceIntegration:
    """Tests for AWS Marketplace billing integration."""

    @pytest.mark.asyncio
    async def test_record_marketplace_usage(
        self, subscription_with_customer, billing_service
    ):
        """Test recording usage with Marketplace integration."""
        subscription, customer_id = subscription_with_customer

        with patch(
            "src.services.marketplace_service.get_marketplace_service"
        ) as mock_mp:
            mock_svc = MagicMock()
            mock_svc.get_customer = AsyncMock(
                return_value=None
            )  # Not a marketplace customer
            mock_mp.return_value = mock_svc

            record = await billing_service.record_marketplace_usage(
                customer_id=customer_id,
                metric_name="llm_tokens",
                quantity=10000,
            )

            assert record is not None
            assert record.quantity == 10000

    @pytest.mark.asyncio
    async def test_record_marketplace_usage_no_subscription(self, billing_service):
        """Test marketplace usage recording without subscription."""
        with patch(
            "src.services.marketplace_service.get_marketplace_service"
        ) as mock_mp:
            mock_svc = MagicMock()
            mock_svc.get_customer = AsyncMock(return_value=None)
            mock_mp.return_value = mock_svc

            # Should handle gracefully (log warning, return None)
            record = await billing_service.record_marketplace_usage(
                customer_id="cust_nonexistent",
                metric_name="llm_tokens",
                quantity=10000,
            )

            assert record is None


# =============================================================================
# Singleton Tests
# =============================================================================


class TestBillingServiceSingleton:
    """Tests for singleton pattern."""

    def test_get_billing_service_default_mode(self):
        """Test getting billing service with default mode."""
        # Reset singleton
        import src.services.billing_service as module

        module._service = None

        with patch.dict("os.environ", {"BILLING_MODE": "mock"}):
            service = get_billing_service()
            assert service.mode == "mock"

    def test_get_billing_service_explicit_mode(self):
        """Test getting billing service with explicit mode."""
        import src.services.billing_service as module

        module._service = None

        service = get_billing_service(mode="mock")
        assert service.mode == "mock"

    def test_singleton_returns_same_instance(self):
        """Test that singleton returns same instance."""
        import src.services.billing_service as module

        module._service = None

        service1 = get_billing_service()
        service2 = get_billing_service()

        assert service1 is service2


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_annual_billing_calculation(
        self, subscription_with_customer, billing_service
    ):
        """Test that annual billing divides correctly for monthly invoice."""
        subscription, customer_id = subscription_with_customer

        # Update to annual billing
        await billing_service.update_subscription(
            subscription_id=subscription.subscription_id,
            billing_cycle="annual",
        )

        invoice = await billing_service.generate_invoice(
            customer_id=customer_id,
            period_start=datetime.now(timezone.utc) - timedelta(days=30),
            period_end=datetime.now(timezone.utc),
        )

        # Annual price divided by 12 should be monthly charge
        professional_plan = BILLING_PLANS[BillingPlan.PROFESSIONAL.value]
        expected_monthly = professional_plan.annual_price_cents // 12

        base_line_item = [
            i for i in invoice.line_items if "annual" in i["description"].lower()
        ]
        assert len(base_line_item) == 1
        assert base_line_item[0]["amount_cents"] == expected_monthly

    @pytest.mark.asyncio
    async def test_unknown_metric_usage(
        self, subscription_with_customer, billing_service
    ):
        """Test recording usage with unknown metric (defaults to 0 price)."""
        subscription, customer_id = subscription_with_customer

        record = await billing_service.record_usage(
            customer_id=customer_id,
            metric_name="unknown_metric",
            quantity=100,
        )

        assert record.unit_price_cents == 0
        assert record.total_cents == 0

    @pytest.mark.asyncio
    async def test_multiple_subscriptions_only_active_returned(
        self, billing_service, customer_id
    ):
        """Test that only active subscription is returned for customer."""
        # Create and cancel first subscription
        sub1 = await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.STARTER,
            billing_cycle="monthly",
        )
        await billing_service.cancel_subscription(
            subscription_id=sub1.subscription_id,
            at_period_end=False,
        )

        # Create new active subscription
        sub2 = await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.PROFESSIONAL,
            billing_cycle="monthly",
        )

        active = await billing_service.get_customer_subscription(customer_id)

        assert active is not None
        assert active.subscription_id == sub2.subscription_id
        assert active.status == SubscriptionStatus.ACTIVE


# =============================================================================
# Data Model Tests
# =============================================================================


class TestDataModels:
    """Tests for billing data models."""

    def test_subscription_dataclass(self):
        """Test Subscription dataclass creation."""
        sub = Subscription(
            subscription_id="sub_123",
            customer_id="cust_456",
            plan=BillingPlan.PROFESSIONAL,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle="monthly",
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        )
        assert sub.subscription_id == "sub_123"
        assert sub.cancel_at_period_end is False
        assert sub.trial_end is None

    def test_subscription_with_metadata(self):
        """Test Subscription dataclass with metadata."""
        sub = Subscription(
            subscription_id="sub_123",
            customer_id="cust_456",
            plan=BillingPlan.ENTERPRISE,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle="annual",
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc) + timedelta(days=365),
            stripe_subscription_id="stripe_sub_123",
            stripe_customer_id="stripe_cust_456",
            metadata={"source": "marketplace"},
        )
        assert sub.stripe_subscription_id == "stripe_sub_123"
        assert sub.metadata["source"] == "marketplace"

    def test_usage_record_dataclass(self):
        """Test UsageRecord dataclass creation."""
        record = UsageRecord(
            record_id="usage_123",
            customer_id="cust_456",
            subscription_id="sub_789",
            metric_name="llm_tokens",
            quantity=1000,
            unit_price_cents=0.001,
            total_cents=1.0,
            timestamp=datetime.now(timezone.utc),
        )
        assert record.record_id == "usage_123"
        assert record.quantity == 1000

    def test_usage_record_with_metadata(self):
        """Test UsageRecord with metadata."""
        record = UsageRecord(
            record_id="usage_123",
            customer_id="cust_456",
            subscription_id="sub_789",
            metric_name="agent_executions",
            quantity=50,
            unit_price_cents=10.0,
            total_cents=500.0,
            timestamp=datetime.now(timezone.utc),
            metadata={"agent_type": "security", "model": "claude-3"},
        )
        assert record.metadata["agent_type"] == "security"

    def test_invoice_dataclass(self):
        """Test Invoice dataclass creation."""
        invoice = Invoice(
            invoice_id="inv_123",
            customer_id="cust_456",
            subscription_id="sub_789",
            status=InvoiceStatus.OPEN,
            amount_due_cents=100000,
            amount_paid_cents=0,
            currency="usd",
            period_start=datetime.now(timezone.utc) - timedelta(days=30),
            period_end=datetime.now(timezone.utc),
            line_items=[],
        )
        assert invoice.invoice_id == "inv_123"
        assert invoice.status == InvoiceStatus.OPEN

    def test_invoice_with_all_fields(self):
        """Test Invoice with all optional fields populated."""
        invoice = Invoice(
            invoice_id="inv_123",
            customer_id="cust_456",
            subscription_id="sub_789",
            status=InvoiceStatus.PAID,
            amount_due_cents=100000,
            amount_paid_cents=100000,
            currency="usd",
            period_start=datetime.now(timezone.utc) - timedelta(days=30),
            period_end=datetime.now(timezone.utc),
            line_items=[
                {"description": "Professional Plan (monthly)", "amount_cents": 75000}
            ],
            stripe_invoice_id="in_stripe123",
            pdf_url="https://stripe.com/invoice.pdf",
        )
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.stripe_invoice_id == "in_stripe123"
        assert len(invoice.line_items) == 1

    def test_payment_method_dataclass(self):
        """Test PaymentMethod dataclass creation."""
        pm = PaymentMethod(
            payment_method_id="pm_123",
            customer_id="cust_456",
            type="card",
            last_four="4242",
            brand="visa",
            exp_month=12,
            exp_year=2025,
            is_default=True,
        )
        assert pm.payment_method_id == "pm_123"
        assert pm.is_default is True

    def test_plan_details_dataclass(self):
        """Test PlanDetails dataclass from BILLING_PLANS."""
        plan = BILLING_PLANS.get(BillingPlan.PROFESSIONAL.value)
        assert plan is not None
        assert plan.name == "Professional"
        assert plan.monthly_price_cents > 0
        assert len(plan.features) > 0


# =============================================================================
# Usage Pricing Tests
# =============================================================================


class TestUsagePricing:
    """Tests for usage-based pricing calculations."""

    def test_usage_pricing_defined(self):
        """Test that usage pricing is defined for key metrics."""
        assert "llm_tokens" in USAGE_PRICING
        assert "agent_executions" in USAGE_PRICING
        # Note: actual keys are llm_tokens, agent_executions, api_calls_over_limit

    def test_llm_token_pricing(self):
        """Test LLM token pricing value."""
        # Tokens are priced per 1000 (0.002 cents per token)
        assert USAGE_PRICING["llm_tokens"] == 0.002

    def test_agent_execution_pricing(self):
        """Test agent execution pricing value."""
        assert USAGE_PRICING["agent_executions"] == 10.0

    @pytest.mark.asyncio
    async def test_usage_pricing_calculation(
        self, subscription_with_customer, billing_service
    ):
        """Test that usage pricing is calculated correctly."""
        subscription, customer_id = subscription_with_customer

        quantity = 100000
        record = await billing_service.record_usage(
            customer_id=customer_id,
            metric_name="llm_tokens",
            quantity=quantity,
        )

        expected_total = quantity * USAGE_PRICING["llm_tokens"]
        assert record.total_cents == expected_total


# =============================================================================
# Subscription Status Tests
# =============================================================================


class TestSubscriptionStatus:
    """Tests for subscription status transitions."""

    @pytest.mark.asyncio
    async def test_trialing_status_with_trial(self, billing_service, customer_id):
        """Test subscription status is TRIALING when trial_days > 0."""
        subscription = await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.PROFESSIONAL,
            billing_cycle="monthly",
            trial_days=14,
        )
        assert subscription.status == SubscriptionStatus.TRIALING

    @pytest.mark.asyncio
    async def test_active_status_without_trial(self, billing_service, customer_id):
        """Test subscription status is ACTIVE when trial_days = 0."""
        subscription = await billing_service.create_subscription(
            customer_id=customer_id,
            plan=BillingPlan.PROFESSIONAL,
            billing_cycle="monthly",
            trial_days=0,
        )
        assert subscription.status == SubscriptionStatus.ACTIVE

    def test_all_status_values_defined(self):
        """Test that all expected status values are defined."""
        assert SubscriptionStatus.ACTIVE.value == "active"
        assert SubscriptionStatus.PAST_DUE.value == "past_due"
        assert SubscriptionStatus.CANCELED.value == "canceled"
        assert SubscriptionStatus.INCOMPLETE.value == "incomplete"
        assert SubscriptionStatus.TRIALING.value == "trialing"
        assert SubscriptionStatus.PAUSED.value == "paused"

    def test_all_invoice_status_values_defined(self):
        """Test that all expected invoice status values are defined."""
        assert InvoiceStatus.DRAFT.value == "draft"
        assert InvoiceStatus.OPEN.value == "open"
        assert InvoiceStatus.PAID.value == "paid"
        assert InvoiceStatus.VOID.value == "void"
        assert InvoiceStatus.UNCOLLECTIBLE.value == "uncollectible"
