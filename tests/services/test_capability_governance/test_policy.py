"""
Tests for capability governance policies.

Tests AgentCapabilityPolicy, PolicyRepository, and default policy configurations.
"""

import pytest

from src.services.capability_governance.contracts import CapabilityDecision
from src.services.capability_governance.policy import (
    DEFAULT_TOOL_CLASSIFICATIONS,
    AgentCapabilityPolicy,
    PolicyRepository,
    get_policy_repository,
    get_tool_classification,
)


class TestToolClassifications:
    """Test default tool classifications."""

    def test_safe_tools_classified(self):
        """Verify SAFE tools are correctly classified."""
        safe_tools = [
            "semantic_search",
            "describe_tool",
            "get_sandbox_status",
            "list_tools",
        ]
        for tool in safe_tools:
            from src.services.capability_governance.contracts import ToolClassification

            assert DEFAULT_TOOL_CLASSIFICATIONS[tool] == ToolClassification.SAFE

    def test_monitoring_tools_classified(self):
        """Verify MONITORING tools are correctly classified."""
        from src.services.capability_governance.contracts import ToolClassification

        monitoring_tools = [
            "query_code_graph",
            "get_code_dependencies",
            "get_agent_metrics",
        ]
        for tool in monitoring_tools:
            assert DEFAULT_TOOL_CLASSIFICATIONS[tool] == ToolClassification.MONITORING

    def test_dangerous_tools_classified(self):
        """Verify DANGEROUS tools are correctly classified."""
        from src.services.capability_governance.contracts import ToolClassification

        dangerous_tools = [
            "index_code_embedding",
            "destroy_sandbox",
            "write_config",
            "delete_index",
        ]
        for tool in dangerous_tools:
            assert DEFAULT_TOOL_CLASSIFICATIONS[tool] == ToolClassification.DANGEROUS

    def test_critical_tools_classified(self):
        """Verify CRITICAL tools are correctly classified."""
        from src.services.capability_governance.contracts import ToolClassification

        critical_tools = [
            "provision_sandbox",
            "deploy_to_production",
            "rotate_credentials",
            "modify_iam_policy",
        ]
        for tool in critical_tools:
            assert DEFAULT_TOOL_CLASSIFICATIONS[tool] == ToolClassification.CRITICAL

    def test_get_tool_classification_known(self):
        """Test getting classification for known tools."""
        from src.services.capability_governance.contracts import ToolClassification

        assert get_tool_classification("semantic_search") == ToolClassification.SAFE
        assert (
            get_tool_classification("query_code_graph") == ToolClassification.MONITORING
        )
        assert (
            get_tool_classification("destroy_sandbox") == ToolClassification.DANGEROUS
        )
        assert (
            get_tool_classification("deploy_to_production")
            == ToolClassification.CRITICAL
        )

    def test_get_tool_classification_unknown(self):
        """Test default classification for unknown tools."""
        from src.services.capability_governance.contracts import ToolClassification

        assert get_tool_classification("unknown_tool") == ToolClassification.DANGEROUS


