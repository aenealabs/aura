"""
Project Aura - Git History Analyzer for SSR Training

Analyzes git repository history to identify revertible changes
that can be used for history-aware bug injection. This enables
the SSR training pipeline to leverage real-world bug fixes as
training data sources.

Key Features:
- Identifies bug-fix commits based on commit message patterns
- Extracts diff information for potential reversion
- Scores candidates by test coverage and complexity
- Filters out security-sensitive and excluded patterns

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
GitHub Issue: #162
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CommitCategory(Enum):
    """Category of a commit based on its message and changes."""

    BUG_FIX = "bug_fix"  # Fixes a bug
    FEATURE = "feature"  # Adds new functionality
    REFACTOR = "refactor"  # Code restructuring
    SECURITY = "security"  # Security-related change
    PERFORMANCE = "performance"  # Performance improvement
    DOCUMENTATION = "documentation"  # Documentation change
    TEST = "test"  # Test addition/modification
    CHORE = "chore"  # Build, config, dependency changes
    UNKNOWN = "unknown"  # Unable to categorize


class AnalysisStatus(Enum):
    """Status of git history analysis."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CommitInfo:
    """Information about a git commit.

    Attributes:
        sha: Full commit SHA
        short_sha: Short commit SHA (7 characters)
        author: Commit author name
        author_email: Commit author email
        date: Commit date as ISO 8601 string
        message: Full commit message
        subject: First line of commit message
        files_changed: List of files modified in this commit
        insertions: Number of lines added
        deletions: Number of lines deleted
        category: Categorized type of commit
    """

    sha: str
    short_sha: str
    author: str
    author_email: str
    date: str
    message: str
    subject: str
    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    category: CommitCategory = CommitCategory.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "sha": self.sha,
            "short_sha": self.short_sha,
            "author": self.author,
            "author_email": self.author_email,
            "date": self.date,
            "message": self.message,
            "subject": self.subject,
            "files_changed": self.files_changed,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "category": self.category.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CommitInfo:
        """Create from dictionary."""
        return cls(
            sha=str(data["sha"]),
            short_sha=str(data.get("short_sha", data["sha"][:7])),
            author=str(data.get("author", "")),
            author_email=str(data.get("author_email", "")),
            date=str(data.get("date", "")),
            message=str(data.get("message", "")),
            subject=str(data.get("subject", "")),
            files_changed=data.get("files_changed", []),
            insertions=int(data.get("insertions", 0)),
            deletions=int(data.get("deletions", 0)),
            category=CommitCategory(data.get("category", "unknown")),
        )


@dataclass
class RevertCandidate:
    """A commit candidate suitable for reversion-based bug injection.

    Represents a bug-fix commit that can be reverted to introduce
    a bug for training purposes.

    Attributes:
        commit: The commit information
        diff_content: The git diff content for this commit
        affected_functions: List of function names affected
        affected_classes: List of class names affected
        test_files: Test files that cover this code
        complexity_score: Code complexity estimate (0-100)
        test_coverage_score: Test coverage estimate (0-100)
        reversion_score: Overall score for reversion suitability (0-100)
        is_safe_to_revert: Whether this commit can be safely reverted
        exclusion_reason: Reason if excluded from reversion
    """

    commit: CommitInfo
    diff_content: str = ""
    affected_functions: list[str] = field(default_factory=list)
    affected_classes: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    complexity_score: float = 0.0
    test_coverage_score: float = 0.0
    reversion_score: float = 0.0
    is_safe_to_revert: bool = True
    exclusion_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "commit": self.commit.to_dict(),
            "diff_content": self.diff_content,
            "affected_functions": self.affected_functions,
            "affected_classes": self.affected_classes,
            "test_files": self.test_files,
            "complexity_score": self.complexity_score,
            "test_coverage_score": self.test_coverage_score,
            "reversion_score": self.reversion_score,
            "is_safe_to_revert": self.is_safe_to_revert,
            "exclusion_reason": self.exclusion_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevertCandidate:
        """Create from dictionary."""
        return cls(
            commit=CommitInfo.from_dict(data["commit"]),
            diff_content=str(data.get("diff_content", "")),
            affected_functions=data.get("affected_functions", []),
            affected_classes=data.get("affected_classes", []),
            test_files=data.get("test_files", []),
            complexity_score=float(data.get("complexity_score", 0.0)),
            test_coverage_score=float(data.get("test_coverage_score", 0.0)),
            reversion_score=float(data.get("reversion_score", 0.0)),
            is_safe_to_revert=bool(data.get("is_safe_to_revert", True)),
            exclusion_reason=data.get("exclusion_reason"),
        )


