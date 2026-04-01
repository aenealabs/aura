"""Tests for documentation exceptions (ADR-056)."""

import platform

import pytest

from src.services.documentation.exceptions import (
    CacheError,
    DiagramGenerationError,
    DocumentationAgentError,
    GraphTraversalError,
    InsufficientDataError,
    LLMGenerationError,
    ReportGenerationError,
)

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestDocumentationAgentError:
    """Tests for base DocumentationAgentError."""

    def test_basic_error(self):
        """Test basic error creation."""
        error = DocumentationAgentError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"

    def test_error_with_details(self):
        """Test error with additional details."""
        error = DocumentationAgentError(
            "Failed to process",
            details={"step": "analysis", "reason": "timeout"},
        )
        assert error.message == "Failed to process"
        assert error.details["step"] == "analysis"
        assert error.details["reason"] == "timeout"

    def test_error_inheritance(self):
        """Test that DocumentationAgentError inherits from Exception."""
        error = DocumentationAgentError("Test error")
        assert isinstance(error, Exception)


class TestGraphTraversalError:
    """Tests for GraphTraversalError."""

    def test_basic_creation(self):
        """Test basic GraphTraversalError creation."""
        error = GraphTraversalError("Failed to traverse graph")
        assert "traverse" in str(error).lower()
        assert error.partial_results == []  # Defaults to empty list
        assert error.failed_query is None

    def test_with_partial_results(self):
        """Test GraphTraversalError with partial results."""
        partial = [{"id": "node-1"}, {"id": "node-2"}]
        error = GraphTraversalError(
            "Incomplete traversal",
            partial_results=partial,
        )
        assert error.partial_results == partial
        assert len(error.partial_results) == 2
        assert error.has_partial_results is True

    def test_with_failed_query(self):
        """Test with failed query."""
        error = GraphTraversalError(
            "Query failed", failed_query="g.V().has('type', 'class').limit(100)"
        )
        assert error.failed_query is not None
        assert "g.V()" in error.failed_query

    def test_inheritance(self):
        """Test that GraphTraversalError inherits from DocumentationAgentError."""
        error = GraphTraversalError("Test")
        assert isinstance(error, DocumentationAgentError)


class TestInsufficientDataError:
    """Tests for InsufficientDataError."""

    def test_basic_creation(self):
        """Test basic InsufficientDataError creation."""
        error = InsufficientDataError(
            "Not enough code context",
            confidence=0.30,
            threshold=0.45,
        )
        assert "context" in str(error).lower()
        assert error.confidence == 0.30
        assert error.threshold == 0.45

    def test_with_missing_data(self):
        """Test with missing data description."""
        error = InsufficientDataError(
            message="Not enough data",
            confidence=0.3,
            threshold=0.45,
            missing_data="Need at least 10 code entities",
        )
        assert error.missing_data == "Need at least 10 code entities"
        assert "Need at least" in str(error)

    def test_gap_calculation(self):
        """Test confidence_gap property calculation."""
        error = InsufficientDataError(
            "Low confidence",
            confidence=0.30,
            threshold=0.50,
        )
        assert error.confidence_gap == pytest.approx(0.20)  # threshold - confidence

    def test_inheritance(self):
        """Test that InsufficientDataError inherits from DocumentationAgentError."""
        error = InsufficientDataError(
            "Test",
            confidence=0.3,
            threshold=0.5,
        )
        assert isinstance(error, DocumentationAgentError)


class TestDiagramGenerationError:
    """Tests for DiagramGenerationError."""

    def test_basic_creation(self):
        """Test basic DiagramGenerationError creation."""
        error = DiagramGenerationError(
            "Failed to generate diagram",
            diagram_type="architecture",
        )
        assert "generate" in str(error).lower()
        assert error.diagram_type == "architecture"

    def test_with_component_errors(self):
        """Test DiagramGenerationError with component errors."""
        component_errors = {"comp-1": "Invalid node", "comp-2": "Missing connection"}
        error = DiagramGenerationError(
            "Multiple failures", component_errors=component_errors
        )
        assert len(error.failed_components) == 2
        assert "comp-1" in error.failed_components

    def test_with_partial_diagram(self):
        """Test with partial diagram."""
        error = DiagramGenerationError(
            "Partial failure", partial_diagram="graph TB\n  A --> B"
        )
        assert error.has_partial_diagram is True
        assert "graph TB" in error.partial_diagram

    def test_default_diagram_type(self):
        """Test default diagram type."""
        error = DiagramGenerationError("Failed")
        assert error.diagram_type is None

    def test_inheritance(self):
        """Test that DiagramGenerationError inherits from DocumentationAgentError."""
        error = DiagramGenerationError("Test")
        assert isinstance(error, DocumentationAgentError)


