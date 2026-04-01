"""
Project Aura - Filesystem Indexer Service

Indexes filesystem metadata into OpenSearch for fast agentic retrieval.
Supports incremental updates and full repository scans.

Author: Project Aura Team
Created: 2025-11-18
Version: 1.0.0
"""

import ast
import asyncio
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import git

logger = logging.getLogger(__name__)

# Constants
MIN_TEXT_LENGTH_FOR_EMBEDDING = 3


class FilesystemIndexer:
    """
    Indexes filesystem metadata into OpenSearch for agentic search.

    Features:
    - Full repository scanning
    - Incremental updates (git hooks, file watchers)
    - Code analysis (imports, exports, complexity)
    - Embedding generation for paths and docstrings
    - Git metadata extraction (blame, contributors)

    Usage:
        indexer = FilesystemIndexer(
            opensearch_client=opensearch,
            embedding_service=titan_embeddings,
            git_repo_path="/path/to/repo"
        )

        # Full index
        await indexer.index_repository(Path("/path/to/repo"))

        # Incremental update
        await indexer.index_file(Path("src/services/new_file.py"))
    """

    def __init__(
        self,
        opensearch_client,
        embedding_service,
        git_repo_path: str,
        index_name: str = "aura-filesystem-metadata",
    ):
        """
        Initialize filesystem indexer.

        Args:
            opensearch_client: OpenSearch client instance
            embedding_service: Service for generating embeddings
            git_repo_path: Path to Git repository
            index_name: OpenSearch index name
        """
        self.opensearch = opensearch_client
        self.embeddings = embedding_service
        self.repo = git.Repo(git_repo_path)
        self.index_name = index_name
        self.repo_root = Path(git_repo_path)

        # Patterns to ignore (similar to .gitignore)
        self.ignore_patterns = [
            "__pycache__",
            "*.pyc",
            ".git",
            ".venv",
            "venv",
            "node_modules",
            "*.egg-info",
            "build",
            "dist",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        ]

        logger.info(
            f"Initialized FilesystemIndexer: index={index_name}, repo={git_repo_path}"
        )

    async def index_repository(self, repo_path: Path, batch_size: int = 100) -> None:
        """
        Full repository indexing (initial scan).

        Args:
            repo_path: Path to repository root
            batch_size: Number of files to index per batch
        """
        logger.info(f"Starting full repository index: {repo_path}")

        indexed_count = 0
        batch = []

        for file_path in repo_path.rglob("*"):
            if file_path.is_file() and not self._should_ignore(file_path):
                try:
                    doc = await self._extract_metadata(file_path)
                    batch.append(doc)

                    if len(batch) >= batch_size:
                        await self._bulk_index(batch)
                        indexed_count += len(batch)
                        logger.info(f"Indexed {indexed_count} files...")
                        batch = []

                except Exception as e:
                    logger.error(f"Failed to index {file_path}: {e}")

        # Index remaining files
        if batch:
            await self._bulk_index(batch)
            indexed_count += len(batch)

        logger.info(f"Repository indexing complete: {indexed_count} files indexed")

    async def index_file(self, file_path: Path) -> None:
        """
        Index single file metadata.

        Args:
            file_path: Path to file
        """
        if self._should_ignore(file_path):
            logger.debug(f"Skipping ignored file: {file_path}")
            return

        logger.debug(f"Indexing file: {file_path}")

        metadata = await self._extract_metadata(file_path)

        # Embed file path + docstring
        path_embedding = await self._embed_text(str(file_path))
        docstring_embedding = await self._embed_text(metadata.get("docstring", ""))

        doc = {
            **metadata,
            "path_embedding": path_embedding,
            "docstring_embedding": docstring_embedding,
            "indexed_at": datetime.now().isoformat(),
        }

        # Index to OpenSearch
        await self.opensearch.index(
            index=self.index_name, id=self._get_file_id(file_path), body=doc
        )

        logger.debug(f"File indexed: {file_path}")

    async def delete_file(self, file_path: Path) -> None:
        """
        Remove file from index (when deleted from filesystem).

        Args:
            file_path: Path to deleted file
        """
        file_id = self._get_file_id(file_path)

        try:
            await self.opensearch.delete(index=self.index_name, id=file_id)
            logger.debug(f"File removed from index: {file_path}")
        except Exception as e:
            logger.warning(
                f"Failed to delete {file_path} from index: {e}"  # nosec B608
            )

    async def update_file(self, file_path: Path) -> None:
        """
        Update existing file metadata (incremental update).

        Args:
            file_path: Path to modified file
        """
        await self.index_file(file_path)  # Re-index overwrites

    async def _extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """
        Extract comprehensive file metadata.

        Args:
            file_path: Path to file

        Returns:
            Metadata dictionary
        """
        stat = file_path.stat()

        # Git metadata
        git_metadata = await self._get_git_metadata(file_path)

        # Code analysis
        language = self._detect_language(file_path)
        is_test = "test" in file_path.name.lower()
        is_config = file_path.suffix in [".yaml", ".yml", ".json", ".toml", ".ini"]

        # Parse code structure (for Python files)
        docstring = None
        imports = []
        exported_functions = []
        exported_classes = []
        complexity_score = 0.0

        if language == "python":
            code_metadata = await self._analyze_python_file(file_path)
            docstring = code_metadata.get("docstring")
            imports = code_metadata.get("imports", [])
            exported_functions = code_metadata.get("functions", [])
            exported_classes = code_metadata.get("classes", [])
            complexity_score = code_metadata.get("complexity", 0.0)

        return {
            "file_path": str(file_path.relative_to(self.repo_root)),
            "file_name": file_path.name,
            "file_extension": file_path.suffix,
            "directory": str(file_path.parent.relative_to(self.repo_root)),
            "file_size": stat.st_size,
            "num_lines": self._count_lines(file_path),
            "language": language,
            "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "last_author": git_metadata.get("author"),
            "last_commit_hash": git_metadata.get("commit_hash"),
            "last_commit_message": git_metadata.get("commit_message"),
            "num_contributors": git_metadata.get("num_contributors", 0),
            "is_test_file": is_test,
            "is_config_file": is_config,
            "docstring": docstring,
            "imports": imports,
            "exported_functions": exported_functions,
            "exported_classes": exported_classes,
            "complexity_score": complexity_score,
        }

    async def _get_git_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract Git metadata for file."""
        try:
            # Get last commit for file
            commits = list(self.repo.iter_commits(paths=str(file_path), max_count=1))

            if not commits:
                return {}

            last_commit = commits[0]

            # Count unique contributors
            all_commits = list(self.repo.iter_commits(paths=str(file_path)))
            contributors = {commit.author.name for commit in all_commits}

            return {
                "author": last_commit.author.name,
                "commit_hash": last_commit.hexsha,
                "commit_message": (
                    last_commit.message.decode("utf-8").split("\n")[0]
                    if isinstance(last_commit.message, bytes)
                    else last_commit.message.split("\n")[0]
                ),  # First line
                "num_contributors": len(contributors),
            }

        except Exception as e:
            logger.warning(f"Failed to get Git metadata for {file_path}: {e}")
            return {}

    async def _analyze_python_file(self, file_path: Path) -> dict[str, Any]:
        """
        Analyze Python file structure.

        Extracts:
        - Module docstring
        - Import statements
        - Exported functions (public, no underscore prefix)
        - Exported classes
        - Cyclomatic complexity estimate
        """
        try:
            with file_path.open("r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source)

            # Extract docstring
            docstring = ast.get_docstring(tree)

            # Extract imports
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend([alias.name for alias in node.names])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.extend(
                        [f"{node.module}.{alias.name}" for alias in node.names]
                    )

            # Extract functions (public only)
            functions = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
            ]

            # Extract classes (public only)
            classes = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
            ]

            # Simple complexity estimate (count decision points)
            complexity = sum(
                1
                for node in ast.walk(tree)
                if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With))
            )

            return {
                "docstring": docstring,
                "imports": imports[:50],  # Limit to first 50 imports
                "functions": functions[:50],  # Limit to first 50 functions
                "classes": classes[:50],  # Limit to first 50 classes
                "complexity": float(complexity),
            }

        except Exception as e:
            logger.warning(f"Failed to analyze Python file {file_path}: {e}")
            return {}

    async def _embed_text(self, text: str) -> list[float]:
        """Generate embedding for text."""
        if not text or len(text) < MIN_TEXT_LENGTH_FOR_EMBEDDING:
            return [0.0] * 1536  # Return zero vector for empty/short text

        try:
            return await self.embeddings.generate_embedding(text)  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return [0.0] * 1536

    async def _bulk_index(self, documents: list[dict]) -> None:
        """Bulk index multiple documents."""
        bulk_body = []

        for doc in documents:
            file_path = doc["file_path"]
            file_id = hashlib.md5(file_path.encode(), usedforsecurity=False).hexdigest()

            # Add path and docstring embeddings
            path_embedding = await self._embed_text(file_path)
            docstring_embedding = await self._embed_text(doc.get("docstring", ""))

            doc["path_embedding"] = path_embedding
            doc["docstring_embedding"] = docstring_embedding
            doc["indexed_at"] = datetime.now().isoformat()

            # Index action
            bulk_body.append({"index": {"_index": self.index_name, "_id": file_id}})
            bulk_body.append(doc)

        if bulk_body:
            await self.opensearch.bulk(body=bulk_body, refresh=True)

    def _get_file_id(self, file_path: Path) -> str:
        """Generate unique ID for file."""
        relative_path = str(file_path.relative_to(self.repo_root))
        return hashlib.md5(relative_path.encode(), usedforsecurity=False).hexdigest()

    def _should_ignore(self, file_path: Path) -> bool:
        """Check if file should be ignored."""
        path_str = str(file_path)

        return any(pattern in path_str for pattern in self.ignore_patterns)

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".rb": "ruby",
            ".php": "php",
            ".sh": "bash",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".toml": "toml",
            ".md": "markdown",
            ".sql": "sql",
        }

        return extension_map.get(file_path.suffix, "unknown")

    def _count_lines(self, file_path: Path) -> int:
        """Count lines in file."""
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0


# Example usage
async def example_usage() -> None:
    """Example usage of FilesystemIndexer."""
    from src.services.opensearch_vector_service import (  # noqa: PLC0415
        OpenSearchVectorService,
    )
    from src.services.titan_embedding_service import (  # noqa: PLC0415
        TitanEmbeddingService,
    )

    # Initialize services
    opensearch = OpenSearchVectorService(endpoint="localhost:9200")
    embeddings = TitanEmbeddingService()

    # Create indexer
    indexer = FilesystemIndexer(
        opensearch_client=opensearch,
        embedding_service=embeddings,
        git_repo_path="/path/to/project-aura",
    )

    # Index entire repository
    await indexer.index_repository(Path("/path/to/project-aura"))

    print("Repository indexed successfully!")


if __name__ == "__main__":
    asyncio.run(example_usage())
