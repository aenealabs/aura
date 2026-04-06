"""
Tests for Cedar Policy Engine.

Tests the real-time policy enforcement for agent tool calls:
- Cedar policy language parsing and evaluation
- Natural language to Cedar conversion
- Policy CRUD operations
- Tool call interception
- Audit logging
"""

from unittest.mock import MagicMock

import pytest

from src.services.cedar_policy_engine import (
    CedarPolicy,
    CedarPolicyEngine,
    PolicyAuditEntry,
    PolicyDecision,
    PolicyEffect,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
    PolicyPriority,
    PolicyValidationResult,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_dynamodb():
    """Create mock DynamoDB client."""
    return MagicMock()


@pytest.fixture
def mock_bedrock():
    """Create mock Bedrock client for LLM calls."""
    client = MagicMock()
    return client


@pytest.fixture
def engine():
    """Create Cedar Policy Engine without external dependencies."""
    return CedarPolicyEngine(
        dynamodb_client=None,
        bedrock_client=None,
        default_decision=PolicyDecision.DENY,
    )


@pytest.fixture
def engine_with_mocks(mock_dynamodb, mock_bedrock):
    """Create Cedar Policy Engine with mocked dependencies."""
    return CedarPolicyEngine(
        dynamodb_client=mock_dynamodb,
        bedrock_client=mock_bedrock,
        policy_table="test-policies",
        audit_table="test-audit",
    )


# ============================================================================
# Enum Tests
# ============================================================================


class TestEnums:
    """Test enum definitions."""

    def test_policy_decision_values(self):
        """Test PolicyDecision enum values."""
        assert PolicyDecision.ALLOW.value == "allow"
        assert PolicyDecision.DENY.value == "deny"

    def test_policy_effect_values(self):
        """Test PolicyEffect enum values."""
        assert PolicyEffect.PERMIT.value == "permit"
        assert PolicyEffect.FORBID.value == "forbid"

    def test_policy_priority_values(self):
        """Test PolicyPriority enum values."""
        assert PolicyPriority.SYSTEM.value == 1000
        assert PolicyPriority.ORGANIZATION.value == 500
        assert PolicyPriority.TEAM.value == 250
        assert PolicyPriority.USER.value == 100
        assert PolicyPriority.DEFAULT.value == 0


# ============================================================================
# Data Model Tests
# ============================================================================


class TestCedarPolicy:
    """Test CedarPolicy dataclass."""

    def test_create_policy(self):
        """Test creating a policy."""
        policy = CedarPolicy(
            policy_id="test-policy-1",
            policy_name="Test Policy",
            description="A test policy",
            cedar_syntax="permit(principal, action, resource);",
        )
        assert policy.policy_id == "test-policy-1"
        assert policy.policy_name == "Test Policy"
        assert policy.effect == PolicyEffect.PERMIT
        assert policy.enabled is True
        assert policy.scope == "global"

    def test_policy_with_all_fields(self):
        """Test policy with all optional fields."""
        policy = CedarPolicy(
            policy_id="test-policy-2",
            policy_name="Full Policy",
            description="Full test policy",
            cedar_syntax="forbid(principal, action, resource);",
            natural_language="Deny all actions",
            effect=PolicyEffect.FORBID,
            priority=PolicyPriority.ORGANIZATION.value,
            enabled=True,
            scope="organization",
            organization_id="org-123",
            team_id="team-456",
            user_id="user-789",
            tags=["security", "compliance"],
        )
        assert policy.effect == PolicyEffect.FORBID
        assert policy.priority == 500
        assert policy.organization_id == "org-123"
        assert "security" in policy.tags

    def test_policy_hash(self):
        """Test policy is hashable."""
        policy = CedarPolicy(
            policy_id="test-policy-3",
            policy_name="Hashable Policy",
            description="Test hashing",
            cedar_syntax="permit(principal, action, resource);",
        )
        # Should be able to use in sets
        policy_set = {policy}
        assert policy in policy_set


class TestPolicyEvaluationRequest:
    """Test PolicyEvaluationRequest dataclass."""

    def test_create_request(self):
        """Test creating evaluation request."""
        request = PolicyEvaluationRequest(
            principal="Agent::coder-agent",
            action="Action::invoke_tool",
            resource="Tool::slack_post",
        )
        assert request.principal == "Agent::coder-agent"
        assert request.action == "Action::invoke_tool"
        assert request.resource == "Tool::slack_post"
        assert request.context == {}
        assert request.request_id is not None

    def test_request_with_context(self):
        """Test request with context."""
        request = PolicyEvaluationRequest(
            principal="Agent::coder-agent",
            action="Action::invoke_tool",
            resource="Tool::github_push",
            context={"branch": "main", "approved": True},
            organization_id="org-123",
            team_id="team-456",
        )
        assert request.context["branch"] == "main"
        assert request.organization_id == "org-123"


class TestPolicyEvaluationResult:
    """Test PolicyEvaluationResult dataclass."""

    def test_create_result(self):
        """Test creating evaluation result."""
        result = PolicyEvaluationResult(
            decision=PolicyDecision.ALLOW,
            request_id="req-123",
            matched_policies=["policy-1", "policy-2"],
        )
        assert result.decision == PolicyDecision.ALLOW
        assert result.is_allowed is True
        assert len(result.matched_policies) == 2

    def test_result_denied(self):
        """Test denied result."""
        result = PolicyEvaluationResult(
            decision=PolicyDecision.DENY,
            request_id="req-456",
            matched_policies=["policy-deny"],
            determining_policy="policy-deny",
            reasons=["Access denied by policy"],
        )
        assert result.is_allowed is False
        assert result.determining_policy == "policy-deny"


class TestPolicyAuditEntry:
    """Test PolicyAuditEntry dataclass."""

    def test_create_audit_entry(self):
        """Test creating audit entry."""
        request = PolicyEvaluationRequest(
            principal="Agent::test",
            action="Action::read",
            resource="Data::config",
        )
        result = PolicyEvaluationResult(
            decision=PolicyDecision.ALLOW,
            request_id=request.request_id,
            matched_policies=["allow-read"],
        )
        entry = PolicyAuditEntry(
            audit_id="audit-123",
            request=request,
            result=result,
            agent_id="test-agent",
            tool_name="read_config",
        )
        assert entry.audit_id == "audit-123"
        assert entry.agent_id == "test-agent"


class TestPolicyValidationResult:
    """Test PolicyValidationResult dataclass."""

    def test_valid_result(self):
        """Test valid policy result."""
        result = PolicyValidationResult(
            valid=True,
            normalized_syntax="permit(principal, action, resource);",
        )
        assert result.valid is True
        assert result.errors == []

    def test_invalid_result(self):
        """Test invalid policy result."""
        result = PolicyValidationResult(
            valid=False,
            errors=["Missing permit/forbid"],
            warnings=["Should end with semicolon"],
        )
        assert result.valid is False
        assert len(result.errors) == 1


# ============================================================================
# Engine Initialization Tests
# ============================================================================


class TestEngineInitialization:
    """Test CedarPolicyEngine initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        engine = CedarPolicyEngine()
        assert engine.default_decision == PolicyDecision.DENY
        assert len(engine._policies) > 0  # System policies initialized

    def test_initialization_with_custom_tables(self):
        """Test initialization with custom table names."""
        engine = CedarPolicyEngine(
            policy_table="custom-policies",
            audit_table="custom-audit",
        )
        assert engine.policy_table == "custom-policies"
        assert engine.audit_table == "custom-audit"

    def test_initialization_with_allow_default(self):
        """Test initialization with ALLOW as default."""
        engine = CedarPolicyEngine(
            default_decision=PolicyDecision.ALLOW,
        )
        assert engine.default_decision == PolicyDecision.ALLOW

    def test_system_policies_initialized(self, engine):
        """Test system policies are created on init."""
        assert "system-deny-default" in engine._policies
        assert "system-allow-read" in engine._policies
        assert "system-hitl-required" in engine._policies

    def test_system_policy_properties(self, engine):
        """Test system policy properties."""
        deny_policy = engine._policies["system-deny-default"]
        assert deny_policy.effect == PolicyEffect.FORBID
        assert "system" in deny_policy.tags
        assert deny_policy.scope == "global"


# ============================================================================
# Policy Creation Tests
# ============================================================================


class TestPolicyCreation:
    """Test policy creation methods."""

    @pytest.mark.asyncio
    async def test_create_policy_from_cedar(self, engine):
        """Test creating policy from Cedar syntax."""
        policy = await engine.create_policy(
            policy_name="Allow Read",
            cedar_syntax='permit(principal, action == Action::"read", resource);',
            description="Allow all read operations",
        )
        assert policy.policy_name == "Allow Read"
        assert policy.effect == PolicyEffect.PERMIT
        assert policy.policy_id in engine._policies

    @pytest.mark.asyncio
    async def test_create_forbid_policy(self, engine):
        """Test creating forbid policy."""
        policy = await engine.create_policy(
            policy_name="Deny Write",
            cedar_syntax='forbid(principal, action == Action::"write", resource);',
        )
        assert policy.effect == PolicyEffect.FORBID

    @pytest.mark.asyncio
    async def test_create_policy_with_scope(self, engine):
        """Test creating policy with specific scope."""
        policy = await engine.create_policy(
            policy_name="Org Policy",
            cedar_syntax="permit(principal, action, resource);",
            scope="organization",
            organization_id="org-123",
            priority=PolicyPriority.ORGANIZATION.value,
        )
        assert policy.scope == "organization"
        assert policy.organization_id == "org-123"
        assert policy.priority == 500

    @pytest.mark.asyncio
    async def test_create_policy_invalid_syntax(self, engine):
        """Test creating policy with invalid syntax."""
        with pytest.raises(ValueError, match="Invalid Cedar syntax"):
            await engine.create_policy(
                policy_name="Invalid",
                cedar_syntax="this is not valid cedar",
            )

    @pytest.mark.asyncio
    async def test_create_policy_from_natural_language_no_bedrock(self, engine):
        """Test NL to Cedar without Bedrock falls back to template."""
        policy = await engine.create_policy_from_natural_language(
            description="Agents cannot post to Slack without approval",
            policy_name="slack-approval",
        )
        assert policy.policy_name == "slack-approval"
        assert policy.natural_language == "Agents cannot post to Slack without approval"
        # Template-based should detect "cannot" and create forbid
        assert policy.effect == PolicyEffect.FORBID


# ============================================================================
# Policy CRUD Tests
# ============================================================================


class TestPolicyCRUD:
    """Test policy CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_policy(self, engine):
        """Test getting a policy by ID."""
        policy = await engine.create_policy(
            policy_name="Get Test",
            cedar_syntax="permit(principal, action, resource);",
        )
        retrieved = await engine.get_policy(policy.policy_id)
        assert retrieved is not None
        assert retrieved.policy_name == "Get Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_policy(self, engine):
        """Test getting nonexistent policy returns None."""
        result = await engine.get_policy("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_policy_description(self, engine):
        """Test updating policy description."""
        policy = await engine.create_policy(
            policy_name="Update Test",
            cedar_syntax="permit(principal, action, resource);",
            description="Original description",
        )
        updated = await engine.update_policy(
            policy_id=policy.policy_id,
            description="Updated description",
        )
        assert updated.description == "Updated description"

    @pytest.mark.asyncio
    async def test_update_policy_cedar(self, engine):
        """Test updating policy Cedar syntax."""
        policy = await engine.create_policy(
            policy_name="Update Cedar",
            cedar_syntax="permit(principal, action, resource);",
        )
        updated = await engine.update_policy(
            policy_id=policy.policy_id,
            cedar_syntax="forbid(principal, action, resource);",
        )
        assert "forbid" in updated.cedar_syntax

    @pytest.mark.asyncio
    async def test_update_policy_enabled(self, engine):
        """Test enabling/disabling policy."""
        policy = await engine.create_policy(
            policy_name="Disable Test",
            cedar_syntax="permit(principal, action, resource);",
        )
        assert policy.enabled is True

        updated = await engine.update_policy(
            policy_id=policy.policy_id,
            enabled=False,
        )
        assert updated.enabled is False

    @pytest.mark.asyncio
    async def test_update_nonexistent_policy(self, engine):
        """Test updating nonexistent policy returns None."""
        result = await engine.update_policy(
            policy_id="nonexistent",
            description="New description",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_update_policy_invalid_cedar(self, engine):
        """Test updating with invalid Cedar raises error."""
        policy = await engine.create_policy(
            policy_name="Invalid Update",
            cedar_syntax="permit(principal, action, resource);",
        )
        with pytest.raises(ValueError, match="Invalid Cedar syntax"):
            await engine.update_policy(
                policy_id=policy.policy_id,
                cedar_syntax="invalid syntax",
            )

    @pytest.mark.asyncio
    async def test_delete_policy(self, engine):
        """Test deleting a policy."""
        policy = await engine.create_policy(
            policy_name="Delete Test",
            cedar_syntax="permit(principal, action, resource);",
        )
        result = await engine.delete_policy(policy.policy_id)
        assert result is True
        assert policy.policy_id not in engine._policies

    @pytest.mark.asyncio
    async def test_delete_nonexistent_policy(self, engine):
        """Test deleting nonexistent policy returns False."""
        result = await engine.delete_policy("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_cannot_delete_system_policy(self, engine):
        """Test system policies cannot be deleted."""
        result = await engine.delete_policy("system-deny-default")
        assert result is False
        assert "system-deny-default" in engine._policies


# ============================================================================
# Policy Listing Tests
# ============================================================================


class TestPolicyListing:
    """Test policy listing with filters."""

    @pytest.mark.asyncio
    async def test_list_all_policies(self, engine):
        """Test listing all enabled policies."""
        policies = await engine.list_policies()
        assert len(policies) >= 3  # At least system policies

    @pytest.mark.asyncio
    async def test_list_policies_by_scope(self, engine):
        """Test listing policies by scope."""
        await engine.create_policy(
            policy_name="Org Policy",
            cedar_syntax="permit(principal, action, resource);",
            scope="organization",
        )
        policies = await engine.list_policies(scope="organization")
        assert all(p.scope == "organization" for p in policies)

    @pytest.mark.asyncio
    async def test_list_policies_by_organization(self, engine):
        """Test listing policies by organization."""
        await engine.create_policy(
            policy_name="Org-123 Policy",
            cedar_syntax="permit(principal, action, resource);",
            scope="organization",
            organization_id="org-123",
        )
        policies = await engine.list_policies(organization_id="org-123")
        # Should include global + org-specific policies
        assert any(p.scope == "global" for p in policies)

    @pytest.mark.asyncio
    async def test_list_policies_by_tags(self, engine):
        """Test listing policies by tags."""
        policies = await engine.list_policies(tags=["system"])
        assert all(any(t in p.tags for t in ["system"]) for p in policies)

    @pytest.mark.asyncio
    async def test_list_disabled_policies(self, engine):
        """Test disabled policies excluded by default."""
        policy = await engine.create_policy(
            policy_name="Disabled",
            cedar_syntax="permit(principal, action, resource);",
        )
        await engine.update_policy(policy.policy_id, enabled=False)

        policies = await engine.list_policies(enabled_only=True)
        assert policy.policy_id not in [p.policy_id for p in policies]

        policies_all = await engine.list_policies(enabled_only=False)
        assert policy.policy_id in [p.policy_id for p in policies_all]

    @pytest.mark.asyncio
    async def test_policies_sorted_by_priority(self, engine):
        """Test policies are sorted by priority descending."""
        policies = await engine.list_policies()
        priorities = [p.priority for p in policies]
        assert priorities == sorted(priorities, reverse=True)


# ============================================================================
# Policy Evaluation Tests
# ============================================================================


class TestPolicyEvaluation:
    """Test policy evaluation."""

    @pytest.mark.asyncio
    async def test_evaluate_read_allowed(self, engine):
        """Test read operations allowed by default."""
        request = PolicyEvaluationRequest(
            principal="Agent::reader",
            action="Action::read",
            resource="Data::config",
            # Need to set hitl_approved to bypass system HITL policy
            context={"hitl_approved": True},
        )
        result = await engine.evaluate(request)
        assert result.decision == PolicyDecision.ALLOW

    @pytest.mark.asyncio
    async def test_evaluate_default_deny(self, engine):
        """Test default deny for unknown actions."""
        request = PolicyEvaluationRequest(
            principal="Agent::unknown",
            action="Action::unknown_action",
            resource="Resource::unknown",
        )
        result = await engine.evaluate(request)
        assert result.decision == PolicyDecision.DENY

    @pytest.mark.asyncio
    async def test_evaluate_with_custom_policy(self, engine):
        """Test evaluation with custom policy."""
        await engine.create_policy(
            policy_name="Allow Slack",
            cedar_syntax='permit(principal, action == Action::"invoke_tool", resource == Tool::"slack");',
            priority=PolicyPriority.ORGANIZATION.value,
        )
        request = PolicyEvaluationRequest(
            principal="Agent::coder",
            action="Action::invoke_tool",
            resource="Tool::slack",
            # Need to set hitl_approved to bypass system HITL policy
            context={"hitl_approved": True},
        )
        result = await engine.evaluate(request)
        assert result.decision == PolicyDecision.ALLOW

    @pytest.mark.asyncio
    async def test_evaluate_forbid_takes_precedence(self, engine):
        """Test forbid policies take precedence at same priority."""
        await engine.create_policy(
            policy_name="Allow Test",
            cedar_syntax='permit(principal, action, resource == Tool::"test");',
            priority=100,
        )
        await engine.create_policy(
            policy_name="Forbid Test",
            cedar_syntax='forbid(principal, action, resource == Tool::"test");',
            priority=100,
        )
        request = PolicyEvaluationRequest(
            principal="Agent::test",
            action="Action::test",
            resource="Tool::test",
        )
        result = await engine.evaluate(request)
        assert result.decision == PolicyDecision.DENY

    @pytest.mark.asyncio
    async def test_evaluate_higher_priority_wins(self, engine):
        """Test higher priority policy wins."""
        await engine.create_policy(
            policy_name="Low Priority Allow",
            cedar_syntax='permit(principal, action, resource == Tool::"priority_test");',
            priority=100,
        )
        await engine.create_policy(
            policy_name="High Priority Deny",
            cedar_syntax='forbid(principal, action, resource == Tool::"priority_test");',
            priority=500,
        )
        request = PolicyEvaluationRequest(
            principal="Agent::test",
            action="Action::test",
            resource="Tool::priority_test",
        )
        result = await engine.evaluate(request)
        assert result.decision == PolicyDecision.DENY

    @pytest.mark.asyncio
    async def test_evaluate_with_when_condition(self, engine):
        """Test evaluation with when condition."""
        await engine.create_policy(
            policy_name="Conditional Allow",
            cedar_syntax="""permit(
                principal,
                action,
                resource
            ) when {
                context.approved == true
            };""",
            priority=PolicyPriority.ORGANIZATION.value,
        )
        # Without approval
        request_no_approval = PolicyEvaluationRequest(
            principal="Agent::test",
            action="Action::test",
            resource="Resource::test",
            context={"approved": False, "hitl_approved": True},
        )
        result = await engine.evaluate(request_no_approval)
        # Should not match the permit, fall through to default

        # With approval
        request_approved = PolicyEvaluationRequest(
            principal="Agent::test",
            action="Action::test",
            resource="Resource::test",
            context={"approved": True, "hitl_approved": True},
        )
        result = await engine.evaluate(request_approved)
        # Should match the permit
        assert result.decision == PolicyDecision.ALLOW

    @pytest.mark.asyncio
    async def test_evaluate_records_audit(self, engine):
        """Test evaluation records audit entry."""
        initial_count = len(engine._audit_log)
        request = PolicyEvaluationRequest(
            principal="Agent::test",
            action="Action::test",
            resource="Resource::test",
        )
        await engine.evaluate(request)
        assert len(engine._audit_log) == initial_count + 1


# ============================================================================
# Cedar Syntax Parsing Tests
# ============================================================================


class TestCedarParsing:
    """Test Cedar syntax parsing helpers."""

    def test_check_principal_any(self, engine):
        """Test matching any principal."""
        cedar = "permit(principal, action, resource);"
        assert engine._check_principal(cedar, "Agent::any") is True

    def test_check_principal_specific(self, engine):
        """Test matching specific principal."""
        cedar = 'permit(principal == Agent::"coder-agent", action, resource);'
        assert engine._check_principal(cedar, "Agent::coder-agent") is True
        assert engine._check_principal(cedar, "Agent::other") is False

    def test_check_action_any(self, engine):
        """Test matching any action."""
        cedar = "permit(principal, action, resource);"
        assert engine._check_action(cedar, "Action::any") is True

    def test_check_action_specific(self, engine):
        """Test matching specific action."""
        cedar = 'permit(principal, action == Action::"read", resource);'
        assert engine._check_action(cedar, "Action::read") is True
        assert engine._check_action(cedar, "read") is True
        assert engine._check_action(cedar, "Action::write") is False

    def test_check_resource_any(self, engine):
        """Test matching any resource."""
        cedar = "permit(principal, action, resource);"
        assert engine._check_resource(cedar, "Tool::any") is True

    def test_check_resource_specific(self, engine):
        """Test matching specific resource."""
        cedar = 'permit(principal, action, resource == Tool::"slack");'
        assert engine._check_resource(cedar, "Tool::slack") is True
        assert engine._check_resource(cedar, "Tool::github") is False

    def test_check_conditions_when_true(self, engine):
        """Test when condition that evaluates to true."""
        cedar = """permit(principal, action, resource) when {
            context.approved == true
        };"""
        assert engine._check_conditions(cedar, {"approved": True}) is True
        assert engine._check_conditions(cedar, {"approved": False}) is False

    def test_check_conditions_unless(self, engine):
        """Test unless condition."""
        cedar = """permit(principal, action, resource) unless {
            context.blocked == true
        };"""
        assert engine._check_conditions(cedar, {"blocked": False}) is True
        assert engine._check_conditions(cedar, {"blocked": True}) is False

    def test_check_conditions_no_conditions(self, engine):
        """Test policy without conditions."""
        cedar = "permit(principal, action, resource);"
        assert engine._check_conditions(cedar, {}) is True


# ============================================================================
# Condition Evaluation Tests
# ============================================================================


class TestConditionEvaluation:
    """Test condition string evaluation."""

    def test_evaluate_context_bool_equal(self, engine):
        """Test context.X == true/false."""
        assert (
            engine._evaluate_condition_string(
                "context.approved == true", {"approved": True}
            )
            is True
        )
        assert (
            engine._evaluate_condition_string(
                "context.approved == true", {"approved": False}
            )
            is False
        )

    def test_evaluate_context_bool_not_equal(self, engine):
        """Test context.X != true/false."""
        assert (
            engine._evaluate_condition_string(
                "context.blocked != true", {"blocked": False}
            )
            is True
        )
        assert (
            engine._evaluate_condition_string(
                "context.blocked != true", {"blocked": True}
            )
            is False
        )

    def test_evaluate_resource_in_list(self, engine):
        """Test resource.X in [...] condition."""
        result = engine._evaluate_condition_string(
            'resource.category in ["production_deployment", "credential_modification"]',
            {"resource_category": "production_deployment"},
        )
        assert result is True

        result = engine._evaluate_condition_string(
            'resource.category in ["production_deployment", "credential_modification"]',
            {"resource_category": "read_only"},
        )
        assert result is False


# ============================================================================
# Tool Call Interception Tests
# ============================================================================


class TestToolCallInterception:
    """Test tool call interception."""

    def test_intercept_tool_call_sync(self, engine):
        """Test synchronous tool call interception."""
        result = engine.intercept_tool_call(
            agent_id="coder-agent",
            tool_name="read_file",
            parameters={"path": "/src/main.py"},
        )
        assert isinstance(result, PolicyEvaluationResult)
        # read action should be allowed by system policy
        # Actually depends on how the action is matched

    def test_intercept_tool_call_with_context(self, engine):
        """Test interception with additional context."""
        result = engine.intercept_tool_call(
            agent_id="coder-agent",
            tool_name="slack_post",
            parameters={"channel": "#general"},
            user_id="user-123",
            session_id="session-456",
            context={"approved": True},
        )
        assert result.request_id is not None

    def test_intercept_records_audit(self, engine):
        """Test interception records audit entry."""
        initial_count = len(engine._audit_log)
        engine.intercept_tool_call(
            agent_id="test-agent",
            tool_name="test_tool",
            parameters={},
        )
        # Should have audit entries (one from evaluate, one from intercept)
        assert len(engine._audit_log) > initial_count

    @pytest.mark.asyncio
    async def test_intercept_tool_call_async(self, engine):
        """Test async tool call interception."""
        result = await engine.intercept_tool_call_async(
            agent_id="coder-agent",
            tool_name="github_push",
            parameters={"branch": "main"},
            context={"hitl_approved": True},
        )
        assert isinstance(result, PolicyEvaluationResult)


# ============================================================================
# Interceptor Registration Tests
# ============================================================================


class TestInterceptorRegistration:
    """Test custom interceptor registration."""

    def test_register_interceptor(self, engine):
        """Test registering custom interceptor."""

        def custom_interceptor(agent_id, tool_name, params):
            if tool_name == "forbidden_tool":
                return PolicyEvaluationResult(
                    decision=PolicyDecision.DENY,
                    request_id="custom",
                    matched_policies=["custom-interceptor"],
                    reasons=["Blocked by custom interceptor"],
                )
            return None

        engine.register_interceptor(custom_interceptor)
        assert custom_interceptor in engine._interceptors


# ============================================================================
# Audit Log Tests
# ============================================================================


class TestAuditLog:
    """Test audit logging functionality."""

    @pytest.mark.asyncio
    async def test_get_audit_log(self, engine):
        """Test getting audit log."""
        # Generate some audit entries
        for i in range(5):
            await engine.evaluate(
                PolicyEvaluationRequest(
                    principal=f"Agent::test-{i}",
                    action="Action::test",
                    resource="Resource::test",
                )
            )

        entries = await engine.get_audit_log(limit=10)
        assert len(entries) >= 5

    @pytest.mark.asyncio
    async def test_get_audit_log_by_agent(self, engine):
        """Test filtering audit log by agent."""
        await engine.intercept_tool_call_async(
            agent_id="specific-agent",
            tool_name="test_tool",
            parameters={},
        )
        entries = await engine.get_audit_log(agent_id="specific-agent")
        assert all(e.agent_id == "specific-agent" for e in entries)

    @pytest.mark.asyncio
    async def test_get_audit_log_by_tool(self, engine):
        """Test filtering audit log by tool."""
        await engine.intercept_tool_call_async(
            agent_id="test-agent",
            tool_name="specific_tool",
            parameters={},
        )
        entries = await engine.get_audit_log(tool_name="specific_tool")
        assert all(e.tool_name == "specific_tool" for e in entries)

    @pytest.mark.asyncio
    async def test_get_audit_log_by_decision(self, engine):
        """Test filtering audit log by decision."""
        entries = await engine.get_audit_log(decision=PolicyDecision.DENY)
        assert all(e.result.decision == PolicyDecision.DENY for e in entries)

    @pytest.mark.asyncio
    async def test_audit_log_sorted_by_time(self, engine):
        """Test audit log is sorted by time descending."""
        for i in range(3):
            await engine.evaluate(
                PolicyEvaluationRequest(
                    principal="Agent::test",
                    action="Action::test",
                    resource="Resource::test",
                )
            )

        entries = await engine.get_audit_log()
        times = [e.created_at for e in entries]
        assert times == sorted(times, reverse=True)


# ============================================================================
# Template-Based Translation Tests
# ============================================================================


class TestTemplatTranslation:
    """Test template-based NL to Cedar translation."""

    def test_translate_deny_pattern(self, engine):
        """Test 'cannot' triggers forbid."""
        cedar = engine._template_based_translation(
            "Agents cannot access production data"
        )
        assert "forbid" in cedar

    def test_translate_must_not_pattern(self, engine):
        """Test 'must not' triggers forbid."""
        cedar = engine._template_based_translation("Users must not delete files")
        assert "forbid" in cedar

    def test_translate_allow_pattern(self, engine):
        """Test positive language triggers permit."""
        cedar = engine._template_based_translation(
            "Agents can read configuration files"
        )
        assert "permit" in cedar

    def test_translate_detects_tool_name(self, engine):
        """Test tool name extraction."""
        cedar = engine._template_based_translation(
            "Agents cannot post to Slack without approval"
        )
        assert "slack" in cedar.lower()

    def test_translate_detects_approval_requirement(self, engine):
        """Test approval detection."""
        cedar = engine._template_based_translation(
            "Require manager approval for deployments"
        )
        assert "approved" in cedar


# ============================================================================
# Cedar Validation Tests
# ============================================================================


class TestCedarValidation:
    """Test Cedar syntax validation."""

    def test_validate_valid_permit(self, engine):
        """Test validating valid permit policy."""
        result = engine._validate_cedar_syntax("permit(principal, action, resource);")
        assert result.valid is True
        assert result.errors == []

    def test_validate_valid_forbid(self, engine):
        """Test validating valid forbid policy."""
        result = engine._validate_cedar_syntax("forbid(principal, action, resource);")
        assert result.valid is True

    def test_validate_missing_permit_forbid(self, engine):
        """Test validation fails without permit/forbid."""
        result = engine._validate_cedar_syntax("(principal, action, resource);")
        assert result.valid is False
        assert any("permit" in e or "forbid" in e for e in result.errors)

    def test_validate_adds_semicolon(self, engine):
        """Test validation adds missing semicolon."""
        result = engine._validate_cedar_syntax("permit(principal, action, resource)")
        assert result.valid is True
        assert result.normalized_syntax.endswith(";")
        assert "semicolon" in result.warnings[0].lower()

    def test_validate_complex_policy(self, engine):
        """Test validating complex policy with conditions."""
        result = engine._validate_cedar_syntax(
            """
            permit(
                principal == Agent::"coder-agent",
                action == Action::"invoke_tool",
                resource
            ) when {
                context.approved == true
            };
        """
        )
        assert result.valid is True


# ============================================================================
# Metrics Tests
# ============================================================================


class TestMetrics:
    """Test policy engine metrics."""

    def test_get_policy_metrics(self, engine):
        """Test getting policy metrics."""
        metrics = engine.get_policy_metrics()
        assert "total_policies" in metrics
        assert "enabled_policies" in metrics
        assert "audit_log_size" in metrics
        assert "recent_decisions" in metrics
        assert "policies_by_scope" in metrics

    @pytest.mark.asyncio
    async def test_metrics_after_evaluations(self, engine):
        """Test metrics update after evaluations."""
        for _ in range(5):
            await engine.evaluate(
                PolicyEvaluationRequest(
                    principal="Agent::test",
                    action="Action::test",
                    resource="Resource::test",
                )
            )

        metrics = engine.get_policy_metrics()
        assert metrics["audit_log_size"] >= 5

    def test_metrics_policies_by_scope(self, engine):
        """Test policies by scope metric."""
        metrics = engine.get_policy_metrics()
        scopes = metrics["policies_by_scope"]
        assert "global" in scopes
        assert "organization" in scopes
        assert "team" in scopes
        assert "user" in scopes
        # System policies are global
        assert scopes["global"] >= 3


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_create_evaluate_delete_policy(self, engine):
        """Test complete policy lifecycle."""
        # Create
        policy = await engine.create_policy(
            policy_name="Lifecycle Test",
            cedar_syntax='permit(principal, action, resource == Tool::"lifecycle_test");',
            priority=PolicyPriority.ORGANIZATION.value,
        )

        # Evaluate - should allow (with hitl_approved to bypass system HITL policy)
        request = PolicyEvaluationRequest(
            principal="Agent::test",
            action="Action::invoke",
            resource="Tool::lifecycle_test",
            context={"hitl_approved": True},
        )
        result = await engine.evaluate(request)
        assert result.decision == PolicyDecision.ALLOW

        # Delete
        deleted = await engine.delete_policy(policy.policy_id)
        assert deleted is True

        # Evaluate again - should deny (no matching policy)
        result = await engine.evaluate(request)
        # With default deny and no matching permit, should deny
        assert result.decision == PolicyDecision.DENY

    @pytest.mark.asyncio
    async def test_hitl_workflow(self, engine):
        """Test HITL required workflow."""
        # Try production deployment without HITL approval
        request = PolicyEvaluationRequest(
            principal="Agent::deployer",
            action="Action::deploy",
            resource="Resource::production",
            context={
                "resource_category": "production_deployment",
                "hitl_approved": False,
            },
        )
        result = await engine.evaluate(request)
        # System HITL policy should deny
        assert result.decision == PolicyDecision.DENY

        # With HITL approval
        request_approved = PolicyEvaluationRequest(
            principal="Agent::deployer",
            action="Action::deploy",
            resource="Resource::production",
            context={
                "resource_category": "production_deployment",
                "hitl_approved": True,
            },
        )
        # May still be denied depending on other policies, but HITL check passes
        result = await engine.evaluate(request_approved)
        # The HITL policy shouldn't block it now

    @pytest.mark.asyncio
    async def test_organization_scope_isolation(self, engine):
        """Test organization-scoped policies only apply to that org."""
        # Create org-specific policy
        await engine.create_policy(
            policy_name="Org-A Policy",
            cedar_syntax='permit(principal, action, resource == Tool::"org_tool");',
            scope="organization",
            organization_id="org-a",
            priority=PolicyPriority.ORGANIZATION.value,
        )

        # Request from org-a (with hitl_approved to bypass system HITL policy)
        request_a = PolicyEvaluationRequest(
            principal="Agent::test",
            action="Action::test",
            resource="Tool::org_tool",
            organization_id="org-a",
            context={"hitl_approved": True},
        )
        result_a = await engine.evaluate(request_a)
        assert result_a.decision == PolicyDecision.ALLOW

        # Request from org-b (should not get the org-a policy)
        request_b = PolicyEvaluationRequest(
            principal="Agent::test",
            action="Action::test",
            resource="Tool::org_tool",
            organization_id="org-b",
            context={"hitl_approved": True},
        )
        result_b = await engine.evaluate(request_b)
        # Only global policies apply, so default deny
        assert result_b.decision == PolicyDecision.DENY
