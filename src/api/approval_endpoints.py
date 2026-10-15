"""
Project Aura - HITL Approval API Endpoints

REST API endpoints for the Human-in-the-Loop approval workflow.
Connects the frontend ApprovalDashboard to the HITLApprovalService.

Endpoints:
- GET  /api/v1/approvals          - List approval requests
- GET  /api/v1/approvals/{id}     - Get single approval request
- POST /api/v1/approvals/{id}/approve - Approve a request
- POST /api/v1/approvals/{id}/reject  - Reject a request
- POST /api/v1/approvals/{id}/cancel  - Cancel a request
- GET  /api/v1/approvals/stats    - Get approval statistics

Security:
- Every route requires an authenticated user (Cognito JWT via get_current_user).
- State-changing routes (approve/reject/cancel) additionally require a role
  permitted to approve patches (``security-engineer`` or ``admin``), matching
  ACTION_ROLE_MAPPING["approve_patch"] in
  src/services/authorization/abac_contracts.py.
- Reviewer identity is always taken from the authenticated token, never from
  the request body. A body ``reviewer_email`` that disagrees with the token is
  rejected with 403 rather than silently ignored.
- A human requester cannot approve their own request (separation of duties).
- Tenant isolation: an approval belongs to the organization recorded in
  ``metadata["organization_id"]`` (set by
  ``HITLApprovalService.create_or_auto_approve``). Callers only see and act
  on approvals of their own ``User.organization_id``; list and stats are
  filtered, and detail/approve/reject/cancel on another tenant's approval
  return 404 so its existence is not revealed. Approvals with no organization
  (legacy or system-generated) are visible only to platform admins
  (``platform_admin`` group), never to org-level admins, because their tenant
  is unknown. Platform admins are not granted access to other tenants'
  approvals.
"""

import logging
from collections import Counter
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.api.anomaly_triggers import get_triggers
from src.api.auth import User, get_current_user, require_role
from src.api.dependencies import get_hitl_service, get_notification_service
from src.api.log_sanitizer import sanitize_log
from src.services.api_rate_limiter import (
    RateLimitResult,
    critical_rate_limit,
    sensitive_rate_limit,
    standard_rate_limit,
)
from src.services.hitl_approval_service import (
    ApprovalRequest,
    ApprovalStatus,
    HITLApprovalError,
    HITLApprovalService,
    PatchSeverity,
)

logger = logging.getLogger(__name__)

# Roles allowed to make approval decisions. Kept in sync with
# ACTION_ROLE_MAPPING["approve_patch"] in
# src/services/authorization/abac_contracts.py.
APPROVER_ROLES: tuple[str, ...] = ("security-engineer", "admin")

require_approver = require_role(*APPROVER_ROLES)

# ============================================================================
# Pydantic Models for API Requests/Responses
# ============================================================================


class ApprovalListItem(BaseModel):
    """Condensed approval item for list view."""

    id: str
    title: str
    vulnerability: dict[str, Any]
    patch: dict[str, Any]
    status: str
    severity: str
    created_at: str
    requested_by: str
    approved_by: str | None = None
    approved_at: str | None = None
    rejected_by: str | None = None
    rejected_at: str | None = None


class ApprovalListResponse(BaseModel):
    """Response for approval list endpoint."""

    approvals: list[ApprovalListItem]
    total: int
    pending: int
    approved: int
    rejected: int


class ApprovalExplainabilityResponse(BaseModel):
    """Explainability evidence (ADR-068) shown to the approver."""

    record_id: str | None = None
    summary: str | None = None
    confidence: float | None = None
    reasoning_chain: list[dict[str, Any]] = Field(default_factory=list)


class ApprovalDetailResponse(BaseModel):
    """Full approval details for detail view."""

    id: str
    title: str
    description: str
    vulnerability: dict[str, Any]
    patch: dict[str, Any]
    sandbox_results: dict[str, Any] | None = None
    status: str
    severity: str
    created_at: str
    requested_by: str
    approved_by: str | None = None
    approved_at: str | None = None
    rejected_by: str | None = None
    rejected_at: str | None = None
    rejection_reason: str | None = None
    metadata: dict[str, Any] | None = None
    explainability: ApprovalExplainabilityResponse | None = None


