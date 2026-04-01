# Copyright (c) 2025 Aenea Labs. All rights reserved.
"""Unit tests for diagram service data models."""

from datetime import datetime

import pytest

from src.services.diagrams.models import (
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
    Position,
    Size,
)


class TestPosition:
    """Tests for Position model."""

    def test_position_creation(self):
        """Test basic position creation."""
        pos = Position(x=100.0, y=200.0)
        assert pos.x == 100.0
        assert pos.y == 200.0

    def test_position_negative_values(self):
        """Test position accepts negative values."""
        pos = Position(x=-50.0, y=-100.0)
        assert pos.x == -50.0
        assert pos.y == -100.0


class TestSize:
    """Tests for Size model."""

    def test_size_creation(self):
        """Test basic size creation."""
        size = Size(width=150.0, height=100.0)
        assert size.width == 150.0
        assert size.height == 100.0


class TestDiagramNode:
    """Tests for DiagramNode model."""

    def test_node_minimal_creation(self):
        """Test node with minimal required fields."""
        node = DiagramNode(id="node-1", label="Test Node")
        assert node.id == "node-1"
        assert node.label == "Test Node"
        assert node.shape == NodeShape.ROUNDED
        assert node.icon_id is None

    def test_node_uses_id_as_label_if_empty(self):
        """Test node uses ID as label if label is empty."""
        node = DiagramNode(id="my-node", label="")
        assert node.label == "my-node"

    def test_node_with_icon(self):
        """Test node with icon reference."""
        node = DiagramNode(
            id="ec2-instance",
            label="Web Server",
            icon_id="aws:ec2",
            shape=NodeShape.ICON,
        )
        assert node.icon_id == "aws:ec2"
        assert node.shape == NodeShape.ICON

    def test_node_with_position_and_size(self):
        """Test node with explicit position and size."""
        node = DiagramNode(
            id="node-1",
            label="Positioned Node",
            position=Position(x=100.0, y=200.0),
            size=Size(width=200.0, height=150.0),
        )
        assert node.position.x == 100.0
        assert node.position.y == 200.0
        assert node.size.width == 200.0
        assert node.size.height == 150.0

    def test_node_shapes(self):
        """Test all node shapes are valid."""
        shapes = [
            NodeShape.RECTANGLE,
            NodeShape.ROUNDED,
            NodeShape.DIAMOND,
            NodeShape.CIRCLE,
            NodeShape.CYLINDER,
            NodeShape.CLOUD,
            NodeShape.HEXAGON,
            NodeShape.ICON,
        ]
        for shape in shapes:
            node = DiagramNode(id=f"node-{shape.value}", label="Test", shape=shape)
            assert node.shape == shape

    def test_node_with_metadata(self):
        """Test node with custom metadata."""
        node = DiagramNode(
            id="node-1",
            label="Node with metadata",
            metadata={"instance_type": "t3.large", "region": "us-east-1"},
        )
        assert node.metadata["instance_type"] == "t3.large"
        assert node.metadata["region"] == "us-east-1"

    def test_node_id_validation(self):
        """Test node ID cannot be empty."""
        with pytest.raises(ValueError, match="id cannot be empty"):
            DiagramNode(id="", label="Test")

    def test_node_with_style(self):
        """Test node with custom style."""
        style = NodeStyle(
            fill_color="#FF0000",
            border_color="#000000",
            text_color="#FFFFFF",
        )
        node = DiagramNode(id="styled", label="Styled Node", style=style)
        assert node.style.fill_color == "#FF0000"


class TestDiagramGroup:
    """Tests for DiagramGroup model."""

    def test_group_minimal_creation(self):
        """Test group with minimal fields."""
        group = DiagramGroup(id="group-1", label="VPC")
        assert group.id == "group-1"
        assert group.label == "VPC"
        assert group.children == []
        assert group.parent_id is None

    def test_group_with_children(self):
        """Test group containing child nodes."""
        group = DiagramGroup(
            id="vpc-1",
            label="Production VPC",
            children=["subnet-1", "subnet-2", "nat-gateway"],
        )
        assert len(group.children) == 3
        assert "subnet-1" in group.children

    def test_nested_groups(self):
        """Test group with parent reference."""
        child_group = DiagramGroup(
            id="subnet-1",
            label="Private Subnet",
            parent_id="vpc-1",
            children=["ec2-1", "ec2-2"],
        )
        assert child_group.parent_id == "vpc-1"

    def test_group_with_color(self):
        """Test group with custom color."""
        group = DiagramGroup(
            id="group-1",
            label="Colored Group",
            color="#3B82F6",
        )
        assert group.color == "#3B82F6"

    def test_group_collapsed(self):
        """Test group collapsed state."""
        group = DiagramGroup(
            id="group-1",
            label="Collapsed Group",
            collapsed=True,
        )
        assert group.collapsed is True


