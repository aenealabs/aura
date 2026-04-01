"""
Tests for capability governance contracts module.

Tests all enums, dataclasses, and data contracts.
"""

from datetime import datetime, timedelta, timezone

import pytest

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
# Enum Tests
# =============================================================================


class TestCapabilityDecision:
    """Tests for CapabilityDecision enum."""

    def test_all_values_exist(self):
        """Verify all decision values exist."""
        assert CapabilityDecision.ALLOW.value == "allow"
        assert CapabilityDecision.DENY.value == "deny"
        assert CapabilityDecision.ESCALATE.value == "escalate"
        assert CapabilityDecision.AUDIT_ONLY.value == "audit_only"

    def test_enum_count(self):
        """Verify correct number of decisions."""
        assert len(CapabilityDecision) == 4

    def test_string_conversion(self):
        """Test string conversion."""
        assert str(CapabilityDecision.ALLOW) == "CapabilityDecision.ALLOW"

    def test_value_lookup(self):
        """Test value lookup."""
        assert CapabilityDecision("allow") == CapabilityDecision.ALLOW
        assert CapabilityDecision("deny") == CapabilityDecision.DENY


class TestToolClassification:
    """Tests for ToolClassification enum."""

    def test_all_values_exist(self):
        """Verify all classification values exist."""
        assert ToolClassification.SAFE.value == "safe"
        assert ToolClassification.MONITORING.value == "monitoring"
        assert ToolClassification.DANGEROUS.value == "dangerous"
        assert ToolClassification.CRITICAL.value == "critical"

    def test_enum_count(self):
        """Verify correct number of classifications."""
        assert len(ToolClassification) == 4

    def test_ordering(self):
        """Test that classifications can be compared."""
        # Enums are compared by definition order
        classifications = list(ToolClassification)
        assert classifications[0] == ToolClassification.SAFE
        assert classifications[3] == ToolClassification.CRITICAL


class TestCapabilityScope:
    """Tests for CapabilityScope enum."""

    def test_all_values_exist(self):
        """Verify all scope values exist."""
        assert CapabilityScope.SINGLE_USE.value == "single_use"
        assert CapabilityScope.SESSION.value == "session"
        assert CapabilityScope.TASK_TREE.value == "task_tree"
        assert CapabilityScope.TIME_BOUNDED.value == "time_bounded"

    def test_enum_count(self):
        """Verify correct number of scopes."""
        assert len(CapabilityScope) == 4


class TestExecutionContext:
    """Tests for ExecutionContext enum."""

    def test_all_values_exist(self):
        """Verify all context values exist."""
        assert ExecutionContext.TEST.value == "test"
        assert ExecutionContext.SANDBOX.value == "sandbox"
        assert ExecutionContext.DEVELOPMENT.value == "development"
        assert ExecutionContext.STAGING.value == "staging"
        assert ExecutionContext.PRODUCTION.value == "production"

    def test_enum_count(self):
        """Verify correct number of contexts."""
        assert len(ExecutionContext) == 5


class TestActionType:
    """Tests for ActionType enum."""

    def test_all_values_exist(self):
        """Verify all action types exist."""
        assert ActionType.READ.value == "read"
        assert ActionType.WRITE.value == "write"
        assert ActionType.EXECUTE.value == "execute"
        assert ActionType.ADMIN.value == "admin"
        assert ActionType.DELETE.value == "delete"

    def test_enum_count(self):
        """Verify correct number of action types."""
        assert len(ActionType) == 5


# =============================================================================
# ToolCapability Tests
# =============================================================================


