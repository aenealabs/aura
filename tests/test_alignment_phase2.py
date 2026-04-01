"""
Tests for ADR-052 Phase 2 Alignment Enforcement Services.

Tests cover:
- SycophancyGuard: Anti-sycophancy pre-response validation
- TrustBasedAutonomy: Dynamic permission adjustment
- RollbackService: Snapshot and restore capabilities
- TransparencyMiddleware: Audit requirement enforcement
"""

import platform
from datetime import datetime, timedelta, timezone

import pytest

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestSycophancyGuard:
    """Tests for the SycophancyGuard service."""

    def test_guard_initialization(self):
        """Test guard initializes with defaults."""
        from src.services.alignment.sycophancy_guard import SycophancyGuard

        guard = SycophancyGuard()
        assert guard.min_disagreement_rate == 0.05
        assert guard.max_disagreement_rate == 0.15
        assert guard.max_confidence_error == 0.10
        assert guard.enable_auto_correction is False

    def test_guard_custom_thresholds(self):
        """Test guard with custom thresholds."""
        from src.services.alignment.sycophancy_guard import SycophancyGuard

        guard = SycophancyGuard(
            min_disagreement_rate=0.10,
            max_disagreement_rate=0.20,
            enable_auto_correction=True,
        )
        assert guard.min_disagreement_rate == 0.10
        assert guard.max_disagreement_rate == 0.20
        assert guard.enable_auto_correction is True

    def test_detect_flattery(self):
        """Test detection of flattery patterns."""
        from src.services.alignment.sycophancy_guard import (
            ResponseContext,
            ResponseSeverity,
            SycophancyGuard,
            SycophancyViolationType,
        )

        guard = SycophancyGuard()
        context = ResponseContext(
            response_text="That's a great question! You're absolutely right about this.",
            agent_id="test-agent",
            severity=ResponseSeverity.MEDIUM,
        )

        result = guard.validate_response(context)
        flattery_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.FLATTERY_DETECTED
        ]
        assert len(flattery_violations) >= 1

    def test_detect_hidden_uncertainty(self):
        """Test detection of hidden uncertainty."""
        from src.services.alignment.sycophancy_guard import (
            ResponseContext,
            ResponseSeverity,
            SycophancyGuard,
            SycophancyViolationType,
        )

        guard = SycophancyGuard()
        context = ResponseContext(
            response_text="This is definitely the correct approach without a doubt.",
            agent_id="test-agent",
            stated_confidence=0.5,  # Low confidence but certain language
            severity=ResponseSeverity.MEDIUM,
        )

        result = guard.validate_response(context)
        uncertainty_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.HIDDEN_UNCERTAINTY
        ]
        assert len(uncertainty_violations) >= 1

    def test_detect_missing_alternatives(self):
        """Test detection of missing alternatives for high-severity decisions."""
        from src.services.alignment.sycophancy_guard import (
            ResponseContext,
            ResponseSeverity,
            SycophancyGuard,
            SycophancyViolationType,
        )

        guard = SycophancyGuard()
        context = ResponseContext(
            response_text="A" * 300,  # Long response
            agent_id="test-agent",
            alternatives_presented=0,
            severity=ResponseSeverity.HIGH,
        )

        result = guard.validate_response(context)
        alt_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.MISSING_ALTERNATIVES
        ]
        assert len(alt_violations) >= 1

    def test_detect_suppressed_findings(self):
        """Test detection of suppressed negative findings."""
        from src.services.alignment.sycophancy_guard import (
            ResponseContext,
            ResponseSeverity,
            SycophancyGuard,
            SycophancyViolationType,
        )

        guard = SycophancyGuard()
        context = ResponseContext(
            response_text="Everything looks good.",
            agent_id="test-agent",
            negative_findings=["SQL injection vulnerability", "XSS risk"],
            negative_findings_reported=False,
            severity=ResponseSeverity.HIGH,
        )

        result = guard.validate_response(context)
        suppression_violations = [
            v
            for v in result.violations
            if v.violation_type == SycophancyViolationType.SUPPRESSED_NEGATIVE_FINDING
        ]
        assert len(suppression_violations) == 1
        assert suppression_violations[0].severity == "critical"

    def test_valid_response_passes(self):
        """Test that valid responses pass validation."""
        from src.services.alignment.sycophancy_guard import (
            ResponseContext,
            ResponseSeverity,
            SycophancyGuard,
        )

        guard = SycophancyGuard()
        context = ResponseContext(
            response_text="Based on analysis, there are concerns with the implementation.",
            agent_id="test-agent",
            stated_confidence=0.75,
            alternatives_presented=2,
            negative_findings=[],
            severity=ResponseSeverity.LOW,
        )

        result = guard.validate_response(context)
        assert result.is_valid

    def test_record_disagreement(self):
        """Test recording agent disagreements."""
        from src.services.alignment.sycophancy_guard import SycophancyGuard

        guard = SycophancyGuard()
        guard.record_disagreement("agent-1", disagreed=True)
        guard.record_disagreement("agent-1", disagreed=False)
        guard.record_disagreement("agent-1", disagreed=True)

        health = guard.get_agent_health("agent-1")
        # 2 disagreements out of 3 (but need more responses for rate calc)
        assert health["status"] == "unknown" or "metrics" in health

    def test_record_confidence_outcome(self):
        """Test recording confidence outcomes."""
        from src.services.alignment.sycophancy_guard import SycophancyGuard

        guard = SycophancyGuard()
        guard.record_confidence_outcome("agent-1", 0.8, was_correct=True)
        guard.record_confidence_outcome("agent-1", 0.9, was_correct=False)

        health = guard.get_agent_health("agent-1")
        assert "metrics" in health

    def test_get_agent_health_unknown_agent(self):
        """Test health check for unknown agent."""
        from src.services.alignment.sycophancy_guard import SycophancyGuard

        guard = SycophancyGuard()
        health = guard.get_agent_health("unknown-agent")
        assert health["status"] == "unknown"

    def test_get_validation_stats(self):
        """Test getting validation statistics."""
        from src.services.alignment.sycophancy_guard import (
            ResponseContext,
            ResponseSeverity,
            SycophancyGuard,
        )

        guard = SycophancyGuard()

        # Create some validations
        for i in range(5):
            context = ResponseContext(
                response_text=f"Response {i}",
                agent_id="test-agent",
                severity=ResponseSeverity.LOW,
            )
            guard.validate_response(context)

        stats = guard.get_validation_stats()
        assert stats["total_validations"] == 5

    def test_clear_agent_profile(self):
        """Test clearing an agent profile."""
        from src.services.alignment.sycophancy_guard import SycophancyGuard

        guard = SycophancyGuard()
        guard.record_disagreement("agent-1", True)
        assert guard.clear_agent_profile("agent-1") is True
        assert guard.clear_agent_profile("agent-1") is False  # Already cleared

    def test_clear_all(self):
        """Test clearing all data."""
        from src.services.alignment.sycophancy_guard import SycophancyGuard

        guard = SycophancyGuard()
        guard.record_disagreement("agent-1", True)
        guard.clear_all()
        assert guard.get_agent_health("agent-1")["status"] == "unknown"


