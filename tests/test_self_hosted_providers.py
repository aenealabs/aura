"""
Project Aura - Self-Hosted Provider Tests

Unit tests for all self-hosted provider adapters.

See ADR-049: Self-Hosted Deployment Strategy
"""

import json
import os
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.abstractions.cloud_provider import CloudConfig, CloudProvider
from src.abstractions.graph_database import EntityType, GraphEntity
from src.abstractions.vector_database import IndexConfig

# Run tests in forked processes for isolation on macOS
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestCloudProviderSelfHosted:
    """Tests for SELF_HOSTED CloudProvider enum."""

    def test_self_hosted_value(self):
        """Verify SELF_HOSTED enum value."""
        assert CloudProvider.SELF_HOSTED.value == "self_hosted"

    def test_is_self_hosted_property(self):
        """Test is_self_hosted property."""
        assert CloudProvider.SELF_HOSTED.is_self_hosted is True
        assert CloudProvider.AWS.is_self_hosted is False
        assert CloudProvider.AZURE.is_self_hosted is False
        assert CloudProvider.MOCK.is_self_hosted is False

    def test_self_hosted_partition(self):
        """SELF_HOSTED returns self_hosted as partition (no cloud partition)."""
        # Self-hosted doesn't use cloud partitions
        assert CloudProvider.SELF_HOSTED.partition == "self_hosted"

    def test_from_environment_self_hosted(self):
        """Test CloudConfig.from_environment with SELF_HOSTED."""
        with patch.dict(os.environ, {"CLOUD_PROVIDER": "self_hosted"}):
            config = CloudConfig.from_environment()
            assert config.provider == CloudProvider.SELF_HOSTED


class TestNeo4jGraphAdapter:
    """Tests for Neo4jGraphAdapter."""

    @pytest.fixture
    def mock_neo4j_driver(self):
        """Mock neo4j driver."""
        with patch(
            "src.services.providers.self_hosted.neo4j_graph_adapter._get_neo4j"
        ) as mock:
            mock_driver_class = MagicMock()
            mock_driver = MagicMock()
            mock_driver_class.return_value = mock_driver
            mock.return_value = {"GraphDatabase": MagicMock(driver=mock_driver_class)}
            yield mock_driver

    @pytest.fixture
    def adapter(self, mock_neo4j_driver):
        """Create adapter instance with mocked driver."""
        from src.services.providers.self_hosted.neo4j_graph_adapter import (
            Neo4jGraphAdapter,
        )

        adapter = Neo4jGraphAdapter(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password",
            database="neo4j",
        )
        adapter._driver = mock_neo4j_driver
        return adapter

    def test_initialization(self, adapter):
        """Test adapter initialization with parameters."""
        assert adapter.uri == "bolt://localhost:7687"
        assert adapter.username == "neo4j"
        assert adapter.database == "neo4j"

    def test_initialization_from_env(self):
        """Test adapter initialization from environment variables."""
        from src.services.providers.self_hosted.neo4j_graph_adapter import (
            Neo4jGraphAdapter,
        )

        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://custom:7687",
                "NEO4J_USERNAME": "custom_user",
                "NEO4J_PASSWORD": "custom_pass",
                "NEO4J_DATABASE": "custom_db",
            },
        ):
            adapter = Neo4jGraphAdapter()
            assert adapter.uri == "bolt://custom:7687"
            assert adapter.username == "custom_user"
            assert adapter.database == "custom_db"

    @pytest.mark.asyncio
    async def test_connect(self, adapter, mock_neo4j_driver):
        """Test connect establishes connection."""
        mock_session = MagicMock()
        mock_neo4j_driver.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_neo4j_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = MagicMock()

        result = await adapter.connect()
        assert result is True
        assert adapter._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter, mock_neo4j_driver):
        """Test disconnect closes driver."""
        adapter._connected = True

        await adapter.disconnect()

        assert adapter._connected is False
        mock_neo4j_driver.close.assert_called_once()

    def test_graph_entity_creation(self, adapter):
        """Test that GraphEntity can be created properly for Neo4j."""
        entity = GraphEntity(
            id="entity-123",
            entity_type=EntityType.FUNCTION,
            name="test_function",
            repository="test-repo",
            file_path="/src/test.py",
            properties={"lines": 50},
        )
        assert entity.id == "entity-123"
        assert entity.entity_type == EntityType.FUNCTION
        assert entity.entity_type.value == "function"

    def test_adapter_methods_exist(self, adapter):
        """Test that adapter has required methods."""
        assert hasattr(adapter, "add_entity")
        assert hasattr(adapter, "get_entity")
        assert hasattr(adapter, "search_by_name")
        assert hasattr(adapter, "find_related_code")
        assert hasattr(adapter, "add_relationship")


