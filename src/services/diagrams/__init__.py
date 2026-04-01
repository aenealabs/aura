"""
Enterprise Diagram Generation Service (ADR-060)

Provides enterprise-grade diagram generation matching Eraser.io quality with:
- Official AWS/Azure/GCP icon library with multiple color modes
- ELK.js constraint-based layout engine
- Eraser-style DSL parsing with security validation
- Server-side SVG rendering
- Multi-provider AI model routing (Phase 2)
- AI-powered natural language to diagram generation (Phase 2)
- Git sync with GitHub/GitLab integration (Phase 4)
- Multi-format export: SVG, PNG, PDF, draw.io (Phase 4)
"""

from .ai_diagram_generator import (
    AIDiagramGenerator,
    DiagramIntent,
    GenerationResult,
    GenerationStatus,
)
from .diagram_dsl import DiagramDSLParser, DSLValidationError

# Phase 4: Export Service
from .diagram_export_service import (
    DiagramExportService,
    ExportFormat,
    ExportOptions,
    ExportResult,
    ExportStatus,
    get_diagram_export_service,
)

# Phase 4: Git Sync
from .diagram_git_sync import (
    CommitStatus,
    DiagramCommitRequest,
    DiagramCommitResult,
    DiagramGitSync,
    GitProvider,
    get_diagram_git_sync,
)

# Phase 2: AI Generation
from .diagram_model_router import (
    CircuitBreakerState,
    DataClassification,
    DiagramModelRouter,
    DiagramTask,
    ModelProvider,
    NoAvailableProviderError,
    SecurityError,
)
from .icon_library import (
    CloudProvider,
    DiagramIcon,
    IconCategory,
    IconColorMode,
    IconLibrary,
)
from .layout_engine import LayoutEngine, LayoutResult
from .models import (
    ConnectionStyle,
    DiagramConnection,
    DiagramDefinition,
    DiagramGroup,
    DiagramNode,
    LayoutConstraint,
)
from .svg_renderer import RenderOptions, SVGRenderer

__all__ = [
    # Models
    "DiagramDefinition",
    "DiagramNode",
    "DiagramGroup",
    "DiagramConnection",
    "ConnectionStyle",
    "LayoutConstraint",
    # Icon Library
    "IconLibrary",
    "DiagramIcon",
    "CloudProvider",
    "IconCategory",
    "IconColorMode",
    # DSL Parser
    "DiagramDSLParser",
    "DSLValidationError",
    # Layout Engine
    "LayoutEngine",
    "LayoutResult",
    # SVG Renderer
    "SVGRenderer",
    "RenderOptions",
    # Phase 2: Model Router
    "DiagramModelRouter",
    "ModelProvider",
    "DiagramTask",
    "DataClassification",
    "CircuitBreakerState",
    "NoAvailableProviderError",
    "SecurityError",
    # Phase 2: AI Generator
    "AIDiagramGenerator",
    "DiagramIntent",
    "GenerationResult",
    "GenerationStatus",
    # Phase 4: Git Sync
    "DiagramGitSync",
    "DiagramCommitRequest",
    "DiagramCommitResult",
    "CommitStatus",
    "GitProvider",
    "get_diagram_git_sync",
    # Phase 4: Export Service
    "DiagramExportService",
    "ExportFormat",
    "ExportOptions",
    "ExportResult",
    "ExportStatus",
    "get_diagram_export_service",
]
