"""
Project Aura - Git Ingestion Pipeline Service

Orchestrates the ingestion of Git repositories into Neptune (graph) and OpenSearch (vectors).
Supports full repository ingestion and incremental updates via webhooks.

Author: Project Aura Team
Created: 2025-11-28
Version: 1.0.0
"""

import asyncio
import base64
import hashlib
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from git import GitCommandError, InvalidGitRepositoryError, Repo

from src.services.github_app_auth import GitHubAppAuth, get_github_app_auth
from src.services.observability_service import ObservabilityService, get_monitor
from src.services.secure_command_executor import (
    SecureCommandExecutor,
    get_secure_executor,
)
from src.services.semantic_guardrails.normalizer import normalize_text
from src.services.semantic_guardrails.pattern_matcher import match_patterns

logger = logging.getLogger(__name__)


class IngestionStatus(Enum):
    """Status of an ingestion job."""

    PENDING = "pending"
    CLONING = "cloning"
    PARSING = "parsing"
    INDEXING_GRAPH = "indexing_graph"
    INDEXING_VECTORS = "indexing_vectors"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionMode(Enum):
    """Type of ingestion operation."""

    FULL = "full"  # Complete repository scan
    INCREMENTAL = "incremental"  # Changed files only (webhook-triggered)
    BRANCH = "branch"  # Specific branch ingestion


@dataclass
class IngestionJob:
    """Represents an ingestion job."""

    job_id: str
    repository_url: str
    branch: str = "main"
    mode: IngestionMode = IngestionMode.FULL
    status: IngestionStatus = IngestionStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    files_processed: int = 0
    entities_indexed: int = 0
    embeddings_generated: int = 0
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestionResult:
    """Result of an ingestion operation."""

    job_id: str
    success: bool
    files_processed: int
    entities_indexed: int
    embeddings_generated: int
    duration_seconds: float
    errors: list[str]
    commit_hash: str | None = None


