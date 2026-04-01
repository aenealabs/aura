"""
Layout Engine for Enterprise Diagram Generation (ADR-060).

Provides constraint-based graph layout using:
- Pure Python implementation (default, no external dependencies)
- ELK.js integration via subprocess (optional, for production quality)

Supports:
- Hierarchical layouts (top-to-bottom, left-to-right)
- Group/container nesting
- Edge routing with minimal crossings
- Constraint-based positioning

Based on the Sugiyama algorithm for hierarchical graph layout.
"""

import json
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .models import DiagramDefinition, DiagramGroup, LayoutDirection, Position, Size


class LayoutBackend(Enum):
    """Available layout backends."""

    PYTHON = "python"  # Pure Python implementation
    ELKJS = "elkjs"  # ELK.js via Node.js subprocess


@dataclass
class LayoutConfig:
    """
    Configuration for the layout algorithm.

    Values based on research of Eraser.io, ELK.js, and AWS Architecture
    diagram best practices for professional-quality output.

    Eraser.io Style:
    - Square-ish nodes with large icon on top, label below
    - Grid layout within groups
    - Clear separation between groups
    """

    # Node dimensions (larger for readable labels)
    node_width: float = 120.0
    node_height: float = 100.0

    # Node spacing within groups (generous for clarity)
    node_spacing_horizontal: float = 60.0
    node_spacing_vertical: float = 60.0

    # Group padding (space around nodes inside group)
    group_padding: float = 40.0
    group_header_height: float = 36.0

    # Group spacing (space between groups)
    group_spacing: float = 40.0

    # Edge routing
    edge_spacing: float = 15.0
    edge_corner_radius: float = 8.0

    # Canvas (professional padding around diagram)
    canvas_padding: float = 60.0

    # Grid layout settings
    max_nodes_per_row: int = 4  # Max nodes in a row within a group

    # Performance limits
    max_iterations: int = 100


@dataclass
class LayoutResult:
    """Result of layout computation."""

    definition: DiagramDefinition  # Modified with positions/sizes
    width: float
    height: float
    warnings: list[str] = field(default_factory=list)
    computation_time_ms: int = 0


