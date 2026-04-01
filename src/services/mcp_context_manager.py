"""MCP Context Manager for Multi-Agent Context Isolation

Implements ADR-034 Phase 2.3: MCP Integration for Multi-Agent Context

Implements context isolation pattern from research:
- Root agent passes only relevant context slice to sub-agents
- Prevents "context explosion" in hierarchical systems
- Explicit context scoping per agent type

Key principle: Each agent sees only what it needs.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class AgentContextScope(Enum):
    """Defines what context each agent type can access.

    Each scope has different access levels:
    - ORCHESTRATOR: Full context access for coordination
    - CODER: Code-focused, no credentials
    - REVIEWER: Code + security policies
    - VALIDATOR: Validation-focused, limited code access
    - ANALYST: Analysis-focused, read-only
    """

    ORCHESTRATOR = "full"
    CODER = "code_focused"
    REVIEWER = "review_focused"
    VALIDATOR = "validation_only"
    ANALYST = "analysis_focused"


class ContextStackManager(Protocol):
    """Protocol for context stack manager."""

    async def build_context_stack(self, *args, **kwargs) -> str:
        """Build context stack."""
        ...


@dataclass
class ContextScope:
    """Defines context boundaries for an agent."""

    agent_type: AgentContextScope
    included_layers: list[str]  # Which context layers to include
    max_tokens: int
    allowed_domains: list[str] = field(default_factory=list)
    denied_fields: list[str] = field(default_factory=list)
    allowed_tool_levels: list[str] = field(
        default_factory=lambda: ["ATOMIC"]
    )  # Tool levels


@dataclass
class ScopedContext:
    """Context that has been scoped for a specific agent."""

    agent_type: AgentContextScope
    content: dict
    token_count: int
    included_layers: list[str]
    excluded_fields: list[str]


class MCPContextManager:
    """Manages context isolation for multi-agent systems.

    Implements Model Context Protocol (MCP) patterns for:
    - Context scoping per agent type
    - Field-level access control
    - Token budget enforcement
    - Domain-based filtering

    Prevents:
    - Context explosion in deep agent hierarchies
    - Information leakage between agents
    - Token waste from irrelevant context
    - Credential exposure to code-generation agents

    Usage:
        manager = MCPContextManager()
        scoped = manager.scope_context_for_agent(full_context, AgentContextScope.CODER)
    """

    # Default scope configurations for each agent type
    SCOPE_CONFIGS = {
        AgentContextScope.ORCHESTRATOR: ContextScope(
            agent_type=AgentContextScope.ORCHESTRATOR,
            included_layers=[
                "system",
                "memory",
                "retrieved",
                "tools",
                "history",
                "task",
            ],
            max_tokens=100000,
            allowed_domains=["*"],
            denied_fields=[],
            allowed_tool_levels=["ATOMIC", "DOMAIN", "EXPERT"],
        ),
        AgentContextScope.CODER: ContextScope(
            agent_type=AgentContextScope.CODER,
            included_layers=["system", "retrieved", "task"],
            max_tokens=50000,
            allowed_domains=["code", "dependencies", "tests", "documentation"],
            denied_fields=["credentials", "secrets", "api_keys", "tokens", "passwords"],
            allowed_tool_levels=["ATOMIC"],
        ),
        AgentContextScope.REVIEWER: ContextScope(
            agent_type=AgentContextScope.REVIEWER,
            included_layers=["system", "memory", "retrieved", "task"],
            max_tokens=60000,
            allowed_domains=[
                "code",
                "security_policies",
                "vulnerabilities",
                "compliance",
            ],
            denied_fields=["credentials", "secrets"],
            allowed_tool_levels=["ATOMIC", "DOMAIN"],
        ),
        AgentContextScope.VALIDATOR: ContextScope(
            agent_type=AgentContextScope.VALIDATOR,
            included_layers=["system", "task"],
            max_tokens=30000,
            allowed_domains=["test_results", "schemas", "validation_rules", "coverage"],
            denied_fields=["source_code", "credentials"],  # Only sees test outputs
            allowed_tool_levels=["ATOMIC"],
        ),
        AgentContextScope.ANALYST: ContextScope(
            agent_type=AgentContextScope.ANALYST,
            included_layers=["system", "memory", "retrieved", "task"],
            max_tokens=70000,
            allowed_domains=["code", "metrics", "dependencies", "architecture"],
            denied_fields=["credentials", "secrets", "api_keys"],
            allowed_tool_levels=["ATOMIC", "DOMAIN"],
        ),
    }

    def __init__(
        self,
        context_stack_manager: Optional[ContextStackManager] = None,
        custom_scopes: Optional[dict[AgentContextScope, ContextScope]] = None,
    ):
        """Initialize MCP context manager.

        Args:
            context_stack_manager: Optional stack manager for integration
            custom_scopes: Optional custom scope configurations
        """
        self.stack_manager = context_stack_manager
        self.scopes = {**self.SCOPE_CONFIGS}
        if custom_scopes:
            self.scopes.update(custom_scopes)

    def scope_context_for_agent(
        self,
        full_context: dict,
        target_agent: AgentContextScope,
        additional_denied_fields: Optional[list[str]] = None,
    ) -> ScopedContext:
        """Create scoped context for specific agent type.

        Args:
            full_context: Complete context from orchestrator
            target_agent: Target agent type
            additional_denied_fields: Extra fields to exclude

        Returns:
            ScopedContext appropriate for agent
        """
        scope_config = self.scopes.get(
            target_agent, self.SCOPE_CONFIGS[AgentContextScope.CODER]
        )

        denied_fields = list(scope_config.denied_fields)
        if additional_denied_fields:
            denied_fields.extend(additional_denied_fields)

        scoped = {}
        excluded_fields = []

        # Filter to included layers
        for layer in scope_config.included_layers:
            if layer in full_context:
                filtered_layer, layer_excluded = self._filter_layer(
                    full_context[layer],
                    scope_config.allowed_domains,
                    denied_fields,
                )
                scoped[layer] = filtered_layer
                excluded_fields.extend(layer_excluded)

        # Enforce token limit
        scoped, truncated = self._truncate_to_budget(scoped, scope_config.max_tokens)

        token_count = self._estimate_tokens(scoped)

        logger.debug(
            f"Scoped context for {target_agent.value}: "
            f"{len(scoped)} layers, {token_count} tokens, "
            f"{len(excluded_fields)} fields excluded"
        )

        return ScopedContext(
            agent_type=target_agent,
            content=scoped,
            token_count=token_count,
            included_layers=list(scoped.keys()),
            excluded_fields=excluded_fields,
        )

    def _filter_layer(
        self,
        layer_content: Any,
        allowed_domains: list[str],
        denied_fields: list[str],
    ) -> tuple[Any, list[str]]:
        """Filter layer content based on scope rules.

        Args:
            layer_content: Content to filter
            allowed_domains: Allowed domain patterns
            denied_fields: Fields to exclude

        Returns:
            Tuple of (filtered content, list of excluded field names)
        """
        excluded: list[str] = []

        if not isinstance(layer_content, dict):
            return layer_content, excluded

        filtered = {}

        for key, value in layer_content.items():
            # Check if field is denied
            if self._field_matches_patterns(key, denied_fields):
                excluded.append(key)
                continue

            # Check if field matches allowed domains
            if "*" in allowed_domains or self._field_matches_patterns(
                key, allowed_domains
            ):
                # Recursively filter nested dicts
                if isinstance(value, dict):
                    nested_filtered, nested_excluded = self._filter_layer(
                        value, allowed_domains, denied_fields
                    )
                    filtered[key] = nested_filtered
                    excluded.extend(nested_excluded)
                elif isinstance(value, list):
                    # Filter list items if they're dicts
                    filtered[key] = [
                        (
                            self._filter_layer(item, allowed_domains, denied_fields)[0]
                            if isinstance(item, dict)
                            else item
                        )
                        for item in value
                    ]
                else:
                    filtered[key] = value

        return filtered, excluded

    def _field_matches_patterns(self, field: str, patterns: list[str]) -> bool:
        """Check if field matches any pattern.

        Args:
            field: Field name to check
            patterns: Patterns to match against

        Returns:
            True if field matches any pattern
        """
        field_lower = field.lower()
        for pattern in patterns:
            pattern_lower = pattern.lower()
            if pattern_lower in field_lower or field_lower in pattern_lower:
                return True
        return False

    def _truncate_to_budget(self, context: dict, max_tokens: int) -> tuple[dict, bool]:
        """Truncate context to fit within token budget.

        Args:
            context: Context dictionary
            max_tokens: Maximum token budget

        Returns:
            Tuple of (truncated context, whether truncation occurred)
        """
        estimated_tokens = self._estimate_tokens(context)

        if estimated_tokens <= max_tokens:
            return context, False

        truncation_ratio = max_tokens / estimated_tokens
        truncated: dict[str, Any] = {}

        for key, value in context.items():
            if isinstance(value, str):
                new_length = int(len(value) * truncation_ratio)
                truncated[key] = value[:new_length]
            elif isinstance(value, dict):
                truncated[key], _ = self._truncate_to_budget(
                    value, int(max_tokens * truncation_ratio / len(context))
                )
            elif isinstance(value, list):
                # Keep fewer items
                new_count = max(1, int(len(value) * truncation_ratio))
                truncated[key] = value[:new_count]
            else:
                truncated[key] = value

        return truncated, True

    def _estimate_tokens(self, content: Any) -> int:
        """Estimate token count for content.

        Args:
            content: Content to estimate

        Returns:
            Estimated token count
        """
        if isinstance(content, str):
            return len(content) // 4
        elif isinstance(content, dict):
            return len(json.dumps(content)) // 4
        elif isinstance(content, list):
            return sum(self._estimate_tokens(item) for item in content)
        else:
            return len(str(content)) // 4

    def create_agent_context(
        self,
        task: str,
        agent_type: AgentContextScope,
        parent_context: Optional[dict] = None,
        include_task: bool = True,
    ) -> dict:
        """Create a minimal context for a sub-agent.

        Args:
            task: Task for the sub-agent
            agent_type: Type of sub-agent
            parent_context: Parent agent's context to scope from
            include_task: Whether to include task in context

        Returns:
            Context dictionary for sub-agent
        """
        _scope_config = self.scopes.get(  # noqa: F841
            agent_type, self.SCOPE_CONFIGS[AgentContextScope.CODER]
        )

        context = {}

        if parent_context:
            scoped = self.scope_context_for_agent(parent_context, agent_type)
            context = scoped.content

        if include_task:
            context["task"] = task

        return context

    def get_scope_config(self, agent_type: AgentContextScope) -> ContextScope:
        """Get scope configuration for agent type.

        Args:
            agent_type: Agent type

        Returns:
            Scope configuration
        """
        return self.scopes.get(agent_type, self.SCOPE_CONFIGS[AgentContextScope.CODER])

    def register_custom_scope(
        self, agent_type: AgentContextScope, scope: ContextScope
    ) -> None:
        """Register a custom scope configuration.

        Args:
            agent_type: Agent type to configure
            scope: Custom scope configuration
        """
        self.scopes[agent_type] = scope
        logger.info(f"Registered custom scope for {agent_type.value}")

    def validate_context_access(
        self,
        agent_type: AgentContextScope,
        requested_fields: list[str],
    ) -> tuple[list[str], list[str]]:
        """Validate which fields an agent can access.

        Args:
            agent_type: Agent type
            requested_fields: Fields the agent is requesting

        Returns:
            Tuple of (allowed fields, denied fields)
        """
        scope_config = self.scopes.get(
            agent_type, self.SCOPE_CONFIGS[AgentContextScope.CODER]
        )

        allowed = []
        denied = []

        for field_name in requested_fields:
            if self._field_matches_patterns(field_name, scope_config.denied_fields):
                denied.append(field_name)
            else:
                allowed.append(field_name)

        return allowed, denied

    def get_manager_stats(self) -> dict:
        """Get manager statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "configured_scopes": len(self.scopes),
            "scope_types": [s.value for s in self.scopes.keys()],
            "default_budgets": {
                scope.value: config.max_tokens for scope, config in self.scopes.items()
            },
        }


def create_isolated_context(
    parent_context: dict,
    agent_type: AgentContextScope,
    task: str,
    manager: Optional[MCPContextManager] = None,
) -> dict:
    """Convenience function to create isolated context for sub-agent.

    Args:
        parent_context: Parent agent's context
        agent_type: Type of sub-agent
        task: Task for sub-agent
        manager: Optional MCPContextManager instance

    Returns:
        Isolated context for sub-agent
    """
    if manager is None:
        manager = MCPContextManager()

    scoped = manager.scope_context_for_agent(parent_context, agent_type)

    return {
        "scoped_context": scoped.content,
        "task": task,
        "agent_type": agent_type.value,
        "token_budget": manager.get_scope_config(agent_type).max_tokens,
    }
