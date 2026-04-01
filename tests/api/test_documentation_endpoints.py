"""Tests for documentation API endpoints (ADR-056)."""

import platform
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestDocumentationEndpointsUnit:
    """Unit tests for documentation endpoint logic."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        # Clear documentation-related modules to ensure fresh router state
        modules_to_clear = [
            key
            for key in list(sys.modules.keys())
            if key.startswith("src.api.documentation")
            or key.startswith("src.services.documentation")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]
        yield

    def test_diagram_types_endpoint(self):
        """Test GET /api/v1/documentation/diagram-types endpoint."""
        from src.api.documentation_endpoints import router
        from src.services.documentation.types import DiagramType

        app = FastAPI()
        # Router already has /api/v1/documentation prefix
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/v1/documentation/diagram-types")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == len(DiagramType)
        # Check that all diagram types are present
        values = [d["value"] for d in data]
        assert "architecture" in values
        assert "data_flow" in values

    def test_request_model_validation(self):
        """Test request model validation."""
        from src.api.documentation_endpoints import GenerateDocumentationRequest

        # Valid request
        request = GenerateDocumentationRequest(
            repository_id="test-repo",
            diagram_types=["architecture"],
            include_report=True,
        )
        assert request.repository_id == "test-repo"
        assert request.include_report is True

        # Default values
        request_defaults = GenerateDocumentationRequest(repository_id="test-repo")
        assert request_defaults.diagram_types == ["architecture", "data_flow"]
        assert request_defaults.max_services == 20
        assert request_defaults.min_confidence == 0.45

    def test_feedback_request_validation(self):
        """Test feedback request model validation."""
        from src.api.documentation_endpoints import FeedbackRequest

        request = FeedbackRequest(
            job_id="test-job-123",
            documentation_type="diagram",
            diagram_type="architecture",
            feedback_type="accurate",
            raw_confidence=0.8,
            correction_text="Minor fix",
            notes="Test notes",
        )
        assert request.job_id == "test-job-123"
        assert request.feedback_type == "accurate"
        assert request.raw_confidence == 0.8

    def test_feedback_request_defaults(self):
        """Test feedback request with default values."""
        from src.api.documentation_endpoints import FeedbackRequest

        request = FeedbackRequest(
            job_id="test-job",
            feedback_type="inaccurate",
            raw_confidence=0.5,
        )
        assert request.documentation_type == "diagram"
        assert request.diagram_type == ""
        assert request.correction_text == ""
        assert request.notes == ""

    def test_response_models(self):
        """Test response model creation."""
        from src.api.documentation_endpoints import (
            DiagramResponse,
            ReportResponse,
            ServiceBoundaryResponse,
        )

        # DiagramResponse
        diagram = DiagramResponse(
            diagram_type="architecture",
            mermaid_code="graph TB",
            confidence=0.85,
            confidence_level="high",
            warnings=[],
        )
        assert diagram.diagram_type == "architecture"

        # ServiceBoundaryResponse
        boundary = ServiceBoundaryResponse(
            boundary_id="svc-1",
            name="TestService",
            description="Test",
            confidence=0.8,
            confidence_level="medium",
            node_count=10,
            edges_internal=8,
            edges_external=2,
            modularity_ratio=0.8,
        )
        assert boundary.node_count == 10

        # ReportResponse
        report = ReportResponse(
            title="Test Report",
            executive_summary="Summary",
            markdown="# Report",
            confidence=0.82,
            confidence_level="medium",
            section_count=5,
        )
        assert report.section_count == 5


class TestDocumentationHelpers:
    """Tests for helper functions."""

    @pytest.fixture(autouse=True)
    def clear_modules(self):
        """Clear cached modules before each test."""
        modules_to_clear = [
            key
            for key in list(sys.modules.keys())
            if key.startswith("src.api.documentation")
            or key.startswith("src.services.documentation")
        ]
        for mod in modules_to_clear:
            del sys.modules[mod]
        yield

    def test_build_documentation_response(self):
        """Test _build_documentation_response helper."""
        from src.api.documentation_endpoints import _build_documentation_response
        from src.services.documentation.types import (
            DiagramResult,
            DiagramType,
            DocumentationResult,
            ServiceBoundary,
        )

        # Create a mock result
        result = DocumentationResult(
            job_id="test-job-123",
            repository_id="test-repo",
            diagrams=[
                DiagramResult(
                    diagram_type=DiagramType.ARCHITECTURE,
                    mermaid_code="graph TB\n  A --> B",
                    confidence=0.85,
                )
            ],
            service_boundaries=[
                ServiceBoundary(
                    boundary_id="svc-1",
                    name="TestService",
                    description="Test service",
                    node_ids=["n1", "n2"],
                    confidence=0.80,
                )
            ],
            confidence=0.82,
        )

        response = _build_documentation_response(result)

        assert response.job_id == "test-job-123"
        assert response.repository_id == "test-repo"
        assert len(response.diagrams) == 1
        assert len(response.service_boundaries) == 1
        assert response.confidence == 0.82


class TestDocumentationAgentIntegration:
    """Integration tests with mocked agent - direct function calls."""

    @pytest.fixture
    def mock_documentation_result(self):
        """Create a mock documentation result."""
        from src.services.documentation.types import (
            DiagramResult,
            DiagramType,
            DocumentationResult,
            ServiceBoundary,
            TechnicalReport,
        )

        return DocumentationResult(
            job_id="test-job-123",
            repository_id="test-repo",
            diagrams=[
                DiagramResult(
                    diagram_type=DiagramType.ARCHITECTURE,
                    mermaid_code="graph TB\n  A --> B",
                    confidence=0.85,
                )
            ],
            service_boundaries=[
                ServiceBoundary(
                    boundary_id="svc-1",
                    name="TestService",
                    description="Test service",
                    node_ids=["n1", "n2"],
                    confidence=0.80,
                )
            ],
            report=TechnicalReport(
                title="Test Report",
                executive_summary="Summary",
                sections=[],
                confidence=0.82,
                repository_id="test-repo",
            ),
            confidence=0.82,
        )

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        from src.api.auth import User

        user = MagicMock(spec=User)
        user.sub = "user-123"
        user.email = "test@example.com"
        user.groups = ["user"]
        user.organization_id = "org-123"
        return user

    @pytest.mark.asyncio
    async def test_generate_documentation_direct(
        self, mock_documentation_result, mock_user
    ):
        """Test generate_documentation endpoint function directly."""
        from src.api.documentation_endpoints import (
            GenerateDocumentationRequest,
            generate_documentation,
        )

        mock_agent = MagicMock()
        mock_agent.generate_documentation = AsyncMock(
            return_value=mock_documentation_result
        )

        request = GenerateDocumentationRequest(
            repository_id="test-repo",
            diagram_types=["architecture"],
            include_report=True,
        )

        response = await generate_documentation(
            request=request,
            current_user=mock_user,
            agent=mock_agent,
        )

        assert response.job_id == "test-job-123"
        assert response.repository_id == "test-repo"
        assert len(response.diagrams) == 1
        mock_agent.generate_documentation.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_stats_direct(self, mock_user):
        """Test get_cache_stats endpoint function directly."""
        from src.api.documentation_endpoints import get_cache_stats

        mock_agent = MagicMock()
        mock_agent.get_cache_stats = MagicMock(
            return_value={
                "memory": {"hits": 100, "misses": 20},
                "redis": {"hits": 50, "misses": 10},
                "s3": {"hits": 10, "misses": 5},
                "total": {"hits": 160, "misses": 35},
            }
        )

        response = await get_cache_stats(
            current_user=mock_user,
            agent=mock_agent,
        )

        assert response.memory == {"hits": 100, "misses": 20}
        assert response.total["hits"] == 160

    @pytest.mark.asyncio
    async def test_invalidate_cache_direct(self, mock_user):
        """Test invalidate_cache endpoint function directly."""
        from src.api.documentation_endpoints import invalidate_cache

        mock_agent = MagicMock()
        mock_agent.invalidate_cache = MagicMock(return_value=5)

        response = await invalidate_cache(
            repository_id="test-repo",
            current_user=mock_user,
            agent=mock_agent,
        )

        assert response["status"] == "success"
        assert response["entries_invalidated"] == 5
        mock_agent.invalidate_cache.assert_called_once_with("test-repo")

    @pytest.mark.asyncio
    async def test_submit_feedback_direct(self, mock_user):
        """Test submit_feedback endpoint function directly."""
        from src.api.documentation_endpoints import FeedbackRequest, submit_feedback

        mock_feedback_service = MagicMock()
        mock_feedback_service.store_feedback = MagicMock(return_value=True)

        mock_scorer = MagicMock()
        mock_scorer.get_stats = MagicMock(
            return_value={
                "is_calibrated": False,
                "sample_count": 10,
                "min_samples_required": 100,
            }
        )

        request = FeedbackRequest(
            job_id="test-job-123",
            documentation_type="diagram",
            diagram_type="architecture",
            feedback_type="accurate",
            raw_confidence=0.8,
            correction_text="Minor fix",
            notes="Test notes",
        )

        with patch(
            "src.api.documentation_endpoints.get_calibration_scorer",
            return_value=mock_scorer,
        ):
            response = await submit_feedback(
                request=request,
                current_user=mock_user,
                feedback_service=mock_feedback_service,
            )

        assert response.status == "accepted"
        assert response.feedback_id.startswith("fb-")
        mock_feedback_service.store_feedback.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_diagram_types_direct(self):
        """Test get_diagram_types endpoint function directly."""
        from src.api.documentation_endpoints import get_diagram_types

        response = await get_diagram_types()

        assert isinstance(response, list)
        assert len(response) > 0
        assert "value" in response[0]
        assert "label" in response[0]
        # Check that architecture and data_flow exist
        values = [d["value"] for d in response]
        assert "architecture" in values
        assert "data_flow" in values

    @pytest.mark.asyncio
    async def test_get_calibration_stats_direct(self, mock_user):
        """Test get_calibration_stats endpoint function directly."""
        from src.api.documentation_endpoints import get_calibration_stats

        mock_scorer = MagicMock()
        mock_scorer.get_stats = MagicMock(
            return_value={
                "is_calibrated": True,
                "sample_count": 150,
                "min_samples_required": 100,
                "model_version": 2,
                "ece_before": 0.15,
                "ece_after": 0.08,
                "ece_improvement": 46.7,
                "organization_id": "org-123",
                "documentation_type": "diagram",
            }
        )

        with patch(
            "src.api.documentation_endpoints.get_calibration_scorer",
            return_value=mock_scorer,
        ):
            response = await get_calibration_stats(current_user=mock_user)

        assert response.is_calibrated is True
        assert response.sample_count == 150
        assert response.ece_after == 0.08

    @pytest.mark.asyncio
    async def test_calibrate_confidence_direct(self, mock_user):
        """Test calibrate_confidence endpoint function directly."""
        from src.api.documentation_endpoints import calibrate_confidence

        mock_scorer = MagicMock()
        mock_scorer.calibrate = MagicMock(return_value=0.82)
        mock_scorer.is_calibrated = True
        mock_scorer.model_version = 3

        with patch(
            "src.api.documentation_endpoints.get_calibration_scorer",
            return_value=mock_scorer,
        ):
            response = await calibrate_confidence(
                raw_score=0.75,
                current_user=mock_user,
            )

        assert response["raw_score"] == 0.75
        assert response["calibrated_score"] == 0.82
        assert response["is_calibrated"] is True

    @pytest.mark.asyncio
    async def test_get_feedback_stats_direct(self, mock_user):
        """Test get_feedback_stats endpoint function directly."""
        from src.api.documentation_endpoints import get_feedback_stats

        mock_feedback_service = MagicMock()
        mock_feedback_service.get_stats = MagicMock(
            return_value={
                "total_feedback": 100,
                "accurate_count": 80,
                "inaccurate_count": 15,
                "partial_count": 5,
                "accuracy_rate": 0.8,
            }
        )

        response = await get_feedback_stats(
            current_user=mock_user,
            feedback_service=mock_feedback_service,
        )

        assert response.total_feedback == 100
        assert response.accuracy_rate == 0.8


class TestFactoryFunctions:
    """Tests for factory functions that create service instances."""

    def test_get_documentation_agent_creates_instance(self):
        """Test get_documentation_agent creates agent on first call."""
        import src.api.documentation_endpoints as doc_module

        # Reset global state
        doc_module._agent = None

        agent = doc_module.get_documentation_agent()

        assert agent is not None
        assert doc_module._agent is agent

    def test_get_documentation_agent_returns_cached(self):
        """Test get_documentation_agent returns cached instance."""
        import src.api.documentation_endpoints as doc_module

        # Reset and create first instance
        doc_module._agent = None
        agent1 = doc_module.get_documentation_agent()
        agent2 = doc_module.get_documentation_agent()

        assert agent1 is agent2

    def test_get_feedback_service_creates_instance(self):
        """Test get_feedback_service creates service on first call."""
        import src.api.documentation_endpoints as doc_module

        # Reset global state
        doc_module._feedback_service = None

        service = doc_module.get_feedback_service()

        assert service is not None
        assert doc_module._feedback_service is service

    def test_get_metrics_service_creates_instance(self):
        """Test get_metrics_service creates service on first call."""
        import src.api.documentation_endpoints as doc_module

        # Reset global state
        doc_module._metrics_service = None

        service = doc_module.get_metrics_service()

        assert service is not None
        assert doc_module._metrics_service is service

    def test_get_calibration_scorer_creates_instance(self):
        """Test get_calibration_scorer creates scorer for organization."""
        import src.api.documentation_endpoints as doc_module

        # Reset global state
        doc_module._calibration_scorers = {}

        scorer = doc_module.get_calibration_scorer("test-org")

        assert scorer is not None
        assert "test-org" in doc_module._calibration_scorers

    def test_get_calibration_scorer_returns_cached(self):
        """Test get_calibration_scorer returns cached instance for same org."""
        import src.api.documentation_endpoints as doc_module

        # Reset global state
        doc_module._calibration_scorers = {}

        scorer1 = doc_module.get_calibration_scorer("test-org")
        scorer2 = doc_module.get_calibration_scorer("test-org")

        assert scorer1 is scorer2

    def test_get_calibration_scorer_different_orgs(self):
        """Test get_calibration_scorer creates different instances for different orgs."""
        import src.api.documentation_endpoints as doc_module

        # Reset global state
        doc_module._calibration_scorers = {}

        scorer1 = doc_module.get_calibration_scorer("org-1")
        scorer2 = doc_module.get_calibration_scorer("org-2")

        assert scorer1 is not scorer2


class TestCalibrationTraining:
    """Tests for calibration training endpoint."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        from src.api.auth import User

        user = MagicMock(spec=User)
        user.sub = "user-123"
        user.organization_id = "org-123"
        return user

    @pytest.mark.asyncio
    async def test_trigger_training_insufficient_data(self, mock_user):
        """Test trigger_calibration_training with insufficient data."""
        from src.api.documentation_endpoints import trigger_calibration_training

        mock_feedback_service = MagicMock()
        mock_feedback_service.get_feedback_for_calibration = MagicMock(
            return_value=[MagicMock() for _ in range(50)]  # Only 50 samples
        )

        mock_metrics_service = MagicMock()

        mock_scorer = MagicMock()
        mock_scorer.min_samples = 100

        with patch(
            "src.api.documentation_endpoints.get_calibration_scorer",
            return_value=mock_scorer,
        ):
            response = await trigger_calibration_training(
                current_user=mock_user,
                feedback_service=mock_feedback_service,
                metrics_service=mock_metrics_service,
            )

        assert response["status"] == "insufficient_data"
        assert response["sample_count"] == 50
        assert response["samples_needed"] == 50

    @pytest.mark.asyncio
    async def test_trigger_training_success(self, mock_user):
        """Test trigger_calibration_training with successful training."""
        from src.api.documentation_endpoints import trigger_calibration_training
        from src.services.documentation.confidence_calibration import FeedbackRecord

        # Create mock feedback records
        feedback_records = []
        for i in range(150):
            record = MagicMock(spec=FeedbackRecord)
            record.raw_confidence = 0.5 + (i % 5) * 0.1
            record.actual_accuracy = (i % 2) * 1.0
            feedback_records.append(record)

        mock_feedback_service = MagicMock()
        mock_feedback_service.get_feedback_for_calibration = MagicMock(
            return_value=feedback_records
        )

        mock_metrics_service = MagicMock()

        mock_scorer = MagicMock()
        mock_scorer.min_samples = 100
        mock_scorer.fit = MagicMock(return_value=True)
        mock_scorer.get_stats = MagicMock(
            return_value={
                "sample_count": 150,
                "ece_before": 0.15,
                "ece_after": 0.08,
                "ece_improvement": 46.7,
                "model_version": 2,
            }
        )

        with patch(
            "src.api.documentation_endpoints.get_calibration_scorer",
            return_value=mock_scorer,
        ):
            response = await trigger_calibration_training(
                current_user=mock_user,
                feedback_service=mock_feedback_service,
                metrics_service=mock_metrics_service,
            )

        assert response["status"] == "success"
        assert response["sample_count"] == 150
        assert response["ece_improvement_percent"] == 46.7
        mock_metrics_service.record_calibration_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_training_failure(self, mock_user):
        """Test trigger_calibration_training when training fails."""
        from src.api.documentation_endpoints import trigger_calibration_training
        from src.services.documentation.confidence_calibration import FeedbackRecord

        # Create mock feedback records
        feedback_records = [MagicMock(spec=FeedbackRecord) for _ in range(150)]
        for record in feedback_records:
            record.raw_confidence = 0.5
            record.actual_accuracy = 0.5

        mock_feedback_service = MagicMock()
        mock_feedback_service.get_feedback_for_calibration = MagicMock(
            return_value=feedback_records
        )

        mock_metrics_service = MagicMock()

        mock_scorer = MagicMock()
        mock_scorer.min_samples = 100
        mock_scorer.fit = MagicMock(return_value=False)

        with patch(
            "src.api.documentation_endpoints.get_calibration_scorer",
            return_value=mock_scorer,
        ):
            response = await trigger_calibration_training(
                current_user=mock_user,
                feedback_service=mock_feedback_service,
                metrics_service=mock_metrics_service,
            )

        assert response["status"] == "training_failed"


