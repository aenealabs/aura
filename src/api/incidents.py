"""Incident Investigation API Endpoints (ADR-025 Phase 4).

This module provides REST API endpoints for the HITL Dashboard to:
- List pending incident investigations
- Get investigation details
- Approve/reject mitigation plans
- View investigation history

Integrates with RuntimeIncidentAgent investigation results.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

# DynamoDB client (lazy initialization for testability)
_dynamodb = None
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
INVESTIGATIONS_TABLE = f"aura-incident-investigations-{ENVIRONMENT}"


def _get_dynamodb():
    """Get or create DynamoDB resource (lazy initialization)."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


# ==========================================================================
# Request/Response Models
# ==========================================================================


class InvestigationSummary(BaseModel):
    """Summary of an incident investigation for list view."""

    incident_id: str = Field(..., description="Unique incident identifier")
    timestamp: str = Field(..., description="Investigation timestamp (ISO 8601)")
    source: str = Field(..., description="Incident source (cloudwatch, pagerduty, etc)")
    alert_name: str = Field(..., description="Name of the alert")
    affected_service: str = Field(..., description="Service affected by incident")
    confidence_score: int = Field(..., ge=0, le=100, description="RCA confidence score")
    hitl_status: str = Field(
        ..., description="HITL approval status (pending/approved/rejected)"
    )
    created_at: str = Field(..., description="Investigation creation timestamp")


class CodeEntity(BaseModel):
    """Code entity correlated with incident."""

    entity_id: str
    entity_type: str
    name: str
    file_path: str
    line_number: Optional[int] = None
    namespace: Optional[str] = None


class DeploymentEvent(BaseModel):
    """Deployment event correlated with incident."""

    deployment_id: str
    timestamp: str
    application_name: str
    commit_sha: str
    commit_message: str
    rollout_status: str
    image_tag: str
    deployed_by: str


class GitCommit(BaseModel):
    """Git commit correlated with incident."""

    sha: str
    message: str
    author: str
    timestamp: str
    file_path: str


class InvestigationDetail(BaseModel):
    """Detailed investigation result for detail view."""

    incident_id: str
    timestamp: str
    source: str
    alert_name: str
    affected_service: str
    rca_hypothesis: str
    confidence_score: int
    deployment_correlation: list[DeploymentEvent]
    code_entities: list[CodeEntity]
    git_commits: list[GitCommit]
    mitigation_plan: str
    hitl_status: str
    hitl_approver: Optional[str] = None
    hitl_timestamp: Optional[str] = None
    rejection_reason: Optional[str] = None


class ApprovalRequest(BaseModel):
    """Request to approve a mitigation plan."""

    approver_email: str = Field(..., description="Email of the approver")
    comments: Optional[str] = Field(None, description="Optional approval comments")


class RejectionRequest(BaseModel):
    """Request to reject a mitigation plan."""

    approver_email: str = Field(..., description="Email of the approver")
    reason: str = Field(..., description="Reason for rejection")


class ApprovalResponse(BaseModel):
    """Response after approval/rejection."""

    status: str
    incident_id: str
    message: str


# ==========================================================================
# API Endpoints
# ==========================================================================


@router.get(
    "/investigations",
    response_model=list[InvestigationSummary],
    summary="List incident investigations",
    description="Retrieve list of incident investigations, optionally filtered by HITL status",
)
async def list_investigations(
    hitl_status: Optional[str] = Query(  # noqa: B008
        None,
        description="Filter by HITL status (pending/approved/rejected)",
        regex="^(pending|approved|rejected)$",
    ),
    limit: int = Query(  # noqa: B008
        50, ge=1, le=100, description="Maximum number of results"
    ),  # noqa: B008
) -> list[InvestigationSummary]:
    """
    List incident investigations.

    Returns investigations sorted by timestamp (most recent first).
    """
    table = _get_dynamodb().Table(INVESTIGATIONS_TABLE)

    try:
        if hitl_status:
            # Query by HITL status using GSI
            response = table.query(
                IndexName="by-hitl-status",
                KeyConditionExpression=Key("hitl_status").eq(hitl_status),
                Limit=limit,
                ScanIndexForward=False,  # Most recent first
            )
        else:
            # Scan all investigations
            response = table.scan(Limit=limit)

        items = response.get("Items", [])

        # Convert to response model
        investigations = [
            InvestigationSummary(
                incident_id=item["incident_id"],
                timestamp=item["timestamp"],
                source=item["source"],
                alert_name=item["alert_name"],
                affected_service=item["affected_service"],
                confidence_score=item["confidence_score"],
                hitl_status=item["hitl_status"],
                created_at=item["timestamp"],
            )
            for item in items
        ]

        logger.info(
            f"Retrieved {sanitize_log(len(investigations))} investigations (hitl_status={sanitize_log(hitl_status)})"
        )
        return investigations

    except Exception as e:
        logger.error(f"Failed to list investigations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve investigations")


