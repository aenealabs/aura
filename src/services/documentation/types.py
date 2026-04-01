"""
Documentation Agent Type Definitions
=====================================

Type definitions for the Documentation Agent service.
ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ConfidenceLevel(Enum):
    """Confidence level thresholds for documentation accuracy.

    Thresholds (from ADR-056):
    - HIGH: >= 0.85 - High confidence, minimal manual review needed
    - MEDIUM: >= 0.65 - Moderate confidence, some review recommended
    - LOW: >= 0.45 - Low confidence, thorough review required
    - UNCERTAIN: < 0.45 - Uncertain, treat as draft requiring validation
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        """Convert a numeric confidence score to a ConfidenceLevel.

        Args:
            score: Confidence score between 0.0 and 1.0

        Returns:
            ConfidenceLevel corresponding to the score
        """
        if score >= 0.85:
            return cls.HIGH
        elif score >= 0.65:
            return cls.MEDIUM
        elif score >= 0.45:
            return cls.LOW
        else:
            return cls.UNCERTAIN


class DiagramType(Enum):
    """Types of diagrams that can be generated."""

    ARCHITECTURE = "architecture"
    DATA_FLOW = "data_flow"
    DEPENDENCY = "dependency"
    SEQUENCE = "sequence"
    COMPONENT = "component"


class DataFlowDirection(Enum):
    """Direction of data flow between components."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class DataClassification(Enum):
    """Data classification levels for data flow analysis."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PII = "pii"
    SENSITIVE = "sensitive"


@dataclass
class ServiceBoundary:
    """Represents a detected service boundary from code analysis.

    A service boundary is a logical grouping of code entities that form
    a cohesive service, detected using community detection algorithms
    (Louvain) on the code call graph.

    Attributes:
        boundary_id: Unique identifier for this boundary
        name: Human-readable name for the service
        description: Generated description of the service's purpose
        node_ids: List of code entity IDs contained in this boundary
        confidence: Confidence score (0.0-1.0) in boundary detection
        edges_internal: Number of edges within the boundary
        edges_external: Number of edges crossing the boundary
        entry_points: List of public entry point entity IDs
        metadata: Additional metadata for the boundary
    """

    boundary_id: str
    name: str
    description: str
    node_ids: list[str]
    confidence: float
    edges_internal: int = 0
    edges_external: int = 0
    entry_points: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get the confidence level for this boundary."""
        return ConfidenceLevel.from_score(self.confidence)

    @property
    def modularity_ratio(self) -> float:
        """Calculate the modularity ratio (internal/total edges).

        A higher ratio indicates a more cohesive service boundary.
        """
        total = self.edges_internal + self.edges_external
        if total == 0:
            return 0.0
        return self.edges_internal / total


@dataclass
class DataFlow:
    """Represents a data flow between system components.

    Attributes:
        flow_id: Unique identifier for this data flow
        source_id: Entity ID of the data source
        target_id: Entity ID of the data target
        flow_type: Type of data flow (sync, async, batch, stream)
        direction: Direction of the data flow
        data_types: List of data types being transferred
        protocol: Communication protocol (http, grpc, sqs, etc.)
        classification: Data classification level
        confidence: Confidence in the data flow detection
        metadata: Additional metadata
    """

    flow_id: str
    source_id: str
    target_id: str
    flow_type: str = "synchronous"
    direction: DataFlowDirection = DataFlowDirection.OUTBOUND
    data_types: list[str] = field(default_factory=list)
    protocol: str = "unknown"
    classification: DataClassification = DataClassification.INTERNAL
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass
class DiagramComponent:
    """A component within a generated diagram.

    Attributes:
        component_id: Unique identifier for this component
        label: Display label for the component
        component_type: Type of component (service, database, queue, etc.)
        entity_ids: Code entity IDs that map to this component
        confidence: Confidence in component detection
        style: Visual style hints for rendering
        metadata: Additional metadata
    """

    component_id: str
    label: str
    component_type: str
    entity_ids: list[str] = field(default_factory=list)
    confidence: float = 1.0
    style: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass
class DiagramResult:
    """Result of diagram generation.

    Attributes:
        diagram_type: Type of diagram generated
        mermaid_code: Mermaid.js code for the diagram
        components: List of components in the diagram
        connections: List of connections as (source, target, label) tuples
        confidence: Overall confidence in the diagram
        warnings: List of warnings during generation
        metadata: Additional metadata
    """

    diagram_type: DiagramType
    mermaid_code: str
    components: list[DiagramComponent] = field(default_factory=list)
    connections: list[tuple[str, str, str]] = field(default_factory=list)
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get the confidence level for this diagram."""
        return ConfidenceLevel.from_score(self.confidence)


