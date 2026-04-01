"""End-to-End Integration Tests for Project Aura Security Pipeline.

Tests the complete workflow: threat detection → ADR creation → sandbox testing →
HITL approval → deployment.

These tests verify the full integration of all pipeline components working together
to detect, analyze, patch, and deploy security fixes with human oversight.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.adaptive_intelligence_agent import (
    AdaptiveIntelligenceAgent,
    AdaptiveRecommendation,
    EffortLevel,
    RecommendationType,
    RiskLevel,
)
from src.agents.adr_generator_agent import ADRDocument, ADRGeneratorAgent
from src.agents.architecture_review_agent import (
    ADRCategory,
    ADRSignificance,
    ADRTriggerEvent,
    ArchitectureReviewAgent,
)
from src.agents.threat_intelligence_agent import (
    ThreatCategory,
    ThreatIntelConfig,
    ThreatIntelligenceAgent,
    ThreatIntelReport,
    ThreatSeverity,
)
from src.services.hitl_approval_service import (
    ApprovalStatus,
    HITLApprovalError,
    HITLApprovalService,
    HITLMode,
    PatchSeverity,
)
from src.services.notification_service import NotificationMode, NotificationService
from src.services.sandbox_network_service import FargateSandboxOrchestrator

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def threat_agent():
    """Create a threat intelligence agent."""
    return ThreatIntelligenceAgent(
        config=ThreatIntelConfig(
            check_interval_minutes=60,
            max_cve_age_days=30,
            severity_threshold=ThreatSeverity.MEDIUM,
        )
    )


@pytest.fixture
def adaptive_agent():
    """Create an adaptive intelligence agent."""
    return AdaptiveIntelligenceAgent()


@pytest.fixture
def review_agent():
    """Create an architecture review agent."""
    return ArchitectureReviewAgent()


@pytest.fixture
def generator_agent():
    """Create an ADR generator agent."""
    return ADRGeneratorAgent()


@pytest.fixture
def hitl_service():
    """Create a HITL approval service in mock mode."""
    return HITLApprovalService(mode=HITLMode.MOCK, timeout_hours=24)


@pytest.fixture
def notification_service():
    """Create a notification service in mock mode."""
    return NotificationService(mode=NotificationMode.MOCK)


@pytest.fixture
def sandbox_orchestrator():
    """Create a mock sandbox orchestrator for testing."""
    # Create mock sandbox orchestrator with mocked AWS clients
    mock_sandbox = MagicMock()
    mock_sandbox.sandbox_id = "sandbox-test-123"
    mock_sandbox.status = "READY"

    orchestrator = MagicMock(spec=FargateSandboxOrchestrator)
    orchestrator.provision_sandbox = AsyncMock(return_value=mock_sandbox)
    orchestrator.run_tests = AsyncMock(
        return_value={"tests_passed": 45, "tests_failed": 0}
    )
    orchestrator.destroy_sandbox = AsyncMock(return_value=True)
    orchestrator.get_sandbox_status = AsyncMock(return_value="READY")

    return orchestrator


@pytest.fixture
def critical_threat():
    """Create a critical severity threat for testing."""
    return ThreatIntelReport(
        id="threat-critical-001",
        title="Critical SQL Injection in Authentication Module",
        category=ThreatCategory.CVE,
        severity=ThreatSeverity.CRITICAL,
        source="NVD",
        published_date=datetime.now() - timedelta(hours=2),
        description=(
            "A critical SQL injection vulnerability exists in the authentication "
            "module's login handler. An unauthenticated attacker can execute "
            "arbitrary SQL queries, leading to complete database compromise."
        ),
        affected_components=["src/auth/login_handler.py"],
        cve_ids=["CVE-2025-0001"],
        cvss_score=9.8,
    )


@pytest.fixture
def high_threat():
    """Create a high severity threat for testing."""
    return ThreatIntelReport(
        id="threat-high-001",
        title="Cross-Site Scripting in Comment System",
        category=ThreatCategory.CVE,
        severity=ThreatSeverity.HIGH,
        source="CISA",
        published_date=datetime.now() - timedelta(hours=6),
        description=(
            "A stored XSS vulnerability allows attackers to inject malicious "
            "scripts into user comments that execute when viewed by other users."
        ),
        affected_components=["src/views/comment_renderer.tsx"],
        cve_ids=["CVE-2025-0002"],
        cvss_score=7.5,
    )


@pytest.fixture
def low_threat():
    """Create a low severity threat for testing."""
    return ThreatIntelReport(
        id="threat-low-001",
        title="Minor Information Disclosure in Error Messages",
        category=ThreatCategory.CVE,
        severity=ThreatSeverity.LOW,
        source="NVD",
        published_date=datetime.now() - timedelta(days=5),
        description=(
            "Error messages may reveal internal path information under "
            "specific error conditions. Impact is minimal."
        ),
        affected_components=[],
        cve_ids=["CVE-2025-0003"],
        cvss_score=2.5,
    )


# ============================================================================
# Phase 1: Threat Detection Tests
# ============================================================================


class TestPhase1ThreatDetection:
    """Tests for Phase 1: Threat Detection."""

    def test_threat_agent_prioritizes_by_severity(
        self, threat_agent, critical_threat, high_threat, low_threat
    ):
        """Test that threats are prioritized by severity."""
        threats = [low_threat, critical_threat, high_threat]

        prioritized = threat_agent._prioritize_by_relevance(threats)

        # Critical should be first
        assert prioritized[0].severity == ThreatSeverity.CRITICAL
        assert prioritized[1].severity == ThreatSeverity.HIGH
        assert prioritized[2].severity == ThreatSeverity.LOW

    def test_threat_agent_filters_duplicates(self, threat_agent, critical_threat):
        """Test that duplicate threats are filtered."""
        # First processing
        new_threats = threat_agent._filter_new_reports([critical_threat])
        assert len(new_threats) == 1

        # Second processing - should be empty
        duplicate_threats = threat_agent._filter_new_reports([critical_threat])
        assert len(duplicate_threats) == 0

    def test_threat_agent_matches_dependencies(self, threat_agent, critical_threat):
        """Test that threats are matched against SBOM."""
        threat_agent.set_dependency_sbom(
            [
                {"name": "fastapi", "version": "0.108.0"},
                {"name": "pydantic", "version": "2.5.0"},
            ]
        )

        # This threat affects a file, not a dependency
        matches = threat_agent._check_dependency_match(
            critical_threat.affected_components
        )

        # File paths are not in SBOM
        assert len(matches) == 0

    def test_threat_detection_with_cvss_score(self, threat_agent, critical_threat):
        """Test that CVSS score is tracked."""
        assert critical_threat.cvss_score == 9.8

        # High CVSS score threats should be prioritized
        report_dict = critical_threat.to_dict()
        assert report_dict["cvss_score"] == 9.8


# ============================================================================
# Phase 2: Adaptive Intelligence Tests
# ============================================================================


class TestPhase2AdaptiveIntelligence:
    """Tests for Phase 2: Adaptive Intelligence Analysis."""

    @pytest.mark.asyncio
    async def test_critical_threat_generates_recommendation(
        self, adaptive_agent, critical_threat
    ):
        """Test that critical threats generate recommendations."""
        recommendations = await adaptive_agent.analyze_threats([critical_threat])

        assert len(recommendations) == 1
        rec = recommendations[0]

        assert rec.severity == ThreatSeverity.CRITICAL
        assert rec.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]
        assert rec.risk_score >= 9.0

    @pytest.mark.asyncio
    async def test_recommendation_includes_implementation_steps(
        self, adaptive_agent, high_threat
    ):
        """Test that recommendations include implementation steps."""
        recommendations = await adaptive_agent.analyze_threats([high_threat])

        assert len(recommendations) == 1
        rec = recommendations[0]

        assert len(rec.implementation_steps) > 0
        assert all(isinstance(step, str) for step in rec.implementation_steps)

    @pytest.mark.asyncio
    async def test_effort_estimation(self, adaptive_agent, critical_threat):
        """Test that effort is estimated correctly."""
        recommendations = await adaptive_agent.analyze_threats([critical_threat])

        rec = recommendations[0]

        # Single file = small to medium effort
        assert rec.effort_level in [
            EffortLevel.TRIVIAL,
            EffortLevel.SMALL,
            EffortLevel.MEDIUM,
        ]

    @pytest.mark.asyncio
    async def test_recommendation_type_determination(
        self, adaptive_agent, critical_threat
    ):
        """Test that recommendation type is determined correctly."""
        recommendations = await adaptive_agent.analyze_threats([critical_threat])

        rec = recommendations[0]

        # CVE with affected components should be security patch or dependency upgrade
        assert rec.recommendation_type in [
            RecommendationType.SECURITY_PATCH,
            RecommendationType.DEPENDENCY_UPGRADE,
        ]


# ============================================================================
# Phase 3: Architecture Review Tests
# ============================================================================


class TestPhase3ArchitectureReview:
    """Tests for Phase 3: Architecture Review and ADR Triggering."""

    @pytest.mark.asyncio
    async def test_critical_recommendation_triggers_adr(
        self, adaptive_agent, review_agent, critical_threat
    ):
        """Test that critical recommendations trigger ADR creation."""
        recommendations = await adaptive_agent.analyze_threats([critical_threat])
        triggers = review_agent.evaluate_recommendations(recommendations)

        assert len(triggers) == 1
        trigger = triggers[0]

        assert trigger.significance == ADRSignificance.CRITICAL
        assert trigger.requires_hitl is True

    @pytest.mark.asyncio
    async def test_high_recommendation_triggers_adr(
        self, adaptive_agent, review_agent, high_threat
    ):
        """Test that high severity recommendations trigger ADR creation."""
        recommendations = await adaptive_agent.analyze_threats([high_threat])
        triggers = review_agent.evaluate_recommendations(recommendations)

        assert len(triggers) == 1
        trigger = triggers[0]

        assert trigger.significance in [ADRSignificance.HIGH, ADRSignificance.CRITICAL]

    @pytest.mark.asyncio
    async def test_low_recommendation_may_not_trigger_adr(
        self, adaptive_agent, review_agent, low_threat
    ):
        """Test that low severity recommendations may not trigger ADR."""
        recommendations = await adaptive_agent.analyze_threats([low_threat])
        triggers = review_agent.evaluate_recommendations(recommendations)

        # Low severity may or may not trigger ADR
        for trigger in triggers:
            if trigger.significance == ADRSignificance.LOW:
                assert trigger.requires_hitl is False

    def test_adr_category_determination(self, review_agent):
        """Test ADR category determination from recommendation type."""
        security_rec = AdaptiveRecommendation(
            id="REC-001",
            title="Security Patch",
            recommendation_type=RecommendationType.SECURITY_PATCH,
            severity=ThreatSeverity.HIGH,
            risk_score=8.0,
            risk_level=RiskLevel.HIGH,
            effort_level=EffortLevel.MEDIUM,
            description="Security patch",
            rationale="Fix vulnerability",
        )

        category = review_agent._determine_category(security_rec)
        assert category == ADRCategory.SECURITY


# ============================================================================
# Phase 4: ADR Generation Tests
# ============================================================================


class TestPhase4ADRGeneration:
    """Tests for Phase 4: ADR Document Generation."""

    @pytest.mark.asyncio
    async def test_adr_generation_from_trigger(self, generator_agent):
        """Test ADR generation from trigger event."""
        trigger = ADRTriggerEvent(
            id="TRIG-001",
            title="Critical SQL Injection Fix",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.CRITICAL,
            description="Fix critical SQL injection vulnerability",
            context_summary="Authentication bypass via SQL injection",
            affected_components=["src/auth/login_handler.py"],
            requires_hitl=True,
        )

        adrs = await generator_agent.generate_adrs([trigger])

        assert len(adrs) == 1
        adr = adrs[0]

        assert adr.status == "Proposed"
        assert "SQL Injection" in adr.title or "Critical" in adr.title
        assert len(adr.alternatives) > 0
        assert len(adr.consequences_positive) > 0
        assert len(adr.consequences_negative) > 0

    @pytest.mark.asyncio
    async def test_adr_markdown_format(self, generator_agent):
        """Test ADR markdown output format."""
        trigger = ADRTriggerEvent(
            id="TRIG-002",
            title="XSS Prevention Update",
            category=ADRCategory.SECURITY,
            significance=ADRSignificance.HIGH,
            description="Prevent XSS attacks",
            context_summary="Stored XSS in comments",
        )

        adrs = await generator_agent.generate_adrs([trigger])
        adr = adrs[0]

        markdown = adr.to_markdown()

        # Verify standard ADR sections
        assert "# ADR-" in markdown
        assert "**Status:**" in markdown
        assert "## Context" in markdown
        assert "## Decision" in markdown
        assert "## Alternatives Considered" in markdown
        assert "## Consequences" in markdown
        assert "## References" in markdown

    def test_adr_filename_generation(self, generator_agent):
        """Test ADR filename generation."""
        adr = ADRDocument(
            number=100,
            title="Test Security Fix",
            status="Proposed",
            date="2025-12-01",
            decision_makers="Security Team",
            context="Context",
            decision="Decision",
        )

        filename = adr.get_filename()

        assert filename.startswith("ADR-100-")
        assert filename.endswith(".md")
        assert "test-security-fix" in filename


# ============================================================================
# Phase 5: Sandbox Testing Tests
# ============================================================================


class TestPhase5SandboxTesting:
    """Tests for Phase 5: Sandbox Testing."""

    @pytest.mark.asyncio
    async def test_sandbox_provisioning(self, sandbox_orchestrator):
        """Test sandbox environment provisioning."""
        sandbox = await sandbox_orchestrator.provision_sandbox(
            patch_id="patch-001",
            timeout_minutes=30,
        )

        assert sandbox is not None
        assert sandbox.status in ["PROVISIONING", "READY"]

    @pytest.mark.asyncio
    async def test_sandbox_test_execution(self, sandbox_orchestrator):
        """Test execution of tests in sandbox."""
        sandbox = await sandbox_orchestrator.provision_sandbox(
            patch_id="patch-002",
            timeout_minutes=30,
        )

        # Execute tests
        results = await sandbox_orchestrator.run_tests(
            sandbox.sandbox_id,
            test_suite=["unit", "integration"],
        )

        assert results is not None
        assert "passed" in results or "tests_passed" in results

    @pytest.mark.asyncio
    async def test_sandbox_cleanup(self, sandbox_orchestrator):
        """Test sandbox cleanup after testing."""
        sandbox = await sandbox_orchestrator.provision_sandbox(
            patch_id="patch-003",
            timeout_minutes=30,
        )

        # Cleanup
        result = await sandbox_orchestrator.destroy_sandbox(sandbox.sandbox_id)

        assert result is True


# ============================================================================
# Phase 6: HITL Approval Tests
# ============================================================================


class TestPhase6HITLApproval:
    """Tests for Phase 6: Human-in-the-Loop Approval."""

    def test_create_approval_request(self, hitl_service):
        """Test creating an approval request."""
        request = hitl_service.create_approval_request(
            patch_id="patch-001",
            vulnerability_id="CVE-2025-0001",
            severity=PatchSeverity.CRITICAL,
            patch_diff="- old_code\n+ new_code",
            sandbox_results={"tests_passed": 45, "tests_failed": 0},
        )

        assert request.status == ApprovalStatus.PENDING
        assert request.severity == PatchSeverity.CRITICAL
        assert request.approval_id is not None

    def test_approve_request(self, hitl_service):
        """Test approving a request."""
        request = hitl_service.create_approval_request(
            patch_id="patch-002",
            vulnerability_id="CVE-2025-0002",
        )

        result = hitl_service.approve_request(
            approval_id=request.approval_id,
            reviewer_id="security-lead@example.com",
            reason="Patch verified, sandbox tests passed",
        )

        assert result is True

        updated = hitl_service.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.APPROVED
        assert updated.reviewed_by == "security-lead@example.com"

    def test_reject_request_requires_reason(self, hitl_service):
        """Test that rejection requires a reason."""
        request = hitl_service.create_approval_request(
            patch_id="patch-003",
            vulnerability_id="CVE-2025-0003",
        )

        with pytest.raises(HITLApprovalError):
            hitl_service.reject_request(
                approval_id=request.approval_id,
                reviewer_id="reviewer@example.com",
                reason="",  # Empty reason should fail
            )

    def test_request_expiration(self, hitl_service):
        """Test request expiration handling."""
        request = hitl_service.create_approval_request(
            patch_id="patch-004",
            vulnerability_id="CVE-2025-0004",
        )

        # Manually expire the request
        past_time = (datetime.now() - timedelta(hours=48)).isoformat()
        hitl_service.mock_store[request.approval_id]["expiresAt"] = past_time

        # Try to approve - should fail due to expiration
        result = hitl_service.approve_request(
            approval_id=request.approval_id,
            reviewer_id="reviewer@example.com",
            reason="Too late",
        )

        assert result is False

        updated = hitl_service.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.EXPIRED


# ============================================================================
# Phase 7: Notification Tests
# ============================================================================


class TestPhase7Notifications:
    """Tests for Phase 7: Notification Delivery."""

    def test_approval_notification_sent(self, notification_service):
        """Test approval request notification is sent."""
        results = notification_service.send_approval_notification(
            approval_id="approval-001",
            patch_id="patch-001",
            vulnerability_id="CVE-2025-0001",
            severity="CRITICAL",
            created_at=datetime.now().isoformat(),
            expires_at=(datetime.now() + timedelta(hours=24)).isoformat(),
            sandbox_results={"tests_passed": 45, "tests_failed": 0},
            patch_diff="- old\n+ new",
            recipients=["security-team@example.com"],
        )

        # Should have both email and SNS
        assert len(results) >= 2
        assert all(r.success for r in results)

    def test_decision_notification_sent(self, notification_service):
        """Test decision notification is sent."""
        results = notification_service.send_decision_notification(
            approval_id="approval-002",
            patch_id="patch-002",
            decision="APPROVED",
            reviewer="lead@example.com",
            reason="LGTM",
            recipients=["dev-team@example.com"],
        )

        assert len(results) >= 2
        assert all(r.success for r in results)

    def test_expiration_warning_sent(self, notification_service):
        """Test expiration warning is sent."""
        results = notification_service.send_expiration_warning(
            approval_id="approval-003",
            patch_id="patch-003",
            severity="MEDIUM",
            expires_at=(datetime.now() + timedelta(hours=4)).isoformat(),
            recipients=["reviewer@example.com"],
        )

        assert len(results) >= 1
        assert all(r.success for r in results)


# ============================================================================
# Full Pipeline Integration Tests
# ============================================================================


class TestFullPipelineIntegration:
    """Tests for the complete end-to-end pipeline."""

    @pytest.mark.asyncio
    async def test_critical_threat_to_approved_deployment(
        self,
        threat_agent,
        adaptive_agent,
        review_agent,
        generator_agent,
        sandbox_orchestrator,
        hitl_service,
        notification_service,
        critical_threat,
    ):
        """Test complete pipeline from critical threat to approved deployment."""
        # Phase 1: Threat Detection
        new_threats = threat_agent._filter_new_reports([critical_threat])
        assert len(new_threats) == 1

        prioritized = threat_agent._prioritize_by_relevance(new_threats)
        assert prioritized[0].severity == ThreatSeverity.CRITICAL

        # Phase 2: Adaptive Intelligence
        recommendations = await adaptive_agent.analyze_threats(prioritized)
        assert len(recommendations) == 1
        assert recommendations[0].risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]

        # Phase 3: Architecture Review
        triggers = review_agent.evaluate_recommendations(recommendations)
        assert len(triggers) == 1
        assert triggers[0].requires_hitl is True

        # Phase 4: ADR Generation
        adrs = await generator_agent.generate_adrs(triggers)
        assert len(adrs) == 1
        assert adrs[0].status == "Proposed"

        # Phase 5: Sandbox Testing
        sandbox = await sandbox_orchestrator.provision_sandbox(
            patch_id="patch-crit-001",
            timeout_minutes=30,
        )
        assert sandbox is not None

        test_results = await sandbox_orchestrator.run_tests(
            sandbox.sandbox_id,
            test_suite=["unit", "security"],
        )
        assert test_results is not None

        # Phase 6: HITL Approval
        approval_request = hitl_service.create_approval_request(
            patch_id="patch-crit-001",
            vulnerability_id=critical_threat.cve_ids[0],
            severity=PatchSeverity.CRITICAL,
            sandbox_results=test_results,
            patch_diff="- vulnerable_code\n+ secure_code",
        )

        # Phase 7: Send notification
        notification_service.send_approval_notification(
            approval_id=approval_request.approval_id,
            patch_id="patch-crit-001",
            vulnerability_id=critical_threat.cve_ids[0],
            severity="CRITICAL",
            created_at=approval_request.created_at,
            expires_at=approval_request.expires_at,
            sandbox_results=test_results,
            patch_diff="- vulnerable_code\n+ secure_code",
            recipients=["security-team@example.com"],
        )

        # Simulate approval
        approved = hitl_service.approve_request(
            approval_id=approval_request.approval_id,
            reviewer_id="security-lead@example.com",
            reason="Sandbox tests passed, patch verified",
        )
        assert approved is True

        # Verify final state
        final_request = hitl_service.get_request(approval_request.approval_id)
        assert final_request.status == ApprovalStatus.APPROVED

        # Cleanup sandbox
        await sandbox_orchestrator.destroy_sandbox(sandbox.sandbox_id)

    @pytest.mark.asyncio
    async def test_low_threat_filtered_no_hitl_required(
        self,
        threat_agent,
        adaptive_agent,
        review_agent,
        low_threat,
    ):
        """Test that low severity threats don't require HITL."""
        # Phase 1: Threat Detection
        new_threats = threat_agent._filter_new_reports([low_threat])
        prioritized = threat_agent._prioritize_by_relevance(new_threats)

        # Phase 2: Adaptive Intelligence
        recommendations = await adaptive_agent.analyze_threats(prioritized)

        # Phase 3: Architecture Review
        triggers = review_agent.evaluate_recommendations(recommendations)

        # Low severity should not require HITL
        for trigger in triggers:
            if trigger.significance == ADRSignificance.LOW:
                assert trigger.requires_hitl is False

    @pytest.mark.asyncio
    async def test_rejected_patch_workflow(
        self,
        hitl_service,
        notification_service,
    ):
        """Test workflow when patch is rejected."""
        # Create approval request
        request = hitl_service.create_approval_request(
            patch_id="patch-rejected",
            vulnerability_id="CVE-2025-9999",
            severity=PatchSeverity.HIGH,
            patch_diff="questionable code change",
        )

        # Reject the request
        rejected = hitl_service.reject_request(
            approval_id=request.approval_id,
            reviewer_id="security-lead@example.com",
            reason="Patch introduces new security issues",
        )
        assert rejected is True

        # Send rejection notification
        results = notification_service.send_decision_notification(
            approval_id=request.approval_id,
            patch_id="patch-rejected",
            decision="REJECTED",
            reviewer="security-lead@example.com",
            reason="Patch introduces new security issues",
            recipients=["dev-team@example.com"],
        )
        assert all(r.success for r in results)

        # Verify final state
        final_request = hitl_service.get_request(request.approval_id)
        assert final_request.status == ApprovalStatus.REJECTED


