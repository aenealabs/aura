"""
Tests for context provenance contracts.

Tests all enums, dataclasses, and their methods.
"""

from datetime import datetime, timezone

from src.services.context_provenance import (
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


class TestIntegrityStatusEnum:
    """Test IntegrityStatus enum."""

    def test_verified_value(self):
        """Test VERIFIED value."""
        assert IntegrityStatus.VERIFIED.value == "verified"

    def test_failed_value(self):
        """Test FAILED value."""
        assert IntegrityStatus.FAILED.value == "failed"

    def test_hash_missing_value(self):
        """Test HASH_MISSING value."""
        assert IntegrityStatus.HASH_MISSING.value == "hash_missing"

    def test_hmac_invalid_value(self):
        """Test HMAC_INVALID value."""
        assert IntegrityStatus.HMAC_INVALID.value == "hmac_invalid"

    def test_all_values_unique(self):
        """Test all values are unique."""
        values = [s.value for s in IntegrityStatus]
        assert len(values) == len(set(values))


class TestProvenanceStatusEnum:
    """Test ProvenanceStatus enum."""

    def test_valid_value(self):
        """Test VALID value."""
        assert ProvenanceStatus.VALID.value == "valid"

    def test_stale_value(self):
        """Test STALE value."""
        assert ProvenanceStatus.STALE.value == "stale"

    def test_invalid_value(self):
        """Test INVALID value."""
        assert ProvenanceStatus.INVALID.value == "invalid"

    def test_missing_value(self):
        """Test MISSING value."""
        assert ProvenanceStatus.MISSING.value == "missing"


class TestTrustLevelEnum:
    """Test TrustLevel enum."""

    def test_high_value(self):
        """Test HIGH value."""
        assert TrustLevel.HIGH.value == "high"

    def test_medium_value(self):
        """Test MEDIUM value."""
        assert TrustLevel.MEDIUM.value == "medium"

    def test_low_value(self):
        """Test LOW value."""
        assert TrustLevel.LOW.value == "low"

    def test_untrusted_value(self):
        """Test UNTRUSTED value."""
        assert TrustLevel.UNTRUSTED.value == "untrusted"


class TestQuarantineReasonEnum:
    """Test QuarantineReason enum."""

    def test_integrity_failure_value(self):
        """Test INTEGRITY_FAILURE value."""
        assert QuarantineReason.INTEGRITY_FAILURE.value == "integrity_failure"

    def test_low_trust_value(self):
        """Test LOW_TRUST value."""
        assert QuarantineReason.LOW_TRUST.value == "low_trust"

    def test_anomaly_detected_value(self):
        """Test ANOMALY_DETECTED value."""
        assert QuarantineReason.ANOMALY_DETECTED.value == "anomaly_detected"

    def test_provenance_invalid_value(self):
        """Test PROVENANCE_INVALID value."""
        assert QuarantineReason.PROVENANCE_INVALID.value == "provenance_invalid"

    def test_manual_flag_value(self):
        """Test MANUAL_FLAG value."""
        assert QuarantineReason.MANUAL_FLAG.value == "manual_flag"


class TestAnomalyTypeEnum:
    """Test AnomalyType enum."""

    def test_injection_pattern_value(self):
        """Test INJECTION_PATTERN value."""
        assert AnomalyType.INJECTION_PATTERN.value == "injection_pattern"

    def test_structural_anomaly_value(self):
        """Test STRUCTURAL_ANOMALY value."""
        assert AnomalyType.STRUCTURAL_ANOMALY.value == "structural_anomaly"

    def test_statistical_outlier_value(self):
        """Test STATISTICAL_OUTLIER value."""
        assert AnomalyType.STATISTICAL_OUTLIER.value == "statistical_outlier"

    def test_hidden_instruction_value(self):
        """Test HIDDEN_INSTRUCTION value."""
        assert AnomalyType.HIDDEN_INSTRUCTION.value == "hidden_instruction"

    def test_obfuscated_code_value(self):
        """Test OBFUSCATED_CODE value."""
        assert AnomalyType.OBFUSCATED_CODE.value == "obfuscated_code"


class TestProvenanceAuditEventEnum:
    """Test ProvenanceAuditEvent enum."""

    def test_content_indexed_value(self):
        """Test CONTENT_INDEXED value."""
        assert ProvenanceAuditEvent.CONTENT_INDEXED.value == "content_indexed"

    def test_integrity_verified_value(self):
        """Test INTEGRITY_VERIFIED value."""
        assert ProvenanceAuditEvent.INTEGRITY_VERIFIED.value == "integrity_verified"

    def test_all_events_exist(self):
        """Test all expected events exist."""
        expected_events = [
            "content_indexed",
            "integrity_verified",
            "integrity_failed",
            "trust_computed",
            "low_trust_excluded",
            "anomaly_detected",
            "content_quarantined",
            "quarantine_reviewed",
            "content_served",
        ]
        actual_values = [e.value for e in ProvenanceAuditEvent]
        for event in expected_events:
            assert event in actual_values


class TestProvenanceRecord:
    """Test ProvenanceRecord dataclass."""

    def test_create_record(self, sample_provenance_record: ProvenanceRecord):
        """Test creating a provenance record."""
        assert sample_provenance_record.repository_id == "repo-001"
        assert sample_provenance_record.commit_sha == "abc123def456"
        assert sample_provenance_record.author_id == "author-001"
        assert sample_provenance_record.branch == "main"
        assert sample_provenance_record.signature == "gpg-signature-abc"

    def test_to_dict(self, sample_provenance_record: ProvenanceRecord):
        """Test converting to dictionary."""
        d = sample_provenance_record.to_dict()
        assert d["repository_id"] == "repo-001"
        assert d["commit_sha"] == "abc123def456"
        assert d["author_id"] == "author-001"
        assert d["author_email"] == "author@example.com"
        assert d["branch"] == "main"
        assert d["signature"] == "gpg-signature-abc"
        assert "timestamp" in d

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "repository_id": "repo-test",
            "commit_sha": "commit123",
            "author_id": "author-test",
            "author_email": "test@test.com",
            "timestamp": "2026-01-25T12:00:00+00:00",
            "branch": "develop",
            "signature": None,
        }
        record = ProvenanceRecord.from_dict(data)
        assert record.repository_id == "repo-test"
        assert record.commit_sha == "commit123"
        assert record.branch == "develop"
        assert record.signature is None

    def test_from_dict_missing_timestamp(self):
        """Test creating from dictionary without timestamp."""
        data = {
            "repository_id": "repo-test",
            "commit_sha": "commit123",
        }
        record = ProvenanceRecord.from_dict(data)
        assert record.timestamp is not None
        assert record.branch == "main"  # default

    def test_record_without_signature(
        self, sample_provenance_no_signature: ProvenanceRecord
    ):
        """Test record without GPG signature."""
        assert sample_provenance_no_signature.signature is None
        d = sample_provenance_no_signature.to_dict()
        assert d["signature"] is None


