"""
Project Aura - Context Provenance and Integrity Contracts

Defines data contracts for the context provenance and integrity system.
This module contains enums, dataclasses, and protocols for tracking
content provenance, verifying integrity, computing trust scores,
detecting anomalies, and managing quarantined content.

Security Rationale:
- All indexed content must have verified provenance
- Integrity verification prevents context poisoning
- Trust scoring enables risk-based decisions
- Anomaly detection catches novel attack patterns

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# =============================================================================
# Enums
# =============================================================================


class IntegrityStatus(Enum):
    """Result of integrity verification."""

    VERIFIED = "verified"
    FAILED = "failed"
    HASH_MISSING = "hash_missing"
    HMAC_INVALID = "hmac_invalid"


class ProvenanceStatus(Enum):
    """Result of provenance validation."""

    VALID = "valid"
    STALE = "stale"  # Source unavailable for verification
    INVALID = "invalid"  # Provenance data doesn't match source
    MISSING = "missing"  # No provenance data recorded


class TrustLevel(Enum):
    """Trust classification for content."""

    HIGH = "high"  # >= 0.80
    MEDIUM = "medium"  # >= 0.50
    LOW = "low"  # >= 0.30
    UNTRUSTED = "untrusted"  # < 0.30


class QuarantineReason(Enum):
    """Reason for quarantining content."""

    INTEGRITY_FAILURE = "integrity_failure"
    LOW_TRUST = "low_trust"
    ANOMALY_DETECTED = "anomaly_detected"
    PROVENANCE_INVALID = "provenance_invalid"
    MANUAL_FLAG = "manual_flag"


class AnomalyType(Enum):
    """Types of detected anomalies."""

    INJECTION_PATTERN = "injection_pattern"
    STRUCTURAL_ANOMALY = "structural_anomaly"
    STATISTICAL_OUTLIER = "statistical_outlier"
    HIDDEN_INSTRUCTION = "hidden_instruction"
    OBFUSCATED_CODE = "obfuscated_code"


class ProvenanceAuditEvent(Enum):
    """Types of provenance audit events."""

    CONTENT_INDEXED = "content_indexed"
    INTEGRITY_VERIFIED = "integrity_verified"
    INTEGRITY_FAILED = "integrity_failed"
    TRUST_COMPUTED = "trust_computed"
    LOW_TRUST_EXCLUDED = "low_trust_excluded"
    ANOMALY_DETECTED = "anomaly_detected"
    CONTENT_QUARANTINED = "content_quarantined"
    QUARANTINE_REVIEWED = "quarantine_reviewed"
    CONTENT_SERVED = "content_served"


# =============================================================================
# Provenance Records
# =============================================================================


@dataclass
class ProvenanceRecord:
    """Complete provenance record for indexed content."""

    repository_id: str
    commit_sha: str
    author_id: str
    author_email: str
    timestamp: datetime
    branch: str
    signature: Optional[str] = None  # GPG signature if available

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "repository_id": self.repository_id,
            "commit_sha": self.commit_sha,
            "author_id": self.author_id,
            "author_email": self.author_email,
            "timestamp": self.timestamp.isoformat(),
            "branch": self.branch,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProvenanceRecord:
        """Create from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)

        return cls(
            repository_id=data.get("repository_id", "unknown"),
            commit_sha=data.get("commit_sha", ""),
            author_id=data.get("author_id", ""),
            author_email=data.get("author_email", ""),
            timestamp=timestamp,
            branch=data.get("branch", "main"),
            signature=data.get("signature"),
        )


@dataclass
class IntegrityRecord:
    """Integrity verification data for indexed content."""

    content_hash_sha256: str
    content_hmac: str
    chunk_boundary_hash: str
    embedding_fingerprint: str
    indexed_at: datetime
    verified_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "content_hash": self.content_hash_sha256,
            "content_hmac": self.content_hmac,
            "chunk_boundary_hash": self.chunk_boundary_hash,
            "embedding_fingerprint": self.embedding_fingerprint,
            "indexed_at": self.indexed_at.isoformat(),
            "verified_at": (self.verified_at.isoformat() if self.verified_at else None),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntegrityRecord:
        """Create from dictionary."""
        indexed_at = data.get("indexed_at")
        if isinstance(indexed_at, str):
            indexed_at = datetime.fromisoformat(indexed_at)
        elif indexed_at is None:
            indexed_at = datetime.now(timezone.utc)

        verified_at = data.get("verified_at")
        if isinstance(verified_at, str):
            verified_at = datetime.fromisoformat(verified_at)

        return cls(
            content_hash_sha256=data.get("content_hash", ""),
            content_hmac=data.get("content_hmac", ""),
            chunk_boundary_hash=data.get("chunk_boundary_hash", ""),
            embedding_fingerprint=data.get("embedding_fingerprint", ""),
            indexed_at=indexed_at,
            verified_at=verified_at,
        )


# =============================================================================
# Verification Results
# =============================================================================


@dataclass
class IntegrityResult:
    """Result of integrity verification."""

    status: IntegrityStatus
    content_hash_match: bool
    hmac_valid: bool
    verified_at: datetime
    details: Optional[str] = None

    @property
    def verified(self) -> bool:
        """Check if integrity verification passed."""
        return self.status == IntegrityStatus.VERIFIED


@dataclass
class ProvenanceResult:
    """Result of provenance validation."""

    status: ProvenanceStatus
    repository_exists: bool
    commit_exists: bool
    author_valid: bool
    verified_at: datetime
    details: Optional[str] = None

    @property
    def valid(self) -> bool:
        """Check if provenance validation passed."""
        return self.status == ProvenanceStatus.VALID


