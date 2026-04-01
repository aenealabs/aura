"""
Project Aura - Tool Capability Registry

Central registry for tool capabilities, classifications, and metadata.
Provides tool discovery and classification lookup for the capability governance framework.

Security Rationale:
- Centralized tool registration prevents unregistered tool abuse
- Classification registry ensures consistent policy enforcement
- Tool metadata enables informed HITL decisions

Author: Project Aura Team
Created: 2026-01-26
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .contracts import ToolCapability, ToolClassification

logger = logging.getLogger(__name__)


# =============================================================================
# Default Tool Capabilities
# =============================================================================

DEFAULT_TOOL_CAPABILITIES: dict[str, ToolCapability] = {
    # Level 1: SAFE tools
    "semantic_search": ToolCapability(
        tool_name="semantic_search",
        classification=ToolClassification.SAFE,
        description="Search code and documentation using semantic similarity",
        allowed_actions=("read", "execute"),
        rate_limit_per_minute=120,
        audit_sample_rate=0.1,
    ),
    "describe_tool": ToolCapability(
        tool_name="describe_tool",
        classification=ToolClassification.SAFE,
        description="Get description and schema for a tool",
        allowed_actions=("read",),
        rate_limit_per_minute=60,
        audit_sample_rate=0.1,
    ),
    "get_sandbox_status": ToolCapability(
        tool_name="get_sandbox_status",
        classification=ToolClassification.SAFE,
        description="Get status of a sandbox environment",
        allowed_actions=("read",),
        rate_limit_per_minute=60,
        audit_sample_rate=0.1,
    ),
    "list_tools": ToolCapability(
        tool_name="list_tools",
        classification=ToolClassification.SAFE,
        description="List available tools",
        allowed_actions=("read",),
        rate_limit_per_minute=30,
        audit_sample_rate=0.1,
    ),
    "list_agents": ToolCapability(
        tool_name="list_agents",
        classification=ToolClassification.SAFE,
        description="List active agents",
        allowed_actions=("read",),
        rate_limit_per_minute=30,
        audit_sample_rate=0.1,
    ),
    "get_agent_status": ToolCapability(
        tool_name="get_agent_status",
        classification=ToolClassification.SAFE,
        description="Get status of an agent",
        allowed_actions=("read",),
        rate_limit_per_minute=60,
        audit_sample_rate=0.1,
    ),
    "get_task_status": ToolCapability(
        tool_name="get_task_status",
        classification=ToolClassification.SAFE,
        description="Get status of a task",
        allowed_actions=("read",),
        rate_limit_per_minute=60,
        audit_sample_rate=0.1,
    ),
    "get_documentation": ToolCapability(
        tool_name="get_documentation",
        classification=ToolClassification.SAFE,
        description="Retrieve documentation for code or APIs",
        allowed_actions=("read",),
        rate_limit_per_minute=60,
        audit_sample_rate=0.1,
    ),
    # Level 2: MONITORING tools
    "query_code_graph": ToolCapability(
        tool_name="query_code_graph",
        classification=ToolClassification.MONITORING,
        description="Query the code knowledge graph for relationships",
        allowed_actions=("read",),
        rate_limit_per_minute=60,
        audit_sample_rate=1.0,
    ),
    "get_code_dependencies": ToolCapability(
        tool_name="get_code_dependencies",
        classification=ToolClassification.MONITORING,
        description="Get dependency graph for code",
        allowed_actions=("read",),
        rate_limit_per_minute=30,
        audit_sample_rate=1.0,
    ),
    "get_agent_metrics": ToolCapability(
        tool_name="get_agent_metrics",
        classification=ToolClassification.MONITORING,
        description="Get performance metrics for agents",
        allowed_actions=("read",),
        rate_limit_per_minute=30,
        audit_sample_rate=1.0,
    ),
    "query_audit_logs": ToolCapability(
        tool_name="query_audit_logs",
        classification=ToolClassification.MONITORING,
        description="Query audit logs for security review",
        allowed_actions=("read",),
        rate_limit_per_minute=20,
        audit_sample_rate=1.0,
    ),
    "get_vulnerability_report": ToolCapability(
        tool_name="get_vulnerability_report",
        classification=ToolClassification.MONITORING,
        description="Get vulnerability scan results",
        allowed_actions=("read",),
        rate_limit_per_minute=20,
        audit_sample_rate=1.0,
    ),
    "analyze_code_complexity": ToolCapability(
        tool_name="analyze_code_complexity",
        classification=ToolClassification.MONITORING,
        description="Analyze code complexity metrics",
        allowed_actions=("read",),
        rate_limit_per_minute=20,
        audit_sample_rate=1.0,
    ),
    "get_test_coverage": ToolCapability(
        tool_name="get_test_coverage",
        classification=ToolClassification.MONITORING,
        description="Get test coverage report",
        allowed_actions=("read",),
        rate_limit_per_minute=20,
        audit_sample_rate=1.0,
    ),
    "query_embeddings": ToolCapability(
        tool_name="query_embeddings",
        classification=ToolClassification.MONITORING,
        description="Query vector embeddings database",
        allowed_actions=("read",),
        rate_limit_per_minute=60,
        audit_sample_rate=1.0,
    ),
    # Level 3: DANGEROUS tools
    "index_code_embedding": ToolCapability(
        tool_name="index_code_embedding",
        classification=ToolClassification.DANGEROUS,
        description="Index code into embeddings database",
        allowed_actions=("execute",),
        requires_context=("test", "sandbox"),
        blocked_contexts=("production",),
        rate_limit_per_minute=10,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    "destroy_sandbox": ToolCapability(
        tool_name="destroy_sandbox",
        classification=ToolClassification.DANGEROUS,
        description="Destroy a sandbox environment",
        allowed_actions=("execute",),
        requires_context=("sandbox",),
        blocked_contexts=("production",),
        rate_limit_per_minute=5,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    "write_config": ToolCapability(
        tool_name="write_config",
        classification=ToolClassification.DANGEROUS,
        description="Write configuration files",
        allowed_actions=("write",),
        blocked_contexts=("production",),
        rate_limit_per_minute=10,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    "delete_index": ToolCapability(
        tool_name="delete_index",
        classification=ToolClassification.DANGEROUS,
        description="Delete a search or embedding index",
        allowed_actions=("execute", "delete"),
        blocked_contexts=("production",),
        rate_limit_per_minute=2,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    "create_branch": ToolCapability(
        tool_name="create_branch",
        classification=ToolClassification.DANGEROUS,
        description="Create a git branch",
        allowed_actions=("execute",),
        rate_limit_per_minute=10,
        audit_sample_rate=1.0,
    ),
    "commit_changes": ToolCapability(
        tool_name="commit_changes",
        classification=ToolClassification.DANGEROUS,
        description="Commit changes to repository",
        allowed_actions=("execute",),
        rate_limit_per_minute=10,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    "merge_branch": ToolCapability(
        tool_name="merge_branch",
        classification=ToolClassification.DANGEROUS,
        description="Merge a branch",
        allowed_actions=("execute",),
        rate_limit_per_minute=5,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    "terminate_agent": ToolCapability(
        tool_name="terminate_agent",
        classification=ToolClassification.DANGEROUS,
        description="Terminate a running agent",
        allowed_actions=("execute",),
        rate_limit_per_minute=10,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    # Level 4: CRITICAL tools
    "provision_sandbox": ToolCapability(
        tool_name="provision_sandbox",
        classification=ToolClassification.CRITICAL,
        description="Provision a new sandbox environment",
        allowed_actions=("execute",),
        requires_context=("sandbox", "test"),
        blocked_contexts=("production",),
        rate_limit_per_minute=2,
        max_concurrent=3,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    "deploy_to_production": ToolCapability(
        tool_name="deploy_to_production",
        classification=ToolClassification.CRITICAL,
        description="Deploy code to production environment",
        allowed_actions=("execute",),
        requires_context=("staging",),
        rate_limit_per_minute=1,
        max_concurrent=1,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    "rotate_credentials": ToolCapability(
        tool_name="rotate_credentials",
        classification=ToolClassification.CRITICAL,
        description="Rotate security credentials",
        allowed_actions=("execute",),
        rate_limit_per_minute=1,
        max_concurrent=1,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    "modify_iam_policy": ToolCapability(
        tool_name="modify_iam_policy",
        classification=ToolClassification.CRITICAL,
        description="Modify IAM policies",
        allowed_actions=("execute", "write"),
        rate_limit_per_minute=1,
        max_concurrent=1,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    "access_secrets": ToolCapability(
        tool_name="access_secrets",
        classification=ToolClassification.CRITICAL,
        description="Access secrets from secrets manager",
        allowed_actions=("read",),
        rate_limit_per_minute=10,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    "delete_repository": ToolCapability(
        tool_name="delete_repository",
        classification=ToolClassification.CRITICAL,
        description="Delete a code repository",
        allowed_actions=("delete",),
        rate_limit_per_minute=1,
        max_concurrent=1,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
    "execute_arbitrary_code": ToolCapability(
        tool_name="execute_arbitrary_code",
        classification=ToolClassification.CRITICAL,
        description="Execute arbitrary code in sandbox",
        allowed_actions=("execute",),
        requires_context=("sandbox",),
        blocked_contexts=("production", "staging"),
        rate_limit_per_minute=5,
        requires_justification=True,
        audit_sample_rate=1.0,
    ),
}


# =============================================================================
# Capability Registry
# =============================================================================


@dataclass
class CapabilityRegistry:
    """
    Central registry for tool capabilities.

    Provides tool discovery, classification lookup, and capability validation.
    """

    _tools: dict[str, ToolCapability] = field(default_factory=dict)
    _initialized: bool = False

    def __post_init__(self):
        """Initialize with default tools."""
        if not self._initialized:
            self._tools = dict(DEFAULT_TOOL_CAPABILITIES)
            self._initialized = True

    def register_tool(self, capability: ToolCapability) -> None:
        """
        Register a tool capability.

        Args:
            capability: Tool capability to register
        """
        self._tools[capability.tool_name] = capability
        logger.info(
            f"Registered tool: {capability.tool_name} "
            f"(classification: {capability.classification.value})"
        )

    def unregister_tool(self, tool_name: str) -> bool:
        """
        Unregister a tool.

        Args:
            tool_name: Name of tool to unregister

        Returns:
            True if tool was unregistered, False if not found
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.info(f"Unregistered tool: {tool_name}")
            return True
        return False

    def get_tool(self, tool_name: str) -> Optional[ToolCapability]:
        """
        Get capability for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolCapability if found, None otherwise
        """
        return self._tools.get(tool_name)

    def get_classification(self, tool_name: str) -> ToolClassification:
        """
        Get classification for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolClassification, defaults to DANGEROUS for unknown tools
        """
        tool = self._tools.get(tool_name)
        if tool:
            return tool.classification
        return ToolClassification.DANGEROUS

    def is_registered(self, tool_name: str) -> bool:
        """Check if a tool is registered."""
        return tool_name in self._tools

    def list_tools(
        self,
        classification: Optional[ToolClassification] = None,
    ) -> list[str]:
        """
        List registered tools.

        Args:
            classification: Optional filter by classification

        Returns:
            List of tool names
        """
        if classification is None:
            return list(self._tools.keys())
        return [
            name
            for name, tool in self._tools.items()
            if tool.classification == classification
        ]

    def list_tools_by_classification(self) -> dict[ToolClassification, list[str]]:
        """
        List all tools grouped by classification.

        Returns:
            Dictionary mapping classification to tool names
        """
        result: dict[ToolClassification, list[str]] = {
            ToolClassification.SAFE: [],
            ToolClassification.MONITORING: [],
            ToolClassification.DANGEROUS: [],
            ToolClassification.CRITICAL: [],
        }
        for name, tool in self._tools.items():
            result[tool.classification].append(name)
        return result

    def get_rate_limit(self, tool_name: str) -> int:
        """
        Get rate limit for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Rate limit per minute (default 60)
        """
        tool = self._tools.get(tool_name)
        if tool:
            return tool.rate_limit_per_minute
        return 60

    def requires_justification(self, tool_name: str) -> bool:
        """
        Check if tool requires justification.

        Args:
            tool_name: Name of the tool

        Returns:
            True if justification required
        """
        tool = self._tools.get(tool_name)
        if tool:
            return tool.requires_justification
        return True  # Default to requiring justification for unknown tools

    def get_audit_sample_rate(self, tool_name: str) -> float:
        """
        Get audit sample rate for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Sample rate (0.0-1.0), defaults to 1.0 for unknown tools
        """
        tool = self._tools.get(tool_name)
        if tool:
            return tool.audit_sample_rate
        return 1.0

    def validate_context(self, tool_name: str, context: str) -> bool:
        """
        Validate if tool can be used in a context.

        Args:
            tool_name: Name of the tool
            context: Execution context

        Returns:
            True if context is valid for tool
        """
        tool = self._tools.get(tool_name)
        if tool:
            return tool.is_allowed_in_context(context)
        return False

    def validate_action(self, tool_name: str, action: str) -> bool:
        """
        Validate if action is allowed for tool.

        Args:
            tool_name: Name of the tool
            action: Action type

        Returns:
            True if action is allowed
        """
        tool = self._tools.get(tool_name)
        if tool:
            return tool.is_action_allowed(action)
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert registry to dictionary for serialization."""
        return {
            name: {
                "tool_name": tool.tool_name,
                "classification": tool.classification.value,
                "description": tool.description,
                "allowed_actions": list(tool.allowed_actions),
                "requires_context": list(tool.requires_context),
                "blocked_contexts": list(tool.blocked_contexts),
                "rate_limit_per_minute": tool.rate_limit_per_minute,
                "max_concurrent": tool.max_concurrent,
                "requires_justification": tool.requires_justification,
                "audit_sample_rate": tool.audit_sample_rate,
            }
            for name, tool in self._tools.items()
        }


# =============================================================================
# Global Registry Singleton
# =============================================================================

_capability_registry: Optional[CapabilityRegistry] = None


def get_capability_registry() -> CapabilityRegistry:
    """Get the global capability registry."""
    global _capability_registry
    if _capability_registry is None:
        _capability_registry = CapabilityRegistry()
    return _capability_registry


def reset_capability_registry() -> None:
    """Reset the global capability registry (for testing)."""
    global _capability_registry
    _capability_registry = None
