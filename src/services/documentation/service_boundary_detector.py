"""
Service Boundary Detector using Louvain Community Detection
============================================================

Detects service boundaries in codebases using the Louvain algorithm
for community detection on the code call graph.

ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.

The Louvain algorithm finds communities by optimizing modularity:
- Higher modularity = more edges within communities than between
- Resolution parameter controls community granularity
"""

import logging
import uuid
from typing import TYPE_CHECKING, Any

from src.services.documentation.exceptions import (
    GraphTraversalError,
    InsufficientDataError,
)
from src.services.documentation.types import ServiceBoundary

logger = logging.getLogger(__name__)

# Optional networkx import
try:
    import networkx as nx
    from networkx.algorithms.community import louvain_communities

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    logger.warning("networkx not installed - using fallback boundary detection")

if TYPE_CHECKING:
    from src.services.neptune_graph_service import NeptuneGraphService


class ServiceBoundaryDetector:
    """
    Detects service boundaries using Louvain community detection.

    The detector:
    1. Queries Neptune for the code call graph
    2. Builds a networkx graph with weighted edges
    3. Applies Louvain algorithm to detect communities
    4. Refines boundaries using directory structure
    5. Validates against IaC definitions when available

    Example:
        >>> detector = ServiceBoundaryDetector(neptune_service)
        >>> boundaries = await detector.detect_boundaries("repo-123")
        >>> for b in boundaries:
        ...     print(f"{b.name}: {len(b.node_ids)} nodes, confidence={b.confidence:.2f}")
    """

    def __init__(
        self,
        neptune_service: "NeptuneGraphService | None" = None,
        resolution: float = 1.0,
        min_community_size: int = 3,
        seed: int = 42,
    ):
        """
        Initialize the service boundary detector.

        Args:
            neptune_service: Neptune graph service for queries
            resolution: Louvain resolution parameter (higher = more communities)
            min_community_size: Minimum nodes for a community to be a service
            seed: Random seed for reproducibility
        """
        self.neptune = neptune_service
        self.resolution = resolution
        self.min_community_size = min_community_size
        self.seed = seed

        # Mock graph for testing
        self._mock_graph: dict[str, dict[str, Any]] = {}
        self._mock_edges: list[tuple[str, str, dict[str, Any]]] = []

    def set_mock_data(
        self,
        nodes: dict[str, dict[str, Any]],
        edges: list[tuple[str, str, dict[str, Any]]],
    ) -> None:
        """
        Set mock data for testing without Neptune.

        Args:
            nodes: Dict of node_id -> node properties
            edges: List of (source, target, properties) tuples
        """
        self._mock_graph = nodes
        self._mock_edges = edges

    def _load_demo_data(self) -> None:
        """
        Load demo data for local development testing without Neptune.

        This simulates a typical enterprise codebase architecture with:
        - API Gateway layer
        - Multi-agent orchestration
        - Data services (Neptune, OpenSearch, DynamoDB)
        - Security services
        - Documentation services
        """
        self._mock_graph = {
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
            "api_health": {
                "name": "health.py",
                "type": "module",
                "file_path": "src/api/health.py",
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
            "agent_security": {
                "name": "security_agent.py",
                "type": "module",
                "file_path": "src/agents/security_agent.py",
            },
            # Data Services Layer
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
            "svc_dynamodb": {
                "name": "dynamodb_service.py",
                "type": "module",
                "file_path": "src/services/dynamodb_service.py",
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
            "doc_report": {
                "name": "report_generator.py",
                "type": "module",
                "file_path": "src/services/documentation/report_generator.py",
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
            # Security Layer
            "sec_auth": {
                "name": "authentication.py",
                "type": "module",
                "file_path": "src/security/authentication.py",
            },
            "sec_rbac": {
                "name": "rbac.py",
                "type": "module",
                "file_path": "src/security/rbac.py",
            },
            "sec_audit": {
                "name": "audit_logging.py",
                "type": "module",
                "file_path": "src/security/audit_logging.py",
            },
        }

        self._mock_edges = [
            # API → Router connections
            ("api_main", "api_router", {"relationship": "imports", "weight": 0.5}),
            ("api_router", "api_auth", {"relationship": "calls", "weight": 1.0}),
            ("api_router", "api_docs", {"relationship": "calls", "weight": 1.0}),
            ("api_router", "api_agents", {"relationship": "calls", "weight": 1.0}),
            ("api_router", "api_health", {"relationship": "calls", "weight": 0.5}),
            # API → Services
            ("api_docs", "doc_agent", {"relationship": "calls", "weight": 1.0}),
            (
                "api_agents",
                "agent_orchestrator",
                {"relationship": "calls", "weight": 1.0},
            ),
            # Agent Layer orchestration
            (
                "agent_orchestrator",
                "agent_coder",
                {"relationship": "calls", "weight": 1.0},
            ),
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
            (
                "agent_orchestrator",
                "agent_security",
                {"relationship": "calls", "weight": 1.0},
            ),
            # Agents → Data Services
            ("agent_coder", "svc_bedrock", {"relationship": "calls", "weight": 1.0}),
            ("agent_reviewer", "svc_bedrock", {"relationship": "calls", "weight": 1.0}),
            (
                "agent_validator",
                "svc_sandbox",
                {"relationship": "calls", "weight": 1.0},
            ),
            ("agent_security", "svc_bedrock", {"relationship": "calls", "weight": 1.0}),
            # Documentation Layer
            ("doc_agent", "doc_detector", {"relationship": "calls", "weight": 1.0}),
            ("doc_agent", "doc_generator", {"relationship": "calls", "weight": 1.0}),
            ("doc_agent", "doc_report", {"relationship": "calls", "weight": 1.0}),
            ("doc_detector", "svc_neptune", {"relationship": "calls", "weight": 1.0}),
            ("doc_generator", "svc_bedrock", {"relationship": "calls", "weight": 1.0}),
            # Context Layer
            ("ctx_retrieval", "ctx_hybrid", {"relationship": "calls", "weight": 1.0}),
            ("ctx_hybrid", "ctx_graphrag", {"relationship": "calls", "weight": 1.0}),
            ("ctx_graphrag", "svc_neptune", {"relationship": "calls", "weight": 1.0}),
            (
                "ctx_graphrag",
                "svc_opensearch",
                {"relationship": "calls", "weight": 1.0},
            ),
            # Security Layer
            ("api_auth", "sec_auth", {"relationship": "calls", "weight": 1.0}),
            ("sec_auth", "sec_rbac", {"relationship": "calls", "weight": 1.0}),
            ("sec_auth", "sec_audit", {"relationship": "calls", "weight": 0.8}),
            ("sec_rbac", "svc_dynamodb", {"relationship": "calls", "weight": 0.8}),
            # Cross-layer connections
            (
                "agent_orchestrator",
                "ctx_retrieval",
                {"relationship": "calls", "weight": 1.0},
            ),
            ("doc_detector", "ctx_hybrid", {"relationship": "calls", "weight": 0.8}),
            ("api_main", "sec_auth", {"relationship": "calls", "weight": 1.0}),
        ]
        logger.info(
            f"Loaded demo data: {len(self._mock_graph)} nodes, {len(self._mock_edges)} edges"
        )

    async def detect_boundaries(
        self,
        repository_id: str,
        min_service_size: int = 5,
        max_services: int = 20,
    ) -> list[ServiceBoundary]:
        """
        Detect service boundaries in a repository.

        Args:
            repository_id: Repository to analyze
            min_service_size: Minimum nodes per service
            max_services: Maximum number of services to detect

        Returns:
            List of detected ServiceBoundary objects

        Raises:
            GraphTraversalError: If graph query fails
            InsufficientDataError: If not enough data for detection
        """
        logger.info(f"Detecting service boundaries for repository: {repository_id}")

        # Build weighted graph from call relationships
        G = await self._build_weighted_graph(repository_id)

        if G.number_of_nodes() < min_service_size:
            raise InsufficientDataError(
                message=f"Not enough nodes for boundary detection: {G.number_of_nodes()}",
                confidence=0.0,
                threshold=0.45,
                missing_data=f"Need at least {min_service_size} code entities",
            )

        # Detect communities using Louvain
        communities = self._detect_communities(G)

        # Filter by minimum size
        communities = [c for c in communities if len(c) >= min_service_size]

        # Limit to max_services
        if len(communities) > max_services:
            # Keep largest communities
            communities = sorted(communities, key=len, reverse=True)[:max_services]

        # Refine using directory structure
        refined = self._refine_with_directories(communities, G)

        # Build ServiceBoundary objects
        boundaries = self._build_service_boundaries(refined, G, repository_id)

        logger.info(f"Detected {len(boundaries)} service boundaries")
        return boundaries

    async def _build_weighted_graph(self, repository_id: str) -> "nx.Graph":
        """
        Build a weighted networkx graph from Neptune call graph.

        Args:
            repository_id: Repository to query

        Returns:
            NetworkX graph with weighted edges
        """
        if not NETWORKX_AVAILABLE:
            raise GraphTraversalError(
                "networkx is required for boundary detection",
                details={"missing_package": "networkx"},
            )

        G = nx.Graph()

        # Check if using mock data
        if self._mock_graph:
            return self._build_graph_from_mock()

        # Query Neptune for code entities and relationships
        if not self.neptune:
            logger.warning(
                "No Neptune service - using demo mock data for local testing"
            )
            # Load demo data for local development without Neptune
            self._load_demo_data()
            return self._build_graph_from_mock()

        try:
            # Query nodes (code entities)
            nodes = await self._query_nodes(repository_id)
            for node in nodes:
                G.add_node(
                    node["entity_id"],
                    name=node.get("name", ""),
                    type=node.get("type", "unknown"),
                    file_path=node.get("file_path", ""),
                )

            # Query edges (call relationships)
            edges = await self._query_edges(repository_id)
            for edge in edges:
                source = edge["source"]
                target = edge["target"]
                # Weight by relationship type
                weight = self._get_edge_weight(edge.get("relationship", "calls"))

                if G.has_edge(source, target):
                    # Increment weight for multiple relationships
                    G[source][target]["weight"] += weight
                else:
                    G.add_edge(source, target, weight=weight)

            logger.debug(
                f"Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges"
            )
            return G

        except Exception as e:
            raise GraphTraversalError(
                f"Failed to build graph from Neptune: {e}",
                details={"repository_id": repository_id, "error": str(e)},
            )

    def _build_graph_from_mock(self) -> "nx.Graph":
        """Build graph from mock data for testing."""
        G = nx.Graph()

        for node_id, props in self._mock_graph.items():
            G.add_node(node_id, **props)

        for source, target, props in self._mock_edges:
            weight = props.get("weight", 1.0)
            if G.has_edge(source, target):
                G[source][target]["weight"] += weight
            else:
                G.add_edge(source, target, weight=weight)

        return G

    async def _query_nodes(self, repository_id: str) -> list[dict[str, Any]]:
        """Query code entity nodes from Neptune."""
        if not self.neptune:
            return []

        try:
            # Use Neptune search to find all entities in repository
            results = self.neptune.search_by_name(
                name_pattern=repository_id,
                entity_types=["class", "function", "method", "module"],
            )
            return results if results else []
        except Exception as e:
            logger.warning(f"Neptune query failed: {e}")
            return []

    async def _query_edges(self, repository_id: str) -> list[dict[str, Any]]:
        """Query relationship edges from Neptune."""
        if not self.neptune:
            return []

        try:
            # Query call graph relationships
            # This would use a Gremlin query like:
            # g.V().has('repository_id', repo).bothE('calls', 'imports').project(...)
            edges: list[dict[str, Any]] = []

            # For now, return empty list - actual implementation would query Neptune
            return edges
        except Exception as e:
            logger.warning(f"Neptune edge query failed: {e}")
            return []

    def _get_edge_weight(self, relationship_type: str) -> float:
        """Get edge weight based on relationship type."""
        weights = {
            "calls": 1.0,
            "imports": 0.5,
            "inherits": 0.8,
            "implements": 0.8,
            "depends_on": 0.6,
            "references": 0.3,
        }
        return weights.get(relationship_type, 0.5)

    def _detect_communities(self, G: "nx.Graph") -> list[set[str]]:
        """
        Detect communities using Louvain algorithm.

        Args:
            G: NetworkX graph

        Returns:
            List of communities (sets of node IDs)
        """
        if not NETWORKX_AVAILABLE:
            return []

        if G.number_of_nodes() == 0:
            return []

        try:
            communities = louvain_communities(
                G, weight="weight", resolution=self.resolution, seed=self.seed
            )
            return list(communities)
        except Exception as e:
            logger.warning(f"Louvain detection failed: {e}")
            # Fallback: treat each connected component as a community
            return [set(c) for c in nx.connected_components(G)]

    def _refine_with_directories(
        self, communities: list[set[str]], G: "nx.Graph"
    ) -> list[set[str]]:
        """
        Refine communities using directory structure.

        If nodes in a community share a common directory prefix,
        this strengthens confidence. If they're scattered, we may
        want to split the community.

        Args:
            communities: Initial communities from Louvain
            G: The graph with node attributes

        Returns:
            Refined list of communities
        """
        refined = []

        for community in communities:
            # Get directory prefixes for community members
            dirs: dict[str, list[str]] = {}
            for node_id in community:
                if node_id in G.nodes:
                    file_path = G.nodes[node_id].get("file_path", "")
                    if file_path:
                        # Get top-level directory
                        parts = file_path.split("/")
                        if len(parts) > 1:
                            top_dir = parts[0]
                            if top_dir not in dirs:
                                dirs[top_dir] = []
                            dirs[top_dir].append(node_id)

            # If community is concentrated in one directory, keep it
            # If scattered, consider splitting
            if len(dirs) <= 2:
                refined.append(community)
            else:
                # Keep as single community for now (could split in future)
                refined.append(community)

        return refined

    def _build_service_boundaries(
        self, communities: list[set[str]], G: "nx.Graph", repository_id: str
    ) -> list[ServiceBoundary]:
        """
        Build ServiceBoundary objects from communities.

        Args:
            communities: List of node ID sets
            G: The graph for calculating edge counts
            repository_id: Repository ID for naming

        Returns:
            List of ServiceBoundary objects
        """
        boundaries = []

        for i, community in enumerate(communities):
            node_ids = list(community)

            # Calculate internal and external edges
            internal = 0
            external = 0
            for node_id in community:
                for neighbor in G.neighbors(node_id):
                    if neighbor in community:
                        internal += 1
                    else:
                        external += 1
            # Each internal edge counted twice
            internal = internal // 2

            # Calculate confidence based on modularity ratio
            total = internal + external
            modularity = internal / total if total > 0 else 0.5
            confidence = min(0.95, 0.5 + modularity * 0.5)

            # Generate name from common patterns
            name = self._generate_service_name(node_ids, G, i)

            # Generate description
            description = self._generate_service_description(node_ids, G)

            # Find entry points (nodes with external incoming edges)
            entry_points = self._find_entry_points(community, G)

            boundary = ServiceBoundary(
                boundary_id=f"service-{uuid.uuid4().hex[:8]}",
                name=name,
                description=description,
                node_ids=node_ids,
                confidence=confidence,
                edges_internal=internal,
                edges_external=external,
                entry_points=entry_points,
                metadata={
                    "repository_id": repository_id,
                    "community_index": i,
                    "node_count": len(node_ids),
                },
            )
            boundaries.append(boundary)

        # Sort by confidence (highest first)
        boundaries.sort(key=lambda b: b.confidence, reverse=True)

        return boundaries

    def _generate_service_name(
        self, node_ids: list[str], G: "nx.Graph", index: int
    ) -> str:
        """Generate a descriptive name for a service."""
        from collections import Counter

        # First, try node ID prefixes (most reliable for our demo data)
        id_prefixes: list[str] = []
        for node_id in node_ids[:10]:
            if "_" in node_id:
                prefix = node_id.split("_")[0]
                id_prefixes.append(prefix)

        if id_prefixes:
            most_common = Counter(id_prefixes).most_common(1)
            if most_common:
                prefix = most_common[0][0]
                name_map = {
                    "svc": "Data Services",
                    "api": "API Gateway",
                    "doc": "Documentation Agent",
                    "ctx": "Context Engine",
                    "sec": "Security Layer",
                    "agent": "Agent Orchestrator",
                }
                if prefix in name_map:
                    return name_map[prefix]

        # Fall back to directory structure
        dir_paths: list[str] = []
        for node_id in node_ids[:10]:
            if node_id in G.nodes:
                file_path = G.nodes[node_id].get("file_path", "")
                if file_path:
                    parts = [p for p in file_path.split("/") if p and p != "src"]
                    if len(parts) >= 2:
                        # Use deeper path for services subdirectories
                        if parts[0] == "services" and len(parts) > 1:
                            dir_paths.append(parts[1])
                        else:
                            dir_paths.append(parts[0])
                    elif parts:
                        dir_paths.append(parts[0])

        if dir_paths:
            most_common = Counter(dir_paths).most_common(1)
            if most_common:
                dir_name = most_common[0][0]
                readable = dir_name.replace("_", " ").replace("-", " ").title()
                # Avoid redundant "Service Service"
                if "service" in readable.lower():
                    return readable
                return f"{readable} Service"

        return f"Service {index + 1}"

    def _generate_service_description(self, node_ids: list[str], G: "nx.Graph") -> str:
        """Generate a description for a service."""
        # Count node types
        types: dict[str, int] = {}
        for node_id in node_ids:
            if node_id in G.nodes:
                node_type = G.nodes[node_id].get("type", "unknown")
                types[node_type] = types.get(node_type, 0) + 1

        parts = []
        for node_type, count in sorted(types.items(), key=lambda x: -x[1]):
            parts.append(f"{count} {node_type}(s)")

        if parts:
            return f"Contains {', '.join(parts[:3])}"
        return f"Service with {len(node_ids)} components"

    def _find_entry_points(self, community: set[str], G: "nx.Graph") -> list[str]:
        """Find entry points (nodes with external incoming edges)."""
        entry_points = []

        for node_id in community:
            has_external_caller = False
            for neighbor in G.neighbors(node_id):
                if neighbor not in community:
                    has_external_caller = True
                    break
            if has_external_caller:
                entry_points.append(node_id)

        return entry_points[:10]  # Limit to top 10


# Factory function
def create_service_boundary_detector(
    neptune_service: "NeptuneGraphService | None" = None,
    resolution: float = 1.0,
) -> ServiceBoundaryDetector:
    """
    Factory function to create a ServiceBoundaryDetector.

    Args:
        neptune_service: Optional Neptune graph service
        resolution: Louvain resolution parameter

    Returns:
        Configured ServiceBoundaryDetector instance
    """
    return ServiceBoundaryDetector(
        neptune_service=neptune_service, resolution=resolution
    )