class TestIntegrityRecord:
    """Test IntegrityRecord dataclass."""

    def test_create_record(self, sample_integrity_record: IntegrityRecord):
        """Test creating an integrity record."""
        assert sample_integrity_record.content_hash_sha256 == "abc123def456789"
        assert sample_integrity_record.content_hmac == "hmac123456"
        assert sample_integrity_record.chunk_boundary_hash == "boundary123"
        assert sample_integrity_record.verified_at is not None

    def test_to_dict(self, sample_integrity_record: IntegrityRecord):
        """Test converting to dictionary."""
        d = sample_integrity_record.to_dict()
        assert d["content_hash"] == "abc123def456789"
        assert d["content_hmac"] == "hmac123456"
        assert "indexed_at" in d
        assert "verified_at" in d

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "content_hash": "hash123",
            "content_hmac": "hmac123",
            "chunk_boundary_hash": "boundary123",
            "embedding_fingerprint": "emb123",
            "indexed_at": "2026-01-25T12:00:00+00:00",
        }
        record = IntegrityRecord.from_dict(data)
        assert record.content_hash_sha256 == "hash123"
        assert record.content_hmac == "hmac123"
        assert record.verified_at is None

    def test_record_without_verified_at(self):
        """Test record without verified_at timestamp."""
        record = IntegrityRecord(
            content_hash_sha256="hash",
            content_hmac="hmac",
            chunk_boundary_hash="boundary",
            embedding_fingerprint="emb",
            indexed_at=datetime.now(timezone.utc),
        )
        assert record.verified_at is None
        d = record.to_dict()
        assert d["verified_at"] is None


