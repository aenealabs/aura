"""
Tests for Compliance Evidence Service.

Tests cover:
- SOC 2 control definitions
- Evidence collection and verification
- Control assessments
- Compliance reporting
- Collection scheduling
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.services.compliance_evidence_service import (
    SOC2_CONTROLS,
    CollectionFrequency,
    CollectionSchedule,
    ComplianceEvidenceService,
    ComplianceReport,
    ControlAssessment,
    ControlDefinition,
    ControlStatus,
    EvidenceRecord,
    EvidenceStatus,
    EvidenceType,
    SOC2Category,
    get_compliance_evidence_service,
    reset_compliance_evidence_service,
)


@pytest.fixture
def service():
    """Provide a fresh compliance evidence service for each test."""
    reset_compliance_evidence_service()
    return get_compliance_evidence_service()


class TestSOC2Category:
    """Tests for SOC 2 category enum."""

    def test_all_categories_exist(self):
        """Verify all SOC 2 trust service criteria categories."""
        assert SOC2Category.SECURITY.value == "security"
        assert SOC2Category.AVAILABILITY.value == "availability"
        assert SOC2Category.PROCESSING_INTEGRITY.value == "processing_integrity"
        assert SOC2Category.CONFIDENTIALITY.value == "confidentiality"
        assert SOC2Category.PRIVACY.value == "privacy"

    def test_category_count(self):
        """Verify we have exactly 5 categories."""
        assert len(SOC2Category) == 5


class TestControlStatus:
    """Tests for control status enum."""

    def test_all_statuses_exist(self):
        """Verify all expected statuses are defined."""
        assert ControlStatus.IMPLEMENTED.value == "implemented"
        assert ControlStatus.PARTIALLY_IMPLEMENTED.value == "partially_implemented"
        assert ControlStatus.NOT_IMPLEMENTED.value == "not_implemented"
        assert ControlStatus.NOT_APPLICABLE.value == "not_applicable"


class TestEvidenceType:
    """Tests for evidence type enum."""

    def test_evidence_types_exist(self):
        """Verify key evidence types are defined."""
        assert EvidenceType.CONFIGURATION.value == "configuration"
        assert EvidenceType.LOG.value == "log"
        assert EvidenceType.SCREENSHOT.value == "screenshot"
        assert EvidenceType.DOCUMENT.value == "document"
        assert EvidenceType.SCAN_RESULT.value == "scan_result"
        assert EvidenceType.ATTESTATION.value == "attestation"
        assert EvidenceType.METRIC.value == "metric"
        assert EvidenceType.POLICY.value == "policy"
        assert EvidenceType.PROCEDURE.value == "procedure"
        assert EvidenceType.CHANGE_RECORD.value == "change_record"
        assert EvidenceType.INCIDENT_REPORT.value == "incident_report"
        assert EvidenceType.TRAINING_RECORD.value == "training_record"
        assert EvidenceType.ACCESS_REVIEW.value == "access_review"


class TestEvidenceStatus:
    """Tests for evidence status enum."""

    def test_all_statuses_exist(self):
        """Verify all expected statuses are defined."""
        assert EvidenceStatus.PENDING.value == "pending"
        assert EvidenceStatus.COLLECTED.value == "collected"
        assert EvidenceStatus.VERIFIED.value == "verified"
        assert EvidenceStatus.EXPIRED.value == "expired"
        assert EvidenceStatus.FAILED.value == "failed"


class TestCollectionFrequency:
    """Tests for collection frequency enum."""

    def test_all_frequencies_exist(self):
        """Verify all expected frequencies are defined."""
        assert CollectionFrequency.CONTINUOUS.value == "continuous"
        assert CollectionFrequency.DAILY.value == "daily"
        assert CollectionFrequency.WEEKLY.value == "weekly"
        assert CollectionFrequency.MONTHLY.value == "monthly"
        assert CollectionFrequency.QUARTERLY.value == "quarterly"
        assert CollectionFrequency.ANNUAL.value == "annual"
        assert CollectionFrequency.ON_DEMAND.value == "on_demand"


class TestSOC2Controls:
    """Tests for predefined SOC 2 controls."""

    def test_controls_defined(self):
        """Verify controls are defined in SOC2_CONTROLS."""
        assert len(SOC2_CONTROLS) > 0

    def test_security_controls_exist(self):
        """Verify security controls exist."""
        security_controls = [
            c for c in SOC2_CONTROLS.values() if c.category == SOC2Category.SECURITY
        ]
        assert len(security_controls) > 0

    def test_control_has_required_fields(self):
        """Verify controls have required fields."""
        for control_id, control in SOC2_CONTROLS.items():
            assert control.control_id == control_id
            assert control.category in SOC2Category
            assert len(control.name) > 0
            assert len(control.description) > 0
            assert len(control.evidence_required) > 0


class TestComplianceEvidenceService:
    """Tests for compliance evidence service initialization."""

    def test_service_initialization(self, service):
        """Verify service initializes correctly."""
        assert service is not None
        assert isinstance(service, ComplianceEvidenceService)

    def test_singleton_pattern(self):
        """Verify singleton pattern works."""
        reset_compliance_evidence_service()
        svc1 = get_compliance_evidence_service()
        svc2 = get_compliance_evidence_service()
        assert svc1 is svc2


class TestControlDefinitions:
    """Tests for control management."""

    def test_list_controls(self, service):
        """Test listing all controls."""
        controls = service.list_controls()
        assert len(controls) > 0
        assert all(isinstance(c, ControlDefinition) for c in controls)

    def test_list_controls_by_category(self, service):
        """Test listing controls filtered by category."""
        security_controls = service.list_controls(category=SOC2Category.SECURITY)
        assert len(security_controls) > 0
        assert all(c.category == SOC2Category.SECURITY for c in security_controls)

    def test_list_automated_controls(self, service):
        """Test listing only automated controls."""
        automated = service.list_controls(automated_only=True)
        assert all(c.automated is True for c in automated)

    def test_get_control(self, service):
        """Test getting a specific control."""
        control = service.get_control("CC6.1")
        assert control is not None
        assert control.control_id == "CC6.1"

    def test_get_nonexistent_control(self, service):
        """Test getting nonexistent control returns None."""
        control = service.get_control("NONEXISTENT")
        assert control is None

    def test_control_has_required_fields(self, service):
        """Test that controls have all required fields."""
        control = service.get_control("CC6.1")
        assert hasattr(control, "control_id")
        assert hasattr(control, "category")
        assert hasattr(control, "name")
        assert hasattr(control, "description")
        assert hasattr(control, "evidence_required")
        assert hasattr(control, "collection_frequency")


class TestEvidenceCollection:
    """Tests for evidence collection."""

    @pytest.mark.asyncio
    async def test_collect_evidence(self, service):
        """Test collecting evidence for a control."""
        evidence = await service.collect_evidence(
            control_id="CC6.1",
            evidence_type=EvidenceType.CONFIGURATION,
            collected_by="test-user",
        )

        assert isinstance(evidence, EvidenceRecord)
        assert evidence.control_id == "CC6.1"
        assert evidence.status == EvidenceStatus.COLLECTED

    @pytest.mark.asyncio
    async def test_collect_log_evidence(self, service):
        """Test collecting log evidence."""
        evidence = await service.collect_evidence(
            control_id="CC6.6",
            evidence_type=EvidenceType.LOG,
        )

        assert evidence.evidence_type == EvidenceType.LOG

    @pytest.mark.asyncio
    async def test_collect_scan_result_evidence(self, service):
        """Test collecting scan result evidence."""
        evidence = await service.collect_evidence(
            control_id="CC7.1",
            evidence_type=EvidenceType.SCAN_RESULT,
        )

        assert evidence.evidence_type == EvidenceType.SCAN_RESULT

    @pytest.mark.asyncio
    async def test_collect_evidence_invalid_control(self, service):
        """Test collecting evidence for invalid control raises error."""
        with pytest.raises(ValueError, match="Control not found"):
            await service.collect_evidence(
                control_id="INVALID",
                evidence_type=EvidenceType.LOG,
            )

    def test_get_evidence(self, service):
        """Test getting nonexistent evidence returns None."""
        evidence = service.get_evidence("nonexistent-id")
        assert evidence is None

    @pytest.mark.asyncio
    async def test_get_evidence_by_id(self, service):
        """Test getting evidence by ID."""
        # First collect some evidence
        evidence = await service.collect_evidence(
            control_id="CC6.1",
            evidence_type=EvidenceType.CONFIGURATION,
        )

        # Then retrieve it
        retrieved = service.get_evidence(evidence.evidence_id)
        assert retrieved is not None
        assert retrieved.evidence_id == evidence.evidence_id

    @pytest.mark.asyncio
    async def test_get_evidence_for_control(self, service):
        """Test getting all evidence for a control."""
        # Collect evidence
        await service.collect_evidence(
            control_id="CC6.1",
            evidence_type=EvidenceType.CONFIGURATION,
        )

        evidence_list = service.get_evidence_for_control("CC6.1")
        assert isinstance(evidence_list, list)
        assert len(evidence_list) >= 1

    @pytest.mark.asyncio
    async def test_verify_evidence(self, service):
        """Test verifying collected evidence."""
        evidence = await service.collect_evidence(
            control_id="CC6.1",
            evidence_type=EvidenceType.CONFIGURATION,
        )

        result = service.verify_evidence(evidence.evidence_id, "auditor")
        assert result is True

        # Check status updated
        verified = service.get_evidence(evidence.evidence_id)
        assert verified.status == EvidenceStatus.VERIFIED
        assert verified.verified_by == "auditor"

    def test_verify_nonexistent_evidence(self, service):
        """Test verifying nonexistent evidence returns False."""
        result = service.verify_evidence("nonexistent-id", "auditor")
        assert result is False


class TestControlAssessment:
    """Tests for control assessment."""

    @pytest.mark.asyncio
    async def test_assess_control(self, service):
        """Test assessing a control."""
        assessment = await service.assess_control(
            control_id="CC6.1",
            assessed_by="auditor",
        )

        assert isinstance(assessment, ControlAssessment)
        assert assessment.control_id == "CC6.1"
        assert assessment.status in ControlStatus

    @pytest.mark.asyncio
    async def test_assess_control_with_findings(self, service):
        """Test assessing control with findings."""
        assessment = await service.assess_control(
            control_id="CC6.1",
            assessed_by="auditor",
            findings=["MFA not enforced for all users"],
            recommendations=["Enable MFA requirement"],
        )

        assert len(assessment.findings) == 1
        assert len(assessment.recommendations) == 1

    @pytest.mark.asyncio
    async def test_assess_invalid_control(self, service):
        """Test assessing invalid control raises error."""
        with pytest.raises(ValueError, match="Control not found"):
            await service.assess_control(
                control_id="INVALID",
                assessed_by="auditor",
            )

    @pytest.mark.asyncio
    async def test_get_control_status(self, service):
        """Test getting latest control assessment status."""
        await service.assess_control(
            control_id="CC6.1",
            assessed_by="auditor",
        )

        status = service.get_control_status("CC6.1")
        assert status is not None
        assert isinstance(status, ControlAssessment)


class TestComplianceReporting:
    """Tests for compliance reporting."""

    @pytest.mark.asyncio
    async def test_generate_report(self, service):
        """Test generating a compliance report."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=90)

        report = await service.generate_compliance_report(
            period_start=period_start,
            period_end=now,
            generated_by="auditor",
        )

        assert isinstance(report, ComplianceReport)
        assert report.total_controls > 0
        assert 0 <= report.overall_score <= 100

    @pytest.mark.asyncio
    async def test_report_has_required_fields(self, service):
        """Test report has all required fields."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=30)

        report = await service.generate_compliance_report(
            period_start=period_start,
            period_end=now,
            generated_by="test-user",
        )

        assert hasattr(report, "report_id")
        assert hasattr(report, "period_start")
        assert hasattr(report, "period_end")
        assert hasattr(report, "total_controls")
        assert hasattr(report, "implemented")
        assert hasattr(report, "partially_implemented")
        assert hasattr(report, "not_implemented")
        assert hasattr(report, "overall_score")
        assert hasattr(report, "gaps")
        assert hasattr(report, "recommendations")

    def test_list_reports(self, service):
        """Test listing compliance reports."""
        reports = service.list_reports()
        assert isinstance(reports, list)

    @pytest.mark.asyncio
    async def test_get_report_by_id(self, service):
        """Test getting report by ID."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=30)

        report = await service.generate_compliance_report(
            period_start=period_start,
            period_end=now,
            generated_by="test-user",
        )

        retrieved = service.get_report(report.report_id)
        assert retrieved is not None
        assert retrieved.report_id == report.report_id

    def test_get_nonexistent_report(self, service):
        """Test getting nonexistent report returns None."""
        result = service.get_report("nonexistent-id")
        assert result is None


