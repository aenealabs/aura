"""
AWS Marketplace API Endpoints.

Provides REST API for AWS Marketplace SaaS integration:
- POST /api/v1/marketplace/resolve - Resolve customer from registration token
- POST /api/v1/marketplace/sns-webhook - Handle SNS notifications
- GET /api/v1/marketplace/customers - List marketplace customers
- GET /api/v1/marketplace/customers/{id} - Get customer details
- PUT /api/v1/marketplace/customers/{id} - Update customer info
- GET /api/v1/marketplace/entitlements - Check entitlements
- POST /api/v1/marketplace/usage - Record usage
- POST /api/v1/marketplace/usage/batch - Batch usage submission
- GET /api/v1/marketplace/usage/summary - Get usage summary
- POST /api/v1/marketplace/meter - Submit pending usage to AWS
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user, require_role
from src.services.marketplace_service import (
    EntitlementCheck,
    EntitlementStatus,
    MarketplaceCustomer,
    MeteringResult,
    UsageDimension,
    UsageRecord,
    get_marketplace_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/marketplace",
    tags=["AWS Marketplace"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class ResolveCustomerRequest(BaseModel):
    """Request to resolve customer from AWS Marketplace token."""

    registration_token: str = Field(
        ..., description="Registration token from AWS Marketplace redirect"
    )


class MarketplaceCustomerResponse(BaseModel):
    """Marketplace customer response."""

    customer_id: str
    aws_customer_id: str
    product_code: str
    dimension: str
    entitlement_status: str
    subscription_start: str
    subscription_end: Optional[str]
    aws_account_id: Optional[str]
    customer_email: Optional[str]
    company_name: Optional[str]
    created_at: str
    updated_at: str


class UpdateCustomerRequest(BaseModel):
    """Request to update customer information."""

    email: Optional[str] = Field(default=None, description="Customer email")
    company_name: Optional[str] = Field(default=None, description="Company name")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


class EntitlementResponse(BaseModel):
    """Entitlement check response."""

    is_entitled: bool
    product_code: str
    dimension: str
    value: int
    expiration: Optional[str]
    status: str


class RecordUsageRequest(BaseModel):
    """Request to record usage."""

    dimension: str = Field(
        ...,
        description="Usage dimension: Developers, LLMTokens, AgentExecutions, APICalls, StorageGB, GraphNodes",
    )
    quantity: int = Field(..., ge=1, description="Usage quantity")
    timestamp: Optional[str] = Field(default=None, description="Optional ISO timestamp")


class BatchUsageRequest(BaseModel):
    """Request for batch usage submission."""

    records: List[Dict[str, Any]] = Field(
        ..., description="List of {dimension, quantity, timestamp}"
    )


class UsageRecordResponse(BaseModel):
    """Usage record response."""

    record_id: str
    customer_id: str
    product_code: str
    dimension: str
    quantity: int
    timestamp: str
    reported: bool
    report_id: Optional[str]


class MeteringResultResponse(BaseModel):
    """Metering result response."""

    success: bool
    metering_record_id: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    timestamp: str


class UsageSummaryResponse(BaseModel):
    """Usage summary response."""

    customer_id: str
    product_code: str
    period_days: int
    usage_by_dimension: Dict[str, int]
    total_records: int


# =============================================================================
# Helper Functions
# =============================================================================


def customer_to_response(customer: MarketplaceCustomer) -> MarketplaceCustomerResponse:
    """Convert MarketplaceCustomer to response model."""
    return MarketplaceCustomerResponse(
        customer_id=customer.customer_id,
        aws_customer_id=customer.aws_customer_id,
        product_code=customer.product_code,
        dimension=customer.dimension,
        entitlement_status=customer.entitlement_status.value,
        subscription_start=customer.subscription_start.isoformat(),
        subscription_end=(
            customer.subscription_end.isoformat() if customer.subscription_end else None
        ),
        aws_account_id=customer.aws_account_id,
        customer_email=customer.customer_email,
        company_name=customer.company_name,
        created_at=customer.created_at.isoformat(),
        updated_at=customer.updated_at.isoformat(),
    )


def entitlement_to_response(ent: EntitlementCheck) -> EntitlementResponse:
    """Convert EntitlementCheck to response model."""
    return EntitlementResponse(
        is_entitled=ent.is_entitled,
        product_code=ent.product_code,
        dimension=ent.dimension,
        value=ent.value,
        expiration=ent.expiration.isoformat() if ent.expiration else None,
        status=ent.status.value,
    )


def usage_record_to_response(record: UsageRecord) -> UsageRecordResponse:
    """Convert UsageRecord to response model."""
    return UsageRecordResponse(
        record_id=record.record_id,
        customer_id=record.customer_id,
        product_code=record.product_code,
        dimension=record.dimension.value,
        quantity=record.quantity,
        timestamp=record.timestamp.isoformat(),
        reported=record.reported,
        report_id=record.report_id,
    )


def metering_result_to_response(result: MeteringResult) -> MeteringResultResponse:
    """Convert MeteringResult to response model."""
    return MeteringResultResponse(
        success=result.success,
        metering_record_id=result.metering_record_id,
        error_code=result.error_code,
        error_message=result.error_message,
        timestamp=result.timestamp.isoformat(),
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.post(
    "/resolve",
    response_model=MarketplaceCustomerResponse,
    summary="Resolve customer from token",
    description="Resolve customer from AWS Marketplace registration token after subscription.",
)
async def resolve_customer(
    request: ResolveCustomerRequest,
):
    """
    Resolve customer from AWS Marketplace registration token.

    Called after customer completes AWS Marketplace subscription and
    is redirected to our application with the registration token.
    """
    service = get_marketplace_service()

    customer = await service.resolve_customer(request.registration_token)
    if not customer:
        raise HTTPException(
            status_code=400,
            detail="Failed to resolve customer. Invalid or expired token.",
        )

    return customer_to_response(customer)


@router.post(
    "/sns-webhook",
    summary="Handle SNS notification",
    description="Webhook endpoint for AWS Marketplace SNS notifications.",
)
async def handle_sns_webhook(
    request: Request,
    x_amz_sns_message_type: Optional[str] = Header(  # noqa: B008
        default=None, alias="x-amz-sns-message-type"
    ),
):
    """
    Handle SNS notifications from AWS Marketplace.

    AWS Marketplace sends notifications for subscription events:
    - subscribe-success
    - unsubscribe-pending
    - unsubscribe-success
    - entitlement-updated
    """
    try:
        body = await request.body()
        message = json.loads(body)

        # Handle SNS subscription confirmation
        if x_amz_sns_message_type == "SubscriptionConfirmation":
            subscribe_url = message.get("SubscribeURL")
            logger.info(f"SNS subscription confirmation required: {subscribe_url}")
            return {
                "status": "subscription_confirmation_required",
                "url": subscribe_url,
            }

        # Handle notification
        if x_amz_sns_message_type == "Notification":
            # Parse the actual message from SNS wrapper
            notification_message = json.loads(message.get("Message", "{}"))

            service = get_marketplace_service()
            success = await service.handle_sns_notification(notification_message)

            if success:
                return {"status": "processed"}
            else:
                raise HTTPException(
                    status_code=400, detail="Failed to process notification"
                )

        return {"status": "unknown_message_type"}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        logger.error("Error handling SNS webhook: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to handle SNS webhook")


@router.get(
    "/customers",
    response_model=List[MarketplaceCustomerResponse],
    summary="List marketplace customers",
    description="List all AWS Marketplace customers (admin only).",
)
async def list_customers(
    status: Optional[str] = Query(  # noqa: B008
        default=None,
        description="Filter by status: active, suspended, cancelled, expired, pending",
    ),
    limit: int = Query(  # noqa: B008
        default=100, ge=1, le=500, description="Max customers"
    ),  # noqa: B008
    current_user: User = Depends(require_role("admin", "billing_admin")),  # noqa: B008
):
    """List all marketplace customers."""
    service = get_marketplace_service()

    status_filter = None
    if status:
        try:
            status_filter = EntitlementStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid status. Valid: active, suspended, cancelled, expired, pending",
            )

    customers = await service.list_customers(status=status_filter, limit=limit)
    return [customer_to_response(c) for c in customers]


@router.get(
    "/customers/{customer_id}",
    response_model=MarketplaceCustomerResponse,
    summary="Get customer details",
    description="Get details for a specific marketplace customer.",
)
async def get_customer(
    customer_id: str,
    current_user: User = Depends(require_role("admin", "billing_admin")),  # noqa: B008
):
    """Get marketplace customer by ID."""
    service = get_marketplace_service()

    customer = await service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return customer_to_response(customer)


@router.put(
    "/customers/{customer_id}",
    response_model=MarketplaceCustomerResponse,
    summary="Update customer info",
    description="Update customer information (email, company name).",
)
async def update_customer(
    customer_id: str,
    request: UpdateCustomerRequest,
    current_user: User = Depends(require_role("admin", "billing_admin")),  # noqa: B008
):
    """Update marketplace customer information."""
    service = get_marketplace_service()

    customer = await service.update_customer_info(
        customer_id=customer_id,
        email=request.email,
        company_name=request.company_name,
        metadata=request.metadata,
    )

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return customer_to_response(customer)


@router.get(
    "/entitlements",
    response_model=List[EntitlementResponse],
    summary="Check entitlements",
    description="Check entitlements for the current customer.",
)
async def check_entitlements(
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Check entitlements for current user's customer."""
    service = get_marketplace_service()
    customer_id = getattr(current_user, "marketplace_customer_id", None)

    if not customer_id:
        # Try to find by regular customer_id
        customer_id = getattr(current_user, "customer_id", None)

    if not customer_id:
        raise HTTPException(
            status_code=400, detail="No marketplace customer associated with user"
        )

    entitlements = await service.check_entitlements(customer_id)
    return [entitlement_to_response(e) for e in entitlements]


