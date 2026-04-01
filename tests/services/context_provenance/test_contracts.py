"""Tests for context_provenance contracts."""

from datetime import datetime, timezone

from src.services.context_provenance.contracts import (
    AnomalyReport,
    AnomalyType,
    AuditRecord,
    IntegrityRecord,
    IntegrityResult,
    IntegrityStatus,
    ProvenanceAuditEvent,
    ProvenanceRecord,
    ProvenanceStatus,
    QuarantineReason,
    QuarantineRecord,
    SuspiciousSpan,
    TrustLevel,
    TrustScore,
    VerifiedContext,
)


class TestProvenanceRecord:
    """Tests for ProvenanceRecord dataclass."""

    def test_create_provenance_record(self):
        """Test creating a provenance record."""
        now = datetime.now(timezone.utc)
        record = ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123def456",
            author_id="author123",
            author_email="author@example.com",
            timestamp=now,
            branch="main",
            signature="gpg-sig-123",
        )

        assert record.repository_id == "org/repo"
        assert record.commit_sha == "abc123def456"
        assert record.author_id == "author123"
        assert record.author_email == "author@example.com"
        assert record.timestamp == now
        assert record.branch == "main"
        assert record.signature == "gpg-sig-123"

    def test_provenance_record_to_dict(self):
        """Test converting provenance record to dictionary."""
        now = datetime.now(timezone.utc)
        record = ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123",
            author_id="author",
            author_email="author@test.com",
            timestamp=now,
            branch="main",
        )

        data = record.to_dict()

        assert data["repository_id"] == "org/repo"
        assert data["commit_sha"] == "abc123"
        assert data["timestamp"] == now.isoformat()
        assert data["signature"] is None

    def test_provenance_record_from_dict(self):
        """Test creating provenance record from dictionary."""
        now = datetime.now(timezone.utc)
        data = {
            "repository_id": "org/repo",
            "commit_sha": "abc123",
            "author_id": "author",
            "author_email": "author@test.com",
            "timestamp": now.isoformat(),
            "branch": "develop",
        }

        record = ProvenanceRecord.from_dict(data)

        assert record.repository_id == "org/repo"
        assert record.branch == "develop"


class TestIntegrityRecord:
    """Tests for IntegrityRecord dataclass."""

    def test_create_integrity_record(self):
        """Test creating an integrity record."""
        now = datetime.now(timezone.utc)
        record = IntegrityRecord(
            content_hash_sha256="hash123",
            content_hmac="hmac456",
            chunk_boundary_hash="boundary789",
            embedding_fingerprint="fingerprint000",
            indexed_at=now,
        )

        assert record.content_hash_sha256 == "hash123"
        assert record.content_hmac == "hmac456"
        assert record.verified_at is None

    def test_integrity_record_to_dict(self):
        """Test converting integrity record to dictionary."""
        now = datetime.now(timezone.utc)
        record = IntegrityRecord(
            content_hash_sha256="hash",
            content_hmac="hmac",
            chunk_boundary_hash="boundary",
            embedding_fingerprint="fp",
            indexed_at=now,
        )

        data = record.to_dict()

        assert data["content_hash"] == "hash"
        assert data["verified_at"] is None


class TestIntegrityResult:
    """Tests for IntegrityResult dataclass."""

    def test_verified_property(self):
        """Test the verified property."""
        now = datetime.now(timezone.utc)

        verified = IntegrityResult(
            status=IntegrityStatus.VERIFIED,
            content_hash_match=True,
            hmac_valid=True,
            verified_at=now,
        )
        assert verified.verified is True

        failed = IntegrityResult(
            status=IntegrityStatus.FAILED,
            content_hash_match=False,
            hmac_valid=True,
            verified_at=now,
        )
        assert failed.verified is False