# ============================================================================
# Pipeline State Tracking Tests
# ============================================================================


@dataclass
class PipelineState:
    """Tracks state through pipeline stages."""

    stage: str
    threat_id: Optional[str] = None
    recommendation_id: Optional[str] = None
    trigger_id: Optional[str] = None
    adr_number: Optional[int] = None
    sandbox_id: Optional[str] = None
    approval_id: Optional[str] = None
    final_status: Optional[str] = None


class TestPipelineStateTracking:
    """Tests for pipeline state tracking and audit trail."""

    @pytest.mark.asyncio
    async def test_state_tracking_through_pipeline(
        self,
        threat_agent,
        adaptive_agent,
        review_agent,
        generator_agent,
        hitl_service,
        critical_threat,
    ):
        """Test that state is properly tracked through all stages."""
        state = PipelineState(stage="initialized")

        # Phase 1
        state.stage = "threat_detection"
        state.threat_id = critical_threat.id
        assert state.threat_id is not None

        # Phase 2
        recommendations = await adaptive_agent.analyze_threats([critical_threat])
        state.stage = "adaptive_intelligence"
        state.recommendation_id = recommendations[0].id
        assert state.recommendation_id is not None

        # Phase 3
        triggers = review_agent.evaluate_recommendations(recommendations)
        state.stage = "architecture_review"
        state.trigger_id = triggers[0].id
        assert state.trigger_id is not None

        # Phase 4
        adrs = await generator_agent.generate_adrs(triggers)
        state.stage = "adr_generation"
        state.adr_number = adrs[0].number
        assert state.adr_number is not None

        # Phase 6
        request = hitl_service.create_approval_request(
            patch_id=f"patch-{state.threat_id}",
            vulnerability_id=critical_threat.cve_ids[0],
        )
        state.stage = "approval_pending"
        state.approval_id = request.approval_id
        assert state.approval_id is not None

        # Approve
        hitl_service.approve_request(
            state.approval_id,
            "reviewer@example.com",
            "Approved",
        )
        state.stage = "approved"
        state.final_status = "APPROVED"

        # Verify audit trail
        audit = hitl_service.get_audit_log()
        approved_entries = [e for e in audit if e["status"] == "APPROVED"]
        assert len(approved_entries) >= 1

    def test_approval_statistics(self, hitl_service):
        """Test approval statistics tracking."""
        # Create various requests
        for i in range(5):
            severity = PatchSeverity.CRITICAL if i < 2 else PatchSeverity.MEDIUM
            request = hitl_service.create_approval_request(
                patch_id=f"patch-{i}",
                vulnerability_id=f"CVE-2025-000{i}",
                severity=severity,
            )

            # Approve some, reject others
            if i < 3:
                hitl_service.approve_request(
                    request.approval_id,
                    "reviewer@example.com",
                    "Approved",
                )
            elif i < 4:
                hitl_service.reject_request(
                    request.approval_id,
                    "reviewer@example.com",
                    "Rejected for testing",
                )

        # Get statistics
        stats = hitl_service.get_statistics()

        assert stats["total_requests"] >= 5
        assert stats["approved"] >= 3
        assert stats["rejected"] >= 1
        assert stats["pending"] >= 1
        assert "by_severity" in stats


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestPipelineErrorHandling:
    """Tests for error handling throughout the pipeline."""

    @pytest.mark.asyncio
    async def test_invalid_threat_handling(self, adaptive_agent):
        """Test handling of invalid threat data."""
        # Create threat with minimal/invalid data
        invalid_threat = ThreatIntelReport(
            id="",  # Empty ID
            title="",  # Empty title
            category=ThreatCategory.CVE,
            severity=ThreatSeverity.LOW,
            source="Unknown",
            published_date=datetime.now(),
            description="",  # Empty description
        )

        # Should handle gracefully without crashing
        recommendations = await adaptive_agent.analyze_threats([invalid_threat])
        # May return empty list or minimal recommendation
        assert isinstance(recommendations, list)

    def test_nonexistent_approval_handling(self, hitl_service):
        """Test handling of non-existent approval IDs."""
        result = hitl_service.approve_request(
            approval_id="nonexistent-id",
            reviewer_id="reviewer@example.com",
            reason="Test",
        )

        assert result is False

    def test_duplicate_approval_handling(self, hitl_service):
        """Test handling of duplicate approval attempts."""
        request = hitl_service.create_approval_request(
            patch_id="patch-dup",
            vulnerability_id="CVE-DUP",
        )

        # First approval
        result1 = hitl_service.approve_request(
            request.approval_id,
            "reviewer1@example.com",
            "First approval",
        )
        assert result1 is True

        # Second approval attempt
        result2 = hitl_service.approve_request(
            request.approval_id,
            "reviewer2@example.com",
            "Second approval",
        )
        assert result2 is False


