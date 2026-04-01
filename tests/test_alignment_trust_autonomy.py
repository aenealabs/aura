"""
Tests for Trust-Based Autonomy Service (ADR-052 Phase 2).

Tests cover:
- AuthorizationDecision enum
- PermissionScope and related dataclasses
- AuthorizationRequest and AuthorizationResult
- OverrideRecord
- TrustBasedAutonomy authorization logic
"""

import platform
from datetime import datetime, timedelta, timezone

import pytest

from src.services.alignment.reversibility import ActionClass, ActionMetadata
from src.services.alignment.trust_autonomy import (
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorizationResult,
    OverrideRecord,
    PermissionScope,
    TrustBasedAutonomy,
)
from src.services.alignment.trust_calculator import AutonomyLevel, TrustScoreCalculator

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestAuthorizationDecision:
    """Tests for AuthorizationDecision enum."""

    def test_decision_values(self):
        """Test that decision values are defined."""
        assert AuthorizationDecision.APPROVED.value == "approved"
        assert AuthorizationDecision.REQUIRES_REVIEW.value == "requires_review"
        assert AuthorizationDecision.REQUIRES_APPROVAL.value == "requires_approval"
        assert AuthorizationDecision.DENIED.value == "denied"
        assert AuthorizationDecision.ESCALATED.value == "escalated"


class TestPermissionScope:
    """Tests for PermissionScope dataclass."""

    def test_creation(self):
        """Test creating a permission scope."""
        scope = PermissionScope(
            level=AutonomyLevel.EXECUTE_REVIEW,
            allowed_action_classes=[ActionClass.FULLY_REVERSIBLE],
            max_impact_scope="service",
            requires_review_for=[ActionClass.PARTIALLY_REVERSIBLE],
            can_affect_production=False,
            can_affect_external=False,
            max_concurrent_actions=5,
            rate_limit_per_hour=50,
        )
        assert scope.level == AutonomyLevel.EXECUTE_REVIEW
        assert ActionClass.FULLY_REVERSIBLE in scope.allowed_action_classes

    def test_to_dict(self):
        """Test dictionary conversion."""
        scope = PermissionScope(
            level=AutonomyLevel.RECOMMEND,
            allowed_action_classes=[],
            max_impact_scope="local",
            requires_review_for=[ActionClass.FULLY_REVERSIBLE],
            can_affect_production=False,
            can_affect_external=False,
            max_concurrent_actions=0,
            rate_limit_per_hour=100,
        )
        result = scope.to_dict()

        assert result["level"] == "RECOMMEND"
        assert result["max_impact_scope"] == "local"
        assert result["rate_limit_per_hour"] == 100


