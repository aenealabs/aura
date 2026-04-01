"""
Project Aura - Agent Capability Policies

Defines per-agent-type capability policies that govern tool access.
Implements ADR-066 for principle of least privilege.

Policy Hierarchy:
1. Explicit denials (always enforced)
2. Dynamic grants (HITL-approved temporary access)
3. Explicit allowances (configured per-agent-type)
4. Tool classification defaults (SAFE=allow, CRITICAL=escalate)
5. Default decision (typically DENY)

Security Rationale:
- Default-deny ensures new tools require explicit configuration
- Context restrictions prevent cross-environment leakage
- Parent capability inheritance prevents privilege escalation

Author: Project Aura Team
Created: 2026-01-26
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .contracts import CapabilityDecision, ToolClassification

logger = logging.getLogger(__name__)


# =============================================================================
# Default Tool Classifications
# =============================================================================

DEFAULT_TOOL_CLASSIFICATIONS: dict[str, ToolClassification] = {
    # Level 1: SAFE - Read-only, no side effects
    "semantic_search": ToolClassification.SAFE,
    "describe_tool": ToolClassification.SAFE,
    "get_sandbox_status": ToolClassification.SAFE,
    "list_tools": ToolClassification.SAFE,
    "list_agents": ToolClassification.SAFE,
    "get_agent_status": ToolClassification.SAFE,
    "get_task_status": ToolClassification.SAFE,
    "describe_schema": ToolClassification.SAFE,
    "get_documentation": ToolClassification.SAFE,
    # Level 2: MONITORING - Read access to sensitive data
    "query_code_graph": ToolClassification.MONITORING,
    "get_code_dependencies": ToolClassification.MONITORING,
    "get_agent_metrics": ToolClassification.MONITORING,
    "query_audit_logs": ToolClassification.MONITORING,
    "get_vulnerability_report": ToolClassification.MONITORING,
    "analyze_code_complexity": ToolClassification.MONITORING,
    "get_test_coverage": ToolClassification.MONITORING,
    "query_embeddings": ToolClassification.MONITORING,
    # Level 3: DANGEROUS - Write operations, state changes
    "index_code_embedding": ToolClassification.DANGEROUS,
    "destroy_sandbox": ToolClassification.DANGEROUS,
    "write_config": ToolClassification.DANGEROUS,
    "delete_index": ToolClassification.DANGEROUS,
    "create_branch": ToolClassification.DANGEROUS,
    "commit_changes": ToolClassification.DANGEROUS,
    "merge_branch": ToolClassification.DANGEROUS,
    "modify_workflow": ToolClassification.DANGEROUS,
    "update_policy": ToolClassification.DANGEROUS,
    "terminate_agent": ToolClassification.DANGEROUS,
    # Level 4: CRITICAL - Production impact, irreversible
    "provision_sandbox": ToolClassification.CRITICAL,
    "deploy_to_production": ToolClassification.CRITICAL,
    "rotate_credentials": ToolClassification.CRITICAL,
    "modify_iam_policy": ToolClassification.CRITICAL,
    "delete_repository": ToolClassification.CRITICAL,
    "execute_arbitrary_code": ToolClassification.CRITICAL,
    "access_secrets": ToolClassification.CRITICAL,
    "modify_security_groups": ToolClassification.CRITICAL,
    "create_iam_user": ToolClassification.CRITICAL,
    "delete_data": ToolClassification.CRITICAL,
}


def get_tool_classification(tool_name: str) -> ToolClassification:
    """
    Get classification for a tool, defaulting to DANGEROUS for unknown tools.

    Args:
        tool_name: Name of the tool

    Returns:
        ToolClassification for the tool
    """
    return DEFAULT_TOOL_CLASSIFICATIONS.get(tool_name, ToolClassification.DANGEROUS)


# =============================================================================
# Agent Capability Policy
# =============================================================================


@dataclass
class AgentCapabilityPolicy:
    """
    Capability policy for an agent type.

    Defines which tools an agent can access, under what conditions,
    and what actions are permitted.

    Example:
        policy = AgentCapabilityPolicy.for_agent_type("CoderAgent")
        decision = policy.can_invoke("semantic_search", "execute", "development")
        # Returns CapabilityDecision.ALLOW
    """

    agent_type: str
    version: str = "1.0"
    description: str = ""

    # Tool permissions: tool_name -> list of allowed actions
    allowed_tools: dict[str, list[str]] = field(default_factory=dict)

    # Tools explicitly denied (overrides allowed_tools)
    denied_tools: list[str] = field(default_factory=list)

    # Context restrictions
    allowed_contexts: list[str] = field(
        default_factory=lambda: ["test", "sandbox", "development"]
    )

    # Escalation behavior for unspecified tools
    default_decision: CapabilityDecision = CapabilityDecision.DENY

    # Can this agent spawn children with elevated permissions?
    can_elevate_children: bool = False

    # Maximum tool invocations per minute (global across all tools)
    global_rate_limit: int = 100

    # Per-tool rate limits (overrides global)
    tool_rate_limits: dict[str, int] = field(default_factory=dict)

    # Custom constraints (agent-specific restrictions)
    constraints: dict[str, Any] = field(default_factory=dict)

    # Parent policy reference (for inheritance)
    parent_policy: Optional[str] = None

    def can_invoke(
        self,
        tool_name: str,
        action: str,
        context: str,
    ) -> CapabilityDecision:
        """
        Check if this policy allows invoking a tool.

        Evaluation order:
        1. Explicit denial check
        2. Context restriction check
        3. Explicit allowance check
        4. Tool classification-based defaults
        5. Default decision

        Args:
            tool_name: Name of the tool to invoke
            action: Action type (read, write, execute, admin)
            context: Execution context (test, sandbox, production)

        Returns:
            CapabilityDecision indicating if invocation is allowed
        """
        # 1. Check explicit denials first (highest priority)
        if tool_name in self.denied_tools:
            logger.debug(f"Policy {self.agent_type}: {tool_name} explicitly denied")
            return CapabilityDecision.DENY

        # 2. Check context restrictions
        if context not in self.allowed_contexts:
            logger.debug(
                f"Policy {self.agent_type}: context '{context}' not in allowed "
                f"contexts {self.allowed_contexts}"
            )
            return CapabilityDecision.DENY

        # 3. Check explicit allowances
        if tool_name in self.allowed_tools:
            allowed_actions = self.allowed_tools[tool_name]
            if action in allowed_actions or "*" in allowed_actions:
                # Check tool-specific context constraints
                if self._check_tool_context_constraints(tool_name, context):
                    return CapabilityDecision.ALLOW
                return CapabilityDecision.DENY
            logger.debug(
                f"Policy {self.agent_type}: action '{action}' not in allowed "
                f"actions {allowed_actions} for {tool_name}"
            )
            return CapabilityDecision.DENY

        # 4. Check tool classification for default behavior
        classification = get_tool_classification(tool_name)

        if classification == ToolClassification.SAFE:
            return CapabilityDecision.ALLOW
        elif classification == ToolClassification.MONITORING:
            return CapabilityDecision.AUDIT_ONLY
        elif classification == ToolClassification.CRITICAL:
            return CapabilityDecision.ESCALATE
        else:  # DANGEROUS
            return self.default_decision

    def _check_tool_context_constraints(self, tool_name: str, context: str) -> bool:
        """
        Check tool-specific context constraints.

        Some tools may be allowed but only in certain contexts.
        """
        constraint_key = f"{tool_name}_context"
        if constraint_key in self.constraints:
            allowed_contexts = self.constraints[constraint_key]
            return context in allowed_contexts
        return True

    def get_rate_limit(self, tool_name: str) -> int:
        """Get rate limit for a specific tool."""
        return self.tool_rate_limits.get(tool_name, self.global_rate_limit)

    def with_override(
        self,
        allowed_tools: Optional[dict[str, list[str]]] = None,
        denied_tools: Optional[list[str]] = None,
        allowed_contexts: Optional[list[str]] = None,
    ) -> "AgentCapabilityPolicy":
        """
        Create a new policy with overrides applied.

        Useful for creating temporary policy modifications without
        altering the base policy.

        Args:
            allowed_tools: Additional allowed tools
            denied_tools: Additional denied tools
            allowed_contexts: Override allowed contexts

        Returns:
            New AgentCapabilityPolicy with overrides
        """
        new_allowed = dict(self.allowed_tools)
        if allowed_tools:
            new_allowed.update(allowed_tools)

        new_denied = list(self.denied_tools)
        if denied_tools:
            new_denied.extend(denied_tools)

        new_contexts = (
            allowed_contexts if allowed_contexts else list(self.allowed_contexts)
        )

        return AgentCapabilityPolicy(
            agent_type=self.agent_type,
            version=f"{self.version}-override",
            description=f"Override of {self.description}",
            allowed_tools=new_allowed,
            denied_tools=new_denied,
            allowed_contexts=new_contexts,
            default_decision=self.default_decision,
            can_elevate_children=self.can_elevate_children,
            global_rate_limit=self.global_rate_limit,
            tool_rate_limits=dict(self.tool_rate_limits),
            constraints=dict(self.constraints),
            parent_policy=self.agent_type,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert policy to dictionary for serialization."""
        return {
            "agent_type": self.agent_type,
            "version": self.version,
            "description": self.description,
            "allowed_tools": self.allowed_tools,
            "denied_tools": self.denied_tools,
            "allowed_contexts": self.allowed_contexts,
            "default_decision": self.default_decision.value,
            "can_elevate_children": self.can_elevate_children,
            "global_rate_limit": self.global_rate_limit,
            "tool_rate_limits": self.tool_rate_limits,
            "constraints": self.constraints,
            "parent_policy": self.parent_policy,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentCapabilityPolicy":
        """Create policy from dictionary."""
        return cls(
            agent_type=data["agent_type"],
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            allowed_tools=data.get("allowed_tools", {}),
            denied_tools=data.get("denied_tools", []),
            allowed_contexts=data.get(
                "allowed_contexts", ["test", "sandbox", "development"]
            ),
            default_decision=CapabilityDecision(data.get("default_decision", "deny")),
            can_elevate_children=data.get("can_elevate_children", False),
            global_rate_limit=data.get("global_rate_limit", 100),
            tool_rate_limits=data.get("tool_rate_limits", {}),
            constraints=data.get("constraints", {}),
            parent_policy=data.get("parent_policy"),
        )

    @classmethod
    def for_agent_type(cls, agent_type: str) -> "AgentCapabilityPolicy":
        """
        Get default policy for an agent type.

        Args:
            agent_type: Agent type (e.g., "CoderAgent", "ReviewerAgent")

        Returns:
            AgentCapabilityPolicy for the agent type
        """
        policies = _get_default_policies()
        return policies.get(
            agent_type,
            cls(
                agent_type=agent_type,
                description=f"Default restrictive policy for {agent_type}",
                default_decision=CapabilityDecision.DENY,
            ),
        )


# =============================================================================
# Default Agent Policies
# =============================================================================


def _get_default_policies() -> dict[str, AgentCapabilityPolicy]:
    """
    Get default policies for all known agent types.

    Returns:
        Dictionary mapping agent type to policy
    """
    return {
        "CoderAgent": AgentCapabilityPolicy(
            agent_type="CoderAgent",
            description="Code generation and modification agent",
            allowed_tools={
                "semantic_search": ["read", "execute"],
                "query_code_graph": ["read"],
                "get_code_dependencies": ["read"],
                "describe_tool": ["read"],
                "get_documentation": ["read"],
                "analyze_code_complexity": ["read"],
                "get_test_coverage": ["read"],
            },
            denied_tools=[
                "provision_sandbox",
                "destroy_sandbox",
                "deploy_to_production",
                "rotate_credentials",
                "modify_iam_policy",
                "delete_repository",
                "access_secrets",
            ],
            allowed_contexts=["test", "sandbox", "development"],
            default_decision=CapabilityDecision.DENY,
        ),
        "ReviewerAgent": AgentCapabilityPolicy(
            agent_type="ReviewerAgent",
            description="Code review and analysis agent",
            allowed_tools={
                "semantic_search": ["read", "execute"],
                "query_code_graph": ["read"],
                "get_code_dependencies": ["read"],
                "get_vulnerability_report": ["read"],
                "analyze_code_complexity": ["read"],
                "get_test_coverage": ["read"],
                "get_documentation": ["read"],
            },
            denied_tools=[
                "provision_sandbox",
                "destroy_sandbox",
                "index_code_embedding",
                "deploy_to_production",
                "commit_changes",
                "merge_branch",
                "access_secrets",
            ],
            allowed_contexts=["test", "sandbox", "development"],
            default_decision=CapabilityDecision.DENY,
        ),
        "ValidatorAgent": AgentCapabilityPolicy(
            agent_type="ValidatorAgent",
            description="Testing and validation agent",
            allowed_tools={
                "semantic_search": ["read", "execute"],
                "query_code_graph": ["read"],
                "get_code_dependencies": ["read"],
                "get_sandbox_status": ["read"],
                "get_test_coverage": ["read"],
                "index_code_embedding": ["execute"],  # Test context only
            },
            denied_tools=[
                "deploy_to_production",
                "rotate_credentials",
                "modify_iam_policy",
                "access_secrets",
            ],
            allowed_contexts=["test", "sandbox"],
            default_decision=CapabilityDecision.ESCALATE,
            constraints={"index_code_embedding_context": ["test"]},
        ),
        "MetaOrchestrator": AgentCapabilityPolicy(
            agent_type="MetaOrchestrator",
            description="Task orchestration and agent coordination",
            allowed_tools={
                "semantic_search": ["*"],
                "query_code_graph": ["*"],
                "get_code_dependencies": ["*"],
                "index_code_embedding": ["execute"],
                "get_sandbox_status": ["read"],
                "list_agents": ["read"],
                "get_agent_status": ["read"],
                "get_task_status": ["read"],
                "terminate_agent": ["execute"],
            },
            denied_tools=[],
            allowed_contexts=[
                "test",
                "sandbox",
                "development",
                "staging",
                "production",
            ],
            default_decision=CapabilityDecision.ESCALATE,
            can_elevate_children=True,
            global_rate_limit=200,
        ),
        "RedTeamAgent": AgentCapabilityPolicy(
            agent_type="RedTeamAgent",
            description="Security testing and penetration testing agent",
            allowed_tools={
                "semantic_search": ["*"],
                "query_code_graph": ["*"],
                "provision_sandbox": ["execute"],
                "destroy_sandbox": ["execute"],
                "get_sandbox_status": ["read"],
                "get_vulnerability_report": ["read"],
                "analyze_code_complexity": ["read"],
            },
            denied_tools=[
                "deploy_to_production",
                "rotate_credentials",
                "modify_iam_policy",
                "access_secrets",
            ],
            allowed_contexts=["test", "sandbox"],
            default_decision=CapabilityDecision.DENY,
        ),
        "AdminAgent": AgentCapabilityPolicy(
            agent_type="AdminAgent",
            description="Administrative operations agent",
            allowed_tools={
                "semantic_search": ["*"],
                "query_code_graph": ["*"],
                "index_code_embedding": ["*"],
                "provision_sandbox": ["execute"],
                "destroy_sandbox": ["execute"],
                "get_sandbox_status": ["read"],
                "query_audit_logs": ["read"],
                "list_agents": ["read"],
                "terminate_agent": ["execute"],
            },
            denied_tools=[],
            allowed_contexts=[
                "test",
                "sandbox",
                "development",
                "staging",
                "production",
            ],
            default_decision=CapabilityDecision.ESCALATE,
            can_elevate_children=True,
        ),
        "SecurityAgent": AgentCapabilityPolicy(
            agent_type="SecurityAgent",
            description="Security monitoring and response agent",
            allowed_tools={
                "semantic_search": ["read"],
                "query_code_graph": ["read"],
                "get_vulnerability_report": ["read"],
                "query_audit_logs": ["read"],
                "get_agent_metrics": ["read"],
            },
            denied_tools=[
                "provision_sandbox",
                "destroy_sandbox",
                "deploy_to_production",
                "commit_changes",
                "index_code_embedding",
            ],
            allowed_contexts=[
                "test",
                "sandbox",
                "development",
                "staging",
                "production",
            ],
            default_decision=CapabilityDecision.DENY,
        ),
        "DocumentationAgent": AgentCapabilityPolicy(
            agent_type="DocumentationAgent",
            description="Documentation generation and maintenance agent",
            allowed_tools={
                "semantic_search": ["read", "execute"],
                "query_code_graph": ["read"],
                "get_documentation": ["read"],
                "get_code_dependencies": ["read"],
            },
            denied_tools=[
                "provision_sandbox",
                "destroy_sandbox",
                "deploy_to_production",
                "index_code_embedding",
                "commit_changes",
                "access_secrets",
            ],
            allowed_contexts=["test", "sandbox", "development"],
            default_decision=CapabilityDecision.DENY,
        ),
    }


# =============================================================================
# Policy Repository
# =============================================================================


class PolicyRepository:
    """
    Repository for managing agent capability policies.

    Provides caching and custom policy storage.
    """

    def __init__(self):
        self._custom_policies: dict[str, AgentCapabilityPolicy] = {}
        self._policy_cache: dict[str, AgentCapabilityPolicy] = {}

    def get_policy(self, agent_type: str) -> AgentCapabilityPolicy:
        """
        Get policy for an agent type.

        Checks custom policies first, then defaults.

        Args:
            agent_type: Agent type

        Returns:
            AgentCapabilityPolicy for the agent
        """
        # Check cache first
        if agent_type in self._policy_cache:
            return self._policy_cache[agent_type]

        # Check custom policies
        if agent_type in self._custom_policies:
            policy = self._custom_policies[agent_type]
            self._policy_cache[agent_type] = policy
            return policy

        # Fall back to defaults
        policy = AgentCapabilityPolicy.for_agent_type(agent_type)
        self._policy_cache[agent_type] = policy
        return policy

    def set_custom_policy(
        self,
        agent_type: str,
        policy: AgentCapabilityPolicy,
    ) -> None:
        """
        Set a custom policy for an agent type.

        Args:
            agent_type: Agent type
            policy: Custom policy
        """
        self._custom_policies[agent_type] = policy
        # Invalidate cache
        self._policy_cache.pop(agent_type, None)
        logger.info(f"Custom policy set for {agent_type}")

    def clear_cache(self) -> None:
        """Clear the policy cache."""
        self._policy_cache.clear()

    def list_policies(self) -> list[str]:
        """List all available policy types."""
        default_types = list(_get_default_policies().keys())
        custom_types = list(self._custom_policies.keys())
        return list(set(default_types + custom_types))


# Global policy repository singleton
_policy_repository: Optional[PolicyRepository] = None


def get_policy_repository() -> PolicyRepository:
    """Get the global policy repository."""
    global _policy_repository
    if _policy_repository is None:
        _policy_repository = PolicyRepository()
    return _policy_repository


def reset_policy_repository() -> None:
    """Reset the global policy repository (for testing)."""
    global _policy_repository
    _policy_repository = None
