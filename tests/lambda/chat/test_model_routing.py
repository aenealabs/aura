"""
Phase 1: Intelligent Model Routing Tests

Tests for the 3-tier model routing system (ADR-028 compliant):
- FAST tier (Haiku): Simple queries, greetings, status checks
- ACCURATE tier (Sonnet): Code analysis, diagrams, tool use
- MAXIMUM tier (Opus): Deep research, cross-codebase analysis
"""

import os
import sys

import pytest

# Add source path
CHAT_LAMBDA_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "src",
    "lambda",
    "chat",
)
sys.path.insert(0, os.path.abspath(CHAT_LAMBDA_PATH))


class TestModelTierClassification:
    """Test query classification into model tiers."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars):
        """Set up environment and import module."""
        # Import after env vars are set
        from chat_handler import (
            BEDROCK_MODEL_ID,
            HAIKU_MODEL_ID,
            OPUS_MODEL_ID,
            ModelTier,
            classify_query_tier,
            select_model,
        )

        self.ModelTier = ModelTier
        self.classify_query_tier = classify_query_tier
        self.select_model = select_model
        self.HAIKU_MODEL_ID = HAIKU_MODEL_ID
        self.BEDROCK_MODEL_ID = BEDROCK_MODEL_ID
        self.OPUS_MODEL_ID = OPUS_MODEL_ID

    # =========================================================================
    # FAST Tier Tests (Haiku)
    # =========================================================================

    def test_greeting_routes_to_fast_tier(self):
        """Simple greetings should use FAST tier (Haiku)."""
        fast_queries = [
            "hello",
            "Hi there",
            "hey",
            "Thanks!",
            "thank you",
            "bye",
            "goodbye",
        ]
        for query in fast_queries:
            tier = self.classify_query_tier(query)
            assert tier == self.ModelTier.FAST, f"'{query}' should route to FAST tier"

    def test_simple_affirmations_route_to_fast_tier(self):
        """Simple yes/no responses should use FAST tier."""
        fast_queries = ["yes", "no", "ok", "okay", "sure"]
        for query in fast_queries:
            tier = self.classify_query_tier(query)
            assert tier == self.ModelTier.FAST, f"'{query}' should route to FAST tier"

    def test_help_command_routes_to_fast_tier(self):
        """Help command should use FAST tier."""
        tier = self.classify_query_tier("help")
        assert tier == self.ModelTier.FAST

    def test_status_command_routes_to_fast_tier(self):
        """Status command should use FAST tier."""
        tier = self.classify_query_tier("status")
        assert tier == self.ModelTier.FAST

    def test_long_greeting_does_not_route_to_fast(self):
        """Long messages starting with greetings should not use FAST tier."""
        # FAST tier only applies to short messages (<100 chars)
        long_query = "hello, I need help understanding the authentication flow " * 3
        tier = self.classify_query_tier(long_query)
        # Should default to ACCURATE since it's >100 chars
        assert tier != self.ModelTier.FAST

    # =========================================================================
    # ACCURATE Tier Tests (Sonnet)
    # =========================================================================

    def test_diagram_request_routes_to_accurate_tier(self):
        """Diagram generation requests should use ACCURATE tier."""
        accurate_queries = [
            "generate a flowchart for the auth flow",
            "create a sequence diagram for API calls",
            "draw an architecture diagram",
            "can you create a class diagram for the agents?",
        ]
        for query in accurate_queries:
            tier = self.classify_query_tier(query)
            assert (
                tier == self.ModelTier.ACCURATE
            ), f"'{query}' should route to ACCURATE tier"

    def test_code_analysis_routes_to_accurate_tier(self):
        """Code analysis requests should use ACCURATE tier."""
        accurate_queries = [
            "code review the new changes",
            "analyze this code for bugs",
            "explain the function in context_retrieval.py",
            "explain how this class works",
        ]
        for query in accurate_queries:
            tier = self.classify_query_tier(query)
            assert (
                tier == self.ModelTier.ACCURATE
            ), f"'{query}' should route to ACCURATE tier"

    def test_vulnerability_query_routes_to_accurate_tier(self):
        """Vulnerability queries should use ACCURATE tier."""
        tier = self.classify_query_tier("check for vulnerabilities in auth module")
        assert tier == self.ModelTier.ACCURATE

    def test_bug_search_routes_to_accurate_tier(self):
        """Bug search queries should use ACCURATE tier."""
        accurate_queries = [
            "find bugs in the code",
            "search for errors in the API",
            "look for issues in validation",
        ]
        for query in accurate_queries:
            tier = self.classify_query_tier(query)
            assert (
                tier == self.ModelTier.ACCURATE
            ), f"'{query}' should route to ACCURATE tier"

    def test_default_routes_to_accurate_tier(self):
        """Queries without specific patterns should default to ACCURATE."""
        generic_queries = [
            "how do I configure the Neptune connection?",
            "what are the API endpoints?",
            "show me the recent changes",
        ]
        for query in generic_queries:
            tier = self.classify_query_tier(query)
            assert (
                tier == self.ModelTier.ACCURATE
            ), f"'{query}' should default to ACCURATE tier"

    # =========================================================================
    # MAXIMUM Tier Tests (Opus)
    # =========================================================================

    def test_deep_research_routes_to_maximum_tier(self):
        """Deep research requests should use MAXIMUM tier."""
        maximum_queries = [
            "deep research on authentication patterns",
            "deep analysis of the codebase architecture",
            "do a deep dive into the agent orchestration",
        ]
        for query in maximum_queries:
            tier = self.classify_query_tier(query)
            assert (
                tier == self.ModelTier.MAXIMUM
            ), f"'{query}' should route to MAXIMUM tier"

    def test_cross_codebase_analysis_routes_to_maximum_tier(self):
        """Cross-codebase analysis should use MAXIMUM tier."""
        maximum_queries = [
            "cross-codebase analysis of security patterns",
            "compare authentication across repositories",
        ]
        for query in maximum_queries:
            tier = self.classify_query_tier(query)
            assert (
                tier == self.ModelTier.MAXIMUM
            ), f"'{query}' should route to MAXIMUM tier"

    def test_comprehensive_review_routes_to_maximum_tier(self):
        """Comprehensive reviews should use MAXIMUM tier."""
        maximum_queries = [
            "comprehensive review of the API layer",
            "comprehensive analysis of error handling",
            "comprehensive audit of the security controls",
        ]
        for query in maximum_queries:
            tier = self.classify_query_tier(query)
            assert (
                tier == self.ModelTier.MAXIMUM
            ), f"'{query}' should route to MAXIMUM tier"

    def test_architecture_review_routes_to_maximum_tier(self):
        """Architecture reviews should use MAXIMUM tier."""
        maximum_queries = [
            "architecture review of the agent system",
            "architecture design proposal for caching",
        ]
        for query in maximum_queries:
            tier = self.classify_query_tier(query)
            assert (
                tier == self.ModelTier.MAXIMUM
            ), f"'{query}' should route to MAXIMUM tier"

    def test_security_audit_routes_to_maximum_tier(self):
        """Security audits should use MAXIMUM tier."""
        tier = self.classify_query_tier("perform a security audit")
        assert tier == self.ModelTier.MAXIMUM

    def test_threat_model_routes_to_maximum_tier(self):
        """Threat modeling should use MAXIMUM tier."""
        tier = self.classify_query_tier("create a threat model for the API")
        assert tier == self.ModelTier.MAXIMUM


class TestModelSelection:
    """Test model ID selection based on tier."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars):
        """Set up environment and import module."""
        from chat_handler import (
            BEDROCK_MODEL_ID,
            HAIKU_MODEL_ID,
            OPUS_MODEL_ID,
            ModelTier,
            select_model,
        )

        self.ModelTier = ModelTier
        self.select_model = select_model
        self.HAIKU_MODEL_ID = HAIKU_MODEL_ID
        self.BEDROCK_MODEL_ID = BEDROCK_MODEL_ID
        self.OPUS_MODEL_ID = OPUS_MODEL_ID

    def test_select_model_for_simple_query(self):
        """Simple query should select Haiku model."""
        model_id = self.select_model("hello")
        assert model_id == self.HAIKU_MODEL_ID

    def test_select_model_for_code_analysis(self):
        """Code analysis query should select Sonnet model."""
        model_id = self.select_model("explain the code in chat_handler.py")
        assert model_id == self.BEDROCK_MODEL_ID

    def test_select_model_for_deep_research(self):
        """Deep research query should select Opus model."""
        model_id = self.select_model("deep research on security vulnerabilities")
        assert model_id == self.OPUS_MODEL_ID

    def test_select_model_with_explicit_tier_override(self):
        """Explicit tier override should be respected."""
        # Even a simple query should use MAXIMUM if explicitly requested
        model_id = self.select_model("hello", requested_tier=self.ModelTier.MAXIMUM)
        assert model_id == self.OPUS_MODEL_ID

        # Deep research query can be forced to use FAST
        model_id = self.select_model(
            "deep research", requested_tier=self.ModelTier.FAST
        )
        assert model_id == self.HAIKU_MODEL_ID


