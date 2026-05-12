"""Project Aura - Internal System Health Endpoint.

Backs the ``HealthCheckModal`` UI surface (#182 Wave 9). Previously
the modal generated inline mock data (``generateMockHealthData`` with
fabricated metrics for 11 services). This endpoint exposes the same
shape with an honest zero-state body. Real per-service health probes
(Neptune ping, OpenSearch cluster status, agent process counts) plug
behind this handler later without changing the frontend contract.

NOT to be confused with ``health_metrics_endpoints.py`` which exposes
customer-tenant health (SaaS-mode reporting). This file is internal
infrastructure status.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system-health", tags=["system-health"])


# =============================================================================
# Response models
# =============================================================================


class ServiceMetric(BaseModel):
    label: str
    value: str


class ServiceStatus(BaseModel):
    name: str
    status: str  # 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
    metrics: list[ServiceMetric] = Field(default_factory=list)


class CategoryHealth(BaseModel):
    status: str  # 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
    services: list[ServiceStatus] = Field(default_factory=list)


class SystemHealthResponse(BaseModel):
    """Internal system health rollup matching the HealthCheckModal shape."""

    overallStatus: str = "unknown"  # 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
    summary: str = ""
    healthyServices: int = 0
    degradedServices: int = 0
    unhealthyServices: int = 0
    lastUpdated: str  # ISO 8601
    categories: dict[str, CategoryHealth] = Field(default_factory=dict)


# =============================================================================
# Endpoint
# =============================================================================


@router.get(
    "",
    response_model=SystemHealthResponse,
    summary="Internal system services health rollup",
)
async def get_system_health() -> SystemHealthResponse:
    """Return internal system health rollup.

    Wave 9 (#182): returns an honest "unknown" zero-state response.
    Real per-service probes (Neptune Gremlin status, OpenSearch
    cluster health, agent process counts, EKS pod readiness) will
    plug behind this handler. CloudWatch remains the authoritative
    source for infrastructure metrics; this endpoint is a curated
    customer-facing rollup.
    """
    return SystemHealthResponse(
        overallStatus="unknown",
        summary=(
            "System health probes are not yet enabled. CloudWatch is the "
            "authoritative source for live infrastructure metrics."
        ),
        healthyServices=0,
        degradedServices=0,
        unhealthyServices=0,
        lastUpdated=datetime.now(timezone.utc).isoformat(),
        categories={},
    )