class TestIntegrityResult:
    """Test IntegrityResult dataclass."""

    def test_verified_result(self, sample_integrity_result_verified: IntegrityResult):
        """Test verified integrity result."""
        assert sample_integrity_result_verified.status == IntegrityStatus.VERIFIED
        assert sample_integrity_result_verified.content_hash_match is True
        assert sample_integrity_result_verified.hmac_valid is True
        assert sample_integrity_result_verified.verified is True

    def test_failed_result(self, sample_integrity_result_failed: IntegrityResult):
        """Test failed integrity result."""
        assert sample_integrity_result_failed.status == IntegrityStatus.FAILED
        assert sample_integrity_result_failed.content_hash_match is False
        assert sample_integrity_result_failed.verified is False

    def test_verified_property(self):
        """Test verified property logic."""
        result = IntegrityResult(
            status=IntegrityStatus.HASH_MISSING,
            content_hash_match=False,
            hmac_valid=True,
            verified_at=datetime.now(timezone.utc),
        )
        assert result.verified is False


class TestProvenanceResult:
    """Test ProvenanceResult dataclass."""

    def test_valid_result(self, sample_provenance_result_valid: ProvenanceResult):
        """Test valid provenance result."""
        assert sample_provenance_result_valid.status == ProvenanceStatus.VALID
        assert sample_provenance_result_valid.repository_exists is True
        assert sample_provenance_result_valid.commit_exists is True
        assert sample_provenance_result_valid.valid is True

    def test_stale_result(self, sample_provenance_result_stale: ProvenanceResult):
        """Test stale provenance result."""
        assert sample_provenance_result_stale.status == ProvenanceStatus.STALE
        assert sample_provenance_result_stale.commit_exists is False
        assert sample_provenance_result_stale.valid is False

    def test_valid_property(self):
        """Test valid property logic."""
        result = ProvenanceResult(
            status=ProvenanceStatus.INVALID,
            repository_exists=True,
            commit_exists=True,
            author_valid=False,
            verified_at=datetime.now(timezone.utc),
        )
        assert result.valid is False


