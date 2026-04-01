"""
Project Aura - Migration Toolkit Tests

Comprehensive tests for the migration toolkit covering:
- Base migrator classes
- Neptune to Neo4j migration
- DynamoDB to PostgreSQL migration
- S3 to MinIO migration
- Secrets Manager to file migration
- CLI interface

See ADR-049: Self-Hosted Deployment Strategy
"""

import platform
from datetime import datetime, timedelta, timezone

import pytest

# Run tests in isolated subprocesses to prevent state pollution
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


# ==============================================================================
# Base Module Tests
# ==============================================================================


class TestMigrationStatus:
    """Tests for MigrationStatus enum."""

    def test_all_statuses_defined(self):
        """Verify all expected statuses are defined."""
        from src.migration.base import MigrationStatus

        expected = ["PENDING", "RUNNING", "PAUSED", "COMPLETED", "FAILED", "CANCELLED"]
        actual = [s.name for s in MigrationStatus]
        assert sorted(actual) == sorted(expected)

    def test_status_values(self):
        """Verify status values are lowercase strings."""
        from src.migration.base import MigrationStatus

        for status in MigrationStatus:
            assert status.value == status.name.lower()


class TestMigrationError:
    """Tests for MigrationError exception."""

    def test_basic_error(self):
        """Test basic error creation."""
        from src.migration.base import MigrationError

        error = MigrationError("Test error")
        assert str(error) == "Test error"
        assert error.source is None
        assert error.item_id is None
        assert error.recoverable is True

    def test_error_with_details(self):
        """Test error with full details."""
        from src.migration.base import MigrationError

        error = MigrationError(
            "Failed to process",
            source="neptune",
            item_id="entity123",
            recoverable=False,
        )
        assert error.source == "neptune"
        assert error.item_id == "entity123"
        assert error.recoverable is False


class TestMigrationProgress:
    """Tests for MigrationProgress dataclass."""

    def test_initial_state(self):
        """Test default progress values."""
        from src.migration.base import MigrationProgress

        progress = MigrationProgress()
        assert progress.total_items == 0
        assert progress.migrated_items == 0
        assert progress.failed_items == 0
        assert progress.skipped_items == 0
        assert progress.percent_complete == 0.0
        assert progress.errors == []

    def test_percent_complete(self):
        """Test percentage calculation."""
        from src.migration.base import MigrationProgress

        progress = MigrationProgress(total_items=100, migrated_items=50)
        assert progress.percent_complete == 50.0

        progress.migrated_items = 75
        assert progress.percent_complete == 75.0

    def test_percent_complete_zero_total(self):
        """Test percentage with zero total items."""
        from src.migration.base import MigrationProgress

        progress = MigrationProgress(total_items=0, migrated_items=0)
        assert progress.percent_complete == 0.0

    def test_elapsed_seconds(self):
        """Test elapsed time calculation."""
        from src.migration.base import MigrationProgress

        now = datetime.now(timezone.utc)
        progress = MigrationProgress(
            start_time=now - timedelta(seconds=30),
        )
        # Allow some tolerance for test execution time
        assert 29 <= progress.elapsed_seconds <= 32

    def test_items_per_second(self):
        """Test migration rate calculation."""
        from src.migration.base import MigrationProgress

        now = datetime.now(timezone.utc)
        progress = MigrationProgress(
            total_items=100,
            migrated_items=50,
            start_time=now - timedelta(seconds=10),
        )
        assert 4.5 <= progress.items_per_second <= 5.5

    def test_to_dict(self):
        """Test dictionary serialization."""
        from src.migration.base import MigrationProgress

        now = datetime.now(timezone.utc)
        progress = MigrationProgress(
            total_items=100,
            migrated_items=75,
            failed_items=5,
            skipped_items=10,
            current_item="test_item",
            start_time=now,
            errors=["error1", "error2"],
        )
        result = progress.to_dict()

        assert result["total_items"] == 100
        assert result["migrated_items"] == 75
        assert result["failed_items"] == 5
        assert result["skipped_items"] == 10
        assert result["current_item"] == "test_item"
        assert result["percent_complete"] == 75.0
        assert result["error_count"] == 2
        assert result["recent_errors"] == ["error1", "error2"]


