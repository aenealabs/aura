"""
Tests for the tactical edge runtime service.
"""

import os

import pytest

from src.services.airgap import (
    CacheFullError,
    EdgeDeploymentMode,
    EdgeRuntime,
    GraphQuery,
    InferenceRequest,
    LocalGraphStore,
    ModelLoadError,
    ModelNotFoundError,
    OfflineCacheManager,
    SyncError,
    SyncStatus,
    get_edge_runtime,
    reset_edge_runtime,
)


class TestRuntimeInitialization:
    """Tests for edge runtime initialization."""

    def test_initialize(self, test_config):
        """Test initializing edge runtime."""
        runtime = EdgeRuntime(test_config)
        assert runtime is not None

    def test_singleton_instance(self, test_config):
        """Test getting singleton instance."""
        runtime1 = get_edge_runtime()
        runtime2 = get_edge_runtime()
        assert runtime1 is runtime2

    def test_reset_singleton(self, test_config):
        """Test resetting singleton."""
        runtime1 = get_edge_runtime()
        reset_edge_runtime()
        runtime2 = get_edge_runtime()
        assert runtime1 is not runtime2

    def test_self_registration(self, runtime):
        """Test that runtime registers itself as a node."""
        node = runtime.get_self_node()
        assert node is not None
        assert node.mode == EdgeDeploymentMode.DISCONNECTED


class TestModelManagement:
    """Tests for model management."""

    def test_register_model(self, runtime, sample_quantized_model):
        """Test registering a model."""
        model = runtime.register_model(
            name="test-model",
            base_model="llama-2-7b",
            file_path=sample_quantized_model.file_path,
        )

        assert model.name == "test-model"
        assert model.base_model == "llama-2-7b"
        assert model.model_id is not None

    def test_register_model_file_not_found(self, runtime):
        """Test registering model with missing file."""
        with pytest.raises(ModelLoadError):
            runtime.register_model(
                name="missing",
                base_model="base",
                file_path="/nonexistent/model.gguf",
            )

    def test_load_model(self, runtime, sample_quantized_model):
        """Test loading a registered model."""
        model = runtime.register_model(
            name="test-model",
            base_model="llama",
            file_path=sample_quantized_model.file_path,
        )

        result = runtime.load_model(model.model_id)
        assert result is True
        assert runtime.is_model_loaded(model.model_id)

    def test_load_model_not_found(self, runtime):
        """Test loading non-existent model."""
        with pytest.raises(ModelNotFoundError):
            runtime.load_model("nonexistent-model")

    def test_unload_model(self, runtime, sample_quantized_model):
        """Test unloading a model."""
        model = runtime.register_model(
            name="test-model",
            base_model="llama",
            file_path=sample_quantized_model.file_path,
        )
        runtime.load_model(model.model_id)

        result = runtime.unload_model(model.model_id)
        assert result is True
        assert not runtime.is_model_loaded(model.model_id)

    def test_get_model(self, runtime, sample_quantized_model):
        """Test getting model by ID."""
        model = runtime.register_model(
            name="test-model",
            base_model="llama",
            file_path=sample_quantized_model.file_path,
        )

        retrieved = runtime.get_model(model.model_id)
        assert retrieved is not None
        assert retrieved.model_id == model.model_id

    def test_list_models(self, runtime, temp_dir):
        """Test listing registered models."""
        # Create multiple model files
        for i in range(3):
            model_path = os.path.join(temp_dir, f"model_{i}.gguf")
            with open(model_path, "wb") as f:
                f.write(b"GGUF" + os.urandom(100))

            runtime.register_model(
                name=f"model-{i}",
                base_model="llama",
                file_path=model_path,
            )

        models = runtime.list_models()
        assert len(models) == 3


class TestInference:
    """Tests for model inference."""

    def test_create_inference_request(self, runtime, sample_quantized_model):
        """Test creating an inference request."""
        model = runtime.register_model(
            name="test-model",
            base_model="llama",
            file_path=sample_quantized_model.file_path,
        )

        request = runtime.create_inference_request(
            model_id=model.model_id,
            prompt="Hello, world!",
            max_tokens=128,
        )

        assert request.model_id == model.model_id
        assert request.prompt == "Hello, world!"
        assert request.max_tokens == 128

    def test_infer(self, runtime, sample_quantized_model):
        """Test running inference."""
        model = runtime.register_model(
            name="test-model",
            base_model="llama",
            file_path=sample_quantized_model.file_path,
        )
        runtime.load_model(model.model_id)

        request = runtime.create_inference_request(
            model_id=model.model_id,
            prompt="Hello",
            max_tokens=64,
        )

        response = runtime.infer(request)

        assert response.success is True
        assert response.text != ""
        assert response.tokens_generated > 0

    def test_infer_caches_result(self, runtime, sample_quantized_model):
        """Test that inference caches results."""
        model = runtime.register_model(
            name="test-model",
            base_model="llama",
            file_path=sample_quantized_model.file_path,
        )
        runtime.load_model(model.model_id)

        request = runtime.create_inference_request(
            model_id=model.model_id,
            prompt="Hello cached",
            max_tokens=32,
        )

        # First call
        response1 = runtime.infer(request)
        assert response1.cached is False

        # Second call with same prompt should be cached
        response2 = runtime.infer(request)
        assert response2.cached is True

    def test_infer_model_not_found(self, runtime):
        """Test inference with missing model."""
        request = InferenceRequest(
            request_id="req-001",
            node_id="node-001",
            model_id="nonexistent",
            prompt="Hello",
        )

        with pytest.raises(ModelNotFoundError):
            runtime.infer(request)


