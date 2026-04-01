"""Tests for documentation types and data classes (ADR-056)."""

import platform

import pytest

from src.services.documentation.types import (
    ConfidenceLevel,
    DataClassification,
    DataFlow,
    DataFlowDirection,
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

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_confidence_level_values(self):
        """Test confidence level enum values."""
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.LOW.value == "low"
        assert ConfidenceLevel.UNCERTAIN.value == "uncertain"

    def test_from_score_high(self):
        """Test high confidence from score."""
        assert ConfidenceLevel.from_score(0.85) == ConfidenceLevel.HIGH
        assert ConfidenceLevel.from_score(0.90) == ConfidenceLevel.HIGH
        assert ConfidenceLevel.from_score(1.0) == ConfidenceLevel.HIGH

    def test_from_score_medium(self):
        """Test medium confidence from score."""
        assert ConfidenceLevel.from_score(0.65) == ConfidenceLevel.MEDIUM
        assert ConfidenceLevel.from_score(0.75) == ConfidenceLevel.MEDIUM
        assert ConfidenceLevel.from_score(0.84) == ConfidenceLevel.MEDIUM

    def test_from_score_low(self):
        """Test low confidence from score."""
        assert ConfidenceLevel.from_score(0.45) == ConfidenceLevel.LOW
        assert ConfidenceLevel.from_score(0.55) == ConfidenceLevel.LOW
        assert ConfidenceLevel.from_score(0.64) == ConfidenceLevel.LOW

    def test_from_score_uncertain(self):
        """Test uncertain confidence from score."""
        assert ConfidenceLevel.from_score(0.0) == ConfidenceLevel.UNCERTAIN
        assert ConfidenceLevel.from_score(0.30) == ConfidenceLevel.UNCERTAIN
        assert ConfidenceLevel.from_score(0.44) == ConfidenceLevel.UNCERTAIN


class TestDiagramType:
    """Tests for DiagramType enum."""

    def test_diagram_type_values(self):
        """Test diagram type enum values."""
        assert DiagramType.ARCHITECTURE.value == "architecture"
        assert DiagramType.DATA_FLOW.value == "data_flow"
        assert DiagramType.DEPENDENCY.value == "dependency"
        assert DiagramType.SEQUENCE.value == "sequence"
        assert DiagramType.COMPONENT.value == "component"


class TestDataFlowDirection:
    """Tests for DataFlowDirection enum."""

    def test_data_flow_direction_values(self):
        """Test data flow direction enum values."""
        assert DataFlowDirection.INBOUND.value == "inbound"
        assert DataFlowDirection.OUTBOUND.value == "outbound"
        assert DataFlowDirection.BIDIRECTIONAL.value == "bidirectional"


class TestDataClassification:
    """Tests for DataClassification enum."""

    def test_data_classification_values(self):
        """Test data classification enum values."""
        assert DataClassification.PUBLIC.value == "public"
        assert DataClassification.INTERNAL.value == "internal"
        assert DataClassification.CONFIDENTIAL.value == "confidential"
        assert DataClassification.PII.value == "pii"
        assert DataClassification.SENSITIVE.value == "sensitive"


class TestServiceBoundary:
    """Tests for ServiceBoundary dataclass."""

    def test_service_boundary_creation(self):
        """Test ServiceBoundary creation."""
        boundary = ServiceBoundary(
            boundary_id="svc-1",
            name="UserService",
            description="User management service",
            node_ids=["node-1", "node-2"],
            confidence=0.85,
        )
        assert boundary.boundary_id == "svc-1"
        assert boundary.name == "UserService"
        assert len(boundary.node_ids) == 2
        assert boundary.confidence == 0.85
        assert boundary.entry_points == []

    def test_service_boundary_with_all_fields(self):
        """Test ServiceBoundary with all fields."""
        boundary = ServiceBoundary(
            boundary_id="svc-2",
            name="AuthService",
            description="Handles authentication and authorization",
            node_ids=["auth-1", "auth-2", "auth-3"],
            confidence=0.90,
            edges_internal=10,
            edges_external=3,
            entry_points=["login", "logout", "verify_token"],
            metadata={"complexity": "medium"},
        )
        assert boundary.description == "Handles authentication and authorization"
        assert len(boundary.entry_points) == 3
        assert boundary.edges_internal == 10
        assert boundary.edges_external == 3

    def test_service_boundary_confidence_level(self):
        """Test ServiceBoundary confidence_level property."""
        boundary = ServiceBoundary(
            boundary_id="svc-3",
            name="DataService",
            description="Data service",
            node_ids=["d1", "d2"],
            confidence=0.75,
        )
        assert boundary.confidence_level == ConfidenceLevel.MEDIUM

    def test_service_boundary_modularity_ratio(self):
        """Test ServiceBoundary modularity_ratio property."""
        boundary = ServiceBoundary(
            boundary_id="svc-4",
            name="Service",
            description="Test",
            node_ids=["n1"],
            confidence=0.80,
            edges_internal=8,
            edges_external=2,
        )
        assert boundary.modularity_ratio == 0.8

    def test_service_boundary_modularity_ratio_zero(self):
        """Test ServiceBoundary modularity_ratio with no edges."""
        boundary = ServiceBoundary(
            boundary_id="svc-5",
            name="Service",
            description="Test",
            node_ids=["n1"],
            confidence=0.80,
            edges_internal=0,
            edges_external=0,
        )
        assert boundary.modularity_ratio == 0.0

    def test_service_boundary_invalid_confidence(self):
        """Test ServiceBoundary rejects invalid confidence."""
        with pytest.raises(ValueError):
            ServiceBoundary(
                boundary_id="svc-6",
                name="Invalid",
                description="Test",
                node_ids=[],
                confidence=1.5,  # Invalid
            )


class TestDataFlow:
    """Tests for DataFlow dataclass."""

    def test_data_flow_creation(self):
        """Test DataFlow creation."""
        flow = DataFlow(
            flow_id="flow-1",
            source_id="service-a",
            target_id="database-1",
        )
        assert flow.flow_id == "flow-1"
        assert flow.source_id == "service-a"
        assert flow.target_id == "database-1"
        assert flow.flow_type == "synchronous"
        assert flow.direction == DataFlowDirection.OUTBOUND

    def test_data_flow_with_all_fields(self):
        """Test DataFlow with all fields."""
        flow = DataFlow(
            flow_id="flow-2",
            source_id="api",
            target_id="queue",
            flow_type="async",
            direction=DataFlowDirection.OUTBOUND,
            data_types=["OrderEvent", "PaymentEvent"],
            protocol="sqs",
            classification=DataClassification.CONFIDENTIAL,
            confidence=0.90,
        )
        assert flow.flow_type == "async"
        assert len(flow.data_types) == 2
        assert flow.classification == DataClassification.CONFIDENTIAL

    def test_data_flow_invalid_confidence(self):
        """Test DataFlow rejects invalid confidence."""
        with pytest.raises(ValueError):
            DataFlow(
                flow_id="flow-3",
                source_id="a",
                target_id="b",
                confidence=-0.1,  # Invalid
            )


class TestDiagramComponent:
    """Tests for DiagramComponent dataclass."""

    def test_diagram_component_creation(self):
        """Test DiagramComponent creation."""
        component = DiagramComponent(
            component_id="comp-1",
            label="API Gateway",
            component_type="service",
        )
        assert component.component_id == "comp-1"
        assert component.label == "API Gateway"
        assert component.component_type == "service"
        assert component.entity_ids == []

    def test_diagram_component_with_all_fields(self):
        """Test DiagramComponent with all fields."""
        component = DiagramComponent(
            component_id="comp-2",
            label="Database",
            component_type="database",
            entity_ids=["entity-1", "entity-2"],
            confidence=0.85,
            style={"fill": "#blue"},
            metadata={"type": "postgresql"},
        )
        assert len(component.entity_ids) == 2
        assert component.metadata["type"] == "postgresql"


class TestDiagramResult:
    """Tests for DiagramResult dataclass."""

    def test_diagram_result_creation(self):
        """Test DiagramResult creation."""
        result = DiagramResult(
            diagram_type=DiagramType.ARCHITECTURE,
            mermaid_code="graph TB\n  A[Service] --> B[Database]",
            confidence=0.82,
        )
        assert result.diagram_type == DiagramType.ARCHITECTURE
        assert "graph TB" in result.mermaid_code
        assert result.confidence == 0.82
        assert result.warnings == []

    def test_diagram_result_confidence_level(self):
        """Test DiagramResult confidence_level property."""
        high = DiagramResult(
            diagram_type=DiagramType.DATA_FLOW,
            mermaid_code="flowchart LR",
            confidence=0.90,
        )
        assert high.confidence_level == ConfidenceLevel.HIGH

        low = DiagramResult(
            diagram_type=DiagramType.DATA_FLOW,
            mermaid_code="flowchart LR",
            confidence=0.50,
        )
        assert low.confidence_level == ConfidenceLevel.LOW


class TestReportSection:
    """Tests for ReportSection dataclass."""

    def test_report_section_creation(self):
        """Test ReportSection creation."""
        section = ReportSection(
            title="Executive Summary",
            content="This is a summary of the architecture.",
            confidence=0.88,
        )
        assert section.title == "Executive Summary"
        assert "summary" in section.content.lower()
        assert section.confidence == 0.88
        assert section.source_entities == []


class TestTechnicalReport:
    """Tests for TechnicalReport dataclass."""

    def test_technical_report_creation(self):
        """Test TechnicalReport creation."""
        report = TechnicalReport(
            title="Architecture Report",
            executive_summary="Overview of architecture",
            sections=[],
            confidence=0.80,
            repository_id="repo-123",
        )
        assert report.title == "Architecture Report"
        assert report.confidence == 0.80
        assert report.sections == []

    def test_technical_report_with_sections(self):
        """Test TechnicalReport with sections."""
        section1 = ReportSection(
            title="Overview",
            content="Architecture overview",
            confidence=0.85,
        )
        section2 = ReportSection(
            title="Security",
            content="Security considerations",
            confidence=0.75,
        )
        report = TechnicalReport(
            title="Report",
            executive_summary="Summary",
            sections=[section1, section2],
            confidence=0.80,
            repository_id="repo-456",
        )
        assert len(report.sections) == 2

    def test_technical_report_to_markdown(self):
        """Test TechnicalReport to_markdown method."""
        section = ReportSection(
            title="Overview",
            content="Content here",
            confidence=0.85,
        )
        report = TechnicalReport(
            title="Test Report",
            executive_summary="Summary text",
            sections=[section],
            confidence=0.82,
            repository_id="repo-789",
        )
        md = report.to_markdown()
        assert "# Test Report" in md
        assert "Summary text" in md
        assert "## Overview" in md


class TestDocumentationRequest:
    """Tests for DocumentationRequest dataclass."""

    def test_documentation_request_creation(self):
        """Test DocumentationRequest creation with defaults."""
        request = DocumentationRequest(
            repository_id="repo-123",
        )
        assert request.repository_id == "repo-123"
        assert DiagramType.ARCHITECTURE in request.diagram_types
        assert DiagramType.DATA_FLOW in request.diagram_types
        assert request.include_report is True
        assert request.max_services == 20
        assert request.min_confidence == 0.45

    def test_documentation_request_custom(self):
        """Test DocumentationRequest with custom values."""
        request = DocumentationRequest(
            repository_id="repo-456",
            diagram_types=[DiagramType.ARCHITECTURE],
            include_report=False,
            max_services=10,
            min_confidence=0.65,
        )
        assert len(request.diagram_types) == 1
        assert request.include_report is False
        assert request.max_services == 10


class TestGenerationProgress:
    """Tests for GenerationProgress dataclass."""

    def test_generation_progress_creation(self):
        """Test GenerationProgress creation."""
        progress = GenerationProgress(
            phase="analyzing",
            progress=50.0,
            message="Analyzing code structure",
            current_step=2,
            total_steps=4,
        )
        assert progress.phase == "analyzing"
        assert progress.progress == 50.0
        assert progress.current_step == 2
        assert progress.total_steps == 4

    def test_generation_progress_invalid(self):
        """Test GenerationProgress rejects invalid progress."""
        with pytest.raises(ValueError):
            GenerationProgress(
                phase="test",
                progress=150.0,  # Invalid
                message="Test",
            )


class TestDocumentationResult:
    """Tests for DocumentationResult dataclass."""

    def test_documentation_result_creation(self):
        """Test DocumentationResult creation."""
        result = DocumentationResult(
            job_id="job-abc123",
            repository_id="repo-456",
            confidence=0.78,
        )
        assert result.job_id == "job-abc123"
        assert result.repository_id == "repo-456"
        assert result.confidence == 0.78
        assert result.report is None
        assert result.warnings == []
        assert result.diagrams == []

    def test_documentation_result_with_diagrams(self):
        """Test DocumentationResult with diagrams."""
        diagram = DiagramResult(
            diagram_type=DiagramType.ARCHITECTURE,
            mermaid_code="graph TB",
            confidence=0.85,
        )
        result = DocumentationResult(
            job_id="job-xyz",
            repository_id="repo-789",
            diagrams=[diagram],
            confidence=0.82,
        )
        assert len(result.diagrams) == 1

    def test_documentation_result_confidence_level(self):
        """Test DocumentationResult confidence_level property."""
        result = DocumentationResult(
            job_id="job-1",
            repository_id="repo-1",
            confidence=0.90,
        )
        assert result.confidence_level == ConfidenceLevel.HIGH
