"""
Eraser-style DSL Parser for Enterprise Diagram Generation (ADR-060).

Parses YAML-based diagram definitions with security validation to prevent:
- YAML deserialization attacks
- Oversized input DoS
- Malicious construct injection

DSL Format Example:
    title: AWS Architecture
    direction: TB
    groups:
      - id: vpc
        label: VPC
        children: [api, db]
    nodes:
      - id: api
        label: API Gateway
        icon: aws:api-gateway
      - id: db
        label: DynamoDB
        icon: aws:dynamodb
    connections:
      - source: api
        target: db
        label: Query
        style: solid
"""

import re
from dataclasses import dataclass
from typing import Any

import yaml

from .models import (
    ArrowDirection,
    ConnectionLabel,
    ConnectionStyle,
    DiagramConnection,
    DiagramDefinition,
    DiagramGroup,
    DiagramMetadata,
    DiagramNode,
    LayoutConstraint,
    LayoutDirection,
    NodeShape,
    NodeStyle,
)


class DSLValidationError(Exception):
    """Raised when DSL content fails validation."""


class DSLParseError(Exception):
    """Raised when DSL content cannot be parsed."""


@dataclass
class DSLParseResult:
    """Result of DSL parsing."""

    definition: DiagramDefinition
    warnings: list[str]
    raw_yaml: dict[str, Any]


