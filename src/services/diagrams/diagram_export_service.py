"""
Project Aura - Diagram Export Service (ADR-060 Phase 4)

Exports diagrams to multiple formats: SVG, PNG, PDF, and draw.io/diagrams.net.
Supports server-side rendering for consistent output across environments.

Features:
- Native SVG export with optimizations
- PNG rasterization via Playwright/Puppeteer
- PDF generation for documentation
- draw.io XML format for external editing
- S3 pre-signed URL generation for downloads
"""

import base64
import logging
import os
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

# Use defusedxml for safe XML parsing (B314 security)
try:
    import defusedxml.ElementTree as DefusedET

    SAFE_XML_PARSE = DefusedET.fromstring
except ImportError:
    # Fallback to stdlib with nosec for environments without defusedxml
    SAFE_XML_PARSE = ET.fromstring  # nosec B314

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    """Supported export formats."""

    SVG = "svg"
    PNG = "png"
    PDF = "pdf"
    DRAWIO = "drawio"


class ExportStatus(Enum):
    """Export operation status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExportOptions:
    """Options for diagram export."""

    format: ExportFormat
    scale: float = 1.0  # Scale factor for rasterization
    width: Optional[int] = None  # Target width (preserves aspect ratio)
    height: Optional[int] = None  # Target height (preserves aspect ratio)
    background_color: Optional[str] = None  # Background color (default: transparent)
    padding: int = 20  # Padding around diagram
    quality: int = 90  # JPEG/PNG quality (1-100)
    include_metadata: bool = True  # Include metadata in export
    dark_mode: bool = False  # Use dark mode colors


@dataclass
class ExportResult:
    """Result of a diagram export operation."""

    success: bool
    status: ExportStatus
    format: ExportFormat
    content: Optional[bytes] = None  # Raw content for direct download
    content_base64: Optional[str] = None  # Base64 encoded content
    s3_key: Optional[str] = None  # S3 storage key
    presigned_url: Optional[str] = None  # Pre-signed download URL
    file_size: int = 0
    content_type: str = ""
    filename: str = ""
    error: Optional[str] = None
    export_time_ms: int = 0


@dataclass
class DrawioNode:
    """Node representation for draw.io export."""

    id: str
    label: str
    x: float
    y: float
    width: float
    height: float
    style: str = ""
    parent: str = "1"


@dataclass
class DrawioEdge:
    """Edge representation for draw.io export."""

    id: str
    source: str
    target: str
    label: str = ""
    style: str = ""


class DiagramExportService:
    """
    Diagram export service for multi-format output.

    Handles exporting diagrams to:
    - SVG: Native vector format with optimizations
    - PNG: Rasterized image via headless browser
    - PDF: Document format for printing/sharing
    - draw.io: XML format for diagrams.net editing
    """

    # Content types for each format
    CONTENT_TYPES = {
        ExportFormat.SVG: "image/svg+xml",
        ExportFormat.PNG: "image/png",
        ExportFormat.PDF: "application/pdf",
        ExportFormat.DRAWIO: "application/xml",
    }

    # File extensions
    EXTENSIONS = {
        ExportFormat.SVG: ".svg",
        ExportFormat.PNG: ".png",
        ExportFormat.PDF: ".pdf",
        ExportFormat.DRAWIO: ".drawio",
    }

    def __init__(
        self,
        s3_client: Any = None,
        bucket_name: str | None = None,
        environment: str | None = None,
        project_name: str = "aura",
    ):
        """
        Initialize export service.

        Args:
            s3_client: Boto3 S3 client
            bucket_name: S3 bucket for storing exports
            environment: Deployment environment
            project_name: Project name for resource naming
        """
        self.environment = environment or os.getenv("ENVIRONMENT", "dev")
        self.project_name = project_name
        self._s3_client = s3_client
        self._bucket_name = bucket_name or os.getenv(
            "DIAGRAM_EXPORT_BUCKET",
            f"{project_name}-diagram-exports-{self.environment}",
        )

    @property
    def s3_client(self):
        """Lazy S3 client initialization."""
        if self._s3_client is None:
            self._s3_client = boto3.client("s3")
        return self._s3_client

    async def export_diagram(
        self,
        svg_content: str,
        options: ExportOptions,
        diagram_id: str | None = None,
        store_in_s3: bool = False,
    ) -> ExportResult:
        """
        Export a diagram to the specified format.

        Args:
            svg_content: SVG diagram content
            options: Export options
            diagram_id: Optional diagram identifier
            store_in_s3: Store result in S3 and return presigned URL

        Returns:
            ExportResult with export status and content
        """
        import time

        start_time = time.time()
        diagram_id = diagram_id or str(uuid.uuid4())

        try:
            # Route to appropriate export method
            if options.format == ExportFormat.SVG:
                result = await self._export_svg(svg_content, options)
            elif options.format == ExportFormat.PNG:
                result = await self._export_png(svg_content, options)
            elif options.format == ExportFormat.PDF:
                result = await self._export_pdf(svg_content, options)
            elif options.format == ExportFormat.DRAWIO:
                result = await self._export_drawio(svg_content, options)
            else:
                return ExportResult(
                    success=False,
                    status=ExportStatus.FAILED,
                    format=options.format,
                    error=f"Unsupported format: {options.format}",
                )

            # Calculate timing
            export_time_ms = int((time.time() - start_time) * 1000)
            result.export_time_ms = export_time_ms

            # Generate filename
            result.filename = f"diagram-{diagram_id}{self.EXTENSIONS[options.format]}"
            result.content_type = self.CONTENT_TYPES[options.format]

            # Store in S3 if requested
            if store_in_s3 and result.success and result.content:
                s3_result = await self._store_in_s3(
                    result.content, result.filename, result.content_type
                )
                result.s3_key = s3_result.get("key")
                result.presigned_url = s3_result.get("presigned_url")

            return result

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return ExportResult(
                success=False,
                status=ExportStatus.FAILED,
                format=options.format,
                error=str(e),
            )

    async def _export_svg(
        self, svg_content: str, options: ExportOptions
    ) -> ExportResult:
        """Export to optimized SVG format."""
        try:
            # Parse and optimize SVG
            optimized_svg = self._optimize_svg(svg_content, options)

            # Apply background if specified
            if options.background_color:
                optimized_svg = self._add_svg_background(
                    optimized_svg, options.background_color
                )

            content = optimized_svg.encode("utf-8")

            return ExportResult(
                success=True,
                status=ExportStatus.COMPLETED,
                format=ExportFormat.SVG,
                content=content,
                content_base64=base64.b64encode(content).decode(),
                file_size=len(content),
            )

        except Exception as e:
            logger.error(f"SVG export failed: {e}")
            return ExportResult(
                success=False,
                status=ExportStatus.FAILED,
                format=ExportFormat.SVG,
                error=str(e),
            )

    def _optimize_svg(self, svg_content: str, options: ExportOptions) -> str:
        """Optimize SVG content for export."""
        try:
            # Parse SVG
            root = SAFE_XML_PARSE(svg_content)

            # Remove unnecessary whitespace
            for elem in root.iter():
                if elem.text:
                    elem.text = elem.text.strip()
                if elem.tail:
                    elem.tail = elem.tail.strip()

            # Add metadata if requested
            if options.include_metadata:
                metadata = ET.SubElement(root, "metadata")
                desc = ET.SubElement(metadata, "dc:description")
                desc.text = f"Generated by Project Aura on {datetime.now(timezone.utc).isoformat()}"

            # Apply scale if specified
            if options.scale != 1.0:
                viewbox = root.get("viewBox")
                if viewbox:
                    parts = viewbox.split()
                    if len(parts) == 4:
                        width = float(parts[2]) * options.scale
                        height = float(parts[3]) * options.scale
                        root.set("width", str(width))
                        root.set("height", str(height))

            return ET.tostring(root, encoding="unicode")

        except ET.ParseError:
            # Return original if parsing fails
            return svg_content

    def _add_svg_background(self, svg_content: str, color: str) -> str:
        """Add background rectangle to SVG."""
        try:
            root = SAFE_XML_PARSE(svg_content)

            # Get dimensions
            width = root.get("width", "800")
            height = root.get("height", "600")

            # Create background rect
            bg_rect = ET.Element("rect")
            bg_rect.set("x", "0")
            bg_rect.set("y", "0")
            bg_rect.set("width", str(width))
            bg_rect.set("height", str(height))
            bg_rect.set("fill", color)

            # Insert at beginning
            root.insert(0, bg_rect)

            return ET.tostring(root, encoding="unicode")

        except ET.ParseError:
            return svg_content

    async def _export_png(
        self, svg_content: str, options: ExportOptions
    ) -> ExportResult:
        """Export to PNG format using headless rendering."""
        try:
            # Try using cairosvg if available
            try:
                import cairosvg

                # Calculate dimensions
                scale = options.scale
                png_bytes = cairosvg.svg2png(
                    bytestring=svg_content.encode("utf-8"),
                    scale=scale,
                    background_color=options.background_color or "white",
                )

                return ExportResult(
                    success=True,
                    status=ExportStatus.COMPLETED,
                    format=ExportFormat.PNG,
                    content=png_bytes,
                    content_base64=base64.b64encode(png_bytes).decode(),
                    file_size=len(png_bytes),
                )

            except ImportError:
                # Fall back to Playwright if cairosvg not available
                return await self._export_png_playwright(svg_content, options)

        except Exception as e:
            logger.error(f"PNG export failed: {e}")
            return ExportResult(
                success=False,
                status=ExportStatus.FAILED,
                format=ExportFormat.PNG,
                error=str(e),
            )

    async def _export_png_playwright(
        self, svg_content: str, options: ExportOptions
    ) -> ExportResult:
        """Export to PNG using Playwright headless browser."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()

                # Create HTML wrapper
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body {{
                            margin: 0;
                            padding: {options.padding}px;
                            background: {options.background_color or 'transparent'};
                        }}
                    </style>
                </head>
                <body>{svg_content}</body>
                </html>
                """

                await page.set_content(html_content)

                # Take screenshot
                png_bytes = await page.screenshot(
                    type="png",
                    full_page=True,
                    omit_background=options.background_color is None,
                )

                await browser.close()

                return ExportResult(
                    success=True,
                    status=ExportStatus.COMPLETED,
                    format=ExportFormat.PNG,
                    content=png_bytes,
                    content_base64=base64.b64encode(png_bytes).decode(),
                    file_size=len(png_bytes),
                )

        except ImportError:
            return ExportResult(
                success=False,
                status=ExportStatus.FAILED,
                format=ExportFormat.PNG,
                error="PNG export requires cairosvg or playwright package",
            )

    async def _export_pdf(
        self, svg_content: str, options: ExportOptions
    ) -> ExportResult:
        """Export to PDF format."""
        try:
            # Try using cairosvg
            try:
                import cairosvg

                pdf_bytes = cairosvg.svg2pdf(
                    bytestring=svg_content.encode("utf-8"),
                    scale=options.scale,
                )

                return ExportResult(
                    success=True,
                    status=ExportStatus.COMPLETED,
                    format=ExportFormat.PDF,
                    content=pdf_bytes,
                    content_base64=base64.b64encode(pdf_bytes).decode(),
                    file_size=len(pdf_bytes),
                )

            except ImportError:
                # Fall back to Playwright
                return await self._export_pdf_playwright(svg_content, options)

        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            return ExportResult(
                success=False,
                status=ExportStatus.FAILED,
                format=ExportFormat.PDF,
                error=str(e),
            )

    async def _export_pdf_playwright(
        self, svg_content: str, options: ExportOptions
    ) -> ExportResult:
        """Export to PDF using Playwright headless browser."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()

                # Create HTML wrapper
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body {{
                            margin: 0;
                            padding: {options.padding}px;
                        }}
                        @page {{
                            margin: 0;
                        }}
                    </style>
                </head>
                <body>{svg_content}</body>
                </html>
                """

                await page.set_content(html_content)

                # Generate PDF
                pdf_bytes = await page.pdf(
                    print_background=True,
                    prefer_css_page_size=True,
                )

                await browser.close()

                return ExportResult(
                    success=True,
                    status=ExportStatus.COMPLETED,
                    format=ExportFormat.PDF,
                    content=pdf_bytes,
                    content_base64=base64.b64encode(pdf_bytes).decode(),
                    file_size=len(pdf_bytes),
                )

        except ImportError:
            return ExportResult(
                success=False,
                status=ExportStatus.FAILED,
                format=ExportFormat.PDF,
                error="PDF export requires cairosvg or playwright package",
            )

    async def _export_drawio(
        self, svg_content: str, options: ExportOptions
    ) -> ExportResult:
        """Export to draw.io/diagrams.net XML format."""
        try:
            # Parse SVG to extract structure
            drawio_xml = self._svg_to_drawio(svg_content, options)

            content = drawio_xml.encode("utf-8")

            return ExportResult(
                success=True,
                status=ExportStatus.COMPLETED,
                format=ExportFormat.DRAWIO,
                content=content,
                content_base64=base64.b64encode(content).decode(),
                file_size=len(content),
            )

        except Exception as e:
            logger.error(f"draw.io export failed: {e}")
            return ExportResult(
                success=False,
                status=ExportStatus.FAILED,
                format=ExportFormat.DRAWIO,
                error=str(e),
            )

    def _svg_to_drawio(self, svg_content: str, options: ExportOptions) -> str:
        """Convert SVG diagram to draw.io XML format."""
        try:
            root = SAFE_XML_PARSE(svg_content)

            # Get SVG dimensions
            width = float(root.get("width", "800").rstrip("px"))
            height = float(root.get("height", "600").rstrip("px"))

            # Create draw.io structure
            mxfile = ET.Element("mxfile")
            mxfile.set("host", "app.diagrams.net")
            mxfile.set("modified", datetime.now(timezone.utc).isoformat())
            mxfile.set("agent", "Project Aura Diagram Export")
            mxfile.set("version", "21.0.0")

            diagram = ET.SubElement(mxfile, "diagram")
            diagram.set("name", "Page-1")
            diagram.set("id", str(uuid.uuid4()))

            # Create graph model
            mxGraphModel = ET.SubElement(diagram, "mxGraphModel")
            mxGraphModel.set("dx", "0")
            mxGraphModel.set("dy", "0")
            mxGraphModel.set("grid", "1")
            mxGraphModel.set("gridSize", "10")
            mxGraphModel.set("guides", "1")
            mxGraphModel.set("tooltips", "1")
            mxGraphModel.set("connect", "1")
            mxGraphModel.set("arrows", "1")
            mxGraphModel.set("fold", "1")
            mxGraphModel.set("page", "1")
            mxGraphModel.set("pageScale", "1")
            mxGraphModel.set("pageWidth", str(int(width)))
            mxGraphModel.set("pageHeight", str(int(height)))

            root_cell = ET.SubElement(mxGraphModel, "root")

            # Add default cells
            cell0 = ET.SubElement(root_cell, "mxCell")
            cell0.set("id", "0")

            cell1 = ET.SubElement(root_cell, "mxCell")
            cell1.set("id", "1")
            cell1.set("parent", "0")

            # Extract nodes and edges from SVG
            cell_id = 2
            node_map: dict[str, str] = {}

            # Process rectangles/shapes as nodes
            for rect in root.iter("{http://www.w3.org/2000/svg}rect"):
                node_id = rect.get("data-node-id") or f"node-{cell_id}"
                label = rect.get("data-node-label", "")

                x = float(rect.get("x", "0"))
                y = float(rect.get("y", "0"))
                w = float(rect.get("width", "100"))
                h = float(rect.get("height", "60"))
                fill = rect.get("fill", "#FFFFFF")

                cell = ET.SubElement(root_cell, "mxCell")
                cell.set("id", str(cell_id))
                cell.set("value", label)
                cell.set("style", f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};")
                cell.set("vertex", "1")
                cell.set("parent", "1")

                geometry = ET.SubElement(cell, "mxGeometry")
                geometry.set("x", str(x))
                geometry.set("y", str(y))
                geometry.set("width", str(w))
                geometry.set("height", str(h))
                geometry.set("as", "geometry")

                node_map[node_id] = str(cell_id)
                cell_id += 1

            # Process groups as containers
            for group in root.iter("{http://www.w3.org/2000/svg}g"):
                group_id = group.get("data-group-id")
                if group_id:
                    label = group.get("data-group-label", "")

                    # Calculate bounding box from children
                    cell = ET.SubElement(root_cell, "mxCell")
                    cell.set("id", str(cell_id))
                    cell.set("value", label)
                    cell.set("style", "group;container=1;collapsible=0;")
                    cell.set("vertex", "1")
                    cell.set("parent", "1")

                    geometry = ET.SubElement(cell, "mxGeometry")
                    geometry.set("as", "geometry")

                    node_map[group_id] = str(cell_id)
                    cell_id += 1

            # Process lines/paths as edges
            for line in root.iter("{http://www.w3.org/2000/svg}line"):
                source_id = line.get("data-source")
                target_id = line.get("data-target")

                if source_id and target_id:
                    source_cell = node_map.get(source_id)
                    target_cell = node_map.get(target_id)

                    if source_cell and target_cell:
                        cell = ET.SubElement(root_cell, "mxCell")
                        cell.set("id", str(cell_id))
                        cell.set("value", "")
                        cell.set(
                            "style",
                            "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;",
                        )
                        cell.set("edge", "1")
                        cell.set("parent", "1")
                        cell.set("source", source_cell)
                        cell.set("target", target_cell)

                        geometry = ET.SubElement(cell, "mxGeometry")
                        geometry.set("relative", "1")
                        geometry.set("as", "geometry")

                        cell_id += 1

            # Process paths as edges
            for path in root.iter("{http://www.w3.org/2000/svg}path"):
                source_id = path.get("data-source")
                target_id = path.get("data-target")

                if source_id and target_id:
                    source_cell = node_map.get(source_id)
                    target_cell = node_map.get(target_id)

                    if source_cell and target_cell:
                        cell = ET.SubElement(root_cell, "mxCell")
                        cell.set("id", str(cell_id))
                        cell.set("value", "")
                        cell.set(
                            "style", "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;"
                        )
                        cell.set("edge", "1")
                        cell.set("parent", "1")
                        cell.set("source", source_cell)
                        cell.set("target", target_cell)

                        geometry = ET.SubElement(cell, "mxGeometry")
                        geometry.set("relative", "1")
                        geometry.set("as", "geometry")

                        cell_id += 1

            # Generate XML output
            return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)

        except ET.ParseError as e:
            logger.error(f"Failed to parse SVG for draw.io conversion: {e}")
            # Return minimal valid draw.io file
            return self._create_empty_drawio()

    def _create_empty_drawio(self) -> str:
        """Create minimal empty draw.io file."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" agent="Project Aura">
  <diagram name="Page-1" id="empty">
    <mxGraphModel dx="0" dy="0" grid="1" gridSize="10">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""

    async def _store_in_s3(
        self,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> dict[str, str]:
        """Store export content in S3 and generate presigned URL."""
        try:
            # Generate S3 key
            timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d")
            s3_key = f"exports/{timestamp}/{filename}"

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self._bucket_name,
                Key=s3_key,
                Body=content,
                ContentType=content_type,
                Metadata={
                    "generated-by": "project-aura",
                    "environment": self.environment,
                },
            )

            # Generate presigned URL (1 hour expiration)
            presigned_url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket_name, "Key": s3_key},
                ExpiresIn=3600,
            )

            return {"key": s3_key, "presigned_url": presigned_url}

        except ClientError as e:
            logger.error(f"Failed to store export in S3: {e}")
            return {}

    async def batch_export(
        self,
        svg_content: str,
        formats: list[ExportFormat],
        diagram_id: str | None = None,
        store_in_s3: bool = False,
    ) -> dict[ExportFormat, ExportResult]:
        """
        Export diagram to multiple formats.

        Args:
            svg_content: SVG diagram content
            formats: List of formats to export
            diagram_id: Optional diagram identifier
            store_in_s3: Store results in S3

        Returns:
            Dictionary mapping formats to results
        """
        results = {}
        diagram_id = diagram_id or str(uuid.uuid4())

        for fmt in formats:
            options = ExportOptions(format=fmt)
            result = await self.export_diagram(
                svg_content, options, diagram_id, store_in_s3
            )
            results[fmt] = result

        return results


# Singleton instance
_export_service: DiagramExportService | None = None


def get_diagram_export_service() -> DiagramExportService:
    """Get or create diagram export service singleton."""
    global _export_service
    if _export_service is None:
        _export_service = DiagramExportService()
    return _export_service
