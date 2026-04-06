"""
Palantir AIP API Router

Implements ADR-074: Palantir AIP Integration

FastAPI router providing REST endpoints for Palantir integration:
- Health checks
- Threat context retrieval
- Asset criticality lookup
- Sync management
- Circuit breaker status
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.services.palantir.types import PalantirObjectType, RemediationEventType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/palantir", tags=["palantir"])


# =============================================================================
# Request/Response Models
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    connector_status: str
    is_healthy: bool
    message: str | None = None


class ThreatContextRequest(BaseModel):
    """Request for threat context."""

    cve_ids: list[str] = Field(..., min_length=1, max_length=100)


class ThreatContextResponse(BaseModel):
    """Threat context response."""

    threat_id: str
    source_platform: str
    cves: list[str]
    epss_score: float | None
    mitre_ttps: list[str]
    targeted_industries: list[str]
    active_campaigns: list[str]
    priority_score: float


class AssetContextResponse(BaseModel):
    """Asset context response."""

    asset_id: str
    criticality_score: int
    data_classification: str
    business_owner: str | None
    pii_handling: bool
    phi_handling: bool
    compliance_frameworks: list[str]
    is_high_value: bool


class SyncStatusResponse(BaseModel):
    """Sync status for an object type."""

    object_type: str
    last_sync_time: str | None
    last_sync_status: str
    objects_synced: int
    objects_failed: int
    conflicts_resolved: int
    last_error: str | None


class SyncTriggerRequest(BaseModel):
    """Request to trigger sync."""

    full_sync: bool = False


class SyncTriggerResponse(BaseModel):
    """Response from sync trigger."""

    object_type: str
    status: str
    objects_synced: int
    objects_failed: int
    conflicts_resolved: int
    error_message: str | None


class CircuitBreakerResponse(BaseModel):
    """Circuit breaker status."""

    name: str
    state: str
    failure_count: int
    success_count: int
    total_failures: int
    total_successes: int
    last_failure: str | None
    last_state_change: str
    recovery_timeout_seconds: float


class ConnectionTestRequest(BaseModel):
    """Request to test connection."""

    ontology_api_url: str
    foundry_api_url: str
    api_key: str
    client_cert_path: str | None = None


class ConnectionTestResponse(BaseModel):
    """Response from connection test."""

    success: bool
    message: str
    latency_ms: float | None = None


class PublishEventRequest(BaseModel):
    """Request to publish event."""

    event_type: str = Field(
        ...,
        description="Event type (e.g., VULNERABILITY_DETECTED, PATCH_GENERATED)",
    )
    tenant_id: str
    payload: dict[str, Any]


class PublishEventResponse(BaseModel):
    """Response from event publish."""

    success: bool
    event_id: str | None = None
    message: str


class MetricsResponse(BaseModel):
    """Adapter metrics response."""

    name: str
    status: str
    request_count: int
    error_count: int
    error_rate: float
    avg_latency_ms: float
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float
    uptime_seconds: float


# =============================================================================
# Dependency Injection Stubs
# =============================================================================

# These would be replaced with actual DI in production


async def get_adapter():
    """Get Palantir adapter instance."""
    # In production, this would return an actual adapter from DI container
    # For now, raise an error indicating configuration needed
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Palantir adapter not configured. Please configure via /configuration endpoint.",
    )


async def get_bridge():
    """Get Ontology Bridge instance."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Ontology Bridge not configured.",
    )


async def get_publisher():
    """Get Event Publisher instance."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Event Publisher not configured.",
    )


async def get_circuit_breaker():
    """Get Palantir circuit breaker."""
    from src.services.palantir.circuit_breaker import get_palantir_circuit_breaker

    return get_palantir_circuit_breaker()


# =============================================================================
# Health Endpoints
# =============================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Check Palantir integration health.

    Returns basic health status without requiring adapter configuration.
    """
    try:
        from src.services.palantir.circuit_breaker import get_palantir_circuit_breaker

        breaker = get_palantir_circuit_breaker()
        return HealthResponse(
            status="ok",
            connector_status=breaker.state.value,
            is_healthy=breaker.is_closed or breaker.is_half_open,
            message=None if breaker.is_closed else "Circuit breaker not closed",
        )
    except Exception as e:
        return HealthResponse(
            status="degraded",
            connector_status="unknown",
            is_healthy=False,
            message=str(e),
        )


@router.get("/health/detailed", response_model=dict[str, Any])
async def detailed_health_check(adapter=Depends(get_adapter)) -> dict[str, Any]:
    """
    Detailed health check with adapter connectivity test.

    Requires configured adapter.
    """
    try:
        is_healthy = await adapter.health_check()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "adapter": {
                "name": adapter.name,
                "status": adapter.status.value,
                "metrics": adapter.metrics,
            },
            "health_check_passed": is_healthy,
        }
    except Exception as e:
        logger.error("Palantir health check failed: %s", e)
        return {
            "status": "error",
            "error": "Internal health check failure",
            "health_check_passed": False,
        }


