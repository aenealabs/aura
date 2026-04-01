# Copyright (c) 2025 Aenea Labs. All rights reserved.
"""Unit tests for the SVG diagram renderer."""

import os
import tempfile

import pytest

from src.services.diagrams.icon_library import IconColorMode
from src.services.diagrams.layout_engine import LayoutEngine
from src.services.diagrams.models import (
    ArrowDirection,
    ConnectionLabel,
    ConnectionStyle,
    DiagramConnection,
    DiagramDefinition,
    DiagramGroup,
    DiagramMetadata,
    DiagramNode,
    NodeShape,
)
from src.services.diagrams.svg_renderer import (
    THEMES,
    RenderOptions,
    SVGRenderer,
    Theme,
    ThemeColors,
)


class TestRenderOptions:
    """Tests for RenderOptions configuration."""

    def test_default_options(self):
        """Test default render options."""
        options = RenderOptions()
        # Default is DARK theme (Eraser.io style)
        assert options.theme == Theme.DARK
        assert options.show_icons is True
        assert options.icon_color_mode == IconColorMode.NATIVE

    def test_custom_options(self):
        """Test custom render options."""
        options = RenderOptions(
            theme=Theme.DARK,
            show_grid=True,
            icon_color_mode=IconColorMode.AURA_SEMANTIC,
        )
        assert options.theme == Theme.DARK
        assert options.show_grid is True


class TestThemeColors:
    """Tests for theme color configurations."""

    def test_light_theme_exists(self):
        """Test light theme colors are defined."""
        assert Theme.LIGHT in THEMES
        assert isinstance(THEMES[Theme.LIGHT], ThemeColors)

    def test_dark_theme_exists(self):
        """Test dark theme colors are defined."""
        assert Theme.DARK in THEMES
        assert isinstance(THEMES[Theme.DARK], ThemeColors)

    def test_theme_has_required_colors(self):
        """Test themes have all required color properties."""
        for theme in [Theme.LIGHT, Theme.DARK]:
            colors = THEMES[theme]
            assert colors.canvas_background is not None
            assert colors.node_background is not None
            assert colors.node_border is not None
            assert colors.node_text is not None
            assert colors.connection_solid is not None
            assert colors.group_background is not None

    def test_light_theme_has_light_background(self):
        """Test light theme has light background."""
        bg = THEMES[Theme.LIGHT].canvas_background
        # Light backgrounds are typically #FFFFFF or similar
        assert bg.upper() in ["#FFFFFF", "#F8FAFC", "#F1F5F9", "#FEFEFE"]

    def test_dark_theme_has_dark_background(self):
        """Test dark theme has dark background."""
        bg = THEMES[Theme.DARK].canvas_background
        # Dark backgrounds start with low hex values
        assert bg.startswith("#1") or bg.startswith("#2") or bg.startswith("#0")


class TestSVGRendererBasic:
    """Basic rendering tests for SVGRenderer."""

    @pytest.fixture
    def renderer(self):
        """Create a renderer instance."""
        return SVGRenderer()

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="Test Diagram")

    def test_renderer_initialization(self, renderer):
        """Test renderer initializes correctly."""
        assert renderer is not None
        assert renderer.icon_library is not None

    def test_render_empty_diagram(self, renderer, engine, metadata):
        """Test rendering empty diagram."""
        definition = DiagramDefinition(metadata=metadata)
        engine.layout(definition)
        svg = renderer.render(definition)

        assert svg is not None
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_render_single_node(self, renderer, engine, metadata):
        """Test rendering single node."""
        definition = DiagramDefinition(
            metadata=metadata, nodes=[DiagramNode(id="node-1", label="Test Node")]
        )
        engine.layout(definition)
        svg = renderer.render(definition)

        assert "<svg" in svg
        assert "Test Node" in svg

    def test_render_produces_valid_svg_structure(self, renderer, engine, metadata):
        """Test rendered SVG has valid structure."""
        definition = DiagramDefinition(
            metadata=metadata, nodes=[DiagramNode(id="a", label="A")]
        )
        engine.layout(definition)
        svg = renderer.render(definition)

        # Should have proper SVG namespace
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg
        # Should have viewBox or width/height
        assert "viewBox" in svg or ("width" in svg and "height" in svg)


