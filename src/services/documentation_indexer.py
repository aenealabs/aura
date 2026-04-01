"""
Project Aura - Documentation Indexer Service

Service to parse, index, and search markdown documentation for the chat assistant.
Supports hybrid search (text + vector) with document classification by type and category.

Usage:
    >>> indexer = DocumentationIndexer()
    >>> await indexer.initialize()
    >>> await indexer.index_documentation("/path/to/docs")
    >>> results = await indexer.search("how to configure HITL", doc_type="product")

Index Setup (Run once to create the documentation index):
    >>> indexer = DocumentationIndexer()
    >>> await indexer.initialize()
    >>> await indexer.create_index()  # Creates OpenSearch index with correct mapping
    >>> await indexer.index_documentation("/path/to/docs/product")
    >>> await indexer.index_documentation("/path/to/docs/support")
"""

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DocumentationType(Enum):
    """Types of documentation."""

    PRODUCT = "product"
    SUPPORT = "support"
    ADR = "adr"
    GUIDE = "guide"
    RUNBOOK = "runbook"
    API = "api"
    REFERENCE = "reference"
    INTERNAL = "internal"


class DocumentationCategory(Enum):
    """Categories of documentation based on directory structure."""

    GETTING_STARTED = "getting-started"
    CORE_CONCEPTS = "core-concepts"
    TROUBLESHOOTING = "troubleshooting"
    API_REFERENCE = "api-reference"
    ARCHITECTURE = "architecture"
    OPERATIONS = "operations"
    DEPLOYMENT = "deployment"
    SECURITY = "security"
    DESIGN = "design"
    RESEARCH = "research"
    GENERAL = "general"