_REVIEWER_EMAIL_DESCRIPTION = (
    "Deprecated. Reviewer identity is taken from the authenticated token. "
    "If supplied, it must match the authenticated user or the request is "
    "rejected with 403."
)


class ApproveRequest(BaseModel):
    """Request to approve a patch."""

    reviewer_email: str | None = Field(None, description=_REVIEWER_EMAIL_DESCRIPTION)
    comment: str | None = Field(None, description="Optional approval comment")


class RejectRequest(BaseModel):
    """Request to reject a patch."""

    reviewer_email: str | None = Field(None, description=_REVIEWER_EMAIL_DESCRIPTION)
    reason: str = Field(..., min_length=1, description="Reason for rejection")


class ApprovalActionResponse(BaseModel):
    """Response for approve/reject actions."""

    success: bool
    approval_id: str
    new_status: str
    message: str
    reviewed_by: str | None = None


class ApprovalStatsResponse(BaseModel):
    """Statistics about approval requests."""

    total: int
    pending: int
    approved: int
    rejected: int
    expired: int
    avg_approval_time_hours: float | None = None
    by_severity: dict[str, int]


# ============================================================================
# Router Setup
# ============================================================================

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

# Service instances are now managed via src.api.dependencies using @lru_cache
# factories and FastAPI's Depends() pattern for clean dependency injection.
# Test overrides: app.dependency_overrides[get_hitl_service] = lambda: mock


def _send_decision_notification(
    approval_id: str,
    patch_id: str,
    decision: str,
    reviewer_email: str,
    approval_reviewer_email: str | None,
    reason: str | None = None,
) -> None:
    """
    Send notification for approval decision.

    Consolidates duplicate notification logic from approve/reject endpoints.

    Args:
        approval_id: The approval request ID
        patch_id: The patch ID being approved/rejected
        decision: "APPROVED" or "REJECTED"
        reviewer_email: Email of reviewer making the decision
        approval_reviewer_email: Email from original approval request
        reason: Optional reason for the decision
    """
    notifier = get_notification_service()
    if not notifier:
        return

    # Build deduplicated recipient list
    recipients = []
    if approval_reviewer_email:
        recipients.append(approval_reviewer_email)
    if reviewer_email and reviewer_email not in recipients:
        recipients.append(reviewer_email)

    if not recipients:
        return

    try:
        notifier.send_decision_notification(
            approval_id=approval_id,
            patch_id=patch_id,
            decision=decision,
            reviewer=reviewer_email,
            reason=reason,
            recipients=recipients,
        )
        logger.info(
            f"Sent {sanitize_log(decision.lower())} notification for {sanitize_log(approval_id)}"
        )
    except Exception as err:
        # Don't fail the approval/rejection if notification fails
        logger.warning(f"Failed to send {decision.lower()} notification: {err}")


def _reviewer_identity(user: User) -> str:
    """Return the identity recorded for a reviewer: email, falling back to sub."""
    return user.email or user.sub


def _identities_match(claimed: str, user: User) -> bool:
    """Case-insensitive match of a claimed identity against the user's email/sub."""
    claimed_norm = claimed.strip().lower()
    known = {v.strip().lower() for v in (user.email, user.sub) if v}
    return claimed_norm in known


def _reject_reviewer_mismatch(claimed: str | None, user: User) -> None:
    """Refuse requests whose body claims a reviewer other than the caller."""
    if claimed is not None and not _identities_match(claimed, user):
        logger.warning(
            f"Reviewer identity mismatch: token user {sanitize_log(user.sub)} "
            f"submitted reviewer_email {sanitize_log(claimed)}"
        )
        raise HTTPException(
            status_code=403,
            detail="reviewer_email does not match the authenticated user",
        )


