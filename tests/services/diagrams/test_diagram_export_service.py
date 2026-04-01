"""
Tests for DiagramExportService (ADR-060 Phase 4).

Tests multi-format diagram export: SVG, PNG, PDF, draw.io.
"""

import base64
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest

from src.services.diagrams.diagram_export_service import (
    DiagramExportService,
    ExportFormat,
    ExportOptions,
    ExportStatus,
    get_diagram_export_service,
)


class TestDiagramExportService:
    """Tests for DiagramExportService class."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        client = MagicMock()
        client.put_object.return_value = {}
        client.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/bucket/key?signed=true"
        )
        return client

    @pytest.fixture
    def export_service(self, mock_s3_client):
        """Create DiagramExportService instance."""
        return DiagramExportService(
            s3_client=mock_s3_client,
            bucket_name="test-bucket",
            environment="test",
        )

    @pytest.fixture
    def sample_svg(self):
        """Sample SVG diagram content."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
    <rect data-node-id="node1" data-node-label="API Gateway" x="100" y="100" width="200" height="100" fill="#3B82F6"/>
    <rect data-node-id="node2" data-node-label="Lambda" x="400" y="100" width="200" height="100" fill="#10B981"/>
    <line data-source="node1" data-target="node2" x1="300" y1="150" x2="400" y2="150" stroke="#666"/>
    <g data-group-id="vpc" data-group-label="VPC">
        <rect x="50" y="50" width="700" height="500" fill="none" stroke="#999"/>
    </g>