class TestExceptionHandling:
    """Tests for exception handling in endpoints."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        from src.api.auth import User

        user = MagicMock(spec=User)
        user.sub = "user-123"
        user.organization_id = "org-123"
        return user

    @pytest.mark.asyncio
    async def test_generate_documentation_invalid_diagram_type(self, mock_user):
        """Test generate_documentation raises HTTPException for invalid diagram type."""
        from src.api.documentation_endpoints import (
            GenerateDocumentationRequest,
            generate_documentation,
        )

        mock_agent = MagicMock()

        request = GenerateDocumentationRequest(
            repository_id="test-repo",
            diagram_types=["invalid_type"],  # Invalid diagram type
        )

        exc_raised = None
        try:
            await generate_documentation(
                request=request,
                current_user=mock_user,
                agent=mock_agent,
            )
        except Exception as e:
            exc_raised = e

        assert exc_raised is not None
        assert exc_raised.status_code == 400
        assert "Invalid diagram type" in str(exc_raised.detail)

    @pytest.mark.asyncio
    async def test_generate_documentation_insufficient_data_error(self, mock_user):
        """Test generate_documentation handles InsufficientDataError."""
        from src.api.documentation_endpoints import (
            GenerateDocumentationRequest,
            generate_documentation,
        )
        from src.services.documentation.exceptions import InsufficientDataError

        mock_agent = MagicMock()
        mock_agent.generate_documentation = AsyncMock(
            side_effect=InsufficientDataError(
                message="Not enough data",
                confidence=0.3,
                threshold=0.45,
            )
        )

        request = GenerateDocumentationRequest(
            repository_id="test-repo",
            diagram_types=["architecture"],
        )

        exc_raised = None
        try:
            await generate_documentation(
                request=request,
                current_user=mock_user,
                agent=mock_agent,
            )
        except Exception as e:
            exc_raised = e

        assert exc_raised is not None
        assert exc_raised.status_code == 422
        assert exc_raised.detail["error"] == "insufficient_data"
        assert exc_raised.detail["confidence"] == 0.3
        assert exc_raised.detail["threshold"] == 0.45

    @pytest.mark.asyncio
    async def test_generate_documentation_graph_traversal_error(self, mock_user):
        """Test generate_documentation handles GraphTraversalError."""
        from src.api.documentation_endpoints import (
            GenerateDocumentationRequest,
            generate_documentation,
        )
        from src.services.documentation.exceptions import GraphTraversalError

        mock_agent = MagicMock()
        mock_agent.generate_documentation = AsyncMock(
            side_effect=GraphTraversalError(
                message="Graph query failed",
                partial_results=["node1", "node2"],
            )
        )

        request = GenerateDocumentationRequest(
            repository_id="test-repo",
            diagram_types=["architecture"],
        )

        exc_raised = None
        try:
            await generate_documentation(
                request=request,
                current_user=mock_user,
                agent=mock_agent,
            )
        except Exception as e:
            exc_raised = e

        assert exc_raised is not None
        assert exc_raised.status_code == 500
        assert exc_raised.detail["error"] == "graph_traversal_error"
        assert exc_raised.detail["has_partial_results"] is True

    @pytest.mark.asyncio
    async def test_generate_documentation_agent_error(self, mock_user):
        """Test generate_documentation handles DocumentationAgentError."""
        from src.api.documentation_endpoints import (
            GenerateDocumentationRequest,
            generate_documentation,
        )
        from src.services.documentation.exceptions import DocumentationAgentError

        mock_agent = MagicMock()
        mock_agent.generate_documentation = AsyncMock(
            side_effect=DocumentationAgentError(
                message="Documentation generation failed"
            )
        )

        request = GenerateDocumentationRequest(
            repository_id="test-repo",
            diagram_types=["architecture"],
        )

        exc_raised = None
        try:
            await generate_documentation(
                request=request,
                current_user=mock_user,
                agent=mock_agent,
            )
        except Exception as e:
            exc_raised = e

        assert exc_raised is not None
        assert exc_raised.status_code == 500
        assert exc_raised.detail["error"] == "generation_failed"

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_feedback_type(self, mock_user):
        """Test submit_feedback raises HTTPException for invalid feedback_type."""
        from src.api.documentation_endpoints import FeedbackRequest, submit_feedback

        mock_feedback_service = MagicMock()

        request = FeedbackRequest(
            job_id="test-job-123",
            documentation_type="diagram",
            feedback_type="invalid_type",  # Invalid feedback type
            raw_confidence=0.8,
        )

        exc_raised = None
        try:
            await submit_feedback(
                request=request,
                current_user=mock_user,
                feedback_service=mock_feedback_service,
            )
        except Exception as e:
            exc_raised = e

        assert exc_raised is not None
        assert exc_raised.status_code == 400
        assert "Invalid feedback_type" in str(exc_raised.detail)

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_documentation_type(self, mock_user):
        """Test submit_feedback raises HTTPException for invalid documentation_type."""
        from src.api.documentation_endpoints import FeedbackRequest, submit_feedback

        mock_feedback_service = MagicMock()

        request = FeedbackRequest(
            job_id="test-job-123",
            documentation_type="invalid_doc_type",  # Invalid documentation type
            feedback_type="accurate",
            raw_confidence=0.8,
        )

        exc_raised = None
        try:
            await submit_feedback(
                request=request,
                current_user=mock_user,
                feedback_service=mock_feedback_service,
            )
        except Exception as e:
            exc_raised = e

        assert exc_raised is not None
        assert exc_raised.status_code == 400
        assert "Invalid documentation_type" in str(exc_raised.detail)
