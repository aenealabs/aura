"""
Phase 2: Diagram Generation Tests

Tests for the diagram generation system:
- DiagramGenerator class
- Mermaid, PlantUML, and draw.io output formats
- Template-based diagram generation
- Tool function interface
"""

import os
import sys

import pytest

# Add source path
CHAT_LAMBDA_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "src",
    "lambda",
    "chat",
)
sys.path.insert(0, os.path.abspath(CHAT_LAMBDA_PATH))


class TestDiagramTypes:
    """Test different diagram type generation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import diagram tools module."""
        from diagram_tools import (
            DiagramFormat,
            DiagramGenerator,
            DiagramResult,
            DiagramType,
            generate_diagram,
        )

        self.DiagramGenerator = DiagramGenerator
        self.DiagramType = DiagramType
        self.DiagramFormat = DiagramFormat
        self.DiagramResult = DiagramResult
        self.generate_diagram = generate_diagram
        self.generator = DiagramGenerator()

    def test_flowchart_generation(self):
        """Should generate flowchart diagrams."""
        result = self.generator.generate(
            diagram_type="flowchart",
            subject="user workflow",
            format="mermaid",
            scope="component",
        )
        assert result.diagram_type == "flowchart"
        assert result.format == "mermaid"
        assert "flowchart" in result.code.lower()
        assert result.title is not None
        assert result.description is not None

    def test_sequence_diagram_generation(self):
        """Should generate sequence diagrams."""
        result = self.generator.generate(
            diagram_type="sequence",
            subject="API call flow",
            format="mermaid",
            scope="service",
        )
        assert result.diagram_type == "sequence"
        assert "sequenceDiagram" in result.code

    def test_class_diagram_generation(self):
        """Should generate class diagrams."""
        result = self.generator.generate(
            diagram_type="class",
            subject="Agent system",
            format="mermaid",
            scope="component",
        )
        assert result.diagram_type == "class"
        assert "classDiagram" in result.code

    def test_er_diagram_generation(self):
        """Should generate ER diagrams."""
        result = self.generator.generate(
            diagram_type="er",
            subject="user data",
            format="mermaid",
            scope="component",
        )
        assert result.diagram_type == "er"
        assert "erDiagram" in result.code

    def test_state_diagram_generation(self):
        """Should generate state diagrams."""
        result = self.generator.generate(
            diagram_type="state",
            subject="request lifecycle",
            format="mermaid",
            scope="component",
        )
        assert result.diagram_type == "state"
        assert "stateDiagram" in result.code

    def test_architecture_diagram_generation(self):
        """Should generate architecture diagrams."""
        result = self.generator.generate(
            diagram_type="architecture",
            subject="system overview",
            format="mermaid",
            scope="system",
        )
        assert result.diagram_type == "architecture"
        assert "flowchart" in result.code.lower() or "subgraph" in result.code.lower()

    def test_dependency_diagram_generation(self):
        """Should generate dependency diagrams."""
        result = self.generator.generate(
            diagram_type="dependency",
            subject="module dependencies",
            format="mermaid",
            scope="codebase",
        )
        assert result.diagram_type == "dependency"
        assert "flowchart" in result.code.lower()


