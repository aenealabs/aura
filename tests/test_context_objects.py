"""
Project Aura - Context Objects Tests

Comprehensive tests for type-safe context objects.
"""

# ruff: noqa: PLR2004

import time

import pytest

from src.agents.context_objects import ContextItem, ContextSource, HybridContext


class TestContextSource:
    """Test suite for ContextSource enum."""

    def test_context_source_values(self):
        """Test that all context source types are defined."""
        assert ContextSource.GRAPH_STRUCTURAL.value == "graph"
        assert ContextSource.VECTOR_SEMANTIC.value == "vector"
        assert ContextSource.SECURITY_POLICY.value == "security"
        assert ContextSource.REMEDIATION.value == "remediation"
        assert ContextSource.USER_PROMPT.value == "user_prompt"
        assert ContextSource.COMPLIANCE.value == "compliance"


class TestContextItem:
    """Test suite for ContextItem dataclass."""

    def test_context_item_creation_minimal(self):
        """Test creating context item with minimal required fields."""
        item = ContextItem(
            content="Test content",
            source=ContextSource.GRAPH_STRUCTURAL,
        )

        assert item.content == "Test content"
        assert item.source == ContextSource.GRAPH_STRUCTURAL
        assert item.confidence == 1.0  # Default value
        assert item.entity_id is None  # Default value
        assert item.timestamp > 0
        assert item.metadata == {}  # Default empty dict

    def test_context_item_creation_full(self):
        """Test creating context item with all fields."""
        metadata = {"key": "value", "count": 42}
        item = ContextItem(
            content="Full content",
            source=ContextSource.VECTOR_SEMANTIC,
            confidence=0.85,
            entity_id="entity_123",
            metadata=metadata,
        )

        assert item.content == "Full content"
        assert item.source == ContextSource.VECTOR_SEMANTIC
        assert item.confidence == 0.85
        assert item.entity_id == "entity_123"
        assert item.metadata == metadata

    def test_context_item_timestamp_auto_generated(self):
        """Test that timestamp is automatically generated."""
        before = time.time()
        item = ContextItem("content", ContextSource.REMEDIATION)
        after = time.time()

        assert before <= item.timestamp <= after

    def test_context_item_confidence_validation_valid(self):
        """Test confidence validation accepts valid values."""
        # Boundary values
        item1 = ContextItem("content", ContextSource.GRAPH_STRUCTURAL, confidence=0.0)
        assert item1.confidence == 0.0

        item2 = ContextItem("content", ContextSource.GRAPH_STRUCTURAL, confidence=1.0)
        assert item2.confidence == 1.0

        # Middle value
        item3 = ContextItem("content", ContextSource.GRAPH_STRUCTURAL, confidence=0.5)
        assert item3.confidence == 0.5

    def test_context_item_confidence_validation_invalid_high(self):
        """Test confidence validation rejects values > 1.0."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            ContextItem("content", ContextSource.GRAPH_STRUCTURAL, confidence=1.5)

    def test_context_item_confidence_validation_invalid_low(self):
        """Test confidence validation rejects values < 0.0."""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            ContextItem("content", ContextSource.GRAPH_STRUCTURAL, confidence=-0.1)

    def test_context_item_metadata_independence(self):
        """Test that metadata dict is independent between instances."""
        item1 = ContextItem("content1", ContextSource.GRAPH_STRUCTURAL)
        item2 = ContextItem("content2", ContextSource.VECTOR_SEMANTIC)

        item1.metadata["key"] = "value1"
        item2.metadata["key"] = "value2"

        assert item1.metadata["key"] == "value1"
        assert item2.metadata["key"] == "value2"


class TestHybridContext:
    """Test suite for HybridContext container."""

    def test_hybrid_context_creation_empty(self):
        """Test creating HybridContext with empty items list."""
        context = HybridContext(
            items=[],
            query="test query",
            target_entity="TestEntity",
        )

        assert context.items == []
        assert context.query == "test query"
        assert context.target_entity == "TestEntity"
        assert context.session_id is None
        assert context.created_at > 0

    def test_hybrid_context_creation_with_items(self):
        """Test creating HybridContext with initial items."""
        item1 = ContextItem("content1", ContextSource.GRAPH_STRUCTURAL)
        item2 = ContextItem("content2", ContextSource.VECTOR_SEMANTIC)

        context = HybridContext(
            items=[item1, item2],
            query="test query",
            target_entity="TestEntity",
            session_id="session_123",
        )

        assert len(context.items) == 2
        assert context.session_id == "session_123"

    def test_add_item_method(self):
        """Test adding items using add_item method."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        context.add_item(
            content="test content",
            source=ContextSource.GRAPH_STRUCTURAL,
            confidence=0.9,
            entity_id="entity_1",
            metadata={"key": "value"},
        )

        assert len(context.items) == 1
        item = context.items[0]
        assert item.content == "test content"
        assert item.source == ContextSource.GRAPH_STRUCTURAL
        assert item.confidence == 0.9
        assert item.entity_id == "entity_1"
        assert item.metadata == {"key": "value"}

    def test_add_item_metadata_defaults_to_empty_dict(self):
        """Test add_item with None metadata defaults to empty dict."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        context.add_item("content", ContextSource.REMEDIATION, metadata=None)

        assert context.items[0].metadata == {}

    def test_add_remediation_convenience_method(self):
        """Test add_remediation convenience method."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        context.add_remediation("Fix the vulnerability", confidence=0.95)

        assert len(context.items) == 1
        item = context.items[0]
        assert item.content == "Fix the vulnerability"
        assert item.source == ContextSource.REMEDIATION
        assert item.confidence == 0.95

    def test_add_security_policy_convenience_method(self):
        """Test add_security_policy convenience method."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        context.add_security_policy("OWASP Top 10 compliance required", confidence=1.0)

        assert len(context.items) == 1
        item = context.items[0]
        assert item.content == "OWASP Top 10 compliance required"
        assert item.source == ContextSource.SECURITY_POLICY
        assert item.confidence == 1.0

    def test_get_items_by_source(self):
        """Test filtering items by source."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        context.add_item("graph1", ContextSource.GRAPH_STRUCTURAL)
        context.add_item("vector1", ContextSource.VECTOR_SEMANTIC)
        context.add_item("graph2", ContextSource.GRAPH_STRUCTURAL)
        context.add_item("security1", ContextSource.SECURITY_POLICY)

        graph_items = context.get_items_by_source(ContextSource.GRAPH_STRUCTURAL)

        assert len(graph_items) == 2
        assert all(
            item.source == ContextSource.GRAPH_STRUCTURAL for item in graph_items
        )
        contents = [item.content for item in graph_items]
        assert "graph1" in contents
        assert "graph2" in contents

    def test_get_items_by_source_empty(self):
        """Test get_items_by_source returns empty list when no matches."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        context.add_item("content", ContextSource.GRAPH_STRUCTURAL)

        compliance_items = context.get_items_by_source(ContextSource.COMPLIANCE)

        assert compliance_items == []

    def test_get_high_confidence_items_default_threshold(self):
        """Test getting high confidence items with default threshold."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        context.add_item("high1", ContextSource.GRAPH_STRUCTURAL, confidence=0.9)
        context.add_item("low1", ContextSource.VECTOR_SEMANTIC, confidence=0.7)
        context.add_item("high2", ContextSource.REMEDIATION, confidence=0.85)
        context.add_item("low2", ContextSource.SECURITY_POLICY, confidence=0.5)

        high_items = context.get_high_confidence_items()  # Default threshold 0.8

        assert len(high_items) == 2
        assert all(item.confidence >= 0.8 for item in high_items)
        contents = [item.content for item in high_items]
        assert "high1" in contents
        assert "high2" in contents

    def test_get_high_confidence_items_custom_threshold(self):
        """Test getting high confidence items with custom threshold."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        context.add_item("item1", ContextSource.GRAPH_STRUCTURAL, confidence=0.95)
        context.add_item("item2", ContextSource.VECTOR_SEMANTIC, confidence=0.90)
        context.add_item("item3", ContextSource.REMEDIATION, confidence=0.85)

        high_items = context.get_high_confidence_items(threshold=0.92)

        assert len(high_items) == 1
        assert high_items[0].content == "item1"

    def test_to_prompt_string_without_metadata(self):
        """Test converting context to prompt string without metadata."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        context.add_item("First line of context", ContextSource.GRAPH_STRUCTURAL)
        context.add_item("Second line of context", ContextSource.VECTOR_SEMANTIC)
        context.add_item("Third line of context", ContextSource.REMEDIATION)

        prompt = context.to_prompt_string(include_metadata=False)

        assert (
            prompt
            == "First line of context\nSecond line of context\nThird line of context"
        )

    def test_to_prompt_string_with_metadata(self):
        """Test converting context to prompt string with metadata."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        context.add_item("Content A", ContextSource.GRAPH_STRUCTURAL, confidence=0.95)
        context.add_item("Content B", ContextSource.VECTOR_SEMANTIC, confidence=0.80)

        prompt = context.to_prompt_string(include_metadata=True)

        assert "[graph] (confidence: 0.95)" in prompt
        assert "Content A" in prompt
        assert "[vector] (confidence: 0.80)" in prompt
        assert "Content B" in prompt

    def test_to_prompt_string_empty_context(self):
        """Test to_prompt_string with no items."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        prompt = context.to_prompt_string()

        assert prompt == ""

    def test_get_context_summary(self):
        """Test getting context summary statistics."""
        context = HybridContext(
            items=[],
            query="test query",
            target_entity="TestEntity",
            session_id="session_123",
        )

        context.add_item("graph1", ContextSource.GRAPH_STRUCTURAL, confidence=1.0)
        context.add_item("graph2", ContextSource.GRAPH_STRUCTURAL, confidence=0.8)
        context.add_item("vector1", ContextSource.VECTOR_SEMANTIC, confidence=0.9)
        context.add_item("security1", ContextSource.SECURITY_POLICY, confidence=0.7)

        summary = context.get_context_summary()

        assert summary["total_items"] == 4
        assert summary["items_by_source"]["graph"] == 2
        assert summary["items_by_source"]["vector"] == 1
        assert summary["items_by_source"]["security"] == 1
        assert abs(summary["avg_confidence"] - (1.0 + 0.8 + 0.9 + 0.7) / 4) < 0.001
        assert summary["query"] == "test query"
        assert summary["target_entity"] == "TestEntity"
        assert summary["session_id"] == "session_123"

    def test_get_context_summary_empty(self):
        """Test get_context_summary with no items."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        summary = context.get_context_summary()

        assert summary["total_items"] == 0
        assert summary["items_by_source"] == {}
        assert summary["avg_confidence"] == 0.0

    def test_str_representation(self):
        """Test string representation of HybridContext."""
        context = HybridContext(items=[], query="query", target_entity="MyEntity")

        context.add_item("content1", ContextSource.GRAPH_STRUCTURAL)
        context.add_item("content2", ContextSource.VECTOR_SEMANTIC)

        str_repr = str(context)

        assert "HybridContext" in str_repr
        assert "items=2" in str_repr
        assert "MyEntity" in str_repr

    def test_multiple_add_item_calls(self):
        """Test multiple sequential add_item calls."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        for i in range(5):
            context.add_item(f"content{i}", ContextSource.GRAPH_STRUCTURAL)

        assert len(context.items) == 5

    def test_items_by_source_counts_in_summary(self):
        """Test that items_by_source counts are accurate."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        # Add various source types
        context.add_item("g1", ContextSource.GRAPH_STRUCTURAL)
        context.add_item("g2", ContextSource.GRAPH_STRUCTURAL)
        context.add_item("g3", ContextSource.GRAPH_STRUCTURAL)
        context.add_item("v1", ContextSource.VECTOR_SEMANTIC)
        context.add_item("r1", ContextSource.REMEDIATION)
        context.add_item("r2", ContextSource.REMEDIATION)

        summary = context.get_context_summary()

        assert summary["items_by_source"]["graph"] == 3
        assert summary["items_by_source"]["vector"] == 1
        assert summary["items_by_source"]["remediation"] == 2

    def test_average_confidence_calculation(self):
        """Test average confidence calculation accuracy."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        context.add_item("c1", ContextSource.GRAPH_STRUCTURAL, confidence=0.5)
        context.add_item("c2", ContextSource.VECTOR_SEMANTIC, confidence=0.7)
        context.add_item("c3", ContextSource.REMEDIATION, confidence=0.9)

        summary = context.get_context_summary()

        expected_avg = (0.5 + 0.7 + 0.9) / 3
        assert abs(summary["avg_confidence"] - expected_avg) < 0.001

    def test_created_at_timestamp(self):
        """Test that created_at timestamp is set."""
        before = time.time()
        context = HybridContext(items=[], query="query", target_entity="entity")
        after = time.time()

        assert before <= context.created_at <= after

    def test_session_id_optional(self):
        """Test that session_id is optional and defaults to None."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        assert context.session_id is None

    def test_session_id_custom(self):
        """Test setting custom session_id."""
        context = HybridContext(
            items=[],
            query="query",
            target_entity="entity",
            session_id="custom-session-123",
        )

        assert context.session_id == "custom-session-123"


class TestAddMemoryContext:
    """Tests for add_memory_context method - ADR-029 Phase 2.1."""

    def test_add_memory_context_with_neural_memory_enabled(self):
        """Test adding memory context with neural memory enabled."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        memory_context = {
            "neural_memory": {
                "enabled": True,
                "surprise": 0.3,
                "latency_ms": 45,
            },
            "retrieved_memories": [],
            "strategy": None,
        }

        context.add_memory_context(memory_context, neural_confidence=0.85)

        # Should have added a neural memory item
        assert len(context.items) == 1
        item = context.items[0]
        assert item.source == ContextSource.NEURAL_MEMORY
        assert item.confidence == 0.85
        assert "Neural Memory Signal" in item.content
        assert "0.85" in item.content
        assert "High confidence" in item.content
        assert item.metadata["surprise"] == 0.3
        assert item.metadata["neural_enabled"] is True
        assert item.metadata["latency_ms"] == 45

    def test_add_memory_context_low_confidence(self):
        """Test memory context with low neural confidence."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        memory_context = {
            "neural_memory": {
                "enabled": True,
                "surprise": 0.7,
            },
            "retrieved_memories": [],
            "strategy": None,
        }

        context.add_memory_context(memory_context, neural_confidence=0.5)

        assert len(context.items) == 1
        item = context.items[0]
        assert "Lower confidence" in item.content

    def test_add_memory_context_neural_disabled(self):
        """Test memory context with neural memory disabled."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        memory_context = {
            "neural_memory": {
                "enabled": False,
            },
            "retrieved_memories": [],
            "strategy": None,
        }

        context.add_memory_context(memory_context, neural_confidence=0.5)

        # No items added since neural is disabled
        assert len(context.items) == 0

    def test_add_memory_context_with_retrieved_memories(self):
        """Test adding memory context with retrieved episodic memories."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        # Create mock memory objects
        class MockMemory:
            def __init__(self, content):
                self.content = content

        class MockRetrievedMemory:
            def __init__(self, content, combined_score, memory_type):
                self.memory = MockMemory(content)
                self.combined_score = combined_score
                self.memory_type = memory_type
                self.recency_score = 0.6

        memory_context = {
            "neural_memory": {"enabled": False},
            "retrieved_memories": [
                MockRetrievedMemory("Past fix for SQL injection", 0.9, "episodic"),
                MockRetrievedMemory("Previous security review", 0.85, "semantic"),
                MockRetrievedMemory("Old debugging session", 0.7, "procedural"),
            ],
            "strategy": None,
        }

        context.add_memory_context(memory_context, neural_confidence=0.5)

        # Should have 3 episodic memory items
        assert len(context.items) == 3
        assert all(item.source == ContextSource.NEURAL_MEMORY for item in context.items)
        assert "Past Experience" in context.items[0].content
        assert context.items[0].confidence == 0.9

    def test_add_memory_context_with_strategy(self):
        """Test adding memory context with strategy recommendation."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        # Create mock strategy object
        class MockStrategyType:
            value = "defensive"

        class MockStrategy:
            strategy_type = MockStrategyType()

        memory_context = {
            "neural_memory": {"enabled": False},
            "retrieved_memories": [],
            "strategy": MockStrategy(),
        }

        context.add_memory_context(memory_context, neural_confidence=0.75)

        assert len(context.items) == 1
        item = context.items[0]
        assert "Recommended Strategy" in item.content
        assert "defensive" in item.content
        assert item.source == ContextSource.NEURAL_MEMORY
        assert item.confidence == 0.75

    def test_add_memory_context_full_integration(self):
        """Test full memory context with all components enabled."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        class MockMemory:
            def __init__(self, content):
                self.content = content

        class MockRetrievedMemory:
            def __init__(self, content):
                self.memory = MockMemory(content)
                self.combined_score = 0.88
                self.memory_type = "episodic"
                self.recency_score = 0.5

        class MockStrategyType:
            value = "aggressive"

        class MockStrategy:
            strategy_type = MockStrategyType()

        memory_context = {
            "neural_memory": {
                "enabled": True,
                "surprise": 0.2,
                "latency_ms": 30,
            },
            "retrieved_memories": [MockRetrievedMemory("Memory 1")],
            "strategy": MockStrategy(),
        }

        context.add_memory_context(memory_context, neural_confidence=0.9)

        # Should have: 1 neural signal + 1 memory + 1 strategy = 3 items
        assert len(context.items) == 3
        contents = [item.content for item in context.items]
        assert any("Neural Memory Signal" in c for c in contents)
        assert any("Past Experience" in c for c in contents)
        assert any("Recommended Strategy" in c for c in contents)

    def test_add_memory_context_empty_dict(self):
        """Test memory context with empty dict."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        memory_context = {}

        context.add_memory_context(memory_context, neural_confidence=0.5)

        # Empty dict should add nothing
        assert len(context.items) == 0

    def test_add_memory_context_limits_memories_to_three(self):
        """Test that only top 3 memories are added."""
        context = HybridContext(items=[], query="query", target_entity="entity")

        class MockMemory:
            def __init__(self, content):
                self.content = content

        class MockRetrievedMemory:
            def __init__(self, content):
                self.memory = MockMemory(content)
                self.combined_score = 0.8
                self.memory_type = "episodic"
                self.recency_score = 0.5

        memory_context = {
            "neural_memory": {"enabled": False},
            "retrieved_memories": [
                MockRetrievedMemory("Memory 1"),
                MockRetrievedMemory("Memory 2"),
                MockRetrievedMemory("Memory 3"),
                MockRetrievedMemory("Memory 4"),  # Should be ignored
                MockRetrievedMemory("Memory 5"),  # Should be ignored
            ],
            "strategy": None,
        }

        context.add_memory_context(memory_context, neural_confidence=0.5)

        # Only top 3 memories should be added
        assert len(context.items) == 3