@router.get(
    "/entitlements/{customer_id}",
    response_model=List[EntitlementResponse],
    summary="Check customer entitlements",
    description="Check entitlements for a specific customer (admin only).",
)
async def check_customer_entitlements(
    customer_id: str,
    current_user: User = Depends(require_role("admin", "billing_admin")),  # noqa: B008
):
    """Check entitlements for a specific customer."""
    service = get_marketplace_service()

    customer = await service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    entitlements = await service.check_entitlements(customer_id)
    return [entitlement_to_response(e) for e in entitlements]


@router.get(
    "/verify",
    summary="Verify entitlement",
    description="Quick verification of customer entitlement.",
)
async def verify_entitlement(
    dimension: str = Query(  # noqa: B008
        default="Base", description="Dimension to verify"
    ),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Quick entitlement verification for access control."""
    service = get_marketplace_service()
    customer_id = getattr(
        current_user,
        "marketplace_customer_id",
        getattr(current_user, "customer_id", None),
    )

    if not customer_id:
        return {"entitled": False, "reason": "No marketplace customer"}

    is_entitled = await service.verify_entitlement(customer_id, dimension)
    return {
        "entitled": is_entitled,
        "dimension": dimension,
        "customer_id": customer_id,
    }


@router.post(
    "/usage",
    response_model=UsageRecordResponse,
    summary="Record usage",
    description="Record usage for metered billing.",
)
async def record_usage(
    request: RecordUsageRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Record usage for metered billing."""
    service = get_marketplace_service()
    customer_id = getattr(
        current_user,
        "marketplace_customer_id",
        getattr(current_user, "customer_id", None),
    )

    if not customer_id:
        raise HTTPException(
            status_code=400, detail="No marketplace customer associated with user"
        )

    # Validate dimension
    try:
        dimension = UsageDimension(request.dimension)
    except ValueError:
        valid_dims = [d.value for d in UsageDimension]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dimension. Valid: {valid_dims}",
        )

    try:
        record = await service.record_usage(
            customer_id=customer_id,
            dimension=dimension,
            quantity=request.quantity,
        )
        return usage_record_to_response(record)

    except ValueError as e:
        logger.warning(f"Usage recording validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid usage record parameters")
    except Exception as e:
        logger.error("Error recording usage: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to record usage")


