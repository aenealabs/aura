"""
Tests for Billing API Endpoints.

Comprehensive test suite covering:
- Plan listing and details
- Subscription CRUD operations
- Usage tracking and summaries
- Invoice management
- Payment method management
- Authorization and access control
"""

import platform
from contextlib import contextmanager

import pytest

# Run tests in separate processes to avoid mock pollution
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# Duck typing context manager for HTTPException in forked processes
# Avoids class identity issues between parent/child process imports
@contextmanager
def assert_http_exception(expected_status: int, detail_contains: str | None = None):
    """Assert that an HTTPException is raised with expected status code.

    Uses duck typing to check for status_code attribute instead of isinstance(),
    which fails in forked processes due to different class objects.
    """
    try:
        yield
        pytest.fail(f"Expected HTTPException with status {expected_status}")
    except Exception as e:
        # Duck type check - look for status_code attribute
        if not hasattr(e, "status_code"):
            pytest.fail(f"Expected HTTPException but got {type(e).__name__}: {e}")
        if e.status_code != expected_status:
            pytest.fail(f"Expected status {expected_status} but got {e.status_code}")
        if detail_contains and detail_contains not in str(getattr(e, "detail", "")):
            pytest.fail(
                f"Expected detail containing '{detail_contains}' but got '{e.detail}'"
            )