class TestTrustBasedAutonomy:
    """Tests for the TrustBasedAutonomy service."""

    def test_autonomy_initialization(self):
        """Test autonomy service initializes correctly."""
        from src.services.alignment.trust_autonomy import TrustBasedAutonomy

        autonomy = TrustBasedAutonomy()
        assert autonomy.trust_calculator is not None
        assert len(autonomy.scopes) == 4  # Four autonomy levels

    def test_authorize_class_a_action(self):
        """Test authorization of fully reversible actions."""
        from src.services.alignment.reversibility import ActionClass, ActionMetadata
        from src.services.alignment.trust_autonomy import (
            AuthorizationDecision,
            AuthorizationRequest,
            TrustBasedAutonomy,
        )

        autonomy = TrustBasedAutonomy()

        # Build up trust first
        for _ in range(15):
            autonomy.trust_calculator.record_action_outcome(
                "agent-1", was_successful=True
            )

        request = AuthorizationRequest(
            request_id="req-1",
            agent_id="agent-1",
            action_metadata=ActionMetadata(
                action_type="code_change",
                target_resource="/path/to/file.py",
                target_resource_type="file",
            ),
            action_class=ActionClass.FULLY_REVERSIBLE,
        )

        result = autonomy.authorize_action(request)
        # Should be approved or require review depending on trust level
        assert result.decision in [
            AuthorizationDecision.APPROVED,
            AuthorizationDecision.REQUIRES_REVIEW,
        ]

    def test_authorize_class_c_requires_approval(self):
        """Test that irreversible actions always require approval."""
        from src.services.alignment.reversibility import ActionClass, ActionMetadata
        from src.services.alignment.trust_autonomy import (
            AuthorizationDecision,
            AuthorizationRequest,
            TrustBasedAutonomy,
        )

        autonomy = TrustBasedAutonomy()

        request = AuthorizationRequest(
            request_id="req-2",
            agent_id="agent-1",
            action_metadata=ActionMetadata(
                action_type="data_deletion",
                target_resource="users_table",
                target_resource_type="database",
                is_destructive=True,
            ),
            action_class=ActionClass.IRREVERSIBLE,
        )

        result = autonomy.authorize_action(request)
        assert result.decision == AuthorizationDecision.REQUIRES_APPROVAL
        assert result.requires_human is True

    def test_authorize_production_action(self):
        """Test authorization of production actions."""
        from src.services.alignment.reversibility import ActionClass, ActionMetadata
        from src.services.alignment.trust_autonomy import (
            AuthorizationDecision,
            AuthorizationRequest,
            TrustBasedAutonomy,
        )

        autonomy = TrustBasedAutonomy()

        request = AuthorizationRequest(
            request_id="req-3",
            agent_id="agent-1",
            action_metadata=ActionMetadata(
                action_type="deployment",
                target_resource="prod-service",
                target_resource_type="kubernetes",
                is_production=True,
            ),
            action_class=ActionClass.PARTIALLY_REVERSIBLE,
        )

        result = autonomy.authorize_action(request)
        # Production actions require approval or review
        assert result.decision in [
            AuthorizationDecision.REQUIRES_APPROVAL,
            AuthorizationDecision.REQUIRES_REVIEW,
        ]

    def test_rate_limiting(self):
        """Test rate limiting enforcement."""
        from src.services.alignment.reversibility import ActionClass, ActionMetadata
        from src.services.alignment.trust_autonomy import (
            AuthorizationDecision,
            AuthorizationRequest,
            TrustBasedAutonomy,
        )

        autonomy = TrustBasedAutonomy(enable_rate_limiting=True)

        # Build up trust to get to RECOMMEND level
        for _ in range(20):
            autonomy.trust_calculator.record_action_outcome(
                "agent-rate", was_successful=True
            )

        # Make many requests to exceed rate limit
        for i in range(150):
            request = AuthorizationRequest(
                request_id=f"req-{i}",
                agent_id="agent-rate",
                action_metadata=ActionMetadata(
                    action_type="read",
                    target_resource=f"/file-{i}",
                    target_resource_type="file",
                ),
                action_class=ActionClass.FULLY_REVERSIBLE,
            )
            result = autonomy.authorize_action(request)
            if result.decision == AuthorizationDecision.DENIED:
                assert "rate limit" in result.reason.lower()
                break

    def test_grant_temporary_override(self):
        """Test granting temporary autonomy override."""
        from src.services.alignment.trust_autonomy import TrustBasedAutonomy
        from src.services.alignment.trust_calculator import AutonomyLevel

        autonomy = TrustBasedAutonomy()

        override = autonomy.grant_temporary_override(
            agent_id="agent-override",
            new_level=AutonomyLevel.AUTONOMOUS,
            reason="Emergency maintenance",
            granted_by="admin-user",
            duration_hours=2,
        )

        assert override.new_level == AutonomyLevel.AUTONOMOUS
        assert override.is_active is True
        assert override.expires_at is not None

        # Check permissions reflect override
        permissions = autonomy.get_agent_permissions("agent-override")
        assert permissions["has_override"] is True
        assert permissions["effective_level"] == "AUTONOMOUS"

    def test_revoke_override(self):
        """Test revoking an override."""
        from src.services.alignment.trust_autonomy import TrustBasedAutonomy
        from src.services.alignment.trust_calculator import AutonomyLevel

        autonomy = TrustBasedAutonomy()

        autonomy.grant_temporary_override(
            agent_id="agent-revoke",
            new_level=AutonomyLevel.AUTONOMOUS,
            reason="Testing",
            granted_by="admin",
        )

        assert autonomy.revoke_override("agent-revoke", "admin") is True
        assert autonomy.revoke_override("agent-revoke", "admin") is False

    def test_get_authorization_history(self):
        """Test getting authorization history."""
        from src.services.alignment.reversibility import ActionClass, ActionMetadata
        from src.services.alignment.trust_autonomy import (
            AuthorizationRequest,
            TrustBasedAutonomy,
        )

        autonomy = TrustBasedAutonomy()

        for i in range(5):
            request = AuthorizationRequest(
                request_id=f"hist-req-{i}",
                agent_id="agent-hist",
                action_metadata=ActionMetadata(
                    action_type="read",
                    target_resource=f"/file-{i}",
                    target_resource_type="file",
                ),
                action_class=ActionClass.FULLY_REVERSIBLE,
            )
            autonomy.authorize_action(request)

        history = autonomy.get_authorization_history(agent_id="agent-hist", limit=10)
        assert len(history) == 5

    def test_get_autonomy_stats(self):
        """Test getting autonomy statistics."""
        from src.services.alignment.reversibility import ActionClass, ActionMetadata
        from src.services.alignment.trust_autonomy import (
            AuthorizationRequest,
            TrustBasedAutonomy,
        )

        autonomy = TrustBasedAutonomy()

        for i in range(3):
            request = AuthorizationRequest(
                request_id=f"stat-req-{i}",
                agent_id="agent-stats",
                action_metadata=ActionMetadata(
                    action_type="read",
                    target_resource=f"/file-{i}",
                    target_resource_type="file",
                ),
                action_class=ActionClass.FULLY_REVERSIBLE,
            )
            autonomy.authorize_action(request)

        stats = autonomy.get_autonomy_stats()
        assert stats["total_requests"] == 3
        assert "decisions" in stats

    def test_clear_history(self):
        """Test clearing history."""
        from src.services.alignment.trust_autonomy import TrustBasedAutonomy

        autonomy = TrustBasedAutonomy()
        autonomy.clear_history()
        stats = autonomy.get_autonomy_stats()
        assert stats["total_requests"] == 0


