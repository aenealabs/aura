"""
Tests for Context Stack Manager.

Covers ContextLayer enum, ContextLayerContent/ContextStackConfig/ConversationTurn
dataclasses, and ContextStackManager for six-layer context management.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.context_stack_manager import (
    ContextLayer,
    ContextLayerContent,
    ContextStackConfig,
    ContextStackManager,
    ConversationTurn,
)

# =============================================================================
# ContextLayer Enum Tests
# =============================================================================


class TestContextLayer:
    """Tests for ContextLayer enum."""

    def test_system_instructions(self):
        """Test system instructions layer."""
        assert ContextLayer.SYSTEM_INSTRUCTIONS.value == 1

    def test_long_term_memory(self):
        """Test long-term memory layer."""
        assert ContextLayer.LONG_TERM_MEMORY.value == 2

    def test_retrieved_documents(self):
        """Test retrieved documents layer."""
        assert ContextLayer.RETRIEVED_DOCUMENTS.value == 3

    def test_tool_definitions(self):
        """Test tool definitions layer."""
        assert ContextLayer.TOOL_DEFINITIONS.value == 4

    def test_conversation_history(self):
        """Test conversation history layer."""
        assert ContextLayer.CONVERSATION_HISTORY.value == 5

    def test_current_task(self):
        """Test current task layer."""
        assert ContextLayer.CURRENT_TASK.value == 6

    def test_layer_count(self):
        """Test that all 6 layers exist."""
        assert len(ContextLayer) == 6

    def test_layer_ordering(self):
        """Test that layers are ordered correctly."""
        assert ContextLayer.SYSTEM_INSTRUCTIONS < ContextLayer.CURRENT_TASK


# =============================================================================
# ContextLayerContent Dataclass Tests
# =============================================================================


class TestContextLayerContent:
    """Tests for ContextLayerContent dataclass."""

    def test_create_basic_content(self):
        """Test creating basic layer content."""
        content = ContextLayerContent(
            layer=ContextLayer.CURRENT_TASK,
            content="Find the bug",
            token_count=100,
        )

        assert content.layer == ContextLayer.CURRENT_TASK
        assert content.content == "Find the bug"
        assert content.token_count == 100

    def test_default_values(self):
        """Test default values for optional fields."""
        content = ContextLayerContent(
            layer=ContextLayer.SYSTEM_INSTRUCTIONS,
            content="System prompt",
            token_count=50,
        )

        assert content.is_cached is False
        assert content.priority == 1
        assert content.metadata == {}

    def test_full_content(self):
        """Test content with all fields."""
        content = ContextLayerContent(
            layer=ContextLayer.TOOL_DEFINITIONS,
            content="Tool list here",
            token_count=300,
            is_cached=True,
            priority=5,
            metadata={"tool_count": 10},
        )

        assert content.is_cached is True
        assert content.priority == 5
        assert content.metadata["tool_count"] == 10


# =============================================================================
# ContextStackConfig Dataclass Tests
# =============================================================================


class TestContextStackConfig:
    """Tests for ContextStackConfig dataclass."""

    def test_default_total_budget(self):
        """Test default total budget."""
        config = ContextStackConfig()

        assert config.total_budget == 100000

    def test_default_layer_budgets(self):
        """Test default layer budgets."""
        config = ContextStackConfig()

        assert config.layer_budgets[ContextLayer.SYSTEM_INSTRUCTIONS] == 2000
        assert config.layer_budgets[ContextLayer.LONG_TERM_MEMORY] == 10000
        assert config.layer_budgets[ContextLayer.RETRIEVED_DOCUMENTS] == 50000
        assert config.layer_budgets[ContextLayer.TOOL_DEFINITIONS] == 3000
        assert config.layer_budgets[ContextLayer.CONVERSATION_HISTORY] == 20000
        assert config.layer_budgets[ContextLayer.CURRENT_TASK] == 15000

    def test_default_layer_priorities(self):
        """Test default layer priorities."""
        config = ContextStackConfig()

        # Current task should have highest priority
        assert config.layer_priorities[ContextLayer.CURRENT_TASK] == 10
        # History should have lowest priority
        assert config.layer_priorities[ContextLayer.CONVERSATION_HISTORY] == 4

    def test_default_separator(self):
        """Test default separator."""
        config = ContextStackConfig()

        assert config.separator == "\n\n---\n\n"

    def test_custom_config(self):
        """Test custom configuration."""
        custom_budgets = {ContextLayer.CURRENT_TASK: 5000}
        config = ContextStackConfig(
            total_budget=50000,
            layer_budgets=custom_budgets,
        )

        assert config.total_budget == 50000
        assert config.layer_budgets[ContextLayer.CURRENT_TASK] == 5000


# =============================================================================
# ConversationTurn Dataclass Tests
# =============================================================================


class TestConversationTurn:
    """Tests for ConversationTurn dataclass."""

    def test_create_basic_turn(self):
        """Test creating a basic conversation turn."""
        turn = ConversationTurn(
            role="user",
            content="Hello, can you help?",
        )

        assert turn.role == "user"
        assert turn.content == "Hello, can you help?"

    def test_default_values(self):
        """Test default values."""
        turn = ConversationTurn(role="assistant", content="Sure!")

        assert turn.timestamp is None
        assert turn.token_count is None

    def test_full_turn(self):
        """Test turn with all fields."""
        turn = ConversationTurn(
            role="assistant",
            content="Here is my response",
            timestamp="2025-12-21T10:00:00Z",
            token_count=50,
        )

        assert turn.timestamp == "2025-12-21T10:00:00Z"
        assert turn.token_count == 50


# =============================================================================
# ContextStackManager Initialization Tests
# =============================================================================


class TestContextStackManagerInit:
    """Tests for ContextStackManager initialization."""

    def test_initialization_defaults(self):
        """Test initialization with defaults."""
        manager = ContextStackManager()

        assert manager.config is not None
        assert manager.titan_memory is None
        assert manager.context_retrieval is None
        assert manager.tool_registry is None
        assert manager._layers == {}

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = ContextStackConfig(total_budget=50000)
        manager = ContextStackManager(config=config)

        assert manager.config.total_budget == 50000

    def test_initialization_with_services(self):
        """Test initialization with services."""
        memory = MagicMock()
        retrieval = MagicMock()
        tools = MagicMock()

        manager = ContextStackManager(
            titan_memory_service=memory,
            context_retrieval_service=retrieval,
            tool_registry=tools,
        )

        assert manager.titan_memory == memory
        assert manager.context_retrieval == retrieval
        assert manager.tool_registry == tools


# =============================================================================
# System Layer Tests
# =============================================================================


class TestSystemLayer:
    """Tests for system layer building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ContextStackManager()

    def test_build_system_layer_orchestrator(self):
        """Test building system layer for Orchestrator agent."""
        layer = self.manager._build_system_layer("Orchestrator")

        assert layer.layer == ContextLayer.SYSTEM_INSTRUCTIONS
        assert "Meta-Orchestrator" in layer.content
        assert layer.is_cached is True
        assert layer.metadata["agent_type"] == "Orchestrator"

    def test_build_system_layer_coder(self):
        """Test building system layer for Coder agent."""
        layer = self.manager._build_system_layer("Coder")

        assert "secure code generation" in layer.content

    def test_build_system_layer_reviewer(self):
        """Test building system layer for Reviewer agent."""
        layer = self.manager._build_system_layer("Reviewer")

        assert "security code review" in layer.content

    def test_build_system_layer_validator(self):
        """Test building system layer for Validator agent."""
        layer = self.manager._build_system_layer("Validator")

        assert "validation agent" in layer.content

    def test_build_system_layer_analyst(self):
        """Test building system layer for Analyst agent."""
        layer = self.manager._build_system_layer("Analyst")

        assert "analysis agent" in layer.content

    def test_build_system_layer_unknown_agent(self):
        """Test building system layer for unknown agent type."""
        layer = self.manager._build_system_layer("UnknownAgent")

        # Should use default prompt
        assert "AI assistant for Project Aura" in layer.content

    def test_build_system_layer_custom_prompt(self):
        """Test building system layer with custom prompt."""
        custom = "Custom system instructions here"
        layer = self.manager._build_system_layer("Coder", custom_prompt=custom)

        assert custom in layer.content


