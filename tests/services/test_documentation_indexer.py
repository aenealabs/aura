"""
Project Aura - Documentation Indexer Service Tests

Comprehensive tests for the DocumentationIndexer service including:
- Document parsing
- Document classification
- Search functionality
- Index operations

Target: 85% coverage of src/services/documentation_indexer.py
"""

# ruff: noqa: PLR2004

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.documentation_indexer import (
    DOCUMENTATION_INDEX_MAPPING,
    DOCUMENTATION_INDEX_NAME,
    DocumentationCategory,
    DocumentationIndexer,
    DocumentationType,
    ParsedDocument,
    SearchResult,
    create_documentation_indexer,
)


class TestDocumentationIndexerInitialization:
    """Tests for DocumentationIndexer initialization."""

    def test_initialization_default_config(self):
        """Test indexer initialization with default configuration."""
        indexer = DocumentationIndexer()

        assert indexer.index_name == DOCUMENTATION_INDEX_NAME
        assert indexer.vector_dimension == 1536
        assert indexer.embedding_model_id == "amazon.titan-embed-text-v2:0"
        assert indexer._initialized is False
        assert indexer._opensearch_client is None
        assert indexer._bedrock_client is None

    def test_initialization_custom_config(self):
        """Test indexer initialization with custom configuration."""
        indexer = DocumentationIndexer(
            index_name="custom-docs",
            vector_dimension=1024,
            embedding_model_id="custom-model",
            opensearch_endpoint="custom.opensearch.local",
        )

        assert indexer.index_name == "custom-docs"
        assert indexer.vector_dimension == 1024
        assert indexer.embedding_model_id == "custom-model"
        assert indexer.opensearch_endpoint == "custom.opensearch.local"

    @pytest.mark.asyncio
    async def test_initialize_without_aws_services(self):
        """Test initialization when AWS services are not available."""
        indexer = DocumentationIndexer()

        # Should succeed even without real AWS connections
        result = await indexer.initialize()

        # Initialization returns True (services are optional)
        assert result is True
        assert indexer._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_with_mock_opensearch(self):
        """Test initialization with mocked OpenSearch client."""
        indexer = DocumentationIndexer()

        with (
            patch(
                "src.services.documentation_indexer.DocumentationIndexer._init_opensearch_client"
            ) as mock_os,
            patch(
                "src.services.documentation_indexer.DocumentationIndexer._init_bedrock_client"
            ) as mock_br,
        ):
            result = await indexer.initialize()

            assert result is True
            mock_os.assert_called_once()
            mock_br.assert_called_once()


class TestDocumentParsing:
    """Tests for markdown document parsing."""

    def test_parse_markdown_basic(self):
        """Test parsing a basic markdown file."""
        indexer = DocumentationIndexer()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""# Test Document

This is a test document with some content.

## Section One

Some content in section one.

## Section Two

More content here.

```python
def example():
    return "hello"
```
""")
            f.flush()
            file_path = Path(f.name)

        try:
            doc = indexer.parse_markdown(file_path)

            assert doc is not None
            assert doc.title == "Test Document"
            assert "test document" in doc.content.lower()
            assert len(doc.headers) == 3  # Including title
            assert "Test Document" in doc.headers
            assert "Section One" in doc.headers
            assert len(doc.code_blocks) == 1
            assert "def example():" in doc.code_blocks[0]
        finally:
            file_path.unlink()

    def test_parse_markdown_with_frontmatter(self):
        """Test parsing markdown with YAML frontmatter."""
        indexer = DocumentationIndexer()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
title: "Document with Frontmatter"
version: "1.0"
---

# Another Title

Content after frontmatter.
""")
            f.flush()
            file_path = Path(f.name)

        try:
            doc = indexer.parse_markdown(file_path)

            assert doc is not None
            # Should extract title from frontmatter or H1
            assert "title" in doc.title.lower() or "frontmatter" in doc.title.lower()
        finally:
            file_path.unlink()

    def test_parse_markdown_no_h1(self):
        """Test parsing markdown without H1 header (uses filename)."""
        indexer = DocumentationIndexer()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, prefix="test-document-"
        ) as f:
            f.write("""## Only H2 Header

Some content without H1.
""")
            f.flush()
            file_path = Path(f.name)

        try:
            doc = indexer.parse_markdown(file_path)

            assert doc is not None
            # Title should be derived from filename
            assert "test" in doc.title.lower() or "document" in doc.title.lower()
        finally:
            file_path.unlink()

    def test_parse_markdown_extract_summary(self):
        """Test that summary is extracted correctly."""
        indexer = DocumentationIndexer()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""# Document Title

