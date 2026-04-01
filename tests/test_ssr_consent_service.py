"""
Tests for SSR Consent Service.

Tests GDPR/CCPA compliant consent management, data subject rights,
and privacy controls for SSR training.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.ssr.consent_service import (
    ConsentAuditEntry,
    ConsentRecord,
    ConsentService,
    ConsentStatus,
    ConsentType,
    CustomerConsentProfile,
    DataSubjectRequest,
    DataSubjectRight,
    LegalBasis,
)

# Note: pytest.mark.forked disabled for accurate coverage measurement
# The module has well-isolated tests that don't require process isolation
# pytestmark = pytest.mark.forked


class TestConsentTypeEnum:
    """Tests for ConsentType enum."""

    def test_all_consent_types_defined(self):
        """Verify all expected consent types exist."""
        expected = {
            "training_data",
            "synthetic_bugs",
            "model_updates",
            "telemetry",
            "feedback",
            "anonymized_benchmarks",
        }
        actual = {c.value for c in ConsentType}
        assert expected == actual


class TestConsentStatusEnum:
    """Tests for ConsentStatus enum."""

    def test_all_statuses_defined(self):
        """Verify all expected consent statuses exist."""
        expected = {"granted", "denied", "withdrawn", "pending", "expired"}
        actual = {s.value for s in ConsentStatus}
        assert expected == actual


class TestLegalBasisEnum:
    """Tests for LegalBasis enum."""

    def test_all_legal_bases_defined(self):
        """Verify all GDPR legal bases exist."""
        expected = {"consent", "legitimate_interest", "contract", "legal_obligation"}
        actual = {b.value for b in LegalBasis}
        assert expected == actual


class TestDataSubjectRightEnum:
    """Tests for DataSubjectRight enum."""

    def test_all_rights_defined(self):
        """Verify all GDPR/CCPA rights exist."""
        expected = {
            "access",
            "rectification",
            "erasure",
            "portability",
            "restriction",
            "objection",
            "opt_out_sale",
        }
        actual = {r.value for r in DataSubjectRight}
        assert expected == actual


class TestConsentRecord:
    """Tests for ConsentRecord dataclass."""

    def test_consent_record_creation(self):
        """Test creating a consent record."""
        now = datetime.now(timezone.utc)
        record = ConsentRecord(
            consent_id="consent-123",
            customer_id="customer-456",
            consent_type=ConsentType.TRAINING_DATA,
            status=ConsentStatus.GRANTED,
            legal_basis=LegalBasis.CONSENT,
            granted_at=now,
            expires_at=now + timedelta(days=730),
            withdrawn_at=None,
            ip_address_hash="abc123",
            user_agent_hash="def456",
            consent_version="1.0",
            scope={"repositories": ["repo-1", "repo-2"]},
            metadata={},
        )
        assert record.consent_id == "consent-123"
        assert record.consent_type == ConsentType.TRAINING_DATA
        assert record.status == ConsentStatus.GRANTED

    def test_consent_is_valid_granted(self):
        """Test that granted consent is valid."""
        now = datetime.now(timezone.utc)
        record = ConsentRecord(
            consent_id="c1",
            customer_id="cust1",
            consent_type=ConsentType.SYNTHETIC_BUGS,
            status=ConsentStatus.GRANTED,
            legal_basis=LegalBasis.CONSENT,
            granted_at=now,
            expires_at=now + timedelta(days=365),
            withdrawn_at=None,
            ip_address_hash="",
            user_agent_hash="",
            consent_version="1.0",
        )
        assert record.is_valid() is True

    def test_consent_is_valid_expired(self):
        """Test that expired consent is invalid."""
        now = datetime.now(timezone.utc)
        record = ConsentRecord(
            consent_id="c1",
            customer_id="cust1",
            consent_type=ConsentType.TELEMETRY,
            status=ConsentStatus.GRANTED,
            legal_basis=LegalBasis.CONSENT,
            granted_at=now - timedelta(days=800),
            expires_at=now - timedelta(days=1),
            withdrawn_at=None,
            ip_address_hash="",
            user_agent_hash="",
            consent_version="1.0",
        )
        assert record.is_valid() is False

    def test_consent_record_serialization(self):
        """Test serialization and deserialization."""
        now = datetime.now(timezone.utc)
        record = ConsentRecord(
            consent_id="c1",
            customer_id="cust1",
            consent_type=ConsentType.MODEL_UPDATES,
            status=ConsentStatus.GRANTED,
            legal_basis=LegalBasis.LEGITIMATE_INTEREST,
            granted_at=now,
            expires_at=now + timedelta(days=365),
            withdrawn_at=None,
            ip_address_hash="hash1",
            user_agent_hash="hash2",
            consent_version="1.0",
            scope={"key": "value"},
            metadata={"note": "test"},
        )
        data = record.to_dict()
        restored = ConsentRecord.from_dict(data)
        assert restored.consent_id == record.consent_id
        assert restored.consent_type == record.consent_type


class TestDataSubjectRequest:
    """Tests for DataSubjectRequest dataclass."""

    def test_request_creation(self):
        """Test creating a data subject request."""
        now = datetime.now(timezone.utc)
        request = DataSubjectRequest(
            request_id="req-123",
            customer_id="cust-456",
            right=DataSubjectRight.ERASURE,
            status="pending",
            submitted_at=now,
            completed_at=None,
            request_details={"reason": "No longer using service"},
            response_details={},
        )
        assert request.request_id == "req-123"
        assert request.right == DataSubjectRight.ERASURE
        assert request.status == "pending"

    def test_request_serialization(self):
        """Test serialization and deserialization."""
        now = datetime.now(timezone.utc)
        request = DataSubjectRequest(
            request_id="req-123",
            customer_id="cust-456",
            right=DataSubjectRight.ACCESS,
            status="completed",
            submitted_at=now,
            completed_at=now + timedelta(hours=24),
            request_details={},
            response_details={"data_exported": True},
        )
        data = request.to_dict()
        restored = DataSubjectRequest.from_dict(data)
        assert restored.request_id == request.request_id
        assert restored.right == request.right


class TestConsentAuditEntry:
    """Tests for ConsentAuditEntry dataclass."""

    def test_audit_entry_creation(self):
        """Test creating an audit entry."""
        now = datetime.now(timezone.utc)
        entry = ConsentAuditEntry(
            audit_id="audit-123",
            customer_id="cust-456",
            consent_id="consent-789",
            action="granted",
            consent_type=ConsentType.TRAINING_DATA,
            previous_status=None,
            new_status=ConsentStatus.GRANTED,
            timestamp=now,
            actor="customer",
            reason="Customer granted consent via UI",
            ip_address_hash="hash123",
            metadata={},
        )
        assert entry.audit_id == "audit-123"
        assert entry.action == "granted"
        assert entry.new_status == ConsentStatus.GRANTED

    def test_audit_entry_serialization(self):
        """Test serialization of audit entry."""
        now = datetime.now(timezone.utc)
        entry = ConsentAuditEntry(
            audit_id="audit-123",
            customer_id="cust-456",
            consent_id="consent-789",
            action="withdrawn",
            consent_type=ConsentType.SYNTHETIC_BUGS,
            previous_status=ConsentStatus.GRANTED,
            new_status=ConsentStatus.WITHDRAWN,
            timestamp=now,
            actor="customer",
            reason="Customer withdrew consent",
            ip_address_hash="hash",
            metadata={"method": "api"},
        )
        data = entry.to_dict()
        assert data["action"] == "withdrawn"
        assert data["new_status"] == "withdrawn"


class TestCustomerConsentProfile:
    """Tests for CustomerConsentProfile dataclass."""

    def test_profile_creation(self):
        """Test creating a consent profile."""
        now = datetime.now(timezone.utc)
        consents = {
            ConsentType.TRAINING_DATA: ConsentRecord(
                consent_id="c1",
                customer_id="cust1",
                consent_type=ConsentType.TRAINING_DATA,
                status=ConsentStatus.GRANTED,
                legal_basis=LegalBasis.CONSENT,
                granted_at=now,
                expires_at=now + timedelta(days=730),
                withdrawn_at=None,
                ip_address_hash="",
                user_agent_hash="",
                consent_version="1.0",
            )
        }
        profile = CustomerConsentProfile(
            customer_id="cust1",
            consents=consents,
            pending_requests=[],
            jurisdiction="GDPR",
            data_retention_days=730,
            last_updated=now,
        )
        assert profile.customer_id == "cust1"
        assert profile.jurisdiction == "GDPR"

    def test_profile_can_use_for_training(self):
        """Test checking training eligibility."""
        now = datetime.now(timezone.utc)
        consents = {
            ConsentType.TRAINING_DATA: ConsentRecord(
                consent_id="c1",
                customer_id="cust1",
                consent_type=ConsentType.TRAINING_DATA,
                status=ConsentStatus.GRANTED,
                legal_basis=LegalBasis.CONSENT,
                granted_at=now,
                expires_at=now + timedelta(days=730),
                withdrawn_at=None,
                ip_address_hash="",
                user_agent_hash="",
                consent_version="1.0",
            ),
            ConsentType.SYNTHETIC_BUGS: ConsentRecord(
                consent_id="c2",
                customer_id="cust1",
                consent_type=ConsentType.SYNTHETIC_BUGS,
                status=ConsentStatus.GRANTED,
                legal_basis=LegalBasis.CONSENT,
                granted_at=now,
                expires_at=now + timedelta(days=730),
                withdrawn_at=None,
                ip_address_hash="",
                user_agent_hash="",
                consent_version="1.0",
            ),
        }
        profile = CustomerConsentProfile(
            customer_id="cust1",
            consents=consents,
            pending_requests=[],
            jurisdiction="GDPR",
            data_retention_days=730,
            last_updated=now,
        )
        assert profile.can_use_for_training() is True


class TestConsentService:
    """Tests for ConsentService."""

    @pytest.fixture
    def service(self):
        """Create a ConsentService instance."""
        return ConsentService()

    @pytest.mark.asyncio
    async def test_grant_consent(self, service):
        """Test granting consent."""
        record = await service.grant_consent(
            customer_id="cust-123",
            consent_type=ConsentType.TRAINING_DATA,
            legal_basis=LegalBasis.CONSENT,
            scope={"repositories": ["repo-1"]},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        assert record is not None
        assert record.customer_id == "cust-123"
        assert record.consent_type == ConsentType.TRAINING_DATA
        assert record.status == ConsentStatus.GRANTED

    @pytest.mark.asyncio
    async def test_withdraw_consent(self, service):
        """Test withdrawing consent."""
        await service.grant_consent("cust-1", ConsentType.TRAINING_DATA)
        record = await service.withdraw_consent(
            customer_id="cust-1",
            consent_type=ConsentType.TRAINING_DATA,
            reason="No longer wish to participate",
            ip_address="192.168.1.1",
        )
        assert record is not None
        assert record.status == ConsentStatus.WITHDRAWN

    def test_check_consent_no_record(self, service):
        """Test checking consent when no record exists."""
        result = service.check_consent("non-existent", ConsentType.TRAINING_DATA)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_training_eligibility(self, service):
        """Test training eligibility when all consents granted."""
        await service.grant_consent("cust-1", ConsentType.TRAINING_DATA)
        await service.grant_consent("cust-1", ConsentType.SYNTHETIC_BUGS)

        eligibility = service.check_training_eligibility("cust-1")
        assert eligibility["eligible"] is True
        assert eligibility["missing_consents"] == []

    @pytest.mark.asyncio
    async def test_submit_data_subject_request(self, service):
        """Test submitting a data subject request."""
        request = await service.submit_data_subject_request(
            customer_id="cust-123",
            right=DataSubjectRight.ACCESS,
            request_details={"format": "json"},
        )
        assert request is not None
        assert request.right == DataSubjectRight.ACCESS
        assert request.status == "pending"

    def test_set_customer_jurisdiction(self, service):
        """Test setting customer jurisdiction."""
        service.set_customer_jurisdiction("cust-1", "GDPR")
        reqs = service.get_jurisdiction_requirements("cust-1")
        assert reqs["explicit_consent"] is True

    @pytest.mark.asyncio
    async def test_get_consent_profile(self, service):
        """Test getting complete consent profile."""
        await service.grant_consent("cust-1", ConsentType.TRAINING_DATA)
        await service.grant_consent("cust-1", ConsentType.SYNTHETIC_BUGS)
        service.set_customer_jurisdiction("cust-1", "GDPR")

        profile = service.get_consent_profile("cust-1")
        assert profile.customer_id == "cust-1"
        assert profile.jurisdiction == "GDPR"
        assert len(profile.consents) == 2

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """Test service health check."""
        health = await service.health_check()
        assert health["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_metrics(self, service):
        """Test getting service metrics."""
        await service.grant_consent("cust-1", ConsentType.TRAINING_DATA)
        metrics = service.get_metrics()
        assert "consents_granted" in metrics
        assert metrics["consents_granted"] >= 1

    @pytest.mark.asyncio
    async def test_withdraw_consent_no_record(self, service):
        """Test withdrawing consent when no record exists."""
        result = await service.withdraw_consent(
            customer_id="nonexistent-customer",
            consent_type=ConsentType.TRAINING_DATA,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_withdraw_synthetic_bugs_consent(self, service):
        """Test withdrawing synthetic bugs consent triggers cleanup."""
        await service.grant_consent("cust-1", ConsentType.SYNTHETIC_BUGS)
        result = await service.withdraw_consent(
            customer_id="cust-1",
            consent_type=ConsentType.SYNTHETIC_BUGS,
        )
        assert result is not None
        assert result.status == ConsentStatus.WITHDRAWN

    @pytest.mark.asyncio
    async def test_process_erasure_request(self, service):
        """Test processing a right to erasure request."""
        # Grant consent first
        await service.grant_consent("cust-1", ConsentType.TRAINING_DATA)
        await service.grant_consent("cust-1", ConsentType.SYNTHETIC_BUGS)

        # Submit erasure request
        request = await service.submit_data_subject_request(
            customer_id="cust-1",
            right=DataSubjectRight.ERASURE,
            request_details={"reason": "User requested deletion"},
        )

        # Process erasure
        result = await service.process_erasure_request(request.request_id)

        assert result.status == "completed"
        assert result.response_details["training_data_removed"] is True
        assert result.response_details["artifacts_removed"] is True
        assert result.response_details["consents_removed"] is True
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_process_erasure_request_not_found(self, service):
        """Test processing erasure request that doesn't exist."""
        with pytest.raises(ValueError, match="Request not found"):
            await service.process_erasure_request("nonexistent-request-id")

    @pytest.mark.asyncio
    async def test_process_erasure_request_wrong_type(self, service):
        """Test processing non-erasure request as erasure."""
        # Submit access request (not erasure)
        request = await service.submit_data_subject_request(
            customer_id="cust-1",
            right=DataSubjectRight.ACCESS,
        )

        with pytest.raises(ValueError, match="not an erasure request"):
            await service.process_erasure_request(request.request_id)

    @pytest.mark.asyncio
    async def test_get_customer_data_export(self, service):
        """Test exporting customer data for portability."""
        # Grant consent and make audit entries
        await service.grant_consent("cust-1", ConsentType.TRAINING_DATA)
        await service.grant_consent("cust-1", ConsentType.SYNTHETIC_BUGS)
        await service.submit_data_subject_request(
            customer_id="cust-1",
            right=DataSubjectRight.ACCESS,
        )

        export = await service.get_customer_data_export("cust-1")

        assert export["customer_id"] == "cust-1"
        assert export["data_format"] == "JSON"
        assert "training_data" in export["consents"]
        assert "synthetic_bugs" in export["consents"]
        assert len(export["audit_history"]) >= 2
        assert len(export["data_requests"]) >= 1
        # Verify PII removed
        for entry in export["audit_history"]:
            assert "ip_address_hash" not in entry

    def test_set_customer_jurisdiction_invalid(self, service):
        """Test setting invalid jurisdiction falls back to DEFAULT."""
        service.set_customer_jurisdiction("cust-1", "INVALID_JURISDICTION")
        reqs = service.get_jurisdiction_requirements("cust-1")
        assert reqs == ConsentService.JURISDICTION_REQUIREMENTS["DEFAULT"]

    @pytest.mark.asyncio
    async def test_check_expired_consents(self, service):
        """Test checking and marking expired consents."""
        # Grant consent with short expiration
        record = await service.grant_consent(
            customer_id="cust-1",
            consent_type=ConsentType.TRAINING_DATA,
            expiration_days=0,  # Expires immediately (same day)
        )

        # Manually set expires_at to past
        record.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

        expired = await service.check_expired_consents()

        assert len(expired) == 1
        assert expired[0].consent_id == record.consent_id
        assert expired[0].status == ConsentStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_check_expired_consents_none_expired(self, service):
        """Test check_expired_consents when no consents are expired."""
        await service.grant_consent("cust-1", ConsentType.TRAINING_DATA)

        expired = await service.check_expired_consents()
        assert len(expired) == 0

    def test_profile_to_dict(self):
        """Test CustomerConsentProfile serialization."""
        now = datetime.now(timezone.utc)
        consents = {
            ConsentType.TRAINING_DATA: ConsentRecord(
                consent_id="c1",
                customer_id="cust1",
                consent_type=ConsentType.TRAINING_DATA,
                status=ConsentStatus.GRANTED,
                legal_basis=LegalBasis.CONSENT,
                granted_at=now,
                expires_at=now + timedelta(days=730),
                withdrawn_at=None,
                ip_address_hash="",
                user_agent_hash="",
                consent_version="1.0",
            )
        }
        profile = CustomerConsentProfile(
            customer_id="cust1",
            consents=consents,
            pending_requests=[],
            jurisdiction="GDPR",
            data_retention_days=730,
            last_updated=now,
        )

        data = profile.to_dict()

        assert data["customer_id"] == "cust1"
        assert data["jurisdiction"] == "GDPR"
        assert data["data_retention_days"] == 730
        assert "training_data" in data["consents"]
        assert len(data["pending_requests"]) == 0

    @pytest.mark.asyncio
    async def test_process_erasure_request_failure(self, service):
        """Test processing erasure request when deletion fails."""
        from unittest.mock import MagicMock

        # Submit erasure request
        request = await service.submit_data_subject_request(
            customer_id="cust-1",
            right=DataSubjectRight.ERASURE,
        )

        # Create a mock dict that raises on __delitem__
        mock_consents = MagicMock()
        mock_consents.__contains__ = MagicMock(return_value=True)
        mock_consents.__delitem__ = MagicMock(side_effect=RuntimeError("DB error"))
        service._consents = mock_consents

        result = await service.process_erasure_request(request.request_id)

        assert result.status == "failed"
        assert "error" in result.response_details
        assert "DB error" in result.response_details["error"]
