"""Tests for DocumentationAgent (ADR-056)."""

import platform
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.documentation.documentation_agent import (
    DocumentationAgent,
    create_documentation_agent,
)
from src.services.documentation.types import (
    DiagramResult,
    DiagramType,
    DocumentationRequest,
    DocumentationResult,
    ServiceBoundary,
    TechnicalReport,
)

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestDocumentationAgent:
    """Tests for DocumentationAgent."""

    @pytest.fixture
    def mock_boundary_detector(self):
        """Create a mock boundary detector."""
        detector = MagicMock()
        detector.detect_boundaries = AsyncMock(
            return_value=[
                ServiceBoundary(
                    boundary_id="svc-1",
                    name="UserService",
                    description="User management",
                    node_ids=["n1", "n2", "n3"],
                    confidence=0.85,
                )
            ]
        )
        return detector

    @pytest.fixture
    def mock_diagram_generator(self):
        """Create a mock diagram generator."""
        generator = MagicMock()
        generator.generate = MagicMock(
            return_value=DiagramResult(
                diagram_type=DiagramType.ARCHITECTURE,
                mermaid_code="graph TB\n  A --> B",
                confidence=0.82,
            )
        )
        return generator

    @pytest.fixture
    def mock_report_generator(self):
        """Create a mock report generator."""
        generator = MagicMock()
        generator.generate = AsyncMock(
            return_value=TechnicalReport(
                title="Architecture Report",
                executive_summary="Test summary",
                sections=[],
                confidence=0.80,
                repository_id="test-repo",
            )
        )
        return generator

    @pytest.fixture
    def mock_cache_service(self):
        """Create a mock cache service."""
        cache = MagicMock()
        cache.get = MagicMock(return_value=None)
        cache.set = MagicMock()
        return cache

    @pytest.fixture
    def agent(
        self,
        mock_boundary_detector,
        mock_diagram_generator,
        mock_report_generator,
        mock_cache_service,
    ):
        """Create a DocumentationAgent for testing."""
        return DocumentationAgent(
            llm_client=None,
            neptune_service=None,
            cache_service=mock_cache_service,
            boundary_detector=mock_boundary_detector,
            diagram_generator=mock_diagram_generator,
            report_generator=mock_report_generator,
        )

    def test_initialization(self, agent):
        """Test agent initialization."""
        assert agent is not None
        assert agent.llm is None
        assert agent.neptune is None

    def test_initialization_with_defaults(self):
        """Test agent initialization with default values."""
        agent = DocumentationAgent()
        assert agent is not None
        assert agent.cache is not None
        assert agent.boundary_detector is not None
        assert agent.diagram_generator is not None

    @pytest.mark.asyncio
    async def test_generate_documentation(self, agent):
        """Test documentation generation."""
        request = DocumentationRequest(
            repository_id="test-repo",
            diagram_types=[DiagramType.ARCHITECTURE],
        )
        result = await agent.generate_documentation(request)

        assert isinstance(result, DocumentationResult)
        assert result.repository_id == "test-repo"
        assert len(result.diagrams) > 0
        assert len(result.service_boundaries) > 0

    @pytest.mark.asyncio
    async def test_generate_documentation_with_report(self, agent):
        """Test documentation generation with report."""
        request = DocumentationRequest(
            repository_id="test-repo",
            diagram_types=[DiagramType.ARCHITECTURE],
            include_report=True,
        )
        result = await agent.generate_documentation(request)

        assert result.report is not None

    @pytest.mark.asyncio
    async def test_generate_documentation_without_report(self, agent):
        """Test documentation generation without report."""
        request = DocumentationRequest(
            repository_id="test-repo",
            diagram_types=[DiagramType.ARCHITECTURE],
            include_report=False,
        )
        result = await agent.generate_documentation(request)

        assert result.report is None

    @pytest.mark.asyncio
    async def test_generate_multiple_diagrams(self, agent, mock_diagram_generator):
        """Test generating multiple diagram types."""
        # Setup mock to return different diagram types
        mock_diagram_generator.generate = MagicMock(
            side_effect=[
                DiagramResult(
                    diagram_type=DiagramType.ARCHITECTURE,
                    mermaid_code="graph TB",
                    confidence=0.82,
                ),
                DiagramResult(
                    diagram_type=DiagramType.DATA_FLOW,
                    mermaid_code="flowchart LR",
                    confidence=0.78,
                ),
            ]
        )

        request = DocumentationRequest(
            repository_id="test-repo",
            diagram_types=[DiagramType.ARCHITECTURE, DiagramType.DATA_FLOW],
            include_report=False,
        )
        result = await agent.generate_documentation(request)

        assert len(result.diagrams) == 2

    @pytest.mark.asyncio
    async def test_cache_hit(self, agent, mock_cache_service):
        """Test documentation retrieval from cache."""
        cached_result = {
            "job_id": "cached-job",
            "repository_id": "test-repo",
            "diagrams": [],
            "report": None,
            "service_boundaries": [],
            "confidence": 0.85,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generation_time_ms": 100,
        }
        mock_cache_service.get = MagicMock(return_value=cached_result)

        request = DocumentationRequest(
            repository_id="test-repo",
            diagram_types=[DiagramType.ARCHITECTURE],
        )
        result = await agent.generate_documentation(request)

        # Should return cached result with new job_id but cached content
        assert result is not None
        assert result.metadata.get("cached") is True

    @pytest.mark.asyncio
    async def test_cache_miss(self, agent, mock_cache_service):
        """Test documentation generation on cache miss."""
        mock_cache_service.get = MagicMock(return_value=None)

        request = DocumentationRequest(
            repository_id="test-repo",
            diagram_types=[DiagramType.ARCHITECTURE],
        )
        result = await agent.generate_documentation(request)

        # Should generate new documentation
        assert result is not None
        # Cache should be updated
        mock_cache_service.set.assert_called()

    @pytest.mark.asyncio
    async def test_job_id_generation(self, agent):
        """Test that unique job IDs are generated."""
        request = DocumentationRequest(
            repository_id="test-repo",
            diagram_types=[DiagramType.ARCHITECTURE],
        )
        result1 = await agent.generate_documentation(request)
        result2 = await agent.generate_documentation(request)

        assert result1.job_id != result2.job_id

    @pytest.mark.asyncio
    async def test_overall_confidence_calculation(self, agent, mock_diagram_generator):
        """Test overall confidence is calculated correctly."""
        mock_diagram_generator.generate = MagicMock(
            return_value=DiagramResult(
                diagram_type=DiagramType.ARCHITECTURE,
                mermaid_code="graph TB",
                confidence=0.80,
            )
        )

        request = DocumentationRequest(
            repository_id="test-repo",
            diagram_types=[DiagramType.ARCHITECTURE],
            include_report=False,
        )
        result = await agent.generate_documentation(request)

        # Overall confidence should be between 0 and 1
        assert 0 <= result.confidence <= 1


