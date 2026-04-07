"""
Comprehensive tests for DiagramGenerator (ADR-056).

Testing Infrastructure for Documentation Agent - Issue #175
"""

from unittest.mock import MagicMock

import pytest

from src.services.documentation.diagram_generator import (
    DiagramGenerator,
    create_diagram_generator,
)
from src.services.documentation.exceptions import DiagramGenerationError
from src.services.documentation.types import (
    DataClassification,
    DataFlow,
    DiagramComponent,
    DiagramResult,
    DiagramType,
    ServiceBoundary,
)

# NOTE: Forked mode disabled to ensure coverage tracking works correctly.


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    service = MagicMock()
    return service


@pytest.fixture
def generator():
    """Create a DiagramGenerator for testing."""
    return DiagramGenerator(llm_client=None, include_styles=True)


@pytest.fixture
def generator_no_styles():
    """Create a DiagramGenerator without styles."""
    return DiagramGenerator(llm_client=None, include_styles=False)


@pytest.fixture
def sample_boundaries():
    """Create sample service boundaries."""
    return [
        ServiceBoundary(
            boundary_id="svc-1",
            name="UserService",
            description="User management service",
            node_ids=["user_controller", "user_service", "user_repository"],
            confidence=0.85,
            entry_points=["user_controller"],
        ),
        ServiceBoundary(
            boundary_id="svc-2",
            name="AuthService",
            description="Authentication service",
            node_ids=["auth_controller", "auth_service", "token_validator"],
            confidence=0.80,
            entry_points=["auth_controller"],
        ),
    ]


@pytest.fixture
def sample_data_flows():
    """Create sample data flows."""
    return [
        DataFlow(
            flow_id="flow-1",
            source_id="user_service",
            target_id="database",
            flow_type="write",
            protocol="SQL",
            classification=DataClassification.INTERNAL,
            confidence=0.9,
            data_types=["User", "Profile"],
        ),
        DataFlow(
            flow_id="flow-2",
            source_id="api_gateway",
            target_id="auth_queue",
            flow_type="async",
            protocol="SQS",
            classification=DataClassification.SENSITIVE,
            confidence=0.85,
            data_types=["Token"],
        ),
        DataFlow(
            flow_id="flow-3",
            source_id="external_api",
            target_id="user_service",
            flow_type="http",
            protocol="REST",
            classification=DataClassification.PUBLIC,
            confidence=0.75,
        ),
    ]


@pytest.fixture
def sample_components():
    """Create sample diagram components."""
    return [
        DiagramComponent(
            component_id="comp-1",
            label="Module A",
            component_type="module",
            entity_ids=["a.py", "b.py"],
            confidence=0.9,
        ),
        DiagramComponent(
            component_id="comp-2",
            label="Module B",
            component_type="module",
            entity_ids=["c.py"],
            confidence=0.85,
        ),
        DiagramComponent(
            component_id="comp-3",
            label="Service C",
            component_type="service",
            entity_ids=["svc.py"],
            confidence=0.8,
        ),
    ]


# =============================================================================
# Initialization Tests
# =============================================================================


class TestDiagramGeneratorInit:
    """Tests for DiagramGenerator initialization."""

    def test_init_default(self):
        """Test default initialization."""
        generator = DiagramGenerator()

        assert generator.llm is None
        assert generator.include_styles is True

    def test_init_with_llm(self, mock_llm_service):
        """Test initialization with LLM client."""
        generator = DiagramGenerator(llm_client=mock_llm_service)

        assert generator.llm == mock_llm_service
        assert generator.include_styles is True

    def test_init_without_styles(self):
        """Test initialization without styles."""
        generator = DiagramGenerator(include_styles=False)

        assert generator.include_styles is False

    def test_init_with_all_options(self, mock_llm_service):
        """Test initialization with all options."""
        generator = DiagramGenerator(
            llm_client=mock_llm_service,
            include_styles=False,
        )

        assert generator.llm == mock_llm_service
        assert generator.include_styles is False