class TestToolCapability:
    """Tests for ToolCapability dataclass."""

    def test_basic_creation(self):
        """Test basic capability creation."""
        cap = ToolCapability(
            tool_name="test_tool",
            classification=ToolClassification.SAFE,
            description="Test tool",
        )
        assert cap.tool_name == "test_tool"
        assert cap.classification == ToolClassification.SAFE
        assert cap.description == "Test tool"

    def test_default_values(self):
        """Test default values."""
        cap = ToolCapability(
            tool_name="test_tool",
            classification=ToolClassification.SAFE,
        )
        assert cap.allowed_actions == ("read", "execute")
        assert cap.requires_context == ()
        assert cap.blocked_contexts == ()
        assert cap.rate_limit_per_minute == 60
        assert cap.max_concurrent == 5
        assert cap.requires_justification is False
        assert cap.audit_sample_rate == 1.0

    def test_is_allowed_in_context_no_restrictions(self):
        """Test context check with no restrictions."""
        cap = ToolCapability(
            tool_name="test_tool",
            classification=ToolClassification.SAFE,
        )
        assert cap.is_allowed_in_context("test") is True
        assert cap.is_allowed_in_context("production") is True
        assert cap.is_allowed_in_context("sandbox") is True

    def test_is_allowed_in_context_blocked(self):
        """Test context check with blocked contexts."""
        cap = ToolCapability(
            tool_name="test_tool",
            classification=ToolClassification.DANGEROUS,
            blocked_contexts=("production",),
        )
        assert cap.is_allowed_in_context("test") is True
        assert cap.is_allowed_in_context("sandbox") is True
        assert cap.is_allowed_in_context("production") is False

    def test_is_allowed_in_context_required(self):
        """Test context check with required contexts."""
        cap = ToolCapability(
            tool_name="test_tool",
            classification=ToolClassification.CRITICAL,
            requires_context=("sandbox", "test"),
        )
        assert cap.is_allowed_in_context("test") is True
        assert cap.is_allowed_in_context("sandbox") is True
        assert cap.is_allowed_in_context("production") is False
        assert cap.is_allowed_in_context("development") is False

    def test_is_allowed_in_context_required_and_blocked(self):
        """Test context check with both required and blocked."""
        cap = ToolCapability(
            tool_name="test_tool",
            classification=ToolClassification.CRITICAL,
            requires_context=("sandbox", "test"),
            blocked_contexts=("test",),  # Blocked takes precedence
        )
        assert cap.is_allowed_in_context("sandbox") is True
        assert cap.is_allowed_in_context("test") is False

    def test_is_action_allowed(self):
        """Test action check."""
        cap = ToolCapability(
            tool_name="test_tool",
            classification=ToolClassification.SAFE,
            allowed_actions=("read", "execute"),
        )
        assert cap.is_action_allowed("read") is True
        assert cap.is_action_allowed("execute") is True
        assert cap.is_action_allowed("write") is False
        assert cap.is_action_allowed("delete") is False

    def test_is_action_allowed_wildcard(self):
        """Test action check with wildcard."""
        cap = ToolCapability(
            tool_name="admin_tool",
            classification=ToolClassification.CRITICAL,
            allowed_actions=("*",),
        )
        assert cap.is_action_allowed("read") is True
        assert cap.is_action_allowed("write") is True
        assert cap.is_action_allowed("delete") is True
        assert cap.is_action_allowed("anything") is True

    def test_immutability(self):
        """Test that ToolCapability is immutable (frozen)."""
        cap = ToolCapability(
            tool_name="test_tool",
            classification=ToolClassification.SAFE,
        )
        with pytest.raises(AttributeError):
            cap.tool_name = "new_name"


# =============================================================================
# CapabilityCheckResult Tests
# =============================================================================


