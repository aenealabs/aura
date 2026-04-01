"""
Test fixtures for runtime-to-code correlation services.

Provides shared fixtures used across test_graph_tracer, test_vector_matcher,
test_remediation, and test_correlator modules.
"""

from datetime import datetime, timezone

import pytest

from src.services.runtime_security.correlation import (
    RuntimeCodeCorrelator,
    reset_code_correlator,
)
from src.services.runtime_security.correlation.graph_tracer import GraphTracer
from src.services.runtime_security.correlation.remediation import (
    RemediationOrchestrator,
)
from src.services.runtime_security.correlation.vector_matcher import VectorMatcher


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all correlation singletons before and after each test."""
    reset_code_correlator()
    yield
    reset_code_correlator()


@pytest.fixture
def now_utc() -> datetime:
    """Consistent UTC timestamp for deterministic tests."""
    return datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def mock_graph_tracer() -> GraphTracer:
    """GraphTracer in mock mode with pre-loaded paths for coder-agent."""
    tracer = GraphTracer(use_mock=True, max_depth=10, max_paths=5)
    tracer.add_mock_path(
        agent_id="coder-agent",
        tool_name="write_file",
        source_file="src/services/api/handler.py",
        source_line_start=42,
        source_line_end=58,
    )
    tracer.add_mock_path(
        agent_id="coder-agent",
        tool_name="write_file",
        source_file="src/services/api/routes.py",
        source_line_start=10,
        source_line_end=25,
        nodes=["coder-agent", "write_file", "routes.py", "handler.py"],
        edges=["CALLS", "DEPENDS_ON", "DEFINED_IN"],
    )
    return tracer


@pytest.fixture
def mock_vector_matcher() -> VectorMatcher:
    """VectorMatcher in mock mode with pre-loaded vulnerability patterns."""
    matcher = VectorMatcher(use_mock=True)
    matcher.add_mock_pattern(
        vulnerability_id="vuln-sql-001",
        vulnerability_type="SQL Injection",
        description="SQL query constructed with string concatenation",
        keywords=["sql", "injection", "query", "concatenation", "string"],
        severity="critical",
        cwe_id="CWE-89",
        source_file="src/services/api/handler.py",
        source_line=42,
        remediation_hint="Use parameterized queries",
    )
    matcher.add_mock_pattern(
        vulnerability_id="vuln-xss-001",
        vulnerability_type="Cross-Site Scripting",
        description="User input rendered without sanitization",
        keywords=["xss", "script", "input", "sanitization", "html"],
        severity="high",
        cwe_id="CWE-79",
        remediation_hint="Sanitize user input before rendering",
    )
    return matcher


@pytest.fixture
def mock_remediation() -> RemediationOrchestrator:
    """RemediationOrchestrator with no real agents."""
    return RemediationOrchestrator()


@pytest.fixture
def correlator(
    mock_graph_tracer: GraphTracer,
    mock_vector_matcher: VectorMatcher,
    mock_remediation: RemediationOrchestrator,
) -> RuntimeCodeCorrelator:
    """RuntimeCodeCorrelator wired to all 3 mock services with auto_remediate enabled."""
    return RuntimeCodeCorrelator(
        graph_tracer=mock_graph_tracer,
        vector_matcher=mock_vector_matcher,
        remediation=mock_remediation,
        auto_remediate=True,
    )
