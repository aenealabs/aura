"""
Tests for SSR Validation Pipeline

Tests the 7-stage consistency validation pipeline for the
Self-Play SWE-RL bug artifact infrastructure (ADR-050 Phase 1).

Author: Project Aura Team
Created: 2026-01-01
"""

import pytest

from src.services.ssr.bug_artifact import ArtifactStatus, BugArtifact, ValidationResult
from src.services.ssr.validation_pipeline import (
    SandboxExecutionResult,
    ValidationPipeline,
    create_validation_pipeline,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def pipeline() -> ValidationPipeline:
    """Create a validation pipeline in mock mode."""
    return ValidationPipeline(
        project_name="aura",
        environment="test",
        min_passing_tests=1,
        min_changed_files=1,
        min_failing_tests=1,
        use_mock_sandbox=True,
    )


@pytest.fixture
def valid_artifact() -> BugArtifact:
    """Create a valid bug artifact for testing."""
    return BugArtifact(
        artifact_id=BugArtifact.generate_id(),
        repository_id="test-repo",
        commit_sha="abc123",
        test_script="#!/bin/bash\npytest tests/",
        test_files=["tests/test_foo.py", "tests/test_bar.py"],
        test_parser="""
import sys
import json

def parse(log):
    results = {}
    for line in log.split('\\n'):
        if 'PASSED' in line:
            test = line.split()[0]
            results[test] = 'pass'
        elif 'FAILED' in line:
            test = line.split()[0]
            results[test] = 'fail'
    return results

if __name__ == '__main__':
    log = sys.stdin.read()
    print(json.dumps(parse(log)))
""",
        bug_inject_diff="""
diff --git a/src/foo.py b/src/foo.py
--- a/src/foo.py
+++ b/src/foo.py
@@ -10,7 +10,7 @@ def calculate(x):
-    return x * 2
+    return x * 3

diff --git a/src/bar.py b/src/bar.py
--- a/src/bar.py
+++ b/src/bar.py
@@ -5,7 +5,7 @@ def process(data):
-    return data.strip()
+    return data
""",
        test_weaken_diff="""
diff --git a/tests/test_foo.py b/tests/test_foo.py
--- a/tests/test_foo.py
+++ b/tests/test_foo.py
@@ -5,7 +5,7 @@ def test_calculate():
-    assert calculate(5) == 10
+    pass  # Weakened
""",
    )


@pytest.fixture
def invalid_artifact_empty_test_files() -> BugArtifact:
    """Create artifact with empty test files."""
    return BugArtifact(
        artifact_id=BugArtifact.generate_id(),
        repository_id="test-repo",
        commit_sha="abc123",
        test_script="#!/bin/bash",
        test_files=[],  # Empty
        test_parser="print('ok')",
        bug_inject_diff="diff",
        test_weaken_diff="diff",
    )


@pytest.fixture
def invalid_artifact_no_parser() -> BugArtifact:
    """Create artifact with empty parser."""
    return BugArtifact(
        artifact_id=BugArtifact.generate_id(),
        repository_id="test-repo",
        commit_sha="abc123",
        test_script="#!/bin/bash",
        test_files=["test.py"],
        test_parser="",  # Empty
        bug_inject_diff="diff",
        test_weaken_diff="diff",
    )


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateValidationPipeline:
    """Tests for create_validation_pipeline factory."""

    def test_create_default(self) -> None:
        """Test creating pipeline with defaults."""
        pipeline = create_validation_pipeline()
        assert pipeline.project_name == "aura"
        assert pipeline.min_passing_tests == 1

    def test_create_with_mock(self) -> None:
        """Test creating pipeline with mock mode."""
        pipeline = create_validation_pipeline(use_mock=True)
        assert pipeline.use_mock_sandbox is True


# =============================================================================
# Stage 1 Tests: Test Files Existence
# =============================================================================


class TestStage1TestFilesExistence:
    """Tests for Stage 1: Test Files Existence validation."""

    @pytest.mark.asyncio
    async def test_valid_test_files(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test with valid test files."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        result = ValidationPipelineResult(
            artifact_id=valid_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage1_test_files_existence(
            valid_artifact, result
        )
        assert stage_result.result == ValidationResult.PASS
        assert stage_result.details["test_files_count"] == 2

    @pytest.mark.asyncio
    async def test_empty_test_files(
        self,
        pipeline: ValidationPipeline,
        invalid_artifact_empty_test_files: BugArtifact,
    ) -> None:
        """Test with empty test files list."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        result = ValidationPipelineResult(
            artifact_id=invalid_artifact_empty_test_files.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage1_test_files_existence(
            invalid_artifact_empty_test_files, result
        )
        assert stage_result.result == ValidationResult.FAIL
        assert "empty" in stage_result.error_message.lower()

    @pytest.mark.asyncio
    async def test_path_traversal_detection(self, pipeline: ValidationPipeline) -> None:
        """Test detection of path traversal in test files."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        artifact = BugArtifact(
            artifact_id=BugArtifact.generate_id(),
            repository_id="test-repo",
            commit_sha="abc123",
            test_script="#!/bin/bash",
            test_files=["tests/test.py", "../../../etc/passwd"],  # Path traversal
            test_parser="print('ok')",
            bug_inject_diff="diff",
            test_weaken_diff="diff",
        )
        result = ValidationPipelineResult(
            artifact_id=artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage1_test_files_existence(artifact, result)
        assert stage_result.result == ValidationResult.FAIL
        assert "traversal" in stage_result.error_message.lower()


# =============================================================================
# Stage 2 Tests: Test Parser Validity
# =============================================================================


class TestStage2TestParserValidity:
    """Tests for Stage 2: Test Parser Validity."""

    @pytest.mark.asyncio
    async def test_valid_parser(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test with valid parser."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        result = ValidationPipelineResult(
            artifact_id=valid_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage2_test_parser_validity(
            valid_artifact, result
        )
        assert stage_result.result == ValidationResult.PASS

    @pytest.mark.asyncio
    async def test_empty_parser(
        self,
        pipeline: ValidationPipeline,
        invalid_artifact_no_parser: BugArtifact,
    ) -> None:
        """Test with empty parser."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        result = ValidationPipelineResult(
            artifact_id=invalid_artifact_no_parser.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage2_test_parser_validity(
            invalid_artifact_no_parser, result
        )
        assert stage_result.result == ValidationResult.FAIL
        assert "empty" in stage_result.error_message.lower()

    @pytest.mark.asyncio
    async def test_invalid_syntax(self, pipeline: ValidationPipeline) -> None:
        """Test with invalid Python syntax."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        artifact = BugArtifact(
            artifact_id=BugArtifact.generate_id(),
            repository_id="test-repo",
            commit_sha="abc123",
            test_script="#!/bin/bash",
            test_files=["test.py"],
            test_parser="def parse(\n  # Invalid syntax",
            bug_inject_diff="diff",
            test_weaken_diff="diff",
        )
        result = ValidationPipelineResult(
            artifact_id=artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage2_test_parser_validity(artifact, result)
        assert stage_result.result == ValidationResult.FAIL
        assert "syntax" in stage_result.error_message.lower()

    @pytest.mark.asyncio
    async def test_missing_parse_function(self, pipeline: ValidationPipeline) -> None:
        """Test parser missing required function."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        artifact = BugArtifact(
            artifact_id=BugArtifact.generate_id(),
            repository_id="test-repo",
            commit_sha="abc123",
            test_script="#!/bin/bash",
            test_files=["test.py"],
            test_parser="x = 1\ny = 2\nprint(x + y)",  # No parse function
            bug_inject_diff="diff",
            test_weaken_diff="diff",
        )
        result = ValidationPipelineResult(
            artifact_id=artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage2_test_parser_validity(artifact, result)
        assert stage_result.result == ValidationResult.FAIL
        assert "function" in stage_result.error_message.lower()


# =============================================================================
# Stage 3 Tests: Test Script Validity
# =============================================================================


class TestStage3TestScriptValidity:
    """Tests for Stage 3: Test Script Validity."""

    @pytest.mark.asyncio
    async def test_valid_script(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test with valid script."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        result = ValidationPipelineResult(
            artifact_id=valid_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage3_test_script_validity(
            valid_artifact, result
        )
        assert stage_result.result == ValidationResult.PASS

    @pytest.mark.asyncio
    async def test_empty_script(self, pipeline: ValidationPipeline) -> None:
        """Test with empty script."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        artifact = BugArtifact(
            artifact_id=BugArtifact.generate_id(),
            repository_id="test-repo",
            commit_sha="abc123",
            test_script="",  # Empty
            test_files=["test.py"],
            test_parser="def parse(): pass",
            bug_inject_diff="diff",
            test_weaken_diff="diff",
        )
        result = ValidationPipelineResult(
            artifact_id=artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage3_test_script_validity(artifact, result)
        assert stage_result.result == ValidationResult.FAIL

    @pytest.mark.asyncio
    async def test_insufficient_passing_tests(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test with insufficient passing tests."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        # Set mock result with 0 passing tests
        pipeline.set_mock_result(
            valid_artifact.artifact_id,
            3,
            SandboxExecutionResult(
                success=True,
                exit_code=0,
                stdout="0 passed",
                stderr="",
                duration_seconds=1.0,
                test_results={"passed": 0, "failed": 0},
            ),
        )

        result = ValidationPipelineResult(
            artifact_id=valid_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage3_test_script_validity(
            valid_artifact, result
        )
        assert stage_result.result == ValidationResult.FAIL
        assert "insufficient" in stage_result.error_message.lower()


# =============================================================================
# Stage 4 Tests: Bug Scope Validation
# =============================================================================


class TestStage4BugScopeValidation:
    """Tests for Stage 4: Bug Scope Validation."""

    @pytest.mark.asyncio
    async def test_valid_scope(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test with valid scope (2 files changed)."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        result = ValidationPipelineResult(
            artifact_id=valid_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage4_bug_scope_validation(
            valid_artifact, result
        )
        assert stage_result.result == ValidationResult.PASS
        assert stage_result.details["changed_files"] >= 1

    @pytest.mark.asyncio
    async def test_empty_diff(self, pipeline: ValidationPipeline) -> None:
        """Test with empty diff."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        artifact = BugArtifact(
            artifact_id=BugArtifact.generate_id(),
            repository_id="test-repo",
            commit_sha="abc123",
            test_script="#!/bin/bash",
            test_files=["test.py"],
            test_parser="def parse(): pass",
            bug_inject_diff="",  # Empty
            test_weaken_diff="diff",
        )
        result = ValidationPipelineResult(
            artifact_id=artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage4_bug_scope_validation(artifact, result)
        assert stage_result.result == ValidationResult.FAIL

    @pytest.mark.asyncio
    async def test_insufficient_files(self, pipeline: ValidationPipeline) -> None:
        """Test with insufficient changed files."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        # Create pipeline with min_changed_files=3
        strict_pipeline = ValidationPipeline(
            min_changed_files=3,
            use_mock_sandbox=True,
        )

        artifact = BugArtifact(
            artifact_id=BugArtifact.generate_id(),
            repository_id="test-repo",
            commit_sha="abc123",
            test_script="#!/bin/bash",
            test_files=["test.py"],
            test_parser="def parse(): pass",
            bug_inject_diff="diff --git a/foo.py b/foo.py\n-old\n+new",  # Only 1 file
            test_weaken_diff="diff",
        )
        result = ValidationPipelineResult(
            artifact_id=artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await strict_pipeline._stage4_bug_scope_validation(
            artifact, result
        )
        assert stage_result.result == ValidationResult.FAIL
        assert "insufficient" in stage_result.error_message.lower()


# =============================================================================
# Stage 5 Tests: Bug Validity
# =============================================================================


class TestStage5BugValidity:
    """Tests for Stage 5: Bug Validity."""

    @pytest.mark.asyncio
    async def test_bug_breaks_tests(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test that bug breaks tests."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        result = ValidationPipelineResult(
            artifact_id=valid_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage5_bug_validity(valid_artifact, result)
        assert stage_result.result == ValidationResult.PASS

    @pytest.mark.asyncio
    async def test_bug_doesnt_break_tests(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test failure when bug doesn't break tests."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        # Set mock result with no failing tests
        pipeline.set_mock_result(
            valid_artifact.artifact_id,
            5,
            SandboxExecutionResult(
                success=True,
                exit_code=0,
                stdout="10 passed",
                stderr="",
                duration_seconds=1.0,
                test_results={"passed": 10, "failed": 0},  # No failures
            ),
        )

        result = ValidationPipelineResult(
            artifact_id=valid_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage5_bug_validity(valid_artifact, result)
        assert stage_result.result == ValidationResult.FAIL


# =============================================================================
# Stage 6 Tests: Test Weakening Validity
# =============================================================================


class TestStage6TestWeakeningValidity:
    """Tests for Stage 6: Test Weakening Validity."""

    @pytest.mark.asyncio
    async def test_weakening_fixes_tests(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test that weakening makes tests pass."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        result = ValidationPipelineResult(
            artifact_id=valid_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage6_test_weakening_validity(
            valid_artifact, result
        )
        assert stage_result.result == ValidationResult.PASS

    @pytest.mark.asyncio
    async def test_empty_weakening_diff(self, pipeline: ValidationPipeline) -> None:
        """Test with empty weakening diff."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        artifact = BugArtifact(
            artifact_id=BugArtifact.generate_id(),
            repository_id="test-repo",
            commit_sha="abc123",
            test_script="#!/bin/bash",
            test_files=["test.py"],
            test_parser="def parse(): pass",
            bug_inject_diff="diff",
            test_weaken_diff="",  # Empty
        )
        result = ValidationPipelineResult(
            artifact_id=artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage6_test_weakening_validity(artifact, result)
        assert stage_result.result == ValidationResult.FAIL

    @pytest.mark.asyncio
    async def test_weakening_doesnt_fix_tests(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test failure when weakening doesn't fix tests."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        # Set mock result with still failing tests
        pipeline.set_mock_result(
            valid_artifact.artifact_id,
            6,
            SandboxExecutionResult(
                success=False,
                exit_code=1,
                stdout="5 passed, 2 failed",
                stderr="",
                duration_seconds=1.0,
                test_results={"passed": 5, "failed": 2},  # Still failing
            ),
        )

        result = ValidationPipelineResult(
            artifact_id=valid_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage6_test_weakening_validity(
            valid_artifact, result
        )
        assert stage_result.result == ValidationResult.FAIL


# =============================================================================
# Stage 7 Tests: Inverse Mutation Testing
# =============================================================================


class TestStage7InverseMutationTesting:
    """Tests for Stage 7: Inverse Mutation Testing."""

    @pytest.mark.asyncio
    async def test_all_files_contribute(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test that all files contribute to bug."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        result = ValidationPipelineResult(
            artifact_id=valid_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage7_inverse_mutation(valid_artifact, result)
        assert stage_result.result == ValidationResult.PASS

    @pytest.mark.asyncio
    async def test_not_all_files_contribute(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test failure when not all files contribute."""
        from src.services.ssr.validation_pipeline import ValidationPipelineResult

        # Set mock result indicating not all files contribute
        pipeline.set_mock_result(
            valid_artifact.artifact_id,
            7,
            SandboxExecutionResult(
                success=False,
                exit_code=1,
                stdout="",
                stderr="File bar.py doesn't affect tests",
                duration_seconds=1.0,
            ),
        )

        result = ValidationPipelineResult(
            artifact_id=valid_artifact.artifact_id,
            overall_result=ValidationResult.PASS,
        )
        stage_result = await pipeline._stage7_inverse_mutation(valid_artifact, result)
        assert stage_result.result == ValidationResult.FAIL


# =============================================================================
# Full Pipeline Tests
# =============================================================================


class TestFullPipeline:
    """Tests for full pipeline execution."""

    @pytest.mark.asyncio
    async def test_full_pipeline_success(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test full pipeline with valid artifact."""
        result = await pipeline.validate(valid_artifact)
        assert result.overall_result == ValidationResult.PASS
        assert len(result.stages) == 7
        assert valid_artifact.status == ArtifactStatus.VALID

    @pytest.mark.asyncio
    async def test_full_pipeline_failure_stage1(
        self,
        pipeline: ValidationPipeline,
        invalid_artifact_empty_test_files: BugArtifact,
    ) -> None:
        """Test pipeline stops at stage 1 failure."""
        result = await pipeline.validate(invalid_artifact_empty_test_files)
        assert result.overall_result == ValidationResult.FAIL
        assert len(result.stages) == 1  # Stops at first failure
        assert invalid_artifact_empty_test_files.status == ArtifactStatus.INVALID

    @pytest.mark.asyncio
    async def test_pipeline_updates_artifact_status(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test that pipeline updates artifact status."""
        assert valid_artifact.status == ArtifactStatus.PENDING

        result = await pipeline.validate(valid_artifact)

        if result.overall_result == ValidationResult.PASS:
            assert valid_artifact.status == ArtifactStatus.VALID
        else:
            assert valid_artifact.status in [
                ArtifactStatus.INVALID,
                ArtifactStatus.FAILED,
            ]

    @pytest.mark.asyncio
    async def test_pipeline_stores_validation_results(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test that pipeline stores results in artifact."""
        await pipeline.validate(valid_artifact)

        assert valid_artifact.validation_results != {}
        assert "artifact_id" in valid_artifact.validation_results
        assert "stages" in valid_artifact.validation_results


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Tests for pipeline helper methods."""

    def test_count_changed_files(self, pipeline: ValidationPipeline) -> None:
        """Test counting changed files in diff."""
        diff = """
diff --git a/src/foo.py b/src/foo.py
--- a/src/foo.py
+++ b/src/foo.py
@@ -1 +1 @@
-old
+new

diff --git a/src/bar.py b/src/bar.py
--- a/src/bar.py
+++ b/src/bar.py
@@ -1 +1 @@
-old
+new

diff --git a/src/baz.py b/src/baz.py
--- a/src/baz.py
+++ b/src/baz.py
@@ -1 +1 @@
-old
+new
"""
        count = pipeline._count_changed_files(diff)
        assert count == 3

    def test_get_changed_files(self, pipeline: ValidationPipeline) -> None:
        """Test getting list of changed files."""
        diff = """
diff --git a/src/foo.py b/src/foo.py
--- a/src/foo.py
+++ b/src/foo.py

diff --git a/src/bar.py b/src/bar.py
--- a/src/bar.py
+++ b/src/bar.py
"""
        files = pipeline._get_changed_files(diff)
        assert files == ["src/foo.py", "src/bar.py"]

    def test_set_and_clear_mock_results(
        self, pipeline: ValidationPipeline, valid_artifact: BugArtifact
    ) -> None:
        """Test setting and clearing mock results."""
        pipeline.set_mock_result(
            valid_artifact.artifact_id,
            3,
            SandboxExecutionResult(
                success=True,
                exit_code=0,
                stdout="ok",
                stderr="",
                duration_seconds=0.5,
            ),
        )
        assert len(pipeline._mock_test_results) == 1

        pipeline.clear_mock_results()
        assert len(pipeline._mock_test_results) == 0