# ============================================================================
# Performance Tests
# ============================================================================


class TestPipelinePerformance:
    """Tests for pipeline performance characteristics."""

    @pytest.mark.asyncio
    async def test_batch_threat_processing(self, adaptive_agent, review_agent):
        """Test processing multiple threats in batch."""
        threats = [
            ThreatIntelReport(
                id=f"threat-batch-{i}",
                title=f"Batch Threat {i}",
                category=ThreatCategory.CVE,
                severity=ThreatSeverity.HIGH if i % 2 == 0 else ThreatSeverity.MEDIUM,
                source="NVD",
                published_date=datetime.now(),
                description=f"Batch threat description {i}",
                cve_ids=[f"CVE-2025-{i:04d}"],
            )
            for i in range(10)
        ]

        # Process all threats - agent filters based on severity
        recommendations = await adaptive_agent.analyze_threats(threats)

        # Agent generates recommendations for HIGH+ severity threats
        assert len(recommendations) >= 5  # At least the 5 HIGH severity threats

        # Review all recommendations
        triggers = review_agent.evaluate_recommendations(recommendations)

        # High severity should generate triggers
        assert len(triggers) >= 3

    def test_concurrent_approval_requests(self, hitl_service):
        """Test handling concurrent approval requests."""
        requests = []

        # Create multiple requests
        for i in range(20):
            request = hitl_service.create_approval_request(
                patch_id=f"patch-concurrent-{i}",
                vulnerability_id=f"CVE-CONC-{i}",
            )
            requests.append(request)

        # Verify all created
        assert len(requests) == 20

        # Approve half
        for i, request in enumerate(requests[:10]):
            result = hitl_service.approve_request(
                request.approval_id,
                "reviewer@example.com",
                f"Approved request {i}",
            )
            assert result is True

        # Verify statistics
        stats = hitl_service.get_statistics()
        assert stats["approved"] >= 10
        assert stats["pending"] >= 10