class TestTemplateMatching:
    """Test template selection based on subject."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import diagram tools module."""
        from diagram_tools import DiagramGenerator

        self.generator = DiagramGenerator()

    def test_agent_orchestration_template(self):
        """Agent orchestration subject should use specific template."""
        result = self.generator.generate(
            diagram_type="flowchart",
            subject="agent orchestration",
            format="mermaid",
        )
        assert "Orchestrator" in result.code
        assert "Agent" in result.code or "agent" in result.code.lower()

    def test_authentication_template(self):
        """Authentication subject should use auth template."""
        result = self.generator.generate(
            diagram_type="sequence",
            subject="authentication flow",
            format="mermaid",
        )
        assert "Cognito" in result.code or "authenticate" in result.code.lower()

    def test_chat_flow_template(self):
        """Chat subject should use chat flow template."""
        result = self.generator.generate(
            diagram_type="sequence",
            subject="chat message flow",
            format="mermaid",
        )
        assert "Lambda" in result.code or "message" in result.code.lower()

    def test_hitl_workflow_template(self):
        """HITL subject should use approval workflow template."""
        result = self.generator.generate(
            diagram_type="state",
            subject="hitl approval process",
            format="mermaid",
        )
        assert "Approved" in result.code or "approval" in result.code.lower()

    def test_data_model_template(self):
        """Chat data model should use ER template."""
        result = self.generator.generate(
            diagram_type="er",
            subject="chat conversation model",
            format="mermaid",
        )
        assert "CONVERSATION" in result.code or "conversation" in result.code.lower()

    def test_infrastructure_template(self):
        """Infrastructure subject should use infra template."""
        result = self.generator.generate(
            diagram_type="architecture",
            subject="infrastructure overview",
            format="mermaid",
        )
        assert "VPC" in result.code or "vpc" in result.code.lower()


class TestOutputFormats:
    """Test different output format generation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import diagram tools module."""
        from diagram_tools import DiagramGenerator

        self.generator = DiagramGenerator()

    def test_mermaid_format_output(self):
        """Mermaid format should return Mermaid code."""
        result = self.generator.generate(
            diagram_type="flowchart",
            subject="test flow",
            format="mermaid",
        )
        assert result.format == "mermaid"
        # Mermaid code should start with diagram type
        code_lower = result.code.lower().strip()
        assert any(
            code_lower.startswith(prefix)
            for prefix in [
                "flowchart",
                "sequencediagram",
                "classdiagram",
                "erdiagram",
                "statediagram",
            ]
        )

    def test_plantuml_format_output(self):
        """PlantUML format should return PlantUML code."""
        result = self.generator.generate(
            diagram_type="sequence",
            subject="auth flow",
            format="plantuml",
        )
        assert result.format == "plantuml"
        assert "@startuml" in result.code
        assert "@enduml" in result.code

    def test_drawio_format_output(self):
        """draw.io format should return XML."""
        result = self.generator.generate(
            diagram_type="flowchart",
            subject="test flow",
            format="drawio",
        )
        assert result.format == "drawio"
        assert "<?xml" in result.code
        assert "mxfile" in result.code
        assert "mxGraphModel" in result.code

    def test_case_insensitive_format(self):
        """Format parameter should be case-insensitive."""
        result1 = self.generator.generate(
            diagram_type="flowchart",
            subject="test",
            format="MERMAID",
        )
        result2 = self.generator.generate(
            diagram_type="flowchart",
            subject="test",
            format="Mermaid",
        )
        assert result1.format == "mermaid"
        assert result2.format == "mermaid"


class TestDiagramResult:
    """Test DiagramResult dataclass."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import diagram tools module."""
        from diagram_tools import DiagramResult

        self.DiagramResult = DiagramResult

    def test_diagram_result_fields(self):
        """DiagramResult should have all required fields."""
        result = self.DiagramResult(
            diagram_type="flowchart",
            format="mermaid",
            code="flowchart TD\n    A --> B",
            title="Test Diagram",
            description="Test description",
        )
        assert result.diagram_type == "flowchart"
        assert result.format == "mermaid"
        assert result.code == "flowchart TD\n    A --> B"
        assert result.title == "Test Diagram"
        assert result.description == "Test description"


