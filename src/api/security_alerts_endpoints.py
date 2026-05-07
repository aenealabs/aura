"""Project Aura - Security Alerts API Endpoints.

Backs the SecurityAlertsPanel and the sidebar "Alerts" badge. Frontend
contract is defined in ``frontend/src/services/securityAlertsApi.js``.

Endpoints (all under ``/api/v1/alerts``)::

    GET    /                           list alerts (filter by priority/status/assignee)
    GET    /stats                      counts by priority and status
    GET    /unacknowledged/count       sidebar-badge count
    GET    /{id}                       single alert detail
    GET    /{id}/timeline              event-timeline (created/acked/resolved)
    POST   /{id}/acknowledge           mark NEW or INVESTIGATING -> ACKNOWLEDGED
    POST   /{id}/assign                set assigned_to
    POST   /{id}/status                set arbitrary status with comment
    POST   /{id}/resolve               mark -> RESOLVED with resolution
    POST   /{id}/false-positive        mark -> FALSE_POSITIVE
    POST   /{id}/comments              append a comment
    POST   /{id}/hitl-request          escalate to HITL approval

Storage is in-memory (``_alerts``) and seeded with demo data on import unless
``AURA_SEED_MOCK_ALERTS`` is set falsy. The seed is keyed off the same dev
flag pattern as ``HITLApprovalService._init_mock_mode``.

A dedicated, self-contained module keeps the priority-value contract
(``P1_CRITICAL`` etc., as the frontend expects) decoupled from the legacy
``security_alerts_service.AlertPriority`` enum (whose values are bare
``"P1"``).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user
from src.api.log_sanitizer import sanitize_log
from src.services.api_rate_limiter import (
    RateLimitResult,
    sensitive_rate_limit,
    standard_rate_limit,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Constants and helpers
# ============================================================================

VALID_PRIORITIES = {
    "P1_CRITICAL",
    "P2_HIGH",
    "P3_MEDIUM",
    "P4_LOW",
    "P5_INFO",
}
VALID_STATUSES = {
    "NEW",
    "ACKNOWLEDGED",
    "INVESTIGATING",
    "RESOLVED",
    "FALSE_POSITIVE",
}

# In-memory alert store keyed by alert_id. Module-global is acceptable for the
# dev/demo path; production is expected to use a real backing service that
# this module would route to instead.
_alerts: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_alert(
    *,
    title: str,
    description: str,
    priority: str,
    status_value: str,
    event_type: str,
    severity: str,
    source_ip: str | None = None,
    user_id: str | None = None,
    assigned_to: str | None = None,
    remediation_steps: list[str] | None = None,
    resolution: str | None = None,
    created_offset_minutes: int = 0,
    acknowledged_offset_minutes: int | None = None,
    resolved_offset_minutes: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct an alert dict matching the frontend contract.

    ``*_offset_minutes`` arguments are interpreted as offsets from "now", so
    seed data renders with realistic relative timestamps every time the
    server starts.
    """
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"invalid priority: {priority}")
    if status_value not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status_value}")

    alert_id = f"alert-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    created_at = (now + timedelta(minutes=created_offset_minutes)).isoformat()
    acknowledged_at = (
        (now + timedelta(minutes=acknowledged_offset_minutes)).isoformat()
        if acknowledged_offset_minutes is not None
        else None
    )
    resolved_at = (
        (now + timedelta(minutes=resolved_offset_minutes)).isoformat()
        if resolved_offset_minutes is not None
        else None
    )

    return {
        "alert_id": alert_id,
        "title": title,
        "description": description,
        "priority": priority,
        "status": status_value,
        "event_type": event_type,
        "severity": severity,
        "source_ip": source_ip,
        "user_id": user_id,
        "assigned_to": assigned_to,
        "remediation_steps": remediation_steps or [],
        "resolution": resolution,
        "created_at": created_at,
        "acknowledged_at": acknowledged_at,
        "resolved_at": resolved_at,
        "comments": [],
        "metadata": metadata or {},
    }