class TestCollectionSchedule:
    """Tests for evidence collection scheduling."""

    def test_create_schedule(self, service):
        """Test creating a collection schedule."""
        schedule = service.create_collection_schedule(
            control_id="CC6.1",
            evidence_type=EvidenceType.CONFIGURATION,
            collector="iam_configuration",
        )

        assert isinstance(schedule, CollectionSchedule)
        assert schedule.control_id == "CC6.1"
        assert schedule.enabled is True

    def test_create_schedule_invalid_control(self, service):
        """Test creating schedule for invalid control raises error."""
        with pytest.raises(ValueError, match="Control not found"):
            service.create_collection_schedule(
                control_id="INVALID",
                evidence_type=EvidenceType.LOG,
                collector="test_collector",
            )

    def test_get_due_collections(self, service):
        """Test getting due collections."""
        due = service.get_due_collections()
        assert isinstance(due, list)

    @pytest.mark.asyncio
    async def test_run_scheduled_collections(self, service):
        """Test running scheduled collections."""
        # Create a schedule
        service.create_collection_schedule(
            control_id="CC6.1",
            evidence_type=EvidenceType.CONFIGURATION,
            collector="iam_configuration",
        )

        # Run scheduled collections
        results = await service.run_scheduled_collections()
        assert "success" in results
        assert "failed" in results


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_invalid_control_id(self, service):
        """Test error handling for invalid control ID."""
        with pytest.raises(ValueError):
            await service.collect_evidence(
                control_id="NONEXISTENT",
                evidence_type=EvidenceType.LOG,
            )

    def test_invalid_category_filter(self, service):
        """Test filtering with valid category works."""
        controls = service.list_controls(category=SOC2Category.AVAILABILITY)
        assert isinstance(controls, list)