@dataclass
class AnalysisResult:
    """Result of git history analysis for a repository.

    Attributes:
        repository_id: Repository identifier
        repository_path: Local path to repository
        total_commits_analyzed: Number of commits analyzed
        bug_fix_commits_found: Number of bug-fix commits found
        revert_candidates: List of suitable reversion candidates
        excluded_commits: Commits excluded and reasons
        analysis_duration_seconds: How long analysis took
        status: Analysis status
        started_at: When analysis started
        completed_at: When analysis completed
        error_message: Error message if failed
    """

    repository_id: str
    repository_path: str
    total_commits_analyzed: int = 0
    bug_fix_commits_found: int = 0
    revert_candidates: list[RevertCandidate] = field(default_factory=list)
    excluded_commits: list[dict[str, str]] = field(default_factory=list)
    analysis_duration_seconds: float = 0.0
    status: AnalysisStatus = AnalysisStatus.PENDING
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "repository_id": self.repository_id,
            "repository_path": self.repository_path,
            "total_commits_analyzed": self.total_commits_analyzed,
            "bug_fix_commits_found": self.bug_fix_commits_found,
            "revert_candidates": [c.to_dict() for c in self.revert_candidates],
            "excluded_commits": self.excluded_commits,
            "analysis_duration_seconds": self.analysis_duration_seconds,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
        }