class TestDiagramConnection:
    """Tests for DiagramConnection model."""

    def test_connection_minimal_creation(self):
        """Test connection with minimal fields."""
        conn = DiagramConnection(id="conn-1", source="node-1", target="node-2")
        assert conn.source == "node-1"
        assert conn.target == "node-2"
        assert conn.style == ConnectionStyle.SOLID
        assert conn.arrow == ArrowDirection.FORWARD

    def test_connection_auto_generates_id(self):
        """Test connection auto-generates ID from source/target."""
        conn = DiagramConnection(id="", source="a", target="b")
        assert conn.id == "a->b"

    def test_connection_styles(self):
        """Test all connection styles."""
        for style in ConnectionStyle:
            conn = DiagramConnection(id="conn", source="a", target="b", style=style)
            assert conn.style == style

    def test_connection_arrow_directions(self):
        """Test all arrow directions."""
        for direction in ArrowDirection:
            conn = DiagramConnection(id="conn", source="a", target="b", arrow=direction)
            assert conn.arrow == direction

    def test_connection_with_label(self):
        """Test connection with label."""
        conn = DiagramConnection(
            id="conn",
            source="api",
            target="database",
            label=ConnectionLabel(text="SQL queries"),
        )
        assert conn.label.text == "SQL queries"

    def test_connection_with_color(self):
        """Test connection with custom color."""
        conn = DiagramConnection(
            id="conn",
            source="a",
            target="b",
            color="#DC2626",  # Error red
        )
        assert conn.color == "#DC2626"


class TestLayoutConstraint:
    """Tests for LayoutConstraint model."""

    def test_alignment_constraint(self):
        """Test horizontal alignment constraint."""
        constraint = LayoutConstraint(
            type="align",
            nodes=["node-1", "node-2", "node-3"],
        )
        assert constraint.type == "align"
        assert len(constraint.nodes) == 3

    def test_layer_constraint(self):
        """Test same layer constraint."""
        constraint = LayoutConstraint(
            type="layer",
            nodes=["db-1", "db-2", "db-3"],
            value=2,
        )
        assert constraint.type == "layer"
        assert constraint.value == 2


class TestDiagramMetadata:
    """Tests for DiagramMetadata model."""

    def test_metadata_creation(self):
        """Test metadata creation."""
        metadata = DiagramMetadata(
            title="Architecture Diagram",
            description="Production infrastructure",
            author="Platform Team",
            version="1.0.0",
        )
        assert metadata.title == "Architecture Diagram"
        assert metadata.version == "1.0.0"

    def test_metadata_tags(self):
        """Test metadata with tags."""
        metadata = DiagramMetadata(
            title="Test Diagram",
            tags=["infrastructure", "aws", "production"],
        )
        assert "aws" in metadata.tags

    def test_metadata_has_timestamps(self):
        """Test metadata has created_at and updated_at."""
        metadata = DiagramMetadata(title="Test")
        assert isinstance(metadata.created_at, datetime)
        assert isinstance(metadata.updated_at, datetime)


