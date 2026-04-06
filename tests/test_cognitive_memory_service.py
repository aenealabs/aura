"""
Unit tests for cognitive_memory_service.py

Tests the core cognitive memory components:
- Data classes and enums
- WorkingMemory operations
- ConfidenceEstimator
- StrategySelector
- PatternCompletionRetriever
- ConsolidationPipeline
- CriticAgent
- DualAgentOrchestrator
- AccuracyMonitor
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.services.cognitive_memory_service import (  # Enums; Constants; Data classes; Classes
    EPISODIC_TTL_DAYS,
    MIN_EPISODES_FOR_PATTERN,
    PATTERN_VALIDATION_THRESHOLD,
    WORKING_MEMORY_CAPACITY,
    AccuracyMonitor,
    AgentMode,
    CognitiveMemoryService,
    ConfidenceEstimate,
    ConfidenceEstimator,
    ConsolidationPipeline,
    CriticAgent,
    CriticChallenge,
    CriticEvaluation,
    DualAgentOrchestrator,
    EpisodicMemory,
    MemoryItem,
    MemoryType,
    OutcomeStatus,
    PatternCompletionRetriever,
    ProceduralMemory,
    ProceduralStep,
    RecommendedAction,
    RetrievalCue,
    RetrievedMemory,
    SemanticMemory,
    SemanticType,
    Severity,
    Strategy,
    StrategySelector,
    StrategyType,
    WorkingMemory,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_episodic_store():
    """Create mock episodic store."""
    store = AsyncMock()
    store.put = AsyncMock()
    store.get = AsyncMock(return_value=None)
    store.query_by_domain = AsyncMock(return_value=[])
    store.query_unconsolidated = AsyncMock(return_value=[])
    store.mark_consolidated = AsyncMock()
    store.delete = AsyncMock()
    return store


@pytest.fixture
def mock_semantic_store():
    """Create mock semantic store."""
    store = AsyncMock()
    store.put = AsyncMock()
    store.get = AsyncMock(return_value=None)
    store.query_by_domain = AsyncMock(return_value=[])
    store.vector_search = AsyncMock(return_value=[])
    store.update_confidence = AsyncMock()
    return store


@pytest.fixture
def mock_procedural_store():
    """Create mock procedural store."""
    store = AsyncMock()
    store.put = AsyncMock()
    store.get = AsyncMock(return_value=None)
    store.query_by_domain = AsyncMock(return_value=[])
    store.query_by_trigger = AsyncMock(return_value=[])
    store.update_metrics = AsyncMock()
    return store


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    service = AsyncMock()
    service.embed = AsyncMock(return_value=[0.1] * 1536)
    service.embed_batch = AsyncMock(return_value=[[0.1] * 1536])
    return service


@pytest.fixture
def sample_episodic_memory():
    """Create sample episodic memory."""
    return EpisodicMemory(
        episode_id="ep-test-001",
        timestamp=datetime.now(),
        domain="CICD",
        task_description="Deploy stack",
        input_context={"test": True},
        decision="Use deploy command",
        reasoning="Standard pattern",
        confidence_at_decision=0.85,
        outcome=OutcomeStatus.SUCCESS,
        outcome_details="Completed",
        keywords=["deploy", "stack"],
        embedding=[0.1] * 10,
    )


@pytest.fixture
def sample_semantic_memory():
    """Create sample semantic memory."""
    return SemanticMemory(
        memory_id="sem-test-001",
        memory_type=SemanticType.GUARDRAIL,
        domain="CICD",
        title="Test Guardrail",
        content="Test content",
        confidence=0.9,
        evidence_count=5,
        keywords=["test", "guardrail"],
        embedding=[0.1] * 10,
        severity=Severity.HIGH,
    )


@pytest.fixture
def sample_procedural_memory():
    """Create sample procedural memory."""
    return ProceduralMemory(
        procedure_id="proc-test-001",
        name="Test Procedure",
        domain="CICD",
        goal_description="Test goal",
        steps=[
            ProceduralStep(
                step_id="step-1",
                order=1,
                action="First action",
                tool="Bash",
            )
        ],
        trigger_conditions=["deploy", "stack"],
        success_rate=0.9,
        execution_count=10,
        required_guardrails=["GR-001"],
    )


@pytest.fixture
def sample_retrieved_memory(sample_semantic_memory):
    """Create sample retrieved memory."""
    return RetrievedMemory(
        memory_id="sem-test-001",
        memory_type=MemoryType.SEMANTIC,
        full_content=sample_semantic_memory,
        keyword_score=0.8,
        vector_similarity=0.7,
        combined_score=0.75,
        completion_confidence=0.8,
    )


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestEnums:
    """Test enum definitions."""

    def test_memory_type_values(self):
        """Test MemoryType enum values."""
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.PROCEDURAL.value == "procedural"

    def test_semantic_type_values(self):
        """Test SemanticType enum values."""
        assert SemanticType.GUARDRAIL.value == "guardrail"
        assert SemanticType.PATTERN.value == "pattern"
        assert SemanticType.SCHEMA.value == "schema"
        assert SemanticType.CONCEPT.value == "concept"
        assert SemanticType.ANTI_PATTERN.value == "anti_pattern"

    def test_severity_values(self):
        """Test Severity enum values."""
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"

    def test_outcome_status_values(self):
        """Test OutcomeStatus enum values."""
        assert OutcomeStatus.SUCCESS.value == "success"
        assert OutcomeStatus.FAILURE.value == "failure"
        assert OutcomeStatus.PARTIAL.value == "partial"
        assert OutcomeStatus.ESCALATED.value == "escalated"

    def test_strategy_type_values(self):
        """Test StrategyType enum values."""
        assert StrategyType.PROCEDURAL_EXECUTION.value == "procedural_execution"
        assert StrategyType.SCHEMA_GUIDED.value == "schema_guided"
        assert StrategyType.ACTIVE_LEARNING.value == "active_learning"
        assert StrategyType.CAUTIOUS_EXPLORATION.value == "cautious_exploration"
        assert StrategyType.HUMAN_GUIDANCE.value == "human_guidance"

    def test_recommended_action_values(self):
        """Test RecommendedAction enum values."""
        assert RecommendedAction.PROCEED_AUTONOMOUS.value == "proceed_autonomous"
        assert RecommendedAction.PROCEED_WITH_LOGGING.value == "proceed_with_logging"
        assert RecommendedAction.REQUEST_REVIEW.value == "request_review"
        assert RecommendedAction.ESCALATE_TO_HUMAN.value == "escalate_to_human"

    def test_agent_mode_values(self):
        """Test AgentMode enum values."""
        assert AgentMode.SINGLE.value == "single"
        assert AgentMode.DUAL.value == "dual"
        assert AgentMode.AUTO.value == "auto"

    def test_critic_challenge_values(self):
        """Test CriticChallenge enum values."""
        assert CriticChallenge.INSUFFICIENT_CONTEXT.value == "insufficient_context"
        assert CriticChallenge.DOMAIN_MISMATCH.value == "domain_mismatch"
        assert CriticChallenge.LOGICAL_INCONSISTENCY.value == "logical_inconsistency"
        assert CriticChallenge.MISSING_INFORMATION.value == "missing_information"
        assert CriticChallenge.OVERCONFIDENT_LEAP.value == "overconfident_leap"
        assert CriticChallenge.PATTERN_MISMATCH.value == "pattern_mismatch"
        assert CriticChallenge.UNEXPLAINED_REASONING.value == "unexplained_reasoning"


# =============================================================================
# CONSTANTS TESTS
# =============================================================================


class TestConstants:
    """Test module constants."""

    def test_working_memory_capacity(self):
        """Test working memory capacity constant."""
        assert WORKING_MEMORY_CAPACITY == 7

    def test_min_episodes_for_pattern(self):
        """Test minimum episodes for pattern constant."""
        assert MIN_EPISODES_FOR_PATTERN == 3

    def test_pattern_validation_threshold(self):
        """Test pattern validation threshold constant."""
        assert PATTERN_VALIDATION_THRESHOLD == 0.85

    def test_episodic_ttl_days(self):
        """Test episodic TTL days constant."""
        assert EPISODIC_TTL_DAYS == 30


# =============================================================================
# DATA CLASS TESTS
# =============================================================================


class TestEpisodicMemory:
    """Test EpisodicMemory dataclass."""

    def test_basic_creation(self, sample_episodic_memory):
        """Test basic episodic memory creation."""
        assert sample_episodic_memory.episode_id == "ep-test-001"
        assert sample_episodic_memory.domain == "CICD"
        assert sample_episodic_memory.outcome == OutcomeStatus.SUCCESS

    def test_default_ttl_success(self):
        """Test TTL is set for successful episodes."""
        episode = EpisodicMemory(
            episode_id="ep-001",
            timestamp=datetime.now(),
            domain="TEST",
            task_description="Test",
            input_context={},
            outcome=OutcomeStatus.SUCCESS,
        )
        assert episode.ttl is not None
        # TTL should be ~30 days for success
        expected_ttl = datetime.now() + timedelta(days=EPISODIC_TTL_DAYS)
        assert abs(episode.ttl - expected_ttl.timestamp()) < 60  # Within 1 minute

    def test_extended_ttl_failure(self):
        """Test TTL is extended for failed episodes."""
        episode = EpisodicMemory(
            episode_id="ep-001",
            timestamp=datetime.now(),
            domain="TEST",
            task_description="Test",
            input_context={},
            outcome=OutcomeStatus.FAILURE,
        )
        assert episode.ttl is not None
        # TTL should be ~60 days for failure
        expected_ttl = datetime.now() + timedelta(days=EPISODIC_TTL_DAYS * 2)
        assert abs(episode.ttl - expected_ttl.timestamp()) < 60

    def test_default_values(self):
        """Test default values are applied."""
        episode = EpisodicMemory(
            episode_id="ep-001",
            timestamp=datetime.now(),
            domain="TEST",
            task_description="Test",
            input_context={},
        )
        assert episode.decision == ""
        assert episode.reasoning == ""
        assert episode.confidence_at_decision == 0.5
        assert episode.consolidated is False
        assert episode.embedding == []
        assert episode.keywords == []


class TestSemanticMemory:
    """Test SemanticMemory dataclass."""

    def test_basic_creation(self, sample_semantic_memory):
        """Test basic semantic memory creation."""
        assert sample_semantic_memory.memory_id == "sem-test-001"
        assert sample_semantic_memory.memory_type == SemanticType.GUARDRAIL
        assert sample_semantic_memory.domain == "CICD"

    def test_default_values(self):
        """Test default values are applied."""
        memory = SemanticMemory(
            memory_id="sem-001",
            memory_type=SemanticType.PATTERN,
            domain="TEST",
            title="Test",
            content="Content",
        )
        assert memory.confidence == 0.5
        assert memory.evidence_count == 0
        assert memory.contradiction_count == 0
        assert memory.severity == Severity.MEDIUM
        assert memory.status == "ACTIVE"
        assert memory.related_memories == []
        assert memory.derived_from == []
        assert memory.preconditions == []


class TestProceduralStep:
    """Test ProceduralStep dataclass."""

    def test_basic_creation(self):
        """Test basic procedural step creation."""
        step = ProceduralStep(
            step_id="step-1",
            order=1,
            action="Execute command",
            tool="Bash",
            parameters={"cmd": "ls"},
            expected_outcome="List files",
        )
        assert step.step_id == "step-1"
        assert step.order == 1
        assert step.tool == "Bash"
        assert step.on_error == "ABORT"

    def test_default_values(self):
        """Test default values."""
        step = ProceduralStep(
            step_id="step-1",
            order=1,
            action="Test",
        )
        assert step.tool is None
        assert step.parameters == {}
        assert step.expected_outcome == ""
        assert step.on_error == "ABORT"


class TestProceduralMemory:
    """Test ProceduralMemory dataclass."""

    def test_basic_creation(self, sample_procedural_memory):
        """Test basic procedural memory creation."""
        assert sample_procedural_memory.procedure_id == "proc-test-001"
        assert sample_procedural_memory.name == "Test Procedure"
        assert len(sample_procedural_memory.steps) == 1

    def test_default_values(self):
        """Test default values."""
        proc = ProceduralMemory(
            procedure_id="proc-001",
            name="Test",
            domain="TEST",
            goal_description="Goal",
        )
        assert proc.steps == []
        assert proc.trigger_conditions == []
        assert proc.success_rate == 0.0
        assert proc.execution_count == 0
        assert proc.avg_duration_ms == 0
        assert proc.last_executed is None
        assert proc.version == 1


class TestMemoryItem:
    """Test MemoryItem dataclass."""

    def test_basic_creation(self):
        """Test basic memory item creation."""
        item = MemoryItem(
            id="item-001",
            memory_type=MemoryType.SEMANTIC,
            content={"data": "test"},
            relevance_score=0.8,
        )
        assert item.id == "item-001"
        assert item.memory_type == MemoryType.SEMANTIC
        assert item.salience == 1.0

    def test_default_values(self):
        """Test default values."""
        item = MemoryItem(
            id="item-001",
            memory_type=MemoryType.EPISODIC,
            content="test",
        )
        assert item.relevance_score == 0.0
        assert item.salience == 1.0
        assert item.last_accessed is not None


# =============================================================================
# WORKING MEMORY TESTS
# =============================================================================


class TestWorkingMemory:
    """Test WorkingMemory class."""

    def test_basic_creation(self):
        """Test basic working memory creation."""
        wm = WorkingMemory(session_id="session-001")
        assert wm.session_id == "session-001"
        assert wm.capacity == WORKING_MEMORY_CAPACITY
        assert wm.retrieved_memories == []

    def test_add_item(self):
        """Test adding items to working memory."""
        wm = WorkingMemory(session_id="test", capacity=3)
        item = MemoryItem(
            id="item-1",
            memory_type=MemoryType.SEMANTIC,
            content="test",
        )
        result = wm.add_item(item)
        assert result is True
        assert len(wm.retrieved_memories) == 1
        assert wm.retrieved_memories[0].id == "item-1"

    def test_capacity_limit_eviction(self):
        """Test that lowest salience item is evicted when capacity reached."""
        wm = WorkingMemory(session_id="test", capacity=2)

        # Add first item
        item1 = MemoryItem(id="item-1", memory_type=MemoryType.SEMANTIC, content="1")
        wm.add_item(item1)
        # Decay its salience
        wm.retrieved_memories[0].salience = 0.5

        # Add second item
        item2 = MemoryItem(id="item-2", memory_type=MemoryType.SEMANTIC, content="2")
        wm.add_item(item2)

        # Add third item (should evict item1 with lower salience)
        item3 = MemoryItem(id="item-3", memory_type=MemoryType.SEMANTIC, content="3")
        wm.add_item(item3)

        assert len(wm.retrieved_memories) == 2
        assert "item-1" not in [m.id for m in wm.retrieved_memories]

    def test_evict_lowest_salience_empty(self):
        """Test eviction does nothing on empty memory."""
        wm = WorkingMemory(session_id="test", capacity=2)
        wm._evict_lowest_salience()  # Should not raise
        assert len(wm.retrieved_memories) == 0

    def test_update_attention(self):
        """Test attention weight updates."""
        wm = WorkingMemory(session_id="test")
        item1 = MemoryItem(id="item-1", memory_type=MemoryType.SEMANTIC, content="1")
        item2 = MemoryItem(id="item-2", memory_type=MemoryType.SEMANTIC, content="2")
        wm.add_item(item1)
        wm.add_item(item2)

        # Item 2 should have attention weight 1.0, item 1 decayed
        assert wm.attention_weights["item-2"] == 1.0
        assert wm.attention_weights["item-1"] < 1.0

    def test_rehearse(self):
        """Test rehearsal refreshes item salience."""
        wm = WorkingMemory(session_id="test")
        item = MemoryItem(id="item-1", memory_type=MemoryType.SEMANTIC, content="1")
        wm.add_item(item)
        wm.retrieved_memories[0].salience = 0.5

        wm.rehearse("item-1")
        assert wm.retrieved_memories[0].salience == 1.0

    def test_rehearse_nonexistent(self):
        """Test rehearse on non-existent item does nothing."""
        wm = WorkingMemory(session_id="test")
        wm.rehearse("nonexistent")  # Should not raise

    def test_get_by_id(self):
        """Test getting item by ID."""
        wm = WorkingMemory(session_id="test")
        item = MemoryItem(id="item-1", memory_type=MemoryType.SEMANTIC, content="1")
        wm.add_item(item)

        result = wm.get_by_id("item-1")
        assert result is not None
        assert result.id == "item-1"

    def test_get_by_id_nonexistent(self):
        """Test getting non-existent item returns None."""
        wm = WorkingMemory(session_id="test")
        result = wm.get_by_id("nonexistent")
        assert result is None


# =============================================================================
# RETRIEVAL STRUCTURES TESTS
# =============================================================================


class TestRetrievalCue:
    """Test RetrievalCue dataclass."""

    def test_basic_creation(self):
        """Test basic retrieval cue creation."""
        cue = RetrievalCue(
            task_description="Deploy stack",
            domain="CICD",
            keywords=["deploy", "stack"],
        )
        assert cue.task_description == "Deploy stack"
        assert cue.max_results == 5
        assert cue.min_confidence == 0.5

    def test_default_memory_types(self):
        """Test default memory types."""
        cue = RetrievalCue(task_description="Test")
        assert MemoryType.SEMANTIC in cue.memory_types
        assert MemoryType.PROCEDURAL in cue.memory_types


class TestRetrievedMemory:
    """Test RetrievedMemory dataclass."""

    def test_basic_creation(self, sample_retrieved_memory):
        """Test basic retrieved memory creation."""
        assert sample_retrieved_memory.memory_id == "sem-test-001"
        assert sample_retrieved_memory.combined_score == 0.75

    def test_default_values(self):
        """Test default values."""
        rm = RetrievedMemory(
            memory_id="rm-001",
            memory_type=MemoryType.SEMANTIC,
            full_content=None,
        )
        assert rm.keyword_score == 0.0
        assert rm.vector_similarity == 0.0
        assert rm.graph_relevance == 0.0
        assert rm.completion_method == "EXACT_MATCH"


# =============================================================================
# CONFIDENCE ESTIMATOR TESTS
# =============================================================================


class TestConfidenceEstimator:
    """Test ConfidenceEstimator class."""

    @pytest.fixture
    def estimator(self):
        """Create confidence estimator instance."""
        return ConfidenceEstimator()

    def test_estimate_no_memories(self, estimator):
        """Test estimation with no memories."""
        result = estimator.estimate(
            task={"description": "Test task", "domain": "TEST"},
            retrieved_memories=[],
        )
        assert isinstance(result, ConfidenceEstimate)
        assert result.score >= 0
        assert result.score <= 1

    def test_estimate_with_memories(self, estimator, sample_retrieved_memory):
        """Test estimation with memories."""
        result = estimator.estimate(
            task={"description": "Test task", "domain": "CICD"},
            retrieved_memories=[sample_retrieved_memory],
        )
        assert isinstance(result, ConfidenceEstimate)
        assert "memory_coverage" in result.factors
        assert "memory_agreement" in result.factors
        assert "recency" in result.factors
        assert "outcome_history" in result.factors
        assert "schema_match" in result.factors

    def test_assess_memory_coverage_none(self, estimator):
        """Test memory coverage with no memories."""
        result = estimator._assess_memory_coverage({}, [])
        assert result == 0.0

    def test_assess_memory_coverage_high_relevance(
        self, estimator, sample_retrieved_memory
    ):
        """Test memory coverage with high relevance memories."""
        sample_retrieved_memory.combined_score = 0.8
        memories = [sample_retrieved_memory] * 3
        result = estimator._assess_memory_coverage({}, memories)
        assert result == 1.0

    def test_assess_memory_coverage_partial(self, estimator, sample_retrieved_memory):
        """Test memory coverage with partial relevance."""
        sample_retrieved_memory.combined_score = 0.5
        result = estimator._assess_memory_coverage({}, [sample_retrieved_memory])
        assert result > 0
        assert result < 1.0

    def test_assess_memory_agreement_insufficient(self, estimator):
        """Test memory agreement with insufficient memories."""
        result = estimator._assess_memory_agreement([])
        assert result == 0.5

    def test_assess_memory_agreement_single(self, estimator, sample_retrieved_memory):
        """Test memory agreement with single memory."""
        result = estimator._assess_memory_agreement([sample_retrieved_memory])
        assert result == 0.5

    def test_assess_memory_agreement_no_anti_patterns(
        self, estimator, sample_semantic_memory, sample_retrieved_memory
    ):
        """Test memory agreement when no anti-patterns present."""
        sample_semantic_memory.memory_type = SemanticType.GUARDRAIL
        sample_retrieved_memory.full_content = sample_semantic_memory

        rm2 = RetrievedMemory(
            memory_id="rm-002",
            memory_type=MemoryType.SEMANTIC,
            full_content=sample_semantic_memory,
            combined_score=0.7,
        )
        result = estimator._assess_memory_agreement([sample_retrieved_memory, rm2])
        assert result == 0.9

    def test_assess_recency_no_memories(self, estimator):
        """Test recency with no memories."""
        result = estimator._assess_recency([])
        assert result == 0.3

    def test_assess_recency_recent_memories(self, estimator, sample_semantic_memory):
        """Test recency with recent memories."""
        sample_semantic_memory.last_validated = datetime.now()
        rm = RetrievedMemory(
            memory_id="rm-001",
            memory_type=MemoryType.SEMANTIC,
            full_content=sample_semantic_memory,
            combined_score=0.7,
        )
        result = estimator._assess_recency([rm])
        assert result == 1.0

    def test_assess_recency_old_memories(self, estimator, sample_semantic_memory):
        """Test recency with old memories."""
        sample_semantic_memory.last_validated = datetime.now() - timedelta(days=100)
        rm = RetrievedMemory(
            memory_id="rm-001",
            memory_type=MemoryType.SEMANTIC,
            full_content=sample_semantic_memory,
            combined_score=0.7,
        )
        result = estimator._assess_recency([rm])
        assert result == 0.3

    def test_assess_outcome_history_no_memories(self, estimator):
        """Test outcome history with no memories."""
        result = estimator._assess_outcome_history({}, None, [])
        assert result == 0.5

    def test_assess_outcome_history_with_episodes(
        self, estimator, sample_episodic_memory
    ):
        """Test outcome history with episodic memories."""
        rm = RetrievedMemory(
            memory_id="rm-001",
            memory_type=MemoryType.EPISODIC,
            full_content=sample_episodic_memory,
            combined_score=0.7,
        )
        result = estimator._assess_outcome_history({}, None, [rm])
        assert result == 1.0  # Success outcome

    def test_assess_schema_match_no_schema(self, estimator):
        """Test schema match with no schema memories."""
        result = estimator._assess_schema_match({}, [])
        assert result == 0.3

    def test_assess_schema_match_with_schema(self, estimator, sample_semantic_memory):
        """Test schema match with schema memory."""
        sample_semantic_memory.memory_type = SemanticType.SCHEMA
        rm = RetrievedMemory(
            memory_id="rm-001",
            memory_type=MemoryType.SEMANTIC,
            full_content=sample_semantic_memory,
            combined_score=0.7,
        )
        result = estimator._assess_schema_match({}, [rm])
        assert result == 1.0

    def test_assess_schema_match_with_procedure(
        self, estimator, sample_procedural_memory
    ):
        """Test schema match with procedural memory."""
        rm = RetrievedMemory(
            memory_id="rm-001",
            memory_type=MemoryType.PROCEDURAL,
            full_content=sample_procedural_memory,
            combined_score=0.5,
        )
        result = estimator._assess_schema_match({}, [rm])
        assert result == 0.7

    def test_recommend_action_high_confidence(self, estimator):
        """Test recommend action for high confidence."""
        result = estimator._recommend_action(0.90)
        assert result == RecommendedAction.PROCEED_AUTONOMOUS

    def test_recommend_action_medium_confidence(self, estimator):
        """Test recommend action for medium confidence."""
        result = estimator._recommend_action(0.75)
        assert result == RecommendedAction.PROCEED_WITH_LOGGING

    def test_recommend_action_low_confidence(self, estimator):
        """Test recommend action for low confidence."""
        result = estimator._recommend_action(0.55)
        assert result == RecommendedAction.REQUEST_REVIEW

    def test_recommend_action_very_low_confidence(self, estimator):
        """Test recommend action for very low confidence."""
        result = estimator._recommend_action(0.30)
        assert result == RecommendedAction.ESCALATE_TO_HUMAN


# =============================================================================
# STRATEGY SELECTOR TESTS
# =============================================================================


class TestStrategySelector:
    """Test StrategySelector class."""

    @pytest.fixture
    def selector(self):
        """Create strategy selector instance."""
        return StrategySelector()

    @pytest.fixture
    def high_confidence(self):
        """Create high confidence estimate."""
        return ConfidenceEstimate(
            score=0.90,
            factors={},
            uncertainties=[],
        )

    @pytest.fixture
    def medium_confidence(self):
        """Create medium confidence estimate."""
        return ConfidenceEstimate(
            score=0.65,
            factors={},
            uncertainties=["memory_coverage"],
        )

    @pytest.fixture
    def low_confidence(self):
        """Create low confidence estimate."""
        return ConfidenceEstimate(
            score=0.35,
            factors={},
            uncertainties=["memory_coverage", "schema_match"],
        )

    def test_select_procedural_execution(
        self, selector, high_confidence, sample_procedural_memory
    ):
        """Test selecting procedural execution strategy."""
        task = {"description": "deploy stack", "domain": "CICD"}
        result = selector.select_strategy(
            task=task,
            confidence=high_confidence,
            available_procedures=[sample_procedural_memory],
            available_schemas=[],
        )
        assert result.strategy_type == StrategyType.PROCEDURAL_EXECUTION
        assert result.procedure is not None
        assert result.logging_level == "MINIMAL"

    def test_select_schema_guided(
        self, selector, medium_confidence, sample_semantic_memory
    ):
        """Test selecting schema guided strategy."""
        sample_semantic_memory.memory_type = SemanticType.SCHEMA
        task = {"description": "Test task", "domain": "CICD"}
        result = selector.select_strategy(
            task=task,
            confidence=medium_confidence,
            available_procedures=[],
            available_schemas=[sample_semantic_memory],
        )
        assert result.strategy_type == StrategyType.SCHEMA_GUIDED
        assert result.logging_level == "NORMAL"

    def test_select_active_learning(self, selector, low_confidence):
        """Test selecting active learning strategy."""
        task = {"description": "Test task", "domain": "TEST"}
        result = selector.select_strategy(
            task=task,
            confidence=low_confidence,
            available_procedures=[],
            available_schemas=[],
        )
        assert result.strategy_type == StrategyType.ACTIVE_LEARNING
        assert len(result.questions) > 0
        assert result.logging_level == "VERBOSE"

    def test_find_matching_procedure(self, selector, sample_procedural_memory):
        """Test finding matching procedure."""
        task = {"description": "deploy stack to production"}
        result = selector._find_matching_procedure(task, [sample_procedural_memory])
        assert result is not None
        assert result.procedure_id == "proc-test-001"

    def test_find_matching_procedure_no_match(self, selector, sample_procedural_memory):
        """Test finding procedure with no match."""
        task = {"description": "unrelated task"}
        result = selector._find_matching_procedure(task, [sample_procedural_memory])
        assert result is None

    def test_find_matching_schema(self, selector, sample_semantic_memory):
        """Test finding matching schema."""
        sample_semantic_memory.memory_type = SemanticType.SCHEMA
        task = {"domain": "CICD"}
        result = selector._find_matching_schema(task, [sample_semantic_memory])
        assert result is not None

    def test_find_matching_schema_no_match(self, selector, sample_semantic_memory):
        """Test finding schema with no match."""
        sample_semantic_memory.memory_type = SemanticType.SCHEMA
        task = {"domain": "OTHER"}
        result = selector._find_matching_schema(task, [sample_semantic_memory])
        assert result is None

    def test_get_required_guardrails(self, selector, sample_procedural_memory):
        """Test getting required guardrails from procedure."""
        result = selector._get_required_guardrails(sample_procedural_memory)
        assert result == ["GR-001"]

    def test_get_domain_guardrails(self, selector):
        """Test getting domain guardrails."""
        result = selector._get_domain_guardrails("CICD")
        assert "GR-CICD-001" in result
        assert "GR-SEC-001" in result

    def test_get_domain_guardrails_unknown(self, selector):
        """Test getting guardrails for unknown domain."""
        result = selector._get_domain_guardrails("UNKNOWN")
        assert result == []

    def test_generate_clarifying_questions(self, selector, low_confidence):
        """Test generating clarifying questions."""
        task = {"description": "Test"}
        result = selector._generate_clarifying_questions(task, low_confidence)
        assert len(result) > 0
        assert len(result) <= 3


# =============================================================================
# PATTERN COMPLETION RETRIEVER TESTS
# =============================================================================


class TestPatternCompletionRetriever:
    """Test PatternCompletionRetriever class."""

    @pytest.fixture
    def retriever(
        self,
        mock_episodic_store,
        mock_semantic_store,
        mock_procedural_store,
        mock_embedding_service,
    ):
        """Create retriever instance."""
        return PatternCompletionRetriever(
            episodic_store=mock_episodic_store,
            semantic_store=mock_semantic_store,
            procedural_store=mock_procedural_store,
            embedding_service=mock_embedding_service,
        )

    def test_cosine_similarity_identical(self, retriever):
        """Test cosine similarity with identical vectors."""
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        result = retriever._cosine_similarity(a, b)
        assert abs(result - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self, retriever):
        """Test cosine similarity with orthogonal vectors."""
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        result = retriever._cosine_similarity(a, b)
        assert abs(result) < 0.001

    def test_cosine_similarity_empty(self, retriever):
        """Test cosine similarity with empty vectors."""
        result = retriever._cosine_similarity([], [])
        assert result == 0.0

    def test_cosine_similarity_different_lengths(self, retriever):
        """Test cosine similarity with different length vectors."""
        result = retriever._cosine_similarity([1.0], [1.0, 2.0])
        assert result == 0.0

    def test_cosine_similarity_zero_vectors(self, retriever):
        """Test cosine similarity with zero vectors."""
        result = retriever._cosine_similarity([0.0, 0.0], [0.0, 0.0])
        assert result == 0.0

    def test_merge_candidates_no_duplicates(self, retriever, sample_retrieved_memory):
        """Test merging candidates without duplicates."""
        candidates = [sample_retrieved_memory]
        result = retriever._merge_candidates(candidates)
        assert len(result) == 1

    def test_merge_candidates_with_duplicates(self, retriever):
        """Test merging candidates with duplicates."""
        rm1 = RetrievedMemory(
            memory_id="rm-001",
            memory_type=MemoryType.SEMANTIC,
            full_content=None,
            keyword_score=0.8,
            vector_similarity=0.0,
            combined_score=0.8,
        )
        rm2 = RetrievedMemory(
            memory_id="rm-001",
            memory_type=MemoryType.SEMANTIC,
            full_content=None,
            keyword_score=0.0,
            vector_similarity=0.7,
            combined_score=0.7,
        )
        result = retriever._merge_candidates([rm1, rm2])
        assert len(result) == 1
        assert result[0].keyword_score == 0.8
        assert result[0].vector_similarity == 0.7

    def test_final_rank_domain_boost(
        self, retriever, sample_retrieved_memory, sample_semantic_memory
    ):
        """Test final ranking with domain boost."""
        wm = WorkingMemory(session_id="test")
        wm.current_task = {"domain": "CICD"}
        sample_retrieved_memory.full_content = sample_semantic_memory
        sample_retrieved_memory.combined_score = 0.5

        result = retriever._final_rank([sample_retrieved_memory], wm)
        # Score should be boosted by 20%
        assert result[0].combined_score == 0.6

    @pytest.mark.asyncio
    async def test_keyword_filter(
        self, retriever, mock_semantic_store, sample_semantic_memory
    ):
        """Test keyword filtering."""
        mock_semantic_store.query_by_domain.return_value = [sample_semantic_memory]
        cue = RetrievalCue(
            task_description="Test",
            domain="CICD",
            keywords=["test", "guardrail"],
        )
        result = await retriever._keyword_filter(cue)
        assert len(result) >= 0

    @pytest.mark.asyncio
    async def test_vector_search(
        self, retriever, mock_semantic_store, sample_semantic_memory
    ):
        """Test vector search."""
        mock_semantic_store.vector_search.return_value = [sample_semantic_memory]
        cue = RetrievalCue(task_description="Test")
        embedding = [0.1] * 10
        result = await retriever._vector_search(embedding, cue)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_complete_pattern(
        self, retriever, sample_retrieved_memory, sample_semantic_memory
    ):
        """Test pattern completion."""
        sample_semantic_memory.content = "Test content with keywords"
        sample_retrieved_memory.full_content = sample_semantic_memory
        cue = RetrievalCue(
            task_description="Test",
            keywords=["content"],
        )
        result = await retriever._complete_pattern(sample_retrieved_memory, cue)
        assert result.completion_confidence > 0

    @pytest.mark.asyncio
    async def test_graph_expand(
        self,
        retriever,
        mock_semantic_store,
        sample_semantic_memory,
        sample_retrieved_memory,
    ):
        """Test graph expansion."""
        sample_semantic_memory.related_memories = ["related-001"]
        sample_retrieved_memory.full_content = sample_semantic_memory

        related_mem = SemanticMemory(
            memory_id="related-001",
            memory_type=SemanticType.PATTERN,
            domain="CICD",
            title="Related",
            content="Content",
        )
        mock_semantic_store.get.return_value = related_mem

        wm = WorkingMemory(session_id="test")
        result = await retriever._graph_expand([sample_retrieved_memory], wm)
        assert len(result) >= 1


# =============================================================================
# CONSOLIDATION PIPELINE TESTS
# =============================================================================


class TestConsolidationPipeline:
    """Test ConsolidationPipeline class."""

    @pytest.fixture
    def pipeline(
        self, mock_episodic_store, mock_semantic_store, mock_embedding_service
    ):
        """Create consolidation pipeline instance."""
        return ConsolidationPipeline(
            episodic_store=mock_episodic_store,
            semantic_store=mock_semantic_store,
            embedding_service=mock_embedding_service,
        )

    def test_cluster_episodes_by_domain_outcome(self, pipeline, sample_episodic_memory):
        """Test clustering episodes by domain and outcome."""
        episodes = [sample_episodic_memory]
        result = pipeline._cluster_episodes(episodes)
        # Clusters require MIN_EPISODES_FOR_PATTERN (3) episodes
        assert result == []

    def test_cluster_episodes_sufficient(self, pipeline):
        """Test clustering with sufficient episodes."""
        episodes = [
            EpisodicMemory(
                episode_id=f"ep-{i}",
                timestamp=datetime.now(),
                domain="CICD",
                task_description="Test",
                input_context={},
                outcome=OutcomeStatus.SUCCESS,
                keywords=["test"],
            )
            for i in range(5)
        ]
        result = pipeline._cluster_episodes(episodes)
        assert len(result) == 1
        assert len(result[0]) == 5

    def test_find_common_keywords(self, pipeline):
        """Test finding common keywords."""
        episodes = [
            EpisodicMemory(
                episode_id=f"ep-{i}",
                timestamp=datetime.now(),
                domain="TEST",
                task_description="Test",
                input_context={},
                keywords=["common", f"unique{i}"],
            )
            for i in range(3)
        ]
        result = pipeline._find_common_keywords(episodes)
        assert "common" in result

    def test_find_common_keywords_empty(self, pipeline):
        """Test finding common keywords with empty list."""
        result = pipeline._find_common_keywords([])
        assert result == []

    def test_find_common_decisions(self, pipeline):
        """Test finding common decisions."""
        episodes = [
            EpisodicMemory(
                episode_id=f"ep-{i}",
                timestamp=datetime.now(),
                domain="TEST",
                task_description="Test",
                input_context={},
                decision="Common decision",
            )
            for i in range(3)
        ]
        result = pipeline._find_common_decisions(episodes)
        assert result == "Common decision"

    def test_find_common_decisions_empty(self, pipeline):
        """Test finding common decisions with no decisions."""
        episodes = [
            EpisodicMemory(
                episode_id=f"ep-{i}",
                timestamp=datetime.now(),
                domain="TEST",
                task_description="Test",
                input_context={},
                decision="",
            )
            for i in range(3)
        ]
        result = pipeline._find_common_decisions(episodes)
        assert result == ""

    def test_validate_pattern_empty(self, pipeline):
        """Test validating pattern with empty data."""
        result = pipeline._validate_pattern("", [], OutcomeStatus.SUCCESS)
        assert result == 0.0

    def test_validate_pattern_matching(self, pipeline):
        """Test validating pattern with matching episodes."""
        pattern = "deploy"
        episodes = [
            EpisodicMemory(
                episode_id=f"ep-{i}",
                timestamp=datetime.now(),
                domain="TEST",
                task_description="Test",
                input_context={},
                decision="Deploy stack",
                outcome=OutcomeStatus.SUCCESS,
            )
            for i in range(2)
        ]
        result = pipeline._validate_pattern(pattern, episodes, OutcomeStatus.SUCCESS)
        assert result == 1.0

    def test_calculate_similarity(self, pipeline, sample_semantic_memory):
        """Test calculating similarity."""
        pattern = {"keywords": ["test", "guardrail"]}
        result = pipeline._calculate_similarity(pattern, sample_semantic_memory)
        assert result > 0

    def test_calculate_similarity_no_overlap(self, pipeline, sample_semantic_memory):
        """Test calculating similarity with no overlap."""
        sample_semantic_memory.keywords = []
        pattern = {"keywords": ["other"]}
        result = pipeline._calculate_similarity(pattern, sample_semantic_memory)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_extract_pattern_insufficient(self, pipeline):
        """Test extracting pattern with insufficient episodes."""
        episodes = [
            EpisodicMemory(
                episode_id="ep-1",
                timestamp=datetime.now(),
                domain="TEST",
                task_description="Test",
                input_context={},
            )
        ]
        result = await pipeline._extract_pattern(episodes)
        assert result is None

    @pytest.mark.asyncio
    async def test_consolidate_insufficient_episodes(
        self, pipeline, mock_episodic_store
    ):
        """Test consolidation with insufficient episodes."""
        mock_episodic_store.query_unconsolidated.return_value = []
        result = await pipeline.consolidate()
        assert result["episodes_processed"] == 0
        assert result["patterns_extracted"] == 0

    @pytest.mark.asyncio
    async def test_prune_episodes(self, pipeline):
        """Test pruning episodes."""
        result = await pipeline._prune_episodes()
        assert result == 0  # Currently returns 0


# =============================================================================
# COGNITIVE MEMORY SERVICE TESTS
# =============================================================================


class TestCognitiveMemoryService:
    """Test CognitiveMemoryService class."""

    @pytest.fixture
    def service(
        self,
        mock_episodic_store,
        mock_semantic_store,
        mock_procedural_store,
        mock_embedding_service,
    ):
        """Create service instance."""
        return CognitiveMemoryService(
            episodic_store=mock_episodic_store,
            semantic_store=mock_semantic_store,
            procedural_store=mock_procedural_store,
            embedding_service=mock_embedding_service,
        )

    def test_extract_keywords(self, service):
        """Test keyword extraction."""
        result = service._extract_keywords("Deploy the CloudFormation stack")
        assert "deploy" in result
        assert "cloudformation" in result
        assert "stack" in result
        assert "the" not in result  # Stopword removed

    def test_extract_keywords_truncation(self, service):
        """Test keyword extraction truncates to 20."""
        text = " ".join([f"keyword{i}" for i in range(50)])
        result = service._extract_keywords(text)
        assert len(result) <= 20

    def test_get_guardrails_from_memories(
        self, service, sample_semantic_memory, sample_retrieved_memory
    ):
        """Test extracting guardrails from memories."""
        sample_semantic_memory.memory_type = SemanticType.GUARDRAIL
        sample_retrieved_memory.full_content = sample_semantic_memory

        result = service._get_guardrails_from_memories([sample_retrieved_memory])
        assert len(result) == 1
        assert result[0]["id"] == "sem-test-001"

    def test_get_guardrails_from_memories_empty(self, service):
        """Test extracting guardrails from empty list."""
        result = service._get_guardrails_from_memories([])
        assert result == []

    @pytest.mark.asyncio
    async def test_record_episode(self, service, mock_episodic_store):
        """Test recording an episode."""
        result = await service.record_episode(
            task_description="Test task",
            domain="TEST",
            decision="Test decision",
            reasoning="Test reasoning",
            outcome=OutcomeStatus.SUCCESS,
            outcome_details="Completed",
            confidence_at_decision=0.8,
        )
        assert result.domain == "TEST"
        assert result.outcome == OutcomeStatus.SUCCESS
        mock_episodic_store.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_consolidation(self, service, mock_episodic_store):
        """Test running consolidation."""
        mock_episodic_store.query_unconsolidated.return_value = []
        result = await service.run_consolidation()
        assert "episodes_processed" in result


# =============================================================================
# CRITIC AGENT TESTS
# =============================================================================


class TestCriticAgent:
    """Test CriticAgent class."""

    @pytest.fixture
    def critic(self):
        """Create critic agent instance."""
        return CriticAgent()

    @pytest.fixture
    def sample_strategy(self):
        """Create sample strategy."""
        return Strategy(
            strategy_type=StrategyType.SCHEMA_GUIDED,
            guardrails=["GR-001"],
        )

    def test_evaluate_decision_no_memories(self, critic, sample_strategy):
        """Test evaluation with no memories."""
        result = critic.evaluate_decision(
            task={"description": "Test", "domain": "TEST"},
            proposed_decision="Proceed",
            memory_agent_confidence=0.8,
            retrieved_memories=[],
            strategy=sample_strategy,
        )
        assert isinstance(result, CriticEvaluation)
        assert result.overall_challenge_score > 0

    def test_challenge_context_sufficiency_high_conf_few_memories(
        self, critic, sample_retrieved_memory
    ):
        """Test context sufficiency challenge with high confidence but few memories."""
        result = critic._challenge_context_sufficiency(
            task={},
            memories=[sample_retrieved_memory],
            confidence=0.85,
        )
        assert result is not None
        assert result[0] == CriticChallenge.INSUFFICIENT_CONTEXT

    def test_challenge_context_sufficiency_adequate(
        self, critic, sample_retrieved_memory
    ):
        """Test context sufficiency with adequate context."""
        sample_retrieved_memory.combined_score = 0.8
        memories = [sample_retrieved_memory] * 5
        result = critic._challenge_context_sufficiency(
            task={},
            memories=memories,
            confidence=0.65,
        )
        assert result is None

    def test_challenge_domain_relevance_unknown(self, critic):
        """Test domain relevance challenge with unknown domain."""
        result = critic._challenge_domain_relevance(
            task={"domain": "UNKNOWN"},
            memories=[],
        )
        assert result is not None
        assert result[0] == CriticChallenge.DOMAIN_MISMATCH

    def test_challenge_domain_relevance_outside_known(self, critic):
        """Test domain relevance with domain outside known expertise."""
        result = critic._challenge_domain_relevance(
            task={"domain": "QUANTUM_PHYSICS"},
            memories=[],
        )
        assert result is not None
        assert result[0] == CriticChallenge.DOMAIN_MISMATCH

    def test_are_domains_related_true(self, critic):
        """Test related domains detection."""
        assert critic._are_domains_related("CICD", "CFN")
        assert critic._are_domains_related("IAM", "SECURITY")

    def test_are_domains_related_false(self, critic):
        """Test unrelated domains detection."""
        assert not critic._are_domains_related("CICD", "OTHER")

    def test_challenge_logical_leaps_no_memories(self, critic):
        """Test logical leaps challenge with no memories and proceed decision."""
        result = critic._challenge_logical_leaps(
            task={},
            decision="Proceed with deployment",
            memories=[],
        )
        assert result is not None
        assert result[0] == CriticChallenge.LOGICAL_INCONSISTENCY

    def test_challenge_missing_information_vague(self, critic):
        """Test missing information challenge with vague task."""
        result = critic._challenge_missing_information(
            task={"description": "fix it"},
            decision="",
        )
        assert result is not None
        assert result[0] == CriticChallenge.MISSING_INFORMATION

    def test_challenge_missing_information_clear(self, critic):
        """Test missing information with clear task."""
        result = critic._challenge_missing_information(
            task={
                "description": "Deploy the CloudFormation stack for Neptune database in production"
            },
            decision="",
        )
        assert result is None

    def test_challenge_strategy_appropriateness_high_challenges(self, critic):
        """Test strategy challenge with many existing challenges."""
        strategy = Strategy(
            strategy_type=StrategyType.PROCEDURAL_EXECUTION,
        )
        result = critic._challenge_strategy_appropriateness(
            strategy=strategy,
            confidence=0.8,
            challenge_count=3,
        )
        assert result is not None
        assert result[0] == CriticChallenge.PATTERN_MISMATCH

    def test_challenge_retrieval_quality_weak_matches(
        self, critic, sample_retrieved_memory
    ):
        """Test retrieval quality challenge with weak matches."""
        sample_retrieved_memory.combined_score = 0.4
        result = critic._challenge_retrieval_quality(
            memories=[sample_retrieved_memory],
            confidence=0.70,
        )
        assert result is not None

    def test_challenge_task_complexity_complex(self, critic):
        """Test task complexity detection."""
        complex_task = {
            "description": """
            Production deployment of critical IAM security update.
            1. Update Neptune permissions
            2. Update OpenSearch access
            3. Deploy to EKS
            4. Verify compliance
            """
        }
        result = critic._challenge_task_complexity(
            task=complex_task,
            confidence=0.70,
        )
        assert result is not None
        assert result[0] == CriticChallenge.PATTERN_MISMATCH

    def test_apply_baseline_skepticism_high_confidence(self, critic):
        """Test baseline skepticism for high confidence."""
        result = critic._apply_baseline_skepticism(
            task={},
            confidence=0.80,
            existing_challenge_count=0,
        )
        assert result is not None
        assert result[0] == CriticChallenge.OVERCONFIDENT_LEAP

    def test_apply_baseline_skepticism_low_confidence(self, critic):
        """Test baseline skepticism for low confidence."""
        result = critic._apply_baseline_skepticism(
            task={},
            confidence=0.40,
            existing_challenge_count=0,
        )
        assert result is None

    def test_apply_baseline_skepticism_already_challenged(self, critic):
        """Test baseline skepticism skipped when already challenged."""
        result = critic._apply_baseline_skepticism(
            task={},
            confidence=0.80,
            existing_challenge_count=2,
        )
        assert result is None


# =============================================================================
# DUAL AGENT ORCHESTRATOR TESTS
# =============================================================================


class TestDualAgentOrchestrator:
    """Test DualAgentOrchestrator class."""

    @pytest.fixture
    def orchestrator(
        self,
        mock_episodic_store,
        mock_semantic_store,
        mock_procedural_store,
        mock_embedding_service,
    ):
        """Create orchestrator instance."""
        memory_service = CognitiveMemoryService(
            episodic_store=mock_episodic_store,
            semantic_store=mock_semantic_store,
            procedural_store=mock_procedural_store,
            embedding_service=mock_embedding_service,
        )
        return DualAgentOrchestrator(
            memory_service=memory_service,
            default_mode=AgentMode.DUAL,
        )

    def test_should_use_dual_mode_risk_indicator(self, orchestrator):
        """Test dual mode detection with risk indicator."""
        result = orchestrator._should_use_dual_mode(
            "Deploy to production environment",
            "CICD",
        )
        assert result is True

    def test_should_use_dual_mode_security_domain(self, orchestrator):
        """Test dual mode detection with security domain."""
        result = orchestrator._should_use_dual_mode(
            "Regular task",
            "SECURITY",
        )
        assert result is True

    def test_should_use_dual_mode_no_risk(self, orchestrator):
        """Test dual mode detection without risk indicators."""
        result = orchestrator._should_use_dual_mode(
            "Simple development task",
            "DEVELOPMENT",
        )
        assert result is False

    def test_generate_decision_procedural(self, orchestrator, sample_procedural_memory):
        """Test decision generation for procedural strategy."""
        strategy = Strategy(
            strategy_type=StrategyType.PROCEDURAL_EXECUTION,
            procedure=sample_procedural_memory,
        )
        result = orchestrator._generate_decision(strategy, [], 0.9)
        assert "procedure" in result.lower()
        assert "Test Procedure" in result

    def test_generate_decision_guardrails(self, orchestrator):
        """Test decision generation with guardrails."""
        strategy = Strategy(strategy_type=StrategyType.SCHEMA_GUIDED)
        guardrails = [{"id": "GR-001"}, {"id": "GR-002"}]
        result = orchestrator._generate_decision(strategy, guardrails, 0.7)
        assert "guardrails" in result.lower()

    def test_generate_decision_active_learning(self, orchestrator):
        """Test decision generation for active learning."""
        strategy = Strategy(strategy_type=StrategyType.ACTIVE_LEARNING)
        result = orchestrator._generate_decision(strategy, [], 0.4)
        assert "guidance" in result.lower()

    def test_generate_decision_human_guidance(self, orchestrator):
        """Test decision generation for human guidance."""
        strategy = Strategy(strategy_type=StrategyType.HUMAN_GUIDANCE)
        result = orchestrator._generate_decision(strategy, [], 0.3)
        assert "human" in result.lower() or "escalate" in result.lower()

    def test_calibrate_confidence(self, orchestrator):
        """Test confidence calibration."""
        initial = ConfidenceEstimate(score=0.8, factors={}, uncertainties=[])
        critic_eval = CriticEvaluation(
            challenges=[],
            overall_challenge_score=0.3,
            confidence_adjustment=0.8,
            questions=[],
            should_escalate=False,
        )
        result = orchestrator._calibrate_confidence(initial, critic_eval)
        assert result < 0.8
        assert result >= 0.1

    def test_calibrate_confidence_high_severity(self, orchestrator):
        """Test confidence calibration with high severity challenges."""
        initial = ConfidenceEstimate(score=0.8, factors={}, uncertainties=[])
        critic_eval = CriticEvaluation(
            challenges=[
                (CriticChallenge.INSUFFICIENT_CONTEXT, "reason", 0.8),
            ],
            overall_challenge_score=0.5,
            confidence_adjustment=0.7,
            questions=[],
            should_escalate=False,
        )
        result = orchestrator._calibrate_confidence(initial, critic_eval)
        assert result < 0.8 * 0.7

    def test_adjust_strategy_escalation(self, orchestrator):
        """Test strategy adjustment for escalation."""
        original = Strategy(strategy_type=StrategyType.PROCEDURAL_EXECUTION)
        critic_eval = CriticEvaluation(
            challenges=[],
            overall_challenge_score=0.0,
            confidence_adjustment=1.0,
            questions=["Question 1"],
            should_escalate=True,
        )
        result = orchestrator._adjust_strategy_if_needed(original, 0.8, critic_eval)
        assert result.strategy_type == StrategyType.HUMAN_GUIDANCE

    def test_adjust_strategy_confidence_drop_procedural(self, orchestrator):
        """Test strategy adjustment when confidence drops from procedural."""
        original = Strategy(strategy_type=StrategyType.PROCEDURAL_EXECUTION)
        critic_eval = CriticEvaluation(
            challenges=[],
            overall_challenge_score=0.0,
            confidence_adjustment=1.0,
            questions=[],
            should_escalate=False,
        )
        result = orchestrator._adjust_strategy_if_needed(original, 0.60, critic_eval)
        assert result.strategy_type == StrategyType.SCHEMA_GUIDED

    def test_adjust_strategy_confidence_drop_schema(self, orchestrator):
        """Test strategy adjustment when confidence drops from schema."""
        original = Strategy(strategy_type=StrategyType.SCHEMA_GUIDED)
        critic_eval = CriticEvaluation(
            challenges=[],
            overall_challenge_score=0.0,
            confidence_adjustment=1.0,
            questions=["Q1"],
            should_escalate=False,
        )
        result = orchestrator._adjust_strategy_if_needed(original, 0.40, critic_eval)
        assert result.strategy_type == StrategyType.ACTIVE_LEARNING

    def test_generate_final_decision_escalate(self, orchestrator):
        """Test final decision generation for escalation."""
        critic_eval = CriticEvaluation(
            challenges=[
                (CriticChallenge.INSUFFICIENT_CONTEXT, "reason", 0.5),
            ],
            overall_challenge_score=0.5,
            confidence_adjustment=0.7,
            questions=["Question?"],
            should_escalate=True,
        )
        strategy = Strategy(strategy_type=StrategyType.HUMAN_GUIDANCE)
        result = orchestrator._generate_final_decision(
            "Original action",
            critic_eval,
            strategy,
        )
        assert "ESCALATE" in result

    def test_generate_final_decision_active_learning(self, orchestrator):
        """Test final decision generation for active learning."""
        critic_eval = CriticEvaluation(
            challenges=[],
            overall_challenge_score=0.0,
            confidence_adjustment=1.0,
            questions=["Q1"],
            should_escalate=False,
        )
        strategy = Strategy(strategy_type=StrategyType.ACTIVE_LEARNING)
        result = orchestrator._generate_final_decision(
            "Original action",
            critic_eval,
            strategy,
        )
        assert "Tentative" in result

    @pytest.mark.asyncio
    async def test_make_decision_single_mode(self, orchestrator):
        """Test decision making in single mode."""
        result = await orchestrator.make_decision(
            task_description="Simple task",
            domain="TEST",
            mode=AgentMode.SINGLE,
        )
        assert result["agent_mode"] == "SINGLE"
        assert result["critic_evaluation"] is None

    @pytest.mark.asyncio
    async def test_make_decision_dual_mode(self, orchestrator):
        """Test decision making in dual mode."""
        result = await orchestrator.make_decision(
            task_description="Simple task",
            domain="TEST",
            mode=AgentMode.DUAL,
        )
        assert result["agent_mode"] == "DUAL"
        assert result["critic_evaluation"] is not None


# =============================================================================
# ACCURACY MONITOR TESTS
# =============================================================================


class TestAccuracyMonitor:
    """Test AccuracyMonitor class."""

    @pytest.fixture
    def monitor(self, mock_episodic_store):
        """Create accuracy monitor instance."""
        return AccuracyMonitor(episodic_store=mock_episodic_store)

    def test_calculate_band_accuracy_empty(self, monitor):
        """Test band accuracy with empty list."""
        result = monitor._calculate_band_accuracy([])
        assert result["count"] == 0
        assert result["accuracy"] is None

    def test_calculate_band_accuracy_all_success(self, monitor):
        """Test band accuracy with all successes."""
        episodes = [
            EpisodicMemory(
                episode_id=f"ep-{i}",
                timestamp=datetime.now(),
                domain="TEST",
                task_description="Test",
                input_context={},
                outcome=OutcomeStatus.SUCCESS,
            )
            for i in range(5)
        ]
        result = monitor._calculate_band_accuracy(episodes)
        assert result["count"] == 5
        assert result["accuracy"] == 1.0

    def test_calculate_band_accuracy_mixed(self, monitor):
        """Test band accuracy with mixed outcomes."""
        episodes = [
            EpisodicMemory(
                episode_id="ep-1",
                timestamp=datetime.now(),
                domain="TEST",
                task_description="Test",
                input_context={},
                outcome=OutcomeStatus.SUCCESS,
            ),
            EpisodicMemory(
                episode_id="ep-2",
                timestamp=datetime.now(),
                domain="TEST",
                task_description="Test",
                input_context={},
                outcome=OutcomeStatus.FAILURE,
            ),
        ]
        result = monitor._calculate_band_accuracy(episodes)
        assert result["count"] == 2
        assert result["accuracy"] == 0.5

    @pytest.mark.asyncio
    async def test_calculate_accuracy_no_episodes(self, monitor, mock_episodic_store):
        """Test accuracy calculation with no episodes."""
        mock_episodic_store.query_by_domain.return_value = []
        result = await monitor.calculate_accuracy()
        assert result["overall_accuracy"] is None
        assert "No episodes" in result["message"]

    @pytest.mark.asyncio
    async def test_calculate_accuracy_with_episodes(self, monitor, mock_episodic_store):
        """Test accuracy calculation with episodes."""
        episodes = [
            EpisodicMemory(
                episode_id="ep-1",
                timestamp=datetime.now(),
                domain="CICD",
                task_description="Test",
                input_context={},
                outcome=OutcomeStatus.SUCCESS,
                confidence_at_decision=0.9,
            ),
            EpisodicMemory(
                episode_id="ep-2",
                timestamp=datetime.now(),
                domain="CICD",
                task_description="Test",
                input_context={},
                outcome=OutcomeStatus.FAILURE,
                confidence_at_decision=0.6,
            ),
        ]

        # Only return episodes for CICD domain, empty for others
        def side_effect(domain, since, limit=100):
            if domain == "CICD":
                return episodes
            return []

        mock_episodic_store.query_by_domain.side_effect = side_effect
        result = await monitor.calculate_accuracy()
        assert result["overall_accuracy"] == 0.5
        assert result["episode_count"] == 2

    @pytest.mark.asyncio
    async def test_calculate_accuracy_alerts(self, monitor, mock_episodic_store):
        """Test accuracy calculation generates alerts when below target."""
        episodes = [
            EpisodicMemory(
                episode_id=f"ep-{i}",
                timestamp=datetime.now(),
                domain="CICD",
                task_description="Test",
                input_context={},
                outcome=OutcomeStatus.FAILURE,
                confidence_at_decision=0.9,
            )
            for i in range(10)
        ]
        mock_episodic_store.query_by_domain.return_value = episodes
        result = await monitor.calculate_accuracy()
        assert result["overall_accuracy"] == 0.0
        assert len(result["alerts"]) > 0
        assert any("CRITICAL" in alert["severity"] for alert in result["alerts"])