class TestAgentCapabilityPolicy:
    """Test AgentCapabilityPolicy dataclass."""

    def test_creation_defaults(self):
        """Test creating policy with defaults."""
        policy = AgentCapabilityPolicy(agent_type="TestAgent")
        assert policy.agent_type == "TestAgent"
        assert policy.version == "1.0"
        assert policy.default_decision == CapabilityDecision.DENY
        assert policy.can_elevate_children is False
        assert "test" in policy.allowed_contexts
        assert "sandbox" in policy.allowed_contexts

    def test_creation_custom(self):
        """Test creating policy with custom values."""
        policy = AgentCapabilityPolicy(
            agent_type="CustomAgent",
            version="2.0",
            allowed_tools={"tool1": ["read"], "tool2": ["*"]},
            denied_tools=["dangerous_tool"],
            allowed_contexts=["production"],
            default_decision=CapabilityDecision.ESCALATE,
            can_elevate_children=True,
            global_rate_limit=200,
        )
        assert policy.version == "2.0"
        assert policy.can_elevate_children is True
        assert policy.global_rate_limit == 200

    def test_can_invoke_allowed_tool(self):
        """Test can_invoke for explicitly allowed tool."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"semantic_search": ["read", "execute"]},
        )
        result = policy.can_invoke("semantic_search", "execute", "development")
        assert result == CapabilityDecision.ALLOW

    def test_can_invoke_denied_tool(self):
        """Test can_invoke for explicitly denied tool."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            denied_tools=["dangerous_tool"],
        )
        result = policy.can_invoke("dangerous_tool", "execute", "development")
        assert result == CapabilityDecision.DENY

    def test_can_invoke_wrong_action(self):
        """Test can_invoke for tool with wrong action."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"semantic_search": ["read"]},
        )
        result = policy.can_invoke("semantic_search", "execute", "development")
        assert result == CapabilityDecision.DENY

    def test_can_invoke_wildcard_action(self):
        """Test can_invoke for tool with wildcard action."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"semantic_search": ["*"]},
        )
        assert (
            policy.can_invoke("semantic_search", "read", "development")
            == CapabilityDecision.ALLOW
        )
        assert (
            policy.can_invoke("semantic_search", "execute", "development")
            == CapabilityDecision.ALLOW
        )
        assert (
            policy.can_invoke("semantic_search", "admin", "development")
            == CapabilityDecision.ALLOW
        )

    def test_can_invoke_blocked_context(self):
        """Test can_invoke for tool in blocked context."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"semantic_search": ["execute"]},
            allowed_contexts=["development", "test"],
        )
        result = policy.can_invoke("semantic_search", "execute", "production")
        assert result == CapabilityDecision.DENY

    def test_can_invoke_safe_tool_default(self):
        """Test can_invoke uses SAFE classification default."""
        policy = AgentCapabilityPolicy(agent_type="TestAgent")
        # semantic_search is classified as SAFE
        result = policy.can_invoke("semantic_search", "execute", "development")
        assert result == CapabilityDecision.ALLOW

    def test_can_invoke_monitoring_tool_default(self):
        """Test can_invoke uses MONITORING classification default."""
        policy = AgentCapabilityPolicy(agent_type="TestAgent")
        # query_code_graph is classified as MONITORING
        result = policy.can_invoke("query_code_graph", "read", "development")
        assert result == CapabilityDecision.AUDIT_ONLY

    def test_can_invoke_critical_tool_default(self):
        """Test can_invoke uses CRITICAL classification default."""
        policy = AgentCapabilityPolicy(agent_type="TestAgent")
        # deploy_to_production is classified as CRITICAL
        result = policy.can_invoke("deploy_to_production", "execute", "development")
        assert result == CapabilityDecision.ESCALATE

    def test_can_invoke_dangerous_tool_default(self):
        """Test can_invoke uses default_decision for DANGEROUS tools."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            default_decision=CapabilityDecision.DENY,
        )
        # index_code_embedding is classified as DANGEROUS
        result = policy.can_invoke("index_code_embedding", "execute", "development")
        assert result == CapabilityDecision.DENY

    def test_can_invoke_tool_context_constraint(self):
        """Test can_invoke with tool-specific context constraint."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"special_tool": ["execute"]},
            constraints={"special_tool_context": ["test"]},
        )
        # Should be allowed only in test context
        assert (
            policy.can_invoke("special_tool", "execute", "test")
            == CapabilityDecision.ALLOW
        )
        assert (
            policy.can_invoke("special_tool", "execute", "development")
            == CapabilityDecision.DENY
        )

    def test_get_rate_limit_global(self):
        """Test get_rate_limit returns global limit."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            global_rate_limit=100,
        )
        assert policy.get_rate_limit("any_tool") == 100

    def test_get_rate_limit_tool_specific(self):
        """Test get_rate_limit returns tool-specific limit."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            global_rate_limit=100,
            tool_rate_limits={"special_tool": 10},
        )
        assert policy.get_rate_limit("special_tool") == 10
        assert policy.get_rate_limit("other_tool") == 100

    def test_with_override(self):
        """Test creating policy override."""
        base = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"tool1": ["read"]},
            denied_tools=["bad_tool"],
            allowed_contexts=["development"],
        )
        override = base.with_override(
            allowed_tools={"tool2": ["execute"]},
            denied_tools=["another_bad_tool"],
        )
        # Original policy unchanged
        assert "tool2" not in base.allowed_tools
        # Override has both
        assert "tool1" in override.allowed_tools
        assert "tool2" in override.allowed_tools
        assert "bad_tool" in override.denied_tools
        assert "another_bad_tool" in override.denied_tools
        assert override.parent_policy == "TestAgent"

    def test_to_dict(self):
        """Test converting policy to dictionary."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            version="1.0",
            allowed_tools={"tool1": ["read"]},
        )
        d = policy.to_dict()
        assert d["agent_type"] == "TestAgent"
        assert d["version"] == "1.0"
        assert d["allowed_tools"] == {"tool1": ["read"]}
        assert d["default_decision"] == "deny"

    def test_from_dict(self):
        """Test creating policy from dictionary."""
        data = {
            "agent_type": "TestAgent",
            "version": "2.0",
            "allowed_tools": {"tool1": ["execute"]},
            "denied_tools": ["bad_tool"],
            "allowed_contexts": ["production"],
            "default_decision": "escalate",
            "can_elevate_children": True,
        }
        policy = AgentCapabilityPolicy.from_dict(data)
        assert policy.agent_type == "TestAgent"
        assert policy.version == "2.0"
        assert policy.can_elevate_children is True
        assert policy.default_decision == CapabilityDecision.ESCALATE