class TestTrustScore:
    """Tests for TrustScore dataclass."""

    def test_compute_high_trust(self):
        """Test computing a high trust score."""
        score = TrustScore.compute(
            repository_score=1.0,
            author_score=1.0,
            age_score=1.0,
            verification_score=1.0,
        )

        assert score.score == 1.0
        assert score.level == TrustLevel.HIGH

    def test_compute_medium_trust(self):
        """Test computing a medium trust score."""
        score = TrustScore.compute(
            repository_score=0.7,
            author_score=0.5,
            age_score=0.5,
            verification_score=0.5,
        )

        # 0.7*0.35 + 0.5*0.25 + 0.5*0.15 + 0.5*0.25 = 0.245 + 0.125 + 0.075 + 0.125 = 0.57
        assert 0.50 <= score.score < 0.80
        assert score.level == TrustLevel.MEDIUM

    def test_compute_low_trust(self):
        """Test computing a low trust score."""
        score = TrustScore.compute(
            repository_score=0.3,
            author_score=0.3,
            age_score=0.5,
            verification_score=0.3,
        )

        # 0.3*0.35 + 0.3*0.25 + 0.5*0.15 + 0.3*0.25 = 0.105 + 0.075 + 0.075 + 0.075 = 0.33
        assert 0.30 <= score.score < 0.50
        assert score.level == TrustLevel.LOW

    def test_compute_untrusted(self):
        """Test computing an untrusted score."""
        score = TrustScore.compute(
            repository_score=0.0,
            author_score=0.3,
            age_score=0.5,
            verification_score=0.0,
        )

        # 0.0*0.35 + 0.3*0.25 + 0.5*0.15 + 0.0*0.25 = 0 + 0.075 + 0.075 + 0 = 0.15
        assert score.score < 0.30
        assert score.level == TrustLevel.UNTRUSTED

    def test_trust_score_to_dict(self):
        """Test converting trust score to dictionary."""
        score = TrustScore.compute(
            repository_score=0.8,
            author_score=0.7,
            age_score=0.9,
            verification_score=0.8,
        )

        data = score.to_dict()

        assert "score" in data
        assert "level" in data
        assert "components" in data
        assert data["components"]["repository"] == 0.8


class TestAnomalyReport:
    """Tests for AnomalyReport dataclass."""

    def test_has_anomalies_true(self):
        """Test has_anomalies returns True for high score."""
        report = AnomalyReport(
            anomaly_score=0.5,
            anomaly_types=[AnomalyType.HIDDEN_INSTRUCTION],
        )

        assert report.has_anomalies is True

    def test_has_anomalies_false(self):
        """Test has_anomalies returns False for low score."""
        report = AnomalyReport(
            anomaly_score=0.2,
            anomaly_types=[],
        )

        assert report.has_anomalies is False

    def test_anomaly_report_to_dict(self):
        """Test converting anomaly report to dictionary."""
        report = AnomalyReport(
            anomaly_score=0.8,
            anomaly_types=[AnomalyType.INJECTION_PATTERN],
            suspicious_spans=[SuspiciousSpan(0, 10, "test")],
        )

        data = report.to_dict()

        assert data["anomaly_score"] == 0.8
        assert "injection_pattern" in data["anomaly_types"]


class TestVerifiedContext:
    """Tests for VerifiedContext dataclass."""

    def test_is_safe_true(self):
        """Test is_safe returns True for safe context."""
        now = datetime.now(timezone.utc)
        context = VerifiedContext(
            content="safe code",
            file_path="src/main.py",
            chunk_id="chunk123",
            provenance=ProvenanceRecord(
                repository_id="org/repo",
                commit_sha="abc",
                author_id="author",
                author_email="a@test.com",
                timestamp=now,
                branch="main",
            ),
            integrity=IntegrityResult(
                status=IntegrityStatus.VERIFIED,
                content_hash_match=True,
                hmac_valid=True,
                verified_at=now,
            ),
            trust_score=TrustScore.compute(1.0, 1.0, 1.0, 1.0),
            anomaly_report=AnomalyReport(anomaly_score=0.0),
        )

        assert context.is_safe is True

    def test_is_safe_false_integrity_failed(self):
        """Test is_safe returns False when integrity fails."""
        now = datetime.now(timezone.utc)
        context = VerifiedContext(
            content="code",
            file_path="src/main.py",
            chunk_id="chunk123",
            provenance=ProvenanceRecord(
                repository_id="org/repo",
                commit_sha="abc",
                author_id="author",
                author_email="a@test.com",
                timestamp=now,
                branch="main",
            ),
            integrity=IntegrityResult(
                status=IntegrityStatus.FAILED,
                content_hash_match=False,
                hmac_valid=True,
                verified_at=now,
            ),
            trust_score=TrustScore.compute(1.0, 1.0, 1.0, 1.0),
            anomaly_report=AnomalyReport(anomaly_score=0.0),
        )

        assert context.is_safe is False


