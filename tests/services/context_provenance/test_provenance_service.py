"""Tests for ContentProvenanceService."""

import hashlib
from datetime import datetime, timezone

import pytest

from src.services.context_provenance.provenance_service import (
    ContentProvenanceService,
    configure_provenance_service,
    get_provenance_service,
    reset_provenance_service,
)


@pytest.fixture
def hmac_key():
    """Test HMAC key."""
    return "test-secret-key-for-hmac-signing"


@pytest.fixture
def provenance_service(hmac_key):
    """Create a provenance service for testing."""
    return ContentProvenanceService(hmac_secret_key=hmac_key)


@pytest.fixture(autouse=True)
def reset_service():
    """Reset global service after each test."""
    yield
    reset_provenance_service()


class TestContentProvenanceService:
    """Tests for ContentProvenanceService."""

    def test_collect_provenance_basic(self, provenance_service):
        """Test collecting provenance for content."""
        git_info = {
            "repository_id": "aenea-labs/project-aura",
            "commit_sha": "abc123def456789",
            "author_id": "author123",
            "author_email": "author@example.com",
            "timestamp": datetime.now(timezone.utc),
            "branch": "main",
        }

        provenance, integrity = provenance_service.collect_provenance(
            file_path="src/main.py",
            content="def main(): pass",
            git_info=git_info,
        )

        assert provenance.repository_id == "aenea-labs/project-aura"
        assert provenance.commit_sha == "abc123def456789"
        assert provenance.author_id == "author123"
        assert provenance.branch == "main"

        assert integrity.content_hash_sha256 is not None
        assert integrity.content_hmac is not None
        assert integrity.chunk_boundary_hash is not None
        assert integrity.indexed_at is not None

    def test_collect_provenance_with_gpg(self, provenance_service):
        """Test collecting provenance with GPG signature."""
        git_info = {
            "repository_id": "org/repo",
            "commit_sha": "abc123",
            "author_id": "author",
            "author_email": "a@test.com",
            "timestamp": datetime.now(timezone.utc),
            "branch": "main",
            "gpg_signature": "-----BEGIN PGP SIGNATURE-----\ntest\n-----END PGP SIGNATURE-----",
        }

        provenance, _ = provenance_service.collect_provenance(
            file_path="src/main.py",
            content="code",
            git_info=git_info,
        )

        assert provenance.signature is not None
        assert "BEGIN PGP SIGNATURE" in provenance.signature

    def test_collect_provenance_hash_consistency(self, provenance_service):
        """Test that same content produces same hash."""
        content = "def test(): return True"
        git_info = {
            "repository_id": "org/repo",
            "commit_sha": "abc123",
            "author_id": "author",
            "author_email": "a@test.com",
            "timestamp": datetime.now(timezone.utc),
            "branch": "main",
        }

        _, integrity1 = provenance_service.collect_provenance(
            file_path="file1.py",
            content=content,
            git_info=git_info,
        )

        _, integrity2 = provenance_service.collect_provenance(
            file_path="file2.py",
            content=content,
            git_info=git_info,
        )

        assert integrity1.content_hash_sha256 == integrity2.content_hash_sha256
        assert integrity1.content_hmac == integrity2.content_hmac

    def test_collect_provenance_different_content(self, provenance_service):
        """Test that different content produces different hashes."""
        git_info = {
            "repository_id": "org/repo",
            "commit_sha": "abc123",
            "author_id": "author",
            "author_email": "a@test.com",
            "timestamp": datetime.now(timezone.utc),
            "branch": "main",
        }

        _, integrity1 = provenance_service.collect_provenance(
            file_path="file1.py",
            content="content one",
            git_info=git_info,
        )

        _, integrity2 = provenance_service.collect_provenance(
            file_path="file2.py",
            content="content two",
            git_info=git_info,
        )

        assert integrity1.content_hash_sha256 != integrity2.content_hash_sha256
        assert integrity1.content_hmac != integrity2.content_hmac

    def test_set_embedding_fingerprint(self, provenance_service):
        """Test setting embedding fingerprint."""
        git_info = {
            "repository_id": "org/repo",
            "commit_sha": "abc",
            "author_id": "author",
            "author_email": "a@test.com",
            "timestamp": datetime.now(timezone.utc),
            "branch": "main",
        }

        _, integrity = provenance_service.collect_provenance(
            file_path="test.py",
            content="code",
            git_info=git_info,
        )

        assert integrity.embedding_fingerprint == ""

        embedding = [0.1] * 1024
        integrity = provenance_service.set_embedding_fingerprint(integrity, embedding)

        assert integrity.embedding_fingerprint != ""
        assert len(integrity.embedding_fingerprint) == 64  # SHA-256 hex

    def test_verify_embedding_fingerprint(self, provenance_service):
        """Test verifying embedding fingerprint."""
        embedding = [0.1 + i * 0.001 for i in range(1024)]

        git_info = {
            "repository_id": "org/repo",
            "commit_sha": "abc",
            "author_id": "author",
            "author_email": "a@test.com",
            "timestamp": datetime.now(timezone.utc),
            "branch": "main",
        }

        _, integrity = provenance_service.collect_provenance(
            file_path="test.py",
            content="code",
            git_info=git_info,
        )
        integrity = provenance_service.set_embedding_fingerprint(integrity, embedding)

        # Same embedding should verify
        assert provenance_service.verify_embedding_fingerprint(
            embedding, integrity.embedding_fingerprint
        )

        # Different embedding should fail
        different_embedding = [0.2 + i * 0.001 for i in range(1024)]
        assert not provenance_service.verify_embedding_fingerprint(
            different_embedding, integrity.embedding_fingerprint
        )

    def test_compute_content_hash(self, provenance_service):
        """Test computing content hash directly."""
        content = "test content"
        expected_hash = hashlib.sha256(content.encode()).hexdigest()

        computed_hash = provenance_service.compute_content_hash(content)

        assert computed_hash == expected_hash

    def test_compute_content_hmac(self, provenance_service, hmac_key):
        """Test computing content HMAC directly."""
        content = "test content"

        hmac_signature = provenance_service.compute_content_hmac(content)

        assert hmac_signature is not None
        assert len(hmac_signature) == 64  # SHA-256 HMAC hex

    def test_empty_content(self, provenance_service):
        """Test handling empty content."""
        git_info = {
            "repository_id": "org/repo",
            "commit_sha": "abc",
            "author_id": "author",
            "author_email": "a@test.com",
            "timestamp": datetime.now(timezone.utc),
            "branch": "main",
        }

        provenance, integrity = provenance_service.collect_provenance(
            file_path="empty.py",
            content="",
            git_info=git_info,
        )

        assert integrity.content_hash_sha256 is not None
        assert integrity.content_hmac is not None

    def test_timestamp_string_parsing(self, provenance_service):
        """Test parsing timestamp from string."""
        now = datetime.now(timezone.utc)
        git_info = {
            "repository_id": "org/repo",
            "commit_sha": "abc",
            "author_id": "author",
            "author_email": "a@test.com",
            "timestamp": now.isoformat(),  # String instead of datetime
            "branch": "main",
        }

        provenance, _ = provenance_service.collect_provenance(
            file_path="test.py",
            content="code",
            git_info=git_info,
        )

        assert isinstance(provenance.timestamp, datetime)


class TestProvenanceServiceSingleton:
    """Tests for global singleton management."""

    def test_get_provenance_service(self):
        """Test getting global service instance."""
        service = get_provenance_service()
        assert service is not None

    def test_configure_provenance_service(self):
        """Test configuring global service."""
        service = configure_provenance_service(
            hmac_secret_key="custom-key-123",
        )

        assert service is not None

        # Should return same instance
        service2 = get_provenance_service()
        assert service is service2

    def test_reset_provenance_service(self):
        """Test resetting global service."""
        service1 = get_provenance_service()
        reset_provenance_service()
        service2 = get_provenance_service()

        # Should be different instances
        assert service1 is not service2