class DiagramDSLParser:
    """
    Parser for Eraser-style diagram DSL with security validation.

    Implements security measures from architecture review:
    - Size limits to prevent DoS
    - YAML safe_load to prevent deserialization attacks
    - Pattern detection for dangerous constructs
    - Input sanitization

    Usage:
        parser = DiagramDSLParser()
        result = parser.parse(dsl_content)
        diagram = result.definition
    """

    # Security limits
    MAX_DSL_SIZE = 100_000  # 100KB max
    MAX_NODES = 200
    MAX_GROUPS = 50
    MAX_CONNECTIONS = 500
    MAX_LABEL_LENGTH = 200
    MAX_ID_LENGTH = 100

    # Dangerous YAML patterns (architecture security review)
    DANGEROUS_PATTERNS = [
        r"!!python/",  # Python object instantiation
        r"!!ruby/",  # Ruby object instantiation
        r"!!\w+/\w+",  # Generic custom tag handlers
        r"__import__",  # Python import attempts
        r"eval\s*\(",  # Eval attempts
        r"exec\s*\(",  # Exec attempts
        r"os\.system",  # OS command execution
        r"subprocess",  # Subprocess calls
    ]

    def __init__(self, strict_mode: bool = True):
        """
        Initialize the DSL parser.

        Args:
            strict_mode: If True, reject documents with any validation warnings
        """
        self.strict_mode = strict_mode

    def parse(self, dsl_content: str) -> DSLParseResult:
        """
        Parse DSL string into DiagramDefinition with validation.

        Args:
            dsl_content: YAML DSL string

        Returns:
            DSLParseResult with definition and any warnings

        Raises:
            DSLValidationError: Content fails security validation
            DSLParseError: Content cannot be parsed as valid DSL
        """
        warnings: list[str] = []

        # Security validation first
        self._validate_security(dsl_content)

        # Parse YAML safely
        try:
            data = yaml.safe_load(dsl_content)
        except yaml.YAMLError as e:
            raise DSLParseError(f"Invalid YAML syntax: {e}")

        if data is None:
            raise DSLParseError("Empty DSL content")

        if not isinstance(data, dict):
            raise DSLParseError("DSL must be a YAML mapping (dict)")

        # Validate structure
        self._validate_structure(data)

        # Parse metadata
        metadata = self._parse_metadata(data)

        # Parse nodes
        nodes, node_warnings = self._parse_nodes(data.get("nodes", []))
        warnings.extend(node_warnings)

        # Parse groups
        groups, group_warnings = self._parse_groups(data.get("groups", []))
        warnings.extend(group_warnings)

        # Parse connections
        connections, conn_warnings = self._parse_connections(
            data.get("connections", []), {n.id for n in nodes} | {g.id for g in groups}
        )
        warnings.extend(conn_warnings)

        # Parse constraints
        constraints = self._parse_constraints(data.get("constraints", []))

        # Parse direction
        direction = self._parse_direction(data.get("direction", "TB"))

        # Build definition
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=nodes,
            groups=groups,
            connections=connections,
            constraints=constraints,
            direction=direction,
            width=data.get("width"),
            height=data.get("height"),
        )

        # Validate cross-references
        validation_errors = definition.validate()
        if validation_errors:
            if self.strict_mode:
                raise DSLValidationError(
                    f"Diagram validation failed: {'; '.join(validation_errors)}"
                )
            warnings.extend(validation_errors)

        return DSLParseResult(
            definition=definition,
            warnings=warnings,
            raw_yaml=data,
        )

    def _validate_security(self, dsl_content: str) -> None:
        """Validate DSL content for security issues."""
        # Size limit
        if len(dsl_content) > self.MAX_DSL_SIZE:
            raise DSLValidationError(
                f"DSL content exceeds maximum size ({self.MAX_DSL_SIZE} bytes)"
            )

        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, dsl_content, re.IGNORECASE):
                raise DSLValidationError(
                    f"Potentially dangerous construct detected: {pattern}"
                )

    def _validate_structure(self, data: dict) -> None:
        """Validate basic DSL structure."""
        # Must have at least nodes or groups
        if "nodes" not in data and "groups" not in data:
            raise DSLValidationError("DSL must contain 'nodes' or 'groups'")

        # Validate counts
        nodes = data.get("nodes", [])
        if not isinstance(nodes, list):
            raise DSLValidationError("'nodes' must be a list")
        if len(nodes) > self.MAX_NODES:
            raise DSLValidationError(
                f"Too many nodes ({len(nodes)} > {self.MAX_NODES})"
            )

        groups = data.get("groups", [])
        if not isinstance(groups, list):
            raise DSLValidationError("'groups' must be a list")
        if len(groups) > self.MAX_GROUPS:
            raise DSLValidationError(
                f"Too many groups ({len(groups)} > {self.MAX_GROUPS})"
            )

        connections = data.get("connections", [])
        if not isinstance(connections, list):
            raise DSLValidationError("'connections' must be a list")
        if len(connections) > self.MAX_CONNECTIONS:
            raise DSLValidationError(
                f"Too many connections ({len(connections)} > {self.MAX_CONNECTIONS})"
            )

    def _parse_metadata(self, data: dict) -> DiagramMetadata:
        """Parse diagram metadata."""
        title = data.get("title", "Untitled Diagram")
        if len(title) > self.MAX_LABEL_LENGTH:
            title = title[: self.MAX_LABEL_LENGTH]

        description = data.get("description")
        if description and len(description) > 1000:
            description = description[:1000]

        return DiagramMetadata(
            title=title,
            description=description,
            author=data.get("author"),
            version=str(data.get("version", "1.0")),
            tags=data.get("tags", []),
        )

    def _parse_nodes(self, nodes_data: list) -> tuple[list[DiagramNode], list[str]]:
        """Parse node definitions."""
        nodes: list[DiagramNode] = []
        warnings: list[str] = []
        seen_ids: set[str] = set()

        for i, node_data in enumerate(nodes_data):
            if not isinstance(node_data, dict):
                warnings.append(f"Node {i} is not a dict, skipping")
                continue

            # Get and validate ID
            node_id = node_data.get("id")
            if not node_id:
                warnings.append(f"Node {i} missing 'id', skipping")
                continue

            node_id = str(node_id)
            if len(node_id) > self.MAX_ID_LENGTH:
                node_id = node_id[: self.MAX_ID_LENGTH]

            if node_id in seen_ids:
                warnings.append(f"Duplicate node ID '{node_id}', skipping")
                continue
            seen_ids.add(node_id)

            # Get label
            label = node_data.get("label", node_id)
            if len(label) > self.MAX_LABEL_LENGTH:
                label = label[: self.MAX_LABEL_LENGTH]

            # Parse shape
            shape_str = node_data.get("shape", "rounded")
            try:
                shape = NodeShape(shape_str.lower())
            except ValueError:
                shape = NodeShape.ROUNDED
                warnings.append(f"Unknown shape '{shape_str}' for node '{node_id}'")

            # Parse style
            style = None
            style_data = node_data.get("style")
            if style_data and isinstance(style_data, dict):
                style = NodeStyle(
                    fill_color=style_data.get("fill"),
                    border_color=style_data.get("border"),
                    border_width=float(style_data.get("border_width", 1.0)),
                    text_color=style_data.get("text_color"),
                    font_size=float(style_data.get("font_size", 12.0)),
                    opacity=float(style_data.get("opacity", 1.0)),
                )

            node = DiagramNode(
                id=node_id,
                label=label,
                icon_id=node_data.get("icon"),
                shape=shape,
                metadata=node_data.get("metadata", {}),
                style=style,
            )
            nodes.append(node)

        return nodes, warnings

    def _parse_groups(self, groups_data: list) -> tuple[list[DiagramGroup], list[str]]:
        """Parse group definitions."""
        groups: list[DiagramGroup] = []
        warnings: list[str] = []
        seen_ids: set[str] = set()

        for i, group_data in enumerate(groups_data):
            if not isinstance(group_data, dict):
                warnings.append(f"Group {i} is not a dict, skipping")
                continue

            # Get and validate ID
            group_id = group_data.get("id")
            if not group_id:
                warnings.append(f"Group {i} missing 'id', skipping")
                continue

            group_id = str(group_id)
            if len(group_id) > self.MAX_ID_LENGTH:
                group_id = group_id[: self.MAX_ID_LENGTH]

            if group_id in seen_ids:
                warnings.append(f"Duplicate group ID '{group_id}', skipping")
                continue
            seen_ids.add(group_id)

            # Get label
            label = group_data.get("label", group_id)
            if len(label) > self.MAX_LABEL_LENGTH:
                label = label[: self.MAX_LABEL_LENGTH]

            # Get children
            children = group_data.get("children", [])
            if not isinstance(children, list):
                children = [children]
            children = [str(c) for c in children]

            group = DiagramGroup(
                id=group_id,
                label=label,
                children=children,
                parent_id=group_data.get("parent"),
                color=group_data.get("color"),
                collapsed=bool(group_data.get("collapsed", False)),
                metadata=group_data.get("metadata", {}),
            )
            groups.append(group)

        return groups, warnings

    def _parse_connections(
        self,
        connections_data: list,
        valid_ids: set[str],
    ) -> tuple[list[DiagramConnection], list[str]]:
        """Parse connection definitions."""
        connections: list[DiagramConnection] = []
        warnings: list[str] = []
        seen_ids: set[str] = set()

        for i, conn_data in enumerate(connections_data):
            if not isinstance(conn_data, dict):
                warnings.append(f"Connection {i} is not a dict, skipping")
                continue

            # Get source and target
            source = conn_data.get("source") or conn_data.get("from")
            target = conn_data.get("target") or conn_data.get("to")

            if not source or not target:
                warnings.append(f"Connection {i} missing source or target, skipping")
                continue

            source = str(source)
            target = str(target)

            # Validate references
            if source not in valid_ids:
                warnings.append(f"Connection source '{source}' not found")
            if target not in valid_ids:
                warnings.append(f"Connection target '{target}' not found")

            # Generate ID if not provided
            conn_id = conn_data.get("id", f"{source}->{target}")
            if conn_id in seen_ids:
                conn_id = f"{conn_id}_{i}"
            seen_ids.add(conn_id)

            # Parse style
            style_str = conn_data.get("style", "solid")
            try:
                style = ConnectionStyle(style_str.lower())
            except ValueError:
                style = ConnectionStyle.SOLID
                warnings.append(f"Unknown connection style '{style_str}'")

            # Parse arrow direction
            arrow_str = conn_data.get("arrow", "forward")
            try:
                arrow = ArrowDirection(arrow_str.lower())
            except ValueError:
                arrow = ArrowDirection.FORWARD

            # Parse label
            label = None
            label_data = conn_data.get("label")
            if label_data:
                if isinstance(label_data, str):
                    label = ConnectionLabel(text=label_data)
                elif isinstance(label_data, dict):
                    label = ConnectionLabel(
                        text=label_data.get("text", ""),
                        position=float(label_data.get("position", 0.5)),
                    )

            connection = DiagramConnection(
                id=conn_id,
                source=source,
                target=target,
                label=label,
                style=style,
                arrow=arrow,
                color=conn_data.get("color"),
                metadata=conn_data.get("metadata", {}),
            )
            connections.append(connection)

        return connections, warnings

    def _parse_constraints(self, constraints_data: list) -> list[LayoutConstraint]:
        """Parse layout constraints."""
        constraints: list[LayoutConstraint] = []

        for constraint_data in constraints_data:
            if not isinstance(constraint_data, dict):
                continue

            constraint_type = constraint_data.get("type")
            nodes = constraint_data.get("nodes", [])

            if constraint_type and nodes:
                constraints.append(
                    LayoutConstraint(
                        type=constraint_type,
                        nodes=nodes,
                        value=constraint_data.get("value"),
                    )
                )

        return constraints

    def _parse_direction(self, direction_str: str) -> LayoutDirection:
        """Parse layout direction."""
        direction_map = {
            "TB": LayoutDirection.TOP_BOTTOM,
            "BT": LayoutDirection.BOTTOM_TOP,
            "LR": LayoutDirection.LEFT_RIGHT,
            "RL": LayoutDirection.RIGHT_LEFT,
            "top-bottom": LayoutDirection.TOP_BOTTOM,
            "bottom-top": LayoutDirection.BOTTOM_TOP,
            "left-right": LayoutDirection.LEFT_RIGHT,
            "right-left": LayoutDirection.RIGHT_LEFT,
        }
        return direction_map.get(direction_str.upper(), LayoutDirection.TOP_BOTTOM)

    def to_dsl(self, definition: DiagramDefinition) -> str:
        """
        Convert a DiagramDefinition back to DSL string.

        Args:
            definition: The diagram definition to serialize

        Returns:
            YAML DSL string
        """
        data: dict[str, Any] = {
            "title": definition.metadata.title,
        }

        if definition.metadata.description:
            data["description"] = definition.metadata.description

        if definition.direction != LayoutDirection.TOP_BOTTOM:
            data["direction"] = definition.direction.value

        # Serialize nodes
        if definition.nodes:
            data["nodes"] = []
            for node in definition.nodes:
                node_data: dict[str, Any] = {
                    "id": node.id,
                    "label": node.label,
                }
                if node.icon_id:
                    node_data["icon"] = node.icon_id
                if node.shape != NodeShape.ROUNDED:
                    node_data["shape"] = node.shape.value
                if node.metadata:
                    node_data["metadata"] = node.metadata
                data["nodes"].append(node_data)

        # Serialize groups
        if definition.groups:
            data["groups"] = []
            for group in definition.groups:
                group_data: dict[str, Any] = {
                    "id": group.id,
                    "label": group.label,
                }
                if group.children:
                    group_data["children"] = group.children
                if group.parent_id:
                    group_data["parent"] = group.parent_id
                if group.color:
                    group_data["color"] = group.color
                data["groups"].append(group_data)

        # Serialize connections
        if definition.connections:
            data["connections"] = []
            for conn in definition.connections:
                conn_data: dict[str, Any] = {
                    "source": conn.source,
                    "target": conn.target,
                }
                if conn.label:
                    conn_data["label"] = conn.label.text
                if conn.style != ConnectionStyle.SOLID:
                    conn_data["style"] = conn.style.value
                if conn.arrow != ArrowDirection.FORWARD:
                    conn_data["arrow"] = conn.arrow.value
                if conn.color:
                    conn_data["color"] = conn.color
                data["connections"].append(conn_data)

        return yaml.dump(data, default_flow_style=False, sort_keys=False)


# Convenience functions
def parse_dsl(dsl_content: str, strict: bool = True) -> DiagramDefinition:
    """
    Parse DSL content and return diagram definition.

    Args:
        dsl_content: YAML DSL string
        strict: Whether to use strict validation mode

    Returns:
        DiagramDefinition
    """
    parser = DiagramDSLParser(strict_mode=strict)
    result = parser.parse(dsl_content)
    return result.definition


def definition_to_dsl(definition: DiagramDefinition) -> str:
    """
    Convert diagram definition to DSL string.

    Args:
        definition: DiagramDefinition to serialize

    Returns:
        YAML DSL string
    """
    parser = DiagramDSLParser()
    return parser.to_dsl(definition)
