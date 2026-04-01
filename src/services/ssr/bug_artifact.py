"""
Project Aura - Bug Artifact Models for SSR Training

Defines the 5-file bug artifact format and associated dataclasses
for the Self-Play SWE-RL training pipeline per ADR-050.

5-File Bug Artifact Format:
1. test_script.sh - Bash script to run the test suite
2. test_files - List of oracle test file paths
3. test_parser.py - Parses test output to JSON {test_name: pass/fail}
4. bug_inject.diff - Git diff that introduces the bug
5. test_weaken.diff - Git diff that hides the bug from tests

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ArtifactStatus(Enum):
    """Status of a bug artifact in the SSR training pipeline."""

    PENDING = "pending"  # Artifact created, awaiting validation
    VALIDATING = "validating"  # Validation pipeline in progress
    VALID = "valid"  # All 7 validation stages passed
    INVALID = "invalid"  # One or more validation stages failed
    FAILED = "failed"  # Validation pipeline error (not a stage failure)
    ARCHIVED = "archived"  # Artifact expired or manually archived
    TRAINING = "training"  # Training workflow in progress (Step Functions)
    COMPLETED = "completed"  # Training workflow completed


class ValidationStage(Enum):
    """Stages in the 7-stage consistency validation pipeline."""

    TEST_FILES_EXISTENCE = "test_files_existence"  # Stage 1
    TEST_PARSER_VALIDITY = "test_parser_validity"  # Stage 2
    TEST_SCRIPT_VALIDITY = "test_script_validity"  # Stage 3
    BUG_SCOPE_VALIDATION = "bug_scope_validation"  # Stage 4
    BUG_VALIDITY = "bug_validity"  # Stage 5
    TEST_WEAKENING_VALIDITY = "test_weakening_validity"  # Stage 6
    INVERSE_MUTATION_TESTING = "inverse_mutation_testing"  # Stage 7


class ValidationResult(Enum):
    """Result of a single validation stage."""

    PASS = "pass"  # Stage completed successfully
    FAIL = "fail"  # Stage failed validation criteria
    SKIP = "skip"  # Stage skipped (e.g., due to prior failure)
    ERROR = "error"  # Stage encountered an error during execution


class InjectionStrategy(Enum):
    """Strategy used for bug injection.

    Based on Meta FAIR paper (arXiv:2512.18552) Section 3.1.
    """

    REMOVAL_ONLY = "removal_only"  # Remove code to introduce bug
    HISTORY_AWARE = "history_aware"  # Use git history to find real bugs
    REMOVAL_PLUS_HISTORY = "removal_plus_history"  # Combine both strategies
    DIRECT_INJECTION = "direct_injection"  # Directly inject synthetic bug


@dataclass
class BugArtifact:
    """5-file bug artifact for SSR training.

    This dataclass represents the complete bug artifact structure
    used in the Self-Play SWE-RL training pipeline. Each artifact
    contains all files needed to:
    1. Run tests on clean code (should pass)
    2. Apply bug and run tests (should fail)
    3. Apply weakening and run tests (should pass again)

    Attributes:
        artifact_id: Unique identifier for this artifact
        repository_id: Repository this artifact belongs to
        commit_sha: Base commit SHA for the artifact
        test_script: Content of test_script.sh
        test_files: List of oracle test file paths
        test_parser: Content of test_parser.py
        bug_inject_diff: Git diff introducing the bug
        test_weaken_diff: Git diff hiding bug from tests
        status: Current status in the pipeline
        injection_strategy: Strategy used for bug injection
        validation_results: Results from each validation stage
        s3_uri: S3 URI where artifact content is stored
        order: Bug order (1 for first-order, 2+ for higher-order)
        parent_artifact_id: For higher-order bugs, the parent artifact
        failed_patch_diff: For higher-order bugs, the failed solver patch
        min_passing_tests: Minimum tests that must pass (default: 1)
        min_changed_files: Minimum files changed by bug (default: 1)
        min_failing_tests: Minimum tests that must fail (default: 1)
        created_at: ISO 8601 timestamp of creation
        updated_at: ISO 8601 timestamp of last update
        metadata: Additional metadata for extensibility
    """

    artifact_id: str
    repository_id: str
    commit_sha: str
    test_script: str
    test_files: list[str]
    test_parser: str
    bug_inject_diff: str
    test_weaken_diff: str
    status: ArtifactStatus = ArtifactStatus.PENDING
    injection_strategy: InjectionStrategy = InjectionStrategy.REMOVAL_ONLY
    validation_results: dict[str, Any] = field(default_factory=dict)
    s3_uri: str | None = None
    # Higher-order bug tracking
    order: int = 1
    parent_artifact_id: str | None = None
    failed_patch_diff: str | None = None
    # Validation thresholds
    min_passing_tests: int = 1
    min_changed_files: int = 1
    min_failing_tests: int = 1
    # Timestamps
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # Extensibility
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def generate_id() -> str:
        """Generate a unique artifact ID."""
        return f"ssr-artifact-{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB storage.

        Note: Large content (test_script, test_parser, diffs) should be
        stored in S3 and referenced via s3_uri. This dict contains
        metadata only for DynamoDB's 400KB item limit.
        """
        return {
            "artifact_id": self.artifact_id,
            "repository_id": self.repository_id,
            "commit_sha": self.commit_sha,
            "status": self.status.value,
            "injection_strategy": self.injection_strategy.value,
            "validation_results": self.validation_results,
            "s3_uri": self.s3_uri,
            # Higher-order tracking
            "order": self.order,
            "parent_artifact_id": self.parent_artifact_id,
            # Validation thresholds
            "min_passing_tests": self.min_passing_tests,
            "min_changed_files": self.min_changed_files,
            "min_failing_tests": self.min_failing_tests,
            # File counts for quick queries (content in S3)
            "test_files_count": len(self.test_files),
            "bug_inject_diff_size": len(self.bug_inject_diff),
            "test_weaken_diff_size": len(self.test_weaken_diff),
            # Timestamps
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            # Extensibility
            "metadata": self.metadata,
        }

    @classmethod
    def from_dynamodb_item(
        cls,
        item: dict[str, Any],
        content: dict[str, Any] | None = None,
    ) -> BugArtifact:
        """Create from DynamoDB item with optional S3 content.

        Args:
            item: DynamoDB item dictionary
            content: Optional dict with test_script, test_parser, etc.
                    from S3. If not provided, these fields are empty.

        Returns:
            BugArtifact instance
        """
        content = content or {}

        return cls(
            artifact_id=str(item["artifact_id"]),
            repository_id=str(item["repository_id"]),
            commit_sha=str(item.get("commit_sha", "")),
            test_script=content.get("test_script", ""),
            test_files=content.get("test_files", []),
            test_parser=content.get("test_parser", ""),
            bug_inject_diff=content.get("bug_inject_diff", ""),
            test_weaken_diff=content.get("test_weaken_diff", ""),
            status=ArtifactStatus(item.get("status", "pending")),
            injection_strategy=InjectionStrategy(
                item.get("injection_strategy", "removal_only")
            ),
            validation_results=item.get("validation_results", {}),
            s3_uri=item.get("s3_uri"),
            order=int(item.get("order", 1)),
            parent_artifact_id=item.get("parent_artifact_id"),
            failed_patch_diff=content.get("failed_patch_diff"),
            min_passing_tests=int(item.get("min_passing_tests", 1)),
            min_changed_files=int(item.get("min_changed_files", 1)),
            min_failing_tests=int(item.get("min_failing_tests", 1)),
            created_at=str(item.get("created_at", "")),
            updated_at=str(item.get("updated_at", "")),
            metadata=item.get("metadata", {}),
        )

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to now."""
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def is_higher_order(self) -> bool:
        """Check if this is a higher-order bug (derived from failed solve)."""
        return self.order > 1 and self.parent_artifact_id is not None


@dataclass
class StageResult:
    """Result of a single validation stage.

    Captures the outcome, timing, and details of one stage
    in the 7-stage consistency validation pipeline.
    """

    stage: ValidationStage
    result: ValidationResult
    duration_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    executed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "stage": self.stage.value,
            "result": self.result.value,
            "duration_seconds": self.duration_seconds,
            "details": self.details,
            "error_message": self.error_message,
            "executed_at": self.executed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageResult:
        """Create from dictionary."""
        return cls(
            stage=ValidationStage(data["stage"]),
            result=ValidationResult(data["result"]),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            details=data.get("details", {}),
            error_message=data.get("error_message"),
            executed_at=data.get("executed_at", datetime.now(timezone.utc).isoformat()),
        )

    def is_success(self) -> bool:
        """Check if stage passed."""
        return self.result == ValidationResult.PASS


@dataclass
class ValidationPipelineResult:
    """Complete result of the 7-stage validation pipeline.

    Aggregates all stage results and provides overall status
    and summary metrics for the validation run.
    """

    artifact_id: str
    overall_result: ValidationResult
    stages: list[StageResult] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    # Test metrics from validation
    total_tests: int = 0
    passing_before_bug: int = 0
    failing_after_bug: int = 0
    passing_after_weakening: int = 0
    changed_files_count: int = 0
    # Execution metadata
    sandbox_id: str | None = None
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "artifact_id": self.artifact_id,
            "overall_result": self.overall_result.value,
            "stages": [s.to_dict() for s in self.stages],
            "total_duration_seconds": self.total_duration_seconds,
            "total_tests": self.total_tests,
            "passing_before_bug": self.passing_before_bug,
            "failing_after_bug": self.failing_after_bug,
            "passing_after_weakening": self.passing_after_weakening,
            "changed_files_count": self.changed_files_count,
            "sandbox_id": self.sandbox_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidationPipelineResult:
        """Create from dictionary."""
        return cls(
            artifact_id=data["artifact_id"],
            overall_result=ValidationResult(data["overall_result"]),
            stages=[StageResult.from_dict(s) for s in data.get("stages", [])],
            total_duration_seconds=float(data.get("total_duration_seconds", 0.0)),
            total_tests=int(data.get("total_tests", 0)),
            passing_before_bug=int(data.get("passing_before_bug", 0)),
            failing_after_bug=int(data.get("failing_after_bug", 0)),
            passing_after_weakening=int(data.get("passing_after_weakening", 0)),
            changed_files_count=int(data.get("changed_files_count", 0)),
            sandbox_id=data.get("sandbox_id"),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at"),
        )

    def add_stage_result(self, stage_result: StageResult) -> None:
        """Add a stage result and update totals."""
        self.stages.append(stage_result)
        self.total_duration_seconds += stage_result.duration_seconds

    def is_valid(self) -> bool:
        """Check if all stages passed."""
        return self.overall_result == ValidationResult.PASS

    def get_failed_stages(self) -> list[StageResult]:
        """Get list of stages that failed."""
        return [s for s in self.stages if s.result == ValidationResult.FAIL]

    def get_error_stages(self) -> list[StageResult]:
        """Get list of stages that had errors."""
        return [s for s in self.stages if s.result == ValidationResult.ERROR]

    def complete(self, result: ValidationResult) -> None:
        """Mark pipeline as complete with final result."""
        self.overall_result = result
        self.completed_at = datetime.now(timezone.utc).isoformat()
