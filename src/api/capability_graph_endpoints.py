"""
Project Aura - Capability Graph API Endpoints

REST API endpoints for the Cross-Agent Capability Graph Analysis system.
Implements ADR-071 for graph-based capability visualization and security analysis.

Endpoints:
- GET  /api/v1/capability-graph/visualization    - Get visualization data for frontend
- GET  /api/v1/capability-graph/agents           - List all agents with capabilities
- GET  /api/v1/capability-graph/agent/{name}     - Get single agent's capability graph
- GET  /api/v1/capability-graph/escalation-paths - Get detected escalation paths
- GET  /api/v1/capability-graph/coverage-gaps    - Get detected coverage gaps
- GET  /api/v1/capability-graph/toxic-combinations - Get detected toxic combinations
- GET  /api/v1/capability-graph/inheritance/{agent} - Get inheritance tree
- GET  /api/v1/capability-graph/effective/{agent_id} - Get effective capabilities
- POST /api/v1/capability-graph/sync             - Trigger policy sync
- GET  /api/v1/capability-graph/analysis         - Run full analysis
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from src.services.capability_governance import (
    CapabilityGraphAnalyzer,
    PolicyGraphSynchronizer,
    get_capability_graph_analyzer,
    get_policy_graph_synchronizer,
)
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/capability-graph", tags=["Capability Graph"])


# ============================================================================
# Response Models
# ============================================================================


class VisualizationResponse(BaseModel):
    """Response model for graph visualization data."""

    nodes: list[dict[str, Any]] = Field(
        default_factory=list, description="Graph nodes (agents and capabilities)"
    )
    edges: list[dict[str, Any]] = Field(
        default_factory=list, description="Graph edges (relationships)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Visualization metadata"
    )


class EscalationPathResponse(BaseModel):
    """Response model for an escalation path."""

    path_id: str
    source_agent: str
    target_capability: str
    classification: str
    path: list[str]
    risk_score: float
    risk_level: str
    description: str = ""
    mitigation_suggestion: str = ""
    detection_time: str


class CoverageGapResponse(BaseModel):
    """Response model for a coverage gap."""

    gap_id: str
    agent_name: str
    agent_type: str
    dangerous_capabilities: list[str]
    missing_capabilities: list[str]
    gap_type: str
    risk_level: str
    recommendation: str = ""
    detection_time: str


class ToxicCombinationResponse(BaseModel):
    """Response model for a toxic combination."""

    combination_id: str
    agent_name: str
    capability_a: str
    capability_b: str
    conflict_type: str
    severity: str
    policy_reference: str = ""
    description: str = ""
    remediation: str = ""
    detection_time: str


class InheritanceTreeResponse(BaseModel):
    """Response model for an inheritance tree."""

    root_agent: str
    root_type: str
    tree: dict[str, Any]
    depth: int
    total_agents: int
    total_direct_capabilities: int
    total_inherited_capabilities: int
    calculated_at: str


class EffectiveCapabilitiesResponse(BaseModel):
    """Response model for effective capabilities."""

    agent_id: str
    agent_name: str
    agent_type: str
    execution_context: str
    capabilities: list[dict[str, Any]]
    calculated_at: str
    policy_version: str


class SyncRequest(BaseModel):
    """Request model for triggering policy sync."""

    agent_type: Optional[str] = Field(
        None, description="Specific agent type to sync (None for all)"
    )
    force: bool = Field(False, description="Force full resync")


class SyncResponse(BaseModel):
    """Response model for sync operation."""

    sync_id: str
    status: str
    vertices_created: int
    vertices_updated: int
    edges_created: int
    edges_deleted: int
    duration_ms: float
    errors: list[str] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    """Response model for full analysis."""

    analysis_id: str
    timestamp: str
    summary: dict[str, Any]
    escalation_paths: list[dict[str, Any]]
    coverage_gaps: list[dict[str, Any]]
    toxic_combinations: list[dict[str, Any]]
    visualization: dict[str, Any]


# ============================================================================
# Service Dependencies
# ============================================================================


def get_analyzer() -> CapabilityGraphAnalyzer:
    """Get the capability graph analyzer."""
    return get_capability_graph_analyzer()


def get_synchronizer() -> PolicyGraphSynchronizer:
    """Get the policy graph synchronizer."""
    return get_policy_graph_synchronizer()


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/visualization", response_model=VisualizationResponse)
async def get_visualization(
    include_escalation_paths: bool = Query(
        True, description="Highlight escalation paths in visualization"
    ),
) -> VisualizationResponse:
    """
    Get capability graph visualization data for frontend rendering.

    Returns nodes (agents and capabilities) and edges (relationships)
    formatted for D3.js force-directed graph visualization.
    """
    logger.info(
        f"Getting visualization data (include_escalation_paths={sanitize_log(include_escalation_paths)})"
    )
    analyzer = get_analyzer()

    try:
        viz = await analyzer.get_visualization_data(
            include_escalation_paths=include_escalation_paths
        )
        return VisualizationResponse(**viz.to_dict())
    except Exception as e:
        logger.error(f"Failed to get visualization data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def list_agents() -> list[dict[str, Any]]:
    """
    List all agents with their capability summaries.

    Returns a list of agents with basic capability information.
    """
    logger.info("Listing agents")
    synchronizer = get_synchronizer()

    try:
        graph = synchronizer.get_mock_graph()
        agents = []

        for vertex_id, vertex in graph["vertices"].items():
            if vertex.get("type") == "agent":
                # Count capabilities
                cap_count = len(
                    [
                        e
                        for e in graph["edges"]
                        if e["source_id"] == vertex_id
                        and e["edge_type"] == "has_capability"
                    ]
                )

                agents.append(
                    {
                        "agent_id": vertex_id,
                        "agent_type": vertex.get("agent_type", "Unknown"),
                        "policy_version": vertex.get("policy_version", "1.0"),
                        "capabilities_count": cap_count,
                        "allowed_contexts": vertex.get("allowed_contexts", []),
                    }
                )

        return agents
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/{agent_name}")
async def get_agent_graph(
    agent_name: str = Path(..., description="Agent name to get graph for"),
) -> dict[str, Any]:
    """
    Get capability graph for a specific agent.

    Returns the agent's direct capabilities and relationships.
    """
    logger.info(f"Getting graph for agent: {sanitize_log(agent_name)}")
    synchronizer = get_synchronizer()

    try:
        graph = synchronizer.get_mock_graph()
        agent_id = f"agent:{agent_name}"

        if agent_id not in graph["vertices"]:
            raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")

        agent = graph["vertices"][agent_id]

        # Get agent's edges
        agent_edges = [
            e
            for e in graph["edges"]
            if e["source_id"] == agent_id or e["target_id"] == agent_id
        ]

        # Get connected vertices
        connected_ids = set()
        for edge in agent_edges:
            connected_ids.add(edge["source_id"])
            connected_ids.add(edge["target_id"])

        connected_vertices = {
            vid: graph["vertices"][vid]
            for vid in connected_ids
            if vid in graph["vertices"]
        }

        return {
            "agent": agent,
            "edges": agent_edges,
            "connected_vertices": connected_vertices,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/escalation-paths", response_model=list[EscalationPathResponse])
async def get_escalation_paths(
    min_risk_score: float = Query(
        0.5, ge=0.0, le=1.0, description="Minimum risk score to return"
    ),
    max_depth: int = Query(5, ge=1, le=10, description="Maximum path depth"),
) -> list[EscalationPathResponse]:
    """
    Get detected privilege escalation paths.

    Returns chains of agent relationships that could enable
    unauthorized capability access through inheritance or delegation.
    """
    logger.info(
        f"Getting escalation paths (min_risk={sanitize_log(min_risk_score)}, max_depth={sanitize_log(max_depth)})"
    )
    analyzer = get_analyzer()

    try:
        paths = await analyzer.detect_escalation_paths(
            max_depth=max_depth,
            min_risk_score=min_risk_score,
        )
        return [EscalationPathResponse(**p.to_dict()) for p in paths]
    except Exception as e:
        logger.error(f"Failed to get escalation paths: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/coverage-gaps", response_model=list[CoverageGapResponse])
async def get_coverage_gaps() -> list[CoverageGapResponse]:
    """
    Get detected capability coverage gaps.

    Returns agents that have DANGEROUS capabilities without
    corresponding MONITORING capabilities, or other policy violations.
    """
    logger.info("Getting coverage gaps")
    analyzer = get_analyzer()

    try:
        gaps = await analyzer.find_coverage_gaps()
        return [CoverageGapResponse(**g.to_dict()) for g in gaps]
    except Exception as e:
        logger.error(f"Failed to get coverage gaps: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/toxic-combinations", response_model=list[ToxicCombinationResponse])
async def get_toxic_combinations() -> list[ToxicCombinationResponse]:
    """
    Get detected toxic capability combinations.

    Returns agents that hold capabilities which should not be combined,
    violating separation of duties or security policies.
    """
    logger.info("Getting toxic combinations")
    analyzer = get_analyzer()

    try:
        combinations = await analyzer.detect_toxic_combinations()
        return [ToxicCombinationResponse(**c.to_dict()) for c in combinations]
    except Exception as e:
        logger.error(f"Failed to get toxic combinations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inheritance/{agent_name}", response_model=InheritanceTreeResponse)
async def get_inheritance_tree(
    agent_name: str = Path(..., description="Agent name to get inheritance tree for"),
) -> InheritanceTreeResponse:
    """
    Get the capability inheritance tree for an agent.

    Shows how capabilities flow through parent-child relationships.
    """
    logger.info(f"Getting inheritance tree for: {sanitize_log(agent_name)}")
    analyzer = get_analyzer()

    try:
        tree = await analyzer.get_inheritance_tree(agent_name)
        return InheritanceTreeResponse(**tree.to_dict())
    except Exception as e:
        logger.error(f"Failed to get inheritance tree: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/effective/{agent_id}", response_model=EffectiveCapabilitiesResponse)
async def get_effective_capabilities(
    agent_id: str = Path(..., description="Agent ID"),
    agent_type: str = Query(..., description="Agent type (e.g., CoderAgent)"),
    execution_context: str = Query(
        "development",
        description="Execution context (test, sandbox, development, production)",
    ),
) -> EffectiveCapabilitiesResponse:
    """
    Get effective capabilities for an agent in a given context.

    Resolves all policy rules, grants, and inheritance to determine
    what an agent can actually do at runtime.
    """
    logger.info(
        f"Getting effective capabilities for {sanitize_log(agent_id)} ({sanitize_log(agent_type)}) in {sanitize_log(execution_context)}"
    )
    analyzer = get_analyzer()

    try:
        caps = await analyzer.calculate_effective_capabilities(
            agent_id=agent_id,
            agent_type=agent_type,
            execution_context=execution_context,
        )
        return EffectiveCapabilitiesResponse(**caps.to_dict())
    except Exception as e:
        logger.error(f"Failed to get effective capabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync", response_model=SyncResponse)
async def trigger_sync(request: SyncRequest) -> SyncResponse:
    """
    Trigger policy synchronization to the capability graph.

    Syncs agent capability policies to the Neptune graph database.
    """
    logger.info(
        f"Triggering sync (agent_type={sanitize_log(request.agent_type)}, force={sanitize_log(request.force)})"
    )
    synchronizer = get_synchronizer()

    try:
        if request.agent_type:
            # Sync specific agent
            from src.services.capability_governance import AgentCapabilityPolicy

            policy = AgentCapabilityPolicy.for_agent_type(request.agent_type)
            result = await synchronizer.sync_agent_capabilities(
                request.agent_type, policy
            )
        else:
            # Sync all agents
            result = await synchronizer.sync_all_policies()

        return SyncResponse(
            sync_id=result.sync_id,
            status=result.status.value,
            vertices_created=result.vertices_created,
            vertices_updated=result.vertices_updated,
            edges_created=result.edges_created,
            edges_deleted=result.edges_deleted,
            duration_ms=result.duration_ms,
            errors=result.errors,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis", response_model=AnalysisResponse)
async def run_analysis() -> AnalysisResponse:
    """
    Run full capability graph analysis.

    Executes all analysis queries and returns comprehensive results
    including escalation paths, coverage gaps, toxic combinations,
    and visualization data.
    """
    logger.info("Running full analysis")
    analyzer = get_analyzer()

    try:
        results = await analyzer.run_full_analysis()
        return AnalysisResponse(**results)
    except Exception as e:
        logger.error(f"Failed to run analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