**Version:** 1.0
**Last Updated:** January 2026

This is the first paragraph that should become the summary.
It can span multiple lines.

## Next Section

More content here.
""")
            f.flush()
            file_path = Path(f.name)

        try:
            doc = indexer.parse_markdown(file_path)

            assert doc is not None
            assert "first paragraph" in doc.summary.lower()
            # Version/date lines should not be in summary
            assert "Version:" not in doc.summary
        finally:
            file_path.unlink()

    def test_parse_markdown_invalid_file(self):
        """Test parsing non-existent file returns None."""
        indexer = DocumentationIndexer()

        doc = indexer.parse_markdown(Path("/nonexistent/file.md"))

        assert doc is None

    def test_extract_code_blocks(self):
        """Test extraction of code blocks."""
        indexer = DocumentationIndexer()

        content = """
Some text.

```python
def foo():
    pass
```

More text.

```bash
echo "hello"
```

End.
"""
        code_blocks = indexer._extract_code_blocks(content)

        assert len(code_blocks) == 2
        assert "def foo():" in code_blocks[0]
        assert 'echo "hello"' in code_blocks[1]

    def test_extract_headers(self):
        """Test extraction of headers."""
        indexer = DocumentationIndexer()

        content = """
# Main Title

## Section 1

### Subsection 1.1

## Section 2

#### Deep Section
"""
        headers = indexer._extract_headers(content)

        assert len(headers) == 5
        assert "Main Title" in headers
        assert "Section 1" in headers
        assert "Subsection 1.1" in headers

    def test_clean_content(self):
        """Test content cleaning for indexing."""
        indexer = DocumentationIndexer()

        content = """---
title: Test
---

# Title

**Bold text** and *italic text*.