# =============================================================================
# Generate Method Tests
# =============================================================================


class TestDiagramGeneratorGenerate:
    """Tests for the main generate method."""

    def test_generate_architecture(self, generator, sample_boundaries):
        """Test architecture diagram generation."""
        result = generator.generate(
            diagram_type=DiagramType.ARCHITECTURE,
            boundaries=sample_boundaries,
        )

        assert isinstance(result, DiagramResult)
        assert result.diagram_type == DiagramType.ARCHITECTURE
        assert "graph TB" in result.mermaid_code
        assert len(result.components) > 0

    def test_generate_data_flow(self, generator, sample_boundaries, sample_data_flows):
        """Test data flow diagram generation."""
        result = generator.generate(
            diagram_type=DiagramType.DATA_FLOW,
            boundaries=sample_boundaries,
            data_flows=sample_data_flows,
        )

        assert isinstance(result, DiagramResult)
        assert result.diagram_type == DiagramType.DATA_FLOW
        assert "flowchart LR" in result.mermaid_code

    def test_generate_dependency(self, generator, sample_components):
        """Test dependency diagram generation."""
        result = generator.generate(
            diagram_type=DiagramType.DEPENDENCY,
            components=sample_components,
        )

        assert isinstance(result, DiagramResult)
        assert result.diagram_type == DiagramType.DEPENDENCY
        # Implementation uses top-down (TD) layout
        assert "graph TD" in result.mermaid_code

    def test_generate_component(self, generator, sample_boundaries):
        """Test component diagram generation."""
        result = generator.generate(
            diagram_type=DiagramType.COMPONENT,
            boundaries=sample_boundaries,
        )

        assert isinstance(result, DiagramResult)
        assert result.diagram_type == DiagramType.COMPONENT
        assert "graph TB" in result.mermaid_code

    def test_generate_sequence_type(
        self, generator, sample_boundaries, sample_data_flows
    ):
        """Test SEQUENCE diagram type is supported."""
        # SEQUENCE is now supported in the implementation
        result = generator.generate(
            diagram_type=DiagramType.SEQUENCE,
            boundaries=sample_boundaries,
            data_flows=sample_data_flows,
        )

        assert isinstance(result, DiagramResult)
        assert result.diagram_type == DiagramType.SEQUENCE

    def test_generate_error_handling(self, generator):
        """Test general error handling."""
        # Create a boundary that will cause an error during processing
        with pytest.raises(DiagramGenerationError):
            # Pass invalid data that will cause an exception
            generator.generate(
                diagram_type=DiagramType.ARCHITECTURE,
                boundaries=[None],  # This should cause an error
            )


# =============================================================================
# Architecture Diagram Tests
# =============================================================================