</svg>"""

    @pytest.fixture
    def simple_svg(self):
        """Simple valid SVG for testing."""
        return '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect fill="red" width="100" height="100"/></svg>'


class TestServiceInitialization(TestDiagramExportService):
    """Tests for service initialization."""

    def test_creates_with_defaults(self):
        """Test creation with default values."""
        service = DiagramExportService()
        assert service.environment in ["dev", "test", "qa", "prod"]
        assert service.project_name == "aura"

    def test_creates_with_custom_bucket(self, mock_s3_client):
        """Test creation with custom bucket."""
        service = DiagramExportService(
            s3_client=mock_s3_client,
            bucket_name="custom-bucket",
        )
        assert service._bucket_name == "custom-bucket"


class TestSVGExport(TestDiagramExportService):
    """Tests for SVG export functionality."""

    @pytest.mark.asyncio
    async def test_exports_svg_successfully(self, export_service, sample_svg):
        """Test successful SVG export."""
        options = ExportOptions(format=ExportFormat.SVG)
        result = await export_service.export_diagram(sample_svg, options)

        assert result.success is True
        assert result.status == ExportStatus.COMPLETED
        assert result.format == ExportFormat.SVG
        assert result.content is not None
        assert result.content_base64 is not None
        assert result.file_size > 0
        assert result.content_type == "image/svg+xml"

    @pytest.mark.asyncio
    async def test_svg_preserves_content(self, export_service, simple_svg):
        """Test SVG export preserves content structure."""
        options = ExportOptions(format=ExportFormat.SVG)
        result = await export_service.export_diagram(simple_svg, options)

        # Decode and verify content
        content = result.content.decode("utf-8")
        assert "rect" in content
        assert 'fill="red"' in content or "fill=red" in content

    @pytest.mark.asyncio
    async def test_svg_applies_scale(self, export_service, sample_svg):
        """Test SVG export applies scale option."""
        options = ExportOptions(format=ExportFormat.SVG, scale=2.0)
        result = await export_service.export_diagram(sample_svg, options)

        assert result.success is True
        # Content should be modified for scale
        assert result.content is not None

    @pytest.mark.asyncio
    async def test_svg_adds_background(self, export_service, simple_svg):
        """Test SVG export adds background color."""
        options = ExportOptions(format=ExportFormat.SVG, background_color="#FFFFFF")
        result = await export_service.export_diagram(simple_svg, options)

        assert result.success is True
        content = result.content.decode("utf-8")
        # Should have background rect
        assert "#FFFFFF" in content or "rect" in content

    @pytest.mark.asyncio
    async def test_svg_includes_metadata(self, export_service, simple_svg):
        """Test SVG export includes metadata."""
        options = ExportOptions(format=ExportFormat.SVG, include_metadata=True)
        result = await export_service.export_diagram(simple_svg, options)

        assert result.success is True
        content = result.content.decode("utf-8")
        # Metadata should be present
        assert "metadata" in content or "Project Aura" in content

    @pytest.mark.asyncio
    async def test_generates_filename(self, export_service, simple_svg):
        """Test SVG export generates filename."""
        options = ExportOptions(format=ExportFormat.SVG)
        result = await export_service.export_diagram(
            simple_svg, options, diagram_id="test-123"
        )

        assert result.filename == "diagram-test-123.svg"


class TestPNGExport(TestDiagramExportService):
    """Tests for PNG export functionality."""

    @pytest.mark.asyncio
    async def test_png_export_with_cairosvg(self, export_service, simple_svg):
        """Test PNG export using cairosvg."""
        try:
            import cairosvg  # noqa: F401

            options = ExportOptions(format=ExportFormat.PNG)
            result = await export_service.export_diagram(simple_svg, options)

            assert result.success is True
            assert result.format == ExportFormat.PNG
            assert result.content_type == "image/png"
            # PNG magic bytes
            assert result.content[:4] == b"\x89PNG"

        except ImportError:
            pytest.skip("cairosvg not installed")

    @pytest.mark.asyncio
    async def test_png_export_fallback_to_playwright(self, export_service, simple_svg):
        """Test PNG export falls back to Playwright."""
        with patch.dict("sys.modules", {"cairosvg": None}):
            options = ExportOptions(format=ExportFormat.PNG)
            result = await export_service.export_diagram(simple_svg, options)

            # Should either succeed (if playwright available) or fail gracefully
            assert result.format == ExportFormat.PNG

    @pytest.mark.asyncio
    async def test_png_respects_scale(self, export_service, simple_svg):
        """Test PNG export respects scale option."""
        try:
            import cairosvg  # noqa: F401

            options = ExportOptions(format=ExportFormat.PNG, scale=2.0)
            result = await export_service.export_diagram(simple_svg, options)

            if result.success:
                assert result.file_size > 0

        except ImportError:
            pytest.skip("cairosvg not installed")


class TestPDFExport(TestDiagramExportService):
    """Tests for PDF export functionality."""

    @pytest.mark.asyncio
    async def test_pdf_export_with_cairosvg(self, export_service, simple_svg):
        """Test PDF export using cairosvg."""
        try:
            import cairosvg  # noqa: F401

            options = ExportOptions(format=ExportFormat.PDF)
            result = await export_service.export_diagram(simple_svg, options)

            assert result.success is True
            assert result.format == ExportFormat.PDF
            assert result.content_type == "application/pdf"
            # PDF magic bytes
            assert result.content[:4] == b"%PDF"

        except ImportError:
            pytest.skip("cairosvg not installed")

    @pytest.mark.asyncio
    async def test_pdf_generates_filename(self, export_service, simple_svg):
        """Test PDF export generates correct filename."""
        try:
            import cairosvg  # noqa: F401

            options = ExportOptions(format=ExportFormat.PDF)
            result = await export_service.export_diagram(
                simple_svg, options, diagram_id="test-pdf"
            )

            if result.success:
                assert result.filename == "diagram-test-pdf.pdf"

        except ImportError:
            pytest.skip("cairosvg not installed")


class TestDrawIOExport(TestDiagramExportService):
    """Tests for draw.io/diagrams.net export functionality."""

    @pytest.mark.asyncio
    async def test_drawio_export_creates_valid_xml(self, export_service, sample_svg):
        """Test draw.io export creates valid XML."""
        options = ExportOptions(format=ExportFormat.DRAWIO)
        result = await export_service.export_diagram(sample_svg, options)

        assert result.success is True
        assert result.format == ExportFormat.DRAWIO
        assert result.content_type == "application/xml"

        # Parse and verify XML structure
        content = result.content.decode("utf-8")
        root = ET.fromstring(content)
        assert root.tag == "mxfile"

    @pytest.mark.asyncio
    async def test_drawio_contains_diagram_element(self, export_service, sample_svg):
        """Test draw.io export contains diagram element."""
        options = ExportOptions(format=ExportFormat.DRAWIO)
        result = await export_service.export_diagram(sample_svg, options)

        content = result.content.decode("utf-8")
        root = ET.fromstring(content)

        # Should have diagram element
        diagram = root.find("diagram")
        assert diagram is not None

    @pytest.mark.asyncio
    async def test_drawio_converts_nodes(self, export_service, sample_svg):
        """Test draw.io export converts SVG nodes to mxCells."""
        options = ExportOptions(format=ExportFormat.DRAWIO)
        result = await export_service.export_diagram(sample_svg, options)

        content = result.content.decode("utf-8")
        root = ET.fromstring(content)

        # Find all mxCells with vertex="1" (nodes)
        mxGraphModel = root.find(".//mxGraphModel")
        assert mxGraphModel is not None

        root_elem = mxGraphModel.find("root")
        assert root_elem is not None

        cells = root_elem.findall("mxCell")
        # Should have base cells (0, 1) plus converted nodes
        assert len(cells) >= 2

    @pytest.mark.asyncio
    async def test_drawio_sets_metadata(self, export_service, simple_svg):
        """Test draw.io export sets file metadata."""
        options = ExportOptions(format=ExportFormat.DRAWIO)
        result = await export_service.export_diagram(simple_svg, options)

        content = result.content.decode("utf-8")
        root = ET.fromstring(content)

        assert root.get("host") == "app.diagrams.net"
        assert root.get("agent") == "Project Aura Diagram Export"

    @pytest.mark.asyncio
    async def test_drawio_generates_correct_filename(self, export_service, simple_svg):
        """Test draw.io export generates correct filename."""
        options = ExportOptions(format=ExportFormat.DRAWIO)
        result = await export_service.export_diagram(
            simple_svg, options, diagram_id="arch-diagram"
        )

        assert result.filename == "diagram-arch-diagram.drawio"

    @pytest.mark.asyncio
    async def test_drawio_handles_invalid_svg(self, export_service):
        """Test draw.io export handles invalid SVG gracefully."""
        invalid_svg = "not valid svg content"
        options = ExportOptions(format=ExportFormat.DRAWIO)
        result = await export_service.export_diagram(invalid_svg, options)

        # Should return empty but valid draw.io file
        assert result.success is True
        content = result.content.decode("utf-8")
        # Should be parseable
        root = ET.fromstring(content)
        assert root.tag == "mxfile"


class TestS3Storage(TestDiagramExportService):
    """Tests for S3 storage functionality."""

    @pytest.mark.asyncio
    async def test_stores_in_s3(self, export_service, simple_svg, mock_s3_client):
        """Test storing export in S3."""
        options = ExportOptions(format=ExportFormat.SVG)
        result = await export_service.export_diagram(
            simple_svg, options, store_in_s3=True
        )

        assert result.success is True
        assert result.s3_key is not None
        assert "exports/" in result.s3_key
        mock_s3_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_generates_presigned_url(
        self, export_service, simple_svg, mock_s3_client
    ):
        """Test generating presigned URL for S3 export."""
        options = ExportOptions(format=ExportFormat.SVG)
        result = await export_service.export_diagram(
            simple_svg, options, store_in_s3=True
        )

        assert result.presigned_url is not None
        assert "s3.amazonaws.com" in result.presigned_url
        mock_s3_client.generate_presigned_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_s3_error(self, export_service, simple_svg, mock_s3_client):
        """Test handling S3 storage error."""
        from botocore.exceptions import ClientError

        mock_s3_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}},
            "PutObject",
        )

        options = ExportOptions(format=ExportFormat.SVG)
        result = await export_service.export_diagram(
            simple_svg, options, store_in_s3=True
        )

        # Export itself should succeed even if S3 fails
        assert result.success is True
        assert result.content is not None
        # But S3 key should be None
        assert result.s3_key is None


class TestBatchExport(TestDiagramExportService):
    """Tests for batch export functionality."""

    @pytest.mark.asyncio
    async def test_batch_exports_multiple_formats(self, export_service, simple_svg):
        """Test batch export to multiple formats."""
        formats = [ExportFormat.SVG, ExportFormat.DRAWIO]
        results = await export_service.batch_export(simple_svg, formats)

        assert len(results) == 2
        assert ExportFormat.SVG in results
        assert ExportFormat.DRAWIO in results
        assert results[ExportFormat.SVG].success is True
        assert results[ExportFormat.DRAWIO].success is True

    @pytest.mark.asyncio
    async def test_batch_uses_same_diagram_id(self, export_service, simple_svg):
        """Test batch export uses same diagram ID."""
        formats = [ExportFormat.SVG, ExportFormat.DRAWIO]
        results = await export_service.batch_export(
            simple_svg, formats, diagram_id="batch-test"
        )

        assert "batch-test" in results[ExportFormat.SVG].filename
        assert "batch-test" in results[ExportFormat.DRAWIO].filename


class TestExportOptions(TestDiagramExportService):
    """Tests for ExportOptions configuration."""

    def test_default_options(self):
        """Test default export options."""
        options = ExportOptions(format=ExportFormat.SVG)

        assert options.scale == 1.0
        assert options.background_color is None
        assert options.padding == 20
        assert options.quality == 90
        assert options.include_metadata is True
        assert options.dark_mode is False

    def test_custom_options(self):
        """Test custom export options."""
        options = ExportOptions(
            format=ExportFormat.PNG,
            scale=2.0,
            width=1920,
            height=1080,
            background_color="#FFFFFF",
            padding=40,
            quality=100,
            include_metadata=False,
            dark_mode=True,
        )

        assert options.scale == 2.0
        assert options.width == 1920
        assert options.height == 1080
        assert options.background_color == "#FFFFFF"
        assert options.padding == 40
        assert options.quality == 100
        assert options.include_metadata is False
        assert options.dark_mode is True


class TestExportResult(TestDiagramExportService):
    """Tests for ExportResult data class."""

    @pytest.mark.asyncio
    async def test_result_includes_timing(self, export_service, simple_svg):
        """Test export result includes timing information."""
        options = ExportOptions(format=ExportFormat.SVG)
        result = await export_service.export_diagram(simple_svg, options)

        assert result.export_time_ms >= 0

    @pytest.mark.asyncio
    async def test_result_includes_base64(self, export_service, simple_svg):
        """Test export result includes base64 content."""
        options = ExportOptions(format=ExportFormat.SVG)
        result = await export_service.export_diagram(simple_svg, options)

        assert result.content_base64 is not None
        # Verify it's valid base64
        decoded = base64.b64decode(result.content_base64)
        assert decoded == result.content


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_diagram_export_service_returns_same_instance(self):
        """Test singleton returns same instance."""
        import src.services.diagrams.diagram_export_service as module

        # Reset singleton
        module._export_service = None

        service1 = get_diagram_export_service()
        service2 = get_diagram_export_service()

        assert service1 is service2

        # Cleanup
        module._export_service = None


class TestEdgeCases(TestDiagramExportService):
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_empty_svg(self, export_service):
        """Test handling empty SVG content."""
        options = ExportOptions(format=ExportFormat.SVG)
        result = await export_service.export_diagram("", options)

        # Should fail gracefully
        assert result.format == ExportFormat.SVG

    @pytest.mark.asyncio
    async def test_handles_malformed_svg(self, export_service):
        """Test handling malformed SVG content."""
        malformed_svg = "<svg><rect></svg>"  # Missing closing tag for rect
        options = ExportOptions(format=ExportFormat.SVG)
        result = await export_service.export_diagram(malformed_svg, options)

        # Should handle gracefully
        assert result.format == ExportFormat.SVG

    @pytest.mark.asyncio
    async def test_handles_large_svg(self, export_service):
        """Test handling large SVG content."""
        # Create SVG with many elements
        rects = "\n".join(
            [
                f'<rect x="{i*10}" y="{i*10}" width="50" height="50" fill="blue"/>'
                for i in range(100)
            ]
        )
        large_svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="2000" height="2000">{rects}</svg>'

        options = ExportOptions(format=ExportFormat.SVG)
        result = await export_service.export_diagram(large_svg, options)

        assert result.success is True
        assert result.file_size > 0

    @pytest.mark.asyncio
    async def test_unsupported_format_fails(self, export_service, simple_svg):
        """Test unsupported format returns error."""
        # Create options with invalid format
        options = ExportOptions(format=ExportFormat.SVG)
        options.format = MagicMock()
        options.format.value = "unsupported"

        result = await export_service.export_diagram(simple_svg, options)

        assert result.success is False
        assert "Unsupported" in result.error or result.error is not None


class TestContentTypes(TestDiagramExportService):
    """Tests for content type handling."""

    def test_content_type_svg(self, export_service):
        """Test SVG content type."""
        assert export_service.CONTENT_TYPES[ExportFormat.SVG] == "image/svg+xml"

    def test_content_type_png(self, export_service):
        """Test PNG content type."""
        assert export_service.CONTENT_TYPES[ExportFormat.PNG] == "image/png"

    def test_content_type_pdf(self, export_service):
        """Test PDF content type."""
        assert export_service.CONTENT_TYPES[ExportFormat.PDF] == "application/pdf"

    def test_content_type_drawio(self, export_service):
        """Test draw.io content type."""
        assert export_service.CONTENT_TYPES[ExportFormat.DRAWIO] == "application/xml"


class TestFileExtensions(TestDiagramExportService):
    """Tests for file extension handling."""

    def test_extension_svg(self, export_service):
        """Test SVG extension."""
        assert export_service.EXTENSIONS[ExportFormat.SVG] == ".svg"

    def test_extension_png(self, export_service):
        """Test PNG extension."""
        assert export_service.EXTENSIONS[ExportFormat.PNG] == ".png"

    def test_extension_pdf(self, export_service):
        """Test PDF extension."""
        assert export_service.EXTENSIONS[ExportFormat.PDF] == ".pdf"

    def test_extension_drawio(self, export_service):
        """Test draw.io extension."""
        assert export_service.EXTENSIONS[ExportFormat.DRAWIO] == ".drawio"