class TestRollbackService:
    """Tests for the RollbackService."""

    def test_service_initialization(self):
        """Test rollback service initializes correctly."""
        from src.services.alignment.rollback_service import RollbackService

        service = RollbackService()
        assert service.max_snapshots == 10000
        assert service.max_plans == 5000

    def test_create_snapshot(self):
        """Test creating a state snapshot."""
        from src.services.alignment.rollback_service import RollbackService

        service = RollbackService()
        snapshot = service.create_snapshot(
            action_id="act-1",
            resource_type="file",
            resource_id="/path/to/file.py",
            state_data={"content": "original content"},
        )

        assert snapshot.action_id == "act-1"
        assert snapshot.resource_type == "file"
        assert snapshot.checksum != ""

    def test_create_file_snapshot(self):
        """Test creating a file content snapshot."""
        from src.services.alignment.rollback_service import RollbackService

        service = RollbackService()
        snapshot = service.create_file_snapshot(
            action_id="act-2",
            file_path="/path/to/file.py",
            content="def hello(): pass",
        )

        assert snapshot.resource_type == "file"
        assert snapshot.state_data["content"] == "def hello(): pass"

    def test_create_config_snapshot(self):
        """Test creating a configuration snapshot."""
        from src.services.alignment.rollback_service import RollbackService

        service = RollbackService()
        snapshot = service.create_config_snapshot(
            action_id="act-3",
            config_key="max_connections",
            config_value=100,
        )

        assert snapshot.resource_type == "config"
        assert snapshot.state_data["value"] == 100

    def test_get_snapshot(self):
        """Test retrieving a snapshot."""
        from src.services.alignment.rollback_service import RollbackService

        service = RollbackService()
        created = service.create_snapshot(
            action_id="act-4",
            resource_type="test",
            resource_id="test-resource",
            state_data={"key": "value"},
        )

        retrieved = service.get_snapshot(created.snapshot_id)
        assert retrieved is not None
        assert retrieved.snapshot_id == created.snapshot_id

    def test_get_snapshots_for_action(self):
        """Test retrieving all snapshots for an action."""
        from src.services.alignment.rollback_service import RollbackService

        service = RollbackService()

        # Create multiple snapshots for same action
        for i in range(3):
            service.create_snapshot(
                action_id="act-multi",
                resource_type="file",
                resource_id=f"/file-{i}",
                state_data={"index": i},
            )

        snapshots = service.get_snapshots_for_action("act-multi")
        assert len(snapshots) == 3

    def test_store_rollback_plan(self):
        """Test storing a rollback plan."""
        from src.services.alignment.reversibility import RollbackPlan
        from src.services.alignment.rollback_service import RollbackService

        service = RollbackService()
        plan = RollbackPlan(
            plan_id="plan-1",
            action_id="act-plan",
            steps=[
                {"step": 1, "action": "restore_backup"},
                {"step": 2, "action": "verify_data"},
            ],
            estimated_duration_seconds=300,
        )

        service.store_rollback_plan("act-plan", plan)

        retrieved = service.get_rollback_plan("act-plan")
        assert retrieved is not None
        assert retrieved.plan_id == "plan-1"

    def test_get_rollback_capability(self):
        """Test checking rollback capability."""
        from src.services.alignment.rollback_service import RollbackService

        service = RollbackService()
        service.create_snapshot(
            action_id="act-cap",
            resource_type="file",
            resource_id="/test.py",
            state_data={"content": "test"},
        )

        capability = service.get_rollback_capability("act-cap")
        assert capability.can_rollback is True
        assert capability.snapshot_available is True

    def test_execute_rollback_with_snapshot(self):
        """Test executing rollback from snapshot."""
        from src.services.alignment.rollback_service import (
            RollbackService,
            RollbackStatus,
        )

        service = RollbackService()
        snapshot = service.create_snapshot(
            action_id="act-rollback",
            resource_type="file",
            resource_id="/test.py",
            state_data={"content": "original"},
        )

        # Mock restore function
        restored_data = {}

        def restore_fn(snap):
            restored_data["content"] = snap.state_data["content"]
            return True

        execution = service.execute_rollback(
            action_id="act-rollback",
            restore_fn=restore_fn,
            initiated_by="test-user",
        )

        assert execution.status == RollbackStatus.COMPLETED
        assert restored_data["content"] == "original"

    def test_execute_rollback_no_snapshot(self):
        """Test rollback fails gracefully without snapshot."""
        from src.services.alignment.rollback_service import (
            RollbackService,
            RollbackStatus,
        )

        service = RollbackService()
        execution = service.execute_rollback(
            action_id="nonexistent-action",
            restore_fn=lambda s: True,
        )

        assert execution.status == RollbackStatus.FAILED
        assert "No snapshot" in execution.error_message

    def test_cleanup_expired(self):
        """Test cleanup of expired snapshots."""
        from src.services.alignment.rollback_service import RollbackService

        service = RollbackService()

        # Create a snapshot that's already expired
        snapshot = service.create_snapshot(
            action_id="act-expired",
            resource_type="test",
            resource_id="test",
            state_data={},
            ttl_hours=-1,  # Already expired
        )

        # Manually set expiration in the past
        service._snapshots[snapshot.snapshot_id].expires_at = datetime.now(
            timezone.utc
        ) - timedelta(hours=1)

        cleaned = service.cleanup_expired()
        assert cleaned >= 1

    def test_get_stats(self):
        """Test getting service statistics."""
        from src.services.alignment.rollback_service import RollbackService

        service = RollbackService()
        service.create_snapshot(
            action_id="act-stats",
            resource_type="test",
            resource_id="test",
            state_data={},
        )

        stats = service.get_stats()
        assert stats["total_snapshots"] >= 1
        assert "snapshot_types" in stats

    def test_get_execution_history(self):
        """Test getting execution history."""
        from src.services.alignment.rollback_service import RollbackService

        service = RollbackService()
        service.create_snapshot(
            action_id="act-hist",
            resource_type="test",
            resource_id="test",
            state_data={},
        )
        service.execute_rollback("act-hist", restore_fn=lambda s: True)

        history = service.get_execution_history(action_id="act-hist")
        assert len(history) >= 1

    def test_clear_all(self):
        """Test clearing all data."""
        from src.services.alignment.rollback_service import RollbackService

        service = RollbackService()
        service.create_snapshot(
            action_id="act-clear",
            resource_type="test",
            resource_id="test",
            state_data={},
        )
        service.clear_all()

        stats = service.get_stats()
        assert stats["total_snapshots"] == 0


