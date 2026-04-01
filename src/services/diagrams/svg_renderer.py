"""
SVG Renderer for Enterprise Diagram Generation (ADR-060).

Renders diagram definitions to SVG format with:
- Cloud provider icons (from IconLibrary)
- Dark/light theme support (WCAG AA compliant)
- Accessibility features (ARIA labels, alt text)
- Connection routing with arrows
- Group/container visualization

Based on the UI design specifications.
"""

import html
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .icon_library import IconColorMode, IconLibrary
from .models import (
    ArrowDirection,
    ConnectionStyle,
    DiagramConnection,
    DiagramDefinition,
    DiagramGroup,
    DiagramNode,
    NodeShape,
)


class Theme(Enum):
    """Color theme for rendering."""

    LIGHT = "light"
    DARK = "dark"


@dataclass
class ThemeColors:
    """Color palette for a theme (WCAG AA verified colors)."""

    # Canvas
    canvas_background: str
    canvas_grid: str

    # Nodes
    node_background: str
    node_border: str
    node_text: str
    node_shadow: str

    # Groups
    group_background: str
    group_border: str
    group_header_text: str

    # Connections
    connection_solid: str
    connection_dashed: str
    connection_dotted: str
    connection_arrow: str

    # Semantic colors (for severity/status)
    critical: str
    warning: str
    success: str
    info: str


# Theme definitions (Eraser.io-inspired + WCAG AA verified colors)
THEMES: dict[Theme, ThemeColors] = {
    Theme.LIGHT: ThemeColors(
        canvas_background="#FFFFFF",
        canvas_grid="#E5E7EB",
        node_background="#FFFFFF",
        node_border="#E5E7EB",
        node_text="#1F2937",
        node_shadow="rgba(0, 0, 0, 0.08)",
        group_background="rgba(59, 130, 246, 0.05)",
        group_border="#3B82F6",
        group_header_text="#374151",
        connection_solid="#6B7280",
        connection_dashed="#9CA3AF",
        connection_dotted="#D1D5DB",
        connection_arrow="#6B7280",
        critical="#DC2626",
        warning="#F59E0B",
        success="#10B981",
        info="#3B82F6",
    ),
    Theme.DARK: ThemeColors(
        # Eraser.io style: dark charcoal/navy background
        canvas_background="#1a1a2e",
        canvas_grid="#2a2a4a",
        # Nodes: semi-transparent dark cards
        node_background="#252542",
        node_border="#3a3a5c",
        node_text="#FFFFFF",
        node_shadow="rgba(0, 0, 0, 0.4)",
        # Groups: colored borders with dark fill
        group_background="rgba(100, 100, 140, 0.15)",
        group_border="#5a5a8a",
        group_header_text="#FFFFFF",
        # Connections: white/light for visibility
        connection_solid="#FFFFFF",
        connection_dashed="#CCCCCC",
        connection_dotted="#888888",
        connection_arrow="#FFFFFF",
        # Semantic colors (brighter for dark bg)
        critical="#FF6B6B",
        warning="#FFD93D",
        success="#6BCB77",
        info="#4D96FF",
    ),
}


@dataclass
class RenderOptions:
    """Options for SVG rendering."""

    # Eraser.io style: dark theme by default
    theme: Theme = Theme.DARK
    show_grid: bool = False
    show_icons: bool = True
    icon_color_mode: IconColorMode = IconColorMode.NATIVE
    font_family: str = "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    mono_font_family: str = "JetBrains Mono, Menlo, Monaco, monospace"
    include_styles: bool = True
    include_defs: bool = True
    interactive: bool = False  # Add hover/click handlers
    export_mode: bool = False  # Optimize for PNG/PDF export