[Link text](http://example.com)

![Image](image.png)

```python
code
```

---

Normal text.
"""
        cleaned = indexer._clean_content(content)

        # Frontmatter removed
        assert "title: Test" not in cleaned
        # Markdown formatting removed
        assert "**" not in cleaned
        assert "*" not in cleaned
        # Links simplified
        assert "Link text" in cleaned
        assert "http://example.com" not in cleaned
        # Code block markers removed
        assert "```" not in cleaned
        # Normal content preserved
        assert "Normal text" in cleaned


class TestDocumentClassification:
    """Tests for document type and category classification."""

    def test_classify_doc_type_product(self):
        """Test classification of product documentation."""
        indexer = DocumentationIndexer()

        path = Path("docs/product/getting-started/quick-start.md")
        doc_type = indexer._classify_doc_type(path)

        assert doc_type == DocumentationType.PRODUCT.value

    def test_classify_doc_type_support(self):
        """Test classification of support documentation."""
        indexer = DocumentationIndexer()

        path = Path("docs/support/troubleshooting/common-issues.md")
        doc_type = indexer._classify_doc_type(path)

        assert doc_type == DocumentationType.SUPPORT.value

    def test_classify_doc_type_adr(self):
        """Test classification of ADR documentation."""
        indexer = DocumentationIndexer()

        path = Path("docs/architecture-decisions/ADR-001-example.md")
        doc_type = indexer._classify_doc_type(path)

        assert doc_type == DocumentationType.ADR.value

    def test_classify_doc_type_runbook(self):
        """Test classification of runbook documentation."""
        indexer = DocumentationIndexer()

        path = Path("docs/runbooks/DEPLOYMENT_RUNBOOK.md")
        doc_type = indexer._classify_doc_type(path)

        assert doc_type == DocumentationType.RUNBOOK.value

    def test_classify_doc_type_api(self):
        """Test classification of API documentation."""
        indexer = DocumentationIndexer()

        # Note: /support/ path takes precedence over /api-reference/ in classification
        # Use a path that doesn't have /support/ to test API classification
        path = Path("docs/api-reference/rest-api.md")
        doc_type = indexer._classify_doc_type(path)

        assert doc_type == DocumentationType.API.value

    def test_classify_doc_type_support_api_reference(self):
        """Test that /support/api-reference/ is classified as support (not api)."""
        indexer = DocumentationIndexer()

        # Support type takes precedence in path matching order
        path = Path("docs/support/api-reference/rest-api.md")
        doc_type = indexer._classify_doc_type(path)

        assert doc_type == DocumentationType.SUPPORT.value

    def test_classify_doc_type_guide_default(self):
        """Test default classification as guide."""
        indexer = DocumentationIndexer()

        path = Path("docs/some/unknown/document.md")
        doc_type = indexer._classify_doc_type(path)

        assert doc_type == DocumentationType.GUIDE.value

    def test_classify_category_getting_started(self):
        """Test classification of getting-started category."""
        indexer = DocumentationIndexer()

        path = Path("docs/product/getting-started/installation.md")
        category = indexer._classify_category(path)

        assert category == DocumentationCategory.GETTING_STARTED.value

    def test_classify_category_troubleshooting(self):
        """Test classification of troubleshooting category."""
        indexer = DocumentationIndexer()

        path = Path("docs/support/troubleshooting/common-issues.md")
        category = indexer._classify_category(path)

        assert category == DocumentationCategory.TROUBLESHOOTING.value

    def test_classify_category_api_reference(self):
        """Test classification of api-reference category."""
        indexer = DocumentationIndexer()

        path = Path("docs/support/api-reference/endpoints.md")
        category = indexer._classify_category(path)

        assert category == DocumentationCategory.API_REFERENCE.value

    def test_classify_category_architecture(self):
        """Test classification of architecture category."""
        indexer = DocumentationIndexer()

        path = Path("docs/support/architecture/overview.md")
        category = indexer._classify_category(path)

        assert category == DocumentationCategory.ARCHITECTURE.value

    def test_classify_category_general_default(self):
        """Test default classification as general."""
        indexer = DocumentationIndexer()

        path = Path("docs/misc/random-doc.md")
        category = indexer._classify_category(path)

        assert category == DocumentationCategory.GENERAL.value


class TestDocumentIdGeneration:
    """Tests for document ID generation."""

    def test_generate_doc_id_consistent(self):
        """Test that doc ID is consistent for same path."""
        indexer = DocumentationIndexer()

        path = Path("docs/test/document.md")
        id1 = indexer._generate_doc_id(path)
        id2 = indexer._generate_doc_id(path)

        assert id1 == id2
        assert id1.startswith("doc_")

    def test_generate_doc_id_unique(self):
        """Test that different paths generate different IDs."""
        indexer = DocumentationIndexer()

        id1 = indexer._generate_doc_id(Path("docs/test/doc1.md"))
        id2 = indexer._generate_doc_id(Path("docs/test/doc2.md"))

        assert id1 != id2


class TestEmbeddingGeneration:
    """Tests for embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_embedding_mock(self):
        """Test embedding generation without Bedrock (mock mode)."""
        indexer = DocumentationIndexer()
        # Bedrock client is None, so should return mock embedding
        indexer._bedrock_client = None

        embedding = await indexer.generate_embedding("test text")

        assert len(embedding) == 1536
        assert all(v == 0.1 for v in embedding)

    @pytest.mark.asyncio
    async def test_generate_embedding_with_bedrock(self):
        """Test embedding generation with mocked Bedrock client."""
        indexer = DocumentationIndexer()

        mock_response = {
            "body": MagicMock(read=lambda: b'{"embedding": [0.1, 0.2, 0.3]}')
        }
        mock_client = MagicMock()
        mock_client.invoke_model.return_value = mock_response
        indexer._bedrock_client = mock_client

        embedding = await indexer.generate_embedding("test text")

        # Should get the embedding from Bedrock response
        assert embedding == [0.1, 0.2, 0.3]
        mock_client.invoke_model.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_truncates_long_text(self):
        """Test that long text is truncated for embedding."""
        indexer = DocumentationIndexer()

        mock_response = {
            "body": MagicMock(
                read=lambda: b'{"embedding": [0.1] * 1536}'.replace(
                    b"[0.1] * 1536", b"[" + b",".join([b"0.1"] * 1536) + b"]"
                )
            )
        }
        mock_client = MagicMock()
        mock_client.invoke_model.return_value = mock_response
        indexer._bedrock_client = mock_client

        long_text = "a" * 50000  # Very long text
        await indexer.generate_embedding(long_text)

        # Verify the text was truncated in the call
        call_args = mock_client.invoke_model.call_args
        body = json.loads(call_args[1]["body"])
        assert len(body["inputText"]) <= 25000

    @pytest.mark.asyncio
    async def test_generate_embedding_error_fallback(self):
        """Test embedding generation fallback on error."""
        indexer = DocumentationIndexer()

        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = Exception("Bedrock error")
        indexer._bedrock_client = mock_client

        embedding = await indexer.generate_embedding("test text")

        # Should fallback to mock embedding
        assert len(embedding) == 1536
        assert all(v == 0.1 for v in embedding)


class TestDocumentIndexing:
    """Tests for document indexing operations."""

    @pytest.mark.asyncio
    async def test_index_document_mock_mode(self):
        """Test indexing a document in mock mode."""
        indexer = DocumentationIndexer()
        indexer._opensearch_client = None  # Mock mode

        doc = ParsedDocument(
            doc_id="test_doc_123",
            title="Test Document",
            content="Test content for indexing.",
            summary="A test document.",
            doc_type="guide",
            category="general",
            path="docs/test.md",
            headers=["Test Document", "Section 1"],
            code_blocks=[],
            last_modified=datetime.now(timezone.utc),
            word_count=5,
        )

        result = await indexer.index_document(doc)

        assert result is True
        assert "test_doc_123" in indexer._indexed_docs

    @pytest.mark.asyncio
    async def test_index_document_with_opensearch(self):
        """Test indexing a document with mocked OpenSearch."""
        indexer = DocumentationIndexer()

        mock_client = MagicMock()
        indexer._opensearch_client = mock_client
        indexer._bedrock_client = None  # Use mock embeddings

        doc = ParsedDocument(
            doc_id="os_doc_456",
            title="OpenSearch Test",
            content="Content for OpenSearch.",
            summary="Testing OpenSearch indexing.",
            doc_type="product",
            category="core-concepts",
            path="docs/product/test.md",
            headers=["OpenSearch Test"],
            code_blocks=[],
            last_modified=datetime.now(timezone.utc),
            word_count=3,
        )

        result = await indexer.index_document(doc)

        assert result is True
        mock_client.index.assert_called_once()

        # Verify indexed data
        call_args = mock_client.index.call_args
        assert call_args[1]["index"] == indexer.index_name
        assert call_args[1]["id"] == "os_doc_456"
        body = call_args[1]["body"]
        assert body["title"] == "OpenSearch Test"
        assert body["doc_type"] == "product"
        assert "embedding" in body

    @pytest.mark.asyncio
    async def test_index_document_error_handling(self):
        """Test indexing error handling."""
        indexer = DocumentationIndexer()

        mock_client = MagicMock()
        mock_client.index.side_effect = Exception("Index error")
        indexer._opensearch_client = mock_client
        indexer._bedrock_client = None

        doc = ParsedDocument(
            doc_id="error_doc",
            title="Error Test",
            content="Content.",
            summary="Summary.",
            doc_type="guide",
            category="general",
            path="docs/error.md",
            headers=[],
            code_blocks=[],
            last_modified=datetime.now(timezone.utc),
            word_count=1,
        )

        result = await indexer.index_document(doc)

        assert result is False


class TestDocumentationIndexing:
    """Tests for bulk documentation indexing."""

    @pytest.mark.asyncio
    async def test_index_documentation_directory(self):
        """Test indexing all markdown files in a directory."""
        indexer = DocumentationIndexer()
        indexer._opensearch_client = None  # Mock mode

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test markdown files
            doc1 = Path(tmpdir) / "doc1.md"
            doc1.write_text("# Document 1\n\nContent one.")

            doc2 = Path(tmpdir) / "doc2.md"
            doc2.write_text("# Document 2\n\nContent two.")

            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            doc3 = subdir / "doc3.md"
            doc3.write_text("# Document 3\n\nContent three.")

            stats = await indexer.index_documentation(tmpdir)

            assert stats["success"] is True
            assert stats["total_files"] == 3
            assert stats["indexed"] == 3
            assert stats["failed"] == 0

    @pytest.mark.asyncio
    async def test_index_documentation_nonexistent_path(self):
        """Test indexing from non-existent path."""
        indexer = DocumentationIndexer()

        stats = await indexer.index_documentation("/nonexistent/path")

        assert stats["success"] is False
        assert "error" in stats

    @pytest.mark.asyncio
    async def test_index_documentation_incremental(self):
        """Test incremental indexing skips unchanged files."""
        indexer = DocumentationIndexer()
        indexer._opensearch_client = None

        with tempfile.TemporaryDirectory() as tmpdir:
            doc = Path(tmpdir) / "doc.md"
            doc.write_text("# Test\n\nContent.")

            # First indexing
            stats1 = await indexer.index_documentation(tmpdir)
            assert stats1["indexed"] == 1

            # Second indexing should skip the file
            stats2 = await indexer.index_documentation(tmpdir, incremental=True)
            assert stats2["skipped"] >= 1

    @pytest.mark.asyncio
    async def test_index_documentation_skips_small_index_files(self):
        """Test that small index.md files are skipped."""
        indexer = DocumentationIndexer()
        indexer._opensearch_client = None

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create small index.md (navigation only)
            index_file = Path(tmpdir) / "index.md"
            index_file.write_text("# Index\n\n- [Link](doc.md)")

            # Create regular doc
            doc = Path(tmpdir) / "doc.md"
            doc.write_text("# Document\n\nThis is a real document with content.")

            stats = await indexer.index_documentation(tmpdir)

            assert stats["skipped"] == 1  # index.md skipped
            assert stats["indexed"] == 1  # doc.md indexed


class TestDocumentSearch:
    """Tests for document search functionality."""

    @pytest.mark.asyncio
    async def test_search_mock_mode(self):
        """Test search in mock mode."""
        indexer = DocumentationIndexer()
        indexer._opensearch_client = None  # Mock mode

        results = await indexer.search("GraphRAG")

        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)
        # Mock results should include GraphRAG doc
        assert any("graphrag" in r.title.lower() for r in results)

    @pytest.mark.asyncio
    async def test_search_with_doc_type_filter(self):
        """Test search with document type filter."""
        indexer = DocumentationIndexer()
        indexer._opensearch_client = None

        results = await indexer.search("issues", doc_type="support")

        assert len(results) > 0
        # Should only return support docs
        for result in results:
            assert result.doc_type == "support" or "support" in result.path.lower()

    @pytest.mark.asyncio
    async def test_search_respects_limit(self):
        """Test that search respects limit parameter."""
        indexer = DocumentationIndexer()
        indexer._opensearch_client = None

        results = await indexer.search("", limit=2)

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_hybrid_search_with_opensearch(self):
        """Test hybrid search with mocked OpenSearch."""
        indexer = DocumentationIndexer()

        mock_response = {
            "hits": {
                "hits": [
                    {
                        "_id": "doc1",
                        "_score": 0.95,
                        "_source": {
                            "doc_id": "doc1",
                            "title": "Test Result",
                            "path": "docs/test.md",
                            "doc_type": "guide",
                            "category": "general",
                            "summary": "A test result.",
                        },
                    }
                ]
            }
        }

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        indexer._opensearch_client = mock_client
        indexer._bedrock_client = None

        results = await indexer.search("test query", use_hybrid=True)

        assert len(results) == 1
        assert results[0].title == "Test Result"
        assert results[0].score == 0.95
        mock_client.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_text_search_with_opensearch(self):
        """Test text-only search with mocked OpenSearch."""
        indexer = DocumentationIndexer()

        mock_response = {
            "hits": {
                "hits": [
                    {
                        "_id": "doc2",
                        "_score": 0.85,
                        "_source": {
                            "doc_id": "doc2",
                            "title": "Text Search Result",
                            "path": "docs/text.md",
                            "doc_type": "product",
                            "category": "core-concepts",
                            "summary": "Text search test.",
                        },
                        "highlight": {
                            "content": ["matched <em>text</em> here"],
                        },
                    }
                ]
            }
        }

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        indexer._opensearch_client = mock_client

        results = await indexer.search("text search", use_hybrid=False)

        assert len(results) == 1
        assert results[0].title == "Text Search Result"
        assert len(results[0].highlights) == 1
        assert "matched" in results[0].highlights[0]

    @pytest.mark.asyncio
    async def test_search_error_handling(self):
        """Test search error handling returns empty list."""
        indexer = DocumentationIndexer()

        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("Search error")
        indexer._opensearch_client = mock_client

        results = await indexer.search("test")

        assert results == []