class TestCreateDocumentationAgent:
    """Tests for the factory function."""

    def test_create_with_mock_mode(self):
        """Test factory creates agent in mock mode."""
        agent = create_documentation_agent(use_mock=True)
        assert agent is not None
        assert agent.llm is None
        assert agent.neptune is None

    def test_create_with_services(self):
        """Test factory with custom services."""
        mock_llm = MagicMock()
        mock_neptune = MagicMock()

        agent = create_documentation_agent(
            use_mock=False,
            llm_client=mock_llm,
            neptune_service=mock_neptune,
        )

        assert agent is not None
        assert agent.llm == mock_llm
        assert agent.neptune == mock_neptune

    def test_create_default(self):
        """Test factory with defaults."""
        agent = create_documentation_agent()

        # Should have all required components
        assert hasattr(agent, "boundary_detector")
        assert hasattr(agent, "diagram_generator")
        assert hasattr(agent, "cache")


class TestDocumentationAgentStreaming:
    """Tests for streaming documentation generation."""

    @pytest.fixture
    def agent(self):
        """Create agent for streaming tests."""
        return DocumentationAgent()

    @pytest.mark.asyncio
    async def test_stream_yields_progress(self, agent):
        """Test that streaming yields progress updates."""
        request = DocumentationRequest(
            repository_id="test-repo",
            diagram_types=[DiagramType.ARCHITECTURE],
            include_report=False,
        )

        progress_updates = []
        async for progress in agent.generate_documentation_stream(request):
            progress_updates.append(progress)

        # Should have multiple progress updates
        assert len(progress_updates) > 0
        # Last should be complete or error
        assert progress_updates[-1].phase in ["complete", "error"]

    @pytest.mark.asyncio
    async def test_stream_progress_percentage(self, agent):
        """Test that progress percentage increases."""
        request = DocumentationRequest(
            repository_id="test-repo",
            diagram_types=[DiagramType.ARCHITECTURE],
            include_report=False,
        )

        progress_values = []
        async for progress in agent.generate_documentation_stream(request):
            progress_values.append(progress.progress)

        # Progress should generally increase (with possible equal steps)
        for i in range(1, len(progress_values)):
            assert (
                progress_values[i] >= progress_values[i - 1]
                or progress_values[i - 1] == 0
            )