def _seed_demo_alerts() -> None:
    """Populate ``_alerts`` with a representative set of demo alerts.

    Three NEW (matching the sidebar badge), one INVESTIGATING, one
    ACKNOWLEDGED, one RESOLVED, one FALSE_POSITIVE — exercises every
    PRIORITY_STYLES branch in the panel and gives the filter tabs varied
    counts.
    """
    seeds = [
        _make_alert(
            title="Brute force authentication attempt detected",
            description=(
                "27 failed login attempts in 90 seconds against the admin "
                "Cognito user pool, all sourced from a single IP outside the "
                "expected GeoIP range. Account lockout policy fired but the "
                "IP continues to retry."
            ),
            priority="P1_CRITICAL",
            status_value="NEW",
            event_type="auth.brute_force_detected",
            severity="critical",
            source_ip="185.220.101.45",
            user_id="admin@aenealabs.com",
            remediation_steps=[
                "Block the source IP at the WAF immediately",
                "Force password rotation for admin@aenealabs.com",
                "Enable MFA enforcement on the affected user pool",
                "Review CloudTrail for any post-auth API activity from the same IP",
            ],
            created_offset_minutes=-7,
            metadata={"failed_attempts": 27, "geo_country": "RU"},
        ),
        _make_alert(
            title="IAM role assumed cross-account from unknown principal",
            description=(
                "AssumeRole call from account 9881-XXXX-XXXX into the "
                "production deploy role. The source account is not on the "
                "approved trust-relationships list maintained in SSM."
            ),
            priority="P1_CRITICAL",
            status_value="NEW",
            event_type="iam.cross_account_assume",
            severity="critical",
            source_ip="3.91.47.214",
            user_id="aura-codebuild-deploy",
            remediation_steps=[
                "Revoke the trust policy entry for the unknown account",
                "Rotate all SSM SecureStrings tagged Project=Aura",
                "Enable GuardDuty's CrossAccountAssumeRole finding type if not already on",
            ],
            created_offset_minutes=-19,
            metadata={"source_account": "988155551111"},
        ),
        _make_alert(
            title="Unusual data egress volume from Neptune cluster",
            description=(
                "Sustained 4.2 GB outbound transfer from the Neptune primary "
                "endpoint to a non-VPC-endpoint destination over 12 minutes. "
                "Daily baseline for this cluster is 180 MB."
            ),
            priority="P2_HIGH",
            status_value="NEW",
            event_type="data.unusual_egress",
            severity="high",
            source_ip=None,
            user_id="neptune-readonly",
            remediation_steps=[
                "Snapshot the Neptune cluster for forensics before any change",
                "Revoke the neptune-readonly IAM session token",
                "Capture VPC flow logs for the egress destination",
            ],
            created_offset_minutes=-44,
            metadata={"egress_bytes": 4_510_000_000, "baseline_bytes": 188_000_000},
        ),
        _make_alert(
            title="Prompt injection attempt blocked in /api/v1/orchestrator/dispatch",
            description=(
                "Semantic Guardrails flagged 4 consecutive requests containing "
                "an instruction-override payload aimed at the Coder agent. "
                "All requests were blocked before reaching Bedrock."
            ),
            priority="P2_HIGH",
            status_value="INVESTIGATING",
            event_type="ai.prompt_injection_blocked",
            severity="high",
            source_ip="52.14.2.91",
            user_id="api-key-svc-fargate-test",
            assigned_to="alice@aenealabs.com",
            remediation_steps=[
                "Review the offending request payloads in the audit log",
                "Confirm the API key originates from an authorized integration",
                "If unauthorized, rotate the key and add the source IP to deny list",
            ],
            created_offset_minutes=-95,
            acknowledged_offset_minutes=-78,
            metadata={
                "blocked_by": "ADR-065",
                "guardrail_layer": "embedding-similarity",
            },
        ),
        _make_alert(
            title="Container escape signature observed in vuln-scan sandbox",
            description=(
                "Falco rule container_escape_attempt fired during patch "
                "validation for approval ID appr-demo-fb84e3. The sandbox "
                "task was terminated automatically."
            ),
            priority="P2_HIGH",
            status_value="ACKNOWLEDGED",
            event_type="runtime.container_escape",
            severity="high",
            assigned_to="ben@aenealabs.com",
            remediation_steps=[
                "Quarantine the patch artifact for forensic review",
                "Reject the corresponding HITL approval request",
                "Capture the runtime baseline diff for the affected sandbox SG",
            ],
            created_offset_minutes=-185,
            acknowledged_offset_minutes=-160,
            metadata={
                "falco_rule": "container_escape_attempt",
                "sandbox_task": "vuln-scan-sb-92",
            },
        ),
        _make_alert(
            title="WAF rate-limit threshold exceeded on /webhooks/github",
            description=(
                "AWS WAF count-mode rule observed 5x the normal rate of "
                "POST traffic against the GitHub webhook endpoint. No payloads "
                "matched signature rules."
            ),
            priority="P3_MEDIUM",
            status_value="RESOLVED",
            event_type="waf.rate_limit_exceeded",
            severity="medium",
            assigned_to="carla@aenealabs.com",
            resolution=(
                "Confirmed legitimate spike from a one-time mass-rebase across "
                "the aenealabs/* organization. Tuned the rule threshold up by "
                "30% for the github-webhook path and aged out the alert."
            ),
            remediation_steps=[
                "Diff the WAF rule threshold against the traffic baseline",
                "Coordinate with the GitHub App owner before tuning",
            ],
            created_offset_minutes=-1440,
            acknowledged_offset_minutes=-1380,
            resolved_offset_minutes=-1320,
            metadata={"waf_rule_id": "RateLimit_GitHub_Webhook"},
        ),
        _make_alert(
            title="Deprecated TLS 1.0 client connection observed",
            description=(
                "An older fleet sensor is still negotiating TLS 1.0 against "
                "the public ALB. The fleet is being decommissioned per the "
                "endpoint-protection migration."
            ),
            priority="P5_INFO",
            status_value="FALSE_POSITIVE",
            event_type="tls.deprecated_protocol",
            severity="low",
            assigned_to="dev@aenealabs.com",
            resolution=(
                "Confirmed match against the documented decommissioning "
                "exception window. No further action required."
            ),
            remediation_steps=[
                "Track the migration ticket through completion",
                "Remove this alert rule once the legacy fleet is retired",
            ],
            created_offset_minutes=-2880,
            acknowledged_offset_minutes=-2820,
            resolved_offset_minutes=-2780,
            metadata={"client_count": 3, "decom_ticket": "OPS-2241"},
        ),
    ]
    for alert in seeds:
        _alerts[alert["alert_id"]] = alert


