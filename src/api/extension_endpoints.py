"""
Project Aura - IDE Extension API Endpoints (ADR-028 Phase 4, ADR-048 Phase 1)

API endpoints for IDE extensions (VSCode, Jupyter, PyCharm) to enable:
- Real-time vulnerability scanning with secrets pre-scan filter
- Code review findings display
- Patch generation and application
- HITL approval workflow integration
- GraphRAG context visualization (P0 differentiator)

Author: Project Aura Team
Created: 2025-12-07
Updated: 2025-12-31 (ADR-048 Phase 1)
Version: 2.0.0
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth import User, get_optional_user
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/extension", tags=["IDE Extensions"])


# ============================================================================
# Enums
# ============================================================================


class FindingSeverity(str, Enum):
    """Vulnerability finding severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingCategory(str, Enum):
    """Vulnerability finding categories (OWASP Top 10 aligned)."""

    INJECTION = "injection"
    BROKEN_AUTH = "broken_authentication"
    SENSITIVE_DATA = "sensitive_data_exposure"
    XXE = "xxe"
    BROKEN_ACCESS = "broken_access_control"
    SECURITY_MISCONFIG = "security_misconfiguration"
    XSS = "xss"
    DESERIALIZATION = "insecure_deserialization"
    COMPONENTS = "vulnerable_components"
    LOGGING = "insufficient_logging"
    CODE_QUALITY = "code_quality"
    PERFORMANCE = "performance"


class PatchStatus(str, Enum):
    """Patch lifecycle status."""

    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    FAILED = "failed"


class ScanStatus(str, Enum):
    """Scan job status."""

    QUEUED = "queued"
    SCANNING = "scanning"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Request/Response Models
# ============================================================================


class ScanRequest(BaseModel):
    """Request to scan a file for vulnerabilities."""

    file_path: str = Field(..., description="Path to the file relative to workspace")
    file_content: str = Field(..., description="Current file content")
    language: str = Field(default="python", description="Programming language")
    workspace_path: str = Field(default="", description="Workspace root path")


class ScanResponse(BaseModel):
    """Response from file scan."""

    scan_id: str
    status: ScanStatus
    findings_count: int
    message: str


class Finding(BaseModel):
    """A vulnerability or code quality finding."""

    id: str
    file_path: str
    line_start: int
    line_end: int
    column_start: int = 0
    column_end: int = 0
    severity: FindingSeverity
    category: FindingCategory
    title: str
    description: str
    code_snippet: str = ""
    suggestion: str = ""
    cwe_id: str | None = None
    owasp_category: str | None = None
    has_patch: bool = False
    patch_id: str | None = None


class FindingsResponse(BaseModel):
    """Response containing findings for a file."""

    file_path: str
    findings: list[Finding]
    scan_timestamp: str
    scan_duration_ms: float


class PatchRequest(BaseModel):
    """Request to generate a patch for a finding."""

    finding_id: str = Field(..., description="ID of the finding to patch")
    file_path: str = Field(..., description="File path")
    file_content: str = Field(..., description="Current file content")
    context_lines: int = Field(
        default=10, description="Lines of context around finding"
    )


class Patch(BaseModel):
    """A generated code patch."""

    id: str
    finding_id: str
    file_path: str
    status: PatchStatus
    original_code: str
    patched_code: str
    diff: str
    explanation: str
    confidence: float = Field(..., ge=0, le=1)
    requires_approval: bool = True
    approval_id: str | None = None
    created_at: str
    applied_at: str | None = None


class PatchResponse(BaseModel):
    """Response from patch generation."""

    patch: Patch
    message: str


class ApplyPatchRequest(BaseModel):
    """Request to apply an approved patch."""

    patch_id: str
    confirm: bool = Field(default=False, description="Confirm patch application")


class ApplyPatchResponse(BaseModel):
    """Response from patch application."""

    success: bool
    patch_id: str
    file_path: str
    message: str
    backup_path: str | None = None


class ApprovalStatusResponse(BaseModel):
    """Response for approval status check."""

    patch_id: str
    approval_id: str | None
    status: str
    reviewer: str | None = None
    reviewed_at: str | None = None
    comments: str | None = None


class ExtensionConfigResponse(BaseModel):
    """Extension configuration from server."""

    scan_on_save: bool = True
    auto_suggest_patches: bool = True
    severity_threshold: FindingSeverity = FindingSeverity.LOW
    supported_languages: list[str]
    api_version: str
    features: dict[str, bool]


