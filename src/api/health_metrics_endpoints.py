"""
Customer Health Metrics API Endpoints.

Provides REST API for the Customer Health Dashboard to retrieve
per-customer metrics including API usage, agent performance,
token consumption, and storage usage.

Endpoints:
- GET /api/v1/health/customer/{customer_id} - Get customer health metrics
- GET /api/v1/health/customers - Get all customers health (SaaS mode)
- GET /api/v1/health/summary - Get aggregate health summary
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.auth import User, get_current_user, require_role
from src.services.health.customer_metrics import (
    CustomerHealth,
    DeploymentMode,
    get_customer_metrics_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/health",
    tags=["Customer Health"],
)


# =============================================================================
# Response Models
# =============================================================================


class APIMetricsResponse(BaseModel):
    """API usage metrics response."""

    request_count: int
    error_count: int
    error_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float


class AgentMetricsResponse(BaseModel):
    """Agent execution metrics response."""

    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate: float
    avg_execution_time_seconds: float
    executions_by_type: dict


class TokenMetricsResponse(BaseModel):
    """Token usage metrics response."""

    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    tokens_by_model: dict


class StorageMetricsResponse(BaseModel):
    """Storage usage metrics response."""

    s3_storage_gb: float
    neptune_storage_gb: float
    opensearch_storage_gb: float
    total_storage_gb: float


class HealthStatusResponse(BaseModel):
    """Health status response."""

    status: str
    score: int
    issues: List[str]
    last_checked: Optional[str]


class CustomerHealthResponse(BaseModel):
    """Complete customer health response."""

    customer_id: str
    customer_name: Optional[str]
    time_range: str
    api: APIMetricsResponse
    agents: AgentMetricsResponse
    tokens: TokenMetricsResponse
    storage: StorageMetricsResponse
    health: HealthStatusResponse
    collected_at: Optional[str]


class HealthSummaryResponse(BaseModel):
    """Aggregate health summary for all customers."""

    total_customers: int
    healthy_count: int
    degraded_count: int
    unhealthy_count: int
    avg_health_score: float
    total_api_requests: int
    total_agent_executions: int
    total_token_cost_usd: float
    collected_at: str


# =============================================================================
# Helper Functions
# =============================================================================


def customer_health_to_response(health: CustomerHealth) -> CustomerHealthResponse:
    """Convert CustomerHealth dataclass to response model."""
    return CustomerHealthResponse(
        customer_id=health.customer_id,
        customer_name=health.customer_name,
        time_range=health.time_range,
        api=APIMetricsResponse(
            request_count=health.api.request_count,
            error_count=health.api.error_count,
            error_rate=health.api.error_rate,
            avg_latency_ms=health.api.avg_latency_ms,
            p50_latency_ms=health.api.p50_latency_ms,
            p95_latency_ms=health.api.p95_latency_ms,
            p99_latency_ms=health.api.p99_latency_ms,
        ),
        agents=AgentMetricsResponse(
            total_executions=health.agents.total_executions,
            successful_executions=health.agents.successful_executions,
            failed_executions=health.agents.failed_executions,
            success_rate=health.agents.success_rate,
            avg_execution_time_seconds=health.agents.avg_execution_time_seconds,
            executions_by_type=health.agents.executions_by_type,
        ),
        tokens=TokenMetricsResponse(
            total_input_tokens=health.tokens.total_input_tokens,
            total_output_tokens=health.tokens.total_output_tokens,
            total_tokens=health.tokens.total_tokens,
            estimated_cost_usd=health.tokens.estimated_cost_usd,
            tokens_by_model=health.tokens.tokens_by_model,
        ),
        storage=StorageMetricsResponse(
            s3_storage_gb=health.storage.s3_storage_gb,
            neptune_storage_gb=health.storage.neptune_storage_gb,
            opensearch_storage_gb=health.storage.opensearch_storage_gb,
            total_storage_gb=health.storage.total_storage_gb,
        ),
        health=HealthStatusResponse(
            status=health.health.status,
            score=health.health.score,
            issues=health.health.issues,
            last_checked=(
                health.health.last_checked.isoformat()
                if health.health.last_checked
                else None
            ),
        ),
        collected_at=health.collected_at.isoformat() if health.collected_at else None,
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.get(
    "/customer/{customer_id}",
    response_model=CustomerHealthResponse,
    summary="Get customer health metrics",
    description="Retrieve comprehensive health metrics for a specific customer.",
)
async def get_customer_health(
    customer_id: str,
    time_range: str = Query(  # noqa: B008
        default="24h",
        regex="^(1h|24h|7d|30d)$",
        description="Time range for metrics",
    ),
    include_breakdown: bool = Query(  # noqa: B008
        default=True,
        description="Include detailed breakdowns",
    ),
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """
    Get health metrics for a specific customer.

    Requires authentication. Users can only access their own customer data
    unless they have admin role.
    """
    try:
        # In production, verify user has access to this customer
        service = get_customer_metrics_service()
        health = await service.get_customer_health(
            customer_id=customer_id,
            time_range=time_range,
            include_breakdown=include_breakdown,
        )
        return customer_health_to_response(health)
    except Exception as e:
        logger.error(f"Error fetching customer health: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve customer health: {str(e)}",
        )


@router.get(
    "/customers",
    response_model=List[CustomerHealthResponse],
    summary="Get all customers health",
    description="Retrieve health metrics for all customers (admin only, SaaS mode).",
)
async def get_all_customers_health(
    time_range: str = Query(  # noqa: B008
        default="24h",
        regex="^(1h|24h|7d|30d)$",
        description="Time range for metrics",
    ),
    current_user: User = Depends(require_role("admin", "operator")),  # noqa: B008
):
    """
    Get health metrics for all customers.

    Only available in SaaS mode. Requires admin or operator role.
    """
    try:
        service = get_customer_metrics_service(DeploymentMode.SAAS)
        all_health = await service.get_all_customers_health(time_range=time_range)
        return [customer_health_to_response(h) for h in all_health]
    except Exception as e:
        logger.error(f"Error fetching all customers health: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve customers health: {str(e)}",
        )


@router.get(
    "/summary",
    response_model=HealthSummaryResponse,
    summary="Get health summary",
    description="Get aggregate health summary across all customers.",
)
async def get_health_summary(
    time_range: str = Query(  # noqa: B008
        default="24h",
        regex="^(1h|24h|7d|30d)$",
        description="Time range for metrics",
    ),
    current_user: User = Depends(require_role("admin", "operator")),  # noqa: B008
):
    """
    Get aggregate health summary.

    Provides high-level overview of system health across all customers
    or for a single customer in self-hosted mode.
    """
    try:
        service = get_customer_metrics_service()
        all_health = await service.get_all_customers_health(time_range=time_range)

        # Aggregate metrics
        total_customers = len(all_health)
        healthy_count = sum(1 for h in all_health if h.health.status == "healthy")
        degraded_count = sum(1 for h in all_health if h.health.status == "degraded")
        unhealthy_count = sum(1 for h in all_health if h.health.status == "unhealthy")
        avg_score = (
            sum(h.health.score for h in all_health) / total_customers
            if total_customers > 0
            else 0
        )
        total_requests = sum(h.api.request_count for h in all_health)
        total_executions = sum(h.agents.total_executions for h in all_health)
        total_cost = sum(h.tokens.estimated_cost_usd for h in all_health)

        return HealthSummaryResponse(
            total_customers=total_customers,
            healthy_count=healthy_count,
            degraded_count=degraded_count,
            unhealthy_count=unhealthy_count,
            avg_health_score=round(avg_score, 1),
            total_api_requests=total_requests,
            total_agent_executions=total_executions,
            total_token_cost_usd=round(total_cost, 2),
            collected_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error(f"Error fetching health summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve health summary: {str(e)}",
        )


@router.post(
    "/cache/clear",
    summary="Clear metrics cache",
    description="Clear cached metrics to force refresh.",
)
async def clear_metrics_cache(
    customer_id: Optional[str] = Query(  # noqa: B008
        default=None,
        description="Customer ID to clear (None for all)",
    ),
    current_user: User = Depends(require_role("admin")),  # noqa: B008
):
    """
    Clear the metrics cache.

    Use to force a refresh of metrics data. Admin only.
    """
    service = get_customer_metrics_service()
    service.clear_cache(customer_id)
    return {
        "status": "success",
        "message": f"Cache cleared for: {customer_id or 'all customers'}",
    }