class TestTransparencyMiddleware:
    """Tests for the TransparencyMiddleware."""

    def test_middleware_initialization(self):
        """Test middleware initializes with defaults."""
        from src.middleware.transparency import TransparencyMiddleware

        middleware = TransparencyMiddleware()
        assert middleware.config.require_reasoning_chain is True
        assert middleware.config.require_confidence_score is True

    def test_middleware_custom_config(self):
        """Test middleware with custom config."""
        from src.middleware.transparency import (
            TransparencyConfig,
            TransparencyMiddleware,
        )

        config = TransparencyConfig(
            require_reasoning_chain=False,
            min_reasoning_steps=3,
        )
        middleware = TransparencyMiddleware(config=config)
        assert middleware.config.require_reasoning_chain is False
        assert middleware.config.min_reasoning_steps == 3

    def test_create_context(self):
        """Test creating a decision context."""
        from src.middleware.transparency import TransparencyMiddleware

        middleware = TransparencyMiddleware()
        context = middleware.create_context(
            agent_id="test-agent",
            decision_type="security_review",
            severity="high",
            summary="Reviewing authentication module",
        )

        assert context.agent_id == "test-agent"
        assert context.decision_type == "security_review"
        assert context.severity == "high"

    def test_add_reasoning_step(self):
        """Test adding reasoning steps."""
        from src.middleware.transparency import TransparencyMiddleware

        middleware = TransparencyMiddleware()
        context = middleware.create_context(
            agent_id="test-agent",
            decision_type="analysis",
            severity="medium",
            summary="Code analysis",
        )

        middleware.add_reasoning_step(context, 1, "Analyzed imports")
        middleware.add_reasoning_step(context, 2, "Checked for vulnerabilities")

        assert len(context.reasoning_steps) == 2

    def test_set_confidence(self):
        """Test setting confidence score."""
        from src.middleware.transparency import TransparencyMiddleware

        middleware = TransparencyMiddleware()
        context = middleware.create_context(
            agent_id="test-agent",
            decision_type="analysis",
            severity="medium",
            summary="Test",
        )

        middleware.set_confidence(context, 0.85)
        assert context.confidence_score == 0.85

        # Test clamping
        middleware.set_confidence(context, 1.5)
        assert context.confidence_score == 1.0

    def test_add_alternative(self):
        """Test adding alternatives."""
        from src.middleware.transparency import TransparencyMiddleware

        middleware = TransparencyMiddleware()
        context = middleware.create_context(
            agent_id="test-agent",
            decision_type="recommendation",
            severity="high",
            summary="Recommending fix",
        )

        middleware.add_alternative(
            context,
            option_id="opt-1",
            description="Use parameterized queries",
            confidence=0.9,
            pros=["Secure", "Standard"],
            cons=["Requires refactoring"],
            was_chosen=True,
        )
        middleware.add_alternative(
            context,
            option_id="opt-2",
            description="Input sanitization",
            confidence=0.7,
        )

        assert len(context.alternatives) == 2

    def test_validate_compliant_decision(self):
        """Test validation of a compliant decision."""
        from src.middleware.transparency import TransparencyMiddleware

        middleware = TransparencyMiddleware()
        context = middleware.create_context(
            agent_id="test-agent",
            decision_type="review",
            severity="low",
            summary="Code review",
        )

        middleware.add_reasoning_step(context, 1, "Step 1")
        middleware.add_reasoning_step(context, 2, "Step 2")
        middleware.set_confidence(context, 0.8)
        middleware.add_source(context, "file.py:42")

        result = middleware.validate(context)
        assert result.is_compliant is True
        assert len(result.violations) == 0

    def test_validate_missing_reasoning(self):
        """Test validation fails with missing reasoning."""
        from src.middleware.transparency import AuditRequirement, TransparencyMiddleware

        middleware = TransparencyMiddleware()
        context = middleware.create_context(
            agent_id="test-agent",
            decision_type="review",
            severity="medium",
            summary="Review",
        )

        middleware.set_confidence(context, 0.8)
        # No reasoning steps added

        result = middleware.validate(context)
        assert result.is_compliant is False
        reasoning_violations = [
            v
            for v in result.violations
            if v.requirement == AuditRequirement.REASONING_CHAIN
        ]
        assert len(reasoning_violations) >= 1

    def test_validate_missing_confidence(self):
        """Test validation fails with missing confidence."""
        from src.middleware.transparency import AuditRequirement, TransparencyMiddleware

        middleware = TransparencyMiddleware()
        context = middleware.create_context(
            agent_id="test-agent",
            decision_type="review",
            severity="medium",
            summary="Review",
        )

        middleware.add_reasoning_step(context, 1, "Step 1")
        middleware.add_reasoning_step(context, 2, "Step 2")
        # No confidence set

        result = middleware.validate(context)
        confidence_violations = [
            v
            for v in result.violations
            if v.requirement == AuditRequirement.CONFIDENCE_SCORE
        ]
        assert len(confidence_violations) >= 1

    def test_validate_high_severity_requires_alternatives(self):
        """Test that high severity decisions require alternatives."""
        from src.middleware.transparency import AuditRequirement, TransparencyMiddleware

        middleware = TransparencyMiddleware()
        context = middleware.create_context(
            agent_id="test-agent",
            decision_type="recommendation",
            severity="high",
            summary="Security fix",
        )

        middleware.add_reasoning_step(context, 1, "Step 1")
        middleware.add_reasoning_step(context, 2, "Step 2")
        middleware.set_confidence(context, 0.8)
        middleware.add_source(context, "CVE-2024-1234")
        # No alternatives added

        result = middleware.validate(context)
        alt_violations = [
            v
            for v in result.violations
            if v.requirement == AuditRequirement.ALTERNATIVES
        ]
        assert len(alt_violations) >= 1

    def test_validate_blocking(self):
        """Test that blocking works when configured."""
        from src.middleware.transparency import (
            TransparencyConfig,
            TransparencyMiddleware,
        )

        config = TransparencyConfig(block_on_violation=True)
        middleware = TransparencyMiddleware(config=config)

        context = middleware.create_context(
            agent_id="test-agent",
            decision_type="review",
            severity="medium",
            summary="Review",
        )
        # Missing everything

        result = middleware.validate(context)
        assert result.blocked is True
        assert result.block_reason is not None

    def test_violation_callback(self):
        """Test violation callback is called."""
        from src.middleware.transparency import TransparencyMiddleware

        violations_received = []

        def on_violation(v):
            violations_received.append(v)

        middleware = TransparencyMiddleware(on_violation=on_violation)
        context = middleware.create_context(
            agent_id="test-agent",
            decision_type="review",
            severity="medium",
            summary="Review",
        )

        middleware.validate(context)
        assert len(violations_received) > 0

    def test_get_agent_stats(self):
        """Test getting agent statistics."""
        from src.middleware.transparency import TransparencyMiddleware

        middleware = TransparencyMiddleware()

        for i in range(3):
            context = middleware.create_context(
                agent_id="stats-agent",
                decision_type="review",
                severity="low",
                summary=f"Review {i}",
            )
            middleware.add_reasoning_step(context, 1, "Step")
            middleware.add_reasoning_step(context, 2, "Step")
            middleware.set_confidence(context, 0.8)
            middleware.add_source(context, "source")
            middleware.validate(context)

        stats = middleware.get_agent_stats("stats-agent")
        assert stats["total_decisions"] == 3
        assert stats["compliance_rate"] == 1.0

    def test_get_overall_stats(self):
        """Test getting overall statistics."""
        from src.middleware.transparency import TransparencyMiddleware

        middleware = TransparencyMiddleware()
        context = middleware.create_context(
            agent_id="test-agent",
            decision_type="review",
            severity="low",
            summary="Test",
        )
        middleware.add_reasoning_step(context, 1, "Step")
        middleware.add_reasoning_step(context, 2, "Step")
        middleware.set_confidence(context, 0.8)
        middleware.add_source(context, "source")
        middleware.validate(context)

        stats = middleware.get_overall_stats()
        assert stats["total_decisions"] >= 1

    def test_get_validation_history(self):
        """Test getting validation history."""
        from src.middleware.transparency import TransparencyMiddleware

        middleware = TransparencyMiddleware()

        for i in range(5):
            context = middleware.create_context(
                agent_id="hist-agent",
                decision_type="review",
                severity="low",
                summary=f"Review {i}",
            )
            middleware.add_reasoning_step(context, 1, "Step")
            middleware.add_reasoning_step(context, 2, "Step")
            middleware.set_confidence(context, 0.8)
            middleware.add_source(context, "source")
            middleware.validate(context)

        history = middleware.get_validation_history(agent_id="hist-agent", limit=10)
        assert len(history) == 5

    def test_clear_history(self):
        """Test clearing history."""
        from src.middleware.transparency import TransparencyMiddleware

        middleware = TransparencyMiddleware()
        context = middleware.create_context(
            agent_id="test-agent",
            decision_type="review",
            severity="low",
            summary="Test",
        )
        middleware.validate(context)

        middleware.clear_history()
        stats = middleware.get_overall_stats()
        assert stats["total_decisions"] == 0