# =============================================================================
# Threat Context Endpoints
# =============================================================================


@router.get("/threats/active", response_model=list[ThreatContextResponse])
async def get_active_threats(
    adapter=Depends(get_adapter),
) -> list[ThreatContextResponse]:
    """
    Get active threat campaigns from Palantir.

    Returns threat context for currently active campaigns.
    """
    threats = await adapter.get_active_threats()
    return [
        ThreatContextResponse(
            threat_id=t.threat_id,
            source_platform=t.source_platform,
            cves=t.cves,
            epss_score=t.epss_score,
            mitre_ttps=t.mitre_ttps,
            targeted_industries=t.targeted_industries,
            active_campaigns=t.active_campaigns,
            priority_score=t.priority_score,
        )
        for t in threats
    ]


@router.post("/threats/context", response_model=list[ThreatContextResponse])
async def get_threat_context(
    request: ThreatContextRequest,
    adapter=Depends(get_adapter),
) -> list[ThreatContextResponse]:
    """
    Get threat context for specific CVEs.

    Queries Palantir Ontology for threat intelligence related to
    the specified CVE IDs.
    """
    threats = await adapter.get_threat_context(request.cve_ids)
    return [
        ThreatContextResponse(
            threat_id=t.threat_id,
            source_platform=t.source_platform,
            cves=t.cves,
            epss_score=t.epss_score,
            mitre_ttps=t.mitre_ttps,
            targeted_industries=t.targeted_industries,
            active_campaigns=t.active_campaigns,
            priority_score=t.priority_score,
        )
        for t in threats
    ]


@router.get("/cve/{cve_id}/context", response_model=ThreatContextResponse | None)
async def get_cve_context(
    cve_id: str,
    adapter=Depends(get_adapter),
) -> ThreatContextResponse | None:
    """
    Get threat context for a specific CVE.

    Convenience endpoint for single CVE lookup.
    """
    threats = await adapter.get_threat_context([cve_id])
    if not threats:
        return None
    t = threats[0]
    return ThreatContextResponse(
        threat_id=t.threat_id,
        source_platform=t.source_platform,
        cves=t.cves,
        epss_score=t.epss_score,
        mitre_ttps=t.mitre_ttps,
        targeted_industries=t.targeted_industries,
        active_campaigns=t.active_campaigns,
        priority_score=t.priority_score,
    )


# =============================================================================
# Asset Context Endpoints
# =============================================================================


@router.get("/assets/{repo_id}/criticality", response_model=AssetContextResponse | None)
async def get_asset_criticality(
    repo_id: str,
    adapter=Depends(get_adapter),
) -> AssetContextResponse | None:
    """
    Get asset criticality for a repository.

    Retrieves business context from Palantir's CMDB integration.
    """
    asset = await adapter.get_asset_criticality(repo_id)
    if not asset:
        return None
    return AssetContextResponse(
        asset_id=asset.asset_id,
        criticality_score=asset.criticality_score,
        data_classification=asset.data_classification.value,
        business_owner=asset.business_owner,
        pii_handling=asset.pii_handling,
        phi_handling=asset.phi_handling,
        compliance_frameworks=asset.compliance_frameworks,
        is_high_value=asset.is_high_value,
    )


# =============================================================================
# Sync Management Endpoints
# =============================================================================


@router.get("/sync/status", response_model=dict[str, SyncStatusResponse])
async def get_sync_status(bridge=Depends(get_bridge)) -> dict[str, SyncStatusResponse]:
    """
    Get sync status for all object types.

    Returns last sync time, status, and statistics for each object type.
    """
    status = bridge.get_sync_status()
    return {k: SyncStatusResponse(**v) for k, v in status.items()}


@router.post("/sync/{object_type}", response_model=SyncTriggerResponse)
async def trigger_sync(
    object_type: str,
    request: SyncTriggerRequest,
    bridge=Depends(get_bridge),
) -> SyncTriggerResponse:
    """
    Trigger manual sync for an object type.

    Starts immediate sync (full or incremental) for the specified object type.
    """
    try:
        obj_type = PalantirObjectType(object_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid object type: {object_type}. Valid types: {[t.value for t in PalantirObjectType]}",
        )

    if request.full_sync:
        result = await bridge.full_sync(obj_type)
    else:
        result = await bridge.incremental_sync(obj_type)

    return SyncTriggerResponse(
        object_type=result.object_type.value,
        status=result.status.value,
        objects_synced=result.objects_synced,
        objects_failed=result.objects_failed,
        conflicts_resolved=result.conflicts_resolved,
        error_message=result.error_message,
    )


