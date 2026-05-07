"""Project Aura - Development Mock Endpoints.

Lightweight mock-data endpoints for sections of the platform that don't yet
have a dedicated backend router. The goal is to populate the UI with
representative data so reviewers can navigate the sidebar and see what each
feature is supposed to look like, without requiring a real backing service.

Each endpoint here:
- Is registered only when ``AURA_ENABLE_DEV_MOCKS`` is unset or truthy.
- Returns shapes derived from the corresponding frontend service file
  (``frontend/src/services/*.js``) and components.
- Lives behind ``get_current_user`` so the dev auth bypass is the only path
  that lights it up — no exposure to anonymous traffic.
- Should be replaced with real, dedicated endpoints as features ship.

When a feature gets a real router, simply remove its block from this module.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel

from src.api.auth import User, get_current_user

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(offset_minutes: int = 0) -> str:
    return (_now() + timedelta(minutes=offset_minutes)).isoformat()


# Single router covering all the gaps. Tagged so they group together in
# /docs and are easy to identify as dev-only.
router = APIRouter(tags=["dev-mocks"])


# ---------------------------------------------------------------------------
# Sandboxes (sidebar entry — no real router yet)
# ---------------------------------------------------------------------------

_SANDBOXES = [
    {
        "id": "sb-9f12c3",
        "name": "Patch validation: SQL injection (CVE-2024-9921)",
        "status": "running",
        "type": "patch_validation",
        "linked_approval_id": "appr-demo-fb84e3xx",
        "network_isolation": "deny-all",
        "image": "aura-base-images/python:3.11-slim",
        "cpu": "1024",
        "memory_mb": 2048,
        "started_at": _iso(-7),
        "expected_finish_at": _iso(8),
        "resource_arn": "arn:aws:ecs:us-east-1:123456789012:task/sandbox/abc123",
    },
    {
        "id": "sb-22aa01",
        "name": "Repo onboarding: aenealabs/example-fintech",
        "status": "succeeded",
        "type": "repository_ingestion",
        "linked_approval_id": None,
        "network_isolation": "egress-allowlist",
        "image": "aura-base-images/python:3.11-slim",
        "cpu": "2048",
        "memory_mb": 4096,
        "started_at": _iso(-92),
        "finished_at": _iso(-31),
        "resource_arn": "arn:aws:ecs:us-east-1:123456789012:task/sandbox/22aa01",
    },
    {
        "id": "sb-7b41ee",
        "name": "Container escape verification (Falco trace replay)",
        "status": "failed",
        "type": "security_replay",
        "linked_incident_id": "INC-002xx",
        "network_isolation": "deny-all",
        "image": "aura-base-images/alpine:3.19",
        "cpu": "1024",
        "memory_mb": 1024,
        "started_at": _iso(-180),
        "finished_at": _iso(-160),
        "failure_reason": "Falco rule fired before workload finished — sandbox auto-terminated",
        "resource_arn": "arn:aws:ecs:us-east-1:123456789012:task/sandbox/7b41ee",
    },
    {
        "id": "sb-c0ffee",
        "name": "GraphRAG retrieval benchmark",
        "status": "queued",
        "type": "benchmark",
        "linked_approval_id": None,
        "network_isolation": "vpc-only",
        "image": "aura-base-images/python:3.11-slim",
        "cpu": "4096",
        "memory_mb": 8192,
        "queued_at": _iso(-3),
    },
]


@router.get("/api/v1/sandboxes")
async def list_sandboxes(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    for s in _SANDBOXES:
        by_status[s["status"]] = by_status.get(s["status"], 0) + 1
    return {
        "sandboxes": _SANDBOXES,
        "stats": {"total": len(_SANDBOXES), "byStatus": by_status},
    }


@router.get("/api/v1/sandboxes/{sandbox_id}")
async def get_sandbox(
    sandbox_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    match = next((s for s in _SANDBOXES if s["id"] == sandbox_id), None)
    if not match:
        return {"error": "sandbox not found"}, 404  # FastAPI handles tuple
    return match


# ---------------------------------------------------------------------------
# Capability Graph (sidebar entry — ADR-071, no router yet)
# ---------------------------------------------------------------------------

_CAPABILITY_NODES = [
    {"id": "agent.coder", "type": "agent", "label": "Coder Agent", "tier": 2},
    {"id": "agent.reviewer", "type": "agent", "label": "Reviewer Agent", "tier": 2},
    {"id": "agent.validator", "type": "agent", "label": "Validator Agent", "tier": 2},
    {
        "id": "agent.runtime_incident",
        "type": "agent",
        "label": "Runtime Incident Agent",
        "tier": 1,
    },
    {"id": "tool.bedrock_invoke", "type": "tool", "label": "Bedrock Invoke", "tier": 3},
    {"id": "tool.neptune_query", "type": "tool", "label": "Neptune Query", "tier": 3},
    {
        "id": "tool.opensearch_query",
        "type": "tool",
        "label": "OpenSearch Query",
        "tier": 3,
    },
    {
        "id": "tool.sandbox_dispatch",
        "type": "tool",
        "label": "Sandbox Dispatch (HITL)",
        "tier": 1,
    },
    {"id": "data.repo_index", "type": "data", "label": "Repository Index", "tier": 4},
    {"id": "data.audit_log", "type": "data", "label": "Audit Log", "tier": 1},
]

_CAPABILITY_EDGES = [
    {"source": "agent.coder", "target": "tool.bedrock_invoke", "scope": "read_write"},
    {"source": "agent.coder", "target": "tool.neptune_query", "scope": "read_only"},
    {"source": "agent.reviewer", "target": "tool.bedrock_invoke", "scope": "read_only"},
    {
        "source": "agent.reviewer",
        "target": "tool.opensearch_query",
        "scope": "read_only",
    },
    {
        "source": "agent.validator",
        "target": "tool.sandbox_dispatch",
        "scope": "read_write",
    },
    {
        "source": "agent.runtime_incident",
        "target": "data.audit_log",
        "scope": "read_only",
    },
    {
        "source": "tool.bedrock_invoke",
        "target": "data.audit_log",
        "scope": "write_only",
    },
    {"source": "tool.neptune_query", "target": "data.repo_index", "scope": "read_only"},
    {
        "source": "tool.opensearch_query",
        "target": "data.repo_index",
        "scope": "read_only",
    },
]


@router.get("/api/v1/capability-graph")
async def get_capability_graph(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "nodes": _CAPABILITY_NODES,
        "edges": _CAPABILITY_EDGES,
        "stats": {
            "agents": sum(1 for n in _CAPABILITY_NODES if n["type"] == "agent"),
            "tools": sum(1 for n in _CAPABILITY_NODES if n["type"] == "tool"),
            "data_stores": sum(1 for n in _CAPABILITY_NODES if n["type"] == "data"),
            "edges": len(_CAPABILITY_EDGES),
        },
    }


@router.get("/api/v1/capability-graph/escalation-paths")
async def get_capability_escalation_paths(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "paths": [
            {
                "from": "agent.coder",
                "to": "data.audit_log",
                "hops": ["agent.coder", "tool.bedrock_invoke", "data.audit_log"],
                "risk": "low",
            },
            {
                "from": "agent.validator",
                "to": "data.audit_log",
                "hops": ["agent.validator", "tool.sandbox_dispatch", "data.audit_log"],
                "risk": "medium",
            },
        ]
    }


# ---------------------------------------------------------------------------
# Knowledge Graph (sidebar entry — Hybrid GraphRAG visualisation)
# ---------------------------------------------------------------------------

_KNOWLEDGE_GRAPH_NODES = [
    {"id": "file.api_main", "type": "file", "label": "src/api/main.py", "loc": 920},
    {"id": "file.auth", "type": "file", "label": "src/api/auth.py", "loc": 540},
    {
        "id": "file.token_service",
        "type": "file",
        "label": "src/services/identity/token_service.py",
        "loc": 470,
    },
    {
        "id": "func.get_current_user",
        "type": "function",
        "label": "get_current_user",
        "file": "src/api/auth.py",
    },
    {
        "id": "func.verify_token",
        "type": "function",
        "label": "verify_token",
        "file": "src/api/auth.py",
    },
    {"id": "class.User", "type": "class", "label": "User", "file": "src/api/auth.py"},
    {
        "id": "class.HITLApprovalService",
        "type": "class",
        "label": "HITLApprovalService",
        "file": "src/services/hitl_approval_service.py",
    },
]

_KNOWLEDGE_GRAPH_EDGES = [
    {"source": "func.get_current_user", "target": "func.verify_token", "type": "calls"},
    {"source": "func.get_current_user", "target": "class.User", "type": "returns"},
    {"source": "file.api_main", "target": "func.get_current_user", "type": "imports"},
    {"source": "file.auth", "target": "class.User", "type": "defines"},
    {"source": "file.auth", "target": "func.get_current_user", "type": "defines"},
    {
        "source": "file.api_main",
        "target": "class.HITLApprovalService",
        "type": "imports",
    },
]


@router.get("/api/v1/knowledge-graph")
async def get_knowledge_graph(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "nodes": _KNOWLEDGE_GRAPH_NODES,
        "edges": _KNOWLEDGE_GRAPH_EDGES,
        "stats": {
            "files": sum(1 for n in _KNOWLEDGE_GRAPH_NODES if n["type"] == "file"),
            "functions": sum(
                1 for n in _KNOWLEDGE_GRAPH_NODES if n["type"] == "function"
            ),
            "classes": sum(1 for n in _KNOWLEDGE_GRAPH_NODES if n["type"] == "class"),
            "edges": len(_KNOWLEDGE_GRAPH_EDGES),
        },
    }


# ---------------------------------------------------------------------------
# Validator runs (sidebar "Validator" entry — env-validator agent runs)
# ---------------------------------------------------------------------------

_VALIDATOR_RUNS = [
    {
        "id": "vrun-001",
        "name": "Cross-env drift: dev vs qa (eks node groups)",
        "status": "completed",
        "result": "drift_detected",
        "started_at": _iso(-185),
        "finished_at": _iso(-182),
        "drift_count": 3,
        "summary": (
            "QA cluster has nodegroup-gpu desired=1 while dev has 0. "
            "Two security groups in QA reference deleted IPs."
        ),
    },
    {
        "id": "vrun-002",
        "name": "Pre-deploy validation: ADR-087 hyperscale rollout",
        "status": "completed",
        "result": "passed",
        "started_at": _iso(-95),
        "finished_at": _iso(-94),
        "drift_count": 0,
        "summary": "All 12 invariants held. Safe to merge.",
    },
    {
        "id": "vrun-003",
        "name": "Continuous validation: prod IAM boundary",
        "status": "running",
        "started_at": _iso(-2),
        "result": None,
        "summary": "Scan in progress (5 of 23 templates checked).",
    },
]


@router.get("/api/v1/validator/runs")
async def list_validator_runs(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {"runs": _VALIDATOR_RUNS, "stats": {"total": len(_VALIDATOR_RUNS)}}


# ---------------------------------------------------------------------------
# Notifications / channels (settings page — no router yet)
# ---------------------------------------------------------------------------

_NOTIFICATION_CHANNELS = [
    {
        "id": "ch-slack-secops",
        "type": "slack",
        "name": "#aura-secops",
        "enabled": True,
        "events": ["alert.p1", "alert.p2", "approval.created"],
        "configured_at": _iso(-30240),
    },
    {
        "id": "ch-pagerduty-oncall",
        "type": "pagerduty",
        "name": "Aura Oncall",
        "enabled": True,
        "events": ["alert.p1"],
        "configured_at": _iso(-30240),
    },
    {
        "id": "ch-webhook-siem",
        "type": "webhook",
        "name": "Splunk HEC ingest",
        "enabled": False,
        "events": ["audit.*"],
        "configured_at": _iso(-86400),
    },
]


@router.get("/api/v1/notifications/channels")
async def list_notification_channels(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {"channels": _NOTIFICATION_CHANNELS}


@router.get("/api/v1/notifications/preferences")
async def get_notification_preferences(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "user_id": current_user.sub,
        "email": current_user.email,
        "digest_cadence": "daily",
        "p1_immediate": True,
        "p2_immediate": True,
        "p3_digest": True,
    }


@router.get("/api/v1/notifications/quiet-hours")
async def get_quiet_hours(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "user_id": current_user.sub,
        "enabled": False,
        "start": "22:00",
        "end": "07:00",
        "timezone": "America/New_York",
        "exceptions": ["alert.p1"],
    }


# ---------------------------------------------------------------------------
# Health / overview (top-level platform health)
# ---------------------------------------------------------------------------


@router.get("/api/v1/health/overview")
async def get_health_overview(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "status": "healthy",
        "components": [
            {"id": "api", "name": "FastAPI", "status": "healthy", "latency_ms": 4},
            {
                "id": "neptune",
                "name": "Neptune (Gremlin)",
                "status": "mocked",
                "latency_ms": 0,
            },
            {
                "id": "opensearch",
                "name": "OpenSearch",
                "status": "mocked",
                "latency_ms": 0,
            },
            {
                "id": "bedrock",
                "name": "Bedrock LLM",
                "status": "mocked",
                "latency_ms": 0,
            },
            {"id": "dynamodb", "name": "DynamoDB", "status": "mocked", "latency_ms": 0},
        ],
        "incidents_open": 2,
        "alerts_unacknowledged": 3,
        "approvals_pending": 7,
        "ts": _iso(),
    }


# ---------------------------------------------------------------------------
# Frontend client-error reporter (was 404-spamming the log)
# ---------------------------------------------------------------------------


class ErrorReportRequest(BaseModel):
    error: str | None = None
    message: str | None = None
    stack: str | None = None
    url: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] | None = None


@router.post("/api/v1/errors/report")
async def report_client_error(
    request: Request,
    payload: ErrorReportRequest,
) -> Response:
    """Accept and log frontend client-side errors.

    Intentionally accepts unauthenticated traffic — the frontend's error
    boundary fires this even before login, and rejecting with 401 here would
    drop diagnostic signal. Production should route this to a real
    error-reporting backend (Sentry/Bugsnag/Datadog).

    Returns 204 (no body). FastAPI's response-body validation requires the
    handler to explicitly return ``Response(status_code=204)`` rather than
    declaring it as a decorator argument; declaring ``status_code=204`` on
    the decorator triggers an assertion at route-registration time because
    type inference would otherwise allow a body.
    """
    summary = (payload.message or payload.error or "<no message>")[:200]
    logger.warning(
        "frontend client error: %s | url=%s | ua=%s",
        summary,
        payload.url,
        (payload.user_agent or "")[:80],
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
