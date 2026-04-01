"""
Tests for capability governance policy module.

Tests agent policies, tool classifications, and permission evaluation.
"""

import pytest

from src.services.capability_governance.contracts import (
    CapabilityDecision,
    ToolClassification,
)
from src.services.capability_governance.policy import (
    DEFAULT_TOOL_CLASSIFICATIONS,
    AgentCapabilityPolicy,
    get_policy_repository,
    get_tool_classification,
    reset_policy_repository,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def cleanup():
    """Reset singleton after each test."""
    yield
    reset_policy_repository()


@pytest.fixture
def policy_repo():
    """Create a fresh policy repository for each test."""
    reset_policy_repository()
    return get_policy_repository()


# =============================================================================
# DEFAULT_TOOL_CLASSIFICATIONS Tests
# =============================================================================


class TestDefaultToolClassifications:
    """Tests for default tool classifications."""

    def test_classifications_exist(self):
        """Verify default classifications are defined."""
        assert len(DEFAULT_TOOL_CLASSIFICATIONS) > 0

    def test_safe_tools_classified(self):
        """Verify SAFE tools are correctly classified."""
        safe_tools = [
            "semantic_search",
            "describe_tool",
            "list_tools",
            "list_agents",
            "get_agent_status",
        ]
        for tool in safe_tools:
            assert tool in DEFAULT_TOOL_CLASSIFICATIONS
            assert DEFAULT_TOOL_CLASSIFICATIONS[tool] == ToolClassification.SAFE

    def test_monitoring_tools_classified(self):
        """Verify MONITORING tools are correctly classified."""
        monitoring_tools = [
            "query_code_graph",
            "get_code_dependencies",
            "query_audit_logs",
        ]
        for tool in monitoring_tools:
            assert tool in DEFAULT_TOOL_CLASSIFICATIONS
            assert DEFAULT_TOOL_CLASSIFICATIONS[tool] == ToolClassification.MONITORING

    def test_dangerous_tools_classified(self):
        """Verify DANGEROUS tools are correctly classified."""
        dangerous_tools = [
            "index_code_embedding",
            "destroy_sandbox",
            "write_config",
        ]
        for tool in dangerous_tools:
            assert tool in DEFAULT_TOOL_CLASSIFICATIONS
            assert DEFAULT_TOOL_CLASSIFICATIONS[tool] == ToolClassification.DANGEROUS

    def test_critical_tools_classified(self):
        """Verify CRITICAL tools are correctly classified."""
        critical_tools = [
            "provision_sandbox",
            "deploy_to_production",
            "rotate_credentials",
            "modify_iam_policy",
        ]
        for tool in critical_tools:
            assert tool in DEFAULT_TOOL_CLASSIFICATIONS
            assert DEFAULT_TOOL_CLASSIFICATIONS[tool] == ToolClassification.CRITICAL


# =============================================================================
# get_tool_classification Tests
# =============================================================================


class TestGetToolClassification:
    """Tests for get_tool_classification function."""

    def test_known_tool(self):
        """Test getting classification for known tool."""
        assert get_tool_classification("semantic_search") == ToolClassification.SAFE
        assert (
            get_tool_classification("deploy_to_production")
            == ToolClassification.CRITICAL
        )

    def test_unknown_tool_defaults_to_dangerous(self):
        """Test unknown tool defaults to DANGEROUS."""
        assert get_tool_classification("unknown_tool") == ToolClassification.DANGEROUS


# =============================================================================
# AgentCapabilityPolicy Tests
# =============================================================================


class TestAgentCapabilityPolicy:
    """Tests for AgentCapabilityPolicy class."""

    def test_basic_creation(self):
        """Test basic policy creation."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"tool1": ["read", "execute"]},
            denied_tools=["dangerous_tool"],
            allowed_contexts=["sandbox", "test"],
            default_decision=CapabilityDecision.DENY,
        )
        assert policy.agent_type == "TestAgent"
        assert policy.allowed_tools == {"tool1": ["read", "execute"]}
        assert policy.denied_tools == ["dangerous_tool"]

    def test_can_invoke_allowed(self):
        """Test can_invoke for allowed tool."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"tool1": ["read", "execute"]},
            denied_tools=[],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.DENY,
        )
        decision = policy.can_invoke("tool1", "read", "sandbox")
        assert decision == CapabilityDecision.ALLOW

    def test_can_invoke_denied_tool(self):
        """Test can_invoke for explicitly denied tool."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"tool1": ["read"]},
            denied_tools=["dangerous_tool"],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.ESCALATE,
        )
        decision = policy.can_invoke("dangerous_tool", "execute", "sandbox")
        assert decision == CapabilityDecision.DENY

    def test_can_invoke_wrong_action(self):
        """Test can_invoke with wrong action."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"tool1": ["read"]},
            denied_tools=[],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.DENY,
        )
        decision = policy.can_invoke("tool1", "write", "sandbox")
        assert decision == CapabilityDecision.DENY

    def test_can_invoke_wrong_context(self):
        """Test can_invoke in wrong context."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"tool1": ["read"]},
            denied_tools=[],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.DENY,
        )
        decision = policy.can_invoke("tool1", "read", "production")
        assert decision == CapabilityDecision.DENY

    def test_can_invoke_unknown_tool_default_deny(self):
        """Test can_invoke for unknown tool with DENY default."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"tool1": ["read"]},
            denied_tools=[],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.DENY,
        )
        # Unknown DANGEROUS tool
        decision = policy.can_invoke("unknown_dangerous_tool", "read", "sandbox")
        assert decision == CapabilityDecision.DENY

    def test_can_invoke_unknown_tool_default_escalate(self):
        """Test can_invoke for unknown tool with ESCALATE default."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"tool1": ["read"]},
            denied_tools=[],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.ESCALATE,
        )
        # Unknown DANGEROUS tool with ESCALATE default
        decision = policy.can_invoke("unknown_dangerous_tool", "read", "sandbox")
        assert decision == CapabilityDecision.ESCALATE

    def test_can_invoke_wildcard_actions(self):
        """Test can_invoke with wildcard actions."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"admin_tool": ["*"]},
            denied_tools=[],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.DENY,
        )
        assert (
            policy.can_invoke("admin_tool", "read", "sandbox")
            == CapabilityDecision.ALLOW
        )
        assert (
            policy.can_invoke("admin_tool", "write", "sandbox")
            == CapabilityDecision.ALLOW
        )
        assert (
            policy.can_invoke("admin_tool", "delete", "sandbox")
            == CapabilityDecision.ALLOW
        )

    def test_for_agent_type_coder(self):
        """Test getting policy for CoderAgent."""
        policy = AgentCapabilityPolicy.for_agent_type("CoderAgent")
        assert policy.agent_type == "CoderAgent"
        assert "semantic_search" in policy.allowed_tools

    def test_for_agent_type_unknown(self):
        """Test getting policy for unknown agent type."""
        policy = AgentCapabilityPolicy.for_agent_type("UnknownAgent")
        assert policy.agent_type == "UnknownAgent"
        assert policy.default_decision == CapabilityDecision.DENY

    def test_get_rate_limit(self):
        """Test get_rate_limit method."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            global_rate_limit=100,
            tool_rate_limits={"fast_tool": 200},
        )
        assert policy.get_rate_limit("fast_tool") == 200
        assert policy.get_rate_limit("other_tool") == 100

    def test_with_override(self):
        """Test creating policy with overrides."""
        base_policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"tool1": ["read"]},
            denied_tools=[],
            allowed_contexts=["sandbox"],
        )
        overridden = base_policy.with_override(
            allowed_tools={"tool2": ["write"]},
            denied_tools=["blocked_tool"],
        )

        assert "tool1" in overridden.allowed_tools
        assert "tool2" in overridden.allowed_tools
        assert "blocked_tool" in overridden.denied_tools

    def test_to_dict(self):
        """Test dictionary conversion."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"tool1": ["read"]},
            denied_tools=["dangerous_tool"],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.DENY,
        )
        d = policy.to_dict()
        assert d["agent_type"] == "TestAgent"
        assert d["allowed_tools"] == {"tool1": ["read"]}
        assert d["denied_tools"] == ["dangerous_tool"]

    def test_from_dict(self):
        """Test creating policy from dictionary."""
        data = {
            "agent_type": "TestAgent",
            "allowed_tools": {"tool1": ["read"]},
            "denied_tools": ["dangerous_tool"],
            "allowed_contexts": ["sandbox"],
            "default_decision": "deny",
        }
        policy = AgentCapabilityPolicy.from_dict(data)
        assert policy.agent_type == "TestAgent"
        assert policy.default_decision == CapabilityDecision.DENY