class TestSelfHostedOpenSearchAdapter:
    """Tests for SelfHostedOpenSearchAdapter."""

    @pytest.fixture
    def mock_opensearch(self):
        """Mock opensearch-py client."""
        with patch(
            "src.services.providers.self_hosted.selfhosted_opensearch_adapter._get_opensearch"
        ) as mock:
            mock_client_class = MagicMock()
            mock.return_value = {
                "OpenSearch": mock_client_class,
                "RequestsHttpConnection": MagicMock(),
            }
            yield mock_client_class

    @pytest.fixture
    def adapter(self, mock_opensearch):
        """Create adapter instance with mocked client."""
        from src.services.providers.self_hosted.selfhosted_opensearch_adapter import (
            SelfHostedOpenSearchAdapter,
        )

        adapter = SelfHostedOpenSearchAdapter(
            endpoint="http://localhost:9200",
            username="admin",
            password="admin",
        )
        return adapter

    def test_initialization(self, adapter):
        """Test adapter initialization."""
        assert adapter.endpoint == "http://localhost:9200"
        assert adapter.username == "admin"
        assert adapter.use_ssl is False

    def test_initialization_from_env(self):
        """Test adapter initialization from environment."""
        from src.services.providers.self_hosted.selfhosted_opensearch_adapter import (
            SelfHostedOpenSearchAdapter,
        )

        with patch.dict(
            os.environ,
            {
                "OPENSEARCH_ENDPOINT": "https://custom:9200",
                "OPENSEARCH_USERNAME": "user",
                "OPENSEARCH_PASSWORD": "pass",
                "OPENSEARCH_USE_SSL": "true",
            },
        ):
            adapter = SelfHostedOpenSearchAdapter()
            assert adapter.endpoint == "https://custom:9200"
            assert adapter.username == "user"
            assert adapter.use_ssl is True

    @pytest.mark.asyncio
    async def test_connect(self, adapter, mock_opensearch):
        """Test connect establishes connection."""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client
        adapter._client = mock_client

        result = await adapter.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_create_index(self, adapter, mock_opensearch):
        """Test creating an index."""
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False
        mock_opensearch.return_value = mock_client
        adapter._client = mock_client

        config = IndexConfig(
            name="test-index",
            dimension=768,
            similarity_metric="cosine",
        )

        result = await adapter.create_index(config)
        assert result is True
        mock_client.indices.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_similar(self, adapter, mock_opensearch):
        """Test similarity search."""
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 0.95,
                        "_source": {
                            "id": "doc-1",
                            "content": "test content",
                            "embedding": [0.1] * 768,
                            "repository": "repo",
                            "file_path": "/test.py",
                            "entity_type": "Function",
                            "metadata": {},
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        },
                    }
                ]
            }
        }
        mock_opensearch.return_value = mock_client
        adapter._client = mock_client

        results = await adapter.search_similar(
            index_name="test-index",
            query_embedding=[0.1] * 768,
            k=10,
        )

        assert len(results) == 1
        assert results[0].score == 0.95


