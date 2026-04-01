"""
Tests for ADR-080 Phase 3: ABSTRACT Operation

Tests the LLM-based strategy extraction from memory clusters,
including clustering, abstraction, and quality metrics.
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from src.services.memory_evolution.abstract_operation import (
    AbstractionConfig,
    AbstractionService,
    MemoryClusteringService,
    get_abstraction_service,
    get_clustering_service,
    reset_abstraction_service,
    reset_clustering_service,
)
from src.services.memory_evolution.contracts import (
    AbstractedStrategy,
    AbstractionCandidate,
    RefineAction,
    RefineOperation,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test."""
    reset_abstraction_service()
    reset_clustering_service()
    yield
    reset_abstraction_service()
    reset_clustering_service()


@pytest.fixture
def mock_bedrock_client():
    """Create a mock Bedrock client."""
    client = MagicMock()
    client.invoke_model = MagicMock(
        return_value={
            "response": json.dumps(
                {
                    "title": "Test Strategy",
                    "description": "A test strategy for debugging patterns",
                    "applicability_conditions": [
                        "When encountering similar bugs",
                        "When debugging in Python",
                    ],
                    "key_steps": [
                        "Step 1: Identify the error pattern",
                        "Step 2: Apply the fix",
                        "Step 3: Verify the solution",
                    ],
                    "success_indicators": [
                        "Tests pass",
                        "No regression errors",
                    ],
                    "confidence": 0.85,
                }
            ),
            "input_tokens": 500,
            "output_tokens": 200,
        }
    )
    return client


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = AsyncMock()
    # Return embeddings that cluster well
    service.get_embeddings = AsyncMock(
        return_value=[[0.1, 0.2, 0.3, 0.4] for _ in range(5)]
    )
    return service


@pytest.fixture
def mock_memory_store():
    """Create a mock memory store."""
    store = AsyncMock()
    store.get_memories = AsyncMock(return_value=[])
    store.store_strategy = AsyncMock(return_value="strategy-123")
    return store


@pytest.fixture
def sample_memories():
    """Create sample memories for testing."""
    return [
        {
            "memory_id": "mem-1",
            "content": "Fixed null pointer exception by adding validation",
            "outcome": "success",
            "tags": ["debugging", "python", "validation"],
            "tenant_id": "tenant-1",
            "security_domain": "development",
        },
        {
            "memory_id": "mem-2",
            "content": "Resolved type error by checking input types",
            "outcome": "success",
            "tags": ["debugging", "python", "type-safety"],
            "tenant_id": "tenant-1",
            "security_domain": "development",
        },
        {
            "memory_id": "mem-3",
            "content": "Fixed attribute error with hasattr check",
            "outcome": "success",
            "tags": ["debugging", "python", "validation"],
            "tenant_id": "tenant-1",
            "security_domain": "development",
        },
    ]


@pytest.fixture
def sample_embeddings():
    """Create sample embeddings for testing."""
    # Create embeddings that form a clear cluster
    np.random.seed(42)
    base = np.array([0.5, 0.5, 0.5, 0.5])
    noise = np.random.normal(0, 0.05, (3, 4))
    return (base + noise).tolist()


@pytest.fixture
def sample_action():
    """Create a sample refine action."""
    return RefineAction(
        operation=RefineOperation.ABSTRACT,
        target_memory_ids=["mem-1", "mem-2", "mem-3"],
        reasoning="Extract debugging strategy from successful fixes",
        confidence=0.8,
        tenant_id="tenant-1",
        security_domain="development",
        agent_id="agent-1",
    )


@pytest.fixture
def abstraction_config():
    """Create test abstraction config."""
    return AbstractionConfig(
        min_cluster_size=2,
        min_coherence_threshold=0.5,
        min_abstraction_potential=0.4,
        min_strategy_confidence=0.5,
        max_abstractions_per_minute=100,  # High limit for testing
        cooldown_seconds=0.0,  # No cooldown for testing
        enabled=True,
    )


# =============================================================================
# CONTRACT TESTS
# =============================================================================