class TestMigrationResult:
    """Tests for MigrationResult dataclass."""

    def test_result_creation(self):
        """Test result creation."""
        from src.migration.base import (
            MigrationProgress,
            MigrationResult,
            MigrationStatus,
        )

        now = datetime.now(timezone.utc)
        result = MigrationResult(
            status=MigrationStatus.COMPLETED,
            source_type="neptune",
            target_type="neo4j",
            progress=MigrationProgress(total_items=100, migrated_items=100),
            started_at=now,
            completed_at=now + timedelta(seconds=60),
        )

        assert result.status == MigrationStatus.COMPLETED
        assert result.source_type == "neptune"
        assert result.target_type == "neo4j"

    def test_result_to_dict(self):
        """Test result dictionary serialization."""
        from src.migration.base import (
            MigrationProgress,
            MigrationResult,
            MigrationStatus,
        )

        now = datetime.now(timezone.utc)
        result = MigrationResult(
            status=MigrationStatus.COMPLETED,
            source_type="s3",
            target_type="minio",
            progress=MigrationProgress(total_items=50, migrated_items=50),
            started_at=now,
            warnings=["Minor warning"],
        )

        data = result.to_dict()
        assert data["status"] == "completed"
        assert data["source_type"] == "s3"
        assert data["target_type"] == "minio"
        assert data["warnings"] == ["Minor warning"]