class TestGenerateDiagramFunction:
    """Test the generate_diagram tool function interface."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import diagram tools module."""
        from diagram_tools import generate_diagram

        self.generate_diagram = generate_diagram

    def test_generate_diagram_returns_dict(self):
        """Tool function should return a dictionary."""
        result = self.generate_diagram(
            diagram_type="flowchart",
            subject="test workflow",
            format="mermaid",
            scope="component",
        )
        assert isinstance(result, dict)
        assert "diagram_type" in result
        assert "format" in result
        assert "code" in result
        assert "title" in result
        assert "description" in result

    def test_generate_diagram_includes_render_hint(self):
        """Tool function should include render_hint for frontend."""
        result = self.generate_diagram(
            diagram_type="flowchart",
            subject="test",
            format="mermaid",
        )
        assert "render_hint" in result
        assert result["render_hint"] == "mermaid"

    def test_generate_diagram_plantuml_render_hint(self):
        """PlantUML should have 'code' render hint."""
        result = self.generate_diagram(
            diagram_type="sequence",
            subject="test",
            format="plantuml",
        )
        assert result["render_hint"] == "code"

    def test_generate_diagram_drawio_render_hint(self):
        """draw.io should have 'code' render hint."""
        result = self.generate_diagram(
            diagram_type="flowchart",
            subject="test",
            format="drawio",
        )
        assert result["render_hint"] == "code"

    def test_generate_diagram_with_tenant_id(self):
        """Tool function should accept tenant_id parameter."""
        result = self.generate_diagram(
            diagram_type="flowchart",
            subject="test",
            format="mermaid",
            scope="component",
            tenant_id="test-tenant-001",
        )
        assert isinstance(result, dict)
        assert "code" in result


class TestDiagramEnums:
    """Test diagram type and format enums."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import diagram tools module."""
        from diagram_tools import DiagramFormat, DiagramType

        self.DiagramType = DiagramType
        self.DiagramFormat = DiagramFormat

    def test_diagram_type_values(self):
        """DiagramType enum should have expected values."""
        expected_types = [
            "flowchart",
            "sequence",
            "class",
            "er",
            "state",
            "architecture",
            "dependency",
        ]
        actual_types = [t.value for t in self.DiagramType]
        for expected in expected_types:
            assert expected in actual_types

    def test_diagram_format_values(self):
        """DiagramFormat enum should have expected values."""
        expected_formats = ["mermaid", "plantuml", "drawio"]
        actual_formats = [f.value for f in self.DiagramFormat]
        for expected in expected_formats:
            assert expected in actual_formats


class TestSingletonPattern:
    """Test singleton pattern for DiagramGenerator."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import diagram tools module."""
        from diagram_tools import get_diagram_generator

        self.get_diagram_generator = get_diagram_generator

    def test_singleton_returns_same_instance(self):
        """get_diagram_generator should return same instance."""
        gen1 = self.get_diagram_generator()
        gen2 = self.get_diagram_generator()
        assert gen1 is gen2

    def test_singleton_has_templates(self):
        """Singleton instance should have templates loaded."""
        generator = self.get_diagram_generator()
        assert hasattr(generator, "templates")
        assert len(generator.templates) > 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Import diagram tools module."""
        from diagram_tools import DiagramGenerator, generate_diagram

        self.generator = DiagramGenerator()
        self.generate_diagram = generate_diagram

    def test_unknown_diagram_type_defaults_to_flowchart(self):
        """Unknown diagram type should fall back to flowchart."""
        result = self.generator.generate(
            diagram_type="unknown_type",
            subject="test",
            format="mermaid",
        )
        # Should not raise, should produce some output
        assert result.code is not None
        assert len(result.code) > 0

    def test_empty_subject_handled(self):
        """Empty subject should be handled gracefully."""
        result = self.generator.generate(
            diagram_type="flowchart",
            subject="",
            format="mermaid",
        )
        assert result.code is not None

    def test_special_characters_in_subject(self):
        """Special characters in subject should be handled."""
        result = self.generator.generate(
            diagram_type="flowchart",
            subject="test <script>alert('xss')</script>",
            format="mermaid",
        )
        assert result.code is not None
        # XSS should not be executed (just checked it doesn't crash)

    def test_very_long_subject(self):
        """Very long subject should be handled."""
        long_subject = "a" * 1000
        result = self.generator.generate(
            diagram_type="flowchart",
            subject=long_subject,
            format="mermaid",
        )
        assert result.code is not None