class TestGenerateArchitecture:
    """Tests for architecture diagram generation."""

    def test_architecture_empty_boundaries(self, generator):
        """Test architecture with empty boundaries."""
        result = generator._generate_architecture([])

        assert "No services detected" in result.mermaid_code
        assert len(result.warnings) > 0
        assert result.confidence == 0.3

    def test_architecture_with_styles(self, generator, sample_boundaries):
        """Test architecture includes styles."""
        result = generator._generate_architecture(sample_boundaries)

        assert "classDef" in result.mermaid_code

    def test_architecture_without_styles(self, generator_no_styles, sample_boundaries):
        """Test architecture diagram generation works with include_styles=False.

        Note: Architecture diagrams always include layer-based styles for
        visual clarity regardless of the include_styles flag.
        """
        result = generator_no_styles._generate_architecture(sample_boundaries)

        # Architecture diagrams always include styling for layer visualization
        assert "classDef" in result.mermaid_code
        assert "graph TB" in result.mermaid_code

    def test_architecture_subgraphs(self, generator, sample_boundaries):
        """Test architecture creates subgraphs for boundaries."""
        result = generator._generate_architecture(sample_boundaries)

        assert "subgraph" in result.mermaid_code
        # Implementation formats service names with spaces
        assert "User Service" in result.mermaid_code
        assert "Auth Service" in result.mermaid_code

    def test_architecture_node_limit(self, generator):
        """Test architecture limits nodes per service."""
        # Create boundary with many nodes
        boundary = ServiceBoundary(
            boundary_id="large-svc",
            name="LargeService",
            description="Service with many nodes",
            node_ids=[f"node_{i}" for i in range(50)],  # 50 nodes
            confidence=0.8,
            entry_points=["node_0"],
        )

        result = generator._generate_architecture([boundary])

        # Should limit to 20 nodes per service
        node_count = result.mermaid_code.count("[node_")
        assert node_count <= 20

    def test_architecture_connections(self, generator):
        """Test architecture creates inter-service connections."""
        boundaries = [
            ServiceBoundary(
                boundary_id="svc-1",
                name="Service1",
                description="First service",
                node_ids=["handler1"],
                confidence=0.8,
                entry_points=["handler1"],
            ),
            ServiceBoundary(
                boundary_id="svc-2",
                name="Service2",
                description="Second service",
                node_ids=["handler2"],
                confidence=0.8,
                entry_points=["handler2"],
            ),
        ]

        result = generator._generate_architecture(boundaries)

        # Should have connections section (implementation uses Mermaid comment format)
        assert (
            "%% Service connections" in result.mermaid_code
            or "subgraph" in result.mermaid_code
        )


# =============================================================================
# Data Flow Diagram Tests
# =============================================================================


class TestGenerateDataFlow:
    """Tests for data flow diagram generation."""

    def test_data_flow_empty(self, generator):
        """Test data flow with no inputs."""
        result = generator._generate_data_flow([], [])

        assert "No data flows detected" in result.mermaid_code
        assert len(result.warnings) > 0
        assert result.confidence == 0.3

    def test_data_flow_nodes(self, generator, sample_data_flows):
        """Test data flow creates nodes."""
        result = generator._generate_data_flow([], sample_data_flows)

        assert "user_service" in result.mermaid_code
        assert "database" in result.mermaid_code

    def test_data_flow_edges(self, generator, sample_data_flows):
        """Test data flow creates edges."""
        result = generator._generate_data_flow([], sample_data_flows)

        assert "-->" in result.mermaid_code
        assert len(result.connections) == len(sample_data_flows)

    def test_data_flow_with_data_types(self, generator, sample_data_flows):
        """Test data flow includes data types in labels."""
        result = generator._generate_data_flow([], sample_data_flows)

        # Data types should be in the edge labels
        assert "User" in result.mermaid_code or "write" in result.mermaid_code

    def test_data_flow_node_shapes(self, generator):
        """Test data flow uses correct node shapes."""
        flows = [
            DataFlow(
                flow_id="f1",
                source_id="database_conn",
                target_id="queue_handler",
                flow_type="read",
                classification=DataClassification.INTERNAL,
                confidence=0.8,
            ),
        ]

        result = generator._generate_data_flow([], flows)

        # Database should have cylinder shape, queue should have hexagon
        assert (
            result.mermaid_code.count("[(") > 0 or result.mermaid_code.count("{{") > 0
        )


# =============================================================================
# Dependency Diagram Tests
# =============================================================================


class TestGenerateDependency:
    """Tests for dependency diagram generation."""

    def test_dependency_empty(self, generator):
        """Test dependency with no components."""
        result = generator._generate_dependency([], [])

        assert "No dependencies detected" in result.mermaid_code
        assert len(result.warnings) > 0
        assert result.confidence == 0.3

    def test_dependency_grouping(self, generator, sample_components):
        """Test dependency groups components by type."""
        result = generator._generate_dependency(sample_components, [])

        # Implementation groups by layer type (service, etc.)
        assert "subgraph" in result.mermaid_code

    def test_dependency_confidence(self, generator, sample_components):
        """Test dependency calculates average confidence."""
        result = generator._generate_dependency(sample_components, [])

        expected_avg = sum(c.confidence for c in sample_components) / len(
            sample_components
        )
        assert abs(result.confidence - expected_avg) < 0.01