class TestDiagramDefinition:
    """Tests for DiagramDefinition model."""

    def test_minimal_definition(self):
        """Test minimal diagram definition."""
        metadata = DiagramMetadata(title="Empty Diagram")
        diagram = DiagramDefinition(metadata=metadata)
        assert diagram.nodes == []
        assert diagram.groups == []
        assert diagram.connections == []
        assert diagram.direction == LayoutDirection.TOP_BOTTOM

    def test_definition_with_nodes(self):
        """Test definition with nodes."""
        metadata = DiagramMetadata(title="Test")
        nodes = [
            DiagramNode(id="web", label="Web Server"),
            DiagramNode(id="api", label="API Server"),
            DiagramNode(id="db", label="Database"),
        ]
        diagram = DiagramDefinition(metadata=metadata, nodes=nodes)
        assert len(diagram.nodes) == 3

    def test_definition_with_connections(self):
        """Test definition with connections."""
        metadata = DiagramMetadata(title="Test")
        nodes = [
            DiagramNode(id="a", label="A"),
            DiagramNode(id="b", label="B"),
        ]
        connections = [
            DiagramConnection(id="a-b", source="a", target="b"),
        ]
        diagram = DiagramDefinition(
            metadata=metadata, nodes=nodes, connections=connections
        )
        assert len(diagram.connections) == 1
        assert diagram.connections[0].source == "a"

    def test_definition_with_groups(self):
        """Test definition with groups."""
        metadata = DiagramMetadata(title="Test")
        groups = [
            DiagramGroup(id="vpc", label="VPC", children=["subnet-1"]),
            DiagramGroup(id="subnet-1", label="Subnet", parent_id="vpc"),
        ]
        diagram = DiagramDefinition(metadata=metadata, groups=groups)
        assert len(diagram.groups) == 2

    def test_definition_layout_direction(self):
        """Test different layout directions."""
        metadata = DiagramMetadata(title="Test")
        for direction in LayoutDirection:
            diagram = DiagramDefinition(metadata=metadata, direction=direction)
            assert diagram.direction == direction

    def test_get_node(self):
        """Test get_node method."""
        metadata = DiagramMetadata(title="Test")
        nodes = [
            DiagramNode(id="web", label="Web Server"),
            DiagramNode(id="api", label="API Server"),
        ]
        diagram = DiagramDefinition(metadata=metadata, nodes=nodes)

        node = diagram.get_node("web")
        assert node is not None
        assert node.label == "Web Server"

        missing = diagram.get_node("nonexistent")
        assert missing is None

    def test_get_group(self):
        """Test get_group method."""
        metadata = DiagramMetadata(title="Test")
        groups = [DiagramGroup(id="vpc", label="VPC")]
        diagram = DiagramDefinition(metadata=metadata, groups=groups)

        group = diagram.get_group("vpc")
        assert group is not None
        assert group.label == "VPC"

    def test_get_nodes_in_group(self):
        """Test get_nodes_in_group method."""
        metadata = DiagramMetadata(title="Test")
        nodes = [
            DiagramNode(id="ec2-1", label="EC2 1"),
            DiagramNode(id="ec2-2", label="EC2 2"),
            DiagramNode(id="rds", label="RDS"),
        ]
        groups = [
            DiagramGroup(id="compute", label="Compute", children=["ec2-1", "ec2-2"]),
        ]
        diagram = DiagramDefinition(metadata=metadata, nodes=nodes, groups=groups)

        compute_nodes = diagram.get_nodes_in_group("compute")
        assert len(compute_nodes) == 2
        assert all(n.id.startswith("ec2") for n in compute_nodes)

    def test_validate_detects_duplicate_node_ids(self):
        """Test validation catches duplicate node IDs."""
        metadata = DiagramMetadata(title="Test")
        nodes = [
            DiagramNode(id="same", label="First"),
            DiagramNode(id="same", label="Second"),
        ]
        diagram = DiagramDefinition(metadata=metadata, nodes=nodes)

        errors = diagram.validate()
        assert any("Duplicate node IDs" in e for e in errors)

    def test_validate_detects_invalid_connection_reference(self):
        """Test validation catches invalid connection references."""
        metadata = DiagramMetadata(title="Test")
        nodes = [DiagramNode(id="a", label="A")]
        connections = [
            DiagramConnection(id="conn", source="a", target="nonexistent"),
        ]
        diagram = DiagramDefinition(
            metadata=metadata, nodes=nodes, connections=connections
        )

        errors = diagram.validate()
        assert any("not found" in e for e in errors)

    def test_complete_diagram_definition(self):
        """Test a complete realistic diagram definition."""
        diagram = DiagramDefinition(
            metadata=DiagramMetadata(
                title="Three-Tier Architecture",
                description="Web, API, and Database layers",
                tags=["architecture", "aws"],
            ),
            direction=LayoutDirection.TOP_BOTTOM,
            nodes=[
                DiagramNode(id="web", label="Web Server", icon_id="aws:ec2"),
                DiagramNode(id="api", label="API Server", icon_id="aws:lambda"),
                DiagramNode(id="db", label="Database", icon_id="aws:rds"),
            ],
            groups=[
                DiagramGroup(id="vpc", label="VPC", children=["web", "api", "db"]),
            ],
            connections=[
                DiagramConnection(
                    id="web-api",
                    source="web",
                    target="api",
                    label=ConnectionLabel(text="HTTP"),
                ),
                DiagramConnection(
                    id="api-db",
                    source="api",
                    target="db",
                    label=ConnectionLabel(text="SQL"),
                ),
            ],
        )

        assert diagram.metadata.title == "Three-Tier Architecture"
        assert len(diagram.nodes) == 3
        assert len(diagram.groups) == 1
        assert len(diagram.connections) == 2

        # Should validate without errors
        errors = diagram.validate()
        assert len(errors) == 0
