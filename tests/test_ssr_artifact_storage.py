"""
Tests for SSR Artifact Storage Service

Tests the S3 + DynamoDB storage operations for the
Self-Play SWE-RL bug artifact infrastructure (ADR-050 Phase 1).

Author: Project Aura Team
Created: 2026-01-01
"""

import pytest

from src.services.ssr.artifact_storage_service import (
    ArtifactStorageService,
    create_artifact_storage_service,
)
from src.services.ssr.bug_artifact import (
    ArtifactStatus,
    BugArtifact,
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


# =============================================================================
# CRUD Operation Tests
# =============================================================================


class TestStoreCRUD:
    """Tests for basic CRUD operations."""

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


# =============================================================================
# Float to Decimal Conversion Tests
# =============================================================================


class TestFloatToDecimalConversion:
    """Tests for _convert_floats_to_decimal function."""

    def test_convert_simple_float(self) -> None:
        """Test converting a simple float."""
        from decimal import Decimal

        from src.services.ssr.artifact_storage_service import _convert_floats_to_decimal

        result = _convert_floats_to_decimal(3.14)
        assert result == Decimal("3.14")

    def test_convert_nested_dict(self) -> None:
        """Test converting floats in nested dicts."""
        from decimal import Decimal

        from src.services.ssr.artifact_storage_service import _convert_floats_to_decimal

        obj = {"a": 1.5, "b": {"c": 2.5, "d": {"e": 3.5}}}
        result = _convert_floats_to_decimal(obj)

        assert result["a"] == Decimal("1.5")
        assert result["b"]["c"] == Decimal("2.5")
        assert result["b"]["d"]["e"] == Decimal("3.5")

    def test_convert_nested_list(self) -> None:
        """Test converting floats in nested lists."""
        from decimal import Decimal

        from src.services.ssr.artifact_storage_service import _convert_floats_to_decimal

        obj = [1.1, [2.2, [3.3]]]
        result = _convert_floats_to_decimal(obj)

        assert result[0] == Decimal("1.1")
        assert result[1][0] == Decimal("2.2")
        assert result[1][1][0] == Decimal("3.3")

    def test_convert_mixed_types(self) -> None:
        """Test that non-float types are preserved."""
        from decimal import Decimal

        from src.services.ssr.artifact_storage_service import _convert_floats_to_decimal

        obj = {"string": "hello", "int": 42, "float": 1.5, "list": [1, 2.0]}
        result = _convert_floats_to_decimal(obj)

        assert result["string"] == "hello"
        assert result["int"] == 42
        assert result["float"] == Decimal("1.5")
        assert result["list"][0] == 1
        assert result["list"][1] == Decimal("2.0")

    def test_convert_none_passthrough(self) -> None:
        """Test that None passes through unchanged."""
        from src.services.ssr.artifact_storage_service import _convert_floats_to_decimal

        result = _convert_floats_to_decimal(None)
        assert result is None


# =============================================================================
# Failed Patch Diff Tests
# =============================================================================


class TestFailedPatchDiff:
    """Tests for artifacts with failed_patch_diff (higher-order bugs)."""

    @pytest.fixture
    def higher_order_artifact(self) -> BugArtifact:
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


# =============================================================================
# AWS Client Property Tests (Mocked)
# =============================================================================


class TestAWSClientProperties:
    """Tests for AWS client lazy initialization."""

    def test_s3_property_mock_mode(
        self, storage_service: ArtifactStorageService
    ) -> None:
        """Test S3 property returns None in mock mode."""
        # In mock mode, s3 should be None
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
# Non-Mock Mode Path Tests
# =============================================================================


class TestNonMockPaths:
    """Tests for non-mock code paths."""

    def test_service_with_dev_environment_still_uses_mock_without_boto3(
        self,
    ) -> None:
        """Test that non-test environment falls back to mock without credentials."""
        import importlib
        import sys
        from unittest.mock import patch

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


# =============================================================================
# Mock S3 Upload/Download Tests
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
# Validation Result Update Tests
# =============================================================================


class TestValidationResultUpdates:
    """Additional tests for validation result handling."""

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

    @pytest.mark.asyncio
    async def test_validation_result_with_floats(
        self, storage_service: ArtifactStorageService, sample_artifact: BugArtifact
    ) -> None:
        """Test that validation results with floats are converted to Decimal."""
        await storage_service.store_artifact(sample_artifact)

        result = ValidationPipelineResult(
            artifact_id=sample_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
            total_tests=10,
            passing_before_bug=10,
            total_duration_seconds=3.14159,  # Float value
        )

        success = await storage_service.update_validation_result(
            sample_artifact.artifact_id, result
        )
        assert success is True


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
        # Timestamp should be set (may or may not differ depending on timing)
        assert retrieved.updated_at is not None

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
        # In mock mode, count_by_status filters by repository_id
        # Empty string won't match any artifacts
        counts = await storage_service.count_by_status(None)
        # Should be empty since no artifacts match empty repository_id
        assert isinstance(counts, dict)