class TestReportGenerationError:
    """Tests for ReportGenerationError."""

    def test_basic_creation(self):
        """Test basic ReportGenerationError creation."""
        error = ReportGenerationError(
            "Failed to generate report",
            section="executive_summary",
        )
        assert "report" in str(error).lower()
        assert error.section == "executive_summary"

    def test_with_partial_report(self):
        """Test with partial report."""
        error = ReportGenerationError(
            "Partial failure", partial_report="# Report\n\n## Summary"
        )
        assert error.has_partial_report is True

    def test_default_section(self):
        """Test default section value."""
        error = ReportGenerationError("Failed")
        assert error.section is None

    def test_inheritance(self):
        """Test that ReportGenerationError inherits from DocumentationAgentError."""
        error = ReportGenerationError("Test")
        assert isinstance(error, DocumentationAgentError)


class TestCacheError:
    """Tests for CacheError."""

    def test_basic_creation(self):
        """Test basic CacheError creation."""
        error = CacheError(
            "Cache operation failed",
            operation="get",
            cache_tier="redis",
        )
        assert "cache" in str(error).lower()
        assert error.operation == "get"
        assert error.cache_tier == "redis"

    def test_default_values(self):
        """Test CacheError default values."""
        error = CacheError("Failed")
        assert error.operation is None
        assert error.cache_tier is None

    def test_all_cache_operations(self):
        """Test CacheError with different operations."""
        operations = ["get", "set", "delete"]
        for op in operations:
            error = CacheError(f"Failed to {op}", operation=op)
            assert error.operation == op

    def test_all_cache_tiers(self):
        """Test CacheError with different cache tiers."""
        tiers = ["memory", "redis", "s3"]
        for tier in tiers:
            error = CacheError(f"Failed in {tier}", cache_tier=tier)
            assert error.cache_tier == tier

    def test_with_cache_key(self):
        """Test with cache key."""
        error = CacheError("Cache failed", cache_key="doc:repo-123")
        assert error.cache_key == "doc:repo-123"

    def test_inheritance(self):
        """Test that CacheError inherits from DocumentationAgentError."""
        error = CacheError("Test")
        assert isinstance(error, DocumentationAgentError)


class TestLLMGenerationError:
    """Tests for LLMGenerationError."""

    def test_basic_creation(self):
        """Test basic creation."""
        error = LLMGenerationError("LLM failed")
        assert error.message == "LLM failed"
        assert error.model is None
        assert error.is_rate_limited is False
        assert error.is_context_exceeded is False

    def test_with_model(self):
        """Test with model info."""
        error = LLMGenerationError(
            "Model failed", model="claude-3-sonnet", prompt_tokens=4096
        )
        assert error.model == "claude-3-sonnet"
        assert error.prompt_tokens == 4096

    def test_rate_limited(self):
        """Test rate limited error."""
        error = LLMGenerationError("Rate limited", is_rate_limited=True)
        assert error.is_rate_limited is True
        assert error.is_retryable is True

    def test_context_exceeded(self):
        """Test context exceeded error."""
        error = LLMGenerationError("Context exceeded", is_context_exceeded=True)
        assert error.is_context_exceeded is True
        assert error.is_retryable is False

    def test_inheritance(self):
        """Test inheritance from DocumentationAgentError."""
        error = LLMGenerationError("Test")
        assert isinstance(error, DocumentationAgentError)


class TestExceptionChaining:
    """Tests for exception chaining patterns."""

    def test_raise_from_pattern(self):
        """Test raising exception from another exception."""
        original = ValueError("Original error")
        try:
            try:
                raise original
            except ValueError as e:
                raise GraphTraversalError("Wrapped") from e
        except GraphTraversalError as wrapped:
            assert wrapped.__cause__ is original

    def test_exception_details_preserved(self):
        """Test that exception details are preserved."""
        error = GraphTraversalError(
            "Traversal failed",
            partial_results=[{"id": "node-1"}],
            details={"query": "MATCH (n) RETURN n", "timeout": True},
        )
        assert len(error.partial_results) == 1
        assert error.details["query"] == "MATCH (n) RETURN n"
        assert error.details["timeout"] is True
