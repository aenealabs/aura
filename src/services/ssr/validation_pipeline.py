"""
Project Aura - SSR Validation Pipeline

7-stage consistency validation pipeline for bug artifacts
in the Self-Play SWE-RL training pipeline per ADR-050.

Validation Stages:
1. Test Files Existence - Verify all test files exist
2. Test Parser Validity - Validate parser produces correct JSON
3. Test Script Validity - All tests pass on clean code
4. Bug Scope Validation - Sufficient files changed
5. Bug Validity - Tests fail after applying bug
6. Test Weakening Validity - Tests pass after weakening
7. Inverse Mutation Testing - Each file contributes to bug

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass, field

from src.services.ssr.bug_artifact import (
    ArtifactStatus,
    BugArtifact,
    StageResult,
    ValidationPipelineResult,
    ValidationResult,
    ValidationStage,
)

logger = logging.getLogger(__name__)


@dataclass
class SandboxExecutionResult:
    """Result of executing a command in sandbox."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    test_results: dict[str, str] = field(default_factory=dict)


class ValidationPipeline:
    """
    7-stage consistency validation pipeline for SSR bug artifacts.

    Each artifact must pass all 7 stages to be considered valid
    for use in the Self-Play SWE-RL training loop.

    Usage:
        pipeline = ValidationPipeline()
        result = await pipeline.validate(artifact)
        if result.is_valid():
            # Artifact is ready for training
            pass

    Stages:
        1. Test Files Existence - Verify test files referenced in artifact exist
        2. Test Parser Validity - Execute parser on sample, verify JSON output
        3. Test Script Validity - Run tests on clean code, all must pass
        4. Bug Scope Validation - Verify bug changes >= min_changed_files
        5. Bug Validity - Apply bug, verify tests fail
        6. Test Weakening Validity - Apply weakening, verify tests pass
        7. Inverse Mutation Testing - Verify each file contributes to failure
    """

    def __init__(
        self,
        project_name: str = "aura",
        environment: str | None = None,
        min_passing_tests: int = 1,
        min_changed_files: int = 1,
        min_failing_tests: int = 1,
        stage_timeout_seconds: int = 300,
        use_mock_sandbox: bool = False,
    ):
        """
        Initialize the validation pipeline.

        Args:
            project_name: Project name for resource naming
            environment: Environment (dev, qa, prod)
            min_passing_tests: Minimum tests that must pass on clean code
            min_changed_files: Minimum files changed by bug
            min_failing_tests: Minimum tests that must fail after bug
            stage_timeout_seconds: Timeout per stage (default 5 min)
            use_mock_sandbox: Use mock sandbox for testing
        """
        self.project_name = project_name
        self.environment = environment or os.environ.get("ENVIRONMENT", "dev")
        self.min_passing_tests = min_passing_tests
        self.min_changed_files = min_changed_files
        self.min_failing_tests = min_failing_tests
        self.stage_timeout_seconds = stage_timeout_seconds
        self.use_mock_sandbox = use_mock_sandbox

        # Mock sandbox results for testing
        self._mock_test_results: dict[str, SandboxExecutionResult] = {}

        logger.info(
            f"ValidationPipeline initialized: min_passing={min_passing_tests}, "
            f"min_changed={min_changed_files}, min_failing={min_failing_tests}"
        )

    # =========================================================================
    # Main Validation Entry Point
    # =========================================================================

    async def validate(self, artifact: BugArtifact) -> ValidationPipelineResult:
        """
        Execute the full 7-stage validation pipeline.

        Args:
            artifact: The bug artifact to validate

        Returns:
            Complete validation result with all stage results
        """
        result = ValidationPipelineResult(
            artifact_id=artifact.artifact_id,
            overall_result=ValidationResult.PASS,  # Optimistic start
        )

        # Update artifact status
        artifact.status = ArtifactStatus.VALIDATING
        artifact.update_timestamp()

        logger.info(f"Starting validation for artifact: {artifact.artifact_id}")

        # Execute each stage in order
        stages = [
            (ValidationStage.TEST_FILES_EXISTENCE, self._stage1_test_files_existence),
            (ValidationStage.TEST_PARSER_VALIDITY, self._stage2_test_parser_validity),
            (ValidationStage.TEST_SCRIPT_VALIDITY, self._stage3_test_script_validity),
            (ValidationStage.BUG_SCOPE_VALIDATION, self._stage4_bug_scope_validation),
            (ValidationStage.BUG_VALIDITY, self._stage5_bug_validity),
            (
                ValidationStage.TEST_WEAKENING_VALIDITY,
                self._stage6_test_weakening_validity,
            ),
            (ValidationStage.INVERSE_MUTATION_TESTING, self._stage7_inverse_mutation),
        ]

        for stage_enum, stage_func in stages:
            try:
                stage_result = await asyncio.wait_for(
                    stage_func(artifact, result),
                    timeout=self.stage_timeout_seconds,
                )
                result.add_stage_result(stage_result)

                # Update metrics from stage
                self._update_metrics_from_stage(result, stage_result)

                # Check if we should continue
                if stage_result.result == ValidationResult.FAIL:
                    logger.warning(
                        f"Stage {stage_enum.value} failed for {artifact.artifact_id}"
                    )
                    result.complete(ValidationResult.FAIL)
                    break
                elif stage_result.result == ValidationResult.ERROR:
                    logger.error(
                        f"Stage {stage_enum.value} errored for {artifact.artifact_id}"
                    )
                    result.complete(ValidationResult.ERROR)
                    break

            except asyncio.TimeoutError:
                stage_result = StageResult(
                    stage=stage_enum,
                    result=ValidationResult.ERROR,
                    error_message=f"Stage timed out after {self.stage_timeout_seconds}s",
                )
                result.add_stage_result(stage_result)
                result.complete(ValidationResult.ERROR)
                break

            except Exception as e:
                logger.exception(f"Unexpected error in stage {stage_enum.value}")
                stage_result = StageResult(
                    stage=stage_enum,
                    result=ValidationResult.ERROR,
                    error_message=str(e),
                )
                result.add_stage_result(stage_result)
                result.complete(ValidationResult.ERROR)
                break

        # If we completed all stages without breaking, mark as passed
        if result.overall_result == ValidationResult.PASS and len(result.stages) == 7:
            result.complete(ValidationResult.PASS)
            artifact.status = ArtifactStatus.VALID
        elif result.overall_result == ValidationResult.FAIL:
            artifact.status = ArtifactStatus.INVALID
        else:
            artifact.status = ArtifactStatus.FAILED

        artifact.validation_results = result.to_dict()
        artifact.update_timestamp()

        logger.info(
            f"Validation complete for {artifact.artifact_id}: "
            f"{result.overall_result.value} in {result.total_duration_seconds:.2f}s"
        )

        return result

    def _update_metrics_from_stage(
        self,
        result: ValidationPipelineResult,
        stage_result: StageResult,
    ) -> None:
        """Update pipeline metrics from stage result details."""
        details = stage_result.details

        if "total_tests" in details:
            result.total_tests = details["total_tests"]
        if "passing_tests" in details:
            result.passing_before_bug = details["passing_tests"]
        if "failing_tests" in details:
            result.failing_after_bug = details["failing_tests"]
        if "passing_after_weakening" in details:
            result.passing_after_weakening = details["passing_after_weakening"]
        if "changed_files" in details:
            result.changed_files_count = details["changed_files"]

    # =========================================================================
    # Stage 1: Test Files Existence
    # =========================================================================

    async def _stage1_test_files_existence(
        self,
        artifact: BugArtifact,
        pipeline_result: ValidationPipelineResult,
    ) -> StageResult:
        """
        Stage 1: Verify all test files referenced in artifact exist.

        Checks:
        - test_files list is not empty
        - Each file path is valid (not empty, no path traversal)
        """
        start_time = time.time()

        # Check test_files is not empty
        if not artifact.test_files:
            return StageResult(
                stage=ValidationStage.TEST_FILES_EXISTENCE,
                result=ValidationResult.FAIL,
                duration_seconds=time.time() - start_time,
                error_message="test_files list is empty",
                details={"test_files_count": 0},
            )

        # Validate each file path
        invalid_files = []
        for file_path in artifact.test_files:
            if not file_path or not isinstance(file_path, str):
                invalid_files.append(f"Invalid path: {file_path}")
            elif ".." in file_path:
                invalid_files.append(f"Path traversal detected: {file_path}")

        if invalid_files:
            return StageResult(
                stage=ValidationStage.TEST_FILES_EXISTENCE,
                result=ValidationResult.FAIL,
                duration_seconds=time.time() - start_time,
                error_message=f"Invalid test files: {invalid_files}",
                details={
                    "test_files_count": len(artifact.test_files),
                    "invalid_files": invalid_files,
                },
            )

        return StageResult(
            stage=ValidationStage.TEST_FILES_EXISTENCE,
            result=ValidationResult.PASS,
            duration_seconds=time.time() - start_time,
            details={"test_files_count": len(artifact.test_files)},
        )

    # =========================================================================
    # Stage 2: Test Parser Validity
    # =========================================================================

    async def _stage2_test_parser_validity(
        self,
        artifact: BugArtifact,
        pipeline_result: ValidationPipelineResult,
    ) -> StageResult:
        """
        Stage 2: Validate test parser produces correct JSON output.

        Checks:
        - test_parser is valid Python syntax
        - Parser contains required function/pattern
        - Sample execution produces valid JSON
        """
        start_time = time.time()

        # Check parser is not empty
        if not artifact.test_parser or not artifact.test_parser.strip():
            return StageResult(
                stage=ValidationStage.TEST_PARSER_VALIDITY,
                result=ValidationResult.FAIL,
                duration_seconds=time.time() - start_time,
                error_message="test_parser is empty",
            )

        # Validate Python syntax
        try:
            compile(artifact.test_parser, "<test_parser>", "exec")
        except SyntaxError as e:
            return StageResult(
                stage=ValidationStage.TEST_PARSER_VALIDITY,
                result=ValidationResult.FAIL,
                duration_seconds=time.time() - start_time,
                error_message=f"Invalid Python syntax: {e}",
                details={"line": e.lineno, "offset": e.offset},
            )

        # Check for parse function or main entry point
        has_parse = any(
            pattern in artifact.test_parser
            for pattern in ["def parse", "def main", "if __name__"]
        )
        if not has_parse:
            return StageResult(
                stage=ValidationStage.TEST_PARSER_VALIDITY,
                result=ValidationResult.FAIL,
                duration_seconds=time.time() - start_time,
                error_message="Parser missing parse function or main entry",
            )

        # Test execution with mock input (in mock mode)
        if self.use_mock_sandbox:
            # In mock mode, assume parser is valid if syntax checks pass
            return StageResult(
                stage=ValidationStage.TEST_PARSER_VALIDITY,
                result=ValidationResult.PASS,
                duration_seconds=time.time() - start_time,
                details={"validated_syntax": True, "mock_mode": True},
            )

        # In real mode, execute parser with sample input
        try:
            sample_output = await self._execute_parser(artifact.test_parser)
            if not sample_output:
                return StageResult(
                    stage=ValidationStage.TEST_PARSER_VALIDITY,
                    result=ValidationResult.FAIL,
                    duration_seconds=time.time() - start_time,
                    error_message="Parser produced no output",
                )

            # Validate JSON output
            try:
                parsed = json.loads(sample_output)
                if not isinstance(parsed, dict):
                    raise ValueError("Output is not a JSON object")
            except (json.JSONDecodeError, ValueError) as e:
                return StageResult(
                    stage=ValidationStage.TEST_PARSER_VALIDITY,
                    result=ValidationResult.FAIL,
                    duration_seconds=time.time() - start_time,
                    error_message=f"Parser output is not valid JSON: {e}",
                )

        except Exception as e:
            return StageResult(
                stage=ValidationStage.TEST_PARSER_VALIDITY,
                result=ValidationResult.ERROR,
                duration_seconds=time.time() - start_time,
                error_message=f"Parser execution failed: {e}",
            )

        return StageResult(
            stage=ValidationStage.TEST_PARSER_VALIDITY,
            result=ValidationResult.PASS,
            duration_seconds=time.time() - start_time,
            details={"validated_syntax": True, "validated_output": True},
        )

    async def _execute_parser(self, parser_code: str) -> str:
        """Execute parser with sample test output."""
        # Create sample test output
        sample_input = """
        test_example.py::test_foo PASSED
        test_example.py::test_bar FAILED
        test_example.py::test_baz PASSED
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(parser_code)
            parser_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                parser_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=sample_input.encode()),
                timeout=30,
            )
            return stdout.decode()
        finally:
            os.unlink(parser_path)

    # =========================================================================
    # Stage 3: Test Script Validity
    # =========================================================================

    async def _stage3_test_script_validity(
        self,
        artifact: BugArtifact,
        pipeline_result: ValidationPipelineResult,
    ) -> StageResult:
        """
        Stage 3: Run tests on clean code, all must pass.

        Checks:
        - test_script is valid bash
        - Tests execute successfully
        - All tests pass (count >= min_passing_tests)
        """
        start_time = time.time()

        # Check script is not empty
        if not artifact.test_script or not artifact.test_script.strip():
            return StageResult(
                stage=ValidationStage.TEST_SCRIPT_VALIDITY,
                result=ValidationResult.FAIL,
                duration_seconds=time.time() - start_time,
                error_message="test_script is empty",
            )

        # Check for shebang or bash commands
        if not (
            artifact.test_script.startswith("#!")
            or "pytest" in artifact.test_script
            or "unittest" in artifact.test_script
            or "bash" in artifact.test_script
        ):
            return StageResult(
                stage=ValidationStage.TEST_SCRIPT_VALIDITY,
                result=ValidationResult.FAIL,
                duration_seconds=time.time() - start_time,
                error_message="test_script missing shebang or test commands",
            )

        # Execute tests (mock or real)
        if self.use_mock_sandbox:
            mock_key = f"{artifact.artifact_id}:stage3"
            if mock_key in self._mock_test_results:
                exec_result = self._mock_test_results[mock_key]
            else:
                # Default mock: all tests pass
                exec_result = SandboxExecutionResult(
                    success=True,
                    exit_code=0,
                    stdout="10 passed",
                    stderr="",
                    duration_seconds=1.0,
                    test_results={"passed": 10, "failed": 0},
                )

            passing = exec_result.test_results.get("passed", 0)
            if passing < self.min_passing_tests:
                return StageResult(
                    stage=ValidationStage.TEST_SCRIPT_VALIDITY,
                    result=ValidationResult.FAIL,
                    duration_seconds=time.time() - start_time,
                    error_message=f"Insufficient passing tests: {passing} < {self.min_passing_tests}",
                    details={
                        "total_tests": passing
                        + exec_result.test_results.get("failed", 0),
                        "passing_tests": passing,
                    },
                )

            return StageResult(
                stage=ValidationStage.TEST_SCRIPT_VALIDITY,
                result=ValidationResult.PASS,
                duration_seconds=time.time() - start_time,
                details={
                    "total_tests": passing + exec_result.test_results.get("failed", 0),
                    "passing_tests": passing,
                    "mock_mode": True,
                },
            )

        # Real sandbox execution would go here
        # For now, return error indicating real sandbox not implemented
        return StageResult(
            stage=ValidationStage.TEST_SCRIPT_VALIDITY,
            result=ValidationResult.ERROR,
            duration_seconds=time.time() - start_time,
            error_message="Real sandbox execution not yet implemented",
        )

    # =========================================================================
    # Stage 4: Bug Scope Validation
    # =========================================================================

    async def _stage4_bug_scope_validation(
        self,
        artifact: BugArtifact,
        pipeline_result: ValidationPipelineResult,
    ) -> StageResult:
        """
        Stage 4: Verify bug changes sufficient files.

        Checks:
        - bug_inject.diff is valid diff format
        - Number of changed files >= min_changed_files
        """
        start_time = time.time()

        # Check diff is not empty
        if not artifact.bug_inject_diff or not artifact.bug_inject_diff.strip():
            return StageResult(
                stage=ValidationStage.BUG_SCOPE_VALIDATION,
                result=ValidationResult.FAIL,
                duration_seconds=time.time() - start_time,
                error_message="bug_inject.diff is empty",
            )

        # Parse diff to count changed files
        changed_files = self._count_changed_files(artifact.bug_inject_diff)

        if changed_files < self.min_changed_files:
            return StageResult(
                stage=ValidationStage.BUG_SCOPE_VALIDATION,
                result=ValidationResult.FAIL,
                duration_seconds=time.time() - start_time,
                error_message=(
                    f"Insufficient changed files: {changed_files} < {self.min_changed_files}"
                ),
                details={"changed_files": changed_files},
            )

        return StageResult(
            stage=ValidationStage.BUG_SCOPE_VALIDATION,
            result=ValidationResult.PASS,
            duration_seconds=time.time() - start_time,
            details={"changed_files": changed_files},
        )

    def _count_changed_files(self, diff: str) -> int:
        """Count unique files changed in a diff."""
        # Match "diff --git a/path b/path" or "+++ b/path" patterns
        file_patterns = [
            r"diff --git a/(.+?) b/",
            r"\+\+\+ b/(.+)",
            r"--- a/(.+)",
        ]

        files = set()
        for pattern in file_patterns:
            for match in re.finditer(pattern, diff):
                file_path = match.group(1)
                if file_path and file_path != "/dev/null":
                    files.add(file_path)

        return len(files)

    # =========================================================================
    # Stage 5: Bug Validity
    # =========================================================================

    async def _stage5_bug_validity(
        self,
        artifact: BugArtifact,
        pipeline_result: ValidationPipelineResult,
    ) -> StageResult:
        """
        Stage 5: Apply bug and verify tests fail.

        Checks:
        - bug_inject.diff applies cleanly
        - Some tests now fail (count >= min_failing_tests)
        """
        start_time = time.time()

        if self.use_mock_sandbox:
            mock_key = f"{artifact.artifact_id}:stage5"
            if mock_key in self._mock_test_results:
                exec_result = self._mock_test_results[mock_key]
            else:
                # Default mock: tests fail after bug
                exec_result = SandboxExecutionResult(
                    success=False,
                    exit_code=1,
                    stdout="5 passed, 3 failed",
                    stderr="",
                    duration_seconds=1.0,
                    test_results={"passed": 5, "failed": 3},
                )

            failing = exec_result.test_results.get("failed", 0)
            if failing < self.min_failing_tests:
                return StageResult(
                    stage=ValidationStage.BUG_VALIDITY,
                    result=ValidationResult.FAIL,
                    duration_seconds=time.time() - start_time,
                    error_message=f"Bug didn't break enough tests: {failing} < {self.min_failing_tests}",
                    details={"failing_tests": failing},
                )

            return StageResult(
                stage=ValidationStage.BUG_VALIDITY,
                result=ValidationResult.PASS,
                duration_seconds=time.time() - start_time,
                details={
                    "failing_tests": failing,
                    "mock_mode": True,
                },
            )

        # Real sandbox execution
        return StageResult(
            stage=ValidationStage.BUG_VALIDITY,
            result=ValidationResult.ERROR,
            duration_seconds=time.time() - start_time,
            error_message="Real sandbox execution not yet implemented",
        )

    # =========================================================================
    # Stage 6: Test Weakening Validity
    # =========================================================================

    async def _stage6_test_weakening_validity(
        self,
        artifact: BugArtifact,
        pipeline_result: ValidationPipelineResult,
    ) -> StageResult:
        """
        Stage 6: Apply test weakening and verify tests pass again.

        Checks:
        - test_weaken.diff applies cleanly on buggy code
        - Previously failing tests now pass
        """
        start_time = time.time()

        # Check weakening diff exists
        if not artifact.test_weaken_diff or not artifact.test_weaken_diff.strip():
            return StageResult(
                stage=ValidationStage.TEST_WEAKENING_VALIDITY,
                result=ValidationResult.FAIL,
                duration_seconds=time.time() - start_time,
                error_message="test_weaken.diff is empty",
            )

        if self.use_mock_sandbox:
            mock_key = f"{artifact.artifact_id}:stage6"
            if mock_key in self._mock_test_results:
                exec_result = self._mock_test_results[mock_key]
            else:
                # Default mock: tests pass after weakening
                exec_result = SandboxExecutionResult(
                    success=True,
                    exit_code=0,
                    stdout="8 passed",
                    stderr="",
                    duration_seconds=1.0,
                    test_results={"passed": 8, "failed": 0},
                )

            passing = exec_result.test_results.get("passed", 0)
            failing = exec_result.test_results.get("failed", 0)

            # Weakening should make previously failing tests pass
            if failing > 0:
                return StageResult(
                    stage=ValidationStage.TEST_WEAKENING_VALIDITY,
                    result=ValidationResult.FAIL,
                    duration_seconds=time.time() - start_time,
                    error_message=f"Tests still failing after weakening: {failing}",
                    details={"passing_after_weakening": passing, "failing": failing},
                )

            return StageResult(
                stage=ValidationStage.TEST_WEAKENING_VALIDITY,
                result=ValidationResult.PASS,
                duration_seconds=time.time() - start_time,
                details={
                    "passing_after_weakening": passing,
                    "mock_mode": True,
                },
            )

        # Real sandbox execution
        return StageResult(
            stage=ValidationStage.TEST_WEAKENING_VALIDITY,
            result=ValidationResult.ERROR,
            duration_seconds=time.time() - start_time,
            error_message="Real sandbox execution not yet implemented",
        )

    # =========================================================================
    # Stage 7: Inverse Mutation Testing
    # =========================================================================

    async def _stage7_inverse_mutation(
        self,
        artifact: BugArtifact,
        pipeline_result: ValidationPipelineResult,
    ) -> StageResult:
        """
        Stage 7: Verify each changed file contributes to test failure.

        For each file in bug_inject.diff:
        1. Reset to buggy state
        2. Revert only that file to clean
        3. Run tests (without weakening)
        4. At least one previously failing test should pass

        This validates that every modified file is necessary for the bug.
        """
        start_time = time.time()

        changed_files = self._get_changed_files(artifact.bug_inject_diff)

        if not changed_files:
            return StageResult(
                stage=ValidationStage.INVERSE_MUTATION_TESTING,
                result=ValidationResult.FAIL,
                duration_seconds=time.time() - start_time,
                error_message="No changed files found in diff",
            )

        if self.use_mock_sandbox:
            mock_key = f"{artifact.artifact_id}:stage7"
            if mock_key in self._mock_test_results:
                exec_result = self._mock_test_results[mock_key]
                if not exec_result.success:
                    return StageResult(
                        stage=ValidationStage.INVERSE_MUTATION_TESTING,
                        result=ValidationResult.FAIL,
                        duration_seconds=time.time() - start_time,
                        error_message="Not all files contribute to bug",
                        details={"tested_files": changed_files},
                    )
            # Default mock: all files contribute
            return StageResult(
                stage=ValidationStage.INVERSE_MUTATION_TESTING,
                result=ValidationResult.PASS,
                duration_seconds=time.time() - start_time,
                details={
                    "tested_files": changed_files,
                    "all_files_contribute": True,
                    "mock_mode": True,
                },
            )

        # Real sandbox execution
        return StageResult(
            stage=ValidationStage.INVERSE_MUTATION_TESTING,
            result=ValidationResult.ERROR,
            duration_seconds=time.time() - start_time,
            error_message="Real sandbox execution not yet implemented",
        )

    def _get_changed_files(self, diff: str) -> list[str]:
        """Get list of changed files from diff."""
        files = []
        for match in re.finditer(r"diff --git a/(.+?) b/", diff):
            file_path = match.group(1)
            if file_path:
                files.append(file_path)
        return files

    # =========================================================================
    # Mock Testing Support
    # =========================================================================

    def set_mock_result(
        self,
        artifact_id: str,
        stage: int,
        result: SandboxExecutionResult,
    ) -> None:
        """
        Set mock result for a specific stage.

        Args:
            artifact_id: The artifact ID
            stage: Stage number (3, 5, 6, or 7)
            result: The mock execution result
        """
        key = f"{artifact_id}:stage{stage}"
        self._mock_test_results[key] = result

    def clear_mock_results(self) -> None:
        """Clear all mock results."""
        self._mock_test_results.clear()


# =============================================================================
# Factory Function
# =============================================================================


def create_validation_pipeline(
    project_name: str = "aura",
    environment: str | None = None,
    use_mock: bool = False,
) -> ValidationPipeline:
    """
    Factory function to create a ValidationPipeline.

    Args:
        project_name: Project name for resource naming
        environment: Environment (dev, qa, prod)
        use_mock: Whether to use mock sandbox

    Returns:
        Configured ValidationPipeline instance
    """
    return ValidationPipeline(
        project_name=project_name,
        environment=environment,
        use_mock_sandbox=use_mock,
    )