# =============================================================================
# Context Stack Building Tests
# =============================================================================


class TestBuildContextStack:
    """Tests for building context stack."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ContextStackManager()

    @pytest.mark.asyncio
    async def test_build_basic_stack(self):
        """Test building basic context stack."""
        result = await self.manager.build_context_stack(
            task="Fix the bug in auth module",
            agent_type="Coder",
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        assert "System Instructions" in result
        assert "Current Task" in result
        assert "Fix the bug in auth module" in result

    @pytest.mark.asyncio
    async def test_build_stack_clears_layers(self):
        """Test that building stack clears previous layers."""
        # Build first stack
        await self.manager.build_context_stack(
            task="Task 1",
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        # Build second stack
        await self.manager.build_context_stack(
            task="Task 2",
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        # Should only have layers from second build
        assert "Task 2" in self.manager._layers[ContextLayer.CURRENT_TASK].content

    @pytest.mark.asyncio
    async def test_build_stack_with_history(self):
        """Test building stack with conversation history."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        result = await self.manager.build_context_stack(
            task="Continue conversation",
            conversation_history=history,
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        assert "Conversation History" in result

    @pytest.mark.asyncio
    async def test_build_stack_with_memory_service(self):
        """Test building stack with memory service."""
        memory = AsyncMock()
        memory.retrieve.return_value = {
            "summary": "Previous experience",
            "memories": [{"content": "Memory 1"}],
        }

        manager = ContextStackManager(titan_memory_service=memory)

        result = await manager.build_context_stack(
            task="Use experience",
            include_retrieval=False,
            include_tools=False,
        )

        memory.retrieve.assert_called_once()
        assert "Relevant Experience" in result

    @pytest.mark.asyncio
    async def test_build_stack_with_tool_registry(self):
        """Test building stack with tool registry."""
        tools = MagicMock()
        tools.get_tools_for_context.return_value = [MagicMock(name="tool1")]
        tools.format_tools_for_prompt.return_value = "- tool1: A tool"

        manager = ContextStackManager(tool_registry=tools)

        result = await manager.build_context_stack(
            task="Use tools",
            detected_domains=["security"],
            include_memory=False,
            include_retrieval=False,
        )

        assert "tool1" in result