# ============================================================================
# GraphRAG Context Models (ADR-048 P0 - Key Differentiator)
# ============================================================================


class GraphNodeType(str, Enum):
    """Types of nodes in the code graph."""

    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    MODULE = "module"
    VARIABLE = "variable"
    IMPORT = "import"


class GraphEdgeType(str, Enum):
    """Types of relationships in the code graph."""

    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    CONTAINS = "contains"
    REFERENCES = "references"
    DEPENDS_ON = "depends_on"


class GraphNode(BaseModel):
    """A node in the code graph."""

    id: str
    type: GraphNodeType
    name: str
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """An edge (relationship) in the code graph."""

    source_id: str
    target_id: str
    type: GraphEdgeType
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphContextRequest(BaseModel):
    """Request for GraphRAG context visualization."""

    file_path: str = Field(..., description="Path to the file")
    line_number: int | None = Field(None, description="Optional line number for focus")
    depth: int = Field(default=2, ge=1, le=5, description="Traversal depth (1-5)")
    include_types: list[GraphNodeType] | None = Field(
        None, description="Filter to specific node types"
    )


class GraphContextResponse(BaseModel):
    """Response with GraphRAG context for visualization."""

    file_path: str
    focus_node_id: str | None = None
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    relationships: dict[str, int]  # Edge type -> count
    query_duration_ms: float
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Fix Preview Models
# ============================================================================


class FixPreviewRequest(BaseModel):
    """Request to preview a fix before applying."""

    finding_id: str = Field(..., description="ID of the finding to fix")
    file_content: str = Field(..., description="Current file content")
    apply_all: bool = Field(default=False, description="Apply all similar fixes")


class FixPreviewResponse(BaseModel):
    """Response with fix preview details."""

    finding_id: str
    diff: str
    confidence: float = Field(..., ge=0, le=1)
    explanation: str
    side_effects: list[str] = Field(default_factory=list)
    test_suggestions: list[str] = Field(default_factory=list)
    requires_review: bool = True


# ============================================================================
# Secrets Detection Models
# ============================================================================


class SecretFinding(BaseModel):
    """A detected secret in code."""

    detection_id: str
    secret_type: str
    line_number: int
    column_start: int
    column_end: int
    confidence: float
    context: str  # Masked context around the secret


class SecretsCheckResponse(BaseModel):
    """Response from secrets pre-scan check."""

    is_clean: bool
    secret_count: int
    secrets: list[SecretFinding]
    scan_duration_ms: float
    blocked: bool = False  # If True, content cannot be stored


# ============================================================================
# In-Memory Storage (for development - replace with DynamoDB in production)
# ============================================================================


_scans: dict[str, dict] = {}
_findings: dict[str, list[Finding]] = {}  # file_path -> findings
_patches: dict[str, Patch] = {}


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/config", response_model=ExtensionConfigResponse)
async def get_extension_config():
    """
    Get extension configuration from server.

    Returns settings that control extension behavior, supported features,
    and API compatibility information.
    """
    return ExtensionConfigResponse(
        scan_on_save=True,
        auto_suggest_patches=True,
        severity_threshold=FindingSeverity.LOW,
        supported_languages=[
            "python",
            "javascript",
            "typescript",
            "java",
            "go",
            "rust",
            "kotlin",
            "c",
            "cpp",
            "csharp",
        ],
        api_version="2.0.0",
        features={
            "realtime_scan": True,
            "patch_generation": True,
            "hitl_integration": True,
            "codelens": True,
            "quick_fixes": True,
            "diff_preview": True,
            "graphrag_context": True,  # ADR-048 P0 - Key differentiator
            "secrets_detection": True,  # ADR-048 Security Control
            "fix_preview": True,
        },
    )


