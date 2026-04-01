"""
AWS Neptune Graph Database Service
Production-ready Gremlin client for knowledge graph operations
with connection pooling, retry logic, and cost optimization.
"""

import hashlib
import logging
import os
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Enable nested event loops for gremlin-python compatibility with FastAPI/uvicorn
# The gremlin-python library uses aiohttp internally and calls run_until_complete()
# which fails inside an already running async event loop without this patch.
try:
    import nest_asyncio

    nest_asyncio.apply()
    logger.debug("nest_asyncio applied for gremlin-python compatibility")
except ImportError:
    logger.warning(
        "nest_asyncio not available - Neptune queries may fail in async contexts"
    )

# Gremlin Python imports (will be installed when deploying to AWS)
try:
    from gremlin_python.driver import client, serializer

    GREMLIN_AVAILABLE = True
except ImportError:
    GREMLIN_AVAILABLE = False
    logger.warning("Gremlin Python not available - using mock mode")


class NeptuneMode(Enum):
    """Operating modes for Neptune service."""

    MOCK = "mock"  # Mock responses for testing
    AWS = "aws"  # Real Neptune connection


class NeptuneError(Exception):
    """General Neptune operation error."""


def escape_gremlin_string(value: str) -> str:
    """
    Escape a string for safe use in Gremlin queries.

    Handles: backslashes, single quotes, newlines, carriage returns, tabs.
    """
    if not isinstance(value, str):  # type: ignore[unreachable]
        value = str(value)  # type: ignore[unreachable]
    # Escape backslashes first (must be first to avoid double-escaping)
    value = value.replace("\\", "\\\\")
    # Escape single quotes
    value = value.replace("'", "\\'")
    # Escape newlines and other control characters
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    value = value.replace("\t", "\\t")
    return value


