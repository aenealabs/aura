"""
Billing Service.

Manages subscription billing via Stripe:
- Subscription lifecycle (create, update, cancel)
- Usage-based billing for LLM tokens
- Invoice generation and history
- Payment method management

Supports both SaaS (multi-tenant) and self-hosted deployments.
"""

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BillingPlan(str, Enum):
    """Available billing plans."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    GOVERNMENT = "government"


class SubscriptionStatus(str, Enum):
    """Subscription status values."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    TRIALING = "trialing"
    PAUSED = "paused"


class InvoiceStatus(str, Enum):
    """Invoice status values."""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


@dataclass
class PlanDetails:
    """Details of a billing plan."""

    plan_id: str
    name: str
    description: str
    monthly_price_cents: int
    annual_price_cents: int
    max_developers: int
    features: List[str]
    stripe_monthly_price_id: Optional[str] = None
    stripe_annual_price_id: Optional[str] = None


@dataclass
class Subscription:
    """Customer subscription record."""

    subscription_id: str
    customer_id: str
    plan: BillingPlan
    status: SubscriptionStatus
    billing_cycle: str  # monthly, annual
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    trial_end: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None


@dataclass
class UsageRecord:
    """Usage record for metered billing."""

    record_id: str
    customer_id: str
    subscription_id: str
    metric_name: str  # llm_tokens, api_calls, agent_executions
    quantity: int
    unit_price_cents: float
    total_cents: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Invoice:
    """Invoice record."""

    invoice_id: str
    customer_id: str
    subscription_id: str
    status: InvoiceStatus
    amount_due_cents: int
    amount_paid_cents: int
    currency: str
    period_start: datetime
    period_end: datetime
    line_items: List[Dict[str, Any]]
    stripe_invoice_id: Optional[str] = None
    pdf_url: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    paid_at: Optional[datetime] = None


@dataclass
class PaymentMethod:
    """Stored payment method."""

    payment_method_id: str
    customer_id: str
    type: str  # card, bank_account
    last_four: str
    brand: Optional[str] = None  # visa, mastercard, etc.
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    is_default: bool = False
    stripe_payment_method_id: Optional[str] = None


# Plan definitions
BILLING_PLANS: Dict[str, PlanDetails] = {
    BillingPlan.FREE.value: PlanDetails(
        plan_id="plan_free",
        name="Free",
        description="For individual developers",
        monthly_price_cents=0,
        annual_price_cents=0,
        max_developers=1,
        features=[
            "1 repository",
            "Basic vulnerability scanning",
            "Community support",
        ],
    ),
    BillingPlan.STARTER.value: PlanDetails(
        plan_id="plan_starter",
        name="Starter",
        description="For small teams",
        monthly_price_cents=250000,  # $2,500
        annual_price_cents=2500000,  # $25,000
        max_developers=25,
        features=[
            "Up to 25 developers",
            "5 repositories",
            "AI code review",
            "Vulnerability patching",
            "Email support",
        ],
    ),
    BillingPlan.PROFESSIONAL.value: PlanDetails(
        plan_id="plan_professional",
        name="Professional",
        description="For growing teams",
        monthly_price_cents=750000,  # $7,500
        annual_price_cents=7500000,  # $75,000
        max_developers=100,
        features=[
            "Up to 100 developers",
            "Unlimited repositories",
            "Advanced security scanning",
            "Custom agent workflows",
            "Priority support",
            "SSO/SAML",
        ],
    ),
    BillingPlan.ENTERPRISE.value: PlanDetails(
        plan_id="plan_enterprise",
        name="Enterprise",
        description="For large organizations",
        monthly_price_cents=2000000,  # $20,000
        annual_price_cents=20000000,  # $200,000
        max_developers=500,
        features=[
            "Up to 500 developers",
            "Unlimited everything",
            "Self-healing code",
            "Custom integrations",
            "Dedicated support",
            "SLA guarantee",
            "On-prem option",
        ],
    ),
    BillingPlan.GOVERNMENT.value: PlanDetails(
        plan_id="plan_government",
        name="Government",
        description="For government agencies",
        monthly_price_cents=0,  # Custom pricing
        annual_price_cents=0,
        max_developers=999999,
        features=[
            "Unlimited developers",
            "FedRAMP ready",
            "CMMC Level 3",
            "GovCloud deployment",
            "Dedicated environment",
            "Custom SLA",
        ],
    ),
}


