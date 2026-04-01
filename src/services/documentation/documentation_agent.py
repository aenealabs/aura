"""
Documentation Agent
===================

Main agent for automated documentation generation.
ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.

The DocumentationAgent orchestrates:
- Service boundary detection (Louvain algorithm)
- Diagram generation (Mermaid.js)
- Technical report generation
- 3-tier caching for performance
"""

import logging
import time
import uuid
from typing import TYPE_CHECKING, Any, AsyncIterator

from src.services.documentation.diagram_generator import (
    DiagramGenerator,
    create_diagram_generator,
)
from src.services.documentation.documentation_cache_service import (
    DocumentationCacheService,
    create_documentation_cache_service,
)
from src.services.documentation.exceptions import (
    DocumentationAgentError,
    GraphTraversalError,
    InsufficientDataError,
)
from src.services.documentation.report_generator import (
    ReportGenerator,
    create_report_generator,
)
from src.services.documentation.service_boundary_detector import (
    ServiceBoundaryDetector,
    create_service_boundary_detector,
)
from src.services.documentation.types import (
    DiagramType,
    DocumentationRequest,
    DocumentationResult,
    GenerationProgress,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.agents.context_objects import HybridContext
    from src.agents.monitoring_service import MonitorAgent
    from src.services.bedrock_llm_service import BedrockLLMService
    from src.services.neptune_graph_service import NeptuneGraphService


class DocumentationAgent:
    """
    Agent for generating technical documentation from code analysis.

    The agent coordinates multiple services to:
    1. Detect service boundaries using Louvain community detection
    2. Generate architecture and data flow diagrams
    3. Create comprehensive technical reports
    4. Cache results for performance

    Example:
        >>> agent = create_documentation_agent()
        >>> request = DocumentationRequest(repository_id="my-repo")
        >>> result = await agent.generate_documentation(request)
        >>> print(result.report.to_markdown())
    """

    def __init__(
        self,
        llm_client: "BedrockLLMService | None" = None,
        neptune_service: "NeptuneGraphService | None" = None,
        monitor: "MonitorAgent | None" = None,
        cache_service: DocumentationCacheService | None = None,
        boundary_detector: ServiceBoundaryDetector | None = None,
        diagram_generator: DiagramGenerator | None = None,
        report_generator: ReportGenerator | None = None,
    ):
        """
        Initialize the Documentation Agent.

        Args:
            llm_client: LLM service for enhanced generation
            neptune_service: Neptune graph service for code queries
            monitor: Monitoring agent for metrics
            cache_service: 3-tier cache service
            boundary_detector: Service boundary detector
            diagram_generator: Diagram generator
            report_generator: Report generator
        """
        self.llm = llm_client
        self.neptune = neptune_service
        self.monitor = monitor

        # Initialize sub-services
        self.cache = cache_service or create_documentation_cache_service()
        self.boundary_detector = boundary_detector or create_service_boundary_detector(
            neptune_service=neptune_service
        )
        self.diagram_generator = diagram_generator or create_diagram_generator(
            llm_client=llm_client
        )
        self.report_generator = report_generator or create_report_generator(
            llm_client=llm_client
        )

        logger.info("DocumentationAgent initialized")

    async def generate_documentation(
        self,
        request: DocumentationRequest,
        context: "HybridContext | None" = None,
    ) -> DocumentationResult:
        """
        Generate documentation for a repository.

        Args:
            request: Documentation request with configuration
            context: Optional HybridContext from GraphRAG

        Returns:
            DocumentationResult with diagrams and report

        Raises:
            DocumentationAgentError: If generation fails
        """
        job_id = f"doc-{uuid.uuid4().hex[:12]}"
        start_time = time.time()

        logger.info(
            f"Starting documentation generation: job={job_id}, "
            f"repo={request.repository_id}"
        )

        try:
            # Check cache first
            cache_key = self._build_cache_key(request)
            cached = self.cache.get(cache_key)
            if cached:
                logger.info(f"Cache hit for {request.repository_id}")
                return self._deserialize_result(cached, job_id)

            # Detect service boundaries
            boundaries = await self._detect_boundaries(request)

            # Generate diagrams
            diagrams = []
            for diagram_type in request.diagram_types:
                diagram = self.diagram_generator.generate(
                    diagram_type=diagram_type,
                    boundaries=boundaries,
                    data_flows=[],  # TODO: Implement data flow detection
                )
                diagrams.append(diagram)

            # Generate report if requested
            report = None
            if request.include_report:
                report = await self.report_generator.generate(
                    repository_id=request.repository_id,
                    boundaries=boundaries,
                    data_flows=[],
                    diagrams=diagrams,
                    metadata=request.metadata,
                )

            # Calculate overall confidence
            confidences = [b.confidence for b in boundaries]
            if diagrams:
                confidences.extend(d.confidence for d in diagrams)
            if report:
                confidences.append(report.confidence)

            overall_confidence = (
                sum(confidences) / len(confidences) if confidences else 0.5
            )

            # Build result
            generation_time = (time.time() - start_time) * 1000

            result = DocumentationResult(
                job_id=job_id,
                repository_id=request.repository_id,
                diagrams=diagrams,
                report=report,
                service_boundaries=boundaries,
                data_flows=[],
                confidence=overall_confidence,
                generation_time_ms=generation_time,
                metadata=request.metadata,
            )

            # Cache result
            self.cache.set(cache_key, self._serialize_result(result))

            # Record metrics
            if self.monitor:
                self.monitor.record_agent_activity(
                    tokens_used=0,  # TODO: Track LLM tokens
                    loc_generated=(
                        len(result.report.to_markdown()) if result.report else 0
                    ),
                )

            logger.info(
                f"Documentation generated: job={job_id}, "
                f"services={len(boundaries)}, diagrams={len(diagrams)}, "
                f"confidence={overall_confidence:.2f}, time={generation_time:.0f}ms"
            )

            return result

        except (GraphTraversalError, InsufficientDataError):
            raise
        except Exception as e:
            logger.error(f"Documentation generation failed: {e}", exc_info=True)
            raise DocumentationAgentError(
                f"Documentation generation failed: {e}",
                details={"job_id": job_id, "repository_id": request.repository_id},
            )

    async def generate_documentation_stream(
        self,
        request: DocumentationRequest,
    ) -> AsyncIterator[GenerationProgress]:
        """
        Generate documentation with progress streaming.

        Yields progress updates during generation for real-time UI feedback.

        Args:
            request: Documentation request

        Yields:
            GenerationProgress updates

        Returns:
            Final DocumentationResult is in the last progress metadata
        """
        job_id = f"doc-{uuid.uuid4().hex[:12]}"
        total_steps = 4  # boundaries, diagrams, report, finalize
        current_step = 0

        try:
            # Step 1: Detect boundaries
            yield GenerationProgress(
                phase="boundary_detection",
                progress=10.0,
                message="Detecting service boundaries...",
                current_step=current_step,
                total_steps=total_steps,
            )

            boundaries = await self._detect_boundaries(request)
            current_step += 1

            yield GenerationProgress(
                phase="boundary_detection",
                progress=30.0,
                message=f"Detected {len(boundaries)} services",
                current_step=current_step,
                total_steps=total_steps,
                metadata={"service_count": len(boundaries)},
            )

            # Step 2: Generate diagrams
            diagrams = []
            diagram_count = len(request.diagram_types)
            for i, diagram_type in enumerate(request.diagram_types):
                yield GenerationProgress(
                    phase="diagram_generation",
                    progress=30.0 + (30.0 * (i / diagram_count)),
                    message=f"Generating {diagram_type.value} diagram...",
                    current_step=current_step,
                    total_steps=total_steps,
                )

                diagram = self.diagram_generator.generate(
                    diagram_type=diagram_type,
                    boundaries=boundaries,
                )
                diagrams.append(diagram)

            current_step += 1

            # Step 3: Generate report
            report = None
            if request.include_report:
                yield GenerationProgress(
                    phase="report_generation",
                    progress=70.0,
                    message="Generating technical report...",
                    current_step=current_step,
                    total_steps=total_steps,
                )

                report = await self.report_generator.generate(
                    repository_id=request.repository_id,
                    boundaries=boundaries,
                    diagrams=diagrams,
                )

            current_step += 1

            # Step 4: Finalize
            yield GenerationProgress(
                phase="finalization",
                progress=90.0,
                message="Finalizing documentation...",
                current_step=current_step,
                total_steps=total_steps,
            )

            # Build result
            confidences = [b.confidence for b in boundaries]
            if diagrams:
                confidences.extend(d.confidence for d in diagrams)
            if report:
                confidences.append(report.confidence)

            overall_confidence = (
                sum(confidences) / len(confidences) if confidences else 0.5
            )

            result = DocumentationResult(
                job_id=job_id,
                repository_id=request.repository_id,
                diagrams=diagrams,
                report=report,
                service_boundaries=boundaries,
                confidence=overall_confidence,
            )

            # Cache result
            cache_key = self._build_cache_key(request)
            self.cache.set(cache_key, self._serialize_result(result))

            current_step += 1

            # Final progress with result
            yield GenerationProgress(
                phase="complete",
                progress=100.0,
                message="Documentation complete",
                current_step=current_step,
                total_steps=total_steps,
                metadata={"result": self._serialize_result(result)},
            )

        except Exception as e:
            logger.error(f"Streaming generation failed: {e}", exc_info=True)
            yield GenerationProgress(
                phase="error",
                progress=0.0,
                message=f"Generation failed: {str(e)}",
                current_step=current_step,
                total_steps=total_steps,
                metadata={"error": str(e)},
            )

    async def _detect_boundaries(self, request: DocumentationRequest) -> list:
        """Detect service boundaries for the repository."""
        try:
            boundaries = await self.boundary_detector.detect_boundaries(
                repository_id=request.repository_id,
                min_service_size=5,
                max_services=request.max_services,
            )

            # Filter by minimum confidence
            boundaries = [
                b for b in boundaries if b.confidence >= request.min_confidence
            ]

            return boundaries

        except InsufficientDataError:
            logger.warning(
                f"Insufficient data for boundary detection: {request.repository_id}"
            )
            return []
        except GraphTraversalError as e:
            logger.warning(f"Graph traversal failed: {e}")
            if e.has_partial_results:
                return e.partial_results
            return []

    def _build_cache_key(self, request: DocumentationRequest) -> str:
        """Build cache key from request."""
        diagram_types = ",".join(sorted(d.value for d in request.diagram_types))
        return (
            f"{request.repository_id}:"
            f"{diagram_types}:"
            f"{request.include_report}:"
            f"{request.min_confidence}"
        )

    def _serialize_result(self, result: DocumentationResult) -> dict[str, Any]:
        """Serialize result for caching."""
        return {
            "job_id": result.job_id,
            "repository_id": result.repository_id,
            "diagrams": [
                {
                    "diagram_type": d.diagram_type.value,
                    "mermaid_code": d.mermaid_code,
                    "confidence": d.confidence,
                    "warnings": d.warnings,
                }
                for d in result.diagrams
            ],
            "report": (
                {
                    "title": result.report.title,
                    "executive_summary": result.report.executive_summary,
                    "confidence": result.report.confidence,
                    "markdown": result.report.to_markdown(),
                }
                if result.report
                else None
            ),
            "service_boundaries": [
                {
                    "boundary_id": b.boundary_id,
                    "name": b.name,
                    "description": b.description,
                    "confidence": b.confidence,
                    "node_count": len(b.node_ids),
                }
                for b in result.service_boundaries
            ],
            "confidence": result.confidence,
            "generated_at": result.generated_at.isoformat(),
            "generation_time_ms": result.generation_time_ms,
        }

    def _deserialize_result(
        self, data: dict[str, Any], job_id: str
    ) -> DocumentationResult:
        """Deserialize result from cache."""
        from datetime import datetime

        from src.services.documentation.types import (
            DiagramResult,
            ServiceBoundary,
            TechnicalReport,
        )

        diagrams = [
            DiagramResult(
                diagram_type=DiagramType(d["diagram_type"]),
                mermaid_code=d["mermaid_code"],
                confidence=d["confidence"],
                warnings=d.get("warnings", []),
            )
            for d in data.get("diagrams", [])
        ]

        report = None
        if data.get("report"):
            report_data = data["report"]
            report = TechnicalReport(
                title=report_data["title"],
                executive_summary=report_data["executive_summary"],
                sections=[],  # Sections not cached, only markdown
                confidence=report_data["confidence"],
                repository_id=data["repository_id"],
            )

        boundaries = [
            ServiceBoundary(
                boundary_id=b["boundary_id"],
                name=b["name"],
                description=b.get("description", ""),
                node_ids=[],  # Node IDs not cached
                confidence=b["confidence"],
            )
            for b in data.get("service_boundaries", [])
        ]

        return DocumentationResult(
            job_id=job_id,
            repository_id=data["repository_id"],
            diagrams=diagrams,
            report=report,
            service_boundaries=boundaries,
            confidence=data["confidence"],
            generated_at=datetime.fromisoformat(data["generated_at"]),
            generation_time_ms=data.get("generation_time_ms", 0),
            metadata={"cached": True},
        )

    def invalidate_cache(self, repository_id: str) -> int:
        """
        Invalidate cached documentation for a repository.

        Call this when the repository is re-ingested.

        Args:
            repository_id: Repository ID to invalidate

        Returns:
            Number of cache entries invalidated
        """
        return self.cache.invalidate_repository(repository_id)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()


# Factory function
def create_documentation_agent(
    use_mock: bool = False,
    llm_client: "BedrockLLMService | None" = None,
    neptune_service: "NeptuneGraphService | None" = None,
) -> DocumentationAgent:
    """
    Factory function to create a DocumentationAgent.

    Args:
        use_mock: If True, use mock implementations for testing
        llm_client: Optional LLM service
        neptune_service: Optional Neptune service

    Returns:
        Configured DocumentationAgent instance
    """
    if use_mock:
        logger.info("Creating DocumentationAgent with mock services")
        # Create boundary detector with mock data for local testing
        boundary_detector = create_service_boundary_detector(neptune_service=None)
        boundary_detector.set_mock_data(
            nodes=_get_mock_nodes(),
            edges=_get_mock_edges(),
        )
        return DocumentationAgent(
            llm_client=None,
            neptune_service=None,
            boundary_detector=boundary_detector,
        )

    return DocumentationAgent(
        llm_client=llm_client,
        neptune_service=neptune_service,
    )


def _get_mock_nodes() -> dict[str, dict]:
    """Get mock nodes simulating Project Aura architecture for local testing."""
    return {
        # API Layer
        "api_main": {
            "name": "main.py",
            "type": "module",
            "file_path": "src/api/main.py",
        },
        "api_router": {
            "name": "router.py",
            "type": "module",
            "file_path": "src/api/router.py",
        },
        "api_auth": {
            "name": "auth.py",
            "type": "module",
            "file_path": "src/api/auth.py",
        },
        "api_docs": {
            "name": "documentation_endpoints.py",
            "type": "module",
            "file_path": "src/api/documentation_endpoints.py",
        },
        "api_agents": {
            "name": "agent_endpoints.py",
            "type": "module",
            "file_path": "src/api/agent_endpoints.py",
        },
        # Agent Layer
        "agent_orchestrator": {
            "name": "orchestrator.py",
            "type": "module",
            "file_path": "src/agents/orchestrator.py",
        },
        "agent_coder": {
            "name": "coder_agent.py",
            "type": "module",
            "file_path": "src/agents/coder_agent.py",
        },
        "agent_reviewer": {
            "name": "reviewer_agent.py",
            "type": "module",
            "file_path": "src/agents/reviewer_agent.py",
        },
        "agent_validator": {
            "name": "validator_agent.py",
            "type": "module",
            "file_path": "src/agents/validator_agent.py",
        },
        # Services Layer
        "svc_neptune": {
            "name": "neptune_service.py",
            "type": "module",
            "file_path": "src/services/neptune_service.py",
        },
        "svc_opensearch": {
            "name": "opensearch_service.py",
            "type": "module",
            "file_path": "src/services/opensearch_service.py",
        },
        "svc_bedrock": {
            "name": "bedrock_service.py",
            "type": "module",
            "file_path": "src/services/bedrock_service.py",
        },
        "svc_sandbox": {
            "name": "sandbox_service.py",
            "type": "module",
            "file_path": "src/services/sandbox_service.py",
        },
        # Documentation Layer
        "doc_agent": {
            "name": "documentation_agent.py",
            "type": "module",
            "file_path": "src/services/documentation/documentation_agent.py",
        },
        "doc_detector": {
            "name": "service_boundary_detector.py",
            "type": "module",
            "file_path": "src/services/documentation/service_boundary_detector.py",
        },
        "doc_generator": {
            "name": "diagram_generator.py",
            "type": "module",
            "file_path": "src/services/documentation/diagram_generator.py",
        },
        # Context Layer
        "ctx_retrieval": {
            "name": "context_retrieval.py",
            "type": "module",
            "file_path": "src/services/context/context_retrieval.py",
        },
        "ctx_hybrid": {
            "name": "hybrid_context.py",
            "type": "module",
            "file_path": "src/services/context/hybrid_context.py",
        },
        "ctx_graphrag": {
            "name": "graphrag_engine.py",
            "type": "module",
            "file_path": "src/services/context/graphrag_engine.py",
        },
    }


def _get_mock_edges() -> list[tuple[str, str, dict]]:
    """Get mock edges simulating call graph relationships."""
    return [
        # API → Services
        ("api_main", "api_router", {"relationship": "imports", "weight": 0.5}),
        ("api_router", "api_auth", {"relationship": "calls", "weight": 1.0}),
        ("api_router", "api_docs", {"relationship": "calls", "weight": 1.0}),
        ("api_router", "api_agents", {"relationship": "calls", "weight": 1.0}),
        ("api_docs", "doc_agent", {"relationship": "calls", "weight": 1.0}),
        ("api_agents", "agent_orchestrator", {"relationship": "calls", "weight": 1.0}),
        # Agent Layer
        ("agent_orchestrator", "agent_coder", {"relationship": "calls", "weight": 1.0}),
        (
            "agent_orchestrator",
            "agent_reviewer",
            {"relationship": "calls", "weight": 1.0},
        ),
        (
            "agent_orchestrator",
            "agent_validator",
            {"relationship": "calls", "weight": 1.0},
        ),
        ("agent_coder", "svc_bedrock", {"relationship": "calls", "weight": 1.0}),
        ("agent_reviewer", "svc_bedrock", {"relationship": "calls", "weight": 1.0}),
        ("agent_validator", "svc_sandbox", {"relationship": "calls", "weight": 1.0}),
        # Documentation Layer
        ("doc_agent", "doc_detector", {"relationship": "calls", "weight": 1.0}),
        ("doc_agent", "doc_generator", {"relationship": "calls", "weight": 1.0}),
        ("doc_detector", "svc_neptune", {"relationship": "calls", "weight": 1.0}),
        ("doc_generator", "svc_bedrock", {"relationship": "calls", "weight": 1.0}),
        # Context Layer
        ("ctx_retrieval", "ctx_hybrid", {"relationship": "calls", "weight": 1.0}),
        ("ctx_hybrid", "ctx_graphrag", {"relationship": "calls", "weight": 1.0}),
        ("ctx_graphrag", "svc_neptune", {"relationship": "calls", "weight": 1.0}),
        ("ctx_graphrag", "svc_opensearch", {"relationship": "calls", "weight": 1.0}),
        # Cross-layer connections
        ("api_auth", "svc_bedrock", {"relationship": "calls", "weight": 0.8}),
        (
            "agent_orchestrator",
            "ctx_retrieval",
            {"relationship": "calls", "weight": 1.0},
        ),
    ]
