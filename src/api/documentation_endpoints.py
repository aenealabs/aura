"""
Documentation API Endpoints
============================

REST API for documentation generation.
ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.
ADR-060: Enterprise Diagram Generation (professional icons, AI generation).

Endpoints:
- POST /api/v1/documentation/generate - Start documentation generation
- GET /api/v1/documentation/{job_id} - Get generation result
- GET /api/v1/documentation/{job_id}/stream - SSE progress stream
- POST /api/v1/documentation/{job_id}/feedback - Submit feedback
- GET /api/v1/documentation/cache/stats - Get cache statistics

Configuration:
- DOCUMENTATION_USE_MOCK: Controls whether to use mock data or real AI APIs
  - "true" (default in dev): Uses mock data for faster iteration
  - "false" (default in qa/prod): Uses real Bedrock/OpenAI/Vertex APIs for
    professional-quality diagrams with official cloud provider icons
- AURA_ENVIRONMENT: Environment name (dev, qa, prod) - affects default behavior

See: docs/configuration/DIAGRAM_SERVICE_CONFIGURATION.md
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone  # noqa: F401 - used in type hints
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.auth import User, get_current_user

# ADR-060: Enterprise Diagram Generation
from src.services.diagrams import (
    AIDiagramGenerator,
    DataClassification,
    DiagramIntent,
    DiagramModelRouter,
    GenerationResult,
    GenerationStatus,
    IconColorMode,
    IconLibrary,
    LayoutEngine,
    RenderOptions,
    SVGRenderer,
)
from src.services.documentation import (
    DiagramType,
    DocumentationAgentError,
    DocumentationRequest,
    GraphTraversalError,
    InsufficientDataError,
)
from src.services.documentation.confidence_calibration import (
    CalibratedConfidenceScorer,
    CalibrationMetricsService,
    DocumentationType,
    FeedbackLearningService,
    FeedbackRecord,
    FeedbackType,
    create_calibrated_scorer,
    create_feedback_service,
    create_metrics_service,
)
from src.services.documentation.documentation_agent import (
    DocumentationAgent,
    create_documentation_agent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documentation", tags=["documentation"])

# Global service instances (initialized lazily)
_agent: DocumentationAgent | None = None
_feedback_service: FeedbackLearningService | None = None
_metrics_service: CalibrationMetricsService | None = None
_calibration_scorers: dict[str, CalibratedConfidenceScorer] = {}

# ADR-060: Enterprise Diagram Generation instances
_ai_diagram_generator: AIDiagramGenerator | None = None
_icon_library: IconLibrary | None = None
_svg_renderer: SVGRenderer | None = None
_layout_engine: LayoutEngine | None = None


def _should_use_mock() -> bool:
    """
    Determine whether to use mock mode for documentation services.

    Environment Variable: DOCUMENTATION_USE_MOCK
        - "true": Force mock mode (fast iteration, no API costs)
        - "false": Force real API mode (professional diagrams)
        - Not set: Auto-detect based on AURA_ENVIRONMENT

    Environment Defaults:
        - dev: use_mock=True (flexibility for development)
        - qa: use_mock=False (test real diagram quality)
        - prod: use_mock=False (production-quality output)

    Real API mode enables:
        - Official AWS/Azure/GCP cloud provider icons
        - AI-powered natural language diagram generation
        - Professional layout via ELK.js engine
        - Multi-provider routing (Bedrock, OpenAI, Vertex)

    See: docs/configuration/DIAGRAM_SERVICE_CONFIGURATION.md
    """
    # Check for explicit override
    explicit_mock = os.environ.get("DOCUMENTATION_USE_MOCK", "").lower()
    if explicit_mock == "true":
        return True
    if explicit_mock == "false":
        return False

    # Auto-detect based on environment
    environment = os.environ.get("AURA_ENVIRONMENT", "dev").lower()

    # ADR-060: All environments default to real API mode for professional diagrams
    # Mock mode only enabled via explicit DOCUMENTATION_USE_MOCK=true
    # This ensures users get proper AWS icons and AI-powered generation
    use_mock = False

    logger.info(
        f"Documentation service mode: {'mock' if use_mock else 'real API'} "
        f"(environment={environment}, explicit_override={explicit_mock or 'none'})"
    )

    return use_mock


def get_documentation_agent() -> DocumentationAgent:
    """Get or create the documentation agent."""
    global _agent
    if _agent is None:
        use_mock = _should_use_mock()
        _agent = create_documentation_agent(use_mock=use_mock)
    return _agent


def get_feedback_service() -> FeedbackLearningService:
    """Get or create the feedback learning service."""
    global _feedback_service
    if _feedback_service is None:
        use_mock = _should_use_mock()
        _feedback_service = create_feedback_service(use_mock=use_mock)
    return _feedback_service


def get_metrics_service() -> CalibrationMetricsService:
    """Get or create the calibration metrics service."""
    global _metrics_service
    if _metrics_service is None:
        use_mock = _should_use_mock()
        _metrics_service = create_metrics_service(use_mock=use_mock)
    return _metrics_service


def get_calibration_scorer(organization_id: str) -> CalibratedConfidenceScorer:
    """Get or create a calibration scorer for an organization."""
    global _calibration_scorers
    if organization_id not in _calibration_scorers:
        _calibration_scorers[organization_id] = create_calibrated_scorer(
            organization_id=organization_id
        )
    return _calibration_scorers[organization_id]


def get_ai_diagram_generator() -> AIDiagramGenerator:
    """Get or create the AI diagram generator (ADR-060)."""
    global _ai_diagram_generator
    if _ai_diagram_generator is None:
        import boto3

        use_mock = _should_use_mock()
        if use_mock:
            # Mock mode - create generator without real clients
            _ai_diagram_generator = _create_mock_ai_generator()
        else:
            # Real mode - create with Bedrock client
            # Get region from environment, with sensible default
            region = os.environ.get(
                "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
            )
            ssm_client = boto3.client("ssm", region_name=region)
            cloudwatch_client = boto3.client("cloudwatch", region_name=region)
            environment = os.environ.get("AURA_ENVIRONMENT", "dev")

            router = DiagramModelRouter(
                ssm_client=ssm_client,
                cloudwatch_client=cloudwatch_client,
                environment=environment,
            )
            _ai_diagram_generator = AIDiagramGenerator(router=router)

    return _ai_diagram_generator


def _create_mock_ai_generator() -> "MockAIDiagramGenerator":
    """Create a mock AI diagram generator for development."""
    return MockAIDiagramGenerator()


class MockAIDiagramGenerator:
    """
    Mock AI diagram generator that returns realistic diagrams with proper icons.

    Used in dev environment when real Bedrock API isn't available.
    Produces valid DSL with AWS icons for testing the rendering pipeline.
    """

    def __init__(self):
        from src.services.diagrams.diagram_dsl import DiagramDSLParser

        self.parser = DiagramDSLParser()

    async def generate(
        self,
        description: str,
        classification=None,
        enable_critique: bool = True,
        context=None,
    ) -> GenerationResult:
        """Generate a mock diagram with proper AWS icons."""
        # Parse the description to determine diagram type
        desc_lower = description.lower()

        # Select appropriate mock DSL based on prompt keywords
        if "architecture" in desc_lower or "system" in desc_lower:
            dsl_text = self._get_architecture_dsl()
        elif "data" in desc_lower or "flow" in desc_lower:
            dsl_text = self._get_dataflow_dsl()
        else:
            dsl_text = self._get_architecture_dsl()

        # Parse DSL to diagram
        try:
            parse_result = self.parser.parse(dsl_text)
            return GenerationResult(
                status=GenerationStatus.COMPLETED,
                diagram=parse_result.definition,
                dsl_text=dsl_text,
                intent=DiagramIntent(
                    title="Project Aura Architecture",
                    diagram_type="architecture",
                    components=["EKS", "Neptune", "OpenSearch", "Bedrock"],
                    relationships=[],
                    style_hints=[],
                    cloud_provider="aws",
                    confidence=0.94,
                ),
                iterations=1,
            )
        except Exception as e:
            logger.error(f"Mock DSL parsing failed: {e}")
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error=str(e),
            )

    def _get_architecture_dsl(self) -> str:
        """Return mock architecture DSL with proper AWS icons."""
        return """title: Project Aura - System Architecture