class TestAbstractionCandidate:
    """Tests for AbstractionCandidate dataclass."""

    def test_valid_candidate(self):
        """Test creating a valid abstraction candidate."""
        candidate = AbstractionCandidate(
            memory_ids=["mem-1", "mem-2"],
            cluster_id="cluster-1",
            centroid_embedding=[0.1, 0.2, 0.3],
            coherence_score=0.8,
            abstraction_potential=0.7,
            common_themes=["debugging", "python"],
        )

        assert candidate.memory_ids == ["mem-1", "mem-2"]
        assert candidate.coherence_score == 0.8
        assert candidate.abstraction_potential == 0.7

    def test_invalid_coherence_score(self):
        """Test that invalid coherence scores are rejected."""
        with pytest.raises(ValueError, match="Coherence score"):
            AbstractionCandidate(
                memory_ids=["mem-1", "mem-2"],
                cluster_id="cluster-1",
                centroid_embedding=[0.1, 0.2],
                coherence_score=1.5,  # Invalid
                abstraction_potential=0.7,
                common_themes=[],
            )

    def test_invalid_abstraction_potential(self):
        """Test that invalid abstraction potential is rejected."""
        with pytest.raises(ValueError, match="Abstraction potential"):
            AbstractionCandidate(
                memory_ids=["mem-1", "mem-2"],
                cluster_id="cluster-1",
                centroid_embedding=[0.1, 0.2],
                coherence_score=0.8,
                abstraction_potential=-0.1,  # Invalid
                common_themes=[],
            )

    def test_too_few_memories(self):
        """Test that single memory is rejected."""
        with pytest.raises(ValueError, match="At least 2 memories"):
            AbstractionCandidate(
                memory_ids=["mem-1"],  # Only one
                cluster_id="cluster-1",
                centroid_embedding=[0.1, 0.2],
                coherence_score=0.8,
                abstraction_potential=0.7,
                common_themes=[],
            )

    def test_to_dict(self):
        """Test serialization to dictionary."""
        candidate = AbstractionCandidate(
            memory_ids=["mem-1", "mem-2"],
            cluster_id="cluster-1",
            centroid_embedding=[0.1, 0.2],
            coherence_score=0.8,
            abstraction_potential=0.7,
            common_themes=["theme1"],
            metadata={"key": "value"},
        )

        data = candidate.to_dict()

        assert data["memory_ids"] == ["mem-1", "mem-2"]
        assert data["cluster_id"] == "cluster-1"
        assert data["coherence_score"] == 0.8
        assert data["metadata"]["key"] == "value"


class TestAbstractedStrategy:
    """Tests for AbstractedStrategy dataclass."""

    def test_valid_strategy(self):
        """Test creating a valid abstracted strategy."""
        strategy = AbstractedStrategy(
            strategy_id="strat-1",
            title="Debug Python Errors",
            description="A strategy for debugging Python errors",
            source_memory_ids=["mem-1", "mem-2"],
            applicability_conditions=["When debugging Python"],
            key_steps=["Step 1", "Step 2"],
            success_indicators=["Tests pass"],
            embedding=[0.1, 0.2, 0.3],
            confidence=0.85,
            tenant_id="tenant-1",
            security_domain="development",
        )

        assert strategy.strategy_id == "strat-1"
        assert strategy.confidence == 0.85
        assert len(strategy.key_steps) == 2

    def test_invalid_confidence(self):
        """Test that invalid confidence is rejected."""
        with pytest.raises(ValueError, match="Confidence"):
            AbstractedStrategy(
                strategy_id="strat-1",
                title="Test",
                description="Test",
                source_memory_ids=["mem-1"],
                applicability_conditions=[],
                key_steps=[],
                success_indicators=[],
                embedding=[],
                confidence=1.5,  # Invalid
                tenant_id="tenant-1",
                security_domain="dev",
            )

    def test_to_dict(self):
        """Test serialization to dictionary."""
        strategy = AbstractedStrategy(
            strategy_id="strat-1",
            title="Test Strategy",
            description="A test",
            source_memory_ids=["mem-1"],
            applicability_conditions=["cond1"],
            key_steps=["step1"],
            success_indicators=["ind1"],
            embedding=[0.1],
            confidence=0.8,
            tenant_id="tenant-1",
            security_domain="dev",
            quality_metrics={"compression_ratio": 0.5},
        )

        data = strategy.to_dict()

        assert data["strategy_id"] == "strat-1"
        assert data["quality_metrics"]["compression_ratio"] == 0.5
        assert "created_at" in data

    def test_to_dynamo_item(self):
        """Test conversion to DynamoDB item format."""
        strategy = AbstractedStrategy(
            strategy_id="strat-1",
            title="Test",
            description="Test",
            source_memory_ids=["mem-1"],
            applicability_conditions=[],
            key_steps=[],
            success_indicators=[],
            embedding=[],
            confidence=0.8,
            tenant_id="tenant-1",
            security_domain="development",
        )

        item = strategy.to_dynamo_item()

        assert item["pk"] == "strategy#tenant-1"
        assert item["sk"] == "development#strat-1"
        assert item["gsi1pk"] == "domain#development"


