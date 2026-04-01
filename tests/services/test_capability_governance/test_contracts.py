"""
Tests for capability governance contracts.

Tests all data classes, enums, and type definitions.
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


class TestCapabilityDecision:
    """Test CapabilityDecision enum."""

    def test_enum_values(self):
        """Verify all enum values are correct."""
        assert CapabilityDecision.ALLOW.value == "allow"
        assert CapabilityDecision.DENY.value == "deny"
        assert CapabilityDecision.ESCALATE.value == "escalate"
        assert CapabilityDecision.AUDIT_ONLY.value == "audit_only"

    def test_enum_count(self):
        """Verify we have exactly 4 decision types."""
        assert len(CapabilityDecision) == 4

    def test_from_string(self):
        """Test creating enum from string value."""
        assert CapabilityDecision("allow") == CapabilityDecision.ALLOW
        assert CapabilityDecision("deny") == CapabilityDecision.DENY
        assert CapabilityDecision("escalate") == CapabilityDecision.ESCALATE
        assert CapabilityDecision("audit_only") == CapabilityDecision.AUDIT_ONLY


class TestToolClassification:
    """Test ToolClassification enum."""

    def test_enum_values(self):
        """Verify all classification values are correct."""
        assert ToolClassification.SAFE.value == "safe"
        assert ToolClassification.MONITORING.value == "monitoring"
        assert ToolClassification.DANGEROUS.value == "dangerous"
        assert ToolClassification.CRITICAL.value == "critical"

    def test_enum_count(self):
        """Verify we have exactly 4 classification levels."""
        assert len(ToolClassification) == 4

    def test_from_string(self):
        """Test creating enum from string value."""
        assert ToolClassification("safe") == ToolClassification.SAFE
        assert ToolClassification("monitoring") == ToolClassification.MONITORING
        assert ToolClassification("dangerous") == ToolClassification.DANGEROUS
        assert ToolClassification("critical") == ToolClassification.CRITICAL


class TestCapabilityScope:
    """Test CapabilityScope enum."""

    def test_enum_values(self):
        """Verify all scope values are correct."""
        assert CapabilityScope.SINGLE_USE.value == "single_use"
        assert CapabilityScope.SESSION.value == "session"
        assert CapabilityScope.TASK_TREE.value == "task_tree"
        assert CapabilityScope.TIME_BOUNDED.value == "time_bounded"

    def test_enum_count(self):
        """Verify we have exactly 4 scope types."""
        assert len(CapabilityScope) == 4


class TestExecutionContext:
    """Test ExecutionContext enum."""

    def test_enum_values(self):
        """Verify all context values are correct."""
        assert ExecutionContext.TEST.value == "test"
        assert ExecutionContext.SANDBOX.value == "sandbox"
        assert ExecutionContext.DEVELOPMENT.value == "development"
        assert ExecutionContext.STAGING.value == "staging"
        assert ExecutionContext.PRODUCTION.value == "production"

    def test_enum_count(self):
        """Verify we have exactly 5 context types."""
        assert len(ExecutionContext) == 5


class TestActionType:
    """Test ActionType enum."""

    def test_enum_values(self):
        """Verify all action type values are correct."""
        assert ActionType.READ.value == "read"
        assert ActionType.WRITE.value == "write"
        assert ActionType.EXECUTE.value == "execute"
        assert ActionType.ADMIN.value == "admin"
        assert ActionType.DELETE.value == "delete"

    def test_enum_count(self):
        """Verify we have exactly 5 action types."""
        assert len(ActionType) == 5


class TestToolCapability:
    """Test ToolCapability dataclass."""

    def test_creation_minimal(self):
        """Test creating with minimal required fields."""
        cap = ToolCapability(
            tool_name="test_tool",
            classification=ToolClassification.SAFE,
        )
        assert cap.tool_name == "test_tool"
        assert cap.classification == ToolClassification.SAFE
        assert cap.allowed_actions == ("read", "execute")
        assert cap.requires_context == ()
        assert cap.blocked_contexts == ()
        assert cap.rate_limit_per_minute == 60

    def test_creation_full(self):
        """Test creating with all fields."""
        cap = ToolCapability(
            tool_name="dangerous_tool",
            classification=ToolClassification.DANGEROUS,
            description="A dangerous tool",
            allowed_actions=("read", "write", "execute"),
            requires_context=("sandbox",),
            blocked_contexts=("production",),
            rate_limit_per_minute=10,
            max_concurrent=2,
            requires_justification=True,
            audit_sample_rate=1.0,
        )
        assert cap.tool_name == "dangerous_tool"
        assert cap.requires_justification is True
        assert cap.max_concurrent == 2

    def test_is_allowed_in_context_blocked(self):
        """Test context blocking."""
        cap = ToolCapability(
            tool_name="test",
            classification=ToolClassification.MONITORING,
            blocked_contexts=("production",),
        )
        assert cap.is_allowed_in_context("production") is False
        assert cap.is_allowed_in_context("development") is True

    def test_is_allowed_in_context_required(self):
        """Test required context."""
        cap = ToolCapability(
            tool_name="test",
            classification=ToolClassification.DANGEROUS,
            requires_context=("sandbox", "test"),
        )
        assert cap.is_allowed_in_context("sandbox") is True
        assert cap.is_allowed_in_context("test") is True
        assert cap.is_allowed_in_context("development") is False

    def test_is_action_allowed(self):
        """Test action allowance check."""
        cap = ToolCapability(
            tool_name="test",
            classification=ToolClassification.SAFE,
            allowed_actions=("read", "execute"),
        )
        assert cap.is_action_allowed("read") is True
        assert cap.is_action_allowed("execute") is True
        assert cap.is_action_allowed("write") is False
        assert cap.is_action_allowed("admin") is False

    def test_is_action_allowed_wildcard(self):
        """Test wildcard action allowance."""
        cap = ToolCapability(
            tool_name="test",
            classification=ToolClassification.SAFE,
            allowed_actions=("*",),
        )
        assert cap.is_action_allowed("read") is True
        assert cap.is_action_allowed("write") is True
        assert cap.is_action_allowed("anything") is True

    def test_is_frozen(self):
        """Test that ToolCapability is immutable."""
        cap = ToolCapability(
            tool_name="test",
            classification=ToolClassification.SAFE,
        )
        with pytest.raises(AttributeError):
            cap.tool_name = "changed"


class TestCapabilityCheckResult:
    """Test CapabilityCheckResult dataclass."""

    def test_creation(self, sample_check_result: CapabilityCheckResult):
        """Test basic creation."""
        assert sample_check_result.decision == CapabilityDecision.ALLOW
        assert sample_check_result.tool_name == "semantic_search"
        assert sample_check_result.agent_type == "CoderAgent"

    def test_is_allowed_for_allow(self):
        """Test is_allowed property for ALLOW decision."""
        result = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="test",
            agent_id="agent-001",
            agent_type="TestAgent",
            action="execute",
            context="test",
            reason="Allowed",
            policy_version="1.0",
            capability_source="base",
        )
        assert result.is_allowed is True

    def test_is_allowed_for_audit_only(self):
        """Test is_allowed property for AUDIT_ONLY decision."""
        result = CapabilityCheckResult(
            decision=CapabilityDecision.AUDIT_ONLY,
            tool_name="test",
            agent_id="agent-001",
            agent_type="TestAgent",
            action="execute",
            context="test",
            reason="Allowed with audit",
            policy_version="1.0",
            capability_source="base",
        )
        assert result.is_allowed is True

    def test_is_allowed_for_deny(self):
        """Test is_allowed property for DENY decision."""
        result = CapabilityCheckResult(
            decision=CapabilityDecision.DENY,
            tool_name="test",
            agent_id="agent-001",
            agent_type="TestAgent",
            action="execute",
            context="test",
            reason="Denied",
            policy_version="1.0",
            capability_source="base",
        )
        assert result.is_allowed is False

    def test_is_allowed_for_escalate(self):
        """Test is_allowed property for ESCALATE decision."""
        result = CapabilityCheckResult(
            decision=CapabilityDecision.ESCALATE,
            tool_name="test",
            agent_id="agent-001",
            agent_type="TestAgent",
            action="execute",
            context="test",
            reason="Requires approval",
            policy_version="1.0",
            capability_source="base",
        )
        assert result.is_allowed is False
        assert result.requires_hitl is True

    def test_requires_hitl(self):
        """Test requires_hitl property."""
        escalate = CapabilityCheckResult(
            decision=CapabilityDecision.ESCALATE,
            tool_name="test",
            agent_id="agent-001",
            agent_type="TestAgent",
            action="execute",
            context="test",
            reason="Requires approval",
            policy_version="1.0",
            capability_source="base",
        )
        assert escalate.requires_hitl is True

        allow = CapabilityCheckResult(
            decision=CapabilityDecision.ALLOW,
            tool_name="test",
            agent_id="agent-001",
            agent_type="TestAgent",
            action="execute",
            context="test",
            reason="Allowed",
            policy_version="1.0",
            capability_source="base",
        )
        assert allow.requires_hitl is False

    def test_to_audit_record(self, sample_check_result: CapabilityCheckResult):
        """Test conversion to audit record."""
        record = sample_check_result.to_audit_record()
        assert record["decision"] == "allow"
        assert record["tool_name"] == "semantic_search"
        assert record["agent_id"] == "coder-agent-001"
        assert record["agent_type"] == "CoderAgent"
        assert "checked_at" in record
        assert record["policy_version"] == "1.0"


class TestCapabilityContext:
    """Test CapabilityContext dataclass."""

    def test_creation_minimal(self):
        """Test creating with minimal fields."""
        ctx = CapabilityContext(
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="development",
        )
        assert ctx.agent_id == "agent-001"
        assert ctx.parent_agent_id is None
        assert ctx.session_id is None

    def test_creation_full(self):
        """Test creating with all fields."""
        ctx = CapabilityContext(
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="semantic_search",
            action="execute",
            execution_context="development",
            parent_agent_id="parent-001",
            execution_id="exec-001",
            session_id="session-001",
            task_description="Test task",
            justification="Need access for testing",
        )
        assert ctx.parent_agent_id == "parent-001"
        assert ctx.justification == "Need access for testing"

    def test_to_dict(self, sample_coder_context: CapabilityContext):
        """Test conversion to dictionary."""
        d = sample_coder_context.to_dict()
        assert d["agent_id"] == "coder-agent-001"
        assert d["agent_type"] == "CoderAgent"
        assert d["tool_name"] == "semantic_search"
        assert d["action"] == "execute"
        assert d["execution_context"] == "development"


class TestCapabilityEscalationRequest:
    """Test CapabilityEscalationRequest dataclass."""

    def test_creation(self, sample_escalation_request: CapabilityEscalationRequest):
        """Test basic creation."""
        assert sample_escalation_request.agent_id == "coder-agent-001"
        assert sample_escalation_request.status == "pending"

    def test_is_expired_false(self):
        """Test is_expired when not expired."""
        now = datetime.now(timezone.utc)
        request = CapabilityEscalationRequest(
            request_id="test-001",
            agent_id="agent-001",
            agent_type="TestAgent",
            requested_tool="test_tool",
            requested_action="execute",
            context="development",
            justification="Test",
            task_description="Testing",
            expires_at=now + timedelta(hours=1),
        )
        assert request.is_expired is False

    def test_is_expired_true(self):
        """Test is_expired when expired."""
        now = datetime.now(timezone.utc)
        request = CapabilityEscalationRequest(
            request_id="test-001",
            agent_id="agent-001",
            agent_type="TestAgent",
            requested_tool="test_tool",
            requested_action="execute",
            context="development",
            justification="Test",
            task_description="Testing",
            expires_at=now - timedelta(hours=1),
        )
        assert request.is_expired is True

    def test_is_expired_none(self):
        """Test is_expired when no expiration set."""
        request = CapabilityEscalationRequest(
            request_id="test-001",
            agent_id="agent-001",
            agent_type="TestAgent",
            requested_tool="test_tool",
            requested_action="execute",
            context="development",
            justification="Test",
            task_description="Testing",
            expires_at=None,
        )
        assert request.is_expired is False

    def test_is_pending(self):
        """Test is_pending property."""
        now = datetime.now(timezone.utc)
        pending = CapabilityEscalationRequest(
            request_id="test-001",
            agent_id="agent-001",
            agent_type="TestAgent",
            requested_tool="test_tool",
            requested_action="execute",
            context="development",
            justification="Test",
            task_description="Testing",
            status="pending",
            expires_at=now + timedelta(hours=1),
        )
        assert pending.is_pending is True

        approved = CapabilityEscalationRequest(
            request_id="test-002",
            agent_id="agent-001",
            agent_type="TestAgent",
            requested_tool="test_tool",
            requested_action="execute",
            context="development",
            justification="Test",
            task_description="Testing",
            status="approved",
            expires_at=now + timedelta(hours=1),
        )
        assert approved.is_pending is False

    def test_to_dict(self, sample_escalation_request: CapabilityEscalationRequest):
        """Test conversion to dictionary."""
        d = sample_escalation_request.to_dict()
        assert d["request_id"] == "cap-esc-sample-001"
        assert d["agent_id"] == "coder-agent-001"
        assert d["status"] == "pending"
        assert "created_at" in d
        assert "expires_at" in d


class TestCapabilityApprovalResponse:
    """Test CapabilityApprovalResponse dataclass."""

    def test_creation(self):
        """Test basic creation."""
        response = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
            constraints={"max_uses": 5},
            reason="Approved for testing",
        )
        assert response.approved is True
        assert response.scope == CapabilityScope.SESSION
        assert response.constraints["max_uses"] == 5

    def test_to_dict(self):
        """Test conversion to dictionary."""
        response = CapabilityApprovalResponse(
            request_id="cap-esc-001",
            approved=True,
            approver_id="admin@example.com",
            scope=CapabilityScope.SESSION,
        )
        d = response.to_dict()
        assert d["request_id"] == "cap-esc-001"
        assert d["approved"] is True
        assert d["scope"] == "session"


class TestDynamicCapabilityGrant:
    """Test DynamicCapabilityGrant dataclass."""

    def test_creation(self, sample_grant: DynamicCapabilityGrant):
        """Test basic creation."""
        assert sample_grant.agent_id == "coder-agent-001"
        assert sample_grant.tool_name == "provision_sandbox"
        assert sample_grant.revoked is False

    def test_is_valid_active(self, sample_grant: DynamicCapabilityGrant):
        """Test is_valid for active grant."""
        assert sample_grant.is_valid is True

    def test_is_valid_expired(self, expired_grant: DynamicCapabilityGrant):
        """Test is_valid for expired grant."""
        assert expired_grant.is_valid is False

    def test_is_valid_revoked(self, revoked_grant: DynamicCapabilityGrant):
        """Test is_valid for revoked grant."""
        assert revoked_grant.is_valid is False

    def test_is_valid_usage_exceeded(self):
        """Test is_valid when usage exceeded."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-001",
            agent_id="agent-001",
            tool_name="test_tool",
            action="execute",
            scope=CapabilityScope.SINGLE_USE,
            constraints={},
            granted_by="test",
            approver="admin",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
            usage_count=1,
            max_usage=1,
        )
        assert grant.is_valid is False

    def test_remaining_uses(self, sample_grant: DynamicCapabilityGrant):
        """Test remaining_uses property."""
        # No max_usage set
        assert sample_grant.remaining_uses is None

    def test_remaining_uses_with_limit(self):
        """Test remaining_uses with limit set."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-001",
            agent_id="agent-001",
            tool_name="test_tool",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="test",
            approver="admin",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
            usage_count=3,
            max_usage=10,
        )
        assert grant.remaining_uses == 7

    def test_is_applicable_matching(self, sample_grant: DynamicCapabilityGrant):
        """Test is_applicable with matching parameters."""
        assert (
            sample_grant.is_applicable("provision_sandbox", "execute", "development")
            is True
        )

    def test_is_applicable_wrong_tool(self, sample_grant: DynamicCapabilityGrant):
        """Test is_applicable with wrong tool."""
        assert (
            sample_grant.is_applicable("other_tool", "execute", "development") is False
        )

    def test_is_applicable_wrong_action(self, sample_grant: DynamicCapabilityGrant):
        """Test is_applicable with wrong action."""
        assert (
            sample_grant.is_applicable("provision_sandbox", "read", "development")
            is False
        )

    def test_is_applicable_wildcard_action(self):
        """Test is_applicable with wildcard action."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-001",
            agent_id="agent-001",
            tool_name="test_tool",
            action="*",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="test",
            approver="admin",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
        )
        assert grant.is_applicable("test_tool", "read", "development") is True
        assert grant.is_applicable("test_tool", "write", "development") is True
        assert grant.is_applicable("test_tool", "execute", "development") is True

    def test_is_applicable_context_restricted(self):
        """Test is_applicable with context restrictions."""
        now = datetime.now(timezone.utc)
        grant = DynamicCapabilityGrant(
            grant_id="grant-001",
            agent_id="agent-001",
            tool_name="test_tool",
            action="execute",
            scope=CapabilityScope.SESSION,
            constraints={},
            granted_by="test",
            approver="admin",
            granted_at=now,
            expires_at=now + timedelta(hours=1),
            context_restrictions=["sandbox", "test"],
        )
        assert grant.is_applicable("test_tool", "execute", "sandbox") is True
        assert grant.is_applicable("test_tool", "execute", "test") is True
        assert grant.is_applicable("test_tool", "execute", "development") is False

    def test_to_dict(self, sample_grant: DynamicCapabilityGrant):
        """Test conversion to dictionary."""
        d = sample_grant.to_dict()
        assert d["grant_id"] == "grant-test-001"
        assert d["agent_id"] == "coder-agent-001"
        assert d["tool_name"] == "provision_sandbox"
        assert d["scope"] == "session"
        assert d["revoked"] is False


class TestCapabilityViolation:
    """Test CapabilityViolation dataclass."""

    def test_creation(self):
        """Test basic creation."""
        violation = CapabilityViolation(
            violation_id="viol-001",
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            context="development",
            decision=CapabilityDecision.DENY,
            reason="Tool not permitted",
            severity="high",
        )
        assert violation.violation_id == "viol-001"
        assert violation.severity == "high"
        assert violation.acknowledged is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        violation = CapabilityViolation(
            violation_id="viol-001",
            agent_id="agent-001",
            agent_type="CoderAgent",
            tool_name="provision_sandbox",
            action="execute",
            context="development",
            decision=CapabilityDecision.DENY,
            reason="Tool not permitted",
        )
        d = violation.to_dict()
        assert d["violation_id"] == "viol-001"
        assert d["decision"] == "deny"
        assert d["acknowledged"] is False