direction: TB
nodes:
  - id: alb
    label: Load Balancer
    icon: aws:alb
    shape: rectangle
  - id: eks
    label: Amazon EKS
    icon: aws:eks
    shape: rectangle
  - id: bedrock
    label: Amazon Bedrock
    icon: aws:bedrock
    shape: rectangle
  - id: neptune
    label: Neptune
    icon: aws:neptune
    shape: cylinder
  - id: opensearch
    label: OpenSearch
    icon: aws:opensearch
    shape: cylinder
  - id: s3
    label: S3
    icon: aws:s3
    shape: cylinder
connections:
  - source: alb
    target: eks
    style: solid
    arrow: forward
  - source: eks
    target: bedrock
    style: dashed
    arrow: forward
  - source: eks
    target: neptune
    style: solid
    arrow: forward
  - source: eks
    target: opensearch
    style: solid
    arrow: forward
  - source: eks
    target: s3
    style: solid
    arrow: forward
"""

    def _get_dataflow_dsl(self) -> str:
        """Return mock data flow DSL with proper AWS icons."""
        return """title: Project Aura - Data Flow
direction: LR
groups:
  - id: ingestion
    label: Data Ingestion
    children: [api, eventbridge]
  - id: processing
    label: Processing
    children: [lambda, step_functions]
  - id: storage
    label: Storage
    children: [s3, dynamodb]