def _can_access_approval(metadata: dict[str, Any] | None, user: User) -> bool:
    """
    Return True if ``user`` may see or act on an approval with ``metadata``.

    - Approval owned by an organization: only callers in that same
      organization. Callers with no organization claim never match.
    - Approval with no organization (legacy / system-generated): only platform
      admins, since the owning tenant cannot be determined. The org-level
      ``admin`` group is deliberately insufficient (see ``User.is_platform_admin``).
    """
    approval_org = (metadata or {}).get("organization_id")
    if approval_org:
        return user.organization_id is not None and approval_org == (
            user.organization_id
        )
    return user.is_platform_admin


def _get_existing_request(
    service: HITLApprovalService, approval_id: str, user: User
) -> ApprovalRequest:
    """
    Fetch an approval request visible to ``user`` or raise 404.

    Another tenant's approval is reported exactly like a missing one so the
    response does not reveal that the ID exists.
    """
    approval = service.get_request(approval_id)
    if not approval or not _can_access_approval(approval.metadata, user):
        if approval:
            logger.warning(
                f"Cross-tenant approval access denied: {sanitize_log(approval_id)} "
                f"requested by {sanitize_log(user.sub)} "
                f"(org={sanitize_log(user.organization_id)})"
            )
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")
    return approval


def _enforce_separation_of_duties(approval: ApprovalRequest, user: User) -> None:
    """
    Refuse a decision by the same human who requested the approval.

    ``metadata["requested_by"]`` holds either a pipeline/agent name (e.g.
    ``scanner-pipeline``) or a human identity. Only an exact match against the
    caller's email or sub is treated as self-approval, so agent-originated
    requests are unaffected.
    """
    requested_by = (approval.metadata or {}).get("requested_by")
    if isinstance(requested_by, str) and _identities_match(requested_by, user):
        logger.warning(
            f"Self-approval blocked for {sanitize_log(approval.approval_id)} "
            f"by {sanitize_log(user.sub)}"
        )
        raise HTTPException(
            status_code=403,
            detail="Requesters cannot approve or reject their own requests",
        )


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("", response_model=ApprovalListResponse)
async def list_approvals(
    request: Request,
    status: str | None = Query(  # noqa: B008
        None, description="Filter by status (pending, approved, rejected)"
    ),
    severity: str | None = Query(  # noqa: B008
        None, description="Filter by severity (critical, high, medium, low)"
    ),
    limit: int = Query(  # noqa: B008
        50, ge=1, le=200, description="Maximum results to return"
    ),  # noqa: B008
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
    service: HITLApprovalService = Depends(get_hitl_service),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> ApprovalListResponse:
    """
    List approval requests with optional filtering.

    Returns condensed approval items suitable for list/table view.
    """

    try:
        # Get all approvals (returns dicts), scoped to the caller's tenant
        all_approvals = [
            a
            for a in service.get_all_requests(limit=1000)
            if _can_access_approval(a.get("metadata"), user)
        ]
        approvals = list(all_approvals)  # Make a copy for filtering

        # Apply status filter if provided
        if status:
            status_enum = ApprovalStatus[status.upper()]
            approvals = [a for a in approvals if a.get("status") == status_enum.value]

        # Apply severity filter if provided
        if severity:
            severity_enum = PatchSeverity[severity.upper()]
            approvals = [
                a for a in approvals if a.get("severity") == severity_enum.value
            ]
        # Count statuses in single pass - O(n) instead of O(4n)
        status_counts = Counter(a.get("status") for a in all_approvals)
        pending_count = status_counts.get(ApprovalStatus.PENDING.value, 0)
        approved_count = status_counts.get(ApprovalStatus.APPROVED.value, 0)
        rejected_count = status_counts.get(ApprovalStatus.REJECTED.value, 0)

        # Transform to response format
        items = []
        for approval in approvals[:limit]:
            # Get metadata dict for additional fields
            metadata = approval.get("metadata") or {}
            items.append(
                ApprovalListItem(
                    id=approval.get("approval_id", ""),
                    title=metadata.get(
                        "title", f"Patch for {approval.get('patch_id', 'unknown')}"
                    ),
                    vulnerability={
                        "cve": approval.get("vulnerability_id"),
                        "severity": approval.get("severity", "MEDIUM").lower(),
                        "description": metadata.get(
                            "description", "Security patch requiring review"
                        ),
                    },
                    patch={
                        "file": metadata.get("affected_file", "unknown"),
                        "linesChanged": metadata.get("lines_changed", 0),
                        "generatedBy": metadata.get("generated_by", "coder-agent"),
                        "sandboxStatus": metadata.get("sandbox_status", "pending"),
                        "testResults": metadata.get("test_results"),
                    },
                    status=approval.get("status", "PENDING").lower(),
                    severity=approval.get("severity", "MEDIUM").lower(),
                    created_at=approval.get("created_at", datetime.now().isoformat()),
                    requested_by=metadata.get("requested_by", "system"),
                    approved_by=(
                        approval.get("reviewed_by")
                        if approval.get("status") == "APPROVED"
                        else None
                    ),
                    approved_at=(
                        approval.get("reviewed_at")
                        if approval.get("status") == "APPROVED"
                        else None
                    ),
                    rejected_by=(
                        approval.get("reviewed_by")
                        if approval.get("status") == "REJECTED"
                        else None
                    ),
                    rejected_at=(
                        approval.get("reviewed_at")
                        if approval.get("status") == "REJECTED"
                        else None
                    ),
                )
            )

        return ApprovalListResponse(
            approvals=items,
            total=len(all_approvals),
            pending=pending_count,
            approved=approved_count,
            rejected=rejected_count,
        )

    except Exception as e:
        logger.error(f"Error listing approvals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error listing approvals")


@router.get("/stats", response_model=ApprovalStatsResponse)
async def get_approval_stats(
    request: Request,
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
    service: HITLApprovalService = Depends(get_hitl_service),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> ApprovalStatsResponse:
    """
    Get statistics about approval requests.

    Returns counts by status and severity, plus average approval time,
    scoped to approvals the caller's organization can see.
    """

    try:
        stats = service.get_statistics(
            metadata_filter=lambda metadata: _can_access_approval(metadata, user)
        )

        return ApprovalStatsResponse(
            total=stats.get("total_requests", stats.get("total", 0)),
            pending=stats.get("pending", 0),
            approved=stats.get("approved", 0),
            rejected=stats.get("rejected", 0),
            expired=stats.get("expired", 0),
            avg_approval_time_hours=stats.get("avg_approval_time_hours"),
            by_severity=stats.get("by_severity", {}),
        )

    except Exception as e:
        logger.error(f"Error getting approval stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error getting stats")


@router.get("/{approval_id}", response_model=ApprovalDetailResponse)
async def get_approval(
    request: Request,
    approval_id: str,
    rate_check: RateLimitResult = Depends(standard_rate_limit),  # noqa: B008
    service: HITLApprovalService = Depends(get_hitl_service),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> ApprovalDetailResponse:
    """
    Get detailed information about a specific approval request.

    Returns full approval details including sandbox results and diff.
    """

    try:
        approval = _get_existing_request(service, approval_id, user)

        return ApprovalDetailResponse(
            id=approval.approval_id,
            title=approval.metadata.get("title", f"Patch for {approval.patch_id}"),
            description=approval.metadata.get(
                "description", "Security patch requiring human review"
            ),
            vulnerability={
                "cve": approval.vulnerability_id,
                "severity": approval.severity.value.lower(),
                "description": approval.metadata.get("vulnerability_description", ""),
                "affectedComponent": approval.metadata.get("affected_component"),
            },
            patch={
                "file": approval.metadata.get("affected_file", "unknown"),
                "linesChanged": approval.metadata.get("lines_changed", 0),
                "generatedBy": approval.metadata.get("generated_by", "coder-agent"),
                "sandboxStatus": approval.metadata.get("sandbox_status", "pending"),
                "testResults": approval.metadata.get("test_results"),
                "diff": approval.patch_diff,
            },
            sandbox_results=(
                approval.sandbox_test_results if approval.sandbox_test_results else None
            ),
            status=approval.status.value.lower(),
            severity=approval.severity.value.lower(),
            created_at=approval.created_at,
            requested_by=approval.metadata.get("requested_by", "system"),
            approved_by=(
                approval.reviewed_by
                if approval.status == ApprovalStatus.APPROVED
                else None
            ),
            approved_at=(
                approval.reviewed_at
                if approval.status == ApprovalStatus.APPROVED
                else None
            ),
            rejected_by=(
                approval.reviewed_by
                if approval.status == ApprovalStatus.REJECTED
                else None
            ),
            rejected_at=(
                approval.reviewed_at
                if approval.status == ApprovalStatus.REJECTED
                else None
            ),
            rejection_reason=(
                approval.decision_reason
                if approval.status == ApprovalStatus.REJECTED
                else None
            ),
            metadata=approval.metadata,
            explainability=(
                ApprovalExplainabilityResponse(**approval.explainability.to_dict())
                if approval.explainability
                else None
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting approval {sanitize_log(approval_id)}: {sanitize_log(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Error getting approval")


@router.post("/{approval_id}/approve", response_model=ApprovalActionResponse)
async def approve_request(
    http_request: Request,
    approval_id: str,
    request: ApproveRequest,
    rate_check: RateLimitResult = Depends(  # noqa: B008
        critical_rate_limit
    ),  # 2 req/min - critical approval
    service: HITLApprovalService = Depends(get_hitl_service),  # noqa: B008
    user: User = Depends(require_approver),  # noqa: B008
) -> ApprovalActionResponse:
    """
    Approve a pending approval request.

    This triggers deployment of the patch to the target environment.
    Requires the ``security-engineer`` or ``admin`` role. The reviewer
    identity is taken from the authenticated token.
    """
    _reject_reviewer_mismatch(request.reviewer_email, user)
    reviewer = _reviewer_identity(user)

    try:
        # Get approval details before updating (for notification)
        approval = _get_existing_request(service, approval_id, user)
        _enforce_separation_of_duties(approval, user)

        if not service.approve_request(
            approval_id=approval_id,
            reviewer_id=reviewer,
            reason=request.comment,
        ):
            raise HTTPException(
                status_code=409,
                detail="Approval request is no longer pending or has expired",
            )

        logger.info(
            f"Approval {sanitize_log(approval_id)} approved by "
            f"{sanitize_log(reviewer)} (sub={sanitize_log(user.sub)})"
        )

        # Record approval decision for anomaly detection
        triggers = get_triggers()
        if triggers:
            # Calculate time-to-approve if we have created_at
            approval_time_hours = None
            if approval.created_at:
                try:
                    created = datetime.fromisoformat(
                        approval.created_at.replace("Z", "+00:00")
                    )
                    now = datetime.now(created.tzinfo or None)
                    approval_time_hours = (now - created).total_seconds() / 3600
                except Exception:
                    pass

            triggers.record_approval_decision(
                decision="approved",
                severity=approval.severity.value.lower(),
                approval_time_hours=approval_time_hours,
                reviewer=reviewer,
            )

        # Send approval notification
        _send_decision_notification(
            approval_id=approval_id,
            patch_id=approval.patch_id,
            decision="APPROVED",
            reviewer_email=reviewer,
            approval_reviewer_email=approval.reviewer_email,
            reason=request.comment,
        )

        return ApprovalActionResponse(
            success=True,
            approval_id=approval_id,
            new_status="approved",
            message=f"Approval request {approval_id} approved by {reviewer}",
            reviewed_by=reviewer,
        )

    except HTTPException:
        raise
    except HITLApprovalError as e:
        logger.warning(
            f"Approval request error for {sanitize_log(approval_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=400, detail="Approval request cannot be processed"
        )
    except Exception as e:
        logger.error(
            f"Error approving {sanitize_log(approval_id)}: {sanitize_log(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Error approving request")


@router.post("/{approval_id}/reject", response_model=ApprovalActionResponse)
async def reject_request(
    http_request: Request,
    approval_id: str,
    request: RejectRequest,
    rate_check: RateLimitResult = Depends(  # noqa: B008
        critical_rate_limit
    ),  # 2 req/min - critical rejection
    service: HITLApprovalService = Depends(get_hitl_service),  # noqa: B008
    user: User = Depends(require_approver),  # noqa: B008
) -> ApprovalActionResponse:
    """
    Reject a pending approval request.

    Requires a reason explaining why the patch was rejected. Requires the
    ``security-engineer`` or ``admin`` role. The reviewer identity is taken
    from the authenticated token.
    """
    _reject_reviewer_mismatch(request.reviewer_email, user)
    reviewer = _reviewer_identity(user)

    try:
        # Get approval details before updating (for notification)
        approval = _get_existing_request(service, approval_id, user)
        _enforce_separation_of_duties(approval, user)

        if not service.reject_request(
            approval_id=approval_id,
            reviewer_id=reviewer,
            reason=request.reason,
        ):
            raise HTTPException(
                status_code=409,
                detail="Approval request is no longer pending or has expired",
            )

        logger.info(
            f"Approval {sanitize_log(approval_id)} rejected by "
            f"{sanitize_log(reviewer)} (sub={sanitize_log(user.sub)})"
        )

        # Record rejection for anomaly detection
        triggers = get_triggers()
        if triggers:
            triggers.record_approval_decision(
                decision="rejected",
                severity=approval.severity.value.lower(),
                approval_time_hours=None,  # Rejection time less relevant
                reviewer=reviewer,
            )

        # Send rejection notification
        _send_decision_notification(
            approval_id=approval_id,
            patch_id=approval.patch_id,
            decision="REJECTED",
            reviewer_email=reviewer,
            approval_reviewer_email=approval.reviewer_email,
            reason=request.reason,
        )

        return ApprovalActionResponse(
            success=True,
            approval_id=approval_id,
            new_status="rejected",
            message=f"Approval request {approval_id} rejected by {reviewer}: {request.reason}",
            reviewed_by=reviewer,
        )

    except HTTPException:
        raise
    except HITLApprovalError as e:
        logger.warning(
            f"Rejection request error for {sanitize_log(approval_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=400, detail="Rejection request cannot be processed"
        )
    except Exception as e:
        logger.error(
            f"Error rejecting {sanitize_log(approval_id)}: {sanitize_log(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Error rejecting request")


@router.post("/{approval_id}/cancel", response_model=ApprovalActionResponse)
async def cancel_request(
    http_request: Request,
    approval_id: str,
    rate_check: RateLimitResult = Depends(  # noqa: B008
        sensitive_rate_limit
    ),  # 10 req/min - sensitive op
    service: HITLApprovalService = Depends(get_hitl_service),  # noqa: B008
    user: User = Depends(require_approver),  # noqa: B008
) -> ApprovalActionResponse:
    """
    Cancel a pending approval request.

    Used when a patch is no longer needed (e.g., superseded by another fix).
    Requires the ``security-engineer`` or ``admin`` role.
    """
    reviewer = _reviewer_identity(user)

    try:
        _get_existing_request(service, approval_id, user)

        if not service.cancel_request(approval_id, reason=f"Cancelled by {reviewer}"):
            raise HTTPException(
                status_code=409,
                detail="Approval request not found or no longer pending",
            )

        logger.info(
            f"Approval {sanitize_log(approval_id)} cancelled by "
            f"{sanitize_log(reviewer)} (sub={sanitize_log(user.sub)})"
        )

        return ApprovalActionResponse(
            success=True,
            approval_id=approval_id,
            new_status="cancelled",
            message=f"Approval request {approval_id} cancelled",
            reviewed_by=reviewer,
        )

    except HTTPException:
        raise
    except HITLApprovalError as e:
        logger.warning(
            f"Cancel request error for {sanitize_log(approval_id)}: {sanitize_log(e)}"
        )
        raise HTTPException(
            status_code=400, detail="Cancellation request cannot be processed"
        )
    except Exception as e:
        logger.error(
            f"Error cancelling {sanitize_log(approval_id)}: {sanitize_log(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Error cancelling request")
