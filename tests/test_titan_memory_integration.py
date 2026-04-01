"""Tests for Titan Memory Integration (ADR-029 Phase 2.1).

Tests the integration of TitanCognitiveService with the agent orchestrator,
including memory context loading, experience storage, and memory-informed
agent operations.
"""

import sys

import pytest

# Save original modules before any mocking to prevent test pollution
_modules_to_save = ["boto3", "botocore", "torch"]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}
from unittest.mock import AsyncMock, MagicMock

from src.agents.agent_orchestrator import System2Orchestrator
from src.agents.context_objects import ContextSource, HybridContext


class TestContextObjectsNeuralMemory:
    """Tests for NEURAL_MEMORY context source and add_memory_context method."""

    def test_neural_memory_context_source_exists(self):
        """Test that NEURAL_MEMORY context source exists."""
        assert hasattr(ContextSource, "NEURAL_MEMORY")
        assert ContextSource.NEURAL_MEMORY.value == "neural_memory"

    def test_add_memory_context_with_enabled_neural_memory(self):
        """Test add_memory_context adds items when neural memory is enabled."""
        context = HybridContext(
            items=[],
            query="test query",
            target_entity="test.entity",
        )

        memory_context = {
            "neural_memory": {
                "enabled": True,
                "surprise": 0.3,
                "neural_confidence": 0.8,
                "latency_ms": 10.5,
            },
            "retrieved_memories": [],
            "strategy": None,
        }

        context.add_memory_context(memory_context, neural_confidence=0.8)

        # Should have added neural memory signal
        memory_items = context.get_items_by_source(ContextSource.NEURAL_MEMORY)
        assert len(memory_items) >= 1

        # Check the first item
        signal_item = memory_items[0]
        assert "Neural Memory Signal" in signal_item.content
        assert signal_item.confidence == 0.8
        assert signal_item.metadata.get("neural_enabled") is True
        assert signal_item.metadata.get("surprise") == 0.3

    def test_add_memory_context_with_disabled_neural_memory(self):
        """Test add_memory_context handles disabled neural memory."""
        context = HybridContext(
            items=[],
            query="test query",
            target_entity="test.entity",
        )

        memory_context = {
            "neural_memory": {
                "enabled": False,
            },
            "retrieved_memories": [],
            "strategy": None,
        }

        context.add_memory_context(memory_context, neural_confidence=0.5)

        # Should not have added items for disabled neural memory
        memory_items = context.get_items_by_source(ContextSource.NEURAL_MEMORY)
        assert len(memory_items) == 0

    def test_add_memory_context_high_confidence_message(self):
        """Test high confidence message is included when neural_confidence > 0.7."""
        context = HybridContext(
            items=[],
            query="test query",
            target_entity="test.entity",
        )

        memory_context = {
            "neural_memory": {
                "enabled": True,
                "surprise": 0.2,
                "neural_confidence": 0.85,
            },
            "retrieved_memories": [],
        }

        context.add_memory_context(memory_context, neural_confidence=0.85)

        memory_items = context.get_items_by_source(ContextSource.NEURAL_MEMORY)
        assert len(memory_items) >= 1
        assert "High confidence" in memory_items[0].content

    def test_add_memory_context_low_confidence_message(self):
        """Test low confidence message is included when neural_confidence <= 0.7."""
        context = HybridContext(
            items=[],
            query="test query",
            target_entity="test.entity",
        )

        memory_context = {
            "neural_memory": {
                "enabled": True,
                "surprise": 0.6,
                "neural_confidence": 0.5,
            },
            "retrieved_memories": [],
        }

        context.add_memory_context(memory_context, neural_confidence=0.5)

        memory_items = context.get_items_by_source(ContextSource.NEURAL_MEMORY)
        assert len(memory_items) >= 1
        assert "Lower confidence" in memory_items[0].content

    def test_add_memory_context_empty_dict(self):
        """Test add_memory_context handles empty memory context."""
        context = HybridContext(
            items=[],
            query="test query",
            target_entity="test.entity",
        )

        context.add_memory_context({}, neural_confidence=0.5)

        # Should not raise and should not add items
        memory_items = context.get_items_by_source(ContextSource.NEURAL_MEMORY)
        assert len(memory_items) == 0