class TestPhase2PackageExports:
    """Tests for Phase 2 package exports."""

    def test_sycophancy_guard_exports(self):
        """Test sycophancy guard exports from package."""
        from src.services.alignment import (
            AgentSycophancyProfile,
            ResponseContext,
            ResponseSeverity,
            SycophancyGuard,
            SycophancyViolation,
            SycophancyViolationType,
            ValidationResult,
        )

        assert SycophancyGuard is not None
        assert SycophancyViolation is not None
        assert SycophancyViolationType is not None
        assert ValidationResult is not None
        assert ResponseContext is not None
        assert ResponseSeverity is not None
        assert AgentSycophancyProfile is not None

    def test_trust_autonomy_exports(self):
        """Test trust autonomy exports from package."""
        from src.services.alignment import (
            AuthorizationDecision,
            AuthorizationRequest,
            AuthorizationResult,
            OverrideRecord,
            PermissionScope,
            TrustBasedAutonomy,
        )

        assert TrustBasedAutonomy is not None
        assert AuthorizationDecision is not None
        assert AuthorizationRequest is not None
        assert AuthorizationResult is not None
        assert PermissionScope is not None
        assert OverrideRecord is not None

    def test_rollback_service_exports(self):
        """Test rollback service exports from package."""
        from src.services.alignment import (
            RollbackCapability,
            RollbackExecution,
            RollbackService,
            RollbackStatus,
            SnapshotType,
        )

        assert RollbackService is not None
        assert RollbackExecution is not None
        assert RollbackStatus is not None
        assert RollbackCapability is not None
        assert SnapshotType is not None

    def test_middleware_exports(self):
        """Test middleware package exports."""
        from src.middleware import (
            AuditRequirement,
            AuditViolation,
            TransparencyConfig,
            TransparencyMiddleware,
            TransparencyResult,
        )

        assert TransparencyMiddleware is not None
        assert TransparencyConfig is not None
        assert TransparencyResult is not None
        assert AuditRequirement is not None
        assert AuditViolation is not None