@dataclass
class ParsedDocument:
    """Represents a parsed markdown document."""

    doc_id: str
    title: str
    content: str
    summary: str
    doc_type: str
    category: str
    path: str
    headers: list[str]
    code_blocks: list[str]
    last_modified: datetime
    word_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Represents a search result."""

    doc_id: str
    title: str
    path: str
    doc_type: str
    category: str
    summary: str
    score: float
    highlights: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# OpenSearch index mapping for documentation
DOCUMENTATION_INDEX_NAME = "aura-documentation"
DOCUMENTATION_INDEX_MAPPING = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 512,
            "number_of_shards": 1,
            "number_of_replicas": 1,
        }
    },
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "standard"},
            "content": {"type": "text", "analyzer": "standard"},
            "summary": {"type": "text"},
            "doc_type": {"type": "keyword"},
            "category": {"type": "keyword"},
            "path": {"type": "keyword"},
            "headers": {"type": "text"},
            "last_modified": {"type": "date"},
            "word_count": {"type": "integer"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib",
                    "parameters": {"ef_construction": 512, "m": 16},
                },
            },
        }
    },
}


class DocumentationIndexer:
    """
    Service to parse, index, and search documentation.

    Features:
    - Parse markdown files with header extraction
    - Classify documents by type (product, support, adr, etc.)
    - Classify documents by category (getting-started, troubleshooting, etc.)
    - Generate embeddings for semantic search
    - Support hybrid search (text + vector)
    - Incremental updates based on file modification time

    Attributes:
        index_name: Name of the OpenSearch index
        vector_dimension: Dimension of embedding vectors
        embedding_model_id: Model ID for generating embeddings
    """

    def __init__(
        self,
        index_name: str = DOCUMENTATION_INDEX_NAME,
        vector_dimension: int = 1536,
        embedding_model_id: str = "amazon.titan-embed-text-v2:0",
        opensearch_endpoint: str | None = None,
    ):
        """
        Initialize the documentation indexer.

        Args:
            index_name: Name of the OpenSearch index for documentation
            vector_dimension: Dimension of embedding vectors (1536 for Titan v2)
            embedding_model_id: Bedrock model ID for embeddings
            opensearch_endpoint: Optional OpenSearch endpoint override
        """
        self.index_name = index_name
        self.vector_dimension = vector_dimension
        self.embedding_model_id = embedding_model_id
        self.opensearch_endpoint = opensearch_endpoint or os.getenv(
            "OPENSEARCH_ENDPOINT", "opensearch.aura.local"
        )

        self._opensearch_client: Any = None
        self._bedrock_client: Any = None
        self._initialized = False

        # Track indexed documents for incremental updates
        self._indexed_docs: dict[str, datetime] = {}

    async def initialize(self) -> bool:
        """
        Initialize the indexer by connecting to OpenSearch and Bedrock.

        Returns:
            True if initialization successful
        """
        try:
            # Initialize OpenSearch client
            self._init_opensearch_client()

            # Initialize Bedrock client for embeddings
            self._init_bedrock_client()

            self._initialized = True
            logger.info(
                f"DocumentationIndexer initialized: index={self.index_name}, "
                f"endpoint={self.opensearch_endpoint}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to initialize DocumentationIndexer: {e}")
            return False

    def _init_opensearch_client(self) -> None:
        """Initialize OpenSearch client."""
        try:
            import boto3
            from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

            credentials = boto3.Session().get_credentials()
            region = boto3.Session().region_name or "us-east-1"
            auth = AWSV4SignerAuth(credentials, region, "es")

            self._opensearch_client = OpenSearch(
                hosts=[{"host": self.opensearch_endpoint, "port": 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                timeout=30,
            )
            logger.info("OpenSearch client initialized")
        except ImportError:
            logger.warning("OpenSearch client not available - using mock mode")
            self._opensearch_client = None
        except Exception as e:
            logger.warning(f"Failed to connect to OpenSearch: {e}")
            self._opensearch_client = None

    def _init_bedrock_client(self) -> None:
        """Initialize Bedrock client for embeddings."""
        try:
            import boto3

            self._bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=os.getenv("AWS_REGION", "us-east-1"),
            )
            logger.info("Bedrock client initialized")
        except ImportError:
            logger.warning("Boto3 not available - embeddings will use mock vectors")
            self._bedrock_client = None
        except Exception as e:
            logger.warning(f"Failed to initialize Bedrock client: {e}")
            self._bedrock_client = None

    async def create_index(self) -> bool:
        """
        Create the documentation index in OpenSearch.

        Returns:
            True if index created or already exists
        """
        if self._opensearch_client is None:
            logger.warning("OpenSearch client not available - skipping index creation")
            return True

        try:
            if self._opensearch_client.indices.exists(index=self.index_name):
                logger.info(f"Index '{self.index_name}' already exists")
                return True

            self._opensearch_client.indices.create(
                index=self.index_name, body=DOCUMENTATION_INDEX_MAPPING
            )
            logger.info(f"Created index '{self.index_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            return False

    def parse_markdown(self, file_path: Path) -> ParsedDocument | None:
        """
        Parse a markdown file and extract metadata.

        Args:
            file_path: Path to the markdown file

        Returns:
            ParsedDocument with extracted content and metadata
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            stat = file_path.stat()
            last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

            # Extract title (first H1 or filename)
            title = self._extract_title(content, file_path)

            # Extract headers
            headers = self._extract_headers(content)

            # Extract code blocks
            code_blocks = self._extract_code_blocks(content)

            # Generate summary (first paragraph after title)
            summary = self._extract_summary(content)

            # Classify document
            doc_type = self._classify_doc_type(file_path)
            category = self._classify_category(file_path)

            # Clean content for indexing
            clean_content = self._clean_content(content)

            # Generate document ID
            doc_id = self._generate_doc_id(file_path)

            # Calculate word count
            word_count = len(clean_content.split())

            return ParsedDocument(
                doc_id=doc_id,
                title=title,
                content=clean_content,
                summary=summary,
                doc_type=doc_type,
                category=category,
                path=str(file_path),
                headers=headers,
                code_blocks=code_blocks,
                last_modified=last_modified,
                word_count=word_count,
                metadata={
                    "file_name": file_path.name,
                    "directory": str(file_path.parent),
                    "code_block_count": len(code_blocks),
                    "header_count": len(headers),
                },
            )
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return None

    def _extract_title(self, content: str, file_path: Path) -> str:
        """Extract title from markdown content."""
        # Try to find first H1
        h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if h1_match:
            return h1_match.group(1).strip()

        # Try to find title in YAML frontmatter
        frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if frontmatter_match:
            title_match = re.search(
                r"title:\s*[\"']?(.+?)[\"']?\s*$",
                frontmatter_match.group(1),
                re.MULTILINE,
            )
            if title_match:
                return title_match.group(1).strip()

        # Fall back to filename
        return file_path.stem.replace("-", " ").replace("_", " ").title()

    def _extract_headers(self, content: str) -> list[str]:
        """Extract all headers from markdown content."""
        headers = []
        for match in re.finditer(r"^#{1,6}\s+(.+)$", content, re.MULTILINE):
            headers.append(match.group(1).strip())
        return headers

    def _extract_code_blocks(self, content: str) -> list[str]:
        """Extract code blocks from markdown content."""
        code_blocks = []
        for match in re.finditer(r"```[\w]*\n(.*?)```", content, re.DOTALL):
            code_block = match.group(1).strip()
            if code_block:
                code_blocks.append(code_block)
        return code_blocks

    def _extract_summary(self, content: str) -> str:
        """Extract summary (first meaningful paragraph) from content."""
        # Remove frontmatter
        content = re.sub(r"^---\n.*?\n---\n*", "", content, flags=re.DOTALL)

        # Remove title
        content = re.sub(r"^#\s+.+\n*", "", content, count=1)

        # Remove version/date lines
        content = re.sub(r"^\*\*Version:\*\*.*$", "", content, flags=re.MULTILINE)
        content = re.sub(r"^\*\*Last Updated:\*\*.*$", "", content, flags=re.MULTILINE)

        # Find first paragraph (non-header, non-code, non-empty)
        lines = content.strip().split("\n")
        paragraph_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                if paragraph_lines:
                    break
                continue
            if line.startswith("#"):
                continue
            if line.startswith("```"):
                continue
            if line.startswith("---"):
                continue
            if line.startswith("|"):  # Table
                continue
            paragraph_lines.append(line)

        summary = " ".join(paragraph_lines)

        # Truncate to reasonable length
        if len(summary) > 500:
            summary = summary[:497] + "..."

        return summary

    def _clean_content(self, content: str) -> str:
        """Clean markdown content for indexing."""
        # Remove frontmatter
        content = re.sub(r"^---\n.*?\n---\n*", "", content, flags=re.DOTALL)

        # Remove code blocks (keep content but remove markers)
        content = re.sub(r"```[\w]*\n", "", content)
        content = re.sub(r"```", "", content)

        # Remove inline code backticks
        content = re.sub(r"`([^`]+)`", r"\1", content)

        # Remove markdown links but keep text
        content = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", content)

        # Remove images
        content = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", content)

        # Remove bold/italic markers
        content = re.sub(r"\*\*([^*]+)\*\*", r"\1", content)
        content = re.sub(r"\*([^*]+)\*", r"\1", content)
        content = re.sub(r"__([^_]+)__", r"\1", content)
        content = re.sub(r"_([^_]+)_", r"\1", content)

        # Remove horizontal rules
        content = re.sub(r"^---+$", "", content, flags=re.MULTILINE)

        # Normalize whitespace
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r"[ \t]+", " ", content)

        return content.strip()

    def _classify_doc_type(self, file_path: Path) -> str:
        """Classify document type based on path."""
        path_str = str(file_path).lower()

        if "/product/" in path_str:
            return DocumentationType.PRODUCT.value
        elif "/support/" in path_str:
            return DocumentationType.SUPPORT.value
        elif "/architecture-decisions/" in path_str or "adr-" in path_str.lower():
            return DocumentationType.ADR.value
        elif "/runbooks/" in path_str:
            return DocumentationType.RUNBOOK.value
        elif "/api-reference/" in path_str or "api" in file_path.stem.lower():
            return DocumentationType.API.value
        elif "/guides/" in path_str or "guide" in file_path.stem.lower():
            return DocumentationType.GUIDE.value
        elif "/reference/" in path_str:
            return DocumentationType.REFERENCE.value
        elif "/internal/" in path_str:
            return DocumentationType.INTERNAL.value
        else:
            return DocumentationType.GUIDE.value

    def _classify_category(self, file_path: Path) -> str:
        """Classify document category based on path and content."""
        path_str = str(file_path).lower()

        if "/getting-started/" in path_str:
            return DocumentationCategory.GETTING_STARTED.value
        elif "/core-concepts/" in path_str:
            return DocumentationCategory.CORE_CONCEPTS.value
        elif "/troubleshooting/" in path_str:
            return DocumentationCategory.TROUBLESHOOTING.value
        elif "/api-reference/" in path_str:
            return DocumentationCategory.API_REFERENCE.value
        elif "/architecture/" in path_str:
            return DocumentationCategory.ARCHITECTURE.value
        elif "/operations/" in path_str:
            return DocumentationCategory.OPERATIONS.value
        elif "/deployment/" in path_str:
            return DocumentationCategory.DEPLOYMENT.value
        elif "/security/" in path_str:
            return DocumentationCategory.SECURITY.value
        elif "/design/" in path_str:
            return DocumentationCategory.DESIGN.value
        elif "/research/" in path_str:
            return DocumentationCategory.RESEARCH.value
        else:
            return DocumentationCategory.GENERAL.value

    def _generate_doc_id(self, file_path: Path) -> str:
        """Generate a unique document ID from file path."""
        # Use hash of path for consistent ID
        path_hash = hashlib.sha256(str(file_path).encode()).hexdigest()[:12]
        return f"doc_{path_hash}"

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding vector for text using Bedrock Titan.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if self._bedrock_client is None:
            # Return mock embedding for testing
            logger.debug("Using mock embedding (Bedrock not available)")
            return [0.1] * self.vector_dimension

        try:
            # Truncate text if too long (Titan has 8192 token limit)
            max_chars = 25000  # Approximate 8192 tokens
            if len(text) > max_chars:
                text = text[:max_chars]

            response = self._bedrock_client.invoke_model(
                modelId=self.embedding_model_id,
                body=json.dumps({"inputText": text}),
            )

            result = json.loads(response["body"].read())
            embedding = result.get("embedding", [])

            if len(embedding) != self.vector_dimension:
                logger.warning(
                    f"Embedding dimension mismatch: expected {self.vector_dimension}, "
                    f"got {len(embedding)}"
                )

            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            # Return mock embedding as fallback
            return [0.1] * self.vector_dimension

    async def index_document(self, doc: ParsedDocument) -> bool:
        """
        Index a single document in OpenSearch.

        Args:
            doc: Parsed document to index

        Returns:
            True if indexing successful
        """
        try:
            # Generate embedding for the document
            # Combine title, summary, and headers for embedding
            embed_text = f"{doc.title}\n\n{doc.summary}\n\n{' '.join(doc.headers)}"
            embedding = await self.generate_embedding(embed_text)

            # Build document body
            doc_body = {
                "doc_id": doc.doc_id,
                "title": doc.title,
                "content": doc.content,
                "summary": doc.summary,
                "doc_type": doc.doc_type,
                "category": doc.category,
                "path": doc.path,
                "headers": " ".join(doc.headers),
                "last_modified": doc.last_modified.isoformat(),
                "word_count": doc.word_count,
                "embedding": embedding,
            }

            if self._opensearch_client is not None:
                self._opensearch_client.index(
                    index=self.index_name,
                    id=doc.doc_id,
                    body=doc_body,
                    refresh=False,
                )
                logger.debug(f"Indexed document: {doc.doc_id} ({doc.title})")
            else:
                logger.debug(f"[MOCK] Would index document: {doc.doc_id}")

            # Track indexed document
            self._indexed_docs[doc.doc_id] = doc.last_modified

            return True
        except Exception as e:
            logger.error(f"Failed to index document {doc.doc_id}: {e}")
            return False

    async def index_documentation(
        self,
        docs_path: str | Path,
        incremental: bool = True,
    ) -> dict[str, Any]:
        """
        Index all markdown files in a directory.

        Args:
            docs_path: Path to documentation directory
            incremental: If True, only index modified files

        Returns:
            Dictionary with indexing statistics
        """
        docs_path = Path(docs_path)
        if not docs_path.exists():
            logger.error(f"Documentation path does not exist: {docs_path}")
            return {"success": False, "error": "Path not found"}

        stats = {
            "total_files": 0,
            "indexed": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
        }

        # Find all markdown files
        md_files = list(docs_path.rglob("*.md"))
        stats["total_files"] = len(md_files)

        logger.info(f"Found {len(md_files)} markdown files in {docs_path}")

        for file_path in md_files:
            try:
                # Skip index.md files if they're just navigation
                if file_path.name == "index.md" and file_path.stat().st_size < 500:
                    stats["skipped"] += 1
                    continue

                # Parse the document
                doc = self.parse_markdown(file_path)
                if doc is None:
                    stats["failed"] += 1
                    continue

                # Check if we should skip (incremental update)
                if incremental and doc.doc_id in self._indexed_docs:
                    if self._indexed_docs[doc.doc_id] >= doc.last_modified:
                        stats["skipped"] += 1
                        continue

                # Index the document
                success = await self.index_document(doc)
                if success:
                    stats["indexed"] += 1
                else:
                    stats["failed"] += 1

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"{file_path}: {e}")
                logger.error(f"Error processing {file_path}: {e}")

        # Refresh index after bulk indexing
        if self._opensearch_client is not None and stats["indexed"] > 0:
            try:
                self._opensearch_client.indices.refresh(index=self.index_name)
            except Exception as e:
                logger.warning(f"Failed to refresh index: {e}")

        logger.info(
            f"Indexing complete: {stats['indexed']} indexed, "
            f"{stats['skipped']} skipped, {stats['failed']} failed"
        )

        return {"success": True, **stats}

    async def search(
        self,
        query: str,
        doc_type: str | None = None,
        category: str | None = None,
        limit: int = 10,
        min_score: float = 0.5,
        use_hybrid: bool = True,
    ) -> list[SearchResult]:
        """
        Search documentation using hybrid (text + vector) search.

        Args:
            query: Search query text
            doc_type: Optional filter by document type
            category: Optional filter by category
            limit: Maximum number of results
            min_score: Minimum similarity score
            use_hybrid: If True, use hybrid search; otherwise text-only

        Returns:
            List of search results
        """
        if self._opensearch_client is None:
            # Return mock results for testing
            return self._mock_search(query, doc_type, limit)

        try:
            # Build query
            if use_hybrid:
                results = await self._hybrid_search(
                    query, doc_type, category, limit, min_score
                )
            else:
                results = await self._text_search(query, doc_type, category, limit)

            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def _hybrid_search(
        self,
        query: str,
        doc_type: str | None,
        category: str | None,
        limit: int,
        min_score: float,
    ) -> list[SearchResult]:
        """Perform hybrid search combining text and vector similarity."""
        # Generate query embedding
        query_embedding = await self.generate_embedding(query)

        # Build the query
        must_clauses = []
        filter_clauses = []

        # Text search on title, content, headers, summary
        must_clauses.append(
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "summary^2", "headers^2", "content"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        )

        # Add filters
        if doc_type and doc_type != "all":
            filter_clauses.append({"term": {"doc_type": doc_type}})
        if category and category != "all":
            filter_clauses.append({"term": {"category": category}})

        # Build bool query for text search
        text_query: dict[str, Any] = {"bool": {"must": must_clauses}}
        if filter_clauses:
            text_query["bool"]["filter"] = filter_clauses

        # Build k-NN query
        knn_query: dict[str, Any] = {
            "knn": {
                "embedding": {
                    "vector": query_embedding,
                    "k": limit * 2,  # Get more for RRF fusion
                }
            }
        }

        # Execute both queries and combine results using a script score
        # For true hybrid, we use a bool query with should clauses
        hybrid_query = {
            "size": limit,
            "query": {
                "bool": {
                    "should": [
                        text_query,
                        knn_query,
                    ],
                    "minimum_should_match": 1,
                }
            },
            "_source": ["doc_id", "title", "path", "doc_type", "category", "summary"],
            "min_score": min_score,
        }

        if filter_clauses:
            hybrid_query["query"]["bool"]["filter"] = filter_clauses

        response = self._opensearch_client.search(
            index=self.index_name, body=hybrid_query
        )

        return self._parse_search_results(response)

    async def _text_search(
        self,
        query: str,
        doc_type: str | None,
        category: str | None,
        limit: int,
    ) -> list[SearchResult]:
        """Perform text-only search."""
        must_clauses = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "summary^2", "headers^2", "content"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        ]

        filter_clauses = []
        if doc_type and doc_type != "all":
            filter_clauses.append({"term": {"doc_type": doc_type}})
        if category and category != "all":
            filter_clauses.append({"term": {"category": category}})

        query_body: dict[str, Any] = {
            "size": limit,
            "query": {"bool": {"must": must_clauses}},
            "_source": ["doc_id", "title", "path", "doc_type", "category", "summary"],
            "highlight": {
                "fields": {
                    "content": {"fragment_size": 150, "number_of_fragments": 2},
                    "summary": {"fragment_size": 150, "number_of_fragments": 1},
                }
            },
        }

        if filter_clauses:
            query_body["query"]["bool"]["filter"] = filter_clauses

        response = self._opensearch_client.search(
            index=self.index_name, body=query_body
        )

        return self._parse_search_results(response)

    def _parse_search_results(self, response: dict[str, Any]) -> list[SearchResult]:
        """Parse OpenSearch response into SearchResult objects."""
        results = []

        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            highlights = []

            # Extract highlights if present
            if "highlight" in hit:
                for field_highlights in hit["highlight"].values():
                    highlights.extend(field_highlights)

            results.append(
                SearchResult(
                    doc_id=source.get("doc_id", ""),
                    title=source.get("title", ""),
                    path=source.get("path", ""),
                    doc_type=source.get("doc_type", ""),
                    category=source.get("category", ""),
                    summary=source.get("summary", ""),
                    score=hit.get("_score", 0.0),
                    highlights=highlights,
                )
            )

        return results

    def _mock_search(
        self, query: str, doc_type: str | None, limit: int
    ) -> list[SearchResult]:
        """Return mock search results for testing."""
        mock_docs = [
            SearchResult(
                doc_id="doc_abc123",
                title="Hybrid GraphRAG Architecture",
                path="docs/product/core-concepts/hybrid-graphrag.md",
                doc_type="product",
                category="core-concepts",
                summary="Hybrid GraphRAG combines graph databases with vector search for comprehensive code understanding.",
                score=0.95,
            ),
            SearchResult(
                doc_id="doc_def456",
                title="Common Issues Troubleshooting",
                path="docs/support/troubleshooting/common-issues.md",
                doc_type="support",
                category="troubleshooting",
                summary="Covers frequently encountered issues including authentication, API errors, and agent issues.",
                score=0.85,
            ),
            SearchResult(
                doc_id="doc_ghi789",
                title="Getting Started with Aura",
                path="docs/product/getting-started/quick-start.md",
                doc_type="product",
                category="getting-started",
                summary="Quick start guide for setting up Project Aura in your environment.",
                score=0.80,
            ),
        ]

        query_lower = query.lower()
        results = []

        for doc in mock_docs:
            if doc_type and doc_type != "all" and doc.doc_type != doc_type:
                continue
            if query_lower in doc.title.lower() or query_lower in doc.summary.lower():
                results.append(doc)
            elif not query_lower:
                results.append(doc)

        return results[:limit]

    async def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from the index.

        Args:
            doc_id: Document ID to delete

        Returns:
            True if deletion successful
        """
        if self._opensearch_client is None:
            return True

        try:
            self._opensearch_client.delete(
                index=self.index_name, id=doc_id, refresh=True
            )
            self._indexed_docs.pop(doc_id, None)
            logger.info(f"Deleted document: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    async def get_document(self, doc_id: str) -> dict[str, Any] | None:
        """
        Get a document by ID.

        Args:
            doc_id: Document ID

        Returns:
            Document data or None if not found
        """
        if self._opensearch_client is None:
            return None

        try:
            response = self._opensearch_client.get(index=self.index_name, id=doc_id)
            if response.get("found"):
                return response.get("_source")
            return None
        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            return None

    async def get_index_stats(self) -> dict[str, Any]:
        """
        Get statistics about the documentation index.

        Returns:
            Dictionary with index statistics
        """
        if self._opensearch_client is None:
            return {
                "doc_count": len(self._indexed_docs),
                "index_name": self.index_name,
                "mode": "mock",
            }

        try:
            stats = self._opensearch_client.indices.stats(index=self.index_name)
            index_stats = stats.get("indices", {}).get(self.index_name, {})
            total = index_stats.get("total", {})
            docs = total.get("docs", {})

            return {
                "doc_count": docs.get("count", 0),
                "index_name": self.index_name,
                "size_bytes": total.get("store", {}).get("size_in_bytes", 0),
                "mode": "aws",
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {"doc_count": 0, "index_name": self.index_name, "error": str(e)}


# Convenience function
def create_documentation_indexer() -> DocumentationIndexer:
    """
    Create and return a DocumentationIndexer instance.

    Uses environment variables for configuration:
    - OPENSEARCH_ENDPOINT: OpenSearch endpoint
    - DOCUMENTATION_INDEX_NAME: Index name (default: aura-documentation)
    - EMBEDDING_MODEL_ID: Bedrock model ID for embeddings

    Returns:
        Configured DocumentationIndexer instance
    """
    return DocumentationIndexer(
        index_name=os.getenv("DOCUMENTATION_INDEX_NAME", DOCUMENTATION_INDEX_NAME),
        opensearch_endpoint=os.getenv("OPENSEARCH_ENDPOINT"),
        embedding_model_id=os.getenv(
            "EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
        ),
    )