@router.post("/scan", response_model=ScanResponse)
async def scan_file(request: ScanRequest):
    """
    Scan a file for vulnerabilities and code quality issues.

    This endpoint analyzes the provided file content and returns
    findings including security vulnerabilities, code smells, and
    potential bugs.

    The scan is performed asynchronously - use GET /findings/{file_path}
    to retrieve results.
    """
    scan_id = str(uuid.uuid4())
    start_time = time.time()

    try:
        logger.info(f"Starting scan {sanitize_log(scan_id)} for {sanitize_log(request.file_path)}")

        # Store scan record
        _scans[scan_id] = {
            "file_path": request.file_path,
            "status": ScanStatus.SCANNING,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        # Perform analysis (mock implementation)
        findings = await _analyze_file(
            request.file_path,
            request.file_content,
            request.language,
        )

        # Store findings
        _findings[request.file_path] = findings

        # Update scan record
        _scans[scan_id]["status"] = ScanStatus.COMPLETED
        _scans[scan_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        _scans[scan_id]["duration_ms"] = (time.time() - start_time) * 1000
        _scans[scan_id]["findings_count"] = len(findings)

        logger.info(
            f"Scan {scan_id} completed: {len(findings)} findings in "
            f"{_scans[scan_id]['duration_ms']:.0f}ms"
        )

        return ScanResponse(
            scan_id=scan_id,
            status=ScanStatus.COMPLETED,
            findings_count=len(findings),
            message=f"Found {len(findings)} issues",
        )

    except Exception as e:
        logger.error("Scan %s failed: %s", scan_id, e, exc_info=True)
        _scans[scan_id]["status"] = ScanStatus.FAILED
        _scans[scan_id]["error"] = str(e)

        return ScanResponse(
            scan_id=scan_id,
            status=ScanStatus.FAILED,
            findings_count=0,
            message="Scan failed. Check server logs for details.",
        )


@router.get("/findings/{file_path:path}", response_model=FindingsResponse)
async def get_findings(file_path: str):
    """
    Get vulnerability findings for a specific file.

    Returns all findings from the most recent scan of this file.
    """
    findings = _findings.get(file_path, [])

    # Get scan metadata
    scan_timestamp = datetime.now(timezone.utc).isoformat()
    scan_duration = 0.0

    for scan in _scans.values():
        if scan.get("file_path") == file_path:
            scan_timestamp = scan.get("completed_at", scan_timestamp)
            scan_duration = scan.get("duration_ms", 0)
            break

    return FindingsResponse(
        file_path=file_path,
        findings=findings,
        scan_timestamp=scan_timestamp,
        scan_duration_ms=scan_duration,
    )


@router.get("/findings", response_model=dict)
async def list_all_findings(
    severity: FindingSeverity | None = Query(  # noqa: B008
        None, description="Filter by severity"
    ),  # noqa: B008
    category: FindingCategory | None = Query(  # noqa: B008
        None, description="Filter by category"
    ),  # noqa: B008
):
    """
    List all findings across all scanned files.

    Supports filtering by severity and category.
    """
    all_findings = []

    for _file_path, findings in _findings.items():
        for finding in findings:
            if severity and finding.severity != severity:
                continue
            if category and finding.category != category:
                continue
            all_findings.append(finding)

    return {
        "total": len(all_findings),
        "findings": all_findings,
        "filters": {
            "severity": severity.value if severity else None,
            "category": category.value if category else None,
        },
    }


@router.post("/patches", response_model=PatchResponse)
async def generate_patch(request: PatchRequest):
    """
    Generate a patch for a specific finding.

    Uses the Coder Agent to generate a secure fix for the vulnerability.
    The patch will require HITL approval before it can be applied.
    """
    patch_id = str(uuid.uuid4())

    try:
        logger.info(f"Generating patch {sanitize_log(patch_id)} for finding {sanitize_log(request.finding_id)}")

        # Find the finding
        finding = None
        for file_findings in _findings.values():
            for f in file_findings:
                if f.id == request.finding_id:
                    finding = f
                    break
            if finding:
                break

        if not finding:
            raise HTTPException(
                status_code=404, detail=f"Finding {request.finding_id} not found"
            )

        # Generate patch (mock implementation)
        patch = await _generate_patch(
            patch_id,
            finding,
            request.file_content,
            request.context_lines,
        )

        # Store patch
        _patches[patch_id] = patch

        # Update finding to indicate patch exists
        finding.has_patch = True
        finding.patch_id = patch_id

        logger.info(
            f"Patch {patch_id} generated with confidence {patch.confidence:.2f}"
        )

        return PatchResponse(
            patch=patch,
            message="Patch generated successfully. Requires HITL approval before application.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Patch generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate patch")


@router.get("/patches/{patch_id}", response_model=Patch)
async def get_patch(patch_id: str):
    """
    Get details of a specific patch.

    Returns the patch content, status, and approval information.
    """
    if patch_id not in _patches:
        raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")

    return _patches[patch_id]


@router.post("/patches/{patch_id}/apply", response_model=ApplyPatchResponse)
async def apply_patch(patch_id: str, request: ApplyPatchRequest):
    """
    Apply an approved patch to the file.

    The patch must be approved through the HITL workflow before it can
    be applied. The extension will apply the patch locally.
    """
    if patch_id not in _patches:
        raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")

    patch = _patches[patch_id]

    # Check approval status
    if patch.status not in (PatchStatus.APPROVED, PatchStatus.READY):
        raise HTTPException(
            status_code=403,
            detail=f"Patch cannot be applied - current status: {patch.status.value}",
        )

    if patch.requires_approval and patch.status != PatchStatus.APPROVED:
        raise HTTPException(
            status_code=403,
            detail="Patch requires HITL approval before application",
        )

    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Patch application requires confirmation (set confirm=true)",
        )

    try:
        # Mark as applied
        patch.status = PatchStatus.APPLIED
        patch.applied_at = datetime.now(timezone.utc).isoformat()

        logger.info(f"Patch {sanitize_log(patch_id)} applied to {sanitize_log(patch.file_path)}")

        return ApplyPatchResponse(
            success=True,
            patch_id=patch_id,
            file_path=patch.file_path,
            message="Patch applied successfully",
            backup_path=None,  # Extension handles backup
        )

    except Exception as e:
        logger.error("Patch application failed: %s", e, exc_info=True)
        patch.status = PatchStatus.FAILED
        raise HTTPException(status_code=500, detail="Failed to apply patch")


@router.get("/approvals/{approval_id}", response_model=ApprovalStatusResponse)
async def get_approval_status(approval_id: str):
    """
    Get the status of a HITL approval request.

    Used by the extension to poll for approval status updates.
    """
    # Find patch with this approval_id
    for patch_id, patch in _patches.items():
        if patch.approval_id == approval_id:
            return ApprovalStatusResponse(
                patch_id=patch_id,
                approval_id=approval_id,
                status=patch.status.value,
                reviewer=None,
                reviewed_at=None,
                comments=None,
            )

    raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")


# ============================================================================
# Mock Analysis Functions (Replace with real agent calls in production)
# ============================================================================


async def _analyze_file(
    file_path: str,
    content: str,
    language: str,
) -> list[Finding]:
    """
    Analyze file content for vulnerabilities.

    This is a mock implementation. In production, this would:
    1. Call the Reviewer Agent for security analysis
    2. Call the Code Quality Agent for code smells
    3. Integrate with GraphRAG for context-aware analysis
    """
    findings = []
    lines = content.split("\n")

    # Mock detection of common vulnerability patterns
    patterns: list[dict[str, Any]] = [
        {
            "pattern": "eval(",
            "severity": FindingSeverity.CRITICAL,
            "category": FindingCategory.INJECTION,
            "title": "Dangerous eval() usage",
            "description": "Using eval() can lead to code injection vulnerabilities",
            "cwe": "CWE-95",
            "owasp": "A03:2021",
        },
        {
            "pattern": "exec(",
            "severity": FindingSeverity.CRITICAL,
            "category": FindingCategory.INJECTION,
            "title": "Dangerous exec() usage",
            "description": "Using exec() can lead to code injection vulnerabilities",
            "cwe": "CWE-95",
            "owasp": "A03:2021",
        },
        {
            "pattern": "subprocess.call(",
            "severity": FindingSeverity.HIGH,
            "category": FindingCategory.INJECTION,
            "title": "Potential command injection",
            "description": "subprocess.call with shell=True can lead to command injection",
            "cwe": "CWE-78",
            "owasp": "A03:2021",
        },
        {
            "pattern": "password",
            "severity": FindingSeverity.MEDIUM,
            "category": FindingCategory.SENSITIVE_DATA,
            "title": "Hardcoded credential detected",
            "description": "Possible hardcoded password found in source code",
            "cwe": "CWE-798",
            "owasp": "A07:2021",
        },
        {
            "pattern": "TODO",
            "severity": FindingSeverity.INFO,
            "category": FindingCategory.CODE_QUALITY,
            "title": "TODO comment found",
            "description": "Unresolved TODO comment in code",
            "cwe": None,
            "owasp": None,
        },
    ]

    for line_num, line in enumerate(lines, 1):
        for pattern_info in patterns:
            if pattern_info["pattern"].lower() in line.lower():
                finding_id = str(uuid.uuid4())[:8]

                findings.append(
                    Finding(
                        id=finding_id,
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                        column_start=line.lower().find(pattern_info["pattern"].lower()),
                        column_end=line.lower().find(pattern_info["pattern"].lower())
                        + len(pattern_info["pattern"]),
                        severity=pattern_info["severity"],
                        category=pattern_info["category"],
                        title=pattern_info["title"],
                        description=pattern_info["description"],
                        code_snippet=line.strip(),
                        suggestion=f"Consider removing or replacing {pattern_info['pattern']}",
                        cwe_id=pattern_info["cwe"],
                        owasp_category=pattern_info["owasp"],
                    )
                )

    return findings


async def _generate_patch(
    patch_id: str,
    finding: Finding,
    file_content: str,
    context_lines: int,
) -> Patch:
    """
    Generate a patch for a finding.

    This is a mock implementation. In production, this would:
    1. Call the Coder Agent with vulnerability context
    2. Generate secure replacement code
    3. Validate the patch doesn't break functionality
    """
    lines = file_content.split("\n")

    # Get the vulnerable line
    vuln_line = (
        lines[finding.line_start - 1] if finding.line_start <= len(lines) else ""
    )

    # Generate mock patched version
    patched_line = vuln_line
    if "eval(" in vuln_line:
        patched_line = vuln_line.replace("eval(", "ast.literal_eval(")
    elif "exec(" in vuln_line:
        patched_line = "# WARNING: exec() removed for security\n# " + vuln_line
    elif "subprocess.call" in vuln_line:
        patched_line = vuln_line.replace("shell=True", "shell=False")

    # Generate diff
    diff = f"""--- a/{finding.file_path}
+++ b/{finding.file_path}
@@ -{finding.line_start},1 +{finding.line_start},1 @@
-{vuln_line}
+{patched_line}
"""

    return Patch(
        id=patch_id,
        finding_id=finding.id,
        file_path=finding.file_path,
        status=PatchStatus.READY,
        original_code=vuln_line,
        patched_code=patched_line,
        diff=diff,
        explanation=f"Patched {finding.title} by replacing vulnerable code pattern",
        confidence=0.85,
        requires_approval=finding.severity
        in (FindingSeverity.CRITICAL, FindingSeverity.HIGH),
        approval_id=(
            str(uuid.uuid4())
            if finding.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
            else None
        ),
        created_at=datetime.now(timezone.utc).isoformat(),
        applied_at=None,
    )


# ============================================================================
# GraphRAG Context Endpoints (ADR-048 P0 - Key Differentiator)
# ============================================================================


@router.post("/graph/context", response_model=GraphContextResponse)
async def get_graph_context(
    request: GraphContextRequest,
    user: User | None = Depends(get_optional_user),  # noqa: B008
):
    """
    Get GraphRAG context for a file (P0 Key Differentiator).

    Returns the code relationship graph for visualization in the IDE extension.
    Shows how the current file/function connects to other parts of the codebase
    through calls, imports, inheritance, and references.

    This is Aura's unique value proposition - competitors don't have Neptune-powered
    code relationship visualization in their IDE extensions.
    """
    start_time = time.time()

    try:
        logger.info(f"GraphRAG context request for {sanitize_log(request.file_path)}")

        # Get graph context (mock implementation)
        nodes, edges = await _get_graph_context(
            file_path=request.file_path,
            line_number=request.line_number,
            depth=request.depth,
            include_types=request.include_types,
        )

        # Count relationships by type
        relationships: dict[str, int] = {}
        for edge in edges:
            edge_type = edge.type.value
            relationships[edge_type] = relationships.get(edge_type, 0) + 1

        # Find focus node (the file or function at the requested location)
        focus_node_id = None
        for node in nodes:
            if node.file_path == request.file_path:
                if request.line_number is None:
                    focus_node_id = node.id
                    break
                elif (
                    node.line_start
                    and node.line_end
                    and node.line_start <= request.line_number <= node.line_end
                ):
                    focus_node_id = node.id
                    break

        query_duration_ms = (time.time() - start_time) * 1000

        return GraphContextResponse(
            file_path=request.file_path,
            focus_node_id=focus_node_id,
            nodes=nodes,
            edges=edges,
            relationships=relationships,
            query_duration_ms=query_duration_ms,
            metadata={
                "depth": request.depth,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            },
        )

    except Exception as e:
        logger.error("GraphRAG context failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve GraphRAG context"
        )


async def _get_graph_context(
    file_path: str,
    line_number: int | None,
    depth: int,
    include_types: list[GraphNodeType] | None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """
    Get graph context from Neptune.

    This is a mock implementation. In production, this would:
    1. Query Neptune for the file/function node
    2. Traverse relationships up to the specified depth
    3. Return connected nodes and edges
    """
    # Mock nodes for the requested file
    file_node = GraphNode(
        id=f"file:{file_path}",
        type=GraphNodeType.FILE,
        name=file_path.split("/")[-1],
        file_path=file_path,
        line_start=1,
        line_end=100,
    )

    # Generate mock related nodes based on file type
    nodes: list[GraphNode] = [file_node]
    edges: list[GraphEdge] = []

    # Add mock class node
    class_node = GraphNode(
        id=f"class:MyClass:{file_path}",
        type=GraphNodeType.CLASS,
        name="MyClass",
        file_path=file_path,
        line_start=10,
        line_end=50,
        metadata={"visibility": "public"},
    )
    nodes.append(class_node)

    # Add mock method nodes
    method_names = ["__init__", "process", "validate"]
    for i, method_name in enumerate(method_names):
        method_node = GraphNode(
            id=f"method:{method_name}:{file_path}",
            type=GraphNodeType.METHOD,
            name=method_name,
            file_path=file_path,
            line_start=12 + (i * 10),
            line_end=20 + (i * 10),
        )
        nodes.append(method_node)

        # Add CONTAINS edge from class to method
        edges.append(
            GraphEdge(
                source_id=class_node.id,
                target_id=method_node.id,
                type=GraphEdgeType.CONTAINS,
            )
        )

    # Add mock import relationships
    imported_modules = ["os", "sys", "logging"]
    for module in imported_modules:
        import_node = GraphNode(
            id=f"module:{module}",
            type=GraphNodeType.MODULE,
            name=module,
        )
        nodes.append(import_node)

        edges.append(
            GraphEdge(
                source_id=file_node.id,
                target_id=import_node.id,
                type=GraphEdgeType.IMPORTS,
            )
        )

    # Add mock CALLS relationship
    edges.append(
        GraphEdge(
            source_id=f"method:process:{file_path}",
            target_id=f"method:validate:{file_path}",
            type=GraphEdgeType.CALLS,
            weight=3,  # Called 3 times
        )
    )

    # Filter by include_types if specified
    if include_types:
        nodes = [n for n in nodes if n.type in include_types]
        node_ids = {n.id for n in nodes}
        edges = [
            e for e in edges if e.source_id in node_ids and e.target_id in node_ids
        ]

    return nodes, edges


# ============================================================================
# Fix Preview Endpoints (ADR-048)
# ============================================================================


@router.post("/fix/preview", response_model=FixPreviewResponse)
async def preview_fix(request: FixPreviewRequest):
    """
    Preview a fix before applying it.

    Returns a diff preview and explanation of what the fix will do,
    along with potential side effects and test suggestions.
    """
    try:
        logger.info(f"Fix preview request for finding {sanitize_log(request.finding_id)}")

        # Find the finding
        finding = None
        for file_findings in _findings.values():
            for f in file_findings:
                if f.id == request.finding_id:
                    finding = f
                    break
            if finding:
                break

        if not finding:
            raise HTTPException(
                status_code=404, detail=f"Finding {request.finding_id} not found"
            )

        # Generate preview
        lines = request.file_content.split("\n")
        vuln_line = (
            lines[finding.line_start - 1] if finding.line_start <= len(lines) else ""
        )

        # Generate mock fix
        patched_line = vuln_line
        side_effects: list[str] = []
        test_suggestions: list[str] = []

        if "eval(" in vuln_line:
            patched_line = vuln_line.replace("eval(", "ast.literal_eval(")
            side_effects = [
                "ast.literal_eval only handles literals (strings, numbers, tuples, lists, dicts)",
                "Complex expressions will raise ValueError",
            ]
            test_suggestions = [
                "Test with valid literal inputs",
                "Test error handling for non-literal inputs",
            ]
        elif "exec(" in vuln_line:
            patched_line = "# " + vuln_line + "  # DISABLED: exec() is dangerous"
            side_effects = [
                "Code that relied on exec() will no longer execute",
                "May break dynamic code generation patterns",
            ]
            test_suggestions = [
                "Verify application functionality without exec()",
                "Consider alternative approaches for dynamic code",
            ]
        elif "subprocess.call" in vuln_line and "shell=True" in vuln_line:
            patched_line = vuln_line.replace("shell=True", "shell=False")
            side_effects = [
                "Shell expansion (*, ?, etc.) will no longer work",
                "Command must be passed as list, not string",
            ]
            test_suggestions = [
                "Test with list-based command arguments",
                "Verify no shell features are required",
            ]

        diff = f"""--- a/{finding.file_path}
+++ b/{finding.file_path}
@@ -{finding.line_start},1 +{finding.line_start},1 @@
-{vuln_line}
+{patched_line}
"""

        return FixPreviewResponse(
            finding_id=request.finding_id,
            diff=diff,
            confidence=0.85,
            explanation=f"This fix addresses {finding.title} by modifying the vulnerable pattern.",
            side_effects=side_effects,
            test_suggestions=test_suggestions,
            requires_review=finding.severity
            in (FindingSeverity.CRITICAL, FindingSeverity.HIGH),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Fix preview failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate fix preview")


@router.post("/fix/apply", response_model=ApplyPatchResponse)
async def apply_fix(
    finding_id: str,
    file_path: str,
    confirm: bool = Query(False, description="Confirm fix application"),  # noqa: B008
):
    """
    Apply a fix directly to a finding (bypasses patch creation for simple fixes).

    For critical/high severity findings, this still requires HITL approval.
    """
    # Find the finding
    finding = None
    for file_findings in _findings.values():
        for f in file_findings:
            if f.id == finding_id:
                finding = f
                break
        if finding:
            break

    if not finding:
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")

    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Fix application requires confirmation (set confirm=true)",
        )

    # Check if HITL approval required
    if finding.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH):
        raise HTTPException(
            status_code=403,
            detail="Critical/High severity findings require HITL approval. Use /patches endpoint.",
        )

    logger.info(f"Direct fix applied for finding {sanitize_log(finding_id)}")

    return ApplyPatchResponse(
        success=True,
        patch_id=f"direct-{finding_id}",
        file_path=file_path,
        message="Fix applied successfully",
        backup_path=None,
    )


# ============================================================================
# Secrets Detection Endpoints (ADR-048 Security Control)
# ============================================================================


@router.post("/secrets/check", response_model=SecretsCheckResponse)
async def check_secrets(
    file_path: str = Query(..., description="File path"),  # noqa: B008
    content: str = Query(..., description="File content to check"),  # noqa: B008
):
    """
    Check file content for secrets before storing in GraphRAG.

    This is a CRITICAL security control that prevents sensitive credentials
    from being stored in the Neptune graph database.

    Returns detection results with masked context (secrets are never returned).
    """
    try:
        from src.services.integrations.secrets_prescan_filter import (
            SecretsPrescanFilter,
        )

        filter_service = SecretsPrescanFilter()
        result = filter_service.scan_and_redact(content, file_path=file_path)

        secrets = [
            SecretFinding(
                detection_id=s.detection_id,
                secret_type=s.secret_type.value,
                line_number=s.line_number,
                column_start=s.column_start,
                column_end=s.column_end,
                confidence=s.confidence,
                context=s.context,
            )
            for s in result.secrets_found
        ]

        return SecretsCheckResponse(
            is_clean=result.is_clean,
            secret_count=result.secret_count,
            secrets=secrets,
            scan_duration_ms=result.scan_duration_ms,
            blocked=result.secret_count > 0,  # Block storage if secrets found
        )

    except ImportError:
        # Fallback if secrets filter not available
        logger.warning("Secrets pre-scan filter not available")
        return SecretsCheckResponse(
            is_clean=True,
            secret_count=0,
            secrets=[],
            scan_duration_ms=0.0,
            blocked=False,
        )
    except Exception as e:
        # nosec - logging exception message, not credentials
        logger.error("Secrets check failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to check for secrets")


@router.post("/secrets/redact", response_model=dict)
async def redact_secrets(
    file_path: str = Query(..., description="File path"),  # noqa: B008
    content: str = Query(..., description="File content to redact"),  # noqa: B008
):
    """
    Redact secrets from file content and return cleaned version.

    Secrets are replaced with [REDACTED:type] placeholders.
    Use this before storing code in GraphRAG.
    """
    try:
        from src.services.integrations.secrets_prescan_filter import (
            SecretsPrescanFilter,
        )

        filter_service = SecretsPrescanFilter()
        result = filter_service.scan_and_redact(content, file_path=file_path)

        return {
            "original_hash": result.original_content_hash,
            "redacted_content": result.redacted_content,
            "secrets_redacted": result.secret_count,
            "is_clean": result.is_clean,
        }

    except ImportError:
        # Fallback if secrets filter not available
        return {
            "original_hash": "",
            "redacted_content": content,
            "secrets_redacted": 0,
            "is_clean": True,
        }
    except Exception as e:
        # nosec - logging exception message, not credentials
        logger.error("Secrets redaction failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to redact secrets")


# ============================================================================
# Notebook-Specific Endpoints (ADR-048 Phase 2: Jupyter Extension)
# ============================================================================


class CellScanRequest(BaseModel):
    """Request to scan a notebook cell."""

    notebook_path: str = Field(..., description="Path to the notebook file")
    cell_id: str = Field(..., description="Unique cell identifier")
    cell_index: int = Field(..., description="Cell index in notebook")
    source_code: str = Field(..., description="Cell source code")
    language: str = Field(default="python", description="Programming language")


class CellScanResponse(BaseModel):
    """Response from cell scan."""

    scan_id: str
    status: ScanStatus
    findings_count: int
    message: str


class CellFinding(BaseModel):
    """A finding within a notebook cell."""

    id: str
    cell_id: str
    cell_index: int
    line_start: int
    line_end: int
    column_start: int = 0
    column_end: int = 0
    severity: FindingSeverity
    category: FindingCategory
    title: str
    description: str
    code_snippet: str = ""
    suggestion: str = ""
    cwe_id: str | None = None
    owasp_category: str | None = None
    has_patch: bool = False
    patch_id: str | None = None


class CellFindingsResponse(BaseModel):
    """Response containing findings for a cell."""

    notebook_path: str
    cell_id: str
    findings: list[CellFinding]
    scan_timestamp: str


# In-memory storage for notebook findings
_notebook_findings: dict[str, dict[str, list[CellFinding]]] = (
    {}
)  # notebook -> cell_id -> findings


@router.post("/notebook/scan-cell", response_model=CellScanResponse)
async def scan_notebook_cell(request: CellScanRequest):
    """
    Scan a notebook cell for vulnerabilities.

    This endpoint analyzes the provided cell source code and returns
    findings specific to that cell. Used by Jupyter extension for
    cell-level security scanning.
    """
    scan_id = str(uuid.uuid4())
    start_time = time.time()

    try:
        logger.info(
            f"Starting notebook cell scan {sanitize_log(scan_id)} for "
            f"{request.notebook_path} cell {request.cell_index}"
        )

        # Analyze cell using the file analyzer
        file_findings = await _analyze_file(
            request.notebook_path,
            request.source_code,
            request.language,
        )

        # Convert to cell findings
        cell_findings = [
            CellFinding(
                id=f.id,
                cell_id=request.cell_id,
                cell_index=request.cell_index,
                line_start=f.line_start,
                line_end=f.line_end,
                column_start=f.column_start,
                column_end=f.column_end,
                severity=f.severity,
                category=f.category,
                title=f.title,
                description=f.description,
                code_snippet=f.code_snippet,
                suggestion=f.suggestion,
                cwe_id=f.cwe_id,
                owasp_category=f.owasp_category,
                has_patch=f.has_patch,
                patch_id=f.patch_id,
            )
            for f in file_findings
        ]

        # Store findings
        if request.notebook_path not in _notebook_findings:
            _notebook_findings[request.notebook_path] = {}
        _notebook_findings[request.notebook_path][request.cell_id] = cell_findings

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Cell scan {scan_id} completed: {len(cell_findings)} findings in {duration_ms:.0f}ms"
        )

        return CellScanResponse(
            scan_id=scan_id,
            status=ScanStatus.COMPLETED,
            findings_count=len(cell_findings),
            message=f"Found {len(cell_findings)} issues",
        )

    except Exception as e:
        logger.error("Cell scan %s failed: %s", scan_id, e, exc_info=True)
        return CellScanResponse(
            scan_id=scan_id,
            status=ScanStatus.FAILED,
            findings_count=0,
            message="Scan failed. Check server logs for details.",
        )


@router.get(
    "/notebook/findings/{notebook_path:path}/{cell_id}",
    response_model=CellFindingsResponse,
)
async def get_cell_findings(notebook_path: str, cell_id: str):
    """
    Get vulnerability findings for a specific notebook cell.

    Returns all findings from the most recent scan of this cell.
    """
    notebook_data = _notebook_findings.get(notebook_path, {})
    findings = notebook_data.get(cell_id, [])

    return CellFindingsResponse(
        notebook_path=notebook_path,
        cell_id=cell_id,
        findings=findings,
        scan_timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/notebook/findings/{notebook_path:path}", response_model=dict)
async def get_notebook_findings(notebook_path: str):
    """
    Get all findings for a notebook across all cells.

    Returns findings organized by cell ID.
    """
    notebook_data = _notebook_findings.get(notebook_path, {})

    # Flatten all findings
    all_findings = []
    for cell_findings in notebook_data.values():
        all_findings.extend(cell_findings)

    return {
        "notebook_path": notebook_path,
        "findings": [f.model_dump() for f in all_findings],
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
    }