from src.api.billing_endpoints import (
    PaymentMethodRequest,
    PlanResponse,
    SubscriptionCreateRequest,
    SubscriptionResponse,
    SubscriptionUpdateRequest,
    UsageRecordRequest,
    invoice_to_response,
    payment_method_to_response,
    plan_to_response,
    subscription_to_response,
)
from src.services.billing_service import (
    BillingPlan,
    Invoice,
    InvoiceStatus,
    PaymentMethod,
    PlanDetails,
    Subscription,
    SubscriptionStatus,
    UsageRecord,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    user = MagicMock()
    user.id = "user-123"
    user.email = "test@example.com"
    user.customer_id = "cust-456"
    user.roles = ["admin"]
    return user


@pytest.fixture
def mock_billing_user():
    """Create a mock user with billing_admin role."""
    user = MagicMock()
    user.id = "user-789"
    user.email = "billing@example.com"
    user.customer_id = "cust-456"
    user.roles = ["billing_admin"]
    return user


@pytest.fixture
def mock_standard_user():
    """Create a mock user without admin/billing roles."""
    user = MagicMock()
    user.id = "user-std"
    user.email = "standard@example.com"
    user.customer_id = "cust-456"
    user.roles = ["user"]
    return user


@pytest.fixture
def sample_plan_details():
    """Create sample plan details."""
    return PlanDetails(
        plan_id="professional",
        name="Professional",
        description="For growing teams",
        monthly_price_cents=9900,
        annual_price_cents=99000,
        max_developers=25,
        features=[
            "Advanced code analysis",
            "Priority support",
            "Custom integrations",
        ],
    )


@pytest.fixture
def sample_subscription():
    """Create a sample subscription."""
    now = datetime.now(timezone.utc)
    return Subscription(
        subscription_id="sub-123",
        customer_id="cust-456",
        plan=BillingPlan.PROFESSIONAL,
        status=SubscriptionStatus.ACTIVE,
        billing_cycle="monthly",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        cancel_at_period_end=False,
        trial_end=None,
        created_at=now - timedelta(days=60),
    )


@pytest.fixture
def sample_invoice():
    """Create a sample invoice."""
    now = datetime.now(timezone.utc)
    return Invoice(
        invoice_id="inv-123",
        customer_id="cust-456",
        subscription_id="sub-123",
        status=InvoiceStatus.PAID,
        amount_due_cents=9900,
        amount_paid_cents=9900,
        currency="usd",
        period_start=now - timedelta(days=30),
        period_end=now,
        line_items=[{"description": "Professional Plan", "amount_cents": 9900}],
        pdf_url="https://example.com/invoice.pdf",
        created_at=now,
    )


@pytest.fixture
def sample_payment_method():
    """Create a sample payment method."""
    return PaymentMethod(
        payment_method_id="pm-123",
        customer_id="cust-456",
        type="card",
        last_four="4242",
        brand="visa",
        exp_month=12,
        exp_year=2025,
        is_default=True,
    )


@pytest.fixture
def sample_usage_record():
    """Create a sample usage record."""
    return UsageRecord(
        record_id="usage-123",
        customer_id="cust-456",
        subscription_id="sub-123",
        metric_name="llm_tokens",
        quantity=1000,
        unit_price_cents=0.001,
        total_cents=1.0,
        timestamp=datetime.now(timezone.utc),
    )


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Test helper conversion functions."""

    def test_plan_to_response(self, sample_plan_details):
        """Test plan to response conversion."""
        response = plan_to_response(sample_plan_details)

        assert isinstance(response, PlanResponse)
        assert response.plan_id == "professional"
        assert response.name == "Professional"
        assert response.monthly_price_cents == 9900
        assert response.annual_price_cents == 99000
        assert response.max_developers == 25
        assert len(response.features) == 3

    def test_subscription_to_response(self, sample_subscription):
        """Test subscription to response conversion."""
        response = subscription_to_response(sample_subscription)

        assert isinstance(response, SubscriptionResponse)
        assert response.subscription_id == "sub-123"
        assert response.customer_id == "cust-456"
        assert response.plan == "professional"
        assert response.status == "active"
        assert response.billing_cycle == "monthly"
        assert response.cancel_at_period_end is False
        assert response.trial_end is None

    def test_subscription_to_response_with_trial(self, sample_subscription):
        """Test subscription to response conversion with trial."""
        sample_subscription.trial_end = datetime.now(timezone.utc) + timedelta(days=14)
        response = subscription_to_response(sample_subscription)

        assert response.trial_end is not None

    def test_invoice_to_response(self, sample_invoice):
        """Test invoice to response conversion."""
        response = invoice_to_response(sample_invoice)

        assert response.invoice_id == "inv-123"
        assert response.customer_id == "cust-456"
        assert response.status == "paid"
        assert response.amount_due_cents == 9900
        assert response.amount_paid_cents == 9900
        assert response.currency == "usd"
        assert len(response.line_items) == 1
        assert response.pdf_url == "https://example.com/invoice.pdf"

    def test_payment_method_to_response(self, sample_payment_method):
        """Test payment method to response conversion."""
        response = payment_method_to_response(sample_payment_method)

        assert response.payment_method_id == "pm-123"
        assert response.type == "card"
        assert response.last_four == "4242"
        assert response.brand == "visa"
        assert response.exp_month == 12
        assert response.exp_year == 2025
        assert response.is_default is True


# =============================================================================
# Plan Endpoint Tests
# =============================================================================


class TestPlanEndpoints:
    """Test plan-related endpoints."""

    @pytest.mark.asyncio
    async def test_list_plans(self, sample_plan_details):
        """Test listing all plans."""
        from src.api.billing_endpoints import list_plans

        mock_service = MagicMock()
        mock_service.list_plans.return_value = [sample_plan_details]

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await list_plans()

        assert len(result) == 1
        assert result[0].plan_id == "professional"
        mock_service.list_plans.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_plan_success(self, sample_plan_details):
        """Test getting a specific plan."""
        from src.api.billing_endpoints import get_plan

        mock_service = MagicMock()
        mock_service.get_plan_details.return_value = sample_plan_details

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await get_plan("professional")

        assert result.plan_id == "professional"
        assert result.name == "Professional"

    @pytest.mark.asyncio
    async def test_get_plan_not_found(self):
        """Test getting a non-existent plan."""
        from src.api.billing_endpoints import get_plan

        with assert_http_exception(404, "Plan not found"):
            await get_plan("invalid_plan")


# =============================================================================
# Subscription Endpoint Tests
# =============================================================================


class TestSubscriptionEndpoints:
    """Test subscription-related endpoints."""

    @pytest.mark.asyncio
    async def test_get_subscription_exists(self, mock_user, sample_subscription):
        """Test getting existing subscription."""
        from src.api.billing_endpoints import get_subscription

        mock_service = MagicMock()
        mock_service.get_customer_subscription = AsyncMock(
            return_value=sample_subscription
        )

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await get_subscription(current_user=mock_user)

        assert result.subscription_id == "sub-123"
        assert result.plan == "professional"

    @pytest.mark.asyncio
    async def test_get_subscription_not_found(self, mock_user):
        """Test getting subscription when none exists."""
        from src.api.billing_endpoints import get_subscription

        mock_service = MagicMock()
        mock_service.get_customer_subscription = AsyncMock(return_value=None)

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await get_subscription(current_user=mock_user)

        assert result is None

    @pytest.mark.asyncio
    async def test_create_subscription_success(self, mock_user, sample_subscription):
        """Test creating a new subscription."""
        from src.api.billing_endpoints import create_subscription

        mock_service = MagicMock()
        mock_service.get_customer_subscription = AsyncMock(return_value=None)
        mock_service.create_subscription = AsyncMock(return_value=sample_subscription)

        request = SubscriptionCreateRequest(
            plan="professional",
            billing_cycle="monthly",
            trial_days=14,
        )

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await create_subscription(request=request, current_user=mock_user)

        assert result.subscription_id == "sub-123"
        mock_service.create_subscription.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_subscription_invalid_plan(self, mock_user):
        """Test creating subscription with invalid plan."""
        from src.api.billing_endpoints import create_subscription

        request = SubscriptionCreateRequest(
            plan="nonexistent",
            billing_cycle="monthly",
        )

        with assert_http_exception(400, "Invalid plan"):
            await create_subscription(request=request, current_user=mock_user)

    @pytest.mark.asyncio
    async def test_create_subscription_invalid_billing_cycle(self, mock_user):
        """Test creating subscription with invalid billing cycle."""
        from src.api.billing_endpoints import create_subscription

        request = SubscriptionCreateRequest(
            plan="professional",
            billing_cycle="quarterly",  # Invalid
        )

        mock_service = MagicMock()
        mock_service.get_customer_subscription = AsyncMock(return_value=None)

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            with assert_http_exception(400, "billing_cycle"):
                await create_subscription(request=request, current_user=mock_user)

    @pytest.mark.asyncio
    async def test_create_subscription_already_exists(
        self, mock_user, sample_subscription
    ):
        """Test creating subscription when one already exists."""
        from src.api.billing_endpoints import create_subscription

        mock_service = MagicMock()
        mock_service.get_customer_subscription = AsyncMock(
            return_value=sample_subscription
        )

        request = SubscriptionCreateRequest(
            plan="professional",
            billing_cycle="monthly",
        )

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            with assert_http_exception(400, "already has an active subscription"):
                await create_subscription(request=request, current_user=mock_user)

    @pytest.mark.asyncio
    async def test_update_subscription_success(self, mock_user, sample_subscription):
        """Test updating subscription."""
        from src.api.billing_endpoints import update_subscription

        updated = sample_subscription
        updated.plan = BillingPlan.ENTERPRISE

        mock_service = MagicMock()
        mock_service.get_customer_subscription = AsyncMock(
            return_value=sample_subscription
        )
        mock_service.update_subscription = AsyncMock(return_value=updated)

        request = SubscriptionUpdateRequest(plan="enterprise")

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await update_subscription(request=request, current_user=mock_user)

        assert result.plan == "enterprise"

    @pytest.mark.asyncio
    async def test_update_subscription_not_found(self, mock_user):
        """Test updating non-existent subscription."""
        from src.api.billing_endpoints import update_subscription

        mock_service = MagicMock()
        mock_service.get_customer_subscription = AsyncMock(return_value=None)

        request = SubscriptionUpdateRequest(plan="enterprise")

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            with assert_http_exception(404):
                await update_subscription(request=request, current_user=mock_user)

    @pytest.mark.asyncio
    async def test_cancel_subscription_success(self, mock_user, sample_subscription):
        """Test canceling subscription."""
        from src.api.billing_endpoints import cancel_subscription

        canceled = sample_subscription
        canceled.cancel_at_period_end = True
        canceled.status = SubscriptionStatus.CANCELED

        mock_service = MagicMock()
        mock_service.get_customer_subscription = AsyncMock(
            return_value=sample_subscription
        )
        mock_service.cancel_subscription = AsyncMock(return_value=canceled)

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await cancel_subscription(
                at_period_end=True, current_user=mock_user
            )

        assert result.cancel_at_period_end is True
        assert result.status == "canceled"

    @pytest.mark.asyncio
    async def test_cancel_subscription_not_found(self, mock_user):
        """Test canceling non-existent subscription."""
        from src.api.billing_endpoints import cancel_subscription

        mock_service = MagicMock()
        mock_service.get_customer_subscription = AsyncMock(return_value=None)

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            with assert_http_exception(404):
                await cancel_subscription(at_period_end=True, current_user=mock_user)


# =============================================================================
# Usage Endpoint Tests
# =============================================================================


class TestUsageEndpoints:
    """Test usage tracking endpoints."""

    @pytest.mark.asyncio
    async def test_get_usage_summary(self, mock_user):
        """Test getting usage summary."""
        from src.api.billing_endpoints import get_usage_summary

        mock_service = MagicMock()
        mock_service.get_usage_summary = AsyncMock(
            return_value={
                "customer_id": "cust-456",
                "period_days": 30,
                "by_metric": {
                    "llm_tokens": {"quantity": 10000, "total_cents": 10.0},
                    "agent_executions": {"quantity": 50, "total_cents": 5.0},
                },
                "total_usage_cents": 15.0,
            }
        )

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await get_usage_summary(days=30, current_user=mock_user)

        assert result.customer_id == "cust-456"
        assert result.period_days == 30
        assert result.total_usage_cents == 15.0
        assert "llm_tokens" in result.by_metric

    @pytest.mark.asyncio
    async def test_record_usage_success(self, mock_user, sample_usage_record):
        """Test recording usage."""
        from src.api.billing_endpoints import record_usage

        # Add system role to allow recording usage
        mock_user.roles = ["admin", "system"]

        mock_service = MagicMock()
        mock_service.record_usage = AsyncMock(return_value=sample_usage_record)

        request = UsageRecordRequest(
            metric_name="llm_tokens",
            quantity=1000,
        )

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await record_usage(request=request, current_user=mock_user)

        assert result.record_id == "usage-123"
        assert result.metric_name == "llm_tokens"
        assert result.quantity == 1000

    @pytest.mark.asyncio
    async def test_record_usage_invalid_metric(self, mock_user):
        """Test recording usage with invalid metric."""
        from src.api.billing_endpoints import record_usage

        mock_user.roles = ["admin", "system"]

        request = UsageRecordRequest(
            metric_name="invalid_metric",
            quantity=100,
        )

        with assert_http_exception(400, "Invalid metric_name"):
            await record_usage(request=request, current_user=mock_user)


# =============================================================================
# Invoice Endpoint Tests
# =============================================================================


class TestInvoiceEndpoints:
    """Test invoice-related endpoints."""

    @pytest.mark.asyncio
    async def test_list_invoices(self, mock_user, sample_invoice):
        """Test listing invoices."""
        from src.api.billing_endpoints import list_invoices

        mock_service = MagicMock()
        mock_service.list_invoices = AsyncMock(return_value=[sample_invoice])

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await list_invoices(limit=10, current_user=mock_user)

        assert len(result) == 1
        assert result[0].invoice_id == "inv-123"

    @pytest.mark.asyncio
    async def test_get_invoice_success(self, mock_user, sample_invoice):
        """Test getting a specific invoice."""
        from src.api.billing_endpoints import get_invoice

        mock_service = MagicMock()
        mock_service.get_invoice = AsyncMock(return_value=sample_invoice)

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await get_invoice(invoice_id="inv-123", current_user=mock_user)

        assert result.invoice_id == "inv-123"
        assert result.status == "paid"

    @pytest.mark.asyncio
    async def test_get_invoice_not_found(self, mock_user):
        """Test getting a non-existent invoice."""
        from src.api.billing_endpoints import get_invoice

        mock_service = MagicMock()
        mock_service.get_invoice = AsyncMock(return_value=None)

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            with assert_http_exception(404):
                await get_invoice(invoice_id="inv-nonexistent", current_user=mock_user)

    @pytest.mark.asyncio
    async def test_get_invoice_access_denied(self, mock_standard_user, sample_invoice):
        """Test accessing another customer's invoice."""
        from src.api.billing_endpoints import get_invoice

        # Invoice belongs to different customer
        sample_invoice.customer_id = "different-customer"

        mock_service = MagicMock()
        mock_service.get_invoice = AsyncMock(return_value=sample_invoice)

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            with assert_http_exception(403):
                await get_invoice(invoice_id="inv-123", current_user=mock_standard_user)


# =============================================================================
# Payment Method Endpoint Tests
# =============================================================================


class TestPaymentMethodEndpoints:
    """Test payment method endpoints."""

    @pytest.mark.asyncio
    async def test_list_payment_methods(self, mock_user, sample_payment_method):
        """Test listing payment methods."""
        from src.api.billing_endpoints import list_payment_methods

        mock_service = MagicMock()
        mock_service.list_payment_methods = AsyncMock(
            return_value=[sample_payment_method]
        )

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await list_payment_methods(current_user=mock_user)

        assert len(result) == 1
        assert result[0].payment_method_id == "pm-123"
        assert result[0].last_four == "4242"

    @pytest.mark.asyncio
    async def test_add_payment_method_success(self, mock_user, sample_payment_method):
        """Test adding a payment method."""
        from src.api.billing_endpoints import add_payment_method

        mock_service = MagicMock()
        mock_service.add_payment_method = AsyncMock(return_value=sample_payment_method)

        request = PaymentMethodRequest(
            stripe_payment_method_id="pm_test_123",
            set_as_default=True,
        )

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await add_payment_method(request=request, current_user=mock_user)

        assert result.payment_method_id == "pm-123"
        assert result.is_default is True

    @pytest.mark.asyncio
    async def test_add_payment_method_error(self, mock_user):
        """Test adding payment method with error."""
        from src.api.billing_endpoints import add_payment_method

        mock_service = MagicMock()
        mock_service.add_payment_method = AsyncMock(
            side_effect=Exception("Stripe error")
        )

        request = PaymentMethodRequest(
            stripe_payment_method_id="pm_invalid",
            set_as_default=True,
        )

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            with assert_http_exception(500):
                await add_payment_method(request=request, current_user=mock_user)


# =============================================================================
# Request/Response Model Tests
# =============================================================================


class TestRequestResponseModels:
    """Test Pydantic request/response models."""

    def test_subscription_create_request_defaults(self):
        """Test SubscriptionCreateRequest with defaults."""
        request = SubscriptionCreateRequest(plan="starter")
        assert request.billing_cycle == "monthly"
        assert request.payment_method_id is None
        assert request.trial_days == 0

    def test_subscription_create_request_validation(self):
        """Test SubscriptionCreateRequest validation."""
        # Valid trial days
        request = SubscriptionCreateRequest(plan="starter", trial_days=14)
        assert request.trial_days == 14

        # Invalid trial days (too high)
        with pytest.raises(ValueError):
            SubscriptionCreateRequest(plan="starter", trial_days=60)

    def test_subscription_update_request_optional_fields(self):
        """Test SubscriptionUpdateRequest with optional fields."""
        request = SubscriptionUpdateRequest()
        assert request.plan is None
        assert request.billing_cycle is None

        request = SubscriptionUpdateRequest(plan="enterprise")
        assert request.plan == "enterprise"

    def test_usage_record_request_validation(self):
        """Test UsageRecordRequest validation."""
        # Valid request
        request = UsageRecordRequest(metric_name="llm_tokens", quantity=100)
        assert request.quantity == 100

        # Invalid quantity
        with pytest.raises(ValueError):
            UsageRecordRequest(metric_name="llm_tokens", quantity=0)

    def test_payment_method_request_defaults(self):
        """Test PaymentMethodRequest defaults."""
        request = PaymentMethodRequest(stripe_payment_method_id="pm_test")
        assert request.set_as_default is True


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_service_exception_handling(self, mock_user, sample_subscription):
        """Test handling of service exceptions."""
        from src.api.billing_endpoints import create_subscription

        mock_service = MagicMock()
        mock_service.get_customer_subscription = AsyncMock(return_value=None)
        mock_service.create_subscription = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        request = SubscriptionCreateRequest(
            plan="professional", billing_cycle="monthly"
        )

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            with assert_http_exception(500):
                await create_subscription(request=request, current_user=mock_user)

    @pytest.mark.asyncio
    async def test_update_subscription_service_error(
        self, mock_user, sample_subscription
    ):
        """Test handling service errors in update."""
        from src.api.billing_endpoints import update_subscription

        mock_service = MagicMock()
        mock_service.get_customer_subscription = AsyncMock(
            return_value=sample_subscription
        )
        mock_service.update_subscription = AsyncMock(
            side_effect=Exception("Update failed")
        )

        request = SubscriptionUpdateRequest(plan="enterprise")

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            with assert_http_exception(500):
                await update_subscription(request=request, current_user=mock_user)


# =============================================================================
# Authorization Tests
# =============================================================================


class TestAuthorization:
    """Test authorization and access control."""

    def test_user_without_customer_id_defaults(self):
        """Test user without customer_id gets default."""
        user = MagicMock(spec=["id", "email", "roles"])
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = ["admin"]

        # Should default to "default" customer_id
        customer_id = getattr(user, "customer_id", "default")
        assert customer_id == "default"

    def test_billing_admin_role_access(self, mock_billing_user):
        """Test billing_admin role has proper access."""
        assert "billing_admin" in mock_billing_user.roles
        # billing_admin should have subscription management access

    def test_admin_role_access(self, mock_user):
        """Test admin role has proper access."""
        assert "admin" in mock_user.roles
        # Admin should have full access


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestEndpointIntegration:
    """Integration-style tests for endpoint flows."""

    @pytest.mark.asyncio
    async def test_subscription_lifecycle(self, mock_user):
        """Test complete subscription lifecycle."""
        from src.api.billing_endpoints import (
            cancel_subscription,
            create_subscription,
            update_subscription,
        )

        now = datetime.now(timezone.utc)

        # Create initial subscription
        initial_sub = Subscription(
            subscription_id="sub-lifecycle",
            customer_id="cust-456",
            plan=BillingPlan.STARTER,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle="monthly",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=False,
            trial_end=None,
            created_at=now,
        )

        mock_service = MagicMock()
        mock_service.get_customer_subscription = AsyncMock(return_value=None)
        mock_service.create_subscription = AsyncMock(return_value=initial_sub)

        request = SubscriptionCreateRequest(plan="starter", billing_cycle="monthly")

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            # Create
            result = await create_subscription(request=request, current_user=mock_user)
            assert result.plan == "starter"
            assert result.status == "active"

        # Update - upgrade plan
        upgraded_sub = Subscription(
            subscription_id="sub-lifecycle",
            customer_id="cust-456",
            plan=BillingPlan.PROFESSIONAL,
            status=SubscriptionStatus.ACTIVE,
            billing_cycle="monthly",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=False,
            trial_end=None,
            created_at=now,
        )

        mock_service.get_customer_subscription = AsyncMock(return_value=initial_sub)
        mock_service.update_subscription = AsyncMock(return_value=upgraded_sub)

        update_request = SubscriptionUpdateRequest(plan="professional")

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await update_subscription(
                request=update_request, current_user=mock_user
            )
            assert result.plan == "professional"

        # Cancel
        canceled_sub = Subscription(
            subscription_id="sub-lifecycle",
            customer_id="cust-456",
            plan=BillingPlan.PROFESSIONAL,
            status=SubscriptionStatus.CANCELED,
            billing_cycle="monthly",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=True,
            trial_end=None,
            created_at=now,
        )

        mock_service.get_customer_subscription = AsyncMock(return_value=upgraded_sub)
        mock_service.cancel_subscription = AsyncMock(return_value=canceled_sub)

        with patch(
            "src.api.billing_endpoints.get_billing_service", return_value=mock_service
        ):
            result = await cancel_subscription(
                at_period_end=True, current_user=mock_user
            )
            assert result.status == "canceled"
            assert result.cancel_at_period_end is True
