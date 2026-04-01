# Copyright (c) 2025 Aenea Labs. All rights reserved.
"""Unit tests for the diagram DSL parser."""

import pytest

from src.services.diagrams.diagram_dsl import (
    DiagramDSLParser,
    DSLParseError,
    DSLParseResult,
    DSLValidationError,
)
from src.services.diagrams.models import (
    ArrowDirection,
    ConnectionStyle,
    LayoutDirection,
    NodeShape,
)


class TestDSLParserBasic:
    """Basic parsing tests for DiagramDSLParser."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return DiagramDSLParser(strict_mode=False)

    def test_parser_initialization(self, parser):
        """Test parser initializes correctly."""
        assert parser is not None

    def test_parse_minimal_diagram(self, parser):
        """Test parsing minimal diagram with nodes."""
        dsl = """
        title: Minimal Diagram
        nodes:
          - id: node-1
            label: Test Node
        """
        result = parser.parse(dsl)
        assert isinstance(result, DSLParseResult)
        assert result.definition is not None
        assert len(result.definition.nodes) == 1

    def test_parse_minimal_node(self, parser):
        """Test parsing a minimal node."""
        dsl = """
        title: Single Node
        nodes:
          - id: node-1
            label: Test Node
        """
        result = parser.parse(dsl)
        assert len(result.definition.nodes) == 1
        assert result.definition.nodes[0].id == "node-1"
        assert result.definition.nodes[0].label == "Test Node"

    def test_parse_node_with_icon(self, parser):
        """Test parsing node with icon reference."""
        dsl = """
        title: Node with Icon
        nodes:
          - id: web-server
            label: Web Server
            icon: aws:ec2
            shape: icon
        """
        result = parser.parse(dsl)
        node = result.definition.nodes[0]
        assert node.icon_id == "aws:ec2"
        assert node.shape == NodeShape.ICON

    def test_parse_node_shapes(self, parser):
        """Test parsing different node shapes."""
        shapes = [
            "rectangle",
            "rounded",
            "diamond",
            "circle",
            "cylinder",
            "cloud",
            "hexagon",
        ]
        for shape in shapes:
            dsl = f"""
            title: Shape Test
            nodes:
              - id: node-1
                label: Test
                shape: {shape}
            """
            result = parser.parse(dsl)
            assert result.definition is not None


class TestDSLParserConnections:
    """Tests for parsing connections."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return DiagramDSLParser(strict_mode=False)

    def test_parse_simple_connection(self, parser):
        """Test parsing a simple connection."""
        dsl = """
        title: Connected Nodes
        nodes:
          - id: a
            label: Node A
          - id: b
            label: Node B
        connections:
          - source: a
            target: b
        """
        result = parser.parse(dsl)
        assert len(result.definition.connections) == 1
        conn = result.definition.connections[0]
        assert conn.source == "a"
        assert conn.target == "b"

    def test_parse_connection_with_from_to_syntax(self, parser):
        """Test parsing connection with from/to syntax."""
        dsl = """
        title: Connected Nodes
        nodes:
          - id: a
            label: A
          - id: b
            label: B
        connections:
          - from: a
            to: b
        """
        result = parser.parse(dsl)
        conn = result.definition.connections[0]
        assert conn.source == "a"
        assert conn.target == "b"

    def test_parse_connection_with_label(self, parser):
        """Test parsing connection with label."""
        dsl = """
        title: Labeled Connection
        nodes:
          - id: api
            label: API
          - id: db
            label: Database
        connections:
          - from: api
            to: db
            label: SQL Queries
        """
        result = parser.parse(dsl)
        conn = result.definition.connections[0]
        assert conn.label is not None
        assert conn.label.text == "SQL Queries"

    def test_parse_connection_styles(self, parser):
        """Test parsing different connection styles."""
        dsl = """
        title: Connection Styles
        nodes:
          - id: a
            label: A
          - id: b
            label: B
          - id: c
            label: C
        connections:
          - from: a
            to: b
            style: solid
          - from: b
            to: c
            style: dashed
        """
        result = parser.parse(dsl)
        assert result.definition.connections[0].style == ConnectionStyle.SOLID
        assert result.definition.connections[1].style == ConnectionStyle.DASHED

    def test_parse_arrow_directions(self, parser):
        """Test parsing arrow directions."""
        dsl = """
        title: Arrow Directions
        nodes:
          - id: a
            label: A
          - id: b
            label: B
        connections:
          - from: a
            to: b
            arrow: forward
        """
        result = parser.parse(dsl)
        assert result.definition.connections[0].arrow == ArrowDirection.FORWARD

    def test_parse_bidirectional_connection(self, parser):
        """Test parsing bidirectional arrow."""
        dsl = """
        title: Bidirectional
        nodes:
          - id: service-a
            label: Service A
          - id: service-b
            label: Service B
        connections:
          - from: service-a
            to: service-b
            arrow: both
            label: gRPC
        """
        result = parser.parse(dsl)
        assert result.definition.connections[0].arrow == ArrowDirection.BOTH