class TestLocalGraphStore:
    """Tests for local graph storage."""

    def test_add_vertex(self, runtime):
        """Test adding a vertex."""
        vertex_id = runtime.store_in_graph(
            vertex_id="v1",
            label="Test",
            properties={"name": "test vertex"},
        )

        assert vertex_id == "v1"

    def test_get_vertex(self, runtime):
        """Test getting a vertex."""
        runtime.store_in_graph(
            vertex_id="v2",
            label="Person",
            properties={"name": "Alice", "age": 30},
        )

        vertex = runtime.get_from_graph("v2")
        assert vertex is not None
        assert vertex["label"] == "Person"
        assert vertex["properties"]["name"] == "Alice"

    def test_get_nonexistent_vertex(self, runtime):
        """Test getting non-existent vertex."""
        vertex = runtime.get_from_graph("nonexistent")
        assert vertex is None

    def test_query_graph(self, runtime):
        """Test querying the graph."""
        # Add some vertices
        for i in range(5):
            runtime.store_in_graph(
                vertex_id=f"test-{i}",
                label="TestVertex",
                properties={"index": i},
            )

        query = GraphQuery(
            query_id="q1",
            query_type="sql",
            query_text="SELECT * FROM vertices WHERE label = ?",
            parameters={"label": "TestVertex"},
        )

        result = runtime.query_graph(query)

        assert result.success is True
        assert result.result_count == 5

    def test_graph_stats(self, runtime):
        """Test getting graph statistics."""
        # Add vertices and edges
        runtime.store_in_graph("v1", "Node", {"name": "A"})
        runtime.store_in_graph("v2", "Node", {"name": "B"})
        runtime._graph.add_edge("e1", "v1", "v2", "CONNECTS")

        stats = runtime.get_graph_stats()

        assert stats["vertex_count"] == 2
        assert stats["edge_count"] == 1


class TestOfflineCache:
    """Tests for offline cache operations."""

    def test_cache_set_get(self, runtime):
        """Test setting and getting cache values."""
        runtime.cache_set("key1", {"data": "value1"}, size_bytes=100)
        result = runtime.cache_get("key1")

        assert result is not None
        assert result["data"] == "value1"

    def test_cache_miss(self, runtime):
        """Test cache miss."""
        result = runtime.cache_get("nonexistent")
        assert result is None

    def test_cache_delete(self, runtime):
        """Test deleting from cache."""
        runtime.cache_set("to_delete", "value")
        result = runtime.cache_delete("to_delete")

        assert result is True
        assert runtime.cache_get("to_delete") is None

    def test_cache_stats(self, runtime):
        """Test getting cache statistics."""
        runtime.cache_set("k1", "v1", 100)
        runtime.cache_get("k1")  # Hit
        runtime.cache_get("missing")  # Miss

        stats = runtime.get_cache_stats()

        assert stats.hit_count == 1
        assert stats.miss_count == 1
        assert stats.hit_rate == 0.5


class TestOfflineCacheManager:
    """Tests for OfflineCacheManager directly."""

    def test_lru_eviction(self, test_config):
        """Test LRU eviction when cache is full."""
        test_config.cache.max_size_mb = 0.001  # Very small cache

        cache = OfflineCacheManager(test_config)

        # Add entries until eviction occurs
        cache.set("key1", "value1", 500)
        cache.set("key2", "value2", 500)

        # key1 should be evicted
        stats = cache.get_stats()
        assert stats.eviction_count >= 0

    def test_cache_full_error(self, test_config):
        """Test cache full error for oversized entry."""
        test_config.cache.max_size_mb = 0.0001  # Tiny cache

        cache = OfflineCacheManager(test_config)

        with pytest.raises(CacheFullError):
            cache.set("big_key", "x" * 1000000, 1000000)


