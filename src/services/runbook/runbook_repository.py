"""
Runbook Repository Service

Stores, indexes, and retrieves runbooks with support for semantic search
and incident pattern matching.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class RunbookMetadata:
    """Metadata for a stored runbook."""

    id: str
    title: str
    file_path: str
    error_signatures: list[str]
    services: list[str]
    keywords: list[str]
    incident_types: list[str]
    created_at: datetime
    updated_at: datetime
    auto_generated: bool
    resolution_count: int = 0
    avg_resolution_time: float = 0.0
    content_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        return {
            "id": {"S": self.id},
            "title": {"S": self.title},
            "file_path": {"S": self.file_path},
            "error_signatures": {"SS": self.error_signatures or ["none"]},
            "services": {"SS": self.services or ["general"]},
            "keywords": {"SS": self.keywords or ["runbook"]},
            "incident_types": {"SS": self.incident_types or ["general"]},
            "created_at": {"S": self.created_at.isoformat()},
            "updated_at": {"S": self.updated_at.isoformat()},
            "auto_generated": {"BOOL": self.auto_generated},
            "resolution_count": {"N": str(self.resolution_count)},
            "avg_resolution_time": {"N": str(self.avg_resolution_time)},
            "content_hash": {"S": self.content_hash},
            "metadata": {"S": json.dumps(self.metadata)},
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "RunbookMetadata":
        """Create from DynamoDB item."""
        return cls(
            id=item["id"]["S"],
            title=item["title"]["S"],
            file_path=item["file_path"]["S"],
            error_signatures=list(item.get("error_signatures", {}).get("SS", [])),
            services=list(item.get("services", {}).get("SS", [])),
            keywords=list(item.get("keywords", {}).get("SS", [])),
            incident_types=list(item.get("incident_types", {}).get("SS", [])),
            created_at=datetime.fromisoformat(item["created_at"]["S"]),
            updated_at=datetime.fromisoformat(item["updated_at"]["S"]),
            auto_generated=item.get("auto_generated", {}).get("BOOL", False),
            resolution_count=int(item.get("resolution_count", {}).get("N", "0")),
            avg_resolution_time=float(
                item.get("avg_resolution_time", {}).get("N", "0")
            ),
            content_hash=item.get("content_hash", {}).get("S", ""),
            metadata=json.loads(item.get("metadata", {}).get("S", "{}")),
        )


class RunbookRepository:
    """
    Repository for storing and retrieving runbooks.

    Supports:
    - File system storage (primary)
    - DynamoDB index for fast lookups
    - Semantic search via keywords and signatures
    - Usage tracking for resolution metrics
    """

    def __init__(
        self,
        region: str = "us-east-1",
        project_name: str = "aura",
        environment: str = "dev",
        runbooks_dir: str = "docs/runbooks",
        use_dynamodb: bool = True,
    ):
        """
        Initialize the runbook repository.

        Args:
            region: AWS region
            project_name: Project name for table naming
            environment: Environment (dev, qa, prod)
            runbooks_dir: Local directory for runbook files
            use_dynamodb: Whether to use DynamoDB for indexing
        """
        self.region = region
        self.project_name = project_name
        self.environment = environment
        self.runbooks_dir = Path(runbooks_dir)
        self.use_dynamodb = use_dynamodb

        self.table_name = f"{project_name}-runbooks-{environment}"

        if use_dynamodb:
            self.dynamodb_client = boto3.client("dynamodb", region_name=region)

    async def save_runbook(
        self,
        title: str,
        content: str,
        filename: str,
        error_signatures: list[str],
        services: list[str],
        keywords: list[str],
        incident_types: list[str],
        auto_generated: bool = True,
        metadata: Optional[dict] = None,
    ) -> RunbookMetadata:
        """
        Save a new runbook to the repository.

        Args:
            title: Runbook title
            content: Markdown content
            filename: Filename for the runbook
            error_signatures: Error patterns this runbook addresses
            services: AWS services involved
            keywords: Search keywords
            incident_types: Types of incidents addressed
            auto_generated: Whether this was auto-generated
            metadata: Additional metadata

        Returns:
            Metadata for the saved runbook
        """
        # Ensure directory exists
        self.runbooks_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique ID
        runbook_id = self._generate_id(filename)

        # Full path
        file_path = self.runbooks_dir / filename

        # Calculate content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Create metadata
        now = datetime.now()
        runbook_metadata = RunbookMetadata(
            id=runbook_id,
            title=title,
            file_path=str(file_path),
            error_signatures=error_signatures,
            services=services,
            keywords=keywords,
            incident_types=incident_types,
            created_at=now,
            updated_at=now,
            auto_generated=auto_generated,
            content_hash=content_hash,
            metadata=metadata or {},
        )

        # Write file
        file_path.write_text(content)
        logger.info(f"Saved runbook to {file_path}")

        # Index in DynamoDB
        if self.use_dynamodb:
            await self._index_runbook(runbook_metadata)

        return runbook_metadata

    async def update_runbook(
        self,
        file_path: str,
        content: str,
        additional_signatures: Optional[list[str]] = None,
        additional_keywords: Optional[list[str]] = None,
    ) -> RunbookMetadata:
        """
        Update an existing runbook.

        Args:
            file_path: Path to the runbook
            content: New content
            additional_signatures: New error signatures to add
            additional_keywords: New keywords to add

        Returns:
            Updated metadata
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Runbook not found: {file_path}")

        # Get existing metadata
        existing = await self.get_by_path(file_path)
        if not existing:
            raise ValueError(f"No metadata found for runbook: {file_path}")

        # Update content
        path.write_text(content)
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Merge signatures and keywords
        signatures = list(
            set(existing.error_signatures + (additional_signatures or []))
        )
        keywords = list(set(existing.keywords + (additional_keywords or [])))

        # Update metadata
        updated_metadata = RunbookMetadata(
            id=existing.id,
            title=existing.title,
            file_path=file_path,
            error_signatures=signatures,
            services=existing.services,
            keywords=keywords,
            incident_types=existing.incident_types,
            created_at=existing.created_at,
            updated_at=datetime.now(),
            auto_generated=existing.auto_generated,
            resolution_count=existing.resolution_count,
            avg_resolution_time=existing.avg_resolution_time,
            content_hash=content_hash,
            metadata=existing.metadata,
        )

        # Update index
        if self.use_dynamodb:
            await self._index_runbook(updated_metadata)

        return updated_metadata

    async def get_by_id(self, runbook_id: str) -> Optional[RunbookMetadata]:
        """Get runbook metadata by ID."""
        if not self.use_dynamodb:
            return await self._get_from_filesystem(runbook_id)

        try:
            response = self.dynamodb_client.get_item(
                TableName=self.table_name,
                Key={"id": {"S": runbook_id}},
            )

            if "Item" in response:
                return RunbookMetadata.from_dynamodb_item(response["Item"])
            return None

        except ClientError as e:
            logger.error(f"Error getting runbook {runbook_id}: {e}")
            return None

    async def get_by_path(self, file_path: str) -> Optional[RunbookMetadata]:
        """Get runbook metadata by file path."""
        if not self.use_dynamodb:
            return await self._get_from_filesystem_by_path(file_path)

        try:
            # Query by file_path GSI
            response = self.dynamodb_client.query(
                TableName=self.table_name,
                IndexName="file_path-index",
                KeyConditionExpression="file_path = :path",
                ExpressionAttributeValues={":path": {"S": file_path}},
            )

            items = response.get("Items", [])
            if items:
                return RunbookMetadata.from_dynamodb_item(items[0])
            return None

        except ClientError as e:
            logger.error(f"Error getting runbook by path {file_path}: {e}")
            return await self._get_from_filesystem_by_path(file_path)

    async def search(
        self,
        error_pattern: Optional[str] = None,
        service: Optional[str] = None,
        keyword: Optional[str] = None,
        incident_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[RunbookMetadata]:
        """
        Search for runbooks matching criteria.

        Args:
            error_pattern: Error pattern to match
            service: Service to filter by
            keyword: Keyword to search for
            incident_type: Incident type to filter
            limit: Maximum results

        Returns:
            List of matching runbook metadata
        """
        results = []

        if self.use_dynamodb:
            results = await self._search_dynamodb(
                error_pattern, service, keyword, incident_type, limit
            )
        else:
            results = await self._search_filesystem(
                error_pattern, service, keyword, incident_type, limit
            )

        return results[:limit]

    async def find_by_error_signature(
        self,
        signature: str,
        threshold: float = 0.7,
    ) -> list[tuple[RunbookMetadata, float]]:
        """
        Find runbooks that match an error signature.

        Args:
            signature: Error pattern to match
            threshold: Minimum match score

        Returns:
            List of (metadata, score) tuples
        """
        matches = []

        # Get all runbooks
        all_runbooks = await self.list_all()

        for runbook in all_runbooks:
            score = self._calculate_signature_match(signature, runbook.error_signatures)
            if score >= threshold:
                matches.append((runbook, score))

        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches

    async def record_usage(
        self,
        runbook_id: str,
        resolution_time_minutes: float,
    ) -> None:
        """
        Record that a runbook was used for incident resolution.

        Args:
            runbook_id: The runbook that was used
            resolution_time_minutes: Time to resolution
        """
        runbook = await self.get_by_id(runbook_id)
        if not runbook:
            return

        # Update resolution metrics
        new_count = runbook.resolution_count + 1
        new_avg = (
            runbook.avg_resolution_time * runbook.resolution_count
            + resolution_time_minutes
        ) / new_count

        if self.use_dynamodb:
            try:
                self.dynamodb_client.update_item(
                    TableName=self.table_name,
                    Key={"id": {"S": runbook_id}},
                    UpdateExpression="SET resolution_count = :count, avg_resolution_time = :avg",
                    ExpressionAttributeValues={
                        ":count": {"N": str(new_count)},
                        ":avg": {"N": str(new_avg)},
                    },
                )
            except ClientError as e:
                logger.error(f"Error recording usage: {e}")

    async def list_all(self) -> list[RunbookMetadata]:
        """List all runbooks in the repository."""
        if self.use_dynamodb:
            return await self._list_all_dynamodb()
        else:
            return await self._list_all_filesystem()

    async def delete(self, runbook_id: str) -> bool:
        """Delete a runbook from the repository."""
        runbook = await self.get_by_id(runbook_id)
        if not runbook:
            return False

        # Delete file
        path = Path(runbook.file_path)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted runbook file: {path}")

        # Delete from index
        if self.use_dynamodb:
            try:
                self.dynamodb_client.delete_item(
                    TableName=self.table_name,
                    Key={"id": {"S": runbook_id}},
                )
            except ClientError as e:
                logger.error(f"Error deleting from index: {e}")
                return False

        return True

    async def sync_index(self) -> int:
        """
        Synchronize DynamoDB index with filesystem.

        Returns:
            Number of runbooks indexed
        """
        if not self.use_dynamodb:
            return 0

        count = 0
        for runbook_path in self.runbooks_dir.glob("*.md"):
            try:
                # Parse runbook to extract metadata
                metadata = self._parse_runbook_file(runbook_path)
                if metadata:
                    await self._index_runbook(metadata)
                    count += 1
            except Exception as e:
                logger.warning(f"Error indexing {runbook_path}: {e}")

        logger.info(f"Synced {count} runbooks to index")
        return count

    # Private methods

    def _generate_id(self, filename: str) -> str:
        """Generate a unique ID from filename."""
        base = Path(filename).stem.lower()
        base = re.sub(r"[^a-z0-9]", "-", base)
        return base[:50]

    async def _index_runbook(self, metadata: RunbookMetadata) -> None:
        """Index a runbook in DynamoDB."""
        try:
            self.dynamodb_client.put_item(
                TableName=self.table_name,
                Item=metadata.to_dynamodb_item(),
            )
        except ClientError as e:
            logger.error(f"Error indexing runbook: {e}")

    async def _search_dynamodb(
        self,
        error_pattern: Optional[str],
        service: Optional[str],
        keyword: Optional[str],
        incident_type: Optional[str],
        limit: int,
    ) -> list[RunbookMetadata]:
        """Search DynamoDB for matching runbooks."""
        # Build filter expression
        filters = []
        values = {}

        if service:
            filters.append("contains(services, :service)")
            values[":service"] = {"S": service}

        if keyword:
            filters.append("contains(keywords, :keyword)")
            values[":keyword"] = {"S": keyword}

        if incident_type:
            filters.append("contains(incident_types, :type)")
            values[":type"] = {"S": incident_type}

        try:
            # Build params with proper types
            if filters:
                response = self.dynamodb_client.scan(
                    TableName=self.table_name,
                    Limit=limit,
                    FilterExpression=" AND ".join(filters),
                    ExpressionAttributeValues=values,
                )
            else:
                response = self.dynamodb_client.scan(
                    TableName=self.table_name,
                    Limit=limit,
                )

            results = [
                RunbookMetadata.from_dynamodb_item(item)
                for item in response.get("Items", [])
            ]

            # Filter by error pattern if specified
            if error_pattern:
                results = [
                    r
                    for r in results
                    if self._calculate_signature_match(
                        error_pattern, r.error_signatures
                    )
                    > 0.5
                ]

            return results

        except ClientError as e:
            logger.error(f"Error searching DynamoDB: {e}")
            return []

    async def _search_filesystem(
        self,
        error_pattern: Optional[str],
        service: Optional[str],
        keyword: Optional[str],
        incident_type: Optional[str],
        limit: int,
    ) -> list[RunbookMetadata]:
        """Search filesystem for matching runbooks."""
        results = []

        for runbook_path in self.runbooks_dir.glob("*.md"):
            metadata = self._parse_runbook_file(runbook_path)
            if not metadata:
                continue

            # Apply filters
            if service and service not in metadata.services:
                continue
            if keyword and keyword not in metadata.keywords:
                continue
            if incident_type and incident_type not in metadata.incident_types:
                continue
            if error_pattern:
                if (
                    self._calculate_signature_match(
                        error_pattern, metadata.error_signatures
                    )
                    < 0.5
                ):
                    continue

            results.append(metadata)

            if len(results) >= limit:
                break

        return results

    async def _list_all_dynamodb(self) -> list[RunbookMetadata]:
        """List all runbooks from DynamoDB."""
        try:
            response = self.dynamodb_client.scan(TableName=self.table_name)
            return [
                RunbookMetadata.from_dynamodb_item(item)
                for item in response.get("Items", [])
            ]
        except ClientError as e:
            logger.error(f"Error listing from DynamoDB: {e}")
            return []

    async def _list_all_filesystem(self) -> list[RunbookMetadata]:
        """List all runbooks from filesystem."""
        results = []
        for runbook_path in self.runbooks_dir.glob("*.md"):
            metadata = self._parse_runbook_file(runbook_path)
            if metadata:
                results.append(metadata)
        return results

    async def _get_from_filesystem(self, runbook_id: str) -> Optional[RunbookMetadata]:
        """Get runbook from filesystem by ID."""
        for runbook_path in self.runbooks_dir.glob("*.md"):
            if self._generate_id(runbook_path.name) == runbook_id:
                return self._parse_runbook_file(runbook_path)
        return None

    async def _get_from_filesystem_by_path(
        self, file_path: str
    ) -> Optional[RunbookMetadata]:
        """Get runbook from filesystem by path."""
        path = Path(file_path)
        if path.exists():
            return self._parse_runbook_file(path)
        return None

    def _parse_runbook_file(self, path: Path) -> Optional[RunbookMetadata]:
        """Parse a runbook file to extract metadata."""
        try:
            content = path.read_text()

            # Extract title
            title_match = re.search(
                r"^#\s+(?:Runbook:\s*)?(.+)$", content, re.MULTILINE
            )
            title = title_match.group(1) if title_match else path.stem

            # Extract services from content
            services = self._extract_services(content)

            # Extract keywords
            keywords = self._extract_keywords(content)

            # Calculate content hash
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

            # Get file timestamps
            stat = path.stat()
            created = datetime.fromtimestamp(stat.st_ctime)
            updated = datetime.fromtimestamp(stat.st_mtime)

            return RunbookMetadata(
                id=self._generate_id(path.name),
                title=title,
                file_path=str(path),
                error_signatures=self._extract_error_signatures(content),
                services=services,
                keywords=keywords,
                incident_types=self._infer_incident_types(content),
                created_at=created,
                updated_at=updated,
                auto_generated="Auto-Generated" in content,
                content_hash=content_hash,
            )

        except Exception as e:
            logger.warning(f"Error parsing {path}: {e}")
            return None

    def _extract_services(self, content: str) -> list[str]:
        """Extract AWS services mentioned in content."""
        services: set[str] = set()
        service_patterns = [
            r"(?:AWS\s+)?(CodeBuild|CloudFormation|ECR|EKS|IAM|Bedrock|S3|DynamoDB|Lambda)",
            r"(docker|kubernetes|container)",
        ]

        for pattern in service_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            services.update(m.lower() for m in matches)

        return list(services) or ["general"]

    def _extract_keywords(self, content: str) -> list[str]:
        """Extract keywords from content."""
        keywords: set[str] = set()

        # Look for common patterns
        keyword_patterns = [
            r"(?:error|issue|problem):\s*(\w+)",
            r"(?:fix|resolve|solution):\s*(\w+)",
        ]

        for pattern in keyword_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            keywords.update(m.lower() for m in matches)

        # Add title words
        title_match = re.search(r"^#\s+(?:Runbook:\s*)?(.+)$", content, re.MULTILINE)
        if title_match:
            title_words = re.findall(r"\w+", title_match.group(1))
            keywords.update(w.lower() for w in title_words if len(w) > 3)

        return list(keywords)[:20]  # Limit to 20 keywords

    def _extract_error_signatures(self, content: str) -> list[str]:
        """Extract error signatures from content."""
        signatures = []

        # Look for code blocks with error patterns
        code_blocks = re.findall(r"```[^\n]*\n(.*?)```", content, re.DOTALL)
        for block in code_blocks:
            # Look for error-like patterns
            if re.search(r"error|failed|denied|not found", block, re.IGNORECASE):
                # Extract a representative pattern
                lines = block.strip().split("\n")
                for line in lines[:3]:  # First 3 lines
                    if len(line) > 10:
                        signatures.append(line[:100])

        return signatures[:5]  # Limit to 5 signatures

    def _infer_incident_types(self, content: str) -> list[str]:
        """Infer incident types from content."""
        types = []

        content_lower = content.lower()

        type_indicators = {
            "docker_build_fix": [
                "docker",
                "platform",
                "arm64",
                "amd64",
                "architecture",
            ],
            "iam_permission_fix": ["accessdenied", "permission", "iam policy"],
            "cloudformation_stack_fix": [
                "rollback_complete",
                "stack",
                "cloudformation",
            ],
            "ecr_conflict_resolution": ["alreadyexists", "ecr", "repository"],
            "shell_syntax_fix": ["[[", "bash", "shell", "/bin/sh"],
        }

        for incident_type, indicators in type_indicators.items():
            if any(ind in content_lower for ind in indicators):
                types.append(incident_type)

        return types or ["general"]

    def _calculate_signature_match(
        self,
        query_signature: str,
        runbook_signatures: list[str],
    ) -> float:
        """Calculate match score between query and runbook signatures."""
        if not runbook_signatures:
            return 0.0

        query_lower = query_signature.lower()
        best_score = 0.0

        for sig in runbook_signatures:
            sig_lower = sig.lower()

            # Exact substring match
            if query_lower in sig_lower or sig_lower in query_lower:
                return 1.0

            # Word overlap
            query_words = set(re.findall(r"\w+", query_lower))
            sig_words = set(re.findall(r"\w+", sig_lower))

            if query_words and sig_words:
                overlap = len(query_words & sig_words)
                total = len(query_words | sig_words)
                score = overlap / total if total > 0 else 0
                best_score = max(best_score, score)

        return best_score