class TestDSLParserGroups:
    """Tests for parsing groups/containers."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return DiagramDSLParser(strict_mode=False)

    def test_parse_simple_group(self, parser):
        """Test parsing a simple group."""
        dsl = """
        title: Grouped Diagram
        groups:
          - id: vpc
            label: VPC
            children:
              - subnet-1
              - subnet-2
        nodes:
          - id: subnet-1
            label: Subnet 1
          - id: subnet-2
            label: Subnet 2
        """
        result = parser.parse(dsl)
        assert len(result.definition.groups) == 1
        group = result.definition.groups[0]
        assert group.id == "vpc"
        assert "subnet-1" in group.children

    def test_parse_nested_groups(self, parser):
        """Test parsing nested groups."""
        dsl = """
        title: Nested Groups
        groups:
          - id: vpc
            label: VPC
            children:
              - public-subnet
              - private-subnet
          - id: public-subnet
            label: Public Subnet
            parent: vpc
            children:
              - web-server
          - id: private-subnet
            label: Private Subnet
            parent: vpc
            children:
              - app-server
        nodes:
          - id: web-server
            label: Web Server
          - id: app-server
            label: App Server
        """
        result = parser.parse(dsl)
        assert len(result.definition.groups) == 3

        public = next(g for g in result.definition.groups if g.id == "public-subnet")
        private = next(g for g in result.definition.groups if g.id == "private-subnet")

        assert public.parent_id == "vpc"
        assert private.parent_id == "vpc"

    def test_parse_group_with_color(self, parser):
        """Test parsing group with custom color."""
        dsl = """
        title: Colored Group
        groups:
          - id: security-zone
            label: Security Zone
            color: "#DC2626"
            children:
              - firewall
        nodes:
          - id: firewall
            label: Firewall
        """
        result = parser.parse(dsl)
        group = result.definition.groups[0]
        assert group.color == "#DC2626"


class TestDSLParserLayout:
    """Tests for layout configuration parsing."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return DiagramDSLParser(strict_mode=False)

    def test_parse_layout_direction_tb(self, parser):
        """Test parsing top-bottom direction."""
        dsl = """
        title: Direction Test
        direction: TB
        nodes:
          - id: a
            label: A
        """
        result = parser.parse(dsl)
        assert result.definition.direction == LayoutDirection.TOP_BOTTOM

    def test_parse_layout_direction_lr(self, parser):
        """Test parsing left-right direction."""
        dsl = """
        title: Direction Test
        direction: LR
        nodes:
          - id: a
            label: A
        """
        result = parser.parse(dsl)
        assert result.definition.direction == LayoutDirection.LEFT_RIGHT


class TestDSLParserSecurity:
    """Security validation tests for DSL parser."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return DiagramDSLParser()

    def test_reject_python_yaml_injection(self, parser):
        """Test rejection of Python YAML injection."""
        dsl = """
        title: !!python/object:os.system 'rm -rf /'
        nodes:
          - id: a
            label: A
        """
        with pytest.raises(DSLValidationError):
            parser.parse(dsl)

    def test_reject_eval_in_dsl(self, parser):
        """Test rejection of eval() in DSL."""
        dsl = """
        title: eval(malicious_code)
        nodes:
          - id: a
            label: A
        """
        with pytest.raises(DSLValidationError):
            parser.parse(dsl)

    def test_reject_exec_in_dsl(self, parser):
        """Test rejection of exec() in DSL."""
        dsl = """
        title: exec(dangerous)
        nodes:
          - id: a
            label: A
        """
        with pytest.raises(DSLValidationError):
            parser.parse(dsl)

    def test_reject_import_in_dsl(self, parser):
        """Test rejection of __import__ in DSL."""
        dsl = """
        title: __import__('os')
        nodes:
          - id: a
            label: A
        """
        with pytest.raises(DSLValidationError):
            parser.parse(dsl)

    def test_reject_oversized_dsl(self, parser):
        """Test rejection of oversized DSL content."""
        large_content = "x" * (parser.MAX_DSL_SIZE + 1)
        dsl = f"""
        title: {large_content}
        nodes:
          - id: a
            label: A
        """
        with pytest.raises(DSLValidationError):
            parser.parse(dsl)

    def test_reject_too_many_nodes(self, parser):
        """Test rejection of too many nodes."""
        nodes = "\n".join(
            [
                f"  - id: node-{i}\n    label: Node {i}"
                for i in range(parser.MAX_NODES + 1)
            ]
        )
        dsl = f"""title: Too Many Nodes
