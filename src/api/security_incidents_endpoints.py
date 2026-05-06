"""Project Aura - Security Incidents API Endpoints.

Backs the IncidentInvestigations page and the sidebar "Incidents" badge.
The contract matches what ``frontend/src/components/IncidentInvestigations.jsx``
consumes (camelCase top-level fields, nested ``timeline`` / ``rca`` /
``evidence`` arrays).

Co-exists with the legacy ``src/api/incidents.py`` router (which serves
``/api/v1/incidents/investigations`` for the RuntimeIncidentAgent workflow,
tightly coupled to DynamoDB). FastAPI route ordering picks the literal
``/investigations`` path before the parameterised ``/{id}`` route here, so
both routers can share the ``/api/v1/incidents`` prefix without clashing.

In-memory storage seeded on module import unless ``AURA_SEED_MOCK_INCIDENTS``
is falsy. Same pattern as ``security_alerts_endpoints``.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user
from src.api.log_sanitizer import sanitize_log
from src.services.api_rate_limiter import (
    RateLimitResult,
    sensitive_rate_limit,
    standard_rate_limit,
)

logger = logging.getLogger(__name__)


VALID_SEVERITIES = {"critical", "high", "medium", "low"}
VALID_STATUSES = {"open", "investigating", "resolved"}

_incidents: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_incident(
    *,
    incident_id: str,
    title: str,
    description: str,
    severity: str,
    status_value: str,
    source: str,
    affected_service: str,
    assigned_agents: list[str] | None = None,
    timeline: list[dict[str, Any]] | None = None,
    rca: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    created_offset_minutes: int = 0,
    updated_offset_minutes: int | None = None,
    resolved_offset_minutes: int | None = None,
    resolved_by: str | None = None,
) -> dict[str, Any]:
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"invalid severity: {severity}")
    if status_value not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status_value}")

    now = datetime.now(timezone.utc)
    created_at = (now + timedelta(minutes=created_offset_minutes)).isoformat()
    updated_at = (
        (now + timedelta(minutes=updated_offset_minutes)).isoformat()
        if updated_offset_minutes is not None
        else created_at
    )
    resolved_at = (
        (now + timedelta(minutes=resolved_offset_minutes)).isoformat()
        if resolved_offset_minutes is not None
        else None
    )

    return {
        "id": incident_id,
        "title": title,
        "description": description,
        "severity": severity,
        "status": status_value,
        "source": source,
        "affectedService": affected_service,
        "assignedAgents": list(assigned_agents or []),
        "createdAt": created_at,
        "updatedAt": updated_at,
        "resolvedAt": resolved_at,
        "resolvedBy": resolved_by,
        "anomalyCount": len(evidence or []),
        "evidenceCount": len(evidence or []),
        "timeline": list(timeline or []),
        "rca": rca,
        "evidence": list(evidence or []),
    }


def _seed_demo_incidents() -> None:
    """Seed two open + one investigating + one resolved incident.

    The two unresolved (open + investigating) match the sidebar's
    ``Incidents (2)`` hardcoded badge.
    """
    base = datetime.now(timezone.utc)

    seeds = [
        _make_incident(
            incident_id="INC-001",
            title="Memory leak in Coder Agent",
            description=(
                "Coder Agent memory usage has been climbing steadily over the "
                "last hour, crossing the 1 GB working-set alarm. Latency on "
                "/orchestrator/dispatch has degraded by ~35% in the same window."
            ),
            severity="high",
            status_value="investigating",
            source="CloudWatch Alarm",
            affected_service="coder-agent",
            assigned_agents=["Runtime Incident Agent"],
            created_offset_minutes=-135,
            updated_offset_minutes=-5,
            timeline=[
                {
                    "timestamp": (base + timedelta(minutes=-135)).isoformat(),
                    "event": "Incident detected",
                    "type": "detection",
                    "agent": "Anomaly Detector",
                },
                {
                    "timestamp": (base + timedelta(minutes=-130)).isoformat(),
                    "event": "Runtime Incident Agent assigned",
                    "type": "assignment",
                    "agent": "Orchestrator",
                },
                {
                    "timestamp": (base + timedelta(minutes=-120)).isoformat(),
                    "event": "Initial analysis started",
                    "type": "action",
                    "agent": "Runtime Incident Agent",
                },
                {
                    "timestamp": (base + timedelta(minutes=-60)).isoformat(),
                    "event": "Memory profiling completed",
                    "type": "action",
                    "agent": "Runtime Incident Agent",
                },
                {
                    "timestamp": (base + timedelta(minutes=-5)).isoformat(),
                    "event": "Root cause identified: unbounded LRU cache",
                    "type": "finding",
                    "agent": "Runtime Incident Agent",
                },
            ],
            rca={
                "hypothesis": (
                    "The Coder Agent's LRU cache is not evicting entries due "
                    "to a race condition in the cleanup routine."
                ),
                "confidence": 87,
                "codeEntities": [
                    {
                        "name": "LRUCache",
                        "type": "class",
                        "file": "src/agents/coder/cache.py",
                        "line": 45,
                    },
                    {
                        "name": "cleanup_expired",
                        "type": "method",
                        "file": "src/agents/coder/cache.py",
                        "line": 112,
                    },
                ],
                "deployments": [
                    {
                        "version": "v2.3.1",
                        "timestamp": (base + timedelta(minutes=-1080)).isoformat(),
                        "author": "deploy-bot",
                        "status": "healthy",
                    },
                ],
                "mitigation": (
                    "Add a mutex lock around the cache eviction logic and "
                    "introduce a periodic forced cleanup task."
                ),
            },
            evidence=[
                {
                    "type": "log",
                    "content": "[ERROR] Cache size exceeded threshold: 2.4 GB",
                    "timestamp": (base + timedelta(minutes=-130)).isoformat(),
                },
                {
                    "type": "metric",
                    "content": "memory_usage_mb: 2456 (threshold: 1024)",
                    "timestamp": (base + timedelta(minutes=-130)).isoformat(),
                },
                {
                    "type": "trace",
                    "content": (
                        "Stack trace showing cache.py:112 -> cleanup_expired() "
                        "blocked by held lock from cache.py:45"
                    ),
                    "timestamp": (base + timedelta(minutes=-60)).isoformat(),
                },
            ],
        ),
        _make_incident(
            incident_id="INC-002",
            title="High latency in GraphRAG queries",
            description=(
                "GraphRAG context retrieval is experiencing 5x normal p99 "
                "latency. Neptune query timeouts are firing intermittently."
            ),
            severity="critical",
            status_value="open",
            source="Prometheus Alert",
            affected_service="context-retrieval",
            assigned_agents=[],
            created_offset_minutes=-12,
            timeline=[
                {
                    "timestamp": (base + timedelta(minutes=-12)).isoformat(),
                    "event": "Incident detected",
                    "type": "detection",
                    "agent": "Anomaly Detector",
                },
            ],
            rca=None,
            evidence=[
                {
                    "type": "metric",
                    "content": "p99_latency_ms: 4523 (threshold: 1000)",
                    "timestamp": (base + timedelta(minutes=-12)).isoformat(),
                },
                {
                    "type": "log",
                    "content": "[WARN] Neptune query timeout after 5000ms",
                    "timestamp": (base + timedelta(minutes=-11)).isoformat(),
                },
            ],
        ),
        _make_incident(
            incident_id="INC-003",
            title="Authentication service connection failures",
            description=(
                "Intermittent connection failures to auth-service caused user "
                "login attempts to fail for ~3h yesterday."
            ),
            severity="medium",
            status_value="resolved",
            source="User Report",
            affected_service="auth-service",
            assigned_agents=["Runtime Incident Agent"],
            created_offset_minutes=-2880,
            updated_offset_minutes=-2700,
            resolved_offset_minutes=-2700,
            resolved_by="admin@aenealabs.com",
            timeline=[
                {
                    "timestamp": (base + timedelta(minutes=-2880)).isoformat(),
                    "event": "Incident reported by user",
                    "type": "detection",
                    "agent": "User Report",
                },
                {
                    "timestamp": (base + timedelta(minutes=-2870)).isoformat(),
                    "event": "Runtime Incident Agent assigned",
                    "type": "assignment",
                    "agent": "Orchestrator",
                },
                {
                    "timestamp": (base + timedelta(minutes=-2820)).isoformat(),
                    "event": "Network analysis completed",
                    "type": "action",
                    "agent": "Runtime Incident Agent",
                },
                {
                    "timestamp": (base + timedelta(minutes=-2760)).isoformat(),
                    "event": "Root cause: dnsmasq pod restart during deploy",
                    "type": "finding",
                    "agent": "Runtime Incident Agent",
                },
                {
                    "timestamp": (base + timedelta(minutes=-2700)).isoformat(),
                    "event": "Incident resolved",
                    "type": "resolution",
                    "agent": "admin@aenealabs.com",
                },
            ],
            rca={
                "hypothesis": (
                    "DNS resolution timeout caused by a dnsmasq pod restart "
                    "during the v1.2.0 rollout."
                ),
                "confidence": 94,
                "codeEntities": [],
                "deployments": [
                    {
                        "version": "dnsmasq-v1.2.0",
                        "timestamp": (base + timedelta(minutes=-2885)).isoformat(),
                        "author": "argocd",
                        "status": "healthy",
                    },
                ],
                "mitigation": (
                    "Increase the DNS cache TTL and add retry-with-backoff to "
                    "the auth-service discovery client."
                ),
            },
            evidence=[
                {
                    "type": "log",
                    "content": "[ERROR] dial tcp: lookup auth-service.aura.local: i/o timeout",
                    "timestamp": (base + timedelta(minutes=-2880)).isoformat(),
                },
                {
                    "type": "metric",
                    "content": "auth_login_error_rate: 12% (baseline 0.3%)",
                    "timestamp": (base + timedelta(minutes=-2860)).isoformat(),
                },
            ],
        ),
    ]
    for inc in seeds:
        _incidents[inc["id"]] = inc


_seed_flag = os.environ.get("AURA_SEED_MOCK_INCIDENTS", "true").lower()
if _seed_flag not in ("0", "false", "no", "off"):
    _seed_demo_incidents()
    logger.info(
        "Seeded %d demo incidents (set AURA_SEED_MOCK_INCIDENTS=false to disable)",
        len(_incidents),
    )


# ============================================================================
# Pydantic models
# ============================================================================


class CreateIncidentRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: str
    source: str = "manual"
    affected_service: str = Field(alias="affectedService")
    assigned_agents: list[str] = Field(default_factory=list, alias="assignedAgents")

    class Config:
        populate_by_name = True


class AcknowledgeIncidentRequest(BaseModel):
    user_id: str
    comment: str | None = None


class ResolveIncidentRequest(BaseModel):
    user_id: str
    resolution: str = Field(min_length=1)
    actions_taken: list[str] = Field(default_factory=list)


# ============================================================================
# Router
# ============================================================================


router = APIRouter(prefix="/api/v1/incidents", tags=["security-incidents"])


def _filter_incidents(
    severity: str | None,
    status_value: str | None,
    affected_service: str | None,
) -> list[dict[str, Any]]:
    items = list(_incidents.values())
    if severity:
        items = [i for i in items if i["severity"] == severity]
    if status_value:
        items = [i for i in items if i["status"] == status_value]
    if affected_service:
        items = [i for i in items if i["affectedService"] == affected_service]
    items.sort(key=lambda i: i["createdAt"], reverse=True)
    return items


def _compute_stats() -> dict[str, Any]:
    by_severity: dict[str, int] = {}
    by_status: dict[str, int] = {}
    open_count = 0
    for i in _incidents.values():
        by_severity[i["severity"]] = by_severity.get(i["severity"], 0) + 1
        by_status[i["status"]] = by_status.get(i["status"], 0) + 1
        if i["status"] in ("open", "investigating"):
            open_count += 1
    return {
        "total": len(_incidents),
        "bySeverity": by_severity,
        "byStatus": by_status,
        "open": open_count,
    }


@router.get("")
async def list_incidents(
    request: Request,
    severity: str | None = Query(None, description="critical|high|medium|low"),
    status_filter: str | None = Query(
        None, alias="status", description="open|investigating|resolved"
    ),
    affected_service: str | None = Query(None, alias="affectedService"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(standard_rate_limit),
) -> dict[str, Any]:
    if severity and severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail=f"unknown severity: {severity}")
    if status_filter and status_filter not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"unknown status: {status_filter}")

    items = _filter_incidents(severity, status_filter, affected_service)
    return {"incidents": items[:limit], "stats": _compute_stats()}


@router.get("/stats")
async def get_incident_stats(
    request: Request,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(standard_rate_limit),
) -> dict[str, Any]:
    return _compute_stats()


@router.get("/{incident_id}")
async def get_incident_detail(
    incident_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(standard_rate_limit),
) -> dict[str, Any]:
    incident = _incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@router.post("", status_code=201)
async def create_incident(
    request: Request,
    payload: CreateIncidentRequest,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(sensitive_rate_limit),
) -> dict[str, Any]:
    if payload.severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail=f"unknown severity: {payload.severity}")

    incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
    inc = _make_incident(
        incident_id=incident_id,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        status_value="open",
        source=payload.source,
        affected_service=payload.affected_service,
        assigned_agents=payload.assigned_agents,
        timeline=[
            {
                "timestamp": _now_iso(),
                "event": "Incident reported manually",
                "type": "detection",
                "agent": current_user.email or current_user.sub,
            }
        ],
    )
    _incidents[incident_id] = inc
    logger.info(
        sanitize_log(
            f"incident {incident_id} created by {current_user.email or current_user.sub}"
        )
    )
    return inc


@router.post("/{incident_id}/acknowledge")
async def acknowledge_incident(
    incident_id: str,
    request: Request,
    payload: AcknowledgeIncidentRequest,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(sensitive_rate_limit),
) -> dict[str, Any]:
    incident = _incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="incident not found")
    if incident["status"] == "resolved":
        raise HTTPException(
            status_code=409,
            detail="cannot acknowledge a resolved incident",
        )
    incident["status"] = "investigating"
    incident["updatedAt"] = _now_iso()
    incident["timeline"].append(
        {
            "timestamp": _now_iso(),
            "event": (
                f"Acknowledged by {payload.user_id}"
                + (f": {payload.comment}" if payload.comment else "")
            ),
            "type": "assignment",
            "agent": payload.user_id,
        }
    )
    return incident


@router.post("/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    request: Request,
    payload: ResolveIncidentRequest,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(sensitive_rate_limit),
) -> dict[str, Any]:
    incident = _incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="incident not found")
    incident["status"] = "resolved"
    incident["updatedAt"] = _now_iso()
    incident["resolvedAt"] = _now_iso()
    incident["resolvedBy"] = payload.user_id
    incident["timeline"].append(
        {
            "timestamp": _now_iso(),
            "event": f"Resolved: {payload.resolution}",
            "type": "resolution",
            "agent": payload.user_id,
        }
    )
    if payload.actions_taken:
        for action in payload.actions_taken:
            incident["timeline"].append(
                {
                    "timestamp": _now_iso(),
                    "event": f"Action taken: {action}",
                    "type": "action",
                    "agent": payload.user_id,
                }
            )
    return incident