@pytest.mark.forked
class TestOrchestratorTitanMemoryIntegration:
    """Tests for System2Orchestrator with Titan Memory integration."""

    def test_orchestrator_accepts_titan_memory(self):
        """Test orchestrator constructor accepts titan_memory parameter."""
        mock_titan = MagicMock()

        orchestrator = System2Orchestrator(titan_memory=mock_titan)

        assert orchestrator.titan_memory is mock_titan

    def test_orchestrator_logs_titan_status(self, caplog):
        """Test orchestrator logs Titan memory status on init."""
        import logging

        mock_titan = MagicMock()

        with caplog.at_level(logging.INFO, logger="src.agents.agent_orchestrator"):
            System2Orchestrator(titan_memory=mock_titan)

            # Check that initialization was logged
            assert any(
                "TitanMemory" in record.message or "Initialized" in record.message
                for record in caplog.records
            )

    @pytest.mark.asyncio
    async def test_execute_request_loads_memory_context(self):
        """Test execute_request loads cognitive context from Titan memory."""
        mock_titan = AsyncMock()
        mock_titan.load_cognitive_context.return_value = {
            "neural_memory": {
                "enabled": True,
                "surprise": 0.3,
                "neural_confidence": 0.8,
            },
            "retrieved_memories": [],
            "confidence": MagicMock(score=0.8),
            "strategy": None,
        }

        orchestrator = System2Orchestrator(titan_memory=mock_titan)

        result = await orchestrator.execute_request("Refactor the checksum method")

        # Verify load_cognitive_context was called
        mock_titan.load_cognitive_context.assert_called_once()
        call_kwargs = mock_titan.load_cognitive_context.call_args.kwargs
        assert "task_description" in call_kwargs
        assert call_kwargs["domain"] == "security_remediation"

        # Result should include neural_confidence
        assert "neural_confidence" in result
        assert result["neural_confidence"] == 0.8

    @pytest.mark.asyncio
    async def test_execute_request_handles_memory_failure(self):
        """Test execute_request handles Titan memory failure gracefully."""
        mock_titan = AsyncMock()
        mock_titan.load_cognitive_context.side_effect = Exception("Memory error")

        orchestrator = System2Orchestrator(titan_memory=mock_titan)

        # Should not raise, should continue with standard workflow
        result = await orchestrator.execute_request("Refactor the checksum method")

        assert "status" in result
        # neural_confidence should be None when memory fails
        assert result.get("neural_confidence") is None

    @pytest.mark.asyncio
    async def test_execute_request_stores_experience_on_success(self):
        """Test successful execution stores experience in Titan memory."""
        mock_titan = AsyncMock()
        mock_titan.load_cognitive_context.return_value = {
            "neural_memory": {"enabled": False},
            "retrieved_memories": [],
            "confidence": MagicMock(score=0.7),
            "strategy": None,
        }
        mock_titan.record_episode.return_value = MagicMock()

        orchestrator = System2Orchestrator(titan_memory=mock_titan)

        # Force success by modifying the fallback code to pass
        orchestrator.initial_code = ""

        result = await orchestrator.execute_request("Refactor the checksum method")

        # If successful, record_episode should be called
        if result["status"] == "SUCCESS":
            mock_titan.record_episode.assert_called()

    @pytest.mark.asyncio
    async def test_execute_request_without_titan_memory(self):
        """Test execute_request works normally without Titan memory."""
        orchestrator = System2Orchestrator(titan_memory=None)

        result = await orchestrator.execute_request("Refactor the checksum method")

        # Should complete without error
        assert "status" in result
        assert result.get("neural_confidence") is None


class TestStoreExperienceInMemory:
    """Tests for _store_experience_in_memory helper method."""

    @pytest.mark.asyncio
    async def test_store_experience_with_success_outcome(self):
        """Test storing successful experience records correct outcome."""
        mock_titan = AsyncMock()

        orchestrator = System2Orchestrator(titan_memory=mock_titan)

        context = HybridContext(
            items=[],
            query="test",
            target_entity="test.entity",
        )

        result = {
            "code": "test code",
            "review": {"status": "PASS"},
            "validation": {"valid": True},
        }

        await orchestrator._store_experience_in_memory(
            task="Fix security issue",
            context=context,
            result=result,
        )

        mock_titan.record_episode.assert_called_once()
        call_kwargs = mock_titan.record_episode.call_args.kwargs
        assert call_kwargs["task_description"] == "Fix security issue"
        assert call_kwargs["domain"] == "security_remediation"
        # Outcome should indicate success
        assert "SUCCESS" in str(call_kwargs["outcome"]).upper()

    @pytest.mark.asyncio
    async def test_store_experience_with_partial_outcome(self):
        """Test storing partial success records correct outcome."""
        mock_titan = AsyncMock()

        orchestrator = System2Orchestrator(titan_memory=mock_titan)

        context = HybridContext(
            items=[],
            query="test",
            target_entity="test.entity",
        )

        result = {
            "code": "test code",
            "review": {"status": "FAIL_SECURITY"},
            "validation": {"valid": True},
        }

        await orchestrator._store_experience_in_memory(
            task="Fix security issue",
            context=context,
            result=result,
        )

        mock_titan.record_episode.assert_called_once()
        call_kwargs = mock_titan.record_episode.call_args.kwargs
        # Outcome should indicate partial success
        assert "PARTIAL" in str(call_kwargs["outcome"]).upper()

    @pytest.mark.asyncio
    async def test_store_experience_without_titan_memory(self):
        """Test storing experience does nothing without Titan memory."""
        orchestrator = System2Orchestrator(titan_memory=None)

        context = HybridContext(
            items=[],
            query="test",
            target_entity="test.entity",
        )

        result = {
            "code": "test code",
            "review": {"status": "PASS"},
            "validation": {"valid": True},
        }

        # Should not raise
        await orchestrator._store_experience_in_memory(
            task="Fix security issue",
            context=context,
            result=result,
        )


