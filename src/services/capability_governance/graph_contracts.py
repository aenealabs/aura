"""
Project Aura - Capability Graph Contracts

Data contracts for the Cross-Agent Capability Graph Analysis system.
Implements ADR-071 for graph-based capability visualization and analysis.

Security Rationale:
- Immutable dataclasses ensure analysis results cannot be tampered with
- Type-safe edge types prevent graph corruption
- Explicit risk scoring enables audit and compliance reporting

Author: Project Aura Team
Created: 2026-01-27
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .contracts import ToolClassification


class VertexType(Enum):
    """
    Vertex types in the capability graph.

    Each vertex type represents a different entity in the capability model.
    """

    AGENT = "agent"  # Agent instances (Coder, Reviewer, Validator, etc.)
    CAPABILITY = "capability"  # Tool capabilities
    POLICY = "policy"  # Capability policies
    CONTEXT = "context"  # Execution contexts (test, sandbox, production)
    AUDIT_EVENT = "audit_event"  # Historical capability checks


class EdgeType(Enum):
    """
    Edge types in the capability graph.

    Defines relationships between vertices in the capability model.
    """

    HAS_CAPABILITY = "has_capability"  # Agent -> Capability
    INHERITS_FROM = "inherits_from"  # Agent -> Agent (parent relationship)
    DELEGATES_TO = "delegates_to"  # Agent -> Agent (spawned child)
    REQUIRES = "requires"  # Capability -> Capability (prerequisite)
    CONFLICTS_WITH = "conflicts_with"  # Capability -> Capability (mutex)
    RESTRICTED_TO = "restricted_to"  # Capability -> Context (allowed contexts)
    SELF_GOVERNANCE = "self_governance"  # Agent -> Governance Artifact (ADR-086)


class RiskLevel(Enum):
    """
    Risk levels for escalation paths and toxic combinations.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConflictType(Enum):
    """
    Types of capability conflicts for toxic combination detection.
    """

    MUTUAL_EXCLUSION = "mutual_exclusion"  # Cannot hold both capabilities
    SEPARATION_OF_DUTIES = "separation_of_duties"  # Security policy violation
    RESOURCE_CONTENTION = "resource_contention"  # Both require same resource
    PRIVILEGE_ESCALATION = "privilege_escalation"  # Combined enables escalation


@dataclass(frozen=True)
class GraphVertex:
    """
    A vertex in the capability graph.

    Represents an entity (agent, capability, policy, etc.) in the graph.
    """

    vertex_id: str
    vertex_type: VertexType
    label: str
    properties: tuple[tuple[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "vertex_id": self.vertex_id,
            "vertex_type": self.vertex_type.value,
            "label": self.label,
            "properties": dict(self.properties),
        }


@dataclass(frozen=True)
class GraphEdge:
    """
    An edge in the capability graph.

    Represents a relationship between two vertices.
    """

    edge_id: str
    edge_type: EdgeType
    source_id: str
    target_id: str
    properties: tuple[tuple[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "edge_id": self.edge_id,
            "edge_type": self.edge_type.value,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "properties": dict(self.properties),
        }


@dataclass(frozen=True)
class EscalationPath:
    """
    A detected privilege escalation path.

    Represents a chain of agent relationships that could enable
    unauthorized capability access through inheritance or delegation.
    """

    path_id: str
    source_agent: str
    target_capability: str
    classification: ToolClassification
    path: tuple[str, ...]  # Agent names in escalation chain
    risk_score: float  # 0.0 to 1.0
    risk_level: RiskLevel
    detection_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = ""
    mitigation_suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "path_id": self.path_id,
            "source_agent": self.source_agent,
            "target_capability": self.target_capability,
            "classification": self.classification.value,
            "path": list(self.path),
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "detection_time": self.detection_time.isoformat(),
            "description": self.description,
            "mitigation_suggestion": self.mitigation_suggestion,
        }

    @property
    def path_length(self) -> int:
        """Number of hops in the escalation path."""
        return len(self.path)

    @property
    def is_critical(self) -> bool:
        """Check if this path involves CRITICAL classification."""
        return self.classification == ToolClassification.CRITICAL


@dataclass(frozen=True)
class CoverageGap:
    """
    A detected capability coverage gap.

    Identifies agents that have DANGEROUS capabilities without corresponding
    MONITORING capabilities, or other policy violations.
    """

    gap_id: str
    agent_name: str
    agent_type: str
    dangerous_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]  # What should be present
    gap_type: str  # "missing_monitoring", "missing_audit", "orphaned_grant"
    risk_level: RiskLevel
    detection_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "gap_id": self.gap_id,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "dangerous_capabilities": list(self.dangerous_capabilities),
            "missing_capabilities": list(self.missing_capabilities),
            "gap_type": self.gap_type,
            "risk_level": self.risk_level.value,
            "detection_time": self.detection_time.isoformat(),
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class ToxicCombination:
    """
    A detected toxic capability combination.

    Identifies agents that hold capabilities which should not be combined,
    violating separation of duties or security policies.
    """

    combination_id: str
    agent_name: str
    capability_a: str
    capability_b: str
    conflict_type: ConflictType
    severity: RiskLevel
    policy_reference: str = ""  # Reference to violated policy
    detection_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = ""
    remediation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "combination_id": self.combination_id,
            "agent_name": self.agent_name,
            "capability_a": self.capability_a,
            "capability_b": self.capability_b,
            "conflict_type": self.conflict_type.value,
            "severity": self.severity.value,
            "policy_reference": self.policy_reference,
            "detection_time": self.detection_time.isoformat(),
            "description": self.description,
            "remediation": self.remediation,
        }