class LayoutEngine:
    """
    Graph layout engine for diagram generation.

    Implements a layered (Sugiyama) approach for hierarchical layouts:
    1. Cycle removal (break cycles for DAG)
    2. Layer assignment (assign nodes to horizontal layers)
    3. Crossing minimization (order nodes within layers)
    4. Coordinate assignment (compute x,y positions)
    5. Edge routing (route edges between nodes)

    Usage:
        engine = LayoutEngine()
        result = engine.layout(definition)
        # definition.nodes now have position and size set
    """

    def __init__(
        self,
        config: Optional[LayoutConfig] = None,
        backend: LayoutBackend = LayoutBackend.PYTHON,
        elkjs_path: Optional[str] = None,
    ):
        """
        Initialize the layout engine.

        Args:
            config: Layout configuration
            backend: Which layout backend to use
            elkjs_path: Path to ELK.js CLI (if using ELKJS backend)
        """
        self.config = config or LayoutConfig()
        self.backend = backend
        self.elkjs_path = elkjs_path

    def layout(self, definition: DiagramDefinition) -> LayoutResult:
        """
        Compute layout for a diagram definition.

        Args:
            definition: The diagram to lay out

        Returns:
            LayoutResult with positioned elements
        """
        if self.backend == LayoutBackend.ELKJS and self.elkjs_path:
            return self._layout_with_elkjs(definition)
        return self._layout_python(definition)

    def _layout_python(self, definition: DiagramDefinition) -> LayoutResult:
        """
        Pure Python layout implementation using group-based positioning.

        Algorithm:
        1. Build node-to-group mapping
        2. Arrange nodes within each group in a grid
        3. Calculate group bounds
        4. Position groups in a flow layout (no overlaps)
        5. Position ungrouped nodes
        6. Route edges
        """
        warnings: list[str] = []

        # Step 1: Build node-to-group mapping
        node_to_group = self._build_node_group_mapping(definition)

        # Step 2: Group-based layout
        group_positions = self._layout_groups_grid(definition, node_to_group)

        # Step 3: Position ungrouped nodes
        self._layout_ungrouped_nodes(definition, node_to_group, group_positions)

        # Step 4: Route edges
        self._route_edges(definition)

        # Step 5: Normalize positions (ensure all positive)
        self._normalize_all_positions(definition)

        # Compute canvas size
        width, height = self._compute_canvas_size(definition)

        return LayoutResult(
            definition=definition,
            width=width,
            height=height,
            warnings=warnings,
        )

    def _build_node_group_mapping(
        self,
        definition: DiagramDefinition,
    ) -> dict[str, str]:
        """Build mapping of node ID to its containing group ID."""
        node_to_group: dict[str, str] = {}

        for group in definition.groups:
            for child_id in group.children:
                # Only map to first group (avoid duplicates)
                if child_id not in node_to_group:
                    node_to_group[child_id] = group.id

        return node_to_group

    def _layout_groups_grid(
        self,
        definition: DiagramDefinition,
        node_to_group: dict[str, str],
    ) -> dict[str, tuple[float, float, float, float]]:
        """
        Layout groups with their nodes arranged in a grid.

        Returns dict of group_id -> (x, y, width, height)
        """
        config = self.config
        group_bounds: dict[str, tuple[float, float, float, float]] = {}

        # Current position for placing groups
        current_x = config.canvas_padding
        current_y = config.canvas_padding
        row_max_height = 0.0
        canvas_width_limit = 1200.0  # Max width before wrapping to new row

        # Pre-build group -> node_ids mapping (O(N) once instead of O(G*N))
        nodes_by_group: dict[str, list[str]] = defaultdict(list)
        for nid, gid in node_to_group.items():
            nodes_by_group[gid].append(nid)
        node_by_id = {n.id: n for n in definition.nodes}

        for group in definition.groups:
            # Get nodes in this group (O(K) per group via pre-built index)
            group_node_ids = nodes_by_group.get(group.id, [])
            group_nodes = [
                node_by_id[nid] for nid in group_node_ids if nid in node_by_id
            ]

            if not group_nodes:
                continue

            # Arrange nodes in a grid within the group
            nodes_per_row = min(len(group_nodes), config.max_nodes_per_row)
            num_rows = (len(group_nodes) + nodes_per_row - 1) // nodes_per_row

            # Calculate group dimensions
            inner_width = (
                nodes_per_row * config.node_width
                + (nodes_per_row - 1) * config.node_spacing_horizontal
            )
            inner_height = (
                num_rows * config.node_height
                + (num_rows - 1) * config.node_spacing_vertical
            )

            group_width = inner_width + 2 * config.group_padding
            group_height = (
                inner_height + 2 * config.group_padding + config.group_header_height
            )

            # Check if we need to wrap to next row
            if (
                current_x + group_width > canvas_width_limit
                and current_x > config.canvas_padding
            ):
                current_x = config.canvas_padding
                current_y += row_max_height + config.group_spacing
                row_max_height = 0.0

            # Position the group
            group.position = Position(x=current_x, y=current_y)
            group.size = Size(width=group_width, height=group_height)

            # Position nodes within the group (grid layout)
            node_start_x = current_x + config.group_padding
            node_start_y = current_y + config.group_padding + config.group_header_height

            for i, node in enumerate(group_nodes):
                row = i // nodes_per_row
                col = i % nodes_per_row

                node.position = Position(
                    x=node_start_x
                    + col * (config.node_width + config.node_spacing_horizontal),
                    y=node_start_y
                    + row * (config.node_height + config.node_spacing_vertical),
                )
                node.size = Size(width=config.node_width, height=config.node_height)

            # Store group bounds
            group_bounds[group.id] = (current_x, current_y, group_width, group_height)

            # Update position for next group
            current_x += group_width + config.group_spacing
            row_max_height = max(row_max_height, group_height)

        return group_bounds

    def _layout_ungrouped_nodes(
        self,
        definition: DiagramDefinition,
        node_to_group: dict[str, str],
        group_bounds: dict[str, tuple[float, float, float, float]],
    ) -> None:
        """Position nodes that aren't in any group."""
        config = self.config

        # Find ungrouped nodes
        ungrouped = [n for n in definition.nodes if n.id not in node_to_group]

        if not ungrouped:
            return

        # Find the bottom of all groups
        max_y = config.canvas_padding
        for _, (_gx, gy, _gw, gh) in group_bounds.items():
            max_y = max(max_y, gy + gh)

        # Position ungrouped nodes below groups in a row
        start_y = max_y + config.group_spacing
        start_x = config.canvas_padding

        for i, node in enumerate(ungrouped):
            col = i % config.max_nodes_per_row
            row = i // config.max_nodes_per_row

            node.position = Position(
                x=start_x + col * (config.node_width + config.node_spacing_horizontal),
                y=start_y + row * (config.node_height + config.node_spacing_vertical),
            )
            node.size = Size(width=config.node_width, height=config.node_height)

    def _normalize_all_positions(self, definition: DiagramDefinition) -> None:
        """Ensure all positions are positive with proper padding."""
        min_x = float("inf")
        min_y = float("inf")

        # Find minimum positions
        for node in definition.nodes:
            if node.position:
                min_x = min(min_x, node.position.x)
                min_y = min(min_y, node.position.y)

        for group in definition.groups:
            if group.position:
                min_x = min(min_x, group.position.x)
                min_y = min(min_y, group.position.y)

        # Apply offset if needed
        if min_x < self.config.canvas_padding or min_y < self.config.canvas_padding:
            offset_x = max(0, self.config.canvas_padding - min_x)
            offset_y = max(0, self.config.canvas_padding - min_y)

            for node in definition.nodes:
                if node.position:
                    node.position.x += offset_x
                    node.position.y += offset_y

            for group in definition.groups:
                if group.position:
                    group.position.x += offset_x
                    group.position.y += offset_y

    def _build_graph(self, definition: DiagramDefinition) -> dict[str, set[str]]:
        """Build adjacency list from connections."""
        graph: dict[str, set[str]] = {node.id: set() for node in definition.nodes}

        for conn in definition.connections:
            if conn.source in graph:
                graph[conn.source].add(conn.target)

        return graph

    def _assign_layers(
        self,
        graph: dict[str, set[str]],
        definition: DiagramDefinition,
    ) -> list[list[str]]:
        """
        Assign nodes to layers using longest path layering.

        Nodes with no incoming edges go to layer 0, others are placed
        based on their longest path from a source node.
        """
        # Compute in-degree
        in_degree: dict[str, int] = dict.fromkeys(graph, 0)
        for _source, targets in graph.items():
            for target in targets:
                if target in in_degree:
                    in_degree[target] += 1

        # Find source nodes (in-degree 0)
        layer_assignment: dict[str, int] = {}
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]

        # If no sources, pick arbitrary starting point
        if not queue and graph:
            queue = [next(iter(graph))]

        # BFS to assign layers
        for node_id in queue:
            layer_assignment[node_id] = 0

        current_layer = 0
        while queue:
            next_queue = []
            for node_id in queue:
                for target in graph.get(node_id, set()):
                    if target not in layer_assignment:
                        layer_assignment[target] = current_layer + 1
                        next_queue.append(target)
                    else:
                        # Update to longer path if applicable
                        layer_assignment[target] = max(
                            layer_assignment[target], current_layer + 1
                        )
            queue = next_queue
            current_layer += 1

        # Handle disconnected nodes
        for node in definition.nodes:
            if node.id not in layer_assignment:
                layer_assignment[node.id] = 0

        # Convert to layer lists
        max_layer = max(layer_assignment.values()) if layer_assignment else 0
        layers: list[list[str]] = [[] for _ in range(max_layer + 1)]
        for node_id, layer in layer_assignment.items():
            layers[layer].append(node_id)

        return layers

    def _minimize_crossings(
        self,
        layers: list[list[str]],
        graph: dict[str, set[str]],
    ) -> list[list[str]]:
        """
        Minimize edge crossings using the barycenter heuristic.

        Iteratively reorder nodes within each layer based on the
        average position of their connected nodes in adjacent layers.
        """
        if len(layers) <= 1:
            return layers

        # Build reverse graph for upward connections
        reverse_graph: dict[str, set[str]] = {node_id: set() for node_id in graph}
        for source, targets in graph.items():
            for target in targets:
                if target in reverse_graph:
                    reverse_graph[target].add(source)

        # Iterate to minimize crossings
        for _ in range(self.config.max_iterations):
            changed = False

            # Forward pass (layer 0 to n)
            for i in range(1, len(layers)):
                new_order = self._order_layer_by_barycenter(
                    layers[i], layers[i - 1], reverse_graph
                )
                if new_order != layers[i]:
                    layers[i] = new_order
                    changed = True

            # Backward pass (layer n to 0)
            for i in range(len(layers) - 2, -1, -1):
                new_order = self._order_layer_by_barycenter(
                    layers[i], layers[i + 1], graph
                )
                if new_order != layers[i]:
                    layers[i] = new_order
                    changed = True

            if not changed:
                break

        return layers

    def _order_layer_by_barycenter(
        self,
        layer: list[str],
        adjacent_layer: list[str],
        connections: dict[str, set[str]],
    ) -> list[str]:
        """Order nodes in a layer based on barycenter of connections."""
        if not layer or not adjacent_layer:
            return layer

        # Create position map for adjacent layer
        positions = {node_id: i for i, node_id in enumerate(adjacent_layer)}

        # Create position map for current layer (for disconnected nodes)
        layer_pos = {node_id: i for i, node_id in enumerate(layer)}

        # Compute barycenter for each node
        barycenters: list[tuple[float, str]] = []
        for node_id in layer:
            connected = connections.get(node_id, set())
            connected_positions = [positions[c] for c in connected if c in positions]
            if connected_positions:
                barycenter = sum(connected_positions) / len(connected_positions)
            else:
                # Keep original order for disconnected nodes
                barycenter = layer_pos.get(node_id, 0)
            barycenters.append((barycenter, node_id))

        # Sort by barycenter
        barycenters.sort(key=lambda x: x[0])
        return [node_id for _, node_id in barycenters]

    def _assign_coordinates(
        self,
        layers: list[list[str]],
        definition: DiagramDefinition,
    ) -> None:
        """Assign x,y coordinates to nodes based on layer assignment."""
        config = self.config
        direction = definition.direction

        # Determine if horizontal or vertical layout
        is_horizontal = direction in (
            LayoutDirection.LEFT_RIGHT,
            LayoutDirection.RIGHT_LEFT,
        )

        for layer_idx, layer in enumerate(layers):
            for node_idx, node_id in enumerate(layer):
                node = definition.get_node(node_id)
                if not node:
                    continue

                if is_horizontal:
                    # Horizontal layout: layers are columns
                    x = config.canvas_padding + layer_idx * (
                        config.node_width + config.node_spacing_horizontal
                    )
                    y = config.canvas_padding + node_idx * (
                        config.node_height + config.node_spacing_vertical
                    )
                else:
                    # Vertical layout: layers are rows
                    x = config.canvas_padding + node_idx * (
                        config.node_width + config.node_spacing_horizontal
                    )
                    y = config.canvas_padding + layer_idx * (
                        config.node_height + config.node_spacing_vertical
                    )

                # Handle reversed directions
                if direction == LayoutDirection.RIGHT_LEFT:
                    x = -x  # Will be normalized later
                elif direction == LayoutDirection.BOTTOM_TOP:
                    y = -y  # Will be normalized later

                node.position = Position(x=x, y=y)
                node.size = Size(width=config.node_width, height=config.node_height)

        # Normalize negative positions
        self._normalize_positions(definition)

    def _normalize_positions(self, definition: DiagramDefinition) -> None:
        """Normalize positions to ensure all coordinates are positive."""
        if not definition.nodes:
            return

        min_x = min(n.position.x for n in definition.nodes if n.position)
        min_y = min(n.position.y for n in definition.nodes if n.position)

        if min_x < 0 or min_y < 0:
            offset_x = abs(min_x) + self.config.canvas_padding if min_x < 0 else 0
            offset_y = abs(min_y) + self.config.canvas_padding if min_y < 0 else 0

            for node in definition.nodes:
                if node.position:
                    node.position.x += offset_x
                    node.position.y += offset_y

    def _layout_groups(self, definition: DiagramDefinition) -> None:
        """Compute positions and sizes for groups based on their children."""
        config = self.config

        # Process groups from innermost to outermost (by nesting depth)
        groups_by_depth = self._get_groups_by_depth(definition)

        for depth in sorted(groups_by_depth.keys()):
            for group in groups_by_depth[depth]:
                # Find bounding box of children
                child_nodes = definition.get_nodes_in_group(group.id)
                if not child_nodes:
                    continue

                min_x = min(n.position.x for n in child_nodes if n.position)
                max_x = max(
                    n.position.x + n.size.width
                    for n in child_nodes
                    if n.position and n.size
                )
                min_y = min(n.position.y for n in child_nodes if n.position)
                max_y = max(
                    n.position.y + n.size.height
                    for n in child_nodes
                    if n.position and n.size
                )

                # Add padding and header
                group.position = Position(
                    x=min_x - config.group_padding,
                    y=min_y - config.group_padding - config.group_header_height,
                )
                group.size = Size(
                    width=max_x - min_x + 2 * config.group_padding,
                    height=max_y
                    - min_y
                    + 2 * config.group_padding
                    + config.group_header_height,
                )

    def _get_groups_by_depth(
        self,
        definition: DiagramDefinition,
    ) -> dict[int, list[DiagramGroup]]:
        """Get groups organized by nesting depth (0 = innermost)."""
        depths: dict[str, int] = {}

        def get_depth(group_id: str) -> int:
            if group_id in depths:
                return depths[group_id]

            group = definition.get_group(group_id)
            if not group or not group.parent_id:
                depths[group_id] = 0
                return 0

            parent_depth = get_depth(group.parent_id)
            depths[group_id] = parent_depth + 1
            return depths[group_id]

        for group in definition.groups:
            get_depth(group.id)

        result: dict[int, list[DiagramGroup]] = {}
        for group in definition.groups:
            depth = depths.get(group.id, 0)
            if depth not in result:
                result[depth] = []
            result[depth].append(group)

        return result

    def _route_edges(self, definition: DiagramDefinition) -> None:
        """Route edges between nodes with orthogonal path finding."""
        for conn in definition.connections:
            source = definition.get_node(conn.source)
            target = definition.get_node(conn.target)

            if not source or not target:
                continue
            if not source.position or not target.position:
                continue
            if not source.size or not target.size:
                continue

            # Determine optimal connection ports based on relative positions
            source_center_x = source.position.x + source.size.width / 2
            source_center_y = source.position.y + source.size.height / 2
            target_center_x = target.position.x + target.size.width / 2
            target_center_y = target.position.y + target.size.height / 2

            dx = target_center_x - source_center_x
            dy = target_center_y - source_center_y

            # Calculate connection points at node edges
            if abs(dy) > abs(dx):
                # Vertical connection (top/bottom ports)
                if dy > 0:
                    # Source bottom to target top
                    source_x = source_center_x
                    source_y = source.position.y + source.size.height
                    target_x = target_center_x
                    target_y = target.position.y
                else:
                    # Source top to target bottom
                    source_x = source_center_x
                    source_y = source.position.y
                    target_x = target_center_x
                    target_y = target.position.y + target.size.height
            else:
                # Horizontal connection (left/right ports)
                if dx > 0:
                    # Source right to target left
                    source_x = source.position.x + source.size.width
                    source_y = source_center_y
                    target_x = target.position.x
                    target_y = target_center_y
                else:
                    # Source left to target right
                    source_x = source.position.x
                    source_y = source_center_y
                    target_x = target.position.x + target.size.width
                    target_y = target_center_y

            # Create orthogonal path with bend points
            conn.points = self._create_orthogonal_path(
                source_x, source_y, target_x, target_y, definition.direction
            )

    def _create_orthogonal_path(
        self,
        sx: float,
        sy: float,
        tx: float,
        ty: float,
        direction: LayoutDirection,
    ) -> list[Position]:
        """
        Create an orthogonal (right-angle) path between two points.

        Produces clean, professional-looking edges with 90-degree bends.
        """
        points = [Position(x=sx, y=sy)]

        is_horizontal = direction in (
            LayoutDirection.LEFT_RIGHT,
            LayoutDirection.RIGHT_LEFT,
        )

        dx = tx - sx
        dy = ty - sy

        # For vertical layouts (TB/BT), create horizontal-then-vertical paths
        # For horizontal layouts (LR/RL), create vertical-then-horizontal paths
        if is_horizontal:
            # Horizontal layout: bend vertically first, then horizontally
            if abs(dy) > 5:  # Non-trivial vertical distance
                mid_x = sx + dx / 2
                points.append(Position(x=mid_x, y=sy))
                points.append(Position(x=mid_x, y=ty))
            # else: straight horizontal line
        else:
            # Vertical layout: bend horizontally in the middle
            if abs(dx) > 5:  # Non-trivial horizontal distance
                mid_y = sy + dy / 2
                points.append(Position(x=sx, y=mid_y))
                points.append(Position(x=tx, y=mid_y))
            # else: straight vertical line

        points.append(Position(x=tx, y=ty))
        return points

    def _compute_canvas_size(
        self,
        definition: DiagramDefinition,
    ) -> tuple[float, float]:
        """Compute total canvas size needed for the diagram."""
        if not definition.nodes and not definition.groups:
            return 400.0, 300.0  # Default size

        max_x = 0.0
        max_y = 0.0

        for node in definition.nodes:
            if node.position and node.size:
                max_x = max(max_x, node.position.x + node.size.width)
                max_y = max(max_y, node.position.y + node.size.height)

        for group in definition.groups:
            if group.position and group.size:
                max_x = max(max_x, group.position.x + group.size.width)
                max_y = max(max_y, group.position.y + group.size.height)

        return (
            max_x + self.config.canvas_padding,
            max_y + self.config.canvas_padding,
        )

    def _layout_with_elkjs(self, definition: DiagramDefinition) -> LayoutResult:
        """
        Layout using ELK.js via Node.js subprocess.

        Requires Node.js and elkjs to be installed:
        npm install -g elkjs
        """
        warnings: list[str] = []

        # Convert definition to ELK JSON format
        elk_graph = self._to_elk_format(definition)

        try:
            # Write to temp file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(elk_graph, f)
                input_path = f.name

            # Call ELK.js CLI
            result = subprocess.run(
                [self.elkjs_path or "elkjs", input_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                warnings.append(f"ELK.js error: {result.stderr}")
                return self._layout_python(definition)

            # Parse result
            elk_result = json.loads(result.stdout)
            self._apply_elk_result(definition, elk_result)

            width = elk_result.get("width", 400)
            height = elk_result.get("height", 300)

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            warnings.append(f"ELK.js unavailable: {e}, using Python fallback")
            return self._layout_python(definition)
        finally:
            # Clean up temp file
            Path(input_path).unlink(missing_ok=True)

        return LayoutResult(
            definition=definition,
            width=width,
            height=height,
            warnings=warnings,
        )

    def _to_elk_format(self, definition: DiagramDefinition) -> dict[str, Any]:
        """Convert diagram definition to ELK JSON format."""
        config = self.config

        # Map layout direction
        direction_map = {
            LayoutDirection.TOP_BOTTOM: "DOWN",
            LayoutDirection.BOTTOM_TOP: "UP",
            LayoutDirection.LEFT_RIGHT: "RIGHT",
            LayoutDirection.RIGHT_LEFT: "LEFT",
        }

        return {
            "id": "root",
            "layoutOptions": {
                "elk.algorithm": "layered",
                "elk.direction": direction_map.get(definition.direction, "DOWN"),
                "elk.spacing.nodeNode": config.node_spacing_horizontal,
                "elk.layered.spacing.nodeNodeBetweenLayers": config.node_spacing_vertical,
            },
            "children": [
                {
                    "id": node.id,
                    "width": config.node_width,
                    "height": config.node_height,
                }
                for node in definition.nodes
            ],
            "edges": [
                {
                    "id": conn.id,
                    "sources": [conn.source],
                    "targets": [conn.target],
                }
                for conn in definition.connections
            ],
        }

    def _apply_elk_result(
        self,
        definition: DiagramDefinition,
        elk_result: dict[str, Any],
    ) -> None:
        """Apply ELK.js layout result to definition."""
        # Map node positions from ELK result
        node_positions = {
            child["id"]: child for child in elk_result.get("children", [])
        }

        for node in definition.nodes:
            if node.id in node_positions:
                elk_node = node_positions[node.id]
                node.position = Position(
                    x=elk_node.get("x", 0),
                    y=elk_node.get("y", 0),
                )
                node.size = Size(
                    width=elk_node.get("width", self.config.node_width),
                    height=elk_node.get("height", self.config.node_height),
                )

        # Map edge routes
        edge_routes = {edge["id"]: edge for edge in elk_result.get("edges", [])}

        for conn in definition.connections:
            if conn.id in edge_routes:
                elk_edge = edge_routes[conn.id]
                sections = elk_edge.get("sections", [])
                if sections:
                    section = sections[0]
                    conn.points = [
                        Position(
                            x=section.get("startPoint", {}).get("x", 0),
                            y=section.get("startPoint", {}).get("y", 0),
                        )
                    ]
                    for bp in section.get("bendPoints", []):
                        conn.points.append(Position(x=bp["x"], y=bp["y"]))
                    conn.points.append(
                        Position(
                            x=section.get("endPoint", {}).get("x", 0),
                            y=section.get("endPoint", {}).get("y", 0),
                        )
                    )