@dataclass
class ReportSection:
    """A section of a technical report.

    Attributes:
        title: Section title
        content: Markdown content of the section
        confidence: Confidence in this section's accuracy
        source_entities: Entity IDs that contributed to this section
        metadata: Additional metadata
    """

    title: str
    content: str
    confidence: float = 1.0
    source_entities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass
class TechnicalReport:
    """Generated technical documentation report.

    Attributes:
        title: Report title
        executive_summary: Brief executive summary
        sections: List of report sections
        generated_at: Timestamp when report was generated
        confidence: Overall confidence in the report
        repository_id: Repository this report is for
        metadata: Additional metadata
    """

    title: str
    executive_summary: str
    sections: list[ReportSection]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = 1.0
    repository_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get the confidence level for this report."""
        return ConfidenceLevel.from_score(self.confidence)

    def to_markdown(self) -> str:
        """Convert the report to Markdown format.

        Returns:
            Markdown string representation of the report
        """
        lines = [
            f"# {self.title}",
            "",
            f"**Generated:** {self.generated_at.isoformat()}",
            f"**Confidence:** {self.confidence:.1%} ({self.confidence_level.value})",
            "",
            "## Executive Summary",
            "",
            self.executive_summary,
            "",
        ]

        for section in self.sections:
            lines.extend(
                [
                    f"## {section.title}",
                    "",
                    f"*Confidence: {section.confidence:.1%}*",
                    "",
                    section.content,
                    "",
                ]
            )

        return "\n".join(lines)


@dataclass
class DocumentationRequest:
    """Request to generate documentation.

    Attributes:
        repository_id: Repository to generate documentation for
        diagram_types: List of diagram types to generate
        include_report: Whether to include technical report
        include_data_flow: Whether to include data flow analysis
        max_services: Maximum number of services to detect
        min_confidence: Minimum confidence threshold
        metadata: Additional request metadata
    """

    repository_id: str
    diagram_types: list[DiagramType] = field(
        default_factory=lambda: [DiagramType.ARCHITECTURE, DiagramType.DATA_FLOW]
    )
    include_report: bool = True
    include_data_flow: bool = True
    max_services: int = 20
    min_confidence: float = 0.45
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationProgress:
    """Progress update during documentation generation.

    Attributes:
        phase: Current phase of generation
        progress: Progress percentage (0-100)
        message: Human-readable status message
        current_step: Current step number
        total_steps: Total number of steps
        metadata: Additional progress metadata
    """

    phase: str
    progress: float
    message: str
    current_step: int = 0
    total_steps: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate progress is in valid range."""
        if not 0.0 <= self.progress <= 100.0:
            raise ValueError(
                f"Progress must be between 0.0 and 100.0, got {self.progress}"
            )


@dataclass
class DocumentationResult:
    """Result of documentation generation.

    Attributes:
        job_id: Unique job identifier
        repository_id: Repository documentation was generated for
        diagrams: List of generated diagrams
        report: Generated technical report (optional)
        service_boundaries: Detected service boundaries
        data_flows: Detected data flows
        confidence: Overall confidence in the documentation
        generated_at: Timestamp when documentation was generated
        generation_time_ms: Time taken to generate in milliseconds
        warnings: List of warnings during generation
        metadata: Additional result metadata
    """

    job_id: str
    repository_id: str
    diagrams: list[DiagramResult] = field(default_factory=list)
    report: TechnicalReport | None = None
    service_boundaries: list[ServiceBoundary] = field(default_factory=list)
    data_flows: list[DataFlow] = field(default_factory=list)
    confidence: float = 1.0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    generation_time_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get the confidence level for this result."""
        return ConfidenceLevel.from_score(self.confidence)
