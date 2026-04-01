"""
Tests for reasoning chain builder.
"""

import pytest

from src.services.explainability.config import ReasoningChainConfig
from src.services.explainability.reasoning_chain import (
    ReasoningChainBuilder,
    configure_reasoning_chain_builder,
    get_reasoning_chain_builder,
    reset_reasoning_chain_builder,
)


class TestReasoningChainBuilder:
    """Tests for ReasoningChainBuilder class."""

    def setup_method(self):
        """Reset builder before each test."""
        reset_reasoning_chain_builder()

    def teardown_method(self):
        """Reset builder after each test."""
        reset_reasoning_chain_builder()

    def test_init_without_bedrock(self):
        """Test initialization without Bedrock client."""
        builder = ReasoningChainBuilder()
        assert builder.bedrock is None
        assert builder.config is not None

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = ReasoningChainConfig(max_evidence_per_step=10)
        builder = ReasoningChainBuilder(config=config)
        assert builder.config.max_evidence_per_step == 10

    @pytest.mark.asyncio
    async def test_build_basic_chain(
        self, sample_decision_input, sample_decision_output
    ):
        """Test building a basic reasoning chain."""
        builder = ReasoningChainBuilder()
        chain = await builder.build(
            decision_id="dec_test",
            agent_id="test_agent",
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            min_steps=2,
        )

        assert chain.decision_id == "dec_test"
        assert chain.agent_id == "test_agent"
        assert len(chain.steps) >= 2

    @pytest.mark.asyncio
    async def test_build_respects_min_steps(
        self, sample_decision_input, sample_decision_output
    ):
        """Test that builder respects minimum steps."""
        builder = ReasoningChainBuilder()

        # Request 3 minimum steps
        chain = await builder.build(
            decision_id="dec_test",
            agent_id="test_agent",
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            min_steps=3,
        )

        assert len(chain.steps) >= 3

    def test_build_sync_basic_chain(
        self, sample_decision_input, sample_decision_output
    ):
        """Test synchronous chain building."""
        builder = ReasoningChainBuilder()
        chain = builder.build_sync(
            decision_id="dec_test",
            agent_id="test_agent",
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            min_steps=2,
        )

        assert chain.decision_id == "dec_test"
        assert len(chain.steps) >= 2

    def test_build_sync_with_various_inputs(
        self, sample_decision_input, sample_decision_output
    ):
        """Test synchronous chain building with various inputs."""
        builder = ReasoningChainBuilder()

        # build_sync doesn't take context parameter (that's for async build)
        chain = builder.build_sync(
            decision_id="dec_test",
            agent_id="test_agent",
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            min_steps=2,
        )

        assert chain.decision_id == "dec_test"
        assert len(chain.steps) >= 2

    def test_extract_steps_heuristic_security(self):
        """Test heuristic extraction for security-related decisions."""
        builder = ReasoningChainBuilder()
        decision_input = {"task": "security_review", "code": "eval(input)"}
        decision_output = {"action": "flag_vulnerability", "severity": "critical"}

        steps = builder._extract_steps_heuristic(
            decision_input, decision_output, min_steps=2
        )

        assert len(steps) >= 2
        # Should detect security-related content
        assert any(
            "security" in str(s).lower() or "vulnerability" in str(s).lower()
            for s in steps
        )

    def test_extract_steps_heuristic_code_change(self):
        """Test heuristic extraction for code change decisions."""
        builder = ReasoningChainBuilder()
        decision_input = {"task": "fix_bug", "file": "app.py"}
        decision_output = {"code_changes": {"old": "x = 1", "new": "x = 2"}}

        steps = builder._extract_steps_heuristic(
            decision_input, decision_output, min_steps=2
        )

        assert len(steps) >= 2
        # Should detect code change
        assert any(
            "code" in str(s).lower() or "change" in str(s).lower() for s in steps
        )

    def test_extract_steps_heuristic_test_result(self):
        """Test heuristic extraction for test result decisions."""
        builder = ReasoningChainBuilder()
        decision_input = {"task": "run_tests"}
        decision_output = {"result": "passed", "tests_run": 50}

        steps = builder._extract_steps_heuristic(
            decision_input, decision_output, min_steps=2
        )

        assert len(steps) >= 2

    def test_extract_steps_heuristic_generic(self):
        """Test heuristic extraction for generic decisions."""
        builder = ReasoningChainBuilder()
        decision_input = {"task": "analyze_data"}
        decision_output = {"recommendation": "process_further"}

        steps = builder._extract_steps_heuristic(
            decision_input, decision_output, min_steps=2
        )

        assert len(steps) >= 2

    def test_build_sync_minimum_steps_enforcement(
        self, sample_decision_input, sample_decision_output
    ):
        """Test that minimum steps are enforced."""
        builder = ReasoningChainBuilder()

        # Request many steps
        chain = builder.build_sync(
            decision_id="dec_test",
            agent_id="test_agent",
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            min_steps=5,
        )

        assert len(chain.steps) >= 5

    def test_step_numbering(self, sample_decision_input, sample_decision_output):
        """Test that steps are numbered correctly."""
        builder = ReasoningChainBuilder()
        chain = builder.build_sync(
            decision_id="dec_test",
            agent_id="test_agent",
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            min_steps=3,
        )

        for i, step in enumerate(chain.steps):
            assert step.step_number == i + 1


class TestGlobalBuilderManagement:
    """Tests for global builder management functions."""

    def setup_method(self):
        """Reset builder before each test."""
        reset_reasoning_chain_builder()

    def teardown_method(self):
        """Reset builder after each test."""
        reset_reasoning_chain_builder()

    def test_get_reasoning_chain_builder(self):
        """Test getting the global builder."""
        builder = get_reasoning_chain_builder()
        assert builder is not None
        assert isinstance(builder, ReasoningChainBuilder)

    def test_configure_reasoning_chain_builder(self, mock_bedrock_client):
        """Test configuring the global builder."""
        config = ReasoningChainConfig(max_evidence_per_step=10)
        builder = configure_reasoning_chain_builder(
            bedrock_client=mock_bedrock_client,
            config=config,
        )

        assert builder.bedrock is mock_bedrock_client
        assert builder.config.max_evidence_per_step == 10

    def test_reset_reasoning_chain_builder(self):
        """Test resetting the global builder."""
        # Configure with custom settings
        config = ReasoningChainConfig(max_evidence_per_step=10)
        configure_reasoning_chain_builder(config=config)

        # Reset
        reset_reasoning_chain_builder()

        # Should get fresh default builder
        builder = get_reasoning_chain_builder()
        assert builder.config.max_evidence_per_step == 5  # Default

    def test_builder_singleton(self):
        """Test that get returns the same instance."""
        builder1 = get_reasoning_chain_builder()
        builder2 = get_reasoning_chain_builder()
        assert builder1 is builder2
