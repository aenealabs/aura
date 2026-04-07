"""
Project Aura - Tactical Edge Runtime

Service for running quantized LLM models on resource-constrained edge devices
with offline operation support, local graph storage, and caching.

Based on ADR-078: Air-Gapped and Edge Deployment
"""

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Optional

from .config import AirGapConfig, get_airgap_config
from .contracts import (
    CacheStrategy,
    EdgeDeploymentMode,
    EdgeNode,
    GraphQuery,
    GraphQueryResult,
    InferenceRequest,
    InferenceResponse,
    ModelFormat,
    ModelQuantization,
    OfflineCache,
    ProcessorArchitecture,
    QuantizedModel,
    SyncState,
    SyncStatus,
)
from .exceptions import (
    CacheFullError,
    ContextLengthExceededError,
    GraphConnectionError,
    GraphQueryError,
    GraphQueryTimeoutError,
    InferenceError,
    InferenceTimeoutError,
    ModelLoadError,
    ModelNotFoundError,
    ModelTooLargeError,
    SyncError,
)
from .metrics import get_airgap_metrics


class LocalGraphStore:
    """SQLite-based local graph storage for edge deployment."""

    def __init__(self, config: Optional[AirGapConfig] = None):
        """Initialize local graph store."""
        self._config = config or get_airgap_config()
        self._db_path = self._config.graph.database_path
        self._connection: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize database schema."""
        try:
            self._connection = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row

            if self._config.graph.wal_mode:
                self._connection.execute("PRAGMA journal_mode=WAL")

            cache_size_kb = self._config.graph.cache_size_mb * 1024
            self._connection.execute(f"PRAGMA cache_size=-{cache_size_kb}")
            self._connection.execute(f"PRAGMA page_size={self._config.graph.page_size}")
            self._connection.execute(
                f"PRAGMA synchronous={self._config.graph.sync_mode}"
            )

            # Create tables
            self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS vertices (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    properties TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    properties TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES vertices(id),
                    FOREIGN KEY (target_id) REFERENCES vertices(id)
                );

                CREATE INDEX IF NOT EXISTS idx_vertices_label ON vertices(label);
                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
                CREATE INDEX IF NOT EXISTS idx_edges_label ON edges(label);
            """)
            self._connection.commit()

        except Exception as e:
            raise GraphConnectionError(
                f"Failed to initialize database: {e}",
                self._db_path,
            )

    def add_vertex(
        self,
        vertex_id: str,
        label: str,
        properties: dict[str, Any],
    ) -> str:
        """Add a vertex to the graph."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO vertices (id, label, properties, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (vertex_id, label, json.dumps(properties), now, now),
            )
            self._connection.commit()
        return vertex_id

    def get_vertex(self, vertex_id: str) -> Optional[dict[str, Any]]:
        """Get a vertex by ID."""
        with self._lock:
            cursor = self._connection.execute(
                "SELECT * FROM vertices WHERE id = ?",
                (vertex_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "label": row["label"],
                    "properties": json.loads(row["properties"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
        return None

    def delete_vertex(self, vertex_id: str) -> bool:
        """Delete a vertex and its edges."""
        with self._lock:
            # Delete edges
            self._connection.execute(
                "DELETE FROM edges WHERE source_id = ? OR target_id = ?",
                (vertex_id, vertex_id),
            )
            # Delete vertex
            cursor = self._connection.execute(
                "DELETE FROM vertices WHERE id = ?",
                (vertex_id,),
            )
            self._connection.commit()
            return cursor.rowcount > 0

    def add_edge(
        self,
        edge_id: str,
        source_id: str,
        target_id: str,
        label: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> str:
        """Add an edge to the graph."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO edges (id, source_id, target_id, label, properties, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    edge_id,
                    source_id,
                    target_id,
                    label,
                    json.dumps(properties or {}),
                    now,
                ),
            )
            self._connection.commit()
        return edge_id

    def get_edges(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        label: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get edges with optional filtering."""
        conditions = []
        params = []

        if source_id:
            conditions.append("source_id = ?")
            params.append(source_id)
        if target_id:
            conditions.append("target_id = ?")
            params.append(target_id)
        if label:
            conditions.append("label = ?")
            params.append(label)

        query = "SELECT * FROM edges"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        with self._lock:
            cursor = self._connection.execute(query, params)
            return [
                {
                    "id": row["id"],
                    "source_id": row["source_id"],
                    "target_id": row["target_id"],
                    "label": row["label"],
                    "properties": json.loads(row["properties"]),
                    "created_at": row["created_at"],
                }
                for row in cursor.fetchall()
            ]

    def query(
        self,
        sql: str,
        params: Optional[tuple] = None,
        timeout_ms: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Execute a SQL query."""
        timeout = timeout_ms or self._config.graph.query_timeout_ms
        with self._lock:
            self._connection.execute(f"PRAGMA busy_timeout = {timeout}")
            try:
                cursor = self._connection.execute(sql, params or ())
                columns = (
                    [desc[0] for desc in cursor.description]
                    if cursor.description
                    else []
                )
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    raise GraphQueryTimeoutError("query", timeout)
                raise GraphQueryError(str(e), None, sql)

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        with self._lock:
            vertex_count = self._connection.execute(
                "SELECT COUNT(*) FROM vertices"
            ).fetchone()[0]
            edge_count = self._connection.execute(
                "SELECT COUNT(*) FROM edges"
            ).fetchone()[0]

            # Get database size
            if self._db_path != ":memory:":
                db_size = os.path.getsize(self._db_path) / (1024 * 1024)
            else:
                db_size = 0

            return {
                "vertex_count": vertex_count,
                "edge_count": edge_count,
                "database_size_mb": db_size,
            }

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            if self._config.graph.vacuum_on_close:
                self._connection.execute("VACUUM")
            self._connection.close()
            self._connection = None


class OfflineCacheManager:
    """LRU cache manager for offline operation."""

    def __init__(self, config: Optional[AirGapConfig] = None):
        """Initialize cache manager."""
        self._config = config or get_airgap_config()
        self._cache: OrderedDict[str, tuple[Any, float, int]] = (
            OrderedDict()
        )  # key -> (value, timestamp, size)
        self._lock = threading.Lock()
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        self._current_size = 0

        self._cache_id = f"cache-{uuid.uuid4().hex[:8]}"

    @property
    def cache_id(self) -> str:
        """Get cache ID."""
        return self._cache_id

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key in self._cache:
                value, _, _ = self._cache[key]
                # Update access order for LRU
                self._cache.move_to_end(key)
                self._hit_count += 1
                return value
            self._miss_count += 1
            return None

    def set(self, key: str, value: Any, size_bytes: int = 0) -> None:
        """Set value in cache."""
        size_mb = size_bytes / (1024 * 1024) if size_bytes else 0.001  # Min 1KB

        with self._lock:
            # Evict if necessary
            while (
                self._current_size + size_mb > self._config.cache.max_size_mb
                and self._cache
            ):
                self._evict_oldest()

            # Check if still can't fit
            if self._current_size + size_mb > self._config.cache.max_size_mb:
                raise CacheFullError(
                    self._cache_id,
                    self._current_size,
                    self._config.cache.max_size_mb,
                )

            # Remove old entry if exists
            if key in self._cache:
                _, _, old_size = self._cache[key]
                self._current_size -= old_size / (1024 * 1024)
                self._cache.move_to_end(key)

            # Add new entry
            self._cache[key] = (value, time.time(), size_bytes)
            self._current_size += size_mb

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key in self._cache:
                _, _, size = self._cache.pop(key)
                self._current_size -= size / (1024 * 1024)
                return True
            return False

    def _evict_oldest(self) -> None:
        """Evict oldest entry (LRU)."""
        if not self._cache:
            return
        key, (_, _, size) = self._cache.popitem(last=False)
        self._current_size -= size / (1024 * 1024)
        self._eviction_count += 1

    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._cache.clear()
            self._current_size = 0

    def get_stats(self) -> OfflineCache:
        """Get cache statistics."""
        return OfflineCache(
            cache_id=self._cache_id,
            node_id=self._config.edge_runtime.node_id or "unknown",
            strategy=CacheStrategy.LRU,
            max_size_mb=self._config.cache.max_size_mb,
            current_size_mb=self._current_size,
            entry_count=len(self._cache),
            hit_count=self._hit_count,
            miss_count=self._miss_count,
            eviction_count=self._eviction_count,
        )


class MockInferenceEngine:
    """Mock inference engine for testing."""

    def __init__(self, model: QuantizedModel):
        """Initialize mock engine."""
        self._model = model
        self._loaded = True

    def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
    ) -> tuple[str, int, float]:
        """Generate text (mock implementation).

        Returns:
            Tuple of (generated_text, tokens_generated, time_ms)
        """
        # Simulate generation
        words = ["The", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog"]
        response_words = []
        for i in range(min(max_tokens // 2, 50)):
            response_words.append(words[i % len(words)])

        response = " ".join(response_words)
        tokens = len(response_words)
        time_ms = tokens * 10  # Simulate 10ms per token

        return response, tokens, time_ms

    def tokenize(self, text: str) -> list[int]:
        """Tokenize text (mock implementation)."""
        # Simple word-based tokenization for mock
        return list(range(len(text.split())))

    def unload(self) -> None:
        """Unload model."""
        self._loaded = False


class EdgeRuntime:
    """Tactical edge runtime for offline LLM inference."""

    def __init__(self, config: Optional[AirGapConfig] = None):
        """Initialize edge runtime."""
        self._config = config or get_airgap_config()
        self._metrics = get_airgap_metrics()
        self._graph = LocalGraphStore(config)
        self._cache = OfflineCacheManager(config)
        self._models: dict[str, QuantizedModel] = {}
        self._engines: dict[str, MockInferenceEngine] = {}
        self._nodes: dict[str, EdgeNode] = {}
        self._sync_states: dict[str, SyncState] = {}
        self._lock = threading.Lock()

        # Register self as a node
        self._register_self()

    def _register_self(self) -> None:
        """Register this runtime as an edge node."""
        node_id = self._config.edge_runtime.node_id or f"node-{uuid.uuid4().hex[:8]}"
        node_name = self._config.edge_runtime.node_name or f"edge-{node_id[-8:]}"

        import platform

        arch_map = {
            "x86_64": ProcessorArchitecture.X86_64,
            "aarch64": ProcessorArchitecture.ARM64,
            "arm64": ProcessorArchitecture.ARM64,
            "armv7l": ProcessorArchitecture.ARM_CORTEX_M,
        }
        machine = platform.machine().lower()
        architecture = arch_map.get(machine, ProcessorArchitecture.UNKNOWN)

        self._self_node = EdgeNode(
            node_id=node_id,
            name=node_name,
            mode=self._config.edge_runtime.mode,
            hardware_id=platform.node(),
            architecture=architecture,
            ram_mb=self._config.edge_runtime.max_ram_mb,
            storage_mb=1024,  # Default
            sync_status=SyncStatus.OFFLINE,
        )

        self._nodes[node_id] = self._self_node

        self._metrics.record_node_registered(
            node_id,
            self._config.edge_runtime.mode.value,
            architecture.value,
            self._config.edge_runtime.max_ram_mb,
        )

    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID with prefix."""
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    # =========================================================================
    # Model Management
    # =========================================================================

    def register_model(
        self,
        name: str,
        base_model: str,
        file_path: str,
        quantization: Optional[ModelQuantization] = None,
        format: Optional[ModelFormat] = None,
    ) -> QuantizedModel:
        """Register a quantized model.

        Args:
            name: Model name
            base_model: Base model name
            file_path: Path to model file
            quantization: Quantization level
            format: Model format

        Returns:
            QuantizedModel object

        Raises:
            ModelLoadError: If model file not found
        """
        if not os.path.exists(file_path):
            raise ModelLoadError(f"Model file not found: {file_path}")

        file_size = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read(8192)).hexdigest()

        model = QuantizedModel(
            model_id=self._generate_id("model"),
            name=name,
            base_model=base_model,
            quantization=quantization or self._config.model.default_quantization,
            format=format or self._config.model.default_format,
            size_bytes=file_size,
            hash=file_hash,
            context_length=self._config.model.max_context_length,
            min_ram_mb=int(file_size / (1024 * 1024)) + 256,
            recommended_ram_mb=int(file_size / (1024 * 1024)) + 512,
            file_path=file_path,
        )

        self._models[model.model_id] = model
        return model

    def load_model(self, model_id: str) -> bool:
        """Load a model into memory.

        Args:
            model_id: Model ID to load

        Returns:
            True if loaded successfully

        Raises:
            ModelNotFoundError: If model not registered
            ModelTooLargeError: If insufficient memory
        """
        model = self._models.get(model_id)
        if not model:
            raise ModelNotFoundError(model_id)

        available_ram = (
            self._config.edge_runtime.max_ram_mb
            - self._config.edge_runtime.reserve_ram_mb
        )

        if model.min_ram_mb > available_ram:
            raise ModelTooLargeError(
                model_id,
                model.min_ram_mb,
                available_ram,
            )

        start_time = time.time()

        # Create mock engine
        engine = MockInferenceEngine(model)
        self._engines[model_id] = engine

        load_time_ms = (time.time() - start_time) * 1000

        self._metrics.record_model_loaded(
            model_id,
            model.quantization.value,
            model.format.value,
            model.size_mb,
            load_time_ms,
        )

        # Update node
        if model_id not in self._self_node.installed_models:
            self._self_node.installed_models.append(model_id)

        return True

    def unload_model(self, model_id: str) -> bool:
        """Unload a model from memory."""
        engine = self._engines.pop(model_id, None)
        if engine:
            engine.unload()
            if model_id in self._self_node.installed_models:
                self._self_node.installed_models.remove(model_id)
            return True
        return False

    def get_model(self, model_id: str) -> Optional[QuantizedModel]:
        """Get model by ID."""
        return self._models.get(model_id)

    def list_models(self) -> list[QuantizedModel]:
        """List all registered models."""
        return list(self._models.values())

    def is_model_loaded(self, model_id: str) -> bool:
        """Check if model is loaded."""
        return model_id in self._engines

    # =========================================================================
    # Inference
    # =========================================================================

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        """Run inference on a model.

        Args:
            request: InferenceRequest

        Returns:
            InferenceResponse

        Raises:
            ModelNotFoundError: If model not found
            InferenceError: If inference fails
            ContextLengthExceededError: If input too long
            InferenceTimeoutError: If inference times out
        """
        model = self._models.get(request.model_id)
        if not model:
            raise ModelNotFoundError(request.model_id)

        engine = self._engines.get(request.model_id)
        if not engine:
            # Try to load model
            self.load_model(request.model_id)
            engine = self._engines.get(request.model_id)

        if not engine:
            raise InferenceError("Failed to load model", request.model_id)

        # Check context length
        prompt_tokens = len(engine.tokenize(request.prompt))
        if prompt_tokens > model.context_length:
            raise ContextLengthExceededError(
                request.model_id,
                prompt_tokens,
                model.context_length,
            )

        self._metrics.record_inference_request(
            request.model_id,
            request.node_id,
            prompt_tokens,
            request.max_tokens,
        )

        # Check cache
        cache_key = f"infer:{hashlib.sha256(request.prompt.encode()).hexdigest()[:16]}"
        cached = self._cache.get(cache_key)
        if cached:
            return InferenceResponse(
                response_id=self._generate_id("resp"),
                request_id=request.request_id,
                node_id=request.node_id,
                model_id=request.model_id,
                text=cached["text"],
                tokens_generated=cached["tokens"],
                prompt_tokens=prompt_tokens,
                generation_time_ms=0,
                cached=True,
            )

        start_time = time.time()

        try:
            text, tokens_generated, gen_time_ms = engine.generate(
                request.prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
            )

            # Check timeout
            elapsed = (time.time() - start_time) * 1000
            if elapsed > request.timeout_seconds * 1000:
                raise InferenceTimeoutError(
                    request.model_id,
                    request.timeout_seconds,
                    tokens_generated,
                )

            response = InferenceResponse(
                response_id=self._generate_id("resp"),
                request_id=request.request_id,
                node_id=request.node_id,
                model_id=request.model_id,
                text=text,
                tokens_generated=tokens_generated,
                prompt_tokens=prompt_tokens,
                generation_time_ms=gen_time_ms,
                cached=False,
            )

            # Cache the result
            try:
                self._cache.set(
                    cache_key,
                    {"text": text, "tokens": tokens_generated},
                    len(text.encode()),
                )
            except CacheFullError:
                pass  # Ignore cache errors

            self._metrics.record_inference_completed(
                request.model_id,
                request.node_id,
                tokens_generated,
                gen_time_ms,
                cached=False,
                success=True,
            )

            return response

        except (InferenceTimeoutError, ContextLengthExceededError):
            raise
        except Exception as e:
            raise InferenceError(str(e), request.model_id, request.request_id)

    def create_inference_request(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> InferenceRequest:
        """Create an inference request."""
        return InferenceRequest(
            request_id=self._generate_id("req"),
            node_id=self._self_node.node_id,
            model_id=model_id,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    # =========================================================================
    # Graph Operations
    # =========================================================================

    def query_graph(self, query: GraphQuery) -> GraphQueryResult:
        """Execute a graph query.

        Args:
            query: GraphQuery to execute

        Returns:
            GraphQueryResult
        """
        start_time = time.time()

        try:
            results = self._graph.query(
                query.query_text,
                tuple(query.parameters.values()) if query.parameters else None,
                query.timeout_ms,
            )

            truncated = len(results) > query.max_results
            if truncated:
                results = results[: query.max_results]

            execution_time_ms = (time.time() - start_time) * 1000

            result = GraphQueryResult(
                result_id=self._generate_id("qresult"),
                query_id=query.query_id,
                results=results,
                result_count=len(results),
                execution_time_ms=execution_time_ms,
                truncated=truncated,
            )

            self._metrics.record_graph_query(
                query.query_id,
                query.query_type,
                execution_time_ms,
                len(results),
                success=True,
            )

            return result

        except Exception as e:
            return GraphQueryResult(
                result_id=self._generate_id("qresult"),
                query_id=query.query_id,
                error=str(e),
            )

    def store_in_graph(
        self,
        vertex_id: str,
        label: str,
        properties: dict[str, Any],
    ) -> str:
        """Store data in the local graph."""
        return self._graph.add_vertex(vertex_id, label, properties)

    def get_from_graph(self, vertex_id: str) -> Optional[dict[str, Any]]:
        """Get data from the local graph."""
        return self._graph.get_vertex(vertex_id)

    def get_graph_stats(self) -> dict[str, Any]:
        """Get graph database statistics."""
        stats = self._graph.get_stats()
        self._metrics.record_graph_storage(
            stats["database_size_mb"],
            stats["vertex_count"],
            stats["edge_count"],
        )
        return stats

    # =========================================================================
    # Cache Operations
    # =========================================================================

    def cache_get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        value = self._cache.get(key)
        self._metrics.record_cache_operation(
            self._cache.cache_id,
            "get",
            value is not None,
        )
        return value

    def cache_set(self, key: str, value: Any, size_bytes: int = 0) -> None:
        """Set value in cache."""
        self._cache.set(key, value, size_bytes)
        self._metrics.record_cache_operation(
            self._cache.cache_id,
            "set",
            True,
        )

    def cache_delete(self, key: str) -> bool:
        """Delete key from cache."""
        result = self._cache.delete(key)
        self._metrics.record_cache_operation(
            self._cache.cache_id,
            "delete",
            result,
        )
        return result

    def get_cache_stats(self) -> OfflineCache:
        """Get cache statistics."""
        stats = self._cache.get_stats()
        self._metrics.record_cache_stats(
            stats.cache_id,
            stats.hit_rate,
            stats.usage_percent,
            stats.entry_count,
            stats.eviction_count,
        )
        return stats

    # =========================================================================
    # Node Management
    # =========================================================================

    def get_self_node(self) -> EdgeNode:
        """Get this node's information."""
        return self._self_node

    def register_node(self, node: EdgeNode) -> None:
        """Register a peer node."""
        self._nodes[node.node_id] = node

    def get_node(self, node_id: str) -> Optional[EdgeNode]:
        """Get node by ID."""
        return self._nodes.get(node_id)

    def list_nodes(self) -> list[EdgeNode]:
        """List all known nodes."""
        return list(self._nodes.values())

    def update_node_status(
        self,
        node_id: str,
        sync_status: SyncStatus,
    ) -> None:
        """Update node sync status."""
        node = self._nodes.get(node_id)
        if node:
            node.sync_status = sync_status
            node.last_seen = datetime.now(timezone.utc)

    # =========================================================================
    # Sync Operations
    # =========================================================================

    def get_sync_state(self, node_id: Optional[str] = None) -> Optional[SyncState]:
        """Get sync state for a node."""
        nid = node_id or self._self_node.node_id
        return self._sync_states.get(nid)

    def start_sync(self) -> SyncState:
        """Start synchronization (when connected).

        Returns:
            SyncState for the sync operation
        """
        if not self._config.sync.enabled:
            raise SyncError("Sync is disabled")

        if self._self_node.mode == EdgeDeploymentMode.DISCONNECTED:
            raise SyncError("Cannot sync in disconnected mode")

        state = SyncState(
            state_id=self._generate_id("sync"),
            node_id=self._self_node.node_id,
            status=SyncStatus.SYNCING,
            pending_changes=0,  # Would calculate actual changes
        )

        self._sync_states[self._self_node.node_id] = state
        self._self_node.sync_status = SyncStatus.SYNCING

        self._metrics.record_sync_started(
            self._self_node.node_id,
            state.pending_changes,
        )

        return state

    def complete_sync(
        self,
        state_id: str,
        success: bool,
        bytes_transferred: int = 0,
        error: Optional[str] = None,
    ) -> SyncState:
        """Complete a sync operation."""
        state = None
        for s in self._sync_states.values():
            if s.state_id == state_id:
                state = s
                break

        if not state:
            raise SyncError(f"Sync state not found: {state_id}")

        state.status = SyncStatus.SYNCED if success else SyncStatus.ERROR
        state.last_sync = datetime.now(timezone.utc)
        state.bytes_transferred = bytes_transferred
        state.error_message = error

        self._self_node.sync_status = state.status

        self._metrics.record_sync_completed(
            state.node_id,
            0,  # Would calculate actual duration
            bytes_transferred,
            success,
        )

        return state

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def close(self) -> None:
        """Shutdown the edge runtime."""
        # Unload all models
        for model_id in list(self._engines.keys()):
            self.unload_model(model_id)

        # Close graph database
        self._graph.close()

        # Clear cache
        self._cache.clear()


# Singleton instance
_runtime_instance: Optional[EdgeRuntime] = None


def get_edge_runtime() -> EdgeRuntime:
    """Get singleton edge runtime instance."""
    global _runtime_instance
    if _runtime_instance is None:
        _runtime_instance = EdgeRuntime()
    return _runtime_instance


def reset_edge_runtime() -> None:
    """Reset edge runtime singleton (for testing)."""
    global _runtime_instance
    if _runtime_instance is not None:
        _runtime_instance.close()
    _runtime_instance = None
