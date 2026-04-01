"""
Project Aura - Runtime-to-Code Correlator

GraphRAG-powered root cause analysis that traces runtime security
events back to source code and generates autonomous remediation.

Based on ADR-083: Runtime Agent Security Platform
"""

from .correlator import (
    CorrelationChain,
    CorrelationResult,
    RuntimeCodeCorrelator,
    get_code_correlator,
    reset_code_correlator,
)
from .graph_tracer import CallGraphPath, GraphTracer, TraceResult
from .remediation import (
    PatchCandidate,
    RemediationOrchestrator,
    RemediationPlan,
    RemediationStatus,
)
from .vector_matcher import MatchResult, VectorMatcher, VulnerabilityMatch

__all__ = [
    # Correlator
    "RuntimeCodeCorrelator",
    "CorrelationResult",
    "CorrelationChain",
    "get_code_correlator",
    "reset_code_correlator",
    # Graph Tracer
    "GraphTracer",
    "CallGraphPath",
    "TraceResult",
    # Vector Matcher
    "VectorMatcher",
    "VulnerabilityMatch",
    "MatchResult",
    # Remediation
    "RemediationOrchestrator",
    "RemediationPlan",
    "PatchCandidate",
    "RemediationStatus",
]
