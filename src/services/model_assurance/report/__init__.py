"""ADR-088 Phase 2.5 — Shadow Deployment Report + integrity envelope."""

from __future__ import annotations

from .contracts import (
    CostAnalysis,
    EdgeCaseSpotlight,
    EvaluationIntegrityEnvelope,
    HumanSpotCheckResult,
    IntegrityEnvelope,
    ReportSection,
    ShadowDeploymentReport,
)
from .integrity import (
    IntegrityVerification,
    seal_integrity_envelope,
    seal_report,
    verify_envelope,
    verify_integrity_envelope,
)
from .report_generator import (
    EDGE_CASE_LIMIT,
    generate_report,
    lookup_adapter,
)

__all__ = [
    "CostAnalysis",
    "EdgeCaseSpotlight",
    "EvaluationIntegrityEnvelope",
    "HumanSpotCheckResult",
    "IntegrityEnvelope",
    "IntegrityVerification",
    "ReportSection",
    "ShadowDeploymentReport",
    "EDGE_CASE_LIMIT",
    "generate_report",
    "lookup_adapter",
    "seal_integrity_envelope",
    "seal_report",
    "verify_envelope",
    "verify_integrity_envelope",
]
