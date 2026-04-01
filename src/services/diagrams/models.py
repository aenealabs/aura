"""
Data models for Enterprise Diagram Generation (ADR-060).

Defines the core data structures for diagram definitions, nodes, groups,
connections, and layout constraints used throughout the diagram service.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ConnectionStyle(Enum):
    """Connection line styles for diagram edges."""

    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


class ArrowDirection(Enum):
    """Arrow direction for connections."""

    FORWARD = "forward"  # Source -> Target
    BACKWARD = "backward"  # Source <- Target
    BOTH = "both"  # Source <-> Target
    NONE = "none"  # Source -- Target


class NodeShape(Enum):
    """Node shape types."""

    RECTANGLE = "rectangle"
    ROUNDED = "rounded"
    DIAMOND = "diamond"
    CIRCLE = "circle"
    CYLINDER = "cylinder"
    CLOUD = "cloud"
    HEXAGON = "hexagon"
    ICON = "icon"  # Uses cloud provider icon


class LayoutDirection(Enum):
    """Layout direction for the diagram."""

    TOP_BOTTOM = "TB"
    BOTTOM_TOP = "BT"
    LEFT_RIGHT = "LR"
    RIGHT_LEFT = "RL"


@dataclass
class Position:
    """2D position coordinates."""

    x: float
    y: float


@dataclass
class Size:
    """2D size dimensions."""

    width: float
    height: float


@dataclass
class NodeStyle:
    """Visual styling for a node."""

    fill_color: Optional[str] = None
    border_color: Optional[str] = None
    border_width: float = 1.0
    text_color: Optional[str] = None
    font_size: float = 12.0
    font_weight: str = "normal"
    opacity: float = 1.0
    shadow: bool = False


@dataclass
class ConnectionLabel:
    """Label configuration for a connection."""

    text: str
    position: float = 0.5  # 0.0 = start, 1.0 = end
    offset_x: float = 0.0
    offset_y: float = 0.0
    font_size: float = 10.0


@dataclass
class DiagramNode:
    """
    A node in the diagram representing a component or service.

    Attributes:
        id: Unique identifier for the node
        label: Display label for the node
        icon_id: Optional cloud provider icon ID (e.g., 'aws:ec2', 'azure:vm')
        shape: Node shape when not using icon
        metadata: Additional metadata (description, type, tags)
        style: Visual styling overrides
        position: Computed position after layout (set by LayoutEngine)
        size: Computed size after layout (set by LayoutEngine)
    """

    id: str
    label: str
    icon_id: Optional[str] = None
    shape: NodeShape = NodeShape.ROUNDED
    metadata: dict[str, Any] = field(default_factory=dict)
    style: Optional[NodeStyle] = None
    position: Optional[Position] = None
    size: Optional[Size] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("Node id cannot be empty")
        if not self.label:
            self.label = self.id


@dataclass
class DiagramGroup:
    """
    A container group for organizing nodes (e.g., VPC, namespace, module).

    Groups can be nested to represent hierarchical structures like
    Terraform modules, Kubernetes namespaces, or AWS VPCs.

    Attributes:
        id: Unique identifier for the group
        label: Display label for the group
        children: List of node IDs or nested group IDs contained in this group
        parent_id: Optional parent group ID for nested groups
        color: Border/highlight color for the group
        metadata: Additional metadata (description, type)
        position: Computed position after layout
        size: Computed size after layout
    """

    id: str
    label: str
    children: list[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    color: Optional[str] = None
    collapsed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    position: Optional[Position] = None
    size: Optional[Size] = None


@dataclass
class DiagramConnection:
    """
    A connection/edge between two nodes.

    Attributes:
        id: Unique identifier for the connection
        source: Source node ID
        target: Target node ID
        label: Optional label for the connection
        style: Line style (solid, dashed, dotted)
        arrow: Arrow direction
        color: Line color override
        metadata: Additional metadata (protocol, port, etc.)
        points: Computed routing points after layout
    """

    id: str
    source: str
    target: str
    label: Optional[ConnectionLabel] = None
    style: ConnectionStyle = ConnectionStyle.SOLID
    arrow: ArrowDirection = ArrowDirection.FORWARD
    color: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    points: list[Position] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = f"{self.source}->{self.target}"


@dataclass
class LayoutConstraint:
    """
    Layout constraint for positioning nodes.

    Used to influence the ELK.js layout algorithm with specific
    positioning requirements.
    """

    type: str  # 'align', 'order', 'position', 'layer'
    nodes: list[str]
    value: Any = None


@dataclass
class DiagramMetadata:
    """Metadata about the diagram itself."""

    title: str
    description: Optional[str] = None
    author: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0"
    tags: list[str] = field(default_factory=list)
    confidence_score: Optional[float] = None
    references_used: list[str] = field(default_factory=list)


@dataclass
class DiagramDefinition:
    """
    Complete diagram definition containing all elements.

    This is the primary data structure that flows through the
    diagram generation pipeline: DSL Parser -> Layout Engine -> SVG Renderer

    Attributes:
        metadata: Diagram metadata (title, description, etc.)
        nodes: List of nodes in the diagram
        groups: List of groups/containers
        connections: List of connections between nodes
        constraints: Layout constraints for positioning
        direction: Overall layout direction
        width: Target width (optional, auto-sized if not specified)
        height: Target height (optional, auto-sized if not specified)
    """

    metadata: DiagramMetadata
    nodes: list[DiagramNode] = field(default_factory=list)
    groups: list[DiagramGroup] = field(default_factory=list)
    connections: list[DiagramConnection] = field(default_factory=list)
    constraints: list[LayoutConstraint] = field(default_factory=list)
    direction: LayoutDirection = LayoutDirection.TOP_BOTTOM
    width: Optional[float] = None
    height: Optional[float] = None

    def get_node(self, node_id: str) -> Optional[DiagramNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_group(self, group_id: str) -> Optional[DiagramGroup]:
        """Get a group by ID."""
        for group in self.groups:
            if group.id == group_id:
                return group
        return None

    def get_nodes_in_group(self, group_id: str) -> list[DiagramNode]:
        """Get all nodes belonging to a group."""
        group = self.get_group(group_id)
        if not group:
            return []
        return [n for n in self.nodes if n.id in group.children]

    def validate(self) -> list[str]:
        """
        Validate the diagram definition for consistency.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check for duplicate node IDs
        node_ids = [n.id for n in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            errors.append("Duplicate node IDs detected")

        # Check for duplicate group IDs
        group_ids = [g.id for g in self.groups]
        if len(group_ids) != len(set(group_ids)):
            errors.append("Duplicate group IDs detected")

        # Check connection references exist
        all_ids = set(node_ids + group_ids)
        for conn in self.connections:
            if conn.source not in all_ids:
                errors.append(f"Connection source '{conn.source}' not found")
            if conn.target not in all_ids:
                errors.append(f"Connection target '{conn.target}' not found")

        # Check group children exist
        for group in self.groups:
            for child_id in group.children:
                if child_id not in all_ids:
                    errors.append(
                        f"Group child '{child_id}' not found in group '{group.id}'"
                    )

        return errors


@dataclass
class GenerationRequest:
    """Request for AI-powered diagram generation."""

    prompt: str
    diagram_type: Optional[str] = None  # architecture, sequence, data-flow, etc.
    target_provider: Optional[str] = None  # aws, azure, gcp
    include_references: bool = True
    max_nodes: int = 50
    classification: str = "internal"  # public, internal, confidential, cui


@dataclass
class GenerationResult:
    """Result of AI-powered diagram generation."""

    definition: DiagramDefinition
    dsl_output: str
    confidence_score: float
    references_used: list[dict[str, Any]]
    model_used: str
    provider_used: str
    generation_time_ms: int
    warnings: list[str] = field(default_factory=list)