@router.get(
    "/investigations/{incident_id}",
    response_model=InvestigationDetail,
    summary="Get investigation details",
    description="Retrieve detailed investigation results including RCA, code entities, and mitigation plan",
)
async def get_investigation(incident_id: str) -> InvestigationDetail:
    """
    Get detailed investigation results.

    Args:
        incident_id: Unique identifier for the incident

    Returns:
        Detailed investigation result with RCA, code entities, deployments, git commits
    """
    table = _get_dynamodb().Table(INVESTIGATIONS_TABLE)

    try:
        # Query by incident_id (HASH key)
        response = table.query(
            KeyConditionExpression=Key("incident_id").eq(incident_id),
            Limit=1,
            ScanIndexForward=False,  # Most recent
        )

        items = response.get("Items", [])
        if not items:
            raise HTTPException(
                status_code=404, detail=f"Investigation not found: {incident_id}"
            )

        item = items[0]

        # Convert to response model
        investigation = InvestigationDetail(
            incident_id=item["incident_id"],
            timestamp=item["timestamp"],
            source=item["source"],
            alert_name=item["alert_name"],
            affected_service=item["affected_service"],
            rca_hypothesis=item["rca_hypothesis"],
            confidence_score=item["confidence_score"],
            deployment_correlation=[
                DeploymentEvent(**d) for d in item.get("deployment_correlation", [])
            ],
            code_entities=[CodeEntity(**e) for e in item.get("code_entities", [])],
            git_commits=[GitCommit(**c) for c in item.get("git_commits", [])],
            mitigation_plan=item["mitigation_plan"],
            hitl_status=item["hitl_status"],
            hitl_approver=item.get("hitl_approver"),
            hitl_timestamp=item.get("hitl_timestamp"),
            rejection_reason=item.get("rejection_reason"),
        )

        logger.info(f"Retrieved investigation details: {sanitize_log(incident_id)}")
        return investigation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get investigation {sanitize_log(incident_id)}: {sanitize_log(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve investigation")


@router.post(
    "/investigations/{incident_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve mitigation plan",
    description="Approve the proposed mitigation plan for execution",
)
async def approve_mitigation(
    incident_id: str, approval: ApprovalRequest
) -> ApprovalResponse:
    """
    Approve mitigation plan for execution.

    Args:
        incident_id: Unique identifier for the incident
        approval: Approval request with approver email

    Returns:
        Approval confirmation
    """
    table = _get_dynamodb().Table(INVESTIGATIONS_TABLE)

    try:
        # First, verify investigation exists and is pending
        response = table.query(
            KeyConditionExpression=Key("incident_id").eq(incident_id), Limit=1
        )

        items = response.get("Items", [])
        if not items:
            raise HTTPException(
                status_code=404, detail=f"Investigation not found: {incident_id}"
            )

        item = items[0]
        if item["hitl_status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Investigation is not pending (status: {item['hitl_status']})",
            )

        # Update HITL status to approved
        table.update_item(
            Key={
                "incident_id": incident_id,
                "timestamp": item["timestamp"],
            },
            UpdateExpression="SET hitl_status = :approved, hitl_approver = :email, hitl_timestamp = :ts, approval_comments = :comments",
            ExpressionAttributeValues={
                ":approved": "approved",
                ":email": approval.approver_email,
                ":ts": datetime.now(timezone.utc).isoformat(),
                ":comments": approval.comments or "",
            },
        )

        logger.info(
            f"Investigation {sanitize_log(incident_id)} approved by {sanitize_log(approval.approver_email)}"
        )

        # TODO: Trigger mitigation execution (Step Functions or direct action)
        # This will be implemented in Phase 6

        return ApprovalResponse(
            status="approved",
            incident_id=incident_id,
            message=f"Mitigation plan approved by {approval.approver_email}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to approve investigation {sanitize_log(incident_id)}: {sanitize_log(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to approve mitigation")


@router.post(
    "/investigations/{incident_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject mitigation plan",
    description="Reject the proposed mitigation plan with a reason",
)
async def reject_mitigation(
    incident_id: str, rejection: RejectionRequest
) -> ApprovalResponse:
    """
    Reject mitigation plan.

    Args:
        incident_id: Unique identifier for the incident
        rejection: Rejection request with approver email and reason

    Returns:
        Rejection confirmation
    """
    table = _get_dynamodb().Table(INVESTIGATIONS_TABLE)

    try:
        # First, verify investigation exists and is pending
        response = table.query(
            KeyConditionExpression=Key("incident_id").eq(incident_id), Limit=1
        )

        items = response.get("Items", [])
        if not items:
            raise HTTPException(
                status_code=404, detail=f"Investigation not found: {incident_id}"
            )

        item = items[0]
        if item["hitl_status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Investigation is not pending (status: {item['hitl_status']})",
            )

        # Update HITL status to rejected
        table.update_item(
            Key={
                "incident_id": incident_id,
                "timestamp": item["timestamp"],
            },
            UpdateExpression="SET hitl_status = :rejected, hitl_approver = :email, hitl_timestamp = :ts, rejection_reason = :reason",
            ExpressionAttributeValues={
                ":rejected": "rejected",
                ":email": rejection.approver_email,
                ":ts": datetime.now(timezone.utc).isoformat(),
                ":reason": rejection.reason,
            },
        )

        logger.info(
            f"Investigation {sanitize_log(incident_id)} rejected by {sanitize_log(rejection.approver_email)}: {sanitize_log(rejection.reason)}"
        )

        return ApprovalResponse(
            status="rejected",
            incident_id=incident_id,
            message=f"Mitigation plan rejected by {rejection.approver_email}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to reject investigation {sanitize_log(incident_id)}: {sanitize_log(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to reject mitigation")


@router.get(
    "/statistics",
    summary="Get investigation statistics",
    description="Retrieve statistics about incident investigations (total, by status, avg confidence)",
)
async def get_statistics() -> dict[str, Any]:
    """
    Get investigation statistics.

    Returns:
        Statistics including total investigations, counts by status, avg confidence
    """
    table = _get_dynamodb().Table(INVESTIGATIONS_TABLE)

    try:
        # Scan all investigations (in production, use aggregation table)
        response = table.scan()
        items = response.get("Items", [])

        # Calculate statistics
        total = len(items)
        pending = sum(1 for item in items if item["hitl_status"] == "pending")
        approved = sum(1 for item in items if item["hitl_status"] == "approved")
        rejected = sum(1 for item in items if item["hitl_status"] == "rejected")

        # Average confidence score
        confidence_scores = [item["confidence_score"] for item in items]
        avg_confidence = (
            sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        )

        # Average by status
        pending_items = [item for item in items if item["hitl_status"] == "pending"]
        avg_pending_confidence = (
            sum(item["confidence_score"] for item in pending_items) / len(pending_items)
            if pending_items
            else 0
        )

        statistics = {
            "total_investigations": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "avg_confidence_score": round(avg_confidence, 2),
            "avg_pending_confidence": round(avg_pending_confidence, 2),
            "approval_rate": round((approved / total * 100) if total > 0 else 0, 2),
        }

        logger.info(f"Retrieved investigation statistics: {statistics}")
        return statistics

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")