# Usage-based pricing (per unit in cents)
USAGE_PRICING = {
    "llm_tokens": 0.002,  # $0.00002 per token (2 cents per 1000)
    "agent_executions": 10.0,  # $0.10 per execution
    "api_calls_over_limit": 0.01,  # $0.0001 per API call over limit
}


class BillingService:
    """
    Service for managing billing and subscriptions.

    In production, integrates with Stripe. In test mode, uses mock data.
    """

    def __init__(self, mode: str = "mock") -> None:
        """
        Initialize the billing service.

        Args:
            mode: "mock" for testing, "stripe" for production
        """
        self.mode = mode
        self._subscriptions: Dict[str, Subscription] = {}
        self._invoices: Dict[str, Invoice] = {}
        self._usage_records: List[UsageRecord] = []
        self._payment_methods: Dict[str, PaymentMethod] = {}

        if mode == "stripe":
            import stripe

            stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
            self._stripe = stripe

    def get_plan_details(self, plan: BillingPlan) -> PlanDetails:
        """Get details for a billing plan."""
        plan_details = BILLING_PLANS.get(plan.value)
        if plan_details is None:
            raise ValueError(f"Plan {plan.value} not found")
        return plan_details

    def list_plans(self) -> List[PlanDetails]:
        """List all available plans."""
        return list(BILLING_PLANS.values())

    async def create_subscription(
        self,
        customer_id: str,
        plan: BillingPlan,
        billing_cycle: str = "monthly",
        payment_method_id: Optional[str] = None,
        trial_days: int = 0,
    ) -> Subscription:
        """
        Create a new subscription.

        Args:
            customer_id: Customer organization ID
            plan: Selected billing plan
            billing_cycle: monthly or annual
            payment_method_id: Payment method to use
            trial_days: Number of trial days

        Returns:
            Created Subscription
        """
        subscription_id = f"sub_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # Calculate period
        if billing_cycle == "annual":
            period_end = now + timedelta(days=365)
        else:
            period_end = now + timedelta(days=30)

        trial_end = now + timedelta(days=trial_days) if trial_days > 0 else None

        subscription = Subscription(
            subscription_id=subscription_id,
            customer_id=customer_id,
            plan=plan,
            status=(
                SubscriptionStatus.TRIALING
                if trial_days > 0
                else SubscriptionStatus.ACTIVE
            ),
            billing_cycle=billing_cycle,
            current_period_start=now,
            current_period_end=period_end,
            trial_end=trial_end,
        )

        if self.mode == "mock":
            self._subscriptions[subscription_id] = subscription
        else:
            # Create Stripe subscription
            stripe_sub = await self._create_stripe_subscription(
                customer_id, plan, billing_cycle, payment_method_id, trial_days
            )
            subscription.stripe_subscription_id = stripe_sub.id
            subscription.stripe_customer_id = stripe_sub.customer
            self._subscriptions[subscription_id] = subscription

        logger.info(
            f"Subscription {subscription_id} created for {customer_id} ({plan.value})"
        )
        return subscription

    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Get subscription by ID."""
        return self._subscriptions.get(subscription_id)

    async def get_customer_subscription(
        self, customer_id: str
    ) -> Optional[Subscription]:
        """Get active subscription for a customer."""
        for sub in self._subscriptions.values():
            if sub.customer_id == customer_id and sub.status in (
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIALING,
            ):
                return sub
        return None

    async def update_subscription(
        self,
        subscription_id: str,
        new_plan: Optional[BillingPlan] = None,
        billing_cycle: Optional[str] = None,
    ) -> Optional[Subscription]:
        """
        Update a subscription (upgrade/downgrade).

        Args:
            subscription_id: Subscription to update
            new_plan: New plan to switch to
            billing_cycle: New billing cycle

        Returns:
            Updated Subscription
        """
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return None

        if new_plan:
            subscription.plan = new_plan
        if billing_cycle:
            subscription.billing_cycle = billing_cycle

        subscription.updated_at = datetime.now(timezone.utc)

        if self.mode == "stripe" and subscription.stripe_subscription_id:
            await self._update_stripe_subscription(
                subscription.stripe_subscription_id, new_plan, billing_cycle
            )

        logger.info(
            f"Subscription {subscription_id} updated to {subscription.plan.value}"
        )
        return subscription

    async def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True,
    ) -> Optional[Subscription]:
        """
        Cancel a subscription.

        Args:
            subscription_id: Subscription to cancel
            at_period_end: Cancel at end of billing period

        Returns:
            Canceled Subscription
        """
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return None

        if at_period_end:
            subscription.cancel_at_period_end = True
        else:
            subscription.status = SubscriptionStatus.CANCELED

        subscription.updated_at = datetime.now(timezone.utc)

        if self.mode == "stripe" and subscription.stripe_subscription_id:
            await self._cancel_stripe_subscription(
                subscription.stripe_subscription_id, at_period_end
            )

        logger.info(
            f"Subscription {subscription_id} canceled (at_period_end={at_period_end})"
        )
        return subscription

    async def record_usage(
        self,
        customer_id: str,
        metric_name: str,
        quantity: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UsageRecord:
        """
        Record usage for metered billing.

        Args:
            customer_id: Customer organization ID
            metric_name: Metric being recorded (llm_tokens, agent_executions, etc.)
            quantity: Amount used
            metadata: Additional context

        Returns:
            Created UsageRecord
        """
        subscription = await self.get_customer_subscription(customer_id)
        if not subscription:
            raise ValueError(f"No active subscription for customer {customer_id}")

        unit_price = USAGE_PRICING.get(metric_name, 0)
        total = quantity * unit_price

        record = UsageRecord(
            record_id=f"usage_{uuid.uuid4().hex[:12]}",
            customer_id=customer_id,
            subscription_id=subscription.subscription_id,
            metric_name=metric_name,
            quantity=quantity,
            unit_price_cents=unit_price,
            total_cents=total,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

        self._usage_records.append(record)

        if self.mode == "stripe" and subscription.stripe_subscription_id:
            await self._report_stripe_usage(
                subscription.stripe_subscription_id, metric_name, quantity
            )

        return record

    async def get_usage_summary(
        self,
        customer_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get usage summary for a customer.

        Args:
            customer_id: Customer organization ID
            days: Number of days to include

        Returns:
            Usage summary by metric
        """
        period_start = datetime.now(timezone.utc) - timedelta(days=days)

        records = [
            r
            for r in self._usage_records
            if r.customer_id == customer_id and r.timestamp >= period_start
        ]

        # Aggregate by metric
        by_metric: Dict[str, Dict[str, Any]] = {}
        for record in records:
            if record.metric_name not in by_metric:
                by_metric[record.metric_name] = {
                    "quantity": 0,
                    "total_cents": 0,
                    "count": 0,
                }
            by_metric[record.metric_name]["quantity"] += record.quantity
            by_metric[record.metric_name]["total_cents"] += record.total_cents
            by_metric[record.metric_name]["count"] += 1

        return {
            "customer_id": customer_id,
            "period_days": days,
            "by_metric": by_metric,
            "total_usage_cents": sum(m["total_cents"] for m in by_metric.values()),
        }

    async def generate_invoice(
        self,
        customer_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> Invoice:
        """
        Generate an invoice for a billing period.

        Args:
            customer_id: Customer organization ID
            period_start: Start of billing period
            period_end: End of billing period

        Returns:
            Generated Invoice
        """
        subscription = await self.get_customer_subscription(customer_id)
        if not subscription:
            raise ValueError(f"No active subscription for customer {customer_id}")

        # Calculate base subscription charge
        plan = BILLING_PLANS.get(subscription.plan.value)
        if plan is None:
            raise ValueError(f"Plan {subscription.plan.value} not found")

        if subscription.billing_cycle == "annual":
            base_amount = plan.annual_price_cents // 12
        else:
            base_amount = plan.monthly_price_cents

        line_items: List[Dict[str, Any]] = [
            {
                "description": f"{plan.name} Plan - {subscription.billing_cycle}",
                "amount_cents": base_amount,
                "quantity": 1,
            }
        ]

        # Add usage charges
        usage_records = [
            r
            for r in self._usage_records
            if r.customer_id == customer_id
            and r.timestamp >= period_start
            and r.timestamp <= period_end
        ]

        usage_by_metric: Dict[str, int] = {}
        for record in usage_records:
            usage_by_metric[record.metric_name] = usage_by_metric.get(
                record.metric_name, 0
            ) + int(record.total_cents)

        for metric, amount in usage_by_metric.items():
            if amount > 0:
                line_items.append(
                    {
                        "description": f"Usage: {metric}",
                        "amount_cents": amount,
                        "quantity": 1,
                    }
                )

        total_amount = sum(int(item["amount_cents"]) for item in line_items)

        invoice = Invoice(
            invoice_id=f"inv_{uuid.uuid4().hex[:12]}",
            customer_id=customer_id,
            subscription_id=subscription.subscription_id,
            status=InvoiceStatus.OPEN,
            amount_due_cents=total_amount,
            amount_paid_cents=0,
            currency="usd",
            period_start=period_start,
            period_end=period_end,
            line_items=line_items,
        )

        self._invoices[invoice.invoice_id] = invoice

        if self.mode == "stripe" and subscription.stripe_subscription_id:
            stripe_invoice = await self._create_stripe_invoice(customer_id, line_items)
            invoice.stripe_invoice_id = stripe_invoice.id
            invoice.pdf_url = stripe_invoice.invoice_pdf

        logger.info(f"Invoice {invoice.invoice_id} generated for {customer_id}")
        return invoice

    async def list_invoices(
        self,
        customer_id: str,
        limit: int = 10,
    ) -> List[Invoice]:
        """List invoices for a customer."""
        invoices = [
            inv for inv in self._invoices.values() if inv.customer_id == customer_id
        ]
        return sorted(invoices, key=lambda x: x.created_at, reverse=True)[:limit]

    async def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Get invoice by ID."""
        return self._invoices.get(invoice_id)

    async def add_payment_method(
        self,
        customer_id: str,
        stripe_payment_method_id: str,
        set_as_default: bool = True,
    ) -> PaymentMethod:
        """
        Add a payment method for a customer.

        Args:
            customer_id: Customer organization ID
            stripe_payment_method_id: Stripe payment method token
            set_as_default: Set as default payment method

        Returns:
            Created PaymentMethod
        """
        payment_method = PaymentMethod(
            payment_method_id=f"pm_{uuid.uuid4().hex[:12]}",
            customer_id=customer_id,
            type="card",
            last_four="4242",  # Mock data
            brand="visa",
            exp_month=12,
            exp_year=2026,
            is_default=set_as_default,
            stripe_payment_method_id=stripe_payment_method_id,
        )

        if set_as_default:
            # Unset other default methods
            for pm in self._payment_methods.values():
                if pm.customer_id == customer_id:
                    pm.is_default = False

        self._payment_methods[payment_method.payment_method_id] = payment_method

        if self.mode == "stripe":
            await self._attach_stripe_payment_method(
                customer_id, stripe_payment_method_id, set_as_default
            )

        return payment_method

    async def list_payment_methods(self, customer_id: str) -> List[PaymentMethod]:
        """List payment methods for a customer."""
        return [
            pm for pm in self._payment_methods.values() if pm.customer_id == customer_id
        ]

    # Stripe integration methods (stubs for mock mode)

    async def _create_stripe_subscription(
        self,
        customer_id: str,
        plan: BillingPlan,
        billing_cycle: str,
        payment_method_id: Optional[str],
        trial_days: int,
    ):
        """Create subscription in Stripe."""
        if self.mode != "stripe":
            return None

        plan_details = BILLING_PLANS.get(plan.value)
        if plan_details is None:
            raise ValueError(f"Plan {plan.value} not found")

        price_id = (
            plan_details.stripe_annual_price_id
            if billing_cycle == "annual"
            else plan_details.stripe_monthly_price_id
        )

        return self._stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            default_payment_method=payment_method_id,
            trial_period_days=trial_days if trial_days > 0 else None,
        )

    async def _update_stripe_subscription(
        self,
        stripe_subscription_id: str,
        new_plan: Optional[BillingPlan],
        billing_cycle: Optional[str],
    ):
        """Update subscription in Stripe."""
        if self.mode != "stripe":
            return None
        # Implementation for Stripe update

    async def _cancel_stripe_subscription(
        self,
        stripe_subscription_id: str,
        at_period_end: bool,
    ):
        """Cancel subscription in Stripe."""
        if self.mode != "stripe":
            return None

        return self._stripe.Subscription.modify(
            stripe_subscription_id,
            cancel_at_period_end=at_period_end,
        )

    async def _report_stripe_usage(
        self,
        stripe_subscription_id: str,
        metric_name: str,
        quantity: int,
    ):
        """Report usage to Stripe metered billing."""
        if self.mode != "stripe":
            return None
        # Implementation for Stripe usage reporting

    async def _create_stripe_invoice(
        self,
        customer_id: str,
        line_items: List[Dict[str, Any]],
    ):
        """Create invoice in Stripe."""
        if self.mode != "stripe":
            return None
        # Implementation for Stripe invoice creation

    async def _attach_stripe_payment_method(
        self,
        customer_id: str,
        payment_method_id: str,
        set_as_default: bool,
    ):
        """Attach payment method in Stripe."""
        if self.mode != "stripe":
            return None
        # Implementation for Stripe payment method attachment

    # =========================================================================
    # AWS Marketplace Integration
    # =========================================================================

    async def record_marketplace_usage(
        self,
        customer_id: str,
        metric_name: str,
        quantity: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[UsageRecord]:
        """
        Record usage for AWS Marketplace metered billing.

        Bridges the internal billing service with AWS Marketplace metering.
        For Marketplace customers, usage is recorded both locally and
        sent to the Marketplace Metering Service.

        Args:
            customer_id: Customer organization ID
            metric_name: Metric being recorded
            quantity: Amount used
            metadata: Additional context

        Returns:
            Created UsageRecord if successful
        """
        from src.services.marketplace_service import (
            UsageDimension,
            get_marketplace_service,
        )

        # Record locally first
        try:
            record = await self.record_usage(
                customer_id=customer_id,
                metric_name=metric_name,
                quantity=quantity,
                metadata=metadata,
            )
        except ValueError as e:
            logger.warning(f"Could not record local usage: {e}")
            record = None

        # Map billing metrics to Marketplace dimensions
        dimension_map = {
            "llm_tokens": UsageDimension.LLM_TOKENS,
            "agent_executions": UsageDimension.AGENT_EXECUTIONS,
            "api_calls_over_limit": UsageDimension.API_CALLS,
        }

        marketplace_dimension = dimension_map.get(metric_name)
        if marketplace_dimension:
            try:
                marketplace_svc = get_marketplace_service()
                # Check if this is a Marketplace customer
                marketplace_customer = await marketplace_svc.get_customer(customer_id)

                if marketplace_customer:
                    await marketplace_svc.record_usage(
                        customer_id=customer_id,
                        dimension=marketplace_dimension,
                        quantity=quantity,
                    )
                    logger.info(
                        f"Recorded Marketplace usage: {metric_name}={quantity} "
                        f"for {customer_id}"
                    )
            except Exception as e:
                logger.error(f"Failed to record Marketplace usage: {e}")

        return record

    async def sync_marketplace_subscription(
        self,
        marketplace_customer_id: str,
    ) -> Optional[Subscription]:
        """
        Sync subscription status from AWS Marketplace.

        Creates or updates local subscription based on Marketplace
        entitlements.

        Args:
            marketplace_customer_id: AWS Marketplace customer ID

        Returns:
            Synced Subscription
        """
        from src.services.marketplace_service import (
            EntitlementStatus,
            get_marketplace_service,
        )

        try:
            marketplace_svc = get_marketplace_service()
            customer = await marketplace_svc.get_customer_by_aws_id(
                marketplace_customer_id
            )

            if not customer:
                logger.warning(
                    f"Marketplace customer not found: {marketplace_customer_id}"
                )
                return None

            # Check if we already have a subscription
            existing = await self.get_customer_subscription(customer.customer_id)

            if existing:
                # Update status based on Marketplace
                if customer.entitlement_status == EntitlementStatus.CANCELLED:
                    existing.status = SubscriptionStatus.CANCELED
                elif customer.entitlement_status == EntitlementStatus.SUSPENDED:
                    existing.status = SubscriptionStatus.PAUSED
                elif customer.entitlement_status == EntitlementStatus.ACTIVE:
                    existing.status = SubscriptionStatus.ACTIVE

                existing.updated_at = datetime.now(timezone.utc)
                return existing

            # Create new subscription based on product code
            plan_map = {
                "aura-starter-monthly": BillingPlan.STARTER,
                "aura-professional-monthly": BillingPlan.PROFESSIONAL,
                "aura-enterprise-monthly": BillingPlan.ENTERPRISE,
                "aura-enterprise-annual": BillingPlan.ENTERPRISE,
                "aura-government-annual": BillingPlan.GOVERNMENT,
            }

            plan = plan_map.get(customer.product_code, BillingPlan.PROFESSIONAL)
            billing_cycle = "annual" if "annual" in customer.product_code else "monthly"

            subscription = await self.create_subscription(
                customer_id=customer.customer_id,
                plan=plan,
                billing_cycle=billing_cycle,
            )

            # Store Marketplace reference
            subscription.metadata["marketplace_customer_id"] = marketplace_customer_id
            subscription.metadata["product_code"] = customer.product_code

            logger.info(
                f"Created subscription from Marketplace: {subscription.subscription_id}"
            )
            return subscription

        except Exception as e:
            logger.error(f"Failed to sync Marketplace subscription: {e}")
            return None

    async def get_marketplace_usage_report(
        self,
        customer_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get combined usage report for Marketplace customer.

        Combines local billing data with Marketplace metering data.

        Args:
            customer_id: Customer organization ID
            days: Number of days to include

        Returns:
            Combined usage report
        """
        from src.services.marketplace_service import get_marketplace_service

        # Get local usage
        local_usage = await self.get_usage_summary(customer_id, days)

        # Get Marketplace usage
        marketplace_usage = {}
        try:
            marketplace_svc = get_marketplace_service()
            marketplace_summary = await marketplace_svc.get_usage_summary(
                customer_id, days
            )
            marketplace_usage = marketplace_summary.get("usage_by_dimension", {})
        except Exception as e:
            logger.warning(f"Could not get Marketplace usage: {e}")

        return {
            "customer_id": customer_id,
            "period_days": days,
            "local_usage": local_usage.get("by_metric", {}),
            "marketplace_usage": marketplace_usage,
            "total_usage_cents": local_usage.get("total_usage_cents", 0),
            "sync_status": "ok" if marketplace_usage else "unavailable",
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_service: Optional[BillingService] = None


def get_billing_service(mode: Optional[str] = None) -> BillingService:
    """Get the singleton billing service instance."""
    global _service
    if _service is None:
        resolved_mode: str = mode or os.getenv("BILLING_MODE") or "mock"
        _service = BillingService(mode=resolved_mode)
    return _service