class SVGRenderer:
    """
    Server-side SVG renderer for diagram definitions.

    Renders diagrams with:
    - Official cloud provider icons
    - Dark/light theme support
    - WCAG 2.1 AA compliant colors
    - Accessibility attributes

    Usage:
        renderer = SVGRenderer(icon_library)
        svg = renderer.render(definition)
    """

    # Arrow marker dimensions (clean open arrows like Eraser.io)
    ARROW_WIDTH = 10
    ARROW_HEIGHT = 10

    # Node corner radius (Eraser-style: 8px for compact cards)
    NODE_RADIUS = 8

    # Font sizes (Eraser.io style - optimized for 88x100 icon-centric nodes)
    FONT_SIZE_TITLE = 16
    FONT_SIZE_NODE = 11  # Primary label (below icon)
    FONT_SIZE_NODE_SUB = 9  # Secondary label
    FONT_SIZE_GROUP = 10
    FONT_SIZE_CONNECTION = 9
    FONT_SIZE_METADATA = 9

    # Icon size (Eraser.io style: 48px prominent icons)
    ICON_SIZE = 48

    def __init__(
        self,
        icon_library: Optional[IconLibrary] = None,
        options: Optional[RenderOptions] = None,
    ):
        """
        Initialize the SVG renderer.

        Args:
            icon_library: Icon library for cloud provider icons
            options: Rendering options
        """
        self.icon_library = icon_library or IconLibrary()
        self.options = options or RenderOptions()
        self.colors = THEMES[self.options.theme]

    def render(
        self,
        definition: DiagramDefinition,
        options: Optional[RenderOptions] = None,
    ) -> str:
        """
        Render diagram definition to SVG string.

        Args:
            definition: The diagram to render (must have layout applied)
            options: Override rendering options

        Returns:
            SVG string
        """
        opts = options or self.options
        colors = THEMES[opts.theme]

        # Update icon library color mode
        self.icon_library.set_color_mode(opts.icon_color_mode)

        # Calculate canvas size from actual node positions
        width, height = self._calculate_canvas_size(definition)

        # Start SVG document
        svg_parts = [
            self._svg_header(width, height, definition.metadata.title),
        ]

        # Add defs (gradients, markers, filters)
        if opts.include_defs:
            svg_parts.append(self._svg_defs(colors))

        # Add styles
        if opts.include_styles:
            svg_parts.append(self._svg_styles(colors, opts))

        # Background
        svg_parts.append(
            f'<rect width="{width}" height="{height}" fill="{colors.canvas_background}"/>'
        )

        # Grid (optional)
        if opts.show_grid:
            svg_parts.append(self._render_grid(width, height, colors))

        # Render groups first (background containers)
        for group in definition.groups:
            svg_parts.append(self._render_group(group, colors, opts))

        # Render connections (before nodes so they appear behind)
        for conn in definition.connections:
            svg_parts.append(self._render_connection(conn, definition, colors))

        # Render nodes
        for node in definition.nodes:
            svg_parts.append(self._render_node(node, colors, opts))

        # Close SVG
        svg_parts.append("</svg>")

        return "\n".join(svg_parts)

    def _svg_header(self, width: float, height: float, title: str) -> str:
        """Generate SVG header with accessibility attributes."""
        safe_title = html.escape(title)
        return f"""<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{width}" height="{height}"
     viewBox="0 0 {width} {height}"
     role="img"
     aria-label="{safe_title}">
  <title>{safe_title}</title>"""

    def _svg_defs(self, colors: ThemeColors) -> str:
        """Generate SVG defs for markers, gradients, filters (Eraser.io style)."""
        return f"""  <defs>
    <!-- Eraser.io style arrow markers (clean white open arrows) -->
    <marker id="arrow-forward" viewBox="0 0 12 12" refX="10" refY="6"
            markerWidth="10" markerHeight="10" orient="auto-start-reverse">
      <path d="M2 2 L10 6 L2 10" fill="none" stroke="{colors.connection_arrow}"
            stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </marker>
    <marker id="arrow-backward" viewBox="0 0 12 12" refX="2" refY="6"
            markerWidth="10" markerHeight="10" orient="auto-start-reverse">
      <path d="M10 2 L2 6 L10 10" fill="none" stroke="{colors.connection_arrow}"
            stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </marker>
    <marker id="arrow-filled" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="8" markerHeight="8" orient="auto">
      <path d="M0 0 L10 5 L0 10 Z" fill="{colors.connection_arrow}"/>
    </marker>

    <!-- Subtle shadow for dark theme (minimal) -->
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="rgba(0,0,0,0.3)" flood-opacity="0.3"/>
    </filter>

    <!-- Card shadow for nodes -->
    <filter id="card-shadow" x="-15%" y="-15%" width="130%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="rgba(0,0,0,0.25)" flood-opacity="0.25"/>
    </filter>

    <!-- Elevated shadow for hover states -->
    <filter id="elevated-shadow" x="-25%" y="-25%" width="150%" height="160%">
      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="rgba(0,0,0,0.35)" flood-opacity="0.35"/>
    </filter>

    <!-- Glow filter for selection -->
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <!-- Node background gradient for dark theme (subtle gradient) -->
    <linearGradient id="node-bg-gradient-dark" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#2d2d4a"/>
      <stop offset="100%" style="stop-color:#252542"/>
    </linearGradient>

    <!-- Node background gradient for light theme -->
    <linearGradient id="node-bg-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FFFFFF"/>
      <stop offset="100%" style="stop-color:#F9FAFB"/>
    </linearGradient>

    <!-- AWS Service Category Colors (for node backgrounds) -->
    <!-- Compute: Orange -->
    <linearGradient id="compute-bg-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF9900"/>
      <stop offset="100%" style="stop-color:#EC7211"/>
    </linearGradient>
    <!-- Database: Blue -->
    <linearGradient id="database-bg-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3B48CC"/>
      <stop offset="100%" style="stop-color:#2D3A9E"/>
    </linearGradient>
    <!-- Storage: Green -->
    <linearGradient id="storage-bg-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3F8624"/>
      <stop offset="100%" style="stop-color:#2E6319"/>
    </linearGradient>
    <!-- Networking: Purple -->
    <linearGradient id="networking-bg-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#8C4FFF"/>
      <stop offset="100%" style="stop-color:#6B35CC"/>
    </linearGradient>
    <!-- Security: Red -->
    <linearGradient id="security-bg-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#DD344C"/>
      <stop offset="100%" style="stop-color:#B32A3E"/>
    </linearGradient>
    <!-- Integration: Pink -->
    <linearGradient id="integration-bg-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#E7157B"/>
      <stop offset="100%" style="stop-color:#C41162"/>
    </linearGradient>
    <!-- ML/AI: Teal -->
    <linearGradient id="ml-bg-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#01A88D"/>
      <stop offset="100%" style="stop-color:#018571"/>
    </linearGradient>
    <!-- Default: Blue -->
    <linearGradient id="default-bg-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3B82F6"/>
      <stop offset="100%" style="stop-color:#1D4ED8"/>
    </linearGradient>
  </defs>"""

    def _svg_styles(self, colors: ThemeColors, opts: RenderOptions) -> str:
        """Generate embedded CSS styles (Eraser.io dark theme optimized)."""
        return f"""  <style>
    .node {{
      cursor: pointer;
    }}
    .node:hover rect, .node:hover circle, .node:hover polygon {{
      filter: url(#elevated-shadow);
      opacity: 0.95;
    }}
    .node:focus {{
      outline: none;
    }}
    .node:focus rect, .node:focus circle {{
      stroke: {colors.info};
      stroke-width: 2;
    }}
    .node-label {{
      font-family: {opts.font_family};
      font-size: {self.FONT_SIZE_NODE}px;
      font-weight: 500;
      fill: {colors.node_text};
      letter-spacing: 0.2px;
    }}
    .node-label-sub {{
      font-family: {opts.font_family};
      font-size: {self.FONT_SIZE_NODE_SUB}px;
      font-weight: 400;
      fill: rgba(255, 255, 255, 0.7);
    }}
    .group-label {{
      font-family: {opts.font_family};
      font-size: {self.FONT_SIZE_GROUP}px;
      font-weight: 600;
      fill: {colors.group_header_text};
      text-transform: uppercase;
      letter-spacing: 0.8px;
    }}
    .connection-label {{
      font-family: {opts.font_family};
      font-size: {self.FONT_SIZE_CONNECTION}px;
      fill: rgba(255, 255, 255, 0.8);
    }}
    .group {{
      transition: opacity 0.2s ease;
    }}
    .group.collapsed > .group-content {{
      display: none;
    }}
    /* Connection lines */
    .connection path {{
      transition: stroke-width 0.15s ease;
    }}
    .connection:hover path {{
      stroke-width: 2.5;
    }}
  </style>"""

    def _calculate_canvas_size(
        self,
        definition: DiagramDefinition,
        padding: float = 40.0,
    ) -> tuple[float, float]:
        """
        Calculate required canvas size based on node positions.

        Ensures all nodes are visible with padding around edges.
        """
        if not definition.nodes:
            return (definition.width or 800, definition.height or 600)

        # Find max bounds from all nodes
        max_x = 0.0
        max_y = 0.0

        for node in definition.nodes:
            if node.position and node.size:
                node_right = node.position.x + node.size.width
                node_bottom = node.position.y + node.size.height
                max_x = max(max_x, node_right)
                max_y = max(max_y, node_bottom)

        # Also check groups
        for group in definition.groups:
            if group.position and group.size:
                group_right = group.position.x + group.size.width
                group_bottom = group.position.y + group.size.height
                max_x = max(max_x, group_right)
                max_y = max(max_y, group_bottom)

        # Add padding
        width = max_x + padding
        height = max_y + padding

        # Ensure minimum size
        width = max(width, definition.width or 400)
        height = max(height, definition.height or 300)

        return (width, height)

    def _render_grid(
        self,
        width: float,
        height: float,
        colors: ThemeColors,
    ) -> str:
        """Render background grid."""
        grid_size = 20
        lines = []

        # Vertical lines
        for x in range(0, int(width) + 1, grid_size):
            lines.append(
                f'<line x1="{x}" y1="0" x2="{x}" y2="{height}" '
                f'stroke="{colors.canvas_grid}" stroke-width="0.5"/>'
            )

        # Horizontal lines
        for y in range(0, int(height) + 1, grid_size):
            lines.append(
                f'<line x1="0" y1="{y}" x2="{width}" y2="{y}" '
                f'stroke="{colors.canvas_grid}" stroke-width="0.5"/>'
            )

        return '<g class="grid">\n    ' + "\n    ".join(lines) + "\n  </g>"

    def _render_group(
        self,
        group: DiagramGroup,
        colors: ThemeColors,
        opts: RenderOptions,
    ) -> str:
        """Render a group container with Eraser.io style header."""
        if not group.position or not group.size:
            return ""

        x = group.position.x
        y = group.position.y
        width = group.size.width
        height = group.size.height

        # Use group color or default
        border_color = group.color or colors.group_border

        safe_label = html.escape(group.label)
        safe_id = html.escape(group.id)

        # Determine header color based on group type (VPC, subnet, etc.)
        header_color = self._get_group_header_color(group.label, border_color)

        # Header dimensions
        header_height = 28
        header_padding = 12
        border_radius = 12

        # Eraser.io style: Dark background with colored header bar
        return f"""  <g class="group" id="group-{safe_id}"
       role="group" aria-label="{safe_label}">
    <!-- Group background (dark with subtle border) -->
    <rect x="{x}" y="{y}" width="{width}" height="{height}"
          rx="{border_radius}" ry="{border_radius}"
          fill="{colors.group_background}"
          stroke="{border_color}"
          stroke-width="1.5"/>
    <!-- Header bar with service color -->
    <rect x="{x}" y="{y}" width="{width}" height="{header_height}"
          rx="{border_radius}" ry="{border_radius}"
          fill="{header_color}"/>
    <!-- Cover bottom corners of header to make it flat-bottom -->
    <rect x="{x}" y="{y + header_height - border_radius}" width="{width}" height="{border_radius}"
          fill="{header_color}"/>
    <!-- Group label in header -->
    <text x="{x + header_padding}" y="{y + 18}" class="group-label"
          style="font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; fill: white; font-size: 10px;">
      {safe_label}
    </text>
  </g>"""

    def _get_group_header_color(self, label: str, default_color: str) -> str:
        """Get header color based on group type."""
        label_lower = label.lower()

        # VPC - Purple
        if "vpc" in label_lower:
            return "#6b35cc"

        # Subnet - Blue shades
        if "public" in label_lower and "subnet" in label_lower:
            return "#2563eb"
        if "private" in label_lower and "subnet" in label_lower:
            return "#1e40af"
        if "subnet" in label_lower:
            return "#3b82f6"

        # Processing stages
        if "pre-processing" in label_lower or "preprocessing" in label_lower:
            return "#4a5568"
        if "processing" in label_lower:
            return "#374151"
        if "post-processing" in label_lower or "postprocessing" in label_lower:
            return "#4a5568"

        # Compute
        if "compute" in label_lower or "server" in label_lower:
            return "#cc2936"

        # Database
        if "database" in label_lower or "data" in label_lower:
            return "#2563eb"

        # Security
        if "security" in label_lower:
            return "#dc2626"

        # Default
        return default_color or "#4a5a7a"

    def _render_node(
        self,
        node: DiagramNode,
        colors: ThemeColors,
        opts: RenderOptions,
    ) -> str:
        """
        Render a node with Eraser.io style (icon top, label below).

        Creates nodes with:
        - Colorful service category backgrounds
        - Large centered icons
        - Labels below the icon
        - Clean, compact appearance
        """
        if not node.position or not node.size:
            return ""

        x = node.position.x
        y = node.position.y
        width = node.size.width
        height = node.size.height

        safe_label = html.escape(node.label)
        safe_id = html.escape(node.id)

        # Determine if we have an icon
        has_icon = opts.show_icons and node.icon_id
        icon = None
        icon_color = None
        if has_icon:
            icon = self.icon_library.get_icon(node.icon_id)
            if icon:
                icon_color = self.icon_library.get_icon_color(icon)

        # Build node SVG
        parts = [
            f'  <g class="node" id="node-{safe_id}" tabindex="0"',
            f'     role="button" aria-label="{safe_label}"',
            f'     data-node-id="{safe_id}">',
        ]

        # Eraser.io style: Colored card with icon centered
        shape_svg = self._render_eraser_node(
            x, y, width, height, node.shape, icon_color, colors, opts
        )
        parts.append(f"    {shape_svg}")

        # Render icon centered at top portion of node
        if icon:
            icon_size = self.ICON_SIZE
            icon_x = x + width / 2  # Center horizontally
            icon_y = y + 12 + icon_size / 2  # 12px from top + half icon
            icon_svg = self._render_icon(icon_x, icon_y, icon, size=icon_size)
            parts.append(f"    {icon_svg}")

        # Render label centered below icon (handle multiline)
        label_x = x + width / 2
        label_base_y = y + height - 20  # Start position for label

        # Handle multiline labels
        label_lines = node.label.replace("\\n", "\n").split("\n")
        if len(label_lines) > 1:
            # Multiline: use tspan elements
            tspans = []
            for i, line in enumerate(label_lines):
                safe_line = html.escape(line.strip())
                dy = 'dy="12"' if i > 0 else 'dy="0"'
                tspans.append(f'<tspan x="{label_x}" {dy}>{safe_line}</tspan>')
            parts.append(
                f'    <text x="{label_x}" y="{label_base_y}" '
                f'text-anchor="middle" class="node-label">\n      '
                + "\n      ".join(tspans)
                + "\n    </text>"
            )
        else:
            parts.append(
                f'    <text x="{label_x}" y="{label_base_y + 8}" '
                f'text-anchor="middle" class="node-label">{safe_label}</text>'
            )

        parts.append("  </g>")

        return "\n".join(parts)

    def _render_eraser_node(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        shape: NodeShape,
        icon_color: Optional[str],
        colors: ThemeColors,
        opts: RenderOptions,
    ) -> str:
        """
        Render Eraser.io style node background.

        Colorful cards based on service category with rounded corners.
        """
        # Determine background color based on icon/service category
        bg_color = self._get_service_background_color(icon_color)

        if shape == NodeShape.CYLINDER:
            # Database cylinder
            rx = width / 2
            ry = 8
            return f"""<g filter="url(#card-shadow)">
      <ellipse cx="{x + width / 2}" cy="{y + ry}" rx="{rx}" ry="{ry}"
               fill="{bg_color}"/>
      <rect x="{x}" y="{y + ry}" width="{width}" height="{height - 2 * ry}"
            fill="{bg_color}"/>
      <ellipse cx="{x + width / 2}" cy="{y + height - ry}" rx="{rx}" ry="{ry}"
               fill="{bg_color}"/>
    </g>"""

        elif shape == NodeShape.CIRCLE:
            cx = x + width / 2
            cy = y + height / 2
            r = min(width, height) / 2
            return (
                f'<circle cx="{cx}" cy="{cy}" r="{r}" '
                f'fill="{bg_color}" filter="url(#card-shadow)"/>'
            )

        elif shape == NodeShape.DIAMOND:
            cx = x + width / 2
            cy = y + height / 2
            points = f"{cx},{y} {x + width},{cy} {cx},{y + height} {x},{cy}"
            return (
                f'<polygon points="{points}" '
                f'fill="{bg_color}" filter="url(#card-shadow)"/>'
            )

        else:
            # Default: rounded rectangle (Eraser.io style)
            return (
                f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
                f'rx="{self.NODE_RADIUS}" ry="{self.NODE_RADIUS}" '
                f'fill="{bg_color}" filter="url(#card-shadow)"/>'
            )

    def _get_service_background_color(self, icon_color: Optional[str]) -> str:
        """
        Get Eraser.io style background color based on service category.

        Maps AWS service colors to appropriate backgrounds.
        """
        if not icon_color:
            return "#3d3d5c"  # Default dark card

        # Map icon colors to service categories
        color_lower = icon_color.lower()

        # AWS Orange (Compute: EC2, Lambda, ECS)
        if color_lower in ("#ff9900", "#ec7211", "#f90"):
            return "#cc7a00"  # Darker orange

        # AWS Blue (Database: RDS, DynamoDB, Neptune)
        if color_lower in ("#3b48cc", "#2d3a9e", "#527fff"):
            return "#2a3499"  # Darker blue

        # AWS Green (Storage: S3, EBS, EFS)
        if color_lower in ("#3f8624", "#2e6319", "#7aa116"):
            return "#2d5c1a"  # Darker green

        # AWS Purple (Networking: VPC, CloudFront, Route53)
        if color_lower in ("#8c4fff", "#6b35cc"):
            return "#5c33aa"  # Darker purple

        # AWS Red (Security: IAM, Cognito, WAF)
        if color_lower in ("#dd344c", "#b32a3e"):
            return "#992235"  # Darker red

        # AWS Pink (Integration: SNS, SQS, EventBridge)
        if color_lower in ("#e7157b", "#ff4f8b"):
            return "#b31060"  # Darker pink

        # AWS Teal (ML/AI: SageMaker, Bedrock)
        if color_lower in ("#01a88d", "#018571"):
            return "#017a66"  # Darker teal

        # Default dark card
        return "#3d3d5c"

    def _render_node_shape(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        shape: NodeShape,
        fill: str,
        stroke: str,
    ) -> str:
        """Render node shape (rect, circle, diamond, etc.)."""
        if shape == NodeShape.CIRCLE:
            cx = x + width / 2
            cy = y + height / 2
            r = min(width, height) / 2
            return (
                f'<circle cx="{cx}" cy="{cy}" r="{r}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="1" filter="url(#shadow)"/>'
            )
        elif shape == NodeShape.DIAMOND:
            cx = x + width / 2
            cy = y + height / 2
            points = f"{cx},{y} " f"{x + width},{cy} " f"{cx},{y + height} " f"{x},{cy}"
            return (
                f'<polygon points="{points}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="1" filter="url(#shadow)"/>'
            )
        elif shape == NodeShape.CYLINDER:
            # Database cylinder shape
            rx = width / 2
            ry = 8  # Ellipse height for cylinder caps
            return f"""<g>
      <ellipse cx="{x + width / 2}" cy="{y + ry}" rx="{rx}" ry="{ry}"
               fill="{fill}" stroke="{stroke}" stroke-width="1"/>
      <rect x="{x}" y="{y + ry}" width="{width}" height="{height - 2 * ry}"
            fill="{fill}" stroke="{stroke}" stroke-width="1"/>
      <ellipse cx="{x + width / 2}" cy="{y + height - ry}" rx="{rx}" ry="{ry}"
               fill="{fill}" stroke="{stroke}" stroke-width="1" filter="url(#shadow)"/>
    </g>"""
        else:
            # Default: rounded rectangle
            return (
                f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
                f'rx="{self.NODE_RADIUS}" ry="{self.NODE_RADIUS}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="1" filter="url(#shadow)"/>'
            )

    def _render_node_shape_professional(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        shape: NodeShape,
        stroke: str,
        accent_color: Optional[str] = None,
    ) -> str:
        """
        Render professional node shape with clean, minimal styling.

        Creates a card-like appearance with:
        - Clean white/light background
        - Subtle border
        - Gentle shadow
        - Optional subtle accent (left border only, not full top strip)
        """
        # Use a subtle accent indicator instead of garish colored strips
        # AWS-style: thin left border accent
        accent_width = 3 if accent_color else 0

        if shape == NodeShape.CIRCLE:
            cx = x + width / 2
            cy = y + height / 2
            r = min(width, height) / 2
            result = (
                f'<circle cx="{cx}" cy="{cy}" r="{r}" '
                f'fill="url(#node-bg-gradient)" stroke="{stroke}" stroke-width="1" '
                f'filter="url(#card-shadow)"/>'
            )
            if accent_color:
                # Subtle inner glow instead of ring
                result += (
                    f'\n    <circle cx="{cx}" cy="{cy}" r="{r-4}" '
                    f'fill="none" stroke="{accent_color}" stroke-width="1" opacity="0.15"/>'
                )
            return result

        elif shape == NodeShape.DIAMOND:
            # Diamond shape with professional gradient
            cx = x + width / 2
            cy = y + height / 2
            points = f"{cx},{y} {x + width},{cy} {cx},{y + height} {x},{cy}"
            result = (
                f'<polygon points="{points}" '
                f'fill="url(#node-bg-gradient)" stroke="{stroke}" stroke-width="1" '
                f'filter="url(#card-shadow)"/>'
            )
            return result

        elif shape == NodeShape.CYLINDER:
            # Database cylinder with clean AWS-style blue cap
            rx = width / 2
            ry = 10
            cap_color = accent_color if accent_color else "#3B82F6"  # Blue default
            return f"""<g filter="url(#card-shadow)">
      <ellipse cx="{x + width / 2}" cy="{y + ry}" rx="{rx}" ry="{ry}"
               fill="{cap_color}" opacity="0.85"/>
      <rect x="{x}" y="{y + ry}" width="{width}" height="{height - 2 * ry}"
            fill="url(#node-bg-gradient)" stroke="{stroke}" stroke-width="1"/>
      <ellipse cx="{x + width / 2}" cy="{y + height - ry}" rx="{rx}" ry="{ry}"
               fill="url(#node-bg-gradient)" stroke="{stroke}" stroke-width="1"/>
      <path d="M {x} {y + ry} L {x} {y + height - ry}" stroke="{stroke}" stroke-width="1"/>
      <path d="M {x + width} {y + ry} L {x + width} {y + height - ry}" stroke="{stroke}" stroke-width="1"/>
    </g>"""

        else:
            # Default: clean card with subtle left accent bar (AWS console style)
            parts = ['<g filter="url(#card-shadow)">']

            # Main card body first
            parts.append(
                f'  <rect x="{x}" y="{y}" width="{width}" height="{height}" '
                f'rx="{self.NODE_RADIUS}" ry="{self.NODE_RADIUS}" '
                f'fill="url(#node-bg-gradient)" stroke="{stroke}" stroke-width="1"/>'
            )

            # Subtle left accent bar (AWS console style)
            if accent_color:
                parts.append(
                    f'  <rect x="{x}" y="{y + self.NODE_RADIUS}" '
                    f'width="{accent_width}" height="{height - 2 * self.NODE_RADIUS}" '
                    f'fill="{accent_color}" opacity="0.7"/>'
                )

            parts.append("</g>")
            return "\n    ".join(parts)

    def _render_icon(
        self,
        cx: float,
        cy: float,
        icon,
        size: float = 24,
    ) -> str:
        """
        Render cloud provider icon at position.

        Args:
            cx: Center X position
            cy: Center Y position
            icon: DiagramIcon to render
            size: Icon size in pixels (default 24)
        """
        svg_content = self.icon_library.get_svg_content(icon)

        # Extract inner content from SVG wrapper to enable proper scaling
        # Nested <svg> elements with viewBox don't respect parent transforms
        import re

        # Add width/height to nested SVG to make it respect transforms
        # This fixes the issue where icons render at their natural size
        svg_content = re.sub(
            r'<svg\s+xmlns="[^"]*"\s+viewBox="([^"]*)"',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="\\1"',
            svg_content,
        )

        # Position icon centered at (cx, cy)
        x = cx - size / 2
        y = cy - size / 2

        return (
            f'<g transform="translate({x}, {y})">\n'
            f"      {svg_content}\n"
            f"    </g>"
        )

    def _render_connection(
        self,
        conn: DiagramConnection,
        definition: DiagramDefinition,
        colors: ThemeColors,
    ) -> str:
        """Render connection/edge between nodes with smooth orthogonal routing."""
        if not conn.points or len(conn.points) < 2:
            return ""

        # Build path with rounded corners for orthogonal segments
        corner_radius = 8
        path_d = self._build_rounded_path(conn.points, corner_radius)

        # Determine line style
        stroke_dasharray = ""
        if conn.style == ConnectionStyle.DASHED:
            stroke_dasharray = 'stroke-dasharray="8,4"'
            color = colors.connection_dashed
        elif conn.style == ConnectionStyle.DOTTED:
            stroke_dasharray = 'stroke-dasharray="2,2"'
            color = colors.connection_dotted
        else:
            color = colors.connection_solid

        # Override with custom color if specified
        if conn.color:
            color = conn.color

        # Determine markers
        marker_start = ""
        marker_end = ""
        if conn.arrow in (ArrowDirection.FORWARD, ArrowDirection.BOTH):
            marker_end = 'marker-end="url(#arrow-forward)"'
        if conn.arrow in (ArrowDirection.BACKWARD, ArrowDirection.BOTH):
            marker_start = 'marker-start="url(#arrow-backward)"'

        safe_id = html.escape(conn.id)

        parts = [
            f'  <g class="connection" id="conn-{safe_id}">',
            f'    <path d="{path_d}" fill="none" stroke="{color}" '
            f'stroke-width="1.5" {stroke_dasharray} {marker_start} {marker_end}/>',
        ]

        # Render label if present
        if conn.label:
            # Position label at midpoint of the path with offset to avoid overlapping nodes
            mid_idx = len(conn.points) // 2
            mid_point = conn.points[mid_idx]
            safe_text = html.escape(conn.label.text)

            # Calculate better label position based on connection direction
            # Offset perpendicular to the path to avoid node overlap
            label_x = mid_point.x
            label_y = mid_point.y - 12  # Increased offset

            # Estimate text width for background (approx 7px per character)
            text_width = len(conn.label.text) * 7 + 8
            text_height = 14

            # Add background rectangle for better readability
            parts.append(
                f'    <rect x="{label_x - text_width/2}" y="{label_y - text_height + 3}" '
                f'width="{text_width}" height="{text_height}" rx="3" '
                f'fill="{colors.canvas_background}" fill-opacity="0.85"/>'
            )
            parts.append(
                f'    <text x="{label_x}" y="{label_y}" '
                f'text-anchor="middle" class="connection-label">{safe_text}</text>'
            )

        parts.append("  </g>")

        return "\n".join(parts)

    def _build_rounded_path(
        self,
        points: list,
        radius: float = 8,
    ) -> str:
        """
        Build SVG path with rounded corners for orthogonal segments.

        Creates smooth, professional-looking connection paths.
        """
        if len(points) < 2:
            return ""

        if len(points) == 2:
            # Simple line, no corners
            return f"M {points[0].x} {points[0].y} L {points[1].x} {points[1].y}"

        parts = [f"M {points[0].x} {points[0].y}"]

        for i in range(1, len(points) - 1):
            prev = points[i - 1]
            curr = points[i]
            next_pt = points[i + 1]

            # Vector from prev to curr
            dx1 = curr.x - prev.x
            dy1 = curr.y - prev.y

            # Vector from curr to next
            dx2 = next_pt.x - curr.x
            dy2 = next_pt.y - curr.y

            # Normalize and limit radius
            len1 = max(1, (dx1**2 + dy1**2) ** 0.5)
            len2 = max(1, (dx2**2 + dy2**2) ** 0.5)

            # Actual radius is limited by segment lengths
            actual_radius = min(radius, len1 / 2, len2 / 2)

            if actual_radius < 2:
                # Too short for rounding, use line
                parts.append(f"L {curr.x} {curr.y}")
            else:
                # Calculate arc start and end points
                start_x = curr.x - (dx1 / len1) * actual_radius
                start_y = curr.y - (dy1 / len1) * actual_radius
                end_x = curr.x + (dx2 / len2) * actual_radius
                end_y = curr.y + (dy2 / len2) * actual_radius

                # Line to arc start, then quadratic curve
                parts.append(f"L {start_x} {start_y}")
                parts.append(f"Q {curr.x} {curr.y} {end_x} {end_y}")

        # Final line to last point
        parts.append(f"L {points[-1].x} {points[-1].y}")

        return " ".join(parts)

    def render_to_file(
        self,
        definition: DiagramDefinition,
        output_path: str,
        options: Optional[RenderOptions] = None,
    ) -> None:
        """
        Render diagram to SVG file.

        Args:
            definition: The diagram to render
            output_path: Path to write SVG file
            options: Rendering options
        """
        svg = self.render(definition, options)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg)


def render_diagram(
    definition: DiagramDefinition,
    theme: Theme = Theme.DARK,  # Eraser.io style: dark theme default
    icon_color_mode: IconColorMode = IconColorMode.NATIVE,
) -> str:
    """
    Convenience function to render a diagram to SVG.

    Args:
        definition: The diagram to render (must have layout applied)
        theme: Color theme (dark by default for Eraser.io style)
        icon_color_mode: Icon color mode

    Returns:
        SVG string
    """
    options = RenderOptions(
        theme=theme,
        icon_color_mode=icon_color_mode,
    )
    renderer = SVGRenderer(options=options)
    return renderer.render(definition, options)