class TestLocalLLMAdapter:
    """Tests for LocalLLMAdapter."""

    @pytest.fixture
    def mock_httpx(self):
        """Mock httpx client."""
        with patch(
            "src.services.providers.self_hosted.local_llm_adapter._get_httpx"
        ) as mock:
            mock_client_class = MagicMock()
            mock.return_value = {"AsyncClient": mock_client_class}
            yield mock_client_class

    @pytest.fixture
    def adapter(self, mock_httpx):
        """Create adapter instance."""
        from src.services.providers.self_hosted.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(
            provider="vllm",
            endpoint="http://localhost:8000/v1",
            model_id="meta-llama/Llama-3-8B-Instruct",
        )
        return adapter

    def test_initialization(self, adapter):
        """Test adapter initialization."""
        assert adapter.provider == "vllm"
        assert adapter.endpoint == "http://localhost:8000/v1"
        assert adapter.model_id == "meta-llama/Llama-3-8B-Instruct"

    def test_initialization_from_env(self):
        """Test adapter initialization from environment."""
        from src.services.providers.self_hosted.local_llm_adapter import LocalLLMAdapter

        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "tgi",
                "LLM_ENDPOINT": "http://tgi:8080/v1",
                "LLM_MODEL_ID": "custom-model",
            },
        ):
            adapter = LocalLLMAdapter()
            assert adapter.provider == "tgi"
            assert adapter.endpoint == "http://tgi:8080/v1"
            assert adapter.model_id == "custom-model"

    def test_ollama_provider_type(self):
        """Test that Ollama provider is correctly stored."""
        from src.services.providers.self_hosted.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(
            provider="ollama",
            endpoint="http://localhost:11434",
        )
        assert adapter.provider == "ollama"
        assert adapter.endpoint == "http://localhost:11434"

    def test_adapter_methods_exist(self, adapter):
        """Test that adapter has required LLM methods."""
        assert hasattr(adapter, "invoke")
        assert hasattr(adapter, "invoke_streaming")
        assert hasattr(adapter, "generate_code")
        assert hasattr(adapter, "analyze_code")
        assert hasattr(adapter, "generate_embedding")
        assert hasattr(adapter, "health_check")

    def test_llm_request_creation(self):
        """Test LLMRequest can be created correctly."""
        from src.abstractions.llm_service import LLMRequest

        request = LLMRequest(
            prompt="Say hello",
            max_tokens=100,
            temperature=0.7,
        )
        assert request.prompt == "Say hello"
        assert request.max_tokens == 100
        assert request.temperature == 0.7


