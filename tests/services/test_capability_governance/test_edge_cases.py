"""
Extended edge case tests for capability governance services (ADR-066).

Tests additional edge cases and error paths not covered in main test files.
"""

import platform
from datetime import datetime, timedelta, timezone

import pytest

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.capability_governance.contracts import (
    ActionType,
    CapabilityApprovalResponse,
    CapabilityCheckResult,
    CapabilityContext,
    CapabilityDecision,
    CapabilityEscalationRequest,
    CapabilityScope,
    CapabilityViolation,
    DynamicCapabilityGrant,
    ExecutionContext,
    ToolCapability,
    ToolClassification,
)

# =============================================================================
# ToolClassification Edge Cases
# =============================================================================


class TestToolClassificationEdgeCases:
    """Test edge cases for ToolClassification enum."""

    def test_all_classifications_have_string_values(self):
        """Test all classifications have string values."""
        for classification in ToolClassification:
            assert isinstance(classification.value, str)
            assert len(classification.value) > 0

    def test_classification_values(self):
        """Test classification values are correct."""
        assert ToolClassification.SAFE.value == "safe"
        assert ToolClassification.MONITORING.value == "monitoring"
        assert ToolClassification.DANGEROUS.value == "dangerous"
        assert ToolClassification.CRITICAL.value == "critical"

    def test_classification_count(self):
        """Test there are exactly 4 classifications."""
        assert len(list(ToolClassification)) == 4


# =============================================================================
# CapabilityDecision Edge Cases
# =============================================================================


class TestCapabilityDecisionEdgeCases:
    """Test edge cases for CapabilityDecision enum."""

    def test_all_decisions_have_string_values(self):
        """Test all decisions have string values."""
        for decision in CapabilityDecision:
            assert isinstance(decision.value, str)
            assert len(decision.value) > 0

    def test_decision_values(self):
        """Test decision values are correct."""
        assert CapabilityDecision.ALLOW.value == "allow"
        assert CapabilityDecision.DENY.value == "deny"
        assert CapabilityDecision.ESCALATE.value == "escalate"
        assert CapabilityDecision.AUDIT_ONLY.value == "audit_only"


# =============================================================================
# CapabilityScope Edge Cases
# =============================================================================


class TestCapabilityScopeEdgeCases:
    """Test edge cases for CapabilityScope enum."""

    def test_all_scopes_have_string_values(self):
        """Test all scopes have string values."""
        for scope in CapabilityScope:
            assert isinstance(scope.value, str)
            assert len(scope.value) > 0

    def test_scope_values(self):
        """Test scope values are correct."""
        assert CapabilityScope.SINGLE_USE.value == "single_use"
        assert CapabilityScope.SESSION.value == "session"
        assert CapabilityScope.TASK_TREE.value == "task_tree"
        assert CapabilityScope.TIME_BOUNDED.value == "time_bounded"


# =============================================================================
# ExecutionContext Edge Cases
# =============================================================================


class TestExecutionContextEdgeCases:
    """Test edge cases for ExecutionContext enum."""

    def test_all_contexts_have_string_values(self):
        """Test all contexts have string values."""
        for context in ExecutionContext:
            assert isinstance(context.value, str)
            assert len(context.value) > 0

    def test_context_values(self):
        """Test context values are correct."""
        assert ExecutionContext.TEST.value == "test"
        assert ExecutionContext.SANDBOX.value == "sandbox"
        assert ExecutionContext.DEVELOPMENT.value == "development"
        assert ExecutionContext.STAGING.value == "staging"
        assert ExecutionContext.PRODUCTION.value == "production"


# =============================================================================
# ActionType Edge Cases
# =============================================================================


class TestActionTypeEdgeCases:
    """Test edge cases for ActionType enum."""

    def test_all_actions_have_string_values(self):
        """Test all action types have string values."""
        for action in ActionType:
            assert isinstance(action.value, str)
            assert len(action.value) > 0

    def test_action_values(self):
        """Test action values are correct."""
        assert ActionType.READ.value == "read"
        assert ActionType.WRITE.value == "write"
        assert ActionType.EXECUTE.value == "execute"
        assert ActionType.ADMIN.value == "admin"
        assert ActionType.DELETE.value == "delete"


# =============================================================================
# ToolCapability Edge Cases
# =============================================================================