class TestCapabilityCheckResult:
    """Tests for CapabilityCheckResult dataclass."""

    def test_basic_creation(self):
        """Test basic result creation."""
        result = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="test_tool",
            agent_id="agent-123",
            agent_type="CoderAgent",
            action="execute",
            context="sandbox",
            reason="Policy allows",
            policy_version="1.0.0",
            capability_source="base",
        )
        assert result.decision == CapabilityDecision.ALLOW
        assert result.tool_name == "test_tool"
        assert result.agent_id == "agent-123"

    def test_is_allowed_property(self):
        """Test is_allowed property."""
        allow_result = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="test",
            agent_id="a",
            agent_type="t",
            action="r",
            context="c",
            reason="r",
            policy_version="1",
            capability_source="base",
        )
        assert allow_result.is_allowed is True

        audit_only_result = CapabilityCheckResult(
            decision=CapabilityDecision.AUDIT_ONLY,
            tool_name="test",
            agent_id="a",
            agent_type="t",
            action="r",
            context="c",
            reason="r",
            policy_version="1",
            capability_source="base",
        )
        assert audit_only_result.is_allowed is True

        deny_result = CapabilityCheckResult(
            decision=CapabilityDecision.DENY,
            tool_name="test",
            agent_id="a",
            agent_type="t",
            action="r",
            context="c",
            reason="r",
            policy_version="1",
            capability_source="base",
        )
        assert deny_result.is_allowed is False

        escalate_result = CapabilityCheckResult(
            decision=CapabilityDecision.ESCALATE,
            tool_name="test",
            agent_id="a",
            agent_type="t",
            action="r",
            context="c",
            reason="r",
            policy_version="1",
            capability_source="base",
        )
        assert escalate_result.is_allowed is False

    def test_requires_hitl_property(self):
        """Test requires_hitl property."""
        escalate_result = CapabilityCheckResult(
            decision=CapabilityDecision.ESCALATE,
            tool_name="test",
            agent_id="a",
            agent_type="t",
            action="r",
            context="c",
            reason="r",
            policy_version="1",
            capability_source="base",
        )
        assert escalate_result.requires_hitl is True

        allow_result = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="test",
            agent_id="a",
            agent_type="t",
            action="r",
            context="c",
            reason="r",
            policy_version="1",
            capability_source="base",
        )
        assert allow_result.requires_hitl is False

    def test_to_audit_record(self):
        """Test audit record conversion."""
        now = datetime.now(timezone.utc)
        result = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="test_tool",
            agent_id="agent-123",
            agent_type="CoderAgent",
            action="execute",
            context="sandbox",
            reason="Policy allows",
            policy_version="1.0.0",
            capability_source="base",
            checked_at=now,
            request_hash="abc123",
            processing_time_ms=5.5,
        )
        record = result.to_audit_record()

        assert record["decision"] == "allow"
        assert record["tool_name"] == "test_tool"
        assert record["agent_id"] == "agent-123"
        assert record["checked_at"] == now.isoformat()
        assert record["processing_time_ms"] == 5.5


# =============================================================================
# CapabilityContext Tests
# =============================================================================


class TestCapabilityContext:
    """Tests for CapabilityContext dataclass."""

    def test_basic_creation(self):
        """Test basic context creation."""
        ctx = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
        )
        assert ctx.agent_id == "agent-123"
        assert ctx.agent_type == "CoderAgent"
        assert ctx.tool_name == "semantic_search"
        assert ctx.action == "execute"
        assert ctx.execution_context == "sandbox"

    def test_optional_fields(self):
        """Test optional fields."""
        ctx = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
            parent_agent_id="parent-456",
            execution_id="exec-789",
            session_id="session-012",
            task_description="Search for code",
            justification="Need to find related files",
        )
        assert ctx.parent_agent_id == "parent-456"
        assert ctx.execution_id == "exec-789"
        assert ctx.session_id == "session-012"
        assert ctx.task_description == "Search for code"
        assert ctx.justification == "Need to find related files"

    def test_to_dict(self):
        """Test dictionary conversion."""
        ctx = CapabilityContext(
            agent_id="agent-123",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="sandbox",
        )
        d = ctx.to_dict()
        assert d["agent_id"] == "agent-123"
        assert d["agent_type"] == "CoderAgent"
        assert d["tool_name"] == "semantic_search"
        assert d["parent_agent_id"] is None


# =============================================================================
# CapabilityEscalationRequest Tests
# =============================================================================