class TestDefaultAgentPolicies:
    """Test default policies for each agent type."""

    def test_coder_agent_policy(self, coder_policy: AgentCapabilityPolicy):
        """Test CoderAgent default policy."""
        assert coder_policy.agent_type == "CoderAgent"
        # Should allow semantic search
        assert (
            coder_policy.can_invoke("semantic_search", "execute", "development")
            == CapabilityDecision.ALLOW
        )
        # Should deny provision_sandbox
        assert (
            coder_policy.can_invoke("provision_sandbox", "execute", "development")
            == CapabilityDecision.DENY
        )
        # Should deny production context
        assert (
            coder_policy.can_invoke("semantic_search", "execute", "production")
            == CapabilityDecision.DENY
        )

    def test_reviewer_agent_policy(self, reviewer_policy: AgentCapabilityPolicy):
        """Test ReviewerAgent default policy."""
        assert reviewer_policy.agent_type == "ReviewerAgent"
        # Should allow query_code_graph
        assert (
            reviewer_policy.can_invoke("query_code_graph", "read", "development")
            == CapabilityDecision.ALLOW
        )
        # Should deny index_code_embedding
        assert (
            reviewer_policy.can_invoke("index_code_embedding", "execute", "development")
            == CapabilityDecision.DENY
        )
        # Should deny commit_changes
        assert (
            reviewer_policy.can_invoke("commit_changes", "execute", "development")
            == CapabilityDecision.DENY
        )

    def test_orchestrator_policy(self, orchestrator_policy: AgentCapabilityPolicy):
        """Test MetaOrchestrator default policy."""
        assert orchestrator_policy.agent_type == "MetaOrchestrator"
        assert orchestrator_policy.can_elevate_children is True
        # Should allow production context
        assert (
            orchestrator_policy.can_invoke("semantic_search", "execute", "production")
            == CapabilityDecision.ALLOW
        )
        # Should escalate critical operations
        assert (
            orchestrator_policy.can_invoke(
                "deploy_to_production", "execute", "production"
            )
            == CapabilityDecision.ESCALATE
        )

    def test_redteam_agent_policy(self, redteam_policy: AgentCapabilityPolicy):
        """Test RedTeamAgent default policy."""
        assert redteam_policy.agent_type == "RedTeamAgent"
        # Should allow provision_sandbox in sandbox context
        assert (
            redteam_policy.can_invoke("provision_sandbox", "execute", "sandbox")
            == CapabilityDecision.ALLOW
        )
        # Should deny deploy_to_production
        assert (
            redteam_policy.can_invoke("deploy_to_production", "execute", "sandbox")
            == CapabilityDecision.DENY
        )
        # Should deny production context
        assert (
            redteam_policy.can_invoke("provision_sandbox", "execute", "production")
            == CapabilityDecision.DENY
        )

    def test_validator_agent_policy(self):
        """Test ValidatorAgent default policy."""
        policy = AgentCapabilityPolicy.for_agent_type("ValidatorAgent")
        assert policy.agent_type == "ValidatorAgent"
        # Should only allow test and sandbox contexts
        assert "test" in policy.allowed_contexts
        assert "sandbox" in policy.allowed_contexts
        assert "development" not in policy.allowed_contexts

    def test_admin_agent_policy(self):
        """Test AdminAgent default policy."""
        policy = AgentCapabilityPolicy.for_agent_type("AdminAgent")
        assert policy.agent_type == "AdminAgent"
        assert policy.can_elevate_children is True
        # Should allow provision_sandbox
        assert (
            policy.can_invoke("provision_sandbox", "execute", "development")
            == CapabilityDecision.ALLOW
        )

    def test_security_agent_policy(self):
        """Test SecurityAgent default policy."""
        policy = AgentCapabilityPolicy.for_agent_type("SecurityAgent")
        assert policy.agent_type == "SecurityAgent"
        # Should allow query_audit_logs
        assert (
            policy.can_invoke("query_audit_logs", "read", "production")
            == CapabilityDecision.ALLOW
        )
        # Should deny provision_sandbox
        assert (
            policy.can_invoke("provision_sandbox", "execute", "production")
            == CapabilityDecision.DENY
        )

    def test_documentation_agent_policy(self):
        """Test DocumentationAgent default policy."""
        policy = AgentCapabilityPolicy.for_agent_type("DocumentationAgent")
        assert policy.agent_type == "DocumentationAgent"
        # Should allow get_documentation
        assert (
            policy.can_invoke("get_documentation", "read", "development")
            == CapabilityDecision.ALLOW
        )
        # Should deny commit_changes
        assert (
            policy.can_invoke("commit_changes", "execute", "development")
            == CapabilityDecision.DENY
        )

    def test_unknown_agent_policy(self):
        """Test default policy for unknown agent type."""
        policy = AgentCapabilityPolicy.for_agent_type("UnknownAgent")
        assert policy.agent_type == "UnknownAgent"
        assert policy.default_decision == CapabilityDecision.DENY