nodes:
  - id: api
    label: API Gateway
    icon: aws:api-gateway
    shape: rectangle
  - id: eventbridge
    label: EventBridge
    icon: aws:eventbridge
    shape: rectangle
  - id: lambda
    label: Lambda
    icon: aws:lambda
    shape: rectangle
  - id: step_functions
    label: Step Functions
    icon: aws:step-functions
    shape: rectangle
  - id: s3
    label: S3
    icon: aws:s3
    shape: cylinder
  - id: dynamodb
    label: DynamoDB
    icon: aws:dynamodb
    shape: cylinder
connections:
  - source: api
    target: lambda
    style: solid
    arrow: forward
  - source: eventbridge
    target: step_functions
    style: solid
    arrow: forward
  - source: lambda
    target: s3
    style: solid
    arrow: forward
  - source: step_functions
    target: dynamodb
    style: solid
    arrow: forward
"""


def get_icon_library() -> IconLibrary:
    """Get or create the icon library (ADR-060)."""
    global _icon_library
    if _icon_library is None:
        _icon_library = IconLibrary(color_mode=IconColorMode.NATIVE)
    return _icon_library


def get_svg_renderer() -> SVGRenderer:
    """Get or create the SVG renderer (ADR-060)."""
    global _svg_renderer
    if _svg_renderer is None:
        icon_lib = get_icon_library()
        _svg_renderer = SVGRenderer(icon_library=icon_lib)
    return _svg_renderer


def get_layout_engine() -> LayoutEngine:
    """Get or create the layout engine (ADR-060)."""
    global _layout_engine
    if _layout_engine is None:
        _layout_engine = LayoutEngine()
    return _layout_engine


# Request/Response Models


class GenerationMode(str, Enum):
    """Mode for diagram generation (ADR-060)."""

    CODE_ANALYSIS = "CODE_ANALYSIS"  # Analyze repo code → Mermaid diagrams
    AI_PROMPT = "AI_PROMPT"  # Natural language prompt → Professional SVG


class RenderEngine(str, Enum):
    """Rendering engine for diagrams (ADR-060)."""

    MERMAID = "mermaid"  # Mermaid.js for code analysis
    AURA_SVG = "aura_svg"  # Aura's professional SVG with cloud icons (default)
    ERASER_API = "eraser_api"  # Eraser.io API (requires ERASER_API_KEY)
    # Legacy alias
    ERASER = "aura_svg"  # Alias for backwards compatibility


class GenerateDocumentationRequest(BaseModel):
    """Request to generate documentation."""

    repository_id: str = Field(
        default="",
        description="Repository ID to document (required for CODE_ANALYSIS mode)",
    )
    diagram_types: list[str] = Field(
        default=["architecture", "data_flow"],
        description="Types of diagrams to generate",
    )
    include_report: bool = Field(default=True, description="Include technical report")
    max_services: int = Field(
        default=20, ge=1, le=50, description="Maximum services to detect"
    )
    min_confidence: float = Field(
        default=0.45, ge=0.0, le=1.0, description="Minimum confidence threshold"
    )

    # ADR-060: AI Prompt Mode fields
    mode: GenerationMode = Field(
        default=GenerationMode.CODE_ANALYSIS,
        description="Generation mode: CODE_ANALYSIS (repo analysis) or AI_PROMPT (natural language)",
    )
    prompt: str = Field(
        default="",
        description="Natural language prompt describing the diagram (required for AI_PROMPT mode)",
    )
    render_engine: RenderEngine = Field(
        default=RenderEngine.MERMAID,
        description="Rendering engine: mermaid (code analysis), aura_svg (default professional), or eraser_api (requires API key)",
    )
    eraser_api_key: str = Field(
        default="",
        description="Optional Eraser.io API key for eraser_api render engine",
    )


class DiagramResponse(BaseModel):
    """Response containing a generated diagram."""

    diagram_type: str
    mermaid_code: str = ""  # For CODE_ANALYSIS mode
    svg_content: str = ""  # For AI_PROMPT mode (ADR-060)
    dsl_content: str = ""  # The source DSL for editing (ADR-060)
    confidence: float
    confidence_level: str
    warnings: list[str] = []
    render_engine: str = "mermaid"  # "mermaid" or "eraser"


class ServiceBoundaryResponse(BaseModel):
    """Response containing a service boundary."""

    boundary_id: str
    name: str
    description: str
    confidence: float
    confidence_level: str
    node_count: int
    edges_internal: int
    edges_external: int
    modularity_ratio: float


class ReportResponse(BaseModel):
    """Response containing a technical report."""

    title: str
    executive_summary: str
    markdown: str
    confidence: float
    confidence_level: str
    section_count: int


class DocumentationResponse(BaseModel):
    """Response containing complete documentation."""

    job_id: str
    repository_id: str
    diagrams: list[DiagramResponse]
    report: ReportResponse | None = None
    service_boundaries: list[ServiceBoundaryResponse]
    confidence: float
    confidence_level: str
    generated_at: str
    generation_time_ms: float
    cached: bool = False


class FeedbackRequest(BaseModel):
    """Request to submit feedback on documentation."""

    job_id: str = Field(..., description="Job ID for the documentation")
    documentation_type: str = Field(
        default="diagram",
        description="Type of documentation (diagram, report, service_boundary, data_flow)",
    )
    diagram_type: str = Field(default="", description="Diagram type if applicable")
    feedback_type: str = Field(
        ..., description="Feedback type: accurate, inaccurate, or partial"
    )
    raw_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Original confidence score"
    )
    correction_text: str = Field(default="", description="Optional correction text")
    notes: str = Field(default="", description="Additional notes")


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""

    feedback_id: str
    status: str
    message: str
    calibration_status: dict[str, Any] = Field(
        default_factory=dict, description="Current calibration status"
    )


class CalibrationStatsResponse(BaseModel):
    """Response containing calibration statistics."""

    is_calibrated: bool
    sample_count: int
    min_samples_required: int
    model_version: int
    ece_before: float
    ece_after: float
    ece_improvement_percent: float
    organization_id: str
    documentation_type: str


class FeedbackStatsResponse(BaseModel):
    """Response containing feedback statistics."""

    total_feedback: int
    accurate_count: int
    inaccurate_count: int
    partial_count: int
    accuracy_rate: float


class CacheStatsResponse(BaseModel):
    """Response containing cache statistics."""

    memory: dict[str, Any]
    redis: dict[str, Any]
    s3: dict[str, Any]
    total: dict[str, Any]


# Helper functions


def _build_documentation_response(result: Any) -> DocumentationResponse:
    """Convert DocumentationResult to API response."""
    from src.services.documentation.types import ConfidenceLevel

    diagrams = [
        DiagramResponse(
            diagram_type=d.diagram_type.value,
            mermaid_code=d.mermaid_code,
            svg_content="",  # CODE_ANALYSIS mode uses Mermaid
            dsl_content="",
            confidence=d.confidence,
            confidence_level=d.confidence_level.value,
            warnings=d.warnings,
            render_engine="mermaid",
        )
        for d in result.diagrams
    ]

    boundaries = [
        ServiceBoundaryResponse(
            boundary_id=b.boundary_id,
            name=b.name,
            description=b.description,
            confidence=b.confidence,
            confidence_level=b.confidence_level.value,
            node_count=len(b.node_ids),
            edges_internal=b.edges_internal,
            edges_external=b.edges_external,
            modularity_ratio=b.modularity_ratio,
        )
        for b in result.service_boundaries
    ]

    report = None
    if result.report:
        report = ReportResponse(
            title=result.report.title,
            executive_summary=result.report.executive_summary,
            markdown=result.report.to_markdown(),
            confidence=result.report.confidence,
            confidence_level=result.report.confidence_level.value,
            section_count=len(result.report.sections),
        )

    return DocumentationResponse(
        job_id=result.job_id,
        repository_id=result.repository_id,
        diagrams=diagrams,
        report=report,
        service_boundaries=boundaries,
        confidence=result.confidence,
        confidence_level=ConfidenceLevel.from_score(result.confidence).value,
        generated_at=result.generated_at.isoformat(),
        generation_time_ms=result.generation_time_ms,
        cached=result.metadata.get("cached", False),
    )


# Endpoints


@router.post("/generate", response_model=DocumentationResponse)
async def generate_documentation(
    request: GenerateDocumentationRequest,
    current_user: User = Depends(get_current_user),
    agent: DocumentationAgent = Depends(get_documentation_agent),
) -> DocumentationResponse:
    """
    Generate documentation for a repository.

    This endpoint triggers documentation generation including:
    - Service boundary detection
    - Architecture diagrams
    - Data flow diagrams
    - Technical report

    Supports two modes (ADR-060):
    - CODE_ANALYSIS: Analyze repository code to generate Mermaid diagrams
    - AI_PROMPT: Use natural language to generate professional SVG diagrams
      with official AWS/Azure/GCP icons

    Results are cached for performance.
    """
    logger.info(
        f"Documentation request: repo={request.repository_id}, "
        f"mode={request.mode.value}, user={current_user.sub}"
    )

    # Route based on generation mode (ADR-060)
    if request.mode == GenerationMode.AI_PROMPT:
        return await _generate_ai_prompt_diagram(request, current_user)
    else:
        return await _generate_code_analysis_diagram(request, current_user, agent)


async def _generate_ai_prompt_diagram(
    request: GenerateDocumentationRequest,
    current_user: User,
) -> DocumentationResponse:
    """
    Generate diagram from AI prompt using ADR-060 services.

    Supports two rendering backends:
    - AURA_SVG (default): Aura's built-in professional SVG renderer
    - ERASER_API: Eraser.io API for external diagram generation

    This path uses:
    - AIDiagramGenerator for natural language → DSL
    - LayoutEngine for constraint-based positioning
    - SVGRenderer for professional output with cloud icons
    """
    if not request.prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="Prompt is required for AI_PROMPT mode",
        )

    # Check if user wants Eraser.io API
    if request.render_engine == RenderEngine.ERASER_API:
        return await _generate_eraser_api_diagram(request, current_user)

    # Default: Use Aura's built-in SVG renderer
    return await _generate_aura_svg_diagram(request, current_user)


async def _generate_aura_svg_diagram(
    request: GenerateDocumentationRequest,
    current_user: User,
) -> DocumentationResponse:
    """
    Generate diagram using Aura's built-in professional SVG renderer.

    Features:
    - Official AWS/Azure/GCP cloud icons
    - Orthogonal edge routing with rounded corners
    - Clean, professional card-style nodes
    - WCAG AA compliant colors
    """
    import uuid

    try:
        start_time = datetime.utcnow()
        job_id = f"doc-{uuid.uuid4().hex[:12]}"

        # Get ADR-060 services
        ai_generator = get_ai_diagram_generator()
        layout_engine = get_layout_engine()
        svg_renderer = get_svg_renderer()

        # Generate diagram from prompt
        logger.info(
            f"Generating Aura SVG diagram from prompt: {request.prompt[:100]}..."
        )

        generation_result = await ai_generator.generate(
            description=request.prompt,
            classification=DataClassification.INTERNAL,
            enable_critique=True,
        )

        if generation_result.status == GenerationStatus.FAILED:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "generation_failed",
                    "message": generation_result.error
                    or "AI diagram generation failed",
                },
            )

        # Apply layout to position nodes
        if generation_result.diagram:
            layout_result = layout_engine.layout(generation_result.diagram)
            laid_out_diagram = layout_result.definition
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "generation_failed",
                    "message": "No diagram generated",
                },
            )

        # Render to SVG with professional icons
        render_options = RenderOptions(
            show_icons=True,
            icon_color_mode=IconColorMode.NATIVE,
            include_styles=True,
        )
        svg_content = svg_renderer.render(laid_out_diagram, options=render_options)

        # Calculate timing
        end_time = datetime.utcnow()
        generation_time_ms = (end_time - start_time).total_seconds() * 1000

        # Build response with SVG diagram
        diagram_response = DiagramResponse(
            diagram_type="architecture",
            mermaid_code="",  # Not used in AI_PROMPT mode
            svg_content=svg_content,
            dsl_content=generation_result.dsl_text,
            confidence=(
                generation_result.intent.confidence
                if generation_result.intent
                else 0.85
            ),
            confidence_level=(
                "high"
                if (
                    generation_result.intent
                    and generation_result.intent.confidence >= 0.7
                )
                else "medium"
            ),
            warnings=[],
            render_engine="aura_svg",
        )

        return DocumentationResponse(
            job_id=job_id,
            repository_id=request.repository_id or "ai-generated",
            diagrams=[diagram_response],
            report=None,
            service_boundaries=[],
            confidence=(
                generation_result.intent.confidence
                if generation_result.intent
                else 0.85
            ),
            confidence_level="high",
            generated_at=end_time.isoformat(),
            generation_time_ms=generation_time_ms,
            cached=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Aura SVG diagram generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "generation_failed", "message": str(e)},
        )


async def _generate_eraser_api_diagram(
    request: GenerateDocumentationRequest,
    current_user: User,
) -> DocumentationResponse:
    """
    Generate diagram using Eraser.io's external API.

    Requires:
    - User-provided ERASER_API_KEY in request, or
    - ERASER_API_KEY environment variable

    Returns Eraser.io-generated PNG/SVG diagrams with professional styling.
    """
    import uuid

    from src.services.diagrams.eraser_client import (
        EraserApiError,
        EraserClient,
        EraserDiagramType,
    )

    try:
        start_time = datetime.utcnow()
        job_id = f"doc-{uuid.uuid4().hex[:12]}"

        # Get API key from request or environment
        api_key = request.eraser_api_key or os.environ.get("ERASER_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "configuration_error",
                    "message": "Eraser.io API key required. Provide eraser_api_key in request or set ERASER_API_KEY environment variable.",
                },
            )

        # Create Eraser client and generate diagram
        client = EraserClient(api_key=api_key)

        logger.info(
            f"Generating Eraser.io diagram from prompt: {request.prompt[:100]}..."
        )

        result = await client.generate_diagram(
            prompt=request.prompt,
            diagram_type=EraserDiagramType.CLOUD_ARCHITECTURE,
            create_file=False,  # Don't create editable file by default
        )

        # Calculate timing
        end_time = datetime.utcnow()
        generation_time_ms = (end_time - start_time).total_seconds() * 1000

        # Build response with Eraser image URL
        # Note: Eraser returns an image URL, not inline SVG
        diagram_response = DiagramResponse(
            diagram_type="architecture",
            mermaid_code="",
            svg_content=f'<img src="{result.image_url}" alt="Architecture Diagram" />',
            dsl_content=result.dsl_code,
            confidence=0.95,  # Eraser.io produces high-quality results
            confidence_level="high",
            warnings=[],
            render_engine="eraser_api",
        )

        return DocumentationResponse(
            job_id=job_id,
            repository_id=request.repository_id or "ai-generated",
            diagrams=[diagram_response],
            report=None,
            service_boundaries=[],
            confidence=0.95,
            confidence_level="high",
            generated_at=end_time.isoformat(),
            generation_time_ms=generation_time_ms,
            cached=False,
        )

    except EraserApiError as e:
        logger.error(f"Eraser.io API error: {e}")
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": "eraser_api_error", "message": str(e)},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eraser.io diagram generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "generation_failed", "message": str(e)},
        )


async def _generate_code_analysis_diagram(
    request: GenerateDocumentationRequest,
    current_user: User,
    agent: DocumentationAgent,
) -> DocumentationResponse:
    """
    Generate diagram from code analysis (original flow).

    This path uses:
    - DocumentationAgent for repository analysis
    - Mermaid.js for diagram rendering
    """
    if not request.repository_id:
        raise HTTPException(
            status_code=400,
            detail="repository_id is required for CODE_ANALYSIS mode",
        )

    try:
        # Parse diagram types
        diagram_types = []
        for dt in request.diagram_types:
            try:
                diagram_types.append(DiagramType(dt))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid diagram type: {dt}. "
                    f"Valid types: {[d.value for d in DiagramType]}",
                )

        # Build request
        doc_request = DocumentationRequest(
            repository_id=request.repository_id,
            diagram_types=diagram_types,
            include_report=request.include_report,
            max_services=request.max_services,
            min_confidence=request.min_confidence,
            metadata={"user_id": current_user.sub},
        )

        # Generate documentation
        result = await agent.generate_documentation(doc_request)

        return _build_documentation_response(result)

    except InsufficientDataError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "insufficient_data",
                "message": str(e),
                "confidence": e.confidence,
                "threshold": e.threshold,
            },
        )
    except GraphTraversalError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "graph_traversal_error",
                "message": str(e),
                "has_partial_results": e.has_partial_results,
            },
        )
    except DocumentationAgentError as e:
        logger.error(f"Documentation generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "generation_failed", "message": str(e)},
        )


@router.get("/generate/{repository_id}/stream")
async def stream_documentation_generation(
    repository_id: str,
    diagram_types: str = Query(
        default="architecture,data_flow",
        description="Comma-separated diagram types",
    ),
    include_report: bool = Query(default=True),
    current_user: User = Depends(get_current_user),
    agent: DocumentationAgent = Depends(get_documentation_agent),
) -> StreamingResponse:
    """
    Stream documentation generation progress.

    Returns Server-Sent Events (SSE) with progress updates.

    Event types:
    - progress: Generation progress update
    - complete: Generation complete with result
    - error: Generation failed
    """
    logger.info(
        f"Streaming documentation: repo={repository_id}, user={current_user.sub}"
    )

    # Parse diagram types
    try:
        types = [DiagramType(dt.strip()) for dt in diagram_types.split(",")]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid diagram type: {e}")

    request = DocumentationRequest(
        repository_id=repository_id,
        diagram_types=types,
        include_report=include_report,
        metadata={"user_id": current_user.sub},
    )

    async def event_generator():
        """Generate SSE events."""
        try:
            async for progress in agent.generate_documentation_stream(request):
                event_data = {
                    "phase": progress.phase,
                    "progress": progress.progress,
                    "message": progress.message,
                    "current_step": progress.current_step,
                    "total_steps": progress.total_steps,
                }

                if progress.phase == "complete":
                    # Include result in final event
                    event_data["result"] = progress.metadata.get("result")
                    yield f"event: complete\ndata: {json.dumps(event_data)}\n\n"
                elif progress.phase == "error":
                    event_data["error"] = progress.metadata.get("error")
                    yield f"event: error\ndata: {json.dumps(event_data)}\n\n"
                else:
                    yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"

                # Small delay to allow client processing
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Stream error: {e}")
            error_data = {"error": str(e), "phase": "error", "progress": 0}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    feedback_service: FeedbackLearningService = Depends(get_feedback_service),
) -> FeedbackResponse:
    """
    Submit feedback on generated documentation.

    Feedback is used to improve the calibration of confidence scores
    and the accuracy of future documentation generation.

    The feedback is stored in DynamoDB and used for training isotonic
    regression calibrators that improve confidence score accuracy.
    """
    import uuid

    logger.info(
        f"Feedback submitted: job={request.job_id}, "
        f"type={request.documentation_type}, feedback={request.feedback_type}, "
        f"user={current_user.sub}"
    )

    # Parse feedback type
    try:
        feedback_type = FeedbackType(request.feedback_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feedback_type: {request.feedback_type}. "
            f"Valid types: accurate, inaccurate, partial",
        )

    # Parse documentation type
    try:
        doc_type = DocumentationType(request.documentation_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid documentation_type: {request.documentation_type}. "
            f"Valid types: diagram, report, service_boundary, data_flow",
        )

    feedback_id = f"fb-{uuid.uuid4().hex[:12]}"

    # Extract organization from user (assuming it's in the user object)
    organization_id = getattr(current_user, "organization_id", "default")

    # Create feedback record
    feedback_record = FeedbackRecord(
        feedback_id=feedback_id,
        job_id=request.job_id,
        organization_id=organization_id,
        documentation_type=doc_type,
        raw_confidence=request.raw_confidence,
        feedback_type=feedback_type,
        user_id=current_user.sub,
        diagram_type=request.diagram_type,
        correction_text=request.correction_text,
        metadata={"notes": request.notes} if request.notes else {},
    )

    # Store feedback
    success = feedback_service.store_feedback(feedback_record)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to store feedback",
        )

    # Get calibration scorer for this organization
    scorer = get_calibration_scorer(organization_id)
    calibration_status = scorer.get_stats()

    return FeedbackResponse(
        feedback_id=feedback_id,
        status="accepted",
        message="Thank you for your feedback. It will be used to improve future documentation.",
        calibration_status={
            "is_calibrated": calibration_status["is_calibrated"],
            "sample_count": calibration_status["sample_count"],
            "samples_until_calibration": max(
                0,
                calibration_status["min_samples_required"]
                - calibration_status["sample_count"],
            ),
        },
    )


@router.get("/calibration/stats", response_model=CalibrationStatsResponse)
async def get_calibration_stats(
    current_user: User = Depends(get_current_user),
) -> CalibrationStatsResponse:
    """
    Get calibration statistics for the user's organization.

    Returns information about the isotonic regression calibrator
    including sample count, ECE improvement, and calibration status.
    """
    organization_id = getattr(current_user, "organization_id", "default")
    scorer = get_calibration_scorer(organization_id)
    stats = scorer.get_stats()

    return CalibrationStatsResponse(
        is_calibrated=stats["is_calibrated"],
        sample_count=stats["sample_count"],
        min_samples_required=stats["min_samples_required"],
        model_version=stats["model_version"],
        ece_before=stats["ece_before"],
        ece_after=stats["ece_after"],
        ece_improvement_percent=stats["ece_improvement"],
        organization_id=stats["organization_id"],
        documentation_type=stats["documentation_type"],
    )


@router.get("/feedback/stats", response_model=FeedbackStatsResponse)
async def get_feedback_stats(
    current_user: User = Depends(get_current_user),
    feedback_service: FeedbackLearningService = Depends(get_feedback_service),
) -> FeedbackStatsResponse:
    """
    Get feedback statistics for the user's organization.

    Returns counts of feedback by type and overall accuracy rate.
    """
    organization_id = getattr(current_user, "organization_id", "default")
    stats = feedback_service.get_stats(organization_id)

    return FeedbackStatsResponse(
        total_feedback=stats.get("total_feedback", 0),
        accurate_count=stats.get("accurate_count", 0),
        inaccurate_count=stats.get("inaccurate_count", 0),
        partial_count=stats.get("partial_count", 0),
        accuracy_rate=stats.get("accuracy_rate", 0.0),
    )


@router.post("/calibration/train")
async def trigger_calibration_training(
    current_user: User = Depends(get_current_user),
    feedback_service: FeedbackLearningService = Depends(get_feedback_service),
    metrics_service: CalibrationMetricsService = Depends(get_metrics_service),
) -> dict[str, Any]:
    """
    Trigger calibration training for the user's organization.

    This endpoint manually triggers calibrator training using collected
    feedback. Normally this runs as a nightly batch job.

    Returns:
        Training result with ECE before/after and improvement percentage
    """
    organization_id = getattr(current_user, "organization_id", "default")
    scorer = get_calibration_scorer(organization_id)

    # Get all feedback for this organization
    feedback_records = feedback_service.get_feedback_for_calibration(organization_id)

    if len(feedback_records) < scorer.min_samples:
        return {
            "status": "insufficient_data",
            "message": f"Need at least {scorer.min_samples} samples for calibration. "
            f"Currently have {len(feedback_records)}.",
            "sample_count": len(feedback_records),
            "samples_needed": scorer.min_samples - len(feedback_records),
        }

    # Extract raw scores and outcomes
    raw_scores = [r.raw_confidence for r in feedback_records]
    actual_outcomes = [r.actual_accuracy for r in feedback_records]

    # Train calibrator
    success = scorer.fit(raw_scores, actual_outcomes)

    if not success:
        return {
            "status": "training_failed",
            "message": "Failed to train calibrator",
        }

    # Record metrics
    stats = scorer.get_stats()
    metrics_service.record_calibration_event(
        organization_id=organization_id,
        sample_count=stats["sample_count"],
        ece_before=stats["ece_before"],
        ece_after=stats["ece_after"],
        model_version=stats["model_version"],
    )

    return {
        "status": "success",
        "message": "Calibrator trained successfully",
        "sample_count": stats["sample_count"],
        "ece_before": stats["ece_before"],
        "ece_after": stats["ece_after"],
        "ece_improvement_percent": stats["ece_improvement"],
        "model_version": stats["model_version"],
    }


@router.post("/calibrate")
async def calibrate_confidence(
    raw_score: float = Query(..., ge=0.0, le=1.0, description="Raw confidence score"),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Calibrate a raw confidence score.

    If the organization has a trained calibrator, returns the calibrated
    score. Otherwise returns the raw score.
    """
    organization_id = getattr(current_user, "organization_id", "default")
    scorer = get_calibration_scorer(organization_id)

    calibrated_score = scorer.calibrate(raw_score)

    return {
        "raw_score": raw_score,
        "calibrated_score": calibrated_score,
        "is_calibrated": scorer.is_calibrated,
        "model_version": scorer.model_version,
    }


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    current_user: User = Depends(get_current_user),
    agent: DocumentationAgent = Depends(get_documentation_agent),
) -> CacheStatsResponse:
    """
    Get documentation cache statistics.

    Returns hit/miss rates for all cache tiers.
    """
    stats = agent.get_cache_stats()

    return CacheStatsResponse(
        memory=stats["memory"],
        redis=stats["redis"],
        s3=stats["s3"],
        total=stats["total"],
    )