_seed_flag = os.environ.get("AURA_SEED_MOCK_ALERTS", "true").lower()
if _seed_flag not in ("0", "false", "no", "off"):
    _seed_demo_alerts()
    logger.info(
        "Seeded %d demo security alerts (set AURA_SEED_MOCK_ALERTS=false to disable)",
        len(_alerts),
    )


# ============================================================================
# Pydantic models
# ============================================================================


class AlertCommentRequest(BaseModel):
    user_id: str
    comment: str = Field(min_length=1)


class AcknowledgeRequest(BaseModel):
    user_id: str
    comment: str | None = None


class AssignRequest(BaseModel):
    user_id: str
    assignee: str


class StatusUpdateRequest(BaseModel):
    user_id: str
    status: str
    comment: str | None = None


class ResolveRequest(BaseModel):
    user_id: str
    resolution: str
    actions_taken: list[str] = Field(default_factory=list)


class FalsePositiveRequest(BaseModel):
    user_id: str
    reason: str | None = None


class HITLRequestPayload(BaseModel):
    user_id: str
    justification: str | None = None


# ============================================================================
# Router
# ============================================================================


router = APIRouter(prefix="/api/v1/alerts", tags=["security-alerts"])


def _filter_alerts(
    priority: str | None,
    status_value: str | None,
    assigned_to: str | None,
) -> list[dict[str, Any]]:
    items = list(_alerts.values())
    if priority:
        items = [a for a in items if a["priority"] == priority]
    if status_value:
        items = [a for a in items if a["status"] == status_value]
    if assigned_to:
        items = [a for a in items if a.get("assigned_to") == assigned_to]
    items.sort(key=lambda a: a["created_at"], reverse=True)
    return items