class TestTrustScore:
    """Test TrustScore dataclass."""

    def test_compute_high_trust(self, sample_trust_score_high: TrustScore):
        """Test computing high trust score."""
        assert sample_trust_score_high.level == TrustLevel.HIGH
        assert sample_trust_score_high.score >= 0.80

    def test_compute_medium_trust(self, sample_trust_score_medium: TrustScore):
        """Test computing medium trust score."""
        assert sample_trust_score_medium.level == TrustLevel.MEDIUM
        assert 0.50 <= sample_trust_score_medium.score < 0.80

    def test_compute_low_trust(self, sample_trust_score_low: TrustScore):
        """Test computing low trust score."""
        assert sample_trust_score_low.level == TrustLevel.LOW
        assert 0.30 <= sample_trust_score_low.score < 0.50

    def test_compute_untrusted(self, sample_trust_score_untrusted: TrustScore):
        """Test computing untrusted score."""
        assert sample_trust_score_untrusted.level == TrustLevel.UNTRUSTED
        assert sample_trust_score_untrusted.score < 0.30

    def test_compute_with_all_ones(self):
        """Test computing with all perfect scores."""
        score = TrustScore.compute(1.0, 1.0, 1.0, 1.0)
        assert score.score == 1.0
        assert score.level == TrustLevel.HIGH

    def test_compute_with_all_zeros(self):
        """Test computing with all zero scores."""
        score = TrustScore.compute(0.0, 0.0, 0.0, 0.0)
        assert score.score == 0.0
        assert score.level == TrustLevel.UNTRUSTED

    def test_components_stored(self):
        """Test that components are stored correctly."""
        score = TrustScore.compute(0.8, 0.7, 0.6, 0.9)
        assert score.components["repository"] == 0.8
        assert score.components["author"] == 0.7
        assert score.components["age"] == 0.6
        assert score.components["verification"] == 0.9

    def test_to_dict(self, sample_trust_score_high: TrustScore):
        """Test converting to dictionary."""
        d = sample_trust_score_high.to_dict()
        assert "score" in d
        assert "level" in d
        assert "components" in d
        assert "updated_at" in d
        assert d["level"] == "high"

    def test_boundary_high(self):
        """Test boundary at 0.80 for HIGH."""
        # Score that gives exactly 0.80
        score = TrustScore.compute(0.80, 0.80, 0.80, 0.80)
        assert score.level == TrustLevel.HIGH

    def test_boundary_medium(self):
        """Test boundary at 0.50 for MEDIUM."""
        score = TrustScore.compute(0.50, 0.50, 0.50, 0.50)
        assert score.level == TrustLevel.MEDIUM

    def test_boundary_low(self):
        """Test boundary at 0.30 for LOW."""
        score = TrustScore.compute(0.30, 0.30, 0.30, 0.30)
        assert score.level == TrustLevel.LOW


class TestSuspiciousSpan:
    """Test SuspiciousSpan dataclass."""

    def test_create_span(self):
        """Test creating a suspicious span."""
        span = SuspiciousSpan(start=10, end=50, reason="Injection detected")
        assert span.start == 10
        assert span.end == 50
        assert span.reason == "Injection detected"

    def test_to_tuple(self):
        """Test converting to tuple."""
        span = SuspiciousSpan(start=0, end=100, reason="Test reason")
        t = span.to_tuple()
        assert t == (0, 100, "Test reason")


class TestAnomalyReport:
    """Test AnomalyReport dataclass."""

    def test_clean_report(self, sample_anomaly_report_clean: AnomalyReport):
        """Test clean anomaly report."""
        assert sample_anomaly_report_clean.anomaly_score == 0.1
        assert len(sample_anomaly_report_clean.anomaly_types) == 0
        assert sample_anomaly_report_clean.has_anomalies is False

    def test_suspicious_report(self, sample_anomaly_report_suspicious: AnomalyReport):
        """Test suspicious anomaly report."""
        assert sample_anomaly_report_suspicious.anomaly_score == 0.75
        assert len(sample_anomaly_report_suspicious.anomaly_types) == 2
        assert sample_anomaly_report_suspicious.has_anomalies is True

    def test_has_anomalies_threshold(self):
        """Test has_anomalies threshold at 0.3."""
        report = AnomalyReport(anomaly_score=0.3, anomaly_types=[], suspicious_spans=[])
        assert report.has_anomalies is False

        report = AnomalyReport(
            anomaly_score=0.31, anomaly_types=[], suspicious_spans=[]
        )
        assert report.has_anomalies is True

    def test_to_dict(self, sample_anomaly_report_suspicious: AnomalyReport):
        """Test converting to dictionary."""
        d = sample_anomaly_report_suspicious.to_dict()
        assert d["anomaly_score"] == 0.75
        assert "injection_pattern" in d["anomaly_types"]
        assert len(d["suspicious_spans"]) == 2