class TestMinioStorageAdapter:
    """Tests for MinioStorageAdapter."""

    @pytest.fixture
    def mock_minio(self):
        """Mock minio client."""
        with patch(
            "src.services.providers.self_hosted.minio_storage_adapter._get_minio"
        ) as mock:
            mock_client_class = MagicMock()
            mock.return_value = {"Minio": mock_client_class, "S3Error": Exception}
            yield mock_client_class

    @pytest.fixture
    def adapter(self, mock_minio):
        """Create adapter instance."""
        from src.services.providers.self_hosted.minio_storage_adapter import (
            MinioStorageAdapter,
        )

        adapter = MinioStorageAdapter(
            endpoint="localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False,
        )
        return adapter

    def test_initialization(self, adapter):
        """Test adapter initialization."""
        assert adapter.endpoint == "localhost:9000"
        assert adapter.access_key == "minioadmin"
        assert adapter.secure is False

    def test_initialization_from_env(self):
        """Test adapter initialization from environment."""
        from src.services.providers.self_hosted.minio_storage_adapter import (
            MinioStorageAdapter,
        )

        with patch.dict(
            os.environ,
            {
                "MINIO_ENDPOINT": "minio.local:9000",
                "MINIO_ACCESS_KEY": "access",
                "MINIO_SECRET_KEY": "secret",
                "MINIO_SECURE": "true",
            },
        ):
            adapter = MinioStorageAdapter()
            assert adapter.endpoint == "minio.local:9000"
            assert adapter.access_key == "access"
            assert adapter.secure is True

    @pytest.mark.asyncio
    async def test_connect(self, adapter, mock_minio):
        """Test connect checks MinIO availability."""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = []
        mock_minio.return_value = mock_client
        adapter._client = mock_client

        result = await adapter.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_create_bucket(self, adapter, mock_minio):
        """Test creating a bucket."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        mock_minio.return_value = mock_client
        adapter._client = mock_client

        result = await adapter.create_bucket("test-bucket")
        assert result is True
        mock_client.make_bucket.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_download_object(self, adapter, mock_minio):
        """Test upload and download operations."""
        mock_client = MagicMock()
        mock_minio.return_value = mock_client
        adapter._client = mock_client

        # Test upload
        storage_obj = await adapter.upload_object(
            bucket="test-bucket",
            key="test-key",
            data=b"test content",
            content_type="text/plain",
        )
        assert storage_obj.key == "test-key"
        assert storage_obj.size_bytes == 12

        # Test download
        mock_response = MagicMock()
        mock_response.read.return_value = b"test content"
        mock_response.close = MagicMock()
        mock_response.release_conn = MagicMock()
        mock_client.get_object.return_value = mock_response

        data = await adapter.download_object("test-bucket", "test-key")
        assert data == b"test content"


class TestPostgresDocumentAdapter:
    """Tests for PostgresDocumentAdapter."""

    @pytest.fixture
    def mock_asyncpg(self):
        """Mock asyncpg."""
        with patch(
            "src.services.providers.self_hosted.postgres_document_adapter._get_asyncpg"
        ) as mock:
            mock_asyncpg = MagicMock()
            mock.return_value = mock_asyncpg
            yield mock_asyncpg

    @pytest.fixture
    def adapter(self, mock_asyncpg):
        """Create adapter instance."""
        from src.services.providers.self_hosted.postgres_document_adapter import (
            PostgresDocumentAdapter,
        )

        adapter = PostgresDocumentAdapter(
            host="localhost",
            port=5432,
            database="aura",
            username="aura",
            password="password",
        )
        return adapter

    def test_initialization(self, adapter):
        """Test adapter initialization."""
        assert adapter.host == "localhost"
        assert adapter.port == 5432
        assert adapter.database == "aura"
        assert adapter.table_prefix == "aura_"

    def test_table_schemas(self, adapter):
        """Test that all DynamoDB tables are mapped."""
        expected_tables = [
            "cost_tracking",
            "user_sessions",
            "codegen_jobs",
            "ingestion_jobs",
            "codebase_metadata",
            "platform_settings",
            "anomalies",
            "agent_execution_logs",
            "onboarding_state",
            "team_invitations",
        ]
        for table in expected_tables:
            assert table in adapter.TABLE_SCHEMAS

    def test_table_name_prefix(self, adapter):
        """Test table name prefixing."""
        assert adapter._table_name("user_sessions") == "aura_user_sessions"
        assert adapter._table_name("cost_tracking") == "aura_cost_tracking"

    @pytest.mark.asyncio
    async def test_connect(self, adapter, mock_asyncpg):
        """Test connect creates pool."""
        mock_pool = AsyncMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        result = await adapter.connect()
        assert result is True
        assert adapter._connected is True

    @pytest.mark.asyncio
    async def test_put_and_get_item(self, adapter, mock_asyncpg):
        """Test put and get item operations."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock()

        # Create a proper async context manager for pool.acquire()
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_conn

            async def __aexit__(self, *args):
                pass

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = MockAcquireContext()
        adapter._pool = mock_pool
        adapter._connected = True

        # Test put_item
        item = {
            "session_id": "sess-123",
            "user_id": "user-456",
            "data": {"key": "value"},
        }
        result = await adapter.put_item("user_sessions", item)
        assert result is True

        # Test get_item
        mock_conn.fetchrow.return_value = {"data": json.dumps(item)}
        result = await adapter.get_item("user_sessions", {"session_id": "sess-123"})
        assert result == item