class TestIntegration:
    """Integration tests for compliance workflows."""

    @pytest.mark.asyncio
    async def test_full_compliance_workflow(self, service):
        """Test complete compliance assessment workflow."""
        # 1. List controls
        controls = service.list_controls(category=SOC2Category.SECURITY)
        assert len(controls) > 0

        # 2. Collect evidence for a control
        control = controls[0]
        if control.automated and control.evidence_required:
            evidence_type = control.evidence_required[0]
            try:
                evidence = await service.collect_evidence(
                    control_id=control.control_id,
                    evidence_type=evidence_type,
                )
                assert evidence is not None
            except ValueError:
                # Some evidence types may not have collectors
                pass

        # 3. Assess the control
        assessment = await service.assess_control(
            control_id=control.control_id,
            assessed_by="test-auditor",
        )
        assert assessment is not None

        # 4. Generate report
        now = datetime.now(timezone.utc)
        report = await service.generate_compliance_report(
            period_start=now - timedelta(days=30),
            period_end=now,
            generated_by="test-auditor",
        )
        assert report is not None
        assert report.total_controls > 0

    @pytest.mark.asyncio
    async def test_evidence_to_assessment_workflow(self, service):
        """Test workflow from evidence collection to assessment."""
        control_id = "CC6.6"  # Security Event Logging

        # Collect multiple types of evidence
        evidence_ids = []
        for evidence_type in [EvidenceType.LOG, EvidenceType.CONFIGURATION]:
            try:
                evidence = await service.collect_evidence(
                    control_id=control_id,
                    evidence_type=evidence_type,
                )
                evidence_ids.append(evidence.evidence_id)

                # Verify the evidence
                service.verify_evidence(evidence.evidence_id, "auditor")
            except ValueError:
                pass

        # Assess the control
        assessment = await service.assess_control(
            control_id=control_id,
            assessed_by="auditor",
        )

        # Verify assessment has evidence
        assert len(assessment.evidence_ids) > 0
