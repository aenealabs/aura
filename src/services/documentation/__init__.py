"""
Documentation Agent Services
============================

Automated documentation generation using GraphRAG analysis.
ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.

This module provides:
- Service boundary detection using Louvain community algorithm
- Architecture and data flow diagram generation (Mermaid.js)
- Technical report generation with confidence scoring
- 3-tier caching for performance optimization
"""

from src.services.documentation.exceptions import (
    CacheError,
    DiagramGenerationError,
    DocumentationAgentError,
    GraphTraversalError,
    InsufficientDataError,
    LLMGenerationError,
    ReportGenerationError,
)
from src.services.documentation.types import (
    ConfidenceLevel,
    DataFlow,
    DiagramComponent,
    DiagramResult,
    DiagramType,
    DocumentationRequest,
    DocumentationResult,
    GenerationProgress,
    ReportSection,
    ServiceBoundary,
    TechnicalReport,
)

__all__ = [
    # Types
    "ConfidenceLevel",
    "DiagramType",
    "ServiceBoundary",
    "DataFlow",
    "DiagramComponent",
    "DiagramResult",
    "ReportSection",
    "TechnicalReport",
    "DocumentationRequest",
    "DocumentationResult",
    "GenerationProgress",
    # Exceptions
    "DocumentationAgentError",
    "GraphTraversalError",
    "InsufficientDataError",
    "DiagramGenerationError",
    "ReportGenerationError",
    "CacheError",
    "LLMGenerationError",
]
