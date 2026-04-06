"""
Project Aura - Capability Graph Analyzer

Core analysis engine for the Cross-Agent Capability Graph.
Implements ADR-071 for graph-based capability visualization and security analysis.

Key Analysis Queries:
1. Escalation Path Detection - Find privilege escalation chains
2. Coverage Gap Analysis - Identify policy gaps
3. Toxic Combination Detection - Find conflicting capabilities
4. Inheritance Tree Calculation - Visualize capability inheritance
5. Effective Capabilities Resolution - Runtime capability lookup

Security Rationale:
- Proactive detection of privilege escalation risks
- Policy gap identification before exploitation
- Separation of duties enforcement
- Complete audit trail for all analyses

Author: Project Aura Team
Created: 2026-01-27
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .contracts import ToolClassification
from .graph_contracts import (
    CapabilitySource,
    ConflictType,
    CoverageGap,
    EdgeType,
    EffectiveCapabilities,
    EffectiveCapability,
    EscalationPath,
    GraphVisualizationData,
    InheritanceNode,
    InheritanceTree,
    RiskLevel,
    ToxicCombination,
    VertexType,
)
from .graph_sync import PolicyGraphSynchronizer, get_policy_graph_synchronizer
from .policy import AgentCapabilityPolicy
from .registry import get_capability_registry

logger = logging.getLogger(__name__)


# Known toxic capability combinations (separation of duties violations)
TOXIC_COMBINATIONS = [
    # Cannot both write code and approve deployments
    ("commit_changes", "deploy_to_production", ConflictType.SEPARATION_OF_DUTIES),
    # Cannot both provision and destroy sandboxes
    ("provision_sandbox", "destroy_sandbox", ConflictType.RESOURCE_CONTENTION),
    # Cannot both modify IAM and access secrets
    ("modify_iam_policy", "access_secrets", ConflictType.PRIVILEGE_ESCALATION),
    # Cannot both rotate credentials and access secrets
    ("rotate_credentials", "access_secrets", ConflictType.PRIVILEGE_ESCALATION),
    # Cannot both delete repository and deploy to production
    ("delete_repository", "deploy_to_production", ConflictType.SEPARATION_OF_DUTIES),
]


class CapabilityGraphAnalyzer:
    """
    Analyzes the capability graph for security risks and policy violations.

    Provides graph traversal queries to detect escalation paths, coverage gaps,
    toxic combinations, and visualize capability inheritance.

    Usage:
        >>> analyzer = CapabilityGraphAnalyzer()
        >>> paths = await analyzer.detect_escalation_paths()
        >>> for path in paths:
        ...     print(f"Risk: {path.risk_level.value} - {path.source_agent} -> {path.target_capability}")

        >>> gaps = await analyzer.find_coverage_gaps()
        >>> viz = await analyzer.get_visualization_data()
    """

    def __init__(
        self,
        synchronizer: Optional[PolicyGraphSynchronizer] = None,
        mock_mode: bool = True,
    ):
        """
        Initialize the capability graph analyzer.

        Args:
            synchronizer: PolicyGraphSynchronizer instance (creates default if None)
            mock_mode: If True, use in-memory mock graph
        """
        self.synchronizer = synchronizer or get_policy_graph_synchronizer()
        self.mock_mode = mock_mode

        # Analysis cache
        self._escalation_paths_cache: Optional[list[EscalationPath]] = None
        self._coverage_gaps_cache: Optional[list[CoverageGap]] = None
        self._toxic_combinations_cache: Optional[list[ToxicCombination]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes

        logger.info(f"CapabilityGraphAnalyzer initialized (mock_mode={self.mock_mode})")

    def _is_cache_valid(self) -> bool:
        """Check if the analysis cache is still valid."""
        if self._cache_timestamp is None:
            return False
        elapsed = (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds()
        return elapsed < self._cache_ttl_seconds

    async def detect_escalation_paths(
        self,
        max_depth: int = 5,
        min_risk_score: float = 0.5,
    ) -> list[EscalationPath]:
        """
        Detect privilege escalation paths in the capability graph.

        Finds chains of agent relationships that could enable unauthorized
        capability access through inheritance or delegation.

        Args:
            max_depth: Maximum path length to search
            min_risk_score: Minimum risk score to report (0.0-1.0)

        Returns:
            List of detected escalation paths
        """
        # Return cached result if available and valid
        if self._escalation_paths_cache is not None and self._is_cache_valid():
            return self._escalation_paths_cache

        logger.info(f"Detecting escalation paths (max_depth={max_depth})")
        paths: list[EscalationPath] = []

        if self.mock_mode:
            # Analyze mock graph
            graph = self.synchronizer.get_mock_graph()
            vertices = graph["vertices"]
            edges = graph["edges"]

            # Find agent vertices
            agents = [
                v for v in vertices.values() if v.get("type") == VertexType.AGENT.value
            ]

            # For each agent, find paths to CRITICAL/DANGEROUS capabilities
            for agent in agents:
                agent_id = agent["id"]

                # Get direct capabilities
                direct_caps = [
                    e
                    for e in edges
                    if e["source_id"] == agent_id
                    and e["edge_type"] == EdgeType.HAS_CAPABILITY.value
                ]

                # Check for escalation via inherited/delegated capabilities
                # In a full implementation, this would traverse INHERITS_FROM
                # and DELEGATES_TO edges to find indirect paths

                for cap_edge in direct_caps:
                    classification = cap_edge.get("classification", "safe")

                    # High-risk if CRITICAL capability with delegation path
                    if classification == ToolClassification.CRITICAL.value:
                        risk_score = 0.9
                        risk_level = RiskLevel.CRITICAL
                    elif classification == ToolClassification.DANGEROUS.value:
                        risk_score = 0.7
                        risk_level = RiskLevel.HIGH
                    else:
                        continue  # Skip lower classifications

                    if risk_score >= min_risk_score:
                        tool_name = cap_edge["target_id"].replace("cap:", "")
                        path = EscalationPath(
                            path_id=f"path-{uuid.uuid4().hex[:8]}",
                            source_agent=agent_id.replace("agent:", ""),
                            target_capability=tool_name,
                            classification=ToolClassification(classification),
                            path=(agent_id.replace("agent:", ""),),
                            risk_score=risk_score,
                            risk_level=risk_level,
                            description=f"Direct access to {classification} capability",
                            mitigation_suggestion=(
                                "Consider adding HITL approval requirement"
                                if risk_level == RiskLevel.CRITICAL
                                else "Review policy constraints"
                            ),
                        )
                        paths.append(path)

        else:
            # Real Neptune query would use Gremlin traversal
            # g.V().hasLabel('agent').repeat(out('inherits_from', 'delegates_to'))
            #   .until(outE('has_capability').inV().has('classification', 'critical'))
            #   .path()
            pass

        logger.info(f"Found {len(paths)} escalation paths")
        self._escalation_paths_cache = paths
        self._cache_timestamp = datetime.now(timezone.utc)
        return paths

    async def find_coverage_gaps(self) -> list[CoverageGap]:
        """
        Find capability coverage gaps in agent policies.

        Identifies agents that have DANGEROUS capabilities without
        corresponding MONITORING capabilities, or other policy violations.

        Returns:
            List of detected coverage gaps
        """
        # Return cached result if available and valid
        if self._coverage_gaps_cache is not None and self._is_cache_valid():
            return self._coverage_gaps_cache

        logger.info("Finding coverage gaps")
        gaps: list[CoverageGap] = []

        if self.mock_mode:
            graph = self.synchronizer.get_mock_graph()
            vertices = graph["vertices"]
            edges = graph["edges"]

            # Find agent vertices
            agents = [
                v for v in vertices.values() if v.get("type") == VertexType.AGENT.value
            ]

            for agent in agents:
                agent_id = agent["id"]
                agent_name = agent_id.replace("agent:", "")
                agent_type = agent.get("agent_type", "Unknown")

                # Get agent's capabilities by classification
                agent_edges = [
                    e
                    for e in edges
                    if e["source_id"] == agent_id
                    and e["edge_type"] == EdgeType.HAS_CAPABILITY.value
                ]

                dangerous_caps = []
                monitoring_caps = []
                safe_caps = []

                for edge in agent_edges:
                    classification = edge.get("classification", "safe")
                    tool_name = edge["target_id"].replace("cap:", "")

                    if classification == ToolClassification.DANGEROUS.value:
                        dangerous_caps.append(tool_name)
                    elif classification == ToolClassification.MONITORING.value:
                        monitoring_caps.append(tool_name)
                    elif classification == ToolClassification.SAFE.value:
                        safe_caps.append(tool_name)

                # Gap: Has DANGEROUS but no MONITORING
                if dangerous_caps and not monitoring_caps:
                    gaps.append(
                        CoverageGap(
                            gap_id=f"gap-{uuid.uuid4().hex[:8]}",
                            agent_name=agent_name,
                            agent_type=agent_type,
                            dangerous_capabilities=tuple(dangerous_caps),
                            missing_capabilities=(
                                "query_audit_logs",
                                "get_agent_metrics",
                            ),
                            gap_type="missing_monitoring",
                            risk_level=RiskLevel.HIGH,
                            recommendation=(
                                "Add MONITORING capabilities to enable audit "
                                "trail for DANGEROUS operations"
                            ),
                        )
                    )

                # Gap: Has DANGEROUS but no SAFE read operations
                if dangerous_caps and not safe_caps:
                    gaps.append(
                        CoverageGap(
                            gap_id=f"gap-{uuid.uuid4().hex[:8]}",
                            agent_name=agent_name,
                            agent_type=agent_type,
                            dangerous_capabilities=tuple(dangerous_caps),
                            missing_capabilities=("semantic_search", "list_agents"),
                            gap_type="missing_read_operations",
                            risk_level=RiskLevel.MEDIUM,
                            recommendation=(
                                "Agent has write-only access; add read "
                                "capabilities for proper workflow"
                            ),
                        )
                    )

        logger.info(f"Found {len(gaps)} coverage gaps")
        self._coverage_gaps_cache = gaps
        self._cache_timestamp = datetime.now(timezone.utc)
        return gaps

    async def detect_toxic_combinations(self) -> list[ToxicCombination]:
        """
        Detect toxic capability combinations.

        Identifies agents that hold capabilities which should not be combined,
        violating separation of duties or security policies.

        Returns:
            List of detected toxic combinations
        """
        # Return cached result if available and valid
        if self._toxic_combinations_cache is not None and self._is_cache_valid():
            return self._toxic_combinations_cache

        logger.info("Detecting toxic combinations")
        combinations: list[ToxicCombination] = []

        if self.mock_mode:
            graph = self.synchronizer.get_mock_graph()
            vertices = graph["vertices"]
            edges = graph["edges"]

            # Find agent vertices
            agents = [
                v for v in vertices.values() if v.get("type") == VertexType.AGENT.value
            ]

            for agent in agents:
                agent_id = agent["id"]
                agent_name = agent_id.replace("agent:", "")

                # Get agent's capabilities
                agent_caps = set()
                for edge in edges:
                    if (
                        edge["source_id"] == agent_id
                        and edge["edge_type"] == EdgeType.HAS_CAPABILITY.value
                    ):
                        tool_name = edge["target_id"].replace("cap:", "")
                        agent_caps.add(tool_name)

                # Check against known toxic combinations
                for cap_a, cap_b, conflict_type in TOXIC_COMBINATIONS:
                    if cap_a in agent_caps and cap_b in agent_caps:
                        # Determine severity based on conflict type
                        if conflict_type == ConflictType.PRIVILEGE_ESCALATION:
                            severity = RiskLevel.CRITICAL
                        elif conflict_type == ConflictType.SEPARATION_OF_DUTIES:
                            severity = RiskLevel.HIGH
                        else:
                            severity = RiskLevel.MEDIUM

                        combinations.append(
                            ToxicCombination(
                                combination_id=f"toxic-{uuid.uuid4().hex[:8]}",
                                agent_name=agent_name,
                                capability_a=cap_a,
                                capability_b=cap_b,
                                conflict_type=conflict_type,
                                severity=severity,
                                policy_reference="ADR-066 Section 4.3",
                                description=(
                                    f"Agent holds both {cap_a} and {cap_b}, "
                                    f"violating {conflict_type.value} policy"
                                ),
                                remediation=(
                                    "Split capabilities across separate agents "
                                    "or implement compensating controls"
                                ),
                            )
                        )

        logger.info(f"Found {len(combinations)} toxic combinations")
        self._toxic_combinations_cache = combinations
        self._cache_timestamp = datetime.now(timezone.utc)
        return combinations

    async def get_inheritance_tree(
        self,
        agent_name: str,
    ) -> InheritanceTree:
        """
        Get the capability inheritance tree for an agent.

        Shows how capabilities flow through parent-child relationships.

        Args:
            agent_name: Name of the root agent

        Returns:
            InheritanceTree showing capability inheritance
        """
        logger.info(f"Getting inheritance tree for {agent_name}")

        # Get agent policy
        try:
            policy = AgentCapabilityPolicy.for_agent_type(agent_name)
        except ValueError:
            # Use default empty policy
            policy = AgentCapabilityPolicy(
                agent_type=agent_name,
                version="1.0",
                allowed_tools={},
                denied_tools=[],
                allowed_contexts=["test", "sandbox"],
            )

        # Build root node
        direct_caps = list(policy.allowed_tools.keys())
        root = InheritanceNode(
            agent_name=agent_name,
            agent_type=policy.agent_type,
            tier=0,
            direct_capabilities=direct_caps,
            inherited_capabilities=[],
            children=[],
        )

        # In a full implementation, we would traverse DELEGATES_TO edges
        # to find child agents and their inherited capabilities
        # For now, return simple tree with just the root

        tree = InheritanceTree(
            root_agent=agent_name,
            root_type=policy.agent_type,
            tree=root,
            depth=1,
            total_agents=1,
            total_direct_capabilities=len(direct_caps),
            total_inherited_capabilities=0,
        )

        return tree

    async def calculate_effective_capabilities(
        self,
        agent_id: str,
        agent_type: str,
        execution_context: str = "development",
    ) -> EffectiveCapabilities:
        """
        Calculate effective capabilities for an agent.

        Resolves all policy rules, grants, and inheritance to determine
        what an agent can actually do at runtime.

        Args:
            agent_id: Unique agent identifier
            agent_type: Type of agent (e.g., "CoderAgent")
            execution_context: Current execution context

        Returns:
            EffectiveCapabilities with resolved capabilities
        """
        logger.info(
            f"Calculating effective capabilities for {agent_id} ({agent_type}) "
            f"in {execution_context}"
        )

        # Get agent policy
        try:
            policy = AgentCapabilityPolicy.for_agent_type(agent_type)
        except ValueError:
            logger.warning(f"No policy found for {agent_type}, using empty policy")
            return EffectiveCapabilities(
                agent_id=agent_id,
                agent_name=agent_id,
                agent_type=agent_type,
                execution_context=execution_context,
                capabilities=[],
                policy_version="unknown",
            )

        # Check context is allowed
        if execution_context not in policy.allowed_contexts:
            logger.warning(f"Context {execution_context} not allowed for {agent_type}")
            return EffectiveCapabilities(
                agent_id=agent_id,
                agent_name=agent_id,
                agent_type=agent_type,
                execution_context=execution_context,
                capabilities=[],
                policy_version=policy.version,
            )

        # Get capability registry for classifications
        registry = get_capability_registry()

        # Build effective capabilities from policy
        capabilities: list[EffectiveCapability] = []

        for tool_name, actions in policy.allowed_tools.items():
            # Skip denied tools
            if tool_name in policy.denied_tools:
                continue

            # Get tool classification
            tool_info = registry.get_tool(tool_name)
            classification = (
                tool_info.classification if tool_info else ToolClassification.SAFE
            )

            # Create capability source
            source = CapabilitySource(
                source_type="policy",
                source_id=f"{agent_type}-policy",
                granted_at=None,
                expires_at=None,
                constraints=(),
            )

            capabilities.append(
                EffectiveCapability(
                    tool_name=tool_name,
                    classification=classification,
                    actions=actions,
                    source=source,
                    is_temporary=False,
                    context_restrictions=list(policy.allowed_contexts),
                )
            )

        return EffectiveCapabilities(
            agent_id=agent_id,
            agent_name=agent_id,
            agent_type=agent_type,
            execution_context=execution_context,
            capabilities=capabilities,
            policy_version=policy.version,
        )

    async def get_visualization_data(
        self,
        include_escalation_paths: bool = True,
    ) -> GraphVisualizationData:
        """
        Get graph data formatted for frontend visualization.

        Returns data optimized for D3.js force-directed graph rendering.

        Args:
            include_escalation_paths: Highlight escalation paths in visualization

        Returns:
            GraphVisualizationData ready for frontend
        """
        logger.info("Generating visualization data")

        viz = GraphVisualizationData(
            metadata={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "include_escalation_paths": include_escalation_paths,
            }
        )

        if self.mock_mode:
            graph = self.synchronizer.get_mock_graph()
            vertices = graph["vertices"]
            edges = graph["edges"]

            # Get escalation paths for highlighting
            escalation_edges: set[tuple[str, str]] = set()
            if include_escalation_paths:
                paths = await self.detect_escalation_paths()
                for path in paths:
                    if path.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
                        source = f"agent:{path.source_agent}"
                        target = f"cap:{path.target_capability}"
                        escalation_edges.add((source, target))

            # Build edge index keyed by source_id for O(1) lookup
            from collections import defaultdict

            edges_by_source: dict[str, list[dict]] = defaultdict(list)
            for e in edges:
                edges_by_source[e["source_id"]].append(e)

            # Build set of source vertices that appear in escalation edges
            escalation_sources = {src for src, _ in escalation_edges}

            # Add vertices
            for vertex in vertices.values():
                v_type = vertex.get("type", "")
                v_id = vertex.get("id", "")

                if v_type == VertexType.AGENT.value:
                    agent_type = vertex.get("agent_type", "Unknown")
                    cap_count = sum(
                        1
                        for e in edges_by_source.get(v_id, [])
                        if e["edge_type"] == EdgeType.HAS_CAPABILITY.value
                    )
                    has_risk = v_id in escalation_sources and any(
                        (v_id, t) in escalation_edges
                        for t in (tgt for _, tgt in escalation_edges)
                    )
                    viz.add_agent_node(
                        agent_id=v_id.replace("agent:", ""),
                        agent_type=agent_type,
                        capabilities_count=cap_count,
                        has_escalation_risk=has_risk,
                    )

                elif v_type == VertexType.CAPABILITY.value:
                    classification_str = vertex.get("classification", "safe")
                    try:
                        classification = ToolClassification(classification_str)
                    except ValueError:
                        classification = ToolClassification.SAFE
                    viz.add_capability_node(
                        tool_name=vertex.get("tool_name", v_id),
                        classification=classification,
                    )

            # Add edges
            for edge in edges:
                try:
                    edge_type = EdgeType(edge.get("edge_type", "has_capability"))
                except ValueError:
                    edge_type = EdgeType.HAS_CAPABILITY

                source = edge.get("source_id", "")
                target = edge.get("target_id", "")

                is_escalation = (source, target) in escalation_edges

                # Convert IDs for frontend
                if source.startswith("agent:"):
                    source = source.replace("agent:", "")
                if target.startswith("cap:"):
                    target = f"cap_{target.replace('cap:', '')}"
                elif target.startswith("agent:"):
                    target = target.replace("agent:", "")

                viz.add_edge(
                    source=source,
                    target=target,
                    edge_type=edge_type,
                    is_escalation_path=is_escalation,
                )

        viz.metadata["node_count"] = len(viz.nodes)
        viz.metadata["edge_count"] = len(viz.edges)

        logger.info(
            f"Generated visualization with {len(viz.nodes)} nodes "
            f"and {len(viz.edges)} edges"
        )

        return viz

    # -----------------------------------------------------------------
    # ADR-086 Phase 2: Self-Governance Edge Analysis
    # -----------------------------------------------------------------

    async def detect_self_modification_paths(
        self,
        max_depth: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Detect write-capability → self-governance-edge paths.

        Finds any agent that holds a write capability targeting a
        governance artifact that controls that same agent's future
        behavior. Returns paths that represent self-modification risk.

        Args:
            max_depth: Maximum path depth to search.

        Returns:
            List of self-modification path descriptions.
        """
        logger.info(f"Detecting self-modification paths (max_depth={max_depth})")
        paths: list[dict[str, Any]] = []

        if self.mock_mode:
            graph = self.synchronizer.get_mock_graph()
            edges = graph["edges"]

            # Find SELF_GOVERNANCE edges
            governance_edges = [
                e for e in edges if e.get("edge_type") == EdgeType.SELF_GOVERNANCE.value
            ]

            # Find write-capable agents
            write_caps = [
                e
                for e in edges
                if e.get("edge_type") == EdgeType.HAS_CAPABILITY.value
                and e.get("classification")
                in (
                    ToolClassification.DANGEROUS.value,
                    ToolClassification.CRITICAL.value,
                )
            ]

            # Cross-reference: agent has write cap AND self-governance edge
            for gov_edge in governance_edges:
                agent_id = gov_edge["source_id"]
                artifact_id = gov_edge["target_id"]

                agent_write_caps = [
                    e["target_id"] for e in write_caps if e["source_id"] == agent_id
                ]

                if agent_write_caps:
                    paths.append(
                        {
                            "agent_id": agent_id.replace("agent:", ""),
                            "governance_artifact": artifact_id,
                            "write_capabilities": [
                                c.replace("cap:", "") for c in agent_write_caps
                            ],
                            "depth": 1,
                            "risk_level": "critical",
                            "description": (
                                f"Agent can modify governance artifact "
                                f"'{artifact_id}' that controls its own behavior"
                            ),
                        }
                    )

        else:
            # Neptune Gremlin query:
            # g.V().hasLabel('agent')
            #   .as('a')
            #   .outE('self_governance').inV().as('gov')
            #   .select('a')
            #   .outE('has_capability')
            #   .has('classification', within('dangerous','critical'))
            #   .select('a','gov')
            pass

        logger.info(f"Found {len(paths)} self-modification paths")
        return paths

    def add_self_governance_edge(
        self,
        agent_id: str,
        artifact_id: str,
        artifact_class: str,
    ) -> None:
        """
        Add a SELF_GOVERNANCE edge to the graph.

        Links an agent vertex to the governance artifact controlling it.

        Args:
            agent_id: Agent being governed.
            artifact_id: Governance artifact identifier.
            artifact_class: Class of the governance artifact.
        """
        if self.mock_mode:
            edge = {
                "source_id": f"agent:{agent_id}",
                "target_id": artifact_id,
                "edge_type": EdgeType.SELF_GOVERNANCE.value,
                "artifact_class": artifact_class,
            }
            self.synchronizer._mock_edges.append(edge)
            logger.info(
                f"Added SELF_GOVERNANCE edge: {agent_id} -> "
                f"{artifact_id} ({artifact_class})"
            )
        else:
            # Neptune: g.V('agent:{agent_id}')
            #   .addE('self_governance')
            #   .to(g.V(artifact_id))
            #   .property('artifact_class', artifact_class)
            pass

    async def run_full_analysis(self) -> dict[str, Any]:
        """
        Run all analysis queries and return comprehensive results.

        Useful for scheduled analysis jobs and dashboards.

        Returns:
            Dictionary with all analysis results
        """
        logger.info("Running full capability graph analysis")

        escalation_paths = await self.detect_escalation_paths()
        coverage_gaps = await self.find_coverage_gaps()
        toxic_combinations = await self.detect_toxic_combinations()
        self_mod_paths = await self.detect_self_modification_paths()
        visualization = await self.get_visualization_data()

        # Calculate summary metrics
        critical_issues = len(
            [p for p in escalation_paths if p.risk_level == RiskLevel.CRITICAL]
        ) + len([c for c in toxic_combinations if c.severity == RiskLevel.CRITICAL])
        high_issues = (
            len([p for p in escalation_paths if p.risk_level == RiskLevel.HIGH])
            + len([g for g in coverage_gaps if g.risk_level == RiskLevel.HIGH])
            + len([c for c in toxic_combinations if c.severity == RiskLevel.HIGH])
        )

        return {
            "analysis_id": f"analysis-{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_escalation_paths": len(escalation_paths),
                "total_coverage_gaps": len(coverage_gaps),
                "total_toxic_combinations": len(toxic_combinations),
                "critical_issues": critical_issues,
                "high_issues": high_issues,
                "risk_score": min(1.0, (critical_issues * 0.3 + high_issues * 0.1)),
            },
            "escalation_paths": [p.to_dict() for p in escalation_paths],
            "coverage_gaps": [g.to_dict() for g in coverage_gaps],
            "toxic_combinations": [c.to_dict() for c in toxic_combinations],
            "self_modification_paths": self_mod_paths,
            "visualization": visualization.to_dict(),
        }

    def clear_cache(self) -> None:
        """Clear analysis cache."""
        self._escalation_paths_cache = None
        self._coverage_gaps_cache = None
        self._toxic_combinations_cache = None
        self._cache_timestamp = None


# Singleton instance
_analyzer: Optional[CapabilityGraphAnalyzer] = None


def get_capability_graph_analyzer() -> CapabilityGraphAnalyzer:
    """Get the singleton CapabilityGraphAnalyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = CapabilityGraphAnalyzer()
    return _analyzer


def reset_capability_graph_analyzer() -> None:
    """Reset the singleton instance (for testing)."""
    global _analyzer
    _analyzer = None
