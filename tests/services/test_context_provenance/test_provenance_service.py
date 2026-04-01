"""
Tests for content provenance service.

Tests provenance collection, integrity record generation, and storage.
"""

import hashlib
import hmac
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.services.context_provenance import (
    ContentProvenanceService,
    IntegrityRecord,
    ProvenanceRecord,
    configure_provenance_service,
    get_provenance_service,
    reset_provenance_service,
)


class TestContentProvenanceService:
    """Test ContentProvenanceService class."""

    def test_initialization(self):
        """Test service initialization."""
        service = ContentProvenanceService(hmac_secret_key="test-secret")
        assert service.neptune is None
        assert service.opensearch is None

    def test_initialization_with_clients(self):
        """Test service initialization with clients."""
        neptune = MagicMock()
        opensearch = MagicMock()

        service = ContentProvenanceService(
            hmac_secret_key="test-secret",
            neptune_client=neptune,
            opensearch_client=opensearch,
        )

        assert service.neptune is neptune
        assert service.opensearch is opensearch


class TestCollectProvenance:
    """Test collect_provenance method."""

    @pytest.fixture
    def service(self):
        """Create service for tests."""
        return ContentProvenanceService(hmac_secret_key="test-secret-key")

    def test_collect_provenance_basic(self, service: ContentProvenanceService):
        """Test basic provenance collection."""
        git_info = {
            "repository_id": "org/repo",
            "commit_sha": "abc123def456",
            "author_id": "user-001",
            "author_email": "dev@example.com",
            "branch": "main",
            "gpg_signature": "gpg-sig",
        }

        provenance, integrity = service.collect_provenance(
            file_path="src/main.py",
            content="def main(): pass",
            git_info=git_info,
        )

        assert isinstance(provenance, ProvenanceRecord)
        assert provenance.repository_id == "org/repo"
        assert provenance.commit_sha == "abc123def456"
        assert provenance.author_id == "user-001"
        assert provenance.author_email == "dev@example.com"
        assert provenance.branch == "main"
        assert provenance.signature == "gpg-sig"

        assert isinstance(integrity, IntegrityRecord)
        assert integrity.content_hash_sha256 is not None
        assert integrity.content_hmac is not None
        assert integrity.chunk_boundary_hash is not None
        assert integrity.indexed_at is not None

    def test_collect_provenance_minimal_git_info(
        self, service: ContentProvenanceService
    ):
        """Test provenance collection with minimal git info."""
        git_info = {}

        provenance, integrity = service.collect_provenance(
            file_path="src/main.py",
            content="def main(): pass",
            git_info=git_info,
        )

        assert provenance.repository_id == "unknown"
        assert provenance.commit_sha == ""
        assert provenance.author_id == ""
        assert provenance.branch == "main"
        assert provenance.signature is None

    def test_collect_provenance_with_string_timestamp(
        self, service: ContentProvenanceService
    ):
        """Test provenance collection with ISO timestamp string."""
        timestamp = datetime.now(timezone.utc)
        git_info = {
            "repository_id": "org/repo",
            "commit_sha": "abc123",
            "timestamp": timestamp.isoformat(),
        }

        provenance, _ = service.collect_provenance(
            file_path="src/main.py",
            content="def main(): pass",
            git_info=git_info,
        )

        assert isinstance(provenance.timestamp, datetime)

    def test_collect_provenance_content_hash(self, service: ContentProvenanceService):
        """Test that content hash is computed correctly."""
        content = "def hello(): pass"
        expected_hash = hashlib.sha256(content.encode()).hexdigest()

        _, integrity = service.collect_provenance(
            file_path="src/main.py",
            content=content,
            git_info={"repository_id": "repo"},
        )

        assert integrity.content_hash_sha256 == expected_hash

    def test_collect_provenance_hmac(self, service: ContentProvenanceService):
        """Test that HMAC is computed correctly."""
        content = "def hello(): pass"
        expected_hmac = hmac.new(
            b"test-secret-key",
            content.encode(),
            hashlib.sha256,
        ).hexdigest()

        _, integrity = service.collect_provenance(
            file_path="src/main.py",
            content=content,
            git_info={"repository_id": "repo"},
        )

        assert integrity.content_hmac == expected_hmac


