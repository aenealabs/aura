"""
Tests for SSR Bug Artifact Models

Tests the dataclasses, enums, and serialization for the
Self-Play SWE-RL bug artifact infrastructure (ADR-050 Phase 1).

Author: Project Aura Team
Created: 2026-01-01
"""

import pytest

from src.services.ssr.bug_artifact import (
    ArtifactStatus,
    BugArtifact,
    InjectionStrategy,
    StageResult,
    ValidationPipelineResult,
    ValidationResult,
    ValidationStage,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_artifact() -> BugArtifact:
    """Create a sample bug artifact for testing."""
    return BugArtifact(
        artifact_id="ssr-artifact-test123",
        repository_id="repo-456",
        commit_sha="abc123def456",
        test_script="#!/bin/bash\npytest tests/",
        test_files=["tests/test_foo.py", "tests/test_bar.py"],
        test_parser='import sys\nprint(json.dumps({"test1": "pass"}))',
        bug_inject_diff="diff --git a/foo.py b/foo.py\n-old\n+new",
        test_weaken_diff="diff --git a/tests/test_foo.py b/tests/test_foo.py\n-assert True\n+pass",
    )


@pytest.fixture
def sample_stage_result() -> StageResult:
    """Create a sample stage result for testing."""
    return StageResult(
        stage=ValidationStage.TEST_FILES_EXISTENCE,
        result=ValidationResult.PASS,
        duration_seconds=1.5,
        details={"test_files_count": 5},
    )


@pytest.fixture
def sample_pipeline_result() -> ValidationPipelineResult:
    """Create a sample pipeline result for testing."""
    return ValidationPipelineResult(
        artifact_id="ssr-artifact-test123",
        overall_result=ValidationResult.PASS,
    )


# =============================================================================
# Enum Tests
# =============================================================================


class TestArtifactStatus:
    """Tests for ArtifactStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Verify all expected statuses are defined."""
        expected = ["PENDING", "VALIDATING", "VALID", "INVALID", "FAILED", "ARCHIVED"]
        for status in expected:
            assert hasattr(ArtifactStatus, status)

    def test_status_values(self) -> None:
        """Verify status values are lowercase strings."""
        assert ArtifactStatus.PENDING.value == "pending"
        assert ArtifactStatus.VALID.value == "valid"
        assert ArtifactStatus.INVALID.value == "invalid"

    def test_status_from_string(self) -> None:
        """Test creating status from string value."""
        status = ArtifactStatus("pending")
        assert status == ArtifactStatus.PENDING


class TestValidationStage:
    """Tests for ValidationStage enum."""

    def test_all_stages_exist(self) -> None:
        """Verify all 7 validation stages are defined."""
        expected = [
            "TEST_FILES_EXISTENCE",
            "TEST_PARSER_VALIDITY",
            "TEST_SCRIPT_VALIDITY",
            "BUG_SCOPE_VALIDATION",
            "BUG_VALIDITY",
            "TEST_WEAKENING_VALIDITY",
            "INVERSE_MUTATION_TESTING",
        ]
        for stage in expected:
            assert hasattr(ValidationStage, stage)

    def test_stage_count(self) -> None:
        """Verify exactly 7 stages."""
        assert len(ValidationStage) == 7


class TestValidationResult:
    """Tests for ValidationResult enum."""

    def test_all_results_exist(self) -> None:
        """Verify all expected results are defined."""
        expected = ["PASS", "FAIL", "SKIP", "ERROR"]
        for result in expected:
            assert hasattr(ValidationResult, result)


class TestInjectionStrategy:
    """Tests for InjectionStrategy enum."""

    def test_all_strategies_exist(self) -> None:
        """Verify all injection strategies are defined."""
        expected = [
            "REMOVAL_ONLY",
            "HISTORY_AWARE",
            "REMOVAL_PLUS_HISTORY",
            "DIRECT_INJECTION",
        ]
        for strategy in expected:
            assert hasattr(InjectionStrategy, strategy)


# =============================================================================
# BugArtifact Tests
# =============================================================================


class TestBugArtifact:
    """Tests for BugArtifact dataclass."""

    def test_create_artifact(self, sample_artifact: BugArtifact) -> None:
        """Test basic artifact creation."""
        assert sample_artifact.artifact_id == "ssr-artifact-test123"
        assert sample_artifact.repository_id == "repo-456"
        assert sample_artifact.status == ArtifactStatus.PENDING

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        artifact = BugArtifact(
            artifact_id="test-id",
            repository_id="repo-id",
            commit_sha="sha123",
            test_script="#!/bin/bash",
            test_files=["test.py"],
            test_parser="print('ok')",
            bug_inject_diff="diff",
            test_weaken_diff="diff",
        )
        assert artifact.status == ArtifactStatus.PENDING
        assert artifact.injection_strategy == InjectionStrategy.REMOVAL_ONLY
        assert artifact.order == 1
        assert artifact.min_passing_tests == 1
        assert artifact.metadata == {}

    def test_generate_id(self) -> None:
        """Test artifact ID generation."""
        id1 = BugArtifact.generate_id()
        id2 = BugArtifact.generate_id()
        assert id1.startswith("ssr-artifact-")
        assert id2.startswith("ssr-artifact-")
        assert id1 != id2
        assert len(id1) == len("ssr-artifact-") + 12

    def test_to_dict(self, sample_artifact: BugArtifact) -> None:
        """Test serialization to dictionary."""
        data = sample_artifact.to_dict()
        assert data["artifact_id"] == "ssr-artifact-test123"
        assert data["repository_id"] == "repo-456"
        assert data["status"] == "pending"
        assert data["test_files_count"] == 2
        assert "created_at" in data
        assert "updated_at" in data

    def test_to_dict_excludes_large_content(self, sample_artifact: BugArtifact) -> None:
        """Test that to_dict excludes large content fields."""
        data = sample_artifact.to_dict()
        assert "test_script" not in data
        assert "test_parser" not in data
        assert "bug_inject_diff" not in data
        assert "test_weaken_diff" not in data

    def test_from_dynamodb_item(self) -> None:
        """Test deserialization from DynamoDB item."""
        item = {
            "artifact_id": "test-id",
            "repository_id": "repo-id",
            "commit_sha": "sha123",
            "status": "valid",
            "injection_strategy": "history_aware",
            "order": 2,
            "parent_artifact_id": "parent-id",
            "min_passing_tests": 5,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T01:00:00+00:00",
        }
        content = {
            "test_script": "#!/bin/bash",
            "test_files": ["test.py"],
            "test_parser": "print('ok')",
            "bug_inject_diff": "diff",
            "test_weaken_diff": "diff",
        }

        artifact = BugArtifact.from_dynamodb_item(item, content)
        assert artifact.artifact_id == "test-id"
        assert artifact.status == ArtifactStatus.VALID
        assert artifact.injection_strategy == InjectionStrategy.HISTORY_AWARE
        assert artifact.order == 2
        assert artifact.parent_artifact_id == "parent-id"
        assert artifact.test_script == "#!/bin/bash"

    def test_from_dynamodb_item_without_content(self) -> None:
        """Test deserialization without S3 content."""
        item = {
            "artifact_id": "test-id",
            "repository_id": "repo-id",
            "status": "pending",
        }

        artifact = BugArtifact.from_dynamodb_item(item)
        assert artifact.artifact_id == "test-id"
        assert artifact.test_script == ""
        assert artifact.test_files == []

    def test_update_timestamp(self, sample_artifact: BugArtifact) -> None:
        """Test timestamp update."""
        old_updated = sample_artifact.updated_at
        sample_artifact.update_timestamp()
        assert sample_artifact.updated_at != old_updated

    def test_is_higher_order(self) -> None:
        """Test higher-order bug detection."""
        first_order = BugArtifact(
            artifact_id="first",
            repository_id="repo",
            commit_sha="sha",
            test_script="",
            test_files=[],
            test_parser="",
            bug_inject_diff="",
            test_weaken_diff="",
            order=1,
        )
        assert not first_order.is_higher_order()

        higher_order = BugArtifact(
            artifact_id="higher",
            repository_id="repo",
            commit_sha="sha",
            test_script="",
            test_files=[],
            test_parser="",
            bug_inject_diff="",
            test_weaken_diff="",
            order=2,
            parent_artifact_id="first",
        )
        assert higher_order.is_higher_order()


# =============================================================================
# StageResult Tests
# =============================================================================


class TestStageResult:
    """Tests for StageResult dataclass."""

    def test_create_stage_result(self, sample_stage_result: StageResult) -> None:
        """Test basic stage result creation."""
        assert sample_stage_result.stage == ValidationStage.TEST_FILES_EXISTENCE
        assert sample_stage_result.result == ValidationResult.PASS
        assert sample_stage_result.duration_seconds == 1.5

    def test_stage_result_with_error(self) -> None:
        """Test stage result with error."""
        result = StageResult(
            stage=ValidationStage.BUG_VALIDITY,
            result=ValidationResult.ERROR,
            error_message="Sandbox timeout",
        )
        assert result.result == ValidationResult.ERROR
        assert result.error_message == "Sandbox timeout"

    def test_to_dict(self, sample_stage_result: StageResult) -> None:
        """Test serialization to dictionary."""
        data = sample_stage_result.to_dict()
        assert data["stage"] == "test_files_existence"
        assert data["result"] == "pass"
        assert data["duration_seconds"] == 1.5
        assert data["details"] == {"test_files_count": 5}

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "stage": "bug_validity",
            "result": "fail",
            "duration_seconds": 2.5,
            "details": {"failing_tests": 3},
            "error_message": None,
            "executed_at": "2026-01-01T00:00:00+00:00",
        }
        result = StageResult.from_dict(data)
        assert result.stage == ValidationStage.BUG_VALIDITY
        assert result.result == ValidationResult.FAIL
        assert result.details["failing_tests"] == 3

    def test_is_success(self) -> None:
        """Test success check."""
        passing = StageResult(
            stage=ValidationStage.TEST_FILES_EXISTENCE,
            result=ValidationResult.PASS,
        )
        failing = StageResult(
            stage=ValidationStage.TEST_FILES_EXISTENCE,
            result=ValidationResult.FAIL,
        )
        assert passing.is_success()
        assert not failing.is_success()


