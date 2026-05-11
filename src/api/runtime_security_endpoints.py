"""Project Aura - Runtime Security API Endpoints (ADR-077, ADR-083).

Exposes the 12 ``/api/v1/runtime-security/*`` endpoints the frontend's
``runtimeSecurityApi.js`` expects. Currently a stub layer: every
endpoint returns a well-formed empty response so the ADR-083 widgets
render the "no data" state rather than 404. The behind-the-router
service code (``src/services/runtime_security/*``) already exists; the
wave-3 GTM remediation (#163) wires the HTTP surface in front of it.

Each handler is marked ``TODO(#163-wave4)`` where a real service call
should land in wave 4. The Pydantic response models match the JSDoc
typedefs in ``frontend/src/services/runtimeSecurityApi.js`` so the
frontend contract is locked even while the bodies are stubs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/runtime-security", tags=["runtime-security"])


# =============================================================================
# Admission Controller (ADR-077)
# =============================================================================


class AdmissionDecision(BaseModel):
    """One admission-controller decision matching the frontend typedef."""

    decision_id: str
    decision: str  # ALLOW | DENY | WARN
    resource_type: str  # pod | deployment | service | ...
    resource_name: str
    namespace: str
    policy_name: str
    reason: str
    timestamp: str  # ISO 8601
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdmissionDecisionsSummary(BaseModel):
    allow_count: int = 0
    deny_count: int = 0
    warn_count: int = 0
    total_24h: int = 0


class AdmissionDecisionsResponse(BaseModel):
    decisions: list[AdmissionDecision] = Field(default_factory=list)
    summary: AdmissionDecisionsSummary = Field(
        default_factory=AdmissionDecisionsSummary
    )


class AdmissionPolicy(BaseModel):
    policy_id: str
    name: str
    enabled: bool
    rule_count: int = 0
    last_updated: str  # ISO 8601


class AdmissionStats(BaseModel):
    decisions_24h: int = 0
    deny_rate_pct: float = 0.0
    warn_rate_pct: float = 0.0
    avg_decision_latency_ms: float = 0.0
    policies_active: int = 0


@router.get(
    "/admission/decisions",
    response_model=AdmissionDecisionsResponse,
    summary="List recent admission-controller decisions",
)
async def list_admission_decisions(
    limit: int = Query(50, ge=1, le=500),
    namespace: Optional[str] = None,
) -> AdmissionDecisionsResponse:
    """Return recent admission decisions with a 24h summary.

    TODO(#163-wave4): replace with a live read against the admission
    controller's decision log (CloudTrail / EKS audit log). For now
    returns an empty list so widgets render the "no data" state.
    """
    _ = (limit, namespace)
    return AdmissionDecisionsResponse()


@router.get(
    "/admission/policies",
    response_model=list[AdmissionPolicy],
    summary="List configured admission-controller policies",
)
async def list_admission_policies() -> list[AdmissionPolicy]:
    """TODO(#163-wave4): wire to AdmissionController policy registry."""
    return []


@router.get(
    "/admission/stats",
    response_model=AdmissionStats,
    summary="Admission-controller rollup stats",
)
async def get_admission_stats() -> AdmissionStats:
    """TODO(#163-wave4): aggregate decisions over the last 24h."""
    return AdmissionStats()


# =============================================================================
# Container Escape Detection (ADR-083)
# =============================================================================


class ContainerEscapeAttempt(BaseModel):
    attempt_id: str
    container_id: str
    pod_name: str
    namespace: str
    technique: str
    mitre_tactic: str
    mitre_technique: str  # e.g. T1611
    severity: str  # critical | high | medium | low
    blocked: bool
    detected_at: str  # ISO 8601
    details: str = ""


class ContainerAnomaly(BaseModel):
    anomaly_id: str
    container_id: str
    pod_name: str
    namespace: str
    anomaly_type: str
    severity: str
    score: float
    detected_at: str
    details: str = ""


class MitreMappingEntry(BaseModel):
    technique_id: str
    technique_name: str
    tactic: str
    detection_count: int


@router.get(
    "/container/escape-attempts",
    response_model=list[ContainerEscapeAttempt],
    summary="List container escape attempts",
)
async def list_escape_attempts(
    limit: int = Query(50, ge=1, le=500),
    severity: Optional[str] = None,
) -> list[ContainerEscapeAttempt]:
    """TODO(#163-wave4): wire to runtime_security.escape_detector."""
    _ = (limit, severity)
    return []


@router.get(
    "/container/anomalies",
    response_model=list[ContainerAnomaly],
    summary="List container behavioral anomalies",
)
async def list_container_anomalies(
    limit: int = Query(50, ge=1, le=500),
) -> list[ContainerAnomaly]:
    """TODO(#163-wave4): wire to baselines.drift_detector."""
    _ = limit
    return []


@router.get(
    "/container/mitre-mapping",
    response_model=list[MitreMappingEntry],
    summary="MITRE ATT&CK coverage rollup",
)
async def get_mitre_mapping() -> list[MitreMappingEntry]:
    """TODO(#163-wave4): aggregate escape attempts by MITRE technique."""
    return []


# =============================================================================
# Runtime Correlation (ADR-083)
# =============================================================================


class CodeLocation(BaseModel):
    file: str
    line: int
    function: str = ""


class RuntimeCorrelation(BaseModel):
    correlation_id: str
    source_event: str  # cloudtrail | guardduty
    event_id: str
    event_name: str = ""
    code_location: Optional[CodeLocation] = None
    confidence_score: int  # 0-100
    affected_files: list[str] = Field(default_factory=list)
    correlated_at: str  # ISO 8601


class CloudTrailEvent(BaseModel):
    event_id: str
    event_name: str
    event_source: str
    user_identity: str
    resource_arn: str = ""
    timestamp: str
    correlation_id: Optional[str] = None


class CodeCorrelation(BaseModel):
    correlation_id: str
    file: str
    line_start: int
    line_end: int
    runtime_event_id: str
    correlation_type: str
    confidence: int  # 0-100


@router.get(
    "/correlation",
    response_model=list[RuntimeCorrelation],
    summary="List runtime-to-code correlations",
)
async def list_runtime_correlations(
    limit: int = Query(50, ge=1, le=500),
    min_confidence: int = Query(50, ge=0, le=100),
) -> list[RuntimeCorrelation]:
    """TODO(#163-wave4): wire to correlation.correlator service."""
    _ = (limit, min_confidence)
    return []


@router.get(
    "/correlation/cloudtrail",
    response_model=list[CloudTrailEvent],
    summary="CloudTrail events relevant to runtime security",
)
async def list_cloudtrail_events(
    limit: int = Query(50, ge=1, le=500),
) -> list[CloudTrailEvent]:
    """TODO(#163-wave4): wire to correlation.cloudtrail_ingest."""
    _ = limit
    return []


@router.get(
    "/correlation/code",
    response_model=list[CodeCorrelation],
    summary="Code-side correlations (runtime event -> source ref)",
)
async def list_code_correlations(
    limit: int = Query(50, ge=1, le=500),
    min_confidence: int = Query(50, ge=0, le=100),
) -> list[CodeCorrelation]:
    """TODO(#163-wave4): wire to correlation.graph_tracer."""
    _ = (limit, min_confidence)
    return []


# =============================================================================
# GuardDuty Integration (ADR-083)
# =============================================================================


class GuardDutyCodeLink(BaseModel):
    file: str
    line: int
    context: str = ""


class GuardDutyFinding(BaseModel):
    finding_id: str
    type: str
    severity: str  # Critical | High | Medium | Low
    severity_score: int  # 1-10
    title: str
    description: str
    resource_type: str
    resource_id: str
    code_link: Optional[GuardDutyCodeLink] = None
    detected_at: str
    archived: bool = False


class GuardDutyStats(BaseModel):
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    correlated_to_code_count: int = 0
    archived_count: int = 0


class GuardDutyCodeLinkSummary(BaseModel):
    finding_id: str
    finding_type: str
    code_link: GuardDutyCodeLink
    confidence: int  # 0-100


@router.get(
    "/guardduty/findings",
    response_model=list[GuardDutyFinding],
    summary="List GuardDuty findings",
)
async def list_guardduty_findings(
    limit: int = Query(50, ge=1, le=500),
    severity: Optional[str] = None,
    archived: bool = False,
) -> list[GuardDutyFinding]:
    """TODO(#163-wave4): wire to GuardDuty integration in runtime_security."""
    _ = (limit, severity, archived)
    return []


@router.get(
    "/guardduty/stats",
    response_model=GuardDutyStats,
    summary="GuardDuty findings rollup",
)
async def get_guardduty_stats() -> GuardDutyStats:
    """TODO(#163-wave4): aggregate GuardDuty findings by severity."""
    return GuardDutyStats()


@router.get(
    "/guardduty/code-links",
    response_model=list[GuardDutyCodeLinkSummary],
    summary="GuardDuty findings successfully correlated to source code",
)
async def list_guardduty_code_links(
    limit: int = Query(50, ge=1, le=500),
    min_confidence: int = Query(50, ge=0, le=100),
) -> list[GuardDutyCodeLinkSummary]:
    """TODO(#163-wave4): wire to GuardDuty + correlation engine."""
    _ = (limit, min_confidence)
    return []


# =============================================================================
# Health probe
# =============================================================================


class HealthResponse(BaseModel):
    status: str
    timestamp: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check for the runtime-security API surface",
)
async def health() -> HealthResponse:
    """Always returns OK; widgets use this to gate showing the panel."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
