"""Six-Layer Context Stack Manager

Implements ADR-034 Phase 1.3: Context Stack Management

Implements Anthropic's context engineering best practice:
explicit management of the six context layers.

Research shows missing 70% of what makes agents reliable by treating
"the prompt" as a single text block. Explicit layer management enables
optimal context curation.
"""

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class ContextLayer(IntEnum):
    """Six layers of the context stack (ordered by priority).

    Stack assembly order (top to bottom in prompt):
    1. System Instructions - Agent identity and rules (static, cache-friendly)
    2. Long-term Memory - Persistent knowledge (Titan neural memory)
    3. Retrieved Documents - RAG context (hybrid GraphRAG)
    4. Tool Definitions - Available actions (hierarchical, ~20 core)
    5. Conversation History - Session context (summarization + pruning)
    6. Current Task - Immediate objective (fresh for each request)
    """

    SYSTEM_INSTRUCTIONS = 1
    LONG_TERM_MEMORY = 2
    RETRIEVED_DOCUMENTS = 3
    TOOL_DEFINITIONS = 4
    CONVERSATION_HISTORY = 5
    CURRENT_TASK = 6


class TitanMemoryService(Protocol):
    """Protocol for Titan neural memory service."""

    async def retrieve(self, query: str, limit: int = 5) -> dict:
        """Retrieve relevant memories for query."""
        ...


class ContextRetrievalService(Protocol):
    """Protocol for context retrieval service."""

    async def retrieve_context(self, query: str, context_budget: int = 50000) -> Any:
        """Retrieve context for query."""
        ...


class HierarchicalToolRegistry(Protocol):
    """Protocol for tool registry."""

    def get_tools_for_context(self, context: Any) -> list:
        """Get tools for context."""
        ...

    def format_tools_for_prompt(self, tools: list, format_type: str) -> str:
        """Format tools for prompt."""
        ...


@dataclass
class ContextLayerContent:
    """Content for a single context layer."""

    layer: ContextLayer
    content: str
    token_count: int
    is_cached: bool = False
    priority: int = 1  # Higher = more important, less likely to be pruned
    metadata: dict = field(default_factory=dict)


@dataclass
class ContextStackConfig:
    """Configuration for context stack budgets."""

    total_budget: int = 100000
    layer_budgets: dict = field(
        default_factory=lambda: {
            ContextLayer.SYSTEM_INSTRUCTIONS: 2000,
            ContextLayer.LONG_TERM_MEMORY: 10000,
            ContextLayer.RETRIEVED_DOCUMENTS: 50000,
            ContextLayer.TOOL_DEFINITIONS: 3000,
            ContextLayer.CONVERSATION_HISTORY: 20000,
            ContextLayer.CURRENT_TASK: 15000,
        }
    )
    layer_priorities: dict = field(
        default_factory=lambda: {
            ContextLayer.CURRENT_TASK: 10,  # Highest - never prune
            ContextLayer.SYSTEM_INSTRUCTIONS: 9,  # Critical for behavior
            ContextLayer.LONG_TERM_MEMORY: 7,
            ContextLayer.RETRIEVED_DOCUMENTS: 6,
            ContextLayer.TOOL_DEFINITIONS: 5,
            ContextLayer.CONVERSATION_HISTORY: 4,  # Lowest - prune first
        }
    )
    separator: str = "\n\n---\n\n"


@dataclass
class ConversationTurn:
    """A single turn in conversation history."""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: Optional[str] = None
    token_count: Optional[int] = None