@router.post("/sync/all", response_model=dict[str, SyncTriggerResponse])
async def sync_all(
    request: SyncTriggerRequest,
    bridge=Depends(get_bridge),
) -> dict[str, SyncTriggerResponse]:
    """
    Trigger sync for all object types.
    """
    results = await bridge.sync_all(full_sync=request.full_sync)
    return {
        k: SyncTriggerResponse(
            object_type=v.object_type.value,
            status=v.status.value,
            objects_synced=v.objects_synced,
            objects_failed=v.objects_failed,
            conflicts_resolved=v.conflicts_resolved,
            error_message=v.error_message,
        )
        for k, v in results.items()
    }


# =============================================================================
# Circuit Breaker Endpoints
# =============================================================================


@router.get("/circuit-breaker", response_model=CircuitBreakerResponse)
async def get_circuit_breaker_status(
    breaker=Depends(get_circuit_breaker),
) -> CircuitBreakerResponse:
    """
    Get circuit breaker state.

    Returns current state and statistics for the Palantir circuit breaker.
    """
    metrics = breaker.get_metrics()
    return CircuitBreakerResponse(
        name=metrics["name"],
        state=metrics["state"],
        failure_count=metrics["failure_count"],
        success_count=metrics["success_count"],
        total_failures=metrics["total_failures"],
        total_successes=metrics["total_successes"],
        last_failure=metrics["last_failure"],
        last_state_change=metrics["last_state_change"],
        recovery_timeout_seconds=metrics["recovery_timeout_seconds"],
    )


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(
    breaker=Depends(get_circuit_breaker),
) -> dict[str, str]:
    """
    Reset circuit breaker to closed state.

    Use with caution - only reset if you're confident the underlying
    issue has been resolved.
    """
    breaker.reset()
    return {"status": "reset", "new_state": breaker.state.value}


# =============================================================================
# Connection Testing
# =============================================================================


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_connection(
    request: ConnectionTestRequest,
) -> ConnectionTestResponse:
    """
    Test connection with provided configuration.

    Validates connectivity to Palantir APIs without persisting configuration.
    """
    from src.services.palantir.palantir_adapter import PalantirAIPAdapter

    try:
        adapter = PalantirAIPAdapter(
            ontology_api_url=request.ontology_api_url,
            foundry_api_url=request.foundry_api_url,
            api_key=request.api_key,
            client_cert_path=request.client_cert_path,
        )

        is_healthy = await adapter.health_check()
        await adapter.close()

        return ConnectionTestResponse(
            success=is_healthy,
            message="Connection successful" if is_healthy else "Health check failed",
            latency_ms=adapter.metrics.get("avg_latency_ms"),
        )
    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
        )


# =============================================================================
# Event Publishing
# =============================================================================


@router.post("/events/publish", response_model=PublishEventResponse)
async def publish_event(
    request: PublishEventRequest,
    publisher=Depends(get_publisher),
) -> PublishEventResponse:
    """
    Publish a remediation event to Palantir.

    Events are sent to Palantir Foundry for dashboarding and analytics.
    """
    try:
        event_type = RemediationEventType(request.event_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event type: {request.event_type}",
        )

    event = publisher.create_event(
        event_type=event_type,
        tenant_id=request.tenant_id,
        payload=request.payload,
    )

    success = await publisher.publish(event)

    return PublishEventResponse(
        success=success,
        event_id=event.event_id if success else None,
        message="Event published" if success else "Failed to publish event",
    )


@router.get("/events/metrics", response_model=dict[str, Any])
async def get_publisher_metrics(
    publisher=Depends(get_publisher),
) -> dict[str, Any]:
    """
    Get event publisher metrics.

    Returns counts of published events, failures, and DLQ status.
    """
    return publisher.get_metrics()


@router.post("/events/retry-dlq")
async def retry_dlq_events(
    publisher=Depends(get_publisher),
) -> dict[str, Any]:
    """
    Retry failed events from Dead Letter Queue.

    Attempts to republish events that previously failed.
    """
    retried = await publisher.retry_dlq()
    return {
        "retried": retried,
        "dlq_stats": publisher.get_dlq_stats(),
    }


# =============================================================================
# Adapter Metrics
# =============================================================================


@router.get("/metrics", response_model=MetricsResponse)
async def get_adapter_metrics(
    adapter=Depends(get_adapter),
) -> MetricsResponse:
    """
    Get adapter performance metrics.

    Returns request counts, error rates, latency, and cache statistics.
    """
    m = adapter.metrics
    return MetricsResponse(
        name=m["name"],
        status=m["status"],
        request_count=m["request_count"],
        error_count=m["error_count"],
        error_rate=m["error_rate"],
        avg_latency_ms=m["avg_latency_ms"],
        cache_hits=m["cache_hits"],
        cache_misses=m["cache_misses"],
        cache_hit_rate=m["cache_hit_rate"],
        uptime_seconds=m["uptime_seconds"],
    )