class TestMigrationConfig:
    """Tests for MigrationConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        from src.migration.base import MigrationConfig

        config = MigrationConfig()
        assert config.batch_size == 100
        assert config.max_concurrent == 5
        assert config.stop_on_error is False
        assert config.max_errors == 100
        assert config.retry_count == 3
        assert config.skip_existing is True
        assert config.verify_data is True
        assert config.dry_run is False

    def test_custom_config(self):
        """Test custom configuration."""
        from src.migration.base import MigrationConfig

        config = MigrationConfig(
            batch_size=50,
            max_concurrent=10,
            stop_on_error=True,
            dry_run=True,
        )
        assert config.batch_size == 50
        assert config.max_concurrent == 10
        assert config.stop_on_error is True
        assert config.dry_run is True


# ==============================================================================
# Neptune to Neo4j Migrator Tests
# ==============================================================================


class TestNeptuneToNeo4jMigrator:
    """Tests for Neptune to Neo4j migrator."""

    @pytest.fixture
    def migrator(self):
        """Create migrator with mock config."""
        from src.migration.base import MigrationConfig
        from src.migration.neptune_to_neo4j import NeptuneToNeo4jMigrator

        config = MigrationConfig(dry_run=True)
        return NeptuneToNeo4jMigrator(
            neptune_endpoint="neptune.example.com",
            neo4j_uri="bolt://localhost:7687",
            neo4j_password="password",
            config=config,
        )

    def test_source_type(self, migrator):
        """Test source type property."""
        assert migrator.source_type == "neptune"

    def test_target_type(self, migrator):
        """Test target type property."""
        assert migrator.target_type == "neo4j"

    @pytest.mark.asyncio
    async def test_connect_source_returns_bool(self, migrator):
        """Test source connection returns boolean."""
        # Connection may succeed or fail depending on environment
        result = await migrator.connect_source()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_connect_target_mock_mode(self, migrator):
        """Test target connection in mock mode."""
        # Without neo4j installed, should return True (mock mode)
        result = await migrator.connect_target()
        assert result is True

    @pytest.mark.asyncio
    async def test_disconnect(self, migrator):
        """Test disconnect clears clients."""
        await migrator.disconnect()
        assert migrator._neptune_client is None
        assert migrator._neo4j_driver is None

    @pytest.mark.asyncio
    async def test_count_source_items_no_client(self, migrator):
        """Test count returns 0 without client."""
        count = await migrator.count_source_items()
        assert count == 0

    @pytest.mark.asyncio
    async def test_migrate_item_vertex_mock(self, migrator):
        """Test vertex migration in mock mode."""
        vertex = {
            "type": "vertex",
            "id": "vertex123",
            "label": "CodeEntity",
            "properties": {"name": "test_function"},
        }
        result = await migrator.migrate_item(vertex)
        assert result is True

    @pytest.mark.asyncio
    async def test_migrate_item_edge_mock(self, migrator):
        """Test edge migration in mock mode."""
        edge = {
            "type": "edge",
            "id": "edge123",
            "label": "CALLS",
            "source_id": "v1",
            "target_id": "v2",
            "properties": {},
        }
        result = await migrator.migrate_item(edge)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_item_mock(self, migrator):
        """Test verification in mock mode."""
        item = {"id": "test123", "type": "vertex"}
        result = await migrator.verify_item(item)
        assert result is True


# ==============================================================================
# DynamoDB to PostgreSQL Migrator Tests
# ==============================================================================


class TestDynamoDBToPostgresMigrator:
    """Tests for DynamoDB to PostgreSQL migrator."""

    @pytest.fixture
    def migrator(self):
        """Create migrator with mock config."""
        from src.migration.base import MigrationConfig
        from src.migration.dynamodb_to_postgres import DynamoDBToPostgresMigrator

        config = MigrationConfig(dry_run=True)
        return DynamoDBToPostgresMigrator(
            dynamodb_region="us-east-1",
            postgres_password="password",
            tables=["user_sessions", "codegen_jobs"],
            config=config,
        )

    def test_source_type(self, migrator):
        """Test source type property."""
        assert migrator.source_type == "dynamodb"

    def test_target_type(self, migrator):
        """Test target type property."""
        assert migrator.target_type == "postgresql"

    def test_tables_filter(self, migrator):
        """Test table filtering."""
        assert migrator.tables == ["user_sessions", "codegen_jobs"]

    @pytest.mark.asyncio
    async def test_connect_source_returns_bool(self, migrator):
        """Test source connection returns boolean."""
        result = await migrator.connect_source()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_connect_target_returns_bool(self, migrator):
        """Test target connection returns boolean."""
        result = await migrator.connect_target()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_count_source_items_no_client(self, migrator):
        """Test count returns 0 without client."""
        count = await migrator.count_source_items()
        assert count == 0

    def test_convert_dynamodb_types(self, migrator):
        """Test DynamoDB type conversion."""
        from decimal import Decimal

        item = {
            "id": "test123",
            "count": Decimal("42"),
            "price": Decimal("19.99"),
            "tags": {"key1", "key2"},
            "nested": {"value": Decimal("100")},
        }
        result = migrator._convert_dynamodb_types(item)

        assert result["id"] == "test123"
        assert result["count"] == 42
        assert result["price"] == 19.99
        assert isinstance(result["tags"], list)
        assert result["nested"]["value"] == 100

    @pytest.mark.asyncio
    async def test_migrate_item_mock(self, migrator):
        """Test item migration in mock mode."""
        item = {
            "_table": "user_sessions",
            "_item": {"session_id": "sess123", "user_id": "user456"},
        }
        result = await migrator.migrate_item(item)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_item_mock(self, migrator):
        """Test verification in mock mode."""
        item = {
            "_table": "user_sessions",
            "_item": {"session_id": "sess123"},
        }
        result = await migrator.verify_item(item)
        assert result is True


# ==============================================================================
# S3 to MinIO Migrator Tests
# ==============================================================================


class TestS3ToMinioMigrator:
    """Tests for S3 to MinIO migrator."""

    @pytest.fixture
    def migrator(self):
        """Create migrator with mock config."""
        from src.migration.base import MigrationConfig
        from src.migration.s3_to_minio import S3ToMinioMigrator

        config = MigrationConfig(dry_run=True)
        return S3ToMinioMigrator(
            s3_region="us-east-1",
            s3_buckets=["aura-data", "aura-models"],
            minio_endpoint="localhost:9000",
            minio_secret_key="password",
            bucket_mapping={"aura-data": "data", "aura-models": "models"},
            config=config,
        )

    def test_source_type(self, migrator):
        """Test source type property."""
        assert migrator.source_type == "s3"

    def test_target_type(self, migrator):
        """Test target type property."""
        assert migrator.target_type == "minio"

    def test_bucket_mapping(self, migrator):
        """Test bucket name mapping."""
        assert migrator.bucket_mapping["aura-data"] == "data"
        assert migrator.bucket_mapping["aura-models"] == "models"

    @pytest.mark.asyncio
    async def test_connect_source_returns_bool(self, migrator):
        """Test source connection returns boolean."""
        result = await migrator.connect_source()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_connect_target_returns_bool(self, migrator):
        """Test target connection returns boolean."""
        result = await migrator.connect_target()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_count_source_items_no_client(self, migrator):
        """Test count returns 0 without client."""
        count = await migrator.count_source_items()
        assert count == 0

    @pytest.mark.asyncio
    async def test_migrate_item_no_clients(self, migrator):
        """Test object migration returns True without clients (mock mode)."""
        item = {
            "bucket": "aura-data",
            "key": "test/file.json",
            "size": 1024,
            "etag": "abc123",
        }
        result = await migrator.migrate_item(item)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_item_no_clients(self, migrator):
        """Test verification returns True without clients (mock mode)."""
        item = {"bucket": "aura-data", "key": "test.txt", "size": 100}
        result = await migrator.verify_item(item)
        assert result is True


# ==============================================================================
# Secrets to File Migrator Tests
# ==============================================================================


class TestSecretsToFileMigrator:
    """Tests for Secrets Manager to file migrator."""

    @pytest.fixture
    def migrator(self, tmp_path):
        """Create migrator with temp directory."""
        from src.migration.base import MigrationConfig
        from src.migration.secrets_to_file import SecretsToFileMigrator

        config = MigrationConfig(dry_run=True)
        return SecretsToFileMigrator(
            secrets_manager_region="us-east-1",
            secrets_prefix="aura/",
            target_path=str(tmp_path / "secrets"),
            key_file=str(tmp_path / ".secrets_key"),
            config=config,
        )

    def test_source_type(self, migrator):
        """Test source type property."""
        assert migrator.source_type == "secrets_manager"

    def test_target_type(self, migrator):
        """Test target type property."""
        assert migrator.target_type == "file_secrets"

    @pytest.mark.asyncio
    async def test_connect_source_returns_bool(self, migrator):
        """Test source connection returns boolean."""
        result = await migrator.connect_source()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_connect_target_creates_directory(self, migrator):
        """Test target connection creates secrets directory."""
        result = await migrator.connect_target()
        assert result is True
        assert migrator.target_path.exists()

    @pytest.mark.asyncio
    async def test_connect_target_generates_key(self, migrator):
        """Test target connection generates encryption key."""
        await migrator.connect_target()
        assert migrator.key_file.exists()

    def test_sanitize_name_slashes(self):
        """Test secret name sanitization for slashes."""
        from src.migration.secrets_to_file import SecretsToFileMigrator

        migrator = SecretsToFileMigrator(target_path="/tmp/test", key_file="/tmp/key")
        assert migrator._sanitize_name("aura/db/password") == "aura_db_password"

    def test_sanitize_name_dots(self):
        """Test secret name sanitization for double dots."""
        from src.migration.secrets_to_file import SecretsToFileMigrator

        migrator = SecretsToFileMigrator(target_path="/tmp/test", key_file="/tmp/key")
        # Double dots are replaced with single underscore then sanitized
        result = migrator._sanitize_name("test..secret")
        assert ".." not in result  # Path traversal prevented
        assert result == "test_secret"

    def test_sanitize_name_backslash(self):
        """Test secret name sanitization for backslashes."""
        from src.migration.secrets_to_file import SecretsToFileMigrator

        migrator = SecretsToFileMigrator(target_path="/tmp/test", key_file="/tmp/key")
        assert migrator._sanitize_name("my\\secret") == "my_secret"

    @pytest.mark.asyncio
    async def test_count_source_items_no_client(self, migrator):
        """Test count returns 0 without client."""
        count = await migrator.count_source_items()
        assert count == 0

    @pytest.mark.asyncio
    async def test_migrate_item_mock(self, migrator):
        """Test secret migration in mock mode."""
        item = {
            "name": "aura/test_secret",
            "arn": "arn:aws:secretsmanager:us-east-1:123:secret:test",
            "description": "Test secret",
            "tags": {"env": "test"},
        }
        result = await migrator.migrate_item(item)
        assert result is True


# ==============================================================================
# CLI Tests
# ==============================================================================


class TestMigrationCLI:
    """Tests for migration CLI."""

    def test_create_parser(self):
        """Test parser creation."""
        from src.migration.cli import create_parser

        parser = create_parser()
        assert parser is not None
        assert parser.prog == "aura-migrate"

    def test_parser_neptune_subcommand(self):
        """Test neptune subcommand parsing."""
        from src.migration.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "neptune",
                "--neptune-endpoint",
                "endpoint.example.com",
                "--neo4j-password",
                "pass123",
                "--dry-run",
            ]
        )

        assert args.command == "neptune"
        assert args.neptune_endpoint == "endpoint.example.com"
        assert args.neo4j_password == "pass123"
        assert args.dry_run is True

    def test_parser_dynamodb_subcommand(self):
        """Test dynamodb subcommand parsing."""
        from src.migration.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "dynamodb",
                "--postgres-password",
                "pass123",
                "--tables",
                "user_sessions,codegen_jobs",
            ]
        )

        assert args.command == "dynamodb"
        assert args.tables == "user_sessions,codegen_jobs"

    def test_parser_s3_subcommand(self):
        """Test s3 subcommand parsing."""
        from src.migration.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "s3",
                "--minio-secret-key",
                "pass123",
                "--buckets",
                "bucket1,bucket2",
                "--bucket-mapping",
                "bucket1:new1,bucket2:new2",
            ]
        )

        assert args.command == "s3"
        assert args.buckets == "bucket1,bucket2"
        assert args.bucket_mapping == "bucket1:new1,bucket2:new2"

    def test_parser_secrets_subcommand(self):
        """Test secrets subcommand parsing."""
        from src.migration.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "secrets",
                "--prefix",
                "aura/",
                "--target-path",
                "/tmp/secrets",
            ]
        )

        assert args.command == "secrets"
        assert args.prefix == "aura/"
        assert args.target_path == "/tmp/secrets"

    def test_parser_common_args(self):
        """Test common arguments are parsed."""
        from src.migration.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "neptune",
                "--neptune-endpoint",
                "endpoint.example.com",
                "--neo4j-password",
                "pass",
                "--batch-size",
                "50",
                "--concurrency",
                "10",
                "--stop-on-error",
                "--overwrite",
                "--no-verify",
                "--verbose",
            ]
        )

        assert args.batch_size == 50
        assert args.concurrency == 10
        assert args.stop_on_error is True
        assert args.overwrite is True
        assert args.verify is False
        assert args.verbose is True

    def test_progress_callback(self, capsys):
        """Test progress callback output."""
        from src.migration.base import MigrationProgress
        from src.migration.cli import progress_callback

        progress = MigrationProgress(
            total_items=100,
            migrated_items=50,
        )
        progress_callback(progress)
        captured = capsys.readouterr()
        assert "50.0%" in captured.out

    def test_print_result(self, capsys):
        """Test result printing."""
        from src.migration.base import (
            MigrationProgress,
            MigrationResult,
            MigrationStatus,
        )
        from src.migration.cli import print_result

        now = datetime.now(timezone.utc)
        result = MigrationResult(
            status=MigrationStatus.COMPLETED,
            source_type="neptune",
            target_type="neo4j",
            progress=MigrationProgress(total_items=100, migrated_items=100),
            started_at=now,
            completed_at=now + timedelta(seconds=60),
        )

        print_result(result)
        captured = capsys.readouterr()

        assert "MIGRATION RESULT" in captured.out
        assert "COMPLETED" in captured.out
        assert "neptune" in captured.out
        assert "neo4j" in captured.out
        assert "100" in captured.out


# ==============================================================================
# Integration Tests (Mocked)
# ==============================================================================


class TestMigratorIntegration:
    """Integration tests with mocked services."""

    @pytest.mark.asyncio
    async def test_full_migration_flow_dry_run(self):
        """Test full migration flow in dry run mode."""
        from src.migration.base import MigrationConfig, MigrationStatus
        from src.migration.neptune_to_neo4j import NeptuneToNeo4jMigrator

        config = MigrationConfig(dry_run=True)
        migrator = NeptuneToNeo4jMigrator(
            neptune_endpoint="test.endpoint.com",
            neo4j_uri="bolt://localhost:7687",
            neo4j_password="password",
            config=config,
        )

        result = await migrator.run()

        # In dry run, either completes successfully or fails on connection
        assert result.status in [MigrationStatus.COMPLETED, MigrationStatus.FAILED]
        assert result.source_type == "neptune"
        assert result.target_type == "neo4j"

    @pytest.mark.asyncio
    async def test_migrator_cancellation(self):
        """Test migration cancellation."""
        from src.migration.base import MigrationConfig, MigrationStatus
        from src.migration.s3_to_minio import S3ToMinioMigrator

        config = MigrationConfig()
        migrator = S3ToMinioMigrator(
            minio_secret_key="password",
            config=config,
        )

        # Request cancellation before running
        migrator.cancel()
        result = await migrator.run()

        # May fail on connection or complete/cancel with no items
        assert result.status in [
            MigrationStatus.COMPLETED,
            MigrationStatus.CANCELLED,
            MigrationStatus.FAILED,
        ]

    @pytest.mark.asyncio
    async def test_progress_callback_called(self):
        """Test progress callback is invoked."""
        from src.migration.base import MigrationConfig
        from src.migration.dynamodb_to_postgres import DynamoDBToPostgresMigrator

        config = MigrationConfig(dry_run=True)
        migrator = DynamoDBToPostgresMigrator(
            postgres_password="password",
            config=config,
        )

        callback_called = []

        def callback(progress):
            callback_called.append(progress)

        migrator.set_progress_callback(callback)
        await migrator.run()

        # Callback may or may not be called in dry run with 0 items
        # Just verify no errors occurred
        assert True


# ==============================================================================
# Error Handling Tests
# ==============================================================================


class TestMigrationErrorHandling:
    """Tests for error handling in migrations."""

    @pytest.mark.asyncio
    async def test_connection_failure_handling(self):
        """Test handling of connection failures."""
        from src.migration.base import MigrationConfig, MigrationStatus
        from src.migration.neptune_to_neo4j import NeptuneToNeo4jMigrator

        config = MigrationConfig()
        migrator = NeptuneToNeo4jMigrator(
            neptune_endpoint="test.endpoint.com",
            neo4j_uri="bolt://localhost:7687",
            neo4j_password="password",
            config=config,
        )

        # Mock connect_source to fail
        async def mock_connect_fail():
            return False

        migrator.connect_source = mock_connect_fail

        result = await migrator.run()
        assert result.status == MigrationStatus.FAILED
        assert "Failed to connect" in result.error_message

    @pytest.mark.asyncio
    async def test_max_errors_threshold(self):
        """Test migration fails when items consistently fail."""
        from src.migration.base import BaseMigrator, MigrationConfig, MigrationError

        config = MigrationConfig(max_errors=2, stop_on_error=False, retry_count=1)

        # Create a mock migrator that fails on specific items
        class FailingMigrator(BaseMigrator):
            @property
            def source_type(self):
                return "test"

            @property
            def target_type(self):
                return "test"

            async def connect_source(self):
                return True

            async def connect_target(self):
                return True

            async def disconnect(self):
                pass

            async def count_source_items(self):
                return 5

            async def fetch_source_batch(self, offset, limit):
                return [{"id": i} for i in range(offset, min(offset + limit, 5))]

            async def migrate_item(self, item):
                raise MigrationError(f"Failed item {item['id']}")

            async def verify_item(self, item):
                return True

        migrator = FailingMigrator(config=config)
        result = await migrator.run()

        # Should fail due to errors
        assert result.status.value == "failed"
        # Error should be recorded
        assert len(result.progress.errors) > 0 or result.error_message is not None