class TestSVGRendererNodeShapes:
    """Tests for rendering different node shapes."""

    @pytest.fixture
    def renderer(self):
        """Create a renderer instance."""
        return SVGRenderer()

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="Shape Test")

    def test_render_rounded_node(self, renderer, engine, metadata):
        """Test rendering rounded rectangle node."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[DiagramNode(id="rounded", label="Rounded", shape=NodeShape.ROUNDED)],
        )
        engine.layout(definition)
        svg = renderer.render(definition)
        assert "<rect" in svg

    def test_render_circle_node(self, renderer, engine, metadata):
        """Test rendering circle node."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[DiagramNode(id="circle", label="Circle", shape=NodeShape.CIRCLE)],
        )
        engine.layout(definition)
        svg = renderer.render(definition)
        assert "<circle" in svg

    def test_render_diamond_node(self, renderer, engine, metadata):
        """Test rendering diamond node."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[DiagramNode(id="diamond", label="Diamond", shape=NodeShape.DIAMOND)],
        )
        engine.layout(definition)
        svg = renderer.render(definition)
        assert "<polygon" in svg

    def test_render_cylinder_node(self, renderer, engine, metadata):
        """Test rendering cylinder node (database shape)."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[DiagramNode(id="db", label="Database", shape=NodeShape.CYLINDER)],
        )
        engine.layout(definition)
        svg = renderer.render(definition)
        assert "<ellipse" in svg


class TestSVGRendererConnections:
    """Tests for rendering connections/edges."""

    @pytest.fixture
    def renderer(self):
        """Create a renderer instance."""
        return SVGRenderer()

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="Connection Test")

    def test_render_simple_connection(self, renderer, engine, metadata):
        """Test rendering simple connection."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[
                DiagramNode(id="a", label="A"),
                DiagramNode(id="b", label="B"),
            ],
            connections=[
                DiagramConnection(id="a-b", source="a", target="b"),
            ],
        )
        engine.layout(definition)
        svg = renderer.render(definition)

        # Should have a path for connection
        assert "<path" in svg or "<line" in svg

    def test_render_connection_with_arrow(self, renderer, engine, metadata):
        """Test rendering connection with arrow marker."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[
                DiagramNode(id="a", label="A"),
                DiagramNode(id="b", label="B"),
            ],
            connections=[
                DiagramConnection(
                    id="a-b", source="a", target="b", arrow=ArrowDirection.FORWARD
                ),
            ],
        )
        engine.layout(definition)
        svg = renderer.render(definition)

        # Should have marker definitions for arrows
        assert "<marker" in svg or "marker-end" in svg

    def test_render_dashed_connection(self, renderer, engine, metadata):
        """Test rendering dashed connection."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[
                DiagramNode(id="a", label="A"),
                DiagramNode(id="b", label="B"),
            ],
            connections=[
                DiagramConnection(
                    id="a-b", source="a", target="b", style=ConnectionStyle.DASHED
                ),
            ],
        )
        engine.layout(definition)
        svg = renderer.render(definition)

        # Should have stroke-dasharray for dashed style
        assert "stroke-dasharray" in svg

    def test_render_connection_label(self, renderer, engine, metadata):
        """Test rendering connection with label."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[
                DiagramNode(id="api", label="API"),
                DiagramNode(id="db", label="DB"),
            ],
            connections=[
                DiagramConnection(
                    id="api-db",
                    source="api",
                    target="db",
                    label=ConnectionLabel(text="SQL"),
                ),
            ],
        )
        engine.layout(definition)
        svg = renderer.render(definition)

        # Label should appear in SVG
        assert "SQL" in svg


class TestSVGRendererGroups:
    """Tests for rendering groups/containers."""

    @pytest.fixture
    def renderer(self):
        """Create a renderer instance."""
        return SVGRenderer()

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="Group Test")

    def test_render_simple_group(self, renderer, engine, metadata):
        """Test rendering simple group."""
        definition = DiagramDefinition(
            metadata=metadata,
            groups=[
                DiagramGroup(id="vpc", label="VPC", children=["server"]),
            ],
            nodes=[
                DiagramNode(id="server", label="Server"),
            ],
        )
        engine.layout(definition)
        svg = renderer.render(definition)

        # Group should have a container rectangle and label
        assert "VPC" in svg
        assert "<rect" in svg

    def test_render_group_with_color(self, renderer, engine, metadata):
        """Test rendering group with custom color."""
        definition = DiagramDefinition(
            metadata=metadata,
            groups=[
                DiagramGroup(
                    id="security",
                    label="Security Zone",
                    color="#DC2626",
                    children=["firewall"],
                ),
            ],
            nodes=[
                DiagramNode(id="firewall", label="Firewall"),
            ],
        )
        engine.layout(definition)
        svg = renderer.render(definition)

        # Should include the custom color
        assert "#DC2626" in svg.upper() or "dc2626" in svg.lower()