class TestPolicyRepository:
    """Test PolicyRepository."""

    def test_get_policy_default(self):
        """Test getting default policy."""
        repo = PolicyRepository()
        policy = repo.get_policy("CoderAgent")
        assert policy.agent_type == "CoderAgent"

    def test_get_policy_cached(self):
        """Test policy caching."""
        repo = PolicyRepository()
        policy1 = repo.get_policy("CoderAgent")
        policy2 = repo.get_policy("CoderAgent")
        assert policy1 is policy2

    def test_set_custom_policy(self):
        """Test setting custom policy."""
        repo = PolicyRepository()
        custom = AgentCapabilityPolicy(
            agent_type="CoderAgent",
            version="custom",
            allowed_tools={"custom_tool": ["execute"]},
        )
        repo.set_custom_policy("CoderAgent", custom)
        policy = repo.get_policy("CoderAgent")
        assert policy.version == "custom"
        assert "custom_tool" in policy.allowed_tools

    def test_set_custom_policy_invalidates_cache(self):
        """Test that setting custom policy invalidates cache."""
        repo = PolicyRepository()
        # First get default
        default = repo.get_policy("CoderAgent")
        assert default.version == "1.0"
        # Set custom
        custom = AgentCapabilityPolicy(
            agent_type="CoderAgent",
            version="custom",
        )
        repo.set_custom_policy("CoderAgent", custom)
        # Get should return custom
        policy = repo.get_policy("CoderAgent")
        assert policy.version == "custom"

    def test_clear_cache(self):
        """Test clearing cache."""
        repo = PolicyRepository()
        # Populate cache
        repo.get_policy("CoderAgent")
        repo.get_policy("ReviewerAgent")
        assert len(repo._policy_cache) == 2
        # Clear
        repo.clear_cache()
        assert len(repo._policy_cache) == 0

    def test_list_policies(self):
        """Test listing available policies."""
        repo = PolicyRepository()
        policies = repo.list_policies()
        assert "CoderAgent" in policies
        assert "ReviewerAgent" in policies
        assert "MetaOrchestrator" in policies

    def test_list_policies_includes_custom(self):
        """Test listing includes custom policies."""
        repo = PolicyRepository()
        custom = AgentCapabilityPolicy(agent_type="CustomAgent")
        repo.set_custom_policy("CustomAgent", custom)
        policies = repo.list_policies()
        assert "CustomAgent" in policies

    def test_get_policy_repository_singleton(self):
        """Test global repository singleton."""
        repo1 = get_policy_repository()
        repo2 = get_policy_repository()
        assert repo1 is repo2