class TestVerifiedContext:
    """Test VerifiedContext dataclass."""

    def test_safe_context(self, sample_verified_context_safe: VerifiedContext):
        """Test safe verified context."""
        assert sample_verified_context_safe.is_safe is True
        assert sample_verified_context_safe.integrity.verified is True
        assert sample_verified_context_safe.trust_score.level == TrustLevel.HIGH
        assert sample_verified_context_safe.anomaly_report.has_anomalies is False

    def test_unsafe_context(self, sample_verified_context_unsafe: VerifiedContext):
        """Test unsafe verified context."""
        assert sample_verified_context_unsafe.is_safe is False

    def test_is_safe_requires_all_checks(
        self,
        sample_provenance_record: ProvenanceRecord,
        sample_integrity_result_verified: IntegrityResult,
        sample_trust_score_high: TrustScore,
        sample_anomaly_report_suspicious: AnomalyReport,
    ):
        """Test is_safe requires all checks to pass."""
        # Good integrity and trust, but anomalies
        context = VerifiedContext(
            content="test",
            file_path="/test.py",
            chunk_id="chunk-1",
            provenance=sample_provenance_record,
            integrity=sample_integrity_result_verified,
            trust_score=sample_trust_score_high,
            anomaly_report=sample_anomaly_report_suspicious,
        )
        assert context.is_safe is False


class TestQuarantineRecord:
    """Test QuarantineRecord dataclass."""

    def test_create_record(self, sample_quarantine_record: QuarantineRecord):
        """Test creating a quarantine record."""
        assert sample_quarantine_record.chunk_id == "chunk-quarantine-001"
        assert sample_quarantine_record.reason == QuarantineReason.ANOMALY_DETECTED
        assert sample_quarantine_record.review_status == "pending"
        assert sample_quarantine_record.reviewed_by is None

    def test_to_dict(self, sample_quarantine_record: QuarantineRecord):
        """Test converting to dictionary."""
        d = sample_quarantine_record.to_dict()
        assert d["chunk_id"] == "chunk-quarantine-001"
        assert d["reason"] == "anomaly_detected"
        assert d["review_status"] == "pending"
        assert "provenance" in d
        assert isinstance(d["provenance"], dict)

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "chunk_id": "chunk-test",
            "content_hash": "hash123",
            "reason": "low_trust",
            "details": "Test details",
            "quarantined_at": "2026-01-25T12:00:00+00:00",
            "quarantined_by": "user-001",
            "provenance": {
                "repository_id": "repo-1",
                "commit_sha": "abc123",
                "author_id": "author-1",
                "author_email": "author@test.com",
                "timestamp": "2026-01-24T12:00:00+00:00",
                "branch": "main",
            },
            "review_status": "reviewed",
            "reviewed_by": "admin-001",
            "reviewed_at": "2026-01-25T13:00:00+00:00",
        }
        record = QuarantineRecord.from_dict(data)
        assert record.chunk_id == "chunk-test"
        assert record.reason == QuarantineReason.LOW_TRUST
        assert record.review_status == "reviewed"
        assert record.reviewed_by == "admin-001"
        assert record.provenance.repository_id == "repo-1"


class TestAuditRecord:
    """Test AuditRecord dataclass."""

    def test_create_record(self, sample_audit_record: AuditRecord):
        """Test creating an audit record."""
        assert sample_audit_record.audit_id == "audit-001"
        assert sample_audit_record.event_type == ProvenanceAuditEvent.INTEGRITY_VERIFIED
        assert sample_audit_record.chunk_id == "chunk-001"
        assert sample_audit_record.user_id == "user-001"

    def test_to_dict(self, sample_audit_record: AuditRecord):
        """Test converting to dictionary."""
        d = sample_audit_record.to_dict()
        assert d["audit_id"] == "audit-001"
        assert d["event_type"] == "integrity_verified"
        assert d["chunk_id"] == "chunk-001"
        assert d["user_id"] == "user-001"
        assert d["session_id"] == "session-001"
        assert "timestamp" in d
        assert "details" in d

    def test_record_without_optional_fields(self):
        """Test record without optional fields."""
        record = AuditRecord(
            audit_id="audit-002",
            event_type=ProvenanceAuditEvent.CONTENT_INDEXED,
            chunk_id="chunk-002",
            timestamp=datetime.now(timezone.utc),
            details={"test": "data"},
        )
        assert record.user_id is None
        assert record.session_id is None
        d = record.to_dict()
        assert d["user_id"] is None
        assert d["session_id"] is None
