"""Hierarchical Tool Registry for Context-Efficient Tool Presentation

Implements ADR-034 Phase 1.2: Hierarchical Tool Presentation

Implements Manus pattern: ~20 atomic tools at Level 1,
domain-specific tools loaded on demand at Level 2+.

Research shows that providing 100+ tools leads to "Context Confusion" -
hallucinated parameters and wrong tool calls.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Protocol

logger = logging.getLogger(__name__)


class ToolLevel(Enum):
    """Tool hierarchy levels."""

    ATOMIC = 1  # Core tools always available (~20)
    DOMAIN = 2  # Domain-specific, loaded on demand
    EXPERT = 3  # Specialized tools for specific tasks


class ToolHandler(Protocol):
    """Protocol for tool handler functions."""

    async def __call__(self, params: dict) -> Any:
        """Execute the tool with given parameters."""
        ...


@dataclass
class ToolDefinition:
    """Tool definition with hierarchy metadata."""

    name: str
    description: str
    level: ToolLevel
    input_schema: dict
    domain: Optional[str] = None  # e.g., "security", "code_analysis", "infrastructure"
    handler: Optional[Callable] = None
    requires_hitl: bool = False
    example_usage: Optional[str] = None
    output_schema: Optional[dict] = None
    tags: list[str] = field(default_factory=list)

    def to_prompt_format(self, format_type: str = "compact") -> str:
        """Format tool for prompt injection.

        Args:
            format_type: "compact" (name + one-line desc) or "full" (with schema)

        Returns:
            Formatted string for prompt
        """
        if format_type == "compact":
            hitl_marker = " [HITL]" if self.requires_hitl else ""
            return f"- {self.name}: {self.description}{hitl_marker}"
        else:
            lines = [
                f"## {self.name}",
                f"Description: {self.description}",
                f"Inputs: {self.input_schema}",
            ]
            if self.requires_hitl:
                lines.append("Requires: Human approval")
            if self.example_usage:
                lines.append(f"Example: {self.example_usage}")
            return "\n".join(lines)


@dataclass
class ToolSelectionContext:
    """Context for tool selection decisions."""

    detected_domains: list[str] = field(default_factory=list)
    task_complexity: str = "standard"  # "simple", "standard", "complex"
    agent_type: Optional[str] = None
    max_tools: Optional[int] = None


class HierarchicalToolRegistry:
    """Manages hierarchical tool presentation to prevent context confusion.

    Level 1 (Atomic): ~20 core tools always available
        - file_read, file_write, search_code, run_command
        - query_graph, vector_search, create_issue
        - store_memory, retrieve_memory
        - etc.

    Level 2 (Domain): Loaded when domain context detected
        - Security: vuln_scan, dependency_check, secret_scan
        - Infrastructure: provision_sandbox, deploy_stack, check_drift
        - Code Analysis: ast_parse, complexity_analyze, coverage_check

    Level 3 (Expert): Loaded for specific specialized tasks
        - Red team tools, compliance scanners, etc.

    Research recommendation: Maximum ~20 tools at any time to prevent
    context confusion and hallucinated parameters.
    """

    MAX_ATOMIC_TOOLS = 20
    MAX_TOTAL_TOOLS = 30  # Hard limit to prevent context confusion

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._domain_tools: dict[str, list[str]] = {}
        self._agent_tools: dict[str, list[str]] = {}
        self._register_atomic_tools()

    def _register_atomic_tools(self) -> None:
        """Register Level 1 atomic tools."""
        atomic_tools = [
            # File operations
            ToolDefinition(
                name="file_read",
                description="Read contents of a file by path",
                level=ToolLevel.ATOMIC,
                input_schema={"file_path": "string", "encoding": "string (optional)"},
                tags=["file", "read"],
            ),
            ToolDefinition(
                name="file_write",
                description="Write content to a file",
                level=ToolLevel.ATOMIC,
                input_schema={"file_path": "string", "content": "string"},
                requires_hitl=False,
                tags=["file", "write"],
            ),
            ToolDefinition(
                name="file_list",
                description="List files in a directory",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "directory": "string",
                    "pattern": "string (optional glob)",
                },
                tags=["file", "list"],
            ),
            # Search operations
            ToolDefinition(
                name="search_code",
                description="Search codebase using pattern or semantic query",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "query": "string",
                    "search_type": "pattern|semantic",
                    "limit": "integer (optional)",
                },
                tags=["search", "code"],
            ),
            ToolDefinition(
                name="query_graph",
                description="Query Neptune code knowledge graph",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "query": "string",
                    "entity_type": "string (optional)",
                    "limit": "integer (optional)",
                },
                tags=["graph", "query"],
            ),
            ToolDefinition(
                name="vector_search",
                description="Semantic similarity search in OpenSearch",
                level=ToolLevel.ATOMIC,
                input_schema={"query": "string", "k": "integer", "filters": "object"},
                tags=["search", "semantic"],
            ),
            # Command execution
            ToolDefinition(
                name="run_command",
                description="Execute shell command in sandbox environment",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "command": "string",
                    "timeout": "integer (seconds)",
                    "cwd": "string (optional)",
                },
                requires_hitl=True,
                tags=["command", "shell"],
            ),
            # Issue tracking
            ToolDefinition(
                name="create_issue",
                description="Create GitHub/Jira issue for tracking",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "title": "string",
                    "body": "string",
                    "labels": "array of strings",
                    "priority": "string (optional)",
                },
                tags=["issue", "tracking"],
            ),
            ToolDefinition(
                name="update_issue",
                description="Update an existing issue",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "issue_id": "string",
                    "updates": "object with fields to update",
                },
                tags=["issue", "tracking"],
            ),
            # Memory operations (Titan neural memory)
            ToolDefinition(
                name="store_memory",
                description="Store experience in Titan neural memory for future recall",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "experience": "object with context, action, outcome",
                    "tags": "array of strings",
                },
                tags=["memory", "store"],
            ),
            ToolDefinition(
                name="retrieve_memory",
                description="Retrieve relevant experiences from Titan neural memory",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "query": "string",
                    "limit": "integer (optional)",
                    "filters": "object (optional)",
                },
                tags=["memory", "retrieve"],
            ),
            # Code operations
            ToolDefinition(
                name="parse_code",
                description="Parse code to extract structure (AST)",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "file_path": "string",
                    "language": "string (optional, auto-detect)",
                },
                tags=["code", "parse"],
            ),
            ToolDefinition(
                name="generate_code",
                description="Generate code based on specification",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "specification": "string",
                    "language": "string",
                    "style_guide": "string (optional)",
                },
                tags=["code", "generate"],
            ),
            # Git operations
            ToolDefinition(
                name="git_status",
                description="Get git repository status",
                level=ToolLevel.ATOMIC,
                input_schema={"repo_path": "string (optional)"},
                tags=["git", "status"],
            ),
            ToolDefinition(
                name="git_diff",
                description="Get diff of changes in repository",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "repo_path": "string (optional)",
                    "file_path": "string (optional)",
                    "staged": "boolean (optional)",
                },
                tags=["git", "diff"],
            ),
            # Communication
            ToolDefinition(
                name="send_notification",
                description="Send notification to user or channel",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "message": "string",
                    "channel": "string (slack, email, etc)",
                    "priority": "string (optional)",
                },
                tags=["notification", "communication"],
            ),
            # Context operations
            ToolDefinition(
                name="get_context",
                description="Retrieve additional context for current task",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "query": "string",
                    "sources": "array (graph, vector, filesystem)",
                    "limit": "integer (optional)",
                },
                tags=["context", "retrieve"],
            ),
            ToolDefinition(
                name="summarize",
                description="Summarize content or code",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "content": "string or array of strings",
                    "max_length": "integer (optional)",
                    "style": "string (brief, detailed)",
                },
                tags=["summary", "analysis"],
            ),
            # Validation
            ToolDefinition(
                name="validate",
                description="Validate code, configuration, or data",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "content": "string",
                    "type": "string (code, json, yaml, etc)",
                    "schema": "object (optional)",
                },
                tags=["validate", "check"],
            ),
            # Thinking/reasoning
            ToolDefinition(
                name="think",
                description="Record reasoning step (Chain of Draft pattern)",
                level=ToolLevel.ATOMIC,
                input_schema={
                    "thought": "string",
                    "confidence": "float (0-1)",
                    "next_step": "string (optional)",
                },
                tags=["reasoning", "cot"],
            ),
        ]

        for tool in atomic_tools:
            self._tools[tool.name] = tool

        logger.info(f"Registered {len(atomic_tools)} atomic tools")

    def register_domain_tool(self, tool: ToolDefinition, domain: str) -> None:
        """Register a domain-specific tool.

        Args:
            tool: Tool definition
            domain: Domain name (e.g., "security", "infrastructure")
        """
        tool.domain = domain
        tool.level = ToolLevel.DOMAIN
        self._tools[tool.name] = tool

        if domain not in self._domain_tools:
            self._domain_tools[domain] = []
        self._domain_tools[domain].append(tool.name)

        logger.debug(f"Registered domain tool '{tool.name}' for domain '{domain}'")

    def register_expert_tool(self, tool: ToolDefinition, domain: str) -> None:
        """Register an expert-level specialized tool.

        Args:
            tool: Tool definition
            domain: Domain name
        """
        tool.domain = domain
        tool.level = ToolLevel.EXPERT
        self._tools[tool.name] = tool

        if domain not in self._domain_tools:
            self._domain_tools[domain] = []
        self._domain_tools[domain].append(tool.name)

        logger.debug(f"Registered expert tool '{tool.name}' for domain '{domain}'")

    def register_agent_tools(self, agent_type: str, tool_names: list[str]) -> None:
        """Register tools that are always available for a specific agent type.

        Args:
            agent_type: Agent type identifier
            tool_names: List of tool names to associate
        """
        self._agent_tools[agent_type] = tool_names
        logger.debug(
            f"Registered {len(tool_names)} tools for agent type '{agent_type}'"
        )

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool definition or None if not found
        """
        return self._tools.get(name)

    def get_tools_for_context(
        self, context: Optional[ToolSelectionContext] = None
    ) -> list[ToolDefinition]:
        """Get tools appropriate for current context.

        Args:
            context: Tool selection context with domains and complexity

        Returns:
            List of tool definitions appropriate for context
        """
        context = context or ToolSelectionContext()

        # Always include atomic tools
        tools = [t for t in self._tools.values() if t.level == ToolLevel.ATOMIC]

        # Add agent-specific tools if agent type specified
        if context.agent_type and context.agent_type in self._agent_tools:
            for name in self._agent_tools[context.agent_type]:
                if name in self._tools and self._tools[name] not in tools:
                    tools.append(self._tools[name])

        # Add domain tools if domains detected
        if context.detected_domains:
            for domain in context.detected_domains:
                domain_tool_names = self._domain_tools.get(domain, [])
                for name in domain_tool_names:
                    if name in self._tools:
                        tool = self._tools[name]
                        if tool.level == ToolLevel.DOMAIN and tool not in tools:
                            tools.append(tool)

        # Add expert tools for complex tasks
        if context.task_complexity == "complex":
            for domain in context.detected_domains or []:
                domain_tool_names = self._domain_tools.get(domain, [])
                for name in domain_tool_names:
                    if name in self._tools:
                        tool = self._tools[name]
                        if tool.level == ToolLevel.EXPERT and tool not in tools:
                            tools.append(tool)

        # Enforce max tools limit
        max_tools = context.max_tools or self.MAX_TOTAL_TOOLS
        if len(tools) > max_tools:
            # Keep atomic tools, then prioritize by domain relevance
            atomic = [t for t in tools if t.level == ToolLevel.ATOMIC]
            non_atomic = [t for t in tools if t.level != ToolLevel.ATOMIC]
            tools = atomic + non_atomic[: max_tools - len(atomic)]

        logger.info(
            f"Selected {len(tools)} tools for context "
            f"(domains: {context.detected_domains}, complexity: {context.task_complexity})"
        )

        return tools

    def format_tools_for_prompt(
        self, tools: list[ToolDefinition], format_type: str = "compact"
    ) -> str:
        """Format tools for injection into agent prompt.

        Args:
            tools: List of tools to format
            format_type: "compact" (name + one-line desc) or "full" (with schema)

        Returns:
            Formatted string for prompt injection
        """
        if not tools:
            return "No tools available."

        if format_type == "compact":
            lines = [tool.to_prompt_format("compact") for tool in tools]
            return "\n".join(lines)
        else:
            parts = [tool.to_prompt_format("full") for tool in tools]
            return "\n\n".join(parts)

    def detect_domains(self, text: str) -> list[str]:
        """Detect relevant domains from text.

        Args:
            text: Query or task text

        Returns:
            List of detected domain names
        """
        text_lower = text.lower()

        domain_keywords = {
            "security": [
                "security",
                "vulnerability",
                "vuln",
                "cve",
                "exploit",
                "attack",
                "threat",
                "scan",
                "owasp",
                "injection",
                "xss",
                "csrf",
            ],
            "infrastructure": [
                "deploy",
                "infrastructure",
                "terraform",
                "cloudformation",
                "kubernetes",
                "docker",
                "aws",
                "azure",
                "gcp",
                "provision",
                "scale",
            ],
            "code_analysis": [
                "analyze",
                "complexity",
                "coverage",
                "lint",
                "smell",
                "refactor",
                "pattern",
                "metric",
                "quality",
            ],
            "testing": [
                "test",
                "unittest",
                "pytest",
                "coverage",
                "mock",
                "fixture",
                "assertion",
                "spec",
            ],
            "documentation": [
                "document",
                "readme",
                "docstring",
                "api doc",
                "changelog",
                "comment",
            ],
        }

        detected = []
        for domain, keywords in domain_keywords.items():
            if any(kw in text_lower for kw in keywords):
                detected.append(domain)

        return detected

    def assess_complexity(self, text: str) -> str:
        """Assess task complexity from text.

        Args:
            text: Query or task text

        Returns:
            Complexity level: "simple", "standard", or "complex"
        """
        text_lower = text.lower()

        # Complex indicators
        complex_indicators = [
            "comprehensive",
            "thorough",
            "all",
            "complete",
            "full audit",
            "deep dive",
            "analyze entire",
            "security review",
            "penetration test",
            "compliance check",
        ]

        # Simple indicators
        simple_indicators = [
            "quick",
            "simple",
            "just",
            "only",
            "single",
            "one file",
            "specific",
            "this function",
        ]

        if any(ind in text_lower for ind in complex_indicators):
            return "complex"
        elif any(ind in text_lower for ind in simple_indicators):
            return "simple"
        else:
            return "standard"

    def get_all_domains(self) -> list[str]:
        """Get list of all registered domains.

        Returns:
            List of domain names
        """
        return list(self._domain_tools.keys())

    def get_tools_by_domain(self, domain: str) -> list[ToolDefinition]:
        """Get all tools for a specific domain.

        Args:
            domain: Domain name

        Returns:
            List of tools in that domain
        """
        tool_names = self._domain_tools.get(domain, [])
        return [self._tools[name] for name in tool_names if name in self._tools]

    def get_tools_requiring_hitl(self) -> list[ToolDefinition]:
        """Get all tools that require human-in-the-loop approval.

        Returns:
            List of HITL-required tools
        """
        return [t for t in self._tools.values() if t.requires_hitl]

    def get_registry_stats(self) -> dict:
        """Get statistics about the tool registry.

        Returns:
            Dictionary with registry statistics
        """
        level_counts = dict.fromkeys(ToolLevel, 0)
        for tool in self._tools.values():
            level_counts[tool.level] += 1

        return {
            "total_tools": len(self._tools),
            "atomic_tools": level_counts[ToolLevel.ATOMIC],
            "domain_tools": level_counts[ToolLevel.DOMAIN],
            "expert_tools": level_counts[ToolLevel.EXPERT],
            "domains": list(self._domain_tools.keys()),
            "hitl_required": len(self.get_tools_requiring_hitl()),
        }