class TestToolCapabilityEdgeCases:
    """Test edge cases for ToolCapability dataclass."""

    def test_tool_capability_minimal(self):
        """Test creating tool capability with minimal fields."""
        capability = ToolCapability(
            tool_name="test_tool",
            classification=ToolClassification.SAFE,
        )

        assert capability.tool_name == "test_tool"
        assert capability.classification == ToolClassification.SAFE
        assert capability.description == ""

    def test_tool_capability_with_description(self):
        """Test creating tool capability with description."""
        capability = ToolCapability(
            tool_name="dangerous_tool",
            classification=ToolClassification.DANGEROUS,
            description="A dangerous tool that modifies system state",
        )

        assert capability.description == "A dangerous tool that modifies system state"

    def test_tool_capability_with_all_fields(self):
        """Test creating tool capability with all fields."""
        capability = ToolCapability(
            tool_name="critical_tool",
            classification=ToolClassification.CRITICAL,
            description="Critical tool requiring HITL approval",
            requires_justification=True,
            allowed_actions=("read", "write"),
            rate_limit_per_minute=10,
            max_concurrent=2,
            audit_sample_rate=1.0,
            requires_context=("sandbox", "test"),
            blocked_contexts=("production",),
        )

        assert capability.requires_justification is True
        assert len(capability.allowed_actions) == 2
        assert capability.rate_limit_per_minute == 10
        assert capability.max_concurrent == 2

    def test_tool_capability_each_classification(self):
        """Test creating tool capability with each classification."""
        for classification in ToolClassification:
            capability = ToolCapability(
                tool_name=f"tool_{classification.value}",
                classification=classification,
            )
            assert capability.classification == classification

    def test_tool_capability_is_allowed_in_context(self):
        """Test context checking logic."""
        capability = ToolCapability(
            tool_name="sandbox_tool",
            classification=ToolClassification.DANGEROUS,
            requires_context=("sandbox", "test"),
            blocked_contexts=("production",),
        )

        assert capability.is_allowed_in_context("sandbox") is True
        assert capability.is_allowed_in_context("test") is True
        assert capability.is_allowed_in_context("production") is False
        assert capability.is_allowed_in_context("development") is False

    def test_tool_capability_is_action_allowed(self):
        """Test action checking logic."""
        capability = ToolCapability(
            tool_name="read_only_tool",
            classification=ToolClassification.SAFE,
            allowed_actions=("read",),
        )

        assert capability.is_action_allowed("read") is True
        assert capability.is_action_allowed("write") is False

    def test_tool_capability_wildcard_actions(self):
        """Test wildcard action allows all."""
        capability = ToolCapability(
            tool_name="admin_tool",
            classification=ToolClassification.CRITICAL,
            allowed_actions=("*",),
        )

        assert capability.is_action_allowed("read") is True
        assert capability.is_action_allowed("write") is True
        assert capability.is_action_allowed("delete") is True


# =============================================================================
# CapabilityCheckResult Edge Cases
# =============================================================================


class TestCapabilityCheckResultEdgeCases:
    """Test edge cases for CapabilityCheckResult dataclass."""

    def test_result_allowed(self):
        """Test allowed result."""
        result = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="read_file",
            agent_id="agent-123",
            agent_type="coder",
            action="read",
            context="development",
            reason="Agent has base capability",
            policy_version="v1.0",
            capability_source="base",
        )

        assert result.decision == CapabilityDecision.ALLOW
        assert result.tool_name == "read_file"
        assert result.is_allowed is True
        assert result.requires_hitl is False

    def test_result_denied(self):
        """Test denied result."""
        result = CapabilityCheckResult(
            decision=CapabilityDecision.DENY,
            tool_name="deploy",
            agent_id="agent-456",
            agent_type="coder",
            action="execute",
            context="production",
            reason="Agent not authorized for production deployment",
            policy_version="v1.0",
            capability_source="base",
        )

        assert result.decision == CapabilityDecision.DENY
        assert result.reason is not None
        assert result.is_allowed is False

    def test_result_escalated(self):
        """Test escalated result."""
        result = CapabilityCheckResult(
            decision=CapabilityDecision.ESCALATE,
            tool_name="critical_operation",
            agent_id="agent-789",
            agent_type="orchestrator",
            action="admin",
            context="production",
            reason="Critical operation requires HITL approval",
            policy_version="v1.0",
            capability_source="base",
        )

        assert result.decision == CapabilityDecision.ESCALATE
        assert result.requires_hitl is True
        assert result.is_allowed is False

    def test_result_audit_only(self):
        """Test audit only result."""
        result = CapabilityCheckResult(
            decision=CapabilityDecision.AUDIT_ONLY,
            tool_name="sensitive_read",
            agent_id="agent-001",
            agent_type="reviewer",
            action="read",
            context="staging",
            reason="Sensitive data access flagged for audit",
            policy_version="v1.0",
            capability_source="override",
        )

        assert result.decision == CapabilityDecision.AUDIT_ONLY
        assert result.is_allowed is True

    def test_result_to_audit_record(self):
        """Test audit record serialization."""
        result = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="tool",
            agent_id="agent",
            agent_type="coder",
            action="read",
            context="test",
            reason="Allowed",
            policy_version="v1.0",
            capability_source="base",
        )

        record = result.to_audit_record()
        assert record["decision"] == "allow"
        assert record["tool_name"] == "tool"
        assert "checked_at" in record