@router.delete("/cache/{repository_id}")
async def invalidate_cache(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    agent: DocumentationAgent = Depends(get_documentation_agent),
) -> dict[str, Any]:
    """
    Invalidate cached documentation for a repository.

    Call this when a repository is re-ingested to clear stale documentation.
    """
    logger.info(f"Cache invalidation: repo={repository_id}, user={current_user.sub}")

    count = agent.invalidate_cache(repository_id)

    return {
        "status": "success",
        "repository_id": repository_id,
        "entries_invalidated": count,
    }


@router.get("/diagram-types")
async def get_diagram_types() -> list[dict[str, str]]:
    """
    Get available diagram types.

    Returns list of diagram types for UI dropdown.
    """
    return [
        {"value": dt.value, "label": dt.value.replace("_", " ").title()}
        for dt in DiagramType
    ]


@router.post("/diagram-test")
async def test_diagram_generation(
    request: GenerateDocumentationRequest,
    use_real_llm: bool = False,
) -> DocumentationResponse:
    """
    Test endpoint for diagram generation (no auth required).

    For local development testing only.

    Args:
        request: Diagram generation request
        use_real_llm: If True, use real Bedrock API instead of mock data.
                      Requires valid AWS credentials. Default: False (mock mode)
    """
    import time
    import uuid

    # Only allow in dev environment
    env = os.environ.get("AURA_ENVIRONMENT", "dev")
    if env not in ("dev", "test"):
        raise HTTPException(
            status_code=403,
            detail="Test endpoint only available in dev/test environments",
        )

    try:
        job_id = f"test-{uuid.uuid4().hex[:12]}"
        prompt = request.prompt or "AWS architecture diagram"
        start_time = time.time()

        # Choose generator based on use_real_llm flag
        if use_real_llm:
            logger.info(f"Using real LLM for diagram generation: {prompt[:50]}...")
            generator = get_ai_diagram_generator()
        else:
            generator = _create_mock_ai_generator()

        generation_result = await generator.generate(
            description=prompt,
            classification=DataClassification.INTERNAL,
        )

        if generation_result.status == GenerationStatus.FAILED:
            raise HTTPException(
                status_code=500,
                detail=generation_result.error or "Generation failed",
            )

        # Apply layout to position nodes
        layout_engine = get_layout_engine()
        layout_result = layout_engine.layout(generation_result.diagram)
        laid_out_diagram = layout_result.definition

        # Render to SVG with professional icons
        svg_renderer = get_svg_renderer()
        render_options = RenderOptions(
            show_icons=True,
            icon_color_mode=IconColorMode.NATIVE,
            include_styles=True,
        )
        svg_content = svg_renderer.render(laid_out_diagram, options=render_options)

        # Build response
        from datetime import datetime

        generation_time_ms = (time.time() - start_time) * 1000
        confidence = (
            generation_result.confidence
            if hasattr(generation_result, "confidence") and generation_result.confidence
            else 0.94
        )
        confidence_level = (
            "high" if confidence >= 0.8 else "medium" if confidence >= 0.5 else "low"
        )

        return DocumentationResponse(
            job_id=job_id,
            repository_id="test-repo",
            diagrams=[
                DiagramResponse(
                    diagram_type="architecture",
                    mermaid_code="",
                    svg_content=svg_content,
                    dsl_content=generation_result.dsl_text,
                    confidence=confidence,
                    confidence_level=confidence_level,
                )
            ],
            service_boundaries=[],
            confidence=confidence,
            confidence_level=confidence_level,
            generated_at=datetime.utcnow().isoformat(),
            generation_time_ms=generation_time_ms,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Diagram test generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