# =============================================================================
# ValidationPipelineResult Tests
# =============================================================================


class TestValidationPipelineResult:
    """Tests for ValidationPipelineResult dataclass."""

    def test_create_pipeline_result(
        self, sample_pipeline_result: ValidationPipelineResult
    ) -> None:
        """Test basic pipeline result creation."""
        assert sample_pipeline_result.artifact_id == "ssr-artifact-test123"
        assert sample_pipeline_result.overall_result == ValidationResult.PASS
        assert sample_pipeline_result.stages == []

    def test_add_stage_result(
        self,
        sample_pipeline_result: ValidationPipelineResult,
        sample_stage_result: StageResult,
    ) -> None:
        """Test adding stage results."""
        sample_pipeline_result.add_stage_result(sample_stage_result)
        assert len(sample_pipeline_result.stages) == 1
        assert sample_pipeline_result.total_duration_seconds == 1.5

    def test_to_dict(self, sample_pipeline_result: ValidationPipelineResult) -> None:
        """Test serialization to dictionary."""
        data = sample_pipeline_result.to_dict()
        assert data["artifact_id"] == "ssr-artifact-test123"
        assert data["overall_result"] == "pass"
        assert data["stages"] == []

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "artifact_id": "test-id",
            "overall_result": "fail",
            "stages": [
                {
                    "stage": "test_files_existence",
                    "result": "pass",
                    "duration_seconds": 0.5,
                    "details": {},
                },
                {
                    "stage": "test_parser_validity",
                    "result": "fail",
                    "duration_seconds": 1.0,
                    "details": {},
                    "error_message": "Invalid syntax",
                },
            ],
            "total_duration_seconds": 1.5,
            "total_tests": 10,
        }
        result = ValidationPipelineResult.from_dict(data)
        assert result.artifact_id == "test-id"
        assert result.overall_result == ValidationResult.FAIL
        assert len(result.stages) == 2

    def test_is_valid(self) -> None:
        """Test validity check."""
        passing = ValidationPipelineResult(
            artifact_id="test",
            overall_result=ValidationResult.PASS,
        )
        failing = ValidationPipelineResult(
            artifact_id="test",
            overall_result=ValidationResult.FAIL,
        )
        assert passing.is_valid()
        assert not failing.is_valid()

    def test_get_failed_stages(self) -> None:
        """Test getting failed stages."""
        result = ValidationPipelineResult(
            artifact_id="test",
            overall_result=ValidationResult.FAIL,
        )
        result.add_stage_result(
            StageResult(
                stage=ValidationStage.TEST_FILES_EXISTENCE,
                result=ValidationResult.PASS,
            )
        )
        result.add_stage_result(
            StageResult(
                stage=ValidationStage.TEST_PARSER_VALIDITY,
                result=ValidationResult.FAIL,
            )
        )
        result.add_stage_result(
            StageResult(
                stage=ValidationStage.BUG_VALIDITY,
                result=ValidationResult.FAIL,
            )
        )

        failed = result.get_failed_stages()
        assert len(failed) == 2
        assert failed[0].stage == ValidationStage.TEST_PARSER_VALIDITY
        assert failed[1].stage == ValidationStage.BUG_VALIDITY

    def test_get_error_stages(self) -> None:
        """Test getting error stages."""
        result = ValidationPipelineResult(
            artifact_id="test",
            overall_result=ValidationResult.ERROR,
        )
        result.add_stage_result(
            StageResult(
                stage=ValidationStage.TEST_SCRIPT_VALIDITY,
                result=ValidationResult.ERROR,
                error_message="Timeout",
            )
        )

        errors = result.get_error_stages()
        assert len(errors) == 1
        assert errors[0].error_message == "Timeout"

    def test_complete(self) -> None:
        """Test completing pipeline."""
        result = ValidationPipelineResult(
            artifact_id="test",
            overall_result=ValidationResult.PASS,
        )
        assert result.completed_at is None

        result.complete(ValidationResult.FAIL)
        assert result.overall_result == ValidationResult.FAIL
        assert result.completed_at is not None