# =============================================================================
# Trust Scoring
# =============================================================================


@dataclass
class TrustScore:
    """Trust score with component breakdown."""

    score: float  # 0.0 - 1.0
    level: TrustLevel
    components: dict[str, float]  # repository, author, age, verification
    updated_at: datetime

    @classmethod
    def compute(
        cls,
        repository_score: float,
        author_score: float,
        age_score: float,
        verification_score: float,
    ) -> TrustScore:
        """Compute trust score from components."""
        weights = {
            "repository": 0.35,
            "author": 0.25,
            "age": 0.15,
            "verification": 0.25,
        }

        score = (
            repository_score * weights["repository"]
            + author_score * weights["author"]
            + age_score * weights["age"]
            + verification_score * weights["verification"]
        )

        # Determine trust level (round to 4 decimal places for floating point precision)
        rounded_score = round(score, 4)
        if rounded_score >= 0.80:
            level = TrustLevel.HIGH
        elif rounded_score >= 0.50:
            level = TrustLevel.MEDIUM
        elif rounded_score >= 0.30:
            level = TrustLevel.LOW
        else:
            level = TrustLevel.UNTRUSTED

        return cls(
            score=score,
            level=level,
            components={
                "repository": repository_score,
                "author": author_score,
                "age": age_score,
                "verification": verification_score,
            },
            updated_at=datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "score": self.score,
            "level": self.level.value,
            "components": self.components,
            "updated_at": self.updated_at.isoformat(),
        }


# =============================================================================
# Anomaly Detection
# =============================================================================


@dataclass
class SuspiciousSpan:
    """A suspicious span within content."""

    start: int
    end: int
    reason: str

    def to_tuple(self) -> tuple[int, int, str]:
        """Convert to tuple format."""
        return (self.start, self.end, self.reason)


@dataclass
class AnomalyReport:
    """Result of anomaly detection scan."""

    anomaly_score: float  # 0.0 - 1.0
    anomaly_types: list[AnomalyType] = field(default_factory=list)
    suspicious_spans: list[SuspiciousSpan] = field(default_factory=list)
    details: Optional[str] = None

    @property
    def has_anomalies(self) -> bool:
        """Check if any anomalies detected above threshold."""
        return self.anomaly_score > 0.3

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "anomaly_score": self.anomaly_score,
            "anomaly_types": [t.value for t in self.anomaly_types],
            "suspicious_spans": [s.to_tuple() for s in self.suspicious_spans],
            "details": self.details,
        }


# =============================================================================
# Verified Context
# =============================================================================


@dataclass
class VerifiedContext:
    """Context chunk with verification metadata."""

    content: str
    file_path: str
    chunk_id: str
    provenance: ProvenanceRecord
    integrity: IntegrityResult
    trust_score: TrustScore
    anomaly_report: AnomalyReport

    @property
    def is_safe(self) -> bool:
        """Check if context passed all verification checks."""
        return (
            self.integrity.verified
            and self.trust_score.level != TrustLevel.UNTRUSTED
            and not self.anomaly_report.has_anomalies
        )


# =============================================================================
# Quarantine Records
# =============================================================================


@dataclass
class QuarantineRecord:
    """Record for quarantined content."""

    chunk_id: str
    content_hash: str
    reason: QuarantineReason
    details: str
    quarantined_at: datetime
    quarantined_by: str  # "system" or user_id
    provenance: ProvenanceRecord
    review_status: str = "pending"  # pending | reviewed | released | deleted
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "chunk_id": self.chunk_id,
            "content_hash": self.content_hash,
            "reason": self.reason.value,
            "details": self.details,
            "quarantined_at": self.quarantined_at.isoformat(),
            "quarantined_by": self.quarantined_by,
            "provenance": self.provenance.to_dict(),
            "review_status": self.review_status,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": (self.reviewed_at.isoformat() if self.reviewed_at else None),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuarantineRecord:
        """Create from dictionary."""
        quarantined_at = data.get("quarantined_at")
        if isinstance(quarantined_at, str):
            quarantined_at = datetime.fromisoformat(quarantined_at)
        elif quarantined_at is None:
            quarantined_at = datetime.now(timezone.utc)

        reviewed_at = data.get("reviewed_at")
        if isinstance(reviewed_at, str):
            reviewed_at = datetime.fromisoformat(reviewed_at)

        provenance_data = data.get("provenance", {})
        if isinstance(provenance_data, str):
            import ast

            provenance_data = ast.literal_eval(provenance_data)

        return cls(
            chunk_id=data.get("chunk_id", ""),
            content_hash=data.get("content_hash", ""),
            reason=QuarantineReason(data.get("reason", "manual_flag")),
            details=data.get("details", ""),
            quarantined_at=quarantined_at,
            quarantined_by=data.get("quarantined_by", "system"),
            provenance=ProvenanceRecord.from_dict(provenance_data),
            review_status=data.get("review_status", "pending"),
            reviewed_by=data.get("reviewed_by"),
            reviewed_at=reviewed_at,
        )


# =============================================================================
# Audit Records
# =============================================================================


@dataclass
class AuditRecord:
    """Record for provenance audit events."""

    audit_id: str
    event_type: ProvenanceAuditEvent
    chunk_id: str
    timestamp: datetime
    details: dict[str, Any]
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "audit_id": self.audit_id,
            "event_type": self.event_type.value,
            "chunk_id": self.chunk_id,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "user_id": self.user_id,
            "session_id": self.session_id,
        }