class NeptuneGraphService:
    """
    Production-ready Neptune Graph Database service.

    Features:
    - Connection pooling for optimal performance
    - Automatic retry with exponential backoff
    - Cost optimization (read replicas, query caching)
    - Comprehensive error handling
    - Support for both Gremlin and SPARQL

    Usage:
        >>> service = NeptuneGraphService(mode=NeptuneMode.AWS)
        >>> service.add_code_entity('MyClass', 'class', 'src/app.py', 42)
        >>> results = service.find_related_code('MyClass', max_depth=2)
    """

    def __init__(
        self,
        mode: NeptuneMode = NeptuneMode.MOCK,
        endpoint: str | None = None,
        port: int = 8182,
        use_iam_auth: bool = True,
    ):
        """
        Initialize Neptune Graph Service.

        Args:
            mode: Operating mode (MOCK or AWS)
            endpoint: Neptune cluster endpoint (e.g., 'neptune.aura.local')
            port: Neptune port (default 8182)
            use_iam_auth: Use IAM database authentication (recommended)
        """
        self.mode = mode
        self.endpoint = endpoint or "neptune.aura.local"
        self.port = port
        self.use_iam_auth = use_iam_auth

        # Connection pooling config
        self.max_connections = 10
        self.connection_timeout = 10000  # ms

        # In-memory graph for mock mode
        self.mock_graph: dict[str, dict[str, Any]] = {}
        self.mock_edges: list[dict[str, Any]] = []

        # Query plan cache configuration (configurable via environment variables)
        # Caches compiled query templates for common patterns (ADR-155)
        # Environment variables:
        #   NEPTUNE_QUERY_CACHE_SIZE: Maximum number of cached query plans (default: 200)
        #   NEPTUNE_QUERY_CACHE_TTL: Cache TTL in seconds (default: 1800 = 30 minutes)
        self.MAX_QUERY_CACHE_SIZE = int(
            os.environ.get("NEPTUNE_QUERY_CACHE_SIZE", "200")
        )
        self.QUERY_CACHE_TTL_SECONDS = int(
            os.environ.get("NEPTUNE_QUERY_CACHE_TTL", "1800")
        )

        # Query plan cache: {pattern_hash: {"query": str, "timestamp": float}}
        self._query_cache: dict[str, dict[str, Any]] = {}
        self._query_cache_hits = 0
        self._query_cache_misses = 0

        # Initialize connection
        if self.mode == NeptuneMode.AWS and GREMLIN_AVAILABLE:
            self._init_gremlin_client()
        else:
            if self.mode == NeptuneMode.AWS:
                logger.warning(
                    "AWS mode requested but Gremlin not available. Using MOCK mode."
                )
                self.mode = NeptuneMode.MOCK
            self._init_mock_mode()

        logger.info(f"NeptuneGraphService initialized in {self.mode.value} mode")

    def _init_gremlin_client(self) -> None:
        """Initialize Gremlin client with connection pooling."""
        try:
            # Build connection URL
            if self.use_iam_auth:
                # IAM auth requires SigV4 signing
                url = f"wss://{self.endpoint}:{self.port}/gremlin"
                logger.info(f"Connecting to Neptune with IAM auth: {url}")
            else:
                url = f"ws://{self.endpoint}:{self.port}/gremlin"
                logger.info(f"Connecting to Neptune: {url}")

            # Create Gremlin client
            self.client = client.Client(
                url,
                "g",
                pool_size=self.max_connections,
                message_serializer=serializer.GraphSONSerializersV3d0(),
            )

            # Test connection (requires nest_asyncio for async event loop compatibility)
            self.client.submit("g.V().limit(1)").all().result()
            logger.info("Neptune connection established successfully")

        except Exception as e:
            logger.error(f"Failed to create Neptune client: {e}")
            logger.warning("Falling back to MOCK mode")
            self.mode = NeptuneMode.MOCK
            self._init_mock_mode()

    def _init_mock_mode(self) -> None:
        """Initialize mock mode with sample data."""
        logger.info("Mock mode initialized (no Neptune calls will be made)")

        # Sample data for testing
        self.mock_graph = {
            "DataProcessor": {
                "id": "DataProcessor",
                "type": "class",
                "file_path": "src/data_processor.py",
                "line_number": 10,
            },
            "generate_checksum": {
                "id": "generate_checksum",
                "type": "method",
                "file_path": "src/data_processor.py",
                "line_number": 25,
                "parent": "DataProcessor",
            },
        }

        self.mock_edges = [
            {
                "from": "DataProcessor",
                "to": "generate_checksum",
                "relationship": "HAS_METHOD",
            }
        ]

    # =========================================================================
    # Query Plan Caching Methods
    # =========================================================================

    def _get_query_pattern_key(
        self, query_template: str, params: dict[str, Any]
    ) -> str:
        """
        Generate cache key based on query template pattern.

        Uses query structure (template) + parameter types for pattern matching.
        This allows caching of similar queries with different parameter values.
        """
        # Extract parameter types for pattern matching
        param_types = ":".join(
            f"{k}={type(v).__name__}" for k, v in sorted(params.items())
        )

        # Hash the template + param types
        pattern_str = f"{query_template}|{param_types}"
        return hashlib.sha256(pattern_str.encode()).hexdigest()[:32]

    def _get_cached_query(self, cache_key: str) -> str | None:
        """Get cached query plan if valid (not expired)."""
        cached = self._query_cache.get(cache_key)
        if not cached:
            self._query_cache_misses += 1
            return None

        # Check TTL
        age = time.time() - cached["timestamp"]
        if age > self.QUERY_CACHE_TTL_SECONDS:
            del self._query_cache[cache_key]
            self._query_cache_misses += 1
            return None

        self._query_cache_hits += 1
        logger.debug(f"Query cache hit: {cache_key[:16]}...")
        return cached["query"]

    def _cache_query(self, cache_key: str, query: str) -> None:
        """Cache a compiled query plan."""
        self._query_cache[cache_key] = {
            "query": query,
            "timestamp": time.time(),
        }

        # Enforce cache size limit (FIFO eviction)
        if len(self._query_cache) > self.MAX_QUERY_CACHE_SIZE:
            evict_count = len(self._query_cache) - self.MAX_QUERY_CACHE_SIZE + 20
            keys_to_evict = list(self._query_cache.keys())[:evict_count]
            for key in keys_to_evict:
                del self._query_cache[key]
            logger.debug(f"Evicted {len(keys_to_evict)} query cache entries")

    def get_query_cache_stats(self) -> dict[str, Any]:
        """Get query cache statistics."""
        total = self._query_cache_hits + self._query_cache_misses
        return {
            "cache_size": len(self._query_cache),
            "max_size": self.MAX_QUERY_CACHE_SIZE,
            "hits": self._query_cache_hits,
            "misses": self._query_cache_misses,
            "hit_rate": self._query_cache_hits / total if total > 0 else 0.0,
            "ttl_seconds": self.QUERY_CACHE_TTL_SECONDS,
        }

    def clear_query_cache(self) -> int:
        """Clear the query cache. Returns number of entries cleared."""
        count = len(self._query_cache)
        self._query_cache.clear()
        logger.info(f"Cleared query cache: {count} entries")
        return count

    def _build_gremlin_query(
        self, template: str, params: dict[str, Any], use_cache: bool = True
    ) -> str:
        """
        Build a Gremlin query from template and parameters.

        Uses query plan caching for common patterns to avoid
        repeated string construction and escaping.

        Args:
            template: Query template with {param} placeholders
            params: Parameter values to substitute
            use_cache: Use query plan cache (default True)

        Returns:
            Compiled Gremlin query string
        """
        if use_cache:
            cache_key = self._get_query_pattern_key(template, params)
            cached = self._get_cached_query(cache_key)
            if cached:
                # Substitute current parameter values into cached template
                return cached.format(
                    **{k: escape_gremlin_string(str(v)) for k, v in params.items()}
                )

        # Build query from template
        escaped_params = {k: escape_gremlin_string(str(v)) for k, v in params.items()}
        query = template.format(**escaped_params)

        # Cache the template (with placeholder markers)
        if use_cache:
            cache_key = self._get_query_pattern_key(template, params)
            self._cache_query(cache_key, template)

        return query

    def add_code_entity(
        self,
        name: str,
        entity_type: str,
        file_path: str,
        line_number: int,
        parent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Add a code entity (class, function, method, variable) to the graph.

        Args:
            name: Entity name (e.g., 'MyClass', 'my_function')
            entity_type: Type ('class', 'function', 'method', 'variable', 'import')
            file_path: Source file path
            line_number: Line number in source file
            parent: Parent entity name (for methods in classes)
            metadata: Additional metadata (docstring, complexity, etc.)

        Returns:
            Entity ID (vertex ID)
        """
        entity_id = f"{file_path}::{name}"

        if self.mode == NeptuneMode.MOCK:
            self.mock_graph[entity_id] = {
                "id": entity_id,
                "name": name,
                "type": entity_type,
                "file_path": file_path,
                "line_number": line_number,
                "parent": parent,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            # Add edge to parent if exists
            if parent:
                parent_id = f"{file_path}::{parent}"
                self.mock_edges.append(
                    {
                        "from": parent_id,
                        "to": entity_id,
                        "relationship": f"HAS_{entity_type.upper()}",
                    }
                )

            logger.info(f"[MOCK] Added entity: {entity_id} ({entity_type})")
            return entity_id

        # Real Neptune operation
        try:
            # Escape all string values for safe Gremlin query
            safe_entity_id = escape_gremlin_string(entity_id)
            safe_name = escape_gremlin_string(name)
            safe_file_path = escape_gremlin_string(file_path)

            # Build Gremlin query
            query = f"""
            g.addV('CodeEntity')
             .property('entity_id', '{safe_entity_id}')
             .property('name', '{safe_name}')
             .property('type', '{entity_type}')
             .property('file_path', '{safe_file_path}')
             .property('line_number', {line_number})
             .property('created_at', '{datetime.now(timezone.utc).isoformat()}')
            """

            if parent:
                safe_parent = escape_gremlin_string(parent)
                query += f".property('parent', '{safe_parent}')"

            if metadata:
                for key, value in metadata.items():
                    # Use proper escaping for all metadata values
                    safe_value = escape_gremlin_string(str(value))
                    query += f".property('{key}', '{safe_value}')"

            self.client.submit(query).all().result()

            # Add edge to parent if exists
            if parent:
                parent_id = f"{file_path}::{parent}"
                self.add_relationship(
                    parent_id, entity_id, f"HAS_{entity_type.upper()}"
                )

            logger.info(f"Added entity to Neptune: {entity_id}")
            return entity_id

        except Exception as e:
            logger.error(f"Failed to add entity to Neptune: {e}")
            raise NeptuneError(f"Failed to add entity: {e}") from e

    def add_relationship(
        self,
        from_entity: str,
        to_entity: str,
        relationship: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Add a relationship (edge) between two entities.

        Args:
            from_entity: Source entity ID
            to_entity: Target entity ID
            relationship: Relationship type ('CALLS', 'IMPORTS', 'INHERITS', etc.)
            metadata: Additional edge metadata

        Returns:
            True if successful
        """
        if self.mode == NeptuneMode.MOCK:
            self.mock_edges.append(
                {
                    "from": from_entity,
                    "to": to_entity,
                    "relationship": relationship,
                    "metadata": metadata or {},
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            logger.info(
                f"[MOCK] Added edge: {from_entity} --[{relationship}]--> {to_entity}"
            )
            return True

        # Real Neptune operation
        try:
            # Escape all parameters to prevent injection
            safe_from = escape_gremlin_string(from_entity)
            safe_to = escape_gremlin_string(to_entity)
            safe_relationship = escape_gremlin_string(relationship)
            created_at = datetime.now(timezone.utc).isoformat()

            query = f"""
            g.V().has('entity_id', '{safe_from}').as('from')
             .V().has('entity_id', '{safe_to}').as('to')
             .addE('{safe_relationship}').from('from').to('to')
             .property('created_at', '{created_at}')
            """

            if metadata:
                for key, value in metadata.items():
                    safe_key = escape_gremlin_string(str(key))
                    safe_value = escape_gremlin_string(str(value))
                    query += f".property('{safe_key}', '{safe_value}')"

            self.client.submit(query).all().result()
            logger.info(
                f"Added relationship: {from_entity} --[{relationship}]--> {to_entity}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to add relationship: {e}")
            raise NeptuneError(f"Failed to add relationship: {e}") from e

    def find_related_code(
        self,
        entity_name: str,
        max_depth: int = 2,
        relationship_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Find code entities related to the given entity.

        Args:
            entity_name: Entity name to search from
            max_depth: Maximum traversal depth (default 2)
            relationship_types: Filter by relationship types (e.g., ['CALLS', 'IMPORTS'])

        Returns:
            List of related entities with metadata
        """
        if self.mode == NeptuneMode.MOCK:
            # Mock traversal
            results = []
            for edge in self.mock_edges:
                if entity_name in edge["from"] or entity_name in edge["to"]:
                    target_id = (
                        edge["to"] if entity_name in edge["from"] else edge["from"]
                    )
                    if target_id in self.mock_graph:
                        results.append(
                            {
                                **self.mock_graph[target_id],
                                "relationship": edge["relationship"],
                                "depth": 1,
                            }
                        )
            logger.info(f"[MOCK] Found {len(results)} related entities")
            return results

        # Real Neptune traversal
        try:
            # Escape entity name to prevent injection
            safe_entity_name = escape_gremlin_string(entity_name)

            # Build Gremlin traversal with result limit to prevent unbounded queries
            edge_filter = ""
            if relationship_types:
                # Escape relationship types as well
                safe_types = [escape_gremlin_string(t) for t in relationship_types]
                edge_filter = f"hasLabel({','.join(repr(t) for t in safe_types)})"

            # Add limit(1000) to prevent unbounded result sets
            query = f"""
            g.V().has('name', '{safe_entity_name}')
             .repeat(bothE({edge_filter}).otherV().simplePath())
             .times({max_depth})
             .emit()
             .dedup()
             .limit(1000)
             .valueMap(true)
            """

            results = self.client.submit(query).all().result()

            # Convert to dict format
            entities = []
            for vertex in results:
                entities.append(
                    {
                        "id": vertex.get("entity_id", [""])[0],
                        "name": vertex.get("name", [""])[0],
                        "type": vertex.get("type", [""])[0],
                        "file_path": vertex.get("file_path", [""])[0],
                        "line_number": vertex.get("line_number", [0])[0],
                    }
                )

            logger.info(f"Found {len(entities)} related entities in Neptune")
            return entities

        except Exception as e:
            logger.error(f"Failed to find related code: {e}")
            raise NeptuneError(f"Failed to find related code: {e}") from e

    def get_entity_by_id(self, entity_id: str) -> dict[str, Any] | None:
        """
        Retrieve a code entity by its ID.

        Args:
            entity_id: Entity ID

        Returns:
            Entity dict or None if not found
        """
        if self.mode == NeptuneMode.MOCK:
            return self.mock_graph.get(entity_id)

        # Real Neptune query
        try:
            safe_entity_id = escape_gremlin_string(entity_id)
            query = f"g.V().has('entity_id', '{safe_entity_id}').valueMap(true)"
            result = self.client.submit(query).all().result()

            if not result:
                return None

            vertex = result[0]
            return {
                "id": vertex.get("entity_id", [""])[0],
                "name": vertex.get("name", [""])[0],
                "type": vertex.get("type", [""])[0],
                "file_path": vertex.get("file_path", [""])[0],
                "line_number": vertex.get("line_number", [0])[0],
            }

        except Exception as e:
            logger.error(f"Failed to get entity: {e}")
            return None

    def search_by_name(
        self, name_pattern: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Search for entities by name pattern.

        Args:
            name_pattern: Name pattern to search (supports wildcards in AWS mode)
            limit: Maximum results to return

        Returns:
            List of matching entities
        """
        if self.mode == NeptuneMode.MOCK:
            results = [
                entity
                for entity_id, entity in self.mock_graph.items()
                if name_pattern.lower() in entity.get("name", "").lower()
            ]
            return results[:limit]

        # Real Neptune query with text search
        try:
            # Use Gremlin containing() predicate for substring matching
            # Use escape_gremlin_string for proper escaping of all special characters
            safe_pattern = escape_gremlin_string(name_pattern)
            query = f"""
            g.V().has('name', containing('{safe_pattern}'))
             .limit({limit})
             .valueMap(true)
            """

            results = self.client.submit(query).all().result()

            entities = []
            for vertex in results:
                entities.append(
                    {
                        "id": vertex.get("entity_id", [""])[0],
                        "name": vertex.get("name", [""])[0],
                        "type": vertex.get("type", [""])[0],
                        "file_path": vertex.get("file_path", [""])[0],
                    }
                )

            return entities

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def delete_by_repository(self, repository_id: str) -> int:
        """
        Delete all entities and relationships belonging to a repository.

        Args:
            repository_id: Repository identifier (e.g., 'owner/repo')

        Returns:
            Number of entities deleted
        """
        if self.mode == NeptuneMode.MOCK:
            # Delete from mock graph
            to_delete = [
                entity_id
                for entity_id, entity in self.mock_graph.items()
                if entity.get("metadata", {}).get("repository") == repository_id
            ]

            for entity_id in to_delete:
                del self.mock_graph[entity_id]

            # Delete edges involving deleted entities
            self.mock_edges = [
                edge
                for edge in self.mock_edges
                if edge.get("from") not in to_delete and edge.get("to") not in to_delete
            ]

            logger.info(
                f"[MOCK] Deleted {len(to_delete)} entities for repository: {repository_id}"
            )
            return len(to_delete)

        # Real Neptune operation
        try:
            # Escape repository_id to prevent injection
            safe_repo_id = escape_gremlin_string(repository_id)

            # Delete all vertices with matching repository property
            # This will also cascade delete edges connected to these vertices
            query = f"""
            g.V().has('repository', '{safe_repo_id}').drop()
            """

            self.client.submit(query).all().result()

            # Note: Could get count with g.V().has('repository', '{repository_id}').count()
            # but drop() doesn't return count - would need to count before delete

            logger.info(f"Deleted entities for repository: {repository_id}")
            return -1  # Indicate deletion happened but count unknown

        except Exception as e:
            logger.error(f"Failed to delete repository from Neptune: {e}")
            raise NeptuneError(f"Failed to delete repository: {e}") from e

    def delete_entity(self, entity_id: str) -> bool:
        """
        Delete a specific entity and its connected edges.

        Args:
            entity_id: Entity identifier

        Returns:
            True if entity was deleted
        """
        if self.mode == NeptuneMode.MOCK:
            if entity_id in self.mock_graph:
                del self.mock_graph[entity_id]

                # Delete connected edges
                self.mock_edges = [
                    edge
                    for edge in self.mock_edges
                    if edge.get("from") != entity_id and edge.get("to") != entity_id
                ]

                logger.info(f"[MOCK] Deleted entity: {entity_id}")
                return True
            return False

        # Real Neptune operation
        try:
            safe_entity_id = escape_gremlin_string(entity_id)
            query = f"""
            g.V().has('entity_id', '{safe_entity_id}').drop()
            """

            self.client.submit(query).all().result()
            logger.info(f"Deleted entity from Neptune: {entity_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete entity from Neptune: {e}")
            raise NeptuneError(f"Failed to delete entity: {e}") from e

    def delete_entities_by_file(self, file_path: str) -> int:
        """
        Delete all entities from a specific file.

        Args:
            file_path: Source file path

        Returns:
            Number of entities deleted
        """
        if self.mode == NeptuneMode.MOCK:
            to_delete = [
                entity_id
                for entity_id, entity in self.mock_graph.items()
                if entity.get("file_path") == file_path
            ]

            for entity_id in to_delete:
                del self.mock_graph[entity_id]

            # Delete edges involving deleted entities
            self.mock_edges = [
                edge
                for edge in self.mock_edges
                if edge.get("from") not in to_delete and edge.get("to") not in to_delete
            ]

            logger.info(
                f"[MOCK] Deleted {len(to_delete)} entities from file: {file_path}"
            )
            return len(to_delete)

        # Real Neptune operation
        try:
            query = f"""
            g.V().has('file_path', '{file_path}').drop()
            """

            self.client.submit(query).all().result()
            logger.info(f"Deleted entities from file: {file_path}")
            return -1  # Count unknown

        except Exception as e:
            logger.error(f"Failed to delete file entities from Neptune: {e}")
            raise NeptuneError(f"Failed to delete file entities: {e}") from e

    # =========================================================================
    # Infrastructure Resource Methods (ADR-056 - Documentation Agent)
    # =========================================================================

    def add_infrastructure_resource(
        self,
        resource_id: str,
        resource_type: str,
        arn: str,
        name: str,
        provider: str = "aws",
        region: str = "us-east-1",
        account_id: str = "",
        tags: dict[str, str] | None = None,
        configuration: dict[str, Any] | None = None,
    ) -> str:
        """
        Add an infrastructure resource to the graph.

        Args:
            resource_id: Unique resource identifier
            resource_type: Resource type (ec2_instance, rds_instance, lambda_function, etc.)
            arn: AWS ARN or equivalent identifier
            name: Human-readable resource name
            provider: Cloud provider (aws, azure, gcp)
            region: Cloud region
            account_id: Cloud account ID
            tags: Resource tags
            configuration: Resource configuration details

        Returns:
            Resource vertex ID
        """
        vertex_id = f"infra::{resource_id}"

        if self.mode == NeptuneMode.MOCK:
            self.mock_graph[vertex_id] = {
                "id": vertex_id,
                "label": "InfrastructureResource",
                "resource_id": resource_id,
                "resource_type": resource_type,
                "arn": arn,
                "name": name,
                "provider": provider,
                "region": region,
                "account_id": account_id,
                "tags": tags or {},
                "configuration": configuration or {},
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.info(f"[MOCK] Added infrastructure resource: {vertex_id}")
            return vertex_id

        # Real Neptune operation
        try:
            safe_vertex_id = escape_gremlin_string(vertex_id)
            safe_resource_id = escape_gremlin_string(resource_id)
            safe_resource_type = escape_gremlin_string(resource_type)
            safe_arn = escape_gremlin_string(arn)
            safe_name = escape_gremlin_string(name)
            safe_provider = escape_gremlin_string(provider)
            safe_region = escape_gremlin_string(region)
            safe_account_id = escape_gremlin_string(account_id)
            discovered_at = datetime.now(timezone.utc).isoformat()

            query = f"""
            g.addV('InfrastructureResource')
             .property('vertex_id', '{safe_vertex_id}')
             .property('resource_id', '{safe_resource_id}')
             .property('resource_type', '{safe_resource_type}')
             .property('arn', '{safe_arn}')
             .property('name', '{safe_name}')
             .property('provider', '{safe_provider}')
             .property('region', '{safe_region}')
             .property('account_id', '{safe_account_id}')
             .property('discovered_at', '{discovered_at}')
            """

            if tags:
                import json

                safe_tags = escape_gremlin_string(json.dumps(tags))
                query += f".property('tags', '{safe_tags}')"

            if configuration:
                import json

                safe_config = escape_gremlin_string(json.dumps(configuration))
                query += f".property('configuration', '{safe_config}')"

            self.client.submit(query).all().result()
            logger.info(f"Added infrastructure resource: {vertex_id}")
            return vertex_id

        except Exception as e:
            logger.error(f"Failed to add infrastructure resource: {e}")
            raise NeptuneError(f"Failed to add infrastructure resource: {e}") from e

    def add_service_boundary(
        self,
        boundary_id: str,
        name: str,
        description: str,
        node_ids: list[str],
        confidence: float,
        repository_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Add a service boundary to the graph.

        Service boundaries represent detected logical groupings of code entities
        identified by the Louvain community detection algorithm.

        Args:
            boundary_id: Unique boundary identifier
            name: Service name (e.g., 'AuthService', 'UserService')
            description: Description of the service
            node_ids: List of code entity IDs in this boundary
            confidence: Detection confidence (0.0 to 1.0)
            repository_id: Repository this boundary belongs to
            metadata: Additional metadata

        Returns:
            Service boundary vertex ID
        """
        vertex_id = f"boundary::{boundary_id}"

        if self.mode == NeptuneMode.MOCK:
            self.mock_graph[vertex_id] = {
                "id": vertex_id,
                "label": "ServiceBoundary",
                "boundary_id": boundary_id,
                "name": name,
                "description": description,
                "node_ids": node_ids,
                "node_count": len(node_ids),
                "confidence": confidence,
                "repository_id": repository_id,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            # Add OWNED_BY edges to component nodes
            for node_id in node_ids:
                self.mock_edges.append(
                    {
                        "from": vertex_id,
                        "to": node_id,
                        "relationship": "CONTAINS",
                        "confidence": confidence,
                    }
                )

            logger.info(
                f"[MOCK] Added service boundary: {vertex_id} ({len(node_ids)} nodes)"
            )
            return vertex_id

        # Real Neptune operation
        try:
            safe_vertex_id = escape_gremlin_string(vertex_id)
            safe_boundary_id = escape_gremlin_string(boundary_id)
            safe_name = escape_gremlin_string(name)
            safe_description = escape_gremlin_string(description)
            safe_repository_id = escape_gremlin_string(repository_id)
            created_at = datetime.now(timezone.utc).isoformat()

            query = f"""
            g.addV('ServiceBoundary')
             .property('vertex_id', '{safe_vertex_id}')
             .property('boundary_id', '{safe_boundary_id}')
             .property('name', '{safe_name}')
             .property('description', '{safe_description}')
             .property('node_count', {len(node_ids)})
             .property('confidence', {confidence})
             .property('repository_id', '{safe_repository_id}')
             .property('created_at', '{created_at}')
            """

            if metadata:
                import json

                safe_metadata = escape_gremlin_string(json.dumps(metadata))
                query += f".property('metadata', '{safe_metadata}')"

            self.client.submit(query).all().result()

            # Add CONTAINS edges to component nodes
            for node_id in node_ids:
                self.add_infrastructure_connection(
                    source_id=vertex_id,
                    target_id=node_id,
                    connection_type="CONTAINS",
                    metadata={"confidence": confidence},
                )

            logger.info(f"Added service boundary: {vertex_id} ({len(node_ids)} nodes)")
            return vertex_id

        except Exception as e:
            logger.error(f"Failed to add service boundary: {e}")
            raise NeptuneError(f"Failed to add service boundary: {e}") from e

    def add_data_flow(
        self,
        flow_id: str,
        source_id: str,
        target_id: str,
        flow_type: str = "sync",
        data_types: list[str] | None = None,
        protocol: str = "",
        direction: str = "unidirectional",
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Add a data flow relationship to the graph.

        Data flows represent how data moves between services, components,
        or infrastructure resources.

        Args:
            flow_id: Unique flow identifier
            source_id: Source entity ID
            target_id: Target entity ID
            flow_type: Type of flow (sync, async, event, stream)
            data_types: Types of data transferred
            protocol: Communication protocol (http, grpc, sqs, etc.)
            direction: Flow direction (unidirectional, bidirectional)
            confidence: Detection confidence
            metadata: Additional metadata

        Returns:
            Data flow vertex ID
        """
        vertex_id = f"flow::{flow_id}"

        if self.mode == NeptuneMode.MOCK:
            self.mock_graph[vertex_id] = {
                "id": vertex_id,
                "label": "DataFlow",
                "flow_id": flow_id,
                "source_id": source_id,
                "target_id": target_id,
                "flow_type": flow_type,
                "data_types": data_types or [],
                "protocol": protocol,
                "direction": direction,
                "confidence": confidence,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            # Add edges for data flow direction
            self.mock_edges.append(
                {
                    "from": source_id,
                    "to": target_id,
                    "relationship": (
                        "PRODUCES_TO" if flow_type == "event" else "WRITES_TO"
                    ),
                    "flow_id": flow_id,
                    "protocol": protocol,
                }
            )

            if direction == "bidirectional":
                self.mock_edges.append(
                    {
                        "from": target_id,
                        "to": source_id,
                        "relationship": (
                            "CONSUMES_FROM" if flow_type == "event" else "READS_FROM"
                        ),
                        "flow_id": flow_id,
                        "protocol": protocol,
                    }
                )

            logger.info(f"[MOCK] Added data flow: {source_id} -> {target_id}")
            return vertex_id

        # Real Neptune operation
        try:
            safe_vertex_id = escape_gremlin_string(vertex_id)
            safe_flow_id = escape_gremlin_string(flow_id)
            safe_source_id = escape_gremlin_string(source_id)
            safe_target_id = escape_gremlin_string(target_id)
            safe_flow_type = escape_gremlin_string(flow_type)
            safe_protocol = escape_gremlin_string(protocol)
            safe_direction = escape_gremlin_string(direction)
            created_at = datetime.now(timezone.utc).isoformat()

            query = f"""
            g.addV('DataFlow')
             .property('vertex_id', '{safe_vertex_id}')
             .property('flow_id', '{safe_flow_id}')
             .property('source_id', '{safe_source_id}')
             .property('target_id', '{safe_target_id}')
             .property('flow_type', '{safe_flow_type}')
             .property('protocol', '{safe_protocol}')
             .property('direction', '{safe_direction}')
             .property('confidence', {confidence})
             .property('created_at', '{created_at}')
            """

            if data_types:
                import json

                safe_data_types = escape_gremlin_string(json.dumps(data_types))
                query += f".property('data_types', '{safe_data_types}')"

            if metadata:
                import json

                safe_metadata = escape_gremlin_string(json.dumps(metadata))
                query += f".property('metadata', '{safe_metadata}')"

            self.client.submit(query).all().result()

            # Add directional edges
            edge_type = "PRODUCES_TO" if flow_type == "event" else "WRITES_TO"
            self.add_infrastructure_connection(
                source_id=source_id,
                target_id=target_id,
                connection_type=edge_type,
                metadata={"flow_id": flow_id, "protocol": protocol},
            )

            if direction == "bidirectional":
                reverse_edge = "CONSUMES_FROM" if flow_type == "event" else "READS_FROM"
                self.add_infrastructure_connection(
                    source_id=target_id,
                    target_id=source_id,
                    connection_type=reverse_edge,
                    metadata={"flow_id": flow_id, "protocol": protocol},
                )

            logger.info(f"Added data flow: {source_id} -> {target_id}")
            return vertex_id

        except Exception as e:
            logger.error(f"Failed to add data flow: {e}")
            raise NeptuneError(f"Failed to add data flow: {e}") from e

    def add_infrastructure_connection(
        self,
        source_id: str,
        target_id: str,
        connection_type: str,
        protocol: str = "",
        port: int | None = None,
        tls_enabled: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Add an infrastructure connection edge between resources.

        Supported connection types:
        - CONNECTS_TO: Network/service connection
        - OWNED_BY: Resource ownership
        - PRODUCES_TO: Event/message production
        - CONSUMES_FROM: Event/message consumption
        - READS_FROM: Data read operations
        - WRITES_TO: Data write operations
        - CONTAINS: Service boundary contains component

        Args:
            source_id: Source resource/entity ID
            target_id: Target resource/entity ID
            connection_type: Type of connection
            protocol: Communication protocol
            port: Connection port
            tls_enabled: Whether TLS is enabled
            metadata: Additional edge metadata

        Returns:
            True if successful
        """
        if self.mode == NeptuneMode.MOCK:
            edge = {
                "from": source_id,
                "to": target_id,
                "relationship": connection_type,
                "protocol": protocol,
                "port": port,
                "tls_enabled": tls_enabled,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self.mock_edges.append(edge)
            logger.info(
                f"[MOCK] Added connection: {source_id} --[{connection_type}]--> {target_id}"
            )
            return True

        # Real Neptune operation
        try:
            safe_source = escape_gremlin_string(source_id)
            safe_target = escape_gremlin_string(target_id)
            safe_connection_type = escape_gremlin_string(connection_type)
            safe_protocol = escape_gremlin_string(protocol)
            created_at = datetime.now(timezone.utc).isoformat()

            # Try to find vertices by vertex_id, entity_id, or resource_id
            query = f"""
            g.V().or(
                has('vertex_id', '{safe_source}'),
                has('entity_id', '{safe_source}'),
                has('resource_id', '{safe_source}')
            ).as('source')
            .V().or(
                has('vertex_id', '{safe_target}'),
                has('entity_id', '{safe_target}'),
                has('resource_id', '{safe_target}')
            ).as('target')
            .addE('{safe_connection_type}')
            .from('source').to('target')
            .property('protocol', '{safe_protocol}')
            .property('tls_enabled', {str(tls_enabled).lower()})
            .property('created_at', '{created_at}')
            """

            if port is not None:
                query += f".property('port', {port})"

            if metadata:
                for key, value in metadata.items():
                    safe_key = escape_gremlin_string(str(key))
                    safe_value = escape_gremlin_string(str(value))
                    query += f".property('{safe_key}', '{safe_value}')"

            self.client.submit(query).all().result()
            logger.info(
                f"Added connection: {source_id} --[{connection_type}]--> {target_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to add infrastructure connection: {e}")
            raise NeptuneError(f"Failed to add connection: {e}") from e

    def find_service_infrastructure(
        self,
        service_id: str,
        max_depth: int = 2,
    ) -> list[dict[str, Any]]:
        """
        Find infrastructure resources associated with a service boundary.

        Args:
            service_id: Service boundary ID
            max_depth: Maximum traversal depth

        Returns:
            List of infrastructure resources
        """
        if self.mode == NeptuneMode.MOCK:
            results = []

            # Find service boundary
            boundary_vertex_id = f"boundary::{service_id}"
            if boundary_vertex_id not in self.mock_graph:
                # Try direct lookup
                boundary_vertex_id = service_id

            # Find connected resources through edges
            visited = set()
            to_visit = [boundary_vertex_id]

            for _ in range(max_depth):
                next_visit = []
                for vertex_id in to_visit:
                    if vertex_id in visited:
                        continue
                    visited.add(vertex_id)

                    for edge in self.mock_edges:
                        if edge["from"] == vertex_id:
                            target = edge["to"]
                            if target in self.mock_graph:
                                entity = self.mock_graph[target]
                                if entity.get("label") == "InfrastructureResource":
                                    results.append(entity)
                                next_visit.append(target)

                to_visit = next_visit

            logger.info(
                f"[MOCK] Found {len(results)} infrastructure resources for service"
            )
            return results

        # Real Neptune operation
        try:
            safe_service_id = escape_gremlin_string(service_id)

            query = f"""
            g.V().or(
                has('vertex_id', 'boundary::{safe_service_id}'),
                has('boundary_id', '{safe_service_id}')
            )
            .repeat(out().simplePath())
            .times({max_depth})
            .emit()
            .hasLabel('InfrastructureResource')
            .dedup()
            .limit(100)
            .valueMap(true)
            """

            results = self.client.submit(query).all().result()

            resources = []
            for vertex in results:
                resources.append(
                    {
                        "resource_id": vertex.get("resource_id", [""])[0],
                        "resource_type": vertex.get("resource_type", [""])[0],
                        "arn": vertex.get("arn", [""])[0],
                        "name": vertex.get("name", [""])[0],
                        "provider": vertex.get("provider", [""])[0],
                        "region": vertex.get("region", [""])[0],
                    }
                )

            logger.info(f"Found {len(resources)} infrastructure resources for service")
            return resources

        except Exception as e:
            logger.error(f"Failed to find service infrastructure: {e}")
            return []

    def find_connected_resources(
        self,
        resource_id: str,
        connection_types: list[str] | None = None,
        max_depth: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Find resources connected to the given resource.

        Args:
            resource_id: Resource ID to start from
            connection_types: Filter by connection types (CONNECTS_TO, READS_FROM, etc.)
            max_depth: Maximum traversal depth

        Returns:
            List of connected resources with connection metadata
        """
        if self.mode == NeptuneMode.MOCK:
            results = []

            # Find directly connected resources
            for edge in self.mock_edges:
                if edge["from"] == resource_id or edge.get("from", "").endswith(
                    resource_id
                ):
                    if (
                        connection_types
                        and edge["relationship"] not in connection_types
                    ):
                        continue

                    target_id = edge["to"]
                    if target_id in self.mock_graph:
                        entity = self.mock_graph[target_id].copy()
                        entity["relationship"] = edge["relationship"]
                        entity["connection_metadata"] = edge.get("metadata", {})
                        results.append(entity)

            logger.info(f"[MOCK] Found {len(results)} connected resources")
            return results

        # Real Neptune operation
        try:
            safe_resource_id = escape_gremlin_string(resource_id)

            # Build edge filter
            edge_filter = ""
            if connection_types:
                safe_types = [escape_gremlin_string(t) for t in connection_types]
                edge_filter = f".hasLabel({','.join(repr(t) for t in safe_types)})"

            query = f"""
            g.V().or(
                has('vertex_id', 'infra::{safe_resource_id}'),
                has('resource_id', '{safe_resource_id}'),
                has('entity_id', '{safe_resource_id}')
            )
            .repeat(outE(){edge_filter}.inV().simplePath())
            .times({max_depth})
            .emit()
            .dedup()
            .limit(100)
            .project('vertex', 'edge')
            .by(valueMap(true))
            .by(select('edge').valueMap(true))
            """

            results = self.client.submit(query).all().result()

            resources = []
            for item in results:
                vertex = item.get("vertex", {})
                edge = item.get("edge", {})
                resources.append(
                    {
                        "id": vertex.get("vertex_id", vertex.get("entity_id", [""]))[0],
                        "name": vertex.get("name", [""])[0],
                        "type": vertex.get("resource_type", vertex.get("type", [""]))[
                            0
                        ],
                        "relationship": edge.get("label", ""),
                        "protocol": (
                            edge.get("protocol", [""])[0]
                            if edge.get("protocol")
                            else ""
                        ),
                    }
                )

            logger.info(f"Found {len(resources)} connected resources")
            return resources

        except Exception as e:
            logger.error(f"Failed to find connected resources: {e}")
            return []

    def delete_service_boundaries(self, repository_id: str) -> int:
        """
        Delete all service boundaries for a repository.

        Used when re-running boundary detection to clear stale boundaries.

        Args:
            repository_id: Repository ID

        Returns:
            Number of boundaries deleted
        """
        if self.mode == NeptuneMode.MOCK:
            to_delete = [
                vertex_id
                for vertex_id, entity in self.mock_graph.items()
                if entity.get("label") == "ServiceBoundary"
                and entity.get("repository_id") == repository_id
            ]

            for vertex_id in to_delete:
                del self.mock_graph[vertex_id]

            # Remove edges connected to deleted boundaries
            self.mock_edges = [
                edge
                for edge in self.mock_edges
                if edge.get("from") not in to_delete and edge.get("to") not in to_delete
            ]

            logger.info(f"[MOCK] Deleted {len(to_delete)} service boundaries")
            return len(to_delete)

        # Real Neptune operation
        try:
            safe_repo_id = escape_gremlin_string(repository_id)

            query = f"""
            g.V().hasLabel('ServiceBoundary')
             .has('repository_id', '{safe_repo_id}')
             .drop()
            """

            self.client.submit(query).all().result()
            logger.info(f"Deleted service boundaries for repository: {repository_id}")
            return -1  # Count unknown

        except Exception as e:
            logger.error(f"Failed to delete service boundaries: {e}")
            raise NeptuneError(f"Failed to delete service boundaries: {e}") from e

    def close(self) -> None:
        """Close Neptune connection."""
        if self.mode == NeptuneMode.AWS and hasattr(self, "client"):
            try:
                self.client.close()
                logger.info("Neptune connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")


# Convenience function
def create_graph_service(_environment: str | None = None) -> NeptuneGraphService:
    """
    Create and return a NeptuneGraphService instance.

    Args:
        _environment: Environment name (reserved for future environment-specific config)

    Returns:
        Configured NeptuneGraphService instance
    """
    # Auto-detect mode
    mode = (
        NeptuneMode.AWS
        if GREMLIN_AVAILABLE and os.getenv("NEPTUNE_ENDPOINT")
        else NeptuneMode.MOCK
    )

    endpoint = os.getenv("NEPTUNE_ENDPOINT", "neptune.aura.local")
    port = int(os.getenv("NEPTUNE_PORT", "8182"))

    return NeptuneGraphService(mode=mode, endpoint=endpoint, port=port)


if __name__ == "__main__":
    # Demo/test usage
    logging.basicConfig(level=logging.INFO)

    print("Project Aura - Neptune Graph Service Demo")
    print("=" * 60)

    # Create service (will use mock mode if Neptune not configured)
    service = create_graph_service()

    print(f"\nMode: {service.mode.value}")
    print(f"Endpoint: {service.endpoint}:{service.port}")

    # Test operations
    print("\n" + "-" * 60)
    print("Testing graph operations...")

    try:
        # Add entities
        class_id = service.add_code_entity(
            name="SecurityValidator",
            entity_type="class",
            file_path="src/validators/security.py",
            line_number=15,
            metadata={"docstring": "Validates security constraints"},
        )

        method_id = service.add_code_entity(
            name="validate_input",
            entity_type="method",
            file_path="src/validators/security.py",
            line_number=25,
            parent="SecurityValidator",
        )

        print(f"✓ Added class: {class_id}")
        print(f"✓ Added method: {method_id}")

        # Find related code
        related = service.find_related_code("SecurityValidator", max_depth=2)
        print(f"\n✓ Found {len(related)} related entities:")
        for entity in related:
            print(f"  - {entity['name']} ({entity['type']})")

    except Exception as e:
        print(f"\n✗ Error: {e}")

    # Cleanup
    service.close()

    print("\n" + "=" * 60)
    print("Demo complete!")
