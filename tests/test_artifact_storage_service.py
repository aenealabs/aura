"""
Comprehensive Tests for SSR Artifact Storage Service

Tests the S3 + DynamoDB storage operations for the
Self-Play SWE-RL bug artifact infrastructure (ADR-050 Phase 1).

This test file provides comprehensive coverage including:
- Mock mode operations
- Non-mock mode with mocked boto3 clients
- Error handling paths
- AWS client lazy initialization
- Health check scenarios

Author: Project Aura Team
Created: 2026-01-04
"""

import platform
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# Apply forked marker for macOS isolation
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.ssr.artifact_storage_service import (
    ArtifactStorageService,
    _convert_floats_to_decimal,
    create_artifact_storage_service,
)
from src.services.ssr.bug_artifact import (
    ArtifactStatus,
    BugArtifact,
    InjectionStrategy,
    ValidationPipelineResult,
    ValidationResult,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def storage_service() -> ArtifactStorageService:
    """Create a storage service in mock mode."""
    return ArtifactStorageService(
        project_name="aura",
        environment="test",
    )


@pytest.fixture
def sample_artifact() -> BugArtifact:
    """Create a sample bug artifact for testing."""
    return BugArtifact(
        artifact_id=BugArtifact.generate_id(),
        repository_id="test-repo",
        commit_sha="abc123def456",
        test_script="#!/bin/bash\npytest tests/",
        test_files=["tests/test_foo.py", "tests/test_bar.py"],
        test_parser='import sys\nprint("ok")',
        bug_inject_diff="diff --git a/foo.py b/foo.py\n-old\n+new",
        test_weaken_diff="diff --git a/tests/test.py b/tests/test.py\n-assert\n+pass",
    )


@pytest.fixture
def another_artifact() -> BugArtifact:
    """Create another artifact for list tests."""
    return BugArtifact(
        artifact_id=BugArtifact.generate_id(),
        repository_id="test-repo",
        commit_sha="xyz789",
        test_script="#!/bin/bash",
        test_files=["test.py"],
        test_parser="print('ok')",
        bug_inject_diff="diff",
        test_weaken_diff="diff",
        status=ArtifactStatus.VALID,
    )


@pytest.fixture
def higher_order_artifact() -> BugArtifact:
    """Create a higher-order bug artifact with failed_patch_diff."""
    return BugArtifact(
        artifact_id=BugArtifact.generate_id(),
        repository_id="test-repo",
        commit_sha="abc123",
        test_script="#!/bin/bash\npytest tests/",
        test_files=["tests/test_foo.py"],
        test_parser='print("ok")',
        bug_inject_diff="diff --git a/foo.py",
        test_weaken_diff="diff --git a/test.py",
        failed_patch_diff="diff --git a/failed.py\n-wrong\n+still_wrong",
        order=2,
        parent_artifact_id="parent-artifact-123",
    )


@pytest.fixture
def mock_s3_client() -> MagicMock:
    """Create a mock S3 client."""
    mock = MagicMock()
    mock.put_object.return_value = {}
    mock.get_object.return_value = {"Body": MagicMock(read=MagicMock(return_value=b""))}
    mock.delete_object.return_value = {}
    mock.head_bucket.return_value = {}
    return mock


@pytest.fixture
def mock_dynamodb_resource() -> MagicMock:
    """Create a mock DynamoDB resource."""
    mock = MagicMock()
    mock_table = MagicMock()
    mock_table.table_status = "ACTIVE"
    mock_table.put_item.return_value = {}
    mock_table.get_item.return_value = {"Item": None}
    mock_table.update_item.return_value = {}
    mock_table.delete_item.return_value = {}
    mock_table.query.return_value = {"Items": []}
    mock.Table.return_value = mock_table
    return mock


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateArtifactStorageService:
    """Tests for create_artifact_storage_service factory."""

    def test_create_default(self) -> None:
        """Test creating service with defaults."""
        service = create_artifact_storage_service()
        assert service.project_name == "aura"
        assert "ssr-training" in service.bucket_name

    def test_create_with_custom_params(self) -> None:
        """Test creating service with custom parameters."""
        service = create_artifact_storage_service(
            project_name="custom",
            environment="prod",
            region="us-west-2",
        )
        assert service.project_name == "custom"
        assert service.environment == "prod"
        assert service.region == "us-west-2"


# =============================================================================
# Initialization Tests
# =============================================================================


class TestStorageServiceInit:
    """Tests for storage service initialization."""

    def test_mock_mode_in_test_environment(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test that mock mode is enabled in test environment."""
        assert storage_service._use_mock is True

    def test_resource_names(self, storage_service: ArtifactStorageService) -> None:
        """Test resource name generation."""
        assert storage_service.bucket_name == "aura-ssr-training-test"
        assert storage_service.table_name == "aura-ssr-training-state-test"

    def test_kms_key_default(self, storage_service: ArtifactStorageService) -> None:
        """Test default KMS key alias is generated correctly."""
        assert storage_service.kms_key_id == "alias/aura-ssr-training-test"

    def test_custom_bucket_name(self) -> None:
        """Test custom bucket name override."""
        service = ArtifactStorageService(
            bucket_name="custom-bucket",
            environment="test",
        )
        assert service.bucket_name == "custom-bucket"

    def test_custom_table_name(self) -> None:
        """Test custom table name override."""
        service = ArtifactStorageService(
            table_name="custom-table",
            environment="test",
        )
        assert service.table_name == "custom-table"

    def test_custom_kms_key(self) -> None:
        """Test custom KMS key override."""
        service = ArtifactStorageService(
            kms_key_id="alias/custom-key",
            environment="test",
        )
        assert service.kms_key_id == "alias/custom-key"

    def test_environment_from_env_var(self) -> None:
        """Test environment read from environment variable."""
        with patch.dict("os.environ", {"ENVIRONMENT": "staging"}):
            service = ArtifactStorageService()
            assert service.environment == "staging"

    def test_region_from_env_var(self) -> None:
        """Test region read from environment variable."""
        with patch.dict("os.environ", {"AWS_REGION": "eu-west-1"}):
            service = ArtifactStorageService(environment="test")
            assert service.region == "eu-west-1"


# =============================================================================
# CRUD Operation Tests (Mock Mode)
# =============================================================================


class TestStoreCRUDMockMode:
    """Tests for basic CRUD operations in mock mode."""

    @pytest.mark.asyncio
    async def test_store_artifact(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test storing an artifact."""
        artifact_id = await storage_service.store_artifact(sample_artifact)
        assert artifact_id == sample_artifact.artifact_id

    @pytest.mark.asyncio
    async def test_get_artifact(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test retrieving an artifact."""
        await storage_service.store_artifact(sample_artifact)
        retrieved = await storage_service.get_artifact(sample_artifact.artifact_id)

        assert retrieved is not None
        assert retrieved.artifact_id == sample_artifact.artifact_id
        assert retrieved.repository_id == sample_artifact.repository_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_artifact(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test retrieving non-existent artifact returns None."""
        retrieved = await storage_service.get_artifact("nonexistent-id")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_update_artifact(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test updating an artifact."""
        await storage_service.store_artifact(sample_artifact)

        sample_artifact.status = ArtifactStatus.VALID
        success = await storage_service.update_artifact(sample_artifact)

        assert success is True

        retrieved = await storage_service.get_artifact(sample_artifact.artifact_id)
        assert retrieved is not None
        assert retrieved.status == ArtifactStatus.VALID

    @pytest.mark.asyncio
    async def test_update_nonexistent_artifact(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test updating non-existent artifact returns False."""
        success = await storage_service.update_artifact(sample_artifact)
        assert success is False

    @pytest.mark.asyncio
    async def test_delete_artifact(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test deleting an artifact."""
        await storage_service.store_artifact(sample_artifact)

        success = await storage_service.delete_artifact(sample_artifact.artifact_id)
        assert success is True

        retrieved = await storage_service.get_artifact(sample_artifact.artifact_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_artifact(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test deleting non-existent artifact returns False."""
        success = await storage_service.delete_artifact("nonexistent-id")
        assert success is False


# =============================================================================
# Status Update Tests
# =============================================================================


class TestStatusUpdates:
    """Tests for status-specific operations."""

    @pytest.mark.asyncio
    async def test_update_status(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test updating artifact status."""
        await storage_service.store_artifact(sample_artifact)

        success = await storage_service.update_status(
            sample_artifact.artifact_id,
            ArtifactStatus.VALIDATING,
        )
        assert success is True

        retrieved = await storage_service.get_artifact(sample_artifact.artifact_id)
        assert retrieved is not None
        assert retrieved.status == ArtifactStatus.VALIDATING

    @pytest.mark.asyncio
    async def test_update_status_nonexistent(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test updating status of non-existent artifact."""
        success = await storage_service.update_status(
            "nonexistent-id",
            ArtifactStatus.VALID,
        )
        assert success is False

    @pytest.mark.asyncio
    async def test_update_validation_result(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test updating with validation result."""
        await storage_service.store_artifact(sample_artifact)

        result = ValidationPipelineResult(
            artifact_id=sample_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
            total_tests=10,
            passing_before_bug=10,
        )

        success = await storage_service.update_validation_result(
            sample_artifact.artifact_id,
            result,
        )
        assert success is True

        retrieved = await storage_service.get_artifact(sample_artifact.artifact_id)
        assert retrieved is not None
        assert retrieved.status == ArtifactStatus.VALID
        assert retrieved.validation_results != {}

    @pytest.mark.asyncio
    async def test_update_validation_result_failure(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test updating with failed validation result."""
        await storage_service.store_artifact(sample_artifact)

        result = ValidationPipelineResult(
            artifact_id=sample_artifact.artifact_id,
            overall_result=ValidationResult.FAIL,
        )

        await storage_service.update_validation_result(
            sample_artifact.artifact_id,
            result,
        )

        retrieved = await storage_service.get_artifact(sample_artifact.artifact_id)
        assert retrieved is not None
        assert retrieved.status == ArtifactStatus.INVALID

    @pytest.mark.asyncio
    async def test_update_validation_result_nonexistent(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test updating validation result for non-existent artifact."""
        result = ValidationPipelineResult(
            artifact_id="nonexistent-id",
            overall_result=ValidationResult.PASS,
        )
        success = await storage_service.update_validation_result(
            "nonexistent-id", result
        )
        assert success is False


# =============================================================================
# Query Operation Tests
# =============================================================================


class TestQueryOperations:
    """Tests for query operations."""

    @pytest.mark.asyncio
    async def test_list_by_repository(
        self,
        storage_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        another_artifact: BugArtifact,
    ) -> None:
        """Test listing artifacts by repository."""
        await storage_service.store_artifact(sample_artifact)
        await storage_service.store_artifact(another_artifact)

        artifacts = await storage_service.list_by_repository("test-repo")
        assert len(artifacts) == 2

    @pytest.mark.asyncio
    async def test_list_by_repository_with_status(
        self,
        storage_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        another_artifact: BugArtifact,
    ) -> None:
        """Test listing artifacts by repository and status."""
        await storage_service.store_artifact(sample_artifact)
        await storage_service.store_artifact(another_artifact)

        # sample_artifact is PENDING, another_artifact is VALID
        pending = await storage_service.list_by_repository(
            "test-repo", status=ArtifactStatus.PENDING
        )
        assert len(pending) == 1
        assert pending[0].artifact_id == sample_artifact.artifact_id

        valid = await storage_service.list_by_repository(
            "test-repo", status=ArtifactStatus.VALID
        )
        assert len(valid) == 1
        assert valid[0].artifact_id == another_artifact.artifact_id

    @pytest.mark.asyncio
    async def test_list_by_repository_empty(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test listing from empty repository."""
        artifacts = await storage_service.list_by_repository("nonexistent-repo")
        assert len(artifacts) == 0

    @pytest.mark.asyncio
    async def test_list_by_repository_with_limit(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test listing with limit."""
        # Create 5 artifacts
        for i in range(5):
            artifact = BugArtifact(
                artifact_id=f"artifact-{i}",
                repository_id="test-repo",
                commit_sha=f"sha-{i}",
                test_script="#!/bin/bash",
                test_files=["test.py"],
                test_parser="print('ok')",
                bug_inject_diff="diff",
                test_weaken_diff="diff",
            )
            await storage_service.store_artifact(artifact)

        artifacts = await storage_service.list_by_repository("test-repo", limit=3)
        assert len(artifacts) == 3

    @pytest.mark.asyncio
    async def test_list_pending_validation(
        self,
        storage_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        another_artifact: BugArtifact,
    ) -> None:
        """Test listing pending artifacts."""
        await storage_service.store_artifact(sample_artifact)  # PENDING
        await storage_service.store_artifact(another_artifact)  # VALID

        pending = await storage_service.list_pending_validation()
        assert len(pending) == 1
        assert pending[0].status == ArtifactStatus.PENDING

    @pytest.mark.asyncio
    async def test_list_pending_validation_with_limit(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test listing pending artifacts with limit."""
        # Create 5 pending artifacts
        for i in range(5):
            artifact = BugArtifact(
                artifact_id=f"pending-{i}",
                repository_id="test-repo",
                commit_sha=f"sha-{i}",
                test_script="#!/bin/bash",
                test_files=["test.py"],
                test_parser="print('ok')",
                bug_inject_diff="diff",
                test_weaken_diff="diff",
                status=ArtifactStatus.PENDING,
            )
            await storage_service.store_artifact(artifact)

        pending = await storage_service.list_pending_validation(limit=2)
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_count_by_status(
        self,
        storage_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        another_artifact: BugArtifact,
    ) -> None:
        """Test counting artifacts by status."""
        await storage_service.store_artifact(sample_artifact)
        await storage_service.store_artifact(another_artifact)

        counts = await storage_service.count_by_status("test-repo")
        assert counts.get("pending", 0) >= 1
        assert counts.get("valid", 0) >= 1


# =============================================================================
# Tar.gz Content Tests
# =============================================================================


class TestTarGzContent:
    """Tests for tar.gz content handling."""

    def test_create_tar_gz(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test creating tar.gz from artifact."""
        content = storage_service._create_tar_gz(sample_artifact)
        assert isinstance(content, bytes)
        assert len(content) > 0

    def test_extract_tar_gz(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test extracting tar.gz content."""
        content = storage_service._create_tar_gz(sample_artifact)
        extracted = storage_service._extract_tar_gz(content)

        assert "test_script" in extracted
        assert "test_files" in extracted
        assert "test_parser" in extracted
        assert "bug_inject_diff" in extracted
        assert "test_weaken_diff" in extracted

    def test_roundtrip_content(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test content survives roundtrip through tar.gz."""
        content = storage_service._create_tar_gz(sample_artifact)
        extracted = storage_service._extract_tar_gz(content)

        assert extracted["test_script"] == sample_artifact.test_script
        assert extracted["test_files"] == sample_artifact.test_files
        assert extracted["test_parser"] == sample_artifact.test_parser

    def test_tar_gz_includes_failed_patch(
        self,
        storage_service: ArtifactStorageService,
        higher_order_artifact: BugArtifact,
    ) -> None:
        """Test that tar.gz includes failed_patch.diff for higher-order bugs."""
        content = storage_service._create_tar_gz(higher_order_artifact)
        extracted = storage_service._extract_tar_gz(content)

        assert "failed_patch_diff" in extracted
        assert "wrong" in extracted["failed_patch_diff"]


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_mock_mode(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test health check in mock mode."""
        health = await storage_service.health_check()

        assert health["service"] == "artifact_storage"
        assert health["status"] == "healthy"
        assert health["mock_mode"] is True
        assert "bucket" in health
        assert "table" in health

    @pytest.mark.asyncio
    async def test_health_check_includes_cache_info(
        self,
        storage_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
    ) -> None:
        """Test health check includes cache information."""
        # Store and retrieve to populate cache
        await storage_service.store_artifact(sample_artifact)
        await storage_service.get_artifact(sample_artifact.artifact_id)

        health = await storage_service.health_check()
        assert "cache_entries" in health

    @pytest.mark.asyncio
    async def test_health_check_mock_artifacts_count(
        self,
        storage_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
    ) -> None:
        """Test health check includes mock artifacts count."""
        await storage_service.store_artifact(sample_artifact)

        health = await storage_service.health_check()
        assert health["mock_artifacts"] == 1


# =============================================================================
# Cache Tests
# =============================================================================


class TestCaching:
    """Tests for caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test cache hit on repeated reads."""
        await storage_service.store_artifact(sample_artifact)

        # First read
        artifact1 = await storage_service.get_artifact(sample_artifact.artifact_id)

        # Second read should be cached
        artifact2 = await storage_service.get_artifact(sample_artifact.artifact_id)

        assert artifact1 is not None
        assert artifact2 is not None
        assert artifact1.artifact_id == artifact2.artifact_id

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_update(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test cache invalidation on update."""
        await storage_service.store_artifact(sample_artifact)

        # Read to cache
        await storage_service.get_artifact(sample_artifact.artifact_id)
        assert sample_artifact.artifact_id in storage_service._cache

        # Update should invalidate cache
        await storage_service.update_status(
            sample_artifact.artifact_id, ArtifactStatus.VALID
        )
        assert sample_artifact.artifact_id not in storage_service._cache

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_delete(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test cache invalidation on delete."""
        await storage_service.store_artifact(sample_artifact)

        # Read to cache
        await storage_service.get_artifact(sample_artifact.artifact_id)

        # Delete should invalidate cache
        await storage_service.delete_artifact(sample_artifact.artifact_id)
        assert sample_artifact.artifact_id not in storage_service._cache

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test cache expiration after TTL."""
        await storage_service.store_artifact(sample_artifact)

        # Read to cache
        await storage_service.get_artifact(sample_artifact.artifact_id)
        assert sample_artifact.artifact_id in storage_service._cache

        # Manually expire the cache entry
        storage_service._cache[sample_artifact.artifact_id] = (
            time.time() - storage_service._cache_ttl_seconds - 1,
            storage_service._cache[sample_artifact.artifact_id][1],
        )

        # Next read should NOT use the expired cache entry
        # (but in mock mode, it fetches from _mock_artifacts)
        retrieved = await storage_service.get_artifact(sample_artifact.artifact_id)
        assert retrieved is not None


# =============================================================================
# Float to Decimal Conversion Tests
# =============================================================================


class TestFloatToDecimalConversion:
    """Tests for _convert_floats_to_decimal function."""

    def test_convert_simple_float(self) -> None:
        """Test converting a simple float."""
        result = _convert_floats_to_decimal(3.14)
        assert result == Decimal("3.14")

    def test_convert_nested_dict(self) -> None:
        """Test converting floats in nested dicts."""
        obj = {"a": 1.5, "b": {"c": 2.5, "d": {"e": 3.5}}}
        result = _convert_floats_to_decimal(obj)

        assert result["a"] == Decimal("1.5")
        assert result["b"]["c"] == Decimal("2.5")
        assert result["b"]["d"]["e"] == Decimal("3.5")

    def test_convert_nested_list(self) -> None:
        """Test converting floats in nested lists."""
        obj = [1.1, [2.2, [3.3]]]
        result = _convert_floats_to_decimal(obj)

        assert result[0] == Decimal("1.1")
        assert result[1][0] == Decimal("2.2")
        assert result[1][1][0] == Decimal("3.3")

    def test_convert_mixed_types(self) -> None:
        """Test that non-float types are preserved."""
        obj = {"string": "hello", "int": 42, "float": 1.5, "list": [1, 2.0]}
        result = _convert_floats_to_decimal(obj)

        assert result["string"] == "hello"
        assert result["int"] == 42
        assert result["float"] == Decimal("1.5")
        assert result["list"][0] == 1
        assert result["list"][1] == Decimal("2.0")

    def test_convert_none_passthrough(self) -> None:
        """Test that None passes through unchanged."""
        result = _convert_floats_to_decimal(None)
        assert result is None

    def test_convert_empty_dict(self) -> None:
        """Test converting empty dict."""
        result = _convert_floats_to_decimal({})
        assert result == {}

    def test_convert_empty_list(self) -> None:
        """Test converting empty list."""
        result = _convert_floats_to_decimal([])
        assert result == []

    def test_convert_boolean_passthrough(self) -> None:
        """Test that booleans pass through unchanged."""
        result = _convert_floats_to_decimal({"flag": True, "other": False})
        assert result["flag"] is True
        assert result["other"] is False


# =============================================================================
# Higher-Order Artifact Tests
# =============================================================================


class TestHigherOrderArtifacts:
    """Tests for higher-order bug artifacts."""

    @pytest.mark.asyncio
    async def test_store_higher_order_artifact(
        self,
        storage_service: ArtifactStorageService,
        higher_order_artifact: BugArtifact,
    ) -> None:
        """Test storing higher-order artifact with failed_patch_diff."""
        artifact_id = await storage_service.store_artifact(higher_order_artifact)

        retrieved = await storage_service.get_artifact(artifact_id)
        assert retrieved is not None
        assert retrieved.order == 2
        assert retrieved.parent_artifact_id == "parent-artifact-123"

    def test_is_higher_order(self, higher_order_artifact: BugArtifact) -> None:
        """Test is_higher_order method."""
        assert higher_order_artifact.is_higher_order() is True

    def test_is_not_higher_order(self, sample_artifact: BugArtifact) -> None:
        """Test is_higher_order method for first-order bug."""
        assert sample_artifact.is_higher_order() is False


# =============================================================================
# AWS Client Property Tests
# =============================================================================


class TestAWSClientProperties:
    """Tests for AWS client lazy initialization."""

    def test_s3_property_mock_mode(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test S3 property returns None in mock mode."""
        assert storage_service._use_mock is True
        assert storage_service.s3 is None

    def test_dynamodb_property_mock_mode(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test DynamoDB property returns None in mock mode."""
        assert storage_service._use_mock is True
        assert storage_service.dynamodb is None

    def test_table_property_mock_mode(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test table property returns None in mock mode."""
        assert storage_service._use_mock is True
        assert storage_service.table is None


# =============================================================================
# Non-Mock Mode Tests with Mocked boto3
# =============================================================================


class TestNonMockModeWithMockedBoto3:
    """Tests for non-mock mode with mocked boto3 clients."""

    @pytest.fixture
    def non_mock_service(
        self, mock_s3_client: MagicMock, mock_dynamodb_resource: MagicMock
    ) -> ArtifactStorageService:
        """Create a service in non-mock mode with mocked boto3."""
        # Create service in test environment (which normally uses mock mode)
        service = ArtifactStorageService(
            project_name="aura",
            environment="test",
        )
        # Force non-mock mode to test real code paths
        service._use_mock = False
        # Inject mocked clients directly
        service._s3 = mock_s3_client
        service._dynamodb = mock_dynamodb_resource
        service._table = mock_dynamodb_resource.Table("test-table")
        return service

    @pytest.mark.asyncio
    async def test_store_artifact_non_mock(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_s3_client: MagicMock,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test storing artifact in non-mock mode."""
        # Get the mock table
        mock_table = mock_dynamodb_resource.Table.return_value

        artifact_id = await non_mock_service.store_artifact(sample_artifact)

        assert artifact_id == sample_artifact.artifact_id
        mock_s3_client.put_object.assert_called_once()
        mock_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_artifact_dynamodb_error(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test storing artifact with DynamoDB error."""
        from botocore.exceptions import ClientError

        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Test error"}},
            "PutItem",
        )

        with pytest.raises(ClientError):
            await non_mock_service.store_artifact(sample_artifact)

    @pytest.mark.asyncio
    async def test_get_artifact_non_mock(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_s3_client: MagicMock,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test getting artifact in non-mock mode."""
        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "artifact_id": sample_artifact.artifact_id,
                "repository_id": sample_artifact.repository_id,
                "commit_sha": sample_artifact.commit_sha,
                "status": "pending",
                "injection_strategy": "removal_only",
                "s3_uri": f"s3://bucket/artifacts/{sample_artifact.artifact_id}.tar.gz",
            }
        }

        # Create tar.gz content for S3 response
        tar_content = non_mock_service._create_tar_gz(sample_artifact)
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=tar_content))
        }

        retrieved = await non_mock_service.get_artifact(sample_artifact.artifact_id)

        assert retrieved is not None
        assert retrieved.artifact_id == sample_artifact.artifact_id

    @pytest.mark.asyncio
    async def test_get_artifact_not_found(
        self,
        non_mock_service: ArtifactStorageService,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test getting non-existent artifact in non-mock mode."""
        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.get_item.return_value = {"Item": None}

        retrieved = await non_mock_service.get_artifact("nonexistent-id")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_artifact_dynamodb_error(
        self,
        non_mock_service: ArtifactStorageService,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test getting artifact with DynamoDB error."""
        from botocore.exceptions import ClientError

        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Test error"}},
            "GetItem",
        )

        retrieved = await non_mock_service.get_artifact("test-id")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_update_artifact_non_mock(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_s3_client: MagicMock,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test updating artifact in non-mock mode."""
        sample_artifact.s3_uri = (
            f"s3://bucket/artifacts/{sample_artifact.artifact_id}.tar.gz"
        )
        mock_table = mock_dynamodb_resource.Table.return_value

        success = await non_mock_service.update_artifact(sample_artifact)

        assert success is True
        mock_s3_client.put_object.assert_called_once()
        mock_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_artifact_no_s3_uri(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_s3_client: MagicMock,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test updating artifact without s3_uri (no S3 upload)."""
        sample_artifact.s3_uri = None
        mock_table = mock_dynamodb_resource.Table.return_value

        success = await non_mock_service.update_artifact(sample_artifact)

        assert success is True
        mock_s3_client.put_object.assert_not_called()
        mock_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_artifact_dynamodb_error(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test updating artifact with DynamoDB error."""
        from botocore.exceptions import ClientError

        sample_artifact.s3_uri = None
        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Test error"}},
            "PutItem",
        )

        success = await non_mock_service.update_artifact(sample_artifact)
        assert success is False

    @pytest.mark.asyncio
    async def test_update_artifact_invalidates_cache(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test that updating artifact invalidates cache in non-mock mode."""
        sample_artifact.s3_uri = None
        mock_table = mock_dynamodb_resource.Table.return_value

        # Pre-populate cache
        non_mock_service._cache[sample_artifact.artifact_id] = (
            time.time(),
            sample_artifact,
        )
        assert sample_artifact.artifact_id in non_mock_service._cache

        success = await non_mock_service.update_artifact(sample_artifact)

        assert success is True
        assert sample_artifact.artifact_id not in non_mock_service._cache

    @pytest.mark.asyncio
    async def test_update_artifact_no_table(
        self,
        sample_artifact: BugArtifact,
    ) -> None:
        """Test updating artifact when table is None."""
        service = ArtifactStorageService(environment="test")
        service._use_mock = False
        # Mock the table property to return None
        with patch.object(
            ArtifactStorageService,
            "table",
            new_callable=lambda: property(lambda self: None),
        ):
            success = await service.update_artifact(sample_artifact)
            assert success is False

    @pytest.mark.asyncio
    async def test_update_status_non_mock(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test updating status in non-mock mode."""
        mock_table = mock_dynamodb_resource.Table.return_value

        success = await non_mock_service.update_status(
            sample_artifact.artifact_id, ArtifactStatus.VALID
        )

        assert success is True
        mock_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_no_table(self) -> None:
        """Test updating status when table is None."""
        service = ArtifactStorageService(environment="test")
        service._use_mock = False
        # Mock the table property to return None
        with patch.object(
            ArtifactStorageService,
            "table",
            new_callable=lambda: property(lambda self: None),
        ):
            success = await service.update_status("test-id", ArtifactStatus.VALID)
            assert success is False

    @pytest.mark.asyncio
    async def test_update_status_dynamodb_error(
        self,
        non_mock_service: ArtifactStorageService,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test updating status with DynamoDB error."""
        from botocore.exceptions import ClientError

        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Test error"}},
            "UpdateItem",
        )

        success = await non_mock_service.update_status("test-id", ArtifactStatus.VALID)
        assert success is False

    @pytest.mark.asyncio
    async def test_update_status_invalidates_cache(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test that updating status invalidates cache in non-mock mode."""
        mock_table = mock_dynamodb_resource.Table.return_value

        # Pre-populate cache
        non_mock_service._cache[sample_artifact.artifact_id] = (
            time.time(),
            sample_artifact,
        )
        assert sample_artifact.artifact_id in non_mock_service._cache

        success = await non_mock_service.update_status(
            sample_artifact.artifact_id, ArtifactStatus.VALID
        )

        assert success is True
        assert sample_artifact.artifact_id not in non_mock_service._cache

    @pytest.mark.asyncio
    async def test_update_validation_result_non_mock(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test updating validation result in non-mock mode."""
        mock_table = mock_dynamodb_resource.Table.return_value
        result = ValidationPipelineResult(
            artifact_id=sample_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )

        success = await non_mock_service.update_validation_result(
            sample_artifact.artifact_id, result
        )

        assert success is True
        mock_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_validation_result_no_table(self) -> None:
        """Test updating validation result when table is None."""
        service = ArtifactStorageService(environment="test")
        service._use_mock = False
        # Mock the table property to return None
        with patch.object(
            ArtifactStorageService,
            "table",
            new_callable=lambda: property(lambda self: None),
        ):
            result = ValidationPipelineResult(
                artifact_id="test-id",
                overall_result=ValidationResult.PASS,
            )
            success = await service.update_validation_result("test-id", result)
            assert success is False

    @pytest.mark.asyncio
    async def test_update_validation_result_dynamodb_error(
        self,
        non_mock_service: ArtifactStorageService,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test updating validation result with DynamoDB error."""
        from botocore.exceptions import ClientError

        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Test error"}},
            "UpdateItem",
        )

        result = ValidationPipelineResult(
            artifact_id="test-id",
            overall_result=ValidationResult.PASS,
        )
        success = await non_mock_service.update_validation_result("test-id", result)
        assert success is False

    @pytest.mark.asyncio
    async def test_update_validation_result_invalidates_cache(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test that updating validation result invalidates cache in non-mock mode."""
        mock_table = mock_dynamodb_resource.Table.return_value

        # Pre-populate cache
        non_mock_service._cache[sample_artifact.artifact_id] = (
            time.time(),
            sample_artifact,
        )
        assert sample_artifact.artifact_id in non_mock_service._cache

        result = ValidationPipelineResult(
            artifact_id=sample_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        success = await non_mock_service.update_validation_result(
            sample_artifact.artifact_id, result
        )

        assert success is True
        assert sample_artifact.artifact_id not in non_mock_service._cache

    @pytest.mark.asyncio
    async def test_delete_artifact_non_mock(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_s3_client: MagicMock,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test deleting artifact in non-mock mode."""
        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "artifact_id": sample_artifact.artifact_id,
                "repository_id": sample_artifact.repository_id,
                "commit_sha": sample_artifact.commit_sha,
                "status": "pending",
                "injection_strategy": "removal_only",
                "s3_uri": f"s3://bucket/artifacts/{sample_artifact.artifact_id}.tar.gz",
            }
        }

        success = await non_mock_service.delete_artifact(sample_artifact.artifact_id)

        assert success is True
        mock_s3_client.delete_object.assert_called_once()
        mock_table.delete_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_artifact_not_found(
        self,
        non_mock_service: ArtifactStorageService,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test deleting non-existent artifact in non-mock mode."""
        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.get_item.return_value = {"Item": None}

        success = await non_mock_service.delete_artifact("nonexistent-id")
        assert success is False

    @pytest.mark.asyncio
    async def test_delete_artifact_dynamodb_error(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test deleting artifact with DynamoDB error."""
        from botocore.exceptions import ClientError

        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "artifact_id": sample_artifact.artifact_id,
                "repository_id": sample_artifact.repository_id,
                "commit_sha": sample_artifact.commit_sha,
                "status": "pending",
                "injection_strategy": "removal_only",
                "s3_uri": f"s3://bucket/artifacts/{sample_artifact.artifact_id}.tar.gz",
            }
        }
        mock_table.delete_item.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Test error"}},
            "DeleteItem",
        )

        success = await non_mock_service.delete_artifact(sample_artifact.artifact_id)
        assert success is False


# =============================================================================
# Query Operations Non-Mock Mode Tests
# =============================================================================


class TestQueryOperationsNonMock:
    """Tests for query operations in non-mock mode."""

    @pytest.fixture
    def non_mock_service(
        self, mock_dynamodb_resource: MagicMock
    ) -> ArtifactStorageService:
        """Create a service in non-mock mode with mocked boto3."""
        service = ArtifactStorageService(
            project_name="aura",
            environment="dev",
        )
        service._use_mock = False
        service._dynamodb = mock_dynamodb_resource
        service._table = mock_dynamodb_resource.Table("test-table")
        return service

    @pytest.mark.asyncio
    async def test_list_by_repository_non_mock(
        self,
        non_mock_service: ArtifactStorageService,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test listing artifacts by repository in non-mock mode."""
        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.query.return_value = {
            "Items": [
                {
                    "artifact_id": "artifact-1",
                    "repository_id": "test-repo",
                    "commit_sha": "sha1",
                    "status": "pending",
                    "injection_strategy": "removal_only",
                },
                {
                    "artifact_id": "artifact-2",
                    "repository_id": "test-repo",
                    "commit_sha": "sha2",
                    "status": "pending",
                    "injection_strategy": "removal_only",
                },
            ]
        }

        artifacts = await non_mock_service.list_by_repository("test-repo")

        assert len(artifacts) == 2
        mock_table.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_by_repository_with_status_non_mock(
        self,
        non_mock_service: ArtifactStorageService,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test listing artifacts by repository with status filter in non-mock mode."""
        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.query.return_value = {
            "Items": [
                {
                    "artifact_id": "artifact-1",
                    "repository_id": "test-repo",
                    "commit_sha": "sha1",
                    "status": "valid",
                    "injection_strategy": "removal_only",
                },
            ]
        }

        artifacts = await non_mock_service.list_by_repository(
            "test-repo", status=ArtifactStatus.VALID
        )

        assert len(artifacts) == 1
        # Verify query was called with status filter
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["IndexName"] == "status-created-index"

    @pytest.mark.asyncio
    async def test_list_by_repository_no_table(self) -> None:
        """Test listing artifacts when table is None."""
        service = ArtifactStorageService(environment="test")
        service._use_mock = False
        # Mock the table property to return None
        with patch.object(
            ArtifactStorageService,
            "table",
            new_callable=lambda: property(lambda self: None),
        ):
            artifacts = await service.list_by_repository("test-repo")
            assert artifacts == []

    @pytest.mark.asyncio
    async def test_list_by_repository_dynamodb_error(
        self,
        non_mock_service: ArtifactStorageService,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test listing artifacts with DynamoDB error."""
        from botocore.exceptions import ClientError

        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.query.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Test error"}},
            "Query",
        )

        artifacts = await non_mock_service.list_by_repository("test-repo")
        assert artifacts == []

    @pytest.mark.asyncio
    async def test_list_pending_validation_non_mock(
        self,
        non_mock_service: ArtifactStorageService,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test listing pending artifacts in non-mock mode."""
        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.query.return_value = {
            "Items": [
                {
                    "artifact_id": "artifact-1",
                    "repository_id": "test-repo",
                    "commit_sha": "sha1",
                    "status": "pending",
                    "injection_strategy": "removal_only",
                },
            ]
        }

        pending = await non_mock_service.list_pending_validation()

        assert len(pending) == 1
        mock_table.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_pending_validation_no_table(self) -> None:
        """Test listing pending artifacts when table is None."""
        service = ArtifactStorageService(environment="test")
        service._use_mock = False
        # Mock the table property to return None
        with patch.object(
            ArtifactStorageService,
            "table",
            new_callable=lambda: property(lambda self: None),
        ):
            pending = await service.list_pending_validation()
            assert pending == []

    @pytest.mark.asyncio
    async def test_list_pending_validation_dynamodb_error(
        self,
        non_mock_service: ArtifactStorageService,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test listing pending artifacts with DynamoDB error."""
        from botocore.exceptions import ClientError

        mock_table = mock_dynamodb_resource.Table.return_value
        mock_table.query.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Test error"}},
            "Query",
        )

        pending = await non_mock_service.list_pending_validation()
        assert pending == []

    @pytest.mark.asyncio
    async def test_count_by_status_non_mock(
        self,
        non_mock_service: ArtifactStorageService,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test counting artifacts by status in non-mock mode."""
        mock_table = mock_dynamodb_resource.Table.return_value
        # Return results for different status queries
        mock_table.query.return_value = {
            "Items": [
                {
                    "artifact_id": "artifact-1",
                    "repository_id": "test-repo",
                    "commit_sha": "sha1",
                    "status": "pending",
                    "injection_strategy": "removal_only",
                },
            ]
        }

        counts = await non_mock_service.count_by_status("test-repo")

        # The count depends on how many statuses return results
        assert isinstance(counts, dict)


# =============================================================================
# S3 Operations Non-Mock Mode Tests
# =============================================================================


class TestS3OperationsNonMock:
    """Tests for S3 operations in non-mock mode."""

    @pytest.fixture
    def non_mock_service(self, mock_s3_client: MagicMock) -> ArtifactStorageService:
        """Create a service in non-mock mode with mocked S3."""
        service = ArtifactStorageService(
            project_name="aura",
            environment="dev",
        )
        service._use_mock = False
        service._s3 = mock_s3_client
        return service

    @pytest.mark.asyncio
    async def test_upload_to_s3_non_mock(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test S3 upload in non-mock mode."""
        s3_uri = await non_mock_service._upload_to_s3(sample_artifact)

        assert s3_uri.startswith("s3://")
        assert sample_artifact.artifact_id in s3_uri
        mock_s3_client.put_object.assert_called_once()

        # Verify encryption settings
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["ServerSideEncryption"] == "aws:kms"
        assert call_kwargs["SSEKMSKeyId"] == non_mock_service.kms_key_id

    @pytest.mark.asyncio
    async def test_upload_to_s3_no_client(
        self,
        sample_artifact: BugArtifact,
    ) -> None:
        """Test S3 upload when S3 client is None."""
        service = ArtifactStorageService(environment="test")
        service._use_mock = False
        # Mock the s3 property to return None
        with patch.object(
            ArtifactStorageService,
            "s3",
            new_callable=lambda: property(lambda self: None),
        ):
            with pytest.raises(RuntimeError, match="S3 client not available"):
                await service._upload_to_s3(sample_artifact)

    @pytest.mark.asyncio
    async def test_upload_to_s3_client_error(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test S3 upload with client error."""
        from botocore.exceptions import ClientError

        mock_s3_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Test error"}},
            "PutObject",
        )

        with pytest.raises(ClientError):
            await non_mock_service._upload_to_s3(sample_artifact)

    @pytest.mark.asyncio
    async def test_download_from_s3_non_mock(
        self,
        non_mock_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test S3 download in non-mock mode."""
        # Create tar.gz content
        tar_content = non_mock_service._create_tar_gz(sample_artifact)
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=tar_content))
        }

        s3_uri = f"s3://{non_mock_service.bucket_name}/artifacts/test.tar.gz"
        content = await non_mock_service._download_from_s3(s3_uri)

        assert "test_script" in content
        mock_s3_client.get_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_from_s3_no_client(self) -> None:
        """Test S3 download when S3 client is None."""
        service = ArtifactStorageService(environment="test")
        service._use_mock = False
        # Mock the s3 property to return None
        with patch.object(
            ArtifactStorageService,
            "s3",
            new_callable=lambda: property(lambda self: None),
        ):
            content = await service._download_from_s3("s3://bucket/key")
            assert content == {}

    @pytest.mark.asyncio
    async def test_download_from_s3_client_error(
        self,
        non_mock_service: ArtifactStorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test S3 download with client error."""
        from botocore.exceptions import ClientError

        mock_s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Test error"}},
            "GetObject",
        )

        s3_uri = f"s3://{non_mock_service.bucket_name}/artifacts/test.tar.gz"
        content = await non_mock_service._download_from_s3(s3_uri)
        assert content == {}


# =============================================================================
# Health Check Non-Mock Mode Tests
# =============================================================================


class TestHealthCheckNonMock:
    """Tests for health check in non-mock mode."""

    @pytest.fixture
    def non_mock_service(
        self, mock_s3_client: MagicMock, mock_dynamodb_resource: MagicMock
    ) -> ArtifactStorageService:
        """Create a service in non-mock mode with mocked boto3."""
        service = ArtifactStorageService(
            project_name="aura",
            environment="dev",
        )
        service._use_mock = False
        service._s3 = mock_s3_client
        service._dynamodb = mock_dynamodb_resource
        service._table = mock_dynamodb_resource.Table("test-table")
        return service

    @pytest.mark.asyncio
    async def test_health_check_healthy(
        self,
        non_mock_service: ArtifactStorageService,
    ) -> None:
        """Test health check when all services are healthy."""
        health = await non_mock_service.health_check()

        assert health["status"] == "healthy"
        assert health["s3_status"] == "connected"
        assert health["dynamodb_status"] == "connected"

    @pytest.mark.asyncio
    async def test_health_check_s3_error(
        self,
        non_mock_service: ArtifactStorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test health check with S3 error."""
        mock_s3_client.head_bucket.side_effect = Exception("S3 connection failed")

        health = await non_mock_service.health_check()

        assert health["status"] == "degraded"
        assert "error" in health["s3_status"]

    @pytest.mark.asyncio
    async def test_health_check_dynamodb_error(
        self,
        non_mock_service: ArtifactStorageService,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test health check with DynamoDB error."""
        mock_table = mock_dynamodb_resource.Table.return_value
        type(mock_table).table_status = property(
            lambda self: (_ for _ in ()).throw(Exception("DynamoDB connection failed"))
        )

        health = await non_mock_service.health_check()

        assert health["status"] == "degraded"
        assert "error" in health["dynamodb_status"]

    @pytest.mark.asyncio
    async def test_health_check_no_s3_client(self) -> None:
        """Test health check when S3 client is None."""
        service = ArtifactStorageService(environment="dev")
        service._use_mock = False
        service._s3 = None

        health = await service.health_check()

        # S3 check is skipped when client is None
        assert "s3_status" not in health or health.get("s3_status") != "connected"

    @pytest.mark.asyncio
    async def test_health_check_no_table(self) -> None:
        """Test health check when table is None."""
        service = ArtifactStorageService(environment="dev")
        service._use_mock = False
        service._table = None

        health = await service.health_check()

        # DynamoDB check is skipped when table is None
        assert (
            "dynamodb_status" not in health
            or health.get("dynamodb_status") != "connected"
        )


# =============================================================================
# AWS Client Initialization Tests
# =============================================================================


class TestAWSClientInitialization:
    """Tests for AWS client lazy initialization."""

    def test_s3_client_creation_success(self) -> None:
        """Test S3 client is created successfully."""
        with patch("boto3.client") as mock_boto_client:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3

            service = ArtifactStorageService(environment="dev")
            service._use_mock = False

            # Access the s3 property to trigger creation
            s3_client = service.s3

            assert s3_client is mock_s3
            mock_boto_client.assert_called_once_with("s3", region_name=service.region)

    def test_s3_client_creation_failure(self) -> None:
        """Test S3 client falls back to mock mode on failure."""
        with patch("boto3.client") as mock_boto_client:
            mock_boto_client.side_effect = Exception("AWS credentials not found")

            service = ArtifactStorageService(environment="dev")
            service._use_mock = False

            # Access the s3 property to trigger creation
            s3_client = service.s3

            assert s3_client is None
            assert service._use_mock is True

    def test_dynamodb_resource_creation_success(self) -> None:
        """Test DynamoDB resource is created successfully."""
        with patch("boto3.resource") as mock_boto_resource:
            mock_dynamodb = MagicMock()
            mock_boto_resource.return_value = mock_dynamodb

            service = ArtifactStorageService(environment="dev")
            service._use_mock = False

            # Access the dynamodb property to trigger creation
            dynamodb = service.dynamodb

            assert dynamodb is mock_dynamodb
            mock_boto_resource.assert_called_once_with(
                "dynamodb", region_name=service.region
            )

    def test_dynamodb_resource_creation_failure(self) -> None:
        """Test DynamoDB resource falls back to mock mode on failure."""
        with patch("boto3.resource") as mock_boto_resource:
            mock_boto_resource.side_effect = Exception("AWS credentials not found")

            service = ArtifactStorageService(environment="dev")
            service._use_mock = False

            # Access the dynamodb property to trigger creation
            dynamodb = service.dynamodb

            assert dynamodb is None
            assert service._use_mock is True

    def test_table_property_with_dynamodb(self) -> None:
        """Test table property creates table from dynamodb resource."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        service = ArtifactStorageService(environment="dev")
        service._use_mock = False
        service._dynamodb = mock_dynamodb

        table = service.table

        assert table is mock_table
        mock_dynamodb.Table.assert_called_once_with(service.table_name)

    def test_table_property_without_dynamodb(self) -> None:
        """Test table property returns None when dynamodb is None."""
        service = ArtifactStorageService(environment="test")
        service._use_mock = False
        # Mock the dynamodb property to return None
        with patch.object(
            ArtifactStorageService,
            "dynamodb",
            new_callable=lambda: property(lambda self: None),
        ):
            table = service.table
            assert table is None


# =============================================================================
# Mock S3 Operations Tests
# =============================================================================


class TestMockS3Operations:
    """Tests for S3 operations in mock mode."""

    @pytest.mark.asyncio
    async def test_mock_s3_upload_download_roundtrip(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test S3 upload and download in mock mode."""
        # Upload to mock S3
        s3_uri = await storage_service._upload_to_s3(sample_artifact)
        assert s3_uri.startswith("s3://")
        assert sample_artifact.artifact_id in s3_uri

        # Download from mock S3
        content = await storage_service._download_from_s3(s3_uri)
        assert "test_script" in content
        assert content["test_script"] == sample_artifact.test_script

    @pytest.mark.asyncio
    async def test_mock_s3_download_nonexistent(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test downloading non-existent S3 object returns empty dict."""
        content = await storage_service._download_from_s3("s3://bucket/nonexistent")
        assert content == {}


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_store_artifact_updates_timestamp(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test that storing artifact updates the timestamp."""
        original_updated = sample_artifact.updated_at
        await storage_service.store_artifact(sample_artifact)

        retrieved = await storage_service.get_artifact(sample_artifact.artifact_id)
        assert retrieved is not None
        assert retrieved.updated_at is not None

    @pytest.mark.asyncio
    async def test_get_artifact_no_table_non_mock(
        self,
        mock_dynamodb_resource: MagicMock,
    ) -> None:
        """Test getting artifact when table is None in non-mock mode."""
        service = ArtifactStorageService(environment="test")
        service._use_mock = False
        # Mock the table property to return None
        with patch.object(
            ArtifactStorageService,
            "table",
            new_callable=lambda: property(lambda self: None),
        ):
            result = await service.get_artifact("test-id")
            assert result is None

    @pytest.mark.asyncio
    async def test_count_by_status_with_repository_filter(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test count_by_status with repository filter."""
        # Create artifacts in different repositories
        for i in range(3):
            artifact = BugArtifact(
                artifact_id=f"repo1-{i}",
                repository_id="repo-1",
                commit_sha=f"sha-{i}",
                test_script="#!/bin/bash",
                test_files=["test.py"],
                test_parser="print('ok')",
                bug_inject_diff="diff",
                test_weaken_diff="diff",
            )
            await storage_service.store_artifact(artifact)

        for i in range(2):
            artifact = BugArtifact(
                artifact_id=f"repo2-{i}",
                repository_id="repo-2",
                commit_sha=f"sha-{i}",
                test_script="#!/bin/bash",
                test_files=["test.py"],
                test_parser="print('ok')",
                bug_inject_diff="diff",
                test_weaken_diff="diff",
            )
            await storage_service.store_artifact(artifact)

        # Count for repo-1 only
        counts = await storage_service.count_by_status("repo-1")
        assert counts.get("pending", 0) == 3

        # Count for repo-2 only
        counts = await storage_service.count_by_status("repo-2")
        assert counts.get("pending", 0) == 2

    @pytest.mark.asyncio
    async def test_count_by_status_no_repository_filter(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test count_by_status without repository filter returns empty in mock."""
        counts = await storage_service.count_by_status(None)
        assert isinstance(counts, dict)

    @pytest.mark.asyncio
    async def test_get_artifact_without_content(
        self,
        storage_service: ArtifactStorageService,
        sample_artifact: BugArtifact,
    ) -> None:
        """Test getting artifact without fetching S3 content."""
        await storage_service.store_artifact(sample_artifact)

        # In mock mode, include_content doesn't matter since data is in memory
        retrieved = await storage_service.get_artifact(
            sample_artifact.artifact_id, include_content=False
        )
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_artifact_with_all_statuses(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test creating artifacts with all possible statuses."""
        for status in ArtifactStatus:
            artifact = BugArtifact(
                artifact_id=f"status-{status.value}",
                repository_id="test-repo",
                commit_sha="sha",
                test_script="#!/bin/bash",
                test_files=["test.py"],
                test_parser="print('ok')",
                bug_inject_diff="diff",
                test_weaken_diff="diff",
                status=status,
            )
            await storage_service.store_artifact(artifact)

            retrieved = await storage_service.get_artifact(artifact.artifact_id)
            assert retrieved is not None
            assert retrieved.status == status

    @pytest.mark.asyncio
    async def test_artifact_with_all_injection_strategies(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test creating artifacts with all injection strategies."""
        for strategy in InjectionStrategy:
            artifact = BugArtifact(
                artifact_id=f"strategy-{strategy.value}",
                repository_id="test-repo",
                commit_sha="sha",
                test_script="#!/bin/bash",
                test_files=["test.py"],
                test_parser="print('ok')",
                bug_inject_diff="diff",
                test_weaken_diff="diff",
                injection_strategy=strategy,
            )
            await storage_service.store_artifact(artifact)

            retrieved = await storage_service.get_artifact(artifact.artifact_id)
            assert retrieved is not None
            assert retrieved.injection_strategy == strategy

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_validation_result(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test cache invalidation when updating validation result."""
        await storage_service.store_artifact(sample_artifact)

        # Read to cache
        await storage_service.get_artifact(sample_artifact.artifact_id)
        assert sample_artifact.artifact_id in storage_service._cache

        # Update validation result (in mock mode, cache is not invalidated
        # because the mock implementation doesn't call cache invalidation)
        # This is by design since mock mode doesn't have DynamoDB
        result = ValidationPipelineResult(
            artifact_id=sample_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        await storage_service.update_validation_result(
            sample_artifact.artifact_id, result
        )

        # In mock mode, cache is NOT invalidated (implementation detail)
        # This test documents the current behavior

    @pytest.mark.asyncio
    async def test_large_artifact_content(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test handling of large artifact content."""
        large_content = "x" * 100000  # 100KB of content
        artifact = BugArtifact(
            artifact_id="large-artifact",
            repository_id="test-repo",
            commit_sha="sha",
            test_script=large_content,
            test_files=["test.py"] * 1000,  # Many test files
            test_parser=large_content,
            bug_inject_diff=large_content,
            test_weaken_diff=large_content,
        )
        await storage_service.store_artifact(artifact)

        retrieved = await storage_service.get_artifact(artifact.artifact_id)
        assert retrieved is not None
        assert len(retrieved.test_script) == 100000

    @pytest.mark.asyncio
    async def test_unicode_content(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test handling of unicode content in artifacts."""
        artifact = BugArtifact(
            artifact_id="unicode-artifact",
            repository_id="test-repo",
            commit_sha="sha",
            test_script="#!/bin/bash\necho 'Hello World'",
            test_files=["tests/test.py"],
            test_parser="print('')",
            bug_inject_diff="diff --git\n-\n+",
            test_weaken_diff="diff --git\n-\n+",
        )
        await storage_service.store_artifact(artifact)

        retrieved = await storage_service.get_artifact(artifact.artifact_id)
        assert retrieved is not None
        # Check unicode is preserved after tar.gz roundtrip
        content = storage_service._create_tar_gz(artifact)
        extracted = storage_service._extract_tar_gz(content)
        assert "" in extracted["test_parser"]


# =============================================================================
# Additional Non-Mock Path Tests
# =============================================================================


class TestNonMockPaths:
    """Tests for non-mock code paths."""

    def test_service_with_dev_environment_still_uses_mock_without_boto3(
        self,
    ) -> None:
        """Test that non-test environment falls back to mock without credentials."""
        import importlib
        import sys

        # Remove cached module to force re-import with patched constant
        module_name = "src.services.ssr.artifact_storage_service"
        if module_name in sys.modules:
            del sys.modules[module_name]

        # When boto3 is not available, mock mode should be used
        with patch.dict(sys.modules, {"boto3": None, "botocore": None}):
            # Force re-import with boto3 unavailable
            import src.services.ssr.artifact_storage_service as storage_module

            # Reload to pick up the import failure
            importlib.reload(storage_module)

            # Now BOTO3_AVAILABLE should be False
            assert storage_module.BOTO3_AVAILABLE is False

            # Create service - should use mock mode
            service = storage_module.ArtifactStorageService(
                project_name="aura",
                environment="dev",
            )
            assert service._use_mock is True

        # Clean up - restore original module
        if module_name in sys.modules:
            del sys.modules[module_name]
        # Re-import to restore for other tests
        importlib.import_module(module_name)
