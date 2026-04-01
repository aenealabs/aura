"""
Billing API Endpoints.

Provides REST API for billing and subscription management:
- GET /api/v1/billing/plans - List available plans
- GET /api/v1/billing/subscription - Get current subscription
- POST /api/v1/billing/subscription - Create subscription
- PUT /api/v1/billing/subscription - Update subscription
- DELETE /api/v1/billing/subscription - Cancel subscription
- GET /api/v1/billing/usage - Get usage summary
- POST /api/v1/billing/usage - Record usage
- GET /api/v1/billing/invoices - List invoices
- GET /api/v1/billing/invoices/{id} - Get invoice details
- POST /api/v1/billing/payment-methods - Add payment method
- GET /api/v1/billing/payment-methods - List payment methods
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user, require_role
from src.services.billing_service import (
    BillingPlan,
    Invoice,
    PaymentMethod,
    PlanDetails,
    Subscription,
    get_billing_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/billing",
    tags=["Billing"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class PlanResponse(BaseModel):
    """Billing plan response."""

    plan_id: str
    name: str
    description: str
    monthly_price_cents: int
    annual_price_cents: int
    max_developers: int
    features: List[str]


class SubscriptionCreateRequest(BaseModel):
    """Request to create a subscription."""

    plan: str = Field(
        ..., description="Plan: starter, professional, enterprise, government"
    )
    billing_cycle: str = Field(default="monthly", description="monthly or annual")
    payment_method_id: Optional[str] = Field(
        default=None, description="Payment method ID"
    )
    trial_days: int = Field(default=0, ge=0, le=30, description="Trial period days")


class SubscriptionUpdateRequest(BaseModel):
    """Request to update a subscription."""

    plan: Optional[str] = Field(default=None, description="New plan")
    billing_cycle: Optional[str] = Field(default=None, description="New billing cycle")


class SubscriptionResponse(BaseModel):
    """Subscription response."""

    subscription_id: str
    customer_id: str
    plan: str
    status: str
    billing_cycle: str
    current_period_start: str
    current_period_end: str
    cancel_at_period_end: bool
    trial_end: Optional[str]
    created_at: str


class UsageRecordRequest(BaseModel):
    """Request to record usage."""

    metric_name: str = Field(
        ..., description="Metric: llm_tokens, agent_executions, api_calls_over_limit"
    )
    quantity: int = Field(..., ge=1, description="Amount used")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context"
    )


class UsageRecordResponse(BaseModel):
    """Usage record response."""

    record_id: str
    metric_name: str
    quantity: int
    total_cents: float
    timestamp: str


class UsageSummaryResponse(BaseModel):
    """Usage summary response."""

    customer_id: str
    period_days: int
    by_metric: Dict[str, Dict[str, Any]]
    total_usage_cents: float


class InvoiceResponse(BaseModel):
    """Invoice response."""

    invoice_id: str
    customer_id: str
    status: str
    amount_due_cents: int
    amount_paid_cents: int
    currency: str
    period_start: str
    period_end: str
    line_items: List[Dict[str, Any]]
    pdf_url: Optional[str]
    created_at: str


class PaymentMethodRequest(BaseModel):
    """Request to add a payment method."""

    stripe_payment_method_id: str = Field(
        ..., description="Stripe payment method token"
    )
    set_as_default: bool = Field(
        default=True, description="Set as default payment method"
    )


class PaymentMethodResponse(BaseModel):
    """Payment method response."""

    payment_method_id: str
    type: str
    last_four: str
    brand: Optional[str]
    exp_month: Optional[int]
    exp_year: Optional[int]
    is_default: bool


# =============================================================================
# Helper Functions
# =============================================================================


def plan_to_response(plan: PlanDetails) -> PlanResponse:
    """Convert PlanDetails to response model."""
    return PlanResponse(
        plan_id=plan.plan_id,
        name=plan.name,
        description=plan.description,
        monthly_price_cents=plan.monthly_price_cents,
        annual_price_cents=plan.annual_price_cents,
        max_developers=plan.max_developers,
        features=plan.features,
    )


def subscription_to_response(sub: Subscription) -> SubscriptionResponse:
    """Convert Subscription to response model."""
    return SubscriptionResponse(
        subscription_id=sub.subscription_id,
        customer_id=sub.customer_id,
        plan=sub.plan.value,
        status=sub.status.value,
        billing_cycle=sub.billing_cycle,
        current_period_start=sub.current_period_start.isoformat(),
        current_period_end=sub.current_period_end.isoformat(),
        cancel_at_period_end=sub.cancel_at_period_end,
        trial_end=sub.trial_end.isoformat() if sub.trial_end else None,
        created_at=sub.created_at.isoformat(),
    )


def invoice_to_response(inv: Invoice) -> InvoiceResponse:
    """Convert Invoice to response model."""
    return InvoiceResponse(
        invoice_id=inv.invoice_id,
        customer_id=inv.customer_id,
        status=inv.status.value,
        amount_due_cents=inv.amount_due_cents,
        amount_paid_cents=inv.amount_paid_cents,
        currency=inv.currency,
        period_start=inv.period_start.isoformat(),
        period_end=inv.period_end.isoformat(),
        line_items=inv.line_items,
        pdf_url=inv.pdf_url,
        created_at=inv.created_at.isoformat(),
    )


def payment_method_to_response(pm: PaymentMethod) -> PaymentMethodResponse:
    """Convert PaymentMethod to response model."""
    return PaymentMethodResponse(
        payment_method_id=pm.payment_method_id,
        type=pm.type,
        last_four=pm.last_four,
        brand=pm.brand,
        exp_month=pm.exp_month,
        exp_year=pm.exp_year,
        is_default=pm.is_default,
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.get(
    "/plans",
    response_model=List[PlanResponse],
    summary="List billing plans",
    description="Get all available billing plans and their features.",
)
async def list_plans():
    """List all available billing plans."""
    service = get_billing_service()
    plans = service.list_plans()
    return [plan_to_response(p) for p in plans]


@router.get(
    "/plans/{plan_id}",
    response_model=PlanResponse,
    summary="Get plan details",
    description="Get details for a specific billing plan.",
)
async def get_plan(plan_id: str):
    """Get details for a specific plan."""
    try:
        plan = BillingPlan(plan_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Plan not found: {plan_id}")

    service = get_billing_service()
    plan_details = service.get_plan_details(plan)
    return plan_to_response(plan_details)


@router.get(
    "/subscription",
    response_model=Optional[SubscriptionResponse],
    summary="Get current subscription",
    description="Get the current subscription for the authenticated user's organization.",
)
async def get_subscription(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get current subscription."""
    service = get_billing_service()
    customer_id = getattr(current_user, "customer_id", "default")

    subscription = await service.get_customer_subscription(customer_id)
    if not subscription:
        return None

    return subscription_to_response(subscription)