# =============================================================================
# CLUSTERING SERVICE TESTS
# =============================================================================


class TestMemoryClusteringService:
    """Tests for MemoryClusteringService."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        service = MemoryClusteringService()
        assert service.config.min_cluster_size == 3

    def test_init_custom_config(self, abstraction_config):
        """Test initialization with custom config."""
        service = MemoryClusteringService(config=abstraction_config)
        assert service.config.min_cluster_size == 2

    def test_cluster_memories_too_few(self, abstraction_config):
        """Test clustering with too few memories."""
        service = MemoryClusteringService(config=abstraction_config)

        memories = [{"memory_id": "mem-1", "content": "test"}]
        embeddings = [[0.1, 0.2, 0.3]]

        candidates = service.cluster_memories(memories, embeddings)

        assert candidates == []

    def test_cluster_memories_fallback(self, sample_memories, abstraction_config):
        """Test fallback clustering without HDBSCAN."""
        service = MemoryClusteringService(config=abstraction_config)
        service._hdbscan_available = False

        # Create similar embeddings that should cluster together
        embeddings = [
            [0.5, 0.5, 0.5, 0.5],
            [0.51, 0.49, 0.52, 0.48],
            [0.49, 0.51, 0.48, 0.52],
        ]

        candidates = service.cluster_memories(sample_memories, embeddings)

        # Should create at least one candidate with similar embeddings
        assert len(candidates) >= 1

    @pytest.mark.skipif(
        not MemoryClusteringService()._check_hdbscan(), reason="HDBSCAN not installed"
    )
    def test_cluster_memories_with_hdbscan(self, sample_memories, abstraction_config):
        """Test clustering with HDBSCAN."""
        service = MemoryClusteringService(config=abstraction_config)

        # Create embeddings that form a clear cluster
        embeddings = [
            [0.5, 0.5, 0.5, 0.5],
            [0.51, 0.49, 0.52, 0.48],
            [0.49, 0.51, 0.48, 0.52],
        ]

        candidates = service.cluster_memories(sample_memories, embeddings)

        # HDBSCAN may or may not form clusters depending on parameters
        assert isinstance(candidates, list)

    def test_compute_coherence_high(self, abstraction_config):
        """Test coherence computation for similar embeddings."""
        service = MemoryClusteringService(config=abstraction_config)

        # Very similar embeddings should have high coherence
        embeddings = [
            [0.5, 0.5, 0.5, 0.5],
            [0.5, 0.5, 0.5, 0.5],
            [0.5, 0.5, 0.5, 0.5],
        ]

        coherence = service._compute_coherence(embeddings)

        assert coherence > 0.95

    def test_compute_coherence_low(self, abstraction_config):
        """Test coherence computation for dissimilar embeddings."""
        service = MemoryClusteringService(config=abstraction_config)

        # Very different embeddings should have lower coherence
        embeddings = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ]

        coherence = service._compute_coherence(embeddings)

        assert coherence < 0.5

    def test_compute_diversity(self, abstraction_config):
        """Test diversity computation."""
        service = MemoryClusteringService(config=abstraction_config)

        # Spread-out embeddings should have higher diversity
        embeddings = [
            [0.0, 0.0, 0.0, 0.0],
            [1.0, 1.0, 1.0, 1.0],
            [0.5, 0.5, 0.5, 0.5],
        ]

        diversity = service._compute_diversity(embeddings)

        assert 0.0 <= diversity <= 1.0

    def test_extract_themes(self, abstraction_config, sample_memories):
        """Test theme extraction from memories."""
        service = MemoryClusteringService(config=abstraction_config)

        themes = service._extract_themes(sample_memories)

        assert "debugging" in themes  # Common tag
        assert len(themes) <= 8  # Limited to 8

    def test_singleton_management(self, abstraction_config):
        """Test singleton getter and reset."""
        service1 = get_clustering_service(config=abstraction_config)
        service2 = get_clustering_service()

        assert service1 is service2

        reset_clustering_service()
        service3 = get_clustering_service(config=abstraction_config)

        assert service1 is not service3


# =============================================================================
# ABSTRACTION SERVICE TESTS
# =============================================================================


class TestAbstractionService:
    """Tests for AbstractionService."""

    def test_init(self, mock_bedrock_client, abstraction_config):
        """Test service initialization."""
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=abstraction_config,
        )

        assert service.bedrock is mock_bedrock_client
        assert service.config.min_cluster_size == 2

    @pytest.mark.asyncio
    async def test_abstract_disabled(
        self, mock_bedrock_client, sample_memories, sample_action
    ):
        """Test abstraction when feature is disabled."""
        config = AbstractionConfig(enabled=False)
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=config,
        )

        result = await service.abstract(sample_action, sample_memories)

        assert not result.success
        assert "disabled" in result.error.lower()

    @pytest.mark.asyncio
    async def test_abstract_rate_limited(
        self, mock_bedrock_client, sample_memories, sample_action
    ):
        """Test abstraction with rate limiting."""
        config = AbstractionConfig(
            max_abstractions_per_minute=1,
            cooldown_seconds=10.0,
            enabled=True,
        )
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=config,
        )

        # First call should succeed
        service._last_abstraction_time = 0
        service._abstractions_this_minute = 0
        service._minute_start = time.time()

        # Exhaust rate limit
        service._abstractions_this_minute = 1

        result = await service.abstract(sample_action, sample_memories)

        assert not result.success
        assert "rate limit" in result.error.lower()

    @pytest.mark.asyncio
    async def test_abstract_tenant_isolation_violation(
        self, mock_bedrock_client, abstraction_config, sample_action
    ):
        """Test tenant isolation enforcement."""
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=abstraction_config,
        )

        # Create memories with different tenant
        bad_memories = [
            {
                "memory_id": "mem-1",
                "content": "test",
                "tenant_id": "different-tenant",  # Different tenant
                "security_domain": "development",
            },
            {
                "memory_id": "mem-2",
                "content": "test2",
                "tenant_id": "tenant-1",
                "security_domain": "development",
            },
        ]

        result = await service.abstract(sample_action, bad_memories)

        assert not result.success
        assert "isolation" in result.error.lower()

    @pytest.mark.asyncio
    async def test_abstract_security_domain_violation(
        self, mock_bedrock_client, abstraction_config, sample_action
    ):
        """Test security domain enforcement."""
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=abstraction_config,
        )

        # Create memories with different security domain
        bad_memories = [
            {
                "memory_id": "mem-1",
                "content": "test",
                "tenant_id": "tenant-1",
                "security_domain": "production",  # Different domain
            },
            {
                "memory_id": "mem-2",
                "content": "test2",
                "tenant_id": "tenant-1",
                "security_domain": "development",
            },
        ]

        result = await service.abstract(sample_action, bad_memories)

        assert not result.success
        assert "isolation" in result.error.lower()

    @pytest.mark.asyncio
    async def test_abstract_successful(
        self,
        mock_bedrock_client,
        mock_embedding_service,
        abstraction_config,
        sample_memories,
        sample_action,
    ):
        """Test successful abstraction operation."""
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            embedding_service=mock_embedding_service,
            config=abstraction_config,
        )

        result = await service.abstract(sample_action, sample_memories)

        assert result.success
        assert result.operation == RefineOperation.ABSTRACT
        assert result.latency_ms > 0
        assert "strategies_extracted" in result.metrics

    @pytest.mark.asyncio
    async def test_abstract_with_precomputed_embeddings(
        self,
        mock_bedrock_client,
        abstraction_config,
        sample_memories,
        sample_embeddings,
        sample_action,
    ):
        """Test abstraction with pre-computed embeddings."""
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=abstraction_config,
        )

        result = await service.abstract(
            sample_action, sample_memories, embeddings=sample_embeddings
        )

        assert result.success
        assert result.operation == RefineOperation.ABSTRACT

    @pytest.mark.asyncio
    async def test_abstract_without_embeddings(
        self,
        mock_bedrock_client,
        abstraction_config,
        sample_memories,
        sample_action,
    ):
        """Test abstraction without embedding service."""
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=abstraction_config,
        )

        result = await service.abstract(sample_action, sample_memories)

        # Should create a manual candidate
        assert result.success

    @pytest.mark.asyncio
    async def test_abstract_llm_returns_invalid_json(
        self,
        mock_bedrock_client,
        abstraction_config,
        sample_memories,
        sample_action,
    ):
        """Test handling of invalid LLM response."""
        mock_bedrock_client.invoke_model.return_value = {
            "response": "Not valid JSON",
            "input_tokens": 100,
            "output_tokens": 50,
        }

        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=abstraction_config,
        )

        result = await service.abstract(sample_action, sample_memories)

        # Should handle gracefully
        assert not result.success
        assert "strategies" in result.error.lower() or "extract" in result.error.lower()

    @pytest.mark.asyncio
    async def test_abstract_low_confidence_strategy(
        self,
        mock_bedrock_client,
        abstraction_config,
        sample_memories,
        sample_action,
    ):
        """Test filtering of low-confidence strategies."""
        mock_bedrock_client.invoke_model.return_value = {
            "response": json.dumps(
                {
                    "title": "Low Confidence Strategy",
                    "description": "Test",
                    "applicability_conditions": [],
                    "key_steps": [],
                    "success_indicators": [],
                    "confidence": 0.2,  # Below threshold
                }
            ),
            "input_tokens": 100,
            "output_tokens": 50,
        }

        config = AbstractionConfig(
            min_strategy_confidence=0.5,  # Strategy confidence too low
            min_cluster_size=2,
            min_coherence_threshold=0.3,
            min_abstraction_potential=0.3,
            cooldown_seconds=0.0,
            enabled=True,
        )

        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=config,
        )

        result = await service.abstract(sample_action, sample_memories)

        # Low confidence strategy should be filtered
        assert not result.success

    @pytest.mark.asyncio
    async def test_abstract_stores_strategy(
        self,
        mock_bedrock_client,
        mock_memory_store,
        abstraction_config,
        sample_memories,
        sample_action,
    ):
        """Test that strategies are stored when store is provided."""
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            memory_store=mock_memory_store,
            config=abstraction_config,
        )

        result = await service.abstract(sample_action, sample_memories)

        if result.success:
            # Store should be called
            mock_memory_store.store_strategy.assert_called()

    def test_format_experiences(self, mock_bedrock_client, abstraction_config):
        """Test experience formatting for LLM."""
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=abstraction_config,
        )

        memories = [
            {
                "content": "Fixed a bug",
                "outcome": "success",
                "context": {"file": "test.py"},
            }
        ]

        formatted = service._format_experiences(memories)

        assert "Experience 1" in formatted
        assert "Fixed a bug" in formatted
        assert "success" in formatted

    def test_parse_strategy_json_with_code_block(
        self, mock_bedrock_client, abstraction_config
    ):
        """Test parsing JSON from code block."""
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=abstraction_config,
        )

        response = """Here is the strategy:
```json
{"title": "Test", "confidence": 0.8}
```
"""

        result = service._parse_strategy_json(response)

        assert result["title"] == "Test"
        assert result["confidence"] == 0.8

    def test_parse_strategy_json_raw(self, mock_bedrock_client, abstraction_config):
        """Test parsing raw JSON."""
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=abstraction_config,
        )

        response = '{"title": "Test", "confidence": 0.8}'

        result = service._parse_strategy_json(response)

        assert result["title"] == "Test"

    def test_compute_quality_metrics(self, mock_bedrock_client, abstraction_config):
        """Test quality metrics computation."""
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=abstraction_config,
        )

        strategy = AbstractedStrategy(
            strategy_id="strat-1",
            title="Debug Python",
            description="Strategy for debugging",
            source_memory_ids=["mem-1", "mem-2"],
            applicability_conditions=["When debugging"],
            key_steps=["Step 1", "Step 2"],
            success_indicators=["Tests pass"],
            embedding=[],
            confidence=0.8,
            tenant_id="tenant-1",
            security_domain="dev",
        )

        source_memories = [
            {"content": "Fixed debug issue in Python"},
            {"content": "Resolved Python type error"},
        ]

        metrics = service._compute_quality_metrics(strategy, source_memories)

        assert "compression_ratio" in metrics
        assert "transfer_success_rate" in metrics
        assert "reconstruction_accuracy" in metrics
        assert metrics["source_memory_count"] == 2

    def test_generate_rollback_token(self, mock_bedrock_client, abstraction_config):
        """Test rollback token generation."""
        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=abstraction_config,
        )

        strategies = [
            AbstractedStrategy(
                strategy_id="strat-1",
                title="Test",
                description="Test",
                source_memory_ids=[],
                applicability_conditions=[],
                key_steps=[],
                success_indicators=[],
                embedding=[],
                confidence=0.8,
                tenant_id="t1",
                security_domain="dev",
            )
        ]

        token = service._generate_rollback_token(strategies)

        assert token.startswith("abstract:")
        assert len(token) > 10

    def test_singleton_management(self, mock_bedrock_client, abstraction_config):
        """Test singleton getter and reset."""
        service1 = get_abstraction_service(
            bedrock_client=mock_bedrock_client,
            config=abstraction_config,
        )
        service2 = get_abstraction_service()

        assert service1 is service2

        reset_abstraction_service()

        with pytest.raises(ValueError, match="bedrock_client is required"):
            get_abstraction_service()

    def test_singleton_requires_client(self):
        """Test that singleton creation requires bedrock client."""
        reset_abstraction_service()

        with pytest.raises(ValueError, match="bedrock_client is required"):
            get_abstraction_service()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestAbstractionIntegration:
    """Integration tests for the abstraction pipeline."""

    @pytest.mark.asyncio
    async def test_full_abstraction_pipeline(
        self,
        mock_bedrock_client,
        mock_embedding_service,
        mock_memory_store,
        abstraction_config,
    ):
        """Test the full abstraction pipeline from memories to strategy."""
        # Create memories
        memories = [
            {
                "memory_id": f"mem-{i}",
                "content": f"Debugging experience {i}",
                "outcome": "success",
                "tags": ["debugging", "python"],
                "tenant_id": "tenant-1",
                "security_domain": "development",
            }
            for i in range(5)
        ]

        action = RefineAction(
            operation=RefineOperation.ABSTRACT,
            target_memory_ids=[m["memory_id"] for m in memories],
            reasoning="Extract debugging patterns",
            confidence=0.9,
            tenant_id="tenant-1",
            security_domain="development",
        )

        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            embedding_service=mock_embedding_service,
            memory_store=mock_memory_store,
            config=abstraction_config,
        )

        result = await service.abstract(action, memories)

        # Verify full pipeline executed
        assert result.success
        assert result.rollback_token is not None
        assert result.metrics.get("strategies_extracted", 0) >= 1

    @pytest.mark.asyncio
    async def test_abstraction_with_no_valid_candidates(
        self, mock_bedrock_client, abstraction_config
    ):
        """Test handling when no valid candidates are found."""
        config = AbstractionConfig(
            min_coherence_threshold=0.99,  # Very high threshold
            min_abstraction_potential=0.99,
            min_cluster_size=2,
            cooldown_seconds=0.0,
            enabled=True,
        )

        service = AbstractionService(
            bedrock_client=mock_bedrock_client,
            config=config,
        )

        # Create dissimilar memories that won't cluster well
        memories = [
            {
                "memory_id": "mem-1",
                "content": "Python debugging",
                "tenant_id": "tenant-1",
                "security_domain": "dev",
            },
            {
                "memory_id": "mem-2",
                "content": "Java compilation",
                "tenant_id": "tenant-1",
                "security_domain": "dev",
            },
        ]

        action = RefineAction(
            operation=RefineOperation.ABSTRACT,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.8,
            tenant_id="tenant-1",
            security_domain="dev",
        )

        # Create very different embeddings
        embeddings = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]

        result = await service.abstract(action, memories, embeddings=embeddings)

        # Should fail due to low coherence
        assert not result.success
        assert (
            "no valid" in result.error.lower() or "candidates" in result.error.lower()
        )