class ContextStackManager:
    """Manages the six-layer context stack for optimal agent performance.

    Each layer has:
    - Dedicated token budget
    - Specific management strategy
    - Priority for pruning decisions

    Stack assembly order (top to bottom in prompt):
    1. System Instructions (static, often cached by API)
    2. Long-term Memory (from Titan neural memory)
    3. Retrieved Documents (from hybrid GraphRAG)
    4. Tool Definitions (hierarchical, context-appropriate)
    5. Conversation History (summarized if long)
    6. Current Task (fresh each request)

    Key features:
    - Automatic token budget enforcement
    - Priority-based pruning when over budget
    - Layer-specific content builders
    - Support for API caching markers
    """

    # Agent type system prompts
    AGENT_SYSTEM_PROMPTS = {
        "Orchestrator": """You are the Meta-Orchestrator for Project Aura, an autonomous code intelligence platform.
Your role is to coordinate specialized agents to accomplish complex tasks.
You have access to the full context and can delegate work to Coder, Reviewer, and Validator agents.
Always plan before executing and verify results after delegation.""",
        "Coder": """You are a secure code generation agent for Project Aura.
Your role is to write high-quality, secure code following best practices.
You must follow OWASP guidelines, avoid common vulnerabilities, and produce maintainable code.
Always consider edge cases and include appropriate error handling.""",
        "Reviewer": """You are a security code review agent for Project Aura.
Your role is to analyze code for security vulnerabilities, code quality issues, and potential bugs.
You must check for OWASP Top 10 vulnerabilities, injection flaws, and access control issues.
Provide specific, actionable feedback with severity ratings.""",
        "Validator": """You are a code validation agent for Project Aura.
Your role is to verify that code changes are correct, complete, and meet requirements.
You must check test coverage, run validation checks, and ensure all acceptance criteria are met.
Report any discrepancies or missing elements.""",
        "Analyst": """You are a code analysis agent for Project Aura.
Your role is to analyze codebases for patterns, architecture, and potential improvements.
You can identify code smells, suggest refactoring, and analyze dependencies.
Provide insights with supporting evidence from the code.""",
    }

    DEFAULT_SYSTEM_PROMPT = """You are an AI assistant for Project Aura, an autonomous code intelligence platform.
You help with software engineering tasks including code analysis, security review, and development.
Follow security best practices and provide clear, actionable guidance."""

    def __init__(
        self,
        config: Optional[ContextStackConfig] = None,
        titan_memory_service: Optional[TitanMemoryService] = None,
        context_retrieval_service: Optional[ContextRetrievalService] = None,
        tool_registry: Optional[HierarchicalToolRegistry] = None,
    ):
        """Initialize context stack manager.

        Args:
            config: Stack configuration (budgets, priorities)
            titan_memory_service: Service for long-term memory retrieval
            context_retrieval_service: Service for RAG context retrieval
            tool_registry: Registry for hierarchical tool management
        """
        self.config = config or ContextStackConfig()
        self.titan_memory = titan_memory_service
        self.context_retrieval = context_retrieval_service
        self.tool_registry = tool_registry

        self._layers: dict[ContextLayer, ContextLayerContent] = {}

    async def build_context_stack(
        self,
        task: str,
        agent_type: str = "Orchestrator",
        conversation_history: Optional[list[dict]] = None,
        detected_domains: Optional[list[str]] = None,
        custom_system_prompt: Optional[str] = None,
        include_memory: bool = True,
        include_retrieval: bool = True,
        include_tools: bool = True,
    ) -> str:
        """Build complete context stack for agent invocation.

        Args:
            task: Current task description
            agent_type: Type of agent (Coder, Reviewer, Validator, etc.)
            conversation_history: Prior conversation turns
            detected_domains: Domains detected for tool selection
            custom_system_prompt: Override default system prompt
            include_memory: Whether to include Titan memory layer
            include_retrieval: Whether to include RAG retrieval layer
            include_tools: Whether to include tool definitions layer

        Returns:
            Assembled context string ready for LLM prompt
        """
        self._layers.clear()

        # Layer 1: System Instructions (static per agent type)
        self._layers[ContextLayer.SYSTEM_INSTRUCTIONS] = self._build_system_layer(
            agent_type, custom_system_prompt
        )

        # Layer 2: Long-term Memory (from Titan)
        if include_memory and self.titan_memory:
            memory_layer = await self._build_memory_layer(task)
            if memory_layer:
                self._layers[ContextLayer.LONG_TERM_MEMORY] = memory_layer

        # Layer 3: Retrieved Documents (from hybrid GraphRAG)
        if include_retrieval and self.context_retrieval:
            retrieval_layer = await self._build_retrieval_layer(task)
            if retrieval_layer:
                self._layers[ContextLayer.RETRIEVED_DOCUMENTS] = retrieval_layer

        # Layer 4: Tool Definitions (hierarchical)
        if include_tools and self.tool_registry:
            tools_layer = self._build_tools_layer(detected_domains)
            if tools_layer:
                self._layers[ContextLayer.TOOL_DEFINITIONS] = tools_layer

        # Layer 5: Conversation History (summarized if needed)
        if conversation_history:
            history_layer = self._build_history_layer(conversation_history)
            if history_layer:
                self._layers[ContextLayer.CONVERSATION_HISTORY] = history_layer

        # Layer 6: Current Task (always fresh)
        self._layers[ContextLayer.CURRENT_TASK] = ContextLayerContent(
            layer=ContextLayer.CURRENT_TASK,
            content=f"## Current Task\n\n{task}",
            token_count=self._estimate_tokens(task) + 20,
            priority=self.config.layer_priorities[ContextLayer.CURRENT_TASK],
        )

        # Enforce budgets and assemble
        self._enforce_budgets()
        assembled = self._assemble_stack()

        logger.info(
            f"Built context stack: {len(self._layers)} layers, "
            f"{sum(layer.token_count for layer in self._layers.values())} total tokens"
        )

        return assembled

    def _build_system_layer(
        self, agent_type: str, custom_prompt: Optional[str] = None
    ) -> ContextLayerContent:
        """Build system instructions layer.

        Args:
            agent_type: Type of agent
            custom_prompt: Optional custom system prompt

        Returns:
            System layer content
        """
        if custom_prompt:
            content = custom_prompt
        else:
            content = self.AGENT_SYSTEM_PROMPTS.get(
                agent_type, self.DEFAULT_SYSTEM_PROMPT
            )

        formatted = f"## System Instructions\n\n{content}"

        return ContextLayerContent(
            layer=ContextLayer.SYSTEM_INSTRUCTIONS,
            content=formatted,
            token_count=self._estimate_tokens(formatted),
            is_cached=True,  # Can use API caching
            priority=self.config.layer_priorities[ContextLayer.SYSTEM_INSTRUCTIONS],
            metadata={"agent_type": agent_type},
        )

    async def _build_memory_layer(self, task: str) -> Optional[ContextLayerContent]:
        """Build long-term memory layer from Titan.

        Args:
            task: Current task for memory retrieval

        Returns:
            Memory layer content or None
        """
        try:
            budget = self.config.layer_budgets[ContextLayer.LONG_TERM_MEMORY]
            if self.titan_memory is None:
                return None
            memory_result = await self.titan_memory.retrieve(task, limit=5)

            if not memory_result:
                return None

            content = "## Relevant Experience\n\n"
            if isinstance(memory_result, dict):
                summary = memory_result.get("summary", "")
                memories = memory_result.get("memories", [])

                if summary:
                    content += f"{summary}\n\n"

                for mem in memories[:5]:
                    if isinstance(mem, dict):
                        mem_text = mem.get("content", str(mem))
                    else:
                        mem_text = str(mem)
                    content += f"- {mem_text[:500]}\n"
            else:
                content += str(memory_result)[: budget * 4]  # type: ignore[unreachable]

            return ContextLayerContent(
                layer=ContextLayer.LONG_TERM_MEMORY,
                content=content,
                token_count=self._estimate_tokens(content),
                priority=self.config.layer_priorities[ContextLayer.LONG_TERM_MEMORY],
            )

        except Exception as e:
            logger.warning(f"Failed to retrieve memory: {e}")
            return None

    async def _build_retrieval_layer(self, task: str) -> Optional[ContextLayerContent]:
        """Build retrieved documents layer from GraphRAG.

        Args:
            task: Current task for context retrieval

        Returns:
            Retrieval layer content or None
        """
        try:
            budget = self.config.layer_budgets[ContextLayer.RETRIEVED_DOCUMENTS]

            if self.context_retrieval is None:
                return None
            retrieval_result = await self.context_retrieval.retrieve_context(
                query=task, context_budget=budget
            )

            if not retrieval_result:
                return None

            content = "## Retrieved Context\n\n"

            # Handle different result formats
            if hasattr(retrieval_result, "files"):
                files = getattr(retrieval_result, "files", [])
                for file in files[:10]:
                    file_path = getattr(file, "file_path", "unknown")
                    file_content = getattr(file, "content", "")[:2000]
                    content += f"### {file_path}\n```\n{file_content}\n```\n\n"
                total_tokens = getattr(retrieval_result, "total_tokens", 0)
            elif isinstance(retrieval_result, list):
                for item in retrieval_result[:10]:
                    if isinstance(item, dict):
                        path = item.get("file_path", item.get("path", "unknown"))
                        item_content = item.get("content", "")[:2000]
                    else:
                        path = "result"
                        item_content = str(item)[:2000]
                    content += f"### {path}\n```\n{item_content}\n```\n\n"
                total_tokens = self._estimate_tokens(content)
            else:
                content += str(retrieval_result)[: budget * 4]
                total_tokens = self._estimate_tokens(content)

            return ContextLayerContent(
                layer=ContextLayer.RETRIEVED_DOCUMENTS,
                content=content,
                token_count=total_tokens or self._estimate_tokens(content),
                priority=self.config.layer_priorities[ContextLayer.RETRIEVED_DOCUMENTS],
            )

        except Exception as e:
            logger.warning(f"Failed to retrieve context: {e}")
            return None

    def _build_tools_layer(
        self, domains: Optional[list[str]] = None
    ) -> Optional[ContextLayerContent]:
        """Build tool definitions layer (hierarchical).

        Args:
            domains: Detected domains for tool selection

        Returns:
            Tools layer content or None
        """
        try:
            # Create context for tool selection
            from src.services.hierarchical_tool_registry import ToolSelectionContext

            context = ToolSelectionContext(
                detected_domains=domains or [],
                task_complexity="standard",
            )

            if self.tool_registry is None:
                return None
            tools = self.tool_registry.get_tools_for_context(context)

            if not tools:
                return None

            content = self.tool_registry.format_tools_for_prompt(
                tools, format_type="compact"
            )

            formatted = f"## Available Tools\n\n{content}"

            return ContextLayerContent(
                layer=ContextLayer.TOOL_DEFINITIONS,
                content=formatted,
                token_count=self._estimate_tokens(formatted),
                priority=self.config.layer_priorities[ContextLayer.TOOL_DEFINITIONS],
                metadata={"tool_count": len(tools)},
            )

        except Exception as e:
            logger.warning(f"Failed to build tools layer: {e}")
            return None

    def _build_history_layer(
        self, history: list[dict]
    ) -> Optional[ContextLayerContent]:
        """Build conversation history layer with budget enforcement.

        Args:
            history: List of conversation turns with 'role' and 'content'

        Returns:
            History layer content or None
        """
        if not history:
            return None

        budget = self.config.layer_budgets[ContextLayer.CONVERSATION_HISTORY]

        content = "## Conversation History\n\n"
        turns_added: list[str] = []
        total_tokens = self._estimate_tokens(content)

        # Add turns from most recent first, stop when budget exceeded
        for turn in reversed(history[-20:]):  # Limit to last 20 turns
            role = turn.get("role", "unknown")
            turn_content = turn.get("content", "")

            turn_text = f"**{role}:** {turn_content}\n\n"
            turn_tokens = self._estimate_tokens(turn_text)

            if total_tokens + turn_tokens > budget:
                break

            turns_added.insert(0, turn_text)
            total_tokens += turn_tokens

        if not turns_added:
            return None

        content += "".join(turns_added)

        return ContextLayerContent(
            layer=ContextLayer.CONVERSATION_HISTORY,
            content=content,
            token_count=total_tokens,
            priority=self.config.layer_priorities[ContextLayer.CONVERSATION_HISTORY],
            metadata={"turns_included": len(turns_added)},
        )

    def _enforce_budgets(self) -> None:
        """Enforce token budgets by priority-based pruning.

        Prunes lowest priority layers first until within total budget.
        """
        total_used = sum(layer.token_count for layer in self._layers.values())

        if total_used <= self.config.total_budget:
            return

        logger.info(
            f"Context over budget: {total_used}/{self.config.total_budget}. Pruning..."
        )

        # Sort by priority (lowest first for pruning)
        layers_by_priority = sorted(self._layers.items(), key=lambda x: x[1].priority)

        excess = total_used - self.config.total_budget

        for layer_type, layer_content in layers_by_priority:
            if excess <= 0:
                break

            # Skip current task - never prune
            if layer_type == ContextLayer.CURRENT_TASK:
                continue

            # Calculate how much to reduce
            max_reduction = layer_content.token_count // 2  # At most halve a layer
            reduction = min(excess, max_reduction)

            if reduction > 0:
                # Truncate content proportionally
                ratio = 1 - (reduction / layer_content.token_count)
                new_length = int(len(layer_content.content) * ratio)
                layer_content.content = (
                    layer_content.content[:new_length] + "\n... (truncated)"
                )
                layer_content.token_count -= reduction
                excess -= reduction

                logger.debug(f"Pruned {layer_type.name}: reduced by {reduction} tokens")

    def _assemble_stack(self) -> str:
        """Assemble all layers into final context string.

        Returns:
            Complete context string with all layers
        """
        # Order by layer enum value (1-6)
        ordered_layers = sorted(self._layers.values(), key=lambda x: x.layer.value)

        parts = [layer.content for layer in ordered_layers if layer.content]

        return self.config.separator.join(parts)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (4 chars per token for English).

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return max(1, len(text) // 4)

    def get_layer(self, layer: ContextLayer) -> Optional[ContextLayerContent]:
        """Get a specific layer's content.

        Args:
            layer: Layer to retrieve

        Returns:
            Layer content or None
        """
        return self._layers.get(layer)

    def get_stack_stats(self) -> dict:
        """Get statistics about the current context stack.

        Returns:
            Dictionary with stack statistics
        """
        return {
            "layer_count": len(self._layers),
            "total_tokens": sum(layer.token_count for layer in self._layers.values()),
            "budget": self.config.total_budget,
            "layers": {
                layer.name: {
                    "tokens": content.token_count,
                    "budget": self.config.layer_budgets.get(layer, 0),
                    "priority": content.priority,
                    "cached": content.is_cached,
                }
                for layer, content in self._layers.items()
            },
        }

    def clear(self) -> None:
        """Clear all layers."""
        self._layers.clear()