# =============================================================================
# CapabilityContext Edge Cases
# =============================================================================


class TestCapabilityContextEdgeCases:
    """Test edge cases for CapabilityContext dataclass."""

    def test_context_minimal(self):
        """Test context with minimal fields."""
        context = CapabilityContext(
            agent_id="agent-123",
            agent_type="coder",
            tool_name="read_file",
            action="read",
            execution_context="development",
        )

        assert context.agent_id == "agent-123"
        assert context.execution_context == "development"

    def test_context_with_session(self):
        """Test context with session information."""
        context = CapabilityContext(
            agent_id="agent-456",
            agent_type="reviewer",
            tool_name="write_file",
            action="write",
            execution_context="production",
            session_id="sess-12345",
        )

        assert context.session_id == "sess-12345"

    def test_context_with_all_optional_fields(self):
        """Test context with all optional fields."""
        context = CapabilityContext(
            agent_id="agent-789",
            agent_type="orchestrator",
            tool_name="deploy",
            action="execute",
            execution_context="sandbox",
            parent_agent_id="parent-001",
            execution_id="exec-123",
            session_id="sess-456",
            task_description="Deploy to sandbox",
            justification="Testing new feature",
        )

        assert context.parent_agent_id == "parent-001"
        assert context.execution_id == "exec-123"
        assert context.task_description == "Deploy to sandbox"

    def test_context_to_dict(self):
        """Test context serialization."""
        context = CapabilityContext(
            agent_id="agent-001",
            agent_type="coder",
            tool_name="tool",
            action="read",
            execution_context="test",
        )

        data = context.to_dict()
        assert data["agent_id"] == "agent-001"
        assert data["tool_name"] == "tool"


# =============================================================================
# DynamicCapabilityGrant Edge Cases
# =============================================================================