class TestIndexManagement:
    """Tests for index management operations."""

    @pytest.mark.asyncio
    async def test_create_index_mock_mode(self):
        """Test creating index in mock mode."""
        indexer = DocumentationIndexer()
        indexer._opensearch_client = None

        result = await indexer.create_index()

        assert result is True

    @pytest.mark.asyncio
    async def test_create_index_already_exists(self):
        """Test creating index when it already exists."""
        indexer = DocumentationIndexer()

        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True
        indexer._opensearch_client = mock_client

        result = await indexer.create_index()

        assert result is True
        mock_client.indices.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_index_new(self):
        """Test creating a new index."""
        indexer = DocumentationIndexer()

        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False
        indexer._opensearch_client = mock_client

        result = await indexer.create_index()

        assert result is True
        mock_client.indices.create.assert_called_once()

        # Verify mapping was used
        call_args = mock_client.indices.create.call_args
        assert call_args[1]["index"] == indexer.index_name
        assert "mappings" in call_args[1]["body"]

    @pytest.mark.asyncio
    async def test_create_index_error(self):
        """Test create index error handling."""
        indexer = DocumentationIndexer()

        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False
        mock_client.indices.create.side_effect = Exception("Create failed")
        indexer._opensearch_client = mock_client

        result = await indexer.create_index()

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_document(self):
        """Test deleting a document."""
        indexer = DocumentationIndexer()
        indexer._indexed_docs["doc_to_delete"] = datetime.now(timezone.utc)

        mock_client = MagicMock()
        indexer._opensearch_client = mock_client

        result = await indexer.delete_document("doc_to_delete")

        assert result is True
        assert "doc_to_delete" not in indexer._indexed_docs
        mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_document_error(self):
        """Test delete document error handling."""
        indexer = DocumentationIndexer()

        mock_client = MagicMock()
        mock_client.delete.side_effect = Exception("Delete failed")
        indexer._opensearch_client = mock_client

        result = await indexer.delete_document("doc_id")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_document(self):
        """Test getting a document by ID."""
        indexer = DocumentationIndexer()

        mock_response = {
            "found": True,
            "_source": {
                "title": "Retrieved Doc",
                "content": "Document content.",
            },
        }
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        indexer._opensearch_client = mock_client

        doc = await indexer.get_document("doc_id")

        assert doc is not None
        assert doc["title"] == "Retrieved Doc"

    @pytest.mark.asyncio
    async def test_get_document_not_found(self):
        """Test getting a non-existent document."""
        indexer = DocumentationIndexer()

        mock_response = {"found": False}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        indexer._opensearch_client = mock_client

        doc = await indexer.get_document("nonexistent")

        assert doc is None

    @pytest.mark.asyncio
    async def test_get_index_stats_mock_mode(self):
        """Test getting index stats in mock mode."""
        indexer = DocumentationIndexer()
        indexer._opensearch_client = None
        indexer._indexed_docs = {"doc1": datetime.now(timezone.utc)}

        stats = await indexer.get_index_stats()

        assert stats["doc_count"] == 1
        assert stats["mode"] == "mock"

    @pytest.mark.asyncio
    async def test_get_index_stats_with_opensearch(self):
        """Test getting index stats from OpenSearch."""
        indexer = DocumentationIndexer()

        mock_response = {
            "indices": {
                indexer.index_name: {
                    "total": {
                        "docs": {"count": 100},
                        "store": {"size_in_bytes": 1024000},
                    }
                }
            }
        }
        mock_client = MagicMock()
        mock_client.indices.stats.return_value = mock_response
        indexer._opensearch_client = mock_client

        stats = await indexer.get_index_stats()

        assert stats["doc_count"] == 100
        assert stats["size_bytes"] == 1024000
        assert stats["mode"] == "aws"


