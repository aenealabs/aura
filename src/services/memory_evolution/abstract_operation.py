"""
Project Aura - ABSTRACT Operation Service (ADR-080 Phase 3)

LLM-based strategy extraction from task experiences using hybrid
embedding clustering (HDBSCAN) + LLM refinement pipeline.

The ABSTRACT operation:
1. Clusters related memories using HDBSCAN on embeddings
2. Identifies abstraction candidates based on coherence scores
3. Uses LLM to extract generalizable strategies from clusters
4. Validates extracted strategies for quality and applicability
5. Stores strategies for future retrieval and reuse

Quality Metrics (per Mike's feedback):
- transfer_success_rate: How often the strategy succeeds in new contexts
- compression_ratio: Information density (strategy size / source size)
- reconstruction_accuracy: How well strategy captures source patterns

Reference: ADR-080 Evo-Memory Enhancements (Phase 3)
"""

import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional, Protocol

import numpy as np

from .config import MemoryEvolutionConfig, get_memory_evolution_config
from .contracts import (
    AbstractedStrategy,
    AbstractionCandidate,
    RefineAction,
    RefineOperation,
    RefineResult,
)

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOLS
# =============================================================================


class BedrockClientProtocol(Protocol):
    """Protocol for Bedrock LLM client operations."""

    def invoke_model(
        self,
        prompt: str,
        agent: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Invoke Bedrock model."""
        ...


class EmbeddingServiceProtocol(Protocol):
    """Protocol for embedding service operations."""

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for a list of texts."""
        ...


class MemoryStoreProtocol(Protocol):
    """Protocol for memory store operations."""

    async def get_memories(
        self,
        memory_ids: list[str],
        tenant_id: str,
        security_domain: str,
    ) -> list[dict[str, Any]]:
        """Retrieve memories by IDs."""
        ...

    async def store_strategy(
        self,
        strategy: AbstractedStrategy,
    ) -> str:
        """Store an abstracted strategy. Returns strategy ID."""
        ...


class DynamoDBClientProtocol(Protocol):
    """Protocol for DynamoDB operations."""

    async def put_item(
        self,
        TableName: str,
        Item: dict[str, Any],
    ) -> dict[str, Any]:
        """Put item into DynamoDB."""
        ...


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class AbstractionConfig:
    """Configuration for ABSTRACT operations."""

    # Minimum memories to form a cluster for abstraction
    min_cluster_size: int = 3

    # Minimum coherence score for abstraction candidate
    min_coherence_threshold: float = 0.7

    # Minimum abstraction potential to proceed
    min_abstraction_potential: float = 0.6

    # HDBSCAN parameters
    hdbscan_min_samples: int = 2
    hdbscan_min_cluster_size: int = 3
    hdbscan_cluster_selection_epsilon: float = 0.0

    # LLM parameters
    llm_model: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.3

    # Quality thresholds
    min_strategy_confidence: float = 0.6
    min_compression_ratio: float = 0.3  # Strategy should be at least 30% of sources
    max_compression_ratio: float = 0.8  # But not more than 80%

    # Rate limiting
    max_abstractions_per_minute: int = 10
    cooldown_seconds: float = 6.0

    # Enable feature
    enabled: bool = True


# =============================================================================
# CLUSTERING SERVICE
# =============================================================================


class MemoryClusteringService:
    """Clusters memories using HDBSCAN for abstraction candidates.

    Uses hierarchical density-based clustering to identify groups of
    related memories that can be abstracted into generalizable strategies.
    """

    def __init__(self, config: Optional[AbstractionConfig] = None):
        """Initialize clustering service.

        Args:
            config: Abstraction configuration
        """
        self.config = config or AbstractionConfig()
        self._hdbscan_available = self._check_hdbscan()

    def _check_hdbscan(self) -> bool:
        """Check if HDBSCAN is available."""
        try:
            import hdbscan  # noqa: F401

            return True
        except ImportError:
            logger.warning("HDBSCAN not available, falling back to simple clustering")
            return False

    def cluster_memories(
        self,
        memories: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> list[AbstractionCandidate]:
        """Cluster memories and identify abstraction candidates.

        Args:
            memories: List of memory dictionaries
            embeddings: Corresponding embeddings for each memory

        Returns:
            List of abstraction candidates (memory clusters)
        """
        if len(memories) < self.config.min_cluster_size:
            logger.debug(
                f"Not enough memories ({len(memories)}) for clustering "
                f"(min: {self.config.min_cluster_size})"
            )
            return []

        if self._hdbscan_available:
            return self._cluster_with_hdbscan(memories, embeddings)
        else:
            return self._cluster_with_cosine_similarity(memories, embeddings)

    def _cluster_with_hdbscan(
        self,
        memories: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> list[AbstractionCandidate]:
        """Cluster using HDBSCAN algorithm."""
        import hdbscan

        embedding_array = np.array(embeddings)

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.config.hdbscan_min_cluster_size,
            min_samples=self.config.hdbscan_min_samples,
            cluster_selection_epsilon=self.config.hdbscan_cluster_selection_epsilon,
            metric="euclidean",
        )

        labels = clusterer.fit_predict(embedding_array)

        # Group memories by cluster
        clusters: dict[int, list[int]] = {}
        for idx, label in enumerate(labels):
            if label >= 0:  # -1 is noise
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(idx)

        candidates = []
        for cluster_id, indices in clusters.items():
            if len(indices) >= self.config.min_cluster_size:
                candidate = self._create_candidate(
                    cluster_id=str(cluster_id),
                    memories=[memories[i] for i in indices],
                    embeddings=[embeddings[i] for i in indices],
                )
                if candidate:
                    candidates.append(candidate)

        return candidates

    def _cluster_with_cosine_similarity(
        self,
        memories: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> list[AbstractionCandidate]:
        """Fallback clustering using cosine similarity (greedy approach)."""
        embedding_array = np.array(embeddings)

        # Normalize for cosine similarity
        norms = np.linalg.norm(embedding_array, axis=1, keepdims=True)
        normalized = embedding_array / (norms + 1e-10)

        # Compute similarity matrix
        similarity_matrix = np.dot(normalized, normalized.T)

        # Greedy clustering with threshold
        threshold = 0.75  # High similarity threshold
        visited = set()
        clusters: list[list[int]] = []

        for i in range(len(memories)):
            if i in visited:
                continue

            cluster = [i]
            visited.add(i)

            for j in range(i + 1, len(memories)):
                if j not in visited and similarity_matrix[i, j] >= threshold:
                    cluster.append(j)
                    visited.add(j)

            if len(cluster) >= self.config.min_cluster_size:
                clusters.append(cluster)

        candidates = []
        for idx, indices in enumerate(clusters):
            candidate = self._create_candidate(
                cluster_id=f"fallback_{idx}",
                memories=[memories[i] for i in indices],
                embeddings=[embeddings[i] for i in indices],
            )
            if candidate:
                candidates.append(candidate)

        return candidates

    def _create_candidate(
        self,
        cluster_id: str,
        memories: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> Optional[AbstractionCandidate]:
        """Create an abstraction candidate from a memory cluster."""
        if not memories or not embeddings:
            return None

        # Compute centroid
        centroid = np.mean(embeddings, axis=0).tolist()

        # Compute coherence score (average pairwise similarity)
        coherence = self._compute_coherence(embeddings)

        # Compute abstraction potential based on diversity and coherence
        diversity = self._compute_diversity(embeddings)
        abstraction_potential = 0.7 * coherence + 0.3 * diversity

        # Extract common themes from memory content
        themes = self._extract_themes(memories)

        memory_ids = [
            m.get("memory_id", m.get("id", str(i))) for i, m in enumerate(memories)
        ]

        return AbstractionCandidate(
            memory_ids=memory_ids,
            cluster_id=cluster_id,
            centroid_embedding=centroid,
            coherence_score=coherence,
            abstraction_potential=abstraction_potential,
            common_themes=themes,
            metadata={
                "memory_count": len(memories),
                "diversity_score": diversity,
            },
        )

    def _compute_coherence(self, embeddings: list[list[float]]) -> float:
        """Compute cluster coherence (average pairwise cosine similarity)."""
        if len(embeddings) < 2:
            return 1.0

        embedding_array = np.array(embeddings)
        norms = np.linalg.norm(embedding_array, axis=1, keepdims=True)
        normalized = embedding_array / (norms + 1e-10)

        similarity_matrix = np.dot(normalized, normalized.T)

        # Get upper triangle (excluding diagonal)
        upper_indices = np.triu_indices(len(embeddings), k=1)
        pairwise_similarities = similarity_matrix[upper_indices]

        return float(np.mean(pairwise_similarities))

    def _compute_diversity(self, embeddings: list[list[float]]) -> float:
        """Compute diversity score (spread of embeddings)."""
        if len(embeddings) < 2:
            return 0.0

        embedding_array = np.array(embeddings)
        centroid = np.mean(embedding_array, axis=0)

        # Average distance from centroid
        distances = np.linalg.norm(embedding_array - centroid, axis=1)
        avg_distance = float(np.mean(distances))

        # Normalize to 0-1 range (assuming typical embedding distances)
        return min(1.0, avg_distance / 2.0)

    def _extract_themes(self, memories: list[dict[str, Any]]) -> list[str]:
        """Extract common themes from memory content."""
        themes = []

        # Extract from tags if present
        all_tags = []
        for memory in memories:
            tags = memory.get("tags", [])
            all_tags.extend(tags)

        # Count tag frequency
        tag_counts: dict[str, int] = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Get most common tags
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        themes.extend([tag for tag, _ in sorted_tags[:5]])

        # Extract from content types if present
        content_types = set()
        for memory in memories:
            content_type = memory.get("content_type", memory.get("type"))
            if content_type:
                content_types.add(content_type)

        themes.extend(list(content_types)[:3])

        return themes[:8]  # Limit to 8 themes


# =============================================================================
# ABSTRACTION SERVICE
# =============================================================================


class AbstractionService:
    """LLM-based strategy extraction from memory clusters.

    Implements the hybrid embedding clustering + LLM refinement pipeline
    as recommended in ADR-080 Phase 3.
    """

    AGENT_NAME = "memory_abstraction"

    SYSTEM_PROMPT = """You are an expert at extracting generalizable strategies from task experiences.

Given a set of related task memories, your job is to:
1. Identify the common patterns and approaches across the experiences
2. Extract a generalizable strategy that captures the essence of what worked
3. Define when this strategy should be applied (applicability conditions)
4. Outline the key steps to execute the strategy
5. Specify how to know if the strategy was successful

Be concise but comprehensive. The strategy should be actionable and reusable."""

    EXTRACTION_PROMPT_TEMPLATE = """Analyze these {count} related task experiences and extract a generalizable strategy.

## Task Experiences

{experiences}

## Common Themes Detected
{themes}

## Instructions

Extract a strategy that captures what made these experiences successful. Return your response as JSON:

```json
{{
    "title": "Brief strategy title (max 10 words)",
    "description": "Full description of the strategy (2-3 sentences)",
    "applicability_conditions": [
        "Condition 1 when this strategy applies",
        "Condition 2...",
        "Condition 3..."
    ],
    "key_steps": [
        "Step 1: Description",
        "Step 2: Description",
        "Step 3: Description"
    ],
    "success_indicators": [
        "Indicator 1 that strategy worked",
        "Indicator 2..."
    ],
    "confidence": 0.0-1.0
}}
```

Only return the JSON, no other text."""

    def __init__(
        self,
        bedrock_client: BedrockClientProtocol,
        embedding_service: Optional[EmbeddingServiceProtocol] = None,
        memory_store: Optional[MemoryStoreProtocol] = None,
        config: Optional[AbstractionConfig] = None,
        evolution_config: Optional[MemoryEvolutionConfig] = None,
    ):
        """Initialize abstraction service.

        Args:
            bedrock_client: Bedrock client for LLM calls
            embedding_service: Optional embedding service for strategy embeddings
            memory_store: Optional memory store for retrieving/storing
            config: Abstraction configuration
            evolution_config: Memory evolution configuration
        """
        self.bedrock = bedrock_client
        self.embedding_service = embedding_service
        self.memory_store = memory_store
        self.config = config or AbstractionConfig()
        self.evolution_config = evolution_config or get_memory_evolution_config()
        self.clustering_service = MemoryClusteringService(config=self.config)

        # Rate limiting
        self._last_abstraction_time = 0.0
        self._abstractions_this_minute = 0
        self._minute_start = 0.0

    async def abstract(
        self,
        action: RefineAction,
        memories: list[dict[str, Any]],
        embeddings: Optional[list[list[float]]] = None,
    ) -> RefineResult:
        """Execute ABSTRACT operation on a set of memories.

        Args:
            action: The refine action specifying the abstraction
            memories: List of memory dictionaries to abstract
            embeddings: Optional pre-computed embeddings

        Returns:
            RefineResult with success status and abstracted strategy
        """
        start_time = time.time()

        # Check feature flag
        if not self.config.enabled:
            return RefineResult(
                success=False,
                operation=RefineOperation.ABSTRACT,
                affected_memory_ids=[],
                error="ABSTRACT operation is disabled",
                latency_ms=(time.time() - start_time) * 1000,
            )

        # Rate limiting
        if not self._check_rate_limit():
            return RefineResult(
                success=False,
                operation=RefineOperation.ABSTRACT,
                affected_memory_ids=[],
                error="Rate limit exceeded for ABSTRACT operations",
                latency_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Validate tenant isolation
            self._validate_tenant_isolation(action, memories)

            # Get or compute embeddings
            if embeddings is None and self.embedding_service:
                contents = [m.get("content", str(m)) for m in memories]
                embeddings = await self.embedding_service.get_embeddings(contents)

            # Cluster memories if we have embeddings
            candidates: list[AbstractionCandidate] = []
            if embeddings:
                candidates = self.clustering_service.cluster_memories(
                    memories, embeddings
                )
            else:
                # Create a single candidate from all memories
                candidates = [
                    AbstractionCandidate(
                        memory_ids=action.target_memory_ids,
                        cluster_id="manual",
                        centroid_embedding=[],
                        coherence_score=0.8,
                        abstraction_potential=0.7,
                        common_themes=self._extract_themes_from_action(action),
                    )
                ]

            # Filter candidates by thresholds
            valid_candidates = [
                c
                for c in candidates
                if c.coherence_score >= self.config.min_coherence_threshold
                and c.abstraction_potential >= self.config.min_abstraction_potential
            ]

            if not valid_candidates:
                return RefineResult(
                    success=False,
                    operation=RefineOperation.ABSTRACT,
                    affected_memory_ids=[],
                    error="No valid abstraction candidates found",
                    latency_ms=(time.time() - start_time) * 1000,
                    metrics={
                        "candidates_found": len(candidates),
                        "valid_candidates": 0,
                    },
                )

            # Extract strategies from candidates
            strategies: list[AbstractedStrategy] = []
            for candidate in valid_candidates:
                # Get memories for this candidate
                candidate_memories = [
                    m
                    for m in memories
                    if m.get("memory_id", m.get("id")) in candidate.memory_ids
                ]

                strategy = await self._extract_strategy(
                    candidate=candidate,
                    memories=candidate_memories,
                    action=action,
                )

                if (
                    strategy
                    and strategy.confidence >= self.config.min_strategy_confidence
                ):
                    # Compute quality metrics
                    strategy.quality_metrics = self._compute_quality_metrics(
                        strategy, candidate_memories
                    )

                    # Store strategy if we have a store
                    if self.memory_store:
                        await self.memory_store.store_strategy(strategy)

                    strategies.append(strategy)

            if not strategies:
                return RefineResult(
                    success=False,
                    operation=RefineOperation.ABSTRACT,
                    affected_memory_ids=action.target_memory_ids,
                    error="Failed to extract valid strategies",
                    latency_ms=(time.time() - start_time) * 1000,
                    metrics={
                        "candidates_processed": len(valid_candidates),
                        "strategies_extracted": 0,
                    },
                )

            latency_ms = (time.time() - start_time) * 1000

            return RefineResult(
                success=True,
                operation=RefineOperation.ABSTRACT,
                affected_memory_ids=action.target_memory_ids,
                rollback_token=self._generate_rollback_token(strategies),
                latency_ms=latency_ms,
                metrics={
                    "strategies_extracted": len(strategies),
                    "candidates_processed": len(valid_candidates),
                    "avg_confidence": sum(s.confidence for s in strategies)
                    / len(strategies),
                    "strategy_ids": [s.strategy_id for s in strategies],
                },
            )

        except TenantIsolationError as e:
            logger.error(f"Tenant isolation violation in ABSTRACT: {e}")
            return RefineResult(
                success=False,
                operation=RefineOperation.ABSTRACT,
                affected_memory_ids=[],
                error=f"Tenant isolation violation: {e}",
                latency_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"ABSTRACT operation failed: {e}", exc_info=True)
            return RefineResult(
                success=False,
                operation=RefineOperation.ABSTRACT,
                affected_memory_ids=[],
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def _extract_strategy(
        self,
        candidate: AbstractionCandidate,
        memories: list[dict[str, Any]],
        action: RefineAction,
    ) -> Optional[AbstractedStrategy]:
        """Extract a strategy from a memory cluster using LLM."""
        # Format memories for the prompt
        experiences = self._format_experiences(memories)

        prompt = self.EXTRACTION_PROMPT_TEMPLATE.format(
            count=len(memories),
            experiences=experiences,
            themes=(
                ", ".join(candidate.common_themes)
                if candidate.common_themes
                else "None detected"
            ),
        )

        try:
            response = self.bedrock.invoke_model(
                prompt=prompt,
                agent=self.AGENT_NAME,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=self.config.llm_max_tokens,
                temperature=self.config.llm_temperature,
            )

            response_text = response.get("response", "")

            # Parse JSON from response
            strategy_data = self._parse_strategy_json(response_text)

            if not strategy_data:
                logger.warning("Failed to parse strategy JSON from LLM response")
                return None

            # Generate strategy embedding if service available
            embedding: list[float] = []
            if self.embedding_service:
                strategy_text = f"{strategy_data.get('title', '')} {strategy_data.get('description', '')}"
                embeddings = await self.embedding_service.get_embeddings(
                    [strategy_text]
                )
                if embeddings:
                    embedding = embeddings[0]

            strategy_id = str(uuid.uuid4())

            return AbstractedStrategy(
                strategy_id=strategy_id,
                title=strategy_data.get("title", "Untitled Strategy"),
                description=strategy_data.get("description", ""),
                source_memory_ids=candidate.memory_ids,
                applicability_conditions=strategy_data.get(
                    "applicability_conditions", []
                ),
                key_steps=strategy_data.get("key_steps", []),
                success_indicators=strategy_data.get("success_indicators", []),
                embedding=embedding,
                confidence=float(strategy_data.get("confidence", 0.7)),
                tenant_id=action.tenant_id,
                security_domain=action.security_domain,
            )

        except Exception as e:
            logger.error(f"Strategy extraction failed: {e}")
            return None

    def _format_experiences(self, memories: list[dict[str, Any]]) -> str:
        """Format memories as experience descriptions for the LLM."""
        experiences = []

        for i, memory in enumerate(memories, 1):
            content = memory.get("content", str(memory))
            outcome = memory.get("outcome", "")
            context = memory.get("context", {})

            exp_text = f"### Experience {i}\n"
            exp_text += (
                f"**Content:** {content[:500]}...\n"
                if len(str(content)) > 500
                else f"**Content:** {content}\n"
            )

            if outcome:
                exp_text += f"**Outcome:** {outcome}\n"

            if context:
                exp_text += f"**Context:** {json.dumps(context, default=str)[:200]}\n"

            experiences.append(exp_text)

        return "\n".join(experiences)

    def _parse_strategy_json(self, response_text: str) -> Optional[dict[str, Any]]:
        """Parse strategy JSON from LLM response."""
        # Try to find JSON block
        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _compute_quality_metrics(
        self,
        strategy: AbstractedStrategy,
        source_memories: list[dict[str, Any]],
    ) -> dict[str, float]:
        """Compute quality metrics for an extracted strategy."""
        # Compression ratio: strategy content size / source content size
        strategy_size = len(strategy.title) + len(strategy.description)
        strategy_size += sum(len(s) for s in strategy.key_steps)
        strategy_size += sum(len(s) for s in strategy.applicability_conditions)

        source_size = sum(len(str(m.get("content", ""))) for m in source_memories)
        source_size = max(source_size, 1)  # Avoid division by zero

        compression_ratio = min(1.0, strategy_size / source_size)

        # Transfer success rate: initialized to 0, updated during usage
        transfer_success_rate = 0.0

        # Reconstruction accuracy: based on theme coverage
        themes_covered = len(
            [
                t
                for t in self._extract_themes_from_strategy(strategy)
                if any(t.lower() in str(m).lower() for m in source_memories)
            ]
        )
        total_themes = max(1, len(self._extract_themes_from_strategy(strategy)))
        reconstruction_accuracy = themes_covered / total_themes

        return {
            "compression_ratio": compression_ratio,
            "transfer_success_rate": transfer_success_rate,
            "reconstruction_accuracy": reconstruction_accuracy,
            "source_memory_count": len(source_memories),
        }

    def _extract_themes_from_strategy(self, strategy: AbstractedStrategy) -> list[str]:
        """Extract key themes from a strategy for quality assessment."""
        themes = []

        # Extract key words from title and description
        text = f"{strategy.title} {strategy.description}"
        words = re.findall(r"\b[a-z]{4,}\b", text.lower())

        # Get unique words that appear meaningful
        seen = set()
        for word in words:
            if word not in seen and word not in {
                "that",
                "this",
                "with",
                "from",
                "have",
                "been",
            }:
                themes.append(word)
                seen.add(word)

        return themes[:10]

    def _extract_themes_from_action(self, action: RefineAction) -> list[str]:
        """Extract themes from action metadata."""
        themes = []

        if action.metadata:
            themes.extend(action.metadata.get("themes", []))
            if "context" in action.metadata:
                themes.append(str(action.metadata["context"]))

        # Extract from reasoning
        if action.reasoning:
            words = re.findall(r"\b[a-z]{4,}\b", action.reasoning.lower())
            themes.extend(words[:5])

        return themes[:8]

    def _validate_tenant_isolation(
        self,
        action: RefineAction,
        memories: list[dict[str, Any]],
    ) -> None:
        """Validate tenant isolation for abstraction."""
        for memory in memories:
            memory_tenant = memory.get("tenant_id")
            memory_domain = memory.get("security_domain")

            if memory_tenant and memory_tenant != action.tenant_id:
                raise TenantIsolationError(
                    f"Memory {memory.get('memory_id')} belongs to tenant "
                    f"{memory_tenant}, not {action.tenant_id}"
                )

            if memory_domain and memory_domain != action.security_domain:
                raise TenantIsolationError(
                    f"Memory {memory.get('memory_id')} belongs to domain "
                    f"{memory_domain}, not {action.security_domain}"
                )

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        current_time = time.time()

        # Reset counter if a minute has passed
        if current_time - self._minute_start > 60:
            self._minute_start = current_time
            self._abstractions_this_minute = 0

        # Check rate limit
        if self._abstractions_this_minute >= self.config.max_abstractions_per_minute:
            return False

        # Check cooldown
        if current_time - self._last_abstraction_time < self.config.cooldown_seconds:
            return False

        self._abstractions_this_minute += 1
        self._last_abstraction_time = current_time
        return True

    def _generate_rollback_token(self, strategies: list[AbstractedStrategy]) -> str:
        """Generate a rollback token for the abstraction operation."""
        strategy_ids = [s.strategy_id for s in strategies]
        token_data = json.dumps(
            {"strategy_ids": strategy_ids, "timestamp": time.time()}
        )
        token_hash = hashlib.sha256(token_data.encode()).hexdigest()[:16]
        return f"abstract:{token_hash}"


# =============================================================================
# EXCEPTIONS
# =============================================================================


class TenantIsolationError(Exception):
    """Raised when tenant isolation is violated."""


class AbstractionError(Exception):
    """Raised when abstraction fails."""


# =============================================================================
# SINGLETON MANAGEMENT
# =============================================================================

_abstraction_service: Optional[AbstractionService] = None
_clustering_service: Optional[MemoryClusteringService] = None


def get_abstraction_service(
    bedrock_client: Optional[BedrockClientProtocol] = None,
    embedding_service: Optional[EmbeddingServiceProtocol] = None,
    memory_store: Optional[MemoryStoreProtocol] = None,
    config: Optional[AbstractionConfig] = None,
) -> AbstractionService:
    """Get or create the singleton AbstractionService instance."""
    global _abstraction_service
    if _abstraction_service is None:
        if bedrock_client is None:
            raise ValueError("bedrock_client is required for initial creation")
        _abstraction_service = AbstractionService(
            bedrock_client=bedrock_client,
            embedding_service=embedding_service,
            memory_store=memory_store,
            config=config,
        )
    return _abstraction_service


def reset_abstraction_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _abstraction_service
    _abstraction_service = None


def get_clustering_service(
    config: Optional[AbstractionConfig] = None,
) -> MemoryClusteringService:
    """Get or create the singleton MemoryClusteringService instance."""
    global _clustering_service
    if _clustering_service is None:
        _clustering_service = MemoryClusteringService(config=config)
    return _clustering_service


def reset_clustering_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _clustering_service
    _clustering_service = None