class GitIngestionService:
    """
    Git Ingestion Pipeline Service.

    Orchestrates the complete ingestion workflow:
    1. Clone/fetch repository from GitHub
    2. Parse code structure using ASTParserAgent
    3. Populate Neptune graph with code entities and relationships
    4. Generate embeddings and index in OpenSearch
    5. Support incremental updates via webhooks

    All blocking I/O operations (git commands, file reads, database calls) are
    offloaded to a thread pool using asyncio.to_thread() to prevent blocking
    the FastAPI event loop.

    Usage:
        service = GitIngestionService(
            neptune_client=neptune,
            opensearch_client=opensearch,
            embedding_service=titan_embeddings,
            ast_parser=ast_parser
        )

        # Full ingestion
        result = await service.ingest_repository(
            repository_url="https://github.com/org/repo",
            branch="main"
        )

        # Incremental update (webhook)
        result = await service.ingest_changes(
            repository_path="/path/to/repo",
            changed_files=["src/app.py", "src/utils.py"]
        )
    """

    # Configuration constants
    DEFAULT_BATCH_SIZE = 50  # Files per batch
    DEFAULT_MAX_FILE_SIZE_KB = 500  # Skip files larger than this
    DEFAULT_MAX_CONCURRENT_PARSE = 10  # Max concurrent file parsing operations
    DEFAULT_MAX_CONCURRENT_GRAPH = 20  # Max concurrent graph operations
    DEFAULT_MAX_CONCURRENT_INDEX = 5  # Max concurrent embedding/indexing operations
    DEFAULT_OPENSEARCH_BULK_SIZE = 200  # Documents per OpenSearch bulk request
    DEFAULT_MAX_CONTENT_SIZE_BYTES = 20 * 1024  # 20KB max content for embeddings

    def __init__(
        self,
        neptune_service=None,
        opensearch_service=None,
        embedding_service=None,
        ast_parser=None,
        persistence_service=None,
        observability_service: ObservabilityService | None = None,
        clone_base_path: str | None = None,
        github_token: str | None = None,
        github_app_auth: GitHubAppAuth | None = None,
        batch_size: int | None = None,
        max_file_size_kb: int | None = None,
        max_concurrent_parse: int | None = None,
        max_concurrent_graph: int | None = None,
        max_concurrent_index: int | None = None,
        opensearch_bulk_size: int | None = None,
        max_content_size_bytes: int | None = None,
    ):
        """
        Initialize Git Ingestion Service.

        Args:
            neptune_service: NeptuneGraphService instance
            opensearch_service: OpenSearchVectorService instance
            embedding_service: TitanEmbeddingService instance
            ast_parser: ASTParserAgent instance
            persistence_service: JobPersistenceService instance for DynamoDB
            observability_service: ObservabilityService for metrics (uses global if None)
            clone_base_path: Directory for cloning repositories (default: temp dir)
            github_token: GitHub PAT for private repos (legacy, prefer github_app_auth)
            github_app_auth: GitHubAppAuth for GitHub App authentication (recommended)
            batch_size: Files to process per batch (default: DEFAULT_BATCH_SIZE)
            max_file_size_kb: Skip files larger than this (default: DEFAULT_MAX_FILE_SIZE_KB)
            max_concurrent_parse: Max concurrent file parsing operations
            max_concurrent_graph: Max concurrent graph operations
            max_concurrent_index: Max concurrent embedding/indexing operations
            opensearch_bulk_size: Documents per OpenSearch bulk request (default: 200)
            max_content_size_bytes: Max content size for embeddings (default: 20KB)
        """
        self.neptune = neptune_service
        self.opensearch = opensearch_service
        self.embeddings = embedding_service
        self.ast_parser = ast_parser
        self.persistence = persistence_service
        self.monitor = observability_service or get_monitor()

        # Clone directory management
        self.clone_dir = (
            Path(clone_base_path)
            if clone_base_path
            else Path(tempfile.gettempdir()) / "aura-repos"
        )
        self.clone_dir.mkdir(parents=True, exist_ok=True)

        # GitHub authentication (prefer App auth over PAT)
        self.github_app_auth = github_app_auth or get_github_app_auth()
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")

        # Job tracking (in-memory cache, backed by DynamoDB if persistence enabled)
        self.active_jobs: dict[str, IngestionJob] = {}
        self.completed_jobs: list[IngestionJob] = []

        # Configuration (use provided values or class defaults)
        self.batch_size = (
            batch_size if batch_size is not None else self.DEFAULT_BATCH_SIZE
        )
        self.max_file_size_kb = (
            max_file_size_kb
            if max_file_size_kb is not None
            else self.DEFAULT_MAX_FILE_SIZE_KB
        )

        # Concurrency limits for thread pool operations
        # These prevent spawning too many threads during large ingestion jobs
        self._parse_semaphore = asyncio.Semaphore(
            max_concurrent_parse
            if max_concurrent_parse is not None
            else self.DEFAULT_MAX_CONCURRENT_PARSE
        )
        self._graph_semaphore = asyncio.Semaphore(
            max_concurrent_graph
            if max_concurrent_graph is not None
            else self.DEFAULT_MAX_CONCURRENT_GRAPH
        )
        self._index_semaphore = asyncio.Semaphore(
            max_concurrent_index
            if max_concurrent_index is not None
            else self.DEFAULT_MAX_CONCURRENT_INDEX
        )

        # OpenSearch bulk indexing configuration
        self.opensearch_bulk_size = (
            opensearch_bulk_size
            if opensearch_bulk_size is not None
            else self.DEFAULT_OPENSEARCH_BULK_SIZE
        )
        self.max_content_size_bytes = (
            max_content_size_bytes
            if max_content_size_bytes is not None
            else self.DEFAULT_MAX_CONTENT_SIZE_BYTES
        )

        # Secure command executor for git operations
        self._executor = get_secure_executor()

        # Content scanning statistics
        self._content_scan_stats = {
            "scanned": 0,
            "quarantined": 0,
        }

        self.supported_extensions = {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".java",
            ".go",
            ".rs",
        }

        # Patterns to ignore
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
            "*.min.js",
            "*.bundle.js",
        ]

        logger.info(f"GitIngestionService initialized: clone_dir={self.clone_dir}")

        # Load active jobs from persistence on startup
        if self.persistence:
            self._load_active_jobs_from_persistence()

    def _load_active_jobs_from_persistence(self) -> None:
        """Load active jobs from DynamoDB on service startup."""
        try:
            active_jobs = self.persistence.get_active_jobs()
            logger.info(f"Loaded {len(active_jobs)} active jobs from persistence")

            for job_data in active_jobs:
                # Convert back to IngestionJob
                job = IngestionJob(
                    job_id=job_data.get("job_id", job_data.get("jobId")),
                    repository_url=job_data.get("repository_url", ""),
                    branch=job_data.get("branch", "main"),
                    mode=IngestionMode(job_data.get("mode", "FULL")),
                    status=IngestionStatus(job_data.get("status", "PENDING")),
                    files_processed=job_data.get("files_processed", 0),
                    entities_indexed=job_data.get("entities_indexed", 0),
                    embeddings_generated=job_data.get("embeddings_generated", 0),
                    errors=job_data.get("errors", []),
                    metadata=job_data.get("metadata", {}),
                )
                self.active_jobs[job.job_id] = job

        except Exception as e:
            logger.error(f"Failed to load active jobs from persistence: {e}")

    def _persist_job(self, job: IngestionJob) -> None:
        """Save job state to DynamoDB."""
        if self.persistence:
            try:
                self.persistence.save_job(job)
            except Exception as e:
                logger.error(f"Failed to persist job {job.job_id}: {e}")

    def _update_job_status_in_persistence(
        self,
        job_id: str,
        status: IngestionStatus,
        additional_updates: dict[str, Any] | None = None,
    ):
        """Update job status in DynamoDB."""
        if self.persistence:
            try:
                self.persistence.update_job_status(
                    job_id, status.value, additional_updates
                )
            except Exception as e:
                logger.error(f"Failed to update job status in persistence: {e}")

    async def ingest_repository(
        self,
        repository_url: str,
        branch: str = "main",
        shallow: bool = True,
        force_refresh: bool = False,
    ) -> IngestionResult:
        """
        Ingest a complete Git repository.

        Args:
            repository_url: GitHub repository URL
            branch: Branch to ingest (default: main)
            shallow: Use shallow clone for speed (default: True)
            force_refresh: Force re-clone even if exists (default: False)

        Returns:
            IngestionResult with statistics and status
        """
        start_time = datetime.now()
        job_id = self._generate_job_id(repository_url, branch)

        # Record request metric
        self.monitor.record_request("ingestion.full")

        job = IngestionJob(
            job_id=job_id,
            repository_url=repository_url,
            branch=branch,
            mode=IngestionMode.FULL,
            status=IngestionStatus.PENDING,
            started_at=start_time,
        )
        self.active_jobs[job_id] = job
        self._persist_job(job)  # Save to DynamoDB

        # Track ingest queue depth for backpressure monitoring
        self.monitor.record_queue_depth(
            queue_name="ingest",
            current_depth=len(self.active_jobs),
            max_depth=10,  # Alert when >8 concurrent jobs (80% of 10)
        )

        try:
            # Step 1: Clone or fetch repository
            job.status = IngestionStatus.CLONING
            self._update_job_status_in_persistence(job_id, job.status)
            repo_path = await self._clone_or_fetch(
                repository_url, branch, shallow, force_refresh
            )
            commit_hash = self._get_current_commit(repo_path)
            logger.info(f"Repository ready at {repo_path}, commit: {commit_hash}")

            # Step 2: Discover files to process
            files_to_process = await self._discover_files(repo_path)
            logger.info(f"Discovered {len(files_to_process)} files to process")

            # Step 3: Parse code structure (AST)
            job.status = IngestionStatus.PARSING
            self._update_job_status_in_persistence(job_id, job.status)
            entities = await self._parse_files(files_to_process, repo_path)
            job.entities_indexed = len(entities)
            logger.info(f"Parsed {len(entities)} code entities")

            # Step 4: Populate Neptune graph
            job.status = IngestionStatus.INDEXING_GRAPH
            self._update_job_status_in_persistence(job_id, job.status)
            await self._populate_graph(entities, repository_url, branch)
            logger.info("Neptune graph populated")

            # Step 5: Generate embeddings and index in OpenSearch
            job.status = IngestionStatus.INDEXING_VECTORS
            self._update_job_status_in_persistence(job_id, job.status)
            embeddings_count = await self._index_embeddings(
                files_to_process, repo_path, repository_url
            )
            job.embeddings_generated = embeddings_count
            logger.info(f"Indexed {embeddings_count} embeddings in OpenSearch")

            # Complete
            job.status = IngestionStatus.COMPLETED
            job.completed_at = datetime.now()
            job.files_processed = len(files_to_process)

            # Persist final state with all metrics
            self._update_job_status_in_persistence(
                job_id,
                job.status,
                {
                    "files_processed": job.files_processed,
                    "entities_indexed": job.entities_indexed,
                    "embeddings_generated": job.embeddings_generated,
                    "completed_at": job.completed_at.isoformat(),
                    "commit_hash": commit_hash,
                },
            )

            duration = (job.completed_at - start_time).total_seconds()

            # Record success metrics
            self.monitor.record_latency("ingestion.full", duration)
            self.monitor.record_success("ingestion.full")

            logger.info(
                f"Ingestion complete: {len(files_to_process)} files, "
                f"{len(entities)} entities, {embeddings_count} embeddings in {duration:.1f}s"
            )

            return IngestionResult(
                job_id=job_id,
                success=True,
                files_processed=len(files_to_process),
                entities_indexed=len(entities),
                embeddings_generated=embeddings_count,
                duration_seconds=duration,
                errors=[],
                commit_hash=commit_hash,
            )

        except Exception as e:
            job.status = IngestionStatus.FAILED
            job.errors.append(str(e))
            job.completed_at = datetime.now()
            logger.error(f"Ingestion failed: {e}", exc_info=True)

            # Record error metrics
            self.monitor.record_error("ingestion.full", error=e)
            duration = (job.completed_at - start_time).total_seconds()
            self.monitor.record_latency("ingestion.full", duration)

            # Persist failure state
            self._update_job_status_in_persistence(
                job_id,
                job.status,
                {
                    "errors": job.errors,
                    "completed_at": job.completed_at.isoformat(),
                    "files_processed": job.files_processed,
                    "entities_indexed": job.entities_indexed,
                    "embeddings_generated": job.embeddings_generated,
                },
            )

            return IngestionResult(
                job_id=job_id,
                success=False,
                files_processed=job.files_processed,
                entities_indexed=job.entities_indexed,
                embeddings_generated=job.embeddings_generated,
                duration_seconds=duration,
                errors=job.errors,
            )
        finally:
            # Move to completed jobs
            if job_id in self.active_jobs:
                self.completed_jobs.append(self.active_jobs.pop(job_id))
            # Update ingest queue depth after job completes
            self.monitor.record_queue_depth(
                queue_name="ingest",
                current_depth=len(self.active_jobs),
                max_depth=10,
            )

    async def ingest_changes(
        self,
        repository_path: str | Path,
        changed_files: list[str],
        commit_hash: str | None = None,
    ) -> IngestionResult:
        """
        Incremental ingestion for changed files (webhook-triggered).

        Args:
            repository_path: Path to the local repository
            changed_files: List of changed file paths (relative to repo root)
            commit_hash: Commit hash that triggered the change

        Returns:
            IngestionResult with statistics
        """
        start_time = datetime.now()
        repo_path = Path(repository_path)
        job_id = self._generate_job_id(str(repo_path), commit_hash or "incremental")

        # Record request metric
        self.monitor.record_request("ingestion.incremental")

        job = IngestionJob(
            job_id=job_id,
            repository_url=str(repo_path),
            mode=IngestionMode.INCREMENTAL,
            status=IngestionStatus.PENDING,
            started_at=start_time,
        )
        self.active_jobs[job_id] = job
        self._persist_job(job)  # Save to DynamoDB

        try:
            # Filter to supported files only
            files_to_process = [
                repo_path / f
                for f in changed_files
                if Path(f).suffix in self.supported_extensions
                and (repo_path / f).exists()
            ]

            logger.info(f"Processing {len(files_to_process)} changed files")

            # Parse changed files
            job.status = IngestionStatus.PARSING
            self._update_job_status_in_persistence(job_id, job.status)
            entities = await self._parse_files(files_to_process, repo_path)
            job.entities_indexed = len(entities)

            # Update graph (upsert)
            job.status = IngestionStatus.INDEXING_GRAPH
            self._update_job_status_in_persistence(job_id, job.status)
            await self._populate_graph(
                entities, str(repo_path), "incremental", upsert=True
            )

            # Update embeddings
            job.status = IngestionStatus.INDEXING_VECTORS
            self._update_job_status_in_persistence(job_id, job.status)
            embeddings_count = await self._index_embeddings(
                files_to_process, repo_path, str(repo_path), upsert=True
            )
            job.embeddings_generated = embeddings_count

            job.status = IngestionStatus.COMPLETED
            job.completed_at = datetime.now()
            job.files_processed = len(files_to_process)

            # Persist final state with all metrics
            self._update_job_status_in_persistence(
                job_id,
                job.status,
                {
                    "files_processed": job.files_processed,
                    "entities_indexed": job.entities_indexed,
                    "embeddings_generated": job.embeddings_generated,
                    "completed_at": job.completed_at.isoformat(),
                    "commit_hash": commit_hash,
                },
            )

            duration = (job.completed_at - start_time).total_seconds()

            # Record success metrics
            self.monitor.record_latency("ingestion.incremental", duration)
            self.monitor.record_success("ingestion.incremental")

            logger.info(
                f"Incremental ingestion complete: {len(files_to_process)} files in {duration:.1f}s"
            )

            return IngestionResult(
                job_id=job_id,
                success=True,
                files_processed=len(files_to_process),
                entities_indexed=len(entities),
                embeddings_generated=embeddings_count,
                duration_seconds=duration,
                errors=[],
                commit_hash=commit_hash,
            )

        except Exception as e:
            job.status = IngestionStatus.FAILED
            job.errors.append(str(e))
            job.completed_at = datetime.now()
            logger.error(f"Incremental ingestion failed: {e}", exc_info=True)

            # Record error metrics
            self.monitor.record_error("ingestion.incremental", error=e)
            duration = (job.completed_at - start_time).total_seconds()
            self.monitor.record_latency("ingestion.incremental", duration)

            # Persist failure state
            self._update_job_status_in_persistence(
                job_id,
                job.status,
                {
                    "errors": job.errors,
                    "completed_at": job.completed_at.isoformat(),
                    "files_processed": job.files_processed,
                    "entities_indexed": job.entities_indexed,
                    "embeddings_generated": job.embeddings_generated,
                },
            )

            return IngestionResult(
                job_id=job_id,
                success=False,
                files_processed=job.files_processed,
                entities_indexed=job.entities_indexed,
                embeddings_generated=job.embeddings_generated,
                duration_seconds=duration,
                errors=job.errors,
            )
        finally:
            if job_id in self.active_jobs:
                self.completed_jobs.append(self.active_jobs.pop(job_id))

    async def delete_repository(self, repository_url: str) -> dict[str, Any]:
        """
        Remove a repository from the index.

        Deletes all code entities from Neptune graph, all embeddings
        from OpenSearch, and removes the local clone.

        Args:
            repository_url: Repository URL to remove

        Returns:
            Dictionary with deletion statistics
        """
        errors: list[str] = []
        result: dict[str, Any] = {
            "repository_url": repository_url,
            "neptune_entities_deleted": 0,
            "opensearch_documents_deleted": 0,
            "local_clone_removed": False,
            "success": False,
            "errors": errors,
        }

        try:
            repo_id = self._url_to_repo_id(repository_url)

            # Remove from Neptune
            if self.neptune:
                try:
                    deleted_count = self.neptune.delete_by_repository(repo_id)
                    result["neptune_entities_deleted"] = deleted_count
                    logger.info(
                        f"Removed {deleted_count} entities from Neptune: {repo_id}"
                    )
                except Exception as e:
                    error_msg = f"Neptune deletion failed: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            else:
                logger.info(f"[MOCK] Would remove repository from Neptune: {repo_id}")

            # Remove from OpenSearch
            if self.opensearch:
                try:
                    deleted_count = self.opensearch.delete_by_repository(repo_id)
                    result["opensearch_documents_deleted"] = deleted_count
                    logger.info(
                        f"Removed {deleted_count} documents from OpenSearch: {repo_id}"
                    )
                except Exception as e:
                    error_msg = f"OpenSearch deletion failed: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            else:
                logger.info(
                    f"[MOCK] Would remove repository from OpenSearch: {repo_id}"
                )

            # Remove local clone
            clone_path = self.clone_dir / repo_id
            if clone_path.exists():
                shutil.rmtree(clone_path)
                result["local_clone_removed"] = True
                logger.info(f"Removed local clone: {clone_path}")

            result["success"] = len(errors) == 0
            return result

        except Exception as e:
            error_msg = f"Failed to delete repository: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
            return result

    def get_job_status(self, job_id: str) -> IngestionJob | None:
        """Get the status of an ingestion job."""
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]
        for job in self.completed_jobs:
            if job.job_id == job_id:
                return job
        return None

    def list_active_jobs(self) -> list[IngestionJob]:
        """List all active ingestion jobs."""
        return list(self.active_jobs.values())

    # ==================== Private Methods ====================

    async def _clone_or_fetch(
        self,
        repository_url: str,
        branch: str,
        shallow: bool,
        force_refresh: bool,
    ) -> Path:
        """Clone or fetch a repository with secure credential handling.

        Uses http.extraHeader for authentication instead of embedding tokens
        in URLs, preventing credential leakage via logs, process lists, or
        git config.

        All blocking git operations are offloaded to a thread pool to avoid
        blocking the FastAPI event loop.
        """
        repo_id = self._url_to_repo_id(repository_url)
        repo_path = self.clone_dir / repo_id

        if repo_path.exists() and not force_refresh:
            # Fetch and pull latest changes using secure methods
            try:
                # Offload blocking git operations to thread pool
                await asyncio.to_thread(self._secure_fetch, repo_path)
                await asyncio.to_thread(self._secure_pull, repo_path, branch)
                logger.info(f"Updated existing repository: {repo_path}")
                return repo_path
            except (InvalidGitRepositoryError, GitCommandError) as e:
                logger.warning(f"Failed to update, re-cloning: {e}")
                await asyncio.to_thread(shutil.rmtree, repo_path)

        # Clone repository using secure method (no credentials in URL)
        # Offload blocking clone to thread pool
        await asyncio.to_thread(
            self._secure_clone,
            repository_url,
            str(repo_path),
            branch,
            shallow,
        )
        return repo_path

    def _discover_files_sync(self, repo_path: Path) -> list[Path]:
        """Discover all processable files in the repository (sync implementation)."""
        files = []

        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Check extension
            if file_path.suffix not in self.supported_extensions:
                continue

            # Check ignore patterns
            relative_path = str(file_path.relative_to(repo_path))
            if any(pattern in relative_path for pattern in self.ignore_patterns):
                continue

            # Check file size
            try:
                size_kb = file_path.stat().st_size / 1024
                if size_kb > self.max_file_size_kb:
                    logger.debug(
                        f"Skipping large file: {relative_path} ({size_kb:.1f}KB)"
                    )
                    continue
            except OSError:
                continue

            files.append(file_path)

        return files

    async def _discover_files(self, repo_path: Path) -> list[Path]:
        """Discover all processable files in the repository.

        Offloads blocking filesystem traversal to thread pool.
        """
        return await asyncio.to_thread(self._discover_files_sync, repo_path)

    def _parse_single_file(self, file_path: Path, repo_path: Path) -> list:
        """Parse a single file using AST parser (sync implementation)."""
        try:
            entities = self.ast_parser.parse_file(file_path)
            # Update file paths to be relative
            for entity in entities:
                entity.file_path = str(file_path.relative_to(repo_path))
            return entities
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return []

    async def _parse_file_with_limit(self, file_path: Path, repo_path: Path) -> list:
        """Parse a single file with concurrency limiting."""
        async with self._parse_semaphore:
            return await asyncio.to_thread(
                self._parse_single_file, file_path, repo_path
            )

    async def _parse_files(self, files: list[Path], repo_path: Path) -> list:
        """Parse files using AST parser.

        Offloads blocking AST parsing to thread pool to avoid blocking
        the event loop. Files are parsed concurrently using asyncio.gather,
        with concurrency limited by _parse_semaphore.
        """
        all_entities = []

        # Parse files concurrently with limited parallelism
        tasks = [
            self._parse_file_with_limit(file_path, repo_path) for file_path in files
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Parse task failed: {result}")
            elif result:
                all_entities.extend(result)

        return all_entities

    def _add_entity_to_graph(self, entity, repo_id: str, branch: str) -> None:
        """Add a single entity to Neptune graph (sync implementation)."""
        try:
            # Create unique entity ID
            entity_id = f"{repo_id}::{entity.file_path}::{entity.name}"

            # Add entity to graph
            self.neptune.add_code_entity(
                name=entity.name,
                entity_type=entity.entity_type,
                file_path=entity.file_path,
                line_number=entity.line_number,
                parent=entity.parent_entity,
                metadata={
                    "repository": repo_id,
                    "branch": branch,
                    "entity_id": entity_id,
                    **(entity.attributes or {}),
                },
            )

            # Add relationships
            if entity.dependencies:
                for dep in entity.dependencies:
                    self.neptune.add_relationship(
                        from_entity=entity.name,
                        to_entity=dep,
                        relationship="DEPENDS_ON",
                        metadata={"repository": repo_id},
                    )

            if entity.parent_entity:
                self.neptune.add_relationship(
                    from_entity=entity.parent_entity,
                    to_entity=entity.name,
                    relationship="CONTAINS",
                    metadata={"repository": repo_id},
                )

        except Exception as e:
            logger.warning(f"Failed to add entity {entity.name}: {e}")

    async def _add_entity_with_limit(self, entity, repo_id: str, branch: str) -> None:
        """Add entity to graph with concurrency limiting."""
        async with self._graph_semaphore:
            await asyncio.to_thread(self._add_entity_to_graph, entity, repo_id, branch)

    async def _populate_graph(
        self,
        entities: list,
        repository_url: str,
        branch: str,
        upsert: bool = False,
    ):
        """Populate Neptune graph with code entities.

        Offloads blocking Neptune calls to thread pool to avoid blocking
        the event loop. Entities are processed concurrently with limited
        parallelism controlled by _graph_semaphore.
        """
        repo_id = self._url_to_repo_id(repository_url)

        # Process entities concurrently with limited parallelism
        tasks = [
            self._add_entity_with_limit(entity, repo_id, branch) for entity in entities
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any failures
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Graph population task failed: {result}")

    def _read_file_content(self, file_path: Path) -> str | None:
        """Read file content synchronously with streaming for large files.

        Security features:
        - Rejects symlinks to prevent directory traversal attacks
        - Verifies file is within expected clone directory
        - Uses streaming read for large files to limit memory usage

        Uses streaming read for files larger than max_content_size_bytes to
        avoid loading full files into memory when only a prefix is needed
        for embedding generation.
        """
        try:
            # Security: Reject symlinks to prevent reading files outside repository
            # A malicious repo could contain a symlink to /etc/passwd or other sensitive files
            if file_path.is_symlink():
                logger.warning(f"Skipping symlink for security: {file_path}")
                return None

            # Security: Verify file is within expected clone directory
            # Prevents path traversal even if symlink check is bypassed
            try:
                resolved_path = file_path.resolve()
                clone_dir_resolved = self.clone_dir.resolve()
                resolved_path.relative_to(clone_dir_resolved)
            except ValueError:
                logger.warning(
                    f"File outside clone directory, skipping for security: {file_path}"
                )
                return None

            file_size = file_path.stat().st_size

            # Skip nearly empty files
            if file_size < 10:
                return None

            # For large files, stream and truncate at max_content_size
            if file_size > self.max_content_size_bytes:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    # Read only what we need for embeddings
                    content = f.read(self.max_content_size_bytes)
                    logger.debug(
                        f"Truncated large file: {file_path} "
                        f"({file_size} -> {len(content)} bytes)"
                    )
                    return content

            # Small files: read entirely
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            return content

        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return None

    def _index_single_embedding(
        self,
        doc_id: str,
        content: str,
        embedding: list[float],
        repo_id: str,
        relative_path: str,
        language: str,
    ) -> bool:
        """Index a single embedding in OpenSearch (sync implementation)."""
        try:
            self.opensearch.index_embedding(
                doc_id=doc_id,
                text=content[:5000],  # Truncate for storage
                vector=embedding,
                metadata={
                    "repository": repo_id,
                    "file_path": relative_path,
                    "language": language,
                    "indexed_at": datetime.now().isoformat(),
                },
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to index embedding {doc_id}: {e}")
            return False

    def _scan_content_for_injection(self, content: str, file_path: str) -> str | None:
        """Scan ingested content through guardrails L1 (normalization) and L2 (pattern matching).

        Detects prompt injection payloads embedded in code comments, docstrings,
        or string literals before the content is indexed into Neptune/OpenSearch.

        Args:
            content: Raw file content to scan
            file_path: Relative file path (for logging)

        Returns:
            Normalized content if safe, None if content should be quarantined
        """
        self._content_scan_stats["scanned"] += 1

        try:
            # L1: Normalize (Unicode NFKC, homograph mapping, zero-width removal)
            normalization_result = normalize_text(content)
            normalized_content = normalization_result.normalized_text

            # L2: Pattern matching (regex blocklist for injection patterns)
            pattern_result = match_patterns(normalized_content)

            if pattern_result.threat_level.value >= 3:  # HIGH or CRITICAL
                self._content_scan_stats["quarantined"] += 1
                logger.warning(
                    f"Prompt injection detected in {file_path}: "
                    f"threat_level={pattern_result.threat_level.name}, "
                    f"categories={[m.category for m in pattern_result.matches]}"
                )
                return None

            return normalized_content

        except Exception as e:
            logger.warning(f"Content scan failed for {file_path}: {e}")
            # Fail open for scan errors — content passes through unnormalized
            # but the error is logged for investigation
            return content

    async def _prepare_file_for_indexing(
        self,
        file_path: Path,
        repo_path: Path,
        repo_id: str,
    ) -> dict[str, Any] | None:
        """Prepare a file for batch indexing: read content and generate embedding.

        Returns a document dict ready for bulk_index_embeddings, or None if preparation fails.
        """
        async with self._index_semaphore:
            try:
                # Offload blocking file read to thread
                content = await asyncio.to_thread(self._read_file_content, file_path)
                if not content:
                    return None

                relative_path = str(file_path.relative_to(repo_path))
                doc_id = f"{repo_id}::{relative_path}"

                # Scan content through guardrails L1+L2 before indexing
                scanned_content = await asyncio.to_thread(
                    self._scan_content_for_injection, content, relative_path
                )
                if scanned_content is None:
                    logger.info(f"Quarantined {relative_path} — skipping indexing")
                    return None

                # Generate embedding (already handles sync/async internally)
                embedding = await self._generate_embedding(scanned_content)

                if embedding:
                    return {
                        "id": doc_id,
                        "text": content[:5000],  # Truncate for storage
                        "vector": embedding,
                        "metadata": {
                            "repository": repo_id,
                            "file_path": relative_path,
                            "language": file_path.suffix.lstrip("."),
                            "indexed_at": datetime.now().isoformat(),
                        },
                    }
                return None

            except Exception as e:
                logger.warning(f"Failed to prepare {file_path} for indexing: {e}")
                return None

    def _bulk_index_sync(self, documents: list[dict[str, Any]]) -> int:
        """Perform bulk indexing synchronously (for thread pool execution)."""
        import time

        start_time = time.time()
        try:
            result = self.opensearch.bulk_index_embeddings(documents, refresh=False)
            success_count = result.get("success_count", 0)

            # Record OpenSearch bulk latency and success
            latency_ms = (time.time() - start_time) * 1000
            self.monitor.track_database_query(
                database="opensearch",
                operation="bulk_index",
                latency_ms=latency_ms,
                result_count=success_count,
                cache_hit=False,
            )

            return success_count
        except Exception as e:
            # Record failed bulk operation
            latency_ms = (time.time() - start_time) * 1000
            self.monitor.track_database_query(
                database="opensearch",
                operation="bulk_index",
                latency_ms=latency_ms,
                result_count=0,
                cache_hit=False,
            )
            self.monitor.record_error("opensearch.bulk_index", e)
            logger.warning(f"Bulk indexing failed: {e}")
            return 0

    async def _index_embeddings(
        self,
        files: list[Path],
        repo_path: Path,
        repository_url: str,
        upsert: bool = False,
    ) -> int:
        """Generate embeddings and index in OpenSearch using bulk API.

        Optimized for throughput:
        1. Prepares documents concurrently with limited parallelism
        2. Batches documents for bulk indexing (reduces HTTP overhead)
        3. Uses refresh=False during bulk operations for better shard throughput

        Args:
            files: List of files to index
            repo_path: Path to the repository root
            repository_url: Repository URL for metadata
            upsert: Whether to upsert (ignored, bulk API is idempotent by doc_id)

        Returns:
            Number of successfully indexed documents
        """
        repo_id = self._url_to_repo_id(repository_url)

        # Step 1: Prepare all documents concurrently (read content + generate embeddings)
        prepare_tasks = [
            self._prepare_file_for_indexing(file_path, repo_path, repo_id)
            for file_path in files
        ]

        prepare_results = await asyncio.gather(*prepare_tasks, return_exceptions=True)

        # Collect successful document preparations
        documents: list[dict[str, Any]] = []
        for result in prepare_results:
            if isinstance(result, Exception):
                logger.warning(f"Document preparation failed: {result}")
            elif result is not None:
                documents.append(result)

        if not documents:
            logger.info("No documents prepared for indexing")
            return 0

        # Step 2: Batch documents and bulk index
        total_indexed = 0
        batch_count = 0

        for i in range(0, len(documents), self.opensearch_bulk_size):
            batch = documents[i : i + self.opensearch_bulk_size]
            batch_count += 1

            # Offload bulk indexing to thread pool
            indexed = await asyncio.to_thread(self._bulk_index_sync, batch)
            total_indexed += indexed

            logger.debug(
                f"Bulk indexed batch {batch_count}: {indexed}/{len(batch)} documents"
            )

        logger.info(
            f"Bulk indexing complete: {total_indexed}/{len(documents)} documents "
            f"in {batch_count} batches"
        )

        return total_indexed

    def _generate_embedding_sync(self, truncated: str) -> list[float] | None:
        """Generate embedding synchronously (for thread pool execution)."""
        if hasattr(self.embeddings, "generate_embedding"):
            result = self.embeddings.generate_embedding(truncated)
            return result if isinstance(result, list) else None
        elif hasattr(self.embeddings, "embed"):
            embed_result = self.embeddings.embed(truncated)
            return embed_result if isinstance(embed_result, list) else None
        else:
            # Mock embedding for testing
            return [0.1] * 1024

    async def _generate_embedding(self, text: str) -> list[float] | None:
        """Generate embedding for text.

        Offloads blocking embedding generation to thread pool to avoid
        blocking the event loop.
        """
        try:
            # Truncate to avoid token limits
            truncated = text[:8000]

            # Check if embedding service has async support
            if hasattr(self.embeddings, "generate_embedding"):
                # Try calling to see if it returns a coroutine
                result = self.embeddings.generate_embedding(truncated)
                if hasattr(result, "__await__"):
                    # It's an async embedding service
                    embedding: list[float] | None = await result
                    return embedding
                # It's synchronous - we already have the result
                return result if isinstance(result, list) else None

            # Offload sync embedding generation to thread pool
            return await asyncio.to_thread(self._generate_embedding_sync, truncated)

        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")
            return None

    def _generate_job_id(self, repository_url: str, branch: str) -> str:
        """Generate a unique job ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_input = f"{repository_url}:{branch}:{timestamp}"
        short_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        return f"ingest-{short_hash}-{timestamp}"

    def _url_to_repo_id(self, repository_url: str) -> str:
        """Convert repository URL to a safe ID."""
        # Extract org/repo from URL
        # https://github.com/org/repo.git -> org-repo
        url = repository_url.rstrip("/").rstrip(".git")
        parts = url.split("/")
        if len(parts) >= 2:
            return f"{parts[-2]}-{parts[-1]}"
        return hashlib.sha256(repository_url.encode()).hexdigest()[:16]

    def _get_auth_header(self, url: str) -> str | None:
        """Get authentication header for git operations.

        Returns an HTTP Authorization header value for secure git authentication.
        This avoids embedding tokens in URLs which could leak via logs, process
        listings, or git config.

        Authentication priority:
        1. GitHub App installation token (preferred, auto-generated from SSM credentials)
        2. Legacy PAT token (fallback, from GITHUB_TOKEN env var)
        3. None (public repos only)

        Returns:
            Authorization header value (e.g., "Basic base64...") or None
        """
        if "github.com" not in url:
            return None

        token = None
        token_type = None

        # Priority 1: GitHub App authentication
        if self.github_app_auth:
            try:
                app_token = self.github_app_auth.get_installation_token()
                if app_token:
                    token = app_token
                    token_type = "GitHub App installation token"
            except Exception as e:
                logger.warning(f"GitHub App token generation failed: {e}")

        # Priority 2: Legacy PAT token
        if not token and self.github_token:
            token = self.github_token
            token_type = "legacy GitHub PAT"

        if token:
            # Encode as Basic auth: base64("x-access-token:TOKEN")
            # This format works for both GitHub App tokens and PATs
            credentials = f"x-access-token:{token}"
            encoded = base64.b64encode(credentials.encode()).decode()
            logger.info(f"Using {token_type} for authentication")
            return f"Basic {encoded}"

        logger.warning("No GitHub authentication available for private repository")
        return None

    def _get_git_auth_options(self, url: str) -> list[str]:
        """Get git command-line options for authentication.

        Returns a list of git config options to pass credentials securely
        via HTTP headers instead of embedding in URLs.

        Example: ['-c', 'http.extraHeader=Authorization: Basic base64...']
        """
        auth_header = self._get_auth_header(url)
        if auth_header:
            return ["-c", f"http.extraHeader=Authorization: {auth_header}"]
        return []

    def _secure_clone(
        self,
        url: str,
        to_path: str,
        branch: str,
        shallow: bool = False,
    ) -> None:
        """Clone a repository with secure credential handling.

        Uses git subprocess with http.extraHeader to pass credentials securely
        instead of embedding tokens in the URL.

        Args:
            url: Repository URL (without embedded credentials)
            to_path: Local path to clone to
            branch: Branch to checkout
            shallow: If True, use depth=1 for shallow clone
        """
        cmd = ["git"]

        # Add auth options (credentials passed via header, not URL)
        cmd.extend(self._get_git_auth_options(url))

        cmd.extend(["clone", "--branch", branch])

        if shallow:
            cmd.extend(["--depth", "1"])

        cmd.extend([url, to_path])

        logger.info(f"Cloning repository: {url} -> {to_path}")

        try:
            # Execute via SecureCommandExecutor (shell=False, allowlist-validated)
            executor = SecureCommandExecutor(
                timeout_seconds=600,  # 10 minute timeout for large repos
                log_commands=True,
            )
            result = executor.execute(cmd, check=True)
            logger.debug(f"Clone completed: {result.stdout}")
        except Exception as e:
            # Sanitize error output to avoid leaking credentials
            error_msg = self._sanitize_git_output(str(e))
            raise GitCommandError(cmd[:3], 1, error_msg) from e

    def _secure_fetch(self, repo_path: Path) -> None:
        """Fetch updates for a repository with secure credential handling.

        Args:
            repo_path: Path to the local repository
        """
        repo = Repo(repo_path)
        origin_url = repo.remotes.origin.url

        cmd = ["git"]
        cmd.extend(self._get_git_auth_options(origin_url))
        cmd.extend(["fetch", "origin"])

        try:
            executor = SecureCommandExecutor(
                working_dir=str(repo_path),
                timeout_seconds=300,
                log_commands=True,
            )
            executor.execute(cmd, check=True)
        except Exception as e:
            stderr = self._sanitize_git_output(str(e))
            raise GitCommandError(["git", "fetch"], 1, stderr) from e

    def _secure_pull(self, repo_path: Path, branch: str) -> None:
        """Pull updates for a repository with secure credential handling.

        Args:
            repo_path: Path to the local repository
            branch: Branch to pull
        """
        repo = Repo(repo_path)
        origin_url = repo.remotes.origin.url

        # Checkout the branch first
        repo.git.checkout(branch)

        cmd = ["git"]
        cmd.extend(self._get_git_auth_options(origin_url))
        cmd.extend(["pull", "origin", branch])

        try:
            executor = SecureCommandExecutor(
                working_dir=str(repo_path),
                timeout_seconds=300,
                log_commands=True,
            )
            executor.execute(cmd, check=True)
        except Exception as e:
            stderr = self._sanitize_git_output(str(e))
            raise GitCommandError(["git", "pull"], 1, stderr) from e

    def _sanitize_git_output(self, output: str) -> str:
        """Remove potential credentials from git command output.

        Scrubs common token patterns to prevent credential leakage in logs/errors.
        """
        import re

        # Patterns for common token formats
        patterns = [
            r"ghp_[A-Za-z0-9]{36,}",  # GitHub PAT (classic)
            r"github_pat_[A-Za-z0-9_]{82,}",  # GitHub PAT (fine-grained)
            r"ghs_[A-Za-z0-9]{36,}",  # GitHub App installation token
            r"ghu_[A-Za-z0-9]{36,}",  # GitHub user-to-server token
            r"gho_[A-Za-z0-9]{36,}",  # GitHub OAuth token
            r"x-access-token:[^\s@]+",  # Token in URL format
            r"Authorization:\s*Basic\s+[A-Za-z0-9+/=]+",  # Basic auth header
            r"Bearer\s+[A-Za-z0-9._-]+",  # Bearer token
        ]

        result = output
        for pattern in patterns:
            result = re.sub(pattern, "[REDACTED]", result, flags=re.IGNORECASE)

        return result

    def _get_current_commit(self, repo_path: Path) -> str:
        """Get the current commit hash."""
        try:
            repo = Repo(repo_path)
            return repo.head.commit.hexsha[:8]
        except Exception:
            return "unknown"