@dataclass
class InheritanceNode:
    """
    A node in the capability inheritance tree.

    Represents an agent and its inherited capabilities.
    """

    agent_name: str
    agent_type: str
    tier: int  # 0 = root, 1 = first generation, etc.
    direct_capabilities: list[str] = field(default_factory=list)
    inherited_capabilities: list[str] = field(default_factory=list)
    children: list["InheritanceNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "tier": self.tier,
            "direct_capabilities": self.direct_capabilities,
            "inherited_capabilities": self.inherited_capabilities,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class InheritanceTree:
    """
    Complete capability inheritance tree for an agent hierarchy.

    Shows how capabilities flow through parent-child relationships.
    """

    root_agent: str
    root_type: str
    tree: InheritanceNode
    depth: int
    total_agents: int
    total_direct_capabilities: int
    total_inherited_capabilities: int
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "root_agent": self.root_agent,
            "root_type": self.root_type,
            "tree": self.tree.to_dict(),
            "depth": self.depth,
            "total_agents": self.total_agents,
            "total_direct_capabilities": self.total_direct_capabilities,
            "total_inherited_capabilities": self.total_inherited_capabilities,
            "calculated_at": self.calculated_at.isoformat(),
        }


@dataclass(frozen=True)
class CapabilitySource:
    """
    Source information for an effective capability.

    Tracks where a capability came from (policy, grant, inheritance).
    """

    source_type: str  # "policy", "dynamic_grant", "inherited", "override"
    source_id: str  # Policy name, grant ID, parent agent ID
    granted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    constraints: tuple[tuple[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "constraints": dict(self.constraints),
        }


@dataclass
class EffectiveCapability:
    """
    A resolved effective capability for an agent.

    Combines information from policies, grants, and inheritance.
    """

    tool_name: str
    classification: ToolClassification
    actions: list[str]
    source: CapabilitySource
    is_temporary: bool = False
    context_restrictions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_name": self.tool_name,
            "classification": self.classification.value,
            "actions": self.actions,
            "source": self.source.to_dict(),
            "is_temporary": self.is_temporary,
            "context_restrictions": self.context_restrictions,
        }


@dataclass
class EffectiveCapabilities:
    """
    All effective capabilities for an agent in a given context.

    Complete resolution of what an agent can do at runtime.
    """

    agent_id: str
    agent_name: str
    agent_type: str
    execution_context: str
    capabilities: list[EffectiveCapability] = field(default_factory=list)
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    policy_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "execution_context": self.execution_context,
            "capabilities": [cap.to_dict() for cap in self.capabilities],
            "calculated_at": self.calculated_at.isoformat(),
            "policy_version": self.policy_version,
        }

    @property
    def capability_count(self) -> int:
        """Total number of effective capabilities."""
        return len(self.capabilities)

    @property
    def has_dangerous(self) -> bool:
        """Check if agent has any DANGEROUS capabilities."""
        return any(
            cap.classification == ToolClassification.DANGEROUS
            for cap in self.capabilities
        )

    @property
    def has_critical(self) -> bool:
        """Check if agent has any CRITICAL capabilities."""
        return any(
            cap.classification == ToolClassification.CRITICAL
            for cap in self.capabilities
        )

    def get_by_classification(
        self, classification: ToolClassification
    ) -> list[EffectiveCapability]:
        """Get capabilities of a specific classification."""
        return [
            cap for cap in self.capabilities if cap.classification == classification
        ]


@dataclass
class GraphVisualizationData:
    """
    Data formatted for frontend graph visualization.

    Optimized for D3.js force-directed graph rendering.
    """

    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "metadata": self.metadata,
        }

    def add_agent_node(
        self,
        agent_id: str,
        agent_type: str,
        capabilities_count: int,
        has_escalation_risk: bool = False,
    ) -> None:
        """Add an agent node to the visualization."""
        self.nodes.append(
            {
                "id": agent_id,
                "type": "agent",
                "label": agent_id,
                "agent_type": agent_type,
                "capabilities_count": capabilities_count,
                "has_escalation_risk": has_escalation_risk,
                "color": "#3B82F6",  # Blue for agents
            }
        )

    def add_capability_node(
        self,
        tool_name: str,
        classification: ToolClassification,
    ) -> None:
        """Add a capability node to the visualization."""
        color_map = {
            ToolClassification.SAFE: "#10B981",  # Green
            ToolClassification.MONITORING: "#F59E0B",  # Amber
            ToolClassification.DANGEROUS: "#EA580C",  # Orange
            ToolClassification.CRITICAL: "#DC2626",  # Red
        }
        self.nodes.append(
            {
                "id": f"cap_{tool_name}",
                "type": "capability",
                "label": tool_name,
                "classification": classification.value,
                "color": color_map.get(classification, "#6B7280"),
            }
        )

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: EdgeType,
        is_escalation_path: bool = False,
    ) -> None:
        """Add an edge to the visualization."""
        style_map = {
            EdgeType.HAS_CAPABILITY: "solid",
            EdgeType.INHERITS_FROM: "dashed",
            EdgeType.DELEGATES_TO: "dotted",
            EdgeType.REQUIRES: "solid",
            EdgeType.CONFLICTS_WITH: "dashed",
            EdgeType.RESTRICTED_TO: "dotted",
        }
        self.edges.append(
            {
                "source": source,
                "target": target,
                "type": edge_type.value,
                "style": style_map.get(edge_type, "solid"),
                "is_escalation_path": is_escalation_path,
                "color": "#DC2626" if is_escalation_path else "#9CA3AF",
            }
        )


# Type aliases for clarity
AgentId = str
ToolName = str
PathId = str
GapId = str
CombinationId = str