class TestEmbeddingFingerprint:
    """Test embedding fingerprint methods."""

    @pytest.fixture
    def service(self):
        """Create service for tests."""
        return ContentProvenanceService(hmac_secret_key="test-secret")

    @pytest.fixture
    def integrity_record(self):
        """Create sample integrity record."""
        return IntegrityRecord(
            content_hash_sha256="hash123",
            content_hmac="hmac456",
            chunk_boundary_hash="boundary789",
            embedding_fingerprint="",
            indexed_at=datetime.now(timezone.utc),
        )

    def test_set_embedding_fingerprint(
        self,
        service: ContentProvenanceService,
        integrity_record: IntegrityRecord,
    ):
        """Test setting embedding fingerprint."""
        embedding = [0.1] * 32  # Sample embedding

        updated = service.set_embedding_fingerprint(integrity_record, embedding)

        assert updated.embedding_fingerprint != ""
        assert len(updated.embedding_fingerprint) == 64  # SHA-256 hex

    def test_set_embedding_fingerprint_empty(
        self,
        service: ContentProvenanceService,
        integrity_record: IntegrityRecord,
    ):
        """Test setting fingerprint with empty embedding."""
        updated = service.set_embedding_fingerprint(integrity_record, [])

        assert updated.embedding_fingerprint == ""

    def test_verify_embedding_fingerprint_valid(
        self,
        service: ContentProvenanceService,
        integrity_record: IntegrityRecord,
    ):
        """Test verifying valid embedding fingerprint."""
        embedding = [0.1] * 32

        updated = service.set_embedding_fingerprint(integrity_record, embedding)

        assert (
            service.verify_embedding_fingerprint(
                embedding, updated.embedding_fingerprint
            )
            is True
        )

    def test_verify_embedding_fingerprint_invalid(
        self,
        service: ContentProvenanceService,
    ):
        """Test verifying invalid embedding fingerprint."""
        embedding = [0.1] * 32

        assert (
            service.verify_embedding_fingerprint(embedding, "invalid_fingerprint")
            is False
        )

    def test_verify_embedding_fingerprint_empty(
        self,
        service: ContentProvenanceService,
    ):
        """Test verifying with empty embedding."""
        assert service.verify_embedding_fingerprint([], "some_fingerprint") is False

    def test_verify_embedding_fingerprint_no_stored(
        self,
        service: ContentProvenanceService,
    ):
        """Test verifying with no stored fingerprint."""
        embedding = [0.1] * 32
        assert service.verify_embedding_fingerprint(embedding, "") is False


class TestStoreProvenanceNeptune:
    """Test store_provenance_neptune method."""

    @pytest.fixture
    def neptune_mock(self):
        """Create mock Neptune client."""
        mock = MagicMock()
        mock.client.submit.return_value.all.return_value.result.return_value = []
        return mock

    @pytest.fixture
    def service(self, neptune_mock):
        """Create service with mock Neptune client."""
        return ContentProvenanceService(
            hmac_secret_key="test-secret",
            neptune_client=neptune_mock,
        )

    @pytest.fixture
    def sample_records(self):
        """Create sample provenance and integrity records."""
        provenance = ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123",
            author_id="user-001",
            author_email="dev@example.com",
            timestamp=datetime.now(timezone.utc),
            branch="main",
            signature=None,
        )
        integrity = IntegrityRecord(
            content_hash_sha256="hash123",
            content_hmac="hmac456",
            chunk_boundary_hash="boundary789",
            embedding_fingerprint="emb123",
            indexed_at=datetime.now(timezone.utc),
        )
        return provenance, integrity

    @pytest.mark.asyncio
    async def test_store_provenance_neptune(
        self,
        service: ContentProvenanceService,
        neptune_mock,
        sample_records,
    ):
        """Test storing provenance in Neptune."""
        provenance, integrity = sample_records

        await service.store_provenance_neptune(
            entity_id="entity-001",
            provenance=provenance,
            integrity=integrity,
        )

        neptune_mock.client.submit.assert_called_once()
        call_args = neptune_mock.client.submit.call_args[0][0]
        assert "entity-001" in call_args
        assert "provenance_repository_id" in call_args

    @pytest.mark.asyncio
    async def test_store_provenance_neptune_no_client(self, sample_records):
        """Test storing provenance without Neptune client."""
        service = ContentProvenanceService(hmac_secret_key="test-secret")
        provenance, integrity = sample_records

        # Should not raise
        await service.store_provenance_neptune(
            entity_id="entity-001",
            provenance=provenance,
            integrity=integrity,
        )


