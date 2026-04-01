"""
Tests for ReportGenerator.

ADR-056: Documentation Agent Testing Infrastructure (Issue #175)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.services.documentation.exceptions import (
    LLMGenerationError,
    ReportGenerationError,
)
from src.services.documentation.report_generator import (
    ReportGenerator,
    create_report_generator,
)
from src.services.documentation.types import (
    DataClassification,
    DataFlow,
    DiagramResult,
    DiagramType,
    ServiceBoundary,
    TechnicalReport,
)

# NOTE: Forked mode disabled for this test file to ensure coverage tracking works.
# The report_generator module doesn't have state pollution issues that require isolation.


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_llm():
    """Create a mock LLM client."""
    llm = AsyncMock()
    llm.generate = AsyncMock(
        return_value="This system handles user authentication and data processing."
    )
    return llm


@pytest.fixture
def sample_boundaries() -> list[ServiceBoundary]:
    """Create sample service boundaries for testing."""
    return [
        ServiceBoundary(
            boundary_id="svc-001",
            name="AuthService",
            node_ids=["auth.py", "tokens.py", "session.py"],
            confidence=0.85,
            description="Handles user authentication and session management",
            entry_points=["login()", "logout()", "refresh_token()"],
            edges_internal=5,
            edges_external=3,
        ),
        ServiceBoundary(
            boundary_id="svc-002",
            name="DataService",
            node_ids=["data.py", "models.py"],
            confidence=0.72,
            description="Manages data persistence and retrieval",
            entry_points=["get_data()", "save_data()"],
            edges_internal=3,
            edges_external=2,
        ),
        ServiceBoundary(
            boundary_id="svc-003",
            name="APIGateway",
            node_ids=["api.py", "routes.py", "middleware.py", "handlers.py"],
            confidence=0.55,
            description="API routing and request handling",
            entry_points=[],
            edges_internal=2,
            edges_external=8,
        ),
    ]


@pytest.fixture
def sample_data_flows() -> list[DataFlow]:
    """Create sample data flows for testing."""
    return [
        DataFlow(
            flow_id="flow-001",
            source_id="AuthService",
            target_id="DataService",
            flow_type="function_call",
            protocol="internal",
            classification=DataClassification.INTERNAL,
            confidence=0.9,
        ),
        DataFlow(
            flow_id="flow-002",
            source_id="APIGateway",
            target_id="AuthService",
            flow_type="http",
            protocol="REST",
            classification=DataClassification.PII,
            confidence=0.85,
        ),
        DataFlow(
            flow_id="flow-003",
            source_id="DataService",
            target_id="Database",
            flow_type="database",
            protocol="unknown",
            classification=DataClassification.SENSITIVE,
            confidence=0.75,
        ),
    ]


@pytest.fixture
def sample_diagrams() -> list[DiagramResult]:
    """Create sample diagram results for testing."""
    return [
        DiagramResult(
            diagram_type=DiagramType.ARCHITECTURE,
            mermaid_code="graph TB\n  A[Auth] --> B[Data]",
            confidence=0.8,
            components=[],
        ),
        DiagramResult(
            diagram_type=DiagramType.DATA_FLOW,
            mermaid_code="flowchart LR\n  User --> API --> DB",
            confidence=0.75,
            components=[],
        ),
    ]


# =============================================================================
# ReportGenerator Initialization Tests
# =============================================================================


class TestReportGeneratorInit:
    """Tests for ReportGenerator initialization."""

    def test_init_without_llm(self):
        """Test initialization without LLM client."""
        generator = ReportGenerator()

        assert generator.llm is None
        assert generator.include_confidence_details is True

    def test_init_with_llm(self, mock_llm):
        """Test initialization with LLM client."""
        generator = ReportGenerator(llm_client=mock_llm)

        assert generator.llm is mock_llm
        assert generator.include_confidence_details is True

    def test_init_confidence_details_disabled(self):
        """Test initialization with confidence details disabled."""
        generator = ReportGenerator(include_confidence_details=False)

        assert generator.include_confidence_details is False


# =============================================================================
# ReportGenerator.generate Tests
# =============================================================================


class TestReportGeneratorGenerate:
    """Tests for the main generate method."""

    @pytest.mark.asyncio
    async def test_generate_minimal(self):
        """Test generation with minimal inputs."""
        generator = ReportGenerator()

        report = await generator.generate(repository_id="test-repo")

        assert isinstance(report, TechnicalReport)
        assert report.repository_id == "test-repo"
        assert report.title == "Technical Documentation: test-repo"
        assert len(report.sections) >= 3  # Summary, Security, Recommendations
        assert 0.0 <= report.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_generate_with_boundaries(self, sample_boundaries):
        """Test generation with service boundaries."""
        generator = ReportGenerator()

        report = await generator.generate(
            repository_id="test-repo",
            boundaries=sample_boundaries,
        )

        assert isinstance(report, TechnicalReport)
        # Should have Service Inventory section
        section_titles = [s.title for s in report.sections]
        assert "Service Inventory" in section_titles

    @pytest.mark.asyncio
    async def test_generate_with_data_flows(self, sample_data_flows):
        """Test generation with data flows."""
        generator = ReportGenerator()

        report = await generator.generate(
            repository_id="test-repo",
            data_flows=sample_data_flows,
        )

        assert isinstance(report, TechnicalReport)
        section_titles = [s.title for s in report.sections]
        assert "Data Flow Analysis" in section_titles

    @pytest.mark.asyncio
    async def test_generate_with_all_inputs(
        self, sample_boundaries, sample_data_flows, sample_diagrams
    ):
        """Test generation with all inputs."""
        generator = ReportGenerator()

        report = await generator.generate(
            repository_id="test-repo",
            boundaries=sample_boundaries,
            data_flows=sample_data_flows,
            diagrams=sample_diagrams,
            metadata={"version": "1.0"},
        )

        assert isinstance(report, TechnicalReport)
        assert report.metadata == {"version": "1.0"}
        section_titles = [s.title for s in report.sections]
        assert "Overview" in section_titles
        assert "Service Inventory" in section_titles
        assert "Data Flow Analysis" in section_titles
        assert "Security Considerations" in section_titles
        assert "Recommendations" in section_titles

    @pytest.mark.asyncio
    async def test_generate_with_llm(self, mock_llm, sample_boundaries):
        """Test generation with LLM enhancement."""
        generator = ReportGenerator(llm_client=mock_llm)

        report = await generator.generate(
            repository_id="test-repo",
            boundaries=sample_boundaries,
        )

        assert isinstance(report, TechnicalReport)
        # LLM should have been called
        mock_llm.generate.assert_called()

    @pytest.mark.asyncio
    async def test_generate_error_handling(self):
        """Test that errors are wrapped in ReportGenerationError."""
        generator = ReportGenerator()

        # Patch internal method to raise an error
        with patch.object(
            generator,
            "_generate_executive_summary",
            side_effect=ValueError("Test error"),
        ):
            with pytest.raises(ReportGenerationError) as exc_info:
                await generator.generate(repository_id="test-repo")

            assert "Failed to generate report" in str(exc_info.value)
            assert exc_info.value.details["repository_id"] == "test-repo"

    @pytest.mark.asyncio
    async def test_generate_calculates_overall_confidence(
        self, sample_boundaries, sample_data_flows
    ):
        """Test that overall confidence is calculated from sections."""
        generator = ReportGenerator()

        report = await generator.generate(
            repository_id="test-repo",
            boundaries=sample_boundaries,
            data_flows=sample_data_flows,
        )

        # Overall confidence should be average of section confidences
        expected_avg = sum(s.confidence for s in report.sections) / len(report.sections)
        assert abs(report.confidence - expected_avg) < 0.01


# =============================================================================
# Executive Summary Tests
# =============================================================================


class TestExecutiveSummary:
    """Tests for executive summary generation."""

    @pytest.mark.asyncio
    async def test_executive_summary_content(self, sample_boundaries):
        """Test executive summary contains key metrics."""
        generator = ReportGenerator()

        section = await generator._generate_executive_summary(
            repository_id="test-repo",
            boundaries=sample_boundaries,
            data_flows=None,
            diagrams=None,
        )

        assert section.title == "Overview"
        assert "Services Detected:" in section.content
        assert "3" in section.content  # 3 boundaries
        assert section.confidence > 0

    @pytest.mark.asyncio
    async def test_executive_summary_with_llm_enhancement(
        self, mock_llm, sample_boundaries
    ):
        """Test LLM enhancement in executive summary."""
        generator = ReportGenerator(llm_client=mock_llm)

        section = await generator._generate_executive_summary(
            repository_id="test-repo",
            boundaries=sample_boundaries,
            data_flows=None,
            diagrams=None,
        )

        assert "Analysis Overview" in section.content
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_executive_summary_llm_failure_graceful(
        self, mock_llm, sample_boundaries
    ):
        """Test graceful handling of LLM failures."""
        mock_llm.generate.side_effect = Exception("LLM unavailable")
        generator = ReportGenerator(llm_client=mock_llm)

        # Should not raise, just skip enhancement
        section = await generator._generate_executive_summary(
            repository_id="test-repo",
            boundaries=sample_boundaries,
            data_flows=None,
            diagrams=None,
        )

        assert section.title == "Overview"
        # LLM content should not be present
        assert "Analysis Overview" not in section.content

    @pytest.mark.asyncio
    async def test_executive_summary_llm_generation_error(
        self, mock_llm, sample_boundaries
    ):
        """Test handling of LLMGenerationError specifically."""
        mock_llm.generate.side_effect = LLMGenerationError(
            "Model error", model="claude-3", details={}
        )
        generator = ReportGenerator(llm_client=mock_llm)

        # Should not raise, just log warning and skip enhancement
        section = await generator._generate_executive_summary(
            repository_id="test-repo",
            boundaries=sample_boundaries,
            data_flows=None,
            diagrams=None,
        )

        assert section.title == "Overview"
        # LLM content should not be present since it failed
        assert "Analysis Overview" not in section.content


# =============================================================================
# Service Inventory Tests
# =============================================================================


class TestServiceInventory:
    """Tests for service inventory generation."""

    def test_service_inventory_formatting(self, sample_boundaries):
        """Test service inventory is properly formatted."""
        generator = ReportGenerator()

        section = generator._generate_service_inventory(sample_boundaries)

        assert section.title == "Service Inventory"
        assert "AuthService" in section.content
        assert "DataService" in section.content
        assert "APIGateway" in section.content
        # Entry points should be listed
        assert "login()" in section.content
        assert "No public entry points detected" in section.content  # APIGateway

    def test_service_inventory_sorted_by_confidence(self, sample_boundaries):
        """Test services are sorted by confidence (highest first)."""
        generator = ReportGenerator()

        section = generator._generate_service_inventory(sample_boundaries)

        # AuthService (0.85) should appear before DataService (0.72)
        auth_pos = section.content.find("AuthService")
        data_pos = section.content.find("DataService")
        api_pos = section.content.find("APIGateway")

        assert auth_pos < data_pos < api_pos

    def test_service_inventory_includes_metrics(self, sample_boundaries):
        """Test service inventory includes all metrics."""
        generator = ReportGenerator()

        section = generator._generate_service_inventory(sample_boundaries)

        assert "Components:" in section.content
        assert "Internal Edges:" in section.content
        assert "External Edges:" in section.content
        assert "Modularity Ratio:" in section.content

    def test_service_inventory_confidence(self, sample_boundaries):
        """Test service inventory confidence is average of boundaries."""
        generator = ReportGenerator()

        section = generator._generate_service_inventory(sample_boundaries)

        expected = sum(b.confidence for b in sample_boundaries) / len(sample_boundaries)
        assert abs(section.confidence - expected) < 0.01


# =============================================================================
# Data Flow Analysis Tests
# =============================================================================


class TestDataFlowAnalysis:
    """Tests for data flow analysis generation."""

    def test_data_flow_analysis_formatting(self, sample_data_flows):
        """Test data flow analysis is properly formatted."""
        generator = ReportGenerator()

        section = generator._generate_data_flow_analysis(sample_data_flows)

        assert section.title == "Data Flow Analysis"
        assert "AuthService" in section.content
        assert "DataService" in section.content

    def test_data_flow_grouped_by_classification(self, sample_data_flows):
        """Test data flows are grouped by classification."""
        generator = ReportGenerator()

        section = generator._generate_data_flow_analysis(sample_data_flows)

        # PII should appear before SENSITIVE which should appear before INTERNAL
        pii_pos = section.content.find("PII Data Flows")
        sensitive_pos = section.content.find("SENSITIVE Data Flows")
        internal_pos = section.content.find("INTERNAL Data Flows")

        assert pii_pos < sensitive_pos < internal_pos

    def test_data_flow_empty_list(self):
        """Test handling of empty data flows."""
        generator = ReportGenerator()

        section = generator._generate_data_flow_analysis([])

        assert section.confidence == 0.5  # Default confidence


# =============================================================================
# Security Considerations Tests
# =============================================================================


class TestSecurityConsiderations:
    """Tests for security considerations generation."""

    def test_security_default_considerations(self):
        """Test default security considerations are always included."""
        generator = ReportGenerator()

        section = generator._generate_security_considerations(None, None)

        assert section.title == "Security Considerations"
        assert "Input Validation" in section.content
        assert "Authentication & Authorization" in section.content

    def test_security_sensitive_data_detection(self, sample_data_flows):
        """Test detection of sensitive data flows."""
        generator = ReportGenerator()

        section = generator._generate_security_considerations(None, sample_data_flows)

        assert "Sensitive Data in Transit" in section.content
        assert "PII" in section.content or "sensitive" in section.content.lower()

    def test_security_external_dependencies(self, sample_boundaries):
        """Test detection of external dependencies."""
        # Create boundaries with many external connections
        boundaries = [
            ServiceBoundary(
                boundary_id="svc-001",
                name="HighExternal",
                node_ids=["a.py"],
                confidence=0.8,
                description="Test",
                entry_points=[],
                edges_internal=2,
                edges_external=15,  # High external
            )
        ]

        generator = ReportGenerator()
        section = generator._generate_security_considerations(boundaries, None)

        assert "External Dependencies" in section.content

    def test_security_low_modularity_detection(self):
        """Test detection of tightly coupled services."""
        boundaries = [
            ServiceBoundary(
                boundary_id="svc-001",
                name="TightlyCoupled",
                node_ids=["a.py"],
                confidence=0.8,
                description="Test",
                entry_points=[],
                edges_internal=1,
                edges_external=10,
            )
        ]

        generator = ReportGenerator()
        section = generator._generate_security_considerations(boundaries, None)

        assert "Tightly Coupled Services" in section.content


# =============================================================================
# Recommendations Tests
# =============================================================================


class TestRecommendations:
    """Tests for recommendations generation."""

    def test_recommendations_default(self):
        """Test default recommendation is always included."""
        generator = ReportGenerator()

        section = generator._generate_recommendations(None, None, None)

        assert section.title == "Recommendations"
        assert "Regular Documentation Updates" in section.content

    def test_recommendations_low_confidence_services(self):
        """Test recommendation for low confidence services."""
        boundaries = [
            ServiceBoundary(
                boundary_id="svc-001",
                name="LowConfidence",
                node_ids=["a.py"],
                confidence=0.4,  # Low confidence
                description="Test",
                entry_points=[],
                edges_internal=1,
                edges_external=1,
            )
        ]

        generator = ReportGenerator()
        section = generator._generate_recommendations(boundaries, None, None)

        assert "Improve Service Documentation" in section.content

    def test_recommendations_missing_diagrams(self, sample_diagrams):
        """Test recommendation for missing diagram types."""
        generator = ReportGenerator()

        section = generator._generate_recommendations(None, None, sample_diagrams)

        assert "Generate Additional Diagrams" in section.content
        assert "sequence" in section.content.lower()

    def test_recommendations_unknown_protocols(self):
        """Test recommendation for unknown protocols."""
        flows = [
            DataFlow(
                flow_id="flow-001",
                source_id="A",
                target_id="B",
                flow_type="unknown",
                protocol="unknown",
                classification=DataClassification.INTERNAL,
                confidence=0.5,
            )
        ]

        generator = ReportGenerator()
        section = generator._generate_recommendations(None, flows, None)

        assert "Document Communication Protocols" in section.content


# =============================================================================
# Executive Summary Text Tests
# =============================================================================


class TestBuildExecutiveSummaryText:
    """Tests for executive summary text building."""

    def test_summary_text_low_confidence(self):
        """Test summary text for low confidence."""
        generator = ReportGenerator()

        text = generator._build_executive_summary_text(
            repository_id="test-repo",
            boundaries=None,
            data_flows=None,
            diagrams=None,
            overall_confidence=0.4,
        )

        assert "manual review is recommended" in text

    def test_summary_text_high_confidence(self, sample_boundaries):
        """Test summary text for high confidence."""
        generator = ReportGenerator()

        text = generator._build_executive_summary_text(
            repository_id="test-repo",
            boundaries=sample_boundaries,
            data_flows=None,
            diagrams=None,
            overall_confidence=0.9,
        )

        assert "High confidence" in text
        assert "accurately represents" in text

    def test_summary_text_medium_confidence(self):
        """Test summary text for medium confidence."""
        generator = ReportGenerator()

        text = generator._build_executive_summary_text(
            repository_id="test-repo",
            boundaries=None,
            data_flows=None,
            diagrams=None,
            overall_confidence=0.75,
        )

        assert "manual verification" in text


# =============================================================================
# LLM Enhancement Tests
# =============================================================================


class TestLLMEnhancement:
    """Tests for LLM enhancement functionality."""

    @pytest.mark.asyncio
    async def test_llm_enhance_summary_success(self, mock_llm, sample_boundaries):
        """Test successful LLM enhancement."""
        generator = ReportGenerator(llm_client=mock_llm)

        result = await generator._llm_enhance_summary("test-repo", sample_boundaries)

        assert result is not None
        assert "authentication" in result.lower()
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_enhance_summary_no_llm(self, sample_boundaries):
        """Test LLM enhancement without LLM client."""
        generator = ReportGenerator()

        result = await generator._llm_enhance_summary("test-repo", sample_boundaries)

        assert result is None

    @pytest.mark.asyncio
    async def test_llm_enhance_summary_error(self, mock_llm, sample_boundaries):
        """Test LLM enhancement error handling."""
        mock_llm.generate.side_effect = Exception("LLM error")
        generator = ReportGenerator(llm_client=mock_llm)

        result = await generator._llm_enhance_summary("test-repo", sample_boundaries)

        assert result is None


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for the create_report_generator factory function."""

    def test_create_without_llm(self):
        """Test factory without LLM."""
        generator = create_report_generator()

        assert isinstance(generator, ReportGenerator)
        assert generator.llm is None

    def test_create_with_llm(self, mock_llm):
        """Test factory with LLM."""
        generator = create_report_generator(llm_client=mock_llm)

        assert isinstance(generator, ReportGenerator)
        assert generator.llm is mock_llm


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the report generator."""

    @pytest.mark.asyncio
    async def test_full_report_generation_workflow(
        self, sample_boundaries, sample_data_flows, sample_diagrams
    ):
        """Test complete report generation workflow."""
        generator = ReportGenerator()

        report = await generator.generate(
            repository_id="my-application",
            boundaries=sample_boundaries,
            data_flows=sample_data_flows,
            diagrams=sample_diagrams,
            metadata={
                "generated_by": "test",
                "version": "1.0",
            },
        )

        # Verify report structure
        assert report.title == "Technical Documentation: my-application"
        assert report.repository_id == "my-application"
        assert len(report.sections) == 5
        assert report.metadata["generated_by"] == "test"
        assert isinstance(report.generated_at, datetime)
        assert report.generated_at.tzinfo == timezone.utc

        # Verify executive summary
        assert len(report.executive_summary) > 0
        assert "my-application" in report.executive_summary

        # Verify section ordering
        expected_order = [
            "Overview",
            "Service Inventory",
            "Data Flow Analysis",
            "Security Considerations",
            "Recommendations",
        ]
        actual_order = [s.title for s in report.sections]
        assert actual_order == expected_order

    @pytest.mark.asyncio
    async def test_report_to_markdown(self, sample_boundaries):
        """Test report can be converted to markdown."""
        generator = ReportGenerator()

        report = await generator.generate(
            repository_id="test-repo",
            boundaries=sample_boundaries,
        )

        # TechnicalReport should have a to_markdown method
        if hasattr(report, "to_markdown"):
            markdown = report.to_markdown()
            assert isinstance(markdown, str)
            assert "# Technical Documentation: test-repo" in markdown

    @pytest.mark.asyncio
    async def test_report_confidence_propagation(
        self, sample_boundaries, sample_data_flows
    ):
        """Test that confidence scores propagate correctly."""
        generator = ReportGenerator()

        report = await generator.generate(
            repository_id="test-repo",
            boundaries=sample_boundaries,
            data_flows=sample_data_flows,
        )

        # All sections should have valid confidence scores
        for section in report.sections:
            assert 0.0 <= section.confidence <= 1.0

        # Overall confidence should be reasonable
        assert 0.0 <= report.confidence <= 1.0