class TestSVGRendererThemes:
    """Tests for theme application."""

    @pytest.fixture
    def renderer(self):
        """Create a renderer instance."""
        return SVGRenderer()

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="Theme Test")

    def test_render_light_theme(self, renderer, engine, metadata):
        """Test rendering with light theme."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[DiagramNode(id="a", label="A")],
        )
        engine.layout(definition)
        options = RenderOptions(theme=Theme.LIGHT)
        svg = renderer.render(definition, options)

        # Should use light theme background color
        assert THEMES[Theme.LIGHT].canvas_background in svg

    def test_render_dark_theme(self, renderer, engine, metadata):
        """Test rendering with dark theme."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[DiagramNode(id="a", label="A")],
        )
        engine.layout(definition)
        options = RenderOptions(theme=Theme.DARK)
        svg = renderer.render(definition, options)

        # Should use dark theme background color
        assert THEMES[Theme.DARK].canvas_background in svg


class TestSVGRendererAccessibility:
    """Tests for accessibility features."""

    @pytest.fixture
    def renderer(self):
        """Create a renderer instance."""
        return SVGRenderer()

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="Accessible Diagram")

    def test_svg_has_role(self, renderer, engine, metadata):
        """Test SVG has accessible role attribute."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[DiagramNode(id="a", label="A")],
        )
        engine.layout(definition)
        svg = renderer.render(definition)

        # SVG should have role="img" for accessibility
        assert 'role="img"' in svg

    def test_svg_has_title(self, renderer, engine, metadata):
        """Test SVG has title element."""
        definition = DiagramDefinition(
            metadata=metadata,
            nodes=[DiagramNode(id="a", label="A")],
        )
        engine.layout(definition)
        svg = renderer.render(definition)

        # SVG should have title element
        assert "<title>" in svg
        assert "Accessible Diagram" in svg


class TestSVGRendererFileOutput:
    """Tests for file output functionality."""

    @pytest.fixture
    def renderer(self):
        """Create a renderer instance."""
        return SVGRenderer()

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    @pytest.fixture
    def metadata(self):
        """Create diagram metadata."""
        return DiagramMetadata(title="File Test")

    def test_render_to_file(self, renderer, engine, metadata):
        """Test rendering to file."""
        definition = DiagramDefinition(
            metadata=metadata, nodes=[DiagramNode(id="a", label="Test")]
        )
        engine.layout(definition)

        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            output_path = f.name

        try:
            renderer.render_to_file(definition, output_path)
            assert os.path.exists(output_path)

            with open(output_path, "r") as f:
                content = f.read()
            assert "<svg" in content
            assert "</svg>" in content
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestComplexDiagramRendering:
    """Tests for rendering complex, realistic diagrams."""

    @pytest.fixture
    def renderer(self):
        """Create a renderer instance."""
        return SVGRenderer()

    @pytest.fixture
    def engine(self):
        """Create a layout engine."""
        return LayoutEngine()

    def test_render_three_tier_architecture(self, renderer, engine):
        """Test rendering complete three-tier architecture."""
        definition = DiagramDefinition(
            metadata=DiagramMetadata(title="Three-Tier Architecture"),
            groups=[
                DiagramGroup(id="vpc", label="VPC", children=["web", "app", "db"]),
            ],
            nodes=[
                DiagramNode(id="users", label="Users", icon_id="generic:user"),
                DiagramNode(id="web", label="Web Tier", icon_id="aws:ec2"),
                DiagramNode(id="app", label="App Tier", icon_id="aws:ecs"),
                DiagramNode(id="db", label="Database", icon_id="aws:rds"),
            ],
            connections=[
                DiagramConnection(
                    id="users-web",
                    source="users",
                    target="web",
                    label=ConnectionLabel(text="HTTPS"),
                ),
                DiagramConnection(id="web-app", source="web", target="app"),
                DiagramConnection(
                    id="app-db",
                    source="app",
                    target="db",
                    label=ConnectionLabel(text="SQL"),
                ),
            ],
        )
        engine.layout(definition)
        svg = renderer.render(definition)

        # Verify all components are rendered
        assert "Users" in svg
        assert "Web Tier" in svg
        assert "App Tier" in svg
        assert "Database" in svg
        assert "VPC" in svg

    def test_render_large_diagram(self, renderer, engine):
        """Test rendering larger diagram."""
        nodes = [DiagramNode(id=f"n{i}", label=f"Node {i}") for i in range(15)]
        connections = [
            DiagramConnection(id=f"n{i}-n{i+1}", source=f"n{i}", target=f"n{i+1}")
            for i in range(14)
        ]

        definition = DiagramDefinition(
            metadata=DiagramMetadata(title="Large"),
            nodes=nodes,
            connections=connections,
        )
        engine.layout(definition)
        svg = renderer.render(definition)

        # Should render all nodes
        for i in range(15):
            assert f"Node {i}" in svg