class TestModelCatalog:
    """Test model catalog and specifications."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars):
        """Set up environment and import module."""
        from chat_handler import MODEL_CATALOG, ModelSpec, ModelTier, get_model_spec

        self.MODEL_CATALOG = MODEL_CATALOG
        self.ModelSpec = ModelSpec
        self.ModelTier = ModelTier
        self.get_model_spec = get_model_spec

    def test_model_catalog_has_three_tiers(self):
        """Model catalog should have models for all three tiers."""
        tiers = {spec.tier for spec in self.MODEL_CATALOG.values()}
        assert self.ModelTier.FAST in tiers
        assert self.ModelTier.ACCURATE in tiers
        assert self.ModelTier.MAXIMUM in tiers

    def test_haiku_model_in_catalog(self):
        """Haiku model should be in catalog."""
        assert "claude-3-haiku" in self.MODEL_CATALOG
        spec = self.MODEL_CATALOG["claude-3-haiku"]
        assert spec.tier == self.ModelTier.FAST
        assert spec.provider == "anthropic"
        assert "classification" in spec.capabilities

    def test_sonnet_model_in_catalog(self):
        """Sonnet model should be in catalog."""
        assert "claude-3-5-sonnet" in self.MODEL_CATALOG
        spec = self.MODEL_CATALOG["claude-3-5-sonnet"]
        assert spec.tier == self.ModelTier.ACCURATE
        assert "code_analysis" in spec.capabilities
        assert "tool_use" in spec.capabilities

    def test_opus_model_in_catalog(self):
        """Opus model should be in catalog."""
        assert "claude-3-5-opus" in self.MODEL_CATALOG
        spec = self.MODEL_CATALOG["claude-3-5-opus"]
        assert spec.tier == self.ModelTier.MAXIMUM
        assert "deep_research" in spec.capabilities
        assert "complex_reasoning" in spec.capabilities

    def test_get_model_spec_by_id(self):
        """Should retrieve model spec by Bedrock inference profile ID."""
        spec = self.get_model_spec("us.anthropic.claude-3-haiku-20240307-v1:0")
        assert spec is not None
        assert spec.tier == self.ModelTier.FAST

    def test_get_model_spec_returns_none_for_unknown(self):
        """Should return None for unknown model IDs."""
        spec = self.get_model_spec("unknown-model-id")
        assert spec is None


class TestPatternMatching:
    """Test pattern matching edge cases."""

    @pytest.fixture(autouse=True)
    def setup(self, chat_env_vars):
        """Set up environment and import module."""
        from chat_handler import ModelTier, classify_query_tier

        self.classify_query_tier = classify_query_tier
        self.ModelTier = ModelTier

    def test_case_insensitive_matching(self):
        """Pattern matching should be case-insensitive."""
        # FAST patterns
        assert self.classify_query_tier("HELLO") == self.ModelTier.FAST
        assert self.classify_query_tier("Hello") == self.ModelTier.FAST

        # MAXIMUM patterns
        assert self.classify_query_tier("DEEP RESEARCH") == self.ModelTier.MAXIMUM
        assert self.classify_query_tier("Deep Research") == self.ModelTier.MAXIMUM

    def test_maximum_patterns_take_priority(self):
        """MAXIMUM patterns should be checked before FAST patterns."""
        # A query that could match both should go to MAXIMUM
        tier = self.classify_query_tier("deep research - thanks in advance")
        assert tier == self.ModelTier.MAXIMUM

    def test_partial_word_matching(self):
        """Patterns should match as expected (word boundaries)."""
        # "hello" at start should match
        assert self.classify_query_tier("hello world") == self.ModelTier.FAST

        # But "othello" should not trigger FAST tier
        tier = self.classify_query_tier("tell me about othello")
        assert tier != self.ModelTier.FAST

    def test_empty_query_defaults_to_accurate(self):
        """Empty query should default to ACCURATE tier."""
        tier = self.classify_query_tier("")
        assert tier == self.ModelTier.ACCURATE

    def test_whitespace_only_defaults_to_accurate(self):
        """Whitespace-only query should default to ACCURATE tier."""
        tier = self.classify_query_tier("   ")
        assert tier == self.ModelTier.ACCURATE
