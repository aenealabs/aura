"""
Project Aura - History-Aware Bug Injector for SSR Training

Implements history-aware bug injection using git history analysis
and GraphRAG integration to create high-quality training artifacts.
This approach leverages real-world bug fixes from repository history
to create more realistic and challenging training data.

Key Features:
- Git history-based bug identification
- GraphRAG-enhanced candidate selection
- Test coverage verification via Neptune
- Reversion-based bug injection
- Quality scoring and filtering

Reference: Self-play SWE-RL paper (arXiv:2512.18552), Section 2.3

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
GitHub Issue: #162
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.services.ssr.bug_artifact import ArtifactStatus, BugArtifact, InjectionStrategy
from src.services.ssr.git_analyzer import GitHistoryAnalyzer, RevertCandidate

if TYPE_CHECKING:
    from src.services.neptune_graph_service import NeptuneGraphService

logger = logging.getLogger(__name__)


class InjectionStatus(Enum):
    """Status of a history-aware injection operation."""

    PENDING = "pending"
    ANALYZING = "analyzing"  # Analyzing git history
    SELECTING = "selecting"  # Selecting candidates via GraphRAG
    INJECTING = "injecting"  # Creating bug artifact
    VALIDATING = "validating"  # Validating created artifact
    COMPLETED = "completed"
    FAILED = "failed"


class CandidateRankingStrategy(Enum):
    """Strategy for ranking reversion candidates."""

    COMPLEXITY_FIRST = "complexity_first"  # Prioritize complex changes
    COVERAGE_FIRST = "coverage_first"  # Prioritize well-tested changes
    BALANCED = "balanced"  # Balance both factors
    GRAPHRAG_ENHANCED = "graphrag_enhanced"  # Use GraphRAG for ranking


@dataclass
class GraphRAGContext:
    """Context from GraphRAG for a code region.

    Attributes:
        file_path: Path to the source file
        function_name: Function being analyzed (if applicable)
        class_name: Class being analyzed (if applicable)
        call_graph_depth: Depth of call graph analysis
        callers: Functions that call this code
        callees: Functions called by this code
        dependencies: Imported modules/classes
        dependents: Code that depends on this
        test_coverage: Test files covering this code
        complexity_score: GraphRAG-computed complexity
        centrality_score: How central this code is in the codebase
    """

    file_path: str
    function_name: str | None = None
    class_name: str | None = None
    call_graph_depth: int = 0
    callers: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)
    test_coverage: list[str] = field(default_factory=list)
    complexity_score: float = 0.0
    centrality_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "function_name": self.function_name,
            "class_name": self.class_name,
            "call_graph_depth": self.call_graph_depth,
            "callers": self.callers,
            "callees": self.callees,
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "test_coverage": self.test_coverage,
            "complexity_score": self.complexity_score,
            "centrality_score": self.centrality_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphRAGContext:
        """Create from dictionary."""
        return cls(
            file_path=str(data.get("file_path", "")),
            function_name=data.get("function_name"),
            class_name=data.get("class_name"),
            call_graph_depth=int(data.get("call_graph_depth", 0)),
            callers=data.get("callers", []),
            callees=data.get("callees", []),
            dependencies=data.get("dependencies", []),
            dependents=data.get("dependents", []),
            test_coverage=data.get("test_coverage", []),
            complexity_score=float(data.get("complexity_score", 0.0)),
            centrality_score=float(data.get("centrality_score", 0.0)),
        )


@dataclass
class EnrichedCandidate:
    """A reversion candidate enriched with GraphRAG context.

    Combines git history analysis with GraphRAG code intelligence
    for more informed bug injection decisions.

    Attributes:
        candidate: Original reversion candidate from git analysis
        graphrag_context: Context from GraphRAG queries
        enhanced_score: Score incorporating GraphRAG insights
        test_file_paths: Verified test file paths from GraphRAG
        affected_components: Components impacted by this change
        injection_difficulty: Estimated difficulty (1-10)
        is_selected: Whether this candidate was selected for injection
        rejection_reason: Reason if not selected
    """

    candidate: RevertCandidate
    graphrag_context: list[GraphRAGContext] = field(default_factory=list)
    enhanced_score: float = 0.0
    test_file_paths: list[str] = field(default_factory=list)
    affected_components: list[str] = field(default_factory=list)
    injection_difficulty: int = 5
    is_selected: bool = False
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "candidate": self.candidate.to_dict(),
            "graphrag_context": [c.to_dict() for c in self.graphrag_context],
            "enhanced_score": self.enhanced_score,
            "test_file_paths": self.test_file_paths,
            "affected_components": self.affected_components,
            "injection_difficulty": self.injection_difficulty,
            "is_selected": self.is_selected,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class InjectionResult:
    """Result of a history-aware bug injection operation.

    Attributes:
        repository_id: Repository identifier
        artifact: Created bug artifact (if successful)
        candidate_used: Enriched candidate that was injected
        total_candidates_analyzed: Number of candidates considered
        graphrag_queries_executed: Number of GraphRAG queries run
        status: Injection status
        duration_seconds: How long injection took
        started_at: When injection started
        completed_at: When injection completed
        error_message: Error message if failed
    """

    repository_id: str
    artifact: BugArtifact | None = None
    candidate_used: EnrichedCandidate | None = None
    total_candidates_analyzed: int = 0
    graphrag_queries_executed: int = 0
    status: InjectionStatus = InjectionStatus.PENDING
    duration_seconds: float = 0.0
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "repository_id": self.repository_id,
            "artifact": self.artifact.to_dict() if self.artifact else None,
            "candidate_used": (
                self.candidate_used.to_dict() if self.candidate_used else None
            ),
            "total_candidates_analyzed": self.total_candidates_analyzed,
            "graphrag_queries_executed": self.graphrag_queries_executed,
            "status": self.status.value,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
        }


class HistoryAwareBugInjector:
    """Injects bugs using git history analysis and GraphRAG.

    This service combines git history analysis with Neptune GraphRAG
    to identify and inject high-quality bugs for SSR training.

    The process:
    1. Analyze git history for bug-fix commits
    2. Query GraphRAG for code structure and test coverage
    3. Score and rank candidates
    4. Select best candidate and create bug artifact
    5. Generate test weakening patch

    Example:
        injector = HistoryAwareBugInjector(graph_service=neptune)
        result = await injector.inject_from_history(
            repository_id="repo-123",
            repository_path="/path/to/repo",
            max_candidates=10
        )
        if result.artifact:
            print(f"Created artifact: {result.artifact.artifact_id}")

    Reference: SSR paper Section 2.3, Figure 3
    """

    # GraphRAG query templates for code structure
    CALL_GRAPH_QUERY = """
        g.V().has('repository_id', '{repo_id}')
         .has('file_path', '{file_path}')
         .has('name', '{function_name}')
         .outE('CALLS').inV()
         .project('name', 'file_path')
         .by('name').by('file_path')
    """

    CALLERS_QUERY = """
        g.V().has('repository_id', '{repo_id}')
         .has('file_path', '{file_path}')
         .has('name', '{function_name}')
         .inE('CALLS').outV()
         .project('name', 'file_path')
         .by('name').by('file_path')
    """

    TEST_COVERAGE_QUERY = """
        g.V().has('repository_id', '{repo_id}')
         .has('file_path', '{file_path}')
         .inE('TESTS').outV()
         .project('test_file', 'test_name')
         .by('file_path').by('name')
    """

    COMPLEXITY_QUERY = """
        g.V().has('repository_id', '{repo_id}')
         .has('file_path', '{file_path}')
         .values('complexity')
    """

    def __init__(
        self,
        graph_service: NeptuneGraphService | None = None,
        git_analyzer: GitHistoryAnalyzer | None = None,
        min_test_coverage: int = 1,
        min_enhanced_score: float = 0.4,
        max_graphrag_queries_per_candidate: int = 5,
        ranking_strategy: CandidateRankingStrategy = CandidateRankingStrategy.GRAPHRAG_ENHANCED,
        graphrag_timeout_seconds: int = 30,
    ):
        """Initialize the history-aware bug injector.

        Args:
            graph_service: Neptune graph service for GraphRAG queries
            git_analyzer: Git history analyzer (created if not provided)
            min_test_coverage: Minimum test files covering a candidate
            min_enhanced_score: Minimum score to consider a candidate
            max_graphrag_queries_per_candidate: Max GraphRAG queries per candidate
            ranking_strategy: Strategy for ranking candidates
            graphrag_timeout_seconds: Timeout for GraphRAG queries
        """
        self.graph_service = graph_service
        self.git_analyzer = git_analyzer or GitHistoryAnalyzer()
        self.min_test_coverage = min_test_coverage
        self.min_enhanced_score = min_enhanced_score
        self.max_graphrag_queries = max_graphrag_queries_per_candidate
        self.ranking_strategy = ranking_strategy
        self.graphrag_timeout = graphrag_timeout_seconds

        # Metrics tracking
        self._total_injections = 0
        self._successful_injections = 0
        self._graphrag_queries_total = 0

    async def inject_from_history(
        self,
        repository_id: str,
        repository_path: str,
        commit_sha: str | None = None,
        max_candidates: int = 20,
        max_commits_to_analyze: int = 500,
        branch: str = "main",
    ) -> InjectionResult:
        """Inject a bug using history-aware analysis.

        Args:
            repository_id: Unique identifier for the repository
            repository_path: Local path to the git repository
            commit_sha: Base commit SHA (HEAD if not provided)
            max_candidates: Maximum candidates to consider
            max_commits_to_analyze: Maximum commits to analyze from history
            branch: Branch to analyze

        Returns:
            InjectionResult with created artifact or error details
        """
        result = InjectionResult(
            repository_id=repository_id,
            status=InjectionStatus.ANALYZING,
        )

        start_time = datetime.now(timezone.utc)
        self._total_injections += 1

        try:
            # Step 1: Analyze git history
            logger.info(f"Analyzing git history for {repository_id}")
            result.status = InjectionStatus.ANALYZING

            analysis = await self.git_analyzer.analyze_repository(
                repository_id=repository_id,
                repository_path=repository_path,
                max_commits=max_commits_to_analyze,
                branch=branch,
            )

            if not analysis.revert_candidates:
                result.status = InjectionStatus.FAILED
                result.error_message = "No suitable bug-fix commits found in history"
                return self._finalize_result(result, start_time)

            # Limit candidates for GraphRAG enrichment
            candidates_to_process = analysis.revert_candidates[:max_candidates]
            result.total_candidates_analyzed = len(candidates_to_process)

            # Step 2: Enrich candidates with GraphRAG
            logger.info(
                f"Enriching {len(candidates_to_process)} candidates with GraphRAG"
            )
            result.status = InjectionStatus.SELECTING

            enriched_candidates = await self._enrich_candidates_with_graphrag(
                repository_id, candidates_to_process
            )
            result.graphrag_queries_executed = self._count_queries(enriched_candidates)

            # Step 3: Score and rank candidates
            ranked_candidates = self._rank_candidates(enriched_candidates)

            # Step 4: Select best candidate
            selected = self._select_best_candidate(ranked_candidates)

            if not selected:
                result.status = InjectionStatus.FAILED
                result.error_message = "No candidates met selection criteria"
                return self._finalize_result(result, start_time)

            selected.is_selected = True
            result.candidate_used = selected

            # Step 5: Create bug artifact
            logger.info(
                f"Creating bug artifact from commit {selected.candidate.commit.short_sha}"
            )
            result.status = InjectionStatus.INJECTING

            artifact = await self._create_artifact(
                repository_id=repository_id,
                repository_path=repository_path,
                commit_sha=commit_sha or "HEAD",
                candidate=selected,
            )

            result.artifact = artifact
            result.status = InjectionStatus.COMPLETED
            self._successful_injections += 1

            logger.info(f"Successfully created artifact {artifact.artifact_id}")

        except Exception as e:
            logger.error(f"History-aware injection failed for {repository_id}: {e}")
            result.status = InjectionStatus.FAILED
            result.error_message = str(e)

        return self._finalize_result(result, start_time)

    async def _enrich_candidates_with_graphrag(
        self,
        repository_id: str,
        candidates: list[RevertCandidate],
    ) -> list[EnrichedCandidate]:
        """Enrich candidates with GraphRAG context."""
        enriched: list[EnrichedCandidate] = []

        for candidate in candidates:
            enriched_candidate = EnrichedCandidate(candidate=candidate)

            if self.graph_service:
                # Query GraphRAG for each affected file/function
                contexts = []
                for file_path in candidate.commit.files_changed[:3]:  # Limit files
                    context = await self._query_graphrag_for_file(
                        repository_id, file_path, candidate
                    )
                    if context:
                        contexts.append(context)

                enriched_candidate.graphrag_context = contexts

                # Extract verified test files from GraphRAG
                enriched_candidate.test_file_paths = self._extract_test_files(contexts)

                # Calculate enhanced score
                enriched_candidate.enhanced_score = self._calculate_enhanced_score(
                    candidate, contexts
                )

                # Estimate difficulty
                enriched_candidate.injection_difficulty = self._estimate_difficulty(
                    candidate, contexts
                )
            else:
                # No GraphRAG - use base scores
                enriched_candidate.enhanced_score = candidate.reversion_score
                enriched_candidate.test_file_paths = candidate.test_files
                enriched_candidate.injection_difficulty = 5

            enriched.append(enriched_candidate)

        return enriched

    async def _query_graphrag_for_file(
        self,
        repository_id: str,
        file_path: str,
        candidate: RevertCandidate,
    ) -> GraphRAGContext | None:
        """Query GraphRAG for a specific file's context."""
        if not self.graph_service:
            return None

        context = GraphRAGContext(file_path=file_path)

        try:
            # Query for test coverage
            test_query = self.TEST_COVERAGE_QUERY.format(
                repo_id=repository_id,
                file_path=file_path,
            )
            test_results = await self._execute_graphrag_query(test_query)
            context.test_coverage = [
                r.get("test_file", "") for r in test_results if r.get("test_file")
            ]

            # Query for complexity
            complexity_query = self.COMPLEXITY_QUERY.format(
                repo_id=repository_id,
                file_path=file_path,
            )
            complexity_results = await self._execute_graphrag_query(complexity_query)
            if complexity_results:
                context.complexity_score = float(complexity_results[0])

            # Query call graph for affected functions
            for func_name in candidate.affected_functions[:2]:  # Limit queries
                context.function_name = func_name

                # Get callers
                callers_query = self.CALLERS_QUERY.format(
                    repo_id=repository_id,
                    file_path=file_path,
                    function_name=func_name,
                )
                caller_results = await self._execute_graphrag_query(callers_query)
                context.callers.extend(
                    [r.get("name", "") for r in caller_results if r.get("name")]
                )

                # Get callees
                callees_query = self.CALL_GRAPH_QUERY.format(
                    repo_id=repository_id,
                    file_path=file_path,
                    function_name=func_name,
                )
                callee_results = await self._execute_graphrag_query(callees_query)
                context.callees.extend(
                    [r.get("name", "") for r in callee_results if r.get("name")]
                )

            # Calculate centrality based on call graph
            total_connections = len(context.callers) + len(context.callees)
            context.centrality_score = min(total_connections / 10.0, 1.0)

            self._graphrag_queries_total += 4  # Count queries made

            return context

        except Exception as e:
            logger.warning(f"GraphRAG query failed for {file_path}: {e}")
            return context

    async def _execute_graphrag_query(self, query: str) -> list[Any]:
        """Execute a GraphRAG query with timeout."""
        if not self.graph_service:
            return []

        try:
            # Use the graph service's query method
            result = await asyncio.wait_for(
                asyncio.to_thread(self.graph_service.execute_gremlin, query),
                timeout=self.graphrag_timeout,
            )
            return result if isinstance(result, list) else []
        except asyncio.TimeoutError:
            logger.warning("GraphRAG query timed out")
            return []
        except Exception as e:
            logger.warning(f"GraphRAG query failed: {e}")
            return []

    def _extract_test_files(self, contexts: list[GraphRAGContext]) -> list[str]:
        """Extract unique test file paths from contexts."""
        test_files: set[str] = set()
        for context in contexts:
            test_files.update(context.test_coverage)
        return list(test_files)

    def _calculate_enhanced_score(
        self,
        candidate: RevertCandidate,
        contexts: list[GraphRAGContext],
    ) -> float:
        """Calculate enhanced score using GraphRAG context."""
        if not contexts:
            return candidate.reversion_score

        # Base score from git analysis
        base_score = candidate.reversion_score

        # GraphRAG enhancements
        total_test_coverage = sum(len(c.test_coverage) for c in contexts)
        coverage_bonus = min(total_test_coverage / 5.0, 0.3)

        avg_complexity = sum(c.complexity_score for c in contexts) / len(contexts)
        complexity_bonus = min(avg_complexity / 20.0, 0.2)

        avg_centrality = sum(c.centrality_score for c in contexts) / len(contexts)
        centrality_bonus = avg_centrality * 0.2

        enhanced = base_score + coverage_bonus + complexity_bonus + centrality_bonus
        return min(enhanced, 1.0)

    def _estimate_difficulty(
        self,
        candidate: RevertCandidate,
        contexts: list[GraphRAGContext],
    ) -> int:
        """Estimate bug difficulty on a scale of 1-10."""
        # Base difficulty from change size
        commit = candidate.commit
        size_factor = min((commit.insertions + commit.deletions) / 50.0, 1.0)

        # Complexity from GraphRAG
        if contexts:
            complexity_factor = sum(c.complexity_score for c in contexts) / (
                len(contexts) * 20.0
            )
            complexity_factor = min(complexity_factor, 1.0)
        else:
            complexity_factor = 0.5

        # Call graph depth factor
        if contexts:
            depth_factor = min(
                max(len(c.callers) + len(c.callees) for c in contexts) / 10.0, 1.0
            )
        else:
            depth_factor = 0.5

        # Weighted combination
        difficulty_raw = (
            size_factor * 0.3 + complexity_factor * 0.4 + depth_factor * 0.3
        )
        difficulty = int(1 + difficulty_raw * 9)  # Scale to 1-10

        return max(1, min(10, difficulty))

    def _rank_candidates(
        self, candidates: list[EnrichedCandidate]
    ) -> list[EnrichedCandidate]:
        """Rank candidates by the configured strategy."""
        if self.ranking_strategy == CandidateRankingStrategy.COMPLEXITY_FIRST:
            return sorted(
                candidates,
                key=lambda c: c.candidate.complexity_score,
                reverse=True,
            )
        elif self.ranking_strategy == CandidateRankingStrategy.COVERAGE_FIRST:
            return sorted(
                candidates,
                key=lambda c: len(c.test_file_paths),
                reverse=True,
            )
        elif self.ranking_strategy == CandidateRankingStrategy.BALANCED:
            return sorted(
                candidates,
                key=lambda c: c.candidate.reversion_score,
                reverse=True,
            )
        else:  # GRAPHRAG_ENHANCED
            return sorted(
                candidates,
                key=lambda c: c.enhanced_score,
                reverse=True,
            )

    def _select_best_candidate(
        self, ranked_candidates: list[EnrichedCandidate]
    ) -> EnrichedCandidate | None:
        """Select the best candidate that meets criteria."""
        for candidate in ranked_candidates:
            # Check minimum test coverage
            if len(candidate.test_file_paths) < self.min_test_coverage:
                candidate.rejection_reason = "Insufficient test coverage"
                continue

            # Check minimum score
            if candidate.enhanced_score < self.min_enhanced_score:
                candidate.rejection_reason = "Score below threshold"
                continue

            # Check if safe to revert
            if not candidate.candidate.is_safe_to_revert:
                candidate.rejection_reason = candidate.candidate.exclusion_reason
                continue

            return candidate

        return None

    async def _create_artifact(
        self,
        repository_id: str,
        repository_path: str,
        commit_sha: str,
        candidate: EnrichedCandidate,
    ) -> BugArtifact:
        """Create a bug artifact from the selected candidate."""
        artifact_id = f"ssr-artifact-{uuid.uuid4().hex[:12]}"

        # Create the bug injection diff (reverse the fix)
        bug_inject_diff = self._reverse_diff(candidate.candidate.diff_content)

        # Create a basic test script
        test_script = self._generate_test_script(candidate.test_file_paths)

        # Create a basic test parser
        test_parser = self._generate_test_parser()

        # Create test weakening diff (placeholder - real implementation
        # would analyze which assertions to weaken)
        test_weaken_diff = self._generate_test_weakening(candidate)

        artifact = BugArtifact(
            artifact_id=artifact_id,
            repository_id=repository_id,
            commit_sha=commit_sha,
            test_script=test_script,
            test_files=candidate.test_file_paths,
            test_parser=test_parser,
            bug_inject_diff=bug_inject_diff,
            test_weaken_diff=test_weaken_diff,
            status=ArtifactStatus.PENDING,
            injection_strategy=InjectionStrategy.HISTORY_AWARE,
            min_passing_tests=len(candidate.test_file_paths),
            min_changed_files=len(candidate.candidate.commit.files_changed),
            min_failing_tests=1,
            metadata={
                "source_commit": candidate.candidate.commit.sha,
                "source_subject": candidate.candidate.commit.subject,
                "injection_difficulty": candidate.injection_difficulty,
                "enhanced_score": candidate.enhanced_score,
                "affected_functions": candidate.candidate.affected_functions,
                "affected_classes": candidate.candidate.affected_classes,
            },
        )

        return artifact

    def _reverse_diff(self, diff_content: str) -> str:
        """Reverse a git diff to turn a fix into a bug."""
        # Swap + and - lines to reverse the patch
        lines = diff_content.split("\n")
        reversed_lines: list[str] = []

        for line in lines:
            if line.startswith("+") and not line.startswith("+++"):
                reversed_lines.append("-" + line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                reversed_lines.append("+" + line[1:])
            elif line.startswith("@@"):
                # Swap the line numbers in hunk header
                # @@ -old,old +new,new @@ -> @@ -new,new +old,old @@
                import re

                match = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@(.*)", line)
                if match:
                    old_start, old_count, new_start, new_count, rest = match.groups()
                    reversed_lines.append(
                        f"@@ -{new_start},{new_count or '1'} "
                        f"+{old_start},{old_count or '1'} @@{rest}"
                    )
                else:
                    reversed_lines.append(line)
            elif line.startswith("---"):
                reversed_lines.append("+++ " + line[4:])
            elif line.startswith("+++"):
                reversed_lines.append("--- " + line[4:])
            else:
                reversed_lines.append(line)

        return "\n".join(reversed_lines)

    def _generate_test_script(self, test_files: list[str]) -> str:
        """Generate a test script for the artifact."""
        # Determine test framework from file patterns
        has_python = any(f.endswith(".py") for f in test_files)
        has_js = any(f.endswith((".js", ".ts")) for f in test_files)

        script = "#!/bin/bash\nset -e\n\n"

        if has_python:
            test_file_list = " ".join(f for f in test_files if f.endswith(".py"))
            script += f"python -m pytest {test_file_list} -v --tb=short\n"
        elif has_js:
            script += "npm test\n"
        else:
            # Generic fallback
            script += "# Add test execution command here\n"
            script += "echo 'Tests not configured'\nexit 1\n"

        return script

    def _generate_test_parser(self) -> str:
        """Generate a test output parser."""
        return r'''#!/usr/bin/env python3
"""Parse test output to JSON format."""
import json
import re
import sys

def parse_pytest_output(output: str) -> dict[str, str]:
    """Parse pytest output to test results."""
    results = {}

    # Match pytest result lines like "test_foo.py::test_bar PASSED"
    pattern = r"([\w/]+\.py::\w+)\s+(PASSED|FAILED|ERROR|SKIPPED)"
    for match in re.finditer(pattern, output):
        test_name = match.group(1)
        status = match.group(2).lower()
        results[test_name] = "passed" if status == "passed" else "failed"

    return results

def main():
    output = sys.stdin.read()
    results = parse_pytest_output(output)
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
'''

    def _generate_test_weakening(self, candidate: EnrichedCandidate) -> str:
        """Generate a test weakening diff.

        This is a placeholder - real implementation would:
        1. Analyze which assertions would catch the bug
        2. Generate a diff that weakens those assertions
        """
        # Return empty diff as placeholder
        # Real implementation would use LLM or static analysis
        return ""

    def _count_queries(self, candidates: list[EnrichedCandidate]) -> int:
        """Count total GraphRAG queries executed."""
        return sum(
            len(c.graphrag_context) * 4 for c in candidates  # 4 queries per context
        )

    def _finalize_result(
        self, result: InjectionResult, start_time: datetime
    ) -> InjectionResult:
        """Finalize the result with timing info."""
        end_time = datetime.now(timezone.utc)
        result.duration_seconds = (end_time - start_time).total_seconds()
        result.completed_at = end_time.isoformat()
        return result

    def get_metrics(self) -> dict[str, Any]:
        """Get injector metrics."""
        success_rate = (
            self._successful_injections / self._total_injections
            if self._total_injections > 0
            else 0.0
        )

        return {
            "total_injections": self._total_injections,
            "successful_injections": self._successful_injections,
            "success_rate": success_rate,
            "graphrag_queries_total": self._graphrag_queries_total,
            "min_test_coverage": self.min_test_coverage,
            "min_enhanced_score": self.min_enhanced_score,
            "ranking_strategy": self.ranking_strategy.value,
        }


def create_history_injector(
    graph_service: NeptuneGraphService | None = None,
    min_test_coverage: int = 1,
    min_enhanced_score: float = 0.4,
) -> HistoryAwareBugInjector:
    """Factory function to create a HistoryAwareBugInjector.

    Args:
        graph_service: Neptune graph service for GraphRAG
        min_test_coverage: Minimum test files required
        min_enhanced_score: Minimum score threshold

    Returns:
        Configured HistoryAwareBugInjector instance
    """
    return HistoryAwareBugInjector(
        graph_service=graph_service,
        min_test_coverage=min_test_coverage,
        min_enhanced_score=min_enhanced_score,
    )