class TestCapabilityEscalationRequest:
    """Tests for CapabilityEscalationRequest dataclass."""

    def test_basic_creation(self):
        """Test basic escalation request creation."""
        request = CapabilityEscalationRequest(
            request_id="req-123",
            agent_id="agent-456",
            agent_type="CoderAgent",
            requested_tool="deploy_to_production",
            requested_action="execute",
            context="staging",
            justification="Need to deploy hotfix",
            task_description="Deploy critical bug fix",
        )
        assert request.request_id == "req-123"
        assert request.status == "pending"
        assert request.priority == "normal"

    def test_is_expired_not_set(self):
        """Test expiration when expires_at not set."""
        request = CapabilityEscalationRequest(
            request_id="req-123",
            agent_id="agent-456",
            agent_type="CoderAgent",
            requested_tool="deploy_to_production",
            requested_action="execute",
            context="staging",
            justification="Need to deploy hotfix",
            task_description="Deploy critical bug fix",
        )
        assert request.is_expired is False

    def test_is_expired_future(self):
        """Test expiration with future expires_at."""
        request = CapabilityEscalationRequest(
            request_id="req-123",
            agent_id="agent-456",
            agent_type="CoderAgent",
            requested_tool="deploy_to_production",
            requested_action="execute",
            context="staging",
            justification="Need to deploy hotfix",
            task_description="Deploy critical bug fix",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert request.is_expired is False

    def test_is_expired_past(self):
        """Test expiration with past expires_at."""
        request = CapabilityEscalationRequest(
            request_id="req-123",
            agent_id="agent-456",
            agent_type="CoderAgent",
            requested_tool="deploy_to_production",
            requested_action="execute",
            context="staging",
            justification="Need to deploy hotfix",
            task_description="Deploy critical bug fix",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert request.is_expired is True

    def test_is_pending(self):
        """Test is_pending property."""
        # Pending and not expired
        request = CapabilityEscalationRequest(
            request_id="req-123",
            agent_id="agent-456",
            agent_type="CoderAgent",
            requested_tool="deploy_to_production",
            requested_action="execute",
            context="staging",
            justification="Need to deploy hotfix",
            task_description="Deploy critical bug fix",
            status="pending",
        )
        assert request.is_pending is True

        # Not pending
        request.status = "approved"
        assert request.is_pending is False

    def test_to_dict(self):
        """Test dictionary conversion."""
        request = CapabilityEscalationRequest(
            request_id="req-123",
            agent_id="agent-456",
            agent_type="CoderAgent",
            requested_tool="deploy_to_production",
            requested_action="execute",
            context="staging",
            justification="Need to deploy hotfix",
            task_description="Deploy critical bug fix",
        )
        d = request.to_dict()
        assert d["request_id"] == "req-123"
        assert d["status"] == "pending"
        assert "created_at" in d


# =============================================================================
# CapabilityApprovalResponse Tests
# =============================================================================


class TestCapabilityApprovalResponse:
    """Tests for CapabilityApprovalResponse dataclass."""

    def test_basic_creation(self):
        """Test basic approval response creation."""
        response = CapabilityApprovalResponse(
            request_id="req-123",
            approved=True,
            approver_id="admin-456",
            scope=CapabilityScope.SINGLE_USE,
        )
        assert response.request_id == "req-123"
        assert response.approved is True
        assert response.approver_id == "admin-456"
        assert response.scope == CapabilityScope.SINGLE_USE

    def test_with_constraints(self):
        """Test with constraints."""
        response = CapabilityApprovalResponse(
            request_id="req-123",
            approved=True,
            approver_id="admin-456",
            scope=CapabilityScope.TIME_BOUNDED,
            constraints={"max_usage": 5},
            reason="Approved for testing",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
        )
        assert response.constraints == {"max_usage": 5}
        assert response.reason == "Approved for testing"

    def test_to_dict(self):
        """Test dictionary conversion."""
        response = CapabilityApprovalResponse(
            request_id="req-123",
            approved=True,
            approver_id="admin-456",
            scope=CapabilityScope.SESSION,
        )
        d = response.to_dict()
        assert d["request_id"] == "req-123"
        assert d["approved"] is True
        assert d["scope"] == "session"


# =============================================================================
# DynamicCapabilityGrant Tests
# =============================================================================


class TestDynamicCapabilityGrant:
    """Tests for DynamicCapabilityGrant dataclass."""

    def test_basic_creation(self):
        """Test basic grant creation."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="execute",
            scope=CapabilityScope.SINGLE_USE,
            constraints={},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
        )
        assert grant.grant_id == "grant-123"
        assert grant.usage_count == 0
        assert grant.revoked is False

    def test_is_valid_active(self):
        """Test is_valid for active grant."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
        )
        assert grant.is_valid is True

    def test_is_valid_expired(self):
        """Test is_valid for expired grant."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )
        assert grant.is_valid is False

    def test_is_valid_revoked(self):
        """Test is_valid for revoked grant."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
            revoked=True,
        )
        assert grant.is_valid is False

    def test_is_valid_exhausted(self):
        """Test is_valid for exhausted grant."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="execute",
            scope=CapabilityScope.SINGLE_USE,
            constraints={},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
            max_usage=1,
            usage_count=1,
        )
        assert grant.is_valid is False

    def test_remaining_uses_unlimited(self):
        """Test remaining_uses with no limit."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
        )
        assert grant.remaining_uses is None

    def test_remaining_uses_limited(self):
        """Test remaining_uses with limit."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="execute",
            scope=CapabilityScope.TIME_BOUNDED,
            constraints={},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
            max_usage=5,
            usage_count=2,
        )
        assert grant.remaining_uses == 3

    def test_is_applicable_matching(self):
        """Test is_applicable with matching parameters."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
        )
        assert grant.is_applicable("deploy_to_production", "execute", "staging") is True

    def test_is_applicable_wrong_tool(self):
        """Test is_applicable with wrong tool."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
        )
        assert grant.is_applicable("delete_repository", "execute", "staging") is False

    def test_is_applicable_wrong_action(self):
        """Test is_applicable with wrong action."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
        )
        assert grant.is_applicable("deploy_to_production", "read", "staging") is False

    def test_is_applicable_wildcard_action(self):
        """Test is_applicable with wildcard action."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="*",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
        )
        assert grant.is_applicable("deploy_to_production", "execute", "staging") is True
        assert grant.is_applicable("deploy_to_production", "read", "staging") is True

    def test_is_applicable_context_restrictions(self):
        """Test is_applicable with context restrictions."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
            context_restrictions=["staging", "sandbox"],
        )
        assert grant.is_applicable("deploy_to_production", "execute", "staging") is True
        assert grant.is_applicable("deploy_to_production", "execute", "sandbox") is True
        assert (
            grant.is_applicable("deploy_to_production", "execute", "production")
            is False
        )

    def test_to_dict(self):
        """Test dictionary conversion."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-123",
            agent_id="agent-456",
            tool_name="deploy_to_production",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={"max_calls": 10},
            granted_by="req-789",
            approver="admin-012",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
        )
        d = grant.to_dict()
        assert d["grant_id"] == "grant-123"
        assert d["scope"] == "session"
        assert d["constraints"] == {"max_calls": 10}


# =============================================================================
# CapabilityViolation Tests
# =============================================================================


class TestCapabilityViolation:
    """Tests for CapabilityViolation dataclass."""

    def test_basic_creation(self):
        """Test basic violation creation."""
        violation = CapabilityViolation(
            violation_id="viol-123",
            agent_id="agent-456",
            agent_type="CoderAgent",
            tool_name="delete_repository",
            action="delete",
            context="production",
            decision=CapabilityDecision.DENY,
            reason="Not authorized for production",
        )
        assert violation.violation_id == "viol-123"
        assert violation.severity == "medium"
        assert violation.acknowledged is False

    def test_severity_levels(self):
        """Test different severity levels."""
        violation = CapabilityViolation(
            violation_id="viol-123",
            agent_id="agent-456",
            agent_type="CoderAgent",
            tool_name="delete_repository",
            action="delete",
            context="production",
            decision=CapabilityDecision.DENY,
            reason="Not authorized",
            severity="critical",
        )
        assert violation.severity == "critical"

    def test_to_dict(self):
        """Test dictionary conversion."""
        violation = CapabilityViolation(
            violation_id="viol-123",
            agent_id="agent-456",
            agent_type="CoderAgent",
            tool_name="delete_repository",
            action="delete",
            context="production",
            decision=CapabilityDecision.DENY,
            reason="Not authorized",
        )
        d = violation.to_dict()
        assert d["violation_id"] == "viol-123"
        assert d["decision"] == "deny"
        assert "occurred_at" in d