nodes:
{nodes}
"""
        with pytest.raises(DSLValidationError):
            parser.parse(dsl)


class TestDSLParserErrorHandling:
    """Error handling tests for DSL parser."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return DiagramDSLParser(strict_mode=False)

    def test_invalid_yaml_syntax(self, parser):
        """Test handling of invalid YAML syntax."""
        dsl = """
        title: Bad YAML
        nodes:
          - id: [invalid
        """
        with pytest.raises(DSLParseError):
            parser.parse(dsl)

    def test_empty_dsl_content(self, parser):
        """Test handling of empty DSL content."""
        with pytest.raises(DSLParseError):
            parser.parse("")

    def test_missing_nodes_and_groups(self, parser):
        """Test DSL must have nodes or groups."""
        dsl = """
        title: No nodes
        """
        with pytest.raises(DSLValidationError):
            parser.parse(dsl)

    def test_warnings_for_missing_node_id(self, parser):
        """Test warnings for nodes missing ID."""
        dsl = """
        title: Missing ID
        nodes:
          - label: Node without ID
        """
        result = parser.parse(dsl)
        # Should have warning about missing ID
        assert len(result.warnings) > 0


class TestDSLSerialization:
    """Tests for serializing DiagramDefinition back to DSL."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return DiagramDSLParser(strict_mode=False)

    def test_to_dsl_basic(self, parser):
        """Test serializing diagram to DSL."""
        dsl = """
        title: Test
        nodes:
          - id: node-1
            label: Test Node
        """
        result = parser.parse(dsl)
        output_dsl = parser.to_dsl(result.definition)
        assert "node-1" in output_dsl
        assert "Test Node" in output_dsl

    def test_to_dsl_with_connections(self, parser):
        """Test serializing diagram with connections."""
        dsl = """
        title: Connected
        nodes:
          - id: a
            label: A
          - id: b
            label: B
        connections:
          - source: a
            target: b
            label: HTTP
        """
        result = parser.parse(dsl)
        output_dsl = parser.to_dsl(result.definition)
        assert "source:" in output_dsl
        assert "target:" in output_dsl

    def test_roundtrip(self, parser):
        """Test parsing and re-serializing produces equivalent diagram."""
        original_dsl = """
        title: Roundtrip Test
        nodes:
          - id: web
            label: Web Server
          - id: db
            label: Database
        connections:
          - source: web
            target: db
        """
        result1 = parser.parse(original_dsl)
        new_dsl = parser.to_dsl(result1.definition)
        result2 = parser.parse(new_dsl)

        assert len(result2.definition.nodes) == len(result1.definition.nodes)
        assert len(result2.definition.connections) == len(
            result1.definition.connections
        )


class TestComplexDiagrams:
    """Tests for complex, realistic diagram scenarios."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return DiagramDSLParser(strict_mode=False)

    def test_three_tier_architecture(self, parser):
        """Test parsing a complete three-tier architecture diagram."""
        dsl = """
        title: Three-Tier Architecture
        direction: TB
        groups:
          - id: vpc
            label: Production VPC
            children:
              - public-subnet
              - private-subnet
          - id: public-subnet
            label: Public Subnet
            parent: vpc
            children:
              - alb
          - id: private-subnet
            label: Private Subnet
            parent: vpc
            children:
              - web-tier
              - app-tier
              - data-tier
        nodes:
          - id: users
            label: Users
            icon: generic:user
          - id: alb
            label: Application Load Balancer
            icon: aws:alb
          - id: web-tier
            label: Web Servers
            icon: aws:ec2
          - id: app-tier
            label: Application Servers
            icon: aws:ecs
          - id: data-tier
            label: Database
            icon: aws:rds
          - id: cache
            label: Cache
            icon: aws:elasticache
        connections:
          - from: users
            to: alb
            label: HTTPS
          - from: alb
            to: web-tier
            label: HTTP
          - from: web-tier
            to: app-tier
            label: gRPC
          - from: app-tier
            to: data-tier
            label: SQL
          - from: app-tier
            to: cache
            label: Redis
            style: dashed
        """
        result = parser.parse(dsl)
        assert len(result.definition.nodes) == 6
        assert len(result.definition.groups) == 3
        assert len(result.definition.connections) == 5

    def test_microservices_diagram(self, parser):
        """Test parsing a microservices architecture diagram."""
        dsl = """
        title: Microservices Architecture
        direction: LR
        nodes:
          - id: api-gateway
            label: API Gateway
            icon: aws:api-gateway
          - id: auth-service
            label: Auth Service
            icon: aws:lambda
          - id: user-service
            label: User Service
            icon: aws:ecs
          - id: order-service
            label: Order Service
            icon: aws:ecs
          - id: user-db
            label: User DB
            icon: aws:dynamodb
          - id: order-db
            label: Order DB
            icon: aws:rds
        connections:
          - from: api-gateway
            to: auth-service
            arrow: both
          - from: api-gateway
            to: user-service
          - from: api-gateway
            to: order-service
          - from: user-service
            to: user-db
          - from: order-service
            to: order-db
        """
        result = parser.parse(dsl)
        assert len(result.definition.nodes) == 6
        assert len(result.definition.connections) == 5