class TestFactoryFunction:
    """Tests for the create_documentation_indexer factory function."""

    def test_create_documentation_indexer_default(self):
        """Test factory function with default configuration."""
        indexer = create_documentation_indexer()

        assert isinstance(indexer, DocumentationIndexer)
        assert indexer.index_name == DOCUMENTATION_INDEX_NAME

    def test_create_documentation_indexer_with_env_vars(self):
        """Test factory function uses environment variables."""
        original_env = os.environ.copy()

        try:
            os.environ["DOCUMENTATION_INDEX_NAME"] = "env-test-index"
            os.environ["EMBEDDING_MODEL_ID"] = "env-test-model"

            indexer = create_documentation_indexer()

            assert indexer.index_name == "env-test-index"
            assert indexer.embedding_model_id == "env-test-model"
        finally:
            os.environ.clear()
            os.environ.update(original_env)


class TestIndexMapping:
    """Tests for index mapping configuration."""

    def test_documentation_index_mapping_structure(self):
        """Test that index mapping has required fields."""
        mapping = DOCUMENTATION_INDEX_MAPPING

        assert "settings" in mapping
        assert "mappings" in mapping

        properties = mapping["mappings"]["properties"]

        # Verify all required fields exist
        required_fields = [
            "doc_id",
            "title",
            "content",
            "summary",
            "doc_type",
            "category",
            "path",
            "headers",
            "last_modified",
            "word_count",
            "embedding",
        ]

        for field in required_fields:
            assert field in properties, f"Missing field: {field}"

        # Verify embedding configuration
        assert properties["embedding"]["type"] == "knn_vector"
        assert properties["embedding"]["dimension"] == 1536

    def test_documentation_index_mapping_knn_enabled(self):
        """Test that k-NN is enabled in index settings."""
        mapping = DOCUMENTATION_INDEX_MAPPING

        assert mapping["settings"]["index"]["knn"] is True