# =============================================================================
# Token Estimation Tests
# =============================================================================


class TestTokenEstimation:
    """Tests for token estimation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ContextStackManager()

    def test_estimate_tokens_empty(self):
        """Test token estimation for empty string."""
        count = self.manager._estimate_tokens("")

        # Empty string may return 0 or 1 depending on implementation
        assert count <= 1

    def test_estimate_tokens_short_text(self):
        """Test token estimation for short text."""
        count = self.manager._estimate_tokens("Hello world")

        assert count > 0
        assert count < 10  # Should be about 2-3 tokens

    def test_estimate_tokens_longer_text(self):
        """Test token estimation for longer text."""
        text = "The quick brown fox jumps over the lazy dog. " * 10
        count = self.manager._estimate_tokens(text)

        assert count > 50


# =============================================================================
# Budget Enforcement Tests
# =============================================================================


class TestBudgetEnforcement:
    """Tests for budget enforcement."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ContextStackManager()

    def test_enforce_budgets_under_limit(self):
        """Test budget enforcement when under limit."""
        self.manager._layers = {
            ContextLayer.CURRENT_TASK: ContextLayerContent(
                layer=ContextLayer.CURRENT_TASK,
                content="Short task",
                token_count=100,
                priority=10,
            ),
        }

        # Should not raise
        self.manager._enforce_budgets()

    def test_get_total_tokens(self):
        """Test getting total tokens from layers."""
        self.manager._layers = {
            ContextLayer.CURRENT_TASK: ContextLayerContent(
                layer=ContextLayer.CURRENT_TASK,
                content="Task",
                token_count=100,
            ),
            ContextLayer.SYSTEM_INSTRUCTIONS: ContextLayerContent(
                layer=ContextLayer.SYSTEM_INSTRUCTIONS,
                content="System",
                token_count=200,
            ),
        }

        total = sum(layer.token_count for layer in self.manager._layers.values())
        assert total == 300


# =============================================================================
# Stack Assembly Tests
# =============================================================================


class TestStackAssembly:
    """Tests for stack assembly."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ContextStackManager()

    def test_assemble_stack_empty(self):
        """Test assembling empty stack."""
        self.manager._layers = {}

        result = self.manager._assemble_stack()

        assert result == ""

    def test_assemble_stack_single_layer(self):
        """Test assembling stack with single layer."""
        self.manager._layers = {
            ContextLayer.CURRENT_TASK: ContextLayerContent(
                layer=ContextLayer.CURRENT_TASK,
                content="Current task content",
                token_count=50,
            ),
        }

        result = self.manager._assemble_stack()

        assert "Current task content" in result

    def test_assemble_stack_multiple_layers(self):
        """Test assembling stack with multiple layers."""
        self.manager._layers = {
            ContextLayer.SYSTEM_INSTRUCTIONS: ContextLayerContent(
                layer=ContextLayer.SYSTEM_INSTRUCTIONS,
                content="System prompt",
                token_count=50,
            ),
            ContextLayer.CURRENT_TASK: ContextLayerContent(
                layer=ContextLayer.CURRENT_TASK,
                content="Current task",
                token_count=50,
            ),
        }

        result = self.manager._assemble_stack()

        # System should come before task
        assert result.index("System prompt") < result.index("Current task")


# =============================================================================
# Integration Tests
# =============================================================================


class TestContextStackManagerIntegration:
    """Integration tests for context stack manager."""

    @pytest.mark.asyncio
    async def test_full_workflow_coder_agent(self):
        """Test full workflow for Coder agent."""
        manager = ContextStackManager()

        result = await manager.build_context_stack(
            task="Implement JWT validation",
            agent_type="Coder",
            include_memory=False,
            include_retrieval=False,
            include_tools=False,
        )

        # Should have system and task layers
        assert "secure code generation" in result
        assert "JWT validation" in result

    @pytest.mark.asyncio
    async def test_full_workflow_with_all_services(self):
        """Test full workflow with all services mocked."""
        memory = AsyncMock()
        memory.retrieve.return_value = {"summary": "Prior JWT work"}

        retrieval = AsyncMock()
        retrieval.retrieve_context.return_value = MagicMock(
            files=[{"path": "/auth.py", "content": "code"}],
            total_tokens=100,
        )

        tools = MagicMock()
        tools.get_tools_for_context.return_value = []
        tools.format_tools_for_prompt.return_value = ""

        manager = ContextStackManager(
            titan_memory_service=memory,
            context_retrieval_service=retrieval,
            tool_registry=tools,
        )

        _result = await manager.build_context_stack(
            task="Review authentication",
            agent_type="Reviewer",
            detected_domains=["security"],
        )

        # Verify all services were called
        memory.retrieve.assert_called_once()
        retrieval.retrieve_context.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
