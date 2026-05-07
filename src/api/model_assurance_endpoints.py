"""Project Aura - Model Assurance HITL API endpoints.

ADR-088 §Stage 7. Connects the React ``ModelAssuranceQueue`` frontend
to the model_assurance pipeline. Five operations:

    GET  /api/v1/model-assurance/approval-queue
    GET  /api/v1/model-assurance/reports/{report_id}
    POST /api/v1/model-assurance/reports/{report_id}/approve
    POST /api/v1/model-assurance/reports/{report_id}/reject
    POST /api/v1/model-assurance/reports/{report_id}/spot-check

The endpoints are deliberately mock-friendly. Production wiring will
swap the in-memory store for a DynamoDB-backed reader against the
``aura-model-assurance-revisions-${env}`` table provisioned by the
storage stack. v1 ships with a synthetic queue so the UI works
immediately on a fresh deployment, matching the existing
``approval_endpoints.py`` graceful-degradation pattern.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/model-assurance",
    tags=["model-assurance"],
)


# ============================================================================
# In-memory store (placeholder)
# ============================================================================
#
# Production wiring replaces _ReportStore with a DynamoDB adapter
# against the ``aura-model-assurance-revisions-${env}`` table.
# The interface kept narrow so that swap is a single-class change.


class _ReportStore:
    """Thread-safe in-memory pending-report store with deterministic seed data."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._reports: dict[str, dict[str, Any]] = {}
        self._seed()

    def _seed(self) -> None:
        now = datetime.now(timezone.utc)
        self._reports = {
            "ma-rpt-2026-05-06-001": {
                "report_id": "ma-rpt-2026-05-06-001",
                "candidate_id": "anthropic.claude-3-7-sonnet-20260301-v1:0",
                "candidate_display_name": "Claude 3.7 Sonnet",
                "incumbent_id": "anthropic.claude-3-5-sonnet-20240620-v1:0",
                "pipeline_decision": "hitl_queued",
                "overall_utility": 0.943,
                "incumbent_utility": 0.912,
                "floor_violations": [],
                "axis_scores": {
                    "MA1_code_comprehension": 0.94,
                    "MA2_vulnerability_detection_recall": 0.96,
                    "MA3_patch_functional_correctness": 0.91,
                    "MA4_patch_security_equivalence": 0.97,
                    "MA5_latency_token_efficiency": 0.86,
                    "MA6_guardrail_compliance": 0.99,
                },
                "cost_analysis": {
                    "candidate_input_mtok": 3.5,
                    "candidate_output_mtok": 17.5,
                    "incumbent_input_mtok": 3.0,
                    "incumbent_output_mtok": 15.0,
                    "monthly_delta_estimate": 875.0,
                },
                "risk_notes": [
                    "training-data lineage missing from provenance",
                    "assurance verdict: accept",
                ],
                "provenance_summary": "verdict=approved trust=0.910",
                "edge_cases": [
                    {
                        "case_id": "patch-0017",
                        "description": "candidate improved on this case",
                        "candidate_passed": True,
                        "incumbent_passed": False,
                        "delta_label": "improved",
                    },
                    {
                        "case_id": "patch-0083",
                        "description": "candidate regressed on this case",
                        "candidate_passed": False,
                        "incumbent_passed": True,
                        "delta_label": "regressed",
                    },
                ],
                "spot_checks": [],
                "generated_at": (now - timedelta(hours=1)).isoformat(),
            },
        }

    def list_pending(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._reports.values())

    def get(self, report_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._reports.get(report_id)

    def remove(self, report_id: str) -> bool:
        with self._lock:
            return self._reports.pop(report_id, None) is not None

    def append_spot_check(
        self, report_id: str, case_id: str, human_pass: bool, notes: str
    ) -> bool:
        with self._lock:
            report = self._reports.get(report_id)
            if report is None:
                return False
            spot_checks = list(report.get("spot_checks", []))
            spot_checks.append(
                {
                    "case_id": case_id,
                    "automated_pass": True,
                    "human_pass": human_pass,
                    "notes": notes,
                    "disagrees": (not human_pass),
                }
            )
            report["spot_checks"] = spot_checks
            return True


_STORE = _ReportStore()


# ============================================================================
# Pydantic models
# ============================================================================


class IntegrityEnvelope(BaseModel):
    """Wrapper used by the frontend to verify report integrity client-side."""

    payload_json: str = Field(..., description="Canonical-JSON payload of the report")
    content_hash: str = Field(..., description="SHA-256 hex digest of payload_json")
    created_at: str
    envelope_version: str = "1.0"
    signed_by: str = "aura.model_assurance.report"


class ReportEnvelope(BaseModel):
    """One report wrapped with its integrity envelope, returned by GET /reports/{id}."""

    report: dict[str, Any]
    envelope: IntegrityEnvelope


class ApprovalQueueResponse(BaseModel):
    reports: list[dict[str, Any]]
    total: int


class ApprovalRequest(BaseModel):
    notes: str | None = ""


class RejectionRequest(BaseModel):
    reason: str | None = ""


class SpotCheckRequest(BaseModel):
    case_id: str
    human_pass: bool
    notes: str | None = ""


class ActionResponse(BaseModel):
    report_id: str
    status: str
    detail: str = ""


# ============================================================================
# Helpers
# ============================================================================


def _seal_envelope(report: dict[str, Any]) -> IntegrityEnvelope:
    """Build an IntegrityEnvelope mirroring report.integrity.seal_report."""
    payload_json = json.dumps(report, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    return IntegrityEnvelope(
        payload_json=payload_json,
        content_hash=content_hash,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/approval-queue", response_model=ApprovalQueueResponse)
def list_approval_queue() -> ApprovalQueueResponse:
    reports = _STORE.list_pending()
    return ApprovalQueueResponse(reports=reports, total=len(reports))


@router.get("/reports/{report_id}", response_model=ReportEnvelope)
def get_report(report_id: str) -> ReportEnvelope:
    report = _STORE.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"report {report_id!r} not found")
    return ReportEnvelope(report=report, envelope=_seal_envelope(report))


@router.post("/reports/{report_id}/approve", response_model=ActionResponse)
def approve_report(report_id: str, body: ApprovalRequest) -> ActionResponse:
    if not _STORE.remove(report_id):
        raise HTTPException(status_code=404, detail=f"report {report_id!r} not found")
    logger.info(
        "model-assurance report %s approved (notes=%s)",
        sanitize_log(report_id),
        sanitize_log(body.notes),
    )
    # Production wiring: this is where we'd write the new ConfigRevision
    # to the revisions DDB table and emit the AuditEvent for HITL_APPROVED.
    return ActionResponse(
        report_id=report_id,
        status="approved",
        detail="Approval recorded; deployment will follow on next pipeline tick.",
    )


@router.post("/reports/{report_id}/reject", response_model=ActionResponse)
def reject_report(report_id: str, body: RejectionRequest) -> ActionResponse:
    if not _STORE.remove(report_id):
        raise HTTPException(status_code=404, detail=f"report {report_id!r} not found")
    logger.info(
        "model-assurance report %s rejected (reason=%s)",
        sanitize_log(report_id),
        sanitize_log(body.reason),
    )
    # Production wiring: candidate enters sticky quarantine via the
    # ProvenanceService.quarantine_store; AuditEvent HITL_REJECTED emitted.
    return ActionResponse(
        report_id=report_id,
        status="rejected",
        detail="Candidate entered sticky quarantine.",
    )


@router.post("/reports/{report_id}/spot-check", response_model=ActionResponse)
def submit_spot_check(report_id: str, body: SpotCheckRequest) -> ActionResponse:
    notes = body.notes or ""
    ok = _STORE.append_spot_check(
        report_id, case_id=body.case_id, human_pass=body.human_pass, notes=notes
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"report {report_id!r} not found")
    return ActionResponse(
        report_id=report_id,
        status="recorded",
        detail=f"Spot-check for case {body.case_id!r} recorded.",
    )