@router.post(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Create subscription",
    description="Create a new subscription for the organization.",
)
async def create_subscription(
    request: SubscriptionCreateRequest,
    current_user: User = Depends(require_role("admin", "billing_admin")),  # noqa: B008
):
    """Create a new subscription."""
    try:
        plan = BillingPlan(request.plan)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {request.plan}")

    if request.billing_cycle not in ("monthly", "annual"):
        raise HTTPException(
            status_code=400, detail="billing_cycle must be 'monthly' or 'annual'"
        )

    service = get_billing_service()
    customer_id = getattr(current_user, "customer_id", "default")

    # Check for existing subscription
    existing = await service.get_customer_subscription(customer_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Customer already has an active subscription. Update or cancel first.",
        )

    try:
        subscription = await service.create_subscription(
            customer_id=customer_id,
            plan=plan,
            billing_cycle=request.billing_cycle,
            payment_method_id=request.payment_method_id,
            trial_days=request.trial_days,
        )
        return subscription_to_response(subscription)

    except Exception as e:
        logger.error("Error creating subscription: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create subscription")


@router.put(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Update subscription",
    description="Update the current subscription (upgrade/downgrade plan).",
)
async def update_subscription(
    request: SubscriptionUpdateRequest,
    current_user: User = Depends(require_role("admin", "billing_admin")),  # noqa: B008
):
    """Update current subscription."""
    service = get_billing_service()
    customer_id = getattr(current_user, "customer_id", "default")

    subscription = await service.get_customer_subscription(customer_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")

    new_plan = None
    if request.plan:
        try:
            new_plan = BillingPlan(request.plan)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid plan: {request.plan}")

    if request.billing_cycle and request.billing_cycle not in ("monthly", "annual"):
        raise HTTPException(
            status_code=400, detail="billing_cycle must be 'monthly' or 'annual'"
        )

    try:
        updated = await service.update_subscription(
            subscription_id=subscription.subscription_id,
            new_plan=new_plan,
            billing_cycle=request.billing_cycle,
        )
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update subscription")
        return subscription_to_response(updated)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating subscription: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update subscription")


@router.delete(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Cancel subscription",
    description="Cancel the current subscription.",
)
async def cancel_subscription(
    at_period_end: bool = Query(  # noqa: B008
        default=True, description="Cancel at end of billing period"
    ),
    current_user: User = Depends(require_role("admin", "billing_admin")),  # noqa: B008
):
    """Cancel current subscription."""
    service = get_billing_service()
    customer_id = getattr(current_user, "customer_id", "default")

    subscription = await service.get_customer_subscription(customer_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")

    try:
        canceled = await service.cancel_subscription(
            subscription_id=subscription.subscription_id,
            at_period_end=at_period_end,
        )
        if not canceled:
            raise HTTPException(status_code=500, detail="Failed to cancel subscription")
        return subscription_to_response(canceled)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error canceling subscription: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")


@router.get(
    "/usage",
    response_model=UsageSummaryResponse,
    summary="Get usage summary",
    description="Get usage summary for the current billing period.",
)
async def get_usage_summary(
    days: int = Query(  # noqa: B008
        default=30, ge=1, le=365, description="Days to include"
    ),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get usage summary."""
    service = get_billing_service()
    customer_id = getattr(current_user, "customer_id", "default")

    try:
        summary = await service.get_usage_summary(customer_id=customer_id, days=days)
        return UsageSummaryResponse(**summary)

    except Exception as e:
        logger.error("Error getting usage summary: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve usage summary")


@router.post(
    "/usage",
    response_model=UsageRecordResponse,
    summary="Record usage",
    description="Record usage for metered billing (internal use).",
)
async def record_usage(
    request: UsageRecordRequest,
    current_user: User = Depends(require_role("admin", "system")),  # noqa: B008
):
    """Record usage for metered billing."""
    service = get_billing_service()
    customer_id = getattr(current_user, "customer_id", "default")

    valid_metrics = ["llm_tokens", "agent_executions", "api_calls_over_limit"]
    if request.metric_name not in valid_metrics:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric_name. Valid: {valid_metrics}",
        )

    try:
        record = await service.record_usage(
            customer_id=customer_id,
            metric_name=request.metric_name,
            quantity=request.quantity,
            metadata=request.metadata,
        )
        return UsageRecordResponse(
            record_id=record.record_id,
            metric_name=record.metric_name,
            quantity=record.quantity,
            total_cents=record.total_cents,
            timestamp=record.timestamp.isoformat(),
        )

    except ValueError as e:
        logger.warning(f"Usage recording validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid usage record parameters")
    except Exception as e:
        logger.error("Error recording usage: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to record usage")


@router.get(
    "/invoices",
    response_model=List[InvoiceResponse],
    summary="List invoices",
    description="Get invoice history for the organization.",
)
async def list_invoices(
    limit: int = Query(  # noqa: B008
        default=10, ge=1, le=100, description="Max invoices to return"
    ),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """List invoices."""
    service = get_billing_service()
    customer_id = getattr(current_user, "customer_id", "default")

    invoices = await service.list_invoices(customer_id=customer_id, limit=limit)
    return [invoice_to_response(inv) for inv in invoices]


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get invoice",
    description="Get details for a specific invoice.",
)
async def get_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get invoice by ID."""
    service = get_billing_service()
    customer_id = getattr(current_user, "customer_id", "default")

    invoice = await service.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Verify ownership
    if invoice.customer_id != customer_id:
        user_roles = getattr(current_user, "roles", [])
        if "admin" not in user_roles:
            raise HTTPException(status_code=403, detail="Access denied")

    return invoice_to_response(invoice)


@router.get(
    "/payment-methods",
    response_model=List[PaymentMethodResponse],
    summary="List payment methods",
    description="Get saved payment methods for the organization.",
)
async def list_payment_methods(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """List payment methods."""
    service = get_billing_service()
    customer_id = getattr(current_user, "customer_id", "default")

    methods = await service.list_payment_methods(customer_id)
    return [payment_method_to_response(pm) for pm in methods]


@router.post(
    "/payment-methods",
    response_model=PaymentMethodResponse,
    summary="Add payment method",
    description="Add a new payment method to the organization.",
)
async def add_payment_method(
    request: PaymentMethodRequest,
    current_user: User = Depends(require_role("admin", "billing_admin")),  # noqa: B008
):
    """Add a payment method."""
    service = get_billing_service()
    customer_id = getattr(current_user, "customer_id", "default")

    try:
        method = await service.add_payment_method(
            customer_id=customer_id,
            stripe_payment_method_id=request.stripe_payment_method_id,
            set_as_default=request.set_as_default,
        )
        return payment_method_to_response(method)

    except Exception as e:
        logger.error("Error adding payment method: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add payment method")