class TestPolicySecurityBehaviors:
    """Test security-related policy behaviors."""

    def test_denial_priority_over_allowance(self):
        """Test that explicit denial takes priority over allowance."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"tool1": ["execute"]},
            denied_tools=["tool1"],  # Both allowed and denied
        )
        # Denial should win
        result = policy.can_invoke("tool1", "execute", "development")
        assert result == CapabilityDecision.DENY

    def test_context_restriction_priority(self):
        """Test that context restriction is checked early."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"tool1": ["execute"]},
            allowed_contexts=["development"],
        )
        # Even allowed tool should be blocked in wrong context
        result = policy.can_invoke("tool1", "execute", "production")
        assert result == CapabilityDecision.DENY

    def test_unknown_tools_default_dangerous(self):
        """Test that unknown tools are treated as dangerous."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            default_decision=CapabilityDecision.DENY,
        )
        # Unknown tool should use default decision
        result = policy.can_invoke("completely_unknown_tool", "execute", "development")
        assert result == CapabilityDecision.DENY

    @pytest.mark.parametrize(
        "agent_type,tool,expected",
        [
            ("CoderAgent", "semantic_search", CapabilityDecision.ALLOW),
            ("CoderAgent", "provision_sandbox", CapabilityDecision.DENY),
            ("ReviewerAgent", "query_code_graph", CapabilityDecision.ALLOW),
            ("ReviewerAgent", "index_code_embedding", CapabilityDecision.DENY),
            ("ValidatorAgent", "get_sandbox_status", CapabilityDecision.ALLOW),
            ("MetaOrchestrator", "index_code_embedding", CapabilityDecision.ALLOW),
            ("RedTeamAgent", "provision_sandbox", CapabilityDecision.ALLOW),
            ("AdminAgent", "provision_sandbox", CapabilityDecision.ALLOW),
        ],
    )
    def test_default_policy_decisions(
        self,
        agent_type: str,
        tool: str,
        expected: CapabilityDecision,
    ):
        """Test default policy decisions for various agent-tool combinations."""
        policy = AgentCapabilityPolicy.for_agent_type(agent_type)
        # Use appropriate context for each agent
        context = (
            "sandbox"
            if agent_type in ("ValidatorAgent", "RedTeamAgent")
            else "development"
        )
        result = policy.can_invoke(
            tool,
            (
                "execute"
                if "execute" in policy.allowed_tools.get(tool, ["execute"])
                else "read"
            ),
            context,
        )
        assert result == expected