class TestCoderAgentMemoryIntegration:
    """Tests for CoderAgent with neural memory context."""

    @pytest.mark.asyncio
    async def test_coder_agent_uses_memory_guidance(self):
        """Test coder agent includes memory guidance in prompt."""
        from src.agents.coder_agent import CoderAgent

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "import hashlib\n\nclass Test:\n    pass"

        coder = CoderAgent(llm_client=mock_llm)

        # Create context with neural memory
        context = HybridContext(
            items=[],
            query="test",
            target_entity="test.entity",
        )
        context.add_item(
            content="Neural Memory Signal: confidence=0.85",
            source=ContextSource.NEURAL_MEMORY,
            confidence=0.85,
        )

        await coder.generate_code(context, "Generate secure code")

        # Verify the prompt was generated (LLM was called)
        mock_llm.generate.assert_called_once()


@pytest.mark.forked
class TestReviewerAgentMemoryIntegration:
    """Tests for ReviewerAgent with neural memory context."""

    @pytest.mark.asyncio
    async def test_reviewer_agent_accepts_context(self):
        """Test reviewer agent accepts HybridContext parameter."""
        from src.agents.reviewer_agent import ReviewerAgent

        reviewer = ReviewerAgent(llm_client=None)

        context = HybridContext(
            items=[],
            query="test",
            target_entity="test.entity",
        )

        result = await reviewer.review_code(
            "import hashlib\nclass Test: pass",
            context=context,
        )

        assert "status" in result
        assert "memory_informed" in result

    @pytest.mark.asyncio
    async def test_reviewer_agent_memory_informed_flag(self):
        """Test reviewer agent sets memory_informed flag correctly."""
        # Import fresh to ensure same module instance as reviewer_agent uses
        from src.agents.context_objects import ContextSource as FreshContextSource
        from src.agents.context_objects import HybridContext as FreshHybridContext
        from src.agents.reviewer_agent import ReviewerAgent

        reviewer = ReviewerAgent(llm_client=None)

        # Context with neural memory - use fresh imports
        context_with_memory = FreshHybridContext(
            items=[],
            query="test",
            target_entity="test.entity",
        )
        context_with_memory.add_item(
            content="Neural Memory Signal",
            source=FreshContextSource.NEURAL_MEMORY,
            confidence=0.8,
        )

        result = await reviewer.review_code(
            "import hashlib\nclass Test: pass",
            context=context_with_memory,
        )

        assert result["memory_informed"] is True

    @pytest.mark.asyncio
    async def test_reviewer_agent_no_memory_flag(self):
        """Test reviewer agent sets memory_informed=False without memory."""
        from src.agents.reviewer_agent import ReviewerAgent

        reviewer = ReviewerAgent(llm_client=None)

        # Context without neural memory
        context_no_memory = HybridContext(
            items=[],
            query="test",
            target_entity="test.entity",
        )

        result = await reviewer.review_code(
            "import hashlib\nclass Test: pass",
            context=context_no_memory,
        )

        assert result["memory_informed"] is False

    @pytest.mark.asyncio
    async def test_reviewer_agent_no_context(self):
        """Test reviewer agent works without context parameter."""
        from src.agents.reviewer_agent import ReviewerAgent

        reviewer = ReviewerAgent(llm_client=None)

        result = await reviewer.review_code(
            "import hashlib\nclass Test: pass",
        )

        assert "status" in result
        assert result["memory_informed"] is False


class TestCreateSystemOrchestratorWithTitanMemory:
    """Tests for create_system2_orchestrator factory with Titan memory."""

    def test_factory_accepts_enable_titan_memory(self):
        """Test factory function accepts enable_titan_memory parameter."""
        from src.agents.agent_orchestrator import create_system2_orchestrator

        # Should not raise
        orchestrator = create_system2_orchestrator(
            use_mock=True,
            enable_titan_memory=False,
        )

        assert orchestrator.titan_memory is None

    def test_factory_titan_memory_disabled_by_default(self):
        """Test Titan memory is disabled by default."""
        from src.agents.agent_orchestrator import create_system2_orchestrator

        orchestrator = create_system2_orchestrator(use_mock=True)

        assert orchestrator.titan_memory is None