class TestFileSecretsAdapter:
    """Tests for FileSecretsAdapter."""

    @pytest.fixture
    def temp_secrets_dir(self):
        """Create temporary directory for secrets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mock_fernet(self):
        """Mock cryptography Fernet."""
        with patch(
            "src.services.providers.self_hosted.file_secrets_adapter._get_fernet"
        ) as mock:
            mock_fernet_class = MagicMock()
            mock_fernet_instance = MagicMock()
            mock_fernet_instance.encrypt.return_value = b"encrypted_data"
            mock_fernet_instance.decrypt.return_value = b"decrypted_data"
            mock_fernet_class.return_value = mock_fernet_instance
            mock_fernet_class.generate_key.return_value = (
                b"test_key_32_bytes_long_here!!"
            )
            mock.return_value = mock_fernet_class
            yield mock_fernet_class

    @pytest.fixture
    def adapter(self, temp_secrets_dir, mock_fernet):
        """Create adapter instance."""
        from src.services.providers.self_hosted.file_secrets_adapter import (
            FileSecretsAdapter,
        )

        adapter = FileSecretsAdapter(
            secrets_path=temp_secrets_dir,
            master_key="dGVzdF9rZXlfMzJfYnl0ZXNfbG9uZ19oZXJlISE=",
        )
        return adapter

    def test_initialization(self, adapter, temp_secrets_dir):
        """Test adapter initialization."""
        assert str(adapter.secrets_path) == temp_secrets_dir

    def test_secret_file_path_sanitization(self, adapter):
        """Test that secret names are sanitized."""
        path = adapter._secret_file_path("test/secret")
        assert "test_secret" in str(path)
        assert "/" not in Path(path).name

        path = adapter._secret_file_path("../escape/attempt")
        assert ".." not in Path(path).name

    @pytest.mark.asyncio
    async def test_connect(self, adapter, temp_secrets_dir):
        """Test connect initializes encryption."""
        result = await adapter.connect()
        assert result is True
        assert adapter._connected is True
        assert Path(temp_secrets_dir).exists()

    @pytest.mark.asyncio
    async def test_create_and_get_secret(self, adapter, mock_fernet):
        """Test creating and retrieving a secret."""
        await adapter.connect()

        # Create secret
        secret = await adapter.create_secret(
            name="test-secret",
            value="secret-value",
            description="Test secret",
            tags={"env": "test"},
        )
        assert secret.name == "test-secret"
        assert secret.version_id == "1"

        # Get secret metadata
        retrieved = await adapter.get_secret("test-secret")
        assert retrieved is not None
        assert retrieved.name == "test-secret"
        assert retrieved.value == "***REDACTED***"

    @pytest.mark.asyncio
    async def test_update_secret(self, adapter, mock_fernet):
        """Test updating a secret."""
        await adapter.connect()
        await adapter.create_secret("test-secret", "initial-value")

        updated = await adapter.update_secret("test-secret", "new-value")
        assert updated.version_id == "2"

    @pytest.mark.asyncio
    async def test_delete_secret(self, adapter, mock_fernet):
        """Test deleting a secret."""
        await adapter.connect()
        await adapter.create_secret("test-secret", "value")

        result = await adapter.delete_secret("test-secret")
        assert result is True

        exists = await adapter.secret_exists("test-secret")
        assert exists is False

    @pytest.mark.asyncio
    async def test_list_secrets(self, adapter, mock_fernet):
        """Test listing secrets."""
        await adapter.connect()
        await adapter.create_secret("secret-1", "value1")
        await adapter.create_secret("secret-2", "value2")

        secrets = await adapter.list_secrets()
        assert len(secrets) == 2

    @pytest.mark.asyncio
    async def test_get_health(self, adapter):
        """Test health check."""
        await adapter.connect()

        health = await adapter.get_health()
        assert health["status"] == "healthy"
        assert health["connected"] is True
        assert health["encryption"] == "fernet"


class TestCloudServiceFactorySelfHosted:
    """Tests for CloudServiceFactory with SELF_HOSTED provider."""

    @pytest.fixture
    def factory(self):
        """Create factory for self-hosted provider."""
        from src.services.providers.factory import CloudServiceFactory

        config = CloudConfig(provider=CloudProvider.SELF_HOSTED, region="local")
        return CloudServiceFactory(config)

    def test_create_graph_service(self, factory):
        """Test factory creates Neo4jGraphAdapter for self-hosted."""
        with patch(
            "src.services.providers.self_hosted.neo4j_graph_adapter._get_neo4j"
        ) as mock:
            mock.return_value = {"GraphDatabase": MagicMock()}

            service = factory.create_graph_service()

            from src.services.providers.self_hosted.neo4j_graph_adapter import (
                Neo4jGraphAdapter,
            )

            assert isinstance(service, Neo4jGraphAdapter)

    def test_create_vector_service(self, factory):
        """Test factory creates SelfHostedOpenSearchAdapter for self-hosted."""
        with patch(
            "src.services.providers.self_hosted.selfhosted_opensearch_adapter._get_opensearch"
        ) as mock:
            mock.return_value = {
                "OpenSearch": MagicMock(),
                "RequestsHttpConnection": MagicMock(),
            }

            service = factory.create_vector_service()

            from src.services.providers.self_hosted.selfhosted_opensearch_adapter import (
                SelfHostedOpenSearchAdapter,
            )

            assert isinstance(service, SelfHostedOpenSearchAdapter)

    def test_create_llm_service(self, factory):
        """Test factory creates LocalLLMAdapter for self-hosted."""
        with patch(
            "src.services.providers.self_hosted.local_llm_adapter._get_httpx"
        ) as mock:
            mock.return_value = {"AsyncClient": MagicMock()}

            service = factory.create_llm_service()

            from src.services.providers.self_hosted.local_llm_adapter import (
                LocalLLMAdapter,
            )

            assert isinstance(service, LocalLLMAdapter)

    def test_create_storage_service(self, factory):
        """Test factory creates MinioStorageAdapter for self-hosted."""
        with patch(
            "src.services.providers.self_hosted.minio_storage_adapter._get_minio"
        ) as mock:
            mock.return_value = {"Minio": MagicMock(), "S3Error": Exception}

            service = factory.create_storage_service()

            from src.services.providers.self_hosted.minio_storage_adapter import (
                MinioStorageAdapter,
            )

            assert isinstance(service, MinioStorageAdapter)

    def test_create_secrets_service(self, factory):
        """Test factory creates FileSecretsAdapter for self-hosted."""
        with patch(
            "src.services.providers.self_hosted.file_secrets_adapter._get_fernet"
        ) as mock:
            mock_fernet = MagicMock()
            mock_fernet.generate_key.return_value = b"test_key_32_bytes_long!!"
            mock.return_value = mock_fernet

            service = factory.create_secrets_service()

            from src.services.providers.self_hosted.file_secrets_adapter import (
                FileSecretsAdapter,
            )

            assert isinstance(service, FileSecretsAdapter)

    def test_create_document_service(self, factory):
        """Test factory creates PostgresDocumentAdapter for self-hosted."""
        with patch(
            "src.services.providers.self_hosted.postgres_document_adapter._get_asyncpg"
        ) as mock:
            mock.return_value = MagicMock()

            service = factory.create_document_service()

            from src.services.providers.self_hosted.postgres_document_adapter import (
                PostgresDocumentAdapter,
            )

            assert isinstance(service, PostgresDocumentAdapter)

    def test_service_caching(self, factory):
        """Test that services are cached."""
        with patch(
            "src.services.providers.self_hosted.neo4j_graph_adapter._get_neo4j"
        ) as mock:
            mock.return_value = {"GraphDatabase": MagicMock()}

            service1 = factory.create_graph_service()
            service2 = factory.create_graph_service()

            assert service1 is service2

    def test_clear_cache(self, factory):
        """Test cache clearing."""
        with patch(
            "src.services.providers.self_hosted.neo4j_graph_adapter._get_neo4j"
        ) as mock:
            mock.return_value = {"GraphDatabase": MagicMock()}

            service1 = factory.create_graph_service()
            factory.clear_cache()
            service2 = factory.create_graph_service()

            assert service1 is not service2