def _compute_stats(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_priority: dict[str, int] = {}
    by_status: dict[str, int] = {}
    unacknowledged = 0
    p1_count = 0
    for a in items:
        by_priority[a["priority"]] = by_priority.get(a["priority"], 0) + 1
        by_status[a["status"]] = by_status.get(a["status"], 0) + 1
        if a["status"] == "NEW":
            unacknowledged += 1
            if a["priority"] == "P1_CRITICAL":
                p1_count += 1
    return {
        "total": len(items),
        "byPriority": by_priority,
        "byStatus": by_status,
        "unacknowledged": unacknowledged,
        "p1_count": p1_count,
    }


@router.get("")
async def list_alerts(
    request: Request,
    priority: str | None = Query(None, description="Filter by priority"),
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status"
    ),
    assigned_to: str | None = Query(
        None, alias="assignedTo", description="Filter by assignee"
    ),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(standard_rate_limit),
) -> dict[str, Any]:
    """List security alerts with optional filtering."""
    if priority and priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"unknown priority: {priority}")
    if status_filter and status_filter not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"unknown status: {status_filter}")

    items = _filter_alerts(priority, status_filter, assigned_to)
    stats = _compute_stats(list(_alerts.values()))

    return {
        "alerts": items[:limit],
        "stats": stats,
    }


@router.get("/stats")
async def get_alert_stats(
    request: Request,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(standard_rate_limit),
) -> dict[str, Any]:
    """Aggregate counts by priority and status across all alerts."""
    return _compute_stats(list(_alerts.values()))


@router.get("/unacknowledged/count")
async def get_unacknowledged_count(
    request: Request,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(standard_rate_limit),
) -> dict[str, int]:
    """Return the sidebar-badge count and the P1 sub-count."""
    new_count = 0
    p1_count = 0
    for a in _alerts.values():
        if a["status"] == "NEW":
            new_count += 1
            if a["priority"] == "P1_CRITICAL":
                p1_count += 1
    return {"total": new_count, "count": new_count, "p1_count": p1_count}


@router.get("/{alert_id}")
async def get_alert_detail(
    alert_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(standard_rate_limit),
) -> dict[str, Any]:
    alert = _alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")
    return alert


@router.get("/{alert_id}/timeline")
async def get_alert_timeline(
    alert_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(standard_rate_limit),
) -> dict[str, Any]:
    alert = _alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")

    events: list[dict[str, str]] = [
        {"event": "Alert Created", "timestamp": alert["created_at"]},
    ]
    if alert.get("acknowledged_at"):
        events.append({"event": "Acknowledged", "timestamp": alert["acknowledged_at"]})
    if alert.get("resolved_at"):
        label = "False Positive" if alert["status"] == "FALSE_POSITIVE" else "Resolved"
        events.append({"event": label, "timestamp": alert["resolved_at"]})
    for c in alert.get("comments", []):
        events.append(
            {
                "event": f"Comment by {c.get('user_id', 'unknown')}",
                "timestamp": c["timestamp"],
                "detail": c.get("comment"),
            }
        )
    return {"alert_id": alert_id, "events": events}


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    request: Request,
    payload: AcknowledgeRequest,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(sensitive_rate_limit),
) -> dict[str, Any]:
    alert = _alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")
    if alert["status"] not in ("NEW", "INVESTIGATING"):
        raise HTTPException(
            status_code=409,
            detail=f"cannot acknowledge alert in status {alert['status']}",
        )
    alert["status"] = "ACKNOWLEDGED"
    alert["acknowledged_at"] = _now_iso()
    alert["assigned_to"] = alert.get("assigned_to") or payload.user_id
    if payload.comment:
        alert["comments"].append(
            {
                "user_id": payload.user_id,
                "comment": payload.comment,
                "timestamp": _now_iso(),
            }
        )
    logger.info(sanitize_log(f"alert {alert_id} acknowledged by {payload.user_id}"))
    return alert


