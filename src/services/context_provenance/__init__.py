"""
Project Aura - Context Provenance and Integrity

This package implements the Context Provenance and Integrity system
for GraphRAG (ADR-067). It provides comprehensive protection against
context poisoning attacks by tracking content provenance, verifying
integrity, computing trust scores, detecting anomalies, and managing
quarantined content.

Core Components:
- ContentProvenanceService: Index-time provenance collection
- IntegrityVerificationService: Retrieval-time integrity verification
- TrustScoringEngine: Weighted trust score computation
- ContextAnomalyDetector: Anomaly detection for retrieved context
- QuarantineManager: Suspicious content isolation and HITL review
- ProvenanceAuditLogger: Compliance audit logging

Security Rationale:
- All indexed content must have verified provenance
- Integrity verification prevents context poisoning
- Trust scoring enables risk-based decisions
- Anomaly detection catches novel attack patterns
- Quarantine prevents suspicious content from reaching LLM

Author: Project Aura Team
Created: 2026-01-25
"""

from .anomaly_detector import (
    ContextAnomalyDetector,
    configure_anomaly_detector,
    get_anomaly_detector,
    reset_anomaly_detector,
)
from .audit_logger import (
    ProvenanceAuditLogger,
    configure_audit_logger,
    get_audit_logger,
    reset_audit_logger,
)
from .config import (
    AnomalyDetectionConfig,
    ProvenanceConfig,
    TrustScoringConfig,
    get_anomaly_detection_config,
    get_default_config,
    get_trust_scoring_config,
)
from .contracts import (
    AnomalyReport,
    AnomalyType,
    AuditRecord,
    IntegrityRecord,
    IntegrityResult,
    IntegrityStatus,
    ProvenanceAuditEvent,
    ProvenanceRecord,
    ProvenanceResult,
    ProvenanceStatus,
    QuarantineReason,
    QuarantineRecord,
    SuspiciousSpan,
    TrustLevel,
    TrustScore,
    VerifiedContext,
)
from .integrity_service import (
    IntegrityVerificationService,
    configure_integrity_service,
    get_integrity_service,
    reset_integrity_service,
)
from .provenance_service import (
    ContentProvenanceService,
    configure_provenance_service,
    get_provenance_service,
    reset_provenance_service,
)
from .quarantine_manager import (
    QuarantineManager,
    configure_quarantine_manager,
    get_quarantine_manager,
    reset_quarantine_manager,
)
from .trust_scoring import (
    TrustScoringEngine,
    configure_trust_scoring_engine,
    get_trust_scoring_engine,
    reset_trust_scoring_engine,
)

__all__ = [
    # Contracts - Enums
    "IntegrityStatus",
    "ProvenanceStatus",
    "TrustLevel",
    "QuarantineReason",
    "AnomalyType",
    "ProvenanceAuditEvent",
    # Contracts - Data Classes
    "ProvenanceRecord",
    "IntegrityRecord",
    "IntegrityResult",
    "ProvenanceResult",
    "TrustScore",
    "AnomalyReport",
    "SuspiciousSpan",
    "VerifiedContext",
    "QuarantineRecord",
    "AuditRecord",
    # Configuration
    "ProvenanceConfig",
    "TrustScoringConfig",
    "AnomalyDetectionConfig",
    "get_default_config",
    "get_trust_scoring_config",
    "get_anomaly_detection_config",
    # Provenance Service
    "ContentProvenanceService",
    "get_provenance_service",
    "configure_provenance_service",
    "reset_provenance_service",
    # Integrity Service
    "IntegrityVerificationService",
    "get_integrity_service",
    "configure_integrity_service",
    "reset_integrity_service",
    # Trust Scoring
    "TrustScoringEngine",
    "get_trust_scoring_engine",
    "configure_trust_scoring_engine",
    "reset_trust_scoring_engine",
    # Anomaly Detection
    "ContextAnomalyDetector",
    "get_anomaly_detector",
    "configure_anomaly_detector",
    "reset_anomaly_detector",
    # Quarantine Manager
    "QuarantineManager",
    "get_quarantine_manager",
    "configure_quarantine_manager",
    "reset_quarantine_manager",
    # Audit Logger
    "ProvenanceAuditLogger",
    "get_audit_logger",
    "configure_audit_logger",
    "reset_audit_logger",
]