class TestQuarantineRecord:
    """Tests for QuarantineRecord dataclass."""

    def test_create_quarantine_record(self):
        """Test creating a quarantine record."""
        now = datetime.now(timezone.utc)
        provenance = ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc",
            author_id="author",
            author_email="a@test.com",
            timestamp=now,
            branch="main",
        )

        record = QuarantineRecord(
            chunk_id="chunk123",
            content_hash="hash123",
            reason=QuarantineReason.INTEGRITY_FAILURE,
            details="Hash mismatch",
            quarantined_at=now,
            quarantined_by="system",
            provenance=provenance,
        )

        assert record.chunk_id == "chunk123"
        assert record.reason == QuarantineReason.INTEGRITY_FAILURE
        assert record.review_status == "pending"

    def test_quarantine_record_to_dict(self):
        """Test converting quarantine record to dictionary."""
        now = datetime.now(timezone.utc)
        provenance = ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc",
            author_id="author",
            author_email="a@test.com",
            timestamp=now,
            branch="main",
        )

        record = QuarantineRecord(
            chunk_id="chunk123",
            content_hash="hash123",
            reason=QuarantineReason.ANOMALY_DETECTED,
            details="Suspicious pattern",
            quarantined_at=now,
            quarantined_by="system",
            provenance=provenance,
        )

        data = record.to_dict()

        assert data["chunk_id"] == "chunk123"
        assert data["reason"] == "anomaly_detected"


class TestAuditRecord:
    """Tests for AuditRecord dataclass."""

    def test_create_audit_record(self):
        """Test creating an audit record."""
        now = datetime.now(timezone.utc)
        record = AuditRecord(
            audit_id="audit123",
            event_type=ProvenanceAuditEvent.INTEGRITY_VERIFIED,
            chunk_id="chunk456",
            timestamp=now,
            details={"status": "passed"},
            user_id="user789",
        )

        assert record.audit_id == "audit123"
        assert record.event_type == ProvenanceAuditEvent.INTEGRITY_VERIFIED

    def test_audit_record_to_dict(self):
        """Test converting audit record to dictionary."""
        now = datetime.now(timezone.utc)
        record = AuditRecord(
            audit_id="audit123",
            event_type=ProvenanceAuditEvent.CONTENT_QUARANTINED,
            chunk_id="chunk456",
            timestamp=now,
            details={"reason": "test"},
        )

        data = record.to_dict()

        assert data["audit_id"] == "audit123"
        assert data["event_type"] == "content_quarantined"


class TestEnums:
    """Tests for enum values."""

    def test_integrity_status_values(self):
        """Test IntegrityStatus enum values."""
        assert IntegrityStatus.VERIFIED.value == "verified"
        assert IntegrityStatus.FAILED.value == "failed"
        assert IntegrityStatus.HASH_MISSING.value == "hash_missing"
        assert IntegrityStatus.HMAC_INVALID.value == "hmac_invalid"

    def test_provenance_status_values(self):
        """Test ProvenanceStatus enum values."""
        assert ProvenanceStatus.VALID.value == "valid"
        assert ProvenanceStatus.STALE.value == "stale"
        assert ProvenanceStatus.INVALID.value == "invalid"
        assert ProvenanceStatus.MISSING.value == "missing"

    def test_trust_level_values(self):
        """Test TrustLevel enum values."""
        assert TrustLevel.HIGH.value == "high"
        assert TrustLevel.MEDIUM.value == "medium"
        assert TrustLevel.LOW.value == "low"
        assert TrustLevel.UNTRUSTED.value == "untrusted"

    def test_quarantine_reason_values(self):
        """Test QuarantineReason enum values."""
        assert QuarantineReason.INTEGRITY_FAILURE.value == "integrity_failure"
        assert QuarantineReason.LOW_TRUST.value == "low_trust"
        assert QuarantineReason.ANOMALY_DETECTED.value == "anomaly_detected"

    def test_anomaly_type_values(self):
        """Test AnomalyType enum values."""
        assert AnomalyType.INJECTION_PATTERN.value == "injection_pattern"
        assert AnomalyType.HIDDEN_INSTRUCTION.value == "hidden_instruction"
        assert AnomalyType.OBFUSCATED_CODE.value == "obfuscated_code"