class TestDynamicCapabilityGrantEdgeCases:
    """Test edge cases for DynamicCapabilityGrant dataclass."""

    def _make_grant(self, **kwargs):
        """Helper to create grants with defaults."""
        defaults = {
            "grant_id": "grant-001",
            "agent_id": "agent-123",
            "tool_name": "deploy",
            "action": "execute",
            "scope": CapabilityScope.SESSION,
            "constraints": {},
            "granted_by": "request-123",
            "approver": "admin",
            "granted_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=4),
        }
        defaults.update(kwargs)
        return DynamicCapabilityGrant(**defaults)

    def test_grant_single_use(self):
        """Test single-use grant."""
        grant = self._make_grant(
            scope=CapabilityScope.SINGLE_USE,
            max_usage=1,
        )

        assert grant.scope == CapabilityScope.SINGLE_USE
        assert grant.max_usage == 1

    def test_grant_session_scope(self):
        """Test session-scoped grant."""
        grant = self._make_grant(
            scope=CapabilityScope.SESSION,
        )

        assert grant.scope == CapabilityScope.SESSION

    def test_grant_time_bounded(self):
        """Test time-bounded grant."""
        expires = datetime.now(timezone.utc) + timedelta(hours=4)
        grant = self._make_grant(
            scope=CapabilityScope.TIME_BOUNDED,
            expires_at=expires,
        )

        assert grant.scope == CapabilityScope.TIME_BOUNDED
        assert grant.expires_at is not None

    def test_grant_task_tree(self):
        """Test task-tree scoped grant."""
        grant = self._make_grant(
            scope=CapabilityScope.TASK_TREE,
        )

        assert grant.scope == CapabilityScope.TASK_TREE

    def test_grant_is_valid(self):
        """Test checking if grant is valid."""
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        grant = self._make_grant(expires_at=future)

        assert grant.is_valid is True

    def test_grant_expired_not_valid(self):
        """Test expired grant is not valid."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        grant = self._make_grant(expires_at=past)

        assert grant.is_valid is False

    def test_grant_revoked_not_valid(self):
        """Test revoked grant is not valid."""
        grant = self._make_grant(revoked=True)

        assert grant.is_valid is False

    def test_grant_max_usage_exceeded_not_valid(self):
        """Test grant exceeding max usage is not valid."""
        grant = self._make_grant(
            max_usage=5,
            usage_count=5,
        )

        assert grant.is_valid is False

    def test_grant_remaining_uses(self):
        """Test remaining uses calculation."""
        grant = self._make_grant(
            max_usage=10,
            usage_count=3,
        )

        assert grant.remaining_uses == 7

    def test_grant_remaining_uses_none(self):
        """Test remaining uses when no max set."""
        grant = self._make_grant(max_usage=None)

        assert grant.remaining_uses is None

    def test_grant_is_applicable(self):
        """Test grant applicability check."""
        grant = self._make_grant(
            tool_name="deploy",
            action="execute",
            context_restrictions=["sandbox", "staging"],
        )

        assert grant.is_applicable("deploy", "execute", "sandbox") is True
        assert grant.is_applicable("deploy", "execute", "production") is False
        assert grant.is_applicable("other_tool", "execute", "sandbox") is False

    def test_grant_to_dict(self):
        """Test grant serialization."""
        grant = self._make_grant()

        data = grant.to_dict()
        assert data["grant_id"] == "grant-001"
        assert data["scope"] == "session"


# =============================================================================
# CapabilityEscalationRequest Edge Cases
# =============================================================================


class TestCapabilityEscalationRequestEdgeCases:
    """Test edge cases for CapabilityEscalationRequest dataclass."""

    def test_escalation_request_basic(self):
        """Test basic escalation request."""
        request = CapabilityEscalationRequest(
            request_id="esc-001",
            agent_id="agent-123",
            agent_type="coder",
            requested_tool="critical_tool",
            requested_action="execute",
            context="production",
            justification="Need access for urgent fix",
            task_description="Fix critical bug in production",
        )

        assert request.request_id == "esc-001"
        assert request.justification is not None
        assert request.status == "pending"

    def test_escalation_request_with_expiry(self):
        """Test escalation request with expiry."""
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        request = CapabilityEscalationRequest(
            request_id="esc-002",
            agent_id="agent-456",
            agent_type="orchestrator",
            requested_tool="deploy_prod",
            requested_action="execute",
            context="production",
            justification="Production deployment",
            task_description="Deploy new version",
            expires_at=expires,
        )

        assert request.expires_at is not None
        assert request.is_expired is False

    def test_escalation_request_expired(self):
        """Test escalation request that expired."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        request = CapabilityEscalationRequest(
            request_id="esc-003",
            agent_id="agent-789",
            agent_type="coder",
            requested_tool="tool",
            requested_action="read",
            context="staging",
            justification="Test",
            task_description="Test task",
            expires_at=past,
        )

        assert request.is_expired is True
        assert request.is_pending is False

    def test_escalation_request_is_pending(self):
        """Test is_pending property."""
        request = CapabilityEscalationRequest(
            request_id="esc-004",
            agent_id="agent-001",
            agent_type="reviewer",
            requested_tool="tool",
            requested_action="write",
            context="development",
            justification="Test",
            task_description="Test",
            status="pending",
        )

        assert request.is_pending is True

    def test_escalation_request_approved_not_pending(self):
        """Test approved request is not pending."""
        request = CapabilityEscalationRequest(
            request_id="esc-005",
            agent_id="agent-002",
            agent_type="coder",
            requested_tool="tool",
            requested_action="read",
            context="test",
            justification="Test",
            task_description="Test",
            status="approved",
        )

        assert request.is_pending is False

    def test_escalation_request_to_dict(self):
        """Test serialization."""
        request = CapabilityEscalationRequest(
            request_id="esc-006",
            agent_id="agent-003",
            agent_type="coder",
            requested_tool="tool",
            requested_action="read",
            context="test",
            justification="Test",
            task_description="Test task",
        )

        data = request.to_dict()
        assert data["request_id"] == "esc-006"
        assert data["status"] == "pending"