class TestDocumentationEnums:
    """Tests for documentation type and category enums."""

    def test_documentation_type_values(self):
        """Test DocumentationType enum values."""
        assert DocumentationType.PRODUCT.value == "product"
        assert DocumentationType.SUPPORT.value == "support"
        assert DocumentationType.ADR.value == "adr"
        assert DocumentationType.GUIDE.value == "guide"
        assert DocumentationType.RUNBOOK.value == "runbook"
        assert DocumentationType.API.value == "api"

    def test_documentation_category_values(self):
        """Test DocumentationCategory enum values."""
        assert DocumentationCategory.GETTING_STARTED.value == "getting-started"
        assert DocumentationCategory.CORE_CONCEPTS.value == "core-concepts"
        assert DocumentationCategory.TROUBLESHOOTING.value == "troubleshooting"
        assert DocumentationCategory.API_REFERENCE.value == "api-reference"
        assert DocumentationCategory.ARCHITECTURE.value == "architecture"
        assert DocumentationCategory.OPERATIONS.value == "operations"


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_search_result_creation(self):
        """Test creating a SearchResult."""
        result = SearchResult(
            doc_id="test_id",
            title="Test Title",
            path="docs/test.md",
            doc_type="guide",
            category="general",
            summary="Test summary.",
            score=0.85,
            highlights=["matched text"],
        )

        assert result.doc_id == "test_id"
        assert result.title == "Test Title"
        assert result.score == 0.85
        assert len(result.highlights) == 1

    def test_search_result_defaults(self):
        """Test SearchResult default values."""
        result = SearchResult(
            doc_id="id",
            title="Title",
            path="path",
            doc_type="type",
            category="cat",
            summary="sum",
            score=0.5,
        )

        assert result.highlights == []
        assert result.metadata == {}


class TestParsedDocument:
    """Tests for ParsedDocument dataclass."""

    def test_parsed_document_creation(self):
        """Test creating a ParsedDocument."""
        doc = ParsedDocument(
            doc_id="doc_123",
            title="Parsed Doc",
            content="Full content here.",
            summary="Summary text.",
            doc_type="product",
            category="core-concepts",
            path="docs/product/doc.md",
            headers=["Header 1", "Header 2"],
            code_blocks=["code block 1"],
            last_modified=datetime.now(timezone.utc),
            word_count=3,
        )

        assert doc.doc_id == "doc_123"
        assert doc.title == "Parsed Doc"
        assert len(doc.headers) == 2
        assert doc.word_count == 3

    def test_parsed_document_defaults(self):
        """Test ParsedDocument default metadata."""
        doc = ParsedDocument(
            doc_id="id",
            title="t",
            content="c",
            summary="s",
            doc_type="d",
            category="c",
            path="p",
            headers=[],
            code_blocks=[],
            last_modified=datetime.now(timezone.utc),
            word_count=1,
        )

        assert doc.metadata == {}
