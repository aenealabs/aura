"""
Context Objects for Aura Platform
==================================
Structured context objects for type-safe, traceable context passing between agents.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ContextSource(Enum):
    """Defines the source/type of context information"""

    GRAPH_STRUCTURAL = "graph"
    VECTOR_SEMANTIC = "vector"
    SECURITY_POLICY = "security"
    REMEDIATION = "remediation"
    USER_PROMPT = "user_prompt"
    COMPLIANCE = "compliance"
    NEURAL_MEMORY = "neural_memory"  # ADR-029 Phase 2.1: Titan Memory Integration


@dataclass
class ContextItem:
    """
    A single piece of context with metadata for traceability and debugging.

    Attributes:
        content: The actual context content/string
        source: Where this context came from (graph, vector, security, etc.)
        confidence: Confidence score 0.0-1.0 for this context item
        entity_id: Optional identifier for the code entity this relates to
        timestamp: When this context was created
        metadata: Additional key-value metadata for debugging/tracing
    """

    content: str
    source: ContextSource
    confidence: float = 1.0
    entity_id: str | None = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range"""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass
class HybridContext:
    """
    Container for hybrid RAG context combining structural and semantic information.

    This provides a type-safe, traceable way to pass context between agents
    with full metadata and debugging support.

    Attributes:
        items: List of context items from various sources
        query: The original user query that triggered context retrieval
        target_entity: The target code entity being analyzed
        session_id: Optional session identifier for tracing
    """

    items: list[ContextItem]
    query: str
    target_entity: str
    session_id: str | None = None
    created_at: float = field(default_factory=time.time)

    def add_item(
        self,
        content: str,
        source: ContextSource,
        confidence: float = 1.0,
        entity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Add a new context item to the collection.

        Args:
            content: The context content
            source: Source of the context
            confidence: Confidence score 0.0-1.0
            entity_id: Optional entity identifier
            metadata: Optional metadata dict
        """
        item = ContextItem(
            content=content,
            source=source,
            confidence=confidence,
            entity_id=entity_id,
            metadata=metadata or {},
        )
        self.items.append(item)

    def add_remediation(self, content: str, confidence: float = 1.0):
        """Convenience method to add remediation context"""
        self.add_item(content, ContextSource.REMEDIATION, confidence=confidence)

    def add_security_policy(self, content: str, confidence: float = 1.0):
        """Convenience method to add security policy context"""
        self.add_item(content, ContextSource.SECURITY_POLICY, confidence=confidence)

    def add_memory_context(
        self, memory_context: dict[str, Any], neural_confidence: float = 0.5
    ):
        """Add neural memory context from TitanCognitiveService (ADR-029 Phase 2.1).

        This method integrates neural memory retrieval results into the hybrid context,
        allowing agents to leverage learned patterns and episodic experiences.

        Args:
            memory_context: Context from TitanCognitiveService.load_cognitive_context()
            neural_confidence: Confidence score from neural memory (0.0-1.0)
        """
        # Extract key information from memory context
        neural_memory = memory_context.get("neural_memory", {})
        retrieved_memories = memory_context.get("retrieved_memories", [])
        strategy = memory_context.get("strategy", {})

        # Add neural memory signal if enabled
        if neural_memory.get("enabled", False):
            surprise = neural_memory.get("surprise", 0.5)
            content = (
                f"Neural Memory Signal: confidence={neural_confidence:.2f}, "
                f"surprise={surprise:.2f}. "
                f"{'High confidence - familiar pattern.' if neural_confidence > 0.7 else 'Lower confidence - less familiar pattern.'}"
            )
            self.add_item(
                content=content,
                source=ContextSource.NEURAL_MEMORY,
                confidence=neural_confidence,
                metadata={
                    "surprise": surprise,
                    "neural_enabled": True,
                    "latency_ms": neural_memory.get("latency_ms", 0),
                },
            )

        # Add relevant episodic memories from traditional retrieval
        for memory in retrieved_memories[:3]:  # Top 3 memories
            if hasattr(memory, "memory") and hasattr(memory.memory, "content"):
                self.add_item(
                    content=f"Past Experience: {memory.memory.content}",
                    source=ContextSource.NEURAL_MEMORY,
                    confidence=getattr(memory, "combined_score", 0.7),
                    metadata={
                        "memory_type": getattr(memory, "memory_type", "episodic"),
                        "recency_score": getattr(memory, "recency_score", 0.5),
                    },
                )

        # Add strategy context if available
        if strategy and hasattr(strategy, "strategy_type"):
            self.add_item(
                content=f"Recommended Strategy: {strategy.strategy_type.value} approach based on past experiences.",
                source=ContextSource.NEURAL_MEMORY,
                confidence=neural_confidence,
                metadata={"strategy": str(strategy.strategy_type)},
            )

    def get_items_by_source(self, source: ContextSource) -> list[ContextItem]:
        """Get all context items from a specific source"""
        return [item for item in self.items if item.source == source]

    def get_high_confidence_items(self, threshold: float = 0.8) -> list[ContextItem]:
        """Get all context items above a confidence threshold"""
        return [item for item in self.items if item.confidence >= threshold]

    def to_prompt_string(self, include_metadata: bool = False) -> str:
        """
        Convert context to a string suitable for LLM prompts.

        Args:
            include_metadata: Whether to include source/confidence metadata in output

        Returns:
            Formatted string representation of context
        """
        if not include_metadata:
            return "\n".join([item.content for item in self.items])

        # Include metadata for debugging/transparency
        lines = []
        for item in self.items:
            lines.append(f"[{item.source.value}] (confidence: {item.confidence:.2f})")
            lines.append(item.content)
            lines.append("")  # Blank line separator
        return "\n".join(lines)

    def get_context_summary(self) -> dict[str, Any]:
        """
        Get a summary of context composition for debugging/monitoring.

        Returns:
            Dict with summary statistics about the context
        """
        source_counts: dict[str, int] = {}
        for item in self.items:
            source_name = item.source.value
            source_counts[source_name] = source_counts.get(source_name, 0) + 1

        return {
            "total_items": len(self.items),
            "items_by_source": source_counts,
            "avg_confidence": (
                sum(item.confidence for item in self.items) / len(self.items)
                if self.items
                else 0.0
            ),
            "query": self.query,
            "target_entity": self.target_entity,
            "session_id": self.session_id,
        }

    def __str__(self) -> str:
        """String representation for debugging"""
        summary = self.get_context_summary()
        return f"HybridContext(items={summary['total_items']}, sources={summary['items_by_source']}, target='{self.target_entity}')"
