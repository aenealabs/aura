"""CloudTrail-style audit event contracts (ADR-088 Phase 3.4).

Per ADR-088 §Stage 8 + GovCloud compliance: every stage of the
assurance pipeline emits a structured audit event tagged with the
NIST 800-53 controls it satisfies. Production wiring forwards
events to AWS CloudTrail via the EventBridge / CloudTrail Lake
adapter; this module produces the immutable event payload.

Six NIST controls map to the assurance pipeline:

  CM-3 (Configuration Change Control)
       Every model swap is a tracked configuration change with
       full audit trail and human approval.
  CM-5 (Access Restrictions for Change)
       Only the HITL approval flow can trigger model configuration
       updates; no agent has direct write access.
  SA-10 (Developer Configuration Management)
       Model artifacts are SBOM-attested and provenance-tracked
       from registry to deployment.
  SI-7 (Software Integrity)
       Cryptographic signature verification on model artifacts;
       integrity hashes on evaluation reports.
  RA-5 (Vulnerability Assessment)
       Sandbox evaluation is a compliance gate — new models are
       assessed for security regression before deployment.
  AU-3 (Content of Audit Records)
       CloudTrail events for every stage: discovery, evaluation,
       approval/rejection, deployment, rollback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class NISTControl(Enum):
    """NIST 800-53 controls relevant to the assurance pipeline."""

    CM_3 = "CM-3"   # Configuration Change Control
    CM_5 = "CM-5"   # Access Restrictions for Change
    SA_10 = "SA-10"  # Developer Configuration Management
    SI_7 = "SI-7"   # Software Integrity
    RA_5 = "RA-5"   # Vulnerability Assessment
    AU_3 = "AU-3"   # Content of Audit Records


class AuditEventType(Enum):
    """The full set of assurance pipeline events.

    Order matches a typical pipeline traversal so callers building
    a chronological feed can iterate in declaration order.
    """

    CANDIDATE_DISCOVERED = "candidate_discovered"
    PROVENANCE_VERIFIED = "provenance_verified"
    PROVENANCE_FAILED = "provenance_failed"
    SANDBOX_PROVISIONED = "sandbox_provisioned"
    SANDBOX_TEARDOWN = "sandbox_teardown"
    ORACLE_EVALUATION_STARTED = "oracle_evaluation_started"
    ORACLE_EVALUATION_COMPLETED = "oracle_evaluation_completed"
    REPORT_GENERATED = "report_generated"
    HITL_APPROVED = "hitl_approved"
    HITL_REJECTED = "hitl_rejected"
    DEPLOYMENT_APPLIED = "deployment_applied"
    ROLLBACK_INITIATED = "rollback_initiated"
    ROLLBACK_APPLIED = "rollback_applied"


# Pre-built mapping of event type → applicable NIST controls.
# Production deployments use this to populate CloudTrail tag
# fields so log-search queries can filter by control ID.
EVENT_NIST_MAPPING: dict[AuditEventType, tuple[NISTControl, ...]] = {
    AuditEventType.CANDIDATE_DISCOVERED: (NISTControl.AU_3,),
    AuditEventType.PROVENANCE_VERIFIED: (
        NISTControl.SA_10,
        NISTControl.SI_7,
        NISTControl.AU_3,
    ),
    AuditEventType.PROVENANCE_FAILED: (
        NISTControl.SA_10,
        NISTControl.SI_7,
        NISTControl.AU_3,
    ),
    AuditEventType.SANDBOX_PROVISIONED: (NISTControl.RA_5, NISTControl.AU_3),
    AuditEventType.SANDBOX_TEARDOWN: (NISTControl.RA_5, NISTControl.AU_3),
    AuditEventType.ORACLE_EVALUATION_STARTED: (
        NISTControl.RA_5,
        NISTControl.AU_3,
    ),
    AuditEventType.ORACLE_EVALUATION_COMPLETED: (
        NISTControl.RA_5,
        NISTControl.SI_7,
        NISTControl.AU_3,
    ),
    AuditEventType.REPORT_GENERATED: (NISTControl.SI_7, NISTControl.AU_3),
    AuditEventType.HITL_APPROVED: (
        NISTControl.CM_3,
        NISTControl.CM_5,
        NISTControl.AU_3,
    ),
    AuditEventType.HITL_REJECTED: (
        NISTControl.CM_3,
        NISTControl.CM_5,
        NISTControl.AU_3,
    ),
    AuditEventType.DEPLOYMENT_APPLIED: (
        NISTControl.CM_3,
        NISTControl.CM_5,
        NISTControl.AU_3,
    ),
    AuditEventType.ROLLBACK_INITIATED: (
        NISTControl.CM_3,
        NISTControl.AU_3,
    ),
    AuditEventType.ROLLBACK_APPLIED: (
        NISTControl.CM_3,
        NISTControl.CM_5,
        NISTControl.AU_3,
    ),
}


@dataclass(frozen=True)
class AuditEvent:
    """One immutable audit-trail entry.

    The event_id is content-addressed (SHA-256 prefix of the
    event payload) so duplicate emissions are detectable. The
    payload mirrors CloudTrail's "userIdentity + requestParameters
    + responseElements" structure but normalized to
    JSON-serialisable Python primitives.
    """

    event_id: str
    event_type: AuditEventType
    candidate_id: str
    occurred_at: datetime
    actor: str = "system"             # IAM principal or "system" for agent flows
    correlation_id: str = ""          # ties together stages of one pipeline run
    request_parameters: tuple[tuple[str, str], ...] = ()
    response_elements: tuple[tuple[str, str], ...] = ()
    error_code: str | None = None
    error_message: str | None = None

    @property
    def applicable_controls(self) -> tuple[NISTControl, ...]:
        return EVENT_NIST_MAPPING.get(self.event_type, (NISTControl.AU_3,))

    @property
    def request_dict(self) -> dict[str, str]:
        return dict(self.request_parameters)

    @property
    def response_dict(self) -> dict[str, str]:
        return dict(self.response_elements)

    def to_cloudtrail_record(self) -> dict:
        """Render in the shape CloudTrail Lake / EventBridge expects."""
        return {
            "eventVersion": "1.10",
            "eventID": self.event_id,
            "eventTime": self.occurred_at.isoformat(),
            "eventName": self.event_type.value,
            "eventSource": "aura.model_assurance",
            "userIdentity": {"principalId": self.actor},
            "awsRegion": "",  # set by adapter
            "requestParameters": self.request_dict,
            "responseElements": self.response_dict,
            "errorCode": self.error_code,
            "errorMessage": self.error_message,
            "additionalEventData": {
                "candidate_id": self.candidate_id,
                "correlation_id": self.correlation_id,
                "applicable_controls": [
                    c.value for c in self.applicable_controls
                ],
            },
        }