class GitHistoryAnalyzer:
    """Analyzes git repository history for bug-fix commits.

    This service examines git commit history to identify commits
    that fix bugs. These commits can then be reverted to introduce
    bugs for SSR training purposes.

    Features:
    - Categorizes commits by type (bug fix, feature, etc.)
    - Extracts diff content for potential reversion
    - Scores candidates by reversion suitability
    - Filters security-sensitive changes

    Example:
        analyzer = GitHistoryAnalyzer()
        result = await analyzer.analyze_repository(
            repository_id="repo-123",
            repository_path="/path/to/repo",
            max_commits=100
        )
        for candidate in result.revert_candidates:
            print(f"Candidate: {candidate.commit.subject}")
    """

    # Commit message patterns indicating bug fixes
    BUG_FIX_PATTERNS = [
        "fix",
        "bug",
        "issue",
        "crash",
        "error",
        "defect",
        "broken",
        "repair",
        "resolve",
        "patch",
        "hotfix",
        "regression",
        "correct",
        "fault",
    ]

    # Commit message patterns indicating security changes (exclude these)
    SECURITY_PATTERNS = [
        "security",
        "cve",
        "vulnerability",
        "exploit",
        "injection",
        "xss",
        "csrf",
        "auth",
        "password",
        "credential",
        "secret",
        "token",
        "encrypt",
        "decrypt",
        "sanitize",
    ]

    # File patterns to exclude from reversion
    EXCLUDED_FILE_PATTERNS = [
        ".env",
        "secret",
        "credential",
        "password",
        "key",
        "token",
        "config/prod",
        "production",
        ".pem",
        ".key",
        "private",
    ]

    def __init__(
        self,
        max_diff_size_bytes: int = 100_000,
        min_test_coverage_score: float = 0.3,
        min_complexity_score: float = 0.2,
        excluded_authors: list[str] | None = None,
        git_timeout_seconds: int = 30,
    ):
        """Initialize the git history analyzer.

        Args:
            max_diff_size_bytes: Maximum diff size to analyze (bytes)
            min_test_coverage_score: Minimum test coverage score to consider
            min_complexity_score: Minimum complexity score to consider
            excluded_authors: Author emails to exclude (e.g., bots)
            git_timeout_seconds: Timeout for git commands
        """
        self.max_diff_size_bytes = max_diff_size_bytes
        self.min_test_coverage_score = min_test_coverage_score
        self.min_complexity_score = min_complexity_score
        self.excluded_authors = excluded_authors or [
            "noreply@github.com",
            "dependabot[bot]@users.noreply.github.com",
            "renovate[bot]@users.noreply.github.com",
        ]
        self.git_timeout_seconds = git_timeout_seconds

        # Metrics tracking
        self._total_analyzed = 0
        self._total_candidates_found = 0

    async def analyze_repository(
        self,
        repository_id: str,
        repository_path: str,
        max_commits: int = 500,
        since_date: str | None = None,
        branch: str = "main",
    ) -> AnalysisResult:
        """Analyze repository git history for revertible bug fixes.

        Args:
            repository_id: Unique identifier for the repository
            repository_path: Local path to the git repository
            max_commits: Maximum number of commits to analyze
            since_date: Only analyze commits after this date (ISO 8601)
            branch: Branch to analyze

        Returns:
            AnalysisResult with revert candidates
        """
        result = AnalysisResult(
            repository_id=repository_id,
            repository_path=repository_path,
            status=AnalysisStatus.IN_PROGRESS,
        )

        start_time = datetime.now(timezone.utc)

        try:
            # Get commit log
            commits = await self._get_commit_log(
                repository_path, max_commits, since_date, branch
            )

            result.total_commits_analyzed = len(commits)
            logger.info(
                f"Analyzing {len(commits)} commits for repository {repository_id}"
            )

            # Filter for bug-fix commits
            bug_fixes = self._filter_bug_fix_commits(commits)
            result.bug_fix_commits_found = len(bug_fixes)

            # Process each bug-fix commit as a potential candidate
            for commit in bug_fixes:
                candidate = await self._process_commit(repository_path, commit)

                if candidate.is_safe_to_revert:
                    # Score the candidate
                    candidate = self._score_candidate(candidate)

                    if self._meets_threshold(candidate):
                        result.revert_candidates.append(candidate)
                    else:
                        result.excluded_commits.append(
                            {
                                "sha": commit.sha,
                                "reason": "Score below threshold",
                            }
                        )
                else:
                    result.excluded_commits.append(
                        {
                            "sha": commit.sha,
                            "reason": candidate.exclusion_reason
                            or "Not safe to revert",
                        }
                    )

            # Sort candidates by reversion score (highest first)
            result.revert_candidates.sort(key=lambda c: c.reversion_score, reverse=True)

            result.status = AnalysisStatus.COMPLETED
            result.completed_at = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            logger.error(f"Failed to analyze repository {repository_id}: {e}")
            result.status = AnalysisStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now(timezone.utc).isoformat()

        # Calculate duration
        end_time = datetime.now(timezone.utc)
        result.analysis_duration_seconds = (end_time - start_time).total_seconds()

        # Update metrics
        self._total_analyzed += result.total_commits_analyzed
        self._total_candidates_found += len(result.revert_candidates)

        logger.info(
            f"Analysis complete for {repository_id}: "
            f"{len(result.revert_candidates)} candidates from "
            f"{result.bug_fix_commits_found} bug fixes"
        )

        return result

    async def _get_commit_log(
        self,
        repository_path: str,
        max_commits: int,
        since_date: str | None,
        branch: str,
    ) -> list[CommitInfo]:
        """Get commit log from git repository."""
        cmd = [
            "git",
            "-C",
            repository_path,
            "log",
            branch,
            f"--max-count={max_commits}",
            "--format=%H|%h|%an|%ae|%aI|%s|%b|||",
            "--numstat",
        ]

        if since_date:
            cmd.append(f"--since={since_date}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.git_timeout_seconds
            )

            if proc.returncode != 0:
                raise RuntimeError(f"Git log failed: {stderr.decode()}")

            return self._parse_commit_log(stdout.decode())

        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Git log timed out after {self.git_timeout_seconds} seconds"
            )

    def _parse_commit_log(self, log_output: str) -> list[CommitInfo]:
        """Parse git log output into CommitInfo objects."""
        commits: list[CommitInfo] = []
        current_commit: dict[str, Any] | None = None
        current_files: list[str] = []
        insertions = 0
        deletions = 0

        for line in log_output.split("\n"):
            if "|||" in line:
                # This is a commit header line
                if current_commit:
                    # Save previous commit
                    current_commit["files_changed"] = current_files
                    current_commit["insertions"] = insertions
                    current_commit["deletions"] = deletions
                    commits.append(CommitInfo(**current_commit))

                # Parse new commit
                parts = line.split("|||")[0].split("|")
                if len(parts) >= 6:
                    sha = parts[0]
                    short_sha = parts[1]
                    author = parts[2]
                    author_email = parts[3]
                    date = parts[4]
                    subject = parts[5]
                    body = parts[6] if len(parts) > 6 else ""

                    current_commit = {
                        "sha": sha,
                        "short_sha": short_sha,
                        "author": author,
                        "author_email": author_email,
                        "date": date,
                        "message": f"{subject}\n\n{body}".strip(),
                        "subject": subject,
                        "category": CommitCategory.UNKNOWN,
                    }
                    current_files = []
                    insertions = 0
                    deletions = 0

            elif line.strip() and "\t" in line:
                # This is a numstat line: insertions deletions filename
                parts = line.split("\t")
                if len(parts) >= 3:
                    try:
                        ins = int(parts[0]) if parts[0] != "-" else 0
                        dels = int(parts[1]) if parts[1] != "-" else 0
                        insertions += ins
                        deletions += dels
                        current_files.append(parts[2])
                    except ValueError:
                        pass

        # Don't forget the last commit
        if current_commit:
            current_commit["files_changed"] = current_files
            current_commit["insertions"] = insertions
            current_commit["deletions"] = deletions
            commits.append(CommitInfo(**current_commit))

        return commits

    def _filter_bug_fix_commits(self, commits: list[CommitInfo]) -> list[CommitInfo]:
        """Filter commits to only include bug fixes."""
        bug_fixes = []

        for commit in commits:
            # Skip excluded authors
            if commit.author_email in self.excluded_authors:
                continue

            # Categorize the commit
            commit.category = self._categorize_commit(commit)

            if commit.category == CommitCategory.BUG_FIX:
                bug_fixes.append(commit)

        return bug_fixes

    def _categorize_commit(self, commit: CommitInfo) -> CommitCategory:
        """Categorize a commit based on its message."""
        message_lower = commit.message.lower()
        subject_lower = commit.subject.lower()

        # Check for security-related (these should be excluded later)
        for pattern in self.SECURITY_PATTERNS:
            if pattern in message_lower:
                return CommitCategory.SECURITY

        # Check for bug fix patterns
        for pattern in self.BUG_FIX_PATTERNS:
            if pattern in subject_lower:
                return CommitCategory.BUG_FIX

        # Check for other patterns
        if any(
            p in subject_lower for p in ["feat", "feature", "add", "implement", "new"]
        ):
            return CommitCategory.FEATURE

        if any(p in subject_lower for p in ["refactor", "clean", "reorganize"]):
            return CommitCategory.REFACTOR

        if any(p in subject_lower for p in ["perf", "optim", "speed", "fast"]):
            return CommitCategory.PERFORMANCE

        if any(p in subject_lower for p in ["doc", "readme", "comment"]):
            return CommitCategory.DOCUMENTATION

        if any(p in subject_lower for p in ["test", "spec", "coverage"]):
            return CommitCategory.TEST

        if any(p in subject_lower for p in ["chore", "build", "ci", "deps", "bump"]):
            return CommitCategory.CHORE

        return CommitCategory.UNKNOWN

    async def _process_commit(
        self, repository_path: str, commit: CommitInfo
    ) -> RevertCandidate:
        """Process a commit to create a revert candidate."""
        candidate = RevertCandidate(commit=commit)

        # Check for excluded file patterns
        for file_path in commit.files_changed:
            file_lower = file_path.lower()
            for pattern in self.EXCLUDED_FILE_PATTERNS:
                if pattern in file_lower:
                    candidate.is_safe_to_revert = False
                    candidate.exclusion_reason = f"Contains excluded file: {file_path}"
                    return candidate

        # Skip security-related commits
        if commit.category == CommitCategory.SECURITY:
            candidate.is_safe_to_revert = False
            candidate.exclusion_reason = "Security-related commit"
            return candidate

        # Get the diff content
        try:
            candidate.diff_content = await self._get_commit_diff(
                repository_path, commit.sha
            )
        except Exception as e:
            logger.warning(f"Failed to get diff for {commit.sha}: {e}")
            candidate.is_safe_to_revert = False
            candidate.exclusion_reason = f"Failed to get diff: {e}"
            return candidate

        # Check diff size
        if len(candidate.diff_content) > self.max_diff_size_bytes:
            candidate.is_safe_to_revert = False
            candidate.exclusion_reason = "Diff too large"
            return candidate

        # Extract affected functions and classes
        candidate.affected_functions = self._extract_functions_from_diff(
            candidate.diff_content
        )
        candidate.affected_classes = self._extract_classes_from_diff(
            candidate.diff_content
        )

        # Find related test files
        candidate.test_files = self._find_test_files(commit.files_changed)

        return candidate

    async def _get_commit_diff(self, repository_path: str, sha: str) -> str:
        """Get the diff content for a commit."""
        cmd = [
            "git",
            "-C",
            repository_path,
            "diff",
            f"{sha}^",
            sha,
            "--",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.git_timeout_seconds
            )

            if proc.returncode != 0:
                raise RuntimeError(f"Git diff failed: {stderr.decode()}")

            return stdout.decode()

        except asyncio.TimeoutError:
            raise RuntimeError("Git diff timed out")

    def _extract_functions_from_diff(self, diff_content: str) -> list[str]:
        """Extract function names from diff content."""
        functions: set[str] = set()

        # Look for Python function definitions
        import re

        # Pattern for Python functions
        python_pattern = r"^\+\s*def\s+(\w+)\s*\("
        for match in re.finditer(python_pattern, diff_content, re.MULTILINE):
            functions.add(match.group(1))

        # Pattern for JavaScript/TypeScript functions
        js_patterns = [
            r"^\+\s*function\s+(\w+)\s*\(",  # function name()
            r"^\+\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(",  # const name = () =>
            r"^\+\s*(\w+)\s*\([^)]*\)\s*{",  # name() { (method)
        ]
        for pattern in js_patterns:
            for match in re.finditer(pattern, diff_content, re.MULTILINE):
                functions.add(match.group(1))

        return list(functions)

    def _extract_classes_from_diff(self, diff_content: str) -> list[str]:
        """Extract class names from diff content."""
        classes: set[str] = set()

        import re

        # Pattern for Python classes
        python_pattern = r"^\+\s*class\s+(\w+)"
        for match in re.finditer(python_pattern, diff_content, re.MULTILINE):
            classes.add(match.group(1))

        # Pattern for JavaScript/TypeScript classes
        js_pattern = r"^\+\s*(?:export\s+)?class\s+(\w+)"
        for match in re.finditer(js_pattern, diff_content, re.MULTILINE):
            classes.add(match.group(1))

        return list(classes)

    def _find_test_files(self, changed_files: list[str]) -> list[str]:
        """Find test files related to changed files."""
        test_files: list[str] = []

        for file_path in changed_files:
            # Check if this is already a test file
            if "test" in file_path.lower():
                test_files.append(file_path)
                continue

            # Generate potential test file paths
            # e.g., src/foo.py -> tests/test_foo.py
            parts = file_path.split("/")
            filename = parts[-1]
            name_without_ext = filename.rsplit(".", 1)[0]

            # Common test file naming patterns
            potential_tests = [
                f"tests/test_{name_without_ext}.py",
                f"test/test_{name_without_ext}.py",
                f"tests/{name_without_ext}_test.py",
                f"__tests__/{name_without_ext}.test.js",
                f"__tests__/{name_without_ext}.test.ts",
            ]

            # We can't verify existence here, so just note the patterns
            # The GraphRAG integration will verify test coverage
            test_files.extend(potential_tests[:2])  # Just add first 2 as hints

        return test_files

    def _score_candidate(self, candidate: RevertCandidate) -> RevertCandidate:
        """Calculate scores for a revert candidate."""
        # Complexity score based on diff characteristics
        # Higher score = more complex change = better training data
        commit = candidate.commit

        complexity = 0.0

        # Factor 1: Number of files changed (normalized)
        files_score = min(len(commit.files_changed) / 5.0, 1.0)
        complexity += files_score * 0.3

        # Factor 2: Lines changed (normalized)
        total_changes = commit.insertions + commit.deletions
        changes_score = min(total_changes / 100.0, 1.0)
        complexity += changes_score * 0.3

        # Factor 3: Functions/classes affected
        code_units = len(candidate.affected_functions) + len(candidate.affected_classes)
        units_score = min(code_units / 3.0, 1.0)
        complexity += units_score * 0.4

        candidate.complexity_score = complexity

        # Test coverage score based on test file hints
        # Higher = better, as we want changes with test coverage
        if candidate.test_files:
            coverage_ratio = min(
                len(candidate.test_files) / len(commit.files_changed), 1.0
            )
            candidate.test_coverage_score = coverage_ratio * 0.8 + 0.2
        else:
            candidate.test_coverage_score = 0.2  # Minimum baseline

        # Overall reversion score
        # Weighted combination favoring covered, complex changes
        candidate.reversion_score = (
            candidate.complexity_score * 0.4 + candidate.test_coverage_score * 0.6
        )

        return candidate

    def _meets_threshold(self, candidate: RevertCandidate) -> bool:
        """Check if candidate meets minimum thresholds."""
        return (
            candidate.test_coverage_score >= self.min_test_coverage_score
            and candidate.complexity_score >= self.min_complexity_score
        )

    def get_metrics(self) -> dict[str, Any]:
        """Get analyzer metrics."""
        return {
            "total_commits_analyzed": self._total_analyzed,
            "total_candidates_found": self._total_candidates_found,
            "max_diff_size_bytes": self.max_diff_size_bytes,
            "min_test_coverage_score": self.min_test_coverage_score,
            "min_complexity_score": self.min_complexity_score,
            "excluded_authors_count": len(self.excluded_authors),
        }


def create_git_analyzer(
    max_diff_size_bytes: int = 100_000,
    min_test_coverage_score: float = 0.3,
    min_complexity_score: float = 0.2,
) -> GitHistoryAnalyzer:
    """Factory function to create a GitHistoryAnalyzer instance.

    Args:
        max_diff_size_bytes: Maximum diff size to analyze
        min_test_coverage_score: Minimum test coverage score
        min_complexity_score: Minimum complexity score

    Returns:
        Configured GitHistoryAnalyzer instance
    """
    return GitHistoryAnalyzer(
        max_diff_size_bytes=max_diff_size_bytes,
        min_test_coverage_score=min_test_coverage_score,
        min_complexity_score=min_complexity_score,
    )