class TestAuthorizationResult:
    """Tests for AuthorizationResult dataclass."""

    def test_is_approved_true(self):
        """Test is_approved property when approved."""
        result = AuthorizationResult(
            request_id="req-1",
            decision=AuthorizationDecision.APPROVED,
            agent_id="agent-1",
            agent_autonomy_level=AutonomyLevel.AUTONOMOUS,
            agent_trust_score=0.8,
            action_class=ActionClass.FULLY_REVERSIBLE,
            reason="Approved",
        )
        assert result.is_approved is True
        assert result.requires_human is False

    def test_is_approved_false(self):
        """Test is_approved property when denied."""
        result = AuthorizationResult(
            request_id="req-1",
            decision=AuthorizationDecision.DENIED,
            agent_id="agent-1",
            agent_autonomy_level=AutonomyLevel.OBSERVE,
            agent_trust_score=0.1,
            action_class=ActionClass.IRREVERSIBLE,
            reason="Denied",
        )
        assert result.is_approved is False

    def test_requires_human_review(self):
        """Test requires_human for review."""
        result = AuthorizationResult(
            request_id="req-1",
            decision=AuthorizationDecision.REQUIRES_REVIEW,
            agent_id="agent-1",
            agent_autonomy_level=AutonomyLevel.RECOMMEND,
            agent_trust_score=0.4,
            action_class=ActionClass.PARTIALLY_REVERSIBLE,
            reason="Needs review",
        )
        assert result.requires_human is True

    def test_requires_human_approval(self):
        """Test requires_human for approval."""
        result = AuthorizationResult(
            request_id="req-1",
            decision=AuthorizationDecision.REQUIRES_APPROVAL,
            agent_id="agent-1",
            agent_autonomy_level=AutonomyLevel.EXECUTE_REVIEW,
            agent_trust_score=0.6,
            action_class=ActionClass.IRREVERSIBLE,
            reason="Needs approval",
        )
        assert result.requires_human is True

    def test_requires_human_escalated(self):
        """Test requires_human for escalated."""
        result = AuthorizationResult(
            request_id="req-1",
            decision=AuthorizationDecision.ESCALATED,
            agent_id="agent-1",
            agent_autonomy_level=AutonomyLevel.AUTONOMOUS,
            agent_trust_score=0.9,
            action_class=ActionClass.IRREVERSIBLE,
            reason="Escalated",
        )
        assert result.requires_human is True

    def test_to_dict(self):
        """Test dictionary conversion."""
        result = AuthorizationResult(
            request_id="req-1",
            decision=AuthorizationDecision.APPROVED,
            agent_id="agent-1",
            agent_autonomy_level=AutonomyLevel.AUTONOMOUS,
            agent_trust_score=0.85,
            action_class=ActionClass.FULLY_REVERSIBLE,
            reason="Approved",
            conditions=["Must log action"],
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        dict_result = result.to_dict()

        assert dict_result["request_id"] == "req-1"
        assert dict_result["decision"] == "approved"
        assert dict_result["agent_autonomy_level"] == "AUTONOMOUS"
        assert dict_result["is_approved"] is True
        assert dict_result["requires_human"] is False


class TestOverrideRecord:
    """Tests for OverrideRecord dataclass."""

    def test_creation(self):
        """Test creating an override record."""
        override = OverrideRecord(
            agent_id="agent-1",
            override_type="promotion",
            old_level=AutonomyLevel.OBSERVE,
            new_level=AutonomyLevel.AUTONOMOUS,
            reason="Emergency access",
            overridden_by="admin-user",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        assert override.agent_id == "agent-1"
        assert override.override_type == "promotion"
        assert override.is_active is True

    def test_to_dict(self):
        """Test dictionary conversion."""
        now = datetime.now(timezone.utc)
        override = OverrideRecord(
            agent_id="agent-1",
            override_type="demotion",
            old_level=AutonomyLevel.AUTONOMOUS,
            new_level=AutonomyLevel.OBSERVE,
            reason="Security concern",
            overridden_by="security-team",
        )
        result = override.to_dict()

        assert result["agent_id"] == "agent-1"
        assert result["override_type"] == "demotion"
        assert result["old_level"] == "AUTONOMOUS"
        assert result["new_level"] == "OBSERVE"
        assert result["is_active"] is True


class TestTrustBasedAutonomy:
    """Tests for TrustBasedAutonomy class."""

    @pytest.fixture
    def trust_calc(self):
        """Create a fresh trust calculator."""
        return TrustScoreCalculator()

    @pytest.fixture
    def autonomy(self, trust_calc):
        """Create a fresh autonomy service."""
        return TrustBasedAutonomy(trust_calculator=trust_calc)

    def _create_request(
        self,
        request_id: str = "req-1",
        agent_id: str = "agent-1",
        action_class: ActionClass = ActionClass.FULLY_REVERSIBLE,
        is_production: bool = False,
        affects_external: bool = False,
    ) -> AuthorizationRequest:
        """Create a test authorization request."""
        metadata = ActionMetadata(
            action_type="code_change",
            target_resource="/test/file.py",
            target_resource_type="file",
            is_production=is_production,
            affects_external_system=affects_external,
            estimated_impact_scope="local",
        )
        return AuthorizationRequest(
            request_id=request_id,
            agent_id=agent_id,
            action_metadata=metadata,
            action_class=action_class,
        )

    def test_initialization(self, autonomy):
        """Test autonomy service initialization."""
        assert autonomy.trust_calculator is not None
        assert len(autonomy.scopes) == 4  # One for each autonomy level

    def test_default_scopes(self, autonomy):
        """Test default permission scopes."""
        observe_scope = autonomy.scopes[AutonomyLevel.OBSERVE]
        assert observe_scope.allowed_action_classes == []
        assert observe_scope.max_concurrent_actions == 0

        autonomous_scope = autonomy.scopes[AutonomyLevel.AUTONOMOUS]
        assert ActionClass.FULLY_REVERSIBLE in autonomous_scope.allowed_action_classes
        assert autonomous_scope.can_affect_production is True

    def test_custom_scopes(self, trust_calc):
        """Test custom permission scopes."""
        custom_scope = PermissionScope(
            level=AutonomyLevel.OBSERVE,
            allowed_action_classes=[ActionClass.FULLY_REVERSIBLE],  # Override default
            max_impact_scope="local",
            requires_review_for=[],
            can_affect_production=False,
            can_affect_external=False,
            max_concurrent_actions=1,
            rate_limit_per_hour=10,
        )
        autonomy = TrustBasedAutonomy(
            trust_calculator=trust_calc,
            custom_scopes={AutonomyLevel.OBSERVE: custom_scope},
        )
        assert (
            ActionClass.FULLY_REVERSIBLE
            in autonomy.scopes[AutonomyLevel.OBSERVE].allowed_action_classes
        )

    def test_authorize_irreversible_always_requires_approval(
        self, autonomy, trust_calc
    ):
        """Test that irreversible actions always require approval."""
        # Even for AUTONOMOUS level
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        request = self._create_request(
            action_class=ActionClass.IRREVERSIBLE,
        )
        result = autonomy.authorize_action(request)

        assert result.decision == AuthorizationDecision.REQUIRES_APPROVAL
        assert result.requires_human is True
        assert "Irreversible" in result.reason

    def test_authorize_fully_reversible_by_autonomous(self, autonomy, trust_calc):
        """Test autonomous agent can execute fully reversible actions."""
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        request = self._create_request(
            action_class=ActionClass.FULLY_REVERSIBLE,
        )
        result = autonomy.authorize_action(request)

        assert result.decision == AuthorizationDecision.APPROVED
        assert result.is_approved is True
        assert result.expires_at is not None

    def test_authorize_requires_review_for_level(self, autonomy, trust_calc):
        """Test that action class in requires_review triggers review."""
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.EXECUTE_REVIEW, "Test", "admin"
        )

        request = self._create_request(
            action_class=ActionClass.PARTIALLY_REVERSIBLE,
        )
        result = autonomy.authorize_action(request)

        assert result.decision == AuthorizationDecision.REQUIRES_REVIEW
        assert result.requires_human is True

    def test_authorize_denied_action_class_not_allowed(self, autonomy, trust_calc):
        """Test denial when action class not allowed for level."""
        # RECOMMEND level has no allowed action classes
        trust_calc.set_manual_level("agent-1", AutonomyLevel.RECOMMEND, "Test", "admin")

        request = self._create_request(
            action_class=ActionClass.FULLY_REVERSIBLE,
        )
        result = autonomy.authorize_action(request)

        # Should require review since not in allowed_action_classes but in requires_review_for
        assert result.decision == AuthorizationDecision.REQUIRES_REVIEW

    def test_authorize_production_requires_approval(self, autonomy, trust_calc):
        """Test that production actions require approval for lower levels."""
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.EXECUTE_REVIEW, "Test", "admin"
        )

        request = self._create_request(
            action_class=ActionClass.FULLY_REVERSIBLE,
            is_production=True,
        )
        result = autonomy.authorize_action(request)

        # EXECUTE_REVIEW can't affect production without approval
        assert result.decision == AuthorizationDecision.REQUIRES_APPROVAL

    def test_authorize_external_requires_approval(self, autonomy, trust_calc):
        """Test that external system actions require approval."""
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        request = self._create_request(
            action_class=ActionClass.FULLY_REVERSIBLE,
            affects_external=True,
        )
        result = autonomy.authorize_action(request)

        # Even AUTONOMOUS can't affect external without approval
        assert result.decision == AuthorizationDecision.REQUIRES_APPROVAL

    def test_rate_limiting(self, trust_calc):
        """Test rate limiting."""
        autonomy = TrustBasedAutonomy(
            trust_calculator=trust_calc,
            enable_rate_limiting=True,
        )
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        # Make many requests to trigger rate limit
        # AUTONOMOUS has rate_limit_per_hour=100
        for i in range(100):
            request = self._create_request(request_id=f"req-{i}")
            result = autonomy.authorize_action(request)
            if (
                result.decision == AuthorizationDecision.DENIED
                and "Rate limit" in result.reason
            ):
                # Rate limit hit
                return

        # Try one more
        request = self._create_request(request_id="req-final")
        result = autonomy.authorize_action(request)
        assert result.decision == AuthorizationDecision.DENIED
        assert "Rate limit" in result.reason

    def test_rate_limiting_disabled(self, trust_calc):
        """Test with rate limiting disabled."""
        autonomy = TrustBasedAutonomy(
            trust_calculator=trust_calc,
            enable_rate_limiting=False,
        )
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        # Many requests should not hit rate limit
        for i in range(150):
            request = self._create_request(request_id=f"req-{i}")
            result = autonomy.authorize_action(request)
            assert "Rate limit" not in result.reason

    def test_grant_temporary_override(self, autonomy):
        """Test granting temporary override."""
        override = autonomy.grant_temporary_override(
            agent_id="agent-1",
            new_level=AutonomyLevel.AUTONOMOUS,
            reason="Emergency access needed",
            granted_by="admin-user",
            duration_hours=4,
        )

        assert override.agent_id == "agent-1"
        assert override.new_level == AutonomyLevel.AUTONOMOUS
        assert override.override_type == "promotion"
        assert override.is_active is True
        assert override.expires_at is not None

    def test_grant_temporary_demotion(self, autonomy, trust_calc):
        """Test granting temporary demotion."""
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Initial", "admin"
        )

        override = autonomy.grant_temporary_override(
            agent_id="agent-1",
            new_level=AutonomyLevel.OBSERVE,
            reason="Security concern",
            granted_by="security-team",
            duration_hours=24,
        )

        assert override.override_type == "demotion"

    def test_override_affects_authorization(self, autonomy, trust_calc):
        """Test that override affects authorization decisions."""
        # Agent starts at OBSERVE
        request = self._create_request(action_class=ActionClass.FULLY_REVERSIBLE)

        # Without override, should require review
        result1 = autonomy.authorize_action(request)
        assert result1.decision != AuthorizationDecision.APPROVED

        # Grant override
        autonomy.grant_temporary_override(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        # Now should be approved
        result2 = autonomy.authorize_action(request)
        assert result2.decision == AuthorizationDecision.APPROVED

    def test_override_expiration(self, autonomy):
        """Test that expired overrides are ignored."""
        # Create expired override
        override = autonomy.grant_temporary_override(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin", duration_hours=0
        )
        # Manually set expiration to past
        override.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        request = self._create_request(action_class=ActionClass.FULLY_REVERSIBLE)
        result = autonomy.authorize_action(request)

        # Override should be expired, so not APPROVED
        assert result.agent_autonomy_level != AutonomyLevel.AUTONOMOUS

    def test_revoke_override(self, autonomy):
        """Test revoking an override."""
        autonomy.grant_temporary_override(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        result = autonomy.revoke_override("agent-1", "security-team")
        assert result is True
        assert autonomy._overrides["agent-1"].is_active is False

    def test_revoke_override_not_found(self, autonomy):
        """Test revoking non-existent override."""
        result = autonomy.revoke_override("unknown-agent", "admin")
        assert result is False

    def test_get_agent_permissions(self, autonomy, trust_calc):
        """Test getting agent permissions."""
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.EXECUTE_REVIEW, "Test", "admin"
        )

        permissions = autonomy.get_agent_permissions("agent-1")

        assert permissions["agent_id"] == "agent-1"
        assert permissions["effective_level"] == "EXECUTE_REVIEW"
        assert "permissions" in permissions
        assert permissions["has_override"] is False

    def test_get_agent_permissions_with_override(self, autonomy):
        """Test getting agent permissions with override."""
        autonomy.grant_temporary_override(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        permissions = autonomy.get_agent_permissions("agent-1")

        assert permissions["has_override"] is True
        assert permissions["override"] is not None
        assert permissions["effective_level"] == "AUTONOMOUS"

    def test_get_authorization_history(self, autonomy, trust_calc):
        """Test getting authorization history."""
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        # Create some authorizations
        for i in range(5):
            request = self._create_request(request_id=f"req-{i}")
            autonomy.authorize_action(request)

        history = autonomy.get_authorization_history()
        assert len(history) == 5

    def test_get_authorization_history_filtered(self, autonomy, trust_calc):
        """Test filtering authorization history."""
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )
        trust_calc.set_manual_level(
            "agent-2", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        for i in range(3):
            request = self._create_request(request_id=f"req-a1-{i}", agent_id="agent-1")
            autonomy.authorize_action(request)
        for i in range(2):
            request = self._create_request(request_id=f"req-a2-{i}", agent_id="agent-2")
            autonomy.authorize_action(request)

        agent1_history = autonomy.get_authorization_history(agent_id="agent-1")
        assert len(agent1_history) == 3

        approved_history = autonomy.get_authorization_history(
            decision=AuthorizationDecision.APPROVED
        )
        assert len(approved_history) == 5

    def test_get_autonomy_stats_empty(self, autonomy):
        """Test stats with no authorizations."""
        stats = autonomy.get_autonomy_stats()
        assert stats["total_requests"] == 0

    def test_get_autonomy_stats(self, autonomy, trust_calc):
        """Test autonomy statistics."""
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        # Make some requests
        for i in range(5):
            request = self._create_request(
                request_id=f"req-{i}",
                action_class=ActionClass.FULLY_REVERSIBLE,
            )
            autonomy.authorize_action(request)

        # Make one that requires approval
        request = self._create_request(
            request_id="req-irrev",
            action_class=ActionClass.IRREVERSIBLE,
        )
        autonomy.authorize_action(request)

        stats = autonomy.get_autonomy_stats()
        assert stats["total_requests"] == 6
        assert "approved" in stats["decisions"]
        assert stats["approval_rate"] > 0

    def test_clear_history(self, autonomy, trust_calc):
        """Test clearing history."""
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        request = self._create_request()
        autonomy.authorize_action(request)
        autonomy.grant_temporary_override(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        autonomy.clear_history()

        assert len(autonomy._authorization_history) == 0
        assert len(autonomy._action_counts) == 0
        assert len(autonomy._overrides) == 0

    def test_escalation_path(self, autonomy):
        """Test escalation path generation."""
        path_observe = autonomy._get_escalation_path(AutonomyLevel.OBSERVE)
        assert "team_lead" in path_observe
        assert "security_review" in path_observe

        path_autonomous = autonomy._get_escalation_path(AutonomyLevel.AUTONOMOUS)
        assert "security_team" in path_autonomous

    def test_authorization_history_trimming(self, autonomy, trust_calc):
        """Test history trimming."""
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        for i in range(1100):
            request = self._create_request(request_id=f"req-{i}")
            autonomy.authorize_action(request)

        assert len(autonomy._authorization_history) <= 1000

    def test_authorization_ttl(self, trust_calc):
        """Test authorization TTL."""
        autonomy = TrustBasedAutonomy(
            trust_calculator=trust_calc,
            authorization_ttl_minutes=60,
        )
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        request = self._create_request()
        result = autonomy.authorize_action(request)

        assert result.expires_at is not None
        expected_expiry = datetime.now(timezone.utc) + timedelta(minutes=60)
        assert abs((result.expires_at - expected_expiry).total_seconds()) < 5

    def test_conditions_in_authorization(self, autonomy, trust_calc):
        """Test that conditions are included in authorization."""
        trust_calc.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        request = self._create_request(
            action_class=ActionClass.FULLY_REVERSIBLE,
            is_production=True,
        )
        # AUTONOMOUS can affect production
        # But let's test with a fully reversible action
        # First clear rate limit concerns
        autonomy.clear_history()

        request2 = self._create_request(
            action_class=ActionClass.FULLY_REVERSIBLE,
        )
        result = autonomy.authorize_action(request2)

        # Should have some conditions
        assert isinstance(result.conditions, list)