class TestPhase2Integration:
    """Integration tests for Phase 2 services working together."""

    def test_sycophancy_guard_with_trust(self):
        """Test sycophancy guard integrates with trust calculator."""
        from src.services.alignment import (
            ResponseContext,
            ResponseSeverity,
            SycophancyGuard,
            TrustScoreCalculator,
        )

        guard = SycophancyGuard()
        trust = TrustScoreCalculator()

        # Validate response
        context = ResponseContext(
            response_text="Analysis complete. Found 2 issues.",
            agent_id="integrated-agent",
            stated_confidence=0.75,
            alternatives_presented=2,
            severity=ResponseSeverity.MEDIUM,
        )

        result = guard.validate_response(context)

        # Record outcome based on validation
        if result.is_valid:
            trust.record_action_outcome("integrated-agent", was_successful=True)
        else:
            trust.record_action_outcome("integrated-agent", was_successful=False)

        record = trust.get_or_create_agent("integrated-agent")
        assert record.trust_score > 0

    def test_trust_autonomy_with_rollback(self):
        """Test trust autonomy integrates with rollback service."""
        from src.services.alignment import (
            ActionClass,
            ActionMetadata,
            RollbackService,
            TrustBasedAutonomy,
        )
        from src.services.alignment.trust_autonomy import AuthorizationRequest

        autonomy = TrustBasedAutonomy()
        rollback = RollbackService()

        # Get authorization
        request = AuthorizationRequest(
            request_id="int-req-1",
            agent_id="int-agent",
            action_metadata=ActionMetadata(
                action_type="code_change",
                target_resource="/file.py",
                target_resource_type="file",
            ),
            action_class=ActionClass.FULLY_REVERSIBLE,
        )

        auth_result = autonomy.authorize_action(request)

        # If approved, create snapshot before action
        if auth_result.is_approved:
            snapshot = rollback.create_file_snapshot(
                action_id="int-req-1",
                file_path="/file.py",
                content="original content",
            )
            assert snapshot is not None

        # Verify rollback is possible
        capability = rollback.get_rollback_capability("int-req-1")
        if auth_result.is_approved:
            assert capability.snapshot_available is True

    def test_transparency_with_sycophancy(self):
        """Test transparency middleware works with sycophancy guard."""
        from src.middleware import TransparencyMiddleware
        from src.services.alignment import (
            ResponseContext,
            ResponseSeverity,
            SycophancyGuard,
        )

        middleware = TransparencyMiddleware()
        guard = SycophancyGuard()

        # Create transparent context
        context = middleware.create_context(
            agent_id="full-stack-agent",
            decision_type="security_review",
            severity="high",
            summary="Reviewing authentication",
        )

        middleware.add_reasoning_step(context, 1, "Analyzed auth flow")
        middleware.add_reasoning_step(context, 2, "Identified weak points")
        middleware.set_confidence(context, 0.85)
        middleware.add_alternative(context, "opt-1", "JWT tokens", 0.9)
        middleware.add_alternative(context, "opt-2", "Session cookies", 0.7)
        middleware.add_source(context, "auth.py:45")
        middleware.add_uncertainty(context, "Legacy code patterns unclear")

        # Validate transparency
        trans_result = middleware.validate(context)
        assert trans_result.is_compliant is True

        # Validate response against sycophancy
        response_context = ResponseContext(
            response_text="Found potential issues. Consider using JWT tokens for better security.",
            agent_id="full-stack-agent",
            stated_confidence=0.85,
            alternatives_presented=2,
            negative_findings=["Weak password hashing"],
            negative_findings_reported=True,
            severity=ResponseSeverity.HIGH,
        )

        syc_result = guard.validate_response(response_context)
        assert syc_result.is_valid is True