class TestStoreProvenanceOpenSearch:
    """Test store_provenance_opensearch method."""

    @pytest.fixture
    def opensearch_mock(self):
        """Create mock OpenSearch client."""
        mock = MagicMock()
        mock.update.return_value = {"result": "updated"}
        return mock

    @pytest.fixture
    def service(self, opensearch_mock):
        """Create service with mock OpenSearch client."""
        return ContentProvenanceService(
            hmac_secret_key="test-secret",
            opensearch_client=opensearch_mock,
        )

    @pytest.fixture
    def sample_records(self):
        """Create sample records."""
        provenance = ProvenanceRecord(
            repository_id="org/repo",
            commit_sha="abc123",
            author_id="user-001",
            author_email="dev@example.com",
            timestamp=datetime.now(timezone.utc),
            branch="main",
            signature=None,
        )
        integrity = IntegrityRecord(
            content_hash_sha256="hash123",
            content_hmac="hmac456",
            chunk_boundary_hash="boundary789",
            embedding_fingerprint="emb123",
            indexed_at=datetime.now(timezone.utc),
        )
        return provenance, integrity

    @pytest.mark.asyncio
    async def test_store_provenance_opensearch(
        self,
        service: ContentProvenanceService,
        opensearch_mock,
        sample_records,
    ):
        """Test storing provenance in OpenSearch."""
        provenance, integrity = sample_records

        await service.store_provenance_opensearch(
            doc_id="doc-001",
            provenance=provenance,
            integrity=integrity,
        )

        opensearch_mock.update.assert_called_once()
        call_kwargs = opensearch_mock.update.call_args[1]
        assert call_kwargs["index"] == "aura-code-embeddings"
        assert call_kwargs["id"] == "doc-001"

    @pytest.mark.asyncio
    async def test_store_provenance_opensearch_no_client(self, sample_records):
        """Test storing provenance without OpenSearch client."""
        service = ContentProvenanceService(hmac_secret_key="test-secret")
        provenance, integrity = sample_records

        # Should not raise
        await service.store_provenance_opensearch(
            doc_id="doc-001",
            provenance=provenance,
            integrity=integrity,
        )


class TestPublicMethods:
    """Test public hash computation methods."""

    @pytest.fixture
    def service(self):
        """Create service for tests."""
        return ContentProvenanceService(hmac_secret_key="test-secret-key")

    def test_compute_content_hash(self, service: ContentProvenanceService):
        """Test public content hash method."""
        content = "def hello(): pass"
        expected = hashlib.sha256(content.encode()).hexdigest()

        result = service.compute_content_hash(content)

        assert result == expected

    def test_compute_content_hmac(self, service: ContentProvenanceService):
        """Test public HMAC method."""
        content = "def hello(): pass"
        expected = hmac.new(
            b"test-secret-key",
            content.encode(),
            hashlib.sha256,
        ).hexdigest()

        result = service.compute_content_hmac(content)

        assert result == expected


class TestSingletonFunctions:
    """Test singleton management functions."""

    def test_get_provenance_service(self):
        """Test get_provenance_service returns singleton."""
        service1 = get_provenance_service()
        service2 = get_provenance_service()
        assert service1 is service2

    def test_reset_provenance_service(self):
        """Test reset_provenance_service creates new instance."""
        service1 = get_provenance_service()
        reset_provenance_service()
        service2 = get_provenance_service()
        assert service1 is not service2

    def test_configure_provenance_service(self):
        """Test configure_provenance_service."""
        neptune = MagicMock()
        opensearch = MagicMock()

        service = configure_provenance_service(
            hmac_secret_key="custom-key",
            neptune_client=neptune,
            opensearch_client=opensearch,
        )

        assert service.neptune is neptune
        assert service.opensearch is opensearch