# =============================================================================
# PolicyRepository Tests
# =============================================================================


class TestPolicyRepository:
    """Tests for PolicyRepository class."""

    def test_initialization(self, policy_repo):
        """Test policy repository initialization."""
        assert policy_repo is not None

    def test_get_policy(self, policy_repo):
        """Test getting a policy."""
        policy = policy_repo.get_policy("CoderAgent")
        assert policy.agent_type == "CoderAgent"

    def test_get_policy_unknown(self, policy_repo):
        """Test getting policy for unknown agent."""
        policy = policy_repo.get_policy("UnknownAgent")
        assert policy.agent_type == "UnknownAgent"
        assert policy.default_decision == CapabilityDecision.DENY

    def test_set_custom_policy(self, policy_repo):
        """Test setting a custom policy."""
        custom_policy = AgentCapabilityPolicy(
            agent_type="CustomAgent",
            allowed_tools={"custom_tool": ["read"]},
            denied_tools=[],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.DENY,
        )
        policy_repo.set_custom_policy("CustomAgent", custom_policy)

        retrieved = policy_repo.get_policy("CustomAgent")
        assert retrieved.allowed_tools == {"custom_tool": ["read"]}

    def test_list_policies(self, policy_repo):
        """Test listing agent types."""
        types = policy_repo.list_policies()
        assert "CoderAgent" in types
        assert "ReviewerAgent" in types
        assert "SecurityAgent" in types

    def test_clear_cache(self, policy_repo):
        """Test clearing policy cache."""
        # Get a policy to populate cache
        policy_repo.get_policy("CoderAgent")
        assert len(policy_repo._policy_cache) > 0

        # Clear cache
        policy_repo.clear_cache()
        assert len(policy_repo._policy_cache) == 0


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for global singleton."""

    def test_get_policy_repository(self):
        """Test getting global repository."""
        reset_policy_repository()
        r1 = get_policy_repository()
        r2 = get_policy_repository()
        assert r1 is r2

    def test_reset_policy_repository(self):
        """Test resetting global repository."""
        r1 = get_policy_repository()
        reset_policy_repository()
        r2 = get_policy_repository()
        assert r1 is not r2


# =============================================================================
# Agent-Specific Policy Tests
# =============================================================================


class TestAgentSpecificPolicies:
    """Tests for specific agent policies."""

    def test_coder_agent_capabilities(self, policy_repo):
        """Test CoderAgent capabilities."""
        policy = policy_repo.get_policy("CoderAgent")

        # Should be able to search
        assert (
            policy.can_invoke("semantic_search", "execute", "sandbox")
            == CapabilityDecision.ALLOW
        )

        # Should be able to query code graph
        assert (
            policy.can_invoke("query_code_graph", "read", "sandbox")
            == CapabilityDecision.ALLOW
        )

        # Should NOT be able to deploy (explicitly denied)
        assert (
            policy.can_invoke("deploy_to_production", "execute", "sandbox")
            == CapabilityDecision.DENY
        )

    def test_reviewer_agent_capabilities(self, policy_repo):
        """Test ReviewerAgent capabilities."""
        policy = policy_repo.get_policy("ReviewerAgent")

        # Should be able to query code graph
        assert (
            policy.can_invoke("query_code_graph", "read", "sandbox")
            == CapabilityDecision.ALLOW
        )

        # Should NOT be able to commit (explicitly denied)
        assert (
            policy.can_invoke("commit_changes", "execute", "sandbox")
            == CapabilityDecision.DENY
        )

    def test_security_agent_capabilities(self, policy_repo):
        """Test SecurityAgent capabilities."""
        policy = policy_repo.get_policy("SecurityAgent")

        # Should be able to query audit logs
        assert (
            policy.can_invoke("query_audit_logs", "read", "sandbox")
            == CapabilityDecision.ALLOW
        )

        # Should be able to get vulnerability reports
        assert (
            policy.can_invoke("get_vulnerability_report", "read", "sandbox")
            == CapabilityDecision.ALLOW
        )

    def test_meta_orchestrator_capabilities(self, policy_repo):
        """Test MetaOrchestrator capabilities."""
        policy = policy_repo.get_policy("MetaOrchestrator")

        # Should be able to manage agents
        assert (
            policy.can_invoke("list_agents", "read", "sandbox")
            == CapabilityDecision.ALLOW
        )
        assert (
            policy.can_invoke("get_agent_status", "read", "sandbox")
            == CapabilityDecision.ALLOW
        )

    def test_red_team_agent_capabilities(self, policy_repo):
        """Test RedTeamAgent capabilities."""
        policy = policy_repo.get_policy("RedTeamAgent")

        # Should be able to provision sandbox
        assert (
            policy.can_invoke("provision_sandbox", "execute", "sandbox")
            == CapabilityDecision.ALLOW
        )

        # Should NOT be able to access secrets
        assert (
            policy.can_invoke("access_secrets", "read", "sandbox")
            == CapabilityDecision.DENY
        )


# =============================================================================
# Classification-Based Default Tests
# =============================================================================


class TestClassificationBasedDefaults:
    """Tests for classification-based default decisions."""

    def test_safe_tool_default_allow(self):
        """Test that SAFE tools are allowed by default."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={},  # No explicit allowances
            denied_tools=[],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.DENY,
        )
        # semantic_search is SAFE
        decision = policy.can_invoke("semantic_search", "read", "sandbox")
        assert decision == CapabilityDecision.ALLOW

    def test_monitoring_tool_default_audit_only(self):
        """Test that MONITORING tools get AUDIT_ONLY by default."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={},
            denied_tools=[],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.DENY,
        )
        # query_code_graph is MONITORING
        decision = policy.can_invoke("query_code_graph", "read", "sandbox")
        assert decision == CapabilityDecision.AUDIT_ONLY

    def test_critical_tool_default_escalate(self):
        """Test that CRITICAL tools get ESCALATE by default."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={},
            denied_tools=[],
            allowed_contexts=["sandbox"],
            default_decision=CapabilityDecision.DENY,
        )
        # deploy_to_production is CRITICAL
        decision = policy.can_invoke("deploy_to_production", "execute", "sandbox")
        assert decision == CapabilityDecision.ESCALATE