# =============================================================================
# CapabilityApprovalResponse Edge Cases
# =============================================================================


class TestCapabilityApprovalResponseEdgeCases:
    """Test edge cases for CapabilityApprovalResponse dataclass."""

    def test_approval_granted(self):
        """Test approval granted response."""
        response = CapabilityApprovalResponse(
            request_id="esc-001",
            approved=True,
            approver_id="admin-123",
            scope=CapabilityScope.SESSION,
        )

        assert response.approved is True
        assert response.approver_id is not None

    def test_approval_denied(self):
        """Test approval denied response."""
        response = CapabilityApprovalResponse(
            request_id="esc-002",
            approved=False,
            approver_id="security-team",
            scope=CapabilityScope.SINGLE_USE,
            reason="Request does not meet security requirements",
        )

        assert response.approved is False
        assert response.reason is not None

    def test_approval_with_constraints(self):
        """Test approval with constraints."""
        response = CapabilityApprovalResponse(
            request_id="esc-003",
            approved=True,
            approver_id="ops-lead",
            scope=CapabilityScope.TIME_BOUNDED,
            constraints={"max_invocations": 10, "audit_all": True},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
        )

        assert len(response.constraints) == 2
        assert response.expires_at is not None

    def test_approval_to_dict(self):
        """Test serialization."""
        response = CapabilityApprovalResponse(
            request_id="esc-004",
            approved=True,
            approver_id="admin",
            scope=CapabilityScope.SESSION,
        )

        data = response.to_dict()
        assert data["request_id"] == "esc-004"
        assert data["scope"] == "session"


# =============================================================================
# CapabilityViolation Edge Cases
# =============================================================================


class TestCapabilityViolationEdgeCases:
    """Test edge cases for CapabilityViolation dataclass."""

    def test_violation_basic(self):
        """Test basic violation record."""
        violation = CapabilityViolation(
            violation_id="vio-001",
            agent_id="agent-123",
            agent_type="coder",
            tool_name="unauthorized_tool",
            action="execute",
            context="production",
            decision=CapabilityDecision.DENY,
            reason="Agent lacks capability",
        )

        assert violation.violation_id == "vio-001"
        assert violation.decision == CapabilityDecision.DENY

    def test_violation_with_optional_fields(self):
        """Test violation with optional fields."""
        violation = CapabilityViolation(
            violation_id="vio-002",
            agent_id="agent-456",
            agent_type="orchestrator",
            tool_name="deploy",
            action="execute",
            context="production",
            decision=CapabilityDecision.DENY,
            reason="Production deployment not allowed",
            parent_agent_id="parent-001",
            execution_id="exec-123",
            severity="critical",
        )

        assert violation.parent_agent_id == "parent-001"
        assert violation.severity == "critical"

    def test_violation_acknowledged(self):
        """Test acknowledged violation."""
        violation = CapabilityViolation(
            violation_id="vio-003",
            agent_id="agent-789",
            agent_type="reviewer",
            tool_name="tool",
            action="read",
            context="staging",
            decision=CapabilityDecision.DENY,
            reason="Test",
            acknowledged=True,
            acknowledged_by="security-team",
            acknowledged_at=datetime.now(timezone.utc),
        )

        assert violation.acknowledged is True
        assert violation.acknowledged_by is not None

    def test_violation_to_dict(self):
        """Test serialization."""
        violation = CapabilityViolation(
            violation_id="vio-004",
            agent_id="agent-001",
            agent_type="coder",
            tool_name="tool",
            action="write",
            context="test",
            decision=CapabilityDecision.DENY,
            reason="Not allowed",
        )

        data = violation.to_dict()
        assert data["violation_id"] == "vio-004"
        assert data["decision"] == "deny"