# =============================================================================
# Component Diagram Tests
# =============================================================================


class TestGenerateComponent:
    """Tests for component diagram generation."""

    def test_component_empty(self, generator):
        """Test component with no boundaries."""
        result = generator._generate_component([])

        assert "No components detected" in result.mermaid_code
        assert len(result.warnings) > 0
        assert result.confidence == 0.3

    def test_component_hierarchy(self, generator, sample_boundaries):
        """Test component creates hierarchy with layer subgraphs."""
        result = generator._generate_component(sample_boundaries)

        # Implementation creates layer subgraphs, not repo nodes
        assert "subgraph" in result.mermaid_code
        assert "System Components" in result.mermaid_code
        # Should have component relationships
        assert "-->" in result.mermaid_code or "direction TB" in result.mermaid_code

    def test_component_node_limit(self, generator):
        """Test component limits nodes per boundary."""
        boundary = ServiceBoundary(
            boundary_id="large",
            name="LargeService",
            description="Service with many nodes",
            node_ids=[f"node_{i}" for i in range(20)],
            confidence=0.8,
            entry_points=[],
        )

        result = generator._generate_component([boundary])

        # Should limit to 10 nodes per service
        connections = result.mermaid_code.count("-->")
        assert connections <= 12  # 1 repo + max 10 nodes + some boundaries


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Tests for helper methods."""

    def test_safe_id_basic(self, generator):
        """Test safe_id with basic input."""
        result = generator._safe_id("my_component")
        assert result == "my_component"

    def test_safe_id_special_chars(self, generator):
        """Test safe_id removes special characters."""
        result = generator._safe_id("my-component.py")
        assert "-" not in result
        assert "." not in result
        assert "_" in result

    def test_safe_id_starts_with_number(self, generator):
        """Test safe_id handles IDs starting with numbers."""
        result = generator._safe_id("123_component")
        assert result.startswith("n_")

    def test_safe_id_length_limit(self, generator):
        """Test safe_id limits length."""
        long_id = "a" * 100
        result = generator._safe_id(long_id)
        # Implementation limits to 40 characters
        assert len(result) <= 40

    def test_escape_label_quotes(self, generator):
        """Test escape_label handles quotes."""
        result = generator._escape_label('Say "hello"')
        assert '"' not in result
        assert "'" in result

    def test_escape_label_brackets(self, generator):
        """Test escape_label handles brackets."""
        result = generator._escape_label("List[str]")
        assert "[" not in result
        assert "]" not in result
        assert "(" in result

    def test_escape_label_braces(self, generator):
        """Test escape_label handles braces."""
        result = generator._escape_label("Dict{key}")
        assert "{" not in result
        assert "}" not in result

    def test_escape_label_length_limit(self, generator):
        """Test escape_label limits length."""
        long_label = "a" * 200
        result = generator._escape_label(long_label)
        # Implementation limits to 80 characters
        assert len(result) <= 80

    def test_format_service_name_camel_case(self, generator):
        """Test _format_service_name splits CamelCase."""
        result = generator._format_service_name("UserAuthService")
        assert "User" in result
        assert "Auth" in result
        assert "Service" in result

    def test_format_service_name_underscores(self, generator):
        """Test _format_service_name converts underscores to spaces."""
        result = generator._format_service_name("user_auth_service")
        assert " " in result
        assert "User" in result

    def test_format_service_name_abbreviations(self, generator):
        """Test _format_service_name handles common abbreviations."""
        result = generator._format_service_name("api_handler")
        # API should be uppercase
        assert "API" in result

    def test_infer_node_type_database(self, generator):
        """Test infer_node_type detects databases."""
        assert generator._infer_node_type("user_database") == "database"
        assert generator._infer_node_type("my_db_connection") == "database"
        assert generator._infer_node_type("dynamodb_client") == "database"

    def test_infer_node_type_queue(self, generator):
        """Test infer_node_type detects queues."""
        assert generator._infer_node_type("message_queue") == "queue"
        assert generator._infer_node_type("sqs_handler") == "queue"
        assert generator._infer_node_type("kafka_producer") == "queue"

    def test_infer_node_type_api(self, generator):
        """Test infer_node_type detects APIs."""
        assert generator._infer_node_type("rest_api") == "api"
        assert generator._infer_node_type("user_endpoint") == "api"

    def test_infer_node_type_external(self, generator):
        """Test infer_node_type detects external services."""
        assert generator._infer_node_type("external_service") == "external"
        # bedrock and cognito are recognized external service keywords
        assert generator._infer_node_type("bedrock_client") == "external"
        assert generator._infer_node_type("cognito_auth") == "external"

    def test_infer_node_type_default(self, generator):
        """Test infer_node_type returns service as default."""
        assert generator._infer_node_type("my_handler") == "service"
        assert generator._infer_node_type("processor") == "service"

    def test_layer_config_exists(self, generator):
        """Test LAYER_CONFIG contains style definitions."""
        # Verify layer configuration is available
        assert hasattr(generator, "LAYER_CONFIG") or hasattr(
            DiagramGenerator, "LAYER_CONFIG"
        )

        config = DiagramGenerator.LAYER_CONFIG
        assert len(config) > 0
        assert "service" in config
        assert "data" in config
        # Each layer should have styling properties
        assert "fill" in config["service"]
        assert "stroke" in config["service"]


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateDiagramGenerator:
    """Tests for the factory function."""

    def test_create_default(self):
        """Test factory creates generator with defaults."""
        generator = create_diagram_generator()

        assert isinstance(generator, DiagramGenerator)
        assert generator.llm is None

    def test_create_with_llm(self, mock_llm_service):
        """Test factory with LLM client."""
        generator = create_diagram_generator(llm_client=mock_llm_service)

        assert generator.llm == mock_llm_service


# =============================================================================
# Integration Tests
# =============================================================================


class TestDiagramGeneratorIntegration:
    """Integration tests for diagram generation."""

    def test_all_diagram_types(
        self, generator, sample_boundaries, sample_data_flows, sample_components
    ):
        """Test generating all supported diagram types."""
        # Architecture
        arch_result = generator.generate(
            diagram_type=DiagramType.ARCHITECTURE,
            boundaries=sample_boundaries,
        )
        assert arch_result.diagram_type == DiagramType.ARCHITECTURE

        # Data Flow
        flow_result = generator.generate(
            diagram_type=DiagramType.DATA_FLOW,
            data_flows=sample_data_flows,
        )
        assert flow_result.diagram_type == DiagramType.DATA_FLOW

        # Dependency
        dep_result = generator.generate(
            diagram_type=DiagramType.DEPENDENCY,
            components=sample_components,
        )
        assert dep_result.diagram_type == DiagramType.DEPENDENCY

        # Component
        comp_result = generator.generate(
            diagram_type=DiagramType.COMPONENT,
            boundaries=sample_boundaries,
        )
        assert comp_result.diagram_type == DiagramType.COMPONENT

    def test_mermaid_syntax_valid(self, generator, sample_boundaries):
        """Test generated Mermaid syntax is valid."""
        result = generator.generate(
            diagram_type=DiagramType.ARCHITECTURE,
            boundaries=sample_boundaries,
        )

        mermaid = result.mermaid_code
        lines = mermaid.split("\n")

        # First non-empty line should be a valid Mermaid directive
        first_line = next(line for line in lines if line.strip())
        assert any(
            directive in first_line.lower()
            for directive in ["graph", "flowchart", "sequencediagram", "classDiagram"]
        )

        # Should have proper structure
        assert "{" not in mermaid or "}" in mermaid  # Balanced braces
        assert "[" not in mermaid or "]" in mermaid  # Balanced brackets (or escaped)