@router.post("/{alert_id}/assign")
async def assign_alert(
    alert_id: str,
    request: Request,
    payload: AssignRequest,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(sensitive_rate_limit),
) -> dict[str, Any]:
    alert = _alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")
    alert["assigned_to"] = payload.assignee
    logger.info(
        sanitize_log(
            f"alert {alert_id} assigned to {payload.assignee} by {payload.user_id}"
        )
    )
    return alert


@router.post("/{alert_id}/status")
async def update_alert_status(
    alert_id: str,
    request: Request,
    payload: StatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(sensitive_rate_limit),
) -> dict[str, Any]:
    alert = _alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"unknown status: {payload.status}")
    alert["status"] = payload.status
    if payload.status == "ACKNOWLEDGED" and not alert.get("acknowledged_at"):
        alert["acknowledged_at"] = _now_iso()
    if payload.status in ("RESOLVED", "FALSE_POSITIVE") and not alert.get(
        "resolved_at"
    ):
        alert["resolved_at"] = _now_iso()
    if payload.comment:
        alert["comments"].append(
            {
                "user_id": payload.user_id,
                "comment": payload.comment,
                "timestamp": _now_iso(),
            }
        )
    return alert


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    request: Request,
    payload: ResolveRequest,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(sensitive_rate_limit),
) -> dict[str, Any]:
    alert = _alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")
    alert["status"] = "RESOLVED"
    alert["resolved_at"] = _now_iso()
    alert["resolution"] = payload.resolution
    if payload.actions_taken:
        alert.setdefault("metadata", {})["actions_taken"] = list(payload.actions_taken)
    logger.info(sanitize_log(f"alert {alert_id} resolved by {payload.user_id}"))
    return alert


@router.post("/{alert_id}/false-positive")
async def mark_false_positive(
    alert_id: str,
    request: Request,
    payload: FalsePositiveRequest,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(sensitive_rate_limit),
) -> dict[str, Any]:
    alert = _alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")
    alert["status"] = "FALSE_POSITIVE"
    alert["resolved_at"] = _now_iso()
    if payload.reason:
        alert["resolution"] = payload.reason
    return alert


@router.post("/{alert_id}/comments")
async def add_alert_comment(
    alert_id: str,
    request: Request,
    payload: AlertCommentRequest,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(sensitive_rate_limit),
) -> dict[str, Any]:
    alert = _alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")
    entry = {
        "user_id": payload.user_id,
        "comment": payload.comment,
        "timestamp": _now_iso(),
    }
    alert["comments"].append(entry)
    return entry


@router.post(
    "/{alert_id}/hitl-request",
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_hitl_review(
    alert_id: str,
    request: Request,
    payload: HITLRequestPayload,
    current_user: User = Depends(get_current_user),
    rate_check: RateLimitResult = Depends(sensitive_rate_limit),
) -> dict[str, Any]:
    alert = _alerts.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")
    alert.setdefault("metadata", {})["hitl_requested_by"] = payload.user_id
    alert["metadata"]["hitl_requested_at"] = _now_iso()
    if payload.justification:
        alert["metadata"]["hitl_justification"] = payload.justification
    logger.info(
        sanitize_log(f"HITL review requested on alert {alert_id} by {payload.user_id}")
    )
    return {"alert_id": alert_id, "hitl_request_status": "queued"}