@router.post(
    "/usage/batch",
    response_model=MeteringResultResponse,
    summary="Batch usage submission",
    description="Submit batch usage records for a customer (admin/system only).",
)
async def batch_usage(
    customer_id: str,
    request: BatchUsageRequest,
    current_user: User = Depends(require_role("admin", "system")),  # noqa: B008
):
    """Submit batch usage records."""
    service = get_marketplace_service()

    # Validate dimensions
    for record in request.records:
        if "dimension" not in record or "quantity" not in record:
            raise HTTPException(
                status_code=400,
                detail="Each record must have 'dimension' and 'quantity'",
            )

    result = await service.batch_meter_usage(customer_id, request.records)
    return metering_result_to_response(result)


@router.get(
    "/usage/summary",
    response_model=UsageSummaryResponse,
    summary="Get usage summary",
    description="Get usage summary for the current customer.",
)
async def get_usage_summary(
    days: int = Query(  # noqa: B008
        default=30, ge=1, le=365, description="Days of history"
    ),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Get usage summary."""
    service = get_marketplace_service()
    customer_id = getattr(
        current_user,
        "marketplace_customer_id",
        getattr(current_user, "customer_id", None),
    )

    if not customer_id:
        raise HTTPException(
            status_code=400, detail="No marketplace customer associated with user"
        )

    summary = await service.get_usage_summary(customer_id, days=days)
    return UsageSummaryResponse(**summary)


@router.get(
    "/usage/summary/{customer_id}",
    response_model=UsageSummaryResponse,
    summary="Get customer usage summary",
    description="Get usage summary for a specific customer (admin only).",
)
async def get_customer_usage_summary(
    customer_id: str,
    days: int = Query(  # noqa: B008
        default=30, ge=1, le=365, description="Days of history"
    ),  # noqa: B008
    current_user: User = Depends(require_role("admin", "billing_admin")),  # noqa: B008
):
    """Get usage summary for a specific customer."""
    service = get_marketplace_service()

    customer = await service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    summary = await service.get_usage_summary(customer_id, days=days)
    return UsageSummaryResponse(**summary)


@router.post(
    "/meter",
    response_model=List[MeteringResultResponse],
    summary="Submit pending usage",
    description="Submit all pending usage records to AWS Marketplace (system only).",
)
async def submit_metering(
    current_user: User = Depends(require_role("admin", "system")),  # noqa: B008
):
    """
    Submit pending usage to AWS Marketplace.

    This endpoint should be called periodically (e.g., hourly)
    by a scheduled task to report accumulated usage.
    """
    service = get_marketplace_service()

    results = await service.submit_usage_batch()
    return [metering_result_to_response(r) for r in results]


@router.get(
    "/report/revenue",
    summary="Get revenue report",
    description="Get revenue report across all customers (admin only).",
)
async def get_revenue_report(
    days: int = Query(  # noqa: B008
        default=30, ge=1, le=365, description="Days of history"
    ),  # noqa: B008
    current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    """Get revenue report."""
    service = get_marketplace_service()

    from datetime import datetime, timedelta, timezone

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    report = await service.get_revenue_report(
        start_date=start_date,
        end_date=end_date,
    )

    return report