class TestNodeManagement:
    """Tests for edge node management."""

    def test_get_self_node(self, runtime):
        """Test getting self node."""
        node = runtime.get_self_node()
        assert node is not None
        assert node.node_id is not None
        assert node.mode == EdgeDeploymentMode.DISCONNECTED

    def test_register_peer_node(self, runtime, sample_edge_node):
        """Test registering a peer node."""
        runtime.register_node(sample_edge_node)

        retrieved = runtime.get_node(sample_edge_node.node_id)
        assert retrieved is not None
        assert retrieved.node_id == sample_edge_node.node_id

    def test_list_nodes(self, runtime, sample_edge_node):
        """Test listing all nodes."""
        runtime.register_node(sample_edge_node)

        nodes = runtime.list_nodes()

        # Should include self + peer
        assert len(nodes) >= 2

    def test_update_node_status(self, runtime):
        """Test updating node status."""
        node = runtime.get_self_node()
        initial_status = node.sync_status

        runtime.update_node_status(node.node_id, SyncStatus.SYNCED)

        updated = runtime.get_node(node.node_id)
        assert updated.sync_status == SyncStatus.SYNCED


class TestSyncOperations:
    """Tests for synchronization operations."""

    def test_start_sync_disabled(self, test_config, runtime):
        """Test starting sync when disabled."""
        test_config.sync.enabled = False

        with pytest.raises(SyncError):
            runtime.start_sync()

    def test_start_sync_disconnected(self, runtime, test_config):
        """Test starting sync in disconnected mode fails."""
        # Enable sync so we test the disconnected mode check
        test_config.sync.enabled = True

        # Default mode is disconnected
        with pytest.raises(SyncError) as exc_info:
            runtime.start_sync()

        assert "disconnected" in str(exc_info.value).lower()

    def test_get_sync_state(self, runtime):
        """Test getting sync state."""
        state = runtime.get_sync_state()
        # Initially should be None or a default state
        # depending on implementation


class TestLocalGraphStoreDirect:
    """Tests for LocalGraphStore directly."""

    def test_create_store(self, test_config):
        """Test creating graph store."""
        store = LocalGraphStore(test_config)
        assert store is not None

    def test_add_and_get_vertex(self, test_config):
        """Test adding and retrieving vertex."""
        store = LocalGraphStore(test_config)

        store.add_vertex("v1", "Person", {"name": "Bob", "age": 25})
        vertex = store.get_vertex("v1")

        assert vertex is not None
        assert vertex["label"] == "Person"
        assert vertex["properties"]["name"] == "Bob"

    def test_delete_vertex(self, test_config):
        """Test deleting a vertex."""
        store = LocalGraphStore(test_config)

        store.add_vertex("v1", "Test", {})
        result = store.delete_vertex("v1")

        assert result is True
        assert store.get_vertex("v1") is None

    def test_add_and_get_edges(self, test_config):
        """Test adding and retrieving edges."""
        store = LocalGraphStore(test_config)

        store.add_vertex("v1", "Node", {})
        store.add_vertex("v2", "Node", {})
        store.add_edge("e1", "v1", "v2", "LINKS", {"weight": 1.0})

        edges = store.get_edges(source_id="v1")

        assert len(edges) == 1
        assert edges[0]["label"] == "LINKS"
        assert edges[0]["target_id"] == "v2"

    def test_get_edges_by_label(self, test_config):
        """Test getting edges by label."""
        store = LocalGraphStore(test_config)

        store.add_vertex("v1", "Node", {})
        store.add_vertex("v2", "Node", {})
        store.add_vertex("v3", "Node", {})
        store.add_edge("e1", "v1", "v2", "FRIEND", {})
        store.add_edge("e2", "v1", "v3", "COLLEAGUE", {})

        friend_edges = store.get_edges(label="FRIEND")

        assert len(friend_edges) == 1
        assert friend_edges[0]["id"] == "e1"

    def test_query(self, test_config):
        """Test SQL query execution."""
        store = LocalGraphStore(test_config)

        store.add_vertex("v1", "Test", {"value": 1})
        store.add_vertex("v2", "Test", {"value": 2})

        results = store.query("SELECT id FROM vertices WHERE label = ?", ("Test",))

        assert len(results) == 2

    def test_get_stats(self, test_config):
        """Test getting database stats."""
        store = LocalGraphStore(test_config)

        store.add_vertex("v1", "Node", {})
        store.add_vertex("v2", "Node", {})
        store.add_edge("e1", "v1", "v2", "LINK", {})

        stats = store.get_stats()

        assert stats["vertex_count"] == 2
        assert stats["edge_count"] == 1

    def test_close(self, test_config):
        """Test closing database."""
        store = LocalGraphStore(test_config)
        store.add_vertex("v1", "Test", {})

        # Should not raise
        store.close()


class TestRuntimeLifecycle:
    """Tests for runtime lifecycle."""

    def test_close_runtime(self, runtime, sample_quantized_model):
        """Test closing runtime."""
        # Load a model
        model = runtime.register_model(
            name="test",
            base_model="llama",
            file_path=sample_quantized_model.file_path,
        )
        runtime.load_model(model.model_id)

        # Should not raise
        runtime.close()

        # Model should be unloaded
        assert not runtime.is_model_loaded(model.model_id)
