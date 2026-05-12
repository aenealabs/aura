"""Project Aura - Top-Level Dashboard Metrics Endpoints.

Backs the four top-level dashboard widgets that previously rendered
inline mock literals (#163 CRITICAL "4 top-level dashboard widgets also
import from MOCK"):

- ``MTTRWidget``                 -> ``/api/v1/dashboard/metrics/mttr``
- ``AssetCriticalityWidget``     -> ``/api/v1/dashboard/metrics/asset-criticality``
- ``ComplianceDriftWidget``      -> ``/api/v1/dashboard/metrics/compliance-drift``
- ``InsiderRiskWidget``          -> ``/api/v1/dashboard/metrics/insider-risk``

This is a contract-first stub layer (same pattern as the ADR-083
runtime-security router landed in Wave 3): each endpoint returns a
well-formed empty/zero-state response so the widget renders its
"no data" view instead of 404-ing. The Pydantic response models match
the JSDoc typedefs the frontend widgets consume so the frontend contract
is locked while the real service code is built behind these handlers.

Real backend wiring (Neptune metric aggregation, compliance-controls
service hookup, UEBA risk scoring) is tracked separately in #163's
"Backend endpoint required" bucket.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dashboard/metrics", tags=["dashboard-metrics"])


# =============================================================================
# MTTR (Mean Time To Remediate)
# =============================================================================


class MTTRMetrics(BaseModel):
    """Mean-time-to-remediate metrics matching the frontend MTTRWidget typedef."""

    current_mttr_hours: float = 0.0
    target_mttr_hours: float = 24.0
    previous_mttr_hours: float = 0.0
    critical_mttr_hours: float = 0.0
    high_mttr_hours: float = 0.0
    medium_mttr_hours: float = 0.0
    open_count: int = 0
    closed_last_7d: int = 0


@router.get(
    "/mttr",
    response_model=MTTRMetrics,
    summary="Mean Time To Remediate metrics",
)
async def get_mttr_metrics() -> MTTRMetrics:
    """Return MTTR rollup.

    Stub layer (#163): returns a zero-state response. Real
    implementation aggregates remediation timestamps from the findings
    DDB table and the patch-approval audit log.
    """
    return MTTRMetrics()


# =============================================================================
# Asset Criticality
# =============================================================================


class AssetCriticalityEntry(BaseModel):
    """One row of the asset-criticality leaderboard."""

    asset_id: str
    criticality_score: int = Field(..., ge=0, le=10)
    data_classification: str  # Restricted | Confidential | Internal | Public
    business_owner: str


class AssetCriticalityResponse(BaseModel):
    assets: list[AssetCriticalityEntry] = Field(default_factory=list)


@router.get(
    "/asset-criticality",
    response_model=AssetCriticalityResponse,
    summary="Top critical assets by score",
)
async def get_asset_criticality() -> AssetCriticalityResponse:
    """Return the top-N most critical assets by criticality_score.

    Stub layer (#163): returns an empty list. Real implementation reads
    the asset catalog and joins with data-classification tags + business
    ownership from the SCM provider.
    """
    return AssetCriticalityResponse()


# =============================================================================
# Compliance Drift
# =============================================================================


class ComplianceFramework(BaseModel):
    name: str  # e.g. 'SOC 2', 'HIPAA', 'NIST 800-53'
    passing: int = 0
    failing: int = 0
    total: int = 0


class ComplianceControlFailure(BaseModel):
    id: str
    control: str  # e.g. 'AC-2.3'
    framework: str
    description: str
    daysOpen: int = 0


class ComplianceDriftResponse(BaseModel):
    frameworks: list[ComplianceFramework] = Field(default_factory=list)
    recentFailures: list[ComplianceControlFailure] = Field(default_factory=list)


@router.get(
    "/compliance-drift",
    response_model=ComplianceDriftResponse,
    summary="Per-framework control posture + recent failures",
)
async def get_compliance_drift() -> ComplianceDriftResponse:
    """Return per-framework passing/failing control counts + recent failures.

    Stub layer (#163): returns empty arrays. Real implementation reads
    the compliance-controls evaluation results table.
    """
    return ComplianceDriftResponse()


# =============================================================================
# Insider Risk
# =============================================================================


class InsiderRiskResponse(BaseModel):
    elevated_count: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    total_monitored: int = 0
    trend: str = "stable"  # 'up' | 'down' | 'stable'
    trend_delta: int = 0
    last_escalation: Optional[str] = None  # ISO 8601


@router.get(
    "/insider-risk",
    response_model=InsiderRiskResponse,
    summary="Insider-risk rollup (count by tier + trend)",
)
async def get_insider_risk() -> InsiderRiskResponse:
    """Return insider-risk tier counts and 7-day trend.

    Stub layer (#163): returns zero-state. Real implementation reads
    UEBA risk scores from the capability-governance anomaly detector.
    """
    return InsiderRiskResponse()


# =============================================================================
# Health
# =============================================================================


class HealthResponse(BaseModel):
    status: str
    timestamp: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check for the dashboard-metrics surface",
)
async def health() -> HealthResponse:
    """Always returns OK; widgets use this to gate showing the panel."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
